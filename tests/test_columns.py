import pandas as pd

from besoccer_pro import columns as cols


def test_maps_spanish_and_english_headers():
    mapping, unknown = cols.map_headers(
        ["Jugador", "Minutos jugados", "Goles", "Precisión pases", "% duelos"]
    )
    assert mapping["Jugador"] == "player"
    assert mapping["Minutos jugados"] == "minutes"
    assert mapping["Goles"] == "goals"
    assert mapping["Precisión pases"] == "pass_accuracy"
    assert mapping["% duelos"] == "duels_won_pct"
    assert unknown == []


def test_ignores_accents_case_and_separators():
    mapping, _ = cols.map_headers(["DEMARCACION", "posición", "Minutes_Played"])
    assert mapping["DEMARCACION"] == "position"
    assert mapping["Minutes_Played"] == "minutes"


def test_strips_export_suffixes():
    mapping, unknown = cols.map_headers(["Goals (total)", "Key Passes p90"])
    assert mapping["Goals (total)"] == "goals"
    assert mapping["Key Passes p90"] == "key_passes"
    assert unknown == []


def test_reports_unknown_headers_instead_of_guessing():
    mapping, unknown = cols.map_headers(["Jugador", "Índice propietario XYZ"])
    assert "Índice propietario XYZ" in unknown
    assert "Índice propietario XYZ" not in mapping


def test_first_column_wins_when_two_claim_same_canonical():
    mapping, unknown = cols.map_headers(["Goles", "Goals"])
    assert mapping == {"Goles": "goals"}
    assert unknown == ["Goals"]


def test_extra_map_overrides_and_rescues_unknown():
    mapping, unknown = cols.map_headers(
        ["Índice propietario XYZ"], extra_map={"Índice propietario XYZ": "xg"}
    )
    assert mapping["Índice propietario XYZ"] == "xg"
    assert unknown == []


def test_normalize_header_is_stable():
    assert cols.normalize_header("  Pases   Clave/90 ") == "pases clave p90"
