# Q1 论文文字修订要求（2026-08-17）

状态：WRITER P0。本文档只约束 `modules/20_q1/paper/q1.tex` 与 `q1_algorithm.tex` 的文字/公式/结果口径，不要求重写 Q1 模型，不新增算法。

## 总原则

Q1 已冻结为：

`统计结构识别 -> 24 h 短期概率预测 -> 2376--2399 h 实际任务基础调度 -> GPU 利用率`

保持“短期 baseline”定位，不引入价格、碳、新能源、多目标优化或长时预测模型。

## P0-1 到达率公式必须修正

当前算法伪代码把 Poisson 到达率写成了按任务样本数作分母。正式实现使用：

`lambda_hat = N_train / 2352`

因此论文统一写为

`lambda_hat = (1/T) * sum_{t=0}^{T-1} n_t, T=2352`。

禁止写成 `1/|D_train| * sum n_t`，除非明确 `|D_train|` 表示小时数而不是任务条数。

## P0-2 Q1-3 伪代码必须与真实硬约束一致

当前真实调度候选同时检查：

1. GPU capacity；
2. IT power capacity；
3. Facility power capacity；
4. SLA latency；
5. LatestFinish / finish<=2406；
6. RT 到达即开工。

算法框中不能只写 `S_rt + g_i <= C_r`。应把候选可行性概括为 GPU/IT/Facility 三层容量同时满足。

保留调度顺序：

`本地立即 -> 本地完整合法时间域顺延 -> 必要时完整 SLA 合法区域迁移`。

## P0-3 资源 mark 口径

正式实现使用经验分布，不使用 KDE。正文中“核密度估计或经验频率表”改为“联合经验分布/经验频率”。

保留：

`(GPU,Duration)|TaskType ~ F_hat_GD^(k)`

但 GPU 需求概率预测实际使用该联合经验样本所诱导的 GPU 边际抽样；Duration 没有直接进入 `Y_rkt` 的 GPU 总量计算。文字应说明：联合 `(G,D)` 用于保持任务资源结构与后续调度语义，GPU 预测取其 GPU 边际，禁止暗示 Duration 直接参与 `Y_rkt`。

## P0-4 数据切分必须写清楚

正文显式写出：

- 0--2351 h：训练；
- 2352--2375 h：验证；
- 0--2375 h：最终 refit；
- 2376--2399 h：一次性独立测试。

Test 不用于回调参数或重新选模。

## P0-5 区间覆盖率措辞

当前测试集 System 90% PICP = 87.5%，不能写“各层均达到或超过 90%”。改为：

“各层覆盖率总体接近 90% 名义水平；System 层为 87.5%（21/24），测试样本仅 24 个小时，因此不据此进一步调参；Region×TaskType 层为 94.21%。”

## P1 结果数字

当前关键结果可以保留：

- System Test WAPE = 0.243；
- Test PICP：System 87.5%，Region 89.58%，TaskType 90.28%，Region×TaskType 94.21%；
- Q1-3 实际到达任务 = 538；
- Moved = 0；
- Delayed = 4；
- Max GPU utilization = 99.0166%；
- Mean GPU utilization = 37.2256%；
- Max finish = 2405.6 h。

但在 registry 升级前仍按 `DRAFT / NEEDS_REVIEW` 管理，不写“最终冻结”。

## P1 图与工程口径

当前 `q1.tex` 已引用若干 `figures/*.pdf`，而分支目前主要是 `figures/editable/` CSV。实际 Origin 图未落盘前：

- 不把缺图视为编译通过；
- 图生成后检查图中数字与当前 CSV 一致；
- 不改变图注所对应的数据层级。

## 禁止事项

- 不增加 ARIMA/LSTM/Prophet 等只为复杂度服务的模型；
- 不把 Q1-2 写成长期预测；
- 不把 Q1-3 写成 Q2 的全时域能源优化；
- 不声称 M3 提高了 System 点预测精度；它的主要价值是层级一致分解与概率区间。

## 验收

论文手完成后应满足：

- [ ] `lambda_hat` 分母改为训练小时数；
- [ ] Q1-3 算法框补全 GPU/IT/Facility；
- [ ] 删除 KDE 模糊口径；
- [ ] 区分联合 `(G,D)` 表征与 GPU 边际预测；
- [ ] 四段时间切分显式写清；
- [ ] PICP 表述修正；
- [ ] 不新增模型或改变 Q1 主结论。
