"""Cadre driver: runs queued agent lanes one at a time, with no orchestrator in the loop.

Generalised from the Auto Crawler week driver (2026-10). See docs/pipeline.md and docs/lessons.md.
Requires Python 3.9+ and git on PATH. Run every command from the repo root.

  python cadre/driver.py run                    # the USER starts this, in their own terminal (L-07)
  python cadre/driver.py status [--all]
  python cadre/driver.py add ID ROLE PROMPT [--state draft|queued|hold] [--maker M] [--checker C] [--front] [--order N]
  python cadre/driver.py set-state ID STATE [--checker C] [--note TEXT] [--force]
  python cadre/driver.py reset-streak           # re-enable builder lanes after the failure-streak pause
  python cadre/driver.py recover                # mark orphaned `running` items failed (only when no driver runs)
  python cadre/driver.py stop                   # writes the stop file; a running lane is ended too

All state lives in <runtime_dir>/queue.json, changed ONLY through this CLI; never rename files (L-16).
"""
import argparse, datetime, json, os, re, signal, subprocess, sys, time

STATES = ["draft", "checked", "queued", "hold", "running", "landed", "reviewed", "stopped", "failed", "parked"]
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SHELL_SAFETY = (
    "SHELL SAFETY (mandatory): in Git Bash NEVER put PowerShell code containing $ inside double quotes; use single "
    "quotes or a .ps1 file run with `powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File x.ps1`. "
    "ALWAYS pass -NonInteractive to powershell. Wrap any command that could hang in `timeout 600 <cmd>`. "
    "Close every process you start, by PID.\n")
READ_ONLY_NOTE = "READ-ONLY ROLE: do not edit or commit anything under the guarded paths: {paths}.\n"


# ---------- config and paths ----------
def load_config(path):
    if not os.path.exists(path): raise SystemExit(f"no config at {path}; copy cadre.config.example.json")
    with open(path, encoding="utf-8") as f: cfg = json.load(f)
    root = os.path.abspath(cfg.get("repo_root", "."))
    cfg["repo_root"] = root
    cfg["runtime_dir"] = os.path.join(root, cfg.get("runtime_dir", ".cadre/run"))
    os.makedirs(cfg["runtime_dir"], exist_ok=True)
    for r in ("builder",):
        if r not in cfg.get("roles", {}): raise SystemExit(f"config.roles must define '{r}'")
    if cfg.get("deadline"):
        d = datetime.datetime.fromisoformat(cfg["deadline"])
        if d.tzinfo is not None: d = d.astimezone().replace(tzinfo=None)   # compare in local naive time
        cfg["_deadline"] = d
    return cfg

def P(cfg, name): return os.path.join(cfg["runtime_dir"], name)
def now(): return datetime.datetime.now()
def stamp(): return now().strftime("%Y-%m-%d %H:%M")

def log(cfg, msg):
    line = f"{stamp()} {msg}"
    print(line, flush=True)
    with open(P(cfg, "driver.log"), "a", encoding="utf-8") as f: f.write(line + "\n")


# ---------- processes ----------
def pid_alive(pid):
    if pid is None: return False
    if os.name == "nt":
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True)
        return re.search(rf"\b{pid}\b", r.stdout) is not None
    try: os.kill(pid, 0); return True
    except OSError: return False

def kill_tree(pid):
    """Kill a process and all its children, by PID (never by image name, L-04)."""
    if not pid_alive(pid): return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)
    else:
        try: os.killpg(os.getpgid(pid), signal.SIGKILL)
        except OSError: pass


# ---------- queue.json with a lock (driver and CLI both write) ----------
class QueueLock:
    def __init__(self, cfg): self.path = P(cfg, "queue.lock")
    def __enter__(self):
        for _ in range(300):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, str(os.getpid()).encode()); os.close(fd)
                return self
            except FileExistsError:
                try:
                    holder = open(self.path).read().strip()
                    stale = time.time() - os.path.getmtime(self.path) > 60
                    if stale and not (holder.isdigit() and pid_alive(int(holder))): os.remove(self.path); continue
                except OSError: pass
                time.sleep(0.1)
        raise SystemExit("ABORT: queue.lock busy for 30 s")
    def __exit__(self, *a):
        try: os.remove(self.path)
        except OSError: pass

