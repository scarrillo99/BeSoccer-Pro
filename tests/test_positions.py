import pytest

from besoccer_pro.positions import POSITION_GROUPS, POSITION_WEIGHTS, normalize_position


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("POR", "GK"), ("Portero", "GK"), ("goalkeeper", "GK"), ("Arquero", "GK"),
        ("DC", "CB"), ("Central", "CB"), ("centre-back", "CB"),
        ("Lateral derecho", "FB"), ("LB", "FB"), ("carrilero", "FB"),
        ("Pivote", "DM"), ("MCD", "DM"),
        ("MC", "CM"), ("Mediocentro", "CM"), ("interior", "CM"),
        ("Mediapunta", "AM"), ("enganche", "AM"),
        ("Extremo izquierdo", "W"), ("RW", "W"), ("winger", "W"),
        ("Delantero centro", "ST"), ("striker", "ST"),
    ],
)
def test_recognises_common_position_labels(raw, expected):
    assert normalize_position(raw) == expected


def test_multiposition_takes_the_first_listed():
    assert normalize_position("MC, MCO") == "CM"
    assert normalize_position("RW/LW") == "W"


def test_unknown_position_returns_none_rather_than_a_wrong_group():
    assert normalize_position("Utility") is None
    assert normalize_position("") is None
    assert normalize_position(None) is None


def test_every_group_has_weights():
    for group in POSITION_GROUPS:
        assert POSITION_WEIGHTS[group], f"faltan pesos para {group}"


def test_attacking_weights_favour_attacking_metrics():
    # Un delantero debe puntuar sobre todo por gol y xG.
    striker = POSITION_WEIGHTS["ST"]
    assert striker["xg_p90"] + striker["goals_p90"] > 0.3
    # Un central no debe puntuar por gol de forma significativa.
    assert POSITION_WEIGHTS["CB"].get("goals_p90", 0) < 0.05


def test_negative_weights_are_only_on_harmful_metrics():
    harmful = {"goals_conceded_p90", "errors_leading_to_shot_p90", "fouls_p90"}
    for group, weights in POSITION_WEIGHTS.items():
        for metric, weight in weights.items():
            if weight < 0:
                assert metric in harmful, f"{group}/{metric} no deberia ser negativa"
