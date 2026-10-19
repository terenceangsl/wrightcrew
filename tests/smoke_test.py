"""Smoke tests for wrightcrew/driver.py: throwaway git repos plus a fake runner. No model, no network.

  python tests/smoke_test.py          # prints one ok/FAIL line per case, exits 1 on any FAIL

Each case replays a defect a checker reproduced (C-1, C-2, I-1, I-2, I-5, I-7) or a core path.
"""
import json, os, shutil, stat, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
DRIVER = os.path.join(HERE, "..", "wrightcrew", "driver.py")
REVIEW_TPL = os.path.join(HERE, "..", "templates", "review_prompt.md")

FAKE = r'''
import os, re, subprocess, sys, time
launch, log = sys.argv[1], sys.argv[2]
t = open(launch, encoding="utf-8").read()
cid = re.search(r"Every commit subject starts with \[([^\]]+)\]", t).group(1)
mode = open("mode.txt").read().strip() if os.path.exists("mode.txt") else "land"
def commit(msg, path="src/a.txt"):
    open(path, "a", encoding="utf-8").write(cid + "\n")
    subprocess.run(["git", "add", path]); subprocess.run(["git", "commit", "-qm", msg])
if cid.startswith("REFILL-"):
    pass   # a refill lane that writes nothing
elif cid.endswith("-REV"):
    t = open(re.search(r"follow (.+?) exactly;", t).group(1), encoding="utf-8").read()   # the review prompt file
    rp = re.search(r"(\.wrightcrew[\\/]run[\\/]reviews[\\/][^\s`]+-REV\.md)", t).group(1)
    os.makedirs(os.path.dirname(rp), exist_ok=True)
    if mode == "review_writes_code": commit(f"[{cid}] oops")
    open(rp, "w").write("UNCLEAN: 2 defects\n" if mode == "review_unclean" else "CLEAN\n")
elif mode in ("land", "review_writes_code", "review_unclean"): commit(f"[{cid}] landed")
elif mode == "unicode":        commit(f"[{cid}] landed ❌→ ok")
elif mode == "land_record":    commit(f"[{cid}] code"); commit(f"[{cid}] RECORD", "notes.txt")
elif mode == "conflict_text":  commit(f"[{cid}] landed; earlier CARD-CONFLICT resolved")
elif mode == "conflict":       open("notes.txt", "a").write("x"); subprocess.run(["git", "add", "notes.txt"]); subprocess.run(["git", "commit", "-qm", f"[{cid}] CARD-CONFLICT: bad card"])
elif mode == "hang":           time.sleep(600)
open(log, "w").write("ok")
'''

def rmtree(d):
    """git object files are read-only on Windows; clear the bit and retry."""
    def onerr(fn, path, _exc):
        os.chmod(path, stat.S_IWRITE); fn(path)
    shutil.rmtree(d, onerror=onerr)

def sh(cmd, cwd, **kw):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)

def make_repo(runner="python", refill=False):
    d = None
    d = tempfile.mkdtemp(prefix="wrightcrew_smoke_")
    os.makedirs(os.path.join(d, "src")); os.makedirs(os.path.join(d, "templates")); os.makedirs(os.path.join(d, "prompts"))
    for c in (["git", "init", "-q"], ["git", "config", "user.email", "t@t"], ["git", "config", "user.name", "t"],
              ["git", "config", "core.autocrlf", "false"]): sh(c, d)
    open(os.path.join(d, "src", "a.txt"), "w").write("a\n"); open(os.path.join(d, "notes.txt"), "w").write("n\n")
    sh(["git", "add", "-A"], d); sh(["git", "commit", "-qm", "init"], d)
    open(os.path.join(d, "fake_runner.py"), "w", encoding="utf-8").write(FAKE)
    shutil.copy(REVIEW_TPL, os.path.join(d, "templates", "review_prompt.md"))
    open(os.path.join(d, "prompts", "p.md"), "w").write("do it")
    cfg = {"repo_root": ".", "guarded_paths": ["src"], "runner": [runner, "fake_runner.py", "{launch}", "{log}"],
           "roles": {"builder": {"tools": "b"}, "review": {"tools": "r"}, "docs": {"tools": "d"}},
           "review_after_builder": True, "review_template": "templates/review_prompt.md", "pause_between_lanes_s": 0}
    if refill: cfg["refill_prompt"] = "prompts/p.md"
    json.dump(cfg, open(os.path.join(d, "wrightcrew.config.json"), "w"))
    return d

