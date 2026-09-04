# Deliverable 4 — Manifest, Schema & File-Naming Specification
### v0.1 (2026-09-03)

**Purpose:** make every stage restartable, auditable, and idempotent. If it isn't in a manifest, it didn't happen. All manifests are append/flush-friendly CSV or JSONL (never Excel, never pickle), UTF-8, with atomic updates (write `*.tmp` → fsync → validate → rename).

**Storage:** Drive `manifests/` (permanent). Colab mirrors locally and syncs on every `checkpoint_rows` interval and at stage end. Drive failure is a retryable error, never a silent skip.

**Statuses (shared vocabulary):** `pending | in_progress | partial | complete | failed | validation_failed | skipped`. Only `complete` means "validated and safe to skip on rerun." `in_progress` found at startup = interrupted → reprocess safely (idempotent keys below prevent duplicates).

---

## 1. Retrieval manifest — `manifests/retrieval_manifest.csv`
One row per **retrieval unit** (one week × one subreddit × one content type × one source, per `slice_size: 7D`).

| Column | Type | Required | Description / validation |
|---|---|---|---|
| `unit_id` | str | Y, unique | `{source}__{subreddit}__{ctype}__{start}_{end}` e.g. `asdump__AskAcademia__comments__2019-01-01_2019-01-07`. Stable across reruns (idempotency key). |
| `source` | enum | Y | `arctic_shift_dumps \| arctic_shift_api \| reddit_api_recent \| pullpush_fallback`. Never mixed within a row. |
| `source_url_or_query` | str | Y | Dump URL + byte range, or exact API query + cursor chain. Must be sufficient to reproduce. |
| `subreddit` | str | Y | Without `r/` prefix, case-preserved. |
| `start_ts` / `end_ts` | ISO-8601 UTC | Y | Unit boundaries; `end` exclusive. |
| `content_type` | enum | Y | `comments \| submissions`. |
| `status` | enum | Y | Shared vocabulary above. |
| `attempt_count` | int | Y | Incremented per attempt; `>max_attempts` → stays `failed`, surfaced in failure summary. |
| `started_at` / `completed_at` | ISO-8601 | Y if started/completed | Wall-clock; used for throughput stats. |
| `last_cursor` | str | N | Last successfully processed record ID / API cursor / dump byte offset. Resume point. |
| `n_read` / `n_usable` | int | Y if attempted | Read vs retained-after-filters; `n_usable ≤ n_read` asserted. |
| `token_estimate` | int | N | Fast whitespace-estimate from counting pass (exact counts come from shards). |
| `output_tmp` / `output_final` | path | N | Shard(s) produced; final set only when validated. |
| `output_sha256` | hex | Y if complete | Checksum of final output; recomputed on resume-skip (skip only if match). |
| `error_category` | enum | N | `network \| rate_limit \| corrupt_archive \| malformed_record \| drive_io \| oom \| unknown`. |
| `error_excerpt` | str ≤300ch | N | Truncated message only; NEVER raw Reddit text or credentials. |
| `config_version` / `config_sha256` | str | Y | Traceability. |
| `retrieval_date` | date | Y | When upstream was contacted (for moving APIs). |

**Completion rule:** a unit is `complete` only when: output closed + reopenable + `n_usable` matches shard header + SHA-256 recorded + manifest flushed to Drive. Anything else is `partial`/`failed`.

## 2. Shard manifest — `manifests/shard_manifest.csv`
One row per **validated compressed shard** (`shards/tokenized/*.jsonl.gz`).

| Column | Notes |
|---|---|
| `shard_id` | `{corpus}__{subreddit-or-REF}__{period_or_slice}__{shardnum:04d}` e.g. `tracked__AskAcademia__2019W01__0003`. |
| `corpus` | `tracked \| reference`. |
| `subreddit`, `period_id` (nullable pre-Stage-3; slice label OK in pilot), `content_type` | Denormalized for filtering without opening shards. |
| `n_records`, `n_tokens`, `min_ts`, `max_ts` | Must match shard self-header (cross-checked). |
| `path`, `sha256`, `bytes_compressed` | Integrity + storage accounting. |
| `source_unit_ids` | `;`-joined retrieval `unit_id`s contributing (provenance chain). |
| `status` | Same vocabulary; `validation_failed` quarantines the file (renamed to `quarantine/`, never silently deleted). |
| `config_version`, `config_sha256`, `created_at` | As above. |

