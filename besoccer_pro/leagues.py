"""Carga de coeficientes de liga y traduccion entre competiciones."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "leagues.yaml"


def _strip_accents(text: str) -> str:
    table = str.maketrans("áàäâéèëêíìïîóòöôúùüûñç", "aaaaeeeeiiiioooouuuunc")
    return text.translate(table)


def _norm(name) -> str:
    text = _strip_accents(str(name).strip().lower())
    for noise in ("  ", ".", "-", "_"):
        text = text.replace(noise, " ")
    return " ".join(text.split())


class LeagueStrength:
    """Coeficientes de fuerza de liga, cargados de YAML y editables en caliente."""

    def __init__(self, coefficients: dict[str, float], default: float = 0.70):
        self._coefficients = {_norm(k): float(v) for k, v in coefficients.items()}
        self.default = float(default)
        self.unmatched: set[str] = set()

    @classmethod
    def load(cls, path: str | os.PathLike | None = None) -> "LeagueStrength":
        config_path = Path(path) if path else DEFAULT_CONFIG
        with open(config_path, "r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
        return cls(raw.get("leagues", {}), raw.get("default", 0.70))

    def coefficient(self, league) -> float:
        """Coeficiente de una liga. Registra las no reconocidas para avisar."""
        key = _norm(league)
        if key in self._coefficients:
            return self._coefficients[key]

        # Coincidencia parcial: "Serie A (Italia) 2024/25" -> "serie a".
        candidates = [
            (name, coef)
            for name, coef in self._coefficients.items()
            if len(name) >= 4 and (name in key or key in name)
        ]
        if candidates:
            name, coef = max(candidates, key=lambda item: len(item[0]))
            return coef

        if key:
            self.unmatched.add(str(league))
        return self.default

    def __contains__(self, league) -> bool:
        return _norm(league) in self._coefficients

    def as_dict(self) -> dict[str, float]:
        return dict(sorted(self._coefficients.items(), key=lambda kv: -kv[1]))
