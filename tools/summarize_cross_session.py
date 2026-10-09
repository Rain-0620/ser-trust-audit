"""Summarise the cross-session arm and the sample-design control from the full experiment."""
import json
import pathlib

OUT = pathlib.Path(r"D:\ser-audit\outputs\full")


def load(name):
    p = OUT / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


sessions = ["Session1", "Session2", "Session3", "Session4", "Session5"]
payloads = {s: load(f"xsession_{s}.json") for s in sessions}

print("=== cross-session clean baseline (balanced, 48/class) ===")
print(f"  {'session':10s} {'n':>5s} {'acc':>6s} {'bacc':>6s} {'95% CI':>16s}  per-class recall")
for s in sessions:
    d = payloads[s]
    if not d:
        print(f"  {s:10s}  MISSING")
        continue
    c = d["clean_reference"]
    ci = c["balanced_accuracy_ci95"]
    r = c["per_class_recall"]
    print(f"  {s:10s} {d['n_utterances']:5d} {c['accuracy']:6.3f} {c['balanced_accuracy']:6.3f} "
          f"[{ci[0]:.3f},{ci[1]:.3f}]  "
          + " ".join(f"{k[:3]}={v:.2f}" for k, v in r.items()))

conds = ["gaussian_snr:7.5", "gaussian_snr:4.0", "lowpass:900.0", "lowpass:600.0"]
print("\n=== cross-session: same conditions on every session ===")
print(f"  {'condition':18s}" + "".join(f"{s:>12s}" for s in sessions))
print(f"  {'':18s}" + "".join(f"{'bacc  deg':>12s}" for s in sessions))
for cond in conds:
    row = f"  {cond:18s}"
    for s in sessions:
        d = payloads[s]
        if not d:
            row += f"{'--':>12s}"
            continue
        hit = next((r for r in d["results"] if r["condition"] == cond and r.get("valid")), None)
        if not hit:
            row += f"{'n/a':>12s}"
            continue
        mark = "YES" if hit["degenerate"] else "no"
        row += f"{hit['balanced_accuracy']:6.3f} {mark:>5s}"
    print(row)

print("\n=== degenerate verdict counts across the 5 sessions ===")
for cond in conds:
    votes = []
    for s in sessions:
        d = payloads[s]
        if not d:
            continue
        hit = next((r for r in d["results"] if r["condition"] == cond and r.get("valid")), None)
        if hit:
            votes.append(1 if hit["degenerate"] else 0)
    if votes:
        print(f"  {cond:18s} collapsed on {sum(votes)}/{len(votes)} sessions")

print("\n=== sample-design control (Session5: full vs balanced) ===")
s5 = load("xsession_Session5.json")
a = load("fam_gaussian_snr.json")
b = load("fam_lowpass.json")
full_by_cond = {}
for p in (a, b):
    if p:
        for r in p["results"]:
            full_by_cond[r["condition"]] = r
if s5:
    for r in s5["results"]:
        f = full_by_cond.get(r["condition"])
        if not f:
            continue
        print(f"  {r['condition']:18s} full n={f['n']:<5d} bacc={f['balanced_accuracy']:.3f} "
              f"maj={f['majority_share']:.2f} P(deg)={f['degenerate_probability']:.2f} "
              f"{'DEG' if f['degenerate'] else 'ok ':4s} | "
              f"balanced n={r['n']:<4d} bacc={r['balanced_accuracy']:.3f} "
              f"maj={r['majority_share']:.2f} P(deg)={r['degenerate_probability']:.2f} "
              f"{'DEG' if r['degenerate'] else 'ok ':4s} | "
              f"{'FLIP' if bool(f['degenerate']) != bool(r['degenerate']) else ''}")

print("\n=== exact no-op sanity checks ===")
for key, payload in (("gaussian_snr", a), ("lowpass", b)):
    if not payload:
        continue
    for r in payload["results"]:
        if abs(r["delta_balanced_accuracy"]) < 1e-9:
            print(f"  {r['condition']:18s} delta=+0.000  McNemar p={r['mcnemar_exact_p']}  "
                  f"clips_modified={r['clips_actually_modified']}")
