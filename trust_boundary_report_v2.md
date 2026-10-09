# Trust boundary report (v2) — speech emotion recognition model `superb-er`

_Generated 2026-10-09T11:35:12 by `tools/make_report.py` from the JSON in `outputs/full/`. Every number below is computed, not transcribed._

This supersedes `trust_boundary_report.md` (v1), which was produced by the agent during the exploratory run described in `evidence/session/`. v1 is kept unchanged as the record of that run; the differences between the two are themselves findings (§7).

## 1. Scope

| | |
|---|---|
| Model | `superb/wav2vec2-base-superb-er` (fine-tuned wav2vec2-base) |
| Model fingerprint | `dac0f46128deec04` |
| Labels | 4 classes: angry / happy / sad / neutral |
| Dataset | IEMOCAP, 4-class subset (ang+exc→happy, sad, neu→neutral) |
| Evaluation set | Session5, **all 1241 4-class utterances** (natural class distribution) |
| Utterance distribution | angry 170 / happy 442 / sad 245 / neutral 384 |
| Cross-session arm | Sessions 1–5, balanced 48 per class = 192 each |
| Device | CUDA — NVIDIA GeForce GTX 1650 |
| Bootstrap resamples | 2000 per condition |
| Conditions measured | **53** across **9** perturbation families |
| Audit tool | `audit.py` v2 (`valid` / CI / paired-test fields) |

## 2. Method

**Primary metric.** `balanced_accuracy` (macro-average recall over the four classes). Raw accuracy is reported alongside it but is not the basis for any claim: the full session is unevenly distributed (happy is 35.6% of it), so raw accuracy rewards predicting the common class.

**Uncertainty.** Every metric carries a 95% percentile bootstrap CI over utterances (2000 resamples, fixed seed). A difference is only called real when it survives the paired test below; nothing here is reported as a bare point estimate.

**Paired comparison.** Each condition is compared against the clean arm measured on the *same utterances in the same run*, using McNemar's exact test on the utterances where the two disagree, plus a bootstrap CI on the balanced-accuracy difference and Cohen's *h* as an effect size.

**Multiple comparisons.** Holm-Bonferroni within each perturbation family (dose levels of one mechanism are not independent hypotheses). A global Holm pass across all 53 conditions is also recorded in the summary JSON and is far more conservative.

**Collapse convention.** A condition is flagged when `majority_share >= 0.75` **or** `mean_normalised_entropy <= 0.30`. This is a labelled convention, not ground truth, so the report always carries `P(degenerate)` — the fraction of bootstrap resamples that trigger it. A verdict with `P(degenerate)` near 0.5 is a coin flip and is reported as such.

**Instrument integrity.** A condition whose transform failed to apply is emitted as `valid: false` with the failure counts and never substituted with clean audio; `clips_actually_modified` records how many clips the transform really changed. See `docs/BUGLOG.md` for why this is stated explicitly.

## 3. Baseline

- Clean balanced accuracy on the full session: **0.7761** 95% CI [0.752, 0.801]
- Clean accuracy: 0.7736 95% CI [0.750, 0.797] (chance level 0.25)
- Majority share 0.3497 (happy), mean normalised entropy 0.3681
- Per-class recall: angry 0.747, happy 0.760, sad 0.837, neutral 0.760

The same clean arm was recomputed independently inside each of the nine family runs; all nine returned balanced accuracy 0.7761 with identical CIs, which is a determinism check on the whole pipeline (fixed seed, audio pinned per clip).

### Baseline is not constant across sessions

| Session | n | balanced acc | 95% CI | weak classes |
|---|---|---|---|---|
| Session1 | 192 | 0.635 | [0.568, 0.699] | neutral 0.38, angry 0.65 |
| Session2 | 192 | 0.792 | [0.739, 0.848] | happy 0.67, angry 0.81 |
| Session3 | 192 | 0.818 | [0.763, 0.870] | happy 0.75, neutral 0.77 |
| Session4 | 192 | 0.844 | [0.795, 0.890] | neutral 0.71, happy 0.75 |
| Session5 | 192 | 0.807 | [0.752, 0.860] | neutral 0.73, angry 0.79 |

The clean baseline ranges from **0.635 to 0.844** — a spread of **0.208** — across the five sessions. Session1 is an outlier at the low end (0.635, CI [0.568, 0.699]) and its CI does not overlap Session3 or Session4. **Any accuracy figure quoted for this model must name the session it was measured on**; a single number is not a property of the model.

## 4. What the model tolerates

Ordered by measured harm. A condition is called *tolerated* when the paired difference is within ±0.05 balanced accuracy, *degraded* when worse, and *collapsed* when the collapse convention fires.

