# Q1 正式模型与编程手交接

状态：`DRAFT / NEEDS_REVIEW`

本文件是问题一当前正式实现规范。编程手以本文件和 `work/tasks/q1.md` 为当前真源；历史聊天、旧 notes 只作参考，不得覆盖本文件。

## 1. 问题一的任务拆分与范围

Q1 由两个有先后逻辑但不相互传递预测误差的部分组成：

1. **Q1-A：GPU 需求统计与 24 h 短期概率预测**
   - 使用 0--2351 h 做参数估计与模型假设诊断；
   - 2352--2375 h 做唯一的模型选择/验证；
   - 模型确定后用 0--2375 h 重新估计；
   - 对 2376--2399 h 做一次性独立测试。
2. **Q1-B：最后 24 h 基础算力调度**
   - 不使用 Q1-A 的预测任务；
   - 直接读取 2376--2399 h 实际到达任务；
   - 允许任务在 2400--2405 h 继续执行或结清；
   - 任何任务不得占用第 2406 小时，必须满足 `finish <= 2406`。

Q1-A 的定位是**短期需求统计基线/参考模型**。它只需解释当前约 98 天历史中能够可靠识别的结构，并完成未来 24 h 预测评价；不承担长期企业负荷预测，不为本问增加长期趋势、概念漂移、在线遗忘或复杂动态状态模型。

Q1 不建立多目标优化模型，不使用主观权重，不引入电价、碳、新能源或储能作为调度目标；这些因素从 Q2 起再进入。

---

## 2. Q1-A：结构化经验标记复合 Poisson 概率模型

### 2.1 模型总体结构

Q1-A 不是单一的 `N_t ~ Poisson(lambda)`。Poisson 只描述最外层“每小时来了多少个任务”。完整任务生成结构为：

`Arrival count -> (SourceRegion, TaskType) -> (GPU_Demand, Duration)`。

数学上写为：

1. `N_t ~ Poisson(lambda)`；
2. `(R_i,K_i) ~ Categorical(pi[r,k])`；
3. `(G_i,D_i) | K_i=k ~ Fhat_GD[k]`，即按 TaskType 保留 `(GPU_Demand, EstimatedDuration)` 的联合经验 mark。

因此单任务联合结构写成：

`P(R=r,K=k,G=g,D=d) = pi[r,k] * fhat_GD[k](g,d)`。

这三层分别对应：

- **到达强度**：一小时来多少任务；
- **业务组成**：任务来自哪个 Region、属于哪种 TaskType；
- **资源重量**：该类任务通常需要多少 GPU、持续多长时间。

### 2.2 预测对象

主要预测量：第 t 小时新到达任务的 GPU_Demand 总量。

对 Region r、TaskType k 定义：

`Y[r,k,t] = sum(GPU_Demand_i for tasks with ArrivalHour=t, SourceRegion=r, TaskType=k)`。

辅助统计量：

`H[r,k,t] = sum(GPU_Demand_i * EstimatedDuration_min_i / 60)`，单位 GPU-hour。

GPU-hour 用于解释任务工作量，不与主预测量 GPU demand 混写；运行中的 GPU utilization 由 Q1-B 的任务状态演化得到，也不与 arrival demand 混写。

### 2.3 总任务到达过程

设第 t 小时新到达任务总数为 `N_t`：

`N_t ~ Poisson(lambda)`。

当前数据依据：

- 小时任务数均值约 20.8333；
- 方差约 20.1815；
- Fano factor 约 0.9687；
- Poisson GOF 未被拒绝；
- lag 1、24、168 自相关均很弱；
- 24 h / weekday 分组未发现稳定到达率差异。

因此当前把一般时变强度 `lambda_t` 降维为常数 `lambda`。这是数据检验后的简化，不是无依据假设。

Q1-A 只做未来 24 h 短期预测，因此不继续为 98 天历史建立长期季节、长期趋势、概念漂移或复杂动态状态模型。

### 2.4 Region × TaskType 联合标记

每个到达任务携带联合标记 `(R,K)`：

`pi[r,k] = P(R=r, K=k)`，满足 `sum pi[r,k] = 1`。

由于 TaskType 与 SourceRegion 显著相关（现有审计 Cramér's V 约 0.434），不得写成 `P(R)P(K)`。

条件于总任务数 `N_t=n`：

`{N[r,k,t]} | N_t=n ~ Multinomial(n, pi)`。

由 Poisson splitting：

`N[r,k,t] ~ Poisson(lambda * pi[r,k])`。

18 个 Region×TaskType 子流由同一个总到达过程和联合组成概率产生，不分别拟合 18 条复杂时间序列。

### 2.5 任务资源联合 mark

当前主模型不把 GPU 和 Duration 强行拆成严格独立变量。

对每个 TaskType k，保留历史任务对：

`(G,D) | K=k ~ Fhat_GD[k]`。

其中 `Fhat_GD[k]` 是训练数据中该 TaskType 的 `(GPU_Demand, EstimatedDuration_min)` 联合经验分布/经验样本集合。

这样做的理由：

- TaskType 对 GPU_Demand 影响很强；
- 给定 TaskType 后，SourceRegion 对 GPU 与 Duration 的附加影响都极弱，因此无需再按 Region 细分 mark；
- GPU 与 Duration 的线性相关接近 0，但“相关接近 0”不能严格推出独立，因此直接保留联合经验对更稳妥，而且不增加待估参数。

对于主 GPU demand 的边际计算，使用：

`G | K=k ~ Fhat_G[k]`，即 `Fhat_GD[k]` 的 GPU 边际经验分布。

离散均匀分布只做简化/稳健性对照：

