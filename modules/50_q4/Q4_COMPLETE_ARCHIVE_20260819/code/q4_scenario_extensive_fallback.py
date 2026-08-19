#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在区域 multi-cut 停滞后直接求 renew_down_80 的能源一体化 Cost MIP。

该脚本只使用已保存的 full-pool checkpoint，输出独立于原求解目录；
它生成真实能源可行整数候选，但如果没有完整域 LP 闭合，不把候选包装成 Cost 证书。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q4_qos_refinement as qos  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--attachment-dir", type=Path, required=True)
    p.add_argument("--time-limit-s", type=float, default=300.0)
    p.add_argument("--mip-rel-gap", type=float, default=1e-5)
    p.add_argument("--canonical-final-dir", type=Path, default=HERE.parent / "results" / "qos_final_recertification")
    args = p.parse_args()
    inp = args.input_dir.resolve(); out = args.output_dir.resolve(); out.mkdir(parents=True, exist_ok=True)
    data = qos.read_data(args.attachment_dir.resolve())
    pool, _, stage, stage_iter, _, _, _ = qos.load_state(inp)
    gpu, it, rhs, _ = qos.make_presolve_rows(data)
    latency = qos.read_latency(args.attachment_dir.resolve())
    assign = qos.assignment_matrix(pool, len(data.task))
    resource = qos.resource_matrix(pool, data, gpu, it, len(rhs))
    wait, _ = qos.pool_values(pool, data, latency)
    spec = qos.StageSpec("renew_down_80 Cost直接能源MIP", "cost", None)
    started = time.time()
    print(f"[直接MIP] 活动列={len(pool)}，来自第{stage_iter}轮区域多切断点；时限={args.time_limit_s:g}s", flush=True)
    result = qos.solve_extensive_mip(pool, data, assign, resource, rhs, np.zeros(len(pool)), wait, spec, args.time_limit_s, args.mip_rel_gap)
    x_full = result.get("x")
    if x_full is None:
        # MIP 没有 incumbent 时仍给出 canonical 排程在该场景下的真实可行上界，
        # 便于后续诊断；该候选不代表场景最优。
        schedule_path = args.canonical_final_dir.resolve() / "q4_字典序最终排程.csv"
        schedule = pd.read_csv(schedule_path)
        task_index = {int(v): i for i, v in enumerate(data.task["TaskID"].to_numpy())}
        region_index = {name: i for i, name in enumerate(qos.REGIONS)}
        candidate_pool = qos.ColumnPool()
        for row in schedule.itertuples(index=False):
            if int(row.TaskID) in task_index:
                candidate_pool.add(task_index[int(row.TaskID)], region_index[str(row.目标区域)], int(row.开工小时))
        if len(candidate_pool) != len(data.task):
            raise SystemExit("MIP 无 incumbent，且 canonical 排程未覆盖当前场景任务")
        candidate_x = np.ones(len(candidate_pool), dtype=float)
        candidate_energy = qos.energy_lp(qos.facility_load(candidate_pool, data, candidate_x), data)
        gpu2, it2, rhs2, _ = qos.make_presolve_rows(data)
        lat2 = qos.read_latency(args.attachment_dir.resolve())
        _, audit2 = qos.audit_solution(candidate_pool, data, candidate_x, gpu2, it2, rhs2, lat2, candidate_energy)
        schedule.to_csv(out / "q4_字典序Canonical场景可行排程.csv", index=False, encoding="utf-8-sig")
        payload = {"状态": "CANONICAL_FEASIBLE_CANDIDATE", "消息": result.get("message", ""),
                   "活动列数": len(pool), "输入断点": str(inp),
                   "真实能源成本_CNY": float(candidate_energy["cost"]), "硬约束审计": audit2,
                   "证书限制": "MIP 无 incumbent；这是 canonical 排程在 renew_down_80 下的可行上界，不是场景最优"}
        (out / "scenario_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
        raise SystemExit(2)
    x = np.rint(np.asarray(x_full[:len(pool)], dtype=float))
    energy = qos.energy_lp(qos.facility_load(pool, data, x), data)
    schedule, audit = qos.audit_solution(pool, data, x, gpu, it, rhs, latency, energy)
    schedule.to_csv(out / "q4_字典序Cost直接MIP排程.csv", index=False, encoding="utf-8-sig")
    dual = result.get("mip_dual_bound")
    dual = None if dual is None or not np.isfinite(dual) else float(dual)
    payload = {
        "状态": "FEASIBLE_CANDIDATE",
        "场景": "renew_down_80", "求解器": "能源一体化Cost MIP",
        "输入断点": str(inp), "活动列数": len(pool), "原区域多切轮次": stage_iter,
        "MIP返回状态": result.get("message", ""), "MIP目标值_CNY": result.get("fun"),
        "MIP下界_CNY": dual, "真实能源成本_CNY": float(energy["cost"]),
        "MIP Gap": result.get("mip_gap"), "硬约束审计": audit,
        "运行秒": time.time() - started,
        "证书限制": "区域多切根节点未闭合，当前仅为真实能源可行整数候选，不是完整域Cost证书",
    }
    if dual is not None:
        payload["候选UB减MIP下界_CNY"] = float(energy["cost"] - dual)
    (out / "scenario_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
