# Final internal audit — 26 October 2026

This is an engineering review by the project's evaluation agent, not an independent external validation or security certification. It checks delivered code and recorded evidence. It does not run a new TEST experiment or claim real-university accuracy.

## Evaluation evidence

- `python scripts/audit_results.py` passes nine groups of consistency checks. It recomputes every saved summary value for five retrieval modes and two challenge runs from per-query files. Corpus/benchmark SHA-256 values match frozen configuration, all original TEST runs contain 69 TEST records, and saved thresholds match the reported operating points. `results/audit_checks.json` records checks and prediction-file hashes.
- Lexical thresholds are 0.35; dense and neural hybrid thresholds are 0.30. Application startup loads those mode-specific frozen values. The low-level `PolicyIndex` constructor retains the original 0.22 default for callers constructing an index directly; it does not automatically mean the caller is using the evaluated configuration. The evaluator and LLM experiment explicitly apply frozen thresholds.
- The initial p95 calculation used floor rounding. This can select the lower value for a category containing two observations and place p95 below the median. The final implementation uses empirical nearest rank: `sorted(values)[ceil(0.95*n)-1]`. A regression test covers two observations, one observation, 69 observations, empty input and invalid probability. All lexical, neural and challenge aggregate files were rebuilt from **saved predictions only**; no inference, threshold selection or prediction record changed. The correction is also recorded in `results/EVALUATION.md`.
- Full-model result files each contain the original 69 TEST IDs with matching relevance and answerability labels. Both use BM25 at 0.35 and attempt generation on 49 cases. FLAN accepts 28 with 26 gold-policy citations; Qwen accepts nine with nine gold-policy citations. Counts, coverage, mean generation times and normalized source-substring acceptance checks recompute exactly from the saved outputs. These are acceptance and citation-membership statistics, not verified answer accuracy. Earlier 12-case smoke files are separate exploratory evidence.
- Retrieval comparisons retain one response builder and question set. The generator comparison retains BM25 context and threshold. CPU FLAN and GPU Qwen timings are not a fair speed comparison; model loading and inference are separately recorded. Extreme observed wall-clock times are retained rather than replaced by guessed performance.

## Code and HTTP review

The app binds to loopback, suppresses request logging, bounds request bytes and question length, validates modes/backends, rejects cross-origin browser requests and renders policy content through `textContent`. Optional model failure is visible rather than silently substituting another backend. Models use pinned revisions. Optional generator inference is serialized to limit duplicate loading and resource contention.

The audit identified three HTTP-boundary defects, corrected by the prototype agent: non-object JSON caused a server error instead of a validation error; boolean `top_k` passed integer validation; and `top_k` was ignored by the language-model adapter. A Windows connection reset during cross-origin rejection was resolved by draining the bounded request body before returning the rejection. Real HTTP tests cover ordinary answers and citations, health, invalid mode/query/body/top_k and cross-origin rejection.

The audit also identified a critical browser initialization error: the script called the `$` DOM helper before its `const` declaration, which would abort script execution. The prototype agent moved the declaration before its first use and added a dependency-free Node VM initialization regression check. API tests alone cannot establish that browser event handlers work.

## Verification record

- `.venv/Scripts/python.exe -m unittest discover -s llm_project/tests -v`: **18 tests passed** after HTTP fixes, including seven evaluator tests, seven engine tests and four real HTTP tests. These tests do not download or execute neural models. Actual neural/model execution evidence comes from the preserved experiment files, not from these unit tests.
- `python llm_project/scripts/audit_results.py`: **nine consistency groups passed**, with no model loading or TEST inference.
- `node llm_project/tests/check_web_init.js`: **passed** after the helper-order fix. The actual embedded script initializes against a stub DOM and installs both submit and backend-change handlers without runtime exceptions. This is an initialization check, not a visual-browser or accessibility audit.

## Remaining limitations

The high dense Recall@3 of 0.9841 does not remove the weak lexical overlap answerability gate. Dense still rejects 20 answerable TEST questions and accepts two unsupported questions. Privacy requests may receive an irrelevant public policy excerpt; no real confidential data exists in this corpus, but that is not robust privacy-intent handling. Single-policy extraction and generation cannot produce complete two-policy answers. Exact source matching can accept a copied phrase that does not answer the question. `verify_citations` checks identifier presence, not entailment.

All policy content and queries are authored synthetic examples. Six unsupported TEST cases are too few for a safety estimate; both explicit initial injection prompts landed in DEV. The 18-question challenge was authored after seeing TEST failures, is explicitly exploratory, and includes simulated quoted instruction attacks rather than actual poisoned retrieved documents. English-only retrieval and regex PII screening do not establish multilingual fairness or full de-identification. No independent human ratings or user study were conducted. Local concurrent neural request load, deployment authentication, official document governance and institutional integrations are outside this demonstration's validation.

The delivered evidence supports a reproducible educational prototype with documented failure modes. It does not support autonomous real-world administrative advice.
