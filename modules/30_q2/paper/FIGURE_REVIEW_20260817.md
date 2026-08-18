# Q2 绘图审核与正文筛选（2026-08-17，2026-08-18复核）

本文件只规定论文图的口径、去重和需要返工的地方，不改变 Q2 模型、canonical 排程或结果真源。

## 总体判断

截至 2026-08-18，`figures/` 下已经形成 Q2-1～Q2-5 五张主图：任务柔性三面板、收敛与初始化敏感性、分段能源边际响应、区域迁移热图、Cost–Carbon 端点关系。旧版“算法—结果图组”已基本齐全，但按当前论文已经升级的 **Data → Mechanism → Model** 主线，仍缺最关键的一个 P0 数据证据：附件本身存在强烈的“弃电—购电并存”时空错配。

当前正文图组不能只回答“算法怎么收敛、结果迁到哪里”，还必须先回答“为什么 Q2 有必要”。

## P0 修正

1. **RT 时间柔性口径**：数据层 `deadline slack` 可约为 0.5 h，但 Q2 对 RealTimeInference 有硬约束 `StartHour = ArrivalHour`，所以其**决策时间柔性严格为 0**。Q2-1 第二面板必须使用真正可调开始时间自由度；若沿用 Deadline Slack，则图题和注释必须明确“RT 的实际调度自由度仍为 0”。
2. **负荷增量—能源响应图的结论必须严格按分段模型解释**，不得写“负荷增量为负时，弃电和购电变化同步下降”。正式机制：
   - `0 <= ΔL <= C0`：先吸收原弃电，`ΔG=0`；
   - `ΔL > C0`：弃电耗尽后才增加购电；
   - `ΔL < 0`：先减少原有购电，购电降至 0 后继续降负荷会增加弃电。
   Q2-3 应标明“弃电吸收区 / 新增购电区 / 降负荷回退区”，不加无物理意义拟合线。
3. **Cost/Carbon 端点关系不得称 Pareto frontier**。当前只展示 Baseline、Cost-primary、Carbon-primary 与 previous-start 等代表点，没有系统扫描 Pareto 前沿。
4. **迁移热图不得把 E/F 等区域预先命名为‘绿色承接中心’**。附件六区域逐时 `AvailableRenewable` 完全相同；迁移承接差异来自 Curtailment、PUE、Price、Carbon、容量与 SLA 的联合结果。
5. **当前仍缺一张 P0 数据证据图：基准能源时空错配及低碳属性。**必须补，不能用算法收敛图替代。

## 必补 P0 数据证据图：基准能源时空错配及低碳属性

建议做一张双面板，正文位置应在 SFETA 算法和收敛图之前。

### (a) 弃电—购电并存的时空错配
必须直接展示两个已经核验的数据事实：

- 0–2399 h 共 `14400` 个 region-hour，其中 `13230` 个 region-hour **同时存在 Curtailment > 0 和供负荷 GridPurchase > 0**，占比：
  \[
  13230/14400 = 91.9\%.
  \]
- 累计弃电量约 `7.748e6 MWh`，Baseline AI Facility Energy 约 `0.951e6 MWh`，比值约：
  \[
  \frac{\text{Curtailment}}{\text{AI Facility Energy}}\approx 8.15.
  \]

图应让读者直接得到结论：Q2 的核心矛盾不是新能源总量不足，而是 **算力负荷与绿色能源严重时空错配**。

推荐表现：
- 左侧：六区域 `Curtailment` 与 `GridToLoad/GridPurchaseToLoad` 的聚合对比或 region-hour joint-status 图；
- 图内醒目标注 `91.9%`；
- 右侧或 inset 标出 `Curtailment / AI Facility Energy ≈ 8.15×`。

### (b) 弃电的低碳属性
展示附件中的数据关系：

\[
\operatorname{Corr}(Curtailment,CarbonIntensity)\approx -0.690\sim -0.849,
\]

