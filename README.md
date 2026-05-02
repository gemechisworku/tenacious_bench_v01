# Tenacious-Bench v0.1

Tenacious-Bench v0.1 is a sales-agent evaluation benchmark focused on policy reliability, grounded outreach, and measurable held-out evaluation.

This repository includes:
1. Benchmark dataset files (`train/dev/held_out`)
2. Scoring evaluator
3. Preference-data + training artifacts for Path B (DPO + LoRA)
4. ACT IV ablation outputs and traces
5. ACT V publication packaging templates

## Quick Start

### 1) Clone the repo
```bash
git clone https://github.com/gemechisworku/tenacious_bench_v01.git
cd tenacious_bench_v01
```

### 2) Create a Python environment
```bash
python -m venv .venv
```

Activate it:
- Windows PowerShell
```powershell
.\.venv\Scripts\Activate.ps1
```
- macOS/Linux
```bash
source .venv/bin/activate
```

### 3) Install dependencies
Start with:
```bash
pip install --upgrade pip
```

If you only need local scoring/evaluation scripts, standard Python is enough for `scoring_evaluator.py`.
If you plan to run generation/training notebooks, install the notebook-specific dependencies used in your Colab/local workflow (Transformers, TRL, PEFT, Unsloth, etc.).

### 4) (Optional) Add API key for generation scripts
Create `.env` in repo root:
```env
OPENROUTER_API_KEY=your_key_here
```

## Basic Usage

### Evaluate sample tasks
```bash
python scoring_evaluator.py --tasks schema.json --out stage1_eval_results.json
```

### Inspect core ACT IV evidence
- `ablation_results.json`
- `held_out_traces.jsonl`
- `training/config.yaml`
- `training/metrics.json`
- `training/training_run.log`

### Use ACT V packaging bundle
Prepared publication staging directory:
- `act5_publish/`

Operator guide:
- `act5_publish/ACT_V_OPERATOR_GUIDE.md`s

## Repository Layout

- `tenacious_bench_v0.1/`: dataset files and quality/control reports
- `generation_scripts/`: dataset generation + ablation scripts
- `training_data/`: preference training inputs
- `training/`: run config/metrics/logs (+ adapter files when added)
- `docs/`: plans, templates, publication drafts
- `act5_publish/`: upload-ready packaging for dataset/model/comms/evidence

## Public Artifacts

- **HuggingFace dataset URL:** https://huggingface.co/datasets/gemechisw/tenacious_bench_v0.1
- **HuggingFace model URL if Path A or C:** Optional Path B adapter URL: https://huggingface.co/gemechisw/tenacious-pathb-dpo-lora-v0.1
- **Blog post URL - Substack:** `https://gemechis1.substack.com/p/tenacious-bench-v01-evaluating-sales`
- **Community engagement URL (github issue, submission):** `https://github.com/sierra-research/tau2-bench/issues/290`

## Status

- Dataset and evaluation pipeline are complete.
- ACT IV ablation outputs are present.
- ACT V packaging is prepared; publication links can be filled in as each artifact goes live.
