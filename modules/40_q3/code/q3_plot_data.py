#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Q3 正式结果表整理 Origin 可直接使用的独立绘图数据。"""

from pathlib import Path
import sys

import pandas as pd


if len(sys.argv) != 1:
    raise SystemExit("本脚本不接收参数，直接读取当前 Q3 模块的处理后结果")

MOD = Path(__file__).resolve().parents[1]
PROC = MOD / "data" / "processed" / "q3_energy_dispatch_0_2406.csv"
SUMMARY = MOD / "tables" / "q3_metrics_summary.csv"
OUT = MOD / "figures" / "editable"
HOURS = list(range(2407))
REGIONS = ["RegionA", "RegionB", "RegionC", "RegionD", "RegionE", "RegionF"]


def write_table(frame: pd.DataFrame, name: str) -> Path:
    path = OUT / name
    frame.to_csv(path, index=False, encoding="utf-8-sig", float_format="%.10f")
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    hourly = pd.read_csv(PROC)
    summary = pd.read_csv(SUMMARY)

    if sorted(hourly["Hour"].unique().tolist()) != HOURS:
        raise ValueError("处理后时序数据的小时范围不是 0--2406")
    if sorted(hourly["Region"].unique().tolist()) != REGIONS:
        raise ValueError("处理后时序数据的区域集合不完整")
    if set(hourly["方案"].unique()) != {"E0_无储能调度", "E1_BESS协同调度"}:
        raise ValueError("处理后时序数据缺少 E0 或 E1")
    if hourly.isna().any().any() or summary.isna().all(axis=0).any():
        raise ValueError("绘图源数据存在空值列")

    # 图1：系统级电网交互功率，按小时汇总六区，不混入区域备用字段。
    grid = (
        hourly.groupby(["Hour", "方案"], as_index=False)["NetGridImport_MW"]
        .sum()
        .pivot(index="Hour", columns="方案", values="NetGridImport_MW")
        .reindex(HOURS)
    )
    fig1 = pd.DataFrame(
        {
            "X_时间（h）": HOURS,
            "Y_E0净电网交互功率（MW）": grid["E0_无储能调度"].to_numpy(),
            "Y_E1净电网交互功率（MW）": grid["E1_BESS协同调度"].to_numpy(),
        }
    )

    # 图2：D/E/F 的 E1 SOC 时序，三列直接对应三条曲线。
    soc = (
        hourly[hourly["方案"] == "E1_BESS协同调度"]
        .pivot(index="Hour", columns="Region", values="SOC_MWh")
        .reindex(HOURS)
    )
    fig2 = pd.DataFrame(
        {
            "X_时间（h）": HOURS,
            "Y_RegionD_SOC（MWh）": soc["RegionD"].to_numpy(),
            "Y_RegionE_SOC（MWh）": soc["RegionE"].to_numpy(),
            "Y_RegionF_SOC（MWh）": soc["RegionF"].to_numpy(),
        }
    )

    regional = summary[summary["Region"].isin(REGIONS)].pivot(
        index="Region", columns="方案", values="Cost_CNY"
    )
    bess_value = (regional["E0_无储能调度"] - regional["E1_BESS协同调度"]).rename("Y_BESS增量经济价值（CNY）")
    order = ["RegionF", "RegionE", "RegionD", "RegionA", "RegionB", "RegionC"]
    fig3 = pd.DataFrame(
        {
            "类别_区域": order,
            "Y_BESS增量经济价值（CNY）": bess_value.reindex(order).to_numpy(),
        }
    )

    system = summary[summary["Region"] == "System"].set_index("方案")
    plan_order = ["B0_附件基准", "E0_无储能调度", "E1_BESS协同调度"]
    fig4 = pd.DataFrame(
        {
            "类别_方案": ["B0 附件基准", "E0 无储能", "E1 BESS"],
            "Y_新能源利用率（%）": system.loc[plan_order, "Eta_R"].to_numpy() * 100.0,
        }
    )

    storage = summary[
        (summary["Region"].isin(["RegionD", "RegionE", "RegionF"]))
        & (summary["方案"] == "E1_BESS协同调度")
    ].set_index("Region").reindex(["RegionD", "RegionE", "RegionF"])
    fig5 = pd.DataFrame(
        {
            "类别_区域": ["RegionD", "RegionE", "RegionF"],
            "Y_充电量（MWh）": storage["Charge_MWh"].to_numpy(),
            "Y_放电量（MWh）": storage["Discharge_MWh"].to_numpy(),
        }
    )

    outputs = [
        write_table(fig1, "图1_系统电网交互功率时序.csv"),
        write_table(fig2, "图2_D-E-F储能SOC时序.csv"),
        write_table(fig3, "图3_各区域BESS增量经济价值.csv"),
        write_table(fig4, "图4_系统新能源利用率对比.csv"),
        write_table(fig5, "图5_D-E-F储能充放电量.csv"),
    ]

    report = """# Q3 绘图报告（Origin 中文版）

状态：`DRAFT / NEEDS_REVIEW`。以下数据均从 Q3 正式求解输出表生成；本报告只指导 Origin 作图，不代表结果已经冻结。

## 可绘制图清单

| 图名 | 要表达的结论 | 推荐图型 | 选择理由 |
|---|---|---|---|
| 图1 系统电网交互功率时序 | E1 相比 E0 显著平滑外部电网交互功率 | 双曲线图 | 时间序列需要保留小时顺序，便于比较波动和短时峰值 |
| 图2 D/E/F 储能 SOC 时序 | D/E/F 储能跨时段搬移的运行过程和终端回到初始水平 | 三曲线图 | SOC 是连续时间状态，曲线能同时展示充放电周期和边界 |
| 图3 各区域 BESS 增量经济价值 | 增量价值集中在 D/E/F，F 最高 | 水平条形图 | 区域名称适合放在纵轴，便于排序比较正负和零值 |
| 图4 系统新能源利用率对比 | E1 的新能源利用率高于 E0，B0 仅作原始参考 | 分组柱状图 | 方案是离散类别，柱高适合比较百分比 |
| 图5 D/E/F 储能充放电量 | 三个有储能价值区域的充放电规模差异 | 分组柱状图 | 同一单位下并列展示充电与放电，避免混入成本或 SOC 信息 |

## 图1：系统电网交互功率时序

- 数据表：`图1_系统电网交互功率时序.csv`
- 选列：`X_时间（h）`、`Y_E0净电网交互功率（MW）`、`Y_E1净电网交互功率（MW）`
- Origin 操作：选中三列，点击“绘图”→“基本二维图”→“折线图”。
- 坐标设置：横轴标题“时间（h）”，范围 0--2406；纵轴标题“净电网交互功率（MW）”，保留正负号，不截断负值。
- 图例与配色：E0 使用灰色 `#8C8C8C`，E1 使用蓝色 `#006BEE`；线宽 1.2--1.5 pt，不给每个小时添加数据标签。
- 结论边界：可说明电网交互功率平滑，不可写成设施计算负荷波动下降。

## 图2：D/E/F 储能 SOC 时序

- 数据表：`图2_D-E-F储能SOC时序.csv`
- 选列：`X_时间（h）`、`Y_RegionD_SOC（MWh）`、`Y_RegionE_SOC（MWh）`、`Y_RegionF_SOC（MWh）`
- Origin 操作：选中四列，点击“绘图”→“基本二维图”→“折线图”。
- 坐标设置：横轴标题“时间（h）”；纵轴标题“储能 SOC（MWh）”；范围从 0 起，按三条曲线的最大值留 5% 上边距。
- 图例与配色：RegionD `#2F7ED8`、RegionE `#F39C12`、RegionF `#27AE60`；三条线宽一致，图例放在空白区域。
- 结论边界：只展示 E1 的储能运行状态，不把 SOC 曲线解释成任务负荷曲线。

## 图3：各区域 BESS 增量经济价值

- 数据表：`图3_各区域BESS增量经济价值.csv`
- 选列：`类别_区域`、`Y_BESS增量经济价值（CNY）`
- Origin 操作：选中两列，点击“绘图”→“条形图”→“水平条形图”。
- 坐标设置：横轴标题“BESS 增量经济价值（CNY）”；纵轴标题“区域”；按表中 F、E、D、A、B、C 顺序显示。
- 配色：D/E/F 使用同一蓝绿色系，A/B/C 的数值零使用浅灰；显示柱端数据标签，保留两位小数。
- 结论边界：价值定义为 E1 相对 E0 的增量，不能把 B0 到 E1 的整体差额全部归因于 BESS。

## 图4：系统新能源利用率对比

- 数据表：`图4_系统新能源利用率对比.csv`
- 选列：`类别_方案`、`Y_新能源利用率（%）`
- Origin 操作：选中两列，点击“绘图”→“柱形图”→“简单柱状图”；在“绘图细节”中打开数据标签。
- 坐标设置：纵轴标题“新能源利用率（%）”，范围建议 0--80%；横轴为方案类别。
- 配色：B0 使用浅灰，E0 使用深灰，E1 使用 `#006BEE`；标签保留两位小数并带 `%`。
- 结论边界：B0 是附件 raw reference，E1-E0 才是储能增量对照。

## 图5：D/E/F 储能充放电量

- 数据表：`图5_D-E-F储能充放电量.csv`
- 选列：`类别_区域`、`Y_充电量（MWh）`、`Y_放电量（MWh）`
- Origin 操作：选中三列，点击“绘图”→“柱形图”→“分组柱状图”。
- 坐标设置：横轴标题“区域”；纵轴标题“能量（MWh）”，范围从 0 起；图例写“充电量”“放电量”。
- 配色：充电量 `#5B8FF9`，放电量 `#F6BD16`；柱间距保持适中，标签保留一位小数。
- 结论边界：图中只展示 E1 的 D/E/F 储能动作规模，不表示电池退化成本或循环寿命。

## 通用排版

中文字体用宋体，英文和数字用 Times New Roman；坐标标题 9--10 pt，刻度和图例 8--9 pt。关闭厚重外框和渐变背景，保留浅色水平辅助网格。每张图单独保存为 Origin 图页，数据绑定到对应 CSV 列，不要把多幅图拼成一张不可编辑图片。
"""
    report_path = OUT / "Q3绘图报告.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"generated {len(outputs)} plotting tables and report: {report_path}")
    for path in outputs:
        print(path.name)


if __name__ == "__main__":
    main()
