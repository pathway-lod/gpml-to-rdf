#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Download the BridgeDb *metabolite* ID-mapping database (~2.79 GB) from figshare.
#
# Source: "Metabolite BridgeDb ID Mapping Database (20260102)"
#         DOI 10.6084/m9.figshare.30993322.v1
#         Built from HMDB (Jan 2026), ChEBI (release 247), Wikidata (2 Jan 2026).
#
# The resulting *.bridge file is what gpml2rdf loads to add metabolite
# cross-references (ChEBI, HMDB, Wikidata, PubChem, KEGG, LipidMaps, ChemSpider,
# InChIKey) during GPML->RDF conversion.
#
# Usage:
#   ./download_bridgedb_metabolites.sh            # -> $HOME/bridgedb-data
#   BRIDGEDB_DIR=/data/bridgedb ./download_bridgedb_metabolites.sh
# ---------------------------------------------------------------------------
set -euo pipefail

# Persistent location for the .bridge file(s). Keep this OUT of /tmp — /tmp is
# cleared on reboot and the file is 2.79 GB.
BRIDGEDB_DIR="${BRIDGEDB_DIR:-$HOME/bridgedb-data}"

BRIDGE_URL="https://ndownloader.figshare.com/files/60760156"   # metabolites_20260102.bridge
QC_URL="https://ndownloader.figshare.com/files/60760153"       # metabolites_20260102.qc
BRIDGE_FILE="metabolites_20260102.bridge"
QC_FILE="metabolites_20260102.qc"
EXPECTED_BYTES=2993572128

mkdir -p "$BRIDGEDB_DIR"
echo "Target folder : $BRIDGEDB_DIR"
echo "Downloading   : $BRIDGE_FILE (~2.79 GB) + $QC_FILE"
echo "(-C - resumes a partial download if interrupted)"
echo

curl -L -C - --fail --retry 5 --retry-delay 5 -o "$BRIDGEDB_DIR/$QC_FILE"     "$QC_URL"
curl -L -C - --fail --retry 5 --retry-delay 5 -o "$BRIDGEDB_DIR/$BRIDGE_FILE" "$BRIDGE_URL"

# size check (macOS: stat -f%z ; Linux: stat -c%s)
got=$(stat -f%z "$BRIDGEDB_DIR/$BRIDGE_FILE" 2>/dev/null || stat -c%s "$BRIDGEDB_DIR/$BRIDGE_FILE")
echo
echo "Downloaded $BRIDGE_FILE: $got bytes (expected $EXPECTED_BYTES)"
if [ "$got" != "$EXPECTED_BYTES" ]; then
  echo "WARNING: size mismatch. Re-run this script to resume/verify the download." >&2
  exit 1
fi

echo
echo "OK. Next: run  ./setup_opsbridgedb.sh  (writes /tmp/OPSBRIDGEDB/config.properties)."
echo "Then run the conversion (see bridgedb/README.md)."
