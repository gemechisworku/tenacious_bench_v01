---
pretty_name: "Tenacious Bench v0.1"
license: "cc-by-4.0"
task_categories:
- text-generation
language:
- en
tags:
- benchmark
- evaluation
- sales
- llm
- safety
configs:
- config_name: default
  data_files:
  - split: train
    path: "train/tasks.jsonl"
  - split: validation
    path: "dev/tasks.jsonl"
  - split: test
    path: "held_out/tasks.jsonl"
---

# Tenacious Bench v0.1

Tenacious Bench v0.1 is a sales-agent evaluation benchmark focused on Tenacious-specific reliability constraints:
1. grounded signal usage
2. bench-safe commitments
3. pricing scope compliance
4. tone/professionalism constraints

## Dataset Structure

Files in this repo:
1. `train/tasks.jsonl`
2. `dev/tasks.jsonl`
3. `held_out/tasks.jsonl`
4. `datasheet.md`
5. `contamination_check.json`
6. `inter_rater_agreement.json`
7. `merge_report.json`

Split semantics:
1. `train` -> model/data construction
2. `validation` (from `dev/tasks.jsonl`) -> calibration/dev checks
3. `test` (from `held_out/tasks.jsonl`) -> sealed held-out evaluation

## Quickstart (<=10 minutes)

```python
from datasets import load_dataset

ds = load_dataset("<your_hf_user>/tenacious_bench_v0.1")
print(ds)
print(ds["train"][0].keys())
```

Local evaluator example:
```powershell
python scoring_evaluator.py --tasks schema.json --out stage1_eval_results.json
```

## Evaluation Snapshot (ACT IV)

Held-out (`n=50`) summary:
1. baseline mean score: `93.44`, pass rate `0.86`
2. prompt-only mean score: `100.0`, pass rate `1.0`
3. trained mean score: `97.92`, pass rate `0.82`

Delta A (trained vs baseline):
1. mean diff: `+4.48`
2. 95% CI: `[3.68, 5.44]`
3. one-sided p-value: `0.0002`

Delta B (trained vs prompt-only):
1. mean diff: `-2.08`
2. 95% CI: `[-3.36, -0.96]`
3. training did not beat prompt-only in this run.

## Intended Use

1. benchmark-style evaluation of sales-agent outputs under explicit policy/tone constraints
2. intervention comparison under fixed rubric and held-out split

## Out-of-Scope Use

1. legal/compliance guarantees
2. generalized SDR ranking outside this benchmark scope

## Known Limitations

1. Hard-policy failures remain in capacity over-commitment, specific TCV quoting, and discount/promo language.
2. Cost-pareto results are low-informational when cost assumptions are zero.
3. This benchmark is machine-rubric-centric and not a full substitute for human review.

## Citation

If you use this dataset, cite this Hugging Face repository URL and the linked project repo.
