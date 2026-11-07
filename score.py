"""Count, per run date and engine, how many answers name me or my site: n/N with a 95% range.

    python3 score.py            # every file in logs/
    python3 score.py logs/2026-11-07.jsonl

An answer counts when a name below appears in the answer text or in a cited source
(title or URL). The echoed prompt and request metadata are not searched.
"""
import collections
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent
# Add the site's domain here once it is live.
NAMES = ["himanshu surana", "himan2411"]


def answer_part(engine, raw):
    """The part of a raw response that is the answer and its sources."""
    if engine == "chatgpt":
        return [o for o in raw.get("output", []) if o.get("type") == "message"]
    if engine == "perplexity":
        return [raw.get("choices"), raw.get("citations"), raw.get("search_results")]
    if engine == "gemini":
        return [[c.get("content"), c.get("groundingMetadata", {}).get("groundingChunks")]
                for c in raw.get("candidates", [])]
    if engine == "google_ai_mode":
        return [raw.get("text_blocks"), raw.get("references")]
    raise ValueError(f"unknown engine {engine}")


def strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from strings(v)


def mentions(engine, raw):
    text = " ".join(strings(answer_part(engine, raw))).lower()
    return any(n in text for n in NAMES)


# Treats answers as independent. Fine for one run per day, add a design effect (see the site's noise calculator) if days pool repeat runs.
def wilson(n, total, z=1.96):
    if total == 0:
        return 0.0, 1.0
    p = n / total
    d = 1 + z * z / total
    c = (p + z * z / (2 * total)) / d
    h = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / d
    return max(0.0, c - h), min(1.0, c + h)


def score(paths):
    rows = collections.defaultdict(lambda: [0, 0, []])  # (date, engine) -> [n, N, prompt ids]
    for path in paths:
        for line in pathlib.Path(path).read_text().splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            row = rows[(pathlib.Path(path).stem, rec["engine"])]
            row[1] += 1
            if mentions(rec["engine"], rec["raw"]):
                row[0] += 1
                row[2].append(rec["prompt_id"])
    return rows


def main(args):
    paths = args or sorted(str(p) for p in (ROOT / "logs").glob("*.jsonl"))
    if not paths:
        print("no logs yet, run python3 run.py first", file=sys.stderr)
        return 2
    print("| Date | Engine | Answers naming me | 95% range | Prompts |")
    print("|---|---|---|---|---|")
    for (date, engine), (n, total, ids) in sorted(score(paths).items()):
        lo, hi = wilson(n, total)
        print(f"| {date} | {engine} | {n}/{total} | {lo:.0%} to {hi:.0%} | {', '.join(ids) or '-'} |")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
