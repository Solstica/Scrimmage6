#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q4 Probe 3: exact joint MILP vs Benders, plus carbon-budget stress probe.

Usage:
    python q4_probe_benders.py <attachment_dir> [output_dir]

The benchmark uses 40 real tasks from ArrivalHour 2376--2390:
16 Training + 14 Batch + 10 RT, selected by GPU-hour within type.
All legal (region,start) candidates are kept. No top-k/wait-window truncation.
Results are DRAFT / NEEDS_REVIEW until independently reproduced.
"""
from pathlib import Path
import sys, math, time, json
import numpy as np
import pandas as pd
from scipy.optimize import linprog, milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix, csr_matrix, hstack, vstack
from tqdm.auto import tqdm

DEFAULT_ATTACHMENT_DIR=Path(r"D:\qq文件\2026年武汉理工大学数学建模训练题目7-9\C题附件")
DEFAULT_OUTPUT_DIR=Path(__file__).resolve().parents[1]/"results"/"local_probe"
if len(sys.argv)>3:
    raise SystemExit("Usage: python q4_probe_benders.py [attachment_dir] [output_dir]")
ATTACH=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else DEFAULT_ATTACHMENT_DIR
OUT=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else DEFAULT_OUTPUT_DIR
if len(sys.argv)==1:
    print(f"未传入参数，使用默认附件目录：{ATTACH}")
OUT.mkdir(parents=True,exist_ok=True)
T0,TTERM=2376,2406
EH=np.arange(T0,TTERM+1); XH=np.arange(T0,TTERM)
REGIONS=["RegionA","RegionB","RegionC","RegionD","RegionE","RegionF"]
RIDX={r:i for i,r in enumerate(REGIONS)}; R=len(REGIONS)

def overlap_profile(duration_min):
    p=float(duration_min)/60.0
    n=int(math.ceil(p-1e-12))
    return np.array([max(0.0,min(j+1.0,p)-j) for j in range(n)],float)

# ---------- load data ----------
w=pd.read_excel(ATTACH/"workload_trace.xlsx")
g=pd.read_excel(ATTACH/"GPU_information.xlsx",sheet_name="GPU中心基础情况").set_index("Region").loc[REGIONS]
lat0=pd.read_excel(ATTACH/"network_latency.xlsx",sheet_name="network_latency")
lat=lat0.pivot(index="FromRegion",columns="ToRegion",values="NetworkLatency_ms").loc[REGIONS,REGIONS].to_numpy(float)
pm0=pd.read_excel(ATTACH/"power_mapping.xlsx",sheet_name="任务功率映射")
PMAP=pm0.set_index("TaskType")["GPU_Power_MW_per_EquivalentGPU"].to_dict()
rt=pd.read_excel(ATTACH/"region_time_data.xlsx")
st=pd.read_excel(ATTACH/"storage_information.xlsx",sheet_name="storage_information").set_index("Region").loc[REGIONS]
wide={}
for c in ["AvailableRenewable_MW","ElectricityPrice_CNY_per_MWh","SellPrice_CNY_per_MWh",
          "CarbonIntensity_tCO2_per_MWh","NonAI_IT_Load_MW","Baseline_AI_IT_Load_MW","SOC_MWh"]:
    wide[c]=rt.pivot(index="Hour",columns="Region",values=c).reindex(index=range(2407),columns=REGIONS).to_numpy().T

# Baseline GPU/AI reconstruction.
base_gpu=np.zeros((R,2406)); base_ai=np.zeros((R,2406))
for t in tqdm(w.itertuples(index=False), total=len(w), desc="重建基线负荷", unit="任务"):
    rr=RIDX[t.SourceRegion]; prof=overlap_profile(t.EstimatedDuration_min); s=int(t.ArrivalHour)
    hs=np.arange(s,min(s+len(prof),2406)); ov=prof[:len(hs)]
    base_gpu[rr,hs]+=float(t.GPU_Demand)*ov
    base_ai[rr,hs]+=float(t.GPU_Demand)*float(PMAP[t.TaskType])*ov

# 40-task stress benchmark.
w2=w.copy(); w2["GPUHour"]=w2.GPU_Demand*w2.EstimatedDuration_min/60.0
pool=w2[(w2.ArrivalHour>=2376)&(w2.ArrivalHour<=2390)]
parts=[]
for typ,n in [("AITraining",16),("BatchInference",14),("RealTimeInference",10)]:
    parts.append(pool[pool.TaskType==typ].nlargest(n,"GPUHour"))
SEL=pd.concat(parts).sort_values("TaskID").reset_index(drop=True); NT=len(SEL)

# Fixed background = baseline minus selected tasks.
bg_gpu=base_gpu[:,T0:TTERM].copy(); bg_ai=base_ai[:,T0:TTERM].copy()
for t in SEL.itertuples(index=False):
    rr=RIDX[t.SourceRegion]; prof=overlap_profile(t.EstimatedDuration_min)
    hs=np.arange(int(t.ArrivalHour),int(t.ArrivalHour)+len(prof)); m=(hs>=T0)&(hs<TTERM)
    if m.any():
        hh=hs[m]-T0; ov=prof[m]
        bg_gpu[rr,hh]-=float(t.GPU_Demand)*ov
        bg_ai[rr,hh]-=float(t.GPU_Demand)*float(PMAP[t.TaskType])*ov
PUE=g.PUE.to_numpy(float)
bg_fac=np.zeros((R,len(EH)))
bg_fac[:,:-1]=PUE[:,None]*(wide["NonAI_IT_Load_MW"][:,T0:TTERM]+bg_ai)
bg_fac[:,-1]=PUE*wide["NonAI_IT_Load_MW"][:,TTERM]

# ---------- complete legal candidate set ----------
cands=[]; task_cands={}
for ti,t in enumerate(tqdm(SEL.itertuples(index=False), total=NT, desc="枚举全合法候选", unit="任务")):
    legal=np.where(lat[RIDX[t.SourceRegion],:]<=float(t.MaxLatency_ms)+1e-9)[0]
    ph=float(t.EstimatedDuration_min)/60.0
    starts=[int(t.ArrivalHour)] if t.TaskType=="RealTimeInference" else list(range(int(t.ArrivalHour),int(math.floor(min(float(t.LatestFinishHour),2406.0)-ph+1e-10))+1))
    prof=overlap_profile(t.EstimatedDuration_min); ids=[]
    for rr in legal:
        for s in starts:
            if s<T0 or s>=TTERM or s+ph>min(float(t.LatestFinishHour),2406.0)+1e-9: continue
            hs=np.arange(s,s+len(prof)); m=(hs>=T0)&(hs<TTERM)
            if not m.any(): continue
            hh=(hs[m]-T0).astype(int); ov=prof[m]
            cands.append(dict(task_idx=ti,TaskID=int(t.TaskID),region_idx=int(rr),region=REGIONS[rr],start=int(s),
                              wait=int(s)-int(t.ArrivalHour),latency=float(lat[RIDX[t.SourceRegion],rr]),hh=hh,
                              gpu_coef=float(t.GPU_Demand)*ov,
                              ai_coef=float(t.GPU_Demand)*float(PMAP[t.TaskType])*ov,
                              facility_coef=float(PUE[rr])*float(t.GPU_Demand)*float(PMAP[t.TaskType])*ov))
            ids.append(len(cands)-1)
    task_cands[ti]=ids
NC=len(cands); T=len(EH); TX=len(XH)
Aload=lil_matrix((R*T,NC)); Agpu=lil_matrix((R*TX,NC)); Aai=lil_matrix((R*TX,NC)); Afac=lil_matrix((R*TX,NC)); Aassign=lil_matrix((NT,NC))
for j,c in enumerate(tqdm(cands, desc="装配稀疏约束矩阵", unit="候选")):
    Aassign[c["task_idx"],j]=1; rr=c["region_idx"]
    for hh,fc,ac,gc in zip(c["hh"],c["facility_coef"],c["ai_coef"],c["gpu_coef"]):
        Aload[rr*T+hh,j]=fc; Agpu[rr*TX+hh,j]=gc; Aai[rr*TX+hh,j]=ac; Afac[rr*TX+hh,j]=fc
Aload=csr_matrix(Aload); Agpu=csr_matrix(Agpu); Aai=csr_matrix(Aai); Afac=csr_matrix(Afac); Aassign=csr_matrix(Aassign)
rhs_gpu=(g.Available_GPU.to_numpy(float)[:,None]-bg_gpu).reshape(-1)
rhs_ai=(g.Max_IT_Power_MW.to_numpy(float)[:,None]-wide["NonAI_IT_Load_MW"][:,T0:TTERM]-bg_ai).reshape(-1)
rhs_fac=(g.Max_Facility_Power_MW.to_numpy(float)[:,None]-bg_fac[:,:-1]).reshape(-1)
bg_flat=bg_fac.reshape(-1)
WAIT=np.array([c["wait"] for c in cands],float); LAT=np.array([c["latency"] for c in cands],float)
def load_from_x(x): return (bg_flat+Aload@x).reshape(R,T)
def sched_metrics(x):
    js=np.where(np.asarray(x)>0.5)[0]; waits=[]; lats=[]; mig=0
    for j in js:
        c=cands[j]; t=SEL.iloc[c["task_idx"]]; mig+=int(c["region"]!=t.SourceRegion); waits.append(c["wait"]); lats.append(c["latency"])
    return dict(migrated=int(mig),total_wait=float(sum(waits)),mean_wait=float(np.mean(waits)),max_wait=float(max(waits)),lat_sum=float(sum(lats)),lat_mean=float(np.mean(lats)))

base_cons=[LinearConstraint(Aassign,np.ones(NT),np.ones(NT)),
           LinearConstraint(Agpu,-np.inf*np.ones(R*TX),rhs_gpu),
           LinearConstraint(Aai,-np.inf*np.ones(R*TX),rhs_ai),
           LinearConstraint(Afac,-np.inf*np.ones(R*TX),rhs_fac)]
r0=milp(c=WAIT+1e-4*LAT,integrality=np.ones(NC),bounds=Bounds(np.zeros(NC),np.ones(NC)),constraints=base_cons)
if not r0.success: raise RuntimeError(r0.message)
X0=np.rint(r0.x).astype(int)

# ---------- energy LP ----------
VN=["u","qR","qG","d","gL","s","w","E"]; V={v:i for i,v in enumerate(VN)}; NV=len(VN)
def eidx(r,t,v): return (r*T+t)*NV+V[v]
renew=wide["AvailableRenewable_MW"][:,EH]; price=wide["ElectricityPrice_CNY_per_MWh"][:,EH]; sellp=wide["SellPrice_CNY_per_MWh"][:,EH]; ci=wide["CarbonIntensity_tCO2_per_MWh"][:,EH]; soc_prev=wide["SOC_MWh"][:,T0-1]

def energy_lp(load,renew_custom=None,carbon_budget=None,retx=False):
    rc=renew if renew_custom is None else renew_custom; n=R*T*NV; c=np.zeros(n)
    for r in range(R):
        for tt in range(T): c[eidx(r,tt,"gL")]=price[r,tt]; c[eidx(r,tt,"qG")]=price[r,tt]; c[eidx(r,tt,"s")]=-sellp[r,tt]
    Aeq=lil_matrix((3*R*T,n)); b=np.zeros(3*R*T); lr=np.empty((R,T),int); row=0
    for r in range(R):
        ec=float(st.iloc[r].ChargeEfficiency); ed=float(st.iloc[r].DischargeEfficiency)
        for tt in range(T):
            for v in ["u","qR","s","w"]: Aeq[row,eidx(r,tt,v)]=1
            b[row]=rc[r,tt]; row+=1
            for v in ["u","d","gL"]: Aeq[row,eidx(r,tt,v)]=1
            b[row]=load[r,tt]; lr[r,tt]=row; row+=1
            Aeq[row,eidx(r,tt,"E")]=1
            if tt>0: Aeq[row,eidx(r,tt-1,"E")]=-1
            else: b[row]=soc_prev[r]
            Aeq[row,eidx(r,tt,"qR")]=-ec; Aeq[row,eidx(r,tt,"qG")]=-ec; Aeq[row,eidx(r,tt,"d")]=1/ed; row+=1
    Aub=lil_matrix((2*R*T+(carbon_budget is not None),n)); bu=np.zeros(Aub.shape[0]); row=0
    for r in range(R):
        mc=float(st.iloc[r].MaxChargePower_MW); mi=float(st.iloc[r].MaxGridImport_MW)
        for tt in range(T):
            Aub[row,eidx(r,tt,"qR")]=1; Aub[row,eidx(r,tt,"qG")]=1; bu[row]=mc; row+=1
            Aub[row,eidx(r,tt,"gL")]=1; Aub[row,eidx(r,tt,"qG")]=1; bu[row]=mi; row+=1
    if carbon_budget is not None:
        for r in range(R):
            for tt in range(T): Aub[row,eidx(r,tt,"gL")]=ci[r,tt]; Aub[row,eidx(r,tt,"qG")]=ci[r,tt]
        bu[row]=carbon_budget
    lb=np.zeros(n); ub=np.full(n,np.inf)
    for r in range(R):
        minE,maxE=float(st.iloc[r].MinSOC_MWh),float(st.iloc[r].StorageCapacity_MWh); md=float(st.iloc[r].MaxDischargePower_MW); sl=min(float(st.iloc[r].SellLimit_MW),float(st.iloc[r].MaxGridExport_MW))
        for tt in range(T): ub[eidx(r,tt,"d")]=md; ub[eidx(r,tt,"s")]=sl; lb[eidx(r,tt,"E")]=minE; ub[eidx(r,tt,"E")]=maxE
        lb[eidx(r,T-1,"E")]=max(lb[eidx(r,T-1,"E")],float(st.iloc[r].InitialSOC_MWh))
    res=linprog(c,A_ub=csr_matrix(Aub),b_ub=bu,A_eq=csr_matrix(Aeq),b_eq=b,bounds=list(zip(lb,ub)),method="highs")
    if not res.success: return dict(success=False,message=res.message)
    x=res.x; cost=0.0; carbon=0.0; cost_r=np.zeros(R)
    for r in range(R):
        for tt in range(T):
            gp=x[eidx(r,tt,"gL")]+x[eidx(r,tt,"qG")]; z=price[r,tt]*gp-sellp[r,tt]*x[eidx(r,tt,"s")]
            cost+=z; cost_r[r]+=z; carbon+=ci[r,tt]*gp
    out=dict(success=True,cost=float(cost),carbon=float(carbon),lambda_=res.eqlin.marginals[lr],cost_r=cost_r)
    if retx: out["x"]=x
    return out

# ---------- exact joint MILP ----------
NE=R*T*NV; cE=np.zeros(NE); cCE=np.zeros(NE)
for r in range(R):
    for tt in range(T): cE[eidx(r,tt,"gL")]=price[r,tt]; cE[eidx(r,tt,"qG")]=price[r,tt]; cE[eidx(r,tt,"s")]=-sellp[r,tt]; cCE[eidx(r,tt,"gL")]=ci[r,tt]; cCE[eidx(r,tt,"qG")]=ci[r,tt]
AeqE=lil_matrix((3*R*T,NE)); beqE=np.zeros(3*R*T); row=0
for r in range(R):
    ec=float(st.iloc[r].ChargeEfficiency); ed=float(st.iloc[r].DischargeEfficiency)
    for tt in range(T):
        for v in ["u","qR","s","w"]: AeqE[row,eidx(r,tt,v)]=1
        beqE[row]=renew[r,tt]; row+=1
        for v in ["u","d","gL"]: AeqE[row,eidx(r,tt,v)]=1
        beqE[row]=bg_fac[r,tt]; row+=1
        AeqE[row,eidx(r,tt,"E")]=1
        if tt>0: AeqE[row,eidx(r,tt-1,"E")]=-1
        else: beqE[row]=soc_prev[r]
        AeqE[row,eidx(r,tt,"qR")]=-ec; AeqE[row,eidx(r,tt,"qG")]=-ec; AeqE[row,eidx(r,tt,"d")]=1/ed; row+=1
AeqE=csr_matrix(AeqE); AubE=lil_matrix((2*R*T,NE)); bubE=np.zeros(2*R*T); row=0
for r in range(R):
    mc=float(st.iloc[r].MaxChargePower_MW); mi=float(st.iloc[r].MaxGridImport_MW)
    for tt in range(T): AubE[row,eidx(r,tt,"qR")]=1; AubE[row,eidx(r,tt,"qG")]=1; bubE[row]=mc; row+=1; AubE[row,eidx(r,tt,"gL")]=1; AubE[row,eidx(r,tt,"qG")]=1; bubE[row]=mi; row+=1
AubE=csr_matrix(AubE); lbE=np.zeros(NE); ubE=np.full(NE,np.inf)
for r in range(R):
    minE,maxE=float(st.iloc[r].MinSOC_MWh),float(st.iloc[r].StorageCapacity_MWh); md=float(st.iloc[r].MaxDischargePower_MW); sl=min(float(st.iloc[r].SellLimit_MW),float(st.iloc[r].MaxGridExport_MW))
    for tt in range(T): ubE[eidx(r,tt,"d")]=md; ubE[eidx(r,tt,"s")]=sl; lbE[eidx(r,tt,"E")]=minE; ubE[eidx(r,tt,"E")]=maxE
    lbE[eidx(r,T-1,"E")]=max(lbE[eidx(r,T-1,"E")],float(st.iloc[r].InitialSOC_MWh))
Xeq=lil_matrix((3*R*T,NC))
for r in range(R):
    for tt in range(T): Xeq[(r*T+tt)*3+1,:]=-Aload[r*T+tt,:]
AeqJ=vstack([hstack([Aassign,csr_matrix((NT,NE))]),hstack([csr_matrix(Xeq),AeqE])]).tocsr()
AubJ=vstack([hstack([Agpu,csr_matrix((R*TX,NE))]),hstack([Aai,csr_matrix((R*TX,NE))]),hstack([Afac,csr_matrix((R*TX,NE))]),hstack([csr_matrix((2*R*T,NC)),AubE])]).tocsr()
bubJ=np.concatenate([rhs_gpu,rhs_ai,rhs_fac,bubE]); cJ=np.concatenate([np.zeros(NC),cE]); integ=np.concatenate([np.ones(NC),np.zeros(NE)]); lbJ=np.concatenate([np.zeros(NC),lbE]); ubJ=np.concatenate([np.ones(NC),ubE]); cCarbon=csr_matrix(np.concatenate([np.zeros(NC),cCE]).reshape(1,-1))
def beq_joint(rc):
    b=beqE.copy()
    for r in range(R):
        for tt in range(T): b[(r*T+tt)*3]=rc[r,tt]
    return np.concatenate([np.ones(NT),b])
def solve_joint(rc,carbon_budget=None,objx=None,cost_cap=None,wait_cap=None):
    b=beq_joint(rc); cons=[LinearConstraint(AeqJ,b,b),LinearConstraint(AubJ,-np.inf*np.ones(len(bubJ)),bubJ)]
    if carbon_budget is not None: cons.append(LinearConstraint(cCarbon,-np.inf,[carbon_budget]))
    if cost_cap is not None: cons.append(LinearConstraint(csr_matrix(cJ.reshape(1,-1)),-np.inf,[cost_cap]))
    if wait_cap is not None: cons.append(LinearConstraint(csr_matrix(np.concatenate([WAIT,np.zeros(NE)]).reshape(1,-1)),-np.inf,[wait_cap]))
    obj=cJ if objx is None else np.concatenate([objx,np.zeros(NE)])
    return milp(c=obj,integrality=integ,bounds=Bounds(lbJ,ubJ),constraints=cons,options={"time_limit":120,"mip_rel_gap":1e-9})

# ---------- Benders ----------
def benders(rc,carbon_budget=None,multicut=False,max_iter=30):
    cuts=[]; nogoods=[]; hist=[]; best=np.inf; bestx=None; converged=False
    e=energy_lp(load_from_x(X0),rc,carbon_budget); L0=load_from_x(X0)
    if not e["success"]:
        raise RuntimeError("Benders 初始排程的能源子问题不可行；该探针需要一个能源可行的初始排程。")
    if multicut and carbon_budget is None:
        for r in range(R):
            lam=e["lambda_"][r]; const=float(e["cost_r"][r]+lam@(bg_fac[r]-L0[r])); coef=np.asarray(lam@Aload[r*T:(r+1)*T,:]).ravel(); cuts.append((r,const,coef))
        ntheta=R
    else:
        lam=e["lambda_"].reshape(-1); const=float(e["cost"]+lam@(bg_flat-L0.reshape(-1))); coef=np.asarray(lam@Aload).ravel(); cuts.append((-1,const,coef)); ntheta=1
    best=e["cost"]; bestx=X0.copy()
    for it in tqdm(range(max_iter), desc="Benders 迭代", unit="轮"):
        n=NC+ntheta; obj=np.concatenate([np.zeros(NC),np.ones(ntheta)]); integM=np.concatenate([np.ones(NC),np.zeros(ntheta)]); lbM=np.concatenate([np.zeros(NC),np.full(ntheta,-1e9)]); ubM=np.concatenate([np.ones(NC),np.full(ntheta,1e9)])
        cons=[LinearConstraint(hstack([Aassign,csr_matrix((NT,ntheta))]),np.ones(NT),np.ones(NT)),LinearConstraint(hstack([Agpu,csr_matrix((R*TX,ntheta))]),-np.inf*np.ones(R*TX),rhs_gpu),LinearConstraint(hstack([Aai,csr_matrix((R*TX,ntheta))]),-np.inf*np.ones(R*TX),rhs_ai),LinearConstraint(hstack([Afac,csr_matrix((R*TX,ntheta))]),-np.inf*np.ones(R*TX),rhs_fac)]
        Ac=lil_matrix((len(cuts),n)); bc=np.zeros(len(cuts))
        for k,(rr,const,coef) in enumerate(cuts): Ac[k,:NC]=coef; Ac[k,NC+(rr if ntheta>1 else 0)]=-1; bc[k]=-const
        cons.append(LinearConstraint(csr_matrix(Ac),-np.inf*np.ones(len(cuts)),bc))
        if nogoods:
            Ang=lil_matrix((len(nogoods),n)); bng=np.full(len(nogoods),NT-1.0)
            for k,js in enumerate(nogoods): Ang[k,js]=1.0
            cons.append(LinearConstraint(csr_matrix(Ang),-np.inf*np.ones(len(nogoods)),bng))
        m=milp(c=obj,integrality=integM,bounds=Bounds(lbM,ubM),constraints=cons,options={"time_limit":60,"mip_rel_gap":1e-9})
        if not m.success: raise RuntimeError(m.message)
        xm=np.rint(m.x[:NC]).astype(int); em=energy_lp(load_from_x(xm),rc,carbon_budget)
        if not em["success"]:
            nogoods.append(np.flatnonzero(xm>0.5))
            hist.append(dict(iter=it+1,LB=float(m.fun),candidate_Q=None,UB=best,gap=None,cuts=len(cuts),nogoods=len(nogoods),energy_feasible=False))
            continue
        q=em["cost"]
        if q<best-1e-7: best=q; bestx=xm.copy()
        gap=best-float(m.fun); hist.append(dict(iter=it+1,LB=float(m.fun),candidate_Q=q,UB=best,gap=gap,cuts=len(cuts),nogoods=len(nogoods),energy_feasible=True))
        if gap<=1e-8*max(1.0,abs(best)):
            converged=True
            break
        Lm=load_from_x(xm)
        if multicut and carbon_budget is None:
            for r in range(R):
                lam=em["lambda_"][r]; const=float(em["cost_r"][r]+lam@(bg_fac[r]-Lm[r])); coef=np.asarray(lam@Aload[r*T:(r+1)*T,:]).ravel(); cuts.append((r,const,coef))
        else:
            lam=em["lambda_"].reshape(-1); const=float(em["cost"]+lam@(bg_flat-Lm.reshape(-1))); coef=np.asarray(lam@Aload).ravel(); cuts.append((-1,const,coef))
    return best,bestx,hist,converged

# Probe 3A: exact and region multi-cut.
t=time.time(); rex=solve_joint(renew); exact_t=time.time()-t
if not rex.success: raise RuntimeError(rex.message)
xex=np.rint(rex.x[:NC]).astype(int); Cstar=float(rex.fun)
t=time.time(); bcost,bx,bhist,bconverged=benders(renew,multicut=True); bend_t=time.time()-t
rw=solve_joint(renew,objx=WAIT,cost_cap=Cstar+1e-5); rlat=solve_joint(renew,objx=LAT,cost_cap=Cstar+1e-5,wait_cap=float(rw.fun)+1e-7); xlex=np.rint(rlat.x[:NC]).astype(int)

# Probe 3B: data-derived carbon activation threshold, then diagnostic gamma=1.4.
Llex=load_from_x(xlex); rmean=renew.mean(axis=1,keepdims=True); lo,hi=1.0,2.0
for _ in range(25):
    mid=(lo+hi)/2; er=energy_lp(Llex,rmean+mid*(renew-rmean))
    if er["carbon"]>1e-6: hi=mid
    else: lo=mid
gcrit=(lo+hi)/2; gamma=1.4; rg=rmean+gamma*(renew-rmean)
rg0=solve_joint(rg); xg0=np.rint(rg0.x[:NC]).astype(int); eg0=energy_lp(load_from_x(xg0),rg); C0=float(eg0["carbon"])
rows=[]
for frac in [1.0,0.75,0.5,0.25,0.0]:
    B=max(1e-8,frac*C0); t=time.time(); rj=solve_joint(rg,carbon_budget=B); et=time.time()-t; xj=np.rint(rj.x[:NC]).astype(int); ej=energy_lp(load_from_x(xj),rg,B); t=time.time(); bc,bxx,bh,bok=benders(rg,B,multicut=False); bt=time.time()-t
    rows.append(dict(fraction=frac,carbon_budget=B,exact_cost=float(rj.fun),exact_carbon=float(ej["carbon"]),exact_time_s=et,benders_cost=bc,benders_converged=bok,benders_iters=len(bh),benders_time_s=bt,**sched_metrics(xj)))
df=pd.DataFrame(rows); basec=float(df.iloc[0].exact_cost); basee=float(df.iloc[0].exact_carbon); df["cost_penalty_vs_costopt"]=df.exact_cost-basec; df["carbon_reduction_vs_costopt"]=basee-df.exact_carbon; df["avg_abatement_CNY_per_tCO2"]=df.cost_penalty_vs_costopt/df.carbon_reduction_vs_costopt.replace(0,np.nan)

pd.DataFrame(bhist).to_csv(OUT/"probe3_cost_benders_history.csv",index=False); df.to_csv(OUT/"probe3_carbon_budget_results.csv",index=False); SEL[["TaskID","TaskType","ArrivalHour","GPU_Demand","EstimatedDuration_min","SourceRegion","GPUHour"]].to_csv(OUT/"probe_selected_tasks.csv",index=False)
summary=dict(tasks=NT,candidates=NC,exact_cost=Cstar,exact_time_s=exact_t,benders_cost=bcost,benders_converged=bconverged,benders_iters=len(bhist),benders_time_s=bend_t,exact_lex_metrics=sched_metrics(xlex),gamma_critical_for_positive_carbon=gcrit,gamma_stress=gamma,stress_cost_opt_carbon=C0)
(OUT/"probe3_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2)); print(df.to_string(index=False))
