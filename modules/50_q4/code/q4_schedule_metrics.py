#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对任意 Q4 任务排程重求真实 Energy/BESS/Grid LP，并输出题面六指标。

用途：场景 Cost/Wait/Latency 已有证书时，不重跑联合优化，只对最终/候选整数排程
统一复核 Cost、Carbon、Latency、QoS、RenewableUtilization、PeakNetImport 与硬约束。
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
import q4_qos_refinement as qr  # noqa: E402


def col(df: pd.DataFrame, *names: str) -> str:
    for name in names:
        if name in df.columns:
            return name
    raise KeyError(f"找不到字段 {names}；实际字段={list(df.columns)}")


def build(data, schedule: pd.DataFrame):
    tid_col = col(schedule, "TaskID")
    reg_col = col(schedule, "目标区域", "区域", "ExecutionRegion")
    start_col = col(schedule, "开工小时", "StartHour")
    tids = schedule[tid_col].astype(int).to_numpy()
    if len(schedule) != len(data.task) or len(np.unique(tids)) != len(data.task):
        raise RuntimeError("排程必须覆盖全部任务且每任务恰好一行")
    imap = {int(v): i for i, v in enumerate(data.task.TaskID.to_numpy())}
    rmap = {str(v): i for i, v in enumerate(fs.REGIONS)}
    if set(tids) != set(imap):
        raise RuntimeError("排程 TaskID 集合与附件不一致")
    pool = fs.ColumnPool()
    for row in schedule.itertuples(index=False):
        pool.add(imap[int(getattr(row, tid_col))], rmap[str(getattr(row, reg_col))], int(getattr(row, start_col)))
    return pool, tid_col, reg_col, start_col


def solve_energy_with_flows(load: np.ndarray, data):
    original = fs.linprog
    captured = {"lp": None}
    def wrapper(*args, **kwargs):
        ans = original(*args, **kwargs); captured["lp"] = ans; return ans
    fs.linprog = wrapper
    try:
        energy = fs.energy_lp(load, data)
    finally:
        fs.linprog = original
    if not energy["success"] or captured["lp"] is None:
        raise RuntimeError("真实 Energy/BESS/Grid LP 失败")
    return energy, captured["lp"]


def main() -> None:
    p = argparse.ArgumentParser(description="Q4 排程六指标快速复核")
    p.add_argument("--attachment-dir", type=Path, required=True)
    p.add_argument("--schedule", type=Path, required=True)
    p.add_argument("--scenario-id", default="scenario")
    p.add_argument("--output", type=Path, required=True, help="输出 JSON；同目录同时生成 CSV")
    a = p.parse_args()

    attach = a.attachment_dir.resolve(); schedule_path = a.schedule.resolve(); out = a.output.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    data = fs.read_data(attach)
    schedule = pd.read_csv(schedule_path)
    pool, tid_col, reg_col, start_col = build(data, schedule)
    x = np.ones(len(pool), dtype=float)
    load = fs.facility_load(pool, data, x)
    energy, lp = solve_energy_with_flows(load, data)

    # 任务侧 QoS / latency
    ids = schedule[tid_col].astype(int).to_numpy()
    task_map = data.task.set_index("TaskID")
    arrival = task_map.loc[ids, "ArrivalHour"].to_numpy(float)
    starts = schedule[start_col].to_numpy(float)
    waits = np.maximum(starts - arrival, 0.0)
    source = task_map.loc[ids, "SourceRegion"].astype(str).to_numpy()
    target = schedule[reg_col].astype(str).to_numpy()
    lat_df = pd.read_excel(attach / "network_latency.xlsx", sheet_name="network_latency")
    lat_piv = lat_df.pivot(index="FromRegion", columns="ToRegion", values="NetworkLatency_ms")
    latencies = np.asarray([float(lat_piv.loc[s, t]) for s, t in zip(source, target)], dtype=float)

    # 能源流用于新能源利用率与 peak net import
    names = ("u", "qR", "qG", "d", "gL", "s", "w", "E"); pos = {v: i for i, v in enumerate(names)}; nv = len(names)
    def ix(r: int, h: int, name: str) -> int:
        return (r * fs.H_ENERGY + h) * nv + pos[name]
    curtailed = np.zeros((fs.R, fs.H_ENERGY)); net = np.zeros((fs.R, fs.H_ENERGY))
    for r in range(fs.R):
        for h in range(fs.H_ENERGY):
            curtailed[r,h] = lp.x[ix(r,h,"w")]
            net[r,h] = lp.x[ix(r,h,"gL")] + lp.x[ix(r,h,"qG")] - lp.x[ix(r,h,"s")]
    renewable_util = 100.0 * (float(data.renew.sum()) - float(curtailed.sum())) / max(float(data.renew.sum()), 1e-12)
    regional_peak = {str(fs.REGIONS[r]): float(max(0.0, np.max(net[r]))) for r in range(fs.R)}

    # 统一硬约束审计
    gpu, it, rhs, _ = qr.make_presolve_rows(data)
    latency_raw = qr.read_latency(attach)
    _, audit = qr.audit_solution(pool, data, x, gpu, it, rhs, latency_raw, energy)
    audit_pass = all(float(v) <= 1e-7 for v in audit.values())

    metrics = {
        "场景": a.scenario_id,
        "Cost_CNY": float(energy["cost"]),
        "Carbon_tCO2": float(energy["carbon"]),
        "TotalWait_h": float(waits.sum()),
        "MeanWait_h": float(waits.mean()),
        "P95Wait_h": float(np.percentile(waits,95)),
        "MaxWait_h": float(waits.max(initial=0.0)),
        "TotalLatency_ms": float(latencies.sum()),
        "MeanLatency_ms": float(latencies.mean()),
        "P95Latency_ms": float(np.percentile(latencies,95)),
        "MaxLatency_ms": float(latencies.max(initial=0.0)),
        "RenewableUtilization_pct": float(renewable_util),
        "PeakNetImport_MW": float(max(regional_peak.values())),
        "RegionalPeakNetImport_MW": regional_peak,
        "MigrationCount": int(np.sum(source != target)),
        "MigrationRate_pct": float(100.0 * np.mean(source != target)),
        "TaskCount": int(len(schedule)),
        "HardAuditPass": bool(audit_pass),
        "HardAudit": audit,
        "Schedule": str(schedule_path),
        "AttachmentDir": str(attach),
    }
    out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    flat = {k:v for k,v in metrics.items() if not isinstance(v, dict)}
    pd.DataFrame([flat]).to_csv(out.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    if not audit_pass:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
