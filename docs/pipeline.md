# GPML-to-RDF Pipeline Overview

Workflow diagram for the PlantMetWiki RDF generation pipeline.
Rendered automatically by GitHub. For an editable version, import into
[draw.io](https://app.diagrams.net) via **File → Import → Mermaid**,
or paste into [mermaid.live](https://mermaid.live) for a quick PNG/SVG export.

```mermaid
flowchart TD
    A["📁 GPML files\n1,162 pathways + 1,316 reactions\n(from Cyc_to_wiki / Zenodo)"]

    A --> B["🔢 Stable ID assignment\nGroovy scripts\nPC1–PC1162 · RC1–RC1316"]

    B --> C["⚙️ Core RDF conversion\nGNU Make — parallelised\ngpml2rdf-4.0.4 Java tool"]

    C --> D1["WPRDF\nwp:Pathway model\noutput/rdf/core/…/Human/"]
    C --> D2["GPMLRDF\nraw GPML structure\noutput/rdf/core/…/gpml/Human/"]

    B --> E1["🐍 Taxonomy extra RDF\ncreate_gpml_taxonomy_extra_rdf.py\nwp:organism · foaf:page"]
    B --> E2["🐍 Properties extra RDF\ncreate_gpml_properties_extra_rdf.py\npmw:plantcycId · dcterms:source · foaf:page"]

    D1 & D2 & E1 & E2 --> F["📦 Aggregate into versioned bundles\n4 TTL bundle files"]

    F --> G["✅ RDF validation\nvalidate_rdf.py — RDFlib\n3 levels: file · bundle · VoID"]

    F --> H["📋 VoID metadata\ncreate_void_from_metadata.py\ntriple counts · provenance · license"]

    G & H --> I["☁️ Upload to Zenodo\nupload_to_zenodo.py\nPlantMetWiki community"]

    I --> J["🔷 4 Named graphs\nCore pathways · Core reactions\nTaxonomy extra · Properties extra"]
```
