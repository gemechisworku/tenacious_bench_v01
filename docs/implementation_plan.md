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

### Phase 3.1: Finalize Path and Rationale
1. Confirm selected path (A/B/C).
2. Complete path-specific reading memos.
3. Write one-page method rationale citing Week 10 trace evidence + paper references.

### Phase 3.2: Training Data Conversion
1. Path A: chat-format instruction pairs, quality filtered.
2. Path B: chosen/rejected preference pairs with leakage controls.
3. Path C: step-level trajectory labels for process scoring.

### Phase 3.3: Data Integrity Checks
1. Re-check contamination boundaries vs held-out/dev.
2. Validate schema conformance and sampling balance.

Deliverables:
1. `training_data/`
2. `methodology_rationale.md`
3. Updated contamination verification output

## ACT IV - Train, Ablate, Measure (Stage 4)

### Phase 4.1: Core Training Run
1. Execute one LoRA run on selected backbone.
2. Capture hyperparameters, seed, loss curves, runtime.
3. Stop early and debug data if non-convergent behavior appears.

### Phase 4.2: Required Ablations
1. Delta A: trained component vs Week 10 baseline on held-out.
2. Delta B: trained component vs prompt-only variant.
3. Delta C: compare to existing Week 10 retail benchmark score (if available, no re-run).
4. Cost/latency comparison with and without trained component.

### Phase 4.3: Statistical Validation
1. Use paired bootstrap for confidence intervals.
2. Record significance targets (p < 0.05 where applicable).
3. Store raw traces mapped to aggregate claims.

Deliverables:
1. `ablation_results.json`
2. `held_out_traces.jsonl`
3. `training_run.log`
4. `model_card.md` (if Path A or C)

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
