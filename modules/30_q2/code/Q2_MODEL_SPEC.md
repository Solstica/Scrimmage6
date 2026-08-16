# Q2 正式模型规范：碳感知时空资源约束任务调度

状态：`DRAFT / NEEDS_REVIEW`

本文件记录 Q2 当前正式建模口径。它在 `Q2_DATA_PROBES.md` 的数据探针基础上，先冻结**算力负荷到能源结果的平衡公式**，再规定 SFETA 应如何使用这些量。Q2 不把储能充放电、SOC、购售电策略本身设为优化决策；这些能源运行自由度留给 Q3/Q4。

## 1. 题意到模型的对应

Q2 的输入：0--2399 h 实际到达任务及逐时电力参数。

Q2 的决策变量：每个任务的执行区域 `r_i` 与开工时刻 `s_i`；等价二元变量为 `x[i,r,s]`。

Q2 的算电耦合：任务调度 -> AI IT -> 总 IT -> Facility Load -> 基准能源状态上的边际能源后果。

Q2 的目标/评价：运行成本、碳排放、网络时延、新能源利用率。当前不使用主观加权和。

SFETA 是 Q2 数学模型的求解/构造算法，不是模型本身。

---

## 2. 任务侧时空调度

设任务 `i` 的到达小时、来源区域、类型、GPU 需求、持续时长、最晚完成时刻、最大允许时延分别为

`a_i, o_i, k_i, g_i, p_i, d_i, L_i`，其中 `p_i = EstimatedDuration_min/60`。

### 2.1 合法区域

`R_i = { r : NetworkLatency[o_i,r] <= L_i }`。

### 2.2 合法开工时刻

- RealTimeInference：`s_i = a_i`；
- BatchInference / AITraining：`s_i >= a_i` 且 `s_i + p_i <= min(d_i,2406)`。

当前按 1 h 时段边界解释开工时刻；若后续题面确认连续开工，统一修改。

完整合法域：

`C_i = R_i × T_i`。

不得人为加入最大等待 24 h、最近若干区域、top-K 候选等搜索域限制。

### 2.3 小时重叠

`omega(i,s,t) = max(0, min(t+1,s+p_i) - max(t,s))`。

并检查 `sum_t omega(i,s,t) = p_i`。

---

## 3. 调度后的算力负荷

任务类型单位 GPU 的 IT 功率为 `alpha[k]`。

AI IT：

`P_AI[r,t](x) = sum_{i,s} alpha[k_i] * g_i * omega(i,s,t) * x[i,r,s]`。

总 IT：

`P_IT[r,t](x) = NonAI_IT_Load[r,t] + P_AI[r,t](x)`。

设施侧负荷：

`L[r,t](x) = PUE[r] * P_IT[r,t](x)`。

基准设施负荷：

`L0[r,t] = PUE[r] * (NonAI_IT_Load[r,t] + Baseline_AI_IT_Load[r,t])`。

定义任务调度引起的设施负荷增量：

`DeltaL[r,t] = L[r,t](x) - L0[r,t]`。

该量是 Q2 从“算”进入“电”的唯一负荷增量接口。

---

## 4. Q2 能源层边界

附件统一平衡式为：

`GridPurchase + AvailableRenewable + DischargePower = Total_Load + ChargePower + GridSell + Curtailment`。

但 Q2 的显式决策只有任务迁移与开工时段；`storage_information.xlsx` 由附件表格指向 Q3/Q4。因此 Q2 不重新优化储能和能源市场运行。

为避免把 Q3/Q4 的自由度提前引入 Q2，采用**基准状态中心化的边际能源核算**：

- `GridCharge0, RenewableCharge0, DischargePower0, GridSell0` 保持基准值；
- 任务调度只改变设施负荷；
- 负荷增加时先利用基准 `Curtailment0`，其余增加供负荷购电；
- 负荷降低时先减少基准供负荷购电，其余形成新增弃电；
- 这是一条固定核算规则，不是额外能源优化决策。

