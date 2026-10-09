"""Validate a completed full-experiment stage file before resuming the driver."""
import json
import pathlib
import sys

FILES = [
    "fam_gaussian_snr.json",
    "fam_lowpass.json",
    "fam_highpass.json",
    "fam_clipping.json",
    "fam_mp3.json",
    "fam_white_noise.json",
    "fam_gain.json",
    "fam_pitch.json",
    "fam_timestretch.json",
]

OUT = pathlib.Path(r"D:\ser-audit\outputs\full")
for name in FILES:
    p = OUT / name
    if not p.exists():
        print(f"  MISSING  {name}")
        continue
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"  CORRUPT  {name}  ({type(exc).__name__})")
        continue
    n = d.get("n_utterances")
    clean = d.get("clean_reference", {})
    print(f"  OK       {name}  conditions={len(d['results'])} n={n} "
          f"clean_bacc={clean.get('balanced_accuracy')} deg={len(d.get('degenerate_conditions', []))} "
          f"invalid={len(d.get('invalid_conditions', []))}")

p = OUT / "fam_gaussian_snr.json"
if p.exists():
    d = json.loads(p.read_text(encoding="utf-8"))
    cs = d["clean_reference"]
    print("\n--- clean reference, full Session5 ---")
    print(f"  accuracy          {cs['accuracy']}  CI {cs['accuracy_ci95']}")
    print(f"  balanced accuracy {cs['balanced_accuracy']}  CI {cs['balanced_accuracy_ci95']}")
    print(f"  majority share    {cs['majority_share']}  ({cs['majority_class']})")
    print(f"  entropy           {cs['mean_normalised_entropy']}")
    print(f"  per-class recall  {cs['per_class_recall']}")
    print("\n--- gaussian_snr dose-response (n=1241) ---")
    print(f"  {'condition':18s} {'bacc':>6s} {'95% CI':>15s} {'delta':>7s} {'maj':>5s} {'P(deg)':>7s}  verdict")
    for r in sorted(d["results"], key=lambda x: -x["value"]):
        ci = r["balanced_accuracy_ci95"]
        degen = "COLLAPSE" if r["degenerate"] else ("degraded" if r["delta_balanced_accuracy"] < -0.05 else "tolerated")
        print(f"  {r['condition']:18s} {r['balanced_accuracy']:6.3f} "
              f"[{ci[0]:.3f},{ci[1]:.3f}] {r['delta_balanced_accuracy']:+7.3f} "
              f"{r['majority_share']:5.2f} {r['degenerate_probability']:7.2f}  {degen}")
