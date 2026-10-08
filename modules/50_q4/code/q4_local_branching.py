"""Opt-in, restricted-column Local Branching for the Q4 regional Benders cost master.

The original full-domain column generation and certification pipeline is not modified.
This script only searches over the columns supplied by an existing Q4 checkpoint.
Usage: python q4_local_branching.py --attachment-dir ... --state-dir ...
       --schedule-csv ... --output-dir ... [--renew-factor 0.8]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csr_matrix, hstack, vstack


def neighborhood_row(incumbent: np.ndarray, n_binary: int, task_count: int,
                     k: int) -> tuple[csr_matrix, float]:
    """Return -sum_{j in incumbent support} x_j <= k-task_count.

    Exactly-one assignment makes this equal to at most k rescheduled tasks.
    """
    if not 0 <= k <= task_count:
        raise ValueError("k must lie between 0 and task_count")
    if incumbent.shape != (n_binary,):
        raise ValueError("incumbent dimension does not match column count")
    support = np.flatnonzero(incumbent > 0.5)
    if len(support) != task_count or np.max(np.abs(incumbent - np.rint(incumbent))) > 1e-7:
        raise ValueError("incumbent must be binary with exactly task_count selected columns")
    row = csr_matrix((np.full(len(support), -1.0),
                      (np.zeros(len(support), dtype=int), support)),
                     shape=(1, n_binary))
    return row, float(k - task_count)


def solve_binary_neighborhood(*, c: np.ndarray, aub: csr_matrix, bub: np.ndarray,
                              aeq: csr_matrix, beq: np.ndarray, n_binary: int,
                              incumbent: np.ndarray, task_count: int, k: int,
                              seconds: float, cutoff: float | None = None):
    """MILP with a task-Hamming ball; no fixing or removal of original columns."""
    row, rhs = neighborhood_row(incumbent, n_binary, task_count, k)
    extra = hstack([row, csr_matrix((1, len(c) - n_binary))], format="csr")
    blocks = [aub, extra]
    bounds = [np.asarray(bub, float), np.asarray([rhs])]
    if cutoff is not None:
        blocks.append(csr_matrix(np.asarray(c, float).reshape(1, -1)))
        bounds.append(np.asarray([float(cutoff)]))
    all_ub = vstack(blocks, format="csr")
    all_rhs = np.concatenate(bounds)
    lb = np.r_[np.zeros(n_binary), np.full(len(c)-n_binary, -1e10)]
    ub = np.r_[np.ones(n_binary), np.full(len(c)-n_binary, np.inf)]
    return milp(c=np.asarray(c, float),
                integrality=np.r_[np.ones(n_binary), np.zeros(len(c)-n_binary)],
                bounds=Bounds(lb, ub),
                constraints=[LinearConstraint(all_ub, -np.inf, all_rhs),
                             LinearConstraint(aeq, beq, beq)],
                options={"time_limit": float(seconds), "mip_rel_gap": 1e-5, "disp": False})


def _read_incumbent(schedule_csv: Path, pool, data, regions) -> np.ndarray:
    schedule = pd.read_csv(schedule_csv, encoding="utf-8-sig")
    region_col = next((name for name in ("目标区域", "区域") if name in schedule), None)
    if region_col is None or "TaskID" not in schedule or "开工小时" not in schedule:
        raise ValueError("schedule must have TaskID, 目标区域/区域, 开工小时")
    lookup = {int(t): i for i, t in enumerate(data.task["TaskID"].to_numpy())}
    if schedule["TaskID"].duplicated().any() or len(schedule) != len(data.task):
        raise ValueError("schedule must contain exactly one placement per task")
    assignments = []
    for entry in schedule.itertuples(index=False):
        task_id = int(getattr(entry, "TaskID"))
        if task_id not in lookup:
            raise ValueError(f"unknown task {task_id}")
        reg = str(getattr(entry, region_col))
        if reg not in regions:
            raise ValueError(f"unknown region {reg}")
        start = int(getattr(entry, "开工小时"))
        task = lookup[task_id]
        pool.add(task, regions.index(reg), start)
        assignments.append((task, regions.index(reg), start))
    ti, rr, ss = pool.arrays()
    idx = {(int(i), int(r), int(s)): j for j, (i,r,s) in enumerate(zip(ti,rr,ss))}
    x = np.zeros(len(ti), dtype=float)
    for key in assignments:
        x[idx[key]] = 1.0
    return x


def run_q4(args) -> dict:
    # Import lazily so neighborhood tests work without the competition attachments.
    from q4_full_solver import (R, REGIONS, read_data, make_presolve_rows,
                                resource_matrix, assignment_matrix, facility_load,
                                energy_lp)
    from q4_qos_refinement import (load_state, cut_matrix, add_region_cuts,
                                    StageSpec, assemble_stage_model, audit_solution)

    data = read_data(args.attachment_dir)
    pool, saved_cuts, _, _, _, _, _ = load_state(args.state_dir)
    incumbent = _read_incumbent(args.schedule_csv, pool, data, list(REGIONS))
    gpu_row, it_row, rhs, _ = make_presolve_rows(data)
    resource = resource_matrix(pool, data, gpu_row, it_row, len(rhs))
    assign = assignment_matrix(pool, len(data.task))
    if np.any(abs(np.asarray(assign @ incumbent).ravel() - 1) > 1e-7):
        raise ValueError("incumbent is missing task assignments")
    if np.any(np.asarray(resource @ incumbent).ravel() - rhs > 1e-7):
        raise ValueError("incumbent violates GPU/IT capacity")
    renew = None if args.renew_factor == 1.0 else data.renew * args.renew_factor

    def evaluate(x):
        energy = energy_lp(facility_load(pool, data, x), data, renew_override=renew)
        if not energy["success"]:
            return energy, False, {"energy_status": energy["message"]}
        _, audit = audit_solution(pool, data, x, gpu_row, it_row, rhs,
                                   np.zeros((R, R)), energy)
        # audit_solution's latency matrix is only used to report QoS, not hard SLA;
        # SLA validity is checked with the original data.legal mask.
        valid = all(not isinstance(v, (int, float, np.number)) or v <= 1e-5
                    for v in audit.values())
        return energy, valid, audit

    energy, valid, audit = evaluate(incumbent)
    if not valid:
        raise ValueError(f"initial incumbent failed full verification: {audit}")
    best = float(energy["cost"])
    initial = best
    # Saved cuts can be reused only for the renewable scenario they were built for.
    # For a changed renewable scenario rebuild cuts at the checked incumbent.
    cuts = list(saved_cuts) if args.renew_factor == 1.0 else []
    add_region_cuts(cuts, data, facility_load(pool, data, incumbent), energy)
    baseline_cut_count = len(cuts)
    n = len(pool)
    spec = StageSpec("Cost-Local-Branching", "cost", None)
    k = min(int(args.k), len(data.task))
    history = []
    t0 = time.monotonic()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for iteration in range(1, args.iterations + 1):
        remaining = args.max_seconds - (time.monotonic() - t0)
        if remaining <= 0:
            break
        cm = cut_matrix(pool, data, cuts)
        aub, bub, aeq, beq, meta = assemble_stage_model(
            assign, resource, cm, rhs,
            np.asarray([cut.const for cut in cuts]), np.zeros(n),
            np.zeros(n), np.asarray([cut.region for cut in cuts]), spec)
        result = solve_binary_neighborhood(
            c=meta["c"], aub=aub, bub=bub, aeq=aeq, beq=beq,
            n_binary=n, incumbent=incumbent, task_count=len(data.task), k=k,
            seconds=min(args.node_seconds, remaining), cutoff=best-args.min_improvement)
        record = {"iteration":iteration, "k":k, "milp_status":int(result.status),
                  "milp_message":str(result.message), "best_true_cost":best,
                  "new_cuts":0, "accepted":False, "elapsed_seconds":round(time.monotonic()-t0,3)}
        if result.x is not None:
            xb = np.asarray(result.x[:n])
            if np.max(abs(xb - np.rint(xb))) <= 1e-6:
                xb = np.rint(xb)
                if np.dot(xb, incumbent) >= len(data.task) - k - 1e-6:
                    e, feasible, _ = evaluate(xb)
                else:
                    e, feasible = None, False
                if feasible:
                    theta = np.asarray(result.x[n:n+R])
                    violated = np.flatnonzero(e["region_cost"] - theta > args.cut_tolerance)
                    if len(violated):
                        add_region_cuts(cuts, data, facility_load(pool,data,xb), e, violated)
                        record["new_cuts"] = len(violated)
                    record["candidate_true_cost"] = float(e["cost"])
                    if float(e["cost"]) < best - args.min_improvement:
                        best = float(e["cost"])
                        incumbent = xb
                        record["accepted"] = True
        if record["accepted"]:
            k = min(args.k, len(data.task))
        else:
            k = min(int(math.ceil(k * 1.5)), args.max_k, len(data.task))
        record["best_true_cost"] = best
        history.append(record)
        with (args.output_dir / "history.csv").open("w", newline="", encoding="utf-8") as stream:
            writer=csv.DictWriter(stream, fieldnames=["iteration", "k", "milp_status", "milp_message", "best_true_cost", "new_cuts", "accepted", "elapsed_seconds", "candidate_true_cost"])
            writer.writeheader(); writer.writerows(history)
    chosen = np.flatnonzero(incumbent > .5)
    ti, rr, ss = pool.arrays()
    pd.DataFrame({"TaskID":data.task.iloc[ti[chosen]]["TaskID"].to_numpy(),
                  "区域":[REGIONS[int(v)] for v in rr[chosen]],
                  "开工小时":ss[chosen]}).to_csv(
                      args.output_dir/"best_schedule.csv", index=False, encoding="utf-8-sig")
    report = {"status":"EXPERIMENTAL_RESTRICTED_COLUMN_HEURISTIC",
              "initial_true_cost":initial, "best_true_cost":best,
              "improvement": initial-best,
              "active_columns":n, "task_count":len(data.task),
              "initial_cut_count":baseline_cut_count, "final_cut_count":len(cuts),
              "iterations_completed":len(history),
              "full_domain_integer_optimality_proved":False,
              "note":"Original Benders/CG certification and its lower bound are unchanged."}
    (args.output_dir/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report


def main():
    p=argparse.ArgumentParser(description="Q4 optional local branching integer search")
    p.add_argument("--attachment-dir", required=True, type=Path)
    p.add_argument("--state-dir", required=True, type=Path,
                   help="Directory containing region_multicut_v1 lexicographic_state.npz")
    p.add_argument("--schedule-csv", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--renew-factor", type=float, default=1.0)
    p.add_argument("--k", type=int, default=20)
    p.add_argument("--max-k", type=int, default=160)
    p.add_argument("--iterations", type=int, default=10)
    p.add_argument("--node-seconds", type=float, default=60.0)
    p.add_argument("--max-seconds", type=float, default=600.0)
    p.add_argument("--min-improvement", type=float, default=1e-3)
    p.add_argument("--cut-tolerance", type=float, default=1e-3)
    a=p.parse_args()
    if not (a.k > 0 and a.max_k >= a.k and a.iterations > 0 and a.node_seconds > 0
            and a.max_seconds > 0 and a.renew_factor > 0 and a.min_improvement > 0):
        p.error("invalid local branching settings")
    print(json.dumps(run_q4(a),ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
