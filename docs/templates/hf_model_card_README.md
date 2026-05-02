---
library_name: transformers
base_model: unsloth/Qwen2.5-3B-Instruct-bnb-4bit
license: mit
tags:
- lora
- peft
- dpo
- evaluation
- sales
---

# Tenacious Path-B DPO LoRA v0.1

LoRA adapter trained for Tenacious-Bench-style response intervention and evaluation experiments.

## Model Details

1. Artifact type: PEFT LoRA adapter (not a full merged model)
2. Base model lineage: `unsloth/Qwen2.5-3B-Instruct-bnb-4bit`
3. Training path: ACT III Path B (DPO + LoRA)

## Intended Use

1. controlled benchmarking and intervention experiments on Tenacious-Bench tasks
2. reproduction of ACT IV Delta A/B outcomes

## Out-of-Scope Use

1. autonomous production deployment without additional policy guardrails
2. legal/compliance-sensitive messaging without human review

## Training Data

1. primary data: preference pairs derived from Tenacious-Bench train/dev
2. held-out split excluded from training
3. preference files:
   - `training_data/path_b/preferences_train_dpo.jsonl`
   - `training_data/path_b/preferences_dev_dpo.jsonl`

## Training Procedure

Copy from `training/config.yaml`:
1. seed: `42`
2. max sequence length: `1024`
3. train pairs: `125`
4. dev pairs: `75`
5. selected beta: `0.1`
6. optimizer/lr/epochs/batch settings from run config

## Evaluation Results (ACT IV Held-Out)

1. baseline mean score: `93.44`
2. trained mean score: `97.92`
3. Delta A (trained vs baseline): `+4.48`, 95% CI `[3.68, 5.44]`, `p=0.0002`
4. Delta B (trained vs prompt-only): `-2.08`, 95% CI `[-3.36, -0.96]` (non-win)

## Known Failure Modes

Remaining failures cluster around hard-policy cases:
1. capacity over-commitment beyond bench
2. quoting specific total contract value
3. discount/promo language

## Ethical and Safety Notes

This adapter can generate fluent outputs that still violate hard policy constraints. It is not a policy-enforcement system by itself.

## Load for Inference

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base_id = "unsloth/Qwen2.5-3B-Instruct-bnb-4bit"
adapter_id = "<your_hf_user>/tenacious-pathb-dpo-lora-v0.1"

tokenizer = AutoTokenizer.from_pretrained(base_id)
base = AutoModelForCausalLM.from_pretrained(base_id)
model = PeftModel.from_pretrained(base, adapter_id)
```

## Links

1. Dataset: `<dataset_url>`
2. Ablation JSON: `<repo_link_to_ablation_results.json>`
3. Traces JSONL: `<repo_link_to_held_out_traces.jsonl>`
4. Methodology: `<repo_link_to_methodology_rationale.md>`
