"""Re-measure the auxiliary arms with the fixed tool.

The cross-session arm and the seed-replication arm both used exactly the four conditions that
BUG-3/BUG-4 invalidated (`gaussian_snr:7.5`, `gaussian_snr:4`, `lowpass:900`, `lowpass:600`),
so every number in both arms is stale. They are cheap to redo (~15 min total).

Writes to outputs/auxiliary/ so the superseded outputs/full/ tree is left as-is for the record.
(NB: "aux" is a reserved device name on Windows and cannot be used as a directory.)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
AUX = ROOT / "outputs" / "auxiliary"
CONDITIONS = "gaussian_snr:7.5,gaussian_snr:4,lowpass:900,lowpass:600"
SESSION = "Session5"
PER_CLASS = 48
SESSIONS = ["Session1", "Session2", "Session3", "Session4", "Session5"]
SEEDS = [20261008, 101, 202, 303, 404]


def clean_env() -> dict:
    env = dict(os.environ)
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        env.pop(name, None)
    return env


def run_sweep(args: list[str], out_file: Path) -> dict | None:
    proc = subprocess.run([str(PY), "audit.py", "sweep", *args], cwd=str(ROOT), env=clean_env(),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        print(f"    FAILED rc={proc.returncode}\n{proc.stderr[-1200:]}")
        return None
    payload = json.loads(proc.stdout)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def main() -> int:
    AUX.mkdir(parents=True, exist_ok=True)

    print("=== cross-session arm (balanced 48/class per session) ===")
    xsess = {}
    for s in SESSIONS:
        out = AUX / f"xsession_{s}.json"
        if out.exists():
            print(f"  {s}: cached")
            xsess[s] = json.loads(out.read_text(encoding="utf-8"))
            continue
        print(f"  {s}: measuring ...", flush=True)
        p = run_sweep(["--conditions", CONDITIONS, "--session", s,
                       "--per-class", str(PER_CLASS), "--bootstrap", "2000"], out)
        if p:
            xsess[s] = p
            clean = p["clean_reference"]["balanced_accuracy"]
            degs = sum(1 for r in p["results"] if r.get("degenerate"))
            print(f"    clean bacc={clean:.3f}  collapsed {degs}/{len(p['results'])}")

    print("\n=== seed replication (Session5, balanced 48/class, 5 draws) ===")
    stability = {}
    table = {}
    for seed in SEEDS:
        out = AUX / f"seed_{seed}.json"
        if out.exists():
            print(f"  seed {seed}: cached")
            p = json.loads(out.read_text(encoding="utf-8"))
        else:
            print(f"  seed {seed}: measuring ...", flush=True)
            p = run_sweep(["--conditions", CONDITIONS, "--session", SESSION,
                           "--per-class", str(PER_CLASS), "--bootstrap", "2000",
                           "--sample-seed", str(seed)], out)
            if not p:
                continue
        table[seed] = {r["condition"]: r for r in p["results"]}

    for spec in [c.strip() for c in CONDITIONS.split(",")]:
        fam, raw = spec.split(":")
        want = float(raw)
        votes = []
        for seed, by_cond in table.items():
            hit = next((r for k, r in by_cond.items()
                        if k.startswith(fam + ":") and abs(float(k.split(":")[1]) - want) < 1e-9),
                       None)
            if hit:
                votes.append(bool(hit["degenerate"]))
        if votes:
            stability[spec] = {"collapsed_on": sum(votes), "of_draws": len(votes),
                               "stable": sum(votes) in (0, len(votes))}

    print("\n  stability:")
    for cond, s in stability.items():
        print(f"    {cond:18s} {s['collapsed_on']}/{s['of_draws']}  "
              f"{'stable' if s['stable'] else 'UNSTABLE'}")

    summary = {
        "note": "re-measured with the RNG-seeding and roll-off fixes (docs/BUGLOG.md BUG-3, BUG-4)",
        "conditions": CONDITIONS,
        "per_class": PER_CLASS,
        "cross_session": {
            s: {"n": p["n_utterances"],
                "clean_balanced_accuracy": p["clean_reference"]["balanced_accuracy"],
                "clean_ci95": p["clean_reference"]["balanced_accuracy_ci95"],
                "per_class_recall": p["clean_reference"]["per_class_recall"],
                "results": [{k: r[k] for k in ("condition", "balanced_accuracy",
                                               "balanced_accuracy_ci95", "majority_share",
                                               "degenerate", "degenerate_probability")}
                            for r in p["results"]]}
            for s, p in xsess.items()},
        "seed_stability": stability,
        "seeds": sorted(table),
    }
    (AUX / "aux_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                          encoding="utf-8")
    print(f"\nwrote {AUX / 'aux_summary.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
