"""How much did the RNG-seeding fix change the previously published numbers?

One representative condition per family, measured with the fixed tool at full scale, compared
field-by-field against the earlier (unseeded) run. Families whose numbers are unchanged are
deterministic DSP and were never affected; families that moved are the stochastic ones.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
FULL = ROOT / "outputs" / "full"
BATTERY_DIR = ROOT / "outputs" / "battery"

REPRESENTATIVE = {
    "gaussian_snr": 30, "lowpass": 2000, "highpass": 400, "clipping": 10,
    "mp3": 32, "white_noise": 0.02, "gain": -20, "pitch": 4, "timestretch": 1.3,
}
PLAN = ROOT / "outputs" / "_impact_plan.json"
IGNORE = {"wall_seconds"}


def clean_env() -> dict:
    env = dict(os.environ)
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        env.pop(name, None)
    return env


def main() -> int:
    PLAN.write_text(json.dumps({k: [v] for k, v in REPRESENTATIVE.items()}), encoding="utf-8")
    print("measuring one representative condition per family at full scale (n=1241) ...")
    p = subprocess.run(
        [str(PY), "audit.py", "battery", "--plan", str(PLAN), "--per-class", "0",
         "--bootstrap", "2000", "--budget-seconds", "1500", "--reset"],
        cwd=str(ROOT), env=clean_env(), capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print(p.stderr[-2500:])
        return 1
    print(f"  {json.loads(p.stdout)['status']}")

    summaries = sorted(BATTERY_DIR.glob("summary_Session5_pc0_seed*.json"))
    new = {r["condition"]: r for r in json.loads(summaries[-1].read_text(encoding="utf-8"))["results"]}

    print("\n=== impact of the seeding fix, by family ===")
    print(f"  {'family':14s} {'condition':18s} {'batch(before)':>13s} {'battery(after)':>15s} "
          f"{'delta':>8s}  {'changed fields'}")
    affected, unaffected = [], []
    for fam, val in REPRESENTATIVE.items():
        cond = f"{fam}:{float(val)}"
        base_file = FULL / f"fam_{fam}.json"
        if not base_file.exists() or cond not in new:
            print(f"  {fam:14s} {cond:18s}   (missing on one side)")
            continue
        base = {r["condition"]: r for r in json.loads(base_file.read_text(encoding="utf-8"))["results"]}
        if cond not in base:
            print(f"  {fam:14s} {cond:18s}   (not in the earlier run)")
            continue
        a, b = base[cond], new[cond]
        diff = [k for k in sorted(set(a) & set(b)) if k not in IGNORE and a[k] != b[k]]
        d = b["balanced_accuracy"] - a["balanced_accuracy"]
        tag = "unchanged" if not diff else f"{len(diff)} fields"
        print(f"  {fam:14s} {cond:18s} {a['balanced_accuracy']:13.4f} "
              f"{b['balanced_accuracy']:15.4f} {d:+8.4f}  {tag}"
              + (f"  ({', '.join(diff[:4])}...)" if len(diff) > 4 else
                 (f"  ({', '.join(diff)})" if diff else "")))
        (affected if diff else unaffected).append(fam)

    print(f"\n  affected by the fix  : {affected}")
    print(f"  unaffected           : {unaffected}")

    # does the verdict survive?
    print("\n=== did any verdict change? ===")
    flips = []
    for fam, val in REPRESENTATIVE.items():
        cond = f"{fam}:{float(val)}"
        base_file = FULL / f"fam_{fam}.json"
        if not base_file.exists() or cond not in new:
            continue
        base = {r["condition"]: r for r in json.loads(base_file.read_text(encoding="utf-8"))["results"]}
        if cond in base and bool(base[cond].get("degenerate")) != bool(new[cond].get("degenerate")):
            flips.append(cond)
    print(f"  verdict flips: {flips if flips else 'none'}")

    out = ROOT / "outputs" / "seeding_impact.json"
    out.write_text(json.dumps({"affected_families": affected,
                               "unaffected_families": unaffected,
                               "verdict_flips": flips}, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
