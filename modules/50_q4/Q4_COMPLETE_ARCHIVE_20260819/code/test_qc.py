import numpy as np

import q4_qcert as qc


def test_dual_correction_is_valid_and_pessimistic():
    rho = np.asarray([-3.0, 2.0, -0.5, 0.0])
    guard = 1e-7
    shift = np.minimum(0.0, rho - guard)
    corrected = rho - shift
    assert np.min(corrected) >= -1e-12
    assert np.sum(shift) < -3.5


def test_default_paths_are_separate_from_old_results():
    assert qc.DEF_OUT != qc.DEF_ROOT
    assert qc.DEF_OUT.name == "renew_down_80_quick_certificate"
