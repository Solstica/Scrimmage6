#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q4 固定最终 QoS 排程的新能源--碳约束情景复核。

这是 energy recourse 情景表：不更改已冻结的任务排程，因此用于分离展示
同一服务质量下新能源振幅、碳预算和电力调度的影响。
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from q4_full_solver import DEFAULT_ATTACH, DEFAULT_OUT, ColumnPool, energy_lp, facility_load, read_data

DEFAULT_QOS = Path(__file__).resolve().parents[1] / "results" / "qos_refinement"
DEFAULT_RESULT = Path(__file__).resolve().parents[1] / "results" / "energy_scenarios"

def main():
    p=argparse.ArgumentParser(description="Q4 新能源压力--碳约束情景")
    p.add_argument("--attachment-dir",type=Path,default=DEFAULT_ATTACH); p.add_argument("--qos-dir",type=Path,default=DEFAULT_QOS); p.add_argument("--output-dir",type=Path,default=DEFAULT_RESULT); p.add_argument("--gamma",type=float,default=1.4)
    a=p.parse_args(); data=read_data(a.attachment_dir.resolve()); out=a.output_dir.resolve(); out.mkdir(parents=True,exist_ok=True)
    schedule=pd.read_csv(a.qos_dir.resolve()/"q4_字典序最终排程.csv"); task_index={int(task):i for i,task in enumerate(data.task.TaskID.to_numpy())}; region_index={name:i for i,name in enumerate(("RegionA","RegionB","RegionC","RegionD","RegionE","RegionF"))}
    pool=ColumnPool()
    for row in schedule.itertuples(index=False): pool.add(task_index[int(row.TaskID)],region_index[row.目标区域],int(row.开工小时))
    if len(pool)!=len(data.task): raise RuntimeError("最终排程未覆盖全部任务")
    load=facility_load(pool,data,np.ones(len(pool))); base=energy_lp(load,data)
    mean=data.renew.mean(axis=1,keepdims=True); stress=mean+a.gamma*(data.renew-mean)
    if stress.min() < -1e-8: raise RuntimeError("gamma 导致负新能源，请降低 gamma")
    stressed=energy_lp(load,data,renew_override=stress)
    if not base["success"] or not stressed["success"]: raise RuntimeError("能源情景 LP 不可行")
    rows=[]
    carbon_anchor=stressed["carbon"]
    for frac in (1.0,0.75,0.5,0.25,0.0):
        budget=max(1e-8, frac*carbon_anchor); r=energy_lp(load,data,renew_override=stress,carbon_budget=budget)
        if not r["success"]:
            rows.append({"碳预算比例":frac,"碳预算_tCO2":budget,"状态":"不可行","能源成本_CNY":np.nan,"碳排放_tCO2":np.nan,"相对成本最优成本变化_CNY":np.nan,"减排量_tCO2":np.nan})
            continue
        rows.append({"碳预算比例":frac,"碳预算_tCO2":budget,"状态":"可行","能源成本_CNY":r["cost"],"碳排放_tCO2":r["carbon"],"相对成本最优成本变化_CNY":r["cost"]-stressed["cost"],"减排量_tCO2":stressed["carbon"]-r["carbon"]})
    df=pd.DataFrame(rows); df["平均减排成本_CNY每tCO2"]=df["相对成本最优成本变化_CNY"]/df["减排量_tCO2"].replace(0,np.nan); df.to_csv(out/"q4_新能源压力_碳预算情景.csv",index=False,encoding="utf-8-sig")
    summary={"状态":"DRAFT / NEEDS_REVIEW","排程口径":"固定 QoS 字典序排程，能源/储能再调度","基准新能源_成本_CNY":base["cost"],"基准新能源_碳排_tCO2":base["carbon"],"压力场景gamma":a.gamma,"压力新能源_成本最优_CNY":stressed["cost"],"压力新能源_成本最优碳排_tCO2":stressed["carbon"],"碳预算结果文件":"q4_新能源压力_碳预算情景.csv"}
    (out/"q4_energy_scenario_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
