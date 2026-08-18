#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q4 正式场景联合优化驱动器。

场景只改变附件参数或能源碳预算，求解仍调用同一份 full-domain
workload--energy--storage 联合模型。默认只列出协议；使用 --run 才启动长时间计算。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q4_full_solver as solver  # noqa: E402

REGIONS = tuple(solver.REGIONS)
SCENARIOS = [
    {"id": "carbon_100", "kind": "carbon", "fraction": 1.00, "description": "canonical 碳预算"},
    {"id": "carbon_75", "kind": "carbon", "fraction": 0.75, "description": "canonical 碳预算 75%"},
    {"id": "carbon_50", "kind": "carbon", "fraction": 0.50, "description": "canonical 碳预算 50%"},
    {"id": "carbon_25", "kind": "carbon", "fraction": 0.25, "description": "canonical 碳预算 25%"},
    {"id": "price_attachment", "kind": "price", "mode": "attachment", "description": "附件逐时价格"},
    {"id": "price_flat", "kind": "price", "mode": "flat", "description": "区域均值平价"},
    {"id": "price_peak_valley", "kind": "price", "mode": "peak_valley", "description": "峰谷透明敏感性，峰值+25%，谷值-25%"},
    {"id": "renew_nominal", "kind": "renewable", "mode": "nominal", "description": "附件名义新能源"},
    {"id": "renew_down_80", "kind": "renewable", "mode": "down_80", "description": "统一下调 20%"},
    {"id": "renew_up_120", "kind": "renewable", "mode": "up_120", "description": "统一上调 20%"},
]


def scenario_by_id(sid: str) -> dict:
    for item in SCENARIOS:
        if item["id"] == sid:
            return dict(item)
    raise KeyError(f"未知场景: {sid}")


def rewrite_region_time(src: Path, dst: Path, spec: dict) -> None:
    """复制附件并只修改 region_time_data.xlsx 中的显式场景列。"""
    shutil.copytree(src, dst, dirs_exist_ok=True)
    if spec["kind"] not in {"price", "renewable"}:
        return
    path = dst / "region_time_data.xlsx"
    book = pd.ExcelFile(path)
    sheets = {name: pd.read_excel(path, sheet_name=name) for name in book.sheet_names}
    frame = sheets[book.sheet_names[0]].copy()
    if spec["kind"] == "price":
        col = "ElectricityPrice_CNY_per_MWh"
        if spec["mode"] == "flat":
            frame[col] = frame.groupby("Region")[col].transform("mean")
        elif spec["mode"] == "peak_valley":
            q25 = frame.groupby("Region")[col].transform(lambda x: x.quantile(0.25))
            q75 = frame.groupby("Region")[col].transform(lambda x: x.quantile(0.75))
            frame[col] = np.where(frame[col] >= q75, frame[col] * 1.25,
                                  np.where(frame[col] <= q25, frame[col] * 0.75, frame[col]))
    else:
        col = "AvailableRenewable_MW"
        if spec["mode"] == "down_80":
            frame[col] = frame[col] * 0.80
        elif spec["mode"] == "up_120":
            frame[col] = frame[col] * 1.20
    sheets[book.sheet_names[0]] = frame
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, data in sheets.items():
            data.to_excel(writer, sheet_name=name, index=False)


def canonical_carbon(attachment_dir: Path, final_dir: Path) -> float:
    data = solver.read_data(attachment_dir)
    schedule = pd.read_csv(final_dir / "q4_字典序最终排程.csv")
    task_index = {int(v): i for i, v in enumerate(data.task.TaskID.to_numpy())}
    region_index = {name: i for i, name in enumerate(REGIONS)}
    pool = solver.ColumnPool()
    for row in schedule.itertuples(index=False):
        pool.add(task_index[int(row.TaskID)], region_index[str(row.目标区域)], int(row.开工小时))
    load = solver.facility_load(pool, data, np.ones(len(pool)))
    result = solver.energy_lp(load, data)
    if not result["success"]:
        raise RuntimeError("canonical 碳锚点能源 LP 不可行")
    return float(result["carbon"])


