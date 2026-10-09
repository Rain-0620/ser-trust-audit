# Run evidence — agent-driven audit session

- Session id: `3e13fa4b-0bae-4cfd-8855-3e6ad8c69ea9`
- Workspace: `D:\ser-audit`
- Harness: Agnes Harness, profile `local-dev`, preset `standard-windows`
- Raw exports: `agent-audit-run.html` (viewable), `agent-audit-run.agnes.json` (JSONL, 155 events)
- Recorded audit invocations: 6; approval requests: 2

## Audit invocations, in the order the agent chose them

| # | Command |
|---|---|
| 1 | `audit.py catalog` |
| 2 | `audit.py probe --session Session5 --per-class 24 --out evidence\probe.json` |
| 3 | `audit.py sweep --conditions gaussian_snr:10,lowpass:1000,mp3:32,pitch:4 --out evidence\sweep1.json` |
| 4 | `audit.py sweep --conditions gaussian_snr:0,lowpass:500,pitch:-4,mp3:16,clipping:20,timestretch:1.3,gain:-20 --out evidence\sweep2.json` |
| 5 | `audit.py curve --family gaussian_snr --from 10 --to 0 --points 9 --out evidence\curve_snr.json` |
| 6 | `audit.py curve --family lowpass --from 1000 --to 500 --points 9 --out evidence\curve_lowpass.json` |

## Approval gate (human in the loop)

The harness asks before **every** shell command. This is by design and cannot be
configured away — `standard.yaml` states: *"Editing and writing inside the workspace is
pre-approved; every shell command is still asked."* Both the request and the decision are
written to the session ledger, so the record shows *what was asked* and *how it was
answered*, not just what ran.

| # | Requested | Class | Decision |
|---|---|---|---|
| 1 | `.venv\Scripts\python.exe audit.py catalog timeoutMs=120000` | destructive | `allowed-session` |
| 2 | `write trust_boundary_report.md (11858 chars)` | destructive | `allowed-once` |

**Reading of the gate:** 2 request(s); 1 answered `allowed-session`, which pre-authorises the remaining shell commands for the rest of the session, so 6 tool invocations ran under human consent given 2 time(s) rather than 6.

## What this demonstrates

1. **Planning is the model's, not a script's.** Nothing in the task prompt named which
   perturbations to test. The agent read the tool catalog and chose round 1 as four
   *mechanistically different* families (`gaussian_snr`, `lowpass`, `mp3`, `pitch`) —
   the task explicitly forbade picking several variants of one mechanism.
2. **Feedback changes the next action.** Round 1 showed one condition *hesitating*
   (accuracy down, entropy up) and could not show collapse. The agent then chose round 2
   to push each mechanism past its comfort zone, which is what produced the two collapses.
3. **Anomaly triggers a new measurement.** Both collapses were followed by `curve` calls
   to bracket the threshold between adjacent sample points, and the report labels every
   resulting number as an *inference between two samples*, never as an observation.
4. **A broken instrument was reported, not papered over.** The `clipping` condition
   returned metrics identical to the clean baseline; the agent declared the family
   **unmeasured** and declined to write a robustness claim. That defect is root-caused
   in `docs/BUGLOG.md` and was a real bug in this tool, not a model error.

Every number in `trust_boundary_report.md` traces to a JSON file under `evidence/`.

_Generated 2026-10-08T21:55:34 by `tools/extract_trace_summary.py`._