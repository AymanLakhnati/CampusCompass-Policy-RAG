# CampusCompass

**University policy support with retrieval augmented generation**  
Ayman Lakhnati · MAAI902 NLP and LLMs · Assessment Task 2

[Public source](https://github.com/AymanLakhnati/CampusCompass-Policy-RAG) · [Final evaluation](results/v2/EVALUATION_V2.md) · [Rubric coverage](docs/ASSESSMENT_MAP.md)

CampusCompass retrieves policy evidence, exposes its response decision, and runs actual local FLAN and Qwen models. **Every policy is fictional.** No real student records are included, and the demo must not be used as institutional advice.

## Start the application

Python 3.10+ is sufficient for the default lexical demo. No packages, account or API key are needed.

```powershell
python app.py
```

Open [the local demo](http://127.0.0.1:8765). Keep the terminal running and press `Ctrl+C` to stop. Use `python app.py --port 8770` if the default port is occupied.

```powershell
python app.py --query "How do I appeal a grade?"
python -m unittest discover -s tests -v
node tests/check_web_init.js
```

The interface uses local fonts and assets. The server binds to localhost and suppresses query/access logs. It is an academic prototype, not a hardened public multiuser service.

## What the final revision adds

- **Multiple-policy evidence:** retrieve separately for question facets and retain complete short policy paragraphs, including nearby conditions.
- **Appropriate relevance gates:** neural modes use actual encoder cosine, while lexical modes use token coverage. DEV alone selects operating thresholds.
- **Partial-evidence refusal:** unsupported facets cause abstention, with candidate policies still visible for inspection.
- **Decision trace:** inspect facet coverage, score definitions, component scores, source versions and each processing stage.
- **Policy Explorer:** local full-text search and department filtering across the entire fictional collection.
- **Evidence export:** download the server response as JSON or copy the answer. Export does not append the raw textarea question.
- **Actual model inspection:** raw FLAN/Qwen candidates are separated from accepted evidence and checked per selected source.
- **Stronger boundaries:** corpus schema checks, control-character/length limits, duplicate JSON key and unknown-field rejection, media-type and origin checks. Basic English privacy/credential/injection guards run before model loading.

These are partial controls. Source copying does not prove relevance or semantic correctness; pattern matching does not guarantee privacy or attack resistance.

## Optional neural models

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-ml-pinned.txt
.\.venv\Scripts\python.exe app.py
```

On macOS/Linux use `.venv/bin/python`. For CUDA, install the official PyTorch wheel appropriate to the driver first. The pinned file records tested core packages, not a complete transitive lock. Broader compatibility ranges remain in `requirements-ml.txt`.

Select MiniLM or neural hybrid retrieval, then optionally FLAN or Qwen as the answer engine. First use downloads weights from Hugging Face; later requests use the cache. Allow several GB of RAM and approximately 1.5 GB of checkpoint storage plus runtime files. CPU is supported; the web app selects CUDA when available. Missing models produce an explicit error, not a silent backend substitution.

| Component | Pinned Hugging Face revision | Role |
|---|---|---|
| `sentence-transformers/all-MiniLM-L6-v2` | `c9745ed1d9f207416be6d2e6f8de32d1f16199bf` | 384-dimensional semantic retrieval |
| `google/flan-t5-small` | `0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab` | Encoder–decoder generation baseline |
| `Qwen/Qwen2.5-0.5B-Instruct` | `7ae557604adf67be50417f59c2c2f167def9a775` | Causal instruction-model generation |

BM25, TF-IDF and lexical rank fusion need no downloads. `hybrid` combines BM25 and MiniLM ranks. Whole short policies are retrieval units. No chunking, fine-tuning or trained answerability classifier is claimed. Source verification is deliberately restrictive and can over-refuse.

## Measured improvements and remaining errors

The original benchmark contains 30 policies and 106 questions: 37 DEV and 69 original TEST. The original test was already observed, so final-revision results on those questions are **regression**, not untouched validation. A separate evaluation agent froze 40 new audit questions before V2 results and withheld their wording from the implementation engineer. This is still internal project evaluation, not external independent validation.

| Dense MiniLM regression measure | V1 | Final V2 |
|---|---:|---:|
| Macro relevant-policy Recall@3 | 98.41% | 98.41% |
| Correct answerability decisions | 47/69 (68.12%) | 56/69 (81.16%) |
| Answerable requests falsely refused | 20/63 | 12/63 |
| Unsupported requests falsely accepted | 2/6 | 1/6 |
| Accepted response cites all gold policies | 40/63 | 48/63 |

The harder fresh audit reaches 87.5% dense Recall@3 and 25/40 (62.5%) decision accuracy. Five of 12 unsupported requests are accepted and ten of 28 answerable requests are refused. Complete gold evidence remains 13/28 from V1 to V2. Lexical modes also have regressions. The full comparison preserves these failures rather than claiming an across-the-board improvement.

Both local language models actually ran on all 40 audit questions. Of 23 requests reaching generation, Qwen accepted two responses and FLAN three. Both Qwen responses cite all gold policies; only one FLAN response does. Neither accepted an unsupported request in this small set, but overall coverage is just 5% and 7.5%. Acceptance, source membership and policy completeness are not semantic answer accuracy.

All original evidence files are preserved and hash-checked. The original timing anomaly remains documented. No fair CPU-versus-GPU speed comparison or production readiness claim is made.

## Reproduce safely

```powershell
python scripts/audit_results.py
python scripts/audit_v2.py
python scripts/evaluate_v2.py --stage initialize --output results/reproduction
python scripts/evaluate_v2.py --stage baseline --output results/reproduction
python scripts/evaluate_v2.py --stage calibrate --output results/reproduction
python scripts/evaluate_v2.py --stage evaluate --output results/reproduction
python scripts/evaluate_v2.py --stage summarize --output results/reproduction
```

Initialization requires a new empty directory and copies the recorded protocol. All five modes run by default and need optional neural dependencies. For lexical-only runs, pass `--modes bm25 tfidf lexical_hybrid` consistently. Recorded reference predictions cannot be overwritten. The app loads final thresholds from `results/v2/frozen_config.json`.

```powershell
python scripts/run_llm_v2.py --backend flan --device cpu --mode dense --results-dir results/reproduction
python scripts/run_llm_v2.py --backend qwen --device cuda --mode dense --results-dir results/reproduction
```

Use `--device cpu` when CUDA is unavailable. Follow [reproduction notes](docs/REPRODUCTION.md) for the original implementation at its pinned commit. Running the current engine on old questions does not reproduce the original engine.

## Deliverables and structure

The final local package includes the black-and-white, double-spaced Word/PDF paper, editable PowerPoint, demonstration guide, executed notebook, dataset and raw model evidence. The separate editable [Canva design](https://canva.link/cqf7cwk9ydh5jrq) provides a creative presentation version. Canva and native PowerPoint are separate artifacts; the downloadable PowerPoint is checked directly against the measured evidence.

| Location | Purpose |
|---|---|
| `app.py`, `src/campuscompass/` | HTTP/CLI, final engine, actual model adapters and offline UI |
| `engine_v1.py`, `llm_v1.py` in the source package | Original implementation snapshots |
| `data/` | Fictional policies, original questions, new frozen audit and data card |
| `results/v2/` | Versioned settings, raw predictions, metrics and verification receipts |
| `docs/report.md` | Final paper source and primary references |
| `docs/ASSESSMENT_MAP.md` | Rubric-to-evidence mapping |
| `docs/DEMONSTRATION.md` | Live demonstration and oral-defense guide |
| `notebooks/CampusCompass_Demonstration.ipynb` | Executed final walkthrough |
| `tests/` | Core, HTTP, evaluator and actual web interaction regression checks |

The API is `POST /api/answer` with `query`, `mode`, `backend` and optional `top_k`. `GET /api/health` exposes size/hash, while `GET /api/policies` exposes only the fictional collection. No account, messaging, record-access or approval tools are available to a model.

## Attribution and interpretation

No claims are made about production safety, multilingual fairness, automated policy currency, staff time saved or student satisfaction. A deployment needs approved current sources, independent questions, human oversight and a supervised pilot.

AI assistance contributed to planning, data construction, code, research and writing. The student must review and understand the work and follow the actual course attribution policy. Fictional corpus policies are test data, not submission instructions. Original code/data use MIT; external weights retain upstream licenses. Large weights and credentials are excluded.

Hosted CI has not demonstrated a successful run. Local and fresh-clone checks are reported separately. The [original README](docs/README_v1.md) remains as a V1 historical reference.
