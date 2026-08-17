# Q1--Q4 近十年文献：支撑、提升与纠偏总审计（2026-08-17）

状态：`DRAFT / NEEDS_REVIEW`

用途：给四问正式论文提供“哪些地方有文献直接支撑、哪些是本题数据特化、哪些表述必须纠偏”的统一索引。外部文献不替代题面与附件定义。

> 引文均只保留短句，用于定位论文原意；正式 LaTeX 引用前仍应由参考文献手核对出版页/PDF 原文和 BibTeX 作者字段。

## Q1：marked Poisson + hierarchical coherent forecast

### Zou et al., JNCA 2022
论文短句：`Memory access behavior can be approximated by a Poisson process at small timescales.`

用途：支持“计算 workload 的 Poisson 性依赖时间尺度，应先做 Fano/GOF/ACF 等诊断”。

**纠偏**：不能写“文献证明 AI 任务天然服从 Poisson”。本题 Poisson 证据来自附件训练段。

### Taddy & Kottas, Bayesian Analysis 2012（基础理论例外，超十年窗口）
论文短句：`yield flexible inference about the conditional distribution for multivariate marks`。

用途：支持 event arrival + multivariate marks 的联合建模；本题 `Region, TaskType, GPU, Duration` 的具体条件结构仍由附件决定。

### Cohen et al., Operations Research 2022
论文短句：`balances the tradeoff between data aggregation and model flexibility.`

用途：支持本题不为 18 个 Region×Type cell 各拟一套资源模型，而在数据支持下共享 `(GPU,Duration)|TaskType`。

### Bertani et al., Operations Research 2025
论文短句：`accurate and coherent probabilistic forecasts for all series in the hierarchy can be obtained by focusing on a joint model`。

用途：支持 Region×TaskType 底层联合建模再向 Region/TaskType/System 严格聚合。

### 当前提升
新增训练段 composition/dispersion probe：18 个子流 dispersion `0.944--1.079`；Bonferroni 后 0/18 拒绝；cell 同时相关绝对均值约 `0.0148`；四块组成 Cramer's V≈`0.0203`。因此暂不升级 NB/时变 pi/covariance model。

## Q2：carbon-aware spatiotemporal workload scheduling

### Sukprasert et al., EuroSys 2024
论文短句：`simple scheduling policies often yield most of these reductions, with more sophisticated techniques yielding little additional benefit.`

用途：支持先利用 deadline/SLO/capacity/workload structure，再判断复杂算法是否必要；同时支持 temporal/spatial workload shifting 的成熟术语。

### Zheng et al., Joule 2020
论文 highlight：`Load migration can reduce renewable curtailment and GHG emissions`。

用途：直接支持 workload migration -> renewable curtailment mitigation。

### CarbonScaler, POMACS 2023
论文表述：算法基于 `marginal resource allocation`。

### Ji et al., Sustainable Computing 2021
论文短句：`An online task scheduling algorithm is developed using marginal cost evaluation.`

用途：共同支持 Q2 使用当前状态边际后果，而不是静态 `Curtailment0 -> CI -> Price` 标签排序。

### Chen et al., Sustainable Computing 2024
论文短句：`By employing a spatio-temporal scheduling method for computing power load, data center enterprises can maximize the benefits of renewable energy`。

用途：支持计算负荷时空调度与 renewable/cost/carbon 联动。

### MAST, OSDI 2024
论文设计原则：`temporal decoupling, scope decoupling, and exhaustive search.`

用途：支持大规模问题优先利用 workload structure，而不是自动转 GA/PSO/RL。

### 当前纠偏
Q2 的 `DeltaL -> DeltaGrid/DeltaCurtailment` 分段式是本文为隔离计算柔性定义的 **baseline-referenced accounting assumption**，不是 Joule/CarbonScaler 给出的客观能源系统定律。

### 当前提升
新增 `flexibility headroom`：旧草稿 Cost/Carbon 分别只捕获 relaxed removal-side headroom 的约 `38.6%/42.1%`；新版动态边际 SFETA 重跑后应重新计算 capture ratio。

## Q3：fixed-load BESS economic dispatch + curtailment recovery

### Zhang et al., Energy 2025
论文短句：`The objective of optimal dispatch is to minimize the electricity cost`。

用途：支持固定 data-center load 下单独做 BESS economic dispatch；Q3 不必重引入任务调度。

### Journal of Energy Storage 2021 curtailed-wind BESS
论文 highlight：`Batteries were charged by curtailed wind and discharged to grid during peak time.`

用途：支持 `curtailed renewable -> BESS -> future value` 的 curtailment-recovery 机制。

