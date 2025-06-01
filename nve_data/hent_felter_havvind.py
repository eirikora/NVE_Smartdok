#!/usr/bin/env python3
"""
hent_felter_havvind.py

Hent én batch med utredningsområder for bunnfaste havvindanlegg (Havvind – lag 1)
og print ut alle unike attributtnavn og geometrinøkler,
slik at du kan se hvilke felt som returneres.
"""

import requests

# ─── ENDPOINT FOR HAVVIND (lag 1 = Utredningsomrader_for_bunnfaste_vindkraftanlegg) :contentReference[oaicite:0]{index=0}
SERVICE = "https://nve.geodataonline.no/arcgis/rest/services/Havvind/MapServer"
LAYER   = 1   # Utredningsomrader_for_bunnfaste_vindkraftanlegg
URL     = f"{SERVICE}/{LAYER}/query"

PARAMS = {
    "where": "1=1",               # hent alle objekter
    "outFields": "*",             # alle attributter
    "returnGeometry": "true",     # inkludér geometri‐objekt
    "outSR": 4326,                # WGS84-lat/lon
    "f": "json",                  # JSON-respons
    "resultRecordCount": 1000,    # maks 1000 objekter én gang
}

resp = requests.get(URL, params=PARAMS, timeout=60)
resp.raise_for_status()
data = resp.json()
if "error" in data:
    raise RuntimeError(data["error"])

features = data.get("features", [])
if not features:
    print("Ingen funksjoner returnert.")
    exit(0)

# Samle alle unike feltnøkler fra "attributes"
unike_attributter = set()
for f in features:
    attrib = f.get("attributes", {}) or {}
    unike_attributter.update(attrib.keys())

# Samle alle unike nøkkelnavn fra "geometry"
geometri_nokler = set()
for f in features:
    geom = f.get("geometry", {}) or {}
    geometri_nokler.update(geom.keys())

print("=== UNIKE ATTRIBUTTFELTNAVN (attributes) ===")
for k in sorted(unike_attributter):
    print(k)
print()
print("=== GEOMETRINØKLER (geometry) ===")
for k in sorted(geometri_nokler):
    print(k)
