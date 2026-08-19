#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""renew_down_80 能源一体化 LP 列生成与整数认证。"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
from scipy.optimize import linprog
from scipy.sparse import coo_matrix, csr_matrix, hstack, vstack

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q4_qos_refinement as qos  # noqa: E402
import q4_region_multicut_scenario as region_solver  # noqa: E402


VARS = ("u", "qR", "qG", "d", "gL", "s", "w", "E")
POS = {name: i for i, name in enumerate(VARS)}
FIELDS = (
    "轮次", "活动列数", "LP目标值_CNY", "真实可行上界_CNY", "UB减LB_CNY",
    "最小缺失列约化成本", "新增列数", "负约化任务区域数", "当前RSS_GiB", "累计分钟",
)


def eidx(n: int, region: int, hour: int, name: str) -> int:
    return n + (region * qos.H_ENERGY + hour) * len(VARS) + POS[name]


def solve_lp(pool, data, gpu_row, it_row, rhs) -> dict:
    n = len(pool)
    ne = qos.R * qos.H_ENERGY * len(VARS)
    nt = n + ne
    assign = qos.assignment_matrix(pool, len(data.task))
    resource = qos.resource_matrix(pool, data, gpu_row, it_row, len(rhs))
    fixed = qos.fixed_facility_load(data)

    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    be: list[float] = []
    load_rows = np.empty((qos.R, qos.H_ENERGY), dtype=np.int32)
    row = 0
    ti, rr, ss = pool.arrays()
    for r in range(qos.R):
        st = data.storage.iloc[r]
        ce = float(st.ChargeEfficiency)
        de = float(st.DischargeEfficiency)
        rbase = row
        for h in range(qos.H_ENERGY):
            for name in ("u", "qR", "s", "w"):
                rows.append(row); cols.append(eidx(n, r, h, name)); vals.append(1.0)
            be.append(float(data.renew[r, h])); row += 1

            for name in ("u", "d", "gL"):
                rows.append(row); cols.append(eidx(n, r, h, name)); vals.append(1.0)
            be.append(float(fixed[r, h]))
            load_rows[r, h] = len(data.task) + row
            row += 1

            rows.append(row); cols.append(eidx(n, r, h, "E")); vals.append(1.0)
            if h:
                rows.append(row); cols.append(eidx(n, r, h - 1, "E")); vals.append(-1.0)
                be.append(0.0)
            else:
                be.append(float(st.InitialSOC_MWh))
            rows.append(row); cols.append(eidx(n, r, h, "qR")); vals.append(-ce)
            rows.append(row); cols.append(eidx(n, r, h, "qG")); vals.append(-ce)
            rows.append(row); cols.append(eidx(n, r, h, "d")); vals.append(1.0 / de)
            row += 1

        for j in np.flatnonzero(rr == r):
            prof = qos.overlap_profile(data.duration[int(ti[j])])
            scale = data.pue[r] * data.gpu[int(ti[j])] * data.alpha[int(ti[j])]
            for k, weight in enumerate(prof):
                hour = int(ss[j]) + k
                if hour < qos.H_TASK and hour < qos.H_ENERGY:
                    rows.append(rbase + 3 * hour + 1)
                    cols.append(int(j))
                    vals.append(-float(scale * weight))

    energy_eq = coo_matrix(
        (np.asarray(vals), (np.asarray(rows), np.asarray(cols))), shape=(row, nt)
    ).tocsr()
    aeq = vstack(
        [hstack([assign, csr_matrix((assign.shape[0], ne))], format="csr"), energy_eq],
        format="csr",
    )
    beq = np.r_[np.ones(assign.shape[0]), np.asarray(be)]

    ur: list[int] = []
    uc: list[int] = []
    uv: list[float] = []
    ub: list[float] = []
    row = 0
    for r in range(qos.R):
        st = data.storage.iloc[r]
        for h in range(qos.H_ENERGY):
            ur.extend((row, row)); uc.extend((eidx(n, r, h, "qR"), eidx(n, r, h, "qG")))
            uv.extend((1.0, 1.0)); ub.append(float(st.MaxChargePower_MW)); row += 1
            ur.extend((row, row)); uc.extend((eidx(n, r, h, "gL"), eidx(n, r, h, "qG")))
            uv.extend((1.0, 1.0)); ub.append(float(st.MaxGridImport_MW)); row += 1
    energy_ub = coo_matrix(
        (np.asarray(uv), (np.asarray(ur), np.asarray(uc))), shape=(row, nt)
    ).tocsr()
    aub = vstack(
        [hstack([resource, csr_matrix((resource.shape[0], ne))], format="csr"), energy_ub],
        format="csr",
    )
    bub = np.r_[rhs, np.asarray(ub)]

    c = np.zeros(nt)
    lb = np.zeros(nt)
    up = np.full(nt, np.inf)
    up[:n] = 1.0
    for r in range(qos.R):
        st = data.storage.iloc[r]
        for h in range(qos.H_ENERGY):
            c[eidx(n, r, h, "gL")] = data.price[r, h]
            c[eidx(n, r, h, "qG")] = data.price[r, h]
            c[eidx(n, r, h, "s")] = -data.sell_price[r, h]
            up[eidx(n, r, h, "d")] = float(st.MaxDischargePower_MW)
            up[eidx(n, r, h, "s")] = min(float(st.SellLimit_MW), float(st.MaxGridExport_MW))
            lb[eidx(n, r, h, "E")] = float(st.MinSOC_MWh)
            up[eidx(n, r, h, "E")] = float(st.StorageCapacity_MWh)
        lb[eidx(n, r, qos.H_ENERGY - 1, "E")] = max(
            lb[eidx(n, r, qos.H_ENERGY - 1, "E")], float(st.InitialSOC_MWh)
        )
    result = linprog(
        c, A_ub=aub, b_ub=bub, A_eq=aeq, b_eq=beq,
        bounds=list(zip(lb, up)), method="highs",
    )
    if not result.success:
        raise RuntimeError("能源一体化 RMP LP 失败：" + result.message)
    eq_dual = np.asarray(result.eqlin.marginals)
    ub_dual = np.asarray(result.ineqlin.marginals)
    return {
        "x": np.asarray(result.x[:n]),
        "objective": float(result.fun),
        "assignment_dual": eq_dual[:len(data.task)],
        "resource_dual": ub_dual[:len(rhs)],
        "load_dual": eq_dual[load_rows],
    }


