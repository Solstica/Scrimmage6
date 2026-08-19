# Q4 Latency 阶段整数 Benders 诊断（第 180 轮）

状态：`DRAFT / NEEDS_RESUME`

## 1. 当前判断

当前 Q4 已经不是“完整域列生成未闭合”或“LP Benders 振荡”问题。

第 180 轮之前已经满足：

- Latency 完整域 LP pricing 无缺失负 reduced-cost 列；
- 最小缺失列 reduced cost = 0；
- LP 最大区域 Benders violation 约 `2.09e-7 CNY`；
- 因此 **Latency 的完整域 LP + region multi-cut Benders 已闭合**。

当前真正瓶颈是：

> restricted MIP 给出的整数候选在 Benders underestimator 下满足 cost cap，但经真实 Energy LP 复核后仍违反真实成本上界。

这应称为 **integer Benders / integer outer-approximation closure**，不是 Column Generation 失败，也不是普通意义的局部极小。

## 2. 第 180 轮状态

- 任务数：50,000；
- 当前阶段：Latency；
- 活动列数：137,139；
- checkpoint Benders cuts：340；
- Cost cap：`-459,274,946.5718 CNY`；
- Wait 整数锚点：`32 h`；
- Latency LP：约 `250,030.8628 ms`；
- restricted MIP candidate Latency：`250,152 ms`；
- 真实 EnergyCost：`-459,235,884.2087 CNY`；
- 相对 Cost cap 违反约 `39,062.36 CNY`；
- RegionE violation 约 `4,352.37 CNY`；
- RegionF violation 约 `35,270.91 CNY`。

因此该整数候选必须继续被 E/F 两个 region cuts 排除。

## 3. 为什么 MIP 目标已多轮为 250152 ms 仍未完成

这不是重复求到同一排程。

Latency 是离散的整数毫秒和，50,000 个任务的 placement 组合存在大规模等目标退化平台。多个不同整数排程可以具有完全相同的：

\[
\sum_i Latency_i = 250152\ \mathrm{ms},
\]

但其 FacilityLoad / BESS / Grid 负荷路径不同，从而真实能源成本不同。

Benders cut 每轮排除的是当前被能源 underestimator 错判为可行的负荷模式；下一轮 MIP 可以立刻在同一个 Latency 值上找到另一个不同的整数排程。因此当前慢点来自 **巨大等目标整数平台上的能源可行化**，不是模型存在多个“局部最优”。

## 4. 当前模型层判断

暂未发现需要修改 Q4 数学模型的证据。

以下结构继续保持：

\[
\text{workload placement}
\rightarrow
\text{AI IT}
\rightarrow
\text{Facility Load}
\rightarrow
\text{Renewable/BESS/Grid recourse}.
\]

region multi-cut 继续保持；完整合法域继续保持；Cost cap、Wait cap、Latency 目标均不改变。

当前不允许：

- 放宽 Cost cap 来掩盖整数能源 violation；
- 新增人工权重；
- 新增最大等待窗；
- 截断完整 placement 域；
- 退回 restricted-pool QoS；
- 因 round=180 而改算法模型。

## 5. P0：继续 resume，停止条件不按轮数

继续当前 checkpoint：

```text
--resume
```

停止条件必须是：

1. Latency root LP 继续保持 Benders + full-domain pricing 闭合；
2. restricted MIP 得到整数候选；
3. 真实 Energy LP 复核满足 Cost cap；
4. integer region violation 全部落入声明的数值门槛；
5. 事件进入 `stage_completed`。

不能以 200/220/250 等人为轮数作为成功判据。

## 6. P0：增加真实可行 Latency incumbent 管理

Wait 阶段已经有真实能源复核通过的整数排程，并满足 `Wait=32 h`，因此它本身就是 Latency stage 的一个合法整数可行解。

要求显式保存：

\[
UB_L = Latency(x^{Wait-feasible}).
\]

以后每发现一个真实 Energy LP 复核通过的 Latency 整数候选，就更新：

\[
UB_L \leftarrow \min(UB_L, Latency(x)).
\]

同时记录当前 restricted MIP lower bound：

\[
LB_L.
\]

输出：

\[
Gap_L = \frac{UB_L-LB_L}{\max(1,|UB_L|)}.
\]

如果 solver 接口允许，可加入有效剪枝：

\[
Latency \le UB_L.
\]

该约束仅使用已知真实可行 incumbent，不改变原问题最优解，不属于新模型模块。

## 7. P1：修正 stage metrics 的 cut 数日志

当前 `integer_added_region_benders_cuts` 行在新增整数 region cuts 前写入 `Benders切数`，因此第 180 轮 CSV 可能显示 338，而 checkpoint 在新增 E/F 两条 cut 后显示 340。

要求在整数 cuts 加入后更新：

```python
row["Benders切数"] = len(cuts)
```

该问题仅影响日志，不影响算法。

## 8. 暂不进入 final-pool recertification

当前尚未得到 Latency stage 的真实能源可行整数 endpoint，因此 **不得开始 final-pool Cost -> Wait -> Latency 再认证**。

正确顺序：

\[
\text{Latency integer feasibility closure}
\rightarrow
\text{final-pool Cost recertification}
\rightarrow
\text{Wait recertification}
\rightarrow
\text{Latency recertification}.
\]

final-pool 再认证要求继续遵循：

`Q4_FINAL_LEXICOGRAPHIC_RECERTIFICATION_REQUIREMENTS_20260817.md`。

## 9. 结果口径

当前最多可表述为：

> 完整域 Latency LP 与 6-region Benders recourse 已闭合；当前 restricted MIP 的 best-known latency lower-bound/candidate 位于约 250152 ms 的大规模退化平台，但整数候选尚未通过真实能源 Cost cap 复核，因此仍为 `DRAFT / NEEDS_RESUME`。

不得表述为：

- “50k Latency 全局最优为 250152 ms”；
- “50k 字典序全局最优已证明”；
- “模型陷入局部最优”；
- “Column Generation 尚未收敛”。

## 10. 下一次回报字段

下一次 checkpoint 至少给出：

- round；
- active columns；
- Benders cuts；
- LP min reduced cost；
- LP max region violation；
- restricted MIP latency；
- true EnergyCost；
- Cost cap violation；
- E/F region violation；
- 当前 feasible `UB_L`；
- 当前 `LB_L` / `Gap_L`；
- 是否出现 `stage_completed`。
