# Confirmatory battery — Session5, n = 1241

Measured by `audit.py battery`. Balanced accuracy with a 95% bootstrap CI; delta and exact McNemar p are paired against the clean arm on the same utterances.

| Condition | Bal. acc | 95% CI | Δ vs clean | McNemar p | Holm (family) | Majority | P(deg) | Verdict |
|---|---|---|---|---|---|---|---|---|
| `gaussian_snr:30.0` | 0.721 | [0.697, 0.745] | -0.055 | 0.00e+00 | 0.00e+00 | happy 0.41 | 0.00 | degraded |
| `gaussian_snr:15.0` | 0.585 | [0.557, 0.613] | -0.191 | 0.00e+00 | 0.00e+00 | happy 0.48 | 0.00 | degraded |
| `gaussian_snr:10.0` | 0.483 | [0.459, 0.510] | -0.293 | 0.00e+00 | 0.00e+00 | happy 0.53 | 0.00 | degraded |
| `gaussian_snr:9.0` | 0.477 | [0.451, 0.503] | -0.299 | 0.00e+00 | 0.00e+00 | happy 0.54 | 0.00 | degraded |
| `gaussian_snr:8.5` | 0.460 | [0.436, 0.485] | -0.316 | 0.00e+00 | 0.00e+00 | happy 0.57 | 0.00 | degraded |
| `gaussian_snr:8.0` | 0.440 | [0.414, 0.463] | -0.336 | 0.00e+00 | 0.00e+00 | happy 0.59 | 0.00 | degraded |
| `gaussian_snr:7.5` | 0.433 | [0.409, 0.458] | -0.343 | 0.00e+00 | 0.00e+00 | happy 0.59 | 0.00 | degraded |
| `gaussian_snr:7.0` | 0.417 | [0.396, 0.439] | -0.359 | 0.00e+00 | 0.00e+00 | happy 0.61 | 0.00 | degraded |
| `gaussian_snr:6.0` | 0.387 | [0.364, 0.409] | -0.389 | 0.00e+00 | 0.00e+00 | happy 0.65 | 0.00 | degraded |
| `gaussian_snr:5.0` | 0.353 | [0.332, 0.374] | -0.423 | 0.00e+00 | 0.00e+00 | happy 0.70 | 0.00 | degraded |
| `gaussian_snr:2.0` | 0.288 | [0.272, 0.304] | -0.488 | 0.00e+00 | 0.00e+00 | happy 0.81 | 1.00 | **COLLAPSE** |
| `gaussian_snr:0.0` | 0.252 | [0.240, 0.264] | -0.525 | 0.00e+00 | 0.00e+00 | happy 0.87 | 1.00 | **COLLAPSE** |
| `lowpass:8000.0` | 0.776 | [0.750, 0.802] | +0.000 | 1.00e+00 | 1.00e+00 | happy 0.35 | 0.00 | tolerated |
| `lowpass:2000.0` | 0.613 | [0.589, 0.637] | -0.163 | 0.00e+00 | 0.00e+00 | neutral 0.50 | 0.00 | degraded |
| `lowpass:1100.0` | 0.546 | [0.523, 0.570] | -0.230 | 0.00e+00 | 0.00e+00 | neutral 0.53 | 0.00 | degraded |
| `lowpass:1000.0` | 0.535 | [0.509, 0.560] | -0.241 | 0.00e+00 | 0.00e+00 | neutral 0.55 | 0.00 | degraded |
| `lowpass:950.0` | 0.531 | [0.507, 0.555] | -0.245 | 0.00e+00 | 0.00e+00 | neutral 0.57 | 0.00 | degraded |
| `lowpass:900.0` | 0.524 | [0.499, 0.547] | -0.252 | 0.00e+00 | 0.00e+00 | neutral 0.60 | 0.13 | degraded |
| `lowpass:850.0` | 0.503 | [0.479, 0.529] | -0.273 | 0.00e+00 | 0.00e+00 | neutral 0.62 | 0.83 | **COLLAPSE** |
| `lowpass:800.0` | 0.492 | [0.468, 0.517] | -0.284 | 0.00e+00 | 0.00e+00 | neutral 0.65 | 1.00 | **COLLAPSE** |
| `lowpass:700.0` | 0.437 | [0.413, 0.461] | -0.339 | 0.00e+00 | 0.00e+00 | neutral 0.73 | 1.00 | **COLLAPSE** |
| `highpass:800.0` | 0.569 | [0.545, 0.592] | -0.207 | 0.00e+00 | 0.00e+00 | angry 0.42 | 0.00 | degraded |
| `highpass:400.0` | 0.677 | [0.653, 0.700] | -0.099 | 0.00e+00 | 0.00e+00 | angry 0.37 | 0.00 | degraded |
| `highpass:200.0` | 0.736 | [0.714, 0.758] | -0.040 | 0.00e+00 | 0.00e+00 | neutral 0.31 | 0.00 | tolerated |
| `highpass:100.0` | 0.767 | [0.745, 0.790] | -0.009 | 5.00e-06 | 5.00e-06 | neutral 0.30 | 0.00 | tolerated |
| `clipping:30.0` | 0.585 | [0.555, 0.612] | -0.192 | 0.00e+00 | 0.00e+00 | sad 0.38 | 0.00 | degraded |
| `clipping:20.0` | 0.660 | [0.633, 0.687] | -0.116 | 0.00e+00 | 0.00e+00 | sad 0.35 | 0.00 | degraded |
| `clipping:10.0` | 0.737 | [0.711, 0.761] | -0.039 | 0.00e+00 | 0.00e+00 | neutral 0.33 | 0.00 | tolerated |
| `clipping:5.0` | 0.761 | [0.736, 0.787] | -0.015 | 1.24e-02 | 2.48e-02 | neutral 0.32 | 0.00 | tolerated |
| `clipping:1.0` | 0.776 | [0.752, 0.800] | +0.000 | 1.00e+00 | 1.00e+00 | happy 0.35 | 0.00 | tolerated |
| `mp3:64.0` | 0.765 | [0.739, 0.790] | -0.011 | 3.02e-01 | 3.02e-01 | happy 0.36 | 0.00 | tolerated |
| `mp3:32.0` | 0.762 | [0.736, 0.787] | -0.014 | 1.35e-01 | 2.71e-01 | neutral 0.34 | 0.00 | tolerated |
| `mp3:16.0` | 0.573 | [0.548, 0.598] | -0.203 | 0.00e+00 | 0.00e+00 | neutral 0.67 | 0.06 | degraded |
| `mp3:8.0` | 0.409 | [0.386, 0.431] | -0.367 | 0.00e+00 | 0.00e+00 | neutral 0.84 | 1.00 | **COLLAPSE** |
| `white_noise:0.1` | 0.210 | [0.190, 0.230] | -0.566 | 0.00e+00 | 0.00e+00 | happy 0.54 | 1.00 | **COLLAPSE** |
| `white_noise:0.05` | 0.243 | [0.226, 0.261] | -0.533 | 0.00e+00 | 0.00e+00 | happy 0.64 | 1.00 | **COLLAPSE** |
| `white_noise:0.02` | 0.289 | [0.270, 0.309] | -0.487 | 0.00e+00 | 0.00e+00 | happy 0.80 | 1.00 | **COLLAPSE** |
| `white_noise:0.005` | 0.479 | [0.452, 0.504] | -0.297 | 0.00e+00 | 0.00e+00 | happy 0.65 | 0.00 | degraded |
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
| gaussian_snr | `gaussian_snr:5.0` | `gaussian_snr:2.0` | [5.0, 2.0] (width 3.0) | majority share 0.81 (>= 0.75) |
| lowpass | `lowpass:900.0` | `lowpass:850.0` | [900.0, 850.0] (width 50.0) | mean entropy 0.29 (<= 0.30) |
| highpass | `highpass:800.0` | — none in range — | — | no collapse observed |
| clipping | `clipping:30.0` | — none in range — | — | no collapse observed |
| mp3 | `mp3:16.0` | `mp3:8.0` | [16.0, 8.0] (width 8.0) | majority share 0.84 (>= 0.75) |
| white_noise | `white_noise:0.005` | `white_noise:0.02` | [0.005, 0.02] (width 0.015) | majority share 0.80 (>= 0.75) |

Intervals are bracketed between two adjacent sampled values — an **inference**, not an observation.
