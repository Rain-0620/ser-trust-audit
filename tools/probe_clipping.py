"""Reproduce the clipping:20 TypeError the agent reported, and identify the root cause."""
import traceback
from pathlib import Path

import numpy as np
import soundfile as sf
from audiomentations import ClippingDistortion, Compose

ROOT = Path(__file__).resolve().parent.parent
wav_dir = ROOT / "data" / "IEMOCAP" / "Session5" / "sentences" / "wav"
first = sorted(wav_dir.glob("*/*.wav"))[0]
wave, sr = sf.read(str(first), dtype="float32", always_2d=False)
print(f"clip={first.name} sr={sr} dtype={wave.dtype} shape={wave.shape} "
      f"min={wave.min():.4f} max={wave.max():.4f}")

for value in (20, 10, 1):
    t = Compose([ClippingDistortion(min_percentile_threshold=value,
                                    max_percentile_threshold=value, p=1.0)])
    try:
        out = np.asarray(t(samples=wave.copy(), sample_rate=16000), dtype=np.float32)
        changed = not np.allclose(out, wave)
        print(f"  clipping:{value:>3}  OK   changed={changed}  "
              f"out_min={out.min():.4f} out_max={out.max():.4f}")
    except Exception as exc:
        print(f"  clipping:{value:>3}  FAIL {type(exc).__name__}: {exc}")
        traceback.print_exc()

print("\n--- probe: what does ClippingDistortion actually do to this clip? ---")
t = ClippingDistortion(min_percentile_threshold=20, max_percentile_threshold=20, p=1.0)
out = t(samples=wave.copy(), sample_rate=16000)
print(f"identical to input: {np.allclose(out, wave)}")
print(f"max |delta|: {np.abs(np.asarray(out) - wave).max():.6e}")
