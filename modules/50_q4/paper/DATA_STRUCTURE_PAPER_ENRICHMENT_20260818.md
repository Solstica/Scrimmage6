# Q4 数据结构驱动论文强化要求（2026-08-18）

## 0. 目的

Q4 当前最容易出现的论文风险，是把联合优化写成一篇“Benders+CG 求解器论文”，而弱化题目真正有价值的数据结构。算法仍然重要，但正文主故事必须重新拉回：

`任务异构性 + 区域算力差异 + 网络服务约束 + PUE/价格/碳 + BESS/SellLimit -> 计算柔性与能源柔性争用同一时空新能源 -> 必须联合优化`。

本轮不改联合模型，不增加权重，不新增算法模块；只强化 Data-to-Coupling-to-Model 的逻辑和图证据。

---

## 1. 必须进入正文前半部的数据关系

### R1 三类任务不是“任务数三等分”，而是柔性与能耗高度异构

数据：
- AITraining 约 1/3 任务，却贡献约 80.14% GPU-hour、约 87.12% AI IT 能量；
- RT 时间刚性，空间合法域约 1--3 区；
- Batch 时间可延迟、主要 5--6 区合法；
- Training 全 6 区可行、时间余量大。

**联合模型作用：**说明 workload placement 对能源层的影响主要由少量“高能耗高柔性”Training 驱动，同时必须优先保护 RT 的服务约束。

### R2 区域优势不是单一维度

数据：
- RegionD AvailableGPU 最大（1472）；
- D/E/F PUE 低于 A/B/C；
- D/E/F BESS 容量/充放电功率/售电能力更强；
- A/B/C 更接近用户侧、RT 网络可达性更好；
- A/B/C SellLimit=0，D/E/F 允许新能源外送。

**联合模型作用：**不存在一个“最好区域”。低时延服务优势、算力优势、设施能效优势、储能/售电优势落在不同区域，必须联合考虑。

### R3 题面角色标签与数值数据存在反直觉差异

附件文字把 E/F 描述为新能源富集区，但数值上六区域 `AvailableRenewable_MW` 逐小时完全相同。

**论文作用：**必须明确：Q4 不根据文字标签硬编码 E/F 绿色优势；真实区域能源差异来自 `PUE + workload + Price/Carbon + BESS/SellLimit + 动态 Curtailment`。

这是全篇非常能体现“真正读数据”的发现，必须进入正文和图。

### R4 Cost 与 Carbon 不是人为制造的冲突轴

同一区域逐时 Price 与 CarbonIntensity 约中等负相关（约 -0.38）；区域倍率结构又不同。

**联合模型作用：**Cost/Carbon 存在真实但非绝对冲突，因此采用 Cost 主层、Carbon 场景/epsilon-constraint，而不是六指标权重和。

### R5 Q2 的计算柔性与 Q3 的储能柔性会争用同一份新能源

动态盈余：

`H[r,t](x)=AvailableRenewable[r,t]-FacilityLoad[r,t](x)`。

同一 1 MWh 绿色余量既可：
1. 由迁入的 Batch/Training 当期消纳；
2. 由 BESS 充入后跨时段释放。

**联合模型作用：**这就是 Q4 不能“先做 Q2 排程、再调用 Q3”的核心原因。

### R6 小规模真实探针已证明顺序优化会产生虚假能源机会

Probe 1：3 个真实 RT、8 个 E/F 组合中，冻结储能的 Q2 静态核算认为迁到 F 可省约 3613.67 CNY；对每个组合重新优化 BESS 后，8 个组合最终能源成本相同，而留在 E 的网络时延更低。

**论文作用：**这是一条非常强的“联合优化必要性”证据，应进入 Q4 模型分析，而不是埋在代码审计文件。

### R7 Energy LP dual 是有用但局部的价值信号

真实 Training TaskID 1 的 6 点诊断中，dual 一阶估计与真实 recourse 排序 Pearson≈0.985、Spearman≈0.898，但大任务跨 active-set breakpoint 时会低估；朴素 iterative dual 还出现 A->B->A 两周期。

**算法作用：**解释为什么不能只用最新 shadow price 做贪心重排，必须累积 Benders cuts；这是“数据/数值行为驱动算法升级”的证据。

### R8 数据结构还能直接减少计算量

附件严格满足 `MaxFacility=PUE*MaxIT`，且 `FacilityLoad=PUE*ITLoad`，Facility capacity row 与 IT row 重复；Energy dual support 高度稀疏；完整合法域约 2.33375201e8 placements。

