# 第9题参考文献来源与支持范围说明

状态：`DRAFT / NEEDS_REVIEW`

本文件记录当前建模讨论中已经实际使用或作为备选依据的文献，以及每篇文献**具体支持什么判断、不能支持什么判断**。正式正文引用前仍需逐句核对，避免“同领域文献替代具体结论”的问题。

## A. 题意、时间粒度与调度问题定位

### `problem`
武汉理工大学训练赛第9题及附件说明。

**支持：**
- 0--2399 h 到达、2400--2405 h 收尾、2406 h 终端结算；
- 1 h 数据粒度；
- Q1 预测训练/验证/测试划分；
- Q1 正式调度使用 2376--2399 实际到达任务；
- Q3 固定 Baseline_AI_IT_Load_MW 与 NonAI_IT_Load_MW；
- Q1/Q2/Q4 的 GPU、IT、Facility、Latency、deadline 等硬约束；
- power_mapping 是任务到 AI IT 功率的统一映射；
- Q4 不要求带宽、迁移数据量、传输能耗/费用和线路潮流。

**不能支持：**
- 任何自行增加的价格权重、碳权重、迁移费用或连续开工时刻假设。

### `artigues_timeindexed_2017`
Christian Artigues, Operations Research Letters, 2017。

**支持：**
- 离散时间下非抢占任务的 time-indexed 表达属于成熟调度建模家族；
- earliest/latest start、处理时长和资源容量可以在统一离散时域中表达。

**本题用途：**
- 只用于说明整数小时开工/时段索引是一种合理建模解释；最终仍以题面 1 h 粒度为最高优先级。

---

## B. Q1：统计、聚合与概率预测

### `cohen_dac_2022`
Cohen, Zhang, Jiao, Operations Research, 2022。

**支持：**
- 当细分对象历史有限时，并非所有参数都必须在最细粒度单独估计；
- 可以根据数据决定参数在 individual / cluster / aggregate 层共享，以降低估计方差。

**本题对应：**
- 总到达率可在系统层估计；
- Region×TaskType 的组成在联合类别层估计；
- GPU mark 主要在 TaskType 层估计；
- Duration 是否需要分 TaskType，应由验证结果决定。

**不能支持：**
- 直接宣称本题必须使用 DAC 算法；目前只吸收其“数据决定估计层级”的思想。

### `yanchenko_hierarchical_2023`
Yanchenko et al., JRSS Series C, 2023。

**支持：**
- 层级、多尺度、可解释的 Bayesian 顺序预测可以在商业大规模场景中实现信息从聚合层向细粒度层传播；
- count data 可以使用 Poisson DGLM 等动态模型，且强调计算效率和解释性。

**本题对应：**
- 作为“如果企业运行中出现漂移/动态变化，可升级为在线动态概率模型”的扩展依据。

**当前不进入主模型的原因：**
- 本题 0--2399 h 数据未显示明显 24 h/168 h 时序记忆；直接使用完整 DGLM 会增加不必要状态参数。

### `bertani_jbu_2025`
Bertani, Jensen, Satopaa, Operations Research, 2025。

**支持：**
- 层级概率预测应保持 coherent，即底层预测加总必须与上层预测一致；
- 可以从底层联合概率模型自然产生所有上层预测。

**本题对应：**
- Region×TaskType 18 个底层需求通过同一 marked process 生成，再按 Region、TaskType 和 system total 汇总；Monte Carlo/解析传播天然保证加和一致，不需要事后 reconciliation。

### `ninh_poissongamma_2025`
Ninh, Hunt, Nguyen, INFORMS Journal on Computing, 2025。

**支持：**
- Poisson--Gamma 仍是近期实际运营场景中用于事件到达率估计和历史信息聚合的成熟结构。

**本题对应：**
- 若需要显式表达到达率参数不确定性，可使用 Gamma--Poisson；
- 但本题训练样本约 4.9 万任务，先验影响很小，因此不应把 Bayesian 先验本身包装成主要创新。

### `agnoletto_quasi_2025`
Agnoletto, Rigon, Dunson, Biometrika, 2025。

**支持：**
- Poisson 类 count model 若存在过离散，可只对均值--方差关系增加 dispersion 处理，提高模型错设下的鲁棒性，而不必立即换成更复杂全参数分布。

**本题对应：**
- 仅作为某些 Region×TaskType 子流出现明显 overdispersion 时的备用鲁棒层；主模型仍由实际 Fano/GOF 决定。

### `abbou_event_2025`
Abbou, Makis, Operations Research, 2025。

**支持：**
- 对 Poisson rate 的不可观测变化可以通过 Bayesian control chart 做事件触发式检测。

**本题对应：**
- 企业推广时可监测 workload regime shift，检测到变化后再重估/折扣旧数据；
- 不进入比赛 24 h 主预测模型。

### 当前 Q1 主模型引用口径

当前建议：

1. 主体采用**标记复合 Poisson 过程**描述任务到达与 GPU mark；
2. GPU mark 优先使用 TaskType 条件经验分布，离散均匀分布只作为参数化对照；
3. Duration 的估计层级由验证集比较决定；
4. 2400 个小时级观测点本身并非“高频大样本时序”，不要为 24 h 预测引入过多动态状态；
5. Monte Carlo 只在需要联合分位数/预测区间时使用，不应成为模型复杂性的主体。

---

## C. REPTA、SFETA 与地理分布式任务调度

### `yang_repta_2026`
Yang et al., Applied Energy, 2026。

