# Tenacious Sales Agent Evaluation Bench (Week 11)

## Project Purpose (Simple Explanation)
This project is about proving whether a sales AI agent actually works for Tenacious, not just on generic public benchmarks.

In Week 10, the agent could generate outreach and handle sales workflows. In this week, the goal is to:
1. Build a **Tenacious-specific evaluation benchmark** (dataset + scoring rules).
2. Train one small model component to fix a real failure mode.
3. Measure improvement with proper ablations and statistical confidence.
4. Publish reproducible artifacts (dataset, model/judge if applicable, technical write-up, community contribution).

The core idea is: **build the bench, test the agent on the bench, improve the agent, and publish evidence**.

## What Should Be Done (Step-by-Step)

### Step 0: Pre-flight setup
1. Confirm tooling: Python environment, Hugging Face token, OpenRouter key, and training environment (Colab/RunPod).
2. Verify Week 10 artifacts exist and are readable (traces, probes, taxonomy).
3. Initialize cost tracking (all API + compute spend logged).
4. Draft initial path declaration (A, B, or C).

### Step 1: ACT I - Audit and Schema Design
1. Audit where generic benchmarks miss Tenacious-specific sales quality.
2. Use Week 10 probes and traces as evidence for those gaps.
3. Design a machine-verifiable benchmark schema (inputs, output, rubric, score logic).
4. Implement a scoring evaluator script and test on sample tasks.

Output: `audit_memo.md`, `schema.json`, `scoring_evaluator.py`, early `methodology.md`.

### Step 2: ACT II - Dataset Authoring
1. Build 200-300 tasks using four sources:
   - trace-derived,
   - programmatic sweeps,
   - multi-LLM synthesis,
   - hand-authored adversarial tasks.
2. Filter generated tasks with judge checks.
3. Partition dataset into train/dev/held-out (50/30/20).
4. Run contamination checks (n-gram, embedding similarity, time-shift).
5. Run inter-rater agreement process and revise rubric if needed.
6. Write full datasheet.

Output: `tenacious_bench_v0.1/`, `datasheet.md`, generation scripts/logs, contamination report, inter-rater agreement report.

### Step 3: ACT III - Method Selection and Training Data Prep
1. Finalize path choice:
   - Path A: SFT generator component,
   - Path B: preference-tuned judge/critic,
   - Path C: process reward model.
2. Convert training partition into path-specific format.
3. Apply leakage and contamination safeguards.
4. Document rationale from Week 10 evidence + paper citations.

Output: `training_data/`, `methodology_rationale.md`, updated contamination checks.

### Step 4: ACT IV - Train, Ablate, Measure
1. Run one core LoRA training job.
2. Evaluate on sealed held-out with required ablations:
   - Delta A: trained vs Week 10 baseline,
   - Delta B: trained vs prompt-only intervention,
   - Delta C: compare with Week 10 retail benchmark score (if already available),
   - cost/latency Pareto.
3. Compute confidence intervals and significance.
4. Save traces, metrics, and run logs.

Output: `ablation_results.json`, `held_out_traces.jsonl`, training logs, model card (if applicable).

### Step 5: ACT V - Publish and Engage
1. Publish dataset to Hugging Face with datasheet + license.
2. Publish adapter/model (if Path A or C) with model card.
3. Publish technical blog post with honest results (including negative findings).
4. Submit one community artifact (issue/PR/submission).
5. Deliver two-page executive memo and demo video.

Output: public URLs, `memo.pdf`, `evidence_graph.json`, final repo completion.

## Expected Deliverables

### Interim (Wednesday, 21:00 UTC)
1. Audit, schema, evaluator.
2. Dataset partitions with datasheet.
3. Contamination output + inter-rater agreement.
4. Methodology draft + early synthesis memos.

### Final (Saturday, 21:00 UTC)
1. Training data + training scripts/logs.
2. Ablation and held-out results with significance.
3. Public dataset/model/blog/community artifact URLs.
4. Two-page memo, demo video, evidence graph.

## Decision Points Requiring Your Confirmation
This repo includes a recommended plan in `docs/implementation_plan.md`, but these choices should be confirmed by you:
1. Training path (A/B/C).
2. Community engagement route (GitHub issue vs PR vs workshop/community submission).
3. Compute strategy (Colab-only vs Colab with RunPod fallback).

See the implementation plan for options and recommendations.
