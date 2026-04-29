# Methodology (Draft, Act I)

## Scope
This document captures the Stage 1 (Act I) benchmark methodology for Tenacious-Bench v0.1: audit evidence, schema assumptions, evaluator behavior, and provisional training-path declaration.

## Evidence Base Used
- `week_10_artifacts/failure_taxonomy.md`
- `week_10_artifacts/probe_library.md`
- `week_10_artifacts/trace_log.jsonl`
- `tenacious_sales_data/schemas/*.json`
- `tenacious_sales_data/seed/bench_summary.json`
- `tenacious_sales_data/seed/pricing_sheet.md`
- `tenacious_sales_data/tenacious_style_guide.md`

## Stage 1 Decisions
1. Benchmark tasks must include both writing-quality and operational-safety checks.
2. Scoring must be machine-verifiable first; LLM-judge scoring can be layered later for nuanced tone calibration.
3. Act I schema uses deterministic fields required for:
- directness (word-count, one ask, subject intent),
- grounding (required signal phrase coverage),
- honesty (weak-signal assertion rules, bench/pricing limits),
- professional tone (banned phrase policy),
- non-condescending framing.

## Provisional Path Declaration
`Path B (preference-tuned judge/critic)` is selected provisionally for Act I planning and will be confirmed in Act III.

Rationale from Week 10 traces:
1. `trace_respond_874662476a68` shows policy boundary enforcement matters at inference time (channel block).
2. `trace_advance_2ef64021c4f8` shows execution-state failures that a critic layer can catch before commit.
3. `trace_schedule_book_2dc2d85ac0fc` and `trace_slots_fail` show operational errors where reject/route behavior is more useful than purely better wording.

This evidence suggests inconsistency and guardrail adherence are primary failure drivers, which aligns with Path B.

## Probe-to-Schema Mapping (Initial)
1. `SIG-001`, `SIG-003`, `REL-001`: weak-signal assertion checks in rubric.
2. `BEN-001`, `BEN-002`, `DCC-003`: bench and pricing commitment checks.
3. `TON-004`, `GAP-002`: banned/condescending language filters.
4. `SCH-001`, `DCC-001`: operational safety checks to be expanded in Act II task design.
5. `MTL-001`, `MTL-004`: thread-isolation checks, to be represented as multi-thread input tasks in Act II.

## Trace IDs Referenced in Act I
1. `trace_orch_d4cc1119b3cb` (low-confidence abstention behavior; positive control)
2. `trace_outreach_draft_095b8708f72e` (high prompt token load; cost risk signal)
3. `trace_reply_890d4d419150` (reply routing flow with scheduling branch)
4. `trace_respond_874662476a68` (policy-blocked channel action)
5. `trace_advance_2ef64021c4f8` (invalid state transition)
6. `trace_schedule_book_2dc2d85ac0fc` (booking failure)
7. `trace_slots_fail` (upstream source unavailable)
8. `trace_mem_get_03bdfa202017` and `trace_outreach_ae9e643c953b` (lead memory/draft lookup failures)

## Act I Limitations
1. Current evaluator is deterministic and intentionally conservative; nuanced rhetorical quality is approximated via phrase-level checks.
2. Multi-thread leakage and timezone ambiguity checks are only scaffolded in schema and will be fully authored in Act II tasks.
3. Statistical calibration of evaluator thresholds is deferred to Act II inter-rater loop.

## Next (Act II Entry Criteria)
1. Use this schema and evaluator as baseline for authoring 200-300 tasks.
2. Add per-task metadata for source mode and difficulty.
3. Introduce contamination checks and inter-rater reliability procedure.
