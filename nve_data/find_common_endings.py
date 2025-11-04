#!/usr/bin/env python3
"""Finn vanlige endinger i vassdragsnavn og sorter dem baklengs.

Leser 'backsorted-names.txt' (baklengs sortert liste over navn),
finner alle endinger som forekommer minst 3 ganger (3–8 bokstaver),
filtrerer bort kortere overlappende varianter,
og skriver dem baklengs-sortert til 'common_endings.txt' i format:

    åga,8
    elva,6
    vatn,5
"""

from collections import Counter
from pathlib import Path


def all_suffixes(word: str, min_len: int = 3, max_len: int = 8) -> list[str]:
    """Returner alle suffikser av ordet mellom min_len og max_len."""
    word = word.lower().strip()
    return [word[-i:] for i in range(min_len, min(len(word), max_len) + 1)]


def main():
    input_path = Path("backsorted-names.txt")
    output_path = Path("common_endings.txt")

    if not input_path.exists():
        print(f"❌ Fant ikke {input_path}")
        return 1

    with input_path.open(encoding="utf-8") as f:
        names = [line.strip().lower() for line in f if line.strip()]

    counter = Counter()
    for name in names:
        for suf in all_suffixes(name):
            counter[suf] += 1

    # behold bare de som forekommer minst 3 ganger
    frequent = {suf: cnt for suf, cnt in counter.items() if cnt >= 3}

    # filtrer bort kortere varianter hvis lengre finnes
    longest_unique: dict[str, int] = {}
    for suf, cnt in sorted(frequent.items(), key=lambda x: (-len(x[0]), -x[1], x[0])):
        if not any(longer.endswith(suf) for longer in longest_unique):
            longest_unique[suf] = cnt

    # sortér baklengs (etter omvendt streng)
    backsorted = sorted(longest_unique.items(), key=lambda x: (x[0][::-1],))

    # skriv resultat
    with output_path.open("w", encoding="utf-8") as f:
        for suf, cnt in backsorted:
            f.write(f"{suf},{cnt}\n")

    print(f"✅ Skrev {len(backsorted)} endinger til {output_path}")
    print("Eksempler (første 10):")
    for suf, cnt in backsorted[:10]:
        print(f"  {suf}: {cnt}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
