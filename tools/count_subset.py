"""Count the four-class IEMOCAP subset so we can size the experiment budget."""
import collections
import pathlib
import re

ROOT = pathlib.Path(r"D:\ser-audit\data\IEMOCAP")
MAP = {"ang": "angry", "exc": "happy", "hap": "happy", "sad": "sad", "neu": "neutral"}
LINE = re.compile(r"^\[[\d.]+\s*-\s*[\d.]+\]\s+(\S+)\s+(\S+)\s+\[")

grand = collections.Counter()
per_session = collections.defaultdict(collections.Counter)
total = 0
missing_wav = 0

for session in sorted(ROOT.glob("Session*")):
    for label_file in (session / "dialog" / "EmoEvaluation").glob("Ses*.txt"):
        for line in label_file.read_text(encoding="utf-8", errors="replace").splitlines():
            m = LINE.match(line)
            if not m:
                continue
            total += 1
            cls = MAP.get(m.group(2))
            if not cls:
                continue
            utt = m.group(1)
            wav = session / "sentences" / "wav" / utt.rsplit("_", 1)[0] / f"{utt}.wav"
            if wav.exists():
                per_session[session.name][cls] += 1
                grand[cls] += 1
            else:
                missing_wav += 1

print(f"total labelled utterances in corpus : {total}")
print(f"4-class utterances with audio       : {sum(grand.values())}")
print(f"4-class labels without audio file   : {missing_wav}")
print()
print("per session:")
for name in sorted(per_session):
    row = per_session[name]
    parts = "  ".join(f"{k}={row[k]:5d}" for k in ("angry", "happy", "sad", "neutral"))
    print(f"  {name}: {parts}   sum={sum(row.values())}")
print()
print("overall 4-class distribution:")
for k, v in sorted(grand.items()):
    print(f"  {k:9s} {v:6d}")
