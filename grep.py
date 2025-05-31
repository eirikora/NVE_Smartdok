#!/usr/bin/env python3
import sys
from pathlib import Path

def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {Path(sys.argv[0]).name} <search_string> <filename>", file=sys.stderr)
        sys.exit(1)

    search, filename = sys.argv[1], sys.argv[2]

    try:
        with open(filename, encoding="utf-8") as fh:
            for line in fh:
                if search in line:          # case-sensitive match
                    print(line.rstrip("\n"))
    except FileNotFoundError:
        print(f"File not found: {filename}", file=sys.stderr)
        sys.exit(1)
    except OSError as err:
        print(f"Error reading {filename}: {err}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()