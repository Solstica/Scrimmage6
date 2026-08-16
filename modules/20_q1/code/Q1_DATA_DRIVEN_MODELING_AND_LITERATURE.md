# Q1 数据结构驱动的建模逻辑与文献定位

状态：`DRAFT / NEEDS_REVIEW`

本文件用于固定问题一的“为什么这样建模”，避免把 Q1 写成先选模型、再往数据里套。正式实现仍以 `README.md` 与 `q1_solver.py` 为准。

## 1. 数据结构先于模型名称

Q1 的概率模型由下列数据事实共同推出：

1. 训练段小时总到达数均值约 20.8，Fano 约 0.97；Poisson 拟合未被拒绝，lag 1/24/168 自相关很弱；
2. `TaskType × SourceRegion` 关联明显，Cramér's V 约 0.434，因此业务组成不能拆成独立的 `P(Region)P(TaskType)`；
3. 给定 `TaskType` 后，Region 对 GPU_Demand 与 Duration 的附加影响很弱；
4. GPU 与 Duration 的线性相关接近 0，但没有足够证据把它们强行拆成独立边际，因此保留 `(GPU,Duration)|TaskType` 的联合经验 mark；
5. 系统点预测的时间记忆很弱，lag-24、lag-168 在验证段明显不优于历史均值，因此不为“模型复杂度”引入 LSTM/ARIMA/季节状态。

因此模型自然形成三层：

`N_t ~ Poisson(lambda)`

`P(R=r,K=k)=pi[r,k]`

`(G,D)|K=k ~ Fhat_GD[k]`

即：

`总到达强度 -> Region-TaskType 联合业务组成 -> TaskType 条件资源标记`。

这就是当前“结构化标记复合 Poisson 短期预测”的真正来源。

## 2. 为什么不是普通历史均值

在 System 层，齐次标记复合 Poisson 的解析均值会自然退化为历史平均 GPU demand，因此 M3 与历史均值 M0 的 System 点预测一致并不是程序错误。

M3 的附加价值在于：

- 保持 Region、TaskType、Region×TaskType、System 四层严格加和一致；
- 直接给出子层概率分布与 90% 预测区间；
- 允许从同一联合 mark 同时解释 GPU demand 与 GPU-hour；
- 将 Q1-1 识别出的 `Region-Type` 关联真正嵌入 Q1-2，而不是只在描述统计中展示。

因此正文不得写“复合 Poisson 显著提高系统点预测精度”；更准确的说法是：

> 在不牺牲系统层点预测精度的前提下，结构化标记模型提供了层级一致的需求分解和概率区间，并在细粒度 Region/Region×TaskType 层保持略优或相当的误差表现。

## 3. 当前独立验证结果的正确解释

当前修正版已经同时输出 Validation/Test 的四层误差与 90% 区间指标。

Test 90% PICP：

- Region×TaskType：约 94.21%；
- Region：约 89.58%；
- TaskType：约 90.28%；
- System：87.5%（21/24）。

System 只有 24 个测试小时，因此 87.5% 不应被单独解释为区间失效。必须联合 Validation PICP、MPIW 和 interval score 评价；不得看到 Test 后回调区间参数。

## 4. Q1-3 与概率预测的边界

Q1-2 预测用于独立验证预测模型，不向 Q1-3 注入“预测任务”。Q1-3 使用 2376--2399 h 实际到达任务。

基础调度从附件可重构的 source-local immediate baseline 出发，采用：

`本地立即 -> 本地顺延 -> 必要迁移`。

2376 时刻必须计入此前任务形成的 carry-in，占用不能从零初始化。当前修正版 carry-in、一致性、GPU/IT/Facility/SLA/deadline 均已通过程序审计。

## 5. 文献支持边界

以下文献只支持 Q1 使用的统计思想，不声称它们给出了本题完全相同的模型。

### 5.1 Marked Poisson process

Taddy M A, Kottas A. Mixture Modeling for Marked Poisson Processes. Bayesian Analysis, 2012, 7(2): 335--362. DOI: 10.1214/12-BA711.

支持：把事件到达过程与多维 mark 联合建模；mark 可以保留条件依赖结构，而不必强行拆成独立边际。

本题吸收：`arrival process + (Region,TaskType,GPU,Duration) marks` 的建模思想。

### 5.2 计算工作负载的 Poisson 性需要由时间尺度与数据检验决定

Zou Q, Zhu Y, Tan Y, Chen W. Diagnosing the coexistence of Poissonity and self-similarity in memory workloads. Journal of Network and Computer Applications, 2022, 205: 103455. DOI: 10.1016/j.jnca.2022.103455.

支持：计算工作负载在特定时间尺度上可以呈现近 Poisson 特征，但不能把 Poisson 当成无条件先验；应检查到达间隔、独立性/自相关和尺度效应。

本题吸收：先做 Fano、GOF、ACF 和时段分组诊断，再接受齐次 Poisson；若数据不支持则不坚持该模型。

### 5.3 层级一致概率预测

Cohen M C, Zhang R, Jiao K. Data Aggregation and Demand Prediction. Operations Research, 2022, 70(5): 2597--2618. DOI: 10.1287/opre.2022.2301.

Bertani N, Jensen S T, Satopaa V A. Joint Bottom-up Method for Probabilistic Forecasting of Hierarchical Time Series. Operations Research, 2025, 73(6): 3260--3277. DOI: 10.1287/opre.2022.0113.

支持：聚合层级之间的一致性本身是需求预测中的重要结构；概率预测不应只看顶层单一误差。

本题吸收：从 Region×TaskType 底层统一聚合到 Region、TaskType、System，并同时评价各层误差和区间覆盖。

## 6. 论文写作建议

Q1 模型建立建议按以下顺序写：

1. 到达过程诊断：Fano + Poisson GOF + ACF；
2. 业务组成诊断：`TaskType × Region` 关联；
3. 条件资源诊断：`(GPU,Duration)|TaskType`；
4. 由三类结构自然得到标记复合 Poisson；
5. 与历史均值、lag-24、lag-168 做官方验证段比较；
6. 独立测试；
7. 实际任务进入基础调度机制。

不要从“我们选用复合 Poisson 模型”起笔。
