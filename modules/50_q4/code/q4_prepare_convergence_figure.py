#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prepare the Origin-ready integer Benders convergence table for Q4."""
from __future__ import annotations

import argparse
import math
import time
from pathlib import Path

import pandas as pd


MODULE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METRICS = (
    MODULE_ROOT
    / "results"
    / "formal_scenarios"
    / "price_flat"
    / "qos_final_recertification"
    / "q4_recertification_stage_metrics.csv"
)
DEFAULT_OUTPUT = MODULE_ROOT / "figures" / "editable" / "图G_price_flat整数Benders误差收敛.csv"
DEFAULT_TOLERANCE_CNY = 1e-3


def read_live_metrics(path: Path, attempts: int = 20) -> pd.DataFrame:
    """Retry because the solver may be appending the metrics file."""
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            frame = pd.read_csv(path)
            required = {"阶段", "轮次", "事件", "最大区域违反_CNY"}
            missing = required.difference(frame.columns)
            if missing:
                raise ValueError("阶段指标缺少列：" + ", ".join(sorted(missing)))
            return frame
        except (OSError, pd.errors.ParserError, ValueError) as exc:
            last_error = exc
            time.sleep(0.25)
    raise RuntimeError(f"无法读取稳定的阶段指标：{path}") from last_error


def excess_orders(violation_cny: float, tolerance_cny: float) -> float:
    """Return orders of magnitude above tolerance; zero means passing."""
    return math.log10(max(float(violation_cny), tolerance_cny) / tolerance_cny)


def prepare_table(metrics: pd.DataFrame, tolerance_cny: float) -> pd.DataFrame:
    integer_events = metrics.loc[
        metrics["事件"].isin(["integer_added_region_benders_cuts", "stage_completed"])
        & metrics["阶段"].astype(str).str.contains("Cost再认证", regex=False),
        ["轮次", "事件", "最大区域违反_CNY"],
    ].copy()
    integer_events["最大区域违反_CNY"] = pd.to_numeric(
        integer_events["最大区域违反_CNY"], errors="coerce"
    )
    integer_events = integer_events.dropna(subset=["轮次", "最大区域违反_CNY"])
    integer_events = integer_events.sort_values("轮次", kind="stable")
    integer_events = integer_events.drop_duplicates(subset=["轮次"], keep="last")
    if integer_events.empty:
        raise ValueError("尚无 Cost 再认证整数候选，不能生成误差收敛图数据")

    current = integer_events["最大区域违反_CNY"].clip(lower=0.0)
    best = current.cummin()
    return pd.DataFrame(
        {
            "X_求解轮次": integer_events["轮次"].astype(int).to_numpy(),
            "Y_当次误差超容差数量级": [
                excess_orders(value, tolerance_cny) for value in current
            ],
            "Y_历史最优误差超容差数量级": [
                excess_orders(value, tolerance_cny) for value in best
            ],
            "Y_收敛基准": 0.0,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="整理 Q4 整数 Benders 误差收敛图数据")
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--tolerance-cny", type=float, default=DEFAULT_TOLERANCE_CNY)
    args = parser.parse_args()
    if args.tolerance_cny <= 0:
        raise SystemExit("tolerance-cny 必须为正数")

    metrics = read_live_metrics(args.metrics.resolve())
    table = prepare_table(metrics, args.tolerance_cny)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output, index=False, encoding="utf-8-sig")

    print(f"已生成：{output}")
    print(f"整数复核点数：{len(table)}")
    print(f"最新轮次：{int(table.iloc[-1]['X_求解轮次'])}")
    print(
        "历史最优超容差数量级："
        f"{float(table.iloc[-1]['Y_历史最优误差超容差数量级']):.6f}"
    )


if __name__ == "__main__":
    main()
