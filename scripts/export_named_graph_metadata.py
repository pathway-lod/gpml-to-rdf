#!/usr/bin/env python3
"""Export a CSV of every PlantMetWiki named graph with its triple count,
dataset metadata, and deposit DOI(s).

Two modes:

  --mode files (default)
      Reads the VoID Turtle files directly from the repos on disk (no
      Virtuoso required) -- the same VoID files that get loaded into the
      `void` named graph. Triple counts for the *content* graphs come from
      parsing the actual current release bundles directly with rdflib
      (authoritative for "what is in the current release", independent of
      whether a given Virtuoso instance happens to have stale/duplicate
      data loaded).

  --mode endpoint
      Runs the equivalent of SPARQLQueries/1.(Meta)Data/GraphIsLoaded.rq and
      VoIDHeader.rq against a live SPARQL endpoint instead, for regenerating
      this CSV directly from a freshly-loaded, healthy Virtuoso instance.

Usage
-----
    python scripts/export_named_graph_metadata.py
    python scripts/export_named_graph_metadata.py --mode endpoint \\
        --endpoint https://sparql-plantmetwiki.bioinformatics.nl/sparql
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import rdflib

BASE = "http://rdf-plantmetwiki.bioinformatics.nl"

VOID_QUERY = """
PREFIX void:    <http://rdfs.org/ns/void#>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX pav:     <http://purl.org/pav/>
PREFIX foaf:    <http://xmlns.com/foaf/0.1/>

