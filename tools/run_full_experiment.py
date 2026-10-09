"""Full-scale audit experiment driver.

Runs the audit across the whole of Session 5 (n = 1241, every 4-class utterance) with
family-wise Holm correction, then a cross-session check on Sessions 1-5. Resumable: an
existing stage output that parses as JSON is skipped, so a crash never costs the whole run.

Usage
    python tools/run_full_experiment.py            # run everything, skip finished stages
    python tools/run_full_experiment.py --force    # re-run every stage
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
OUT = ROOT / "outputs" / "full"
LOG = OUT / "experiment.log"

# One invocation per mechanism family, so Holm-Bonferroni is applied within the family
# (the natural unit: dose levels of the same mechanism are not independent hypotheses).
#
# Values are chosen to bracket the regions where the model was seen to fail, with finer
# spacing there and coarser spacing in the plateaus.
FAMILIES: dict[str, list[float]] = {
    "gaussian_snr": [30, 15, 10, 9, 8.5, 8, 7.5, 7, 6, 5, 2, 0],   # fine around 6-10 dB
    "lowpass": [8000, 2000, 1100, 1000, 950, 900, 850, 800, 700],   # fine around 700-1100 Hz
    "highpass": [100, 200, 400, 800],
    "clipping": [1, 5, 10, 20, 30],
    "mp3": [64, 32, 16, 8],
    "white_noise": [0.005, 0.02, 0.05, 0.1],
    "gain": [20, -10, -20, -30],
    "pitch": [6, 4, 2, -2, -4, -6],
    "timestretch": [0.7, 0.85, 1.15, 1.3, 1.5],
}

# Cross-session arm: the two mechanisms that collapse, probed on every session.
XSESS_CONDITIONS = "gaussian_snr:7.5,gaussian_snr:4,lowpass:900,lowpass:600"
XSESS_SESSIONS = ["Session1", "Session2", "Session3", "Session4", "Session5"]
XSESS_PER_CLASS = 48

BOOTSTRAP = 2000


def log(msg: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{stamp}] {msg}"
    print(line, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def clean_env() -> dict:
    env = dict(os.environ)
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        env.pop(name, None)
    return env


def run_stage(label: str, out_file: Path, argv: list[str], force: bool) -> dict | None:
    if out_file.exists() and not force:
        try:
            payload = json.loads(out_file.read_text(encoding="utf-8"))
            log(f"SKIP {label} (already complete: {out_file.name})")
            return payload
        except Exception:
            log(f"WARN {label} output unreadable, re-running")

    log(f"START {label}  ->  {out_file.name}")
    t0 = time.time()
    proc = subprocess.run([str(PY), "audit.py", *argv], cwd=str(ROOT), env=clean_env(),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    elapsed = time.time() - t0
    if proc.returncode != 0:
        log(f"FAIL {label} rc={proc.returncode} in {elapsed:.0f}s")
        log(proc.stderr[-3000:] if proc.stderr else "(no stderr)")
        return None
    try:
        payload = json.loads(proc.stdout)
    except Exception as exc:
        log(f"FAIL {label} could not parse stdout: {exc}")
        return None
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"DONE  {label} in {elapsed:.0f}s")
    return payload


def severity_rank(family: str, value: float) -> float:
    """Map a parameter value to 'how distorted is this', so the threshold is findable.

    For higher_is_cleaner families, severity increases as the value falls, so the rank is the
    negated value; for the symmetric families (pitch, timestretch, gain) the notion of a single
    severity axis does not apply and the caller must not ask for a threshold.
    """
    if family in ("pitch", "timestretch", "gain"):
        return float("nan")
    if family in ("gaussian_snr", "lowpass", "mp3"):
        return -value
    return value          # highpass, clipping, white_noise: larger value = more distortion


def find_threshold(family: str, results: list[dict]) -> dict | None:
    measured = [r for r in results if r.get("valid") and r.get("degenerate") is not None]
    if len(measured) < 2 or family in ("pitch", "timestretch", "gain"):
        return None
    ordered = sorted(measured, key=lambda r: severity_rank(family, r["value"]))
    first_bad_index = next((i for i, r in enumerate(ordered) if r["degenerate"]), None)
    if first_bad_index is None:
        return {
            "family": family,
            "threshold_found": False,
            "note": "no sampled value collapsed; the tolerance boundary lies outside the sampled range",
            "worst_sampled": ordered[-1]["condition"],
        }
    first_bad = ordered[first_bad_index]
    prev = ordered[first_bad_index - 1] if first_bad_index > 0 else None
    return {
        "family": family,
        "threshold_found": True,
        "first_degenerate_condition": first_bad["condition"],
        "first_degenerate_value": first_bad["value"],
        "first_degenerate_probability": first_bad["degenerate_probability"],
        "last_healthy_condition": prev["condition"] if prev else None,
        "last_healthy_value": prev["value"] if prev else None,
        "bracketing_interval": [prev["value"], first_bad["value"]] if prev
                               else [first_bad["value"], first_bad["value"]],
        "interval_width": abs(first_bad["value"] - prev["value"]) if prev else 0.0,
        "collapse_signature": first_bad.get("collapse_reason"),
        "degenerate_majority_class": first_bad.get("majority_class"),
        "basis": "bracketed between two adjacent sampled values — an inference, not an observation",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-run stages that already have output")
    ap.add_argument("--skip-cross-session", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    log("=" * 78)
    log("full-scale audit experiment starting")
    log(f"phase A: {len(FAMILIES)} families x full Session5 (all 4-class utterances)")
    log(f"bootstrap_b={BOOTSTRAP}")

    phase_a: dict[str, dict] = {}
    t_start = time.time()
    for family, values in FAMILIES.items():
        spec = ",".join(f"{family}:{v}" for v in values)
        payload = run_stage(
            f"A:{family} (n={len(values)})",
            OUT / f"fam_{family}.json",
            ["sweep", "--conditions", spec, "--session", "Session5",
             "--per-class", "0", "--bootstrap", str(BOOTSTRAP)],
            args.force,
        )
        if payload:
            phase_a[family] = payload
    log(f"phase A complete in {(time.time() - t_start) / 60:.1f} min")

    phase_c: dict[str, dict] = {}
    if not args.skip_cross_session:
        log("-" * 78)
        log(f"phase C: cross-session, conditions={XSESS_CONDITIONS} per_class={XSESS_PER_CLASS}")
        t_c = time.time()
        for session in XSESS_SESSIONS:
            payload = run_stage(
                f"C:{session}",
                OUT / f"xsession_{session}.json",
                ["sweep", "--conditions", XSESS_CONDITIONS, "--session", session,
                 "--per-class", str(XSESS_PER_CLASS), "--bootstrap", str(BOOTSTRAP)],
                args.force,
            )
            if payload:
                phase_c[session] = payload
        log(f"phase C complete in {(time.time() - t_c) / 60:.1f} min")

    # ---------------- aggregate ----------------
    log("-" * 78)
    log("aggregating")

    all_conditions: list[dict] = []
    thresholds: dict[str, dict | None] = {}
    for family, payload in phase_a.items():
        results = payload["results"]
        all_conditions.extend(results)
        thresholds[family] = find_threshold(family, results)

    # Holm across ALL full-scale conditions, as an alternative (more conservative) view
    measured = [c for c in all_conditions if c.get("valid")]
    p_sorted = sorted(measured, key=lambda c: c["mcnemar_exact_p"])
    m = len(p_sorted)
    running_max = 0.0
    rejected_rank = -1
    for rank, cond in enumerate(p_sorted):
        adj = min(1.0, cond["mcnemar_exact_p"] * (m - rank))
        running_max = max(running_max, adj)
        cond["holm_global_adjusted_p"] = round(running_max, 6)
        if cond["mcnemar_exact_p"] <= 0.05 / (m - rank):
            rejected_rank = rank
    global_significant = {c["condition"] for rank, c in enumerate(p_sorted) if rank <= rejected_rank}
    for cond in all_conditions:
        cond["holm_global_significant"] = cond["condition"] in global_significant

    # clean baseline (recomputed identically inside every sweep; they must agree)
    clean_arms = {f: p["clean_reference"] for f, p in phase_a.items() if p.get("clean_reference")}

    # Sample-design control: Session5 appears in both phases, so any condition present in both
    # isolates the effect of the test set itself (n=1241 natural distribution vs n=192 balanced).
    # This is what separates "the model really collapses at 7.5 dB" from "the small balanced
    # subset made the collapse detector fire early".
    control: dict = {"note": "same session, same model, same condition — different test set"}
    a_session5 = {c["condition"]: c for c in all_conditions}
    c_session5_payload = phase_c.get("Session5")
    if c_session5_payload:
        cmp_rows = []
        for c in c_session5_payload["results"]:
            full = a_session5.get(c["condition"])
            if not full or not c.get("valid") or not full.get("valid"):
                continue
            cmp_rows.append({
                "condition": c["condition"],
                "full_n": full["n"],
                "full_balanced_accuracy": full["balanced_accuracy"],
                "full_majority_share": full["majority_share"],
                "full_degenerate": full["degenerate"],
                "full_P_degenerate": full["degenerate_probability"],
                "balanced_n": c["n"],
                "balanced_balanced_accuracy": c["balanced_accuracy"],
                "balanced_majority_share": c["majority_share"],
                "balanced_degenerate": c["degenerate"],
                "balanced_P_degenerate": c["degenerate_probability"],
                "verdict_flips": bool(full["degenerate"]) != bool(c["degenerate"]),
            })
        control["comparisons"] = cmp_rows
        control["clean_full"] = {k: clean_arms.get("gaussian_snr", {}).get(k)
                                 for k in ("balanced_accuracy", "balanced_accuracy_ci95",
                                           "per_class_recall")}
        control["clean_balanced"] = {
            k: c_session5_payload["clean_reference"].get(k)
            for k in ("balanced_accuracy", "balanced_accuracy_ci95", "per_class_recall")
        }
        flips = [r["condition"] for r in cmp_rows if r["verdict_flips"]]
        control["conditions_with_flipped_verdict"] = flips
        control["interpretation"] = (
            "A flipped verdict here means the collapse call depends on the evaluation set, "
            "not only on the model: the small balanced subset and the full session disagree."
            if flips else
            "No verdict flip between the two evaluation sets for the shared conditions."
        )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase_a": {
            "session": "Session5",
            "per_class": 0,
            "n_utterances": next(iter(phase_a.values()))["n_utterances"] if phase_a else None,
            "bootstrap_b": BOOTSTRAP,
            "n_conditions": len(all_conditions),
            "families": list(phase_a.keys()),
        },
        "thresholds": thresholds,
        "sample_design_control": control,
        "multiple_comparison_global": {
            "method": "holm-bonferroni",
            "alpha": 0.05,
            "m_conditions": m,
            "n_significant": len(global_significant),
            "note": "per-family Holm is also present inside each fam_*.json (multiple_comparison)",
        },
        "conditions": all_conditions,
        "cross_session": {
            session: {
                "n_utterances": p["n_utterances"],
                "results": p["results"],
            }
            for session, p in phase_c.items()
        },
    }
    summary_file = OUT / "full_experiment_summary.json"
    summary_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"wrote {summary_file}")

    # markdown table for the report
    lines = ["# Full-scale audit results — Session5, n = %s" % summary["phase_a"]["n_utterances"], ""]
    lines.append("Balanced accuracy (macro recall) with 95% bootstrap CI; delta and exact McNemar "
                 "p-value are paired against the clean reference on the same utterances.")
    lines += ["", "| Condition | Bal. acc | 95% CI | Δ vs clean | McNemar p | Holm (family) | Majority | P(deg) | Verdict |",
              "|---|---|---|---|---|---|---|---|---|"]
    for family, payload in phase_a.items():
        fam_adj = (payload.get("multiple_comparison") or {}).get("adjusted_p", {})
        for cond in sorted(payload["results"], key=lambda c: -(c.get("value") or 0)):
            if not cond.get("valid"):
                lines.append(f"| `{cond['condition']}` | — | — | — | — | — | — | — | "
                             f"**INVALID** ({cond.get('invalid_reason', '')}) |")
                continue
            ci = cond["balanced_accuracy_ci95"]
            verdict = "**COLLAPSE**" if cond["degenerate"] else (
                "degraded" if (cond["delta_balanced_accuracy"] or 0) < -0.05 else "tolerated")
            lines.append(
                f"| `{cond['condition']}` | {cond['balanced_accuracy']:.3f} | "
                f"[{ci[0]:.3f}, {ci[1]:.3f}] | {cond['delta_balanced_accuracy']:+.3f} | "
                f"{cond['mcnemar_exact_p']:.2e} | {fam_adj.get(cond['condition'], float('nan')):.2e} | "
                f"{cond['majority_class']} {cond['majority_share']:.2f} | "
                f"{cond['degenerate_probability']:.2f} | {verdict} |")
    lines += ["", "## Located thresholds", ""]
    lines += ["| Family | Last healthy | First collapsed | Bracketed interval | Signature |", "|---|---|---|---|---|"]
    for family, th in thresholds.items():
        if not th:
            continue
        if not th.get("threshold_found"):
            lines.append(f"| {family} | {th['worst_sampled']} | — none in range — | — | no collapse observed |")
            continue
        lo, hi = th["bracketing_interval"]
        lines.append(f"| {family} | {th['last_healthy_condition']} | {th['first_degenerate_condition']} | "
                     f"[{lo}, {hi}] (width {th['interval_width']}) | {th['collapse_signature']} |")
    md_file = OUT / "full_experiment_results.md"
    md_file.write_text("\n".join(lines), encoding="utf-8")
    log(f"wrote {md_file}")

    if control.get("comparisons"):
        lines += ["", "## Sample-design control (same session, different test set)", "",
                  "Session5 is evaluated twice: as the full 4-class set (n=1241, natural class "
                  "distribution) and as a balanced subset (n=192). Shared conditions show whether "
                  "a collapse verdict is a property of the model or of the evaluation set.",
                  "",
                  "| Condition | Full n=%d bacc | Full majority | Full verdict | Balanced n=%d bacc | Balanced majority | Balanced verdict | Flip? |"
                  % (control["comparisons"][0]["full_n"], control["comparisons"][0]["balanced_n"]),
                  "|---|---|---|---|---|---|---|---|"]
        for r in control["comparisons"]:
            lines.append(
                f"| `{r['condition']}` | {r['full_balanced_accuracy']:.3f} | "
                f"{r['full_majority_share']:.2f} | {'COLLAPSE' if r['full_degenerate'] else 'not'} | "
                f"{r['balanced_balanced_accuracy']:.3f} | {r['balanced_majority_share']:.2f} | "
                f"{'COLLAPSE' if r['balanced_degenerate'] else 'not'} | "
                f"{'**YES**' if r['verdict_flips'] else 'no'} |")
        lines += ["", f"_{control['interpretation']}_"]
        md_file.write_text("\n".join(lines), encoding="utf-8")
        log(f"sample-design control: flips={control['conditions_with_flipped_verdict']}")

    # consistency check: every sweep recomputes the clean arm independently; they must match
    accs = {f: c["accuracy"] for f, c in clean_arms.items()}
    log(f"clean-arm accuracy across {len(accs)} independent sweeps: "
        f"{sorted(set(accs.values()))}  (deterministic => single value expected)")
    log(f"TOTAL experiment wall time {(time.time() - t_start) / 60:.1f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
