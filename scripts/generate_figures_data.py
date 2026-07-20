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
import re
from pathlib import Path

import pandas as pd
from SPARQLWrapper import SPARQLWrapper, JSON

# ── Named graph URIs ──────────────────────────────────────────────────────────
G_PW    = "http://rdf-plantmetwiki.bioinformatics.nl/graph/pathways"
G_TAX   = "http://rdf-plantmetwiki.bioinformatics.nl/graph/gpml-taxonomy-extra"
G_NCBI  = "http://rdf-plantmetwiki.bioinformatics.nl/graph/ncbitaxon"
G_PROPS = "http://rdf-plantmetwiki.bioinformatics.nl/graph/gpml-properties-extra"

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

def sparql(endpoint: str, query: str, timeout: int = 300, page_size: int = 10_000) -> pd.DataFrame:
    """Run a SELECT query against Virtuoso; return results as a DataFrame.

    Paginates with LIMIT/OFFSET so results aren't silently truncated by
    Virtuoso's default 10,000-row SPARQL endpoint cap -- this previously
    caused undercounted results for any query returning ungrouped
    (pwID, entity) pairs (e.g. wp:Metabolite memberships: 22,109 true pairs,
    only 10,000 returned without pagination).

    page_size MUST match (or be below) the server's actual enforced cap:
    Virtuoso silently caps every response at that cap regardless of the
    LIMIT requested, so a larger page_size makes a capped (partial-looking)
    response indistinguishable from a genuinely final page, ending
    pagination early with data silently missing.
    """
    sw = SPARQLWrapper(endpoint)
    sw.setReturnFormat(JSON)
    sw.setTimeout(timeout)
    base_query = PREFIXES + "\n" + query.strip()

    # Caller already specified its own LIMIT (e.g. a connectivity probe) --
    # run as-is, single page, no pagination appended.
    if re.search(r"\bLIMIT\s+\d+", query, re.IGNORECASE):
        sw.setQuery(base_query)
        results = sw.query().convert()
        vars_ = results["head"]["vars"]
        rows = [{v: r.get(v, {}).get("value", "") for v in vars_}
                for r in results["results"]["bindings"]]
        return pd.DataFrame(rows, columns=vars_)

    vars_: list[str] = []
    all_bindings: list[dict] = []
    offset = 0
    while True:
        sw.setQuery(f"{base_query}\nLIMIT {page_size} OFFSET {offset}")
        results = sw.query().convert()
        vars_ = results["head"]["vars"]
        bindings = results["results"]["bindings"]
        all_bindings.extend(bindings)
        if len(bindings) < page_size:
            break
        offset += page_size

    rows = [{v: r.get(v, {}).get("value", "") for v in vars_} for r in all_bindings]
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


def interaction_subtypes_per_pathway(ep: str, out_dir: Path) -> None:
    """Per-pathway counts for the wp: interaction sub-types not already
    covered by genes/enzymes/metabolites/conversions_per_pathway.csv, needed
    for the per-pathway content-coverage figure."""
    print("Interaction sub-types per pathway (TranscriptionTranslation/Inhibition/Stimulation) ...")
    for label, wp_class, fname in [
        ("TranscriptionTranslation", "wp:TranscriptionTranslation", "transcriptiontranslation_per_pathway.csv"),
        ("Inhibition",               "wp:Inhibition",               "inhibition_per_pathway.csv"),
        ("Stimulation",              "wp:Stimulation",              "stimulation_per_pathway.csv"),
    ]:
        save(sparql(ep, f"""
            SELECT ?pwID (COUNT(DISTINCT ?i) AS ?count)
            FROM <{G_PW}>
            WHERE {{
                ?pwID a wp:Pathway .
                ?i a {wp_class} ; dcterms:isPartOf ?pwID .
            }}
            GROUP BY ?pwID
        """), out_dir, fname)

    print("Publications per pathway ...")
    save(sparql(ep, f"""
        PREFIX cito: <http://purl.org/spar/cito/>
        SELECT ?pwID (COUNT(DISTINCT ?pub) AS ?count)
        FROM <{G_PW}>
        WHERE {{
            ?pwID a wp:Pathway .
            ?pwID (dcterms:references | cito:cites) ?pub .
        }}
        GROUP BY ?pwID
    """), out_dir, "publications_per_pathway.csv")