def price(pool, data, gpu_row, it_row, resource_dual, assignment_dual, load_dual,
          tol: float, columns_per_task: int) -> tuple[list[tuple[int, int, int, float]], float, int]:
    profiles = {}
    examples = {
        int(task_type): int(np.flatnonzero(data.type_idx == task_type)[0])
        for task_type in np.unique(data.type_idx)
    }
    for task_type, duration in set(zip(data.type_idx.tolist(), data.duration.tolist())):
        prof = qos.overlap_profile(duration)
        alpha = data.alpha[examples[int(task_type)]]
        for region in range(qos.R):
            hourly = np.zeros(qos.H_TASK)
            for hour in range(qos.H_TASK):
                gi = int(gpu_row[region, hour])
                ii = int(it_row[region, hour])
                if gi >= 0:
                    hourly[hour] += -resource_dual[gi]
                if ii >= 0:
                    hourly[hour] += -resource_dual[ii] * alpha
                hourly[hour] += load_dual[region, hour] * data.pue[region] * alpha
            profiles[(int(task_type), region, int(round(duration * 60)))] = np.convolve(
                hourly, prof[::-1], mode="valid"
            )
    active = qos.active_starts(pool)
    task_types = data.task["TaskType"].astype(str).to_numpy()
    additions = []
    minimum = math.inf
    negative = 0
    for task in range(len(data.task)):
        start0 = int(data.arrival[task])
        end = start0 if task_types[task] == "RealTimeInference" else qos.legal_last_start(data, task)
        candidates = []
        for region in np.flatnonzero(data.legal[task]):
            scores = data.gpu[task] * profiles[
                (int(data.type_idx[task]), int(region), int(round(data.duration[task] * 60)))
            ][start0:end + 1]
            found = qos.best_missing(scores, start0, active.get((task, int(region)), set()))
            if found is None:
                continue
            score, start = found
            reduced = float(score - assignment_dual[task])
            minimum = min(minimum, reduced)
            if reduced < -tol:
                negative += 1
                candidates.append((reduced, int(region), int(start)))
        candidates.sort()
        additions.extend(
            (task, region, start, reduced)
            for reduced, region, start in candidates[:columns_per_task]
        )
    additions.sort(key=lambda item: item[3])
    return additions, 0.0 if not np.isfinite(minimum) else float(minimum), negative


def canonical_candidate(pool, data, final_dir, gpu_row, it_row, rhs, latency) -> tuple[np.ndarray, dict, dict]:
    schedule = pd.read_csv(final_dir / "q4_字典序最终排程.csv")
    task_index = {int(v): i for i, v in enumerate(data.task.TaskID.to_numpy())}
    region_index = {name: i for i, name in enumerate(qos.REGIONS)}
    index = {qos.ColumnPool.key(t, r, s): j for j, (t, r, s) in enumerate(zip(*pool.arrays()))}
    x = np.zeros(len(pool))
    for row in schedule.itertuples(index=False):
        key = qos.ColumnPool.key(task_index[int(row.TaskID)], region_index[str(row.目标区域)], int(row.开工小时))
        if key not in index:
            raise RuntimeError("canonical 排程列不在热启动 final-pool")
        x[index[key]] = 1.0
    energy = qos.energy_lp(qos.facility_load(pool, data, x), data)
    _, audit = qos.audit_solution(pool, data, x, gpu_row, it_row, rhs, latency, energy)
    return x, energy, audit


