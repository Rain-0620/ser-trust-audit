"""Run the audit tool's test cases and write docs/TEST_CASES.md.

Three classes, matching how a reviewer would probe the work:

  normal   the tool runs and returns the expected, reproducible numbers
  boundary a case whose correct answer is *uncertainty* — the tool must report the
           boundary rather than force a verdict
  failure  a bad input that must produce a clear, typed error and a non-zero exit code,
           never a plausible-looking result

`tests.txt` style "did it exit 0" checking is not enough here: the failure class exists
precisely because a tool that reports a number for an unmeasurable condition is worse than
one that crashes. So each case asserts on structure and on specific values, not just exit status.

Usage
    .venv\\Scripts\\python.exe tools/test_cases.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"
DOC = ROOT / "docs" / "TEST_CASES.md"
FIXTURE = ROOT / "data" / "IEMOCAP" / "_selftest_bad_samplerate"

PER_CLASS = 8          # small enough to run quickly; the full-scale run is the real evidence
BOOTSTRAP = 100

EXIT_OK, EXIT_USAGE, EXIT_MODEL, EXIT_DATA = 0, 2, 3, 4


def clean_env() -> dict:
    env = dict(os.environ)
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        env.pop(name, None)
    return env


def make_bad_samplerate_fixture() -> None:
    """A tiny session whose only wav is 8 kHz — the tool must refuse it, not resample."""
    evaldir = FIXTURE / "dialog" / "EmoEvaluation"
    wavdir = FIXTURE / "sentences" / "wav" / "Ses99F_impro01"
    evaldir.mkdir(parents=True, exist_ok=True)
    wavdir.mkdir(parents=True, exist_ok=True)
    utt = "Ses99F_impro01_X001"
    (evaldir / "Ses99F_impro01.txt").write_text(
        f"[0.000 - 2.000]\t{utt}\tneu\t[3.0, 3.0, 3.0]\n", encoding="utf-8")
    tone = 0.1 * np.sin(2 * np.pi * 220 * np.arange(16000) / 8000).astype(np.float32)
    sf.write(str(wavdir / f"{utt}.wav"), tone, 8000)


def run(args: list[str]) -> dict:
    proc = subprocess.run([str(PY), "audit.py", *args], cwd=str(ROOT), env=clean_env(),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    payload = None
    if proc.returncode == 0:
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            payload = None
    return {
        "args": args,
        "cmd": ".venv\\Scripts\\python.exe audit.py " + " ".join(args),
        "rc": proc.returncode,
        "payload": payload,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def probe_clean(r: dict) -> dict:
    return (r["payload"] or {}).get("clean", {})


CASES: list[dict] = []


def case(kind: str, name: str, args: list[str], expect_rc: int,
         check=None, why: str = "", expect_msg: str | None = None) -> None:
    CASES.append({"kind": kind, "name": name, "args": args, "expect_rc": expect_rc,
                  "check": check, "why": why, "expect_msg": expect_msg})


# ---------------- normal ----------------
case("normal", "list the perturbation catalogue", ["catalog"], EXIT_OK,
     check=lambda r: (len(r["payload"]["families"]) == 9
                      and r["payload"]["families"]["clipping"]["parameter_type"] == "int"),
     why="九族扰动全部列出；clipping 声明为 int 参数，这正是 v1 缺陷的防线")

case("normal", "clean baseline on a fixed sample", ["probe", "--session", "Session5",
                                                   "--per-class", str(PER_CLASS),
                                                   "--bootstrap", str(BOOTSTRAP)], EXIT_OK,
     check=lambda r: (r["payload"]["model_fingerprint"] == "dac0f46128deec04"
                      and 0.0 < probe_clean(r)["accuracy"] <= 1.0
                      and probe_clean(r)["balanced_accuracy_ci95"][0]
                      <= probe_clean(r)["balanced_accuracy"]
                      <= probe_clean(r)["balanced_accuracy_ci95"][1]),
     why="模型指纹可复现；基线落在自身置信区间内")

case("normal", "a tolerated perturbation", ["sweep", "--conditions", "gaussian_snr:30",
                                          "--per-class", str(PER_CLASS),
                                          "--bootstrap", str(BOOTSTRAP)], EXIT_OK,
     check=lambda r: (r["payload"]["results"][0]["degenerate"] is False
                      and r["payload"]["results"][0]["valid"] is True),
     why="轻噪声下模型仍正常工作，判定为未塌缩")

# ---------------- boundary ----------------
case("boundary", "arithmetic no-op must show exactly zero effect",
     ["sweep", "--conditions", "lowpass:8000,clipping:1",
      "--per-class", str(PER_CLASS), "--bootstrap", str(BOOTSTRAP)], EXIT_OK,
     check=lambda r: all(abs(c["delta_balanced_accuracy"]) < 1e-9
                         and c["mcnemar_exact_p"] == 1.0 for c in r["payload"]["results"]),
     why="8000 Hz 是 16 kHz 的 Nyquist 上限、1% 削波几乎不改变波形。两者必须给出 Δ 恰好 0 "
         "且 p=1.0 —— 这是对 no-op 检测能力的检验，也是 v1 那个缺陷（失败被伪装成 0 效应）的反面")

case("boundary", "the tool must bracket a threshold, not report a point",
     ["curve", "--family", "gaussian_snr", "--from", "10", "--to", "0",
      "--points", "5", "--per-class", str(PER_CLASS), "--bootstrap", str(BOOTSTRAP)], EXIT_OK,
     check=lambda r: ("threshold" in r["payload"]
                      and r["payload"]["results"][0]["balanced_accuracy_ci95"][0]
                      < r["payload"]["results"][0]["balanced_accuracy_ci95"][1]
                      and "basis" in (r["payload"].get("threshold") or {"basis": ""})),
     why="curve 必须同时给出括号区间和「这是推断而非观测」的声明，而不是一个孤立的阈值数字")

case("boundary", "regression: the v1 clipping defect must stay fixed",
     ["sweep", "--conditions", "clipping:20", "--per-class", str(PER_CLASS),
      "--bootstrap", str(BOOTSTRAP)], EXIT_OK,
     check=lambda r: (r["payload"]["results"][0]["valid"] is True
                      and r["payload"]["results"][0]["transform_failures"] == 0
                      and r["payload"]["results"][0]["clips_actually_modified"] == PER_CLASS * 4),
     why="v1 里 clipping 因 float/int 类型错而全族失败，且失败被静默回退成干净音频，"
         "产出与基线逐位相同的假结果。此用例确保它不会再发生（BUGLOG BUG-1）")

# ---------------- failure ----------------
case("failure", "model directory does not exist",
     ["probe", "--model", r"D:\no-such-model-directory", "--per-class", "2"], EXIT_MODEL,
     expect_msg="does not exist",
     why="必须以模型类错误退出，而不是甩出 transformers 的原始堆栈")

case("failure", "model path is a file, not a directory",
     ["probe", "--model", r"D:\ser-audit\audit.py", "--per-class", "2"], EXIT_MODEL,
     expect_msg="must be a directory",
     why="常见误用：把 --model 指向了权重文件本身")

case("failure", "model directory is incomplete",
     ["probe", "--model", r"D:\ser-audit\cache", "--per-class", "2"], EXIT_MODEL,
     expect_msg="incomplete",
     why="缺 config.json 的目录必须被识别为不可用，而不是中途崩在加载阶段")

case("failure", "unknown perturbation family",
     ["sweep", "--conditions", "gaussain_snr:10", "--per-class", "2"], EXIT_USAGE,
     expect_msg="unknown perturbation family",
     why="拼错时必须报错，并且最好给出最接近的合法族名")

case("failure", "non-numeric value for a numeric family",
     ["sweep", "--conditions", "gaussian_snr:loud", "--per-class", "2"], EXIT_USAGE,
     expect_msg="is not a number",
     why="值必须是数字，报错时要指出该族的单位和示例")

case("failure", "condition missing the value",
     ["sweep", "--conditions", "gaussian_snr", "--per-class", "2"], EXIT_USAGE,
     expect_msg="malformed condition",
     why="缺冒号属于用法错误，要给出正确格式")

case("failure", "sweep without conditions",
     ["sweep", "--per-class", "2"], EXIT_USAGE,
     expect_msg="needs --conditions",
     why="漏参数时给出可直接照抄的示例命令")

case("failure", "curve without a range",
     ["curve", "--family", "gaussian_snr", "--per-class", "2"], EXIT_USAGE,
     expect_msg="--from and --to",
     why="curve 缺范围无法定位任何东西，必须拒绝执行而不是默默用默认值")

case("failure", "session that does not exist in the dataset",
     ["probe", "--session", "Session99", "--per-class", "2"], EXIT_DATA,
     expect_msg="session not found",
     why="报错时要列出实际可用的 session，便于立刻改正")

case("failure", "audio at the wrong sample rate",
     ["probe", "--session", FIXTURE.name, "--per-class", "2"], EXIT_DATA,
     expect_msg="wrong sample rate",
     why="模型只在 16 kHz 上训练过。工具必须拒绝，而不是悄悄重采样 —— "
         "悄悄重采样会改变被测量的信号，让审计结论失去意义")


def main() -> int:
    make_bad_samplerate_fixture()
    results = []
    try:
        for c in CASES:
            print(f"  [{c['kind']:8s}] {c['name']}", flush=True)
            r = run(c["args"])
            ok = r["rc"] == c["expect_rc"]
            detail = ""
            if ok and c["check"] is not None:
                try:
                    ok = bool(c["check"](r))
                    if not ok:
                        detail = "exit code was right but the structural check failed"
                except Exception as exc:
                    ok = False
                    detail = f"check raised {type(exc).__name__}: {exc}"
            if ok and c["expect_msg"]:
                ok = c["expect_msg"].lower() in r["stderr"].lower()
                if not ok:
                    detail = f"stderr did not contain {c['expect_msg']!r}"
            if ok and c["expect_rc"] != EXIT_OK and "Traceback" in r["stderr"]:
                ok = False
                detail = "a raw Python traceback leaked to the user"
            r["pass"] = ok
            r["detail"] = detail
            results.append({**c, **{k: r[k] for k in ("cmd", "rc", "pass", "detail", "payload",
                                                      "stdout", "stderr")}})
            print(f"           -> rc={r['rc']} {'PASS' if ok else 'FAIL ' + detail}", flush=True)
    finally:
        shutil.rmtree(FIXTURE, ignore_errors=True)

    n_pass = sum(1 for r in results if r["pass"])
    kinds = {"normal": "正常", "boundary": "边界", "failure": "失败"}
    L = ["# Test cases — audit tool", "",
         f"_Generated {datetime.now().isoformat(timespec='seconds')} by `tools/test_cases.py`._",
         "",
         f"**{n_pass}/{len(results)} passed.** Sample size for the metric cases is "
         f"`--per-class {PER_CLASS}` (32 utterances) so the suite runs in a few minutes; the "
         f"full-scale evidence is in `outputs/full/` (n=1241) and `trust_boundary_report_v2.md`.",
         "",
         "## What the three classes are for", "",
         "| Class | Purpose |", "|---|---|",
         "| normal | the tool runs and returns reproducible numbers |",
         "| boundary | the correct answer is *uncertainty*; the tool must report the boundary "
         "instead of forcing a verdict |",
         "| failure | a bad input must give a clear typed error and a non-zero exit code, "
         "**never a plausible-looking result** |", "",
         "## Exit codes", "",
         "| Code | Meaning |", "|---|---|",
         "| 0 | success |", "| 2 | bad input (arguments, unknown family, malformed condition) |",
         "| 3 | model unusable |", "| 4 | dataset unusable |",
         "| 5 | unexpected defect in the tool |", "",
         "## Results", ""]

    for kind in ("normal", "boundary", "failure"):
        rows = [r for r in results if r["kind"] == kind]
        if not rows:
            continue
        L += [f"### {kinds[kind]} ({sum(1 for r in rows if r['pass'])}/{len(rows)} pass)", "",
              "| Case | Command | Expected | Actual | Result |", "|---|---|---|---|---|"]
        for r in rows:
            L.append(f"| {r['name']} | `{r['cmd']}` | rc={r['expect_rc']}"
                     + (f", stderr contains “{r['expect_msg']}”" if r.get("expect_msg") else "")
                     + f" | rc={r['rc']} | {'PASS' if r['pass'] else 'FAIL — ' + r['detail']} |")
        L.append("")
        L += ["<details><summary>Why each case matters</summary>", ""]
        for r in rows:
            L.append(f"- **{r['name']}** — {r['why']}")
        L += ["", "</details>", ""]

    L += ["## Reproduce", "", "```",
          ".venv\\Scripts\\python.exe tools/test_cases.py",
          "```", "",
          "Each case runs `.venv\\Scripts\\python.exe audit.py <args>` from the repo root with "
          "the proxy environment variables removed (an inherited HTTP proxy makes the model "
          "endpoint unreachable on this machine).", "",
          "## Representative outputs", ""]
    for r in results:
        if r["kind"] == "failure" and r["expect_msg"]:
            L += [f"**{r['name']}** — `{r['cmd']}`", "", "```",
                  r["stderr"].strip()[-700:], "```", ""]

    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text("\n".join(L), encoding="utf-8")
    print(f"\nwrote {DOC}")
    print(f"{n_pass}/{len(results)} passed")
    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
