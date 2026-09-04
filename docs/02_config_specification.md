# Deliverable 3 — Project Configuration Specification
### v0.1 (2026-09-03) · Single source of truth: `config/project_config.yaml`

**Principle:** no notebook hard-codes a consequential choice. Every choice in Deliverable 1 lives here, versioned. Every output records `config_version` + `config_sha256`. Changing a **FROZEN-after-production** field requires a config version bump and re-validation of affected stages.

- **Config version:** semantic `vMAJOR.MINOR.PATCH` (e.g. `v0.1.0`). Pilot uses `v0.x`. First production freeze is `v1.0.0`.
- **Hash:** SHA-256 of the canonical YAML bytes, computed at notebook startup and written to every manifest row and model metadata.
- **Where stored:** Google Drive `.../reddit_embeddings_project/config/project_config.yaml` (permanent). Colab copies to local path via `00_setup` notebook; local edits are never authoritative — edit the Drive copy, bump version, re-run setup.
- **Companion files:** `subreddit_list.csv`, `period_definitions.csv` (empty until Stage 3), `source_definitions.yaml`, `bot_patterns.yaml`, all versioned alongside.

---

## 1. Parameter reference (every field explained)

### 1.1 Meta
| Key | Type | Example | Meaning / why it matters |
|---|---|---|---|
| `config_version` | str | `v0.1.0` | Human version; bump on any consequential change. |
| `project_name` | str | `reddit_word_embeddings` | Prefix for Drive paths and log names. |
| `created_date` / `last_modified` | ISO date | `2026-09-03` | Audit trail. |
| `notes` | str | `pilot defaults pre-counts` | What this version is for. |

### 1.2 Paths (no hard-coded Drive paths in notebooks)
| Key | Default | Notes |
|---|---|---|
| `drive_root` | `/content/drive/MyDrive/reddit_embeddings_project` | Single editable root; everything derives from it. |
| `colab_tmp` | `/content/tmp_reddit` | Ephemeral raw archives; safe to delete. |
| Sub-keys | `config/ manifests/ metadata/ shards/tokenized shards/temporary models/word2vec models/fasttext vectors/ diagnostics/... logs/ notebooks/` | Mirrors brief §5. Notebooks resolve all paths from these keys. |

### 1.3 Corpus scope
| Key | Default (pilot) | Frozen? | Notes |
|---|---|---|---|
| `date_range.start / .end` | `2018-01-01 / 2025-12-31` | Freeze at v1.0 | Inclusive UTC. Records filtered on `created_utc`. |
| `content_types` | `[comments, submissions]` | Freeze | `submissions` = title+selftext (see below). |
| `submission_combine` | `title_sep_selftext` | Freeze | `title + "\n\n" + selftext`; `has_selftext` flag retained. |
| `unit_of_text` | `one_record` | Freeze | One comment/submission = one doc. No thread pooling. |
| `language.policy` | `english_train_only_count_rest` | Freeze (threshold tunable) | `detector: fasttext_lid176`, `threshold: 0.70`, `min_chars_for_detection: 20`. Non-English counted, excluded from training shards. |
| `deletion_policy` | `exclude_count` | Freeze | Excludes `[deleted]`, `[removed]`, empty/whitespace. |
| `dedup_policy` | `exact_within_subreddit_period` | Tunable | `hash: sha256(normalized_text)`, `scope: [subreddit, period_id]`, keep-first. Fuzzy OFF v1. |
| `bot_policy` | `flag_only` | Tunable | `bot_patterns_file: config/bot_patterns.yaml`; sets `is_suspected_bot`, does not exclude in v1. |

### 1.4 Sources (priority order = fallback order)
```yaml
source_priority: [arctic_shift_dumps, arctic_shift_api, reddit_api_recent, pullpush_fallback]
sources:
  arctic_shift_dumps: {enabled: true,  base: "https://github.com/ArthurHeitmann/arctic_shift", monthly_cadence: true, lag_weeks: 4-6}
  arctic_shift_api:    {enabled: true,  base: "https://arctic-shift.photon-reddit.com/api", page_size: 100, qpm_budget: 60}
  reddit_api_recent:   {enabled: false, page_size: 100, qpm_budget: 60, only_newer_than_latest_dump: true}
  pullpush_fallback:   {enabled: false, use_only_if_arctic_gap: true}
```
`only_newer_than_latest_dump` and `use_only_if_arctic_gap` are enforced in code, not comments — prevents silent source mixing.

