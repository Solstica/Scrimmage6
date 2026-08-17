"""Q2 iterative dynamic-marginal refinement.

Keeps q2_solver.py as the single-pass numerical kernel, but replaces the formal
run protocol with repeated full scans from the attachment source-local reference
state. A formal endpoint is accepted only after the primary objective changes
by less than the declared relative tolerance and all hard constraints pass.
"""
from __future__ import annotations

import argparse
import importlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args():
    p = argparse.ArgumentParser(description="Q2 iterative dynamic-marginal SFETA")
    p.add_argument("attachment_dir", type=Path)
    p.add_argument("mode", nargs="?", choices=("dynamic", "cost", "carbon"), default="cost")
    p.add_argument("--start", choices=("reference", "previous"), default="reference")
    p.add_argument("--max-passes", type=int, default=8)
    p.add_argument("--relative-tol", type=float, default=1e-3)
    return p.parse_args()


def import_core(attach: Path, mode: str):
    # q2_solver.py still parses argv at import time; isolate that historical interface.
    saved = sys.argv[:]
    try:
        sys.argv = ["q2_solver.py", str(attach), mode]
        return importlib.import_module("q2_solver")
    finally:
        sys.argv = saved


def reference_schedule(core, tasks, latency, region_index):
    rows = []
    for task in tasks.itertuples(index=False):
        src = region_index[task.SourceRegion]
        duration = float(task.EstimatedDuration_min) / 60.0
        start = int(task.ArrivalHour)
        rows.append({
            "TaskID": int(task.TaskID), "TaskType": task.TaskType,
            "ArrivalHour": int(task.ArrivalHour), "GPU_Demand": float(task.GPU_Demand),
            "Duration_h": duration, "SourceRegion": task.SourceRegion,
            "ExecutionRegion": task.SourceRegion, "StartHour": start,
            "FinishHour": start + duration, "MaxLatency_ms": float(task.MaxLatency_ms),
            "Latency_ms": float(latency[src, src]),
            "LatestFinishHour": float(task.LatestFinishHour),
        })
    return pd.DataFrame(rows)


def build_priority(tasks, latency, region_index):
    work = tasks.copy()
    work["RegionCount"] = work.apply(
        lambda row: int(np.sum(latency[region_index[row.SourceRegion], :] <= row.MaxLatency_ms + 1e-9)),
        axis=1,
    )
    work["Slack_h"] = work.LatestFinishHour - work.ArrivalHour - work.EstimatedDuration_min / 60.0
    work["GPUHour"] = work.GPU_Demand * work.EstimatedDuration_min / 60.0
    return work.sort_values(
        ["RegionCount", "Slack_h", "GPUHour", "TaskID"],
        ascending=[True, True, False, True],
    )


def removal_bad_hours(core, old_region, old_hours, gpu, ai, base_facility, nonai,
                      pue, c0, g0, grid0, used0, max_grid):
    facility = pue[old_region] * (nonai[old_region, old_hours] + ai[old_region, old_hours])
    delta = facility - base_facility[old_region, old_hours]
    _, _, purchase, curt, used = core.energy_response(
        delta, c0[old_region, old_hours], g0[old_region, old_hours],
        grid0[old_region, old_hours], used0[old_region, old_hours]
    )
    bad = ((purchase < -1e-7) | (purchase > max_grid[old_region] + 1e-7)
           | (curt < -1e-7) | (used < -1e-7))
    return old_hours[bad]


