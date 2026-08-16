from pathlib import Path
import json
import math
import sys

import numpy as np
import pandas as pd
from scipy import stats


if len(sys.argv) != 2:
    raise SystemExit("用法: python q1_solver.py C题附件目录")

sj = Path(sys.argv[1]).resolve()
if not sj.exists():
    raise SystemExit("数据目录不存在")

root = Path(__file__).resolve().parents[3]
mod = Path(__file__).resolve().parents[1]
code = mod / "code"
proc = mod / "data" / "processed"
tab = mod / "tables"
res = mod / "results"
plotdata = mod / "figures" / "editable"
for p in [proc, plotdata, tab, res]:
    p.mkdir(parents=True, exist_ok=True)
seed = 20260816
rng = np.random.default_rng(seed)
regions = ["RegionA", "RegionB", "RegionC", "RegionD", "RegionE", "RegionF"]
types = ["RealTimeInference", "BatchInference", "AITraining"]
type_cn = {"RealTimeInference": "实时推理", "BatchInference": "批量推理", "AITraining": "AI训练"}
prio = {"RealTimeInference": 0, "BatchInference": 1, "AITraining": 2}
power = {"RealTimeInference": 0.08, "BatchInference": 0.10, "AITraining": 0.16}


def save_csv(df, path):
    df.to_csv(path, index=False, encoding="utf-8-sig")


def acf(x, lag):
    if lag >= len(x):
        return float("nan")
    a = np.asarray(x[lag:], dtype=float)
    b = np.asarray(x[:-lag], dtype=float)
    if a.std() == 0 or b.std() == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def cramers_v(tb):
    chi2 = stats.chi2_contingency(tb, correction=False)[0]
    n = tb.to_numpy().sum()
    den = min(tb.shape[0] - 1, tb.shape[1] - 1)
    return float(math.sqrt(chi2 / n / den)) if den > 0 else 0.0


def fano(x):
    a = np.asarray(x, dtype=float)
    return float(a.var(ddof=1) / a.mean()) if a.mean() > 0 else 0.0


def marks(train):
    out = {}
    for k in types:
        a = train.loc[train.TaskType == k, ["GPU_Demand", "EstimatedDuration_min"]].to_numpy()
        out[k] = a.astype(float)
    return out


def compound(rate, vals, n=5000):
    ns = rng.poisson(rate, size=n)
    ans = np.zeros(n, dtype=float)
    for j, m in enumerate(ns):
        if m:
            ans[j] = rng.choice(vals, size=m, replace=True).sum()
    return ans


def make_intervals(vals):
    vals["PI_R"] = {}
    vals["PI_K"] = {}
    for r in regions:
        a = np.sum([vals["SIM"][(r, k)] for k in types], axis=0)
        vals["PI_R"][r] = (float(np.quantile(a, 0.05)), float(np.quantile(a, 0.95)))
    for k in types:
        a = np.sum([vals["SIM"][(r, k)] for r in regions], axis=0)
        vals["PI_K"][k] = (float(np.quantile(a, 0.05)), float(np.quantile(a, 0.95)))
    a = np.sum([vals["SIM"][(r, k)] for r in regions for k in types], axis=0)
    vals["PI_SYS"] = (float(np.quantile(a, 0.05)), float(np.quantile(a, 0.95)))


