SHELL := /bin/bash

PCWPRDFS := ${shell cat pathways.txt | sed -e 's/\(.*\)/output\/rdf\/core\/pathways\/Human\/\1.ttl/' }
PCGPMLRDFS := ${shell cat pathways.txt | sed -e 's/\(.*\)/output\/rdf\/core\/pathways\/gpml\/Human\/\1.ttl/' }
RCWPRDFS := ${shell cat reactions.txt | sed -e 's/\(.*\)/output\/rdf\/core\/reactions\/Human\/\1.ttl/' }
RCGPMLRDFS := ${shell cat reactions.txt | sed -e 's/\(.*\)/output\/rdf\/core\/reactions\/gpml\/Human\/\1.ttl/' }

GPMLRDFJAR = tools/gpml2rdf-4.0.4-SNAPSHOT.jar
LOG_DIR = logs

.PHONY: all rdf

all: rdf

# Wraps pcrdf/reactrdf in a sub-make so the combined output (including
# parallel -j jobs) is captured to a timestamped log file as well as
# printed live, e.g. `make -B -k -j 12 rdf` -> logs/rdf-<timestamp>.log
rdf:
	@mkdir -p $(LOG_DIR)
	@logfile="$(LOG_DIR)/rdf-$$(date +%Y%m%d-%H%M%S).log"; \
	echo "Logging build output to $$logfile"; \
	$(MAKE) pcrdf reactrdf 2>&1 | tee "$$logfile"; \
	exit $${PIPESTATUS[0]}

pathways.txt:
	@find input/gpml/renamed/pathways -name "*.gpml" | xargs -I{} basename {} .gpml | sort | grep "^PC" > pathways.txt

reactions.txt:
	@find input/gpml/renamed/reactions -name "*.gpml" | xargs -I{} basename {} .gpml | sort | grep "^RC" > reactions.txt

pcrdf: ${PCGPMLRDFS} ${PCWPRDFS}
reactrdf: ${RCGPMLRDFS} ${RCWPRDFS}

output/rdf/core/pathways/Human/%.ttl: input/gpml/renamed/pathways/%.gpml
	@echo "Creating GPMLRDF and WPRDF from $< ..."
	@mkdir -p output/rdf/core/pathways/Human
	@mkdir -p output/rdf/core/pathways/gpml/Human
	@xpath -q -e "string(/Pathway/@version)" $< | cut -d'_' -f2 | xargs java -cp ${GPMLRDFJAR} org.wikipathways.wp2rdf.CreateRDF -d rdf-plantmetwiki.bioinformatics.nl $< output/rdf/core/pathways/gpml/Human/ output/rdf/core/pathways/Human/

output/rdf/core/pathways/gpml/Human/%.ttl: input/gpml/renamed/pathways/%.gpml
	@echo "Creating GPMLRDF and WPRDF from $< ..."
	@mkdir -p output/rdf/core/pathways/Human
	@mkdir -p output/rdf/core/pathways/gpml/Human
	@xpath -q -e "string(/Pathway/@version)" $< | cut -d'_' -f2 | xargs java -cp ${GPMLRDFJAR} org.wikipathways.wp2rdf.CreateRDF -d rdf-plantmetwiki.bioinformatics.nl $< output/rdf/core/pathways/gpml/Human/ output/rdf/core/pathways/Human/

output/rdf/core/reactions/Human/%.ttl: input/gpml/renamed/reactions/%.gpml
	@echo "Creating GPMLRDF and WPRDF from $< ..."
	@mkdir -p output/rdf/core/reactions/Human
	@mkdir -p output/rdf/core/reactions/gpml/Human
	@xpath -q -e "string(/Pathway/@version)" $< | cut -d'_' -f2 | xargs java -cp ${GPMLRDFJAR} org.wikipathways.wp2rdf.CreateRDF -d rdf-plantmetwiki.bioinformatics.nl $< output/rdf/core/reactions/gpml/Human/ output/rdf/core/reactions/Human/

output/rdf/core/reactions/gpml/Human/%.ttl: input/gpml/renamed/reactions/%.gpml
	@echo "Creating GPMLRDF and WPRDF from $< ..."
	@mkdir -p output/rdf/core/reactions/Human
	@mkdir -p output/rdf/core/reactions/gpml/Human
	@xpath -q -e "string(/Pathway/@version)" $< | cut -d'_' -f2 | xargs java -cp ${GPMLRDFJAR} org.wikipathways.wp2rdf.CreateRDF -d rdf-plantmetwiki.bioinformatics.nl $< output/rdf/core/reactions/gpml/Human/ output/rdf/core/reactions/Human/
