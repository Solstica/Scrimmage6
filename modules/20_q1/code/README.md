# Q1 正式模型与编程手交接

状态：`DRAFT / NEEDS_REVIEW`

本文件是问题一当前正式实现规范。编程手以本文件和 `work/tasks/q1.md` 为当前真源；历史聊天、旧 notes 只作参考，不得覆盖本文件。

## 1. 问题一的任务拆分

Q1 由两个有先后逻辑但不相互传递预测误差的部分组成：

1. **Q1-A：GPU 需求统计与短期概率预测**
   - 使用 0--2351 h 做参数估计；
   - 2352--2375 h 做模型选择/验证；
   - 模型确定后用 0--2375 h 重新估计；
   - 对 2376--2399 h 做独立测试。
2. **Q1-B：最后 24 h 基础算力调度**
   - 不使用 Q1-A 的预测任务；
   - 直接读取 2376--2399 h 实际到达任务；
   - 允许任务在 2400--2405 h 继续执行或结清；
   - 任何任务不得占用第 2406 小时，必须满足 `finish <= 2406`。

Q1 不建立多目标优化模型，不使用主观权重，不引入电价、碳、新能源或储能作为调度目标；这些因素从 Q2 起再进入。

---

## 2. Q1-A：经验标记复合 Poisson 概率模型

### 2.1 预测对象

主要预测量：第 t 小时新到达任务的 GPU_Demand 总量。

对 Region r、TaskType k 定义

`Y[r,k,t] = sum(GPU_Demand_i for tasks with ArrivalHour=t, SourceRegion=r, TaskType=k)`。

辅助统计量：

`H[r,k,t] = sum(GPU_Demand_i * EstimatedDuration_min_i / 60)`，单位 GPU-hour。

GPU-hour 用于解释任务工作量，不与主预测量 GPU demand 混写。

### 2.2 总任务到达过程

设第 t 小时新到达任务总数为 `N_t`：

`N_t ~ Poisson(lambda)`。

当前数据依据：

- 小时任务数均值约 20.8333；
- 方差约 20.1815；
- Fano factor 约 0.9687；
- Poisson GOF 未被拒绝；
- lag 1、24、168 自相关均很弱；
- 24 h / weekday 分组未发现稳定到达率差异。

因此主模型不加入 LSTM、ARIMA、24 h/168 h 季节项或复杂动态状态。只有验证集显著改善时才能升级。

### 2.3 Region × TaskType 联合标记

每个到达任务携带联合标记 `(R,K)`：

`pi[r,k] = P(R=r, K=k)`，满足 `sum pi[r,k] = 1`。

由于 TaskType 与 SourceRegion 显著相关，不写成 `P(R)P(K)`。

由 Poisson splitting：

`N[r,k,t] ~ Poisson(lambda * pi[r,k])`。

18 个 Region×TaskType 子流由同一个总到达过程和联合组成概率产生，不分别拟合 18 条复杂时间序列。

### 2.4 GPU mark

主模型采用 TaskType 条件经验离散分布：

`G | K=k ~ Fhat_G[k]`。

经验 PMF：

`p_hat[k,g] = count(K=k and GPU_Demand=g) / count(K=k)`。

当前数据支持 GPU 主要由 TaskType 决定；给定 TaskType 后 SourceRegion 的附加影响很弱。

离散均匀分布只做简化/稳健性对照：

- RealTimeInference：1--7；
- BatchInference：4--23；
- AITraining：16--127。

不得把“未拒绝均匀分布”写成真实生成分布已被证明。

### 2.5 Duration mark 与降维

Duration 当前不进入主 GPU demand 点预测，但进入 GPU-hour 统计和 Q1-B overlap。

验证阶段比较两个版本：

- `D ~ Fhat_D`：全局经验 Duration 分布；
- `D | K=k ~ Fhat_D[k]`：按 TaskType 条件经验分布。

若第二种在验证集没有稳定收益，则正式模型采用统一 `Fhat_D`，避免无必要分层。

当前已有检验显示：给定 TaskType 后 Duration 对 SourceRegion 的附加依赖极弱；三种 TaskType 的 Duration 也非常接近。

### 2.6 复合 Poisson 解析量

对任一 `(r,k,t)`：

`E[Y_rkt] = lambda * pi[r,k] * E[G|K=k]`。

`Var[Y_rkt] = lambda * pi[r,k] * E[G^2|K=k]`。

系统、Region、TaskType 各层预测均由底层 `Y_rkt` 加总得到，必须保持严格加和一致：

`Y[r,t] = sum_k Y[r,k,t]`；

`Y[k,t] = sum_r Y[r,k,t]`；