def run_solver(spec: dict, attachment_dir: Path, output_dir: Path, carbon_budget: float | None,
               max_hours: float, min_free_gib: float) -> dict:
    """在当前进程中调用同一 full solver；碳预算通过受控 wrapper 注入。"""
    original_energy = solver.energy_lp
    original_linprog = solver.linprog
    capture = {"inside": False, "context": None, "result": None, "lp": None}

    def capture_linprog(*args, **kwargs):
        result = original_linprog(*args, **kwargs)
        if capture["inside"]:
            capture["lp"] = result
        return result

    def wrapped_energy(load, data, renew_override=None, carbon_budget=None):
        budget = carbon_budget if carbon_budget is not None else carbon_budget_outer
        capture["context"] = (np.asarray(load, dtype=float).copy(), data, renew_override, budget)
        capture["inside"] = True
        try:
            result = original_energy(load, data, renew_override=renew_override, carbon_budget=budget)
            capture["result"] = result
            return result
        finally:
            capture["inside"] = False

    carbon_budget_outer = None if carbon_budget is None else float(carbon_budget)
    solver.linprog = capture_linprog
    solver.energy_lp = wrapped_energy
    old_argv = sys.argv[:]
    try:
        sys.argv = [str(HERE / "q4_full_solver.py"), "--attachment-dir", str(attachment_dir),
                    "--output-dir", str(output_dir), "--max-hours", str(max_hours),
                    "--min-free-gib", str(min_free_gib)]
        solver.main()
    finally:
        sys.argv = old_argv
        solver.energy_lp = original_energy
        solver.linprog = original_linprog
    summary = output_dir / "summary.json"
    result = json.loads(summary.read_text(encoding="utf-8")) if summary.is_file() else {"状态": "未生成 summary"}
    result["六指标"] = write_metrics(spec, attachment_dir, output_dir, capture, result)
    return result


def write_metrics(spec: dict, attachment_dir: Path, output_dir: Path, capture: dict, summary: dict) -> dict:
    schedule_path = output_dir / "best_schedule.csv"
    if not schedule_path.is_file() or capture["context"] is None or capture["lp"] is None:
        return {"状态": "缺少最终排程或能源 LP 证据"}
    data = solver.read_data(attachment_dir)
    schedule = pd.read_csv(schedule_path)
    task_map = data.task.set_index("TaskID")
    starts = schedule["开工小时"].to_numpy(float)
    task_ids = schedule["TaskID"].astype(int).to_numpy()
    arrival = task_map.loc[task_ids, "ArrivalHour"].to_numpy(float)
    waits = np.maximum(starts - arrival, 0.0)
    source = task_map.loc[task_ids, "SourceRegion"].astype(str).to_numpy()
    target = schedule["区域"].astype(str).to_numpy()
    latency = pd.read_excel(attachment_dir / "network_latency.xlsx", sheet_name="network_latency")
    lat = latency.pivot(index="FromRegion", columns="ToRegion", values="NetworkLatency_ms")
    latencies = np.asarray([float(lat.loc[s, t]) for s, t in zip(source, target)], dtype=float)
    load, _, renew_override, _ = capture["context"]
    lp = capture["lp"]
    names = ("u", "qR", "qG", "d", "gL", "s", "w", "E")
    pos = {name: i for i, name in enumerate(names)}
    nv = len(names)
    def ix(r: int, h: int, name: str) -> int:
        return (r * solver.H_ENERGY + h) * nv + pos[name]
    renew = data.renew if renew_override is None else renew_override
    curtailed = np.asarray([lp.x[ix(r, h, "w")] for r in range(solver.R) for h in range(solver.H_ENERGY)])
    imports = np.asarray([lp.x[ix(r, h, "gL")] + lp.x[ix(r, h, "qG")] for r in range(solver.R) for h in range(solver.H_ENERGY)]).reshape(solver.R, solver.H_ENERGY)
    exports = np.asarray([lp.x[ix(r, h, "s")] for r in range(solver.R) for h in range(solver.H_ENERGY)]).reshape(solver.R, solver.H_ENERGY)
    metrics = {
        "类别_场景": spec["id"],
        "类别_求解状态": summary.get("状态", "未知"),
        "Y_能源成本（CNY）": float(capture["result"].get("cost", np.nan)),
        "Y_碳排放（tCO2）": float(capture["result"].get("carbon", np.nan)),
        "Y_总等待（h）": float(waits.sum()),
        "Y_平均等待（h）": float(waits.mean()),
        "Y_P95等待（h）": float(np.percentile(waits, 95)),
        "Y_最大等待（h）": float(waits.max(initial=0.0)),
        "Y_总时延（ms）": float(latencies.sum()),
        "Y_平均时延（ms）": float(latencies.mean()),
        "Y_P95时延（ms）": float(np.percentile(latencies, 95)),
        "Y_最大时延（ms）": float(latencies.max(initial=0.0)),
        "Y_可再生能源利用率（%）": float(100.0 * (renew.sum() - curtailed.sum()) / max(renew.sum(), 1e-12)),
        "Y_系统峰值净购电（MW）": float(np.max(imports - exports)),
        "Y_迁移任务数（个）": int(np.sum(source != target)),
        "Y_任务数（个）": int(len(schedule)),
    }
    pd.DataFrame([metrics]).to_csv(output_dir / "q4_six_metrics.csv", index=False, encoding="utf-8-sig")
    aggregate = output_dir.parent / "q4_formal_six_metrics.csv"
    old = pd.read_csv(aggregate) if aggregate.is_file() else pd.DataFrame()
    pd.concat([old, pd.DataFrame([metrics])], ignore_index=True).drop_duplicates(subset=["类别_场景"], keep="last").to_csv(aggregate, index=False, encoding="utf-8-sig")
    return metrics


