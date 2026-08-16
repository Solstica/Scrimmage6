# shared 实时待办

## TODO
- [ ] 建立跨四问统一的 DS-REPTA（Data-Structure-aware REPTA）接口：任务层候选域、算力负荷映射、能源边际代价、储能状态与结果指标。
- [ ] 统一数据因果接口：workload → GPU usage → AI IT load → IT load → facility load → renewable/grid/storage → cost/carbon/peak。
- [ ] 统一候选域压缩：先由 LatestFinish、MaxLatency、GPU/IT/Facility 容量删去不可行的 (region,start) 组合，再进入 REPTA 排序与修复。
- [ ] 统一能源边际机会成本定义：优先区分“消纳弃电=0、挤占可售新能源=SellPrice、需要新增购电=BuyPrice”三段状态，并与碳边际代价联动。
- [ ] 统一 24 h 新能源周期与 168 h 碳强度周期的滚动时域接口，后续检验是否采用 168 h horizon。
- [ ] 将 `shared/Q9_DATA_AUDIT.md` 中的统计结论落实为当前仓库可重复运行的数据审计脚本，并由各问引用同一份输出。
- [ ] 按 `shared/Q9_SPEC_INTERPRETATION.md` 实现统一时间集合、任务 overlap、SOC 时序索引和 2406 终端边界检查器。

## NEEDS_REVIEW
- [ ] DS-REPTA 为当前统一命名，正式论文前需确认是否保留该名称或改为更中文化的模型名。
- [ ] RegionE 的基准 SOC 在 Hour 0 与 storage_information.xlsx 的 InitialSOC + SOC 递推存在约 1 MWh 单点不一致；Q3/Q4 必须按题面使用 InitialSOC_MWh 为唯一初态，不自行修改原始附件。
- [ ] Q2 的零购电可行性探针表明碳排目标可退化到 0；正式目标组织需进一步确认运行成本、售电机会成本、新能源利用率与 SLA 的权衡方式。
- [ ] Q4 是否最终采用 Benders/分解式联合求解，需在小规模精确 MILP 对照后决定。
- [ ] 开工时刻是否严格限定整数小时边界；当前按 1 h 时间粒度解释为整数开工、分钟级 Duration 用实际 overlap 计量。
- [ ] 2406 若发生纯终端充放电/购售电，其成本与碳排是否纳入最终统计；当前建议纳入以避免“免费终端补能”，需按附件 1 原始公式最终确认。

## DONE
- [x] 确定四问不写成四套互不相关模型，统一理解为 DS-REPTA 的四种工作模式。
- [x] 确定预测部分优先使用可解释统计模型，拒绝将 LSTM 等黑箱模型作为默认路线。
- [x] 确定可视化优先项：区域×任务类型分布、任务类型感知时延迁移图、任务/GPU时间序列、电价-碳强度-新能源曲线、总时间轴。
- [x] 完成第9题六份附件终极数据审计，形成 `shared/Q9_DATA_AUDIT.md`：任务到达近 Poisson、TaskType×Region 强结构、约 2.33 亿原始候选组合、20/80/150 ms 可行域剪枝、24 h 新能源/168 h 碳周期、区域电价/碳固定偏序、基准字段依赖关系、GPU 紧约束、新能源富余和零购电可行性探针。
- [x] 深挖官方 7 条说明并形成 `shared/Q9_SPEC_INTERPRETATION.md`：区分 6 类时间集合，明确预测与正式调度解耦、Q3 固定算力负荷、SOC 端点索引、2400--2405 drain、2406 terminal settlement，以及 Q4 禁止自行补充网络潮流/带宽/迁移能耗成本。
