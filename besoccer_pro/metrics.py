"""Normalizacion de metricas: limpieza, por-90 y metricas derivadas."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import columns as cols

# Metricas donde MAS es PEOR. El signo se aplica al invertir el percentil.
NEGATIVE_METRICS = {
    "goals_conceded_p90",
    "errors_leading_to_shot_p90",
    "fouls_p90",
    "yellow_cards_p90",
    "red_cards_p90",
}


def _to_number(series: pd.Series) -> pd.Series:
    """Convierte a numero tolerando formatos de export.

    Maneja '85%', '1.234,5' (formato ES), '1,234.5' (formato EN), '€2.5M',
    '-' y celdas vacias.
    """
    if pd.api.types.is_numeric_dtype(series):
        return series.astype(float)

    text = series.astype(str).str.strip()
    text = text.str.replace(r"[€$£\s]", "", regex=True)
    text = text.str.replace("%", "", regex=False)

    # Sufijos de valor de mercado: 2.5M -> 2500000, 800K -> 800000.
    multiplier = pd.Series(1.0, index=series.index)
    multiplier = multiplier.mask(text.str.match(r"^-?[\d.,]+[Mm]$", na=False), 1e6)
    multiplier = multiplier.mask(text.str.match(r"^-?[\d.,]+[KkMm]il$", na=False), 1e3)
    multiplier = multiplier.mask(text.str.match(r"^-?[\d.,]+[Kk]$", na=False), 1e3)
    text = text.str.replace(r"[MmKk](il)?$", "", regex=True)

    # Decimales: si hay coma y punto, el ultimo separador manda.
    both = text.str.contains(",", na=False) & text.str.contains(r"\.", na=False)
    comma_last = both & (text.str.rfind(",") > text.str.rfind("."))
    text = text.mask(comma_last, text.str.replace(".", "", regex=False).str.replace(",", ".", regex=False))
    text = text.mask(both & ~comma_last, text.str.replace(",", "", regex=False))
    # Solo coma: decimal en formato ES.
    only_comma = text.str.contains(",", na=False) & ~text.str.contains(r"\.", na=False)
    text = text.mask(only_comma, text.str.replace(",", ".", regex=False))

    text = text.replace({"": None, "-": None, "nan": None, "None": None, "N/A": None, "n/a": None})
    return pd.to_numeric(text, errors="coerce") * multiplier


def coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte a numerico todas las columnas canonicas que deben serlo."""
    numeric_fields = set(
        cols.VOLUME_METRICS + cols.RATIO_METRICS + cols.CONTEXT_FIELDS
        + cols.PROPRIETARY_FIELDS
    ) | {"age", "height", "market_value"}
    out = df.copy()
    for column in out.columns:
        if column in numeric_fields:
            out[column] = _to_number(out[column])
    return out


def derive_age(df: pd.DataFrame, season_end_year: int | None = None) -> pd.DataFrame:
    """Rellena `age` desde `birth_date` cuando el export no trae la edad."""
    out = df.copy()
    if "age" in out.columns and out["age"].notna().any():
        if "birth_date" not in out.columns:
            return out

    if "birth_date" in out.columns:
        # ISO primero (lo mas comun en exports); lo que quede sin parsear se
        # reintenta como fecha europea dd/mm/aaaa.
        births = pd.to_datetime(out["birth_date"], errors="coerce", format="ISO8601")
        if births.isna().any():
            fallback = pd.to_datetime(
                out["birth_date"], errors="coerce", dayfirst=True, format="mixed"
            )
            births = births.fillna(fallback)
        reference = pd.Timestamp(
            year=season_end_year or pd.Timestamp.today().year, month=6, day=30
        )
        computed = (reference - births).dt.days / 365.25
        if "age" in out.columns:
            out["age"] = out["age"].fillna(computed)
        else:
            out["age"] = computed
    return out


def add_contract_years(df: pd.DataFrame, today: pd.Timestamp | None = None) -> pd.DataFrame:
    """Anos de contrato restantes a partir de `contract_until`.

    Acepta las formas habituales de export: "2027", "30/06/2027", "2027-06-30"
    y "jun 2027". Un ano suelto se interpreta como 30 de junio, que es el
    cierre de temporada europeo.
    """
    out = df.copy()
    if "contract_until" not in out.columns:
        return out

    raw = out["contract_until"].astype(str).str.strip()
    reference = today or pd.Timestamp.today()

    # Ano suelto -> 30 de junio de ese ano.
    year_only = raw.str.fullmatch(r"(19|20)\d{2}(\.0)?")
    parsed = pd.to_datetime(
        raw.where(~year_only.fillna(False)), errors="coerce",
        dayfirst=True, format="mixed",
    )
    years = pd.to_numeric(raw.str.extract(r"^((?:19|20)\d{2})")[0], errors="coerce")
    june = pd.to_datetime(
        years.where(year_only.fillna(False)).dropna().astype(int).astype(str) + "-06-30",
        errors="coerce",
    )
    parsed = parsed.fillna(june)

    out["contract_until_date"] = parsed
    out["contract_years_left"] = (parsed - reference).dt.days / 365.25
    return out