**Tolerated (11 conditions)** — usable, no material loss:

| Condition | balanced acc | 95% CI | Δ | effect size (\|h\|) |
|---|---|---|---|---|
| `lowpass:8000.0` | 0.776 | [0.750, 0.802] | +0.000 | 0.000 |
| `clipping:1` | 0.776 | [0.752, 0.801] | +0.000 | 0.000 |
| `highpass:100.0` | 0.766 | [0.743, 0.789] | -0.011 | 0.025 |
| `mp3:64` | 0.765 | [0.740, 0.790] | -0.011 | 0.027 |
| `mp3:32` | 0.762 | [0.738, 0.788] | -0.014 | 0.033 |
| `clipping:5` | 0.761 | [0.737, 0.786] | -0.015 | 0.036 |
| `highpass:200.0` | 0.746 | [0.725, 0.768] | -0.030 | 0.070 |
| `clipping:10` | 0.737 | [0.712, 0.761] | -0.039 | 0.091 |
| `pitch:2.0` | 0.733 | [0.710, 0.756] | -0.043 | 0.099 |
| `timestretch:0.85` | 0.733 | [0.707, 0.759] | -0.043 | 0.100 |
| `gaussian_snr:30.0` | 0.733 | [0.709, 0.755] | -0.044 | 0.102 |

## 5. Where it stops working

| Family | Last healthy | First collapsed | Bracketed interval | Rule that fired |
|---|---|---|---|---|
| gaussian_snr | `gaussian_snr:5.0` | `gaussian_snr:2.0` | [5.0, 2.0] (width 3.0) | majority share 0.82 (>= 0.75) |
| white_noise | `white_noise:0.005` | `white_noise:0.02` | [0.005, 0.02] (width 0.015) | majority share 0.80 (>= 0.75) |
| lowpass | `lowpass:900.0` | `lowpass:850.0` | [900.0, 850.0] (width 50.0) | mean entropy 0.30 (<= 0.30) |
| highpass | `highpass:800.0` | — none in range — | — | no collapse observed |
| mp3 | `mp3:16` | `mp3:8` | [16, 8] (width 8) | majority share 0.84 (>= 0.75) |
| clipping | `clipping:30` | — none in range — | — | no collapse observed |

Intervals are bracketed between two adjacent sampled values — an **inference**, not an observation. The sampling steps were: `gaussian_snr` 0.5 dB inside 6–10 dB, `lowpass` 50 Hz inside 700–1100 Hz, coarser elsewhere.

## 6. Two different ways this model fails

The collapse is not one phenomenon. Grouped by the class the model falls into:

| Constant class it falls into | Triggered by | Evidence |
|---|---|---|
| **happy** | additive noise — real-world SNR below ≈5 dB | `gaussian_snr:0.0` (maj 0.87, P(deg) 1.00), `gaussian_snr:2.0` (maj 0.82, P(deg) 1.00), `white_noise:0.02` (maj 0.80, P(deg) 1.00) |
| **neutral** | bandwidth, codec and timing distortion — low-pass, low-bitrate MP3, time-stretch | `mp3:8` (maj 0.84, P(deg) 1.00), `timestretch:1.5` (maj 0.81, P(deg) 1.00), `lowpass:700.0` (maj 0.72, P(deg) 1.00) |

The rule that fires also differs — the model fails in two mechanically different ways:

| Rule that fired | Conditions | Reading |
|---|---|---|
| `majority_share >= 0.75` | `gaussian_snr:2.0`, `gaussian_snr:0.0`, `white_noise:0.02`, `mp3:8`, `timestretch:1.5` | one class takes over the output — majority share rises to 0.87 |
| `mean_normalised_entropy <= 0.30` | `white_noise:0.05`, `white_noise:0.1`, `lowpass:850.0`, `lowpass:800.0`, `lowpass:700.0` | the output is *confidently wrong* rather than dominated — accuracy is still 0.27–0.48 and the entropy rule fires first |

This matters operationally: a downstream consumer who monitors accuracy alone sees "worse but working". Both signatures are the model emitting a constant, and the two constant classes differ by which part of the signal was destroyed — a check on prediction diversity catches it, an accuracy threshold at 0.5 does not (the `neutral` collapses sit at 0.35–0.49 accuracy).

Full per-condition detail (balanced accuracy, CI, Δ, Δ CI, McNemar p, Holm-adjusted p, majority share, P(degenerate), verdict) is in `outputs/full/full_experiment_results.md`.

## 7. The threshold depends on the evaluation set

This is the most important methodological result here, and it is why v1's numbers moved.

