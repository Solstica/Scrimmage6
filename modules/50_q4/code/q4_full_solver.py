#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q4 全规模延迟列生成 + Benders 求解器。

完整合法域始终是所有满足 latency、arrival、deadline、finish<=2406 的
(TaskID, Region, StartHour)。脚本从不显式创建该 2.33 亿列集合；列只在
精确定价发现负约化成本时加入受限主问题。

直接运行会使用项目约定的 C 题附件目录；可在 PyCharm/VS Code 直接运行。
运行中的 results/full_run/checkpoint.json 是可读取的实时状态文件。

状态：DRAFT / NEEDS_REVIEW。若 root 未闭合、资源门槛触发，或 restricted MIP
未完成，输出绝不声称全局整数最优。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
from scipy.optimize import Bounds, LinearConstraint, linprog, milp
from scipy.sparse import coo_matrix, csr_matrix, hstack, lil_matrix, vstack
from tqdm.auto import tqdm


REGIONS = ("RegionA", "RegionB", "RegionC", "RegionD", "RegionE", "RegionF")
R = len(REGIONS)
H_TASK = 2406                 # 可计算任务小时 0..2405
H_ENERGY = 2407               # 加入 2406 终端结算小时
EPS = 1e-7
DEFAULT_ATTACH = Path(r"D:\qq文件\2026年武汉理工大学数学建模训练题目7-9\C题附件")
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "results" / "full_run"


def overlap_profile(minutes: float) -> np.ndarray:
    p = float(minutes) / 60.0
    n = int(math.ceil(p - 1e-12))
    return np.array([max(0.0, min(k + 1.0, p) - k) for k in range(n)], dtype=np.float64)


@dataclass
class Data:
    task: pd.DataFrame
    type_idx: np.ndarray
    source: np.ndarray
    arrival: np.ndarray
    latest: np.ndarray
    duration: np.ndarray
    gpu: np.ndarray
    alpha: np.ndarray
    legal: np.ndarray
    pue: np.ndarray
    gpu_cap: np.ndarray
    it_cap: np.ndarray
    non_ai: np.ndarray
    renew: np.ndarray
    price: np.ndarray
    sell_price: np.ndarray
    carbon: np.ndarray
    storage: pd.DataFrame


@dataclass
class Cut:
    const: float
    lam: np.ndarray             # shape (R, H_ENERGY), full load-balance subgradient
    region: int = -1            # -1 表示旧版总 recourse；>=0 表示区域 recourse cut


