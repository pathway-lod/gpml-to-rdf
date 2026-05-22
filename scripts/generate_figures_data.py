#!/usr/bin/env python3
"""Generate figure-ready CSVs from the local RDF bundles.

Reads output/bundles/*.ttl, runs SPARQL queries via rdflib (no Virtuoso
required), and writes CSVs to notebooks/figures/output/.

The notebook notebooks/plantmetwiki_figures.ipynb loads these CSVs
and produces the actual figures.

Usage
-----
    conda activate plantmetwiki-rdf
    python scripts/generate_figures_data.py

    # Specify bundles directory explicitly
    python scripts/generate_figures_data.py --bundles output/bundles

    # Skip reloading the large core bundle if already generated
    python scripts/generate_figures_data.py --skip-core
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from rdflib import Graph


# ── Namespaces ────────────────────────────────────────────────────────────────
PREFIXES = """
PREFIX wp:      <http://vocabularies.wikipathways.org/wp#>
PREFIX ncbi:    <http://purl.obolibrary.org/obo/NCBITaxon_>
PREFIX rdfs:    <http://www.w3.org/2000/01/rdf-schema#>
PREFIX dcterms: <http://purl.org/dc/terms/>
"""

WP = "http://vocabularies.wikipathways.org/wp#"
WP_INTERACTION = WP + "Interaction"

# ── Helpers ───────────────────────────────────────────────────────────────────

def sparql(g: Graph, query: str) -> pd.DataFrame:
    results = g.query(PREFIXES + query)
    return pd.DataFrame(results, columns=[str(v) for v in results.vars])


def save_csv(df: pd.DataFrame, out_dir: Path, name: str) -> pd.DataFrame:
    path = out_dir / name
    df.to_csv(path, index=False)
    print(f"  ✔ {name}  ({len(df):,} rows)")
    return df


# ── Queries ───────────────────────────────────────────────────────────────────

def query_genes_per_pathway(g: Graph, out_dir: Path) -> pd.DataFrame:
    print("Genes per pathway ...")
    return save_csv(sparql(g, """
        SELECT ?pwID ?title (COUNT(DISTINCT ?entity) AS ?count)
        WHERE {
            ?entity a wp:GeneProduct ;
                    dcterms:isPartOf ?pwID .
            ?pwID rdfs:label ?title .
        }
        GROUP BY ?pwID ?title
        ORDER BY DESC(?count)
    """), out_dir, "genes_per_pathway.csv")


def query_metabolites_per_pathway(g: Graph, out_dir: Path) -> pd.DataFrame:
    print("Metabolites per pathway ...")
    return save_csv(sparql(g, """
        SELECT ?pwID ?title (COUNT(DISTINCT ?entity) AS ?count)
        WHERE {
            ?entity a wp:Metabolite ;
                    dcterms:isPartOf ?pwID .
            ?pwID rdfs:label ?title .
        }
        GROUP BY ?pwID ?title
        ORDER BY DESC(?count)
    """), out_dir, "metabolites_per_pathway.csv")


def query_enzymes_per_pathway(g: Graph, out_dir: Path) -> pd.DataFrame:
    print("Enzymes (Protein) per pathway ...")
    return save_csv(sparql(g, """
        SELECT ?pwID ?title (COUNT(DISTINCT ?entity) AS ?count)
        WHERE {
            ?entity a wp:Protein ;
                    dcterms:isPartOf ?pwID .
            ?pwID rdfs:label ?title .
        }
        GROUP BY ?pwID ?title
        ORDER BY DESC(?count)
    """), out_dir, "enzymes_per_pathway.csv")


def query_conversions_per_pathway(g: Graph, out_dir: Path) -> pd.DataFrame:
    print("Conversions per pathway ...")
    return save_csv(sparql(g, """
        SELECT ?pwID ?title (COUNT(DISTINCT ?interaction) AS ?count)
        WHERE {
            ?interaction a wp:Conversion ;
                         dcterms:isPartOf ?pwID .
            ?pwID rdfs:label ?title .
        }
        GROUP BY ?pwID ?title
        ORDER BY DESC(?count)
    """), out_dir, "conversions_per_pathway.csv")


def query_interaction_types(g: Graph, out_dir: Path) -> pd.DataFrame:
    print("Interaction types ...")
    return save_csv(sparql(g, """
        SELECT ?type (COUNT(DISTINCT ?interaction) AS ?n)
        WHERE {
            ?interaction a ?type .
            FILTER(STRSTARTS(STR(?type), "http://vocabularies.wikipathways.org/wp#"))
        }
        GROUP BY ?type
        ORDER BY DESC(?n)
    """), out_dir, "interaction_types.csv")


def query_pathway_titles(g: Graph, out_dir: Path) -> pd.DataFrame:
    print("Pathway titles ...")
    return save_csv(sparql(g, """
        SELECT DISTINCT ?pwID ?title
        WHERE {
            ?pwID a wp:Pathway ; rdfs:label ?title .
            FILTER(CONTAINS(STR(?pwID), "/pathways/"))
        }
    """), out_dir, "pathway_titles.csv")


def query_species_per_pathway(g_core: Graph, g_tax: Graph, out_dir: Path) -> pd.DataFrame:
    """Two-graph join in Python (avoids slow SPARQL federation on huge graphs)."""
    print("Species per pathway (two-step Python join) ...")

    print("  Step 1: entity → pathway + DataNode URI (core) ...")
    entity_pathway = sparql(g_core, """
        SELECT DISTINCT ?entity ?pwID ?datanode
        WHERE {
            ?entity dcterms:isPartOf ?pwID ;
                    wp:isAbout ?datanode .
            FILTER(CONTAINS(STR(?pwID), "/pathways/"))
            FILTER(CONTAINS(STR(?datanode), "/DataNode/"))
        }
    """)
    print(f"    {len(entity_pathway):,} entity→pathway pairs")

    print("  Step 2: DataNode → taxon (taxonomy-extra) ...")
    node_to_taxon = sparql(g_tax, """
        SELECT DISTINCT ?node ?species
        WHERE {
            ?node wp:organism ?species .
            FILTER(?species != ncbi:33090)
            FILTER(CONTAINS(STR(?node), "/DataNode/"))
        }
    """)
    print(f"    {len(node_to_taxon):,} DataNode→taxon pairs")

    print("  Step 3: Python join → species per pathway ...")
    merged = entity_pathway.merge(
        node_to_taxon.rename(columns={"node": "datanode"}), on="datanode", how="inner"
    )
    species_pw = (
        merged.groupby("pwID")["species"]
        .nunique()
        .reset_index()
        .rename(columns={"species": "count"})
        .sort_values("count", ascending=False)
    )
    return save_csv(species_pw, out_dir, "species_per_pathway.csv")


def query_per_species_metrics(g_core: Graph, g_tax: Graph,
                               node_to_taxon: pd.DataFrame,
                               out_dir: Path) -> pd.DataFrame:
    """Per-species pathway/gene/enzyme/metabolite counts (Python join)."""
    print("Per-species metrics (Python join) ...")

    node_types = sparql(g_core, f"""
        SELECT DISTINCT ?entity ?type ?datanode ?pwID
        WHERE {{
            ?entity a ?type ;
                    dcterms:isPartOf ?pwID ;
                    wp:isAbout ?datanode .
            FILTER(?type IN (wp:GeneProduct, wp:Protein, wp:Metabolite))
            FILTER(CONTAINS(STR(?pwID), "/pathways/"))
            FILTER(CONTAINS(STR(?datanode), "/DataNode/"))
        }}
    """)
    print(f"  {len(node_types):,} entity-type-pathway triples")

    joined = node_to_taxon.rename(columns={"node": "datanode"}).merge(
        node_types, on="datanode", how="inner"
    )

    per_species = (
        joined.groupby("species")
        .agg(
            pathways    = ("pwID",   "nunique"),
            genes       = ("entity", lambda x: x[joined.loc[x.index, "type"] == WP + "GeneProduct"].nunique()),
            enzymes     = ("entity", lambda x: x[joined.loc[x.index, "type"] == WP + "Protein"].nunique()),
            metabolites = ("entity", lambda x: x[joined.loc[x.index, "type"] == WP + "Metabolite"].nunique()),
        )
        .reset_index()
        .sort_values("pathways", ascending=False)
    )
    per_species["species"] = per_species["species"].apply(
        lambda x: str(x).split("/")[-1].replace("NCBITaxon_", "ncbi:")
        if str(x).startswith("http") else x
    )
    return save_csv(per_species, out_dir, "per_species_nrs.csv")


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bundles",   type=Path, default=Path("output/bundles"),
                   help="Directory containing *.ttl bundle files")
    p.add_argument("--out-dir",   type=Path,
                   default=Path("notebooks/figures/output"),
                   help="Output directory for CSVs")
    p.add_argument("--skip-core", action="store_true",
                   help="Skip reloading core bundle if CSVs already exist")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # ── Auto-detect version ────────────────────────────────────────────────
    core_files = sorted(args.bundles.glob("all-*.ttl"))
    if not core_files:
        print(f"[ERROR] No core bundle (all-*.ttl) found in {args.bundles}")
        return 1
    version = core_files[-1].stem.replace("all-", "")
    core_file = args.bundles / f"all-{version}.ttl"
    tax_file  = args.bundles / f"all_gpml_taxonomy_extra-{version}.ttl"

    print(f"Version:  {version}")
    print(f"Core:     {core_file.name}  ({core_file.stat().st_size/1e6:.0f} MB)")
    print(f"Taxonomy: {tax_file.name}  ({tax_file.stat().st_size/1e6:.1f} MB)")
    print(f"Output:   {args.out_dir}\n")

    # ── Load taxonomy (small, always) ──────────────────────────────────────
    print("Loading taxonomy bundle (~4 MB) ...")
    g_tax = Graph()
    g_tax.parse(str(tax_file), format="turtle")
    print(f"  {len(g_tax):,} triples\n")

    # Pre-fetch node→taxon for Python joins (reused across queries)
    print("Fetching DataNode→taxon pairs from taxonomy bundle ...")
    node_to_taxon = sparql(g_tax, """
        SELECT DISTINCT ?node ?species
        WHERE {
            ?node wp:organism ?species .
            FILTER(?species != ncbi:33090)
            FILTER(CONTAINS(STR(?node), "/DataNode/"))
        }
    """)
    print(f"  {len(node_to_taxon):,} pairs\n")

    # ── Load core (large) ──────────────────────────────────────────────────
    if args.skip_core:
        existing = list(args.out_dir.glob("genes_per_pathway.csv"))
        if existing:
            print("[--skip-core] Core CSVs already present — skipping bundle load.")
            print("  Re-running taxonomy-only queries and species join ...")
            g_core = None
        else:
            args.skip_core = False

    if not args.skip_core:
        print(f"Loading core bundle (~300 MB, 1-2 min) ...")
        g_core = Graph()
        g_core.parse(str(core_file), format="turtle")
        print(f"  {len(g_core):,} triples\n")

        print("── Core queries ──────────────────────────────────────────────")
        query_genes_per_pathway(g_core, args.out_dir)
        query_metabolites_per_pathway(g_core, args.out_dir)
        query_enzymes_per_pathway(g_core, args.out_dir)
        query_conversions_per_pathway(g_core, args.out_dir)
        query_interaction_types(g_core, args.out_dir)
        query_pathway_titles(g_core, args.out_dir)

    print("\n── Cross-graph queries (Python join) ─────────────────────────")
    query_species_per_pathway(g_core, g_tax, args.out_dir)
    query_per_species_metrics(g_core, g_tax, node_to_taxon, args.out_dir)

    print(f"\n✔ All CSVs written to {args.out_dir}")
    print("  Open notebooks/plantmetwiki_figures.ipynb to generate figures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
