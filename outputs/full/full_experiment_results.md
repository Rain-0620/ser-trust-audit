# Full-scale audit results — Session5, n = 1241

Balanced accuracy (macro recall) with 95% bootstrap CI; delta and exact McNemar p-value are paired against the clean reference on the same utterances.

| Condition | Bal. acc | 95% CI | Δ vs clean | McNemar p | Holm (family) | Majority | P(deg) | Verdict |
|---|---|---|---|---|---|---|---|---|
| `gaussian_snr:30.0` | 0.733 | [0.709, 0.755] | -0.044 | 0.00e+00 | 0.00e+00 | happy 0.39 | 0.00 | tolerated |
| `gaussian_snr:15.0` | 0.584 | [0.554, 0.612] | -0.192 | 0.00e+00 | 0.00e+00 | happy 0.47 | 0.00 | degraded |
| `gaussian_snr:10.0` | 0.478 | [0.453, 0.505] | -0.298 | 0.00e+00 | 0.00e+00 | happy 0.52 | 0.00 | degraded |
| `gaussian_snr:9.0` | 0.454 | [0.430, 0.479] | -0.322 | 0.00e+00 | 0.00e+00 | happy 0.55 | 0.00 | degraded |
| `gaussian_snr:8.5` | 0.464 | [0.440, 0.490] | -0.312 | 0.00e+00 | 0.00e+00 | happy 0.56 | 0.00 | degraded |
| `gaussian_snr:8.0` | 0.446 | [0.421, 0.469] | -0.330 | 0.00e+00 | 0.00e+00 | happy 0.58 | 0.00 | degraded |
| `gaussian_snr:7.5` | 0.433 | [0.410, 0.457] | -0.343 | 0.00e+00 | 0.00e+00 | happy 0.60 | 0.00 | degraded |
| `gaussian_snr:7.0` | 0.419 | [0.397, 0.441] | -0.357 | 0.00e+00 | 0.00e+00 | happy 0.62 | 0.00 | degraded |
| `gaussian_snr:6.0` | 0.390 | [0.368, 0.412] | -0.387 | 0.00e+00 | 0.00e+00 | happy 0.65 | 0.00 | degraded |
| `gaussian_snr:5.0` | 0.361 | [0.339, 0.382] | -0.415 | 0.00e+00 | 0.00e+00 | happy 0.69 | 0.00 | degraded |
| `gaussian_snr:2.0` | 0.282 | [0.268, 0.297] | -0.494 | 0.00e+00 | 0.00e+00 | happy 0.82 | 1.00 | **COLLAPSE** |
| `gaussian_snr:0.0` | 0.255 | [0.242, 0.268] | -0.522 | 0.00e+00 | 0.00e+00 | happy 0.87 | 1.00 | **COLLAPSE** |
| `lowpass:8000.0` | 0.776 | [0.750, 0.802] | +0.000 | 1.00e+00 | 1.00e+00 | happy 0.35 | 0.00 | tolerated |
| `lowpass:2000.0` | 0.625 | [0.600, 0.650] | -0.152 | 0.00e+00 | 0.00e+00 | neutral 0.50 | 0.00 | degraded |
| `lowpass:1100.0` | 0.548 | [0.524, 0.572] | -0.228 | 0.00e+00 | 0.00e+00 | neutral 0.54 | 0.00 | degraded |
| `lowpass:1000.0` | 0.548 | [0.523, 0.573] | -0.228 | 0.00e+00 | 0.00e+00 | neutral 0.55 | 0.00 | degraded |
| `lowpass:950.0` | 0.544 | [0.520, 0.569] | -0.232 | 0.00e+00 | 0.00e+00 | neutral 0.57 | 0.00 | degraded |
| `lowpass:900.0` | 0.535 | [0.511, 0.560] | -0.241 | 0.00e+00 | 0.00e+00 | neutral 0.59 | 0.01 | degraded |
| `lowpass:850.0` | 0.519 | [0.494, 0.544] | -0.257 | 0.00e+00 | 0.00e+00 | neutral 0.62 | 0.76 | **COLLAPSE** |
| `lowpass:800.0` | 0.493 | [0.468, 0.519] | -0.283 | 0.00e+00 | 0.00e+00 | neutral 0.65 | 1.00 | **COLLAPSE** |
| `lowpass:700.0` | 0.451 | [0.426, 0.475] | -0.325 | 0.00e+00 | 0.00e+00 | neutral 0.72 | 1.00 | **COLLAPSE** |
| `highpass:800.0` | 0.558 | [0.535, 0.584] | -0.218 | 0.00e+00 | 0.00e+00 | angry 0.39 | 0.00 | degraded |
| `highpass:400.0` | 0.686 | [0.663, 0.710] | -0.090 | 0.00e+00 | 0.00e+00 | angry 0.35 | 0.00 | degraded |
| `highpass:200.0` | 0.746 | [0.725, 0.768] | -0.030 | 0.00e+00 | 0.00e+00 | neutral 0.31 | 0.00 | tolerated |
| `highpass:100.0` | 0.766 | [0.743, 0.789] | -0.011 | 9.00e-06 | 9.00e-06 | neutral 0.29 | 0.00 | tolerated |
| `clipping:30` | 0.585 | [0.557, 0.613] | -0.192 | 0.00e+00 | 0.00e+00 | sad 0.38 | 0.00 | degraded |
| `clipping:20` | 0.660 | [0.634, 0.687] | -0.116 | 0.00e+00 | 0.00e+00 | sad 0.35 | 0.00 | degraded |
| `clipping:10` | 0.737 | [0.712, 0.761] | -0.039 | 0.00e+00 | 0.00e+00 | neutral 0.33 | 0.00 | tolerated |
| `clipping:5` | 0.761 | [0.737, 0.786] | -0.015 | 1.24e-02 | 2.48e-02 | neutral 0.32 | 0.00 | tolerated |
| `clipping:1` | 0.776 | [0.752, 0.801] | +0.000 | 1.00e+00 | 1.00e+00 | happy 0.35 | 0.00 | tolerated |
| `mp3:64` | 0.765 | [0.740, 0.790] | -0.011 | 3.02e-01 | 3.02e-01 | happy 0.36 | 0.00 | tolerated |
| `mp3:32` | 0.762 | [0.738, 0.788] | -0.014 | 1.35e-01 | 2.71e-01 | neutral 0.34 | 0.00 | tolerated |
| `mp3:16` | 0.573 | [0.548, 0.598] | -0.203 | 0.00e+00 | 0.00e+00 | neutral 0.67 | 0.06 | degraded |
| `mp3:8` | 0.409 | [0.386, 0.432] | -0.367 | 0.00e+00 | 0.00e+00 | neutral 0.84 | 1.00 | **COLLAPSE** |
| `white_noise:0.1` | 0.218 | [0.198, 0.238] | -0.558 | 0.00e+00 | 0.00e+00 | happy 0.53 | 1.00 | **COLLAPSE** |
| `white_noise:0.05` | 0.237 | [0.220, 0.255] | -0.539 | 0.00e+00 | 0.00e+00 | happy 0.65 | 1.00 | **COLLAPSE** |
| `white_noise:0.02` | 0.286 | [0.267, 0.305] | -0.490 | 0.00e+00 | 0.00e+00 | happy 0.80 | 1.00 | **COLLAPSE** |
| `white_noise:0.005` | 0.475 | [0.447, 0.501] | -0.301 | 0.00e+00 | 0.00e+00 | happy 0.66 | 0.00 | degraded |
| `gain:20.0` | 0.689 | [0.661, 0.713] | -0.087 | 0.00e+00 | 0.00e+00 | happy 0.40 | 0.00 | degraded |
| `gain:-10.0` | 0.672 | [0.643, 0.702] | -0.104 | 0.00e+00 | 0.00e+00 | happy 0.46 | 0.00 | degraded |
| `gain:-20.0` | 0.601 | [0.573, 0.625] | -0.175 | 0.00e+00 | 0.00e+00 | neutral 0.40 | 0.00 | degraded |
| `gain:-30.0` | 0.525 | [0.498, 0.551] | -0.252 | 0.00e+00 | 0.00e+00 | neutral 0.40 | 0.00 | degraded |
| `pitch:6.0` | 0.576 | [0.551, 0.601] | -0.200 | 0.00e+00 | 0.00e+00 | angry 0.38 | 0.00 | degraded |
| `pitch:4.0` | 0.629 | [0.606, 0.651] | -0.147 | 0.00e+00 | 0.00e+00 | angry 0.39 | 0.00 | degraded |
| `pitch:2.0` | 0.733 | [0.710, 0.756] | -0.043 | 0.00e+00 | 0.00e+00 | neutral 0.27 | 0.00 | tolerated |
| `pitch:-2.0` | 0.700 | [0.674, 0.724] | -0.076 | 0.00e+00 | 0.00e+00 | neutral 0.36 | 0.00 | degraded |
| `pitch:-4.0` | 0.574 | [0.547, 0.601] | -0.202 | 0.00e+00 | 0.00e+00 | neutral 0.41 | 0.00 | degraded |
| `pitch:-6.0` | 0.487 | [0.457, 0.515] | -0.289 | 0.00e+00 | 0.00e+00 | neutral 0.47 | 0.00 | degraded |
| `timestretch:1.5` | 0.415 | [0.395, 0.434] | -0.361 | 0.00e+00 | 0.00e+00 | neutral 0.81 | 1.00 | **COLLAPSE** |
| `timestretch:1.3` | 0.494 | [0.473, 0.514] | -0.282 | 0.00e+00 | 0.00e+00 | neutral 0.70 | 0.00 | degraded |
| `timestretch:1.15` | 0.644 | [0.619, 0.668] | -0.133 | 0.00e+00 | 0.00e+00 | neutral 0.51 | 0.00 | degraded |
| `timestretch:0.85` | 0.733 | [0.707, 0.759] | -0.043 | 0.00e+00 | 0.00e+00 | neutral 0.33 | 0.00 | tolerated |
| `timestretch:0.7` | 0.637 | [0.610, 0.666] | -0.139 | 0.00e+00 | 0.00e+00 | sad 0.37 | 0.00 | degraded |