def add_layers(base, vals, hours, split):
    out = []
    for h in hours:
        for r in regions:
            for k in types:
                x = base.get((h, r, k), 0.0)
                out.append({"Split": split, "Hour": h, "Level": "RegionTaskType", "Region": r,
                            "TaskType": k, "ActualGPU": x, "M0": vals["M0"][(r, k)],
                            "M1": vals["M1"].get((h, r, k), np.nan),
                            "M2": vals["M2"].get((h, r, k), np.nan),
                            "M3": vals["M3"][(r, k)], "PI05": vals["PI05"][(r, k)],
                            "PI95": vals["PI95"][(r, k)]})
        for r in regions:
            q = [z for z in out if z["Hour"] == h and z["Level"] == "RegionTaskType" and z["Region"] == r]
            out.append({"Split": split, "Hour": h, "Level": "Region", "Region": r, "TaskType": "ALL",
                        "ActualGPU": sum(z["ActualGPU"] for z in q), "M0": sum(z["M0"] for z in q),
                        "M1": sum(z["M1"] for z in q), "M2": sum(z["M2"] for z in q),
                        "M3": sum(z["M3"] for z in q), "PI05": vals["PI_R"][r][0],
                        "PI95": vals["PI_R"][r][1]})
        for k in types:
            q = [z for z in out if z["Hour"] == h and z["Level"] == "RegionTaskType" and z["TaskType"] == k]
            out.append({"Split": split, "Hour": h, "Level": "TaskType", "Region": "ALL", "TaskType": k,
                        "ActualGPU": sum(z["ActualGPU"] for z in q), "M0": sum(z["M0"] for z in q),
                        "M1": sum(z["M1"] for z in q), "M2": sum(z["M2"] for z in q),
                        "M3": sum(z["M3"] for z in q), "PI05": vals["PI_K"][k][0],
                        "PI95": vals["PI_K"][k][1]})
        q = [z for z in out if z["Hour"] == h and z["Level"] == "RegionTaskType"]
        out.append({"Split": split, "Hour": h, "Level": "System", "Region": "ALL", "TaskType": "ALL",
                    "ActualGPU": sum(z["ActualGPU"] for z in q), "M0": sum(z["M0"] for z in q),
                    "M1": sum(z["M1"] for z in q), "M2": sum(z["M2"] for z in q),
                    "M3": sum(z["M3"] for z in q), "PI05": vals["PI_SYS"][0],
                    "PI95": vals["PI_SYS"][1]})
    return pd.DataFrame(out)


def metric(df, col, split):
    x = df.loc[df.Level == "System", ["ActualGPU", col]].dropna()
    err = x[col] - x.ActualGPU
    return {"Split": split, "Model": col, "MAE": float(err.abs().mean()),
            "RMSE": float(np.sqrt(np.mean(err ** 2))),
            "WAPE": float(err.abs().sum() / x.ActualGPU.abs().sum())}


def overlap(start, dur, hour):
    return max(0.0, min(hour + 1.0, start + dur) - max(float(hour), start))


