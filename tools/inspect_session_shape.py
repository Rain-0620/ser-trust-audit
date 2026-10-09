"""Inspect the real structure of the exported AGH session events."""
import json
from pathlib import Path

F = Path(r"D:\ser-audit\evidence\session\v2-agent-run.agnes.json")
events = []
for line in F.read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if line:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass

print(f"parsed events: {len(events)}")
print(f"top-level keys of event 0: {sorted(events[0].keys())}")
print()

printed = set()
for ev in events:
    kind = str(ev.get("kind") or ev.get("event") or ev.get("type") or "?")
    if kind in printed:
        continue
    printed.add(kind)
    print(f"=== {kind} ===")
    print(json.dumps(ev, ensure_ascii=False)[:900])
    print()
    if len(printed) >= 12:
        break
