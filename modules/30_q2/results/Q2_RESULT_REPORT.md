# Q2 动态边际调度结果报告

状态：`DRAFT / NEEDS_REVIEW`

## 1. 正式求解协议

Q2 仍采用 **Carbon-Aware Spatiotemporal Workload Scheduling**。数学模型、完整合法 `(task,region,start)` 域、任务 priority rule 与动态边际能源响应均未改变。

旧单遍 `q2_solver.py` 已降级为数值 kernel / 历史复现入口；正式运行使用：

`modules/30_q2/code/q2_iterative_solver.py`

流程为：

`source-local reference -> feasibility repair -> repeated full scans -> convergence gate -> Cost/Carbon endpoint comparison -> hard audit`。

停止条件固定为：

`(J_{k-1}-J_k)/|J_{k-1}| < 1e-3`。

## 2. canonical Cost-primary 端点

从附件 source-local immediate 参考状态启动。该参考状态可精确重构附件 AI IT，但包含少量 GPU 超容量 region-hour，因此第 1 遍同时承担 feasibility repair。

| Pass | Cost / CNY | Carbon / tCO2 | Mean wait / h | P95 / h | Max wait / h | Migration |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1,562,872,479.39 | 1,833,672.65 | 14.327 | 42 | 2054 | 75.054% |
| 2 | 1,556,268,582.43 | 1,827,611.80 | 19.049 | 71 | 2017 | 75.062% |
| 3 | **1,555,371,304.13** | **1,826,774.35** | **20.475** | **76** | **2016** | **74.896%** |

Pass 2->3 成本相对改善为 `0.05766%`，低于 `0.1%` 门槛，因此第 3 遍收敛。

相对附件参考状态：

- 成本降低 `246,415,568.56 CNY`，降幅 **13.6762%**；
- 碳排减少 `218,593.12 tCO2`，降幅 **10.6872%**；
- 新能源利用率由 `32.8464%` 提升至 **37.2921%**；
- 新增新能源直接消纳 / 弃电减少 `513,260.57 MWh`；
- 迁移率 **74.896%**，其中 RT 合法迁移 `11,685` 个；RT 全部保持到达即开工。

## 3. canonical Carbon-primary 端点

| Pass | Cost / CNY | Carbon / tCO2 | Mean wait / h | P95 / h | Max wait / h | Migration |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1,564,578,141.38 | 1,821,562.90 | 13.264 | 46 | 1893 | 75.550% |
| 2 | 1,559,285,978.50 | 1,816,461.36 | 19.793 | 76 | 2149 | 75.732% |
| 3 | **1,558,153,356.53** | **1,815,531.61** | **20.959** | **83** | **2034** | **75.706%** |

Pass 2->3 碳排相对改善为 `0.05118%`，低于 `0.1%` 门槛，因此第 3 遍收敛。

相对附件参考状态：

- 成本降低 **13.5218%**；
- 碳排减少 `229,835.87 tCO2`，降幅 **11.2369%**；
- 新能源利用率 **37.3129%**。

## 4. Cost--Carbon 端点关系

两种模式使用相同初始化、相同完整合法域与相同 `relative_tol=1e-3`。

- Carbon-primary 相比 Cost-primary 多花 `2,782,052.40 CNY`，仅占 Cost-primary 总成本 **0.1789%**；
- Cost-primary 相比 Carbon-primary 多排 `11,242.75 tCO2`，占 Carbon-primary 碳排 **0.6193%**。

因此成本与碳排在本题数据上**总体高度同向但并非完全退化为同一目标**。Q2 代表策略继续采用 Cost-primary，并用 Carbon-primary 作为端点对照；不引入人工 Cost/Carbon 加权和。若后续初始化稳健性检查改变这一关系，再回到 DRAFT 复核。

## 5. 硬约束与能量审计

Cost-primary 与 Carbon-primary 最终端点均满足：

- `50000/50000` 任务覆盖；
- 最后一遍 fallback = 0；
- GPU-hour、IT、Facility 容量 PASS；
- GridImport / GridExport PASS；
- SLA PASS；
- RT `StartHour=ArrivalHour` PASS；
- 逐任务 `FinishHour<=LatestFinishHour` PASS；
- `FinishHour<=2406`，2406 无计算任务占用；
- 统一能量平衡最大残差约 `2.004e-4 MW`，低于 `1e-3 MW` 门槛。

Cost-primary 最大 GPU 容量浮点超差仅 `1.14e-13 GPU-hour`；Carbon-primary 为 `4.55e-13 GPU-hour`，属于数值零。

## 6. removal-dependent 修正

旧实现会在“移除当前任务后能源状态暂时无效”时直接锁死该任务。新版允许与原时段部分重叠、能够修复这些小时能源边界的合法候选。

reference-start 第 1 遍中 Cost/Carbon 分别观察到 `99 / 120` 个 removal-dependent 任务；第 2、3 遍均为 0。最终端点不再依赖旧 `removal_locked` 规则。

## 7. 服务代价与解释边界

Cost-primary 最终：

- mean wait = `20.475 h`；
- P95 wait = `76 h`；
- max wait = `2016 h`。

Carbon-primary 最终：

- mean wait = `20.959 h`；
- P95 wait = `83 h`；
- max wait = `2034 h`。

这些等待均满足任务自己的 LatestFinish，当前不是硬约束错误。Q2 不增加人为 24h/48h 最大等待窗去隐藏这一代价；正式写作应说明：能源导向时空调度会使用 Batch/Training 的长时间柔性换取弃电缓解、降本与减碳，而系统级 Cost--QoS 正式权衡留给 Q4。

在结果冻结前仍需对 3--5 个极端等待任务做逐任务样例审计，确认其 Arrival、Start、Slack、ExecutionRegion 和能源机会解释一致。

## 8. 当前还不能升级 FROZEN 的原因

本轮 reference-start canonical 端点已收敛并通过全部硬约束，但当前仍保持 `DRAFT / NEEDS_REVIEW`，原因是还缺两项最终验证：

1. 用 `--start previous` 做初始化稳健性检查，确认启发式路径依赖不会实质改变 Cost/Carbon 结论；
2. 完成极端等待任务样例审计和人工口径复核。

上述两项通过后可升级 `VALIDATED`；只有 registry 达到 `FROZEN + CHECKED` 后才能进入正式正文。
