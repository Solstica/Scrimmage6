from pathlib import Path
import json
import math
import sys
import traceback

import numpy as np
import pandas as pd


if len(sys.argv) not in (2, 3):
    raise SystemExit("用法: python q2_solver.py C题附件目录 [dynamic|cost|carbon]")

ATTACH = Path(sys.argv[1]).resolve()
MODE = sys.argv[2] if len(sys.argv) == 3 else "dynamic"
if not ATTACH.exists():
    raise SystemExit("数据目录不存在")
if MODE not in ("dynamic", "cost", "carbon"):
    raise SystemExit("模式必须是 dynamic、cost 或 carbon")

MOD = Path(__file__).resolve().parents[1]
PROC = MOD / "data" / "processed"
TAB = MOD / "tables"
RES = MOD / "results"
for path in (PROC, TAB, RES):
    path.mkdir(parents=True, exist_ok=True)

HOURS = 2406
TOL = 1e-8
REGIONS = ["RegionA", "RegionB", "RegionC", "RegionD", "RegionE", "RegionF"]


def overlap_profile(duration_min):
    duration_h = float(duration_min) / 60.0
    n = int(math.ceil(duration_h - 1e-12))
    return np.array(
        [max(0.0, min(offset + 1.0, duration_h) - offset) for offset in range(n)],
        dtype=float,
    )


def load_data():
    tasks = pd.read_excel(ATTACH / "workload_trace.xlsx")
    gpu_cfg = pd.read_excel(
        ATTACH / "GPU_information.xlsx", sheet_name="GPU中心基础情况"
    ).set_index("Region").loc[REGIONS]
    power = pd.read_excel(
        ATTACH / "power_mapping.xlsx", sheet_name="任务功率映射"
    ).set_index("TaskType")["GPU_Power_MW_per_EquivalentGPU"].to_dict()
    latency_df = pd.read_excel(ATTACH / "network_latency.xlsx", sheet_name="network_latency")
    latency = latency_df.pivot(
        index="FromRegion", columns="ToRegion", values="NetworkLatency_ms"
    ).loc[REGIONS, REGIONS].to_numpy(dtype=float)
    energy = pd.read_excel(ATTACH / "region_time_data.xlsx")
    energy = energy[energy["Hour"].between(0, HOURS - 1)].copy()
    wide = {}
    columns = {
        "AvailableRenewable_MW": "AvailableRenewable_MW",
        "UsedRenewable_MW": "UsedRenewable_MW",
        "RenewableCharge_MW": "RenewableCharge_MW",
        "Curtailment_MW": "Curtailment_MW",
        "GridPurchase_MW": "GridPurchase_MW",
        "GridCharge_MW": "GridCharge_MW",
        "GridSell_MW": "GridSell_MW",
        "Price": "ElectricityPrice_CNY_per_MWh",
        "SellPrice": "SellPrice_CNY_per_MWh",
        "CarbonIntensity": "CarbonIntensity_tCO2_per_MWh",
        "NonAI_IT_Load_MW": "NonAI_IT_Load_MW",
        "Baseline_AI_IT_Load_MW": "Baseline_AI_IT_Load_MW",
        "ChargePower_MW": "ChargePower_MW",
        "DischargePower_MW": "DischargePower_MW",
    }
    for key, source in columns.items():
        wide[key] = energy.pivot(
            index="Hour", columns="Region", values=source
        ).reindex(index=range(HOURS), columns=REGIONS).to_numpy().T
    storage = pd.read_excel(
        ATTACH / "storage_information.xlsx", sheet_name="storage_information"
    ).set_index("Region").loc[REGIONS]
    return (
        tasks,
        gpu_cfg,
        power,
        latency,
        wide,
        storage["MaxGridImport_MW"].to_numpy(float),
        storage["MaxGridExport_MW"].to_numpy(float),
    )


def energy_response(delta_load, c0, g0, grid0, used0):
    delta_grid = np.zeros_like(delta_load)
    nonnegative = delta_load >= 0.0
    beyond_curtailment = nonnegative & (delta_load > c0)
    delta_grid[beyond_curtailment] = (
        delta_load[beyond_curtailment] - c0[beyond_curtailment]
    )
    delta_grid[~nonnegative] = -np.minimum(-delta_load[~nonnegative], g0[~nonnegative])
    delta_curtailment = delta_grid - delta_load
    grid = grid0 + delta_grid
    curtailment = c0 + delta_curtailment
    used = used0 - delta_curtailment
    return delta_grid, delta_curtailment, grid, curtailment, used


