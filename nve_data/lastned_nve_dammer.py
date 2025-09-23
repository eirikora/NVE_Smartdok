#!/usr/bin/env python3
"""
Last ned alle dam-objekter fra NVE Vannkraft1-tjenesten.
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
           "Vannkraft1/MapServer/5/query")  # Dam layer (layer 5)
BATCH = 100
TIMEOUT = (10, 180)
PAUSE = 0.25

FIELDS: List[str] = [
    "damNr", "damNavn", "objektType", "damKategori", "damFunksjon",
    "damHovedType", "status", "kommunenummer", "kommuneNavn", "fylke",
    "vassdragsNr", "idriftsattAar", "volumOppdemt_Mm3", "hohDamTopp",
    "damAnsvarlig", "vannkraftverkNavn", "vannkraftverkNr", "konsesjonStatus",
    "magasinNr", "magasinNavn"
]

JSONL = Path("dammer.jsonl")
CSV   = Path("dammer.csv")
OIDS  = Path("resume_dam_oid.txt")


def make_session(retries=5, backoff=1.0) -> requests.Session:
    retry = Retry(total=retries, backoff_factor=backoff,
                  status_forcelist=(500, 502, 503, 504),
                  allowed_methods={"GET"})
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": "NVE-dam-downloader/1.0"})
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
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:  # Skip empty lines
                    continue
                try:
                    data = json.loads(line)
                    dam_nr = data.get("damNr")
                    if dam_nr is not None:
                        ids.add(dam_nr)
                except Exception as e:
                    print(f"Warning: Could not parse line {line_num} in {JSONL}: {e}")
    return ids


def centroid_from_geometry(geom: dict) -> tuple[float, float] | None:
    if not geom:
        return None
    if "x" in geom and "y" in geom:          # punkt
        return geom["y"], geom["x"]
    if "paths" in geom:                      # line (polyline)
        xmin = ymin = float("inf")
        xmax = ymax = -float("inf")
        for path in geom["paths"]:
            for x, y in path:
                xmin, xmax = min(xmin, x), max(xmax, x)
                ymin, ymax = min(ymin, y), max(ymax, y)
        return (ymin + ymax) / 2, (xmin + xmax) / 2
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

    # Debug: print query details for first few calls
    # print(f"DEBUG: Querying {oid_field}>{last_oid}, expecting up to {BATCH} records")

    r = session.get(SERVICE, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    response_data = r.json()

    # Debug: print response if features is missing
    if "features" not in response_data:
        print(f"DEBUG: Unexpected API response: {response_data}")
        if "error" in response_data:
            print(f"API Error: {response_data['error']}")
        return []

    features = response_data["features"]
    # print(f"DEBUG: Got {len(features)} features, OID range: {features[0]['attributes'].get(oid_field) if features else 'N/A'} - {features[-1]['attributes'].get(oid_field) if features else 'N/A'}")

    return features


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
    print(f"ℹ️  API melder om {total:,} dammer totalt")

    seen = already_downloaded()
    print(f"🔄  Fant {len(seen):,} dammer fra før – fortsetter …")
    if len(seen) > 0 and len(seen) < 20:
        print(f"DEBUG: Existing damNr values: {sorted(seen)}")

    last_oid = load_resume_oid()
    first_csv = not CSV.exists()

    while True:
        feats = query_next_batch(oid_field, last_oid)
        if not feats:
            print("No more features returned, ending download.")
            break

        buffer: List[str] = []
        processed_count = 0

        # if last_oid < 20:
        #     print(f"DEBUG: Processing {len(feats)} features, seen set has {len(seen)} items")

        for feat in feats:
            attr = feat["attributes"]
            # Handle missing damNr field gracefully
            dam_nr = attr.get("damNr")
            if dam_nr is None:
                if last_oid < 20:  # Only debug first few
                    print(f"Warning: damNr missing in feature OID {attr.get('OBJECTID')}")
                continue
            if dam_nr in seen:
                if last_oid < 20:  # Only debug first few
                    print(f"DEBUG: Skipping damNr {dam_nr} - already seen")
                last_oid = attr.get(oid_field, last_oid)
                continue

            # -- koordinater --
            if "centroid" in feat:
                lat, lon = feat["centroid"]["y"], feat["centroid"]["x"]
            else:
                res = centroid_from_geometry(feat.get("geometry"))
                if res is None:
                    if last_oid < 20:
                        print(f"DEBUG: No coordinates for damNr {dam_nr}, skipping")
                    continue
                lat, lon = res
            # -----------------

            attr |= {"lat": lat, "lon": lon}

            oid_val = attr.pop(oid_field, None)   # fjern før skriving
            if oid_val is not None:
                last_oid = oid_val

            seen.add(dam_nr)
            buffer.append(json.dumps(attr, ensure_ascii=False) + "\n")
            write_csv_row(attr, first_csv)
            first_csv = False
            processed_count += 1

        with JSONL.open("a", encoding="utf-8") as jf:
            jf.writelines(buffer)

        # Always update last_oid to avoid infinite loops
        if feats:
            max_oid_in_batch = max(feat["attributes"].get(oid_field, 0) for feat in feats)
            if max_oid_in_batch > last_oid:
                last_oid = max_oid_in_batch

        save_resume_oid(last_oid)
        print(f"{last_oid:>9} OID → +{len(buffer):4} processed:{processed_count:4} "
              f"({len(seen):,}/{total:,})")
        time.sleep(PAUSE)

        # Break if no new records processed to avoid infinite loops
        if processed_count == 0 and len(feats) > 0:
            print("No new records processed but features returned. Possible duplicate handling issue.")
            break

        if len(seen) >= total:
            break

    if len(seen) >= total:
        print(f"\n✅  Alle {total:,} dammer lastet ned.")
    else:
        print(f"\n⚠️  Avsluttet før fullført – har {len(seen):,} av "
              f"{total:,}.  Kjør igjen for å fortsette.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\n⏹️  Avbrutt av bruker.")