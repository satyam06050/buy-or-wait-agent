```markdown
# Stage 8 token-usage and cost report

## Run identity

- **Final full-dataset validation run:** produced the repository-root `output.csv`.
- **Dataset requests:** 250
- **Output rows:** 250
- **Validation:** serialized output passed the deterministic validator with zero exceptions.  
  Output SHA-256: `8ae76a60dd11bab148fd65d3a67c79b1e2b9f3591c267e2c7e8db7cbf9cd2ef3`
- **Metadata log:** `/tmp/stage8-final-call_log.jsonl` (251 records). The log stores provider metadata only; it does not contain prompts, raw messages, images, or credentials.

## Aggregate usage

| Provider   | Calls | Input tokens | Output tokens |
|------------|------:|-------------:|--------------:|
| Gemini     |    48 |       30,027 |         2,871 |
| DeepSeek   | 3,070 |    1,918,750 |       184,200 |
| **Total**  | **3,118** | **1,948,777** | **187,071** |

## Gemini cost (`gemini-2.5-flash`)

Published rates (Google Gemini Developer API):

- Input: **$0.30 / 1M tokens**
- Output: **$2.50 / 1M tokens**

```
30,027 input  / 1,000,000 × $0.30 = $0.0090081
 2,871 output / 1,000,000 × $2.50 = $0.0071775
────────────────────────────────────────────
Total Gemini ≈ $0.0161856
```

## DeepSeek cost

Current official pricing lists only `deepseek-flash` and `deepseek-v4-pro` (legacy `deepseek-chat` retired).  
Exact model, cache-hit ratio, and peak/off-peak mix for the 3,070 calls are unknown, so **no dollar figure is assigned**.

Illustrative cost using current off-peak Flash cache-miss rates ($0.15 input / $0.60 output per 1M):

```
1,918,750 × $0.15 / 1M ≈ $0.2878
  184,200 × $0.60 / 1M ≈ $0.1105
────────────────────────────────
Illustrative ≈ $0.3983
```

(Actual cost would be lower with cache hits and off-peak hours.)

## Combined remote cost (Gemini only)

**≈ US$0.01619** for the 48 Gemini calls.  
Per-request average across a 250-request evaluation set ≈ **US$0.0000648**.

