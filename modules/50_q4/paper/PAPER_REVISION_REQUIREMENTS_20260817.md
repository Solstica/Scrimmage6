# Q4 论文文字修订要求（2026-08-17）

状态：WRITER P0。Q4 当前算法仍在修复 Wait/Latency full-domain repricing，因此本文件把“可立即修正文案”和“必须等待新结果再填”的内容分开。禁止在 P0 算法验收前冻结 50k 最终结果。

## 总体定位

Q4 保持 joint workload--energy--storage scheduling：

`task placement/start x -> AI IT -> Facility Load -> Renewable/BESS/Grid recourse`。

算法路线保持：

`Cost Benders/CG -> Carbon epsilon-constraint when active -> Wait full-domain CG -> Latency full-domain CG`。

不恢复六指标等权 minimax，不使用 AHP/熵权/人工综合权重。

## P0-1 Energy Subproblem 必须与正式代码/Q3 同口径

当前 `q4.tex` 中简写的 `R, B+, B-, G+, G-` 能量平衡存在正负号和变量语义混乱，而且与 `q4_full_solver.py` 的正式 LP 不一致。

正式代码实际使用与 Q3 一致的 8 变量能源流：

- `u`：新能源直接供负荷；
- `qR`：新能源充电；
- `qG`：电网充电；
- `d`：储能放电供负荷；
- `gL`：电网供负荷；
- `s`：新能源售电；
- `w`：弃电；
- `E`：SOC。

核心关系应统一写为：

`AvailableRenewable = u + qR + s + w`

`FacilityLoad = u + d + gL`

`GridPurchase = gL + qG`

`E_t = E_{t-1} + eta_c(qR+qG) - d/eta_d`

并保留 Q3 同样的 SOC、Charge/Discharge、GridImport、SellLimit/MaxGridExport、terminal SOC 约束。

建议 Q4 直接说明“给定 workload 后，能源子问题沿用 Q3 同口径 LP”，不要再另造一套容易错位的能量流变量。

## P0-2 workload overlap 公式修正

不要在 overlap 函数里放 `1{r=execRegion_i}`，因为执行区域本身由 `x_{irs}` 决定。

统一写：

`omega_{ist} = max(0, min(t+1,s+p_i)-max(t,s))`

`AI_IT[r,t](x) = sum_{i,s} alpha[k_i] * GPU_i * omega_{ist} * x_{irs}`。

Facility Load 再由 `PUE_r*(NonAI+AI_IT)` 得到。

## P0-3 40-task exact benchmark 数字必须统一

当前真实 Probe 3 benchmark：

- 40 个真实任务：16 Training、14 Batch、10 RT；
- complete legal placements = 3,139；
- Exact joint MILP Cost* = -5,450,201.934546 CNY；
- Region multi-cut Benders 在 2 次迭代内复现 exact Cost。

当前 `q4.tex` 中出现的 `177,995 placements` 和 `-4.5913e8 CNY` 与该 benchmark 不一致，必须删除/更正。不要把 50k 全系统量级数字误写到 40-task 表中。

## P0-4 40-task lexicographic QoS 结果可以保留

这是当前最可靠的 Q4 算法验证证据：

在 `Cost <= Cost* + tol` 的完整合法域内：

1. min total wait；
2. 保持 Cost/Wait 最优，再 min total network latency。

得到：

- migrated = 5；
- total wait = 6 h；
- mean wait = 0.15 h；
- max wait = 2 h；
- latency sum = 437 ms；
- mean latency = 10.925 ms。

明确标为“40-task exact benchmark 的字典序验证结果”，不能冒充 50k 最终结果。

## P0-5 当前 50k Cost 结果只作 DRAFT probe

当前 `results/full_run/summary.json` 真源：

- tasks = 50,000；
- implicit legal domain = 233,375,201；
- Cost root LP closed = true；
- active columns = 51,247；
- Benders cuts = 2；
- restricted integer completed；
- feasible UB energy cost = -459,264,025.4665 CNY；
- runtime ≈ 2.064 min；
- RSS ≈ 0.254 GiB；
- global integer optimum proved = false。

当前论文旧 scaling 表中的 `51,465 columns / 11 cuts / ~24 s / ~650 MB` 已不是当前 full-run canonical 真源。论文若要保留 scaling，只能引用最新结果文件，并显式区分 root closure、restricted integer 与 global integer proof。

禁止写“50k 全局整数最优已证明”。