def read_q(cfg):
    p = P(cfg, "queue.json")
    if not os.path.exists(p): return {"items": [], "builder_fail_streak": 0}
    for _ in range(50):
        try:
            with open(p, encoding="utf-8") as f: q = json.load(f)
            q.setdefault("builder_fail_streak", 0); return q
        except (PermissionError, json.JSONDecodeError): time.sleep(0.1)
    raise SystemExit("ABORT: cannot read queue.json")

def write_q(cfg, q):
    p = P(cfg, "queue.json"); tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(q, f, indent=2)
    for _ in range(50):   # Windows: os.replace fails while a reader holds the file open (I-6)
        try: os.replace(tmp, p); return
        except PermissionError: time.sleep(0.1)
    raise SystemExit("ABORT: cannot replace queue.json (held open)")

def find(q, item_id):
    for it in q["items"]:
        if it["id"] == item_id: return it
    return None

def mutate(cfg, fn):
    with QueueLock(cfg):
        q = read_q(cfg); r = fn(q); write_q(cfg, q); return r

def update_item(cfg, item_id, **fields):
    def f(q):
        it = find(q, item_id)
        if it is None: raise SystemExit(f"no item {item_id}")
        it.update(fields); it["updated"] = stamp()
    mutate(cfg, f)

def add_item(cfg, item_id, role, prompt, state="draft", maker="", checker="", front=False, order=None, extra=None):
    if not ID_RE.match(item_id): raise SystemExit(f"bad id {item_id!r}: use letters, digits, . _ - (max 64)")
    if state not in STATES or state == "running": raise SystemExit(f"bad initial state {state}")
    def f(q):
        if find(q, item_id): raise SystemExit(f"item {item_id} already exists (never overwrite, L-17)")
        orders = [it["order"] for it in q["items"]] or [0]
        o = order if order is not None else ((min(orders) - 10) if front else (max(orders) + 10))
        it = {"id": item_id, "role": role, "prompt": prompt, "state": state, "order": o, "maker": maker,
              "checker": checker, "attempts": 0, "commits": [], "lane_pid": None, "note": "",
              "added": stamp(), "updated": stamp()}
        if extra: it.update(extra)
        q["items"].append(it)
    mutate(cfg, f)


