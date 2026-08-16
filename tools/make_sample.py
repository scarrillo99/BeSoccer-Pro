"""Genera exports de PRUEBA sintéticos para validar el pipeline.

IMPORTANTE: los jugadores, equipos y numeros de estos ficheros son INVENTADOS
por un generador aleatorio. No son datos reales ni sirven para scouting. Estan
solo para que el proyecto se pueda ejecutar y testear sin credenciales.

Se generan dos ficheros con cabeceras distintas (uno en castellano, otro en
ingles) precisamente para comprobar que el mapeo de columnas funciona.
"""

from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

random.seed(20260816)

OUTPUT = Path(__file__).resolve().parent.parent / "data" / "sample"

SYLLABLES_A = ["Ar", "Bel", "Cor", "Dan", "Eli", "Far", "Gol", "Hen", "Iva", "Jor",
               "Kal", "Lun", "Mor", "Nev", "Ost", "Pra", "Qui", "Ros", "Sil", "Tor"]
SYLLABLES_B = ["ba", "ce", "din", "ez", "fal", "gio", "hus", "ic", "ju", "kov",
               "lan", "mir", "nen", "os", "pel", "rin", "sen", "tov", "vic", "zar"]

POSITIONS_ES = ["POR", "DC", "Lateral derecho", "Pivote", "MC", "Mediapunta",
                "Extremo izquierdo", "Delantero centro"]
POSITIONS_EN = ["GK", "CB", "RB", "DM", "CM", "AM", "LW", "ST"]


def fake_name() -> str:
    return (random.choice(SYLLABLES_A) + random.choice(SYLLABLES_B) + " " +
            random.choice(SYLLABLES_A) + random.choice(SYLLABLES_B))


def player_row(position: str, league_quality: float) -> dict:
    """Genera una fila con perfil estadistico coherente con la demarcacion."""
    age = random.choices(range(17, 36), weights=[2, 4, 6, 8, 9, 10, 10, 9, 9, 8,
                                                 7, 6, 5, 4, 3, 2, 2, 1, 1])[0]
    minutes = int(random.triangular(120, 3200, 1800))
    nineties = max(minutes / 90, 0.5)
    talent = random.betavariate(2.2, 2.2)  # 0-1, calidad latente del jugador

    base = {
        "position": position,
        "age": age,
        "minutes": minutes,
        "matches": max(1, int(minutes / random.uniform(55, 90))),
        "pass_accuracy": round(random.uniform(62, 92) + talent * 5, 1),
        "duels_won_pct": round(random.uniform(38, 62) + talent * 8, 1),
        "aerials_won_pct": round(random.uniform(30, 70), 1),
        "recoveries": round(nineties * random.uniform(3, 9) * (0.7 + talent), 0),
        "interceptions": round(nineties * random.uniform(0.5, 2.5) * (0.7 + talent), 0),
        "tackles_won": round(nineties * random.uniform(0.4, 2.2) * (0.7 + talent), 0),
        "clearances": round(nineties * random.uniform(0.2, 4.0), 0),
        "blocks": round(nineties * random.uniform(0.1, 1.2), 0),
        "fouls": round(nineties * random.uniform(0.4, 2.2), 0),
        "progressive_passes": round(nineties * random.uniform(1.5, 8) * (0.6 + talent), 0),
        "progressive_carries": round(nineties * random.uniform(0.5, 5) * (0.6 + talent), 0),
        "key_passes": round(nineties * random.uniform(0.2, 2.2) * (0.5 + talent), 0),
        "dribbles_completed": round(nineties * random.uniform(0.1, 3.0) * (0.5 + talent), 0),
        "crosses_completed": round(nineties * random.uniform(0.05, 1.5), 0),
        "touches_box": round(nineties * random.uniform(0.2, 6.0), 0),
        "aerials_won": round(nineties * random.uniform(0.3, 4.0), 0),
        "yellow_cards": random.randint(0, 9),
        "red_cards": random.choices([0, 1, 2], weights=[92, 7, 1])[0],
        "market_value": int(
            (talent ** 2 * 40_000_000 * league_quality) * random.uniform(0.4, 1.6)
            * (1.4 if age < 24 else 0.8) + 50_000
        ),
    }

    attacking = {"Delantero centro", "ST", "Extremo izquierdo", "LW",
                 "Mediapunta", "AM"}
    if position in attacking:
        rate = talent * random.uniform(0.25, 0.85)
        base["goals"] = int(nineties * rate)
        base["assists"] = int(nineties * rate * random.uniform(0.3, 0.9))
        base["xg"] = round(nineties * rate * random.uniform(0.8, 1.25), 2)
        base["xa"] = round(nineties * rate * random.uniform(0.3, 0.9), 2)
        base["shots"] = int(nineties * random.uniform(1.0, 4.5))
        base["shots_on_target"] = int(base["shots"] * random.uniform(0.25, 0.55))
    elif position in {"POR", "GK"}:
        base["saves"] = int(nineties * random.uniform(2.0, 4.5) * (1.3 - talent * 0.4))
        base["goals_conceded"] = int(nineties * random.uniform(0.7, 2.0) * (1.4 - talent * 0.6))
        base["clean_sheets"] = int(base["matches"] * random.uniform(0.05, 0.45) * (0.6 + talent))
        base["claims"] = int(nineties * random.uniform(0.2, 1.5))
        base["goals"] = 0
        base["assists"] = 0
    else:
        base["goals"] = int(nineties * talent * random.uniform(0.0, 0.20))
        base["assists"] = int(nineties * talent * random.uniform(0.0, 0.25))
        base["xg"] = round(nineties * random.uniform(0.01, 0.18), 2)
        base["xa"] = round(nineties * random.uniform(0.02, 0.25), 2)
        base["shots"] = int(nineties * random.uniform(0.2, 1.8))
        base["shots_on_target"] = int(base["shots"] * random.uniform(0.2, 0.5))

    return base


