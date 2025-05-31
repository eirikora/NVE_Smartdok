#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Statistikk for elvenavn i elver_per_name.csv
-------------------------------------------
• Antall rader i fila
• Antall unike elvenavn
• Antall elvenavn som forekommer mer enn én gang
• Liste med duplikater + forekomsttall
"""

import pandas as pd
from pathlib import Path

DATAFIL = Path("elver_per_name.csv")


def main() -> None:
    df = pd.read_csv(DATAFIL)

    # Rens: trim whitespace og konverter til streng
    df["elvenavn"] = df["elvenavn"].astype(str).str.strip()

    total_rows = len(df)

    # Unike navn – ser bort fra tomme strenger/NaN
    name_mask = df["elvenavn"].notna() & (df["elvenavn"] != "")
    unique_names = df.loc[name_mask, "elvenavn"].nunique()

    # Finn duplikater
    dup_counts = (
        df.loc[name_mask, "elvenavn"]
        .value_counts()
        .loc[lambda s: s > 1]
        .sort_index()
    )
    n_dup_names = dup_counts.size

    # --- Utskrift ----------------------------------------------------------
    print(f"Antall rader i fila:      {total_rows}")
    print(f"Unike elvenavn:           {unique_names}")
    print(f"Antall duplikate navn:    {n_dup_names}")
    if n_dup_names:
        print("\nElvenavn som forekommer flere ganger:\n")
        print(dup_counts.to_string(header=False))


if __name__ == "__main__":
    main()
