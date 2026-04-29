# Synthesis Memo 01: Best Practices and Lessons Learned on Synthetic Data for Language Models (Liu et al., 2024)

## Paper Design Choice I Disagree With
The paper's synthesis strategy emphasizes large-scale synthetic generation plus iterative filtering as a primary route to quality gains (discussion in the generation/filtering sections and case studies). I disagree with applying that choice directly to Tenacious-Bench v0.1.

## My Position
For this benchmark, synthetic scale should be constrained, not maximized. The right design is to cap synthesis at the most diagnostic slice and keep trace-derived and hand-authored slices dominant for failure-mode fidelity.

## Why I Disagree (With Week 10/11 Evidence)
Week 10 showed our highest-risk failures are not generic language fluency failures; they are domain-mechanism failures tied to workflow state and operational commitments.

Evidence from Week 10:
1. `trace_advance_2ef64021c4f8` shows an invalid state transition (`brief_ready -> booked`).
2. `trace_respond_874662476a68` shows a policy-blocked channel action.
3. `trace_schedule_book_2dc2d85ac0fc` and `trace_slots_fail` show scheduling fragility when upstream availability fails.
4. `trace_mem_get_03bdfa202017` and `trace_outreach_ae9e643c953b` show thread/data coupling failures.
5. `trace_orch_d4cc1119b3cb` is a positive control where abstention was correct under weak evidence.

These are not failures that synthetic scale alone reliably reproduces. They require context that preserves Week 10 execution semantics. If we over-weight synthetic generation, we dilute the signal we actually need to measure.

Evidence from Week 11 authoring:
1. The audit and taxonomy from `week_10_artifacts/failure_taxonomy.md` showed highest trigger concentration in `MTL-*`, `SIG-*`, `BEN-*`, and `GAP-*` families.
2. Our authoring distribution intentionally constrained synthesis to roughly one quarter and preserved larger trace/programmatic slices, matching where the failures came from.
3. During pipeline tuning, cost/time pressure forced practical discipline: synthesis calls are the expensive bottleneck; preserving non-synthesis fidelity from existing artifacts gave better throughput without removing hard cases.

## Concrete Implementation Consequence
I implemented and retained a four-mode allocation where synthesis remains bounded and targeted:
1. Trace-derived approximately 30%.
2. Programmatic approximately 30%.
3. Multi-LLM synthesis approximately 25%.
4. Hand-authored adversarial approximately 15%.

This is not an anti-synthetic stance. It is a scope decision: use synthetic data where it adds unique diagnostic difficulty, not as the default mass-production mechanism.

## Counterfactual I Rejected
I considered a "synthesis-first" build (majority synthetic + judge filter). I rejected it because:
1. It raised cost/latency quickly.
2. It produced weaker linkage to Week 10 mechanism failures.
3. It increased the chance of benchmark drift toward stylistic artifacts instead of operational safety failures.

## What I Kept From the Paper
I still adopted core lessons from Liu et al.:
1. Strong filtering is mandatory.
2. Diversity of synthesis paths improves candidate quality.
3. Data provenance should be explicit per item.

The disagreement is with default weighting, not with synthetic-data utility. For Tenacious-Bench, fidelity to observed Week 10 failure mechanisms is the dominant objective, and that objective is better served by constrained synthesis plus high-fidelity trace grounding.

