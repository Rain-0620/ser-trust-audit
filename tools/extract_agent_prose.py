"""Pull the agent's prose out of the session (it lives in assistant/message, not assistant/output)
and check whether the report quotes the confirmatory numbers."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SESSION = ROOT / "evidence" / "session" / "v2-agent-run.agnes.json"
SUMMARY = ROOT / "outputs" / "battery" / "summary_Session5_pc0_seed20261008.json"

events = []
for line in SESSION.read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if line:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass

prose = []
for ev in events:
    if ev.get("type") not in ("assistant/message", "assistant/output"):
        continue
    data = ev.get("data", {})

    def collect(node, acc):
        if isinstance(node, dict):
            if node.get("type") == "text" and isinstance(node.get("text"), str):
                acc.append(node["text"])
            for v in node.values():
                collect(v, acc)
        elif isinstance(node, list):
            for v in node:
                collect(v, acc)

    acc: list[str] = []
    collect(data, acc)
    joined = "\n".join(acc).strip()
    if joined:
        prose.append(joined)

print(f"assistant prose blocks: {len(prose)}")
if not prose:
    raise SystemExit("no prose found")

longest = max(prose, key=len)
print(f"longest: {len(longest)} chars")
print("\n" + "=" * 78)
print(longest[:7000])
print("=" * 78)

blob = "\n".join(prose)
print(f"\ntotal prose: {len(blob)} chars")

# the final short message (the summary the operator sees)
print("\n=== last 3 prose blocks (truncated) ===")
for p in prose[-3:]:
    print(f"  [{len(p)} chars] {p[:300].replace(chr(10), ' ')}")

if SUMMARY.exists():
    s = json.loads(SUMMARY.read_text(encoding="utf-8"))
    print("\n=== confirmatory numbers cited in the prose ===")
    cited = 0
    for r in sorted(s["results"], key=lambda r: (r["family"], -float(r["value"]))):
        for v in (f"{r['balanced_accuracy']:.3f}", f"{r['balanced_accuracy']:.4f}"):
            if v in blob:
                print(f"  {r['condition']:20s} {v}")
                cited += 1
                break
    print(f"  -> {cited}/{len(s['results'])} confirmatory values appear in the agent's prose")

    print("\n=== exploratory (small-sample) numbers leaking in? ===")
    for v in ("0.6979", "0.698", "0.729", "0.469", "n=96", "96 条", "±0.10"):
        c = blob.count(v)
        if c:
            print(f"  {v!r} appears {c}x")

print("\n=== integrity phrases ===")
for phrase in ("inference", "推断", "confirmatory", "确认阶段", "degenerate_probability",
               "P(deg)", "unmeasured", "valid: false", "Holm"):
    print(f"  {'YES' if phrase in blob else 'no ':4s} {blob.count(phrase):3d}x  {phrase!r}")

print("\n=== stray files the agent asked for ===")
for p in sorted(ROOT.glob("outputs/*.json")):
    print(f"  {p.relative_to(ROOT)}  {p.stat().st_size} B")
