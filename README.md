# SER Trust-Boundary Audit

An **agent that audits a speech-emotion-recognition model** — it plans its own perturbation
experiments, reads the multi-metric output, notices when a measurement is broken, and writes a
report saying **under which measurable conditions the model's output should not be trusted**.

The agent runs on **Agnes Harness (AGH)**, the execution substrate required by the competition,
driven by the **Agnes** model. What this repository contains is the part we built: a deterministic
measurement tool, an agent behaviour protocol, and the evidence the runs produced.

```
        Agnes (the model that plans and judges)
                    │
        SKILL.md    │  agent behaviour protocol — what counts as a finding,
        (ours)      │  what must not be claimed, how to tell "unsure" from "collapsed"
                    ▼
        audit.py    │  deterministic measurement tool: 9 perturbation families,
        (ours)      │  11 metrics per condition, bootstrap CIs, paired tests,
                    │  Holm correction, resumable full-scale confirmation
                    ▼
        AGH         │  session ledger, command-approval gate, skill loading
        (provided)  │  → this is where the run evidence comes from
```

**Audit target** (not our model, and not used by our agent): `superb/wav2vec2-base-superb-er`,
evaluated on IEMOCAP Session 5.

---

## Headline result

Full-scale confirmation: **53 conditions × 1241 utterances**, clean balanced accuracy
**0.776** (95% CI [0.752, 0.802]) against a chance level of 0.25.

**10 conditions tolerated · 33 degraded · 10 collapsed.**

The model has **two mechanically different failure modes**, and they land in two different
constant classes:

| Signature | Triggered by | Model degenerates to | Firing rule |
|---|---|---|---|
| **A** — additive noise | `gaussian_snr ≤ 2 dB`, `white_noise ≥ 0.02` | **happy** | one class takes ≥ 80% of outputs |
| **B** — bandwidth / codec / time | `lowpass ≤ 850 Hz`, `mp3 ≤ 8 kbps`, `timestretch ≥ 1.5×` | **neutral** | **entropy ≤ 0.30** |

Signature B is the interesting one: its accuracy is still 0.44–0.50, roughly double chance, so it
looks like "somewhat degraded" — but the model has stopped discriminating. **A monitor that only
tracks accuracy cannot see it.**

### Trust boundary (thresholds are inferences between adjacent sampled points)

| Condition | Threshold | Collapses to |
|---|---|---|
| SNR below ~3.5 dB | bracketed `[5.0, 2.0]` dB | happy |
| Low-pass cutoff below ~875 Hz | bracketed `[900, 850]` Hz | neutral |
| MP3 bitrate below ~12 kbps | bracketed `[16, 8]` kbps | neutral |
| White-noise amplitude above ~0.01 | bracketed `[0.005, 0.02]` | happy |
| Time-stretch above ~1.4× | bracketed `[1.3, 1.5]` | neutral |

Tolerated within the tested range: high-pass up to 800 Hz, clipping up to 30%, MP3 ≥ 32 kbps,
pitch shift ±2 semitones.

### The threshold is not a property of the model — it depends on the evaluation set

`lowpass:900 Hz` reads as **healthy** on the full session (n=1241, P(degenerate)=0.01) and as
**collapsed** on a balanced subset of the same session (n=192, P(degenerate)=0.58 — itself a coin
flip). Re-measured across 5 sessions and 5 independent sampling seeds it collapses in only **2 of
5** draws. By contrast `lowpass:600 Hz` collapses **5 of 5** every time.

That contrast is the point: it separates *a real finding* from *a threshold artefact*.

---

## Repository layout

```
audit.py                        the measurement tool (single file, agent-driven CLI)
audit-task-prompt.txt           the prompt handed to the agent
download_model.py               fetches the audit target from Hugging Face
feasibility_check.py            environment / throughput check
probe_*.py                      early environment probes (network, mirrors, HF access)

.agh/skills/ser-trust-audit/
  SKILL.md                      the agent behaviour protocol (loaded by AGH as a skill)

tools/                          analysis, verification and reporting scripts
  make_report.py                generates the v2 report from result JSON (not hand-written)
  report_render.py              renders a Markdown report to a tall image (video use)
  build_demo_video.py           builds the demo video from the screen recordings
  verify_determinism.py         proves two independent processes produce identical numbers
  verify_battery_identity.py    cross-checks the tool against earlier results
  replicate_seed.py             5 independent sampling seeds
  run_full_experiment.py        the first script-driven full run (superseded, see BUGLOG)
  test_cases.py                 16 normal / boundary / failure test cases
  ...                           (session-export parsing, trace extraction, checklists)

docs/
  TEST_CASES.md                 the 16 test cases with expected vs actual behaviour
  BUGLOG.md                     four defects found in our own tool, with root cause + fix
  COMPLIANCE.md                 rule-by-rule conformance check for the submission
  DEMO-RUNBOOK.md               how to run the live demo and record it
  public-article-agent-audits-ser.md   the public write-up of this work

trust_boundary_report.md        ← the agent's final report (authoritative result)
trust_boundary_report_v2.md     earlier script-generated report (superseded, see BUGLOG)

evidence/
  README.md                     what each run is, and what was redacted before publishing
  session/                      AGH session exports for both agent runs (HTML + JSONL)
  probe.json sweep*.json curve_*.json    per-call tool output from the exploration phase

outputs/
  battery/                      ← the full-scale confirmation run (authoritative data)
  auxiliary/                    cross-session and cross-seed replication
  full/                         the first full run, before BUG-3/BUG-4 were fixed (superseded)
  approval-log.jsonl            the human-in-the-loop approval ledger
  *.json                        exploration-phase tool output
```

