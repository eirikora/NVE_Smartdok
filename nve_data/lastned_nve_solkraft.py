#!/usr/bin/env python3
"""
Hent alle solkraftanlegg fra NVE (Solkraft – lag 0)
og lagre som:
  • solkraftverk.jsonl   (én rad per linje, UTF-8)
  • solkraftverk.csv     (samme innhold)

Kolonner:
  anleggNavn, anleggsNr, brukersattKonsesjonStatus, brukersattKonsesjonStatusDato,
  effekt_MW, effekt_MW_idrift, eier, forsteIdriftDato, forventetProduksjon_Gwh,
  fylkeNavn, kommune, status, saksID, stadium,
  domene, lat, lon
"""

from pathlib import Path
import csv, json, time, requests

# ────────────────────────────────────────────────────────────────────────
SERVICE = "https://nve.geodataonline.no/arcgis/rest/services/Solkraft/MapServer"
LAYER   = 0   # Solkraftomrade (lag 0 = alle registrerte solkraftanlegg)
URL     = f"{SERVICE}/{LAYER}/query"

# Feltene du ønsker å beholde (i denne rekkefølgen)
KEEP = [
    "anleggNavn",
    "anleggsNr",
    "brukersattKonsesjonStatus",
    "brukersattKonsesjonStatusDato",
    "effekt_MW",
    "effekt_MW_idrift",
    "eier",
    "forsteIdriftDato",
    "forventetProduksjon_Gwh",
    "fylkeNavn",
    "kommune",
    "status",
    "saksID",
    "stadium",
]

# Permanente filnavn
OUT_JSONL = Path("solkraftverk.jsonl")
OUT_CSV   = Path("solkraftverk.csv")
# ────────────────────────────────────────────────────────────────────────

PARAMS_BASE = {
    "where": "1=1",               # ingen filtrering
    "outFields": "*",             # henter alle tilgjengelige felt
    "returnGeometry": "true",     # vi trenger polygon‐geometri for lat/lon
    "outSR": 4326,                # WGS84 (lat/lon)
    "f": "json",
    "resultRecordCount": 1000,    # maks antall per kall
}


def compute_centroid_from_rings(rings):
    """
    Enkel centroid‐beregning for polygoner definert i 'rings'.
    Tar alle punkter i alle ytre ringer, regner gjennomsnittlig x,y.
    Hvis ingen gyldige punkter: returnerer (None, None).
    """
    total_x = 0.0
    total_y = 0.0
    count = 0
    for ring in rings or []:
        for point in ring or []:
            try:
                x, y = point[0], point[1]
                total_x += x
                total_y += y
                count += 1
            except (TypeError, IndexError):
                continue
    if count == 0:
        return None, None
    return (total_y / count, total_x / count)  # lat=y, lon=x


rows = []
offset = 0

while True:
    rsp = requests.get(URL, params=PARAMS_BASE | {"resultOffset": offset}, timeout=60)
    rsp.raise_for_status()
    data = rsp.json()
    if "error" in data:
        raise RuntimeError(data["error"])

    feats = data.get("features", [])
    for f in feats:
        a = f.get("attributes", {})

        # Bygg ny dict med kun ønskede attributter
        row = {k: a.get(k) for k in KEEP}

        # Legg til domene
        row["domene"] = "Solkraft"

        # Hent polygongeometri og regn ut centroid
        geom = f.get("geometry", {}) or {}
        rings = geom.get("rings")
        lat, lon = compute_centroid_from_rings(rings)
        row["lat"] = lat
        row["lon"] = lon

        rows.append(row)

    print(f"{offset:>6}  +{len(feats):>4}  →  {len(rows):>6} solkraftanlegg")
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

print(f"\n✅  Ferdig! Lagret {len(rows)} solkraftanlegg som {OUT_JSONL} og {OUT_CSV}")
