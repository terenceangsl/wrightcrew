"""Summarise a lane log written in JSONL (`pi --mode json`) without reading it whole.

  python tools/lane_summary.py <lane.log> [--tail 600]

Prints: event counts, whether the run settled (`agent_settled`), the last stopReason, tool calls by name, the last
errors, and the tail of the final assistant text. Lines that are not JSON (runner banners) are counted, not parsed.
A log of 40k events is never worth reading into a model's context (L-40). Exit code: 0 settled, 2 not settled,
1 unreadable file.
"""
import argparse, collections, json, sys


def summarise(path, tail=600):
    counts, tools, errors = collections.Counter(), collections.Counter(), []
    last_stop, last_text, settled, nonjson = None, "", False, 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("{"):
                nonjson += 1
                continue
            try:
                e = json.loads(line)
            except ValueError:
                nonjson += 1
                continue
            if not isinstance(e, dict):
                nonjson += 1
                continue
            t = e.get("type")
            counts[t] += 1
            if t == "agent_settled":
                settled = True
            if t == "message_end":
                m = e.get("message") or {}
                if m.get("role") == "assistant":
                    last_stop = m.get("stopReason")
                    for part in m.get("content") or []:
                        if part.get("type") == "text":
                            last_text = part.get("text", "")
                        if part.get("type") in ("toolCall", "tool_use"):
                            tools[part.get("name", "?")] += 1
                    if m.get("errorMessage"):
                        errors.append(str(m["errorMessage"])[:200])
    return {"events": dict(counts), "non_json_lines": nonjson, "settled": settled, "last_stop_reason": last_stop,
            "tool_calls": dict(tools), "errors": errors[-3:], "final_text_tail": last_text[-tail:]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("log")
    ap.add_argument("--tail", type=int, default=600, help="characters of the final text to show")
    a = ap.parse_args(argv)
    try:
        r = summarise(a.log, a.tail)
    except OSError as ex:
        print("cannot read log:", ex)
        return 1
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("events:", r["events"])
    print("non-json lines:", r["non_json_lines"], "| settled:", r["settled"], "| last stopReason:", r["last_stop_reason"])
    print("tool calls:", r["tool_calls"])
    print("errors:", r["errors"])
    print(f"final text (tail {a.tail} chars):", r["final_text_tail"])
    return 0 if r["settled"] else 2


if __name__ == "__main__":
    sys.exit(main())