`Y[t] = sum_r sum_k Y[r,k,t]`。

不得分别独立预测上层和下层后再出现总量不一致。

### 2.7 参数估计

主模型先使用频率估计：

`lambda_hat = total_arrivals / number_of_hours`；

`pi_hat[r,k] = count(r,k) / total_arrivals`；

`Fhat_G[k]`、`Fhat_D`/`Fhat_D[k]` 均由经验频率得到。

Gamma-Poisson / Dirichlet Bayesian 更新不是当前主模型必需部分。若后续需要显式参数不确定性或企业在线更新，可作为扩展加入，但不能因为形式高级而增加正文复杂度。

### 2.8 预测分布与数值方法

均值与方差优先使用解析式。

完整离散预测分布优先实现以下任一方式：

1. 概率母函数/FFT；
2. 等价离散递推；
3. Monte Carlo（只用于联合分位数、预测带和可视化）。

若 Monte Carlo 实现更稳定，可采用固定随机种子与 `B >= 10000` 次模拟；不得把 Monte Carlo 本身包装成模型创新。

### 2.9 候选模型比较

验证区间 2352--2375 至少比较：

- M0：历史均值基准；
- M1：`t-24` 季节朴素；
- M2：`t-168` 季节朴素；
- M3：当前齐次经验标记复合 Poisson；
- M4：仅在需要时增加 24 h 非齐次到达率；
- M5：仅在明显过离散时启用 Negative Binomial / quasi-Poisson 备选。

模型选择原则：验证指标没有稳定改善时，保留更简单模型。

### 2.10 评价指标

点预测：

- MAE；
- RMSE；
- WAPE。

若输出概率区间，再计算：

- 90% / 95% PICP；
- MPIW 或 normalized interval width；
- 可选 interval score。

2376--2399 是一次性独立测试；测试结果不得返回用于修改模型。

---

## 3. Q1-B：基础调度机制模型

### 3.1 模型性质

Q1-B 是规则/状态演化模型，不是多目标优化模型。

目标是根据题面给定的任务规则与资源约束，把 2376--2399 h 实际到达任务形成一个合法基础排程，并展示甘特图和区域 GPU 利用率。

### 3.2 baseline 机制

当前数据审计已验证：若所有任务均

- `ExecutionRegion = SourceRegion`；
- `StartHour = ArrivalHour`；

并使用分钟级 Duration 与小时实际 overlap 重算，能够在浮点误差范围内复现 `Baseline_AI_IT_Load_MW`。

因此该规则作为已有基准运行状态的解释：**本地、到达即执行**。

Q1-B 从该机制出发；只有发生硬约束冲突时才做必要调整。

### 3.3 三类任务规则

RealTimeInference：

- 到达即开工：`StartHour = ArrivalHour`；
- 不能通过延迟处理冲突；
- 执行 Region 必须满足 `NetworkLatency <= 20 ms`。

BatchInference：

- `StartHour >= ArrivalHour`；
- 允许等待；
- Region 必须满足 `NetworkLatency <= 80 ms`；
- 必须在 LatestFinish/2406 之前完成。

AITraining：

- `StartHour >= ArrivalHour`；
- 允许等待；
- Region 必须满足 `NetworkLatency <= 150 ms`；
- 必须在 LatestFinish/2406 之前完成。

全部任务：

- NonPreemptive；
- 不可拆分；
- 执行过程中 Region 固定；
- 不得占用 `[2406,2407)`。

### 3.4 候选域原则

不得人为缩小搜索域。

对任务 i，只能因明确硬不可行删除候选，例如：

- `s < EarliestStart_i`；
- `s + p_i > LatestFinish_i`；
- `s + p_i > 2406`；
- `Latency(SourceRegion_i,r) > MaxLatency_i`；
- 单个任务自身 GPU/IT/Facility 需求已超过某 Region 的绝对上限。

禁止自行增加：

- “最多延迟 24 h”；
- “只查最近 3 个区域”；
- “只保留最低价附近若干时段”；
- 固定 top-K 候选。

GPU/IT/Facility 的多任务冲突属于联合运行状态，不得因为一个临时排程满载就永久删除该候选。

### 3.5 小时 overlap

若整数小时开工 `s_i`，持续时间 `p_i = Duration_min/60`，与小时 `[t,t+1)` 的重叠为：

`omega(i,s,t) = max(0, min(t+1, s+p_i) - max(t,s))`。

必须满足数值检查：

`sum_t omega(i,s,t) == p_i`（浮点容差内）。

GPU-hour：

`GPUUse[r,t] = sum_i GPU_i * omega_i,t`。

AI IT 能量/1h平均功率：

`AI_IT[r,t] = sum_i PowerMap[type_i] * GPU_i * omega_i,t`。