## Located thresholds

| Family | Last healthy | First collapsed | Bracketed interval | Signature |
|---|---|---|---|---|
| gaussian_snr | gaussian_snr:5.0 | gaussian_snr:2.0 | [5.0, 2.0] (width 3.0) | majority share 0.82 (>= 0.75) |
| lowpass | lowpass:900.0 | lowpass:850.0 | [900.0, 850.0] (width 50.0) | mean entropy 0.30 (<= 0.30) |
| highpass | highpass:800.0 | — none in range — | — | no collapse observed |
| clipping | clipping:30 | — none in range — | — | no collapse observed |
| mp3 | mp3:16 | mp3:8 | [16, 8] (width 8) | majority share 0.84 (>= 0.75) |
| white_noise | white_noise:0.005 | white_noise:0.02 | [0.005, 0.02] (width 0.015) | majority share 0.80 (>= 0.75) |

## Sample-design control (same session, different test set)

Session5 is evaluated twice: as the full 4-class set (n=1241, natural class distribution) and as a balanced subset (n=192). Shared conditions show whether a collapse verdict is a property of the model or of the evaluation set.

| Condition | Full n=1241 bacc | Full majority | Full verdict | Balanced n=192 bacc | Balanced majority | Balanced verdict | Flip? |
|---|---|---|---|---|---|---|---|
| `gaussian_snr:7.5` | 0.433 | 0.60 | not | 0.406 | 0.60 | not | no |
| `lowpass:900.0` | 0.535 | 0.59 | not | 0.547 | 0.52 | COLLAPSE | **YES** |

_A flipped verdict here means the collapse call depends on the evaluation set, not only on the model: the small balanced subset and the full session disagree._