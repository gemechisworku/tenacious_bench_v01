Title:
Proposal: sales-policy reliability slice to complement tau-bench evaluation

Body:

## Summary

I am exploring a benchmark slice for sales-agent reliability where outputs can look fluent but still violate policy constraints. I think this can complement tau-bench by adding a narrower stress test for high-risk outbound messaging behavior.

## Problem Context

In my experiments, strong general agent behavior did not always translate to safe sales behavior. Repeated failure patterns were:
1. overconfident claims from weak signals
2. capacity over-commitment beyond approved bench limits
3. specific pricing/discount language outside policy
4. tone/professional framing failures under short outreach constraints

## Approach

I built `tenacious_bench_v0.1` with:
1. mixed task construction (trace-derived, programmatic, synthesis, adversarial)
2. machine-verifiable rubric constraints focused on directness, grounding, honesty, and tone
3. strict train/dev/held-out split with contamination checks
4. preference-tuning experiment (Path B: DPO + LoRA) for intervention behavior

## Key Findings

Held-out (`n=50`) results:
1. baseline mean score: `93.44`
2. trained mean score: `97.92` (Delta A `+4.48`, 95% CI `[3.68, 5.44]`, one-sided p `0.0002`)
3. prompt-only intervention remained stronger than training in this run (Delta B `-2.08`)

Interpretation:
1. targeted training improved baseline behavior
2. hard-policy slices remained the dominant unresolved failures

## Collaboration Proposal

If useful to maintainers, I can contribute:
1. a compact "sales-policy reliability" subset for discussion
2. failure-tag to rubric-dimension mapping
3. a minimal protocol proposal for evaluating policy-sensitive outbound responses

## References

1. Dataset: `https://huggingface.co/datasets/gemechisw/tenacious_bench_v0.1`
2. Model adapter: `https://huggingface.co/gemechisw/tenacious-pathb-dpo-lora-v0.1`
3. Ablation results: `https://github.com/gemechisworku/tenacious_bench_v01/blob/main/ablation_results.json`
4. Held-out traces: `https://github.com/gemechisworku/tenacious_bench_v01/blob/main/held_out_traces.jsonl`
5. Technical write-up: `https://gemechis1.substack.com/p/tenacious-bench-v01-evaluating-sales`
