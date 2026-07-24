#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
from pathlib import Path


PMN_LICENSE_URI = "http://rdf-plantmetwiki.bioinformatics.nl/license/pmn-open-database-license"
PMN_LICENSE_PAGE = "https://plantcyc.org/?webform=license-agreement"
PMN_LICENSE_TITLE = "OPEN DATABASE LICENSE FOR THE PLANT METABOLIC NETWORK DATABASES"
PMN_LICENSE_RIGHTS = (
    "OPEN DATABASE LICENSE FOR THE PLANT METABOLIC NETWORK DATABASES (PMN). "
    "The databases may be used royalty-free worldwide and may be modified and "
    "redistributed, provided that derived copies clearly identify the source "
    "database(s), include applicable copyright notices and author lists, and "
    "identify or summarize modifications."
)

PUBLISHER_URI = "http://rdf-plantmetwiki.bioinformatics.nl/organization/wur-plant-sciences"
PUBLISHER_NAME = "Wageningen University & Research, Department of Plant Sciences"
PUBLISHER_HOMEPAGE = "https://www.wur.nl/"

# Documents the wp:/pmw: RDF model used by all PlantMetWiki datasets.
CLASS_STRUCTURE_PAGE = (
    "https://github.com/pathway-lod/gpml-to-rdf/blob/main/README.md"
    "#three-layer-rdf-architecture"
)

# BridgeDb metabolite cross-reference predicates materialised in the core graph
# (org.pathvisio.io.rdf BridgeDbIDMapper, bundled in gpml2rdf-4.0.4-SNAPSHOT.jar).
# Canonical public SPARQL endpoint (must match the URL monitored by YummyData and
# declared to consumers). Used for both void:sparqlEndpoint and the sd:Service.
SPARQL_ENDPOINT = "https://plantmetwiki.bioinformatics.nl/sparql"


def add_service_description(lines: list[str], core_dataset: str) -> None:
    """Emit a SPARQL 1.1 Service Description for the public endpoint, combined into
    the VoID document. Advertises the endpoint URL, query language, result formats
    and features, and links its default dataset to the core VoID dataset — this is
    what tools like YummyData look for when dereferencing the endpoint."""
    svc = f"{SPARQL_ENDPOINT}#service"
    ds = f"{SPARQL_ENDPOINT}#dataset"
    lines.extend(
        [
            f"{ttl_uri(svc)} a sd:Service ;",
            f"    sd:endpoint {ttl_uri(SPARQL_ENDPOINT)} ;",
            "    sd:supportedLanguage sd:SPARQL11Query ;",
            "    sd:resultFormat formats:Turtle , formats:RDF_XML , formats:N-Triples ,",
            "                    formats:SPARQL_Results_JSON , formats:SPARQL_Results_XML , formats:SPARQL_Results_CSV ;",
            "    sd:feature sd:UnionDefaultGraph , sd:BasicFederatedQuery ;",
            f"    sd:defaultDataset {ttl_uri(ds)} .",
            "",
            f"{ttl_uri(ds)} a sd:Dataset ;",
            f"    sd:defaultGraph [ a sd:Graph ; dcterms:isPartOf {ttl_uri(core_dataset)} ] .",
            "",
        ]
    )


BRIDGEDB_LINK_PREDICATES = [
    "http://vocabularies.wikipathways.org/wp#bdbChEBI",
    "http://vocabularies.wikipathways.org/wp#bdbHmdb",
    "http://vocabularies.wikipathways.org/wp#bdbWikidata",
    "http://vocabularies.wikipathways.org/wp#bdbPubChem",
    "http://vocabularies.wikipathways.org/wp#bdbKeggCompound",
    "http://vocabularies.wikipathways.org/wp#bdbLipidMaps",
    "http://vocabularies.wikipathways.org/wp#bdbChemspider",
    "http://vocabularies.wikipathways.org/wp#bdbInChIKey",
]


