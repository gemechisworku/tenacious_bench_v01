# Act I Audit Memo (Tenacious-Bench v0.1)

Public benchmarks do not grade the failure modes that matter most for Tenacious sales execution: confidence-calibrated claims, bench-safe commitments, and thread-safe operational behavior.

Explicit contrast with a named public benchmark: **τ²-Bench retail** primarily measures broad task completion and tool-use success under generic workflows, while Tenacious-Bench must additionally score sales-policy dimensions that retail does not directly encode: weak-signal softening, no unsupported capacity or pricing commitments, channel-policy legality, and thread/state consistency across outreach actions.

Week 10 evidence shows this gap clearly. The probe replay in `week_10_artifacts/failure_taxonomy.md` reports an overall trigger rate of `76/280 (27.14%)`, with high-risk categories concentrated in outreach trust and execution safety. The largest buckets were `MTL-*` (multi-thread leakage, `32.5%`), `SIG-*` (hiring-signal over-claiming, `31.25%`), `BEN-*` (bench over-commitment, `29.17%`), and `GAP-*` (gap over-claiming, `29.17%`).

The same pattern appears in trace behavior. In `trace_orch_d4cc1119b3cb`, enrichment correctly abstains at low segment confidence (`0.35`) and low AI maturity confidence (`0.35`), which is good behavior we must preserve. But nearby traces show reliability and control failures that generic language benchmarks ignore:

- `trace_advance_2ef64021c4f8`: invalid state transition (`brief_ready -> booked`).
- `trace_respond_874662476a68`: policy-blocked channel action (SMS restriction violated).
- `trace_schedule_book_2dc2d85ac0fc`: booking failure on unavailable slot.
- `trace_slots_fail`: external scheduling source unavailable (Cal.com lookup failure).
- `trace_mem_get_03bdfa202017` and `trace_outreach_ae9e643c953b`: lead memory/draft lookup failures for the same unknown lead, indicating state/data coupling risk.

Cost also matters. `trace_outreach_draft_095b8708f72e` shows a first-touch draft call with `7490` prompt tokens. That is not automatically wrong, but it is exactly the type of context-bloat pattern that `COST-*` probes target and that a sales benchmark should measure.

Probe-level coverage further supports a Tenacious-specific benchmark design. The following probes are directly business-critical and underrepresented in generic evals: `ICP-001`, `ICP-003`, `SIG-001`, `SIG-004`, `BEN-001`, `BEN-002`, `TON-004`, `MTL-001`, `SCH-001`, `GAP-002`. Together they test segment precedence, confidence-aware phrasing, bench constraints, re-engagement tone, thread isolation, timezone clarity, and non-condescending competitor framing.

Therefore, Tenacious-Bench v0.1 should use machine-verifiable scoring over five markers aligned to the style guide:

1. Direct: length bounds, one ask, intentful subject.
2. Grounded: at least one claim mapped to provided signal evidence.
3. Honest: weak-signal softening and no unsupported capacity/pricing commitments.
4. Professional: banned-phrase exclusions and no external "bench" phrasing.
5. Non-condescending: no "behind/catch-up" framing.

This benchmark must also include operational safety checks that are not pure writing quality: channel-policy compliance, state-transition validity, and scheduling-time ambiguity handling. A model can write fluent outreach and still fail Tenacious sales operations.

Conclusion: the benchmark gap is not linguistic polish; it is evidence calibration plus execution safety under real sales constraints. Tenacious-Bench should prioritize those failure mechanisms first, then optimize generation quality within those boundaries.
