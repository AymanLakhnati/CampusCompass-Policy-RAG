# V2 internal audit — 26 October 2026

This is a project engineering audit, not an external certification or a human answer-quality study. The evaluator authored the original data and knew the V1 failures. The historical audit is preserved in `AUDIT_V1.md`. V1 measured source is available at commit `e8806e539d46603c724aa4a0238927862f174986` and in the preserved V1 source modules.

## Evaluation design and frozen evidence

The 40-question audit was written and hashed before V2 outputs were seen and was withheld from the implementation engineer until the engine froze. It has 28 supported questions, including eight requiring two policies, and 12 unsupported requests. It includes conditions, false premises, missing operational facts, French/Arabic, privacy/credential requests and instruction attacks. Its hash is `f4e5f0c738ad71f5d5cfe0e7b2f077e6b05bb9f0b2b61168a58e26c1a3fc28c2`; the early timestamp and source snapshot hash are in `results/v2/audit_freeze.json`. This is a fresh engineering-blind project audit, **not independently authored external validation**.

V2 settings use only the existing 37 DEV questions. Candidate thresholds span 0.20–0.60 in 0.025 steps. Selection maximizes balanced answerability accuracy, then unsupported rejection, complete gold evidence, and lower threshold. Threshold-zero DEV observations permit pass/refusal simulation because threshold changes do not change facets, ranking or the source selected for a facet; if every facet passes, selected citations are unchanged. Selected values are 0.35 for lexical modes and 0.425 for dense/hybrid actual cosine. These are selected operating points, not calibrated probabilities.

The configuration records corpus, benchmark, audit, V2 source and inherited V1 source hashes. The inherited-source hash was appended during final reproducibility review and matches the pre-V2 snapshot exactly; no settings, source or predictions changed. All 27 original V1 evidence files, including raw full-model generations, remain byte-identical under `v1_evidence_manifest.json`. Prior TEST questions were already inspected during V1 work; their V2 reuse measures regression and cannot validate untouched generalization. V1 TEST observations were reused rather than rerun. Fresh audit baseline and V2 observations are separately stored.

## Measured findings

| Dense response measure | V1 reused TEST | V2 reused TEST | V1 fresh audit | V2 fresh audit |
|---|---:|---:|---:|---:|
| Supported questions accepted | 43/63 | 51/63 | 17/28 | 18/28 |
| Unsupported questions accepted | 2/6 | 1/6 | 5/12 | 5/12 |
| Complete required-policy citations | 40/63 | 48/63 | 13/28 | 13/28 |
| Answerability accuracy | 47/69 | 56/69 | 24/40 | 25/40 |
| Raw-query macro Recall@3 | 0.9841 | 0.9841 | 0.8750 | 0.8750 |

The revision improves the reused regression set. The fresh audit does **not** establish improved evidence completeness or unsupported-request rejection. Five unsupported dense-audit requests receive public excerpts: private counselling notes, bank IBAN, a real emergency telephone number, guaranteed visa outcome, and a live shuttle cancellation. Nothing confidential is present to disclose, but accepting these requests is still an answerability failure. A public excerpt stating a limitation can be informative without answering the requested unavailable fact; the gold labels require refusal for the missing fact.

Facet splitting also loses shared context. A request combining library borrowing and a group study room can retrieve club classroom rules for its second fragment. A comparison involving two policies may remain one facet and cite only one. French and Arabic questions are refused, and some valid compound single-policy questions are over-split. These are recorded failures, not silently repaired against the audit.

Full 40-case actual Qwen and FLAN audit experiments use dense retrieval at 0.425 and CUDA. Each attempts generation on 23 questions. Qwen accepts two (5% total coverage), both with all gold-policy citations; FLAN accepts three (7.5%), only one with all gold-policy citations. Neither accepts an unsupported audit question, but Qwen refuses 26/28 supported questions and FLAN 25/28. This is strong over-refusal, not evidence of useful overall accuracy. Every source candidate, rejection, canonical copied phrase and timing is saved. Exact source membership checks copying; **it cannot prove entailment, relevance, correct interpretation or full answer coverage**.

`results/v2/EVALUATION_V2.md` and `metrics_v2.json` report all five modes, category breakdowns, query-bootstrap intervals and timings. Raw query top-three retrieval is separated from facet-expanded response evidence. Gold evidence complete means an accepted response cites all annotated required policies; it does not mean a human verified its answer. Intervals from a small authored sample are not population guarantees. Timings are warm local observations; historical V1 regression timings and concurrent CPU/GPU conditions do not establish a fair speed improvement or a production SLA.

