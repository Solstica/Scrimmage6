# Q4 正式模型规范：联合算力—储能—电力调度与六指标折中

状态：`DRAFT / NEEDS_REVIEW`

本文件是 Q4 当前模型真源。后续代码、结果和正文若与本文件冲突，以本文件为准并回到 `DRAFT` 重新验证。

## 1. 已锁定的底层模型

Q4 建立 **joint workload--energy--storage scheduling**：任务执行区域与开工时刻、储能充放电、新能源利用以及区域购售电共同优化。

完整因果关系为：

`任务时空决策 x -> AI IT -> Facility Load -> Renewable/BESS/Grid recourse -> 六类评价指标`。

不得把 Q2 的任务排程固定后再单向调用 Q3。Q2 的时空柔性与 Q3 的储能时间柔性会争用同一份逐时新能源和购电容量，因此 Q4 必须联合求解。

### 1.1 任务决策

对任务 i 的完整合法 placement `(r,s)` 定义二元变量 `x[i,r,s]`。完整合法域保留：

- RT：`s_i = ArrivalHour_i`，区域枚举全部满足 `NetworkLatency <= MaxLatency_i` 的区域；
- Batch / Training：`s_i >= ArrivalHour_i`，且 `s_i + p_i <= LatestFinishHour_i`、`s_i + p_i <= 2406`；
- 任务不可拆分、不可抢占、运行期间区域固定；
- 不允许人为 top-k 区域、最大等待窗口或候选时间裁剪。

### 1.2 计算与能源耦合

任务在小时 t 的重叠量为

`omega(i,s,t)=max(0,min(t+1,s+p_i)-max(t,s))`。

AI IT、总 IT 和设施负荷统一按附件口径重算：

`AI_IT[r,t] = sum alpha[k_i] * GPU_i * omega(i,s,t) * x[i,r,s]`，

`IT_Load[r,t] = NonAI_IT_Load[r,t] + AI_IT[r,t]`，

`Facility_Load[r,t] = PUE[r] * IT_Load[r,t]`。

能源层显式优化新能源直接消纳、储能充放电、SOC、购电和售电，并满足统一能量平衡、SOC 上下限、充放电功率、效率、终端 SOC、MaxGridImport / MaxGridExport 等硬约束。

## 2. 已锁定的求解框架

完整合法域约 `2.33e8` placements，不一次性显式展开。全规模实现继续采用：

`Benders decomposition + exact column generation`。

- Master：任务 placement、GPU/IT 资源约束及当前 Benders cuts；
- Subproblem：给定设施负荷后的连续能源/储能 LP；
- Pricing：在每个任务的完整合法域上做 exact reduced-cost search；
- 允许 exact dominance presolve 和 sparse cut assembly；
- 禁止通过经验 top-k、固定时间窗等方式永久删除合法列。

当前 40-task exact 校准和 50k root scaling 只验证求解表示与定价机制，不等于最终 50k 整数多目标解。

## 3. 六指标统一定义

题面要求在运行成本、碳排放、网络时延、服务质量、新能源利用率和区域峰值净购电之间权衡。Q4 不再采用“Cost 几乎锁死后再优化 QoS”的绝对字典序。

统一将六项写成待最小化损失 `f_j(x,y)`：

1. `f_C`：系统运行成本；
2. `f_E`：电网购电对应碳排放；
3. `f_L`：所有任务的总网络时延（平均时延仅为常数倍等价统计）；
4. `f_Q`：服务质量损失。RT 仍强制到达即开工；对 Batch/Training 定义等待 `w_i=s_i-a_i` 与可用 slack `S_i=LatestFinishHour_i-a_i-p_i`，采用最坏相对等待
   `f_Q = max_i w_i / S_i`（只对 `S_i>0` 的弹性任务），避免用任意小时上限制造人为 QoS 约束；同时报告总等待、平均等待、P95 和最大等待；
5. `f_R = 1 - eta_R`：新能源未利用率，其中 `eta_R` 按附件统一口径计算；
6. `f_P = sum_r PeakNetImport_r`，其中 `PeakNetImport_r >= GridPurchase[r,t]-GridSell[r,t]` 对所有 t 成立；正文同时报告各区域峰值。

六指标定义固定后，基准方案和所有场景均使用同一套定义，不随场景改变优先级。

## 4. 六指标锚点与标准化折中

### 4.1 单目标锚点

分别求六个单目标锚点：

`x^(k) = argmin f_k(x,y),  k in {C,E,L,Q,R,P}`。

得到 payoff table：`F[j,k] = f_j(x^(k))`。

