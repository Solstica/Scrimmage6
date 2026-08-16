# Q1 参考文献审计

状态：`DRAFT / NEEDS_REVIEW`

Q1 的参考文献只用于支持统计建模思想与验证纪律，不声称存在一篇论文给出本题完全相同的三层模型。

## 1. Marked Poisson process

Taddy M A, Kottas A. Mixture Modeling for Marked Poisson Processes. Bayesian Analysis, 2012, 7(2): 335--362. DOI: 10.1214/12-BA711.

可支持：
- 事件到达过程与多维 marks 的联合表示；
- marks 可保留条件依赖，而不必强行拆成独立边际。

本题对应：`N_t -> (Region,TaskType) -> (GPU,Duration)|TaskType`。

不能支持：
- 本题的齐次 Poisson 参数值；
- 本题 `pi_rk` 或 GPU/Duration 的具体经验分布。

这些必须由附件数据检验得到。

## 2. 计算工作负载中的 Poisson 性必须经过尺度和诊断验证

Zou Q, Zhu Y, Tan Y, Chen W. Diagnosing the coexistence of Poissonity and self-similarity in memory workloads. Journal of Network and Computer Applications, 2022, 205: 103455. DOI: 10.1016/j.jnca.2022.103455.

可支持：
- 计算工作负载在某些时间尺度上可呈近 Poisson 特征；
- Poisson 假设不能脱离时间尺度、独立性和自相关诊断直接套用。

本题对应：Fano、Poisson GOF、ACF、hour-of-day/weekday 诊断后才接受齐次 Poisson。

## 3. 层级聚合与一致概率预测

Cohen M C, Zhang R, Jiao K. Data Aggregation and Demand Prediction. Operations Research, 2022, 70(5): 2597--2618. DOI: 10.1287/opre.2022.2301.

Bertani N, Jensen S T, Satopaa V A. Joint Bottom-up Method for Probabilistic Forecasting of Hierarchical Time Series. Operations Research, 2025, 73(6): 3260--3277. DOI: 10.1287/opre.2022.0113.

可支持：
- 聚合层级对需求预测有实质意义；
- 概率预测应检查层级一致性，而不是只评价顶层点预测。

本题对应：Region×TaskType 底层统一聚合到 Region、TaskType、System，并同时报告各层误差与 PICP/MPIW/interval score。

## 4. 论文引用建议

Q1 正文最多保留 2--3 篇真正承载方法的引用即可：

- marked Poisson：Taddy & Kottas；
- Poisson 工作负载诊断：Zou et al.；
- 层级一致预测：Cohen et al. 或 Bertani et al.。

不要为提高参考文献数量堆大量深度学习 workload forecasting 论文，因为当前数据诊断并不支持采用深度模型。
