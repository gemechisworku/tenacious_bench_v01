---
base_model: unsloth/Qwen2.5-3B-Instruct-bnb-4bit
library_name: peft
pipeline_tag: text-generation
tags:
- base_model:adapter:unsloth/Qwen2.5-3B-Instruct-bnb-4bit
- dpo
- lora
- transformers
- trl
- unsloth
---

# Model Card for `gemechisw/tenacious-pathb-dpo-lora-v0.1`

PEFT LoRA adapter trained with DPO for Tenacious-Bench sales-agent intervention experiments, focused on improving policy/reliability behavior over the Week 10 baseline while preserving reproducibility and explicit failure reporting.

## Model Details

### Model Description

This artifact is an adapter-only checkpoint (not a full merged foundation model). It was trained on preference pairs derived from Tenacious-Bench v0.1 train/dev splits, where chosen outputs pass benchmark constraints and rejected outputs represent policy/reliability failures.

- **Developed by:** Gemechis Worku
- **Funded by [optional]:** [More Information Needed]
- **Shared by [optional]:** Gemechis Worku
- **Model type:** PEFT LoRA adapter trained with DPO (Path B)
- **Language(s) (NLP):** English
- **License:** [More Information Needed]
- **Finetuned from model [optional]:** `unsloth/Qwen2.5-3B-Instruct-bnb-4bit`

### Model Sources [optional]

- **Repository:** https://github.com/gemechisworku/tenacious_bench_v01
- **Paper [optional]:** [More Information Needed]
- **Demo [optional]:** [More Information Needed]

## Uses

### Direct Use

1. Benchmark-time intervention experiments on Tenacious-Bench v0.1 tasks.
2. Reproducing comparisons between baseline, prompt-only, and trained variants.
3. Evaluating preference-tuned behavior on sales-policy-sensitive drafting tasks.

### Downstream Use [optional]

1. As an adapter component inside a larger sales-assistant pipeline where outputs are additionally guarded by deterministic policy checks.
2. As a starting point for further preference optimization on expanded hard-policy slices.

### Out-of-Scope Use

1. Fully autonomous production outreach without additional policy guardrails.
2. Legal/compliance-sensitive quoting decisions without human review.
3. General-purpose conversational deployment outside the benchmark scope.

## Bias, Risks, and Limitations

1. The adapter can produce fluent outputs that still violate hard policy constraints.
2. Remaining known failure clusters include capacity over-commitment, specific TCV quoting, and discount/promo language.
3. Evaluation performance is benchmark-specific and should not be interpreted as universal sales competence.
4. Delta B did not beat a strong prompt-only intervention in this run.

### Recommendations

1. Keep a deterministic policy layer in front of any send action.
2. Require human approval for capacity, pricing, and discount claims.
3. Use this model as an experimental component, not as a standalone policy system.
4. Monitor failure-family slices separately, not only aggregate score.

## How to Get Started with the Model

Use the code below to load the base model and attach the adapter.

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base_id = "unsloth/Qwen2.5-3B-Instruct-bnb-4bit"
adapter_id = "gemechisw/tenacious-pathb-dpo-lora-v0.1"