def add_bridgedb_linkset(
    lines: list[str],
    core_dataset: str,
    build: str,
    source_doi: str,
    today: str,
) -> None:
    """Describe the BridgeDb-materialised metabolite cross-references (wp:bdb*)
    as a void:Linkset that is a subset of the core dataset, with the BridgeDb
    mapping database recorded as its source."""
    linkset = f"{core_dataset}/bridgedb-linkset"
    source_uri = f"https://doi.org/{source_doi}"

    # BridgeDb mapping database (figshare) as a source void:Dataset
    lines.extend(
        [
            f"{ttl_uri(source_uri)} a void:Dataset ;",
            f"    dcterms:title {ttl_literal('Metabolite BridgeDb ID Mapping Database (' + build + ')', 'en')} ;",
            f"    dcterms:identifier {ttl_literal(source_doi)} ;",
            f"    dcterms:description {ttl_literal('BridgeDb metabolite identifier-mapping database built from HMDB, ChEBI and Wikidata; used to materialise metabolite cross-references during GPML-to-RDF conversion.', 'en')} ;",
            f"    pav:version {ttl_literal(build)} ;",
            f"    foaf:page {ttl_uri(source_uri)} .",
            "",
        ]
    )

    # The cross-references themselves as a void:Linkset (subset of core)
    lines.extend(
        [
            f"{ttl_uri(linkset)} a void:Linkset ;",
            f"    dcterms:title {ttl_literal('PlantMetWiki metabolite BridgeDb cross-references', 'en')} ;",
            f"    dcterms:description {ttl_literal('BridgeDb-materialised cross-references (wp:bdb* predicates) linking PlantMetWiki wp:Metabolite nodes to ChEBI, HMDB, Wikidata, PubChem, KEGG Compound, LipidMaps, ChemSpider and InChIKey. Added under dedicated predicates that augment, and never overwrite, the curated PlantCyc source identifier.', 'en')} ;",
            f"    void:subjectsTarget {ttl_uri(core_dataset)} ;",
            f"    dcterms:source {ttl_uri(source_uri)} ;",
            f"    pav:derivedFrom {ttl_uri(source_uri)} ;",
            f"    pav:createdWith {ttl_literal('gpml2rdf-4.0.4-SNAPSHOT.jar (org.pathvisio.io.rdf BridgeDbIDMapper)')} ;",
            f"    pav:version {ttl_literal(build)} ;",
            f"    pav:createdOn {ttl_literal(today)}^^xsd:date ;",
        ]
    )
    for pred in BRIDGEDB_LINK_PREDICATES:
        lines.append(f"    void:linkPredicate {ttl_uri(pred)} ;")
    lines.append(f"    dcterms:publisher {ttl_uri(PUBLISHER_URI)} ;")
    lines.append(f"    foaf:page {ttl_uri(source_uri)} .")
    lines.append("")

    # Tie the linkset into the core dataset
    lines.append(f"{ttl_uri(core_dataset)} void:subset {ttl_uri(linkset)} .")
    lines.append("")


def ttl_uri(uri: str) -> str:
    return f"<{uri}>"


def ttl_literal(value: str, lang: str | None = None) -> str:
    value = str(value).replace("\\", "\\\\").replace('"', '\\"')
    value = value.replace("\n", "\\n").replace("\r", "")
    return f'"{value}"@{lang}' if lang else f'"{value}"'


def add_pmn_license_document(lines: list[str]) -> None:
    lines.extend(
        [
            f"{ttl_uri(PMN_LICENSE_URI)} a dcterms:LicenseDocument ;",
            f"    dcterms:title {ttl_literal(PMN_LICENSE_TITLE, 'en')} ;",
            f"    dcterms:description {ttl_literal(PMN_LICENSE_RIGHTS, 'en')} ;",
            f"    foaf:page {ttl_uri(PMN_LICENSE_PAGE)} .",
            "",
        ]
    )


def add_publisher_org(lines: list[str]) -> None:
    lines.extend(
        [
            f"{ttl_uri(PUBLISHER_URI)} a foaf:Organization ;",
            f"    foaf:name {ttl_literal(PUBLISHER_NAME, 'en')} ;",
            f"    foaf:homepage {ttl_uri(PUBLISHER_HOMEPAGE)} .",
            "",
        ]
    )