class ColumnPool:
    """只保存 packed 标量元数据；禁止每个候选使用 dict/object。"""
    def __init__(self) -> None:
        self.task: list[int] = []
        self.region: list[int] = []
        self.start: list[int] = []
        self.keys: set[int] = set()

    @staticmethod
    def key(task: int, region: int, start: int) -> int:
        return int(task) * (R * H_TASK) + int(region) * H_TASK + int(start)

    def add(self, task: int, region: int, start: int) -> bool:
        key = self.key(task, region, start)
        if key in self.keys:
            return False
        self.keys.add(key)
        self.task.append(int(task)); self.region.append(int(region)); self.start.append(int(start))
        return True

    def arrays(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        return (np.asarray(self.task, dtype=np.int32), np.asarray(self.region, dtype=np.int8),
                np.asarray(self.start, dtype=np.int16))

    def __len__(self) -> int:
        return len(self.task)


def read_data(attach: Path) -> Data:
    workload = pd.read_excel(attach / "workload_trace.xlsx")
    required = {"TaskID", "TaskType", "ArrivalHour", "EstimatedDuration_min", "SourceRegion", "MaxLatency_ms", "LatestFinishHour", "GPU_Demand"}
    missing = required - set(workload.columns)
    if missing:
        raise RuntimeError("workload_trace.xlsx 缺少字段：" + ", ".join(sorted(missing)))
    gpu_info = pd.read_excel(attach / "GPU_information.xlsx", sheet_name="GPU中心基础情况").set_index("Region").loc[list(REGIONS)]
    latency = pd.read_excel(attach / "network_latency.xlsx", sheet_name="network_latency").pivot(index="FromRegion", columns="ToRegion", values="NetworkLatency_ms").loc[list(REGIONS), list(REGIONS)].to_numpy(float)
    pmap = pd.read_excel(attach / "power_mapping.xlsx", sheet_name="任务功率映射").set_index("TaskType")["GPU_Power_MW_per_EquivalentGPU"].to_dict()
    rt = pd.read_excel(attach / "region_time_data.xlsx")
    storage = pd.read_excel(attach / "storage_information.xlsx", sheet_name="storage_information").set_index("Region").loc[list(REGIONS)]
    needed = ["AvailableRenewable_MW", "ElectricityPrice_CNY_per_MWh", "SellPrice_CNY_per_MWh", "CarbonIntensity_tCO2_per_MWh", "NonAI_IT_Load_MW"]
    wide = {name: rt.pivot(index="Hour", columns="Region", values=name).reindex(index=range(H_ENERGY), columns=list(REGIONS)).to_numpy(float).T for name in needed}
    type_names = workload["TaskType"].astype(str).to_numpy()
    type_order = {name: idx for idx, name in enumerate(sorted(pmap))}
    source_names = workload["SourceRegion"].astype(str).to_numpy()
    source = np.asarray([REGIONS.index(x) if x in REGIONS else -1 for x in source_names], dtype=np.int8)
    if np.any(source < 0):
        raise RuntimeError("任务中存在非标准源区域")
    type_idx = np.asarray([type_order[x] for x in type_names], dtype=np.int8)
    alpha = np.asarray([pmap[x] for x in type_names], dtype=float)
    legal = np.empty((len(workload), R), dtype=bool)
    for i, (src, max_latency) in enumerate(zip(source, workload["MaxLatency_ms"].to_numpy(float))):
        legal[i] = latency[src] <= max_latency + 1e-9
    return Data(
        task=workload, type_idx=type_idx, source=source,
        arrival=workload["ArrivalHour"].to_numpy(np.int16), latest=workload["LatestFinishHour"].to_numpy(float),
        duration=workload["EstimatedDuration_min"].to_numpy(float), gpu=workload["GPU_Demand"].to_numpy(float),
        alpha=alpha, legal=legal, pue=gpu_info["PUE"].to_numpy(float),
        gpu_cap=gpu_info["Available_GPU"].to_numpy(float), it_cap=gpu_info["Max_IT_Power_MW"].to_numpy(float),
        non_ai=wide["NonAI_IT_Load_MW"], renew=wide["AvailableRenewable_MW"], price=wide["ElectricityPrice_CNY_per_MWh"],
        sell_price=wide["SellPrice_CNY_per_MWh"], carbon=wide["CarbonIntensity_tCO2_per_MWh"], storage=storage,
    )


def legal_last_start(data: Data, i: int) -> int:
    duration_h = data.duration[i] / 60.0
    return min(H_TASK - 1, int(math.floor(min(data.latest[i], float(H_TASK)) - duration_h + 1e-10)))


def make_presolve_rows(data: Data) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """A: 删除 Facility 重复行，再逐小时应用 GPU/IT 支配关系。"""
    gpu_row = np.full((R, H_TASK), -1, dtype=np.int32)
    it_row = np.full((R, H_TASK), -1, dtype=np.int32)
    rhs: list[float] = []
    kind: list[str] = []
    alpha_min, alpha_max = float(data.alpha.min()), float(data.alpha.max())
    for r in range(R):
        for h in range(H_TASK):
            gcap = data.gpu_cap[r]
            icap = data.it_cap[r] - data.non_ai[r, h]
            if icap >= alpha_max * gcap - 1e-10:
                gpu_row[r, h] = len(rhs); rhs.append(gcap); kind.append("GPU")
            elif icap <= alpha_min * gcap + 1e-10:
                it_row[r, h] = len(rhs); rhs.append(icap); kind.append("IT")
            else:
                gpu_row[r, h] = len(rhs); rhs.append(gcap); kind.append("GPU")
                it_row[r, h] = len(rhs); rhs.append(icap); kind.append("IT")
    return gpu_row, it_row, np.asarray(rhs, dtype=float), np.asarray(kind)


def initial_pool(data: Data) -> ColumnPool:
    """在完整合法域中构造一个 GPU/IT 可行初始排程。

    这只是为 RMP 提供可行起点：后续 pricing 仍检查每一个合法区域和开工
    时刻。按 slack、RT、GPU 需求排序能避免把刚性任务留到最后。
    """
    pool = ColumnPool()
    gpu_load = np.zeros((R, H_TASK), dtype=float)
    ai_load = np.zeros((R, H_TASK), dtype=float)
    it_remaining = data.it_cap[:, None] - data.non_ai[:, :H_TASK]
    task_types = data.task["TaskType"].astype(str).to_numpy()
    order = sorted(range(len(data.task)), key=lambda i: (
        0 if task_types[i] == "RealTimeInference" else 1,
        legal_last_start(data, i) - int(data.arrival[i]),
        -float(data.gpu[i]),
    ))
    for i in tqdm(order, desc="构造资源可行初始排程", unit="任务", leave=False):
        start0, end = int(data.arrival[i]), legal_last_start(data, i)
        starts = np.array([start0], dtype=np.int32) if task_types[i] == "RealTimeInference" else np.arange(start0, end + 1, dtype=np.int32)
        prof = overlap_profile(data.duration[i]); best: tuple[float,int,int] | None = None
        for r in np.flatnonzero(data.legal[i]):
            feasible = np.ones(len(starts), dtype=bool)
            score = np.zeros(len(starts), dtype=float)
            for offset, weight in enumerate(prof):
                hours = starts + offset
                gpu_use = data.gpu[i] * weight; ai_use = gpu_use * data.alpha[i]
                feasible &= gpu_load[r, hours] + gpu_use <= data.gpu_cap[r] + 1e-9
                feasible &= ai_load[r, hours] + ai_use <= it_remaining[r, hours] + 1e-9
                score += gpu_load[r, hours] / max(data.gpu_cap[r], 1e-9)
                score += ai_load[r, hours] / np.maximum(it_remaining[r, hours], 1e-9)
            if feasible.any():
                locs = np.flatnonzero(feasible); local = locs[int(np.argmin(score[locs]))]
                candidate = (float(score[local]), int(r), int(starts[local]))
                if best is None or candidate[0] < best[0]: best = candidate
        if best is None:
            raise RuntimeError(f"无法构造资源可行初始列：TaskID={data.task.iloc[i].TaskID}；完整域仍会保留，需检查容量或附件口径。")
        _, r, s = best; pool.add(i, r, s)
        for offset, weight in enumerate(prof):
            gpu_load[r, s+offset] += data.gpu[i] * weight
            ai_load[r, s+offset] += data.gpu[i] * data.alpha[i] * weight
    return pool


def resource_matrix(pool: ColumnPool, data: Data, gpu_row: np.ndarray, it_row: np.ndarray, nrows: int) -> csr_matrix:
    ti, rr, ss = pool.arrays(); n = len(ti)
    # 每列 1 个指派非零元 + 至多 7 个小时 x 2 条资源行；预分配避免 Python object-per-nnz。
    capacity = n * 15
    rows = np.empty(capacity, dtype=np.int32); cols = np.empty(capacity, dtype=np.int32); vals = np.empty(capacity, dtype=np.float64)
    k = 0
    for j in range(n):
        prof = overlap_profile(data.duration[int(ti[j])]); r, s, task = int(rr[j]), int(ss[j]), int(ti[j])
        for offset, weight in enumerate(prof):
            h = s + offset
            gr, ir = int(gpu_row[r, h]), int(it_row[r, h])
            if gr >= 0:
                rows[k] = gr; cols[k] = j; vals[k] = data.gpu[task] * weight; k += 1
            if ir >= 0:
                rows[k] = ir; cols[k] = j; vals[k] = data.gpu[task] * data.alpha[task] * weight; k += 1
    return coo_matrix((vals[:k], (rows[:k], cols[:k])), shape=(nrows, n)).tocsr()


def assignment_matrix(pool: ColumnPool, task_count: int) -> csr_matrix:
    ti, _, _ = pool.arrays()
    return coo_matrix((np.ones(len(ti)), (ti, np.arange(len(ti)))), shape=(task_count, len(ti))).tocsr()


def task_ai_load(pool: ColumnPool, data: Data, x: np.ndarray) -> np.ndarray:
    ti, rr, ss = pool.arrays(); out = np.zeros((R, H_TASK), dtype=float)
    for j, value in enumerate(x):
        if abs(value) <= 1e-12:
            continue
        task, r, s = int(ti[j]), int(rr[j]), int(ss[j])
        prof = overlap_profile(data.duration[task])
        out[r, s:s + len(prof)] += value * data.gpu[task] * data.alpha[task] * prof
    return out


def facility_load(pool: ColumnPool, data: Data, x: np.ndarray) -> np.ndarray:
    ai = task_ai_load(pool, data, x)
    load = np.empty((R, H_ENERGY), dtype=float)
    load[:, :H_TASK] = data.pue[:, None] * (data.non_ai[:, :H_TASK] + ai)
    load[:, H_TASK] = data.pue * data.non_ai[:, H_TASK]
    return load


def fixed_facility_load(data: Data) -> np.ndarray:
    """不随任务排程改变的 Non-AI 设施负荷。"""
    load = np.empty((R, H_ENERGY), dtype=float)
    load[:, :H_TASK] = data.pue[:, None] * data.non_ai[:, :H_TASK]
    load[:, H_TASK] = data.pue * data.non_ai[:, H_TASK]
    return load


def energy_lp(load: np.ndarray, data: Data, renew_override: np.ndarray | None = None, carbon_budget: float | None = None) -> dict:
    """完整 0..2406h Renewable/BESS/Grid LP，并返回 load-balance 对偶。"""
    names = ("u", "qR", "qG", "d", "gL", "s", "w", "E"); pos = {name: i for i, name in enumerate(names)}; nv = len(names)
    def ix(r: int, h: int, name: str) -> int: return (r * H_ENERGY + h) * nv + pos[name]
    renew = data.renew if renew_override is None else renew_override
    n = R * H_ENERGY * nv; c = np.zeros(n)
    for r in range(R):
        for h in range(H_ENERGY):
            c[ix(r,h,"gL")] = data.price[r,h]; c[ix(r,h,"qG")] = data.price[r,h]; c[ix(r,h,"s")] = -data.sell_price[r,h]
    ae = lil_matrix((3 * R * H_ENERGY, n)); be = np.zeros(3 * R * H_ENERGY); load_row = np.empty((R, H_ENERGY), dtype=np.int32); row = 0
    for r in range(R):
        ce, de = float(data.storage.iloc[r].ChargeEfficiency), float(data.storage.iloc[r].DischargeEfficiency)
        initial = float(data.storage.iloc[r].InitialSOC_MWh)
        for h in range(H_ENERGY):
            for v in ("u", "qR", "s", "w"): ae[row, ix(r,h,v)] = 1
            be[row] = renew[r,h]; row += 1
            for v in ("u", "d", "gL"): ae[row, ix(r,h,v)] = 1
            be[row] = load[r,h]; load_row[r,h] = row; row += 1
            ae[row, ix(r,h,"E")] = 1
            if h: ae[row, ix(r,h-1,"E")] = -1
            else: be[row] = initial
            ae[row, ix(r,h,"qR")] = -ce; ae[row, ix(r,h,"qG")] = -ce; ae[row, ix(r,h,"d")] = 1 / de; row += 1
    au = lil_matrix((2 * R * H_ENERGY + int(carbon_budget is not None), n)); bu = np.zeros(au.shape[0]); row = 0
    lb = np.zeros(n); ub = np.full(n, np.inf)
    for r in range(R):
        st = data.storage.iloc[r]; charge, import_cap = float(st.MaxChargePower_MW), float(st.MaxGridImport_MW)
        for h in range(H_ENERGY):
            au[row, ix(r,h,"qR")] = 1; au[row, ix(r,h,"qG")] = 1; bu[row] = charge; row += 1
            au[row, ix(r,h,"gL")] = 1; au[row, ix(r,h,"qG")] = 1; bu[row] = import_cap; row += 1
            ub[ix(r,h,"d")] = float(st.MaxDischargePower_MW); ub[ix(r,h,"s")] = min(float(st.SellLimit_MW), float(st.MaxGridExport_MW))
            lb[ix(r,h,"E")] = float(st.MinSOC_MWh); ub[ix(r,h,"E")] = float(st.StorageCapacity_MWh)
        lb[ix(r,H_ENERGY-1,"E")] = max(lb[ix(r,H_ENERGY-1,"E")], float(st.InitialSOC_MWh))
    if carbon_budget is not None:
        for r in range(R):
            for h in range(H_ENERGY):
                au[row, ix(r,h,"gL")] = data.carbon[r,h]
                au[row, ix(r,h,"qG")] = data.carbon[r,h]
        bu[row] = carbon_budget
    result = linprog(c, A_ub=csr_matrix(au), b_ub=bu, A_eq=csr_matrix(ae), b_eq=be, bounds=list(zip(lb,ub)), method="highs")
    if not result.success:
        return {"success": False, "message": result.message}
    carbon = sum(data.carbon[r,h] * (result.x[ix(r,h,"gL")] + result.x[ix(r,h,"qG")]) for r in range(R) for h in range(H_ENERGY))
    region_cost = np.zeros(R, dtype=float)
    for r in range(R):
        for h in range(H_ENERGY):
            region_cost[r] += (
                data.price[r, h] * (result.x[ix(r, h, "gL")] + result.x[ix(r, h, "qG")])
                - data.sell_price[r, h] * result.x[ix(r, h, "s")]
            )
    grid_import = np.empty((R, H_ENERGY)); grid_export = np.empty((R, H_ENERGY)); soc = np.empty((R, H_ENERGY))
    for r in range(R):
        for h in range(H_ENERGY):
            grid_import[r,h] = result.x[ix(r,h,"gL")] + result.x[ix(r,h,"qG")]
            grid_export[r,h] = result.x[ix(r,h,"s")]
            soc[r,h] = result.x[ix(r,h,"E")]
    import_cap = data.storage["MaxGridImport_MW"].to_numpy(float)[:,None]
    export_cap = data.storage["MaxGridExport_MW"].to_numpy(float)[:,None]
    sell_cap = data.storage["SellLimit_MW"].to_numpy(float)[:,None]
    min_soc = data.storage["MinSOC_MWh"].to_numpy(float)[:,None]
    max_soc = data.storage["StorageCapacity_MWh"].to_numpy(float)[:,None]
    initial_soc = data.storage["InitialSOC_MWh"].to_numpy(float)
    audit = {
        "最大电网购电越界_MW": float(max(0.0, np.max(grid_import - import_cap))),
        "最大电网上网越界_MW": float(max(0.0, np.max(grid_export - export_cap))),
        "最大售电上限越界_MW": float(max(0.0, np.max(grid_export - sell_cap))),
        "最大SOC下界越界_MWh": float(max(0.0, np.max(min_soc - soc))),
        "最大SOC上界越界_MWh": float(max(0.0, np.max(soc - max_soc))),
        "终端SOC缺口_MWh": float(max(0.0, np.max(initial_soc - soc[:,-1]))),
    }
    return {
        "success": True,
        "cost": float(result.fun),
        "region_cost": region_cost,
        "carbon": float(carbon),
        "lam": result.eqlin.marginals[load_row],
        "audit": audit,
    }


def cut_matrix(pool: ColumnPool, data: Data, cuts: list[Cut]) -> csr_matrix:
    ti, rr, ss = pool.arrays(); n = len(ti)
    if not cuts:
        return csr_matrix((0, n))
    rows: list[np.ndarray] = []; cols: list[np.ndarray] = []; vals: list[np.ndarray] = []
    for q, cut in enumerate(cuts):
        value = np.zeros(n, dtype=float)
        # 每列只占最多 7 个小时；对每个 active column 做短向量积，比扫描
        # 所有 region-hour support 再做布尔筛选更省时，也只写入非零 payload。
        for j in range(n):
            task, r, s = int(ti[j]), int(rr[j]), int(ss[j])
            prof = overlap_profile(data.duration[task])
            value[j] = data.pue[r] * data.gpu[task] * data.alpha[task] * np.dot(cut.lam[r, s:s+len(prof)], prof)
        nz = np.flatnonzero(np.abs(value) > 1e-10)
        if len(nz): rows.append(np.full(len(nz), q, dtype=np.int32)); cols.append(nz.astype(np.int32)); vals.append(value[nz])
    if not rows:
        return csr_matrix((len(cuts), n))
    return coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(len(cuts), n)).tocsr()


