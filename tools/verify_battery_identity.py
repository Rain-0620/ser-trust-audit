"""Verify that `battery` reproduces the existing full-scale numbers exactly.

If chunking the work across calls changed any statistic, the AGH execution record would not
match the report — which is the whole point of adding the subcommand. This runs battery on two
conditions at full scale and compares every field against the earlier script-produced JSON.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
PLAN = ROOT / "outputs" / "_identity_plan.json"
BASELINE = ROOT / "outputs" / "full" / "fam_gaussian_snr.json"
BATTERY_DIR = ROOT / "outputs" / "battery"

FAMILY = "gaussian_snr"
VALUES = [30, 15]


def clean_env() -> dict:
    env = dict(os.environ)
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        env.pop(name, None)
    return env


def main() -> int:
    PLAN.write_text(json.dumps({FAMILY: VALUES}), encoding="utf-8")
    print(f"plan: {FAMILY} -> {VALUES}  (full session, n=1241, bootstrap 2000)")
    print("running battery (this takes a few minutes) ...")

    proc = subprocess.run(
        [str(PY), "audit.py", "battery", "--plan", str(PLAN), "--per-class", "0",
         "--bootstrap", "2000", "--budget-seconds", "900", "--reset"],
        cwd=str(ROOT), env=clean_env(), capture_output=True, text=True,
        encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        print(f"battery failed rc={proc.returncode}\n{proc.stderr[-2500:]}")
        return 1
    payload = json.loads(proc.stdout)
    print(f"  status={payload['status']} completed={payload['completed']}/{payload['total']}")

    # the aggregate lives under a keyed name; find it
    summaries = sorted(BATTERY_DIR.glob("summary_Session5_pc0_seed*.json"))
    if not summaries:
        print(f"no battery summary under {BATTERY_DIR}")
        return 1
    battery = json.loads(summaries[-1].read_text(encoding="utf-8"))
    battery_by_cond = {r["condition"]: r for r in battery["results"]}

    if not BASELINE.exists():
        print(f"baseline missing: {BASELINE}")
        return 1
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    base_by_cond = {r["condition"]: r for r in base["results"]}

    print("\n=== field-by-field comparison, battery vs earlier script run ===")
    keys = sorted({k for r in base_by_cond.values() for k in r} |
                  {k for r in battery_by_cond.values() for k in r})
    # fields that legitimately differ: timing
    timing = {"wall_seconds"}
    all_ok = True
    for cond in [f"{FAMILY}:{float(v)}" for v in VALUES]:
        a, b = battery_by_cond.get(cond), base_by_cond.get(cond)
        if a is None or b is None:
            print(f"  {cond}: MISSING on one side (battery={a is not None}, base={b is not None})")
            all_ok = False
            continue
        diffs = []
        for k in keys:
            if k in timing:
                continue
            if k in a and k in b and a[k] != b[k]:
                diffs.append(f"{k}: battery={a[k]!r} base={b[k]!r}")
        status = "IDENTICAL" if not diffs else "DIFFERS"
        if diffs:
            all_ok = False
        print(f"  {cond:18s} {status}")
        for d in diffs[:8]:
            print(f"      {d}")

    print("\n=== clean arm comparison ===")
    ca, cb = battery["clean_reference"], base["clean_reference"]
    cdiff = [f"{k}: battery={ca[k]!r} base={cb[k]!r}"
             for k in sorted(set(ca) & set(cb)) if ca[k] != cb[k]]
    print("  clean arm: " + ("IDENTICAL" if not cdiff else "DIFFERS"))
    for d in cdiff[:8]:
        print(f"      {d}")
    if cdiff:
        all_ok = False

    print("\n=== thresholds block ===")
    print(f"  battery thresholds: {list(battery.get('thresholds', {}).keys())}")
    print(f"  baseline thresholds: {list(base.get('thresholds', {}).keys())}")

    print()
    print("RESULT: " + ("battery reproduces the existing numbers exactly"
                        if all_ok else "MISMATCH — investigate before relying on the record"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
