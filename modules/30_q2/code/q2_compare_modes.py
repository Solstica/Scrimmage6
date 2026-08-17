from pathlib import Path
import json

import pandas as pd


MOD = Path(__file__).resolve().parents[1]
RES = MOD / "results"
TAB = MOD / "tables"

# Cost/Carbon are the two formal converged endpoints required to decide the
# Q2 objective structure. Dynamic-curtailment-first is only an optional
# ablation/probe and must never block the endpoint comparison.
REQUIRED = {
    "Cost-primary": "cost_only",
    "Carbon-primary": "carbon_only",
}
OPTIONAL = {
    "动态弃电优先（可选消融）": "dynamic_marginal",
}


def load_summary(suffix, required=True):
    path = RES / ("q2_run_summary_" + suffix + ".json")
    if not path.exists():
        if required:
            raise RuntimeError(f"缺少正式端点结果：{path.name}")
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    audit = payload["audit"]
    if not audit.get("converged", False):
        if required:
            raise RuntimeError(f"{suffix} 尚未通过重复完整扫描收敛门禁")
        return None
    if audit.get("hard_constraint_status", audit.get("status")) != "PASS":
        if required:
            raise RuntimeError(f"{suffix} 硬约束审计未通过")
        return None
    return payload


def main():
    runs = {name: load_summary(suffix, required=True) for name, suffix in REQUIRED.items()}
    for name, suffix in OPTIONAL.items():
        payload = load_summary(suffix, required=False)
        if payload is not None:
            runs[name] = payload
        else:
            print(f"[INFO] 跳过可选消融 {suffix}：未运行或未通过收敛门禁。")

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
            "成本损失_相对CostPrimary百分比": 100.0 * cost_penalty / cost["cost_cny"],
            "成本损失_相对基准降本百分比": 100.0 * cost_penalty / (-cost["delta_cost_cny"]),
            "碳排_tCO2": 0.0,
        },
        {
            "方案": "交叉损失：Cost-primary 相对 Carbon-primary",
            "状态": "收敛端点探针",
            "成本_CNY": 0.0,
            "碳排_tCO2": carbon_penalty,
            "碳损失_相对CarbonPrimary百分比": 100.0 * carbon_penalty / carbon["carbon_tco2"],
            "碳损失_相对基准减排百分比": 100.0 * carbon_penalty / (-carbon["delta_carbon_tco2"]),
        },
    ])
    pd.DataFrame(rows).to_csv(
        TAB / "q2_objective_probe_20260817.csv", index=False, encoding="utf-8-sig"
    )

    history = []
    for name, suffix in {**REQUIRED, **OPTIONAL}.items():
        path = RES / ("q2_convergence_" + suffix + ".csv")
        if not path.exists():
            continue
        # Only include histories whose endpoint was actually accepted above.
        if name not in runs:
            continue
        h = pd.read_csv(path)
        h.insert(0, "方案", name)
        history.append(h)
    if history:
        pd.concat(history, ignore_index=True).to_csv(
            TAB / "q2_convergence_comparison_20260817.csv",
            index=False,
            encoding="utf-8-sig",
        )

    print(json.dumps({
        "status": "PASS",
        "required_endpoints": list(REQUIRED),
        "optional_included": [name for name in OPTIONAL if name in runs],
        "cost_primary_cny": cost["cost_cny"],
        "carbon_primary_tco2": carbon["carbon_tco2"],
        "carbon_primary_cost_penalty_cny": cost_penalty,
        "carbon_primary_cost_penalty_pct_of_cost_primary": 100.0 * cost_penalty / cost["cost_cny"],
        "cost_primary_carbon_penalty_tco2": carbon_penalty,
        "cost_primary_carbon_penalty_pct_of_carbon_primary": 100.0 * carbon_penalty / carbon["carbon_tco2"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
