# Q4 数据结构与算—储—电耦合审计

状态：`DRAFT / NEEDS_REVIEW`

## 1. 题目要求与建模边界

Q4 要在前三问基础上联合考虑：任务迁移、开工时段、电价、碳排放、可用新能源、储能、区域购售电边界、网络时延和任务异构性，并在系统运行成本、碳排放、网络时延、服务质量、新能源利用率和区域峰值净购电之间权衡；同时比较不同碳约束、电价机制和新能源波动场景。

官方说明继续适用：

- 0--2399 h 有新任务到达；2400--2405 h 只结清已到达任务；2406 h 禁止计算任务占用，只做电力/储能终端结算；
- 所有任务必须满足 GPU/IT/Facility、Latency、LatestFinish 和 `finish<=2406`；
- `SOC(2406)>=InitialSOC`；
- Q4 不建立线路潮流、网络带宽、迁移数据量、迁移传输能耗/费用；
- Q4 的 AI IT 必须由 workload + overlap + power_mapping 重新计算，不能把 baseline AI IT 当作优化后负荷。

## 2. 附件数据结构

### 2.1 任务异构性

50,000 个任务在任务数上近似三等分，但 GPU-hour/AI 能耗高度不均衡：

- AITraining：约 1/3 任务，约 80.14% GPU-hour、约 87.12% AI IT 能量；
- BatchInference：约 15.32% GPU-hour；
- RealTimeInference：约 4.54% GPU-hour。

时空柔性也不同：

- RT：时间刚性，空间合法域约 1--3 区；
- Batch：时间可延迟，空间合法域主要 5--6 区；
- Training：全部 6 区可行，时间余量最大，同时承担绝大多数计算工作量。

因此 Q4 不能只按任务数组织调度，继续保留 `|R_i|`、Slack、GPU-hour 三个维度。

### 2.2 区域资源结构

- RegionD 的 AvailableGPU 最大（1472）；
- PUE：D/E/F 低于 A/B/C；
- D/E/F 的 BESS 充放电功率、容量和售电能力显著更大；
- A/B/C 的 SellLimit=0，D/E/F 允许新能源外送。

附件文字把 A/B/C 定义为东部用户侧高负荷区、D 为西部算力中心、E/F 为新能源区。但数值上六区域 `AvailableRenewable_MW` 逐小时完全相同，因此 Q4 不能硬编码“E/F 当前新能源更多”。区域能源差异主要来自 PUE、价格、碳强度、储能和售电边界。

### 2.3 电价与碳结构

区域价格与碳强度的时间形状高度一致、主要呈区域倍率差异；但同一区域逐时 `Price` 与 `CarbonIntensity` 约为中等负相关（约 -0.38）。因此成本与碳不是完全同向目标，Q4 的 Cost--Carbon 权衡有数据依据，不需要人为制造冲突。

### 2.4 新能源与基准能源状态

附件存在大量 `Curtailment>0` 与供负荷 GridPurchase 同时出现的 region-hour。Q2 释放计算侧时空柔性可吸收部分弃电；Q3 释放 BESS 时间柔性也可回收弃电。Q4 中两类柔性会争用同一份时空新能源余量。

## 3. Q4 新出现的耦合

给定任务调度 `x`：

`AI_IT[r,t](x) -> FacilityLoad[r,t](x)`。

定义动态新能源盈余：

`H[r,t](x) = AvailableRenewable[r,t] - FacilityLoad[r,t](x)`。

Q3 中固定负荷下的弃电源、购电缺口和剩余出口能力在 Q4 中都变成 `x` 的函数。因此 Q4 不能把 Q3 的 `C0/D0/X0` 原样当固定输入，也不能继续把 Q2 的 baseline Curtailment 当成静态绿色得分。

同一 1 MWh 新能源余量可以：

1. 被迁入的 Batch/Training 当期消纳；
2. 被 BESS 充入后跨时段释放。

所以计算柔性和储能柔性既互补又竞争。

## 4. 完整联合参考模型

任务变量：`x[i,r,s] in {0,1}`。

能源变量：`u,qR,qG,d,gL,s,w,E`。

核心链：

`x -> AI IT -> Facility Load -> Renewable/Grid/BESS recourse`。

完整模型同时满足：

- 每任务恰好一个合法 `(r,s)`；
- GPU-hour、IT、Facility；
- SLA/Latency、LatestFinish、2406 边界；
- Renewable balance；
- Load balance；
- BESS SOC dynamics / charge / discharge；
- Grid import/export / SellLimit；
- terminal SOC。

该联合 MILP 用于定义 exact benchmark，不主张直接对约 2.33e8 个全域候选做一次性全规模 MILP。

## 5. Probe 1--2 已确认的事实

### Probe 1：顺序 Q2->Q3 会产生虚假能源机会

3 个真实 RT 任务、每个只有 E/F 两个合法区域，共 8 个组合。冻结储能的 Q2 会认为全部迁到 F 可节约约 3613.67 CNY；但对每个组合重新优化 BESS 后，8 个组合最终能源成本相同。此时全部留在 E 的网络时延明显更低。

结论：`Q2 static marginal value != Q4 post-BESS recourse value`。

### Probe 2：Energy LP dual 是有效的任务候选价值信号

对真实 Training TaskID 1 在 RegionE 的多个合法 StartHour 比较：Q2 静态核算几乎给出相同能源价值，而重新求完整 BESS LP 后的真实成本变化从约 20.8k CNY 降到 0；Energy LP load-balance dual 的一阶估计与真实 recourse 的排序高度一致（该 6 点诊断 Pearson 约 0.985，Spearman 约 0.898）。

但大任务跨越 active-set breakpoint 时 dual 会低估真实变化，因此 dual 只能指导搜索，不能永久替代 recourse LP。

### Probe 2B：24/40 任务 exact benchmark

40 个真实任务（16 Training + 14 Batch + 10 RT，3139 个完整合法候选）上：

- Sequential：能源 gap 约 0.373%，但 36/40 任务迁移、平均等待约 7.6 h；
- One-shot dual：能源 gap 约 0.126%，迁移/等待大幅收敛；
- 朴素 iterative dual 会经过 exact energy optimum，但出现 `A->B->A` 两周期振荡。

说明只保留最新 dual 的全量重排不保证收敛；需要真实 recourse acceptance 或保留历史 dual 信息。

## 6. 当前模型方向

能源子问题在给定任务负荷后是连续 LP，记其最优值函数为：

`Q(L) = min_y EnergyCost(L,y)`。

负荷平衡约束的 dual/shadow price `lambda[r,t]` 是 `Q(L)` 对局部负荷的次梯度。任务候选造成的设施负荷变化 `deltaL[i,r,s,t]` 可用：

`sum_t lambda[r,t] * deltaL[i,r,s,t]`

作为局部 recourse 一阶估计。

Probe 2 的振荡说明历史边际信息不能每轮丢弃。对第 k 次已评估负荷 `L^k`，LP 对偶给出 Benders 支持超平面：

`Q(L) >= Q(L^k) + lambda^k · (L-L^k)`。

因此正式 Q4 优先研究：

- exact joint MILP：小规模 benchmark；
- Benders master：任务时空决策；
- LP subproblem：新能源/BESS/Grid recourse；
- single-cut / region multi-cut；
- Cost 最优后再做 QoS/Latency 字典序或 epsilon-constraint 精化。

`Benders` 只有在真实实现 master + dual cut 累积后才使用该名称；仅用最新 dual 重新排序任务时应称 `dual-guided coordination heuristic`。
