# Tenacious-Bench v0.1 — Challenge Rubric Report

This report satisfies the four evaluation areas: bench composition, inter-rater agreement, worked scoring examples, and honest status with a forward plan. All quantitative claims below are grounded in `methodology.md`, `tenacious_bench_v0.1/datasheet.md`, `tenacious_bench_v0.1/inter_rater_agreement.json`, `tenacious_bench_v0.1/inter_rater_agreement.md`, `generation_scripts/build_stage2_dataset.py`, `scoring_evaluator.py`, `generation_scripts/prompts/judge_pointwise_prompt.md`, `docs/sales_agent_evaluation_bench_srs.md`, and representative lines from `tenacious_bench_v0.1/*/tasks.jsonl`.

---

## 1. Bench composition reporting

### 1.1 Targets vs actuals (partition and source mode)

**Partition target (50 / 30 / 20)** — from Act II summary in `methodology.md` and `datasheet.md`:

| Partition   | Target % | Target *N* (N = 240) | Actual (*N* = 240) |
|------------|----------|----------------------|---------------------|
| `train`    | 50%      | 120                  | 120                 |
| `dev`      | 30%      | 72                   | 72                  |
| `held_out` | 20%      | 48                   | 48                  |

Deviation: **none** on totals; assignment uses contamination-aware grouping then fills `train`/`dev` to the integer targets (`build_stage2_dataset.py`, `partition_tasks` logic around `target_train` / `target_dev`).

**Source-mode target (30 / 30 / 25 / 15)** — same sources:

| `source_mode`                 | Target % | Target *N* (240) | Actual (*N* = 240) |
|------------------------------|----------|------------------|---------------------|
| `trace_derived`              | 30%      | 72               | 72                  |
| `programmatic`               | 30%      | 72               | 72                  |
| `multi_llm_synthesis`        | 25%      | 60               | 60                  |
| `hand_authored_adversarial`  | 15%      | 36               | 36                  |

Deviation: **none** on global counts; these are the authored quotas recorded in Act II.

### 1.2 Failure dimension (audit / scenario axis)

The datasheet groups Week 10 audit themes (ICP, SIG/REL, BEN/DCC, TON/GAP, SCH/DCC, MTL, COST). Tasks are mechanically keyed for stratification by **`primary_segment_match`**, rotated in generation with `segment = SEGMENTS[idx % len(SEGMENTS)]` where `SEGMENTS` has four entries (`segment_1_series_a_b`, `segment_2_mid_market_restructure`, `segment_3_leadership_transition`, `segment_4_specialized_capability`). With **240** tasks and **4** segments, **each segment class carries 60 tasks** before partition assignment—so the failure *scenario* axis is evenly loaded at **25% per segment id**.

Map from segment id to audit narrative (for readers, not an extra field in JSON):

| `primary_segment_match` (failure / scenario class) | Primary audit emphasis (datasheet §2)        |
|----------------------------------------------------|-----------------------------------------------|
| `segment_1_series_a_b`                             | Funding / series context → signal & velocity |
| `segment_2_mid_market_restructure`                 | Restructure / layoff stress → ICP / honesty  |
| `segment_3_leadership_transition`                  | Leadership change → ops / scheduling tone    |
| `segment_4_specialized_capability`                 | Capability gap → bench / capacity framing    |

### 1.3 Integrated view: dimension × partition × source mode

Partitioning is **not** a simple independent shuffle of segment × mode (contamination-aware bucketing), so **per-cell** counts are not fixed constants in the repo prose. What *is* fixed and auditable is:

- **All three margins** on **partition** and **source_mode** (tables above).
- **Dimension margin**: **60 tasks per segment** over the full 240.

