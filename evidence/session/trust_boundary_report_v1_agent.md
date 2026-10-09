# Trust Boundary Report — SER Model `superb-er`

All numbers below are traceable to the JSON files in `evidence/` (probe.json, sweep1.json,
sweep2.json, curve_snr.json, curve_lowpass.json). No numbers have been fabricated.

---

## 1. Scope

- Model: `<workspace>\models\superb-er`
- **Model fingerprint: `dac0f46128deec04`**
- Model labels: `0=neu, 1=hap, 2=ang, 3=sad` (catalog reports 4 classes: angry, happy, sad, neutral)
- Dataset split: **Session5 only** of the IEMOCAP-style dataset
- Per-class sample: **24** → **96 utterances** total
- Seed: **20261008** (per run manifest)
- Device: **CUDA — NVIDIA GeForce GTX 1650**
- Chance level for 4 classes: **0.25**
- Collapse rule: `degenerate` when `majority_share >= 0.75` **or** `mean_normalised_entropy <= 0.30`

---

## 2. Baseline (clean, probe.json)

- Clean accuracy: **0.6979** (vs. chance 0.25 → 2.79× chance; ~0.448 above chance)
- Majority share: 0.2917 (class `sad`)
- Mean normalised entropy: **0.369**
- `degenerate: false`
- Throughput: **15.64 clips/s** (64 ms per clip)
- Per-class recall: angry 0.625, happy 0.6667, sad 0.9583, neutral 0.5417
- Notable: even clean baseline shows a mild prior toward `sad` and weak recall on `neutral`.

---

## 3. Findings — Round 1 sweep (sweep1.json) — different mechanisms

| Condition | Accuracy | Δ vs. clean (0.698) | Entropy | Majority | Distinct preds | Degenerate? |
|---|---|---|---|---|---|---|
| clean (probe) | 0.698 | — | 0.369 | 0.29 | 4 | no |
| `gaussian_snr:10` dB (additive noise) | **0.469** | −0.229 | 0.469 | 0.59 | 4 | no |
| `lowpass:1000` Hz (bandwidth loss) | **0.552** | −0.146 | 0.309 | 0.51 | 4 | no (borderline) |
| `mp3:32` kbps (codec) | **0.729** | **+0.031** | 0.377 | 0.27 | 4 | no |
| `pitch:+4` semitones (prosody) | **0.635** | −0.063 | 0.365 | 0.46 | 4 | no |

### Interpretation

- **MP3 at 32 kbps**: model is *tolerant* — accuracy actually exceeds clean (0.729 > 0.698). Codec artefacts at 32 kbps do not harm this model.
- **Pitch shift +4 st**: only mildly hurts (0.635). Prosody-mismatch via pitch is tolerable.
- **SNR 10 dB**: model becomes *unsure* — accuracy drops to 0.469 but entropy **rises to 0.469** (from 0.369). The model is still answering the question (4 distinct predictions, majority 0.59); it is just much less confident. This is "hesitation", not collapse.
- **Lowpass 1000 Hz**: accuracy 0.552, entropy 0.309 (very close to the 0.30 collapse line). The model is *borderline* — still not degenerate at 1000 Hz, but the next lower step will cross the line (see curve below).

> Note: `mp3:32` accuracy (0.729) exceeding the clean baseline (0.698) is not a signal that the model is "better" with codec; it is a sampling-noise effect with n=96. Report it as "no measured harm", not "improvement".

---

## 4. Findings — Round 2 sweep (sweep2.json) — push each mechanism past its comfort zone

| Condition | Accuracy | Entropy | Majority | Degenerate? |
|---|---|---|---|---|
| `gaussian_snr:0` dB | **0.281** | **0.247** | **0.833** (`happy`) | **YES** — majority ≥ 0.75 |
| `lowpass:500` Hz | **0.396** | **0.166** | **0.760** (`neutral`) | **YES** — majority ≥ 0.75 |
| `pitch:-4` st | 0.531 | 0.429 | 0.385 | no |
| `mp3:16` kbps | 0.521 | 0.345 | 0.656 | no |
| `clipping:20` % | 0.698 | 0.369 | 0.292 | no — **see §5 failure note** |
| `timestretch:1.3` | 0.469 | 0.355 | 0.615 | no |
| `gain:-20` dB | 0.646 | 0.386 | 0.385 | no |

### Interpretation

