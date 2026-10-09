"""Peek at the exported session HTML to confirm it carries the real execution trace."""
import json
import re
from pathlib import Path

SESSION_DIR = Path(__file__).resolve().parent.parent / "evidence" / "session"
html = (SESSION_DIR / "agent-audit-run.html").read_text(encoding="utf-8", errors="replace")

text = re.sub(r"<script[\s\S]*?</script>", " ", html)
text = re.sub(r"<style[\s\S]*?</style>", " ", text)
text = re.sub(r"<[^>]+>", " ", text)
text = re.sub(r"&quot;", '"', text)
text = re.sub(r"&amp;", "&", text)
text = re.sub(r"&lt;", "<", text)
text = re.sub(r"&gt;", ">", text)
text = re.sub(r"&#x27;|&#39;", "'", text)
text = re.sub(r"\s+", " ", text).strip()
print(f"visible text length: {len(text)}")
print("\n--- first 1800 chars ---")
print(text[:1800])

print("\n--- every audit.py invocation found in the trace ---")
for m in re.finditer(r"audit\.py\s+([a-z]+[^\"\s]*(?:\s+--[^\"\s]+(?:[ =]\S+)?)*)", text):
    print("  ", m.group(0)[:150])

data = json.loads((SESSION_DIR / "agent-audit-run.agnes.json").read_text(encoding="utf-8", errors="replace"))
print(f"\n--- agnes json: type={type(data).__name__} ---")
if isinstance(data, dict):
    for k, v in data.items():
        print(f"   {k}: {type(v).__name__}" + (f" len={len(v)}" if hasattr(v, '__len__') else ""))
    msgs = data.get("messages") or data.get("conversation") or []
    print(f"   message count: {len(msgs)}")
    roles = {}
    for msg in msgs:
        if isinstance(msg, dict):
            roles[msg.get("role", "?")] = roles.get(msg.get("role", "?"), 0) + 1
    print(f"   roles: {roles}")
