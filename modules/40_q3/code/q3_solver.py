from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy.sparse import coo_matrix, vstack


if len(sys.argv) != 2:
    raise SystemExit("用法: python q3_solver.py C题附件目录")

ATTACH = Path(sys.argv[1]).resolve()
if not ATTACH.exists():
    raise SystemExit("数据目录不存在")

MOD = Path(__file__).resolve().parents[1]
PROC = MOD / "data" / "processed"
TAB = MOD / "tables"
RES = MOD / "results"
for folder in (PROC, TAB, RES):
    folder.mkdir(parents=True, exist_ok=True)

REGIONS = ["RegionA", "RegionB", "RegionC", "RegionD", "RegionE", "RegionF"]
TOL_COST = 1e-4
TOL = 1e-6
NAMES = ("u", "qR", "qG", "d", "gL", "s", "w", "E")


def read_inputs():
    rt = pd.read_excel(ATTACH / "region_time_data.xlsx")
    rt = rt[rt.Hour.between(0, 2406)].copy()
    storage = pd.read_excel(ATTACH / "storage_information.xlsx", sheet_name="storage_information")
    storage = storage.set_index("Region").loc[REGIONS]
    gpu = pd.read_excel(ATTACH / "GPU_information.xlsx", sheet_name="GPU中心基础情况").set_index("Region").loc[REGIONS]
    return rt, storage, gpu["PUE"].to_dict()


def make_arrays(rt, region, pue):
    q = rt[rt.Region == region].sort_values("Hour").reset_index(drop=True)
    assert len(q) == 2407 and q.Hour.to_list() == list(range(2407))
    load = float(pue[region]) * (q.Baseline_AI_IT_Load_MW.to_numpy(float) + q.NonAI_IT_Load_MW.to_numpy(float))
    return q, load


def solve_region(q, st, pue, no_storage=False):
    T = len(q)
    n = len(NAMES) * T
    off = {name: i * T for i, name in enumerate(NAMES)}

    def ix(name, t):
        return off[name] + t

    # Renewable allocation, load balance, and SOC dynamics.
    rows, cols, vals, rhs = [], [], [], []
    row = 0
    load = float(pue) * (q.Baseline_AI_IT_Load_MW.to_numpy(float) + q.NonAI_IT_Load_MW.to_numpy(float))
    avail = q.AvailableRenewable_MW.to_numpy(float)
    for t in range(T):
        for name in ("u", "qR", "s", "w"):
            rows.append(row); cols.append(ix(name, t)); vals.append(1.0)
        rhs.append(avail[t]); row += 1
        for name in ("u", "d", "gL"):
            rows.append(row); cols.append(ix(name, t)); vals.append(1.0)
        rhs.append(load[t]); row += 1
        rows += [row, row, row, row]
        cols += [ix("E", t), ix("qR", t), ix("qG", t), ix("d", t)]
        vals += [1.0, -float(st.ChargeEfficiency), -float(st.ChargeEfficiency), 1.0 / float(st.DischargeEfficiency)]
        if t == 0:
            rhs.append(float(st.InitialSOC_MWh))
        else:
            rows.append(row); cols.append(ix("E", t - 1)); vals.append(-1.0)
            rhs.append(0.0)
        row += 1
    Aeq = coo_matrix((vals, (rows, cols)), shape=(row, n)).tocsr()
    beq = np.asarray(rhs, dtype=float)

    # Charge, purchase, and terminal-SOC constraints.
    ur, uc, uv, brhs = [], [], [], []
    r = 0
    for t in range(T):
        ur += [r, r]; uc += [ix("qR", t), ix("qG", t)]; uv += [1.0, 1.0]
        brhs.append(float(st.MaxChargePower_MW)); r += 1
        ur += [r, r]; uc += [ix("gL", t), ix("qG", t)]; uv += [1.0, 1.0]
        brhs.append(float(st.MaxGridImport_MW)); r += 1
    ur.append(r); uc.append(ix("E", T - 1)); uv.append(-1.0)
    brhs.append(-float(st.InitialSOC_MWh)); r += 1
    Aub_base = coo_matrix((uv, (ur, uc)), shape=(r, n)).tocsr()
    bub_base = np.asarray(brhs, dtype=float)

    buy = q.ElectricityPrice_CNY_per_MWh.to_numpy(float)
    sell = q.SellPrice_CNY_per_MWh.to_numpy(float)
    c_cost = np.zeros(n)
    c_cost[off["gL"]:off["gL"] + T] = buy
    c_cost[off["qG"]:off["qG"] + T] = buy
    c_cost[off["s"]:off["s"] + T] = -sell
    c_throughput = np.zeros(n)
    for name in ("qR", "qG", "d"):
        c_throughput[off[name]:off[name] + T] = 1.0

    sell_cap = min(float(st.SellLimit_MW), float(st.MaxGridExport_MW))
    bnds = []
    for name in NAMES:
        for _ in range(T):
            if name == "E":
                bnds.append((float(st.MinSOC_MWh), float(st.StorageCapacity_MWh)))
            elif name == "d":
                bnds.append((0.0, float(st.MaxDischargePower_MW) if not no_storage else 0.0))
            elif name == "s":
                bnds.append((0.0, sell_cap))
            elif name == "gL":
                bnds.append((0.0, float(st.MaxGridImport_MW)))
            elif name in ("qR", "qG"):
                bnds.append((0.0, float(st.MaxChargePower_MW) if not no_storage else 0.0))
            else:
                bnds.append((0.0, None))

    r1 = linprog(c_cost, A_ub=Aub_base, b_ub=bub_base, A_eq=Aeq, b_eq=beq,
                 bounds=bnds, method="highs")
    if not r1.success:
        raise RuntimeError("Stage 1 failed for {}: {}".format(st.name, r1.message))
    cost_star = float(r1.fun)
    cost_row = coo_matrix(c_cost.reshape(1, -1))
    A2 = vstack([Aub_base, cost_row], format="csr")
    b2 = np.r_[bub_base, cost_star + TOL_COST]
    r2 = linprog(c_throughput, A_ub=A2, b_ub=b2, A_eq=Aeq, b_eq=beq,
                 bounds=bnds, method="highs")
    if not r2.success:
        raise RuntimeError("Stage 2 failed for {}: {}".format(st.name, r2.message))
    x = r2.x
    out = {name: x[off[name]:off[name] + T] for name in NAMES}
    out["GridPurchase"] = out["gL"] + out["qG"]
    out["ChargePower"] = out["qR"] + out["qG"]
    out["NetGridImport"] = out["GridPurchase"] - out["s"]
    out["Cost"] = float(c_cost @ x)
    out["CostStage1"] = cost_star
    out["Throughput"] = float(c_throughput @ x)
    out["Stage1SCDHours"] = int(np.sum((r1.x[off["qR"]:off["qR"] + T] + r1.x[off["qG"]:off["qG"] + T] > TOL) & (r1.x[off["d"]:off["d"] + T] > TOL)))
    out["Stage2SCDHours"] = int(np.sum((out["ChargePower"] > TOL) & (out["d"] > TOL)))
    return out, load


