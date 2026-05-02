# Tenacious Sales Agent Evaluation Bench (Week 11)

## Overview
This repo builds and evaluates a Tenacious-specific sales-agent benchmark.

Main outcomes:
1. Audit of benchmark gaps from Week 10 evidence.
2. Machine-verifiable schema + scoring evaluator.
3. Authored dataset with `train/dev/held_out` partitions.
4. Routed multi-LLM generation and judge filtering pipeline.

Core artifacts:
1. [audit_memo.md](./audit_memo.md)
2. [schema.json](./schema.json)
3. [scoring_evaluator.py](./scoring_evaluator.py)
4. [methodology.md](./methodology.md)
5. [datasheet.md](./tenacious_bench_v0.1/datasheet.md)
6. [build_stage2_dataset.py](./generation_scripts/build_stage2_dataset.py)
7. [common_reading_01_synthetic_data_tradeoff.md](./synthesis_memos/common_reading_01_synthetic_data_tradeoff.md)
8. [common_reading_02_llm_judge_scope.md](./synthesis_memos/common_reading_02_llm_judge_scope.md)

## Repo Usage
Typical flow:
1. Run Stage 2 generation pipeline (smoke test first).
2. Inspect progress, status, judge logs, contamination check, and cost log.
3. Re-run full dataset generation (240 tasks) once smoke test is stable.
4. Use `scoring_evaluator.py` to evaluate outputs/tasks.

## Directory Map
1. `docs/`: SRS and implementation plan.
2. `week_10_artifacts/`: trace and probe inputs used for benchmark construction.
3. `tenacious_sales_data/`: style/policy/seed data.
4. `generation_scripts/`: dataset generation pipeline + prompts + logs.
5. `tenacious_bench_v0.1/`: generated dataset partitions and reports.
6. `synthesis_memos/`: common-reading memos with paper design disagreements grounded in Week 10/11 evidence.

## Setup
Requirements:
1. Python 3.11+ (tested on Python 3.13).
2. OpenRouter API key in `.env` as `OPENROUTER_API_KEY=...`.

Optional sanity check:
```powershell
python --version
```

## Run Generation Pipeline
### 1) Smoke test (recommended first)
```powershell
python generation_scripts/build_stage2_dataset.py `
  --frontier-generator-model anthropic/claude-sonnet-4.6 `
  --cheap-generator-model deepseek/deepseek-chat-v3.1 `
  --cheap-judge-model mistralai/mistral-small-2603 `
  --eval-judge-model openai/gpt-5-mini `
  --total-tasks 3 `
  --eval-calibration-size 3 `
  --max-attempts-per-mode 20 `
  --max-consecutive-request-failures 4 `
  --request-timeout-s 25 `
  --snapshot-every 1 `
  --progress-log generation_scripts/run_progress_smoke.log `
  --status-json generation_scripts/run_status_smoke.json `
  --cost-log-md cost_log_smoke.md `
  --cost-log-jsonl generation_scripts/api_call_cost_log_smoke.jsonl
```

### 2) Full run (240 tasks)
```powershell
python generation_scripts/build_stage2_dataset.py `
  --frontier-generator-model anthropic/claude-sonnet-4.6 `
  --cheap-generator-model deepseek/deepseek-chat-v3.1 `
  --cheap-judge-model mistralai/mistral-small-2603 `
  --eval-judge-model openai/gpt-5-mini `
  --total-tasks 240 `
  --eval-calibration-size 50 `
  --max-attempts-per-mode 500 `
  --max-consecutive-request-failures 8 `
  --request-timeout-s 30 `
  --snapshot-every 5 `
  --progress-log generation_scripts/run_progress_full.log `
  --status-json generation_scripts/run_status_full.json `
  --cost-log-md cost_log.md `
  --cost-log-jsonl generation_scripts/api_call_cost_log.jsonl
```

## Where to Watch Progress
1. Live step log: `generation_scripts/run_progress_*.log`
2. Current state snapshot: `generation_scripts/run_status_*.json`
3. Per-call API usage/cost: `generation_scripts/api_call_cost_log*.jsonl`
4. Final cost summary: `cost_log*.md`

## Generated Outputs
1. `tenacious_bench_v0.1/train/tasks.jsonl`
2. `tenacious_bench_v0.1/dev/tasks.jsonl`
3. `tenacious_bench_v0.1/held_out/tasks.jsonl`
4. `tenacious_bench_v0.1/contamination_check.json`
5. `tenacious_bench_v0.1/inter_rater_agreement.json`
6. `generation_scripts/judge_filter_log.jsonl`
7. `generation_scripts/judge_pairwise_log.jsonl`
8. `generation_scripts/eval_calibration_log.jsonl`
9. `generation_scripts/seed_counts.json`

