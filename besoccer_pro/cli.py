"""Interfaz de linea de comandos.

    python -m besoccer_pro doctor         --input data/*.csv
    python -m besoccer_pro summary        --input data/
    python -m besoccer_pro rank           --input data/ --position ST --top 30
    python -m besoccer_pro breakouts      --input data/ --max-age 22
    python -m besoccer_pro underperformers --input data/ --position CM
    python -m besoccer_pro profile        --input data/ --player "Apellido"
    python -m besoccer_pro leagues
"""

from __future__ import annotations

import argparse
import sys

from . import ingest, reports, scoring
from .leagues import LeagueStrength
from .positions import POSITION_GROUPS, POSITION_LABELS

EXTRA_REPORT_COLUMNS = {
    # Las columnas que el export no traiga se omiten solas al formatear.
    "breakouts": [
        "player", "age", "position_group", "team", "league", "group",
        "is_reserve_team", "minutes", "perf_score", "rate_score",
        "potential_score", "visibility_score", "breakout_index", "reliability",
        "besoccer_index", "contract_years_left",
    ],
    "underperformers": [
        "player", "age", "position_group", "team", "league", "minutes",
        "perf_score", "rate_score", "efficiency_gap", "potential_score",
        "reliability",
    ],
}


def _parse_map(values) -> dict[str, str]:
    """Convierte --map "Cabecera=canonico" en diccionario."""
    mapping: dict[str, str] = {}
    for item in values or []:
        if "=" not in item:
            raise SystemExit(f"--map espera FORMATO 'Cabecera=canonico', recibido: {item}")
        source, target = item.split("=", 1)
        mapping[source.strip()] = target.strip()
    return mapping


def _add_input_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", "-i", nargs="+", required=True,
                        help="Ficheros, globs o carpetas con los exports.")
    parser.add_argument("--map", dest="column_map", nargs="+",
                        help='Mapeo manual de cabeceras: --map "Goles totales=goals"')
    parser.add_argument("--delimiter", help="Separador del CSV si la deteccion falla.")
    parser.add_argument("--default-league",
                        help="Liga a asignar si el export no trae la columna.")
    parser.add_argument("--assume-position",
                        help="Demarcacion de TODO el fichero cuando el export no "
                             "la trae (ej. ST en un ranking de delanteros).")
    parser.add_argument("--assume-per90", dest="assume_per90",
                        action="store_true", default=None,
                        help="Los valores del export ya vienen por 90 minutos.")
    parser.add_argument("--assume-totals", dest="assume_per90",
                        action="store_false",
                        help="Los valores son totales de temporada (requiere minutos).")
    parser.add_argument("--season-end-year", type=int,
                        help="Ano de fin de temporada para calcular edades desde fecha de nacimiento.")
    parser.add_argument("--leagues-config",
                        help="Ruta alternativa a leagues.yaml con vuestros coeficientes.")
    parser.add_argument("--min-minutes", type=int, default=None,
                        help="Minutos minimos de muestra. Sin valor, cada comando usa "
                             "el suyo: 450 en rank, 600 en breakouts/underperformers.")


def _add_filter_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--position", "-p",
                        help=f"Demarcacion(es) separadas por coma: {', '.join(POSITION_GROUPS)}")
    parser.add_argument("--league", "-l", help="Filtra por liga (coincidencia parcial).")
    parser.add_argument("--max-age", type=float)
    parser.add_argument("--min-age", type=float)
    parser.add_argument("--min-reliability", type=float,
                        help="Fiabilidad minima 0-1 (0.5 ~ 900 minutos).")
    parser.add_argument("--reserves", choices=["only", "exclude"],
                        help="Filiales: 'only' solo filiales, 'exclude' sin ellos.")
    parser.add_argument("--max-contract-years", type=float,
                        help="Solo jugadores a los que les quedan como mucho N "
                             "anos de contrato (ej. 1 = ultimo ano, mas barato).")
    parser.add_argument("--top", "-n", type=int, default=25)
    parser.add_argument("--out", "-o", help="Guardar en .csv, .xlsx o .md")


