#!/usr/bin/env python3
"""Export held-out outputs for ACT IV ablations.

Modes:
- baseline: copy `candidate_output` from held-out tasks.
- prompt_only: deterministic prompt-engineered output.
- trained: run base model + LoRA adapter inference (Unsloth) and export outputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_prompt(task: Dict[str, Any]) -> str:
    inp = task.get("input", {})
    return (
        "You are a Tenacious outbound sales assistant. Draft one concise outreach response "
        "that is grounded, honest, professional, and non-condescending.\n\n"
        f"Outreach type: {inp.get('outreach_type', 'cold')}\n"
        f"Hiring signal brief: {json.dumps(inp.get('hiring_signal_brief', {}), ensure_ascii=False)}\n"
        f"Competitor gap brief: {json.dumps(inp.get('competitor_gap_brief', {}), ensure_ascii=False)}\n"
        f"Bench summary: {json.dumps(inp.get('bench_summary', {}), ensure_ascii=False)}\n"
        f"Request context: {json.dumps(inp.get('request_context', {}), ensure_ascii=False)}\n"
        f"Prior thread: {json.dumps(inp.get('prior_thread', {}), ensure_ascii=False)}\n\n"
        "Output format:\n"
        "Subject: <one subject line>\n"
        "Body: <one concise body>"
    )


def build_prompt_only_output(task: Dict[str, Any]) -> Dict[str, str]:
    inp = task.get("input", {})
    hs = inp.get("hiring_signal_brief", {})
    hv = hs.get("hiring_velocity", {})
    funding = hs.get("buying_window_signals", {}).get("funding_event", {})

    prospect = hs.get("prospect_name", "there")
    roles_now = hv.get("open_roles_today", "N/A")
    roles_prev = hv.get("open_roles_60_days_ago", "N/A")
    stage = funding.get("stage", "recent signal")

    return {
        "subject": "Request: 15 minutes on hiring priorities",
        "body": (
            f"Hi {prospect}, I noticed your open roles moved from {roles_prev} to {roles_now}. "
            f"I also saw a {stage} signal where public data was available. "
            "If useful, I can share two scoped options aligned to confirmed capacity only. "
            "Would you be open to a 15-minute review next week?"
        ),
    }


def parse_subject_body(text: str) -> Dict[str, str]:
    subject = ""
    body = text.strip()
    for line in text.splitlines():
        if line.lower().startswith("subject:") and not subject:
            subject = line.split(":", 1)[1].strip()
    lower = text.lower()
    if "body:" in lower:
        idx = lower.find("body:")
        body = text[idx + len("body:") :].strip()
    return {"subject": subject, "body": body}


def resolve_base_model(base_model: str, adapter_path: str) -> str:
    if base_model != "auto":
        return base_model
    cfg_path = Path(adapter_path) / "adapter_config.json"
    if not cfg_path.exists():
        raise ValueError(
            "base model is set to 'auto' but adapter_config.json is missing. "
            "Pass --base-model explicitly."
        )
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    resolved = str(cfg.get("base_model_name_or_path", "")).strip()
    if not resolved:
        raise ValueError(
            "base model is set to 'auto' but adapter_config.json has no "
            "'base_model_name_or_path'. Pass --base-model explicitly."
        )
    return resolved


def export_baseline(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for t in tasks:
        co = t.get("candidate_output", {}) if isinstance(t.get("candidate_output"), dict) else {}
        rows.append({
            "task_id": t.get("task_id", ""),
            "subject": str(co.get("subject", "")),
            "body": str(co.get("body", "")),
        })
    return rows


def export_prompt_only(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for t in tasks:
        out = build_prompt_only_output(t)
        rows.append({"task_id": t.get("task_id", ""), "subject": out["subject"], "body": out["body"]})
    return rows


def export_trained(
    tasks: List[Dict[str, Any]],
    *,
    base_model: str,
    adapter_path: str,
    max_seq_length: int,
    max_new_tokens: int,
    inference_backend: str = "auto",
    local_files_only: bool = False,
) -> List[Dict[str, Any]]:
    resolved_base_model = resolve_base_model(base_model, adapter_path)

    def _export_with_unsloth() -> List[Dict[str, Any]]:
        import os
        import torch
        from unsloth import FastLanguageModel

        if not torch.cuda.is_available():
            raise RuntimeError("Unsloth inference requires CUDA, but CUDA is not available.")

        os.environ["UNSLOTH_STABLE_DOWNLOADS"] = "1"
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=resolved_base_model,
            max_seq_length=max_seq_length,
            load_in_4bit=True,
            local_files_only=local_files_only,
        )
        model.load_adapter(adapter_path)
        FastLanguageModel.for_inference(model)

        rows: List[Dict[str, Any]] = []
        for t in tasks:
            prompt = build_prompt(t)
            inputs = tokenizer([prompt], return_tensors="pt", truncation=True, max_length=max_seq_length).to("cuda")
            outputs = model.generate(**inputs, max_new_tokens=max_new_tokens)
            text = tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]

            if text.startswith(prompt):
                text = text[len(prompt) :].strip()

            sb = parse_subject_body(text)
            if not sb["subject"]:
                sb["subject"] = "Request: 15 minutes on hiring priorities"
            rows.append({"task_id": t.get("task_id", ""), "subject": sb["subject"], "body": sb["body"]})
        return rows

    def _export_with_transformers() -> List[Dict[str, Any]]:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        device = "cuda" if torch.cuda.is_available() else "cpu"

        try:
            model = AutoModelForCausalLM.from_pretrained(
                resolved_base_model,
                local_files_only=local_files_only,
            )
            model.load_adapter(adapter_path, local_files_only=local_files_only)
        except Exception as e:
            raise RuntimeError(
                "Failed to load base model + LoRA adapter with Transformers/PEFT. "
                "Ensure `peft` is installed and base model weights are available."
            ) from e

        model.to(device)
        model.eval()
        tokenizer = AutoTokenizer.from_pretrained(
            adapter_path,
            local_files_only=local_files_only,
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        rows: List[Dict[str, Any]] = []
        for t in tasks:
            prompt = build_prompt(t)
            inputs = tokenizer([prompt], return_tensors="pt", truncation=True, max_length=max_seq_length).to(device)
            with torch.no_grad():
                outputs = model.generate(**inputs, max_new_tokens=max_new_tokens)
            text = tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]

            if text.startswith(prompt):
                text = text[len(prompt) :].strip()

            sb = parse_subject_body(text)
            if not sb["subject"]:
                sb["subject"] = "Request: 15 minutes on hiring priorities"
            rows.append({"task_id": t.get("task_id", ""), "subject": sb["subject"], "body": sb["body"]})
        return rows

    backend = inference_backend.lower().strip()
    if backend == "unsloth":
        return _export_with_unsloth()
    if backend == "transformers":
        return _export_with_transformers()
    if backend == "auto":
        unsloth_error: Exception | None = None
        try:
            return _export_with_unsloth()
        except Exception as e:
            unsloth_error = e
        try:
            return _export_with_transformers()
        except Exception as e:
            raise RuntimeError(
                "Could not run trained inference with either backend. "
                f"unsloth_error={unsloth_error!r}; transformers_error={e!r}"
            ) from e
    raise ValueError(f"Unsupported inference backend: {inference_backend}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export held-out outputs for ACT IV ablations")
    p.add_argument("--held-out", type=Path, default=Path("tenacious_bench_v0.1/held_out/tasks.jsonl"))
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--mode", choices=["baseline", "prompt_only", "trained"], required=True)
    p.add_argument("--limit", type=int, default=0)

    p.add_argument("--base-model", default="auto")
    p.add_argument("--adapter-path", default="training/tenacious_path_b_dpo_lora")
    p.add_argument("--max-seq-length", type=int, default=1024)
    p.add_argument("--max-new-tokens", type=int, default=220)
    p.add_argument(
        "--inference-backend",
        choices=["auto", "unsloth", "transformers"],
        default="auto",
        help="Backend for trained inference. 'auto' tries unsloth then transformers.",
    )
    p.add_argument(
        "--local-files-only",
        action="store_true",
        help="Do not download model files; require all weights/tokenizers locally.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    tasks = read_jsonl(args.held_out)
    if args.limit and args.limit > 0:
        tasks = tasks[: args.limit]

    if args.mode == "baseline":
        rows = export_baseline(tasks)
    elif args.mode == "prompt_only":
        rows = export_prompt_only(tasks)
    else:
        rows = export_trained(
            tasks,
            base_model=args.base_model,
            adapter_path=args.adapter_path,
            max_seq_length=args.max_seq_length,
            max_new_tokens=args.max_new_tokens,
            inference_backend=args.inference_backend,
            local_files_only=args.local_files_only,
        )

    write_jsonl(args.out, rows)
    print(json.dumps({"mode": args.mode, "rows": len(rows), "out": str(args.out)}, indent=2))


if __name__ == "__main__":
    main()
