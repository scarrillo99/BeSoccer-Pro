"""Umbrales numéricos por demarcación sacados del propio pool."""

import numpy as np
import pandas as pd
import pytest

from besoccer_pro import reports, scoring
from besoccer_pro.leagues import LeagueStrength


@pytest.fixture
def pool():
    n = 30
    df = pd.DataFrame({
        "player": [f"J{i}" for i in range(n)],
        "position_group": ["W"] * n,
        "league": ["Primera Federación"] * n,
        "team": [f"C{i % 6}" for i in range(n)],
        "minutes": [2000] * n,
        "age": [22] * n,
        "dribbles_completed_p90": np.linspace(0.2, 3.0, n),
        "goals_p90": np.linspace(0.0, 0.4, n),
        "key_passes_p90": np.linspace(0.2, 2.0, n),
    })
    return scoring.score_players(df, LeagueStrength.load())


def test_reports_real_percentiles_from_the_pool(pool):
    out = reports.benchmarks(pool, "W")
    assert "Extremo" in out and "n = 30" in out
    # p50 de dribbles debe coincidir con la mediana real.
    mediana = pool["dribbles_completed_p90"].median()
    assert f"{mediana:.2f}" in out


def test_metrics_are_ordered_by_weight(pool):
    out = reports.benchmarks(pool, "W")
    # El regate pesa mas que el pase clave en un extremo.
    assert out.index("dribbles_completed_p90") < out.index("key_passes_p90")


def test_only_shows_metrics_present_in_the_data(pool):
    out = reports.benchmarks(pool, "W")
    assert "crosses_completed_p90" not in out


def test_refuses_on_a_sample_too_small_to_mean_anything(pool):
    assert "insuficiente" in reports.benchmarks(pool.head(4), "W")


def test_unknown_position_is_rejected(pool):
    assert "no reconocida" in reports.benchmarks(pool, "XX")
