# Q4 论文文字修订要求（2026-08-18更新）

状态：`CANONICAL PAPER RESULT AVAILABLE / SCENARIOS PENDING`。

旧版“Wait/Latency full-domain repricing 尚未完成、1171 h 结果不得进入正文”的阻塞已经解除。50k `region_multicut_v1` 已完成两轮 final-pool `Cost -> Wait -> Latency` 再认证；本文件现只保留最终论文需要执行的最新要求。

真源：

- `modules/50_q4/results/qos_refinement_multicut/q4_qos_summary.json`；
- `modules/50_q4/results/FINAL_RECERTIFICATION_REVIEW_20260818.md`；
- `work/tasks/q4_finalization_20260818.md`。

## P0-1 50k canonical 正式结果

正文必须使用：

- Cost=`-459340688.8007043 CNY`；
- Total Wait=`0 h`；
- Total Latency=`250860 ms`；
- mean latency=`5.0172 ms`；
- migrated=`61/50000=0.122%`；
- max latency=`58 ms`；
- max finish=`2405.6 h`；
- final active columns=`137158`；
- Benders cuts=`1173`；
- hard audit PASS；
- max physical residual≈`1.14e-13`。

删除/降级所有旧 restricted-pool 结论：

- total wait=378199 h；
- max wait=1171 h；
- migrated≈37127；
- 旧 Cost anchor≈-459274946.57。

这些只属于算法开发历史，不得再进入正式正文结果。

## P0-2 final-pool recertification 证据

必须说明两轮 sweep：

- Sweep1 Latency pricing 新增 19 列；
- Sweep2 Cost/Wait/Latency 均新增 0 列；
- 两轮 Cost/Wait/Latency anchors 完全一致；
- min missing reduced cost=0；
- max region Benders violation=0；
- restricted MIP gap=0；
- true Energy LP 复核通过。

正式称呼：

`final-pool recertified best-known integer representative solution`。

## P0-3 最优性边界

禁止写“50k 全局整数最优已证明”。

Latency：

- full-domain LP LB=`250469.954579 ms`；
- integer representative UB=`250860 ms`；
- relative gap≈`0.1555%`。

`restricted MIP gap=0` 只表示最终活动列池上的 MIP 已求到最优，不是完整域整数证书。

40-task exact benchmark 继续保留，作为算法 exactness validation，不外推成 50k global proof。

## P0-4 新的核心结果解释

Q2 Cost-primary（energy/BESS fixed）：

- migration≈74.896%；
- mean wait≈20.475 h；
- max wait=2016 h。

Q4 joint：

- migration=0.122%；
- Total/Mean/Max Wait=0。

必须解释为：

> 储能时间柔性替代了绝大部分原本由 workload 时间平移和跨区迁移承担的调节需求；计算柔性只需极少量空间修正即可维持 Cost 最优面内服务质量。

不要写成“Q2 错误”或“Q4 不需要 workload flexibility”。

## P0-5 Q3->Q4 成本差暂不冻结

Q3 E1≈`-459217791.04 CNY` 与 Q4≈`-459340688.80 CNY` 的表面差约 `122897.76 CNY`。

在 Hour 2406 terminal settlement、Cost/Carbon/RenewableUtilization、GridSell/GridPurchase 与 Baseline 命名完全统一前，只能称 cross-question probe，不得写成正式 synergy / incremental benefit。

## P0-6 正式场景——整问最后的主阻塞

必须在同一个 joint workload--energy--storage 模型下分别完成：

1. Carbon constraints；
2. electricity-price mechanisms；
3. renewable fluctuation scenarios。

每个场景必须重新允许 workload + BESS/Grid 联合优化并执行 exact pricing。历史 `gamma=1.4` 仍只是 diagnostic pressure probe。

## P0-7 六指标

canonical 与场景统一报告：

- Cost；
- Carbon；
- QoS/Wait；
- Latency；
- RenewableUtilization；
- regional PeakNetImport。

不使用 AHP、熵权、等权 minimax 或人为六指标加权。

## P1 图

正文优先：

1. 区域优势错位结构矩阵；
2. 顺序 Q2->Q3 失真 probe；
3. 计算柔性--储能柔性争用/替代机制；
4. Benders + Exact CG 流程；
5. 50k final-pool 两轮再认证；
6. accounting 统一后的 Q2/Q3/Q4 comparison；
7. Carbon/price/renewable 正式场景。

## P1 模型评价

必须具体写：

- 数据结构驱动；
- 无主观权重；
- 完整合法域不裁剪；
- 40-task exact + 50k final-pool recertification；
- 50k global integer optimum 未证明，Latency gap≈0.1555%；
- formal scenarios 尚需完成后才能整问 `FROZEN + CHECKED`。

## 当前验收

- [x] Energy subproblem 与 Q3 统一；
- [x] overlap 公式修正；
- [x] 40-task exact benchmark；
- [x] 50k full-domain Wait/Latency repricing；
- [x] final-pool Cost->Wait->Latency 两轮再认证；
- [x] 50k final task-level representative solution；
- [x] hard audit PASS；
- [x] `q4.tex` canonical 结果同步；
- [ ] final schedule/stage metrics 正式入库；
- [ ] canonical 六指标；
- [ ] Carbon formal scenarios；
- [ ] price mechanism scenarios；
- [ ] renewable fluctuation scenarios；
- [ ] Q2/Q3/Q4 accounting 统一；
- [ ] 全文摘要/图/表最终冻结。