- RealTimeInference：GPU 1--7；
- BatchInference：GPU 4--23；
- AITraining：GPU 16--127；
- Duration 三类均覆盖约 10--399 min。

不得把“未拒绝均匀分布”写成真实生成分布已被证明。

### 2.6 复合 Poisson 解析量与解释

对任一 `(r,k,t)`：

`E[Y_rkt] = lambda * pi[r,k] * E[G|K=k]`。

`Var[Y_rkt] = lambda * pi[r,k] * E[G^2|K=k]`。

该均值分解必须在结果解释中保留：

`GPU demand = overall arrival intensity × region-type composition × per-task GPU intensity`。

即：

- `lambda` 说明总体来多少任务；
- `pi[r,k]` 说明这些任务是什么区域/业务组成；
- `E[G|K=k]` 说明不同业务单任务 GPU 强度。

GPU-hour 辅助量：

`H[r,k,t] = sum_i G_i * D_i/60 * I(R_i=r,K_i=k)`。

其均值为：

`E[H_rkt] = lambda * pi[r,k] * E[G*D/60 | K=k]`。

这里直接由联合经验 mark 估计 `E[G*D/60|K=k]`，不强行使用 `E[G]E[D]`。

系统、Region、TaskType 各层预测均由底层 `Y_rkt` 加总得到，必须保持严格加和一致：

`Y[r,t] = sum_k Y[r,k,t]`；

`Y[k,t] = sum_r Y[r,k,t]`；

`Y[t] = sum_r sum_k Y[r,k,t]`。

不得分别独立预测上层和下层后再出现总量不一致。

### 2.7 参数估计与必要诊断

主模型使用频率估计：

`lambda_hat = total_arrivals / number_of_hours`；

`pi_hat[r,k] = count(r,k) / total_arrivals`；

`Fhat_GD[k]` 由训练区间该 TaskType 的历史 `(G,D)` 样本直接构造。

Gamma-Poisson / Dirichlet Bayesian 更新不是当前主模型必需部分；当前任务样本量足以支持频率估计。

在 0--2351 **训练区间内部**只做以下假设诊断，不把它们作为额外模型选择验证：

1. `pi[r,k]` 是否存在明显时间不稳定；
2. 18 个 Region×TaskType 子流的 Fano/dispersion 是否出现明显异常；
3. GPU/Duration 条件关系是否与现有审计一致。

这些诊断仅用于判断主模型假设是否明显失效。若没有明显异常，保持模型简洁；不得因此在训练区间内部另外构造 pseudo-validation 或 rolling model-selection 流程。

### 2.8 预测分布与数值方法

均值与方差优先使用解析式。

完整离散预测分布可实现以下任一方式：

1. 概率母函数/FFT；
2. 等价离散递推；
3. Monte Carlo（用于联合分位数、预测带和可视化）。

若 Monte Carlo 实现更稳定，可采用固定随机种子与 `B >= 10000` 次模拟；模拟时从 `Fhat_GD[k]` 直接重采样历史 `(GPU,Duration)` 对。不得把 Monte Carlo 本身包装成模型创新。

### 2.9 官方数据切分与候选模型比较

严格遵守：

- `0--2351`：参数估计 + 假设诊断；
- `2352--2375`：唯一模型选择/验证区间；
- 模型冻结后 `0--2375`：重新估计；
- `2376--2399`：一次性独立测试。

**禁止**在 0--2351 内再切 rolling/pseudo-backtest 作为模型选择依据；训练内部的分块图或稳定性统计只能作为描述性诊断，不能参与模型选择或调参。

验证阶段只保留必要比较：

- M0：历史均值基准；
- M1：`t-24` 季节朴素；
- M2：`t-168` 季节朴素；
- M3：当前结构化经验标记复合 Poisson。

只有当官方验证集明确显示主模型的 Poisson/区间假设失真时，才考虑局部 24 h 非齐次 Poisson、quasi-Poisson 或 Negative Binomial；不预先为 Q1 增加复杂模型。

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
- 输出所有统计检验与联合 mark 分布；
- 复核已有审计数值。

`modules/20_q1/code/q1_forecast.py`
- 实现 M0--M3；
- 执行严格 train/validation/refit/test；
- 输出点预测与概率区间；
- 只有官方验证显示必要时再增加局部备选分布。

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
- `mark_joint_gpu_duration_by_type.csv`；
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
2. Region×TaskType GPU-hour 热图，与任务数图并列；
3. 三类 GPU_Demand 经验分布；
4. `(GPU,Duration)|TaskType` 联合关系/二维统计图；
5. Duration 分布及全局/分类型对照；
6. 小时任务数直方图 + Poisson PMF；
7. ACF 图，明确标出 lag 1/24/168；
8. 0--2399 到达任务数与到达 GPU demand 时序图；
9. 2376--2399 预测值 + 实际值 + 概率区间；
10. 最后 24 h/收尾期任务甘特图；
11. 各 Region GPU utilization 曲线。

不要在图中写未经 registry 冻结的结论性文字。

---

## 7. 强制验收门禁

### Q1-A

- 训练/验证/测试切分严格无泄漏；
- 0--2351 内部诊断不得充当额外模型选择验证；
- 测试集仅在模型冻结后计算一次；
- 预测各层级严格加和一致；
- 主模型至少与历史均值、t-24、t-168 比较；
- 若采用复杂扩展，必须由官方验证集给出明确必要性；
- 经验 GPU mark 与离散均匀简化版至少做一次稳健性对照；
- 联合 `(GPU,Duration)|TaskType` mark 能够被复现并用于 GPU-hour/模拟输出。

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