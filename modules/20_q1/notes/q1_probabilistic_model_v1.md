# Q1-A 概率预测模型 v1（待外部文献审查）

状态：`DRAFT / NEEDS_REVIEW`

本文件记录问题一前半部分“GPU需求统计与短期预测”的当前正式候选。该版本先落盘，后续依据文献审查与验证结果继续修改，不直接视为 FROZEN。

## 1. 模型定位

Q1-A 不建立机器学习预测器，也不把预测结果传入 Q1 后半段正式调度。预测只用于第 2376--2399 小时独立评价；正式基础调度仍使用该区间真实到达任务。

当前候选为：

**共轭贝叶斯更新的分层标记复合泊松过程 + 后验预测 Monte Carlo。**

其中概率模型负责描述任务生成机制，Monte Carlo 只用于联合后验预测分布与预测区间传播，不代替模型本身。

## 2. 总任务到达过程

设第 t 小时新到达任务总数为 N_t，采用

`N_t | lambda ~ Poisson(lambda)`。

数据审计支持该简化：小时任务数 Fano 因子约 0.97，Poisson 拟合未被拒绝，lag 1/24/168 自相关均弱。当前不引入季节项、LSTM 或高阶自回归结构。

## 3. Region × TaskType 联合标记

每个新任务携带 `(R,K)` 联合标记，直接建模

`pi_rk = P(R=r, K=k)`，且 `sum_r,k pi_rk = 1`。

由于 TaskType 与 SourceRegion 存在显著关联，不采用 `P(R)P(K)` 独立分解。由 Poisson splitting：

`N_rk,t | lambda, pi_rk ~ Poisson(lambda*pi_rk)`。

因此 18 个 Region×TaskType 子流由统一总到达率与联合组成概率产生，而不是分别拟合 18 条复杂时间序列。

## 4. GPU 与 Duration 条件标记

当前条件检验支持：给定 TaskType 后，GPU_Demand 与 Duration 对 SourceRegion 的附加依赖很弱；GPU 与 Duration 相关近 0。因此候选分解为

`P(R,K,G,D) = pi_rk * f_k^G(G) * f_k^D(D)`。

现有数据中三类 GPU_Demand 分别与以下离散均匀分布相容：

- RealTimeInference：1--7；
- BatchInference：4--23；
- AITraining：16--127。

Duration 三类均在 10--399 min 上与离散均匀分布相容。

正式实现需同时保留“参数化离散均匀 mark”和“历史经验 mark”两种版本做稳健性对照，避免将“未拒绝均匀分布”误写成已证明真实分布唯一为均匀。

## 5. GPU demand 与 GPU-hour

主预测量定义为某小时新到达任务的 GPU 总需求：

`Y_rk,t = sum_{j=1}^{N_rk,t} G_j,k`。

其条件均值、方差为复合泊松解析式：

`E[Y_rk,t | lambda,pi] = lambda*pi_rk*E[G|K=k]`，

`Var[Y_rk,t | lambda,pi] = lambda*pi_rk*E[G^2|K=k]`。

辅助统计量定义任务工作量 `X_i = G_i*D_i/60` (GPU-hour)，用于解释不同 TaskType 的真实计算量差异，但不与主预测量“新到达 GPU demand”混写。

## 6. 有限历史的不确定性

当前数据条数多，但时间跨度只有约 98 天，缺少支持季节/长期趋势的历史长度。因此通过减少时间自由参数并显式传播参数不确定性处理“历史有限”，而不是引入更复杂黑箱。

候选共轭更新：

- `lambda`：Gamma--Poisson；
- `pi`：Dirichlet--Multinomial。

当前先验候选为 Jeffreys/弱信息先验。由于样本量大，需在文献审查后判断是否继续保留 Jeffreys 形式，或改为更直观的经验贝叶斯/弱信息分层 Gamma 结构。

## 7. 后验预测 Monte Carlo

模型估计完成后，每次模拟依次抽样：

1. `lambda^(b)`；
2. `pi^(b)`；
3. `N_rk,t^(b)`；
4. 任务 GPU mark，必要时抽 Duration mark；
5. 聚合得到未来 24 h 的 `Y_rk,t^(b)` 与 GPU-hour。

Monte Carlo 输出点预测、中位数、95% 后验预测区间及 Region×TaskType 联合需求分布。均值/方差能解析求解时以解析式为主，模拟主要服务于分位数和联合不确定性传播。

## 8. 官方时间划分

- 0--2351：参数估计；
- 2352--2375：模型选择/调参验证；
- 模型确定后用 0--2375 重估；
- 2376--2399：一次性独立测试。

验证阶段至少比较：齐次 marked compound Poisson、增加 24 h 时间项的非齐次 Poisson、Negative Binomial/Poisson-Gamma 备选，以及历史均值、t-24、t-168 基准。只有验证结果支持时才增加时间结构。

## 9. 评价指标

点预测：MAE、RMSE、WAPE。

概率预测：PICP（区间覆盖率）、MPIW（平均区间宽度），并在文献审查后考虑加入 proper scoring rule（如 interval score / CRPS），避免概率预测只看点误差。

## 10. 必做可视化

- Region×TaskType 任务数热图；
- Region×TaskType GPU-hour 热图；
- 三类 GPU_Demand 分布与拟合 PMF；
- 三类 Duration 分布；
- GPU--Duration 关系/条件独立性结果；
- 每小时任务数直方图 + Poisson PMF；
- ACF 图（突出 1/24/168 h）；
- 2376--2399 预测曲线 + 真实值 + 95% 预测区间；
- 生成机制图：arrival count -> (Region,TaskType) -> GPU/Duration marks -> aggregate demand。

## 11. 当前风险 / NEEDS_REVIEW

- 聚合 Poisson 拟合良好不保证 18 个子流全部等离散；已知部分稀疏子流可能存在轻微偏离，需做层级诊断。
- Dirichlet 联合组成假设隐含 `pi_rk` 在当前短期内稳定，需用分段/滚动检验确认。
- 参数化均匀 mark 可能过度理想化，必须与经验 mark 版本做预测区间与误差对照。
- Jeffreys 先验在当前大样本下影响很小，是否值得正文保留需依据文献与表达简洁性决定。
- Monte Carlo 不是模型创新本身；若解析/闭式后验预测足以给出所需区间，则模拟只作为实现工具。
- 对企业实际运行最重要的风险是 regime shift；当前齐次模型需审查是否加入轻量在线更新/遗忘机制，而不破坏可解释性。
