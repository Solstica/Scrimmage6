#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q4 四个相对碳预算的零碳退化证书。

只复核 canonical 最终排程一次：若真实 Energy/BESS/Grid LP 的 Carbon <= tol，
则 carbon_100/75/50/25 的预算全部等于 0，四个场景具有同一可行子集
{Carbon = 0}。canonical 字典序代表解已经在更大的原可行域上达到 Cost 锚点、
Wait=0 和最终 Latency 锚点，因此无需重复求四次联合模型。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q4_full_solver as fs  # noqa: E402

FRACTIONS = (1.00, 0.75, 0.50, 0.25)
IDS = ("carbon_100", "carbon_75", "carbon_50", "carbon_25")


def pick_col(frame: pd.DataFrame, *names: str) -> str:
    for name in names:
        if name in frame.columns:
            return name
    raise KeyError(f"缺少字段，候选={names}，实际={list(frame.columns)}")


def build_pool(data, schedule: pd.DataFrame) -> fs.ColumnPool:
    task_col = pick_col(schedule, "TaskID")
    region_col = pick_col(schedule, "目标区域", "区域", "ExecutionRegion")
    start_col = pick_col(schedule, "开工小时", "StartHour")
    task_index = {int(v): i for i, v in enumerate(data.task.TaskID.to_numpy())}
    region_index = {name: i for i, name in enumerate(fs.REGIONS)}
    if len(schedule) != len(data.task) or schedule[task_col].nunique() != len(data.task):
        raise RuntimeError("canonical 最终排程不是每任务恰好一行")
    pool = fs.ColumnPool()
    for row in schedule.itertuples(index=False):
        tid = int(getattr(row, task_col))
        region = str(getattr(row, region_col))
        start = int(getattr(row, start_col))
        pool.add(task_index[tid], region_index[region], start)
    return pool


def task_metrics(data, schedule: pd.DataFrame) -> dict:
    task_col = pick_col(schedule, "TaskID")
    region_col = pick_col(schedule, "目标区域", "区域", "ExecutionRegion")
    start_col = pick_col(schedule, "开工小时", "StartHour")
    ids = schedule[task_col].astype(int).to_numpy()
    task_map = data.task.set_index("TaskID")
    arrival = task_map.loc[ids, "ArrivalHour"].to_numpy(float)
    starts = schedule[start_col].to_numpy(float)
    waits = np.maximum(starts - arrival, 0.0)
    source = task_map.loc[ids, "SourceRegion"].astype(str).to_numpy()
    target = schedule[region_col].astype(str).to_numpy()

    if "时延_ms" in schedule.columns:
        latency = schedule["时延_ms"].to_numpy(float)
    elif "Latency_ms" in schedule.columns:
        latency = schedule["Latency_ms"].to_numpy(float)
    else:
        lat = pd.read_excel(data.attachment_dir / "network_latency.xlsx", sheet_name="network_latency")
        piv = lat.pivot(index="FromRegion", columns="ToRegion", values="NetworkLatency_ms")
        latency = np.asarray([float(piv.loc[s, t]) for s, t in zip(source, target)], dtype=float)

    return {
        "总等待_h": float(waits.sum()),
        "平均等待_h": float(waits.mean()),
        "P95等待_h": float(np.percentile(waits, 95)),
        "最大等待_h": float(waits.max(initial=0.0)),
        "总时延_ms": float(latency.sum()),
        "平均时延_ms": float(latency.mean()),
        "P95时延_ms": float(np.percentile(latency, 95)),
        "最大时延_ms": float(latency.max(initial=0.0)),
        "迁移任务数": int(np.sum(source != target)),
        "迁移率": float(np.mean(source != target)),
    }