def _load(args):
    data, report = ingest.load(
        args.input,
        extra_map=_parse_map(args.column_map),
        delimiter=args.delimiter,
        default_league=args.default_league,
        season_end_year=args.season_end_year,
        default_position=args.assume_position,
        assume_per90=args.assume_per90,
    )
    strength = LeagueStrength.load(args.leagues_config)
    scored = scoring.score_players(
        data, strength,
        min_minutes=args.min_minutes or scoring.DEFAULT_MIN_MINUTES,
    )

    warnings = []
    if not report.get("has_minutes"):
        warnings.append(
            "SIN MINUTOS. Los valores se tratan como ya normalizados por 90. "
            "No se puede medir el tamano de la muestra, asi que la columna "
            "Fiab. va vacia: un 0,60 goles/90 puede venir de 2.400 minutos o "
            "de 200 y aqui no hay forma de distinguirlo. Anade la columna de "
            "minutos al export."
        )
    if not report.get("has_age"):
        warnings.append(
            "SIN EDAD. El techo (potential_score) no se puede calcular y queda "
            "vacio, por lo que `breakouts` no devolvera nada. La edad es la "
            "mitad del calculo de potencial: anadela al export."
        )
    if report.get("assumed_position"):
        assumed = report["assumed_position"]
        warnings.append(
            f"Demarcacion declarada a mano: {assumed['rows']} jugadores "
            f"tratados como {assumed['group']}. Se comparan todos entre si."
        )
    if report.get("unmapped_position_rows"):
        warnings.append(
            f"{report['unmapped_position_rows']} filas descartadas por posicion "
            f"no reconocida: {', '.join(report.get('unmapped_positions', [])[:8])}"
        )
    if strength.unmatched:
        warnings.append(
            "Ligas sin coeficiente (se usa el valor por defecto, revisa "
            f"config/leagues.yaml): {', '.join(sorted(strength.unmatched)[:8])}"
        )
    if report.get("metrics_missing"):
        missing = report["metrics_missing"]
        warnings.append(
            f"{len(missing)} metricas ausentes en el export "
            f"(los pesos se reponderan): {', '.join(missing[:10])}"
        )
    for warning in warnings:
        print(f"[aviso] {warning}\n", file=sys.stderr)

    return scored


def _emit(result, args, columns=None, title=None):
    print(reports.format_table(result, columns))
    if args.out:
        path = reports.save(result, args.out, columns)
        print(f"\nGuardado en {path}", file=sys.stderr)
    if title:
        print(f"\n{len(result)} jugadores — {title}", file=sys.stderr)


