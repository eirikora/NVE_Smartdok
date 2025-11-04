#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bygger en omvendt indeks for vassdrag fra en JSONL-fil og skriver resultatet som JSON.

For hver linje i input hentes navn, vassdragsnummer og koordinater.
Navn normaliseres med ending_map.json slik at «Storelva ved Oslofjorden»
blir til «StorELV ved OsloFJORD».

Bruk:
    python build_regine_index.py vassdrag_nedborfelt_all.jsonl
"""

from __future__ import annotations
import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Iterable, List

# ----------------- Mønstre -----------------
NAME_FIELDS = ("NAVNVASSOMR", "navnNedbf", "navn1orden", "elvHierark")
PAREN_PATTERN = re.compile(r"\s*\([^)]*\)")
SPLIT_PATTERN = re.compile(r"/|,|\bog\b", flags=re.IGNORECASE)


# ----------------- Navnehåndtering -----------------
def normalise_names(value: str) -> list[str]:
    """Fjern parenteser og splitt på komma, skråstrek og 'og'."""
    stripped = PAREN_PATTERN.sub("", value or "").strip()
    if not stripped:
        return []
    return [p.strip() for p in SPLIT_PATTERN.split(stripped) if p.strip()]


def extract_names(record: dict) -> list[str]:
    """Trekk ut alle navn fra et JSONL-objekt."""
    ordered = OrderedDict()
    for field in NAME_FIELDS:
        val = record.get(field)
        if isinstance(val, str):
            for n in normalise_names(val):
                ordered.setdefault(n, None)
    lok = record.get("lokalnavn")
    if isinstance(lok, str):
        for n in normalise_names(lok):
            ordered.setdefault(n, None)
    return list(ordered.keys())


# ----------------- Lese input -----------------
def load_records(path: Path) -> Iterable[dict]:
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            text = line.strip()
            if not text:
                continue
            try:
                yield json.loads(text)
            except json.JSONDecodeError as e:
                raise ValueError(f"Feil på linje {lineno}: {e}") from e


# ----------------- Lese ending_map.json -----------------
def load_ending_map() -> dict[str, str]:
    map_path = Path(__file__).parent / "ending_map.json"
    if not map_path.exists():
        raise FileNotFoundError(f"Fant ikke {map_path}")
    with map_path.open(encoding="utf-8") as fh:
        return json.load(fh)


# ----------------- Erstatte endinger -----------------
def replace_with_category(text: str, ending_map: dict[str, str]) -> str:
    """Mapper hvert ord separat, f.eks. 'Storelva ved Oslofjorden' -> 'StorELV ved OsloFJORD'."""
    words = text.strip().split()
    endings = sorted(ending_map.keys(), key=len, reverse=True)
    mapped = []
    for w in words:
        lw = w.lower()
        for e in endings:
            if lw.endswith(e) and len(lw) > len(e):
                w = w[: len(w) - len(e)] + ending_map[e]
                break
        mapped.append(w)
    return " ".join(mapped)


# ----------------- Bygge utdata -----------------
def build_index(records: Iterable[dict], endings: dict[str, str]) -> list[dict]:
    out = []
    for rec in records:
        vnr = rec.get("VASSOMR") or rec.get("vassdragNr")
        lon, lat = rec.get("center_lon"), rec.get("center_lat")
        if not vnr or lon is None or lat is None:
            continue
        for n in extract_names(rec):
            out.append(
                {
                    "navn_normalisert": replace_with_category(n, endings),
                    "navn": n,
                    "vassdragsnr": vnr,
                    "long": lon,
                    "lat": lat,
                }
            )
    return out


# ----------------- CLI -----------------
def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path, help="JSONL-fil med vassdragmetadata")
    p.add_argument(
        "output",
        type=Path,
        nargs="?",
        help="Valgfri output-fil (default: INDEX_regine.json)",
    )
    return p.parse_args(argv)


# ----------------- MAIN -----------------
def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    input_path = args.input

    # Standard outputfil = INDEX_regine.json
    output_path = args.output or Path("INDEX_regine.json")

    endings = load_ending_map()
    data = build_index(load_records(input_path), endings)

    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)

    print(f"✅ {len(data)} rader skrevet til {output_path}")
    print(f"📘 Brukte mapping fra ending_map.json i {Path(__file__).parent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
