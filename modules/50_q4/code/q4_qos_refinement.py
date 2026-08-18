#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q4 等成本字典序完整域列生成。

先在真实能源成本上界内最小化总等待，再保持成本和等待上界最小化
总网络时延。两个阶段均重新扫描全部合法区域和开工时刻，并在每次
新增区域 Benders cut 后重新定价。能源 recourse 按六个区域分别维护
theta 和 cuts，输出始终保持 DRAFT，整数全局最优性只有 branch-and-price
证明后才能升级。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from itertools import count
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
from scipy.optimize import Bounds, LinearConstraint, linprog, milp
from scipy.sparse import coo_matrix, csr_matrix, hstack, vstack
from tqdm.auto import tqdm

from q4_full_solver import (
    DEFAULT_ATTACH,
    DEFAULT_OUT,
    H_ENERGY,
    H_TASK,
    R,
    REGIONS,
    ColumnPool,
    Cut,
    CutMatrixCache,
    assignment_matrix,
    cut_matrix,
    energy_lp,
    facility_load,
    fixed_facility_load,
    legal_last_start,
    load_solver_state,
    make_presolve_rows,
    overlap_profile,
    read_data,
    resource_matrix,
)


MODEL_VERSION = "region_multicut_v1"
DEFAULT_RESULT = Path(__file__).resolve().parents[1] / "results" / "qos_refinement_multicut"
LATENCY_INCUMBENT_JSON = "q4_latency_feasible_incumbent.json"
LATENCY_INCUMBENT_CSV = "q4_latency_feasible_incumbent.csv"
LATENCY_CERTIFICATE_CSV = "q4_latency_integer_certificate.csv"
WAIT_RECOVERY_JSON = "q4_wait_incumbent_recovery.json"
# 该值来自已验证的旧版 restricted-integer Wait 端点；仅用于恢复丢失的 incumbent，
# 最终仍由 final-pool Cost -> Wait -> Latency 再认证重新计算。
RECOVERY_WAIT_ANCHOR_H = 32.0
METRIC_FIELDS = (
    "阶段", "轮次", "事件", "活动列数", "Benders切数", "LP目标值",
    "theta_CNY", "真实能源成本_CNY", "Benders违反_CNY", "最大区域违反_CNY",
    "theta_A_CNY", "theta_B_CNY", "theta_C_CNY", "theta_D_CNY", "theta_E_CNY", "theta_F_CNY",
    "真实能源成本_A_CNY", "真实能源成本_B_CNY", "真实能源成本_C_CNY",
    "真实能源成本_D_CNY", "真实能源成本_E_CNY", "真实能源成本_F_CNY",
    "区域违反_A_CNY", "区域违反_B_CNY", "区域违反_C_CNY",
    "区域违反_D_CNY", "区域违反_E_CNY", "区域违反_F_CNY",
    "新增列数",
    "最小缺失列约化成本", "根节点闭合", "MIP状态", "MIP目标值",
    "当前RSS_GiB", "累计分钟",
)
EXTENDED_METRIC_FIELDS = METRIC_FIELDS + (
    "主导违反区域", "LP界", "MIP Gap", "阶段运行秒", "峰值RSS_GiB",
    "可行Latency上界_ms", "Latency下界_ms", "Latency相对Gap", "成本上界违反_CNY",
)
LATENCY_CERTIFICATE_FIELDS = (
    "轮次", "活动列数", "Benders切数", "LP最小缺失列约化成本",
    "LP最大区域违反_CNY", "restricted_MIP_Latency_ms", "真实能源成本_CNY",
    "成本上界违反_CNY", "RegionE违反_CNY", "RegionF违反_CNY",
    "可行Latency上界_ms", "Latency下界_ms", "Latency相对Gap", "事件",
)


@dataclass
class StageSpec:
    name: str
    objective: str
    cost_cap: float | None
    wait_cap: float | None = None


@dataclass
class StageOutcome:
    x: np.ndarray
    energy: dict
    objective: float
    lp_bound: float
    mip_gap: float | None
    iterations: int
    added_columns: int
    min_reduced_cost: float
    mip_objective: float
    final_max_region_violation: float
    benders_cuts: int
    runtime_s: float
    peak_rss_gib: float


class StageStopped(RuntimeError):
    pass


