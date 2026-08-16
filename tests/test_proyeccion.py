"""Proyección a una categoría objetivo: ¿puede este jugador jugar en Segunda?"""

import numpy as np
import pandas as pd
import pytest

from besoccer_pro import scoring
from besoccer_pro.leagues import LeagueStrength

STRENGTH = LeagueStrength.load()
SEGUNDA = "Segunda División"


def pool(n=30, league="Primera Federación", age=21, minutes=2200, floor=0.05, top=0.9):
    return pd.DataFrame({
        "player": [f"J{i}" for i in range(n)],
        "position_group": ["ST"] * n,
        "league": [league] * n,
        "team": [f"C{i}" for i in range(n)],
        "minutes": [minutes] * n,
        "age": [age] * n,
        "goals_p90": np.linspace(floor, top, n),
        "xg_p90": np.linspace(floor, top, n),
        "shots_on_target_p90": np.linspace(floor, top, n) * 2,
        "touches_box_p90": np.linspace(1, 6, n),
    })


# --- el listón -------------------------------------------------------------

def test_bar_is_percentile_times_league_coefficient():
    coef = STRENGTH.coefficient(SEGUNDA)
    assert scoring.target_level(STRENGTH, SEGUNDA, 50) == pytest.approx(50 * coef)
    assert scoring.target_level(STRENGTH, SEGUNDA, 65) == pytest.approx(65 * coef)


def test_higher_role_means_higher_bar():
    rotacion = scoring.target_level(STRENGTH, SEGUNDA, 50)
    titular = scoring.target_level(STRENGTH, SEGUNDA, 65)
    top = scoring.target_level(STRENGTH, SEGUNDA, 85)
    assert rotacion < titular < top


def test_stronger_target_league_raises_the_bar():
    assert (scoring.target_level(STRENGTH, "La Liga", 50)
            > scoring.target_level(STRENGTH, SEGUNDA, 50)
            > scoring.target_level(STRENGTH, "Primera Federación", 50))


def test_invalid_percentile_is_rejected():
    for bad in (0, -5, 140):
        with pytest.raises(ValueError, match="percentil"):
            scoring.target_level(STRENGTH, SEGUNDA, bad)


# --- la proyeccion ---------------------------------------------------------

def test_only_players_clearing_the_bar_are_returned():
    scored = scoring.score_players(pool(), STRENGTH)
    result = scoring.project(scored, STRENGTH, SEGUNDA, 50, max_age=25, top=100)
    bar = scoring.target_level(STRENGTH, SEGUNDA, 50)
    assert (result["potential_score"] >= bar).all()
    assert (result["projection_margin"] >= 0).all()


def test_ordered_by_margin_over_the_bar():
    scored = scoring.score_players(pool(), STRENGTH)
    result = scoring.project(scored, STRENGTH, SEGUNDA, 50, top=100)
    assert result["projection_margin"].is_monotonic_decreasing


def test_ready_now_separates_arrived_from_projected():
    scored = scoring.score_players(pool(), STRENGTH)
    result = scoring.project(scored, STRENGTH, SEGUNDA, 50, top=100)
    bar = scoring.target_level(STRENGTH, SEGUNDA, 50)
    # ready_now mira el nivel ACTUAL, no el techo.
    assert (result[result["ready_now"]]["perf_score"] >= bar).all()
    assert (result[~result["ready_now"]]["perf_score"] < bar).all()


def test_only_projects_excludes_those_already_at_that_level():
    scored = scoring.score_players(pool(), STRENGTH)
    todos = scoring.project(scored, STRENGTH, SEGUNDA, 50, top=100)
    proyectos = scoring.project(scored, STRENGTH, SEGUNDA, 50,
                                include_ready=False, top=100)
    assert not proyectos["ready_now"].any()
    assert len(proyectos) < len(todos)


def test_age_ceiling_is_applied():
    mixto = pd.concat([pool(15, age=21), pool(15, age=29)], ignore_index=True)
    mixto["player"] = [f"P{i}" for i in range(30)]
    scored = scoring.score_players(mixto, STRENGTH)
    result = scoring.project(scored, STRENGTH, SEGUNDA, 50, max_age=25, top=100)
    assert (result["age"] <= 25).all()


def test_thin_samples_are_excluded_by_default():
    """Proyectar desde 300 minutos es el error clasico: se filtra por defecto."""
    scored = scoring.score_players(pool(minutes=300), STRENGTH)
    assert scoring.project(scored, STRENGTH, SEGUNDA, 50, top=100).empty
    # Bajando el listón de fiabilidad a mano sí aparecen.
    assert not scoring.project(scored, STRENGTH, SEGUNDA, 50,
                               min_reliability=None, top=100).empty


def test_projection_needs_age_and_says_so():
    sin_edad = pool().drop(columns=["age"])
    scored = scoring.score_players(sin_edad, STRENGTH)
    with pytest.raises(ValueError, match="edad"):
        scoring.project(scored, STRENGTH, SEGUNDA, 50)


# --- comportamiento por edad ----------------------------------------------

def test_at_25_the_list_is_mostly_players_who_already_arrived():
    """A los 25 apenas queda recorrido: el techo es casi el nivel actual.

    Consecuencia práctica: filtrar hasta 25 años devuelve sobre todo fichajes
    'listos ya', no proyectos. Los proyectos de verdad están en 19-22.
    """
    veteranos = scoring.score_players(pool(30, age=25), STRENGTH)
    jovenes = scoring.score_players(pool(30, age=20), STRENGTH)

    salto_25 = (veteranos["potential_score"] - veteranos["perf_score"]).mean()
    salto_20 = (jovenes["potential_score"] - jovenes["perf_score"]).mean()
    assert salto_20 > 2 * salto_25

    # Y a igualdad de rendimiento, pasan mas jovenes que veteranos el listón.
    assert (len(scoring.project(jovenes, STRENGTH, SEGUNDA, 50, top=100))
            > len(scoring.project(veteranos, STRENGTH, SEGUNDA, 50, top=100)))


def test_a_dominant_third_tier_player_projects_to_second_division():
    """Comprobacion de sensatez: el mejor de 1a RFEF con 21 anos debe proyectar."""
    scored = scoring.score_players(pool(30, age=21), STRENGTH)
    mejor = scored.iloc[-1]
    bar = scoring.target_level(STRENGTH, SEGUNDA, 50)
    assert mejor["potential_score"] > bar


def test_a_mediocre_fourth_tier_player_does_not():
    scored = scoring.score_players(
        pool(30, league="Segunda Federación", age=24), STRENGTH)
    mediano = scored.iloc[len(scored) // 2]
    bar = scoring.target_level(STRENGTH, SEGUNDA, 65)
    assert mediano["potential_score"] < bar
