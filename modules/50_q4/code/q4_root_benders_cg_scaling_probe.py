#!/usr/bin/env python3
import zipfile, xml.etree.ElementTree as ET, re, math, time, json, os, gc, resource, sys
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix, csr_matrix, hstack, vstack

BASE='/mnt/data'
REGIONS=[f'Region{x}' for x in 'ABCDEF']; RIDX={r:i for i,r in enumerate(REGIONS)}; R=6
NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'; RNS='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
TLOAD=2407; TTASK=2406
ALPHA_TYPES=['AITraining','BatchInference','RealTimeInference']

def colnum(ref):
    s=re.match(r'([A-Z]+)',ref).group(1); n=0
    for c in s: n=n*26+ord(c)-64
    return n-1

def read_xlsx(path,sheet_name=None):
    with zipfile.ZipFile(path) as z:
        ss=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            root=ET.fromstring(z.read('xl/sharedStrings.xml'))
            ss=[''.join(t.text or '' for t in si.iter(f'{{{NS}}}t')) for si in root.findall(f'{{{NS}}}si')]
        wb=ET.fromstring(z.read('xl/workbook.xml')); rel=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        rmap={x.attrib['Id']:x.attrib['Target'] for x in rel}; sheets=[]
        for s in wb.find(f'{{{NS}}}sheets'):
            target=rmap[s.attrib[f'{{{RNS}}}id']]
            if not target.startswith('xl/'): target='xl/'+target
            target=target.replace('xl//','xl/')
            sheets.append((s.attrib['name'],target))
        _,target=sheets[0] if sheet_name is None else next(x for x in sheets if x[0]==sheet_name)
        root=ET.fromstring(z.read(target)); out=[]; hdr=None
        for row in root.findall(f'.//{{{NS}}}sheetData/{{{NS}}}row'):
            d={}
            for c in row.findall(f'{{{NS}}}c'):
                i=colnum(c.attrib['r']); typ=c.attrib.get('t'); v=c.find(f'{{{NS}}}v'); val='' if v is None else v.text
                if typ=='s' and val!='': val=ss[int(val)]
                elif typ=='inlineStr':
                    t=c.find(f'{{{NS}}}is/{{{NS}}}t'); val=t.text if t is not None else ''
                d[i]=val
            if hdr is None:
                hdr=[d.get(i,'') for i in range(max(d)+1)] if d else []; continue
            out.append({hdr[i]:d.get(i,'') for i in range(len(hdr))})
        return out

def fnum(x):
    try:return float(x)
    except:return x

def overlap(duration_min):
    p=duration_min/60.; n=int(math.ceil(p-1e-12))
    return np.array([max(0.,min(j+1.,p)-j) for j in range(n)],float)

def rss_mb():return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024

print('loading...',flush=True); t0=time.time()
w=read_xlsx(BASE+'/workload_trace.xlsx')
grows=read_xlsx(BASE+'/GPU_information.xlsx','GPU中心基础情况')
latrows=read_xlsx(BASE+'/network_latency.xlsx','network_latency')
pmrows=read_xlsx(BASE+'/power_mapping.xlsx','任务功率映射')
rrows=read_xlsx(BASE+'/region_time_data.xlsx','region_time_data')
srows=read_xlsx(BASE+'/storage_information.xlsx','storage_information')
for x in w:
    for k in ['TaskID','ArrivalHour','GPU_Demand','EstimatedDuration_min','MaxLatency_ms','LatestFinishHour','EarliestStartHour']:x[k]=fnum(x[k])
