# Q2 建模优化文献说明

状态：`DRAFT / NEEDS_REVIEW`

本文件只记录近十年文献中**能够优化 Q2 建模表达、目标组织或 SFETA 规则，而不要求大改现有结构**的内容。题面与附件的变量定义、统一能量平衡、碳排公式和新能源利用率口径始终优先于外部文献。

## 0. 术语结论先行

当前推荐把 Q2 主模型写成：

**碳感知时空工作负载调度（Carbon-Aware Spatiotemporal Workload Scheduling）**。

该说法有 EuroSys 2024 等直接文献依据。针对本题再说明：

- 使用 `spatiotemporal workload flexibility`；
- 满足 `resource/capacity constraints`；
- 通过 workload shifting / migration 实现 `renewable curtailment mitigation`；
- 使用 time-indexed formulation 表达离散开工位置；
- SFETA 候选位置评价吸收 `marginal resource allocation` 思想。

此前“任务时空柔性—弃电消纳耦合的碳感知资源约束调度模型”只保留为中文机制性描述，不再宣称为已有标准模型专名。

`SFETA` 是本文自定义算法名；`least-flexible-first` 也不作为标准算法名使用。

---

## 1. Yang et al. — REPTA, Applied Energy 2026

文献：Yang L, Shahidehpour M, Chen X, Wang C, Fang X, Yang Q. *High-speed REPTA algorithm for performance cost optimization in data centers considering workload delay tolerances*. Applied Energy, 404, 127156.

### 支持
- delay-sensitive / delay-tolerant workload 应显式区分；
- delay tolerance 会使任务时间维度的组合变量迅速膨胀；
- 可把完整优化模型与快速任务分配算法分开；
- 利用 RES 与价格状态做任务时空迁移，而不是把所有指标压成一个静态评分。

### 本题吸收
- Q2 模型与 SFETA 分离；
- 保留 non-iterative / domain-driven task assignment 思路；
- 用任务时空可行域和边际能源后果驱动 SFETA。

### 不直接照搬
- REPTA 的 local RES -> remote RES -> lowest price 规则依赖跨区 RES 差异；本题 `AvailableRenewable_MW` 六区域逐时相同，不能照搬。
- REPTA 的完整 electricity-heat / BESS 模型不进入 Q2。

---

## 2. Sukprasert et al. — EuroSys 2024

文献：Sukprasert T, Souza A, Bashir N, Irwin D, Shenoy P. *On the Limitations of Carbon-Aware Temporal and Spatial Workload Shifting in the Cloud*. EuroSys 2024, 924--941. DOI: 10.1145/3627703.3650079.

### 直接确认的科研术语
- carbon-aware temporal and spatial workload shifting；
- spatiotemporal workload scheduling；
- temporal / spatial workload flexibility 及其受 job duration、deadline、SLO、capacity 等限制的思想。

### 本题吸收
- 正式模型名称改用 `Carbon-Aware Spatiotemporal Workload Scheduling`；
- RT / Batch / Training 的 duration、deadline/SLA、空间可迁移域成为模型结构变量；
- 简单调度策略可能已获得多数收益，因此不因 2.33e8 候选就自动引入复杂元启发式。

### 不直接照搬
- 文献自己的碳强度数据和 workload trace 不替代本题附件数据。

---

## 3. Zare Ghaleh Seyyedi et al. — RSER 2024

文献：Zare Ghaleh Seyyedi A, Akbari E, Mahmoudi Rashid S, Nejati S A, Gitizadeh M. *Application of robust optimized spatiotemporal load management of data centers for renewable curtailment mitigation*. Renewable and Sustainable Energy Reviews, 2024, 204:114793. DOI: 10.1016/j.rser.2024.114793.

### 直接确认的科研术语
- spatiotemporal flexibility；
- spatiotemporal load management；
- renewable curtailment mitigation。

