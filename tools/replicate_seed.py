"""Replicate the borderline collapse verdicts on independent test-set draws.

Phase C showed that `lowpass:900` collapses on 2 of 5 sessions, and the sample-design control
showed the same condition flips between the full session and the balanced subset. That leaves
one confound: composition. This runs the same session, same conditions, only the *draw* of the
balanced subset changes, so any verdict scatter here is pure sampling noise.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
OUT = ROOT / "outputs" / "full" / "seed_replication"
CONDITIONS = "gaussian_snr:7.5,gaussian_snr:4,lowpass:900,lowpass:600"
SESSION = "Session5"
PER_CLASS = 48
SEEDS = [20261008, 101, 202, 303, 404]


def clean_env() -> dict:
    env = dict(os.environ)
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        env.pop(name, None)
    return env


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    for seed in SEEDS:
        out_file = OUT / f"seed_{seed}.json"
        if out_file.exists():
            results[seed] = json.loads(out_file.read_text(encoding="utf-8"))
            print(f"  seed {seed}: cached", flush=True)
            continue
        print(f"  seed {seed}: running ...", flush=True)
        proc = subprocess.run(
            [str(PY), "audit.py", "sweep", "--conditions", CONDITIONS,
             "--session", SESSION, "--per-class", str(PER_CLASS),
             "--bootstrap", "2000", "--sample-seed", str(seed)],
            cwd=str(ROOT), env=clean_env(), capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            print(f"    FAILED rc={proc.returncode}\n{proc.stderr[-1500:]}")
            continue
        payload = json.loads(proc.stdout)
        out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        results[seed] = payload

    if not results:
        print("no results")
        return 1

    print("\n=== verdict by test-set draw (Session5, balanced 48/class) ===")
    specs = [c.strip() for c in CONDITIONS.split(",")]

    def find(payload: dict, spec: str):
        """Match by family + numeric value: the tool formats values as floats, so the
        condition string 'gaussian_snr:4' comes back as 'gaussian_snr:4.0'."""
        fam, raw = spec.split(":", 1)
        want = float(raw)
        for r in payload["results"]:
            if r.get("family") == fam and abs(float(r.get("value", 1e9)) - want) < 1e-9:
                return r
        return None

    header = f"  {'condition':18s}" + "".join(f"{s:>12d}" for s in sorted(results))
    print(header)
    stability = {}
    for spec in specs:
        row = f"  {spec:18s}"
        verdicts = []
        for seed in sorted(results):
            hit = find(results[seed], spec)
            if not hit or not hit.get("valid"):
                row += f"{'n/a':>12s}"
                continue
            verdicts.append(bool(hit["degenerate"]))
            row += f"{('DEG' if hit['degenerate'] else 'ok') + ' ' + format(hit['degenerate_probability'], '.2f'):>12s}"
        print(row)
        if verdicts:
            stability[spec] = {
                "collapsed_on": sum(verdicts),
                "of_draws": len(verdicts),
                "stable": sum(verdicts) in (0, len(verdicts)),
            }

    print("\n=== stability ===")
    for cond, s in stability.items():
        tag = "STABLE" if s["stable"] else "UNSTABLE"
        print(f"  {cond:18s} collapsed on {s['collapsed_on']}/{s['of_draws']} draws   [{tag}]")

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "session": SESSION,
        "per_class": PER_CLASS,
        "seeds": sorted(results),
        "conditions": specs,
        "stability": stability,
        "note": "Same session, same conditions, same per-class budget. Only the draw of the "
                "balanced subset differs, so scatter here is sampling noise in the collapse "
                "detector, not a property of the model.",
    }
    (OUT / "seed_replication_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {OUT / 'seed_replication_summary.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
