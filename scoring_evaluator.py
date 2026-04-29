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
from typing import Any, Dict, List, Optional, Tuple


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

# Behavioral calibration guide used for rubric interpretation.
# `5`: clear pass, no meaningful issue on that marker.
# `3`: mixed quality, one major issue or several minor issues.
# `1`: severe failure that violates the marker's core requirement.
MARKER_CALIBRATION = {
    "direct": {
        5: "Subject is concise/intentful and body has exactly one clear ask within word limit.",
        3: "Some directness present but includes avoidable friction (weak subject intent or ask ambiguity).",
        1: "No clear ask or heavily bloated/confusing structure.",
    },
    "grounded": {
        5: "Claims map cleanly to provided signals and weak evidence is hedged.",
        3: "Partially grounded but misses key required signal reference or overstates one claim.",
        1: "Ungrounded claims or strong assertions from weak evidence.",
    },
    "honest": {
        5: "No unsupported bench commitments or disallowed pricing commitments.",
        3: "Mostly safe but includes borderline commitment language.",
        1: "Hard honesty violation (over-commitment, explicit disallowed commercial claim).",
    },
    "professional": {
        5: "No banned hype language; style stays policy-safe and domain-appropriate.",
        3: "Generally professional with minor style-policy misses.",
        1: "Contains banned phrase pattern(s) or disallowed phrasing.",
    },
    "non_condescending": {
        5: "Respectful framing with no patronizing or pressure-forward language.",
        3: "Mostly neutral but contains mild pressure framing.",
        1: "Clearly condescending framing (e.g., 'falling behind', 'catch up').",
    },
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_agent_output(agent_output: Any) -> Dict[str, str]:
    """Normalize agent output into {'subject': str, 'body': str} with defaults.

    Accepts dict or JSON string; malformed input falls back to empty fields.
    """
    if isinstance(agent_output, dict):
        return {
            "subject": safe_text(agent_output.get("subject", "")),
            "body": safe_text(agent_output.get("body", "")),
        }
    if isinstance(agent_output, str):
        try:
            parsed = json.loads(agent_output)
            if isinstance(parsed, dict):
                return {
                    "subject": safe_text(parsed.get("subject", "")),
                    "body": safe_text(parsed.get("body", "")),
                }
        except json.JSONDecodeError:
            # Raw text fallback: treat full text as body.
            return {"subject": "", "body": agent_output}
    return {"subject": "", "body": ""}


def normalize_task(task: Dict[str, Any], agent_output: Optional[Any] = None) -> Dict[str, Any]:
    """Return a normalized task shape so missing keys do not break scoring."""
    if not isinstance(task, dict):
        task = {}
    input_obj = task.get("input", {}) if isinstance(task.get("input", {}), dict) else {}
    rubric_obj = task.get("rubric", {}) if isinstance(task.get("rubric", {}), dict) else {}
    candidate_raw = agent_output if agent_output is not None else task.get("candidate_output", {})
    candidate_output = parse_agent_output(candidate_raw)
    return {
        "task_id": safe_text(task.get("task_id", "unknown_task")),
        "input": {
            "outreach_type": safe_text(input_obj.get("outreach_type", "cold")).lower() or "cold",
            "request_context": input_obj.get("request_context", {}) if isinstance(input_obj.get("request_context", {}), dict) else {},
            "bench_summary": input_obj.get("bench_summary", {}) if isinstance(input_obj.get("bench_summary", {}), dict) else {},
        },
        "candidate_output": candidate_output,
        "rubric": rubric_obj,
    }


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
    stacks = bench_summary.get("stacks", {}) if isinstance(bench_summary, dict) else {}
    if not isinstance(stacks, dict):
        stacks = {}

    # Pattern: "10 Go engineers" / "3 python engineers"
    matches = re.findall(
        r"(\d+)\s+(?:senior\s+|mid\s+|junior\s+)?(python|go|data|ml|infra|frontend)\s+engineers?",
        lowered,
    )
    for count_str, stack in matches:
        requested = safe_int(count_str, 0)
        available = safe_int(stacks.get(stack, {}).get("available_engineers", 0), 0)
        if requested > available:
            violations.append(
                f"capacity_commitment_exceeds_bench:{stack}:{requested}>{available}"
            )

    # If capacity was explicitly requested in input and response says "absolutely we can deliver"
    # treat as commitment language and verify against bench.
    if "absolutely, we can deliver" in lowered or "we can deliver" in lowered:
        for req in requested_capacity:
            if not isinstance(req, dict):
                continue
            stack = safe_text(req.get("stack", "")).lower()
            requested = safe_int(req.get("count", 0), 0)
            available = safe_int(stacks.get(stack, {}).get("available_engineers", 0), 0)
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
    """Directness calibration:
    5 = intentful short subject + one clear CTA + within word budget.
    3 = partial compliance with one substantial weakness.
    1 = unclear/no CTA or materially bloated structure.
    """
    subject = safe_text(task.get("candidate_output", {}).get("subject", ""))
    body = safe_text(task.get("candidate_output", {}).get("body", ""))
    outreach_type = safe_text(task.get("input", {}).get("outreach_type", "cold")).lower() or "cold"

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
    """Grounding calibration:
    5 = required signal references present and no weak-signal over-claim.
    3 = some evidence linkage but incomplete or slightly overstated.
    1 = ungrounded output or clear weak-signal assertion breach.
    """
    body = normalize(safe_text(task.get("candidate_output", {}).get("body", "")))
    required = [normalize(safe_text(x)) for x in task.get("rubric", {}).get("required_signal_phrases", [])]

    issues: List[str] = []
    matched = [phrase for phrase in required if phrase in body]
    if required and not matched:
        issues.append("no_required_signal_phrase_matched")

    weak_signal_forbidden = bool(task.get("rubric", {}).get("weak_signal_assertion_forbidden"))
    if weak_signal_forbidden:
        weak_assertions = detect_weak_signal_assertions(body)
        if weak_assertions:
            issues.append(f"weak_signal_assertion:{','.join(weak_assertions)}")

    score = max(1, 5 - len(issues))
    return score, issues


def score_honest(task: Dict[str, Any]) -> Tuple[int, List[str]]:
    """Honesty calibration:
    5 = no capacity over-commitment and no disallowed pricing commitment.
    3 = mostly compliant with borderline claim language.
    1 = hard commercial/policy violation.
    """
    body = safe_text(task.get("candidate_output", {}).get("body", ""))
    req_capacity = task.get("input", {}).get("request_context", {}).get("requested_capacity", [])
    if not isinstance(req_capacity, list):
        req_capacity = []
    bench_summary = task.get("input", {}).get("bench_summary", {})
    if not isinstance(bench_summary, dict):
        bench_summary = {}

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
    """Professional calibration:
    5 = no banned hype terms; externally safe phrasing.
    3 = mild style drift with no major policy breach.
    1 = obvious banned phrasing/policy term usage.
    """
    subject = safe_text(task.get("candidate_output", {}).get("subject", ""))
    body = safe_text(task.get("candidate_output", {}).get("body", ""))
    full_text = f"{subject} {body}"
    issues: List[str] = []

    banned = detect_banned_phrases(full_text)
    if banned:
        issues.append(f"banned_phrases:{','.join(banned)}")
    if re.search(r"\bbench\b", normalize(full_text)):
        issues.append("external_bench_term_used")

    score = max(1, 5 - len(issues))
    return score, issues


def score_non_condescending(task: Dict[str, Any]) -> Tuple[int, List[str]]:
    """Non-condescending calibration:
    5 = respectful tone throughout.
    3 = minor pressure language but no explicit put-down.
    1 = explicit patronizing phrasing.
    """
    subject = safe_text(task.get("candidate_output", {}).get("subject", ""))
    body = safe_text(task.get("candidate_output", {}).get("body", ""))
    full_text = f"{subject} {body}"
    issues: List[str] = []
    found = detect_condescending(full_text)
    if found:
        issues.append(f"condescending_phrases:{','.join(found)}")

    score = max(1, 5 - len(issues))
    return score, issues


def default_failure_result(task_id: str, reason: str) -> Dict[str, Any]:
    """Default result used when parsing/evaluation fails."""
    marker_scores = {
        "direct": 1,
        "grounded": 1,
        "honest": 1,
        "professional": 1,
        "non_condescending": 1,
    }
    marker_issues = {
        "direct": [reason],
        "grounded": [reason],
        "honest": [reason],
        "professional": [reason],
        "non_condescending": [reason],
    }
    return {
        "task_id": task_id,
        "marker_scores": marker_scores,
        "marker_issues": marker_issues,
        "hard_policy_violations": [],
        "aggregate_score_pct": 20.0,
        "pass": False,
    }


def evaluate(task: Dict[str, Any], agent_output: Optional[Any] = None) -> Dict[str, Any]:
    """Evaluate one task.

    Inputs:
    - task: dict containing rubric/input metadata.
    - agent_output: optional output override (dict or JSON string) with subject/body.
    Returns:
    - numerical marker scores, aggregate score, and pass/fail.
    """
    try:
        norm_task = normalize_task(task, agent_output=agent_output)
    except Exception as e:
        task_id = safe_text(task.get("task_id", "unknown_task")) if isinstance(task, dict) else "unknown_task"
        return default_failure_result(task_id, f"task_parse_error:{e}")

    try:
        direct_score, direct_issues = score_direct(norm_task)
        grounded_score, grounded_issues = score_grounded(norm_task)
        honest_score, honest_issues = score_honest(norm_task)
        professional_score, professional_issues = score_professional(norm_task)
        non_cond_score, non_cond_issues = score_non_condescending(norm_task)
    except Exception as e:
        return default_failure_result(norm_task.get("task_id", "unknown_task"), f"evaluation_error:{e}")

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
        "task_id": norm_task.get("task_id"),
        "marker_scores": marker_scores,
        "marker_issues": marker_issues,
        "hard_policy_violations": hard_policy_violations,
        "aggregate_score_pct": aggregate_score,
        "pass": overall_pass,
    }


