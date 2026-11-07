"""Ask every engine with an API key each prompt in prompts.jsonl and append the raw answers
to logs/YYYY-MM-DD.jsonl. Python standard library only.

    OPENAI_API_KEY=... PERPLEXITY_API_KEY=... GEMINI_API_KEY=... SERPAPI_API_KEY=... python3 run.py
"""
import datetime
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).parent


def chatgpt(prompt, key, model):
    body = {"model": model, "input": prompt, "tools": [{"type": "web_search"}]}
    return "https://api.openai.com/v1/responses", {"Authorization": f"Bearer {key}"}, body


def perplexity(prompt, key, model):
    body = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    return "https://api.perplexity.ai/chat/completions", {"Authorization": f"Bearer {key}"}, body


def gemini(prompt, key, model):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"contents": [{"parts": [{"text": prompt}]}], "tools": [{"google_search": {}}]}
    return url, {"x-goog-api-key": key}, body


def google_ai_mode(prompt, key, model):
    # Google has no API for its AI answers; SerpApi returns the AI Mode answer as JSON.
    query = urllib.parse.urlencode({"engine": "google_ai_mode", "q": prompt, "api_key": key})
    return f"https://serpapi.com/search.json?{query}", {}, None


# name: (request builder, key variable, model variable, default model)
ENGINES = {
    "chatgpt": (chatgpt, "OPENAI_API_KEY", "OPENAI_MODEL", "gpt-5-mini"),
    "perplexity": (perplexity, "PERPLEXITY_API_KEY", "PERPLEXITY_MODEL", "sonar"),
    "gemini": (gemini, "GEMINI_API_KEY", "GEMINI_MODEL", "gemini-flash-latest"),
    "google_ai_mode": (google_ai_mode, "SERPAPI_API_KEY", None, "google_ai_mode"),
}


def ask(url, headers, body):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.load(resp)


def main():
    prompts = [json.loads(line) for line in (ROOT / "prompts.jsonl").read_text().splitlines() if line.strip()]
    engines = [(name, *spec) for name, spec in ENGINES.items() if os.environ.get(spec[1])]
    missing = [spec[1] for spec in ENGINES.values() if not os.environ.get(spec[1])]
    if missing:
        print("skipping engines without a key: " + ", ".join(missing), file=sys.stderr)
    if not engines:
        print("no API keys set, nothing to run", file=sys.stderr)
        return 2

    now = datetime.datetime.now(datetime.timezone.utc)
    out = ROOT / "logs" / f"{now:%Y-%m-%d}.jsonl"
    out.parent.mkdir(exist_ok=True)
    failed = 0
    with out.open("a") as f:
        for name, build, key_var, model_var, default in engines:
            key = os.environ[key_var]
            model = os.environ.get(model_var, default) if model_var else default
            for p in prompts:
                try:
                    raw = ask(*build(p["prompt"], key, model))
                except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
                    failed += 1
                    print(f"{name} {p['id']}: {e}", file=sys.stderr)
                    continue
                rec = {"time": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                       "engine": name, "model": model, "prompt_id": p["id"], "prompt": p["prompt"], "raw": raw}
                # The logs are published, so a key echoed back in a response must never reach them.
                f.write(json.dumps(rec, ensure_ascii=False).replace(key, "[redacted]") + "\n")
                f.flush()
                print(f"{name} {p['id']} ok", file=sys.stderr)
    print(f"wrote {out.relative_to(ROOT)}, {failed} failed", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
