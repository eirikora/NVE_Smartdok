#!/usr/bin/env python3
"""
Hent alle vannkraftverk fra NVE (Vannkraft1 – lag 0)
og lagre som:
  • vannkraftverk.jsonl   (én rad per linje, UTF-8)
  • vannkraftverk.csv     (samme innhold)

Kolonner:
  vannkraftverkNr, vannkraftverkNavn, kommunenummer, kommuneNavn, fylke,
  konsesjonStatus, status, idriftsattAar,
  maksYtelse_MW, midlereProduksjon_GWh, bruttoFallhoyde_m,
  domene, lat, lon
"""

from pathlib import Path
import csv, json, time, requests

# ────────────────────────────────────────────────────────────────────────
SERVICE = "https://nve.geodataonline.no/arcgis/rest/services/Vannkraft1/MapServer"
LAYER   = 0
URL     = f"{SERVICE}/{LAYER}/query"

# Feltene vi vil TA MED i de ferdige filene (rekkefølgen bevares)
KEEP = [
    "vannkraftverkNr", "vannkraftverkNavn",
    "kommunenummer", "kommuneNavn", "fylke",
    "konsesjonStatus", "status",
    "idriftsattAar",
    "maksYtelse_MW",            # finnes, men er ofte 0 – behold likevel
    "midlereProduksjon_GWh",
    "bruttoFallhoyde_m",
]

# permanente filnavn
OUT_JSONL = Path("vannkraftverk.jsonl")
OUT_CSV   = Path("vannkraftverk.csv")
# ────────────────────────────────────────────────────────────────────────

PARAMS_BASE = {
    "where": "1=1",
    "outFields": "*",           # <- sikker mot stavefeil
    "returnGeometry": "true",
    "outSR": 4326,              # lat/lon
    "f": "json",
    "resultRecordCount": 1000,
}

rows, offset = [], 0
while True:
    rsp = requests.get(URL, params=PARAMS_BASE | {"resultOffset": offset},
                       timeout=60)
    rsp.raise_for_status()
    data = rsp.json()
    if "error" in data:
        raise RuntimeError(data["error"])

    feats = data["features"]
    for f in feats:
        a = f["attributes"]
        # bygg ny dict med bare ønskede felt (empty hvis mangler)
        row = {k: a.get(k) for k in KEEP}
        row["domene"] = "Vannkraft"
        row["lat"] = f["geometry"]["y"]
        row["lon"] = f["geometry"]["x"]
        rows.append(row)

    print(f"{offset:>6}  +{len(feats):>4}  →  {len(rows):>6} kraftverk")
    if len(feats) < PARAMS_BASE["resultRecordCount"]:
        break
    offset += PARAMS_BASE["resultRecordCount"]
    time.sleep(0.25)

# ── Lagre JSON Lines ────────────────────────────────────────────────────
with OUT_JSONL.open("w", encoding="utf-8") as jf:
    for r in rows:
        jf.write(json.dumps(r, ensure_ascii=False) + "\n")

# ── Lagre CSV ───────────────────────────────────────────────────────────
field_order = KEEP + ["domene", "lat", "lon"]
with OUT_CSV.open("w", newline="", encoding="utf-8") as cf:
    w = csv.DictWriter(cf, fieldnames=field_order)
    w.writeheader()
    w.writerows(rows)

print(f"\n✅  Ferdig! Lagret {len(rows)} kraftverk som {OUT_JSONL} og {OUT_CSV}")
