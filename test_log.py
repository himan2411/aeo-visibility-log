"""Offline check of run.py and score.py. Every response here is synthetic, shaped like each
engine's documented JSON; none of it is real engine output. Run: python3 test_log.py"""
import http.client
import io
import json
import os
import pathlib
import tempfile
from unittest import mock

import run
import score

# Synthetic responses, one per engine, each naming me only in its sources. Search queries
# and the echoed request name me too, to prove they are not counted.
SYNTHETIC = {
    "chatgpt": {"output": [
        {"type": "web_search_call", "action": {"query": "Himanshu Surana"}},
        {"type": "message", "content": [{"type": "output_text", "text": "Try these consultants.",
            "annotations": [{"type": "url_citation", "url": "https://github.com/himan2411", "title": "GitHub"}]}]}]},
    "perplexity": {"choices": [{"message": {"content": "A few options [1]."}}],
                   "search_results": [{"title": "Himanshu Surana - AEO", "url": "https://example.org"}]},
    # Gemini cites only the source domain as the title, behind a redirect link.
    "gemini": {"candidates": [{"content": {"parts": [{"text": "Consider an AEO specialist."}]},
                               "groundingMetadata": {"webSearchQueries": ["himanshu surana"], "groundingChunks": [
                                   {"web": {"title": "himan2411.github.io",
                                            "uri": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/x"}}]}}]},
    "google_ai_mode": {"search_parameters": {"q": "Himanshu Surana"},
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


def perplexity_says(text):
    return {"choices": [{"message": {"content": text}}]}


def test_mentions():
    for engine, raw in SYNTHETIC.items():
        assert score.mentions(engine, raw), engine
        assert not score.mentions(engine, without_sources(engine, raw)), engine
    for text in ["Himanshu\nSurana", "Himanshu Surana", "Himanshu  Surana", "linkedin.com/in/himanshu-surana"]:
        assert score.mentions("perplexity", perplexity_says(text)), text


def test_wilson():
    lo, hi = score.wilson(0, 24)
    assert lo < 1e-9 and 0.13 < hi < 0.15, hi
    lo, hi = score.wilson(12, 24)
    assert 0.31 < lo < 0.33 and 0.67 < hi < 0.69, (lo, hi)


def test_run_then_score():
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        (root / "prompts.jsonl").write_text('{"id": "p1", "prompt": "Who does AEO?"}\n'
                                            '{"id": "p2", "prompt": "Who does FDE?"}\n')
        seen = []

        def fake_urlopen(req, timeout):
            seen.append(req.full_url)
            if len(seen) == 1:  # the first call drops the connection; the run must go on
                raise http.client.RemoteDisconnected("Remote end closed connection without response")
            engine = next(e for e, host in [("chatgpt", "openai"), ("perplexity", "perplexity"),
                                            ("gemini", "googleapis"), ("google_ai_mode", "serpapi")]
                          if host in req.full_url)
            raw = dict(SYNTHETIC[engine], echo="key-" + engine)  # an echoed key must be redacted
            return io.BytesIO(json.dumps(raw).encode())

        keys = {spec[1]: "key-" + name for name, spec in run.ENGINES.items()}
        with mock.patch.dict(os.environ, keys), mock.patch.object(run, "ROOT", root), \
                mock.patch("urllib.request.urlopen", fake_urlopen):
            assert run.main() == 1  # one failed call

        assert len(seen) == 8
        [log] = (root / "logs").glob("*.jsonl")
        text = log.read_text()
        assert "key-" not in text and text.count("[redacted]") == 7

        # A blocked Gemini answer is a non-answer: out of N, counted on its own.
        with log.open("a") as f:
            f.write(json.dumps({"engine": "gemini", "prompt_id": "p3",
                                "raw": {"candidates": [{"finishReason": "SAFETY"}]}}) + "\n")
        rows = {e: r for (_, e), r in score.score([log]).items()}
        assert rows["chatgpt"] == [1, 1, ["p2"], 0], rows["chatgpt"]
        assert rows["gemini"] == [2, 2, ["p1", "p2"], 1], rows["gemini"]
        assert rows["perplexity"][:2] == rows["google_ai_mode"][:2] == [2, 2]

        # A broken log line names its file and line.
        with log.open("a") as f:
            f.write("{not json\n")
        try:
            score.score([log])
            raise AssertionError("bad line not reported")
        except SystemExit as e:
            assert f"{log}:9:" in str(e), e


if __name__ == "__main__":
    test_mentions()
    test_wilson()
    test_run_then_score()
    print("ok")
