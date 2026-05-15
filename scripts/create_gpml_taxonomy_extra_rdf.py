#!/usr/bin/env python3

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote


import re as _re

NS = {"gpml": "http://pathvisio.org/GPML/2021"}
_TAX_PREFIX = _re.compile(r"^TAX-(\d+)$")

PMW_BASE = "http://rdf-plantmetwiki.bioinformatics.nl"
VIRIDIPLANTAE_TAXON = "33090"

DATASOURCE_URI = {
    # Proteins / genes
    "uniprot": "https://identifiers.org/uniprot/",
    "Uniprot": "https://identifiers.org/uniprot/",
    "Uniprot-TrEMBL": "https://identifiers.org/uniprot/",
    "plantcyc": "https://identifiers.org/plantcyc/",
    "PlantCyc": "https://identifiers.org/plantcyc/",
    "TAIR gene name": "https://identifiers.org/tair.name/",
    "tair.name": "https://identifiers.org/tair.name/",
    "Entrez Gene": "https://identifiers.org/ncbigene/",
    # Metabolites
    "InChIKey": "https://identifiers.org/inchikey/",
    "ChEBI": "https://identifiers.org/chebi/",
    "MetaNetX": "https://identifiers.org/metanetx.chemical/",
    "PubChem-compound": "https://identifiers.org/pubchem.compound/",
    "KEGG Compound": "https://identifiers.org/kegg.compound/",
    "HMDB": "https://identifiers.org/hmdb/",
}


def ttl_uri(uri: str) -> str:
    return f"<{uri}>"


def safe_identifier(identifier: str) -> str:
    return quote(identifier.strip(), safe=":/#._-~")


def pathway_uri(pathway_id: str, version: str) -> str:
    return f"{PMW_BASE}/pathways/{pathway_id}_r{version}"


def datanode_uri(pathway_id: str, version: str, element_id: str) -> str:
    return f"{PMW_BASE}/Pathway/{pathway_id}_r{version}/DataNode/{element_id}"


def xref_uri(datasource: str | None, identifier: str | None) -> str | None:
    if not datasource or not identifier:
        return None

    base = DATASOURCE_URI.get(datasource)
    if not base:
        return None

    return base + safe_identifier(identifier)


def extract_taxonomy_map(root: ET.Element) -> dict[str, str]:
    taxonomy: dict[str, str] = {}

    for ann in root.findall("gpml:Annotations/gpml:Annotation", NS):
        ann_id = ann.attrib.get("elementId")
        ann_type = ann.attrib.get("type")
        xref = ann.find("gpml:Xref", NS)

        if not ann_id or ann_type != "Taxonomy" or xref is None:
            continue

        identifier = xref.attrib.get("identifier")
        datasource = xref.attrib.get("dataSource")

        if datasource == "NCBI Taxonomy" and identifier:
            taxonomy[ann_id] = identifier
        elif datasource == "Taxonomy" and identifier:
            # TAX-XXXX is BioCyc's encoding of NCBI Taxonomy IDs
            m = _TAX_PREFIX.match(identifier)
            if m:
                taxonomy[ann_id] = m.group(1)

    return taxonomy


def write_taxonomy_ttl(gpml_file: Path, out_file: Path) -> None:
    tree = ET.parse(gpml_file)
    root = tree.getroot()

    pathway_id = gpml_file.stem
    version = root.attrib.get("version", "")
    pwy_uri = pathway_uri(pathway_id, version)

    taxonomy = extract_taxonomy_map(root)

    lines: list[str] = [
        "@prefix wp: <http://vocabularies.wikipathways.org/wp#> .",
        "@prefix ncbi: <http://purl.obolibrary.org/obo/NCBITaxon_> .",
        "",
        f"{ttl_uri(pwy_uri)} wp:organism ncbi:{VIRIDIPLANTAE_TAXON} .",
        "",
    ]

    for dn in root.findall("gpml:DataNodes/gpml:DataNode", NS):
        dn_type = dn.attrib.get("type")
        if dn_type not in {"GeneProduct", "Protein", "Metabolite"}:
            continue

        element_id = dn.attrib.get("elementId")
        if not element_id:
            continue

        tax_ids: set[str] = set()

        for ann_ref in dn.findall("gpml:AnnotationRef", NS):
            ref = ann_ref.attrib.get("elementRef")
            if ref and ref in taxonomy:
                tax_ids.add(taxonomy[ref])

        if not tax_ids:
            continue

        gpml_node_uri = datanode_uri(pathway_id, version, element_id)

        xref = dn.find("gpml:Xref", NS)
        biological_entity_uri = None

        if xref is not None:
            biological_entity_uri = xref_uri(
                xref.attrib.get("dataSource"),
                xref.attrib.get("identifier"),
            )

        for tax_id in sorted(tax_ids):
            lines.append(f"{ttl_uri(gpml_node_uri)} wp:organism ncbi:{tax_id} .")

            if biological_entity_uri:
                lines.append(
                    f"{ttl_uri(biological_entity_uri)} wp:organism ncbi:{tax_id} ."
                )

        lines.append("")

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(lines), encoding="utf-8")


def process_directory(input_dir: Path, output_dir: Path) -> int:
    count = 0

    for gpml_file in sorted(input_dir.glob("*.gpml")):
        write_taxonomy_ttl(gpml_file, output_dir / f"{gpml_file.stem}.ttl")
        count += 1

    return count


def aggregate_ttls(output_root: Path, aggregate_file: Path) -> None:
    ttl_files = sorted(output_root.rglob("*.ttl"))

    # Collect unique @prefix lines in first-seen order so each prefix
    # appears exactly once at the top of the bundle.
    seen_prefixes: dict[str, str] = {}
    for ttl_file in ttl_files:
        with ttl_file.open(encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped.startswith("@prefix"):
                    break
                parts = stripped.split()
                if len(parts) >= 2 and parts[1] not in seen_prefixes:
                    seen_prefixes[parts[1]] = stripped

    with aggregate_file.open("w", encoding="utf-8") as out:
        for prefix_line in seen_prefixes.values():
            out.write(prefix_line + "\n")
        out.write("\n")
        for ttl_file in ttl_files:
            with ttl_file.open(encoding="utf-8") as fh:
                for line in fh:
                    if not line.strip().startswith("@prefix"):
                        out.write(line)

    print(f"Aggregated {len(ttl_files)} TTL files into {aggregate_file}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create PlantMetWiki taxonomy extra RDF from GPML pathway and "
            "reaction files. Adds Viridiplantae at pathway/reaction level and "
            "specific NCBI taxa to GeneProduct/Protein nodes."
        )
    )

    parser.add_argument("--pathways-dir", default="input/gpml/renamed/pathways")
    parser.add_argument("--reactions-dir", default="input/gpml/renamed/reactions")
    parser.add_argument("--output-dir", default="output/rdf/taxonomy-extra")
    parser.add_argument(
        "--aggregate-file",
        default="output/bundles/all_gpml_taxonomy_extra-plantcyc17.0.0-gpml2021.ttl",
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

    print(f"Pathway taxonomy TTL files:  {pathway_count}")
    print(f"Reaction taxonomy TTL files: {reaction_count}")

    if not args.no_aggregate:
        aggregate_ttls(output_root, Path(args.aggregate_file))


if __name__ == "__main__":
    main()