**Shard record schema (inside each `.jsonl.gz`, one JSON per line):** `rid_hash` (sha256 of `kind_id`, NOT the raw ID — dedup-capable without storing linkable IDs longer than needed), `sub` , `ts` (ISO UTC), `period` (nullable), `ctype`, `tokens` (list[str]), `flags` (`is_suspected_bot, has_selftext, lang, n_raw_chars`). NO usernames, NO raw text, NO scores. Header line `#manifest {...}` with counts+config for self-validation.

## 3. Corpus statistics — `metadata/corpus_statistics/<slice>.csv` + monthly rollups
Per (month × subreddit × content_type): `n_read, n_valid, n_deleted, n_removed, n_empty, n_nonenglish, n_dup_exact, token_approx, uniq_token_estimate (HyperLogLog or sample-based — never a full vocab set in RAM), median_len, min_ts, max_ts, missing_intervals, bytes_processed, source, retrieval_date, status`. This is the Stage 2 counting output that justifies period boundaries; shards are NOT written in this stage.

## 4. Period definitions — `config/period_definitions.csv` (versioned, frozen at v1.0)
`model_id, corpus_type, subreddit_or_group, start_date, end_date, est_docs, est_tokens, boundary_reason (e.g. merged_2_cells_below_threshold), sufficiency (sufficient|insufficient|pooled_only)`. Sorted, non-overlapping per series. Training code refuses to run if the file's `config_version` differs from the active config.

## 5. Training manifest — `manifests/training_manifest.csv`
One row per (model_spec × seed): `model_id, corpus_type, subreddit_or_group, period_id, spec_hash, dim, window, sg, negative, epochs, min_count, max_vocab, subsample, workers, lr, seed, vocab_size, words_processed, epochs_done, train_secs, peak_ram_mb (approx), model_path, vectors_path, model_sha256, vectors_sha256, config_version, status, diagnostics_path`. Partial epochs checkpoint to `models/checkpoints/`; only fully-trained + validated rows become `complete`.

## 6. Failure log — `manifests/failure_log.jsonl`
One JSON object per failure event (append-only, never rewritten): `{ts, stage, unit_or_shard_id, attempt, error_category, error_excerpt, input_ref, action (retry|quarantine|skip_with_reason), config_version}`. End-of-notebook summary aggregates this file into "what failed / how to retry only failures" (`--only-failed` mode reads exactly this file).

## 7. File-naming convention (no `model_final` names)

```
w2v__<sub-or-group>__<period>__cfg-<ver>__seed-<seed>.model        # gensim native
vectors_norm__<sub-or-group>__<period>__cfg-<ver>__seed-<seed>.kv  # normalized keyed vectors
shard: <corpus>__<sub-or-REF>__<slice>__<nnnn>.jsonl.gz
diag:  <stage>__<sub-or-REF>__<period>__cfg-<ver>.<ext>
logs:  <notebook>__<UTC-timestamp>__cfg-<ver>.log
```
Lowercase sub names with non-alphanumerics stripped (`askacademia`), periods as `2019h1/2019q1/2018-2020`. Every model ships with a sidecar `<same-stem>.nfo.json` (spec + data provenance + package versions + hashes). Normalized derivatives never overwrite the original; filename must contain `norm`.

## 8. Atomicity & rerun semantics (applies to all stages)
1. Write to `*.tmp` in the destination directory. 2. Close + reopen + row-count/hash check. 3. Rename to final (POSIX atomic on same filesystem; Drive File Stream safe via same-folder rename). 4. Update manifest + flush + (for Drive) verify file size after sync. Rerun logic: `complete`+checksum-match → skip; `partial/in_progress/validation_failed` → reprocess unit idempotently (dedupe on `unit_id`/`rid_hash`); `failed` → retry until `max_attempts`, then surface in retry-only list. Crash loses at most `checkpoint_rows` of progress by design.
