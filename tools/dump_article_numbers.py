"""Dump the numbers needed for the public write-up, straight from the JSON artefacts."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BATT = ROOT / "outputs" / "battery"
AUX = ROOT / "outputs" / "auxiliary"

summary = sorted(BATT.glob("summary_*.json"))[-1]
s = json.loads(summary.read_text(encoding="utf-8"))
c = s["clean_reference"]

print("=== clean baseline, full Session5 (n=%d) ===" % s["n_utterances"])
print(f"  balanced_accuracy {c['balanced_accuracy']}  CI {c['balanced_accuracy_ci95']}")
print(f"  accuracy          {c['accuracy']}  CI {c['accuracy_ci95']}")
print(f"  majority          {c['majority_class']} {c['majority_share']}")
print(f"  per-class recall  {c['per_class_recall']}")

print("\n=== degenerate conditions (%d of %d) ===" % (s["n_degenerate"], s["n_conditions"]))
for r in sorted(s["results"], key=lambda r: (r["family"], float(r["value"]))):
    if r.get("degenerate"):
        print(f"  {r['condition']:18s} bacc={r['balanced_accuracy']:.3f} "
              f"maj={r['majority_share']:.2f} ({r['majority_class']}) "
              f"P(deg)={r['degenerate_probability']:.2f}  via {r['collapse_reason']}")

print("\n=== thresholds ===")
for fam, t in s["thresholds"].items():
    if t.get("threshold_found"):
        lo, hi = t["bracketing_interval"]
        print(f"  {fam:14s} [{lo}, {hi}]  width {t['interval_width']}  "
              f"first bad: {t['first_degenerate_condition']}")
    else:
        print(f"  {fam:14s} no collapse in range (worst {t.get('worst_sampled')})")

print("\n=== tolerated (|delta| < 0.05) ===")
for r in sorted(s["results"], key=lambda r: -r["balanced_accuracy"]):
    if r.get("valid") and not r.get("degenerate") and abs(r["delta_balanced_accuracy"]) < 0.05:
        print(f"  {r['condition']:20s} bacc={r['balanced_accuracy']:.4f} "
              f"delta={r['delta_balanced_accuracy']:+.4f}")

print("\n=== gain: every level degraded? ===")
for r in sorted(s["results"], key=lambda r: r["family"]):
    if r["family"] == "gain":
        print(f"  {r['condition']:12s} bacc={r['balanced_accuracy']:.3f} "
              f"delta={r['delta_balanced_accuracy']:+.3f} deg={r['degenerate']}")

aux = AUX / "aux_summary.json"
if aux.exists():
    a = json.loads(aux.read_text(encoding="utf-8"))
    print("\n=== cross-session clean baseline (balanced 48/class) ===")
    for sess, d in a["cross_session"].items():
        print(f"  {sess:10s} n={d['n']} bacc={d['clean_balanced_accuracy']:.3f} "
              f"CI {d['clean_ci95']}")
    print("\n=== cross-session verdicts on the shared conditions ===")
    conds = [x.strip() for x in a["conditions"].split(",")]
    for spec in conds:
        fam, raw = spec.split(":")
        want = float(raw)
        row = []
        for sess, d in a["cross_session"].items():
            hit = next((r for r in d["results"]
                        if r["condition"].startswith(fam + ":")
                        and abs(float(r["condition"].split(":")[1]) - want) < 1e-9), None)
            row.append("DEG" if hit and hit["degenerate"] else "ok ")
        print(f"  {spec:18s} " + "  ".join(row) + f"   ({'/'.join(a['cross_session'])[:40]})")
    print("\n=== seed stability (Session5, n=192, 5 draws) ===")
    for cond, st in a["seed_stability"].items():
        print(f"  {cond:18s} {st['collapsed_on']}/{st['of_draws']} "
              f"{'stable' if st['stable'] else 'UNSTABLE'}")
