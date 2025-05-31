#!/usr/bin/env python3
"""
Aggreger strekninger_raw.jsonl til én rad pr. (elvId, elvenavn).
• Ingen splitting av elvenavnHierarki
• Lengste hierarki-streng + tilhørende vassdragsNr tas med
• Skriver bounding-box som UL/LR-hjørner (lat før lon)
"""
from __future__ import annotations
import json, csv, pathlib, collections

RAW_PATH = pathlib.Path("strekninger_raw.jsonl")
OUT_CSV  = pathlib.Path("elver_per_name.csv")
OUT_JSON = pathlib.Path("elver_per_name.json")

assert RAW_PATH.exists(), "Kjør først del 1 slik at strekninger_raw.jsonl finnes."

Agg = collections.namedtuple(
    "Agg",
    "length xmin xmax ymin ymax hierarki vnr"
)
elver: dict[tuple[str, str], Agg] = {}
print("Leser og aggregerer …")

with RAW_PATH.open(encoding="utf-8") as f:
    for line in f:
        feat = json.loads(line)
        a    = feat["attributes"]

        key  = (a["elvId"], a["elvenavn"].strip())

        xmin = ymin =  1e99
        xmax = ymax = -1e99
        for path in feat["geometry"]["paths"]:
            for x, y in path:
                xmin, xmax = min(xmin, x), max(xmax, x)
                ymin, ymax = min(ymin, y), max(ymax, y)

        lengde = a.get("lengde_m") or 0.0
        hier   = (a.get("elvenavnHierarki") or "").strip()
        vnr    = a.get("vassdragsNr") or ""

        if key not in elver:
            elver[key] = Agg(lengde, xmin, xmax, ymin, ymax, hier, vnr)
        else:
            e = elver[key]
            # lengste hierarki-streng «vinner»
            hier_sel, vnr_sel = (hier, vnr) if len(hier) > len(e.hierarki) else (e.hierarki, e.vnr)
            elver[key] = Agg(
                length   = e.length + lengde,
                xmin     = min(e.xmin, xmin),
                xmax     = max(e.xmax, xmax),
                ymin     = min(e.ymin, ymin),
                ymax     = max(e.ymax, ymax),
                hierarki = hier_sel,
                vnr      = vnr_sel
            )

print(f"✔ Aggregerte {len(elver):,} navngitte elver")

rows = []
for (eid, navn), e in elver.items():
    rows.append({
        "elvId"           : eid,
        "elvenavn"        : navn,
        "vassdragsNr"     : e.vnr,
        "total_lengde_m"  : round(e.length, 1),
        # bbox (lat før lon)
        "ul_lat"          : round(e.ymax, 6),
        "ul_lon"          : round(e.xmin, 6),
        "lr_lat"          : round(e.ymin, 6),
        "lr_lon"          : round(e.xmax, 6),
        # for evt. bruk senere
        "elvenavnHierarki": e.hierarki,
    })

field_order = [
    "elvenavn",
    "elvId",
    "elvenavnHierarki",
    "vassdragsNr",
    "total_lengde_m",
    "ul_lat", "ul_lon",
    "lr_lat", "lr_lon",
]

with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=field_order)
    w.writeheader()
    w.writerows(rows)

OUT_JSONL = pathlib.Path("elver_per_name.jsonl")
with OUT_JSONL.open("w", encoding="utf-8") as jf:
    for r in rows:
        jf.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"CSV : {OUT_CSV}  ({OUT_CSV.stat().st_size/1e6:.1f} MB)")
print(f"JSONL: {OUT_JSONL} ({OUT_JSONL.stat().st_size/1e6:.1f} MB)")
print("✅  Ferdig – én rad per unik elv med UL/LR-bbox og lat-før-lon-rekkefølge.")
