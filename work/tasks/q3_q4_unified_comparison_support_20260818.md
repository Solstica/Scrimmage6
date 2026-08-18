# Q3 -> Q4 统一比较支持任务（2026-08-18）

Q4 canonical 已完成两轮 final-pool `Cost -> Wait -> Latency` 再认证。Q3 需要提供固定 workload + BESS 的统一 accounting 真源，用于最终 `Q2-only vs Q3-only vs Q4-joint` 比较；不修改 Q3 数学模型。

## 已知 Q3 canonical 结果

- B0 raw reference cost ≈ `1,801,660,137.89 CNY`；
- E0 no-BESS optimized energy cost ≈ `-419,820,327.74 CNY`；
- E1 BESS optimized cost ≈ `-459,217,791.04 CNY`；
- BESS incremental value = `E1-E0 ≈ -39,397,463.30 CNY`；
- E1 carbon≈0；
- renewable utilization≈69.5142%；
- grid purchase≈0；
- regional PeakImport system max=0 under E1。

Q4 canonical true Energy cost=`-459340688.8007043 CNY`。

两者表面差额约 `122,897.76 CNY`，但在 Hour 2406 accounting 完全统一前只能视为 probe，不能冻结为“联合优化增量收益”。

## P0 accounting 对齐

- [ ] 明确 Q3 E0/E1 的成本统计是否包含 2406 terminal settlement。
- [ ] 与 Q4 统一 GridPurchase、GridSell、RenewableUtilization、Carbon、PeakNetImport 定义。
- [ ] 输出 `q3_unified_comparison_metrics.csv/json`。
- [ ] 保留 B0/E0/E1 三层；最终跨问比较优先使用 E1 代表 `storage-only flexibility`。
- [ ] 不将 B0 当作满足 terminal SOC 的优化可行点。

## P0 机制解释

最终 Q4 对照应检验：

- Q3 E1 已经通过 BESS 释放大量能源侧时间柔性；
- Q4 在其基础上只需少量 workload 空间修正就得到 `Wait=0`、migration=0.122%；
- 因此 workload 与 storage flexibility 具有强替代关系，而非价值简单相加。

若 accounting 对齐后 Q3 E1 与 Q4 Cost 仍非常接近，应把“额外经济收益有限但服务质量显著恢复”作为数据结果，而不是为了追求漂亮百分比修改模型。

## P1 unified comparison 支持

为 Q4/Shared 输出同口径：

- Cost；
- Carbon；
- RenewableUtilization；
- regional PeakNetImport；
- storage throughput/SOC 代表量（只作为机制辅助，不进入六指标加权）。

Q3 不需要新增 workload migration/wait 指标，因为 workload 固定；统一比较表中应明确标记为 `fixed workload / not a Q3 decision`，避免与 Q2/Q4 混淆。
