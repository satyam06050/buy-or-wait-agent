# Stage 8 — Packaging findings

## Implemented

- Expanded `README.md` with:
  - the Stage 1 recurrence rule and cited event/user examples;
  - exact currency-coverage findings and cited event IDs;
  - Stage 0/5 unresolved edge cases and conservative handling;
  - live and offline rerun commands;
  - test and packaging commands;
  - explicit secret/cache/dataset exclusion guidance.
- Added `code/evaluation/usage_report.md` with usage numbers drawn from the logged full offline validation run and the metadata-only provider call log.
- The report separates:
  - 250 deterministic offline explanation slots in the final full run;
  - one failed DeepSeek text-extraction attempt in that run;
  - 16 successful Gemini image resolutions that populated the cache;
  - failed provider attempts with unknown token usage.
- Pricing references use the current official Gemini and DeepSeek pricing pages; no unsupported `deepseek-chat` price is guessed because the provider was unavailable and the current page no longer lists that model.

## Full-run evidence

- Final full-run metadata: `/tmp/stage8-final-call_log.jsonl`.
- Records: 251 (250 explanation slots plus one text-extraction failure).
- Final output: 250 rows, deterministic serialized validation passed; SHA-256 `8ae76a60dd11bab148fd65d3a67c79b1e2b9f3591c267e2c7e8db7cbf9cd2ef3`.
- Remote cache-population metadata: `evaluation/call_log.jsonl`, 24 records; 16 successful Gemini responses, 5 Gemini HTTP 429 failures, and 3 DeepSeek HTTP 402 failures.
- Successful Gemini usage: 10,009 input tokens, 957 output tokens, 10,966 total tokens.

## Package gate

The final `code.zip` will be built from a temporary staging directory containing the runnable `code/` tree, `README.md`, and a root-level `evaluation/usage_report.md`. It will exclude `.env`, API keys, dataset inputs, caches, bytecode, provider logs, and the chat transcript. The root `output.csv` and `log.txt` remain separate submission artifacts.
