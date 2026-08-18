# Q4 计算压缩 A/B/C 探针结果（2026-08-17）

状态：`DRAFT / NEEDS_REVIEW`

目的：验证 `Q4_DATA_STRUCTURE_COMPUTE_REDUCTION_PLAN_20260817.md` 中三个不改变完整合法域的计算压缩：

- A：Facility duplicate + GPU/IT dominance exact presolve；
- B：按 Energy-LP dual support 稀疏装配 Benders cuts；
- C：全局 Carbon budget 改写为 Master 区域预算 `b_r` + regional recourse。

所有任务候选均使用完整 SLA / deadline / finish<=2406 合法域，不使用 top-k、固定等待窗口或最近区域裁剪。

## Probe A — exact presolve

附件逐区严格满足 `MaxFacility = PUE * MaxIT`，且 `FacilityLoad=PUE*ITLoad`，因此 Facility capacity 与 IT capacity 完全重复，可严格删除。

对 GPU/IT rows，使用当前 benchmark 的残余容量 `Gcap=AvailableGPU-bgGPU`、`Icap=MaxIT-NonAI-bgAI` 与 `alpha_min=0.08, alpha_max=0.16`：若 `Icap >= alpha_max*Gcap`，IT row 被 GPU row 支配；若 `Icap <= alpha_min*Gcap`，GPU row 被 IT row 支配；其余两条均保留。

| Tasks | Legal columns | Resource rows 原始→presolve | Row ↓ | Matrix nnz 原始→presolve | nnz ↓ | LP solve 原始→presolve | Objective diff |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 40 | 3,139 | 540 → 196 | 63.70% | 59,272 → 23,043 | 61.12% | 0.0274s → 0.0126s | 0 |
| 100 | 5,435 | 540 → 197 | 63.52% | 99,755 → 39,464 | 60.44% | 0.0451s → 0.0221s | 0 |
| 500 | 30,152 | 540 → 205 | 62.04% | 393,563 → 165,601 | 57.92% | 0.2199s → 0.1071s | 0 |

三组 LP 的 `nit` 与 objective 完全一致；presolve 后求解时间约减半。

**决策：采用。** 这是严格等价的模型 presolve，不属于启发式近似。正式 Q4 Task Master 不再同时保留 Facility/IT duplicate rows，并逐 `(r,t)` 应用 GPU/IT dominance gate。

## Probe B — sparse Benders cuts

在 40/100/500 个真实任务的 full explicit candidate benchmark 上运行 region-multi-cut Benders LP，并逐轮记录 Energy subproblem load-balance dual `lambda[r,t]` 的 support、`lambda^T Aload` 在 task columns 上的非零系数密度，以及 dense coefficient vector 与 sparse payload 的存储量。

| Tasks | Columns | Benders iters | Final gap | Mean `|supp(lambda)|` /31 | Max support | Mean column-cut density | Max density |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 40 | 3,139 | 2 | 0 | 4.07 | 12 | 3.35% | 9.65% |
| 100 | 5,435 | 2 | 0 | 3.36 | 12 | 2.57% | 10.60% |
| 500 | 30,152 | 4 | 0 | 3.50 | 12 | 2.79% | 9.84% |

500-task 中 Benders 总时间约 1.53s，其中六区 Energy LP 累计仅约 0.063s，主要时间已经落在 Master LP。

Cut 存储对比：40 tasks `0.352 MB → 0.0179 MB`（-94.91%）；100 tasks `0.609 MB → 0.0237 MB`（-96.10%）；500 tasks `9.166 MB → 0.3845 MB`（-95.81%）。

**决策：采用 sparse-cut assembly。** Benders cut 只保存/写入 `|coef|>tol` 的 active coefficients；正式全规模每轮重新检测 support，不固定假设“永远只有 3%”。

## Probe C — Carbon budget allocation Benders

原约束 `sum_r Carbon_r <= B_C` 改写为 Master 中 6 个连续变量 `b_r>=0, sum_r b_r<=B_C`，regional recourse 加 `Carbon_r <= b_r`。Regional optimality cut 对 `(L_r,b_r)` 同时线性化；若某 master point 的 `b_r` 小于该负荷的最小可达碳排，则由 regional min-carbon LP 生成 feasibility cut。

Probe C 复用 Probe 3 的 40-task frozen benchmark（2376--2390，16 Training + 14 Batch + 10 RT）和 `gamma=1.4` 诊断新能源压力场景。

Cost-opt anchor：Cost=`-5,018,111.400085 CNY`，Carbon=`53.6476298462 tCO2`。

| Budget | Global Cost | Allocation Cost | |Cost diff| | Global Carbon | Allocation Carbon |
|---:|---:|---:|---:|---:|---:|
| 100% | -5,018,111.400085 | -5,018,111.400085 | 9.3e-10 | 53.64763 | 53.64763 |
| 75% | -5,016,918.645302 | -5,016,918.645302 | 1.9e-9 | 40.23572 | 40.23572 |
| 50% | -5,015,725.890518 | -5,015,725.890518 | 9.3e-10 | 26.82381 | 26.82381 |
| 25% | -5,014,489.572050 | -5,014,489.572050 | 9.3e-10 | 13.41191 | 13.41191 |
| 0% | -5,013,150.079014 | -5,013,150.079014 | 9.3e-10 | 0 | 0 |

区域预算改写与 global-carbon formulation 一致到 solver tolerance。

小样本串行 wall time：global 方法五档约 `0.45--0.48s`；allocation 方法约 `0.72--1.07s`。当前实现把 6 个 regional LP 串行调用，40 tasks / 31 h 下函数/solver 启动开销使 allocation 更慢。

**决策：数学上通过，计算上暂不冻结为默认实现。** 单场景/小规模继续优先 global-carbon subproblem；full-horizon、多场景或真正并行执行时，再测试 `b_r + regional recourse` 是否获得 wall-time 优势。

## 总结

1. Probe A：resource matrix nnz 约下降 58--61%，小规模 LP solve time 约减半，目标完全不变；
2. Probe B：真实数据 active-set 下 Benders cuts 高度稀疏，sparse payload 比 dense cut 低约 95%，直接纳入全规模实现；
3. Probe C：carbon-budget allocation 是精确等价分解，但小规模串行实现不快，不能提前宣布性能收益；
4. 结合 exact column pricing，Q4 计算瓶颈进一步集中到 large Restricted Master degeneracy / integer refinement，而不是 Energy LP、pricing 或 cut storage；
5. `peak RAM 目标 10 GB / 硬上限 20 GB、总时间硬上限 9 h` 继续保留。Probe A+B 提高了落在目标区间内的可信度。

结果文件位于 `modules/50_q4/results/`：`q4_probeA_exact_presolve_20260817.csv`、`q4_probeB_sparse_cuts_summary_20260817.csv`、`q4_probeC_carbon_allocation_20260817.csv`、`q4_abc_probes_summary_20260817.json`。
