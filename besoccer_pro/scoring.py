"""Modelo de puntuacion: nivel actual, techo y deteccion de infravalorados.

Ideas del modelo
----------------
1. Un jugador se compara PRIMERO contra sus pares de la misma demarcacion en
   SU liga (percentil intra-liga). Comparar en crudo a un central de la
   Eredivisie con uno de la Premier no dice nada.
2. Ese percentil se traduce a escala comun multiplicando por el coeficiente
   de liga (`config/leagues.yaml`). Eso da el NIVEL ACTUAL absoluto.
3. Con pocos minutos, un por-90 espectacular es ruido. Se aplica contraccion
   bayesiana hacia la media segun minutos jugados (fiabilidad).
4. El TECHO estima cuanto margen de mejora queda: recorrido por edad x
   calidad por-90 demostrada.
5. El INDICE DE IRRUPCION compara ese techo con la VISIBILIDAD actual del
   jugador (minutos, nivel de liga, valor de mercado). Un techo alto con
   visibilidad baja es exactamente el perfil que se busca: rinde poco hoy en
   terminos de escaparate, pero el dato dice que puede dar mucho mas.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .leagues import LeagueStrength
from .metrics import available_metrics
from .positions import POSITION_WEIGHTS

# Minutos a los que se considera media fiabilidad. 900 min = 10 partidos.
RELIABILITY_HALF_POINT = 900.0

# Tamano minimo de grupo para que el percentil intra-liga sea significativo.
MIN_POOL_SIZE = 8

# Recorrido de mejora restante por edad. 1.0 = todo por desarrollar.
AGE_HEADROOM = {
    16: 1.00, 17: 0.98, 18: 0.94, 19: 0.88, 20: 0.80, 21: 0.71,
    22: 0.61, 23: 0.50, 24: 0.38, 25: 0.26, 26: 0.16, 27: 0.08,
    28: 0.03, 29: 0.01,
}
DEFAULT_MIN_MINUTES = 450


def age_headroom(age) -> float:
    """Margen de crecimiento restante segun edad (0-1)."""
    if age is None or (isinstance(age, float) and np.isnan(age)):
        # Sin edad no se puede proyectar: se asume jugador ya formado.
        return 0.0
    years = int(np.floor(float(age)))
    if years <= 16:
        return 1.0
    if years >= 30:
        return 0.0
    return AGE_HEADROOM.get(years, 0.0)


def reliability(minutes, half_point: float = RELIABILITY_HALF_POINT) -> float:
    """Fiabilidad de la muestra (0-1) a partir de los minutos jugados."""
    if minutes is None or (isinstance(minutes, float) and np.isnan(minutes)):
        return 0.0
    played = max(float(minutes), 0.0)
    return played / (played + half_point)


def _percentile(series: pd.Series) -> pd.Series:
    """Percentil 0-100 dentro del grupo, robusto a NaN y a grupos de 1."""
    valid = series.notna()
    result = pd.Series(np.nan, index=series.index, dtype=float)
    count = int(valid.sum())
    if count == 0:
        return result
    if count == 1:
        result[valid] = 50.0
        return result
    result[valid] = series[valid].rank(pct=True, method="average") * 100
    return result


def _composite(
    group: pd.DataFrame, weights: dict[str, float]
) -> tuple[pd.Series, int]:
    """Score compuesto 0-100 de un grupo, ponderando percentiles por metrica.

    Peso negativo = metrica donde mas es peor: se invierte el percentil.
    Metricas sin dato para un jugador concreto se excluyen y el resto se
    reponderan, para no penalizar a quien tiene el export incompleto.
    """
    active = available_metrics(group, weights)
    if not active:
        return pd.Series(np.nan, index=group.index, dtype=float), 0

    weighted_sum = pd.Series(0.0, index=group.index)
    weight_used = pd.Series(0.0, index=group.index)

    for metric, weight in active.items():
        pct = _percentile(group[metric])
        if weight < 0:
            pct = 100 - pct
        magnitude = abs(weight)
        has_value = pct.notna()
        weighted_sum = weighted_sum.add((pct * magnitude).fillna(0), fill_value=0)
        weight_used = weight_used.add(has_value * magnitude, fill_value=0)

    score = weighted_sum / weight_used.replace(0, np.nan)
    return score, len(active)


def score_players(
    df: pd.DataFrame,
    league_strength: LeagueStrength | None = None,
    min_minutes: int = DEFAULT_MIN_MINUTES,
    reliability_half_point: float = RELIABILITY_HALF_POINT,
) -> pd.DataFrame:
    """Puntua un pool de jugadores ya normalizado (ver `metrics.prepare`).

    Devuelve el DataFrame con las columnas de scoring anadidas. Los jugadores
    por debajo de `min_minutes` se marcan en `below_min_minutes` pero NO se
    eliminan: filtrarlos es decision de cada informe.
    """
    strength = league_strength or LeagueStrength.load()

    if "position_group" not in df.columns:
        raise ValueError(
            "Falta `position_group`. Ejecuta el cargador (ingest) antes de puntuar."
        )

    out = df.copy().reset_index(drop=True)
    out["league_coef"] = out.get("league", pd.Series(index=out.index, dtype=object)).map(
        strength.coefficient
    )
    out["league_coef"] = out["league_coef"].fillna(strength.default)

    if "minutes" not in out.columns:
        out["minutes"] = np.nan
    out["below_min_minutes"] = out["minutes"].fillna(0) < min_minutes

    out["rate_percentile"] = np.nan   # percentil bruto intra-liga (calidad p90)
    out["metrics_used"] = 0
    out["pool_size"] = 0
    out["pool_type"] = ""

    # --- 1. Percentil dentro de (liga, grupo, demarcacion) ---
    # El grupo importa tanto como la liga en divisiones territoriales: en 2a
    # RFEF hay cinco grupos y el nivel entre ellos no es comparable. Si el
    # export trae la columna, se compara dentro del grupo.
    group_keys = ["position_group"]
    if "group" in out.columns and out["group"].notna().any():
        group_keys.insert(0, "group")
    if "league" in out.columns:
        group_keys.insert(0, "league")

    for keys, group in out.groupby(group_keys, dropna=False):
        position = keys[-1] if isinstance(keys, tuple) else keys
        weights = POSITION_WEIGHTS.get(position)
        if not weights:
            continue

        if len(group) >= MIN_POOL_SIZE:
            score, used = _composite(group, weights)
            out.loc[group.index, "rate_percentile"] = score
            out.loc[group.index, "metrics_used"] = used
            out.loc[group.index, "pool_size"] = len(group)
            out.loc[group.index, "pool_type"] = (
                "liga+grupo+posicion" if "group" in group_keys else "liga+posicion"
            )

    # --- 2. Fallback: ligas con muestra corta se puntuan contra toda la posicion ---
    pending = out["rate_percentile"].isna()
    if pending.any():
        for position, group in out[pending].groupby("position_group", dropna=False):
            weights = POSITION_WEIGHTS.get(position)
            if not weights:
                continue
            # Se puntua contra TODOS los jugadores de esa posicion del pool.
            reference = out[out["position_group"] == position]
            score, used = _composite(reference, weights)
            out.loc[group.index, "rate_percentile"] = score.reindex(group.index)
            out.loc[group.index, "metrics_used"] = used
            out.loc[group.index, "pool_size"] = len(reference)
            out.loc[group.index, "pool_type"] = "posicion (muestra corta)"

    # --- 3. Fiabilidad y contraccion hacia la media ---
    out["reliability"] = out["minutes"].apply(
        lambda m: reliability(m, reliability_half_point)
    )
    shrunk = 50.0 + out["reliability"] * (out["rate_percentile"] - 50.0)

    # --- 4. Traduccion a escala comun ---
    # rate_score  = calidad por-90 en bruto, traducida (senal de talento)
    # perf_score  = nivel actual creible (contraido por minutos)
    out["rate_score"] = out["rate_percentile"] * out["league_coef"]
    out["perf_score"] = shrunk * out["league_coef"]

    # --- 5. Techo ---
    headroom = out["age"].apply(age_headroom) if "age" in out.columns else 0.0
    out["age_headroom"] = headroom
    quality_gate = (out["rate_score"] / 100.0).clip(lower=0.0, upper=1.0)
    out["potential_score"] = (
        out["perf_score"]
        + out["age_headroom"] * (100.0 - out["perf_score"]) * quality_gate
    ).clip(upper=100.0)

    # Cuanto rinde por minuto frente a lo que se le reconoce.
    out["efficiency_gap"] = out["rate_score"] - out["perf_score"]

    # --- 6. Visibilidad: lo que hoy ve el mercado ---
    minutes_pct = _percentile(out["minutes"])
    league_component = out["league_coef"] * 100.0

    # Senales de "lo que el mercado ya paga por el": valor y salario. El
    # salario, cuando esta, es la mejor de las dos: refleja el sueldo pactado
    # hoy, no una estimacion de traspaso.
    market_signals = []
    labels = []
    threshold = max(10, int(0.25 * len(out)))
    for field, label in (("salary", "salario"), ("market_value", "valor")):
        if field in out.columns and out[field].notna().sum() >= threshold:
            pct = _percentile(out[field])
            market_signals.append(pct.fillna(pct.median()))
            labels.append(label)

    if market_signals:
        market_pct = sum(market_signals) / len(market_signals)
        visibility = (
            0.35 * minutes_pct.fillna(0)
            + 0.30 * league_component
            + 0.35 * market_pct
        )
        out["visibility_basis"] = "minutos+liga+" + "+".join(labels)
    else:
        visibility = 0.55 * minutes_pct.fillna(0) + 0.45 * league_component
        out["visibility_basis"] = "minutos+liga"

    out["visibility_score"] = visibility

    # --- 7. Indice de irrupcion: techo alto, escaparate bajo ---
    out["breakout_index"] = out["potential_score"] - out["visibility_score"]

    for column in ("rate_score", "perf_score", "potential_score",
                   "visibility_score", "breakout_index", "efficiency_gap"):
        out[column] = out[column].round(1)
    out["reliability"] = out["reliability"].round(3)

    return out


def rank(
    df: pd.DataFrame,
    by: str = "perf_score",
    position: str | None = None,
    league: str | None = None,
    max_age: float | None = None,
    min_age: float | None = None,
    min_minutes: int | None = None,
    min_reliability: float | None = None,
    max_contract_years: float | None = None,
    reserves: str | None = None,
    top: int = 25,
) -> pd.DataFrame:
    """Filtra y ordena un pool ya puntuado.

    `reserves`: None = todos, "only" = solo filiales, "exclude" = sin filiales.
    """
    view = df.copy()

    if reserves and "is_reserve_team" in view.columns:
        if reserves == "only":
            view = view[view["is_reserve_team"]]
        elif reserves == "exclude":
            view = view[~view["is_reserve_team"]]

    if max_contract_years is not None:
        if "contract_years_left" not in view.columns:
            raise ValueError(
                "El export no trae fecha de fin de contrato, no se puede "
                "filtrar por vencimiento. Anade esa columna en BeSoccer Pro."
            )
        view = view[view["contract_years_left"] <= max_contract_years]

    if position:
        wanted = {p.strip().upper() for p in position.split(",")}
        view = view[view["position_group"].isin(wanted)]
    if league:
        needle = league.lower()
        view = view[view["league"].astype(str).str.lower().str.contains(needle, na=False)]
    if max_age is not None and "age" in view.columns:
        view = view[view["age"] <= max_age]
    if min_age is not None and "age" in view.columns:
        view = view[view["age"] >= min_age]
    if min_minutes is not None:
        view = view[view["minutes"].fillna(0) >= min_minutes]
    if min_reliability is not None:
        view = view[view["reliability"] >= min_reliability]

    view = view.sort_values(by, ascending=False, na_position="last")
    return view.head(top) if top else view


def breakouts(
    df: pd.DataFrame,
    max_age: float = 23,
    min_minutes: int = 600,
    min_potential: float = 60.0,
    max_visibility: float | None = None,
    top: int = 30,
    **filters,
) -> pd.DataFrame:
    """Jugadores con techo alto y reconocimiento bajo hoy.

    Los valores por defecto son deliberadamente conservadores: 600 minutos
    para que el por-90 signifique algo, y techo minimo 60 para no llenar la
    lista de chavales con muestra anecdotica.
    """
    view = df[df["potential_score"] >= min_potential]
    if max_visibility is not None:
        view = view[view["visibility_score"] <= max_visibility]
    return rank(
        view,
        by="breakout_index",
        max_age=max_age,
        min_minutes=min_minutes,
        top=top,
        **filters,
    )


def underperformers(
    df: pd.DataFrame,
    max_age: float = 25,
    min_minutes: int = 600,
    min_efficiency_gap: float = 8.0,
    top: int = 30,
    **filters,
) -> pd.DataFrame:
    """Rinden por encima de lo que refleja su rol: mucha calidad p90, poco peso.

    Distinto de `breakouts`: aqui no manda la edad ni el escaparate, sino la
    brecha entre lo que hace en el campo y los minutos que acumula. Sirve para
    detectar suplentes de nivel y jugadores mal encajados en su equipo.
    """
    view = df[df["efficiency_gap"] >= min_efficiency_gap]
    return rank(view, by="efficiency_gap", max_age=max_age,
                min_minutes=min_minutes, top=top, **filters)
