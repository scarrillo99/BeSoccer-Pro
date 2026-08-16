"""Adaptador de API configurable (opcional).

No hay contrato publico documentado de la API de BeSoccer Pro / Visother, y
las credenciales NO van en el codigo. Este cliente es generico: se configura
por variables de entorno o por `config/api.yaml`, con la ruta de paginacion y
el campo que contiene los registros. Asi, cuando el proveedor confirme el
endpoint y entregue un token, solo hay que rellenar la config.

Variables de entorno:
    BESOCCER_API_BASE      URL base, ej. https://api.proveedor.com/v1
    BESOCCER_API_TOKEN     token/bearer (NUNCA se escribe en disco ni en logs)
    BESOCCER_API_AUTH      "bearer" (defecto) | "header" | "query"
    BESOCCER_API_KEY_NAME  nombre de cabecera/parametro si auth != bearer
    BESOCCER_API_RECORDS   ruta al array de registros, ej. "data.players"
    BESOCCER_API_PAGE_PARAM   nombre del parametro de pagina (defecto "page")
    BESOCCER_API_SIZE_PARAM   nombre del parametro de tamano (defecto "per_page")
"""

from __future__ import annotations

import os
import time
import urllib.parse
import urllib.request
import json
from pathlib import Path

import pandas as pd
import yaml

from . import columns as cols

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "api.yaml"


class ApiConfigError(RuntimeError):
    """La configuracion de API esta incompleta."""


def load_config(path: str | os.PathLike | None = None) -> dict:
    """Config desde YAML (si existe) sobrescrita por variables de entorno."""
    config: dict = {}
    config_path = Path(path) if path else CONFIG_PATH
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}

    env_map = {
        "base_url": "BESOCCER_API_BASE",
        "token": "BESOCCER_API_TOKEN",
        "auth_style": "BESOCCER_API_AUTH",
        "key_name": "BESOCCER_API_KEY_NAME",
        "records_path": "BESOCCER_API_RECORDS",
        "page_param": "BESOCCER_API_PAGE_PARAM",
        "size_param": "BESOCCER_API_SIZE_PARAM",
    }
    for key, variable in env_map.items():
        value = os.environ.get(variable)
        if value:
            config[key] = value

    config.setdefault("auth_style", "bearer")
    config.setdefault("page_param", "page")
    config.setdefault("size_param", "per_page")
    config.setdefault("page_size", 200)
    config.setdefault("max_pages", 100)
    config.setdefault("timeout", 30)
    config.setdefault("pause", 0.4)
    return config


def _dig(payload, path: str | None):
    """Extrae el array de registros siguiendo una ruta tipo 'data.players'."""
    if not path:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for value in payload.values():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    return value
        return []
    node = payload
    for part in path.split("."):
        if isinstance(node, dict):
            node = node.get(part)
        else:
            return []
    return node if isinstance(node, list) else []


def fetch(
    endpoint: str,
    params: dict | None = None,
    config: dict | None = None,
    paginate: bool = True,
) -> list[dict]:
    """Descarga registros de un endpoint, paginando hasta agotar resultados."""
    settings = config or load_config()
    base = settings.get("base_url")
    token = settings.get("token")
    if not base:
        raise ApiConfigError(
            "Falta la URL base. Define BESOCCER_API_BASE o config/api.yaml. "
            "Mientras tanto usa exports CSV, que es el camino soportado."
        )
    if not token:
        raise ApiConfigError(
            "Falta el token. Definelo en la variable de entorno "
            "BESOCCER_API_TOKEN. No lo escribas en ningun fichero del repo."
        )

    query = dict(params or {})
    headers = {"Accept": "application/json", "User-Agent": "besoccer-pro/1.0"}

    style = str(settings.get("auth_style", "bearer")).lower()
    if style == "bearer":
        headers["Authorization"] = f"Bearer {token}"
    elif style == "header":
        headers[settings.get("key_name") or "X-API-Key"] = token
    elif style == "query":
        query[settings.get("key_name") or "api_key"] = token
    else:
        raise ApiConfigError(f"auth_style no soportado: {style}")

    records: list[dict] = []
    page = int(settings.get("first_page", 1))
    pages_read = 0

    while True:
        if paginate:
            query[settings["page_param"]] = page
            query[settings["size_param"]] = settings["page_size"]

        url = f"{base.rstrip('/')}/{endpoint.lstrip('/')}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"

        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=settings["timeout"]) as response:
            payload = json.loads(response.read().decode("utf-8"))

        batch = _dig(payload, settings.get("records_path"))
        records.extend(batch)
        pages_read += 1

        if not paginate or not batch or len(batch) < int(settings["page_size"]):
            break
        if pages_read >= int(settings["max_pages"]):
            break
        page += 1
        time.sleep(float(settings["pause"]))

    return records


def to_frame(records: list[dict], extra_map: dict[str, str] | None = None) -> pd.DataFrame:
    """Convierte la respuesta cruda de la API al esquema canonico."""
    frame = pd.DataFrame(records)
    if frame.empty:
        return frame
    # Aplana un nivel de anidamiento: {"stats": {...}} -> stats_goals, etc.
    nested = [c for c in frame.columns if frame[c].apply(lambda v: isinstance(v, dict)).any()]
    for column in nested:
        expanded = pd.json_normalize(frame[column].apply(lambda v: v if isinstance(v, dict) else {}))
        expanded.columns = [f"{column}_{c}" for c in expanded.columns]
        frame = pd.concat([frame.drop(columns=[column]), expanded], axis=1)

    mapping, _unknown = cols.map_headers(list(frame.columns), extra_map)
    frame = frame.rename(columns=mapping)
    return frame[[c for c in frame.columns if c in cols.ALL_CANONICAL]].copy()
