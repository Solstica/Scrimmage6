# CCDC 2027 Q4 — Historical timing audit and full-scale neural pilot (2026-10-08)

## Audited archival run

Repository: `Solstica/Scrimmage6`, ref `feature/q4`, path `modules/50_q4/Q4_COMPLETE_ARCHIVE_20260819/records`.

Archived `qos_final_recertification/q4_recertification_stage_metrics.csv` contains 186 event records. Their event breakdown includes 92 regional Benders cut additions, 40 integer-checked cut additions, 46 root-LP closures, and 6 stage-completion records (two sweeps). The final log records elapsed 243.43 min; the Cost re-certification was recorded up to 99.87 min. These are persisted elapsed counters across resumed runs, not isolated per-call timings.

Stress logs `formal_scenarios/renew_down_80_region_multicut_run2/renew_down_80_region_multicut_full_pool/q4_lexicographic_stage_metrics.csv` record 82 iterations and about 60.09 minutes at 498 cuts, without root closure in that logged run. This provides concrete evidence that Benders cut generation can dominate total time before the integer MIP stage.

## Real uploaded-data local test — DIFFERENT column set

Actual task/region/energy input was supplied by the user as six Excel sheets and cached locally as CSV. We reconstructed a **legal but different** 137,158-column task placement pool and built six Benders cuts from the initial energy LP. No archived GitHub NPZ binary was mounted in the local runtime. Thus the following times are **not** a timing of the original 1,173-cut checkpoint.

Under renewable factor 0.8: 50,000 jobs, 137,158 columns, 28,872 GPU/IT rows and 1.25M nonzeros; LP root 1.73–1.84s, six energy LP 0.8s, full-domain exact pricing 2.59s over 233,375,201 eligible placements, and limited-cut integer MIP reached a 20s time limit with an incumbent. The integer candidate's true energy cost was -405,945,973.77 CNY (initial feasible -400,478,236.84 CNY). No global/complete Benders optimality claim.

Under renewable factor 1.0: limited-cut MIP 2.55s, but true recourse of its solution (-454,472,850.18 CNY) was WORSE than the initial feasible incumbent (-458,734,779.13 CNY), because only six preliminary cuts had been added. The optimizer's zero gap was ONLY for the approximate integer master. This is a strong warning against learning supervised labels from incomplete Benders cuts without recourse verification.

## Small MLP trained from limited-cut teacher

Train labels from factor 0.8 MIP for 80% of TaskIDs, task-ID holdout 20%, compare factor 1.0 test. A 48–32 MLP directly scores task–region–start placement columns; a deterministic repair decoder starts from the known feasible original full schedule. At test time this neural policy does **not** call an integer MIP, and six true energy LPs audit the result.

| Renewable factor | Initial cost (CNY) | Weak limited-cut MIP (CNY) | MLP + repair (CNY) |
| --- | ---: | ---: | ---: |
| 0.8 | -400478236.84 | -405945973.77 | -405454404.51 |
| 1.0 | **-458734779.13** | -454472850.18 | -454746862.99 |

The MLP is inferior to the integer candidate under 80% and inferior to the initial incumbent at 100%. Label prediction accuracy of 89.46% (held-out TaskIDs, factor 0.8) and 88.63% (held-out TaskIDs, factor 1.0) is not evidence of objective improvement. Independent 50,000-job resimulation and six-region energy LP checks confirm no hard violations for both neural schedules. Learning should NOT be marketed as proven superior to the original MIP.

The full local reproducibility package with raw-data caches, scripts, labeled reconstructed pool, neural weights, two complete schedules, per-stage timings, and audit reports is provided in the active user conversation as `Q4_CCDC_Fullscale_Profile_Neural_20261008.zip`.

## Exact historical checkpoint profiling code

The **read-only** profiler `q4_full_checkpoint_profiler.py` is stored in this same branch. Run it with the original uploaded Excel sheets and existing GitHub `Q4_COMPLETE_ARCHIVE_20260819/records/qos_final_recertification/lexicographic_state.npz`; it uses the actual saved active columns and all saved regional Benders cuts, timing `master_lp`, `six_region_energy_lp`, `full_domain_pricing`, and `restricted_integer_mip` without modifying artifacts or claiming integer optimality.

**Algorithmic conclusion:** Do not replace the whole Q4 MIP based on restricted 300-task pilots or on the six-cut 137k surrogate. Profile the exact archived full-cut model. Make a learned primal scheduler compete on true energy-verified incumbents under matched total wall time; keep Benders and LP pricing for recourse and lower-bound certification.
