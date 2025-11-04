#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Leser common_endings.txt og grupperer alle endinger som deler samme suffiks.

For eksempel:
  bajåkka,5
  gajåkka,4
  njajåkka,3
  ...
→ gir én rad:  jåkka,12

Det samme for døla, lla, la osv.
"""

from pathlib import Path
from collections import defaultdict

def read_input(path: Path):
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ending, count = line.split(",", 1)
                ending = ending.strip().strip("'").strip("’")
                count = int(count.strip())
                if ending:
                    rows.append((ending, count))
            except ValueError:
                continue
    return rows


def find_common_suffixes(rows, min_len=3, max_len=10, min_count=2):
    """Finn de lengste suffiksene som forekommer på tvers av flere rader."""
    suffix_map = defaultdict(list)
    for ending, cnt in rows:
        e = ending.lower()
        for i in range(min_len, min(max_len, len(e)) + 1):
            suf = e[-i:]
            suffix_map[suf].append((ending, cnt))

    # filtrer bare de suffiksene som har flere forskjellige endinger
    candidates = {suf: vals for suf, vals in suffix_map.items() if len(vals) >= min_count}

    # behold bare de lengste unike (ikke delmengde av en lengre)
    longest_unique = {}
    for suf in sorted(candidates, key=lambda s: (-len(s), s)):
        if not any(longer.endswith(suf) for longer in longest_unique):
            longest_unique[suf] = candidates[suf]

    # summer counts
    summarized = {suf: sum(cnt for _, cnt in vals) for suf, vals in longest_unique.items()}
    return summarized


def main():
    in_path = Path("common_endings.txt")
    out_path = Path("common_endings_summary.txt")

    if not in_path.exists():
        print(f"❌ Fant ikke {in_path}")
        return 1

    rows = read_input(in_path)
    if not rows:
        print("⚠️ Ingen data å behandle.")
        return 0

    summarized = find_common_suffixes(rows)

    # legg til de som ikke havnet i noen felles gruppe (enkeltstående)
    all_suffix_members = {suf for suf, _ in summarized.items()}
    grouped = set()
    for ending, _ in rows:
        for suf in all_suffix_members:
            if ending.endswith(suf):
                grouped.add(ending)
                break
    for ending, cnt in rows:
        if ending not in grouped:
            summarized[ending] = cnt

    # backsortér slik at ...a før ...b
    output = sorted(summarized.items(), key=lambda x: x[0][::-1])

    with out_path.open("w", encoding="utf-8") as f:
        for suf, total in output:
            f.write(f"{suf},{total}\n")

    print(f"✅ Skrev {len(output)} rader til {out_path}")
    for suf, total in list(output)[:15]:
        print(f"  {suf}: {total}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
