# Q3 数据结构驱动论文与作图任务（2026-08-18）

依据：`modules/40_q3/paper/DATA_STRUCTURE_PAPER_ENRICHMENT_20260818.md`。

本任务不改变 Q3 的 fixed-load BESS LP、Cost -> Throughput 两阶段结构或 B0/E0/E1 定义；只强化“数据结构先于模型”的论文表达和图证据。

## P0 正文数据链

- [ ] 在八变量 LP 之前保留并加强 `H[r,t]=AvailableRenewable-FacilityLoad` 数据探针。
- [ ] 正文显式列出六区 `AvailableRenewable / FacilityLoad` 总量比约 1.745--1.812，说明当前附件不是典型新能源短缺系统。
- [ ] 显式说明 A--E 全 2407 h `H>=0`，F 仅 1 h `H<0`。
- [ ] 将 H 与 SellLimit 联合推导 A/B/C、D/E、F 三类角色；明确该分类不是 cluster、不是人工分组、不是求解后归纳。
- [ ] 在 B0/E0/E1 小节前说明 D/E/F baseline `SOC(2406)<InitialSOC`，因此 B0 只是 raw reference；`E1-E0` 才是 BESS 增量价值。
- [ ] 保留 Price/Carbon/Renewable 时间相关的说明，但明确当前 GridPurchase 几乎退化为 0，因此不人为构造 Cost--Carbon 多目标。
- [ ] 结果分析采用“数据结构预测角色 -> LP 输出验证角色”的写法，不只列最终成本表。

## P0 必补数据图

### Q3-A 六区域新能源盈余结构证据图
- [ ] 生成每区 `min(H)`。
- [ ] 生成每区 `#(H<0)`。
- [ ] 生成/整理 SellLimit。
- [ ] 用一张复合图或共享横轴多面板表现三者，直接标识 A/B/C、D/E、F 三组。
- [ ] 不使用综合评分，不用 K-means/聚类，不人为标准化后加权分类。

### Q3-B D/E/F SOC 三面板
- [ ] 每个区域独立小面板，保持 MWh 单位。
- [ ] 加 MinSOC、InitialSOC、Capacity 水平参考线。
- [ ] 不把三个不同容量区域只画成无上下文的共轴绝对值曲线。

### Q3-C 六区域 BESS 增量价值
- [ ] 用 `E1-E0` 画区域增量价值，A/B/C=0、D/E/F>0。
- [ ] 图注禁止把 `B0-E1` 称为 BESS 单独贡献。

### Q3-D RegionF 唯一短缺小时机制图
- [ ] 自动定位唯一 `H<0` 小时。
- [ ] 截取其前后 24--48 h 窗口。
- [ ] 上层：AvailableRenewable 与 FacilityLoad；中层：Charge/Discharge；下层：GridPurchase/GridSell。
- [ ] 竖线标唯一短缺小时，说明 F 除售电价值时移外还有购电替代价值。

## P1 结果图

### Q3-E E0 vs E1 NetGridImport 时序
- [ ] 图中增加 `y=0` 参考线。
- [ ] 正值=净购电，负值=净售电。
- [ ] 支撑 `115.39 -> 4.98 MW` 的 Grid-interaction sigma 降低；不得写成 FacilityLoad 波动降低。

### Q3-F B0/E0/E1 RenewableUtilization
- [ ] 先准备绘图数据。
- [ ] Q2--Q4 accounting 统一前不得冻结正式数值图。
- [ ] B0 明确标 `raw reference`。

## P1 降级/删除
- [ ] “D/E/F总充电量 vs 总放电量”普通柱图降级附录，优先级低于 Q3-D。
- [ ] Stage 1 具体 SCD 数量、具体退化吞吐量不得做正文图。
- [ ] 不新增 Cost--Carbon Pareto 图；当前数据不支持把它作为 Q3 主冲突。

## WRITER 验收
- [ ] 读者在看到 LP 前能够仅凭 H+SellLimit 图推断三类储能角色。
- [ ] 正文解释 A/B/C 零储能不是“求解器恰好这样算”，而是数据结构可预判的成本最优行为。
- [ ] D/E 的机制统一写成“储能放电供负荷 -> 释放同期新能源售电”，不写储能直接售电。
- [ ] F 最高增量价值不归因于唯一短缺小时单一因素。
- [ ] `Cost -> Throughput` 只解释为成本最优面代表解选择，不包装成新的物理目标。