def evaluate_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """Backward-compatible wrapper for existing call sites."""
    return evaluate(task=task, agent_output=task.get("candidate_output", {}))


def load_tasks(tasks_path: Path) -> List[Dict[str, Any]]:
    try:
        text = tasks_path.read_text(encoding="utf-8")
    except Exception as e:
        raise ValueError(f"Failed to read tasks file: {e}") from e

    # First try JSON parsing.
    try:
        raw = json.loads(text)
        if isinstance(raw, list):
            return [x for x in raw if isinstance(x, dict)]
        if isinstance(raw, dict):
            if "examples" in raw and isinstance(raw["examples"], list):
                return [x for x in raw["examples"] if isinstance(x, dict)]
            return [raw]
    except json.JSONDecodeError:
        pass

    # Fallback: JSONL parsing for robustness.
    rows: List[Dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
            if isinstance(row, dict):
                rows.append(row)
        except json.JSONDecodeError:
            continue
    if rows:
        return rows
    raise ValueError("Unsupported or malformed tasks file structure.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Tenacious-Bench tasks.")
    parser.add_argument("--tasks", type=Path, default=Path("schema.json"))
    parser.add_argument("--out", type=Path, default=Path("stage1_eval_results.json"))
    args = parser.parse_args()

    tasks = load_tasks(args.tasks)
    results: List[Dict[str, Any]] = []
    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            results.append(default_failure_result(f"row_{i}", "task_not_dict"))
            continue
        try:
            candidate = task.get("candidate_output", {})
            results.append(evaluate(task=task, agent_output=candidate))
        except Exception as e:
            task_id = safe_text(task.get("task_id", f"row_{i}"))
            results.append(default_failure_result(task_id, f"uncaught_eval_error:{e}"))
    payload = {
        "tasks_evaluated": len(results),
        "results": results,
    }

    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
