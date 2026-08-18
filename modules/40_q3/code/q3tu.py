#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Q3 正式结果表整理 Origin 可直接使用的独立绘图数据。"""

from pathlib import Path
import sys

import numpy as np
import pandas as pd


if len(sys.argv) != 1:
    raise SystemExit("本脚本不接收参数，直接读取当前 Q3 模块的处理后结果")

MOD = Path(__file__).resolve().parents[1]
PROC = MOD / "data" / "processed" / "q3_energy_dispatch_0_2406.csv"
SUMMARY = MOD / "tables" / "q3_metrics_summary.csv"
OUT = MOD / "figures" / "editable"
HOURS = list(range(2407))
REGIONS = ["RegionA", "RegionB", "RegionC", "RegionD", "RegionE", "RegionF"]
cs = {
    # 数值来自 storage_information.xlsx，是 Q3 硬约束，不由图中序列估计。
    "RegionD": {"MinSOC_MWh": 90.0, "InitialSOC_MWh": 405.0, "StorageCapacity_MWh": 900.0},
    "RegionE": {"MinSOC_MWh": 82.0, "InitialSOC_MWh": 370.0, "StorageCapacity_MWh": 820.0},
    "RegionF": {"MinSOC_MWh": 85.0, "InitialSOC_MWh": 382.5, "StorageCapacity_MWh": 850.0},
}