G={x['Region']:{k:fnum(v) for k,v in x.items()} for x in grows}; PM={x['TaskType']:fnum(x['GPU_Power_MW_per_EquivalentGPU']) for x in pmrows}
LAT=np.zeros((6,6))
for x in latrows:LAT[RIDX[x['FromRegion']],RIDX[x['ToRegion']]]=fnum(x['NetworkLatency_ms'])
ST={x['Region']:{k:fnum(v) for k,v in x.items()} for x in srows}
fields=['AvailableRenewable_MW','ElectricityPrice_CNY_per_MWh','SellPrice_CNY_per_MWh','CarbonIntensity_tCO2_per_MWh','NonAI_IT_Load_MW']
RT={f:np.zeros((R,TLOAD)) for f in fields}
for x in rrows:
    h=int(float(x['Hour'])); rr=RIDX[x['Region']]
    for f in fields:RT[f][rr,h]=fnum(x[f])
PUE=np.array([G[r]['PUE'] for r in REGIONS]); AVGPU=np.array([G[r]['Available_GPU'] for r in REGIONS]); MAXIT=np.array([G[r]['Max_IT_Power_MW'] for r in REGIONS])
ALPHA_MIN=min(PM.values());ALPHA_MAX=max(PM.values())
print('loaded',len(w),'in',time.time()-t0,'rss',rss_mb(),flush=True)

base_gpu=np.zeros((R,TTASK),dtype=np.float32); base_ai=np.zeros((R,TTASK),dtype=np.float32)
for x in w:
    rr=RIDX[x['SourceRegion']];s=int(x['ArrivalHour']);prof=overlap(int(x['EstimatedDuration_min']));ee=min(s+len(prof),TTASK)
    if ee<=s:continue
    ov=prof[:ee-s].astype(np.float32);base_gpu[rr,s:ee]+=np.float32(x['GPU_Demand'])*ov;base_ai[rr,s:ee]+=np.float32(x['GPU_Demand']*PM[x['TaskType']])*ov

def build_feasible_reference():
    usedg=base_gpu.astype(float).copy(); useda=base_ai.astype(float).copy()
    placements=[(RIDX[x['SourceRegion']],int(x['ArrivalHour'])) for x in w]
    profs=[overlap(int(x['EstimatedDuration_min'])) for x in w]
    moves=[]
    for _it in range(500):
        excess=usedg-AVGPU[:,None]; rr,hh=np.unravel_index(np.argmax(excess),excess.shape)
        if excess[rr,hh]<=1e-7: break
        cand=[]
        for i,x in enumerate(w):
            r0,s0=placements[i]
            if r0!=rr: continue
            z=hh-s0
            if 0<=z<len(profs[i]) and profs[i][z]>0:
                cand.append((0 if x['TaskType']!='RealTimeInference' else 1,-x['GPU_Demand']*profs[i][z],i))
        cand.sort(); fixed=False
        for _,_,i in cand:
            x=w[i];r0,s0=placements[i];prof=profs[i];alpha=PM[x['TaskType']]
            for z,ov in enumerate(prof):
                h=s0+z
                if h<TTASK: usedg[r0,h]-=x['GPU_Demand']*ov; useda[r0,h]-=x['GPU_Demand']*alpha*ov
            legal=np.where(LAT[RIDX[x['SourceRegion']]]<=x['MaxLatency_ms']+1e-9)[0]
            if x['TaskType']=='RealTimeInference': starts=[int(x['ArrivalHour'])]
            else:
                latest=int(math.floor(2406-x['EstimatedDuration_min']/60.+1e-10)); starts=range(int(x['ArrivalHour']),latest+1)
            found=None
            rs=sorted(legal,key=lambda r:(0 if r==RIDX[x['SourceRegion']] else 1,LAT[RIDX[x['SourceRegion']],r]))
            for s2 in starts:
                for r2 in rs:
                    good=True
                    for z,ov in enumerate(prof):
                        h=s2+z
                        if h>=TTASK or usedg[r2,h]+x['GPU_Demand']*ov>AVGPU[r2]+1e-8 or RT['NonAI_IT_Load_MW'][r2,h]+useda[r2,h]+x['GPU_Demand']*alpha*ov>MAXIT[r2]+1e-8:
                            good=False; break
                    if good: found=(int(r2),int(s2)); break
                if found: break
            if found and found!=(r0,s0):
                placements[i]=found
                for z,ov in enumerate(prof):
                    h=found[1]+z
                    if h<TTASK: usedg[found[0],h]+=x['GPU_Demand']*ov; useda[found[0],h]+=x['GPU_Demand']*alpha*ov
                moves.append((i,r0,s0,found[0],found[1])); fixed=True; break
            for z,ov in enumerate(prof):
                h=s0+z
                if h<TTASK: usedg[r0,h]+=x['GPU_Demand']*ov; useda[r0,h]+=x['GPU_Demand']*alpha*ov
        if not fixed: raise RuntimeError(('reference repair failed',int(rr),int(hh),float(excess[rr,hh])))
    if np.max(usedg-AVGPU[:,None])>1e-6: raise RuntimeError('reference GPU infeasible')
    if max(float((RT['NonAI_IT_Load_MW'][r,:TTASK]+useda[r]-MAXIT[r]).max()) for r in range(R))>1e-6: raise RuntimeError('reference IT infeasible')
    return placements,usedg,useda,moves

