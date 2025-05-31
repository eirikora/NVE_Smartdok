#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Statistikk for norske vannkraftverk
-----------------------------------
• Antall kraftverk
• Data som mangler (navn, idriftsatt år, effekt, koordinater, kommune)
• Total og gjennomsnittlig installert effekt (MW)
• Min./maks. driftsår
• Fordeling på status-kode
• Duplikate kraftverksnavn
"""

import json
import pandas as pd
from pathlib import Path

DATAFIL = Path("vannkraftverk.json")


def load_data(path: Path) -> pd.DataFrame:
    """Les JSON-filen og returnér som DataFrame."""
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return pd.DataFrame(data)


def main() -> None:
    df = load_data(DATAFIL)

    total = len(df)

    # masker for manglende verdier
    m_name = df["vannkraftverkNavn"].isna() | (df["vannkraftverkNavn"].astype(str).str.strip() == "")
    m_year = df["idriftsattAar"].isna()
    m_effect = df["maksYtelse_MW"].isna()
    m_coords = df["lat"].isna() | df["lon"].isna()
    m_kommune = df["kommuneNavn"].isna() | (df["kommuneNavn"].astype(str).str.strip() == "")

    # beregninger
    total_mw = df["maksYtelse_MW"].sum(skipna=True)
    avg_mw = df["maksYtelse_MW"].mean(skipna=True)
    min_year = int(df["idriftsattAar"].min(skipna=True))
    max_year = int(df["idriftsattAar"].max(skipna=True))

    # -- Duplikate navn ------------------------------------------------------
    # NB: Ser bort fra rader uten navn
    dup_counts = (
        df.loc[~m_name, "vannkraftverkNavn"]
        .value_counts()           # antall forekomster per navn
        .loc[lambda s: s > 1]     # beholder bare de som forekommer > 1 gang
        .sort_index()
    )
    n_dup_names = dup_counts.size
    # ------------------------------------------------------------------------

    print(f"Antall kraftverk: {total}")
    print(f"Uten navn:            {m_name.sum():>5}  ({m_name.mean():.1%})")
    print(f"Uten idriftsatt år:   {m_year.sum():>5}  ({m_year.mean():.1%})")
    print(f"Uten effekt (MW):     {m_effect.sum():>5}  ({m_effect.mean():.1%})")
    print(f"Uten koordinater:     {m_coords.sum():>5}  ({m_coords.mean():.1%})")
    print(f"Uten kommune:         {m_kommune.sum():>5}  ({m_kommune.mean():.1%})")
    print("-" * 40)
    print(f"Total installert effekt: {total_mw:,.2f} MW")
    print(f"Gjennomsnittlig effekt:  {avg_mw:,.2f} MW")
    print(f"Eldste driftsår:         {min_year}")
    print(f"Nyeste driftsår:         {max_year}")
    print("\nFordeling på status-kode:")
    print(df["status"].value_counts(dropna=False).to_string())
    print("-" * 40)
    print(f"Antall duplikate navn: {n_dup_names}")
    if n_dup_names:
        print("\nNavn som forekommer mer enn én gang:\n")
        print(dup_counts.to_string(header=False))


if __name__ == "__main__":
    main()
