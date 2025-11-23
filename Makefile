WPRDFS := ${shell cat pathways.txt | sed -e 's/\(.*\)/wp\/Human\/\1.ttl/' }
GPMLRDFS := ${shell cat pathways.txt | sed -e 's/\(.*\)/wp\/gpml\/Human\/\1.ttl/' }

GPMLRDFJAR = gpml2rdf-4.0.4-SNAPSHOT.jar

all: rdf

pathways.txt:
	@find orig-renamed -name "*gpml" | cut -d'/' -f2 | sort | grep "PC" | cut -d'.' -f1 > pathways.txt

rdf: ${GPMLRDFS}
gpml: ${GPMLS}

wp/Human/%.ttl: orig-renamed/%.gpml src/java/main/org/wikipathways/curator/CreateRDF.class
	@echo "Creating $@ WPRDF from $< ..."
	@mkdir -p wp/Human
	@xpath -q -e "string(/Pathway/@Version)" $< | cut -d'_' -f2 | xargs java -cp src/java/main/.:${GPMLRDFJAR} org.wikipathways.curator.CreateRDF $< $@

wp/gpml/Human/%.ttl: orig-renamed/%.gpml src/java/main/org/wikipathways/curator/CreateGPMLRDF.class
	@mkdir -p wp/gpml/Human
	@xpath -q -e "string(/Pathway/@Version)" $< | cut -d'_' -f2 | xargs java -cp src/java/main/.:${GPMLRDFJAR} org.wikipathways.curator.CreateGPMLRDF $< $@

src/java/main/org/wikipathways/curator/CreateRDF.class: src/java/main/org/wikipathways/curator/CreateRDF.java
	@echo "Compiling $@ ..."
	@javac -cp ${GPMLRDFJAR} src/java/main/org/wikipathways/curator/CreateRDF.java

src/java/main/org/wikipathways/curator/CreateGPMLRDF.class: src/java/main/org/wikipathways/curator/CreateGPMLRDF.java
	@echo "Compiling $@ ..."
	@javac -cp ${GPMLRDFJAR} src/java/main/org/wikipathways/curator/CreateGPMLRDF.java