REF_PLACEMENTS,REF_GPU,REF_AI,REF_MOVES=build_feasible_reference()
print('reference repaired moves',len(REF_MOVES),'max_gpu_margin',float(np.min(AVGPU[:,None]-REF_GPU)),flush=True)

def select_tasks(n):
    if n>=len(w):return list(range(len(w)))
    counts={typ:sum(1 for x in w if x['TaskType']==typ) for typ in ALPHA_TYPES}
    quota={typ:int(round(n*counts[typ]/len(w))) for typ in ALPHA_TYPES}
    while sum(quota.values())<n:
        typ=max(ALPHA_TYPES,key=lambda z:counts[z]-quota[z]);quota[typ]+=1
    while sum(quota.values())>n:
        typ=max(ALPHA_TYPES,key=lambda z:quota[z]);quota[typ]-=1
    out=[]
    for typ in ALPHA_TYPES:
        ids=[i for i,x in enumerate(w) if x['TaskType']==typ]
        ids.sort(key=lambda i:(w[i]['ArrivalHour'],w[i]['TaskID']))
        q=quota[typ]
        if q>=len(ids):pick=ids
        else:
            pos=np.linspace(0,len(ids)-1,q).round().astype(int)
            pick=[];seen=set()
            for p in pos:
                if int(p) not in seen:seen.add(int(p));pick.append(ids[int(p)])
            if len(pick)<q:
                for j in ids:
                    if j not in pick:pick.append(j)
                    if len(pick)==q:break
        out.extend(pick)
    out.sort(key=lambda i:w[i]['TaskID'])
    return out[:n]

