"""Destacar sobre el propio equipo.

Un jugador en un equipo de zona baja está penalizado por el contexto: peores
pases recibidos, menos ataque, más defensa. Compararlo con SUS compañeros
aísla lo que aporta él del ruido del equipo.
"""

import numpy as np
import pandas as pd
import pytest

from besoccer_pro import scoring
from besoccer_pro.leagues import LeagueStrength

STRENGTH = LeagueStrength.load()


def squad(team, produccion, n=12, age=21):
    return pd.DataFrame({
        "player": [f"{team}_{i}" for i in range(n)],
        "position_group": ["ST"] * n,
        "league": ["Primera Federación"] * n,
        "team": [team] * n,
        "minutes": [2000] * n,
        "age": [age] * n,
        "goals_p90": produccion,
        "xg_p90": produccion,
    })


@pytest.fixture
def dos_equipos():
    bueno = squad("Bueno", np.linspace(0.40, 0.85, 12))
    flojo = squad("Flojo", np.linspace(0.02, 0.30, 12))
    # Una estrella aislada en el equipo flojo: produce como los del bueno.
    flojo.loc[11, ["goals_p90", "xg_p90"]] = 0.80
    flojo.loc[11, "player"] = "Estrella Aislada"
    return pd.concat([bueno, flojo], ignore_index=True)


def test_standout_compares_against_own_teammates(dos_equipos):
    s = scoring.score_players(dos_equipos, STRENGTH)
    estrella = s[s["player"] == "Estrella Aislada"].iloc[0]
    mejor_del_bueno = s[s["team"] == "Bueno"].nlargest(1, "perf_score").iloc[0]
    # Produce parecido, pero destaca mucho más sobre los suyos.
    assert estrella["standout_index"] > mejor_del_bueno["standout_index"]


def test_team_score_excludes_the_player_himself(dos_equipos):
    """Leave-one-out: incluirse diluye la señal, y más en plantillas cortas."""
    s = scoring.score_players(dos_equipos, STRENGTH)
    fila = s[s["player"] == "Estrella Aislada"].iloc[0]
    companeros = s[(s["team"] == "Flojo") & (s["player"] != "Estrella Aislada")]
    assert fila["team_score"] == pytest.approx(companeros["perf_score"].mean(), abs=0.1)
    assert fila["team_score"] < s[s["team"] == "Flojo"]["perf_score"].mean()


def test_standout_is_zero_on_average_within_a_team(dos_equipos):
    s = scoring.score_players(dos_equipos, STRENGTH)
    for _, grupo in s.groupby("team"):
        assert grupo["standout_index"].mean() == pytest.approx(0, abs=1.5)


def test_single_player_team_has_no_comparison(dos_equipos):
    solo = squad("Solo", [0.5], n=1)
    s = scoring.score_players(pd.concat([dos_equipos, solo], ignore_index=True), STRENGTH)
    fila = s[s["team"] == "Solo"].iloc[0]
    assert pd.isna(fila["standout_index"])


def test_min_standout_filter(dos_equipos):
    s = scoring.score_players(dos_equipos, STRENGTH)
    r = scoring.rank(s, min_standout=10, top=100)
    assert (r["standout_index"] >= 10).all()
    assert "Estrella Aislada" in r["player"].tolist()


def test_squad_size_is_reported(dos_equipos):
    """Con plantillas cortas en el export, la media de compañeros es frágil."""
    s = scoring.score_players(dos_equipos, STRENGTH)
    assert (s[s["team"] == "Bueno"]["squad_sampled"] == 12).all()


def test_works_without_team_column(dos_equipos):
    s = scoring.score_players(dos_equipos.drop(columns=["team"]), STRENGTH)
    assert s["standout_index"].isna().all()
