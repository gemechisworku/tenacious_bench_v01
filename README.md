# Tenacious-Bench v0.1

Tenacious-Bench v0.1 is a Tenacious-specific sales-agent benchmark focused on grounded claims, policy-safe commitments, and operational reliability.  
Declared path: **Path B (DPO + LoRA judge/critic style intervention)**.

## Status
1. Dataset, scoring, contamination, and inter-rater artifacts are committed.
2. ACT IV ablation outputs are committed.
3. ACT V packaging bundle is staged under `act5_publish/`.

## Setup
1. Clone and enter repo:
```bash
git clone https://github.com/gemechisworku/tenacious_bench_v01.git
cd tenacious_bench_v01
```
2. Create/activate virtual env:
```bash
python -m venv .venv
```
```powershell
.\.venv\Scripts\Activate.ps1
```
3. Install pinned dependencies:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## Reproduce Headline Number
Headline metric: **Delta A (trained vs baseline) mean lift = +4.48 points** from `ablation_results.json`.

Fast reproducibility check from committed artifact:
```bash
python -c "import json; d=json.load(open('ablation_results.json')); print(d['delta_a_trained_vs_week10_baseline']['mean_diff'])"
```

Full held-out rerun entrypoint:
```bash
python generation_scripts/run_act4_ablations.py --held-out tenacious_bench_v0.1/held_out/tasks.jsonl --evaluator scoring_evaluator.py --out-ablation ablation_results.json --out-traces held_out_traces.jsonl
```

## Core Commands
1. Score sample tasks:
```bash
python scoring_evaluator.py --tasks schema.json --out stage1_eval_results.json
```
2. Recompute contamination report:
```bash
python generation_scripts/run_contamination_checks.py --dataset-root tenacious_bench_v0.1 --out tenacious_bench_v0.1/contamination_check.json
```
3. Reproducible Path B training entrypoint:
```bash
python training/run_path_b_dpo.py --train-file training_data/path_b/preferences_train_dpo.jsonl --dev-file training_data/path_b/preferences_dev_dpo.jsonl
```

## Repository Layout
1. `tenacious_bench_v0.1/`: dataset splits and QA reports
2. `generation_scripts/`: generation, contamination, and ablation harnesses
3. `training_data/`: preference datasets
4. `training/`: training config/logs and reproducible trainer script
5. `act5_publish/`: publication bundle

## Public Artifacts
1. HuggingFace dataset URL: https://huggingface.co/datasets/gemechisw/tenacious_bench_v0.1
2. HuggingFace model URL (Path B adapter): https://huggingface.co/gemechisw/tenacious-pathb-dpo-lora-v0.1
3. Blog post URL: https://gemechis1.substack.com/p/tenacious-bench-v01-evaluating-sales
4. Community engagement URL: https://github.com/sierra-research/tau2-bench/issues/290

## License
This repository is released under **CC-BY-4.0**. See `LICENSE`.

## Attribution and Credits
1. Dataset and training artifacts: Gemechis Worku
2. Reference benchmark context: Sierra Research τ²-Bench community discussions
3. Open-source ecosystem: Hugging Face, TRL, PEFT, and Unsloth tooling