定义基准供负荷购电：

`G0[r,t] = max(GridPurchase0[r,t] - GridCharge0[r,t], 0)`。

定义基准直接新能源：

`U0[r,t] = UsedRenewable0[r,t]`，

基准弃电：

`C0[r,t] = Curtailment0[r,t]`。

---

## 5. 基准状态中心化边际能量平衡

令

`dplus[r,t] = max(DeltaL[r,t], 0)`，

`dminus[r,t] = max(-DeltaL[r,t], 0)`。

### 5.1 负荷增加：先吸收弃电，再新增购电

可由原弃电吸收的增量：

`Aplus[r,t] = min(dplus[r,t], C0[r,t])`。

超过弃电余量的新增电网供负荷功率：

`Bplus[r,t] = dplus[r,t] - Aplus[r,t]`。

### 5.2 负荷降低：先减少供负荷购电，再增加弃电

可直接削减的基准供负荷购电：

`Bminus[r,t] = min(dminus[r,t], G0[r,t])`。

剩余负荷下降量：

`Aminus[r,t] = dminus[r,t] - Bminus[r,t]`。

其物理含义为直接新能源消纳减少、弃电增加。

实现时必须检查：

`Aminus[r,t] <= U0[r,t] + tolerance`。

若出现违反，不允许静默截断；说明“固定基准储能/市场背景”的 Q2 口径在该 region-hour 已失效，需要建模手重新审查，而不是自动修改储能策略。

### 5.3 更新后的能源量

供负荷购电：

`G[r,t] = G0[r,t] + Bplus[r,t] - Bminus[r,t]`。

总购电：

`GridPurchase[r,t] = GridCharge0[r,t] + G[r,t]`。

直接新能源消纳：

`UsedRenewable[r,t] = U0[r,t] + Aplus[r,t] - Aminus[r,t]`。

弃电：

`Curtailment[r,t] = C0[r,t] - Aplus[r,t] + Aminus[r,t]`。

保持：

- `RenewableCharge = RenewableCharge0`；
- `GridCharge = GridCharge0`；
- `DischargePower = DischargePower0`；
- `GridSell = GridSell0`。

若基准数据满足附件统一能量平衡，则上述更新在每个 `(r,t)` 上保持能量守恒，并在 `DeltaL=0` 时精确回到附件基准状态。

---

## 6. 成本、碳与新能源利用率

绝对运行成本按附件口径：

`Cost = sum_{r,t} [ GridPurchase[r,t] * Price[r,t] - GridSell0[r,t] * SellPrice[r,t] ]`。

绝对碳排：

`Carbon = sum_{r,t} GridPurchase[r,t] * CarbonIntensity[r,t]`。

由于 `GridCharge0` 与 `GridSell0` 在 Q2 中固定，对任务调度方案的比较等价于比较其供负荷购电 `G[r,t]` 的边际成本/碳：

`DeltaCost_sched = sum_{r,t} (Bplus-Bminus) * Price[r,t]`，

`DeltaCarbon_sched = sum_{r,t} (Bplus-Bminus) * CarbonIntensity[r,t]`。

新能源利用率按附件统一定义：

`eta_R = sum(UsedRenewable + RenewableCharge0 + GridSell0) / sum(AvailableRenewable)`。

所以 Q2 中调度对新能源利用率的影响只来自直接消纳变化：

`Delta RenewableUse = sum(Aplus - Aminus)`。

这给出一条可解释关系：

`任务时空迁移 -> Facility Load 增量 -> 吸收/释放基准弃电 -> 供负荷购电变化 -> Cost/Carbon/Renewable Utilization`。

---

## 7. 资源与 SLA 硬约束

所有任务必须满足：

- 每个任务恰好选择一个 `(r,s)`；
- NonPreemptive、不可拆分、运行中不可迁移；
- GPU 容量；
- Max IT power；
- Max Facility power；
- `NetworkLatency[o_i,r] <= MaxLatency_i`；
- EarliestStart / LatestFinish；
- `finish_i <= 2406`；
- 2406 无计算任务占用。

