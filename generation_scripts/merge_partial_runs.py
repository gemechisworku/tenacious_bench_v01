#!/usr/bin/env python3
"""Merge separately generated dataset runs into one unified dataset folder.

Use this when synthesis and non-synthesis were generated in separate runs and
you need a single final `tenacious_bench_v0.1` dataset without re-generation.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generation_scripts.build_stage2_dataset import (  # noqa: E402
    contamination_report,
    inter_rater_snapshot,
    split_dataset_grouped,
    to_jsonl,
)
SPLITS = ("train", "dev", "held_out")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def load_run_tasks(run_root: Path) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    for split in SPLITS:
        tasks.extend(read_jsonl(run_root / split / "tasks.jsonl"))
    return tasks


def dedupe_by_task_id(tasks: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    seen: Dict[str, Dict[str, Any]] = {}
    dup_count = 0
    for t in tasks:
        task_id = str(t.get("task_id", "")).strip()
        if not task_id:
            continue
        if task_id in seen:
            dup_count += 1
            continue
        seen[task_id] = t
    return {"tasks": list(seen.values()), "duplicates_dropped": dup_count}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--synth-root", default="tenacious_bench_synth_only")
    p.add_argument("--other-root", default="tenacious_bench_other_only")
    p.add_argument("--out-root", default="tenacious_bench_v0.1")
    p.add_argument("--expected-total", type=int, default=250)
    p.add_argument("--split-search-tries", type=int, default=300)
    return p.parse_args()


def similarity_key(task: Dict[str, Any]) -> str:
    brief = task["input"]["hiring_signal_brief"]
    req = task["input"]["request_context"]["requested_capacity"][0]
    return "|".join(
        [
            str(brief.get("prospect_domain", "")),
            str(brief.get("primary_segment_match", "")),
            str(req.get("stack", "")),
            str(req.get("count", "")),
            str(task["input"].get("outreach_type", "")),
        ]
    )


def split_grouped_seed(tasks: List[Dict[str, Any]], seed: int) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for t in tasks:
        grouped.setdefault(similarity_key(t), []).append(t)
    groups = list(grouped.values())
    rnd = random.Random(seed)
    rnd.shuffle(groups)

    total = len(tasks)
    target_train = int(total * 0.5)
    target_dev = int(total * 0.3)

    train: List[Dict[str, Any]] = []
    dev: List[Dict[str, Any]] = []
    held: List[Dict[str, Any]] = []
    for g in groups:
        if len(train) + len(g) <= target_train:
            train.extend(g)
        elif len(dev) + len(g) <= target_dev:
            dev.extend(g)
        else:
            held.extend(g)

    while len(train) < target_train and held:
        train.append(held.pop())
    while len(dev) < target_dev and held:
        dev.append(held.pop())
    return {"train": train, "dev": dev, "held_out": held}


def choose_best_split(tasks: List[Dict[str, Any]], tries: int) -> Dict[str, Any]:
    best = None
    for seed in range(max(1, tries)):
        splits = split_grouped_seed(tasks, seed)
        rep = contamination_report(splits)
        ngram = int(rep["checks"]["ngram_overlap_8gram_max_shared_count"])
        cosine = float(rep["checks"]["embedding_similarity_max_cosine"])
        passed = bool(rep["pass"])
        # Higher is better: pass first, then lower ngram, then lower cosine.
        score = (1 if passed else 0, -ngram, -cosine)
        candidate = {"seed": seed, "splits": splits, "contamination": rep, "score": score}
        if best is None or candidate["score"] > best["score"]:
            best = candidate
            if passed:
                break
    assert best is not None
    return best


def main() -> None:
    args = parse_args()
    synth_root = ROOT / args.synth_root
    other_root = ROOT / args.other_root
    out_root = ROOT / args.out_root

    synth_tasks = load_run_tasks(synth_root)
    other_tasks = load_run_tasks(other_root)
    combined = synth_tasks + other_tasks

    deduped = dedupe_by_task_id(combined)
    tasks: List[Dict[str, Any]] = deduped["tasks"]
    duplicates_dropped = int(deduped["duplicates_dropped"])

    # Search for the cleanest split available without re-generation.
    # Keep legacy seed=42 helper as baseline reference.
    _baseline = split_dataset_grouped(tasks)
    chosen = choose_best_split(tasks, tries=args.split_search_tries)
    splits = chosen["splits"]
    out_root.mkdir(parents=True, exist_ok=True)
    for split_name, split_tasks in splits.items():
        to_jsonl(out_root / split_name / "tasks.jsonl", split_tasks)

    contamination = chosen["contamination"]
    (out_root / "contamination_check.json").write_text(
        json.dumps(contamination, indent=2), encoding="utf-8"
    )

    inter_rater = inter_rater_snapshot(tasks)
    (out_root / "inter_rater_agreement.json").write_text(
        json.dumps(inter_rater, indent=2), encoding="utf-8"
    )

    source_mode_counts = Counter(str(t.get("source_mode", "unknown")) for t in tasks)
    report = {
        "synth_root": args.synth_root,
        "other_root": args.other_root,
        "out_root": args.out_root,
        "synth_tasks_loaded": len(synth_tasks),
        "other_tasks_loaded": len(other_tasks),
        "combined_before_dedupe": len(combined),
        "duplicates_dropped_by_task_id": duplicates_dropped,
        "total_after_dedupe": len(tasks),
        "expected_total": args.expected_total,
        "expected_total_match": len(tasks) == args.expected_total,
        "split_counts": {k: len(v) for k, v in splits.items()},
        "split_seed_selected": chosen["seed"],
        "split_search_tries": args.split_search_tries,
        "source_mode_counts": dict(source_mode_counts),
        "contamination_pass": bool(contamination.get("pass")),
        "inter_rater_overall_pct": inter_rater.get("overall_pct"),
    }
    (out_root / "merge_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
