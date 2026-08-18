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
                "类别_任务类型": ["AI训练", "批量推理", "实时推理"],
                "Y_空间合法区域数下限（个）": [6, 5, 1],
                "Y_空间合法区域数上限（个）": [6, 6, 3],
            }
        ),
        "图01_任务空间柔性范围.csv",
    )
    save(
        pd.DataFrame(
            {
                "类别_任务类型": ["AI训练", "批量推理", "实时推理"],
                "Y_实际可调开工时长中位数（h）": [1184.22, 1207.22, 0.0],
            }
        ),
        "图02_截止时间余量中位数.csv",
    )
    save(
        pd.DataFrame(
            {
                "类别_任务类型": ["AI训练", "批量推理", "实时推理"],
                "Y_GPU小时中位数（GPU·h）": [194.35, 37.80, 10.83],
            }
        ),
        "图03_任务GPU小时中位数.csv",
    )

    cost_conv = pd.read_csv(RESULTS / "q2_convergence_cost_only.csv")
    previous_conv = pd.read_csv(RESULTS / "q2_convergence_cost_only_previous_start.csv")
    passes = sorted(set(cost_conv["pass"]).union(previous_conv["pass"]))
    cost_curve = pd.DataFrame({"X_扫描轮次（次）": passes})
    cost_curve["Y_参考起点运行成本（CNY）"] = cost_curve["X_扫描轮次（次）"].map(
        cost_conv.set_index("pass")["cost_cny"]
    )
    cost_curve["Y_前次起点运行成本（CNY）"] = cost_curve["X_扫描轮次（次）"].map(
        previous_conv.set_index("pass")["cost_cny"]
    )
    save(cost_curve, "图04_成本收敛轨迹.csv")

    carbon_conv = pd.read_csv(RESULTS / "q2_convergence_carbon_only.csv")
    carbon_curve = pd.DataFrame({"X_扫描轮次（次）": sorted(cost_conv["pass"].unique())})
    carbon_curve["Y_Cost主端点碳排放（tCO₂）"] = carbon_curve["X_扫描轮次（次）"].map(
        cost_conv.set_index("pass")["carbon_tco2"]
    )
    carbon_curve["Y_Carbon主端点碳排放（tCO₂）"] = carbon_curve["X_扫描轮次（次）"].map(
        carbon_conv.set_index("pass")["carbon_tco2"]
    )
    save(carbon_curve, "图05_碳排收敛轨迹.csv")

    cost_metrics = pd.read_csv(TABLES / "q2_metrics_cost_only.csv").iloc[0]
    carbon_metrics = pd.read_csv(TABLES / "q2_metrics_carbon_only.csv").iloc[0]
    previous_metrics = pd.read_csv(TABLES / "q2_metrics_cost_only_previous_start.csv").iloc[0]
    endpoint_labels = ["附件基准", "Cost主端点", "Carbon主端点", "前次起点"]
    endpoint_cost = pd.DataFrame(
        {
            "类别_方案": endpoint_labels,
            "Y_运行成本（CNY）": [
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
            "类别_方案": endpoint_labels,
            "Y_碳排放（tCO₂）": [
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
                "TaskType": "类别_任务类型",
                "平均等待_h": "Y_平均等待时间（h）",
                "等待P95_h": "Y_等待时间95%分位数（h）",
                "最大等待_h": "Y_最大等待时间（h）",
            }
        )[["类别_任务类型", "Y_平均等待时间（h）", "Y_等待时间95%分位数（h）"]],
        "图08_任务类型等待分布.csv",
    )

    migration = (
        schedule.groupby(["SourceRegion", "ExecutionRegion"])
        .size()
        .unstack(fill_value=0)
        .reindex(index=REGIONS, columns=REGIONS, fill_value=0)
        .reset_index()
        .rename(columns={"SourceRegion": "类别_来源区域"})
    )
    migration["类别_来源区域"] = migration["类别_来源区域"].map(REGION_ZH)
    migration = migration.rename(columns={r: f"Y_{REGION_ZH[r]}执行任务数（个）" for r in REGIONS})
    save(migration, "图09_区域迁移矩阵.csv")

    hourly = pd.read_csv(DATA / "q2_hourly_energy_cost_only.csv")
    energy = (
        hourly.groupby("Hour", as_index=False)[
            ["Facility_Load_MW", "GridPurchase_MW", "Curtailment_MW", "UsedRenewable_MW"]
        ]
        .sum()
        .rename(
            columns={
                "Hour": "X_时间（h）",
                "Facility_Load_MW": "Y_设施负荷（MW）",
                "GridPurchase_MW": "Y_电网购电功率（MW）",
                "Curtailment_MW": "Y_弃电功率（MW）",
                "UsedRenewable_MW": "Y_新能源利用功率（MW）",
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
            "DeltaL_MW": "X_设施负荷扰动ΔL（MW）",
            "DeltaCurtailment_MW": "Y_弃电功率变化ΔC（MW）",
            "DeltaGridPurchase_MW": "Y_电网购电功率变化ΔG（MW）",
        }
    )

    def response_segment(row: pd.Series) -> str:
        delta_load = float(row["X_设施负荷扰动ΔL（MW）"])
        baseline_grid = float(row["BaselineGridPurchase_MW"])
        baseline_curtail = float(row["BaselineCurtailment_MW"])
        if delta_load >= -1e-8:
            return "弃电吸收区" if delta_load <= baseline_curtail + 1e-8 else "购电边际区"
        return "降负荷减购电区" if -delta_load <= baseline_grid + 1e-8 else "降负荷回退弃电区"

    response.insert(1, "类别_能源响应分段", response.apply(response_segment, axis=1))
    response = response[
        ["X_设施负荷扰动ΔL（MW）", "类别_能源响应分段", "Y_弃电功率变化ΔC（MW）", "Y_电网购电功率变化ΔG（MW）"]
    ]
    save(response, "图11_负荷增量与能源响应.csv")

    save(
        pd.DataFrame(
            {
                "X_运行成本（CNY）": [
                    cost_metrics["baseline_cost_cny"],
                    cost_metrics["cost_cny"],
                    carbon_metrics["cost_cny"],
                    previous_metrics["cost_cny"],
                ],
                "Y_碳排放（tCO₂）": [
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

    # 基准能源错配与低碳属性：数据来自已核验的 Q2_DATA_PROBES.md。
    # 该探针使用附件基准状态（Hour 0--2399），不混入调度后的端点结果。
    save(
        pd.DataFrame(
            {
                "类别_统计范围": ["0–2399 h，六区域"],
                "Y_同时弃电且购电区域时数（个）": [13230],
                "Y_其他区域时数（个）": [1170],
            }
        ),
        "图13a_弃电购电共存统计.csv",
    )
    save(
        pd.DataFrame(
            {
                "类别_能量指标": ["累计弃电量", "基准AI设施侧能量"],
                "Y_累计能量（MWh）": [7748360.94, 950773.63],
            }
        ),
        "图13a_弃电与AI设施侧能量.csv",
    )
    save(
        pd.DataFrame(
            {
                "类别_区域": ["区域A", "区域B", "区域C", "区域D", "区域E", "区域F"],
                "Y_弃电与碳强度Pearson相关系数": [-0.690, -0.693, -0.697, -0.789, -0.814, -0.849],
                "Y_弃电与可用新能源Pearson相关系数": [0.995213, 0.995223, 0.994745, 0.968689, 0.948162, 0.925246],
            }
        ),
        "图13b_弃电低碳属性相关性.csv",
    )

    # 代表性任务甘特图：只展示一个 72 h 开工时窗的 9 个特征任务。
    gantt_groups = [
        ("实时推理", [19264, 43240, 41451]),
        ("批量推理", [33356, 10622, 46942]),
        ("AI训练", [15694, 38894, 27293]),
    ]
    # 固定纵向位置，便于 Origin 直接按任务行绘制并保持三类任务的视觉分组。
    gantt_y = {
        19264: 11, 43240: 10, 41451: 9,
        33356: 7, 10622: 6, 46942: 5,
        15694: 3, 38894: 2, 27293: 1,
    }
    gantt_features = {
        19264: "典型即到即执行",
        43240: "长时高负载",
        41451: "终端收尾",
        33356: "跨区长等待",
        10622: "长时高负载",
        46942: "终端收尾",
        15694: "跨区短时高负载",
        38894: "高负载终端收尾",
        27293: "跨区延期代表",
    }
    gantt_task_ids = [task_id for _, ids in gantt_groups for task_id in ids]
    gantt_source = schedule.set_index("TaskID").loc[gantt_task_ids].copy()
    gantt_source["等待_h"] = gantt_source["StartHour"] - gantt_source["ArrivalHour"]
    gantt_source["GPU小时"] = gantt_source["GPU_Demand"] * gantt_source["Duration_h"]

    if not (gantt_source.loc[[19264, 43240, 41451], "等待_h"] == 0).all():
        raise ValueError("代表性RT任务不满足到达即开工")
    if not (
        gantt_source.loc[33356, "等待_h"] == 6
        and gantt_source.loc[33356, "SourceRegion"] != gantt_source.loc[33356, "ExecutionRegion"]
        and gantt_source.loc[10622, "等待_h"] == 0
        and gantt_source.loc[46942, "等待_h"] == 0
    ):
        raise ValueError("代表性Batch任务不满足跨区长等待")
    if not (
        (gantt_source.loc[[15694, 38894, 27293], "GPU小时"] >= 150).all()
        and (gantt_source.loc[27293, "等待_h"] == 5)
        and (gantt_source.loc[[15694, 38894, 27293], "SourceRegion"] != gantt_source.loc[[15694, 38894, 27293], "ExecutionRegion"]).all()
    ):
        raise ValueError("代表性AI训练任务不满足高GPU-hour跨区时间平移")

    gantt_rows: list[dict[str, object]] = []
    for group_title, task_ids in gantt_groups:
        for task_id in task_ids:
            row = gantt_source.loc[task_id]
            task_type = TYPE_ZH[row["TaskType"]]
            execution = REGION_ZH[row["ExecutionRegion"]]
            wait_h = float(row["等待_h"])
            gpu = float(row["GPU_Demand"])
            gpu_label = f"{gpu:.0f}" if gpu.is_integer() else f"{gpu:.1f}"
            gantt_rows.append(
                {
                    "Y_绘图位置": gantt_y[task_id],
                    "X_到达时间（h）": row["ArrivalHour"],
                    "X_开始时间（h）": row["StartHour"],
                    "X_结束时间（h）": row["FinishHour"],
                    "类别_任务类型": task_type,
                    "类别_特征分支": gantt_features[task_id],
                    "类别_执行区域": execution,
                    "类别_调度状态": "延期调整" if wait_h > 0 else "到达即执行",
                    "标签_任务ID": task_id,
                    "标签_显示文本": f"ID {task_id}｜{gantt_features[task_id]}｜{gpu_label} GPU",
                }
            )
    save(pd.DataFrame(gantt_rows), "图14_九个代表性任务甘特图.csv")

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