def repair_filter(core, valid, region, starts, profile, old_region, bad_hours,
                  task_ai, ai, base_facility, nonai, pue, c0, g0, grid0, used0, max_grid):
    """Allow overlapping candidates to repair removal-only energy infeasibility."""
    if len(bad_hours) == 0:
        return valid
    if region != old_region:
        valid[:] = False
        return valid
    candidates = np.flatnonzero(valid)
    for hour in bad_hours:
        if not len(candidates):
            break
        rel = hour - starts[candidates]
        cover = (rel >= 0) & (rel < len(profile))
        survivors = candidates[cover]
        if not len(survivors):
            valid[:] = False
            break
        shares = profile[rel[cover].astype(int)]
        ai_new = ai[old_region, hour] + task_ai * shares
        facility_new = pue[old_region] * (nonai[old_region, hour] + ai_new)
        delta = facility_new - base_facility[old_region, hour]
        _, _, purchase, curt, used = core.energy_response(
            delta,
            np.full(len(survivors), c0[old_region, hour]),
            np.full(len(survivors), g0[old_region, hour]),
            np.full(len(survivors), grid0[old_region, hour]),
            np.full(len(survivors), used0[old_region, hour]),
        )
        okay = ((purchase >= -1e-7) & (purchase <= max_grid[old_region] + 1e-7)
                & (curt >= -1e-7) & (used >= -1e-7))
        keep = np.zeros_like(valid)
        keep[survivors[okay]] = True
        valid &= keep
        candidates = np.flatnonzero(valid)
    return valid


def run_pass(core, mode, tasks, work, schedule, gpu, ai, latency, region_index, power,
             profile_cache, base_facility, nonai, capacity_gpu, max_it, pue,
             max_facility, c0, g0, grid0, used0, price, carbon, max_grid):
    schedule_index = dict(zip(schedule.TaskID.astype(int), schedule.index))
    fallback = removal_dependent = changed = 0
    for position, task in enumerate(work.itertuples(index=False), 1):
        idx = schedule_index[int(task.TaskID)]
        old_region = region_index[schedule.at[idx, "ExecutionRegion"]]
        old_start = int(schedule.at[idx, "StartHour"])
        profile = profile_cache[int(task.EstimatedDuration_min)]
        core.add_task(gpu, ai, task, old_region, old_start, power, profile_cache, -1.0)
        old_hours = np.arange(old_start, old_start + len(profile))
        bad_hours = removal_bad_hours(
            core, old_region, old_hours, gpu, ai, base_facility, nonai, pue,
            c0, g0, grid0, used0, max_grid
        )
        removal_dependent += int(len(bad_hours) > 0)

        duration = float(task.EstimatedDuration_min) / 60.0
        source = region_index[task.SourceRegion]
        if task.TaskType == "RealTimeInference":
            lo = hi = int(task.ArrivalHour)
        else:
            lo = int(max(task.ArrivalHour, task.EarliestStartHour))
            hi = int(math.floor(min(task.LatestFinishHour - duration, 2406.0 - duration) + 1e-10))
        allowed = np.flatnonzero(latency[source, :] <= task.MaxLatency_ms + 1e-9)

        pieces = [[] for _ in range(7)]
        for region in allowed:
            starts = np.arange(lo, hi + 1, dtype=int)
            valid, dcurt, dcost, dcarbon = core.evaluate_region_candidates(
                int(region), starts, profile, float(task.GPU_Demand),
                float(task.GPU_Demand) * float(power[task.TaskType]),
                gpu, ai, base_facility, nonai, capacity_gpu, max_it, pue,
                max_facility, c0, g0, grid0, used0, price, carbon, max_grid,
            )
            valid = repair_filter(
                core, valid, int(region), starts, profile, old_region, bad_hours,
                float(task.GPU_Demand) * float(power[task.TaskType]), ai,
                base_facility, nonai, pue, c0, g0, grid0, used0, max_grid,
            )
            starts = starts[valid]
            if not len(starts):
                continue
            pieces[0].append(np.full(len(starts), region, dtype=int))
            pieces[1].append(starts)
            pieces[2].append(np.full(len(starts), latency[source, region], dtype=float))
            pieces[3].append(np.full(len(starts), int(region != source), dtype=int))
            pieces[4].append(dcurt[valid]); pieces[5].append(dcost[valid]); pieces[6].append(dcarbon[valid])

        choice = None
        if pieces[0]:
            choice = core.pick_candidate(tuple(np.concatenate(x) for x in pieces), mode)
        if choice is None:
            # Pass 1 starts from a reference state with 44 GPU-overloaded region-hours.
            # A temporary fallback is allowed during repair; convergence requires zero fallback in the last pass.
            core.add_task(gpu, ai, task, old_region, old_start, power, profile_cache, 1.0)
            fallback += 1
        else:
            region, start = choice
            changed += int(region != old_region or start != old_start)
            core.add_task(gpu, ai, task, region, start, power, profile_cache, 1.0)
            schedule.at[idx, "ExecutionRegion"] = core.REGIONS[region]
            schedule.at[idx, "StartHour"] = start
            schedule.at[idx, "FinishHour"] = start + duration
            schedule.at[idx, "Latency_ms"] = latency[source, region]
        if position % 5000 == 0:
            print(json.dumps({"mode": mode, "processed": position, "total": len(work),
                              "fallback": fallback, "changed": changed,
                              "removal_dependent": removal_dependent}, ensure_ascii=False), flush=True)
    return fallback, removal_dependent, changed


