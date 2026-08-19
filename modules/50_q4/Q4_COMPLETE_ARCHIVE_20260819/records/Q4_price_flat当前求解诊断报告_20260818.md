# Q4 `price_flat` 正式场景当前求解诊断报告

更新时间：2026-08-18 21:10（Asia/Shanghai）  
报告状态：`DRAFT / RUNNING DIAGNOSIS`  
适用对象：第四问正式场景分析中的 `price_flat` 场景  

## 1. 结论摘要

当前运行**没有完成，也没有发生死循环或内存故障**。程序位于 `price_flat` 场景最终字典序再认证的第一轮、第一阶段：`Sweep 1 -> Cost 再认证`。

当前已经可以反复做到：

- LP 区域 Benders 一致性闭合；
- 完整合法域精确定价闭合；
- restricted MIP 返回 Gap 为 0 的整数候选。

但整数候选代入真实能源与储能 recourse 后，区域成本仍高于主问题中的区域成本估计量，因此触发新的区域 Benders cuts，重新返回 LP。当前瓶颈应准确称为：

> **Cost 阶段的整数 Benders / 整数外逼近一致性尚未闭合。**

它不是完整域列生成失败，不是内存不足，也不能解释成普通的“局部最优”。`price_flat` 去除了逐时电价差异，产生大量成本相同或近似相同的离散排程，restricted MIP 容易在巨大退化平台上不断切换到尚未被现有 cuts 精确刻画的新负荷模式，这是当前收敛慢的主要原因。

## 2. 必须区分的两个结果口径

### 2.1 第四问基准解

原第四问基准问题已经在独立目录中完成两轮 `Cost -> Wait -> Latency` 再认证，存在可用的基准代表性整数解。该结果不等于本报告正在计算的正式场景结果。

基准结果目录：

`modules/50_q4/results/qos_final_recertification/`

### 2.2 当前正式场景

当前运行的是正式场景协议中的：

`price_flat`：把每个区域的逐时电价替换为该区域附件电价的时间均值，然后重新求解完整 workload--energy--storage 联合模型。

当前场景目录：

`modules/50_q4/results/formal_scenarios/price_flat/`

因此，目前的困难只表示 `price_flat` 场景尚未完成，不能反向否定已经完成的第四问基准解。

## 3. 当前位于完整流程的什么位置

`price_flat` 场景的计算链条如下：

```text
场景附件生成
  -> Cost-primary 初始求解
  -> QoS Cost/Wait/Latency 候选列池生成（已完成）
  -> final-pool 字典序再认证
       -> Sweep 1 Cost      <- 当前位于这里，尚未完成
       -> Sweep 1 Wait
       -> Sweep 1 Latency
       -> Sweep 2 Cost
       -> Sweep 2 Wait
       -> Sweep 2 Latency
       -> 锚点稳定性比较
       -> 最终真实能源复核与硬约束审计
       -> 生成 FINISHED_DRAFT 汇总
```

按阶段计数，最少需要完成六个再认证阶段，当前第一个 Cost 阶段尚未完成。阶段耗时并不均匀，因此不能据此直接换算百分比。

## 4. 当前运行快照

截至 2026-08-18 21:10，最近一次完整观测为：

| 项目 | 当前值 | 判断 |
|---|---:|---|
| 进程 | PID `34704` | 存活并持续消耗 CPU |
| 当前状态 | `RUNNING` | 未结束 |
| 当前阶段 | `R1 Cost再认证` | Sweep 1 的 Cost 阶段 |
| 最新轮次 | 177 | 仍在增加 |
| 活动列数 | 137139 | Cost 阶段未出现新增列 |
| Benders cuts | 603 | 持续增加 |
| 第 177 轮 LP 最大区域违反 | 0 CNY | LP 层通过 |
| 完整域最小缺失列约化成本 | 0 | 完整域定价通过 |
| 第 177 轮整数最大区域违反 | 8466.097 CNY | 真实能源复核未通过 |
| 声明容差 | 0.001 CNY | 当前仍高出约 846.6 万倍 |
| 当前进程 RSS | 约 0.3--0.6 GiB | 内存不是瓶颈 |
| 最终汇总 | 尚未生成 | 不能用于场景结论或绘图 |

第 177 轮的 `8466.097 CNY` 是截至该快照已失败整数候选中的最小最大区域违反，说明 cuts 正在产生一定改善；但违反量尚未进入容差量级，且历史序列非单调，因此不能据此宣称即将收敛。

## 5. 已经完成和通过的部分

### 5.1 `price_flat` 主 QoS 候选阶段

主 QoS 阶段已输出一个可行候选：

