"""Carga de exports (CSV/Excel) de BeSoccer Pro / Visother Pro.

Los exports varian por modulo, idioma y competicion. La estrategia es:
mapear cabeceras de forma tolerante, avisar de lo que no se reconoce y no
romper nunca por una columna que falta.
"""

from __future__ import annotations

import glob as globlib
import json
from pathlib import Path

import pandas as pd

from . import columns as cols
from . import metrics
from .positions import normalize_position


def _read_any(path: Path, delimiter: str | None = None) -> pd.DataFrame:
    """Lee CSV/TSV/Excel detectando separador y codificacion habituales."""
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls", ".xlsm"):
        return pd.read_excel(path)

    attempts = []
    if delimiter:
        attempts.append({"sep": delimiter})
    else:
        # sep=None + engine python -> deteccion automatica (coma, ';', tab).
        attempts.append({"sep": None, "engine": "python"})
        attempts.extend([{"sep": ";"}, {"sep": ","}, {"sep": "\t"}])

    last_error: Exception | None = None
    for options in attempts:
        for encoding in ("utf-8-sig", "latin-1"):
            try:
                frame = pd.read_csv(path, encoding=encoding, **options)
                if frame.shape[1] > 1:
                    return frame
            except Exception as error:  # noqa: BLE001 - se prueba el siguiente combo
                last_error = error
    if last_error:
        raise ValueError(f"No se pudo leer {path.name}: {last_error}")
    raise ValueError(f"{path.name} parece tener una sola columna. Revisa el separador.")


def expand_paths(patterns) -> list[Path]:
    """Expande rutas, globs y directorios a una lista de ficheros."""
    found: list[Path] = []
    for pattern in patterns:
        path = Path(pattern)
        if path.is_dir():
            for extension in ("*.csv", "*.tsv", "*.xlsx", "*.xls"):
                found.extend(sorted(path.glob(extension)))
        elif any(char in str(pattern) for char in "*?["):
            found.extend(sorted(Path(p) for p in globlib.glob(str(pattern))))
        elif path.exists():
            found.append(path)
        else:
            raise FileNotFoundError(f"No existe: {pattern}")
    if not found:
        raise FileNotFoundError(f"Ningun fichero coincide con: {patterns}")
    return found


def load_raw(
    patterns,
    extra_map: dict[str, str] | None = None,
    delimiter: str | None = None,
    default_league: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Carga y unifica exports. Devuelve (DataFrame canonico, informe de carga)."""
    files = expand_paths(patterns)
    frames: list[pd.DataFrame] = []
    report: dict = {"files": [], "unknown_columns": {}, "rows_in": 0}

    for path in files:
        raw = _read_any(path, delimiter)
        raw = raw.loc[:, ~raw.columns.astype(str).str.match(r"^Unnamed")]
        mapping, unknown = cols.map_headers(list(raw.columns), extra_map)

        frame = raw.rename(columns=mapping)
        frame = frame[[c for c in frame.columns if c in cols.ALL_CANONICAL]].copy()
        frame["source_file"] = path.name

        # Exports por liga que no repiten la columna liga en cada fila.
        if "league" not in frame.columns:
            frame["league"] = default_league or path.stem

        frames.append(frame)
        report["files"].append(
            {"file": path.name, "rows": len(raw), "mapped": len(mapping),
             "unknown": len(unknown)}
        )
        report["rows_in"] += len(raw)
        if unknown:
            report["unknown_columns"][path.name] = unknown

    combined = pd.concat(frames, ignore_index=True, sort=False)

    if "player" not in combined.columns:
        raise ValueError(
            "No se ha encontrado columna de nombre de jugador en ningun "
            "fichero. Usa `doctor` para ver las cabeceras detectadas y "
            "--map \"Tu Cabecera=player\" para forzar el mapeo."
        )

    report["rows_combined"] = len(combined)
    return combined, report


def load(
    patterns,
    extra_map: dict[str, str] | None = None,
    delimiter: str | None = None,
    default_league: str | None = None,
    season_end_year: int | None = None,
    drop_unknown_positions: bool = True,
) -> tuple[pd.DataFrame, dict]:
    """Carga + normaliza + asigna demarcacion. Listo para `scoring.score_players`."""
    combined, report = load_raw(patterns, extra_map, delimiter, default_league)

    if "position" in combined.columns:
        combined["position_group"] = combined["position"].apply(normalize_position)
    else:
        combined["position_group"] = None
        report["warning_position"] = (
            "El export no trae columna de posicion: no se puede puntuar por "
            "demarcacion. Anade la columna o usa --map."
        )

    unmapped_positions = combined[combined["position_group"].isna()]
    if len(unmapped_positions):
        raw_values = (
            unmapped_positions.get("position", pd.Series(dtype=object))
            .dropna().astype(str).unique().tolist()
        )
        report["unmapped_positions"] = sorted(raw_values)[:40]
        report["unmapped_position_rows"] = int(len(unmapped_positions))

    if drop_unknown_positions:
        combined = combined[combined["position_group"].notna()].copy()

    # Duplicados: mismo jugador en varios ficheros (ej. liga + copa).
    if {"player", "team"}.issubset(combined.columns):
        before = len(combined)
        subset = ["player", "team", "league"] if "league" in combined.columns else ["player", "team"]
        combined = combined.sort_values("minutes" if "minutes" in combined.columns else "player",
                                        ascending=False)
        combined = combined.drop_duplicates(subset=subset, keep="first")
        report["duplicates_removed"] = before - len(combined)

    prepared = metrics.prepare(combined, season_end_year)
    report["rows_out"] = len(prepared)
    report["metrics_present"] = sorted(
        m for m in cols.VOLUME_METRICS + cols.RATIO_METRICS
        if m in prepared.columns and prepared[m].notna().any()
    )
    report["metrics_missing"] = sorted(
        m for m in cols.VOLUME_METRICS + cols.RATIO_METRICS
        if m not in prepared.columns or not prepared[m].notna().any()
    )
    return prepared, report


def diagnose(patterns, extra_map: dict[str, str] | None = None,
             delimiter: str | None = None) -> dict:
    """Informe de compatibilidad de un export, sin puntuar nada.

    Pensado para la primera vez que se conecta un export nuevo: dice que
    columnas se han reconocido, cuales se han perdido y que metricas faltan
    para cada demarcacion.
    """
    files = expand_paths(patterns)
    result: dict = {"files": []}

    for path in files:
        raw = _read_any(path, delimiter)
        mapping, unknown = cols.map_headers(list(raw.columns), extra_map)
        detail = {
            "file": path.name,
            "rows": len(raw),
            "columns": len(raw.columns),
            "recognised": {v: k for k, v in mapping.items()},
            "unknown": unknown,
        }
        if "position" in mapping.values():
            source = next(k for k, v in mapping.items() if v == "position")
            values = raw[source].dropna().astype(str).unique().tolist()
            detail["positions_seen"] = sorted(values)[:40]
            detail["positions_unmapped"] = sorted(
                {v for v in values if normalize_position(v) is None}
            )[:40]
        result["files"].append(detail)

    return result


def to_json(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)
