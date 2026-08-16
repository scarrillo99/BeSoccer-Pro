"""Pruebas de carga extremo a extremo sobre los exports de muestra."""

from pathlib import Path

import pandas as pd
import pytest

from besoccer_pro import ingest, scoring

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"

pytestmark = pytest.mark.skipif(
    not SAMPLE_DIR.exists(),
    reason="Genera los datos de muestra con: python tools/make_sample.py",
)


def test_loads_both_header_languages_into_one_pool():
    data, report = ingest.load([str(SAMPLE_DIR)])
    assert len(data) > 500
    assert report["unknown_columns"] == {}
    assert set(data["league"].unique()) >= {"Eredivisie", "Championship"}
    # Cabeceras ES e EN acaban en las mismas columnas canonicas.
    assert {"player", "minutes", "goals", "position_group"} <= set(data.columns)


def test_semicolon_and_comma_separated_files_both_parse():
    spanish, _ = ingest.load([str(SAMPLE_DIR / "export_es_muestra.csv")])
    english, _ = ingest.load([str(SAMPLE_DIR / "export_en_sample.csv")])
    assert len(spanish) > 400 and len(english) > 400
    assert spanish["minutes"].notna().all()


def test_per90_columns_are_created_on_load():
    data, _ = ingest.load([str(SAMPLE_DIR)])
    assert "goals_p90" in data.columns
    played = data[data["minutes"] > 0]
    expected = played["goals"] / (played["minutes"] / 90)
    assert played["goals_p90"].round(6).equals(expected.round(6))


def test_every_row_gets_a_position_group():
    data, _ = ingest.load([str(SAMPLE_DIR)])
    assert data["position_group"].notna().all()


def test_full_pipeline_produces_ranked_lists():
    data, _ = ingest.load([str(SAMPLE_DIR)])
    scored = scoring.score_players(data)
    for column in ("perf_score", "rate_score", "potential_score", "breakout_index"):
        assert scored[column].notna().any()

    strikers = scoring.rank(scored, position="ST", top=10)
    assert len(strikers) == 10
    assert (strikers["position_group"] == "ST").all()
    assert strikers["perf_score"].is_monotonic_decreasing

    talents = scoring.breakouts(scored, max_age=21, min_minutes=600, top=10)
    assert (talents["age"] <= 21).all()
    assert talents["breakout_index"].is_monotonic_decreasing


def test_diagnose_lists_recognised_columns():
    result = ingest.diagnose([str(SAMPLE_DIR)])
    assert len(result["files"]) == 2
    for detail in result["files"]:
        assert detail["unknown"] == []
        assert "player" in detail["recognised"]
        assert detail["positions_unmapped"] == []


def test_missing_player_column_raises_a_useful_error(tmp_path):
    path = tmp_path / "malo.csv"
    pd.DataFrame({"Equipo": ["A"], "Minutos jugados": [900]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="nombre de jugador"):
        ingest.load([str(path)])


def test_unknown_file_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        ingest.load(["no_existe_este_fichero.csv"])
