# Q4 Local Branching — real-data preliminary verification (2026-10-08)

The original six competition Excel workbooks were supplied in the conversation and used in an independent feasibility / recourse test.

- Original input: 50,000 individual non-preemptive AI tasks; six regions; 2,407 energy time slots.
- Reconstructed greedy initial schedule: all 50,000 tasks assigned; no violations of legal region, realtime-immediate-start, deadline, GPU capacity, or IT capacity.
- Complete Renewable/BESS/Grid LP: six region LPs solved for the full horizon under both nominal and 80%-renewable scenarios.
- Unit/regression tests: 4 passed, including a mocked energy-oracle integration test.

The experiment fixed 49,700 tasks and made only **300 legal same-start region migrations** available. This restricted search was used to check the method, **not** as a substitute for the original full-domain column generation or Cost/Wait/Latency final certification.

| Renewable factor | Method | Verified cost CNY | Initial cost CNY | Integer-search time s |
|:--|:--|--:|--:|--:|
| 1.0 | Benders + unrestricted MIP on selected candidates | -459,325,953.20 | -458,734,779.13 | 3.71 |
| 1.0 | Benders + Local Branching on same candidates | -459,316,725.14 | -458,734,779.13 | 4.45 |
| 0.8 | Benders + unrestricted MIP on selected candidates | -404,206,391.91 | -400,478,236.84 | 20.20 |
| 0.8 | Benders + Local Branching on same candidates | -404,244,391.93 | -400,478,236.84 | 5.76 |

All four **complete 50,000-task output schedules** underwent a separate resource-capacity, temporal, legal-region, and energy-LP feasibility recheck. No hard-constraint violations were found; HiGHS reported zero equality and inequality residuals in these runs.

**Interpretation:** The stressed renewable scenario slightly favors Local Branching; the nominal scenario favors unrestricted MIP. The 5-round tests did **not** use matched wall-clock stopping conditions. One trial for two scenarios and a restricted migration set cannot support a general speedup or optimality claim.

The corresponding executable scripts, input audit, CSV schedules, iteration traces and full report are delivered separately as `Q4_CCDC_LocalBranching_RealData_Package.zip` in the conversation. This repository branch keeps the optional `q4_local_branching.py` solver but does not overwrite the original Q4 pipeline.

**Next experiment:** Download the archived `region_multicut_v1` column/cut checkpoints, run the optional Local Branching search using the original user-supplied Excel files, repeat across equivalent time budgets / multiple seeds and compare Cost-stage incumbents and lower bounds against the original Benders–CG implementation. Re-run Cost→Wait→Latency recertification before paper conclusions.
