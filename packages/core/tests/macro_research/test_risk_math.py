"""Baked reference parameters + covariance/correlation helpers."""

import numpy as np
from openlia.macro_research.risk_math import (
    ASSET_ORDER,
    CORRELATIONS,
    DEFAULT_VOLS,
    EXPECTED_RETURNS,
    correlation_matrix,
    covariance_matrix,
)


def test_asset_order_is_the_five_classes() -> None:
    assert ASSET_ORDER == (
        "equities",
        "long_bonds",
        "intermediate_bonds",
        "gold",
        "commodities",
    )


def test_baked_params_cover_every_asset() -> None:
    for asset in ASSET_ORDER:
        assert asset in EXPECTED_RETURNS
        assert asset in DEFAULT_VOLS


def test_correlation_matrix_is_symmetric_unit_diagonal() -> None:
    corr = correlation_matrix(CORRELATIONS)
    assert corr.shape == (5, 5)
    assert np.allclose(np.diag(corr), 1.0)
    assert np.allclose(corr, corr.T)


def test_correlation_matrix_is_positive_semidefinite() -> None:
    # Empirical correlations (computed from daily log returns) form a valid (PSD)
    # matrix so the Gaussian simulator can draw from it.
    corr = correlation_matrix(CORRELATIONS)
    eigenvalues = np.linalg.eigvalsh(corr)
    assert eigenvalues.min() >= -1e-8


def test_covariance_matrix_diagonal_is_variance() -> None:
    cov = covariance_matrix(vols=DEFAULT_VOLS, correlations=CORRELATIONS)
    for i, asset in enumerate(ASSET_ORDER):
        assert np.isclose(cov[i, i], DEFAULT_VOLS[asset] ** 2)
    assert np.allclose(cov, cov.T)
