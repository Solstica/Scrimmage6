# Q2 计算柔性可利用上界探针（2026-08-17）

状态：`DRAFT / NEEDS_REVIEW`

目的：给 Q2 一个不依赖启发式算法本身的 `flexibility headroom` 参照，回答“当前 SFETA 获得了附件理论可利用柔性的多少”，避免只报单个算法降幅。

## 1. 上界构造

保持 Q2 的题目边界：储能充放电、购售电策略不作为 Q2 决策；使用 baseline-referenced 增量能源口径。

对 BatchInference 与 AITraining 做诊断性连续松弛：

- 保留各 SourceRegion×TaskType 的总 IT 能量；
- 保留该 SourceRegion×TaskType 的完整 SLA 合法目标区域；
- 保留目标区域逐小时 GPU、IT、Facility 容量；
- 放松单任务不可拆分、非抢占、Arrival/LatestFinish 等逐任务时间约束。

该 fluid relaxation 只用于理论 headroom，不是可执行排程。

## 2. Flexible workload 规模

- BatchInference IT energy = `76,909.78 MWh`；baseline facility contribution = `101,371.97 MWh`；
- AITraining IT energy = `643,766.19 MWh`；baseline facility contribution = `825,622.45 MWh`；
- 两类合计 IT energy = `720,675.97 MWh`；baseline facility contribution = `926,994.42 MWh`。

这再次说明 Training 是 Q2 主要可调能源载体。

## 3. removal-side 理论收益上界

在 Q2 baseline-referenced 响应中，若从原 `(r,t)` 移走 facility load `z`，供负荷购电最多下降 `min(z,G0[r,t])`。因此得到一个不依赖新放置位置的绝对 removal-side 上界：

`UB_cost = sum Price[r,t] * min(FlexibleFacilityBaseline[r,t], G0[r,t])`

`UB_carbon = sum CI[r,t] * min(FlexibleFacilityBaseline[r,t], G0[r,t])`

结果：

- Cost saving upper bound = `342,323,537.51 CNY`；
- Carbon saving upper bound = `302,280.05 tCO2`。

按类型单独看：

- Training：Cost headroom `290.84 million CNY`，Carbon headroom `257,475 tCO2`；
- Batch：Cost headroom `52.76 million CNY`，Carbon headroom `45,647 tCO2`。

按类型分别计算的 headroom 不应简单相加解释，因为二者会竞争同一 baseline `G0`。

## 4. “重新放置不增加购电”可行性检查

进一步解一个 spatial-SLA + GPU/IT/Facility capacity 保留的 divisible-flow feasibility LP，要求新 fluid placement 满足：

`PUE[r] * z_new[r,t] - FlexibleFacilityBaseline[r,t] <= Curtailment0[r,t]`

即任一 `(r,t)` 的净新增 facility load 不超过 baseline curtailment，从而不会触发正的 `DeltaGridPurchase`。

结果：**可行**。

这意味着在放松任务时间/不可拆分约束后，附件存在足够的时空弃电与容量承接全部 Batch+Training 工作量；Q2 的真正限制主要来自任务级 temporal/deadline/nonpreemptive 约束和构造算法，而不是总量意义上的绿色承载不足。

## 5. 与当前旧草稿的距离

旧静态 SFETA 草稿（尚未按动态边际规则重跑）：

- Cost saving ≈ `132,192,823.42 CNY`；
- Carbon saving ≈ `127,153.98 tCO2`。

相对于上述 removal-side headroom：

- Cost capture ≈ `38.62%`；
- Carbon capture ≈ `42.06%`。

**这些 capture 只用于说明旧草稿仍有显著 headroom，不能作为最终算法质量结论。**新版动态边际 SFETA 重跑后必须重新计算。

## 6. 建模影响

建议 Q2 正文/评价增加：

`FlexCapture_cost = ActualCostSaving / UB_cost`

`FlexCapture_carbon = ActualCarbonSaving / UB_carbon`

并明确 UB 是 relaxed upper bound，不是可执行 schedule。

该指标能回答：复杂调度实际获取了附件中多少可利用计算柔性，而不是仅展示“下降了多少百分比”。

结果见 `modules/30_q2/results/q2_flexibility_headroom_20260817.csv`。
