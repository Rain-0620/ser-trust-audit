"""Extract the agent's own report from the v2 session and check which numbers it quotes."""
from __future__ import annotations

import json
import re
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

# user messages (to see whether the operator had to nudge it)
print("=== user messages ===")
for ev in events:
    if str(ev.get("kind")) == "user/message":
        blob = json.dumps(ev, ensure_ascii=False)
        m = re.search(r'"text"\s*:\s*"((?:[^"\\]|\\.){0,600})"', blob)
        if m:
            try:
                txt = json.loads('"' + m.group(1) + '"')
            except Exception:
                txt = m.group(1)
            print(f"  - {txt[:400]}")
print()

# the final assistant outputs
outputs = []
for ev in events:
    if str(ev.get("kind")) == "assistant/output":
        blob = json.dumps(ev, ensure_ascii=False)
        m = re.search(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"', blob)
        if m:
            try:
                outputs.append(json.loads('"' + m.group(1) + '"'))
            except Exception:
                outputs.append(m.group(1))
print(f"assistant/output events with text: {len(outputs)}")
if outputs:
    last = max(outputs, key=len)
    print(f"longest assistant output: {len(last)} chars")
    print("\n" + "=" * 78)
    print(last[:6000])
    print("=" * 78)

# does the report file exist?
print("\n=== report files written by the agent ===")
for pat in ("outputs/*report*", "outputs/*trust*", "*report*.md", "outputs/battery1.json"):
    for p in sorted(ROOT.glob(pat)):
        print(f"  {p.relative_to(ROOT)}  ({p.stat().st_size} B)")

# cross-check quoted numbers against the battery summary
if SUMMARY.exists():
    s = json.loads(SUMMARY.read_text(encoding="utf-8"))
    truth = {r["condition"]: r for r in s["results"]}
    blob = "\n".join(outputs)
    print("\n=== does the report quote the confirmatory values? ===")
    checks = ["0.7761", "0.7214", "0.2876", "0.4094", "0.5033", "0.2892", "0.5244"]
    for c in checks:
        print(f"  {c:10s} appears {blob.count(c)}x")
    print("\n=== does the report quote exploratory-only values? (n=96 numbers) ===")
    for c in ["0.6979", "0.729", "0.635", "0.552"]:
        print(f"  {c:10s} appears {blob.count(c)}x")
