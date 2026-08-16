"""Exports tipo "Ponderación por métrica" de BeSoccer Pro.

Esa vista devuelve valores YA normalizados por 90, sin minutos, sin edad y
sin demarcación. El motor tiene que digerirlo sin romperse y —sobre todo—
sin fingir que puede calcular lo que no puede.
"""

import numpy as np
import pandas as pd
import pytest

from besoccer_pro import columns as cols
from besoccer_pro import ingest, metrics, scoring
from besoccer_pro.leagues import LeagueStrength

STRENGTH = LeagueStrength({"primera federacion": 0.62}, default=0.62)

CABECERAS = [
    "Jugador", "Equipo", "Rating(1-5)", "Goles", "Primeros goles", "Asistencias",
    "Tiros a puerta", "% Efectividad", "Toques en el área", "Pases clave",
    "Pases al último tercio con éxito", "Recuperaciones en últ. tercio",
    "Duelos aéreos ganados",
]


@pytest.fixture
def export(tmp_path):
    """Réplica de la forma real del export: 20 filas, valores ya por-90."""
    rng = np.random.default_rng(11)
    n = 20
    frame = pd.DataFrame({
        "Jugador": [f"Jugador {i}" for i in range(n)],
        "Equipo": [f"Club {i % 5}" for i in range(n)],
        "Rating(1-5)": np.linspace(2.6, 0.7, n),
        "Goles": np.linspace(0.6, 0.0, n),
        "Primeros goles": np.linspace(0.24, 0.0, n),
        "Asistencias": rng.uniform(0, 0.25, n).round(2),
        "Tiros a puerta": np.linspace(1.6, 0.0, n),
        "% Efectividad": rng.uniform(18, 67, n).round(2),
        "Toques en el área": np.linspace(4.0, 0.0, n),
        "Pases clave": rng.uniform(0, 0.9, n).round(2),
        "Pases al último tercio con éxito": rng.uniform(0.3, 7.3, n).round(2),
        "Recuperaciones en últ. tercio": rng.uniform(0, 1.0, n).round(2),
        "Duelos aéreos ganados": rng.uniform(0.1, 6.2, n).round(2),
    })
    path = tmp_path / "ranking_general.xlsx"
    frame.to_excel(path, index=False)
    return path


def test_all_columns_of_this_view_are_recognised():
    mapping, unknown = cols.map_headers(CABECERAS)
    assert unknown == [], f"sin mapear: {unknown}"
    assert mapping["Rating(1-5)"] == "besoccer_index"
    assert mapping["Primeros goles"] == "opening_goals"
    assert mapping["Pases al último tercio con éxito"] == "passes_final_third"
    assert mapping["Recuperaciones en últ. tercio"] == "recoveries_final_third"
    assert mapping["% Efectividad"] == "conversion_pct"


def test_loads_without_minutes_position_or_age(export):
    data, report = ingest.load([str(export)], default_position="ST",
                               default_league="Primera Federación")
    assert len(data) == 20
    assert report["has_minutes"] is False
    assert report["has_age"] is False
    assert report["assumed_position"] == {"group": "ST", "rows": 20}


def test_values_are_not_divided_again(export):
    """El fallo grave a evitar: volver a normalizar un dato ya por-90."""
    data, _ = ingest.load([str(export)], default_position="ST")
    assert data["goals_p90"].max() == pytest.approx(0.6)
    assert data["goals_p90"].equals(data["goals"])


def test_ranking_still_works_and_respects_production(export):
    data, _ = ingest.load([str(export)], default_position="ST",
                          default_league="Primera Federación")
    scored = scoring.score_players(data, STRENGTH)
    assert scored["perf_score"].notna().all()
    top = scoring.rank(scored, by="perf_score", top=5)
    assert len(top) == 5
    # El maximo goleador del pool debe estar arriba del ranking.
    mejor_goleador = data.loc[data["goals_p90"].idxmax(), "player"]
    assert mejor_goleador in top["player"].tolist()


def test_reliability_is_blank_not_zero(export):
    """Fiabilidad vacia = "no medido". Un 0 diria "muestra pesima", que es falso."""
    data, _ = ingest.load([str(export)], default_position="ST")
    scored = scoring.score_players(data, STRENGTH)
    assert scored["reliability"].isna().all()


def test_scores_are_not_flattened_when_minutes_are_missing(export):
    """Sin minutos NO se contrae: contraer con fiabilidad 0 aplanaria todo a 50."""
    data, _ = ingest.load([str(export)], default_position="ST")
    scored = scoring.score_players(data, STRENGTH)
    assert scored["perf_score"].std() > 5
    assert scored["perf_score"].equals(scored["rate_score"])


def test_potential_is_blank_without_age(export):
    """Lo importante: sin edad NO se inventa un techo."""
    data, _ = ingest.load([str(export)], default_position="ST")
    scored = scoring.score_players(data, STRENGTH)
    assert scored["potential_score"].isna().all()
    assert scored["breakout_index"].isna().all()
    # Y por tanto la lista de irrupcion sale vacia en vez de enganosa.
    assert scoring.breakouts(scored, min_potential=0, min_minutes=0).empty


def test_potential_appears_as_soon_as_age_is_added(export):
    """Anadir la columna de edad desbloquea el calculo entero."""
    data, _ = ingest.load([str(export)], default_position="ST")
    data["age"] = [19 + (i % 12) for i in range(len(data))]
    scored = scoring.score_players(data, STRENGTH)
    assert scored["potential_score"].notna().all()
    jovenes = scored[scored["age"] <= 21]
    veteranos = scored[scored["age"] >= 29]
    # A igualdad de rendimiento, el joven proyecta mas techo que el veterano.
    assert (jovenes["potential_score"] - jovenes["perf_score"]).mean() > (
        veteranos["potential_score"] - veteranos["perf_score"]).mean()


def test_assumed_position_must_be_a_real_group(export):
    with pytest.raises(ValueError, match="no reconocida"):
        ingest.load([str(export)], default_position="XQZ")


def test_besoccer_rating_survives_to_the_report(export):
    data, _ = ingest.load([str(export)], default_position="ST")
    scored = scoring.score_players(data, STRENGTH)
    assert scored["besoccer_index"].notna().all()
    # Pero sigue sin entrar en el calculo.
    alterado = data.copy()
    alterado["besoccer_index"] = 1.0
    assert scoring.score_players(alterado, STRENGTH)["perf_score"].equals(
        scored["perf_score"])
