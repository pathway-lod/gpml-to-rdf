#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Write /tmp/OPSBRIDGEDB/config.properties so gpml2rdf's CreateRDF finds the
# BridgeDb mapping databases.
#
# The converter (org.wikipathways.wp2rdf.CreateRDF, bundled in
# tools/gpml2rdf-4.0.4-SNAPSHOT.jar) loads this exact path:
#     /tmp/OPSBRIDGEDB/config.properties
# and reads the 'bridgefiles' key (a DIRECTORY of *.bridge files). If the
# folder is missing it prints "WARN: BridgeDb config file folder does not
# exist:" and skips metabolite mapping silently -- which is why earlier
# conversions produced NO metabolite cross-references.
#
# NOTE: /tmp is cleared on reboot, so re-run this script once per session/reboot
# before converting. The 2.79 GB .bridge file itself lives in BRIDGEDB_DIR
# (persistent), not in /tmp.
#
# Usage:
#   ./setup_opsbridgedb.sh
#   BRIDGEDB_DIR=/data/bridgedb ./setup_opsbridgedb.sh
# ---------------------------------------------------------------------------
set -euo pipefail

BRIDGEDB_DIR="${BRIDGEDB_DIR:-$HOME/bridgedb-data}"
OPS_DIR="/tmp/OPSBRIDGEDB"

if [ ! -d "$BRIDGEDB_DIR" ] || ! ls "$BRIDGEDB_DIR"/*.bridge >/dev/null 2>&1; then
  echo "ERROR: no *.bridge files found in $BRIDGEDB_DIR" >&2
  echo "       Run ./download_bridgedb_metabolites.sh first." >&2
  exit 1
fi

mkdir -p "$OPS_DIR"
printf 'bridgefiles=%s\n' "$BRIDGEDB_DIR" > "$OPS_DIR/config.properties"

echo "Wrote $OPS_DIR/config.properties:"
echo "-----------------------------------------"
cat "$OPS_DIR/config.properties"
echo "-----------------------------------------"
echo ".bridge files that will be loaded:"
ls -lh "$BRIDGEDB_DIR"/*.bridge
echo
echo "BridgeDb metabolite mapping is now ENABLED for the next gpml2rdf run."
