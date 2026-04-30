#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


ZENODO_API = "https://zenodo.org/api/records/"


def fetch_latest_record(concept_doi: str) -> dict:
    """Resolve concept DOI to latest Zenodo record."""
    url = ZENODO_API + concept_doi.split(".")[-1]
    print(f"Resolving Zenodo concept DOI: {url}")

    with urllib.request.urlopen(url) as response:
        return json.load(response)


def find_gpml_file(record: dict) -> str:
    """Find the GPML zip file in Zenodo record."""
    for f in record["files"]:
        name = f["key"]
        if "gpml" in name.lower() and name.endswith(".zip"):
            print(f"Found GPML file: {name}")
            return f["links"]["self"]

    raise RuntimeError("No GPML zip file found in Zenodo record")


def download_file(url: str, output: Path) -> None:
    print(f"Downloading: {url}")
    urllib.request.urlretrieve(url, output)
    print(f"Saved: {output}")


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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download latest GPML dataset from Zenodo concept DOI."
    )

    parser.add_argument(
        "--concept-doi",
        default="10.5281/zenodo.18404067",
        help="Zenodo concept DOI (default = latest PlantCyc GPML)",
    )
    parser.add_argument("--pathways-dir", default="orig-pw")
    parser.add_argument("--reactions-dir", default="orig-react")
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

    # --------------------------------------------------
    # Resolve latest Zenodo record
    # --------------------------------------------------
    record = fetch_latest_record(args.concept_doi)

    version = record["metadata"]["version"]
    print(f"Using version: {version}")

    # --------------------------------------------------
    # Find GPML ZIP file
    # --------------------------------------------------
    gpml_url = find_gpml_file(record)

    # --------------------------------------------------
    # Download + extract
    # --------------------------------------------------
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        zip_path = tmp_dir / "gpml.zip"

        download_file(gpml_url, zip_path)

        extract_dir = tmp_dir / "extracted"
        extract_dir.mkdir()

        print("Extracting...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        # --------------------------------------------------
        # Copy files
        # --------------------------------------------------
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