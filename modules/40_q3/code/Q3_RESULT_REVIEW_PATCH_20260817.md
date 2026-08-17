# Q3 正式结果复核补丁（2026-08-17）

状态：`DRAFT / NEEDS_REVIEW`

本补丁不改变 Q3 的 fixed-load BESS LP，只修正结果语义与正文口径。

## 已确认通过

- full LP 主成本、E0/E1 对照与先前 reduced-model 独立探针一致；
- E1-E0 BESS 增量经济价值 `39,397,463.30 CNY`；
- 六区域能量平衡、SOC、购售电、充放电上限残差通过；
- A/B/C 零储能动作，D/E/F 产生全部 BESS 增量价值；
- Stage 2 同时充放电时段为 0。

## 本轮纠偏

1. `System PeakImport` 不再允许跨区域售电抵消区域购电峰值。正式峰值采用逐区 `PeakImport_r=max_t max(GridPurchase-GridSell,0)`，系统汇总时报告六区最大值；原跨区域净交换峰值另行命名 `AggregateNetExchangePeak`。
2. Q3 Facility Load 固定，因此设施负荷波动变化率为 0。E0->E1 的 `SigmaGrid: 115.3914 -> 4.9825 MW`（约 -95.68%）和 `MeanAbsRamp: 29.2902 -> 0.4044 MW`（约 -98.62%）只解释为“电网交互功率平滑”。
3. Stage 1 同时充放电数量依赖多重最优代表解：早期 probe 曾得到 2111，本次正式 solver 得到 6。正文不冻结该数量，只保留“纯成本面退化；Stage 2 最小吞吐量后稳定为 0”。
4. A/B/C 的 `1e-4 CNY`、`1e-7 MWh` 量级结果由 Stage-2 成本容差产生，正式展示记为 numerical zero。
5. B0 仅是附件 raw reference；附件部分区域终端 SOC 不满足 Q3 正式终端约束。B0-E0 / B0-E1 不作为储能单独贡献。

实现补丁：`modules/40_q3/code/q3_result_semantics_patch.py`。
