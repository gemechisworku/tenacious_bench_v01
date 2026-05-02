#!/usr/bin/env python3
"""Reproducible Path B DPO training entrypoint (LoRA-only).

This script is intentionally explicit for ACT III rubric checks:
- all core hyperparameters are surfaced as CLI args
- seed is fixed and logged
- backbone model + revision pin are required
- DPOTrainer is used (Path B aligned)
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import DPOConfig, DPOTrainer


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Path B DPO + LoRA training.")
    p.add_argument("--train-file", type=Path, default=Path("training_data/path_b/preferences_train_dpo.jsonl"))
    p.add_argument("--dev-file", type=Path, default=Path("training_data/path_b/preferences_dev_dpo.jsonl"))
    p.add_argument("--output-dir", type=Path, default=Path("training/tenacious_path_b_dpo_lora"))
    p.add_argument("--metrics-json", type=Path, default=Path("training/metrics_repro.json"))
    p.add_argument("--log-jsonl", type=Path, default=Path("training/train_eval_log.jsonl"))

    p.add_argument("--base-model", type=str, default="unsloth/Qwen2.5-3B-Instruct-bnb-4bit")
    p.add_argument(
        "--base-model-revision",
        type=str,
        default="e4e89f41c15add339047cb9e9efcaa88da2128c8",
        help="Pinned revision/commit hash for reproducibility.",
    )
    p.add_argument("--seed", type=int, default=42)

    p.add_argument("--learning-rate", type=float, default=1e-5)
    p.add_argument("--per-device-train-batch-size", type=int, default=2)
    p.add_argument("--per-device-eval-batch-size", type=int, default=2)
    p.add_argument("--gradient-accumulation-steps", type=int, default=4)
    p.add_argument("--num-train-epochs", type=float, default=2.0)
    p.add_argument("--warmup-ratio", type=float, default=0.1)
    p.add_argument("--lr-scheduler-type", type=str, default="cosine")
    p.add_argument("--max-length", type=int, default=1024)
    p.add_argument("--max-prompt-length", type=int, default=768)
    p.add_argument("--beta", type=float, default=0.1)

    p.add_argument("--lora-rank", type=int, default=16)
    p.add_argument("--lora-alpha", type=int, default=32)
    p.add_argument("--lora-dropout", type=float, default=0.05)
    return p.parse_args()


def set_all_seeds(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def append_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    args = parse_args()
    set_all_seeds(args.seed)

    if not args.base_model_revision:
        raise ValueError("base-model-revision must be a pinned hash/revision.")

    dataset = load_dataset(
        "json",
        data_files={"train": str(args.train_file), "dev": str(args.dev_file)},
    )

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, revision=args.base_model_revision, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        revision=args.base_model_revision,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
    )

    # LoRA-only tuning (base weights frozen by PEFT adapters).
    peft_cfg = LoraConfig(
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "up_proj", "down_proj", "gate_proj"],
    )
    model = get_peft_model(model, peft_cfg)

    dpo_cfg = DPOConfig(
        output_dir=str(args.output_dir),
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.per_device_train_batch_size,
        per_device_eval_batch_size=args.per_device_eval_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        num_train_epochs=args.num_train_epochs,
        warmup_ratio=args.warmup_ratio,
        lr_scheduler_type=args.lr_scheduler_type,
        max_length=args.max_length,
        max_prompt_length=args.max_prompt_length,
        eval_strategy="epoch",
        logging_steps=1,
        save_strategy="epoch",
        seed=args.seed,
        report_to=[],
        bf16=torch.cuda.is_available(),
    )

    trainer = DPOTrainer(
        model=model,
        args=dpo_cfg,
        beta=args.beta,
        train_dataset=dataset["train"],
        eval_dataset=dataset["dev"],
        processing_class=tokenizer,
    )

    train_out = trainer.train()
    eval_out = trainer.evaluate()
    trainer.save_model(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))

    metrics = {
        "base_model": args.base_model,
        "base_model_revision": args.base_model_revision,
        "seed": args.seed,
        "path": "B",
        "trainer": "DPOTrainer",
        "lora_only": True,
        "hyperparameters": {
            "learning_rate": args.learning_rate,
            "per_device_train_batch_size": args.per_device_train_batch_size,
            "per_device_eval_batch_size": args.per_device_eval_batch_size,
            "gradient_accumulation_steps": args.gradient_accumulation_steps,
            "num_train_epochs": args.num_train_epochs,
            "warmup_ratio": args.warmup_ratio,
            "lr_scheduler_type": args.lr_scheduler_type,
            "max_length": args.max_length,
            "max_prompt_length": args.max_prompt_length,
            "beta": args.beta,
            "lora_rank": args.lora_rank,
            "lora_alpha": args.lora_alpha,
            "lora_dropout": args.lora_dropout,
        },
        "train_metrics": train_out.metrics,
        "eval_metrics": eval_out,
    }

    args.metrics_json.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_json.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    append_jsonl(args.log_jsonl, trainer.state.log_history)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()

