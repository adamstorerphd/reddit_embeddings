#!/usr/bin/env python3
"""Assemble LLM_HANDOFF_BUNDLE.txt — a single self-contained text file for pasting
into an LLM so it can debug and rewrite this pipeline.

Everything under PART 5 and later is read verbatim from the working tree at build
time, so the bundle can never drift from the code it describes. The narrative
parts (PART 0-4, 12) are hand-written and carry explicit evidence for every claim.

Usage:
    python tools/build_llm_bundle.py            # writes LLM_HANDOFF_BUNDLE.txt
    python tools/build_llm_bundle.py --check    # rebuild and fail if it differs
"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "LLM_HANDOFF_BUNDLE.txt"
W = 96


def rule(char: str = "=") -> str:
    return char * W


def banner(title: str) -> str:
    return f"\n{rule('=')}\n{title}\n{rule('=')}\n"


def part(num: str, title: str) -> str:
    return f"\n\n{rule('=')}\nPART {num} -- {title}\n{rule('=')}\n"


def file_block(path: Path, rel: str, note: str = "", lang_hint: str = "") -> str:
    """Render one repository file verbatim, with a provenance header."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.endswith("\n"):
        text += "\n"
    n_lines = text.count("\n")
    n_bytes = path.stat().st_size
    head = [rule("-"), f"FILE: {rel}", f"BYTES: {n_bytes} | LINES: {n_lines}"]
    if note:
        head.append(f"NOTE: {note}")
    head.append(rule("-"))
    return "\n".join(head) + "\n" + text


def notebook_block(path: Path, rel: str, note: str = "") -> str:
    """Render an .ipynb as readable text: markdown cells raw, code cells numbered."""
    nb = json.loads(path.read_text(encoding="utf-8"))
    cells = nb.get("cells", [])
    n_md = sum(1 for c in cells if c.get("cell_type") == "markdown")
    n_code = sum(1 for c in cells if c.get("cell_type") == "code")
    n_out = sum(1 for c in cells if c.get("cell_type") == "code" and c.get("outputs"))
    head = [
        rule("-"),
        f"FILE: {rel}",
        f"CELLS: {len(cells)} total | {n_md} markdown | {n_code} code | {n_out} code cells with saved outputs",
    ]
    if note:
        head.append(f"NOTE: {note}")
    head.append("NOTE: cell numbers below are the notebook's own 0-based cell indices.")
    head.append(rule("-"))
    out = ["\n".join(head) + "\n"]
    for i, c in enumerate(cells):
        src = "".join(c.get("source", []))
        ctype = c.get("cell_type", "code").upper()
        out.append(f"\n>>>>>> CELL [{i}] {ctype} {'>' * max(0, W - 26 - len(str(i)))}\n")
        out.append(src.rstrip("\n") + "\n")
        # Markdown cells have no outputs by definition; only annotate code cells.
        if c.get("cell_type") == "code":
            outs = c.get("outputs", [])
            if outs:
                out.append(f"\n[saved outputs: {len(outs)} -- present in the .ipynb, not reproduced here]\n")
            else:
                out.append("\n[saved outputs: NONE -- this code cell has never been executed, "
                           "or was saved with outputs cleared]\n")
    return "".join(out)


# =============================================================================
# NARRATIVE
# =============================================================================

PART0 = """
PURPOSE OF THIS FILE
--------------------
This is a single self-contained dump of the repository
`adamstorerphd/reddit_embeddings` (working branch `arena/01a087fa-reddit-embeddings`).
It is meant to be pasted whole into an LLM and used to (a) diagnose why the
pipeline does not yet produce usable embeddings, and (b) write a better version.

Nothing here is summarised by paraphrase. PART 5 onwards is the literal source of
every notebook, library module, config file and spec document in the repository,
read from disk at build time. PART 1-4 is analysis, and every claim in it is
annotated with the command or file that proves it.

HOW TO READ IT
--------------
  PART 1  What the project is trying to do            (read first)
  PART 2  What is actually in the repo right now      (verified state)
  PART 3  Confirmed defects, ranked, with evidence    (the debugging brief)
  PART 4  File-by-file inventory                      (what each file is for)
  PART 5  Notebook sources, verbatim (00 -> 05)
  PART 6  Shared library `src/`, verbatim
  PART 7  CLI runner `run_pipeline.py`, verbatim
  PART 8  Test suite, verbatim
  PART 9  Configuration, verbatim
  PART 10 Design/spec documents `docs/00`-`docs/07`, verbatim
  PART 11 Runtime evidence: manifests, logs, provenance sidecars
  PART 12 What "better" should mean + open questions

WHAT AN ASSISTING LLM SHOULD PRODUCE
------------------------------------
1. A diagnosis: confirm or refute each defect in PART 3, and find any others.
2. A rewritten pipeline. The single most important property is in DEFECT 1 below:
   a dry run must be structurally incapable of writing an artefact that the rest
   of the pipeline reads as real. Today it is fully capable, and it already has.
3. Explicit answers to the open questions in PART 12.
"""

PART1 = """
1.1  THE RESEARCH QUESTION
--------------------------
The owner wants to measure how the *meaning* of academic-career concepts changes
over time in Reddit's academic communities -- diachronic lexical semantic change.
Target concepts are things like precarity, funding, mentoring, publishing,
teaching-load, mental-health vocabulary. The instrument is word embeddings: train
one Word2Vec skip-gram model per (subreddit x time-period), then compare word
senses across periods.

This is a standard Diachronic Word Embedding / semantic-change design (the
SemEval-2020 Task 1 family, and the Antoniak & Mimno 2018 stability literature,
both cited in `docs/06_corpus_size_evidence.md`).

1.2  THE METHOD AS DESIGNED
---------------------------
  Scope      Tier 1 = one complete focal subreddit (still `TBD` in config).
             Tier 2 = 100-500 well-represented subreddits as a reference set.
  Corpus     Comments + submissions (title + selftext concatenated), English-only
             for training, 2013-01-01 to 2025-12-31.
  Source     Arctic Shift community archive API
             (https://arctic-shift.photon-reddit.com/api). No Reddit credentials,
             no paid infrastructure. Pushshift is retired and explicitly excluded.
  Periods    Adaptive. Base unit = 3 months (a quarter); merge forward up to 12
             months until a period clears the token threshold.
  Thresholds min_usable_tokens_per_model = 5,000,000 (solo period model)
             absolute_floor_tokens       = 2,000,000 (below: pooled-only, never forced)
             axis_grade_tokens           = 10,000,000 (fine-grained claims)
             max_train_tokens_per_model  = 20,000,000 (overflow -> hash-cap)
  Model      gensim skip-gram, dim 200, window 5, negative 5, epochs 5,
             min_count 20, max_vocab 200k, subsample 1e-5, alpha 0.025 -> 1e-4.
  Seeds      3 seeds per period (1047, 2048, 9182). Production seed chosen by a
             PRE-SPECIFIED rule (max mean cross-seed neighbour Jaccard, ties to
             lowest seed id) -- never by which seed flatters the hypothesis.
  Cleaning   Meaning-preserving: stopwords and negation kept, URLs/mentions/code
             blocks replaced by placeholder tokens, digits > 4 -> <num>.

1.3  HARD CONSTRAINTS (these drive every design decision)
---------------------------------------------------------
  * Free Google Colab runtime + roughly 15 GB of Google Drive. Sessions die.
  * The design rule is therefore "stream-train-and-discard": fetch a period's
    text into an ephemeral scratch file, train, export vectors, then DELETE the
    raw text. Zero KB of raw Reddit text is retained.
  * Every stage must be restartable and idempotent. Manifest CSVs with SHA256
    checksums are the source of truth; a completed unit with a matching checksum
    is skipped on rerun.
  * GitHub holds code/config/docs/manifests. Google Drive holds shards, model
    binaries, vectors.
  * Privacy: no usernames in shards, no user profiling, no long quotes,
    no redistribution.

1.4  THE STAGES
---------------
  Stage 0  notebook 00  mount Drive, verify deps, create skeleton, validate config
  Stage 1  notebook 01  liveness-probe Arctic Shift, demo the cleaner, pull 3
                        sample weeks as a pilot, write pilot retrieval manifest
  Stage 2  notebook 02  monthly aggregate counts -> token estimates
  Stage 3  notebook 02  freeze `config/period_definitions.csv` (gated by a flag)
  Stage 4  notebook 03  build bounded, deduped, privacy-stripped compressed shards
  Stage 5  notebook 03  build the Tier-2 reference shards by stable-ID hash sampling
  Stage 6  notebook 03  validate shards, quarantine failures
  Stage 7  notebook 04  train one skip-gram per (period x seed), write provenance
  Stage 8  notebook 04  multi-seed stability comparison, pick production seed
  Stage 9  notebook 05  L2-normalise + export `.kv`, concept trajectories, plots
  Stage 10 notebook 05  write concept reports and RUN_SUMMARY.md

Notebook `03_04_stream_train_pipeline.ipynb` is a newer, more compact variant
that fuses Stages 4-8 into one streaming loop (fetch -> train -> export -> purge,
one period at a time, never materialising a full shard set). It is the design the
`run_pipeline.py --stream-train` flag implements. Both variants are included
below because they disagree with each other in ways that matter (see DEFECT 7).
"""

