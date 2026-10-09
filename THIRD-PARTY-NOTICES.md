# Third-party components, licences and data provenance

This repository contains **only original code and our own experimental output**. No third-party
model weights, no third-party audio, and no third-party source code are redistributed here.

---

## 1. Runtime substrate

| Component | Role | Licence | What we did |
|---|---|---|---|
| **Agnes Harness (AGH)** | the agent execution substrate required by the competition: session ledger, command-approval gate, skill loading | Apache-2.0 | Compiled and configured it. **No original AGH source file was modified.** All of our work lives outside its tree. |
| **Agnes model** (`agnes-3.0-flash`) | the model that plans the experiments, interprets results and writes the report | provided by the organisers | Called through AGH. Not fine-tuned, not modified. |

AGH is provided by the competition organisers. It is a dependency, not our contribution, and it is
not redistributed here.

## 2. Audit target

| Component | Licence | Note |
|---|---|---|
| `superb/wav2vec2-base-superb-er` | Apache-2.0 | **This is the object being audited, not a model our agent uses.** Weights are *not* redistributed; `download_model.py` fetches them from Hugging Face, and `audit.py --model <dir>` takes a path. |

The distinction matters: our agent runs on Agnes, and this model is what it measures. The audit
target is a pre-existing open model that we did not train.

## 3. Data

| Dataset | Licence | Note |
|---|---|---|
| **IEMOCAP** (Interactive Emotional Dyadic Motion Capture, USC SAIL) | requires a signed licence agreement | **Not redistributed.** Obtain it from USC/SAIL directly and place the released WAVs under `data/IEMOCAP/Session<N>/`. |

Only derived, aggregate measurements (accuracy, recall, entropy, confidence intervals) appear in
this repository. No audio, no transcripts, no speaker identifiers.

## 4. Python dependencies (installed, not vendored)

| Package | Version used | Licence |
|---|---|---|
| PyTorch | 2.6.0+cu124 | BSD-3-Clause |
| transformers | 5.19.0 | Apache-2.0 |
| audiomentations | 0.43.1 | MIT |
| soundfile | 0.14.0 | BSD-3-Clause |
| NumPy | 2.5.3 | BSD-3-Clause |
| SciPy | 1.18.1 | BSD-3-Clause |
| librosa | 0.11.0 | ISC |
| huggingface-hub | 1.33.0 | Apache-2.0 |

`audiomentations` supplies the nine perturbation transforms that `audit.py` composes. We use it
**unmodified**; the defects documented in `docs/BUGLOG.md` are in how *we* drive it (unseeded global
RNGs, un-pinned filter order), not in the library.

## 5. Tools used during development only

`ffmpeg` / `ffprobe` (gyan.dev essentials build) were used locally to cut the demo video. They are
excluded from this repository via `.gitignore` (`tools/bin/`).

## 6. Fonts used in rendered images and video

`Microsoft YaHei` and `Consolas`, taken from the local Windows installation at render time. No font
files are redistributed.

---

## Attribution for this work

Original work in this repository: `audit.py`, `.agh/skills/ser-trust-audit/SKILL.md`, everything in
`tools/` and `docs/`, and all experimental output under `evidence/` and `outputs/`.

If you build on it, cite this repository.