def energy_metrics(load: np.ndarray, data) -> dict:
    original = fs.linprog
    captured = {"lp": None}

    def wrapper(*args, **kwargs):
        ans = original(*args, **kwargs)
        captured["lp"] = ans
        return ans

    fs.linprog = wrapper
    try:
        energy = fs.energy_lp(load, data)
    finally:
        fs.linprog = original
    if not energy["success"] or captured["lp"] is None:
        raise RuntimeError("canonical Energy/BESS/Grid LP 复核失败")

    lp = captured["lp"]
    names = ("u", "qR", "qG", "d", "gL", "s", "w", "E")
    pos = {name: i for i, name in enumerate(names)}
    nv = len(names)

    def ix(r: int, h: int, name: str) -> int:
        return (r * fs.H_ENERGY + h) * nv + pos[name]

    curtailed = np.zeros((fs.R, fs.H_ENERGY), dtype=float)
    net_import = np.zeros((fs.R, fs.H_ENERGY), dtype=float)
    for r in range(fs.R):
        for h in range(fs.H_ENERGY):
            curtailed[r, h] = lp.x[ix(r, h, "w")]
            grid_buy = lp.x[ix(r, h, "gL")] + lp.x[ix(r, h, "qG")]
            sell = lp.x[ix(r, h, "s")]
            net_import[r, h] = grid_buy - sell

    regional_peak = {
        str(fs.REGIONS[r]): float(max(0.0, np.max(net_import[r])))
        for r in range(fs.R)
    }
    renewable_util = 100.0 * (float(data.renew.sum()) - float(curtailed.sum())) / max(float(data.renew.sum()), 1e-12)
    return {
        "Cost_CNY": float(energy["cost"]),
        "Carbon_tCO2": float(energy["carbon"]),
        "RenewableUtilization_pct": float(renewable_util),
        "PeakNetImport_MW": float(max(regional_peak.values())),
        "RegionalPeakNetImport_MW": regional_peak,
        "能源审计": energy.get("audit", {}),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Q4 四个相对碳预算退化证书")
    p.add_argument("--attachment-dir", type=Path, default=fs.DEFAULT_ATTACH)
    p.add_argument("--canonical-dir", type=Path,
                   default=HERE.parent / "results" / "qos_final_recertification")
    p.add_argument("--output-dir", type=Path,
                   default=HERE.parent / "results" / "formal_scenarios" / "carbon_degeneracy")
    p.add_argument("--carbon-zero-tol", type=float, default=1e-9)
    args = p.parse_args()

    attach = args.attachment_dir.resolve()
    canonical = args.canonical_dir.resolve()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    data = fs.read_data(attach)
    # 供 task_metrics 无需猜附件目录
    try:
        data.attachment_dir = attach
    except Exception:
        pass
    schedule = pd.read_csv(canonical / "q4_字典序最终排程.csv")
    pool = build_pool(data, schedule)
    x = np.ones(len(pool), dtype=float)
    load = fs.facility_load(pool, data, x)
    em = energy_metrics(load, data)
    tm = task_metrics(data, schedule)

    carbon = float(em["Carbon_tCO2"])
    degenerate = bool(abs(carbon) <= args.carbon_zero_tol)
    rows = []
    for sid, frac in zip(IDS, FRACTIONS):
        budget = float(max(0.0, frac * carbon))
        rows.append({
            "场景": sid,
            "碳预算比例": frac,
            "碳预算_tCO2": budget,
            "Cost_CNY": em["Cost_CNY"],
            "Carbon_tCO2": carbon,
            "总等待_h": tm["总等待_h"],
            "平均时延_ms": tm["平均时延_ms"],
            "RenewableUtilization_pct": em["RenewableUtilization_pct"],
            "PeakNetImport_MW": em["PeakNetImport_MW"],
            "迁移率": tm["迁移率"],
            "证书状态": "DEGENERATE_EQUIVALENT_PASS" if degenerate else "NOT_DEGENERATE",
        })

    result = {
        "状态": "PASS" if degenerate else "NOT_DEGENERATE",
        "canonical_carbon_tCO2": carbon,
        "carbon_zero_tol": args.carbon_zero_tol,
        "退化成立": degenerate,
        "数学说明": (
            "若 canonical Carbon=0，则四个相对预算均为 Carbon<=0；因 Carbon>=0，"
            "四场景具有同一零碳可行子集。canonical 字典序代表解在更大的原可行域上已达到 Cost 锚点，"
            "且 Wait=0，因此该解在四个碳预算下仍保持 Cost/Wait 锚点；无需重复四次联合求解。"
        ),
        "能源指标": em,
        "任务指标": tm,
        "场景": rows,
    }
    (out / "carbon_degeneracy_certificate.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(rows).to_csv(out / "carbon_degeneracy_six_metrics.csv", index=False, encoding="utf-8-sig")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not degenerate:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
