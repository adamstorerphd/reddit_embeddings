# Deliverable 2 — Data-Source Assessment
### Verified 2026-09-03 (America/Los_Angeles) · v0.1

**Method:** live web verification of docs, API status reports, and community tests conducted July–August 2026. Claims below distinguish **official Reddit services** from **community archives**. Prices/limits are reported figures, not quotes — confirm before relying on them.

**Bottom line:** build the primary pipeline on **Arctic Shift dumps + Arctic Shift API** (free, no credentials, bulk-capable, Colab-streamable). Use the **official Reddit API only for recent/prospective top-ups**. Treat **Reddit for Researchers** as an optional parallel application. Do **not** build on Pushshift. Do **not** buy paid infrastructure for v1.

---

## 1. Summary table

| Source | Operator | Coverage (as of verification) | Access model | Cost | Rate limits / size | Colab fit | Recommendation |
|---|---|---|---|---|---|---|---|
| **Arctic Shift dumps** (monthly `.zst` + per-subreddit torrents + Parquet mirror on Hugging Face) | Community (Arthur Heitmann), open-source | 2005–present; ~2.5B items through Feb 2026; ~261 GB Parquet; monthly cadence, 4–6 wk lag | Direct download / torrent / HF; `zstandard` streaming; no key | Free (you pay bandwidth/compute) | Files are GB-scale per month globally; per-subreddit slices much smaller; process compressed, never unpack fully | ★★★★★ Primary for historical bulk | **PRIMARY for Stages 1–4** |
| **Arctic Shift API** (`arctic-shift.photon-reddit.com/api/...`, web search + download tool) | Same community project | Same archive, served paginated | REST, no auth; single-subreddit full-text search | Free, best-effort, no SLA | Rate-limited; suitable for pilot slices & gap-filling, NOT full-corpus pulls | ★★★★☆ Pilot +补 gaps | **PRIMARY for pilot; SECONDARY for production** |
| **PullPush.io** (Pushshift-compatible API + search frontend) | Community | 2005+ but partial after 2023; one July-2026 test found it frozen since May 2025 with intermittent 502s; other listings report 1–2 mo recency gap | REST, no auth | Free | Reports vary (~1k req/hr in one test vs ~120k/hr in marketing copy — treat as unreliable) | ★★☆☆☆ Fallback only | **FALLBACK / cross-check only; pilot must test liveness before any use** |
| **Official Reddit Data API** (+ PRAW) | Reddit, Inc. (official) | Live only; NO historical search; listings capped (~100/listing), comment trees truncated | OAuth app; approval queue since late-2025 Responsible Builder Policy (slow/opaque; new self-serve approvals often denied) | Free ≤100 QPM OAuth / ~10 QPM unauth (non-commercial only); commercial = negotiated contract, widely reported ~$0.24/1k calls with ~$12k/mo minimum block — confirm directly | 100 queries/min averaged over 10-min window | ★★★☆☆ Recent-only | **RECENT/PROSPECTIVE top-up only; do not use for history** |
| **Reddit for Researchers** (beta program) | Reddit, Inc. (official) | Program-defined; details not fully public | Application-gated; PI at accredited university required; ~50-participant beta cohorts; weeks-long review | Free if admitted | Program-defined quotas | ★★★☆☆ If admitted | **OPTIONAL parallel track; do not block pilot** |
| **Academic Torrents / old Pushshift dumps** | Community mirrors | Frozen (2005–2023 or mid-2025 depending on mirror; ~3.97 TB full) | Torrent / offline | Free | TB-scale; unsuitable for free Colab | ★★☆☆☆ | **REFERENCE / reproducibility cross-check only** |
| **Hugging Face processed subsets** | Various | Varies; quality/freshness inconsistent | Download | Free | GB-scale | ★★★☆☆ | **DIAGNOSTIC use only (never as primary citable source)** |
| **Paid scrapers / aggregation APIs** (Apify actors, SocialGrep, Xpoz, Bright Data, etc.) | Commercial | Live + some history | API key | e.g. Apify from ~$1.50/1k results; SocialGrep $9–49/mo; enterprise datasets $250–$4k+ | Per-result metering | ★★☆☆☆ | **OPTIONAL, never required; cost estimate required before any use per brief §1** |

## 2. What happened (context you need for methods section)

- **Pushshift (2015–2023) is dead for general research.** Reddit revoked its access in May 2023 during API monetization. The surviving Reddit-hosted instance is moderator-only. Old dumps are frozen in time. Do not cite Pushshift as a live source.
- **Arctic Shift is the maintained community successor** for bulk history: monthly dumps, versioned releases, collection notes, removal-request process, and helper scripts (`zstandard`-based streaming). It is volunteer-run with no uptime guarantee — hence our manifest/retry design.
- **PullPush mimics the old Pushshift API** (easy port of old scripts) but post-2023 coverage is partial and reliability reports conflict. Treat any PullPush-derived counts as provisional until cross-checked against Arctic Shift dumps for the same slice.
- **Official API lockdown tightened in 2025–2026:** self-service approval closed under the Responsible Builder Policy; unauthenticated JSON endpoints began returning 403 (May 2026 reports); commercial access is negotiated (no public rate card on current terms). The free tier remains usable for low-volume, non-commercial, already-approved apps — adequate for topping up the last 4–6 weeks that dumps have not yet covered, inadequate for history at scale.

## 3. Source-by-source assessment (streaming, limits, terms, reproducibility)

