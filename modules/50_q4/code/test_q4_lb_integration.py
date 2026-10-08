"""Small end-to-end smoke test with a linear two-job energy recourse oracle."""
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, hstack

sys.path.insert(0, str(Path(__file__).parent))
from q4_local_branching import run_q4


class Pool:
    def __init__(self):
        self.cols = []
        for i in range(2):
            for s in range(2):
                self.add(i, 0, s)

    def add(self, i, r, s):
        col = (int(i), int(r), int(s))
        if col not in self.cols:
            self.cols.append(col)

    def arrays(self):
        return tuple(np.asarray([col[k] for col in self.cols], dtype=int)
                     for k in range(3))

    def __len__(self):
        return len(self.cols)


class IntegrationTest(unittest.TestCase):
    def test_true_energy_acceptance(self):
        pool = Pool()
        data = SimpleNamespace(task=pd.DataFrame({"TaskID": [101, 102]}),
                               renew=np.ones((1, 2)))

        def facility_load(pool, data, x):
            return np.array([[float(x[0] + x[2]), 0.]])

        def energy_lp(load, data, renew_override=None):
            cost = 5.0 + 10.0 * load[0, 0]
            return {"success": True, "cost": cost, "region_cost": np.array([cost]),
                    "lam": np.array([[10., 0.]]), "audit": {}}

        def add_region_cuts(cuts, data, load, energy, regions=None):
            cuts.append(SimpleNamespace(
                const=float(energy["cost"] - 10*load[0, 0]),
                lam=energy["lam"], region=0))
            return 1

        def cut_matrix(pool, data, cuts):
            row = [10. if s == 0 else 0. for _, _, s in pool.cols]
            return csr_matrix([row for _ in cuts])

        def assemble_stage_model(assign, resource, cuts, rhs, constants,
                                 objective, wait, cut_regions, spec):
            n = assign.shape[1]
            aub = hstack([cuts, csr_matrix(-np.ones((len(cut_regions), 1)))],
                         format="csr")
            aeq = hstack([assign, csr_matrix((2, 1))], format="csr")
            return (aub, -np.asarray(constants), aeq, np.ones(2),
                    {"c": np.r_[np.zeros(n), 1.]})

        full = types.ModuleType("q4_full_solver")
        full.R = 1
        full.REGIONS = ["R0"]
        full.read_data = lambda _: data
        full.make_presolve_rows = lambda _: (None, None, np.zeros(0), None)
        full.resource_matrix = lambda *args: csr_matrix((0, len(pool)))
        full.assignment_matrix = lambda pool, n: csr_matrix(
            [[1, 1, 0, 0], [0, 0, 1, 1]])
        full.facility_load = facility_load
        full.energy_lp = energy_lp

        qos = types.ModuleType("q4_qos_refinement")
        qos.load_state = lambda _: (pool, [], None, 0, None, None, 2)
        qos.cut_matrix = cut_matrix
        qos.add_region_cuts = add_region_cuts
        qos.StageSpec = lambda *args: None
        qos.assemble_stage_model = assemble_stage_model
        qos.audit_solution = lambda *args: (None, {"violation": 0})

        old_full = sys.modules.get("q4_full_solver")
        old_qos = sys.modules.get("q4_qos_refinement")
        sys.modules["q4_full_solver"] = full
        sys.modules["q4_qos_refinement"] = qos
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                start = root / "start.csv"
                pd.DataFrame({
                    "TaskID": [101, 102], "区域": ["R0", "R0"],
                    "开工小时": [0, 0]}).to_csv(start, index=False)
                args = SimpleNamespace(
                    attachment_dir=root, state_dir=root, schedule_csv=start,
                    output_dir=root/"result", renew_factor=1.0, k=1, max_k=2,
                    iterations=2, node_seconds=5.0, max_seconds=30.0,
                    min_improvement=1e-3, cut_tolerance=1e-3)
                summary = run_q4(args)
                self.assertAlmostEqual(summary["initial_true_cost"], 25.)
                self.assertAlmostEqual(summary["best_true_cost"], 5.)
                self.assertEqual(summary["iterations_completed"], 2)
                self.assertFalse(summary["full_domain_integer_optimality_proved"])
                actual = pd.read_csv(args.output_dir/"best_schedule.csv")
                self.assertEqual(actual["开工小时"].tolist(), [1, 1])
        finally:
            if old_full is None:
                del sys.modules["q4_full_solver"]
            else:
                sys.modules["q4_full_solver"] = old_full
            if old_qos is None:
                del sys.modules["q4_qos_refinement"]
            else:
                sys.modules["q4_qos_refinement"] = old_qos


if __name__ == "__main__":
    unittest.main()
