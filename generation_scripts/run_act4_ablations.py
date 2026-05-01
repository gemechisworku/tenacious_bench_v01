#!/usr/bin/env python3
"""Run ACT IV ablations (Delta A/B/C + Cost-Pareto) for Tenacious-Bench held-out.

This script is designed for two modes:
1) Smoke mode (small --limit) to validate pipeline quickly.
2) Full held-out run for final ACT IV artifacts.

Outputs:
- ablation_results.json
- held_out_traces.jsonl
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import time
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, Iterable, List, Optional


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


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
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


def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def to_candidate_output(obj: Any) -> Dict[str, str]:
    if isinstance(obj, dict):
        if "subject" in obj and "body" in obj:
            return {"subject": str(obj.get("subject", "")), "body": str(obj.get("body", ""))}
        if "candidate_output" in obj and isinstance(obj["candidate_output"], dict):
            co = obj["candidate_output"]
            return {"subject": str(co.get("subject", "")), "body": str(co.get("body", ""))}
    if isinstance(obj, str):
        if "\nBody:" in obj and obj.lower().startswith("subject:"):
            first, rest = obj.split("\nBody:", 1)
            return {"subject": first[len("Subject:"):].strip(), "body": rest.strip()}
        return {"subject": "", "body": obj}
    return {"subject": "", "body": ""}


def load_outputs_map(path: Optional[Path]) -> Dict[str, Dict[str, str]]:
    if path is None:
        return {}
    rows = read_jsonl(path)
    out: Dict[str, Dict[str, str]] = {}
    for row in rows:
        task_id = str(row.get("task_id", "")).strip()
        if not task_id:
            continue
        out[task_id] = to_candidate_output(row)
    return out


def build_prompt_only_output(task: Dict[str, Any]) -> Dict[str, str]:
    inp = task.get("input", {})
    hs = inp.get("hiring_signal_brief", {})
    hv = hs.get("hiring_velocity", {})
    funding = hs.get("buying_window_signals", {}).get("funding_event", {})
    prospect = hs.get("prospect_name", "there")
    roles_now = hv.get("open_roles_today", "N/A")
    roles_prev = hv.get("open_roles_60_days_ago", "N/A")
    funding_stage = funding.get("stage", "recent signal")

    subject = "Request: 15 minutes on hiring priorities"
    body = (
        f"Hi {prospect}, I noticed your open roles moved from {roles_prev} to {roles_now}. "
        f"I also saw a {funding_stage} signal in your recent trajectory where available. "
        "If useful, I can share two scoped options aligned to confirmed capacity only. "
        "Would you be open to a 15-minute review next week?"
    )
    return {"subject": subject, "body": body}


def approx_tokens(text: str) -> int:
    # Rough token proxy for cost estimation when exact tokenizer isn't available.
    words = len(text.split())
    return max(1, int(words * 1.3))


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    rank = (len(sorted_vals) - 1) * p
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return sorted_vals[lo]
    frac = rank - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def paired_bootstrap(diffs: List[float], iterations: int, seed: int) -> Dict[str, Any]:
    if not diffs:
        return {
            "n": 0,
            "mean_diff": 0.0,
            "ci95": {"low": 0.0, "high": 0.0},
            "p_value_one_sided_gt0": 1.0,
            "p_value_two_sided": 1.0,
        }

    rng = random.Random(seed)
    n = len(diffs)
    observed = mean(diffs)
    reps: List[float] = []
    for _ in range(iterations):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        reps.append(mean(sample))

    ci_low = percentile(reps, 0.025)
    ci_high = percentile(reps, 0.975)

    le_zero = sum(1 for x in reps if x <= 0.0)
    ge_zero = sum(1 for x in reps if x >= 0.0)

    p_one = (le_zero + 1) / (iterations + 1)  # H1: mean diff > 0
    p_two = 2 * min((le_zero + 1) / (iterations + 1), (ge_zero + 1) / (iterations + 1))
    p_two = min(1.0, p_two)

    return {
        "n": n,
        "mean_diff": round(observed, 6),
        "ci95": {"low": round(ci_low, 6), "high": round(ci_high, 6)},
        "p_value_one_sided_gt0": round(p_one, 6),
        "p_value_two_sided": round(p_two, 6),
    }


def summarize_variant(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    scores = [float(r["score"]["aggregate_score_pct"]) for r in rows]
    passes = [bool(r["score"]["pass"]) for r in rows]
    latencies = [float(r["latency_ms"]) for r in rows]
    costs = [float(r["cost_usd"]) for r in rows]

    return {
        "n": len(rows),
        "mean_score_pct": round(mean(scores), 6) if scores else 0.0,
        "median_score_pct": round(median(scores), 6) if scores else 0.0,
        "pass_rate": round(sum(1 for x in passes if x) / len(passes), 6) if passes else 0.0,
        "mean_latency_ms": round(mean(latencies), 6) if latencies else 0.0,
        "median_latency_ms": round(median(latencies), 6) if latencies else 0.0,
        "mean_cost_usd": round(mean(costs), 8) if costs else 0.0,
        "median_cost_usd": round(median(costs), 8) if costs else 0.0,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run ACT IV ablation evaluation on held-out tasks.")
    p.add_argument("--held-out", type=Path, default=Path("tenacious_bench_v0.1/held_out/tasks.jsonl"))
    p.add_argument("--evaluator", type=Path, default=Path("scoring_evaluator.py"))
    p.add_argument("--out-ablation", type=Path, default=Path("ablation_results.json"))
    p.add_argument("--out-traces", type=Path, default=Path("held_out_traces.jsonl"))

    p.add_argument("--trained-outputs-file", type=Path, default=None)
    p.add_argument("--prompt-outputs-file", type=Path, default=None)
    p.add_argument("--baseline-outputs-file", type=Path, default=None)
    p.add_argument("--trained-adapter-path", type=Path, default=Path("training/tenacious_path_b_dpo_lora"))
    p.add_argument("--trained-base-model", type=str, default="auto")
    p.add_argument("--trained-max-seq-length", type=int, default=1024)
    p.add_argument("--trained-max-new-tokens", type=int, default=220)
    p.add_argument(
        "--trained-inference-backend",
        choices=["auto", "unsloth", "transformers"],
        default="auto",
    )
    p.add_argument(
        "--trained-local-files-only",
        action="store_true",
        help="Do not download base model files for trained inference.",
    )

    p.add_argument("--week10-retail-score", type=float, default=None)
    p.add_argument("--bootstrap-iters", type=int, default=5000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--limit", type=int, default=0, help="For smoke test. 0 means full held-out.")

    p.add_argument("--assume-cost-baseline", type=float, default=0.0, help="USD per task")
    p.add_argument("--assume-cost-prompt", type=float, default=0.0, help="USD per task")
    p.add_argument("--assume-cost-trained", type=float, default=0.0, help="USD per task")
    return p.parse_args()


def build_trained_map_via_inference(tasks: List[Dict[str, Any]], args: argparse.Namespace) -> Dict[str, Dict[str, str]]:
    export_path = Path(__file__).with_name("export_heldout_outputs.py")
    export_module = load_module(export_path, "export_heldout_outputs_module")

    rows = export_module.export_trained(
        tasks,
        base_model=args.trained_base_model,
        adapter_path=str(args.trained_adapter_path),
        max_seq_length=args.trained_max_seq_length,
        max_new_tokens=args.trained_max_new_tokens,
        inference_backend=args.trained_inference_backend,
        local_files_only=args.trained_local_files_only,
    )
    out: Dict[str, Dict[str, str]] = {}
    for row in rows:
        task_id = str(row.get("task_id", "")).strip()
        if not task_id:
            continue
        out[task_id] = to_candidate_output(row)
    return out


def main() -> None:
    args = parse_args()

    evaluate = load_evaluator(args.evaluator)
    tasks = read_jsonl(args.held_out)
    if args.limit and args.limit > 0:
        tasks = tasks[: args.limit]

    baseline_map = load_outputs_map(args.baseline_outputs_file)
    prompt_map = load_outputs_map(args.prompt_outputs_file)
    trained_map = load_outputs_map(args.trained_outputs_file)

    if not trained_map:
        trained_map = build_trained_map_via_inference(tasks, args)
    if not trained_map:
        raise ValueError(
            "No trained outputs available. Provide --trained-outputs-file or ensure "
            "--trained-adapter-path with valid inference dependencies."
        )

    traces: List[Dict[str, Any]] = []

    for task in tasks:
        task_id = str(task.get("task_id", ""))
        if not task_id:
            continue

        # Baseline variant
        t0 = time.perf_counter()
        baseline_output = baseline_map.get(task_id) or to_candidate_output(task.get("candidate_output", {}))
        baseline_latency_ms = (time.perf_counter() - t0) * 1000.0
        baseline_score = evaluate(task=task, agent_output=baseline_output)

        # Prompt-only variant
        t1 = time.perf_counter()
        prompt_output = prompt_map.get(task_id) or build_prompt_only_output(task)
        prompt_latency_ms = (time.perf_counter() - t1) * 1000.0
        prompt_score = evaluate(task=task, agent_output=prompt_output)

        # Trained variant
        t2 = time.perf_counter()
        trained_output = trained_map.get(task_id)
        trained_source = "file" if args.trained_outputs_file else "live_inference"
        if trained_output is None:
            raise ValueError(f"Missing trained output for task_id={task_id}")
        trained_latency_ms = (time.perf_counter() - t2) * 1000.0
        trained_score = evaluate(task=task, agent_output=trained_output)

        prompt_text = json.dumps(task.get("input", {}), ensure_ascii=False)

        variants = [
            ("baseline", baseline_output, baseline_score, baseline_latency_ms, args.assume_cost_baseline, "file_or_task_candidate"),
            ("prompt_only", prompt_output, prompt_score, prompt_latency_ms, args.assume_cost_prompt, "file_or_rule"),
            ("trained", trained_output, trained_score, trained_latency_ms, args.assume_cost_trained, trained_source),
        ]

        for variant_name, output, score, latency_ms, cost_usd, source in variants:
            out_text = f"Subject: {output.get('subject', '')}\nBody: {output.get('body', '')}"
            traces.append(
                {
                    "task_id": task_id,
                    "variant": variant_name,
                    "variant_source": source,
                    "output": output,
                    "score": score,
                    "aggregate_score_pct": score.get("aggregate_score_pct", 0.0),
                    "pass": score.get("pass", False),
                    "latency_ms": round(latency_ms, 4),
                    "cost_usd": round(cost_usd, 8),
                    "approx_prompt_tokens": approx_tokens(prompt_text),
                    "approx_output_tokens": approx_tokens(out_text),
                }
            )

    # Group traces by variant
    grouped: Dict[str, List[Dict[str, Any]]] = {"baseline": [], "prompt_only": [], "trained": []}
    for row in traces:
        grouped[row["variant"]].append(row)

    summary = {k: summarize_variant(v) for k, v in grouped.items()}

    # Paired arrays for Delta A/B
    by_task_variant: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for row in traces:
        by_task_variant.setdefault(row["task_id"], {})[row["variant"]] = row

    def paired_diffs(left: str, right: str) -> List[float]:
        diffs: List[float] = []
        for task_id, m in by_task_variant.items():
            if left in m and right in m:
                diffs.append(float(m[left]["aggregate_score_pct"]) - float(m[right]["aggregate_score_pct"]))
        return diffs

    diffs_a = paired_diffs("trained", "baseline")
    diffs_b = paired_diffs("trained", "prompt_only")

    delta_a = paired_bootstrap(diffs_a, args.bootstrap_iters, args.seed)
    delta_b = paired_bootstrap(diffs_b, args.bootstrap_iters, args.seed + 1)

    delta_a["claim_positive_with_significance"] = bool(
        delta_a["n"] > 0
        and delta_a["ci95"]["low"] > 0.0
        and delta_a["p_value_one_sided_gt0"] < 0.05
    )
    delta_b["claim_training_beats_prompt_only"] = bool(
        delta_b["n"] > 0
        and delta_b["ci95"]["low"] > 0.0
        and delta_b["p_value_one_sided_gt0"] < 0.05
    )

    delta_c: Dict[str, Any] = {"available": False}
    if args.week10_retail_score is not None:
        trained_mean = summary["trained"]["mean_score_pct"]
        delta_c = {
            "available": True,
            "week10_retail_score": args.week10_retail_score,
            "trained_mean_score_pct": trained_mean,
            "mean_diff_pct": round(trained_mean - args.week10_retail_score, 6),
            "note": "Informational only; not a paired held-out test.",
        }

    # Cost-Pareto (trained vs baseline)
    trained_s = summary["trained"]
    baseline_s = summary["baseline"]
    prompt_s = summary["prompt_only"]

    def safe_ratio(num: float, den: float) -> Optional[float]:
        if den == 0:
            return None
        return round(num / den, 6)

    cost_pareto = {
        "trained_vs_baseline": {
            "score_lift_pct": round(trained_s["mean_score_pct"] - baseline_s["mean_score_pct"], 6),
            "latency_delta_ms": round(trained_s["mean_latency_ms"] - baseline_s["mean_latency_ms"], 6),
            "cost_delta_usd": round(trained_s["mean_cost_usd"] - baseline_s["mean_cost_usd"], 8),
            "cost_ratio": safe_ratio(trained_s["mean_cost_usd"], baseline_s["mean_cost_usd"]),
            "latency_ratio": safe_ratio(trained_s["mean_latency_ms"], baseline_s["mean_latency_ms"]),
        },
        "trained_vs_prompt_only": {
            "score_lift_pct": round(trained_s["mean_score_pct"] - prompt_s["mean_score_pct"], 6),
            "latency_delta_ms": round(trained_s["mean_latency_ms"] - prompt_s["mean_latency_ms"], 6),
            "cost_delta_usd": round(trained_s["mean_cost_usd"] - prompt_s["mean_cost_usd"], 8),
            "cost_ratio": safe_ratio(trained_s["mean_cost_usd"], prompt_s["mean_cost_usd"]),
            "latency_ratio": safe_ratio(trained_s["mean_latency_ms"], prompt_s["mean_latency_ms"]),
        },
    }

    run_mode = "smoke" if args.limit and args.limit > 0 else "full"
    results = {
        "run_mode": run_mode,
        "inputs": {
            "held_out": str(args.held_out),
            "evaluator": str(args.evaluator),
            "trained_outputs_file": str(args.trained_outputs_file) if args.trained_outputs_file else None,
            "trained_adapter_path": str(args.trained_adapter_path),
            "trained_base_model": args.trained_base_model,
            "trained_inference_backend": args.trained_inference_backend,
            "trained_local_files_only": bool(args.trained_local_files_only),
            "prompt_outputs_file": str(args.prompt_outputs_file) if args.prompt_outputs_file else None,
            "baseline_outputs_file": str(args.baseline_outputs_file) if args.baseline_outputs_file else None,
            "limit": args.limit,
            "bootstrap_iters": args.bootstrap_iters,
            "seed": args.seed,
        },
        "variant_summary": summary,
        "delta_a_trained_vs_week10_baseline": delta_a,
        "delta_b_trained_vs_prompt_only": delta_b,
        "delta_c_trained_vs_week10_retail": delta_c,
        "cost_pareto": cost_pareto,
        "notes": [
            "Trained variant is sourced from provided trained outputs file or live adapter inference only.",
            "No heuristic trained-output proxy is used in this script.",
        ],
    }

    write_json(args.out_ablation, results)
    write_jsonl(args.out_traces, traces)

    print(json.dumps({
        "run_mode": run_mode,
        "tasks_evaluated": len(by_task_variant),
        "outputs": {"ablation_results": str(args.out_ablation), "held_out_traces": str(args.out_traces)},
        "delta_a": delta_a,
        "delta_b": delta_b,
    }, indent=2))


if __name__ == "__main__":
    main()