class EnergyTemplate:
    def __init__(self,r):
        self.r=r; T=TLOAD; nv=8; self.n=T*nv; self.idx=lambda t,v:t*nv+v
        eqr=[];eqc=[];eqv=[];beq=[];self.loadrows=[];row=0
        eta_c=ST[REGIONS[r]]['ChargeEfficiency'];eta_d=ST[REGIONS[r]]['DischargeEfficiency']
        for t in range(T):
            for v in [0,1,5,6]:eqr.append(row);eqc.append(self.idx(t,v));eqv.append(1.)
            beq.append(RT['AvailableRenewable_MW'][r,t]);row+=1
            for v in [0,3,4]:eqr.append(row);eqc.append(self.idx(t,v));eqv.append(1.)
            beq.append(0.);self.loadrows.append(row);row+=1
            eqr.append(row);eqc.append(self.idx(t,7));eqv.append(1.)
            if t>0:
                eqr.append(row);eqc.append(self.idx(t-1,7));eqv.append(-1.);beq.append(0.)
            else:beq.append(ST[REGIONS[r]]['InitialSOC_MWh'])
            eqr.extend([row,row,row]);eqc.extend([self.idx(t,1),self.idx(t,2),self.idx(t,3)]);eqv.extend([-eta_c,-eta_c,1./eta_d]);row+=1
        self.Aeq=coo_matrix((eqv,(eqr,eqc)),shape=(row,self.n)).tocsr();self.beq0=np.array(beq,float)
        ur=[];uc=[];uv=[];bub=[];row=0
        for t in range(T):
            ur += [row,row];uc += [self.idx(t,1),self.idx(t,2)];uv += [1.,1.];bub.append(ST[REGIONS[r]]['MaxChargePower_MW']);row+=1
            ur += [row,row];uc += [self.idx(t,4),self.idx(t,2)];uv += [1.,1.];bub.append(ST[REGIONS[r]]['MaxGridImport_MW']);row+=1
        self.Aub=coo_matrix((uv,(ur,uc)),shape=(row,self.n)).tocsr();self.bub=np.array(bub,float)
        self.c=np.zeros(self.n)
        for t in range(T):
            self.c[self.idx(t,2)]=RT['ElectricityPrice_CNY_per_MWh'][r,t]
            self.c[self.idx(t,4)]=RT['ElectricityPrice_CNY_per_MWh'][r,t]
            self.c[self.idx(t,5)]=-RT['SellPrice_CNY_per_MWh'][r,t]
        lb=np.zeros(self.n);ub=np.full(self.n,np.inf)
        sellcap=min(ST[REGIONS[r]]['SellLimit_MW'],ST[REGIONS[r]]['MaxGridExport_MW'])
        for t in range(T):
            ub[self.idx(t,3)]=ST[REGIONS[r]]['MaxDischargePower_MW'];ub[self.idx(t,5)]=sellcap
            lb[self.idx(t,7)]=ST[REGIONS[r]]['MinSOC_MWh'];ub[self.idx(t,7)]=ST[REGIONS[r]]['StorageCapacity_MWh']
        lb[self.idx(T-1,7)]=max(lb[self.idx(T-1,7)],ST[REGIONS[r]]['InitialSOC_MWh'])
        self.bounds=list(zip(lb,ub))
    def solve(self,L):
        b=self.beq0.copy();b[np.asarray(self.loadrows)]=L
        ts=time.time();res=linprog(self.c,A_ub=self.Aub,b_ub=self.bub,A_eq=self.Aeq,b_eq=b,bounds=self.bounds,method='highs');dt=time.time()-ts
        if not res.success:raise RuntimeError((self.r,res.message))
        lam=np.asarray(res.eqlin.marginals)[self.loadrows]
        return float(res.fun),lam,dt
ET=[EnergyTemplate(r) for r in range(R)]