def pathway_titles(ep: str, out_dir: Path) -> pd.DataFrame:
    print("Pathway titles (+ PlantCyc PWY identifier) ...")
    titles_df = sparql(ep, f"""
        SELECT DISTINCT ?pwID (STR(?titleLit) AS ?title)
        FROM <{G_PW}>
        WHERE {{
            ?pwID a wp:Pathway ; dc:title ?titleLit .
        }}
    """)
    # PlantCyc PWY/RXN code lives in the properties-extra graph (captured from
    # the GPML <Property key="UniqueID" value="PWY-...">), keyed by the same
    # versioned pwID URI used in graph/pathways.
    pcid_df = sparql(ep, f"""
        SELECT DISTINCT ?pwID ?pcid
        FROM <{G_PROPS}>
        WHERE {{ ?pwID dcterms:identifier ?pcid . }}
    """)
    merged = titles_df.merge(pcid_df, on="pwID", how="left")
    return save(merged, out_dir, "pathway_titles.csv")


def entity_totals(ep: str, out_dir: Path) -> pd.DataFrame:
    """True unique counts per wp: class (no double-counting across pathways)."""
    print("Entity totals (unique counts per wp: class) ...")
    rows = []
    for label, wp_class in [
        ("Pathways",     None),   # handled specially: split by PC*/RC* prefix
        ("Genes",        "wp:GeneProduct"),
        ("Enzymes",      "wp:Protein"),
        ("Metabolites",  "wp:Metabolite"),
        ("Complexes",    "wp:Complex"),
        ("Conversions",  "wp:Conversion"),
        ("Catalysis",    "wp:Catalysis"),
        ("Interactions", "wp:Interaction"),
    ]:
        if wp_class is None:
            continue
        df = sparql(ep, f"""
            SELECT (COUNT(DISTINCT ?e) AS ?n)
            FROM <{G_PW}>
            WHERE {{ ?e a {wp_class} }}
        """)
        n = int(df["n"].iloc[0])
        rows.append({"entity": label, "count": n})
        print(f"  {label}: {n:,}")

    pw_df = sparql(ep, f"""
        SELECT DISTINCT ?pwID FROM <{G_PW}> WHERE {{ ?pwID a wp:Pathway . }}
    """)
    n_pathways  = pw_df["pwID"].str.contains("/PC").sum()
    n_reactions = pw_df["pwID"].str.contains("/RC").sum()
    rows.insert(0, {"entity": "Reactions", "count": int(n_reactions)})
    rows.insert(0, {"entity": "Pathways",  "count": int(n_pathways)})
    print(f"  Pathways: {n_pathways:,}  Reactions: {n_reactions:,}")

    return save(pd.DataFrame(rows), out_dir, "entity_totals.csv")


def annotation_summary(ep: str, out_dir: Path) -> pd.DataFrame:
    """For each major entity type: total distinct nodes vs directly species-annotated nodes.

    'Directly annotated' means the entity itself carries wp:organism in
    graph/gpml-taxonomy-extra (only genes and enzymes in PlantCyc).
    Metabolites have no direct wp:organism triple — their count in the
    'annotated' column is 0 by definition.
    """
    print("Annotation summary (total vs species-annotated per entity type) ...")
    rows = []
    for entity_label, wp_class in [
        ("genes",       "wp:GeneProduct"),
        ("enzymes",     "wp:Protein"),
        ("metabolites", "wp:Metabolite"),
        ("complexes",   "wp:Complex"),
    ]:
        total_df = sparql(ep, f"""
            SELECT (COUNT(DISTINCT ?e) AS ?n)
            FROM <{G_PW}>
            WHERE {{ ?e a {wp_class} }}
        """)
        total = int(total_df["n"].iloc[0])

        ann_df = sparql(ep, f"""
            SELECT (COUNT(DISTINCT ?e) AS ?n)
            WHERE {{
                GRAPH <{G_TAX}> {{ ?e wp:organism ?t . FILTER(?t != ncbi:33090) }}
                GRAPH <{G_PW}>  {{ ?e a {wp_class} }}
            }}
        """)
        annotated = int(ann_df["n"].iloc[0])

        rows.append({"entity": entity_label, "total": total, "annotated": annotated})
        print(f"  {entity_label}: total={total:,}  annotated={annotated:,}")

    return save(pd.DataFrame(rows), out_dir, "annotation_summary.csv")


