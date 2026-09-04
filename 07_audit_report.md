# Audit Report — live execution + consolidation (2026-09-03, config v0.3.0)

**Method:** every shippable notebook was executed (real runs, not reviews): 00 full, 01 dry-run (18/18 units),
04 train/eval on 2 synthetic periods × 2 seeds (4/4 models), 05 normalize/inspect (4 vectors, 86 trajectory rows,
2 plots). 02/03 network paths were probed live; their pure logic (freeze math, dedup, hash sampling) was unit-tested
5/5 + 3/3. All test artifacts removed afterwards; manifests reset; workspace is at a clean pre-production state.

## 1. Bugs found by execution (all fixed, all verified)

| # | Severity | Location | Symptom | Fix | Verified by |
|---|---|---|---|---|---|
| 1 | CRITICAL | 01 cleaner regexes | `re.error: unbalanced parenthesis` — hand-written JSON doubled every backslash (`\\S` instead of `\S`) | Rebuilt cell from plain-Python source; runtime asserts on URLs, mentions, markdown, emoji, `<NUM>` | 01 dry-run 18/18 + cleaner checks PASS |
| 2 | HIGH | 01 cleaner order | `MD_FMT` (`>` in class) ate `<URL>`/`<USER>` brackets after insertion → tokens `url` not `<url>` | Markdown strip now runs BEFORE token insertion (documented in-cell) | Behavior asserts PASS |
| 3 | HIGH | 02 dump discovery | Dump index is torrent-only → 0 HTTP files; notebook would have recorded 156 phantom "gaps" | Counting redesigned aggregate-first (02 rewritten); torrents documented non-Colab-viable | Live index fetch + probe |
| 4 | HIGH | 02 streaming engine | Leftover buffer + decompressor tail dropped at EOF; `end_ts` wrote invalid `-32` date; connection never closed | Flush + tail-line processing, real month-end math, close in `finally` (carried into 03) | Unit-tested path |
| 5 | CRITICAL | 07 registry | `todo` comprehension shadowed/unpacked dicts → crash on any non-empty registry | Rewrote registry with plain loop + checksum verification (04 Cell 4) | 04 E2E rerun: 4/4 trained |
| 6 | HIGH | 07/04 train | `store_dir` never created → `FileNotFoundError` on first save (4/4 FAIL) | `mkdir` + `_tmp()` suffix helper | Retry run: 4/4 OK (also proved retry-only) |
| 7 | MEDIUM | 07/04 manifests | int-vs-str seed comparison → duplicate manifest rows (28-row read observed) | Normalized keys to str in `tupsert` + one-time dedupe | Manifest holds exactly 4/4 rows |
| 8 | MEDIUM | 07 DRY | Hard `/content/tmp_reddit` → crash off-Colab | `resolve_tmp()` with workspace fallback (03 + 04) | E2E tmp resolved locally |
| 9 | LOW | 01 resume | `complete` rows skipped without checksum re-check (spec violation) | Checksum-verified skip, else idempotent reprocess | Patched + re-validated |

## 2. Source findings (live probes, 2026-09-03)

- Arctic Shift search API LIVE (`/posts/search`, `/comments/search`, `{"data"}` envelope, `after/before/sort/limit/fields` all accepted).
- Aggregate endpoint accepts `frequency=month` but **times out even on a 3-month medium-sub window** ("Timeout. Maybe slow down a bit") → auto-split + bounded-fallback design; exactness claims removed.
- PullPush **429 on first contact** → fallback-only status confirmed empirically.
- HF Parquet mirror: repo id unverifiable (empty Hub search, no id in guides) → NOT a source until pinned; config + sources files say so explicitly.
- Bulk `.zst`: torrent-only upstream → not streamable on free Colab; local-file streaming kept for user-supplied files; per-subreddit download-tool is the Tier-1 bulk candidate (verify URL pattern in pilot).

## 3. Consolidation: 12 notebooks → 6

| New | Covers (old) | Gate preserved |
|---|---|---|
| 00_setup | 00 | — |
| 01_pilot | 01 | approvals before 02 |
| 02_counts_and_periods | 02 + 03 | `FREEZE_PERIODS` lock; estimates never freeze unless `ALLOW_ESTIMATES` |
| 03_build_shards | 04 + 05 + 06 | inspection read before 04 |
| 04_train_evaluate | 07 + 08 | frozen-periods assert; prespecified seed rule |
| 05_vectors_inspect | 09 + 10 + 11 | descriptive-only viewer; `RUN_SUMMARY.md` |

Superseded files moved to `notebooks/archive/` (provenance, do-not-run). Notebook sources live in `/home/user/build/nb0{2,3,4,5}.py` — edit there, rebuild with the assembler snippet in this report's appendix? (Rebuild: split on `# TYPE:`, `json.dump`; 10 lines.)

## 4. Residual risks (not bugs — operating realities)

1. Aggregate timeouts on huge subs may force quarterly→monthly splits or bounded estimates; method column makes this visible per row.
2. Free-Colab wall-clock: full-range counts/shards/training span sessions by design (resume-tested); keep `MAX_*` caps small per session.
3. `fields=` trimming is assumed supported on search (documented in API README); pilot cell verifies before production paging.
4. Tiny-model seed Jaccard flags fired correctly on synthetic data (0.06–0.08 < 0.30) — expect OK on real 5M+ corpora; the flag, not the value, was under test.

## 5. Proven checklist

00 setup+validate ✓ · 01 bounded slices+manifests+report ✓ · cleaner spec incl. negation ✓ · atomic writes+checksums ✓ ·
failed-only retry (04 run 1→2) ✓ · checksum-verified resume ✓ · sidecar provenance ✓ · production-seed rule machinery ✓ ·
normalize/export ✓ · trajectories CSV+plots+reports ✓ · PII strip (validator asserts no author/username keys) ✓.
Unproven until real data: aggregate behavior on huge subs, download-tool pattern, full-range timings (all instrumented to measure on first contact).
