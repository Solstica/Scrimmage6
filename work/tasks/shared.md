# shared 实时待办

## TODO
- [ ] 建立跨四问统一的 DS-REPTA（Data-Structure-aware REPTA）接口：任务层候选域、算力负荷映射、能源边际代价、储能状态与结果指标。
- [ ] 完成第9题六份附件的终极数据审计，输出“关系—统计量/检验—实际特征—对算法的后果”总表。
- [ ] 固化时间轴：0--2351 参数估计，2352--2375 模型选择，2376--2399 预测独立评价；正式调度使用实际任务，任务/储能状态延伸检查至 2406。
- [ ] 统一数据因果接口：workload → GPU usage → AI IT load → IT load → facility load → renewable/grid/storage → cost/carbon/peak。
- [ ] 统一候选域压缩：先由 LatestFinish、MaxLatency、GPU/IT/Facility 容量删去不可行的 (region,start) 组合，再进入 REPTA 排序与修复。
- [ ] 统一能源边际机会成本定义：优先区分“消纳弃电=0、挤占可售新能源=SellPrice、需要新增购电=BuyPrice”三段状态，并与碳边际代价联动。
- [ ] 统一 24 h 新能源周期与 168 h 碳强度周期的滚动时域接口，后续检验是否采用 168 h horizon。

## NEEDS_REVIEW
- [ ] DS-REPTA 为当前统一命名，正式论文前需确认是否保留该名称或改为更中文化的模型名。
- [ ] 已观察到 AvailableRenewable_MW 区域差异极弱/可能逐时相同、碳强度约 168 h 周期等特征，必须用最终审计代码复算后才能进入正文。
- [ ] Q4 是否最终采用 Benders/分解式联合求解，需在小规模精确 MILP 对照后决定。

## DONE
- [x] 确定四问不写成四套互不相关模型，统一理解为 DS-REPTA 的四种工作模式。
- [x] 确定预测部分优先使用可解释统计模型，拒绝将 LSTM 等黑箱模型作为默认路线。
- [x] 确定可视化优先项：区域×任务类型分布、任务类型感知时延迁移图、任务/GPU时间序列、电价-碳强度-新能源曲线、总时间轴。