定义：

`f_j^I = min_k F[j,k]`（ideal anchor），

`f_j^N = max_k F[j,k]`（由六个锚点构造的 payoff-table anti-ideal；不宣称为严格 nadir）。

若某指标 `f_j^N-f_j^I` 小于数值容差，则该指标视为在锚点集合内近似常数，只报告而不参与归一化除法。

### 4.2 标准化最坏遗憾折中

定义无量纲退让：

`d_j(x,y) = (f_j(x,y)-f_j^I)/(f_j^N-f_j^I)`。

第一阶段求：

`min z`

s.t.

`d_j(x,y) <= z,  for all active j`，

并满足完整联合调度硬约束。

得到 `z*` 后，在 `z <= z* + tol` 内第二阶段最小化：

`sum_j d_j(x,y)`。

若仍存在数值等价解，只作解释性 tie-break：先减小最大绝对等待，再减少迁移任务数；不得重新把 Cost 设成近乎不可动的第一优先级。

该规则的含义是：限制六项指标中最差的相对退让，再减少总体退让。它不使用 AHP、熵权或人为线性加权系数。

## 5. 三类场景的正式比较协议

所有场景都必须重新优化 `(x,y)`，不能固定某个 QoS 排程后只重算能源层，否则只能得到“该固定排程下”的条件结果。

场景之间固定六指标折中规则，仅改变外生参数。

### 5.1 碳约束路径

先得到成本锚点对应碳排 `E_cost` 与最低碳锚点 `E_min`。定义可行的碳预算路径：

`B_C(lambda) = E_min + lambda * (E_cost-E_min),  0<=lambda<=1`。

正式建议至少取 `lambda in {1,0.75,0.5,0.25,0}`。该定义避免把“相对某个固定排程减 50%”误判为全局不可行；每个预算点都在联合模型中重新求解。

### 5.2 电价机制

使用平均价格保持不变的峰谷强度参数：

`p_rt(beta) = pbar_r + beta * (p_rt-pbar_r)`。

- `beta=0`：Flat；
- `beta=1`：附件原逐时价格；
- `beta>1`：增强峰谷差 sensitivity。

`beta>1` 不解释为现实政策给定常数。正式数值采用预先声明的 sensitivity grid；禁止求解后挑一个“效果好”的 beta。

### 5.3 新能源波动

为区分“波动程度”与“总新能源量”，优先使用均值保持的波动幅度构造。对每个区域：

`R_raw_rt(gamma) = Rbar_r + gamma * (R_rt-Rbar_r)`，

负值截为 0 后，再按区域总量缩放，使场景总可用新能源与附件基准总量一致。

- `gamma=0`：同总量的平滑出力；
- `gamma=1`：附件原出力；
- `gamma>1`：增强波动 sensitivity。

当前历史 `gamma=1.4` 结果仅作 probe，不能直接冻结为正式场景参数。

### 5.4 场景数量与计算复用

默认采用 one-factor-at-a-time 比较，不做 `碳 x 电价 x 新能源` 全排列。以 5 档碳预算、3 档电价、3 档新能源为例，基准点重复后只需约 9 个主场景；如需讨论交互作用，再增加 1--2 个联合压力场景。

每个新场景：

1. 复用基准场景 active column pool 和可行整数 incumbent 作为 warm start；
2. 在完整合法域上重新 exact pricing，允许产生新列；
3. Benders cuts 只有在数学上证明对新场景仍有效时才复用；否则重新生成 scenario-specific cuts；
4. 重新完成整数可行性、energy recourse、六指标和场景约束审计。

Warm start 只降低计算量，不限制新场景的策略变化。

## 6. 当前结果状态纪律

以下内容目前只能视为 probe / DRAFT：

- “Cost 只允许 0.001 CNY 浮动后最小等待”的 QoS 结果；
- 固定 QoS 排程后得到的碳预算可行/不可行结论；
- `gamma=1.4` 下的新能源压力和碳预算结果；
- 仅 root LP relaxation 的 50k scaling 结果作为算法扩展性结论可以保留，但不能替代最终整数多目标解。

最终进入正文的代表方案必须至少完成：

- 六个 anchor；
- 标准化最坏遗憾折中解；
- restricted integer master / 必要时更强整数精化及 integrality gap；
- 真实 Energy LP 复核；
- GPU/IT、SLA、LatestFinish、2406、SOC、购售电边界全部审计；
- 三类场景按同一折中规则重新优化；
- `results/registry.csv` 达到 `FROZEN + CHECKED`。
