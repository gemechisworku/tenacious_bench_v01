#!/usr/bin/env python3
"""Run contamination checks for Tenacious-Bench splits.

Checks implemented:
1. N-gram overlap (<1 shared 8-gram on input fields)
2. Embedding cosine (<0.85) with a cheap sentence-transformer encoder
3. Time-shift provenance validation for public-data date signals
4. Coverage across held_out vs train and held_out vs dev
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


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


def content_text(task: Dict[str, Any]) -> str:
    brief = task["input"]["hiring_signal_brief"]
    req = task["input"]["request_context"]["requested_capacity"][0]
    profile = task["input"]["request_context"].get("company_profile", {})
    bench_state = task["input"]["request_context"].get("bench_state", "")
    fields = [
        brief.get("prospect_domain", ""),
        brief.get("primary_segment_match", ""),
        str(brief.get("segment_confidence", "")),
        str(brief.get("hiring_velocity", {}).get("open_roles_today", "")),
        str(brief.get("hiring_velocity", {}).get("open_roles_60_days_ago", "")),
        str(brief.get("buying_window_signals", {}).get("funding_event", {}).get("closed_at", "")),
        str(brief.get("buying_window_signals", {}).get("layoff_event", {}).get("date", "")),
        str(brief.get("buying_window_signals", {}).get("leadership_change", {}).get("started_at", "")),
        req.get("stack", ""),
        str(req.get("count", "")),
        task["input"].get("outreach_type", ""),
        str(profile.get("company_size", "")),
        str(bench_state),
    ]
    return re.sub(r"\s+", " ", " ".join(fields).lower()).strip()


def ngrams(tokens: List[str], n: int) -> set:
    return {" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def norm(a: List[float]) -> float:
    return math.sqrt(sum(x * x for x in a))


def cosine(a: List[float], b: List[float]) -> float:
    na = norm(a)
    nb = norm(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot(a, b) / (na * nb)


def cheap_hash_embedding(text: str, dim: int = 256) -> List[float]:
    vec = [0.0] * dim
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest()[:8], 16)
        idx = h % dim
        sign = -1.0 if (h >> 1) & 1 else 1.0
        vec[idx] += sign
    return vec


class Embedder:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.backend = "hash_fallback"
        self.model = None
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self.model = SentenceTransformer(model_name)
            self.backend = "sentence_transformers"
        except Exception:
            self.model = None

    def encode(self, texts: List[str]) -> List[List[float]]:
        if self.model is not None:
            arr = self.model.encode(texts, normalize_embeddings=True)
            return [list(map(float, row)) for row in arr]
        return [cheap_hash_embedding(t) for t in texts]


def compare_pairs(
    held: List[Dict[str, Any]],
    ref: List[Dict[str, Any]],
    ref_name: str,
    embedder: Embedder,
    ngram_n: int,
    cosine_threshold: float,
) -> Dict[str, Any]:
    held_texts = [content_text(t) for t in held]
    ref_texts = [content_text(t) for t in ref]
    held_ngrams = [ngrams(t.split(), ngram_n) for t in held_texts]
    ref_ngrams = [ngrams(t.split(), ngram_n) for t in ref_texts]

    held_emb = embedder.encode(held_texts)
    ref_emb = embedder.encode(ref_texts)

    max_ngram_shared = 0
    max_cosine = 0.0
    ngram_hits = 0
    cosine_hits = 0
    ngram_samples: List[Dict[str, Any]] = []
    max_cos_pair: Dict[str, Any] = {}

    for hi, htask in enumerate(held):
        for ri, rtask in enumerate(ref):
            shared = len(held_ngrams[hi].intersection(ref_ngrams[ri]))
            max_ngram_shared = max(max_ngram_shared, shared)
            if shared >= 1:
                ngram_hits += 1
                if len(ngram_samples) < 10:
                    ngram_samples.append(
                        {
                            "held_out_task_id": htask["task_id"],
                            f"{ref_name}_task_id": rtask["task_id"],
                            f"shared_{ngram_n}gram_count": shared,
                        }
                    )

            c = cosine(held_emb[hi], ref_emb[ri])
            if c >= cosine_threshold:
                cosine_hits += 1
            if c > max_cosine:
                max_cosine = c
                max_cos_pair = {
                    "held_out_task_id": htask["task_id"],
                    f"{ref_name}_task_id": rtask["task_id"],
                    "cosine_similarity": round(c, 6),
                }

    return {
        "ngram_overlap": {
            "n": ngram_n,
            "max_shared_count": max_ngram_shared,
            "threshold": f"< 1 shared {ngram_n}-gram",
            "flagged_pairs": ngram_hits,
            "sample_pairs": ngram_samples,
        },
        "embedding_similarity": {
            "backend": embedder.backend,
            "model_name": embedder.model_name,
            "max_cosine": round(max_cosine, 6),
            "threshold": "< 0.85",
            "flagged_pairs": cosine_hits,
            "max_pair": max_cos_pair,
        },
        "pass": bool(max_ngram_shared < 1 and max_cosine < cosine_threshold),
    }


def time_shift_checks(splits: Dict[str, List[Dict[str, Any]]], signal_window_days: int) -> Dict[str, Any]:
    issues: List[Dict[str, Any]] = []
    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    for split_name, tasks in splits.items():
        for task in tasks:
            task_id = task["task_id"]
            brief = task["input"]["hiring_signal_brief"]
            generated_at_raw = str(brief.get("generated_at", ""))
            try:
                generated_at = datetime.fromisoformat(generated_at_raw.replace("Z", "+00:00"))
            except Exception:
                issues.append(
                    {"task_id": task_id, "split": split_name, "field": "generated_at", "issue": "invalid_iso_datetime"}
                )
                continue

            dates = {
                "funding_closed_at": brief["buying_window_signals"]["funding_event"].get("closed_at"),
                "layoff_date": brief["buying_window_signals"]["layoff_event"].get("date"),
                "leadership_started_at": brief["buying_window_signals"]["leadership_change"].get("started_at"),
            }
            for field, raw_value in dates.items():
                raw = str(raw_value or "")
                if "YYYY" in raw:
                    issues.append({"task_id": task_id, "split": split_name, "field": field, "issue": "placeholder_date"})
                    continue
                if not date_re.match(raw):
                    issues.append({"task_id": task_id, "split": split_name, "field": field, "issue": "invalid_date_format"})
                    continue
                event_dt = datetime.fromisoformat(f"{raw}T00:00:00+00:00")
                if event_dt > generated_at:
                    issues.append({"task_id": task_id, "split": split_name, "field": field, "issue": "event_after_generation"})
                lookback_days = (generated_at - event_dt).days
                if lookback_days > signal_window_days:
                    issues.append(
                        {
                            "task_id": task_id,
                            "split": split_name,
                            "field": field,
                            "issue": "outside_signal_window",
                            "lookback_days": lookback_days,
                        }
                    )

    return {
        "signal_window_days": signal_window_days,
        "issue_count": len(issues),
        "issues_sample": issues[:30],
        "pass": len(issues) == 0,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run contamination checks for Tenacious-Bench splits.")
    p.add_argument("--dataset-root", type=Path, default=Path("tenacious_bench_v0.1"))
    p.add_argument("--out", type=Path, default=Path("tenacious_bench_v0.1/contamination_check.json"))
    p.add_argument("--embedding-model", type=str, default="sentence-transformers/all-MiniLM-L6-v2")
    p.add_argument("--ngram-n", type=int, default=8)
    p.add_argument("--cosine-threshold", type=float, default=0.85)
    p.add_argument("--signal-window-days", type=int, default=730)
    return p.parse_args()


def main() -> None:
    args = parse_args()

    splits = {
        "train": read_jsonl(args.dataset_root / "train" / "tasks.jsonl"),
        "dev": read_jsonl(args.dataset_root / "dev" / "tasks.jsonl"),
        "held_out": read_jsonl(args.dataset_root / "held_out" / "tasks.jsonl"),
    }

    embedder = Embedder(args.embedding_model)
    held_vs_train = compare_pairs(
        held=splits["held_out"],
        ref=splits["train"],
        ref_name="train",
        embedder=embedder,
        ngram_n=args.ngram_n,
        cosine_threshold=args.cosine_threshold,
    )
    held_vs_dev = compare_pairs(
        held=splits["held_out"],
        ref=splits["dev"],
        ref_name="dev",
        embedder=embedder,
        ngram_n=args.ngram_n,
        cosine_threshold=args.cosine_threshold,
    )
    time_shift = time_shift_checks(splits, signal_window_days=args.signal_window_days)

    summary_max_ngram = max(
        int(held_vs_train["ngram_overlap"]["max_shared_count"]),
        int(held_vs_dev["ngram_overlap"]["max_shared_count"]),
    )
    summary_max_cos = max(
        float(held_vs_train["embedding_similarity"]["max_cosine"]),
        float(held_vs_dev["embedding_similarity"]["max_cosine"]),
    )
    report = {
        "coverage": {
            "pairs_checked": ["held_out_vs_train", "held_out_vs_dev"],
            "split_sizes": {k: len(v) for k, v in splits.items()},
        },
        "checks": {
            "ngram_overlap_8gram_max_shared_count": summary_max_ngram,
            "ngram_overlap_threshold": "< 1 shared 8-gram between held_out and each reference split",
            "embedding_similarity_max_cosine": round(summary_max_cos, 6),
            "embedding_similarity_threshold": "< 0.85",
            "held_out_vs_train": held_vs_train,
            "held_out_vs_dev": held_vs_dev,
            "time_shift": time_shift,
        },
        "flagged_counts": {
            "ngram_pairs_flagged": int(held_vs_train["ngram_overlap"]["flagged_pairs"])
            + int(held_vs_dev["ngram_overlap"]["flagged_pairs"]),
            "embedding_pairs_flagged": int(held_vs_train["embedding_similarity"]["flagged_pairs"])
            + int(held_vs_dev["embedding_similarity"]["flagged_pairs"]),
            "time_shift_tasks_flagged": int(time_shift["issue_count"]),
        },
        "pass": bool(held_vs_train["pass"] and held_vs_dev["pass"] and time_shift["pass"]),
    }

    write_json(args.out, report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

