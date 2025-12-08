WPRDFS := ${shell cat pathways.txt | sed -e 's/\(.*\)/wp\/Human\/\1.ttl/' }
GPMLRDFS := ${shell cat pathways.txt | sed -e 's/\(.*\)/wp\/gpml\/Human\/\1.ttl/' }

GPMLRDFJAR = gpml2rdf-4.0.4-SNAPSHOT.jar

all: rdf

pathways.txt:
	@find orig-renamed -name "*gpml" | cut -d'/' -f2 | sort | grep "PC" | cut -d'.' -f1 > pathways.txt

rdf: ${GPMLRDFS} ${WPRDFS}
gpml: ${GPMLS}

wp/Human/%.ttl: orig-renamed/%.gpml
	@echo "Creating GPMLRDF and WPRDF from $< ..."
	@mkdir -p wp/Human
	@mkdir -p wp/gpml/Human
	@xpath -q -e "string(/Pathway/@version)" $< | cut -d'_' -f2 | xargs java -cp ${GPMLRDFJAR} org.wikipathways.wp2rdf.CreateRDF -d rdf.plantmetwiki.bioinformatics.nl $< wp/gpml/Human/ wp/Human/

wp/gpml/Human/%.ttl: orig-renamed/%.gpml
	@echo "Creating GPMLRDF and WPRDF from $< ..."
	@mkdir -p wp/Human
	@mkdir -p wp/gpml/Human
	@xpath -q -e "string(/Pathway/@version)" $< | cut -d'_' -f2 | xargs java -cp ${GPMLRDFJAR} org.wikipathways.wp2rdf.CreateRDF -d rdf.plantmetwiki.bioinformatics.nl $< wp/gpml/Human/ wp/Human/
