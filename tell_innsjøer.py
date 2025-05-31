#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Statistikk for innsjø-attributter
---------------------------------
• Antall innsjøer
• Uten navn (%)
• Uten høyde (%)
• Uten areal (%)
• Uten kommune (%)
"""

import json
import pandas as pd
from pathlib import Path

DATAFIL = Path("innsjo_attr.json")


def load_data(path: Path) -> pd.DataFrame:
    """Les JSON-filen og returnér som DataFrame.

    Forventet format er en *liste* med objekter, f.eks.
    [
        {"vatnLnr": 3577, ...},
        {"vatnLnr": 66750, ...}
    ]
    """
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return pd.DataFrame(data)


def main() -> None:
    df = load_data(DATAFIL)

    total = len(df)

    # Sett opp «mangler»-masker
    m_name = df["navn"].isna() | (df["navn"].astype(str).str.strip() == "")
    m_hoyde = df["hoyde"].isna()
    m_areal = df["areal_km2"].isna()
    m_kommune = df["kommune"].isna() | (df["kommune"].astype(str).str.strip() == "")

    # Utskrift
    print(f"Antall innsjøer: {total}")
    print(f"Uten navn:      {m_name.sum():>6}  ({m_name.mean():.1%})")
    print(f"Uten høyde:     {m_hoyde.sum():>6}  ({m_hoyde.mean():.1%})")
    print(f"Uten areal:     {m_areal.sum():>6}  ({m_areal.mean():.1%})")
    print(f"Uten kommune:   {m_kommune.sum():>6}  ({m_kommune.mean():.1%})")


if __name__ == "__main__":
    main()