## P0-6 当前 50k QoS 数字不得进入最终结论

旧 `q4_qos_refinement.py` 只在 Cost-stage active pool 上做 Wait/Latency restricted refinement，没有重新对完整合法域定价。

因此当前：

- total wait = 378,199 h；
- mean wait = 7.56398 h；
- max wait = 1171 h；
- migrated = 37,127；
- mean latency = 29.13924 ms；

均为 `DRAFT / NEEDS_REVIEW`，不能写成完整字典序模型最终结果。

论文手在队友完成以下验收前，不更新 50k QoS 结论：

`40-task Cost-CG -> Wait full-domain CG -> Latency full-domain CG`

必须先复现：migrated=5、total wait=6 h、max wait=2 h、latency_sum=437 ms。

随后才允许跑/写 50k。

## P0-7 gamma=1.4 只能写成诊断压力探针

40-task benchmark 中，基准新能源下 Carbon 可退化为 0。均值保持波动放大探针得到：

`gamma_crit ≈ 1.303326`

因此 `gamma=1.4` 只是在临界点以上选取的诊断压力点，用来验证 Carbon epsilon-constraint 被激活时的 Cost--Carbon 权衡。

可保留诊断结果：

- gamma=1.4 Cost optimum = -5,018,111.400085 CNY；
- Carbon = 53.64762985 tCO2；
- zero-carbon cost penalty ≈ 4,961.32 CNY；
- 局部平均减排成本约 92.48 CNY/tCO2。

但标题/正文必须写“诊断性新能源波动压力探针”，不能写成正式比赛场景。正式 Renewable scenario 仍待协议冻结。

## P0-8 Benders/CG 表述纪律

保持以下结论：

- Benders 由 40-task exact benchmark 验证；
- Cost stage pricing 对完整合法域 exact；
- Wait/Latency 必须分别重新 full-domain exact pricing；
- Cost-stage active columns 不能自动代表 Cost-optimal face 上的 QoS 完整候选；
- 只有 root/reduced-cost closure 不能证明 50k global integer optimum。

如果写 Benders cut，区域 cut 下求和索引应与单一区域 `Q_r` 一致，避免公式里再次混入无关区域求和。

## P1 六指标角色

题面要求报告 Cost、Carbon、Latency、QoS、RenewableUtilization、PeakNetImport，但当前不能把六项等权加入一个目标。

正文当前角色写为：

- Cost：主层；
- Carbon：在被数据/场景激活时用 epsilon-constraint；
- QoS/Wait：Cost 面上的字典序精化；
- Latency：Wait 后的进一步字典序精化；
- RenewableUtilization、regional PeakNetImport：必须报告，并等待 full-system 辨识/冲突探针后判断是否需要额外约束/目标层。

## P1 与 Q2/Q3 的统一解释

建议在 Q4 开头加一段四问边界：

- Q1：最后 24h 基础 workload 调度，energy 不优化；
- Q2：workload 优化，BESS/能源动作固定；
- Q3：workload 固定，energy/BESS 优化；
- Q4：workload + energy/BESS 联合优化。

用此解释 Q2 和 Q3 不是简单串联，Q4 也不能固定 Q2 排程后调用 Q3。

## 禁止事项

- 不继续使用 177,995 / -4.5913e8 的错误 40-task 表；
- 不使用旧 51,465/11 cuts scaling 数字冒充当前 full-run；
- 不把 restricted QoS 的 1171 h 写成正式结论；
- 不把 gamma=1.4 冻结为正式场景；
- 不写六指标等权 minimax；
- 不声称 50k global integer optimum；
- 不在新 full-domain QoS 结果出来前为了“美化结果”增加人为最大等待窗或权重。

## 验收

### 可立即修改
- [ ] Energy subproblem 与 Q3/正式代码统一；
- [ ] workload overlap 公式修正；
- [ ] 40-task benchmark 改为 3139 placements、Cost*=-5,450,201.934546；
- [ ] gamma=1.4 改成诊断 probe；
- [ ] 旧 scaling 数字降级/移除；
- [ ] 明确 global integer optimum 未证明。

### 必须等待队友算法修正后
- [ ] 40-task full-domain Wait/Latency 验收；
- [ ] 新 50k Cost/Wait/Latency 三阶段结果；
- [ ] TaskID 32861 before/after 审计；
- [ ] 新六指标表；
- [ ] Cost--QoS opportunity curve；
- [ ] 正式 Renewable/Price/Carbon 场景结果。
