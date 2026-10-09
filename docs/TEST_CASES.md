# Test cases — audit tool

_Generated 2026-10-09T14:39:15 by `tools/test_cases.py`._

**16/16 passed.** Sample size for the metric cases is `--per-class 8` (32 utterances) so the suite runs in a few minutes; the full-scale evidence is in `outputs/full/` (n=1241) and `trust_boundary_report_v2.md`.

## What the three classes are for

| Class | Purpose |
|---|---|
| normal | the tool runs and returns reproducible numbers |
| boundary | the correct answer is *uncertainty*; the tool must report the boundary instead of forcing a verdict |
| failure | a bad input must give a clear typed error and a non-zero exit code, **never a plausible-looking result** |

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 2 | bad input (arguments, unknown family, malformed condition) |
| 3 | model unusable |
| 4 | dataset unusable |
| 5 | unexpected defect in the tool |

## Results

### 正常 (3/3 pass)

| Case | Command | Expected | Actual | Result |
|---|---|---|---|---|
| list the perturbation catalogue | `.venv\Scripts\python.exe audit.py catalog` | rc=0 | rc=0 | PASS |
| clean baseline on a fixed sample | `.venv\Scripts\python.exe audit.py probe --session Session5 --per-class 8 --bootstrap 100` | rc=0 | rc=0 | PASS |
| a tolerated perturbation | `.venv\Scripts\python.exe audit.py sweep --conditions gaussian_snr:30 --per-class 8 --bootstrap 100` | rc=0 | rc=0 | PASS |

<details><summary>Why each case matters</summary>

- **list the perturbation catalogue** — 九族扰动全部列出；clipping 声明为 int 参数，这正是 v1 缺陷的防线
- **clean baseline on a fixed sample** — 模型指纹可复现；基线落在自身置信区间内
- **a tolerated perturbation** — 轻噪声下模型仍正常工作，判定为未塌缩

</details>

### 边界 (3/3 pass)

| Case | Command | Expected | Actual | Result |
|---|---|---|---|---|
| arithmetic no-op must show exactly zero effect | `.venv\Scripts\python.exe audit.py sweep --conditions lowpass:8000,clipping:1 --per-class 8 --bootstrap 100` | rc=0 | rc=0 | PASS |
| the tool must bracket a threshold, not report a point | `.venv\Scripts\python.exe audit.py curve --family gaussian_snr --from 10 --to 0 --points 5 --per-class 8 --bootstrap 100` | rc=0 | rc=0 | PASS |
| regression: the v1 clipping defect must stay fixed | `.venv\Scripts\python.exe audit.py sweep --conditions clipping:20 --per-class 8 --bootstrap 100` | rc=0 | rc=0 | PASS |

<details><summary>Why each case matters</summary>

- **arithmetic no-op must show exactly zero effect** — 8000 Hz 是 16 kHz 的 Nyquist 上限、1% 削波几乎不改变波形。两者必须给出 Δ 恰好 0 且 p=1.0 —— 这是对 no-op 检测能力的检验，也是 v1 那个缺陷（失败被伪装成 0 效应）的反面
- **the tool must bracket a threshold, not report a point** — curve 必须同时给出括号区间和「这是推断而非观测」的声明，而不是一个孤立的阈值数字
- **regression: the v1 clipping defect must stay fixed** — v1 里 clipping 因 float/int 类型错而全族失败，且失败被静默回退成干净音频，产出与基线逐位相同的假结果。此用例确保它不会再发生（BUGLOG BUG-1）

</details>

### 失败 (10/10 pass)

