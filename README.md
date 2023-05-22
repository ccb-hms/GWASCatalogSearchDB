# GWASCatalogSearchDB

This resource aims to facilitate search for GWAS records in the GWAS Catalog database. This is achieved by combining the EFO ontology mappings given in the GWAS Catalog metadata with tabular representations of ontology relationships, such that users can search for GWAS Catalog records leveraging the EFO class hierarchy. 

`src/assemble_database.py` generates the SQLite3 database `gwascatalog_search.db` that contains:
- The original GWAS Catalog metadata table with all traits and associated study accession identifiers
- Tables that specify EFO terms—their labels, identifiers and mapping counts—and the asserted and inferred hierarchical (SubclassOf) relationships between EFO terms (extracted from a [SemanticSQL](https://github.com/INCATools/semantic-sql) EFO build). 

`src/query_database.py` contains a simple search function (described below) to query the generated database for GWAS Catalog records annotated/mapped to a user-specified set of EFO traits.

```python
def resources_annotated_with_terms(db_cursor, 
                                   search_terms=['EFO:0009605', 'EFO:0005741'],  # pancreas and infectious disease
                                   include_subclasses=True, 
                                   direct_subclasses_only=False]
```

- `db_cursor`— cursor for database connection
- `search_terms`— a collection of ontology terms to search on
- `include_subclasses`— include resources annotated with subclasses of the given search terms,
        otherwise only resources explicitly annotated with those terms are returned
- `direct_subclasses_only`— include only the direct subclasses of the given search terms,
        otherwise all the resources annotated with inferred subclasses of the given terms are returned
