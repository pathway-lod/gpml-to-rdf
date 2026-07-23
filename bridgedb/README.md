# BridgeDb metabolite ID mapping for gpml2rdf

Adds cross-references (ChEBI, HMDB, Wikidata, PubChem, KEGG Compound, LipidMaps,
ChemSpider, InChIKey) to `wp:Metabolite` nodes during GPML → RDF conversion, via
the BridgeDb metabolite ID-mapping database.

## Why this is needed (root cause of the missing mappings)

The converter `org.wikipathways.wp2rdf.CreateRDF` (in
`tools/gpml2rdf-4.0.4-SNAPSHOT.jar`) always tries to enable BridgeDb mapping. It
loads its configuration from a **fixed path**:

```
/tmp/OPSBRIDGEDB/config.properties
```

and reads a single key, `bridgefiles`, which must point to a **directory**
containing one or more `*.bridge` mapping databases. It then loads *every*
`.bridge` file in that folder (`org.pathvisio.io.rdf.wp.BridgeDbIDMapper`).

If that folder / config is missing, the converter prints:

```
WARN: BridgeDb config file folder does not exist: ...
```

and **silently skips metabolite mapping**. In previous PlantMetWiki conversions
the config was absent, so no `.bridge` database was loaded and **no metabolite
cross-references were emitted** — the symptom we are fixing here.

## What gets added to the RDF

For each metabolite the mapper emits BridgeDb-derived cross-references as
dedicated `wp:bdb*` predicates (WikiPathways vocabulary), **in addition to** the
node's existing source identifier — it does *not* overwrite the source Xref:

| Predicate | Target database |
|---|---|
| `wp:bdbChEBI` | ChEBI |
| `wp:bdbHmdb` | HMDB |
| `wp:bdbWikidata` | Wikidata |
| `wp:bdbPubChem` | PubChem Compound |
| `wp:bdbKeggCompound` | KEGG Compound |
| `wp:bdbLipidMaps` | LipidMaps |
| `wp:bdbChemspider` | ChemSpider |
| `wp:bdbInChIKey` | InChIKey |

(Gene/protein predicates such as `wp:bdbEnsembl`, `wp:bdbEntrezGene`,
`wp:bdbUniprot` are emitted too if gene `.bridge` files are present.)

## Mapping database used

