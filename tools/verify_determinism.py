"""Does the audit now produce byte-identical results across separate processes?

Before the per-condition RNG seeding fix, stochastic transforms (AddGaussianSNR, AddGaussianNoise)
drew from unseeded global RNGs, so `gaussian_snr` and `white_noise` changed on every run. This
runs the same conditions twice in two fresh processes and diffs every field.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
ARGS = ["sweep", "--conditions",
        "gaussian_snr:30,white_noise:0.02,lowpass:2000,highpass:400,clipping:10,mp3:32",
        "--per-class", "8", "--bootstrap", "100"]
IGNORE = {"wall_seconds"}


def clean_env() -> dict:
    env = dict(os.environ)
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        env.pop(name, None)
    return env


def run() -> dict:
    p = subprocess.run([str(PY), "audit.py", *ARGS], cwd=str(ROOT), env=clean_env(),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print(p.stderr[-2000:])
        sys.exit(1)
    return json.loads(p.stdout)


def main() -> int:
    print("run 1 (fresh process) ...")
    a = run()
    print("run 2 (fresh process) ...")
    b = run()

    ok = True
    print("\n=== per-condition comparison across two processes ===")
    for ca, cb in zip(a["results"], b["results"]):
        cond = ca["condition"]
        diff = [f"{k}: {ca[k]!r} vs {cb[k]!r}"
                for k in sorted(set(ca) & set(cb)) if k not in IGNORE and ca[k] != cb[k]]
        if b"clips" in b"":
            pass
        print(f"  {cond:20s} {'IDENTICAL' if not diff else 'DIFFERS'}"
              f"   bacc={ca['balanced_accuracy']:.4f}  clips_modified={ca.get('clips_actually_modified')}")
        for d in diff[:6]:
            print(f"      {d}")
        if diff:
            ok = False

    print("\n=== clean arm ===")
    cd = [f"{k}: {a['clean_reference'][k]!r} vs {b['clean_reference'][k]!r}"
          for k in sorted(set(a["clean_reference"]) & set(b["clean_reference"]))
          if k not in IGNORE and a["clean_reference"][k] != b["clean_reference"][k]]
    print("  " + ("IDENTICAL" if not cd else "DIFFERS"))
    for d in cd[:6]:
        print(f"      {d}")
    if cd:
        ok = False

    print()
    print("RESULT: " + ("the audit is reproducible across processes"
                        if ok else "STILL NOT REPRODUCIBLE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