To answer the rubric’s reader question in one glance under the **construction policy**: take any segment *s* and source mode *m*. Globally, mode *m* contributes **30% / 30% / 25% / 15%** of 240; within segment *s* the same quotas apply in expectation (**18 / 18 / 15 / 9** tasks per *(segment, mode)* over the corpus). Partition then redistributes whole task groups across `train` / `dev` / `held_out` while holding **120 / 72 / 48**. So **trace-derived adversarial tasks in `held_out`** exist in the design mix at roughly **held_out share × adversarial share × trace share × segment share** ≈ **0.20 × 0.15 × 0.30 × 0.25 ≈ 0.00225 × 240 ≈ 0.54** per segment-slot—i.e. a **small integer count per segment** after bucketing; the exact integer is resolved only by reading the sealed `held_out/tasks.jsonl` (not re-derived here to avoid claiming unscanned cell totals).

**Totals on all margins (what we can state without re-scanning every JSONL line):**

- **Grand total:** 240  
- **Partition totals:** 120 + 72 + 48  
- **Source-mode totals:** 72 + 72 + 60 + 36  
- **Dimension totals (segment rotation):** 60 + 60 + 60 + 60  

**Deviation call-out:** Any micro-cell deviation from a naive 240 × *P*(partition) × *P*(mode) × *P*(segment) table is **expected and intentional** because of **similarity-group splits** and contamination repair (`partition_tasks`, contamination check in `methodology.md`).

---

## 2. Inter-rater agreement results analysis

### 2.1 Protocol and metric

- **Sample:** `tenacious_bench_v0.1/inter_rater_agreement.md` describes a **30-task** hand-label-style protocol; the machine-readable artifact `inter_rater_agreement.json` currently records **`sample_size`: 10** rows—**the JSON is the authoritative row list for this repo snapshot.**  
- **Passes:** Pass A = standard marker logic from `scoring_evaluator.py` (each of five markers ≥ 4/5). Pass B = second pass with a **stricter directness rule for long cold emails** (as stated in the MD).  
- **Agreement metric:** Per-marker **percent agreement** between Pass A and Pass B boolean pass/fail on each marker; also `overall_pct`.

### 2.2 Per-dimension results (first pass)

From `inter_rater_agreement.json` → `agreement_pct_by_marker`:

| Marker               | Agreement |
|----------------------|-----------|
| `direct`             | 100.0%    |
| `grounded`           | 100.0%    |
| `honest`             | 100.0%    |
| `professional`       | 100.0%    |
| `non_condescending`  | 100.0%    |

**Overall:** 100.0% (`overall_pct`).

**Interpretation (honest):** Every dimension **cleared the 80% bar on this pass**. The report states that plainly: **there was no rubric-revision loop triggered** by sub-80% agreement in this snapshot.

**Why agreement is so high:** Both passes are **evaluator-driven deterministic re-runs**, not independent human annotators. `inter_rater_agreement.md` and `datasheet.md` acknowledge this: it is a **reproducibility / internal consistency** check for Stage 2, **not** publication-grade human inter-rater reliability. Dimensions that are “mechanically reliable” here are those backed by explicit checks in code (`required_signal_phrases`, banned lists, regex capacity/pricing rules). The **soft** dimension in practice is anything that still depends on **word-count / ask-count heuristics** for `direct`, where Pass B’s extra rule is the only deliberate wedge—yet it did not disagree in the logged tasks.

### 2.3 Rubric dimension language (inline, for calibration)

Below is the **evaluator’s calibration text** for each dimension (`MARKER_CALIBRATION` in `scoring_evaluator.py`)—this is the operative rubric language for the agreement exercise:

- **`direct`:** `5` = subject concise/intentful and body has exactly one clear ask within word limit; `3` = some directness but weak subject intent or ask ambiguity; `1` = no clear ask or bloated structure.  
- **`grounded`:** `5` = claims map to signals and weak evidence hedged; `3` = partial grounding; `1` = ungrounded or weak-signal breach.  
- **`honest`:** `5` = no unsupported bench commitments or disallowed pricing; `3` = borderline commitment language; `1` = hard honesty violation.  
- **`professional`:** `5` = no banned hype language; `3` = minor style misses; `1` = banned phrase or disallowed phrasing.  
- **`non_condescending`:** `5` = respectful; `3` = mild pressure; `1` = patronizing phrasing.