- **`gaussian_snr:0` dB → COLLAPSE.** Majority share 0.83, only 2 distinct predictions, model answers "happy" for essentially everything. Accuracy (0.281) is barely above chance. This is **not** a "merely degraded" result — the model has stopped answering the question.
- **`lowpass:500` Hz → COLLAPSE.** Majority share 0.76, 3 distinct predictions, model answers "neutral" for essentially everything. Same failure mode: stopped answering.
- **`pitch:-4` st** is still "unsure" (entropy 0.429, no degenerate flag).
- **`mp3:16` kbps** is "unsure" but not degenerate.
- **`timestretch:1.3`** is "unsure" (entropy normal, majority 0.61) — time-stretching hurts accuracy more than the model's confidence suggests.
- **`gain:-20 dB`** is tolerable (acc 0.646, entropy 0.386, majority 0.39).
- **`clipping:20%`** — **measurement failure, see §5.**

### ⚠️ Measurement failure: `clipping:20`

The run log reports:
```
clipping:20.0 transform failed on one clip → TypeError
```
repeated for every one of the 96 clips. Despite this, the sweep still emitted a result row:
`acc=0.698, entropy=0.369, majority=0.29, distinct=4, degenerate=false`
— numbers that are **bit-identical to the clean baseline** (probe: 0.698 / 0.369 / 0.29).

Per the skill protocol, a condition that is bit-identical to clean when every clip failed its transform is not evidence of robustness — it is evidence that **the transform silently did nothing** and the result is actually another measurement of the clean baseline. **The `clipping` family must be treated as unmeasured in this run.** I have not modified `audit.py` to investigate the TypeError; flagging it here as a finding.

---

## 5. Thresholds located by curve

### 5.1 `gaussian_snr` (curve_snr.json, 10 → 0 dB, 9 points, step = 1.25 dB)

| SNR (dB) | Accuracy | Entropy | Majority | Degenerate? |
|---|---|---|---|---|
| 10.00 | 0.458 | 0.469 | 0.594 | no |
| 8.75 | 0.417 | 0.459 | 0.667 | no |
| **7.50** | **0.365** | **0.426** | **0.760** | **YES** (majority ≥ 0.75) |
| 6.25 | 0.396 | 0.416 | 0.771 | YES |
| 5.00 | 0.323 | 0.369 | 0.802 | YES |
| 3.75 | 0.323 | 0.316 | 0.813 | YES |
| 2.50 | 0.260 | 0.302 | 0.833 | YES |
| 1.25 | 0.260 | 0.265 | 0.875 | YES |
| 0.00 | 0.250 | 0.249 | 0.885 | YES |

