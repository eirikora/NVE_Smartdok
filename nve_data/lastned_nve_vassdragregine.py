#!/usr/bin/env python3
"""
Last ned alle nivåer av vassdrag (lag 0–3) fra NVE Nedborfelt1,
inkludert geometrisenter (lat/lon), og lagre samlet som CSV + JSONL.
"""
import requests, json, csv, time
from pathlib import Path

SERVICE = "https://nve.geodataonline.no/arcgis/rest/services/Nedborfelt1/MapServer"
OUT_JSONL = Path("vassdrag_nedborfelt_all.jsonl")
OUT_CSV   = Path("vassdrag_nedborfelt_all.csv")

# Lagdefinisjoner
LAGS = {
    0: ("Hovednedbørfelt",
         ["VASSOMR", "NAVNVASSOMR", "AREAL_KM2", "LANDAREAL"]),
    1: ("Nedbørfelt",
         ["vassdragNr", "navnNedbf", "areal", "elvlengdKm", "tilsig"]),
    2: ("Delnedbørfelt",
         ["vassdragNr", "navn1orden", "areal", "elvlengdKm", "tilsig"]),
    3: ("REGINE_enhet",
         ["vassdragNr", "elvHierark", "lokalnavn", "nivaa", "arealEnh", "tilsigEnh"]),
}

all_rows = []  # <-- én felles liste for alle lag

for layer, (lagtype, felter) in LAGS.items():
    url = f"{SERVICE}/{layer}/query"
    print(f"\n=== Laster {lagtype} (lag {layer}) ===")

    meta = requests.get(f"{SERVICE}/{layer}?f=pjson", timeout=60).json()
    oid_field = meta.get("objectIdFieldName") or "OBJECTID"

    stats = requests.get(
        url,
        params={
            "where": "1=1",
            "outStatistics": json.dumps([
                {"statisticType": "min", "onStatisticField": oid_field, "outStatisticFieldName": "min_oid"},
                {"statisticType": "max", "onStatisticField": oid_field, "outStatisticFieldName": "max_oid"},
            ]),
            "f": "json",
        },
        timeout=60,
    ).json()
    ext = stats["features"][0]["attributes"]
    min_oid, max_oid = ext["min_oid"], ext["max_oid"]
    print(f"OID-range: {min_oid} → {max_oid}")

    batch = 800
    total = 0
    for start in range(min_oid, max_oid + 1, batch):
        end = start + batch - 1
        where = f"{oid_field} >= {start} AND {oid_field} <= {end}"

        params = {
            "where": where,
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": 4326,
            "geometryPrecision": 5,
            "f": "json",
        }

        try:
            r = requests.get(url, params=params, timeout=180)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"⚠️  Feil for lag {layer}, OID {start}-{end}: {e}")
            continue

        feats = data.get("features", [])
        if not feats:
            continue

        for f in feats:
            a = f["attributes"]
            geom = f.get("geometry", {})
            lat = lon = None
            if "rings" in geom:
                xs, ys = zip(*[pt for ring in geom["rings"] for pt in ring])
                lon = (min(xs) + max(xs)) / 2
                lat = (min(ys) + max(ys)) / 2

            row = {fld: a.get(fld) for fld in felter}
            row["center_lat"] = lat
            row["center_lon"] = lon
            row["lagtype"] = lagtype
            row["domene"] = "Vassdrag (REGINE)"
            all_rows.append(row)

        total += len(feats)
        print(f"  {end:>8} → {total:>6} ({lagtype})")
        time.sleep(0.3)

print(f"\nTotalt hentet {len(all_rows)} vassdrag fra lag 0–3")

# ── lagre samlet ───────────────────────────────────────────────
OUT_JSONL.write_text(
    "\n".join(json.dumps(r, ensure_ascii=False) for r in all_rows),
    encoding="utf-8"
)

all_fields = sorted({k for r in all_rows for k in r.keys()})
with OUT_CSV.open("w", newline="", encoding="utf-8") as cf:
    w = csv.DictWriter(cf, fieldnames=all_fields)
    w.writeheader()
    w.writerows(all_rows)

print(f"✅ Ferdig! Lagret {len(all_rows)} rader i {OUT_JSONL} og {OUT_CSV}")
