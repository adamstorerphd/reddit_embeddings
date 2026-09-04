# Evidence Note — Minimum Corpus Size per Subreddit-Period
### v0.1 (2026-09-03) · Status: APPROVED by user 2026-09-03 → config v0.2.1 (frozen at v1.0.0 after counts)

**Question:** how many words/tokens per subreddit per period justify a standalone embedding?
**Short answer:** think in **tokens per trained model**, not comments per month. Evidence points to
~5M usable tokens as the standard minimum for a solo period embedding (~200k comments at
Reddit lengths), a ~2M-token absolute floor below which no solo model is trained, and ~10M+ for
fine-grained (axis-grade) work. Monthly embeddings therefore only qualify for very large
communities; quarterly/merged periods are the norm. Your "50k comments" instinct is the right
order of magnitude — reframed below as a monthly activity floor feeding quarterly models.

## 1. What the literature shows

- **Stability degrades on small corpora (foundational warning).** Antoniak & Mimno (TACL 2018)
  find nearest-neighbor structure "highly sensitive to small changes in the training corpus" and
  that "these effects are more prominent for smaller training corpora," recommending never to rely
  on a single model, especially on small corpora. Directly relevant: two of their test corpora ARE
  subreddits — AskScience (~332k docs × 44 words ≈ 14.6M tokens) and AskHistorians (~64k docs ×
  66 words ≈ 4.2M tokens). Even at 4–15M tokens, bootstrap variability was measurable — which is
  why our pipeline has Stage 9 (multi-seed) rather than trusting any single run.
- **Shared-task precedent: ~6–7M tokens per period works; ~1.7M is thin.** SemEval-2020 Task 1
  (unsupervised lexical semantic change) ran English on 6.5M/6.7M-token period slices; German and
  Swedish on 70–110M; Latin on 1.7M/9.4M — and systems performed worst on Latin, consistent with
  the small-C1 slice being the hardest. Our 5M standard sits just under the English precedent;
  our 2M floor sits just above the level where degradation was observed.
- **Field practice uses large slices.** The survey literature (decade slices of COHA, yearly
  Gigaword slices, Google Ngrams) works at 10M+ per slice, while explicitly flagging "a clear
  need to devise algorithms that work on small datasets" common in historical/digital-humanities
  work. Reddit quarterly slices of large subs land in the same regime as the survey mainstream.
- **Low-frequency words are the failure point.** Stability studies converge: high-frequency words
  stabilize first; rare words stay seed-sensitive regardless of corpus size. Hence TWO thresholds:
  (a) corpus-level min tokens per model, (b) word-level min_count (=20 provisional) PLUS a higher
  interpretation floor (≥100 occurrences) for any word entering a substantive claim.
- **Good news for Reddit register.** Antoniak & Mimno find short documents (their Reddit
  corpora: 44–66 words/doc) produce LESS cross-run variability than very long documents. Our
  one-record = one-doc design is the low-variance choice.
- **Noise can masquerade as change.** Dubossarsky et al. (2017) show frequency/sampling effects
  alone can reproduce "laws" of semantic change — another reason thresholds must be enforced and
  frequency-matched controls used, not eyeballed.
- **Seed instability persists even when large** (Wendlandt et al. 2018) — size thresholds reduce
  but never eliminate the need for Stage 9 seed evaluation.

## 2. Comments → tokens conversion (planning factors; pilot measures the real thing)

- Large Reddit sample (15M comments): mean 170 chars, median 87, mode 30 — heavy short-tail.
- Political-subs study: median 14–24 words/comment; combined medians 17–30 words.
- Planning factor: **~25 usable tokens per comment** (central), ~10 for titles, selftext highly
  variable. Stage 2 will replace these with measured median/mean per subreddit.

| Monthly comments | ≈ Monthly tokens | Verdict |
|---|---|---|
| 50k | ~1.25M | Below solo-model floor as a MONTH; viable QUARTERLY building block (~3.75M/quarter) |
| 65–80k | ~1.6–2M | Quarterly (~5–6M) meets standard minimum |
| 200k+ | ~5M+ | Monthly solo embedding defensible |
| <20k | <0.5M | Pooled-only; needs 6–12 mo merges even for quarterly |

## 3. PROPOSED thresholds (approve → config v0.2.1; freeze → v1.0.0 after counts)

- `min_usable_tokens_per_model (standard)`: 3M → **5M** (solo period embedding)
- `absolute_floor_tokens`: **2M** (below: no solo model, pooled-only or unavailable — never forced)
- `axis_grade_tokens`: **10M** (flag models below this as unsuitable for fine-grained axis claims)
- `max_train_tokens_per_model`: 20M (unchanged; overflow → uniform hash cap, both counts recorded)
- `min_count`: 20 (unchanged); `interpretation_floor`: **100 occurrences** for claim-bearing words
- Monthly solo models only where a single month clears 5M (≈200k comments); otherwise base
  quarterly (≥65k comments/mo avg), merge-forward to 12 mo, or pool.

## 4. How this is enforced (no silent forcing)
Stage 2 counts emit tokens/month/sub; Stage 3 applies the rule mechanically
(sufficient → keep; short → merge forward ≤12 mo; still short → pooled_only/unavailable with reason).
Every `period_definitions.csv` row carries est_tokens + reason, so a weak model can never appear
without a paper trail. Thresholds change only via config version bump.
