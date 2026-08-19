#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新能源下调情景的区域 Benders + 完整域定价验证器。

该脚本与旧的 q4_full_solver 输出完全隔离：
1. 从 canonical final-pool 读取合法列作为热启动列池；
2. 重新按 renew_down_80 附件计算能源 recourse 与六区域 cuts；
3. Cost 阶段使用 q4_qos_refinement 的 region multi-cut；
4. 根节点闭合后使用真实能源一体化 Cost MIP；
5. 通过 --task-limit 做 100/500/5000 任务门禁，正式规模不传该参数。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import q4_formal_scenarios as formal  # noqa: E402
import q4_qos_refinement as qos  # noqa: E402


def copy_scenario_attachment(base: Path, target: Path, task_limit: int | None) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(base, target)
    formal.rewrite_region_time(base, target, formal.scenario_by_id("renew_down_80"))
    if task_limit is not None:
        path = target / "workload_trace.xlsx"
        frame = pd.read_excel(path).head(task_limit)
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            frame.to_excel(writer, index=False)


def load_hot_pool(attachment: Path, final_dir: Path, task_limit: int | None):
    data = qos.read_data(attachment)
    # 优先复用 canonical final-pool 的全部活动列，而不是只读取最终排程的一列/任务。
    # 这保持完整合法域列池信息，同时仍允许当前场景重新选择 workload placement。
    try:
        canonical_pool, _, _, _, _, _, _ = qos.load_state(final_dir)
        ti, rr, ss = canonical_pool.arrays()
        pool = qos.ColumnPool()
        for task, region, start in zip(ti, rr, ss):
            if int(task) < len(data.task):
                pool.add(int(task), int(region), int(start))
    except Exception:
        schedule = pd.read_csv(final_dir / "q4_字典序最终排程.csv")
        task_index = {int(v): i for i, v in enumerate(data.task["TaskID"].to_numpy())}
        region_index = {name: i for i, name in enumerate(qos.REGIONS)}
        pool = qos.ColumnPool()
        selected = set(task_index)
        for row in schedule.itertuples(index=False):
            task_id = int(row.TaskID)
            if task_id in selected:
                pool.add(task_index[task_id], region_index[str(row.目标区域)], int(row.开工小时))
    # canonical 列池应覆盖所有抽样任务；若缺失则停止，不偷偷裁剪任务域。
    covered = set(pool.arrays()[0].tolist())
    if len(covered) != len(data.task):
        raise RuntimeError(f"canonical final-pool 未覆盖抽样任务：{len(data.task) - len(covered)} 个")
    x = np.zeros(len(pool), dtype=float)
    seen: set[int] = set()
    for j, task in enumerate(pool.arrays()[0]):
        task_i = int(task)
        if task_i not in seen:
            x[j] = 1.0
            seen.add(task_i)
    energy = qos.energy_lp(qos.facility_load(pool, data, x), data)
    if not energy["success"]:
        raise RuntimeError("热启动列池的新能源能源 LP 不可行：" + str(energy["message"]))
    return data, pool, x, energy


def args_for_stage(ns) -> argparse.Namespace:
    return argparse.Namespace(
        benders_tol_cny=ns.benders_tol_cny,
        columns_per_task=ns.columns_per_task,
        cost_feas_tol_cny=ns.cost_feas_tol_cny,
        heartbeat_seconds=ns.heartbeat_seconds,
        integer_time_limit_s=ns.integer_time_limit_s,
        max_stage_iter=ns.max_stage_iter,
        max_hours=ns.max_hours,
        max_active_columns=ns.max_active_columns,
        max_rss_gib=ns.max_rss_gib,
        min_free_gib=ns.min_free_gib,
        mip_rel_gap=ns.mip_rel_gap,
        price_tol=ns.price_tol,
        progress_mode="plain",
        wait_tolerance=1e-6,
    )


