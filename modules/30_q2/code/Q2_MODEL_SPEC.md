# Q2 正式模型规范：碳感知时空工作负载调度

状态：`DRAFT / NEEDS_REVIEW`

## 0. 正式命名与术语纪律

Q2 正式模型名称优先采用已有文献中的术语：

**碳感知时空工作负载调度模型（Carbon-Aware Spatiotemporal Workload Scheduling）**。

本题在该成熟问题框架上进一步加入两类题目特化结构：

1. **资源容量约束（resource/capacity constraints）**：GPU、IT、Facility、GridImport、SLA、deadline；
2. **新能源弃电缓解（renewable curtailment mitigation）**：利用可延迟、可迁移任务吸收基准状态中的可用新能源弃电裕量。

此前使用的“任务时空柔性—弃电消纳耦合的碳感知资源约束调度模型”保留为**中文机制性描述**，不再把它包装成已有文献中的标准模型名。

“spatiotemporal flexibility / temporal and spatial workload shifting / carbon-aware workload scheduling / renewable curtailment mitigation / resource-constrained scheduling / time-indexed formulation / marginal resource allocation”均有对应文献来源；具体核对见 `Q2_TERMINOLOGY_AUDIT.md`。

SFETA（Spatio-temporal Flexibility and Energy-aware Task Assignment）是**本文自定义算法名**，不是已有标准算法或公认缩写。若论文保留该名称，必须明确写为“本文在 REPTA 思想基础上构造的任务分配启发式”，不能写成既有算法名称。

---

## 1. 题意到模型的对应

Q2 输入：第 0--2399 小时实际到达任务及逐时电力参数。

Q2 决策变量：每个任务的执行区域 `r_i` 与开工时刻 `s_i`；等价的时间索引二元变量为 `x[i,r,s]`。

Q2 算电耦合：

`任务时空调度 -> AI IT -> 总 IT -> Facility Load -> 增量能量平衡 -> Cost / Carbon / Renewable Utilization`。

Q2 目标/评价：运行成本、碳排放、网络时延、新能源利用率。当前不使用主观加权和。

SFETA 只负责求解/构造调度方案，不定义数学模型本身。

---

## 2. 任务时空调度与可行域

设任务 `i` 的到达小时、来源区域、类型、GPU 需求、持续时间、最晚完成时刻、最大允许网络时延分别为

`a_i, o_i, k_i, g_i, p_i, d_i, L_i`，其中 `p_i = EstimatedDuration_min/60`（h）。

### 2.1 空间可行域

`R_i = { r : NetworkLatency[o_i,r] <= L_i }`。

这对应文献中的 spatial workload shifting / spatial flexibility，但本题的具体可行域完全由附件 `network_latency.xlsx` 与 MaxLatency 决定。

### 2.2 时间可行域

- RealTimeInference：`s_i = a_i`；
- BatchInference / AITraining：`s_i >= a_i` 且 `s_i + p_i <= min(d_i,2406)`。

当前按 1 h 时段边界解释开工时刻。完整合法域为：

`C_i = R_i × T_i`。

不得人为增加“最多等待 24 h”“只看最近几个区域”“top-K 候选”等搜索域限制。

### 2.3 小时重叠

`omega(i,s,t) = max(0, min(t+1,s+p_i) - max(t,s))`（h）。

必须满足：

`sum_t omega(i,s,t) = p_i`（浮点容差内）。

---

## 3. 调度后的算力负荷

令 `Delta t = 1 h`，任务类型 `k` 的单位 GPU IT 功率映射为 `alpha[k]`（MW/GPU）。

### 3.1 AI IT 平均功率

严格按量纲写为：

`P_AI[r,t](x) = (1/Delta t) * sum_{i,s} alpha[k_i] * g_i * omega(i,s,t) * x[i,r,s]`（MW）。

由于 `Delta t = 1 h`，其数值与附件写法一致，但正文保留 `1/Delta t` 以避免 MW 与 MWh 混淆。

### 3.2 总 IT 与设施负荷

`P_IT[r,t](x) = NonAI_IT_Load[r,t] + P_AI[r,t](x)`。

