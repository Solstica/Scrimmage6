# Q2 论文文字修订要求（2026-08-17）

状态：WRITER P0。本文档以 2026-08-17 新的重复完整扫描 canonical 结果为准，旧单遍 SFETA 数字全部退出正文。

## 总体定位

Q2 仍是“任务时空柔性 + 基准能源状态下动态边际能量响应”的大规模构造式调度问题。模型本体不更换；需要更新的是：

1. 求解算法从单遍改为外层重复完整扫描直到收敛；
2. 结果表全部替换为 canonical 收敛端点；
3. 加入多起点路径依赖与极端等待的模型评价；
4. 统一 Q2/Q3 的 Hour 2406 能源结算口径后再冻结绝对成本。

## P0-1 算法框必须改为重复完整扫描

当前正式入口：`modules/30_q2/code/q2_iterative_solver.py`。

论文算法结构写为：

`reference/previous feasible start -> full scan 1 -> full scan 2 -> ... -> convergence gate`。

停止条件：

`(J_{k-1}-J_k)/|J_{k-1}| < 1e-3`

且最后一遍必须满足 fallback=0、全部硬约束 PASS。

每次处理任务时，应表达真实实现逻辑：

1. 从当前排程暂时移除任务；
2. 基于 removal 后的当前残余负荷/能源状态；
3. 枚举完整合法 `(region,start)` 域；
4. 计算 `EnergyResponse(current+candidate)-EnergyResponse(current)`；
5. 按主目标选候选并更新状态。

禁止把它写回单遍静态贪心。

## P0-2 RT 规则必须修正

RT 的正式规则是：

`StartHour = ArrivalHour`

但允许在全部 SLA 合法区域之间迁移。不能再写“RealTimeInference 保持来源区域即时开工”。

canonical Cost-primary 中 RT 合法迁移 11,685 个。

## P0-3 canonical Cost-primary 数字

reference-start，3-pass 收敛：

- Cost = 1,555,371,304.1316478 CNY；
- 相对当前 Q2 0--2405 accounting reference 的成本降低 = 246,415,568.56023908 CNY；
- 当前口径降本率 = 13.6761773712%；
- Carbon = 1,826,774.354637248 tCO2；
- 减碳 = 218,593.12064679852 tCO2；
- 当前口径减碳率 = 10.6872297173%；
- Renewable utilization = 37.2921190163%；
- migrated = 37,448；migration rate = 74.896%；
- delayed = 20,282；
- RT migrated = 11,685；
- mean wait = 20.47522 h；
- P95 wait = 76 h；
- max wait = 2016 h；
- mean latency = 26.74732 ms；
- max latency = 82 ms；
- hard constraints = PASS；
- last relative improvement = 5.7656e-4。

旧正文中的 1.6696e9 CNY、7.34%、1.9182e6 tCO2、46.66% migration、15.28 h mean wait 等全部为 superseded 旧单遍结果，必须删除。

## P0-4 Carbon-primary 端点与目标组织

Carbon-primary，reference-start，3-pass 收敛：

- Carbon* = 1,815,531.6056203956 tCO2；
- Cost = 1,558,153,356.531096 CNY；
- Carbon-primary 相比 Cost-primary 额外成本 = 2,782,052.3994481564 CNY，占 Cost-primary 0.178867%；
- Cost-primary 相比 Carbon-primary 额外碳排 = 11,242.74901685235 tCO2，占 Carbon-primary 0.619254%。

论文结论：Cost 与 Carbon 高度同向但不完全退化。Q2 采用 Cost-primary 代表方案 + Carbon-primary 端点对照；不使用人工 Cost/Carbon 权重。

## P0-5 多起点稳健性必须加入模型评价

previous-start Cost-primary：4-pass 收敛，全部硬约束 PASS：

