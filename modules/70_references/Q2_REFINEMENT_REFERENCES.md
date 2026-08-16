# Q2 建模优化文献说明

状态：`DRAFT / NEEDS_REVIEW`

本文件只记录近十年文献中**能够优化 Q2 建模表达、目标组织或 SFETA 规则，而不要求大改现有结构**的内容。题面与附件的变量定义、统一能量平衡、碳排公式和新能源利用率口径始终优先于外部文献。

## 1. Yang et al. — REPTA, Applied Energy 2026

文献：Yang L, Shahidehpour M, Chen X, Wang C, Fang X, Yang Q. *High-speed REPTA algorithm for performance cost optimization in data centers considering workload delay tolerances*. Applied Energy, 404, 127156.

### 支持
- delay-sensitive / delay-tolerant workload 应显式区分；
- delay tolerance 会使任务时间维度的组合变量迅速膨胀；
- 可把完整优化模型与快速任务分配算法分开：模型规定可行性与性能，REPTA 负责快速构造任务分配；
- 利用 RES 与价格状态做任务时空迁移，而不是把所有指标压成一个静态评分。

### 本题吸收
- Q2 模型与 SFETA 分离；
- 保留 non-iterative / domain-driven task assignment 思路；
- 用任务时空柔性和边际能源后果驱动 SFETA。

### 不直接照搬
- REPTA 的 local RES -> remote RES -> lowest price 规则依赖跨区 RES 差异；本题 `AvailableRenewable_MW` 六区域逐时相同，因此不能照搬。
- REPTA 的完整 electricity-heat / BESS 模型不进入 Q2。

---

## 2. Sukprasert et al. — EuroSys 2024

文献：Sukprasert T, Souza A, Bashir N, Irwin D, Shenoy P. *On the Limitations of Carbon-Aware Temporal and Spatial Workload Shifting in the Cloud*. EuroSys 2024, 924--941. DOI: 10.1145/3627703.3650079.

### 支持
- carbon-aware workload shifting 的潜力受 job duration、deadline、SLO、时间与空间柔性共同限制；
- 简单调度策略往往已经能获得大部分可实现收益，更复杂的策略未必产生同量级增益；
- 空间迁移收益必须受容量和服务约束限制。

### 本题吸收
- SFETA 的首要结构变量采用 `|R_i|`、slack/`|T_i|` 和任务资源重量，而不是增加复杂学习器；
- RT / Batch / Training 的实际柔性差异直接决定调度顺序；
- 不因为存在 2.33e8 个候选就自动使用复杂元启发式。

### 不直接照搬
- 文献使用其自己的碳强度数据与工作负载设置；不能据此改写本题附件提供的 CarbonIntensity 定义。

---

## 3. Hanafy et al. — CarbonScaler, POMACS 2023 / SIGMETRICS

文献：Hanafy W A, Liang Q, Bashir N, Irwin D, Shenoy P. *CarbonScaler: Leveraging Cloud Workload Elasticity for Optimizing Carbon-Efficiency*. Proceedings of the ACM on Measurement and Analysis of Computing Systems, 2023, 7(3), Article 57. DOI: 10.1145/3626788.

### 支持
- carbon-aware scheduling 可以采用经典 marginal resource allocation 思想；
- 调度时评价新增资源分配带来的**边际碳后果**，比给站点一个静态“绿色得分”更贴合资源分配问题。

### 本题吸收
- SFETA 不直接按 `Price`、`CarbonIntensity`、Region 标签静态排序；
- 对任务候选 `(r,s)` 计算放置后的 `DeltaCost`、`DeltaCarbon`、可吸收 Curtailment、新增 Grid-to-load；
- 候选优劣由能量平衡产生的边际量决定。

### 不直接照搬
- CarbonScaler 允许弹性改变任务资源规模；本题 GPU_Demand 固定、任务不可拆分不可抢占，因此只吸收 marginal allocation 思想，不使用动态 scaling。

---

## 4. Xu et al. — GREEN, NSDI 2025

文献：Xu K, Sun D, Tian H, Zhang J, Chen K. *GREEN: Carbon-efficient Resource Scheduling for Machine Learning Clusters*. NSDI 2025, 999--1014.

### 支持
- 碳强度可以作为 ML 调度器的外部调度信号；
- 时间柔性可以用于把可延迟任务移动到更低碳时段；
- carbon efficiency 不能脱离完成时间与容量约束单独优化。

