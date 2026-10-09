"""SER trustworthiness-audit toolkit — structured CLI designed to be driven by an agent.

Every subcommand prints a single JSON object to stdout and progress text to stderr, so an
agent (running on Agnes Harness) can call it, parse the result, and decide what to do next.
That plan -> call -> observe -> adapt loop is the point of the tool, not a side effect.

Subcommands
    catalog                 families, metrics, and the recommended workflow
    probe                   load model + test set, report the clean baseline and environment
    sweep --conditions ...  apply a set of perturbations, report metrics, stats and collapse flags
    curve --family F ...    sample one family along its parameter range (find the cliff)
    battery                 confirm at full scale across many conditions; resumable, so it can be
                            called repeatedly under a shell timeout until status is "complete"

Examples
    python audit.py probe --session Session5 --per-class 24
    python audit.py sweep --conditions gaussian_snr:10,lowpass:2000,pitch:-4
    python audit.py curve --family gaussian_snr --from 20 --to -5 --points 6
    python audit.py battery --budget-seconds 480       # call until status == "complete"
    python audit.py battery --status                    # progress, without measuring

Design notes
    * Deterministic: the test-set draw, the bootstrap resamples and the *transform randomness*
      are all seeded, and each perturbation pins min == max, so the audio for a given condition
      is identical between runs — and identical no matter which call measured it. An audit that
      cannot be reproduced is not evidence. (See docs/BUGLOG.md BUG-3: pinning min == max is not
      by itself enough, because several transforms draw from the global RNGs.)
    * Collapse is not just low accuracy. A model that answers one class for everything scores
      at chance while looking "merely degraded"; we flag it explicitly.
    * Accuracy alone is not a result. Every condition carries a bootstrap CI, a paired test
      against the clean reference, and an effect size, so a difference can be called real or
      noise. With multiple conditions, p-values are Holm-corrected.
    * A failed transform is NEVER silently replaced by the clean clip. If a transform could
      not be applied, the condition is reported as invalid rather than as "no measured harm".
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import random
import re
import sys
import time
import zlib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn

import numpy as np

# torch / transformers / audiomentations / scipy / soundfile are imported lazily, inside the
# functions that need them. Importing them costs ~13 s, which is unacceptable for `catalog`
# (the first thing an agent calls to learn the tool) and for argument validation. Keeping the
# module import light means a typo fails in under a second and the catalogue is instant.

ROOT = Path(__file__).resolve().parent
IEMOCAP = ROOT / "data" / "IEMOCAP"
DEFAULT_MODEL = ROOT / "models" / "superb-er"
CACHE = ROOT / "cache"
CLASSES = ("angry", "happy", "sad", "neutral")
SEED = 20261008
SAMPLE_SEED = SEED          # current test-set draw; set from --sample-seed in main()
BOOTSTRAP_B = 2000
ALPHA = 0.05

IEMOCAP_TO_CLASS = {"ang": "angry", "exc": "happy", "hap": "happy", "sad": "sad", "neu": "neutral"}
LABEL_LINE = re.compile(r"^\[[\d.]+\s*-\s*[\d.]+\]\s+(\S+)\s+(\S+)\s+\[")

# Each family maps a human-meaningful parameter onto a deterministic audiomentations transform.
# CATALOG holds metadata only (what `catalog` reports), so it stays importable without pulling in
# audiomentations. The transforms themselves are built on demand by build_transform().
# "cast" fixes the parameter type required by the underlying transform (see the clipping bug
# in docs/BUGLOG.md: passing 20.0 where an int is required raises TypeError).
CATALOG: dict[str, dict] = {
    "gaussian_snr": {
        "unit": "dB",
        "desc": "Additive white Gaussian noise at a target signal-to-noise ratio",
        "sweep": [30, 20, 15, 10, 5, 2, 0, -5],
        "higher_is_cleaner": True,
    },
    "lowpass": {
        "unit": "Hz",
        "desc": "Low-pass filter, 18 dB/octave (order pinned), removes high-frequency content "
                "(bandwidth limitation)",
        "sweep": [8000, 4000, 2000, 1000, 500],
        "higher_is_cleaner": True,
    },
    "highpass": {
        "unit": "Hz",
        "desc": "High-pass filter, 18 dB/octave (order pinned), removes low-frequency content "
                "(telephone-like)",
        "sweep": [100, 200, 400, 800],
        "higher_is_cleaner": False,
    },
    "clipping": {
        "unit": "percent-clipped",
        "desc": "Clipping distortion: hard-limits the given percentage of the waveform "
                "(higher value = MORE distortion)",
        "sweep": [1, 5, 10, 20, 30],
        "cast": int,
        "higher_is_cleaner": False,
    },
    "mp3": {
        "unit": "kbps",
        "desc": "MP3 codec compression at a fixed bitrate (codec artefacts)",
        "sweep": [64, 32, 16, 8],
        "cast": int,
        "higher_is_cleaner": True,
    },
    "pitch": {
        "unit": "semitones",
        "desc": "Pitch shift without tempo change (speaker/prosody mismatch)",
        "sweep": [6, 4, 2, -2, -4, -6],
        "higher_is_cleaner": None,   # symmetric: both directions can hurt
    },
    "timestretch": {
        "unit": "rate",
        "desc": "Time stretch without pitch change (speaking-rate mismatch)",
        "sweep": [0.7, 0.85, 1.15, 1.3, 1.5],
        "higher_is_cleaner": None,
    },
    "gain": {
        "unit": "dB",
        "desc": "Global gain change (recording level mismatch)",
        "sweep": [20, 10, -10, -20, -30],
        "higher_is_cleaner": None,
    },
    "white_noise": {
        "unit": "amplitude",
        "desc": "Additive uniform noise at a fixed amplitude (no SNR control); "
                "higher amplitude = MORE noise",
        "sweep": [0.001, 0.005, 0.02, 0.05, 0.1],
        "higher_is_cleaner": False,
    },
}


def build_transform(family: str, value: float):
    """Construct the deterministic audiomentations pipeline for one (family, value) pair.

    Imported here rather than at module scope: audiomentations pulls in torch, which costs
    ~13 s and is not needed for `catalog` or for reporting a bad argument.
    """
    from audiomentations import (
        AddGaussianNoise, AddGaussianSNR, ClippingDistortion, Compose, Gain,
        HighPassFilter, LowPassFilter, Mp3Compression, PitchShift, TimeStretch,
    )

    if family == "gaussian_snr":
        return Compose([AddGaussianSNR(min_snr_db=value, max_snr_db=value, p=1.0)])
    if family == "lowpass":
        # Pin the roll-off too. audiomentations draws the filter order from the RNG on every
        # clip (randint(min_rolloff//6, max_rolloff//6)), so leaving the default [12, 24] means
        # "lowpass:900" measures a *mixture* of 2nd-, 3rd- and 4th-order filters rather than one
        # well-defined filter. 18 dB/octave is the midpoint of that default range, so pinning it
        # makes the condition a single reproducible measurement without shifting the operating
        # point. See docs/BUGLOG.md BUG-4.
        return Compose([LowPassFilter(min_cutoff_freq=value, max_cutoff_freq=value,
                                      min_rolloff=18, max_rolloff=18, p=1.0)])
    if family == "highpass":
        return Compose([HighPassFilter(min_cutoff_freq=value, max_cutoff_freq=value,
                                       min_rolloff=18, max_rolloff=18, p=1.0)])
    if family == "clipping":
        # min/max must be int here — passing a float raises at call time (docs/BUGLOG.md BUG-1)
        return Compose([ClippingDistortion(min_percentile_threshold=int(value),
                                           max_percentile_threshold=int(value), p=1.0)])
    if family == "mp3":
        return Compose([Mp3Compression(min_bitrate=int(value), max_bitrate=int(value), p=1.0)])
    if family == "pitch":
        return Compose([PitchShift(min_semitones=value, max_semitones=value, p=1.0)])
    if family == "timestretch":
        return Compose([TimeStretch(min_rate=value, max_rate=value, p=1.0)])
    if family == "gain":
        return Compose([Gain(min_gain_db=value, max_gain_db=value, p=1.0)])
    if family == "white_noise":
        return Compose([AddGaussianNoise(min_amplitude=value, max_amplitude=value, p=1.0)])
    fail(EXIT_USAGE, f"no transform is implemented for family '{family}'")


# The canonical confirmatory battery: one row per family, listing every parameter value worth
# measuring at full scale. `catalog` publishes this, so the agent can see what a full-scale
# confirmation covers before deciding whether to run it, extend it, or narrow it.
#
# The value lists are denser where the model was observed to change behaviour (0.5 dB inside
# 6-10 dB SNR, 50 Hz inside 700-1100 Hz low-pass) and coarser on the plateaus.
BATTERY: dict[str, list[float]] = {
    "gaussian_snr": [30, 15, 10, 9, 8.5, 8, 7.5, 7, 6, 5, 2, 0],
    "lowpass": [8000, 2000, 1100, 1000, 950, 900, 850, 800, 700],
    "highpass": [100, 200, 400, 800],
    "clipping": [1, 5, 10, 20, 30],
    "mp3": [64, 32, 16, 8],
    "white_noise": [0.005, 0.02, 0.05, 0.1],
    "gain": [20, -10, -20, -30],
    "pitch": [6, 4, 2, -2, -4, -6],
    "timestretch": [0.7, 0.85, 1.15, 1.3, 1.5],
}
BATTERY_DIR = ROOT / "outputs" / "battery"


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# Distinct exit codes so a caller (or the agent) can tell *what kind* of failure happened
# without parsing prose. A failed run must be loud and typed, never a plausible-looking number.
EXIT_OK = 0
EXIT_USAGE = 2            # bad arguments / unknown family
EXIT_MODEL = 3            # model directory unusable
EXIT_DATA = 4             # dataset missing, empty, or wrong format
EXIT_UNEXPECTED = 5       # anything else

DEBUG = False             # set from --debug; controls whether tracebacks are shown


def fail(code: int, problem: str, hint: str | None = None) -> "NoReturn":
    """Print a clean, actionable error to stderr and exit with a typed code."""
    log("")
    log(f"[audit] ERROR: {problem}")
    if hint:
        for line in hint.strip().splitlines():
            log(f"[audit]   {line.strip()}")
    log(f"[audit] exit code {code} "
        + {EXIT_USAGE: "(bad input)", EXIT_MODEL: "(model unusable)",
           EXIT_DATA: "(dataset unusable)"}.get(code, "(unexpected)"))
    raise SystemExit(code)


def normalize_label(text: str) -> str | None:
    low = text.strip().lower()
    if low in IEMOCAP_TO_CLASS:
        return IEMOCAP_TO_CLASS[low]
    if low in {"neutral", "happy", "angry", "sad", "excited"}:
        return "happy" if low == "excited" else low
    return None


def read_labels(session: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    base = IEMOCAP / session / "dialog" / "EmoEvaluation"
    for path in sorted(base.glob("Ses*.txt")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = LABEL_LINE.match(line)
            if m:
                cls = normalize_label(m.group(2))
                if cls:
                    labels[m.group(1)] = cls
    return labels


def wav_path(session: str, utt: str) -> Path:
    # Dialogue directory names vary in length, so split on the last underscore.
    return IEMOCAP / session / "sentences" / "wav" / utt.rsplit("_", 1)[0] / f"{utt}.wav"


def select_testset(session: str, per_class: int, seed: int) -> tuple[list[str], list[str]]:
    """Choose the evaluation set. Returns (utterance_ids, truths).

    per_class > 0 : balanced sample of that many per class (seed-controlled).
    per_class == 0: every 4-class utterance in the session.
    Only the *selection* is cached (a small JSON); audio is always read from disk so the
    cache cannot go stale against the dataset.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    session_dir = IEMOCAP / session
    if not session_dir.is_dir():
        available = sorted(p.name for p in IEMOCAP.glob("Session*") if p.is_dir())
        fail(EXIT_DATA, f"dataset session not found: {session_dir}",
             (f"Available sessions: {', '.join(available)}" if available
              else f"No Session* directories under {IEMOCAP} — has IEMOCAP been extracted?")
             + "\nSee data/IEMOCAP/_dataset_health.md for the expected layout.")

    key = f"{session}_pc{per_class}_seed{seed}"
    cache_file = CACHE / f"selection_{key}.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if data.get("utts") and data.get("truths"):
                return data["utts"], data["truths"]
            log(f"[audit] cached selection for {key} is empty — rebuilding")
        except (json.JSONDecodeError, UnicodeDecodeError, KeyError) as exc:
            log(f"[audit] cached selection for {key} is unreadable "
                f"({type(exc).__name__}) — rebuilding")

    labels = read_labels(session)
    if not labels:
        evaldir = session_dir / "dialog" / "EmoEvaluation"
        fail(EXIT_DATA, f"no emotion labels parsed for {session}",
             f"Looked in {evaldir} for Ses*.txt files.\n"
             f"Found {len(list(evaldir.glob('Ses*.txt')))} file(s) there.\n"
             "Expected label lines of the form '[start - end] utterance_id emo [V, A, D]'.")

    rng = np.random.default_rng(seed)
    by_class: dict[str, list[str]] = defaultdict(list)
    for utt, cls in sorted(labels.items()):
        if wav_path(session, utt).exists():
            by_class[cls].append(utt)

    if not by_class:
        fail(EXIT_DATA, f"no audio found for the labelled utterances in {session}",
             f"Looked for wav files under {session_dir / 'sentences' / 'wav'}.\n"
             f"{len(labels)} labelled utterances were parsed but none had a matching file.")

    short = {c: len(v) for c, v in by_class.items() if per_class and len(v) < per_class}
    if short:
        log(f"[audit] requested {per_class} per class but only have {short} — using all available")
        if any(len(v) == 0 for v in by_class.values()):
            log(f"[audit] note: no audio for class(es) "
                f"{[c for c in CLASSES if not by_class.get(c)]} in {session} — "
                f"the evaluation set will not be balanced")

    utts: list[str] = []
    truths: list[str] = []
    for cls in CLASSES:
        items = by_class[cls]
        if not items:
            continue
        if per_class == 0:
            idx = np.arange(len(items))
        else:
            idx = rng.choice(len(items), size=min(per_class, len(items)), replace=False)
        for i in idx:
            utts.append(items[int(i)])
            truths.append(cls)

    if not utts:
        fail(EXIT_DATA, f"evaluation set for {session} ended up empty",
             "No 4-class utterances with audio were selected. Check the label normalisation "
             "against the dataset's emotion tags.")

    cache_file.write_text(json.dumps({"utts": utts, "truths": truths}), encoding="utf-8")
    return utts, truths