def indicators(q, load, sol):
    carbon = float(np.sum(sol["GridPurchase"] * q.CarbonIntensity_tCO2_per_MWh.to_numpy(float)))
    denom = float(q.AvailableRenewable_MW.sum())
    eta = float(np.sum(sol["u"] + sol["qR"] + sol["s"]) / denom)
    net = sol["NetGridImport"]
    return {
        "Cost_CNY": sol["Cost"],
        "Carbon_tCO2": carbon,
        "PeakImport_MW": float(max(0.0, net.max())),
        "SigmaGrid_MW": float(net.std(ddof=0)),
        "MeanAbsRamp_MW": float(np.abs(np.diff(net)).mean()),
        "Eta_R": eta,
        "GridPurchase_MWh": float(sol["GridPurchase"].sum()),
        "GridSell_MWh": float(sol["s"].sum()),
        "Curtailment_MWh": float(sol["w"].sum()),
        "Throughput_MWh": sol["Throughput"],
        "Charge_MWh": float(sol["ChargePower"].sum()),
        "Discharge_MWh": float(sol["d"].sum()),
        "TerminalSOC_MWh": float(sol["E"][-1]),
        "Stage1SCDHours": sol["Stage1SCDHours"],
        "Stage2SCDHours": sol["Stage2SCDHours"],
        "FacilityLoadStd_MW": float(load.std(ddof=0)),
    }