def drv(d, *args, timeout=120):
    return sh([sys.executable, DRIVER, *args], d, timeout=timeout)

def run_until_idle(d, seconds=40):
    """Start the driver, wait until it logs 'nothing runnable', then stop it."""
    p = subprocess.Popen([sys.executable, DRIVER, "run"], cwd=d, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    logf = os.path.join(d, ".wrightcrew", "run", "driver.log"); end = time.time() + seconds
    while time.time() < end and p.poll() is None:
        if os.path.exists(logf) and "nothing runnable" in open(logf, encoding="utf-8").read(): break
        time.sleep(0.5)
    open(os.path.join(d, ".wrightcrew", "run", "STOP"), "w").write("x")
    try: p.wait(30)
    except subprocess.TimeoutExpired: p.kill()
    return json.load(open(os.path.join(d, ".wrightcrew", "run", "queue.json"), encoding="utf-8"))

def state(q, i): return next(x for x in q["items"] if x["id"] == i)

results = []
def case(name, fn):
    d = None
    try:
        d = fn(); results.append(("ok", name))
    except AssertionError as e:
        results.append(("FAIL", f"{name}: {e}"))
    except Exception as e:  # noqa: BLE001
        results.append(("FAIL", f"{name}: {type(e).__name__}: {e}"))

def with_repo(mode, setup):
    d = make_repo(); open(os.path.join(d, "mode.txt"), "w").write(mode)
    try: return setup(d)
    finally: rmtree(d)

def t_guard():
    def s(d):
        r = drv(d, "add", "A", "builder", "prompts/p.md", "--state", "queued")
        assert "without --checker" in r.stderr + r.stdout, "unchecked builder was queued"
        assert drv(d, "add", "A", "builder", "prompts/p.md", "--state", "queued", "--checker", "opus").returncode == 0
        r = drv(d, "add", "A", "builder", "prompts/p.md")
        assert "already exists" in r.stderr + r.stdout, "duplicate id accepted"
        r = drv(d, "add", "bad id", "builder", "prompts/p.md")
        assert "bad id" in r.stderr + r.stdout, "bad id accepted"
    return with_repo("land", s)

def t_land_and_review():
    def s(d):
        drv(d, "add", "A", "builder", "prompts/p.md", "--state", "queued", "--checker", "opus")
        drv(d, "add", "B", "builder", "prompts/p.md", "--state", "draft")
        q = run_until_idle(d)
        assert state(q, "A")["state"] == "reviewed", f"A is {state(q, 'A')['state']}"
        assert state(q, "A-REV")["state"] == "landed", f"A-REV is {state(q, 'A-REV')['state']}"
        assert state(q, "B")["state"] == "draft", "draft ran"
    return with_repo("land", s)

def t_unicode():   # C-1
    def s(d):
        drv(d, "add", "U", "builder", "prompts/p.md", "--state", "queued", "--checker", "opus")
        q = run_until_idle(d)
        assert state(q, "U")["state"] in ("landed", "reviewed"), f"U is {state(q, 'U')['state']}"
    return with_repo("unicode", s)

def t_missing_runner():   # C-2
    d = make_repo(runner="no_such_runner_exe_xyz")
    try:
        drv(d, "add", "M", "builder", "prompts/p.md", "--state", "queued", "--checker", "opus")
        q = run_until_idle(d)
        assert state(q, "M")["state"] == "failed", f"M is {state(q, 'M')['state']} (should be failed, not stuck running)"
    finally: rmtree(d)

def t_review_range():   # I-1
    def s(d):
        drv(d, "add", "R", "builder", "prompts/p.md", "--state", "queued", "--checker", "opus")
        q = run_until_idle(d)
        assert len(state(q, "R")["commits"]) == 2, f"commits {state(q, 'R')['commits']}"
        body = open(os.path.join(d, ".wrightcrew", "run", "prompts", "R-REV.md"), encoding="utf-8").read()
        shas = state(q, "R")["commits"]
        assert f"..{shas[-1]}" in body and all(c in body for c in shas), "review prompt does not carry the card's commit range"
    return with_repo("land_record", s)

def t_conflict_text():   # I-2
    def s(d):
        drv(d, "add", "C", "builder", "prompts/p.md", "--state", "queued", "--checker", "opus")
        q = run_until_idle(d)
        assert state(q, "C")["state"] in ("landed", "reviewed"), f"C is {state(q, 'C')['state']}"
    return with_repo("conflict_text", s)

def t_conflict():
    def s(d):
        drv(d, "add", "K", "builder", "prompts/p.md", "--state", "queued", "--checker", "opus")
        q = run_until_idle(d)
        assert state(q, "K")["state"] == "stopped", f"K is {state(q, 'K')['state']}"
    return with_repo("conflict", s)

def t_review_readonly():   # I-7
    def s(d):
        drv(d, "add", "W", "builder", "prompts/p.md", "--state", "queued", "--checker", "opus")
        q = run_until_idle(d)
        assert state(q, "W-REV")["state"] == "failed", f"W-REV is {state(q, 'W-REV')['state']}"
    return with_repo("review_writes_code", s)

def t_stop_kills_lane():   # I-5
    def s(d):
        drv(d, "add", "H", "builder", "prompts/p.md", "--state", "queued", "--checker", "opus")
        p = subprocess.Popen([sys.executable, DRIVER, "run"], cwd=d, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(8); open(os.path.join(d, ".wrightcrew", "run", "STOP"), "w").write("x")
        p.wait(60)
        q = json.load(open(os.path.join(d, ".wrightcrew", "run", "queue.json"), encoding="utf-8"))
        assert state(q, "H")["state"] == "failed", f"H is {state(q, 'H')['state']}"
        assert "stop file" in state(q, "H")["note"], state(q, "H")["note"]
    return with_repo("hang", s)

def t_refill_empty_queue():   # v0.2 CRITICAL: refill crashed the driver
    d = make_repo(refill=True)
    try:
        p = subprocess.Popen([sys.executable, DRIVER, "run"], cwd=d, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logf = os.path.join(d, ".wrightcrew", "run", "driver.log"); end = time.time() + 40; text = ""
        while time.time() < end:
            text = open(logf, encoding="utf-8").read() if os.path.exists(logf) else ""
            if "nothing runnable" in text: break
            time.sleep(0.5)
        alive = p.poll() is None
        open(os.path.join(d, ".wrightcrew", "run", "STOP"), "w").write("x"); p.wait(30)
        assert "REFILL rc=0" in text, "no 'REFILL rc=0' in the log"
        assert "nothing runnable" in text and alive, "driver died after the refill lane"
    finally: rmtree(d)

def t_review_unclean():   # v0.2 IMPORTANT: substring verdict
    def s(d):
        drv(d, "add", "N", "builder", "prompts/p.md", "--state", "queued", "--checker", "opus")
        q = run_until_idle(d)
        assert state(q, "N")["state"] == "landed", f"N is {state(q, 'N')['state']} (UNCLEAN must not mark reviewed)"
        assert "review findings" in state(q, "N")["note"], state(q, "N")["note"]
    return with_repo("review_unclean", s)

for n, f in [("checker guard / duplicate / bad id", t_guard), ("land -> review -> reviewed; draft held", t_land_and_review),
             ("C-1 unicode subject", t_unicode), ("C-2 missing runner -> failed", t_missing_runner),
             ("I-1 review covers the card range", t_review_range), ("I-2 CARD-CONFLICT text mid-subject", t_conflict_text),
             ("CARD-CONFLICT prefix -> stopped", t_conflict), ("I-7 review lane writing code -> failed", t_review_readonly),
             ("I-5 stop file ends a running lane", t_stop_kills_lane),
             ("v0.2 refill on an empty queue keeps the driver alive", t_refill_empty_queue),
             ("v0.2 UNCLEAN review keeps the card landed", t_review_unclean)]:
    case(n, f)
for r, n in results: print(f"{r:<4} {n}")
print(f"{sum(r == 'ok' for r, _ in results)} ok / {sum(r == 'FAIL' for r, _ in results)} FAIL")
sys.exit(0 if all(r == "ok" for r, _ in results) else 1)