PART2 = """
This is the verified state of the tree, not the state the documentation claims.

2.1  REPOSITORY
---------------
  Remote branch history: a single commit,
    c0b58d3  "Test autonomous Colab push (2026-09-08 14:58:24 UTC)"
  Working tree clean. `main` and the working branch point at the same commit.
  There is no earlier history to diff against, so "what changed recently" cannot
  be recovered from git; the file contents and the log timestamps are the only
  evidence.

2.2  DUPLICATION
----------------
  15 files exist twice, once at the repo root and once under `notebooks/` or
  `docs/`. Verified byte-identical with `diff -q`:
      00_setup_and_configuration.ipynb      == notebooks/00_setup_and_configuration.ipynb
      01_test_data_access.ipynb             == notebooks/01_test_data_access.ipynb
      02_counts_and_periods.ipynb           == notebooks/02_counts_and_periods.ipynb
      03_04_stream_train_pipeline.ipynb     == notebooks/03_04_stream_train_pipeline.ipynb
      03_build_shards.ipynb                 == notebooks/03_build_shards.ipynb
      04_train_evaluate.ipynb               == notebooks/04_train_evaluate.ipynb
      05_vectors_inspect.ipynb              == notebooks/05_vectors_inspect.ipynb
      00_decision_checklist.md              == docs/00_decision_checklist.md
      ... and the remaining 01-07 markdown docs likewise
  Both copies are tracked by git (`git ls-files` lists both sets). They are
  identical *today*. Nothing enforces that they stay identical.

2.3  EXECUTION STATE
--------------------
  README.md, line 2, claims: "6 notebooks, all executed".
  Actual: all 7 notebooks contain ZERO saved outputs. Verified by parsing each
  .ipynb and counting code cells with a non-empty `outputs` list:
      00_setup_and_configuration.ipynb        5 cells (1 md, 4 code)   executed: 0
      01_test_data_access.ipynb               8 cells (1 md, 7 code)   executed: 0
      02_counts_and_periods.ipynb             8 cells (1 md, 7 code)   executed: 0
      03_04_stream_train_pipeline.ipynb       6 cells (1 md, 5 code)   executed: 0
      03_build_shards.ipynb                   8 cells (1 md, 7 code)   executed: 0
      04_train_evaluate.ipynb                 9 cells (1 md, 8 code)   executed: 0
      05_vectors_inspect.ipynb                8 cells (1 md, 7 code)   executed: 0
  So the repository contains no in-repo evidence of any notebook run.

  Seven pipeline-runner logs DO exist under `logs/`, and every one of them
  records `Dry-Run: True`. Example, `logs/pipeline_runner__20260904T220105Z.log`:
      Mode: SUBREDDIT_LIST | Targets (2): ['AskAcademia', 'PhD']
      Dry-Run: True | Auto-Commit: False

2.4  WHAT THE ARTEFACTS CONTAIN
-------------------------------
  `metadata/monthly_counts/*.json` (8 files). Every month in every file has the
  identical count 50000, and the file self-describes as fabricated:
      "counts": {"2019-01": 50000, "2019-02": 50000, ...},
      "median": 25.0, "valid_rate": 0.85,
      "factor_source": "synthetic_estimate",
      "method": "aggregate:dry_run"
  The 50000 is a hard-coded fallback, not a measurement. See
  `run_pipeline.py:316`  ->  `synthetic_counts = {m: 50000 for m in months}`
  and the same pattern in `02_counts_and_periods.ipynb` Cell 3.

  `config/period_definitions.csv` -- 8 frozen period rows, all four subreddits,
  2019 Q1 and Q2. Every single row says:
      est_tokens = 6375000, total_eligible_tokens = 6375000,
      sampled_train_tokens = 6375000, sufficiency = "sufficient",
      method = "aggregate+factors"
  Identical numbers for r/academia (large), r/gradschool, r/PhD (small) and
  r/AskAcademia (medium) -- four communities with wildly different real volumes.
  These are arithmetic on the fabricated 50000/month constant, and the
  `sufficiency = sufficient` gate was passed on that basis.

  `models/word2vec/tracked/*/*.nfo.json` -- 24 provenance sidecars. All 24
  identical in the fields that matter:
      docs_trained = 400, tokens_trained = 5600, vocab_size = 413,
      train_secs ~ 0.02-0.03
  The project's own threshold for a usable model is 5,000,000 tokens
  (`periodization.min_usable_tokens_per_model`). These models were trained on
  5,600 tokens -- 0.11% of the minimum, and 0.088% of the 6,375,000 the frozen
  period file promised.

  `manifests/training_manifest.csv` -- 24 rows, all with `status = complete`.

  `vectors/*.kv` -- 24 files, 336 KB each, 7.9 MB total, all tracked in git.
  Loaded one with gensim 4.4.0 to see what is actually inside:
      vector_size: 200 | vocab: 413
      index_to_key[:13] = ['rewarding','but','easy','not','phd','in',
                           'publication','and','teaching','research','about',
                           'discussion','academic']
      index_to_key[13:] = ['399','398','397', ... ] -- 400 bare integers
      kv.most_similar('research') ->
          [('100', 0.252), ('294', 0.215), ('111', 0.206),
           ('253', 0.202), ('325', 0.183)]
  Thirteen real words and four hundred synthetic integer "words". The nearest
  neighbours of a real word are numbers. These vectors carry no semantic
  information whatsoever, and they are the artefacts most likely to be mistaken
  for results.

  `shards/tokenized/pilot/` -- contains only `.gitkeep`. The 24 shard files that
  `manifests/pilot/retrieval_manifest.csv` claims to have produced are absent.
  Checked all 24 `output_final` paths: 24 of 24 missing from disk. They are
  absolute paths into `/home/user/reddit_embeddings/...` on the machine that ran
  the pipeline, and `shards/tokenized/**/*.jsonl.gz` is gitignored.

  `RUN_SUMMARY.md` says:
      - Models complete: 24
      - Normalized vectors exported: 0
  while `vectors/` holds 24 `.kv` files and the training manifest records a
  `vectors_path` and `vectors_sha256` for all 24. The summary contradicts the
  filesystem.

2.5  WHAT PASSES
----------------
  The project's own test suite was run in a fresh venv (Python 3.11.2,
  pytest 9.1.1, gensim 4.4.0):
      $ .venv/bin/python -m pytest tests/ -v
      tests/test_pipeline.py::test_paths PASSED                        [ 20%]
      tests/test_pipeline.py::test_cleaner PASSED                      [ 40%]
      tests/test_pipeline.py::test_storage_and_gensim_atomic PASSED    [ 60%]
      tests/test_pipeline.py::test_manifests PASSED                    [ 80%]
      tests/test_pipeline.py::test_api PASSED                          [100%]
      ============================== 5 passed in 0.09s ===============================
  So the plumbing genuinely works: path resolution, the cleaner's negation and
  redaction rules, atomic writes with fsync, gensim atomic save with companion
  .npy handling, manifest upsert idempotency, checksum verification. The library
  in `src/` is sound. The failure is not in the utilities -- it is in the
  pipeline's refusal to distinguish a rehearsal from a run.

2.6  CONFIGURATION AND SCOPE ARE STILL UNSET
--------------------------------------------
  `config/project_config.yaml` still has `scope.tier1_complete_subreddit: TBD`.
  `config/subreddit_list.csv` has every row annotated "EXAMPLE ROW -- replace
  with your focal list".
  So the four subreddits that appear in the artefacts (academia, gradschool,
  PhD, AskAcademia) are placeholders, not a research decision. No real scope has
  been frozen yet.
"""