def xie(frame: pd.DataFrame, name: str) -> Path:
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

    # 图1：按运行日汇总系统电网交互，避免 2407 个小时点在正文图中重叠。
    grid = (
        hourly.groupby(["Hour", "方案"], as_index=False)["NetGridImport_MW"]
        .sum()
        .pivot(index="Hour", columns="方案", values="NetGridImport_MW")
        .reindex(HOURS)
    )
    grid["运行日"] = grid.index // 24 + 1
    xt = grid.groupby("运行日").agg(
        {
            "E0_无储能调度": ["max", "min", "mean"],
            "E1_BESS协同调度": ["max", "min", "mean"],
        }
    )
    if len(xt) != 101:
        raise ValueError("系统电网交互日统计应为 101 个运行日")
    fig1 = pd.DataFrame(
        {
            "X_运行日（d）": xt.index.to_numpy(),
            "Y_无储能方案日内最大净电网交互功率（MW）": xt[("E0_无储能调度", "max")].to_numpy(),
            "Y_无储能方案日内最小净电网交互功率（MW）": xt[("E0_无储能调度", "min")].to_numpy(),
            "Y_无储能方案日均净电网交互功率（MW）": xt[("E0_无储能调度", "mean")].to_numpy(),
            "Y_储能优化方案日内最大净电网交互功率（MW）": xt[("E1_BESS协同调度", "max")].to_numpy(),
            "Y_储能优化方案日内最小净电网交互功率（MW）": xt[("E1_BESS协同调度", "min")].to_numpy(),
            "Y_储能优化方案日均净电网交互功率（MW）": xt[("E1_BESS协同调度", "mean")].to_numpy(),
            "Y_零功率参考线（MW）": np.zeros(len(xt)),
        }
    )

    # 图2：按运行日保留 D/E/F 的日内范围与日终状态，最后一日截至 Hour 2406。
    soc = hourly[hourly["方案"] == "E1_BESS协同调度"].sort_values(["Region", "Hour"]).copy()
    soc["运行日"] = soc["Hour"] // 24 + 1
    soc_day = soc.groupby(["运行日", "Region"])["SOC_MWh"].agg(["max", "min", "last"])
    fig2 = pd.DataFrame({"X_运行日（d）": list(range(1, 102))})
    for region in ["RegionD", "RegionE", "RegionF"]:
        params = cs[region]
        qm = region.replace("Region", "") + "区"
        rq = soc_day.xs(region, level="Region").reindex(range(1, 102))
        if rq.isna().any().any():
            raise ValueError(f"{qm} 储能日统计存在缺失")
        fig2[f"Y_{qm}日内最高荷电状态（MWh）"] = rq["max"].to_numpy()
        fig2[f"Y_{qm}日内最低荷电状态（MWh）"] = rq["min"].to_numpy()
        fig2[f"Y_{qm}日终荷电状态（MWh）"] = rq["last"].to_numpy()
        fig2[f"Y_{qm}最小荷电状态参考线（MWh）"] = params["MinSOC_MWh"]
        fig2[f"Y_{qm}初始荷电状态参考线（MWh）"] = params["InitialSOC_MWh"]
        fig2[f"Y_{qm}储能容量参考线（MWh）"] = params["StorageCapacity_MWh"]

    regional = summary[summary["Region"].isin(REGIONS)].pivot(
        index="Region", columns="方案", values="Cost_CNY"
    )
    jz = (regional["E0_无储能调度"] - regional["E1_BESS协同调度"]).rename("Y_储能增量经济价值（元）")
    order = ["RegionF", "RegionE", "RegionD", "RegionA", "RegionB", "RegionC"]
    fig3 = pd.DataFrame(
        {
            "类别_区域": [region.replace("Region", "") + "区" for region in order],
            "Y_储能增量经济价值（元）": jz.reindex(order).to_numpy(),
        }
    )

    system = summary[summary["Region"] == "System"].set_index("方案")
    fa = ["B0_附件基准", "E0_无储能调度", "E1_BESS协同调度"]
    f4f = pd.DataFrame(
        {
            "类别_方案": ["附件原始参考方案（B0）", "无储能方案（E0）", "储能优化方案（E1）"],
            "Y_新能源利用率（%）": system.loc[fa, "Eta_R"].to_numpy() * 100.0,
        }
    )

    storage = summary[
        (summary["Region"].isin(["RegionD", "RegionE", "RegionF"]))
        & (summary["方案"] == "E1_BESS协同调度")
    ].set_index("Region").reindex(["RegionD", "RegionE", "RegionF"])
    f5f = pd.DataFrame(
        {
            "类别_区域": ["D区", "E区", "F区"],
            "Y_充电量（MWh）": storage["Charge_MWh"].to_numpy(),
            "Y_放电量（MWh）": storage["Discharge_MWh"].to_numpy(),
        }
    )

    # 图4：RegionF 唯一新能源短缺小时的客观窗口（末端边界使窗口为 31 h）。
    f1 = hourly[(hourly["Region"] == "RegionF") & (hourly["方案"] == "E1_BESS协同调度")].copy()
    f1["H_MW"] = f1["AvailableRenewable_MW"] - f1["FacilityLoad_MW"]
    qh = f1.loc[f1["H_MW"] < -1e-9, "Hour"].astype(int).tolist()
    if len(qh) != 1:
        raise ValueError(f"RegionF 新能源短缺小时应恰好 1 个，实际为 {qh}")
    qs = qh[0]
    k0 = max(HOURS[0], qs - 24)
    k1 = min(HOURS[-1], qs + 24)
    if not 24 <= k1 - k0 + 1 <= 48:
        raise ValueError("RegionF 机制图窗口长度不在 24--48 h 范围内")
    e1f = f1[f1["Hour"].between(k0, k1)].sort_values("Hour")
    e0f = hourly[
        (hourly["Region"] == "RegionF")
        & (hourly["方案"] == "E0_无储能调度")
        & (hourly["Hour"].between(k0, k1))
    ].sort_values("Hour")
    if e0f["Hour"].tolist() != e1f["Hour"].tolist():
        raise ValueError("RegionF E0/E1 机制图窗口小时不一致")
    fig4 = pd.DataFrame(
        {
            "X_时间（h）": e1f["Hour"].to_numpy(dtype=int),
            "Y_可用新能源（MW）": e1f["AvailableRenewable_MW"].to_numpy(),
            "Y_设施负荷（MW）": e1f["FacilityLoad_MW"].to_numpy(),
            "Y_储能优化方案充电功率（MW）": (e1f["qR_新能源充电_MW"] + e1f["qG_电网充电_MW"]).to_numpy(),
            "Y_储能优化方案放电功率（MW）": e1f["d_放电_MW"].to_numpy(),
            "Y_无储能方案电网购电功率（MW）": e0f["GridPurchase_MW"].to_numpy(),
            "Y_储能优化方案电网购电功率（MW）": e1f["GridPurchase_MW"].to_numpy(),
            "Y_无储能方案新能源售电功率（MW）": e0f["s_新能源售电_MW"].to_numpy(),
            "Y_储能优化方案新能源售电功率（MW）": e1f["s_新能源售电_MW"].to_numpy(),
        }
    )

    outputs = [
        xie(fig1, "图1_系统电网交互日统计.csv"),
        xie(fig2, "图2_D-E-F区储能荷电状态日统计.csv"),
        xie(fig3, "图3_各区域储能增量经济价值.csv"),
        xie(fig4, "图4_F区短缺小时运行机制.csv"),
        xie(f4f, "附录A1_系统新能源利用率对比.csv"),
        xie(f5f, "附录A2_D-E-F区储能充放电量.csv"),
    ]

    report = """# Q3 绘图报告（Origin 中文版）

状态：`DRAFT / NEEDS_REVIEW`。本版按 `FIGURE_REVIEW_20260817.md` 调整为 4 张正文核心图；新能源利用率和总充放电量保留为附录候选。所有数据均来自 Q3 正式求解输出，图形仍需在 Origin 中由队友导入后编辑。

## 正文核心图清单

| 图名 | 要表达的结论 | 推荐图型 | 选择理由 |
|---|---|---|---|
| 图1 系统净电网交互日统计 | 比较两种方案的每日平均交互水平及日内波动范围 | 双面板高低值-均值图 + 零参考线 | 101 个运行日可读，日内极值不被逐小时重叠掩盖 |
| 图2 D/E/F区储能荷电状态日统计 | 展示各区每日荷电范围、日终状态及硬约束边界 | 三面板高低值-日终图 | 保留日内储能动作和终端约束，避免 2407 点重叠 |
| 图3 六区域储能增量经济价值 | 储能优化方案相对无储能方案的价值集中在 D/E/F区，A/B/C区为零 | 排序水平条形图 | 直接比较区域正值、零值和排序 |
| 图4 F区唯一短缺小时运行机制 | 低价期充能、后续放电供负荷并释放新能源售电，且在唯一短缺小时避免购电 | 三层共享 X 轴组合图 | 上层看供需缺口，中层看储能动作，下层看购售电结果 |

## 图1：系统净电网交互日统计

- 数据表：`图1_系统电网交互日统计.csv`。每行对应一个运行日；第 101 日仅含 Hour 2400--2406，保留其终端时段信息。
- 无储能方案选列：`X_运行日（d）`、`Y_无储能方案日内最大净电网交互功率（MW）`、`Y_无储能方案日内最小净电网交互功率（MW）`、`Y_无储能方案日均净电网交互功率（MW）`。
- 储能优化方案选列：`X_运行日（d）`、`Y_储能优化方案日内最大净电网交互功率（MW）`、`Y_储能优化方案日内最小净电网交互功率（MW）`、`Y_储能优化方案日均净电网交互功率（MW）`。
- Origin 操作：先选中无储能方案四列，点击“绘图”→“金融”→“高-低-收盘图”，其中“收盘”表示日均值；点击“图形”→“图层管理”新增第二图层，再以储能优化方案四列建立同类图；两个图层上下对齐并链接 X 轴。最后在“绘图设置”中把 `Y_零功率参考线（MW）` 添加为灰色虚线。
- 坐标轴：横轴“运行日（d）”，范围 1--101；纵轴“净电网交互功率（MW）”，两个图层统一范围，上限至少设为 50 MW，使零功率参考线可见。
- 配色与线型：无储能方案使用 `#777777`，储能优化方案使用 `#006BEE`；高低范围线 0.8 pt，日均值符号及连线 1.2 pt；零线 `#333333` 虚线 0.8 pt。
- 图例：分别标为“无储能方案：日内范围、日均值”“储能优化方案：日内范围、日均值”“零功率参考线”。
- 图注必须说明：正值=净购电，负值=净售电；图比较的是外部电网交互，不能写成设施计算负荷波动下降。

## 图2：D/E/F区储能荷电状态日统计

- 数据表：`图2_D-E-F区储能荷电状态日统计.csv`。每行对应一个运行日；第 101 日的日终值为 Hour 2406 的终端荷电状态。
- D区面板选列：`X_运行日（d）`、`Y_D区日内最高荷电状态（MWh）`、`Y_D区日内最低荷电状态（MWh）`、`Y_D区日终荷电状态（MWh）`、`Y_D区最小荷电状态参考线（MWh）`、`Y_D区初始荷电状态参考线（MWh）`、`Y_D区储能容量参考线（MWh）`。
- E区面板选列：`X_运行日（d）`、`Y_E区日内最高荷电状态（MWh）`、`Y_E区日内最低荷电状态（MWh）`、`Y_E区日终荷电状态（MWh）`、`Y_E区最小荷电状态参考线（MWh）`、`Y_E区初始荷电状态参考线（MWh）`、`Y_E区储能容量参考线（MWh）`。
- F区面板选列：`X_运行日（d）`、`Y_F区日内最高荷电状态（MWh）`、`Y_F区日内最低荷电状态（MWh）`、`Y_F区日终荷电状态（MWh）`、`Y_F区最小荷电状态参考线（MWh）`、`Y_F区初始荷电状态参考线（MWh）`、`Y_F区储能容量参考线（MWh）`。
- Origin 操作：先用 D区前三个日统计列建立“高-低-收盘图”，其中“收盘”表示日终值；通过“图形”→“图层管理”增加 E区、F区两层并分别添加相应列；在每层“绘图设置”中再添加三条荷电状态参考线，设置三个图层共享 X 轴并上下对齐。
- 坐标轴：三面板横轴统一“运行日（d）”，范围 1--101；纵轴均为“储能荷电状态（MWh）”，各面板从 0 起并按本区储能容量留 5% 上边距。
- 配色与线型：D/E/F区日内范围和日终值分别用 `#006BEE`、`#CB5CD7`、`#FF8B76`；最小荷电状态、初始荷电状态、储能容量参考线依次用浅灰、深灰和黑色细虚线，宽度 0.8 pt。
- 图注结论：日内范围展示每天的充放电幅度，日终值展示跨日状态转移和 2406 h 终端约束；不能把日统计曲线解读为瞬时负荷曲线。

## 图3：六区域储能增量经济价值

- 数据表：`图3_各区域储能增量经济价值.csv`。
- 选列：`类别_区域`、`Y_储能增量经济价值（元）`。
- Origin 操作：选中两列，点击“绘图”→“条形图”→“水平条形图”；按表中 `F区、E区、D区、A区、B区、C区` 顺序显示。
- 坐标轴：横轴“储能增量经济价值（元）”；纵轴“区域”；零值必须保留，不能删除 A/B/C区。
- 配色与标签：D/E/F区用同一蓝绿色系，A/B/C区零值用 `#D9D9D9`；柱端显示数据标签，保留两位小数，数值与单位之间留空格。
- 结论边界：增量价值严格定义为储能优化方案相对无储能方案的成本降低额；不能把附件原始参考方案到储能优化方案的整体差额全部归因于储能。

## 图4：F区唯一短缺小时运行机制图

- 数据表：`图4_F区短缺小时运行机制.csv`；窗口为 2376--2406 h，共 31 个小时，包含唯一新能源不足小时 2400 h。
- 上层选列：`X_时间（h）`、`Y_可用新能源（MW）`、`Y_设施负荷（MW）`。
- 中层选列：`X_时间（h）`、`Y_储能优化方案充电功率（MW）`、`Y_储能优化方案放电功率（MW）`。
- 下层选列：`X_时间（h）`、`Y_无储能方案电网购电功率（MW）`、`Y_储能优化方案电网购电功率（MW）`、`Y_无储能方案新能源售电功率（MW）`、`Y_储能优化方案新能源售电功率（MW）`。
- Origin 操作：先用上层两条供需曲线建立折线图；点击“图形”→“图层管理”新增中层和下层；在“绘图设置”中添加对应列并启用“链接 X 轴范围”。
- 参考线：在三个图层的 2400 h 位置添加同一条竖直灰色虚线，并在上层标注“唯一新能源不足小时”。
- 配色：可用新能源 `#006BEE`、设施负荷 `#777777`；充电 `#CB5CD7`、放电 `#FF8B76`；无储能方案购电 `#777777`、储能优化方案购电 `#006BEE`；无储能方案售电 `#BDBDBD`、储能优化方案售电 `#27AE60`。主线 1.2--1.4 pt，参考线 0.8 pt。
- 结论边界：图中展示“放电承担设施负荷，释放同期新能源用于外送售电”；2400 h 无储能方案有购电而储能优化方案无购电，说明 F区还具有短缺小时购电替代价值。不得写成储能放电直接售电。

## 附录候选图

### 附录 A1：系统新能源利用率对比

- 数据表：`附录A1_系统新能源利用率对比.csv`。
- 选列：`类别_方案`、`Y_新能源利用率（%）`；选择“绘图”→“柱形图”→“简单柱状图”。
- 类别标签为“附件原始参考方案（B0）”“无储能方案（E0）”“储能优化方案（E1）”；配色分别为浅灰、深灰和 `#006BEE`。
- 该图暂不作为冻结正文结论，须待 Q2--Q4 统一 accounting 和 Hour 2406 口径后再决定是否纳入正文。

### 附录 A2：D/E/F 总充放电量

- 数据表：`附录A2_D-E-F区储能充放电量.csv`。
- 选列：`类别_区域`、`Y_充电量（MWh）`、`Y_放电量（MWh）`；选择“绘图”→“柱形图”→“分组柱状图”。
- 该图只表达动作规模，机制信息弱且与图3存在重复，正文优先不使用；不得从柱高推断电池退化成本或循环寿命。

## 通用排版与 Origin 可编辑性

中文字体用宋体，英文和数字用 Times New Roman；坐标轴标题 9 pt，刻度、图例和注释 8--8.5 pt；主模型线宽 1.4 pt，参考线 0.8--1.0 pt。画布按双栏 180 mm 宽度设计，白底、浅灰主网格，关闭厚重外框和渐变背景。每张图单独保存为 Origin 图页，数据绑定到对应 CSV 列，不要导出后再嵌入位图。
"""
    bg = OUT / "Q3绘图报告.md"
    bg.write_text(report, encoding="utf-8")
    print(f"generated {len(outputs)} plotting tables and one report")


if __name__ == "__main__":
    main()
