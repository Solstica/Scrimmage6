# Q2 术语与模型命名审计

状态：`DRAFT / NEEDS_REVIEW`

目的：避免把聊天中的描述性短语包装成已有科研术语。下表区分“文献中已有术语”“可作为描述但不是标准模型专名”“本文自定义算法名”“不建议使用”。

## 0. 最重要的命名结论

经过文献核查，目前**没有找到一个公认、唯一、带固定缩写的模型名称**能够完整等价于本题 Q2 的全部结构（区域迁移 + 开工时段 + GPU/IT/Facility/SLA + 电价/碳强度/新能源 + 弃电缓解）。

最接近、最规范的科研问题族表述是：

- `carbon-aware temporal and spatial workload shifting`；
- `carbon-aware spatiotemporal workload scheduling`；
- `spatio-temporal scheduling model for computing load in data centers`。

因此论文不应再为主模型强造缩写。推荐正式写：

> **碳感知时空工作负载调度模型**（carbon-aware spatiotemporal workload scheduling），并针对本题嵌入资源容量约束与新能源弃电缓解机制。

这里是**文献化问题族/模型类型名称**，不是声称存在一个统一公认的 “CASWS” 等标准缩写。

已有论文确实各自提出过 ESTS、REPTA、GREEN、CarbonScaler、CarbonClipper 等命名算法/系统，但这些是各论文自己的方法名，不能拿来冒充本题模型的标准名称。

---

## 1. 模型主体术语

| 中文候选 | 推荐英文 | 文献状态 | 本题处理 |
|---|---|---|---|
| 碳感知调度 | carbon-aware scheduling / carbon-aware workload scheduling | **标准术语** | 保留。CarbonIntensity 必须进入调度决策，而非仅事后核算 |
| 时空工作负载迁移 | temporal and spatial workload shifting / spatiotemporal workload shifting | **标准术语** | 保留，用于描述跨时段延迟与跨区域迁移 |
| 时空工作负载调度 | spatiotemporal workload scheduling / spatio-temporal scheduling of computing load | **已有高认可文献直接使用同类表述** | 推荐作为 Q2 主模型名称的中心词 |
| 时空柔性 | spatiotemporal flexibility / temporal and spatial flexibility | **已有文献直接使用** | 可用于描述任务的可延迟、可迁移能力 |
| 工作负载迁移 | workload migration / load migration | **标准术语** | 保留，尤其适合解释跨 Region 迁移 |
| 资源约束调度 | resource-constrained scheduling | **成熟运筹术语** | 可作问题属性；本题无 precedence graph，不应直接称 RCPSP |
| 时间索引模型 | time-indexed formulation | **成熟调度建模术语** | 可用于解释 `x[i,r,s]` 形式 |
| 新能源弃电 | renewable curtailment | **标准能源术语** | 保留 |
| 弃电缓解 | renewable curtailment mitigation | **已有文献直接使用** | 推荐替代“弃电消纳耦合”作为更文献化表述 |
| 弃电消纳 | absorbing curtailed renewable energy / reducing curtailment | **物理含义成立，但不是统一标准模型名** | 正文可解释，不宜单独造英文缩写 |
| 边际资源分配 | marginal resource allocation | **成熟优化术语，CarbonScaler 明确采用** | 可用于解释 SFETA 的候选增量评价 |
| 优先规则 | priority rule / dispatching rule | **成熟调度术语** | 用于描述任务处理顺序 |
| 最小松弛时间 | minimum slack / minimum slack time first | **成熟调度规则术语** | 可解释 slack 优先项；本题的空间可行域优先仍是自定义规则 |
| 信号感知调度 | signal-aware scheduling | **系统领域已有术语** | 可解释 price/CI/power availability 是外部信号；不是本题主模型名 |

---

## 2. 直接支持上述术语的文献

### 2.1 与本题结构最接近：Chen et al., Sustainable Computing 2024

Donglin Chen, Yifan Ma, Lei Wang, Mengdi Yao. **Spatio-temporal management of renewable energy consumption, carbon emissions, and cost in data centers.** Sustainable Computing: Informatics and Systems, 2024, 41:100950. DOI: 10.1016/j.suscom.2023.100950.

该文直接提出/使用：

- `spatio-temporal scheduling method for computing power load`；
- `spatio-temporal scheduling model for computing load in data centers`；
- online/offline load 的不同 QoS；
- `temporal flexibility` 和 `spatial flexibility`；
- 以 renewable-energy consumption、carbon emissions、operating cost 为目标的任务调度；
- 两阶段时空调度算法 `ESTS`。

这篇文献与 Q2 的“算力负荷时空调度 + 新能源 + 碳排 + 成本 + QoS/容量”高度接近。因此 Q2 使用“时空工作负载/算力负荷调度模型”有非常直接的文献基础。