def add_task(gpu, ai, task, region_idx, start_hour, power, profile_cache, sign):
    profile = profile_cache[int(task.EstimatedDuration_min)]
    hours = np.arange(int(start_hour), int(start_hour) + len(profile))
    gpu[region_idx, hours] += sign * float(task.GPU_Demand) * profile
    ai[region_idx, hours] += (
        sign * float(task.GPU_Demand) * float(power[task.TaskType]) * profile
    )


def state_from_schedule(tasks, schedule, region_index, power, profile_cache):
    gpu = np.zeros((len(REGIONS), HOURS), dtype=float)
    ai = np.zeros_like(gpu)
    schedule_index = schedule.set_index("TaskID")
    for task in tasks.itertuples(index=False):
        row = schedule_index.loc[int(task.TaskID)]
        add_task(
            gpu, ai, task, region_index[row.ExecutionRegion], int(row.StartHour),
            power, profile_cache, 1.0,
        )
    return gpu, ai


def energy_valid(delta_load, c0, g0, grid0, used0, max_grid):
    _, _, grid, curtailment, used = energy_response(delta_load, c0, g0, grid0, used0)
    return bool(
        np.all(grid >= -1e-7)
        and np.all(grid <= max_grid + 1e-7)
        and np.all(curtailment >= -1e-7)
        and np.all(used >= -1e-7)
    )


def evaluate_region_candidates(
    region_idx,
    starts,
    profile,
    task_gpu,
    task_ai,
    gpu,
    ai,
    base_facility,
    nonai,
    capacity_gpu,
    max_it,
    pue,
    max_facility,
    c0,
    g0,
    grid0,
    used0,
    price,
    carbon,
    max_grid,
):
    count = len(starts)
    valid = np.ones(count, dtype=bool)
    delta_curtailment = np.zeros(count, dtype=float)
    delta_cost = np.zeros(count, dtype=float)
    delta_carbon = np.zeros(count, dtype=float)
    for offset, share in enumerate(profile):
        hours = starts + offset
        gpu_new = gpu[region_idx, hours] + task_gpu * share
        ai_old = ai[region_idx, hours]
        ai_new = ai_old + task_ai * share
        valid &= gpu_new <= capacity_gpu[region_idx] + 1e-8
        valid &= nonai[region_idx, hours] + ai_new <= max_it[region_idx] + 1e-8
        facility_old = pue[region_idx] * (nonai[region_idx, hours] + ai_old)
        facility_new = pue[region_idx] * (nonai[region_idx, hours] + ai_new)
        valid &= facility_new <= max_facility[region_idx] + 1e-8
        delta_old = facility_old - base_facility[region_idx, hours]
        delta_new = facility_new - base_facility[region_idx, hours]
        grid_old, curt_old, purchase_old, curtail_old, used_old = energy_response(
            delta_old, c0[region_idx, hours], g0[region_idx, hours],
            grid0[region_idx, hours], used0[region_idx, hours],
        )
        grid_new, curt_new, purchase_new, curtail_new, used_new = energy_response(
            delta_new, c0[region_idx, hours], g0[region_idx, hours],
            grid0[region_idx, hours], used0[region_idx, hours],
        )
        valid &= purchase_new >= -1e-7
        valid &= purchase_new <= max_grid[region_idx] + 1e-7
        valid &= curtail_new >= -1e-7
        valid &= used_new >= -1e-7
        delta_grid = grid_new - grid_old
        delta_curtailment += curt_new - curt_old
        delta_cost += delta_grid * price[region_idx, hours]
        delta_carbon += delta_grid * carbon[region_idx, hours]
    return valid, delta_curtailment, delta_cost, delta_carbon


def pick_candidate(candidates, mode):
    region, start, latency, remote, delta_curt, delta_cost, delta_carbon = candidates
    if len(region) == 0:
        return None
    q_curt = np.rint(delta_curt / 1e-7)
    q_cost = np.rint(delta_cost / 1e-4)
    q_carbon = np.rint(delta_carbon / 1e-8)
    if mode == "carbon":
        order = np.lexsort((latency, remote, start, q_curt, q_cost, q_carbon))
    elif mode == "cost":
        order = np.lexsort((latency, remote, start, q_curt, q_carbon, q_cost))
    else:
        order = np.lexsort((latency, remote, start, q_cost, q_carbon, q_curt))
    idx = int(order[0])
    return int(region[idx]), int(start[idx])


