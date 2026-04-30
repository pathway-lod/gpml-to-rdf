#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path


def ttl_uri(uri: str) -> str:
    return f"<{uri}>"


def ttl_literal(value: str, lang: str | None = None) -> str:
    value = str(value).replace("\\", "\\\\").replace('"', '\\"')
    value = value.replace("\n", "\\n").replace("\r", "")
    return f'"{value}"@{lang}' if lang else f'"{value}"'


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
    license_info = metadata.get("license")

    license_value = None
    if isinstance(license_info, dict):
        license_value = license_info.get("id")
    elif isinstance(license_info, str):
        license_value = license_info

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

    if doi:
        lines.append(f"{ttl_uri(core_dataset)} dcterms:source {ttl_uri('https://doi.org/' + doi)} .")
        lines.append(f"{ttl_uri(taxonomy_dataset)} dcterms:source {ttl_uri('https://doi.org/' + doi)} .")
        lines.append(f"{ttl_uri(properties_dataset)} dcterms:source {ttl_uri('https://doi.org/' + doi)} .")
        lines.append("")

    if conceptdoi:
        lines.append(f"{ttl_uri(core_dataset)} pav:derivedFrom {ttl_uri('https://doi.org/' + conceptdoi)} .")
        lines.append(f"{ttl_uri(taxonomy_dataset)} pav:derivedFrom {ttl_uri('https://doi.org/' + conceptdoi)} .")
        lines.append(f"{ttl_uri(properties_dataset)} pav:derivedFrom {ttl_uri('https://doi.org/' + conceptdoi)} .")
        lines.append("")

    if record_url:
        lines.append(f"{ttl_uri(core_dataset)} foaf:page {ttl_uri(record_url)} .")
        lines.append("")

    if publication_date:
        lines.append(f"{ttl_uri(core_dataset)} dcterms:issued {ttl_literal(publication_date)}^^xsd:date .")
        lines.append("")

    if license_value:
        lines.append(f"{ttl_uri(core_dataset)} dcterms:license {ttl_literal(license_value)} .")
        lines.append(f"{ttl_uri(taxonomy_dataset)} dcterms:license {ttl_literal(license_value)} .")
        lines.append(f"{ttl_uri(properties_dataset)} dcterms:license {ttl_literal(license_value)} .")
        lines.append("")

    lines.extend(file_distribution(core_dataset, Path(args.core_rdf)))
    lines.extend(file_distribution(taxonomy_dataset, Path(args.taxonomy_extra)))
    lines.extend(file_distribution(properties_dataset, Path(args.properties_extra)))

    Path(args.output).write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote VoID metadata: {args.output}")


if __name__ == "__main__":
    main()