import numpy as np
import pandas as pd
import pytest

from besoccer_pro import scoring
from besoccer_pro.leagues import LeagueStrength

STRENGTH = LeagueStrength({"liga fuerte": 1.0, "liga debil": 0.5}, default=0.7)


def striker_pool(n=20, league="liga fuerte", minutes=2000, age=25):
    """Pool de delanteros donde el jugador i es estrictamente mejor que el i-1."""
    return pd.DataFrame({
        "player": [f"J{i}" for i in range(n)],
        "position_group": ["ST"] * n,
        "league": [league] * n,
        "team": [f"E{i}" for i in range(n)],
        "minutes": [minutes] * n,
        "age": [age] * n,
        "xg_p90": np.linspace(0.1, 0.9, n),
        "goals_p90": np.linspace(0.1, 0.9, n),
        "shots_on_target_p90": np.linspace(0.3, 1.8, n),
        "touches_box_p90": np.linspace(1.0, 8.0, n),
        "duels_won_pct": np.linspace(35, 65, n),
    })


# --- bloques basicos -------------------------------------------------------

def test_age_headroom_decreases_with_age():
    ages = [17, 19, 21, 23, 25, 27, 29, 33]
    values = [scoring.age_headroom(a) for a in ages]
    assert values == sorted(values, reverse=True)
    assert values[0] > 0.9
    assert scoring.age_headroom(33) == 0.0


def test_age_headroom_without_age_assumes_no_growth():
    assert scoring.age_headroom(None) == 0.0
    assert scoring.age_headroom(float("nan")) == 0.0


def test_reliability_half_point_is_900_minutes():
    assert scoring.reliability(900) == pytest.approx(0.5)
    assert scoring.reliability(0) == 0.0
    assert scoring.reliability(3000) > scoring.reliability(1500)


# --- percentiles y composicion --------------------------------------------

def test_better_production_scores_higher_within_the_same_league():
    scored = scoring.score_players(striker_pool(), STRENGTH)
    best = scored.iloc[-1]
    worst = scored.iloc[0]
    assert best["rate_score"] > worst["rate_score"]
    assert best["perf_score"] > worst["perf_score"]


def test_negative_weight_metric_is_inverted():
    # Porteros identicos salvo goles encajados: encajar mas debe puntuar menos.
    n = 12
    pool = pd.DataFrame({
        "player": [f"P{i}" for i in range(n)],
        "position_group": ["GK"] * n,
        "league": ["liga fuerte"] * n,
        "minutes": [2000] * n,
        "age": [26] * n,
        "save_pct": [70.0] * n,
        "goals_conceded_p90": np.linspace(0.5, 2.5, n),
    })
    scored = scoring.score_players(pool, STRENGTH)
    assert scored.iloc[0]["rate_score"] > scored.iloc[-1]["rate_score"]


def test_players_missing_a_metric_are_not_penalised():
    pool = striker_pool(n=12)
    pool.loc[5, "touches_box_p90"] = np.nan
    scored = scoring.score_players(pool, STRENGTH)
    assert scored.loc[5, "rate_score"] > scored.loc[4, "rate_score"]


# --- contraccion por minutos ----------------------------------------------

def test_low_minutes_shrinks_towards_the_mean():
    strong = striker_pool(n=20, minutes=3000)
    scored_full = scoring.score_players(strong, STRENGTH)

    thin = striker_pool(n=20, minutes=200)
    scored_thin = scoring.score_players(thin, STRENGTH)

    # El mejor del pool con muchos minutos conserva casi todo su percentil;
    # con 200 minutos se contrae hacia 50.
    assert scored_full.iloc[-1]["perf_score"] > scored_thin.iloc[-1]["perf_score"]
    assert abs(scored_thin.iloc[-1]["perf_score"] - 50) < 15


def test_rate_score_ignores_minutes_but_perf_score_does_not():
    thin = striker_pool(n=20, minutes=200)
    full = striker_pool(n=20, minutes=3000)
    thin_scored = scoring.score_players(thin, STRENGTH)
    full_scored = scoring.score_players(full, STRENGTH)
    assert thin_scored.iloc[-1]["rate_score"] == pytest.approx(
        full_scored.iloc[-1]["rate_score"]
    )
    assert thin_scored.iloc[-1]["perf_score"] < full_scored.iloc[-1]["perf_score"]


def test_below_min_minutes_is_flagged_not_dropped():
    pool = striker_pool(n=12, minutes=200)
    scored = scoring.score_players(pool, STRENGTH, min_minutes=450)
    assert len(scored) == 12
    assert scored["below_min_minutes"].all()


