import os, sys, shutil
from pathlib import Path

# Try to force every HTTP client to bypass any proxy, then download one small file
# through huggingface_hub itself. Compare against explicit hf-mirror use.
def attempt(label, env_overrides, endpoint=None):
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "NO_PROXY", "no_proxy", "HF_ENDPOINT"):
        os.environ.pop(k, None)
    os.environ.update(env_overrides)
    if endpoint:
        os.environ["HF_ENDPOINT"] = endpoint

    import importlib
    import huggingface_hub
    importlib.reload(huggingface_hub)
    from huggingface_hub import hf_hub_download

    cache = Path("D:/ser-audit/.hfprobe") / label
    cache.mkdir(parents=True, exist_ok=True)
    try:
        path = hf_hub_download(
            repo_id="superb/wav2vec2-base-superb-er",
            filename="preprocessor_config.json",
            cache_dir=str(cache),
        )
        size = os.path.getsize(path)
        print(f"  {label:22s} OK   {size} bytes")
        if size:
            print(f"      {open(path, encoding='utf-8').read()[:80]!r}")
    except Exception as e:
        print(f"  {label:22s} FAIL {type(e).__name__}: {str(e)[:160]}")


print("huggingface_hub", __import__("huggingface_hub").__version__)
print(f"env proxies seen: {__import__('urllib.request', fromlist=['x']).getproxies()}")

attempt("noproxy-star", {"no_proxy": "*", "NO_PROXY": "*"})
attempt("mirror-noproxy", {"no_proxy": "*", "NO_PROXY": "*"}, endpoint="https://hf-mirror.com")