**算法作用：**Exact dominance、sparse cuts、exact pricing 都是数据结构的计算利用，而不是算法堆叠。

---

## 2. Q4 正文必须重新建立的“必要性链”

在 Benders/CG 之前必须有一节或一段明确写出：

1. 任务柔性异构；
2. 区域资源/能效/网络/储能优势错位；
3. 原始新能源出力六区并无空间差异；
4. workload 改变后，Q3 的盈余、弃电、购电、SOC机会全部变成 `x` 的函数；
5. 顺序 Q2->Q3 探针确实会给出错误的迁移价值；
6. 因此需要 joint workload-energy-storage scheduling。

只有这六步完成后，再进入“如何算”：Benders + CG。

---

## 3. 必补主图

### 主图 Q4-A：六区域算力—网络—能源—储能结构矩阵（P0）

不做综合评分、不做熵权/AHP。

建议行=Region A--F，列至少包括：
- AvailableGPU；
- PUE；
- RT/典型来源的合法可达性或平均低时延可达指标；
- StorageCapacity；
- MaxCharge/Discharge；
- SellLimit；
- Price/Carbon 的代表性统计；
- baseline Curtailment 或其他真实动态能源机会统计。

可标准化仅用于同图展示，但图注必须同时给原始单位/含义。

目的：让读者直接看到“低时延、算力、能效、储能、售电优势不在同一区域”。

### 主图 Q4-B：顺序优化失真 Probe（P0）

用 3-task/8-combination Probe 做小图或表图：
- 横轴=8 个合法 E/F placement 组合；
- 一组=Q2 冻结储能静态边际成本；
- 一组=重新优化 BESS 后真实 Energy recourse；
- 旁边标网络 latency。

目的：直接证明 `Q2 static marginal != Q4 post-BESS recourse`，这是 Q4 联合模型必要性的最有力证据。

### 主图 Q4-C：计算柔性与储能柔性争用同一绿色余量的机制示意（P0）

这是机制图，不需要再生复杂数据：

`AvailableRenewable -> 当期迁入任务消纳`
与
`AvailableRenewable -> BESS charge -> later discharge`

两路共享同一 `H[r,t](x)`。

目的：解释为什么 workload 和 BESS 不能顺序固定。

### 主图 Q4-D：40-task exact benchmark 算法验证（P1）

简洁呈现：
- 3139 explicit placements；
- exact joint vs Benders/CG cost 一致；
- Cost-only 服务退化 vs Cost->Wait->Latency 代表解。

不要把 benchmark 做成主流程图的大块，它是算法可信度证据。

### 主图 Q4-E：50k 求解闭合图（最终结果后，P1）

只在最终结果完成后画：
- active columns / pricing rounds / Benders violation；
- 区分 LP closure、restricted integer feasible endpoint、是否有 integrality gap；
- 不用“全局最优”字样，除非真的有 certificate。

### 主图 Q4-F：Q2-only / Q3-only / Q4-joint 统一口径对比（最终结果后，P0）

这是 Q4 最终最重要的结果图之一。

在统一 accounting 下比较：
- Cost；
- Carbon；
- Wait/QoS；
- Latency；
- RenewableUtilization；
- regional PeakNetImport（可拆成表或标准化相对改善图）。

目的：量化“联合优化比两个独立优化到底多得到什么”。

### 主图 Q4-G：正式场景对比（最终结果后，P0）

题面要求不同：
- Carbon constraints；
- electricity-price mechanisms；
- renewable fluctuation scenarios。

正式场景协议冻结后再画，不用现有 `gamma=1.4` 诊断 probe 冒充正式场景。

---

## 4. Q4 正文需要降权的内容

以下内容保留，但不应压过数据主线：
- Exact Dominance Presolve；
- Sparse Benders Cuts；
- memory compression；
- 每轮 cut 数/列数细节；
- 过多 solver 迭代日志。

建议把它们统一放在“可计算性与算法验证”小节，而不是模型分析主段。

---

## 5. 写作验收

读者在看到 Benders 一词前，必须已经能回答：
1. 为什么 Q2 和 Q3 不能顺序拼接；
2. 为什么不存在一个天然最优 Region；
3. 为什么题面 E/F 新能源标签不能直接变成绿色评分；
4. 为什么 Cost 与 Carbon 不做人工权重和；
5. 为什么联合模型必须同时包含 task placement 与 BESS/Grid variables。

如果 Q4 的“创新”读起来只剩 Benders+CG，而上述数据关系看不见，本轮不算通过。
