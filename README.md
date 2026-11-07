# AEO visibility log

My personal site sells AEO, so I measure it the way I would measure a client: a frozen set of buyer questions, asked to the AI engines on a schedule, with every raw answer kept. The score is plain: out of N answers, how many name me or my site, per engine.

Anyone can rerun it. The prompts, the code and the answer logs are all here.

## What is in it

- `prompts.jsonl`: 24 questions a buyer might ask, 14 about AEO and 10 about forward-deployed AI engineering. None of them names me. They are frozen: changing one breaks the comparison over time, so new questions get new ids.
- `run.py`: asks each engine every prompt and appends the raw JSON responses to `logs/YYYY-MM-DD.jsonl`. Python standard library only.
- `score.py`: reads the logs and prints n/N per date and engine, with a 95% range (Wilson) and the prompts that named me.
- `test_log.py`: offline check of the runner and scorer on synthetic responses.

## Engines

| Engine | API | Key | Default model |
|---|---|---|---|
| ChatGPT | OpenAI Responses API with web search | `OPENAI_API_KEY` | `gpt-5-mini` (`OPENAI_MODEL`) |
| Perplexity | Sonar API | `PERPLEXITY_API_KEY` | `sonar` (`PERPLEXITY_MODEL`) |
| Gemini | Gemini API with Google Search grounding | `GEMINI_API_KEY` | `gemini-flash-latest` (`GEMINI_MODEL`) |
| Google AI Mode | SerpApi (Google has no API for its AI answers) | `SERPAPI_API_KEY` | - |

The APIs are not the consumer apps. They have no memory or location, and their search settings can differ, so the numbers show direction and are not a copy of what one person sees in the app.

## Run it

```sh
OPENAI_API_KEY=... PERPLEXITY_API_KEY=... GEMINI_API_KEY=... SERPAPI_API_KEY=... python3 run.py
python3 score.py
python3 test_log.py
```

Engines without a key are skipped. One run is 24 calls per engine. I plan to run it once a week. Running it twice on one day adds a second run to that day's file, and then the range is too narrow, because answers to the same question are not independent.

An answer counts when "Himanshu Surana" or "himan2411" appears in the answer text or in a cited source. Search queries and the echoed request are not counted. I add the site's domain to `NAMES` in `score.py` once it is live.

## Results

Not run yet. The site is not live, so the first run will be the baseline. The table from `score.py` goes here after each run.
