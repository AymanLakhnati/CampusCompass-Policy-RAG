# V2 measured comparison

V1 regression predictions reused byte-for-byte as observations, V2 TEST is regression only. New audit baseline and V2 evaluated at frozen mode-specific thresholds. Latencies are sequential warm local observations, not an isolated benchmark; V1 historical regression latency came from the original session.

| Set | Version / mode | R@3 | Answerable accepted | Unsupported accepted | Gold evidence complete | Median / p95 ms |
|---|---|---:|---:|---:|---:|---:|
| regression | v1 / bm25 | 0.8968 | 45/63 | 4/6 | 39/63 | 0.55 / 0.74 |
| regression | v1 / dense | 0.9841 | 43/63 | 2/6 | 40/63 | 25.55 / 43.72 |
| regression | v1 / hybrid | 0.9762 | 44/63 | 4/6 | 41/63 | 20.31 / 25.66 |
| regression | v1 / lexical_hybrid | 0.9127 | 45/63 | 4/6 | 39/63 | 2.32 / 2.85 |
| regression | v1 / tfidf | 0.9206 | 45/63 | 4/6 | 39/63 | 1.45 / 1.93 |
| audit | v1 / bm25 | 0.8929 | 16/28 | 3/12 | 11/28 | 0.18 / 0.27 |
| audit | v1 / dense | 0.8750 | 17/28 | 5/12 | 13/28 | 13.38 / 23.11 |
| audit | v1 / hybrid | 0.8929 | 18/28 | 6/12 | 14/28 | 10.23 / 13.07 |
| audit | v1 / lexical_hybrid | 0.8929 | 16/28 | 3/12 | 11/28 | 0.75 / 0.83 |
| audit | v1 / tfidf | 0.8929 | 16/28 | 3/12 | 11/28 | 0.66 / 0.74 |
| regression | v2 / bm25 | 0.8968 | 43/63 | 4/6 | 40/63 | 1.02 / 2.44 |
| regression | v2 / dense | 0.9841 | 51/63 | 1/6 | 48/63 | 9.98 / 29.93 |
| regression | v2 / hybrid | 0.9762 | 50/63 | 1/6 | 46/63 | 12.03 / 28.98 |
| regression | v2 / lexical_hybrid | 0.9127 | 43/63 | 4/6 | 40/63 | 1.02 / 2.34 |
| regression | v2 / tfidf | 0.9206 | 43/63 | 4/6 | 40/63 | 0.96 / 2.36 |
| audit | v2 / bm25 | 0.8929 | 13/28 | 3/12 | 11/28 | 1.42 / 3.10 |
| audit | v2 / dense | 0.8750 | 18/28 | 5/12 | 13/28 | 15.31 / 45.71 |
| audit | v2 / hybrid | 0.8929 | 15/28 | 5/12 | 12/28 | 14.71 / 42.53 |
| audit | v2 / lexical_hybrid | 0.8929 | 13/28 | 3/12 | 11/28 | 1.23 / 2.66 |
| audit | v2 / tfidf | 0.8929 | 12/28 | 3/12 | 10/28 | 1.40 / 3.01 |

The audit contains 40 newly written project-authored questions, including 28 supported and 12 unsupported requests. Its wording was withheld from the implementation engineer until V2 freeze. It is not externally independent, and its author knew V1 failures. The reused TEST set cannot validate generalization after engineering informed by V1 results. No settings may be changed based on audit scores and still be described as evaluated on an untouched audit.

Gold evidence complete means an accepted response cites every annotated required policy. It does not prove every condition was interpreted correctly. Unsupported acceptance, false refusal, complete evidence and source membership are separate measures. Bootstrap intervals and category diagnostics are in metrics_v2.json.
