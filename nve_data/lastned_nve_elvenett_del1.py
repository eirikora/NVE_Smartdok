#!/usr/bin/env python3
"""
Del 1 – last ned *alle* navngitte elve-/bekkestrekninger fra NVE ELVIS
(lag 2 «elvenett») på en måte som tåler nett-hikke og kan gjenopptas.

✔   én strekning per linje i strekninger_raw.jsonl  (JSON Lines)
✔   progress.json holder neste offset så skriptet kan fortsette
✔   automatisk retry på time-outs / 5xx-feil
"""

from __future__ import annotations
import json, time, pathlib, requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ────────────────────────────────────────────────────────────────────────────
# KONFIGURASJON

SERVICE = (
    "https://nve.geodataonline.no/arcgis/rest/services/"
    "Elvenett1/MapServer/2/query"
)

BATCH      = 1000                           # maks tillatt av serveren
OUT_RAW    = pathlib.Path("strekninger_raw.jsonl")
OUT_PROG   = pathlib.Path("progress.json")

FIELDS = [
    "elvId",
    "elvenavn",
    "elvenavnHierarki",
    "vassdragsNr",
    "lengde_m",
]

BASE_PARAMS = {
    # hent KUN strekn. som faktisk har navn
    "where"             : "elvenavn IS NOT NULL AND elvenavn <> ''",
    "outFields"         : ",".join(FIELDS),
    "returnGeometry"    : "true",      # trengs for bbox i del 2
    "outSR"             : 4326,        # lat/lon
    "geometryPrecision" : 5,           # færre desimaler => mindre trafikk
    "f"                 : "json",
    "resultRecordCount" : BATCH,
}

# ────────────────────────────────────────────────────────────────────────────
# HTTP-sesjon med retry

retry_cfg = Retry(
    total=5,                       # 5 nye forsøk
    backoff_factor=1.5,            # 1.5 s → 3 s → 4.5 s …
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=["GET"],
)
ses = requests.Session()
ses.mount("https://", HTTPAdapter(max_retries=retry_cfg))

# ────────────────────────────────────────────────────────────────────────────
# GJENOPPTAK – finn start-offset

if OUT_PROG.exists():
    state   = json.loads(OUT_PROG.read_text())
    offset  = state.get("offset", 0)
    written = state.get("written", 0)
else:
    offset = written = 0

raw_f = OUT_RAW.open("a", encoding="utf-8")

print("Starter nedlasting … (Ctrl-C trygt; kjør igjen for å fortsette)")

# ────────────────────────────────────────────────────────────────────────────
# HOVEDLØKKE: last ned helt til serveren returnerer tom batch

while True:
    try:
        r = ses.get(
            SERVICE,
            params={**BASE_PARAMS, "resultOffset": offset},
            timeout=(10, 180),       # 10 s connect, 180 s read
        )
        r.raise_for_status()
        feats = r.json()["features"]
    except Exception as exc:
        print(f"[{offset}]  🚨  {exc} – prøver om 30 s …")
        time.sleep(30)
        continue                    # samme offset på nytt forsøk

    if not feats:                   # tom batch ⇒ alt er hentet
        break

    for f in feats:
        raw_f.write(json.dumps(f, ensure_ascii=False) + "\n")
    written += len(feats)
    offset  += BATCH

    OUT_PROG.write_text(json.dumps({"offset": offset, "written": written}))
    print(f"{offset:>7}  +{len(feats):>4}  ==>  {written:>7} strekn. lagret")
    time.sleep(0.25)                # litt høflig pusterom

raw_f.close()
OUT_PROG.unlink(missing_ok=True)     # ferdig, progress-filen trengs ikke lenger
print("\n✅  Nedlasting fullført!")
print(f"   • {written:,} strekninger i {OUT_RAW}")