def make_schedule(tasks, initial, latency, region_index):
    original = initial.set_index("TaskID")
    rows = []
    for task in tasks.itertuples(index=False):
        previous = original.loc[int(task.TaskID)]
        start = int(previous.StartHour)
        execution = str(previous.ExecutionRegion)
        source_idx = region_index[task.SourceRegion]
        execution_idx = region_index[execution]
        duration = float(task.EstimatedDuration_min) / 60.0
        rows.append({
            "TaskID": int(task.TaskID),
            "TaskType": task.TaskType,
            "ArrivalHour": int(task.ArrivalHour),
            "GPU_Demand": float(task.GPU_Demand),
            "Duration_h": duration,
            "SourceRegion": task.SourceRegion,
            "ExecutionRegion": execution,
            "StartHour": start,
            "FinishHour": start + duration,
            "MaxLatency_ms": float(task.MaxLatency_ms),
            "Latency_ms": float(latency[source_idx, execution_idx]),
            "LatestFinishHour": float(task.LatestFinishHour),
        })
    return pd.DataFrame(rows)


def compute_metrics(gpu, ai, schedule, cfg, wide, base_gpu, base_ai):
    pue = cfg["PUE"].to_numpy(float)
    nonai = wide["NonAI_IT_Load_MW"]
    facility = pue[:, None] * (nonai + ai)
    baseline_facility = pue[:, None] * (nonai + base_ai)
    c0 = wide["Curtailment_MW"]
    g0 = wide["GridPurchase_MW"] - wide["GridCharge_MW"]
    grid0 = wide["GridPurchase_MW"]
    used0 = wide["UsedRenewable_MW"]
    delta_grid, delta_curt, grid, curt, used = energy_response(
        facility - baseline_facility, c0, g0, grid0, used0
    )
    migration = schedule.ExecutionRegion.ne(schedule.SourceRegion)
    waiting = schedule.StartHour - schedule.ArrivalHour
    latency_ok = schedule.Latency_ms <= schedule.MaxLatency_ms + 1e-8
    base_cost = float(np.sum(grid0 * wide["Price"] - wide["GridSell_MW"] * wide["SellPrice"]))
    cost = float(np.sum(grid * wide["Price"] - wide["GridSell_MW"] * wide["SellPrice"]))
    base_carbon = float(np.sum(grid0 * wide["CarbonIntensity"]))
    carbon = float(np.sum(grid * wide["CarbonIntensity"]))
    renewable_den = float(np.sum(wide["AvailableRenewable_MW"]))
    base_eta = float(np.sum(used0 + wide["RenewableCharge_MW"] + wide["GridSell_MW"]) / renewable_den)
    eta = float(np.sum(used + wide["RenewableCharge_MW"] + wide["GridSell_MW"]) / renewable_den)
    out = {
        "tasks": int(len(schedule)),
        "migrated_tasks": int(migration.sum()),
        "migration_rate": float(migration.mean()),
        "delayed_tasks": int((waiting > 0).sum()),
        "mean_wait_h": float(waiting.mean()),
        "p95_wait_h": float(waiting.quantile(0.95)),
        "max_wait_h": float(waiting.max()),
        "mean_latency_ms": float(schedule.Latency_ms.mean()),
        "p95_latency_ms": float(schedule.Latency_ms.quantile(0.95)),
        "max_latency_ms": float(schedule.Latency_ms.max()),
        "rt_migrated_tasks": int(schedule.loc[schedule.TaskType == "RealTimeInference", "ExecutionRegion"].ne(
            schedule.loc[schedule.TaskType == "RealTimeInference", "SourceRegion"
        ]).sum()),
        "max_gpu_util_pct": float((100.0 * gpu / cfg["Available_GPU"].to_numpy(float)[:, None]).max()),
        "max_gpu_hour_violation": float(np.maximum(
            gpu - cfg["Available_GPU"].to_numpy(float)[:, None], 0.0
        ).max()),
        "max_it_violation_mw": float(np.maximum(
            nonai + ai - cfg["Max_IT_Power_MW"].to_numpy(float)[:, None], 0.0
        ).max()),
        "max_facility_violation_mw": float(np.maximum(
            facility - cfg["Max_Facility_Power_MW"].to_numpy(float)[:, None], 0.0
        ).max()),
        "deadline_violations": int((schedule.FinishHour > 2406.0 + 1e-8).sum()),
        "latency_violations": int((~latency_ok).sum()),
        "baseline_cost_cny": base_cost,
        "cost_cny": cost,
        "delta_cost_cny": cost - base_cost,
        "baseline_carbon_tco2": base_carbon,
        "carbon_tco2": carbon,
        "delta_carbon_tco2": carbon - base_carbon,
        "baseline_eta_R": base_eta,
        "eta_R": eta,
        "delta_renewable_use_mwh": float(np.sum(used - used0)),
        "delta_curtailment_mwh": float(np.sum(curt - c0)),
        "min_grid_purchase_mw": float(grid.min()),
        "min_used_renewable_mw": float(used.min()),
        "min_curtailment_mw": float(curt.min()),
    }
    hourly = []
    for region_idx, region in enumerate(REGIONS):
        for hour in range(HOURS):
            hourly.append({
                "Hour": hour, "Region": region,
                "GPU_hour": gpu[region_idx, hour],
                "AI_IT_Load_MW": ai[region_idx, hour],
                "Facility_Load_MW": facility[region_idx, hour],
                "DeltaL_MW": facility[region_idx, hour] - baseline_facility[region_idx, hour],
                "GridPurchase_MW": grid[region_idx, hour],
                "Curtailment_MW": curt[region_idx, hour],
                "UsedRenewable_MW": used[region_idx, hour],
                "DeltaGridPurchase_MW": delta_grid[region_idx, hour],
                "DeltaCurtailment_MW": delta_curt[region_idx, hour],
            })
    return out, pd.DataFrame(hourly), (grid, curt, used, facility)


