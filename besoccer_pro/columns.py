"""Mapeo de cabeceras de export -> nombres canonicos.

Los exports de BeSoccer Pro / Visother salen con cabeceras en castellano o
ingles segun el idioma de la cuenta y el modulo. Aqui se centraliza el
diccionario de sinonimos para que el resto del pipeline trabaje siempre con
un unico juego de nombres.

Si una cabecera no se reconoce, `besoccer-pro doctor` la lista para que la
anadas aqui (o via --map en la CLI) en vez de perderla en silencio.
"""

from __future__ import annotations

import re

# Identificacion del jugador
IDENTITY_FIELDS = [
    "player", "team", "league", "group", "country", "season",
    "age", "birth_date", "position", "foot", "height", "market_value",
    "contract_until", "nationality", "player_id",
]

# Indices propios de BeSoccer Pro. No entran en el calculo del nivel (seria
# circular: son composites de las mismas metricas), pero se arrastran hasta
# los informes para poder contrastar el modelo contra su indice oficial.
PROPRIETARY_FIELDS = [
    "besoccer_index", "elo", "reap", "salary", "injury_days", "potential_rating",
]

# Metricas de volumen: se convierten a por-90.
VOLUME_METRICS = [
    "goals", "assists", "xg", "xa", "shots", "shots_on_target",
    "key_passes", "passes", "passes_completed", "progressive_passes",
    "progressive_carries", "dribbles_completed", "dribbles_attempted",
    "crosses", "crosses_completed", "touches_box", "aerials_won",
    "aerials_attempted", "duels_won", "duels_attempted", "tackles",
    "tackles_won", "interceptions", "recoveries", "clearances", "blocks",
    "fouls", "fouls_drawn", "saves", "goals_conceded", "claims",
    "errors_leading_to_shot",
]

# Metricas que ya son ratios/porcentajes: NO se dividen por 90.
RATIO_METRICS = [
    "pass_accuracy", "long_pass_accuracy", "duels_won_pct", "aerials_won_pct",
    "dribble_success_pct", "save_pct", "conversion_pct", "clean_sheet_rate",
]

# Contexto de participacion
CONTEXT_FIELDS = [
    "minutes", "matches", "starts", "yellow_cards", "red_cards", "clean_sheets",
]

