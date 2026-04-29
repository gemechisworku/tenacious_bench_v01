# Cheap-Tier Bulk Variation Prompt

You are creating controlled variations of an existing benchmark seed.

Variation rules:
1. Keep the core failure mode unchanged.
2. Vary structured slots only:
- company
- segment match/confidence
- stack and requested headcount
- AI maturity and confidence
- outreach type (cold/warm/reengagement)
3. Preserve evaluability: candidate output must still map to rubric checks.
4. Keep one unique lexical tag in each output for traceability.

Avoid introducing ungrounded facts or unsupported claims unless the task is explicitly adversarial by design.