### 7.1 v1 (n=96, balanced subset) vs v2 (n=1241, full session)

| Finding | v1 | v2 |
|---|---|---|
| `gaussian_snr` collapse | first at **7.5 dB** | first at **2 dB**; 5 dB is only degraded |
| `lowpass` collapse | first at **937.5 Hz** | first at **850 Hz** |
| `clipping` | unmeasured (tool defect) | tolerated to 10%, degraded at 20–30%, never collapses |
| clean baseline | 0.698 (balanced 24/class) | 0.776 (CI ±0.024) |

Two causes, and the data separates them:

**(a) Small-sample noise in the collapse statistic.** At n=96 a majority share near 0.65 can exceed 0.75 by chance. Every v1 verdict with `P(degenerate)` unavailable was a single draw from that distribution. v2 reports `P(degenerate)`, so this is now visible instead of implied.

**(b) Class composition.** v1 used a balanced subset; v2 uses the natural distribution. The same model, same session, same condition gives different verdicts on the two sets — §7.2.

### 7.2 Controlled comparison: same session, same condition, different test set

| Condition | full n=1241 | verdict | balanced n=192 | verdict | flip |
|---|---|---|---|---|---|
| `gaussian_snr:7.5` | 0.433 / maj 0.60 / P(deg) 0.00 | not | 0.406 / maj 0.60 / P(deg) 0.00 | not | no |
| `lowpass:900.0` | 0.535 / maj 0.59 / P(deg) 0.01 | not | 0.547 / maj 0.52 / P(deg) 0.58 | COLLAPSE | **YES** |

`lowpass:900.0` **flips** between the two sets. On the full session it is *not* collapsed (P(deg) 0.01 — the data is firmly against the call); on the balanced subset it *is* collapsed, but only just (P(deg) 0.58 — a coin flip). Reporting either verdict alone would have been misleading: the condition sits exactly on the boundary, and the honest statement is "boundary region", not a threshold.

### 7.3 Does the same condition collapse on every session?

| Condition | collapsed on | reading |
|---|---|---|
| `gaussian_snr:7.5` | 0/5 sessions | **stable** — same verdict everywhere |
| `gaussian_snr:4.0` | 1/5 sessions | **unstable** — verdict depends on the session |
| `lowpass:900.0` | 2/5 sessions | **unstable** — verdict depends on the session |
| `lowpass:600.0` | 5/5 sessions | **stable** — same verdict everywhere |

Deep degradation collapses everywhere; borderline conditions do not. That is the difference between a finding and a threshold artefact, and only the cross-session arm can tell them apart. Any threshold from §5 that is not reproduced across sessions should be treated as a boundary region, not a number.

### 7.4 Independent test-set draws

Same session, same conditions, same 48-per-class budget, 5 independent draws (seeds [101, 202, 303, 404, 20261008]):

| Condition | collapsed on | reading |
|---|---|---|
| `gaussian_snr:7.5` | 0/5 draws | **stable** |
| `gaussian_snr:4` | 2/5 draws | **unstable** |
| `lowpass:900` | 2/5 draws | **unstable** |
| `lowpass:600` | 5/5 draws | **stable** |

Only the draw of the subset changes here, so any scatter is pure sampling noise in the collapse detector — no session or class-composition effect can explain it.

## 8. Trust boundary

**Do not rely on this model's output when any of the following holds**, stated in measurable units:

| Condition on the audio | Threshold | Failure mode | Status |
|---|---|---|---|
| Additive noise, SNR | below ≈5 dB (collapsed at 2 dB; 5 dB already −0.42 balanced accuracy) | falls into a constant **happy** | threshold bracketed, stable across sessions |
| Low-pass cutoff | below ≈850 Hz | falls into a constant **neutral**, while accuracy remains 0.35–0.49 | bracketed 900→850 Hz; **borderline, verify per session** |
| Additive noise, fixed amplitude | above ≈0.02 | constant **happy** | collapsed at 0.02 with P(deg)=1.00 |
| MP3 bitrate | below ≈16 kbps (8 kbps collapses) | constant **neutral** | bracketed 16→8 kbps |
| Time stretch | at 1.5× and beyond (1.3× degraded) | constant **neutral** | 1.5× collapsed, P(deg)=1.00 |

**Use with reduced confidence** (measurably degraded, still answering the question, `P(degenerate)` ≈ 0):

