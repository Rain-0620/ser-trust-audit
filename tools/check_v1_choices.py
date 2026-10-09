"""Check what the v1 agent actually chose: sample size, and the shell timeout per tool call.

Both matter for whether a re-run can cover the full-scale evidence.
"""
import json
import re
from pathlib import Path

SESSION = Path(__file__).resolve().parent.parent / "evidence" / "session" / "agent-audit-run.agnes.json"

events = []
for line in SESSION.read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if line:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass

print(f"events: {len(events)}")

text = SESSION.read_text(encoding="utf-8", errors="replace")
timeouts = sorted(set(int(m) for m in re.findall(r'"timeoutMs"\s*:\s*(\d+)', text)))
print(f"\n--- per-tool-call timeouts the agent used ---")
for t in timeouts:
    print(f"  {t} ms = {t/60000:.1f} min   (appears {text.count(chr(34)+'timeoutMs'+chr(34)+': '+str(t))}x)")

print("\n--- per-class values that appear in the session ---")
pcs = sorted(set(int(m) for m in re.findall(r"--per-class[\\\" ]+(\d+)", text)))
print(f"  {pcs}")

print("\n--- sample sizes actually measured ---")
for m in sorted(set(re.findall(r'"n_utterances"\s*:\s*(\d+)', text))):
    print(f"  n = {m}")

print("\n--- did any command run the full session? ---")
print(f"  mentions of '--per-class 0': {text.count('--per-class 0')}")
print(f"  mentions of 'battery':       {text.count('battery')}")

print("\n--- tool call durations (effect/settled or tool/result timing if present) ---")
for ev in events:
    kind = str(ev.get("kind") or ev.get("event") or ev.get("type") or "")
    if kind in ("tool/call", "tool/result"):
        blob = json.dumps(ev, ensure_ascii=False)
        m = re.search(r'"timeoutMs"\s*:\s*(\d+)', blob)
        cmd = re.search(r"audit\.py\s+(catalog|probe|sweep|curve)[^\"\\]*", blob)
        if cmd:
            print(f"  {kind:12s} timeout={m.group(1) if m else '-':>8s} ms   {cmd.group(0)[:70]}")
