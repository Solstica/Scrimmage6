"""Generate one-table-per-figure Origin data for the latest Q2 endpoints."""

from pathlib import Path

import pandas as pd


MODULE = Path(__file__).resolve().parents[1]
DATA = MODULE / "data" / "processed"
RESULTS = MODULE / "results"
TABLES = MODULE / "tables"
OUT = MODULE / "figures" / "editable"


TYPE_ZH = {
    "AITraining": "AI训练",
    "BatchInference": "批量推理",
    "RealTimeInference": "实时推理",
}
REGIONS = [f"Region{c}" for c in "ABCDEF"]
REGION_ZH = {r: f"区域{r[-1]}" for r in REGIONS}


def save(frame: pd.DataFrame, filename: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT / filename, index=False, encoding="utf-8-sig")


def main() -> None:
    schedule = pd.read_csv(DATA / "q2_schedule_cost_only.csv")
    schedule["等待_h"] = schedule["StartHour"] - schedule["ArrivalHour"]
    schedule["Slack_h"] = (
        schedule["LatestFinishHour"]
        - schedule["ArrivalHour"]
        - schedule["Duration_h"]
    )

    # Values below are the checked medians/ranges recorded in Q2_DATA_PROBES.md.
    save(
        pd.DataFrame(
            {
                "X_任务类型": ["AI训练", "批量推理", "实时推理"],
                "Y_空间合法区域数_下限_个": [6, 5, 1],
                "Y_空间合法区域数_上限_个": [6, 6, 3],
            }
        ),
        "图01_任务空间柔性范围.csv",
    )
    save(
        pd.DataFrame(
            {
                "X_任务类型": ["AI训练", "批量推理", "实时推理"],
                "Y_DeadlineSlack中位数_h": [1184.22, 1207.22, 0.50],
            }
        ),
        "图02_任务时间余量中位数.csv",
    )
    save(
        pd.DataFrame(
            {
                "X_任务类型": ["AI训练", "批量推理", "实时推理"],
                "Y_GPU小时中位数_GPU小时": [194.35, 37.80, 10.83],
            }
        ),
        "图03_任务GPU小时中位数.csv",
    )

    cost_conv = pd.read_csv(RESULTS / "q2_convergence_cost_only.csv")
    previous_conv = pd.read_csv(RESULTS / "q2_convergence_cost_only_previous_start.csv")
    passes = sorted(set(cost_conv["pass"]).union(previous_conv["pass"]))
    cost_curve = pd.DataFrame({"X_扫描轮次": passes})
    cost_curve["Y_参考起点成本_CNY"] = cost_curve["X_扫描轮次"].map(
        cost_conv.set_index("pass")["cost_cny"]
    )
    cost_curve["Y_前次起点成本_CNY"] = cost_curve["X_扫描轮次"].map(
        previous_conv.set_index("pass")["cost_cny"]
    )
    save(cost_curve, "图04_成本收敛轨迹.csv")

    carbon_conv = pd.read_csv(RESULTS / "q2_convergence_carbon_only.csv")
    carbon_curve = pd.DataFrame({"X_扫描轮次": sorted(cost_conv["pass"].unique())})
    carbon_curve["Y_Cost主端点碳排_tCO2"] = carbon_curve["X_扫描轮次"].map(
        cost_conv.set_index("pass")["carbon_tco2"]
    )
    carbon_curve["Y_Carbon主端点碳排_tCO2"] = carbon_curve["X_扫描轮次"].map(
        carbon_conv.set_index("pass")["carbon_tco2"]
    )
    save(carbon_curve, "图05_碳排收敛轨迹.csv")

    cost_metrics = pd.read_csv(TABLES / "q2_metrics_cost_only.csv").iloc[0]
    carbon_metrics = pd.read_csv(TABLES / "q2_metrics_carbon_only.csv").iloc[0]
    previous_metrics = pd.read_csv(TABLES / "q2_metrics_cost_only_previous_start.csv").iloc[0]
    endpoint_labels = ["附件基准", "Cost主端点", "Carbon主端点", "前次起点Cost"]
    endpoint_cost = pd.DataFrame(
        {
            "X_方案": endpoint_labels,
            "Y_运行成本_CNY": [
                cost_metrics["baseline_cost_cny"],
                cost_metrics["cost_cny"],
                carbon_metrics["cost_cny"],
                previous_metrics["cost_cny"],
            ],
        }
    )
    save(endpoint_cost, "图06_方案运行成本对比.csv")
    endpoint_carbon = pd.DataFrame(
        {
            "X_方案": endpoint_labels,
            "Y_碳排放_tCO2": [
                cost_metrics["baseline_carbon_tco2"],
                cost_metrics["carbon_tco2"],
                carbon_metrics["carbon_tco2"],
                previous_metrics["carbon_tco2"],
            ],
        }
    )
    save(endpoint_carbon, "图07_方案碳排放对比.csv")

    waits = pd.read_csv(TABLES / "q2_wait_by_type_cost_only.csv")
    waits["TaskType"] = waits["TaskType"].map(TYPE_ZH)
    save(
        waits.rename(
            columns={
                "TaskType": "X_任务类型",
                "平均等待_h": "Y_平均等待_h",
                "等待P95_h": "Y_等待P95_h",
                "最大等待_h": "Y_最大等待_h",
            }
        )[["X_任务类型", "Y_平均等待_h", "Y_等待P95_h"]],
        "图08_任务类型等待分布.csv",
    )

    migration = (
        schedule.groupby(["SourceRegion", "ExecutionRegion"])
        .size()
        .unstack(fill_value=0)
        .reindex(index=REGIONS, columns=REGIONS, fill_value=0)
        .reset_index()
        .rename(columns={"SourceRegion": "X_来源区域"})
    )
    migration["X_来源区域"] = migration["X_来源区域"].map(REGION_ZH)
    migration = migration.rename(columns={r: f"Y_{REGION_ZH[r]}_任务数" for r in REGIONS})
    save(migration, "图09_区域迁移矩阵.csv")

    hourly = pd.read_csv(DATA / "q2_hourly_energy_cost_only.csv")
    energy = (
        hourly.groupby("Hour", as_index=False)[
            ["Facility_Load_MW", "GridPurchase_MW", "Curtailment_MW", "UsedRenewable_MW"]
        ]
        .sum()
        .rename(
            columns={
                "Hour": "X_小时",
                "Facility_Load_MW": "Y_设施负荷_MW",
                "GridPurchase_MW": "Y_电网购电_MW",
                "Curtailment_MW": "Y_弃电_MW",
                "UsedRenewable_MW": "Y_利用新能源_MW",
            }
        )
    )
    save(energy, "图10_逐时能源状态.csv")

    baseline_hourly = pd.read_csv(DATA / "q2_hourly_energy_0_2405.csv")
    response = hourly.merge(
        baseline_hourly[["Hour", "Region", "GridPurchase_MW", "Curtailment_MW"]].rename(
            columns={
                "GridPurchase_MW": "BaselineGridPurchase_MW",
                "Curtailment_MW": "BaselineCurtailment_MW",
            }
        ),
        on=["Hour", "Region"],
        how="left",
        validate="one_to_one",
    )
    response = response.rename(
        columns={
            "DeltaL_MW": "X_任务负荷增量_MW",
            "DeltaCurtailment_MW": "Y_弃电变化_MW",
            "DeltaGridPurchase_MW": "Y_购电变化_MW",
        }
    )

    def response_segment(row: pd.Series) -> str:
        delta_load = float(row["X_任务负荷增量_MW"])
        baseline_grid = float(row["BaselineGridPurchase_MW"])
        baseline_curtail = float(row["BaselineCurtailment_MW"])
        if delta_load >= -1e-8:
            return "弃电吸收区" if delta_load <= baseline_curtail + 1e-8 else "购电边际区"
        return "降负荷减购电区" if -delta_load <= baseline_grid + 1e-8 else "降负荷回退弃电区"

    response.insert(1, "类别_能源响应分段", response.apply(response_segment, axis=1))
    response = response[
        ["X_任务负荷增量_MW", "类别_能源响应分段", "Y_弃电变化_MW", "Y_购电变化_MW"]
    ]
    save(response, "图11_负荷增量与能源响应.csv")

    save(
        pd.DataFrame(
            {
                "X_运行成本_CNY": [
                    cost_metrics["baseline_cost_cny"],
                    cost_metrics["cost_cny"],
                    carbon_metrics["cost_cny"],
                    previous_metrics["cost_cny"],
                ],
                "Y_碳排放_tCO2": [
                    cost_metrics["baseline_carbon_tco2"],
                    cost_metrics["carbon_tco2"],
                    carbon_metrics["carbon_tco2"],
                    previous_metrics["carbon_tco2"],
                ],
                "标签_方案": endpoint_labels,
            }
        ),
        "图12_成本碳排端点散点.csv",
    )

    extreme = (
        schedule.sort_values(["等待_h", "TaskID"], ascending=[False, True])
        .head(5)[
            [
                "TaskID",
                "TaskType",
                "ArrivalHour",
                "StartHour",
                "FinishHour",
                "LatestFinishHour",
                "Slack_h",
                "SourceRegion",
                "ExecutionRegion",
                "Latency_ms",
                "MaxLatency_ms",
                "等待_h",
            ]
        ]
        .rename(
            columns={
                "TaskID": "任务ID",
                "TaskType": "任务类型",
                "ArrivalHour": "到达时刻_h",
                "StartHour": "开工时刻_h",
                "FinishHour": "完成时刻_h",
                "LatestFinishHour": "最晚完成时刻_h",
                "Slack_h": "可用时间余量_h",
                "SourceRegion": "来源区域",
                "ExecutionRegion": "执行区域",
                "Latency_ms": "网络时延_ms",
                "MaxLatency_ms": "时延上限_ms",
                "等待_h": "等待时间_h",
            }
        )
    )
    extreme["任务类型"] = extreme["任务类型"].map(TYPE_ZH)
    extreme["来源区域"] = extreme["来源区域"].map(REGION_ZH)
    extreme["执行区域"] = extreme["执行区域"].map(REGION_ZH)
    extreme.to_csv(RESULTS / "q2_extreme_wait_audit.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