PART3 = """
Ranked by how badly it will hurt. Each defect states the evidence.

======================================================================
DEFECT 1 -- CRITICAL -- Dry-run output is indistinguishable from real output
======================================================================
EVIDENCE
  * `run_pipeline.py:316` synthesises counts: `{m: 50000 for m in months}`.
  * Those counts are written to `metadata/monthly_counts/*.json` with
    `"method": "aggregate:dry_run"` -- but nothing downstream reads `method`.
  * `02_counts_and_periods.ipynb` Cell 5 applies the real sufficiency rule to
    those numbers and writes `sufficiency = sufficient` into
    `config/period_definitions.csv`.
  * `03_04_stream_train_pipeline.ipynb` Cell 3 trains on synthetic documents and
    sets `min_count=E["min_count"] if not DRY_RUN else 1` -- it *relaxes* the
    configured vocabulary floor specifically so the fake data will fit.
  * The resulting sidecar records `docs_trained: 400, tokens_trained: 5600` and
    the manifest records `status: complete`.
RESULT
  24 models and 24 `.kv` vector files exist, are committed to git (7.9 MB), are
  registered as `complete` in `manifests/training_manifest.csv`, and are
  semantically empty. Any future session that runs `05_vectors_inspect.ipynb`
  will happily produce concept-trajectory plots and a "semantic shift" report
  out of 13 real words and 400 integers.
FIX REQUIRED
  A dry run must be unable to reach the production store. Concretely: dry-run
  artefacts go to a separate root (e.g. `dryrun/` or `models/word2vec/_dryrun/`),
  every artefact and manifest row carries `provenance_mode: dry_run | real`,
  `status` becomes `complete_real` vs `complete_dryrun`, and any consumer refuses
  to read a row whose mode does not match the mode it was asked for. A single
  boolean flag that every stage politely ignores is not a guardrail.

======================================================================
DEFECT 2 -- CRITICAL -- The token-sufficiency gate can be passed by a constant
======================================================================
EVIDENCE
  All 8 rows of `config/period_definitions.csv` carry the identical
  `est_tokens = 6375000` across four subreddits of very different real size, and
  all 8 are marked `sufficient`. `docs/06_corpus_size_evidence.md` is a careful,
  well-sourced argument that 5M tokens is the floor -- and the gate then passed
  every period on a number derived from a hard-coded 50000/month.
  There is no assertion anywhere that est_tokens came from a live measurement.
  `docs/02_config_specification.md` states the principle
  ("no notebook hard-codes a consequential choice") but the counting fallback
  violates it.
FIX REQUIRED
  `02_counts_and_periods.ipynb` must hard-fail, not silently estimate, when the
  aggregate endpoint times out and no real count was obtained. A `method` column
  that records `estimate_fallback` must be *enforced* by the freeze gate: rows
  whose method is not a measured aggregate may not be frozen. Note the notebook
  does have an `ALLOW_ESTIMATES` concept mentioned in `docs/07_audit_report.md`
  ("estimates never freeze unless ALLOW_ESTIMATES") -- but no such flag exists in
  the current `02_counts_and_periods.ipynb` Cell 1. That guard was lost.

======================================================================
DEFECT 3 -- HIGH -- The audit report claims a clean tree; the tree is not clean
======================================================================
EVIDENCE
  `docs/07_audit_report.md`, opening paragraph:
      "All test artifacts removed afterwards; manifests reset; workspace is at a
       clean pre-production state."
  Reality: 24 synthetic models, 24 synthetic `.kv` vectors (committed), 8 frozen
  synthetic period rows, a 24-row training manifest and a 24-row pilot manifest
  are all present. They postdate the audit (audit is dated 2026-09-03; the
  artefacts are timestamped 2026-09-04T22:07 UTC in their own sidecars).
  The same report also says notebook sources live in
  `/home/user/build/nb0{2,3,4,5}.py` -- that directory does not exist in this
  sandbox and is not in the repository.
FIX REQUIRED
  Treat the audit report as stale. Either regenerate it from a real run, or mark
  it superseded at the top. Do not let a document assert a property of the tree
  that a script does not check.

======================================================================
DEFECT 4 -- HIGH -- RUN_SUMMARY.md under-reports vectors, for two reasons
======================================================================
EVIDENCE
  `RUN_SUMMARY.md` reports "Normalized vectors exported: 0" while 24 `.kv` files
  exist. Traced to `run_pipeline.py` `run_stage_5()`:
      mp = Path(r["model_path"])
      if not mp.exists():            # .model files are gitignored -> always absent
          continue
      vp = vec_dir / (...)
      if not vp.exists():            # .kv already exists -> block never entered
          ...
          n_norm += 1                # only counted here
  Two independent bugs, both making `n_norm` stay 0:
    (a) rows are skipped when the `.model` is missing even though the `.kv` that
        stage 5 exists to produce is already present;
    (b) `n_norm` counts only *newly created* exports, not the total on disk.
  The manifest rows are therefore never re-verified against the `.kv` files, so a
  corrupt or stale `.kv` would go unnoticed.
FIX REQUIRED
  Stage 5 should report `vectors on disk` and `vectors verified against manifest
  checksum` as separate numbers, and should verify every manifest row's
  `vectors_sha256` rather than only creating missing files.

======================================================================
DEFECT 5 -- HIGH -- A previous session's branch name is hard-coded
======================================================================
EVIDENCE
  `03_04_stream_train_pipeline.ipynb` Cell 3:
      subprocess.run(["git", "push", "origin",
                      "arena/01a06e48-reddit-embeddings"], cwd=ROOT, check=True)
  `run_pipeline.py:106`:
      branch = branch_res.stdout.strip() or "arena/01a06e48-reddit-embeddings"
  `arena/01a06e48-...` is a different Arena session's branch. The current session
  branch is `arena/01a087fa-reddit-embeddings`.
  The repository's only commit is literally titled
  "Test autonomous Colab push (2026-09-08 14:58:24 UTC)", and
  `logs/colab_secret_verification.txt` reads
  "Verified autonomous Colab push at 2026-09-08 14:58:24 UTC" -- so this path has
  actually fired.
FIX REQUIRED
  Never hard-code a branch. Use `git rev-parse --abbrev-ref HEAD` and fail loudly
  if it is empty or detached, rather than falling back to a stale literal. Better:
  push to an explicitly configured remote branch, and make auto-push opt-in and
  visible (it currently defaults to False, which is right, but the fallback
  string is still a landmine).

======================================================================
DEFECT 6 -- MEDIUM -- 15 duplicated files with nothing keeping them in sync
======================================================================
EVIDENCE  See 2.2. Both copies are git-tracked and currently identical.
RISK      The README tells the reader to open `notebooks/00_...ipynb`; the root
          copies invite editing the wrong one. The first edit to either copy
          creates a silent fork.
FIX REQUIRED
  Keep one canonical location (`notebooks/`, `docs/`) and delete the root copies,
  or make the root copies symlinks / add a CI check that diffs them.

======================================================================
DEFECT 7 -- MEDIUM -- Two mutually incompatible stage 4-8 implementations
======================================================================
EVIDENCE
  `03_build_shards.ipynb` + `04_train_evaluate.ipynb` implement
  build-shards-then-train. `03_04_stream_train_pipeline.ipynb` implements
  fetch-train-purge streaming. `README.md` documents only the first pair in its
  "Run order (6 notebooks)" section and never mentions `03_04`. The `nfo.json`
  sidecars and the `.kv` files in the tree were produced by the *streaming*
  path (they exist while `shards/tokenized/` is empty).
  The two paths also differ in the `sampling_rule` string they write and in how
  `min_count` is handled under DRY_RUN.
FIX REQUIRED
  Pick one. If streaming is the answer (it is, given the Colab constraint),
  retire `03_build_shards.ipynb` and `04_train_evaluate.ipynb` to `archive/` and
  update the README run order.

======================================================================
DEFECT 8 -- MEDIUM -- Manifests store machine-absolute paths
======================================================================
EVIDENCE
  Every `output_final`, `model_path` and `vectors_path` in the manifests is
  `/home/user/reddit_embeddings/...`. Checked all 24 pilot rows: 24 of 24 point
  at files that do not exist on this machine.
CONSEQUENCE
  The checksum-verified resume logic cannot work across machines or across a
  Colab remount at a different path. Idempotency -- the project's central
  promise -- silently degrades to "always redo".
FIX REQUIRED
  Store paths relative to the project root and resolve them through
  `src/paths.get_project_root()` at read time.

======================================================================
DEFECT 9 -- MEDIUM -- `src/cleaner.py` asserts at import time
======================================================================
EVIDENCE
  The module ends with a loop of `assert _res == _expected` over `_tests`.
  These currently pass (verified: `tests/test_pipeline.py::test_cleaner PASSED`,
  and importing the module succeeds). But an `assert` at import time means a
  future cleaning-rule change makes `from src.cleaner import ...` raise
  `AssertionError` in every notebook at once, with a message about a test rather
  than about the import. Under `python -O` the asserts silently vanish, so the
  guarantee disappears in exactly the runs where it matters.
FIX REQUIRED
  Move these into `tests/`. Import should have no side effects.

======================================================================
DEFECT 10 -- LOW -- Cosmetic and documentation drift
======================================================================
  * `05_vectors_inspect.ipynb` Cell 7 writes
    `f"# PROJECT RUN SUMMARY ({today}, config v{cfg['config_version']})"`.
    `config_version` is already `"v0.3.0"`, so this renders `config vv0.3.0`.
    `run_pipeline.py:682` gets it right (`config {cfg['config_version']}`).
  * `README.md` documents a 6-notebook run order and omits `03_04`.
  * `README.md` claims "6 notebooks, all executed" (see 2.3).
  * `README.md` still contains first-time `git init` / `git remote add` /
    `YOUR_USERNAME` instructions for a repository that is already on GitHub.
  * `requirements.txt` has no upper bounds and does not pin `gensim`, yet every
    `.nfo.json` records `gensim_version: 4.4.0` as provenance. Unpinned
    dependency + provenance-by-version-string is a reproducibility gap.

======================================================================
WHAT IS *NOT* A DEFECT (checked, and fine)
======================================================================
  * `src/storage.save_gensim_atomic` correctly handles gensim's companion
    `.npy` files via a staging directory and cleans it up in `finally`.
    Covered by `test_storage_and_gensim_atomic` with a mock that emits
    `.vectors.npy` and `.syn1neg.npy`. Verified passing.
  * `src/api.api_get` retries 429/500/502/503 with exponential backoff and
    treats an upstream 422-with-"Timeout" as a retryable timeout. Matches the
    documented Arctic Shift aggregate behaviour in
    `config/source_definitions.yaml`.
  * `src/manifests.upsert_manifest_row` writes tmp -> fsync -> `os.replace`, so
    it is atomic, and is idempotent on the key fields. Verified by test.
  * The cleaner keeps negation (`not`, `never`, `no`) and stopwords, which is
    the correct choice for semantic-change work, and runs markdown stripping
    *before* inserting `<url>`/`<user>` placeholders so the bracket characters
    survive. `docs/07_audit_report.md` bug #2 records this being found and fixed;
    the fix is present in the current source.
"""

