# Tenacious-Bench v0.1: A Sales-Agent Evaluation That Prioritizes Policy Reliability Over Demo Fluency

Generic agent benchmarks are useful, but they are usually optimized to answer a different question than the one sales teams need answered in production.

The generic question is:
1. Can the agent complete multi-step tasks with tools?

The sales production question is:
1. Will the agent make safe, honest, high-signal claims under constraints that affect customer trust and revenue risk?

Tenacious-Bench v0.1 was built for the second question.

## 1) The Gap: Why Generic Benchmarks Under-Specify Sales Failures

Benchmarks such as tau^2-Bench are strong for broad agent workflow evaluation, tool use, and task progression. They are not wrong; they are measuring a wider target.

The issue is mismatch, not quality.

In sales outreach, many critical failures are not "can the agent finish the task," but "did the agent violate trust or policy while sounding polished."

### Failure types that matter in sales but are weakly represented in generic evals

1. Confidence calibration failures:
Claiming high certainty from weak signals.

2. Capacity commitment failures:
Implying bench capacity that is not authorized.

3. Pricing-scope failures:
Quoting specific contract values or discount language outside policy.

4. Tone under constraints:
Maintaining non-condescending professional language in 60-120 words while still being specific.

### Example mismatch

A generic benchmark may reward:
1. Correct structure.
2. Correct tool call.
3. "Plausible" final answer.

A sales benchmark should penalize the same output if it says:
1. "We can support all your urgent hires this quarter" when no such capacity is approved.
2. "Your annual contract should be around $X" when pricing precision is disallowed.
3. Promotional language that conflicts with current policy.

This was the motivation for a narrower benchmark: smaller scope, stronger enforcement.

## 2) Audit Method: From Week 10 Failures to Measurable Rubrics

We started with Week 10 probes and traces, then converted failure observations into machine-checkable requirements.

Representative trace patterns that motivated the design:
1. `trace_respond_874662476a68`: policy boundary handling issues.
2. `trace_advance_2ef64021c4f8`: invalid state-transition behavior.
3. `trace_schedule_book_2dc2d85ac0fc` and `trace_slots_fail`: scheduling reliability breakdown.
4. `trace_mem_get_03bdfa202017` and `trace_outreach_ae9e643c953b`: context/memory coupling failures.

### Design rules for the benchmark

1. Machine-verifiable first:
Deterministic rubric markers before subjective scoring.

2. Sealed held-out:
Strict train/dev/held-out separation and contamination checks.

3. Evidence-linked reporting:
Every headline claim must map to a concrete artifact.

4. Publish negative results:
If training loses against a strong prompt baseline, report it directly.

## 3) Dataset Construction: 250 Tasks, Four Generation Modes, One Sealed Held-Out

Tenacious-Bench v0.1 contains 250 tasks:
1. train: 125
2. dev: 75
3. held_out: 50

Authoring mix:
1. trace-derived (~30%)
2. programmatic sweeps (~30%)
3. multi-LLM synthesis (~25%)
4. hand-authored adversarial (~15%)

### Why multiple authoring modes

1. Trace-derived tasks preserve real failure signatures from prior runs.
2. Programmatic sweeps stress known variables (signal strength, segment, ask type) at scale.
3. Multi-LLM synthesis increases lexical diversity and reduces overfitting to one writing style.
4. Hand-authored adversarial tasks target known policy breakpoints directly.

### Quality and leakage controls

1. Model-family separation between generation and judge paths.
2. Pairwise filtering for near-duplicate synthetic candidates.
3. Contamination checks across train vs held-out.
4. Held-out split excluded from training preference construction.

The result is not a "perfect dataset." It is an auditable one.

## 4) Why We Chose Path B (DPO + LoRA) Instead of Path A or Path C

This was a method choice grounded in failure type.

### The three options

1. Path A (SFT generator):
Good for phrasing quality, but less direct for "block this output" behavior.

2. Path B (preference tuning critic/intervention):
Directly optimizes chosen vs rejected behavior for safety and consistency.

3. Path C (process reward model):
Powerful but significantly heavier in data prep and runtime complexity.

### Why Path B fit this project

From ACT III and `methodology_rationale.md`, dominant issues were guardrail and reliability failures, not only style quality. Path B gave the best alignment-to-risk with manageable training complexity.

In practical terms:
1. We had 125 train preference pairs and 75 dev pairs.
2. We needed rapid iteration on Colab-class hardware.
3. We needed a method that can encode "looks fluent but should be rejected."

Path B matched all three.

### Why DPO inside Path B

We selected DPO first, with SimPO/ORPO as alternatives.

