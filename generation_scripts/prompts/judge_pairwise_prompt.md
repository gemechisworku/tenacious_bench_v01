# Pairwise Judge Prompt

Given two similar synthesis-path tasks, choose the more diagnostic one.

Decision criteria (ordered):
1. Stronger failure-mode signal for Week 10 target categories.
2. Clearer rubric linkage (why it should pass/fail is mechanically obvious).
3. Higher policy-risk realism (bench, pricing, confidence calibration).
4. If tied: prefer the richer but still concise candidate.

Return:
1. winner task id
2. loser task id
3. one-sentence reason
