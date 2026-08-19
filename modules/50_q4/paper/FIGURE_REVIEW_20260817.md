# Q4 绘图审核与冻结门禁（2026-08-18 21:30更新）

本文件规定 Q4 canonical 联合优化完成后的正文图优先级，并复核 `Q4_绘图报告.md` 的具体方案。当前 canonical 端点可用于正式结果图；Carbon / price / renewable 三类正式场景尚未完成，场景图不得提前进入结论。

## 当前 canonical 真结果

- Cost = `-459340688.8007043 CNY`；
- Total Wait = `0 h`；
- Total Latency = `250860 ms`；
- Mean Latency = `5.0172 ms`；
- migrated = `61 / 50000 = 0.122%`；
- active columns = `137158`；
- Benders cuts = `1173`；
- full-domain pricing min reduced cost = 0；
- max region Benders violation = 0；
- hard audit PASS；
- Latency full-domain LP lower bound = `250469.954579 ms`，integer representative = `250860 ms`，relative gap≈`0.1555%`。

不得把 `restricted MIP gap=0` 写成“full-domain integer gap=0”或“50k global integer optimum proved”。

## 正文图必须服务三条线

1. **为什么必须联合优化**：区域优势错位、计算柔性与储能柔性争用同一新能源、顺序 Q2->Q3 会失真；
2. **联合模型为什么可信**：40-task exact、完整域 pricing、真实 Energy recourse、最终再认证；
3. **联合优化改变了什么**：Q2 的高 workload 调整需求在 Q4 中被 BESS 柔性大幅替代，最终 Wait=0、migration=0.122%。

---

## P0 图A：六区域算力—网络—能源—储能结构矩阵——保留，但必须改表达

图型可继续使用热图，但不能把不同方向指标直接标准化后都解释为“越大越好”。

推荐列分块：

- 算力：AvailableGPU（↑）；
- 网络：RT/低时延可达性（↑）、代表时延（↓）；
- 能效：PUE（↓）；
- 储能/售电：StorageCapacity、MaxCharge/Discharge、SellLimit（↑）；
- 能源经济：Price、CarbonIntensity（↓）、baseline Curtailment（只表示可消纳空间，不直接定义为“优势”）。

二选一：

1. **结构标准化矩阵**：直接画各指标 z-score，并在列名加 `↑/↓`，不统一解释颜色为“优劣”；
2. **优势方向矩阵**：仅对明确的 cost-type 指标反号，使颜色统一表示“更有利”，但图注必须说明只是方向统一，未做任何加权、综合评分或 AHP/熵权。

图A必须保持“无综合区域得分”。原始数值另放配套表或附录。

## P0 图B：顺序 Q2->Q3 失真 probe——当前绘图报告漏掉，必须补

这是 Q4 最有解释力的数据/机制图之一，不应被迁移矩阵或求解器闭合图替代。

建议双面板：

- (a) 3 个真实 RT、8 个 E/F placement 在 Q2 static marginal 下的成本差，标出“全部迁 F 约节约 3613.67 CNY”；
- (b) 每个 placement 重新求 BESS/Energy recourse 后的真实能源最优成本，8 个组合相同，同时标出 E 方案 latency 更低。

图中直接写：

`Q2 static marginal != Q4 post-BESS recourse`

这张图回答“为什么不能先固定 Q2 最优排程再跑 Q3”。

## P0 图C：迁移结构——C1/C2 可合并，但 C1 必须屏蔽对角线

### C1 区域迁移矩阵

canonical 只有 61 个迁移任务。如果把 50000 个全部任务计入 6x6 矩阵，对角线约 49939 个本地任务会完全压死非对角信号。

因此正式热图必须使用：

- 仅 `Moved=1` 的 61 个任务；或
- 对角线 mask/置空，仅显示 off-diagonal moved counts。

图注写“迁移任务的源→目标分布”，不能叫“全部任务执行矩阵”。每格直接显示整数任务数。

### C2 不同任务类型迁移率