### A. Arctic Shift dumps — PRIMARY
- **Formats:** `.zst` compressed NDJSON (monthly global + per-subreddit), `.zst_blocks`, plus Parquet mirror queryable with DuckDB. Work compressed; never decompress to disk on Colab.
- **Streaming into Colab:** `requests (stream=True) → zstandard streaming decompressor → JSON-per-line iterator → bounded shard writer`. One archive/month at a time; per-subreddit torrents preferred when available (smaller). Small local cache (1–2 archives) to avoid re-downloads; delete after validated shards are written.
- **Rate/reliability:** bulk download speed is the constraint, not API QPM. Expect GB/hour-scale; pilot measures actual throughput (Stage 1 metric).
- **Terms/ethics:** community archive; honors removal requests via public form; retains content deleted after collection (must disclose as limitation); do not redistribute raw data; no usernames in derivative shards.
- **Reproducibility:** cite release tag / dump date / file checksum + retrieval date in manifest. Dumps are citable fixed snapshots — superior to a moving API for a methods section.
- **Gaps to verify in pilot:** per-slice completeness vs API counts; missing-date intervals; 2023-regime continuity.

### B. Arctic Shift API — PILOT + GAP-FILL
- **Use for:** pilot slices (days/weeks), coverage spot-checks, small-subreddit backfill where a full dump is wasteful.
- **Constraints:** single-subreddit full-text search only (no global keyword search); paginated; rate-limited; best-effort. Page-by-page with cursor persistence; backoff on 429/502; record every query in retrieval manifest.
- **Do not use for:** full-corpus pulls (too many pages; will throttle and risk incompleteness).

### C. PullPush — FALLBACK ONLY
- Use only if Arctic Shift has a demonstrable gap for a slice AND PullPush demonstrably fills it in the pilot. Record source per record; never mix sources silently within one manifest unit. Cross-check counts; expect discrepancies.

### D. Official Reddit API (PRAW / raw REST) — RECENT TOP-UP ONLY
- **Use for:** the 4–6 week window newer than the latest dump + prospective collection going forward.
- **Design:** OAuth (script app), 100 QPM budget, page size 100, paginated listings (`before`/`after`), exponential backoff, per-page manifest rows. Separate `source=reddit_api` units so the provenance is explicit.
- **Do not use for:** any historical backfill (no search, capped listings, approval risk).
- **Compliance:** Data API Terms (deletion-compliance within 48h for served content, non-commercial scope on free tier, no scraping workarounds). Flag any step that would violate terms for institutional review.

### E. Reddit for Researchers — OPTIONAL
- PI-gated, application + weeks of review, program-defined quotas. Worth applying if you have a PI and plan to publish — it strengthens provenance. But the pipeline must not depend on admission; Arctic Shift path proceeds regardless.

### F. Academic Torrents / HF subsets — REFERENCE ONLY
- Useful for methods cross-checks ("our Arctic Shift counts for slice X match torrent snapshot Y within Z%") and for NLP pre-training context. Not primary because: TB-scale (torrents) or undocumented processing (HF subsets).

### G. Paid options — EXCLUDED FROM v1 BY DEFAULT
- Per brief §1: any paid service requires (a) stated purpose, (b) free alternative, (c) pre-use cost estimate. None clears that bar for v1. If a later gap forces reconsideration (e.g. no free coverage for a critical recent month), produce a one-page cost memo first (volume × per-result rate + storage) and cap spend.

## 4. Recommended source architecture

```
History (2018 → latest_dump-6wk):  Arctic Shift DUMPS (primary) → shards
Pilot / spot-checks / small fills: Arctic Shift API (primary) → same shard format
Cross-checks:                      PullPush / torrents (diagnostic counts only)
Recent (latest_dump → today):       Official API (separate manifest source) → same shard format
                                    [optional] Reddit for Researchers if admitted
```

Every shard records `source, source_url_or_query, retrieval_date, source_checksum_or_cursor` so models are traceable to the exact upstream snapshot.

## 5. Risks & mitigations

| Risk | Mitigation built into pipeline |
|---|---|
| Community archive downtime / 502s | Retry with backoff; `failed` status without halting pipeline; retry-failed-only mode; dumps preferred over API |
| Conflicting coverage claims | Counting-only pass (Stage 2) + API-vs-dump consistency checks on pilot slices; gaps recorded, not interpolated |
| Dump lag (4–6 wk) | Explicit recent-window top-up via official API; periods never defined over uncovered dates |
| ToS / removal obligations | Removal-request support; no redistribution; username stripping; deletion-compliance for API-served content |
| Reproducibility of moving APIs | Prefer fixed dumps; record query+cursor+retrieval date for every API unit |

## 6. What the pilot must verify (feeds Deliverable 5)
1. Arctic Shift dump throughput to Colab (MB/s, records/s) and per-subreddit slice sizes.
2. Arctic Shift API liveness + effective QPM for our query pattern.
3. PullPush liveness (go/no-go for fallback role).
4. API-vs-dump count agreement on ≥2 overlapping test slices (±5% target; investigate if worse).
5. Official API credential status (approved/pending/denied) and recent-window yield.

*Verification sources consulted 2026-09-03: Arctic Shift GitHub repo and download/API docs; independent July–August 2026 field tests of Arctic Shift/PullPush freshness and rate limits; Reddit API pricing/limit guides (100 QPM free tier, ~$0.24/1k commercial reports, approval-queue notes); Reddit-for-Researchers beta criteria (PI-gated). Full URLs retained in project log; key endpoints pinned in `config/source_definitions.yaml` (Deliverable 3).*
