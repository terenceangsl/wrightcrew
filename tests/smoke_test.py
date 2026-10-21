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
        assert drv(d, "add", "A", "builder", "prompts/p.md", "--state", "queued", "--maker", "sonnet", "--checker", "opus").returncode == 0
        r = drv(d, "add", "A", "builder", "prompts/p.md")
        assert "already exists" in r.stderr + r.stdout, "duplicate id accepted"
        r = drv(d, "add", "bad id", "builder", "prompts/p.md")
        assert "bad id" in r.stderr + r.stdout, "bad id accepted"
    return with_repo("land", s)

def t_land_and_review():
    def s(d):
        drv(d, "add", "A", "builder", "prompts/p.md", "--state", "queued", "--maker", "sonnet", "--checker", "opus")
        drv(d, "add", "B", "builder", "prompts/p.md", "--state", "draft")
        q = run_until_idle(d)
        assert state(q, "A")["state"] == "reviewed", f"A is {state(q, 'A')['state']}"
        assert state(q, "A-REV")["state"] == "landed", f"A-REV is {state(q, 'A-REV')['state']}"
        assert state(q, "B")["state"] == "draft", "draft ran"
    return with_repo("land", s)

def t_unicode():   # C-1
    def s(d):
        drv(d, "add", "U", "builder", "prompts/p.md", "--state", "queued", "--maker", "sonnet", "--checker", "opus")
        q = run_until_idle(d)
        assert state(q, "U")["state"] in ("landed", "reviewed"), f"U is {state(q, 'U')['state']}"
    return with_repo("unicode", s)

def t_missing_runner():   # C-2
    d = make_repo(runner="no_such_runner_exe_xyz")
    try:
        drv(d, "add", "M", "builder", "prompts/p.md", "--state", "queued", "--maker", "sonnet", "--checker", "opus")
        q = run_until_idle(d)
        assert state(q, "M")["state"] == "failed", f"M is {state(q, 'M')['state']} (should be failed, not stuck running)"
    finally: rmtree(d)

def t_review_range():   # I-1
    def s(d):
        drv(d, "add", "R", "builder", "prompts/p.md", "--state", "queued", "--maker", "sonnet", "--checker", "opus")
        q = run_until_idle(d)
        assert len(state(q, "R")["commits"]) == 2, f"commits {state(q, 'R')['commits']}"
        body = open(os.path.join(d, ".wrightcrew", "run", "prompts", "R-REV.md"), encoding="utf-8").read()
        shas = state(q, "R")["commits"]
        assert f"..{shas[-1]}" in body and all(c in body for c in shas), "review prompt does not carry the card's commit range"
    return with_repo("land_record", s)

def t_conflict_text():   # I-2
    def s(d):
        drv(d, "add", "C", "builder", "prompts/p.md", "--state", "queued", "--maker", "sonnet", "--checker", "opus")
        q = run_until_idle(d)
        assert state(q, "C")["state"] in ("landed", "reviewed"), f"C is {state(q, 'C')['state']}"
    return with_repo("conflict_text", s)

def t_conflict():
    def s(d):
        drv(d, "add", "K", "builder", "prompts/p.md", "--state", "queued", "--maker", "sonnet", "--checker", "opus")
        q = run_until_idle(d)
        assert state(q, "K")["state"] == "stopped", f"K is {state(q, 'K')['state']}"
    return with_repo("conflict", s)

def t_review_readonly():   # I-7
    def s(d):
        drv(d, "add", "W", "builder", "prompts/p.md", "--state", "queued", "--maker", "sonnet", "--checker", "opus")
        q = run_until_idle(d)
        assert state(q, "W-REV")["state"] == "failed", f"W-REV is {state(q, 'W-REV')['state']}"
    return with_repo("review_writes_code", s)

def t_stop_kills_lane():   # I-5
    def s(d):
        drv(d, "add", "H", "builder", "prompts/p.md", "--state", "queued", "--maker", "sonnet", "--checker", "opus")
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
        drv(d, "add", "N", "builder", "prompts/p.md", "--state", "queued", "--maker", "sonnet", "--checker", "opus")
        q = run_until_idle(d)
        assert state(q, "N")["state"] == "landed", f"N is {state(q, 'N')['state']} (UNCLEAN must not mark reviewed)"
        assert "review findings" in state(q, "N")["note"], state(q, "N")["note"]
    return with_repo("review_unclean", s)

