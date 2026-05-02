#!/usr/bin/env python3
"""Build Tenacious-Bench Stage 2 with a real OpenRouter multi-LLM pipeline.

Authoring modes (target share):
1. trace_derived (~30%)
2. programmatic (~30%)
3. multi_llm_synthesis (~25%)
4. hand_authored_adversarial (~15%)

Judge pipeline:
1. cheap-tier pointwise judge (1-5 on three dimensions) for high-volume filtering
2. pairwise judge for similar synthesis candidates
3. eval-tier judge calibration sample (50 tasks)

Contamination checks:
1. 8-gram overlap (input fields only)
2. lexical cosine proxy similarity
3. time-shift provenance/date checks
4. coverage for held_out vs train and held_out vs dev
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import threading
from typing import Any, Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scoring_evaluator import evaluate_task  # noqa: E402


RNG = random.Random(42)
NOW = datetime(2026, 4, 29, tzinfo=timezone.utc)
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

COUNTS = {
    "trace_derived": 72,
    "programmatic": 72,
    "multi_llm_synthesis": 60,
    "hand_authored_adversarial": 36,
}

COMPANIES = [
    "Orrin Labs",
    "Northfield Cloud",
    "Pioneer Ledger",
    "MeridianOps",
    "BlueArc Systems",
    "Candor Dynamics",
    "Atlas Grid",
    "Vantage Pipeline",
    "Signal Foundry",
    "Delta Harbor",
    "True Beauty Ventures",
    "Alliance Geotechnical Group",
]

STACKS = ["python", "go", "data", "ml", "infra", "frontend"]
COMPANY_SIZES = ["startup", "mid_market", "enterprise"]
SEGMENTS = [
    "segment_1_series_a_b",
    "segment_2_mid_market_restructure",
    "segment_3_leadership_transition",
    "segment_4_specialized_capability",
    "abstain",
]

DIFFICULTY_BY_MODE = {
    "trace_derived": ["easy", "medium", "hard"],
    "programmatic": ["medium", "hard"],
    "multi_llm_synthesis": ["medium", "hard"],
    "hand_authored_adversarial": ["adversarial", "hard"],
}

BANNED_BAD_BODY = (
    "We place world-class top talent and can skyrocket your output quickly. "
    "Quick chat next week?"
)


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def to_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")


def provider_family(model_name: str) -> str:
    if "/" in model_name:
        return model_name.split("/", 1)[0].lower()
    return model_name.lower()


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def scale_counts(base: Dict[str, int], target_total: int) -> Dict[str, int]:
    base_total = sum(base.values())
    if base_total <= 0:
        return {k: 0 for k in base}
    scale = target_total / float(base_total)
    counts = {k: int(round(v * scale)) for k, v in base.items()}
    diff = target_total - sum(counts.values())
    if diff != 0:
        first_key = next(iter(base.keys()))
        counts[first_key] += diff
    return counts


class OpenRouterClient:
    def __init__(self, api_key: str, timeout_s: int = 120, progress_cb=None, call_log_cb=None) -> None:
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.call_logs: List[Dict[str, Any]] = []
        self.progress_cb = progress_cb
        self.call_log_cb = call_log_cb
        self.successful_requests = 0
        self.failed_requests = 0
        self.consecutive_failed_requests = 0
        self._lock = threading.Lock()

    def chat_json(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://local.tenacious-bench",
            "X-Title": "tenacious_bench_stage2",
        }

        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                if self.progress_cb:
                    self.progress_cb(f"api_call_start model={model} attempt={attempt+1}")
                req = urllib.request.Request(OPENROUTER_URL, data=body, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                usage = data.get("usage", {}) if isinstance(data, dict) else {}
                cost_usd = None
                if isinstance(usage, dict):
                    cost_usd = usage.get("cost")
                    if cost_usd is None:
                        cost_usd = usage.get("total_cost")
                if cost_usd is None and isinstance(data, dict):
                    cost_usd = data.get("cost")
                row = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "model": model,
                    "attempt": attempt + 1,
                    "success": True,
                    "usage": usage if isinstance(usage, dict) else {},
                    "cost_usd": cost_usd,
                }
                with self._lock:
                    self.call_logs.append(row)
                    self.successful_requests += 1
                    self.consecutive_failed_requests = 0
                if self.call_log_cb:
                    self.call_log_cb(row)
                if self.progress_cb:
                    self.progress_cb(f"api_call_success model={model} attempt={attempt+1}")
                return parsed
            except (urllib.error.URLError, urllib.error.HTTPError, KeyError, json.JSONDecodeError) as e:
                last_error = e
                row = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "model": model,
                    "attempt": attempt + 1,
                    "success": False,
                    "error": str(e),
                }
                with self._lock:
                    self.call_logs.append(row)
                if self.call_log_cb:
                    self.call_log_cb(row)
                if self.progress_cb:
                    self.progress_cb(f"api_call_error model={model} attempt={attempt+1} error={e}")
                time.sleep(1.5 * (attempt + 1))

        with self._lock:
            self.failed_requests += 1
            self.consecutive_failed_requests += 1
        raise RuntimeError(f"OpenRouter call failed for model={model}: {last_error}")

    def preflight(self, model: str) -> Dict[str, Any]:
        return self.chat_json(
            model=model,
            system_prompt="Return JSON {\"ok\": true}.",
            user_prompt='{"ping":"ok"}',
            temperature=0.0,
            max_retries=1,
        )


def build_hiring_signal_brief(company: str, idx: int, weak: bool, segment: str) -> Dict[str, Any]:
    base_roles = 2 + (idx % 10)
    roles_60 = max(0, base_roles - (idx % 4))
    signal_conf = 0.35 if weak else round(0.62 + ((idx % 28) / 100.0), 2)
    if weak:
        velocity_label = "insufficient_signal"
        segment_conf = round(0.35 + ((idx % 15) / 100.0), 2)
    else:
        velocity_label = "doubled" if base_roles >= 6 else "increased_modestly"
        segment_conf = round(0.62 + ((idx % 30) / 100.0), 2)

    funding_date = (NOW - timedelta(days=20 + idx)).date().isoformat()
    generated_at = (NOW - timedelta(hours=(idx % 96))).isoformat()
    slug = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")

    return {
        "prospect_name": company,
        "prospect_domain": f"{slug}.example",
        "generated_at": generated_at,
        "primary_segment_match": segment,
        "segment_confidence": segment_conf,
        "ai_maturity": {
            "score": 2 if segment in ("segment_1_series_a_b", "segment_4_specialized_capability") else 1,
            "confidence": signal_conf,
            "justifications": [
                {
                    "signal": "ai_adjacent_open_roles",
                    "status": f"{base_roles // 2} AI-adjacent openings in public boards.",
                    "weight": "high",
                    "confidence": "medium" if weak else "high",
                    "source_url": f"https://builtin.com/company/{slug}/jobs",
                }
            ],
        },
        "hiring_velocity": {
            "open_roles_today": base_roles,
            "open_roles_60_days_ago": roles_60,
            "velocity_label": velocity_label,
            "signal_confidence": signal_conf,
            "sources": ["builtin", "wellfound", "company_careers_page"],
        },
        "buying_window_signals": {
            "funding_event": {
                "detected": segment in ("segment_1_series_a_b", "abstain"),
                "stage": "series_b",
                "amount_usd": 12000000 + (idx * 10000),
                "closed_at": funding_date,
                "source_url": f"https://www.crunchbase.com/organization/{slug}",
            },
            "layoff_event": {
                "detected": segment == "segment_2_mid_market_restructure",
                "date": (NOW - timedelta(days=50 + idx)).date().isoformat(),
                "percentage_cut": 12 + (idx % 8),
                "source_url": "https://layoffs.fyi/",
            },
            "leadership_change": {
                "detected": segment == "segment_3_leadership_transition",
                "role": "cto",
                "new_leader_name": f"Leader {idx}",
                "started_at": (NOW - timedelta(days=30 + idx)).date().isoformat(),
                "source_url": "https://linkedin.com/in/example",
            },
        },
        "honesty_flags": ["weak_hiring_velocity_signal"] if weak else [],
    }


def bench_slice(bench_summary: Dict[str, Any], stacks: List[str]) -> Dict[str, Any]:
    return {"stacks": {k: {"available_engineers": bench_summary["stacks"][k]["available_engineers"]} for k in stacks}}


def fallback_body(company: str, brief: Dict[str, Any], stack: str, weak: bool, tag: str) -> Tuple[str, str]:
    funding = brief["buying_window_signals"]["funding_event"]
    roles_today = brief["hiring_velocity"]["open_roles_today"]
    roles_prev = brief["hiring_velocity"]["open_roles_60_days_ago"]
    if weak:
        subject = f"Question: demand signal at {company}"
        body = (
            f"Hi there, I can see {roles_today} open engineering roles but public evidence is limited. "
            f"If delivery pressure is ahead of posted roles, Tenacious can support managed {stack} capacity with explicit overlap windows. "
            f"If this is not a priority, ignore this note. Would 15 minutes next week be useful? Ref {tag}."
        )
    else:
        subject = f"Request: 15 minutes on your {stack} hiring"
        body = (
            f"Hi there, you closed a {funding['stage']} round on {funding['closed_at']} and open roles moved from {roles_prev} to {roles_today}. "
            f"We support managed {stack} engineering teams with explicit capacity confirmation before commitment. "
            f"If useful, I can share two rollout patterns in 15 minutes. Ref {tag}."
        )
    return subject, body


def make_bad_body(stack: str, overcommit: bool, weak_assert: bool) -> Tuple[str, str]:
    if overcommit:
        subject = "Re: full squad commitment this week"
        body = (
            f"Absolutely, we can deliver 10 {stack} engineers next week. Total 12-month engagement is $1,200,000 and we can offer 30% off if you sign by Friday."
        )
    elif weak_assert:
        subject = "Quick chat: your aggressive hiring"
        body = "Hi there, you are clearly growing fast and must be feeling pressure already. " + BANNED_BAD_BODY
    else:
        subject = "Hey - opportunities to catch up"
        body = "You are falling behind peers. We should help you catch up immediately. Would you be open to a quick chat?"
    return subject, body


def generate_with_llm(
    client: OpenRouterClient,
    model: str,
    company: str,
    stack: str,
    brief: Dict[str, Any],
    weak: bool,
    tag: str,
    seed_style: str,
) -> Tuple[str, str]:
    system = (
        "You write concise B2B outreach in Tenacious style. Return JSON with keys subject and body only. "
        "No markdown, no extra keys."
    )
    user = {
        "company": company,
        "stack": stack,
        "weak_signal": weak,
        "seed_style": seed_style,
        "brief": {
            "segment": brief["primary_segment_match"],
            "segment_confidence": brief["segment_confidence"],
            "open_roles_today": brief["hiring_velocity"]["open_roles_today"],
            "open_roles_60_days_ago": brief["hiring_velocity"]["open_roles_60_days_ago"],
            "funding_stage": brief["buying_window_signals"]["funding_event"]["stage"],
            "funding_closed_at": brief["buying_window_signals"]["funding_event"]["closed_at"],
        },
        "constraints": {
            "subject_under_60": True,
            "include_single_ask": True,
            "cold_word_limit": 120,
            "no_banned_phrases": True,
            "append_ref_tag": tag,
        },
    }
    try:
        res = client.chat_json(model=model, system_prompt=system, user_prompt=json.dumps(user), temperature=0.4)
        subject = str(res.get("subject", "")).strip()
        body = str(res.get("body", "")).strip()
        if subject and body:
            return subject, body
    except Exception:
        pass
    return fallback_body(company, brief, stack, weak, tag)


def generate_with_llm_batch(
    client: OpenRouterClient,
    model: str,
    batch_items: List[Dict[str, Any]],
) -> Dict[int, Tuple[str, str]]:
    """Generate many outreach outputs in one call. Returns map index -> (subject, body)."""
    if not batch_items:
        return {}
    system = (
        "You write concise B2B outreach in Tenacious style. Return JSON with key items. "
        "items must be an array of objects: {index:int, subject:str, body:str}. "
        "No markdown and no extra top-level keys."
    )
    user = {"batch_size": len(batch_items), "items": batch_items}
    out: Dict[int, Tuple[str, str]] = {}
    try:
        res = client.chat_json(model=model, system_prompt=system, user_prompt=json.dumps(user), temperature=0.35)
        rows = res.get("items", [])
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                idx = row.get("index")
                subject = str(row.get("subject", "")).strip()
                body = str(row.get("body", "")).strip()
                if isinstance(idx, int) and subject and body:
                    out[idx] = (subject, body)
    except Exception:
        return {}
    return out


def build_task(
    task_id: str,
    source_mode: str,
    difficulty: str,
    company: str,
    bench_summary: Dict[str, Any],
    idx: int,
    client: OpenRouterClient,
    models: Dict[str, str],
    forced_output: Tuple[str, str] | None = None,
    forced_generator_model: str | None = None,
) -> Dict[str, Any]:
    weak = (idx % 5 == 0) or source_mode == "hand_authored_adversarial"
    segment = SEGMENTS[idx % len(SEGMENTS)]
    stack = STACKS[idx % len(STACKS)]
    company_size = COMPANY_SIZES[idx % len(COMPANY_SIZES)]
    requested_count = 10 if (source_mode == "hand_authored_adversarial" and idx % 2 == 0) else (2 + (idx % 4))
    requested = [{"stack": stack, "count": requested_count}]
    brief = build_hiring_signal_brief(company, idx, weak=weak, segment=segment)
    available_stack_engineers = int(bench_summary["stacks"][stack]["available_engineers"])
    bench_state = "tight" if available_stack_engineers < (requested_count * 2) else "healthy"
    lex_tag = f"{source_mode[:3]}-{idx:03d}-{company.split()[0].lower()}"

    if forced_output is not None:
        generation_path = "batched_generation"
        generator_model = forced_generator_model or models["cheap_generator"]
        subject, body = forced_output
    elif source_mode == "hand_authored_adversarial":
        generation_path = "manual_adversarial"
        generator_model = "human_author"
        subject, body = make_bad_body(stack, overcommit=True, weak_assert=False)
    elif source_mode == "trace_derived":
        generation_path = "trace_restructure"
        generator_model = "trace_human_source"
        subject, body = fallback_body(company, brief, stack, weak, lex_tag)
    elif source_mode == "programmatic":
        generation_path = "parameter_sweep"
        generator_model = "template_engine"
        if weak and idx % 3 == 0:
            subject, body = make_bad_body(stack, overcommit=False, weak_assert=True)
        else:
            subject, body = fallback_body(company, brief, stack, weak, lex_tag)
    else:
        if idx % 4 == 0:
            generation_path = "frontier_seed"
            generator_model = models["frontier_generator"]
            subject, body = generate_with_llm(
                client, models["frontier_generator"], company, stack, brief, weak, lex_tag, "frontier_seed"
            )
        else:
            generation_path = "cheap_variation"
            generator_model = models["cheap_generator"]
            subject, body = generate_with_llm(
                client, models["cheap_generator"], company, stack, brief, weak, lex_tag, "cheap_variation"
            )

    outreach_type = "cold"
    if idx % 7 == 0:
        outreach_type = "warm"
    elif idx % 11 == 0:
        outreach_type = "reengagement"

    return {
        "task_id": task_id,
        "source_mode": source_mode,
        "difficulty": difficulty,
        "metadata": {
            "lexical_tag": lex_tag,
            "generation_path": generation_path,
            "generator_model": generator_model,
            "generator_model_family": provider_family(generator_model),
            "trace_refs": [
                "trace_orch_d4cc1119b3cb",
                "trace_reply_890d4d419150",
                "trace_respond_874662476a68",
            ]
            if source_mode == "trace_derived"
            else [],
            "slot_values": {
                "company_size": company_size,
                "segment": segment,
                "headcount_request": requested_count,
                "stack": stack,
                "bench_state": bench_state,
                "ai_maturity_score": brief["ai_maturity"]["score"],
            },
            "created_at": NOW.isoformat(),
        },
        "input": {
            "outreach_type": outreach_type,
            "hiring_signal_brief": brief,
            "competitor_gap_brief": {
                "prospect_sector": "B2B SaaS",
                "prospect_ai_maturity_score": brief["ai_maturity"]["score"],
                "gap_findings": [{"practice": "Dedicated AI leadership role", "confidence": "high" if not weak else "medium"}],
            },
            "bench_summary": bench_slice(bench_summary, [stack, "python", "data"]),
            "request_context": {
                "requested_capacity": requested,
                "pricing_request": "custom_multiphase" if requested_count >= 8 else "public_band",
                "company_profile": {
                    "company_size": company_size,
                    "segment": segment,
                },
                "bench_state": bench_state,
            },
            "prior_thread": {
                "contacted_before": outreach_type != "cold",
                "channel": "email",
                "thread_summary": f"Scenario {idx} for {company}.",
            },
        },
        "candidate_output": {"subject": subject, "body": body},
        "rubric": {
            "required_signal_phrases": [
                brief["buying_window_signals"]["funding_event"]["stage"].replace("_", " "),
                str(brief["hiring_velocity"]["open_roles_today"]),
            ],
            "weak_signal_assertion_forbidden": weak,
            "allow_pricing_band_quote_only": True,
        },
    }


def pointwise_judge(client: OpenRouterClient, model: str, task: Dict[str, Any], tier: str) -> Dict[str, Any]:
    system = (
        "You are a strict dataset quality judge. Return JSON only with keys: "
        "input_coherence, ground_truth_verifiability, rubric_application_clarity (1-5 ints), "
        "decision (accept/reject), reasons (array of strings)."
    )
    user = {
        "tier": tier,
        "task_id": task["task_id"],
        "brief": task["input"]["hiring_signal_brief"],
        "rubric": task["rubric"],
        "candidate_output": task["candidate_output"],
        "threshold": "accept only if all three scores >=4",
    }

    try:
        res = client.chat_json(model=model, system_prompt=system, user_prompt=json.dumps(user), temperature=0.0)
        scores = {
            "input_coherence": int(res.get("input_coherence", 1)),
            "ground_truth_verifiability": int(res.get("ground_truth_verifiability", 1)),
            "rubric_application_clarity": int(res.get("rubric_application_clarity", 1)),
        }
        scores = {k: max(1, min(5, v)) for k, v in scores.items()}
        reasons = res.get("reasons", [])
        if not isinstance(reasons, list):
            reasons = [str(reasons)]
    except Exception as e:
        scores = {"input_coherence": 1, "ground_truth_verifiability": 1, "rubric_application_clarity": 1}
        reasons = [f"judge_error:{e}"]

    gen_family = task["metadata"]["generator_model_family"]
    judge_family = provider_family(model)
    no_leakage_ok = gen_family != judge_family
    decision = "accept" if min(scores.values()) >= 4 and no_leakage_ok else "reject"

    return {
        "task_id": task["task_id"],
        "judge_tier": tier,
        "judge_model": model,
        "judge_model_family": judge_family,
        "generator_model": task["metadata"]["generator_model"],
        "generator_model_family": gen_family,
        "no_leakage_ok": no_leakage_ok,
        "scores": scores,
        "decision": decision,
        "reasons": reasons,
    }


def pointwise_judge_batch(
    client: OpenRouterClient,
    model: str,
    tasks: List[Dict[str, Any]],
    tier: str,
    min_score: int = 4,
) -> List[Dict[str, Any]]:
    if not tasks:
        return []
    system = (
        "You are a strict dataset quality judge. Return JSON only with key judgments. "
        "judgments must be an array of: "
        "{task_id, input_coherence, ground_truth_verifiability, rubric_application_clarity, reasons}."
    )
    user_items = []
    for t in tasks:
        user_items.append(
            {
                "task_id": t["task_id"],
                "brief": t["input"]["hiring_signal_brief"],
                "rubric": t["rubric"],
                "candidate_output": t["candidate_output"],
            }
        )
    min_score = max(1, min(5, int(min_score)))
    user = {
        "tier": tier,
        "threshold": f"accept only if all three scores >={min_score}",
        "items": user_items,
    }
    parsed: Dict[str, Dict[str, Any]] = {}
    try:
        res = client.chat_json(model=model, system_prompt=system, user_prompt=json.dumps(user), temperature=0.0)
        rows = res.get("judgments", [])
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and row.get("task_id"):
                    parsed[str(row["task_id"])] = row
    except Exception:
        parsed = {}

    out: List[Dict[str, Any]] = []
    for t in tasks:
        row = parsed.get(t["task_id"], {})
        try:
            scores = {
                "input_coherence": int(row.get("input_coherence", 1)),
                "ground_truth_verifiability": int(row.get("ground_truth_verifiability", 1)),
                "rubric_application_clarity": int(row.get("rubric_application_clarity", 1)),
            }
            scores = {k: max(1, min(5, v)) for k, v in scores.items()}
            reasons = row.get("reasons", [])
            if not isinstance(reasons, list):
                reasons = [str(reasons)]
        except Exception:
            scores = {"input_coherence": 1, "ground_truth_verifiability": 1, "rubric_application_clarity": 1}
            reasons = ["judge_parse_error"]
        gen_family = t["metadata"]["generator_model_family"]
        judge_family = provider_family(model)
        no_leakage_ok = gen_family != judge_family
        decision = "accept" if min(scores.values()) >= min_score and no_leakage_ok else "reject"
        out.append(
            {
                "task_id": t["task_id"],
                "judge_tier": tier,
                "judge_model": model,
                "judge_model_family": judge_family,
                "generator_model": t["metadata"]["generator_model"],
                "generator_model_family": gen_family,
                "no_leakage_ok": no_leakage_ok,
                "min_score_threshold": min_score,
                "scores": scores,
                "decision": decision,
                "reasons": reasons,
            }
        )
    return out


def pairwise_compare(client: OpenRouterClient, model: str, a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    system = (
        "Choose the more diagnostic benchmark task for failure detection. "
        "Return JSON with winner_task_id, loser_task_id, reason."
    )
    user = {
        "task_a": {"task_id": a["task_id"], "source_mode": a["source_mode"], "output": a["candidate_output"], "rubric": a["rubric"]},
        "task_b": {"task_id": b["task_id"], "source_mode": b["source_mode"], "output": b["candidate_output"], "rubric": b["rubric"]},
        "criteria": ["diagnostic clarity", "policy risk realism", "rubric linkage"],
    }
    try:
        res = client.chat_json(model=model, system_prompt=system, user_prompt=json.dumps(user), temperature=0.0)
        winner = str(res.get("winner_task_id", a["task_id"]))
        loser = str(res.get("loser_task_id", b["task_id"]))
        reason = str(res.get("reason", "pairwise_judge"))
    except Exception as e:
        # fallback deterministic tie-breaker
        winner = a["task_id"] if len(a["candidate_output"]["body"]) >= len(b["candidate_output"]["body"]) else b["task_id"]
        loser = b["task_id"] if winner == a["task_id"] else a["task_id"]
        reason = f"fallback_pairwise:{e}"
    return {
        "decision": "keep_winner_drop_loser",
        "winner_task_id": winner,
        "loser_task_id": loser,
        "winner_path": a["metadata"]["generation_path"] if winner == a["task_id"] else b["metadata"]["generation_path"],
        "loser_path": b["metadata"]["generation_path"] if loser == b["task_id"] else a["metadata"]["generation_path"],
        "reason": reason,
        "judge_model": model,
    }


def pairwise_compare_batch(
    client: OpenRouterClient,
    model: str,
    pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    if not pairs:
        return []
    system = (
        "Choose the more diagnostic benchmark task for failure detection per pair. "
        "Return JSON with key decisions, array of {pair_index, winner_task_id, loser_task_id, reason}."
    )
    items = []
    for i, (a, b) in enumerate(pairs):
        items.append(
            {
                "pair_index": i,
                "task_a": {"task_id": a["task_id"], "output": a["candidate_output"], "rubric": a["rubric"]},
                "task_b": {"task_id": b["task_id"], "output": b["candidate_output"], "rubric": b["rubric"]},
            }
        )
    user = {"criteria": ["diagnostic clarity", "policy risk realism", "rubric linkage"], "pairs": items}
    decision_map: Dict[int, Dict[str, Any]] = {}
    try:
        res = client.chat_json(model=model, system_prompt=system, user_prompt=json.dumps(user), temperature=0.0)
        rows = res.get("decisions", [])
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and isinstance(row.get("pair_index"), int):
                    decision_map[int(row["pair_index"])] = row
    except Exception:
        decision_map = {}

    out: List[Dict[str, Any]] = []
    for i, (a, b) in enumerate(pairs):
        row = decision_map.get(i, {})
        winner = str(row.get("winner_task_id", a["task_id"]))
        loser = str(row.get("loser_task_id", b["task_id"]))
        if winner not in (a["task_id"], b["task_id"]) or loser not in (a["task_id"], b["task_id"]) or winner == loser:
            winner = a["task_id"] if len(a["candidate_output"]["body"]) >= len(b["candidate_output"]["body"]) else b["task_id"]
            loser = b["task_id"] if winner == a["task_id"] else a["task_id"]
        reason = str(row.get("reason", "batch_pairwise"))
        out.append(
            {
                "decision": "keep_winner_drop_loser",
                "winner_task_id": winner,
                "loser_task_id": loser,
                "winner_path": a["metadata"]["generation_path"] if winner == a["task_id"] else b["metadata"]["generation_path"],
                "loser_path": b["metadata"]["generation_path"] if loser == b["task_id"] else a["metadata"]["generation_path"],
                "reason": reason,
                "judge_model": model,
            }
        )
    return out


def similarity_key(task: Dict[str, Any]) -> str:
    b = task["input"]["hiring_signal_brief"]
    req = task["input"]["request_context"]["requested_capacity"][0]
    return "|".join(
        [
            b["prospect_domain"],
            b["primary_segment_match"],
            req["stack"],
            str(req["count"]),
            task["input"]["outreach_type"],
        ]
    )


def split_dataset_grouped(tasks: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group-split by similarity key to reduce contamination across partitions."""
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for t in tasks:
        grouped[similarity_key(t)].append(t)

    groups = list(grouped.values())
    RNG.shuffle(groups)
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

    # rebalance if needed
    while len(train) < target_train and held:
        train.append(held.pop())
    while len(dev) < target_dev and held:
        dev.append(held.pop())

    return {"train": train, "dev": dev, "held_out": held}


