"""Is the clipping TypeError caused by passing float where audiomentations expects int?"""
from pathlib import Path

import numpy as np
import soundfile as sf
from audiomentations import ClippingDistortion, Compose

ROOT = Path(__file__).resolve().parent.parent
first = sorted((ROOT / "data" / "IEMOCAP" / "Session5" / "sentences" / "wav").glob("*/*.wav"))[0]
wave, _ = sf.read(str(first), dtype="float32", always_2d=False)


def attempt(label, **kwargs):
    t = Compose([ClippingDistortion(p=1.0, **kwargs)])
    try:
        out = np.asarray(t(samples=wave.copy(), sample_rate=16000), dtype=np.float32)
        print(f"  {label:38s} OK    changed={not np.allclose(out, wave)}")
    except Exception as exc:
        print(f"  {label:38s} FAIL  {type(exc).__name__}: {exc}")


print("--- int vs float for percentile thresholds ---")
attempt("int   (20, 20)", min_percentile_threshold=20, max_percentile_threshold=20)
attempt("float (20.0, 20.0)", min_percentile_threshold=20.0, max_percentile_threshold=20.0)

print("\n--- same question for the other int-typed families we use ---")
from audiomentations import Mp3Compression
for label, kw in [
    ("mp3 int   (32, 32)", dict(min_bitrate=32, max_bitrate=32)),
    ("mp3 float (32.0, 32.0)", dict(min_bitrate=32.0, max_bitrate=32.0)),
]:
    try:
        t = Compose([Mp3Compression(p=1.0, **kw)])
        out = np.asarray(t(samples=wave.copy(), sample_rate=16000), dtype=np.float32)
        print(f"  {label:38s} OK    changed={not np.allclose(out, wave)}")
    except Exception as exc:
        print(f"  {label:38s} FAIL  {type(exc).__name__}: {exc}")