## Evaluate Tasks
Run evaluator on schema examples:
```powershell
python scoring_evaluator.py --tasks schema.json --out stage1_eval_results.json
```

## Train Path B Critic (DPO + LoRA)
Prebuild preference files:
```powershell
python generation_scripts/build_path_b_preferences.py --project-root .
```

Generated training inputs:
1. `training_data/path_b/preferences_train_dpo.jsonl`
2. `training_data/path_b/preferences_dev_dpo.jsonl`

Notebook runbook:
1. `notebooks/DPO_training_unsloth.ipynb`
2. Colab-first flow with optional mini-sweep (`beta`/`epochs`) and artifact export to `training/`.

## ACT IV Ablations (Delta A/B/C + Cost-Pareto)
Generate held-out outputs per variant, then run ablation evaluation.

Colab notebook option (recommended if local machine lacks GPU/deps):
1. `notebooks/ACT4_ablation_unsloth.ipynb`
2. The notebook runs real trained inference from `training/tenacious_path_b_dpo_lora` and then runs smoke/full ACT IV ablations.

Expected JSONL output row format for each variant file:
```json
{"task_id":"TBENCH-...","subject":"...","body":"..."}
```

### 1) Export baseline and prompt-only outputs (fast, local)
```powershell
python generation_scripts/export_heldout_outputs.py `
  --mode baseline `
  --held-out tenacious_bench_v0.1/held_out/tasks.jsonl `
  --out training/heldout_baseline_outputs.jsonl

python generation_scripts/export_heldout_outputs.py `
  --mode prompt_only `
  --held-out tenacious_bench_v0.1/held_out/tasks.jsonl `
  --out training/heldout_prompt_outputs.jsonl
```

### 2) Export trained-model outputs (run on Colab GPU)
```powershell
python generation_scripts/export_heldout_outputs.py `
  --mode trained_intervene `
  --held-out tenacious_bench_v0.1/held_out/tasks.jsonl `
  --base-outputs-file training/heldout_baseline_outputs.jsonl `
  --adapter-path training/tenacious_path_b_dpo_lora `
  --base-model auto `
  --max-new-tokens 140 `
  --out training/heldout_trained_outputs.jsonl
```

### 3) Smoke test the full ablation pipeline (recommended)
```powershell
python generation_scripts/run_act4_ablations.py `
  --held-out tenacious_bench_v0.1/held_out/tasks.jsonl `
  --baseline-outputs-file training/heldout_baseline_outputs.jsonl `
  --prompt-outputs-file training/heldout_prompt_outputs.jsonl `
  --trained-outputs-file training/heldout_trained_outputs.jsonl `
  --limit 10 `
  --bootstrap-iters 500 `
  --out-ablation training/ablation_results_smoke.json `
  --out-traces training/held_out_traces_smoke.jsonl
```

### 4) Full ACT IV run
```powershell
python generation_scripts/run_act4_ablations.py `
  --held-out tenacious_bench_v0.1/held_out/tasks.jsonl `
  --baseline-outputs-file training/heldout_baseline_outputs.jsonl `
  --prompt-outputs-file training/heldout_prompt_outputs.jsonl `
  --trained-outputs-file training/heldout_trained_outputs.jsonl `
  --week10-retail-score <your_week10_tau2_score> `
  --bootstrap-iters 5000 `
  --out-ablation ablation_results.json `
  --out-traces held_out_traces.jsonl
```

Submission naming requirement:
1. Use `--out-ablation ablation_results.json`
2. Use `--out-traces held_out_traces.jsonl`
3. Do not submit `_smoke` filenames as final deliverables.

Notes:
1. Delta A and Delta B significance are computed with paired bootstrap (`95% CI`, one-sided `p` for positive lift).
2. Delta C is informational only and uses your existing Week 10 retail score (no re-run).
3. Cost-Pareto uses per-task cost assumptions; pass `--assume-cost-*` flags if you want non-zero cost modeling.

## Rough Runtime and Cost Estimates
Based on a real API-backed 3-task smoke run in this repo:
1. 3-task smoke run took ~2.2 minutes.
2. Observed cost was about `$0.0139` total for that smoke run.

Rough full-run estimates for 240 tasks:
1. Runtime: ~1.5 to 4 hours depending on model latency, retries, and temporary API/network issues.
2. Cost: ~`$1` to `$6` typical range with these model tiers; can be higher if retries spike or if output lengths increase.

These are rough operational estimates, not a hard guarantee.

## Current Status
1. ACT I and ACT II artifacts are implemented.
2. Real OpenRouter-backed pipeline is implemented with fail-fast and visibility logging.
3. Remaining work is ACT III-V training/ablation/publication packaging.
