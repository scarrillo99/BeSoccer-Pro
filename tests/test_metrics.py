import numpy as np
import pandas as pd
import pytest

from besoccer_pro import metrics


def test_parses_export_number_formats():
    series = pd.Series(["85%", "1.234,5", "1,234.5", "€2.5M", "800K", "-", "", None])
    parsed = metrics._to_number(series)
    assert parsed[0] == 85
    assert parsed[1] == pytest.approx(1234.5)   # formato ES
    assert parsed[2] == pytest.approx(1234.5)   # formato EN
    assert parsed[3] == pytest.approx(2_500_000)
    assert parsed[4] == pytest.approx(800_000)
    assert parsed[5:].isna().all()


def test_per90_uses_minutes_and_leaves_ratios_alone():
    df = pd.DataFrame({
        "minutes": [900.0, 1800.0],
        "goals": [5.0, 5.0],
        "pass_accuracy": [80.0, 90.0],
    })
    out = metrics.add_per90(df)
    assert out["goals_p90"].tolist() == [0.5, 0.25]
    assert "pass_accuracy_p90" not in out.columns


def test_per90_is_nan_for_players_without_minutes():
    df = pd.DataFrame({"minutes": [0.0, np.nan], "goals": [3.0, 3.0]})
    out = metrics.add_per90(df)
    assert out["goals_p90"].isna().all()


def test_without_minutes_values_are_taken_as_already_per90():
    """Varias vistas de BeSoccer Pro exportan ya normalizado por 90.

    Sin minutos no se puede dividir, asi que se asume que el dato ya viene
    por-90 y se copia tal cual. La perdida (no poder medir la muestra) la
    avisa la CLI; aqui solo se comprueba que no se rompe ni se inventa.
    """
    out = metrics.add_per90(pd.DataFrame({"goals": [0.47, 0.35]}))
    assert out["goals_p90"].tolist() == [0.47, 0.35]
    assert not metrics.has_minutes(out)


def test_per90_mode_can_be_forced_either_way():
    df = pd.DataFrame({"minutes": [900.0], "goals": [5.0]})
    assert metrics.add_per90(df, assume_per90=True)["goals_p90"].iloc[0] == 5.0
    assert metrics.add_per90(df, assume_per90=False)["goals_p90"].iloc[0] == 0.5


def test_derives_ratios_that_the_export_omits():
    df = pd.DataFrame({
        "passes": [100.0], "passes_completed": [85.0],
        "duels_attempted": [50.0], "duels_won": [30.0],
    })
    out = metrics.add_derived(df)
    assert out["pass_accuracy"].iloc[0] == pytest.approx(85.0)
    assert out["duels_won_pct"].iloc[0] == pytest.approx(60.0)


def test_goalkeeper_save_pct_uses_shots_faced():
    df = pd.DataFrame({"saves": [80.0], "goals_conceded": [20.0]})
    out = metrics.add_derived(df)
    assert out["save_pct"].iloc[0] == pytest.approx(80.0)


def test_ratios_expressed_zero_to_one_are_rescaled():
    df = pd.DataFrame({"pass_accuracy": [0.85, 0.9, 0.78]})
    out = metrics.add_derived(df)
    assert out["pass_accuracy"].max() == pytest.approx(90.0)


def test_age_derived_from_birth_date():
    df = pd.DataFrame({"birth_date": ["2004-01-15"], "minutes": [900.0]})
    out = metrics.derive_age(df, season_end_year=2025)
    assert out["age"].iloc[0] == pytest.approx(21.5, abs=0.2)


def test_available_metrics_renormalises_over_present_columns():
    df = pd.DataFrame({"goals_p90": [0.5], "xg_p90": [0.4]})
    weights = {"goals_p90": 0.2, "xg_p90": 0.2, "ausente_p90": 0.6}
    active = metrics.available_metrics(df, weights)
    assert set(active) == {"goals_p90", "xg_p90"}
    assert sum(active.values()) == pytest.approx(1.0)


def test_available_metrics_ignores_all_nan_columns():
    df = pd.DataFrame({"goals_p90": [0.5], "xg_p90": [np.nan]})
    active = metrics.available_metrics(df, {"goals_p90": 0.5, "xg_p90": 0.5})
    assert set(active) == {"goals_p90"}
