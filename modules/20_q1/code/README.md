# Q1 正式模型与编程手交接

状态：`DRAFT / NEEDS_REVIEW`

本文件是问题一当前正式实现规范。编程手以本文件和 `work/tasks/q1.md` 为当前真源；历史聊天、旧 notes 只作参考，不得覆盖本文件。

## 1. 问题一完整结构

Q1 包含三个连续任务：

1. **Q1-1：GPU 需求统计与结构识别**：比较不同 Region、不同 TaskType 的任务数、GPU_Demand、Duration、GPU-hour，识别数据之间的关联和条件关系；
2. **Q1-2：24 h 短期 GPU 需求概率预测**：把 Q1-1 提取出的结构嵌入标记复合 Poisson 模型，对 2376--2399 h 做独立预测评价；
3. **Q1-3：基础算力调度**：不使用预测任务，直接对 2376--2399 h 实际到达任务形成合法排程，并输出最后 24 h + drain 的甘特图和区域 GPU 利用率。

逻辑链：

`统计结构识别 -> 短期需求预测 -> 实际任务进入基础运行机制 -> GPU 利用率`。

Q1-1 **不是分类问题**：`TaskType` 和 `SourceRegion` 已由附件给定；本部分负责通过统计检验提取结构，为 Q1-2 的概率分解提供依据。

Q1 不建立多目标优化模型，不使用主观权重，不引入电价、碳、新能源或储能作为调度目标；这些因素从 Q2 起再进入。

---

## 2. Q1-1：GPU 需求统计与结构识别

### 2.1 三个统计层次

至少同时统计：

- 任务数；
- GPU_Demand；
- `GPU-hour = GPU_Demand * EstimatedDuration_min / 60`。

重点说明“任务数占比 != GPU 需求占比 != 计算工作量占比”。当前审计显示 AITraining 任务数约占 1/3，但贡献约 80% GPU-hour，因此 GPU-hour 是解释真实计算负荷的重要辅助量。

### 2.2 Region × TaskType 结构

直接统计联合分布

`pi[r,k] = P(SourceRegion=r, TaskType=k)`。

当前已有结果显示 TaskType 与 SourceRegion 存在明显关联（Cramér's V≈0.434）：RT 主要集中在 A/B/C，Training 主要集中在 D/E/F，Batch 相对分散。因此后续预测不能写成 `P(R)P(K)`。

### 2.3 GPU / Duration 条件关系

当前检验支持：

- 给定 TaskType 后，SourceRegion 对 GPU_Demand 的附加影响很弱；
- 给定 TaskType 后，SourceRegion 对 Duration 的附加影响很弱；
- GPU 与 Duration 的线性相关接近 0，但这不能推出严格独立。

因此主实现优先保留联合经验 mark：

`(GPU_Demand, EstimatedDuration) | TaskType=k ~ Fhat_GD[k]`。

主 GPU demand 预测使用该联合分布的 GPU 边际；GPU-hour 使用完整 `(G,D)` 联合 mark。离散均匀分布只作为参数化简化对照，不能写成唯一真实分布。

### 2.4 必做图表

- Region×TaskType 任务数热图；
- Region×TaskType GPU-hour 热图；
- 三类 GPU_Demand 经验分布；
- Duration 全局/分类型分布；
- GPU-Duration 联合/散点或二维统计图；
- 小时任务数直方图 + Poisson PMF；
- ACF 图（lag 1/24/168）。

---

## 3. Q1-2：结构化标记复合 Poisson 短期预测

### 3.1 模型定位

这是一个**24 h 短期基线/参考预测模型**。不研究长期企业趋势、概念漂移、在线遗忘或复杂状态切换；本问只预测紧邻历史的 2376--2399 h。

### 3.2 总到达过程

设第 t 小时新到达任务总数为 `N_t`：

`N_t ~ Poisson(lambda)`。

当前数据依据：小时任务数均值约 20.8333、方差约 20.1815、Fano≈0.9687，Poisson GOF 未被拒绝，lag 1/24/168 自相关很弱，24 h / weekday 分组未发现稳定差异。因此主模型不加入 LSTM、ARIMA、季节状态或长期动态参数。

### 3.3 联合业务标记

每个到达任务先抽取 `(R,K)`：

`P(R=r,K=k)=pi[r,k]`，`sum pi[r,k]=1`。

由 Poisson splitting：

`N[r,k,t] ~ Poisson(lambda*pi[r,k])`。

18 个 Region×TaskType 子流由同一个总到达过程和联合组成概率产生，不分别拟合 18 条复杂时间序列。

### 3.4 资源 mark

给定 TaskType 后采用联合经验 mark：

`(G,D)|K=k ~ Fhat_GD[k]`。

完整任务生成关系写为：

`P(R,K,G,D) = pi[r,k] * fhat_GD[k](g,d)`。

这把 Q1-1 中识别出的关系直接嵌入预测模型：Region 与 TaskType 联合决定业务组成；TaskType 决定主要资源重量；不额外按 Region 细分 GPU/Duration。

### 3.5 预测量

主要预测量：

`Y[r,k,t] = sum GPU_Demand_i`，其中任务满足 `ArrivalHour=t, SourceRegion=r, TaskType=k`。

辅助工作量：

`H[r,k,t] = sum GPU_Demand_i * EstimatedDuration_i / 60`，单位 GPU-hour。

复合 Poisson 解析量：

