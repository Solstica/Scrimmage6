# Q4 最终化任务（2026-08-18）

依据：`modules/50_q4/results/FINAL_RECERTIFICATION_REVIEW_20260818.md`。

## 当前状态

`region_multicut_v1` canonical 联合优化主问题已经完成两轮 final-pool `Cost -> Wait -> Latency` 再认证。

正式 canonical endpoint：

- Cost = `-459340688.8007043 CNY`；
- Total Wait = `0 h`；
- Total Latency = `250860 ms`；
- 50,000 tasks 全覆盖；
- migrated = `61`（0.122%）；
- mean latency = `5.0172 ms`；
- max latency = `58 ms`；
- max finish = `2405.6 h`；
- active columns = `137158`；
- Benders cuts = `1173`；
- full-domain pricing reduced cost = 0；
- max region Benders violation = 0；
- hard audit PASS。

Canonical 关键结果已经在 `results/registry.csv` 中单独升级为 `FROZEN + CHECKED`；Q4 整问仍保持 `FINISHED_DRAFT`，因为正式 Carbon/price/renewable 场景尚未完成。

**Q4 canonical solver closure 已完成。停止继续修改主模型/主算法。**

不能写 `global integer optimum proved`。Latency full-domain LP / integer gap：

- LB = `250469.954579 ms`；
- UB = `250860 ms`；
- relative gap ≈ `0.1555%`。

## P0-A 结果 artifact 归档

- [x] 最终 `q4_qos_summary.json` 已更新为 FINISHED_DRAFT final summary；
- [x] 已生成 `q4_final_schedule_kpi_20260818.csv`；
- [x] 已生成 `q4_final_migration_matrix_20260818.csv`；
- [x] 已生成 `FINAL_RECERTIFICATION_REVIEW_20260818.md`；
- [ ] 把完整 `q4_recertification_stage_metrics.csv` 推入 `modules/50_q4/results/qos_refinement_multicut/`；
- [ ] 把 50k `q4_字典序最终排程.csv` 推入同目录或明确的 final/ 子目录；
- [ ] 对完整排程文件保存 checksum/行数/TaskID唯一性说明；
- [ ] 最终 artifact 文件名不再使用 round/temporary/recovery 字样。

## P0-B 正式场景分析——这是现在最高优先级

题面要求必须完成三类场景，每类都在同一 joint model 下重新允许 workload + BESS/Grid 联合优化。

### Carbon constraints

- [ ] 先计算 canonical Carbon。
- [ ] 以 canonical 或透明场景下的 Carbon 为数据锚点设置 epsilon budgets。
- [ ] 建议先用 `{100%, 75%, 50%, 25%, minimum-feasible}` 相对预算；若 Carbon 在原始场景退化，则明确报告“原始场景不活跃”，并在可解释压力情景中激活后再比较。
- [ ] 每个点重新 exact pricing + true Energy verification。
- [ ] 输出 Cost/Carbon/Wait/Latency/RenewableUtilization/PeakNetImport。
- [ ] 历史 `gamma=1.4` 只能保留 diagnostic，不得冒充正式场景。

### Electricity-price mechanisms

- [ ] 以附件逐时价格机制为 canonical。
- [ ] 构造 `flat price`、`attachment price`、`transparent peak-valley sensitivity` 三类；参数必须事前写入场景协议，不允许看结果后调参。
- [ ] 不修改 sell-price 语义或售电来源限制。
- [ ] 每个场景允许 workload + BESS/Grid 重新联合优化。

### Renewable fluctuation

- [ ] 保持六区原始 AvailableRenewable 的附件空间语义，不凭 E/F 标签人为加区域系数。
- [ ] 建议做可复现的统一幅值/时序扰动，例如 nominal、downward stress、upward/shape stress；参数在运行前冻结。
- [ ] 场景中重新优化 workload + storage/grid；不得只把 canonical schedule 固定后重算 Energy LP。
- [ ] 输出 six-metric 统一表和主要机制变化。

## P0-C 六指标正式报告

canonical 与全部正式场景统一输出：

