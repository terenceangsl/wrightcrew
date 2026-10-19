"""Cadre driver: runs queued agent lanes one at a time, with no orchestrator in the loop.

Generalised from the Auto Crawler week driver (2026-10). See docs/pipeline.md and docs/lessons.md.

  python cadre/driver.py run                    # the USER starts this, in their own terminal (L-07)
  python cadre/driver.py status
  python cadre/driver.py add ID ROLE PROMPT [--state draft|queued|hold] [--maker M] [--checker C] [--front] [--order N]
  python cadre/driver.py set-state ID STATE [--checker C] [--note TEXT]
  python cadre/driver.py stop                   # creates the stop file; the driver exits before its next lane

All state lives in <runtime_dir>/queue.json. Change it ONLY through this CLI; never rename files (L-16).
Config: cadre.config.json in the repo root (see cadre.config.example.json).
"""
import argparse, datetime, json, os, subprocess, sys, time

STATES = ["draft", "checked", "queued", "hold", "running", "landed", "reviewed", "stopped", "failed", "parked"]
SHELL_SAFETY = (
    "SHELL SAFETY (mandatory): in Git Bash NEVER put PowerShell code containing $ inside double quotes; use single "
    "quotes or a .ps1 file run with `powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File x.ps1`. "
    "ALWAYS pass -NonInteractive to powershell. Wrap any command that could hang in `timeout 600 <cmd>`. "
    "Close every process you start, by PID.\n")


# ---------- config and paths ----------
def load_config(path):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    root = os.path.abspath(cfg.get("repo_root", os.path.dirname(os.path.abspath(path))))
    cfg["repo_root"] = root
    cfg["runtime_dir"] = os.path.join(root, cfg.get("runtime_dir", ".cadre/run"))
    os.makedirs(cfg["runtime_dir"], exist_ok=True)
    return cfg

def P(cfg, name): return os.path.join(cfg["runtime_dir"], name)
def now(): return datetime.datetime.now()
def stamp(): return now().strftime("%Y-%m-%d %H:%M")

def log(cfg, msg):
    line = f"{stamp()} {msg}"
    print(line, flush=True)
    with open(P(cfg, "driver.log"), "a", encoding="utf-8") as f: f.write(line + "\n")


# ---------- queue.json with a simple lock (driver and CLI may both write) ----------
class QueueLock:
    def __init__(self, cfg): self.path = P(cfg, "queue.lock")
    def __enter__(self):
        for _ in range(200):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY); os.write(fd, str(os.getpid()).encode()); os.close(fd)
                return self
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(self.path) > 60: os.remove(self.path); continue  # stale lock
                except OSError: pass
                time.sleep(0.1)
        raise SystemExit("ABORT: queue.lock busy for 20 s")
    def __exit__(self, *a):
        try: os.remove(self.path)
        except OSError: pass

def read_q(cfg):
    p = P(cfg, "queue.json")
    if not os.path.exists(p): return {"items": []}
    with open(p, encoding="utf-8") as f: return json.load(f)

def write_q(cfg, q):
    p = P(cfg, "queue.json"); tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(q, f, indent=2)
    os.replace(tmp, p)

def find(q, item_id):
    for it in q["items"]:
        if it["id"] == item_id: return it
    return None

def update_item(cfg, item_id, **fields):
    with QueueLock(cfg):
        q = read_q(cfg); it = find(q, item_id)
        if it is None: raise SystemExit(f"no item {item_id}")
        it.update(fields); it["updated"] = stamp(); write_q(cfg, q)
        return it

def add_item(cfg, item_id, role, prompt, state="draft", maker="", checker="", front=False, order=None):
    if state not in STATES: raise SystemExit(f"bad state {state}")
    with QueueLock(cfg):
        q = read_q(cfg)
        if find(q, item_id): raise SystemExit(f"item {item_id} already exists (never overwrite, L-17)")
        orders = [it["order"] for it in q["items"]] or [0]
        if order is None: order = (min(orders) - 10) if front else (max(orders) + 10)
        q["items"].append({"id": item_id, "role": role, "prompt": prompt, "state": state, "order": order,
                           "maker": maker, "checker": checker, "attempts": 0, "commit": None,
                           "note": "", "added": stamp(), "updated": stamp()})
        write_q(cfg, q)


# ---------- environment checks ----------
def pid_alive(pid):
    if os.name == "nt":
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
        return str(pid) in r.stdout
    try: os.kill(pid, 0); return True
    except OSError: return False

def guarded_clean(cfg):
    paths = cfg.get("guarded_paths", [])
    if not paths: return True
    r = subprocess.run(["git", "status", "--short", "--"] + paths, cwd=cfg["repo_root"], capture_output=True, text=True)
    return r.returncode == 0 and r.stdout.strip() == ""

def model_up(cfg):
    url = cfg.get("health_url")
    if not url: return True
    try:
        import urllib.request
        urllib.request.urlopen(url, timeout=15).read(); return True
    except Exception:
        return False