`E[Y_rkt] = lambda * pi[r,k] * E[G|K=k]`；

`Var[Y_rkt] = lambda * pi[r,k] * E[G^2|K=k]`。

必须保留解释：

`GPU demand = overall arrival intensity × region-type composition × per-task GPU intensity`。

系统、Region、TaskType 各层预测均由底层 `Y_rkt` 加总，保持严格一致。

### 3.6 参数估计与数值方法

主模型使用频率估计：

- `lambda_hat = total_arrivals / number_of_hours`；
- `pi_hat[r,k] = count(r,k) / total_arrivals`；
- `Fhat_GD[k]` 由历史任务对的经验频率得到。

Gamma-Poisson / Dirichlet Bayesian 更新不是主模型必需部分；Monte Carlo 只作为联合分位数/预测带的数值工具。均值、方差优先解析计算；完整离散预测分布可用 FFT、离散递推或固定随机种子的 Monte Carlo。

### 3.7 训练 / 验证 / 测试纪律

严格执行：

- `0--2351`：参数估计与模型假设诊断；
- `2352--2375`：**唯一模型选择/验证区间**；
- 模型冻结后 `0--2375`：重估参数；
- `2376--2399`：一次性独立测试。

禁止在 `0--2351` 内再切 rolling/pseudo-backtest 作为额外选模或调参依据。训练内部可以检查 `pi[r,k]` 分段稳定性和子流 dispersion，但这些只能用于判断当前假设是否明显失效，不能形成第二套验证集。

验证至少比较：历史均值、t-24、t-168、当前齐次标记复合 Poisson。只有官方验证区间明确支持时才增加 24 h 非齐次 Poisson 或局部 quasi-Poisson/dispersion 扩展。

评价：MAE、RMSE、WAPE；若输出概率区间，再给 PICP、MPIW/interval score。

---

## 4. Q1-3：基础算力调度机制

### 4.1 模型性质

Q1-3 是规则/状态演化模型，不是多目标优化模型。输入是 2376--2399 h **实际到达任务**，不是 Q1-2 预测结果。

### 4.2 baseline 机制

当前数据审计已验证：若所有任务均

- `ExecutionRegion = SourceRegion`；
- `StartHour = ArrivalHour`；

并使用分钟级 Duration 与小时实际 overlap 重算，可以在浮点误差范围内复现 `Baseline_AI_IT_Load_MW`。

因此基础运行解释为：**本地、到达即执行**。只有发生硬约束冲突时才做必要调整。

### 4.3 任务规则

RealTimeInference：`StartHour=ArrivalHour`，Region 满足 `Latency<=20 ms`。

BatchInference：允许等待，Region 满足 `Latency<=80 ms`，必须在 LatestFinish/2406 前完成。

AITraining：允许等待，Region 满足 `Latency<=150 ms`，必须在 LatestFinish/2406 前完成。

全部任务：NonPreemptive、不可拆分、运行中 Region 固定、不得占用 `[2406,2407)`。

### 4.4 候选域

不得人为缩小搜索域。只能因为题面硬不可行删除 `(region,start)` 候选，例如 deadline、2406 边界、MaxLatency、单任务自身绝对容量超限。禁止“最多延迟24h”“最近3区”“top-K时段”等人为窗口。

### 4.5 overlap 与资源映射

若整数小时开工 `s_i`、持续时间 `p_i=Duration_min/60`：

`omega(i,s,t)=max(0,min(t+1,s+p_i)-max(t,s))`。

必须验证 `sum_t omega(i,s,t)=p_i`。

`GPUUse[r,t] = sum_i GPU_i * omega_i,t`；

`AI_IT[r,t] = sum_i PowerMap[type_i] * GPU_i * omega_i,t`；

`IT[r,t] = NonAI_IT_Load[r,t] + AI_IT[r,t]`；

`Facility[r,t] = PUE[r] * IT[r,t]`。

统一检查 GPU、IT、Facility、Latency、Earliest/LatestFinish、`finish<=2406`。

### 4.6 冲突处理

唯一规则顺序尚未冻结。编程手先实现可插拔确定性规则：

- baseline 本地立即执行；
- 对弹性任务 earliest-feasible 顺延；
- 本地无法满足硬约束时枚举全部 SLA 可行 Region；
- 不使用价格、碳、新能源权重。

所有规则使用同一可行性检查器，并输出对比结果。

---

## 5. 编程文件与机器可读产物

建议代码：

- `q1_data_audit.py`：Q1-1 统计结构与模型诊断；
- `q1_forecast.py`：Q1-2 train/validation/refit/test；
- `q1_scheduler.py`：Q1-3 overlap、baseline、规则调度、constraint audit；
- `q1_make_outputs.py`：统一输出图表与 processed data。

processed data 至少包括：

- `hourly_arrivals.csv`；
- `mark_distribution_gpu.csv`；
- `mark_distribution_duration.csv`；
- `mark_joint_gpu_duration_by_type.csv`；
- `forecast_validation.csv`；
- `forecast_test_2376_2399.csv`；
- `schedule_2376_2405.csv`；
- `gpu_utilization_2376_2405.csv`；
- `constraint_audit.csv`。

所有新结果先 `DRAFT / NEEDS_REVIEW`；只有代码可重复、门禁通过、建模手复核后再升级。正文 `q1.tex` 暂不写未经冻结的正式数值。
