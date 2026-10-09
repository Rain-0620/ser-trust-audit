import os, urllib.request, json, sys

TARGETS = [
    ("hf-config", "https://huggingface.co/superb/wav2vec2-base-superb-er/resolve/main/preprocessor_config.json"),
    ("hf-model", "https://huggingface.co/superb/wav2vec2-base-superb-er/resolve/main/config.json"),
    ("mirror-config", "https://hf-mirror.com/superb/wav2vec2-base-superb-er/resolve/main/preprocessor_config.json"),
    ("mirror-model", "https://hf-mirror.com/superb/wav2vec2-base-superb-er/resolve/main/config.json"),
]

def probe(label, url, strip_proxy):
    saved = {k: os.environ.get(k) for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "HF_ENDPOINT")}
    if strip_proxy:
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            os.environ.pop(k, None)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "python-probe/1.0"})
        with urllib.request.urlopen(req, timeout=45) as r:
            body = r.read(600)
            print(f"  {label:14s} status={r.status} len={len(body)} ct={r.headers.get('content-type')}")
            print(f"     head={body[:200]!r}")
    except Exception as e:
        print(f"  {label:14s} FAIL {type(e).__name__}: {str(e)[:150]}")
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

print(f"proxies visible to urllib: {urllib.request.getproxies()}")
print("\n-- direct (proxy env removed) --")
for name, url in TARGETS:
    probe(name, url, True)
print("\n-- via mirror endpoint --")
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
probe("mirror-endpoint", TARGETS[3][1], False)
