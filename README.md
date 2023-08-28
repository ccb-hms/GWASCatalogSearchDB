# GWASCatalogSearchDB

This repository provides a SQLite database designed to facilitate search for GWAS records in the [GWAS Catalog](https://www.ebi.ac.uk/gwas/) database—the NHGRI-EBI Catalog of human genome-wide association studies. This is achieved by combining the [EFO](https://www.ebi.ac.uk/efo/) ontology mappings specified in the GWAS Catalog metadata with tabular representations of ontology relationships—extracted from a [SemanticSQL](https://github.com/INCATools/semantic-sql) database representation of EFO—such that users can search for GWAS Catalog records by leveraging the EFO class hierarchy. 

### Building the database
The database is built by running the Python module below. 

```python
python3 src/build_gwascatalog_db.py
```
This generates a tarball `gwascatalog_search.db.tar.gz` containing the SQLite3 database `gwascatalog_search.db`. 

The database contains the tables depicted and described below.

![](resources/gwascatalog_search_tables.png)

- `gwascatalog_metadata` contains the GWAS Catalog table [_All studies v1.0.2_](https://www.ebi.ac.uk/gwas/docs/file-downloads).
- `gwascatalog_associations` contains some columns from the table [_All associations v1.0.2_](https://www.ebi.ac.uk/gwas/docs/file-downloads).  
- `gwascatalog_references` contains details obtained from PubMed about the articles in the `PUBMEDID` column of the metadata table. 
- `gwascatalog_mappings` contains ontology mappings extracted from `gwascatalog_metadata` with each mapping in a separate row. In the original metadata there are often multiple ontology mappings provided as comma-separated strings.
- `efo_labels` contains the following details:
  - all terms in EFO, represented by their CURIEs (`Subject` column). 
  - term labels (`Object` column). 
  - term IRIs (`IRI` column).
  - disease locations associated with each term, if available (`DiseaseLocation` column). 
  - count of how many metadata points are directly mapped to those ontology terms (`Direct` column). 
  - count of how many metadata points are indirectly mapped to those terms via a more specific term in the hierarchy (`Inherited` column).
- `efo_edges` and `efo_entailed_edges` contain, respectively, the asserted and entailed hierarchical (IS-A/SubClassOf) relationships between terms in EFO.
- `efo_synonyms` contains the potentially multiple synonyms (in the `Object` column) of each EFO term (given in the `Subject` column).
- `version_info` contains the timestamps of download of the GWAS Catalog tables and the EFO version. 

### Querying the database
`src/query_database.py` contains a search function (described below) to query the `gwascatalog_search.db` database for records annotated/mapped to a user-specified set of EFO traits.

```python
# search for GWAS Catalog records annotated with pancreas or infectious disease
resources_annotated_with_terms(db_cursor, 
                               search_terms=['EFO:0009605', 'EFO:0005741'],
                               include_subclasses=True, 
                               direct_subclasses_only=False]
```
The function parameters are:
- `db_cursor`— cursor for database connection
- `search_terms`— a collection of ontology terms to search on
- `include_subclasses`— include resources annotated with subclasses of the given search terms,
        otherwise only resources explicitly annotated with those terms are returned
- `direct_subclasses_only`— include only the direct subclasses of the given search terms,
        otherwise all the resources annotated with inferred subclasses of the given terms are returned

Each search term must be an EFO term specified by its compact uniform resource identifier ([CURIE](https://www.w3.org/TR/curie/)). For example `EFO:0005741` is the short form of [http://www.ebi.ac.uk/efo/EFO_0005741](http://www.ebi.ac.uk/efo/EFO_0005741).