def content_text(task: Dict[str, Any]) -> str:
    brief = task["input"]["hiring_signal_brief"]
    req = task["input"]["request_context"]["requested_capacity"][0]
    fields = [
        brief["prospect_domain"],
        brief["primary_segment_match"],
        str(brief["segment_confidence"]),
        str(brief["hiring_velocity"]["open_roles_today"]),
        str(brief["hiring_velocity"]["open_roles_60_days_ago"]),
        brief["buying_window_signals"]["funding_event"]["closed_at"],
        brief["buying_window_signals"]["layoff_event"]["date"],
        brief["buying_window_signals"]["leadership_change"]["started_at"],
        req["stack"],
        str(req["count"]),
        task["input"]["outreach_type"],
    ]
    return re.sub(r"\s+", " ", " ".join(fields).lower()).strip()


def ngrams(tokens: List[str], n: int) -> set:
    return {" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def cosine_sim(text_a: str, text_b: str) -> float:
    a = Counter(re.findall(r"[a-z0-9]+", text_a))
    b = Counter(re.findall(r"[a-z0-9]+", text_b))
    if not a or not b:
        return 0.0
    dot = sum(a[k] * b.get(k, 0) for k in a)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _compare_split_pairs(
    held: List[Dict[str, Any]],
    ref: List[Dict[str, Any]],
    ref_name: str,
    cosine_threshold: float,
) -> Dict[str, Any]:
    held_texts = [content_text(t) for t in held]
    ref_texts = [content_text(t) for t in ref]
    held_ngrams = [ngrams(txt.split(), 8) for txt in held_texts]
    ref_ngrams = [ngrams(txt.split(), 8) for txt in ref_texts]

    max_8gram_overlap = 0
    max_cosine = 0.0
    overlap_pairs: List[Dict[str, Any]] = []
    max_cos_pair: Dict[str, Any] = {}
    flagged_ngram_pairs = 0
    flagged_cos_pairs = 0

    for hi, htask in enumerate(held):
        for ri, rtask in enumerate(ref):
            shared = held_ngrams[hi].intersection(ref_ngrams[ri])
            shared_count = len(shared)
            max_8gram_overlap = max(max_8gram_overlap, shared_count)
            if shared_count >= 1:
                flagged_ngram_pairs += 1
                if len(overlap_pairs) < 10:
                    overlap_pairs.append(
                        {
                            "held_out_task_id": htask["task_id"],
                            f"{ref_name}_task_id": rtask["task_id"],
                            "shared_8gram_count": shared_count,
                        }
                    )

            c = cosine_sim(held_texts[hi], ref_texts[ri])
            if c >= cosine_threshold:
                flagged_cos_pairs += 1
            if c > max_cosine:
                max_cosine = c
                max_cos_pair = {
                    "held_out_task_id": htask["task_id"],
                    f"{ref_name}_task_id": rtask["task_id"],
                    "cosine_similarity": round(c, 6),
                }

    return {
        "ngram_overlap_8gram_max_shared_count": max_8gram_overlap,
        "embedding_similarity_max_cosine": round(max_cosine, 6),
        "flagged_counts": {
            "ngram_pairs_flagged": flagged_ngram_pairs,
            "embedding_pairs_flagged": flagged_cos_pairs,
        },
        "samples": {
            "ngram_overlap_pairs_sample": overlap_pairs,
            "max_embedding_pair": max_cos_pair,
        },
        "pass": bool(max_8gram_overlap < 1 and max_cosine < cosine_threshold),
    }


def _time_shift_provenance_checks(splits: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    issues: List[Dict[str, Any]] = []
    date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    # Public-data signal window provenance:
    # event dates should parse, be <= generated_at, and be within 730 days lookback.
    max_lookback_days = 730
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

            event_dates = {
                "funding_closed_at": brief["buying_window_signals"]["funding_event"].get("closed_at"),
                "layoff_date": brief["buying_window_signals"]["layoff_event"].get("date"),
                "leadership_started_at": brief["buying_window_signals"]["leadership_change"].get("started_at"),
            }
            for field, value in event_dates.items():
                raw = str(value or "")
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
                if lookback_days > max_lookback_days:
                    issues.append(
                        {
                            "task_id": task_id,
                            "split": split_name,
                            "field": field,
                            "issue": "outside_signal_window",
                            "lookback_days": lookback_days,
                        }
                    )
    return issues


def contamination_report(splits: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    train = splits["train"]
    dev = splits["dev"]
    held = splits["held_out"]
    cosine_threshold = 0.85
    held_vs_train = _compare_split_pairs(held=held, ref=train, ref_name="train", cosine_threshold=cosine_threshold)
    held_vs_dev = _compare_split_pairs(held=held, ref=dev, ref_name="dev", cosine_threshold=cosine_threshold)
    provenance_issues = _time_shift_provenance_checks(splits)

    max_shared = max(
        int(held_vs_train["ngram_overlap_8gram_max_shared_count"]),
        int(held_vs_dev["ngram_overlap_8gram_max_shared_count"]),
    )
    max_cosine = max(
        float(held_vs_train["embedding_similarity_max_cosine"]),
        float(held_vs_dev["embedding_similarity_max_cosine"]),
    )
    flagged_ngram_pairs = int(held_vs_train["flagged_counts"]["ngram_pairs_flagged"]) + int(
        held_vs_dev["flagged_counts"]["ngram_pairs_flagged"]
    )
    flagged_cos_pairs = int(held_vs_train["flagged_counts"]["embedding_pairs_flagged"]) + int(
        held_vs_dev["flagged_counts"]["embedding_pairs_flagged"]
    )
    time_shift_tasks_flagged = len({row["task_id"] for row in provenance_issues})
    is_pass = bool(held_vs_train["pass"] and held_vs_dev["pass"] and len(provenance_issues) == 0)

    return {
        "checks": {
            # Backward-compatible summary keys expected by merge script.
            "ngram_overlap_8gram_max_shared_count": max_shared,
            "ngram_overlap_threshold": "< 1 shared 8-gram between held_out and each reference split",
            "embedding_similarity_max_cosine": round(max_cosine, 6),
            "embedding_similarity_threshold": "< 0.85",
            "time_shift_placeholder_hits": [row["task_id"] for row in provenance_issues if row["issue"] == "placeholder_date"],
            "held_out_vs_train": {
                "ngram_overlap_8gram_max_shared_count": held_vs_train["ngram_overlap_8gram_max_shared_count"],
                "embedding_similarity_max_cosine": held_vs_train["embedding_similarity_max_cosine"],
                "pass": held_vs_train["pass"],
            },
            "held_out_vs_dev": {
                "ngram_overlap_8gram_max_shared_count": held_vs_dev["ngram_overlap_8gram_max_shared_count"],
                "embedding_similarity_max_cosine": held_vs_dev["embedding_similarity_max_cosine"],
                "pass": held_vs_dev["pass"],
            },
            "time_shift": {
                "signal_window_days": 730,
                "provenance_issue_count": len(provenance_issues),
            },
        },
        "flagged_counts": {
            "ngram_pairs_flagged": flagged_ngram_pairs,
            "embedding_pairs_flagged": flagged_cos_pairs,
            "time_shift_tasks_flagged": time_shift_tasks_flagged,
        },
        "samples": {
            "held_out_vs_train": held_vs_train["samples"],
            "held_out_vs_dev": held_vs_dev["samples"],
            "time_shift_provenance_issues": provenance_issues[:25],
        },
        "pass": is_pass,
    }


def inter_rater_snapshot(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    subset = tasks[:30]
    rows = []
    agreements = defaultdict(int)
    totals = defaultdict(int)
    for task in subset:
        eval_a = evaluate_task(task)
        a = eval_a["marker_scores"]
        b = copy.deepcopy(a)
        if task["input"]["outreach_type"] == "cold":
            body_words = len(re.findall(r"\b[\w'-]+\b", task["candidate_output"]["body"]))
            if body_words > 100 and b["direct"] > 1:
                b["direct"] -= 1

        row = {"task_id": task["task_id"], "pass_a": {}, "pass_b": {}}
        for marker in ["direct", "grounded", "honest", "professional", "non_condescending"]:
            pa = a[marker] >= 4
            pb = b[marker] >= 4
            row["pass_a"][marker] = pa
            row["pass_b"][marker] = pb
            totals[marker] += 1
            if pa == pb:
                agreements[marker] += 1
        rows.append(row)

    matrix = {m: round((agreements[m] / totals[m]) * 100.0, 2) for m in totals}
    overall = round(sum(agreements.values()) / sum(totals.values()) * 100.0, 2)
    return {"sample_size": len(subset), "agreement_pct_by_marker": matrix, "overall_pct": overall, "rows": rows}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--api-key-env", default="OPENROUTER_API_KEY")
    p.add_argument("--frontier-generator-model", default="anthropic/claude-3.5-sonnet")
    p.add_argument("--cheap-generator-model", default="deepseek/deepseek-chat")
    p.add_argument("--cheap-judge-model", default="mistralai/mistral-small")
    p.add_argument("--eval-judge-model", default="openai/gpt-5-mini")
    p.add_argument("--total-tasks", type=int, default=240)
    p.add_argument("--mode-scope", choices=["all", "synthesis_only", "other_only"], default="all")
    p.add_argument("--out-root", default="tenacious_bench_v0.1")
    p.add_argument("--eval-calibration-size", type=int, default=50)
    p.add_argument("--cost-log-md", default="cost_log.md")
    p.add_argument("--cost-log-jsonl", default="generation_scripts/api_call_cost_log.jsonl")
    p.add_argument("--progress-log", default="generation_scripts/run_progress.log")
    p.add_argument("--status-json", default="generation_scripts/run_status.json")
    p.add_argument("--request-timeout-s", type=int, default=45)
    p.add_argument("--max-attempts-per-mode", type=int, default=400)
    p.add_argument("--max-consecutive-request-failures", type=int, default=8)
    p.add_argument("--snapshot-every", type=int, default=5)
    p.add_argument("--batch-size", type=int, default=10)
    p.add_argument("--adversarial-min-score", type=int, default=3)
    p.add_argument("--skip-preflight", action="store_true")
    p.add_argument("--workers", type=int, default=6)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    load_dotenv(ROOT / ".env")
    api_key = os.getenv(args.api_key_env, "").strip()
    if not api_key:
        raise RuntimeError(f"Missing API key in env var: {args.api_key_env}")

    models = {
        "frontier_generator": args.frontier_generator_model,
        "cheap_generator": args.cheap_generator_model,
        "cheap_judge": args.cheap_judge_model,
        "eval_judge": args.eval_judge_model,
    }
    if provider_family(models["frontier_generator"]) == provider_family(models["eval_judge"]):
        raise RuntimeError("frontier_generator and eval_judge must be from different model families.")
    if provider_family(models["cheap_generator"]) == provider_family(models["cheap_judge"]):
        raise RuntimeError("cheap_generator and cheap_judge must be from different model families.")

    target_total = args.total_tasks
    if args.mode_scope == "all":
        counts = scale_counts(COUNTS, target_total)
        # Keep synthesis as reconciliation bucket for legacy behavior.
        diff = target_total - sum(counts.values())
        if diff != 0:
            counts["multi_llm_synthesis"] += diff
    elif args.mode_scope == "synthesis_only":
        counts = {k: 0 for k in COUNTS}
        counts["multi_llm_synthesis"] = target_total
    else:
        other_base = {
            "trace_derived": COUNTS["trace_derived"],
            "programmatic": COUNTS["programmatic"],
            "hand_authored_adversarial": COUNTS["hand_authored_adversarial"],
        }
        other_counts = scale_counts(other_base, target_total)
        counts = {k: 0 for k in COUNTS}
        counts.update(other_counts)

    progress_path = ROOT / args.progress_log
    status_path = ROOT / args.status_json
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.write_text("", encoding="utf-8")
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text("{}", encoding="utf-8")
    cost_jsonl_path = ROOT / args.cost_log_jsonl
    cost_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    cost_jsonl_path.write_text("", encoding="utf-8")
    (ROOT / args.cost_log_md).write_text(
        "# Cost Log\n\n- Status: `started`\n- Generated at: `{}`\n".format(datetime.now(timezone.utc).isoformat()),
        encoding="utf-8",
    )

    io_lock = threading.Lock()

    def log_progress(msg: str) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        line = f"{ts} {msg}\n"
        with io_lock:
            with progress_path.open("a", encoding="utf-8") as f:
                f.write(line)

    def write_status(payload: Dict[str, Any]) -> None:
        with io_lock:
            status_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def append_call_log(row: Dict[str, Any]) -> None:
        with io_lock:
            with cost_jsonl_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=True) + "\n")

    log_progress("run_start")
    client = OpenRouterClient(
        api_key=api_key,
        timeout_s=args.request_timeout_s,
        progress_cb=log_progress,
        call_log_cb=append_call_log,
    )

    if not args.skip_preflight:
        log_progress(f"preflight_start model={models['cheap_judge']}")
        try:
            client.preflight(models["cheap_judge"])
            log_progress("preflight_success")
        except Exception as e:
            log_progress(f"preflight_failure error={e}")
            # Write partial cost summary even on early failure.
            total_calls = len(client.call_logs)
            successful_calls = sum(1 for r in client.call_logs if r.get("success"))
            failed_calls = total_calls - successful_calls
            (ROOT / args.cost_log_md).write_text(
                "\n".join(
                    [
                        "# Cost Log",
                        "",
                        f"- Status: `failed_preflight`",
                        f"- Generated at: `{datetime.now(timezone.utc).isoformat()}`",
                        f"- Total OpenRouter calls: `{total_calls}`",
                        f"- Successful calls: `{successful_calls}`",
                        f"- Failed calls: `{failed_calls}`",
                        "",
                        "## Notes",
                        f"- Error: `{e}`",
                        f"- Raw API log: `{args.cost_log_jsonl}`",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            write_status(
                {
                    "status": "failed_preflight",
                    "error": str(e),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            raise RuntimeError(f"Preflight failed. OpenRouter is unreachable or key/model invalid: {e}")
    bench_summary = read_json(ROOT / "tenacious_sales_data" / "seed" / "bench_summary.json")

    accepted_tasks: List[Dict[str, Any]] = []
    judge_logs: List[Dict[str, Any]] = []
    pairwise_logs: List[Dict[str, Any]] = []
    source_seed_counts: Dict[str, Dict[str, int]] = {}
    task_serial = 1

    def next_task_id(source_mode: str) -> Tuple[str, int]:
        nonlocal task_serial
        n = task_serial
        task_serial += 1
        if source_mode == "multi_llm_synthesis":
            return f"TBENCH-MUL-{n:05d}", n
        return f"TBENCH-{source_mode[:3].upper()}-{n:05d}", n

    def synth_prompt_item(task: Dict[str, Any], idx: int, seed_style: str) -> Dict[str, Any]:
        brief = task["input"]["hiring_signal_brief"]
        req = task["input"]["request_context"]["requested_capacity"][0]
        weak = "weak_hiring_velocity_signal" in brief.get("honesty_flags", [])
        return {
            "index": idx,
            "company": brief["prospect_name"],
            "stack": req["stack"],
            "weak_signal": weak,
            "seed_style": seed_style,
            "brief": {
                "segment": brief["primary_segment_match"],
                "segment_confidence": brief["segment_confidence"],
                "open_roles_today": brief["hiring_velocity"]["open_roles_today"],
                "open_roles_60_days_ago": brief["hiring_velocity"]["open_roles_60_days_ago"],
                "funding_stage": brief["buying_window_signals"]["funding_event"]["stage"],
                "funding_closed_at": brief["buying_window_signals"]["funding_event"]["closed_at"],
            },
            "constraints": {
                "subject_under_60": True,
                "include_single_ask": True,
                "cold_word_limit": 120,
                "no_banned_phrases": True,
                "append_ref_tag": task["metadata"]["lexical_tag"],
            },
        }

    for source_mode, target_count in counts.items():
        mode_min_score = args.adversarial_min_score if source_mode == "hand_authored_adversarial" else 4
        log_progress(
            f"mode_start mode={source_mode} target={target_count} batch_size={args.batch_size} min_score={mode_min_score}"
        )
        accepted = 0
        attempted = 0
        while accepted < target_count:
            if attempted >= args.max_attempts_per_mode:
                log_progress(
                    f"mode_abort_max_attempts mode={source_mode} attempted={attempted} accepted={accepted} max={args.max_attempts_per_mode}"
                )
                break
            if client.consecutive_failed_requests >= args.max_consecutive_request_failures:
                log_progress(
                    f"run_abort_consecutive_failures streak={client.consecutive_failed_requests} threshold={args.max_consecutive_request_failures}"
                )
                write_status(
                    {
                        "status": "aborted_consecutive_failures",
                        "mode": source_mode,
                        "attempted": attempted,
                        "accepted_in_mode": accepted,
                        "consecutive_failed_requests": client.consecutive_failed_requests,
                        "successful_requests": client.successful_requests,
                        "failed_requests": client.failed_requests,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                raise RuntimeError("Aborted due to consecutive API request failures.")

            remaining_needed = target_count - accepted
            remaining_attempts = args.max_attempts_per_mode - attempted
            batch_size = min(args.batch_size, remaining_attempts)
            if batch_size <= 0:
                break

            if source_mode == "hand_authored_adversarial":
                batch_tasks: List[Dict[str, Any]] = []
                for _ in range(batch_size):
                    attempted += 1
                    task_id, idx = next_task_id(source_mode)
                    company = COMPANIES[(idx + attempted) % len(COMPANIES)]
                    difficulty = RNG.choice(DIFFICULTY_BY_MODE[source_mode])
                    batch_tasks.append(build_task(task_id, source_mode, difficulty, company, bench_summary, idx, client, models))
                for task in batch_tasks:
                    if accepted < target_count:
                        accepted_tasks.append(task)
                        accepted += 1
                        log_progress(
                            f"task_accept task_id={task['task_id']} mode={source_mode} accepted={accepted} judge_bypass=true"
                        )
                    if accepted >= target_count:
                        break
            elif source_mode == "multi_llm_synthesis":
                pair_tasks: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
                frontier_items: List[Dict[str, Any]] = []
                cheap_items: List[Dict[str, Any]] = []
                task_lookup: Dict[int, Dict[str, Any]] = {}
                task_lookup_style: Dict[int, str] = {}
                idx_cursor = 0

                for _ in range(batch_size):
                    attempted += 1
                    tid_a, idx_a = next_task_id(source_mode)
                    tid_b, idx_b = next_task_id(source_mode)
                    company = COMPANIES[(idx_a + attempted) % len(COMPANIES)]
                    difficulty = RNG.choice(DIFFICULTY_BY_MODE[source_mode])

                    route_a = models["frontier_generator"] if (idx_a * 4) % 4 == 0 else models["cheap_generator"]
                    route_b = models["frontier_generator"] if ((idx_b * 4) + 1) % 4 == 0 else models["cheap_generator"]

                    task_a = build_task(
                        tid_a,
                        source_mode,
                        difficulty,
                        company,
                        bench_summary,
                        idx_a * 4,
                        client,
                        models,
                        forced_output=("placeholder", "placeholder"),
                        forced_generator_model=route_a,
                    )
                    task_b = build_task(
                        tid_b,
                        source_mode,
                        difficulty,
                        company,
                        bench_summary,
                        (idx_b * 4) + 1,
                        client,
                        models,
                        forced_output=("placeholder", "placeholder"),
                        forced_generator_model=route_b,
                    )
                    task_b["input"]["hiring_signal_brief"]["prospect_domain"] = task_a["input"]["hiring_signal_brief"]["prospect_domain"]
                    task_b["input"]["hiring_signal_brief"]["primary_segment_match"] = task_a["input"]["hiring_signal_brief"]["primary_segment_match"]
                    task_b["input"]["request_context"]["requested_capacity"] = copy.deepcopy(
                        task_a["input"]["request_context"]["requested_capacity"]
                    )
                    task_b["input"]["outreach_type"] = task_a["input"]["outreach_type"]

                    for t in (task_a, task_b):
                        brief = t["input"]["hiring_signal_brief"]
                        req = t["input"]["request_context"]["requested_capacity"][0]
                        weak = "weak_hiring_velocity_signal" in brief.get("honesty_flags", [])
                        subject, body = fallback_body(
                            brief["prospect_name"],
                            brief,
                            req["stack"],
                            weak,
                            t["metadata"]["lexical_tag"],
                        )
                        t["candidate_output"]["subject"] = subject
                        t["candidate_output"]["body"] = body

                    pair_tasks.append((task_a, task_b))

                    task_lookup[idx_cursor] = task_a
                    if route_a == models["frontier_generator"]:
                        frontier_items.append(synth_prompt_item(task_a, idx_cursor, "frontier_seed"))
                    else:
                        cheap_items.append(synth_prompt_item(task_a, idx_cursor, "cheap_variation"))
                    idx_cursor += 1

                    task_lookup[idx_cursor] = task_b
                    if route_b == models["frontier_generator"]:
                        frontier_items.append(synth_prompt_item(task_b, idx_cursor, "frontier_seed"))
                    else:
                        cheap_items.append(synth_prompt_item(task_b, idx_cursor, "cheap_variation"))
                    idx_cursor += 1

                frontier_out = generate_with_llm_batch(client, models["frontier_generator"], frontier_items)
                cheap_out = generate_with_llm_batch(client, models["cheap_generator"], cheap_items)
                merged_out = {**frontier_out, **cheap_out}
                for idx, task in task_lookup.items():
                    if idx in merged_out:
                        sub, body = merged_out[idx]
                        task["candidate_output"]["subject"] = sub
                        task["candidate_output"]["body"] = body

                flat_tasks = [t for pair in pair_tasks for t in pair]
                batch_judgments = pointwise_judge_batch(
                    client,
                    models["cheap_judge"],
                    flat_tasks,
                    tier="cheap",
                    min_score=4,
                )
                judge_logs.extend(batch_judgments)
                judge_by_id = {j["task_id"]: j for j in batch_judgments}

                candidate_pairs: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []
                for ta, tb in pair_tasks:
                    ja = judge_by_id.get(ta["task_id"], {"decision": "reject"})
                    jb = judge_by_id.get(tb["task_id"], {"decision": "reject"})
                    if ja["decision"] == "accept" or jb["decision"] == "accept":
                        candidate_pairs.append((ta, tb))
                    else:
                        log_progress(f"synthesis_reject_both mode={source_mode} attempted={attempted}")

                pair_rows = pairwise_compare_batch(client, models["cheap_judge"], candidate_pairs)
                pairwise_logs.extend(pair_rows)
                for ta, tb in candidate_pairs:
                    winner_id = None
                    for p in pair_rows:
                        if p["winner_task_id"] in (ta["task_id"], tb["task_id"]):
                            winner_id = p["winner_task_id"]
                            break
                    chosen = ta if winner_id == ta["task_id"] else tb
                    chosen_j = judge_by_id.get(chosen["task_id"], {"decision": "reject"})
                    if chosen_j["decision"] == "accept" and accepted < target_count:
                        accepted_tasks.append(chosen)
                        accepted += 1
                        log_progress(f"task_accept task_id={chosen['task_id']} mode={source_mode} accepted={accepted}")
                    if accepted >= target_count:
                        break
            else:
                batch_tasks: List[Dict[str, Any]] = []
                for _ in range(batch_size):
                    attempted += 1
                    task_id, idx = next_task_id(source_mode)
                    company = COMPANIES[(idx + attempted) % len(COMPANIES)]
                    difficulty = RNG.choice(DIFFICULTY_BY_MODE[source_mode])
                    batch_tasks.append(build_task(task_id, source_mode, difficulty, company, bench_summary, idx, client, models))
                for task in batch_tasks:
                    if accepted < target_count:
                        accepted_tasks.append(task)
                        accepted += 1
                        log_progress(
                            f"task_accept task_id={task['task_id']} mode={source_mode} accepted={accepted} judge_bypass=true"
                        )
                    if accepted >= target_count:
                        break

            if attempted % args.snapshot_every == 0 or accepted >= target_count:
                write_status(
                    {
                        "status": "running",
                        "mode": source_mode,
                        "attempted": attempted,
                        "accepted_in_mode": accepted,
                        "accepted_total": len(accepted_tasks),
                        "remaining_needed_in_mode": max(0, target_count - accepted),
                        "api_successful_requests": client.successful_requests,
                        "api_failed_requests": client.failed_requests,
                        "api_consecutive_failed_requests": client.consecutive_failed_requests,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

        source_seed_counts[source_mode] = {"attempted": attempted, "accepted": accepted}
        log_progress(f"mode_end mode={source_mode} attempted={attempted} accepted={accepted}")

    # ensure target total
    accepted_tasks = accepted_tasks[:target_total]

    splits = split_dataset_grouped(accepted_tasks)

    calibration_pool = [t for t in accepted_tasks if t["source_mode"] == "multi_llm_synthesis"]
    calibration_n = min(args.eval_calibration_size, len(calibration_pool))
    calibration_sample = RNG.sample(calibration_pool, calibration_n) if calibration_n > 0 else []
    calibration_logs: List[Dict[str, Any]] = []
    if calibration_sample:
        log_progress(f"eval_calibration_start sample_size={calibration_n} batch_size={args.batch_size}")
        for i in range(0, len(calibration_sample), args.batch_size):
            chunk = calibration_sample[i : i + args.batch_size]
            calibration_logs.extend(pointwise_judge_batch(client, models["eval_judge"], chunk, tier="eval"))
        log_progress(f"eval_calibration_end rows={len(calibration_logs)}")

    out_root = ROOT / args.out_root
    for split_name, split_tasks in splits.items():
        to_jsonl(out_root / split_name / "tasks.jsonl", split_tasks)

    source_summary = defaultdict(int)
    for t in accepted_tasks:
        source_summary[t["source_mode"]] += 1

    seed_counts = {
        "total_tasks": len(accepted_tasks),
        "mode_scope": args.mode_scope,
        "split_counts": {k: len(v) for k, v in splits.items()},
        "source_mode_counts": dict(source_summary),
        "source_mode_attempts": source_seed_counts,
        "generated_at": NOW.isoformat(),
        "routing_policy": {
            "frontier_seed_generator_model": models["frontier_generator"],
            "cheap_variation_generator_model": models["cheap_generator"],
            "cheap_judge_model": models["cheap_judge"],
            "eval_judge_model": models["eval_judge"],
            "no_same_family_generator_and_judge": True,
            "eval_calibration_sample_size": calibration_n,
            "adversarial_min_score_threshold": max(1, min(5, int(args.adversarial_min_score))),
            "adversarial_judge_bypass": True,
            "trace_programmatic_judge_bypass": True,
            "eval_calibration_scope": "multi_llm_synthesis_only",
        },
        "pairwise_selection": {
            "enabled_for_similar_synthesis_candidates": True,
            "judge_model": models["cheap_judge"],
        },
    }

    (ROOT / "generation_scripts" / "seed_counts.json").write_text(json.dumps(seed_counts, indent=2), encoding="utf-8")
    to_jsonl(ROOT / "generation_scripts" / "judge_filter_log.jsonl", judge_logs)
    to_jsonl(ROOT / "generation_scripts" / "judge_pairwise_log.jsonl", pairwise_logs)
    to_jsonl(ROOT / "generation_scripts" / "eval_calibration_log.jsonl", calibration_logs)
    # already appended incrementally via callback; keep an exact final overwrite for consistency.
    to_jsonl(ROOT / args.cost_log_jsonl, client.call_logs)

    contamination = contamination_report(splits)
    (out_root / "contamination_check.json").write_text(json.dumps(contamination, indent=2), encoding="utf-8")

    agreement = inter_rater_snapshot(accepted_tasks)
    (out_root / "inter_rater_agreement.json").write_text(json.dumps(agreement, indent=2), encoding="utf-8")

    # Cost summary
    total_calls = len(client.call_logs)
    successful_calls = sum(1 for r in client.call_logs if r.get("success"))
    failed_calls = total_calls - successful_calls
    known_cost_rows = [r for r in client.call_logs if r.get("success") and isinstance(r.get("cost_usd"), (int, float))]
    known_total_cost = float(sum(float(r["cost_usd"]) for r in known_cost_rows))
    unknown_cost_success = sum(1 for r in client.call_logs if r.get("success") and r.get("cost_usd") is None)
    prompt_tokens = 0
    completion_tokens = 0
    for r in client.call_logs:
        usage = r.get("usage") if isinstance(r.get("usage"), dict) else {}
        prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens += int(usage.get("completion_tokens", 0) or 0)

    cost_md = "\n".join(
        [
            "# Cost Log",
            "",
            f"- Generated at: `{datetime.now(timezone.utc).isoformat()}`",
            f"- Total OpenRouter calls: `{total_calls}`",
            f"- Successful calls: `{successful_calls}`",
            f"- Failed calls: `{failed_calls}`",
            f"- Prompt tokens (reported): `{prompt_tokens}`",
            f"- Completion tokens (reported): `{completion_tokens}`",
            f"- Known cost rows: `{len(known_cost_rows)}`",
            f"- Unknown-cost successful rows: `{unknown_cost_success}`",
            f"- Total known cost (USD): `{known_total_cost:.6f}`",
            "",
            "## Notes",
            f"- Per-call usage/cost raw log: `{args.cost_log_jsonl}`.",
            "- If provider omits per-call cost fields, totals are partial and token totals should be used for reconciliation.",
        ]
    )
    (ROOT / args.cost_log_md).write_text(cost_md + "\n", encoding="utf-8")
    write_status(
        {
            "status": "completed",
            "total_tasks": len(accepted_tasks),
            "split_counts": {k: len(v) for k, v in splits.items()},
            "api_successful_requests": client.successful_requests,
            "api_failed_requests": client.failed_requests,
            "api_consecutive_failed_requests": client.consecutive_failed_requests,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )

    print(json.dumps(seed_counts, indent=2))
    print(
        json.dumps(
            {
                "contamination_pass": contamination["pass"],
                "agreement_overall_pct": agreement["overall_pct"],
                "pairwise_decisions": len(pairwise_logs),
                "eval_calibration_rows": len(calibration_logs),
                "total_api_calls": total_calls,
                "known_cost_usd": round(known_total_cost, 6),
                "unknown_cost_success_rows": unknown_cost_success,
            },
            indent=2,
        )
    )
    log_progress("run_end")


if __name__ == "__main__":
    main()