def commits_for(cfg, item_id, since_iso):
    r = subprocess.run(["git", "log", f"--since={since_iso}", "--format=%H%x09%s"], cwd=cfg["repo_root"],
                       capture_output=True, text=True)
    tag = f"[{item_id}]"
    return [ln.split("\t", 1) for ln in r.stdout.splitlines() if tag in ln]


# ---------- lanes ----------
def run_lane(cfg, it):
    role_cfg = cfg["roles"][it["role"]]
    name = f"{it['id']}_a{max(1, it['attempts'])}".replace("/", "_")   # attempts is already counted at pick time
    lane_log = P(cfg, f"lane_{name}.log")
    launch = P(cfg, f"lane_{name}_launch.txt")
    prompt_path = os.path.join(cfg["repo_root"], it["prompt"])
    task = (f"TASK ({it['role']} role, card {it['id']}): follow {prompt_path} exactly; that card only, then STOP. "
            f"Every commit subject starts with [{it['id']}].\n")
    with open(launch, "w", encoding="utf-8", newline="\n") as f: f.write(task + SHELL_SAFETY)
    cmd = [a.format(tools=role_cfg["tools"], name=name, launch=launch, log=lane_log,
                    timeout=str(cfg.get("lane_timeout_s", 14400)), model=cfg.get("model", ""))
           for a in cfg["runner"]]
    log(cfg, f"LAUNCH {it['role']} {it['id']} -> {lane_log}")
    rc = subprocess.run(cmd, cwd=cfg["repo_root"]).returncode
    log(cfg, f"EXIT {it['id']} rc={rc}")
    return rc

def outcome(cfg, it, rc, since_iso):
    hits = commits_for(cfg, it["id"], since_iso)
    if any("CARD-CONFLICT" in s for _, s in hits): return "stopped", (hits[0][0] if hits else None)
    if rc == 0 and hits and guarded_clean(cfg): return "landed", hits[0][0]   # newest first
    if it["role"] != "builder" and rc == 0: return "landed", (hits[0][0] if hits else None)
    return "failed", (hits[0][0] if hits else None)

def queue_review(cfg, it, commit):
    tpl_path = os.path.join(cfg["repo_root"], cfg["review_template"])
    with open(tpl_path, encoding="utf-8") as f: tpl = f.read()
    rid = f"{it['id']}-REV"
    rel_dir = os.path.relpath(cfg["runtime_dir"], cfg["repo_root"])
    prompt_rel = os.path.join(rel_dir, "prompts", f"{rid}.md")
    os.makedirs(os.path.dirname(os.path.join(cfg["repo_root"], prompt_rel)), exist_ok=True)
    body = (tpl.replace("{commit}", commit).replace("{id}", it["id"])
               .replace("{report_path}", os.path.join(rel_dir, "reviews", f"{rid}.md"))
               .replace("{fix_draft_path}", os.path.join(rel_dir, "reviews", f"{rid}_fixcard.md")))
    os.makedirs(os.path.join(cfg["runtime_dir"], "reviews"), exist_ok=True)
    with open(os.path.join(cfg["repo_root"], prompt_rel), "w", encoding="utf-8") as f: f.write(body)
    try:
        add_item(cfg, rid, "review", prompt_rel, state="queued", maker="driver", checker="n/a (read-only)", front=True)
        log(cfg, f"REVIEW queued {rid} for {commit[:8]}")
    except SystemExit as e:
        log(cfg, f"review not queued: {e}")


# ---------- the loop ----------
def cmd_run(cfg):
    pidf = P(cfg, "driver.pid")
    if os.path.exists(pidf):
        old = open(pidf).read().strip()
        if old.isdigit() and pid_alive(int(old)): raise SystemExit(f"ABORT: a driver is already running (pid {old})")
    with open(pidf, "w") as f: f.write(str(os.getpid()))
    deadline = datetime.datetime.fromisoformat(cfg["deadline"]) if cfg.get("deadline") else None
    stops = [P(cfg, s) for s in cfg.get("stop_files", ["STOP", "USER_BACK"])]
    max_fails = cfg.get("max_builder_fail_streak", 2)
    fails = 0
    log(cfg, f"START pid {os.getpid()} deadline {deadline}")
    try:
        while True:
            if deadline and now() >= deadline: log(cfg, "deadline reached"); break
            hit = [s for s in stops if os.path.exists(s)]
            if hit: log(cfg, f"stop file {hit[0]}"); break
            if not model_up(cfg): log(cfg, "model endpoint down; waiting 5 min"); time.sleep(300); continue
            with QueueLock(cfg):
                q = read_q(cfg)
                cands = sorted((it for it in q["items"] if it["state"] == "queued"), key=lambda it: it["order"])
                pick = None
                for it in cands:
                    if it["role"] == "builder" and (fails >= max_fails or not guarded_clean(cfg)): continue
                    pick = it; break
                if pick:
                    pick["state"] = "running"; pick["attempts"] += 1; pick["updated"] = stamp(); write_q(cfg, q)
            if pick is None:
                if cfg.get("refill_prompt") and not cfg.get("_refilled_since_last_lane"):
                    run_refill(cfg); cfg["_refilled_since_last_lane"] = True; continue
                log(cfg, "nothing queued; waiting 30 min"); time.sleep(1800); cfg["_refilled_since_last_lane"] = False; continue
            cfg["_refilled_since_last_lane"] = False
            since = (now() - datetime.timedelta(minutes=1)).isoformat(timespec="seconds")
            rc = run_lane(cfg, pick)
            state, commit = outcome(cfg, pick, rc, since)
            update_item(cfg, pick["id"], state=state, commit=commit, note=f"rc={rc}")
            log(cfg, f"OUTCOME {pick['id']} {state} {commit or ''}")
            if pick["role"] == "builder":
                fails = 0 if state in ("landed", "stopped") else fails + 1
                if not guarded_clean(cfg): log(cfg, "WARNING: guarded paths dirty after a builder lane; builder lanes pause")
                if state == "landed" and cfg.get("review_after_builder") and commit: queue_review(cfg, pick, commit)
            time.sleep(cfg.get("pause_between_lanes_s", 60))
    finally:
        try: os.remove(pidf)
        except OSError: pass
        log(cfg, "STOP")

