#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Q4 canonical 结果生成 Origin 可直接导入的独立绘图数据。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

REGIONS = ["RegionA", "RegionB", "RegionC", "RegionD", "RegionE", "RegionF"]


def read_inputs(attachment_dir: Path, final_dir: Path):
    gpu = pd.read_excel(attachment_dir / "GPU_information.xlsx", sheet_name="GPU中心基础情况").set_index("Region").loc[REGIONS]
    storage = pd.read_excel(attachment_dir / "storage_information.xlsx", sheet_name="storage_information").set_index("Region").loc[REGIONS]
    rt = pd.read_excel(attachment_dir / "region_time_data.xlsx")
    latency = pd.read_excel(attachment_dir / "network_latency.xlsx", sheet_name="network_latency")
    latency_matrix = latency.pivot(index="FromRegion", columns="ToRegion", values="NetworkLatency_ms").loc[REGIONS, REGIONS]
    schedule = pd.read_csv(final_dir / "q4_字典序最终排程.csv")
    stage_metrics = pd.read_csv(final_dir / "q4_recertification_stage_metrics.csv")
    summary = json.loads((final_dir / "q4_qos_summary.json").read_text(encoding="utf-8"))
    return gpu, storage, rt, latency_matrix, schedule, stage_metrics, summary


def write_region_structure(out: Path, gpu, storage, rt, latency_matrix) -> None:
    grouped = rt.groupby("Region", sort=False)
    rows = []
    for region in REGIONS:
        r = grouped.get_group(region)
        rows.append({
            "类别_区域": region,
            "Y_可用GPU（个）": float(gpu.loc[region, "Available_GPU"]),
            "Y_PUE": float(gpu.loc[region, "PUE"]),
            "Y_储能容量（MWh）": float(storage.loc[region, "StorageCapacity_MWh"]),
            "Y_最大充电功率（MW）": float(storage.loc[region, "MaxChargePower_MW"]),
            "Y_最大放电功率（MW）": float(storage.loc[region, "MaxDischargePower_MW"]),
            "Y_售电上限（MW）": float(storage.loc[region, "SellLimit_MW"]),
            "Y_平均电价（CNY/MWh）": float(r["ElectricityPrice_CNY_per_MWh"].mean()),
            "Y_平均碳强度（tCO2/MWh）": float(r["CarbonIntensity_tCO2_per_MWh"].mean()),
            "Y_平均可再生能源（MW）": float(r["AvailableRenewable_MW"].mean()),
            "Y_平均可达时延（ms）": float(latency_matrix[region].mean()),
        })
    raw = pd.DataFrame(rows)
    raw.to_csv(out / "图A_区域结构原始指标.csv", index=False, encoding="utf-8-sig")
    normalized = raw.copy()
    numeric = [c for c in normalized.columns if c != "类别_区域"]
    for col in numeric:
        values = normalized[col].to_numpy(float)
        lo, hi = float(values.min()), float(values.max())
        normalized[col] = 0.5 if abs(hi - lo) <= 1e-12 else (values - lo) / (hi - lo)
    normalized.columns = ["类别_区域"] + [f"Y_标准化_{c[2:]}" for c in numeric]
    normalized.to_csv(out / "图A_区域结构标准化热图.csv", index=False, encoding="utf-8-sig")


def write_recertification(out: Path, stage_metrics: pd.DataFrame) -> None:
    stages = stage_metrics.copy()
    stage_map = {"Cost再认证": "Cost", "Wait再认证": "Wait", "Latency再认证": "Latency"}
    stages["类别_阶段"] = stages["阶段"].map(stage_map).fillna(stages["阶段"].astype(str))
    stages.insert(0, "X_阶段序号", np.arange(1, len(stages) + 1))
    anchor = stages[["X_阶段序号", "类别_阶段"]].copy()
    anchor["Y_Cost锚点（CNY）"] = np.where(anchor["类别_阶段"].eq("Cost"), stages["LP界"], np.nan)
    anchor["Y_Wait锚点（h）"] = np.where(anchor["类别_阶段"].eq("Wait"), stages["LP界"], np.nan)
    anchor["Y_Latency锚点（ms）"] = np.where(anchor["类别_阶段"].eq("Latency"), stages["LP界"], np.nan)
    anchor.to_csv(out / "图D_最终再认证锚点.csv", index=False, encoding="utf-8-sig")
    closure = stages[["X_阶段序号", "类别_阶段"]].copy()
    closure["Y_活动列数（列）"] = stages["活动列数"]
    closure["Y_Benders切数（条）"] = stages["Benders切数"]
    closure["Y_最小缺失列约化成本（CNY）"] = stages["最小缺失列约化成本"]
    closure["Y_最大区域违反（CNY）"] = stages["最大区域违反_CNY"]
    closure.to_csv(out / "图D_再认证闭合证据.csv", index=False, encoding="utf-8-sig")


