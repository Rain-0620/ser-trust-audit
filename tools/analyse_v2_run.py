"""Analyse the v2 dry-run session: what the agent actually did, in order.

Answers the three questions that decide whether this run is usable as the recorded evidence:
  1. did it discover and drive `battery` itself?
  2. did it report the confirmatory numbers, not the exploratory ones?
  3. does the AGH record contain the same numbers as outputs/battery/?
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SESSION = ROOT / "evidence" / "session" / "v2-agent-run.agnes.json"
BATTERY_SUMMARY = ROOT / "outputs" / "battery" / "summary_Session5_pc0_seed20261008.json"

events = []
for line in SESSION.read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if line:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass

print(f"events: {len(events)}")
kinds = Counter(str(e.get("kind") or e.get("event") or e.get("type") or "?") for e in events)
for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]):
    print(f"  {k:34s} {v}")

text = SESSION.read_text(encoding="utf-8", errors="replace")

print("\n=== every audit.py invocation, in order ===")
calls = []
for m in re.finditer(r"audit\.py\s+(catalog|probe|sweep|curve|battery)\b[^\"\\\n]*", text):
    cmd = m.group(0).strip().rstrip('",')
    cmd = re.sub(r"\s*,?\s*\"?timeoutMs=.*$", "", cmd).strip()
    calls.append(cmd)
seen = []
for c in calls:
    if not seen or seen[-1] != c:
        seen.append(c)
battery_calls = [c for c in calls if c.startswith("battery")]
print(f"  total invocations : {len(calls)}")
print(f"  battery calls     : {len(battery_calls)}")
by_kind = Counter(c.split()[1] if len(c.split()) > 1 else c for c in calls)
for k, v in by_kind.items():
    print(f"    {k:10s} {v}")

print("\n=== the sequence (consecutive duplicates collapsed) ===")
for i, c in enumerate(seen[:60], 1):
    print(f"  {i:3d}. {c[:110]}")
if len(seen) > 60:
    print(f"  ... and {len(seen) - 60} more distinct steps")

print("\n=== distinct battery argument forms ===")
for form, n in Counter(re.sub(r"battery", "battery", c) for c in battery_calls).most_common():
    print(f"  {n:3d}x  {form[:100]}")

print("\n=== did the agent read the battery summary? ===")
print(f"  mentions summary_Session5      : {text.count('summary_Session5')}")
print(f"  mentions report_Session5       : {text.count('report_Session5')}")
print(f"  mentions 'status' + 'complete' : {text.count('\"status\": \"complete\"')}")
print(f"  mentions outputs/battery       : {text.count('outputs')}")

if BATTERY_SUMMARY.exists():
    s = json.loads(BATTERY_SUMMARY.read_text(encoding="utf-8"))
    print("\n=== battery summary (ground truth) ===")
    print(f"  conditions {s['n_conditions']}  valid {s['n_valid']}  degenerate {s['n_degenerate']}")
    print(f"  clean balanced accuracy {s['clean_reference']['balanced_accuracy']} "
          f"CI {s['clean_reference']['balanced_accuracy_ci95']}")
    print(f"  thresholds located for: {list(s['thresholds'].keys())}")
    print("\n  every condition the agent could have quoted:")
    for r in sorted(s["results"], key=lambda r: (r["family"], -float(r["value"]))):
        mark = "DEG" if r.get("degenerate") else ("inv" if not r.get("valid") else "   ")
        print(f"    {mark} {r['condition']:20s} bacc={r['balanced_accuracy']:.4f} "
              f"maj={r['majority_share']:.2f} P(deg)={r['degenerate_probability']:.2f}")