class ScaleBench:
    def __init__(self,n):
        self.selidx=select_tasks(n); self.sel=[w[i] for i in self.selidx];self.N=len(self.sel)
        self.bg_gpu=REF_GPU.astype(np.float64).copy();self.bg_ai=REF_AI.astype(np.float64).copy()
        for gi,x in zip(self.selidx,self.sel):
            rr,s=REF_PLACEMENTS[gi];prof=overlap(int(x['EstimatedDuration_min']));alpha=PM[x['TaskType']]
            for z,ov in enumerate(prof):
                h=s+z
                if h<TTASK:
                    self.bg_gpu[rr,h]-=x['GPU_Demand']*ov;self.bg_ai[rr,h]-=x['GPU_Demand']*alpha*ov
        self.bg_load=np.zeros((R,TLOAD),float)
        self.bg_load[:,:TTASK]=PUE[:,None]*(RT['NonAI_IT_Load_MW'][:,:TTASK]+self.bg_ai)
        self.bg_load[:,TTASK]=PUE*RT['NonAI_IT_Load_MW'][:,TTASK]
        self.rhs_gpu=(AVGPU[:,None]-self.bg_gpu)
        self.rhs_it=(MAXIT[:,None]-RT['NonAI_IT_Load_MW'][:,:TTASK]-self.bg_ai)
        self.gmap=np.full((R,TTASK),-1,np.int32);self.imap=np.full((R,TTASK),-1,np.int32);row=0
        for r in range(R):
            for t in range(TTASK):
                rg=self.rhs_gpu[r,t];ri=self.rhs_it[r,t]
                kg=ki=True
                if ri>=ALPHA_MAX*rg-1e-10:ki=False
                elif ri<=ALPHA_MIN*rg+1e-10:kg=False
                if kg:self.gmap[r,t]=row;row+=1
                if ki:self.imap[r,t]=row;row+=1
        self.nres=row;self.resrhs=np.empty(row,float)
        for r in range(R):
            for t in range(TTASK):
                if self.gmap[r,t]>=0:self.resrhs[self.gmap[r,t]]=self.rhs_gpu[r,t]
                if self.imap[r,t]>=0:self.resrhs[self.imap[r,t]]=self.rhs_it[r,t]
        self.cols=[];self.colset=set();self.Aassign=csr_matrix((self.N,0));self.Ares=csr_matrix((self.nres,0));self.Aload=csr_matrix((R*TLOAD,0))
        self.cuts=[]
        self.types=np.array([ALPHA_TYPES.index(x['TaskType']) for x in self.sel],np.int8)
        self.arrival=np.array([int(x['ArrivalHour']) for x in self.sel],np.int16)
        self.dur=np.array([int(x['EstimatedDuration_min']) for x in self.sel],np.int16)
        self.gpu=np.array([float(x['GPU_Demand']) for x in self.sel],float)
        self.source=np.array([RIDX[x['SourceRegion']] for x in self.sel],np.int8)
        self.maxlat=np.array([float(x['MaxLatency_ms']) for x in self.sel],float)
        self.legal=[np.where(LAT[self.source[i]]<=self.maxlat[i]+1e-9)[0].astype(np.int8) for i in range(self.N)]
        init=[(i,int(REF_PLACEMENTS[gi][0]),int(REF_PLACEMENTS[gi][1])) for i,gi in enumerate(self.selidx)]
        self.add_columns(init)
    def add_columns(self,newcols):
        uniq=[]
        for tup in newcols:
            key=(int(tup[0]),int(tup[1]),int(tup[2]))
            if key in self.colset:continue
            self.colset.add(key);uniq.append(key)
        if not uniq:return 0
        m=len(uniq);ar=[];ac=[];av=[];rrs=[];ccs=[];vvs=[];lrs=[];lcs=[];lvs=[]
        for j,(i,r,s) in enumerate(uniq):
            x=self.sel[i];prof=overlap(int(x['EstimatedDuration_min'])); alpha=PM[x['TaskType']];g=float(x['GPU_Demand'])
            ar.append(i);ac.append(j);av.append(1.)
            for z,ov in enumerate(prof):
                h=s+z
                if h>=TTASK:break
                gm=self.gmap[r,h];im=self.imap[r,h]
                if gm>=0:rrs.append(int(gm));ccs.append(j);vvs.append(g*ov)
                if im>=0:rrs.append(int(im));ccs.append(j);vvs.append(alpha*g*ov)
                lrs.append(r*TLOAD+h);lcs.append(j);lvs.append(PUE[r]*alpha*g*ov)
        Aa=coo_matrix((av,(ar,ac)),shape=(self.N,m)).tocsr();Ar=coo_matrix((vvs,(rrs,ccs)),shape=(self.nres,m)).tocsr();Al=coo_matrix((lvs,(lrs,lcs)),shape=(R*TLOAD,m)).tocsr()
        self.Aassign=hstack([self.Aassign,Aa],format='csr');self.Ares=hstack([self.Ares,Ar],format='csr');self.Aload=hstack([self.Aload,Al],format='csr')
        self.cols.extend(uniq);return m
    def baseline_load(self):
        return self.bg_load + np.asarray(self.Aload[:,:self.N]@np.ones(self.N)).reshape(R,TLOAD)
    def add_benders_cut(self,r,L,Q,lam):
        const=Q+float(lam@(self.bg_load[r]-L));self.cuts.append({'r':int(r),'lam':lam.astype(np.float64),'const':float(const)})
    def solve_master(self):
        nc=len(self.cols);K=len(self.cuts);nv=nc+R;c=np.r_[np.zeros(nc),np.ones(R)]
        if K:
            lr=[];lc=[];lv=[];const=np.empty(K);theta_r=np.empty(K,np.int32)
            for k,cut in enumerate(self.cuts):
                r=cut['r'];lam=cut['lam'];supp=np.flatnonzero(np.abs(lam)>1e-10)
                lr.extend([k]*len(supp));lc.extend((r*TLOAD+supp).tolist());lv.extend(lam[supp].tolist());const[k]=cut['const'];theta_r[k]=r
            Lm=coo_matrix((lv,(lr,lc)),shape=(K,R*TLOAD)).tocsr();beta=(Lm@self.Aload).tocsr()
            Theta=coo_matrix((-np.ones(K),(np.arange(K),nc+theta_r)),shape=(K,nv)).tocsr()
            Crows=hstack([beta,csr_matrix((K,R))],format='csr')+Theta
            Aub=vstack([hstack([self.Ares,csr_matrix((self.nres,R))],format='csr'),Crows],format='csr');bub=np.r_[self.resrhs,-const]
        else:
            Aub=hstack([self.Ares,csr_matrix((self.nres,R))],format='csr');bub=self.resrhs
        Aeq=hstack([self.Aassign,csr_matrix((self.N,R))],format='csr');bounds=[(0,1)]*nc+[(None,None)]*R
        ts=time.time();res=linprog(c,A_ub=Aub,b_ub=bub,A_eq=Aeq,b_eq=np.ones(self.N),bounds=bounds,method='highs');dt=time.time()-ts
        if not res.success:raise RuntimeError(('master',self.N,nc,res.message))
        yres=np.asarray(res.ineqlin.marginals[:self.nres]);ycut=np.asarray(res.ineqlin.marginals[self.nres:]) if K else np.empty(0);yeq=np.asarray(res.eqlin.marginals)
        return res,dt,yeq,yres,ycut
    def current_load(self,x):
        return self.bg_load+np.asarray(self.Aload@x).reshape(R,TLOAD)
    def price(self,yeq,yres,ycut,add_per_task=2,tol=-1e-7):
        yg=np.zeros((R,TTASK));yi=np.zeros((R,TTASK))
        for r in range(R):
            gm=self.gmap[r];m=gm>=0;yg[r,m]=yres[gm[m]]
            im=self.imap[r];m=im>=0;yi[r,m]=yres[im[m]]
        psi=np.zeros((R,TLOAD))
        for k,cut in enumerate(self.cuts):
            if abs(ycut[k])>1e-14:psi[cut['r']]+=ycut[k]*cut['lam']
        uniq_keys=set()
        for i in range(self.N):
            if self.sel[i]['TaskType']=='RealTimeInference':continue
            for r in self.legal[i]:uniq_keys.add((int(self.types[i]),int(r),int(self.dur[i])))
        cache={}
        for typidx,r,dmin in uniq_keys:
            typ=ALPHA_TYPES[typidx];alpha=PM[typ];prof=overlap(dmin)
            q=-(yg[r]+alpha*yi[r]+PUE[r]*alpha*psi[r,:TTASK]);score=np.correlate(q,prof,mode='valid')
            latest=int(math.floor(2406-dmin/60.+1e-10));score=score[:latest+1]
            vals=np.empty_like(score);args=np.empty(score.size,np.int16);best=np.inf;bi=score.size-1
            for s in range(score.size-1,-1,-1):
                if score[s]<=best:best=score[s];bi=s
                vals[s]=best;args[s]=bi
            cache[(typidx,r,dmin)]=(vals,args)
        new=[];minrc=np.inf;neg_count=0
        for i in range(self.N):
            typ=self.sel[i]['TaskType'];g=self.gpu[i];cand=[]
            if typ=='RealTimeInference':
                s=int(self.arrival[i]);prof=overlap(int(self.dur[i]));alpha=PM[typ]
                for r in self.legal[i]:
                    term=0.
                    for z,ov in enumerate(prof):
                        h=s+z
                        if h<TTASK:term += g*ov*(-(yg[r,h]+alpha*yi[r,h]+PUE[r]*alpha*psi[r,h]))
                    rc=-yeq[i]+term;minrc=min(minrc,rc)
                    if rc<tol and (i,int(r),s) not in self.colset:cand.append((rc,(i,int(r),s)))
            else:
                a=int(self.arrival[i]);typidx=int(self.types[i]);d=int(self.dur[i])
                for r in self.legal[i]:
                    vals,args=cache[(typidx,int(r),d)]
                    if a>=len(vals):continue
                    s=int(args[a]);rc=-yeq[i]+g*float(vals[a]);minrc=min(minrc,rc)
                    if rc<tol and (i,int(r),s) not in self.colset:cand.append((rc,(i,int(r),s)))
            if cand:
                cand.sort(key=lambda z:z[0]);neg_count+=len(cand);new.extend([z[1] for z in cand[:add_per_task]])
        return new,float(minrc),int(neg_count),len(cache)

