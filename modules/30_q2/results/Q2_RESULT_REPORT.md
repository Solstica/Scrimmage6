# Q2 动态边际调度结果报告

状态：`DRAFT / NEEDS_REVIEW`

## 1. 当前结果状态

旧 `q2_solver.py` 的单遍 Cost-only / Carbon-only 数值已被收敛性审计判定为**不能冻结**。原因不是硬约束失败，而是逐任务动态边际重分配存在明显路径依赖：完成一遍扫描后，后续任务的移动会改变 GPU/IT 与能源余量，从而可能为此前已处理任务重新创造更优 placement。

因此正式运行入口改为：

`modules/30_q2/code/q2_iterative_solver.py`

正式流程为：

`source-local reference -> feasibility repair -> repeated full scans -> convergence gate -> Cost/Carbon endpoint comparison -> hard audit`。

Q2 数学模型、完整合法域、任务 priority rule 与动态边际能源响应均不改变。

## 2. 旧单遍结果只保留为历史草稿

旧仓库 Cost-only 单遍结果：

- Cost = `1,593,353,325.29 CNY`；
- Carbon = `1,853,354.50 tCO2`；
- 相对附件参考状态降本 `11.5682%`、降碳 `9.3877%`；
- 新能源利用率 `37.4894%`；
- migration rate `57.348%`；
- max wait `2136 h`。

这些数值虽然通过当时的 GPU/IT/Facility/Grid/SLA/2406 审计，但属于**单遍、固定 warm start** 的可行草稿，不再用于正文定稿，也不能继续用于 Cost--Carbon 交叉损失结论。

## 3. 独立收敛性复核

使用六份原始附件、相同任务 priority 和相同动态边际规则，从 `SourceRegion + ArrivalHour` 参考状态开始重复完整扫描。参考状态可重构附件 AI IT，但存在 44 个 GPU 超容量 region-hour，因此第一遍同时承担 feasibility repair。

### Cost-primary

| Pass | Cost / CNY | Carbon / tCO2 | Mean wait / h | P95 / h | Max wait / h | Migration |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1,562,972,727.00 | 1,833,942.57 | 10.830 | 38 | 2022 | 75.146% |
| 2 | 1,556,114,268.08 | 1,827,546.45 | 17.179 | 67 | 2022 | 75.086% |
| 3 | **1,554,958,103.85** | **1,826,451.48** | **18.915** | **76** | **2022** | **75.026%** |

Pass 1->2 的成本改善约 `0.4388%`；Pass 2->3 约 `0.0743%`。

### Carbon-primary

| Pass | Cost / CNY | Carbon / tCO2 | Mean wait / h | P95 / h | Max wait / h | Migration |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1,564,876,940.77 | 1,822,051.46 | 10.868 | 35 | 1644 | 75.592% |
| 2 | 1,558,908,225.56 | 1,816,179.29 | 16.499 | 62 | 2274 | 75.640% |
| 3 | **1,557,745,700.93** | **1,815,207.88** | **17.693** | **70** | **2158** | **75.610%** |

Pass 1->2 的碳排改善约 `0.3223%`；Pass 2->3 约 `0.0535%`。

因此当前正式停止规则取：

`(J_{k-1}-J_k)/|J_{k-1}| < 1e-3`。

独立复核 trace 位于 `results/q2_independent_convergence_audit_20260817.csv`。这些数值用于证明单遍不足、确定停止协议并交叉检查 canonical 重跑；正式 registry 仍需由新入口重新生成。

## 4. Cost--Carbon 关系的当前判断

相同初始化与相同收敛协议下：

- Carbon-primary 相比 Cost-primary 多花约 `2.788e6 CNY`，约为 Cost-primary 总成本的 `0.1793%`；
- Cost-primary 相比 Carbon-primary 多排约 `11243.6 tCO2`，约为 Carbon-primary 碳排的 `0.6194%`。

成本与碳仍总体同向，但旧单遍报告中的 `0.0667% / 0.0343%` 不能继续使用。正式 Q2 仍优先采用“成本主目标 + 碳排同步评价/必要时约束”的组织方式，待 canonical 收敛端点重算后再冻结。

## 5. 新版审计要求

正式 endpoint 必须同时满足：

- 50000/50000 任务覆盖；
- 重复完整扫描达到 `relative_tol=1e-3`；
- 末遍 fallback=0；
- GPU-hour、IT、Facility、GridImport/GridExport 全部通过；
- SLA 通过；
- RT 显式 `StartHour=ArrivalHour`；
- 每个任务 `FinishHour<=LatestFinishHour`；
- `FinishHour<=2406` 且 2406 无计算占用；
- 统一能量平衡残差 `<=1e-3 MW`；
- Cost-primary 与 Carbon-primary 使用同一 start 与同一收敛协议。

旧最终审计只显式检查 2406 的缺口已经在 `q2_iterative_solver.py` 中补为逐任务 `LatestFinishHour` 审计。

## 6. 等待时间的解释边界

重复扫描降低 Cost/Carbon 时，Batch/Training 的平均与 P95 等待可能增加；这反映 Q2 只释放计算侧时空柔性并以能源目标为主的代价。Q2 不增加人为最大等待窗口，也不借助权重把极端等待隐藏掉。等待均值、P95、最大值与按 TaskType 分布必须如实报告；系统级 QoS 与 Cost 的正式权衡由 Q4 联合模型处理。
