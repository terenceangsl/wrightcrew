"""Example lane runner: runs ONE agent command with a hard timeout, logs its output, kills the whole process tree.

The driver calls it through cadre.config.json "runner", for example:
  python tools/run_lane.example.py --timeout 14400 --log <log> --launch <launch.txt> -- pi -p --provider local --model M --tools T

The launch text (the task, plus shell safety) is passed to the agent on stdin. Adapt the command after `--` to your agent
CLI: some take the prompt as an argument instead, which you can do with a wrapper or `@file` syntax.
Exit code = the agent's exit code, or 124 on timeout (L-21: the whole tree is killed, not just the top process).
"""
import argparse, os, signal, subprocess, sys, time

def kill_tree(p):
    if p.poll() is not None: return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
    else:
        try: os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except OSError: pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--launch", required=True)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    if not cmd: sys.exit("no agent command after --")
    kw = {}
    if os.name != "nt": kw["start_new_session"] = True
    else: kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    with open(a.launch, "rb") as stdin, open(a.log, "ab") as log:
        log.write(f"\n=== lane start {time.strftime('%Y-%m-%d %H:%M:%S')} cmd={cmd!r}\n".encode()); log.flush()
        p = subprocess.Popen(cmd, stdin=stdin, stdout=log, stderr=subprocess.STDOUT, **kw)
        try:
            rc = p.wait(timeout=a.timeout)
        except subprocess.TimeoutExpired:
            kill_tree(p); p.wait(30); rc = 124
            log.write(f"\n=== TIMEOUT after {a.timeout}s: process tree killed\n".encode())
        except KeyboardInterrupt:
            kill_tree(p); rc = 130
        log.write(f"=== lane end rc={rc}\n".encode())
    sys.exit(rc)

if __name__ == "__main__":
    main()
