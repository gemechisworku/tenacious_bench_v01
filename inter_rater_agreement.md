# Inter-Rater Agreement (Stage 2 Manual Calibration)

## Protocol
1. Sample size: `30` held-out-eligible tasks.
2. Two manual labeling passes were completed by the same rater **24 hours apart**.
3. The second pass was performed **blind to first-pass labels**.
4. Dimensions labeled per task: `direct`, `grounded`, `honest`, `professional`, `non_condescending`.

## Initial Agreement (Before Revision)
Per-dimension agreement:
1. `direct`: `76.67%`
2. `grounded`: `83.33%`
3. `honest`: `86.67%`
4. `professional`: `90.00%`
5. `non_condescending`: `86.67%`

Initial overall agreement: `84.67%`.

## Rubric Revision Trigger and Change
Revision threshold: `<80%` per dimension.

Triggered dimension:
1. `direct` (`76.67%`)

Applied revision (`R1`):
1. Added explicit cold-email length bands and tie-break guidance.
2. Clarified one-ask counting when rhetorical follow-up lines appear.

## Final Agreement (After Revision)
Per-dimension agreement:
1. `direct`: `90.00%`
2. `grounded`: `90.00%`
3. `honest`: `93.33%`
4. `professional`: `96.67%`
5. `non_condescending`: `93.33%`

Final overall agreement: `92.67%`.

## Per-Dimension Matrix (Final)
1. `direct`: `27/30` agree
2. `grounded`: `27/30` agree
3. `honest`: `28/30` agree
4. `professional`: `29/30` agree
5. `non_condescending`: `28/30` agree

Raw structured record:
`tenacious_bench_v0.1/inter_rater_agreement.json`

