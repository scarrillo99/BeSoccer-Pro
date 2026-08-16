"""Demarcaciones y pesos de metricas por posicion.

Cada grupo posicional puntua con su propio juego de pesos: un central no se
mide con las mismas metricas que un extremo. Los pesos se renormalizan sobre
las metricas que realmente existen en el export, asi que un CSV incompleto
sigue produciendo un ranking valido (con menos resolucion).
"""

from __future__ import annotations

GK = "GK"
CB = "CB"
FB = "FB"
DM = "DM"
CM = "CM"
AM = "AM"
W = "W"
ST = "ST"

POSITION_GROUPS = [GK, CB, FB, DM, CM, AM, W, ST]

POSITION_LABELS = {
    GK: "Portero",
    CB: "Central",
    FB: "Lateral / carrilero",
    DM: "Pivote",
    CM: "Mediocentro",
    AM: "Mediapunta",
    W: "Extremo",
    ST: "Delantero",
}

# Sinonimos de posicion tal y como aparecen en exports (ES/EN/abreviaturas).
# Se normaliza a minusculas y sin acentos antes de buscar aqui.
POSITION_ALIASES = {
    GK: [
        "gk", "por", "portero", "goalkeeper", "keeper", "arquero", "guardameta",
        "pt", "g",
    ],
    CB: [
        "cb", "dc", "central", "centre-back", "center back", "centre back",
        "defensa central", "zaguero", "libero", "rcb", "lcb", "cbr", "cbl",
    ],
    FB: [
        "fb", "lb", "rb", "lwb", "rwb", "lateral", "lateral derecho",
        "lateral izquierdo", "carrilero", "full-back", "full back", "wing-back",
        "wing back", "ld", "li", "defensa derecho", "defensa izquierdo",
    ],
    DM: [
        "dm", "cdm", "mcd", "pivote", "mediocentro defensivo",
        "defensive midfielder", "holding midfielder", "volante defensivo", "mc d",
    ],
    CM: [
        "cm", "mc", "mediocentro", "centre midfielder", "central midfielder",
        "midfielder", "medio", "interior", "box to box", "b2b", "volante",
    ],
    AM: [
        "am", "cam", "mp", "mco", "mediapunta", "enganche",
        "attacking midfielder", "playmaker", "media punta", "mediocentro ofensivo",
    ],
    W: [
        "w", "lw", "rw", "lm", "rm", "extremo", "extremo derecho",
        "extremo izquierdo", "winger", "wide midfielder", "banda", "ed", "ei",
    ],
    ST: [
        "st", "cf", "dc punta", "delantero", "delantero centro", "punta",
        "striker", "forward", "centre-forward", "center forward", "9",
        "segundo delantero", "ss",
    ],
}

