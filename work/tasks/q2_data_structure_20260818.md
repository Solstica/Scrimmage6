# Q2 数据结构驱动论文与作图任务（2026-08-18）

依据：`modules/30_q2/paper/DATA_STRUCTURE_PAPER_ENRICHMENT_20260818.md`。

本任务不改变 Q2 数学模型、SFETA、合法域、Cost/Carbon 目标结构；只负责把已经发现并已进入模型的数据关系补进正文与图。

## P0 正文必须补入的数据证据

- [ ] 在“能源层分析”开头加入基准能源错配事实：0--2399 h 共 14,400 region-hour，其中 13,230 / 14,400（约 91.9%）同时存在 `Curtailment>0` 与 `GridToLoad>0`。
- [ ] 同段加入累计量：Curtailment≈7,748,360.94 MWh，GridToLoad≈4,028,324.59 MWh，baseline AI facility energy≈950,773.63 MWh，`Curtailment / AI facility energy≈8.15`。
- [ ] 把上述事实解释为“计算负荷与绿色能源的时空错配”，作为 Q2 释放 workload 时空柔性的必要性证据。
- [ ] 将“六区 AvailableRenewable 逐时完全相同”提升为反直觉数据发现；明确不能按 E/F 文字标签构造绿色区域评分。
- [ ] 补写 `corr(Curtailment,CarbonIntensity)≈-0.690~-0.849` 与 `corr(Curtailment,AvailableRenewable)≈0.925~0.995` 的机制解释：弃电吸收天然具有低碳属性。
- [ ] 将 Price--Carbon 相关（Pearson≈0.578，Spearman≈0.613）与 Cost-primary / Carbon-primary 端点组织直接关联，解释为何不使用人工权重和。
- [ ] 将 Batch/Training 千小时级 slack 与 2016 h 最大等待放在同一逻辑中说明：极端等待是利用附件长 slack 的能源导向服务代价，不是 deadline/index bug。

## P0 必补数据图

### Q2-A 基准能源错配证据图
- [ ] 生成绘图 CSV：每区/系统 `Curtailment>0`、`GridToLoad>0`、二者同时发生的 region-hour 数量和比例。
- [ ] 生成绘图 CSV：累计 Curtailment、GridToLoad、AI facility energy；图中显式标注 `91.9%` 与 `8.15×`。
- [ ] 若采用复合图，增加六区 Curtailment 分布或小时空间极差；旁注 `AvailableRenewable_A(t)=...=AvailableRenewable_F(t)`。
- [ ] Origin 图标题只表达“基准能源时空错配”，不把 baseline 描述成优化最优状态。

### Q2-B 任务柔性结构三面板
- [ ] 空间柔性：按 TaskType 画 `|R_i|`。
- [ ] 时间柔性：画真正的可调 start 自由度；RT 必须显示为 0，不使用 deadline slack≈0.5 h 误导。
- [ ] 资源重量：GPU-hour。
- [ ] 图注明确排序 `|R_i|小 -> slack小 -> GPU-hour大` 来自数据，不是综合评分。

### Q2-C 分段边际能源响应
- [ ] 重做/复核 `DeltaL -> DeltaGridPurchase`。
- [ ] 重做/复核 `DeltaL -> DeltaCurtailment`。
- [ ] 标注“弃电吸收区 / 新增购电区 / 降负荷回退区”。
- [ ] 禁止使用“负荷下降时弃电和购电同步下降”这一错误解释。

## P1 强化图

### Q2-D 弃电—碳强度关系
- [ ] 生成六区相关图或散点/hexbin，至少表现 Curtailment vs CarbonIntensity。
- [ ] 另表现 Curtailment vs AvailableRenewable，支撑“高新能源富余 -> 高弃电 -> 通常更低碳”的数据链。

### Q2-E Cost/Carbon/初始化端点
- [ ] 同图放 Baseline、Cost-primary(reference)、Carbon-primary(reference)、Cost previous-start。
- [ ] 标注 Carbon-primary 对 Cost-primary 的成本代价约 +0.1789%，Cost-primary 对 Carbon-primary 的碳代价约 +0.6193%。
- [ ] 不称 Pareto front。

### Q2-F Source -> Execution 迁移矩阵
- [x] 已有 `图09_区域迁移矩阵.csv`。
- [ ] 按真实矩阵完成 Origin 图，结论只按实际承接关系写，不预设 C/E/F 为“绿色中心”。

## P1 图表删并
- [ ] 若 Q2-E 已存在，删除单独 Cost 柱图 + Carbon 柱图的正文重复展示。
- [ ] Mean/P95/Max wait 不用同一线性柱图；max=2016 h 只用标注或审计表说明。
- [ ] 四条 2406 h 全时序若过密，移附录；不能为了图多牺牲机制图。

## WRITER 验收
- [ ] 读者在 SFETA 算法出现前已经看到：任务柔性、91.9%弃电购电并存、8.15×绿色余量、弃电低碳属性。
- [ ] `DeltaG` 分段公式前有明确数据动机，而不是公式先行。
- [ ] 正文明确区分“原始 AvailableRenewable 空间相同”和“基准 Curtailment 空间不同”。
- [ ] Q2 最终创新表述优先写“数据驱动的完整域动态边际调度”，而不是只写“改进启发式算法”。
