"""Divisiones territoriales (1a y 2a RFEF) y equipos filiales.

En estas categorias el grupo importa tanto como la division: comparar a un
jugador del Grupo 1 contra uno del Grupo 5 como si fuera la misma competicion
falsea el percentil, que es la base de todo el modelo.
"""

import numpy as np
import pandas as pd
import pytest

from besoccer_pro import columns as cols
from besoccer_pro import metrics, scoring
from besoccer_pro.leagues import LeagueStrength

RFEF = LeagueStrength.load()


def squad(group, n, floor, ceiling, league="Segunda Federación", team="Club"):
    """Grupo con produccion entre `floor` y `ceiling` goles/90."""
    return pd.DataFrame({
        "player": [f"{group}_{i}" for i in range(n)],
        "position_group": ["ST"] * n,
        "league": [league] * n,
        "group": [group] * n,
        "team": [team] * n,
        "minutes": [2000] * n,
        "age": [21] * n,
        "goals_p90": np.linspace(floor, ceiling, n),
        "xg_p90": np.linspace(floor, ceiling, n),
        "shots_on_target_p90": np.linspace(floor, ceiling, n) * 2,
    })


def test_group_column_is_recognised():
    mapping, unknown = cols.map_headers(["Jugador", "Liga", "Grupo"])
    assert mapping["Grupo"] == "group"
    assert unknown == []


def test_players_are_compared_within_their_group_not_the_whole_division():
    # Grupo flojo (0.1-0.4 g/90) y grupo fuerte (0.5-0.9 g/90).
    pool = pd.concat([squad("Grupo 1", 12, 0.1, 0.4),
                      squad("Grupo 5", 12, 0.5, 0.9)], ignore_index=True)
    scored = scoring.score_players(pool, RFEF)

    assert (scored["pool_type"] == "liga+grupo+posicion").all()

    # El mejor de cada grupo es percentil alto EN SU GRUPO, aunque en cifras
    # absolutas el del grupo flojo marque la mitad.
    best_weak = scored[scored["player"] == "Grupo 1_11"].iloc[0]
    best_strong = scored[scored["player"] == "Grupo 5_11"].iloc[0]
    assert best_weak["rate_score"] == pytest.approx(best_strong["rate_score"])


def test_without_group_column_the_division_is_pooled_as_one():
    pool = pd.concat([squad("Grupo 1", 12, 0.1, 0.4),
                      squad("Grupo 5", 12, 0.5, 0.9)], ignore_index=True)
    scored = scoring.score_players(pool.drop(columns=["group"]), RFEF)
    assert (scored["pool_type"] == "liga+posicion").all()
    # Sin grupo, el mejor del grupo flojo queda por debajo del mejor del fuerte.
    best_weak = scored[scored["player"] == "Grupo 1_11"].iloc[0]
    best_strong = scored[scored["player"] == "Grupo 5_11"].iloc[0]
    assert best_weak["rate_score"] < best_strong["rate_score"]


def test_rfef_divisions_have_coefficients_configured():
    for name in ("Primera Federación", "1a RFEF", "Segunda Federación", "2a RFEF"):
        assert name in RFEF, f"falta coeficiente para {name}"
    assert RFEF.coefficient("Primera Federación") > RFEF.coefficient("Segunda Federación")


def test_rfef_level_scores_stay_below_top_flight_equivalents():
    """Un percentil 95 en 2a RFEF no puede puntuar como un percentil 95 en LaLiga."""
    rfef = scoring.score_players(squad("Grupo 3", 20, 0.1, 0.9), RFEF)
    top = scoring.score_players(
        squad("-", 20, 0.1, 0.9, league="La Liga"), RFEF)
    assert rfef.iloc[-1]["perf_score"] < top.iloc[-1]["perf_score"]


# --- filiales --------------------------------------------------------------

@pytest.mark.parametrize("team", [
    "Real Madrid Castilla", "Barça Atlètic", "Bilbao Athletic",
    "Villarreal B", "Sevilla Atlético B", "Racing II", "Filial del Betis",
])
def test_reserve_teams_are_flagged(team):
    out = metrics.add_team_flags(pd.DataFrame({"team": [team]}))
    assert out["is_reserve_team"].iloc[0], f"no detectado: {team}"


@pytest.mark.parametrize("team", [
    "Cultural Leonesa", "Racing de Ferrol", "Algeciras CF", "Unionistas",
    "Atlético de Madrid", "Athletic Club", "Club Atlético Osasuna",
])
def test_senior_clubs_are_not_flagged_as_reserves(team):
    out = metrics.add_team_flags(pd.DataFrame({"team": [team]}))
    assert not out["is_reserve_team"].iloc[0], f"falso positivo: {team}"


def test_reserve_filter_splits_the_pool():
    pool = pd.concat([
        squad("Grupo 1", 10, 0.2, 0.8, team="Villarreal B"),
        squad("Grupo 2", 10, 0.2, 0.8, team="Algeciras CF"),
    ], ignore_index=True)
    scored = scoring.score_players(metrics.add_team_flags(pool), RFEF)

    only = scoring.rank(scored, reserves="only", top=50)
    without = scoring.rank(scored, reserves="exclude", top=50)
    assert len(only) == 10 and len(without) == 10
    assert only["team"].unique().tolist() == ["Villarreal B"]
    assert without["team"].unique().tolist() == ["Algeciras CF"]


def test_default_potential_threshold_is_too_high_for_the_fourth_tier():
    """Documenta por que hay que bajar --min-potential en 2a RFEF.

    Con coeficiente 0.52, el umbral por defecto de 60 —pensado para ligas
    top— deja fuera a casi toda la categoria: solo sobrevive la punta
    absoluta del grupo. Bajarlo a 40 devuelve una lista trabajable.
    """
    pool = squad("Grupo 3", 20, 0.1, 0.9)
    pool["age"] = 21
    scored = scoring.score_players(pool, RFEF)

    con_defecto = scoring.breakouts(scored, max_age=23, min_minutes=600,
                                    min_potential=60, top=100)
    realista = scoring.breakouts(scored, max_age=23, min_minutes=600,
                                 min_potential=40, top=100)

    assert len(con_defecto) <= 0.20 * len(pool)
    assert len(realista) >= 3 * max(len(con_defecto), 1)
