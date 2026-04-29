# Frontier Seed Generator Prompt

You are generating hard benchmark seeds for Tenacious sales-agent evaluation.

Requirements:
1. Anchor the seed to at least one concrete Week 10 failure mode (`SIG-*`, `BEN-*`, `TON-*`, `MTL-*`, `SCH-*`, `GAP-*`).
2. Include realistic public-signal fields: funding date/stage, hiring velocity, signal confidence, and bench request.
3. Prefer edge cases that pressure policy boundaries (weak-signal assertions, capacity over-commitment risk, pricing scope pressure).
4. Output machine-verifiable task structure with:
- `input` fields
- `candidate_output` (`subject`, `body`)
- rubric flags for required phrase checks and weak-signal behavior.

Do not produce generic marketing copy. Produce diagnostic tasks that can fail for specific reasons.