def add_per90(df: pd.DataFrame) -> pd.DataFrame:
    """Anade columnas `<metrica>_p90` para toda metrica de volumen presente.

    Se exige un minimo de minutos para calcular el ratio: por debajo, el
    por-90 es ruido puro y es preferible dejarlo vacio.
    """
    out = df.copy()
    if "minutes" not in out.columns:
        raise ValueError(
            "El export no tiene columna de minutos. Sin minutos no se puede "
            "normalizar a por-90 ni medir fiabilidad. Revisa `doctor`."
        )

    minutes = out["minutes"].fillna(0)
    nineties = (minutes / 90.0).replace(0, np.nan)

    for metric in cols.VOLUME_METRICS:
        if metric in out.columns:
            out[f"{metric}_p90"] = out[metric] / nineties

    for card in ("yellow_cards", "red_cards"):
        if card in out.columns:
            out[f"{card}_p90"] = out[card] / nineties

    return out


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula ratios que el export puede no traer pero se deducen."""
    out = df.copy()

    def ratio(numerator: str, denominator: str, target: str, scale: float = 100.0):
        if target in out.columns and out[target].notna().any():
            return
        if numerator in out.columns and denominator in out.columns:
            den = out[denominator].replace(0, np.nan)
            out[target] = (out[numerator] / den) * scale

    ratio("passes_completed", "passes", "pass_accuracy")
    ratio("duels_won", "duels_attempted", "duels_won_pct")
    ratio("aerials_won", "aerials_attempted", "aerials_won_pct")
    ratio("dribbles_completed", "dribbles_attempted", "dribble_success_pct")
    ratio("goals", "shots", "conversion_pct")
    ratio("saves", "shots", "save_pct")
    ratio("clean_sheets", "matches", "clean_sheet_rate")

    # save_pct correcto para porteros: paradas / (paradas + goles encajados).
    if {"saves", "goals_conceded"}.issubset(out.columns):
        faced = out["saves"] + out["goals_conceded"]
        computed = (out["saves"] / faced.replace(0, np.nan)) * 100
        if "save_pct" in out.columns:
            out["save_pct"] = out["save_pct"].where(out["save_pct"].notna(), computed)
        else:
            out["save_pct"] = computed

    # Porcentajes que vienen en 0-1 en algunos exports -> pasar a 0-100.
    for pct in cols.RATIO_METRICS:
        if pct in out.columns:
            series = out[pct]
            if series.notna().any() and series.max(skipna=True) <= 1.5:
                out[pct] = series * 100

    if {"goals", "assists"}.issubset(out.columns):
        out["goal_contributions"] = out["goals"].fillna(0) + out["assists"].fillna(0)
        if "minutes" in out.columns:
            nineties = (out["minutes"] / 90.0).replace(0, np.nan)
            out["goal_contributions_p90"] = out["goal_contributions"] / nineties

    return out


def available_metrics(df: pd.DataFrame, weights: dict[str, float]) -> dict[str, float]:
    """Filtra los pesos de una posicion a las metricas presentes y con datos.

    Renormaliza en valor absoluto para que el score siga en escala 0-100
    aunque falte la mitad del juego de metricas.
    """
    present = {
        metric: weight
        for metric, weight in weights.items()
        if metric in df.columns and df[metric].notna().any()
    }
    total = sum(abs(w) for w in present.values())
    if total == 0:
        return {}
    return {metric: weight / total for metric, weight in present.items()}


def prepare(df: pd.DataFrame, season_end_year: int | None = None) -> pd.DataFrame:
    """Pipeline completo de normalizacion sobre un DataFrame ya mapeado."""
    out = coerce_numeric(df)
    out = derive_age(out, season_end_year)
    out = add_contract_years(out)
    out = add_derived(out)
    out = add_per90(out)
    out = add_derived(out)  # segunda pasada: ratios que dependen de p90
    return out
