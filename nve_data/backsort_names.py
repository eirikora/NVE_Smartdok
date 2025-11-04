#!/usr/bin/env python3
"""Lag en backsorted versjon av unique-names.txt.

Leser en tekstfil der hvert navn står på egen linje, og skriver ut en ny fil
(backsorted-names.txt) der navnene er sortert alfabetisk baklengs – dvs.
bokstavrekkefølgen vurderes fra slutten av hvert ord (slik at 'aa' kommer før 'ba').

Eksempel:
  Input:
      aa
      ab
      ba
  Output:
      aa
      ba
      ab
"""

from pathlib import Path

def main():
    input_path = Path("unique-names.txt")
    output_path = Path("backsorted-names.txt")

    if not input_path.exists():
        print(f"❌ Fant ikke {input_path}")
        return 1

    # Les navn og fjern tomme linjer
    with input_path.open(encoding="utf-8") as f:
        names = [line.strip() for line in f if line.strip()]

    # Sorter baklengs (etter omvendt streng)
    sorted_names = sorted(names, key=lambda n: n[::-1])

    # Skriv resultat
    with output_path.open("w", encoding="utf-8") as f:
        for name in sorted_names:
            f.write(name + "\n")

    print(f"✅ Skrev {len(sorted_names)} navn til {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
