# Bug log — defects found in the audit tool during agent-driven runs

Two defects in `audit.py` were found **by the agent, not by us**, during the recorded audit
session on 2026-10-08. Both are kept here because they are evidence of the closed loop working:
the agent observed a result that contradicted its expectations, refused to accept it, and
reported the discrepancy with a reason instead of reporting the number as a finding.

Neither defect changes the model's measured behaviour. Both change what the tool is *able to
measure*, which is why the affected conditions were re-run at full scale after the fix.

---

## BUG-1 — `clipping` never applied: TypeError swallowed by a fallback

### Symptom (as reported by the agent)

Every condition in the `clipping` family produced metrics **bit-identical to the clean
baseline**:

| field | clean (`probe.json`) | `clipping:20` (`sweep2.json`) |
|---|---|---|
| accuracy | 0.6979 | 0.6979 |
| mean_normalised_entropy | 0.369 | 0.369 |
| majority_share | 0.2917 | 0.2917 |
| per-class recall | .625/.667/.958/.542 | .625/.667/.958/.542 |

The run log carried `clipping:20.0 transform failed on one clip → TypeError`, once per clip,
96 times.

### Root cause

`ClippingDistortion` declares its thresholds as `int`. `parse_conditions()` cast **every**
parameter to `float`, so the transform was constructed with `min_percentile_threshold=20.0`.
audiomentations validates the declared type and raises at call time.

Reproduced in isolation (`tools/probe_clipping2.py`):

```
int   (20, 20)      OK    changed=True
float (20.0, 20.0)  FAIL  TypeError: 'float' object cannot be interpreted as an integer
```

`Mp3Compression` does **not** enforce its declared type, which is why `mp3:32` — also an
int-typed family — ran correctly and hid the pattern.

### The second, worse defect

The exception path in `run_conditions()` read:

```python
except Exception as exc:
    log(f"    {family}:{value} transform failed on one clip — {type(exc).__name__}")
    sample = wave          # <-- silent fallback to the clean clip
```

A failed transform therefore became **a second measurement of the clean baseline**, presented
in the results table as a normal condition. The output looked like *"the model is robust to
clipping (accuracy unchanged)"*. The truth was *"clipping was never applied"* — a false
negative on a whole failure family, and exactly the kind of result a model vendor would want
to publish.

> This is the failure mode the tool exists to catch. An audit tool that can silently substitute
> a null condition for a real one is not an audit tool.

### Fix

1. `CATALOG` entries may declare a required parameter type; `parse_conditions()` casts with it
   (`"cast": int` for `clipping` and `mp3`).
2. The exception path no longer substitutes the clean clip. It records `None` for the
   prediction, and the condition is emitted as **`valid: false`** with
   `transform_failures`, `transform_failure_types` and an `invalid_reason`. A condition that
   could not be applied is reported as **UNMEASURED**, never as "no harm".
