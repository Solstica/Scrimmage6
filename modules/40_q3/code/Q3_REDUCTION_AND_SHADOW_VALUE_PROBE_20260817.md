# Q3 约化充分条件与 shadow-value 探针（2026-08-17）

状态：`DRAFT / NEEDS_REVIEW`

目的：把近期文献审计提出的三件事落实到附件数据：

1. E0 闭式分解需要什么条件；
2. A/B/C 零动作与 `GridCharge=0` 到底能证明到什么程度；
3. reduced BESS 与 full energy-flow LP 的“无损”是一般定理还是附件级数值结论；同时测试 SOC dual 是否适合作机理解释。

## 1. E0 闭式分解的附件条件

附件全时域满足：

- `min BuyPrice = 234.65 CNY/MWh > 0`；
- `SellPrice >= 0`；
- `max(SellPrice-BuyPrice) = -51.62 CNY/MWh < 0`，即 `BuyPrice > SellPrice` 全时域成立。

因此在无储能、无其他跨时段自由度时，1 MWh 新能源直接供负荷的价值不低于售电价值；E0 可逐时写成：

`D0=(-H)_+`

`S0=min(H_+, SellCap)`

`C0=(H-SellCap)_+`

`X0=SellCap-S0`

其中 `H=AvailableRenewable-FacilityLoad`。

## 2. A/B/C 零 BESS 动作

附件验证：

- A/B/C：`H>=0` 对 2407 个小时全部成立；
- A/B/C：`SellLimit=0`；
- BuyPrice 非负；
- terminal 要求 `SOC(2406)>=InitialSOC`。

于是存在 `GridPurchase=0` 的零成本方案。因为 A/B/C 无售电收入、成本不能低于 0，Stage 1 最优值为 0；Stage 2 在成本最优面最小化 throughput，自然选择：

`qR=qG=d=0`。

这可以作为附件条件下的结构命题，而不只是 solver 现象。

## 3. 为什么存在 `GridCharge=0` 的成本最优代表解

附件还满足：

- `min AvailableRenewable = 500 MW`；
- 六区 `MaxChargePower <= 260 MW`；
- `BuyPrice >= SellPrice >= 0`。

因此任意时刻的总充电功率都小于可用新能源。若某成本最优解存在 `qG>0`，可把这部分电网充电替换为同量新能源充电：

- 优先从 curtailment 中替换：成本严格不增；
- 若来自售电新能源：少购电 `BuyPrice`、少售电 `SellPrice`，因 `Buy>=Sell`，成本不增；
- 若来自直接供负荷新能源：相应增加同量 grid-to-load、同时减少同量 grid-charge，总 GridPurchase 不变。

总充电功率、SOC 递推和充电上限保持不变，因此 **至少存在一个成本最优代表解满足 `qG=0`**。

正式程序的 Stage 2 也验证六区 `GridCharge` 总量与最大逐时值均为 0。

注意：这不是说任意 Stage-1 solver 返回的成本最优解都必然 `qG=0`；多重最优仍可能存在。

## 4. reduced vs full LP 数值等价

对六区分别求：

- full energy-flow LP：`u,qR,qG,d,gL,s,w,E`；
- reduced incremental BESS LP：`c,dG,dS,E`；
- 两者均采用 `Economic optimum -> minimum throughput`。

结果：

- A/B/C：BESS value = 0，throughput = 0；
- D：full BESS value `9,743,701.129188 CNY`，reduced 差约 `3.56e-7 CNY`；throughput 差约 `9.32e-7 MWh`；
- E：value 差约 `6.24e-7 CNY`；throughput 差约 `1.05e-6 MWh`；
- F：value 差约 `7.26e-8 CNY`；throughput 差约 `1.00e-6 MWh`。

因此当前可以写：

> 在本附件参数与时序数据上，reduced incremental model 与 full energy-flow LP 在最优经济价值和最小吞吐量上数值一致到约 `1e-6`。

暂时不要写成对任意数据都成立的“一般等价定理”；若论文需要定理化，必须单独补全充分条件证明。

## 5. SOC dual / shadow value 的可解释性边界

从 reduced Stage-1 LP 读取 SOC 动态等式的 dual：

- A/B/C：全 0；
- D：当前求解基下全 0；
- E：约 42 个小时非零，最小 marginal 约 `-187.9344`；
- F：约 88 个小时非零，最小 marginal 约 `-197.2065`。

这说明 shadow value 可以用来解释 E/F 的稀缺时段，但 **不能把一条 solver dual 曲线当成唯一经济价值定理**。D 区虽然 BESS 有约 9.74 百万元经济价值，当前最优基却可以返回全零 SOC dual，反映 LP 多重最优/退化导致 dual 也可能非唯一。

因此 Q3 正文若画 shadow-value 曲线，应表述为“某一最优对偶代表解的局部边际解释”，并与实际 charge/discharge/SOC active constraints 联合解释。

结果明细见 `modules/40_q3/results/q3_reduction_equivalence_20260817.csv`。