\[
\operatorname{Corr}(Curtailment,AvailableRenewable)\approx 0.925\sim 0.995.
\]

推荐按六区域画 Curtailment–CarbonIntensity 散点/hexbin，或者 6 个相关系数点图；目标不是做新预测，而是证明“优先吸收弃电”通常也偏向低碳时段，从数据上解释为何不需要人工构造 Cost/Carbon/Renewable 主观加权分数。

如版面紧张，(a)(b) 必须合并为一张复合图，而不是删除 (a)。

## 当前五张图的审核结论

### Q2-1 任务柔性三面板 —— 保留，P0
- (a) 合法区域数；
- (b) 真正可调时间自由度；
- (c) GPU-hour。
- 作用：解释 SFETA 的任务优先级来自“空间受限、时间刚性、资源重量”。
- 验收：RT 的实际调度时间自由度必须为 0。

### Q2-2 收敛与初始化敏感性 —— 保留，但降为算法证据
- (a) Cost-primary reference-start vs previous-start；
- (b) Cost-primary 与 Carbon-primary 的收敛/端点变化。
- 作用：证明重复完整扫描收敛并揭示初始化路径依赖。
- 不允许绘制不存在的 Carbon previous-start 正式结果。
- 在新的 Data→Model 叙事中，该图应排在“能源时空错配”与“动态边际机制”之后或附近，不应作为第二张核心数据图抢在问题必要性之前。

### Q2-3 设施负荷扰动的分段能源边际响应 —— 保留，P0
- X：`ΔL`；
- Y：`ΔGridPurchase`、`ΔCurtailment`；
- 标注三段物理区域；
- 作用：Q2 模型机制核心图。

### Q2-4 SourceRegion -> ExecutionRegion 迁移热图 —— 保留，P1
- 6×6 矩阵，保留数值标签；
- 图注只描述真实迁移结构，不预设“新能源区”“绿色中心”等标签。

### Q2-5 Cost–Carbon 端点关系 —— 保留，P1
推荐至少包含：
- Baseline；
- Cost-primary reference-start；
- Carbon-primary reference-start；
- Cost-primary previous-start。

图注可量化：
- Carbon-primary 相对 Cost-primary 的成本代价约 `0.1789%`；
- Cost-primary 相对 Carbon-primary 的碳代价约 `0.6193%`。

若当前图中缺 Baseline 或 previous-start，应补齐。不得称为 Pareto frontier。

## 正文推荐最终图序

1. **Q2-1 任务柔性结构**；
2. **Q2-2 基准能源时空错配及低碳属性（新图，必须补）**；
3. **Q2-3 分段能源边际响应**；
4. **Q2-4 SFETA 收敛与初始化敏感性**；
5. **Q2-5 Source→Execution 迁移热图**；
6. **Cost–Carbon 端点关系**：篇幅允许时正文，否则与结果表配合或降为次级图。

图号可以在最终排版时重编号，不要求文件名立即跟随重命名。

## 次级/附录候选

- 逐时 FacilityLoad / GridPurchase / Curtailment / UsedRenewable：只有 Origin 实图视觉清晰时进正文，否则附录；
- 等待 Mean/P95 图：正文篇幅允许时加入；Max≈2016 h 用注释或审计表单列，不与 Mean/P95 同一线性柱图；
- 单独成本柱图、碳排柱图：删除或附录，避免和 Cost–Carbon 端点图重复。

## 最终统一叙事

Q2 图组应形成：

`任务柔性 + 基准能源错配 → 动态边际机制 → 迭代收敛 → 空间重构 → 双端点选择`

其中最不能缺的是：

\[
\boxed{91.9\%\text{ region-hour 同时弃电+购电，且累计弃电约为 AI Facility Energy 的 }8.15\text{ 倍}}
\]

这才是 Q2 的数据驱动必要性证据。禁止将旧 single-pass 结果或未统一 Hour-2406 accounting 的绝对成本混入最终冻结图。
