"""Two housekeeping jobs after the v2 dry run.

1. List the approvals, so we know how much operator interaction a recorded run costs.
2. Recover the v1 agent report text from the v1 session export — the v2 run overwrote
   trust_boundary_report.md on disk, and the v1 report is part of the record.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SESS_DIR = ROOT / "evidence" / "session"


def load(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


print("=== approvals in the v2 dry run ===")
v2 = load(SESS_DIR / "v2-agent-run.agnes.json")
for ev in v2:
    if str(ev.get("type", "")).startswith("approval/"):
        data = ev.get("data", {})
        blob = json.dumps(data, ensure_ascii=False)
        subject = ""
        m = re.search(r'"(?:command|path|subject|summary)"\s*:\s*"((?:[^"\\]|\\.){0,160})"', blob)
        if m:
            subject = m.group(1)
        decision = ""
        d = re.search(r'"(?:decision|outcome|result|verdict)"\s*:\s*"([a-z\-]+)"', blob)
        if d:
            decision = d.group(1)
        ts = str(ev.get("ts", ""))[11:19]
        print(f"  {ts}  {ev['type']:20s} {decision:16s} {subject[:80]}")

print("\n=== recovering the v1 report from the v1 session ===")
v1 = load(SESS_DIR / "agent-audit-run.agnes.json")
best = ""
for ev in v1:
    if ev.get("type") not in ("assistant/message", "assistant/output"):
        continue
    acc: list[str] = []

    def collect(node):
        if isinstance(node, dict):
            if node.get("type") == "text" and isinstance(node.get("text"), str):
                acc.append(node["text"])
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for v in node:
                collect(v)

    collect(ev.get("data", {}))
    joined = "\n".join(acc)
    if len(joined) > len(best):
        best = joined

print(f"  longest v1 prose: {len(best)} chars")
if best:
    start = best.find("# Trust Boundary Report")
    if start < 0:
        start = best.find("# ")
    end = best.find("## 8. Evidence files")
    end = best.find("\n---", end) if end > 0 else -1
    body = best[start:] if start >= 0 else best
    out = SESS_DIR / "trust_boundary_report_v1_agent.md"
    out.write_text(body, encoding="utf-8")
    print(f"  wrote {out}  ({len(body)} chars)")
    print("  first line:", body.splitlines()[0] if body else "(empty)")