def augment_deadline_audit(audit, schedule):
    rt = schedule.TaskType.eq("RealTimeInference")
    audit["latest_finish_violations"] = int((schedule.FinishHour > schedule.LatestFinishHour + 1e-8).sum())
    audit["horizon_2406_violations"] = int((schedule.FinishHour > 2406.0 + 1e-8).sum())
    audit["earliest_start_violations"] = int((schedule.StartHour < schedule.ArrivalHour - 1e-8).sum())
    audit["rt_immediate_start_violations"] = int((schedule.loc[rt, "StartHour"] != schedule.loc[rt, "ArrivalHour"]).sum())
    audit["deadline_violations"] = int(
        ((schedule.FinishHour > schedule.LatestFinishHour + 1e-8)
         | (schedule.FinishHour > 2406.0 + 1e-8)).sum()
    )
    return audit


def primary(mode, audit):
    if mode == "cost":
        return float(audit["cost_cny"])
    if mode == "carbon":
        return float(audit["carbon_tco2"])
    return float(audit["delta_curtailment_mwh"])


def main():
    args = parse_args()
    attach = args.attachment_dir.resolve()
    if not attach.exists():
        raise SystemExit("数据目录不存在")
    if args.max_passes < 2:
        raise SystemExit("max-passes 至少为2")
    if args.relative_tol <= 0:
        raise SystemExit("relative-tol 必须为正")
    core = import_core(attach, args.mode)
    tasks, cfg, power, latency, wide, max_grid, max_export = core.load_data()
    region_index = {r: i for i, r in enumerate(core.REGIONS)}
    profile_cache = {int(d): core.overlap_profile(int(d)) for d in tasks.EstimatedDuration_min.unique()}

    if args.start == "previous":
        p = core.PROC / "q2_schedule_0_2405.csv"
        if not p.exists():
            raise SystemExit("缺少旧可行草稿 q2_schedule_0_2405.csv")
        schedule = core.make_schedule(tasks, pd.read_csv(p), latency, region_index)
    else:
        schedule = reference_schedule(core, tasks, latency, region_index)
    gpu, ai = core.state_from_schedule(tasks, schedule, region_index, power, profile_cache)

    base_gpu = np.zeros_like(gpu); base_ai = np.zeros_like(ai)
    for task in tasks.itertuples(index=False):
        core.add_task(base_gpu, base_ai, task, region_index[task.SourceRegion], int(task.ArrivalHour), power, profile_cache, 1.0)
    nonai = wide["NonAI_IT_Load_MW"]; pue = cfg["PUE"].to_numpy(float)
    base_facility = pue[:, None] * (nonai + base_ai)
    c0 = wide["Curtailment_MW"]; g0 = wide["GridPurchase_MW"] - wide["GridCharge_MW"]
    grid0 = wide["GridPurchase_MW"]; used0 = wide["UsedRenewable_MW"]
    capacity_gpu = cfg["Available_GPU"].to_numpy(float)
    max_it = cfg["Max_IT_Power_MW"].to_numpy(float)
    max_facility = cfg["Max_Facility_Power_MW"].to_numpy(float)
    work = build_priority(tasks, latency, region_index)

    history = []; previous = None; converged = False; last_rel = None
    fallback = removal_dependent = changed = 0
    for pass_no in range(1, args.max_passes + 1):
        fallback, removal_dependent, changed = run_pass(
            core, args.mode, tasks, work, schedule, gpu, ai, latency, region_index, power,
            profile_cache, base_facility, nonai, capacity_gpu, max_it, pue, max_facility,
            c0, g0, grid0, used0, wide["Price"], wide["CarbonIntensity"], max_grid,
        )
        audit, _, _ = core.compute_metrics(gpu, ai, schedule, cfg, wide, base_gpu, base_ai)
        augment_deadline_audit(audit, schedule)
        value = primary(args.mode, audit)
        if previous is not None:
            last_rel = (previous - value) / max(abs(previous), 1.0)
            if last_rel < -1e-9:
                raise RuntimeError(f"第{pass_no}遍主目标恶化：{last_rel:.3e}")
        history.append({
            "mode": args.mode, "start": args.start, "pass": pass_no,
            "primary_objective": value, "relative_improvement": last_rel,
            "cost_cny": audit["cost_cny"], "carbon_tco2": audit["carbon_tco2"],
            "eta_R": audit["eta_R"], "mean_wait_h": audit["mean_wait_h"],
            "p95_wait_h": audit["p95_wait_h"], "max_wait_h": audit["max_wait_h"],
            "migration_rate": audit["migration_rate"], "fallback_count": fallback,
            "changed_placements": changed, "removal_dependent_count": removal_dependent,
            "gpu_violation": audit["max_gpu_hour_violation"],
            "latest_finish_violations": audit["latest_finish_violations"],
        })
        print(json.dumps(history[-1], ensure_ascii=False), flush=True)
        hard_ready = (audit["max_gpu_hour_violation"] <= 1e-7
                      and audit["max_it_violation_mw"] <= 1e-7
                      and audit["max_facility_violation_mw"] <= 1e-7
                      and audit["latest_finish_violations"] == 0
                      and audit["horizon_2406_violations"] == 0
                      and audit["rt_immediate_start_violations"] == 0
                      and audit["latency_violations"] == 0 and fallback == 0)
        if previous is not None and last_rel < args.relative_tol and hard_ready:
            converged = True
            break
        previous = value

    audit, hourly, energy = core.compute_metrics(gpu, ai, schedule, cfg, wide, base_gpu, base_ai)
    augment_deadline_audit(audit, schedule)
    final_grid, final_curt, final_used, final_facility = energy
    balance_base = (wide["AvailableRenewable_MW"] - wide["UsedRenewable_MW"]
                    - wide["RenewableCharge_MW"] - wide["GridSell_MW"] - wide["Curtailment_MW"])
    balance_final = (final_grid + wide["AvailableRenewable_MW"] + wide["DischargePower_MW"]
                     - final_facility - wide["ChargePower_MW"] - wide["GridSell_MW"] - final_curt)
    audit.update({
        "mode": args.mode, "start": args.start, "passes": len(history), "converged": converged,
        "last_relative_primary_improvement": last_rel, "fallback_count_last_pass": fallback,
        "removal_dependent_count_last_pass": removal_dependent,
        "energy_balance_max_residual_baseline_mw": float(np.max(np.abs(balance_base))),
        "energy_balance_max_residual_final_mw": float(np.max(np.abs(balance_final))),
        "max_grid_import_violation_mw": float(np.maximum(final_grid - max_grid[:, None], 0).max()),
        "max_grid_export_violation_mw": float(np.maximum(wide["GridSell_MW"] - max_export[:, None], 0).max()),
    })
    hard_pass = (audit["max_gpu_hour_violation"] <= 1e-7 and audit["max_it_violation_mw"] <= 1e-7
                 and audit["max_facility_violation_mw"] <= 1e-7 and audit["max_grid_import_violation_mw"] <= 1e-7
                 and audit["max_grid_export_violation_mw"] <= 1e-7 and audit["latest_finish_violations"] == 0
                 and audit["horizon_2406_violations"] == 0 and audit["rt_immediate_start_violations"] == 0
                 and audit["latency_violations"] == 0 and audit["min_grid_purchase_mw"] >= -1e-7
                 and audit["min_used_renewable_mw"] >= -1e-7 and audit["min_curtailment_mw"] >= -1e-7
                 and audit["energy_balance_max_residual_final_mw"] <= 1e-3 and fallback == 0)
    audit["hard_constraint_status"] = "PASS" if hard_pass else "FAIL"
    audit["status"] = "PASS" if hard_pass and converged else "FAIL"

    suffix = {"dynamic":"dynamic_marginal","cost":"cost_only","carbon":"carbon_only"}[args.mode]
    wait_by_type = schedule.assign(
        等待时间_h=schedule.StartHour-schedule.ArrivalHour,
        是否迁移=schedule.ExecutionRegion.ne(schedule.SourceRegion),
    ).groupby("TaskType").agg(
        任务数=("TaskID","size"), 迁移任务数=("是否迁移","sum"), 迁移率=("是否迁移","mean"),
        延迟任务数=("等待时间_h",lambda x:int((x>0).sum())), 平均等待_h=("等待时间_h","mean"),
        等待P95_h=("等待时间_h",lambda x:float(x.quantile(.95))), 最大等待_h=("等待时间_h","max")
    ).reset_index()

    schedule.to_csv(core.PROC/f"q2_schedule_{suffix}.csv", index=False, encoding="utf-8-sig")
    hourly.to_csv(core.PROC/f"q2_hourly_energy_{suffix}.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame([audit]).to_csv(core.TAB/f"q2_metrics_{suffix}.csv", index=False, encoding="utf-8-sig")
    wait_by_type.to_csv(core.TAB/f"q2_wait_by_type_{suffix}.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(history).to_csv(core.RES/f"q2_convergence_{suffix}.csv", index=False, encoding="utf-8-sig")
    checks = [
        ("重复完整扫描收敛", converged, 0 if converged else 1),
        ("逐任务LatestFinish", audit["latest_finish_violations"]==0, audit["latest_finish_violations"]),
        ("RT到达即开工", audit["rt_immediate_start_violations"]==0, audit["rt_immediate_start_violations"]),
        ("2406边界", audit["horizon_2406_violations"]==0, audit["horizon_2406_violations"]),
        ("GPU/IT/Facility容量", audit["max_gpu_hour_violation"]<=1e-7 and audit["max_it_violation_mw"]<=1e-7 and audit["max_facility_violation_mw"]<=1e-7, max(audit["max_gpu_hour_violation"],audit["max_it_violation_mw"],audit["max_facility_violation_mw"])),
        ("GridImport/GridExport", audit["max_grid_import_violation_mw"]<=1e-7 and audit["max_grid_export_violation_mw"]<=1e-7, max(audit["max_grid_import_violation_mw"],audit["max_grid_export_violation_mw"])),
        ("SLA", audit["latency_violations"]==0, audit["latency_violations"]),
        ("统一能量平衡", audit["energy_balance_max_residual_final_mw"]<=1e-3, audit["energy_balance_max_residual_final_mw"]),
        ("最终fallback为零", fallback==0, fallback),
    ]
    pd.DataFrame([{"检查项":a,"通过":bool(b),"最大误差":float(c)} for a,b,c in checks]).to_csv(
        core.RES/f"q2_constraint_audit_{suffix}.csv", index=False, encoding="utf-8-sig")
    (core.RES/f"q2_run_summary_{suffix}.json").write_text(json.dumps({
        "status":audit["status"], "model_status":"DRAFT / NEEDS_REVIEW",
        "convergence_protocol":{"start":args.start,"max_passes":args.max_passes,"relative_tol":args.relative_tol},
        "audit":audit,"history":history}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"mode":args.mode,"status":audit["status"],"passes":len(history),"audit":audit}, ensure_ascii=False))


if __name__ == "__main__":
    main()
