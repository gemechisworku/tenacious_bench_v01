# Implementation Plan (ACT I-V)

## Objective
Deliver a Tenacious-specific sales evaluation benchmark, train one targeted model component, prove measurable lift with statistical rigor, and publish reproducible public artifacts.

## Guiding Constraints
1. Strong adherence to ACT I-V from `docs/sales_agent_evaluation_bench_srs.md`.
2. Cost discipline (target total compute + API spend within the program envelope).
3. Machine-verifiable scoring and contamination-safe held-out evaluation.
4. Reproducibility first: scripts, fixed seeds, logs, and evidence mapping.

## Decision Checkpoints (Need Your Confirmation)

### Decision 1: Training Path
Options:
1. Path A - SFT generation component.
Brief: Best for tone/grounding phrasing quality improvements.
2. Path B - Preference-tuned judge/critic.
Brief: Best for catching inconsistent or unsafe outputs before send.
3. Path C - Process reward model.
Brief: Best for trajectory-level reliability; highest data-prep complexity.

Recommendation:
1. **Path B (Recommended)** because it is typically most production-relevant for Week 10-style inconsistency failures and gives strong risk-control value with lower training complexity than Path C.

### Decision 2: Community Engagement Deliverable
Options:
1. GitHub issue/discussion on a relevant benchmark repo.
Brief: Fastest, realistic, and high-signal for timeline.
2. Pull request to a benchmark/tooling repo.
Brief: Stronger contribution signal but dependency risk on external maintainer review.
3. Workshop/community submission (NeurIPS/ICLR Tiny Papers/Discord boards).
Brief: Highest upside but longer uncertainty window.

Recommendation:
1. **GitHub issue/discussion (Recommended)** for reliable completion within deadline.

### Decision 3: Compute Strategy
Options:
1. Colab T4 only.
Brief: Lowest cost, but session interruptions may slow late-stage reruns.
2. Colab T4 + RunPod fallback.
Brief: Better schedule protection if training reruns are needed.

Recommendation:
1. **Colab + RunPod fallback (Recommended)** for schedule reliability while preserving cost control.

## ACT I - Audit and Schema Design (Stage 1)

### Phase 1.1: Audit Week 10 Evidence
1. Extract at least 8 probe IDs and at least 5 trace IDs tied to concrete failures.
2. Categorize failures by Tenacious dimensions (grounding, tone, pricing scope, bench commitment, etc.).
3. Write a <=600-word audit memo focused on what generic benchmarks miss.

### Phase 1.2: Schema Definition
1. Define task fields: prospect brief, bench summary context, thread history, candidate output, metadata.
2. Define rubric fields for machine scoring (binary/threshold/judge-backed dimensions).
3. Add difficulty tags and source mode metadata.

### Phase 1.3: Scoring Evaluator
1. Implement deterministic checks (banned phrases, word limits, required signal references where applicable).
2. Integrate judge-scored dimensions with thresholds.
3. Validate on three dummy tasks and record expected outputs.

Deliverables:
1. `audit_memo.md`
2. `schema.json` (+ 3 example tasks)
3. `scoring_evaluator.py`
4. `methodology.md` (draft + path declaration)

## ACT II - Dataset Authoring (Stage 2)

### Phase 2.1: Task Generation Pipeline
1. Author tasks across four required modes with target mix:
   - trace-derived (~30%),
   - programmatic sweeps (~30%),
   - multi-LLM synthesis (~25%),
   - hand-authored adversarial (~15%).
2. Log generation mode for each task.

### Phase 2.2: Quality Filtering
1. Run judge filter on coherence, verifiability, rubric clarity.
2. Use pairwise comparison to keep the more diagnostic duplicate candidates.
3. Enforce generation-judge model-family separation to reduce preference leakage.

### Phase 2.3: Partition and Contamination Control
1. Split to train/dev/held-out = 50/30/20.
2. Run contamination checks:
   - n-gram overlap,
   - embedding similarity,
   - time-shift verification.
3. Seal held-out and ensure it is excluded from training scripts.

### Phase 2.4: Reliability and Documentation
1. Perform inter-rater agreement on 30 tasks, relabel after 24 hours.
2. Revise rubric if any dimension is <80% agreement.
3. Complete datasheet with motivation, composition, collection, preprocessing, uses, distribution, maintenance.

Deliverables:
1. `tenacious_bench_v0.1/train/`
2. `tenacious_bench_v0.1/dev/`
3. `tenacious_bench_v0.1/held_out/` (sealed workflow)
4. `datasheet.md`
5. `generation_scripts/` + judge logs
6. `contamination_check.json`
7. `inter_rater_agreement.md`

## ACT III - Method Selection and Training Data Prep (Stage 3)

### Stage 3 Objective
Train a small preference-tuned **critic/judge component** that improves unsafe/inconsistent-output detection before send.

