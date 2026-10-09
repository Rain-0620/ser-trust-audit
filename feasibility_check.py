"""Feasibility check on real IEMOCAP data.

Proves the project's core technical path on this machine end to end:
    load the pretrained SER model -> infer clean IEMOCAP utterances
    -> apply controlled perturbations -> re-infer -> measure accuracy loss and flips.

This is the seed of the audit pipeline: the perturbation -> re-inference -> compare loop
is exactly what the AGH agent will drive later, just without the agent on top yet.

Run:  .venv\\Scripts\\python.exe feasibility_check.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from audiomentations import (
    AddGaussianSNR,
    ClippingDistortion,
    Compose,
    LowPassFilter,
    Mp3Compression,
    PitchShift,
    TimeStretch,
)
from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

ROOT = Path(__file__).resolve().parent
IEMOCAP = ROOT / "data" / "IEMOCAP"
MODEL_DIR = ROOT / "models" / "superb-er"
TEST_SESSION = "Session5"          # the conventional held-out split in the SUPERB protocol
PER_CLASS = int(sys.argv[1]) if len(sys.argv) > 1 else 8
SEED = 20261008                    # fixed so the audit is reproducible

# IEMOCAP raw emotion codes -> the four classes this model was trained on.
# excited and happy are merged because IEMOCAP annotators use them interchangeably.
IEMOCAP_TO_CLASS = {
    "ang": "angry",
    "exc": "happy",
    "hap": "happy",
    "sad": "sad",
    "neu": "neutral",
}

# Deterministic settings (min == max) so every run produces identical audio.
CONDITIONS: list[tuple[str, object]] = [
    ("clean", None),
    ("gaussian_snr20", Compose([AddGaussianSNR(min_snr_db=20, max_snr_db=20, p=1.0)])),
    ("gaussian_snr10", Compose([AddGaussianSNR(min_snr_db=10, max_snr_db=10, p=1.0)])),
    ("gaussian_snr0", Compose([AddGaussianSNR(min_snr_db=0, max_snr_db=0, p=1.0)])),
    ("lowpass_2k", Compose([LowPassFilter(min_cutoff_freq=2000, max_cutoff_freq=2000, p=1.0)])),
    ("clipping_p20", Compose([ClippingDistortion(min_percentile_threshold=20,
                                                 max_percentile_threshold=20, p=1.0)])),
    ("mp3_16kbps", Compose([Mp3Compression(min_bitrate=16, max_bitrate=16, p=1.0)])),
    ("pitch_up_4st", Compose([PitchShift(min_semitones=4, max_semitones=4, p=1.0)])),
    ("pitch_down_4st", Compose([PitchShift(min_semitones=-4, max_semitones=-4, p=1.0)])),
    ("timestretch_1_25", Compose([TimeStretch(min_rate=1.25, max_rate=1.25, p=1.0)])),
]


def normalize_label(text: str) -> str | None:
    """Map either the model's label strings or IEMOCAP codes onto the four audit classes."""
    low = text.strip().lower()
    if low in IEMOCAP_TO_CLASS:
        return IEMOCAP_TO_CLASS[low]
    if low in {"neutral", "happy", "angry", "sad", "excited"}:
        return "happy" if low == "excited" else low
    return None


LABEL_LINE = re.compile(r"^\[[\d.]+\s*-\s*[\d.]+\]\s+(\S+)\s+(\S+)\s+\[")


