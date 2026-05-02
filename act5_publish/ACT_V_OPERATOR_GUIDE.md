# ACT V Operator Guide (Manual Publishing)

This guide is optimized for your confirmed choices:
1. You will upload artifacts manually.
2. Hugging Face releases are public.
3. Keep local split files as `train/dev/held_out`.
4. Skip DOI.
5. Publish blog on Hugging Face Community.
6. You will post the community issue yourself.

## 1) Current Artifact State

Present:
1. `ablation_results.json`
2. `held_out_traces.jsonl`
3. `training/config.yaml`
4. `training/metrics.json`
5. `training/training_run.log`
6. dataset files under `tenacious_bench_v0.1/`

Missing for model release:
1. LoRA adapter directory (example target: `training/tenacious_path_b_dpo_lora/`)

## 2) Pre-Publish Local Packaging

Build one staging directory per artifact type before upload.

### Dataset staging
Use this exact structure so the card YAML can map splits explicitly:

```text
act5_publish/
  dataset/
    README.md
    train/tasks.jsonl
    dev/tasks.jsonl
    held_out/tasks.jsonl
    datasheet.md
    contamination_check.json
    inter_rater_agreement.json
    merge_report.json
```

### Model staging
```text
act5_publish/
  model/
    README.md
    adapter_config.json
    adapter_model.safetensors (or shard files)
    tokenizer files (only if required by your loading path)
```

## 3) Dataset Publication (Hugging Face)

### Option A: Web UI
1. Create dataset repo: `https://huggingface.co/new-dataset`
2. Name: `tenacious_bench_v0.1`
3. Visibility: Public.
4. Upload dataset staging files.
5. Replace `README.md` with template from `docs/templates/hf_dataset_card_README.md`.
6. Commit.

### Option B: CLI (if preferred)
```powershell
hf auth login
hf upload <your_hf_user>/tenacious_bench_v0.1 . . --repo-type dataset
```
Run the command from inside `act5_publish/dataset/`.

## 4) Split Mapping While Keeping `train/dev/held_out`

Because files are not named `validation/test`, define split mapping in dataset-card YAML:
1. `train/tasks.jsonl` -> `train`
2. `dev/tasks.jsonl` -> `validation`
3. `held_out/tasks.jsonl` -> `test`

The template in `docs/templates/hf_dataset_card_README.md` already includes this `configs` block.

## 5) Model/Adapter Publication (Hugging Face)

1. Sync adapter directory from Colab first.
2. Create model repo (public), e.g. `tenacious-pathb-dpo-lora-v0.1`.
3. Upload only adapter assets + required inference files.
4. Use template from `docs/templates/hf_model_card_README.md`.
5. Verify the load snippet works.

Suggested load path to test in card:
```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base_id = "unsloth/Qwen2.5-3B-Instruct-bnb-4bit"
adapter_id = "<your_hf_user>/tenacious-pathb-dpo-lora-v0.1"

tok = AutoTokenizer.from_pretrained(base_id)
base = AutoModelForCausalLM.from_pretrained(base_id)
model = PeftModel.from_pretrained(base, adapter_id)
```

## 6) Hugging Face Community Blog

1. Open `https://huggingface.co/blog`
2. Click `New Article`.
3. Paste/edit draft from `docs/templates/hf_blog_post_draft.md`.
4. Include links to:
   - dataset URL
   - model URL
   - `ablation_results.json` (repo link)
   - `held_out_traces.jsonl` (repo link)
5. Publish.

## 7) Community Engagement Issue (You Post Manually)

1. Open `https://github.com/sierra-research/tau2-bench/issues`
2. Create issue with template in `docs/templates/community_issue_template.md`.
3. Include links to the published dataset/model/blog.
4. Keep tone as gap report + concrete evidence + proposed follow-up.

## 8) Final README Update Checklist

After publishing, update root `README.md` with:
1. Final ACT IV numbers (Delta A/B summary).
2. Dataset URL.
3. Model URL.
4. Blog URL.
5. Community issue URL.
6. Notes on known unresolved hard-policy failures.

## 9) Quality Gate Before You Announce

1. Dataset page renders with viewer and card.
2. Model card has base model, training params, limitations, honest Delta B non-win.
3. Blog has explicit "what did not work".
4. Every public claim in blog/memo maps to local artifact evidence.

## References
1. https://huggingface.co/docs/hub/en/datasets-adding
2. https://huggingface.co/docs/hub/datasets-cards
3. https://huggingface.co/docs/hub/datasets-manual-configuration
4. https://huggingface.co/docs/hub/en/model-cards
5. https://huggingface.co/docs/trl/en/peft_integration
6. https://huggingface.co/docs/huggingface_hub/main/en/guides/cli
7. https://huggingface.co/blog
8. https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-an-issue
