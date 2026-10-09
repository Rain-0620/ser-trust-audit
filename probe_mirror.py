import os, sys, socket, time, urllib.request

# Short timeouts: we want a fast yes/no, not a retry storm.
socket.setdefaulttimeout(12)

def strip_proxy():
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY", "no_proxy"):
        os.environ.pop(k, None)

def keep_proxy():
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        os.environ[k] = "http://127.0.0.1:2106"

HOSTS = {
    "hf-mirror": "https://hf-mirror.com/superb/wav2vec2-base-superb-er/resolve/main/preprocessor_config.json",
    "modelscope": "https://www.modelscope.cn/api/v1/models",
    "hf-official": "https://huggingface.co/superb/wav2vec2-base-superb-er/resolve/main/preprocessor_config.json",
}

def probe(label, url, mode):
    if mode == "direct":
        strip_proxy()
    else:
        keep_proxy()
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "probe/1.0"})
        with urllib.request.urlopen(req) as r:
            body = r.read(300)
        print(f"  {label:22s} {mode:7s} OK   {time.time()-t0:5.1f}s {r.status} {len(body)}B  {body[:60]!r}")
        return True
    except Exception as e:
        print(f"  {label:22s} {mode:7s} FAIL {time.time()-t0:5.1f}s {type(e).__name__}: {str(e)[:90]}")
        return False

for name, url in HOSTS.items():
    probe(name, url, "direct")
    probe(name, url, "proxy")
