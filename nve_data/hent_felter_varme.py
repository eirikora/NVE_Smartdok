#!/usr/bin/env python3
"""
hent_felter_varme.py

Hent én eksempelbatch fra hvert lag (0–6) i Mapservices/Varme
og skriv ut unike attributtnavn og geometrinøkler.
"""

import requests

SERVICE = "https://nve.geodataonline.no/arcgis/rest/services/Mapservices/Varme/MapServer"
LAG_RANGE = range(0, 7)          # 0–6

PARAMS = {
    "where": "1=1",
    "outFields": "*",
    "returnGeometry": "true",
    "outSR": 4326,
    "f": "json",
    "resultRecordCount": 1,      # ett objekt er nok til å se feltene
}

for layer in LAG_RANGE:
    url = f"{SERVICE}/{layer}/query"
    try:
        rsp = requests.get(url, params=PARAMS, timeout=60)
        rsp.raise_for_status()
    except Exception as e:
        print(f"--- LAG {layer} FEILET ({e}) ---\n")
        continue

    data = rsp.json()
    if "error" in data:
        print(f"--- LAG {layer} GA FEILSVAR: {data['error']} ---\n")
        continue

    feats = data.get("features", [])
    if not feats:
        print(f"--- LAG {layer}: Ingen funksjoner returnert ---\n")
        continue

    attribs = feats[0].get("attributes", {}) or {}
    geom = feats[0].get("geometry", {}) or {}

    print(f"=== LAG {layer} ATTRIBUTTFELTNAVN ===")
    for k in sorted(attribs):
        print(k)
    print()
    print(f"=== LAG {layer} GEOMETRINØKLER ===")
    for k in sorted(geom):
        print(k)
    print("\n")
