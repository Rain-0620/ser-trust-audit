"""Did the agent actually receive the v2 skill protocol, and what did it finally write?

Three checks:
  1. is the SKILL.md body present in the session context, or only its metadata?
  2. the ordered list of tool calls, with the shell command each one ran
  3. the agent's final report text, and which numbers it quotes
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SESSION = ROOT / "evidence" / "session" / "v2-agent-run.agnes.json"
SUMMARY = ROOT / "outputs" / "battery" / "summary_Session5_pc0_seed20261008.json"
V1_REPORT_IN_SESSION = "trust_boundary_report.md"

events = []
for line in SESSION.read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if line:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass

raw = SESSION.read_text(encoding="utf-8", errors="replace")


def texts(obj, out):
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            texts(v, out)
    elif isinstance(obj, list):
        for v in obj:
            texts(v, out)


# ---- 1. was the skill body delivered? ----
MARKERS = [
    "Confirm at full scale before you conclude",
    "your primary metric",
    "degenerate_probability",
    "The battery, and why it is called more than once",
    "Report the confirmatory numbers",
    "canonical_battery",
    "recommended_workflow",
]
print("=== is the v2 skill protocol present in the session? ===")
for m in MARKERS:
    print(f"  {'YES' if m in raw else 'no ':4s} {raw.count(m):3d}x  '{m}'")

# the context-breakdown entries report the skills section size
print("\n=== skills section token counts reported by the harness ===")
for ev in events:
    if ev.get("type") == "x/core/context-breakdown":
        for sec in ev.get("data", {}).get("sections", []):
            if "skill" in str(sec.get("id", "")) or "skill" in str(sec.get("source", "")):
                print(f"  {sec}")

# ---- 2. ordered tool calls ----
print("\n=== ordered tool calls (command each one ran) ===")
n = 0
for ev in events:
    if ev.get("type") != "tool/call":
        continue
    n += 1
    blob = json.dumps(ev.get("data", {}), ensure_ascii=False)
    cmd = re.search(r"audit\.py\s+(catalog|probe|sweep|curve|battery)\b[^\"\\]*", blob)
    kind = ev.get("data", {}).get("name") or ev.get("data", {}).get("tool") or "?"
    label = cmd.group(0)[:96] if cmd else blob[:96]
    print(f"  {n:3d}. [{kind}] {label}")
print(f"  -> {n} tool calls")

# ---- 3. the final report ----
out_texts = []
for ev in events:
    if ev.get("type") == "assistant/output":
        t = []
        texts(ev.get("data", {}), t)
        joined = "\n".join(x for x in t if len(x) > 40)
        if joined:
            out_texts.append(joined)

print(f"\n=== assistant outputs with prose: {len(out_texts)} ===")
if out_texts:
    longest = max(out_texts, key=len)
    print(f"longest: {len(longest)} chars")
    print("\n" + "-" * 78)
    print(longest[:5000])
    print("-" * 78)

    # does it cite confirmatory numbers?
    if SUMMARY.exists():
        s = json.loads(SUMMARY.read_text(encoding="utf-8"))
        truth = {r["condition"]: r for r in s["results"]}
        blob = "\n".join(out_texts)
        print("\n=== numbers cited by the agent vs the battery summary ===")
        for cond, r in sorted(truth.items()):
            v = f"{r['balanced_accuracy']:.3f}"
            if v in blob:
                print(f"  cited     {cond:20s} {v}")
        print("\n=== exploratory (n=96) numbers leaking into the report? ===")
        for v in ("0.6979", "0.729", "0.698", "0.469"):
            c = blob.count(v)
            if c:
                print(f"  {v} appears {c}x")

# ---- 4. did it overwrite the v1 report? ----
print("\n=== report files on disk ===")
for p in sorted(ROOT.glob("*.md")):
    print(f"  {p.name}  {p.stat().st_size} B  (modified {p.stat().st_mtime:.0f})")
