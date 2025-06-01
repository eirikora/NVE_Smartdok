#!/usr/bin/env python3
import argparse
import pathlib
import os
import sys
import json
import re
import math
from collections import defaultdict

# --- Globale datastrukturer for NVE-data ---
NVE_DATA = {
    "elver": [],
    "innsjoer": [],
    "vannkraftverk": [],
    "solkraftverk": [],
    "vindkraftverk": [],
    # ... (legg til andre typer hvis de skal brukes aktivt)
}

KOMMUNE_COORDS = {} # { "kommunenavn_lower": {"lat": float, "lon": float, "count": int} }

# --- Hjelpefunksjoner ---

def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance in kilometers between two points
    on the earth (specified in decimal degrees).
    """
    if None in [lat1, lon1, lat2, lon2]:
        return float('inf') # Kan ikke beregne avstand hvis data mangler
    # Convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of earth in kilometers.
    return c * r

def calculate_centerpoint(ul_lat_str, ul_lon_str, lr_lat_str, lr_lon_str):
    """
    Beregner senterpunktet for en bounding box gitt som strenger.
    Returnerer (center_lat, center_lon) eller (None, None) ved feil.
    """
    try:
        ul_lat, ul_lon = float(ul_lat_str), float(ul_lon_str)
        lr_lat, lr_lon = float(lr_lat_str), float(lr_lon_str)
        
        # Enkel validering av bbox-koordinater
        if not (-90 <= ul_lat <= 90 and -180 <= ul_lon <= 180 and \
                -90 <= lr_lat <= 90 and -180 <= lr_lon <= 180):
            return None, None

        center_lat = (ul_lat + lr_lat) / 2
        center_lon = (ul_lon + lr_lon) / 2
        return center_lat, center_lon
    except (ValueError, TypeError, AttributeError):
        return None, None


def load_jsonl(file_path, entity_type=None): # Lagt til entity_type
    """Laster en JSONL-fil og returnerer en liste med dictionaries."""
    data = []
    if not file_path.is_file():
        print(f"Advarsel: Datafilen {file_path} ble ikke funnet.", file=sys.stderr)
        return data
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                item = json.loads(line)
                if entity_type == "elver":
                    # Beregn og legg til senterpunkt for elver
                    ul_lat = item.get("ul_lat")
                    ul_lon = item.get("ul_lon")
                    lr_lat = item.get("lr_lat")
                    lr_lon = item.get("lr_lon")
                    center_lat, center_lon = calculate_centerpoint(ul_lat, ul_lon, lr_lat, lr_lon)
                    item["center_lat"] = center_lat
                    item["center_lon"] = center_lon
                    if center_lat is None:
                        # print(f"Advarsel: Kunne ikke beregne senterpunkt for elv på linje {line_num} i {file_path}: {item.get('elvenavn')}", file=sys.stderr)
                        pass


                data.append(item)
            except json.JSONDecodeError as e:
                print(f"Feil ved parsing av JSON i {file_path} på linje {line_num}: {e} -> {line.strip()}", file=sys.stderr)
    return data

def build_kommune_coords_from_nve_data():
    """
    Bygger en enkel lookup for kommunekoordinater basert på gjennomsnittet
    av koordinatene til anlegg i NVE-dataene.
    """
    print("Bygger kommunekoordinat-database...", file=sys.stderr)
    datasets_with_kommune_geo = [
        (NVE_DATA["innsjoer"], "kommune", "center_lat", "center_lon"),
        (NVE_DATA["vannkraftverk"], "kommuneNavn", "lat", "lon"),
        (NVE_DATA["solkraftverk"], "kommune", "lat", "lon"),
        (NVE_DATA["vindkraftverk"], "kommune", "lat", "lon"),
        (NVE_DATA["elver"], "vassdragsNr", "center_lat", "center_lon") # Bruker elvers senterpunkt
    ]

    temp_kommune_data = defaultdict(lambda: {"lat_sum": 0, "lon_sum": 0, "count": 0})

    for dataset, kommune_key, lat_key, lon_key in datasets_with_kommune_geo:
        for item in dataset:
            # For elver, kan kommuneinfo mangle direkte. Vi kan prøve å utlede det fra vassdragsNr hvis nødvendig,
            # eller bare bruke de andre datasettene som har klarere kommuneinfo for å bygge kommunekoordinater.
            # Her fokuserer vi på å bruke koordinatene fra entiteter som *har* kommunenavn.
            kommune_navn_raw = item.get(kommune_key)
            
            # For elver er 'kommune_key' satt til 'vassdragsNr'. Vi trenger å mappe dette til kommunenavn,
            # ELLER vi stoler på at de andre datasettene gir god nok dekning for kommunekoordinater.
            # For nå, la oss anta at vi primært bygger på de andre datasettene for kommune-til-kordinat mapping.
            # Vi kan forbedre dette hvis nødvendig ved å koble vassdragsNr til kommuner.
            
            if entity_type_from_dataset(dataset) != "elver" and not kommune_navn_raw:
                continue # Skip if not an elv and kommune name is missing

            kommune_navn_list = []
            if isinstance(kommune_navn_raw, list):
                kommune_navn_list = [str(kn).lower().strip() for kn in kommune_navn_raw]
            elif isinstance(kommune_navn_raw, str):
                kommune_navn_list = [kommune_navn_raw.lower().strip()]
            
            if not kommune_navn_list and entity_type_from_dataset(dataset) == "elver":
                # For elver uten direkte kommune, kan vi prøve en annen strategi om nødvendig,
                # men foreløpig bygger vi KOMMUNE_COORDS fra anlegg med klar kommune.
                continue


            lat_str = item.get(lat_key)
            lon_str = item.get(lon_key)

            if lat_str is not None and lon_str is not None:
                try:
                    lat = float(lat_str)
                    lon = float(lon_str)
                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        for kn_lower in kommune_navn_list:
                            if kn_lower: # Ignorer tomme kommunenavn
                                temp_kommune_data[kn_lower]["lat_sum"] += lat
                                temp_kommune_data[kn_lower]["lon_sum"] += lon
                                temp_kommune_data[kn_lower]["count"] += 1
                except (ValueError, TypeError):
                    continue
    
    for kn_lower, data in temp_kommune_data.items():
        if data["count"] > 0:
            KOMMUNE_COORDS[kn_lower] = {
                "lat": data["lat_sum"] / data["count"],
                "lon": data["lon_sum"] / data["count"]
            }
    if not KOMMUNE_COORDS:
        print("Advarsel: Kunne ikke bygge kommunekoordinat-database. Posisjonsbasert flertydighetsløsning vil ikke være effektiv.", file=sys.stderr)
    else:
        print(f"Bygget koordinater for {len(KOMMUNE_COORDS)} kommuner.", file=sys.stderr)

def entity_type_from_dataset(dataset_list_ref):
    """Identifiserer hvilken NVE_DATA nøkkel en gitt datasettliste tilhører (for debugging/logikk)."""
    for key, value_list in NVE_DATA.items():
        if dataset_list_ref is value_list: # Sjekker objektidentitet
            return key
    return "unknown"

def extract_document_municipality(sd_content):
    """
    Prøver å trekke ut kommunenavn fra starten av dokumentet ved å først slå sammen
    de første linjene for å håndtere informasjon som går over flere linjer.
    Returnerer (kommunenavn_lower, fylkenavn_lower) eller (None, None).
    """
    # Hent de første N linjene
    num_lines_to_check = 30 # Antall linjer å vurdere fra toppen
    header_lines = sd_content.splitlines()[:num_lines_to_check]

    # Slå sammen disse linjene til én lang streng med mellomrom mellom
    # Dette hjelper hvis f.eks. "FROLAND" er på én linje og "kommune" på neste.
    # Fjern ledende/etterfølgende whitespace fra hver linje før sammenslåing for å unngå for mange mellomrom.
    # Erstatt også flere mellomrom i den sammenslåtte strengen med ett enkelt mellomrom.
    joined_header_text = " ".join(line.strip() for line in header_lines)
    joined_header_text = re.sub(r'\s+', ' ', joined_header_text).strip() # Normaliser mellomrom

    # print(f"DEBUG extract_document_municipality: Joined header text (first ~200 chars): '{joined_header_text[:200]}'")

    # Definer regex-mønstre. Noen er justert for å fungere bedre på en lang streng
    # i stedet for linje-for-linje. '^' og '$' er mindre relevante nå.
    patterns = [
        # Mønster som ser etter "navn=", etterfulgt av kommune og evt. fylke
        # Eksempel: <... navn="X Y Z">, Froland kommune i Aust-Agder fylke
        # Eksempel: <... navn="X Y Z">, Froland kommune
        r"<(?:\w+)\s+navn=\"[^\"]+\"[^>]*>\s*,\s*([\w\s\-]+?)\s+kommune\s+i\s+([\w\s\-]+?)(?:\s+fylke)?",
        r"<(?:\w+)\s+navn=\"[^\"]+\"[^>]*>\s*,\s*([\w\s\-]+?)\s+kommune",

        # Mønster som ser etter "utbygging av", "bygging av" etc. etterfulgt av kommune og evt. fylke
        # Eksempel: tillatelse til utbygging av Vassfossen kraftverk i Froland kommune i Aust-Agder
        r"(?:utbygging|bygging)\s+av[^,]+?i\s+([\w\s\-]+?)\s+kommune\s+i\s+([\w\s\-]+?)(?:\s+fylke)?",
        r"(?:utbygging|bygging)\s+av[^,]+?i\s+([\w\s\-]+?)\s+kommune",
        
        # Mønster for "i [Navn] kommune i [Navn] fylke" eller "i [Navn] kommune" (mer generelt)
        r"i\s+([\w\s\-]+?)\s+kommune\s+i\s+([\w\s\-]+?)(?:\s+fylke)?",
        r"i\s+([\w\s\-]+?)\s+kommune",

        # Mønster for "Kommune: [Navn]" eller "Kommune: [Navn] i [Fylke]"
        r"Kommune:\s*([\w\s\-]+?)(?:\s+i\s+([\w\s\-]+?)(?:\s+fylke)?)?",
        
        # Mønster for "[Navn] kommune i [Navn] fylke" eller "[Navn] kommune" stående mer alene
        # (mindre spesifikk, så legges mot slutten)
        r"([\w\s\-]+?)\s+kommune\s+i\s+([\w\s\-]+?)(?:\s+fylke)?",
        r"([\w\s\-]+?)\s+kommune"
    ]

    for pattern_idx, pattern in enumerate(patterns):
        # print(f"DEBUG: Prøver mønster {pattern_idx}: {pattern}")
        match = re.search(pattern, joined_header_text, re.IGNORECASE)
        if match:
            # print(f"DEBUG: Treff med mønster {pattern_idx}!")
            groups = match.groups()
            
            kommune_raw = groups[0]
            fylke_raw = None
            if len(groups) > 1 and groups[1]: # Hvis mønsteret hadde en fangstgruppe for fylke
                fylke_raw = groups[1]
            
            kommune = kommune_raw.strip().lower() if kommune_raw else None
            fylke = fylke_raw.strip().lower() if fylke_raw else None
            
            # Fjern "kommune" og "fylke" fra selve navnene hvis de har sneket seg med
            if kommune:
                kommune = re.sub(r'\s+kommune$', '', kommune, flags=re.IGNORECASE).strip()
            if fylke:
                fylke = re.sub(r'\s+fylke$', '', fylke, flags=re.IGNORECASE).strip()

            if kommune: # Vi må ha en kommune for å returnere et gyldig resultat
                # print(f"DEBUG: Fant kommune: '{kommune}', Fylke: '{fylke}'")
                return kommune, fylke
            # else:
                # print(f"DEBUG: Mønster {pattern_idx} ga treff, men ingen kommunenavn etter rensing.")
                
    # print("DEBUG: Ingen kommune funnet med noen av mønstrene.")
    return None, None

def normalize_name(name, entity_type="generic"):
    """
    Normaliserer et navn ved å konvertere til små bokstaver og fjerne vanlige suffikser.
    """
    if not isinstance(name, str):
        return "" # Returner tom streng hvis navnet ikke er en streng

    name_lower = name.lower().strip()

    # Generelle suffikser å fjerne
    suffixes_to_remove = [
        "kraftverk", "vannkraftverk", "vindkraftverk", "solkraftverk",
        "kraftanlegg", "anlegg", "pumpestasjon", "kraftstasjon",
        "minikraftverk", "mikrokraftverk", "småkraftverk"
    ]
    if entity_type == "elv":
        suffixes_to_remove.extend(["elva", " elvi", " elven", " åna", " åni", " åne", " bekken"]) # Utvidet for elver
    elif entity_type == "innsjø":
        suffixes_to_remove.extend(["vatnet", " vannet", " sjøen", " tjernet", " tjønna", " tjønn", " løken"])

    # Fjern suffikser iterativt (noen navn kan ha flere, f.eks. "X kraftverk anlegg")
    # Dette er en enkel tilnærming; mer avansert rekkefølge kan være nødvendig
    for _ in range(2): # Kjør et par ganger for å fange opp nestede suffikser
        for suffix in suffixes_to_remove:
            if name_lower.endswith(suffix):
                name_lower = name_lower[:-len(suffix)].strip()

    # Fjern spesialtegn, men behold norske bokstaver og mellomrom
    # name_lower = re.sub(r'[^\w\sæøåÆØÅ\-]', '', name_lower) # Kan være for aggressivt
    name_lower = name_lower.replace('-', ' ') # Erstatt bindestrek med mellomrom for bedre matching
    name_lower = re.sub(r'\s+', ' ', name_lower).strip() # Normaliser mellomrom
    #if name_lower.startswith("vassf"):
    #    print(f"DEBUG; Normalizing: {name} -->  >{name_lower}<")
    return name_lower


def find_best_match(entity_name_original, entity_type, nve_items, name_key, id_key, lat_key, lon_key, doc_kommune_coords, eier_key=None):
    """
    Finner det beste treffet i nve_items for en gitt entitet.
    Bruker normaliserte navn for matching.
    """
    normalized_input_name = normalize_name(entity_name_original, entity_type)
    # print(f"  Originalt inputnavn: '{entity_name_original}', Normalisert: '{normalized_input_name}' (Type: {entity_type})", file=sys.stderr)


    exact_match_candidates = []
    partial_match_candidates = []

    #if normalized_input_name == "vassfossen":
    #    print(f"DEBUG; name_key:{name_key}")

    for item in nve_items:
        nve_name_original = item.get(name_key)
        if not nve_name_original:
            continue

        normalized_nve_name = normalize_name(nve_name_original, entity_type)
        # if entity_type == "kraftverk": # Debugging
            # print(f"    DB original: '{nve_name_original}', DB normalisert: '{normalized_nve_name}'", file=sys.stderr)

        if normalized_nve_name == normalized_input_name:
            exact_match_candidates.append(item)
        # Enkel inneholder-sjekk, men vær forsiktig så det ikke blir for mange falske positiver
        # Vurder lengdeforskjell for å unngå at "Aurland" matcher "Aurland I" hvis vi søker på "Aurland"
        # og "Aurland I" er i databasen, men også "Aurland III" etc.
        elif normalized_input_name in normalized_nve_name or normalized_nve_name in normalized_input_name:
            # Tillat en viss fleksibilitet, men ikke for stor forskjell
            # Dette kan trenge justering basert på datakvalitet
            len_diff = abs(len(normalized_input_name) - len(normalized_nve_name))
            if len_diff <= max(5, len(normalized_input_name) * 0.3): # Tillat opptil 5 tegn eller 30% forskjell
                 partial_match_candidates.append(item)


    candidates = exact_match_candidates
    if not candidates:
        candidates = partial_match_candidates
    
    if not candidates:
        # print(f"  DEBUG; Ingen kandidater funnet for '{normalized_input_name}' etter normalisering.", file=sys.stderr)
        return None

    # print(f"  Kandidater for '{normalized_input_name}': {[c.get(name_key) for c in candidates]}", file=sys.stderr)

    if len(candidates) == 1:
        # print(f"  DEBUG; Valgte eneste kandidat: {candidates[0].get(name_key)}", file=sys.stderr)
        return candidates[0]

    # Flere kandidater, bruk posisjon hvis mulig
    if doc_kommune_coords:
        best_candidate = None
        min_dist = float('inf')
        
        for cand_idx, cand in enumerate(candidates):
            current_lat_key = "center_lat" if entity_type == "elv" else lat_key
            current_lon_key = "center_lon" if entity_type == "elv" else lon_key

            lat_val = cand.get(current_lat_key)
            lon_val = cand.get(current_lon_key)

            if lat_val is not None and lon_val is not None:
                try:
                    cand_lat, cand_lon = float(lat_val), float(lon_val)
                    dist = haversine(doc_kommune_coords["lat"], doc_kommune_coords["lon"], cand_lat, cand_lon)
                    
                    # print(f"    Kandidat for '{normalized_input_name}': {cand.get(name_key)}, Dist: {dist:.2f} km", file=sys.stderr)

                    if dist < min_dist:
                        min_dist = dist
                        best_candidate = cand
                    elif dist == min_dist and best_candidate is None : 
                        best_candidate = cand
                except (ValueError, TypeError) as e:
                    continue
            # else:
                # print(f"    Advarsel: Manglende koordinater for kandidat '{cand.get(name_key)}' ({current_lat_key}, {current_lon_key})", file=sys.stderr)

        if best_candidate:
            # print(f"   Valgte kandidat for '{normalized_input_name}' basert på avstand ({min_dist:.2f} km): {best_candidate.get(name_key)}", file=sys.stderr)
            return best_candidate
        elif candidates: 
             # print(f"   Flere kandidater for '{normalized_input_name}' uten posisjonsdata for avgjørelse, velger første: {candidates[0].get(name_key)}", file=sys.stderr)
             return candidates[0]

    if candidates: # Fallback hvis ingen posisjonsdata for dokumentet
        # print(f"   Flere kandidater for '{normalized_input_name}', velger første (ingen doc_kommune_coords eller ingen klar vinner): {candidates[0].get(name_key)}", file=sys.stderr)
        return candidates[0]
    # print("DEBUG; Ingen match")
    return None

def escape_attribute_value_for_nsd(value):
    """
    Forbereder en attributtverdi for inkludering i en NSD-tag.
    1. Konverterer til streng.
    2. Erstatter newlines med mellomrom.
    3. Fjerner ledende/etterfølgende whitespace.
    4. Escaper doble anførselstegn til "
    """
    if value is None:
        return "" # Returner tom streng for None verdier for å unngå "None" i output
    
    # 1. Konverter til streng
    str_value = str(value)
    
    # 2. Erstatter newlines (både \n og \r\n og \r) med mellomrom
    #    Dette gjøres ved å splitte på alle typer linjeskift og joine med ett mellomrom.
    cleaned_value = " ".join(str_value.splitlines()) # Håndterer \n, \r, \r\n
    
    # 3. Fjerner ledende/etterfølgende whitespace som kan ha oppstått
    cleaned_value = cleaned_value.strip()
    
    # 4. Escaper doble anførselstegn
    return cleaned_value.replace('"', '"')

def enrich_tag_match(match_obj, doc_kommune_coords, doc_eier_lower=None):
    """
    Behandler et regex match-objekt for en tag, slår opp entiteten,
    og returnerer den berikede taggen som en enlinjes streng med rensede attributter.
    """
    # match_obj forventes fra regexen som fanger:
    # group(1): tag_type (f.eks. "elv", "kraftverk")
    # group(2): entity_name (verdien av 'navn' attributtet)
    # group(3): existing_attrs_str (resten av attributtene som en streng)
    
    entity_type_original = match_obj.group(1).lower() # Behold original type for output-tag
    entity_name_from_tag = match_obj.group(2) # Navn direkte fra input-taggen
    existing_attrs_str = match_obj.group(3)

    # Normalisert type for intern logikk (f.eks. innsjoe -> innsjø)
    entity_type_for_logic = entity_type_original
    if entity_type_for_logic == "innsjoe":
        entity_type_for_logic = "innsjø"

    # print(f"Prosesserer tag: <{entity_type_original} navn=\"{entity_name_from_tag}\">", file=sys.stderr)

    best_item = None
    new_attrs_from_lookup = {} # Attributter funnet fra NVE-oppslag

    # --- Logikk for å slå opp 'best_item' og fylle 'new_attrs_from_lookup' ---
    # (Denne delen er lik din eksisterende logikk for elv, innsjø, kraftverk, dam)
    # Viktig: Sørg for at alle verdier du putter inn i new_attrs_from_lookup her
    # er råverdier (de vil bli renset senere).

    if entity_type_for_logic == "elv":
        best_item = find_best_match(entity_name_from_tag, entity_type_for_logic, NVE_DATA["elver"], "elvenavn", "elvId", "center_lat", "center_lon", doc_kommune_coords)
        if best_item:
            new_attrs_from_lookup["id"] = best_item.get("elvId")
            new_attrs_from_lookup["center_lat"] = best_item.get("center_lat")
            new_attrs_from_lookup["center_lon"] = best_item.get("center_lon")
            new_attrs_from_lookup["ul_lat"] = best_item.get("ul_lat")
            new_attrs_from_lookup["ul_lon"] = best_item.get("ul_lon")
            new_attrs_from_lookup["lr_lat"] = best_item.get("lr_lat")
            new_attrs_from_lookup["lr_lon"] = best_item.get("lr_lon")
            new_attrs_from_lookup["vassdragsNr"] = best_item.get("vassdragsNr")

    elif entity_type_for_logic == "innsjø":
        best_item = find_best_match(entity_name_from_tag, entity_type_for_logic, NVE_DATA["innsjoer"], "navn", "vatnLnr", "center_lat", "center_lon", doc_kommune_coords)
        if best_item:
            new_attrs_from_lookup["id"] = best_item.get("vatnLnr")
            new_attrs_from_lookup["magasinNr"] = best_item.get("magasinNr")
            new_attrs_from_lookup["lat"] = best_item.get("center_lat")
            new_attrs_from_lookup["lon"] = best_item.get("center_lon")
            new_attrs_from_lookup["areal_km2"] = best_item.get("areal_km2")
            kommune_data = best_item.get("kommune")
            if isinstance(kommune_data, list):
                new_attrs_from_lookup["kommune"] = ", ".join(map(str, kommune_data))
            else:
                new_attrs_from_lookup["kommune"] = kommune_data

    elif entity_type_for_logic == "kraftverk":
        # (Din eksisterende logikk for å finne beste kraftverkstype og sette new_attrs_from_lookup)
        # Eksempel (forkortet):
        # print(f"DEBUG; Sjekker {entity_name_from_tag}")
        best_item = find_best_match(entity_name_from_tag, entity_type_for_logic, NVE_DATA["vannkraftverk"], "vannkraftverkNavn", "vannkraftverkNr", "lat", "lon", doc_kommune_coords)
        # ... (lignende for sol og vind) ...
        # ... (logikk for å velge best_item og data_source) ...
        
        # Anta at best_item og data_source er satt:
        if best_item:
            new_attrs_from_lookup["id"] = best_item.get("vannkraftverkNr")
            new_attrs_from_lookup["type"] = "vann"
            new_attrs_from_lookup["kommune"] = best_item.get("kommuneNavn")
            new_attrs_from_lookup["status"] = best_item.get("status")
            new_attrs_from_lookup["ytelse_MW"] = best_item.get("maksYtelse_MW")
            # ... (elif for solkraft, vindkraft) ...
            new_attrs_from_lookup["lat"] = best_item.get("lat")
            new_attrs_from_lookup["lon"] = best_item.get("lon")
            # Eier-logikk
            eier_from_nve = new_attrs_from_lookup.get("eier") # Hent eier hvis den ble satt av NVE-data
            if doc_eier_lower and (not eier_from_nve or eier_from_nve is None):
                 new_attrs_from_lookup["eier"] = doc_eier_lower.title()


    elif entity_type_for_logic == "dam":
        best_item = find_best_match(entity_name_from_tag, entity_type_for_logic, NVE_DATA["innsjoer"], "navn", "vatnLnr", "center_lat", "center_lon", doc_kommune_coords)
        if best_item:
            new_attrs_from_lookup["type"] = "innsjødam"
            new_attrs_from_lookup["id"] = best_item.get("vatnLnr")
            # ... (andre dam-attributter) ...

    # --- Slutt på NVE-oppslagslogikk ---

    # Kombiner eksisterende attributter (unntatt 'navn') med nye/oppdaterte
    final_attrs_to_write = {}

    # 1. Parse eksisterende attributter fra input-taggen
    if existing_attrs_str:
        # Regex for å finne key="value" eller key='value'
        # Denne regexen må være robust nok for verdier som kan inneholde escapede anførselstegn
        # Enklere: anta at attributter i input .sd er velformede og ikke har newlines
        attr_regex_existing = r'([\w_:-]+)\s*=\s*"(.*?)"' # Fokuser på doble anførselstegn
        for attr_match in re.finditer(attr_regex_existing, existing_attrs_str):
            key = attr_match.group(1)
            val = attr_match.group(2) # Innholdet mellom anførselstegnene
            if key.lower() != "navn": # Ikke ta med 'navn' her, det håndteres separat
                 final_attrs_to_write[key] = val # Behold som det er, renses senere

    # 2. Legg til/overskriv med nye attributter fra NVE-oppslag
    for key, value in new_attrs_from_lookup.items():
        if value is not None: # Bare inkluder hvis det er en verdi
            final_attrs_to_write[key] = value

    # 3. Legg til match_found status
    if new_attrs_from_lookup: # Hvis vi fant noe fra NVE
        final_attrs_to_write["match_found"] = "true"
    else:
        # Hvis ingen nye attributter ble funnet, men det fantes eksisterende,
        # kan vi anta at det ikke var en match, med mindre vi vil beholde
        # eksisterende attributter selv om ingen NVE-match.
        # For nå: hvis new_attrs er tom, er det ingen NVE-match.
        if not any(k for k in final_attrs_to_write if k not in ["navn", "match_found"]): # Hvis bare gamle attrs
             final_attrs_to_write["match_found"] = "false"


    # Bygg den nye tag-strengen, alt på én linje, med rensede og escapede verdier
    # Start med tag-type og det originale navnet
    # Viktig: Bruk entity_name_from_tag her, da det er navnet som var i .sd-filen
    # og som brukeren/steg2 har identifisert.
    
    # Rens og escape navnet for output-taggen
    cleaned_display_name = escape_attribute_value_for_nsd(entity_name_from_tag)
    
    # Start med å bygge attributt-strengen
    attribute_parts_for_output = [f'navn="{cleaned_display_name}"']

    for key, value in sorted(final_attrs_to_write.items()):
        if key.lower() == "navn": # Allerede håndtert
            continue
        
        # Rens og escape hver verdi før den legges til
        cleaned_value = escape_attribute_value_for_nsd(value)
        attribute_parts_for_output.append(f'{key}="{cleaned_value}"')
        
    # Sett sammen den endelige taggen
    # Bruk entity_type_original for å bevare tag-navnet fra input (.sd)
    output_tag_string = f"<{entity_type_original} {' '.join(attribute_parts_for_output)}>"
    
    return output_tag_string

def process_sd_content(sd_content):
    """
    Parser .sd-innhold, identifiserer entiteter i flere faser,
    og beriker taggene.
    """
    # Fase 1: Finn dokumentets kommune og dens koordinater
    doc_kommune_lower, doc_fylke_lower = extract_document_municipality(sd_content)
    doc_kommune_coords_ref = None # Dette vil være referansepunktet, starter som kommune
    doc_eier_lower = None

    first_lines = "\n".join(sd_content.splitlines()[:10])
    eier_match = re.search(r"^\s*([\w\s.&;-]+?\s(?:AS|ANS|SA|BA|KS|DA|FKF|IKF|KF|HF|SF|RF|OF|NUF))\s*(?:—|Postboks|$)", first_lines, re.IGNORECASE | re.MULTILINE)
    if eier_match:
        doc_eier_lower = eier_match.group(1).strip().lower()
        print(f"Antatt dokumenteier: {doc_eier_lower.title()}", file=sys.stderr)

    if doc_kommune_lower and doc_kommune_lower in KOMMUNE_COORDS:
        doc_kommune_coords_ref = KOMMUNE_COORDS[doc_kommune_lower]
        print(f"Fase 1: Dokument antas å tilhøre kommune: {doc_kommune_lower} (lat: {doc_kommune_coords_ref['lat']:.4f}, lon: {doc_kommune_coords_ref['lon']:.4f})", file=sys.stderr)
    elif doc_kommune_lower:
        print(f"Fase 1: Dokument antas å tilhøre kommune: {doc_kommune_lower}, men fant ikke pre-kalkulerte koordinater for den.", file=sys.stderr)
    else:
        print("Fase 1: Kunne ikke sikkert identifisere kommune for dokumentet.", file=sys.stderr)

    # Fase 2: Identifiser hovedkraftverket og dets posisjon
    hoved_kraftverk_coords = None
    # *** HER ER ENDRINGEN ***
    tag_regex_kraftverk = r"<(kraftverk)\s+navn=\"([^\"]+)\"([^>]*)>" # Nå med 3 grupper
    
    temp_sd_content_for_kraftverk_pass = sd_content # Ikke strengt nødvendig å kopiere her, da vi kun itererer
    processed_kraftverk_tags = {} 

    kraftverk_matches = list(re.finditer(tag_regex_kraftverk, temp_sd_content_for_kraftverk_pass))

    for match_obj in kraftverk_matches:
        original_kraftverk_tag = match_obj.group(0)
        # Vi trenger ikke sjekke processed_kraftverk_tags her, da dette er første gang vi behandler dem for å finne koordinater.
        # Vi vil uansett re-prosessere alle tagger i det siste passet for selve erstatningen.
        # print(f"DEBUG: Sjekker kraftverk match {match_obj}")

        enriched_kraftverk_tag_str = enrich_tag_match(match_obj, doc_kommune_coords_ref, doc_eier_lower)
        
        lat_match = re.search(r'lat="([^"]+)"', enriched_kraftverk_tag_str)
        lon_match = re.search(r'lon="([^"]+)"', enriched_kraftverk_tag_str)
        
        if lat_match and lon_match and hoved_kraftverk_coords is None: 
            try:
                hoved_kraftverk_coords = {
                    "lat": float(lat_match.group(1)),
                    "lon": float(lon_match.group(1))
                }
                kraftverk_navn_fra_tag = match_obj.group(2) # Gruppe 2 er navnet i den nye regexen
                print(f"Fase 2: Hovedkraftverk identifisert: '{kraftverk_navn_fra_tag}' (lat: {hoved_kraftverk_coords['lat']:.4f}, lon: {hoved_kraftverk_coords['lon']:.4f})", file=sys.stderr)
            except ValueError:
                kraftverk_navn_fra_tag = match_obj.group(2)
                print(f"Fase 2: Kunne ikke parse koordinater for kraftverk '{kraftverk_navn_fra_tag}' fra beriket tag: {enriched_kraftverk_tag_str}", file=sys.stderr)
        
        # Lagre den berikede taggen for det siste passet
        processed_kraftverk_tags[original_kraftverk_tag] = enriched_kraftverk_tag_str


    # Fase 3: Identifiser andre entiteter (og kraftverk på nytt for selve erstatningen)
    final_reference_coords = hoved_kraftverk_coords if hoved_kraftverk_coords else doc_kommune_coords_ref

    if final_reference_coords is hoved_kraftverk_coords and hoved_kraftverk_coords is not None:
        print("Fase 3: Bruker hovedkraftverkets koordinater som referanse for andre entiteter.", file=sys.stderr)
    elif final_reference_coords is doc_kommune_coords_ref and doc_kommune_coords_ref is not None:
        print("Fase 3: Bruker kommunens koordinater som referanse (hovedkraftverk ikke funnet/tagget eller mangler koordinater).", file=sys.stderr)
    else:
        print("Fase 3: Ingen pålitelige referansekoordinater tilgjengelig for matching.", file=sys.stderr)

    tag_regex_alle = r"<(\w+)\s+navn=\"([^\"]+)\"([^>]*)>"
    
    def replacer_final_pass(match_obj):
        entity_type = match_obj.group(1).lower()
        original_tag_text = match_obj.group(0)

        if entity_type == "kraftverk" and original_tag_text in processed_kraftverk_tags:
            return processed_kraftverk_tags[original_tag_text]
        
        return enrich_tag_match(match_obj, final_reference_coords, doc_eier_lower)

    nsd_content_final = re.sub(tag_regex_alle, replacer_final_pass, sd_content)
    return nsd_content_final

# --- Hovedlogikk ---
def main():
    parser = argparse.ArgumentParser(
        description="Beriker et .sd (Smart Dokument) med metadata fra NVEs datasett og produserer en .nsd-fil.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "input_file",
        type=pathlib.Path,
        help="Sti til input .sd-fil"
    )
    parser.add_argument(
        "-o", "--output",
        type=pathlib.Path,
        help="Valgfri sti for output .nsd-fil. Standard: <input_fil_navn>.nsd"
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Skriv output til stdout i stedet for en fil."
    )
    parser.add_argument(
        "--data-dir",
        type=pathlib.Path,
        default=pathlib.Path("."), 
        help="Mappe som inneholder NVEs jsonl-datafiler (f.eks. elver_per_name.jsonl)."
    )

    args = parser.parse_args()

    input_path: pathlib.Path = args.input_file
    data_dir: pathlib.Path = args.data_dir

    if not input_path.is_file():
        print(f"Feil: Input-filen '{input_path}' ble ikke funnet.", file=sys.stderr)
        sys.exit(1)

    if input_path.suffix.lower() != ".sd":
        print(f"Advarsel: Input-filen '{input_path}' har ikke .sd-ending.", file=sys.stderr)

    print("Laster NVE-data...", file=sys.stderr)
    NVE_DATA["elver"] = load_jsonl(data_dir / "elver_per_name.jsonl", entity_type="elver") # Send med type for spesialbehandling
    NVE_DATA["innsjoer"] = load_jsonl(data_dir / "innsjoe_full.jsonl")
    NVE_DATA["vannkraftverk"] = load_jsonl(data_dir / "vannkraftverk.jsonl")
    NVE_DATA["solkraftverk"] = load_jsonl(data_dir / "solkraftverk.jsonl")
    NVE_DATA["vindkraftverk"] = load_jsonl(data_dir / "vindkraftverk.jsonl")
    
    build_kommune_coords_from_nve_data()

    try:
        sd_content = input_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Feil under lesing av filen '{input_path}': {e}", file=sys.stderr)
        sys.exit(1)

    if not sd_content.strip():
        print(f"Filen '{input_path}' er tom.", file=sys.stderr)
        if args.stdout:
            print("", end="")
        else:
            output_path = args.output if args.output else input_path.with_suffix(".nsd")
            output_path.write_text("", encoding="utf-8")
            print(f"Tom output skrevet til '{output_path}'", file=sys.stderr)
        sys.exit(0)
        
    nsd_content = process_sd_content(sd_content)

    if args.stdout:
        print(nsd_content)
    else:
        output_path = args.output if args.output else input_path.with_suffix(".nsd")
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(nsd_content, encoding="utf-8")
            print(f"Beriket innhold lagret til: {output_path}", file=sys.stderr)
        except Exception as e:
            print(f"Feil under skriving til output-filen '{output_path}': {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()