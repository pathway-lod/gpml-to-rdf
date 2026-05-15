#!/usr/bin/env python3
"""
Create OWL sameAs mappings between OBO and BioPortal NCBI Taxonomy IRIs.

Our taxonomy-extra RDF uses OBO Foundry IRIs:
    http://purl.obolibrary.org/obo/NCBITaxon_3702

BioPortal uses a different namespace for the same taxon:
    http://purl.bioontology.org/ontology/NCBITAXON/3702

This script reads the taxonomy-extra bundle, extracts every unique NCBI
taxon ID that appears in our data, and generates a TTL file with
owl:sameAs triples linking the two IRI forms. Loading this mapping as a
named graph in Virtuoso enables federated SPARQL queries against
BioPortal's SPARQL endpoint (sparql.bioontology.org) without changing
any existing triples.

Usage:
    python scripts/create_ncbi_iri_mappings.py

Output:
    output/bundles/ncbi_iri_mappings-<VERSION>.ttl

Recommended Virtuoso graph:
    http://rdf-plantmetwiki.bioinformatics.nl/graph/ncbi-iri-mappings

Example federated query enabled by this mapping (run on Virtuoso):

    PREFIX wp:   <http://vocabularies.wikipathways.org/wp#>
    PREFIX owl:  <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?node ?obo_taxon ?label
    WHERE {
      GRAPH <.../graph/gpml-taxonomy-extra> {
          ?node wp:organism ?obo_taxon .
      }
      GRAPH <.../graph/ncbi-iri-mappings> {
          ?obo_taxon owl:sameAs ?bioportal_taxon .
      }
      SERVICE <https://sparql.bioontology.org/ontology/NCBITAXON> {
          ?bioportal_taxon rdfs:label ?label .
      }
    }
    LIMIT 20
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


OBO_BASE        = "http://purl.obolibrary.org/obo/NCBITaxon_"
BIOPORTAL_BASE  = "http://purl.bioontology.org/ontology/NCBITAXON/"
# Matches both prefix form (ncbi:3702) and full URI form (NCBITaxon_3702)
OBO_PATTERN     = re.compile(r"(?:ncbi:|NCBITaxon_)(\d+)")


def extract_taxon_ids(taxonomy_ttl: Path) -> set[str]:
    """Extract all unique NCBI taxon IDs from the taxonomy-extra bundle."""
    ids: set[str] = set()
    for line in taxonomy_ttl.read_text(encoding="utf-8").splitlines():
        if line.startswith("@prefix"):
            continue
        for match in OBO_PATTERN.finditer(line):
            ids.add(match.group(1))
    return ids


def write_mappings(taxon_ids: set[str], output_file: Path) -> None:
    """Write owl:sameAs + skos:exactMatch triples to a Turtle file."""
    lines = [
        "@prefix owl:  <http://www.w3.org/2002/07/owl#> .",
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
        "",
        "# OBO Foundry IRI → BioPortal IRI mappings for NCBI Taxonomy.",
        "# Generated from taxa that appear in the PlantMetWiki taxonomy-extra bundle.",
        "# owl:sameAs  : machine-readable identity assertion",
        "# skos:exactMatch : for tools that prefer SKOS-based alignment",
        "",
    ]

    for taxon_id in sorted(taxon_ids, key=int):
        obo_iri       = f"{OBO_BASE}{taxon_id}"
        bioportal_iri = f"{BIOPORTAL_BASE}{taxon_id}"
        lines.append(f"<{obo_iri}> owl:sameAs      <{bioportal_iri}> ;")
        lines.append(f"            skos:exactMatch <{bioportal_iri}> .")
        lines.append("")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument(
        "--taxonomy-bundle",
        default=None,
        help="Path to all_gpml_taxonomy_extra-*.ttl (auto-detected if omitted)",
    )
    parser.add_argument(
        "--output-dir",
        default="output/bundles",
    )
    args = parser.parse_args()

    bundles = Path(args.output_dir)

    # Auto-detect taxonomy bundle
    if args.taxonomy_bundle:
        taxonomy_file = Path(args.taxonomy_bundle)
    else:
        candidates = sorted(bundles.glob("all_gpml_taxonomy_extra-*.ttl"))
        if not candidates:
            raise FileNotFoundError(f"No taxonomy-extra bundle found in {bundles}")
        taxonomy_file = candidates[-1]  # latest

    # Extract version from filename: all_gpml_taxonomy_extra-VERSION.ttl
    version = taxonomy_file.stem.replace("all_gpml_taxonomy_extra-", "")

    print(f"Reading taxonomy bundle: {taxonomy_file}")
    taxon_ids = extract_taxon_ids(taxonomy_file)
    print(f"Found {len(taxon_ids):,} unique NCBI taxon IDs")

    output_file = bundles / f"ncbi_iri_mappings-{version}.ttl"
    write_mappings(taxon_ids, output_file)

    print(f"Written {len(taxon_ids):,} mapping pairs to: {output_file}")
    print()
    print("Each taxon gets two alignment triples:")
    print("  <obo:NCBITaxon_X> owl:sameAs      <bioportal:NCBITAXON/X>")
    print("  <obo:NCBITaxon_X> skos:exactMatch <bioportal:NCBITAXON/X>")
    print()
    print("Load into Virtuoso as:")
    print("  http://rdf-plantmetwiki.bioinformatics.nl/graph/ncbi-iri-mappings")

    # Print a few examples
    sample = sorted(taxon_ids, key=int)[:5]
    print()
    print("Sample mappings:")
    for tid in sample:
        print(f"  NCBITaxon_{tid}  →  NCBITAXON/{tid}")


if __name__ == "__main__":
    main()