def read_labels(session: str) -> dict[str, str]:
    """Parse EmoEvaluation files into {utterance_id: audit_class}."""
    labels: dict[str, str] = {}
    for path in sorted((IEMOCAP / session / "dialog" / "EmoEvaluation").glob("Ses*.txt")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            m = LABEL_LINE.match(line)
            if not m:
                continue
            utt, raw = m.group(1), m.group(2)
            cls = normalize_label(raw)
            if cls:
                labels[utt] = cls
    return labels


def build_testset(labels: dict[str, str], per_class: int) -> list[tuple[str, Path, str]]:
    rng = np.random.default_rng(SEED)
    by_class: dict[str, list[tuple[str, Path]]] = defaultdict(list)
    for utt, cls in sorted(labels.items()):
        # Utterance ids are "<dialog>_<turn>"; dialogue directory names vary in length
        # (Ses05F_impro01 vs Ses05F_script03_2), so split on the last underscore.
        dialog = utt.rsplit("_", 1)[0]
        path = IEMOCAP / TEST_SESSION / "sentences" / "wav" / dialog / f"{utt}.wav"
        if path.exists():
            by_class[cls].append((utt, path))
    picked: list[tuple[str, Path, str]] = []
    for cls in ("angry", "happy", "sad", "neutral"):
        items = by_class[cls]
        if not items:
            continue
        idx = rng.choice(len(items), size=min(per_class, len(items)), replace=False)
        picked.extend((items[i][0], items[i][1], cls) for i in idx)
    return picked


def main() -> None:
    print("=" * 78)
    print("SER audit feasibility check — real IEMOCAP / Session5")
    print("=" * 78)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"torch {torch.__version__} | device={device}"
          + (f" ({torch.cuda.get_device_name(0)})" if device == "cuda" else ""))

    print("\n[1/5] loading model from disk ...")
    t0 = time.time()
    extractor = AutoFeatureExtractor.from_pretrained(str(MODEL_DIR))
    model = AutoModelForAudioClassification.from_pretrained(str(MODEL_DIR)).to(device).eval()
    print(f"  loaded in {time.time() - t0:.1f}s")
    print(f"  raw labels : {model.config.id2label}")
    id_to_class = {i: normalize_label(s) for i, s in model.config.id2label.items()}
    class_to_ids = defaultdict(list)
    for i, c in id_to_class.items():
        if c:
            class_to_ids[c].append(i)
    print(f"  mapped     : {dict(id_to_class)}")

    def predict(wave: np.ndarray) -> tuple[str | None, float, np.ndarray]:
        inputs = extractor(wave, sampling_rate=16000, return_tensors="pt", padding=True)
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            logits = model(**inputs).logits
        probs = torch.softmax(logits, dim=-1)[0].cpu().numpy()
        order = np.argsort(probs)[::-1]
        for index in order:
            cls = id_to_class.get(int(index))
            if cls:
                return cls, float(probs[index]), probs
        return None, 0.0, probs

    print("\n[2/5] building test set ...")
    labels = read_labels(TEST_SESSION)
    print(f"  parsed {len(labels)} labelled utterances from {TEST_SESSION}/dialog/EmoEvaluation")
    testset = build_testset(labels, PER_CLASS)
    counts = defaultdict(int)
    for _, _, c in testset:
        counts[c] += 1
    print(f"  selected {len(testset)} utterances  {dict(counts)}")
    if not testset:
        raise SystemExit("no test utterances found — check the IEMOCAP layout and label paths")

    print("\n[3/5] clean baseline + latency ...")
    waves = []
    for utt, path, truth in testset:
        wave, sr = sf.read(str(path), dtype="float32", always_2d=False)
        if wave.ndim > 1:
            wave = wave.mean(axis=1)
        if sr != 16000:
            raise ValueError(f"{path.name}: {sr} Hz")
        waves.append(wave)

    if device == "cuda":
        predict(waves[0])
    t0 = time.time()
    clean_preds = [predict(w)[0] for w in waves]
    per_clip = (time.time() - t0) / len(waves)
    clean_acc = np.mean([p == t for p, (_, _, t) in zip(clean_preds, testset)])
    print(f"  clean accuracy = {clean_acc:.3f}   {per_clip * 1000:.1f} ms/clip  ({1 / per_clip:.1f} clips/s)")

    print("\n[4/5] perturbation sweep ...")
    rows: list[dict] = []
    summary: list[tuple[str, float, int, int]] = []
    for name, transform in CONDITIONS:
        preds: list[str | None] = []
        try:
            for wave in waves:
                sample = wave if transform is None else np.asarray(
                    transform(samples=wave.copy(), sample_rate=16000), dtype=np.float32)
                preds.append(predict(sample)[0])
        except Exception as exc:
            # One unusable perturbation must not destroy the whole run: record and continue.
            print(f"  {name:17s} SKIPPED — {type(exc).__name__}: {str(exc)[:80]}")
            continue
        acc = float(np.mean([p == t for p, (_, _, t) in zip(preds, testset)]))
        flips = sum(1 for a, b in zip(clean_preds, preds) if a != b)
        distinct = len(set(preds))
        rows.extend(
            {"utterance": u, "truth": t, "condition": name, "prediction": p}
            for (u, _, t), p in zip(testset, preds)
        )
        summary.append((name, acc, flips, distinct))
        bar = "#" * int(round(acc * 40))
        print(f"  {name:17s} acc={acc:.3f}  flipped={flips:3d}/{len(waves)}  distinct={distinct}  {bar}")

    print("\n[5/5] writing results ...")
    outdir = ROOT / "outputs"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "feasibility_results.json").write_text(
        json.dumps({
            "session": TEST_SESSION,
            "n_utterances": len(testset),
            "clean_accuracy": clean_acc,
            "ms_per_clip": per_clip * 1000,
            "device": device,
            "gpu": torch.cuda.get_device_name(0) if device == "cuda" else None,
            "conditions": [
                {"condition": n, "accuracy": a, "flips": f, "distinct_predictions": d}
                for n, a, f, d in summary
            ],
            "rows": rows,
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"  wrote {outdir / 'feasibility_results.json'}")

    worst = min(summary[1:], key=lambda r: r[1]) if len(summary) > 1 else None
    print("\n" + "-" * 78)
    if worst:
        print(f"  most damaging perturbation : {worst[0]}  accuracy {worst[1]:.3f} "
              f"(drop {clean_acc - worst[1]:+.3f} vs clean)")
    collapsed = [n for n, _, _, d in summary if d == 1]
    print(f"  conditions where every prediction collapsed to one class : "
          f"{collapsed if collapsed else 'none'}")
    print("=" * 78)


if __name__ == "__main__":
    main()