PART4_INTRO = """
Every file currently in the working tree, with what it is for and whether to
trust it. Paths are relative to the repository root. "VERDICT" is the assessment
an assisting LLM should carry into a rewrite.
"""

FILE_DESCRIPTIONS = {
    # ---- notebooks ----
    "notebooks/00_setup_and_configuration.ipynb": (
        "Stage 0. Mounts Google Drive under Colab, locates the project root by "
        "searching upward then a bounded depth downward for `config/project_config.yaml`, "
        "pip-installs any missing dependency, creates the ~20-directory skeleton, loads "
        "and prints the config version/SHA, and prints a summary. 5 cells, no user "
        "settings. Re-implements `src/paths.get_project_root` inline instead of importing "
        "it, because the import needs the root first.",
        "Keep. Harmless. Deduplicate the root-finder into `src/paths` once the bootstrap "
        "order is solved."),
    "notebooks/01_test_data_access.ipynb": (
        "Stage 1 pilot. One editable settings cell (PILOT_MODE, PILOT_SUBS, PILOT_WEEKS, "
        "MAX_RECORDS_PER_CELL, DRY_RUN). Probes the Arctic Shift posts and comments "
        "search endpoints and writes `diagnostics/retrieval/source_probes.json`; demos "
        "the cleaner on 5 fixed sample strings; pulls up to 1000 records per "
        "(subreddit x week x content-type) unit into gzip JSONL shards under "
        "`shards/tokenized/pilot/`; upserts one manifest row per unit into "
        "`manifests/pilot/retrieval_manifest.csv`; shows a pandas inspection table.",
        "Keep the shape. Fix: DRY_RUN output must not land in the same shard tree or the "
        "same manifest as real output (DEFECT 1)."),
    "notebooks/02_counts_and_periods.ipynb": (
        "Stages 2-3. Editable cell sets CORPUS_MODE, CUSTOM_SUBREDDITS, FULL_RANGE, "
        "PROBE_MONTHS, FREEZE_PERIODS. Queries Arctic Shift `/posts/search/aggregate` and "
        "`/comments/search/aggregate` with `frequency=month` for the whole 2013-2026 span "
        "in one call per (subreddit, content-type); on any exception falls back to 50000 "
        "per month. Measures a median-tokens-per-document factor from a 100-record sample. "
        "Caches both to `metadata/monthly_counts/<sub>__<ctype>.json`. Rolls up to a "
        "monthly summary, applies the 5M/2M/10M sufficiency triage, and when FREEZE_PERIODS "
        "is True writes `config/period_definitions.csv`.",
        "Rewrite. The silent fallback to 50000/month is DEFECT 2 and it has already "
        "produced a frozen period file full of fabricated numbers. The "
        "`ALLOW_ESTIMATES`-style gate described in `docs/07_audit_report.md` is missing "
        "from the current source."),
    "notebooks/03_04_stream_train_pipeline.ipynb": (
        "Fused Stages 4-8, streaming. Editable cell sets PERIOD_FILTER, SEEDS "
        "[1047,2048,9182], AUTO_GIT_PUSH=False, DRY_RUN=False. Per period: pages Arctic "
        "Shift into an ephemeral scratch file under `shards/temporary/`, trains each "
        "required seed with a manual per-epoch alpha schedule from an "
        "`EphemeralSentenceStream`, saves the `.model` and an L2-normalised `.kv`, writes "
        "a rich `.nfo.json` provenance sidecar, upserts the training manifest, then "
        "DELETES the scratch text in a `finally` block. Then a seed-stability cell "
        "computes cross-seed neighbour Jaccard over the top-frequency diagnostic "
        "vocabulary and picks the production seed by the pre-specified rule, writing "
        "`models/production_seed.json`.",
        "This is the right architecture for the Colab constraint and is what actually "
        "produced the committed artefacts. Fix DEFECT 1 (min_count relaxed to 1 under "
        "DRY_RUN, dry-run artefacts written to the production store) and DEFECT 5 "
        "(hard-coded push branch)."),
    "notebooks/03_build_shards.ipynb": (
        "Stages 4-6, non-streaming. Editable cell sets PERIOD_FILTER and DRY_RUN. Defines "
        "a `ShardWriter` (bounded compressed shard, header manifest line, EOF flush, "
        "connection closed in a finally), an API pager and a local-file streamer; builds "
        "tracked shards as week units per (subreddit, period) with exact-dedup capped by "
        "a hash set; builds Tier-2 reference shards by uniform stable-ID hash fraction; "
        "then reopens every shard to cross-check the manifest and quarantines failures.",
        "Competing implementation of DEFECT 7. Its privacy-stripping validator and its "
        "quarantine logic are worth porting into the streaming path; the notebook itself "
        "should probably be retired."),
    "notebooks/04_train_evaluate.ipynb": (
        "Stages 7-8, non-streaming. Editable cell sets MODEL_FILTER_SUB, PERIOD_FILTER, "
        "SEED_FILTER, DRY_RUN. Refreshes a `corpus_master.csv` rollup; rebuilds a "
        "registry of expected (period x seed) models where COMPLETE requires the file to "
        "exist AND its checksum to match; trains from `ShardSentences` (a re-iterable "
        "streaming corpus) one model at a time with per-epoch checkpoints; validates new "
        "models by reopening them and running data-driven probes including a negation "
        "check; then runs the same seed-stability comparison.",
        "Also competing with DEFECT 7. Its registry rule -- 'COMPLETE requires "
        "file + checksum, not just a status string' -- is exactly the discipline the "
        "streaming path lacks and should be adopted there."),
    "notebooks/05_vectors_inspect.ipynb": (
        "Stages 9-10. Editable cell defines CONCEPTS (name, pole_a / pole_b anchor word "
        "sets, targets), SEED_FILTER and a CLAIM_FLOOR frequency threshold. L2-normalises "
        "and exports `.kv`; indexes available models grouped by subreddit and period; runs "
        "a metric engine computing semantic projection onto a concept axis, anchor "
        "distance and Jaccard stability; draws diagnostic plots (projection over time, "
        "Jaccard overlap, frequency guardrail) with matplotlib in Agg mode; writes "
        "per-concept markdown reports to `diagnostics/semantic_axes/` and rewrites "
        "`RUN_SUMMARY.md`.",
        "The analysis layer, and the one that would currently produce confident-looking "
        "nonsense from the empty vectors (DEFECT 1). It must refuse to run on any model "
        "whose provenance says tokens_trained is below the configured floor. Also has the "
        "`config vv0.3.0` typo (DEFECT 10)."),
    # ---- library ----
    "src/__init__.py": (
        "Package docstring only. Makes `src` importable so `from src.storage import ...` "
        "works once the project root is on sys.path.", "Keep as-is."),
    "src/cleaner.py": (
        "The meaning-preserving cleaner. Compiled regexes for URL / u-mention / "
        "r-mention / fenced code / markdown formatting / markdown links / emoji, plus a "
        "token regex that also matches the placeholder tokens. `clean_and_tokenize` "
        "normalises NFKC, strips markdown, replaces code/URL/user/subreddit with "
        "placeholders, lowercases, tokenises, maps digit runs longer than 4 to `<num>`, "
        "and drops documents below 10 chars or 3 tokens. Also `extract_text` (comment "
        "body vs. title + selftext) and `lang_of` (a function-word-ratio heuristic "
        "standing in for fasttext lid176, which the config asks for but which is not a "
        "dependency).",
        "Good and well-tested. Two issues: the import-time asserts (DEFECT 9), and "
        "`lang_of` is a heuristic while `config/project_config.yaml` declares "
        "`detector: fasttext_lid176` and `threshold: 0.7` -- the config overstates what "
        "the code does."),
    "src/storage.py": (
        "`sha256_file` (1 MB chunks), `atomic_write_bytes` / `atomic_write_text` (tmp + "
        "fsync + os.replace, refuses to write an empty file), and "
        "`save_gensim_atomic`, which saves into a timestamped staging directory and then "
        "`os.replace`s each generated file so gensim's companion `.npy` arrays land with "
        "their correct target names.",
        "Solid. Keep. Covered by a test that mocks the companion-file behaviour."),
    "src/paths.py": (
        "`get_project_root()` resolves the root across Colab and local by, in order: the "
        "canonical Drive clone path, upward search from cwd for "
        "`config/project_config.yaml`, a bounded 1-2 level downward search, the Drive "
        "mount, then the parent of `src/`. Raises a clear RuntimeError instead of "
        "returning a path that does not exist. `resolve_tmp()` prefers "
        "`paths.colab_tmp` from config and falls back to `shards/temporary`.",
        "Good. Note it is duplicated inline in notebooks 00/01/02 because those notebooks "
        "need the root before they can import it."),
    "src/manifests.py": (
        "Column definitions for the three manifests (RETRIEVAL_COLS, SHARD_COLS, "
        "TRAINING_COLS), `load_manifest`, `upsert_manifest_row` (atomic tmp+fsync+replace, "
        "idempotent on key fields, normalises every value to str), and "
        "`verify_output_shards`, which accepts semicolon-delimited multi-file lists and "
        "three checksum formats: exact per-file, combined "
        "`sha256(';'.join(hashes))`, and single-file.",
        "Solid. Keep."),
    "src/api.py": (
        "`api_get` with exponential backoff on 429/500/502/503 and on "
        "network timeouts, and special handling that turns an upstream 422 whose body "
        "contains 'Timeout' into a retryable TimeoutError. `retry_get` is an alias. "
        "`parse_agg` defensively finds the timestamp key and the count key in an "
        "aggregate response by substring-matching key names. `api_pages` is a generator "
        "that walks a (subreddit, content-type, time-window) oldest-first, advancing the "
        "cursor to `last.created_utc + 1`.",
        "Good. `parse_agg`'s substring key-sniffing is fragile but is a reasonable "
        "response to an API whose envelope is not formally pinned. Consider asserting "
        "the exact key names once and failing loudly on drift."),
    # ---- runner ----
    "run_pipeline.py": (
        "A 761-line CLI that re-implements the notebooks as importable stage functions "
        "(`run_stage_0`, `run_stage_1`, `run_stage_2`, `run_stream_and_train`, "
        "`run_stage_5`) with argparse flags `--mode`, `--subreddits`, `--stage`, "
        "`--stream-train`, `--dry-run`, `--auto-commit`, `--auto-push`, "
        "`--max-periods`. Writes timestamped logs to `logs/` and an environment record "
        "to `logs/env__*.json`. `git_commit_progress()` optionally commits and pushes "
        "checkpoints between stages.",
        "The most complete single artefact in the repo, and the best base for a rewrite -- "
        "but it carries DEFECT 1 (synthetic counts), DEFECT 4 (stage-5 vector count) and "
        "DEFECT 5 (branch fallback). It also duplicates nearly all notebook logic, so the "
        "two are guaranteed to drift."),
    # ---- tests ----
    "tests/test_pipeline.py": (
        "Five plain-function tests, runnable under pytest or as a script: `test_paths`, "
        "`test_cleaner` (negation retention, redaction tokens, emoji/code, >4-digit "
        "numbers, [deleted]), `test_storage_and_gensim_atomic` (atomic text write, SHA, "
        "and companion-.npy handling via a mock model), `test_manifests` (upsert "
        "idempotency, str normalisation, all three checksum formats, mismatch detection), "
        "and `test_api` (attribute presence only).",
        "All 5 pass. Coverage gap: `test_api` asserts only that functions exist -- there "
        "is no test of the backoff logic, the 422-timeout branch, or `parse_agg`. And "
        "nothing tests the period-freeze math, the hash sampling, or the seed-selection "
        "rule, which `docs/07_audit_report.md` claims were unit-tested 5/5 + 3/3. Those "
        "tests are not in the repository."),
    # ---- config ----
    "config/project_config.yaml": (
        "The single source of truth, v0.3.0, 226 lines. Paths, corpus definition "
        "(2013-01-01 to 2025-12-31, comments + submissions, English-only training, "
        "exclude-and-count deletions, exact dedup within subreddit-period), scope (Tier 1 "
        "still `TBD`, Tier 2 = 100-500 subreddits), source priority, slicing, reference "
        "sampling with a 20M-token cap, cleaning rules, periodization thresholds "
        "(5M / 2M / 10M / 20M), embeddings hyperparameters and the 3 seed candidates, "
        "the pre-specified seed-selection rule, ethics safeguards, reliability policy, "
        "counting method priority, and seed_eval parameters.",
        "The best-designed file in the repository and the right contract to keep. Two "
        "gaps: `scope.tier1_complete_subreddit` is still `TBD`, and it declares a "
        "fasttext language detector that `src/cleaner.py` does not implement."),
    "config/subreddit_list.csv": (
        "Candidate subreddits with tier, include and pilot flags. Rows: AskAcademia "
        "(medium), gradschool (medium), PhD (small), academia (large), Professors "
        "(excluded).",
        "Placeholder. Every row is annotated 'EXAMPLE ROW -- replace with your focal "
        "list'. No research scope has actually been chosen."),
    "config/period_definitions.csv": (
        "The FROZEN period plan consumed by the sharding and training stages: model_id, "
        "corpus_type, subreddit, start/end date, est_docs, est_tokens, "
        "total_eligible_tokens, sampled_train_tokens, sampling_fraction, boundary_reason, "
        "sufficiency, method, config_version. Currently 8 rows (4 subreddits x 2019 Q1/Q2).",
        "DISTRUST ENTIRELY. All 8 rows carry the identical fabricated "
        "`est_tokens = 6375000` and `sufficiency = sufficient`. This file must be "
        "regenerated from real aggregate counts before any training run. See DEFECT 2."),
    "config/source_definitions.yaml": (
        "Verified 2026-09-03 inventory of Arctic Shift endpoints (posts/comments search "
        "and aggregate), the download tool, the removal-request form, PullPush, and the "
        "official Reddit API terms. Records the response envelope `{\"data\": [...]}`, "
        "the accepted search params, the aggregate params and their timeout behaviour, "
        "and three findings: the bulk dump index is torrent-only (not Colab-viable), the "
        "HF Parquet mirror repo id is unverified, and PullPush 429s on first contact.",
        "Trust. This is real verification work and it is specific. Re-probe the "
        "endpoints before a production run, since it is dated."),
    "config/bot_patterns.yaml": (
        "Three regexes (automoderator, generic bot signature, remindme bot) used to FLAG "
        "but never exclude suspected bots in v1.",
        "Keep. Note that no code in the repository currently reads this file -- the "
        "`bot_policy.patterns_file` config key points at it but nothing loads it."),
    # ---- docs ----
    "docs/00_decision_checklist.md": (
        "Deliverable 1. 16 numbered decisions with recommended defaults, each mapping to "
        "a config field, with BLOCKING items flagged. Written to be answered by the "
        "researcher before anything is frozen.",
        "Read. Several BLOCKING items are still unanswered (notably the Tier-1 "
        "subreddit)."),
    "docs/01_data_source_assessment.md": (
        "Deliverable 2. Source-by-source comparison distinguishing official Reddit "
        "services from community archives. Conclusion: build on Arctic Shift dumps + "
        "API, use the official Reddit API only for recent top-ups, treat Reddit for "
        "Researchers as an optional parallel application, do not build on Pushshift, buy "
        "no paid infrastructure for v1.",
        "Trust. Consistent with `config/source_definitions.yaml` and with what the code "
        "actually does."),
    "docs/02_config_specification.md": (
        "Deliverable 3. Field-by-field explanation of `project_config.yaml`, the semantic "
        "versioning rule (vMAJOR.MINOR.PATCH, pilot on v0.x, first production freeze at "
        "v1.0.0), and which fields are frozen after production. States the governing "
        "principle that no notebook hard-codes a consequential choice.",
        "Read. That principle is the one the code currently violates (DEFECT 2)."),
    "docs/03_manifest_and_naming_spec.md": (
        "Deliverable 4. Schemas for the retrieval, shard and training manifests, the "
        "failure log, periods and filenames, plus the atomicity rules (write .tmp, fsync, "
        "validate, rename) and the 'if it isn't in a manifest, it didn't happen' rule. "
        "Specifies CSV/JSONL only -- never Excel, never pickle.",
        "Trust. The implementation in `src/manifests.py` and `src/storage.py` matches "
        "this spec closely."),
    "docs/04_pilot_plan.md": (
        "Deliverable 5. A 9-12 unit pilot across 3 subreddit sizes via both intended "
        "source paths, with pass/review/fail gates and a decision-report template. "
        "Budget: <2 GB Drive, <4 h on a free Colab runtime, no credentials beyond a "
        "Google login. Explicitly says do not proceed to Stage 2 until the report is "
        "reviewed and the config is frozen to v1.0.",
        "Read. The gate it describes was not honoured: `period_definitions.csv` was "
        "frozen from dry-run numbers."),
    "docs/05_scope_and_periodization_addendum.md": (
        "Addendum v0.2.0. Records the researcher's scope decisions: Tier 1 = one complete "
        "focal subreddit (name TBD), Tier 2 = 100-500 well-represented subreddits chosen "
        "empirically, 2013-2025, concept axes deferred until after training, and adaptive "
        "periods with an overflow cap. Defines the provisional 'well-represented' rule "
        "(active_month_share >= 0.9, sufficient_period_share >= 0.8, max_gap_months <= 3) "
        "and the three resulting classes (solo_per_period, pooled_only, excluded).",
        "Read. This is the scope contract the code should enforce and mostly does not yet."),
    "docs/06_corpus_size_evidence.md": (
        "The evidence note behind the token thresholds, approved by the researcher "
        "2026-09-03. Argues from Antoniak & Mimno (TACL 2018) on embedding instability "
        "with small corpora -- noting two of their test corpora are subreddits -- "
        "SemEval-2020 Task 1 period sizes, survey-literature practice at 10M+ per slice, "
        "the low-frequency-word failure mode, and Dubossarsky et al. (2017) on frequency "
        "artefacts masquerading as semantic change. Lands on 5M standard / 2M floor / 10M "
        "axis-grade, plus a 20M cap and a 100-occurrence interpretation floor. Includes a "
        "comments-to-tokens conversion table.",
        "Trust, and treat as the acceptance criterion. Every model currently in the repo "
        "fails it by three orders of magnitude."),
    "docs/07_audit_report.md": (
        "An audit dated 2026-09-03 recording 9 bugs found by execution and their fixes, "
        "live source probes, the 12-notebook-to-6 consolidation, residual risks, and a "
        "'proven checklist'.",
        "STALE. Its bug list is genuinely useful history and its fixes are present in the "
        "current source, but its closing claim that the workspace is 'at a clean "
        "pre-production state' is false (DEFECT 3), and it points at notebook sources in "
        "`/home/user/build/` that do not exist."),
    # ---- misc ----
    "README.md": (
        "Entry point. Reading order for the five deliverables, the directory layout, key "
        "assumptions, a changelog of what was built at each version, the 6-notebook run "
        "order, and a GitHub / Google Drive / Google Colab hybrid-workflow section with "
        "clone and save-back instructions.",
        "Partly stale. Claims '6 notebooks, all executed' (zero saved outputs), omits "
        "`03_04_stream_train_pipeline.ipynb` from the run order, and still carries "
        "first-time `git init` / `YOUR_USERNAME` setup instructions for a repo that "
        "already has a remote."),
    "RUN_SUMMARY.md": (
        "Machine-written rollup: models complete, normalized vectors exported, training "
        "registry path, restartability note. Written by `run_pipeline.run_stage_5()`.",
        "Wrong. Reports 'Normalized vectors exported: 0' against 24 `.kv` files on disk. "
        "See DEFECT 4."),
    "requirements.txt": (
        "Eight unpinned-minimum dependencies: pyyaml, requests, zstandard, tqdm, gensim, "
        "numpy, matplotlib, pytest.",
        "Looseness is a reproducibility gap given every sidecar records gensim 4.4.0 as "
        "provenance. Note `pandas` is imported by notebooks 01/02/04/05 but is not "
        "listed."),
    ".gitignore": (
        "Ignores `__pycache__`, notebook checkpoints, tmp/staging files, "
        "`shards/temporary/*` and `shards/quarantine/*`, the compressed tokenized shards "
        "`shards/tokenized/**/*.jsonl.gz`, `models/checkpoints/*.model*`, "
        "`models/word2vec/**/*.model`, `*.npy`, virtualenvs, caches and OS files.",
        "Correct for the GitHub/Drive split. But it is the reason `run_stage_5` finds no "
        "`.model` files on a fresh clone (DEFECT 4), and the reason the pilot shard paths "
        "in the manifest dangle (DEFECT 8). Note `vectors/*.kv` is NOT ignored, which is "
        "why 7.9 MB of synthetic vectors are committed."),
    "archive/README.md": (
        "Three-line note: the archive is superseded by the consolidated 00-05 pipeline at "
        "config v0.3.0, kept for provenance, do not run. Maps each archived notebook to "
        "its replacement.",
        "Trust."),
}