def main(argv=None) -> int:
    """Punto de entrada. Los errores previstos salen como mensaje, no traceback."""
    try:
        return _run(argv)
    except (ValueError, FileNotFoundError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


def _run(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="besoccer-pro",
        description="Deteccion de talento sobre exports de BeSoccer Pro / Visother Pro.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser(
        "doctor", help="Comprueba que columnas del export se reconocen.")
    _add_input_args(doctor)

    summary_cmd = subparsers.add_parser(
        "summary", help="Resumen del pool: ligas, demarcaciones, cobertura.")
    _add_input_args(summary_cmd)

    rank_cmd = subparsers.add_parser(
        "rank", help="Mejores jugadores por nivel actual.")
    _add_input_args(rank_cmd)
    _add_filter_args(rank_cmd)
    rank_cmd.add_argument("--by", default="perf_score",
                          choices=["perf_score", "rate_score", "potential_score",
                                   "breakout_index", "efficiency_gap", "minutes"],
                          help="Criterio de ordenacion (defecto: nivel actual).")

    breakout_cmd = subparsers.add_parser(
        "breakouts", help="Techo alto con escaparate bajo: los que hay que fichar antes.")
    _add_input_args(breakout_cmd)
    _add_filter_args(breakout_cmd)
    breakout_cmd.add_argument("--min-potential", type=float, default=60.0)
    breakout_cmd.add_argument("--max-visibility", type=float,
                              help="Techo maximo de escaparate para que entre en la lista.")

    under_cmd = subparsers.add_parser(
        "underperformers",
        help="Rinden por 90 mas de lo que dice su rol: suplentes de nivel y mal encajados.")
    _add_input_args(under_cmd)
    _add_filter_args(under_cmd)
    under_cmd.add_argument("--min-gap", type=float, default=8.0)

    profile_cmd = subparsers.add_parser("profile", help="Ficha detallada de un jugador.")
    _add_input_args(profile_cmd)
    profile_cmd.add_argument("--player", required=True)

    leagues_cmd = subparsers.add_parser("leagues", help="Coeficientes de liga configurados.")
    leagues_cmd.add_argument("--leagues-config")

    args = parser.parse_args(argv)

    if args.command == "leagues":
        strength = LeagueStrength.load(getattr(args, "leagues_config", None))
        print(f"{'Liga':<36} Coef")
        print("-" * 44)
        for league, coefficient in strength.as_dict().items():
            print(f"{league:<36} {coefficient:.2f}")
        print(f"\nPor defecto (liga no listada): {strength.default:.2f}")
        print("Editables en config/leagues.yaml — son criterio de scouting, no dato oficial.")
        return 0

    if args.command == "doctor":
        result = ingest.diagnose(
            args.input, _parse_map(args.column_map), args.delimiter)
        for detail in result["files"]:
            print(f"\n=== {detail['file']} ===")
            print(f"  filas: {detail['rows']}   columnas: {detail['columns']}")
            print(f"  reconocidas ({len(detail['recognised'])}):")
            for canonical, original in sorted(detail["recognised"].items()):
                print(f"    {canonical:<28} <- {original}")
            if detail["unknown"]:
                print(f"  NO reconocidas ({len(detail['unknown'])}):")
                for column in detail["unknown"]:
                    print(f"    {column}")
                print('  -> mapealas con: --map "Nombre Columna=nombre_canonico"')
            if detail.get("positions_unmapped"):
                print(f"  posiciones sin mapear: {', '.join(detail['positions_unmapped'])}")
                print("  -> anadelas en besoccer_pro/positions.py (POSITION_ALIASES)")
        return 0

    data = _load(args)

    if args.command == "summary":
        print(reports.summary(data))
        return 0

    if args.command == "profile":
        print(reports.profile(data, args.player))
        return 0

    common = dict(position=args.position, league=args.league,
                  max_age=args.max_age, min_age=args.min_age,
                  min_reliability=args.min_reliability,
                  max_contract_years=args.max_contract_years,
                  reserves=args.reserves, top=args.top)

    if args.command == "rank":
        result = scoring.rank(
            data, by=args.by,
            min_minutes=args.min_minutes or scoring.DEFAULT_MIN_MINUTES,
            **common,
        )
        label = POSITION_LABELS.get((args.position or "").upper(), args.position or "todas")
        _emit(result, args, title=f"ranking por {args.by} — {label}")
        return 0

    if args.command == "breakouts":
        filters = {k: v for k, v in common.items() if k not in ("max_age", "top")}
        result = scoring.breakouts(
            data,
            max_age=args.max_age if args.max_age is not None else 23,
            min_minutes=args.min_minutes if args.min_minutes is not None else 600,
            min_potential=args.min_potential,
            max_visibility=args.max_visibility,
            top=args.top,
            **filters,
        )
        _emit(result, args, EXTRA_REPORT_COLUMNS["breakouts"],
              "techo alto / escaparate bajo")
        return 0

    if args.command == "underperformers":
        filters = {k: v for k, v in common.items() if k not in ("max_age", "top")}
        result = scoring.underperformers(
            data,
            max_age=args.max_age if args.max_age is not None else 25,
            min_minutes=args.min_minutes if args.min_minutes is not None else 600,
            min_efficiency_gap=args.min_gap,
            top=args.top,
            **filters,
        )
        _emit(result, args, EXTRA_REPORT_COLUMNS["underperformers"],
              "calidad por 90 por encima de su rol")
        return 0

    parser.error(f"Comando no soportado: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