def write_migration(out: Path, schedule: pd.DataFrame) -> None:
    matrix = schedule.pivot_table(index="源区域", columns="目标区域", values="TaskID", aggfunc="count", fill_value=0).reindex(index=REGIONS, columns=REGIONS, fill_value=0)
    matrix.index.name = "类别_源区域"
    matrix.columns = [f"Y_目标{region}（任务数）" for region in matrix.columns]
    matrix.reset_index().to_csv(out / "图C_区域迁移矩阵.csv", index=False, encoding="utf-8-sig")
    type_rows = []
    for task_type, group in schedule.groupby("任务类型", sort=True):
        total = len(group)
        moved = int(group["是否迁移"].astype(str).str.lower().isin(["true", "1"]).sum())
        type_rows.append({"类别_任务类型": task_type, "Y_任务数（个）": total, "Y_迁移数（个）": moved, "Y_迁移率（%）": 100.0 * moved / total if total else 0.0})
    pd.DataFrame(type_rows).to_csv(out / "图C_任务类型迁移.csv", index=False, encoding="utf-8-sig")


def write_distributions(out: Path, schedule: pd.DataFrame) -> None:
    wait = schedule["等待_h"].astype(float)
    labels = ["0", "(0,1]", "(1,2]", ">2"]
    wait_bins = pd.cut(wait, bins=[-1e-12, 0, 1, 2, np.inf], labels=labels, include_lowest=True, right=True)
    wait_counts = wait_bins.value_counts().reindex(labels, fill_value=0)
    pd.DataFrame({"类别_等待区间（h）": labels, "Y_任务数（个）": wait_counts.to_numpy()}).to_csv(out / "图E_等待分布.csv", index=False, encoding="utf-8-sig")
    latency = schedule["时延_ms"].astype(float)
    labels = ["<=5", "(5,10]", "(10,20]", "(20,40]", "(40,60]", ">60"]
    latency_bins = pd.cut(latency, bins=[-np.inf, 5, 10, 20, 40, 60, np.inf], labels=labels, right=True)
    counts = latency_bins.value_counts().reindex(labels, fill_value=0)
    pd.DataFrame({"类别_时延区间（ms）": labels, "Y_任务数（个）": counts.to_numpy()}).to_csv(out / "图E_时延分布.csv", index=False, encoding="utf-8-sig")


def write_six_metric_template(out: Path, summary: dict) -> None:
    pd.DataFrame([{
        "类别_场景": "canonical_final_pool",
        "Y_能源成本（CNY）": summary["最终真实能源成本_CNY"],
        "Y_总等待（h）": summary["best-known integer Wait anchor_h"],
        "Y_总时延（ms）": summary["best-known integer Latency anchor_ms"],
        "Y_碳排放（tCO2）": np.nan,
        "Y_可再生能源利用率（%）": np.nan,
        "Y_系统峰值净购电（MW）": np.nan,
        "类别_数据状态": "待补六指标正式能源统计",
    }]).to_csv(out / "图F_六指标场景对比_待补正式场景.csv", index=False, encoding="utf-8-sig")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attachment-dir", type=Path, default=Path(r"D:\qq文件\2026年武汉理工大学数学建模训练题目7-9\C题附件"))
    parser.add_argument("--final-dir", type=Path, default=Path(r"D:\第三次训练赛-worktrees\q4\modules\50_q4\results\qos_final_recertification"))
    parser.add_argument("--output-dir", type=Path, default=Path(r"D:\第三次训练赛-worktrees\q4\modules\50_q4\figures\editable"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    gpu, storage, rt, latency, schedule, metrics, summary = read_inputs(args.attachment_dir, args.final_dir)
    write_region_structure(args.output_dir, gpu, storage, rt, latency)
    write_recertification(args.output_dir, metrics)
    write_migration(args.output_dir, schedule)
    write_distributions(args.output_dir, schedule)
    write_six_metric_template(args.output_dir, summary)
    print(json.dumps({"状态": "完成", "输出目录": str(args.output_dir), "文件数": len(list(args.output_dir.glob("*.csv")))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