def solve_rmp(pool: ColumnPool, data: Data, gpu_row: np.ndarray, it_row: np.ndarray, rhs: np.ndarray, cuts: list[Cut]) -> tuple[dict, csr_matrix, csr_matrix, csr_matrix]:
    ar = assignment_matrix(pool, len(data.task)); resource = resource_matrix(pool, data, gpu_row, it_row, len(rhs)); cm = cut_matrix(pool, data, cuts)
    n = len(pool); zero_r = csr_matrix((len(rhs), 1)); theta = -np.ones((len(cuts), 1))
    aub = vstack([hstack([resource, zero_r]), hstack([cm, csr_matrix(theta)])]).tocsr()
    bub = np.concatenate([rhs, -np.asarray([cut.const for cut in cuts])])
    aeq = hstack([ar, csr_matrix((len(data.task), 1))]).tocsr()
    result = linprog(np.r_[np.zeros(n), 1.0], A_ub=aub, b_ub=bub, A_eq=aeq, b_eq=np.ones(len(data.task)), bounds=[(0,None)]*n+[(-1e10,None)], method="highs")
    if not result.success:
        raise RuntimeError("RMP LP 失败：" + result.message)
    return {"x": result.x[:n], "theta": float(result.x[-1]), "lb": float(result.fun), "eq_dual": result.eqlin.marginals, "ub_dual": result.ineqlin.marginals}, ar, resource, cm


