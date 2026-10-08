# Q4 Local Branching experiment (CCDC)

An **opt-in integer primal heuristic** layered on the original region-multi-cut Benders / full-domain column-generation root. The existing solver, original cuts, pricing implementation, and certification pipeline remain unchanged. This file does **not** prove full-domain integer optimality.

## Model and scope
For a known feasible assignment `xbar`, the extra row is
`sum_i (1 - x[i, assigned_region_i, assigned_start_i]) <= K`.
All task assignments remain exactly-one. The method searches at most K task changes **among the saved active columns**. The real Energy/BESS/Grid LP checks each proposed integer schedule. An improved incumbent is accepted only after this verification. If the checked energy epigraph is underestimated, add valid region cuts and re-solve the local neighborhood.

## Inputs
The training competition's original Excel sheets are not tracked in this repository. Download the Q4 attachment files to a local directory first. Use a completed `region_multicut_v1` checkpoint containing `lexicographic_state.npz`, and an integer task schedule with columns `TaskID,区域,开工小时` (or `目标区域` in place of `区域`).

Example from repository root:

```sh
python modules/50_q4/code/q4_local_branching.py \
  --attachment-dir /path/to/original/attachments \
  --state-dir modules/50_q4/results/qos_final_recertification \
  --schedule-csv modules/50_q4/results/full_run/best_schedule.csv \
  --output-dir /tmp/q4_local_branching_baseline \
  --k 20 --max-k 160 --iterations 10 \
  --node-seconds 60 --max-seconds 600
```

For the renewable-pressure diagnostic, supply `--renew-factor 0.8`. Existing baseline Benders cuts are discarded in this scenario and cuts are generated for the changed renewable supply. In this case, ensure the input incumbent remains energy-feasible under the new scenario.

Outputs: `history.csv`, `best_schedule.csv`, `summary.json`.

## Validation and scientific limitations
```sh
python -m unittest modules/50_q4/code/test_q4_local_branching.py -v
```
Unit tests verify exact task-change interpretation, the K=0..3 neighborhood optima, an epigraph cut, and a strict improvement cutoff.

A genuine comparison still requires running the original Excel data with equal wall-time budgets and objective/feasibility verification. **A root-LP full-domain pricing check alone does not prove global optimality of the original integer MILP.** Local Branching neither modifies the complete legal domain nor expands the active pool; therefore its found incumbents cannot be described as exact full-domain integer solutions.

No improvements or runtimes for the original 50,000-task case are claimed here.