**支持：**
- delay-sensitive / delay-tolerant workload 的显式区分；
- heterogeneous delay tolerance 会导致 MILP 决策变量膨胀；
- REPTA 是 Stage II 的具体 non-iterative 任务分配算法，而非三阶段整体的泛称；
- Phase A 优先消纳本地 RES overproduction；Phase B 再做跨区时空迁移，无 RES 时按低电价处理；
- 三阶段整体为：preliminary energy dispatch -> REPTA -> final energy redispatch。

**本题对应：**
- Q2/Q4 的 SFETA 从 REPTA 的“领域规则驱动、非迭代时空任务分配”出发；
- 不能照搬其跨区域 RES complementarity，因为本题 AvailableRenewable 在六区域逐时相同。

### `miao_ecmr_2024`
Miao et al., Science and Technology for Energy Transition, 2024。

**支持：**
- 分布式数据中心/edge-cloud 中可根据 SLA、能源价格、碳强度和可再生能源进行任务分配；
- 时隙可采用不超过 1 h 的离散时间；
- 可作为与 REPTA/SFETA 的领域基线或相关工作。

**不能支持：**
- 本题 E/F 必然具有不同的风/光曲线；附件数值没有这一空间差异。

### `zhao_zhou_2022`
Zhao, Zhou, Journal of Parallel and Distributed Computing, 2022。

**支持：**
- 地理分布式云数据中心中能源和碳感知 placement 是成熟研究方向；
- RES、能耗、碳与 SLA 可以共同进入任务放置判断。

**本题用途：**
- 相关工作和算法对照；其预测模块不直接迁移到本题 Q1。

### `lin_carbon_2023`
Lin, Chen, Li, IEEE Transactions on Cloud Computing, 2023。

**支持：**
- 可再生能源数据中心负载平衡可采用非黑箱在线优化；
- 面对价格/能源/碳等不确定性，可利用虚拟队列等在线方法获得理论保证。

**本题用途：**
- 支持“无需机器学习也可以进行在线数据中心调度”的判断；
- 更适合作为 Q4 在线扩展/理论对照，而不是 Q2 确定数据下的主算法。

### `cao_srhc_2024`
Cao et al., Applied Energy, 2024。

**支持：**
- geo-distributed data center 的时空 workload flexibility 可以用 stochastic receding horizon control 在线管理；
- 论文实例采用 1 h 粒度、24 h 研究期，并以 12 h rolling window 处理在线不确定性。

**本题用途：**
- 说明 1 h 是数据中心能源/工作负载协同研究中常见的运行粒度；
- 支持 Q4 未来考虑 rolling horizon，但本题不应仅因 2406 h 总时域长就自动采用复杂 MPC。

### `han_fourlevel_2024`
Han et al., Applied Energy, 2024。

**支持：**
- 任务 delay sensitivity、区域迁移边界与多级调度可以显式结合；
- 地域信息可用于分层调度。

**本题用途：**
- 支持 TaskType/SLA 对空间可行域进行先验限制；
- 其四层架构不是本题必要结构。

### `yang_mpc_2025`
Yang et al., Energy, 2025。

**支持：**
- geographically distributed DC 可采用 day-ahead + intra-day MPC 的两阶段协同；
- 原文案例同样使用 1 h 时间间隔和 24 h 优化时域。

**本题用途：**
- 作为企业在线运行/不确定性处理的扩展参考；
- 本题 Q2--Q4 已给实际数据，不能为了套 MPC 再人为制造预测误差。

### `wu_survey_2025`
Wu et al., IEEE TPDS, 2025。

**支持：**
- geo-distributed task scheduling 是成熟计算机系统研究问题；
- 网络条件、区域价格和计算能力异质性均是典型调度因素；
- 数学优化、启发式、AI 和混合方法均属于已有方法族。

**本题用途：**
- 支持选择数学/规则驱动算法而不使用黑箱 ML 的合理性；
- 作为相关工作总览。

---

## D. 储能、不确定性与 Q3/Q4 备选方法

### `han_dro_2025`
Han et al., Journal of Building Engineering, 2025。

**支持：**
- 多任务响应与可再生能源不确定性可以进入两阶段数据驱动 DRO；
- 任务的不同执行时间/延迟容忍度可以量化其调节潜力。

**本题用途：**
- 只作为 Q4 新能源波动场景的高级备选；本题官方主运行参数为实际值，不应默认引入 WGAN/DRO。

### `han_ecmx_2026`
Han et al., Energy Conversion and Management: X, 2026。

**支持：**
- C&CG + ADMM 可以处理 geo-distributed DC 的可再生不确定性、时空负荷与分布式协同。

**本题用途：**
- Q4 高级鲁棒/分解扩展候选；目前不进入主模型，避免增加与题目数据不匹配的复杂度。

---

## E. SFETA 命名边界

### `chen_feta_2020`
Chen et al., PVLDB, 2020。

**支持：**
- FETA 已被正式用于 Fair and Effective Task Assignment 问题名称。

**本题后果：**
- 不再把本题算法命名为 FETA，避免与已有文献术语冲突；
- 当前候选名保留为 SFETA（Spatio-temporal Flexibility and Energy-aware Task Assignment），待 Q2 算法正式冻结后再确认是否进入论文。

---

## F. 当前引用纪律

1. 题面和附件定义优先于外部文献；外部文献不能覆盖官方数据口径。
2. 数据审计得到的“近 Poisson、24/168 h 周期、六区 renewable 相同、价格/碳固定偏序”等属于**附件数据实证结果**，引用应优先指向本仓库审计代码/结果，而不是用外部论文替代证据。
3. 外部文献只承担：模型家族来源、算法机制来源、企业推广或备选方法依据。
4. 正式论文不会把本文件列出的所有文献全部引用；只保留实际支撑正文句子的文献。
5. 任何尚未进入当前代码验证的 DRO、MPC、在线控制方法均标为扩展/备选，不得写成已采用方法。
