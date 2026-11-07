"""Offline check of run.py and score.py. Every response here is synthetic, shaped like each
engine's documented JSON; none of it is real engine output. Run: python3 test_log.py"""
import io
import json
import os
import pathlib
import tempfile
import urllib.request

import run
import score

# Synthetic responses, one per engine, each naming me only in its sources.
SYNTHETIC = {
    "chatgpt": {"output": [
        {"type": "web_search_call", "action": {"query": "Himanshu Surana"}},
        {"type": "message", "content": [{"type": "output_text", "text": "Try these consultants.",
            "annotations": [{"type": "url_citation", "url": "https://github.com/himan2411", "title": "GitHub"}]}]}]},
    "perplexity": {"choices": [{"message": {"content": "A few options [1]."}}],
                   "search_results": [{"title": "Himanshu Surana - AEO", "url": "https://example.org"}]},
    "gemini": {"candidates": [{"content": {"parts": [{"text": "Consider an AEO specialist."}]},
                               "groundingMetadata": {"webSearchQueries": ["himanshu surana"],
                                                     "groundingChunks": [{"web": {"title": "Himanshu Surana"}}]}}]},
    "google_ai_mode": {"search_parameters": {"q": "x"},
                       "text_blocks": [{"type": "list", "list": [{"snippet": "Himanshu Surana runs audits."}]}],
                       "references": []},
}


def without_sources(engine, raw):
    raw = json.loads(json.dumps(raw))
    if engine == "chatgpt":
        raw["output"][1]["content"][0]["annotations"] = []
    elif engine == "perplexity":
        raw["search_results"] = []
    elif engine == "gemini":
        raw["candidates"][0]["groundingMetadata"]["groundingChunks"] = []
    else:
        raw["text_blocks"] = []
    return raw


def test_mentions():
    for engine, raw in SYNTHETIC.items():
        assert score.mentions(engine, raw), engine
        # Search queries and echoed request metadata must not count as a mention.
        assert not score.mentions(engine, without_sources(engine, raw)), engine


def test_wilson():
    lo, hi = score.wilson(0, 24)
    assert lo == 0 and 0.13 < hi < 0.15, hi
    lo, hi = score.wilson(12, 24)
    assert 0.31 < lo < 0.33 and 0.67 < hi < 0.69, (lo, hi)


def test_run_then_score():
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        (root / "prompts.jsonl").write_text('{"id": "p1", "prompt": "Who does AEO?"}\n')
        seen = []

        def fake_urlopen(req, timeout):
            seen.append(req.full_url)
            engine = next(e for e, host in [("chatgpt", "openai"), ("perplexity", "perplexity"),
                                            ("gemini", "googleapis"), ("google_ai_mode", "serpapi")]
                          if host in req.full_url)
            raw = dict(SYNTHETIC[engine], echo="key-" + engine)  # an echoed key must be redacted
            return io.BytesIO(json.dumps(raw).encode())

        keys = {spec[1]: "key-" + name for name, spec in run.ENGINES.items()}
        old = run.ROOT, urllib.request.urlopen, {k: os.environ.get(k) for k in keys}
        run.ROOT, urllib.request.urlopen = root, fake_urlopen
        os.environ.update(keys)
        try:
            assert run.main() == 0
        finally:
            run.ROOT, urllib.request.urlopen = old[0], old[1]
            for k, v in old[2].items():
                os.environ.pop(k) if v is None else os.environ.__setitem__(k, v)

        assert len(seen) == 4
        [log] = (root / "logs").glob("*.jsonl")
        text = log.read_text()
        assert "key-" not in text and text.count("[redacted]") == 4
        rows = score.score([log])
        assert sorted(e for _, e in rows) == sorted(run.ENGINES)
        assert all(r[:2] == [1, 1] for r in rows.values())


if __name__ == "__main__":
    test_mentions()
    test_wilson()
    test_run_then_score()
    print("ok")
