# Q4 近五年文献审计：算力—能源—储能联合调度

状态：`DRAFT / NEEDS_REVIEW`

目的：只吸收能直接支撑 Q4 的问题类型、分解范式、边际价值反馈、多目标组织和大规模任务调度思想。题面和附件字段定义优先；不把外部研究中的线路潮流、热系统、碳市场、随机预测、带宽、迁移能耗等机制移植进本题。

## 1. Integrated workload--energy management：Energy 2025

Guo H, Yu H, Wang M, Liu C, Li C. *Integrated management of workloads and energy system for data centers*. Energy, 2025, 327:136400. DOI: 10.1016/j.energy.2025.136400.

直接支持：

- workload transfer 与 energy dispatch 存在双向耦合；
- workload heterogeneity 应进入 transfer model；
- 只追求 energy cost 可能恶化 average delay rate；
- workload transfer 的驱动力不仅是价格/新能源，还包括 energy system optimal operation。

本题吸收：Q4 不能只做 Q2->Q3 one-shot；需要联合/反馈式 workload--energy coordination，并把服务质量独立于硬 SLA 评价。

不吸收：该文具体上海案例参数、热系统等。

## 2. 数据中心 + 电力系统 Benders / group multi-cut：IJEPES 2021

Niu T, Hu B, Xie K, Pan C, Jin H, Li C. *Spacial coordination between data centers and power system considering uncertainties of both source and load sides*. International Journal of Electrical Power & Energy Systems, 2021, 124:106358. DOI: 10.1016/j.ijepes.2020.106358.

直接支持：

- data-center load 与 power-system dispatch 可做协调优化；
- Benders decomposition 可分离需求侧/计算决策与能源子问题；
- group-based multi-cut 可提高分解效率。

本题吸收：任务离散 master + 给定任务负荷后的连续 Renewable/BESS/Grid LP subproblem；无系统级跨区耦合时可利用区域可分性做 region multi-cut。

不吸收：随机电力系统、线路/网络约束。本题官方明确不建线路潮流。

## 3. Marginal-cost-guided task scheduling：Sustainable Computing 2021

Ji K, Zhang F, Chi C, Song P, Zhou B, Marahatta A, Liu Z. *A joint energy efficiency optimization scheme based on marginal cost and workload prediction in data centers*. Sustainable Computing: Informatics and Systems, 2021, 32:100596. DOI: 10.1016/j.suscom.2021.100596.

直接支持：

- marginal cost evaluation 可用于 task scheduling 与 migration；
- 边际量比静态区域标签更适合指导动态任务分配。

本题吸收：Energy LP 的 load-balance dual/shadow price 作为任务候选的局部 recourse value；但 Probe 2 已显示大任务跨 active-set breakpoint 时一阶 dual 会有误差，因此正式算法需要重新求 recourse/cut，而不是一次定价到底。

不吸收：该文 workload prediction / cooling resource 管理层。

## 4. REPTA 三阶段快速范式：Applied Energy 2026

Yang L, Shahidehpour M, Chen X, Wang C, Fang X, Yang Q. *High-speed REPTA algorithm for performance cost optimization in data centers considering workload delay tolerances*. Applied Energy, 2026, 404:127156. DOI: 10.1016/j.apenergy.2025.127156.

直接支持：

- delay-tolerant workload 会造成大规模组合变量；
- 可先解能源、再按 RES/price 分配延迟任务、再重新解能源；
- domain-specific constructive algorithm 可比通用元启发式更适合大规模数据中心调度。

本题用途：作为 Q4 sequential baseline 和 Q2 SFETA 的研究范式参考。

Probe 1/2 已发现 one-shot sequential 会把储能可回收的新能源误判成免费任务机会，因此 Q4 不直接照搬 non-iterative 三阶段策略。

## 5. Geo-distributed ML global scheduling：OSDI 2024

Choudhury A, Wang Y, Pelkonen T, et al. *MAST: Global Scheduling of ML Training across Geo-Distributed Datacenters at Hyperscale*. OSDI 2024:563--580.

直接支持：

- geo-distributed ML training 的跨区域 placement 是成熟系统问题；
- temporal decoupling、scope decoupling 与 exhaustive-search-style structure exploitation 可用于大规模调度；
- 算法扩展性应优先利用 workload structure，而不是自动切换 GA/PSO/RL。

本题吸收：继续利用 RT/Batch/Training 的时空柔性结构；完整候选域不做 top-k 人为截断。

## 6. Carbon-efficient ML scheduling：NSDI 2025

Xu K, Sun D, Tian H, Zhang J, Chen K. *GREEN: Carbon-efficient Resource Scheduling for Machine Learning Clusters*. NSDI 2025:999--1014.

直接支持：

- carbon-aware scheduling 必须同时考虑 time efficiency/JCT；
- ML job temporal flexibility 可用于 shifting 到低碳时段；
- 碳收益与服务性能应单独评价，不能只做碳硬约束后忽略任务性能。

本题吸收：Q4 的 ServiceQuality 需要独立于 NetworkLatency 和 deadline-feasibility 表达；正式指标优先从 waiting/delay/JCT family 中选择。

## 7. 多目标 epsilon-constraint：Energy 2023

*Multi-objective robust optimal bidding strategy for a data center operator based on bi-level optimization*. Energy, 2023, 269:126761. DOI: 10.1016/j.energy.2023.126761.

可支持：

- 数据中心可同时优化 operating cost 与 carbon emissions；
- spatial/temporal workload dispatch 与多目标 Pareto 分析可结合；
- epsilon-constraint 是不依赖跨量纲主观加权的成熟组织方法。

本题吸收：先求单指标锚点，再以 Cost 为主目标、Carbon/QoS/Latency/Renewable/Peak 作为 epsilon bounds；不照搬其 bi-level market-power、KKT、DRO、TOPSIS。

## 8. 当前文献结论

Q4 最有依据的范式是：

1. **joint workload--energy optimization**：题目本体；
2. **Benders decomposition / multi-cut**：离散任务 master + 连续能源 recourse；
3. **marginal/dual value feedback**：用于解释和构造 cut，不作为一次性静态评分；
4. **epsilon-constraint**：组织 Cost--Carbon--QoS 等权衡；
5. **domain-structured scheduling**：利用任务时空柔性解决全规模 master 的候选规模问题。

不建议为了“先进”引入：RL、PSO/GA、DRO、MPC、Stackelberg、shared storage、hydrogen、线路潮流、带宽或迁移传输能耗。这些要么缺参数，要么超出官方边界。

## 9. 与当前 Probe 的对应

- Probe 1：实证 one-shot Q2->Q3 会产生虚假迁移收益；支持 joint workload--energy 而非单向串联；
- Probe 2：Energy LP dual 对真实 recourse 排序有效，但全量重排会振荡；支持 marginal feedback + 历史信息保留；
- Probe 3：40-task exact benchmark 上，region multi-cut Benders 2 次迭代复现 exact joint Cost；新能源波动激活 Carbon budget 后，global-cut Benders 对 5 个 epsilon budget 同样 2 次迭代复现 exact MILP。

这些结果只说明当前小规模 benchmark 的算法结构匹配，不能直接外推全 50,000 任务收敛次数。
