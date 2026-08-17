# 全文数据结构驱动公共模块任务（2026-08-18）

适用分支：`feature/paper-shell`。

目标：把 Q1--Q4 已经确认的数据关系写进标题、摘要、重述、假设、符号、评价与文献，使完整论文不是“模型清单”，而是“数据关系驱动的模型链”。

## P0 摘要
- [ ] 删除当前模板句。
- [ ] 首句给出核心数据矛盾：异构任务、区域算力/网络/能效/储能优势错位，以及附件存在显著算电时空错配。
- [ ] Q1 只概括“结构化标记复合 Poisson + 基础调度”，不要堆细节。
- [ ] Q2 强调释放 workload 时空柔性并利用弃电/购电错配；写最终 canonical 数字时只用 FROZEN/CHECKED。
- [ ] Q3 强调 H+SellLimit 导出三类储能角色、E1-E0 识别 BESS 增量价值。
- [ ] Q4 强调两类柔性争用同一新能源余量，因此 joint scheduling；算法名放后，不让 Benders/CG 抢主语。
- [ ] 最后一段“本文特点”改成数据结构驱动、无主观权重、完整合法域、严格审计/benchmark。

## P0 问题重述
- [ ] 删除通用模板，真实写四问。
- [ ] 用“释放哪些决策自由度”组织：Q1 baseline；Q2 workload；Q3 energy/BESS；Q4 joint。
- [ ] 明确 0--2399 arrivals、2400--2405 drain、2406 terminal energy settlement。

## P0 标题
- [ ] 不使用“Poisson+SFETA+LP+Benders+CG”算法堆叠标题。
- [ ] 标题主语围绕“异构任务时空柔性、储能时间柔性、计算—能源协同调度”。
- [ ] 算法名最多作为副标题/补充，不应压过题目对象。

## P0 模型假设
- [ ] 重写为 3--6 条真实假设，不使用“主要机制稳定/数据具有代表性”通用套话。
- [ ] 必含：任务不可抢占/拆分/中途迁移；网络只使用题给 latency/SLA；题给 power mapping/PUE/逐时参数在对应小时有效；Q1 24h 局部到达结构近似稳定；raw baseline 异常不擅自修正。
- [ ] 不增加题目没有的迁移能耗、带宽、SOH、线路潮流等假设。

## P0 符号表
- [ ] 统一跨问核心符号：`x_{irs}`、`a_i,p_i,g_i`、`L_{rt}`、`H_{rt}`、`E_{rt}`、Cost、Carbon、RenewableUtilization、Wait、Latency。
- [ ] 标注单位，避免 Q2/Q4 对同一量改名。
- [ ] 单问局部变量留在首次出现处，不把符号表无限扩张。

## P0 模型总结与评价
- [ ] 总结按“Q1发现结构 -> Q2释放计算柔性 -> Q3释放储能柔性 -> Q4联合两类柔性”串联。
- [ ] 优点具体写：数据结构驱动；不使用 AHP/熵权；完整合法域；Q2 multi-start；Q3 E0/E1 识别；Q4 exact benchmark + recourse audit。
- [ ] 局限具体写：Q1 test仅24h；Q2启发式初始化路径依赖；Q4 50k global integer optimum若未证明，必须报告 LB/UB/gap 而非泛泛“算法复杂”。
- [ ] 不写“模型具有较强普适性”等无证据套话。

## P0 参考文献
- [ ] 补 Q1 marked/compound Poisson 与短期需求建模。
- [ ] 补 carbon-aware / geo-distributed workload scheduling。
- [ ] 补 BESS economic dispatch / complementarity / no-storage benchmark。
- [ ] 补 Benders、column generation、multi-cut、必要时 stabilization。
- [ ] 至少 10 篇，英文不少于 3；正文中的方法名称必须有对应引用或明确为本文自定义算法。

## P1 全文数据主线检查
- [ ] Q1 第一张数据图回答“为什么 marked Poisson”。
- [ ] Q2 第一张数据图回答“为什么 workload 迁移有必要”，优先展示 91.9% 弃电+购电并存与 8.15×绿色余量。
- [ ] Q3 第一张数据图回答“为什么自然分成 A/B/C、D/E、F”。
- [ ] Q4 第一张数据图回答“为什么没有单一最优 Region、为什么 Q2/Q3 必须联合”。
- [ ] 流程图只画逻辑，不替代数据证据图。

## P1 跨问统一口径
- [ ] Cost/Carbon/RenewableUtilization 的统计时域统一；Hour 2406 单独说明。
- [ ] Baseline/reference/B0 命名统一。
- [ ] PeakImport 定义统一为区域独立峰值，不允许跨区售电抵消另一区购电后再称“区域峰值”。
- [ ] RT immediate-start 统一。
- [ ] “全局最优”只在有 certificate 时使用。

## 最终验收
只看摘要、每问第一张数据图、流程图和结果表，读者应能回答：
1. 附件里最关键的非显然关系是什么；
2. 这些关系分别决定了什么模型；
3. 为什么不使用主观六指标权重；
4. 为什么 Q2+Q3 的顺序拼接不能替代 Q4；
5. 为什么复杂算法是数据规模/耦合结构逼出来的，而不是为了炫技。