def run(ns) -> int:
    base = ns.attachment_dir.resolve()
    final_dir = ns.canonical_final_dir.resolve()
    suffix = "full_pool" if ns.task_limit is None else f"{ns.task_limit}task"
    out = ns.output_dir.resolve() / f"renew_down_80_region_multicut_{suffix}"
    attachment = out / "attachment"
    out.mkdir(parents=True, exist_ok=True)
    copy_scenario_attachment(base, attachment, ns.task_limit)
    resumed = bool(ns.resume and (out / "lexicographic_state.npz").is_file())
    if resumed:
        data = qos.read_data(attachment)
        pool, cuts, state_stage, stage_iter, _, _, initial_columns = qos.load_state(out)
        if state_stage not in ("cost", "recovery"):
            raise RuntimeError(f"当前断点阶段为 {state_stage}，该场景脚本只恢复 Cost 阶段")
        x = None
        initial_energy = None
    else:
        data, pool, x, initial_energy = load_hot_pool(attachment, final_dir, ns.task_limit)
        cuts = []
        qos.add_region_cuts(cuts, data, qos.facility_load(pool, data, x), initial_energy)
        stage_iter = 0
        initial_columns = len(pool)
    gpu, it, rhs, _ = qos.make_presolve_rows(data)
    latency = qos.read_latency(attachment)
    stage_args = args_for_stage(ns)
    spec = qos.StageSpec("renew_down_80 Cost区域多切", "cost", None)
    started = time.time()
    print(
        f"[场景启动] renew_down_80 | 任务={len(data.task)} | 热启动列={len(pool)} | "
        f"初始区域cuts={len(cuts)} | 恢复={resumed} | 起始轮次={stage_iter} | 输出={out}", flush=True,
    )
    try:
        result = qos.run_stage(
            spec, pool, cuts, data, gpu, it, rhs, latency, stage_args, out,
            started, initial_columns, None, stage_iter,
        )
    except qos.StageStopped as exc:
        payload = {
            "状态": "NEEDS_REVIEW", "场景": "renew_down_80",
            "任务数": len(data.task), "原因": str(exc),
            "活动列数": len(pool), "Benders切数": len(cuts),
            "输出目录": str(out), "热启动": True,
        }
        (out / "scenario_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)
        return 2

    schedule, audit = qos.audit_solution(pool, data, result.x, gpu, it, rhs, latency, result.energy)
    schedule.to_csv(out / "q4_字典序Cost场景排程.csv", index=False, encoding="utf-8-sig")
    metrics = pd.read_csv(out / "q4_lexicographic_stage_metrics.csv")
    last = metrics.iloc[-1].to_dict()
    load = qos.facility_load(pool, data, result.x)
    load_hash = hashlib.sha256(np.ascontiguousarray(load).tobytes()).hexdigest()
    audit_pass = all(float(v) <= 1e-5 for v in audit.values() if isinstance(v, (int, float)))
    gap = float(result.energy["cost"] - result.lp_bound)
    cert_pass = audit_pass and gap <= 0.001
    summary = {
        "状态": "PASS" if cert_pass else "NEEDS_REVIEW",
        "阶段状态": "stage_completed",
        "场景": "renew_down_80", "任务数": len(data.task),
        "真实能源成本_CNY": float(result.energy["cost"]),
        "完整域LP下界_CNY": float(result.lp_bound),
        "UB减LB_CNY": gap,
        "成本证书状态": "PASS" if cert_pass else "NEEDS_RESUME_OR_INTEGER_GAP",
        "Benders闭合容差_CNY": ns.benders_tol_cny,
        "活动列数": len(pool), "Benders切数": len(cuts),
        "完整域最小约化成本": float(result.min_reduced_cost),
        "区域最大违反_CNY": float(result.final_max_region_violation),
        "硬约束审计": audit, "FacilityLoad哈希": load_hash,
        "最后指标": last, "热启动": True,
    }
    (out / "scenario_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0 if summary["状态"] == "PASS" else 3


def main() -> None:
    p = argparse.ArgumentParser(description="renew_down_80 区域 multi-cut 场景求解器")
    p.add_argument("--attachment-dir", type=Path, default=qos.DEFAULT_ATTACH)
    p.add_argument("--canonical-final-dir", type=Path, default=HERE.parent / "results" / "qos_final_recertification")
    p.add_argument("--output-dir", type=Path, default=HERE.parent / "results" / "formal_scenarios")
    p.add_argument("--task-limit", type=int, choices=(100, 500, 5000), default=None)
    p.add_argument("--resume", action="store_true", help="从 output-dir 下已有的区域 multi-cut Cost 断点恢复")
    p.add_argument("--max-stage-iter", type=int, default=200)
    p.add_argument("--max-hours", type=float, default=0.5)
    p.add_argument("--benders-tol-cny", type=float, default=0.006)
    p.add_argument("--cost-feas-tol-cny", type=float, default=0.001)
    p.add_argument("--price-tol", type=float, default=1e-7)
    p.add_argument("--columns-per-task", type=int, default=2)
    p.add_argument("--integer-time-limit-s", type=float, default=600.0)
    p.add_argument("--mip-rel-gap", type=float, default=1e-7)
    p.add_argument("--heartbeat-seconds", type=float, default=30.0)
    p.add_argument("--max-active-columns", type=int, default=1_000_000)
    p.add_argument("--max-rss-gib", type=float, default=10.0)
    p.add_argument("--min-free-gib", type=float, default=2.0)
    ns = p.parse_args()
    if ns.task_limit is None:
        print("[正式规模] 未指定 --task-limit，将使用 50000 任务；请先完成 100/500/5000 门禁。", flush=True)
    raise SystemExit(run(ns))


if __name__ == "__main__":
    main()