可以和 C1 做成同一复合图右侧小面板。建议同时标“迁移数/任务总数”和迁移率，避免 0.0x% 的极小百分比失去规模感。

## P1 图D：final recertification——不要把 D1、D2 都作为正文主图

当前 `Sweep 1 = Sweep 2` 的 Cost/Wait/Latency 三个锚点完全一致，Wait 又恒为 0；另外 min reduced cost 和 max Benders violation 最终也都是 0。把这些画成三张柱图/双Y图，视觉信息量很低。

更推荐：

- 正文使用一张**再认证证据表/证书卡片**：Sweep1、Sweep2、Cost、Wait、Latency、active columns、cuts、LP LB、integer UB、0.1555% gap；
- 若一定要图，只保留一个次级图：活动列/切数随再认证阶段变化，并在终点标 `RC=0, violation=0`；
- 完整 D1/D2 可放附录或模型检验，不占正文主图位置。

## P0 图E：联合优化的服务质量收益——重构当前 E1/E2

### 原 E1 “等待分布”不建议单独成图

50000 个任务全部 Wait=0，画一根 50000 的柱子没有信息增量。改成正文数字结论或合并到跨问比较：

`Q2 mean wait 20.475 h -> Q4 0 h`

### E1 建议改为 Q2 vs Q4 柔性替代双面板

- (a) migration：74.896% -> 0.122%；
- (b) mean wait：20.475 h -> 0 h；

必要时再用标注补 max wait：2016 h -> 0 h。

这是 Q4 最重要的结果图之一，直接支撑“储能柔性替代绝大部分 workload 时空调节需求”。

### E2 网络时延分布可保留

绝大多数任务不超过 5 ms、尾部很稀疏。普通线性计数柱图会被第一档支配，因此建议：

- 计数柱图 + 尾部 inset；或
- 精确 ECDF（不是平滑拟合），标 P95=5 ms、max=58 ms。

禁止用核密度/平滑曲线制造不存在的连续分布。

## P0 图F：正式场景六指标——当前只能保留模板

场景全部完成、统一 accounting 后再画。

不建议把六指标放进一个雷达图或一个双Y综合图。建议按场景族分面：

- Carbon constraints；
- electricity-price mechanisms；
- renewable fluctuation。

每个场景族优先展示**相对 canonical 的变化量/变化率**：

- Cost 因 canonical 为负值（净收益），优先画 `ΔCost`，避免原始负柱方向造成误读；
- Carbon、RenewableUtilization、PeakNetImport 各自独立尺度；
- Wait、Latency 单独面板。

不同场景族不要强行排成“同一横轴的一组类别”，因为它们代表不同机制。

`price_flat` 未完成前禁止使用运行中 DRAFT 数字。

## P0 统一排版修正

`Q4_绘图报告.md` 中“**双栏图宽约 180 mm**”与当前论文模板不一致。当前 A4 四边页边距均为 25 mm，正文最大宽度约：

`210 mm - 25 mm - 25 mm = 160 mm`。

因此：

- 正文全宽复合图建议按 `155--160 mm` 导出；
- 对应 LaTeX 使用 `\FigureDoubleWidth=1.00\textwidth` 或略小；
- 单图约 `0.60\textwidth`，对应约 95 mm；
- 180 mm 图会越出正文版心，不得作为最终导出宽度。

中文宋体、英文/数字 Times New Roman、坐标带单位、SVG/PDF 矢量优先的要求保留。

## 推荐最终正文图序

1. Q4 总体流程图；
2. **图A 区域结构错位矩阵**；
3. **图B 顺序 Q2->Q3 失真 probe + 计算/BESS耦合机制**；
4. Benders + 完整域列生成算法图（可压缩）；
5. **图E Q2 vs Q4 柔性替代结果**；
6. 迁移结构 / 时延分布（按篇幅二选一或组合）；
7. final recertification 证据表（优先表而非图）；
8. **图F 三类正式场景**。

40-task exact benchmark、cut 数/内存/收敛轨迹等属于算法验证，优先进入表格或附录，不与数据机制图争正文版面。
