#!/usr/bin/env python3
"""
hent_felter_solkraft.py

Hent én batch med solkraftdata fra NVE (Solkraft – lag 0)
og print ut alle unike attributtnavn og geometrinøkler.
"""

import requests

# ─── ENDPOINT FOR SOLKRAFT (lag 0 = Solkraftomrade) :contentReference[oaicite:0]{index=0}
SERVICE = "https://nve.geodataonline.no/arcgis/rest/services/Solkraft/MapServer"
LAYER   = 0   # Solkraftomrade (lag 0)
URL     = f"{SERVICE}/{LAYER}/query"

PARAMS = {
    "where": "1=1",               # hent alle objekter
    "outFields": "*",             # alle attributter
    "returnGeometry": "true",     # inkludér geometri
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
