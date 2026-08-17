# Q1 组成稳定性与子流 Poisson 门禁探针（2026-08-17）

状态：`DRAFT / NEEDS_REVIEW`

目的：补齐 `pi[r,k]` 固定组成与 Poisson splitting 的数据门禁。只使用训练段 `Hour=0..2351`，不形成新的验证集，也不回调 Test。

## 1. 18 个 Region×TaskType 子流 dispersion

对每个子流逐小时计数 `N[r,k,t]` 计算

`Dispersion = Var(N[r,k,t]) / E[N[r,k,t]]`。

结果范围：

- 最小：`0.944346`（RegionD × RealTimeInference）；
- 最大：`1.078970`（RegionD × AITraining）；
- 18 个子流整体均靠近 1。

按 Poisson dispersion 的卡方近似逐格检验，仅 `RegionD×AITraining` 原始 p 值约 `0.00807`；18 重比较 Bonferroni 门槛为 `0.00278`，因此 **0/18 子流在 Bonferroni 0.05 水平拒绝 Poisson dispersion**。

这不证明每个子流严格独立 Poisson，但说明没有数据证据要求把主模型整体升级成 Negative-Binomial/Quasi-Poisson。

## 2. 子流同时相关性

18 个子流小时计数的非对角 Pearson 相关：

- min = `-0.04606`；
- max = `0.04598`；
- mean absolute correlation = `0.01477`。

因此训练段没有明显的强 contemporaneous cell dependence。Poisson splitting 的独立子流近似可继续作为主模型；不为极弱相关强行引入高维 copula/多元状态模型。

## 3. `pi[r,k]` 的训练段组成稳定性

把 0--2351 h 只作诊断性地分成 4 个连续块，比较 `Block × RegionTaskType` 组成表：

- chi-square = `60.3735`；
- df = `51`；
- p = `0.17315`；
- Cramer's V = `0.02027`。

每个 cell 相对四块平均组成概率的最大绝对偏离不超过约 `0.00447`（0.447 个百分点）。

因此固定 `pi[r,k]` 在当前 24 h 短期预测口径下得到进一步支持。

## 4. 模型决策

当前不升级 Q1 主模型：

`N_t ~ Poisson(lambda)`

`P(R=r,K=k)=pi[r,k]`

`(G,D)|K=k ~ Fhat_GD[k]`

仍作为正式候选。

纠偏口径：

- 外部文献只支持“计算 workload 的 Poisson 性依赖时间尺度，应由数据检验决定”；
- 本题采用 Poisson 的证据来自本附件训练段 Fano/GOF/ACF 与本探针，不可写成“文献证明 AI 任务天然服从 Poisson”。

结果明细见 `modules/20_q1/results/q1_cell_dispersion_probe_20260817.csv`。