def raw_baseline(q, load):
    grid = q.GridPurchase_MW.to_numpy(float)
    sell = q.GridSell_MW.to_numpy(float)
    net = grid - sell
    return {
        "Cost_CNY": float(np.sum(grid * q.ElectricityPrice_CNY_per_MWh - sell * q.SellPrice_CNY_per_MWh)),
        "Carbon_tCO2": float(np.sum(grid * q.CarbonIntensity_tCO2_per_MWh)),
        "PeakImport_MW": float(max(0.0, net.max())),
        "SigmaGrid_MW": float(net.std(ddof=0)),
        "MeanAbsRamp_MW": float(np.abs(np.diff(net)).mean()),
        "Eta_R": float(np.sum(q.UsedRenewable_MW + q.RenewableCharge_MW + q.GridSell_MW) / q.AvailableRenewable_MW.sum()),
        "GridPurchase_MWh": float(grid.sum()),
        "GridSell_MWh": float(sell.sum()),
        "Curtailment_MWh": float(q.Curtailment_MW.sum()),
        "Throughput_MWh": float((q.ChargePower_MW + q.DischargePower_MW).sum()),
        "Charge_MWh": float(q.ChargePower_MW.sum()),
        "Discharge_MWh": float(q.DischargePower_MW.sum()),
        "TerminalSOC_MWh": float(q.SOC_MWh.iloc[-1]),
        "Stage1SCDHours": int(np.sum((q.ChargePower_MW > TOL) & (q.DischargePower_MW > TOL))),
        "Stage2SCDHours": np.nan,
        "FacilityLoadStd_MW": float(load.std(ddof=0)),
    }


def validate(q, st, load, sol):
    r1 = q.AvailableRenewable_MW.to_numpy(float) - sol["u"] - sol["qR"] - sol["s"] - sol["w"]
    r2 = load - sol["u"] - sol["d"] - sol["gL"]
    r3 = sol["GridPurchase"] - sol["gL"] - sol["qG"]
    r4 = sol["ChargePower"] - sol["qR"] - sol["qG"]
    soc_prev = np.r_[float(st.InitialSOC_MWh), sol["E"][:-1]]
    r5 = sol["E"] - soc_prev - float(st.ChargeEfficiency) * sol["ChargePower"] + sol["d"] / float(st.DischargeEfficiency)
    return {
        "renewable_balance_max_mw": float(np.max(np.abs(r1))),
        "load_balance_max_mw": float(np.max(np.abs(r2))),
        "grid_purchase_split_max_mw": float(np.max(np.abs(r3))),
        "charge_split_max_mw": float(np.max(np.abs(r4))),
        "soc_dynamics_max_mwh": float(np.max(np.abs(r5))),
        "terminal_soc_gap_mwh": float(sol["E"][-1] - float(st.InitialSOC_MWh)),
        "min_soc_margin_mwh": float(sol["E"].min() - float(st.MinSOC_MWh)),
        "max_soc_margin_mwh": float(float(st.StorageCapacity_MWh) - sol["E"].max()),
        "max_charge_margin_mw": float(float(st.MaxChargePower_MW) - sol["ChargePower"].max()),
        "max_discharge_margin_mw": float(float(st.MaxDischargePower_MW) - sol["d"].max()),
        "max_grid_import_margin_mw": float(float(st.MaxGridImport_MW) - sol["GridPurchase"].max()),
        "max_grid_export_margin_mw": float(min(float(st.SellLimit_MW), float(st.MaxGridExport_MW)) - sol["s"].max()),
        "stage2_scd_hours": int(sol["Stage2SCDHours"]),
    }