ARCHIVE_NOTES = {
    "notebooks/archive/02_build_monthly_counts.ipynb":
        "Superseded by 02_counts_and_periods.ipynb.",
    "notebooks/archive/07_train_word2vec_models.ipynb":
        "Superseded by 04_train_evaluate.ipynb.",
    "notebooks/archive/10_inspect_concepts_over_time.ipynb":
        "Superseded by 05_vectors_inspect.ipynb.",
}

PART12 = """
12.1  THE ONE THING THAT MATTERS MOST
-------------------------------------
This pipeline is well-engineered plumbing wrapped around a missing guarantee. The
atomic writes, checksums, manifests, provenance sidecars, streaming-and-purge
memory strategy and pre-specified seed rule are all good work, and the `src/`
library passes its tests. What is missing is the distinction between a rehearsal
and a run. Because that distinction does not exist in the data model, a single
`--dry-run` invocation produced 24 models and 7.9 MB of committed vectors that
are registered as `complete` and contain 13 real words.

So: before adding features, make "is this real?" a first-class, unforgeable
property of every artefact, and make every consumer check it.

12.2  WHAT A BETTER VERSION SHOULD DO
-------------------------------------
 1. Purge the synthetic state. Delete the 24 `.kv` files, the 24 `.nfo.json`
    sidecars, `manifests/training_manifest.csv`, `manifests/pilot/`,
    `metadata/monthly_counts/`, and regenerate `config/period_definitions.csv`
    from an empty file. Keep `config/` otherwise.
 2. Add `provenance_mode` to every manifest row and every sidecar, with values
    `dry_run` / `real`. Route dry-run artefacts to a separate directory tree.
    Make `05_vectors_inspect.ipynb` and stage 5 refuse `dry_run` rows unless
    explicitly told otherwise.
 3. Restore the freeze gate. `02_counts_and_periods.ipynb` must raise when the
    aggregate endpoint returns nothing measured. Reinstate the `ALLOW_ESTIMATES`
    flag that `docs/07_audit_report.md` says existed, defaulting to False, and
    have it gate the write to `period_definitions.csv`.
 4. Enforce the token floor at TRAIN time, not only at plan time. Before
    training a period, assert `tokens_trained >= periodization.absolute_floor_tokens`
    and refuse to write a `complete` row otherwise. Today the floor exists only
    in the planning stage, and the training stage overrode `min_count` to 1 to
    make fake data fit.
 5. Collapse to ONE stage 4-8 implementation. Keep the streaming one. Port
    `04_train_evaluate.ipynb`'s registry rule (COMPLETE = file exists AND
    checksum matches) and `03_build_shards.ipynb`'s privacy validator into it.
 6. Delete `run_pipeline.py` OR delete the notebooks. Two full implementations
    of the same pipeline cannot both be right, and the artefacts in the tree
    came from the streaming notebook path while the summary was written by the
    CLI. That split is how `RUN_SUMMARY.md` came to contradict the filesystem.
 7. Make paths project-relative in all manifests (DEFECT 8).
 8. Remove the duplicated root-level notebooks and docs (DEFECT 6).
 9. Remove the hard-coded branch name (DEFECT 5). Resolve it at runtime or make
    the remote branch an explicit config field.
10. Add tests for the things that actually break: period-freeze math, hash
    sampling determinism, the seed-selection rule, and the API backoff and
    `parse_agg` paths. `docs/07_audit_report.md` claims these were tested; the
    tests are not in the repository.
11. Decide the research scope. `scope.tier1_complete_subreddit` is `TBD` and
    `subreddit_list.csv` is all placeholder rows. Nothing downstream can be
    meaningful until this is a real decision.
12. Reconcile the language-detection story: either add fasttext lid176 as a real
    dependency, or change the config to say what `lang_of` actually does.

12.3  QUESTIONS THE ASSISTING LLM SHOULD ANSWER
-----------------------------------------------
 A. Is `arctic-shift.photon-reddit.com` still live and still rate-limiting at
    ~60 qpm, as `config/source_definitions.yaml` recorded on 2026-09-03? The
    whole design depends on it and it has no SLA. What is the fallback if it is
    gone? (`docs/01_data_source_assessment.md` names PullPush, but records that
    it 429s on first contact.)
 B. The aggregate endpoint is documented as timing out even on a 3-month
    medium-subreddit window. For 100-500 Tier-2 subreddits across 13 years, is
    aggregate-first actually viable? What is the real plan if it is not?
 C. At dim=200 with 5M-20M tokens per model and up to 500 subreddits x ~50
    periods, how many models is that, and does it fit in the Colab/Drive budget
    the design assumes? Nobody has done this arithmetic in the repository.
 D. Is Word2Vec per (subreddit x period) the right instrument at all, versus a
    single large multilingual/contextual model fine-tuned per period, or versus
    a pooled-corpus approach with frequency-matched controls? The design cites
    Dubossarsky et al. on frequency artefacts but implements no
    frequency-matched control.
 E. `05_vectors_inspect.ipynb` computes a projection onto a concept axis defined
    by researcher-chosen pole words. What is the plan for validating that the
    axis means what it is assumed to mean, given the config already defers
    concept definition until after training?

12.4  BUILD PROVENANCE OF THIS BUNDLE
-------------------------------------
Generated by `tools/build_llm_bundle.py` reading the working tree directly.
Re-run it after any change; `--check` fails if the committed bundle has drifted
from the sources it embeds.
"""


