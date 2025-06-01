#!/usr/bin/env python3
"""
Hent alle utbygde vindkraftverk fra NVE (Vindkraft2 – lag 0)
og lagre som:
  • vindkraftverk.jsonl   (én rad per linje, UTF-8)
  • vindkraftverk.csv     (samme innhold)

Kolonner:
  anleggNavn, anleggsNr, antallTurbiner,
  brukersattKonsesjonStatus, brukersattKonsesjonStatusDato,
  effekt_MW, effekt_MW_idrift, eier,
  forsteIdriftDato, forventetProduksjon_Gwh,
  fylkeNavn, kommune, saksID, stadium, status,
  domene, lat, lon
"""

from pathlib import Path
import csv, json, time, requests

# ────────────────────────────────────────────────────────────────────────
SERVICE = "https://nve.geodataonline.no/arcgis/rest/services/Vindkraft2/MapServer"
LAYER   = 0   # Vindkraft_utbygd (laget med ferdigbygde vindkraftverk)
URL     = f"{SERVICE}/{LAYER}/query"

# Feltene du ønsket å beholde (i denne rekkefølgen)
KEEP = [
    "anleggNavn",
    "anleggsNr",
    "antallTurbiner",
    "brukersattKonsesjonStatus",
    "brukersattKonsesjonStatusDato",
    "effekt_MW",
    "effekt_MW_idrift",
    "eier",
    "forsteIdriftDato",
    "forventetProduksjon_Gwh",
    "fylkeNavn",
    "kommune",
    "saksID",
    "stadium",
    "status",
]

# Permanente filnavn
OUT_JSONL = Path("vindkraftverk.jsonl")
OUT_CSV   = Path("vindkraftverk.csv")
# ────────────────────────────────────────────────────────────────────────

PARAMS_BASE = {
    "where": "1=1",               # ingen filtrering
    "outFields": "*",             # henter alle felt
    "returnGeometry": "true",     # trenger geometri for lat/lon
    "outSR": 4326,                # WGS84 (lat/lon)
    "f": "json",                  # JSON‐format
    "resultRecordCount": 1000,    # maks antall per kall
}

rows, offset = [], 0
while True:
    rsp = requests.get(URL, params=PARAMS_BASE | {"resultOffset": offset}, timeout=60)
    rsp.raise_for_status()
    data = rsp.json()
    if "error" in data:
        raise RuntimeError(data["error"])

    feats = data.get("features", [])
    for f in feats:
        a = f.get("attributes", {})

        # Bygg en ny dict med kun de valgte feltene
        row = {k: a.get(k) for k in KEEP}

        # Legg til domene
        row["domene"] = "Vindkraft"

        # Hent ut latitude/longitude fra geometry (punkt eller polygon)
        geom = f.get("geometry", {}) or {}
        if geom.get("x") is not None and geom.get("y") is not None:
            row["lon"] = geom["x"]
            row["lat"] = geom["y"]
        else:
            # Hvis det finnes et 'x','y'-par under polygoncentroid
            c = geom.get("centroid", {})
            row["lon"] = c.get("x")
            row["lat"] = c.get("y")

        rows.append(row)

    print(f"{offset:>6}  +{len(feats):>4}  →  {len(rows):>6} rader")

    # Hvis færre enn maksimal batch-størrelse returneres, er vi ferdige
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

print(f"\n✅  Ferdig! Lagret {len(rows)} vindkraftverk som {OUT_JSONL} og {OUT_CSV}")
