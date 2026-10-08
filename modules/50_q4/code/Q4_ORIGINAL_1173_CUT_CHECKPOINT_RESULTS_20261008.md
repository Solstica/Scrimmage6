# Original 1,173-cut Q4 checkpoint: independent real-data validation (2026-10-08)

The actual archived `qos_final_recertification/lexicographic_state.npz` was supplied by the user and verified locally, SHA-256 `62b4eee955cdaaf059fd1701dda30a62bfeec5355b6e6df2ca1b7e0638a0ae87`.

- `model_version=region_multicut_v1`, `stage=finished`, **50,000 jobs, 137,158 exact saved placement columns, 1,173 regional Benders cuts**.
- Archived `cut_region` distribution: A/B/C: 1 each; D: 100; E: 512; F: 558.
- 90 hand-recalculated native cut/placement coefficients match the sparse matrix to **zero** absolute discrepancy.
- Reconstructed actual archived Cost LP lower bound: **-459,340,688.8007056 CNY**, matching historical records.
- Actual full-domain pricing: **233,375,201** legal placements checked, zero missing negative reduced-cost columns.
- On the local experiment system: archive cut matrix **0.30 s**, Cost LP **2.25 s**, six regional energy LP **~0.70 s**, full-domain pricing **2.29 s**.
- 20-second original-cut restricted MIP: solver status **time limit**, approximate master cost **-459,335,974.64 CNY**, exact energy LP cost **-458,274,721.95 CNY**, energy-model underestimation ~**1,061,252.68 CNY**; the integer assignment passes resource and energy feasibility checks.
- Adding three mathematically valid regional recourse cuts from this integer solution (D/E/F) yields a subsequent 20-second MIP candidate with exact energy cost **-458,570,866.08 CNY**, remaining recourse underestimation ~**760,013.45 CNY**.
- The archive's first 50k columns form a feasible initial schedule with exact cost **-458,815,194.33 CNY**: **both** limited-time MIP candidates are worse than this existing feasible upper bound.
- A frozen two-layer MLP previously trained from a different six-cut 80%-renewable restricted master was transferred to the **actual archived columns**, no retraining. Neural inference 0.012 s, capacity repair 0.456 s, energy recheck 0.738 s, valid schedule but **-458,068,266.80 CNY** true cost; rejected by incumbent acceptance.

This study reproduces the **Cost-stage** LP/MIP, not the complete Cost–Wait–Latency recertification program. Currency was scaled to million CNY for numerical stability, and the integer MIP results are time-limited and environment-dependent. **Do not claim that simple MLP replaces or accelerates the full exact Benders-CG solver.**

The user was provided in the current ChatGPT conversation an independently runnable artifact bundle named `Q4_Archived_Checkpoint_Validation_20261008.zip`, including source code, exact uploaded NPZ, CSV cached copies of original six spreadsheets, experiments, and a Chinese technical report. The read-only integration profiler in this branch, `q4_full_checkpoint_profiler.py`, is also available for running against the same input from within the original repository.

**Decision:** ML research should focus on true energy-verified feasible incumbent improvement in nontrivial stress scenes. Rebuild scenario-specific Benders cuts, compare under matched total wall-time budgets, and retain exact energy LP and lower-bound certification.
