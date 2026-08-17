#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q4 成本优先后的 QoS/时延字典序精化。

读取 q4_full_solver.py 已完成成本根节点闭合时保存的列池与 Benders cut：
1) EnergyCost <= C*+tol 下最小总等待；
2) 保持成本、等待最优下最小时延。
每一阶段都用真实能源 LP 复核；若 Benders 近似不足则补 cut 后重解。
"""
from __future__ import annotations

import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import csr_matrix, hstack, vstack

from q4_full_solver import (DEFAULT_ATTACH, DEFAULT_OUT, REGIONS, Cut, assignment_matrix,
    cut_matrix, energy_lp, facility_load, load_solver_state, make_presolve_rows,
    read_data, resource_matrix)


def build_mip(pool, data, gpu_row, it_row, rhs, cuts, objective, cost_cap, wait_cap=None):
    n = len(pool); ar = assignment_matrix(pool, len(data.task)); resource = resource_matrix(pool, data, gpu_row, it_row, len(rhs)); cm = cut_matrix(pool, data, cuts)
    aub = vstack([hstack([resource, csr_matrix((len(rhs),1))]), hstack([cm, csr_matrix(-np.ones((len(cuts),1)))])]).tocsr()
    bub = list(rhs) + [-cut.const for cut in cuts]
    # theta is an underestimator, so the cap must be rechecked with the true energy LP below.
    cost_row = csr_matrix(np.r_[np.zeros(n), 1.0].reshape(1,-1)); aub = vstack([aub, cost_row]).tocsr(); bub.append(cost_cap)
    if wait_cap is not None:
        wait_row = csr_matrix(np.r_[objective["wait"], 0.0].reshape(1,-1)); aub = vstack([aub, wait_row]).tocsr(); bub.append(wait_cap)
    aeq = hstack([ar, csr_matrix((len(data.task),1))]).tocsr()
    obj = objective["value"]
    result = milp(c=np.r_[obj, 0.0], integrality=np.r_[np.ones(n),0], bounds=Bounds(np.r_[np.zeros(n),-1e10],np.r_[np.ones(n),np.inf]), constraints=[LinearConstraint(aub,-np.inf*np.ones(len(bub)),np.asarray(bub)),LinearConstraint(aeq,np.ones(len(data.task)),np.ones(len(data.task)))], options={"time_limit":1800,"mip_rel_gap":1e-7})
    if not result.success: raise RuntimeError(result.message)
    return result.x[:n]


def main():
    parser=argparse.ArgumentParser(description="Q4 成本优先 QoS/时延精化")
    parser.add_argument("--attachment-dir",type=Path,default=DEFAULT_ATTACH)
    parser.add_argument("--input-dir",type=Path,default=DEFAULT_OUT)
    parser.add_argument("--output-dir",type=Path,default=Path(__file__).resolve().parents[1]/"results"/"qos_refinement")
    parser.add_argument("--cost-tolerance",type=float,default=1e-3)
    parser.add_argument("--max-benders",type=int,default=30)
    args=parser.parse_args(); inp=args.input_dir.resolve(); out=args.output_dir.resolve(); out.mkdir(parents=True,exist_ok=True)
    summary=json.loads((inp/"summary.json").read_text(encoding="utf-8")); cap=float(summary["可行上界_能源成本_CNY"])+args.cost_tolerance
    data=read_data(args.attachment_dir.resolve()); pool,cuts,_,_,_=load_solver_state(inp); gpu_row,it_row,rhs,_=make_presolve_rows(data); ti,rr,ss=pool.arrays()
    wait=(ss-data.arrival[ti]).astype(float)
    lat_raw=pd.read_excel(args.attachment_dir.resolve()/"network_latency.xlsx",sheet_name="network_latency").pivot(index="FromRegion",columns="ToRegion",values="NetworkLatency_ms").loc[list(REGIONS),list(REGIONS)].to_numpy(float)
    latency=np.asarray([lat_raw[int(data.source[t]),int(r)] for t,r in zip(ti,rr)],dtype=float)
    stages=[]
    def solve_with_validation(name, value, wait_cap=None):
        nonlocal cuts
        for attempt in range(1,args.max_benders+1):
            x=build_mip(pool,data,gpu_row,it_row,rhs,cuts,{"value":value,"wait":wait},cap,wait_cap)
            load=facility_load(pool,data,x); e=energy_lp(load,data)
            if not e["success"]: raise RuntimeError(e["message"])
            if e["cost"] <= cap+1e-4:
                stages.append({"阶段":name,"尝试":attempt,"真实能源成本_CNY":float(e["cost"]),"总等待_h":float(wait@x),"总时延_ms":float(latency@x),"Benders切数":len(cuts)})
                return x,e
            print(f"{name}：第 {attempt} 次真实成本 {e['cost']:.6f} 高于上界 {cap:.6f}，补充 Benders cut 后重解。")
            fixed=data.pue[:,None]*data.non_ai
            cuts.append(Cut(const=float(e["cost"]+np.sum(e["lam"]*(fixed-load))),lam=e["lam"].copy()))
        raise RuntimeError(name+f" 在 {args.max_benders} 次 Benders 校正内未满足真实成本上界")
    x_wait,e_wait=solve_with_validation("最小等待",wait)
    wait_star=float(wait@x_wait)
    x_lat,e_lat=solve_with_validation("最小时延",latency,wait_star+1e-6)
    chosen=np.flatnonzero(x_lat>0.5)
    result=pd.DataFrame({"TaskID":data.task.iloc[ti[chosen]]["TaskID"].to_numpy(),"任务类型":data.task.iloc[ti[chosen]]["TaskType"].to_numpy(),"源区域":[REGIONS[int(data.source[t])] for t in ti[chosen]],"目标区域":[REGIONS[int(r)] for r in rr[chosen]],"到达小时":data.arrival[ti[chosen]],"开工小时":ss[chosen],"等待_h":wait[chosen],"时延_ms":latency[chosen]})
    result["是否迁移"]=result["源区域"]!=result["目标区域"]; result.to_csv(out/"q4_字典序最终排程.csv",index=False,encoding="utf-8-sig")
    metrics={"状态":"DRAFT / NEEDS_REVIEW","列池范围":"成本目标已通过完整域定价的活动列池；QoS 精化未另行做全域零成本列定价","成本上界_CNY":cap,"最小等待_h":wait_star,"最终真实能源成本_CNY":float(e_lat["cost"]),"最终总等待_h":float(wait@x_lat),"最终平均等待_h":float(wait@x_lat/len(data.task)),"最终最大等待_h":float(wait[chosen].max()),"最终总时延_ms":float(latency@x_lat),"最终平均时延_ms":float(latency@x_lat/len(data.task)),"迁移任务数":int(result["是否迁移"].sum()),"阶段记录":stages}
    (out/"q4_qos_summary.json").write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding="utf-8"); print(json.dumps(metrics,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
