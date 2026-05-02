# Tenacious-Bench v0.1: What Our Sales-Agent Eval Found That Generic Benchmarks Miss

## 1) The Gap

Most standard agent benchmarks score broad tool-use competence, but they under-specify sales-context failures that matter operationally:
1. confidence mismatch against weak hiring signals
2. over-commitment beyond bench capacity
3. pricing/discount language drift
4. tone issues under short-form outreach constraints

Our goal was not a broader benchmark. It was a narrower, higher-signal one for Tenacious-style outbound behavior.

## 2) Audit Method

We started from Week 10 traces and probes, then mapped concrete failures into explicit rubric dimensions and machine-verifiable constraints.

Key design principle:
1. claims should be auditable against artifact evidence
2. held-out evaluation should remain contamination-safe
3. negative results should be preserved, not hidden

## 3) Dataset Construction

Tenacious-Bench v0.1 totals 250 tasks with a 50/30/20 split:
1. train: 125
2. dev: 75
3. held_out: 50

Authoring modes:
1. trace-derived (~30%)
2. programmatic sweeps (~30%)
3. multi-LLM synthesis (~25%)
4. hand-authored adversarial (~15%)

Design choices that mattered:
1. model-family separation between generation and judge paths
2. pairwise filtering for near-duplicate synthetic candidates
3. contamination checks and sealed held-out workflow

## 4) Training Experiment (Path B: DPO + LoRA)

We selected Path B because the dominant failures were guardrail/reliability failures, not only writing quality.

Core training setup:
1. base model family: Qwen2.5-3B instruct variant
2. LoRA adapter training with DPO on preference pairs
3. fixed held-out for final comparison

What changed late in the cycle:
1. exporter intervention mode (`trained_intervene`) replaced generation-style misuse
2. stricter postprocessing prevented format/directness regressions
3. inference controls were tightened for consistency

## 5) Results: Honest Delta A/Delta B

Held-out aggregate:
1. baseline mean score: 93.44
2. prompt-only mean score: 100.0
3. trained mean score: 97.92

Delta A (trained vs baseline):
1. +4.48 mean lift
2. 95% CI [3.68, 5.44]
3. one-sided p=0.0002

Delta B (trained vs prompt-only):
1. -2.08 mean diff
2. 95% CI [-3.36, -0.96]
3. training did not beat prompt-only in this run

This is the central takeaway: training beat the original baseline with statistical support, but not the stronger prompt-only intervention.

## 6) What Did Not Work

After fixing formatting/directness collapse, residual failures clustered in hard-policy honesty:
1. capacity over-commitment
2. specific total contract value claims
3. discount/promo language

These are precisely the slices we need to harden next.

## 7) What’s Next

1. add targeted hard-policy adversarial slices in v0.2
2. improve intervention policy controls for high-risk claims
3. rerun cost-aware ablation with non-zero cost assumptions
4. keep publishing negative findings alongside improvements

## Links

1. Dataset: `<dataset_url>`
2. Model adapter: `<model_url>`
3. Ablation results: `<ablation_results_url>`
4. Traces: `<held_out_traces_url>`
5. Repo: `<repo_url>`
