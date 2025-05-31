#!/usr/bin/env python3
"""
Hent én batch med utbygde vindkraftverk fra NVE (Vindkraft2 – lag 0)
og print ut alle unike attributtnavn for å se hva tjenesten returnerer.
"""

import requests

SERVICE = "https://nve.geodataonline.no/arcgis/rest/services/Vindkraft2/MapServer"
LAYER   = 0
URL     = f"{SERVICE}/{LAYER}/query"

PARAMS = {
    "where": "1=1",
    "outFields": "*",          # henter alle attributter
    "returnGeometry": "true",  # inkluderer geometri‐objekt
    "outSR": 4326,
    "f": "json",
    "resultRecordCount": 1000, # kun én batch på maks 1000 objekter
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

# Samle alle unike attributtnøkler:
unike_attributter = set()
for f in features:
    attrib = f.get("attributes", {})
    unike_attributter.update(attrib.keys())

# Legg også til nøklene under 'geometry' (hvis du vil se geometri‐felter)
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
