# Q4 price_flat 正式场景求解复核（2026-08-18）

状态：`REVIEWED / ACTION REQUIRED`

依据：当前 `price_flat` 运行诊断、canonical final recertification 真源，以及 `q4_qos_refinement.py` 当前实现。

## 结论

当前瓶颈判断基本正确：不是 CG、不是内存、不是 restricted MIP 未求最优，而是 Cost 阶段整数候选落到现有区域 Benders 外逼近尚未精确刻画的新负荷模式，导致真实能源 recourse 高于 theta，形成 integer-Benders / integer-OA 闭合缓慢。

但在继续等待或改成 extensive MIP 之前，必须先做两个更高优先级的证书检查。

## P0-1 场景数据注入真实性检查

当前 `price_flat` Cost LP 下界约为 `-459340688.800706 CNY`，与 canonical 最终真实成本 `-459340688.8007043 CNY` 几乎完全相同。这个结果既可能是“flat buy price 在当前零/极低购电结构下确实不活跃”，也可能是 final recertification 误用了 canonical attachments。

因此必须在日志/summary 中固定输出：

- scenario name=`price_flat`；
- 当前 attachment 目录绝对路径；
- A--F 六区 Price 的 mean/std/min/max；
- flat 场景每区 `std(Price)=0`；
- 与 canonical Price 至少一个时点不同；
- 场景输入文件 checksum/hash。

上述门禁未通过前，不解释“price_flat 对成本没有影响”。

## P0-2 用 canonical 最终整数排程做跨场景 Cost 证书

price_flat 只改变价格机制，不改变 GPU/IT/Facility/SLA/任务时域等物理可行域，因此 canonical 50k 最终任务排程仍是 price_flat 的物理可行候选。

立即执行：

1. 固定 canonical 最终 workload schedule；
2. 使用 price_flat attachments 重新求完整 Energy/BESS/Grid LP；
3. 得到真实 `UB_flat`；
4. 与当前完整域 Cost LP lower bound `LB_flat` 比较。

若

`UB_flat - LB_flat <= 0.001 CNY`

则无需继续 integer-Benders Cost 闭合：已有“完整域 LP 下界 + 整数真实能源可行上界”相等证书，price_flat Cost 层可直接认证。

若该同一排程仍保持 `Total Wait=0`，则由于 Wait 的理论下界就是 0，Wait 层也直接认证；此时只需继续 Latency 层。

这是严格证书，不是启发式跳步。

## P1 若跨场景证书失败：Cost 阶段改用能源一体化整数 MIP

当前代码 `use_ext(spec)` 在 `spec.cost_cap is None` 时直接返回 False，所以纯 Cost 阶段不会调用 `solve_extensive_mip`；而 Wait/Latency 在带 Cost cap 时已经存在能源一体化 MIP 路径。

当前 `solve_extensive_mip` 又无条件加入 `float(spec.cost_cap)` 的成本上界行，因此若要用于 Cost 阶段，需要先改成：

- `objective == cost` 且 `cost_cap is None` 时不建立 cost-cap 行；
- 目标函数直接由真实 GridPurchase/GridSell 能源变量给出；
- 其余 workload、GPU/IT、Renewable、SOC、Grid 边界保持不变。

先用 100/500/5k 任务做 restricted-Benders MIP 与 extensive-Cost MIP 的目标/硬约束一致性测试，再在现有 137139 活动列上求解。

该修改不改变数学模型，只消除 Cost 整数候选中的 theta 低估循环。

## P1 候选负荷签名必须补

每次 restricted MIP 返回后，在 Energy LP 之前原子保存：

- TaskID -> active column index；
- 六区域 FacilityLoad 时间序列 hash；
- MIP objective / theta；
- true region energy cost；
- region violation；
- 是否与历史候选重复。

这用于区分“巨大退化平台上探索新负荷模式”和“数值/切割问题反复返回同一模式”。

## 停止当前循环的门禁

若 P0-1、P0-2 尚未执行，不建议让 integer-Benders 无限继续。

现有进程可在不影响 checkpoint 的前提下继续短时运行；出现以下任一项即停止并切换上述证书/一体化方案：

- 连续 15 个整数候选不刷新 best max-region violation；
- 继续 60--90 min 仍无 stage_completed；
- 发现重复 FacilityLoad hash；
- cut 数继续快速增加但 best violation 不再下降。

禁止通过放宽 `0.001 CNY`、裁剪合法域、缩短等待窗或修改字典序来“加速”。

## 关于 price_flat 场景本身

若最终确认 flat buy-price 下 canonical/price_flat Cost 几乎不变，应把它解释为场景结果：在本附件的联合最优结构下，购电价格时间形状可能处于弱激活/不激活状态，而不是场景失败。

当前正式协议中还包含 transparent peak-valley sensitivity，可继续作为价格机制中真正激活时间价差信号的第二个比较场景。不要在运行后反向修改 price_flat 定义，也不要临时改变 SellPrice 语义。
