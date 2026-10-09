"""Recover the v1 agent report from the v1 session's write tool call (not from prose)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SESS = ROOT / "evidence" / "session"
SRC = SESS / "agent-audit-run.agnes.json"
OUT = SESS / "trust_boundary_report_v1_agent.md"

events = []
for line in SRC.read_text(encoding="utf-8", errors="replace").splitlines():
    line = line.strip()
    if line:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass

found = None
for ev in events:
    blob = json.dumps(ev, ensure_ascii=False)
    if "trust_boundary_report.md" not in blob:
        continue
    # walk the whole event for a long string that looks like the report
    stack = [ev]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
        elif isinstance(node, str):
            if len(node) > 3000 and ("Trust Boundary Report" in node or "# " in node[:200]):
                if found is None or len(node) > len(found):
                    found = node

if found is None:
    print("could not find the report text in the v1 session")
    # last resort: is it in the HTML?
    html = (SESS / "agent-audit-run.html").read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"<script[\s\S]*?</script>", " ", html)
    text = re.sub(r"<[^>]+>", " ", text)
    print(f"  html visible text: {len(text)} chars; contains title: "
          f"{'Trust Boundary Report' in text}")
    raise SystemExit(1)

OUT.write_text(found, encoding="utf-8")
print(f"recovered {len(found)} chars -> {OUT}")
print("  first 3 lines:")
for line in found.splitlines()[:3]:
    print("   ", line)
print("  last 3 lines:")
for line in found.splitlines()[-3:]:
    print("   ", line)
