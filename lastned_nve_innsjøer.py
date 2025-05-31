#!/usr/bin/env python3
"""
Last ned alle innsjø- og magasinobjekter fra NVE.
Robust mot manglende 'centroid' og sikrer at OBJECTID alltid er tilgjengelig.
"""

from __future__ import annotations
import csv, json, sys, time
from pathlib import Path
from typing import List, Dict

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SERVICE = ("https://nve.geodataonline.no/arcgis/rest/services/"
           "Innsjodatabase2/MapServer/5/query")
BATCH = 1000
TIMEOUT = (10, 180)
PAUSE = 0.25

FIELDS: List[str] = [
    "vatnLnr", "navn", "kommNr", "kommune",
    "hoyde", "areal_km2",
    "objektType", "magasinNr"
]

JSONL = Path("innsjoe_full.jsonl")
CSV   = Path("innsjoe_full.csv")
OIDS  = Path("resume_oid.txt")


def make_session(retries=5, backoff=1.0) -> requests.Session:
    retry = Retry(total=retries, backoff_factor=backoff,
                  status_forcelist=(500, 502, 503, 504),
                  allowed_methods={"GET"})
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": "NVE-innsjoe-downloader/2.1"})
    return s


session = make_session()


def get_layer_meta() -> dict:
    r = session.get(SERVICE.rsplit("/", 1)[0], params={"f": "json"},
                    timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def resolve_oid_field(meta: dict) -> str:
    return (meta.get("objectIdField") or
            meta.get("objectIdFieldName") or
            next(f["name"] for f in meta["fields"]
                 if f["type"] == "esriFieldTypeOID"))


def get_total_count() -> int:
    r = session.get(
        SERVICE,
        params={"where": "1=1", "returnCountOnly": "true", "f": "json"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["count"]


def load_resume_oid() -> int:
    try:
        return int(OIDS.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def save_resume_oid(oid: int) -> None:
    OIDS.write_text(str(oid))


def already_downloaded() -> set[int]:
    ids = set()
    if JSONL.exists():
        with JSONL.open(encoding="utf-8") as f:
            for line in f:
                try:
                    ids.add(json.loads(line)["vatnLnr"])
                except Exception:
                    pass
    return ids


def centroid_from_geometry(geom: dict) -> tuple[float, float] | None:
    if not geom:
        return None
    if "x" in geom and "y" in geom:          # punkt
        return geom["y"], geom["x"]
    if "rings" in geom:                      # polygon
        xmin = ymin = float("inf")
        xmax = ymax = -float("inf")
        for ring in geom["rings"]:
            for x, y in ring:
                xmin, xmax = min(xmin, x), max(xmax, x)
                ymin, ymax = min(ymin, y), max(ymax, y)
        return (ymin + ymax) / 2, (xmin + xmax) / 2
    return None


def query_next_batch(oid_field: str, last_oid: int) -> List[dict]:
    out_fields = FIELDS + [oid_field] if oid_field not in FIELDS else FIELDS
    params = {
        "where": f"{oid_field}>{last_oid}",
        "outFields": ",".join(out_fields),
        "orderByFields": f"{oid_field} ASC",
        "returnGeometry": "true",
        "geometryPrecision": 5,
        "outSR": 4326,
        "resultRecordCount": BATCH,
        "f": "json",
    }
    r = session.get(SERVICE, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["features"]


def write_csv_row(row: Dict, first: bool) -> None:
    mode = "a" if CSV.exists() else "w"
    with CSV.open(mode, newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=row.keys())
        if first:
            w.writeheader()
        w.writerow(row)


def main() -> None:
    meta = get_layer_meta()
    oid_field = resolve_oid_field(meta)
    total = get_total_count()
    print(f"ℹ️  OID-felt er «{oid_field}»")
    print(f"ℹ️  API melder om {total:,} objekter totalt")

    seen = already_downloaded()
    print(f"🔄  Fant {len(seen):,} innsjøer fra før – fortsetter …")

    last_oid = load_resume_oid()
    first_csv = not CSV.exists()

    while True:
        feats = query_next_batch(oid_field, last_oid)
        if not feats:
            break

        buffer: List[str] = []

        for feat in feats:
            attr = feat["attributes"]
            if attr["vatnLnr"] in seen:
                last_oid = attr.get(oid_field, last_oid)
                continue

            # -- koordinater --
            if "centroid" in feat:
                lat, lon = feat["centroid"]["y"], feat["centroid"]["x"]
            else:
                res = centroid_from_geometry(feat.get("geometry"))
                if res is None:
                    continue
                lat, lon = res
            # -----------------

            attr |= {"center_lat": lat, "center_lon": lon}

            oid_val = attr.pop(oid_field, None)   # fjern før skriving
            if oid_val is not None:
                last_oid = oid_val

            seen.add(attr["vatnLnr"])
            buffer.append(json.dumps(attr, ensure_ascii=False) + "\n")
            write_csv_row(attr, first_csv)
            first_csv = False

        with JSONL.open("a", encoding="utf-8") as jf:
            jf.writelines(buffer)

        save_resume_oid(last_oid)
        print(f"{last_oid:>9} OID → +{len(buffer):4} "
              f"({len(seen):,}/{total:,})")
        time.sleep(PAUSE)

        if len(seen) >= total:
            break

    if len(seen) >= total:
        print(f"\n✅  Alle {total:,} objekter lastet ned.")
    else:
        print(f"\n⚠️  Avsluttet før fullført – har {len(seen):,} av "
              f"{total:,}.  Kjør igjen for å fortsette.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\n⏹️  Avbrutt av bruker.")
