# Q4 全域字典序阶段 Benders 震荡修正要求：区域 Multi-cut

状态：**P0 / MUST FIX BEFORE CONTINUING 50k LATENCY STAGE**

日期：2026-08-17

## 0. 本文件对应问题

本要求针对 Q4 的 50k `Cost -> Wait -> Latency` 全域字典序求解。

当前 full-domain Wait repricing 已基本证明有效；Latency 阶段在重新做完整合法域 pricing 后也发现了大量新的低延迟列，但随后用于约束真实能源成本的 **single aggregate Benders cut** 收敛明显过慢并出现震荡。因此，本轮只修正能源 recourse 的 Benders 表示，不改变数学模型、合法域、字典序目标或 cost cap。

严禁因为当前震荡而：

- 截断合法 `(task, region, start)` 域；
- 加 top-k / 最大等待窗口；
- 引入经验权重或 minimax；
- 放宽 cost cap 到 1%、5% 等事后阈值；
- 退回只在 Cost 列池内做 QoS/Latency 的旧实现。

---

## 1. 当前 50k 局部结果说明了什么

### 1.1 Cost 根阶段没有结构性问题

当前导出结果：

- tasks = 50,000；
- implicit legal domain = 233,375,201 placements；
- root LP closed = true；
- active columns = 51,260；
- Benders cuts = 6；
- feasible energy-cost UB = `-459,274,946.57280177 CNY`；
- global integer optimum proved = false。

因此 Cost 根阶段仍按现有口径保留。

### 1.2 Wait full-domain repricing 已验证必要且有效

当前阶段记录显示，Wait 阶段重新对完整合法域定价后能够闭合，并得到约：

- MIP total wait = 32 h；
- 真实 Energy LP 复核成本不违反 Cost cap。

这证明旧版“只在 Cost active columns 上最小 Wait”的实现确实遗漏了重要合法 placement。**不得回退。**

### 1.3 Latency full-domain repricing 也确实激活了大量新列

在 Latency 阶段，旧列池能源 violation 已接近数值零时，完整合法域重新定价一次发现：

- 新增负 reduced-cost 列约 57,515 个；
- 最负 reduced cost 约 `-1400.33`；
- Latency LP objective 从约 `1.331e6 ms` 降到约 `2.536e5 ms`。

这说明 Latency full-domain repricing 是正确且必要的。

问题不是“新增这些列错了”，而是新增大量低延迟列后，当前 aggregate Benders 对真实 Energy Cost cap 的逼近过弱。

### 1.4 当前 aggregate Benders 呈现平台型震荡

新 latency 列加入后，真实能源 cost-cap violation 一度约：

`711,379.9 CNY`

随后虽总体下降，但 120+ 轮仍在约 `8e4 ~ 1.4e5 CNY` 量级震荡；局部最新值约 `82,679.9 CNY`。

这与 `1e-3 CNY` 的最终闭合容差相差多个数量级，因此当前不是“最终 tolerance 太紧”，而是 recourse 表示/切割强度问题。

**结论：当前 run 不建议继续靠单 aggregate cut 硬磨到 180 轮。应先修 Benders 结构。**

---

## 2. 数学原因：当前能源 recourse 在无全局 Carbon budget 时严格区域可分

在 baseline Cost / Wait / Latency 字典序阶段，没有全系统 Carbon budget 等跨区能源耦合约束时，完整能源 recourse 可以写为

\[
Q(L)=\sum_{r\in\mathcal R}Q_r(L_r),\qquad \mathcal R=\{A,B,C,D,E,F\}.
\]

其中每个 `Q_r` 都是 Region r 在给定设施负荷轨迹 `L_r` 下的 Renewable/BESS/Grid 连续 LP 最优值。

因此继续只维护一个 aggregate `theta`：

\[
\theta \ge Q(L^k)+\lambda^k\cdot(L-L^k)
\]

虽然理论上有效，但在 Latency 阶段大量 workload placement 退化时可能非常弱：不同区域 recourse 的高估/低估被总和掩盖，Master 可以在不同区域负荷组合间跳动。

40-task exact/Benders probe 已经验证：**无系统级 Carbon budget 时 region multi-cut 是自然且精确的结构。**

---

## 3. P0 修正：single aggregate theta -> 6-region theta_r + multi-cut

### 3.1 Master 中建立 6 个 recourse 变量

将当前单个

\[
\theta
\]

改为

\[
\theta_A,\theta_B,\theta_C,\theta_D,\theta_E,\theta_F.
\]

总能源 recourse 近似为

\[
\Theta=\sum_r\theta_r.
\]

### 3.2 每个区域独立构造 Benders optimality cut

给定第 k 个 workload 解，分别求解六个区域的真实能源 LP，得到

\[
Q_r(L_r^k),\quad \lambda_r^k.
\]

对每个区域加入：

\[
\boxed{
\theta_r
\ge
Q_r(L_r^k)
+
(\lambda_r^k)^\top(L_r-L_r^k)
}
\]

而不是先把六区 dual/recourse 聚合后只生成一条总 cut。

### 3.3 Cost cap 必须使用六区 theta 之和

Wait / Latency 阶段保持同一个已冻结 Cost cap：

\[
\boxed{
\sum_r\theta_r\le C^*+\varepsilon_C
}
\]

不要改变 `C*` 的来源，不要因为当前震荡临时扩大 `epsilon_C`。

### 3.4 每轮真实能源复核后，同时加入所有 violated-region cuts

对当前 Master 解 `L^k`，计算每区真实误差

\[
v_r^k=Q_r(L_r^k)-\theta_r^k.
\]

若

\[
v_r^k>\varepsilon_B
\]

则该区必须加入新 cut。

**一轮允许同时加入 0--6 条区域 cut。**