**边界：** ESTS 是该论文自己的算法，本题不直接改名为 ESTS；本题还有附件特有的 GPU-hour、MaxLatency、PUE、Curtailment 基准状态等结构。

### 2.2 Carbon-aware temporal/spatial workload shifting — EuroSys 2024

Sukprasert T, Souza A, Bashir N, Irwin D, Shenoy P. **On the Limitations of Carbon-Aware Temporal and Spatial Workload Shifting in the Cloud.** EuroSys 2024, 924--941. DOI: 10.1145/3627703.3650079.

该文直接使用/讨论：
- carbon-aware temporal and spatial workload shifting；
- carbon-aware spatiotemporal scheduling for cloud workloads；
- job duration、deadline、SLO 作为 workload shifting 的限制因素；
- 简单 scheduling policies 与复杂算法的收益差异。

因此“碳感知时空工作负载调度/迁移”属于成熟科研语言，不是本文造词。

### 2.3 Spatiotemporal flexibility + renewable curtailment mitigation — RSER 2024

Zare Ghaleh Seyyedi A, Akbari E, Mahmoudi Rashid S, Nejati S A, Gitizadeh M. **Application of robust optimized spatiotemporal load management of data centers for renewable curtailment mitigation.** Renewable and Sustainable Energy Reviews, 2024, 204:114793. DOI: 10.1016/j.rser.2024.114793.

该文摘要直接把跨地点、跨时段的负荷转移能力称为 **spatiotemporal flexibility**，并将其用于 **renewable curtailment mitigation**。

因此原中文“任务时空柔性—弃电消纳”有明确文献对应，但正式英文不应自行造 `curtailment absorption coupling`；推荐用：

`spatiotemporal workload flexibility + renewable curtailment mitigation`。

### 2.4 Load migration reduces curtailment and carbon emissions — Joule 2020

Zheng J, Chien A A, Suh S. **Mitigating Curtailment and Carbon Emissions through Load Migration between Data Centers.** Joule, 2020, 4(10):2208--2222. DOI: 10.1016/j.joule.2020.08.001.

该文直接研究 data-center load migration 对 renewable curtailment 与 GHG emissions 的降低作用。

因此“通过跨数据中心任务/负荷迁移吸收弃电并降碳”有直接同行评议文献基础。

### 2.5 Marginal resource allocation — CarbonScaler 2023

Hanafy W A, Liang Q, Bashir N, Irwin D, Shenoy P. **CarbonScaler: Leveraging Cloud Workload Elasticity for Optimizing Carbon-Efficiency.** Proceedings of the ACM on Measurement and Analysis of Computing Systems, 2023, 7(3):Article 57. DOI: 10.1145/3626788.

CarbonScaler 明确指出其 greedy carbon-scaling algorithm 基于 well-known **marginal resource allocation** problem。

本题只吸收“比较一个候选位置带来的增量 Cost/Carbon/curtailment 后果”这一思想，不采用 CarbonScaler 的资源弹性 scaling。

### 2.6 Carbon-efficient scheduling + temporal flexibility — GREEN, NSDI 2025

Xu K, Sun D, Tian H, Zhang J, Chen K. **GREEN: Carbon-efficient Resource Scheduling for Machine Learning Clusters.** NSDI 2025:999--1014.

该文使用 carbon-aware scheduling，并明确利用 ML jobs 的 **temporal flexibility** 把负荷移至低碳时段，同时维持时间效率与容量约束。

### 2.7 Geo-distributed ML scheduling — MAST, OSDI 2024

Choudhury A, Wang Y, Pelkonen T, et al. **MAST: Global Scheduling of ML Training across Geo-Distributed Datacenters at Hyperscale.** OSDI 2024:563--580.

该文确认 geo-distributed datacenter scheduling / global ML scheduling 属于成熟系统问题表述，并说明区域容量约束和全局任务放置具有实际系统意义。

### 2.8 Time-indexed formulation — Operations Research Letters 2017

Artigues C. **On the strength of time-indexed formulations for the resource-constrained project scheduling problem.** Operations Research Letters, 2017, 45(2):154--159. DOI: 10.1016/j.orl.2017.02.001.

该文明确把离散时域中的 0--1 `time-indexed formulations` 作为非抢占调度中的成熟建模形式。本题可借用 `x[i,r,s]` 表达，但因为任务之间没有 precedence graph，不将本题直接命名为 RCPSP。

### 2.9 Minimum slack priority

调度文献中存在成熟的 `minimum slack` / `minimum slack time first (MSTF/MSF/MSLK)` priority rules。本文只借用 slack 越小越优先这一调度思想，不声称本题的完整任务排序就是某个现成 MSTF 算法。

