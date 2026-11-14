# Evaluation results

Corpus: one 6-page document, 10 questions (8 answerable, 2 not in the docs). One run per config.
The model ignores temperature, so a re-run can differ a little.

| Config | Chunk size | Retries | Chunks stored | Retrieval hit | Answer correct | Out-of-scope correct | Avg latency | Avg retries (in-docs) | Errors |
|---|---|---|---|---|---|---|---|---|---|
| c500_retry_on | 500 | 2 | 12 | 8/8 (100%) | 8/8 (100%) | 2/2 (100%) | 15.3s | 0.00 | 0 |
| c1000_retry_on | 1000 | 2 | 6 | 8/8 (100%) | 8/8 (100%) | 2/2 (100%) | 14.1s | 0.00 | 0 |
| c500_retry_off | 500 | 0 | 12 | 8/8 (100%) | 8/8 (100%) | 2/2 (100%) | 11.1s | 0.00 | 0 |
| c1000_retry_off | 1000 | 0 | 6 | 8/8 (100%) | 8/8 (100%) | 2/2 (100%) | 12.8s | 0.00 | 0 |