不要只选择 violation 最大的一个区域，也不要再次把六区合成一条 aggregate cut。

推荐 Benders 闭合判据：

\[
\max_r v_r^k \le \varepsilon_B
\]

且真实总能源成本满足

\[
\sum_r Q_r(L_r^k)\le C^*+\varepsilon_C+\varepsilon_{audit}.
\]

---

## 4. Energy LP 实现要求

Q4 能源 recourse 继续复用当前正式 Renewable/BESS/Grid 物理模型，不改变能源可行域：

- `u`: renewable directly to load；
- `qR`: renewable charge；
- `qG`: grid charge；
- `d`: discharge；
- `gL`: grid to load；
- `s`: renewable sell；
- `w`: curtailment；
- `E`: SOC。

每区 Energy LP 继续包含：

\[
AvailableRenewable=u+qR+s+w,
\]

\[
Load=u+d+gL,
\]

\[
GridPurchase=gL+qG,
\]

SOC 动态、充放电功率、GridImport、SellLimit/MaxGridExport、terminal SOC 等现有约束全部不变。

不要为了 multi-cut 改写能源物理模型。

---

## 5. Wait / Latency 阶段的完整域 repricing 规则保持不变

本轮修正 **只改 Benders recourse 表示**。

仍然必须保持：

### Wait 阶段

\[
Cost\le C^*+\varepsilon_C
\]

下最小化 TotalWait，并对完整合法 `(task,region,start)` 域重新做 Wait reduced-cost pricing，直到无负 reduced-cost 列。

### Latency 阶段

保持 Cost/Wait 最优（或对应冻结容差）后最小化 TotalLatency，并重新扫描完整合法域做 Latency reduced-cost pricing，直到无负 reduced-cost 列。

RT 仍固定 `StartHour=ArrivalHour`；Batch/Training 保持完整 deadline/2406 合法 start 域。

严禁只在上一阶段 active columns 内做 restricted MIP 就宣称闭合。

---

## 6. 日志与诊断输出必须增加六区 violation

下一版每轮至少输出：

- `Iteration`
- `Stage` (Cost / Wait / Latency)
- `ActiveColumns`
- `NewColumns`
- `MinReducedCost`
- `Theta_A ... Theta_F`
- `TrueQ_A ... TrueQ_F`
- `Violation_A ... Violation_F`
- `MaxRegionViolation`
- `TotalTrueEnergyCost`
- `CostCapViolation`
- `BendersCuts_A ... BendersCuts_F`
- `Runtime_s`
- `RSS_GiB`

其中：

\[
Violation_r=TrueQ_r-Theta_r.
\]

目的：若 multi-cut 后仍震荡，可以直接判断是 D/E/F 某一储能区域未闭合，还是六区共同问题。

---

## 7. 验收顺序

### P0-A：先做 40-task exact benchmark

必须继续复现既有 exact benchmark：

- migrated = 5；
- total wait = 6 h；
- max wait = 2 h；
- latency sum = 437 ms；
- mean latency = 10.925 ms；
- Energy Cost 与 exact joint benchmark 一致（求解器容差内）。

同时输出 region multi-cut 的每区 violation 和 cut 数。

如果 40-task 不能复现，不得直接上 50k。

### P0-B：50k Wait 阶段

要求：

- full-domain Wait pricing closed；
- region Benders closed；
- 真实 Energy Cost 满足 cost cap；
- 输出最终 total/mean/P95/max wait；
- 保留当前约 32 h total wait 作为回归参考，但不得为追数字而改模型。

### P0-C：50k Latency 阶段

要求：

- full-domain Latency pricing closed；
- region Benders closed；
- Cost cap 与 Wait cap 均由真实模型审计通过；
- 输出 final total/mean latency、migration、wait statistics；
- 全部 GPU/IT/SLA/deadline/finish<=2406 与能源硬约束 PASS。

只有这一步完成后，50k QoS/Latency 才可进入论文正式结果。

---

## 8. 当前禁止事项

在 multi-cut 修复前，禁止：

1. 继续把 120+ 轮 aggregate-cut 震荡解释为“只是还没跑够”；
2. 为了闭合把 Benders tolerance 从 `1e-3 CNY` 直接放到 `1e4~1e5 CNY`；
3. 修改 cost cap 以掩盖能源 violation；
4. 删除第 89 轮 Latency full-domain pricing 找到的新列；
5. 退回旧 restricted Cost-column-pool QoS 方案；
6. 引入新的人工权重、minimax、AHP、熵权；
7. 将当前 50k Latency 中间解写入 paper/registry 的正式结果。

---

## 9. 对论文口径的影响

当前结果只能用于算法诊断：

- Wait full-domain repricing 已显示明显价值；
- Latency full-domain repricing 找到大量新的改进列，证明该阶段必须重新定价；
- 后续 aggregate Benders cost-cap 震荡是实现层收敛问题，不是“Latency 优化本身不可行”。

在 region multi-cut + full-domain repricing 全部闭合前，不得写：

- 50k 最终 latency 已得到；
- 50k Cost/Wait/Latency 全局最优已证明；
- 80k CNY 量级 cost violation 可忽略；
- 旧版 1171 h max wait 是 Cost 主层不可避免的真实代价。

---

## 10. 最终固定路线

若本轮 region multi-cut 验收通过，Q4 baseline 主算法保持：

\[
\boxed{
Cost\text{-Benders/CG}
\to
Wait\text{-Benders/CG}
\to
Latency\text{-Benders/CG}
}
\]

其中无全局能源耦合约束时 Energy recourse 使用 **6-region multi-cut Benders**；若后续引入全系统 Carbon budget，则再切换为 global recourse/global cut 或显式 carbon-budget allocation，而不是混用本文件的区域可分假设。