COLUMN_SYNONYMS: dict[str, list[str]] = {
    # --- identidad ---
    "player": [
        "player", "jugador", "nombre", "name", "player name", "nombre jugador",
        "futbolista", "full name",
    ],
    "player_id": ["player id", "id jugador", "id", "idplayer", "player_id"],
    "team": [
        "team", "equipo", "club", "squad", "equipo actual", "current club",
    ],
    "league": [
        "league", "liga", "competition", "competicion", "torneo", "campeonato",
        "division", "categoria",
    ],
    # Divisiones con varios grupos territoriales (1a y 2a RFEF, Serie C,
    # Regionalliga...). Es determinante: el nivel entre grupos NO es el mismo.
    "group": [
        "group", "grupo", "subgrupo", "sub grupo", "conference", "zona",
        "grupo competicion",
    ],
    "country": ["country", "pais", "pais liga", "league country"],
    "season": ["season", "temporada", "campana", "year", "ano"],
    "age": ["age", "edad", "years", "anos"],
    "birth_date": [
        "birth date", "fecha nacimiento", "fecha de nacimiento", "nacimiento",
        "date of birth", "dob", "birthday",
    ],
    "position": [
        "position", "posicion", "demarcacion", "pos", "rol", "role",
        "posicion principal", "main position", "primary position",
    ],
    "foot": ["foot", "pie", "pierna", "pierna habil", "preferred foot"],
    "height": ["height", "altura", "estatura", "cm"],
    "nationality": ["nationality", "nacionalidad", "pais jugador", "passport"],
    "market_value": [
        "market value", "valor mercado", "valor de mercado", "valor",
        "transfer value", "value",
    ],
    "contract_until": [
        "contract until", "contrato hasta", "fin contrato", "contract expires",
        "vencimiento contrato", "contract end", "finalizacion contrato",
        "expiracion contrato", "hasta",
    ],
    # --- indices propios de BeSoccer Pro ---
    "besoccer_index": [
        "besoccer index", "indice besoccer", "indice de rendimiento",
        "indice rendimiento", "performance index", "rating", "valoracion",
        "nota", "indice",
    ],
    "elo": ["elo", "elo rating", "indice elo", "puntuacion elo"],
    "reap": ["reap", "indice reap", "reap index", "reap score"],
    "potential_rating": [
        "potential", "potencial", "indice potencial", "potential rating",
        "proyeccion",
    ],
    "salary": [
        "salary", "salario", "sueldo", "estimacion salarial", "salario estimado",
        "wage", "wages", "estimated salary", "ficha",
    ],
    "injury_days": [
        "injury days", "dias lesionado", "dias de baja", "days injured",
        "tiempo lesionado", "bajas",
    ],
    # --- participacion ---
    "minutes": [
        "minutes", "minutos", "min", "mins", "minutes played",
        "minutos jugados", "mp",
    ],
    "matches": [
        "matches", "partidos", "games", "pj", "apps", "appearances",
        "partidos jugados", "matches played",
    ],
    "starts": [
        "starts", "titularidades", "titular", "lineups", "once inicial",
        "matches started",
    ],
    "yellow_cards": [
        "yellow cards", "tarjetas amarillas", "amarillas", "ta", "yellow",
    ],
    "red_cards": ["red cards", "tarjetas rojas", "rojas", "tr", "red"],
    "clean_sheets": [
        "clean sheets", "porterias a cero", "porteria a cero", "vallas invictas",
        "imbatido", "cs",
    ],
    # --- ataque ---
    "goals": ["goals", "goles", "g", "gol", "goals scored"],
    "assists": ["assists", "asistencias", "a", "asist", "ast"],
    "xg": ["xg", "expected goals", "goles esperados", "x g"],
    "xa": [
        "xa", "expected assists", "asistencias esperadas", "x a", "xag",
    ],
    "shots": ["shots", "tiros", "remates", "disparos", "total shots"],
    "shots_on_target": [
        "shots on target", "tiros a puerta", "remates a puerta",
        "disparos a puerta", "sot", "tiros puerta",
    ],
    "conversion_pct": [
        "conversion", "conversion rate", "porcentaje conversion", "efectividad",
        "% conversion", "goal conversion",
    ],
    "touches_box": [
        "touches in box", "toques en area", "toques area",
        "touches in penalty area", "toques en el area",
    ],
    # --- creacion ---
    "key_passes": [
        "key passes", "pases clave", "ocasiones creadas", "chances created",
        "kp", "pases de gol",
    ],
    "passes": ["passes", "pases", "total passes", "pases totales"],
    "passes_completed": [
        "passes completed", "pases completados", "pases acertados",
        "pases buenos", "accurate passes", "pases correctos",
    ],
    "pass_accuracy": [
        "pass accuracy", "precision pases", "% pases", "porcentaje pases",
        "acierto pase", "pass %", "pass success", "precision de pase",
    ],
    "long_pass_accuracy": [
        "long pass accuracy", "precision pases largos", "% pases largos",
        "acierto pase largo",
    ],
    "progressive_passes": [
        "progressive passes", "pases progresivos", "pases de progresion",
        "prog passes",
    ],
    "progressive_carries": [
        "progressive carries", "conducciones progresivas", "conducciones",
        "prog carries", "carries",
    ],
    "crosses": ["crosses", "centros", "total crosses"],
    "crosses_completed": [
        "crosses completed", "centros completados", "centros acertados",
        "accurate crosses", "centros buenos",
    ],
    # --- regate y duelos ---
    "dribbles_completed": [
        "dribbles completed", "regates completados", "regates exitosos",
        "successful dribbles", "regates buenos", "dribbles won",
    ],
    "dribbles_attempted": [
        "dribbles", "regates", "dribbles attempted", "regates intentados",
    ],
    "dribble_success_pct": [
        "dribble success", "% regates", "porcentaje regates",
        "acierto regate",
    ],
    "duels_won": ["duels won", "duelos ganados", "duelos won"],
    "duels_attempted": [
        "duels", "duelos", "duels attempted", "duelos disputados",
        "total duels",
    ],
    "duels_won_pct": [
        "duels won %", "% duelos", "porcentaje duelos", "duelos ganados %",
        "duel success", "acierto duelos",
    ],
    "aerials_won": [
        "aerials won", "duelos aereos ganados", "juegos aereos ganados",
        "aerial duels won", "aereos ganados",
    ],
    "aerials_attempted": [
        "aerials", "duelos aereos", "aerial duels", "juegos aereos",
    ],
    "aerials_won_pct": [
        "aerials won %", "% duelos aereos", "porcentaje aereos",
        "aerial success", "acierto aereo",
    ],
    # --- defensa ---
    "tackles": ["tackles", "entradas", "tackles attempted"],
    "tackles_won": [
        "tackles won", "entradas ganadas", "entradas exitosas",
        "successful tackles",
    ],
    "interceptions": ["interceptions", "intercepciones", "int", "cortes"],
    "recoveries": [
        "recoveries", "recuperaciones", "balones recuperados", "ball recoveries",
    ],
    "clearances": ["clearances", "despejes", "rechaces"],
    "blocks": ["blocks", "bloqueos", "tiros bloqueados", "blocked shots"],
    "fouls": ["fouls", "faltas", "faltas cometidas", "fouls committed"],
    "fouls_drawn": [
        "fouls drawn", "faltas recibidas", "fouls suffered", "faltas a favor",
    ],
    "errors_leading_to_shot": [
        "errors", "errores", "errors leading to shot", "errores que acaban en tiro",
        "fallos graves",
    ],
    # --- porteria ---
    "saves": ["saves", "paradas", "atajadas", "detenciones"],
    "save_pct": [
        "save %", "% paradas", "porcentaje paradas", "save percentage",
        "acierto paradas", "saves %",
    ],
    "goals_conceded": [
        "goals conceded", "goles encajados", "goles recibidos", "gc",
        "goals against",
    ],
    "claims": [
        "claims", "salidas", "blocajes", "high claims", "salidas aereas",
    ],
}