def build_league(name: str, teams: int, quality: float, positions) -> pd.DataFrame:
    rows = []
    club_names = [f"{random.choice(SYLLABLES_A)}{random.choice(SYLLABLES_B)} FC"
                  for _ in range(teams)]
    for club in club_names:
        squad = ["POR" if positions is POSITIONS_ES else "GK"] * 2
        squad += [random.choice(positions[1:]) for _ in range(20)]
        for position in squad:
            row = player_row(position, quality)
            row.update({"player": fake_name(), "team": club, "league": name})
            rows.append(row)
    return pd.DataFrame(rows)


HEADERS_ES = {
    "player": "Jugador", "team": "Equipo", "league": "Liga", "age": "Edad",
    "position": "Demarcación", "minutes": "Minutos jugados", "matches": "PJ",
    "goals": "Goles", "assists": "Asistencias", "xg": "Goles esperados",
    "xa": "Asistencias esperadas", "shots": "Remates",
    "shots_on_target": "Remates a puerta", "key_passes": "Pases clave",
    "pass_accuracy": "Precisión pases", "progressive_passes": "Pases progresivos",
    "progressive_carries": "Conducciones progresivas",
    "dribbles_completed": "Regates completados", "crosses_completed": "Centros acertados",
    "touches_box": "Toques en área", "aerials_won": "Duelos aéreos ganados",
    "aerials_won_pct": "% duelos aéreos", "duels_won_pct": "% duelos",
    "tackles_won": "Entradas ganadas", "interceptions": "Intercepciones",
    "recoveries": "Recuperaciones", "clearances": "Despejes", "blocks": "Bloqueos",
    "fouls": "Faltas cometidas", "yellow_cards": "Tarjetas amarillas",
    "red_cards": "Tarjetas rojas", "saves": "Paradas",
    "goals_conceded": "Goles encajados", "clean_sheets": "Porterías a cero",
    "claims": "Salidas", "market_value": "Valor de mercado",
}

HEADERS_EN = {
    "player": "Player", "team": "Club", "league": "Competition", "age": "Age",
    "position": "Position", "minutes": "Minutes Played", "matches": "Apps",
    "goals": "Goals", "assists": "Assists", "xg": "xG", "xa": "xA",
    "shots": "Shots", "shots_on_target": "Shots On Target",
    "key_passes": "Key Passes", "pass_accuracy": "Pass Accuracy",
    "progressive_passes": "Progressive Passes",
    "progressive_carries": "Progressive Carries",
    "dribbles_completed": "Dribbles Completed", "crosses_completed": "Accurate Crosses",
    "touches_box": "Touches In Box", "aerials_won": "Aerial Duels Won",
    "aerials_won_pct": "Aerials Won %", "duels_won_pct": "Duels Won %",
    "tackles_won": "Tackles Won", "interceptions": "Interceptions",
    "recoveries": "Recoveries", "clearances": "Clearances", "blocks": "Blocks",
    "fouls": "Fouls", "yellow_cards": "Yellow Cards", "red_cards": "Red Cards",
    "saves": "Saves", "goals_conceded": "Goals Conceded",
    "clean_sheets": "Clean Sheets", "claims": "High Claims",
    "market_value": "Market Value",
}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)

    spanish = pd.concat([
        build_league("LaLiga Hypermotion", 12, 0.55, POSITIONS_ES),
        build_league("Primera División Argentina", 12, 0.5, POSITIONS_ES),
    ], ignore_index=True)
    spanish.rename(columns=HEADERS_ES)[
        [v for k, v in HEADERS_ES.items() if k in spanish.columns]
    ].to_csv(OUTPUT / "export_es_muestra.csv", index=False, sep=";",
             encoding="utf-8-sig")

    english = pd.concat([
        build_league("Eredivisie", 12, 0.65, POSITIONS_EN),
        build_league("Championship", 12, 0.6, POSITIONS_EN),
    ], ignore_index=True)
    english.rename(columns=HEADERS_EN)[
        [v for k, v in HEADERS_EN.items() if k in english.columns]
    ].to_csv(OUTPUT / "export_en_sample.csv", index=False)

    print(f"Generados en {OUTPUT}:")
    print(f"  export_es_muestra.csv  ({len(spanish)} filas, separador ';', cabeceras ES)")
    print(f"  export_en_sample.csv   ({len(english)} filas, separador ',', cabeceras EN)")
    print("\nDATOS SINTÉTICOS — no usar para scouting real.")


if __name__ == "__main__":
    main()
