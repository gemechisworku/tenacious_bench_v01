# Inter-Rater Agreement (Stage 2)

## Protocol
1. Sample size: `30` tasks.
2. Pass A: standard marker-pass logic from `scoring_evaluator.py` (`>=4/5` per marker).
3. Pass B: independent second pass with a stricter directness adjustment for long cold emails.

This is a deterministic two-pass reproducibility check for Stage 2 build-out. A true 24-hour manual relabel loop is planned for v0.2.

## Results
Agreement by marker:
1. `direct`: `100.0%`
2. `grounded`: `100.0%`
3. `honest`: `100.0%`
4. `professional`: `100.0%`
5. `non_condescending`: `100.0%`

Overall agreement across all marker decisions: `100.0%`.

Raw detail file:
`tenacious_bench_v0.1/inter_rater_agreement.json`

## Interpretation
1. Stage 2 rubric is internally consistent under deterministic re-labeling.
2. High agreement is expected because both passes are evaluator-driven.
3. For publication-grade methodology, replace this with manual two-pass labeling + adjudication notes.
