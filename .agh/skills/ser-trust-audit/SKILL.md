---
name: ser-trust-audit
description: Audit a pretrained speech emotion recognition (SER) model and determine the conditions under which it can still be trusted. Plans perturbation experiments, detects when the model degenerates into a constant predictor, quantifies every claim with confidence intervals and paired significance tests, refines the measurement around any anomaly found, and reports an evidence-backed trust boundary. Use when asked to audit, stress-test, or verify an emotion recognition model.
---

# SER trustworthiness audit

You are auditing a pretrained speech emotion recognition model.

Your job is **not** to measure accuracy. A fixed grid of perturbations can do that, and it
already exists. Your job is to find the conditions where the model stops being trustworthy,
to prove it rather than assert it, and to be suspicious of your own measurements.

## Tool

Everything runs through `audit.py` from the repository root, using the project virtualenv:

```
.venv\Scripts\python.exe audit.py <command> [options]
```

Every subcommand prints **exactly one JSON object on stdout** (progress goes to stderr).
`--out <path>` also writes that JSON to a file so the run leaves evidence behind.

| Command | Purpose |
| --- | --- |
| `catalog` | families, units, parameter types, the canonical battery, and the recommended workflow |
| `probe` | clean baseline, label space, model fingerprint, throughput |
| `sweep --conditions family:value,...` | run a chosen set of conditions (exploration) |
| `curve --family F --from A --to B --points N` | sample one family across its range (locating) |
| `battery` | confirm across many conditions at full scale (confirmation) |

Useful options: `--per-class N` sets how many utterances per class are sampled
(`--per-class 0` uses **every** 4-class utterance in the session — the default for `battery`,
and what "full scale" means); `--bootstrap N` sets the number of bootstrap resamples behind the
confidence intervals (default 2000).

### The battery, and why it is called more than once

A full-scale confirmation is roughly 53 conditions × 1241 utterances ≈ 85 minutes of GPU work.
A harness shell call is capped well below that (600 s was observed on AGH), so one call cannot
finish it. `battery` therefore keeps its own state under `outputs/battery/` and measures as much
as `--budget-seconds` allows, then exits:

```json
{ "status": "in_progress", "completed": 12, "total": 53, "remaining": ["..."] }
```

**Call it again until `status` is `"complete"`** — it resumes from the state file and reuses the
cached clean arm. `battery --status` reports progress without measuring anything; `battery --reset`
starts over; `--plan <file.json>` overrides which values are measured at full scale (`catalog`
publishes the canonical list under `canonical_battery`).

Chunking cannot change the numbers: every statistic derives from a fixed seed and pinned audio,
so a condition measured in call 9 is identical to the same condition measured in call 1.

## Reading the output

Every condition returns a bundle, not a number. The fields that matter:

**Accuracy and its uncertainty**
- `balanced_accuracy` — **your primary metric** (macro-average recall). Prefer it over
  `accuracy`: the full session has an uneven class distribution, and raw accuracy rewards
  simply predicting the common class.
- `accuracy`, `macro_f1`, `chance_level`, `per_class_recall` — supporting detail.
- `balanced_accuracy_ci95`, `accuracy_ci95` — **95% bootstrap confidence intervals.** Any
  difference smaller than the width of these intervals is not a finding.

**Is the model still answering the question?**
- `mean_normalised_entropy` — how spread the probabilities still are.
- `majority_share`, `majority_class` — how much one class dominates the output.
- `degenerate` — the tool's verdict, using a convention (`majority_share >= 0.75` **or**
  `mean_normalised_entropy <= 0.30`). Treat this as a labelled convention, not ground truth.
- `degenerate_probability` — **the fraction of bootstrap resamples that triggered that
  convention.** This is how much the verdict is actually supported by the data. Report it
  alongside the verdict; `degenerate: true` with `degenerate_probability: 0.51` is a
  coin-flip, not a collapse.
- `majority_share_ci95`, `entropy_ci95` — intervals on the two quantities the rule thresholds.

**Was the condition even measurable?**
- `valid` — `false` means **the transform did not apply** to the audio. The row is NOT a
  measurement of that condition. Report it as unmeasured; never as "no harm".
- `transform_failures`, `transform_failure_types`, `invalid_reason` — why it failed.
- `clips_actually_modified` — how many clips the transform actually changed. A valid
  condition with this at 0 is a silent no-op.

**Did this condition change behaviour, or is it noise?**
- `delta_balanced_accuracy`, `delta_balanced_accuracy_ci95` — difference from the clean
  reference, paired on the same utterances. If the interval contains 0, you have not shown
  a difference.
- `mcnemar_exact_p` — exact paired test on the utterances where clean and perturbed disagree.
  Sensitivity to change, not the size of it.
- `cohens_h_vs_clean` — effect size; `|h| < 0.2` is small, `> 0.8` is large.
- `multiple_comparison` — Holm-Bonferroni adjusted p-values across the conditions of that
  sweep, plus `significant_after_correction`. **Use this list, not the raw p-values**, when
  you claim many findings: testing 20 conditions and quoting the smallest p-value is the
  classic multiple-comparison error.

**Reference and thresholds**
- `clean_reference` — the clean arm measured on the same utterances in the same run. Compare
  against this, not against a number from an earlier run.
- `curve` output also carries `threshold` with `first_degenerate`, `last_healthy`,
  `bracketing_interval` and `interval_width` — the tool's own bracketing of the crossing point.

