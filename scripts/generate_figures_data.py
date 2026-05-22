#!/usr/bin/env python3
"""Generate figure-ready CSVs from the PlantMetWiki RDF data.

Strategy
--------
- **Core queries** (per-pathway counts, interaction types, pathway titles):
  SPARQLWrapper → local Virtuoso (fast, indexed).
  Virtuoso must have the data loaded; it uses the same TTL files, so
  reproducibility is preserved.

- **Species queries** (taxonomy-extra bundle, ~4 MB):
  rdflib on the local TTL file — fast because the bundle is small.
  Cross-graph join between taxonomy-extra and core is done in Python.

Why not rdflib for everything?
  Loading the 309 MB core bundle into rdflib takes 2-3 min and queries
  are unindexed; simple COUNT queries can take 10+ min. Virtuoso indexes
  the same data and answers in seconds.

Usage
-----
    conda activate plantmetwiki-rdf

    # Default: local Virtuoso at localhost:8890
    python scripts/generate_figures_data.py

    # Custom endpoint
    python scripts/generate_figures_data.py --endpoint http://localhost:8890/sparql

    # Named graph (if data is in a specific graph)
    python scripts/generate_figures_data.py --graph http://rdf-plantmetwiki.bioinformatics.nl/graph/pathways

    # Use rdflib fallback for core too (slow, no Virtuoso needed)
    python scripts/generate_figures_data.py --no-virtuoso
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from rdflib import Graph
from SPARQLWrapper import SPARQLWrapper, JSON

# ── Prefixes ──────────────────────────────────────────────────────────────────
PREFIXES = """
PREFIX wp:      <http://vocabularies.wikipathways.org/wp#>
PREFIX ncbi:    <http://purl.obolibrary.org/obo/NCBITaxon_>
PREFIX rdfs:    <http://www.w3.org/2000/01/rdf-schema#>
PREFIX dcterms: <http://purl.org/dc/terms/>
"""

WP = "http://vocabularies.wikipathways.org/wp#"
WP_INTERACTION = WP + "Interaction"
DEFAULT_ENDPOINT = "http://localhost:8890/sparql"

# ── SPARQL helpers ────────────────────────────────────────────────────────────

def sparql_endpoint(endpoint: str, query: str,
                    graph: str | None = None,
                    timeout: int = 120) -> pd.DataFrame:
    """Run a SELECT query against a Virtuoso SPARQL endpoint."""
    sw = SPARQLWrapper(endpoint)
    sw.setReturnFormat(JSON)
    sw.setTimeout(timeout)
    if graph:
        full_query = f"PREFIX wp: <{WP}>\n{PREFIXES}\n" \
                     f"SELECT * WHERE {{ GRAPH <{graph}> {{ {query.strip().lstrip('SELECT').split('WHERE')[1]} }} }}"
        # Simpler: just wrap with FROM NAMED
        full_query = PREFIXES + f"\n{query.strip()}"
        sw.addParameter("default-graph-uri", graph)
    else:
        full_query = PREFIXES + "\n" + query.strip()
    sw.setQuery(full_query)
    results = sw.query().convert()
    vars_ = results["head"]["vars"]
    rows  = [{v: r.get(v, {}).get("value", "") for v in vars_}
              for r in results["results"]["bindings"]]
    return pd.DataFrame(rows, columns=vars_)


def sparql_rdflib(g: Graph, query: str) -> pd.DataFrame:
    """Run a SELECT query on an rdflib Graph."""
    results = g.query(PREFIXES + query)
    return pd.DataFrame(results, columns=[str(v) for v in results.vars])


def save_csv(df: pd.DataFrame, out_dir: Path, name: str) -> pd.DataFrame:
    path = out_dir / name
    df.to_csv(path, index=False)
    print(f"  ✔ {name}  ({len(df):,} rows)")
    return df


# ── Core queries (Virtuoso) ───────────────────────────────────────────────────

CORE_QUERIES = {
    "genes_per_pathway.csv": """
        SELECT ?pwID ?title (COUNT(DISTINCT ?entity) AS ?count)
        WHERE {
            ?entity a wp:GeneProduct ;
                    dcterms:isPartOf ?pwID .
            ?pwID rdfs:label ?title .
            FILTER(CONTAINS(STR(?pwID), "/pathways/"))
        }
        GROUP BY ?pwID ?title
        ORDER BY DESC(?count)
    """,
    "metabolites_per_pathway.csv": """
        SELECT ?pwID ?title (COUNT(DISTINCT ?entity) AS ?count)
        WHERE {
            ?entity a wp:Metabolite ;
                    dcterms:isPartOf ?pwID .
            ?pwID rdfs:label ?title .
            FILTER(CONTAINS(STR(?pwID), "/pathways/"))
        }
        GROUP BY ?pwID ?title
        ORDER BY DESC(?count)
    """,
    "enzymes_per_pathway.csv": """
        SELECT ?pwID ?title (COUNT(DISTINCT ?entity) AS ?count)
        WHERE {
            ?entity a wp:Protein ;
                    dcterms:isPartOf ?pwID .
            ?pwID rdfs:label ?title .
            FILTER(CONTAINS(STR(?pwID), "/pathways/"))
        }
        GROUP BY ?pwID ?title
        ORDER BY DESC(?count)
    """,
    "conversions_per_pathway.csv": """
        SELECT ?pwID ?title (COUNT(DISTINCT ?interaction) AS ?count)
        WHERE {
            ?interaction a wp:Conversion ;
                         dcterms:isPartOf ?pwID .
            ?pwID rdfs:label ?title .
            FILTER(CONTAINS(STR(?pwID), "/pathways/"))
        }
        GROUP BY ?pwID ?title
        ORDER BY DESC(?count)
    """,
    "interaction_types.csv": """
        SELECT ?type (COUNT(DISTINCT ?interaction) AS ?n)
        WHERE {
            ?interaction a ?type .
            FILTER(STRSTARTS(STR(?type),
                   "http://vocabularies.wikipathways.org/wp#"))
        }
        GROUP BY ?type
        ORDER BY DESC(?n)
    """,
    "pathway_titles.csv": """
        SELECT DISTINCT ?pwID ?title
        WHERE {
            ?pwID a wp:Pathway ; rdfs:label ?title .
            FILTER(CONTAINS(STR(?pwID), "/pathways/"))
        }
    """,
}


def run_core_queries_virtuoso(endpoint: str, out_dir: Path,
                               graph: str | None = None) -> None:
    """Run all core queries against Virtuoso and save CSVs."""
    print(f"Querying Virtuoso at {endpoint} ...")
    for name, query in CORE_QUERIES.items():
        print(f"  {name} ...")
        try:
            df = sparql_endpoint(endpoint, query, graph=graph)
            save_csv(df, out_dir, name)
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")


def run_core_queries_rdflib(core_file: Path, out_dir: Path) -> Graph:
    """Fallback: load core bundle into rdflib and run queries (slow)."""
    print(f"Loading core bundle via rdflib (~2 min): {core_file.name} ...")
    g = Graph()
    g.parse(str(core_file), format="turtle")
    print(f"  {len(g):,} triples loaded")
    for name, query in CORE_QUERIES.items():
        print(f"  {name} ...")
        save_csv(sparql_rdflib(g, query), out_dir, name)
    return g


# ── Taxonomy queries (rdflib, fast) ──────────────────────────────────────────

def run_taxonomy_queries(tax_file: Path, out_dir: Path,
                          g_core_rdflib: Graph | None = None,
                          endpoint: str | None = None,
                          graph: str | None = None) -> None:
    """Species per pathway and per-species metrics.

    Taxonomy bundle is small (~4 MB) → rdflib is fast.
    Cross-graph join with core is done in Python.
    """
    print(f"\nLoading taxonomy bundle (rdflib): {tax_file.name} ...")
    g_tax = Graph()
    g_tax.parse(str(tax_file), format="turtle")
    print(f"  {len(g_tax):,} triples")

    # Step 1: DataNode → taxon (from taxonomy bundle)
    print("  DataNode → taxon pairs ...")
    node_to_taxon = sparql_rdflib(g_tax, """
        SELECT DISTINCT ?node ?species
        WHERE {
            ?node wp:organism ?species .
            FILTER(?species != ncbi:33090)
            FILTER(CONTAINS(STR(?node), "/DataNode/"))
        }
    """)
    print(f"    {len(node_to_taxon):,} pairs")

    # Step 2: entity → pathway + DataNode URI (from core)
    print("  Entity → pathway + DataNode URI ...")
    ep_query = """
        SELECT DISTINCT ?entity ?pwID ?datanode
        WHERE {
            ?entity dcterms:isPartOf ?pwID ;
                    wp:isAbout ?datanode .
            FILTER(CONTAINS(STR(?pwID), "/pathways/"))
            FILTER(CONTAINS(STR(?datanode), "/DataNode/"))
        }
    """
    if endpoint:
        entity_pathway = sparql_endpoint(endpoint, ep_query, graph=graph)
    else:
        entity_pathway = sparql_rdflib(g_core_rdflib, ep_query)
    print(f"    {len(entity_pathway):,} entity→pathway pairs")

    # Step 3: Python join → species per pathway
    merged_sp = entity_pathway.merge(
        node_to_taxon.rename(columns={"node": "datanode"}),
        on="datanode", how="inner"
    )
    species_pw = (
        merged_sp.groupby("pwID")["species"]
        .nunique().reset_index()
        .rename(columns={"species": "count"})
        .sort_values("count", ascending=False)
    )
    save_csv(species_pw, out_dir, "species_per_pathway.csv")

    # Step 4: per-species metrics
    print("  Per-species metrics (Python join) ...")
    nt_query = """
        SELECT DISTINCT ?entity ?type ?datanode ?pwID
        WHERE {
            ?entity a ?type ;
                    dcterms:isPartOf ?pwID ;
                    wp:isAbout ?datanode .
            FILTER(?type IN (wp:GeneProduct, wp:Protein, wp:Metabolite))
            FILTER(CONTAINS(STR(?pwID), "/pathways/"))
            FILTER(CONTAINS(STR(?datanode), "/DataNode/"))
        }
    """
    if endpoint:
        node_types = sparql_endpoint(endpoint, nt_query, graph=graph)
    else:
        node_types = sparql_rdflib(g_core_rdflib, nt_query)

    joined = node_to_taxon.rename(columns={"node": "datanode"}).merge(
        node_types, on="datanode", how="inner"
    )
    per_species = (
        joined.groupby("species").agg(
            pathways    = ("pwID",   "nunique"),
            genes       = ("entity", lambda x: x[joined.loc[x.index, "type"] == WP + "GeneProduct"].nunique()),
            enzymes     = ("entity", lambda x: x[joined.loc[x.index, "type"] == WP + "Protein"].nunique()),
            metabolites = ("entity", lambda x: x[joined.loc[x.index, "type"] == WP + "Metabolite"].nunique()),
        ).reset_index().sort_values("pathways", ascending=False)
    )
    per_species["species"] = per_species["species"].apply(
        lambda x: str(x).split("/")[-1].replace("NCBITaxon_", "ncbi:")
        if str(x).startswith("http") else x
    )
    save_csv(per_species, out_dir, "per_species_nrs.csv")


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--endpoint",    default=DEFAULT_ENDPOINT,
                   help=f"Virtuoso SPARQL endpoint (default: {DEFAULT_ENDPOINT})")
    p.add_argument("--graph",       default=None,
                   help="Named graph URI to query (optional)")
    p.add_argument("--bundles",     type=Path, default=Path("output/bundles"),
                   help="Local TTL bundles directory (for taxonomy + rdflib fallback)")
    p.add_argument("--out-dir",     type=Path,
                   default=Path("notebooks/figures/output"),
                   help="Output directory for CSVs")
    p.add_argument("--no-virtuoso", action="store_true",
                   help="Use rdflib for all queries (slow, no Virtuoso needed)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Auto-detect taxonomy bundle
    tax_files = sorted(args.bundles.glob("all_gpml_taxonomy_extra-*.ttl"))
    if not tax_files:
        print(f"[ERROR] No taxonomy bundle found in {args.bundles}")
        return 1
    tax_file = tax_files[-1]

    print(f"Output: {args.out_dir}")
    print(f"Taxonomy bundle: {tax_file.name} ({tax_file.stat().st_size/1e6:.1f} MB)\n")

    g_core_rdflib: Graph | None = None
    endpoint: str | None = None

    if args.no_virtuoso:
        # Slow fallback: rdflib for everything
        core_files = sorted(args.bundles.glob("all-*.ttl"))
        if not core_files:
            print(f"[ERROR] No core bundle found in {args.bundles}")
            return 1
        print("[--no-virtuoso] Using rdflib for all queries (slow) ...")
        g_core_rdflib = run_core_queries_rdflib(core_files[-1], args.out_dir)
    else:
        # Fast path: Virtuoso for core queries
        try:
            test = sparql_endpoint(args.endpoint,
                                   "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o } LIMIT 1",
                                   timeout=5)
            print(f"✔ Virtuoso reachable at {args.endpoint}")
        except Exception as e:
            print(f"[ERROR] Cannot reach Virtuoso at {args.endpoint}: {e}")
            print("  → Run with --no-virtuoso to use rdflib fallback (slow)")
            return 1
        endpoint = args.endpoint
        print()
        run_core_queries_virtuoso(args.endpoint, args.out_dir, graph=args.graph)

    print()
    run_taxonomy_queries(tax_file, args.out_dir,
                         g_core_rdflib=g_core_rdflib,
                         endpoint=endpoint,
                         graph=args.graph)

    print(f"\n✔ All CSVs written to {args.out_dir}")
    print("  Open notebooks/plantmetwiki_figures.ipynb to generate figures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
