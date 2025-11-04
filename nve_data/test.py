#!/usr/bin/env python3
"""
Skriv ut faktiske feltnavn og eksempler fra lag 0 (Hovednedbørfelt)
i NVE Nedborfelt1-tjenesten.
"""
import requests, json

URL = "https://nve.geodataonline.no/arcgis/rest/services/Nedborfelt1/MapServer/0/query"

# hent noen få rader med alle felter
r = requests.get(
    URL,
    params={
        "where": "1=1",
        "outFields": "*",
        "returnGeometry": "false",
        "resultRecordCount": 5,
        "f": "json",
    },
    timeout=60,
)
r.raise_for_status()
data = r.json()

print(f"Fant {len(data.get('features', []))} eksempler\n")
for i, feat in enumerate(data.get("features", []), 1):
    print(f"Feature {i}")
    for k, v in feat["attributes"].items():
        print(f"  {k:<25} {v!r}")
    print()
