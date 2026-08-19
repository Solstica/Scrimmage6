from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd
import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))

from q4_full_solver import (
    Data, ColumnPool, Cut, H_ENERGY, R, assignment_matrix, energy_lp,
    facility_load, make_presolve_rows, price_all, resource_matrix,
)
from q4_qos_refinement import (
    StageSpec,
    best_missing,
    fmt_time,
    load_latency_incumbent,
    load_state,
    mip_wait,
    pool_values,
    price_full_domain,
    restricted_mip_lower_bound,
    save_latency_incumbent,
    save_state,
    solve_extensive_mip,
    use_bar,
    use_ext,
)


def small_data():
    task = pd.DataFrame({
        "TaskID": [1, 2],
        "TaskType": ["BatchInference", "RealTimeInference"],
    })
    legal = np.zeros((2, R), dtype=bool)
    legal[:, :2] = True
    zeros = np.zeros((R, H_ENERGY))
    return Data(
        task=task,
        type_idx=np.asarray([0, 1], dtype=np.int8),
        source=np.asarray([0, 0], dtype=np.int8),
        arrival=np.asarray([0, 2], dtype=np.int16),
        latest=np.asarray([4.0, 6.0]),
        duration=np.asarray([60.0, 60.0]),
        gpu=np.asarray([1.0, 1.0]),
        alpha=np.asarray([1.0, 2.0]),
        legal=legal,
        pue=np.ones(R),
        gpu_cap=np.full(R, 100.0),
        it_cap=np.full(R, 500.0),
        non_ai=zeros.copy(),
        renew=zeros.copy(),
        price=zeros.copy(),
        sell_price=zeros.copy(),
        carbon=zeros.copy(),
        storage=pd.DataFrame(index=range(R)),
    )


def test_best_missing_skips_only_active_starts_in_range():
    found = best_missing(np.asarray([0.0, 1.0, 2.0]), 5, {1, 5, 9})
    assert found == (1.0, 6)


def test_wait_and_latency_pricing_scan_missing_complete_domain():
    data = small_data()
    pool = ColumnPool()
    pool.add(0, 0, 2)
    pool.add(1, 0, 2)
    gpu_row, it_row, rhs, _ = make_presolve_rows(data)
    latency = np.full((R, R), 100.0)
    latency[0, 0] = 5.0
    latency[0, 1] = 7.0
    cuts = [Cut(0.0, np.zeros((R, H_ENERGY)))]
    wait_additions, wait_min, _ = price_full_domain(
        pool, data, gpu_row, it_row, np.zeros(len(rhs)), np.zeros(1), cuts,
        np.asarray([10.0, 10.0]), StageSpec("Wait阶段", "wait", 0.0),
        latency, None, 1e-9, 2,
    )
    assert wait_min == -10.0
    assert {(task, region, start) for task, region, start, _ in wait_additions} == {
        (0, 0, 0), (0, 1, 0), (1, 1, 2),
    }
    latency_additions, _, _ = price_full_domain(
        pool, data, gpu_row, it_row, np.zeros(len(rhs)), np.zeros(1), cuts,
        np.asarray([20.0, 20.0]), StageSpec("Latency阶段", "latency", 0.0, 0.0),
        latency, -2.0, 1e-9, 2,
    )
    assert all(start == int(data.arrival[task]) for task, _, start, _ in latency_additions)


def test_cost_pricing_keeps_realtime_start_fixed_at_arrival():
    data = small_data()
    pool = ColumnPool()
    pool.add(0, 0, 2)
    pool.add(1, 0, 2)
    gpu_row, it_row, rhs, _ = make_presolve_rows(data)
    cuts = [Cut(0.0, np.zeros((R, H_ENERGY)))]
    additions = price_all(
        pool, data, gpu_row, it_row, np.zeros(len(rhs)), np.zeros(1), cuts,
        np.asarray([10.0, 10.0]), 1e-9,
    )
    realtime = [row for row in additions if row[0] == 1]
    assert realtime
    assert all(start == 2 for _, _, start, _ in realtime)


def test_lexicographic_checkpoint_roundtrip_keeps_float64_cuts(tmp_path):
    pool = ColumnPool()
    pool.add(0, 1, 2)
    lam = np.full((R, H_ENERGY), 1.0 / 3.0, dtype=np.float64)
    save_state(tmp_path, pool, [Cut(12.5, lam)], "latency", 4, 100.0, 6.0, 1)
    restored, cuts, stage, iteration, cost_cap, wait_star, initial = load_state(tmp_path)
    assert len(restored) == 1
    assert cuts[0].lam.dtype == np.float64
    assert np.array_equal(cuts[0].lam, lam)
    assert (stage, iteration, cost_cap, wait_star, initial) == ("latency", 4, 100.0, 6.0, 1)


