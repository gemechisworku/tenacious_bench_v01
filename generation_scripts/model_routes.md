# Model Routes and Authoring Modes (Stage 2)

This file documents the routed authoring + judge policy implemented in `build_stage2_dataset.py` using OpenRouter-backed model calls.

## Authoring Modes and Shares
1. `trace_derived` (~30%)
2. `programmatic` (~30%)
3. `multi_llm_synthesis` (~25%)
4. `hand_authored_adversarial` (~15%)

## Generator Routing Policy
1. `trace_derived`
- Source: `week_10_artifacts/trace_log.jsonl`
- Generator path: `trace_restructure`
- Generator family: `trace_human_source`

2. `programmatic`
- Source: parameter sweeps across segment, confidence, stack, requested count, and outreach type.
- Generator path: `parameter_sweep`
- Generator family: `template_engine`

3. `multi_llm_synthesis`
- Hard seeds path: `frontier_seed`
- Frontier generator family: `claude_family`
- Bulk variation path: `cheap_variation`
- Cheap generator family: `qwen_deepseek_family`

4. `hand_authored_adversarial`
- Source: `probe_library.md` + `failure_taxonomy.md`
- Generator path: `manual_adversarial`
- Generator family: `human_author`

## Judge Pipeline
### Pointwise judge
All candidates are scored 1-5 on:
1. `input_coherence`
2. `ground_truth_verifiability`
3. `rubric_application_clarity`

Threshold:
- accept only when all dimensions are `>=4`.

Judge tiers:
1. cheap tier for high-volume filtering (configured by `--cheap-judge-model`)
2. eval tier for calibration sample only (configured by `--eval-judge-model`)

### Pairwise judge
When two synthesis candidates are similar, pairwise comparison selects the more diagnostic candidate and drops the weaker one.

Pairwise output is logged with:
1. winner/loser task ids
2. synthesis paths
3. reason and diagnostic scores

## Preference Leakage Protection
Policy:
1. a task may not be judged by the same model family that generated it
2. family mismatch is enforced in code (`no_leakage_ok`)
3. script fails fast if cheap-generator and cheap-judge come from the same provider family

## Calibration Policy
1. eval-tier calibration sample size: 50 tasks
2. eval calibration logs written to `generation_scripts/eval_calibration_log.jsonl`

## Prompt Files
1. `generation_scripts/prompts/generator_frontier_seed_prompt.md`
2. `generation_scripts/prompts/generator_bulk_variation_prompt.md`
3. `generation_scripts/prompts/judge_pointwise_prompt.md`
4. `generation_scripts/prompts/judge_pairwise_prompt.md`

## Logs
1. `generation_scripts/judge_filter_log.jsonl`
2. `generation_scripts/judge_pairwise_log.jsonl`
3. `generation_scripts/eval_calibration_log.jsonl`
4. `generation_scripts/seed_counts.json`
