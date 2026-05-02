# Methodology Rationale (ACT III Path B)

## Path Declaration
This project executes **ACT III Path B** using **DPO + LoRA** on a 3B-class open backbone (`Qwen2.5-3B-Instruct` variant via Unsloth).

## Why Path B
Week 10 evidence indicates dominant failure modes are guardrail and reliability failures rather than pure phrasing quality. Representative traces:
1. `trace_respond_874662476a68` (policy-blocked action handling failure)
2. `trace_advance_2ef64021c4f8` (invalid state-transition behavior)
3. `trace_schedule_book_2dc2d85ac0fc` and `trace_slots_fail` (scheduling reliability breakdown)
4. `trace_mem_get_03bdfa202017` and `trace_outreach_ae9e643c953b` (memory/context coupling failure)

Given these patterns, preference tuning on chosen vs rejected responses is the most direct way to improve pre-send rejection and correction behavior.

## Alternative Paths Considered and Dismissed
1. **Path A (SFT generator quality lift)** was rejected for this cycle because Week 10 failures were dominated by inconsistency and policy-guardrail misses, not only fluency or tone quality.
2. **Path C (trajectory/PRM focus)** was deferred because the immediate bottleneck was single-step acceptance/rejection behavior before send, which is addressed faster by pairwise preferences in Path B.
3. Path B was selected as the shortest route from observed failure mode to intervention: preference pairs directly encode acceptable vs unacceptable policy behavior.

## Method Choice
Primary training method used in-repo is **DPO** with LoRA adapters.

Rationale:
1. Stable and well-understood objective for small-to-medium preference datasets.
2. Current dataset size (`125` train preference pairs, `75` dev preference pairs) supports fast iteration and practical hyperparameter tuning on Colab T4.
3. DPO run converged in Stage 4 core training with decreasing train and validation loss.

Reproducible scripted configuration:
1. `training/run_path_b_dpo.py` exposes explicit hyperparameters for learning rate, batch sizes, LoRA rank/alpha/dropout, epochs, warmup, and scheduler.
2. Backbone model and revision pin are explicit arguments (`--base-model`, `--base-model-revision`).
3. Trainer is path-aligned (`DPOTrainer`) and logs train/eval metrics to committed artifacts.

## Preference Data Construction
Preference files are generated from `tenacious_bench_v0.1/train/tasks.jsonl` and `tenacious_bench_v0.1/dev/tasks.jsonl` using:
- `generation_scripts/build_path_b_preferences.py`

Outputs:
1. `training_data/path_b/preferences_train.jsonl`
2. `training_data/path_b/preferences_dev.jsonl`
3. `training_data/path_b/preferences_train_dpo.jsonl`
4. `training_data/path_b/preferences_dev_dpo.jsonl`
5. `training_data/path_b/build_manifest.json`

## Stage 3 Contamination and Leakage Protocol
1. Held-out split (`tenacious_bench_v0.1/held_out/tasks.jsonl`) is excluded from preference construction and training data generation.
2. Preference generation uses only `train` and `dev` inputs.
3. Dataset contamination status is inherited from Stage 2 controls and recorded in `tenacious_bench_v0.1/contamination_check.json` (`pass: true`).
4. Pair construction metadata is logged in the manifest, including split counts and preference validity checks.

## References
1. Rafailov et al., 2023. *Direct Preference Optimization: Your Language Model is Secretly a Reward Model*.  
Section used: objective construction and preference-to-reward equivalence framing (Sec. 2-3).  
https://arxiv.org/abs/2305.18290
2. Meng et al., 2024. *SimPO: Simple Preference Optimization with a Reference-Free Reward*.  
Section used: reference-free preference optimization rationale and stability discussion (Sec. 3-4).  
https://arxiv.org/abs/2405.14734
3. Hong et al., 2024. *ORPO: Monolithic Preference Optimization without Reference Model*.  
Section used: odds-ratio preference objective tradeoffs vs DPO-style setup (Sec. 3).  
https://arxiv.org/abs/2403.07691