def test_latency_incumbent_only_accepts_better_true_feasible_schedule(tmp_path):
    data = small_data()
    pool = ColumnPool()
    pool.add(0, 0, 0)
    pool.add(0, 1, 0)
    pool.add(1, 0, 2)
    pool.add(1, 1, 2)
    latency = np.full((R, R), 10.0)
    latency[0, 0] = 2.0
    latency[0, 1] = 5.0
    first = save_latency_incumbent(tmp_path, pool, data, np.asarray([0, 1, 0, 1]), latency, {"cost": 1.0}, "first")
    better = save_latency_incumbent(tmp_path, pool, data, np.asarray([1, 0, 1, 0]), latency, {"cost": 2.0}, "better")
    worse = save_latency_incumbent(tmp_path, pool, data, np.asarray([0, 1, 0, 1]), latency, {"cost": 3.0}, "worse")
    assert first["总时延_ms"] == 10.0
    assert better["总时延_ms"] == 4.0
    assert worse["总时延_ms"] == 4.0
    assert load_latency_incumbent(tmp_path)["来源"] == "better"
    forced = save_latency_incumbent(tmp_path, pool, data, np.asarray([0, 1, 0, 1]), latency, {"cost": 4.0}, "new_cap", force=True)
    assert forced["总时延_ms"] == 10.0
    assert load_latency_incumbent(tmp_path)["来源"] == "new_cap"


def test_restricted_mip_lower_bound_prefers_dual_bound():
    class Result:
        fun = 12.0
        mip_dual_bound = 10.5

    assert restricted_mip_lower_bound(Result()) == 10.5


def test_extensive_mip_lower_bound_prefers_dictionary_dual_bound():
    result = {"fun": 12.0, "mip_dual_bound": 10.5}
    assert restricted_mip_lower_bound(result) == 10.5


def test_plain_progress_mode_and_mip_heartbeat(capsys):
    class Args:
        progress_mode = "plain"

    assert not use_bar(Args())
    assert fmt_time(3661) == "1小时01分01秒"
    result = mip_wait("单元测试", lambda: time.sleep(0.04) or 7, psutil.Process(), 0.01)
    assert result == 7
    output = capsys.readouterr().out
    assert "MIP心跳" in output
    assert "不代表已经收敛" in output


def test_latency_uses_true_energy_extensive_mip():
    spec = StageSpec("Latency阶段", "latency", -1.0, 32.0)
    assert use_ext(spec)
    assert use_ext(StageSpec("Wait阶段", "wait", -1.0))
    assert use_ext(StageSpec("Cost阶段", "cost", None))


def test_small_latency_extensive_mip_matches_true_energy():
    data = small_data()
    data.price[:] = 1.0
    data.storage = pd.DataFrame({
        "ChargeEfficiency": np.ones(R),
        "DischargeEfficiency": np.ones(R),
        "InitialSOC_MWh": np.zeros(R),
        "MaxChargePower_MW": np.zeros(R),
        "MaxGridImport_MW": np.full(R, 10.0),
        "MaxDischargePower_MW": np.zeros(R),
        "SellLimit_MW": np.zeros(R),
        "MaxGridExport_MW": np.zeros(R),
        "MinSOC_MWh": np.zeros(R),
        "StorageCapacity_MWh": np.zeros(R),
    })
    pool = ColumnPool()
    for task, start in ((0, 0), (1, 2)):
        pool.add(task, 0, start)
        pool.add(task, 1, start)
    gpu_row, it_row, rhs, _ = make_presolve_rows(data)
    assign = assignment_matrix(pool, len(data.task))
    resource = resource_matrix(pool, data, gpu_row, it_row, len(rhs))
    wait, _ = pool_values(pool, data, np.zeros((R, R)))
    objective = np.asarray([1.0, 5.0, 1.0, 5.0])
    spec = StageSpec("Latency阶段", "latency", 3.001, 0.0)
    result = solve_extensive_mip(
        pool, data, assign, resource, rhs, objective, wait, spec, 30.0, 1e-9,
    )
    assert result["success"], result["message"]
    x = np.rint(result["x"][:len(pool)])
    energy = energy_lp(facility_load(pool, data, x), data)
    assert energy["success"]
    assert energy["cost"] <= spec.cost_cap + 1e-7
    assert float(wait @ x) <= spec.wait_cap + 1e-7
    assert float(objective @ x) == 2.0
