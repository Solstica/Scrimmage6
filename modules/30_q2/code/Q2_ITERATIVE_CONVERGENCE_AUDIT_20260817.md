# Q2 重复完整扫描收敛审计（2026-08-17）

状态：`DRAFT / NEEDS_REVIEW`

## 1. 为什么需要修改正式求解流程

当前 `q2_solver.py` 的动态边际候选评价本身保留：对任务完整合法 `(region,start)` 域，依据当前排程状态计算 `DeltaCurtailment / DeltaGridPurchase / DeltaCost / DeltaCarbon`，再按 Cost-primary、Carbon-primary 或动态弃电优先的确定性字典序选择候选。

问题出在求解协议：旧正式运行固定从 `q2_schedule_0_2405.csv` 开始，只做一遍完整任务扫描。逐任务重分配是路径依赖的；后处理任务改变 GPU/IT 与能源余量以后，可能为此前已经扫描过的任务重新创造更优 placement。单遍结果不能视为算法稳定端点。

因此正式 Q2 改为：

`source-local reference / feasibility repair -> repeated full dynamic-marginal scans -> convergence gate -> Cost/Carbon endpoint comparison -> hard-constraint audit`。

这只增加外层重复扫描，不改变 Q2 数学模型、任务 priority rule、动态边际能源响应或 Cost/Carbon 目标结构。

## 2. 原始附件独立复核

使用六份原始附件独立重算得到：

- 任务数 50,000；
- 完整合法 `(task,region,integer-start)` 候选约 `233,375,201`；
- source-local immediate 参考状态可将 `Baseline_AI_IT_Load_MW` 重构到约 `3.33e-7 MW`；
- 该参考状态并非 GPU 硬约束可行解：共有 44 个 region-hour 超过 GPU 容量，因此第一遍扫描同时承担 feasibility repair；
- Batch/Training 的 `LatestFinishHour` 均为 2406；RT 必须到达即开工，并满足其自身 `LatestFinishHour`。

## 3. 独立重复扫描结果

### Cost-primary

| Pass | Cost / CNY | Carbon / tCO2 | Mean wait / h | P95 / h | Max wait / h | Migration |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1,562,972,727.00 | 1,833,942.57 | 10.830 | 38 | 2022 | 75.146% |
| 2 | 1,556,114,268.08 | 1,827,546.45 | 17.179 | 67 | 2022 | 75.086% |
| 3 | 1,554,958,103.85 | 1,826,451.48 | 18.915 | 76 | 2022 | 75.026% |

Pass 1->2 的成本相对改善约 `0.4388%`；Pass 2->3 约 `0.0743%`。

### Carbon-primary

| Pass | Cost / CNY | Carbon / tCO2 | Mean wait / h | P95 / h | Max wait / h | Migration |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1,564,876,940.77 | 1,822,051.46 | 10.868 | 35 | 1644 | 75.592% |
| 2 | 1,558,908,225.56 | 1,816,179.29 | 16.499 | 62 | 2274 | 75.640% |
| 3 | 1,557,745,700.93 | 1,815,207.88 | 17.693 | 70 | 2158 | 75.610% |

Pass 1->2 的碳排相对改善约 `0.3223%`；Pass 2->3 约 `0.0535%`。

因此本轮采用

`(J_{k-1}-J_k)/|J_{k-1}| < 1e-3`

作为完整扫描停止门槛。独立结果仅用于证明单遍不足和确定停止协议；正式 registry 数值必须由仓库 canonical solver 重新生成。

## 4. Cost--Carbon 结论需要重算

在相同 reference start 与相同停止协议下：

- Carbon-primary 相比 Cost-primary 多花约 `2.788e6 CNY`，约为 Cost-primary 总成本的 `0.1793%`；
- Cost-primary 相比 Carbon-primary 多排约 `11243.6 tCO2`，约为 Carbon-primary 碳排的 `0.6194%`。

成本与碳仍总体同向，但旧单遍结果中的 `0.0667% / 0.0343%` 交叉损失受到初始化与单遍扫描影响，不能继续作为定稿依据。

## 5. 代码修正

正式入口改为 `q2_iterative_solver.py`：

1. 默认从附件 `SourceRegion + ArrivalHour` 参考状态开始；第一遍允许承担资源可行性修复；
2. 保留 `RegionCount -> Slack -> GPUHour` priority；
3. 每遍扫描仍枚举完整合法空间与整数开工域；RT 显式固定 `StartHour=ArrivalHour`；
4. 重复扫描，直到主目标相对改善小于 `1e-3`；
5. 每遍输出 convergence trace；
6. 正式 PASS 同时要求末遍 fallback=0 与全部硬约束通过；
7. 最终 deadline 审计显式区分 `LatestFinishHour`、`finish<=2406` 与 RT immediate-start；
8. 旧 `removal_locked` 不再直接把任务锁死。若移除任务会暂时破坏 Q2 能源非负边界，只允许能够覆盖并修复这些小时的重叠候选继续参与比较。

旧 `q2_solver.py` 暂保留为单遍数值 kernel 与历史结果复现入口；正式结果不再直接由它单独生成。

## 6. 冻结门禁

Q2 结果进入 `FROZEN + CHECKED` 前至少满足：

- Cost-primary 与 Carbon-primary 使用相同 start 规则和相同 `relative_tol`；
- 两者 convergence trace 均满足停止门槛；
- 50000/50000 任务覆盖；
- GPU/IT/Facility、GridImport/Export、SLA、EarliestStart、逐任务 LatestFinish、RT immediate-start、2406、统一能量平衡全部 PASS；
- Cost/Carbon endpoint cross-loss 由收敛端点重新计算；
- 等待分布按 TaskType 报告，极端等待如实保留，Q2 不通过人为最大等待窗口隐藏能源导向调度的服务代价。