def price_all(pool: ColumnPool, data: Data, gpu_row: np.ndarray, it_row: np.ndarray, rdual: np.ndarray, cdual: np.ndarray, cuts: list[Cut], eqdual: np.ndarray, tol: float) -> list[tuple[int,int,int,float]]:
    """完整域精确定价：每个 task-region 的所有合法整数 start 都参与 min 扫描。"""
    cut_signal = np.zeros((R, H_TASK), dtype=float)
    for dual, cut in zip(cdual, cuts):
        cut_signal += -dual * cut.lam[:, :H_TASK]
    profiles: dict[tuple[int,int,int], np.ndarray] = {}
    for task_type, duration in set(zip(data.type_idx.tolist(), data.duration.tolist())):
        prof = overlap_profile(duration)
        for r in range(R):
            # GPU/IT dual 必须按 task 的 alpha 组合；type 内 alpha 固定。
            example = int(np.flatnonzero(data.type_idx == task_type)[0])
            per_hour = np.zeros(H_TASK)
            for h in range(H_TASK):
                gr, ir = int(gpu_row[r,h]), int(it_row[r,h])
                if gr >= 0: per_hour[h] += -rdual[gr]
                if ir >= 0: per_hour[h] += -rdual[ir] * data.alpha[example]
                per_hour[h] += cut_signal[r,h] * data.pue[r] * data.alpha[example]
            profiles[(task_type, r, int(round(duration * 60)))] = np.convolve(per_hour, prof[::-1], mode="valid")
    active: dict[tuple[int,int], set[int]] = {}
    for task, region, start in zip(*pool.arrays()):
        active.setdefault((int(task), int(region)), set()).add(int(start))
    additions: list[tuple[int,int,int,float]] = []
    iterator = tqdm(range(len(data.task)), desc="完整域精确定价", unit="任务", leave=False)
    task_types = data.task["TaskType"].astype(str).to_numpy()
    for i in iterator:
        start0 = int(data.arrival[i])
        end = start0 if task_types[i] == "RealTimeInference" else legal_last_start(data, i)
        if end < start0:
            raise RuntimeError(f"TaskID={data.task.iloc[i].TaskID} 无合法开工时刻")
        best: tuple[float,int,int] | None = None
        for r in np.flatnonzero(data.legal[i]):
            scores = profiles[(int(data.type_idx[i]), int(r), int(round(data.duration[i] * 60)))][start0:end+1]
            used = {start for start in active.get((i, int(r)), set()) if start0 <= start <= end}
            if len(used) >= len(scores):
                continue
            local = int(np.argmin(scores)); s = start0 + local
            if s in used:
                count = min(len(scores), len(used) + 1)
                candidates = np.argpartition(scores, count - 1)[:count]
                local = min((int(k) for k in candidates if start0 + int(k) not in used), key=lambda k: scores[k])
                s = start0 + local
            score = float(scores[local] * data.gpu[i])
            if best is None or score < best[0]: best = (score, int(r), s)
        if best is None:
            continue
        reduced = best[0] - eqdual[i]
        if reduced < -tol:
            additions.append((i, best[1], best[2], reduced))
    additions.sort(key=lambda item: item[3])
    return additions


