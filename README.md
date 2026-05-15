# GPML to RDF for PlantMetWiki

Converts PlantCyc-derived GPML2021 pathway and reaction files into RDF using the WikiPathways GPMLRDF stack. The output feeds the [PlantMetWiki](https://plantmetwiki.bioinformatics.nl/) SPARQL endpoint.

## Three-layer RDF architecture

| Layer | Script | Output |
|---|---|---|
| **Core WikiPathways RDF** | `make -B -k -j 12 rdf` (Java) | `output/rdf/core/` |
| **Taxonomy extra RDF** | `create_gpml_taxonomy_extra_rdf.py` | `output/rdf/taxonomy-extra/` |
| **GPML property extra RDF** | `create_gpml_properties_extra_rdf.py` | `output/rdf/properties-extra/` |

The plugin layers preserve PlantCyc-specific information while keeping the core WikiPathways RDF model unchanged.

## Pipeline overview

```
1. Download GPML      →  input/gpml/original/
2. Rename files       →  input/gpml/renamed/   (stable PC*/RC* identifiers)
3. Generate index     →  pathways.txt, reactions.txt
4. Core RDF           →  output/rdf/core/
5. Taxonomy extra     →  output/rdf/taxonomy-extra/
6. Properties extra   →  output/rdf/properties-extra/
7. Bundle             →  output/bundles/all-*.ttl
8. VoID metadata      →  output/bundles/void-*.ttl
9. Validate           →  pass/fail per bundle
10. Upload to Zenodo  →  draft record
```

---

## Set up the environment

```bash
mamba env create -f environment.yml
conda activate plantmetwiki-rdf
```

All Python and Groovy commands below assume the environment is activated. The `make` step requires `conda run -n plantmetwiki-rdf make ...` explicitly because Make subshells do not inherit the activated conda environment and would otherwise use the system Java (which may be too old).

---

## 1. Prepare GPML input

### Option A — download from Zenodo (recommended for reproducible builds)

The concept DOI `10.5281/zenodo.18404067` always resolves to the latest PlantCyc GPML2021 release:

```bash
python scripts/download_gpml_input.py --clean
```

Files are saved to `input/gpml/original/pathways/` and `input/gpml/original/reactions/`.

### Option B — copy from a local GitHub checkout (useful for development branches)

```bash
gh repo clone pathway-lod/Cyc_to_wiki
mkdir -p input/gpml/original/pathways input/gpml/original/reactions
cp ../Cyc_to_wiki/<VERSION_FOLDER>/individual_pathways/*.gpml input/gpml/original/pathways/
cp ../Cyc_to_wiki/<VERSION_FOLDER>/individual_reactions/*.gpml input/gpml/original/reactions/
```

Replace `<VERSION_FOLDER>` with the relevant output directory, e.g. `plantcyc17.0.0-gpml2021-v1__git<sha>__<timestamp>`.

---

## 2. Rename GPML files

The converter expects stable `PC*` / `RC*` identifiers:

```bash
mkdir -p input/gpml/renamed/pathways input/gpml/renamed/reactions
groovy scripts/createPathwayfiles.groovy
groovy scripts/createReactionfiles.groovy
```

Output: `input/gpml/renamed/pathways/PC1.gpml … PC1162.gpml` and `input/gpml/renamed/reactions/RC1.gpml … RC1316.gpml`.

---

## 3. Generate index files

Make reads `pathways.txt` and `reactions.txt` at parse time to determine build targets — generate them before running `make rdf`:

```bash
make pathways.txt reactions.txt
```

---

## 4. Generate core WikiPathways RDF

```bash
conda run -n plantmetwiki-rdf make -B -k -j 12 rdf
```

Flags:
- `-B` — force rebuild (Make reads the index files at parse time)
- `-k` — keep going past individual file errors
- `-j 12` — run 12 jobs in parallel (adjust to available CPU cores)
- `conda run -n plantmetwiki-rdf` — ensures Java 11+ from the conda environment

For each GPML file, two Turtle files are created:
- `output/rdf/core/pathways/Human/` — **WPRDF** (WikiPathways RDF, standard model)
- `output/rdf/core/pathways/gpml/Human/` — **GPMLRDF** (direct GPML structure in RDF)

---

## 5. Generate taxonomy extra RDF

Adds `wp:organism` triples at pathway and DataNode level:
- `ncbi:33090` (Viridiplantae) on every pathway and reaction
- Species-specific NCBI taxon IDs on GeneProduct, Protein, and Metabolite nodes where GPML contains `<AnnotationRef>` taxonomy annotations

```bash
python scripts/create_gpml_taxonomy_extra_rdf.py
```

Output: `output/rdf/taxonomy-extra/` and `output/bundles/all_gpml_taxonomy_extra-<VERSION>.ttl`.

Quick checks:
```bash
grep -R "ncbi:33090" output/rdf/taxonomy-extra | head   # Viridiplantae
grep -R "ncbi:3702"  output/rdf/taxonomy-extra | head   # Arabidopsis thaliana
```

Suggested Virtuoso graph: `http://rdf-plantmetwiki.bioinformatics.nl/graph/gpml-taxonomy-extra`

---

## 6. Generate GPML property extra RDF

Preserves all `<Property key="" value="">` elements from Pathway, DataNode, and Interaction elements as `pmw:gpmlProperty` blank nodes:

```bash
python scripts/create_gpml_properties_extra_rdf.py
```

Output: `output/rdf/properties-extra/` and `output/bundles/all_gpml_properties_extra-<VERSION>.ttl`.

To inspect which property keys exist and how often:

```bash
python scripts/audit_gpml_properties.py
# output/audit/gpml_property_audit_summary.csv
# output/audit/gpml_property_audit_by_scope.csv
```

Suggested Virtuoso graph: `http://rdf-plantmetwiki.bioinformatics.nl/graph/gpml-properties-extra`

---

## 7. Bundle core RDF

Set a version label and assemble the core bundle. `bundle_rdf.py` writes each `@prefix` declaration exactly once at the top so prefixes are never duplicated across the thousands of individual TTL files:

```bash
VERSION="plantcyc17.0.0-gpml2021-v1"

python scripts/bundle_rdf.py \
  --input-dir output/rdf/core/pathways \
  --input-dir output/rdf/core/reactions \
  --output    output/bundles/all-${VERSION}.ttl
```

Apply hotfixes to normalise identifiers:

```bash
perl -pi -e 's|identifiers\.org/TAIR_gene_name|identifiers.org/tair.name|g' output/bundles/all-${VERSION}.ttl
perl -pi -e 's|SLM_SLM%3A|SLM_|g' output/bundles/all-${VERSION}.ttl
```

Optional syntax validation (requires `rapper`):

```bash
rapper -i turtle -t -q output/bundles/all-${VERSION}.ttl > /dev/null
```

---

## 8. Create VoID metadata

```bash
VERSION=$(python -c 'import json; print(json.load(open("build/zenodo_gpml_metadata.json"))["version"])')

python scripts/create_void_from_metadata.py \
  --core-rdf         output/bundles/all-${VERSION}.ttl \
  --taxonomy-extra   output/bundles/all_gpml_taxonomy_extra-${VERSION}.ttl \
  --properties-extra output/bundles/all_gpml_properties_extra-${VERSION}.ttl \
  --output           output/bundles/void-${VERSION}.ttl
```

---

## 9. Validate RDF bundles

Run before uploading to Zenodo. Checks individual TTL files, bundle sizes, expected predicates, and the VoID file:

```bash
python scripts/validate_rdf.py
```

Use `--skip-individual` to skip per-file parsing (faster, used in CI):

```bash
python scripts/validate_rdf.py --skip-individual
```

---

## 10. Upload to Zenodo

### Option A — local upload

```bash
cp .env.template .env
# edit .env: set ZENODO_ACCESS_TOKEN=your-token-here

set -a && source .env && set +a
python scripts/upload_to_zenodo.py --source-record 18174552
```

Add `--sandbox` to test against the Zenodo sandbox first. The script creates a **draft** — review and publish it in the Zenodo UI.

> Set the license manually in the Zenodo UI: *OPEN DATABASE LICENSE FOR THE PLANT METABOLIC NETWORK DATABASES*

### Option B — GitHub Actions (recommended)

A `workflow_dispatch` workflow at `.github/workflows/upload-zenodo.yml` runs the full pipeline (download → rename → RDF → bundle → validate → upload):

1. Add `ZENODO_ACCESS_TOKEN` as a repository secret
2. Go to **Actions** → **Upload to Zenodo** → **Run workflow**
3. Enter the source Zenodo record ID

---

## Final output files

```
output/bundles/all-<VERSION>.ttl
output/bundles/all_gpml_taxonomy_extra-<VERSION>.ttl
output/bundles/all_gpml_properties_extra-<VERSION>.ttl
output/bundles/void-<VERSION>.ttl
```

Recommended Virtuoso graphs:
```
http://rdf-plantmetwiki.bioinformatics.nl/graph/pathways
http://rdf-plantmetwiki.bioinformatics.nl/graph/gpml-taxonomy-extra
http://rdf-plantmetwiki.bioinformatics.nl/graph/gpml-properties-extra
```