## Code, API and security review

V2 validates library queries, modes, integer `top_k`, control characters and the exact six-field corpus schema; it rejects malformed dates, empty/duplicate documents and oversized passages. Neural decisions use actual encoder cosine rather than a lexical-overlap veto. Sources include version/effective-date metadata, full paragraphs preserving exceptions, selected and unselected candidates, decision traces and explicit confidence definitions. The internal `coverage.complete` flag means all planned facets passed the heuristic; it is distinct from evaluated gold completeness.

The local HTTP boundary rejects invalid JSON shapes, duplicate keys, unsupported content type, invalid modes/backends, oversized questions and boolean `top_k`. The bounded body is drained before cross-origin rejection, avoiding the Windows connection-reset defect seen in V1. Model preflight can refuse sensitive requests before optional model loading. The adapter propagates `top_k`, checks every selected source separately and refuses when any generated phrase fails membership. The service is read-only, binds to loopback and suppresses live query/access logging. Saved raw evaluation questions use synthetic placeholders; they are not live-user logs.

The original frontend helper-order runtime error was corrected. A Node VM regression test executes the embedded script against a stub DOM and checks installed submit/backend handlers. Text is rendered via `textContent`; this initialization test is not a visual-browser or accessibility audit. English intent patterns are partial and the audit demonstrates a private-counselling miss. No actual poisoned retrieved document was tested: quoted malicious query text is only a simulation of one aspect of indirect injection. Loopback and origin checks are not a substitute for authentication, authorization, rate limits or operational hardening in deployment.

## Verification and reproducibility

- Full Python unit/HTTP/evaluation tests: **36 passed**. Tests cover metric denominators, multi-source completeness, source membership, DEV-only calibration, output preservation, fresh-directory initialization, semantic gating, corpus validation and real HTTP errors. Neural unit cases use controlled scores; actual model execution is evidenced separately by saved runs.
- `python scripts/audit_v2.py`: **22 evidence groups pass**. It recomputes labels, all summary values, citation completeness, source membership, chosen settings and timing percentiles; verifies full40 model outputs; and confirms all 27 V1 evidence files are unchanged. Receipt: `results/v2/audit_receipt_v2.json`. This checker performs no retrieval/model inference.
- `node tests/check_web_init.js`: browser-script initialization check. Visual report/deck QA is separate and should be rerun after final artifact builds.
- `scripts/evaluate_v2.py --stage initialize --output results/reproduction` scaffolds an empty reproduction directory. Use that same output for baseline, calibrate, evaluate and summarize stages. Existing prediction/config files are refused rather than overwritten. `run_llm_v2.py --results-dir results/reproduction` supports optional actual local-model replay. Replaying an observed audit is reproducibility, not a new independent study.
- A complete BM25 fresh-directory replay of initialize, baseline, calibrate, evaluate, summarize and the read-only audit was executed successfully in a temporary directory. It reproduced the selected 0.35 threshold and reference decision/retrieval counts; temporary observations were not substituted for the canonical frozen results.
- `results/v2/runtime_environment_v2.json` records Python 3.12.14, PyTorch 2.5.1+cu118, Transformers 4.57.1, CUDA 11.8 and a 4 GB GTX 1650 Ti, plus core tokenizer/hub/safetensors/truststore versions. SentencePiece is absent; installed fast tokenizers successfully executed the pinned revisions. `requirements-ml-pinned.txt` is a tested core-version list, not a full transitive lock or a guarantee of bitwise outputs on other hardware.

## Assessment readiness and remaining limits

`ASSESSMENT_MAP.md` maps every rubric weight and deliverable to inspectable artifacts and reviewer actions. The final report must remain within the specified 3,000–4,000 words; its final build receipt, PDF visual inspection, presentation notes, executable notebook and hosted repository link form separate delivery checks. This audit verifies evidence and engineering consistency, not grading outcomes.

No real institutional documents, student records, independent human ratings or user-study outcomes are claimed. No finetuning occurred: pretrained encoders/models and DEV threshold selection are documented accurately. All policies are fictional. Official-source governance, human escalation, calibrated answerability, context-preserving query planning, multilingual validation, actual poisoned-document tests and independent semantic correctness review remain necessary before operational deployment. Any change informed by this audit requires a new version and a fresh validation sample before another untouched-audit claim.