def fmt_time(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remain = divmod(total, 3600)
    minutes, secs = divmod(remain, 60)
    if hours:
        return f"{hours:d}小时{minutes:02d}分{secs:02d}秒"
    return f"{minutes:d}分{secs:02d}秒"


def use_bar(args) -> bool:
    mode = getattr(args, "progress_mode", "auto")
    if mode == "bar":
        return True
    if mode == "plain":
        return False
    return bool(sys.stderr.isatty())


def stage_ui(spec: StageSpec, start_iter: int, args) -> None:
    print("\n" + "=" * 76, flush=True)
    print(f"[阶段开始] {spec.name} | 下一轮={start_iter + 1} | 目标={spec.objective}", flush=True)
    print(
        "[完成条件] 1/5 LP与Benders一致；2/5 完整合法域无负约化成本；"
        "3/5 整数MIP完成；4/5 真实Energy复核；5/5 Cost/Wait硬上界。",
        flush=True,
    )
    print(
        "[当前结论] 上述五项全部显示“通过”，只代表本阶段完成；"
        "正式可结束还需 final recertification 至少两个完整 sweep 锚点稳定并通过硬约束审计。",
        flush=True,
    )
    if getattr(args, "max_stage_iter", 0) == 0:
        print("[运行上限] 本阶段不限轮数，将持续到真实闭合或安全门槛触发。", flush=True)
    else:
        print(f"[运行上限] 本阶段累计最多 {args.max_stage_iter} 轮。", flush=True)


def round_ui(row: dict, args) -> None:
    iteration = int(row["轮次"])
    event = str(row["事件"])
    vmax = float(row["最大区域违反_CNY"])
    region = str(row["主导违反区域"])
    if event == "added_region_benders_cuts":
        print(
            f"[第{iteration}轮][1/5 LP与Benders] 未通过 | 最大区域违反={vmax:.6g} CNY "
            f"大于容差={args.benders_tol_cny:.6g}，主导区域={region}，cuts={row['Benders切数']}；继续迭代。",
            flush=True,
        )
        return
    min_rc = float(row["最小缺失列约化成本"])
    if event == "added_columns":
        print(
            f"[第{iteration}轮][1/5 LP与Benders] 通过 | 最大区域违反={vmax:.6g} CNY；"
            f"[2/5 完整域定价] 未通过 | 最小约化成本={min_rc:.6g}，"
            f"新增列={row['新增列数']}，活动列={row['活动列数']}；继续迭代。",
            flush=True,
        )
        return
    print(
        f"[第{iteration}轮][1/5 LP与Benders] 通过 | 最大区域违反={vmax:.6g} CNY；"
        f"[2/5 完整域定价] 通过 | 最小约化成本={min_rc:.6g}，"
        f"阈值不得低于={-args.price_tol:.6g}。",
        flush=True,
    )


def mip_wait(label: str, solve, process: psutil.Process, interval: float):
    if interval <= 0:
        return solve()
    stop = threading.Event()
    started = time.time()
    cpu0 = sum(process.cpu_times()[:2])

    def report() -> None:
        while not stop.wait(interval):
            elapsed = time.time() - started
            cpu_used = max(0.0, sum(process.cpu_times()[:2]) - cpu0)
            rss = process.memory_info().rss / 1024 ** 3
            print(
                f"[MIP心跳] {label} | 已运行={fmt_time(elapsed)} | "
                f"新增CPU时间={fmt_time(cpu_used)} | RSS={rss:.2f} GiB | "
                "HiGHS仍在分支定界；出现本行表示主程序未失联，但不代表已经收敛。",
                flush=True,
            )

    worker = threading.Thread(target=report, name="q4-mip-heartbeat", daemon=True)
    worker.start()
    try:
        return solve()
    finally:
        stop.set()
        worker.join(timeout=1.0)


def use_ext(spec: StageSpec) -> bool:
    if spec.cost_cap is None:
        return False
    return spec.objective in ("wait", "latency") or spec.wait_cap is not None


def read_latency(attach: Path) -> np.ndarray:
    raw = pd.read_excel(attach / "network_latency.xlsx", sheet_name="network_latency")
    return raw.pivot(index="FromRegion", columns="ToRegion", values="NetworkLatency_ms").loc[list(REGIONS), list(REGIONS)].to_numpy(float)


def pool_values(pool: ColumnPool, data, latency_raw: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    task, region, start = pool.arrays()
    wait = (start - data.arrival[task]).astype(float)
    latency = latency_raw[data.source[task], region].astype(float)
    return wait, latency


def assemble_stage_model(assign: csr_matrix, resource: csr_matrix, cuts: csr_matrix,
                         rhs: np.ndarray, cut_const: np.ndarray, objective: np.ndarray,
                         wait: np.ndarray, cut_regions: np.ndarray, spec: StageSpec) -> tuple[csr_matrix, np.ndarray, csr_matrix, np.ndarray, dict]:
    n = assign.shape[1]
    blocks = [hstack([resource, csr_matrix((resource.shape[0], R))])]
    bounds = [rhs]
    if cuts.shape[0]:
        theta_coeff = np.zeros((cuts.shape[0], R), dtype=float)
        for row, region in enumerate(cut_regions):
            theta_coeff[row, int(region)] = -1.0
        blocks.append(hstack([cuts, csr_matrix(theta_coeff)]))
        bounds.append(-cut_const)
    offsets = {"resource": (0, resource.shape[0])}
    row = resource.shape[0]
    offsets["cuts"] = (row, row + cuts.shape[0]); row += cuts.shape[0]
    if spec.cost_cap is not None:
        blocks.append(csr_matrix(np.r_[np.zeros(n), np.ones(R)].reshape(1, -1)))
        bounds.append(np.asarray([spec.cost_cap], dtype=float))
        offsets["cost_cap"] = row; row += 1
    else:
        offsets["cost_cap"] = None
    if spec.wait_cap is not None:
        blocks.append(csr_matrix(np.r_[wait, np.zeros(R)].reshape(1, -1)))
        bounds.append(np.asarray([spec.wait_cap], dtype=float))
        offsets["wait_cap"] = row; row += 1
    else:
        offsets["wait_cap"] = None
    aub = vstack(blocks).tocsr()
    bub = np.concatenate(bounds)
    aeq = hstack([assign, csr_matrix((assign.shape[0], R))]).tocsr()
    beq = np.ones(assign.shape[0])
    theta_cost = np.ones(R) if spec.objective == "cost" else np.zeros(R)
    c = np.r_[objective, theta_cost]
    return aub, bub, aeq, beq, {"offsets": offsets, "c": c}


def solve_stage_lp(assign: csr_matrix, resource: csr_matrix, cuts: csr_matrix,
                   rhs: np.ndarray, cut_const: np.ndarray, objective: np.ndarray,
                   wait: np.ndarray, cut_regions: np.ndarray, spec: StageSpec) -> dict:
    aub, bub, aeq, beq, meta = assemble_stage_model(assign, resource, cuts, rhs, cut_const, objective, wait, cut_regions, spec)
    n = assign.shape[1]
    result = linprog(meta["c"], A_ub=aub, b_ub=bub, A_eq=aeq, b_eq=beq,
                     bounds=[(0.0, None)] * n + [(-1e10, None)] * R, method="highs")
    if not result.success:
        raise StageStopped(spec.name + " RMP LP 失败：" + result.message)
    marginal = np.asarray(result.ineqlin.marginals)
    offsets = meta["offsets"]
    r0, r1 = offsets["resource"]; c0, c1 = offsets["cuts"]
    return {
        "result": result,
        "x": result.x[:n],
        "theta": result.x[-R:].copy(),
        "theta_total": float(np.sum(result.x[-R:])),
        "objective": float(result.fun),
        "assignment_dual": np.asarray(result.eqlin.marginals),
        "resource_dual": marginal[r0:r1],
        "cut_dual": marginal[c0:c1],
        "cost_cap_dual": None if offsets["cost_cap"] is None else float(marginal[offsets["cost_cap"]]),
        "wait_cap_dual": None if offsets["wait_cap"] is None else float(marginal[offsets["wait_cap"]]),
    }


def solve_stage_mip(assign: csr_matrix, resource: csr_matrix, cuts: csr_matrix,
                    rhs: np.ndarray, cut_const: np.ndarray, objective: np.ndarray,
                    wait: np.ndarray, cut_regions: np.ndarray, spec: StageSpec, time_limit: float, gap: float):
    aub, bub, aeq, beq, meta = assemble_stage_model(assign, resource, cuts, rhs, cut_const, objective, wait, cut_regions, spec)
    n = assign.shape[1]
    options = {"mip_rel_gap": gap, "disp": True}
    if time_limit > 0:
        options["time_limit"] = time_limit
    return milp(
        c=meta["c"],
        integrality=np.r_[np.ones(n), np.zeros(R)],
        bounds=Bounds(np.r_[np.zeros(n), np.full(R, -1e10)], np.r_[np.ones(n), np.full(R, np.inf)]),
        constraints=[
            LinearConstraint(aub, -np.inf * np.ones(len(bub)), bub),
            LinearConstraint(aeq, beq, beq),
        ],
        options=options,
    )


def solve_extensive_mip(pool: ColumnPool, data, assign: csr_matrix, resource: csr_matrix,
                        rhs: np.ndarray, objective: np.ndarray, wait: np.ndarray,
                        spec: StageSpec, time_limit: float, gap: float) -> dict:
    """在活动列池上把真实 Renewable/BESS/Grid recourse 直接并入整数模型。"""
    n = len(pool); nv = 8; ne = R * H_ENERGY * nv; nt = n + ne
    pos = {"u": 0, "qR": 1, "qG": 2, "d": 3, "gL": 4, "s": 5, "w": 6, "E": 7}
    def ix(r: int, h: int, name: str) -> int:
        return n + (r * H_ENERGY + h) * nv + pos[name]

    ti, rr, ss = pool.arrays()
    fixed = fixed_facility_load(data)
    erows: list[int] = []; ecols: list[int] = []; evals: list[float] = []
    ebe: list[float] = []; row = 0
    for r in range(R):
        st = data.storage.iloc[r]
        ce, de = float(st.ChargeEfficiency), float(st.DischargeEfficiency)
        rbase = row

        for h in range(H_ENERGY):
            for name in ("u", "qR", "s", "w"):
                erows.append(row)
                ecols.append(ix(r, h, name))
                evals.append(1.0)
            ebe.append(float(data.renew[r, h]))
            row += 1

            for name in ("u", "d", "gL"):
                erows.append(row)
                ecols.append(ix(r, h, name))
                evals.append(1.0)
            ebe.append(float(fixed[r, h]))
            row += 1

            erows.append(row)
            ecols.append(ix(r, h, "E"))
            evals.append(1.0)
            if h:
                erows.append(row)
                ecols.append(ix(r, h - 1, "E"))
                evals.append(-1.0)
                ebe.append(0.0)
            else:
                ebe.append(float(st.InitialSOC_MWh))
            erows.append(row)
            ecols.append(ix(r, h, "qR"))
            evals.append(-ce)
            erows.append(row)
            ecols.append(ix(r, h, "qG"))
            evals.append(-ce)
            erows.append(row)
            ecols.append(ix(r, h, "d"))
            evals.append(1.0 / de)
            row += 1

        for j in np.flatnonzero(rr == r):
            prof = overlap_profile(data.duration[int(ti[j])])
            scale = data.pue[r] * data.gpu[int(ti[j])] * data.alpha[int(ti[j])]
            for k, weight in enumerate(prof):
                hh = int(ss[j]) + k
                if hh < H_TASK and hh < H_ENERGY:
                    erows.append(rbase + 3 * hh + 1)
                    ecols.append(int(j))
                    evals.append(-float(scale * weight))
    ee = coo_matrix((np.asarray(evals), (np.asarray(erows), np.asarray(ecols))), shape=(row, nt)).tocsr()
    az = csr_matrix((assign.shape[0], ne))
    aeq = vstack([hstack([assign, az], format="csr"), ee], format="csr")
    beq = np.r_[np.ones(assign.shape[0]), np.asarray(ebe, dtype=float)]

    urows: list[int] = []; ucols: list[int] = []; uvals: list[float] = []; ubv: list[float] = []
    row = 0
    for r in range(R):
        st = data.storage.iloc[r]
        charge = float(st.MaxChargePower_MW); imp = float(st.MaxGridImport_MW)
        for h in range(H_ENERGY):
            urows.extend([row, row]); ucols.extend([ix(r, h, "qR"), ix(r, h, "qG")]); uvals.extend([1.0, 1.0]); ubv.append(charge); row += 1
            urows.extend([row, row]); ucols.extend([ix(r, h, "gL"), ix(r, h, "qG")]); uvals.extend([1.0, 1.0]); ubv.append(imp); row += 1
    cost_row = row
    for r in range(R):
        for h in range(H_ENERGY):
            price = float(data.price[r, h]); sell = float(data.sell_price[r, h])
            urows.extend([row, row, row]); ucols.extend([ix(r, h, "gL"), ix(r, h, "qG"), ix(r, h, "s")]); uvals.extend([price, price, -sell])
    ubv.append(float(spec.cost_cap)); row += 1
    if spec.wait_cap is not None:
        wait_row = row
        for j, value in enumerate(wait):
            if abs(float(value)) > 1e-12:
                urows.append(row); ucols.append(j); uvals.append(float(value))
        ubv.append(float(spec.wait_cap)); row += 1
    aub = coo_matrix((np.asarray(uvals), (np.asarray(urows), np.asarray(ucols))), shape=(row, nt)).tocsr()
    bub = np.r_[np.asarray(rhs, dtype=float), np.asarray(ubv, dtype=float)]
    ar = hstack([resource, csr_matrix((resource.shape[0], ne))], format="csr")
    aub = vstack([ar, aub], format="csr")

    c = np.zeros(nt, dtype=float)
    if spec.objective == "cost":
        for r in range(R):
            for h in range(H_ENERGY):
                c[ix(r, h, "gL")] = data.price[r, h]
                c[ix(r, h, "qG")] = data.price[r, h]
                c[ix(r, h, "s")] = -data.sell_price[r, h]
    else:
        c[:n] = objective
    lb = np.zeros(nt, dtype=float); up = np.full(nt, np.inf, dtype=float); up[:n] = 1.0
    for r in range(R):
        st = data.storage.iloc[r]
        for h in range(H_ENERGY):
            up[ix(r, h, "d")] = float(st.MaxDischargePower_MW)
            up[ix(r, h, "s")] = min(float(st.SellLimit_MW), float(st.MaxGridExport_MW))
            lb[ix(r, h, "E")] = float(st.MinSOC_MWh)
            up[ix(r, h, "E")] = float(st.StorageCapacity_MWh)
        lb[ix(r, H_ENERGY - 1, "E")] = max(lb[ix(r, H_ENERGY - 1, "E")], float(st.InitialSOC_MWh))
    options = {"mip_rel_gap": gap, "disp": True}
    if time_limit > 0: options["time_limit"] = time_limit
    res = milp(c=c, integrality=np.r_[np.ones(n), np.zeros(ne)], bounds=Bounds(lb, up),
               constraints=[LinearConstraint(aub, -np.inf * np.ones(len(bub)), bub), LinearConstraint(aeq, beq, beq)],
               options=options)
    return {"success": bool(res.success), "message": str(res.message), "x": res.x,
            "fun": math.nan if res.fun is None else float(res.fun),
            "mip_gap": getattr(res, "mip_gap", None),
            "mip_dual_bound": getattr(res, "mip_dual_bound", None), "cost_row": cost_row}


def active_starts(pool: ColumnPool) -> dict[tuple[int, int], set[int]]:
    active: dict[tuple[int, int], set[int]] = {}
    for task, region, start in zip(*pool.arrays()):
        active.setdefault((int(task), int(region)), set()).add(int(start))
    return active


def best_missing(scores: np.ndarray, start0: int, used: set[int]) -> tuple[float, int] | None:
    relevant = {start for start in used if start0 <= start < start0 + len(scores)}
    if len(relevant) >= len(scores):
        return None
    local = int(np.argmin(scores))
    if start0 + local in relevant:
        count = min(len(scores), len(relevant) + 1)
        candidates = np.argpartition(scores, count - 1)[:count]
        available = [int(k) for k in candidates if start0 + int(k) not in relevant]
        if not available:
            return None
        local = min(available, key=lambda k: scores[k])
    return float(scores[local]), start0 + local


def price_full_domain(pool: ColumnPool, data, gpu_row: np.ndarray, it_row: np.ndarray,
                      resource_dual: np.ndarray, cut_dual: np.ndarray, cuts: list[Cut],
                      assignment_dual: np.ndarray, spec: StageSpec, latency_raw: np.ndarray,
                      wait_cap_dual: float | None, tol: float, columns_per_task: int,
                      show_bar: bool | None = None) -> tuple[list[tuple[int, int, int, float]], float, int]:
    cut_signal = np.zeros((R, H_TASK), dtype=float)
    for dual, cut in zip(cut_dual, cuts):
        cut_signal += -dual * cut.lam[:, :H_TASK]
    profiles: dict[tuple[int, int, int], np.ndarray] = {}
    examples = {int(task_type): int(np.flatnonzero(data.type_idx == task_type)[0]) for task_type in np.unique(data.type_idx)}
    for task_type, duration in set(zip(data.type_idx.tolist(), data.duration.tolist())):
        prof = overlap_profile(duration)
        alpha = data.alpha[examples[int(task_type)]]
        for region in range(R):
            hourly = np.zeros(H_TASK)
            for hour in range(H_TASK):
                gpu_index, it_index = int(gpu_row[region, hour]), int(it_row[region, hour])
                if gpu_index >= 0:
                    hourly[hour] += -resource_dual[gpu_index]
                if it_index >= 0:
                    hourly[hour] += -resource_dual[it_index] * alpha
                hourly[hour] += cut_signal[region, hour] * data.pue[region] * alpha
            profiles[(int(task_type), region, int(round(duration * 60)))] = np.convolve(hourly, prof[::-1], mode="valid")
    beta_wait = 1.0 if spec.objective == "wait" else 0.0
    if wait_cap_dual is not None:
        beta_wait -= wait_cap_dual
    task_types = data.task["TaskType"].astype(str).to_numpy()
    active = active_starts(pool)
    additions: list[tuple[int, int, int, float]] = []
    minimum = math.inf
    negative_regions = 0
    if show_bar is None:
        show_bar = bool(sys.stderr.isatty())
    iterator = tqdm(
        range(len(data.task)), desc=spec.name + " 完整域精确定价",
        unit="任务", leave=False, disable=not show_bar,
    )
    for task in iterator:
        start0 = int(data.arrival[task])
        end = start0 if task_types[task] == "RealTimeInference" else legal_last_start(data, task)
        if end < start0:
            raise RuntimeError(f"TaskID={data.task.iloc[task].TaskID} 无合法开工时刻")
        starts = np.arange(start0, end + 1, dtype=float)
        candidates: list[tuple[float, int, int]] = []
        for region in np.flatnonzero(data.legal[task]):
            base = profiles[(int(data.type_idx[task]), int(region), int(round(data.duration[task] * 60)))][start0:end + 1]
            scores = data.gpu[task] * base + beta_wait * (starts - data.arrival[task])
            if spec.objective == "latency":
                scores = scores + latency_raw[int(data.source[task]), int(region)]
            found = best_missing(scores, start0, active.get((task, int(region)), set()))
            if found is None:
                continue
            score, start = found
            reduced = score - assignment_dual[task]
            minimum = min(minimum, reduced)
            if reduced < -tol:
                negative_regions += 1
                candidates.append((reduced, int(region), start))
        candidates.sort(key=lambda item: item[0])
        additions.extend((task, region, start, reduced) for reduced, region, start in candidates[:columns_per_task])
    additions.sort(key=lambda item: item[3])
    return additions, (0.0 if not np.isfinite(minimum) else float(minimum)), negative_regions


def add_region_cuts(cuts: list[Cut], data, load: np.ndarray, energy: dict,
                    regions: np.ndarray | None = None) -> int:
    fixed = fixed_facility_load(data)
    selected = np.arange(R, dtype=np.int8) if regions is None else np.asarray(regions, dtype=np.int8)
    for region in selected:
        r = int(region)
        lam = np.zeros_like(energy["lam"], dtype=np.float64)
        lam[r] = energy["lam"][r]
        const = float(energy["region_cost"][r] + np.dot(lam[r], fixed[r] - load[r]))
        cuts.append(Cut(const=const, lam=lam, region=r))
    return int(len(selected))


def append_metric(path: Path, row: dict) -> None:
    exists = path.is_file()
    fields = EXTENDED_METRIC_FIELDS
    if exists:
        with path.open("r", encoding="utf-8-sig", newline="") as check:
            header = check.readline().strip().split(",")
        if header == list(METRIC_FIELDS):
            fields = METRIC_FIELDS
        elif header != list(EXTENDED_METRIC_FIELDS):
            raise StageStopped("指标文件字段属于旧版 aggregate Benders，请使用新的 output-dir")
    with path.open("a", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow({name: row.get(name, "") for name in fields})


def save_state(out: Path, pool: ColumnPool, cuts: list[Cut], stage: str, stage_iter: int,
               cost_cap: float | None, wait_star: float | None, initial_columns: int) -> None:
    task, region, start = pool.arrays()
    target = out / "lexicographic_state.npz"
    temporary = out / "lexicographic_state.tmp.npz"
    np.savez_compressed(
        temporary,
        model_version=np.asarray(MODEL_VERSION),
        task=task,
        region=region,
        start=start,
        cut_const=np.asarray([cut.const for cut in cuts], dtype=np.float64),
        cut_lam=np.stack([cut.lam.astype(np.float64) for cut in cuts]),
        cut_region=np.asarray([cut.region for cut in cuts], dtype=np.int8),
        stage=np.asarray(stage),
        stage_iter=np.int32(stage_iter),
        cost_cap=np.float64(np.nan if cost_cap is None else cost_cap),
        wait_star=np.float64(np.nan if wait_star is None else wait_star),
        initial_columns=np.int32(initial_columns),
    )
    temporary.replace(target)


def load_state(out: Path) -> tuple[ColumnPool, list[Cut], str, int, float, float | None, int]:
    path = out / "lexicographic_state.npz"
    if not path.is_file():
        raise RuntimeError("未找到字典序断点：" + str(path))
    with np.load(path, allow_pickle=False) as saved:
        version = str(saved["model_version"].item()) if "model_version" in saved else "legacy_aggregate"
        if version != MODEL_VERSION or "cut_region" not in saved:
            raise RuntimeError("该断点属于旧版 aggregate Benders，区域 multi-cut 语义已改变；请使用新的 output-dir 从 Cost 锚点重新开始")
        pool = ColumnPool()
        for task, region, start in zip(saved["task"], saved["region"], saved["start"]):
            pool.add(int(task), int(region), int(start))
        cuts = [Cut(float(const), lam.astype(np.float64), int(region))
                for const, lam, region in zip(saved["cut_const"], saved["cut_lam"], saved["cut_region"])]
        wait_value = float(saved["wait_star"])
        return pool, cuts, str(saved["stage"].item()), int(saved["stage_iter"]), float(saved["cost_cap"]), None if np.isnan(wait_value) else wait_value, int(saved["initial_columns"])


def write_checkpoint(out: Path, payload: dict) -> None:
    target = out / "checkpoint.json"
    temporary = out / "checkpoint.tmp.json"
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)


def load_latency_incumbent(out: Path) -> dict | None:
    path = out / LATENCY_INCUMBENT_JSON
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_latency_incumbent(out: Path, pool: ColumnPool, data, x: np.ndarray,
                           latency_raw: np.ndarray, energy: dict, source: str,
                           force: bool = False) -> dict:
    task, region, start = pool.arrays()
    chosen = np.flatnonzero(x > 0.5)
    chosen_task = task[chosen]
    chosen_region = region[chosen]
    chosen_start = start[chosen]
    wait = chosen_start - data.arrival[chosen_task]
    latency = latency_raw[data.source[chosen_task], chosen_region]
    if len(chosen) != len(data.task) or len(np.unique(chosen_task)) != len(data.task):
        raise StageStopped("可行 Latency incumbent 没有完整覆盖任务")
    metadata = {
        "来源": source,
        "总等待_h": float(np.sum(wait)),
        "总时延_ms": float(np.sum(latency)),
        "真实能源成本_CNY": float(energy["cost"]),
        "任务数": int(len(chosen)),
        "全局整数最优已证明": False,
    }
    current = load_latency_incumbent(out)
    if not force and current is not None and float(current["总时延_ms"]) <= metadata["总时延_ms"] + 1e-9:
        return current
    schedule = pd.DataFrame({
        "TaskID": data.task.iloc[chosen_task]["TaskID"].to_numpy(),
        "目标区域": [REGIONS[int(r)] for r in chosen_region],
        "开工小时": chosen_start,
        "等待_h": wait.astype(float),
        "时延_ms": latency.astype(float),
    }).sort_values("TaskID")
    schedule.to_csv(out / LATENCY_INCUMBENT_CSV, index=False, encoding="utf-8-sig")
    (out / LATENCY_INCUMBENT_JSON).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata


def append_latency_certificate(out: Path, row: dict) -> None:
    path = out / LATENCY_CERTIFICATE_CSV
    exists = path.is_file()
    with path.open("a", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=LATENCY_CERTIFICATE_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({name: row.get(name, "") for name in LATENCY_CERTIFICATE_FIELDS})


def restricted_mip_lower_bound(mip) -> float:
    if isinstance(mip, dict):
        value = mip.get("mip_dual_bound")
        fallback = mip.get("fun")
    else:
        value = getattr(mip, "mip_dual_bound", None)
        fallback = getattr(mip, "fun", None)
    if value is None or not np.isfinite(value):
        return float(fallback)
    return float(value)


def run_final_recertification(attach: Path, qos_out: Path) -> None:
    script = Path(__file__).with_name("q4_final_recertification.py")
    final_out = qos_out.parent / "qos_final_recertification"
    summary_path = final_out / "q4_qos_summary.json"
    if summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("状态") == "FINISHED_DRAFT":
            print("final-pool 字典序再认证已完成，跳过重复运行")
            return
    command = [
        sys.executable, str(script),
        "--attachment-dir", str(attach),
        "--input-dir", str(qos_out),
        "--output-dir", str(final_out),
    ]
    if (final_out / "recertification_control.json").is_file():
        command.append("--resume")
    print("QoS 阶段真实闭合，自动进入 final-pool Cost -> Wait -> Latency 再认证")
    result = subprocess.run(command, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def load_cost_anchor(input_dir: Path, data, cost_tolerance: float, required_benders_tol: float) -> tuple[ColumnPool, list[Cut], float, float, dict[int, tuple[int, int]]]:
    summary = json.loads((input_dir / "summary.json").read_text(encoding="utf-8"))
    recorded_tol = summary.get("Benders闭合容差_CNY")
    if not summary.get("根节点闭合") or recorded_tol is None or float(recorded_tol) > required_benders_tol + 1e-12:
        raise RuntimeError("Cost 阶段来自旧版宽松 Benders 门禁。请先用修正版 q4_full_solver.py 重新运行 full_run，不能沿用旧 root 结果。")
    pool, _, _, _, _ = load_solver_state(input_dir)
    schedule = pd.read_csv(input_dir / "best_schedule.csv")
    task_index = {int(task_id): i for i, task_id in enumerate(data.task["TaskID"].to_numpy())}
    placement: dict[int, tuple[int, int]] = {}
    for row in schedule.itertuples(index=False):
        task = task_index[int(row.TaskID)]
        region = REGIONS.index(str(row.区域)); start = int(row.开工小时)
        pool.add(task, region, start); placement[int(row.TaskID)] = (region, start)
    index = {ColumnPool.key(task, region, start): j for j, (task, region, start) in enumerate(zip(*pool.arrays()))}
    x = np.zeros(len(pool))
    for task_id, (region, start) in placement.items():
        x[index[ColumnPool.key(task_index[task_id], region, start)]] = 1.0
    if int(np.count_nonzero(x > 0.5)) != len(data.task):
        raise RuntimeError("Cost 排程没有覆盖全部任务")
    load = facility_load(pool, data, x)
    energy = energy_lp(load, data)
    if not energy["success"]:
        raise RuntimeError("Cost 排程真实能源复核失败：" + energy["message"])
    cuts: list[Cut] = []
    add_region_cuts(cuts, data, load, energy)
    return pool, cuts, float(energy["cost"] + cost_tolerance), float(energy["cost"]), placement


def check_limits(args, process: psutil.Process, started: float, pool: ColumnPool) -> None:
    if args.max_hours > 0 and (time.time() - started) / 3600 > args.max_hours:
        raise StageStopped("达到总运行时间门槛")
    if args.max_active_columns > 0 and len(pool) >= args.max_active_columns:
        raise StageStopped("达到活动列数门槛")
    if args.max_rss_gib > 0 and process.memory_info().rss / 1024 ** 3 > args.max_rss_gib:
        raise StageStopped("达到 RSS 内存门槛")


def run_stage(spec: StageSpec, pool: ColumnPool, cuts: list[Cut], data, gpu_row: np.ndarray,
              it_row: np.ndarray, rhs: np.ndarray, latency_raw: np.ndarray, args,
              out: Path, started: float, initial_columns: int,
              wait_star_state: float | None, start_iter: int = 0,
              metrics_name: str = "q4_lexicographic_stage_metrics.csv") -> StageOutcome:
    process = psutil.Process()
    metrics_path = out / metrics_name
    total_added = 0
    last_min_rc = math.nan
    stage_started = time.time()
    cm_cache = CutMatrixCache()
    state_stage = "recovery" if spec.objective == "cost" and spec.wait_cap is not None else spec.objective
    peak_rss_gib = process.memory_info().rss / 1024 ** 3
    latency_incumbent = load_latency_incumbent(out) if spec.objective == "latency" else None
    if latency_incumbent is not None:
        violates_cost = spec.cost_cap is not None and float(latency_incumbent["真实能源成本_CNY"]) > spec.cost_cap + args.cost_feas_tol_cny
        violates_wait = spec.wait_cap is not None and float(latency_incumbent["总等待_h"]) > spec.wait_cap + args.wait_tolerance
        if violates_cost or violates_wait:
            latency_incumbent = None
    stage_ui(spec, start_iter, args)
    iterations = count(start_iter + 1) if args.max_stage_iter == 0 else range(start_iter + 1, args.max_stage_iter + 1)
    bar = tqdm(
        iterations, desc=spec.name + " Benders+CG", unit="轮", total=None,
        disable=not use_bar(args),
    )
    for iteration in bar:
        check_limits(args, process, started, pool)
        peak_rss_gib = max(peak_rss_gib, process.memory_info().rss / 1024 ** 3)
        wait, latency = pool_values(pool, data, latency_raw)
        objective = np.zeros(len(pool)) if spec.objective == "cost" else (wait if spec.objective == "wait" else latency)
        assign = assignment_matrix(pool, len(data.task))
        resource = resource_matrix(pool, data, gpu_row, it_row, len(rhs))
        cm = cut_matrix(pool, data, cuts, cm_cache)
        const = np.asarray([cut.const for cut in cuts], dtype=float)
        cut_regions = np.asarray([cut.region for cut in cuts], dtype=np.int8)
        if np.any(cut_regions < 0):
            raise StageStopped("发现非区域化 Benders cut，不能与 region multi-cut 混用")
        lp = solve_stage_lp(assign, resource, cm, rhs, const, objective, wait, cut_regions, spec)
        load = facility_load(pool, data, lp["x"])
        energy = energy_lp(load, data)
        if not energy["success"]:
            raise StageStopped(spec.name + " LP 能源子问题不可行：" + energy["message"])
        region_violation = energy["region_cost"] - lp["theta"]
        violation = float(energy["cost"] - lp["theta_total"])
        cap_violation = 0.0 if spec.cost_cap is None else float(energy["cost"] - spec.cost_cap)
        violated_regions = np.flatnonzero(region_violation > args.benders_tol_cny)
        if cap_violation > args.cost_feas_tol_cny and len(violated_regions) == 0:
            violated_regions = np.arange(R, dtype=np.int8)
        event = "added_region_benders_cuts"
        added = 0
        root_closed = False
        min_rc = math.nan
        if len(violated_regions):
            add_region_cuts(cuts, data, load, energy, violated_regions)
        else:
            additions, min_rc, _ = price_full_domain(
                pool, data, gpu_row, it_row, lp["resource_dual"], lp["cut_dual"], cuts,
                lp["assignment_dual"], spec, latency_raw, lp["wait_cap_dual"],
                args.price_tol, args.columns_per_task, use_bar(args),
            )
            added = sum(pool.add(task, region, start) for task, region, start, _ in additions)
            total_added += added
            last_min_rc = min_rc
            if added:
                event = "added_columns"
            elif min_rc >= -args.price_tol and cap_violation <= args.cost_feas_tol_cny:
                event = "root_lp_closed"
                root_closed = True
            else:
                raise StageStopped(spec.name + " 定价发现负约化成本，但没有成功加入缺失列")
        dominant = int(np.argmax(region_violation))
        row = {
            "阶段": spec.name, "轮次": iteration, "事件": event, "活动列数": len(pool),
            "Benders切数": len(cuts), "LP目标值": lp["objective"], "theta_CNY": lp["theta_total"],
            "真实能源成本_CNY": energy["cost"], "Benders违反_CNY": violation,
            "最大区域违反_CNY": float(np.max(region_violation)),
            **{f"theta_{REGIONS[r][-1]}_CNY": float(lp["theta"][r]) for r in range(R)},
            **{f"真实能源成本_{REGIONS[r][-1]}_CNY": float(energy["region_cost"][r]) for r in range(R)},
            **{f"区域违反_{REGIONS[r][-1]}_CNY": float(region_violation[r]) for r in range(R)},
            "新增列数": added, "最小缺失列约化成本": min_rc, "根节点闭合": root_closed,
            "当前RSS_GiB": process.memory_info().rss / 1024 ** 3, "累计分钟": (time.time() - started) / 60,
            "主导违反区域": REGIONS[dominant], "LP界": float(lp["objective"]),
            "阶段运行秒": float(time.time() - stage_started),
            "峰值RSS_GiB": peak_rss_gib,
            "可行Latency上界_ms": "" if latency_incumbent is None else float(latency_incumbent["总时延_ms"]),
        }
        append_metric(metrics_path, row)
        save_state(out, pool, cuts, state_stage, iteration, spec.cost_cap, wait_star_state, initial_columns)
        write_checkpoint(out, {"模型版本": MODEL_VERSION, "状态": "RUNNING", "当前阶段": spec.name, "轮次": iteration, "事件": event, "活动列数": len(pool), "Benders切数": len(cuts), "最新": row})
        bar.set_postfix(vmax=f"{row['最大区域违反_CNY']:.2f}", vr=REGIONS[dominant][-1], lp=f"{lp['objective']:.0f}", ec=f"{energy['cost']:.0f}", cols=len(pool), cuts=len(cuts), new=added, rc=f"{min_rc:.3g}" if np.isfinite(min_rc) else "-", rss=f"{row['当前RSS_GiB']:.2f}G")
        round_ui(row, args)
        if not root_closed:
            continue
        wait, latency = pool_values(pool, data, latency_raw)
        objective = np.zeros(len(pool)) if spec.objective == "cost" else (wait if spec.objective == "wait" else latency)
        assign = assignment_matrix(pool, len(data.task))
        resource = resource_matrix(pool, data, gpu_row, it_row, len(rhs))
        cm = cut_matrix(pool, data, cuts, cm_cache)
        const = np.asarray([cut.const for cut in cuts], dtype=float)
        cut_regions = np.asarray([cut.region for cut in cuts], dtype=np.int8)
        write_checkpoint(out, {"模型版本": MODEL_VERSION, "状态": "MIP_SOLVING", "当前阶段": spec.name, "轮次": iteration, "事件": "root_lp_closed_start_restricted_mip", "活动列数": len(pool), "Benders切数": len(cuts), "最新": row})
        use_extensive = use_ext(spec)
        mip_kind = "能源一体化 MIP" if use_extensive else "restricted MIP"
        print(
            f"[第{iteration}轮][3/5 整数MIP] 开始 {mip_kind} | "
            f"心跳间隔={args.heartbeat_seconds:g}秒。此步骤可能长时间没有新的最优解。",
            flush=True,
        )
        if use_extensive:
            mip = mip_wait(
                spec.name + " 能源一体化MIP",
                lambda: solve_extensive_mip(
                    pool, data, assign, resource, rhs, objective, wait, spec,
                    args.integer_time_limit_s, args.mip_rel_gap,
                ),
                process, args.heartbeat_seconds,
            )
            mok, mmsg, mx, mfun, mgap = mip["success"], mip["message"], mip["x"], mip["fun"], mip["mip_gap"]
        else:
            mip = mip_wait(
                spec.name + " restricted MIP",
                lambda: solve_stage_mip(
                    assign, resource, cm, rhs, const, objective, wait, cut_regions,
                    spec, args.integer_time_limit_s, args.mip_rel_gap,
                ),
                process, args.heartbeat_seconds,
            )
            mok, mmsg, mx, mfun = mip.success, mip.message, mip.x, float(mip.fun) if mip.fun is not None else math.nan
            mgap = None if not hasattr(mip, "mip_gap") or mip.mip_gap is None else float(mip.mip_gap)
        if not mok or mx is None:
            row.update({"事件": "restricted_mip_incomplete", "MIP状态": mmsg})
            append_metric(metrics_path, row)
            raise StageStopped(spec.name + " restricted MIP 未完成：" + mmsg)
        print(
            f"[第{iteration}轮][3/5 整数MIP] 通过 | 目标值={mfun:.10g} | "
            f"MIP gap={'未知' if mgap is None else f'{mgap:.3g}'}。",
            flush=True,
        )
        x = np.rint(mx[:len(pool)])
        print(f"[第{iteration}轮][4/5 真实Energy复核] 正在计算整数排程的真实能源成本。", flush=True)
        integer_energy = energy_lp(facility_load(pool, data, x), data)
        if not integer_energy["success"]:
            raise StageStopped(spec.name + " 整数候选能源子问题不可行：" + integer_energy["message"])
        integer_region_violation = np.zeros(R, dtype=float) if use_extensive else integer_energy["region_cost"] - mx[-R:]
        integer_violation = 0.0 if use_extensive else float(integer_energy["cost"] - np.sum(mx[-R:]))
        cap_violation = 0.0 if spec.cost_cap is None else float(integer_energy["cost"] - spec.cost_cap)
        if use_extensive and cap_violation > args.cost_feas_tol_cny:
            raise StageStopped(spec.name + " 能源一体化 MIP 返回的整数解违反 Cost cap")
        candidate_latency = float(latency @ x)
        latency_lb = restricted_mip_lower_bound(mip) if spec.objective == "latency" else math.nan
        latency_ub = math.nan if latency_incumbent is None else float(latency_incumbent["总时延_ms"])
        latency_gap = math.nan if not np.isfinite(latency_ub) else max(0.0, latency_ub - latency_lb) / max(1.0, abs(latency_ub))
        integer_violated_regions = np.flatnonzero(integer_region_violation > args.benders_tol_cny)
        if cap_violation > args.cost_feas_tol_cny and len(integer_violated_regions) == 0:
            integer_violated_regions = np.arange(R, dtype=np.int8)
        if len(integer_violated_regions) and not use_extensive:
            add_region_cuts(cuts, data, facility_load(pool, data, x), integer_energy, integer_violated_regions)
            print(
                f"[第{iteration}轮][4/5 真实Energy复核] 未通过 | "
                f"触发{len(integer_violated_regions)}个区域 cut，"
                f"最大违反={float(np.max(integer_region_violation)):.6g} CNY；返回LP继续。",
                flush=True,
            )
            row.update({"事件": "integer_added_region_benders_cuts", "MIP状态": "需要继续", "MIP目标值": mfun, "真实能源成本_CNY": integer_energy["cost"], "Benders违反_CNY": integer_violation, "最大区域违反_CNY": float(np.max(integer_region_violation)), "根节点闭合": False, "Benders切数": len(cuts), "可行Latency上界_ms": "" if not np.isfinite(latency_ub) else latency_ub, "Latency下界_ms": "" if not np.isfinite(latency_lb) else latency_lb, "Latency相对Gap": "" if not np.isfinite(latency_gap) else latency_gap, "成本上界违反_CNY": max(0.0, cap_violation)})
            row.update({f"theta_{REGIONS[r][-1]}_CNY": float(mx[-R + r]) for r in range(R)})
            row.update({f"真实能源成本_{REGIONS[r][-1]}_CNY": float(integer_energy["region_cost"][r]) for r in range(R)})
            row.update({f"区域违反_{REGIONS[r][-1]}_CNY": float(integer_region_violation[r]) for r in range(R)})
            row.update({"主导违反区域": REGIONS[int(np.argmax(integer_region_violation))], "MIP Gap": mgap, "MIP目标值": mfun, "峰值RSS_GiB": peak_rss_gib})
            append_metric(metrics_path, row)
            if spec.objective == "latency":
                append_latency_certificate(out, {
                    "轮次": iteration, "活动列数": len(pool), "Benders切数": len(cuts),
                    "LP最小缺失列约化成本": min_rc,
                    "LP最大区域违反_CNY": float(np.max(region_violation)),
                    "restricted_MIP_Latency_ms": candidate_latency,
                    "真实能源成本_CNY": float(integer_energy["cost"]),
                    "成本上界违反_CNY": max(0.0, cap_violation),
                    "RegionE违反_CNY": float(integer_region_violation[4]),
                    "RegionF违反_CNY": float(integer_region_violation[5]),
                    "可行Latency上界_ms": "" if not np.isfinite(latency_ub) else latency_ub,
                    "Latency下界_ms": latency_lb,
                    "Latency相对Gap": "" if not np.isfinite(latency_gap) else latency_gap,
                    "事件": "integer_added_region_benders_cuts",
                })
            save_state(out, pool, cuts, state_stage, iteration, spec.cost_cap, wait_star_state, initial_columns)
            write_checkpoint(out, {"模型版本": MODEL_VERSION, "状态": "RUNNING", "当前阶段": spec.name, "轮次": iteration, "事件": row["事件"], "活动列数": len(pool), "Benders切数": len(cuts), "最新": row})
            continue
        integer_objective = float(integer_energy["cost"] if spec.objective == "cost" else objective @ x)
        if spec.wait_cap is not None and float(wait @ x) > spec.wait_cap + 1e-6:
            raise StageStopped(spec.name + " 整数候选违反等待上界")
        print(
            f"[第{iteration}轮][4/5 真实Energy复核] 通过 | "
            f"真实能源成本={float(integer_energy['cost']):.6f} CNY | "
            f"最大区域一致性违反={float(np.max(integer_region_violation)):.6g} CNY。",
            flush=True,
        )
        wait_v = float(wait @ x)
        cost_s = "无Cost上界" if spec.cost_cap is None else f"Cost={integer_energy['cost']:.6f} <= {spec.cost_cap:.6f} CNY"
        wait_s = "无Wait上界" if spec.wait_cap is None else f"Wait={wait_v:.6f} <= {spec.wait_cap:.6f} h"
        print(f"[第{iteration}轮][5/5 阶段硬约束] 通过 | {cost_s} | {wait_s}。", flush=True)
        mip_gap = mgap
        mip_objective = mfun
        if spec.objective in ("wait", "latency") or spec.wait_cap is not None:
            latency_incumbent = save_latency_incumbent(out, pool, data, x, latency_raw, integer_energy, spec.name, force=spec.objective == "wait")
            latency_ub = float(latency_incumbent["总时延_ms"])
            latency_gap = max(0.0, latency_ub - latency_lb) / max(1.0, abs(latency_ub)) if np.isfinite(latency_lb) else math.nan
        print(
            f"[阶段完成] {spec.name} 五项门禁全部通过 | 阶段目标={integer_objective:.10g} | "
            "注意：这不是整道Q4的最终结束信号。",
            flush=True,
        )
        row.update({"事件": "stage_completed", "MIP状态": "restricted_mip_completed", "MIP目标值": mip_objective, "真实能源成本_CNY": integer_energy["cost"], "Benders违反_CNY": integer_violation, "最大区域违反_CNY": float(np.max(integer_region_violation)), "根节点闭合": True, "LP界": float(lp["objective"]), "MIP Gap": mip_gap, "主导违反区域": REGIONS[int(np.argmax(integer_region_violation))], "峰值RSS_GiB": peak_rss_gib, "Benders切数": len(cuts), "可行Latency上界_ms": "" if not np.isfinite(latency_ub) else latency_ub, "Latency下界_ms": "" if not np.isfinite(latency_lb) else latency_lb, "Latency相对Gap": "" if not np.isfinite(latency_gap) else latency_gap, "成本上界违反_CNY": max(0.0, cap_violation)})
        append_metric(metrics_path, row)
        if spec.objective == "latency":
            append_latency_certificate(out, {
                "轮次": iteration, "活动列数": len(pool), "Benders切数": len(cuts),
                "LP最小缺失列约化成本": min_rc,
                "LP最大区域违反_CNY": float(np.max(region_violation)),
                "restricted_MIP_Latency_ms": candidate_latency,
                "真实能源成本_CNY": float(integer_energy["cost"]),
                "成本上界违反_CNY": max(0.0, cap_violation),
                "RegionE违反_CNY": float(integer_region_violation[4]),
                "RegionF违反_CNY": float(integer_region_violation[5]),
                "可行Latency上界_ms": latency_ub, "Latency下界_ms": latency_lb,
                "Latency相对Gap": latency_gap, "事件": "stage_completed",
            })
        return StageOutcome(x=x, energy=integer_energy, objective=integer_objective,
                            lp_bound=float(lp["objective"]), mip_gap=mip_gap,
                            iterations=iteration, added_columns=total_added,
                            min_reduced_cost=float(last_min_rc), mip_objective=mip_objective,
                            final_max_region_violation=float(np.max(integer_region_violation)),
                            benders_cuts=len(cuts), runtime_s=float(time.time() - stage_started),
                            peak_rss_gib=peak_rss_gib)
    raise StageStopped(spec.name + " 达到最大迭代轮数")


def audit_solution(pool: ColumnPool, data, x: np.ndarray, gpu_row: np.ndarray,
                   it_row: np.ndarray, rhs: np.ndarray, latency_raw: np.ndarray,
                   energy: dict) -> tuple[pd.DataFrame, dict]:
    task, region, start = pool.arrays()
    chosen = np.flatnonzero(x > 0.5)
    chosen_task = task[chosen]; chosen_region = region[chosen]; chosen_start = start[chosen]
    wait = chosen_start - data.arrival[chosen_task]
    latency = latency_raw[data.source[chosen_task], chosen_region]
    finish = chosen_start + data.duration[chosen_task] / 60.0
    schedule = pd.DataFrame({
        "TaskID": data.task.iloc[chosen_task]["TaskID"].to_numpy(),
        "任务类型": data.task.iloc[chosen_task]["TaskType"].to_numpy(),
        "源区域": [REGIONS[int(r)] for r in data.source[chosen_task]],
        "目标区域": [REGIONS[int(r)] for r in chosen_region],
        "到达小时": data.arrival[chosen_task],
        "开工小时": chosen_start,
        "完成小时": finish,
        "等待_h": wait.astype(float),
        "时延_ms": latency.astype(float),
    })
    schedule["是否迁移"] = schedule["源区域"] != schedule["目标区域"]
    resource = resource_matrix(pool, data, gpu_row, it_row, len(rhs))
    resource_value = np.asarray(resource @ x).ravel()
    assignment = np.asarray(assignment_matrix(pool, len(data.task)) @ x).ravel()
    realtime = data.task.iloc[chosen_task]["TaskType"].astype(str).to_numpy() == "RealTimeInference"
    audit = {
        "任务覆盖违规数": int(np.count_nonzero(np.abs(assignment - 1.0) > 1e-7)),
        "GPU或IT容量违规行数": int(np.count_nonzero(resource_value - rhs > 1e-7)),
        "最大容量越界": float(max(0.0, np.max(resource_value - rhs))),
        "到达时间违规数": int(np.count_nonzero(chosen_start < data.arrival[chosen_task])),
        "RT即到即开违规数": int(np.count_nonzero(chosen_start[realtime] != data.arrival[chosen_task][realtime])),
        "SLA区域违规数": int(sum(not data.legal[int(t), int(r)] for t, r in zip(chosen_task, chosen_region))),
        "LatestFinish违规数": int(np.count_nonzero(finish - data.latest[chosen_task] > 1e-7)),
        "完成晚于2406违规数": int(np.count_nonzero(finish - 2406.0 > 1e-7)),
        **energy.get("audit", {}),
    }
    return schedule.sort_values("TaskID").reset_index(drop=True), audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Q4 Wait/Latency 完整域字典序 Benders-CG")
    parser.add_argument("--attachment-dir", type=Path, default=DEFAULT_ATTACH)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--cost-tolerance", type=float, default=1e-3)
    parser.add_argument("--wait-tolerance", type=float, default=1e-6)
    parser.add_argument("--benders-tol-cny", type=float, default=1e-3)
    parser.add_argument("--cost-feas-tol-cny", type=float, default=1e-3)
    parser.add_argument("--price-tol", type=float, default=1e-7)
    parser.add_argument("--columns-per-task", type=int, default=2)
    parser.add_argument("--max-stage-iter", type=int, default=0, help="0 表示持续到阶段真实闭合")
    parser.add_argument("--integer-time-limit-s", type=float, default=0.0, help="0 表示单次 MIP 不设时限")
    parser.add_argument("--mip-rel-gap", type=float, default=1e-7)
    parser.add_argument("--max-hours", type=float, default=0.0, help="0 表示不设总时长门槛")
    parser.add_argument("--max-active-columns", type=int, default=1_000_000)
    parser.add_argument("--max-rss-gib", type=float, default=10.0)
    parser.add_argument("--min-free-gib", type=float, default=2.0)
    parser.add_argument(
        "--progress-mode", choices=("auto", "bar", "plain"), default="auto",
        help="auto在PyCharm输出窗使用清晰逐行反馈，在真实终端使用动态进度条",
    )
    parser.add_argument(
        "--heartbeat-seconds", type=float, default=30.0,
        help="MIP长时间求解时的心跳间隔；0表示关闭心跳",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--no-final-recertification", action="store_true", help="仅调试时关闭自动最终再认证")
    args = parser.parse_args()
    if args.columns_per_task < 1:
        raise SystemExit("columns-per-task 必须至少为 1")
    if args.max_stage_iter < 0 or args.max_hours < 0 or args.integer_time_limit_s < 0:
        raise SystemExit("max-stage-iter、max-hours 和 integer-time-limit-s 不能为负；0 表示不限")
    if args.heartbeat_seconds < 0:
        raise SystemExit("heartbeat-seconds 不能为负；0 表示关闭心跳")
    vm = psutil.virtual_memory(); free_gib = vm.available / 1024 ** 3
    if free_gib < args.min_free_gib:
        raise SystemExit(f"停止：当前可用内存 {free_gib:.2f} GiB，小于门槛 {args.min_free_gib:.2f} GiB")
    attach = args.attachment_dir.resolve(); input_dir = args.input_dir.resolve(); out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    started = time.time(); data = read_data(attach); latency_raw = read_latency(attach)
    print(
        "[Q4求解说明] 当前脚本负责生成和扩展QoS列池。即使Wait/Latency阶段完成，"
        "也必须继续通过final recertification的Cost->Wait->Latency至少两个稳定sweep，才显示正式可结束。",
        flush=True,
    )
    gpu_row, it_row, rhs, _ = make_presolve_rows(data)
    cost_placement: dict[int, tuple[int, int]] = {}
    if args.resume:
        pool, cuts, stage, stage_iter, cost_cap, wait_star, initial_columns = load_state(out)
        cost_anchor = cost_cap - args.cost_tolerance
        print(f"恢复阶段={stage}，第 {stage_iter} 轮后，活动列={len(pool)}，cuts={len(cuts)}")
        recovery_marker = out / WAIT_RECOVERY_JSON
        if stage in ("wait", "cost") and recovery_marker.is_file():
            marker = json.loads(recovery_marker.read_text(encoding="utf-8"))
            if marker.get("状态") == "RUNNING" and marker.get("Latency恢复轮次") is not None:
                wait_star = RECOVERY_WAIT_ANCHOR_H
                stage_iter = 0
                stage = "recovery"
                save_state(out, pool, cuts, stage, stage_iter, cost_cap, wait_star, initial_columns)
                write_checkpoint(out, {"模型版本": MODEL_VERSION, "状态": "RECOVERING_WAIT_INCUMBENT", "当前阶段": "Wait=32可行端点恢复", "活动列数": len(pool), "Benders切数": len(cuts), "等待锚点_h": wait_star})
        if stage == "latency" and load_latency_incumbent(out) is None and wait_star is not None:
            print("旧断点未保存 Wait 真实可行排程；先在当前扩展列池自动重建 Latency 可行上界")
            (out / WAIT_RECOVERY_JSON).write_text(json.dumps({"状态": "RUNNING", "Latency恢复轮次": stage_iter}, ensure_ascii=False, indent=2), encoding="utf-8")
            stage, stage_iter = "recovery", 0
            save_state(out, pool, cuts, stage, stage_iter, cost_cap, wait_star, initial_columns)
            write_checkpoint(out, {"模型版本": MODEL_VERSION, "状态": "RECOVERING_WAIT_INCUMBENT", "当前阶段": "Wait=32可行端点恢复", "活动列数": len(pool), "Benders切数": len(cuts), "等待锚点_h": wait_star})
    else:
        pool, cuts, cost_cap, cost_anchor, cost_placement = load_cost_anchor(input_dir, data, args.cost_tolerance, args.benders_tol_cny)
        stage, stage_iter, wait_star, initial_columns = "wait", 0, None, len(pool)
        metrics = out / "q4_lexicographic_stage_metrics.csv"
        if metrics.is_file():
            metrics.unlink()
        save_state(out, pool, cuts, stage, stage_iter, cost_cap, wait_star, initial_columns)
    try:
        wait_outcome = None
        if stage == "recovery":
            recovery_spec = StageSpec("Wait=32可行端点恢复", "cost", cost_cap, wait_star + args.wait_tolerance)
            wait_outcome = run_stage(recovery_spec, pool, cuts, data, gpu_row, it_row, rhs, latency_raw, args, out, started, initial_columns, wait_star, 0)
            recovery_path = out / WAIT_RECOVERY_JSON
            recovery = json.loads(recovery_path.read_text(encoding="utf-8")) if recovery_path.is_file() else {}
            recovery.update({"状态": "COMPLETED", "恢复方式": "Cost目标+Wait锚点约束", "重建Wait锚点_h": wait_star, "可行Latency上界_ms": load_latency_incumbent(out)["总时延_ms"]})
            recovery_path.write_text(json.dumps(recovery, ensure_ascii=False, indent=2), encoding="utf-8")
            stage = "latency"
            stage_iter = int(recovery.get("Latency恢复轮次", 0))
            save_state(out, pool, cuts, stage, stage_iter, cost_cap, wait_star, initial_columns)
            write_checkpoint(out, {"模型版本": MODEL_VERSION, "状态": "WAIT_COMPLETED", "等待最优值_h": wait_star, "活动列数": len(pool), "Benders切数": len(cuts)})
        if stage == "wait":
            wait_spec = StageSpec("Wait阶段", "wait", cost_cap)
            wait_outcome = run_stage(wait_spec, pool, cuts, data, gpu_row, it_row, rhs, latency_raw, args, out, started, initial_columns, None, stage_iter)
            wait_star = wait_outcome.objective
            recovery_path = out / WAIT_RECOVERY_JSON
            if recovery_path.is_file():
                recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
                stage_iter = int(recovery.get("Latency恢复轮次", 0))
                recovery.update({"状态": "COMPLETED", "重建Wait锚点_h": wait_star, "可行Latency上界_ms": load_latency_incumbent(out)["总时延_ms"]})
                recovery_path.write_text(json.dumps(recovery, ensure_ascii=False, indent=2), encoding="utf-8")
            else:
                stage_iter = 0
            stage = "latency"
            save_state(out, pool, cuts, stage, stage_iter, cost_cap, wait_star, initial_columns)
            write_checkpoint(out, {"模型版本": MODEL_VERSION, "状态": "WAIT_COMPLETED", "等待最优值_h": wait_star, "活动列数": len(pool), "Benders切数": len(cuts)})
        if wait_star is None:
            raise StageStopped("缺少 Wait 阶段最优值，不能进入 Latency 阶段")
        latency_spec = StageSpec("Latency阶段", "latency", cost_cap, wait_star + args.wait_tolerance)
        latency_outcome = run_stage(latency_spec, pool, cuts, data, gpu_row, it_row, rhs, latency_raw, args, out, started, initial_columns, wait_star, stage_iter)
    except StageStopped as exc:
        summary = {"模型版本": MODEL_VERSION, "状态": "DRAFT / NEEDS_RESUME", "原因": str(exc), "当前阶段": stage, "活动列数": len(pool), "Benders切数": len(cuts), "成本上界_CNY": cost_cap, "等待最优值_h": wait_star}
        write_checkpoint(out, summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        raise SystemExit(2)
    schedule, audit = audit_solution(pool, data, latency_outcome.x, gpu_row, it_row, rhs, latency_raw, latency_outcome.energy)
    schedule.to_csv(out / "q4_字典序最终排程.csv", index=False, encoding="utf-8-sig")
    stage_metrics = pd.read_csv(out / "q4_lexicographic_stage_metrics.csv")
    wait_added = int(stage_metrics.loc[stage_metrics["阶段"] == "Wait阶段", "新增列数"].fillna(0).sum())
    latency_added = int(stage_metrics.loc[stage_metrics["阶段"] == "Latency阶段", "新增列数"].fillna(0).sum())
    focus = {}
    if 32861 in set(schedule["TaskID"]):
        row = schedule.loc[schedule["TaskID"] == 32861].iloc[0]
        focus = {"TaskID": 32861, "修正后区域": row["目标区域"], "修正后开工小时": int(row["开工小时"]), "修正后等待_h": float(row["等待_h"])}
        if cost_placement:
            region, start = cost_placement[32861]
            focus.update({"Cost阶段区域": REGIONS[region], "Cost阶段开工小时": start})
    summary = {
        "模型版本": MODEL_VERSION,
        "状态": "DRAFT / NEEDS_REVIEW",
        "算法": "Cost-Benders/CG -> Wait-region-multi-cut/CG -> Latency-region-multi-cut/CG",
        "完整候选域": "Wait和Latency阶段均重新扫描全部合法区域与开工时刻",
        "任务数": len(data.task),
        "成本锚点_CNY": cost_anchor,
        "epsilon_C_CNY": args.cost_tolerance,
        "最终真实能源成本_CNY": float(latency_outcome.energy["cost"]),
        "总等待_h": float(schedule["等待_h"].sum()),
        "平均等待_h": float(schedule["等待_h"].mean()),
        "P95等待_h": float(schedule["等待_h"].quantile(0.95)),
        "最大等待_h": float(schedule["等待_h"].max()),
        "总时延_ms": float(schedule["时延_ms"].sum()),
        "平均时延_ms": float(schedule["时延_ms"].mean()),
        "迁移任务数": int(schedule["是否迁移"].sum()),
        "最终活动列数": len(pool),
        "Cost阶段输入列数": initial_columns,
        "Wait阶段新增列数": wait_added,
        "Latency阶段新增列数": latency_added,
        "Benders切数": len(cuts),
        "运行分钟": (time.time() - started) / 60,
        "约束审计": audit,
        "重点任务32861": focus,
        "restricted_integer_status": "restricted_mip_completed",
        "全局整数最优已证明": False,
    }
    (out / "q4_qos_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_checkpoint(out, {**summary, "状态": "FINISHED_DRAFT"})
    save_state(out, pool, cuts, "finished", latency_outcome.iterations, cost_cap, wait_star, initial_columns)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not args.no_final_recertification:
        run_final_recertification(attach, out)


if __name__ == "__main__":
    main()