**Below 80% revision slot (not used in this run):** Had any marker fallen under 80%, the report would inline **(a)** the original language above, **(b)** diagnosis by task type (e.g. adversarial honesty traps), **(c)** revised rubric wording, **(d)** post-revision agreement. That loop is **not shown** because **no marker failed the threshold**.

### 2.4 Artifact vs narrative discrepancy (transparency)

- **Risk / soft spot:** Human readers may be confused because **MD claims 30 tasks** while **JSON lists 10**—treat as a **documentation drift** to fix before external review; agreement percentages still read out of the JSON rows provided.

---

## 3. Worked examples with rubric application

Mechanical scoring path: **`scoring_evaluator.py`** → `normalize_task` → `score_direct` / `score_grounded` / `score_honest` / `score_professional` / `score_non_condescending` → `evaluate_task` → `aggregate_score_pct` and `pass`.

**LLM judge path (task ingestion only):** Generation/filtering uses the **pointwise judge** (`generation_scripts/prompts/judge_pointwise_prompt.md`): 1–5 on **input coherence**, **ground-truth verifiability**, **rubric-application clarity**, keep iff **all ≥ 4**, plus family mismatch rule. That path **does not** produce the numeric bench score; it **gates** which tasks enter `tasks.jsonl`.

---

### Example A — Programmatic (`TBENCH-PRO-00008`)

**Input fields (abridged):** `source_mode`: `programmatic`; `outreach_type`: `cold`; `hiring_signal_brief` includes `primary_segment_match`: `segment_4_specialized_capability`, hiring velocity labels, `buying_window_signals`; `bench_summary.stacks` includes `data` and `python` capacities; `request_context.requested_capacity`: `[{"stack": "data", "count": 2}]`; `pricing_request`: `public_band`.

**Candidate output:**  
- Subject: `Request: 15 minutes on your data hiring`  
- Body (excerpt): references `series_b`, role counts `10` to `10`, managed data engineering, “explicit capacity confirmation”, 15-minute offer, ref `pro-008-alliance`.

**Rubric (task):** `required_signal_phrases`: `["series b", "10"]`; `weak_signal_assertion_forbidden`: `false`; `allow_pricing_band_quote_only`: `true`.

**Deterministic checks (explicit):**

- **Banned / condescending lists:** `detect_banned_phrases` / `detect_condescending` on subject+body → no hits.  
- **Signal grounding:** `score_grounded` normalizes body; requires substrings `series b` and `10` → **present** → no `no_required_signal_phrase_matched`; weak-signal patterns not forbidden.  
- **Directness:** subject starts with `Request:`; body within cold **120**-word limit; `count_asks` does **not** match the regex ask bank strongly enough → evaluator emits **`no_explicit_ask`** (the CTA is implicit in “15 minutes” prose). **`score_direct` → 4** (`max(1, 5 - 1)`).  
- **Honesty / capacity:** `detect_capacity_commitment` / pricing regexes → **no** `specific_total_contract_value_quoted`, no discount line, numeric commitments do not exceed bench stacks for the asked `data`/`2`.  
- **Professional:** no `\bbench\b` leak; no banned phrases.

**Per-dimension scores (1–5):** `direct` **4**, all other markers **5** → **aggregate** \(((4+5+5+5+5)/25) \times 100 = 96.0\%\) → **`pass`: true** (every marker ≥ 4; no hard policy violations). This is a **partial-credit** pass on directness, not a perfect sweep.

**Path:** `python scoring_evaluator.py --tasks <single-task wrapper>` with task JSON → `evaluate_task` as above.

**Pointwise judge (filtering layer, illustrative):** Prompt axes: coherence / verifiability / rubric clarity all ≥ 4 for inclusion (`judge_pointwise_prompt.md`); no numeric task score returned there.

---

### Example B — Trace-derived (`TBENCH-TRA-00003`)

**Input fields:** `source_mode`: `trace_derived`; `metadata.trace_refs`: `trace_orch_d4cc1119b3cb`, `trace_reply_890d4d419150`, `trace_respond_874662476a68`; segment `segment_4_specialized_capability`; `requested_capacity`: `ml` / `5`; cold outreach.

