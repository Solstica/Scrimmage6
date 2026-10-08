# Real Q4 stress experiment — 2026-10-08

Experimental code and full datasets/checkpoint packaged in the current ChatGPT conversation as **Q4_Stress_Learning_Experiment_20261008.zip**.

## Setup

- User-provided actual Q4 `region_multicut_v1` archive with 50,000 AI tasks, 137,158 **original** active columns.
- Two stress scenarios: available renewable factor 0.8 and 0.9.
- **Do not reuse** the original 1,173 Benders cuts under new renewable supply. Baseline starts with 6 scenario-specific optimality cuts from the feasible initial assignment and adds further valid integer-solution regional cuts.
- Baseline: 55s budget, iterative regional-cut Benders-MIP over all saved columns, genuine energy-LP objective check.
- Learned MLP (only scenario 80%, three seeds): sample 120 verified single-move energy-cost labels, train small 17-32-16-1 regressor, capacity-safe decode up to 3,000 moves, accept energy-verified improvement; learning/label time included.
- Nonlearned dual-guided control: regional recourse load-balance dual ranking, 3,000 capacity-safe moves, true energy-LP batch verification.
- **This is a restricted original archived-column study, not full-domain stress column-generation certification, nor integer optimality.**

## Verified best net energy cost (CNY)

| Renewable | Initial | Iterative Benders-MIP | Dual-guided |
|---|---:|---:|---:|
| 80% | -401,445,986.21 | -410,203,149.38 | **-411,265,390.80** |
| 90% | -443,056,598.53 | -445,298,828.86 | **-449,187,626.73** |

For 80%, the neural MLP best costs were -404,284,898.99 (seed13), -401,451,741.90 (seed29), and -403,672,404.39 (seed47).

At 80%, dual-guided first reached its verified best at ~5.69s including input setup vs MIP at ~18.39s; at 90%, ~5.28s vs MIP at ~18.36s. The 80% MIP overran its nominal 55s limit to 60.29s search time, without improving its best incumbent beyond the first iteration.

Independent verification of all 7 saved 50k-task schedules: unique assignment, legal region/time, RT timing, GPU/IT capacity, facility capacity, six-region energy LP and stress-specific affine Benders cut validity passed. Package contains `summary.csv`, `convergence.csv`, result traces, schedules, separate verifier and PNG plots.

## Interpretation

Direct LP marginal values currently outperform an online small-sample MLP, and also outperform this weakly closed Benders-MIP within the tested budget. This supports further investigation of **dual-guided feasible primal reconstruction**, not a claim of a general neural substitute for MIP. Need full-domain stress pricing, stronger baselines, matched hard wall-clock control, multi-instance statistics, and lexicographic QoS verification before publication-level superiority claims.
