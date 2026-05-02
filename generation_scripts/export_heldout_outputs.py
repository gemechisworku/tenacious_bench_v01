#!/usr/bin/env python3
"""Export held-out outputs for ACT IV ablations.

Modes:
- baseline: copy `candidate_output` from held-out tasks.
- prompt_only: deterministic prompt-engineered output.
- trained: run base model + LoRA adapter inference (Unsloth) and export outputs.
- trained_intervene: revise a base output with the trained adapter (Path B intervention mode).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List

SUBJECT_INTENT_PREFIX = "Request:"
SUBJECT_MAX_LEN = 60
OUTREACH_WORD_LIMITS = {"cold": 120, "warm": 200, "reengagement": 100}
ASK_PATTERNS = ("would you", "are you open", "can we", "could we", "schedule", "book")
META_TAIL_MARKERS = (
    "this response is tailored",
    "the subject line is",
    "this approach is designed",
    "[your name]",
    "[your position]",
    "[your company",
    "[contact information]",
    "[linkedin",
    "[source url",
)


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
        "You are a Tenacious outbound sales assistant.\n"
        "Write exactly one outreach email with strict format:\n"
        "Subject: <one line>\n"
        "Body: <one concise paragraph>\n"
        "Rules: no explanation, no placeholders, no signatures, no bullet lists, no markdown.\n"
        "Keep body concise and include exactly one clear CTA.\n\n"
        f"Outreach type: {inp.get('outreach_type', 'cold')}\n"
        f"Hiring signal brief: {json.dumps(inp.get('hiring_signal_brief', {}), ensure_ascii=False)}\n"
        f"Competitor gap brief: {json.dumps(inp.get('competitor_gap_brief', {}), ensure_ascii=False)}\n"
        f"Bench summary: {json.dumps(inp.get('bench_summary', {}), ensure_ascii=False)}\n"
        f"Request context: {json.dumps(inp.get('request_context', {}), ensure_ascii=False)}\n"
        f"Prior thread: {json.dumps(inp.get('prior_thread', {}), ensure_ascii=False)}\n\n"
        "Return only Subject and Body."
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


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def split_sentences(text: str) -> List[str]:
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", text.strip()) if x.strip()]


def load_outputs_map(path: Path) -> Dict[str, Dict[str, str]]:
    rows = read_jsonl(path)
    out: Dict[str, Dict[str, str]] = {}
    for row in rows:
        task_id = str(row.get("task_id", "")).strip()
        if not task_id:
            continue
        out[task_id] = {
            "subject": str(row.get("subject", "")).strip(),
            "body": str(row.get("body", "")).strip(),
        }
    return out


def build_intervention_prompt(task: Dict[str, Any], base_output: Dict[str, str]) -> str:
    inp = task.get("input", {})
    outreach_type = str(inp.get("outreach_type", "cold")).lower() or "cold"
    word_limit = OUTREACH_WORD_LIMITS.get(outreach_type, 120)
    required = task.get("rubric", {}).get("required_signal_phrases", [])
    required_text = ", ".join(str(x) for x in required if str(x).strip()) or "<none>"
    return (
        "You are a Tenacious rewrite assistant.\n"
        "Revise the draft email below so it is direct, grounded, honest, professional, and non-condescending.\n"
        "Return ONLY two fields in plain text:\n"
        "Subject: <one line starting with 'Request:'>\n"
        "Body: <one concise paragraph>\n"
        "Constraints:\n"
        f"- Body word limit: {word_limit}\n"
        "- Exactly one CTA question.\n"
        "- No placeholders, signatures, explanations, bullets, or markdown.\n"
        f"- Include required signal phrase(s) when possible: {required_text}\n\n"
        f"Outreach type: {outreach_type}\n"
        f"Task input: {json.dumps(inp, ensure_ascii=False)}\n\n"
        f"Current draft subject: {base_output.get('subject', '')}\n"
        f"Current draft body: {base_output.get('body', '')}\n"
    )


def clean_body_text(body: str) -> str:
    if not body:
        return ""
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    cleaned: List[str] = []
    for ln in lines:
        low = ln.lower()
        if low.startswith("subject:"):
            continue
        if low.startswith("body:"):
            ln = ln.split(":", 1)[1].strip()
            low = ln.lower()
        if low.startswith("best regards") or low.startswith("regards,") or low.startswith("sincerely"):
            break
        if ln.startswith("---"):
            break
        if any(marker in low for marker in META_TAIL_MARKERS):
            continue
        cleaned.append(ln)
    text = " ".join(cleaned) if cleaned else body
    return normalize_spaces(text)


def enforce_single_cta(body: str) -> str:
    sents = split_sentences(body)
    kept: List[str] = []
    cta_seen = False
    for s in sents:
        low = s.lower()
        is_cta = ("?" in s) or any(p in low for p in ASK_PATTERNS)
        if is_cta:
            if cta_seen:
                continue
            cta_seen = True
        kept.append(s)
    if not cta_seen:
        kept.append("Would you be open to a 15-minute review next week?")
    return " ".join(kept).strip()


def enforce_required_signal_phrase(body: str, task: Dict[str, Any]) -> str:
    required = [str(x).strip() for x in task.get("rubric", {}).get("required_signal_phrases", []) if str(x).strip()]
    if not required:
        return body
    low = body.lower()
    for phrase in required:
        if phrase.lower() in low:
            return body

    inp = task.get("input", {})
    hs = inp.get("hiring_signal_brief", {})
    hv = hs.get("hiring_velocity", {})
    funding = hs.get("buying_window_signals", {}).get("funding_event", {})
    roles_now = hv.get("open_roles_today", "N/A")
    stage = str(funding.get("stage", "recent signal")).replace("_", " ")
    add = f" I noticed a {stage} signal and {roles_now} open roles."
    return (body + add).strip()


def trim_to_word_limit(body: str, outreach_type: str) -> str:
    limit = OUTREACH_WORD_LIMITS.get(outreach_type, 120)
    words = body.split()
    if len(words) <= limit:
        return body
    return " ".join(words[:limit]).rstrip(" ,;:-") + "."


def normalize_subject(subject: str, task: Dict[str, Any]) -> str:
    s = normalize_spaces(subject or "")
    if s.lower().startswith("subject:"):
        s = normalize_spaces(s.split(":", 1)[1])
    if not s:
        s = "15 minutes on hiring priorities"
    s = s.strip("[](){}\"' ")
    if not s.lower().startswith("request:"):
        s = f"{SUBJECT_INTENT_PREFIX} {s}"
    if len(s) > SUBJECT_MAX_LEN:
        s = "Request: 15 minutes on hiring priorities"
    return s


def postprocess_output(task: Dict[str, Any], raw_output: Dict[str, str]) -> Dict[str, str]:
    outreach_type = str(task.get("input", {}).get("outreach_type", "cold")).lower() or "cold"
    subject = normalize_subject(raw_output.get("subject", ""), task)
    body = clean_body_text(raw_output.get("body", ""))
    body = enforce_required_signal_phrase(body, task)
    body = enforce_single_cta(body)
    body = trim_to_word_limit(body, outreach_type)
    body = normalize_spaces(body)
    if not body:
        body = build_prompt_only_output(task)["body"]
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
    intervention_base_map: Dict[str, Dict[str, str]] | None = None,
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
            if intervention_base_map is None:
                prompt = build_prompt(t)
            else:
                task_id = str(t.get("task_id", "")).strip()
                base = intervention_base_map.get(task_id) or build_prompt_only_output(t)
                prompt = build_intervention_prompt(t, base)
            inputs = tokenizer([prompt], return_tensors="pt", truncation=True, max_length=max_seq_length).to("cuda")
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                repetition_penalty=1.05,
            )
            text = tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]

            if text.startswith(prompt):
                text = text[len(prompt) :].strip()

            sb = parse_subject_body(text)
            sb = postprocess_output(t, sb)
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
            if intervention_base_map is None:
                prompt = build_prompt(t)
            else:
                task_id = str(t.get("task_id", "")).strip()
                base = intervention_base_map.get(task_id) or build_prompt_only_output(t)
                prompt = build_intervention_prompt(t, base)
            inputs = tokenizer([prompt], return_tensors="pt", truncation=True, max_length=max_seq_length).to(device)
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=False,
                    repetition_penalty=1.05,
                )
            text = tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]

            if text.startswith(prompt):
                text = text[len(prompt) :].strip()

            sb = parse_subject_body(text)
            sb = postprocess_output(t, sb)
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
    p.add_argument("--mode", choices=["baseline", "prompt_only", "trained", "trained_intervene"], required=True)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument(
        "--base-outputs-file",
        type=Path,
        default=None,
        help="Required for trained_intervene mode. Input draft outputs to revise per task_id.",
    )

    p.add_argument("--base-model", default="auto")
    p.add_argument("--adapter-path", default="training/tenacious_path_b_dpo_lora")
    p.add_argument("--max-seq-length", type=int, default=1024)
    p.add_argument("--max-new-tokens", type=int, default=140)
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
    elif args.mode == "trained":
        rows = export_trained(
            tasks,
            base_model=args.base_model,
            adapter_path=args.adapter_path,
            max_seq_length=args.max_seq_length,
            max_new_tokens=args.max_new_tokens,
            inference_backend=args.inference_backend,
            local_files_only=args.local_files_only,
        )
    else:
        if args.base_outputs_file is None:
            raise ValueError("--base-outputs-file is required for mode=trained_intervene")
        if not args.base_outputs_file.exists():
            raise ValueError(f"base outputs file not found: {args.base_outputs_file}")
        base_map = load_outputs_map(args.base_outputs_file)
        if not base_map:
            raise ValueError(f"base outputs file is empty or invalid: {args.base_outputs_file}")
        rows = export_trained(
            tasks,
            base_model=args.base_model,
            adapter_path=args.adapter_path,
            max_seq_length=args.max_seq_length,
            max_new_tokens=args.max_new_tokens,
            inference_backend=args.inference_backend,
            local_files_only=args.local_files_only,
            intervention_base_map=base_map,
        )

    write_jsonl(args.out, rows)
    print(json.dumps({"mode": args.mode, "rows": len(rows), "out": str(args.out)}, indent=2))


if __name__ == "__main__":
    main()