def add_pmn_license_to_dataset(lines: list[str], dataset_uri: str) -> None:
    lines.extend(
        [
            f"{ttl_uri(dataset_uri)} dcterms:license {ttl_uri(PMN_LICENSE_URI)} ;",
            f"    dcterms:rights {ttl_literal(PMN_LICENSE_RIGHTS, 'en')} .",
            "",
        ]
    )


def count_triples_with_rapper(file_path: Path) -> int | None:
    if not file_path.exists() or not shutil.which("rapper"):
        return None

    try:
        result = subprocess.run(
            ["rapper", "-i", "turtle", "-o", "ntriples", str(file_path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.SubprocessError:
        return None

    return sum(
        1
        for line in result.stdout.splitlines()
        if line.strip() and not line.startswith("#")
    )


def file_distribution(dataset_uri: str, file_path: Path) -> list[str]:
    if not file_path.exists():
        return []

    file_uri = f"{dataset_uri}/distribution/{file_path.name}"

    return [
        f"{ttl_uri(dataset_uri)} dcat:distribution {ttl_uri(file_uri)} .",
        f"{ttl_uri(file_uri)} a dcat:Distribution ;",
        f"    dcterms:title {ttl_literal(file_path.name)} ;",
        f"    dcat:byteSize {file_path.stat().st_size} .",
        "",
    ]


def add_dataset_file_info(lines: list[str], dataset_uri: str, file_path: Path) -> None:
    lines.extend(file_distribution(dataset_uri, file_path))

    triples = count_triples_with_rapper(file_path)
    if triples is not None:
        lines.append(f"{ttl_uri(dataset_uri)} void:triples {triples} .")
        lines.append("")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--metadata-file",
        default="build/zenodo_gpml_metadata.json",
    )
    parser.add_argument("--core-rdf", required=True)
    parser.add_argument("--taxonomy-extra", required=True)
    parser.add_argument("--properties-extra", required=True)
    parser.add_argument("--output", required=True)
    # BridgeDb metabolite mapping (optional; enables the wp:bdb* linkset in VoID)
    parser.add_argument(
        "--bridgedb-build",
        default=None,
        help="BridgeDb metabolite mapping DB build (e.g. 20260102). If set, a "
        "void:Linkset describing the materialised wp:bdb* cross-references is added.",
    )
    parser.add_argument(
        "--bridgedb-source-doi",
        default="10.6084/m9.figshare.30993322",
        help="DOI of the BridgeDb metabolite mapping database (figshare).",
    )
    # RDF release record + human-facing release version (Zenodo of the RDF bundles)
    parser.add_argument(
        "--rdf-conceptdoi",
        default=None,
        help="Concept DOI of the RDF release record on Zenodo (self-identifier of these bundles).",
    )
    parser.add_argument(
        "--release-version",
        default=None,
        help="Human-facing release version of the RDF deposit, e.g. 3.2.",
    )

    args = parser.parse_args()

    metadata = json.loads(Path(args.metadata_file).read_text(encoding="utf-8"))

    version = metadata["version"]
    title = metadata.get("title", f"PlantCyc GPML release {version}")
    doi = metadata.get("doi")
    conceptdoi = metadata.get("conceptdoi")
    publication_date = metadata.get("publication_date")
    record_url = metadata.get("zenodo_record_url")

    today = dt.date.today().isoformat()

    base = "http://rdf-plantmetwiki.bioinformatics.nl/dataset"
    core_dataset       = f"{base}/{version}/core"
    taxonomy_dataset   = f"{base}/{version}/taxonomy-extra"
    properties_dataset = f"{base}/{version}/properties-extra"

    lines = [
        "@prefix void:    <http://rdfs.org/ns/void#> .",
        "@prefix dcterms: <http://purl.org/dc/terms/> .",
        "@prefix pav:     <http://purl.org/pav/> .",
        "@prefix dcat:    <http://www.w3.org/ns/dcat#> .",
        "@prefix foaf:    <http://xmlns.com/foaf/0.1/> .",
        "@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .",
        "@prefix sd:      <http://www.w3.org/ns/sparql-service-description#> .",
        "@prefix formats: <http://www.w3.org/ns/formats/> .",
        "",
    ]

    add_pmn_license_document(lines)
    add_publisher_org(lines)

    # Source GPML dataset — the Zenodo record that was used as input.
    # Recording this as a void:Dataset makes the provenance navigable: anyone
    # loading this VoID can follow the DOI to find the exact GPML release.
    if doi:
        source_uri = f"https://doi.org/{doi}"
        lines.extend(
            [
                f"{ttl_uri(source_uri)} a void:Dataset ;",
                f"    dcterms:title {ttl_literal(title, 'en')} ;",
                f"    dcterms:identifier {ttl_literal(doi)} ;",
                f"    dcterms:hasVersion {ttl_literal(version)} ;",
                f"    foaf:page {ttl_uri(source_uri)} .",
                "",
            ]
        )
    if conceptdoi and conceptdoi != doi:
        concept_uri = f"https://doi.org/{conceptdoi}"
        lines.extend(
            [
                f"{ttl_uri(concept_uri)} a void:Dataset ;",
                f"    dcterms:title {ttl_literal(title + ' (concept DOI — always resolves to latest release)', 'en')} ;",
                f"    dcterms:identifier {ttl_literal(conceptdoi)} ;",
                f"    foaf:page {ttl_uri(concept_uri)} .",
                "",
            ]
        )

    lines.extend(
        [
            f"{ttl_uri(core_dataset)} a void:Dataset ;",
            f"    dcterms:title {ttl_literal('PlantMetWiki core RDF derived from ' + title, 'en')} ;",
            f"    dcterms:description {ttl_literal('Core WikiPathways RDF generated from PlantCyc-derived GPML2021 pathway and reaction files.', 'en')} ;",
            f"    dcterms:hasVersion {ttl_literal(version)} ;",
            f"    pav:version {ttl_literal(version)} ;",
            f"    pav:createdOn {ttl_literal(today)}^^xsd:date ;",
            f"    pav:createdWith {ttl_literal('gpml2rdf-4.0.4-SNAPSHOT.jar')} ;",
            f"    void:sparqlEndpoint {ttl_uri(SPARQL_ENDPOINT)} ;",
            f"    void:vocabulary {ttl_uri('http://vocabularies.wikipathways.org/wp#')} ,",
            f"                    {ttl_uri('http://vocabularies.wikipathways.org/gpml#')} ,",
            f"                    {ttl_uri('http://purl.org/dc/terms/')} ,",
            f"                    {ttl_uri('http://purl.org/pav/')} ;",
            f"    foaf:homepage {ttl_uri('https://plantmetwiki.bioinformatics.nl/')} .",
            "",
            f"{ttl_uri(taxonomy_dataset)} a void:Dataset ;",
            f"    dcterms:title {ttl_literal('PlantMetWiki taxonomy extra RDF derived from ' + title, 'en')} ;",
            f"    dcterms:description {ttl_literal('Extra RDF layer adding Viridiplantae pathway/reaction annotations and specific NCBI Taxonomy annotations for GeneProduct and Protein nodes. Taxon IRIs use the OBO Foundry NCBITaxon namespace (purl.obolibrary.org/obo/NCBITaxon_).', 'en')} ;",
            f"    dcterms:isPartOf {ttl_uri(core_dataset)} ;",
            f"    dcterms:hasVersion {ttl_literal(version)} ;",
            f"    dcterms:references {ttl_uri('http://purl.obolibrary.org/obo/ncbitaxon.owl')} ;",
            f"    void:vocabulary {ttl_uri('http://purl.obolibrary.org/obo/NCBITaxon_')} ;",
            f"    pav:createdOn {ttl_literal(today)}^^xsd:date .",
            "",
            f"{ttl_uri(properties_dataset)} a void:Dataset ;",
            f"    dcterms:title {ttl_literal('PlantMetWiki GPML property extra RDF derived from ' + title, 'en')} ;",
            f"    dcterms:description {ttl_literal('Extra RDF layer preserving PlantCyc and GPML key-value Property elements from Pathway, DataNode, and Interaction elements.', 'en')} ;",
            f"    dcterms:isPartOf {ttl_uri(core_dataset)} ;",
            f"    dcterms:hasVersion {ttl_literal(version)} ;",
            f"    pav:createdOn {ttl_literal(today)}^^xsd:date .",
            "",
        ]
    )

    all_datasets = [core_dataset, taxonomy_dataset, properties_dataset]

    if doi:
        source_uri = f"https://doi.org/{doi}"
        for ds in all_datasets:
            lines.append(f"{ttl_uri(ds)} dcterms:source {ttl_uri(source_uri)} .")
        lines.append("")

    if conceptdoi:
        concept_uri = f"https://doi.org/{conceptdoi}"
        for ds in all_datasets:
            lines.append(f"{ttl_uri(ds)} pav:derivedFrom {ttl_uri(concept_uri)} .")
        lines.append("")

    # foaf:page on every dataset → concept DOI landing page on Zenodo.
    # Use the concept DOI so the link always resolves to the latest version.
    if conceptdoi:
        concept_page = f"https://doi.org/{conceptdoi}"
        for ds in all_datasets:
            lines.append(f"{ttl_uri(ds)} foaf:page {ttl_uri(concept_page)} .")
        lines.append("")
    elif record_url:
        # Fallback: specific-version record URL (less preferred than concept DOI)
        for ds in all_datasets:
            lines.append(f"{ttl_uri(ds)} foaf:page {ttl_uri(record_url)} .")
        lines.append("")

    # dcterms:issued = date the RDF was generated (today), not the GPML input date.
    # The GPML input date is already captured via dcterms:source / pav:derivedFrom above.
    # dcterms:modified mirrors dcterms:issued here since each release regenerates
    # the full bundle from scratch (no incremental updates).
    for ds in all_datasets:
        lines.append(f"{ttl_uri(ds)} dcterms:issued {ttl_literal(today)}^^xsd:date .")
        lines.append(f"{ttl_uri(ds)} dcterms:modified {ttl_literal(today)}^^xsd:date .")
    lines.append("")

    for ds in all_datasets:
        lines.append(f"{ttl_uri(ds)} dcterms:publisher {ttl_uri(PUBLISHER_URI)} .")
        lines.append(f"{ttl_uri(ds)} foaf:page {ttl_uri(CLASS_STRUCTURE_PAGE)} .")
    lines.append("")

    for ds in all_datasets:
        add_pmn_license_to_dataset(lines, ds)

    add_dataset_file_info(lines, core_dataset, Path(args.core_rdf))
    add_dataset_file_info(lines, taxonomy_dataset, Path(args.taxonomy_extra))
    add_dataset_file_info(lines, properties_dataset, Path(args.properties_extra))

    # RDF release record (this deposit) + human-facing release version.
    if args.release_version:
        lines.append(
            f"{ttl_uri(core_dataset)} dcterms:hasVersion {ttl_literal(args.release_version)} ."
        )
    if args.rdf_conceptdoi:
        rdf_uri = f"https://doi.org/{args.rdf_conceptdoi}"
        lines.extend(
            [
                f"{ttl_uri(rdf_uri)} a void:Dataset ;",
                f"    dcterms:title {ttl_literal('PlantMetWiki RDF release (concept DOI — always resolves to latest version)', 'en')} ;",
                f"    dcterms:identifier {ttl_literal(args.rdf_conceptdoi)} ;",
                f"    foaf:page {ttl_uri(rdf_uri)} .",
                f"{ttl_uri(core_dataset)} dcterms:isVersionOf {ttl_uri(rdf_uri)} .",
                "",
            ]
        )

    # BridgeDb linkset (materialised metabolite cross-references) — optional.
    if args.bridgedb_build:
        add_bridgedb_linkset(
            lines,
            core_dataset,
            args.bridgedb_build,
            args.bridgedb_source_doi,
            today,
        )

    # SPARQL 1.1 Service Description (combined into the VoID document).
    add_service_description(lines, core_dataset)

    Path(args.output).write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote VoID metadata: {args.output}")


if __name__ == "__main__":
    main()