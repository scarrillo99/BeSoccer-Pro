"""Formato de salida: tablas de consola, CSV, Markdown y ficha de jugador."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .positions import POSITION_LABELS, POSITION_WEIGHTS
from .scoring import _percentile

# Nombre legible de cada columna en los informes.
DISPLAY_NAMES = {
    "player": "Jugador",
    "age": "Edad",
    "team": "Equipo",
    "league": "Liga",
    "position_group": "Pos",
    "minutes": "Min",
    "matches": "PJ",
    "perf_score": "Nivel",
    "rate_score": "Calidad/90",
    "potential_score": "Techo",
    "breakout_index": "Irrupcion",
    "efficiency_gap": "Brecha",
    "visibility_score": "Escaparate",
    "reliability": "Fiab.",
    "league_coef": "CoefLiga",
    "market_value": "Valor",
    "salary": "Salario",
    "contract_until": "Contrato",
    "contract_years_left": "AnosContr",
    "besoccer_index": "IdxBeSoccer",
    "elo": "Elo",
    "reap": "REAP",
    "potential_rating": "PotBeSoccer",
    "goals": "G",
    "assists": "A",
    "goal_contributions": "G+A",
}

DEFAULT_COLUMNS = [
    "player", "age", "position_group", "team", "league", "minutes",
    "perf_score", "rate_score", "potential_score", "breakout_index",
    "reliability",
]


def _present(df: pd.DataFrame, requested) -> list[str]:
    return [c for c in requested if c in df.columns]


def format_table(df: pd.DataFrame, columns=None, max_width: int = 22) -> str:
    """Tabla de texto alineada, apta para terminal."""
    columns = _present(df, columns or DEFAULT_COLUMNS)
    if df.empty or not columns:
        return "(sin resultados con esos filtros)"

    view = df[columns].copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            decimals = 3 if column == "reliability" else (0 if column in ("minutes", "age") else 1)
            view[column] = view[column].round(decimals)
    view = view.astype(object).where(view.notna(), "-")

    headers = [DISPLAY_NAMES.get(c, c) for c in columns]
    rows = [[str(v)[:max_width] for v in record] for record in view.values]

    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rows)) if rows else len(headers[i])
        for i in range(len(headers))
    ]

    def line(cells):
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(cells)).rstrip()

    out = [line(headers), "  ".join("-" * w for w in widths)]
    out.extend(line(row) for row in rows)
    return "\n".join(out)


def to_markdown(df: pd.DataFrame, columns=None, title: str | None = None) -> str:
    columns = _present(df, columns or DEFAULT_COLUMNS)
    if df.empty or not columns:
        return f"### {title}\n\n_(sin resultados)_\n" if title else "_(sin resultados)_\n"

    view = df[columns].copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            decimals = 3 if column == "reliability" else (0 if column in ("minutes", "age") else 1)
            view[column] = view[column].round(decimals)
    view = view.astype(object).where(view.notna(), "-")

    headers = [DISPLAY_NAMES.get(c, c) for c in columns]
    lines = []
    if title:
        lines.append(f"### {title}\n")
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for record in view.values:
        lines.append("| " + " | ".join(str(v) for v in record) + " |")
    return "\n".join(lines) + "\n"


def save(df: pd.DataFrame, path: str | Path, columns=None) -> Path:
    """Guarda el listado en CSV, XLSX o Markdown segun la extension."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    columns = _present(df, columns or DEFAULT_COLUMNS)
    view = df[columns] if columns else df

    suffix = destination.suffix.lower()
    if suffix in (".md", ".markdown"):
        destination.write_text(to_markdown(df, columns), encoding="utf-8")
    elif suffix in (".xlsx", ".xls"):
        view.to_excel(destination, index=False)
    else:
        view.to_csv(destination, index=False, encoding="utf-8-sig")
    return destination


def profile(df: pd.DataFrame, name: str, radar_metrics: int = 8) -> str:
    """Ficha de un jugador: puntuaciones y percentiles frente a sus pares.

    Los percentiles se calculan contra jugadores de su misma demarcacion y
    liga (si el grupo es suficiente), que es la comparacion que interesa.
    """
    needle = name.strip().lower()
    matches = df[df["player"].astype(str).str.lower().str.contains(needle, na=False)]
    if matches.empty:
        return f"No se encuentra ningun jugador que contenga '{name}'."

    blocks = []
    for _, player in matches.head(5).iterrows():
        position = player["position_group"]
        peers = df[df["position_group"] == position]
        same_league = peers[peers.get("league") == player.get("league")]
        if len(same_league) >= 8:
            peers = same_league
            scope = f"{player.get('league', '?')}"
        else:
            scope = "todas las ligas del pool"

        header = [
            f"{player['player']}  ({POSITION_LABELS.get(position, position)})",
            f"  Equipo: {player.get('team', '-')}   Liga: {player.get('league', '-')}"
            f"   Edad: {player.get('age', '-')}",
            f"  Minutos: {player.get('minutes', '-')}   Fiabilidad: {player.get('reliability', '-')}"
            f"   Coef. liga: {player.get('league_coef', '-')}",
            "",
            f"  Nivel actual .......... {player.get('perf_score', float('nan')):.1f}",
            f"  Calidad por 90 ........ {player.get('rate_score', float('nan')):.1f}",
            f"  Techo estimado ........ {player.get('potential_score', float('nan')):.1f}",
            f"  Escaparate actual ..... {player.get('visibility_score', float('nan')):.1f}",
            f"  Indice de irrupcion ... {player.get('breakout_index', float('nan')):+.1f}",
            "",
            f"  Percentiles vs {POSITION_LABELS.get(position, position)} de {scope} "
            f"(n={len(peers)}):",
        ]

        weights = POSITION_WEIGHTS.get(position, {})
        rows = []
        for metric, weight in weights.items():
            if metric not in peers.columns or peers[metric].notna().sum() < 3:
                continue
            pct = _percentile(peers[metric])
            value = player.get(metric)
            score = pct.get(player.name)
            if score is None or (isinstance(score, float) and np.isnan(score)):
                continue
            if weight < 0:
                score = 100 - score
            rows.append((metric, value, score, abs(weight)))

        rows.sort(key=lambda item: item[3], reverse=True)
        for metric, value, score, _weight in rows[:radar_metrics]:
            bar = "#" * int(round(score / 5)) + "." * (20 - int(round(score / 5)))
            shown = f"{value:,.2f}" if isinstance(value, (int, float, np.floating)) and not pd.isna(value) else "-"
            header.append(f"    {metric:<28} {shown:>9}  [{bar}] p{score:.0f}")

        blocks.append("\n".join(header))

    return "\n\n".join(blocks)


def summary(df: pd.DataFrame) -> str:
    """Resumen del pool cargado: cobertura por liga y demarcacion."""
    lines = [f"Jugadores en el pool: {len(df)}"]
    if "league" in df.columns:
        by_league = df.groupby("league").agg(
            jugadores=("player", "count"),
            coef=("league_coef", "first"),
            min_medios=("minutes", "mean"),
        ).sort_values("jugadores", ascending=False)
        lines.append("\nPor liga:")
        for league, row in by_league.iterrows():
            lines.append(
                f"  {str(league)[:32]:<34} {int(row['jugadores']):>5} jug."
                f"   coef {row['coef']:.2f}   {row['min_medios']:.0f} min medios"
            )
    lines.append("\nPor demarcacion:")
    for position, count in df["position_group"].value_counts().items():
        lines.append(f"  {POSITION_LABELS.get(position, position):<24} {count:>5}")
    return "\n".join(lines)
