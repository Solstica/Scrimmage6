from pathlib import Path
import json

import pandas as pd


MOD = Path(__file__).resolve().parents[1]
RES = MOD / "results"
TAB = MOD / "tables"

FILES = {
    "动态弃电优先": "dynamic_marginal",
    "Cost-only": "cost_only",
    "Carbon-only": "carbon_only",
}


def load_audit(suffix):
    path = RES / ("q2_run_summary_" + suffix + ".json")
    return json.loads(path.read_text(encoding="utf-8"))["audit"]


def main():
    modes = {name: load_audit(suffix) for name, suffix in FILES.items()}
    headroom = pd.read_csv(RES / "q2_flexibility_headroom_20260817.csv")
    ub_cost = float(headroom.loc[
        headroom.Item.eq("RemovalCostHeadroomCombined"), "Value"
    ].iloc[0])
    ub_carbon = float(headroom.loc[
        headroom.Item.eq("RemovalCarbonHeadroomCombined"), "Value"
    ].iloc[0])
    cost = modes["Cost-only"]
    carbon = modes["Carbon-only"]
    rows = []
    for name, audit in modes.items():
        rows.append({
            "方案": name,
            "状态": audit["status"],
            "成本_CNY": audit["cost_cny"],
            "成本降幅_CNY": -audit["delta_cost_cny"],
            "成本降幅_百分比": -100.0 * audit["delta_cost_cny"] / audit["baseline_cost_cny"],
            "碳排_tCO2": audit["carbon_tco2"],
            "碳排减少_tCO2": -audit["delta_carbon_tco2"],
            "碳排降幅_百分比": -100.0 * audit["delta_carbon_tco2"] / audit["baseline_carbon_tco2"],
            "新能源利用率_百分比": 100.0 * audit["eta_R"],
            "新增新能源消纳_MWh": audit["delta_renewable_use_mwh"],
            "迁移率_百分比": 100.0 * audit["migration_rate"],
            "平均等待_h": audit["mean_wait_h"],
            "等待P95_h": audit["p95_wait_h"],
            "最大等待_h": audit["max_wait_h"],
            "RT迁移任务数": audit["rt_migrated_tasks"],
        })
    rows.extend([
        {
            "方案": "交叉损失：Carbon-only 相对 Cost-only",
            "状态": "探针",
            "成本_CNY": carbon["cost_cny"] - cost["cost_cny"],
            "成本降幅_CNY": (carbon["cost_cny"] - cost["cost_cny"]) / (-cost["delta_cost_cny"]),
            "碳排_tCO2": 0.0,
            "碳排减少_tCO2": 0.0,
        },
        {
            "方案": "交叉损失：Cost-only 相对 Carbon-only",
            "状态": "探针",
            "成本_CNY": 0.0,
            "成本降幅_CNY": 0.0,
            "碳排_tCO2": cost["carbon_tco2"] - carbon["carbon_tco2"],
            "碳排减少_tCO2": (cost["carbon_tco2"] - carbon["carbon_tco2"]) / (-carbon["delta_carbon_tco2"]),
        },
        {
            "方案": "FlexCapture_cost",
            "状态": "松弛上界对照",
            "成本_CNY": (-cost["delta_cost_cny"]) / ub_cost,
        },
        {
            "方案": "FlexCapture_carbon",
            "状态": "松弛上界对照",
            "碳排_tCO2": (-carbon["delta_carbon_tco2"]) / ub_carbon,
        },
    ])
    pd.DataFrame(rows).to_csv(
        TAB / "q2_objective_probe_20260817.csv", index=False, encoding="utf-8-sig"
    )


if __name__ == "__main__":
    main()
