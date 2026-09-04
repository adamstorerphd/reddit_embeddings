# Deliverable 5 — Pilot Plan (complete BEFORE production)
### v0.1 (2026-09-03) · Config `v0.1.0` · Notebook `01_test_data_access.ipynb`

**Objective:** replace guesses with measurements. The pilot retrieves *small, nonadjacent slices* for *3 subreddit sizes* via *both intended source paths*, builds trial shards, and produces a **decision report** (not just files) that sets final thresholds, shard sizes, and go/no-go for scale-up. Cost target: <2 GB Drive, <4 h wall-clock on a free Colab runtime, zero credentials beyond a Google login.

**Do not proceed to Stage 2 (full counting pass) until this report is reviewed and `project_config.yaml` is frozen to v1.0.**

---

## 1. Pilot matrix (9–12 retrieval units total — small by design)

| Dimension | Pilot value | Rationale |
|---|---|---|
| Subreddits | 1 large + 1 medium + 1 small, drawn from YOUR candidate list (Deliverable 1, Q1). If you have no list yet: pilot uses public volume proxies to pick e.g. one top-100, one mid-rank, one niche community — recorded as provisional and replaced before production. | Estimates must span orders of magnitude; a single-size pilot cannot size shards or judge small-sub feasibility. |
| Date slices (nonadjacent) | **2019-01-01–07, 2021-06-01–07, 2023-07-01–07** (one week each) + **2025-11-01–03** (3-day recency probe for official-API path, if credentials exist; else skipped with reason). | Covers pre-COVID, mid-pandemic, post-API-change regimes + recency gap. Nonadjacent weeks defeat seasonality/ordering bias. |
| Content types | Both `comments` and `submissions` for every cell (title+selftext concat per D1 default). | Tests the register mix and the submissions-to-comments token ratio. |
| Sources per cell | **Path A (bulk):** Arctic Shift dump slice covering that week. **Path B (paged):** Arctic Shift API for the same week (subset OK). PullPush queried once per size-tier as liveness probe only. | Directly compares the two production paths on identical windows; yields the API-vs-dump agreement metric. |
| Sampling | No hash-sampling in pilot retrieval (measure full-week volume first); APPLY the 2% hash rule post-hoc on one week to demonstrate determinism (same input twice → byte-identical sample). | Proves the reference-sampling code before it matters. |

Total: 3 subs × 3 weeks × 2 ctypes = 18 candidate units; **execute a minimum of 9** (all comments cells + 1 submissions cell per tier) if time-constrained — the report must state which cells were deferred.

## 2. Inputs / outputs

**Inputs:** `config/project_config.yaml v0.1.0`, `config/subreddit_list.csv` (pilot rows flagged `pilot=true`), `config/source_definitions.yaml`. No prior manifests required (fresh pilot directory `manifests/pilot/` so production manifests stay clean).

**Outputs (all under Drive pilot prefix, permanent):**
1. `manifests/pilot/retrieval_manifest.csv` + `failure_log.jsonl` (real manifests, real statuses — the resume logic is under test).
2. Trial shards `shards/tokenized/pilot/*.jsonl.gz` (bounded at 50k records; expect 1–3 shards per cell).
3. Hand-inspection sample `diagnostics/retrieval/pilot_inspection_200.csv` (200 rows: raw → cleaned → tokens → keep/drop + reason).
4. **Pilot decision report** `diagnostics/retrieval/pilot_report.md` (template §5 — the actual deliverable).
5. Log `logs/01_test_data_access__<ts>__cfg-v0.1.0.log` + end-of-run summary cell output.

## 3. Procedure (notebook sections; each bounded, checkpointed, resumable)