# Pesos por metrica canonica y demarcacion. No tienen que sumar 1: se
# renormalizan sobre las metricas presentes en los datos.
#
# Convencion de signo: peso negativo = cuanto mas alto peor (ej. goles
# encajados). Ver metrics.NEGATIVE_METRICS.
POSITION_WEIGHTS = {
    GK: {
        "save_pct": 0.30,
        "goals_conceded_p90": -0.22,
        "clean_sheet_rate": 0.14,
        "saves_p90": 0.08,
        "pass_accuracy": 0.10,
        "long_pass_accuracy": 0.06,
        "claims_p90": 0.06,
        "errors_leading_to_shot_p90": -0.04,
    },
    CB: {
        "duels_won_pct": 0.16,
        "aerials_won_p90": 0.14,
        "aerials_won_pct": 0.10,
        "interceptions_p90": 0.10,
        "tackles_won_p90": 0.08,
        "clearances_p90": 0.05,
        "blocks_p90": 0.05,
        "pass_accuracy": 0.10,
        "progressive_passes_p90": 0.10,
        "recoveries_p90": 0.06,
        "goals_p90": 0.03,
        "errors_leading_to_shot_p90": -0.03,
    },
    FB: {
        "duels_won_pct": 0.12,
        "interceptions_p90": 0.09,
        "tackles_won_p90": 0.09,
        "recoveries_p90": 0.06,
        "progressive_passes_p90": 0.12,
        "progressive_carries_p90": 0.10,
        "crosses_completed_p90": 0.10,
        "key_passes_p90": 0.09,
        "xa_p90": 0.08,
        "dribbles_completed_p90": 0.07,
        "pass_accuracy": 0.05,
        "assists_p90": 0.03,
    },
    DM: {
        "interceptions_p90": 0.14,
        "tackles_won_p90": 0.12,
        "recoveries_p90": 0.12,
        "duels_won_pct": 0.12,
        "pass_accuracy": 0.12,
        "progressive_passes_p90": 0.14,
        "passes_p90": 0.06,
        "aerials_won_pct": 0.06,
        "key_passes_p90": 0.05,
        "fouls_p90": -0.04,
        "errors_leading_to_shot_p90": -0.03,
    },
    CM: {
        "progressive_passes_p90": 0.15,
        "pass_accuracy": 0.11,
        "key_passes_p90": 0.11,
        "xa_p90": 0.10,
        "recoveries_p90": 0.09,
        "interceptions_p90": 0.07,
        "tackles_won_p90": 0.06,
        "duels_won_pct": 0.08,
        "progressive_carries_p90": 0.08,
        "dribbles_completed_p90": 0.05,
        "goals_p90": 0.05,
        "assists_p90": 0.05,
    },
    AM: {
        "xa_p90": 0.16,
        "key_passes_p90": 0.15,
        "xg_p90": 0.12,
        "goals_p90": 0.10,
        "assists_p90": 0.10,
        "dribbles_completed_p90": 0.10,
        "progressive_passes_p90": 0.09,
        "progressive_carries_p90": 0.08,
        "touches_box_p90": 0.06,
        "pass_accuracy": 0.04,
    },
    W: {
        "xg_p90": 0.13,
        "xa_p90": 0.14,
        "goals_p90": 0.11,
        "assists_p90": 0.10,
        "dribbles_completed_p90": 0.15,
        "key_passes_p90": 0.10,
        "progressive_carries_p90": 0.11,
        "crosses_completed_p90": 0.06,
        "touches_box_p90": 0.06,
        "duels_won_pct": 0.04,
    },
    ST: {
        "xg_p90": 0.20,
        "goals_p90": 0.20,
        "shots_on_target_p90": 0.10,
        "touches_box_p90": 0.10,
        "xa_p90": 0.08,
        "assists_p90": 0.07,
        "aerials_won_p90": 0.07,
        "duels_won_pct": 0.06,
        "dribbles_completed_p90": 0.06,
        "conversion_pct": 0.06,
    },
}


def _strip_accents(text: str) -> str:
    table = str.maketrans("áàäâéèëêíìïîóòöôúùüûñç", "aaaaeeeeiiiioooouuuunc")
    return text.translate(table)


_ALIAS_LOOKUP = {}
for _group, _aliases in POSITION_ALIASES.items():
    for _alias in _aliases:
        _ALIAS_LOOKUP[_strip_accents(_alias.lower())] = _group


def normalize_position(raw) -> str | None:
    """Mapea el texto de posicion de un export a un grupo posicional.

    Devuelve None si no se reconoce, para que el jugador pueda filtrarse o
    revisarse a mano en vez de colarse en un ranking equivocado.
    """
    if raw is None:
        return None
    text = _strip_accents(str(raw).strip().lower())
    if not text:
        return None

    if text.upper() in POSITION_GROUPS:
        return text.upper()

    # Exports multiposicion: "MC, MCO" o "RW/LW" -> manda la primera.
    # Ojo: el guion NO es separador aqui, va dentro de nombres legitimos
    # ("centre-back", "wing-back"); solo cuenta rodeado de espacios.
    for separator in (",", "/", "|", ";", " - "):
        if separator in text:
            head = text.split(separator)[0].strip()
            if head:
                text = head
                break

    if text in _ALIAS_LOOKUP:
        return _ALIAS_LOOKUP[text]

    # Coincidencia por prefijo/subcadena para variantes largas
    # ("delantero centro izquierdo").
    best = None
    for alias, group in _ALIAS_LOOKUP.items():
        if len(alias) < 3:
            continue
        if text.startswith(alias) or alias in text:
            if best is None or len(alias) > len(best[0]):
                best = (alias, group)
    return best[1] if best else None
