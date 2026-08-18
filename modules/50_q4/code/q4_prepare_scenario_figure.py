#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把正式场景六指标汇总整理为 Origin 图 F 的独立数据表。"""
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

COLS = [
    "类别_场景", "Y_能源成本（CNY）", "Y_碳排放（tCO2）",
    "Y_总等待（h）", "Y_平均等待（h）", "Y_P95等待（h）", "Y_最大等待（h）",
    "Y_总时延（ms）", "Y_平均时延（ms）", "Y_P95时延（ms）", "Y_最大时延（ms）",
    "Y_可再生能源利用率（%）", "Y_系统峰值净购电（MW）",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path(r"D:\第三次训练赛-worktrees\q4\modules\50_q4\results\formal_scenarios\q4_formal_six_metrics.csv"))
    parser.add_argument("--output", type=Path, default=Path(r"D:\第三次训练赛-worktrees\q4\modules\50_q4\figures\editable\图F_六指标场景对比.csv"))
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit(f"正式场景汇总不存在：{args.input}")
    data = pd.read_csv(args.input)
    missing = [col for col in COLS if col not in data.columns]
    if missing:
        raise SystemExit("正式场景六指标缺列：" + ", ".join(missing))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    data[COLS].sort_values("类别_场景").to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"已生成 {args.output}，行数={len(data)}")


if __name__ == "__main__":
    main()
