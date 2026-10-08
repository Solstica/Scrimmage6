# Q4 Benders–CG LP Root Acceleration — 2026-10-08

Experimental branch: feature/q4-local-branching-ccdc. Full reproducible code, the original 50,000-task checkpoint, cached original CSVs, per-round histories, all restart NPZ files and a detailed Chinese report are packaged in this ChatGPT conversation as **Q4_BendersCG_Accelerated_Root_20261008.zip**.

## Same-model cold-start LP comparison

The existing restricted LP (using 18-round stress-specific regions cuts and newly priced columns) was held fixed.

| renewable | columns / cuts | HiGHS dual simplex 45s | HiGHS interior point |
| --- | --- | --- | --- |
| 80% | 155,423 / 132 | timed out at 45.35s, no accepted optimal solution | 29.41s, optimal |
| 90% | 162,515 / 101 | timed out at 45.28s, no accepted optimal solution | 27.87s, optimal |

The interior-point results passed maximum assignment/capacity violations < 1e-12. This is a **solver-method switch**, **not** LP basis warm starting: highspy was unavailable in the environment and no basis was persisted.

## Valid full-domain bounds after continued separation

The root method additionally performs full legal-placement pricing across **233,375,201** original eligible placements, decreases each task's assignment dual by its most negative missing-column reduced cost, adds scenario-specific valid regional Benders cuts, and keeps the best provably valid global LP bound rather than the restricted LP objective.

| renewable | original 18-round valid LB (CNY) | resumed final valid LB (CNY) | verified integer UB (CNY) | abs gap (CNY) |
| --- | ---: | ---: | ---: | ---: |
| 80% | -489,185,401.06 | -489,185,401.06 (23 rounds) | -415,935,771.62 | 73,249,629.44 |
| 90% | -465,450,184.44 | **-460,594,931.76 (35 rounds)** | -454,226,184.47 | **6,368,747.29** |

90% relative gap vs abs(UB) is about 1.40%, down from 2.47%. The final 90% restricted master has 167,497 columns, 338 cuts, last pricing found 50 tasks with missing negative reduced-cost columns, and maximum regional recourse-cut violation is 789,387 CNY. **Neither 50k-task scenario has its complete LP root closed or has proved integer optimality.**

## Controlled valid cut densification

From the SAME 90% round-21 checkpoint, compare 2 new LP/pricing iterations:
- Standard one Benders cut per violated region: full-domain LB -462,084,376.24 CNY; time ~53.34s.
- Additional two load-interpolation cuts per region (35% and 70% of the way from current fractional load to verified integer incumbent): LB -461,928,593.80 CNY; time ~54.25s.
- Improvement 155,782.43 CNY in certified LB with 0.91s extra execution in this single ablation. These are valid **multi-point cuts**, **not claimed Pareto-optimal**.
- Matched 80% experiment: both versions retain the old -489,185,401.06 CNY bound; extra cuts reduce current cut violation but do not improve the best global bound, so not general advantage.

## Independent verification

- 70 explicit cost dual-repair LP tests + 100 cost/QoS conditional lower bound tests: passed.
- Final 90% 50,000-job integer schedule: 0 assignment, legality or resource violations; true recourse cost -454,226,184.47488326 CNY; 0/338 invalid regional cuts >0.01 CNY.
- 338 cuts also checked against initial and incumbent schedules and their 25%, 50%, 75% convex load combinations, all passed.
- Reproducible code in bundle; note CSVs cache original user Excel sheets faithfully.
- Solver choice is not itself a novel mathematical algorithm, and root closure remains unresolved.

Paper implication: report algorithmic profiling as a numerical implementation improvement, avoid asserting provable faster convergence for all scenarios, and keep official regional multi-cut Benders + exact pricing as the mathematical main framework.
