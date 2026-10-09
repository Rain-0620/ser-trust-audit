"""Final integrity check across every deliverable produced for this project."""
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\ser-audit")
FULL = ROOT / "outputs" / "full"
SEED = FULL / "seed_replication"

FAMILIES = ["gaussian_snr", "lowpass", "highpass", "clipping", "mp3",
            "white_noise", "gain", "pitch", "timestretch"]
SESSIONS = ["Session1", "Session2", "Session3", "Session4", "Session5"]

print(f"checked at {datetime.now():%Y-%m-%d %H:%M:%S}")
print()
print("=== experiment stages (Phase A) ===")
total_conditions = 0
for f in FAMILIES:
    p = FULL / f"fam_{f}.json"
    if not p.exists():
        print(f"  MISSING  {p.name}")
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    n_valid = sum(1 for r in d["results"] if r.get("valid"))
    total_conditions += len(d["results"])
    print(f"  OK  {p.name:26s} n={d['n_utterances']:5d}  "
          f"conditions={len(d['results']):2d}  valid={n_valid}")
print(f"  -> {total_conditions} conditions total")

print("\n=== cross-session (Phase C) ===")
for s in SESSIONS:
    p = FULL / f"xsession_{s}.json"
    if not p.exists():
        print(f"  MISSING  {p.name}")
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    print(f"  OK  {p.name:26s} n={d['n_utterances']:5d}  conditions={len(d['results'])}  "
          f"clean_bacc={d['clean_reference']['balanced_accuracy']:.3f}")

print("\n=== seed replication ===")
p = SEED / "seed_replication_summary.json"
if p.exists():
    d = json.loads(p.read_text(encoding="utf-8"))
    print(f"  OK  {p.name}  seeds={d['seeds']}")
    for cond, st in d["stability"].items():
        print(f"      {cond:18s} {st['collapsed_on']}/{st['of_draws']}  "
              f"{'stable' if st['stable'] else 'unstable'}")
else:
    print("  MISSING")

print("\n=== aggregate + reports ===")
for rel in ["outputs/full/full_experiment_summary.json",
            "outputs/full/full_experiment_results.md",
            "outputs/full/experiment.log",
            "trust_boundary_report_v2.md",
            "trust_boundary_report.md"]:
    p = ROOT / rel
    print(f"  {'OK ' if p.exists() else 'MISSING'}  {rel}"
          + (f"  ({p.stat().st_size} B)" if p.exists() else ""))

p = FULL / "full_experiment_summary.json"
if p.exists():
    d = json.loads(p.read_text(encoding="utf-8"))
    print(f"      summary: phase_a conditions={d['phase_a']['n_conditions']} "
          f"n={d['phase_a']['n_utterances']} families={len(d['phase_a']['families'])}")
    print(f"      thresholds found: "
          f"{sum(1 for t in d['thresholds'].values() if t and t.get('threshold_found'))}"
          f"/{len(d['thresholds'])} families")
    print(f"      cross_session sessions={len(d['cross_session'])}")
    print(f"      sample_design_control rows={len(d.get('sample_design_control', {}).get('comparisons', []))}")
    print(f"      global Holm m={d['multiple_comparison_global']['m_conditions']} "
          f"significant={d['multiple_comparison_global']['n_significant']}")

print("\n=== tooling ===")
for rel in ["audit.py", "tools/run_full_experiment.py", "tools/make_report.py",
            "tools/replicate_seed.py", "tools/summarize_cross_session.py",
            "tools/validate_stage.py", "tools/extract_trace_summary.py",
            "tools/peek_session_export.py", "docs/BUGLOG.md",
            ".agh/skills/ser-trust-audit/SKILL.md",
            "evidence/session/agent-audit-run.html",
            "evidence/session/trace_summary.md",
            "audit-task-prompt.txt"]:
    p = ROOT / rel
    print(f"  {'OK ' if p.exists() else 'MISSING'}  {rel}")

print("\n=== model + data still intact ===")
for rel in ["models/superb-er/pytorch_model.bin", "data/IEMOCAP/Session5",
            "data/IEMOCAP/Session1", ".venv/Scripts/python.exe"]:
    p = ROOT / rel
    print(f"  {'OK ' if p.exists() else 'MISSING'}  {rel}")
