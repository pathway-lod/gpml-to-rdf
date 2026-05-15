#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
import urllib.request
import urllib.error
import zipfile
from pathlib import Path


ZENODO_API = "https://zenodo.org/api/records/"
DEFAULT_METADATA_FILE = Path("build/zenodo_gpml_metadata.json")


def fetch_with_retry(url: str, retries: int = 5, backoff: float = 10.0) -> dict:
    """Fetch a URL with exponential backoff on 503 errors."""
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            if e.code == 503 and attempt < retries:
                wait = backoff * (2 ** (attempt - 1))
                print(f"  Zenodo returned 503 (attempt {attempt}/{retries}), retrying in {wait:.0f}s...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Unreachable")


def fetch_latest_record(concept_doi: str) -> dict:
    """Resolve concept DOI to latest Zenodo record."""
    url = ZENODO_API + concept_doi.split(".")[-1]
    print(f"Resolving Zenodo concept DOI: {url}")
    return fetch_with_retry(url)


def find_gpml_file(record: dict) -> dict:
    """Find the GPML zip file metadata in Zenodo record."""
    for f in record["files"]:
        name = f["key"]
        if "gpml" in name.lower() and name.endswith(".zip"):
            print(f"Found GPML file: {name}")
            return f

    raise RuntimeError("No GPML zip file found in Zenodo record")


def download_file(url: str, output: Path, retries: int = 5, backoff: float = 10.0) -> None:
    print(f"Downloading: {url}")
    for attempt in range(1, retries + 1):
        try:
            urllib.request.urlretrieve(url, output)
            print(f"Saved: {output}")
            return
        except urllib.error.HTTPError as e:
            if e.code == 503 and attempt < retries:
                wait = backoff * (2 ** (attempt - 1))
                print(f"  503 on download (attempt {attempt}/{retries}), retrying in {wait:.0f}s...")
                time.sleep(wait)
            else:
                raise


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_gpml_files(source_root: Path, pattern: str, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)

    files = [
        p for p in source_root.rglob("*.gpml")
        if pattern in str(p)
    ]

    for src in files:
        shutil.copy2(src, output_dir / src.name)

    return len(files)


def write_metadata(
    record: dict,
    gpml_file: dict,
    concept_doi: str,
    pathway_count: int,
    reaction_count: int,
    metadata_file: Path = DEFAULT_METADATA_FILE,
) -> None:
    metadata = record.get("metadata", {})

    output = {
        "record_id": record.get("id"),
        "conceptdoi": metadata.get("conceptdoi", concept_doi),
        "doi": metadata.get("doi"),
        "version": metadata.get("version"),
        "title": metadata.get("title"),
        "publication_date": metadata.get("publication_date"),
        "license": metadata.get("license"),
        "creators": metadata.get("creators", []),
        "zenodo_record_url": record.get("links", {}).get("html"),
        "zenodo_api_url": record.get("links", {}).get("self"),
        "gpml_file": {
            "key": gpml_file.get("key"),
            "size": gpml_file.get("size"),
            "checksum": gpml_file.get("checksum"),
            "download_url": gpml_file.get("links", {}).get("self"),
        },
        "download_outputs": {
            "pathway_count": pathway_count,
            "reaction_count": reaction_count,
            "pathways_dir": "input/gpml/original/pathways",
            "reactions_dir": "input/gpml/original/reactions",
        },
    }

    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    metadata_file.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Metadata written to: {metadata_file}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download latest GPML dataset from Zenodo concept DOI."
    )

    parser.add_argument(
        "--concept-doi",
        default="10.5281/zenodo.18404067",
        help="Zenodo concept DOI (default = latest PlantCyc GPML)",
    )
    parser.add_argument("--pathways-dir", default="input/gpml/original/pathways")
    parser.add_argument("--reactions-dir", default="input/gpml/original/reactions")
    parser.add_argument("--clean", action="store_true")

    args = parser.parse_args()

    pathways_dir = Path(args.pathways_dir)
    reactions_dir = Path(args.reactions_dir)

    if args.clean:
        clean_dir(pathways_dir)
        clean_dir(reactions_dir)
    else:
        pathways_dir.mkdir(parents=True, exist_ok=True)
        reactions_dir.mkdir(parents=True, exist_ok=True)

    record = fetch_latest_record(args.concept_doi)

    version = record["metadata"]["version"]
    print(f"Using version: {version}")

    gpml_file = find_gpml_file(record)
    gpml_url = gpml_file["links"]["self"]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        zip_path = tmp_dir / "gpml.zip"

        download_file(gpml_url, zip_path)

        extract_dir = tmp_dir / "extracted"
        extract_dir.mkdir()

        print("Extracting...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        pw_count = copy_gpml_files(
            extract_dir,
            "individual_pathways",
            pathways_dir,
        )

        rxn_count = copy_gpml_files(
            extract_dir,
            "individual_reactions",
            reactions_dir,
        )

    write_metadata(
        record=record,
        gpml_file=gpml_file,
        concept_doi=args.concept_doi,
        pathway_count=pw_count,
        reaction_count=rxn_count,
    )

    print()
    print("✅ Done")
    print(f"Version: {version}")
    print(f"Pathways:  {pw_count}")
    print(f"Reactions: {rxn_count}")

    if pw_count == 0 or rxn_count == 0:
        print("⚠️ Warning: file structure may have changed!")

    return 0


if __name__ == "__main__":
    sys.exit(main())