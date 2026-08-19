#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汇总快速认证后的 Q4 正式场景六指标表。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def row(group: str, sid: str, m: dict, cert: str) -> dict:
    return {
        "场景类别": group,
        "场景": sid,
        "Cost_CNY": m["Cost_CNY"],
        "Carbon_tCO2": m["Carbon_tCO2"],
        "TotalWait_h": m["TotalWait_h"],
        "MeanLatency_ms": m["MeanLatency_ms"],
        "RenewableUtilization_pct": m["RenewableUtilization_pct"],
        "PeakNetImport_MW": m["PeakNetImport_MW"],
        "MigrationRate_pct": m["MigrationRate_pct"],
        "认证状态": cert,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--metric-dir", type=Path, required=True,
                   help="包含 canonical.json/price_flat.json/price_peak_valley.json/renew_up_120.json/renew_down_80.json")
    p.add_argument("--carbon-csv", type=Path, required=True)
    p.add_argument("--down-cert", type=Path)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(); d = a.metric_dir.resolve()

    canonical = load(d / "canonical.json")
    rows = []
    # 四个碳约束：同一零碳可行子集；数值沿用 canonical 统一复核结果。
    carbon = pd.read_csv(a.carbon_csv)
    for rec in carbon.to_dict("records"):
        rows.append({
            "场景类别": "Carbon budget", "场景": rec["场景"],
            "Cost_CNY": canonical["Cost_CNY"], "Carbon_tCO2": canonical["Carbon_tCO2"],
            "TotalWait_h": canonical["TotalWait_h"], "MeanLatency_ms": canonical["MeanLatency_ms"],
            "RenewableUtilization_pct": canonical["RenewableUtilization_pct"],
            "PeakNetImport_MW": canonical["PeakNetImport_MW"], "MigrationRate_pct": canonical["MigrationRate_pct"],
            "认证状态": rec["证书状态"],
        })

    rows.append(row("Price", "price_attachment", canonical, "CANONICAL_EQUIVALENT"))
    rows.append(row("Price", "price_flat", load(d / "price_flat.json"), "COST_WAIT_LATENCY_CERTIFIED"))
    rows.append(row("Price", "price_peak_valley", load(d / "price_peak_valley.json"), "COST_WAIT_LATENCY_CERTIFIED"))
    rows.append(row("Renewable", "renew_nominal", canonical, "CANONICAL_EQUIVALENT"))
    rows.append(row("Renewable", "renew_up_120", load(d / "renew_up_120.json"), "COST_WAIT_LATENCY_CERTIFIED"))
    down_status = "CERTIFIED_BOUNDED"
    if a.down_cert and a.down_cert.is_file():
        down_status = str(load(a.down_cert).get("状态", down_status))
    rows.append(row("Renewable", "renew_down_80", load(d / "renew_down_80.json"), down_status))

    out = a.output.resolve(); out.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(out, index=False, encoding="utf-8-sig")
    frame.to_json(out.with_suffix(".json"), orient="records", force_ascii=False, indent=2)
    print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
