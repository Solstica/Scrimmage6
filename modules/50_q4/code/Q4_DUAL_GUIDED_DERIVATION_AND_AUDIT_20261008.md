# Q4: rigorous dual derivation and verified primal scheduler (2026-10-08)

## Model

For each job placement j=(i,r,s), its contribution to hourly facility load is A_(r',t),j = 1[r'=r] PUE_r alpha_i g_i omega_i,s,t. Write L(x)=F+Ax, where F is the fixed non-AI facility load.

The full regional energy linear program minimizes purchasing minus renewable electricity sale revenue, subject to renewable allocation, load supply, storage SOC dynamics, charging/discharging, grid import/export, and terminal SOC requirements.

Its standard matrix form is:

    min c^T y
    s.t. Aeq y = b0 + B L, D y <= d, y >= 0.

Its exact dual is:

    max (b0+B L)^T pi + d^T mu
    s.t. Aeq^T pi + D^T mu <= c, mu <= 0, pi unrestricted.

For renewable/price/storage parameters held fixed, obtain optimal equality marginals pi^k and select the load-balance component lambda^k = B^T pi^k. By weak and strong LP duality,

    Q_r(L) >= Q_r(L^k) + (lambda_r^k)^T (L-L^k).

This gives the valid region Benders cut:

    theta_r >= Q_r(L_r^k) + lambda_r^k · (F_r-L_r^k)
                          + sum_j (lambda_r^k · A_rj) x_j.

The same lambda gives a **lower bound** for a task move from incumbent column j0 to another legal column j:

    dual_delta(j0,j) = lambda^T (A_j - A_j0)
    true_cost_change >= dual_delta(j0,j).

A nonnegative dual_delta cannot strictly reduce true recourse cost for this current schedule. A negative dual_delta is only an improving candidate signal and is NOT a guaranteed saving. This mathematically valid local direction check does not remove any column from the full-domain master.

In the original model, SciPy linprog returns lambda from its load-balance equality marginals: result.eqlin.marginals[load_row] (full solver) or result.eqlin.marginals[1::3] (standalone region energy LP).

## Undergraduate-level solver description

One task schedule determines when and where computing power is needed. For that schedule solve the energy-storage/grid LP to get the cheapest real electricity arrangement. The LP reports each region-hour shadow price. Use those prices to estimate whether rescheduling a single job could lower cost. Try good directions in order, reject every capacity-infeasible change, and call the real energy LP at several milestones. Keep a new schedule only if its checked true cost improves. Recompute shadow prices at the new schedule and repeat.

The exact tested experiment used the original 50,000-job 137,158-column checkpoint. The pure dual method made up to 3,000 capacity-safe job changes per round and checked costs at 50, 150, 400, 1,000 and 3,000 changes; four rounds were used. It remains a primal improvement heuristic until cuts and full-domain pricing are fed back into the actual Benders-CG master.

## Mathematical validation

Independent real-data tests at 80% and 90% renewable supply:
- 36 legal feasible single-job move subgradient checks per scenario (72 total), 0 inequality failures at 0.001 CNY tolerance.
- Six regions times eight variables times 2,407 hours: maximum exact LP stationarity/KKT residuals 5.6843e-14 (80%) and 2.8422e-14 (90%).
- Twelve positive-score feasible moves per scenario also checked; every true energy cost increased.
- In 80% renewables, eight feasible task moves jointly had a dual estimate -288.88 CNY but real energy cost *increased* 34,749.77 CNY, proving the need for exact recourse acceptance.

Four-round archive active-column experiment from the prior report: 80% cost -412,302,389.07 CNY in about 24.04 s; 90% cost -453,101,228.85 CNY in about 23.00 s. Results do not prove integer global optimality or the end-to-end runtime of an integrated Benders-CG solver.

The full reproducible numerical audit and detailed Chinese explanation, including all eight hourly variable dual constraints, are in the same user's current conversation as Q4_Dual_Theory_Complete_20261008.zip.
