from pathlib import Path
import json

import pandas as pd


MOD = Path(__file__).resolve().parents[1]
RES = MOD / "results"
TAB = MOD / "tables"

FILES = {
    "动态弃电优先": "dynamic_marginal",
    "Cost-primary": "cost_only",
    "Carbon-primary": "carbon_only",
}


def load_summary(suffix):
    path = RES / ("q2_run_summary_" + suffix + ".json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    audit = payload["audit"]
    if not audit.get("converged", False):
        raise RuntimeError(f"{suffix} 尚未通过重复完整扫描收敛门禁")
    if audit.get("hard_constraint_status", audit.get("status")) != "PASS":
        raise RuntimeError(f"{suffix} 硬约束审计未通过")
    return payload


def main():
    runs = {name: load_summary(suffix) for name, suffix in FILES.items()}
    cost = runs["Cost-primary"]["audit"]
    carbon = runs["Carbon-primary"]["audit"]

    rows = []
    for name, payload in runs.items():
        a = payload["audit"]
        rows.append({
            "方案": name,
            "状态": a["status"],
            "完整扫描次数": a["passes"],
            "末次主目标相对改善": a["last_relative_primary_improvement"],
            "成本_CNY": a["cost_cny"],
            "成本降幅_CNY": -a["delta_cost_cny"],
            "成本降幅_百分比": -100.0 * a["delta_cost_cny"] / a["baseline_cost_cny"],
            "碳排_tCO2": a["carbon_tco2"],
            "碳排减少_tCO2": -a["delta_carbon_tco2"],
            "碳排降幅_百分比": -100.0 * a["delta_carbon_tco2"] / a["baseline_carbon_tco2"],
            "新能源利用率_百分比": 100.0 * a["eta_R"],
            "新增新能源消纳_MWh": a["delta_renewable_use_mwh"],
            "迁移率_百分比": 100.0 * a["migration_rate"],
            "平均等待_h": a["mean_wait_h"],
            "等待P95_h": a["p95_wait_h"],
            "最大等待_h": a["max_wait_h"],
            "RT迁移任务数": a["rt_migrated_tasks"],
        })

    cost_penalty = carbon["cost_cny"] - cost["cost_cny"]
    carbon_penalty = cost["carbon_tco2"] - carbon["carbon_tco2"]
    rows.extend([
        {
            "方案": "交叉损失：Carbon-primary 相对 Cost-primary",
            "状态": "收敛端点探针",
            "成本_CNY": cost_penalty,
            "成本降幅_CNY": cost_penalty / (-cost["delta_cost_cny"]),
            "碳排_tCO2": 0.0,
            "碳排减少_tCO2": 0.0,
        },
        {
            "方案": "交叉损失：Cost-primary 相对 Carbon-primary",
            "状态": "收敛端点探针",
            "成本_CNY": 0.0,
            "成本降幅_CNY": 0.0,
            "碳排_tCO2": carbon_penalty,
            "碳排减少_tCO2": carbon_penalty / (-carbon["delta_carbon_tco2"]),
        },
    ])
    pd.DataFrame(rows).to_csv(
        TAB / "q2_objective_probe_20260817.csv", index=False, encoding="utf-8-sig"
    )

    history = []
    for name, suffix in FILES.items():
        path = RES / ("q2_convergence_" + suffix + ".csv")
        h = pd.read_csv(path)
        h.insert(0, "方案", name)
        history.append(h)
    pd.concat(history, ignore_index=True).to_csv(
        TAB / "q2_convergence_comparison_20260817.csv",
        index=False,
        encoding="utf-8-sig",
    )


if __name__ == "__main__":
    main()
