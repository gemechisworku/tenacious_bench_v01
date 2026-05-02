Title:
Tenacious-specific benchmark gap report + public artifact release (dataset/model/eval)

Body:

Hi maintainers, sharing a focused benchmark-gap report from a Tenacious-style sales-agent evaluation workflow.

## Why this issue

We observed a recurring gap between broad tool-use benchmark success and sales-domain policy reliability under short outreach constraints.

## Gap summary

High-impact slices where generic scoring under-specifies failures:
1. weak-signal over-assertion
2. capacity over-commitment beyond allowed bench
3. pricing/discount specificity drift
4. tone/professional framing under constrained word budgets

## What we built

1. Dataset: `tenacious_bench_v0.1` (public)
2. Adapter model artifact (Path B DPO LoRA): public
3. Held-out ablation artifacts with confidence intervals and trace outputs

Links:
1. Dataset: `<dataset_url>`
2. Model: `<model_url>`
3. Blog/postmortem: `<blog_url>`
4. Ablation JSON: `<ablation_json_url>`
5. Trace JSONL: `<traces_jsonl_url>`

## Result snapshot

Held-out (`n=50`):
1. baseline mean score: `93.44`
2. prompt-only mean score: `100.0`
3. trained mean score: `97.92`
4. Delta A (trained vs baseline): `+4.48`, 95% CI `[3.68, 5.44]`, one-sided p `0.0002`
5. Delta B (trained vs prompt-only): `-2.08`, 95% CI `[-3.36, -0.96]`

## Proposed follow-up

I think this could be useful as:
1. a complementary stress slice for policy-sensitive outreach behavior
2. a discussion seed for evaluation dimensions that separate phrasing quality from hard-policy reliability

If useful, I can follow up with:
1. compact subset export
2. mapping table from failure tags -> scoring dimensions
3. draft proposal for a minimal integration protocol