| 指标 | 候选值 |
|---|---:|
| 真实能源成本 | -459275918.623763 CNY |
| 总等待 | 32 h |
| 平均等待 | 0.00064 h |
| 最大等待 | 2 h |
| 总时延 | 250163 ms |
| 平均时延 | 5.00326 ms |
| 迁移任务数 | 12 |
| 任务数 | 50000 |

该候选的任务覆盖、GPU/IT 容量、到达时间、实时任务、SLA、截止时间、能源平衡、储能和电网边界审计均通过。但其状态仍是 `DRAFT / NEEDS_REVIEW`，因为 final-pool 再认证发现 Cost 仍可改善。

### 5.2 当前 Cost LP 层

Cost 再认证中反复得到：

- LP 目标/成本下界约为 `-459340688.800706 CNY`；
- LP 真实能源成本约为 `-459340688.800704 CNY`；
- 完整域定价的最小缺失列约化成本为 0；
- 活动列数保持 137139。

这表明当前主要问题不在“还有负约化成本列没有加入”，而在整数候选与能源 recourse 的一致性。

## 6. 当前遇到的具体困难

### 6.1 LP 闭合不等于整数候选闭合

主问题用六个区域成本变量 `theta_A,...,theta_F` 表示真实能源 recourse 的分段线性下估计。现有 Benders cuts 可以在当前 LP 分数解处把该估计收紧，因此 LP 能够达到区域违反为 0。

当变量转为整数后，MIP 会选择另一组任务区域和开工时刻。该整数排程对应新的设施负荷轨迹，可能落在现有 cuts 尚未精确刻画的位置。真实 Energy LP 重新计算后发现：

```text
真实区域能源成本 > MIP 中的区域 theta
```

于是该整数候选必须被新的区域 cut 排除，算法返回 LP 继续。

### 6.2 `price_flat` 场景放大离散退化

逐时电价被替换为区域均价后，同一区域内不同开工时刻之间失去了一部分价格区分信号。大量排程可以取得相同或非常接近的 Cost 目标，但具有不同的：

- 逐时设施负荷；
- 新能源消纳；
- BESS 充放电路径；
- 电网购售电路径；
- 区域真实 recourse 成本。

因此一个 cut 排除当前负荷模式后，MIP 仍可能在同一 Cost 水平上找到另一个尚未充分刻画的整数负荷模式。该判断是根据场景结构和当前日志作出的机制性推断。

### 6.3 违反量下降并不单调

截至快照，阶段指标包含：

- 20 次 `root_lp_closed`；
- 20 次 `integer_added_region_benders_cuts`；
- 157 次 LP 区域 cuts 更新；
- 整数候选最大区域违反范围约为 `8466.10` 至 `1044398.69 CNY`；
- 整数失败违反量中位数约为 `92167.90 CNY`。

近期整数候选最大区域违反曾依次出现约：

`220367 -> 28441 -> 65761 -> 35814 -> 68964 -> 59347 -> 19902 -> 8466 CNY`。

总体最低值在改善，但中间有明显反弹。因此，轮次增加本身不能证明已经接近最终闭合。

### 6.4 Cost 下界长期不变

多轮 LP 与 MIP 的 Cost 目标保持在约 `-459340688.8007 CNY`，新增 cuts 主要改变的是候选的能源一致性，而非目标下界。这进一步说明当前处在大规模同目标退化平台上的整数可行化过程。

### 6.5 日志无法完整识别候选是否重复

当前 final recertification 目录保存了 checkpoint、列池状态和聚合 metrics，但没有逐轮保存完整整数排程或设施负荷签名。因此仅凭现有文件不能严格证明每次 MIP 返回的是不同排程，也不能直接统计候选重复率。这不影响当前算法运行，但限制了对退化平台的精确诊断。

## 7. 已排除的故障类型

### 7.1 不是进程停止或死锁

- Python 进程存在且 CPU 时间持续增加；
- `checkpoint.json`、`lexicographic_state.npz` 和阶段 metrics 持续更新；
- 轮次和 cuts 数持续增长。

### 7.2 不是内存不足

当前 Python RSS 远低于 `10 GiB` 门槛，未出现 `MemoryError`，也没有触发最小可用内存保护。

### 7.3 不是完整域列生成没有闭合

根节点闭合轮次中完整域最小缺失列约化成本为 0，且 Cost 阶段活动列数没有增加。当前瓶颈不是 CG 定价。

### 7.4 不是 restricted MIP 自身没有求到最优

多个整数子问题返回 `MIP gap = 0`。问题是该最优性只针对当前有限 Benders 外逼近主问题；真实能源复核发现外逼近仍低估 recourse，因此还不能接受该整数解。

## 8. 尚未完成的门禁

当前至少还缺少：

