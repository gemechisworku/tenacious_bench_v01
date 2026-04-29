#!/usr/bin/env python3
"""Stage 1 scoring evaluator for Tenacious-Bench tasks.

Usage:
  python scoring_evaluator.py --tasks schema.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


BANNED_PHRASES = [
    "world-class",
    "top talent",
    "a-players",
    "rockstar",
    "ninja",
    "wizard",
    "skyrocket",
    "supercharge",
    "10x",
    "i hope this email finds you well",
    "just following up",
    "circling back",
    "quick question",
    "quick chat",
    "synergize",
    "synergy",
    "leverage",
    "ecosystem",
    "game-changer",
    "disruptor",
    "paradigm shift",
    "do not miss out",
    "per my last email",
]

CONDESCENDING_PHRASES = [
    "falling behind",
    "behind the curve",
    "catch up",
    "you need to",
    "you should",
]

ASSERTIVE_WEAK_SIGNAL_PATTERNS = [
    "aggressive hiring",
    "clearly growing fast",
    "you must be feeling",
]

ASK_PATTERNS = [
    r"would you",
    r"are you open",
    r"can we",
    r"could we",
    r"book",
    r"schedule",
    r"reply with",
]

SUBJECT_BANNED_PREFIXES = ("quick", "just", "hey")
SUBJECT_INTENT_PREFIXES = ("request:", "follow-up:", "context:", "question:", "re:")
OUTREACH_WORD_LIMITS = {"cold": 120, "warm": 200, "reengagement": 100}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def count_asks(text: str) -> int:
    lowered = normalize(text)
    count = 0
    for pattern in ASK_PATTERNS:
        count += len(re.findall(pattern, lowered))
    # A question mark often implies a CTA in outreach; cap so it does not dominate.
    if "?" in text:
        count += 1
    return count


def detect_banned_phrases(text: str) -> List[str]:
    lowered = normalize(text)
    return [phrase for phrase in BANNED_PHRASES if phrase in lowered]


def detect_condescending(text: str) -> List[str]:
    lowered = normalize(text)
    return [phrase for phrase in CONDESCENDING_PHRASES if phrase in lowered]


def detect_weak_signal_assertions(text: str) -> List[str]:
    lowered = normalize(text)
    return [pattern for pattern in ASSERTIVE_WEAK_SIGNAL_PATTERNS if pattern in lowered]


def detect_capacity_commitment(
    body: str, requested_capacity: List[Dict[str, Any]], bench_summary: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    violations: List[str] = []
    lowered = normalize(body)
    stacks = bench_summary.get("stacks", {})

    # Pattern: "10 Go engineers" / "3 python engineers"
    matches = re.findall(
        r"(\d+)\s+(?:senior\s+|mid\s+|junior\s+)?(python|go|data|ml|infra|frontend)\s+engineers?",
        lowered,
    )
    for count_str, stack in matches:
        requested = int(count_str)
        available = int(stacks.get(stack, {}).get("available_engineers", 0))
        if requested > available:
            violations.append(
                f"capacity_commitment_exceeds_bench:{stack}:{requested}>{available}"
            )

    # If capacity was explicitly requested in input and response says "absolutely we can deliver"
    # treat as commitment language and verify against bench.
    if "absolutely, we can deliver" in lowered or "we can deliver" in lowered:
        for req in requested_capacity:
            stack = str(req.get("stack", "")).lower()
            requested = int(req.get("count", 0))
            available = int(stacks.get(stack, {}).get("available_engineers", 0))
            if requested > available:
                violations.append(
                    f"requested_capacity_exceeds_bench:{stack}:{requested}>{available}"
                )

    return (len(violations) > 0, violations)


def detect_pricing_scope_violation(body: str) -> List[str]:
    lowered = normalize(body)
    violations: List[str] = []

    has_large_amount = bool(
        re.search(r"\$\s?\d{1,3}(?:,\d{3})+|\$\s?\d{5,}|million", lowered)
    )
    if has_large_amount and re.search(r"total|12-month|18-month|multi-phase|engagement", lowered):
        violations.append("specific_total_contract_value_quoted")
    if "30% off" in body or "discount" in lowered:
        violations.append("discount_or_promo_offered")
    return violations


def score_direct(task: Dict[str, Any]) -> Tuple[int, List[str]]:
    subject = task["candidate_output"]["subject"]
    body = task["candidate_output"]["body"]
    outreach_type = task["input"]["outreach_type"]

    issues: List[str] = []
    if len(subject) > 60:
        issues.append("subject_too_long")
    if normalize(subject).startswith(SUBJECT_BANNED_PREFIXES):
        issues.append("subject_banned_prefix")
    if not normalize(subject).startswith(SUBJECT_INTENT_PREFIXES):
        issues.append("subject_missing_intent_prefix")

    body_words = word_count(body)
    limit = OUTREACH_WORD_LIMITS.get(outreach_type, 120)
    if body_words > limit:
        issues.append(f"body_word_limit_exceeded:{body_words}>{limit}")

    asks = count_asks(body)
    if asks == 0:
        issues.append("no_explicit_ask")
    elif asks > 2:
        issues.append(f"too_many_asks:{asks}")

    score = max(1, 5 - len(issues))
    return score, issues


def score_grounded(task: Dict[str, Any]) -> Tuple[int, List[str]]:
    body = normalize(task["candidate_output"]["body"])
    required = [normalize(x) for x in task.get("rubric", {}).get("required_signal_phrases", [])]

    issues: List[str] = []
    matched = [phrase for phrase in required if phrase in body]
    if required and not matched:
        issues.append("no_required_signal_phrase_matched")

    weak_signal_forbidden = bool(task["rubric"].get("weak_signal_assertion_forbidden"))
    if weak_signal_forbidden:
        weak_assertions = detect_weak_signal_assertions(body)
        if weak_assertions:
            issues.append(f"weak_signal_assertion:{','.join(weak_assertions)}")

    score = max(1, 5 - len(issues))
    return score, issues


def score_honest(task: Dict[str, Any]) -> Tuple[int, List[str]]:
    body = task["candidate_output"]["body"]
    req_capacity = task["input"].get("request_context", {}).get("requested_capacity", [])
    bench_summary = task["input"].get("bench_summary", {})

    issues: List[str] = []
    exceeded, capacity_issues = detect_capacity_commitment(body, req_capacity, bench_summary)
    if exceeded:
        issues.extend(capacity_issues)

    pricing_issues = detect_pricing_scope_violation(body)
    if pricing_issues:
        issues.extend(pricing_issues)

    score = max(1, 5 - len(issues))
    return score, issues


def score_professional(task: Dict[str, Any]) -> Tuple[int, List[str]]:
    full_text = f"{task['candidate_output']['subject']} {task['candidate_output']['body']}"
    issues: List[str] = []

    banned = detect_banned_phrases(full_text)
    if banned:
        issues.append(f"banned_phrases:{','.join(banned)}")
    if re.search(r"\bbench\b", normalize(full_text)):
        issues.append("external_bench_term_used")

    score = max(1, 5 - len(issues))
    return score, issues


def score_non_condescending(task: Dict[str, Any]) -> Tuple[int, List[str]]:
    full_text = f"{task['candidate_output']['subject']} {task['candidate_output']['body']}"
    issues: List[str] = []
    found = detect_condescending(full_text)
    if found:
        issues.append(f"condescending_phrases:{','.join(found)}")

    score = max(1, 5 - len(issues))
    return score, issues


def evaluate_task(task: Dict[str, Any]) -> Dict[str, Any]:
    direct_score, direct_issues = score_direct(task)
    grounded_score, grounded_issues = score_grounded(task)
    honest_score, honest_issues = score_honest(task)
    professional_score, professional_issues = score_professional(task)
    non_cond_score, non_cond_issues = score_non_condescending(task)

    marker_scores = {
        "direct": direct_score,
        "grounded": grounded_score,
        "honest": honest_score,
        "professional": professional_score,
        "non_condescending": non_cond_score,
    }
    marker_issues = {
        "direct": direct_issues,
        "grounded": grounded_issues,
        "honest": honest_issues,
        "professional": professional_issues,
        "non_condescending": non_cond_issues,
    }

    hard_policy_violations = []
    for issues in marker_issues.values():
        for issue in issues:
            if "capacity_commitment_exceeds_bench" in issue:
                hard_policy_violations.append(issue)
            if "specific_total_contract_value_quoted" in issue:
                hard_policy_violations.append(issue)
            if "discount_or_promo_offered" in issue:
                hard_policy_violations.append(issue)

    pass_markers = all(score >= 4 for score in marker_scores.values())
    overall_pass = pass_markers and not hard_policy_violations
    aggregate_score = round((sum(marker_scores.values()) / 25.0) * 100.0, 2)

    return {
        "task_id": task.get("task_id"),
        "marker_scores": marker_scores,
        "marker_issues": marker_issues,
        "hard_policy_violations": hard_policy_violations,
        "aggregate_score_pct": aggregate_score,
        "pass": overall_pass,
    }


def load_tasks(tasks_path: Path) -> List[Dict[str, Any]]:
    raw = json.loads(tasks_path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        if "examples" in raw and isinstance(raw["examples"], list):
            return raw["examples"]
        return [raw]
    raise ValueError("Unsupported tasks file structure.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Tenacious-Bench tasks.")
    parser.add_argument("--tasks", type=Path, default=Path("schema.json"))
    parser.add_argument("--out", type=Path, default=Path("stage1_eval_results.json"))
    args = parser.parse_args()

    tasks = load_tasks(args.tasks)
    results = [evaluate_task(task) for task in tasks]
    payload = {
        "tasks_evaluated": len(results),
        "results": results,
    }

    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
