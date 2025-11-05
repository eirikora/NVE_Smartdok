"""Ny og strukturert versjon av verktøy for å identifisere vassdragsnavn.

Modulen tilbyr funksjonen :func:`resolve_vassdrag` som tar en tekststreng med ett
eller flere vassdragsnavn og rangerer sannsynlige treff fra NVEs
``INDEX_regine.json``. Strategien følger retningslinjene i brukerhistorien:

1. Del opp teksten i individuelle vassdragsnavn.
2. Lag søkekandidater for hvert navn (original, stamme, varianter med
   «vassdraget» osv.).
3. Normaliser navnekandidatene ved å erstatte haleord (elv, bekk, foss …)
   med generiske kategorier («ELV», «VANN», «FJORD»).
4. Forsøk eksakte oppslag mot ``navn``-feltet i indeksen (100 poeng).
5. Forsøk eksakte oppslag mot ``navn_normalisert`` (90 poeng), og varianter
   med byttet hale (60 poeng).
6. Utfør fonetisk matching som fallback (50 poeng + justeringer).
7. Gi nærmeste treff en bonus dersom en referansekoordinat oppgis.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from math import atan2, cos, radians, sin, sqrt
from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence

DEFAULT_ENDING_MAP_PATH = Path(__file__).parent / "ending_map.json"
DEFAULT_REGINE_INDEX_PATH = Path(__file__).parent / "INDEX_regine.json"


@dataclass
class MatchResult:
    """Beskrivelse av et match-resultat."""

    input_name: str
    candidate: str
    match_type: str
    score: int
    entry: dict
    coord_bonus: int = 0
    base_score: int = 0

    def as_dict(self) -> dict:
        """Returner resultatet som et serialiserbart dictionary."""

        return {
            "input_name": self.input_name,
            "candidate": self.candidate,
            "match_type": self.match_type,
            "score": self.score,
            "vassdragsnr": self.entry.get("vassdragsnr"),
            "matched_navn": self.entry.get("navn"),
            "navn_normalisert": self.entry.get("navn_normalisert"),
            "lat": self.entry.get("lat"),
            "long": self.entry.get("long"),
            "coord_bonus": self.coord_bonus,
            "base_score": self.base_score,
        }


@lru_cache(maxsize=1)
def load_ending_map(path: Path = DEFAULT_ENDING_MAP_PATH) -> dict[str, str]:
    """Last mapping fra haleord til kategorier (ELV/VANN/FJORD/... )."""

    if not path.exists():  # pragma: no cover - defensiv beskyttelse
        raise FileNotFoundError(f"Fant ikke ending_map.json på {path}")

    with path.open(encoding="utf-8") as handle:
        data: dict[str, str] = json.load(handle)

    return data


@lru_cache(maxsize=1)
def load_regine_index(path: Path = DEFAULT_REGINE_INDEX_PATH) -> list[dict]:
    """Last ``INDEX_regine.json`` som en liste av dictionaries."""

    if not path.exists():  # pragma: no cover - defensiv beskyttelse
        raise FileNotFoundError(
            "Fant ikke INDEX_regine.json. Kør build_regine_index.py først?"
        )

    with path.open(encoding="utf-8") as handle:
        entries: list[dict] = json.load(handle)

    return entries


def resolve_vassdrag(
    text: str,
    *,
    regine_index: Sequence[dict] | None = None,
    ending_map: dict[str, str] | None = None,
    coord: tuple[float, float] | None = None,
    debug: bool = False,
    debug_log: Callable[[str], None] | None = None,
) -> list[dict]:
    """Finn sannsynlige vassdrag for navn som beskrives i ``text``.

    Returnerer en liste med ordbøker (en per match) sortert etter poengsum.
    Hvert element inneholder ``input_name`` (original delstreng),
    ``candidate`` (søket som ga treff), ``match_type`` og metadata fra
    indeksen. Angi ``coord=(lon, lat)`` for å tildele nærhetsbonus.
    """

    if not text.strip():
        return []

    def log(message: str) -> None:
        if not debug:
            return
        if debug_log is not None:
            debug_log(message)
        else:
            print(f"[debug] {message}")

    log(f"Start søk for tekst: {text!r}")
    if coord is not None:
        log(f"Referansekoordinat: lon={coord[0]}, lat={coord[1]}")

    ending_map = ending_map or load_ending_map()
    regine_index = list(regine_index or load_regine_index())

    suffixes = _collect_suffixes(ending_map)
    all_results: list[MatchResult] = []

    raw_names = split_vassdrag_names(text, suffixes=suffixes)
    log(f"Identifiserte delnavn: {raw_names}")

    for raw_name in raw_names:
        log(f"Behandler vassdragsnavn: {raw_name!r}")
        candidate_results = _score_single_name(
            raw_name, regine_index, ending_map, suffixes, log
        )
        all_results.extend(candidate_results)

    if coord is not None:
        _apply_coordinate_bonus(all_results, coord, log if debug else None)

    # Sorter globalt på score (synkende) og vassdragsnummer som sekundær nøkkel
    all_results.sort(key=lambda item: (-item.score, item.entry.get("vassdragsnr")))
    return [result.as_dict() for result in all_results]


def split_vassdrag_names(text: str, *, suffixes: Sequence[str]) -> list[str]:
    """Del opp ``text`` i separate vassdragsnavn."""

    normalized = re.sub(r"\s+(?:og|&|\+/)\s+", ",", text, flags=re.IGNORECASE)
    normalized = normalized.replace("/", ",")
    parts = [part.strip(" ,") for part in normalized.split(",")]
    parts = [part for part in parts if part]

    expanded: list[str] = []
    for part in parts:
        expanded.extend(_expand_hyphenated(part, suffixes=suffixes))

    return expanded


def _expand_hyphenated(name: str, *, suffixes: Sequence[str]) -> list[str]:
    """Utvid kombinasjonsnavn som «Tokke-Vinjevassdraget» til to navn."""

    if "-" not in name:
        return [name]

    pieces = [piece.strip() for piece in name.split("-") if piece.strip()]
    if len(pieces) < 2:
        return [name]

    last_stem, last_suffix = _split_suffix(pieces[-1], suffixes)
    suffix_only = False
    if not last_suffix:
        last_lower = pieces[-1].lower()
        if last_lower in suffixes:
            last_suffix = pieces[-1]
            suffix_only = True
        else:
            return [name]

    expanded = []
    seen: set[str] = set()
    for idx, piece in enumerate(pieces):
        stem, suffix = _split_suffix(piece, suffixes)
        piece_lower = piece.lower()
        if suffix:
            if piece not in seen:
                seen.add(piece)
                expanded.append(piece)
            continue

        if (
            suffix_only
            and idx == len(pieces) - 1
            and piece_lower == last_suffix.lower()
        ):
            continue

        base = stem or piece
        combined = _join_stem_suffix(base, last_suffix)
        if combined not in seen:
            seen.add(combined)
            expanded.append(combined)

    return expanded


def _collect_suffixes(ending_map: dict[str, str]) -> list[str]:
    """Lag en sortert liste over kjente haler for effektiv matching."""

    extra_suffixes = ["vassdraget", "vassdrag", "vassdragene", "vassdragets"]
    suffixes = set(ending_map.keys()) | {s.lower() for s in extra_suffixes}
    return sorted(suffixes, key=len, reverse=True)


def _split_suffix(word: str, suffixes: Sequence[str]) -> tuple[str, str]:
    """Del ``word`` i (stamme, hale) hvis halen er kjent."""

    lowered = word.lower()
    for suffix in suffixes:
        if lowered.endswith(suffix) and len(lowered) > len(suffix):
            cut = len(word) - len(suffix)
            return word[:cut], word[cut:]
    return word, ""


def _join_stem_suffix(stem: str, suffix: str) -> str:
    """Kombiner en stamme og en hale uten å introdusere ekstra mellomrom."""

    stem = stem.strip()
    if not stem:
        return suffix
    if stem.endswith("-"):
        stem = stem[:-1]
    if suffix.startswith("-"):
        suffix = suffix[1:]
    return f"{stem}{suffix}" if not stem.endswith(" ") else f"{stem}{suffix}"


def _generate_original_candidates(name: str, suffixes: Sequence[str]) -> list[str]:
    """Lag navnekandidater basert på original skrivemåte."""

    trimmed = name.strip()
    if not trimmed:
        return []

    candidates: list[str] = []
    seen: set[str] = set()

    def _add(candidate: str) -> None:
        candidate = candidate.strip()
        if candidate and candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)

    _add(trimmed)

    stem, suffix = _split_suffix(trimmed, suffixes)
    if stem and stem != trimmed:
        _add(stem)

    # «Glomma» -> «Glommavassdraget»
    if not trimmed.lower().endswith("vassdraget"):
        base = stem or trimmed
        _add(_join_stem_suffix(base, "vassdraget"))
        if base:
            base_s = base.rstrip()
            if not base_s.lower().endswith("s"):
                base_s = f"{base_s}s"
            _add(_join_stem_suffix(base_s, "vassdraget"))

    # Legg til siste ord (og variant med vassdraget) for sammensatte navn
    if " " in trimmed:
        last_word = trimmed.split()[-1]
        _add(last_word)
        if not last_word.lower().endswith("vassdraget"):
            _add(_join_stem_suffix(last_word, "vassdraget"))
            last_base = last_word.rstrip()
            if last_base:
                if not last_base.lower().endswith("s"):
                    last_base = f"{last_base}s"
                _add(_join_stem_suffix(last_base, "vassdraget"))

    return candidates


def _normalize_name(
    name: str,
    ending_map: dict[str, str],
    suffixes: Sequence[str],
) -> tuple[str, str | None, str]:
    """Returner (normalisert navn, kategori, stamme)."""

    if not name:
        return "", None, ""

    collapse = {
        "ELV": "ELV",
        "ELV_SAMISK": "ELV",
        "VANN": "VANN",
        "VANN_SAMISK": "VANN",
        "FJORD": "FJORD",
        "DAL": "DAL",
        "FJELL": "FJELL",
    }

    words = name.split()
    normalized_words: list[str] = []
    last_category: str | None = None

    for word in words:
        stem, suffix = _split_suffix(word, suffixes)
        category = None
        if suffix:
            mapped = ending_map.get(suffix.lower())
            if mapped:
                category = collapse.get(mapped, mapped)
        if category:
            normalized_words.append(f"{stem}{category}")
            last_category = category
        else:
            normalized_words.append(word)

    normalized = " ".join(normalized_words)

    # Finn stamme (uten siste kategori-ord)
    stem_normalized = normalized
    match = re.search(r"(.*?)(ELV|VANN|FJORD|DAL|FJELL)(?:\b|$)", normalized)
    if match:
        stem_normalized = match.group(1).strip()

    return normalized, last_category, stem_normalized


def _generate_normalized_candidates(
    candidates: Iterable[str],
    ending_map: dict[str, str],
    suffixes: Sequence[str],
) -> dict[str, tuple[str | None, str]]:
    """Lag mapping fra normalisert navn til (kategori, stamme)."""

    normalized: dict[str, tuple[str | None, str]] = {}
    for candidate in candidates:
        normalized_name, category, stem = _normalize_name(candidate, ending_map, suffixes)
        if normalized_name:
            normalized[normalized_name] = (category, stem)
    return normalized


def _score_single_name(
    name: str,
    regine_index: Sequence[dict],
    ending_map: dict[str, str],
    suffixes: Sequence[str],
    debug_log: Callable[[str], None] | None = None,
) -> list[MatchResult]:
    """Beregn matches for ett vassdragsnavn."""

    candidates = _generate_original_candidates(name, suffixes)
    if debug_log:
        debug_log(f"  Originale kandidater: {candidates}")
    normalized_candidates = _generate_normalized_candidates(
        candidates, ending_map, suffixes
    )
    if debug_log:
        debug_log(
            "  Normaliserte kandidater: "
            + ", ".join(
                f"{norm!r}->{info}"
                for norm, info in normalized_candidates.items()
            )
        )

    best_per_vassdrag: dict[str, MatchResult] = {}

    def register(entry: dict, score: int, candidate: str, match_type: str) -> None:
        key = str(entry.get("vassdragsnr"))
        adjusted_score = score
        vnr = entry.get("vassdragsnr")
        if isinstance(vnr, str) and vnr:
            penalty = max(0, len(vnr) - 3) * 5
            adjusted_score -= penalty
        else:
            penalty = 0
        # Ensure 'message' is always defined so static analysis knows it's a str
        message = ""
        if debug_log:
            message = (
                f"  -> {match_type} treff for kandidat {candidate!r} ga {score} poeng"
                f" mot {entry.get('navn')} (vnr {vnr})"
            )
            if penalty:
                message += f", penalty {penalty} -> {adjusted_score}"
            else:
                message += f" (justert {adjusted_score})"
        result = MatchResult(
            name,
            candidate,
            match_type,
            adjusted_score,
            entry,
            coord_bonus=0,
            base_score=adjusted_score,
        )
        current = best_per_vassdrag.get(key)
        if current is None or adjusted_score > current.score:
            best_per_vassdrag[key] = result
            if debug_log:
                debug_log(message + " [ny beste]")
        else:
            if debug_log:
                message = (
                    f"  -> {match_type} treff for kandidat {candidate!r} ga {score} poeng"
                    f" mot {entry.get('navn')} (vnr {vnr})"
                )
                if penalty:
                    message += f", penalty {penalty} -> {adjusted_score}"
                else:
                    message += f" (justert {adjusted_score})"
                debug_log(message + f" [forkastet, eksisterende score {current.score}]")

    # Steg 4 – eksakt match på «navn»
    for candidate in candidates:
        for entry in _lookup_exact(regine_index, "navn", candidate):
            if debug_log:
                debug_log(f"  Søker eksakt i 'navn' med kandidat {candidate!r}")
            register(entry, 100, candidate, "navn")

    # Steg 5 – normaliserte matcher
    for normalized_name, (category, _stem) in normalized_candidates.items():
        for entry in _lookup_exact(regine_index, "navn_normalisert", normalized_name):
            if debug_log:
                debug_log(
                    f"  Søker eksakt i 'navn_normalisert' med {normalized_name!r}"
                )
            register(entry, 90, normalized_name, "navn_normalisert")

        # Prøv hale-bytte (ELV <-> VANN/FJORD)
        alt_names = _swap_normalized_tail(normalized_name, category)
        for alt_name in alt_names:
            for entry in _lookup_exact(regine_index, "navn_normalisert", alt_name):
                if debug_log:
                    debug_log(
                        f"  Søker med haleswap {normalized_name!r} -> {alt_name!r}"
                    )
                register(entry, 60, alt_name, "navn_normalisert_hale")

    # Steg 6 – fonetisk matching på originale kandidater
    for candidate in candidates:
        phonetic_matches = _phonetic_matches(
            candidate, regine_index, ending_map, suffixes, debug_log
        )
        for entry, score_adjustment in phonetic_matches:
            register(entry, 50 + score_adjustment, candidate, "fonetisk")

    return list(best_per_vassdrag.values())

def _apply_coordinate_bonus(
    results: Sequence[MatchResult],
    coord: tuple[float, float],
    debug_log: Callable[[str], None] | None = None,
) -> None:
    lon_ref, lat_ref = coord
    candidates: list[tuple[MatchResult, float]] = []

    for result in results:
        lon = result.entry.get("long")
        lat = result.entry.get("lat")
        if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
            continue
        distance = _haversine_distance_km(lon_ref, lat_ref, lon, lat)
        candidates.append((result, distance))

    if not candidates:
        if debug_log:
            debug_log("Ingen gyldige koordinater for bonusberegning.")
        return

    candidates.sort(key=lambda item: item[1])
    bonuses = [25, 20, 15, 10, 5]

    for idx, (result, distance) in enumerate(candidates):
        bonus = bonuses[idx] if idx < len(bonuses) else 0
        if bonus <= 0:
            break
        result.score += bonus
        result.coord_bonus += bonus
        if debug_log:
            debug_log(
                f"Koordinatbonus +{bonus}p til {result.entry.get('navn')} "
                f"(vnr {result.entry.get('vassdragsnr')}) "
                f"med avstand {distance:.2f} km "
                f"(score {result.base_score} -> {result.score})"
            )

def _lookup_exact(entries: Sequence[dict], field: str, value: str) -> Iterator[dict]:
    value_lower = value.casefold()
    for entry in entries:
        field_value = entry.get(field)
        if isinstance(field_value, str) and field_value.casefold() == value_lower:
            yield entry


def _swap_normalized_tail(name: str, category: str | None) -> list[str]:
    if not category:
        return []
    if category not in {"ELV", "VANN", "FJORD"}:
        return []

    swaps = {
        "ELV": ("VANN", "FJORD"),
        "VANN": ("ELV", "FJORD"),
        "FJORD": ("ELV", "VANN"),
    }
    pattern = re.compile(rf"(.*?){category}(\b|$)")
    match = pattern.search(name)
    if not match:
        return []

    prefix = match.group(1)
    return [f"{prefix}{replacement}" for replacement in swaps[category]]


def _haversine_distance_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Beregn avstand mellom to punkter med Haversine-formelen."""

    radius = 6371.0  # jordradius i km
    lon1_rad, lat1_rad = radians(lon1), radians(lat1)
    lon2_rad, lat2_rad = radians(lon2), radians(lat2)

    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad

    a = sin(dlat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return radius * c


def _phonetic_matches(
    candidate: str,
    entries: Sequence[dict],
    ending_map: dict[str, str],
    suffixes: Sequence[str],
    debug_log: Callable[[str], None] | None = None,
) -> list[tuple[dict, int]]:
    candidate_phonetic = _phonetic_signature(candidate)
    if debug_log:
        debug_log(f"  Fonetisk søk for {candidate!r} (signatur {candidate_phonetic!r})")
    candidate_norm, candidate_category, candidate_stem = _normalize_name(
        candidate, ending_map, suffixes
    )
    candidate_stem_clean = _clean_letters(candidate_stem)

    matches: list[tuple[dict, int]] = []
    if not candidate_phonetic:
        if debug_log:
            debug_log("    Ingen fonetisk signatur, hopper over.")
        return matches

    for entry in entries:
        navn = entry.get("navn")
        if not isinstance(navn, str):
            continue

        if navn.casefold() == candidate.casefold():
            continue

        if _phonetic_signature(navn) != candidate_phonetic:
            continue

        entry_norm, entry_category, entry_stem = _normalize_name(navn, ending_map, suffixes)
        entry_stem_clean = _clean_letters(entry_stem)

        if not _stems_within_tolerance(candidate_stem_clean, entry_stem_clean):
            if debug_log:
                debug_log(
                    f"    Forkastet fonetisk treff {navn!r}: stamme {entry_stem_clean!r}"
                    f" vs {candidate_stem_clean!r}"
                )
            continue

        score = _startswith_bonus(candidate, navn)
        if not _first_letter_matches(candidate, navn):
            score -= 50

        # Bonus hvis kategoriene matcher (typisk ELV/VANN)
        if candidate_category and entry_category and candidate_category == entry_category:
            score += 5

        if debug_log:
            debug_log(
                f"    Fonetisk treff {navn!r} med justering {score}"
            )
        matches.append((entry, score))

    return matches


def _phonetic_signature(text: str) -> str:
    if not text:
        return ""

    lowered = text.casefold()
    replacements = (
        ("ch", "k"),
        ("ph", "f"),
        ("th", "t"),
        ("aa", "å"),
        ("-", ""),
        (" ", ""),
    )
    for old, new in replacements:
        lowered = lowered.replace(old, new)

    if lowered.startswith("c"):
        lowered = "k" + lowered[1:]

    result: list[str] = []
    previous_char = ""
    for char in lowered:
        if char == previous_char and char.isalpha():
            continue
        previous_char = char
        result.append(char)

    return "".join(result)


def _stems_within_tolerance(candidate: str, entry: str) -> bool:
    if not candidate or not entry:
        return False

    length = max(len(candidate), len(entry))
    if length <= 3:
        allowed = 0
    elif length <= 6:
        allowed = 1
    else:
        allowed = 2

    return _levenshtein(candidate, entry) <= allowed


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a

    if not b:
        return len(a)

    previous_row = list(range(len(b) + 1))
    for i, char_a in enumerate(a, 1):
        current_row = [i]
        for j, char_b in enumerate(b, 1):
            insert = current_row[j - 1] + 1
            delete = previous_row[j] + 1
            substitute = previous_row[j - 1] + (char_a != char_b)
            current_row.append(min(insert, delete, substitute))
        previous_row = current_row
    return previous_row[-1]


def _startswith_bonus(candidate: str, navn: str) -> int:
    cand = _clean_letters(candidate)
    target = _clean_letters(navn)
    bonus = 0
    for char_cand, char_target in zip(cand, target):
        if char_cand == char_target:
            bonus += 3
        else:
            break
    return bonus


def _first_letter_matches(candidate: str, navn: str) -> bool:
    cand = _clean_letters(candidate)
    target = _clean_letters(navn)
    if not cand or not target:
        return False
    return cand[0] == target[0]


def _clean_letters(text: str) -> str:
    return re.sub(r"[^a-zæøå]", "", text.casefold())


def _cli(argv: Sequence[str]) -> int:
    debug = False
    lon: float | None = None
    lat: float | None = None
    args: list[str] = []

    i = 1
    while i < len(argv):
        item = argv[i]
        if item == "--debug":
            debug = True
            i += 1
            continue
        if item == "--lon":
            if i + 1 >= len(argv):
                print("Flagget --lon krever en verdi.", file=sys.stderr)
                return 1
            try:
                lon = float(argv[i + 1])
            except ValueError:
                print("Lon må være et tall.", file=sys.stderr)
                return 1
            i += 2
            continue
        if item == "--lat":
            if i + 1 >= len(argv):
                print("Flagget --lat krever en verdi.", file=sys.stderr)
                return 1
            try:
                lat = float(argv[i + 1])
            except ValueError:
                print("Lat må være et tall.", file=sys.stderr)
                return 1
            i += 2
            continue
        args.append(item)
        i += 1

    if (lon is None) != (lat is None):
        print("Oppgi både --lon og --lat for koordinatbonus.", file=sys.stderr)
        return 1

    coord_arg = (lon, lat) if lon is not None and lat is not None else None

    if args:
        query = " ".join(args).strip()
    else:
        query = "Tokke-Vinjevassdraget"

    if not query:
        print("Oppgi et vassdragsnavn å slå opp.", file=sys.stderr)
        return 1

    print(f"Søker etter: {query}\n")

    debug_lines: list[str] = []
    matches = resolve_vassdrag(
        query,
        coord=coord_arg,
        debug=debug,
        debug_log=debug_lines.append if debug else None,
    )
    if debug and debug_lines:
        print("Debug-logg:")
        for line in debug_lines:
            print(line)
        print()
    if not matches:
        print("Ingen matcher funnet.")
        return 0

    total = len(matches)
    print(f"Fant {total} matcher:\n")

    max_display = 7
    display_set = matches[:max_display]
    if total > max_display:
        print(f"Viser de {max_display} beste treffene:\n")

    for idx, match in enumerate(display_set, 1):
        navn = match.get("matched_navn") or "(uten navn)"
        vnr = match.get("vassdragsnr") or "?"
        score = match.get("score", 0)
        print(f"{idx}. [{score}] {navn} (vassdragsnr: {vnr})")

        candidate = match.get("candidate") or ""
        input_name = match.get("input_name") or ""
        match_type = match.get("match_type") or "ukjent"
        print(f"   Variant: '{input_name}' -> '{candidate}' ({match_type})")

        base_score = match.get("base_score")
        if isinstance(base_score, (int, float)) and base_score != score:
            print(f"   Basisscore: {base_score}")

        coord_bonus = match.get("coord_bonus") or 0
        if coord_bonus:
            print(f"   Koordinatbonus: +{coord_bonus}")

        lat = match.get("lat")
        lon = match.get("long")
        if lat is not None and lon is not None:
            print(f"   Koordinater: {lat}, {lon}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv))
