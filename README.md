# GPML to RDF for plant Wikipathways 

This README explains the step you need to do to generate the RDF for the GPML pathways.

## Get the data

Download the plant pathways:

```shell
gh repo clone pathway-lod/Cyc_to_wiki
```

and save them in the `orig` folder:

```shell
cd gpml-to-rdf
mkdir orig; cd orig
cp ../../Cyc_to_wiki/biocyc_pathways_20251121085146/individual_pathways/*gpml
```

Renamed the files and put the results in `orig-renamed/`:

```shell
cd ..
mkdir orig-renamed
groovy createGPMLfiles.groovy
```

Then create the RDF with:

```shell
nice -20 make -j 12 rdf
```
