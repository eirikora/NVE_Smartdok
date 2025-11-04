#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leser unique-names.txt og ending_map.json.
Lager:
  - mapped-names.txt : navn med kategori (backsorted)
  - not_mapped.txt   : umappede navn (backsorted)
"""

import json
from pathlib import Path


def load_ending_map(path: Path) -> dict[str, str]:
    """Leser mapping fra JSON-fil."""
    if not path.exists():
        raise FileNotFoundError(f"Fant ikke {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def replace_with_category(text: str, ending_map: dict[str, str]) -> str | None:
    """
    Mapper hvert ord i teksten separat, slik at:
        'Storelva ved Oslofjorden' -> 'StorELV ved OsloFJORD'
    Hvis ingen ord matches, returneres None.
    """
    stripped = text.strip()
    if not stripped:
        return None

    words = stripped.split()
    endings_sorted = sorted(ending_map.keys(), key=len, reverse=True)
    mapped_any = False
    mapped_words = []

    for word in words:
        original = word
        lower_word = word.lower()
        replaced = False

        for ending in endings_sorted:
            if lower_word.endswith(ending) and len(lower_word) > len(ending):
                cut = len(word) - len(ending)
                word = word[:cut] + ending_map[ending]
                replaced = True
                mapped_any = True
                break

        mapped_words.append(word)

    result = " ".join(mapped_words)
    return result if mapped_any else None


def main():
    input_path = Path("unique-names.txt")
    mapped_path = Path("mapped-names.txt")
    not_mapped_path = Path("not_mapped.txt")
    map_path = Path("ending_map.json")

    # Les JSON mapping
    try:
        ending_map = load_ending_map(map_path)
    except Exception as e:
        print(f"❌ Kunne ikke lese mapping: {e}")
        return 1

    mapped = []
    not_mapped = []

    with input_path.open(encoding="utf-8") as infile:
        for line in infile:
            name = line.strip()
            if not name:
                continue
            mapped_name = replace_with_category(name, ending_map)
            if mapped_name:
                mapped.append((name, mapped_name))
            else:
                not_mapped.append(name)

    # Sorter begge backsorted (slik at like endinger kommer sammen)
    mapped_sorted = sorted(mapped, key=lambda x: x[1][::-1])
    not_mapped_sorted = sorted(not_mapped, key=lambda n: n[::-1])

    # Skriv resultater
    with mapped_path.open("w", encoding="utf-8") as f:
        for orig, mapped_val in mapped_sorted:
            f.write(f"{orig},{mapped_val}\n")

    with not_mapped_path.open("w", encoding="utf-8") as f:
        for name in not_mapped_sorted:
            f.write(name + "\n")

    print(f"✅ Skrev {len(mapped_sorted)} mappede navn til {mapped_path}")
    print(f"✅ Skrev {len(not_mapped_sorted)} umappede navn til {not_mapped_path}")
    print(f"📘 Brukte mapping fra {map_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