### 1.5 Slicing, batching, sharding (memory control)
| Key | Pilot default | Guidance |
|---|---|---|
| `slice_size` | `7D` (one week per retrieval unit) | Smaller = more resumable; larger = fewer manifest rows. Weekly is the recommended compromise; daily for very large subs if weeks OOM. |
| `api_page_size` | `100` | Max allowed by both APIs; do not lower without reason. |
| `records_per_shard` | `50_000` | Bounded shard: close + validate + checksum, then open next. Tune so compressed shard ≈ 20–100 MB. |
| `batch_size` | `1_000` | In-RAM buffer flushed to shard; never hold more than this. |
| `max_ram_records` | = batch_size | Hard invariant asserted in code. |
| `checkpoint_rows` | `5_000` | Manifest flush frequency (crash loses ≤ this many rows of progress). |

### 1.6 Reference sampling
| Key | Default | Meaning |
|---|---|---|
| `hash_sampling.hash_fields` | `id` | Stable Reddit base-36 ID; order-independent. |
| `hash_sampling.algorithm` | `sha256(id) mod 10000 < fraction*10000` | Deterministic, expandable (lowering threshold later only adds records). |
| `hash_sampling.fraction_primary` | `0.02` (2%) | Pilot value; final set after counts (target ≥ min-tokens per reference period). |
| `hash_sampling.seed_note` | `sha256 needs no seed; seed recorded for tie-breaks only` | Avoids false "seeded sample" claims. |
| `reference_estimands` | `[volume_weighted_primary, capped_sensitivity]` | `capped_sensitivity.max_docs_per_subreddit_period: 5000` (pilot). |
| `sampling_seed` | `20260903` | Recorded for any stochastic tie-breaking / shuffling; NOT the embedding seed. |

### 1.7 Cleaning & tokenization (frozen spec v1; see table in D1)
`lowercase: true, unicode_norm: NFKC, keep_stopwords: true, keep_negation: true, url_token: <URL>, mention_tokens: <USER>/<SUBREDDIT>, number_rule: pure-digit>4→<NUM>, emoji: drop_and_count, markdown: strip_keep_text, code_blocks: replace_with_<CODE>, min_chars_per_doc: 10, min_tokens_per_doc: 3`. Hand-inspection sample (n=200) required before production (Stage 7).

### 1.8 Periodization (Stage 3 fills `period_definitions.csv`)
`base_unit: 6M, min_usable_tokens_per_model: 5_000_000 (PROVISIONAL — must be re-set from counts), max_period_months: 12, merge_rule: adjacent_forward, insufficient_action: mark_unavailable`. Reference corpus: `base_unit: 6M` same thresholds.

### 1.9 Embeddings
`model: skipgram_w2v, dim: 200, window: 5, negative: 5, epochs: 5, min_count: 20 (provisional), max_vocab: 200000, subsample: 1e-5, workers: 2 (Colab-safe), lr: 0.025→min 0.0001, seed_candidates: [1047, 2048, 9182], production_seed_rule: prespecified_stability (Stage 9), toolkit: gensim, toolkit_version_pinned_at_setup`. FastText deferred: `enabled: false`.

### 1.10 Reliability
`retry: {max_attempts: 5, backoff_base_s: 2, retry_on: [429, 500, 502, 503, timeout, checksum_mismatch]}, resume: {treat_in_progress_as_interrupted: true, retry_failed_only: true}, atomic_writes: true (tmp+rename+checksum), drive_sync_check: true, log_level: INFO, progress_every_n: 10000`.

## 2. Example `project_config.yaml` (authoritative draft — ships as file)

See `config/project_config.yaml` (v0.1.0 pilot defaults). Notebooks load it with `yaml.safe_load`, validate required keys at startup (fail fast with a readable error, not a KeyError mid-run), compute `config_sha256`, and echo both at the top of every log.

## 3. Change control

- Pilot (`v0.x`): any field may change; record reason in `notes`.
- Production freeze (`v1.0.0`): scope/cleaning/period/hash-rule/embedding fields become FROZEN. A change creates `v1.1.0` + a migration note listing which manifests/models are invalidated. Validated models are never overwritten — new config writes new filenames.
- Every output (manifest row, shard header, model `.nfo.json`) carries `config_version` + `config_sha256`.

## 4. What you must inspect before running Notebook 00
1. `drive_root` matches your Drive.
2. `date_range` + `content_types`.
3. `records_per_shard / batch_size` (lower if on a small-RAM runtime).
4. `hash_sampling.fraction_primary` (pilot 2% is deliberately small).
5. `source_priority` (leave pullpush/reddit_api disabled until pilot verifies them).
