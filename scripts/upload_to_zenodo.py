#!/usr/bin/env python3

from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import requests


ZENODO_API = "https://zenodo.org/api"
SANDBOX_API = "https://sandbox.zenodo.org/api"
METADATA_FILE = Path("build/zenodo_gpml_metadata.json")


def require_token() -> str:
    token = os.environ.get("ZENODO_ACCESS_TOKEN")
    if not token:
        raise SystemExit(
            "Missing ZENODO_ACCESS_TOKEN.\n"
            "Set it with:\n"
            "  export ZENODO_ACCESS_TOKEN='your-token-here'"
        )
    return token


def api_base(use_sandbox: bool) -> str:
    return SANDBOX_API if use_sandbox else ZENODO_API


def request_json(
    method: str,
    url: str,
    token: str,
    **kwargs: Any,
) -> dict:
    params = kwargs.pop("params", {})
    params["access_token"] = token

    response = requests.request(method, url, params=params, **kwargs)

    if not response.ok:
        print(f"❌ Zenodo API error: {method} {url}", file=sys.stderr)
        print(f"Status: {response.status_code}", file=sys.stderr)
        print(response.text, file=sys.stderr)
        response.raise_for_status()

    if response.text:
        return response.json()
    return {}


def load_build_metadata(path: Path = METADATA_FILE) -> dict:
    if not path.exists():
        raise SystemExit(
            f"Missing metadata file: {path}\n"
            "Run first:\n"
            "  python scripts/download_gpml_input.py --clean"
        )

    return json.loads(path.read_text(encoding="utf-8"))


def gzip_file(input_path: Path, output_path: Path, overwrite: bool = False) -> Path:
    if output_path.exists() and not overwrite:
        print(f"Using existing gzip: {output_path}")
        return output_path

    print(f"Compressing: {input_path} -> {output_path}")
    with input_path.open("rb") as src, gzip.open(output_path, "wb") as dst:
        shutil.copyfileobj(src, dst)

    return output_path


def prepare_files(version: str, overwrite: bool = False) -> list[Path]:
    required = [
        Path(f"all-{version}.ttl"),
        Path(f"all_gpml_taxonomy_extra-{version}.ttl"),
        Path(f"all_gpml_properties_extra-{version}.ttl"),
        Path(f"void-{version}.ttl"),
    ]

    missing = [p for p in required if not p.exists()]
    if missing:
        raise SystemExit(
            "Missing expected release files:\n"
            + "\n".join(f"  - {p}" for p in missing)
        )

    files = [
        gzip_file(Path(f"all-{version}.ttl"), Path(f"all-{version}.ttl.gz"), overwrite),
        gzip_file(
            Path(f"all_gpml_taxonomy_extra-{version}.ttl"),
            Path(f"all_gpml_taxonomy_extra-{version}.ttl.gz"),
            overwrite,
        ),
        gzip_file(
            Path(f"all_gpml_properties_extra-{version}.ttl"),
            Path(f"all_gpml_properties_extra-{version}.ttl.gz"),
            overwrite,
        ),
        Path(f"void-{version}.ttl"),
        METADATA_FILE,
    ]

    return files


def get_record_metadata(api: str, source_record: str, token: str) -> dict:
    return request_json(
        "GET",
        f"{api}/records/{source_record}",
        token,
    )


def create_new_version(api: str, source_record: str, token: str) -> dict:
    print(f"Creating new Zenodo version from record {source_record}...")
    result = request_json(
        "POST",
        f"{api}/deposit/depositions/{source_record}/actions/newversion",
        token,
    )

    latest_draft_url = result["links"]["latest_draft"]
    draft = request_json("GET", latest_draft_url, token)

    print(f"Created draft deposition: {draft['id']}")
    return draft


def delete_existing_draft_files(api: str, draft: dict, token: str) -> None:
    files = request_json(
        "GET",
        f"{api}/deposit/depositions/{draft['id']}/files",
        token,
    )

    for f in files:
        file_id = f["id"]
        filename = f.get("filename", file_id)
        print(f"Deleting existing draft file: {filename}")
        request_json(
            "DELETE",
            f"{api}/deposit/depositions/{draft['id']}/files/{file_id}",
            token,
        )


def upload_file(api: str, draft: dict, file_path: Path, token: str) -> None:
    bucket_url = draft["links"]["bucket"]
    upload_url = f"{bucket_url}/{file_path.name}"

    print(f"Uploading: {file_path.name}")
    with file_path.open("rb") as fp:
        response = requests.put(
            upload_url,
            data=fp,
            params={"access_token": token},
        )

    if not response.ok:
        print(f"❌ Upload failed: {file_path}", file=sys.stderr)
        print(f"Status: {response.status_code}", file=sys.stderr)
        print(response.text, file=sys.stderr)
        response.raise_for_status()


def creators_from_existing_record(record: dict) -> list[dict]:
    creators = record.get("metadata", {}).get("creators", [])
    if creators:
        return creators

    return [
        {
            "name": "Willighagen, Egon",
            "affiliation": "Maastricht University",
        }
    ]


