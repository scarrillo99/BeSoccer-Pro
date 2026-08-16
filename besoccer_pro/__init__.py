"""BeSoccer Pro — deteccion de talento sobre exports de datos de scouting.

Uso rapido desde Python:

    from besoccer_pro import ingest, scoring

    data, report = ingest.load(["data/laliga.csv", "data/eredivisie.csv"])
    scored = scoring.score_players(data)
    lista = scoring.breakouts(scored, max_age=22, top=30)
"""

from . import columns, ingest, leagues, metrics, positions, reports, scoring

__version__ = "1.0.0"

__all__ = [
    "columns", "ingest", "leagues", "metrics", "positions", "reports", "scoring",
]