def write_protocol(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "q4_formal_scenario_protocol.json").write_text(
        json.dumps({"版本": "formal_joint_v1", "场景": SCENARIOS,
                    "约束": ["每个场景重新运行 full-domain joint model", "不固定 canonical 排程", "不声称全局整数最优"]},
                   ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--run", action="store_true", help="启动单个正式场景")
    parser.add_argument("--scenario-id")
    parser.add_argument("--attachment-dir", type=Path, default=solver.DEFAULT_ATTACH)
    parser.add_argument("--canonical-final-dir", type=Path,
                        default=HERE.parent / "results" / "qos_final_recertification")
    parser.add_argument("--output-root", type=Path,
                        default=HERE.parent / "results" / "formal_scenarios")
    parser.add_argument("--max-hours", type=float, default=8.5)
    parser.add_argument("--min-free-gib", type=float, default=12.0,
                        help="传给 full solver 的最低可用内存门槛；默认 12 GiB")
    args = parser.parse_args()
    protocol_dir = args.output_root.resolve()
    write_protocol(protocol_dir)
    if args.list or not args.run:
        print(json.dumps({"协议": "formal_joint_v1", "场景": SCENARIOS,
                          "提示": "先审阅协议，再用 --run --scenario-id <id> 启动单个场景"},
                         ensure_ascii=False, indent=2))
        return
    if not args.scenario_id:
        raise SystemExit("--run 必须同时提供 --scenario-id")
    spec = scenario_by_id(args.scenario_id)
    scenario_dir = protocol_dir / spec["id"]
    attach_dir = scenario_dir / "attachment"
    out_dir = scenario_dir / "solver"
    rewrite_region_time(args.attachment_dir.resolve(), attach_dir, spec)
    budget = None
    if spec["kind"] == "carbon":
        anchor = canonical_carbon(args.attachment_dir.resolve(), args.canonical_final_dir.resolve())
        budget = max(0.0, anchor * float(spec["fraction"]))
        (scenario_dir / "carbon_anchor.json").write_text(
            json.dumps({"canonical_carbon_tCO2": anchor, "fraction": spec["fraction"],
                        "budget_tCO2": budget, "inactive": anchor <= 1e-9},
                       ensure_ascii=False, indent=2), encoding="utf-8")
    summary = run_solver(spec, attach_dir, out_dir, budget, args.max_hours, args.min_free_gib)
    print(json.dumps({"场景": spec, "输出目录": str(out_dir), "summary": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