# --- traduccion entre ligas ------------------------------------------------

def test_same_percentile_scores_higher_in_a_stronger_league():
    strong = scoring.score_players(striker_pool(league="liga fuerte"), STRENGTH)
    weak = scoring.score_players(striker_pool(league="liga debil"), STRENGTH)
    assert strong.iloc[-1]["perf_score"] > weak.iloc[-1]["perf_score"]
    assert weak.iloc[-1]["league_coef"] == 0.5


def test_unknown_league_falls_back_to_default_and_is_reported():
    strength = LeagueStrength({"liga fuerte": 1.0}, default=0.7)
    scored = scoring.score_players(striker_pool(league="Liga Marciana"), strength)
    assert scored["league_coef"].iloc[0] == 0.7
    assert "Liga Marciana" in strength.unmatched


# --- techo e irrupcion -----------------------------------------------------

def test_young_player_has_more_upside_than_identical_veteran():
    pool = pd.concat([
        striker_pool(n=10, age=19).assign(player=[f"joven{i}" for i in range(10)]),
        striker_pool(n=10, age=30).assign(player=[f"veterano{i}" for i in range(10)]),
    ], ignore_index=True)
    scored = scoring.score_players(pool, STRENGTH)
    young = scored[scored["player"] == "joven9"].iloc[0]
    old = scored[scored["player"] == "veterano9"].iloc[0]
    assert young["perf_score"] == pytest.approx(old["perf_score"])
    assert young["potential_score"] > old["potential_score"]


def test_potential_never_below_current_level_nor_above_100():
    scored = scoring.score_players(striker_pool(n=20, age=18), STRENGTH)
    assert (scored["potential_score"] >= scored["perf_score"] - 0.05).all()
    assert (scored["potential_score"] <= 100).all()


def test_breakout_index_favours_high_ceiling_with_low_visibility():
    pool = pd.concat([
        striker_pool(n=10, age=19, minutes=700, league="liga debil"),
        striker_pool(n=10, age=29, minutes=3000, league="liga fuerte"),
    ], ignore_index=True)
    pool["player"] = [f"tapado{i}" for i in range(10)] + [f"consagrado{i}" for i in range(10)]
    scored = scoring.score_players(pool, STRENGTH)
    hidden = scored[scored["player"] == "tapado9"].iloc[0]
    established = scored[scored["player"] == "consagrado9"].iloc[0]
    assert hidden["breakout_index"] > established["breakout_index"]
    assert hidden["visibility_score"] < established["visibility_score"]


def test_efficiency_gap_is_positive_for_high_quality_low_minutes():
    scored = scoring.score_players(striker_pool(n=20, minutes=500), STRENGTH)
    assert scored.iloc[-1]["efficiency_gap"] > 0


# --- muestras pequenas -----------------------------------------------------

def test_small_league_pools_fall_back_to_position_wide_comparison():
    small = striker_pool(n=3, league="liga rara")
    big = striker_pool(n=20, league="liga fuerte")
    big["player"] = [f"grande{i}" for i in range(20)]
    scored = scoring.score_players(pd.concat([small, big], ignore_index=True), STRENGTH)
    tiny = scored[scored["league"] == "liga rara"]
    assert (tiny["pool_type"] == "posicion (muestra corta)").all()
    assert tiny["rate_score"].notna().all()


def test_scoring_requires_position_group():
    with pytest.raises(ValueError, match="position_group"):
        scoring.score_players(pd.DataFrame({"player": ["x"], "minutes": [90]}), STRENGTH)


# --- filtros de listado ----------------------------------------------------

def test_rank_applies_filters_and_ordering():
    pool = pd.concat([
        striker_pool(n=10, age=20), striker_pool(n=10, age=33),
    ], ignore_index=True)
    pool["player"] = [f"a{i}" for i in range(20)]
    scored = scoring.score_players(pool, STRENGTH)
    result = scoring.rank(scored, by="perf_score", max_age=25, top=5)
    assert len(result) == 5
    assert (result["age"] <= 25).all()
    assert result["perf_score"].is_monotonic_decreasing


def test_breakouts_respects_age_and_minutes_filters():
    pool = pd.concat([
        striker_pool(n=12, age=21, minutes=1200),
        striker_pool(n=12, age=31, minutes=1200),
    ], ignore_index=True)
    pool["player"] = [f"b{i}" for i in range(24)]
    scored = scoring.score_players(pool, STRENGTH)
    result = scoring.breakouts(scored, max_age=23, min_minutes=600, min_potential=0)
    assert not result.empty
    assert (result["age"] <= 23).all()
    assert (result["minutes"] >= 600).all()