- **File:** `metabolites_20260102.bridge` (~2.79 GB)
- **Source:** figshare — *Metabolite BridgeDb ID Mapping Database (20260102)*,
  DOI [10.6084/m9.figshare.30993322](https://doi.org/10.6084/m9.figshare.30993322)
- **Built from:** HMDB (Jan 2026), ChEBI (release 247), Wikidata (2 Jan 2026)

Record the DOI/version in the manuscript and in the release metadata (VoID),
because the mapping outcome depends on the exact BridgeDb build.

## Prerequisites — Java 11+

`gpml2rdf-4.0.4-SNAPSHOT.jar` is compiled for **Java 11** (class file version 55).
Running it under Java 8 fails with:

```
UnsupportedClassVersionError: ... class file version 55.0 ...
this version of the Java Runtime only recognizes class file versions up to 52.0
```

macOS often ships only the old Java 8 applet JRE. Install Java 11 into the build
env (matches the jar; safest choice):

```bash
conda install -n plantmetwiki-rdf -c conda-forge 'openjdk=11'
conda activate plantmetwiki-rdf
java -version        # must print openjdk 11.x, not 1.8
```

`conda activate plantmetwiki-rdf` puts this `java` first on PATH, so both the
single-file test and `make rdf` use it.

## Setup (three steps)

```bash
cd bridgedb

# 1. Download the .bridge database (~2.79 GB) into $HOME/bridgedb-data
#    (override with BRIDGEDB_DIR=/some/path)
bash download_bridgedb_metabolites.sh

# 2. Write /tmp/OPSBRIDGEDB/config.properties pointing at that folder.
#    RE-RUN THIS after every reboot — /tmp is ephemeral.
bash setup_opsbridgedb.sh

# 3. Sanity check
cat /tmp/OPSBRIDGEDB/config.properties      # bridgefiles=/Users/you/bridgedb-data
ls -lh "$HOME/bridgedb-data"/*.bridge
```

## Run the conversion  ⚠️ EXPENSIVE — do this deliberately

No new flags are needed: with `/tmp/OPSBRIDGEDB/config.properties` in place, the
normal build now enables BridgeDb mapping. From the repo root:

```bash
conda activate plantmetwiki-rdf

# Full parallel rebuild (forces re-conversion of all PC*/RC* GPML files).
# This is the expensive step; expect a long run + heavy I/O.
make -B -k -j 12 rdf        # logs to logs/rdf-<timestamp>.log
```

Confirm mapping actually fired by grepping the run log for the mapper's messages
and the new predicates in the output TTL:

```bash
grep -c "InChIKey found:" logs/rdf-*.log            # >0 means mapping ran
grep -rl "wp:bdbChEBI\|bdbInChIKey" output/rdf/core/pathways/Human | head
```

If you only want to test on a single pathway first (recommended before the full
run), convert one GPML file directly. NOTE: `CreateRDF` takes a **4th positional
argument — the GPML version** (the Makefile supplies it via `xpath ... | xargs`);
omitting it throws `ArrayIndexOutOfBoundsException: Index 3 out of bounds`.

```bash
conda activate plantmetwiki-rdf                      # ensures Java 11 is on PATH
GPML=input/gpml/renamed/pathways/PC241.gpml
VER=$(xpath -q -e "string(/Pathway/@version)" "$GPML" | cut -d'_' -f2)   # e.g. 20260605-171052
mkdir -p /tmp/out/gpml /tmp/out/wp
java -cp tools/gpml2rdf-4.0.4-SNAPSHOT.jar org.wikipathways.wp2rdf.CreateRDF \
  -d rdf-plantmetwiki.bioinformatics.nl "$GPML" /tmp/out/gpml/ /tmp/out/wp/ "$VER"
grep -oE "bdb(ChEBI|Hmdb|Wikidata|PubChem|InChIKey|KeggCompound|LipidMaps|Chemspider)" \
  /tmp/out/wp/PC241.ttl | sort | uniq -c        # expect nonzero counts once BridgeDb is set up
```

Verified example: with BridgeDb enabled, `PC241.ttl` (avenacin) gains ~106
`wp:bdb*` triples (bdbWikidata/bdbInChIKey/bdbPubChem/bdbChEBI/…); without the
`.bridge` file it has none. The full `make rdf` run supplies the version argument
automatically, so no manual handling is needed there.

After a successful full run, re-aggregate/validate/load exactly as in the main
[../README.md](../README.md) (the BridgeDb graph is part of the core pathways
RDF; no separate named graph is required).

## Risks & things to verify (see analysis notebook)

`notebooks/08_bridgedb_metabolite_mapping.ipynb` quantifies the before/after
effect and checks the risks below.

1. **Augmentation, not overwrite.** BridgeDb writes new `wp:bdb*` triples; the
   GPML source identifier is preserved. Verify the source `dc:identifier` /
   InChIKey on each node is unchanged after conversion.
2. **Stereochemistry conflation.** A BridgeDb `wp:bdbInChIKey` (or `wp:bdbChEBI`)
   can differ from the source InChIKey when the mapping DB stores a different
   stereochemical form of the same skeleton (the momilactone A case in the
   federation section). This is a *cross-reference*, not an identity claim, but
   downstream queries that treat all InChIKeys on a node as equivalent could
   conflate stereoisomers. The notebook flags nodes where source and BridgeDb
   InChIKeys share a 14-char skeleton but differ in the stereo layer.
3. **Determinism / idempotency.** Mapping is deterministic for a fixed `.bridge`
   build; re-running the conversion reproduces the same triples. Pin the figshare
   DOI/version so results are reproducible.
4. **Coverage is source-Xref dependent.** Only metabolites whose source Xref is
   present in the `.bridge` DB gain mappings; specialist plant metabolites absent
   from HMDB/ChEBI/Wikidata will still map to nothing (consistent with the
   federation-gap analysis).