def load_waves(session: str, utts: list[str]) -> list[np.ndarray]:
    import soundfile as sf

    waves: list[np.ndarray] = []
    for utt in utts:
        path = wav_path(session, utt)
        if not path.exists():
            fail(EXIT_DATA, f"audio file missing: {path}",
                 f"Utterance '{utt}' was selected but its wav file is not on disk. "
                 "Delete the cache/*.json selection for this session to reselect.")
        try:
            wave, sr = sf.read(str(path), dtype="float32", always_2d=False)
        except Exception as exc:
            fail(EXIT_DATA, f"could not read audio: {path.name}",
                 f"{type(exc).__name__}: {exc}")
        if wave.ndim > 1:
            wave = wave.mean(axis=1)
        if sr != 16000:
            fail(EXIT_DATA,
                 f"wrong sample rate in {path.name}: expected 16000 Hz, got {sr} Hz",
                 "This model is trained on 16 kHz audio. Resample the corpus first — the audit "
                 "must not silently resample, because that would change the signal being measured.")
        if wave.size == 0:
            fail(EXIT_DATA, f"audio file is empty: {path.name}")
        waves.append(wave.astype(np.float32))
    return waves


class SerModel:
    def __init__(self, model_dir: Path) -> None:
        # Cheap filesystem checks first: importing torch costs ~13 s, and there is no reason to
        # pay that before discovering the path is wrong.
        if not model_dir.exists():
            fail(EXIT_MODEL, f"model directory does not exist: {model_dir}",
                 f"Pass an existing directory with --model, or omit --model to use the "
                 f"default at {DEFAULT_MODEL}.")
        if not model_dir.is_dir():
            fail(EXIT_MODEL, f"--model must be a directory, got a file: {model_dir}",
                 "Point --model at the folder containing config.json and the weights.")
        missing = [n for n in ("config.json", "preprocessor_config.json")
                   if not (model_dir / n).exists()]
        weights = next((n for n in ("pytorch_model.bin", "model.safetensors")
                        if (model_dir / n).exists()), None)
        if missing or weights is None:
            absent = missing + ([] if weights else ["pytorch_model.bin or model.safetensors"])
            fail(EXIT_MODEL,
                 f"model directory is incomplete: {model_dir}",
                 "Missing: " + ", ".join(absent) + "\n"
                 "A HuggingFace audio-classification folder needs config.json, "
                 "preprocessor_config.json and the weights.\n"
                 "If the model has not been downloaded yet, fetch it first — "
                 "`tools/download_model.py` in this project handles the mirrors.")

        import torch
        from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

        self._torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.gpu = torch.cuda.get_device_name(0) if self.device == "cuda" else None
        try:
            self.extractor = AutoFeatureExtractor.from_pretrained(str(model_dir))
        except Exception as exc:
            fail(EXIT_MODEL, f"could not load the feature extractor from {model_dir}",
                 f"{type(exc).__name__}: {exc}\n"
                 "preprocessor_config.json is probably malformed or from a different model type.")
        try:
            self.model = AutoModelForAudioClassification.from_pretrained(
                str(model_dir)).to(self.device).eval()
        except Exception as exc:
            fail(EXIT_MODEL, f"could not load the audio-classification model from {model_dir}",
                 f"{type(exc).__name__}: {exc}\n"
                 "config.json must declare an audio-classification architecture, and the "
                 "weights must match it.")

        self.id_to_class = {i: normalize_label(s) for i, s in self.model.config.id2label.items()}
        if not any(self.id_to_class.values()):
            fail(EXIT_MODEL,
                 "model label space does not overlap this audit's four classes",
                 f"model id2label: {self.model.config.id2label}\n"
                 f"this tool audits: {', '.join(CLASSES)}\n"
                 "An audit of a model with unrelated output labels would be meaningless.")
        self.fingerprint = hashlib.sha256((model_dir / weights).read_bytes()).hexdigest()[:16]

    def predict(self, wave: np.ndarray) -> tuple[str | None, np.ndarray, float]:
        inputs = self.extractor(wave, sampling_rate=16000, return_tensors="pt", padding=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with self._torch.no_grad():
            logits = self.model(**inputs).logits
        probs = self._torch.softmax(logits, dim=-1)[0].cpu().numpy()
        for index in np.argsort(probs)[::-1]:
            cls = self.id_to_class.get(int(index))
            if cls:
                return cls, probs, float(probs[index])
        return None, probs, 0.0


def predict_all(model: SerModel, waves: list[np.ndarray]) -> tuple[list[str | None], list[np.ndarray]]:
    preds: list[str | None] = []
    probs: list[np.ndarray] = []
    for wave in waves:
        cls, prob, _ = model.predict(wave)
        preds.append(cls)
        probs.append(prob)
    return preds, probs


def _entropies(prob_rows: list[np.ndarray]) -> np.ndarray:
    eps = 1e-12
    return np.array([float(-(p * np.log(p + eps)).sum() / np.log(len(p))) for p in prob_rows])


def _point_metrics(correct: np.ndarray, entropy: np.ndarray, codes: np.ndarray,
                   truths: list[str], preds: list[str | None]) -> dict:
    n = len(preds)
    counts = Counter(preds)
    majority_class, majority_count = counts.most_common(1)[0]
    recall = {}
    for cls in CLASSES:
        idx = [i for i, t in enumerate(truths) if t == cls]
        if idx:
            recall[cls] = float(np.mean([preds[i] == cls for i in idx]))
    # macro F1 over the 4 classes
    f1s = []
    for cls in CLASSES:
        tp = sum(1 for p, t in zip(preds, truths) if p == cls and t == cls)
        fp = sum(1 for p, t in zip(preds, truths) if p == cls and t != cls)
        fn = sum(1 for p, t in zip(preds, truths) if p != cls and t == cls)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return {
        "n": n,
        "accuracy": round(float(correct.mean()), 4),
        "balanced_accuracy": round(float(np.mean(list(recall.values()))), 4) if recall else None,
        "macro_f1": round(float(np.mean(f1s)), 4),
        "chance_level": round(1 / len(CLASSES), 4),
        "distinct_predictions": len(counts),
        "majority_class": majority_class,
        "majority_share": round(majority_count / n, 4),
        "mean_normalised_entropy": round(float(entropy.mean()), 4),
        "per_class_recall": {k: round(v, 4) for k, v in recall.items()},
    }


def bootstrap_stats(correct: np.ndarray, entropy: np.ndarray, codes: np.ndarray,
                    truths: list[str], preds: list[str | None], b: int, seed: int) -> dict:
    """Resample utterances with replacement, recompute the metric set and the collapse verdict.

    This is what turns a point estimate into a claim: every headline number gets a 95% CI, and
    the binary 'degenerate' flag becomes a probability, because a threshold on a noisy estimate
    should not be reported as a certainty.
    """
    n = len(preds)
    rng = np.random.default_rng(seed)
    accs, bals, majs, ents, degens = [], [], [], [], []
    recall_codes = np.array([CLASSES.index(t) for t in truths])
    for _ in range(b):
        idx = rng.integers(0, n, n)
        accs.append(correct[idx].mean())
        majs.append(np.bincount(codes[idx] + 1, minlength=len(CLASSES) + 2).max() / n)
        ents.append(entropy[idx].mean())
        recs = [correct[idx][recall_codes[idx] == c].mean()
                for c in range(len(CLASSES))
                if (recall_codes[idx] == c).any()]
        bals.append(float(np.mean(recs)))
        degens.append(bool(majs[-1] >= 0.75 or ents[-1] <= 0.30))
    return {
        "bootstrap_b": b,
        "accuracy_ci95": [round(float(np.percentile(accs, 2.5)), 4),
                          round(float(np.percentile(accs, 97.5)), 4)],
        "balanced_accuracy_ci95": [round(float(np.percentile(bals, 2.5)), 4),
                                   round(float(np.percentile(bals, 97.5)), 4)],
        "majority_share_ci95": [round(float(np.percentile(majs, 2.5)), 4),
                                round(float(np.percentile(majs, 97.5)), 4)],
        "entropy_ci95": [round(float(np.percentile(ents, 2.5)), 4),
                         round(float(np.percentile(ents, 97.5)), 4)],
        "degenerate_probability": round(float(np.mean(degens)), 4),
    }


def paired_vs_clean(correct: np.ndarray, clean_correct: np.ndarray,
                    clean_bal: float, cond_bal: float, b: int, seed: int) -> dict:
    """McNemar exact test + bootstrap CI on the paired balanced-accuracy difference.

    Both arms see the same utterances, so the comparison is paired: the informative quantity is
    how often the decision changed and in which direction, not two independent error bars.
    """
    from scipy import stats

    b_cc = int(np.sum(clean_correct & ~correct))   # clean right, condition wrong
    c_cw = int(np.sum(~clean_correct & correct))   # clean wrong, condition right
    discordant = b_cc + c_cw
    if discordant == 0:
        p_value = 1.0
    else:
        p_value = float(stats.binomtest(b_cc, discordant, 0.5).pvalue)

    rng = np.random.default_rng(seed)
    n = len(correct)
    deltas = []
    for _ in range(b):
        idx = rng.integers(0, n, n)
        deltas.append(correct[idx].mean() - clean_correct[idx].mean())
    delta = float(cond_bal - clean_bal)
    # Cohen's h on accuracy-like proportions, clipped to the valid domain
    p1 = min(max(cond_bal, 0.0), 1.0)
    p2 = min(max(clean_bal, 0.0), 1.0)
    cohens_h = float(2 * np.arcsin(np.sqrt(p1)) - 2 * np.arcsin(np.sqrt(p2)))
    return {
        "delta_balanced_accuracy": round(delta, 4),
        "delta_balanced_accuracy_ci95": [round(float(np.percentile(deltas, 2.5)), 4),
                                         round(float(np.percentile(deltas, 97.5)), 4)],
        "delta_accuracy": round(float(correct.mean() - clean_correct.mean()), 4),
        "mcnemar_b_clean_right_cond_wrong": b_cc,
        "mcnemar_c_clean_wrong_cond_right": c_cw,
        "mcnemar_exact_p": round(p_value, 6),
        "cohens_h_vs_clean": round(cohens_h, 4),
    }


def holm_correct(p_values: list[float], labels: list[str], alpha: float = ALPHA) -> dict:
    """Holm-Bonferroni step-down across the conditions of one sweep.

    Running 20 perturbations and reporting the smallest p-value as 'significant' is the classic
    multiple-comparison error. With m conditions, this controls the family-wise error rate.
    """
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running_max = 0.0
    rejected_until = -1
    for rank, i in enumerate(order):
        adj = min(1.0, p_values[i] * (m - rank))
        running_max = max(running_max, adj)
        adjusted[i] = running_max
        if p_values[i] <= alpha / (m - rank):
            rejected_until = rank
    significant = {labels[i] for rank, i in enumerate(order) if rank <= rejected_until}
    return {
        "method": "holm-bonferroni",
        "alpha": alpha,
        "m_conditions": m,
        "adjusted_p": {labels[i]: round(adjusted[i], 6) for i in range(m)},
        "significant_after_correction": sorted(significant),
    }


def parse_conditions(spec: str) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            fail(EXIT_USAGE, f"malformed condition '{chunk}'",
                 "Expected family:value, e.g. gaussian_snr:10 or lowpass:2000.")
        family, raw = chunk.split(":", 1)
        if family not in CATALOG:
            near = difflib.get_close_matches(family, list(CATALOG), n=3, cutoff=0.5)
            fail(EXIT_USAGE, f"unknown perturbation family '{family}'",
                 (f"Did you mean: {', '.join(near)}" if near
                  else f"Known families: {', '.join(CATALOG)}")
                 + "\nRun `catalog` to see units and suggested values.")
        # Apply the transform's required parameter type (clipping needs int, not float).
        cast = CATALOG[family].get("cast", float)
        try:
            out.append((family, cast(float(raw))))
        except ValueError:
            fail(EXIT_USAGE,
                 f"'{raw}' is not a number, so '{chunk}' cannot be a condition",
                 f"family '{family}' takes a numeric value in {CATALOG[family]['unit']}, "
                 f"e.g. {family}:{CATALOG[family]['sweep'][0]}")
    if not out:
        fail(EXIT_USAGE, "no conditions parsed from --conditions",
             "Provide at least one, e.g. --conditions gaussian_snr:10,lowpass:2000")
    return out


def run_conditions(model: SerModel, waves, truths, conditions, clean_correct,
                   clean_bal: float, bootstrap_b: int) -> list[dict]:
    n = len(waves)
    results: list[dict] = []
    for family, value in conditions:
        # Several audiomentations transforms draw from the *global* RNGs (AddGaussianSNR does
        # `random.uniform` for the SNR and `np.random.normal` for the noise). Pinning min == max
        # pins the parameter but NOT the realisation, so without this the audio differs on every
        # run and the audit is not reproducible. Seed per condition, derived from the condition
        # name, so a condition's audio is identical no matter which call measured it.
        condition_seed = SEED + zlib.crc32(f"{family}:{value}".encode()) % 100000
        random.seed(condition_seed)
        np.random.seed(condition_seed)

        transform = build_transform(family, value)
        preds: list[str | None] = []
        probs: list[np.ndarray] = []
        failures = 0
        error_types: Counter = Counter()
        changed = 0
        t0 = time.time()
        for wave in waves:
            try:
                sample = np.asarray(transform(samples=wave.copy(), sample_rate=16000), dtype=np.float32)
                if sample.shape != wave.shape or not np.array_equal(sample, wave):
                    changed += 1
            except Exception as exc:                      # a transform may be unusable for a clip
                failures += 1
                error_types[type(exc).__name__] += 1
                preds.append(None)
                probs.append(np.zeros(len(CLASSES), dtype=np.float32))
                continue                                  # do NOT fall back to the clean clip
            cls, prob, _ = model.predict(sample)
            preds.append(cls)
            probs.append(prob)
        wall = round(time.time() - t0, 1)

        valid = failures == 0
        diag: dict = {
            "condition": f"{family}:{value}",
            "family": family,
            "value": value,
            "unit": CATALOG[family]["unit"],
            "wall_seconds": wall,
            "valid": bool(valid),
            "transform_failures": failures,
            "transform_failure_types": dict(error_types),
            "clips_actually_modified": changed,
        }
        if not valid:
            # A condition whose transform never applied is not a measurement of that condition.
            diag.update({
                "invalid_reason": (
                    f"transform failed on {failures}/{n} clips "
                    f"({', '.join(error_types)}) — no usable audio, condition is UNMEASURED"
                ),
                "degenerate": None,
            })
            results.append(diag)
            log(f"    {diag['condition']:24s} INVALID — {failures}/{n} transform failures "
                f"({', '.join(error_types)})")
            continue

        correct = np.array([p == t for p, t in zip(preds, truths)], dtype=bool)
        entropy = _entropies(probs)
        codes = np.array([CLASSES.index(p) if p in CLASSES else -1 for p in preds])
        point = _point_metrics(correct, entropy, codes, truths, preds)

        seed_here = SEED + zlib.crc32(f"{family}:{value}".encode()) % 100000
        stats_a = bootstrap_stats(correct, entropy, codes, truths, preds, bootstrap_b, seed_here)
        stats_p = paired_vs_clean(correct, clean_correct, clean_bal,
                                 float(np.mean(list(point["per_class_recall"].values()))),
                                 bootstrap_b, seed_here + 1)

        degenerate = point["majority_share"] >= 0.75 or point["mean_normalised_entropy"] <= 0.30
        point["degenerate"] = bool(degenerate)
        point["collapse_reason"] = (
            None if not degenerate
            else f"majority share {point['majority_share']:.2f} (>= 0.75)"
            if point["majority_share"] >= 0.75
            else f"mean entropy {point['mean_normalised_entropy']:.2f} (<= 0.30)"
        )
        diag.update(point)
        diag.update(stats_a)
        diag.update(stats_p)
        results.append(diag)

        flag = "  <<< DEGENERATE" if degenerate else ""
        log(f"    {diag['condition']:24s} bacc={point['balanced_accuracy']:.3f} "
            f"[{stats_a['balanced_accuracy_ci95'][0]:.3f},{stats_a['balanced_accuracy_ci95'][1]:.3f}] "
            f"d={stats_p['delta_balanced_accuracy']:+.3f} "
            f"p={stats_p['mcnemar_exact_p']:.4f} "
            f"maj={point['majority_share']:.2f} "
            f"P(deg)={stats_a['degenerate_probability']:.2f}{flag}")
    return results


def emit(payload: dict, out: Path | None) -> None:
    payload["run_manifest"] = {
        "tool": "ser-audit",
        "tool_version": "2.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "sample_seed": SAMPLE_SEED,
        "bootstrap_b": payload.get("bootstrap_b"),
        "alpha": ALPHA,
        "host": {"device": payload.get("device"), "gpu": payload.get("gpu")},
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        log(f"    wrote {out}")
    print(text)


# ---------------------------------------------------------------------------------------
# battery: the confirmatory stage, made resumable so it fits inside a shell timeout
# ---------------------------------------------------------------------------------------
# A full-scale confirmation is ~53 conditions x 1241 utterances ~= 85 minutes of GPU work. A
# harness shell call is typically capped well below that (600 s in the AGH profile used here),
# so the work has to be chunked. `battery` keeps its own state file, does as much as the
# time budget allows, then exits reporting what is left. The agent calls it again until
# status becomes "complete". Chunking cannot change the numbers: every per-condition statistic
# is derived from a fixed seed and the same pinned audio, so the result is identical whether
# a condition is measured in call 1 or call 9.

def _battery_paths(session: str, per_class: int, sample_seed: int) -> dict[str, Path]:
    key = f"{session}_pc{per_class}_seed{sample_seed}"
    return {
        "state": BATTERY_DIR / f"state_{key}.json",
        "clean": BATTERY_DIR / f"clean_{key}.npz",
        "summary": BATTERY_DIR / f"summary_{key}.json",
        "markdown": BATTERY_DIR / f"report_{key}.md",
    }


def _resolve_plan(families_arg: str | None, plan_arg: str | None) -> dict[str, list]:
    """Build the plan: a dict of family -> list of values, or fail loudly."""
    if plan_arg:
        raw = plan_arg
        candidate = Path(plan_arg)
        if candidate.exists():
            raw = candidate.read_text(encoding="utf-8")
        try:
            plan = json.loads(raw)
        except json.JSONDecodeError as exc:
            fail(EXIT_USAGE, f"--plan is not valid JSON: {exc}",
                 'Expected {"gaussian_snr": [10, 0], "lowpass": [2000]}, or a path to that file.')
        if not isinstance(plan, dict) or not plan:
            fail(EXIT_USAGE, "--plan must be a non-empty object",
                 'Expected {"family": [value, value, ...]}')
        unknown = [f for f in plan if f not in CATALOG]
        if unknown:
            near = difflib.get_close_matches(unknown[0], list(CATALOG), n=3, cutoff=0.5)
            fail(EXIT_USAGE, f"--plan names unknown families: {', '.join(unknown)}",
                 (f"Did you mean: {', '.join(near)}" if near
                  else f"Known families: {', '.join(CATALOG)}"))
        resolved = {}
        cast_map = {f: CATALOG[f].get("cast", float) for f in plan}
        for fam, values in plan.items():
            if not isinstance(values, list) or not values:
                fail(EXIT_USAGE, f"--plan entry '{fam}' must be a non-empty list of values")
            resolved[fam] = [cast_map[fam](float(v)) for v in values]
        return resolved

    if families_arg and families_arg != "all":
        wanted = [f.strip() for f in families_arg.split(",") if f.strip()]
        unknown = [f for f in wanted if f not in BATTERY]
        if unknown:
            near = difflib.get_close_matches(unknown[0], list(BATTERY), n=3, cutoff=0.5)
            fail(EXIT_USAGE, f"unknown family in --families: {', '.join(unknown)}",
                 (f"Did you mean: {', '.join(near)}" if near
                  else f"Battery families: {', '.join(BATTERY)}"))
        return {f: list(BATTERY[f]) for f in wanted}
    return {f: list(BATTERY[f]) for f in BATTERY}


def _battery_units(plan: dict[str, list]) -> list[tuple[str, float]]:
    return [(fam, float(v)) for fam, values in plan.items() for v in values]


def _load_clean_arm(paths: dict[str, Path], model: "SerModel", waves, truths, session: str,
                    per_class: int, sample_seed: int):
    """Return (clean_correct, clean_bal, clean_reference). Cached: the clean arm is the same
    measurement for every condition, so recomputing it per call would waste ~85 s each time."""
    if paths["clean"].exists():
        data = np.load(paths["clean"], allow_pickle=True)
        preds = list(data["preds"])
        probs = list(data["probs"])
        log("[battery] reusing the cached clean arm")
    else:
        log("[battery] measuring the clean arm (once per battery, then cached)")
        preds, probs = predict_all(model, waves)
        paths["clean"].parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(paths["clean"],
                            preds=np.array(preds, dtype=object),
                            probs=np.array(probs, dtype=np.float32))

    correct = np.array([p == t for p, t in zip(preds, truths)], dtype=bool)
    codes = np.array([CLASSES.index(p) if p in CLASSES else -1 for p in preds])
    entropy = _entropies(probs)
    point = _point_metrics(correct, entropy, codes, truths, preds)
    bal = float(np.mean(list(point["per_class_recall"].values())))
    reference = dict(point)
    reference["degenerate"] = bool(point["majority_share"] >= 0.75
                                   or point["mean_normalised_entropy"] <= 0.30)
    reference.update(bootstrap_stats(correct, entropy, codes, truths, preds, BOOTSTRAP_B, SEED))
    reference["sample_seed"] = sample_seed
    reference["session"] = session
    reference["per_class"] = per_class
    return correct, bal, reference


def _aggregate_battery(state: dict, paths: dict[str, Path]) -> dict:
    """Holm within each family, then locate each family's collapse threshold."""
    results = list(state["done"].values())
    by_family: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_family[r["family"]].append(r)

    multiple = {}
    for fam, rows in by_family.items():
        measured = [r for r in rows if r.get("valid")]
        if len(measured) > 1:
            multiple[fam] = holm_correct([r["mcnemar_exact_p"] for r in measured],
                                         [r["condition"] for r in measured])

    thresholds = {}
    for fam, rows in by_family.items():
        if fam in ("pitch", "timestretch", "gain"):
            continue                       # no single severity axis, so no threshold to locate
        measured = [r for r in rows if r.get("valid") and r.get("degenerate") is not None]
        if len(measured) < 2:
            continue
        order = (lambda v: -v) if fam in ("gaussian_snr", "lowpass", "mp3") else (lambda v: v)
        ordered = sorted(measured, key=lambda r: order(r["value"]))
        idx = next((i for i, r in enumerate(ordered) if r["degenerate"]), None)
        if idx is None:
            thresholds[fam] = {"family": fam, "threshold_found": False,
                               "worst_sampled": ordered[-1]["condition"]}
            continue
        bad = ordered[idx]
        prev = ordered[idx - 1] if idx > 0 else None
        thresholds[fam] = {
            "family": fam,
            "threshold_found": True,
            "first_degenerate_condition": bad["condition"],
            "first_degenerate_value": bad["value"],
            "first_degenerate_probability": bad["degenerate_probability"],
            "last_healthy_condition": prev["condition"] if prev else None,
            "last_healthy_value": prev["value"] if prev else None,
            "bracketing_interval": [prev["value"], bad["value"]] if prev
                                   else [bad["value"], bad["value"]],
            "interval_width": abs(bad["value"] - prev["value"]) if prev else 0.0,
            "collapse_signature": bad.get("collapse_reason"),
            "degenerate_majority_class": bad.get("majority_class"),
            "basis": "bracketed between two adjacent sampled values — an inference, not an "
                     "observation",
        }

    degenerate = [r for r in results if r.get("degenerate")]
    summary = {
        "command": "battery",
        "status": "complete",
        "session": state["session"],
        "per_class": state["per_class"],
        "n_utterances": state["n_utterances"],
        "bootstrap_b": state["bootstrap"],
        "sample_seed": state["sample_seed"],
        "model_fingerprint": state.get("model_fingerprint"),
        "gpu": state.get("gpu"),
        "n_conditions": len(results),
        "n_valid": sum(1 for r in results if r.get("valid")),
        "n_degenerate": len(degenerate),
        "clean_reference": state["clean_reference"],
        "thresholds": thresholds,
        "multiple_comparison_within_family": multiple,
        "results": results,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    out_dir = paths["summary"].parent
    out_dir.mkdir(parents=True, exist_ok=True)
    paths["summary"].write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                encoding="utf-8")

    L = [f"# Confirmatory battery — {state['session']}, n = {state['n_utterances']}", "",
         "Measured by `audit.py battery`. Balanced accuracy with a 95% bootstrap CI; delta and "
         "exact McNemar p are paired against the clean arm on the same utterances.", "",
         "| Condition | Bal. acc | 95% CI | Δ vs clean | McNemar p | Holm (family) | Majority "
         "| P(deg) | Verdict |", "|---|---|---|---|---|---|---|---|---|"]
    for fam, rows in by_family.items():
        adj = (multiple.get(fam) or {}).get("adjusted_p", {})
        for r in sorted(rows, key=lambda c: -float(c["value"])):
            if not r.get("valid"):
                L.append(f"| `{r['condition']}` | — | — | — | — | — | — | — | **UNMEASURED** |")
                continue
            ci = r["balanced_accuracy_ci95"]
            verdict = ("**COLLAPSE**" if r["degenerate"]
                       else "degraded" if r["delta_balanced_accuracy"] < -0.05 else "tolerated")
            L.append(f"| `{r['condition']}` | {r['balanced_accuracy']:.3f} | "
                     f"[{ci[0]:.3f}, {ci[1]:.3f}] | {r['delta_balanced_accuracy']:+.3f} | "
                     f"{r['mcnemar_exact_p']:.2e} | {adj.get(r['condition'], float('nan')):.2e} | "
                     f"{r['majority_class']} {r['majority_share']:.2f} | "
                     f"{r['degenerate_probability']:.2f} | {verdict} |")
    L += ["", "## Located thresholds", "",
          "| Family | Last healthy | First collapsed | Bracketed interval | Signature |",
          "|---|---|---|---|---|"]
    for fam, th in thresholds.items():
        if not th.get("threshold_found"):
            L.append(f"| {fam} | `{th['worst_sampled']}` | — none in range — | — | "
                     f"no collapse observed |")
            continue
        lo, hi = th["bracketing_interval"]
        L.append(f"| {fam} | `{th['last_healthy_condition']}` | "
                 f"`{th['first_degenerate_condition']}` | [{lo}, {hi}] "
                 f"(width {th['interval_width']}) | {th['collapse_signature']} |")
    L += ["", "Intervals are bracketed between two adjacent sampled values — an **inference**, "
          "not an observation.", ""]
    paths["markdown"].write_text("\n".join(L), encoding="utf-8")
    return summary


def run_battery(args) -> int:
    # The harness timeout applies to the whole process, not just to the measuring loop, so the
    # budget has to be counted from here — model load, audio read and the clean arm all count.
    t_call = time.time()
    paths = _battery_paths(args.session, args.per_class, args.sample_seed)
    BATTERY_DIR.mkdir(parents=True, exist_ok=True)

    if args.reset:
        for p in paths.values():
            if p.exists():
                p.unlink()
        log("[battery] state cleared — the next run will measure everything from scratch")

    if args.status:
        if not paths["state"].exists():
            emit({"command": "battery", "status": "not_started",
                  "hint": "run battery without --status to begin"}, args.out)
            return 0
        state = json.loads(paths["state"].read_text(encoding="utf-8"))
        done = len(state["done"])
        total = len(state["plan_units"])
        emit({"command": "battery",
              "status": "complete" if done >= total else "in_progress",
              "completed": done, "total": total,
              "remaining": [f"{f}:{v}" for f, v in
                            [tuple(u) for u in state["plan_units"]] if f"{f}:{v}" not in state["done"]][:50],
              "started_at": state.get("started_at"),
              "calls_so_far": state.get("calls", 0),
              "summary_file": str(paths["summary"]) if done >= total else None}, args.out)
        return 0

    plan = _resolve_plan(args.families, args.plan)
    units = _battery_units(plan)
    plan_units = [[f, v] for f, v in units]

    if paths["state"].exists():
        state = json.loads(paths["state"].read_text(encoding="utf-8"))
        if state.get("plan_units") != plan_units:
            fail(EXIT_USAGE, "the existing battery state was built from a different plan",
                 f"State file: {paths['state']}\n"
                 "Re-run with --reset to start over, or use the same --plan/--families as before.")
    else:
        state = {"session": args.session, "per_class": args.per_class,
                 "bootstrap": args.bootstrap, "sample_seed": args.sample_seed,
                 "plan": plan, "plan_units": plan_units, "done": {},
                 "started_at": datetime.now(timezone.utc).isoformat(), "calls": 0,
                 "n_utterances": None, "clean_reference": None}

    state["calls"] = state.get("calls", 0) + 1
    remaining = [u for u in units if f"{u[0]}:{u[1]}" not in state["done"]]

    if not remaining:
        log("[battery] all conditions already measured — aggregating")
        summary = _aggregate_battery(state, paths)
        payload = dict(summary)
        payload.pop("results", None)
        payload["remaining"] = []
        payload["summary_file"] = str(paths["summary"])
        payload["report_file"] = str(paths["markdown"])
        emit(payload, args.out)
        return 0

    utts, truths = select_testset(args.session, args.per_class, args.sample_seed)
    state["n_utterances"] = len(utts)
    log(f"[battery] {len(state['done'])}/{len(units)} done, {len(remaining)} to go, "
        f"budget {args.budget_seconds}s")

    log(f"[battery] loading model {args.model}")
    model = SerModel(args.model)
    state["model_fingerprint"] = model.fingerprint
    state["gpu"] = model.gpu
    waves = load_waves(args.session, utts)
    clean_correct, clean_bal, clean_reference = _load_clean_arm(
        paths, model, waves, truths, args.session, args.per_class, args.sample_seed)
    state["clean_reference"] = clean_reference

    t0 = time.time()
    measured_now = 0
    conditions_seconds = 0.0
    for family, value in remaining:
        elapsed = time.time() - t_call
        per_condition = conditions_seconds / measured_now if measured_now else 0.0
        # Always allow at least one condition through, so even a tiny budget makes progress.
        # After the first one, use the observed cost from this call rather than a guess, because
        # a condition takes ~87 s at n=1241 but only a couple of seconds on a small sample.
        if measured_now > 0 and elapsed + per_condition > args.budget_seconds:
            log(f"[battery] budget reached after {measured_now} condition(s) "
                f"({elapsed:.0f}s of {args.budget_seconds:.0f}s budget)")
            break
        cond_t0 = time.time()
        diag = run_conditions(model, waves, truths, [(family, value)],
                              clean_correct, clean_bal, args.bootstrap)[0]
        conditions_seconds += time.time() - cond_t0
        state["done"][f"{family}:{value}"] = diag
        measured_now += 1
        paths["state"].write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    left = [f"{f}:{v}" for f, v in units if f"{f}:{v}" not in state["done"]]
    payload = {
        "command": "battery",
        "status": "complete" if not left else "in_progress",
        "completed": len(state["done"]),
        "total": len(units),
        "measured_this_call": measured_now,
        "seconds_this_call": round(time.time() - t0, 1),
        "remaining": left[:50],
        "remaining_count": len(left),
        "state_file": str(paths["state"]),
    }
    if not left:
        log("[battery] all conditions measured — aggregating")
        summary = _aggregate_battery(state, paths)
        payload.update({k: v for k, v in summary.items() if k not in ("results",)})
        payload["status"] = "complete"
        payload["summary_file"] = str(paths["summary"])
        payload["report_file"] = str(paths["markdown"])
    else:
        payload["next"] = "call battery again to continue; it resumes from the state file"
    emit(payload, args.out)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["catalog", "probe", "sweep", "curve", "battery"])
    ap.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    ap.add_argument("--session", default="Session5")
    ap.add_argument("--per-class", type=int, default=None,
                    help="utterances sampled per class; 0 = every 4-class utterance. "
                         "Defaults to 24 for probe/sweep/curve and 0 (full session) for battery.")
    ap.add_argument("--conditions", help="sweep: family:value,family:value,...")
    ap.add_argument("--family", help="curve: one perturbation family")
    ap.add_argument("--families", help="battery: 'all' or a comma-separated subset of families")
    ap.add_argument("--plan", help="battery: JSON file or inline JSON mapping family -> [values]")
    ap.add_argument("--budget-seconds", type=float, default=480.0,
                    help="battery: stop after roughly this long and report what is left "
                         "(keep below the harness shell timeout; 600 s was observed on AGH)")
    ap.add_argument("--status", action="store_true",
                    help="battery: report progress without measuring anything")
    ap.add_argument("--reset", action="store_true",
                    help="battery: discard saved state and measure everything from scratch")
    ap.add_argument("--from", dest="frm", type=float, help="curve: start value")
    ap.add_argument("--to", dest="to", type=float, help="curve: end value")
    ap.add_argument("--points", type=int, default=6)
    ap.add_argument("--bootstrap", type=int, default=BOOTSTRAP_B,
                    help="bootstrap resamples for confidence intervals (0 disables)")
    ap.add_argument("--sample-seed", type=int, default=SEED,
                    help="seed for drawing the test set, to replicate a result on a different "
                         "sample of the same session (bootstrap seeds are unaffected)")
    ap.add_argument("--out", type=Path, help="also write the JSON payload here")
    ap.add_argument("--debug", action="store_true",
                    help="show full tracebacks instead of clean error messages")
    args = ap.parse_args()

    global SAMPLE_SEED, DEBUG
    SAMPLE_SEED = args.sample_seed
    DEBUG = args.debug

    if args.per_class is None:
        args.per_class = 0 if args.command == "battery" else 24

    if args.command == "catalog":
        emit({
            "families": {
                k: {"unit": v["unit"], "description": v["desc"],
                    "suggested_sweep": v["sweep"], "higher_is_cleaner": v["higher_is_cleaner"],
                    "parameter_type": v.get("cast", float).__name__}
                for k, v in CATALOG.items()
            },
            "classes": list(CLASSES),
            "collapse_rule": "flagged degenerate when majority_share >= 0.75 or mean_normalised_entropy <= 0.30",
            "metrics": ["accuracy", "balanced_accuracy (macro recall)", "macro_f1",
                        "majority_share", "mean_normalised_entropy", "degenerate_probability",
                        "delta_balanced_accuracy_ci95", "mcnemar_exact_p", "cohens_h_vs_clean"],
            "notes": "metrics carry bootstrap CIs; conditions are paired-tested against the clean "
                     "reference on the same utterances; sweep-level p-values are Holm-corrected",
            "commands": {
                "catalog": "this listing",
                "probe": "clean baseline, label space, model fingerprint, throughput",
                "sweep": "measure a chosen set of conditions, with CIs and paired tests",
                "curve": "sample one family across its range and bracket its threshold",
                "battery": "confirm at full scale across many conditions; resumable, so it can be "
                           "called repeatedly under a shell timeout until status is 'complete'. "
                           "Progress is kept in outputs/battery/; --status reports it without "
                           "measuring, --reset starts over, --plan overrides the value lists "
                           "below, --budget-seconds caps one call.",
            },
            "canonical_battery": {k: v for k, v in BATTERY.items()},
            "canonical_battery_size": sum(len(v) for v in BATTERY.values()),
            "recommended_workflow": [
                "probe — establish the clean baseline and the label space",
                "sweep — explore a few mechanistically different conditions",
                "curve — for anything that looks degenerate, bracket its threshold",
                "battery — confirm the whole picture at full scale (--per-class 0); call it "
                "until status is complete",
                "report the confirmatory (battery) numbers, not the exploratory ones",
            ],
        }, args.out)
        return 0

    if args.command == "battery":
        return run_battery(args)

    # Validate every argument *before* paying for a model load and a dataset read. A typo in a
    # family name should cost nothing, not 30 seconds of GPU setup followed by an error.
    conditions: list[tuple[str, float]] | None = None
    if args.command == "sweep":
        if not args.conditions:
            fail(EXIT_USAGE, "sweep needs --conditions",
                 "Example: sweep --conditions gaussian_snr:10,lowpass:2000")
        conditions = parse_conditions(args.conditions)
    elif args.command == "curve":
        if not args.family or args.frm is None or args.to is None:
            fail(EXIT_USAGE, "curve needs --family, --from and --to",
                 "Example: curve --family gaussian_snr --from 20 --to -5 --points 6")
        if args.family not in CATALOG:
            near = difflib.get_close_matches(args.family, list(CATALOG), n=3, cutoff=0.5)
            fail(EXIT_USAGE, f"unknown perturbation family '{args.family}'",
                 (f"Did you mean: {', '.join(near)}" if near
                  else f"Known families: {', '.join(CATALOG)}"))
        if args.points < 2:
            fail(EXIT_USAGE, f"--points must be at least 2, got {args.points}",
                 "A curve needs two sampled values to bracket a transition between.")
    if args.per_class < 0:
        fail(EXIT_USAGE, f"--per-class must be >= 0, got {args.per_class}",
             "0 means 'use every 4-class utterance in the session'.")
    if args.bootstrap < 0:
        fail(EXIT_USAGE, f"--bootstrap must be >= 0, got {args.bootstrap}",
             "0 disables the confidence intervals.")

    # Dataset next: a wrong --session should also fail before the model is loaded.
    utts, truths = select_testset(args.session, args.per_class, args.sample_seed)
    log(f"[audit] test set {args.session}: {len(utts)} utterances, distribution={dict(Counter(truths))}")

    log(f"[audit] loading model {args.model}")
    model = SerModel(args.model)
    log(f"[audit] device={model.device}"
        + (f" gpu={model.gpu}" if model.gpu else ""))
    waves = load_waves(args.session, utts)
    log(f"[audit] audio loaded")

    if args.command == "probe":
        t0 = time.time()
        preds, probs = predict_all(model, waves)
        elapsed = time.time() - t0
        correct = np.array([p == t for p, t in zip(preds, truths)], dtype=bool)
        entropy = _entropies(probs)
        codes = np.array([CLASSES.index(p) if p in CLASSES else -1 for p in preds])
        point = _point_metrics(correct, entropy, codes, truths, preds)
        payload = {
            "command": "probe",
            "model_dir": str(args.model),
            "model_fingerprint": model.fingerprint,
            "model_labels": model.model.config.id2label,
            "device": model.device,
            "gpu": model.gpu,
            "session": args.session,
            "per_class": args.per_class,
            "class_distribution": dict(Counter(truths)),
            "ms_per_clip": round(elapsed / len(waves) * 1000, 1),
            "clips_per_second": round(len(waves) / elapsed, 2),
            "bootstrap_b": args.bootstrap,
            "clean": point,
            "sampled_utterances": utts,
        }
        if args.bootstrap:
            payload["clean"].update(bootstrap_stats(correct, entropy, codes, truths, preds,
                                                   args.bootstrap, SEED))
        emit(payload, args.out)
        return 0

    # sweep and curve both need the clean reference arm for paired comparison
    log("[audit] computing clean reference arm")
    clean_preds, clean_probs = predict_all(model, waves)
    clean_correct = np.array([p == t for p, t in zip(clean_preds, truths)], dtype=bool)
    clean_codes = np.array([CLASSES.index(p) if p in CLASSES else -1 for p in clean_preds])
    clean_entropy = _entropies(clean_probs)
    clean_point = _point_metrics(clean_correct, clean_entropy, clean_codes, truths, clean_preds)
    clean_bal = float(np.mean(list(clean_point["per_class_recall"].values())))
    clean_reference = dict(clean_point)
    clean_reference["degenerate"] = bool(
        clean_point["majority_share"] >= 0.75 or clean_point["mean_normalised_entropy"] <= 0.30)
    if args.bootstrap:
        clean_reference.update(bootstrap_stats(clean_correct, clean_entropy, clean_codes,
                                              truths, clean_preds, args.bootstrap, SEED))

    if args.command == "sweep":
        assert conditions is not None          # validated before the model was loaded
        log(f"[audit] sweeping {len(conditions)} condition(s), bootstrap_b={args.bootstrap}")
        results = run_conditions(model, waves, truths, conditions, clean_correct, clean_bal,
                                 args.bootstrap)
        measured = [r for r in results if r["valid"]]
        stats_block = None
        if len(measured) > 1:
            stats_block = holm_correct([r["mcnemar_exact_p"] for r in measured],
                                       [r["condition"] for r in measured])
        emit({
            "command": "sweep",
            "model_fingerprint": model.fingerprint,
            "device": model.device,
            "gpu": model.gpu,
            "session": args.session,
            "per_class": args.per_class,
            "n_utterances": len(waves),
            "bootstrap_b": args.bootstrap,
            "clean_reference": clean_reference,
            "results": results,
            "degenerate_conditions": [r["condition"] for r in results if r.get("degenerate")],
            "invalid_conditions": [r["condition"] for r in results if not r["valid"]],
            "multiple_comparison": stats_block,
        }, args.out)
        return 0

    if args.command == "curve":
        values = np.linspace(args.frm, args.to, args.points)
        cast = CATALOG[args.family].get("cast", float)
        conditions = [(args.family, cast(round(float(v), 4))) for v in values]
        log(f"[audit] sampling {args.family} over {args.frm} -> {args.to} ({args.points} points)")
        results = run_conditions(model, waves, truths, conditions, clean_correct, clean_bal,
                                 args.bootstrap)
        measured = [r for r in results if r["valid"]]
        stats_block = None
        if len(measured) > 1:
            stats_block = holm_correct([r["mcnemar_exact_p"] for r in measured],
                                       [r["condition"] for r in measured])

        # Locate the crossing: the last healthy step and the first collapsed step.
        first_bad = next((r for r in measured if r.get("degenerate")), None)
        threshold = None
        if first_bad:
            i = measured.index(first_bad)
            prev = measured[i - 1] if i > 0 else None
            threshold = {
                "first_degenerate": first_bad["condition"],
                "first_degenerate_value": first_bad["value"],
                "first_degenerate_probability": first_bad["degenerate_probability"],
                "last_healthy": prev["condition"] if prev else None,
                "last_healthy_value": prev["value"] if prev else None,
                "bracketing_interval": [prev["value"], first_bad["value"]] if prev
                                       else [first_bad["value"], first_bad["value"]],
                "interval_width": abs(first_bad["value"] - prev["value"]) if prev else 0.0,
                "basis": "inference between two adjacent sampled points, not an observation",
            }
        emit({
            "command": "curve",
            "model_fingerprint": model.fingerprint,
            "device": model.device,
            "gpu": model.gpu,
            "session": args.session,
            "per_class": args.per_class,
            "n_utterances": len(waves),
            "bootstrap_b": args.bootstrap,
            "family": args.family,
            "unit": CATALOG[args.family]["unit"],
            "range": [args.frm, args.to],
            "clean_reference": clean_reference,
            "results": results,
            "first_degenerate": first_bad["condition"] if first_bad else None,
            "threshold": threshold,
            "multiple_comparison": stats_block,
        }, args.out)
        return 0

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise                                   # fail() and argparse already reported cleanly
    except KeyboardInterrupt:
        log("[audit] interrupted")
        raise SystemExit(130)
    except Exception as exc:                    # last resort: never dump a bare traceback
        if DEBUG:
            raise
        fail(EXIT_UNEXPECTED, f"unhandled {type(exc).__name__}: {exc}",
             "This is a defect in the audit tool, not a result about the model.\n"
             "Re-run with --debug for the full traceback, and report it — a tool that fails "
             "silently or confusingly cannot be an instrument of record.")