# ---------- git ----------
def git(cfg, *args):
    r = subprocess.run(["git", "-c", "i18n.logOutputEncoding=UTF-8", *args], cwd=cfg["repo_root"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")   # C-1
    return r.returncode, r.stdout

def head(cfg):
    rc, out = git(cfg, "rev-parse", "HEAD")
    return out.strip() if rc == 0 else None

def card_commits(cfg, item_id, start, end="HEAD"):
    """Commits in start..end whose subject STARTS with [ID] (I-2). Oldest first."""
    rng = f"{start}..{end}" if start else end
    rc, out = git(cfg, "log", "--reverse", "--format=%H%x09%s", rng)
    tag = f"[{item_id}]"
    return [ln.split("\t", 1) for ln in out.splitlines() if "\t" in ln and ln.split("\t", 1)[1].lstrip().startswith(tag)]

def guarded_dirty(cfg):
    paths = cfg.get("guarded_paths", [])
    if not paths: return ""
    rc, out = git(cfg, "status", "--short", "--", *paths)
    return out.strip() if rc == 0 else "git status failed"

def touched_guarded(cfg, start):
    paths = cfg.get("guarded_paths", [])
    if not paths or not start: return ""
    rc, out = git(cfg, "diff", "--name-only", f"{start}..HEAD", "--", *paths)
    return out.strip()

def model_up(cfg):
    url = cfg.get("health_url")
    if not url: return True
    try:
        import urllib.request
        urllib.request.urlopen(url, timeout=15).read(); return True
    except Exception:
        return False


# ---------- stop conditions ----------
def stop_reason(cfg):
    for s in cfg.get("stop_files", ["STOP", "USER_BACK"]):
        if os.path.exists(P(cfg, s)): return f"stop file {s}"
    if cfg.get("_deadline") and now() >= cfg["_deadline"]: return "deadline reached"
    return None

def nap(cfg, seconds):
    """Sleep in small steps so stop files and the deadline are noticed (I-5)."""
    end = time.time() + seconds
    while time.time() < end:
        if stop_reason(cfg): return
        time.sleep(min(10, max(0, end - time.time())))


# ---------- lanes ----------
def run_lane(cfg, it):
    """Returns (rc, note). Never raises: any error becomes rc=-1 with a note (C-2)."""
    try:
        role_cfg = cfg["roles"][it["role"]]
        name = f"{it['id']}_a{max(1, it['attempts'])}"
        lane_log = P(cfg, f"lane_{name}.log"); launch = P(cfg, f"lane_{name}_launch.txt")
        prompt_path = os.path.join(cfg["repo_root"], it["prompt"])
        if not os.path.exists(prompt_path): return -1, f"prompt missing: {it['prompt']}"
        text = (f"TASK ({it['role']} role, card {it['id']}): follow {prompt_path} exactly; that card only, then STOP. "
                f"Every commit subject starts with [{it['id']}].\n" + SHELL_SAFETY)
        if it["role"] != "builder":
            text += READ_ONLY_NOTE.format(paths=", ".join(cfg.get("guarded_paths", [])) or "(none)")
        with open(launch, "w", encoding="utf-8", newline="\n") as f: f.write(text)
        tmo = int(cfg.get("lane_timeout_s", 14400))
        fill = {"tools": role_cfg["tools"], "name": name, "launch": launch, "log": lane_log,
                "timeout": str(tmo), "model": cfg.get("model", "")}
        cmd = []
        for a in cfg["runner"]:
            for k, v in fill.items(): a = a.replace("{" + k + "}", v)   # plain replace: braces elsewhere are safe
            cmd.append(a)
        kw = {"cwd": cfg["repo_root"]}
        if os.name != "nt": kw["start_new_session"] = True
        proc = subprocess.Popen(cmd, **kw)
        update_item(cfg, it["id"], lane_pid=proc.pid)
        log(cfg, f"LAUNCH {it['role']} {it['id']} pid {proc.pid} -> {lane_log}")
        backstop = time.time() + tmo + 600   # if the runner ignores {timeout}
        while proc.poll() is None:
            why = stop_reason(cfg) if cfg.get("stop_kills_running_lane", True) else None
            if why or time.time() > backstop:
                note = why or "backstop timeout"
                log(cfg, f"ENDING lane {it['id']} ({note})"); kill_tree(proc.pid); proc.wait(30)
                return -2, note
            time.sleep(5)
        log(cfg, f"EXIT {it['id']} rc={proc.returncode}")
        return proc.returncode, ""
    except Exception as e:   # noqa: BLE001 - any error must release the item
        return -1, f"driver error: {type(e).__name__}: {e}"

def decide(cfg, it, rc, note, start):
    commits = card_commits(cfg, it["id"], start)
    shas = [c[0] for c in commits]
    if rc == -2: return "failed", shas, note
    if it["role"] == "builder":
        conflict = any(s.lstrip()[len(it["id"]) + 2:].lstrip().upper().startswith("CARD-CONFLICT") for _, s in commits)
        if conflict: return "stopped", shas, note or "CARD-CONFLICT"
        if rc == 0 and commits and not guarded_dirty(cfg): return "landed", shas, note
        return "failed", shas, note or ("no [ID] commit" if not commits else "guarded paths dirty")
    # read-only roles (I-7)
    t = touched_guarded(cfg, start)
    if t or guarded_dirty(cfg): return "failed", shas, "READ-ONLY VIOLATION: guarded paths changed by a non-builder lane"
    if it["role"] == "review":
        rp = os.path.join(cfg["repo_root"], it.get("report", ""))
        if not it.get("report") or not os.path.exists(rp): return "failed", shas, "review wrote no report"
    return ("landed" if rc == 0 else "failed"), shas, note

def queue_review(cfg, it, shas):
    rid = f"{it['id']}-REV"
    if rid in [x["id"] for x in read_q(cfg)["items"]]: log(cfg, f"review {rid} exists; not re-queued"); return
    tpl_path = os.path.join(cfg["repo_root"], cfg["review_template"])
    with open(tpl_path, encoding="utf-8") as f: tpl = f.read()
    rel = os.path.relpath(cfg["runtime_dir"], cfg["repo_root"])
    prompt_rel = os.path.join(rel, "prompts", f"{rid}.md")
    report_rel = os.path.join(rel, "reviews", f"{rid}.md")
    rng = f"{shas[0]}^..{shas[-1]}"   # the card's whole range, code + records (I-1)
    body = (tpl.replace("{commit}", rng).replace("{commits}", " ".join(shas)).replace("{id}", it["id"])
               .replace("{report_path}", report_rel).replace("{fix_draft_path}", os.path.join(rel, "reviews", f"{rid}_fixcard.md")))
    os.makedirs(os.path.dirname(os.path.join(cfg["repo_root"], prompt_rel)), exist_ok=True)
    os.makedirs(os.path.join(cfg["runtime_dir"], "reviews"), exist_ok=True)
    with open(os.path.join(cfg["repo_root"], prompt_rel), "w", encoding="utf-8") as f: f.write(body)
    add_item(cfg, rid, "review", prompt_rel, state="queued", maker="driver", checker="n/a (read-only)", front=True,
             extra={"report": report_rel, "parent": it["id"]})
    log(cfg, f"REVIEW queued {rid} for {rng}")

def close_review(cfg, it):
    """A CLEAN review marks its parent `reviewed`; findings leave the parent `landed` with a note."""
    rp = os.path.join(cfg["repo_root"], it.get("report", ""))
    first = open(rp, encoding="utf-8", errors="replace").read(400).upper() if os.path.exists(rp) else ""
    if "CLEAN" in first and "FINDINGS" not in first: update_item(cfg, it["parent"], state="reviewed")
    else: update_item(cfg, it["parent"], note=f"review findings: {it.get('report')}")


# ---------- the loop ----------
def acquire_driver_lock(cfg):
    pidf = P(cfg, "driver.pid")
    for _ in range(2):
        try:
            fd = os.open(pidf, os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, str(os.getpid()).encode()); os.close(fd)
            return pidf
        except FileExistsError:
            old = open(pidf).read().strip()
            if old.isdigit() and pid_alive(int(old)): raise SystemExit(f"ABORT: a driver is already running (pid {old})")
            os.remove(pidf)
    raise SystemExit("ABORT: cannot take driver.pid")

def reconcile(cfg):
    """At startup: a `running` item whose lane is alive means a driver crashed mid-lane -> refuse to start;
    a dead one is marked failed (C-2)."""
    q = read_q(cfg)
    for it in q["items"]:
        if it["state"] == "running":
            if pid_alive(it.get("lane_pid")):
                raise SystemExit(f"ABORT: lane for {it['id']} (pid {it['lane_pid']}) is still alive; wait or kill that PID, then rerun")
            update_item(cfg, it["id"], state="failed", note="orphaned: driver ended mid-lane", lane_pid=None)
            log(cfg, f"RECOVER {it['id']} -> failed (orphaned)")

def cmd_run(cfg):
    leftover = stop_reason(cfg)
    if leftover: raise SystemExit(f"ABORT: {leftover} present before start; remove it first")
    pidf = acquire_driver_lock(cfg)
    max_fails = cfg.get("max_builder_fail_streak", 2)
    refilled_this_idle = False
    log(cfg, f"START pid {os.getpid()} deadline {cfg.get('_deadline')}")
    try:
        reconcile(cfg)
        while True:
            why = stop_reason(cfg)
            if why: log(cfg, why); break
            if not model_up(cfg): log(cfg, "model endpoint down; waiting 5 min"); nap(cfg, 300); continue
            blocked = []
            def pick_fn(q):
                cands = sorted((x for x in q["items"] if x["state"] == "queued"), key=lambda x: x["order"])
                for x in cands:
                    if x["role"] == "builder":
                        if q["builder_fail_streak"] >= max_fails: blocked.append(f"{x['id']} (fail streak)"); continue
                        d = guarded_dirty(cfg)
                        if d: blocked.append(f"{x['id']} (guarded paths dirty)"); continue
                    x["state"] = "running"; x["attempts"] += 1; x["updated"] = stamp(); x["lane_pid"] = None
                    return dict(x)
                return None
            it = mutate(cfg, pick_fn)
            if it is None:
                if blocked: log(cfg, "BLOCKED: " + ", ".join(blocked) + "  (fix, or `driver.py reset-streak`)")
                drafts = sum(1 for x in read_q(cfg)["items"] if x["state"] == "draft")
                if cfg.get("refill_prompt") and not refilled_this_idle and drafts < cfg.get("max_open_drafts", 6):
                    run_refill(cfg); refilled_this_idle = True; continue
                log(cfg, f"nothing runnable (drafts {drafts}); waiting 30 min"); nap(cfg, 1800); continue
            refilled_this_idle = False
            start = head(cfg)
            rc, note = run_lane(cfg, it)
            state, shas, note = decide(cfg, it, rc, note, start)
            update_item(cfg, it["id"], state=state, commits=shas, note=(note or f"rc={rc}"), lane_pid=None)
            log(cfg, f"OUTCOME {it['id']} {state} {' '.join(s[:8] for s in shas)} {note}")
            if it["role"] == "builder":
                def streak(q): q["builder_fail_streak"] = 0 if state in ("landed", "stopped") else q["builder_fail_streak"] + 1
                mutate(cfg, streak)
                if state == "landed" and cfg.get("review_after_builder") and shas: queue_review(cfg, it, shas)
            elif it["role"] == "review" and state == "landed" and it.get("parent"):
                close_review(cfg, it)
            nap(cfg, cfg.get("pause_between_lanes_s", 60))
    finally:
        try: os.remove(pidf)
        except OSError: pass
        log(cfg, "STOP")

def run_refill(cfg):
    rid = "REFILL-" + now().strftime("%m%d%H%M%S")
    it = {"id": rid, "role": cfg.get("refill_role", "docs"), "prompt": cfg["refill_prompt"], "attempts": 1}
    start = head(cfg)
    rc, note = run_lane(cfg, it)
    if touched_guarded(cfg, start) or guarded_dirty(cfg):
        log(cfg, "REFILL READ-ONLY VIOLATION: guarded paths changed; builder lanes pause")
        mutate(cfg, lambda q: q.__setitem__("builder_fail_streak", 99))
    if cfg.get("refill_autoqueue"):   # default false: drafts wait for a checker (L-12)
        def f(q):
            for x in q["items"]:
                if x["state"] == "draft" and x.get("maker") == "refill":
                    x["state"] = "queued"; x["checker"] = "NONE (refill_autoqueue)"; x["updated"] = stamp()
        mutate(cfg, f)
    log(cfg, f"REFILL rc={rc} {note}")


# ---------- CLI ----------
def cmd_status(cfg):
    with QueueLock(cfg): q = read_q(cfg)
    pidf = P(cfg, "driver.pid")
    pid = open(pidf).read().strip() if os.path.exists(pidf) else ""
    alive = pid.isdigit() and pid_alive(int(pid))
    print(f"driver: {'RUNNING pid ' + pid if alive else 'not running'} · builder fail streak {q['builder_fail_streak']}"
          f" · stop: {stop_reason(cfg) or 'none'}")
    counts = {}
    for it in q["items"]: counts[it["state"]] = counts.get(it["state"], 0) + 1
    print("counts: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    for it in sorted(q["items"], key=lambda x: x["order"]):
        if it["state"] in ("landed", "reviewed") and "--all" not in sys.argv: continue
        c = ",".join(s[:8] for s in it.get("commits") or [])
        print(f"  {it['order']:>6} {it['state']:<8} {it['role']:<8} {it['id']:<22} maker={it['maker'] or '-'} "
              f"checker={it['checker'] or '-'} {('commits=' + c) if c else ''} {it.get('note', '')}")

def cmd_set_state(cfg, a):
    if a.state not in STATES or a.state == "running": raise SystemExit(f"bad state; one of {[s for s in STATES if s != 'running']}")
    def f(q):
        it = find(q, a.id)
        if it is None: raise SystemExit(f"no item {a.id}")
        if it["state"] == "running" and not a.force:
            raise SystemExit("item is running; wait, or use --force if its lane is dead (L-16)")
        if it["state"] == "running" and pid_alive(it.get("lane_pid")):
            raise SystemExit(f"its lane pid {it['lane_pid']} is still alive; kill that PID first")
        if a.state == "queued" and it["role"] == "builder" and not (a.checker or it.get("checker")):
            raise SystemExit("a builder item cannot be queued without a checker (L-12): pass --checker")
        it["state"] = a.state; it["updated"] = stamp()
        if a.checker: it["checker"] = a.checker
        if a.note: it["note"] = a.note
    mutate(cfg, f); print(f"{a.id} -> {a.state}")

def main():
    ap = argparse.ArgumentParser(description="Cadre driver")
    ap.add_argument("--config", default="cadre.config.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run"); s = sub.add_parser("status"); s.add_argument("--all", action="store_true")
    sub.add_parser("stop"); sub.add_parser("reset-streak"); sub.add_parser("recover")
    a = sub.add_parser("add"); a.add_argument("id"); a.add_argument("role"); a.add_argument("prompt")
    a.add_argument("--state", default="draft"); a.add_argument("--maker", default=""); a.add_argument("--checker", default="")
    a.add_argument("--front", action="store_true"); a.add_argument("--order", type=float)
    st = sub.add_parser("set-state"); st.add_argument("id"); st.add_argument("state")
    st.add_argument("--checker"); st.add_argument("--note"); st.add_argument("--force", action="store_true")
    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.cmd == "run": cmd_run(cfg)
    elif args.cmd == "status": cmd_status(cfg)
    elif args.cmd == "stop":
        with open(P(cfg, cfg.get("stop_files", ["STOP"])[0]), "w") as f: f.write(stamp())
        print("stop file written; the driver ends the running lane and exits")
    elif args.cmd == "reset-streak": mutate(cfg, lambda q: q.__setitem__("builder_fail_streak", 0)); print("streak reset")
    elif args.cmd == "recover":
        pid = open(P(cfg, "driver.pid")).read().strip() if os.path.exists(P(cfg, "driver.pid")) else ""
        if pid.isdigit() and pid_alive(int(pid)): raise SystemExit(f"a driver is running (pid {pid}); stop it first")
        reconcile(cfg); print("recovered")
    elif args.cmd == "add":
        if args.role not in cfg["roles"]: raise SystemExit(f"unknown role {args.role}; roles: {list(cfg['roles'])}")
        if args.state == "queued" and args.role == "builder" and not args.checker:
            raise SystemExit("a builder item cannot be queued without --checker (maker needs a checker, L-12)")
        add_item(cfg, args.id, args.role, args.prompt, args.state, args.maker, args.checker, args.front, args.order)
        print(f"added {args.id} as {args.state}")
    elif args.cmd == "set-state": cmd_set_state(cfg, args)

if __name__ == "__main__":
    main()