| Case | Command | Expected | Actual | Result |
|---|---|---|---|---|
| model directory does not exist | `.venv\Scripts\python.exe audit.py probe --model D:\no-such-model-directory --per-class 2` | rc=3, stderr contains “does not exist” | rc=3 | PASS |
| model path is a file, not a directory | `.venv\Scripts\python.exe audit.py probe --model D:\ser-audit\audit.py --per-class 2` | rc=3, stderr contains “must be a directory” | rc=3 | PASS |
| model directory is incomplete | `.venv\Scripts\python.exe audit.py probe --model D:\ser-audit\cache --per-class 2` | rc=3, stderr contains “incomplete” | rc=3 | PASS |
| unknown perturbation family | `.venv\Scripts\python.exe audit.py sweep --conditions gaussain_snr:10 --per-class 2` | rc=2, stderr contains “unknown perturbation family” | rc=2 | PASS |
| non-numeric value for a numeric family | `.venv\Scripts\python.exe audit.py sweep --conditions gaussian_snr:loud --per-class 2` | rc=2, stderr contains “is not a number” | rc=2 | PASS |
| condition missing the value | `.venv\Scripts\python.exe audit.py sweep --conditions gaussian_snr --per-class 2` | rc=2, stderr contains “malformed condition” | rc=2 | PASS |
| sweep without conditions | `.venv\Scripts\python.exe audit.py sweep --per-class 2` | rc=2, stderr contains “needs --conditions” | rc=2 | PASS |
| curve without a range | `.venv\Scripts\python.exe audit.py curve --family gaussian_snr --per-class 2` | rc=2, stderr contains “--from and --to” | rc=2 | PASS |
| session that does not exist in the dataset | `.venv\Scripts\python.exe audit.py probe --session Session99 --per-class 2` | rc=4, stderr contains “session not found” | rc=4 | PASS |
| audio at the wrong sample rate | `.venv\Scripts\python.exe audit.py probe --session _selftest_bad_samplerate --per-class 2` | rc=4, stderr contains “wrong sample rate” | rc=4 | PASS |

<details><summary>Why each case matters</summary>

- **model directory does not exist** — 必须以模型类错误退出，而不是甩出 transformers 的原始堆栈
- **model path is a file, not a directory** — 常见误用：把 --model 指向了权重文件本身
- **model directory is incomplete** — 缺 config.json 的目录必须被识别为不可用，而不是中途崩在加载阶段
- **unknown perturbation family** — 拼错时必须报错，并且最好给出最接近的合法族名
- **non-numeric value for a numeric family** — 值必须是数字，报错时要指出该族的单位和示例
- **condition missing the value** — 缺冒号属于用法错误，要给出正确格式
- **sweep without conditions** — 漏参数时给出可直接照抄的示例命令
- **curve without a range** — curve 缺范围无法定位任何东西，必须拒绝执行而不是默默用默认值
- **session that does not exist in the dataset** — 报错时要列出实际可用的 session，便于立刻改正
- **audio at the wrong sample rate** — 模型只在 16 kHz 上训练过。工具必须拒绝，而不是悄悄重采样 —— 悄悄重采样会改变被测量的信号，让审计结论失去意义

</details>

## Reproduce

```
.venv\Scripts\python.exe tools/test_cases.py
```

Each case runs `.venv\Scripts\python.exe audit.py <args>` from the repo root with the proxy environment variables removed (an inherited HTTP proxy makes the model endpoint unreachable on this machine).

## Representative outputs

**model directory does not exist** — `.venv\Scripts\python.exe audit.py probe --model D:\no-such-model-directory --per-class 2`

```
[audit] test set Session5: 8 utterances, distribution={'angry': 2, 'happy': 2, 'sad': 2, 'neutral': 2}
[audit] loading model D:\no-such-model-directory

[audit] ERROR: model directory does not exist: D:\no-such-model-directory
[audit]   Pass an existing directory with --model, or omit --model to use the default at D:\ser-audit\models\superb-er.
[audit] exit code 3 (model unusable)
```

**model path is a file, not a directory** — `.venv\Scripts\python.exe audit.py probe --model D:\ser-audit\audit.py --per-class 2`