---

## 3. 对当前自定义词的处理

### 3.1 “任务时空柔性—弃电消纳耦合的碳感知资源约束调度模型”

判断：**中文机制描述合理，但不是一个已发表的标准模型专名。**

建议正文：

> 本文建立碳感知时空工作负载调度模型（carbon-aware spatiotemporal workload scheduling），并针对附件数据嵌入任务时空柔性、资源容量约束与新能源弃电缓解机制。

英文概括可写：

> Carbon-aware spatiotemporal workload scheduling with resource-capacity constraints and renewable curtailment mitigation.

不建议为这一整串再造英文缩写。

### 3.2 “基准状态中心化边际能源核算”

判断：**不是标准科研术语，属于此前聊天中形成的描述性名称。**

已改为：

> 基准状态增量能量平衡 / baseline-referenced incremental energy balance

并明确它只是本题为了隔离 Q2 与 Q3 自由度而采用的核算规则，不宣称为已有模型。

### 3.3 “least-flexible-first”

判断：**不把它当作标准算法名。**

正式写法：

> priority-rule-based constructive scheduling heuristic，优先规则依次使用空间可行域大小、slack、GPU-hour。

其中 minimum slack / slack-based priority rule 是成熟调度思想；`|R_i|` 小者优先属于本题针对空间迁移可行域设计的 problem-specific priority rule。

### 3.4 SFETA

判断：**本文自定义算法名，不是已有标准缩写。**

对 `SFETA` 及完整扩展 `Spatio-temporal Flexibility and Energy-aware Task Assignment` 的检索没有发现该名称已作为相同领域标准算法使用；但这只能支持“未发现明显同名冲突”，不能证明唯一性或注册意义。

如果保留，必须写：

> We develop an SFETA heuristic ...

而不能写：

> We adopt the SFETA algorithm ...

算法家族应描述为：

`priority-rule-based constructive task assignment/scheduling heuristic`。

其来源关系：

- REPTA：非迭代、领域规则驱动的时空任务分配思想；
- scheduling priority rules：slack 等优先级；
- CarbonScaler：marginal resource allocation 的候选增量评价。

---

## 4. 当前推荐术语表

| 论文中文 | 论文英文 | 是否可当正式术语 |
|---|---|---|
| 碳感知时空工作负载调度 | carbon-aware spatiotemporal workload scheduling | 是，作为成熟问题族/描述；无统一标准缩写 |
| 时空算力负荷调度 | spatio-temporal scheduling of computing load | 是，Chen et al. 2024 直接使用同类表述 |
| 时间/空间工作负载迁移 | temporal/spatial workload shifting | 是 |
| 任务时空柔性 | spatiotemporal workload flexibility | 是 |
| 时间柔性 | temporal flexibility | 是 |
| 空间柔性 | spatial flexibility | 是 |
| 可延迟任务 | delay-tolerant / deferrable workloads | 是 |
| 地理分布式数据中心 | geo-distributed / geographically distributed datacenters | 是 |
| 新能源弃电 | renewable curtailment | 是 |
| 新能源弃电缓解 | renewable curtailment mitigation | 是 |
| 工作负载迁移 | workload/load migration | 是 |
| 资源容量约束 | resource/capacity constraints | 是，描述性标准术语 |
| 时间索引建模 | time-indexed formulation | 是 |
| 边际资源分配 | marginal resource allocation | 是 |
| 优先规则 | priority rule / dispatching rule | 是 |
| 最小松弛时间规则 | minimum slack / minimum slack time first | 是 |
| 基准状态增量能量平衡 | baseline-referenced incremental energy balance | 本题描述，不声称标准专名 |
| 弃电消纳耦合 | curtailment absorption coupling | **不建议当英文正式术语** |
| least-flexible-first | least-flexible-first | **不声称标准算法名** |
| SFETA | Spatio-temporal Flexibility and Energy-aware Task Assignment | **本文自定义算法名** |

---

## 5. 当前模型命名建议

### 正式模型名

**碳感知时空工作负载调度模型**

英文：

**Carbon-Aware Spatiotemporal Workload Scheduling**

若希望更贴近 Chen et al. 2024 的措辞，也可以写：

**Spatio-temporal Scheduling Model for Computing Load with Carbon Awareness**。

第一种更像计算机系统领域的问题族表述；第二种更像数据中心能源调度论文的模型表述。

### 本题特化说明

“考虑资源容量约束与新能源弃电缓解”作为模型特化说明，而不是再制造一个新模型专名。

### 算法名

SFETA 可继续作为本文自定义算法名，但必须注明自定义；若论文后续觉得缩写过多，可直接写“基于优先规则与边际能源评价的构造式调度算法”，不影响模型成立。
