# Q4 绘图审核与冻结门禁（2026-08-17）

本文件规定 Q4 在算法尚未最终闭合时允许制作/冻结的图，不改变 Q4 优化模型、Benders/CG 逻辑或结果状态。

## 当前定位

Q4 的正文图必须服务于两条主线：
1. `计算排程 -> FacilityLoad -> Energy recourse` 的联合耦合；
2. `Cost -> Wait -> Latency` 字典序求解及其 Benders + exact pricing 证据。

当前 50k Latency 阶段仍在 region multi-cut Benders 闭合过程中，因此任何 50k 最终 QoS 数字图、最终调度图、最终 Cost/Wait/Latency 对比图都不得冻结。

## 现在可以制作的图

### Q4-1 计算—能源耦合流程/机制图
- placement `x_irs` -> overlap `ω_ist` -> AI IT Load -> Facility Load -> Energy LP `Q(L)`；
- 只表达模型结构，不依赖未冻结结果。

### Q4-2 Cost stage 的 Benders + Exact CG 算法图
- Restricted Master；
- Energy LP 与 dual cut；
- full implicit-domain exact pricing；
- negative reduced-cost column 回到 Master；
- Cost stage closed。
- 可注明完整隐式合法域约 `2.33e8` placements，但不得将 50k 当前可行 UB 写成“全局整数最优”。

### Q4-3 字典序三 Stage 流程图
- Stage 1 `min Cost`；
- Cost cap；
- Stage 2 `min Total Wait` + full-domain Wait repricing；
- Wait cap；
- Stage 3 `min Total Latency` + full-domain Latency repricing；
- 显式注明“无主观加权”。

### Q4-4 40-task exact benchmark 图
只有已由 exact joint / explicit full-domain 真源确认的结果可画：
- 3139 legal placements；
- Cost exact benchmark；
- `Cost -> Wait -> Latency` 的 40-task exact QoS 结果。
该图用于证明算法设计，不外推为 50k 全局整数最优。

## 50k 算法闭合后再制作

### Q4-5 Region multi-cut convergence
建议画：
- X：Benders round；
- 总 violation；
- 分区 violation A–F（可用 log 纵轴/或只突出活跃区域）；
- full-domain pricing 触发轮次用竖线标记。
作用：展示为什么 single aggregate cut 弱、region multi-cut 如何利用 `Q(L)=sum_r Q_r(L_r)` 的真实可分结构。

### Q4-6 50k Cost/Wait/Latency 最终字典序结果
仅在三个 Stage 都通过：
- full-domain pricing 无负 reduced-cost column；
- region Benders violation 进入最终门禁；
- hard constraints PASS；
- final schedule / summary 生成；
之后才能冻结。

## 禁止事项

- 不画/不冻结旧 restricted-pool 的 50k QoS 结果；
- 不把旧 `max wait=1171h`、`total wait=378199h` 当最终 Q4 结论；
- 不把当前中间 Benders violation 或 round 120 临时排程当最终结果；
- 不把 `gamma=1.4` 诊断压力点包装成正式场景；
- 不写“50k global integer optimum proved”除非存在真实 certificate；
- 不为了画图新增权重、Cost cap、候选域截断或任意等待窗。

## 正文最终叙事目标

`联合耦合结构 -> Benders/CG求解证据 -> Cost/Wait/Latency字典序 -> exact benchmark -> 50k可扩展结果`

Q4 图应突出算法结构与证据链，不追求“图多”。
