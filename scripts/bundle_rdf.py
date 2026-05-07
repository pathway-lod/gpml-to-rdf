#!/usr/bin/env python3
"""Bundle multiple Turtle files into a single file.

Each @prefix declaration is written exactly once at the top of the output
file regardless of how many source files contain it.  This avoids the
duplicate-prefix problem that arises when files are concatenated naively
with `find | xargs cat`.

Usage
-----
  python scripts/bundle_rdf.py \
      --input-dir output/rdf/core/pathways \
      --input-dir output/rdf/core/reactions \
      --output    output/bundles/all-plantcyc17.0.0-gpml2021.ttl
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def collect_prefixes(files: list[Path]) -> list[str]:
    """Return unique @prefix lines in first-seen order."""
    seen: dict[str, str] = {}
    for f in files:
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped.startswith("@prefix"):
                    break  # prefix block is always at the top; stop early
                parts = stripped.split()
                if len(parts) >= 2:
                    key = parts[1]  # e.g. "wp:"
                    if key not in seen:
                        seen[key] = stripped
    return list(seen.values())


def bundle(files: list[Path], output: Path) -> None:
    prefixes = collect_prefixes(files)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as out:
        for line in prefixes:
            out.write(line + "\n")
        out.write("\n")

        for f in files:
            with f.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if not line.strip().startswith("@prefix"):
                        out.write(line)

    print(f"Bundled {len(files)} files → {output}  ({output.stat().st_size // 1024} KB)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bundle TTL files with deduplicated @prefix declarations."
    )
    parser.add_argument(
        "--input-dir",
        dest="input_dirs",
        action="append",
        required=True,
        metavar="DIR",
        help="Directory to search for *.ttl files (may be given multiple times)",
    )
    parser.add_argument("--output", required=True, metavar="FILE")
    args = parser.parse_args()

    files: list[Path] = []
    for d in args.input_dirs:
        p = Path(d)
        if not p.is_dir():
            print(f"ERROR: not a directory: {p}", file=sys.stderr)
            return 1
        files.extend(sorted(p.rglob("*.ttl")))

    if not files:
        print("ERROR: no *.ttl files found in the given directories.", file=sys.stderr)
        return 1

    bundle(files, Path(args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
