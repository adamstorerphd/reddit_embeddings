# Addendum v0.2.0 — Scope, "Well-Represented", and Period Design
### Records user decisions 2026-09-03 · supplements Deliverables 1–5, does not replace them

## 1. Decisions recorded
- **IRB:** no constraints reported. Safeguards stay on (no usernames, no profiling, no long quotes, removal-request support). Revisit only if institution says otherwise.
- **Scope:** Tier 1 = ONE complete focal subreddit (name TBD — see §2); Tier 2 = 100–500 well-represented subreddits (selected empirically, §3). Both include comments + submissions (title + selftext concatenated, flagged).
- **Range:** extended back before 2018 → `2013-01-01–2025-12-31` in config v0.2.0. Rationale: Arctic Shift covers 2005+, but pre-2013 Reddit is thin for most communities and roughly doubles storage/processing for rapidly diminishing embedding quality. 2013 keeps 13 years including pre/post-2023 API-regime change. Extension further back remains possible later as a config bump + counts rerun, never silently.
- **Drive:** design for free tier (~15 GB) with headroom; upgrade optional and only buys headroom/retention, never required. Rule: full-range projection must fit `free − 3 GB headroom` or scope is cut before Stage 2.
- **Concepts:** DEFERRED. No axes, no seed lists now. Stage 9 stability checks will use a generic diagnostic vocabulary (top-frequency content words + function words like not/never/no), which tests training stability without smuggling in substantive choices.

## 2. The one complete subreddit (Tier 1)
Do not nominate by intuition. Process: (a) you propose 2–4 candidates you care about; (b) pilot + Stage 2 counts rank them on volume, continuity, and pre-2018 depth; (c) we freeze ONE for complete 2013–2025 retrieval first, prove the full pipeline end-to-end (retrieve → shards → periods → 1–2 trained models), then expand. If you have no candidates, the pilot auto-ranks from the candidate universe and proposes one large/high-continuity community for your approval. Completing one sub first bounds risk: a failure mode found on 1 sub costs hours; found on 500 costs weeks.

## 3. What "well-represented" means (operational, auditable)
Computed ONLY from Stage 2 monthly counts — no full text needed for triage. Provisional rule (finalized after seeing the distributions in Stage 3):
- **Active month:** ≥100 docs in that month.
- **Sufficient period:** period tokens ≥ `min_usable_tokens_per_model` (provisional 3M; reset from counts).
- **Solo-per-period (Tier A, gets own embedding):** active in ≥90% of months AND sufficient in ≥80% of base periods AND longest gap ≤3 months.
- **Pooled-only (Tier B, contributes to reference/pooled models only):** below Tier A but active in ≥50% of months; never forced into a solo embedding.
- **Excluded (Tier C):** below Tier B; listed with reason, not silently dropped.
Reference set assembly: take all Tier A (up to 500 cap), then stratified-sample Tier B across size strata to reach 100–500 total, preserving breadth. Both estimands from Deliverable 1 are then computable: volume-weighted primary + capped sensitivity. The 100–500 window is a cost/quality tradeoff: <100 risks idiosyncratic reference; >500 multiplies retrieval/training cost roughly linearly for diminishing stability gains on free Colab.

## 4. Period design (deep dive — quarterly/monthly + overflow + merge)
**Core idea: count monthly, model adaptively.** Monthly counts are the atomic, always-retained inventory. Periods (what embeddings are trained on) are built from whole months:
1. Start from the base unit (quarterly for Tier 1/large subs, 6-monthly for pooled reference).
2. **Underflow → merge forward:** if a base cell has < min tokens, merge it with the NEXT cell(s), up to 12 months. If still short → mark `pooled_only`/`unavailable`, never train a weak embedding.
3. **Overflow → uniform cap, never first-N:** if a cell has MORE than `max_train_tokens_per_model` (provisional 20M), apply a deterministic per-period hash fraction `f = budget/eligible` (sha256 of record ID, same machinery as reference sampling) so the training sample is uniform over the whole period. Verify week-shares stay within tolerance (e.g. each week within ±30% of its eligible share); record BOTH `total_eligible_tokens` and `sampled_train_tokens` in `period_definitions.csv`. This answers your "fills up quickly but want a sample from the period" requirement without recency or ordering bias.
4. Boundaries are UTC month-starts, contiguous, non-overlapping, forward-merge only (deterministic; reruns give identical periods from identical counts).
5. Monthly vs quarterly is therefore NOT a premature lock: monthly inventory lets Stage 3 test both. Default expectation: quarterly solo models for large subs (monthly would 3–4× training cost and add noise), 6-monthly for reference, annual/pooled for small subs — but the counts decide, and the decision is frozen in `period_definitions.csv` v1.0 with reasons per row.
6. Pre-2018 months are typically thinner: expect more merged (6–12 mo) periods there and cleaner quarterlies after ~2015 — this is normal and will be visible in the Stage 3 sufficiency chart, not hidden.

## 5. What changes vs Deliverables 1–5
- `project_config.yaml` v0.2.0 (this addendum's rules). Period atom `1M`, base `3M`/`6M`, overflow cap, scope block, `semantics.concepts_deferred_until`.
- `period_definitions.csv` gains columns `total_eligible_tokens, sampled_train_tokens, sampling_fraction` alongside estimates.
- Pilot (Notebook 01) stays small (3 tiers × 3 weeks incl. a pre-2018 week 2015-06-01–07) but now also demonstrates the overflow-cap calculation post-hoc on the largest cell.
- Tier-2 identification method (candidate universe → DuckDB/Parquet counts → Tier A/B/C) is designed now, executed in Stage 2 (Notebook 02), frozen in Stage 3.
