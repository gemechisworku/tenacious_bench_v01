#!/usr/bin/env python3
"""Build Path B preference files for SimPO training.

This script reads Tenacious-Bench train/dev task splits and writes preference pairs to:
  training_data/path_b/preferences_train.jsonl
  training_data/path_b/preferences_dev.jsonl

It uses `scoring_evaluator.py` for local quality checks to keep chosen/rejected ordering sane.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_evaluator(evaluator_path: Path):
    spec = importlib.util.spec_from_file_location("scoring_evaluator_module", evaluator_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load evaluator from {evaluator_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.evaluate


def build_prompt(task: Dict[str, Any]) -> str:
    inp = task.get("input", {})
    return (
        "You are a Tenacious outbound sales assistant. Draft one concise response that is grounded, "
        "honest, professional, and non-condescending.\n\n"
        f"Outreach type: {inp.get('outreach_type', 'cold')}\n"
        f"Hiring signal brief: {json.dumps(inp.get('hiring_signal_brief', {}), ensure_ascii=False)}\n"
        f"Competitor gap brief: {json.dumps(inp.get('competitor_gap_brief', {}), ensure_ascii=False)}\n"
        f"Bench summary: {json.dumps(inp.get('bench_summary', {}), ensure_ascii=False)}\n"
        f"Request context: {json.dumps(inp.get('request_context', {}), ensure_ascii=False)}\n"
        f"Prior thread: {json.dumps(inp.get('prior_thread', {}), ensure_ascii=False)}"
    )


def output_to_text(candidate_output: Dict[str, Any]) -> str:
    subject = str(candidate_output.get("subject", "")).strip()
    body = str(candidate_output.get("body", "")).strip()
    return f"Subject: {subject}\nBody: {body}".strip()


def text_to_candidate(text: str) -> Dict[str, str]:
    subject = ""
    body = text.strip()
    if "\nBody:" in text:
        first, rest = text.split("\nBody:", 1)
        if first.lower().startswith("subject:"):
            subject = first[len("Subject:") :].strip()
            body = rest.strip()
    return {"subject": subject, "body": body}


def detect_failure_family(eval_result: Dict[str, Any], prompt_text: str) -> str:
    issues: List[str] = []
    for marker_issues in eval_result.get("marker_issues", {}).values():
        issues.extend(marker_issues)
    joined = " ".join(issues).lower()
    p = prompt_text.lower()

    if any(k in joined for k in ["capacity_commitment", "specific_total_contract_value", "discount", "pricing"]):
        return "BEN"
    if any(k in joined for k in ["banned_phrases", "condescending", "external_bench_term"]):
        return "TON"
    if any(k in joined for k in ["required_signal", "weak_signal_assertion"]):
        return "SIG"
    if any(k in p for k in ["schedule", "slots", "calendar", "book"]):
        return "SCH"
    return "MTL"


def repair_candidate(task: Dict[str, Any]) -> str:
    inp = task.get("input", {})
    hs = inp.get("hiring_signal_brief", {})
    hv = hs.get("hiring_velocity", {})
    fund = hs.get("buying_window_signals", {}).get("funding_event", {})

    prospect = hs.get("prospect_name", "there")
    roles_now = hv.get("open_roles_today", "N/A")
    roles_prev = hv.get("open_roles_60_days_ago", "N/A")
    stage = fund.get("stage", "recent funding")
    closed = fund.get("closed_at", "recently")

    subject = "Request: 15 minutes on hiring plan"
    body = (
        f"Hi {prospect}, I noticed your open roles moved from {roles_prev} to {roles_now}. "
        f"I also saw a {stage} event around {closed} where available. "
        "If useful, I can share two scoped delivery options aligned to confirmed capacity. "
        "Would you be open to a 15-minute review next week?"
    )
    return output_to_text({"subject": subject, "body": body})


def degrade_response(chosen_text: str, family: str) -> str:
    tails = {
        "BEN": " We can absolutely deliver 10 Go engineers next week and give 30% off.",
        "TON": " You are falling behind and need to catch up immediately.",
        "SIG": " This is definitely true even without strong evidence.",
        "SCH": " I have already booked your calendar without confirmation.",
        "MTL": " Quick question quick chat quick follow-up can we can we can we?",
    }
    return chosen_text + tails.get(family, tails["MTL"])


def score_text(task: Dict[str, Any], text: str, evaluate_fn) -> Dict[str, Any]:
    return evaluate_fn(task=task, agent_output=text_to_candidate(text))


def make_preference_row(task: Dict[str, Any], evaluate_fn) -> Dict[str, Any]:
    prompt = build_prompt(task)
    source_mode = task.get("source_mode", "unknown")
    generator_family = task.get("metadata", {}).get("generator_model_family", "unknown_generator")

    baseline_text = output_to_text(task.get("candidate_output", {}))
    baseline_eval = score_text(task, baseline_text, evaluate_fn)
    family = detect_failure_family(baseline_eval, prompt)

    if baseline_eval.get("pass", False):
        chosen = baseline_text
        rejected = degrade_response(chosen, family)
    else:
        rejected = baseline_text
        chosen = repair_candidate(task)

    chosen_eval = score_text(task, chosen, evaluate_fn)
    rejected_eval = score_text(task, rejected, evaluate_fn)

    # Make sure chosen is stronger than rejected for training signal.
    if not chosen_eval.get("pass", False):
        chosen = repair_candidate(task)
        chosen_eval = score_text(task, chosen, evaluate_fn)

    if rejected_eval.get("pass", False):
        rejected = degrade_response(chosen, family)
        rejected_eval = score_text(task, rejected, evaluate_fn)

    if chosen_eval.get("aggregate_score_pct", 0.0) <= rejected_eval.get("aggregate_score_pct", 0.0):
        penalty_tails = [
            " We can also guarantee any headcount regardless of availability.",
            " This is a guaranteed outcome with no need to verify the signal.",
            " You are behind the curve and should act now before it's too late.",
            " If you sign by Friday, we will apply a 30% discount automatically.",
        ]
        for tail in penalty_tails:
            rejected = rejected + tail
            rejected_eval = score_text(task, rejected, evaluate_fn)
            if chosen_eval.get("aggregate_score_pct", 0.0) > rejected_eval.get("aggregate_score_pct", 0.0):
                break

    # Hard fallback: make chosen deterministic-safe and rejected deterministic-bad.
    if chosen_eval.get("aggregate_score_pct", 0.0) <= rejected_eval.get("aggregate_score_pct", 0.0):
        chosen = repair_candidate(task)
        chosen_eval = score_text(task, chosen, evaluate_fn)
        rejected = (
            "Subject: Quick chat on urgent hiring\n"
            "Body: We can guarantee any team size immediately with a 30% discount. "
            "You are falling behind and should catch up now."
        )
        rejected_eval = score_text(task, rejected, evaluate_fn)

    return {
        "task_id": task.get("task_id", ""),
        "prompt": prompt,
        "chosen": chosen,
        "rejected": rejected,
        "failure_family": family,
        "source_mode": source_mode,
        "generator_family": generator_family,
        "judge_family": "tenacious_rule_judge",
        "chosen_score": chosen_eval.get("aggregate_score_pct", 0.0),
        "rejected_score": rejected_eval.get("aggregate_score_pct", 0.0),
    }


def build_split(tasks: List[Dict[str, Any]], evaluate_fn) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    fam = Counter()
    src = Counter()
    strict_pref_violations = 0

    for task in tasks:
        row = make_preference_row(task, evaluate_fn)
        if row["chosen_score"] <= row["rejected_score"]:
            strict_pref_violations += 1
        fam[row["failure_family"]] += 1
        src[row["source_mode"]] += 1
        rows.append(row)

    summary = {
        "rows": len(rows),
        "failure_family_counts": dict(fam),
        "source_mode_counts": dict(src),
        "strict_preference_violations": strict_pref_violations,
    }
    return rows, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Path B preference files for SimPO training.")
    parser.add_argument("--project-root", type=Path, default=Path("."), help="Repository root path")
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    random.seed(args.seed)

    project_root = args.project_root.resolve()
    data_root = project_root / "tenacious_bench_v0.1"
    train_path = data_root / "train" / "tasks.jsonl"
    dev_path = data_root / "dev" / "tasks.jsonl"
    evaluator_path = project_root / "scoring_evaluator.py"

    out_dir = project_root / "training_data" / "path_b"
    out_train = out_dir / "preferences_train.jsonl"
    out_dev = out_dir / "preferences_dev.jsonl"
    out_train_dpo = out_dir / "preferences_train_dpo.jsonl"
    out_dev_dpo = out_dir / "preferences_dev_dpo.jsonl"
    out_manifest = out_dir / "build_manifest.json"

    for required in [train_path, dev_path, evaluator_path]:
        if not required.exists():
            raise FileNotFoundError(f"Required file not found: {required}")

    evaluate_fn = load_evaluator(evaluator_path)

    train_tasks = read_jsonl(train_path)
    dev_tasks = read_jsonl(dev_path)

    train_rows, train_summary = build_split(train_tasks, evaluate_fn)
    dev_rows, dev_summary = build_split(dev_tasks, evaluate_fn)

    write_jsonl(out_train, train_rows)
    write_jsonl(out_dev, dev_rows)

    # DPO trainer only needs prompt/chosen/rejected; write stripped files for Colab simplicity.
    train_rows_dpo = [{"prompt": r["prompt"], "chosen": r["chosen"], "rejected": r["rejected"]} for r in train_rows]
    dev_rows_dpo = [{"prompt": r["prompt"], "chosen": r["chosen"], "rejected": r["rejected"]} for r in dev_rows]
    write_jsonl(out_train_dpo, train_rows_dpo)
    write_jsonl(out_dev_dpo, dev_rows_dpo)

    manifest = {
        "project_root": str(project_root),
        "seed": args.seed,
        "inputs": {
            "train_tasks": str(train_path),
            "dev_tasks": str(dev_path),
            "evaluator": str(evaluator_path),
        },
        "outputs": {
            "preferences_train": str(out_train),
            "preferences_dev": str(out_dev),
            "preferences_train_dpo": str(out_train_dpo),
            "preferences_dev_dpo": str(out_dev_dpo),
        },
        "train_summary": train_summary,
        "dev_summary": dev_summary,
    }
    write_json(out_manifest, manifest)

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
