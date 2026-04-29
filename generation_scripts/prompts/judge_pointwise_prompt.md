# Pointwise Judge Prompt

Score each candidate task on a 1-5 scale for:
1. Input coherence
2. Ground-truth verifiability
3. Rubric-application clarity

Scoring guidance:
1. `5`: fully coherent/verifiable/clear with no blockers.
2. `4`: mostly solid; minor issue but still acceptable.
3. `3`: ambiguous or partially malformed; needs revision.
4. `2`: major quality issue likely to break scoring.
5. `1`: unusable.

Inclusion threshold:
- Keep only if all three dimensions are `>= 4`.

Additional rule:
- If task generator family equals judge family, reject to prevent preference leakage.
