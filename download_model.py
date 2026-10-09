"""Download a Hugging Face model into a local directory using urllib only.

huggingface_hub's HTTP stack (httpx + the optional hf_xet backend) fails on this machine:
the local proxy answers CONNECT with 502, and Xet transfers come back empty. Plain urllib
through the same proxy works, so we fetch the files ourselves and load the model from disk.

    python download_model.py superb/wav2vec2-base-superb-er
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

MIRRORS = ["https://hf-mirror.com", "https://huggingface.co"]
SKIP_SUFFIXES = (".gitattributes",)
CHUNK = 1 << 20


def api_files(repo_id: str, endpoint: str) -> list[str]:
    url = f"{endpoint}/api/models/{repo_id}"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "dl/1.0"}), timeout=30) as r:
        info = json.loads(r.read())
    return [s["rfilename"] for s in info.get("siblings", [])]


def download(url: str, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "dl/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as fh:
        total = int(r.headers.get("content-length") or 0)
        got = 0
        last = time.time()
        while True:
            chunk = r.read(CHUNK)
            if not chunk:
                break
            fh.write(chunk)
            got += len(chunk)
            if time.time() - last > 2:
                pct = f"{got * 100 // total:3d}%" if total else "  ?"
                print(f"      {pct}  {got / 1048576:7.1f} MB  {got / (time.time() - start) / 1024:6.0f} KB/s")
                last = time.time()
    if total and tmp.stat().st_size != total:
        tmp.unlink(missing_ok=True)
        raise IOError(f"size mismatch: expected {total}, got {got}")
    tmp.replace(dest)
    return got


def main() -> int:
    repo_id = sys.argv[1] if len(sys.argv) > 1 else "superb/wav2vec2-base-superb-er"
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("models") / repo_id.split("/")[-1]
    target.mkdir(parents=True, exist_ok=True)

    listing = None
    for endpoint in MIRRORS:
        try:
            listing = api_files(repo_id, endpoint)
            print(f"file list from {endpoint}: {len(listing)} entries")
            break
        except Exception as e:
            print(f"  {endpoint} listing failed: {type(e).__name__}: {str(e)[:100]}")

    names = [n for n in (listing or ["config.json", "preprocessor_config.json", "model.safetensors"])
             if not n.endswith(SKIP_SUFFIXES) and "/" not in n]
    print(f"target directory: {target.resolve()}")

    for name in names:
        dest = target / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"  {name:28s} already present ({dest.stat().st_size / 1048576:.1f} MB)")
            continue
        global start
        for endpoint in MIRRORS:
            url = f"{endpoint}/{repo_id}/resolve/main/{name}"
            start = time.time()
            try:
                print(f"  {name:28s} GET {endpoint}")
                size = download(url, dest)
                print(f"  {name:28s} OK  {size / 1048576:.1f} MB in {time.time() - start:.0f}s")
                break
            except Exception as e:
                print(f"  {name:28s} FAIL {type(e).__name__}: {str(e)[:110]}")
        else:
            print(f"  {name:28s} ALL MIRRORS FAILED")
            return 1
    return 0


if __name__ == "__main__":
    start = time.time()
    raise SystemExit(main())
