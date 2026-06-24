#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

NS = {"gpml": "http://pathvisio.org/GPML/2021"}


def audit_file(gpml_file: Path, counts: Counter, by_scope: dict[str, Counter]) -> None:
    tree = ET.parse(gpml_file)
    root = tree.getroot()

    for prop in root.findall("gpml:Property", NS):
        key = prop.attrib.get("key")
        if key:
            counts[key] += 1
            by_scope["Pathway"][key] += 1

    for dn in root.findall("gpml:DataNodes/gpml:DataNode", NS):
        dn_type = dn.attrib.get("type", "DataNode")
        scope = f"DataNode:{dn_type}"

        for prop in dn.findall("gpml:Property", NS):
            key = prop.attrib.get("key")
            if key:
                counts[key] += 1
                by_scope[scope][key] += 1

    for interaction in root.findall("gpml:Interactions/gpml:Interaction", NS):
        for prop in interaction.findall("gpml:Property", NS):
            key = prop.attrib.get("key")
            if key:
                counts[key] += 1
                by_scope["Interaction"][key] += 1


def write_summary_csv(counts: Counter, out_file: Path) -> None:
    with out_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["property_key", "count"])

        for key, count in counts.most_common():
            writer.writerow([key, count])


def write_scope_csv(by_scope: dict[str, Counter], out_file: Path) -> None:
    with out_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["scope", "property_key", "count"])

        for scope in sorted(by_scope):
            for key, count in by_scope[scope].most_common():
                writer.writerow([scope, key, count])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit GPML Property key usage in pathway and reaction files."
    )
    parser.add_argument("--pathways-dir", default="input/gpml/renamed/pathways")
    parser.add_argument("--reactions-dir", default="input/gpml/renamed/reactions")
    parser.add_argument("--summary", default="output/audit/gpml_property_audit_summary.csv")
    parser.add_argument("--by-scope", default="output/audit/gpml_property_audit_by_scope.csv")

    args = parser.parse_args()

    counts: Counter = Counter()
    by_scope: dict[str, Counter] = defaultdict(Counter)

    gpml_files = list(Path(args.pathways_dir).glob("*.gpml"))
    gpml_files += list(Path(args.reactions_dir).glob("*.gpml"))

    for gpml_file in sorted(gpml_files):
        audit_file(gpml_file, counts, by_scope)

    Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    write_summary_csv(counts, Path(args.summary))
    write_scope_csv(by_scope, Path(args.by_scope))

    print(f"Audited GPML files: {len(gpml_files)}")
    print(f"Unique property keys: {len(counts)}")
    print(f"Wrote: {args.summary}")
    print(f"Wrote: {args.by_scope}")

    print()
    print("Top 20 property keys:")
    for key, count in counts.most_common(20):
        print(f"{key}\t{count}")


if __name__ == "__main__":
    main()