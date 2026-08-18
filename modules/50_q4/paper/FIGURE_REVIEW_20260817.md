# Q4 绘图审核与冻结门禁（2026-08-18更新）

本文件规定 Q4 canonical 联合优化完成后的正文图优先级。当前 `region_multicut_v1` 已完成两轮 final-pool `Cost -> Wait -> Latency` 再认证，50k canonical 端点已经可用于结果图；但题目正式场景尚未完成，因此整问仍是 `FINISHED_DRAFT`，不是 `FROZEN + CHECKED`。

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

## 正文主图必须服务三条线

1. **为什么必须联合优化**：区域优势错位、计算柔性与储能柔性争用同一新能源、顺序 Q2->Q3 会失真；
2. **算法为什么可信**：40-task exact + Benders/CG/full-domain pricing + final-pool recertification；
3. **联合优化到底改变了什么**：Q2 的高 workload 调整需求在 Q4 中被 BESS 柔性大幅替代，最终 Wait=0、migration=0.122%。

---

## P0 主图1：六区域算力—网络—能源—储能结构矩阵

必须展示原始/标准化但**不加权汇总**的区域特征：

- AvailableGPU；
- PUE；
- RT/低时延可达性；
- StorageCapacity；
- MaxCharge/MaxDischarge；
- SellLimit；
- Price/Carbon 的代表统计；
- baseline Curtailment。

图应让读者直接看见：

`低时延优势 != 算力优势 != PUE优势 != 储能/售电优势`。

不得构造区域综合得分、AHP/熵权或把 E/F 直接标成“绿色最优区”。附件六区域逐时 AvailableRenewable 数值相同。

## P0 主图2：顺序 Q2->Q3 失真 probe

用 3 个真实 RT、8 个 E/F placement 的小规模 probe：

- 冻结 BESS 的 Q2 static marginal 会显示迁 F 约节约 `3613.67 CNY`；
- 每个 placement 重新求真实 BESS recourse 后，8 个组合的最优能源成本相同；
- 此时低 latency 的 E placement 更优。

图中直接标：

`Q2 static marginal != Q4 post-BESS recourse`。

这张图是“为什么不能固定 Q2 后再跑 Q3”的最直接证据。

## P0 主图3：两类柔性争用并替代同一新能源

机制图核心变量：

`H_rt(x)=AvailableRenewable_rt-FacilityLoad_rt(x)`。

同一时空新能源余量可：

- 被迁入 workload 当期消纳；
- 进入 BESS 跨时段释放。

最终结果必须在图注或旁边指出：在当前附件数据下，两类柔性不仅互补，而且表现出强替代关系——储能柔性吸收了绝大部分原本由 workload 时间/空间调整承担的调节需求。

## P0 主图4：50k final-pool 字典序再认证

现在可以正式制作。

建议双面板或三阶段表图：

### (a) Sweep 1 / Sweep 2 anchors

- Cost：`-459340688.8007043 CNY`，两轮一致；
- Wait：`0 h`，两轮一致；
- Latency：`250860 ms`，两轮一致。

### (b) closure evidence

- active columns：137139 -> 137158 -> 137158；
- Latency Sweep1 新增 19 列，Sweep2 新增 0；
- final cuts=1173；
- min missing reduced cost=0；
- max region Benders violation=0。

### (c) 最优性边界

同时给出：

- Latency LP LB=`250469.954579 ms`；
- integer UB=`250860 ms`；
- relative gap≈`0.1555%`。

图注必须写“best-known integer representative / final-pool recertified”，不写 global optimum。

## P0 主图5：Q2-only vs Q3-only vs Q4-joint

**accounting 统一后才允许冻结。**

这一张应成为 Q4 最重要的最终结果图之一。至少比较：

- Cost；
- Carbon；
- migration；
- Wait；
- Latency；
- RenewableUtilization；
- regional PeakNetImport。

重点突出已经确认的 workload 侧变化：

- Q2 Cost-primary migration≈74.896%，mean wait≈20.475 h；
- Q4 migration=0.122%，Total/Mean/Max Wait=0。

结果解释：不是 Q4 “不需要 workload flexibility”，而是 BESS 时间柔性使绝大部分 workload 时间调整不再必要，只剩少量空间修正。

Q3 E1 与 Q4 表面成本差 `~122897.76 CNY` 在 accounting 未统一前不得画成正式 synergy 数字。

## P0 主图6：题目正式场景

必须最终覆盖：

1. Carbon constraints；
2. electricity-price mechanisms；
3. renewable fluctuation scenarios。

每个场景都必须是 joint reoptimization，不得固定 canonical workload 只重算 Energy LP。

历史 `gamma=1.4` 只能保留 diagnostic probe，不能放在“正式场景结果”标题下。

---

## 算法/验证图保留项

### 计算—能源耦合流程图
保留，但它只是 mechanism figure，不能替代区域结构数据图。

### Benders + Exact CG 流程图
保留：Restricted Master -> 6-region Energy recourse -> multi-cut -> exact pricing。可注明隐式完整域约 `2.33e8` placements。

### 40-task exact benchmark
保留为 validation badge/小图或表，避免占主图中心。它证明算法逻辑，不外推成 50k global integer certificate。

### Region multi-cut convergence
可放次级图/附录。现在 final result 已经比“每轮 violation 曲线”更重要；若正文篇幅紧张，优先保留 final-pool recertification 图而不是长收敛曲线。

## 禁止事项

- 删除旧 restricted-pool `total wait=378199 h / max wait=1171 h` 的正式展示；
- 不把昨夜 MemoryError/恢复过程当论文结果图；
- 不把 `MIP gap=0` 单独画成“全局整数最优”；
- 不把 Q2 高迁移率直接解释为 Q4 应高迁移；
- 不把 Q3/Q4 未统一 accounting 的绝对成本直接做柱图；
- 不新增六指标综合分。

## 推荐最终图序

1. Q4 总体流程图；
2. **区域优势错位结构矩阵**；
3. **顺序 Q2->Q3 失真 probe / 两类柔性耦合机制**（可合并）；
4. Benders + Exact CG 算法图；
5. **50k final-pool recertification**；
6. **Q2/Q3/Q4 unified comparison**；
7. **Carbon / price / renewable 正式场景**。

统一叙事：

`区域与任务数据冲突 -> 顺序优化会失真 -> 联合模型 -> 完整域求解闭合 -> 储能替代大部分 workload 调节 -> 场景下检验该机制是否保持`。
