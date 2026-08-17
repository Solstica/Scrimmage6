# Q4 数据结构驱动论文与作图任务（2026-08-18）

依据：`modules/50_q4/paper/DATA_STRUCTURE_PAPER_ENRICHMENT_20260818.md`。

本任务不改变当前 joint workload--energy--storage 模型，不干扰 Latency integer Benders resume；只负责把联合优化的“数据必要性”补进正文和图，避免 Q4 退化为纯求解器叙事。

## P0 正文必要性链

- [ ] 在 Benders/CG 之前增加“为什么必须联合优化”的数据分析段。
- [ ] 明确三类任务柔性与能耗异构：Training 约 1/3 任务但约 80.14% GPU-hour、87.12% AI IT energy；RT 时间刚性且只 1--3 个合法区。
- [ ] 明确区域优势错位：D 的 GPU 最大；D/E/F PUE 较低且 BESS/SellLimit 更强；A/B/C 用户侧低时延优势更明显；不存在单一“最佳区域”。
- [ ] 明确六区 AvailableRenewable 逐时完全相同，禁止把 E/F 题面“新能源区”标签直接转成绿色评分。
- [ ] 明确 Q4 动态盈余 `H[r,t](x)` 随 workload placement 改变，因此 Q3 的盈余/弃电/购电机会不是 Q4 固定输入。
- [ ] 将 3-task/8-combination Probe 1 写进模型分析：Q2 静态核算认为迁到 F 节约约 3613.67 CNY，但重新优化 BESS 后 8 个组合能源成本相同，留 E 网络时延更低；直接证明 sequential Q2->Q3 可能失真。
- [ ] 将 Training TaskID 1 dual probe 写成“为什么使用 Benders history 而非最新 shadow price 贪心”的数值依据；dual 只作局部次梯度，不替代真实 recourse。
- [ ] 数据结构计算压缩（Facility/IT重复、dual稀疏、2.33e8 placements）放到“可计算性”小节，不抢模型必要性主线。

## P0 必补数据图

### Q4-A 六区域算力—网络—能源—储能结构矩阵
- [ ] 行=Region A--F。
- [ ] 列至少含 AvailableGPU、PUE、RT/低时延可达指标、StorageCapacity、MaxCharge/Discharge、SellLimit、Price/Carbon代表量、baseline Curtailment代表量。
- [ ] 若为视觉统一做标准化，只用于图形显示；图注/附表保留原始单位和原始值。
- [ ] 禁止 AHP、熵权、综合评分或“总优势排名”。
- [ ] 图的核心结论必须是：低时延、算力、能效、储能、售电优势错位。

### Q4-B 顺序优化失真 Probe
- [ ] 以 8 个 E/F placement 组合为横轴。
- [ ] 对比冻结 BESS 的 Q2 static marginal 与重新优化 BESS 后 true energy recourse。
- [ ] 叠加/旁注网络 latency。
- [ ] 图注结论固定为 `Q2 static marginal != Q4 post-BESS recourse value`，用来证明 joint model 必要性。

### Q4-C 两类柔性争用同一绿色余量机制图
- [ ] 展示 `AvailableRenewable/H(x)` 同时可被迁入任务当期消纳或 BESS 跨时搬移。
- [ ] 强调两路既互补又竞争，因此不能先固定 Q2 schedule 再调用 Q3。
- [ ] 这是一张机制图，不需要引入新的加权指标。

## P1 算法证据图

### Q4-D 40-task exact benchmark
- [ ] 简洁展示 3139 explicit placements、exact joint 与 Benders/CG Cost 一致。
- [ ] 同图或旁表展示 Cost-only 服务退化与 Cost->Wait->Latency 代表解差异。
- [ ] 不占主流程图大块；定位为算法可信度证据。

### Q4-E 50k closure 图
- [ ] 等当前 Latency integer Benders 得到真实能源可行候选后再做。
- [ ] 区分 root LP closure、full-domain pricing、restricted MIP、true energy recourse check。
- [ ] 若展示 LB/UB/gap，必须用当前正式定义；无 certificate 时禁止“global optimum”。

## P0 最终结果图（等待 Q4 真正闭合）

### Q4-F Q2-only / Q3-only / Q4-joint 统一口径对比
- [ ] 统一 Hour 2406 accounting 后再计算。
- [ ] 比较 Cost、Carbon、Wait/QoS、Latency、RenewableUtilization、regional PeakNetImport。
- [ ] 目的：量化联合优化相对两个单侧优化新增的协同价值。
- [ ] 不用六指标加权成一个总分。

### Q4-G 正式场景对比
- [ ] Carbon constraints：正式 epsilon/scenario 结果。
- [ ] Electricity-price mechanisms：按冻结协议。
- [ ] Renewable fluctuation：按冻结协议。
- [ ] 当前 `gamma=1.4` 只作诊断 probe，不得混入正式场景图。

## P1 正文删减/降权
- [ ] Exact Dominance、Sparse Cuts、memory compression、逐轮 cut 日志统一压到“算法可计算性与验证”。
- [ ] Q4 前半正文的篇幅优先给“数据异构 -> 联合耦合必要性”，不是给求解器细节。
- [ ] 流程图中 6-region multi-cut 只保留小标签/一行 `Q(L)=sum_r Q_r(L_r)`，不塞完整公式块。

## WRITER 验收
- [ ] 读者在看到 Benders 之前已经理解 Q2->Q3 顺序拼接为什么可能错。
- [ ] 读者能从 Q4-A 看见“没有单一最佳 Region”。
- [ ] 正文明确区分“题面角色标签”和“实际数值结构”。
- [ ] Cost/Carbon 不加权的理由来自真实 Price/Carbon 数据关系，而非写作偏好。
- [ ] Q4 创新表述优先为“数据结构驱动的计算—储能—电网联合耦合”，Benders+CG 是可计算性手段。