### 本题吸收
- “任务时空柔性”有正式英文对应 `spatiotemporal workload/load flexibility`；
- “弃电消纳”正式论文建议写 `renewable curtailment mitigation`，而不是自造 `curtailment absorption coupling`；
- 数据中心通过时间移动和空间迁移成为新能源消纳的可调负荷，这与本题的 Batch/Training 调度机制一致。

### 不直接照搬
- 该文包含配电网、线路等电力系统结构；本题 Q2 不要求线路潮流，因此只吸收术语与柔性/弃电关系。

---

## 4. Zheng, Chien & Suh — Joule 2020

文献：Zheng J, Chien A A, Suh S. *Mitigating Curtailment and Carbon Emissions through Load Migration between Data Centers*. Joule, 2020. DOI: 10.1016/j.joule.2020.08.001.

### 支持
- `load migration` / workload migration 是数据中心跨区域调度的成熟表述；
- 把可迁移负荷放到新能源过剩时段/区域，可以同时降低 renewable curtailment 与 GHG emissions。

### 本题吸收
- 用 workload migration 解释跨 Region 的任务调度；
- 用 renewable curtailment mitigation 解释 `Curtailment0` 被新增计算负荷吸收的物理机制。

### 不直接照搬
- 该文的电网区域与历史数据不用于本题数值；本题仍按附件统一 CarbonEmission 公式。

---

## 5. Hanafy et al. — CarbonScaler, POMACS 2023

文献：Hanafy W A, Liang Q, Bashir N, Irwin D, Shenoy P. *CarbonScaler: Leveraging Cloud Workload Elasticity for Optimizing Carbon-Efficiency*. Proceedings of the ACM on Measurement and Analysis of Computing Systems, 2023, 7(3), Article 57. DOI: 10.1145/3626788.

### 支持
- carbon-aware scheduling 可以采用经典 `marginal resource allocation` 思想；
- 调度时评价新增资源分配带来的边际碳后果，比给站点一个静态“绿色得分”更贴合资源分配问题。

### 本题吸收
- SFETA 不直接按 Price、CarbonIntensity、Region 标签静态排序；
- 对任务候选 `(r,s)` 计算 `DeltaGridPurchase / DeltaCost / DeltaCarbon / DeltaCurtailment`；
- 候选优劣由能量平衡产生的边际量决定。

### 不直接照搬
- CarbonScaler 允许弹性改变任务资源规模；本题 GPU_Demand 固定、任务不可拆分不可抢占，因此不使用动态 scaling。

---

## 6. Xu et al. — GREEN, NSDI 2025

文献：Xu K, Sun D, Tian H, Zhang J, Chen K. *GREEN: Carbon-efficient Resource Scheduling for Machine Learning Clusters*. NSDI 2025, 999--1014.

### 支持
- carbon-aware scheduling / carbon-efficient resource scheduling 是系统领域正式用语；
- ML jobs 的 temporal flexibility 可用于低碳时段调度；
- 碳效率必须与容量、完成时间等系统约束一起处理。

### 本题吸收
- CarbonIntensity 必须真正进入候选选择或碳约束，不能仅事后核算；
- SLA、deadline、GPU/IT/Facility 继续作为硬约束；
- Q2 已给实际逐时能源参数，不额外增加预测层。

---

## 7. Choudhury et al. — MAST, OSDI 2024

文献：Choudhury A, Wang Y, Pelkonen T, et al. *MAST: Global Scheduling of ML Training across Geo-Distributed Datacenters at Hyperscale*. OSDI 2024, 563--580.

### 支持
- `geo-distributed datacenter scheduling` / `global scheduling of ML training` 属于成熟系统问题表述；
- 大规模 ML workload 的跨区域 placement 受到 regional capacity 等约束。

### 本题吸收
- “地理分布式数据中心任务调度”是可用的领域定位；
- 资源容量约束不是额外造出的机制，而是 geo-distributed scheduling 的基本现实边界。

---

## 8. Hanafy et al. — ASPLOS 2024