| Condition | balanced accuracy | Δ |
|---|---|---|
| `gaussian_snr:5.0` | 0.361 | -0.415 |
| `gaussian_snr:6.0` | 0.390 | -0.387 |
| `gaussian_snr:7.0` | 0.419 | -0.357 |
| `gaussian_snr:7.5` | 0.433 | -0.343 |
| `gaussian_snr:8.0` | 0.446 | -0.330 |
| `gaussian_snr:9.0` | 0.454 | -0.322 |
| `gaussian_snr:8.5` | 0.464 | -0.312 |
| `white_noise:0.005` | 0.475 | -0.301 |
| `gaussian_snr:10.0` | 0.478 | -0.298 |
| `pitch:-6.0` | 0.487 | -0.289 |

**Settings that showed no material loss** (|Δ| < 0.05, paired against clean on the same utterances). Listed per family, with the mildest setting that cost real accuracy:

| Family | Every tolerated setting | Mildest setting that degraded |
|---|---|---|
| gaussian_snr | `30` | `15` dB → degraded (Δ -0.192) |
| white_noise | — none — | `0.005` amplitude → degraded (Δ -0.301) |
| lowpass | `8000` *(no-op control)* — **all tolerated values are no-ops; this family has no demonstrated safe operating point below the clean end** | `2000` Hz → degraded (Δ -0.152) |
| highpass | `100`, `200` | `400` Hz → degraded (Δ -0.090) |
| mp3 | `32`, `64` | `16` kbps → degraded (Δ -0.203) |
| clipping | `1` *(no-op control)*, `5`, `10` | `20` percent-clipped → degraded (Δ -0.116) |
| gain | — none — | `20` dB → degraded (Δ -0.087) |
| pitch | `2` | `-2` semitones → degraded (Δ -0.076) |
| timestretch | `0.85` | `1.15` rate → degraded (Δ -0.133) |

Units are the family's own unit (`catalog` reports them). Note that `lowpass` has no tolerated setting below 8000 Hz and 8000 Hz is the Nyquist limit of 16 kHz audio — so this family has **no demonstrated safe region** inside the tested range: a 2 kHz cutoff already costs 0.152 balanced accuracy.

**white_noise, gain** showed no tolerated setting at all: every level tested cost real accuracy. For `gain` this is notable — a plain recording-level mismatch, the kind of thing that happens whenever a microphone changes, is enough to degrade this model. Robustness to "trivial" transformations cannot be assumed.

## 9. Limitations

1. **One dataset.** Everything is IEMOCAP. Nothing here establishes behaviour on other corpora, other languages, or spontaneous non-acted speech.
2. **One model.** A single fine-tuned wav2vec2-base checkpoint. No claim is made about wav2vec2 generally or about SER generally.
3. **Session1 is weaker and noisier.** Its clean baseline (0.635) is 0.21 below Session4's. Cross-session comparisons involving Session1 carry more uncertainty; the Session1-only collapse of `gaussian_snr:4` should not be relied on.
4. **Thresholds are bracketed, not observed.** Every interval in §5 is an inference between two adjacent sampled values, at the stated step size.
5. **The collapse convention is ours.** `majority_share ≥ 0.75` / `entropy ≤ 0.30` is a definition. Other definitions would move the boundaries. `P(degenerate)` reports how much the data supports each verdict under *this* definition.
6. **Significance is not importance.** At n=1241 the paired test is powerful enough that `highpass:100` reaches p≈9e-06 on a −0.011 change. Conclusions here rest on effect size and the Δ CI, not on p-values. Where a Holm-adjusted p is 0, read it as "far below the resolution of this table", not as a precise quantity.
7. **Two conditions are effective no-ops by construction and are reported as controls:** `lowpass:8000` (the Nyquist limit of 16 kHz audio) and `clipping:1` both returned Δ = +0.000 with McNemar p = 1.0. Their presence is a validation that the pipeline can detect an unchanged condition, not a robustness finding.
8. **Instrument integrity.** All 53 transforms applied successfully, so no condition had to be dropped. This is a change from v1, where the entire `clipping` family was unmeasurable because of the defect documented in `docs/BUGLOG.md`.

## 10. Evidence index

| Artifact | Contents |
|---|---|
| `outputs/full/fam_<family>.json` | per-condition metrics, CIs, paired tests, Holm per family |
| `outputs/full/full_experiment_summary.json` | all conditions, thresholds, global Holm, control |
| `outputs/full/full_experiment_results.md` | flat table of all conditions |
| `outputs/full/xsession_<session>.json` | cross-session arm |
| `outputs/full/seed_replication/` | independent test-set draws at n=192 |
| `evidence/session/` | AGH session export of the v1 agent run (run evidence) |
| `docs/BUGLOG.md` | defects found during the v1 run and their fixes |
| `tools/` | experiment drivers and this report generator |