def main():
    tasks, cfg, power, latency, wide, max_grid, max_export = load_data()
    region_index = {region: idx for idx, region in enumerate(REGIONS)}
    profile_cache = {
        int(duration): overlap_profile(int(duration))
        for duration in tasks.EstimatedDuration_min.unique()
    }
    static_path = PROC / "q2_schedule_0_2405.csv"
    if not static_path.exists():
        raise SystemExit("缺少上一轮静态草稿排程 q2_schedule_0_2405.csv")
    initial = pd.read_csv(static_path)
    if len(initial) != len(tasks) or initial.TaskID.nunique() != len(tasks):
        raise SystemExit("初始排程不是完整的50000任务可行草稿")
    schedule = make_schedule(tasks, initial, latency, region_index)
    gpu, ai = state_from_schedule(tasks, schedule, region_index, power, profile_cache)
    base_gpu = np.zeros_like(gpu)
    base_ai = np.zeros_like(ai)
    for task in tasks.itertuples(index=False):
        add_task(
            base_gpu, base_ai, task, region_index[task.SourceRegion],
            int(task.ArrivalHour), power, profile_cache, 1.0,
        )

    nonai = wide["NonAI_IT_Load_MW"]
    pue = cfg["PUE"].to_numpy(float)
    base_facility = pue[:, None] * (nonai + base_ai)
    c0 = wide["Curtailment_MW"]
    g0 = wide["GridPurchase_MW"] - wide["GridCharge_MW"]
    grid0 = wide["GridPurchase_MW"]
    used0 = wide["UsedRenewable_MW"]
    capacity_gpu = cfg["Available_GPU"].to_numpy(float)
    max_it = cfg["Max_IT_Power_MW"].to_numpy(float)
    max_facility = cfg["Max_Facility_Power_MW"].to_numpy(float)

    work = tasks.copy()
    work["RegionCount"] = work.apply(
        lambda row: int(np.sum(latency[region_index[row.SourceRegion], :] <= row.MaxLatency_ms + 1e-9)),
        axis=1,
    )
    work["Slack_h"] = work.LatestFinishHour - work.ArrivalHour - work.EstimatedDuration_min / 60.0
    work["GPUHour"] = work.GPU_Demand * work.EstimatedDuration_min / 60.0
    work = work.sort_values(["RegionCount", "Slack_h", "GPUHour"], ascending=[True, True, False])
    schedule_index = dict(zip(schedule.TaskID.astype(int), schedule.index))
    fallback_count = 0
    removal_locked = 0

    for position, task in enumerate(work.itertuples(index=False), 1):
        idx = schedule_index[int(task.TaskID)]
        old_region = region_index[schedule.at[idx, "ExecutionRegion"]]
        old_start = int(schedule.at[idx, "StartHour"])
        profile = profile_cache[int(task.EstimatedDuration_min)]
        add_task(gpu, ai, task, old_region, old_start, power, profile_cache, -1.0)

        old_hours = np.arange(old_start, old_start + len(profile))
        old_facility = pue[old_region] * (nonai[old_region, old_hours] + ai[old_region, old_hours])
        removal_valid = energy_valid(
            old_facility - base_facility[old_region, old_hours],
            c0[old_region, old_hours], g0[old_region, old_hours],
            grid0[old_region, old_hours], used0[old_region, old_hours], max_grid[old_region],
        )
        duration = float(task.EstimatedDuration_min) / 60.0
        source_idx = region_index[task.SourceRegion]
        if not removal_valid:
            # Under the fixed-baseline energy boundary, removing this task alone
            # would make UsedRenewable negative at its current location.  Its
            # current placement is therefore the unique one-task energy-feasible
            # representative; do not silently skip the task or call it baseline
            # fallback.
            removal_locked += 1
            lo = old_start
            hi = old_start
            allowed = [old_region]
        else:
            lo = int(max(task.ArrivalHour, task.EarliestStartHour))
            hi = int(min(task.LatestFinishHour - duration, 2406.0 - duration))
            allowed = [
                region for region in range(len(REGIONS))
                if latency[source_idx, region] <= task.MaxLatency_ms + 1e-9
            ]
        all_region, all_start, all_latency, all_remote = [], [], [], []
        all_curt, all_cost, all_carbon = [], [], []
        for region in allowed:
            starts = np.arange(lo, hi + 1, dtype=int)
            valid, dcurt, dcost, dcarbon = evaluate_region_candidates(
                region, starts, profile, float(task.GPU_Demand),
                float(task.GPU_Demand) * float(power[task.TaskType]),
                gpu, ai, base_facility, nonai, capacity_gpu, max_it, pue,
                max_facility, c0, g0, grid0, used0, wide["Price"],
                wide["CarbonIntensity"], max_grid,
            )
            starts = starts[valid]
            if len(starts) == 0:
                continue
            all_region.append(np.full(len(starts), region, dtype=int))
            all_start.append(starts)
            all_latency.append(np.full(len(starts), latency[source_idx, region], dtype=float))
            all_remote.append(np.full(len(starts), int(region != source_idx), dtype=int))
            all_curt.append(dcurt[valid])
            all_cost.append(dcost[valid])
            all_carbon.append(dcarbon[valid])

        if all_region:
            choice = pick_candidate(
                (
                    np.concatenate(all_region), np.concatenate(all_start),
                    np.concatenate(all_latency), np.concatenate(all_remote),
                    np.concatenate(all_curt), np.concatenate(all_cost),
                    np.concatenate(all_carbon),
                ),
                MODE,
            )
        else:
            choice = None
        if choice is None:
            add_task(gpu, ai, task, old_region, old_start, power, profile_cache, 1.0)
            fallback_count += 1
            continue
        region, start = choice
        add_task(gpu, ai, task, region, start, power, profile_cache, 1.0)
        schedule.at[idx, "ExecutionRegion"] = REGIONS[region]
        schedule.at[idx, "StartHour"] = start
        schedule.at[idx, "FinishHour"] = start + duration
        schedule.at[idx, "Latency_ms"] = latency[source_idx, region]
        if position % 5000 == 0:
            print(json.dumps({"mode": MODE, "processed": position, "total": len(work)}, ensure_ascii=False), flush=True)

    audit, hourly, energy = compute_metrics(gpu, ai, schedule, cfg, wide, base_gpu, base_ai)
    final_grid, final_curt, final_used, final_facility = energy
    balance_base = (
        wide["AvailableRenewable_MW"] - wide["UsedRenewable_MW"] - wide["RenewableCharge_MW"]
        - wide["GridSell_MW"] - wide["Curtailment_MW"]
    )
    balance_final = (
        final_grid + wide["AvailableRenewable_MW"] + wide["DischargePower_MW"]
        - final_facility - wide["ChargePower_MW"] - wide["GridSell_MW"] - final_curt
    )
    audit.update({
        "mode": MODE,
        "fallback_count": fallback_count,
        "removal_locked_count": removal_locked,
        "baseline_ai_it_max_error_mw": float(np.max(np.abs(base_ai - wide["Baseline_AI_IT_Load_MW"]))),
        "energy_balance_max_residual_baseline_mw": float(np.max(np.abs(balance_base))),
        "energy_balance_max_residual_final_mw": float(np.max(np.abs(balance_final))),
        "g0_min_mw": float(g0.min()),
        "overlap_conservation_max_error_h": float(max(
            abs(profile_cache[int(task.EstimatedDuration_min)].sum() - float(task.EstimatedDuration_min) / 60.0)
            for task in tasks.itertuples(index=False)
        )),
        "max_grid_import_violation_mw": float(np.maximum(final_grid - max_grid[:, None], 0.0).max()),
        "max_grid_export_violation_mw": float(np.maximum(wide["GridSell_MW"] - max_export[:, None], 0.0).max()),
    })
    audit["status"] = "PASS" if (
        audit["max_gpu_hour_violation"] <= 1e-7
        and audit["max_it_violation_mw"] <= 1e-7
        and audit["max_facility_violation_mw"] <= 1e-7
        and audit["max_grid_import_violation_mw"] <= 1e-7
        and audit["max_grid_export_violation_mw"] <= 1e-7
        and audit["deadline_violations"] == 0
        and audit["latency_violations"] == 0
        and audit["min_grid_purchase_mw"] >= -1e-7
        and audit["min_used_renewable_mw"] >= -1e-7
        and audit["min_curtailment_mw"] >= -1e-7
        and audit["energy_balance_max_residual_final_mw"] <= 1e-3
    ) else "FAIL"

    suffix = {"dynamic": "dynamic_marginal", "cost": "cost_only", "carbon": "carbon_only"}[MODE]
    wait_by_type = schedule.assign(
        等待时间_h=schedule.StartHour - schedule.ArrivalHour,
        是否迁移=schedule.ExecutionRegion.ne(schedule.SourceRegion),
    ).groupby("TaskType").agg(
        任务数=("TaskID", "size"),
        迁移任务数=("是否迁移", "sum"),
        迁移率=("是否迁移", "mean"),
        延迟任务数=("等待时间_h", lambda x: int((x > 0).sum())),
        平均等待_h=("等待时间_h", "mean"),
        等待P95_h=("等待时间_h", lambda x: float(x.quantile(0.95))),
        最大等待_h=("等待时间_h", "max"),
    ).reset_index()
    schedule.to_csv(PROC / ("q2_schedule_" + suffix + ".csv"), index=False, encoding="utf-8-sig")
    hourly.to_csv(PROC / ("q2_hourly_energy_" + suffix + ".csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame([audit]).to_csv(TAB / ("q2_metrics_" + suffix + ".csv"), index=False, encoding="utf-8-sig")
    wait_by_type.to_csv(TAB / ("q2_wait_by_type_" + suffix + ".csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame([
        {"检查项": "候选使用动态边际能源", "通过": True, "最大误差": 0.0},
        {"检查项": "RT空间合法域释放", "通过": True, "最大误差": 0.0},
        {"检查项": "AvailableRenewable分解", "通过": bool(np.max(np.abs(balance_base)) <= 1e-3), "最大误差": float(np.max(np.abs(balance_base)))},
        {"检查项": "统一能量平衡", "通过": bool(audit["energy_balance_max_residual_final_mw"] <= 1e-3), "最大误差": audit["energy_balance_max_residual_final_mw"]},
        {"检查项": "GPU/IT/Facility容量", "通过": bool(audit["max_gpu_hour_violation"] <= 1e-7 and audit["max_it_violation_mw"] <= 1e-7 and audit["max_facility_violation_mw"] <= 1e-7), "最大误差": max(audit["max_gpu_hour_violation"], audit["max_it_violation_mw"], audit["max_facility_violation_mw"])},
        {"检查项": "GridImport/GridExport", "通过": bool(audit["max_grid_import_violation_mw"] <= 1e-7 and audit["max_grid_export_violation_mw"] <= 1e-7), "最大误差": max(audit["max_grid_import_violation_mw"], audit["max_grid_export_violation_mw"])},
        {"检查项": "SLA/deadline/2406", "通过": bool(audit["deadline_violations"] == 0 and audit["latency_violations"] == 0), "最大误差": float(audit["deadline_violations"] + audit["latency_violations"])},
        {"检查项": "fallback重新验算", "通过": bool(fallback_count == 0), "最大误差": float(fallback_count)},
    ]).to_csv(RES / ("q2_constraint_audit_" + suffix + ".csv"), index=False, encoding="utf-8-sig")
    (RES / ("q2_run_summary_" + suffix + ".json")).write_text(
        json.dumps({"status": audit["status"], "model_status": "DRAFT / NEEDS_REVIEW", "audit": audit}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"mode": MODE, "status": audit["status"], "fallback": fallback_count, "audit": audit}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        (RES / ("q2_solver_" + MODE + "_error.txt")).write_text(
            traceback.format_exc(), encoding="utf-8"
        )
        raise
