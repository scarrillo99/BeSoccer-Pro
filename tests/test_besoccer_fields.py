"""Campos propios de BeSoccer Pro: indices, salario y contrato."""

import numpy as np
import pandas as pd
import pytest

from besoccer_pro import columns as cols
from besoccer_pro import metrics, scoring
from besoccer_pro.leagues import LeagueStrength

STRENGTH = LeagueStrength({"liga fuerte": 1.0}, default=0.7)


def test_proprietary_indices_are_recognised():
    mapping, unknown = cols.map_headers(
        ["Índice de rendimiento", "Elo", "REAP", "Estimación salarial",
         "Valor de mercado", "Días lesionado", "Contrato hasta"]
    )
    assert mapping["Índice de rendimiento"] == "besoccer_index"
    assert mapping["Elo"] == "elo"
    assert mapping["REAP"] == "reap"
    assert mapping["Estimación salarial"] == "salary"
    assert mapping["Valor de mercado"] == "market_value"
    assert mapping["Días lesionado"] == "injury_days"
    assert mapping["Contrato hasta"] == "contract_until"
    assert unknown == []


def test_proprietary_indices_are_coerced_to_numbers():
    df = pd.DataFrame({"besoccer_index": ["78,5"], "salary": ["1.2M"], "elo": ["1650"]})
    out = metrics.coerce_numeric(df)
    assert out["besoccer_index"].iloc[0] == pytest.approx(78.5)
    assert out["salary"].iloc[0] == pytest.approx(1_200_000)
    assert out["elo"].iloc[0] == pytest.approx(1650)


# --- contrato --------------------------------------------------------------

def test_contract_year_only_is_read_as_end_of_season():
    df = pd.DataFrame({"contract_until": ["2027"]})
    out = metrics.add_contract_years(df, today=pd.Timestamp("2026-06-30"))
    assert out["contract_until_date"].iloc[0] == pd.Timestamp("2027-06-30")
    assert out["contract_years_left"].iloc[0] == pytest.approx(1.0, abs=0.02)


def test_contract_accepts_european_and_iso_dates():
    df = pd.DataFrame({"contract_until": ["30/06/2028", "2028-06-30"]})
    out = metrics.add_contract_years(df, today=pd.Timestamp("2026-06-30"))
    assert out["contract_until_date"].nunique() == 1
    assert (out["contract_years_left"] > 1.9).all()


def test_unparseable_contract_becomes_nan_not_an_error():
    df = pd.DataFrame({"contract_until": ["sin datos", ""]})
    out = metrics.add_contract_years(df)
    assert out["contract_years_left"].isna().all()


def test_rank_filters_by_remaining_contract():
    pool = pd.DataFrame({
        "player": [f"J{i}" for i in range(10)],
        "position_group": ["ST"] * 10,
        "league": ["liga fuerte"] * 10,
        "minutes": [2000] * 10,
        "age": [24] * 10,
        "goals_p90": np.linspace(0.2, 0.8, 10),
        "xg_p90": np.linspace(0.2, 0.8, 10),
        "contract_until": ["2027"] * 5 + ["2030"] * 5,
    })
    prepared = metrics.add_contract_years(pool, today=pd.Timestamp("2026-06-30"))
    scored = scoring.score_players(prepared, STRENGTH)
    expiring = scoring.rank(scored, max_contract_years=1.5, top=50)
    assert len(expiring) == 5
    assert (expiring["contract_years_left"] <= 1.5).all()


def test_contract_filter_without_the_column_fails_clearly():
    pool = pd.DataFrame({
        "player": ["A"], "position_group": ["ST"], "league": ["liga fuerte"],
        "minutes": [2000], "age": [24], "goals_p90": [0.5],
    })
    scored = scoring.score_players(pool, STRENGTH)
    with pytest.raises(ValueError, match="contrato"):
        scoring.rank(scored, max_contract_years=1)


# --- salario en el escaparate ---------------------------------------------

def _pool_with(field, values):
    n = len(values)
    return pd.DataFrame({
        "player": [f"J{i}" for i in range(n)],
        "position_group": ["ST"] * n,
        "league": ["liga fuerte"] * n,
        "minutes": [2000] * n,
        "age": [24] * n,
        "goals_p90": [0.5] * n,
        "xg_p90": [0.5] * n,
        field: values,
    })


def test_salary_feeds_the_visibility_score():
    salaries = list(np.linspace(50_000, 5_000_000, 20))
    scored = scoring.score_players(_pool_with("salary", salaries), STRENGTH)
    assert "salario" in scored["visibility_basis"].iloc[0]
    # Mismo rendimiento y minutos: el que mas cobra tiene mas escaparate.
    assert scored.iloc[-1]["visibility_score"] > scored.iloc[0]["visibility_score"]
    # Y por tanto menos margen de irrupcion.
    assert scored.iloc[-1]["breakout_index"] < scored.iloc[0]["breakout_index"]


def test_salary_and_market_value_are_blended_when_both_present():
    pool = _pool_with("salary", list(np.linspace(50_000, 5_000_000, 20)))
    pool["market_value"] = list(np.linspace(100_000, 40_000_000, 20))
    scored = scoring.score_players(pool, STRENGTH)
    assert scored["visibility_basis"].iloc[0] == "minutos+liga+salario+valor"


def test_sparse_market_data_is_ignored_rather_than_trusted():
    pool = _pool_with("salary", [np.nan] * 18 + [1_000_000, 2_000_000])
    scored = scoring.score_players(pool, STRENGTH)
    assert scored["visibility_basis"].iloc[0] == "minutos+liga"


def test_besoccer_index_is_not_used_in_the_model():
    """Su indice se arrastra a los informes, pero no entra en el calculo.

    Meterlo seria circular: es un composite de las mismas metricas, y el valor
    del sistema esta en poder contrastar ambos criterios por separado.
    """
    base = _pool_with("besoccer_index", [50.0] * 20)
    inflated = base.copy()
    inflated["besoccer_index"] = np.linspace(10, 99, 20)

    scored_base = scoring.score_players(base, STRENGTH)
    scored_inflated = scoring.score_players(inflated, STRENGTH)

    assert scored_base["perf_score"].equals(scored_inflated["perf_score"])
    assert scored_base["potential_score"].equals(scored_inflated["potential_score"])
    # Pero la columna sobrevive para poder compararla en el informe.
    assert "besoccer_index" in scored_inflated.columns