def build_inventory() -> str:
    out = [PART4_INTRO]

    groups = [
        ("NOTEBOOKS (canonical location: notebooks/)", [
            "notebooks/00_setup_and_configuration.ipynb",
            "notebooks/01_test_data_access.ipynb",
            "notebooks/02_counts_and_periods.ipynb",
            "notebooks/03_04_stream_train_pipeline.ipynb",
            "notebooks/03_build_shards.ipynb",
            "notebooks/04_train_evaluate.ipynb",
            "notebooks/05_vectors_inspect.ipynb",
        ]),
        ("SHARED LIBRARY (src/)", [
            "src/__init__.py", "src/cleaner.py", "src/storage.py",
            "src/paths.py", "src/manifests.py", "src/api.py",
        ]),
        ("CLI RUNNER", ["run_pipeline.py"]),
        ("TESTS", ["tests/test_pipeline.py"]),
        ("CONFIGURATION", [
            "config/project_config.yaml", "config/subreddit_list.csv",
            "config/period_definitions.csv", "config/source_definitions.yaml",
            "config/bot_patterns.yaml",
        ]),
        ("SPEC / DESIGN DOCUMENTS (docs/)", [
            "docs/00_decision_checklist.md", "docs/01_data_source_assessment.md",
            "docs/02_config_specification.md", "docs/03_manifest_and_naming_spec.md",
            "docs/04_pilot_plan.md", "docs/05_scope_and_periodization_addendum.md",
            "docs/06_corpus_size_evidence.md", "docs/07_audit_report.md",
        ]),
        ("PROJECT META", ["README.md", "RUN_SUMMARY.md", "requirements.txt", ".gitignore"]),
    ]

    for title, paths in groups:
        out.append(f"\n{rule('-')}\n{title}\n{rule('-')}\n")
        for rel in paths:
            desc = FILE_DESCRIPTIONS.get(rel)
            if not desc:
                continue
            what, verdict = desc
            p = ROOT / rel
            exists = p.exists()
            size = p.stat().st_size if exists else 0
            out.append(f"\n### {rel}\n")
            out.append(f"    present: {exists} | bytes: {size}\n")
            out.append(f"    WHAT IT IS: {what}\n")
            out.append(f"    VERDICT:    {verdict}\n")

    out.append(f"\n{rule('-')}\nDUPLICATED AT THE REPOSITORY ROOT (byte-identical; see DEFECT 6)\n{rule('-')}\n")
    for rel in sorted(p for p in FILE_DESCRIPTIONS if p.startswith(("notebooks/", "docs/"))):
        dup = Path(rel).name
        same = "IDENTICAL" if (ROOT / dup).exists() and (ROOT / rel).exists() \
            and (ROOT / dup).read_bytes() == (ROOT / rel).read_bytes() else "DIFFERS/ABSENT"
        out.append(f"    {dup:45s} == {rel:55s} {same}\n")

    out.append(f"\n{rule('-')}\nARCHIVED (do not run; provenance only)\n{rule('-')}\n")
    for rel, note in ARCHIVE_NOTES.items():
        p = ROOT / rel
        out.append(f"    {rel:52s} {note}\n")
    out.append("    archive/README.md                                      maps each archived notebook to its replacement\n")

    out.append(f"\n{rule('-')}\nDATA / OUTPUT DIRECTORIES (contents described in PART 2.4 and PART 11)\n{rule('-')}\n")
    for d, note in [
        ("metadata/monthly_counts/", "8 cached count JSONs, all synthetic (50000/month, method=aggregate:dry_run)"),
        ("manifests/", "training_manifest.csv (24 rows, all status=complete)"),
        ("manifests/pilot/", "retrieval_manifest.csv (24 rows, all output_final paths missing)"),
        ("models/word2vec/tracked/", "24 .nfo.json sidecars; the .model binaries are gitignored and absent"),
        ("vectors/", "24 .kv files, 7.9 MB, tracked in git; vocab 413 = 13 real words + 400 integers"),
        ("shards/tokenized/pilot/", "empty (.gitkeep only); shard files are gitignored"),
        ("shards/temporary/", "empty scratch dir used by the streaming path"),
        ("shards/quarantine/", "empty; destination for shards that fail validation"),
        ("diagnostics/", "5 subdirs, all empty except .gitkeep"),
        ("logs/", "7 pipeline_runner logs (all Dry-Run: True), 1 env record, 1 Colab push verification note"),
        ("tests/", "test_pipeline.py -- 5 tests, all passing"),
        ("archive/", "3 superseded notebooks + README (mirrors notebooks/archive/)"),
    ]:
        out.append(f"    {d:32s} {note}\n")

    return "".join(out)


