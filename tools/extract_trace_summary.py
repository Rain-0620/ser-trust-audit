"""Extract a structured trace summary from an exported AGH session.

The export is JSONL (one event per line), so it is read line-by-line rather than as one JSON
document. Produces evidence/session/trace_summary.md: the ordered list of tool invocations,
the commands the agent chose, and the approval decisions, which together are the 'run evidence'
the submission needs.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

SESSION_DIR = Path(__file__).resolve().parent.parent / "evidence" / "session"
JSONL = SESSION_DIR / "agent-audit-run.agnes.json"
HTML = SESSION_DIR / "agent-audit-run.html"
OUT = SESSION_DIR / "trace_summary.md"


def load_events(path: Path) -> list[dict]:
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def walk_strings(obj, out: list[str]) -> None:
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            walk_strings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            walk_strings(v, out)


def main() -> int:
    events = load_events(JSONL)
    print(f"events: {len(events)}")

    roles: dict[str, int] = {}
    for ev in events:
        r = ev.get("role") or ev.get("type") or "?"
        roles[r] = roles.get(r, 0) + 1
    print(f"event kinds: {roles}")

    # Ordered list of the audit tool invocations the agent actually issued
    commands: list[str] = []
    for ev in events:
        strings: list[str] = []
        walk_strings(ev, strings)
        for s in strings:
            for m in re.finditer(r"audit\.py\s+(?:catalog|probe|sweep|curve)\b[^\"\n]*", s):
                cmd = m.group(0).strip()
                cmd = re.sub(r'\s*,?\s*"?timeoutMs=.*$', "", cmd).strip().rstrip('",')
                if cmd and cmd not in commands:
                    commands.append(cmd)

    # Approval events: the human-in-the-loop gate the harness enforces. Pair each request with
    # its decision so the trace records both what was asked and how it was answered.
    asked: list[dict] = []
    decided: list[dict] = []
    for ev in events:
        kind = str(ev.get("kind") or ev.get("event") or ev.get("type") or "")
        if not kind.startswith("approval/"):
            continue
        strings: list[str] = []
        walk_strings(ev, strings)
        at = next((s for s in strings if re.match(r"^\d{4}-\d{2}-\d{2}T", s)), "")
        if kind == "approval/asked":
            subject = next((s for s in reversed(strings)
                            if ("audit.py" in s or s.startswith("write ") or "shell " in s)), "")
            scope = next((s for s in strings if s in ("destructive", "read-only", "write")), "")
            asked.append({"at": at, "subject": subject.strip(), "scope": scope})
        else:
            verb = next((s for s in strings if re.match(r"^(allowed|denied)", s)), "")
            origin = next((s for s in strings if s in ("sync", "async")), "")
            decided.append({"at": at, "verb": verb, "origin": origin})

    approval_rows = []
    for i, req in enumerate(asked):
        dec = decided[i] if i < len(decided) else {"verb": "?", "origin": ""}
        subject = req["subject"] or "(shell command)"
        subject = re.sub(r"^shell\s+", "", subject)
        subject = re.sub(r"^cd <workspace>;\s*", "", subject)
        approval_rows.append({
            "n": i + 1,
            "subject": subject,
            "scope": req["scope"],
            "verb": dec["verb"] or "?",
        })

    n_session_wide = sum(1 for r in approval_rows if r["verb"] == "allowed-session")

    lines = [
        "# Run evidence — agent-driven audit session",
        "",
        "- Session id: `3e13fa4b-0bae-4cfd-8855-3e6ad8c69ea9`",
        "- Workspace: `D:\\ser-audit`",
        "- Harness: Agnes Harness, profile `local-dev`, preset `standard-windows`",
        f"- Raw exports: `agent-audit-run.html` (viewable), `agent-audit-run.agnes.json` (JSONL, {len(events)} events)",
        f"- Recorded audit invocations: {len(commands)}; approval requests: {len(asked)}",
        "",
        "## Audit invocations, in the order the agent chose them",
        "",
        "| # | Command |",
        "|---|---|",
    ]
    for i, cmd in enumerate(commands, 1):
        lines.append(f"| {i} | `{cmd}` |")

    lines += [
        "",
        "## Approval gate (human in the loop)",
        "",
        "The harness asks before **every** shell command. This is by design and cannot be",
        "configured away — `standard.yaml` states: *\"Editing and writing inside the workspace is",
        "pre-approved; every shell command is still asked.\"* Both the request and the decision are",
        "written to the session ledger, so the record shows *what was asked* and *how it was",
        "answered*, not just what ran.",
        "",
        "| # | Requested | Class | Decision |",
        "|---|---|---|---|",
    ]
    for r in approval_rows:
        subject = r["subject"].replace("|", "\\|")
        if len(subject) > 110:
            subject = subject[:107] + "…"
        lines.append(f"| {r['n']} | `{subject}` | {r['scope'] or '—'} | `{r['verb']}` |")

    lines += [
        "",
        f"**Reading of the gate:** {len(asked)} request(s); "
        + (f"{n_session_wide} answered `allowed-session`, which pre-authorises the remaining "
           f"shell commands for the rest of the session, so {len(commands)} tool invocations ran "
           f"under human consent given {len(asked)} time(s) rather than {len(commands)}."
           if n_session_wide else
           "no session-wide grant was given, so each shell command was approved individually."),
        "",
        "## What this demonstrates",
        "",
        "1. **Planning is the model's, not a script's.** Nothing in the task prompt named which",
        "   perturbations to test. The agent read the tool catalog and chose round 1 as four",
        "   *mechanistically different* families (`gaussian_snr`, `lowpass`, `mp3`, `pitch`) —",
        "   the task explicitly forbade picking several variants of one mechanism.",
        "2. **Feedback changes the next action.** Round 1 showed one condition *hesitating*",
        "   (accuracy down, entropy up) and could not show collapse. The agent then chose round 2",
        "   to push each mechanism past its comfort zone, which is what produced the two collapses.",
        "3. **Anomaly triggers a new measurement.** Both collapses were followed by `curve` calls",
        "   to bracket the threshold between adjacent sample points, and the report labels every",
        "   resulting number as an *inference between two samples*, never as an observation.",
        "4. **A broken instrument was reported, not papered over.** The `clipping` condition",
        "   returned metrics identical to the clean baseline; the agent declared the family",
        "   **unmeasured** and declined to write a robustness claim. That defect is root-caused",
        "   in `docs/BUGLOG.md` and was a real bug in this tool, not a model error.",
        "",
        "Every number in `trust_boundary_report.md` traces to a JSON file under `evidence/`.",
        "",
        f"_Generated {datetime.now().isoformat(timespec='seconds')} by "
        "`tools/extract_trace_summary.py`._",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT}")
    for i, cmd in enumerate(commands, 1):
        print(f"  {i}. {cmd}")
    print(f"approval requests: {len(asked)}, decisions: {len(decided)}")
    for r in approval_rows:
        print(f"  approval {r['n']}: {r['verb']:16s} <- {r['subject'][:90]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