**纠偏**：本题附件 `GridSell` 是新能源富余外送；不能照搬“电池直接向电网售电”。本题 `dS` 是电池替代设施负荷，从而释放当期新能源进行售电。

### Wang et al., Applied Energy 2024 exact relaxation
论文短句：`it is guaranteed that there is no simultaneous charging and discharging`，但依赖其 generalized relaxation condition。

**纠偏**：本题 `Cost -> minimum throughput` 只是 lexicographic physical tie-break，不得称为该文 exact-relaxation theorem。

### Cruise et al., Operations Research 2019
论文短句：`We apply Lagrangian theory to develop such a model`。

用途：支持使用储能状态约束 dual/shadow value 解释跨时段边际价值。

### Grimaldi et al., Journal of Energy Storage 2025
论文表述：比较 wind-battery 与 `scenario without storage`。

用途：支持 E0/E1 识别 BESS incremental value。

### 当前提升/纠偏
附件条件可证明 A/B/C 的字典序代表解零动作，并证明至少存在 `GridCharge=0` 的成本最优代表解。Full vs reduced LP 在附件上 value/throughput 一致到约 `1e-6`，目前应称 `dataset-level numerical lossless reduction`，不先包装成一般等价定理。

SOC dual 在 E/F 有清晰非零稀缺窗口，但 D 可因退化返回全零 dual；因此 shadow curve 只作某一最优对偶代表解的局部解释。

## Q4：joint workload--energy--storage + Benders

### Guo et al., Energy 2025
论文短句：`simultaneously optimize workload transfer and energy dispatch.`

用途：直接支持 Q4 不是 Q2->Q3 one-shot，而需要 workload transfer 与 energy dispatch 双向协调；该文同时报告 energy cost 与 delay tradeoff。

### Niu et al., IJEPES 2021
论文短句：`Benders decomposition and a new type of group based multi-cut approach is applied to solve the problem.`

用途：支持 data-center flexibility + energy dispatch 的 Benders/multi-cut 分解范式。

**边界**：其 master/subproblem 不是本题 `task x[i,r,s] + BESS recourse` 的原样模型；本题具体 cut 由附件结构推导并由 exact benchmark 验证。

### Ji et al., Sustainable Computing 2021
`marginal cost evaluation` 支持 Energy-LP dual 作为 task candidate 的局部 recourse value；Probe 2 进一步证明只保留最新 dual 会振荡，因此升级为历史 Benders cuts。

### Energy 2023 multiobjective data-center paper
论文短句：`The Pareto set is obtained using the epsilon constraint method.`

用途：支持 Cost--Carbon 等跨量纲目标优先用 epsilon-constraint，而不是 AHP/人工加权。

### REPTA, Applied Energy 2026
论文短句：`A non-iterative REPTA algorithm is designed to achieve fast decision-making.`

用途：作为 Q4 sequential baseline；Probe 1/2 已证明 one-shot 会产生虚假能源机会和过度迁移，因此不再作为四问统一框架。

### 当前规模纠偏
40-task exact benchmark 上 Benders 可 2 iteration 复现 exact joint MILP，但完整合法 master 有 `233,375,201` binary candidates。仅 assignment+GPU+IT+Facility 的显式 sparse matrix 下界约 `2.96e9` nonzeros、约 `35--47 GB` CSR 存储，不含 solver 开销和 cuts。

因此：

- 完整 Benders **数学模型**成立；
- 50,000-task **实现**需要 delayed column/candidate generation 或其他 exact implicit master；
- 不能把 40-task probe 写成“全规模全局最优已经解决”；
- 仍禁止 arbitrary top-k / fixed wait window。

### Renewable scenario 纠偏
附件 0--2399 的 100 个新能源日 profile 完全一致，daily CV 与 amplitude 无经验分布可供 Q25/Q50/Q75 校准。因此正式“新能源波动场景”只能明确写成 scenario/sensitivity construction，不能声称来自 100 天日波动分位数。Probe 3 的 `gamma` 机制可保留为透明生成器，但参数需由系统临界点/明确压力级别组织。

## 总结：四问创新应如何表述

- Q1：不是“新 Poisson”，而是附件诊断驱动的 marked structure + coherent hierarchy；
- Q2：不是“新启发式名字”，而是 task flexibility/resource weight/current marginal energy response；
- Q3：不是“新 LP”，而是 E0 解析、区域消去、curtailment-recovery 的数据结构约化；
- Q4：不是“首次 Benders”，而是本题 task-level discrete master 与 BESS recourse 的结构匹配、dual/cut 必要性探针和多目标边界组织。

统一主张：**成熟算法负责求解，附件数据结构决定模型自由度、约化和耦合。**