def build() -> str:
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True).stdout.strip()
        br = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True).stdout.strip()
    except Exception:
        sha, br = "unknown", "unknown"

    s = []
    s.append(rule("=") + "\n")
    s.append("REDDIT WORD-EMBEDDINGS PIPELINE -- FULL CONTEXT BUNDLE FOR LLM REVIEW\n")
    s.append(f"Built:   {now}\n")
    s.append(f"Repo:    adamstorerphd/reddit_embeddings\n")
    s.append(f"Branch:  {br}\n")
    s.append(f"Commit:  {sha}\n")
    s.append("         (the commit this was built FROM; a file cannot record its own hash,\n")
    s.append("          so after committing, the bundle names its parent commit)\n")
    s.append("Purpose: paste this whole file into an LLM to diagnose and rewrite the pipeline.\n")
    s.append(rule("=") + "\n")

    s.append(part("0", "HOW TO USE THIS FILE") + PART0)
    s.append(part("1", "WHAT THE PROJECT IS") + PART1)
    s.append(part("2", "VERIFIED STATE OF THE REPOSITORY") + PART2)
    s.append(part("3", "CONFIRMED DEFECTS (RANKED)") + PART3)
    s.append(part("4", "FILE-BY-FILE INVENTORY") + build_inventory())

    # ---- PART 5: notebooks ----
    s.append(part("5", "NOTEBOOK SOURCES (VERBATIM)"))
    s.append("""
All seven notebooks, cell by cell. Markdown cells are reproduced as written;
code cells are numbered with the notebook's own 0-based cell index. Every code
cell carries a trailing bracketed line stating how many saved outputs it holds.
At build time that number is NONE for every code cell in every notebook, which
is the in-repo evidence for the claim in PART 2.3 that no notebook has ever been
executed.

Root-level copies of these seven files also exist and are byte-identical
(DEFECT 6); they are not repeated here.
""")
    nb_notes = {
        "notebooks/00_setup_and_configuration.ipynb": "Stage 0. No user settings cell.",
        "notebooks/01_test_data_access.ipynb": "Stage 1 pilot. Cell 1 is the only cell the user edits.",
        "notebooks/02_counts_and_periods.ipynb": "Stages 2-3. Contains the DEFECT 2 counting fallback in Cell 3.",
        "notebooks/03_04_stream_train_pipeline.ipynb":
            "Fused Stages 4-8, streaming. The path that produced the committed artefacts. "
            "Contains DEFECT 1 (min_count relaxed under DRY_RUN) and DEFECT 5 (hard-coded push branch).",
        "notebooks/03_build_shards.ipynb": "Stages 4-6, non-streaming. Competing implementation (DEFECT 7).",
        "notebooks/04_train_evaluate.ipynb": "Stages 7-8, non-streaming. Competing implementation (DEFECT 7).",
        "notebooks/05_vectors_inspect.ipynb": "Stages 9-10, the analysis layer. Would currently plot noise (DEFECT 1).",
    }
    for rel, note in nb_notes.items():
        s.append("\n" + notebook_block(ROOT / rel, rel, note))

    # ---- PART 6: src ----
    s.append(part("6", "SHARED LIBRARY src/ (VERBATIM)"))
    s.append("""
This is the part of the codebase that works. All five test functions covering it
pass (PART 2.5). Rewrite the notebooks around this library rather than replacing it.
""")
    for rel in ["src/__init__.py", "src/cleaner.py", "src/storage.py",
                "src/paths.py", "src/manifests.py", "src/api.py"]:
        s.append("\n" + file_block(ROOT / rel, rel))

    # ---- PART 7: runner ----
    s.append(part("7", "CLI RUNNER run_pipeline.py (VERBATIM)"))
    s.append("""
A second, complete implementation of the same pipeline. Carries DEFECT 1
(synthetic counts at line ~316), DEFECT 4 (run_stage_5 vector count) and
DEFECT 5 (branch fallback at line ~106).
""")
    s.append("\n" + file_block(ROOT / "run_pipeline.py", "run_pipeline.py"))

    # ---- PART 8: tests ----
    s.append(part("8", "TEST SUITE (VERBATIM)"))
    s.append("""
All 5 tests pass. Coverage gaps are listed in PART 4 under tests/test_pipeline.py.
""")
    s.append("\n" + file_block(ROOT / "tests/test_pipeline.py", "tests/test_pipeline.py"))

    # ---- PART 9: config ----
    s.append(part("9", "CONFIGURATION (VERBATIM)"))
    s.append("""
`config/project_config.yaml` is the contract. `config/period_definitions.csv` is
the file that must be regenerated before anything else -- see DEFECT 2.
""")
    for rel in ["config/project_config.yaml", "config/subreddit_list.csv",
                "config/period_definitions.csv", "config/source_definitions.yaml",
                "config/bot_patterns.yaml"]:
        note = ""
        if rel.endswith("period_definitions.csv"):
            note = ("ALL 8 ROWS CARRY IDENTICAL FABRICATED est_tokens=6375000 AND "
                    "sufficiency=sufficient. Do not trust. See DEFECT 2.")
        if rel.endswith("subreddit_list.csv"):
            note = "Placeholder rows only; no real scope has been chosen."
        s.append("\n" + file_block(ROOT / rel, rel, note))

    # ---- PART 10: docs ----
    s.append(part("10", "DESIGN AND SPEC DOCUMENTS docs/ (VERBATIM)"))
    s.append("""
The five numbered deliverables plus three addenda. docs/06 is the acceptance
criterion every model in the repo currently fails; docs/07 is stale (DEFECT 3).
""")
    doc_notes = {
        "docs/07_audit_report.md":
            "STALE. Its closing 'clean pre-production state' claim is false (DEFECT 3), "
            "and it references notebook sources in /home/user/build/ that do not exist. "
            "Its bug list is still useful history.",
        "docs/06_corpus_size_evidence.md":
            "The acceptance criterion. Every model currently in the repo has 5,600 tokens "
            "against a 5,000,000-token floor.",
    }
    for rel in ["docs/00_decision_checklist.md", "docs/01_data_source_assessment.md",
                "docs/02_config_specification.md", "docs/03_manifest_and_naming_spec.md",
                "docs/04_pilot_plan.md", "docs/05_scope_and_periodization_addendum.md",
                "docs/06_corpus_size_evidence.md", "docs/07_audit_report.md"]:
        s.append("\n" + file_block(ROOT / rel, rel, doc_notes.get(rel, "")))

    # ---- PART 11: evidence ----
    s.append(part("11", "RUNTIME EVIDENCE (VERBATIM)"))
    s.append("""
Manifests, logs, provenance sidecars and the machine-written summary. This is the
evidence behind PART 2.4 and PART 3.
""")
    s.append("\n" + file_block(ROOT / "RUN_SUMMARY.md", "RUN_SUMMARY.md",
                               "Machine-written by run_pipeline.run_stage_5(). Reports 0 vectors "
                               "against 24 .kv files on disk. See DEFECT 4."))
    s.append("\n" + file_block(ROOT / "requirements.txt", "requirements.txt"))
    s.append("\n" + file_block(ROOT / ".gitignore", ".gitignore"))
    s.append("\n" + file_block(ROOT / "archive/README.md", "archive/README.md"))
    s.append("\n" + file_block(ROOT / "metadata/monthly_counts/phd__comments.json",
                               "metadata/monthly_counts/phd__comments.json",
                               "Representative of all 8 files: every month is the hard-coded "
                               "50000 fallback, self-labelled synthetic_estimate / aggregate:dry_run."))
    s.append("\n" + file_block(ROOT / "models/word2vec/tracked/phd/w2v__phd__2019q1__cfg-v0.3.0__seed-1047.nfo.json",
                               "models/word2vec/tracked/phd/w2v__phd__2019q1__cfg-v0.3.0__seed-1047.nfo.json",
                               "Representative of all 24 sidecars: docs_trained=400, tokens_trained=5600, "
                               "vocab_size=413. The config floor is 5,000,000 tokens."))
    s.append("\n" + file_block(ROOT / "logs/env__20260904__cfg-v0.3.0.json",
                               "logs/env__20260904__cfg-v0.3.0.json"))
    s.append("\n" + file_block(ROOT / "logs/colab_secret_verification.txt",
                               "logs/colab_secret_verification.txt",
                               "Evidence that the hard-coded-branch auto-push path has actually fired (DEFECT 5)."))

    # one full log + the head of the training manifest
    log = ROOT / "logs/pipeline_runner__20260904T220105Z.log"
    s.append("\n" + file_block(log, "logs/pipeline_runner__20260904T220105Z.log",
                               "One of seven logs. Every one records 'Dry-Run: True'."))

    tm = ROOT / "manifests/training_manifest.csv"
    lines = tm.read_text(encoding="utf-8").splitlines()
    s.append("\n" + rule("-") + "\n")
    s.append("FILE: manifests/training_manifest.csv\n")
    s.append(f"ROWS: {len(lines) - 1} data rows (header + first 3 shown; all 24 have status=complete)\n")
    s.append(rule("-") + "\n")
    s.append("\n".join(lines[:4]) + "\n")

    pm = ROOT / "manifests/pilot/retrieval_manifest.csv"
    lines = pm.read_text(encoding="utf-8").splitlines()
    s.append("\n" + rule("-") + "\n")
    s.append("FILE: manifests/pilot/retrieval_manifest.csv\n")
    s.append(f"ROWS: {len(lines) - 1} data rows (header + first 2 shown). "
             "ALL 24 output_final paths are machine-absolute and absent from disk (DEFECT 8).\n")
    s.append(rule("-") + "\n")
    s.append("\n".join(lines[:3]) + "\n")

    # the .kv inspection transcript
    s.append("\n" + rule("-") + "\n")
    s.append("TRANSCRIPT: what is actually inside the committed vectors\n")
    s.append(rule("-") + "\n")
    s.append("""
Command run at build time:

    from gensim.models import KeyedVectors
    kv = KeyedVectors.load('vectors/vectors_norm__phd__2019q1__cfg-v0.3.0__seed-1047.kv')
    print("vector_size:", kv.vector_size, "| vocab:", len(kv))
    print(kv.index_to_key[:40])
    print(kv.most_similar('research', topn=5))

Output:

    vector_size: 200 | vocab: 413
    ['rewarding', 'but', 'easy', 'not', 'phd', 'in', 'publication', 'and',
     'teaching', 'research', 'about', 'discussion', 'academic', '399', '398',
     '397', '396', '395', '394', '393', '392', '391', '390', '389', '388',
     '387', '386', '385', '384', '383', '382', '381', '380', '379', '378',
     '377', '376', '375', '374', '373']
    [('100', 0.25245410203933716), ('294', 0.21510863304138184),
     ('111', 0.20567281544208527), ('253', 0.2019256204366684),
     ('325', 0.18309950828552246)]

Thirteen real words, then four hundred bare integers. The nearest neighbours of
the real word 'research' are numbers. These files are the single most misleading
artefact in the repository.
""")

    s.append(part("12", "WHAT 'BETTER' SHOULD MEAN") + PART12)

    s.append("\n" + rule("=") + "\n")
    s.append(f"END OF BUNDLE -- built {now} from {br}@{sha[:12]} by tools/build_llm_bundle.py\n")
    s.append(rule("=") + "\n")

    return "".join(s)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="rebuild in memory and fail if it differs from the file on disk")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    text = build()

    if args.check:
        if not args.out.exists():
            print(f"FAIL: {args.out} does not exist; run without --check to build it.")
            return 1
        current = args.out.read_text(encoding="utf-8")
        if current == text:
            print(f"OK: {args.out} matches the current working tree.")
            return 0

        # The provenance header legitimately differs between builds: the build
        # timestamp changes every run, and the recorded commit changes as soon as
        # the bundle itself is committed (a file cannot contain its own hash).
        # Neither is content, so both are excluded from the drift comparison.
        PROVENANCE = ("Built:", "Commit:", "END OF BUNDLE",
                      "         (the commit this was built FROM",
                      "          so after committing, the bundle names its parent commit)")

        def strip_provenance(t: str) -> list[str]:
            return [l for l in t.splitlines() if not l.startswith(PROVENANCE)]

        if strip_provenance(current) == strip_provenance(text):
            print(f"OK: {args.out} matches the working tree "
                  f"(ignoring build timestamp and the commit it was built from).")
            return 0
        print(f"FAIL: {args.out} has drifted from the working tree. Rebuild it.")
        # Show where it first diverges, so the drift is actionable.
        a, b = strip_provenance(current), strip_provenance(text)
        for n, (x, y) in enumerate(zip(a, b), 1):
            if x != y:
                print(f"  first divergence at content line {n}:")
                print(f"    on disk: {x[:90]!r}")
                print(f"    rebuilt: {y[:90]!r}")
                break
        else:
            print(f"  line counts differ: on disk {len(a)} vs rebuilt {len(b)}")
        return 1

    args.out.write_text(text, encoding="utf-8")
    kb = len(text.encode("utf-8")) / 1024
    words = len(text.split())
    print(f"Wrote {args.out.relative_to(ROOT)}: {kb:.1f} KB, {text.count(chr(10)):,} lines, "
          f"~{words:,} words, ~{words * 4 // 3:,} estimated tokens")
    return 0


if __name__ == "__main__":
    sys.exit(main())
