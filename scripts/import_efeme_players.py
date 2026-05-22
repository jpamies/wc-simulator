#!/usr/bin/env python3
"""Import players from EFEM API and store one JSON file per World Cup country.

The script supports partial imports and keeps a markdown status board under
`data/raw/efeme/README.md` so the import can be resumed later.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
GROUPS_PATH = BASE_DIR / "data" / "tournament" / "groups.json"
OUTPUT_DIR = BASE_DIR / "data" / "raw" / "efeme"
STATUS_PATH = OUTPUT_DIR / "import_status.json"
README_PATH = OUTPUT_DIR / "README.md"

API_URL = "https://efem.club/api/players/filter"
DEFAULT_PAGE_SIZE = 500
DEFAULT_ORDER = "efemScore desc"
API_VERSION = "26.3.0"
API_FALLBACK_VERSION = "26.2.0"

# Map WC group names to EFEM API names when they differ
EFEM_NAME_ALIASES = {
    "USA": "United States",
    "Korea Republic": "South Korea",
    "Bosnia-Herzegovina": "Bosnia",
    "Côte d'Ivoire": "Ivory Coast",
    "IR Iran": "Iran",
    "Cabo Verde": "Cape Verde",
}

# Some countries need a direct regex pattern because a plain name is ambiguous.
EFEM_FILTER_PATTERNS = {
    "Congo DR": "Congo",
}

# Additional server-side-safe guardrails: once fetched, keep only matching nation codes.
POST_FETCH_NATION_CODE_FILTERS = {
    "Korea Republic": {"KOR"},
    "Congo DR": {"COD"},
}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.lower().replace("&", " and ").replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


def load_world_cup_countries() -> list[str]:
    doc = read_json(GROUPS_PATH)
    groups = doc.get("groups", {})
    countries: list[str] = []
    for group_code in sorted(groups.keys()):
        countries.extend(groups[group_code])
    # Keep order but remove duplicates if any.
    seen: set[str] = set()
    ordered_unique: list[str] = []
    for c in countries:
        if c not in seen:
            seen.add(c)
            ordered_unique.append(c)
    return ordered_unique


def get_country_filter_term(country: str) -> str:
    direct_pattern = EFEM_FILTER_PATTERNS.get(country)
    if direct_pattern is not None:
        return direct_pattern

    efem_country_name = EFEM_NAME_ALIASES.get(country, country)
    # Keep wildcard behavior, but escape regex chars when using plain names.
    return re.escape(efem_country_name)


def build_query(country: str, page: int, page_size: int, order_by: str) -> str:
    filter_term = get_country_filter_term(country)
    filter_value = f"playerbase.gender=0,nationality=*{filter_term}/i"
    params = {
        "filterString": f"pageSize={page_size}",
        "page": str(page),
        "version": API_VERSION,
        "fallbackVersion": API_FALLBACK_VERSION,
        "filter": filter_value,
        "orderBy": order_by,
    }
    return urllib.parse.urlencode(params)


def fetch_page(country: str, page: int, page_size: int, order_by: str) -> dict[str, Any]:
    query = build_query(country, page, page_size, order_by)
    url = f"{API_URL}?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "wc-simulator-efeme-import/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        body = response.read().decode("utf-8")
    payload = json.loads(body)
    if not isinstance(payload, dict) or "data" not in payload:
        raise ValueError(f"Unexpected response for {country} page {page}")
    return payload


def fetch_country_players(country: str, page_size: int, order_by: str) -> tuple[list[dict[str, Any]], int]:
    players: list[dict[str, Any]] = []
    reported_total = 0
    page = 1

    while True:
        payload = fetch_page(country, page, page_size, order_by)
        if page == 1:
            reported_total = int(payload.get("count", 0))
        chunk = payload.get("data") or []
        if not chunk:
            break
        players.extend(chunk)

        if len(chunk) < page_size:
            break
        if reported_total and len(players) >= reported_total:
            break

        page += 1

    # Defensive dedupe by player id (if API sends duplicates across pages).
    dedup: dict[Any, dict[str, Any]] = {}
    for p in players:
        dedup[p.get("id")] = p
    final_players = list(dedup.values())

    allowed_codes = POST_FETCH_NATION_CODE_FILTERS.get(country)
    if allowed_codes:
        filtered_players: list[dict[str, Any]] = []
        for player in final_players:
            primary = player.get("primaryNationality") or {}
            code = primary.get("nationCode")
            if code in allowed_codes:
                filtered_players.append(player)
        final_players = filtered_players

    return final_players, reported_total


def load_status(countries: list[str]) -> dict[str, Any]:
    if STATUS_PATH.exists():
        doc = read_json(STATUS_PATH)
    else:
        doc = {
            "source": {
                "api_url": API_URL,
                "version": API_VERSION,
                "fallback_version": API_FALLBACK_VERSION,
                "default_page_size": DEFAULT_PAGE_SIZE,
                "order_by": DEFAULT_ORDER,
            },
            "countries": {},
            "last_update": None,
            "player_schema_reference": None,
        }

    countries_map = doc.setdefault("countries", {})
    for country in countries:
        countries_map.setdefault(
            country,
            {
                "status": "pending",
                "players": None,
                "extracted_at": None,
                "file": f"{slugify(country)}.json",
                "error": None,
            },
        )
    return doc


def schema_snapshot(player: dict[str, Any]) -> dict[str, Any]:
    top_level = sorted(player.keys())
    nested: dict[str, list[str]] = {}
    for key, value in player.items():
        if isinstance(value, dict):
            nested[key] = sorted(value.keys())
    return {
        "top_level_fields": top_level,
        "nested_fields": nested,
        "captured_at": now_iso(),
    }


def render_readme(status_doc: dict[str, Any], countries: list[str]) -> str:
    countries_map = status_doc.get("countries", {})
    imported = 0
    total_players = 0

    rows: list[str] = []
    for country in countries:
        item = countries_map.get(country, {})
        state = item.get("status", "pending")
        count = item.get("players")
        extracted_at = item.get("extracted_at") or "-"
        file_name = item.get("file", f"{slugify(country)}.json")

        if state == "done":
            imported += 1
            total_players += int(count or 0)

        players_txt = str(count) if count is not None else "-"
        rows.append(f"| {country} | {state} | {players_txt} | {extracted_at} | {file_name} |")

    schema_ref = status_doc.get("player_schema_reference") or {}
    top_fields = schema_ref.get("top_level_fields") or []
    nested_fields = schema_ref.get("nested_fields") or {}

    lines: list[str] = []
    lines.append("# EFEM Import Status")
    lines.append("")
    lines.append("Estado de la importación de jugadores desde EFEM para las 48 selecciones del Mundial 2026.")
    lines.append("")
    lines.append("## Resumen")
    lines.append("")
    lines.append(f"- Países objetivo: {len(countries)}")
    lines.append(f"- Países importados: {imported}")
    lines.append(f"- Jugadores almacenados: {total_players}")
    lines.append(f"- Última actualización: {status_doc.get('last_update') or '-'}")
    lines.append("")
    lines.append("## Estado por país")
    lines.append("")
    lines.append("| País | Estado | Jugadores | Extraído (UTC) | Archivo |")
    lines.append("|---|---:|---:|---|---|")
    lines.extend(rows)
    lines.append("")
    lines.append("## Datos obtenidos por jugador")
    lines.append("")
    if not top_fields:
        lines.append("Aún no hay muestras importadas. Tras la primera importación este bloque se completará automáticamente.")
    else:
        lines.append("### Campos top-level")
        lines.append("")
        lines.append(", ".join(top_fields))
        lines.append("")
        if nested_fields:
            lines.append("### Objetos anidados detectados")
            lines.append("")
            for key in sorted(nested_fields.keys()):
                lines.append(f"- {key}: {', '.join(nested_fields[key])}")
            lines.append("")
        lines.append(f"Muestra de esquema capturada: {schema_ref.get('captured_at', '-')}")

    lines.append("")
    lines.append("## Notas")
    lines.append("")
    lines.append("- Cada país se guarda en un JSON independiente dentro de este directorio.")
    lines.append("- El proceso es incremental: se puede lanzar por países y continuar más tarde.")
    lines.append("- El estado persistente se guarda en import_status.json.")
    lines.append("")
    lines.append("## Ejemplos de uso")
    lines.append("")
    lines.append("python scripts/import_efeme_players.py --country Spain")
    lines.append("python scripts/import_efeme_players.py --all")

    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import EFEM players by country")
    parser.add_argument(
        "--country",
        action="append",
        default=[],
        help="Country name from data/tournament/groups.json. Can be repeated.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Import all World Cup countries.",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help=f"EFEM page size (default: {DEFAULT_PAGE_SIZE}).",
    )
    parser.add_argument(
        "--order-by",
        default=DEFAULT_ORDER,
        help=f"Order by clause (default: '{DEFAULT_ORDER}').",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    countries = load_world_cup_countries()
    status_doc = load_status(countries)

    if args.all:
        target_countries = countries
    elif args.country:
        requested = {c.strip() for c in args.country if c.strip()}
        unknown = sorted(requested - set(countries))
        if unknown:
            print("Unknown countries:", ", ".join(unknown), file=sys.stderr)
            print("Use one of:", ", ".join(countries), file=sys.stderr)
            return 2
        target_countries = [c for c in countries if c in requested]
    else:
        print("Nothing to import. Use --all or one or more --country.", file=sys.stderr)
        return 2

    print(f"Importing {len(target_countries)} country(ies) with pageSize={args.page_size}")

    schema_set = bool(status_doc.get("player_schema_reference"))

    for idx, country in enumerate(target_countries, start=1):
        print(f"[{idx}/{len(target_countries)}] {country}...")
        status_item = status_doc["countries"][country]

        try:
            players, reported_total = fetch_country_players(country, args.page_size, args.order_by)
            extracted_at = now_iso()
            file_name = f"{slugify(country)}.json"
            out_path = OUTPUT_DIR / file_name

            country_doc = {
                "source": {
                    "api_url": API_URL,
                    "version": API_VERSION,
                    "fallback_version": API_FALLBACK_VERSION,
                    "order_by": args.order_by,
                    "page_size": args.page_size,
                    "country_filter": country,
                    "effective_filter_term": get_country_filter_term(country),
                },
                "extracted_at": extracted_at,
                "country": country,
                "reported_total": reported_total,
                "downloaded_total": len(players),
                "players": players,
            }
            write_json(out_path, country_doc)

            status_item["status"] = "done"
            status_item["players"] = len(players)
            status_item["extracted_at"] = extracted_at
            status_item["file"] = file_name
            status_item["error"] = None

            if players and not schema_set:
                status_doc["player_schema_reference"] = schema_snapshot(players[0])
                schema_set = True

            print(f"    OK: {len(players)} players saved to {file_name}")

        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            status_item["status"] = "error"
            status_item["error"] = str(exc)
            status_item["extracted_at"] = now_iso()
            print(f"    ERROR: {exc}", file=sys.stderr)

    status_doc["last_update"] = now_iso()
    write_json(STATUS_PATH, status_doc)

    readme = render_readme(status_doc, countries)
    README_PATH.write_text(readme, encoding="utf-8")

    print(f"Status updated: {STATUS_PATH}")
    print(f"Report updated: {README_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