def cumulative_coverage(ep: str, out_dir: Path) -> pd.DataFrame:
    """True cumulative *unique*-entity coverage curves.

    genes/enzymes/metabolites use a shared, identifiers.org-style URI that is
    reused across every pathway the entity participates in, so simply summing
    per-pathway counts double-counts shared entities (e.g. metabolites sum to
    22,109 "pathway memberships" vs only 4,577 truly distinct wp:Metabolite
    nodes). Conversions and Catalysis interactions, by contrast, are minted
    with a pathway-specific URI (one Conversion belongs to exactly one
    pathway), so their per-pathway counts already sum to the true unique
    total with no adjustment needed.

    For genes/enzymes/metabolites we fetch the full (pathway, entity)
    membership list, rank pathways by their distinct-entity contribution
    (descending, matching the existing "ranked by contribution" framing),
    and accumulate the *unique* entities seen so far at each step.
    """
    print("Cumulative coverage curves (true unique-entity accumulation) ...")
    rows = []

    def unique_curve(wp_class: str, total: int) -> list[float]:
        df = sparql(ep, f"""
            SELECT ?pwID ?entity
            FROM <{G_PW}>
            WHERE {{
                ?pwID a wp:Pathway .
                ?entity a {wp_class} ; dcterms:isPartOf ?pwID .
            }}
        """)
        by_pw = df.groupby("pwID")["entity"].apply(set)
        by_pw = by_pw.sort_values(key=lambda s: s.apply(len), ascending=False)
        seen: set[str] = set()
        curve = []
        for s in by_pw:
            seen |= s
            curve.append(len(seen) / total if total else 0.0)
        return curve

    def simple_curve(csv_name: str, count_col: str, total: int) -> list[float]:
        df = pd.read_csv(out_dir / csv_name)
        s = pd.to_numeric(df[count_col], errors="coerce").fillna(0).sort_values(ascending=False)
        return (s.cumsum() / total).tolist() if total else s.cumsum().tolist()

    totals = pd.read_csv(out_dir / "entity_totals.csv").set_index("entity")["count"]

    for label, curve in [
        ("Genes",       unique_curve("wp:GeneProduct", int(totals["Genes"]))),
        ("Enzymes",     unique_curve("wp:Protein",     int(totals["Enzymes"]))),
        ("Metabolites", unique_curve("wp:Metabolite",  int(totals["Metabolites"]))),
        ("Conversions", simple_curve("conversions_per_pathway.csv", "count", int(totals["Conversions"]))),
    ]:
        print(f"  {label}: {len(curve):,} pathways, reaches {curve[-1]*100:.1f}% of {totals[label]:,}")
        for rank, frac in enumerate(curve, start=1):
            rows.append({"metric": label, "rank": rank, "cumulative_fraction": frac})

    # Catalysis: same pathway-unique-URI property as Conversion, so a simple
    # per-pathway count (no membership-list query needed) is already correct.
    cat_pw = sparql(ep, f"""
        SELECT ?pwID (COUNT(DISTINCT ?cat) AS ?count)
        FROM <{G_PW}>
        WHERE {{ ?pwID a wp:Pathway . ?cat a wp:Catalysis ; dcterms:isPartOf ?pwID . }}
        GROUP BY ?pwID
    """)
    save(cat_pw, out_dir, "catalysis_per_pathway.csv")
    cat_curve = simple_curve("catalysis_per_pathway.csv", "count", int(totals["Catalysis"]))
    print(f"  Catalysis: {len(cat_curve):,} pathways, reaches {cat_curve[-1]*100:.1f}% of {totals['Catalysis']:,}")
    for rank, frac in enumerate(cat_curve, start=1):
        rows.append({"metric": "Catalysis", "rank": rank, "cumulative_fraction": frac})

    return save(pd.DataFrame(rows), out_dir, "cumulative_coverage.csv")


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
    """Per-species counts: pathways, genes, enzymes + indirect metabolites/conversions/catalysis/publications.

    Three annotation strategies:
      DIRECT          — wp:organism on the entity itself (only genes/proteins in PlantCyc)
      INDIRECT, CHAIN  — via the actual reaction graph: species X's enzyme E is
                 wp:source of a wp:Catalysis whose wp:target is a specific
                 wp:Conversion; only that conversion (and catalysis step)
                 and its own metabolites are attributed to X (genes are
                 chained through E via wp:TranscriptionTranslation). This
                 replaced an earlier, looser "same pathway" rule that
                 over-attributed every metabolite/conversion in a pathway to
                 any species with a gene anywhere in it.
      INDIRECT, PATHWAY — publications only: BioCyc citations are curated at
                 pathway/reaction granularity, so they stay pathway-level
                 (kept in the CSV for reference; not chain-attributable, so
                 not used in the species-combined figure).

    `pathways` is the single (not direct/indirect split) count of pathways
    containing a direct gene/protein node of that species.

    Queries joined in Python (each simple enough not to time out).
    """
    print("Per-species metrics (direct + chain-indirect, Python join) ...")

    # ── Direct annotations ────────────────────────────────────────────────────

    # Q1: pathways per species (direct: gene/protein node in pathway)
    print("  pathways per species (direct) ...")
    q_pw = sparql(ep, f"""
        SELECT ?taxon ?species (COUNT(DISTINCT ?pw) AS ?pathways)
        WHERE {{
            GRAPH <{G_TAX}>  {{ ?node wp:organism ?taxon . FILTER(?taxon != ncbi:33090) }}
            GRAPH <{G_PW}>   {{ ?node dcterms:isPartOf ?pw . ?pw a wp:Pathway . }}
            GRAPH <{G_NCBI}> {{ ?taxon rdfs:label ?species . }}
        }}
        GROUP BY ?taxon ?species
    """)
    print(f"    {len(q_pw):,} species")

    # Q2: genes per species (direct)
    print("  genes per species (direct) ...")
    q_genes = sparql(ep, f"""
        SELECT ?taxon (COUNT(DISTINCT ?entity) AS ?genes)
        WHERE {{
            GRAPH <{G_TAX}> {{ ?entity wp:organism ?taxon . FILTER(?taxon != ncbi:33090) }}
            GRAPH <{G_PW}>  {{ ?entity a wp:GeneProduct . }}
        }}
        GROUP BY ?taxon
    """)

    # Q3: enzymes per species (direct)
    print("  enzymes per species (direct) ...")
    q_enzymes = sparql(ep, f"""
        SELECT ?taxon (COUNT(DISTINCT ?entity) AS ?enzymes)
        WHERE {{
            GRAPH <{G_TAX}> {{ ?entity wp:organism ?taxon . FILTER(?taxon != ncbi:33090) }}
            GRAPH <{G_PW}>  {{ ?entity a wp:Protein . }}
        }}
        GROUP BY ?taxon
    """)

    # ── Indirect annotations via the actual catalysis chain ──────────────────
    # Strategy: species X has enzyme E (a wp:Protein, or a wp:GeneProduct whose
    # product is E via wp:TranscriptionTranslation). Only the wp:Catalysis
    # step(s) E actually participates in (wp:source E), the wp:Conversion(s)
    # each catalysis targets, and the metabolites that specific conversion's
    # wp:source/wp:target point to are attributed to X — *not* every
    # metabolite/conversion merely co-occurring in the same pathway.

    catalysis_chain = f"""
        {{ ?cat a wp:Catalysis ; wp:source ?entity ; wp:target ?conversion . }}
        UNION
        {{
            ?tt  a wp:TranscriptionTranslation ; wp:source ?entity ; wp:target ?protein .
            ?cat a wp:Catalysis ; wp:source ?protein ; wp:target ?conversion .
        }}
    """

    # Q4: metabolites per species (indirect via the specific catalysis chain)
    print("  metabolites per species (indirect via catalysis chain) ...")
    q_metabolites = sparql(ep, f"""
        SELECT ?taxon (COUNT(DISTINCT ?metabolite) AS ?metabolites)
        WHERE {{
            GRAPH <{G_TAX}> {{ ?entity wp:organism ?taxon . FILTER(?taxon != ncbi:33090) }}
            GRAPH <{G_PW}>  {{
                {catalysis_chain}
                ?conversion (wp:source|wp:target) ?metabolite .
                ?metabolite a wp:Metabolite .
            }}
        }}
        GROUP BY ?taxon
    """)

    # Q5: conversions per species (indirect via the specific catalysis chain)
    print("  conversions per species (indirect via catalysis chain) ...")
    q_conversions = sparql(ep, f"""
        SELECT ?taxon (COUNT(DISTINCT ?conversion) AS ?conversions)
        WHERE {{
            GRAPH <{G_TAX}> {{ ?entity wp:organism ?taxon . FILTER(?taxon != ncbi:33090) }}
            GRAPH <{G_PW}>  {{ {catalysis_chain} }}
        }}
        GROUP BY ?taxon
    """)

    # Q5b: catalysis interactions per species (the chain step itself, i.e. the
    # specific wp:Catalysis edges the species' enzyme(s) actually participate
    # in — distinct from Q5's count of the *conversions* those edges target).
    print("  catalysis interactions per species (via catalysis chain) ...")
    q_catalysis = sparql(ep, f"""
        SELECT ?taxon (COUNT(DISTINCT ?cat) AS ?catalysis)
        WHERE {{
            GRAPH <{G_TAX}> {{ ?entity wp:organism ?taxon . FILTER(?taxon != ncbi:33090) }}
            GRAPH <{G_PW}>  {{ {catalysis_chain} }}
        }}
        GROUP BY ?taxon
    """)

    # Q6: publications per species (indirect via pathway references) — kept at
    # the pathway level: BioCyc citations are curated per-pathway/per-reaction,
    # not per-reaction-step, so there is no finer-grained chain to follow here.
    # Not used in the species-combined figure (publications are pathway-level
    # only, not chain-attributable), but kept in the CSV for reference.
    print("  publications per species (indirect via pathway references) ...")
    q_pubs = sparql(ep, f"""
        PREFIX cito: <http://purl.org/spar/cito/>
        SELECT ?taxon (COUNT(DISTINCT ?pub) AS ?publications)
        WHERE {{
            GRAPH <{G_TAX}> {{ ?geneNode wp:organism ?taxon . FILTER(?taxon != ncbi:33090) }}
            GRAPH <{G_PW}>  {{
                ?geneNode dcterms:isPartOf ?pw . ?pw a wp:Pathway .
                ?pw (dcterms:references | cito:cites) ?pub .
            }}
        }}
        GROUP BY ?taxon
    """)

    # ── Join all results in Python ────────────────────────────────────────────
    df = (q_pw
          .merge(q_genes,       on="taxon", how="left")
          .merge(q_enzymes,     on="taxon", how="left")
          .merge(q_metabolites, on="taxon", how="left")
          .merge(q_conversions, on="taxon", how="left")
          .merge(q_catalysis,   on="taxon", how="left")
          .merge(q_pubs,        on="taxon", how="left")
          .fillna(0))
    for col in ("pathways", "genes", "enzymes", "metabolites", "conversions",
                "catalysis", "publications"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    df["taxon_id"] = df["taxon"].str.rsplit("_", n=1).str[-1]
    df = df.sort_values("pathways", ascending=False)

    return save(df[["species", "taxon_id", "pathways", "genes", "enzymes",
                     "metabolites", "conversions", "catalysis", "publications"]],
                out_dir, "per_species_nrs.csv")


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
    interaction_subtypes_per_pathway(args.endpoint, args.out_dir)
    pathway_titles(args.endpoint, args.out_dir)
    annotation_summary(args.endpoint, args.out_dir)
    entity_totals(args.endpoint, args.out_dir)
    cumulative_coverage(args.endpoint, args.out_dir)

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