1. **Setup & verify:** mount Drive, load+hash config, pin package versions, check `zstandard/pyyaml/requests` availability, confirm free disk/RAM, probe all sources (dump HEAD, API 1-page query, PullPush 1 query, official API auth status) — abort options per probe, never hang.
2. **Path A (dump slice):** stream ONE `.zst` range covering the target week → filter subreddit+date in-stream → write trial shards (batch 1k, shard 50k) → per-record validation → atomic close + checksum + manifest row. Record MB/s, records/s, compressed MB per 10k records.
3. **Path B (API slice):** page the same week (page 100, cursor persisted every page, backoff on 429/502) → identical shard path → record effective QPM, failure count, page-loss events.
4. **Agreement check:** compare Path A vs B counts for overlapping cells (target ±5%; investigate misses: timezone edges, deletion drift, API truncation).
5. **Cleaning validation:** generate the 200-row inspection sample across keep/drop reasons; YOU read at least 50 rows and approve or revise rules in config (one-line change, version bump).
6. **Trial training smoke test (tiny):** train ONE throwaway 50-dim, 1-epoch model on the largest pilot cell to prove the iterable-corpus path works under RAM limits — then DELETE it (not a finding, just a plumbing check).
7. **Report + next-stage recommendation:** fill the §5 template; notebook ends with completed/remaining/failed + safe-rerun statement.

**Memory discipline:** never hold more than `batch_size` (1k) records; process `.zst` as a stream; release decompressor per unit; shard cap enforced; verbose logs to file with only a progress line per 10k records in-cell.

## 4. Validation criteria (pass / review / fail)

| Metric | Pass | Review (proceed with caution) | Fail (do not scale) |
|---|---|---|---|
| Dump throughput | ≥100 MB/hr sustained | 30–100 MB/hr (shrink slices to daily) | <30 MB/hr or repeated corrupt archives |
| API effective yield | ≥80% of dump count on overlap | 50–80% (use API for fills only) | <50% or persistent 502s (disable source) |
| Shard integrity | 100% reopen + checksum match | — | Any mismatch (fix atomic-write path) |
| Cleaning sample | ≥90% decisions judged correct on 50-row read | 75–90% (revise patterns, re-sample) | <75% (halt; rewrite rules) |
| Storage projection | Full-range projection ≤ Drive free − 3 GB headroom | Within 2× headroom (enable shard deletion policy) | Exceeds Drive (narrow scope before Stage 2) |
| Crash recovery | Kill-simulated rerun skips completes, retries rest | — | Duplicates or lost rows (fix manifest keys) |

## 5. Decision-report template (notebook writes this; you approve it)

`diagnostics/retrieval/pilot_report.md` must contain: (a) records/day and usable-tokens/day per tier with the raw numbers; (b) measured MB/s, records/s, compressed-MB-per-10k, projected full-range GB and model-training hours; (c) API-vs-dump agreement % per cell with explanation of gaps; (d) rate-limit/failure frequencies by source; (e) cleaning-sample approval note + any rule changes; (f) recommended FINAL `slice_size`, `records_per_shard`, `hash_fraction`, `min_tokens_per_model` (replacing provisionals with evidence); (g) explicit GO / GO-WITH-CHANGES / NO-GO for the Stage 2 counting pass, with scope cuts if needed (e.g. "drop submissions for small tier", "extend base unit to 12M for small subs").

## 6. Failure & recovery (pilot proves the pattern production will rely on)
Network error → backoff ≤5 attempts, cursor retained, `failed` row without stopping other cells. Corrupt dump block → quarantine block, continue, record `corrupt_archive`. Malformed record → count + skip (cap: abort cell if >5% malformed). Drive hiccup → retry sync, never mark complete unflushed. Colab disconnect → rerun notebook: completes skip by checksum, interrupted units reprocess idempotently, `--only-failed` retries exactly the failure log. End-of-run cell always prints: completed / remaining / failed / safe-to-rerun / next notebook.

## 7. Go / no-go rules for scale-up
- **GO** if all Pass criteria met → freeze `project_config.yaml v1.0.0` + lock `period_definitions.csv` schema → run Stage 2 counting pass.
- **GO-WITH-CHANGES** if any Review band hit → apply the report's scope/slice/threshold changes as `v0.2.0`, re-run affected pilot cells only, then freeze.
- **NO-GO** if any Fail → do not run Stage 2; instead resolve the blocking item (credentials, scope cut, source switch) and repeat the pilot. Running a full count on a failing pilot wastes the exact hours restartability is meant to save.

## 8. Your action to launch
Confirm the three pilot subreddits (or authorize provisional auto-selection) and the three pilot weeks (or accept defaults above). On your confirmation I build `00_setup_and_configuration.ipynb` + `01_test_data_access.ipynb` to this spec — no production code before the pilot report is reviewed.
