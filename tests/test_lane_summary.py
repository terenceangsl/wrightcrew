"""Tests for tools/lane_summary.py. No model, no network.   python tests/test_lane_summary.py"""
import json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import lane_summary


def ev(**k):
    return json.dumps(k)


def msg(stop, *content, err=None):
    m = {"role": "assistant", "stopReason": stop, "content": list(content)}
    if err:
        m["errorMessage"] = err
    return ev(type="message_end", message=m)


def run(lines):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "lane.log")
        open(p, "w", encoding="utf-8").write("\n".join(lines) + "\n")
        return lane_summary.summarise(p), lane_summary.main([p])


results = []


def case(name, f):
    try:
        f()
        results.append(("ok", name))
    except Exception as e:
        results.append(("FAIL", f"{name}: {e!r}"))


def t_settled():
    r, rc = run(["== runner banner ==", ev(type="agent_start"),
                 msg("toolUse", {"type": "toolCall", "name": "bash"}, {"type": "toolCall", "name": "bash"}),
                 msg("stop", {"type": "text", "text": "done"}), ev(type="agent_settled")])
    assert r["settled"] and r["last_stop_reason"] == "stop" and r["tool_calls"] == {"bash": 2}, r
    assert r["non_json_lines"] == 1 and r["final_text_tail"] == "done", r
    assert rc == 0, rc


def t_not_settled():
    r, rc = run([ev(type="agent_start"), "{broken json", "[1,2]"])
    assert not r["settled"] and r["non_json_lines"] == 2 and rc == 2, (r, rc)


def t_errors_tail():
    r, _ = run([msg("error", err=f"e{i}") for i in range(5)])
    assert r["errors"] == ["e2", "e3", "e4"], r


def t_missing():
    assert lane_summary.main(["no_such_file.log"]) == 1


for n, f in [("settled run summarised", t_settled), ("unsettled run, bad lines counted, rc 2", t_not_settled),
             ("last 3 errors kept", t_errors_tail), ("missing file rc 1", t_missing)]:
    case(n, f)
for r, n in results:
    print(f"{r:<4} {n}")
print(f"{sum(r == 'ok' for r, _ in results)} ok / {sum(r == 'FAIL' for r, _ in results)} FAIL")
sys.exit(0 if all(r == "ok" for r, _ in results) else 1)
