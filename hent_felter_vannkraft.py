#!/usr/bin/env python3
"""
Hent én batch med vannkraftverk fra NVE (Vannkraft1 – lag 0)
og print ut alle unike attributtnavn og geometrinøkler,
slik at du kan se hvilke felt som returneres.
"""

import requests

SERVICE = "https://nve.geodataonline.no/arcgis/rest/services/Vannkraft1/MapServer"
LAYER   = 0   # Vannkraftverk‐lag 0 (utbygde vannkraftverk)
URL     = f"{SERVICE}/{LAYER}/query"

PARAMS = {
    "where": "1=1",               # ingen begrensning
    "outFields": "*",             # hent alle felt
    "returnGeometry": "true",     # inkluder også geometri‐objekt
    "outSR": 4326,                # WGS84 (lat/lon)
    "f": "json",                  # få JSON‐respons
    "resultRecordCount": 1000,    # én batch på opptil 1000 objekter
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

# Samle alle unike felt-nøkler under "attributes"
unike_attributter = set()
for f in features:
    attrib = f.get("attributes", {}) or {}
    unike_attributter.update(attrib.keys())

# Samle alle unike nøkkel‐navn under "geometry"
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