```
[audit] test set Session5: 8 utterances, distribution={'angry': 2, 'happy': 2, 'sad': 2, 'neutral': 2}
[audit] loading model D:\ser-audit\audit.py

[audit] ERROR: --model must be a directory, got a file: D:\ser-audit\audit.py
[audit]   Point --model at the folder containing config.json and the weights.
[audit] exit code 3 (model unusable)
```

**model directory is incomplete** — `.venv\Scripts\python.exe audit.py probe --model D:\ser-audit\cache --per-class 2`

```
[audit] test set Session5: 8 utterances, distribution={'angry': 2, 'happy': 2, 'sad': 2, 'neutral': 2}
[audit] loading model D:\ser-audit\cache

[audit] ERROR: model directory is incomplete: D:\ser-audit\cache
[audit]   Missing: config.json, preprocessor_config.json, pytorch_model.bin or model.safetensors
[audit]   A HuggingFace audio-classification folder needs config.json, preprocessor_config.json and the weights.
[audit]   If the model has not been downloaded yet, fetch it first — `tools/download_model.py` in this project handles the mirrors.
[audit] exit code 3 (model unusable)
```

**unknown perturbation family** — `.venv\Scripts\python.exe audit.py sweep --conditions gaussain_snr:10 --per-class 2`

```
[audit] ERROR: unknown perturbation family 'gaussain_snr'
[audit]   Did you mean: gaussian_snr, gain
[audit]   Run `catalog` to see units and suggested values.
[audit] exit code 2 (bad input)
```

**non-numeric value for a numeric family** — `.venv\Scripts\python.exe audit.py sweep --conditions gaussian_snr:loud --per-class 2`

```
[audit] ERROR: 'loud' is not a number, so 'gaussian_snr:loud' cannot be a condition
[audit]   family 'gaussian_snr' takes a numeric value in dB, e.g. gaussian_snr:30
[audit] exit code 2 (bad input)
```

**condition missing the value** — `.venv\Scripts\python.exe audit.py sweep --conditions gaussian_snr --per-class 2`

```
[audit] ERROR: malformed condition 'gaussian_snr'
[audit]   Expected family:value, e.g. gaussian_snr:10 or lowpass:2000.
[audit] exit code 2 (bad input)
```

**sweep without conditions** — `.venv\Scripts\python.exe audit.py sweep --per-class 2`

```
[audit] ERROR: sweep needs --conditions
[audit]   Example: sweep --conditions gaussian_snr:10,lowpass:2000
[audit] exit code 2 (bad input)
```

**curve without a range** — `.venv\Scripts\python.exe audit.py curve --family gaussian_snr --per-class 2`

```
[audit] ERROR: curve needs --family, --from and --to
[audit]   Example: curve --family gaussian_snr --from 20 --to -5 --points 6
[audit] exit code 2 (bad input)
```

**session that does not exist in the dataset** — `.venv\Scripts\python.exe audit.py probe --session Session99 --per-class 2`

```
[audit] ERROR: dataset session not found: D:\ser-audit\data\IEMOCAP\Session99
[audit]   Available sessions: Session1, Session2, Session3, Session4, Session5
[audit]   See data/IEMOCAP/_dataset_health.md for the expected layout.
[audit] exit code 4 (dataset unusable)
```

**audio at the wrong sample rate** — `.venv\Scripts\python.exe audit.py probe --session _selftest_bad_samplerate --per-class 2`

```
[audit] test set _selftest_bad_samplerate: 1 utterances, distribution={'neutral': 1}
[audit] loading model D:\ser-audit\models\superb-er

Loading weights:   0%|          | 0/216 [00:00<?, ?it/s]
Loading weights: 100%|██████████| 216/216 [00:00<00:00, 20087.57it/s]
[audit] device=cuda gpu=NVIDIA GeForce GTX 1650

[audit] ERROR: wrong sample rate in Ses99F_impro01_X001.wav: expected 16000 Hz, got 8000 Hz
[audit]   This model is trained on 16 kHz audio. Resample the corpus first — the audit must not silently resample, because that would change the signal being measured.
[audit] exit code 4 (dataset unusable)
```
