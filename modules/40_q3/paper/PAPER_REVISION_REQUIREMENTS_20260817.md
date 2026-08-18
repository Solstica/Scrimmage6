# Q3 论文文字修订要求（2026-08-17）

状态：WRITER P0。Q3 当前模型与结果主体可保留，不重写模型；本文件只修正机制表述、退化解口径和跨问一致性。

## 总体定位

Q3 固定计算负荷：

`FacilityLoad = PUE * (Baseline_AI_IT_Load + NonAI_IT_Load)`

仅优化 Renewable / BESS / Grid 能源侧。主求解结构保持：

`Cost -> Throughput`

三层对照保持：

- B0：附件 raw baseline；
- E0：同固定负荷、无储能能源调度；
- E1：完整 BESS 调度；
- 只有 E1-E0 解释为 BESS 增量价值。

## P0-1 D/E/F 储能机制表述必须修正

正式 LP 中售电变量 `s[r,t]` 只允许来自当期新能源分配；储能放电 `d[r,t]` 不能直接作为售电来源。

因此正文不能写：

“低售电价时充电，高售电价时放电并售出。”

统一改为：

“低价期利用新能源给储能充电；高价期储能放电承担部分设施负荷，从而释放同期新能源用于外送售电，实现新能源跨时段价值转移。”

对 RegionF 再补：除上述间接售电时移外，储能还在唯一新能源短缺小时替代电网购电。

## P0-2 Stage 1 退化解数字不得包装成稳定物理结果

Stage 1 纯成本 LP 存在多重最优。不同求解器/探针曾返回不同数量的 SCD 时段和不同总吞吐量，因此以下数字不能作为稳定正文结论：

- “Stage 1 固定出现 2111 个 SCD Region-Hour”；
- “Stage 1 总吞吐量固定为 1,331,389.40 MWh”；
- “Stage 2 一定相对 Stage 1 下降 74.00%”。

正式正文只保留稳定结论：

1. Stage 1 可能返回含无经济意义同时充放电的成本等价退化解；
2. 在 `Cost <= Cost* + 1e-4 CNY` 内最小化 Throughput 后，SCD 稳定降为 0；
3. Stage 2 系统总吞吐量 = 346,201.93 MWh；
4. 主成本只发生求解容差量级变化。

若需要说明 2111 / 6 等，只放模型审计或附录，用于证明 Stage 1 代表解不稳定，不进入主结果表。

## P0-3 系统结果保持

当前正式主表关键数字可保留：

- B0 Cost = 1,801,660,137.89 CNY；
- E0 Cost = -419,820,327.74 CNY；
- E1 Cost = -459,217,791.04 CNY；
- BESS incremental value = 39,397,463.30 CNY；
- B0 Carbon = 2,045,367.48 tCO2；
- E0 Carbon = 8.8506 tCO2；
- E1 Carbon = numerical zero；
- Renewable utilization：B0 32.8623%，E0 67.9150%，E1 69.5142%；
- E0 Grid purchase = 31.5979 MWh；E1 = numerical zero；
- E1 renewable sell = 1,491,718.26 MWh。

解释纪律：B0->E1 的整体大幅改善不能全部归因于 BESS；只有 E1-E0 是 BESS 增量价值。

## P0-4 波动指标口径保持清楚

Facility Load 在 B0/E0/E1 中固定，波动变化率严格为 0。

可报告储能改善的是 NetGridImport：

- std：115.3914 -> 4.9825 MW，约 -95.68%；
- mean absolute ramp：29.2902 -> 0.4044 MW，约 -98.62%。

正文只能写“电网交互功率显著平滑”，禁止写“设施负荷波动降低”。

## P0-5 PeakImport 口径

PeakImport 必须按区域计算：

`PeakImport_r = max_t max(NetGridImport[r,t], 0)`。

E0 最大区域峰值在 RegionF = 31.597867 MW；E1 六区域均为 numerical zero。

不得用“六区域 NetGridImport 先相加再取峰值”替代区域峰值，否则跨区售电会抵消局部购电。

## P1 B0 数据异常与边界

继续明确：

- B0 只是附件 raw reference；
- D/E/F 的 B0 terminal SOC 低于 Q3 `InitialSOC` 要求，因此 B0 不是正式优化可行点；
- RegionE Hour0 baseline SOC 约 1 MWh 差异只记录，不修改附件原数据；
- Hour 2406 能源结算真实计入成本/碳，不能免费补终端 SOC。

## P1 分区机制

保留数据结构导出的三类：

- A/B/C：持续盈余 + 不可售电，Stage 2 零储能动作；
- D/E：持续盈余 + 可售电，BESS 通过“放电供负荷 -> 释放同期新能源售电”实现价值时移；
- F：上述机制 + 唯一短缺小时的购电替代。

区域增量价值保持：

- D = 9,743,701.13 CNY；
- E = 13,696,192.16 CNY；
- F = 15,957,570.01 CNY。

## P1 图形建议

正文至少预留两类图，图完成后再写最终图号：

1. D/E/F 代表区域 SOC + Charge/Discharge 时序；
2. E0/E1 NetGridImport 对比或区域典型小时对比。

不要为图形引入新模型或 Stage 3，除非建模手另行冻结。

## 禁止事项

- 不重新调度 workload；
- 不引入电池退化成本、随机规划、MPC、RL；
- 不把 Stage 1 的具体退化代表解写成稳定物理结果；
- 不写“储能放电直接售电”；
- 不把 B0-E1 解释成纯 BESS 收益。

## 验收

- [ ] D/E/F 机制改为“放电供负荷、释放新能源售电”；
- [ ] 删除 Stage1 固定 2111/SCD、1.331e6 MWh、74% 等稳定化表述；
- [ ] 保留 Stage2 SCD=0、Throughput=346,201.93 MWh；
- [ ] B0/E0/E1 归因口径正确；
- [ ] Facility Load 与 NetGridImport 波动严格区分；
- [ ] PeakImport 按区域定义；
- [ ] 不新增模型层。