3. Each valid condition now also reports `clips_actually_modified`, so a transform that
   silently no-ops (e.g. `p < 1`, or a percentile below the signal's noise floor) is visible.

### Verification after fix

`clipping:20` at n=32: `valid: true`, `transform_failures: 0`, `clips_actually_modified: 32`,
balanced accuracy 0.8125 vs clean 0.8438. The family is now measurably **tolerated** rather
than spuriously reported as identical to clean.

---

## BUG-2 — `higher_is_cleaner` inverted for `clipping` and `white_noise`

`catalog` advertised both families with `higher_is_cleaner: true`, i.e. it told a downstream
agent that a *higher* parameter value means *less* distortion. Both are the opposite:

- `clipping`: `percentile_threshold` is the **percentage of the waveform hard-limited**, so
  `30` is more destructive than `1`. Confirmed by `tools/probe_clipping.py`: clipping at 20
  attenuates this clip from ±0.043 to ±0.008; clipping at 1 leaves it untouched.
- `white_noise`: `amplitude` is the added noise amplitude — larger is worse.

An agent that trusted the flag would have ordered its own sweep wrongly and read the collapse
curve backwards.

### Fix

`higher_is_cleaner` set to `false` for both; their `sweep` lists reordered to run from mild to
severe; `clipping`'s unit renamed `percentile` → `percent-clipped`; both descriptions now state
the direction explicitly.

---

## BUG-3 — the audit was not reproducible: stochastic transforms drew from unseeded global RNGs

Found **by us**, on 2026-10-09, while verifying that the new `battery` subcommand reproduced the
numbers already in the report. It did not — and the reason was a defect in the tool, not in the
battery.

### Symptom

The clean arm matched exactly, but perturbed conditions did not:

| field | earlier run | battery re-run |
|---|---|---|
| clean balanced accuracy | 0.7761 | 0.7761 (identical, and CI identical) |
| `gaussian_snr:30` balanced accuracy | 0.7325 | **0.7212** |
| `gaussian_snr:30` accuracy | 0.7027 | **0.6954** |

A gap of ~9 utterances out of 1241 — far too large to be rounding.

### Root cause

The tool seeded its own test-set draw and its bootstrap resamples, and every perturbation pins
`min == max`, so it *looked* deterministic. But in audiomentations the realisation is separate
from the parameter:

```python
# audiomentations/augmentations/add_gaussian_snr.py
def randomize_parameters(self, samples, sample_rate):
    snr = random.uniform(self.min_snr_db, self.max_snr_db)   # Python's global RNG
    ...
def apply(self, samples, sample_rate):
    noise = np.random.normal(0.0, self.parameters["noise_std"], size=samples.shape)
    return samples + noise                                   # numpy's global RNG
```

Pinning `min_snr_db == max_snr_db` pins **the target SNR**, not **the noise waveform**. The noise
is drawn from two process-global RNGs that the tool never seeded, so:

- `gaussian_snr` and `white_noise` produced different audio on every run;
- `lowpass`, `highpass`, `gain`, `clipping`, `mp3`, `pitch`, `timestretch` are deterministic DSP
  and were unaffected.

This also invalidated a claim made earlier in the project — that nine independent runs agreeing on
the clean arm demonstrated end-to-end determinism. It demonstrated determinism of the **clean arm
only**, which passes through no transform at all. The perturbed conditions had never been checked.

### Fix

`run_conditions` now seeds **both global RNGs per condition**, with a seed derived from the
condition name:

```python
condition_seed = SEED + zlib.crc32(f"{family}:{value}".encode()) % 100000
random.seed(condition_seed)
np.random.seed(condition_seed)
```

Deriving the seed *per condition* rather than once per run matters: it makes a condition's audio
independent of measurement order, which is what allows the `battery` work to be split across
several calls without changing the result.

### Verification

`tools/verify_determinism.py` runs the same conditions in two fresh processes and diffs every
field (`gaussian_snr:30`, `white_noise:0.02`, `lowpass:2000`, `clipping:10`): **identical**. The
clean arm is identical too.

### Consequence

Every number produced before this fix is superseded for the two stochastic families. The
confirmatory battery was therefore re-measured with the fixed tool, and
`trust_boundary_report_v2.md` was regenerated from that output, so the report has a single
provenance and the recorded AGH session reproduces it exactly.

---

## BUG-4 — `lowpass` / `highpass` measured a mixture of filters, not one filter

Found immediately after BUG-3, from the same verification: after seeding the RNGs, `gaussian_snr`
and `white_noise` became reproducible, but measuring one representative condition per family
showed that `lowpass` and `highpass` had **also** moved relative to the earlier run:

| family | earlier run | after the BUG-3 fix | delta |
|---|---|---|---|
| `gaussian_snr:30` | 0.7325 | 0.7214 | −0.0111 |
| `lowpass:2000` | 0.6246 | 0.6176 | −0.0070 |
| `highpass:400` | 0.6865 | 0.6799 | −0.0066 |
| `white_noise:0.02` | 0.2856 | 0.2892 | +0.0036 |
| `gain:-20`, `pitch:4`, `timestretch:1.3` | — | — | unchanged |

### Root cause

`LowPassFilter` and `HighPassFilter` inherit `BaseButterworthFilter.randomize_parameters`, which
draws the filter **order** from the RNG on every clip:

```python
# audiomentations/augmentations/base_butterword_filter.py
random_order = random.randint(self.min_rolloff // 6, self.max_rolloff // 6)
self.parameters["rolloff"] = random_order * 6
```

The library defaults are `min_rolloff=12, max_rolloff=24`, and the audit never overrode them — it
only pinned `min_cutoff_freq == max_cutoff_freq`. So each clip was filtered by an order drawn from
{2, 3, 4}, and the reported number was an **average over an uncontrolled nuisance parameter**.

This is distinct from BUG-3: seeding made those measurements *reproducible*, but still not
*well-defined*. "lowpass:900" did not denote one perturbed signal; it denoted three.

> The other families were unaffected for a simple reason: their randomness is a draw over a range
> that was already pinned to a single value. `ClippingDistortion` uses `random.randint(min, max)`
> and `Mp3Compression` uses `random.choice(...)` over a one-element list, so both are degenerate.
> `Gain` uses `random.uniform(min, max)`, likewise degenerate. Only the filters have a *second*,
> independent parameter that was never pinned.

### Fix

`build_transform` now pins the roll-off as well:

```python
LowPassFilter(min_cutoff_freq=value, max_cutoff_freq=value,
              min_rolloff=18, max_rolloff=18, p=1.0)
```

18 dB/octave (order 3) is the **midpoint of audiomentations' default range [12, 24]**, chosen
deliberately: it makes the condition a single well-defined filter, and it keeps the operating
point closest to what had already been measured, so the correction is a definition fix rather
than a change of experimental conditions. The `catalog` descriptions and the report now state the
roll-off explicitly.

### Verification

`tools/verify_determinism.py` now covers six conditions across the four previously uncertain
families (`gaussian_snr`, `white_noise`, `lowpass`, `highpass`) plus two known-deterministic ones
(`clipping`, `mp3`): all six and the clean arm are **identical across two fresh processes**.

### Consequence

Together with BUG-3 this invalidates the earlier numbers for **four** of the nine families, so the
confirmatory battery was re-measured from scratch with the fixed tool and the report regenerated
from that single output. **No collapse verdict flipped in any of the four** — the effect is
0.004–0.011 in balanced accuracy, well inside the reported confidence intervals — so the
conclusions stand; only the figures changed.

---

## Why this is in the submission

The recorded session shows the agent doing three things a fixed pipeline does not:

1. **Detected an implausible result** — it noticed that a perturbation returned numbers
   *identical* to clean, rather than merely similar.
2. **Diagnosed rather than reported** — it traced the identity to the transform failing on
   every clip and declared the family **unmeasured**, declining to write "model is robust to
   clipping" into the report.
3. **Refused to fix the tool itself**, flagging the defect for the humans instead of silently
   patching the measurement mid-audit — the correct behaviour when the tool is the instrument
   of record.

The agent's own write-up of the defect is preserved verbatim in
`trust_boundary_report.md` §4 ("Measurement failure: `clipping:20`").