### Why Path B Fits This Repo Best
Week 10 evidence indicates **inconsistency and guardrail failures** more than pure phrasing failures:
1. `trace_respond_874662476a68`: policy-blocked channel action.
2. `trace_advance_2ef64021c4f8`: invalid state transition.
3. `trace_schedule_book_2dc2d85ac0fc` and `trace_slots_fail`: scheduling reliability breakdowns.
4. `trace_mem_get_03bdfa202017` + `trace_outreach_ae9e643c953b`: context/memory coupling failures.

Implication:
1. Path A (generator SFT) would improve wording but does not directly maximize rejection/rollback quality.
2. Path C (process reward model) is high-prep and heavier for timeline.
3. **Path B is best-aligned** to catching "looks fine but should be blocked" outputs at lower training complexity.

### DPO vs SimPO Decision (for Path B)
Options:
1. `DPO` (Rafailov et al., 2023): foundational, strong baseline, but typically uses reference-policy terms.
2. `SimPO` (Meng et al., 2024): reference-free objective using average log-prob reward + margin; lower memory/compute overhead.

Current execution decision (as of 2026-05-01):
1. **DPO (Executed first)** as the primary Stage 3 run.

Reasoning:
1. Dataset size for preference tuning is small-to-moderate (`125` train pairs, `75` dev pairs), where DPO is typically stable and straightforward to tune.
2. The first successful LoRA run has already been completed with DPO and converged.
3. SimPO remains optional as a follow-up ablation if time permits.

Note on ORPO:
1. ORPO (Hong et al., 2024) remains a valid fallback if DPO/SimPO regression behavior appears.

### Phase 3.1 - Freeze Inputs and Leakage Controls
1. Freeze merged dataset snapshot (`tenacious_bench_v0.1/`) and record hash/timestamp.
2. Use only `train/tasks.jsonl` for preference construction.
3. Keep `dev` for calibration and `held_out` strictly sealed.
4. Enforce preference-leakage controls (Li et al., 2025):
   - generator family for rewrites must differ from judge family,
   - avoid same/inherited-family pairings for chosen/rejected labeling,
   - log model family metadata per pair.

### Phase 3.2 - Build Preference Pairs (Path B Data)
1. Define rejected pool:
   - outputs failing deterministic rubric markers or hard-policy checks.
2. Define chosen pool:
   - corrected rewrites from Week 10 hand-fixes first,
   - then dev-tier rewrite only when hand-fix unavailable,
   - chosen outputs must pass evaluator thresholds.
3. Pairing strategy:
   - same task input, two outputs (`chosen`, `rejected`),
   - preserve failure tag (`SIG/BEN/TON/MTL/SCH`) for stratified sampling.
4. Save as:
   - `training_data/path_b/preferences_train.jsonl`
   - `training_data/path_b/preferences_dev.jsonl`
   - schema: `{task_id, prompt, chosen, rejected, failure_family, source_mode, generator_family, judge_family}`

### Phase 3.3 - DPO LoRA Training Runbook (Executed)
1. Backbone:
   - default: `Qwen2.5-3B-Instruct` (or equivalent open 2B-4B model that fits T4 safely).
2. LoRA config:
   - `r=16`, `alpha=32`, `dropout=0.05`,
   - target modules: attention + MLP projections (`q_proj,k_proj,v_proj,o_proj,up_proj,down_proj,gate_proj`).
3. Training config (initial):
   - optimizer `adamw_8bit`,
   - lr `1e-5` to `2e-5`,
   - epochs `1-2`,
   - effective batch size `8` to `32` via gradient accumulation,
   - max length `1024` (or task-fit cap),
   - fixed seed `42`.
4. Loss/monitoring:
   - DPO objective (`beta` tuned via optional mini sweep),
   - monitor train loss + validation loss.
5. Output artifacts:
   - LoRA adapter only (no full merged model by default),
   - notebook run outputs + `training/config.yaml`,
   - `training/metrics.json`,
   - `training/training_run.log` (or equivalent exported run log).

### Phase 3.4 - Stage 3 Verification Gates
1. Data gate:
   - no held-out task IDs in `training_data/path_b/*`,
   - schema validation passes for all preference rows.
2. Leakage gate:
   - zero same-family generator/judge cases in preference construction logs.
3. Quality gate:
   - chosen/rejected inversion spot-check sample (>=50 pairs) with manual audit notes.

### Stage 3 Deliverables (Submission Shape + Status)
Completed:
1. `training_data/path_b/preferences_train.jsonl`
2. `training_data/path_b/preferences_dev.jsonl`
3. `training_data/path_b/preferences_train_dpo.jsonl`
4. `training_data/path_b/preferences_dev_dpo.jsonl`
5. `training_data/path_b/build_manifest.json`
6. `generation_scripts/build_path_b_preferences.py`
7. `notebooks/DPO_training_unsloth.ipynb` (plus synced copy `notebooks/SimPO_training_unsloth.ipynb`, currently DPO-based)
8. `methodology_rationale.md`
9. Updated `README.md` section: "How to train Path B critic (DPO + LoRA)".

Pending to finalize Stage 3 package in-repo:
1. Sync `training/` artifacts from Colab run:
   - `training/config.yaml`,
   - `training/metrics.json`,
   - `training/training_run.log` (or exported equivalent),
   - adapter directory (e.g., `training/tenacious_path_b_dpo_lora/`).