主运行时域 0--2399；2400--2405 仅结清此前任务，并计入对应任务引起的能源、成本和碳变化。

---

## 8. 目标组织：当前不做主观加权

题面把运行成本、碳排放、网络时延和新能源利用率写为“目标或评价指标”，因此当前不构造

`w1*Cost + w2*Carbon + w3*Latency - w4*RenewableUtilization`。

当前建议：

1. Latency 首先作为 SLA 硬约束，同时报告平均/分位时延和迁移率；
2. Renewable utilization 由统一公式报告，并额外报告 `Delta Curtailment` / 新增弃电消纳；
3. Cost 与 Carbon 先做两个极值/冲突探针；
4. 若两者在正确的边际核算口径下基本同向，则采用单主目标 + 另一指标评价；
5. 若存在实质 Pareto 冲突，再采用 epsilon-constraint，而不是主观权重。

这一部分在极值探针完成前保持 `NEEDS_REVIEW`。

---

## 9. SFETA 在模型中的位置

SFETA（Spatio-temporal Flexibility and Energy-aware Task Assignment）只负责求解上述大规模组合调度模型。

数据已经给出约 `2.33e8` 个完整合法 `(task,region,start)` 候选，因此不直接展开巨大 MILP，也不人为截断合法域。

### 9.1 任务顺序

优先采用无权重字典序：

1. `|R_i|` 小者先；
2. slack / `|T_i|` 小者先；
3. 必要时 `GPU-hour = g_i*p_i` 大者先。

这是由本题 RT / Batch / Training 的实际时空柔性差异驱动的 least-flexible-first 规则。

### 9.2 候选位置评价

候选 `(r,s)` 不按原始 `Price`、`CarbonIntensity` 或 E/F 区域标签直接打分，而计算**该任务置入当前状态后的边际能源后果**：

- 能吸收多少剩余 Curtailment；
- 新增多少供负荷购电；
- `DeltaCost_i,r,s`；
- `DeltaCarbon_i,r,s`；
- 当前资源可行性与 SLA。

这使 SFETA 的 energy-aware / carbon-aware 信息由能量守恒直接产生，而不是人为权重。

### 9.3 当前不加入的复杂机制

- LSTM / 强化学习；
- PSO/GA 等黑箱元启发式；
- 储能控制；
- 线路潮流；
- 带宽、迁移数据量、迁移能耗/费用；
- 人为 top-K / 最大等待窗口。

---

## 10. 必须实现的审计门禁

程序手在正式 Q2 求解前至少检查：

1. `DeltaL=0` 时所有能源结果精确复现附件基准；
2. 每个 `(r,t)` 更新后满足附件统一能量平衡；
3. `GridPurchase >= 0, UsedRenewable >= 0, Curtailment >= 0`；
4. `Aminus <= U0`，若失败立即报错；
5. 所有任务级 GPU/IT/Facility/SLA/deadline 约束零违规；
6. 2406 无任务占用；
7. Cost/Carbon/eta_R 均按附件统一公式重算；
8. 不从 `storage_information.xlsx` 引入 Q2 额外决策自由度。

---

## 11. 当前判断

当前最适合本题 Q2 的模型结构不是“任务调度 + 完整能源系统重新优化”，而是：

**碳感知多区域时空资源约束任务调度 + 基准状态中心化边际能源核算。**

其优点：

- 与题面“任务迁移与开工时段为决策变量”严格对应；
- `DeltaL=0` 精确回到附件基准；
- 保留附件中 Curtailment / GridPurchase 的真实基准结构，不因自由重分配新能源导致零购电/零碳退化；
- 不提前侵入 Q3/Q4 的储能与能源调度自由度；
- Cost、Carbon、Renewable Utilization 均由同一能量平衡链得到，便于解释与审计。
