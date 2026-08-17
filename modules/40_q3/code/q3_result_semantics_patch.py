#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q3 result-semantics patch.

Usage:
    python q3_result_semantics_patch.py <q3_module_dir> <attachment_dir>

This patch does not change the Q3 optimization model or decision variables.
It only corrects result aggregation/labels:
1) system PeakImport is reported as the maximum regional peak net import,
   rather than allowing exports in other regions to cancel a regional import peak;
2) the former cross-region aggregate-net peak is retained under an explicit name;
3) gross grid-purchase peak is added;
4) tiny solver-tolerance artifacts are mapped to numerical zero for display.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

if len(sys.argv) != 3:
    raise SystemExit("Usage: python q3_result_semantics_patch.py <q3_module_dir> <attachment_dir>")

MOD = Path(sys.argv[1]).resolve()
ATTACH = Path(sys.argv[2]).resolve()
TAB = MOD / "tables"
PROC = MOD / "data" / "processed"

summary_path = TAB / "q3_metrics_summary.csv"
hourly_path = PROC / "q3_energy_dispatch_0_2406.csv"
summary = pd.read_csv(summary_path)
hourly = pd.read_csv(hourly_path)
rt = pd.read_excel(ATTACH / "region_time_data.xlsx")
rt = rt[rt.Hour.between(0, 2406)].copy()

summary["AggregateNetExchangePeak_MW"] = np.nan
summary["GrossGridPurchasePeak_MW"] = np.nan

labels = ["B0_附件基准", "E0_无储能调度", "E1_BESS协同调度"]
for label in labels:
    region_mask = (summary["方案"] == label) & (summary["Region"] != "System")
    system_mask = (summary["方案"] == label) & (summary["Region"] == "System")
    regional_peak = float(summary.loc[region_mask, "PeakImport_MW"].max())

    if label == "B0_附件基准":
        z = rt.groupby("Hour", as_index=True).agg(
            Net=("NetGridImport_MW", "sum"),
            Purchase=("GridPurchase_MW", "sum"),
        ).reindex(range(2407))
    else:
        q = hourly[hourly["方案"] == label].copy()
        z = q.groupby("Hour", as_index=True).agg(
            Net=("NetGridImport_MW", "sum"),
            Purchase=("GridPurchase_MW", "sum"),
        ).reindex(range(2407))

    aggregate_net_peak = float(max(0.0, z["Net"].to_numpy(float).max()))
    gross_purchase_peak = float(max(0.0, z["Purchase"].to_numpy(float).max()))

    # Canonical system peak = maximum regional peak net purchase.
    summary.loc[system_mask, "PeakImport_MW"] = regional_peak
    summary.loc[system_mask, "AggregateNetExchangePeak_MW"] = aggregate_net_peak
    summary.loc[system_mask, "GrossGridPurchasePeak_MW"] = gross_purchase_peak

# Tiny Stage-2 tolerance artifacts are presentation zeros only.
zero_rules = {
    "Cost_CNY": 1e-3,
    "Carbon_tCO2": 1e-6,
    "PeakImport_MW": 1e-6,
    "GridPurchase_MWh": 1e-6,
    "SigmaGrid_MW": 1e-6,
    "MeanAbsRamp_MW": 1e-6,
}
for col, tol in zero_rules.items():
    if col in summary.columns:
        arr = summary[col].to_numpy(float)
        arr[np.abs(arr) < tol] = 0.0
        summary[col] = arr

summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
print("patched:", summary_path)
print(summary[summary.Region == "System"][
    ["方案", "PeakImport_MW", "AggregateNetExchangePeak_MW", "GrossGridPurchasePeak_MW",
     "FacilityLoadStd_MW", "SigmaGrid_MW", "MeanAbsRamp_MW"]
].to_string(index=False))
