# Measure real package-download throughput through several indexes so we can pick a fast one.
# Downloads the same small package from each index with a clean cache and no dependencies.
import subprocess, sys, tempfile, time, os, shutil

PY = sys.executable
TARGET = "numpy==2.2.4"

INDEXES = [
    ("tuna-tsinghua", "https://pypi.tuna.tsinghua.edu.cn/simple"),
    ("aliyun", "https://mirrors.aliyun.com/pypi/simple"),
    ("tencent", "https://mirrors.cloud.tencent.com/pypi/simple"),
    ("ustc", "https://pypi.mirrors.ustc.edu.cn/simple"),
    ("pypi-direct", "https://pypi.org/simple"),
]

for name, index in INDEXES:
    tmp = tempfile.mkdtemp(prefix="pipdl-")
    env = dict(os.environ)
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        env.pop(k, None)
    start = time.time()
    proc = subprocess.run(
        [PY, "-m", "pip", "download", "--no-deps", "--no-cache-dir",
         "--index-url", index, "-d", tmp, TARGET],
        capture_output=True, text=True, env=env, timeout=600,
    )
    dt = time.time() - start
    size = sum(
        os.path.getsize(os.path.join(root, f))
        for root, _, files in os.walk(tmp) for f in files
    )
    if proc.returncode == 0 and size:
        print(f"  {name:14s} OK   {dt:6.1f}s  {size/1024/1024:6.1f}MB  {size/dt/1024:7.0f} KB/s")
    else:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or ["?"]
        print(f"  {name:14s} FAIL {dt:6.1f}s  {tail[0][:80]}")
    shutil.rmtree(tmp, ignore_errors=True)