def main():
    work = pd.read_excel(sj / "workload_trace.xlsx", sheet_name="Sheet1")
    gpu = pd.read_excel(sj / "GPU_information.xlsx", sheet_name="GPU中心基础情况")
    grid = pd.read_excel(sj / "region_time_data.xlsx", sheet_name="region_time_data")
    lat = pd.read_excel(sj / "network_latency.xlsx", sheet_name="network_latency")

    need = {"TaskID", "TaskType", "ArrivalHour", "GPU_Demand", "EstimatedDuration_min",
            "SourceRegion", "MaxLatency_ms", "LatestFinishHour", "EarliestStartHour"}
    if not need.issubset(work.columns):
        raise SystemExit("workload_trace 字段不完整")
    if len(work) != 50000 or work.TaskID.nunique() != len(work):
        raise SystemExit("任务数量或 TaskID 不符合附件")

    work["Duration_h"] = work.EstimatedDuration_min / 60.0
    work["GPUHour"] = work.GPU_Demand * work.Duration_h
    work["AI_IT_MWh"] = work.GPU_Demand * work.TaskType.map(power) * work.Duration_h
    train = work.loc[work.ArrivalHour <= 2351].copy()
    valid = work.loc[(work.ArrivalHour >= 2352) & (work.ArrivalHour <= 2375)].copy()
    test = work.loc[(work.ArrivalHour >= 2376) & (work.ArrivalHour <= 2399)].copy()

    all_hours = pd.DataFrame({"Hour": np.arange(2400)})
    agg = work.groupby("ArrivalHour").agg(TaskCount=("TaskID", "size"), TotalGPU=("GPU_Demand", "sum"),
                                            TotalGPUHour=("GPUHour", "sum")).reset_index()
    hourly = all_hours.merge(agg, left_on="Hour", right_on="ArrivalHour", how="left").drop(columns="ArrivalHour")
    hourly = hourly.fillna(0)
    for r in regions:
        for k in types:
            a = work.loc[(work.SourceRegion == r) & (work.TaskType == k)].groupby("ArrivalHour").agg(
                **{f"Count_{r}_{k}": ("TaskID", "size"), f"GPU_{r}_{k}": ("GPU_Demand", "sum"),
                   f"GPUHour_{r}_{k}": ("GPUHour", "sum")}).reset_index()
            hourly = hourly.merge(a, left_on="Hour", right_on="ArrivalHour", how="left").drop(columns="ArrivalHour")
    hourly = hourly.fillna(0)
    save_csv(hourly, proc / "hourly_arrivals.csv")

    mg = work.groupby(["TaskType", "GPU_Demand"]).size().reset_index(name="Count")
    mg["Probability"] = mg.groupby("TaskType").Count.transform(lambda x: x / x.sum())
    save_csv(mg, proc / "mark_distribution_gpu.csv")
    md = work.groupby(["TaskType", "EstimatedDuration_min"]).size().reset_index(name="Count")
    md["Probability"] = md.groupby("TaskType").Count.transform(lambda x: x / x.sum())
    save_csv(md, proc / "mark_distribution_duration.csv")
    mj = work.groupby(["TaskType", "GPU_Demand", "EstimatedDuration_min"]).size().reset_index(name="Count")
    mj["Probability"] = mj.groupby("TaskType").Count.transform(lambda x: x / x.sum())
    save_csv(mj, proc / "mark_joint_gpu_duration_by_type.csv")

    total_count = train.groupby("ArrivalHour").size().reindex(range(2352), fill_value=0)
    tb = pd.crosstab(train.SourceRegion, train.TaskType).reindex(index=regions, columns=types, fill_value=0)
    kv = {}
    for k in types:
        groups = [train.loc[(train.TaskType == k) & (train.SourceRegion == r), "GPU_Demand"].to_numpy() for r in regions]
        kw = stats.kruskal(*groups)
        kv[k] = {"p_value": float(kw.pvalue), "eta2": float((kw.statistic - len(regions) + 1) / (len(train) - len(regions)))}
    mx = int(total_count.max())
    obs = total_count.value_counts().sort_index().reindex(range(mx + 1), fill_value=0).to_numpy()
    exp = np.array([stats.poisson.pmf(i, total_count.mean()) for i in range(mx + 1)]) * len(total_count)
    exp[-1] += stats.poisson.sf(mx, total_count.mean()) * len(total_count)
    chi = stats.chisquare(obs, f_exp=exp)
    audit = {
        "task_count": int(len(work)), "train_count": int(len(train)), "validation_count": int(len(valid)),
        "test_count": int(len(test)), "mean_hourly_arrivals": float(total_count.mean()),
        "fano_total": fano(total_count), "acf": {str(x): acf(total_count, x) for x in [1, 24, 168]},
        "poisson_chisquare_p": float(chi.pvalue), "cramers_v_region_tasktype": cramers_v(tb),
        "gpu_source_given_type": kv,
        "all_deadlines_feasible_at_arrival": bool(np.all(work.Duration_h <= work.LatestFinishHour - work.ArrivalHour)),
        "missing_values": int(work.isna().sum().sum())
    }
    (res / "data_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")

    lam = len(train) / 2352.0
    pi = train.groupby(["SourceRegion", "TaskType"]).size() / len(train)
    em = marks(train)
    mean_g = {k: float(em[k][:, 0].mean()) for k in types}
    mean_h = {k: float((em[k][:, 0] * em[k][:, 1] / 60.0).mean()) for k in types}
    m0 = {}
    m3 = {}
    q05 = {}
    q95 = {}
    sim1 = {}
    for r in regions:
        for k in types:
            rate = lam * float(pi.get((r, k), 0.0))
            m0[(r, k)] = float(train.loc[(train.SourceRegion == r) & (train.TaskType == k), "GPU_Demand"].sum() / 2352.0)
            m3[(r, k)] = rate * mean_g[k]
            sim = compound(rate, em[k][:, 0])
            sim1[(r, k)] = sim
            q05[(r, k)] = float(np.quantile(sim, 0.05))
            q95[(r, k)] = float(np.quantile(sim, 0.95))

    actual = work.groupby(["ArrivalHour", "SourceRegion", "TaskType"]).GPU_Demand.sum().to_dict()
    base = {}
    for h in range(2400):
        for r in regions:
            for k in types:
                base[(h, r, k)] = float(actual.get((h, r, k), 0.0))
    m1 = {(h, r, k): base.get((h - 24, r, k), np.nan) for h in range(2352, 2400) for r in regions for k in types}
    m2 = {(h, r, k): base.get((h - 168, r, k), np.nan) for h in range(2352, 2400) for r in regions for k in types}
    vals = {"M0": m0, "M1": m1, "M2": m2, "M3": m3, "PI05": q05, "PI95": q95, "SIM": sim1}
    make_intervals(vals)
    fval = add_layers(base, vals, range(2352, 2376), "Validation")

    refit = work.loc[work.ArrivalHour <= 2375]
    lam2 = len(refit) / 2376.0
    pi2 = refit.groupby(["SourceRegion", "TaskType"]).size() / len(refit)
    em2 = marks(refit)
    vals2 = {"M0": {}, "M1": m1, "M2": m2, "M3": {}, "PI05": {}, "PI95": {}, "SIM": {}}
    for r in regions:
        for k in types:
            rate = lam2 * float(pi2.get((r, k), 0.0))
            vals2["M0"][(r, k)] = float(refit.loc[(refit.SourceRegion == r) & (refit.TaskType == k), "GPU_Demand"].sum() / 2376.0)
            vals2["M3"][(r, k)] = rate * float(em2[k][:, 0].mean())
            sim = compound(rate, em2[k][:, 0])
            vals2["SIM"][(r, k)] = sim
            vals2["PI05"][(r, k)] = float(np.quantile(sim, 0.05))
            vals2["PI95"][(r, k)] = float(np.quantile(sim, 0.95))
    vals2["M1"] = {(h, r, k): base.get((h - 24, r, k), np.nan) for h in range(2376, 2400) for r in regions for k in types}
    vals2["M2"] = {(h, r, k): base.get((h - 168, r, k), np.nan) for h in range(2376, 2400) for r in regions for k in types}
    make_intervals(vals2)
    ftest = add_layers(base, vals2, range(2376, 2400), "Test")
    save_csv(fval, proc / "forecast_validation.csv")
    save_csv(ftest, proc / "forecast_test_2376_2399.csv")
    mt = []
    for col in ["M0", "M1", "M2", "M3"]:
        mt.append(metric(fval, col, "Validation"))
        mt.append(metric(ftest, col, "Test"))
    sys_test = ftest.loc[ftest.Level == "System"].copy()
    mt.append({"Split": "Test", "Model": "M3_90PI", "MAE": np.nan, "RMSE": np.nan,
               "WAPE": np.nan, "PICP": float(((sys_test.ActualGPU >= sys_test.PI05) & (sys_test.ActualGPU <= sys_test.PI95)).mean()),
               "MPIW": float((sys_test.PI95 - sys_test.PI05).mean())})
    metrics = pd.DataFrame(mt)
    save_csv(metrics, tab / "q1_forecast_metrics.csv")
    act = sys_test.ActualGPU.to_numpy(dtype=float)
    mu = float(sum(vals2["M3"].values()))
    uni = {k: 0.5 * (em2[k][:, 0].min() + em2[k][:, 0].max()) for k in types}
    mu_uni = float(sum(lam2 * float(pi2.get((r, k), 0.0)) * uni[k] for r in regions for k in types))
    sens = []
    for name, pred in [("到达率降低5%", 0.95 * mu), ("基准经验标记", mu), ("到达率提高5%", 1.05 * mu), ("均匀GPU标记对照", mu_uni)]:
        e = np.full(len(act), pred) - act
        sens.append({"Scenario": name, "SystemMeanGPU": pred, "MAE": float(np.mean(np.abs(e))),
                     "RMSE": float(np.sqrt(np.mean(e ** 2))), "WAPE": float(np.sum(np.abs(e)) / np.sum(np.abs(act)))})
    save_csv(pd.DataFrame(sens), tab / "q1_forecast_sensitivity.csv")

    cfg = gpu.set_index("Region").loc[regions]
    lmap = {(x.FromRegion, x.ToRegion): float(x.NetworkLatency_ms) for x in lat.itertuples(index=False)}
    gidx = grid.set_index(["Region", "Hour"])
    ai0 = np.zeros((6, 2407), dtype=float)
    for x in work.itertuples(index=False):
        ri = regions.index(x.SourceRegion)
        for h in range(int(x.ArrivalHour), min(2406, math.ceil(x.ArrivalHour + x.Duration_h))):
            ai0[ri, h] += x.GPU_Demand * power[x.TaskType] * overlap(float(x.ArrivalHour), x.Duration_h, h)
    ref = np.zeros((6, 2407), dtype=float)
    for ri, r in enumerate(regions):
        for h in range(2407):
            ref[ri, h] = float(gidx.loc[(r, h), "Baseline_AI_IT_Load_MW"])
    base_err = ai0 - ref

    sub = test.sort_values(["ArrivalHour", "TaskType", "LatestFinishHour", "TaskID"], key=lambda x: x.map(prio) if x.name == "TaskType" else x).copy()
    gu = np.zeros((6, 30), dtype=float)
    ai = np.zeros((6, 30), dtype=float)
    ans = []
    bad = []
    for x in sub.itertuples(index=False):
        dur = float(x.Duration_h)
        src = x.SourceRegion
        cand = [src] + [r for r in regions if r != src and lmap[(src, r)] <= x.MaxLatency_ms]
        first = int(max(x.ArrivalHour, x.EarliestStartHour))
        last = int(math.floor(min(float(x.LatestFinishHour), 2406.0) - dur + 1e-9))
        chosen = None
        for st in range(first, last + 1):
            for r in cand:
                ri = regions.index(r)
                ok = True
                for h in range(st, min(2406, math.ceil(st + dur))):
                    j = h - 2376
                    if j < 0 or j >= 30:
                        continue
                    ov = overlap(float(st), dur, h)
                    nonai = float(gidx.loc[(r, h), "NonAI_IT_Load_MW"])
                    if gu[ri, j] + x.GPU_Demand * ov > float(cfg.loc[r, "Available_GPU"]) + 1e-8:
                        ok = False
                    if nonai + ai[ri, j] + x.GPU_Demand * power[x.TaskType] * ov > float(cfg.loc[r, "Max_IT_Power_MW"]) + 1e-8:
                        ok = False
                    if float(cfg.loc[r, "PUE"]) * (nonai + ai[ri, j] + x.GPU_Demand * power[x.TaskType] * ov) > float(cfg.loc[r, "Max_Facility_Power_MW"]) + 1e-8:
                        ok = False
                    if not ok:
                        break
                if ok:
                    chosen = (r, st)
                    break
            if chosen:
                break
        if not chosen:
            bad.append(int(x.TaskID))
            continue
        r, st = chosen
        ri = regions.index(r)
        for h in range(st, min(2406, math.ceil(st + dur))):
            j = h - 2376
            if 0 <= j < 30:
                ov = overlap(float(st), dur, h)
                gu[ri, j] += x.GPU_Demand * ov
                ai[ri, j] += x.GPU_Demand * power[x.TaskType] * ov
        ans.append({"TaskID": int(x.TaskID), "SourceRegion": src, "ExecutionRegion": r,
                    "ArrivalHour": int(x.ArrivalHour), "StartHour": st, "FinishTime": st + dur,
                    "GPU_Demand": float(x.GPU_Demand), "Duration_h": dur, "TaskType": x.TaskType,
                    "Latency_ms": lmap[(src, r)], "Moved": int(r != src), "Delayed": int(st != x.ArrivalHour)})
    sch = pd.DataFrame(ans)
    save_csv(sch, proc / "schedule_2376_2405.csv")
    util = []
    for ri, r in enumerate(regions):
        for j, h in enumerate(range(2376, 2406)):
            nonai = float(gidx.loc[(r, h), "NonAI_IT_Load_MW"])
            it = nonai + ai[ri, j]
            util.append({"Hour": h, "Region": r, "GPUUse_GPUh": gu[ri, j],
                         "Available_GPU": float(cfg.loc[r, "Available_GPU"]),
                         "GPU_Utilization_Percent": 100.0 * gu[ri, j] / float(cfg.loc[r, "Available_GPU"]),
                         "AI_IT_Load_MW": ai[ri, j], "IT_Load_MW": it,
                         "Facility_Load_MW": it * float(cfg.loc[r, "PUE"])})
    util = pd.DataFrame(util)
    save_csv(util, proc / "gpu_utilization_2376_2405.csv")

    ca = []
    ov_err = 0.0
    for x in sch.itertuples(index=False):
        s = sum(overlap(float(x.StartHour), float(x.Duration_h), h) for h in range(int(x.StartHour), math.ceil(x.FinishTime)))
        ov_err = max(ov_err, abs(s - float(x.Duration_h)))
    ca.append({"Check": "overlap_conservation", "Passed": ov_err < 1e-10,
               "MaxViolation": ov_err, "Count": int(ov_err >= 1e-10)})
    ca.append({"Check": "baseline_ai_it_mae", "Passed": bool(np.max(np.abs(base_err)) < 1e-6),
               "MaxViolation": float(np.max(np.abs(base_err))), "Count": int(np.sum(np.abs(base_err) > 1e-6))})
    ca.append({"Check": "all_tasks_scheduled", "Passed": len(bad) == 0, "MaxViolation": float(len(bad)), "Count": len(bad)})
    ca.append({"Check": "latency", "Passed": bool((sch.Latency_ms <= test.set_index("TaskID").loc[sch.TaskID, "MaxLatency_ms"].to_numpy()).all()), "MaxViolation": 0.0, "Count": 0})
    ca.append({"Check": "finish_before_2406", "Passed": bool((sch.FinishTime <= 2406.0 + 1e-9).all()), "MaxViolation": float(max(0.0, sch.FinishTime.max() - 2406.0)), "Count": int((sch.FinishTime > 2406.0 + 1e-9).sum())})
    ca.append({"Check": "gpu_capacity", "Passed": bool((util.GPU_Utilization_Percent <= 100.0 + 1e-8).all()), "MaxViolation": float(max(0.0, util.GPU_Utilization_Percent.max() - 100.0)), "Count": int((util.GPU_Utilization_Percent > 100.0 + 1e-8).sum())})
    ca.append({"Check": "it_capacity", "Passed": bool((util.IT_Load_MW <= util.Region.map(cfg.Max_IT_Power_MW) + 1e-8).all()), "MaxViolation": float(max(0.0, (util.IT_Load_MW - util.Region.map(cfg.Max_IT_Power_MW)).max())), "Count": int((util.IT_Load_MW > util.Region.map(cfg.Max_IT_Power_MW) + 1e-8).sum())})
    ca.append({"Check": "facility_capacity", "Passed": bool((util.Facility_Load_MW <= util.Region.map(cfg.Max_Facility_Power_MW) + 1e-8).all()), "MaxViolation": float(max(0.0, (util.Facility_Load_MW - util.Region.map(cfg.Max_Facility_Power_MW)).max())), "Count": int((util.Facility_Load_MW > util.Region.map(cfg.Max_Facility_Power_MW) + 1e-8).sum())})
    ca = pd.DataFrame(ca)
    save_csv(ca, proc / "constraint_audit.csv")
    summ = pd.DataFrame([{"Tasks": len(sch), "Moved": int(sch.Moved.sum()), "Delayed": int(sch.Delayed.sum()),
                          "MaxGPUUtilPct": float(util.GPU_Utilization_Percent.max()),
                          "MeanGPUUtilPct": float(util.GPU_Utilization_Percent.mean()),
                          "MaxFinish": float(sch.FinishTime.max()), "AllChecksPassed": bool(ca.Passed.all())}])
    save_csv(summ, tab / "q1_schedule_summary.csv")
    stat_tab = work.groupby(["SourceRegion", "TaskType"]).agg(TaskCount=("TaskID", "size"),
        GPUHour=("GPUHour", "sum"), MeanGPU=("GPU_Demand", "mean"), MeanDurationMin=("EstimatedDuration_min", "mean")).reset_index()
    save_csv(stat_tab, tab / "q1_statistics_summary.csv")

    z1 = stat_tab.loc[:, ["SourceRegion", "TaskType", "TaskCount"]].copy()
    z1["X_任务类型序号_无量纲"] = z1.TaskType.map({k: i + 1 for i, k in enumerate(types)})
    z1["Y_区域序号_无量纲"] = z1.SourceRegion.map({r: i + 1 for i, r in enumerate(regions)})
    z1["标签_任务类型"] = z1.TaskType.map(type_cn)
    z1["标签_区域"] = z1.SourceRegion
    z1 = z1.rename(columns={"TaskCount": "Z_任务数_个"})
    save_csv(z1.loc[:, ["X_任务类型序号_无量纲", "Y_区域序号_无量纲", "Z_任务数_个", "标签_任务类型", "标签_区域"]], plotdata / "图01_区域与任务类型任务数热图.csv")
    z2 = work.groupby("TaskType").agg(TaskCount=("TaskID", "size"), GPUHour=("GPUHour", "sum")).reindex(types).reset_index()
    z2["类别_任务类型"] = z2.TaskType.map(type_cn)
    z2["Y_任务数占比_百分比"] = 100.0 * z2.TaskCount / z2.TaskCount.sum()
    z2["Y_GPU小时占比_百分比"] = 100.0 * z2.GPUHour / z2.GPUHour.sum()
    save_csv(z2.loc[:, ["类别_任务类型", "Y_任务数占比_百分比", "Y_GPU小时占比_百分比"]], plotdata / "图02_任务数与GPU小时占比分组柱状图.csv")
    z3 = pd.DataFrame({f"Y_{type_cn[k]}GPU需求_等效GPU": work.loc[work.TaskType == k, "GPU_Demand"].reset_index(drop=True) for k in types})
    save_csv(z3, plotdata / "图03_三类任务GPU需求箱线图.csv")
    z4 = pd.DataFrame()
    for k in types:
        a = work.loc[work.TaskType == k, ["GPU_Demand", "EstimatedDuration_min"]].reset_index(drop=True)
        z4[f"X_{type_cn[k]}GPU需求_等效GPU"] = a.GPU_Demand
        z4[f"Y_{type_cn[k]}执行时长_分钟"] = a.EstimatedDuration_min
    save_csv(z4, plotdata / "图04_GPU需求与执行时长分组散点图.csv")
    vc = total_count.value_counts().sort_index(); x = np.arange(int(total_count.max()) + 1)
    poi = pd.DataFrame({"X_每小时到达任务数_个": x, "Y_实际频率_百分比": 100.0 * vc.reindex(x, fill_value=0).to_numpy() / len(total_count), "Y_泊松理论概率_百分比": 100.0 * stats.poisson.pmf(x, total_count.mean())})
    save_csv(poi, plotdata / "图05_小时到达任务数与泊松拟合组合图.csv")
    lags = np.arange(1, 169)
    z6 = pd.DataFrame({"X_滞后时间_小时": lags, "Y_自相关系数_无量纲": [acf(total_count, int(z)) for z in lags], "Y_零参考线_无量纲": np.zeros(len(lags)), "标签_关键滞后": [f"lag {z}" if z in [1, 24, 168] else "" for z in lags]})
    save_csv(z6, plotdata / "图06_小时到达任务数自相关棒棒糖图.csv")
    z7 = hourly.loc[:, ["Hour", "TaskCount", "TotalGPU"]].rename(columns={"Hour": "X_时间_小时", "TaskCount": "Y_到达任务数_个", "TotalGPU": "Y_到达GPU需求_等效GPU"})
    save_csv(z7, plotdata / "图07_到达任务数与GPU需求双Y组合图.csv")
    q = ftest.loc[ftest.Level == "System", ["Hour", "ActualGPU", "M0", "M1", "M2", "M3", "PI05", "PI95"]]
    z8 = q.rename(columns={"Hour": "X_时间_小时", "ActualGPU": "Y_实际到达GPU需求_等效GPU", "M3": "Y_复合泊松预测均值_等效GPU", "PI05": "Y_90%预测区间下限_等效GPU", "PI95": "Y_90%预测区间上限_等效GPU"})
    save_csv(z8.loc[:, ["X_时间_小时", "Y_实际到达GPU需求_等效GPU", "Y_复合泊松预测均值_等效GPU", "Y_90%预测区间下限_等效GPU", "Y_90%预测区间上限_等效GPU"]], plotdata / "图08_测试集预测与90%预测区间.csv")
    z9 = sch.sort_values(["ExecutionRegion", "StartHour", "TaskType", "TaskID"]).reset_index(drop=True)
    z9["Y_绘图序号_无量纲"] = np.arange(1, len(z9) + 1)
    z9["类别_执行区域"] = z9.ExecutionRegion
    z9["类别_任务类型"] = z9.TaskType.map(type_cn)
    z9["标签_任务编号"] = z9.TaskID.astype(str)
    z9 = z9.rename(columns={"StartHour": "X_开始时间_小时", "FinishTime": "X_结束时间_小时"})
    save_csv(z9.loc[:, ["Y_绘图序号_无量纲", "X_开始时间_小时", "X_结束时间_小时", "类别_执行区域", "类别_任务类型", "标签_任务编号"]], plotdata / "图09_最后24小时任务甘特图.csv")
    z10 = util.copy()
    z10["Y_区域序号_无量纲"] = z10.Region.map({r: i + 1 for i, r in enumerate(regions)})
    z10["标签_区域"] = z10.Region
    z10 = z10.rename(columns={"Hour": "X_时间_小时", "GPU_Utilization_Percent": "Z_GPU利用率_百分比"})
    save_csv(z10.loc[:, ["X_时间_小时", "Y_区域序号_无量纲", "Z_GPU利用率_百分比", "标签_区域"]], plotdata / "图10_区域GPU利用率热图.csv")

    out = {"status": "PASS" if ca.Passed.all() else "FAIL", "seed": seed, "lambda_train": lam,
           "baseline_ai_it_max_error": float(np.max(np.abs(base_err))), "scheduled_tasks": int(len(sch)),
           "unscheduled_tasks": bad, "forecast_metrics": metrics.to_dict(orient="records"),
           "outputs": [str(x.relative_to(mod)) for x in [proc / "hourly_arrivals.csv", proc / "forecast_validation.csv", proc / "forecast_test_2376_2399.csv", proc / "schedule_2376_2405.csv", proc / "gpu_utilization_2376_2405.csv", proc / "constraint_audit.csv", tab / "q1_forecast_metrics.csv", tab / "q1_forecast_sensitivity.csv", tab / "q1_schedule_summary.csv"]]}
    (res / "run_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": out["status"], "scheduled_tasks": out["scheduled_tasks"], "max_gpu_util_pct": float(util.GPU_Utilization_Percent.max()), "baseline_error": out["baseline_ai_it_max_error"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