- **First degenerate point: `gaussian_snr:7.5` dB** (per tool's own `first_degenerate`).
- The transition from "unsure" to "collapsed" happens between 8.75 dB (not degenerate) and 7.50 dB (degenerate).
- **Sampled spacing in this region: 1.25 dB.** The threshold is therefore **located to within ±1.25 dB, i.e. between 7.5 and 8.75 dB SNR** — this is an **inference** from two adjacent samples; the curve was not run finer than 1.25 dB.
- Pattern: accuracy degrades smoothly from 0.458 → 0.250; **majority share jumps discretely from 0.667 to 0.760** — a genuine discontinuity at 7.5 dB, not a gradual fade.

### 5.2 `lowpass` (curve_lowpass.json, 1000 → 500 Hz, 9 points, step = 62.5 Hz)

| Cutoff (Hz) | Accuracy | Entropy | Majority | Degenerate? |
|---|---|---|---|---|
| 1000 | 0.531 | 0.316 | 0.500 | no |
| **937.5** | **0.552** | **0.297** | **0.500** | **YES** (entropy ≤ 0.30) |
| 875 | 0.573 | 0.287 | 0.531 | YES |
| 812.5 | 0.490 | 0.295 | 0.635 | YES |
| 750 | 0.479 | 0.288 | 0.646 | YES |
| 687.5 | 0.469 | 0.259 | 0.677 | YES |
| 625 | 0.438 | 0.240 | 0.729 | YES |
| 562.5 | 0.375 | 0.213 | 0.823 | YES |
| 500 | 0.354 | 0.219 | 0.792 | YES |

- **First degenerate point: `lowpass:937.5` Hz** — degenerate by the *entropy* rule, not the majority-share rule. Accuracy is actually still 0.552 here. The tool flags `first_degenerate = lowpass:937.5`.
- **Important:** this lowpass "collapse" has a **different signature** than the SNR collapse. At 937.5 Hz the model still answers 4 distinct classes and its accuracy is 0.552 (above the SNR-collapsed 0.25–0.40 range). It only becomes majority-dominated by 562.5 Hz (majority 0.82).
- The threshold "below which the model is no longer trustworthy" for lowpass is therefore **between 1000 Hz and 937.5 Hz**, located to within **±62.5 Hz** by sampling. **This is an inference from two adjacent samples.**
- Practical read: the model is *confidently wrong* in this band (accuracy 0.49–0.57 with entropy 0.22–0.30 and majority "neutral"). It is not "unsure" the way it is at SNR 10 dB; it has **stopped answering the question** and is defaulting to `neutral`.

---

## 6. Trust boundary — conditions under which this model's output should NOT be relied on

Based on the measurements above, the model is **untrustworthy** (its output should not be used for any downstream decision) under:

| Condition | Measured threshold | Evidence | Failure mode |
|---|---|---|---|
| Additive Gaussian noise | **SNR < 7.5 dB** (first degenerate point; threshold inferred to ±1.25 dB between 7.5 and 8.75) | curve_snr.json | **Collapse to "happy"** (majority 0.76 → 0.89) |
| Bandwidth restriction (low-pass) | **cutoff < 1000 Hz** (first degenerate point at 937.5 Hz; threshold inferred to ±62.5 Hz between 937.5 and 1000) | curve_lowpass.json | **Collapse to "neutral"** (majority 0.50 → 0.82); accuracy in 0.35–0.57 range with entropy ≤ 0.30 |
| Any condition producing `majority_share ≥ 0.75` or `mean_normalised_entropy ≤ 0.30` (the tool's own collapse rule) | — | per-condition degenerate flag | Model has stopped answering the question |

Additional **caution** (model is still answering, but is measurably degraded — usable with reduced confidence, not "trustworthy" in the same sense as clean):

| Condition | Measured state |
|---|---|
| SNR 10 dB | acc 0.469, entropy 0.469 — model is *unsure* (high entropy, low accuracy); not collapsed |
| Lowpass 1000 Hz | acc 0.552, entropy 0.309 — *borderline*, just above the entropy collapse line |
| Pitch shift ±4 st | acc 0.531 / 0.635, entropy 0.36–0.43 — mildly degraded, not collapsed |
| `timestretch:1.3` | acc 0.469, entropy 0.355 — measurably degraded, not collapsed |
| `mp3:16` kbps | acc 0.521, entropy 0.345 — degraded but model still spread over 4 classes |
| `gain:-20 dB` | acc 0.646, entropy 0.386 — essentially clean; gain is **tolerated** |
| `mp3:32` kbps | acc 0.729 — no measured harm at this bitrate (see caveat in §3) |

The model is **tolerant** of: 32 kbps MP3, pitch shifts of ±4 semitones, −20 dB gain. It is **not** tolerant of: SNR below ≈ 7.5–8.75 dB, low-pass cutoffs below 1000 Hz, and it shows clear degradation at timestretch 1.3× and low-bitrate (16 kbps) MP3.

---

## 7. Limitations

1. **Sample size.** n = 96 utterances (24 per class). Confidence intervals on accuracy at this n are roughly ±0.10 (1 std error ≈ √(p(1−p)/n) ≈ 0.05; ±1 SE ≈ ±0.05, ±2 SE ≈ ±0.10). Differences of 0.05 or less between conditions (e.g., MP3:32 kbps "beating" clean) are **not** statistically meaningful.
2. **Single session.** All measurements use **Session5 only**. No other session was audited; generalisation to Sessions 1–4, 7–10 is **not** established.
3. **Unmeasured families.** `highpass`, `white_noise` (fixed amplitude, no SNR control), and **`clipping` (unmeasured due to the TypeError failure in §5)** have no threshold in this report.
4. **Inferred thresholds.** All thresholds marked "±X in between two adjacent samples" are **inferences**, not observations. The curve sampling step was:
   - `gaussian_snr`: 1.25 dB step → threshold in [7.5, 8.75] dB
   - `lowpass`: 62.5 Hz step → threshold in [937.5, 1000] Hz
   A finer run (e.g., 0.625 dB / 31.25 Hz) would tighten these.
5. **The `lowpass` collapse threshold (937.5 Hz) is triggered by the entropy rule, not the majority-share rule** — this is a genuinely different failure signature from `gaussian_snr`, and both should be reported as separate findings.
6. **No clean-session replication.** No re-run with a different seed or session was performed to check stability of the clean-baseline number 0.698.
7. **Clipping transform is broken in the tool** (`TypeError` on every clip). Until that is fixed, no claim about clipping robustness is possible. I have **not** modified `audit.py` to work around this.

---

## 8. Evidence files

- `evidence/probe.json` — clean baseline, label space, fingerprint, throughput
- `evidence/sweep1.json` — round-1 four-mechanism sweep
- `evidence/sweep2.json` — round-2 push-past-comfort sweep + clipping failure
- `evidence/curve_snr.json` — gaussian_snr 10 → 0 dB, 9 points, step 1.25 dB
- `evidence/curve_lowpass.json` — lowpass 1000 → 500 Hz, 9 points, step 62.5 Hz