def save_pool(path: Path, pool) -> None:
    task, region, start = pool.arrays()
    np.savez_compressed(path, task=task, region=region, start=start)


def append_metric(path: Path, row: dict) -> None:
    exists = path.is_file()
    with path.open("a", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def run(args) -> int:
    base = args.attachment_dir.resolve()
    final_dir = args.canonical_final_dir.resolve()
    suffix = "full_pool" if args.task_limit is None else f"{args.task_limit}task"
    out = args.output_dir.resolve() / f"renew_down_80_extensive_cg_{suffix}"
    attachment = out / "attachment"
    out.mkdir(parents=True, exist_ok=True)
    region_solver.copy_scenario_attachment(base, attachment, args.task_limit)
    data, pool, _, _ = region_solver.load_hot_pool(attachment, final_dir, args.task_limit)
    gpu_row, it_row, rhs, _ = qos.make_presolve_rows(data)
    latency = qos.read_latency(attachment)
    _, upper_energy, upper_audit = canonical_candidate(
        pool, data, final_dir, gpu_row, it_row, rhs, latency
    )
    upper = float(upper_energy["cost"])
    metrics = out / "q4_extensive_cg_metrics.csv"
    started = time.time()
    process = psutil.Process()
    for iteration in range(1, args.max_iter + 1):
        lp = solve_lp(pool, data, gpu_row, it_row, rhs)
        additions, min_rc, negative = price(
            pool, data, gpu_row, it_row, lp["resource_dual"], lp["assignment_dual"],
            lp["load_dual"], args.price_tol, args.columns_per_task,
        )
        added = sum(pool.add(task, region, start) for task, region, start, _ in additions)
        row = {
            "轮次": iteration, "活动列数": len(pool), "LP目标值_CNY": lp["objective"],
            "真实可行上界_CNY": upper, "UB减LB_CNY": upper - lp["objective"],
            "最小缺失列约化成本": min_rc, "新增列数": added,
            "负约化任务区域数": negative,
            "当前RSS_GiB": process.memory_info().rss / 1024 ** 3,
            "累计分钟": (time.time() - started) / 60,
        }
        append_metric(metrics, row)
        save_pool(out / "column_pool.npz", pool)
        checkpoint = {"状态": "RUNNING", "模型": "extensive_lp_cg_v1", "最新": row}
        (out / "checkpoint.json").write_text(
            json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(
            f"[第{iteration}轮] LP={lp['objective']:.6f} | UB-LB={upper-lp['objective']:.6f} | "
            f"rc={min_rc:.6g} | 新增列={added} | 活动列={len(pool)} | RSS={row['当前RSS_GiB']:.2f}GiB",
            flush=True,
        )
        if not added and min_rc >= -args.price_tol:
            summary = {
                "状态": "ROOT_LP_CLOSED", "模型": "extensive_lp_cg_v1",
                "任务数": len(data.task), "完整域LP下界_CNY": lp["objective"],
                "canonical真实可行上界_CNY": upper,
                "UB减LB_CNY": upper - lp["objective"], "活动列数": len(pool),
                "完整域最小约化成本": min_rc, "canonical硬约束审计": upper_audit,
                "运行分钟": (time.time() - started) / 60,
                "全局整数最优已证明": upper - lp["objective"] <= args.cost_tol,
            }
            (out / "scenario_summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
            return 0
    return 2


def main() -> None:
    parser = argparse.ArgumentParser(description="renew_down_80 能源一体化LP列生成")
    parser.add_argument("--attachment-dir", type=Path, default=qos.DEFAULT_ATTACH)
    parser.add_argument("--canonical-final-dir", type=Path, default=HERE.parent / "results" / "qos_final_recertification")
    parser.add_argument("--output-dir", type=Path, default=HERE.parent / "results" / "formal_scenarios")
    parser.add_argument("--task-limit", type=int, choices=(100, 500, 5000), default=None)
    parser.add_argument("--max-iter", type=int, default=100)
    parser.add_argument("--columns-per-task", type=int, default=1)
    parser.add_argument("--price-tol", type=float, default=1e-7)
    parser.add_argument("--cost-tol", type=float, default=1e-3)
    raise SystemExit(run(parser.parse_args()))


if __name__ == "__main__":
    main()
