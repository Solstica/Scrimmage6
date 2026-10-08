"""Read-only profiler for the archived 50k-task Q4 Benders–CG master.

Execute beside q4_qos_refinement.py after checking out this repository branch.
Uses the ORIGINAL archived ColumnPool and Benders cuts, not a reconstructed pool.
Does not modify checkpoints, append cuts, perform recertification or claim optimality.
"""
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from q4_full_solver import (
    read_data, make_presolve_rows, assignment_matrix, resource_matrix,
    facility_load, energy_lp, cut_matrix,
)
from q4_qos_refinement import (
    load_state, pool_values, read_latency, StageSpec, solve_stage_lp,
    price_full_domain, solve_stage_mip,
)


def profile(args):
    summary = {"scope": "archived exact Q4 regional-multicut active-column master",
               "integer_optimality_proved": False,
               "timings_seconds": {}}
    tic = time.perf_counter()

    def measured(name, action):
        start = time.perf_counter()
        answer = action()
        summary["timings_seconds"][name] = round(time.perf_counter() - start, 6)
        print(name, summary["timings_seconds"][name], flush=True)
        return answer

    path = args.state_dir / "lexicographic_state.npz"
    if not path.is_file():
        raise SystemExit(f"Archived checkpoint missing: {path}")
    summary["state_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    pool, cuts, stage, iteration, cost_cap, wait_star, initial_columns = measured(
        "checkpoint_load", lambda: load_state(args.state_dir))
    if any(cut.region < 0 for cut in cuts):
        raise SystemExit("Rejecting checkpoint containing aggregate (not regional) cuts")
    n = len(pool)
    summary.update(columns=n, cuts=len(cuts), saved_stage=stage,
                   saved_iteration=iteration, initial_columns=initial_columns)

    data = measured("excel_load", lambda: read_data(args.attachment_dir))
    summary["tasks"] = len(data.task)
    if len(data.task) != 50000:
        print("WARNING: not the full original 50,000-task instance", flush=True)
    gpu_row, it_row, rhs, kinds = measured("presolve", lambda: make_presolve_rows(data))
    latency_raw = measured("latency_load", lambda: read_latency(args.attachment_dir))
    wait, latency = measured("column_objectives", lambda: pool_values(pool, data, latency_raw))
    assign = measured("assignment_matrix", lambda: assignment_matrix(pool, len(data.task)))
    resource = measured("resource_matrix", lambda: resource_matrix(
        pool, data, gpu_row, it_row, len(rhs)))
    cm = measured("benders_cut_matrix", lambda: cut_matrix(pool, data, cuts))
    summary["nonzeros"] = {"assignment": assign.nnz, "resource": resource.nnz,
                           "cuts": cm.nnz}
    const = np.asarray([cut.const for cut in cuts], dtype=float)
    regions = np.asarray([cut.region for cut in cuts], dtype=np.int8)
    spec = StageSpec("Cost profiling", "cost", None)
    objective = np.zeros(n)

    lp = measured("master_lp", lambda: solve_stage_lp(
        assign, resource, cm, rhs, const, objective, wait, regions, spec))
    summary["root_lp_objective"] = float(lp["objective"])
    fractional = measured("fractional_facility_load", lambda: facility_load(
        pool, data, lp["x"]))
    energy = measured("six_region_energy_lp", lambda: energy_lp(fractional, data))
    summary["energy_success"] = bool(energy["success"])
    if energy["success"]:
        summary["energy_cost"] = float(energy["cost"])
        summary["max_region_cut_violation"] = float(
            np.max(energy["region_cost"] - lp["theta"]))

    if args.full_pricing:
        additions, reduced, negative = measured("full_domain_pricing", lambda:
            price_full_domain(pool, data, gpu_row, it_row,
                              lp["resource_dual"], lp["cut_dual"], cuts,
                              lp["assignment_dual"], spec, latency_raw,
                              lp["wait_cap_dual"], args.price_tol,
                              args.columns_per_task, show_bar=False))
        summary.update(new_columns_found=len(additions),
                       missing_min_reduced_cost=float(reduced),
                       negative_task_regions=negative)

    if args.mip_seconds > 0:
        mip = measured("restricted_integer_mip", lambda: solve_stage_mip(
            assign, resource, cm, rhs, const, objective, wait, regions, spec,
            args.mip_seconds, args.mip_gap))
        summary["mip"] = {
            "status": int(mip.status), "message": str(mip.message),
            "reported_gap": None if getattr(mip, "mip_gap", None) is None
            else float(mip.mip_gap),
            "reported_bound": None if getattr(mip, "mip_dual_bound", None) is None
            else float(mip.mip_dual_bound),
        }
        if mip.x is not None:
            x = np.asarray(mip.x[:n])
            if np.max(np.abs(x - np.rint(x))) <= 1e-5:
                x = np.rint(x)
                summary["mip"]["max_assignment_error"] = float(np.max(
                    np.abs(assign @ x - 1.0)))
                summary["mip"]["max_resource_excess"] = float(max(
                    0.0, np.max(resource @ x - rhs)))
                checked = measured("integer_energy_recheck", lambda:
                    energy_lp(facility_load(pool, data, x), data))
                summary["mip"]["true_energy_cost"] = (
                    float(checked["cost"]) if checked["success"] else None)

    summary["total_wall_seconds"] = round(time.perf_counter()-tic, 6)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attachment-dir", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("q4_full_checkpoint_profile.json"))
    parser.add_argument("--full-pricing", action="store_true")
    parser.add_argument("--price-tol", type=float, default=1e-7)
    parser.add_argument("--columns-per-task", type=int, default=2)
    parser.add_argument("--mip-seconds", type=float, default=30.0)
    parser.add_argument("--mip-gap", type=float, default=1e-5)
    args = parser.parse_args()
    if args.mip_seconds < 0: parser.error("mip-seconds must be nonnegative")
    profile(args)


if __name__ == "__main__":
    main()