def update_draft_metadata(
    api: str,
    draft: dict,
    source_record_metadata: dict,
    build_metadata: dict,
    token: str,
) -> dict:
    version = build_metadata["version"]
    zenodo_input_doi = build_metadata.get("doi")
    zenodo_input_record = build_metadata.get("zenodo_record_url")
    gpml_file_key = build_metadata.get("gpml_file", {}).get("key")

    existing_metadata = source_record_metadata.get("metadata", {})

    description = (
        "<p>This is the Resource Description Framework created from the GPML "
        "versions of the PlantCyc pathways and reactions.</p>"
        f"<p>This release was generated from PlantCyc GPML input version "
        f"<strong>{version}</strong>.</p>"
    )

    if zenodo_input_doi:
        description += (
            f"<p>Input GPML Zenodo DOI: "
            f"<a href=\"https://doi.org/{zenodo_input_doi}\">{zenodo_input_doi}</a>.</p>"
        )

    if gpml_file_key:
        description += f"<p>Input GPML archive: <code>{gpml_file_key}</code>.</p>"

    if zenodo_input_record:
        description += (
            f"<p>Input GPML Zenodo record: "
            f"<a href=\"{zenodo_input_record}\">{zenodo_input_record}</a>.</p>"
        )

    description += (
        "<p>This upload contains the core WikiPathways RDF, a taxonomy extra RDF "
        "layer, a GPML property extra RDF layer, VoID metadata, and build metadata.</p>"
    )

    metadata = {
        "metadata": {
            "title": "PlantMetWiki RDF",
            "upload_type": "dataset",
            "description": description,
            "creators": creators_from_existing_record(source_record_metadata),
            "version": version,
            "access_right": "open",
            "license": existing_metadata.get("license") or "other-open",
            "keywords": existing_metadata.get("keywords", [])
            or ["PlantMetWiki", "PlantCyc", "WikiPathways", "GPML", "RDF"],
            "related_identifiers": [
                {
                    "identifier": "https://github.com/pathway-lod/gpml-to-rdf",
                    "relation": "isSupplementTo",
                    "scheme": "url",
                }
            ],
        }
    }

    if zenodo_input_doi:
        metadata["metadata"]["related_identifiers"].append(
            {
                "identifier": zenodo_input_doi,
                "relation": "isDerivedFrom",
                "scheme": "doi",
            }
        )

    print("Updating draft metadata...")
    return request_json(
        "PUT",
        f"{api}/deposit/depositions/{draft['id']}",
        token,
        json=metadata,
        headers={"Content-Type": "application/json"},
    )


def publish_draft(api: str, draft: dict, token: str) -> dict:
    print("Publishing draft...")
    return request_json(
        "POST",
        f"{api}/deposit/depositions/{draft['id']}/actions/publish",
        token,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a new Zenodo version for PlantMetWiki RDF files."
    )
    parser.add_argument(
        "--source-record",
        required=True,
        help="Latest published Zenodo record ID to version from, e.g. 18174552",
    )
    parser.add_argument(
        "--sandbox",
        action="store_true",
        help="Use sandbox.zenodo.org instead of production Zenodo.",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish the draft after uploading. Default is to leave as draft.",
    )
    parser.add_argument(
        "--overwrite-gzip",
        action="store_true",
        help="Regenerate .ttl.gz files even if they already exist.",
    )
    parser.add_argument(
        "--keep-existing-draft-files",
        action="store_true",
        help="Do not delete files imported into the new version draft.",
    )

    args = parser.parse_args()

    token = require_token()
    api = api_base(args.sandbox)

    build_metadata = load_build_metadata()
    version = build_metadata["version"]

    files = prepare_files(version, overwrite=args.overwrite_gzip)

    print("Files to upload:")
    for file_path in files:
        print(f"  - {file_path}")

    source_record_metadata = get_record_metadata(api, args.source_record, token)
    draft = create_new_version(api, args.source_record, token)

    if not args.keep_existing_draft_files:
        delete_existing_draft_files(api, draft, token)

    for file_path in files:
        upload_file(api, draft, file_path, token)

    draft = update_draft_metadata(
        api=api,
        draft=draft,
        source_record_metadata=source_record_metadata,
        build_metadata=build_metadata,
        token=token,
    )

    print()
    print("✅ Zenodo draft prepared")
    print(f"Draft ID: {draft['id']}")
    print(f"Draft URL: {draft.get('links', {}).get('html', 'Open in Zenodo UI')}")

    if args.publish:
        published = publish_draft(api, draft, token)
        print()
        print("✅ Published")
        print(f"Record ID: {published.get('id')}")
        print(f"DOI: {published.get('doi') or published.get('metadata', {}).get('doi')}")
        print(f"URL: {published.get('links', {}).get('html')}")
    else:
        print()
        print("Not published yet. Review the draft in Zenodo first.")
        print("To publish automatically, rerun with --publish.")

    return 0


if __name__ == "__main__":
    sys.exit(main())