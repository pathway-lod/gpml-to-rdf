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
    core_dataset = f"{base}/{version}/core"
    taxonomy_dataset = f"{base}/{version}/taxonomy-extra"
    properties_dataset = f"{base}/{version}/properties-extra"

    lines = [
        "@prefix void:    <http://rdfs.org/ns/void#> .",
        "@prefix dcterms: <http://purl.org/dc/terms/> .",
        "@prefix pav:     <http://purl.org/pav/> .",
        "@prefix dcat:    <http://www.w3.org/ns/dcat#> .",
        "@prefix foaf:    <http://xmlns.com/foaf/0.1/> .",
        "@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .",
        "",
    ]

    add_pmn_license_document(lines)

    lines.extend(
        [
            f"{ttl_uri(core_dataset)} a void:Dataset ;",
            f"    dcterms:title {ttl_literal('PlantMetWiki core RDF derived from ' + title, 'en')} ;",
            f"    dcterms:description {ttl_literal('Core WikiPathways RDF generated from PlantCyc-derived GPML2021 pathway and reaction files.', 'en')} ;",
            f"    dcterms:hasVersion {ttl_literal(version)} ;",
            f"    pav:version {ttl_literal(version)} ;",
            f"    pav:createdOn {ttl_literal(today)}^^xsd:date ;",
            f"    pav:createdWith {ttl_literal('gpml2rdf-4.0.4-SNAPSHOT.jar')} ;",
            f"    void:sparqlEndpoint {ttl_uri('https://sparql-plantmetwiki.bioinformatics.nl/sparql')} ;",
            f"    void:vocabulary {ttl_uri('http://vocabularies.wikipathways.org/wp#')} ,",
            f"                    {ttl_uri('http://vocabularies.wikipathways.org/gpml#')} ,",
            f"                    {ttl_uri('http://purl.org/dc/terms/')} ,",
            f"                    {ttl_uri('http://purl.org/pav/')} ;",
            f"    foaf:homepage {ttl_uri('https://plantmetwiki.bioinformatics.nl/')} .",
            "",
            f"{ttl_uri(taxonomy_dataset)} a void:Dataset ;",
            f"    dcterms:title {ttl_literal('PlantMetWiki taxonomy extra RDF derived from ' + title, 'en')} ;",
            f"    dcterms:description {ttl_literal('Extra RDF layer adding Viridiplantae pathway/reaction annotations and specific NCBI Taxonomy annotations for GeneProduct and Protein nodes.', 'en')} ;",
            f"    dcterms:isPartOf {ttl_uri(core_dataset)} ;",
            f"    dcterms:hasVersion {ttl_literal(version)} ;",
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

    if doi:
        source_uri = f"https://doi.org/{doi}"
        lines.append(f"{ttl_uri(core_dataset)} dcterms:source {ttl_uri(source_uri)} .")
        lines.append(f"{ttl_uri(taxonomy_dataset)} dcterms:source {ttl_uri(source_uri)} .")
        lines.append(f"{ttl_uri(properties_dataset)} dcterms:source {ttl_uri(source_uri)} .")
        lines.append("")

    if conceptdoi:
        concept_uri = f"https://doi.org/{conceptdoi}"
        lines.append(f"{ttl_uri(core_dataset)} pav:derivedFrom {ttl_uri(concept_uri)} .")
        lines.append(f"{ttl_uri(taxonomy_dataset)} pav:derivedFrom {ttl_uri(concept_uri)} .")
        lines.append(f"{ttl_uri(properties_dataset)} pav:derivedFrom {ttl_uri(concept_uri)} .")
        lines.append("")

    if record_url:
        lines.append(f"{ttl_uri(core_dataset)} foaf:page {ttl_uri(record_url)} .")
        lines.append("")

    # dcterms:issued = date the RDF was generated (today), not the GPML input date.
    # The GPML input date is already captured via dcterms:source / pav:derivedFrom above.
    lines.append(f"{ttl_uri(core_dataset)} dcterms:issued {ttl_literal(today)}^^xsd:date .")
    lines.append(f"{ttl_uri(taxonomy_dataset)} dcterms:issued {ttl_literal(today)}^^xsd:date .")
    lines.append(f"{ttl_uri(properties_dataset)} dcterms:issued {ttl_literal(today)}^^xsd:date .")
    lines.append("")

    add_pmn_license_to_dataset(lines, core_dataset)
    add_pmn_license_to_dataset(lines, taxonomy_dataset)
    add_pmn_license_to_dataset(lines, properties_dataset)

    add_dataset_file_info(lines, core_dataset, Path(args.core_rdf))
    add_dataset_file_info(lines, taxonomy_dataset, Path(args.taxonomy_extra))
    add_dataset_file_info(lines, properties_dataset, Path(args.properties_extra))

    Path(args.output).write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote VoID metadata: {args.output}")


if __name__ == "__main__":
    main()