def _strip_accents(text: str) -> str:
    table = str.maketrans("áàäâéèëêíìïîóòöôúùüûñç", "aaaaeeeeiiiioooouuuunc")
    return text.translate(table)


def normalize_header(header: str) -> str:
    """Normaliza una cabecera para compararla: minusculas, sin acentos ni ruido."""
    text = _strip_accents(str(header).strip().lower())
    text = text.replace("/90", " p90").replace("per 90", " p90")
    text = re.sub(r"[_\-.]+", " ", text)
    text = re.sub(r"[^a-z0-9%+ ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


_SYNONYM_LOOKUP: dict[str, str] = {}
for _canonical, _variants in COLUMN_SYNONYMS.items():
    _SYNONYM_LOOKUP[normalize_header(_canonical)] = _canonical
    for _variant in _variants:
        _SYNONYM_LOOKUP[normalize_header(_variant)] = _canonical


def map_headers(
    headers, extra_map: dict[str, str] | None = None
) -> tuple[dict[str, str], list[str]]:
    """Mapea las cabeceras de un export a nombres canonicos.

    Devuelve (mapeo cabecera->canonico, lista de cabeceras no reconocidas).
    `extra_map` permite forzar equivalencias desde la CLI sin tocar el codigo.
    """
    overrides = {
        normalize_header(k): v for k, v in (extra_map or {}).items()
    }
    mapping: dict[str, str] = {}
    unknown: list[str] = []
    taken: set[str] = set()

    for header in headers:
        key = normalize_header(header)
        canonical = overrides.get(key) or _SYNONYM_LOOKUP.get(key)

        if canonical is None:
            # Tolera sufijos de export: "Goles (total)", "Goals p90".
            stripped = re.sub(r"\b(total|totales|p90|90|avg|media)\b", "", key).strip()
            stripped = re.sub(r"\s+", " ", stripped)
            if stripped and stripped != key:
                canonical = overrides.get(stripped) or _SYNONYM_LOOKUP.get(stripped)

        if canonical is None:
            unknown.append(header)
            continue

        # La primera columna que reclama un canonico se lo queda; evita que
        # "Goles" y "Goles p90" compitan por el mismo destino.
        if canonical in taken:
            unknown.append(header)
            continue

        mapping[header] = canonical
        taken.add(canonical)

    return mapping, unknown


ALL_CANONICAL = (
    IDENTITY_FIELDS + CONTEXT_FIELDS + VOLUME_METRICS + RATIO_METRICS
    + PROPRIETARY_FIELDS
)
