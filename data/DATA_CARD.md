# CampusCompass demonstration data card

**All institutions, rules, dates, amounts, and scenarios in this directory are fictional.** CampusCompass has no affiliation with any real university. These rules are not advice about the user's university. The files contain no scraped institutional documents, student records, or human-subject research. The only email is an intentionally non-routable `example.invalid` placeholder.

## Scope and provenance

The project authors created 30 English policy passages spanning registrar services, finance, housing, library, IT, accessibility, wellbeing, laboratories, ethics, transport, dining, and complaints. A passage is a complete retrieval unit; retaining conditions and exceptions is more appropriate than splitting these short texts into arbitrary token windows. `scripts/build_dataset.py` is the original source and deterministically recreates both JSONL files. Version 1.0 uses a fictional effective date of 2026-09-01. The default research-data retention and other policy choices are design examples, not claims about law or best practice.

`policies.jsonl` fields: `id` (stable P01–P30), `title`, `department`, `version`, `effective_date` (ISO date), `text`. No website URLs are invented. A citation resolves to a local policy and its version.

`evaluation.jsonl` fields: `id`, `split`, `query`, `relevant_ids`, `answerable`, `category`, `expected_terms`. There are **106 queries: 37 development and 69 test**. Development contains 30 single-policy positives, six unanswerable items, and one two-policy item. Test contains 60 rephrased single-policy positives, six unanswerable items, and three two-policy items, one including an email placeholder. Unanswerable questions include unknown institutional facts, credential disclosure, private records, and prompt injection. A policy about resetting a password does not make a request for an actual Wi-Fi password answerable.

Gold relevant IDs designate the minimum policies intended to support the requested answer. A two-policy query requires both policies for complete retrieval; reporting any-hit alone would overstate success. `expected_terms` are broad topic facets shared across paraphrases, **not exact reference answers**; their string-match rate is a diagnostic only and is not a correctness score.

## Splitting and freezing

Policies are available to all retrieval modes. Splits separate question wording rather than policies, because this is a closed-corpus retrieval task. Development questions select only the refusal threshold using balanced answerability accuracy. The lexical alias list, retriever choices, and corpus are engineering decisions, not learned supervised models. Test wording is fixed in the checked-in JSONL. The evaluator saves corpus/benchmark SHA-256 hashes and all chosen thresholds to `frozen_config.json` before any test inference. It then evaluates each mode once and saves every prediction. Existing results require an explicit overwrite flag or a fresh output directory.

The same project authors wrote the corpus, development questions, and test questions. **This is not a blind, independent benchmark**, and shared vocabulary makes it easier than authentic campus queries. No test set was supplied by an instructor, no students were recruited, and no user study was conducted. Any later changes motivated by observed failures require a new untouched validation sample before claiming improved generalization.

## Evaluation and limitations

Macro Recall@1/3 averages the proportion of gold policies found for answerable queries; Hit@1/3 measures at least one; Complete@3 requires all; MRR@3 rewards the first relevant policy. Negative queries have no gold retrieval target and are excluded from these retrieval denominators. Answerability measures acceptance of supported queries and rejection of unsupported or unsafe requests. Report both subgroup rates because there are only six test negatives.

Citation precision checks gold policy membership, and citation coverage checks the proportion of required policies cited. Verbatim support checks whether each returned sentence occurs in a cited source. This narrow mechanical check can be perfect while an answer is incomplete or irrelevant; it is not semantic entailment. The optional generative LLM has separate risks and is **not evaluated by the extractive-answer metrics**. There is no valid exact-match answer-accuracy claim in this benchmark.

Query-level bootstrap intervals use seed 42 and 2,000 resamples. Small, correlated, authored samples do not support population-wide confidence claims. Timings are sequential local wall-clock measurements after warmup, not production throughput or an SLA. The corpus lacks multilingual wording, OCR errors, policy conflicts, malicious retrieved documents, realistic slang, and current official contact information. The basic PII regex is not full de-identification. Operational deployment would require licensed official policies, document ownership, version governance, real stakeholder testing, privacy review, and a separately authored evaluation set.

## Exploratory challenge supplement

`challenge.jsonl` contains 18 further diagnostic prompts, authored **after** the original TEST results were inspected. It includes direct instruction attacks, quoted malicious instructions, authority impersonation, attempted exfiltration, private-record and credential requests, overlapping out-of-domain queries, French, Arabic, mixed Darija, and multi-policy questions. It has 11 unanswerable and seven answerable cases. `scripts/challenge.py` loads frozen thresholds without tuning and preserves per-query results. A quoted malicious note in a query simulates one aspect of indirect injection; no retrieved policy was poisoned, so it cannot establish resistance to actual document-based attacks. This is exploratory failure analysis, not an independent benchmark or an improvement-validation set.

## Rights and maintenance

These are original synthetic project assets; distribute with the repository's license. Do not present them as real institutional rules. Amend policy versions and benchmark hashes together when factual content changes; retain historical results. Deleted or superseded policies should not silently remain authoritative.
