#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q4 final-pool Cost、Wait、Latency 字典序再认证。"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psutil

from q4_full_solver import DEFAULT_ATTACH, R, make_presolve_rows, read_data
from q4_qos_refinement import (
    DEFAULT_RESULT,
    MODEL_VERSION,
    StageOutcome,
    StageSpec,
    StageStopped,
    audit_solution,
    load_state,
    read_latency,
    run_stage,
    save_state,
    write_checkpoint,
)


DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "results" / "qos_final_recertification"
CONTROL_NAME = "recertification_control.json"


def write_json(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def finite_or_none(value) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def ensure_completed_qos(input_dir: Path) -> None:
    summary = input_dir / "q4_qos_summary.json"
    checkpoint = input_dir / "checkpoint.json"
    state = input_dir / "lexicographic_state.npz"
    if not state.is_file():
        raise RuntimeError("缺少 QoS 最终列池断点：" + str(state))
    if summary.is_file():
        return
    if checkpoint.is_file() and read_json(checkpoint).get("状态") == "FINISHED_DRAFT":
        return
    raise RuntimeError("QoS Latency 阶段尚未闭合，不能开始 final-pool 再认证")


def initial_control(pool_size: int) -> dict:
    return {
        "模型版本": MODEL_VERSION,
        "状态": "RUNNING",
        "当前sweep": 1,
        "当前阶段": "cost",
        "Cost锚点_CNY": None,
        "Wait锚点_h": None,
        "Latency锚点_ms": None,
        "sweep起始锚点": {"Cost锚点_CNY": None, "Wait锚点_h": None, "Latency锚点_ms": None},
        "初始活动列数": pool_size,
        "阶段记录": [],
    }


def stage_spec(stage: str, control: dict, args) -> StageSpec:
    cost = finite_or_none(control.get("Cost锚点_CNY"))
    wait = finite_or_none(control.get("Wait锚点_h"))
    if stage == "cost":
        return StageSpec("R1 Cost再认证", "cost", None)
    if stage == "wait":
        if cost is None:
            raise StageStopped("缺少 Cost 锚点，不能执行 Wait 再认证")
        return StageSpec("R2 Wait再认证", "wait", cost + args.cost_tolerance)
    if stage == "latency":
        if cost is None or wait is None:
            raise StageStopped("缺少 Cost 或 Wait 锚点，不能执行 Latency 再认证")
        return StageSpec("R3 Latency再认证", "latency", cost + args.cost_tolerance, wait + args.wait_tolerance)
    raise StageStopped("未知再认证阶段：" + stage)


def stage_record(stage: str, sweep: int, outcome: StageOutcome, pool_size: int) -> dict:
    return {
        "sweep": sweep,
        "阶段": stage,
        "活动列数": pool_size,
        "新增列数": outcome.added_columns,
        "Benders切数": outcome.benders_cuts,
        "最大区域Benders违反_CNY": outcome.final_max_region_violation,
        "最小缺失列约化成本": outcome.min_reduced_cost,
        "LP界": outcome.lp_bound,
        "restricted_MIP目标": outcome.mip_objective,
        "restricted_MIP_gap": outcome.mip_gap,
        "真实能源成本_CNY": float(outcome.energy["cost"]),
        "阶段目标": outcome.objective,
        "轮次": outcome.iterations,
        "运行秒": outcome.runtime_s,
        "峰值RSS_GiB": outcome.peak_rss_gib,
        "global_integer_optimum_proved": False,
    }


def anchors_changed(control: dict, args) -> bool:
    reference = control["sweep起始锚点"]
    current = {
        "Cost锚点_CNY": control["Cost锚点_CNY"],
        "Wait锚点_h": control["Wait锚点_h"],
        "Latency锚点_ms": control["Latency锚点_ms"],
    }
    tolerance = {
        "Cost锚点_CNY": args.cost_tolerance,
        "Wait锚点_h": args.wait_tolerance,
        "Latency锚点_ms": args.latency_tolerance,
    }
    return any(reference.get(key) is None or abs(float(current[key]) - float(reference[key])) > tolerance[key] for key in current)


def audit_passes(audit: dict, tolerance: float = 1e-5) -> bool:
    for name, value in audit.items():
        if isinstance(value, (int, float, np.integer, np.floating)) and float(value) > tolerance:
            return False
    return True


def sweep_ui(control: dict, stage: str) -> None:
    rank = {"cost": 1, "wait": 2, "latency": 3}[stage]
    label = {"cost": "Cost", "wait": "Wait", "latency": "Latency"}[stage]
    print("\n" + "#" * 76, flush=True)
    print(
        f"[最终再认证] Sweep {control['当前sweep']} | {rank}/3 {label}阶段开始",
        flush=True,
    )
    print(
        "[整题结束条件] 至少两个完整sweep；本sweep三个阶段均通过；"
        "Cost/Wait/Latency锚点在容差内不再变化；最终硬约束审计通过。",
        flush=True,
    )


def anchorui(control: dict, changed: bool) -> None:
    old = control["sweep起始锚点"]
    print(
        f"[Sweep {control['当前sweep']} 锚点对照] "
        f"Cost: {old.get('Cost锚点_CNY')} -> {control.get('Cost锚点_CNY')} CNY | "
        f"Wait: {old.get('Wait锚点_h')} -> {control.get('Wait锚点_h')} h | "
        f"Latency: {old.get('Latency锚点_ms')} -> {control.get('Latency锚点_ms')} ms",
        flush=True,
    )
    if changed:
        print("[最终门禁] 未通过：本sweep锚点发生变化，必须继续下一完整sweep。", flush=True)
    else:
        print("[最终门禁] 锚点稳定：继续执行最终硬约束审计。", flush=True)


def save_control(out: Path, control: dict) -> None:
    write_json(out / CONTROL_NAME, control)
    write_checkpoint(out, {
        "模型版本": MODEL_VERSION,
        "状态": control["状态"],
        "当前sweep": control["当前sweep"],
        "当前阶段": control["当前阶段"],
        "活动列数": control.get("活动列数"),
        "Benders切数": control.get("Benders切数"),
        "Cost锚点_CNY": control.get("Cost锚点_CNY"),
        "Wait锚点_h": control.get("Wait锚点_h"),
        "Latency锚点_ms": control.get("Latency锚点_ms"),
        "全局整数最优已证明": False,
    })


def main() -> None:
    parser = argparse.ArgumentParser(description="Q4 final-pool 字典序再认证")
    parser.add_argument("--attachment-dir", type=Path, default=DEFAULT_ATTACH)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-stage-iter", type=int, default=0, help="0 表示每阶段持续到真实闭合")
    parser.add_argument("--max-sweeps", type=int, default=0, help="0 表示持续到完整 sweep 锚点不变")
    parser.add_argument("--cost-tolerance", type=float, default=1e-3)
    parser.add_argument("--wait-tolerance", type=float, default=1e-6)
    parser.add_argument("--latency-tolerance", type=float, default=1e-6)
    parser.add_argument("--benders-tol-cny", type=float, default=1e-3)
    parser.add_argument("--cost-feas-tol-cny", type=float, default=1e-3)
    parser.add_argument("--price-tol", type=float, default=1e-7)
    parser.add_argument("--columns-per-task", type=int, default=2)
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
    args = parser.parse_args()
    if args.max_sweeps < 0 or args.max_sweeps == 1:
        raise SystemExit("max-sweeps 必须为 0 或至少 2")
    if args.max_stage_iter < 0 or args.max_hours < 0 or args.integer_time_limit_s < 0:
        raise SystemExit("max-stage-iter、max-hours 和 integer-time-limit-s 不能为负；0 表示不限")
    if args.heartbeat_seconds < 0:
        raise SystemExit("heartbeat-seconds 不能为负；0 表示关闭心跳")
    if args.columns_per_task < 1:
        raise SystemExit("columns-per-task 必须至少为 1")

    input_dir = args.input_dir.resolve()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    available = psutil.virtual_memory().available / 1024 ** 3
    if available < args.min_free_gib:
        raise SystemExit(f"停止：当前可用内存 {available:.2f} GiB，小于门槛 {args.min_free_gib:.2f} GiB")
    data = read_data(args.attachment_dir.resolve())
    latency_raw = read_latency(args.attachment_dir.resolve())
    gpu_row, it_row, rhs, _ = make_presolve_rows(data)

    if args.resume:
        control_path = out / CONTROL_NAME
        if not control_path.is_file():
            raise RuntimeError("缺少再认证控制文件，请不要对未初始化目录使用 --resume")
        control = read_json(control_path)
        pool, cuts, saved_stage, saved_iter, _, _, initial_columns = load_state(out)
        print(f"恢复 sweep={control['当前sweep']}，阶段={control['当前阶段']}，第 {saved_iter} 轮后，活动列={len(pool)}，cuts={len(cuts)}")
    else:
        if (out / CONTROL_NAME).is_file() or (out / "lexicographic_state.npz").is_file():
            raise RuntimeError("输出目录已有再认证断点；请使用 --resume，或指定新的 output-dir")
        ensure_completed_qos(input_dir)
        pool, cuts, _, _, _, _, initial_columns = load_state(input_dir)
        control = initial_control(len(pool))
        saved_stage, saved_iter = "cost", 0
        save_state(out, pool, cuts, saved_stage, saved_iter, None, None, initial_columns)
        save_control(out, control)
        print(f"从 QoS final pool 启动：活动列={len(pool)}，cuts={len(cuts)}；将执行至少两轮完整 sweep")
    print(
        "[正式结束规则] 只有程序打印“正式可结束”，且q4_qos_summary.json状态为FINISHED_DRAFT、"
        "约束审计通过，才可把当前结果作为再认证后的best-known整数方案。",
        flush=True,
    )

    try:
        while True:
            stage = str(control["当前阶段"])
            spec = stage_spec(stage, control, args)
            sweep_ui(control, stage)
            start_iter = saved_iter if saved_stage == stage else 0
            outcome = run_stage(
                spec, pool, cuts, data, gpu_row, it_row, rhs, latency_raw, args, out,
                started, initial_columns, finite_or_none(control.get("Wait锚点_h")), start_iter,
                "q4_recertification_stage_metrics.csv",
            )
            record = stage_record(stage, int(control["当前sweep"]), outcome, len(pool))
            control["阶段记录"].append(record)
            write_json(out / f"sweep_{control['当前sweep']}_{stage}_summary.json", record)
            control["活动列数"] = len(pool)
            control["Benders切数"] = len(cuts)
            saved_iter = 0

            if stage == "cost":
                control["Cost锚点_CNY"] = outcome.objective
                control["当前阶段"] = "wait"
                saved_stage = "wait"
                save_state(out, pool, cuts, saved_stage, 0, outcome.objective + args.cost_tolerance, None, initial_columns)
            elif stage == "wait":
                control["Wait锚点_h"] = outcome.objective
                control["当前阶段"] = "latency"
                saved_stage = "latency"
                save_state(out, pool, cuts, saved_stage, 0, finite_or_none(control["Cost锚点_CNY"]) + args.cost_tolerance, outcome.objective, initial_columns)
            else:
                control["Latency锚点_ms"] = outcome.objective
                changed = anchors_changed(control, args)
                anchorui(control, changed)
                if not changed:
                    schedule, audit = audit_solution(pool, data, outcome.x, gpu_row, it_row, rhs, latency_raw, outcome.energy)
                    schedule.to_csv(out / "q4_字典序最终排程.csv", index=False, encoding="utf-8-sig")
                    summary = {
                        "模型版本": MODEL_VERSION,
                        "状态": "FINISHED_DRAFT" if audit_passes(audit) else "DRAFT / NEEDS_REVIEW",
                        "算法": "final-pool Cost -> Wait -> Latency lexicographic recertification",
                        "完整候选域": "每个阶段均执行完整合法域精确定价；无 top-k 或等待窗裁剪",
                        "任务数": len(data.task),
                        "best-known integer Cost anchor_CNY": control["Cost锚点_CNY"],
                        "best-known integer Wait anchor_h": control["Wait锚点_h"],
                        "best-known integer Latency anchor_ms": control["Latency锚点_ms"],
                        "final-pool lexicographic recertified representative solution": True,
                        "最终真实能源成本_CNY": float(outcome.energy["cost"]),
                        "最终活动列数": len(pool),
                        "Benders切数": len(cuts),
                        "阶段记录": control["阶段记录"],
                        "约束审计": audit,
                        "约束审计通过": audit_passes(audit),
                        "运行分钟": (time.time() - started) / 60,
                        "全局整数最优已证明": False,
                    }
                    write_json(out / "q4_qos_summary.json", summary)
                    control["状态"] = summary["状态"]
                    control["当前阶段"] = "finished"
                    save_state(out, pool, cuts, "finished", 0, finite_or_none(control["Cost锚点_CNY"]) + args.cost_tolerance, finite_or_none(control["Wait锚点_h"]), initial_columns)
                    save_control(out, control)
                    if summary["状态"] == "FINISHED_DRAFT":
                        print(
                            "[正式可结束] 至少两个完整sweep的字典序锚点稳定，"
                            "完整域定价、真实能源复核和最终硬约束审计均已通过。",
                            flush=True,
                        )
                    else:
                        print("[仍不可结束] 锚点已稳定，但最终硬约束审计未通过。", flush=True)
                    print(json.dumps(summary, ensure_ascii=False, indent=2))
                    return
                if args.max_sweeps > 0 and int(control["当前sweep"]) >= args.max_sweeps:
                    control["当前sweep"] = int(control["当前sweep"]) + 1
                    control["sweep起始锚点"] = {
                        "Cost锚点_CNY": control["Cost锚点_CNY"],
                        "Wait锚点_h": control["Wait锚点_h"],
                        "Latency锚点_ms": control["Latency锚点_ms"],
                    }
                    control["当前阶段"] = "cost"
                    saved_stage = "cost"
                    save_state(out, pool, cuts, "cost", 0, None, None, initial_columns)
                    raise StageStopped("完成 sweep 但锚点仍变化；请增大 --max-sweeps 后 --resume")
                control["当前sweep"] = int(control["当前sweep"]) + 1
                control["sweep起始锚点"] = {
                    "Cost锚点_CNY": control["Cost锚点_CNY"],
                    "Wait锚点_h": control["Wait锚点_h"],
                    "Latency锚点_ms": control["Latency锚点_ms"],
                }
                control["当前阶段"] = "cost"
                saved_stage = "cost"
                save_state(out, pool, cuts, "cost", 0, None, None, initial_columns)
            save_control(out, control)
    except StageStopped as exc:
        control["状态"] = "DRAFT / NEEDS_RESUME"
        control["原因"] = str(exc)
        control["活动列数"] = len(pool)
        control["Benders切数"] = len(cuts)
        save_control(out, control)
        print(json.dumps(control, ensure_ascii=False, indent=2))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