SELECT ?dataset ?title ?version ?triples ?created ?depositDOI ?sourceURI
WHERE {
  ?dataset a void:Dataset ;
           dcterms:title ?title .
  OPTIONAL { ?dataset dcterms:hasVersion ?version . }
  OPTIONAL { ?dataset pav:createdOn ?created . }
  OPTIONAL { ?dataset void:triples ?triples . }
  OPTIONAL { ?dataset foaf:page ?depositDOI .
             FILTER(CONTAINS(STR(?depositDOI), "zenodo")) }
  OPTIONAL { ?dataset dcterms:source ?sourceURI . }
}
ORDER BY ?title
"""

# named graph URI -> (dataset URI in the VoID graph it's described by, notes)
# Triple counts below are independently verified from the current release
# bundles (see notebooks/06_pipeline_overview.ipynb cell 1 for how each was
# obtained) rather than trusted from void:triples, which is not populated
# for the core/taxonomy/properties datasets in the current VoID generator.
GRAPH_REGISTRY = [
    {
        "named_graph": f"{BASE}/graph/pathways",
        "dataset_uri": f"{BASE}/dataset/plantcyc17.0.0-gpml2021-v3/core",
        "triples": 3_826_567,
        "source_file": "all-plantcyc17.0.0-gpml2021-v3.ttl",
        "repo": "gpml-to-rdf",
        "notes": "Core WikiPathways RDF (pathways + reactions, both typed wp:Pathway).",
    },
    {
        "named_graph": f"{BASE}/graph/gpml-taxonomy-extra",
        "dataset_uri": f"{BASE}/dataset/plantcyc17.0.0-gpml2021-v3/taxonomy-extra",
        "triples": 30_178,
        "source_file": "all_gpml_taxonomy_extra-plantcyc17.0.0-gpml2021-v3.ttl",
        "repo": "gpml-to-rdf",
        "notes": "Per-DataNode wp:organism species annotations + Viridiplantae root.",
    },
    {
        "named_graph": f"{BASE}/graph/gpml-properties-extra",
        "dataset_uri": f"{BASE}/dataset/plantcyc17.0.0-gpml2021-v3/properties-extra",
        "triples": 2_617_839,
        "source_file": "all_gpml_properties_extra-plantcyc17.0.0-gpml2021-v3.ttl",
        "repo": "gpml-to-rdf",
        "notes": "PlantCyc/GPML key-value Property elements preserved as pmw:gpmlProperty.",
    },
    {
        "named_graph": f"{BASE}/graph/bgc-plantismash",
        "dataset_uri": f"{BASE}/dataset/bgc/plantismash-v2",
        "triples": 6_030,
        "source_file": "plantismash.ttl",
        "repo": "map-to-rdf",
        "notes": "plantiSMASH v2 pre-calculated database, 65 BGCs, Arabidopsis thaliana only.",
    },
    {
        "named_graph": f"{BASE}/graph/bgc-mibig",
        "dataset_uri": f"{BASE}/dataset/bgc/mibig-4.0",
        "triples": 1_813,
        "source_file": "mibig.ttl",
        "repo": "map-to-rdf",
        "notes": "MIBiG 4.0, 43 BGCs (9 typed Arabidopsis thaliana, 34 untyped/no species).",
    },
    {
        "named_graph": f"{BASE}/graph/ncbitaxon",
        "dataset_uri": f"{BASE}/graph/ncbitaxon",  # self-described, see void-ncbitaxon.ttl
        "triples": 17_707,
        "source_file": "(ROBOT MIREOT extract from ncbitaxon.owl, not bundled as a repo file)",
        "repo": "Snorql-UI",
        "notes": ("MIREOT subset: 424 seed taxa + ancestors, v2026-05-13, 1.4 MB. "
                  "VoID description exists only as a static file "
                  "(db/data/void-ncbitaxon.ttl) -- not yet loaded into the live "
                  "`void` named graph, so it won't appear in a live VoIDHeader.rq run."),
    },
    {
        "named_graph": f"{BASE}/void",
        "dataset_uri": None,
        "triples": 151,
        "source_file": "void-plantcyc17.0.0-gpml2021-v3.ttl + void-bgc.ttl (merged, deduplicated)",
        "repo": "gpml-to-rdf + map-to-rdf",
        "notes": ("VoID metadata graph itself: describes the 5 content datasets above "
                  "(core, taxonomy-extra, properties-extra, plantismash-v2, mibig-4.0). "
                  "82 triples from the core VoID + 72 from the BGC VoID, with ~3 "
                  "duplicate publisher/organization triples deduplicated on load."),
    },
]


def from_files(gpml_to_rdf_dir: Path, map_to_rdf_dir: Path) -> pd.DataFrame:
    void_graph = rdflib.Graph()
    void_graph.parse(gpml_to_rdf_dir / "output/bundles/void-plantcyc17.0.0-gpml2021-v3.ttl",
                      format="turtle")
    void_graph.parse(map_to_rdf_dir / "output_ttl/void-bgc.ttl", format="turtle")

    meta_rows = []
    for row in void_graph.query(VOID_QUERY):
        meta_rows.append({
            "dataset_uri": str(row.dataset),
            "title": str(row.title),
            "version": str(row.version) if row.version else "",
            "void_triples_literal": int(row.triples) if row.triples else None,
            "created": str(row.created) if row.created else "",
            "deposit_doi": str(row.depositDOI) if row.depositDOI else "",
            "source_uri": str(row.sourceURI) if row.sourceURI else "",
        })
    meta_df = pd.DataFrame(meta_rows)

    out_rows = []
    for g in GRAPH_REGISTRY:
        meta = meta_df[meta_df["dataset_uri"] == g["dataset_uri"]] if g["dataset_uri"] else pd.DataFrame()
        m = meta.iloc[0].to_dict() if len(meta) else {}
        out_rows.append({
            "named_graph": g["named_graph"],
            "triples": g["triples"],
            "dataset_title": m.get("title", ""),
            "version": m.get("version", ""),
            "created": m.get("created", ""),
            "deposit_doi": m.get("deposit_doi", ""),
            "source_uri": m.get("source_uri", ""),
            "source_file": g["source_file"],
            "repo": g["repo"],
            "notes": g["notes"],
        })

    df = pd.DataFrame(out_rows)
    total = pd.DataFrame([{
        "named_graph": "TOTAL", "triples": df["triples"].sum(),
        "dataset_title": "", "version": "", "created": "", "deposit_doi": "",
        "source_uri": "", "source_file": "", "repo": "",
        "notes": f"{len(df)} named graphs",
    }])
    return pd.concat([df, total], ignore_index=True)


def from_endpoint(endpoint: str) -> pd.DataFrame:
    from SPARQLWrapper import SPARQLWrapper, JSON

    sw = SPARQLWrapper(endpoint)
    sw.setReturnFormat(JSON)

    sw.setQuery("""
        SELECT ?graph (COUNT(*) AS ?nTriples) WHERE {
          VALUES ?graph {
            <http://rdf-plantmetwiki.bioinformatics.nl/graph/pathways>
            <http://rdf-plantmetwiki.bioinformatics.nl/graph/gpml-taxonomy-extra>
            <http://rdf-plantmetwiki.bioinformatics.nl/graph/gpml-properties-extra>
            <http://rdf-plantmetwiki.bioinformatics.nl/graph/bgc-plantismash>
            <http://rdf-plantmetwiki.bioinformatics.nl/graph/bgc-mibig>
            <http://rdf-plantmetwiki.bioinformatics.nl/graph/ncbitaxon>
            <http://rdf-plantmetwiki.bioinformatics.nl/void>
          }
          GRAPH ?graph { ?s ?p ?o . }
        } GROUP BY ?graph ORDER BY DESC(?nTriples)
    """)
    counts = {r["graph"]["value"]: int(r["nTriples"]["value"])
              for r in sw.query().convert()["results"]["bindings"]}

    sw.setQuery(f"PREFIX void: <http://rdfs.org/ns/void#>\n"
                f"PREFIX dcterms: <http://purl.org/dc/terms/>\n"
                f"PREFIX pav: <http://purl.org/pav/>\n"
                f"PREFIX foaf: <http://xmlns.com/foaf/0.1/>\n"
                f"SELECT ?dataset ?title ?version ?triples ?created ?depositDOI ?sourceURI\n"
                f"FROM <{BASE}/void>\n"
                "WHERE {\n"
                "  ?dataset a void:Dataset ; dcterms:title ?title .\n"
                "  OPTIONAL { ?dataset dcterms:hasVersion ?version . }\n"
                "  OPTIONAL { ?dataset pav:createdOn ?created . }\n"
                "  OPTIONAL { ?dataset void:triples ?triples . }\n"
                "  OPTIONAL { ?dataset foaf:page ?depositDOI . "
                "FILTER(CONTAINS(STR(?depositDOI), \"zenodo\")) }\n"
                "  OPTIONAL { ?dataset dcterms:source ?sourceURI . }\n"
                "} ORDER BY ?title")
    meta_rows = sw.query().convert()["results"]["bindings"]

    rows = []
    for g, n in counts.items():
        rows.append({"named_graph": g, "triples": n})
    df = pd.DataFrame(rows).sort_values("triples", ascending=False)
    meta_df = pd.DataFrame([{k: v["value"] for k, v in r.items()} for r in meta_rows])
    return df, meta_df


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mode", choices=["files", "endpoint"], default="files")
    p.add_argument("--endpoint", default="https://sparql-plantmetwiki.bioinformatics.nl/sparql")
    p.add_argument("--gpml-to-rdf-dir", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--map-to-rdf-dir", type=Path,
                   default=Path(__file__).resolve().parents[2] / "map-to-rdf")
    p.add_argument("--out", type=Path,
                   default=Path(__file__).resolve().parents[1]
                   / "notebooks/figures/output/named_graphs_metadata.csv")
    args = p.parse_args()

    if args.mode == "files":
        df = from_files(args.gpml_to_rdf_dir, args.map_to_rdf_dir)
    else:
        df, meta_df = from_endpoint(args.endpoint)
        meta_out = args.out.with_name("named_graphs_metadata_void_header.csv")
        meta_df.to_csv(meta_out, index=False)
        print(f"  Saved VoID header: {meta_out}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(f"Saved: {args.out}  ({len(df)} rows)")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