### Which numbers are authoritative

`trust_boundary_report.md` and `outputs/battery/` are the authoritative result — they come from the
full-scale confirmation run executed by the agent through AGH, with the tool at its current
version.

`trust_boundary_report_v2.md` and `outputs/full/` are **kept only for the record**. They were
produced by the earlier script-driven run, and are superseded because that run predates two
defects in our own tool (BUG-3 and BUG-4 in `docs/BUGLOG.md`). The report was generated from
those files, so they are retained rather than deleted — but do not read their `gaussian_snr`,
`lowpass`, `highpass` or `white_noise` numbers as results.

---

## Reproduce

### 1. Environment

Python 3.13 with CUDA-capable PyTorch. Verified with:

```
python            3.13.14
torch             2.6.0+cu124
transformers      5.19.0
audiomentations   0.43.1
soundfile         0.14.0
numpy             2.5.3
scipy             1.18.1
librosa           0.11.0
huggingface-hub   1.33.0
```

```bash
python -m venv .venv
.venv/Scripts/pip install torch transformers audiomentations soundfile numpy scipy librosa
```

### 2. Audit target and data

Neither is redistributed here.

* **Model** — `superb/wav2vec2-base-superb-er` (Apache-2.0). `python download_model.py` fetches it
  into `models/superb-er/`. `audit.py --model <dir>` points at it.
* **Dataset** — IEMOCAP (requires signing the USC/SAIL license; not redistributable). Place the
  released WAVs so that `data/IEMOCAP/Session<N>/` contains the utterances used by
  `tools/extract_iemocap.py`. The tool expects **16 kHz mono** audio and falls back cleanly with a
  readable error if a file is not.

### 3. Run the tool on its own

```bash
.venv/Scripts/python.exe audit.py catalog
.venv/Scripts/python.exe audit.py probe --session Session5 --per-class 24
.venv/Scripts/python.exe audit.py sweep --conditions gaussian_snr:10,lowpass:2000,pitch:-4
.venv/Scripts/python.exe audit.py curve --family gaussian_snr --from 20 --to -5 --points 6

# full-scale confirmation, resumable: repeat until status == "complete"
.venv/Scripts/python.exe audit.py battery --budget-seconds 480
.venv/Scripts/python.exe audit.py battery --status
```

Every subcommand prints one JSON object on stdout (for the agent to parse) and progress text on
stderr (for the human). Exit codes are typed: `0` ok, `2` bad input, `3` model unavailable,
`4` dataset unavailable, `5` defect in the tool itself.

### 4. Run the tests

```bash
.venv/Scripts/python.exe tools/test_cases.py
```

16 cases — normal, boundary and failure — in `docs/TEST_CASES.md`.

### 5. Check reproducibility

```bash
.venv/Scripts/python.exe tools/verify_determinism.py    # two processes must agree bit-for-bit
```

---

## Why some of this is in the repository at all

`docs/BUGLOG.md` documents four defects found in our own instrument, two of them found by the
agent during a live run:

1. a perturbation family that never applied (a float passed where an `int` was required) and
   **failed silently by falling back to the clean audio** — so "measured nothing" was presented as
   "robust";
2. the tool was **not reproducible for four families** because several transforms draw their
   randomness from the global RNGs, which were never seeded;
3. the low-pass / high-pass filters randomised their **filter order per clip**, so
   "`lowpass:900`" measured a mixture of three filters rather than one;
4. two families had their clean/harmful direction labelled backwards in the catalogue.

They are in the submission because the honest handling of a broken instrument **is** the result.
The agent's response to defect 1 was to declare the family *unmeasured* and refuse to write a
robustness claim, rather than report the flattering number it was handed.

---

## Third-party components

See `THIRD-PARTY-NOTICES.md`. In short: AGH (Apache-2.0, provided by the organisers, used
unmodified), `audiomentations` (MIT), `superb/wav2vec2-base-superb-er` (Apache-2.0), IEMOCAP
(licensed, not redistributed). This repository contains no third-party model weights or audio data.

## Licence

MIT — see `LICENSE`.