def run_scale(n,max_iter=30,wall_cap=1800):
    print('\n=== SCALE',n,'===',flush=True);start=time.time();b=ScaleBench(n);build=time.time()-start
    L=b.baseline_load();energy0=0
    for r in range(R):
        Q,lam,dt=ET[r].solve(L[r]);energy0+=dt;b.add_benders_cut(r,L[r],Q,lam)
    hist=[];status='MAXITER'
    for it in range(1,max_iter+1):
        if time.time()-start>wall_cap:status='WALL_CAP';break
        res,tm,yeq,yres,ycut=b.solve_master();nc=len(b.cols);x=res.x[:nc];theta=res.x[nc:]
        L=b.current_load(x);Qsum=0.;te=0.;newcuts=0
        for r in range(R):
            Q,lam,dt=ET[r].solve(L[r]);te+=dt;Qsum+=Q
            if theta[r] < Q-1e-5:b.add_benders_cut(r,L[r],Q,lam);newcuts+=1
        lb=float(res.fun);gap=float(Qsum-lb)
        rec={'iter':it,'columns':nc,'cuts':len(b.cuts),'master_s':tm,'energy_s':te,'lb':lb,'recourse':Qsum,'gap':gap,'newcuts':newcuts,'rss_mb':rss_mb()}
        if newcuts:
            hist.append(rec);print(rec,flush=True);continue
        tp=time.time();newcols,minrc,neg_count,ntpl=b.price(yeq,yres,ycut,add_per_task=2);tp=time.time()-tp
        added=b.add_columns(newcols);rec.update({'pricing_s':tp,'min_rc':minrc,'neg_candidates':neg_count,'templates':ntpl,'added':added});hist.append(rec);print(rec,flush=True)
        if added==0 and minrc>=-1e-7 and gap<=1e-4:
            status='CONVERGED';break
    total=time.time()-start
    return {'n':n,'status':status,'build_s':build,'initial_energy_s':energy0,'total_s':total,'peak_rss_mb':rss_mb(),'final_columns':len(b.cols),'columns_per_task':len(b.cols)/n,'cuts':len(b.cuts),'iterations':len(hist),'history':hist}

if __name__=='__main__':
    sizes=[int(x) for x in sys.argv[1:]] if len(sys.argv)>1 else [5000,10000,25000,50000]
    results=[]
    for n in sizes:
        try:results.append(run_scale(n,max_iter=30,wall_cap=2400))
        except Exception as e:
            import traceback;traceback.print_exc();results.append({'n':n,'status':'ERROR','error':repr(e),'peak_rss_mb':rss_mb()})
        gc.collect()
    out={'generated_at':'2026-08-17','results':results}
    open(BASE+'/q4_root_benders_cg_scaling_probe_20260817.json','w').write(json.dumps(out,ensure_ascii=False,indent=2))
    print('\nWROTE JSON',flush=True)
