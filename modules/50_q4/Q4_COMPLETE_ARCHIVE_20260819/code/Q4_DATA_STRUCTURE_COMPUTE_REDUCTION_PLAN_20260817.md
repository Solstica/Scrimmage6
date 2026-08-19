# Q4 数据结构驱动的计算压缩与 A/B/C 探针计划（2026-08-17）

状态：`DRAFT / NEEDS_REVIEW`

本文件记录在不改变完整合法任务域、不牺牲目标质量的前提下，对 Q4 `Benders + stabilized column generation` 的进一步数据结构化压缩。原则：所有删除/合并必须有等价性或支配性证明；禁止 arbitrary top-k、固定等待窗口、最近区域裁剪。

## 1. 已发现的严格等价结构

### 1.1 Facility capacity 与 IT capacity 完全重复

附件逐区满足

`Max_Facility_Power_MW = PUE * Max_IT_Power_MW`。

模型又有 `FacilityLoad=PUE*ITLoad`，故 Facility capacity row 与 IT capacity row 完全等价，可从 Task Master 中删除，不影响可行域或最优解。

### 1.2 GPU / IT row 的逐小时支配判据

三类任务 AI IT 功率映射范围为 `alpha in [0.08,0.16] MW/equivalent-GPU`。定义

`C_AI[r,t]=MaxIT[r]-NonAI[r,t]`。

若 `C_AI[r,t] >= 0.16*AvailableGPU[r]`，则 IT row 严格冗余；若 `C_AI[r,t] <= 0.08*AvailableGPU[r]`，则 GPU row 严格冗余；中间区间两者均保留。

附件全时域初步统计：14436 个 Region-Hour 中，约 9950 个 IT row 冗余、2243 个 GPU row 冗余、仅约 2243 个需要两条同时保留。结合 Facility duplicate elimination，资源 rows 由 43308 降至约 16679；对完整 2.33e8 候选的基础 matrix nonzeros 初步估计由约 2.958e9 降至约 1.279e9，下降约 56.8%。正式值由 Probe A 独立复现。

### 1.3 Benders recourse dual 的 active-set 稀疏性

baseline full-horizon Energy LP 的 load-balance dual 初步观察：A/B/C/D 基本为 0，E/F 仅少量时段非零。正式实现应按 `supp(lambda)` 稀疏装配 Benders cut，不为所有 active columns 建 dense cut coefficient。该稀疏性不是永久定理，每轮必须动态重新检测。

### 1.4 Carbon budget 可通过区域预算变量重新分解

全局 `sum_r Carbon_r <= B_C` 可在 Master 中增加 6 个 `b_r>=0`，满足 `sum_r b_r<=B_C`，各区域 recourse 增加 `Carbon_r<=b_r`。该改写与原全局碳预算等价，但可恢复 6 个 regional energy subproblems 并行求解。Probe C 将与 global-carbon subproblem 逐档精确对照。

## 2. 数据结构上明确不采用的压缩

- 不做任务同质聚合：50,000 任务在关键 signature 上几乎全部唯一，收益极小；
- 不把 100 天折叠成 1 天：renewable 虽 24h 严格重复，但任务、NonAI、Price/CI 状态并不允许整体日级合并；
- 不合并 A/B/C 或 E/F：PUE、容量、电价、CI、储能、latency 等均存在差异；
- 不固定 RT 本地执行；RT 仍保留完整 SLA-feasible Region；
- 不按当前 dual/price 永久删除合法 column。

## 3. Pricing 模板化

附件空间合法域只有少量模板；flexible task 的 duration 最多约 7 个小时格、Duration 取值有限。正式 pricing 使用 `(TaskType,Region,Duration)` overlap/power template + suffix-min/argmin，column 仅存 `(TaskID,Region,Start,DurationClass)` 等 packed metadata，禁止 Python dict/object per-column。

## 4. Column pool 管理

- 普通 aging：长期非 basic、x=0、reduced cost 为正的 column 可从 RAM 移出；exact pricing 保证必要时可重新生成，故不改变完整域；
- 有 incumbent 后才考虑 reduced-cost fixing；必须由 `LB/UB/reduced cost` 证明安全，禁止经验阈值永久删列；
- dual stabilization 只用于 pricing 加速，终止时必须用原始 dual 做 exact reduced-cost scan。

## 5. A/B/C 三个必须完成的探针

### Probe A — exact presolve

在 40/100/500 个真实任务的完整合法候选上，对比：

1. 原始 `GPU + IT + Facility` rows；
2. 删除 Facility duplicate；
3. 再应用逐 `(r,t)` GPU/IT dominance。

记录：rows、nnz、build/solve time、peak RSS、LP objective；要求 presolved 与 original objective 在 solver tolerance 内相同。

### Probe B — sparse Benders cuts

在至少 40/100/500-task Benders 运行中逐轮记录：

- `|supp(lambda_r^k)|`；
- active-column cut coefficient nnz/density；
- sparse vs dense-equivalent cut assembly time/memory；
- LB/UB/gap 一致性。

结论只允许写“附件与当前迭代实际观测的 sparsity”，不得把 baseline 0.9% 外推成固定比例。

### Probe C — carbon-budget allocation Benders

沿 Probe 3 的 100/75/50/25/0% Carbon budget：

- 方法 G：global energy subproblem + global Benders cut；
- 方法 R：Master `b_r` allocation + 6 regional carbon-constrained subproblems + regional cuts。

逐档比较：Cost、Carbon、LB/UB、iterations、energy-subproblem wall time、总 wall time；要求 Cost/Carbon/optimum 一致到 solver tolerance。

## 6. 工程门禁

继续执行：

- 目标 peak RAM <= 10 GB，绝对 <=20 GB；
- 总 wall-clock <=9 h；
- 目标常规 active RMP 内存进一步压到约 4--8 GB；
- 任何优化必须先在小规模 exact benchmark 上验证等价性。