## Protocol

**1. Probe before you perturb.**
Run `probe` first. You need the clean baseline, the chance level, the label space, and the
model fingerprint (so the audit is tied to one exact artifact). Do not skip this.

**2. Plan a first sweep that separates failure mechanisms.**
Pick a small set of conditions that probe *different* things — additive noise, bandwidth
loss, codec artefacts, prosody change. Several variants of the same mechanism teach you
nothing new. Breadth first; you will go deep only where the data tells you to.

**3. Read the whole bundle, not the headline.**
Four distinct outcomes, and they are different findings:

| What you see | What it means |
| --- | --- |
| accuracy down, entropy **up** | the model is **unsure** — degraded, still answering |
| high `majority_share`, low entropy, high `degenerate_probability` | the model has **stopped answering** and is emitting one class |
| `delta` CI contains 0 | **no measured effect** — do not call it robust, call it not detected |
| `valid: false` | **unmeasured** — the transform never applied; say so |

Say which one you observed. A model that is "merely degraded" and a model that has collapsed
have completely different implications for anyone relying on it.

**4. Never report an anomaly without locating it.**
If a condition is degenerate, or the drop between two sampled points is discontinuous, that
is the most interesting thing in the run — do not just report the number. Run `curve` across
that family to bracket the transition, then state the threshold in the family's own unit and
quote the `bracketing_interval`. "Accuracy falls gradually with noise" and "the model holds
until about X dB and then collapses" are different claims; only the second is worth reporting.

**5. Confirm at full scale before you conclude.**
Exploration is done on a small sample on purpose: it is fast and it tells you where to look. It
is **not** evidence you can report. A small balanced sample has a wide confidence interval and a
noisy collapse statistic, so a verdict reached there can flip when the same condition is measured
on the whole session.

So after you have explored and located the interesting region, run the confirmatory battery:

```
.venv\Scripts\python.exe audit.py battery --budget-seconds 480
```

and **call it again until `status` is `"complete"`** (see the Tool section — one call cannot
finish it). Then read the aggregate it writes: `outputs/battery/summary_*.json` and
`report_*.md`. Pass `--plan` if your exploration suggests conditions the canonical list does not
cover; run `battery --status` to see where it is without measuring.

**Report the confirmatory numbers, not the exploratory ones.** The exploratory run is how you
decided where to look; the confirmatory run is what you claim. If the two disagree, the
confirmatory run wins, and the disagreement itself is worth one sentence in the report — it means
the small-sample verdict was noise.

**6. Check whether your measurement itself is valid.**
If a perturbation leaves the result bit-identical to clean, suspect the transform silently did
nothing rather than concluding the model is robust — check `clips_actually_modified`, and if a
condition is `valid: false`, report it as unmeasured. An audit that hides its own failures is
worthless. If you believe the tool itself is broken, report the defect; do not patch the
instrument mid-audit and carry on, because the tool is the instrument of record.

**7. Separate what you measured from what you inferred.**
Reported numbers must come from tool output. A threshold you located between two sampled
points is an inference — label it as such and state your sampling step.

**8. Check that your threshold is not an artefact of your evaluation set.**
Even after the battery confirms a threshold on the full session, ask whether it is a property of
the *model* or of the *evaluation set*. Two cheap checks, both worth doing when you have budget:

- Re-measure the same conditions on a balanced subset of the same session (`--per-class 48`) and
  compare the verdicts. A verdict that flips between the full session and the subset sits on a
  boundary — say so, and do not report a single number for it.
- Re-measure on a different session entirely (`--session Session1` … `Session5`) with `sweep`. A
  condition that collapses on every session is a finding; one that collapses on two of five is a
  boundary region. Report the split, not one verdict.

## Required output

Produce a short report with these sections, and keep every number traceable to a tool call:

1. **Scope** — model fingerprint, dataset split, sample size and class distribution, seed,
   device, and **which numbers are confirmatory (battery) versus exploratory**.
2. **Baseline** — clean balanced accuracy with its 95% CI, against chance level, plus
   throughput.
3. **Findings** — per condition: balanced accuracy with CI, delta with CI, McNemar p (and its
   Holm-adjusted value), majority share, degenerate verdict **with `degenerate_probability`**.
   Call out:
   - which perturbations the model tolerates (delta CI overlapping 0),
   - which make it *unsure*,
   - which make it *collapse*, and
   - for any collapse, the located threshold, the bracketing interval, and how you located it.
   - any condition that was **unmeasured**, and why.
   - anything that looked like a difference but did not survive correction — report it as
     not established rather than dropping it silently.
   - any case where the confirmatory result contradicted the exploratory one, and what that
     implies about the exploratory sample.
4. **Trust boundary** — the operating conditions under which this model's output should not
   be relied on, stated in measurable units with the evidence for each.
5. **Limitations** — sample size, which sessions were covered, unmeasured perturbations,
   thresholds that are inferences rather than observations, and any result that depended on
   the choice of evaluation set.

## Rules

- Do not modify `audit.py` or the model to make a result look better.
- Do not report a number you did not obtain from the tool.
- Do not report a point estimate without its interval, or a difference without its test.
- **Do not present an exploratory (small-sample) number as a result.** Either confirm it with
  `battery`, or label it explicitly as exploratory and say what its sample size was.
- If a run fails, report the failure. A failed measurement is a finding.
- Keep the JSON outputs; they are the run evidence.