### 本题吸收
- `CarbonIntensity_{r,t}` 必须真正影响候选选择，不能只在最终结果中核算；
- SLA、deadline、GPU/IT/Facility 继续作为硬约束；
- Q2 已给实际逐时能源参数，不额外增加预测层。

### 不直接照搬
- GREEN 面向 ML cluster 的内部资源调度，本题是多区域数据中心；其集群机制不迁移。

---

## 5. Hanafy et al. — ASPLOS 2024

文献：Hanafy W A, Liang Q, Bashir N, Souza A, Irwin D, Shenoy P. *Going Green for Less Green: Optimizing the Cost of Reducing Cloud Carbon Emissions*. ASPLOS 2024, 479--496. DOI: 10.1145/3620666.3651374.

### 支持
- 降碳与经济成本之间的关系应被显式量化，而不是先验假定完全一致或完全冲突；
- carbon-aware 策略需要讨论“减碳带来的成本代价”。

### 本题吸收
- Q2 先分别做 Cost-only 与 Carbon-only 极值/近极值探针，量化交叉损失；
- 数据若显示两者基本同向，就不强行制造多目标 Pareto；若存在真实冲突，再选择无权重多目标方法。

### 不直接照搬
- 不使用其碳核算口径替换附件统一公式。

---

## 6. Tamby & Vanderpooten — INFORMS Journal on Computing 2021

文献：Tamby S, Vanderpooten D. *Enumeration of the Nondominated Set of Multiobjective Discrete Optimization Problems*. INFORMS Journal on Computing, 2021, 33(1):72--85. DOI: 10.1287/ijoc.2020.0953.

### 支持
- ε-constraint 是离散多目标优化中不依赖主观权重的成熟方法；
- 可以通过一个目标优化、其他目标设约束来生成非支配解。

### 本题吸收
- 只在 Cost 与 Carbon 极值探针确认存在实质冲突后，才考虑 ε-constraint；
- 不采用 AHP/TOPSIS 或不同物理单位的人工加权和。

### 不直接照搬
- Q2 不需要完整枚举所有非支配点；题目只要求建立模型并给出调度策略。完整碳约束场景比较主要留给 Q4。

---

## 7. Miao et al. — ECMR, 2024

文献：Miao Z et al. *Energy and carbon-aware distributed machine learning tasks scheduling scheme for the multi-renewable energy-based edge-cloud continuum*. Science and Technology for Energy Transition, 2024, 79:82. DOI: 10.2516/stet/2024076.

### 支持
- 调度器可以先识别能源状态，再检查计算资源和时延约束；
- 当 RES 匹配不可行时需要有资源可行性 fallback，而不是让任务失败；
- price / carbon / RES / SLA 可以共同作为分布式任务调度信息。

### 本题吸收
- SFETA 采用“能源状态 -> 边际后果 -> 资源/SLA 可行性”的结构化判断；
- 不构造一个混合 Price/Carbon/RES/Latency 的主观总分。

### 不直接照搬
- ECMR 假定多 RES 存在真实地理互补；本题附件实际 `AvailableRenewable` 没有这种空间差异。

---

## 8. 当前文献审查后的 Q2 改进结论

不更换 Q2 主结构，也不更换 SFETA 名义上的算法定位。只做四个建模改进：

1. **边际化**：任务候选使用 `DeltaCost / DeltaCarbon / Curtailment absorbed`，不使用区域静态综合评分；
2. **柔性显式化**：由 `|R_i|`、slack/`|T_i|` 和 GPU-hour 形成 least-flexible-first 字典序；
3. **目标先诊断再组织**：先测 Cost--Carbon 极值冲突，再决定单目标+评价或 ε-constraint；
4. **复杂度克制**：不引入 RL、PSO、GA、MPC、DRO 等与当前确定数据和 Q2 任务边界不匹配的复杂机制。

## 9. 引用边界

- 本题 CarbonEmission 必须继续使用附件指定的 `GridPurchase * CarbonIntensity`；即使外部研究讨论 average/marginal carbon intensity，也不能更换官方口径。
- 本题新能源利用率必须继续使用附件指定公式。
- 外部文献只支撑建模原则与算法思想，不能替代附件数据实证结果，如“六区 AvailableRenewable 相同”“Curtailment 与 CI 负相关”等。
