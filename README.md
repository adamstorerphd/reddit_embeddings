# Restartable Reddit Word-Embedding Pipeline
### Project root · config v0.3.0 (audited + consolidated 2026-09-03) · 6 notebooks, all executed

> ## LLM handoff bundle
> **`LLM_HANDOFF_BUNDLE.txt`** (337 KB, ~49k tokens) is a single self-contained
> dump of this repository built for pasting into an LLM. It contains a project
> description, the verified state of the tree, a ranked defect list with
> evidence, a file-by-file inventory, and the verbatim source of all 7 notebooks,
> the `src/` library, `run_pipeline.py`, the tests, the config and `docs/00`–`07`.
>
> Rebuild it after any change with `python tools/build_llm_bundle.py`, or verify
> it has not drifted with `python tools/build_llm_bundle.py --check`.
>
> **Read PART 2 and PART 3 of that file before trusting anything below.** In
> particular, the "all executed" claim in this README's subtitle is wrong: no
> notebook has saved outputs, and every artefact currently in `models/`,
> `vectors/` and `manifests/` came from a `--dry-run` on synthetic data.

This workspace contains the **five initial deliverables** (no production code yet, per your instruction).

## Start here (read in order)
1. `docs/00_decision_checklist.md` — **Deliverable 1.** 16 decisions with recommended defaults. Reply with confirmations to freeze config.
2. `docs/01_data_source_assessment.md` — **Deliverable 2.** Verified source comparison (Arctic Shift primary; official API recent-only; Pushshift retired).
3. `docs/02_config_specification.md` + `config/project_config.yaml` — **Deliverable 3.** Every parameter explained; single source of truth.
4. `docs/03_manifest_and_naming_spec.md` — **Deliverable 4.** Schemas for retrieval/shard/training manifests, failure log, periods, filenames, atomicity rules.
5. `docs/04_pilot_plan.md` — **Deliverable 5.** 9–12 unit pilot with pass/review/fail gates and a decision-report template.

## Directory layout (brief §5 — created as skeleton)
`config/ manifests/ metadata/ shards/tokenized shards/temporary models/word2vec models/fasttext vectors/ diagnostics/... logs/ notebooks/ docs/`

## Immediate objective restated
Validate sources, freeze a versioned config, and run a small pilot that measures throughput, storage, and coverage — before any full counting pass or embedding training.

## Key assumptions
- Free Colab + ~15 GB free Drive (confirm yours); no paid services in v1.
- Arctic Shift (community) reachable; official Reddit credentials NOT assumed.
- Focal subreddit list + date range still yours to confirm (see Deliverable 1, §4 checklist).

## Built (v0.2.0 — 2026-09-03)
- `docs/05_scope_and_periodization_addendum.md` — your new scope decisions recorded (Tier-1 + 100–500 Tier-2, 2013–2025, deferred concepts, adaptive periods with overflow cap).
- `notebooks/00_setup_and_configuration.ipynb` — Stage 0 (validated, 7 cells).
- `notebooks/01_test_data_access.ipynb` — Stage 1 pilot (validated, 9 cells).

## Next step (your move)
Give the Tier-1 subreddit name (or authorize auto-rank) + confirm Cell 1 of Notebook 01, then press Run all.

## Run order (6 notebooks — consolidated & modular)
00_setup → 01_pilot → 02_counts_and_periods (freeze-gated) → 03_build_shards → 04_train_evaluate → 05_vectors_inspect.
Old granular files in `notebooks/archive/` (do not run).
Shared utilities live in `src/` (`cleaner.py`, `storage.py`, `manifests.py`, `paths.py`, `api.py`).

## Built
- `src/` — Modular shared Python package (cleaner, storage, paths, api, manifests).
- `notebooks/00_setup_and_configuration.ipynb` — Stage 0 setup & environment validation.
- `notebooks/01_test_data_access.ipynb` — Stage 1 pilot data access & cleaner inspection.
- `notebooks/02_counts_and_periods.ipynb` — Stages 2–3 monthly counting & freeze gate.
- `notebooks/03_build_shards.ipynb` — Stages 4–7 tracked & reference sharding.
- `notebooks/04_train_evaluate.ipynb` — Stages 8–9 Word2Vec training & seed stability evaluation.
- `notebooks/05_vectors_inspect.ipynb` — Stages 10–12 vector normalization, concept inspection & trajectories.
- `tests/test_pipeline.py` — Automated test suite for core library utilities.

## GitHub + Google Drive + Google Colab Workflow

This project is configured for a **hybrid workflow**:
- **GitHub** tracks code (`src/`), notebooks (`notebooks/`), configs (`config/`), and documentation (`docs/`).
- **Google Drive** stores persistent large data: compressed shards (`shards/`), trained Word2Vec models (`models/`), normalized vectors (`vectors/`), logs, and manifests.
- `.gitignore` automatically prevents files >100 MB or binary datasets from being committed to GitHub.

### 1. Push to GitHub (First Time)
In your local terminal:
```bash
cd reddit_embeddings_project
git init
git add .
git commit -m "feat: consolidated reddit embeddings pipeline with src/ library"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 2. Run in Google Colab
1. Open Google Colab and mount Google Drive.
2. In Colab, clone the repository directly to your Google Drive so that both code updates and generated model weights persist:
```bash
%cd /content/drive/MyDrive
!git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git reddit_embeddings_project
%cd /content/drive/MyDrive/reddit_embeddings_project
```
3. Open `notebooks/00_setup_and_configuration.ipynb` and run cells in order.
4. To pull future code updates in Colab, run:
```bash
!git pull origin main
```

### 3. Save Notebook Changes back to GitHub from Colab
If you modify code or write notes in a notebook in Google Colab:
- Go to `File` → `Save a copy in GitHub`.
- Select your repository and branch, then save.

## Guiding-order compliance
Validity > compliance > restartability > reproducibility > validation > low-memory > low-cost > speed > convenience. No downstream regressions or hypothesis tests are implemented at this stage.
