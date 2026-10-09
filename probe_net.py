import os, sys, time, urllib.request

URLS = [
    ("pytorch", "https://download.pytorch.org/whl/cu124/torch-2.6.0%2Bcu124-cp312-cp312-win_amd64.whl"),
    ("pypi", "https://pypi.org/simple/numpy/"),
]

def fetch(url, limit=2_000_000, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "probe/1.0"})
    start = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        total = 0
        while total < limit:
            chunk = r.read(65536)
            if not chunk:
                break
            total += len(chunk)
    return time.time() - start, total

def run(label, keep_proxy):
    saved = {k: os.environ.get(k) for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")}
    if not keep_proxy:
        for k in saved:
            os.environ.pop(k, None)
    for name, url in URLS:
        try:
            dt, n = fetch(url)
            rate = n / dt / 1024 if dt else 0
            print(f"  {label:10s} {name:8s} OK   {dt:5.1f}s  {n/1024:7.0f}KB  {rate:7.0f} KB/s")
        except Exception as e:
            print(f"  {label:10s} {name:8s} FAIL {type(e).__name__}: {str(e)[:70]}")
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

print("download throughput probe (2MB per target)")
run("with-proxy", True)
run("direct", False)