- Cost = 1,576,174,462.1213064 CNY；
- Carbon = 1,838,076.5728143891 tCO2；
- eta_R = 37.7179719234%；
- mean wait = 23.82928 h；
- P95 wait = 94 h；
- max wait = 2239 h；
- migration = 63.218%。

相对 reference-start Cost 约高 1.34%。因此不得写“算法对初始化不敏感”或“得到全局最优”。

建议正文表述：

“SFETA 为面向约 2.33e8 个合法候选的大规模动态边际构造式启发式，存在一定路径依赖。本文采用多起点收敛比较，并选取全部硬约束满足且主目标更优的 reference-start 端点作为代表解，不声称全局整数最优。”

## P0-6 极端等待必须主动解释

canonical max wait = 2016 h。人工审计最坏任务 TaskID 13051：BatchInference，Arrival=69，Start=2085，Finish=2090.0667，LatestFinish=2406，AvailableSlack≈2331.93 h，只使用约 86.45% 合法 slack，Latency=22<80 ms。

前 8 个极端等待任务全部为 Batch/Training，无 RT；全部满足 SLA、LatestFinish 和 finish<=2406。

论文应写：长等待是能源主目标利用官方超长时间柔性的服务代价，不是时间索引或 deadline bug。Q2 不人为加入 24/48 h 最大等待窗；Cost--QoS 正式权衡留给 Q4。

## P0-7 Hour 2406 跨问 accounting 口径

当前 Q2 求解代码的经济核算为 Hour 0--2405；Q3 能源模型包含 Hour 0--2406，且 Hour 2406 只做能源终端结算、禁止计算任务占用。

因此 Q2 当前 baseline Cost=1,801,786,872.691887 CNY，而 Q3 B0=1,801,660,137.89 CNY，存在约 126,734.80 CNY 的公共常数差异。

文字手暂时不要自行手加/手减该常数并宣称新 canonical 数字。统一原则写为：

- 0--2405：计算调度敏感时域；
- 2406：仅能源终端结算；
- Q2 排程与相对节约不受该公共常数影响；
- 最终绝对 Cost 与 renewable-utilization 等跨问题对比数值，等待建模手完成统一 accounting/registry 后再冻结。

在 registry 未更新前，正文若必须放数字，明确标注“Q2 调度敏感时域口径”，不要把它与 Q3 B0 直接并表比较。

## P1 FlexCapture 与 ±5% 敏感性

旧论文中的 FlexCapture 38.62% / 42.06% 属于旧结果，不得继续使用。要么按新 canonical endpoint 重算，要么删除具体百分比，仅保留定义。

旧参数 ±5% 敏感性结论同理：未对新 canonical endpoint 重算前，不得继续作为正式验证结果。

## P1 硬约束与截止时间

正文审计必须至少明确：

- GPU/IT/Facility；
- GridImport/Export；
- SLA；
- `Finish_i <= LatestFinishHour_i`；
- `Finish_i <= 2406`；
- RT immediate-start；
- overlap/energy balance；
- final pass fallback=0。

不要只写系统统一 2406 deadline。

## 禁止事项

- 不恢复旧单遍结果；
- 不增加人工加权柔性 score；
- 不截断完整合法时间域；
- 不为了消除 2016 h 等待而事后增加最大等待窗；
- 不声称全局最优；
- 不把 Q4 的 QoS 优化提前塞回 Q2。

## 验收

- [ ] `q2_algorithm.tex` 有外层 convergence loop；
- [ ] removal-dependent 动态边际语义正确；
- [ ] RT 写成“即时开工但可合法迁移”；
- [ ] 主表替换为 2026-08-17 canonical endpoint；
- [ ] 加 Carbon-primary 端点与交叉代价；
- [ ] 加 previous-start 路径依赖说明；
- [ ] 加合法极端等待说明；
- [ ] 删除/重算旧 FlexCapture 与旧敏感性数字；
- [ ] Hour 2406 accounting 未统一前不冻结跨问绝对成本。
