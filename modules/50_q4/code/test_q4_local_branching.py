import sys
import unittest
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix

sys.path.insert(0, str(Path(__file__).parent))
from q4_local_branching import neighborhood_row, solve_binary_neighborhood


class LocalBranchingTests(unittest.TestCase):
    def test_asymmetric_neighborhood(self):
        incumbent = np.array([1, 0, 1, 0, 1, 0], float)
        row, rhs = neighborhood_row(incumbent, 6, 3, 1)
        self.assertEqual(rhs, -2)
        self.assertEqual(float((row @ incumbent).item()), -3)
        self.assertEqual(float((row @ np.array([1, 0, 0, 1, 0, 1])).item()), -1)
        with self.assertRaises(ValueError):
            neighborhood_row(np.array([1, 0, 1, 0, 0, 0], float), 6, 3, 1)

    def test_task_reassignments_limited_by_k(self):
        incumbent = np.array([1, 0, 1, 0, 1, 0], float)
        assignment = csr_matrix([[1, 1, 0, 0, 0, 0],
                                 [0, 0, 1, 1, 0, 0],
                                 [0, 0, 0, 0, 1, 1]], dtype=float)
        objective = np.array([10, 1, 10, 1, 10, 1], float)
        for k, expected in ((0, 30), (1, 21), (2, 12), (3, 3)):
            result = solve_binary_neighborhood(
                c=objective, aub=csr_matrix((0, 6)), bub=np.zeros(0),
                aeq=assignment, beq=np.ones(3), n_binary=6,
                incumbent=incumbent, task_count=3, k=k, seconds=5)
            self.assertEqual(result.status, 0, result.message)
            self.assertAlmostEqual(result.fun, expected, places=6)

    def test_benders_epigraph_and_improvement_cutoff(self):
        incumbent = np.array([1, 0, 1, 0], float)
        assignment = csr_matrix([[1, 1, 0, 0, 0],
                                 [0, 0, 1, 1, 0]], dtype=float)
        benders = csr_matrix([[10, 2, 10, 2, -1]], dtype=float)
        objective = np.array([0, 0, 0, 0, 1], float)
        kwargs = dict(c=objective, aub=benders, bub=np.zeros(1),
                      aeq=assignment, beq=np.ones(2), n_binary=4,
                      incumbent=incumbent, task_count=2, seconds=5, cutoff=19)
        improved = solve_binary_neighborhood(k=1, **kwargs)
        self.assertEqual(improved.status, 0)
        self.assertAlmostEqual(improved.fun, 12)
        impossible = solve_binary_neighborhood(k=0, **kwargs)
        self.assertEqual(impossible.status, 2)


if __name__ == "__main__":
    unittest.main()
