# shared 实时待办

## TODO
- [ ] 统一数据因果关系：workload → GPU usage → AI IT load → IT load → facility load → renewable/grid/storage → cost/carbon/peak；各问按题面逻辑递进，不再把“接口化”本身当建模目标。
- [ ] 将 `shared/Q9_DATA_AUDIT.md` 中的统计结论落实为当前仓库可重复运行的数据审计脚本，并由各问引用同一份输出。
- [ ] 按 `shared/Q9_SPEC_INTERPRETATION.md` 实现统一时间集合、任务 overlap、SOC 时序索引和 2406 终端边界检查器。
- [ ] 继续核查 2406 纯终端能源动作的成本/碳结算口径，避免免费终端补能。
- [ ] Q2/Q4 的任务分配候选算法暂定 `SFETA`（Spatio-temporal Flexibility and Energy-aware Task Assignment），详细来源与改造边界见 `shared/Q9_SFETA_ADAPTATION.md`；正式论文前再次检查命名碰撞。
- [ ] SFETA 的合法候选域只允许按题面硬约束/可证明不可行性剪枝；禁止为了算得快人为限定最大延迟、最近区域、固定候选数量等搜索域。

## NEEDS_REVIEW
- [ ] RegionE 的基准 SOC 在 Hour 0 与 storage_information.xlsx 的 InitialSOC + SOC 递推存在约 1 MWh 单点不一致；Q3/Q4 必须按题面使用 InitialSOC_MWh 为唯一初态，不自行修改原始附件。
- [ ] Q2 的零购电可行性探针表明碳排目标可退化到 0；正式目标组织需进一步确认运行成本、售电机会成本、新能源利用率与 SLA 的权衡方式。
- [ ] Q4 是否最终采用 Benders/分解式联合求解，需在小规模精确对照后决定，不提前把算法结构写死。
- [ ] 开工时刻是否严格限定整数小时边界；当前按 1 h 时间粒度解释为整数开工、分钟级 Duration 用实际 overlap 计量。

## DONE
- [x] 确定四问按题意和数据关系逐层建立：Q1 统计预测+基础规则调度；Q2 引入能源感知时空任务分配；Q3 固定任务研究储能/电力响应；Q4 再联合任务与能源柔性。撤销“DS-REPTA 四工作模式”的旧理解。
- [x] 确定预测部分优先使用可解释统计模型，拒绝将 LSTM 等黑箱模型作为默认路线。
- [x] 确定可视化优先项：区域×任务类型分布、任务类型感知时延迁移图、任务/GPU时间序列、电价-碳强度-新能源曲线、总时间轴。
- [x] 完成第9题六份附件终极数据审计，形成 `shared/Q9_DATA_AUDIT.md`：任务到达近 Poisson、TaskType×Region 强结构、约 2.33 亿原始候选组合、20/80/150 ms 可行域剪枝、24 h 新能源/168 h 碳周期、区域电价/碳固定偏序、基准字段依赖关系、GPU 紧约束、新能源富余和零购电可行性探针。
- [x] 深挖官方 7 条说明并形成 `shared/Q9_SPEC_INTERPRETATION.md`：区分 6 类时间集合，明确预测与正式调度解耦、Q3 固定算力负荷、SOC 端点索引、2400--2405 drain、2406 terminal settlement，以及 Q4 禁止自行补充网络潮流/带宽/迁移能耗成本。
- [x] 读取 2026 Applied Energy REPTA 全文，确认 REPTA 是三阶段策略中的 Stage II 具体非迭代任务分配算法：Phase A 本地消纳 RES overproduction，Phase B 跨区搜索 RES overproduction，仍无则选择低电价；形成 `shared/Q9_SFETA_ADAPTATION.md`。
