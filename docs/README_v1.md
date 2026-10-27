# CampusCompass

### University policy support with local retrieval augmented generation

MAAI902 NLP and LLMs • Assessment Task 2 • Ayman Lakhnati

[Public source repository](https://github.com/AymanLakhnati/CampusCompass-Policy-RAG)

CampusCompass is an executable research prototype that retrieves university
policies, exposes its evidence, and offers either verbatim extraction or an
actual local language model. **Every policy is fictional.** This project is
not affiliated with a university service and must not be used for real deadlines,
eligibility, fees, emergencies, or student records.

## Start the demo

Python 3.10+ is sufficient for the complete default application. No API key,
account, paid service, or installation is required for lexical retrieval.

```powershell
python app.py
```

Open [the local demo](http://127.0.0.1:8765). Keep the terminal running.
Choose a question, inspect the answer and source, then compare the retrieval
methods and optional answer engines. `Ctrl+C` stops the server.

Local verification passes 18 Python tests, the web initialization regression,
and nine saved-results consistency groups. The hosted workflow did not start;
no hosted CI pass is claimed.

```powershell
python app.py --query "How do I appeal a grade?"
python -m unittest discover -s tests -v
```

If the port is occupied, run `python app.py --port 8766` and use that port.
The server binds to `127.0.0.1`, suppresses access/query logs, and renders answers
as text. It is a local academic demo, not a hardened multiuser service.

## Actual neural models

Install optional dependencies in a dedicated environment. The baseline remains
available if model loading fails; the app reports model errors explicitly.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-ml.txt
.\.venv\Scripts\python.exe app.py
```

On macOS/Linux use `.venv/bin/python` instead. For GPU inference, install the
appropriate official PyTorch build for your driver before the other packages.
Select **Neural** or **Hybrid** retrieval for MiniLM; select **FLAN** or **Qwen**
as the answer engine to run actual generation. First use downloads model weights
from Hugging Face. Subsequent use reuses the local cache. Approximate checkpoint
storage is 90 MB for MiniLM, 310 MB for FLAN and 1 GB for Qwen, plus runtime files.
Allow several GB of free RAM; a CUDA GPU is optional. The interface chooses CUDA
when available, whereas the experiment CLI lets you set the device explicitly.

| Component | Pinned Hugging Face revision | Role |
|---|---|---|
| `sentence-transformers/all-MiniLM-L6-v2` | `c9745ed1d9f207416be6d2e6f8de32d1f16199bf` | 384-dimensional semantic retrieval |
| `google/flan-t5-small` | `0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab` | Compact encoder–decoder generation baseline |
| `Qwen/Qwen2.5-0.5B-Instruct` | `7ae557604adf67be50417f59c2c2f167def9a775` | Local instruction-model generation |

BM25 and TF-IDF are distinct lexical baselines. `lexical_hybrid` fuses their
ranks; `hybrid` fuses **BM25 and MiniLM** ranks. No vector database is required
for 30 records. Neural generation copies a phrase from the highest-ranked
policy, then passes an exact-source gate. This intentionally restrictive design
often rejects useful paraphrases, and an accepted phrase can still answer the
wrong question. It is an experiment in evidence control, not unconstrained chat.

## Recorded results

The original authored benchmark has **30 policies and 106 queries**: 37 DEV
and 69 TEST. TEST includes 63 answerable and six unsupported questions.
The same project created the corpus and questions, so this is not independent
or blind external validation. No model was trained on the benchmark.

| Retrieval mode | TEST macro Recall@3 | MRR@3 | Answerability accuracy |
|---|---:|---:|---:|
| BM25 | 89.68% | 85.98% | 68.12% |
| TF-IDF | 92.06% | 86.77% | 68.12% |
| Lexical fusion | 91.27% | 86.51% | 68.12% |
| MiniLM dense | 98.41% | 93.92% | 68.12% |
| BM25 + MiniLM | 97.62% | 93.39% | 66.67% |

These retrieval results score relevant policies, **not final answer accuracy**.
The overlap gate remains weak: dense retrieval rejects 20/63 answerable
questions and falsely accepts 2/6 unsupported questions. Multi-policy answers
are incomplete because the response builder uses one source. Mechanical source
copying passes by construction and does not certify relevance or correctness.

Both actual language models ran on the full 69 TEST cases with BM25 evidence
and the previously DEV-selected threshold 0.35. Of 49 attempted generations,
FLAN accepted 28 responses (26 cited a gold policy), and Qwen accepted nine
(all nine cited a gold policy). These are acceptance and citation counts, not
semantic answer-correctness ratings. A separate 18-question challenge exposes
additional privacy, language and attack limitations. See
[measured findings](results/EVALUATION.md) and the report for failure analysis.

Raw wall-clock timings contain a major pause anomaly. Do not interpret the
recorded mean FLAN latency or Qwen model-loading duration as compute benchmarks.
The timing audit preserves the outlier rather than silently deleting it.

## Reproduce without overwriting reference evidence

```powershell
python scripts/evaluate.py --modes bm25 tfidf lexical_hybrid --output results/rerun_lexical
python scripts/evaluate.py --modes dense hybrid --output results/rerun_neural
python scripts/run_llm_experiment.py --backend flan --device cpu --output results/rerun_flan.json
python scripts/run_llm_experiment.py --backend qwen --device cuda --output results/rerun_qwen.json
python scripts/challenge.py --help
```

Use `--device cpu` for Qwen if CUDA is unavailable. The default LLM CLI uses
the same BM25 context for both models and saves raw generations, decisions,
revision and timing. The original smoke experiments are retained separately
and use a different threshold; do not mix them into the full TEST comparison.
Threshold selection uses DEV only. Existing benchmark directories are protected
against accidental replacement. Never use TEST outcomes to tune a threshold
and continue calling that set an untouched test.

The app loads frozen mode-specific settings from `results/lexical/frozen_config.json`
and `results/neural/frozen_config.json`. The low-level `PolicyIndex` default is
an API convenience, not the recorded operating point; pass the frozen threshold
when comparing results. `scripts/summarize_results.py` rebuilds the readable
evaluation from saved results without rerunning inference.

## Project contents

| Location | Purpose |
|---|---|
| `app.py` | Local web server and JSON/CLI interfaces |
| `src/campuscompass/engine.py` | Redaction, retrieval, abstention and extraction |
| `src/campuscompass/llm.py` | Actual local model generation and verification |
| `src/campuscompass/web.html` | Responsive demonstration interface |
| `data/` | Fictional policies, DEV/TEST labels, exploratory challenges and data card |
| `results/` | Frozen settings, per-query evidence, aggregates and failure analysis |
| `notebooks/CampusCompass_Demonstration.ipynb` | Executed plain-Python walkthrough |
| `docs/report.md` | Full technical report and verified primary references |
| `docs/DEMONSTRATION.md` | Presentation and live demonstration script |
| `docs/ASSESSMENT_MAP.md` | Rubric-to-evidence mapping |
| `tests/` | Meaningful core, HTTP and evaluator regression tests |

The downloadable submission package includes the Word/PDF report, presentation,
source ZIP, demonstration guide, and evidence manifest. Large pretrained model
weights are downloaded from their publishers and are not redistributed here.

## API

`GET /api/health` returns corpus size/hash. `GET /api/policies` returns the
fictional collection. `POST /api/answer` accepts JSON:

```json
{"query":"How do I appeal a grade?","mode":"bm25","backend":"extractive","top_k":3}
```

Valid retrieval modes: `bm25`, `tfidf`, `lexical_hybrid`, `dense`, `hybrid`.
Valid engines: `extractive`, `flan`, `qwen`. A response exposes status,
answer method, citations, ranking, redacted query and heuristic confidence.
No account action, approval, messaging, file mutation or record lookup is
available to a model. The corpus contains no real private records or secrets.

## Responsible interpretation and attribution

The prototype uses English retrieval and does not establish multilingual
fairness, production safety, privacy compliance, student satisfaction or staff
time savings. Basic redaction and attack patterns are incomplete. A real
deployment needs approved current sources, independently authored evaluation,
access controls, calibrated answerability and supervised human review.

AI assistance contributed to planning, data construction, code, research and
writing. The student must review and understand the submission and comply with
the actual course attribution policy. The fictional corpus's own policies are
test data, not instructions governing this submission.

Original project code and fictional data use the MIT license. External model
weights retain upstream licenses. Academic sources and model cards are listed
in the technical report. The project does not claim to train the pretrained
models or reproduce their original research experiments.
