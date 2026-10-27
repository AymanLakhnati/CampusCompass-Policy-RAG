# Reproduction and evidence versions

## Original study

The original measured implementation is preserved at Git commit
`e8806e539d46603c724aa4a0238927862f174986`.
Use a separate checkout to reproduce that implementation:

```powershell
git clone --no-checkout https://github.com/AymanLakhnati/CampusCompass-Policy-RAG.git CampusCompass-v1
cd CampusCompass-v1
git checkout --detach e8806e539d46603c724aa4a0238927862f174986
python -m unittest discover -s tests -v
python scripts/evaluate.py --modes bm25 tfidf lexical_hybrid --output results/rerun_original
```

Install the optional neural requirements before rerunning dense retrieval or
generation. Never reset an existing checkout or overwrite an evidence folder
to create a clean run. A new checkout keeps reference evidence separate.

## Revised prototype

The final revision improves evidence selection, multiple-policy responses and
request handling. Its measurements are stored separately under `results/v2/`.
The original test questions were already observed during the first study;
retesting those questions measures regression, not untouched generalization.
A separately authored audit set has its own freeze record and limitations.
Read the final evaluation protocol before running those scripts.

Pretrained model revisions are pinned in the model adapters. The optional
`requirements-ml-pinned.txt` records tested core library versions, while
`requirements-ml.txt` provides broader compatibility ranges. Neither file
claims bitwise reproducibility across different hardware or library builds.

The Git attributes preserve exact dataset and result bytes across operating
systems, allowing the stored SHA256 values to remain meaningful. Corpus hashes,
question hashes and frozen configuration accompany the measurements. Raw model
generations, rejected candidates and source excerpts remain inspectable.

## Default application

The lexical application uses only the Python standard library and runs without
an API key. Neural models are optional and require additional packages and
first-use model downloads. No real student records are included. The server
binds to localhost and must not be exposed as a public institutional service.