tokenizer = AutoTokenizer.from_pretrained(base_id)
base = AutoModelForCausalLM.from_pretrained(base_id)
model = PeftModel.from_pretrained(base, adapter_id)
```

## Training Details

### Training Data

Training data comes from Tenacious-Bench v0.1 preference pairs:
1. `training_data/path_b/preferences_train_dpo.jsonl` (125 pairs)
2. `training_data/path_b/preferences_dev_dpo.jsonl` (75 pairs)

Dataset reference:
1. https://huggingface.co/datasets/gemechisw/tenacious_bench_v0.1

Preprocessing and controls:
1. Held-out split excluded from preference construction.
2. Chosen/rejected pairs derived under benchmark rubric constraints.
3. Leakage controls documented in `methodology_rationale.md` and implementation plan ACT III.

### Training Procedure

#### Preprocessing [optional]

1. Preference pairs were built from train/dev tasks only.
2. Rejected outputs include deterministic-rubric and hard-policy failures.
3. Chosen outputs are corrected outputs that pass threshold criteria.

#### Training Hyperparameters

- **Training regime:** Mixed precision (Colab/Unsloth workflow; exact mode to confirm from notebook runtime)
- **Method:** DPO + LoRA
- **Seed:** 42
- **Max sequence length:** 1024
- **Optimizer:** `adamw_8bit`
- **Learning rate:** `1e-5`
- **Epochs:** configured `2` in run config
- **Per-device batch size:** `2`
- **Gradient accumulation steps:** `4`
- **DPO beta (selected run):** `0.1` (run args include `beta: 0.05`, selected run metadata records `0.1`)
- **LoRA config (project runbook):** `r=16`, `alpha=32`, `dropout=0.05`
- **LoRA target modules:** `q_proj,k_proj,v_proj,o_proj,up_proj,down_proj,gate_proj`

#### Speeds, Sizes, Times [optional]

1. Train runtime: `994.5271` seconds (~16.6 minutes).
2. Train samples/sec: `0.251`.
3. Train steps/sec: `0.032`.
4. Reported train loss: `0.2612`.
5. Artifacts tracked in:
   - `training/config.yaml`
   - `training/metrics.json`
   - `training/training_run.log`

## Evaluation

### Testing Data, Factors & Metrics

#### Testing Data

Held-out evaluation used Tenacious-Bench v0.1 held-out split:
1. `tenacious_bench_v0.1/held_out/tasks.jsonl` (`n=50`)

Supporting outputs and traces:
1. `ablation_results.json`
2. `held_out_traces.jsonl`

#### Factors

Evaluation disaggregates by variant and policy behavior:
1. Baseline vs prompt-only vs trained intervention.
2. Failure families including signal honesty, bench capacity, pricing scope, and tone constraints.

#### Metrics

1. Mean score percentage.
2. Pass rate.
3. Paired bootstrap 95% confidence interval for mean differences.
4. One-sided and two-sided p-values for lift claims.

### Results

Held-out aggregate (`n=50`):
1. Baseline mean score: `93.44`, pass rate `0.86`.
2. Prompt-only mean score: `100.0`, pass rate `1.0`.
3. Trained mean score: `97.92`, pass rate `0.82`.

Delta A (trained vs baseline):
1. Mean diff: `+4.48`.
2. 95% CI: `[3.68, 5.44]`.
3. One-sided p-value: `0.0002`.
4. Claim positive with significance: `true`.

Delta B (trained vs prompt-only):
1. Mean diff: `-2.08`.
2. 95% CI: `[-3.36, -0.96]`.
3. One-sided p-value: `1.0`.
4. Claim training beats prompt-only: `false`.

#### Summary

The adapter produced statistically significant lift over the baseline comparator (Delta A), but did not outperform the prompt-only intervention (Delta B). Remaining failures are concentrated in hard-policy honesty slices.

## Model Examination [optional]

No dedicated interpretability study was run for this release. Error analysis was performed at trace level via `held_out_traces.jsonl` and summarized in project documentation.

## Environmental Impact

Carbon emissions can be estimated using the [Machine Learning Impact calculator](https://mlco2.github.io/impact#compute) presented in [Lacoste et al. (2019)](https://arxiv.org/abs/1910.09700).

- **Hardware Type:** NVIDIA T4 (Colab workflow)
- **Hours used:** ~0.28 hours for the reported training run
- **Cloud Provider:** Google Colab
- **Compute Region:** [More Information Needed]
- **Carbon Emitted:** [More Information Needed]

## Technical Specifications [optional]

### Model Architecture and Objective

1. Base architecture: Qwen2.5-3B Instruct variant (4-bit base loading workflow via Unsloth).
2. Adapter method: LoRA on attention + MLP projection modules.
3. Objective: Direct Preference Optimization over chosen/rejected response pairs.
4. Training path: ACT III Path B.

### Compute Infrastructure

Colab-based training workflow with adapter-only output artifacts.

#### Hardware

1. GPU class: T4 (16GB class runtime target)
2. Local development artifacts synchronized into repo for reproducibility.

#### Software

1. Unsloth training notebook workflow.
2. TRL-based DPO training pipeline.
3. Transformers + PEFT adapter loading stack.

## Citation [optional]

**BibTeX:**

```bibtex
@misc{worku2026tenaciouspathb,
  title        = {Tenacious DPO LoRA v0.1},
  author       = {Gemechis Worku},
  year         = {2026},
  howpublished = {Hugging Face model repository},
  note         = {Adapter model for Tenacious-Bench v0.1}
}
```

**APA:**

Worku, G. (2026). *Tenacious DPO LoRA v0.1* [Model adapter]. Hugging Face.

## Glossary [optional]

1. **Delta A:** Trained minus baseline held-out mean score difference.
2. **Delta B:** Trained minus prompt-only held-out mean score difference.
3. **DPO:** Direct Preference Optimization.
4. **LoRA:** Low-Rank Adaptation for parameter-efficient fine-tuning.

## More Information [optional]

Related project artifacts:
1. Dataset card: https://huggingface.co/datasets/gemechisw/tenacious_bench_v0.1
2. Ablation JSON: https://github.com/gemechisworku/tenacious_bench_v01/blob/main/ablation_results.json
3. Traces JSONL: https://github.com/gemechisworku/tenacious_bench_v01/blob/main/held_out_traces.jsonl
4. Methodology rationale: https://github.com/gemechisworku/tenacious_bench_v01/blob/main/methodology_rationale.md

## Model Card Authors [optional]

Gemechis Worku

## Model Card Contact

[More Information Needed]

### Framework versions

- PEFT 0.19.1