## Stage 3 Decision Checkpoint (Need Your Confirmation)
### Decision 4: Path B Method
Options:
1. DPO (Selected): stronger canonical baseline, stable on small-to-medium preference sets.
2. SimPO: optional follow-up ablation if time permits.

Recommendation:
1. **DPO first run (completed) + optional SimPO ablation** only if timeline allows.

### Decision 5: Backbone Size
Options:
1. 2B class (fastest, cheapest, lower ceiling).
2. 3B-4B class (Recommended: best balance on Colab/RunPod budget).
3. 7B class (higher ceiling, riskier runtime/cost).

Recommendation:
1. **3B-4B class** for first successful Stage 3 completion.

## ACT IV - Train, Ablate, Measure (Stage 4)

Challenge-aligned schedule:
1. Day 5 morning: run one core LoRA training job and inspect convergence by 30 minutes.
2. Day 5 afternoon + Day 6: run ablations and sealed held-out evaluation passes.

### Phase 4.1: Core Training Run (Day 5 Morning)
Status:
1. Core DPO + LoRA run completed in Colab with convergent train/validation losses.

Acceptance criteria:
1. Wall time target `30-90` minutes.
2. If non-convergent by ~30 minutes, stop and debug data (do not scale compute blindly).
3. Capture hyperparameters, seed, loss curves, and runtime.

### Phase 4.2: Required Ablations (Day 5 Afternoon + Day 6)
1. Delta A: trained model vs Week 10 baseline on Tenacious-Bench held-out.
2. Delta B: trained model vs prompt-engineered intervention on same backbone (no training).
3. Delta C: trained model vs existing Week 10 `tau^2-Bench retail held-out` score (informational only; reuse existing number, no re-run).
4. Cost-Pareto: per-task cost + latency with trained component vs without.

Current status:
1. Delta A: pending.
2. Delta B: pending.
3. Delta C: pending (depends on existing Week 10 retail score availability).
4. Cost-Pareto: pending.

### Phase 4.3: Statistical Validation and Reporting
1. Use paired bootstrap for confidence intervals.
2. Require `95% CI` separation and `p < 0.05` for Delta A significance claim.
3. Write sealed-slice aggregate results to `ablation_results.json`.
4. Write raw scoring traces to `held_out_traces.jsonl`.

ACT IV Deliverables:
1. `ablation_results.json`
2. `held_out_traces.jsonl`
3. `training/training_run.log` (with hyperparameters + loss curves, or equivalent exported run log)
4. `model_card.md` only if Path A or C (not required for Path B)

## ACT V - Publish and Engage (Stage 5)

### Phase 5.1: Public Dataset Release
1. Publish `tenacious_bench_v0.1` to Hugging Face.
2. Include datasheet, license, quickstart, baseline references.

### Phase 5.2: Public Model/Judge Release
1. Publish LoRA adapter/judge artifact as appropriate.
2. Add full model card with limitations and evaluation summary.

### Phase 5.3: Technical Communication
1. Publish 1200-2000 word technical blog with methods and honest findings.
2. Publish one community engagement artifact (per decision checkpoint).

### Phase 5.4: Executive Packaging
1. Produce two-page memo with deployment recommendation + skeptic appendix.
2. Produce evidence graph mapping each numeric claim to source artifacts.
3. Record and publish demo video (<=6 minutes).

Deliverables:
1. Hugging Face dataset URL
2. Hugging Face model URL (if applicable)
3. Blog URL
4. Community artifact URL
5. `memo.pdf`
6. `evidence_graph.json`
7. Final `README.md` status updates

## Timeline-Aligned Milestones

### By Wednesday (Interim)
1. ACT I complete.
2. ACT II mostly complete with partitioned dataset + datasheet + contamination outputs.

### By Saturday (Final)
1. ACT III complete.
2. ACT IV complete with ablations and stats.
3. ACT V complete with public URLs and memo artifacts.

## Execution Risks and Mitigation
1. Risk: Weak synthetic task quality.
Mitigation: tighten judge thresholds, increase adversarial hand-authored slice.
2. Risk: Leakage between generation and judge.
Mitigation: enforce model-family rotation and audit logs.
3. Risk: Held-out contamination.
Mitigation: automated contamination checks on every partition update.
4. Risk: Training lift fails Delta B.
Mitigation: publish honest negative result; treat as method finding, not failure to report.
5. Risk: Time overrun near publication.
Mitigation: prioritize reproducibility and required artifacts over optional polish.

## Sources Used for Stage 3 Method Choice
1. Direct Preference Optimization (Rafailov et al., 2023): https://arxiv.org/abs/2305.18290
2. SimPO (Meng et al., 2024, NeurIPS): https://arxiv.org/abs/2405.14734
3. ORPO (Hong et al., 2024): https://arxiv.org/abs/2403.07691
4. Prometheus 2 (Kim et al., 2024): https://arxiv.org/abs/2405.01535
5. Preference Leakage (Li et al., 2025/2026 version): https://arxiv.org/abs/2502.01534