def write_checkpoint(out: Path, payload: dict) -> None:
    (out / "checkpoint.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_solver_state(out: Path, pool: ColumnPool, cuts: list[Cut], completed_iter: int, initial_columns: int, incumbent_cost: float) -> None:
    """原子替换压缩数值状态；仅在一轮完整结束后写入。"""
    ti, rr, ss = pool.arrays()
    target, temporary = out / "checkpoint_state.npz", out / "checkpoint_state.tmp.npz"
    lam = np.stack([cut.lam.astype(np.float64) for cut in cuts])
    np.savez_compressed(temporary, task=ti, region=rr, start=ss,
                        cut_const=np.asarray([cut.const for cut in cuts]), cut_lam=lam,
                        completed_iter=np.int32(completed_iter), initial_columns=np.int32(initial_columns),
                        incumbent_cost=np.float64(incumbent_cost))
    temporary.replace(target)


def load_solver_state(out: Path) -> tuple[ColumnPool, list[Cut], int, int, float]:
    state_path = out / "checkpoint_state.npz"
    if not state_path.is_file():
        raise RuntimeError(f"没有找到可恢复状态文件：{state_path}")
    with np.load(state_path, allow_pickle=False) as saved:
        pool = ColumnPool()
        for task, region, start in zip(saved["task"], saved["region"], saved["start"]):
            pool.add(int(task), int(region), int(start))
        cuts = [Cut(float(const), lam.astype(np.float64)) for const, lam in zip(saved["cut_const"], saved["cut_lam"])]
        return pool, cuts, int(saved["completed_iter"]), int(saved["initial_columns"]), float(saved["incumbent_cost"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Q4 全规模 delayed-column Benders solver")
    parser.add_argument("--attachment-dir", type=Path, default=DEFAULT_ATTACH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-iter", type=int, default=25)
    parser.add_argument("--max-hours", type=float, default=8.5)
    parser.add_argument("--max-active-columns", type=int, default=1_000_000)
    parser.add_argument("--max-rss-gib", type=float, default=10.0)
    parser.add_argument("--min-free-gib", type=float, default=12.0)
    parser.add_argument("--price-tol", type=float, default=1e-6)
    parser.add_argument("--benders-tol-cny", type=float, default=1e-3)
    parser.add_argument("--integer-time-limit-s", type=float, default=10800.0)
    parser.add_argument("--resume", action="store_true", help="从 output-dir/checkpoint_state.npz 的完整轮次继续")
    args = parser.parse_args()
    attach, out = args.attachment_dir.resolve(), args.output_dir.resolve(); out.mkdir(parents=True, exist_ok=True)
    vm = psutil.virtual_memory(); free_gib = vm.available / 1024**3
    if free_gib < args.min_free_gib:
        raise SystemExit(f"停止：当前可用内存 {free_gib:.2f} GiB，小于门槛 {args.min_free_gib:.2f} GiB。请关闭 GPT/PyCharm 外的高占用程序后重试。")
    if free_gib < 16:
        print(f"警告：当前可用内存 {free_gib:.2f} GiB，建议至少 16 GiB；程序会严格执行列池/RSS 门槛。")
    process = psutil.Process()
    started = time.time(); data = read_data(attach); gpu_row, it_row, rhs, _ = make_presolve_rows(data)
    if args.resume:
        pool, cuts, completed_iter, initial_columns, incumbent_cost = load_solver_state(out)
        if not len(pool) or not len(cuts):
            raise RuntimeError("检查点缺少活动列或 Benders cut，不能恢复")
        print(f"从第 {completed_iter} 轮后恢复：{len(pool)} 活动列，{len(cuts)} 条 cut")
    else:
        pool = initial_pool(data)
        initial_columns = len(pool)
        initial_load = facility_load(pool, data, np.ones(len(pool)))
        fixed_load = fixed_facility_load(data)
        first = energy_lp(initial_load, data)
        if not first["success"]: raise RuntimeError("资源可行初始排程的能源子问题不可行：" + first["message"])
        cuts = [Cut(const=float(first["cost"] + np.sum(first["lam"] * (fixed_load - initial_load))), lam=first["lam"].copy())]
        incumbent_cost = float(first["cost"]); completed_iter = 0
        save_solver_state(out, pool, cuts, completed_iter, initial_columns, incumbent_cost)
        write_checkpoint(out, {"状态":"INITIALIZED","已完成轮次":0,"活动列数":len(pool),"Benders切数":len(cuts),"完整候选域":"implicit / 未裁剪"})
    incumbent_x = np.r_[np.ones(initial_columns), np.zeros(len(pool)-initial_columns)]
    metrics_path = out / "iteration_metrics.csv"
    file_mode = "a" if args.resume and metrics_path.is_file() else "w"
    with metrics_path.open(file_mode, newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=["iter","active_columns","cuts","lp_lb_cny","energy_cost_cny","theta_cny","violation_cny","new_columns","min_reduced_cost","rss_gib","elapsed_min","eta_min"])
        if file_mode == "w": writer.writeheader()
        root_closed = False; stop_reason = "max_iter"
        bar = tqdm(range(completed_iter + 1, args.max_iter + 1), desc="Q4 Root CG+Benders", unit="轮")
        for iteration in bar:
            if (time.time()-started)/3600 > args.max_hours:
                stop_reason = "max_hours"; break
            if len(pool) >= args.max_active_columns:
                stop_reason = "max_active_columns"; break
            if process.memory_info().rss / 1024**3 > args.max_rss_gib:
                stop_reason = "max_rss_gib"; break
            rmp_t0 = time.time(); rmp, _, _, _ = solve_rmp(pool, data, gpu_row, it_row, rhs, cuts); rmp_s = time.time()-rmp_t0
            load = facility_load(pool, data, rmp["x"]); energy = energy_lp(load, data)
            if not energy["success"]: raise RuntimeError("LP 主问题给出能源不可行负荷：" + energy["message"])
            violation = float(energy["cost"] - rmp["theta"])
            new_columns = 0; min_rc = 0.0
            if violation > args.benders_tol_cny:
                cuts.append(Cut(const=float(energy["cost"] + np.sum(energy["lam"] * (fixed_facility_load(data) - load))), lam=energy["lam"].copy()))
                stop_reason = "added_benders_cut"
            else:
                m = len(rhs); additions = price_all(pool, data, gpu_row, it_row, rmp["ub_dual"][:m], rmp["ub_dual"][m:], cuts, rmp["eq_dual"], args.price_tol)
                new_columns = sum(pool.add(i,r,s) for i,r,s,_ in additions)
                min_rc = float(additions[0][3]) if additions else 0.0
                if not additions:
                    root_closed = True; stop_reason = "root_lp_closed"; 
            elapsed = (time.time()-started)/60; eta = elapsed/iteration*(args.max_iter-iteration) if iteration else 0
            row = {"iter":iteration,"active_columns":len(pool),"cuts":len(cuts),"lp_lb_cny":rmp["lb"],"energy_cost_cny":energy["cost"],"theta_cny":rmp["theta"],"violation_cny":violation,"new_columns":new_columns,"min_reduced_cost":min_rc,"rss_gib":process.memory_info().rss/1024**3,"elapsed_min":elapsed,"eta_min":eta}
            writer.writerow(row); fh.flush(); save_solver_state(out, pool, cuts, iteration, initial_columns, incumbent_cost); write_checkpoint(out, {"状态":"RUNNING","轮次":iteration,"停止原因":stop_reason,"根节点闭合":root_closed,"活动列数":len(pool),"Benders切数":len(cuts),"最新":row,"完整候选域":"implicit / 未裁剪"})
            bar.set_postfix(cols=len(pool), cuts=len(cuts), lb=f"{rmp['lb']:.0f}", new=new_columns, rss=f"{row['rss_gib']:.2f}G", rmp=f"{rmp_s:.1f}s")
            if root_closed: break
    # 仅在 root 闭合后做 restricted integer refinement；它是上界，不把它伪称为全局整数最优。
    integer_status = "未执行：root 未闭合"
    if root_closed:
        rmp, ar, resource, cm = solve_rmp(pool, data, gpu_row, it_row, rhs, cuts); n=len(pool)
        aub=vstack([hstack([resource,csr_matrix((len(rhs),1))]),hstack([cm,csr_matrix(-np.ones((len(cuts),1)))])]).tocsr()
        bub=np.r_[rhs, -np.asarray([cut.const for cut in cuts])]; aeq=hstack([ar,csr_matrix((len(data.task),1))]).tocsr()
        mip=milp(c=np.r_[np.zeros(n),1.0],integrality=np.r_[np.ones(n),0],bounds=Bounds(np.r_[np.zeros(n),-1e10],np.r_[np.ones(n),np.inf]),constraints=[LinearConstraint(aub,-np.inf*np.ones(len(bub)),bub),LinearConstraint(aeq,np.ones(len(data.task)),np.ones(len(data.task)))],options={"time_limit":args.integer_time_limit_s,"mip_rel_gap":1e-5})
        if mip.success:
            candidate=mip.x[:n]; evaluated=energy_lp(facility_load(pool,data,candidate),data)
            if evaluated["success"] and evaluated["cost"] < incumbent_cost: incumbent_cost, incumbent_x = float(evaluated["cost"]), np.rint(candidate)
            integer_status = "restricted_mip_completed"
        else: integer_status = "restricted_mip_incomplete: " + mip.message
    ti, rr, ss = pool.arrays(); chosen = np.flatnonzero(np.asarray(incumbent_x) > 0.5)
    pd.DataFrame({"TaskID":data.task.iloc[ti[chosen]]["TaskID"].to_numpy(),"区域":[REGIONS[int(x)] for x in rr[chosen]],"开工小时":ss[chosen]}).to_csv(out/"best_schedule.csv",index=False,encoding="utf-8-sig")
    summary={"状态":"DRAFT / NEEDS_REVIEW","完整候选域":"未裁剪的 implicit domain","任务数":len(data.task),"候选域总数_预检":233375201,"根节点闭合":root_closed,"停止原因":stop_reason,"Benders闭合容差_CNY":args.benders_tol_cny,"restricted_integer_status":integer_status,"活动列数":len(pool),"Benders切数":len(cuts),"可行上界_能源成本_CNY":incumbent_cost,"运行分钟":(time.time()-started)/60,"峰值当前RSS_GiB":process.memory_info().rss/1024**3,"全局整数最优已证明":False}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8"); write_checkpoint(out,{**summary,"状态":"FINISHED"})
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
