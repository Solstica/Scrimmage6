# Q2 绘图审核与正文筛选（2026-08-17）

本文件只规定论文图的口径、去重和需要返工的地方，不改变 Q2 模型、canonical 排程或结果真源。

## 总体判断

当前 12 张候选图覆盖充分，但重复较多。正文应围绕“任务柔性依据 → 迭代收敛与路径依赖 → 动态边际能源机制 → 空间迁移 → Cost/Carbon 端点关系”压缩到约 5 张主图。

## P0 修正

1. **RT 时间柔性口径**：数据层 `deadline slack` 可约为 0.5 h，但 Q2 对 RealTimeInference 有硬约束 `StartHour = ArrivalHour`，所以其**决策时间柔性严格为 0**。原“时间余量中位数”图要么改名为 `Deadline Slack` 并显式备注 RT immediate-start，要么重算真正的可调开始时间自由度。
2. **负荷增量—能源响应图的结论必须改写**。不得写“负荷增量为负时，弃电和购电变化同步下降”。正式分段机制为：
   - `0 <= ΔL <= C0`：先吸收原弃电，`ΔG=0`；
   - `ΔL > C0`：弃电耗尽后才增加购电；
   - `ΔL < 0`：先减少原有购电，购电降至 0 后继续降负荷会增加弃电。
   图名建议改为“设施负荷扰动的分段能源边际响应”，标出弃电吸收区、购电边际区和降负荷回退区。
3. **等待分布图**：Mean/P95/Max 不应在同一线性柱图。Max≈2016 h 会压扁 Mean/P95。正文只画 Mean 与 P95，Max 用注释/虚线单列；极端合法等待由审计表支撑。
4. **Cost/Carbon 端点图去重**：三种端点成本柱图、碳排柱图、Cost–Carbon 散点三者重复。正文优先保留散点，并加入 Baseline 点；不得称为 Pareto 前沿。

## 正文推荐图组

### Q2-1 任务柔性三面板
- (a) 合法区域数；
- (b) 真正可调时间自由度/或明确命名的 Deadline Slack；
- (c) GPU-hour。
- 作用：解释 SFETA 排序为什么由“空间受限、时间刚性、资源重量”共同决定。

### Q2-2 收敛与初始化敏感性（双面板）
- (a) Cost-primary reference-start vs previous-start；
- (b) Cost-primary 与 Carbon-primary 的碳排收敛。
- 作用：同时证明重复完整扫描收敛、存在路径依赖、Cost/Carbon总体高度同向。

### Q2-3 设施负荷扰动的分段能源边际响应
- X：`ΔL`；
- Y：`ΔGridPurchase`、`ΔCurtailment`；
- 标注三段物理区域，不加拟合线。
- 作用：Q2 机制核心图。

### Q2-4 SourceRegion -> ExecutionRegion 迁移热图
- 6×6 矩阵，数值标签；
- 不预先写死“C/E 是承接中心”，由真实矩阵结果决定。

### Q2-5 Cost–Carbon 端点散点
- Baseline、Cost-primary、Carbon-primary、previous-start；
- 注明 Carbon-primary 相对 Cost-primary 的成本代价约 0.1789%，Cost-primary 相对 Carbon-primary 的碳代价约 0.6193%。
- 不使用“Pareto frontier”措辞。

## 次级/附录候选
- 逐时 FacilityLoad / GridPurchase / Curtailment / UsedRenewable：只有在 Origin 实图视觉清晰时进正文，否则附录；
- 等待 Mean/P95 图：正文篇幅允许时加入；
- 单独成本柱图、碳排柱图：删除或附录。

## 统一叙事

Q2 图组应形成：

`任务柔性依据 -> 完整扫描收敛 -> 动态边际能源机制 -> 空间重构 -> 双端点选择`

禁止将旧 single-pass 结果或未统一 Hour-2406 accounting 的绝对成本混入最终冻结图。
