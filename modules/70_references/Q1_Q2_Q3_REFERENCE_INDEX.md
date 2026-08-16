# Q1--Q3 参考文献索引与使用边界

状态：`DRAFT / NEEDS_REVIEW`

本文件只做索引，不替代逐篇审计。

## Q1

详细：`Q1_REFERENCE_AUDIT.md`。

主引用建议：
- Taddy & Kottas 2012：marked Poisson process；
- Zou et al. 2022：计算工作负载的 Poisson 性需要由时间尺度和统计诊断确认；
- Cohen et al. 2022 / Bertani et al. 2025：层级聚合与一致概率预测。

Q1 的 `lambda`、`pi_rk`、条件 mark 与 90% 区间都必须由附件数据给出，不能由文献替代。

## Q2

详细：`Q2_REFINEMENT_REFERENCES.md`。

主引用建议：
- Sukprasert et al., EuroSys 2024：carbon-aware temporal/spatial workload shifting；
- Zheng et al., Joule 2020：load migration 用于 renewable curtailment mitigation；
- Hanafy et al., POMACS 2023 CarbonScaler：marginal resource allocation；
- Xu et al., NSDI 2025 GREEN：ML job temporal flexibility 与 carbon-aware scheduling；
- Chen et al., Sustainable Computing 2024：spatio-temporal management of renewable consumption, carbon and cost；
- Tamby & Vanderpooten：只有 Cost--Carbon 实质冲突时才考虑 epsilon-constraint。

Q2 当前必须坚持：动态边际能源后果，不把 baseline Curtailment 当成静态绿色得分；完整 RT 空间合法域；不人为截断候选。

## Q3

详细：`Q3_REFERENCE_AUDIT.md`。

主引用建议：
- Zhang et al., Energy 2025：data-center BESS optimal dispatch；
- Wang et al., Applied Energy 2024：storage complementarity exact relaxation；
- Vaičys et al., Journal of Energy Storage 2024：convex BESS dispatch；
- Grimaldi et al., Journal of Energy Storage 2025：no-storage benchmark、curtailment、energy arbitrage。

Q3 的 A/B/C、D/E、F 区域机制来自附件 `H=AvailableRenewable-FacilityLoad` 和 SellLimit，不把它包装成已有标准模型。

## 共同纪律

1. 题面和附件定义优先于外部文献；
2. 文献用于支持术语、问题类型、建模原则与算法思想；
3. 任何本题具体数值、相关性、分区结论必须来自附件和代码审计；
4. 不用同领域论文替代官方 CarbonEmission、新能源利用率、SOC、GPU/IT/Facility 等口径；
5. 不为了“参考文献高级”引入题目未给参数的 DRO、RL、MPC、degradation、shared storage、线路潮流等机制。
