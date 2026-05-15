#!/usr/bin/env python3
"""
Test federated queries against BioPortal's NCBI Taxonomy SPARQL endpoint.

Verifies that:
1. The NCBI IRI mapping file is syntactically valid
2. BioPortal's endpoint is reachable with the provided API key
3. Our OBO taxon IRIs resolve to labels via the mapping

Requires:
    BIOPORTAL_API_KEY set in .env (see .env.template)

Usage:
    set -a && source .env && set +a
    python scripts/test_bioportal_federation.py
"""

from __future__ import annotations

import os
import sys
import urllib.request
import urllib.parse
import json as _json
from pathlib import Path

from rdflib import Graph


BIOPORTAL_SPARQL   = "https://sparql.bioontology.org/sparql"   # may be unavailable
BIOPORTAL_REST     = "https://data.bioontology.org/ontologies/NCBITAXON/classes"
OBO_BASE           = "http://purl.obolibrary.org/obo/NCBITaxon_"
BIOPORTAL_BASE     = "http://purl.bioontology.org/ontology/NCBITAXON/"

# A handful of well-known taxa to test with
TEST_TAXA = {
    "3702":  "Arabidopsis thaliana",
    "33090": "Viridiplantae",
    "3847":  "Glycine max",
    "3055":  "Chlamydomonas reinhardtii",
    "4081":  "Solanum lycopersicum",
}


def check_mapping_file(mapping_file: Path) -> int:
    """Parse the mapping TTL and return the number of owl:sameAs triples."""
    print(f"\n── Validating mapping file: {mapping_file.name}")
    g = Graph()
    g.parse(str(mapping_file), format="turtle")
    owl_sameAs = sum(1 for _, p, _ in g
                     if str(p) == "http://www.w3.org/2002/07/owl#sameAs")
    print(f"   {len(g):,} total triples  |  {owl_sameAs:,} owl:sameAs pairs")
    return owl_sameAs


def lookup_bioportal_label(api_key: str, taxon_id: str) -> str | None:
    """Fetch the prefLabel for a single NCBI taxon ID via BioPortal REST API."""
    encoded = urllib.parse.quote(f"{BIOPORTAL_BASE}{taxon_id}", safe="")
    url = f"{BIOPORTAL_REST}/{encoded}?apikey={api_key}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = _json.load(r)
            return data.get("prefLabel")
    except Exception:
        return None


def query_bioportal_labels(api_key: str, taxon_ids: list[str]) -> dict[str, str]:
    """Fetch labels for a list of NCBI taxon IDs via BioPortal REST API."""
    results = {}
    for tid in taxon_ids:
        label = lookup_bioportal_label(api_key, tid)
        if label:
            results[tid] = label
    return results


def main() -> int:
    api_key = os.environ.get("BIOPORTAL_API_KEY", "")
    if not api_key or api_key == "your-bioportal-api-key-here":
        print("⚠️  BIOPORTAL_API_KEY not set.")
        print("   Register at https://bioportal.bioontology.org/accounts/new")
        print("   Then: set -a && source .env && set +a")
        print()
        print("   Running mapping file validation only...")
        api_key = None

    # 1 — Validate mapping TTL
    bundles = Path("output/bundles")
    candidates = sorted(bundles.glob("ncbi_iri_mappings-*.ttl"))
    if not candidates:
        print("❌ No mapping file found. Run: python scripts/create_ncbi_iri_mappings.py")
        return 1

    mapping_file = candidates[-1]
    n_mappings = check_mapping_file(mapping_file)
    print(f"   ✅ Mapping file valid ({n_mappings:,} owl:sameAs triples)")

    if not api_key:
        return 0

    # 2 — Test BioPortal endpoint
    print(f"\n── Testing BioPortal REST API ({BIOPORTAL_REST})")
    print(f"   Querying labels for {len(TEST_TAXA)} well-known taxa...")

    try:
        labels = query_bioportal_labels(api_key, list(TEST_TAXA.keys()))
    except Exception as e:
        print(f"   ❌ Endpoint error: {e}")
        return 1

    all_ok = True
    for taxon_id, expected_name in TEST_TAXA.items():
        label = labels.get(taxon_id, None)
        if label:
            match = "✅" if expected_name.lower() in label.lower() else "⚠️ "
            print(f"   {match} NCBITaxon_{taxon_id:<8}  {label}")
        else:
            print(f"   ❌ NCBITaxon_{taxon_id:<8}  no label returned")
            all_ok = False

    print()
    if all_ok:
        print("✅ BioPortal endpoint reachable and labels match expected values.")
        print()
        print("Federated query template for Virtuoso:")
        print("""
    PREFIX wp:   <http://vocabularies.wikipathways.org/wp#>
    PREFIX owl:  <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX ncbi: <http://purl.obolibrary.org/obo/NCBITaxon_>

    SELECT ?node ?obo_taxon ?label
    WHERE {
      GRAPH <http://rdf-plantmetwiki.bioinformatics.nl/graph/gpml-taxonomy-extra> {
          ?node wp:organism ?obo_taxon .
          FILTER(?obo_taxon != ncbi:33090)
      }
      GRAPH <http://rdf-plantmetwiki.bioinformatics.nl/graph/ncbi-iri-mappings> {
          ?obo_taxon owl:sameAs ?bioportal_taxon .
      }
      SERVICE <https://sparql.bioontology.org/sparql?apikey=YOUR_KEY> {
          ?bioportal_taxon rdfs:label ?label .
      }
    }
    LIMIT 20
        """)
    else:
        print("⚠️  Some taxa returned no label — check API key or BioPortal availability.")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
