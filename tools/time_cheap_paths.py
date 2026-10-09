"""Time the cheap paths: `catalog` and argument validation must not pay for torch."""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "Scripts" / "python.exe"

CASES = [
    (["catalog"], 0),
    (["sweep", "--conditions", "gaussain_snr:10"], 2),
    (["probe", "--model", r"D:\no-such-model-directory"], 3),
    (["probe", "--session", "Session99"], 4),
    (["sweep"], 2),
]

env = dict(os.environ)
for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
    env.pop(name, None)

print(f"  {'command':44s} {'exit':>5s} {'seconds':>8s}   first diagnostic line")
for args, expect in CASES:
    t0 = time.time()
    p = subprocess.run([str(PY), "audit.py", *args], cwd=str(ROOT), env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    el = time.time() - t0
    line = next((l.strip() for l in p.stderr.splitlines()
                 if "ERROR" in l or "exit code" in l), "")
    if args[0] == "catalog" and p.returncode == 0:
        line = "9 families listed"
    flag = "ok " if p.returncode == expect else "BAD"
    print(f"  {' '.join(args):44s} {p.returncode:5d} {el:7.2f}s {flag} {line[:70]}")