文献：Hanafy W A, Liang Q, Bashir N, Souza A, Irwin D, Shenoy P. *Going Green for Less Green: Optimizing the Cost of Reducing Cloud Carbon Emissions*. ASPLOS 2024, 479--496. DOI: 10.1145/3620666.3651374.

### 支持
- 降碳与经济成本的关系应被实证量化，不应先验假定完全冲突或完全一致。

### 本题吸收
- Q2 先做 Cost-only 与 Carbon-only 极值/近极值探针；
- 数据若显示两者基本同向，不强行制造多目标 Pareto。

---

## 9. Tamby & Vanderpooten — INFORMS Journal on Computing 2021

文献：Tamby S, Vanderpooten D. *Enumeration of the Nondominated Set of Multiobjective Discrete Optimization Problems*. INFORMS Journal on Computing, 2021, 33(1):72--85. DOI: 10.1287/ijoc.2020.0953.

### 支持
- epsilon-constraint 是离散多目标优化中不依赖主观权重的成熟方法。

### 本题吸收
- 只在 Cost 与 Carbon 极值探针确认存在实质冲突后采用 epsilon-constraint；
- 不用 AHP/TOPSIS 或跨物理量人工加权和代替调度模型。

---

## 10. Artigues — Operations Research Letters 2017

文献：Artigues C. *On the strength of time-indexed formulations for the resource-constrained project scheduling problem*. Operations Research Letters, 2017, 45(2):154--159. DOI: 10.1016/j.orl.2017.02.001.

### 支持
- `time-indexed formulation` 是成熟离散调度建模术语；
- resource-constrained scheduling 是成熟问题族。

### 本题边界
- 本题可用 `x[i,r,s]` 的 time-indexed formulation；
- 但本题没有活动 precedence graph，不直接把 Q2 命名成 RCPSP。

---

## 11. 当前自定义词处理

### SFETA

- **不是**标准文献算法名；
- 若保留，必须明确“本文构造/改进的 SFETA heuristic”；
- 其算法家族写作 `priority-rule-based constructive task assignment/scheduling heuristic`。

### least-flexible-first

- 不再声称是标准算法名；
- 正式写作“基于空间可行域大小和 slack 的 priority rule”；
- slack 可联系 scheduling literature 中的 minimum-slack priority 思想；`|R_i|` 是本题特化规则。

### 基准状态中心化边际能源核算

- 不作为文献术语；
- 改写为“基准状态增量能量平衡”，并明确属于本题为隔离 Q2 与 Q3 决策自由度设计的核算假设。

### 弃电消纳耦合

- 中文机制解释可以保留；
- 英文正式术语优先 `renewable curtailment mitigation`；
- 不造 `curtailment absorption coupling` 之类缩写。

---

## 12. 当前文献审查后的 Q2 改进结论

不更换 Q2 主结构，也不更换 SFETA 的本文算法定位。正式改进为：

1. **术语文献化**：主模型写 `Carbon-Aware Spatiotemporal Workload Scheduling`；
2. **柔性显式化**：使用 spatial feasible set、temporal slack、GPU-hour，不制造抽象柔性总分；
3. **弃电机制文献化**：使用 `renewable curtailment mitigation`，并保持 AvailableRenewable 是原始输入；
4. **边际化**：候选使用 `DeltaGridPurchase / DeltaCost / DeltaCarbon / DeltaCurtailment`；
5. **目标先诊断再组织**：先测 Cost--Carbon 冲突，再决定单目标+评价或 epsilon-constraint；
6. **复杂度克制**：不引入 RL、PSO、GA、MPC、DRO 等与当前确定数据和 Q2 边界不匹配的复杂机制。

## 13. 引用边界

- 本题 CarbonEmission 必须继续使用附件指定的 `GridPurchase * CarbonIntensity * Delta t`；即使外部研究讨论 average/marginal carbon intensity，也不能更换官方口径。
- 本题新能源利用率继续使用附件指定公式。
- 外部文献只支撑术语、建模原则与算法思想，不能替代附件数据实证结果，如“六区 AvailableRenewable 相同”“Curtailment 与 CI 负相关”等。
