#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gjenbrukbar funksjon for å slå opp vassdragsnavn mot NVEs Regine-database.

Eksempel:
    from resolve_vassdrag import resolve_vassdrag

    matches = resolve_vassdrag("Tokke-Vinjevassdraget")
    for match in matches:
        print(f"{match['score']}: {match['matched_navn']} ({match['vassdragsnr']})")
"""

import json
import re
from pathlib import Path
from typing import Optional


# Standard stier (kan overstyres)
DEFAULT_ENDING_MAP_PATH = Path(__file__).parent / "ending_map.json"
DEFAULT_REGINE_INDEX_PATH = Path(__file__).parent / "INDEX_regine.json"

# Cache for å unngå å laste filene flere ganger
_ENDING_MAP_CACHE: Optional[dict[str, str]] = None
_REGINE_INDEX_CACHE: Optional[list[dict]] = None


def load_ending_map(path: Path = DEFAULT_ENDING_MAP_PATH) -> dict[str, str]:
    """Leser mapping fra JSON-fil."""
    global _ENDING_MAP_CACHE
    if _ENDING_MAP_CACHE is None:
        if not path.exists():
            raise FileNotFoundError(f"Fant ikke {path}")
        with path.open(encoding="utf-8") as f:
            _ENDING_MAP_CACHE = json.load(f)
    return _ENDING_MAP_CACHE


def load_regine_index(path: Path = DEFAULT_REGINE_INDEX_PATH) -> list[dict]:
    """Laster INDEX_regine.json."""
    global _REGINE_INDEX_CACHE
    if _REGINE_INDEX_CACHE is None:
        if not path.exists():
            raise FileNotFoundError(f"Fant ikke {path}")
        with path.open(encoding="utf-8") as f:
            _REGINE_INDEX_CACHE = json.load(f)
    return _REGINE_INDEX_CACHE


def normalize_vassdrag_navn(text: str, ending_map: dict[str, str]) -> str:
    """
    Normaliserer et vassdragsnavn ved å mappe endinger til kategorier.
    Eksempel: 'Storelva' -> 'StorELV', 'Iddefjorden' -> 'IddeFJORD'
    """
    stripped = text.strip()
    if not stripped:
        return ""

    words = stripped.split()
    endings_sorted = sorted(ending_map.keys(), key=len, reverse=True)
    normalized_words = []

    for word in words:
        lower_word = word.lower()
        replaced = False

        # Prøv å matche lengste ending først
        for ending in endings_sorted:
            if lower_word.endswith(ending) and len(lower_word) > len(ending):
                # Behold den originale casen for stammen, legg til kategorien
                cut = len(word) - len(ending)
                word = word[:cut] + ending_map[ending]
                replaced = True
                break

        normalized_words.append(word)

    return " ".join(normalized_words)


def find_exact_match(search_name: str, regine_index: list[dict]) -> Optional[dict]:
    """
    Søker etter eksakt match i INDEX_regine.json basert på 'navn' eller 'navn_normalisert' (case-insensitive).
    Prioriterer match på 'navn' feltet først, deretter 'navn_normalisert'.
    Returnerer første match hvis funnet, ellers None.
    """
    search_lower = search_name.lower()

    # Første pass: søk etter match på 'navn' feltet (originalnavn i indeksen)
    for entry in regine_index:
        if entry.get("navn", "").lower() == search_lower:
            return entry

    # Andre pass: søk etter match på 'navn_normalisert' feltet
    for entry in regine_index:
        if entry.get("navn_normalisert", "").lower() == search_lower:
            return entry

    return None


def phonetic_normalize(text: str) -> str:
    """
    Normaliserer et norsk navn fonetisk for å håndtere stavevarianter.

    Håndterer:
    - Dobbeltkonsonanter → enkel konsonant (mm→m, nn→n, etc.)
    - ch → k (Christiania → Kristiania)
    - c → k (i starten av ord)
    - ph → f
    - th → t
    - aa → å
    - Fjerner mellomrom og bindestrek

    Eksempel:
        "Nummedalslågen" → "numedalslagen"
        "Numedalslågen" → "numedalslagen"
        "Christiania" → "kristiania"
        "Kristiania" → "kristiania"
    """
    if not text:
        return ""

    # Konverter til lowercase
    normalized = text.lower()

    # Erstatt spesielle tegnkombinasjoner
    replacements = [
        ("ch", "k"),
        ("ph", "f"),
        ("th", "t"),
        ("aa", "å"),
        # Fjern bindestrek og mellomrom
        ("-", ""),
        (" ", ""),
    ]

    for old, new in replacements:
        normalized = normalized.replace(old, new)

    # c → k i starten av ord (hvis fulgt av vokal)
    if normalized.startswith("c"):
        normalized = "k" + normalized[1:]

    # Reduser dobbeltkonsonanter til enkelt
    # (men behold dobbel hvis det er en vokal før og etter)
    consonants = "bcdfghjklmnpqrstvwxz"
    result = []
    i = 0
    while i < len(normalized):
        char = normalized[i]
        # Sjekk om det er en dobbeltkonsonant
        if i < len(normalized) - 1 and char == normalized[i + 1] and char in consonants:
            # Legg til kun én av konsonanten
            result.append(char)
            i += 2  # Hopp over begge
        else:
            result.append(char)
            i += 1

    return "".join(result)


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Beregner Levenshtein distance (edit distance) mellom to strenger.
    Returnerer antall enkeltkarakters endringer (insert, delete, replace) som trengs.
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost of insertions, deletions, or substitutions
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def find_fuzzy_matches(
    search_name: str,
    regine_index: list[dict],
    max_distance: int = 2,
    min_length: int = 5
) -> list[tuple[dict, int, str]]:
    """
    Søker etter fuzzy matches basert på fonetisk normalisering og edit distance.

    Args:
        search_name: Navnet å søke etter
        regine_index: Regine-indeksen
        max_distance: Maksimal Levenshtein distance (default: 2)
        min_length: Minimum lengde på søkeord for fuzzy matching (default: 5)

    Returns:
        Liste med tuples: (match_entry, edit_distance, matched_field)
        Sortert etter edit distance (lavest først)
    """
    # Ikke gjør fuzzy matching på veldig korte navn
    if len(search_name) < min_length:
        return []

    search_phonetic = phonetic_normalize(search_name)
    matches = []

    for entry in regine_index:
        # Sjekk både 'navn' og 'navn_normalisert' feltet
        for field in ["navn", "navn_normalisert"]:
            entry_value = entry.get(field, "")
            if not entry_value:
                continue

            entry_phonetic = phonetic_normalize(entry_value)

            # Beregn edit distance
            distance = levenshtein_distance(search_phonetic, entry_phonetic)

            # Hvis distansen er innenfor grensen, legg til match
            if distance <= max_distance:
                matches.append((entry, distance, field))

    # Sorter etter edit distance (lavest først) og returner
    matches.sort(key=lambda x: x[1])

    # Fjern duplikater (samme vassdragsnr)
    seen = set()
    unique_matches = []
    for match, distance, field in matches:
        if match["vassdragsnr"] not in seen:
            seen.add(match["vassdragsnr"])
            unique_matches.append((match, distance, field))

    return unique_matches


def find_startswith_matches(
    search_name: str,
    regine_index: list[dict],
    min_length: int = 3
) -> list[tuple[dict, str]]:
    """
    Søker etter matches hvor enten søkenavn eller vassdragsnavn starter med det andre.
    F.eks. "suldal" matcher "suldalsvassdraget" eller vice versa.

    Args:
        search_name: Navnet å søke etter
        regine_index: Regine-indeksen
        min_length: Minimum lengde for startswith matching (default: 3)

    Returns:
        Liste med tuples: (match_entry, matched_field)
    """
    # Ikke gjør startswith matching på veldig korte navn
    if len(search_name) < min_length:
        return []

    search_lower = search_name.lower()
    matches = []
    seen = set()

    for entry in regine_index:
        # Sjekk både 'navn' og 'navn_normalisert' feltet
        for field in ["navn", "navn_normalisert"]:
            entry_value = entry.get(field, "")
            if not entry_value or len(entry_value) < min_length:
                continue

            entry_lower = entry_value.lower()

            # Sjekk om ett starter med det andre
            if entry_lower.startswith(search_lower) or search_lower.startswith(entry_lower):
                # Unngå duplikater basert på vassdragsnr + field
                key = (entry["vassdragsnr"], field)
                if key not in seen:
                    seen.add(key)
                    matches.append((entry, field))

    return matches


def generate_variants(original_name: str, ending_map: dict[str, str]) -> list[tuple[str, int, str]]:
    """
    Genererer alle mulige varianter av et vassdragsnavn med scoringer.

    Returnerer liste med tuples: (variant, score, beskrivelse)
    Høyere score = bedre match.

    Score-system (grunnpoeng + bonuspoeng/penalty):
        Grunnpoeng:
            100: Originalnavn (ingen endring)
            98: Originalnavn + "vassdraget" (f.eks. "Glomma" → "Glommavassdraget")
            97: Originalnavn + "ELV" (f.eks. "Glomma" → "GlommaELV")
            96: Originalnavn + "VANN" (f.eks. "Glomma" → "GlommaVANN")
            96: Startswith match på 'navn' (f.eks. "Suldal" → "Suldalsvassdraget")
            95: Fuzzy match med edit distance 0 (fonetisk identisk)
            94: Startswith match på 'navn_normalisert'
            92: Fuzzy match med edit distance 1 (1 tegn forskjell)
            90: Normalisert navn
            89: Fuzzy match med edit distance 2 (2 tegn forskjell)
            88: Stamme normalisert (f.eks. "jostedalvassdraget" → "josteDAL")
            87: Navn uten retningsord (f.eks. "Nordre Vinstra" → "Vinstra")
            86: Navn uten retningsord normalisert (f.eks. "Nordre Vinstra" → "VinstrELV")
            85: Stamme fra normalisert navn (f.eks. "BandakVANN" → "Bandak")
            82: Stamme fra originalnavn (f.eks. "jostedalvassdraget" → "jostedal")
            80: Navn uten bindestrek
            75-70: Stamme + primære suffix (ELV, VANN, vassdraget) - mest relevant for vassdrag
            65-60: Stamme + sekundære suffix (FJORD, DAL, FJELL)
            55-50: Stamme + 's' + suffix (primære)
            45-40: Stamme + 's' + suffix (sekundære)
            35-30: Stamme-variasjoner og foss/fall-stemmer

        Bonuspoeng (vassdragsnr lengde - kortere = viktigere):
            +10: 3 eller færre tegn (f.eks. "002" - hovedvassdrag)
            +8: 4 tegn
            +6: 5 tegn (f.eks. "015.Z")
            +4: 6 tegn
            +2: 7 tegn (f.eks. "016.BD5")
            +0: 8+ tegn (f.eks. "016.BD31")

        Prefix bonus/penalty (kritisk for gode matches):
            +25: Startswith match (ett navn starter med det andre)
            +12: Første 2 bokstaver matcher
            +8: Første bokstav matcher
            -15: Første bokstav matcher IKKE (forhindrer "vinsteren"→"ISTEREN")
    """
    variants = []

    # 1. Originalnavn (score 100)
    variants.append((original_name, 100, "original"))

    # 1b. Hvis originalnavn ikke allerede slutter på vassdrag-relaterte suffix,
    # prøv å legge til "vassdraget", "ELV", "VANN" (høyere score enn fuzzy)
    # Dette håndterer søk som "Glomma" → "Glommavassdraget"
    lower_name = original_name.lower()
    has_vassdrag_suffix = any(
        lower_name.endswith(suffix)
        for suffix in ["vassdraget", "vassdragene", "vassdrag", "vasdrag", "elv", "elva",
                       "vann", "vatn", "sjø", "tjern", "bekk", "å"]
    )

    if not has_vassdrag_suffix and len(original_name) > 3:
        # Prøv med "vassdraget" (score 99 - høyere enn fuzzy med prefix bonus)
        # Dette sikrer at "Glomma" → "Glommavassdraget" scorer høyere enn fuzzy "GLÅMA"
        variants.append((original_name + "vassdraget", 99, "add_vassdraget"))

        # Prøv også med normaliserte suffix
        variants.append((original_name + "ELV", 98, "add_ELV"))
        variants.append((original_name + "VANN", 97, "add_VANN"))

    # 2. Normalisert navn (score 90)
    normalized = normalize_vassdrag_navn(original_name, ending_map)
    if normalized and normalized != original_name:
        variants.append((normalized, 90, "normalized"))

        # 2b. Fjern normaliserte kategorier for å finne stammen
        # Eksempel: "BandakVANN" → "Bandak"
        normalized_categories = ["ELV_SAMISK", "VANN_SAMISK", "ELV", "VANN", "DAL", "FJORD", "FJELL"]
        for category in normalized_categories:
            if normalized.endswith(category):
                # Finn stammen ved å fjerne kategorien
                stem_from_normalized = normalized[:-len(category)]
                if stem_from_normalized and stem_from_normalized != original_name:
                    variants.append((stem_from_normalized, 85, "normalized_stem"))
                break

    # 3. Prøv uten retningsord (score 87)
    # Fjern ord som "nordre", "søndre", "østre", "vestre", "øvre", "nedre", "gamle"
    directional_prefixes = ["nordre", "søndre", "østre", "vestre", "øvre", "nedre", "gamle", "nørdre", "søndre"]
    words = original_name.split()
    if len(words) > 1:
        first_word_lower = words[0].lower()
        if first_word_lower in directional_prefixes:
            # Fjern første ord og lag nytt navn
            without_directional = " ".join(words[1:])
            if without_directional:
                variants.append((without_directional, 87, "no_directional"))

                # Prøv også å normalisere navnet uten retningsord
                normalized_no_dir = normalize_vassdrag_navn(without_directional, ending_map)
                if normalized_no_dir and normalized_no_dir != without_directional:
                    variants.append((normalized_no_dir, 86, "no_directional_normalized"))

    # 4. Navn uten bindestrek (score 80)
    if '-' in original_name:
        no_hyphen = original_name.replace('-', '')
        variants.append((no_hyphen, 80, "no_hyphen"))

    # 4-7. Stamme-baserte varianter
    lower_name = original_name.lower()
    stem = None
    suffix_found = None

    # Finn stammen ved å fjerne vanlige suffix
    for suffix in ["vassdragene", "vassdraget", "vassdrag", "vasdrag", "reguleringen"]:
        if lower_name.endswith(suffix):
            stem_len = len(original_name) - len(suffix)
            stem = original_name[:stem_len]
            suffix_found = suffix
            break

    # Hvis ingen suffix funnet, bruk hele navnet som stamme
    if stem is None:
        stem = original_name

    if stem:
        # 3a. Prøv å normalisere stammen først (for bedre matching)
        # Eksempel: "josteDal" → "josteDAL" matcher "Jostedøla" i indeksen
        if suffix_found:  # Bare hvis vi faktisk fjernet et suffix
            stem_normalized = normalize_vassdrag_navn(stem, ending_map)
            if stem_normalized and stem_normalized != stem and stem_normalized != normalized:
                variants.append((stem_normalized, 88, "stem_normalized"))

            # Prøv også bare stammen (høyere score hvis vi fjernet et suffix)
            variants.append((stem, 82, "stem_only"))

        # Primære suffixes: mest relevante for vassdrag
        primary_suffixes = ["ELV", "VANN", "vassdraget"]
        # Sekundære suffixes: mindre sannsynlige for vassdrag
        secondary_suffixes = ["FJORD", "DAL", "FJELL"]

        # Prøv primære suffixes først (høyere score)
        for suffix in primary_suffixes:
            # Stamme + suffix
            variant = stem + suffix
            variants.append((variant, 75, f"stem+{suffix}"))

            # Stamme + 's' + suffix
            variant = stem + "s" + suffix
            variants.append((variant, 55, f"stem+s+{suffix}"))

            # Stamme uten siste bokstav + suffix
            if len(stem) > 2:
                variant = stem[:-1] + suffix
                variants.append((variant, 50, f"stem-1+{suffix}"))

            # Stamme + 'a' + suffix
            variant = stem + "a" + suffix
            variants.append((variant, 45, f"stem+a+{suffix}"))

        # Prøv sekundære suffixes (lavere score)
        for suffix in secondary_suffixes:
            # Stamme + suffix
            variant = stem + suffix
            variants.append((variant, 65, f"stem+{suffix}"))

            # Stamme + 's' + suffix
            variant = stem + "s" + suffix
            variants.append((variant, 45, f"stem+s+{suffix}"))

            # Stamme uten siste bokstav + suffix
            if len(stem) > 2:
                variant = stem[:-1] + suffix
                variants.append((variant, 40, f"stem-1+{suffix}"))

            # Stamme + 'a' + suffix
            variant = stem + "a" + suffix
            variants.append((variant, 35, f"stem+a+{suffix}"))

        # Bare stammen (score 30) - kun hvis vi ikke fjernet et suffix
        # (hvis vi fjernet suffix, har vi allerede lagt til stemmen med score 82)
        if stem != original_name and not suffix_found:
            variants.append((stem, 30, "stem_only"))

    # 9. Håndter foss/fall-suffix
    foss_suffixes = ["fossen", "foss", "faldene", "fallet", "fall", "fossan", "fosane"]

    for foss_suffix in foss_suffixes:
        if lower_name.endswith(foss_suffix):
            stem_len = len(original_name) - len(foss_suffix)
            foss_stem = original_name[:stem_len]

            # Prøv bare stammen
            variants.append((foss_stem, 30, "foss_stem"))

            # Prøv primære suffixes (høyere score)
            for suffix in ["vassdraget", "ELV", "VANN"]:
                variant = foss_stem + suffix
                variants.append((variant, 35, f"foss_stem+{suffix}"))

            # Prøv sekundære suffixes (lavere score)
            for suffix in ["DAL", "FJORD"]:
                variant = foss_stem + suffix
                variants.append((variant, 25, f"foss_stem+{suffix}"))

            # Stamme uten 's' på slutten
            if foss_stem.endswith('s'):
                short_stem = foss_stem[:-1]
                # Bare stamme
                variants.append((short_stem, 30, "foss_short_stem"))
                # Med primære suffixes
                for suffix in ["vassdraget", "ELV", "VANN"]:
                    variant = short_stem + suffix
                    variants.append((variant, 35, f"foss_short_stem+{suffix}"))
                # Med sekundære suffixes
                for suffix in ["DAL", "FJORD"]:
                    variant = short_stem + suffix
                    variants.append((variant, 25, f"foss_short_stem+{suffix}"))

            break  # Bare første matchende foss-suffix

    return variants


def calculate_vassdragsnr_bonus(vassdragsnr: str) -> int:
    """
    Beregner bonuspoeng basert på lengden av vassdragsnummeret.
    Kortere nummer = mer overordnet vassdrag = høyere bonus.

    Eksempler:
        "002" (3 tegn) → +10 poeng (hovedvassdrag)
        "015.Z" (5 tegn) → +6 poeng (delvassdrag)
        "016.BD5" (7 tegn) → +2 poeng (undervassdrag)
        "016.BD31" (8 tegn) → +0 poeng (dypt nested)

    Bonuspoeng:
        3 eller færre tegn: +10
        4 tegn: +8
        5 tegn: +6
        6 tegn: +4
        7 tegn: +2
        8+ tegn: +0
    """
    length = len(vassdragsnr)

    if length <= 3:
        return 10
    elif length == 4:
        return 8
    elif length == 5:
        return 6
    elif length == 6:
        return 4
    elif length == 7:
        return 2
    else:
        return 0


def resolve_vassdrag_single(
    vassdragsforslag: str,
    ending_map_path: Path = DEFAULT_ENDING_MAP_PATH,
    regine_index_path: Path = DEFAULT_REGINE_INDEX_PATH,
    max_results: int = 10
) -> list[dict]:
    """
    Søker etter et enkelt vassdragsnavn og returnerer de beste matchene.

    Args:
        vassdragsforslag: Vassdragsnavnet å slå opp
        ending_map_path: Sti til ending_map.json
        regine_index_path: Sti til INDEX_regine.json
        max_results: Maksimalt antall resultater å returnere

    Returns:
        Liste med matcher sortert etter score (høyest først).
        Hver match er en dict med:
        {
            "original_input": str,
            "matched_navn": str,
            "matched_variant": str,
            "vassdragsnr": str,
            "lat": float,
            "long": float,
            "score": int,
            "match_type": str
        }
    """
    # Last inn data
    ending_map = load_ending_map(ending_map_path)
    regine_index = load_regine_index(regine_index_path)

    # Generer alle varianter
    variants = generate_variants(vassdragsforslag, ending_map)

    # Søk etter matcher
    matches = []
    seen_vassdragsnr = set()  # Unngå duplikater

    for variant, score, match_type in variants:
        match = find_exact_match(variant, regine_index)
        if match and match["vassdragsnr"] not in seen_vassdragsnr:
            # Legg til bonus basert på vassdragsnr lengde
            vassdragsnr_bonus = calculate_vassdragsnr_bonus(match["vassdragsnr"])
            final_score = score + vassdragsnr_bonus

            matches.append({
                "original_input": vassdragsforslag,
                "matched_navn": match["navn"],
                "matched_variant": variant,
                "vassdragsnr": match["vassdragsnr"],
                "lat": match["lat"],
                "long": match["long"],
                "score": final_score,
                "match_type": match_type,
                "vassdragsnr_bonus": vassdragsnr_bonus
            })
            seen_vassdragsnr.add(match["vassdragsnr"])

    # Hvis vi ikke fant nok matcher, prøv startswith matching
    # Dette fanger opp matches som "suldal" → "suldalsvassdraget"
    if len(matches) < max_results:
        startswith_matches = find_startswith_matches(vassdragsforslag, regine_index, min_length=3)

        for match, field in startswith_matches:
            if match["vassdragsnr"] not in seen_vassdragsnr:
                # Score: 96 for 'navn', 94 for 'navn_normalisert'
                base_score = 96 if field == "navn" else 94

                # Legg til bonus basert på vassdragsnr lengde
                vassdragsnr_bonus = calculate_vassdragsnr_bonus(match["vassdragsnr"])

                # Legg til ekstra bonus hvis search_lower er identisk med starten
                matched_value = match[field].lower() if match.get(field) else ""
                search_lower = vassdragsforslag.lower()
                prefix_bonus = 25  # Startswith får alltid +25 bonus

                final_score = base_score + vassdragsnr_bonus + prefix_bonus

                matches.append({
                    "original_input": vassdragsforslag,
                    "matched_navn": match["navn"],
                    "matched_variant": match[field],
                    "vassdragsnr": match["vassdragsnr"],
                    "lat": match["lat"],
                    "long": match["long"],
                    "score": final_score,
                    "match_type": f"startswith_{field}",
                    "vassdragsnr_bonus": vassdragsnr_bonus,
                    "prefix_bonus": prefix_bonus
                })
                seen_vassdragsnr.add(match["vassdragsnr"])

    # Hvis vi ikke fant nok matcher, prøv fuzzy matching
    # Score for fuzzy matches: 95 (distance 0), 92 (distance 1), 89 (distance 2)
    if len(matches) < max_results:
        # Først: kjør fuzzy matching på originalnavn
        fuzzy_matches = find_fuzzy_matches(vassdragsforslag, regine_index, max_distance=2, min_length=5)

        for match, distance, field in fuzzy_matches:
            if match["vassdragsnr"] not in seen_vassdragsnr:
                # Beregn score basert på edit distance
                fuzzy_score = 95 - (distance * 3)  # 95, 92, 89 for distance 0, 1, 2

                # Prefix matching: bonus hvis matcher, penalty hvis ikke
                # Dette er kritisk for å unngå dårlige matcher som "vinsteren" → "ISTEREN"
                matched_value = match[field].lower() if match.get(field) else ""
                search_lower = vassdragsforslag.lower()
                prefix_bonus = 0

                if matched_value and search_lower:
                    # Sjekk for startswith (stor bonus hvis ett navn starter med det andre)
                    # F.eks. "suldal" matcher "suldalsvassdraget"
                    # Minimum lengde 3 for å unngå falske positive
                    if len(search_lower) >= 3 and len(matched_value) >= 3:
                        if matched_value.startswith(search_lower) or search_lower.startswith(matched_value):
                            prefix_bonus = 25  # Stor bonus for startswith match

                    # Hvis ikke startswith, sjekk første bokstaver
                    if prefix_bonus == 0:
                        if matched_value[0] == search_lower[0]:
                            # +8 bonus hvis første bokstav matcher
                            prefix_bonus = 8

                            # +4 ekstra hvis første 2 bokstaver matcher
                            if len(matched_value) >= 2 and len(search_lower) >= 2:
                                if matched_value[:2] == search_lower[:2]:
                                    prefix_bonus = 12
                        else:
                            # Stor penalty hvis første bokstav IKKE matcher
                            # Dette forhindrer "vinsteren" → "ISTEREN" matches
                            if distance >= 1:
                                prefix_bonus = -15  # Penalty!

                # Legg til bonus basert på vassdragsnr lengde
                vassdragsnr_bonus = calculate_vassdragsnr_bonus(match["vassdragsnr"])
                final_score = fuzzy_score + vassdragsnr_bonus + prefix_bonus

                matches.append({
                    "original_input": vassdragsforslag,
                    "matched_navn": match["navn"],
                    "matched_variant": match[field],  # Vis hvilket felt som matchet
                    "vassdragsnr": match["vassdragsnr"],
                    "lat": match["lat"],
                    "long": match["long"],
                    "score": final_score,
                    "match_type": f"fuzzy_{field}_dist{distance}",
                    "vassdragsnr_bonus": vassdragsnr_bonus,
                    "prefix_bonus": prefix_bonus
                })
                seen_vassdragsnr.add(match["vassdragsnr"])

    # Hvis vi fortsatt ikke har nok matcher, prøv fuzzy matching på viktige varianter
    # Spesielt "no_directional" varianten
    if len(matches) < max_results:
        important_variants = [
            (variant, base_score, match_type)
            for variant, base_score, match_type in variants
            if match_type in ["no_directional", "no_directional_normalized", "normalized", "stem_normalized"]
        ]

        for variant, base_score, match_type in important_variants:
            if len(matches) >= max_results:
                break

            variant_fuzzy_matches = find_fuzzy_matches(variant, regine_index, max_distance=2, min_length=5)

            for match, distance, field in variant_fuzzy_matches:
                if match["vassdragsnr"] not in seen_vassdragsnr:
                    # Beregn score: bruk base_score fra varianten, reduser litt for fuzzy
                    # f.eks. no_directional (87) + fuzzy dist 1 (-3) = 84
                    fuzzy_penalty = distance * 3
                    fuzzy_score = max(base_score - fuzzy_penalty, 50)  # Minimum 50

                    # Prefix matching: bonus hvis matcher, penalty hvis ikke
                    matched_value = match[field].lower() if match.get(field) else ""
                    variant_lower = variant.lower()
                    prefix_bonus = 0

                    if matched_value and variant_lower:
                        # Sjekk for startswith (stor bonus hvis ett navn starter med det andre)
                        # F.eks. "suldal" matcher "suldalsvassdraget"
                        # Minimum lengde 3 for å unngå falske positive
                        if len(variant_lower) >= 3 and len(matched_value) >= 3:
                            if matched_value.startswith(variant_lower) or variant_lower.startswith(matched_value):
                                prefix_bonus = 25  # Stor bonus for startswith match

                        # Hvis ikke startswith, sjekk første bokstaver
                        if prefix_bonus == 0:
                            if matched_value[0] == variant_lower[0]:
                                # +8 bonus hvis første bokstav matcher
                                prefix_bonus = 8

                                # +4 ekstra hvis første 2 bokstaver matcher
                                if len(matched_value) >= 2 and len(variant_lower) >= 2:
                                    if matched_value[:2] == variant_lower[:2]:
                                        prefix_bonus = 12
                            else:
                                # Stor penalty hvis første bokstav IKKE matcher
                                if distance >= 1:
                                    prefix_bonus = -15  # Penalty!

                    # Legg til bonus basert på vassdragsnr lengde
                    vassdragsnr_bonus = calculate_vassdragsnr_bonus(match["vassdragsnr"])
                    final_score = fuzzy_score + vassdragsnr_bonus + prefix_bonus

                    matches.append({
                        "original_input": vassdragsforslag,
                        "matched_navn": match["navn"],
                        "matched_variant": match[field],
                        "vassdragsnr": match["vassdragsnr"],
                        "lat": match["lat"],
                        "long": match["long"],
                        "score": final_score,
                        "match_type": f"{match_type}_fuzzy_{field}_dist{distance}",
                        "vassdragsnr_bonus": vassdragsnr_bonus,
                        "prefix_bonus": prefix_bonus
                    })
                    seen_vassdragsnr.add(match["vassdragsnr"])

    # Sorter etter score (høyest først) og returner topp-N
    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches[:max_results]


def resolve_vassdrag(
    vassdragsforslag: str,
    ending_map_path: Path = DEFAULT_ENDING_MAP_PATH,
    regine_index_path: Path = DEFAULT_REGINE_INDEX_PATH,
    max_results: int = 10
) -> list[dict]:
    """
    Hovedfunksjon for å slå opp vassdragsnavn mot NVEs Regine-database.

    Håndterer både enkle navn ("Glomma") og sammensatte navn ("Tokke-Vinjevassdraget").

    Args:
        vassdragsforslag: Vassdragsnavnet å slå opp
        ending_map_path: Sti til ending_map.json
        regine_index_path: Sti til INDEX_regine.json
        max_results: Maksimalt antall resultater å returnere per del

    Returns:
        Liste med matcher sortert etter score (høyest først).

        For enkle navn:
        [
            {
                "original_input": "Glomma",
                "matched_navn": "Glommavassdraget",
                "matched_variant": "GlommaELV",
                "vassdragsnr": "002",
                "lat": 60.89467,
                "long": 9.96461,
                "score": 90,
                "match_type": "normalized"
            },
            ...
        ]

        For sammensatte navn:
        [
            {
                "original_input": "Tokke-Vinjevassdraget",
                "original_part": "Tokke",
                "matched_navn": "Tokkevassdraget",
                "matched_variant": "TokkevELV",
                "vassdragsnr": "123",
                "lat": 59.5,
                "long": 8.5,
                "score": 90,
                "match_type": "normalized",
                "is_composite": true
            },
            {
                "original_input": "Tokke-Vinjevassdraget",
                "original_part": "Vinje",
                "matched_navn": "Vinjevassdraget",
                ...
            }
        ]

    Eksempel:
        >>> matches = resolve_vassdrag("Tokke-Vinjevassdraget")
        >>> for m in matches:
        ...     print(f"{m['score']}: {m['matched_navn']} ({m['vassdragsnr']})")
    """
    # Sjekk om dette er et sammensatt navn
    if ' og ' in vassdragsforslag.lower() or '-' in vassdragsforslag:
        return resolve_composite_vassdrag(vassdragsforslag, ending_map_path, regine_index_path, max_results)
    else:
        return resolve_vassdrag_single(vassdragsforslag, ending_map_path, regine_index_path, max_results)


def resolve_composite_vassdrag(
    vassdragsforslag: str,
    ending_map_path: Path = DEFAULT_ENDING_MAP_PATH,
    regine_index_path: Path = DEFAULT_REGINE_INDEX_PATH,
    max_results: int = 10
) -> list[dict]:
    """
    Håndterer sammensatte vassdragsnavn (med '-' eller 'og').
    Eksempel: 'Tokke-Vinjevassdraget' → søker etter 'Tokke' og 'Vinje' separat.
    """
    # Split på " og " eller "-"
    parts = []
    if ' og ' in vassdragsforslag.lower():
        parts = re.split(r'\s+og\s+', vassdragsforslag, flags=re.IGNORECASE)
    elif '-' in vassdragsforslag:
        potential_parts = vassdragsforslag.split('-')

        # Filtrer bort vanlige suffixer og korte deler
        cleaned_parts = []
        for p in potential_parts:
            p = p.strip()
            if not p:
                continue
            lower_p = p.lower()
            # Hopp over suffixer som "vassdragene", "vassdraget", etc.
            if lower_p in ['vassdragene', 'vassdraget', 'vassdrag', 'kraftverk', 'verk']:
                continue
            # Hopp over veldig korte deler (< 3 tegn)
            if len(p) < 3:
                continue
            cleaned_parts.append(p)

        if len(cleaned_parts) >= 2:
            parts = cleaned_parts

    if not parts or len(parts) < 2:
        # Ikke et sammensatt navn, søk som enkelt navn
        return resolve_vassdrag_single(vassdragsforslag, ending_map_path, regine_index_path, max_results)

    # Søk etter hver del
    all_matches = []
    for part in parts:
        part = part.strip()
        if not part:
            continue

        matches = resolve_vassdrag_single(part, ending_map_path, regine_index_path, max_results)

        # Legg til metadata om at dette er del av sammensatt navn
        for match in matches:
            match["original_input"] = vassdragsforslag  # Overstyr til fullt navn
            match["original_part"] = part
            match["is_composite"] = True
            all_matches.append(match)

    # Sorter etter score
    all_matches.sort(key=lambda x: x["score"], reverse=True)
    return all_matches


if __name__ == "__main__":
    # Eksempel på bruk
    import sys

    if len(sys.argv) > 1:
        vassdragsnavn = " ".join(sys.argv[1:])
    else:
        vassdragsnavn = "Tokke-Vinjevassdraget"

    print(f"Søker etter: {vassdragsnavn}\n")

    matches = resolve_vassdrag(vassdragsnavn)

    if not matches:
        print("Ingen matcher funnet.")
    else:
        print(f"Fant {len(matches)} matcher:\n")
        for i, match in enumerate(matches, 1):
            # Vis bonuser hvis de finnes
            bonus_parts = []
            if match.get('vassdragsnr_bonus'):
                bonus_parts.append(f"+{match['vassdragsnr_bonus']} vassdragsnr")
            if match.get('prefix_bonus'):
                bonus_parts.append(f"+{match['prefix_bonus']} prefix")
            bonus_str = f" ({', '.join(bonus_parts)})" if bonus_parts else ""

            if match.get("is_composite"):
                print(f"{i}. [{match['score']}] {match['matched_navn']} (vassdragsnr: {match['vassdragsnr']}){bonus_str}")
                print(f"   Del: '{match['original_part']}' → '{match['matched_variant']}' ({match['match_type']})")
            else:
                print(f"{i}. [{match['score']}] {match['matched_navn']} (vassdragsnr: {match['vassdragsnr']}){bonus_str}")
                print(f"   Variant: '{match['matched_variant']}' ({match['match_type']})")
            print(f"   Koordinater: {match['lat']}, {match['long']}\n")
