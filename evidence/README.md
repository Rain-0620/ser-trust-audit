# Run evidence

Everything here was written by the tool or by Agnes Harness. Nothing in this directory is
hand-authored, and no number in any report is transcribed from anything else.

## The two agent runs

| Run | Session id | What it is |
|---|---|---|
| **v1** | `3e13fa4b-0bae-4cfd-8855-3e6ad8c69ea9` | The first agent-driven audit: exploration only, 96 utterances per class-balanced subset. Its conclusions are **superseded** (see below). |
| **v2** | `973a1f0e-30d2-422b-907d-f3ad876e94ef` | The full run: exploration **plus** the full-scale confirmation battery, 53 conditions × 1241 utterances. **This is the run `trust_boundary_report.md` comes from.** |

For each run:

* `<name>.agnes.json` — the session ledger as JSON Lines, one event per line, exactly as AGH
  recorded it. This is the primary record: model turns, tool calls with their full arguments,
  tool output, approval requests and approval decisions.
* `<name>.html` — the same ledger rendered, for reading in a browser.

Plus:

* `trace_summary.md` — the v1 tool-call sequence, extracted from the ledger by
  `tools/extract_trace_summary.py`.
* `trust_boundary_report_v1_agent.md` — the v1 report, recovered from the ledger after the v2 run
  overwrote the working copy. The v1 report is kept verbatim because its handling of a broken
  measurement is itself part of the result.

## What the ledger shows

Read the v2 ledger and you can follow the whole loop without trusting any summary:

1. the prompt the agent was given;
2. `catalog` — it reads what the tool can do and what workflow the tool recommends;
3. `probe` — the clean baseline;
4. `sweep` — **it chooses** four mechanistically different perturbations (nothing in the prompt
   names them);
5. `curve` — it refines the families that looked anomalous, and re-runs one of them three times to
   narrow the threshold;
6. `battery` — **30 calls** to the full-scale confirmation, because a single shell call has a
   timeout and the full sweep does not fit in one; it lowers its own `--budget-seconds` from 480
   to 250 after the first call is killed;
7. the approval gate — every shell command is asked, and both the request and the decision are in
   the ledger;
8. the report being written, after two attempts were rejected by the approval gate.

## Redaction

The ledger records who operated the session and which model route it ran on. Those two
identifiers say something about the machine and the account, and nothing about the work, so they
were replaced with neutral placeholders:

| Before | After | Occurrences (v1 / v2) |
|---|---|---|
| the local operator id | `operator` | 150 / 1068 |
| the internal account route id | `account-redacted` | 19 / 70 |

Nothing else was modified — not the tool calls, not their arguments, not their output, not the
model turns, not the approval decisions. The substitution is reproducible:
`python tools/redact_session_export.py`.

## A note on v1's numbers

The v1 run measured 96 utterances on a class-balanced subset. Two of its conclusions did not
survive the full-scale measurement:

* it reported a collapse at `gaussian_snr:7.5` dB; at n=1241 that condition is **not** collapsed
  (P(degenerate) = 0.00), and it does not reproduce in any of 5 independent resamples;
* it reported `lowpass:1000` as a borderline collapse (P(degenerate) = 0.263); at n=1241 it is
  healthy (0.00).

This is why the protocol has a separate confirmation stage and why the report only cites the
confirmatory numbers. The disagreement is not hidden — the agent lists it itself in section 3.5 of
its own report.