def t_self_check_refused():   # W-02
    def s(d):
        r = drv(d, "add", "SELF", "builder", "prompts/p.md", "--state", "queued", "--maker", "opus", "--checker", "opus")
        assert r.returncode == 1, f"maker==checker accepted (rc {r.returncode})"
        r = drv(d, "add", "SELF2", "builder", "prompts/p.md", "--state", "queued", "--maker", "Opus", "--checker", " opus ")
        assert r.returncode == 1, "case/space variant accepted"
        drv(d, "add", "D", "builder", "prompts/p.md", "--maker", "opus")
        r = drv(d, "set-state", "D", "queued", "--checker", "OPUS")
        assert r.returncode == 1, f"set-state queued with checker==maker accepted (rc {r.returncode})"
        assert drv(d, "set-state", "D", "queued", "--checker", "sonnet").returncode == 0, "a different checker was refused"
    return with_repo("land", s)

def t_lock_empty_pid():   # W-04: an empty driver.pid is LOCKED, never deleted
    def s(d):
        rd = os.path.join(d, ".wrightcrew", "run"); os.makedirs(rd)
        pf = os.path.join(rd, "driver.pid"); open(pf, "w").close()
        p = subprocess.Popen([sys.executable, DRIVER, "run"], cwd=d, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try: out, _ = p.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            p.kill(); p.communicate(); raise AssertionError("run did not abort on an empty driver.pid")
        assert p.returncode != 0 and "ABORT" in out and "recover" in out, f"rc {p.returncode}: {out!r}"
        assert os.path.exists(pf), "the empty driver.pid was deleted"
    return with_repo("land", s)

def t_lock_not_deleted_by_other():   # W-04: finally deletes driver.pid only if it holds our pid
    def s(d):
        rd = os.path.join(d, ".wrightcrew", "run"); pf = os.path.join(rd, "driver.pid"); logf = os.path.join(rd, "driver.log")
        p = subprocess.Popen([sys.executable, DRIVER, "run"], cwd=d, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        end = time.time() + 30
        while time.time() < end and not (os.path.exists(logf) and "START" in open(logf, encoding="utf-8").read()): time.sleep(0.3)
        assert os.path.exists(pf), "driver did not start"
        open(pf, "w").write(str(os.getpid()))          # another LIVE pid (this test process) now owns the lock
        open(os.path.join(rd, "STOP"), "w").write("x")
        try: p.wait(40)
        except subprocess.TimeoutExpired: p.kill(); p.wait(); raise AssertionError("driver did not stop")
        assert os.path.exists(pf) and open(pf).read().strip() == str(os.getpid()), "driver deleted a lock it does not own"
    return with_repo("land", s)

def t_warn_missing_guarded():   # W-11
    d = make_repo()
    try:
        cfgp = os.path.join(d, "wrightcrew.config.json"); c = json.load(open(cfgp))
        c["guarded_paths"] = ["src", "no_such_dir"]; json.dump(c, open(cfgp, "w"))
        run_until_idle(d, seconds=15)
        text = open(os.path.join(d, ".wrightcrew", "run", "driver.log"), encoding="utf-8").read()
        assert "WARNING: guarded path 'no_such_dir' does not exist" in text, "no warning in the log"
        assert "guarded path 'src'" not in text, "warned about an existing path"
    finally: rmtree(d)

def t_status_ascii():   # W-14
    def s(d):
        r = drv(d, "status")
        assert r.returncode == 0 and "·" not in r.stdout and all(ord(ch) < 128 for ch in r.stdout), f"non-ASCII in status: {r.stdout!r}"
    return with_repo("land", s)

def t_queue_needs_maker():   # V-04
    def s(d):
        r = drv(d, "add", "NM", "builder", "prompts/p.md", "--state", "queued", "--checker", "opus")
        assert r.returncode == 1 and "maker" in r.stderr + r.stdout, f"queued add without --maker accepted (rc {r.returncode})"
        drv(d, "add", "NM2", "builder", "prompts/p.md")
        r = drv(d, "set-state", "NM2", "queued", "--checker", "opus")
        assert r.returncode == 1, f"set-state queued on an item with no maker accepted (rc {r.returncode})"
        assert drv(d, "add", "NM3", "docs", "prompts/p.md", "--state", "queued").returncode == 0, "docs item wrongly needs a maker"
    return with_repo("land", s)

def t_status_stale_lock():   # V-07
    def s(d):
        rd = os.path.join(d, ".wrightcrew", "run"); os.makedirs(rd)
        open(os.path.join(rd, "driver.pid"), "w").close()
        r = drv(d, "status")
        assert "stale lock" in r.stdout and "recover" in r.stdout, f"no stale-lock hint: {r.stdout!r}"
        open(os.path.join(rd, "driver.pid"), "w").write("not-a-pid")
        assert "stale lock" in drv(d, "status").stdout, "garbage pid not flagged"
    return with_repo("land", s)

def t_lock_released_on_early_error():   # V-08
    def s(d):
        rd = os.path.join(d, ".wrightcrew", "run"); os.makedirs(os.path.join(rd, "driver.log"))   # log() will raise
        r = drv(d, "run", timeout=30)
        assert r.returncode != 0, "run should fail when driver.log cannot be written"
        assert not os.path.exists(os.path.join(rd, "driver.pid")), "lock left behind after an early exception"
    return with_repo("land", s)

def t_recover_foreign_pid():   # V-05: a live pid that is not a driver (reused pid) does not block recover
    def s(d):
        rd = os.path.join(d, ".wrightcrew", "run"); os.makedirs(rd); pf = os.path.join(rd, "driver.pid")
        fp = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        try:
            open(pf, "w").write(str(fp.pid))
            r = drv(d, "recover")
            assert r.returncode == 0 and not os.path.exists(pf), f"recover refused a non-driver pid (rc {r.returncode}): {r.stdout!r} {r.stderr!r}"
        finally: fp.kill(); fp.wait()
    return with_repo("land", s)

def t_recover_owner_check():   # V-06: recover deletes driver.pid only if it still holds the value it read
    import contextlib, io
    drv_dir = os.path.dirname(os.path.abspath(DRIVER)); had_mod = "driver" in sys.modules; old_path = list(sys.path)   # W2-07
    sys.path.insert(0, drv_dir)
    import driver as D
    d = make_repo(); old_cwd = os.getcwd(); old_rec = D.reconcile; old_argv = sys.argv
    try:
        rd = os.path.join(d, ".wrightcrew", "run"); os.makedirs(rd); pf = os.path.join(rd, "driver.pid")
        open(pf, "w").write("999999999")                    # dead pid
        def racing_reconcile(cfg): open(pf, "w").write("424242")   # a new driver takes the lock during recover
        D.reconcile = racing_reconcile; os.chdir(d); sys.argv = ["driver.py", "recover"]
        try:
            with contextlib.redirect_stdout(io.StringIO()): D.main()   # W2-07: keep driver output out of the suite output
        except SystemExit as e: assert e.code not in (0, None), f"recover reported success after the lock changed (code {e.code})"
        assert os.path.exists(pf) and open(pf).read() == "424242", "recover deleted a driver.pid whose value changed"
    finally:
        D.reconcile = old_rec; sys.argv = old_argv; os.chdir(old_cwd); rmtree(d)
        sys.path[:] = old_path
        if not had_mod: sys.modules.pop("driver", None)

def t_queue_lock_stale_breaker():   # D-1: the stale breaker must not delete a live lock that replaced the one it judged
    drv_dir = os.path.dirname(os.path.abspath(DRIVER)); had_mod = "driver" in sys.modules; old_path = list(sys.path)
    sys.path.insert(0, drv_dir)
    import driver as D
    d = make_repo(); old_pa = D.pid_alive; old_spins = getattr(D.QueueLock, "SPINS", None)
    try:
        cfg = {"runtime_dir": os.path.join(d, ".wrightcrew", "run")}; os.makedirs(cfg["runtime_dir"])
        lk = os.path.join(cfg["runtime_dir"], "queue.lock"); live = str(os.getpid()) + "\n"   # newline marks waiter B's file
        open(lk, "w").write("999999999"); os.utime(lk, (time.time() - 120, time.time() - 120))   # stale, dead pid
        def racing_pid_alive(pid):   # waiter B replaces the lock while waiter C is still deciding
            os.remove(lk); open(lk, "w").write(live); return False
        D.pid_alive = racing_pid_alive; D.QueueLock.SPINS = 3
        try:
            with D.QueueLock(cfg): raise AssertionError("waiter C entered while waiter B's live lock existed")
        except SystemExit: pass   # gave up: acceptable
        assert os.path.exists(lk) and open(lk).read() == live, "the stale breaker deleted a live lock"
    finally:
        D.pid_alive = old_pa; rmtree(d)
        if old_spins is not None: D.QueueLock.SPINS = old_spins
        sys.path[:] = old_path
        if not had_mod: sys.modules.pop("driver", None)

def t_live_driver_blocks():   # W2-03: a REAL live driver still blocks a second run and recover, and status says RUNNING
    def s(d):
        rd = os.path.join(d, ".wrightcrew", "run"); pf = os.path.join(rd, "driver.pid"); logf = os.path.join(rd, "driver.log")
        p = subprocess.Popen([sys.executable, DRIVER, "run"], cwd=d, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            end = time.time() + 30
            while time.time() < end and not (os.path.exists(logf) and "START" in open(logf, encoding="utf-8").read()): time.sleep(0.3)
            assert os.path.exists(pf), "driver did not start"
            pid = open(pf).read().strip()
            r = drv(d, "run", timeout=60)
            assert r.returncode != 0 and "already running" in r.stdout + r.stderr, f"second run not refused (rc {r.returncode}): {r.stdout!r} {r.stderr!r}"
            r = drv(d, "recover", timeout=60)
            assert r.returncode == 1, f"recover on a live driver gave rc {r.returncode}: {r.stdout!r} {r.stderr!r}"
            assert os.path.exists(pf) and open(pf).read().strip() == pid, "recover touched a live driver's driver.pid"
            assert f"RUNNING pid {pid}" in drv(d, "status", timeout=60).stdout, "status does not say RUNNING"
        finally:
            open(os.path.join(rd, "STOP"), "w").write("x")
            try: p.wait(40)
            except subprocess.TimeoutExpired: p.kill(); p.wait()
    return with_repo("land", s)

def t_set_state_maker():   # V-10
    def s(d):
        assert drv(d, "add", "X", "builder", "prompts/p.md", "--state", "draft").returncode == 0
        r = drv(d, "set-state", "X", "queued", "--maker", "sonnet", "--checker", "opus")
        assert r.returncode == 0, f"set-state --maker refused (rc {r.returncode}): {r.stderr!r}"
        assert "maker=sonnet" in drv(d, "status").stdout, "maker not set"
        drv(d, "add", "Y", "builder", "prompts/p.md")
        r = drv(d, "set-state", "Y", "queued", "--maker", "opus", "--checker", "opus")
        assert r.returncode == 1, f"maker == checker accepted via set-state --maker (rc {r.returncode})"
    return with_repo("land", s)

for n, f in [("checker guard / duplicate / bad id", t_guard), ("land -> review -> reviewed; draft held", t_land_and_review),
             ("C-1 unicode subject", t_unicode), ("C-2 missing runner -> failed", t_missing_runner),
             ("I-1 review covers the card range", t_review_range), ("I-2 CARD-CONFLICT text mid-subject", t_conflict_text),
             ("CARD-CONFLICT prefix -> stopped", t_conflict), ("I-7 review lane writing code -> failed", t_review_readonly),
             ("I-5 stop file ends a running lane", t_stop_kills_lane),
             ("v0.2 refill on an empty queue keeps the driver alive", t_refill_empty_queue),
             ("v0.2 UNCLEAN review keeps the card landed", t_review_unclean),
             ("W-02 checker == maker refused (add, set-state)", t_self_check_refused),
             ("W-04 empty driver.pid is LOCKED; run aborts", t_lock_empty_pid),
             ("W-04 driver does not delete a lock it does not own", t_lock_not_deleted_by_other),
             ("W-11 missing guarded path warns", t_warn_missing_guarded),
             ("W-14 status output is ASCII", t_status_ascii),
             ("V-04 queued builder item needs a maker", t_queue_needs_maker),
             ("V-07 status flags a stale driver.pid", t_status_stale_lock),
             ("V-08 lock released after an early exception", t_lock_released_on_early_error),
             ("V-05 recover clears a driver.pid held by a non-driver process", t_recover_foreign_pid),
             ("V-06 recover does not delete a driver.pid that changed", t_recover_owner_check),
             ("D-1 queue.lock stale breaker keeps a live lock", t_queue_lock_stale_breaker),
             ("V-10 set-state --maker; maker == checker refused", t_set_state_maker),
             ("W2-03 a live real driver blocks run and recover; status RUNNING", t_live_driver_blocks)]:
    case(n, f)
for r, n in results: print(f"{r:<4} {n}")
print(f"{sum(r == 'ok' for r, _ in results)} ok / {sum(r == 'FAIL' for r, _ in results)} FAIL")
sys.exit(0 if all(r == "ok" for r, _ in results) else 1)
