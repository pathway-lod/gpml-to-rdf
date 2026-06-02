#!/usr/bin/env python3
"""Generate figure-ready CSVs by querying the local Virtuoso instance.

All queries run via SPARQLWrapper against the PlantMetWiki named graphs.
No local TTL files are required — Virtuoso must be running and loaded.

Named graphs used:
  graph/pathways              — core WikiPathways RDF
  graph/gpml-taxonomy-extra   — per-DataNode species annotations
  graph/ncbitaxon             — NCBITaxon ontology for label resolution

Usage
-----
    conda activate plantmetwiki-rdf
    python scripts/generate_figures_data.py                    # default localhost:8890
    python scripts/generate_figures_data.py --endpoint http://localhost:8890/sparql
    python scripts/generate_figures_data.py --out-dir notebooks/figures/output
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from SPARQLWrapper import SPARQLWrapper, JSON

# ── Named graph URIs ──────────────────────────────────────────────────────────
G_PW   = "http://rdf-plantmetwiki.bioinformatics.nl/graph/pathways"
G_TAX  = "http://rdf-plantmetwiki.bioinformatics.nl/graph/gpml-taxonomy-extra"
G_NCBI = "http://rdf-plantmetwiki.bioinformatics.nl/graph/ncbitaxon"

DEFAULT_ENDPOINT = "http://localhost:8890/sparql"

WP             = "http://vocabularies.wikipathways.org/wp#"
WP_INTERACTION = WP + "Interaction"

PREFIXES = f"""
PREFIX wp:      <{WP}>
PREFIX dc:      <http://purl.org/dc/elements/1.1/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX rdfs:    <http://www.w3.org/2000/01/rdf-schema#>
PREFIX ncbi:    <http://purl.obolibrary.org/obo/NCBITaxon_>
"""

# ── SPARQL helper ─────────────────────────────────────────────────────────────

def sparql(endpoint: str, query: str, timeout: int = 300) -> pd.DataFrame:
    """Run a SELECT query against Virtuoso; return results as a DataFrame."""
    sw = SPARQLWrapper(endpoint)
    sw.setReturnFormat(JSON)
    sw.setTimeout(timeout)
    sw.setQuery(PREFIXES + "\n" + query.strip())
    results = sw.query().convert()
    vars_   = results["head"]["vars"]
    rows    = [{v: r.get(v, {}).get("value", "") for v in vars_}
               for r in results["results"]["bindings"]]
    return pd.DataFrame(rows, columns=vars_)


def save(df: pd.DataFrame, out_dir: Path, name: str) -> pd.DataFrame:
    path = out_dir / name
    df.to_csv(path, index=False)
    print(f"  ✔ {name}  ({len(df):,} rows)")
    return df


# ── Core pathway queries (graph/pathways) ────────────────────────────────────
# All use dc:title — pathways do NOT have rdfs:label in this dataset.

def genes_per_pathway(ep: str, out_dir: Path) -> pd.DataFrame:
    print("Genes per pathway ...")
    return save(sparql(ep, f"""
        SELECT ?pwID (STR(?titleLit) AS ?title) (COUNT(DISTINCT ?entity) AS ?count)
        FROM <{G_PW}>
        WHERE {{
            ?pwID a wp:Pathway ; dc:title ?titleLit .
            ?entity a wp:GeneProduct ; dcterms:isPartOf ?pwID .
        }}
        GROUP BY ?pwID ?titleLit ORDER BY DESC(?count)
    """), out_dir, "genes_per_pathway.csv")


def metabolites_per_pathway(ep: str, out_dir: Path) -> pd.DataFrame:
    print("Metabolites per pathway ...")
    return save(sparql(ep, f"""
        SELECT ?pwID (STR(?titleLit) AS ?title) (COUNT(DISTINCT ?entity) AS ?count)
        FROM <{G_PW}>
        WHERE {{
            ?pwID a wp:Pathway ; dc:title ?titleLit .
            ?entity a wp:Metabolite ; dcterms:isPartOf ?pwID .
        }}
        GROUP BY ?pwID ?titleLit ORDER BY DESC(?count)
    """), out_dir, "metabolites_per_pathway.csv")


def enzymes_per_pathway(ep: str, out_dir: Path) -> pd.DataFrame:
    print("Enzymes (Protein) per pathway ...")
    return save(sparql(ep, f"""
        SELECT ?pwID (STR(?titleLit) AS ?title) (COUNT(DISTINCT ?entity) AS ?count)
        FROM <{G_PW}>
        WHERE {{
            ?pwID a wp:Pathway ; dc:title ?titleLit .
            ?entity a wp:Protein ; dcterms:isPartOf ?pwID .
        }}
        GROUP BY ?pwID ?titleLit ORDER BY DESC(?count)
    """), out_dir, "enzymes_per_pathway.csv")


def conversions_per_pathway(ep: str, out_dir: Path) -> pd.DataFrame:
    print("Conversions per pathway ...")
    return save(sparql(ep, f"""
        SELECT ?pwID (STR(?titleLit) AS ?title) (COUNT(DISTINCT ?interaction) AS ?count)
        FROM <{G_PW}>
        WHERE {{
            ?pwID a wp:Pathway ; dc:title ?titleLit .
            ?interaction a wp:Conversion ; dcterms:isPartOf ?pwID .
        }}
        GROUP BY ?pwID ?titleLit ORDER BY DESC(?count)
    """), out_dir, "conversions_per_pathway.csv")


def interaction_types(ep: str, out_dir: Path) -> pd.DataFrame:
    print("Interaction types ...")
    return save(sparql(ep, f"""
        SELECT ?type (COUNT(DISTINCT ?interaction) AS ?n)
        FROM <{G_PW}>
        WHERE {{
            ?interaction a ?type .
            FILTER(STRSTARTS(STR(?type), "{WP}"))
        }}
        GROUP BY ?type ORDER BY DESC(?n)
    """), out_dir, "interaction_types.csv")


def pathway_titles(ep: str, out_dir: Path) -> pd.DataFrame:
    print("Pathway titles ...")
    return save(sparql(ep, f"""
        SELECT DISTINCT ?pwID (STR(?titleLit) AS ?title)
        FROM <{G_PW}>
        WHERE {{
            ?pwID a wp:Pathway ; dc:title ?titleLit .
        }}
    """), out_dir, "pathway_titles.csv")


# ── Species queries (3-graph join via Virtuoso) ───────────────────────────────
# Species are at the DataNode level in graph/gpml-taxonomy-extra.
# Labels come from graph/ncbitaxon (OBO Foundry NCBITaxon ontology).

def species_per_pathway(ep: str, out_dir: Path) -> pd.DataFrame:
    """Count unique species per pathway via cross-graph SPARQL join."""
    print("Species per pathway (3-graph join) ...")
    return save(sparql(ep, f"""
        SELECT ?pwID (COUNT(DISTINCT ?taxon) AS ?count)
        WHERE {{
            GRAPH <{G_TAX}> {{
                ?node wp:organism ?taxon .
                FILTER(?taxon != ncbi:33090)
            }}
            GRAPH <{G_PW}> {{
                ?node dcterms:isPartOf ?pwID .
                ?pwID a wp:Pathway .
            }}
        }}
        GROUP BY ?pwID ORDER BY DESC(?count)
    """), out_dir, "species_per_pathway.csv")


def per_species_nrs(ep: str, out_dir: Path) -> pd.DataFrame:
    """Per-species counts: pathways, genes, enzymes.

    Three separate simple queries joined in Python — much faster than a single
    complex cross-graph OPTIONAL query, which times out on large datasets.
    """
    print("Per-species metrics (3 separate queries + Python join) ...")

    # Q1: pathways per species
    print("  pathways per species ...")
    q_pw = sparql(ep, f"""
        SELECT ?taxon ?species (COUNT(DISTINCT ?pw) AS ?pathways)
        WHERE {{
            GRAPH <{G_TAX}> {{ ?node wp:organism ?taxon . FILTER(?taxon != ncbi:33090) }}
            GRAPH <{G_PW}>  {{ ?node dcterms:isPartOf ?pw .
                               FILTER(CONTAINS(STR(?pw), "/pathways/")) }}
            GRAPH <{G_NCBI}> {{ ?taxon rdfs:label ?species . }}
        }}
        GROUP BY ?taxon ?species
    """)
    print(f"    {len(q_pw):,} species")

    # Q2: genes per species (entity has wp:organism AND a wp:GeneProduct)
    print("  genes per species ...")
    q_genes = sparql(ep, f"""
        SELECT ?taxon (COUNT(DISTINCT ?entity) AS ?genes)
        WHERE {{
            GRAPH <{G_TAX}> {{ ?entity wp:organism ?taxon . FILTER(?taxon != ncbi:33090) }}
            GRAPH <{G_PW}>  {{ ?entity a wp:GeneProduct . }}
        }}
        GROUP BY ?taxon
    """)

    # Q3: enzymes per species
    print("  enzymes per species ...")
    q_enzymes = sparql(ep, f"""
        SELECT ?taxon (COUNT(DISTINCT ?entity) AS ?enzymes)
        WHERE {{
            GRAPH <{G_TAX}> {{ ?entity wp:organism ?taxon . FILTER(?taxon != ncbi:33090) }}
            GRAPH <{G_PW}>  {{ ?entity a wp:Protein . }}
        }}
        GROUP BY ?taxon
    """)

    # Join in Python
    df = (q_pw
          .merge(q_genes,   on="taxon", how="left")
          .merge(q_enzymes, on="taxon", how="left")
          .fillna(0))
    for col in ("pathways", "genes", "enzymes"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    df = df.sort_values("pathways", ascending=False)

    return save(df[["species", "pathways", "genes", "enzymes"]], out_dir, "per_species_nrs.csv")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--endpoint", default=DEFAULT_ENDPOINT,
                   help=f"Virtuoso SPARQL endpoint (default: {DEFAULT_ENDPOINT})")
    p.add_argument("--out-dir", type=Path,
                   default=Path("notebooks/figures/output"),
                   help="Output directory for CSVs")
    p.add_argument("--skip-species", action="store_true",
                   help="Skip slow per-species metrics query")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Quick connectivity check
    try:
        test = sparql(args.endpoint,
                      "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o } LIMIT 1",
                      timeout=5)
        print(f"✔ Virtuoso reachable at {args.endpoint}")
    except Exception as e:
        print(f"ERROR: Cannot reach Virtuoso at {args.endpoint}: {e}")
        print("  Make sure Virtuoso is running: docker compose up -d virtuoso")
        return 1

    print(f"Output: {args.out_dir}\n")

    # ── Core pathway queries ──────────────────────────────────────────────────
    print("── Core pathway queries ─────────────────────────────────────")
    genes_per_pathway(args.endpoint, args.out_dir)
    metabolites_per_pathway(args.endpoint, args.out_dir)
    enzymes_per_pathway(args.endpoint, args.out_dir)
    conversions_per_pathway(args.endpoint, args.out_dir)
    interaction_types(args.endpoint, args.out_dir)
    pathway_titles(args.endpoint, args.out_dir)

    # ── Species queries ───────────────────────────────────────────────────────
    print("\n── Species queries (multi-graph) ────────────────────────────")
    species_per_pathway(args.endpoint, args.out_dir)

    if not args.skip_species:
        per_species_nrs(args.endpoint, args.out_dir)
    else:
        print("  [--skip-species] skipping per_species_nrs.csv")

    print(f"\n✔ All CSVs written to {args.out_dir}")
    print("  Open notebooks/plantmetwiki_figures.ipynb to generate figures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