`L[r,t](x) = PUE[r] * P_IT[r,t](x)`。

基准设施负荷：

`L0[r,t] = PUE[r] * (NonAI_IT_Load[r,t] + Baseline_AI_IT_Load[r,t])`。

定义任务调度造成的设施负荷增量：

`DeltaL[r,t] = L[r,t](x) - L0[r,t]`。

这是 Q2 从计算侧进入能源侧的唯一负荷接口。

### 3.3 GPU-hour 容量约束

附件明确按实际小时重叠时长折算 GPU-hour，因此必须显式写为：

`sum_{i,s} g_i * omega(i,s,t) * x[i,r,s] <= AvailableGPU[r] * Delta t`。

同时满足：

`P_IT[r,t](x) <= MaxITPower[r]`，

`L[r,t](x) <= MaxFacilityPower[r]`。

---

## 4. AvailableRenewable 与基准弃电裕量

题目给定的外生新能源输入是 `AvailableRenewable[r,t]`。Q2 不用 `Curtailment0` 替代该输入，而把基准弃电解释为由可用新能源及基准能源分配导出的**剩余可消纳裕量**。

若附件基准新能源分配满足：

`AvailableRenewable = UsedRenewable0 + RenewableCharge0 + GridSell0 + Curtailment0`，

则必须审计：

`Curtailment0[r,t] = AvailableRenewable[r,t] - UsedRenewable0[r,t] - RenewableCharge0[r,t] - GridSell0[r,t]`。

若该恒等式在数据中不成立，则不得继续使用本节口径，需回到附件字段定义重新核对。

因此：

- `AvailableRenewable` 是题面要求考虑的原始外生信号；
- `Curtailment0` 是在基准运行状态下由该信号导出的、可被新计算负荷进一步吸收的新能源裕量。

---

## 5. Q2 能源层边界：基准状态增量能量平衡

附件统一能量平衡为：

`GridPurchase + AvailableRenewable + DischargePower = TotalLoad + ChargePower + GridSell + Curtailment`。

Q2 的显式决策只有任务迁移与开工时段。为与 Q3 的储能优化形成清晰递进，Q2 作如下**题目特化建模假设**：

- `GridCharge0, RenewableCharge0, DischargePower0, GridSell0` 保持附件基准状态；
- Q2 只改变任务调度造成的设施负荷；
- 新增负荷先吸收基准弃电裕量，剩余部分增加供负荷购电；
- 负荷降低先减少基准供负荷购电，若仍有剩余则表现为新能源直接消纳下降、弃电增加。

该规则称为“基准状态增量能量平衡”，只是本文核算规则，不作为已有文献模型名。

### 5.1 基准供负荷购电

定义：

`G0[r,t] = GridPurchase0[r,t] - GridCharge0[r,t]`。

必须审计：

`G0[r,t] >= -tolerance`。

禁止使用 `max(GridPurchase0-GridCharge0,0)` 静默修正异常。

基准直接新能源：

`U0[r,t] = UsedRenewable0[r,t]`。

基准弃电：

`C0[r,t] = Curtailment0[r,t]`。

### 5.2 紧凑的增量购电分段式

定义供负荷购电变化 `DeltaG[r,t]`：

`DeltaG[r,t] = 0`, if `0 <= DeltaL[r,t] <= C0[r,t]`；

`DeltaG[r,t] = DeltaL[r,t] - C0[r,t]`, if `DeltaL[r,t] > C0[r,t]`；

`DeltaG[r,t] = -min(-DeltaL[r,t], G0[r,t])`, if `DeltaL[r,t] < 0`。

含义：

1. 增量负荷不超过弃电裕量：全部由原弃电吸收，不增加购电；
2. 增量负荷超过弃电裕量：超出部分新增购电；
3. 负荷下降：先减少原有供负荷购电。

### 5.3 弃电与直接新能源变化

由新旧能量平衡相减：

`DeltaGridPurchase[r,t] = DeltaL[r,t] + DeltaCurtailment[r,t]`。

在 Q2 固定 `GridCharge0` 的条件下，`DeltaGridPurchase = DeltaG`，故：

