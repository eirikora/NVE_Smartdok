#!/usr/bin/env python3
"""
list_fields.py

Leser en liste med JSONL-filer og skriver ut alle unike feltnavn per fil.
"""

import json
from pathlib import Path

# Liste med alle filene du vil undersøke
FILES = [
    "elver_per_name.jsonl",
    "innsjoe_full.jsonl",
    "havvind.jsonl",
    "solkraftverk.jsonl",
    "vannkraftverk.jsonl",
    "varme_lag1_industri.jsonl",
    "varme_lag2_datasenter.jsonl",
    "varme_lag3_avfallsforbrenning.jsonl",
    "varme_lag4_fjernvarme_konsesjon.jsonl",
    "varme_lag5_fjernvarme_effekt.jsonl",
    "varme_lag6_fjernvarme_produksjon.jsonl",
    "vindkraftverk.jsonl",
]

def list_fields_in_file(path: Path) -> set[str]:
    """
    Åpner én JSONL-fil og returnerer settet av alle unike nøkkelstrenger
    fra top-nivå i hvert JSON-objekt i filen.
    """
    fields = set()
    with path.open(encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            # samle alle top-nivå-nøkler
            if isinstance(obj, dict):
                fields.update(obj.keys())
    return fields

def main():
    for filename in FILES:
        path = Path(filename)
        if not path.exists():
            print(f"[ADVARSEL] Fil ikke funnet: {filename}")
            continue

        felter = list_fields_in_file(path)
        print(f"\n--- {filename} ---")
        for k in sorted(felter):
            print(k)

if __name__ == "__main__":
    main()