1. Cost；
2. Carbon；
3. Total/Mean/P95/Max Wait；
4. Total/Mean/P95/Max Latency；
5. RenewableUtilization；
6. regional PeakNetImport（A--F + system max）。

不得构造六指标综合分、AHP/熵权或等权 minimax。

## P0-D Q2/Q3/Q4 accounting 统一与跨问比较

先统一：

- 0--2399 arrivals；
- 2400--2405 drain；
- 2406 terminal energy settlement only；
- Cost/Carbon/RenewableUtilization 统计时域；
- GridSell / GridPurchase；
- PeakNetImport；
- Baseline/reference/B0 命名。

统一后冻结：

`Q2-only workload flexibility` vs `Q3-only storage flexibility` vs `Q4-joint flexibility`。

重点验证新机制结论：

- Q2 canonical workload KPI 已单独冻结：migration=74.896%，mean wait=20.47522 h，max wait=2016 h；
- Q4 canonical：migration=0.122%，wait=0；
- 判断 storage flexibility 是否替代绝大部分 workload temporal/spatial adjustment。

Q3 E1 与 Q4 当前表面成本差约 122,897.76 CNY 只作 probe，accounting 未统一前不得写正式增量收益。

## P0-E 论文正文更新

- [x] 删除“50k Wait/Latency 仍在闭合”“最终排程继续 DRAFT 不进入结论”等过期文字；
- [x] 加入 50k final-pool recertification 正式结果表；
- [x] 加入两轮 sweep 锚点完全一致的稳定性说明；
- [x] 加入 `61/50000` migration、`Wait=0`、mean latency=5.0172 ms 的结果解释；
- [x] 将 Q4 机制结论升级为“计算柔性与储能柔性存在显著替代关系”；
- [x] 明确 `restricted MIP gap=0 != full-domain integer optimum proved`；
- [x] 报告 Latency LP--integer gap≈0.1555%；
- [x] 保留 40-task exact benchmark 作为算法验证，不再让它替代 50k 正式结果；
- [x] `modules/60_evaluation/paper/evaluation.tex` 已从模板改为问题特定评价；
- [x] `modules/00_abstract/paper/abstract.tex` 已生成数据驱动 draft，且只使用当前允许冻结的关键数字。

## P1 图

正文优先：

1. **Q4-A 区域优势错位结构矩阵**：AvailableGPU/PUE/latency accessibility/BESS/SellLimit/Price/Carbon/Curtailment，无综合评分；
2. **Q4-B 顺序 Q2->Q3 失真 probe**；
3. **Q4-C 计算柔性 vs 储能柔性争用/替代新能源机制图**；
4. **Q4-D final-pool recertification**：Sweep1/2 的 Cost、Wait、Latency anchors + active columns/cuts；
5. **Q4-E Q2-only/Q3-only/Q4-joint 统一比较**：accounting 统一后再画；
6. **Q4-F 正式场景**：Carbon / price / renewable。

算法 Benders/CG 流程图保留，但不能取代上述数据/结果图。

## P1 结果冻结门禁

只有以下同时满足才把整问升级 `FROZEN + CHECKED`：

- [x] canonical 50k recertification 完成；
- [x] canonical hard audit PASS；
- [x] canonical 关键 KPI 已在 registry 单独 FROZEN+CHECKED；
- [ ] 完整 final schedule / recertification metrics 入库；
- [ ] canonical 六指标齐全；
- [ ] Carbon constraints 正式场景完成；
- [ ] electricity-price mechanisms 完成；
- [ ] renewable fluctuation scenarios 完成；
- [ ] Q2/Q3/Q4 accounting 统一；
- [ ] 正文/图/表全部引用同一冻结结果。

## 禁止事项

- 不再继续给 canonical 主算法加 branch-and-price、stabilization 或新启发式；
- 不恢复旧 restricted-pool `1171 h / 378199 h` 结果；
- 不声称 50k 全局整数最优；
- 不用场景结果反向修改 canonical 模型；
- 不把未统一 accounting 的 Q3/Q4 成本差写成正式 synergy；
- 不把 Q2 高迁移解释成 Q4 也必须高迁移。