def run_refill(cfg):
    it = {"id": "REFILL-" + now().strftime("%m%d%H%M"), "role": "docs", "prompt": cfg["refill_prompt"], "attempts": 0}
    rc = run_lane(cfg, it)
    if cfg.get("refill_autoqueue"):   # default false: drafts wait for a checker (L-12)
        with QueueLock(cfg):
            q = read_q(cfg)
            for x in q["items"]:
                if x["state"] == "draft" and x.get("maker") == "refill":
                    x["state"] = "queued"; x["note"] = "auto-queued unchecked (refill_autoqueue)"; x["updated"] = stamp()
            write_q(cfg, q)
    log(cfg, f"REFILL rc={rc}")


# ---------- CLI ----------
def cmd_status(cfg):
    q = read_q(cfg)
    pidf = P(cfg, "driver.pid")
    alive = os.path.exists(pidf) and open(pidf).read().strip().isdigit() and pid_alive(int(open(pidf).read().strip()))
    print(f"driver: {'RUNNING pid ' + open(pidf).read().strip() if alive else 'not running'}")
    counts = {}
    for it in q["items"]: counts[it["state"]] = counts.get(it["state"], 0) + 1
    print("counts: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    for it in sorted(q["items"], key=lambda it: it["order"]):
        if it["state"] in ("landed", "reviewed") and "--all" not in sys.argv: continue
        print(f"  {it['order']:>6} {it['state']:<8} {it['role']:<8} {it['id']:<22} maker={it['maker'] or '-'} "
              f"checker={it['checker'] or '-'} {('commit=' + it['commit'][:8]) if it.get('commit') else ''} {it.get('note', '')}")

def main():
    ap = argparse.ArgumentParser(description="Cadre driver")
    ap.add_argument("--config", default="cadre.config.json")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run"); s = sub.add_parser("status"); s.add_argument("--all", action="store_true"); sub.add_parser("stop")
    a = sub.add_parser("add"); a.add_argument("id"); a.add_argument("role"); a.add_argument("prompt")
    a.add_argument("--state", default="draft"); a.add_argument("--maker", default=""); a.add_argument("--checker", default="")
    a.add_argument("--front", action="store_true"); a.add_argument("--order", type=float)
    st = sub.add_parser("set-state"); st.add_argument("id"); st.add_argument("state")
    st.add_argument("--checker"); st.add_argument("--note")
    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.cmd == "run": cmd_run(cfg)
    elif args.cmd == "status": cmd_status(cfg)
    elif args.cmd == "stop":
        open(P(cfg, cfg.get("stop_files", ["STOP"])[0]), "w").write(stamp()); print("stop file written")
    elif args.cmd == "add":
        if args.role not in cfg["roles"]: raise SystemExit(f"unknown role {args.role}; roles: {list(cfg['roles'])}")
        if args.state == "queued" and args.role == "builder" and not args.checker:
            raise SystemExit("a builder item cannot be queued without --checker (maker needs a checker, L-12)")
        add_item(cfg, args.id, args.role, args.prompt, args.state, args.maker, args.checker, args.front, args.order)
        print(f"added {args.id} as {args.state}")
    elif args.cmd == "set-state":
        if args.state not in STATES: raise SystemExit(f"bad state; one of {STATES}")
        q = read_q(cfg); it = find(q, args.id)
        if it is None: raise SystemExit(f"no item {args.id}")
        if it["state"] == "running": raise SystemExit("item is running; wait for it to finish (L-16)")
        if args.state == "queued" and it["role"] == "builder" and not (args.checker or it.get("checker")):
            raise SystemExit("a builder item cannot be queued without a checker (L-12): pass --checker")
        fields = {"state": args.state}
        if args.checker: fields["checker"] = args.checker
        if args.note: fields["note"] = args.note
        update_item(cfg, args.id, **fields); print(f"{args.id} -> {args.state}")

if __name__ == "__main__":
    main()