`DeltaCurtailment[r,t] = DeltaG[r,t] - DeltaL[r,t]`。

`DeltaUsedRenewable[r,t] = -DeltaCurtailment[r,t]`。

更新后：

`GridPurchase[r,t] = GridPurchase0[r,t] + DeltaG[r,t]`；

`Curtailment[r,t] = C0[r,t] + DeltaCurtailment[r,t]`；

`UsedRenewable[r,t] = U0[r,t] - DeltaCurtailment[r,t]`。

并保持：

- `RenewableCharge = RenewableCharge0`；
- `GridCharge = GridCharge0`；
- `DischargePower = DischargePower0`；
- `GridSell = GridSell0`。

### 5.4 能源侧审计边界

必须满足：

`GridPurchase[r,t] >= 0`，

`UsedRenewable[r,t] >= 0`，

`Curtailment[r,t] >= 0`。

更新后还需满足区域统一购售电边界：

`GridPurchase[r,t] <= MaxGridImport[r]`，

`GridSell0[r,t] <= MaxGridExport[r]`。

如果上述任一条件失败，不允许静默截断；说明当前“固定基准储能/外送策略”的 Q2 假设在该候选方案上失效，需返回建模手复核。

---

## 6. 成本、碳与新能源利用率

### 6.1 运行成本

绝对运行成本：

`Cost = sum_{r,t} [GridPurchase[r,t] * Price[r,t] - GridSell0[r,t] * SellPrice[r,t]] * Delta t`。

由于 `GridSell0` 固定，调度方案之间的差异可写为：

`DeltaCost_sched = sum_{r,t} DeltaG[r,t] * Price[r,t] * Delta t`。

### 6.2 碳排放

`Carbon = sum_{r,t} GridPurchase[r,t] * CarbonIntensity[r,t] * Delta t`。

调度增量：

`DeltaCarbon_sched = sum_{r,t} DeltaG[r,t] * CarbonIntensity[r,t] * Delta t`。

CarbonIntensity 必须真正参与 Q2 的候选调度或碳约束，不能只在调度完成后做后验统计，否则不足以体现 carbon-aware scheduling。

### 6.3 新能源利用率

按附件统一口径：

`eta_R = sum_{r,t} (UsedRenewable[r,t] + RenewableCharge0[r,t] + GridSell0[r,t]) * Delta t / sum_{r,t} AvailableRenewable[r,t] * Delta t`。

Q2 调度引起的新增直接新能源消纳为：

`DeltaRenewableUse = sum_{r,t} (-DeltaCurtailment[r,t]) * Delta t`。

因此模型中的实际因果链为：

`任务时空迁移 -> Facility Load变化 -> renewable curtailment mitigation / 新增购电 -> Cost / Carbon / Renewable Utilization`。

---

## 7. 任务与系统硬约束

所有任务必须满足：

- 每个任务恰好选择一个 `(r,s)`；
- NonPreemptive；
- 不可拆分；
- 运行过程中 Region 固定；
- GPU-hour 容量约束；
- Max IT power；
- Max Facility power；
- MaxGridImport / MaxGridExport；
- `NetworkLatency[o_i,r] <= MaxLatency_i`；
- EarliestStart / LatestFinish；
- `finish_i <= 2406`；
- 2406 无计算任务占用。

主任务到达时域为 0--2399；2400--2405 仅结清此前到达的可延迟任务，并计入调度导致的能源、成本与碳变化。

### 7.1 2406 口径

Q2 的任务调度只影响 0--2405。

- 若比较 baseline 与 Q2 的**调度增量 Cost/Carbon**，只需要统计 0--2405；
- 若论文报告包含 2406 的全系统绝对 Cost/Carbon，则 2406 只能使用共同的基准终端能源结算项，不得安排任何计算任务，也不得把它伪装成 Q2 调度收益。

---

## 8. 目标组织：先测冲突，再决定形式

题面允许运行成本、碳排放、网络时延和新能源利用率作为“目标或评价指标”，因此当前不构造跨量纲主观加权和。

当前规则：

