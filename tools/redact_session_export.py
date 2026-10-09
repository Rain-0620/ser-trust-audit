"""Redact local identifiers from the AGH session exports before publishing them.

The session ledger records the operator of the session and the model route it ran on. Neither is
needed to follow the run, and both identify the machine / account rather than the work, so they
are replaced with neutral placeholders. Nothing else is touched: the tool calls, their arguments,
their output, the approval decisions and the model turns are left exactly as the harness wrote
them.

The patterns match by *shape* rather than by value, so this file does not itself contain the
identifiers it removes.

Running it again is a no-op: the rules map their output back to itself, and the script verifies
that a second pass changes nothing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = [
    ROOT / "evidence" / "session" / "agent-audit-run.agnes.json",
    ROOT / "evidence" / "session" / "v2-agent-run.agnes.json",
]

# The session ledger tags every event with an actor:
#     {"id":"<actor>","org":"local","role":...,"deptPath":[],"attrs":{...}}
# The harness runs under the ids "local" and "system"; the only other actor is the human
# operator. The rule is therefore "redact any actor that is not the harness", which is stated as a
# set of exclusions so that this file never contains the identifier it removes. "operator" is this
# script's own output, so excluding it too keeps a second run a genuine no-op.
OPERATOR = re.compile(r'"id":"(?!local"|system"|operator")[^"]{1,64}","org":"local"')
# Internal model-route / account identifier.
ACCOUNT = re.compile(r"account-acct-[0-9a-fA-F-]{36}")

RULES = [
    (OPERATOR, '"id":"operator","org":"local"'),
    (ACCOUNT, "account-redacted"),
]


def apply_rules(text: str) -> tuple[str, dict[str, int]]:
    hits: dict[str, int] = {}
    for pattern, new in RULES:
        text, n = pattern.subn(new, text)
        if n:
            hits[pattern.pattern] = n
    return text, hits


def main() -> int:
    total = 0
    for p in TARGETS:
        if not p.exists():
            print(f"  missing: {p.name}")
            continue
        text = p.read_text(encoding="utf-8")
        once, hits = apply_rules(text)
        twice, _ = apply_rules(once)
        if twice != once:
            print(f"  WARNING: {p.name} is not stable under a second pass — not writing")
            continue
        p.write_text(once, encoding="utf-8")
        n = sum(hits.values())
        total += n
        print(f"  {p.name}: {n} replacement(s)" + (f"  {hits}" if hits else "  (already clean)"))
    print(f"total replacements: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