1. Sweep 1 Cost 阶段整数真实能源一致性通过；
2. Sweep 1 Wait 阶段完成；
3. Sweep 1 Latency 阶段完成；
4. Sweep 2 的 Cost、Wait、Latency 三阶段完成；
5. 两轮 Cost/Wait/Latency 锚点在容差内稳定；
6. 最终 50000 任务排程完整性核验；
7. 最终真实能源、储能、电网和全部硬约束审计；
8. 生成状态为 `FINISHED_DRAFT` 的正式场景汇总。

只要上述任一项缺失，`price_flat` 就不能进入正式六指标汇总和图 F。

## 9. 当前是否应该继续运行

当前建议：**继续现有进程，暂不重启。**

依据是：

- 进程健康，内存安全；
- 最新整数最大区域违反 `8466.097 CNY` 创下本阶段已失败候选的新低；
- 根节点仍能稳定闭合，说明新增 cuts 没有破坏主问题；
- 目前没有 Traceback、文件损坏或模型门禁被绕过的证据。

但这不是无限等待建议。若后续满足以下任一条件，应保留 checkpoint 后调整实现：

- 连续 15 个整数候选没有刷新最小最大区域违反；
- 再运行 60--90 分钟仍未出现 `stage_completed`；
- 相同设施负荷模式被重复返回；
- 单次 MIP 时间或 cuts 矩阵构造时间持续显著增长；
- 文件停止更新、CPU 不再增加或出现非受控异常。

## 10. 若继续不闭合，优先修改方向

### P0：保存并比较整数候选负荷签名

每次 MIP 返回后，在真实能源复核前原子保存：

- 整数排程摘要；
- 六区域逐时设施负荷哈希；
- 总等待、总时延和 MIP 目标；
- 真实能源成本与各区域违反；
- 是否与历史候选重复。

这一步不改变数学模型，可以确认算法是在探索新负荷模式，还是因数值问题重复返回已经切除的模式。

### P1：Cost 阶段启用能源一体化整数 MIP

当前代码只对带 Cost cap 的 Wait/Latency 阶段使用能源一体化 MIP，Cost 阶段仍使用 restricted MIP + 整数 Benders cuts。若当前循环长期不闭合，可把已有 `solve_extensive_mip` 路径扩展到 Cost 再认证阶段，使整数排程与能源 recourse 在同一 MIP 中求解，从机制上消除整数候选的 theta 低估循环。

该方案不放宽 Cost cap、不裁剪合法域，也不改变题目模型，但会增加单次 MIP 的规模和求解时间，必须先备份当前状态并通过小规模恒等测试和内存门禁。

### P2：加强退化诊断与 cut 管理

在不改变模型的前提下检查：

- 区域 cuts 是否重复或数值近重复；
- cuts 的缩放和系数量级；
- 同目标整数候选的负荷签名重复率；
- 是否可使用求解器原生 warm start；
- 是否可对已有真实能源可行 incumbent 增加有效目标上界。

不得采用的“加速”包括：放宽 `0.001 CNY` 一致性容差、删除合法列、缩短合法开工窗口、改变 Cost/Wait/Latency 字典序或加入主观权重。

## 11. 当前可向队友汇报的简明口径

> 第四问基准解已经完成；当前未完成的是新增 `price_flat` 正式场景。该场景已完成主 QoS 候选求解，正在 final-pool Sweep 1 的 Cost 再认证。完整域定价和 LP Benders 已多次闭合，restricted MIP 也能以 Gap=0 返回整数候选，但整数候选经真实能源 recourse 复核后仍存在区域成本低估，因此不断追加区域 cuts。最新整数最大区域违反约为 8466.10 CNY，是当前新低，但距离 0.001 CNY 门槛仍很远。进程、CPU、checkpoint 和内存均正常，当前瓶颈是平价场景巨大同目标整数平台上的 integer-Benders closure，而不是列生成、内存或进程故障。

## 12. 证据文件

- 当前 checkpoint：`results/formal_scenarios/price_flat/qos_final_recertification/checkpoint.json`
- 再认证控制文件：`results/formal_scenarios/price_flat/qos_final_recertification/recertification_control.json`
- 阶段过程指标：`results/formal_scenarios/price_flat/qos_final_recertification/q4_recertification_stage_metrics.csv`
- 再认证列池与 cuts：`results/formal_scenarios/price_flat/qos_final_recertification/lexicographic_state.npz`
- 主 QoS 候选汇总：`results/formal_scenarios/price_flat/qos/q4_qos_summary.json`
- 正式场景协议：`Q4正式场景协议_20260818.md`

## 13. 结果状态

本报告中的所有 `price_flat` 数值均为运行过程诊断值，状态为 `DRAFT`。在 `qos_final_recertification/q4_qos_summary.json` 生成、状态达到 `FINISHED_DRAFT`、至少两个完整 sweep 锚点稳定且最终硬约束审计通过之前，禁止把这些数值写成正式场景结论、论文摘要或最终绘图数据。
