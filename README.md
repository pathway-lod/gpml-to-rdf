# GPML to RDF for plant Wikipathways 

This README explains the step you need to do to generate the RDF for the GPML pathways.

## Get the data

Download the plant pathways and save them in the `orig` folder:

```shell
mkdir orig; cd orig
# copy the GPML files here
```

Renamed the files and put the results in `orig-renamed/`:

```shell
cd ..
mkdir orig-renamed
groovy createGPMLfiles.groovy
```
