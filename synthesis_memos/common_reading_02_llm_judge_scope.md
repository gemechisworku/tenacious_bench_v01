# Synthesis Memo 02: A Survey on LLM-as-a-Judge (Gu et al., 2024/2025)

## Paper Design Choice I Disagree With
The survey's practical framing (sections on usage patterns and reliability) encourages broad use of LLM judges as scalable evaluators across large candidate pools. I disagree with applying "judge everywhere" in Tenacious-Bench v0.1.

## My Position
Judge scope should be selective: use LLM judging where it is most needed (multi-LLM synthesis), and bypass it where deterministic or source-grounded paths are sufficient (trace-derived, programmatic, hand-authored adversarial in our interim build).

## Why I Disagree (With Week 10/11 Evidence)
The key failure pattern in Week 10 was not "we lack any judge at all"; it was that specific mechanism failures (state, policy, commitment safety) were under-measured by generic benchmarks. That means we should spend judge budget where ambiguity is highest, not uniformly.

Week 10 anchors:
1. `trace_respond_874662476a68`: channel-policy boundary.
2. `trace_advance_2ef64021c4f8`: invalid lifecycle transition.
3. `trace_schedule_book_2dc2d85ac0fc` and `trace_slots_fail`: booking path brittleness.
4. `trace_orch_d4cc1119b3cb`: correct abstention case that deterministic checks can preserve.

Week 11 pipeline evidence:
1. Early smoke behavior showed extremely high call inflation when judge was applied broadly (`43` calls for a tiny run).
2. After narrowing judge scope to synthesis-only plus calibration, the same style of small test dropped to `6` calls with successful completion, lower cost, and no run instability.
3. Non-synthesis categories remained structurally valid because they are generated from trace/programmatic/adversarial paths tied to explicit rubric fields rather than unconstrained generation.

These numbers indicate that blanket judging was a poor cost-quality tradeoff for this benchmark stage.

## Reliability and Leakage Considerations
The survey discusses judge bias and reliability risks; I agree. My disagreement is about where to pay the reliability tax:
1. For synthesis, I retained pointwise plus pairwise judging and model-family rotation.
2. For non-synthesis, I prioritized deterministic checks and source controls because their ambiguity is lower and provenance is stronger.

This design still respects leakage constraints from the challenge spec: generator/judge family separation is enforced where judging occurs.

## Counterfactual I Rejected
I rejected "uniform judge pass over all tasks" for three reasons:
1. Cost/latency overhead materially reduced iteration speed during authoring.
2. Operational risk increased (timeouts/retries in preflight and run-time).
3. It did not improve diagnostic value proportionally on trace/programmatic slices.

## What I Kept From the Paper
I retained three survey-aligned practices:
1. Structured rubric decomposition (marker-wise scoring).
2. Explicit logging for judge outputs and failure reasons.
3. Calibration sample with a stronger judge tier.

So the disagreement is targeted: not "no LLM judge," but "LLM judge where uncertainty is highest." In this project, synthesis outputs are the uncertainty-heavy slice; that is where LLM-as-a-judge adds the most value per dollar and per minute.

