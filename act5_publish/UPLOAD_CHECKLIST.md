# ACT V Upload Checklist (Manual)

## Dataset Repo (`<your_hf_user>/tenacious_bench_v0.1`)
- Upload everything under `dataset/`
- Ensure `README.md` renders with split mapping and metadata
- Verify Dataset Viewer loads train/validation/test from YAML mapping

## Model Repo (`<your_hf_user>/tenacious-pathb-dpo-lora-v0.1`)
- Add adapter files into `model/` first
- Upload everything under `model/`
- Verify model card links and load snippet

## Blog + Community
- Use drafts in `comms/`
- Publish HF community article
- Open community issue with links to dataset/model/blog

## Evidence Anchors
- Use files in `evidence/` as canonical source for numeric claims
- Keep `PACKAGE_MANIFEST.json` for integrity tracking