总 IT：

`IT[r,t] = NonAI_IT_Load[r,t] + AI_IT[r,t]`。

设施功率：

`Facility[r,t] = PUE[r] * IT[r,t]`。

### 3.6 每小时硬约束

必须同时检查：

- GPU capacity；
- Max IT power；
- Max facility power；
- Network latency；
- Earliest/Latest finish；
- `finish <= 2406`。

注意题面 GPU 容量按实际 overlap 的 GPU-hour 口径实现，不自行下沉到分钟级瞬时并发约束。

### 3.7 冲突处理

**当前尚未冻结唯一冲突处理顺序。** 编程手先实现可插拔的确定性规则框架，至少支持：

- 本地立即执行 baseline；
- 对弹性任务按 earliest feasible start 顺延；
- 在本地无法满足硬约束时枚举全部 SLA 可行 Region；
- 不使用价格、碳、新能源权重。

不同规则必须使用同一可行性检查器，并输出对比结果。最终论文采用哪一条规则由实际可行率、等待/迁移统计和题意解释共同决定。

---

## 4. 编程手必须实现的文件

建议结构，不新建平行目录：

`modules/20_q1/code/q1_data_audit.py`
- 读取数据；
- 生成 0--2406 标准时间索引；
- 输出所有统计检验与 mark 分布；
- 复核已有审计数值。

`modules/20_q1/code/q1_forecast.py`
- 实现 M0--M5 候选；
- 执行 train/validation/refit/test；
- 输出点预测与概率区间。

`modules/20_q1/code/q1_scheduler.py`
- 实现 overlap；
- baseline 重构；
- 规则调度；
- 全部硬约束检查；
- 生成 2376--2405 排程。

`modules/20_q1/code/q1_make_outputs.py`
- 汇总 tables/figures/processed data；
- 不在脚本中手写论文结论。

如程序手希望合并脚本，可以，但必须保持上述逻辑模块可独立测试。

---

## 5. 必须输出的机器可读产物

放入 `modules/20_q1/data/processed/`：

- `hourly_arrivals.csv`：hour、total count、total GPU、total GPU-hour、各 Region/Type 分量；
- `mark_distribution_gpu.csv`；
- `mark_distribution_duration.csv`；
- `forecast_validation.csv`；
- `forecast_test_2376_2399.csv`；
- `schedule_2376_2405.csv`：TaskID、SourceRegion、ExecutionRegion、ArrivalHour、StartHour、FinishTime、GPU、Duration、TaskType、Latency；
- `gpu_utilization_2376_2405.csv`；
- `constraint_audit.csv`。

放入 `modules/20_q1/tables/`：

- 统计汇总表；
- 模型验证/测试误差表；
- 基础调度结果统计表。

---

## 6. 必须生成的图

放入 `modules/20_q1/figures/`，可编辑源放 `figures/editable/`：

1. Region×TaskType 任务数热图；
2. Region×TaskType GPU-hour 热图；
3. 三类 GPU_Demand 经验分布；
4. Duration 分布及全局/分类型对照；
5. 小时任务数直方图 + Poisson PMF；
6. ACF 图，明确标出 lag 1/24/168；
7. 0--2399 到达任务数与到达 GPU demand 时序图；
8. 2376--2399 预测值 + 实际值 + 概率区间；
9. 最后 24 h/收尾期任务甘特图；
10. 各 Region GPU utilization 曲线。

不要在图中写未经 registry 冻结的结论性文字。

---

## 7. 强制验收门禁

### Q1-A

- 训练/验证/测试切分严格无泄漏；
- 测试集仅在模型冻结后计算一次；
- 预测各层级严格加和一致；
- M3 至少与历史均值、t-24、t-168 比较；
- 若采用复杂扩展，必须在验证集有稳定收益；
- 经验 GPU mark 与离散均匀简化版至少做一次稳健性对照。

### Q1-B

- baseline AI IT 重构误差应达到浮点容差量级；
- 每任务 `sum(omega)=Duration/60`；
- 100% 任务满足 SLA 和完成时限；
- GPU/IT/Facility 约束无违规；
- 2406 无计算任务占用；
- 所有调度调整均可追溯到明确硬约束冲突，不能因隐含成本/碳偏好调整。

---

## 8. 结果状态

当前所有新结果先写 `DRAFT / NEEDS_REVIEW`。

只有代码可重复运行、门禁通过、建模手复核后，才进入 `modules/20_q1/results/registry.csv` 并逐步升级为 `VALIDATED` / `FROZEN + CHECKED`。

正文 `q1.tex` 当前仍是模板，不要在结果未冻结前直接填入关键数值。