1. DPO (Rafailov et al., 2023) is a stable baseline for pairwise preference optimization.
2. SimPO (Meng et al., 2024) is promising and lighter in some settings; we kept it as follow-up.
3. ORPO (Hong et al., 2024) remained a fallback if DPO behavior regressed.

Given dataset size and schedule risk, DPO was the pragmatic first run.

### LoRA choice

LoRA kept adaptation lightweight and reproducible:
1. Lower memory cost.
2. Faster reruns.
3. Adapter-only artifact publishing.

Core setup used:
1. 3B-class Qwen2.5 Instruct variant via Unsloth.
2. Max sequence length 1024.
3. Seed 42.
4. Effective batching via gradient accumulation.

## 5) Paper Grounding Behind the Method Stack

The training and evaluation choices were informed by five key references:

1. DPO (Rafailov et al., 2023): preference optimization without an explicit reward model in the standard RLHF pipeline.
2. SimPO (Meng et al., 2024): reference-free preference objective with a simpler optimization form.
3. ORPO (Hong et al., 2024): monolithic preference optimization as an alternative training path.
4. Prometheus 2 (Kim et al., 2024): practical guidance for evaluator/judge design expectations.
5. Preference leakage analysis (Li et al., 2025): model-family separation rationale between generators and judges.

This project did not attempt a full method bake-off. It selected a practical first path, then preserved room for follow-up ablations.

## 6) Experiment Adjustments That Materially Changed Outcomes

One important lesson: evaluation quality can collapse if the trained component is wired incorrectly, even when training itself is fine.

We found and fixed three major issues in exporter/evaluation flow:
1. Introduced `trained_intervene` mode so trained behavior acts as intervention over baseline drafts.
2. Added strict postprocessing (subject prefix, CTA count, word limit, cleanup/meta-tail stripping, safety normalization).
3. Tightened inference prompt/decoding controls.

This removed a major formatting/directness failure mode that initially obscured real capability.

## 7) Results: Positive Delta A, Negative Delta B

Held-out results (`n=50`):
1. baseline mean score: 93.44 (pass rate 0.86)
2. prompt-only mean score: 100.0 (pass rate 1.0)
3. trained mean score: 97.92 (pass rate 0.82)

Delta A (trained vs baseline):
1. mean diff: +4.48
2. 95% CI: [3.68, 5.44]
3. one-sided p-value: 0.0002
4. significance claim: true

Delta B (trained vs prompt-only):
1. mean diff: -2.08
2. 95% CI: [-3.36, -0.96]
3. one-sided p-value: 1.0
4. "training beats prompt-only": false

Interpretation:
1. Training produced statistically supported lift over the original baseline.
2. Prompt-only intervention remained stronger in this run.

This is not a contradiction. It is a useful boundary on what this training recipe did and did not improve.

## 8) What Did Not Work (and Why We Kept It in the Record)

After resolving directness/format regressions, failures concentrated in hard-policy honesty slices:
1. Capacity over-commitment beyond bench.
2. Specific TCV quoting.
3. Discount/promo language.

These failures matter because they are exactly the kind that can pass superficial fluency checks while creating operational risk.

We kept these negative findings visible for two reasons:
1. They define the next benchmark expansion target.
2. They prevent over-claiming progress from a single aggregate score.

## 9) What Changes in v0.2

Planned next steps:
1. Expand hard-policy adversarial slices for capacity/pricing/promo constraints.
2. Add stricter intervention-time policy controls for high-risk claims.
3. Rerun cost-aware ablations with non-zero cost assumptions.
4. Keep paired bootstrap reporting and explicit non-win disclosure for all comparisons.

## 10) Reproducibility and Artifacts

Public artifacts:
1. Dataset: `<dataset_url>`
2. Model adapter: `<model_url>`
3. Ablation results: `<ablation_results_url>`
4. Held-out traces: `<held_out_traces_url>`
5. Repository: `<repo_url>`

Key local evidence files:
1. `ablation_results.json`
2. `held_out_traces.jsonl`
3. `training/config.yaml`
4. `training/metrics.json`
5. `training/training_run.log`
6. `methodology_rationale.md`

## References

1. Rafailov et al., 2023. Direct Preference Optimization (DPO). https://arxiv.org/abs/2305.18290
2. Meng et al., 2024. SimPO. https://arxiv.org/abs/2405.14734
3. Hong et al., 2024. ORPO. https://arxiv.org/abs/2403.07691
4. Kim et al., 2024. Prometheus 2. https://arxiv.org/abs/2405.01535
5. Li et al., 2025. Preference leakage analysis. https://arxiv.org/abs/2502.01534
