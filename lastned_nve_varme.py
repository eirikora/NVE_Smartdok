#!/usr/bin/env python3
"""
Last ned alle aktuelle lag (1–6) fra NVE «Varme» og lagre hvert lag som
 • varme_lag{N}.jsonl
 • varme_lag{N}.csv

Lag 0 gir 400-feil – hoppes over.
"""

from pathlib import Path
import csv, json, time, requests

BASE = "https://nve.geodataonline.no/arcgis/rest/services/Mapservices/Varme/MapServer"

# ─── Hvilke felter vi vil beholde fra hvert lag ──────────────────────────
KEEP = {
    1: ["anlegg", "eier", "kommune"],
    2: ["aktor", "dagensInstallerteEffekt_MW", "navn", "sted", "typeSenter"],
    3: ["navn", "eier", "kapasitet"],
    4: ["Anlegg", "Kommune", "Selskap", "Summert"],
    5: ["Anlegg", "Kommune", "Selskap", "Summert"],
    6: ["Anlegg", "Kommune", "Selskap", "Summert"],
}

# lag-beskrivelse legges i filnavnet og i domene-feltet
DESCR = {
    1: "industri",
    2: "datasenter",
    3: "avfallsforbrenning",
    4: "fjernvarme_konsesjon",
    5: "fjernvarme_effekt",
    6: "fjernvarme_produksjon",
}

PARAMS = {
    "where": "1=1",
    "outFields": "*",
    "returnGeometry": "true",
    "outSR": 4326,
    "f": "json",
    "resultRecordCount": 1000,
}

def centroid_from_rings(rings):
    """Grov centroid av polygon(rings) → lat, lon (None,None hvis tom)."""
    sx = sy = n = 0
    for ring in rings or []:
        for x, y, *_ in ring:
            sx += x
            sy += y
            n += 1
    return (sy / n, sx / n) if n else (None, None)

for layer in range(1, 7):               # lag 1–6
    url = f"{BASE}/{layer}/query"
    keep = KEEP[layer]
    desc = DESCR[layer]

    rows, offset = [], 0
    while True:
        rsp = requests.get(url, params=PARAMS | {"resultOffset": offset}, timeout=60)
        try:
            rsp.raise_for_status()
        except Exception as e:
            print(f"⚠️  Lag {layer}: HTTP-feil {e}; hopper over dette laget.")
            rows = []
            break

        data = rsp.json()
        if "error" in data:
            print(f"⚠️  Lag {layer}: {data['error']}; hopper over.")
            rows = []
            break

        feats = data.get("features", [])
        for f in feats:
            a = f.get("attributes", {})

            row = {k: a.get(k) for k in keep}  # ønskede felter
            row["domene"] = f"Varme_{desc}"    # domene for sporbarhet

            geom = f.get("geometry", {}) or {}
            if "x" in geom and "y" in geom:    # punktlag
                row["lat"], row["lon"] = geom["y"], geom["x"]
            else:                              # polygon – beregn centroid
                row["lat"], row["lon"] = centroid_from_rings(geom.get("rings"))

            rows.append(row)

        print(f" Lag {layer} – offset {offset:>5}  +{len(feats):>4}  →  {len(rows)}")

        if len(feats) < PARAMS["resultRecordCount"]:
            break
        offset += PARAMS["resultRecordCount"]
        time.sleep(0.25)

    # hopp over lag som feilet
    if not rows:
        continue

    # ── Skriv filer ────────────────────────────────────────────────────
    stem = f"varme_lag{layer}_{desc}"
    out_jsonl = Path(f"{stem}.jsonl")
    out_csv   = Path(f"{stem}.csv")

    with out_jsonl.open("w", encoding="utf-8") as jf:
        for r in rows:
            jf.write(json.dumps(r, ensure_ascii=False) + "\n")

    field_order = keep + ["domene", "lat", "lon"]
    with out_csv.open("w", newline="", encoding="utf-8") as cf:
        w = csv.DictWriter(cf, fieldnames=field_order)
        w.writeheader()
        w.writerows(rows)

    print(f"✅  Lag {layer}: lagret {len(rows)} rader til {out_jsonl} / {out_csv}\n")