1. **Latency**：先作为 SLA 硬约束，同时报告平均/分位时延、迁移率；
2. **Renewable utilization**：按统一公式报告，并额外报告 `DeltaCurtailment`；
3. **Cost 与 Carbon**：先分别做 Cost-only / Carbon-only 极值或近极值探针；
4. 若两者基本同向，采用单主目标 + 另一指标评价，同时保证 CarbonIntensity 仍进入候选优先级或碳约束；
5. 若存在实质冲突，再采用 epsilon-constraint，不使用人为权重。

这一部分在极值探针完成前保持 `NEEDS_REVIEW`。

---

## 9. SFETA 的正式定位

SFETA 是本文自定义名称，不是已有标准术语。

算法家族更准确的文献化描述是：

**priority-rule-based constructive task assignment / scheduling heuristic**，并吸收 REPTA 的非迭代任务分配思想与 CarbonScaler 的 marginal resource allocation 思想。

### 9.1 任务优先规则

不再把“least-flexible-first”写成已有算法名。当前只是本文的 priority rule：

1. `|R_i|` 小者优先（本题特化的空间可行域大小）；
2. slack / `|T_i|` 小者优先，其中 slack 对应经典 scheduling 中的 minimum-slack 思想；
3. 必要时 `GPU-hour = g_i * p_i` 大者优先。

该规则的依据来自本题 RT / Batch / Training 的真实时空柔性差异，而非主观权重。

### 9.2 候选位置评价

对每个合法 `(r,s)`，按当前调度状态计算：

- `DeltaCurtailment_i,r,s`；
- `DeltaG_i,r,s`；
- `DeltaCost_i,r,s`；
- `DeltaCarbon_i,r,s`；
- 是否触及 GPU/IT/Facility/GridImport/SLA/deadline 约束。

这属于文献中“marginal resource allocation / signal-aware scheduling”的本题化使用，而不是给区域定义静态绿色评分。

### 9.3 当前不加入的机制

- LSTM / 强化学习；
- PSO/GA 等黑箱元启发式；
- Q2 储能控制；
- 线路潮流；
- 带宽、迁移数据量、迁移能耗/迁移费用；
- 人为 top-K / 最大等待窗口。

---

## 10. 必须实现的审计门禁

程序手正式求解 Q2 前至少检查：

1. `DeltaL=0` 时能源结果精确复现附件 baseline；
2. `AvailableRenewable = UsedRenewable0 + RenewableCharge0 + GridSell0 + Curtailment0` 在数据中成立；
3. `G0 = GridPurchase0 - GridCharge0 >= -tol`；
4. 每个 `(r,t)` 更新后满足附件统一能量平衡；
5. `GridPurchase, UsedRenewable, Curtailment >= 0`；
6. `GridPurchase <= MaxGridImport`，`GridSell0 <= MaxGridExport`；
7. `sum_t omega(i,s,t)=p_i`；
8. GPU-hour / IT / Facility / SLA / deadline 零违规；
9. 2406 无任务占用；
10. Cost / Carbon / eta_R 按附件统一口径重算；
11. 不从 `storage_information.xlsx` 引入 SOC、充放电策略等 Q2 未授权决策自由度。

---

## 11. 当前模型总结

Q2 的正式科研语境应表述为：

**Carbon-Aware Spatiotemporal Workload Scheduling with resource-capacity constraints and renewable curtailment mitigation.**

中文可写为：

**碳感知时空工作负载调度模型，并嵌入资源容量约束与新能源弃电缓解机制。**

此前“任务时空柔性—弃电消纳耦合”仍然准确描述本题特化机制，但不再作为声称已有文献标准名称的模型名。

该结构同时保留了：

- 题目给定的任务迁移与开工时段决策；
- 数据中真实存在的 temporal/spatial flexibility；
- `AvailableRenewable` 作为原始新能源输入；
- `Curtailment0` 作为可进一步消纳的基准新能源裕量；
- CarbonIntensity 真正进入调度；
- Q2 与 Q3/Q4 能源决策自由度的边界；
- SFETA 作为本文构造式求解算法，而不是模型本身。
