# 第9题 SFETA 算法来源、命名与改造边界

状态：`DRAFT / NEEDS_REVIEW`

本文件记录 2026 Applied Energy 的 REPTA 原始算法机制、本题数据结构与拟采用的改造方向。正式论文引用前仍需在 references 分支登记原文文献并由当前实现验证算法结果。

## 1. 命名

当前候选名称：`SFETA` = **Spatio-temporal Flexibility and Energy-aware Task Assignment**，中文暂译“时空柔性—能源感知任务分配算法”。

不采用 `FETA` 作为新算法简称：FETA 已在既有 task-assignment 文献中被用于其他含义，容易与既有术语冲突。正式论文前仍需再次检查命名碰撞；若无更合适的成熟术语，保留 SFETA。

## 2. REPTA 原始机制（来源：Yang et al., Applied Energy 404, 2026, 127156）

原文完整三阶段结构为：

1. Stage I：排除 delay-tolerant tasks，先求一次 EHCO（electricity-heat coordinated optimization），得到发电源与购电的 preliminary scheduling；
2. Stage II：REPTA 只负责 delay-tolerant task dispatch，且为非迭代规则算法；
3. Stage III：固定 Stage II 得到的任务时空排程，再求一次 EHCO 得到最终能源调度。

REPTA 的 Stage II 又分两相：

- Phase A：优先让本地 delay-tolerant tasks 消纳本地 RES overproduction；
- Phase B：未分配任务若允许跨区，则搜索其他 DTC 的 RES overproduction；若仍无可用 RES，则分配到允许时间窗内最低电价的 DTC/时段。

因此 REPTA 不是三阶段框架的统称，而是 Stage II 的具体任务分配算法。

## 3. 本题为什么不能直接照搬 REPTA

第9题附件与原文场景存在结构差异：

- 本题任务有逐任务 ArrivalHour、Duration、LatestFinish、MaxLatency、GPU_Demand，可直接形成精确任务级时空可行域；
- network_latency 与 MaxLatency 给出硬 SLA gate，本题不要求带宽、迁移数据量、迁移能耗或迁移费用；
- 终极数据审计显示 `AvailableRenewable_MW` 六区域逐时相同，原 REPTA 所利用的跨区域 RES complementarity 在该字段中没有体现；
- D/E/F 允许售电，新增算力负荷可能消耗弃电、挤占原本可售新能源或触发新增购电，单纯比较 RES overproduction / buy price 不足以描述真实边际经济影响。

## 4. SFETA 当前拟改造的三处机制

### 4.1 任务级时空柔性，而不是只有 delay-tolerant 标签

对任务 i 定义合法区域集合与合法开始时间集合：

`R_i = {r | latency(source_i,r) <= MaxLatency_i}`

`T_i = {s | s >= EarliestStart_i, s + duration_i <= min(LatestFinish_i,2406)}`

候选集：`C_i = R_i × T_i`。

不得为了求解速度人为限定“最多延迟24h”“只看最近若干区域”等额外搜索域。只有由官方 SLA、deadline、单任务自身容量等可证明不可能的候选才能安全删除。

### 4.2 任务优先级使用可调度紧迫度

候选量、剩余 slack、GPU×Duration 等用于描述任务有多难安排。当前方向是先处理可行域较小/剩余松弛较小/资源压力较大的任务，再对其完整合法候选排序；不以任意加权和替代硬约束。

### 4.3 用能源边际机会状态替代单纯“RES最大/电价最低”

新增算力负荷的直接经济状态至少区分：

1. 消纳原本弃掉的新能源：边际电费约为 0；
2. 挤占原本可以出售的新能源：边际机会成本约为 SellPrice；
3. 需要新增电网购电：边际成本为 BuyPrice。

该状态需要在候选分配过程中动态更新，作用类似原 REPTA 的 `RESO` 更新，但适配本题购售电机制。

## 5. 四问与 SFETA 的关系

- Q1：不使用 SFETA。完成任务统计/预测，并建立基础规则调度机制；Q1 不是多目标优化问题。
- Q2：首次进入能源感知的任务时空分配，SFETA 作为主要候选算法。
- Q3：任务层冻结，只研究给定 Baseline AI IT load 下的储能/购售电/新能源响应；不应硬称 SFETA。
- Q4：将 Q2 的 SFETA 任务分配机制与 Q3 的能源/储能响应联合。是否采用进一步的分解算法由后续精确对照决定，不提前冻结。

## 6. 当前验证计划

- 用原始 REPTA 逻辑作为 baseline：local RES -> remote RES -> lowest buy price；
- 用 SFETA 替代 Stage II，并保持完整合法时空域；
- 对比成本、碳排、新能源利用率、任务完成率、等待、迁移量和计算时间；
- 做消融：去掉任务柔性排序、去掉 SellPrice opportunity cost 等，确认改造是否产生真实增益；
- 不以修改算法名称本身作为创新证据。
