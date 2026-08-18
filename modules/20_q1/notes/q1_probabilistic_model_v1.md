# Q1-A 概率预测模型 v1（已被正式实现规范取代）

状态：`SUPERSEDED / LEGACY_NOT_CURRENT`

> 当前实现真源已经迁移到 `modules/20_q1/code/README.md` 与 `work/tasks/q1.md`。本文件保留用于记录路线演化，不得作为编程手当前实现依据。主要变化：主模型已从“共轭贝叶斯 + 后验 Monte Carlo”收敛为“经验标记复合 Poisson”；Gamma-Poisson/Dirichlet 仅保留为可选扩展；GPU mark 改用 TaskType 条件经验分布，Monte Carlo 降级为概率区间数值工具。

## 1. 模型定位（历史版本）

Q1-A 不建立机器学习预测器，也不把预测结果传入 Q1 后半段正式调度。预测只用于第 2376--2399 小时独立评价；正式基础调度仍使用该区间真实到达任务。

历史候选为：

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

历史版本曾候选分解为

`P(R,K,G,D) = pi_rk * f_k^G(G) * f_k^D(D)`。

现有数据中三类 GPU_Demand 与离散均匀分布相容，但正式版本已改为 TaskType 条件经验 GPU mark；离散均匀只作简化对照。

Duration 三类均在 10--399 min 上与离散均匀分布相容；正式版本要求在验证集比较全局经验分布与 TaskType 条件经验分布。

## 5. GPU demand 与 GPU-hour

主预测量定义为某小时新到达任务的 GPU 总需求：

`Y_rk,t = sum_{j=1}^{N_rk,t} G_j,k`。

其条件均值、方差为复合泊松解析式：

`E[Y_rk,t | lambda,pi] = lambda*pi_rk*E[G|K=k]`，

`Var[Y_rk,t | lambda,pi] = lambda*pi_rk*E[G^2|K=k]`。

辅助统计量定义任务工作量 `X_i = G_i*D_i/60` (GPU-hour)。

## 6. 历史版本中的有限历史处理

历史候选曾采用：

- `lambda`：Gamma--Poisson；
- `pi`：Dirichlet--Multinomial。

正式版本考虑到训练阶段已有约 2352 个小时和约 4.9 万个任务，先验影响很小，因此这部分不再作为主模型必需结构，只保留为企业在线更新/参数不确定性扩展。

## 7. 历史版本中的 Monte Carlo

历史版本计划从 `lambda`、`pi` 后验与 mark 分布重复抽样得到未来 24 h 联合分布。正式版本仍允许 Monte Carlo，但只作为完整离散分位数与可视化的数值实现之一；解析均值/方差优先。

## 8. 官方时间划分

- 0--2351：参数估计；
- 2352--2375：模型选择/调参验证；
- 模型确定后用 0--2375 重估；
- 2376--2399：一次性独立测试。

## 9. 评价指标

点预测：MAE、RMSE、WAPE。

概率预测：PICP、MPIW/interval score（若输出区间）。

## 10. 历史可视化候选

- Region×TaskType 任务数热图；
- Region×TaskType GPU-hour 热图；
- 三类 GPU_Demand 分布；
- Duration 分布；
- 每小时任务数直方图 + Poisson PMF；
- ACF；
- 2376--2399 预测曲线 + 真实值 + 区间。

以上图表已继承到当前正式实现规范。
