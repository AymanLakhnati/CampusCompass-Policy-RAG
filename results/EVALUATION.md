# Measured evaluation and failure analysis

The original fixed benchmark contains 37 DEV and 69 TEST queries. The same authors created the corpus and questions; this is an internal authored benchmark, not blind external validation. All thresholds were selected on DEV before TEST inference. Results below describe deterministic extractive answers, not the optional generative models.

| Mode | DEV threshold | Macro R@1 | Macro R@3 | MRR@3 | Answerability accuracy | Reject unsupported | Median / p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| bm25 | 0.35 | 0.8016 | 0.8968 | 0.8598 | 0.6812 | 0.3333 | 0.55 / 0.74 |
| tfidf | 0.35 | 0.8016 | 0.9206 | 0.8677 | 0.6812 | 0.3333 | 1.45 / 1.93 |
| lexical_hybrid | 0.35 | 0.8016 | 0.9127 | 0.8651 | 0.6812 | 0.3333 | 2.32 / 2.85 |
| dense | 0.30 | 0.8810 | 0.9841 | 0.9392 | 0.6812 | 0.6667 | 25.55 / 43.72 |
| hybrid | 0.30 | 0.8651 | 0.9762 | 0.9339 | 0.6667 | 0.3333 | 20.31 / 25.66 |

Recall averages the proportion of required policies retrieved over 63 answerable TEST queries. Multi-policy examples therefore receive partial credit. MRR uses the first relevant item within three results. Refusal is assessed on all 69 TEST queries, including only six unsupported cases; this small negative sample is a substantial limitation. Latency is warm, local, sequential wall-clock inference, including redaction, retrieval and extraction; it excludes model loading and is not an isolated production load test. P95 uses nearest-rank rounding. Bootstrap percentile intervals and category breakdowns are in each metrics JSON.

## What worked

The pinned MiniLM dense encoder retrieves more semantically rephrased rules than the lexical baselines in this authored sample. Dense Recall@3 is 0.9841 versus BM25 0.8968. Reciprocal-rank hybrid fusion reaches 0.9762 and does not outperform dense retrieval here. There is no statistical or production superiority claim. All returned extractive sentences pass the mechanical source-membership check by construction. This demonstrates traceability, not answer correctness.

## What failed

- **The refusal heuristic is weak.** Dense retrieval still refuses 20 of 63 answerable TEST questions, and incorrectly accepts two of six unsupported requests. Hybrid refuses 19 answerable questions and incorrectly accepts four unsupported requests. Token overlap is not a calibrated probability; high retrieval recall does not solve answerability.
- **Public excerpts can look like answers to unsupported questions.** BM25 accepts a request for a current president and returns a library excerpt because of incidental lexical overlap. A visa-guarantee question matches a grant policy containing “guaranteed approval.” Both are errors even though the quoted text is authentic.
- **Privacy intent is not adequately classified.** Requests for private grades or an actual authentication code can receive public privacy/reset-policy excerpts. No real secret is exposed because none exists in the corpus, but marking these as answered is misleading and unacceptable for deployment.
- **Single-document extraction cannot complete multi-policy answers.** The engine can retrieve both club event approval and room reservation policies but cites only the first. A correct retrieval set therefore does not guarantee complete response coverage.
- **Paraphrase and numerical language expose lexical fragility.** Examples include “week seven” versus “week 8,” “diagnosis” versus “diagnostic details,” and “four missed classes” versus “fourth unexcused absence.” Neural retrieval helps ranking, while the unchanged lexical refusal gate may still reject them.

No gate or retriever was tuned after these TEST results. Promising next work is a separately trained and calibrated answerability model, intent-based handling of private-record requests, complete multi-source evidence selection, and independently authored multilingual/poisoned-document tests. These are future work, not implemented benefits.

## Exploratory challenge supplement

An additional 18-question challenge suite was authored after inspecting the original TEST results. It is diagnostic, uses the frozen mode-specific thresholds without tuning, and cannot validate an improvement. It includes 11 unsupported requests and seven answerable queries, including French, Arabic, mixed Darija, and multi-policy requests. Quoted malicious instructions simulate one aspect of indirect injection; the retrieved corpus itself was not poisoned.

| Challenge mode | R@3 on seven positives | Answerability accuracy | False accepts / 11 | False refusals / 7 |
|---|---:|---:|---:|---:|
| bm25 | 0.7143 | 0.6111 | 3 | 4 |
| hybrid | 0.8571 | 0.6111 | 3 | 4 |

Review every case in `results/challenge/predictions_*.jsonl`; aggregate rates on tiny mixed categories should not be read as safety certification.

## Audit correction

The initial evaluator used floor rounding for p95, which can select the lower observation in a two-item category. The final evaluator uses the empirical nearest-rank convention `sorted[ceil(0.95*n)-1]`. Lexical, neural and challenge summaries were rebuilt from the original saved per-query latencies. No TEST inference was repeated, no threshold changed, and no prediction record was altered.