def main():
    rt, storage, pue = read_inputs()
    summary_rows, hourly_rows, audit_rows = [], [], []
    loads = {}
    for region in REGIONS:
        q, load = make_arrays(rt, region, pue)
        loads[region] = load
        st = storage.loc[region]
        b0 = raw_baseline(q, load)
        e0, _ = solve_region(q, st, pue[region], no_storage=True)
        e1, _ = solve_region(q, st, pue[region], no_storage=False)
        e0m = indicators(q, load, e0)
        e1m = indicators(q, load, e1)
        for label, metric in (("B0_附件基准", b0), ("E0_无储能调度", e0m), ("E1_BESS协同调度", e1m)):
            summary_rows.append({"Region": region, "方案": label, **metric})
        for t in range(len(q)):
            for label, sol in (("E0_无储能调度", e0), ("E1_BESS协同调度", e1)):
                hourly_rows.append({
                    "Region": region, "Hour": t, "方案": label, "FacilityLoad_MW": load[t],
                    "AvailableRenewable_MW": q.AvailableRenewable_MW.iloc[t],
                    "u_直接新能源_MW": sol["u"][t], "qR_新能源充电_MW": sol["qR"][t],
                    "qG_电网充电_MW": sol["qG"][t], "d_放电_MW": sol["d"][t],
                    "gL_电网供负荷_MW": sol["gL"][t], "s_新能源售电_MW": sol["s"][t],
                    "w_弃电_MW": sol["w"][t], "SOC_MWh": sol["E"][t],
                    "GridPurchase_MW": sol["GridPurchase"][t], "NetGridImport_MW": sol["NetGridImport"][t],
                })
        check = validate(q, st, load, e1)
        audit_rows.append({"Region": region, **check})

    summary = pd.DataFrame(summary_rows)
    hourly = pd.DataFrame(hourly_rows)
    # System ratios and fluctuation metrics must be reconstructed from the
    # system-wide hourly sequence, rather than summed from regional ratios.
    system_load = np.sum(np.vstack([loads[r] for r in REGIONS]), axis=0)
    available_total = float(rt.AvailableRenewable_MW.sum())
    system_rows = []
    sum_keys = [
        "Cost_CNY", "Carbon_tCO2", "GridPurchase_MWh", "GridSell_MWh",
        "Curtailment_MWh", "Throughput_MWh", "Charge_MWh", "Discharge_MWh",
        "TerminalSOC_MWh", "Stage1SCDHours",
    ]
    for label in ("B0_附件基准", "E0_无储能调度", "E1_BESS协同调度"):
        sub = summary[summary["方案"] == label]
        row = {"Region": "System", "方案": label}
        for key in sum_keys:
            row[key] = float(sub[key].sum())
        row["Stage2SCDHours"] = np.nan if label == "B0_附件基准" else float(sub["Stage2SCDHours"].sum())
        if label == "B0_附件基准":
            z = rt.groupby("Hour", as_index=True).agg(
                Net=("NetGridImport_MW", "sum"),
                Renewable=("UsedRenewable_MW", "sum"),
                Charge=("RenewableCharge_MW", "sum"),
                Sell=("GridSell_MW", "sum"),
            ).reindex(range(2407))
            row["Eta_R"] = float((z.Renewable + z.Charge + z.Sell).sum() / available_total)
            net = z.Net.to_numpy(float)
        else:
            z = hourly[hourly["方案"] == label].groupby("Hour", as_index=True).agg(
                Net=("NetGridImport_MW", "sum"),
                Renewable=("u_直接新能源_MW", "sum"),
                Charge=("qR_新能源充电_MW", "sum"),
                Sell=("s_新能源售电_MW", "sum"),
            ).reindex(range(2407))
            row["Eta_R"] = float((z.Renewable + z.Charge + z.Sell).sum() / available_total)
            net = z.Net.to_numpy(float)
        row["PeakImport_MW"] = float(max(0.0, net.max()))
        row["SigmaGrid_MW"] = float(net.std(ddof=0))
        row["MeanAbsRamp_MW"] = float(np.abs(np.diff(net)).mean())
        row["FacilityLoadStd_MW"] = float(system_load.std(ddof=0))
        system_rows.append(row)
    summary = pd.concat([summary, pd.DataFrame(system_rows)], ignore_index=True, sort=False)
    audit = pd.DataFrame(audit_rows)
    audit["Passed"] = (
        (audit.renewable_balance_max_mw <= TOL) & (audit.load_balance_max_mw <= TOL)
        & (audit.grid_purchase_split_max_mw <= TOL) & (audit.charge_split_max_mw <= TOL)
        & (audit.soc_dynamics_max_mwh <= TOL) & (audit.terminal_soc_gap_mwh >= -TOL)
        & (audit.min_soc_margin_mwh >= -TOL) & (audit.max_soc_margin_mwh >= -TOL)
        & (audit.max_charge_margin_mw >= -TOL) & (audit.max_discharge_margin_mw >= -TOL)
        & (audit.max_grid_import_margin_mw >= -TOL) & (audit.max_grid_export_margin_mw >= -TOL)
        & (audit.stage2_scd_hours == 0)
    )
    summary.to_csv(TAB / "q3_metrics_summary.csv", index=False, encoding="utf-8-sig")
    hourly.to_csv(PROC / "q3_energy_dispatch_0_2406.csv", index=False, encoding="utf-8-sig")
    audit.to_csv(RES / "q3_constraint_audit.csv", index=False, encoding="utf-8-sig")
    e0_total = summary[(summary.Region == "System") & (summary.方案 == "E0_无储能调度")].iloc[0]
    e1_total = summary[(summary.Region == "System") & (summary.方案 == "E1_BESS协同调度")].iloc[0]
    out = {
        "status": "PASS" if bool(audit.Passed.all()) else "FAIL",
        "model_status": "DRAFT / NEEDS_REVIEW",
        "e0_cost_cny": float(e0_total.Cost_CNY), "e1_cost_cny": float(e1_total.Cost_CNY),
        "bess_value_cny": float(e0_total.Cost_CNY - e1_total.Cost_CNY),
        "e0_carbon_tco2": float(e0_total.Carbon_tCO2), "e1_carbon_tco2": float(e1_total.Carbon_tCO2),
        "stage2_scd_hours": int(e1_total.Stage2SCDHours),
    }
    (RES / "q3_run_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
