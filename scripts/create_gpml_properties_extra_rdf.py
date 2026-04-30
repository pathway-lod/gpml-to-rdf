#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {"gpml": "http://pathvisio.org/GPML/2021"}

PMW_BASE = "http://rdf-plantmetwiki.bioinformatics.nl"
PMW_VOCAB = "http://rdf-plantmetwiki.bioinformatics.nl/vocab/"


def ttl_uri(uri: str) -> str:
    return f"<{uri}>"


def ttl_literal(value: str) -> str:
    value = html.unescape(value)
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    value = value.replace("\n", "\\n").replace("\r", "")
    return f'"{value}"'


def pathway_id_from_file(path: Path) -> str:
    return path.stem


def pathway_uri(pathway_id: str, version: str) -> str:
    return f"{PMW_BASE}/pathways/{pathway_id}_r{version}"


def datanode_uri(pathway_id: str, version: str, element_id: str) -> str:
    return f"{PMW_BASE}/Pathway/{pathway_id}_r{version}/DataNode/{element_id}"


def interaction_uri(pathway_id: str, version: str, element_id: str) -> str:
    return f"{PMW_BASE}/Pathway/{pathway_id}_r{version}/Interaction/{element_id}"


def property_lines(subject_uri: str, prop: ET.Element) -> list[str]:
    key = prop.attrib.get("key")
    value = prop.attrib.get("value")

    if not key or value is None:
        return []

    return [
        f"{ttl_uri(subject_uri)} pmw:gpmlProperty [",
        f"    pmw:key {ttl_literal(key)} ;",
        f"    pmw:value {ttl_literal(value)}",
        "] .",
        "",
    ]


def write_properties_ttl(gpml_file: Path, out_file: Path) -> None:
    tree = ET.parse(gpml_file)
    root = tree.getroot()

    pathway_id = pathway_id_from_file(gpml_file)
    version = root.attrib.get("version", "")
    pwy_uri = pathway_uri(pathway_id, version)

    lines: list[str] = [
        "@prefix pmw: <http://rdf-plantmetwiki.bioinformatics.nl/vocab/> .",
        "",
    ]

    # Pathway-level properties
    for prop in root.findall("gpml:Property", NS):
        lines.extend(property_lines(pwy_uri, prop))

    # DataNode-level properties
    for dn in root.findall("gpml:DataNodes/gpml:DataNode", NS):
        element_id = dn.attrib.get("elementId")
        if not element_id:
            continue

        subject = datanode_uri(pathway_id, version, element_id)

        for prop in dn.findall("gpml:Property", NS):
            lines.extend(property_lines(subject, prop))

    # Interaction-level properties
    for interaction in root.findall("gpml:Interactions/gpml:Interaction", NS):
        element_id = interaction.attrib.get("elementId")
        if not element_id:
            continue

        subject = interaction_uri(pathway_id, version, element_id)

        for prop in interaction.findall("gpml:Property", NS):
            lines.extend(property_lines(subject, prop))

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(lines), encoding="utf-8")


def process_directory(input_dir: Path, output_dir: Path) -> int:
    count = 0
    for gpml in sorted(input_dir.glob("*.gpml")):
        write_properties_ttl(gpml, output_dir / f"{gpml.stem}.ttl")
        count += 1
    return count


def aggregate_ttls(output_root: Path, aggregate_file: Path) -> None:
    ttl_files = sorted(output_root.rglob("*.ttl"))

    with aggregate_file.open("w", encoding="utf-8") as out:
        for ttl in ttl_files:
            out.write(ttl.read_text(encoding="utf-8"))
            out.write("\n")

    print(f"Aggregated {len(ttl_files)} TTL files into {aggregate_file}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create PlantMetWiki extra RDF preserving GPML key-value Properties."
    )
    parser.add_argument("--pathways-dir", default="orig-pw-renamed")
    parser.add_argument("--reactions-dir", default="orig-react-renamed")
    parser.add_argument("--output-dir", default="extra-properties")
    parser.add_argument(
        "--aggregate-file",
        default="all_gpml_properties_extra-plantcyc17.0.0-gpml2021.ttl",
    )
    parser.add_argument("--no-aggregate", action="store_true")

    args = parser.parse_args()

    output_root = Path(args.output_dir)

    pathway_count = process_directory(
        Path(args.pathways_dir),
        output_root / "pathways",
    )

    reaction_count = process_directory(
        Path(args.reactions_dir),
        output_root / "reactions",
    )

    print(f"Pathway property TTL files:  {pathway_count}")
    print(f"Reaction property TTL files: {reaction_count}")

    if not args.no_aggregate:
        aggregate_ttls(output_root, Path(args.aggregate_file))


if __name__ == "__main__":
    main()