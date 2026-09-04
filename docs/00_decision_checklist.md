# Deliverable 1 — Decision Checklist
### Restartable Reddit Word-Embedding Pipeline · v0.1 (2026-09-03)

**Status:** DRAFT for your review. Nothing here is locked. Every item below becomes a field in `config/project_config.yaml` (Deliverable 3). Do not start production retrieval until you have confirmed or changed the **BLOCKING** items.

**How to use this file:**
1. Read the "Recommended default" column.
2. If you agree, do nothing — it will become the config default.
3. If you disagree, tell me the new value; I will update the config spec and record the change with a new config version.
4. Items marked BLOCKING affect the pilot design. Items marked DEFERRABLE can be decided after the counting pass.

---

## 1. Corpus scope (blocking for pilot)

| # | Decision (brief §4) | Options | Recommended default | Why | Changeable later? |
|---|---|---|---|---|---|
| Q1 | Which subreddits are focal? | You choose 3–8 | **You must supply.** For the *pilot only*, I propose auto-selecting 1 large (>1M comments/yr), 1 medium (~100k–500k/yr), 1 small (<50k/yr) from your candidate list. Production list lives in `config/subreddit_list.csv`. | Pilot needs variance in volume to estimate shard sizes and training feasibility. | Yes — adding subreddits later is safe; removing one after training wastes work but does not corrupt other models. |
| Q2 | Years / date range? | e.g. 2015–2025 | **Default: 2018-01-01 to 2025-12-31, with pilot slices in 2019, 2021, 2023** (nonadjacent, covering API-regime change in 2023). Historical reason: Arctic Shift coverage is strongest 2015+; pre-2015 is sparser and less comparable. Reference corpus uses same range. | Covers pre/post-2023 API change + COVID + recent periods while staying in well-archived years. | Start date can be extended backward later at cost of re-running counts; end date should be frozen per period version. |
| Q3 | Comments, submissions, or both? | comments-only / submissions-only / both | **Default: BOTH, modeled separately then evaluated for pooling.** Rationale: comments dominate token volume (~80–90% of Reddit text); titles+selftext add topical framing but different register. Training them separately first lets you test whether pooling is valid. | Document type affects register and embedding geometry — consequential. | Must be fixed before Stage 4 shards; changing later requires rebuilding shards. |
| Q4 | If submissions: combine title + selftext? | concat / title-only / separate fields | **Default: concatenate as `title + "\n\n" + selftext`, with a flag `has_selftext`. Empty selftext (link/image posts) retained as title-only with flag.** | Preserves context; flag lets you ablate later. Link-only titles are short — handled by min-length rule, not dropped silently. | Fixed in cleaning spec v1; changing requires re-tokenization. |
| Q5 | English-only? | yes / no / flag-only | **Default: English-only for training; RETAIN counts of non-English for diagnostics (do not silently discard).** Detection: fastText `lid.176` or `langdetect` on raw text, threshold documented; short texts (<20 chars) skipped for language ID and retained unless clearly non-English. | Embeddings are language-sensitive; mixing languages distorts neighborhoods. But exclusion rates must be reported (Stage 2 counts). | Threshold can be tuned after pilot hand-inspection sample. |
| Q6 | Unit of text? | comment / submission = 1 doc; vs. thread-pooled | **Default: one Reddit record = one document (one "sentence" stream for Word2Vec = one record's token list).** Do NOT concatenate threads. | Thread-pooling inflates context windows and confounds authorship; Word2Vec skip-gram expects short documents. | Locked before training; affects all downstream interpretation. |
| Q7 | Deleted / removed handling? | exclude / flag | **Default: EXCLUDE `body == "[deleted]"`, `"[removed]"`, empty/whitespace-only from training; COUNT them separately in Stage 2 inventory.** Note limitation: historical archives cannot reflect later deletions — record this as a coverage caveat. | They carry no semantic signal; including them injects a spurious high-frequency token. | Counting rule locked; training exclusion locked. |
| Q13 | Temporal resolution? | month / quarter / 6-mo / year | **Default: adaptive (Deliverable 5 + Stage 3): start from 6-month calendar cells; merge if < min-tokens; cap at 12 months.** Reference corpus: annual or 6-month. Do not promise quarterly subreddit embeddings until counts prove feasibility. | Fixed quarters will starve small subreddits; fixed years will blur change in large ones. | Period definitions are versioned (`period_definitions.csv`); frozen once training starts (config version bump required to change). |

## 2. Cleaning & sampling (blocking for shard design)

| # | Decision | Options | Recommended default | Why |
|---|---|---|---|---|
| Q8 | Bots? | exclude / flag / retain | **Default: FLAG, do not auto-exclude in v1.** Maintain `config/bot_patterns.yaml` (e.g. `^I am a bot`, AutoModerator, known flair). Record `is_suspected_bot` per shard record; exclude only exact-duplicate boilerplate via dedup rule. Full bot exclusion requires your approved list — false positives (e.g. helpful bots quoting policy) can bias semantics. | Aggressive bot filtering is a silent substantive choice. Flag-first is auditable. |
| Q9 | Crossposts / duplicates? | exclude / flag | **Default: EXACT-text dedup within (subreddit, period) via SHA-256 of normalized text; keep first occurrence, count duplicates. Near-duplicate (fuzzy) dedup OFF in v1.** Crosspost flag retained where `crosspost_parent` present. | Exact dedup removes boilerplate without risking over-merging paraphrases. Fuzzy dedup is expensive on Colab and hard to reproduce — defer to sensitivity analysis. |
| Q10 | Volume-weighting? | yes / raw | **Default: within a subreddit-period, natural volume weighting (each document = 1 training instance). NO up/down-weighting of authors or threads in v1.** | Any reweighting is an estimand change; natural weighting is the transparent baseline. Record author-concentration diagnostics instead. |
| Q11 | Reference corpus balancing? | volume-weighted / balanced / capped | **Default primary estimand: VOLUME-WEIGHTED deterministic hash sample (each eligible Reddit doc has equal inclusion probability → large subs dominate, as they do on Reddit). Sensitivity: CAPPED sample (max N docs per subreddit-period).** Rationale: volume-weighted answers "what did Reddit overall look like?"; capped answers "what did the average community look like?" — you likely want both, with the first as primary. | This is an estimand decision, not a technical one. Both are supported by the same hash-sampling code; only the cap differs. |
| — | Tokenization & normalization | many | **Default: minimal, meaning-preserving: Unicode NFKC, lowercase=TRUE (recorded), preserve apostrophes inside words (`don't` → `don't`, not `don t`), keep negation/stopwords (NO stopword removal), replace URLs → `<URL>`, user/subreddit mentions → `<USER>`/`<SUBREDDIT>`, split on whitespace+punctuation via regex, keep tokens with internal `-`/`'`; drop tokens that are pure numbers >4 digits → `<NUM>` else keep; emoji → drop with count (v1) after reporting frequency.** See Deliverable 3 for full table. | Embeddings need stopwords/negation ("not", "never", pronouns, modals) — removing them is a substantive distortion. Lowercasing is the one aggressive normalization we accept, because case variants fragment rare-word counts; it is logged and reversible in config. |
| — | Min-count / vocab cap | thresholds | **Default: `min_count=20` per model, `max_vocab=200,000`, `sample (subsampling)=1e-5`.** Final thresholds set AFTER counting pass — these are pilot values only. | Illustrative thresholds must not become final without evidence (brief §Stage 3). |
| — | Model & hyperparams | w2v / fastText | **Default: skip-gram Word2Vec, dim=200, window=5, negatives=5, epochs=5, seed varied (Stage 9). FastText only as later robustness model.** | Skip-gram suits rare-word / small-corpus regimes; lower memory than FastText subwords on free Colab. |
| — | Alignment | none / Procrustes | **Default: NO alignment in primary workflow. Each period model keeps its own coordinates; axes built independently per model with identical seed definitions.** Alignment (orthogonal Procrustes) only as labeled robustness check. | Alignment imposes a false common space and hides instability; independent axes are more honest. |

## 3. Infrastructure & ethics (blocking for setup)

| # | Decision | Recommended default |
|---|---|---|
| Q14 | Drive storage available? | **You must confirm (e.g. 15 GB free vs 2 TB paid). Default design assumes 15 GB free tier.** Budget: pilot <2 GB; production models ~50–200 MB each; shards deleted after validation. If <10 GB free, we shrink shard retention. |
| Q15 | Official academic Reddit access? | **Default: assume NOT available; design primary path on Arctic Shift (free, no credentials).** Optionally apply to Reddit for Researchers in parallel (PI-gated, weeks-long review) — I can draft the application text, but do not block the pilot on it. |
| Q16 | IRB / ethics / quotation rules? | **Default: treat as human-subjects-adjacent: no usernames in shards, no user profiling, no verbatim long quotes in outputs, support removal requests, log limitation that archives retain deleted content.** You must confirm with your institution whether IRB exemption / data-use agreement is needed BEFORE publication. I provide no legal clearance. |
| Q12 | Future semantic axes? | **List 2–5 candidate axes now (e.g. warmth–competence, progressive–conservative) with 5–10 seed words per pole — used ONLY for Stage 9 stability checks and Stage 12 coverage diagnostics, NOT for hypothesis testing.** Without seeds we cannot evaluate whether vocab thresholds preserve your concepts. |

## 4. What I need from you before the pilot

- [ ] **Q1:** candidate focal subreddit list (or approve: pilot auto-picks large/medium/small after counts)
- [ ] **Q2:** confirm date range (or accept 2018–2025 default)
- [ ] **Q3/Q4:** confirm comments+submissions, title+selftext concat (or change)
- [ ] **Q12:** 2–5 candidate concept areas (names only, seeds can come later)
- [ ] **Q14:** free vs paid Drive capacity
- [ ] **Q15:** are you affiliated with a university PI willing to apply for Reddit for Researchers? (yes/no/defer)
- [ ] **Q16:** any known IRB / quotation / retention constraints? (none-known is an acceptable answer, recorded as such)

> Reply with e.g. "Accept all defaults; focal candidates: r/AskAcademia, r/gradschool, r/PhD, r/academia, r/Professors; range 2016–2024; Drive 15GB free; PI yes; IRB unknown" and I will freeze `project_config.yaml` v0.1 and build Notebook 00 + 01.