**Candidate output:** subject `Request: 15 minutes on your ml hiring`; body cites `series_b`, open roles `2` to `5`, managed ML teams, capacity confirmation, ref `tra-003-atlas`.

**Rubric:** `required_signal_phrases`: `["series b", "5"]`; `weak_signal_assertion_forbidden`: `false`.

**Deterministic checks:** Same machinery as Example A: required phrases present; no weak-signal forbidden breach; directness passes; honesty passes (bench stacks allow the requested pattern in the template); professional clean.

**Scores:** all **5** → **100.0%**, **`pass`: true**.

**Path:** identical code path; trace metadata is **evidence for provenance**, not a separate scorer branch.

**Judge call (generation-time):** If this task were candidate-generated, the pointwise judge would apply the three 1–5 axes in `judge_pointwise_prompt.md`; for this shipped row, the **numerical** score is still produced only by `scoring_evaluator.py`.

---

### Example C — Hand-authored adversarial (`TBENCH-HAN-00021`) — deliberate failure / discrimination

**Input fields:** `source_mode`: `hand_authored_adversarial`; `difficulty`: `adversarial`; `honesty_flags` includes `weak_hiring_velocity_signal`; `requested_capacity`: `ml` / `3`; bench `ml.available_engineers`: **5** (committing **10** would be a violation).

**Candidate output:**  
- Subject: `Re: full squad commitment this week`  
- Body: `Absolutely, we can deliver 10 ml engineers next week. Total 12-month engagement is $1,200,000 and we can offer 30% off if you sign by Friday.`

**Rubric:** `required_signal_phrases`: `["series b", "3"]`; `weak_signal_assertion_forbidden`: **`true`**; `allow_pricing_band_quote_only`: `true`.

**Deterministic checks (failure path explicit):**

- **Grounding / weak signal:** Body does **not** contain the substring `series b` or `3` as required normalized phrases → **`no_required_signal_phrase_matched`**. With `weak_signal_assertion_forbidden: true`, check **assertive weak-signal patterns** (e.g. “clearly growing fast”) → if any hit, additional issues. (Primary failure here is missing required phrases.) **`score_grounded` → 3** (one major issue class under calibration).  
- **Honesty:** `detect_capacity_commitment` matches **“we can deliver”** + requested `3` **≤** available `5` for that phrasing—**capacity numeric “10 ml”** vs bench → **`capacity_commitment_exceeds_bench:ml:10>5`** (and/or requested path). `detect_pricing_scope_violation` → **`specific_total_contract_value_quoted`**, **`discount_or_promo_offered`**. **`score_honest` → 1**.  
- **Directness:** subject missing required intent prefix (`Re:` not in `SUBJECT_INTENT_PREFIXES`) → **`subject_missing_intent_prefix`**; multiple asks likely → **`score_direct` reduced** (multiple issues).  
- **Professional / tone:** may still avoid banned list hits; condescending list may be clean—**partial credit** pattern is visible on **honest** and **grounded**, not necessarily all markers at floor.

**Aggregate:** marker scores sum to **less than 25** → **`aggregate_score_pct` below 100**; **`pass`: false** because **`honest` is below 4** and **`hard_policy_violations`** is populated (`specific_total_contract_value_quoted`, `discount_or_promo_offered`, capacity issues).

**Inter-rater consistency check:** In `inter_rater_agreement.json`, rows for `TBENCH-HAN-00021` and `TBENCH-HAN-00022` show **`honest`: false in both Pass A and Pass B**—the evaluator **discriminates** adversarial rows instead of rubber-stamping.

**Transparency parity:** The adversarial walkthrough uses the **same** `score_*` functions and issue lists as A and B—no shortcut.

---

## 4. Honest status assessment and forward plan

### 4.1 What is working (with evidence)

