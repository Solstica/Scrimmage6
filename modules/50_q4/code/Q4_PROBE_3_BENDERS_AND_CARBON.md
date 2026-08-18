# Q4 Probe 3：完整 Benders 与碳约束激活

状态：`DRAFT / NEEDS_REVIEW`

本探针延续 Probe 2 的 40 个真实任务 benchmark：

- 16 AITraining；
- 14 BatchInference；
- 10 RealTimeInference；
- ArrivalHour 2376--2390；
- 各类型按 GPU-hour 取高负荷任务；
- 3139 个完整合法 `(region,start)` 候选；
- 未设置 top-k、最大等待窗口或最近区域截断；
- 2376 前后未释放的其他真实任务保持为固定背景；
- 能源结算 2376--2406，2406 禁止任务占用；
- 2375 末附件 SOC 作为局部 benchmark 的已知前态，2406 仍满足官方 `SOC>=InitialSOC`。

该样本用于算法压力测试，不解释为总体随机样本。

## 1. Probe 3A：真正 Benders 是否能复现 exact joint MILP

### 1.1 完整联合参考模型

Master 变量：任务二元变量 `x[i,r,s]`。

Subproblem：给定 `x` 后的连续 Renewable/BESS/Grid LP。

Task -> Facility Load：

`L[r,t](x)=BackgroundLoad[r,t]+sum a[i,r,s,t] x[i,r,s]`。

能源最优值函数：

`Q(L)=min_y Cost(L,y)`。

由 LP load-balance dual `lambda^k` 构造 Benders optimality cut：

`theta >= Q(L^k) + lambda^k · (L(x)-L^k)`。

成本目标无跨区域碳预算时，六个能源子问题可区域分解，因此同时测试 region multi-cut：每一区域设置 `theta_r` 并分别累积 cut。

### 1.2 结果

Exact joint MILP：

`Cost* = -5,450,201.934546 CNY`。

Region multi-cut Benders：

- Iteration 1：LB = -5,465,627.184364；真实 recourse UB = -5,450,201.934546；gap = 15,425.25 CNY；6 cuts；
- Iteration 2：LB = -5,450,201.934546；UB = -5,450,201.934546；gap < 1e-9；累计 12 cuts。

因此：

`Benders Cost = Exact Cost`

在求解器精度内成立，仅 2 次 master--subproblem 迭代。

当前环境测试时间：exact joint Stage 1 约 0.16--0.22 s；multi-cut Benders 约 0.35--0.41 s。时间只作为本机小规模诊断，不外推到 5 万任务。

### 1.3 成本多重最优与服务质量

成本最优集合很大。单纯 Cost-only exact 解可出现 38/40 迁移、总等待 172 h；这不代表真正需要这些迁移。

在 `Cost<=Cost*+tol` 上继续：

1. 最小总等待；
2. 保持 Cost/Wait 最优，再最小总网络时延。

得到代表解：

- migrated = 5；
- total wait = 6 h；
- mean wait = 0.15 h；
- max wait = 2 h；
- latency sum = 437 ms；
- mean latency = 10.925 ms。

这再次说明 Q4 的 QoS/Latency 不能只靠成本最优求解器的任意代表解，需要字典序或 epsilon-constraint 精化。

## 2. Probe 3B：为什么原始数据下 Carbon 会退化

当前真实新能源曲线在 40-task benchmark 下仍足以让联合成本最优的购电碳排降为 0。因此基准场景无法测试 Q4 的 Carbon budget cut。

题目明确要求比较“新能源波动场景”。为避免直接拍一个 `R*0.8`，本探针只做诊断性、均值保持的波动放大：

`R_gamma[t] = mean(R) + gamma * (R[t]-mean(R))`。

该式保持局部时域平均新能源不变，只改变振幅；它目前是 probe generator，不是已冻结的正式场景公式。

固定 exact lexicographic workload 后，用二分搜索寻找“cost-optimal energy recourse 首次出现正碳排”的临界振幅：

`gamma_crit ≈ 1.303326`。

因此选取圆整的 `gamma=1.4` 作为**临界值以上的诊断压力点**，而不是把 1.4 直接写成正式比赛场景参数。

## 3. gamma=1.4 下 Cost--Carbon 权衡真实出现

40-task joint cost optimum：

- Cost = -5,018,111.400085 CNY；
- Carbon = 53.64762985 tCO2。

因此以 cost-optimal carbon 作为锚点，构造预算：100%、75%、50%、25%、0%。这是 epsilon-constraint 的数据锚点路径，不需要 Cost/Carbon 人工加权。

结果：

| 碳预算比例 | Carbon budget (tCO2) | Exact Cost (CNY) | Cost penalty vs cost-opt (CNY) | Carbon reduction (tCO2) | 平均减排成本 (CNY/tCO2) |
|---:|---:|---:|---:|---:|---:|
| 100% | 53.64763 | -5,018,111.40 | 0.00 | 0.00 | -- |
| 75% | 40.23572 | -5,016,918.65 | 1,192.75 | 13.41191 | 88.93 |
| 50% | 26.82381 | -5,015,725.89 | 2,385.51 | 26.82381 | 88.93 |
| 25% | 13.41191 | -5,014,489.57 | 3,621.83 | 40.23572 | 90.02 |
| 0% | ~0 | -5,013,150.08 | 4,961.32 | 53.64763 | 92.48 |

说明在新能源波动增强后，Cost--Carbon 冲突不再退化，而且从 cost-optimal 到 zero-carbon 的局部平均减排代价约 92.5 CNY/tCO2。

## 4. Carbon budget 下完整 Benders 仍然成立

加入全系统：

`sum GridPurchase[r,t]*CI[r,t] <= B_C`

后，区域能源子问题被一个系统级碳预算耦合，不能再直接使用“每区独立 theta_r”的 region multi-cut。此时使用 global recourse subproblem + single Benders cut。

对 100%、75%、50%、25%、0% 五个碳预算，Benders 均在 2 次迭代内复现 exact joint MILP 的 Cost（求解器精度内）。

这给出一个重要结构结论：

- 无系统级耦合指标时：能源 recourse 可按 Region 分解，优先 region multi-cut；
- 加全局 Carbon budget 后：能源 recourse 被碳约束耦合，使用 global cut，除非额外引入 carbon-budget allocation master。

## 5. Probe 3 对正式 Q4 的影响

1. `Benders` 现在不再只是“可考虑算法”，而是被小规模 exact benchmark 直接验证可行；
2. Probe 2 的 dual-guided heuristic 出现两周期振荡，正好说明只保留最新 dual 不足；Benders 通过累积支持超平面保留历史 recourse 信息；
3. 40-task cost-only benchmark 两次迭代即闭合，说明 recourse value function 在该局部数据上结构较简单；不能直接外推全 5 万任务，但值得推进；
4. Cost-only Benders 达到能源最优后仍需 QoS/Latency 精化；
5. Carbon 预算在真实 baseline 新能源下退化，但在题目要求的新能源波动场景中自然激活，因此 Q4 的 Carbon 场景应与 Renewable scenario 联合审计，而不是强行在 baseline 上制造 Pareto；
6. `gamma=1.4` 仅是第三组 probe 的压力点。正式“新能源波动场景”仍需做术语/文献审计后冻结。

复现代码：`modules/50_q4/code/q4_probe_benders.py`。
结果 CSV：`modules/50_q4/results/probe3_*.csv`。
