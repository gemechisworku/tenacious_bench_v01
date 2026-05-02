# Tenacious-Bench v0.1 Datasheet

## 1) Motivation
Tenacious-Bench v0.1 exists to evaluate sales-agent behavior that generic benchmarks do not grade reliably: confidence-calibrated signal use, bench-safe commitments, pricing-scope compliance, and tone adherence under outreach constraints.

Primary benchmark goal:
1. Detect Tenacious-specific failure modes from Week 10 evidence (`SIG-*`, `BEN-*`, `TON-*`, `MTL-*`, `GAP-*`).
2. Support measurable before/after evaluation of Week 11 model interventions.

## 2) Composition
Total tasks: `250`

Source-mode composition:
1. `trace_derived`: 75 (30.0%)
2. `programmatic`: 75 (30.0%)
3. `multi_llm_synthesis`: 62 (24.8%)
4. `hand_authored_adversarial`: 38 (15.2%)

Partitions:
1. `train`: 125 (50.0%)
2. `dev`: 75 (30.0%)
3. `held_out`: 50 (20.0%)

Failure-dimension coverage (targeted from Week 10 taxonomy):
1. ICP/segment decision failures (`ICP-*`)
2. Signal over-claiming and reliability mismatch (`SIG-*`, `REL-*`)
3. Bench and pricing commitment failures (`BEN-*`, `DCC-003`)
4. Tone and non-condescending failures (`TON-*`, `GAP-*`)
5. Scheduling/state-control edge cases (`SCH-*`, `DCC-*`)
6. Multi-thread/context leakage (`MTL-*`)
7. Cost-pathology pressure tasks (`COST-*`)

Per-mode typical task examples:
1. `trace_derived`: direct restructuring of a Week 10 trace into a scored outreach task with explicit signal confidence and policy gates.
2. `programmatic`: parameterized sweeps that vary stack, headcount request, confidence, and outreach type from a base failure template.
3. `multi_llm_synthesis`: hard frontier-seed scenario plus cheap-tier lexical variation, followed by pairwise diagnostic selection.
4. `hand_authored_adversarial`: explicit policy-breaking prompts (capacity over-commitment, fabricated pricing certainty, weak-signal assertions).

Task schema includes:
1. input context (`hiring_signal_brief`, `bench_summary`, `request_context`, `prior_thread`)
2. candidate output (`subject`, `body`)
3. machine-verifiable rubric constraints
4. metadata (`source_mode`, `difficulty`, `lexical_tag`, optional trace refs)

## 3) Collection Process
Inputs used:
1. `week_10_artifacts/failure_taxonomy.md`
2. `week_10_artifacts/probe_library.md`
3. `week_10_artifacts/trace_log.jsonl`
4. `tenacious_sales_data/seed/bench_summary.json`
5. `tenacious_sales_data/seed/pricing_sheet.md`
6. `tenacious_sales_data/schemas/*`
7. `tenacious_sales_data/tenacious_style_guide.md`

Generation pipeline:
1. Deterministic scenario synthesis with fixed seed (`42`).
2. Four source-mode routes with target ratios.
3. Multi-LLM synthesis route uses frontier + cheap generators, followed by pointwise and pairwise judge filtering.
4. Non-synthesis routes (trace-derived, programmatic, adversarial) were retained from deterministic/task-authored routes in final build without additional LLM-judge filtering.
5. Two separate finalized runs were merged (synthesis-only + other-only), then globally deduplicated and globally repartitioned to restore one consistent train/dev/held-out split.
6. Partitioning target remains 50/30/20 at merged-dataset level.
7. Contamination checks run on final merged split (held-out versus train).

Merge artifact:
1. `tenacious_bench_v0.1/merge_report.json` documents source run sizes, dedup result, selected split seed, and final counts.

## 4) Preprocessing / Cleaning / Labeling
Preprocessing steps:
1. Normalize domains, timestamps, segment labels, and capacity request fields.
2. Add lexical tags for dedup and auditability.
3. Enforce rubric field presence before acceptance.

Labeling protocol:
1. Machine scoring via `scoring_evaluator.py` using five markers:
`direct`, `grounded`, `honest`, `professional`, `non_condescending`.
2. Hard-policy violations flagged separately (capacity over-commitment, specific TCV quoting, discounting).
3. Synthesis candidates additionally use LLM-judge pointwise/pairwise filtering during authoring.

Inter-rater agreement artifact:
1. Stored in `tenacious_bench_v0.1/inter_rater_agreement.json`.
2. Human-readable summary in `tenacious_bench_v0.1/inter_rater_agreement.md`.
3. Current merged-set snapshot: sample size `30`, overall agreement `100.0%`.

## 5) Uses
Intended uses:
1. Evaluate sales-agent outputs on Tenacious-specific behavioral constraints.
2. Compare baseline versus trained intervention with consistent scoring.
3. Seed preference or SFT data pipelines in later acts.

Out-of-scope uses:
1. Generalized SDR performance ranking across unrelated domains.
2. Legal/compliance conclusions outside the explicit rubric.

## 6) Distribution
Local structure:
1. `tenacious_bench_v0.1/train/tasks.jsonl`
2. `tenacious_bench_v0.1/dev/tasks.jsonl`
3. `tenacious_bench_v0.1/held_out/tasks.jsonl`
4. `tenacious_bench_v0.1/contamination_check.json`
5. `tenacious_bench_v0.1/inter_rater_agreement.json`
6. `tenacious_bench_v0.1/merge_report.json`

Generation and logs:
1. `generation_scripts/build_stage2_dataset.py`
2. `generation_scripts/merge_partial_runs.py`
3. `generation_scripts/seed_counts.json`
4. `generation_scripts/judge_filter_log.jsonl`
5. `generation_scripts/judge_pairwise_log.jsonl`
6. `generation_scripts/eval_calibration_log.jsonl`
7. `generation_scripts/model_routes.md`
8. `generation_scripts/prompts/*.md`

## 7) Maintenance
Update policy for v0.2:
1. Keep the merged global-split workflow whenever partial runs are combined, to prevent cross-run split leakage.
2. Expand thread-leakage and timezone ambiguity slices using additional real traces.
3. Run true 24-hour relabel agreement protocol with manual adjudication notes.
4. Keep held-out sealed and rerun contamination checks on every update.

Known limitations in v0.1:
1. Dataset was generated in two production runs and merged afterward; this is reproducible but adds an extra merge/split step.
2. Inter-rater check is implemented as two deterministic evaluation passes for Stage 2 reproducibility.
3. Failure-dimension counts are coverage-targeted and should be expanded with additional manual adversarial depth in v0.2.
4. Contamination max cosine is reported as `0.85` after rounding in JSON output; internal comparison still satisfied the `< 0.85` pass condition in code.

## Pushkarna Layered Detail
1. Telescopic: this benchmark measures Tenacious-specific sales-agent reliability under grounded outreach constraints.
2. Periscopic: it contains 250 tasks split 50/30/20 with four authoring modes, merged-run reconciliation, and contamination controls.
3. Microscopic: each task stores structured brief fields, request context, candidate output, rubric keys, source mode, difficulty, and lexical trace tag for auditability.

## License
Current intended dataset license: `CC-BY-4.0` for publication.
Rationale: permits open benchmarking reuse while preserving attribution for the benchmark construction work.