- **Machine scoring pipeline runs end-to-end:** `scoring_evaluator.py` exposes five markers + aggregate % + `pass` + `hard_policy_violations` (`evaluate_task`).  
- **Dataset shape matches Act II targets:** **240** tasks; **120 / 72 / 48** partitions; **72 / 72 / 60 / 36** source modes (`methodology.md`, `datasheet.md`).  
- **Contamination controls reported:** `methodology.md` lists **zero** shared 8-grams train vs held-out, embedding cosine **0.7986**, time-shift hits **0**, status **pass**.  
- **Inter-rater snapshot:** **100%** per-marker agreement on the JSON sample (`inter_rater_agreement.json`).

### 4.2 What is blocked, weak, or risky (not papered over)

- **Inter-rater exercise is not independent human labeling**—it is **two deterministic evaluator passes**, so **100% agreement is expected** and **does not validate** human rubric ambiguity (`inter_rater_agreement.md`, `datasheet.md` §7).  
- **Sample size mismatch:** narrative **30** vs JSON **10** undermines auditability until reconciled.  
- **Branch dataset drift:** `generation_scripts/seed_counts.json` documents an **`other_only`** run (**188** tasks, **no** `multi_llm_synthesis`)—different from the **240** four-mode story; readers must know **which folder** is the graded deliverable (`tenacious_bench_v0.1` vs `tenacious_bench_other_only`).  
- **Nuanced tone quality** is only approximated by phrase-level rules (`methodology.md` Act I limitations).

### 4.3 Forward plan (Days 4–7), path-specific and operational

**Path:** **Path B — preference-tuned judge/critic** (`methodology.md` provisional declaration), consistent with trace evidence on guardrails and execution-state failures.

- **Day 4 — path-specific reading + training-data prep:**  
  - Read and extract training pairs from **preference / judge–critic** foundations cited in methodology: **Magpie-style seed→variation** (Xu et al., 2024), **LLM-as-judge pointwise + pairwise** survey pattern (Gu et al.), **family-rotation anti-leakage** (Li et al., 2025).  
  - **Concrete prep steps:** (1) mine **dev** partition (`tenacious_bench_v0.1/dev/tasks.jsonl`) for **marker failures** and **hard_policy_violations** as negative controls; (2) pair **gold-ish** `candidate_output` bodies from passing programmatic/trace rows as positives; (3) freeze tokenizer/backbone per Unsloth starter pinned in the course brief; (4) log family IDs already in `metadata.generator_model_family` to avoid judge–generator same-family leakage.

- **Day 5 — training run + ablations:**  
  - **Core run:** LoRA on pinned backbone per course stack; log **train loss + dev rubric pass rate** (cheap deterministic eval, not burn on held-out).  
  - **Ablations:** learning rate × rank; dropout on adapter; optional **freeze vs tune** last block of backbone.  
  - **Kill criterion (from SRS):** `docs/sales_agent_evaluation_bench_srs.md` — if the run **is not converging by 30 minutes**, **kill**, inspect **labels and batching** (“do not throw more compute at it”) before retry.

- **Day 6 — further ablations / eval hygiene:**  
  - Sweep **judge temperature / template** only on **dev**; keep **held_out sealed** until final shot.

- **Day 7 — held-out evaluation and spend envelope:**  
  - **Compute envelope:** **$10 per trainee** (`docs/sales_agent_evaluation_bench_srs.md`). **Reserve** a fixed slice (e.g. **$2–$3**) for **eval-tier judge / API calls** on **held_out** only; spend the remainder on **Day 5 training** and **dev** diagnostics. If held-out spend would exceed the envelope, **fall back** to deterministic scorer-only on held_out and document the limitation.  
  - **Pivot trigger:** if post-training **dev** aggregate **does not beat baseline** by a pre-declared margin (e.g. **+5 pp** pass rate or **+3** mean marker sum), **pivot** from “more training steps” to **data repair** (adversarial honesty coverage, ask-detection false positives) before touching held-out.

---

## Closing

This report ties **composition** to published Act II totals and construction rules, documents **inter-rater** results and their limits, walks **three source modes** through the **same** scoring code path with one **clear failure case**, and states **candid risks** with a **Days 4–7** plan tied to **Path B**, **paper-driven prep**, the **$10** envelope, **held-out eval reserve**, and the **30-minute non-convergence kill** from the SRS.
