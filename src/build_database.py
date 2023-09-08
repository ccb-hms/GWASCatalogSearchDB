import os
import sqlite3
import time
import text2term
import bioregistry
import pandas as pd
from tqdm import tqdm
from pathlib import Path
from metapub import PubMedFetcher
from generate_ontology_tables import get_semsql_tables_for_ontology
from generate_mapping_report import get_mapping_counts

__version__ = "1.3.0"

DB_RESOURCES_FOLDER = "../resources/"

text2term_mapping_source_term_col = "SourceTerm"
text2term_mapping_source_term_id_col = "SourceTermID"
text2term_mapping_target_term_iri_col = "MappedTermIRI"
text2term_mapping_score_col = "MappingScore"


# Assemble a SQLite database that contains:
# 1) The original user-specified metadata table
# 3) SemanticSQL tables of the specified ontology that enable search by leveraging the ontology class hierarchy
# 4) Mappings of the values in the specified column of the metadata table to terms in the specified ontology
# 5) Counts of how many data points in the metadata were mapped—either directly or indirectly—to each ontology term
def build_database(metadata_df, dataset_name, ontology_name,
                   resource_col=text2term_mapping_source_term_col,
                   resource_id_col=text2term_mapping_source_term_id_col,
                   output_database_filepath="",
                   ontology_term_iri_col=text2term_mapping_target_term_iri_col,
                   ontology_semsql_db_url="", ontology_url="", pmid_col="",
                   ontology_mappings_df=None, mapping_minimum_score=0.7, mapping_base_iris=(),
                   include_cross_ontology_references_table=False, additional_tables=(), additional_ontologies=()):
    ontology_name = ontology_name.lower()

    # Get target ontology URL from the specified ontology name
    if ontology_url == "":
        ontology_url = bioregistry.get_owl_download(ontology_name)

    # Create SQLite database
    if output_database_filepath == "":
        output_database_filepath = "../" + dataset_name + "_search.db"
    Path(output_database_filepath).touch()
    db_connection = sqlite3.connect(output_database_filepath)

    # Add the given metadata table to the database
    import_df_to_db(db_connection, data_frame=metadata_df, table_name=dataset_name + "_metadata")

    # Add ontology tables to the database
    primary_ontology_labels_df = import_ontology_tables(db_connection, ontology_name=ontology_name,
                                                        ontology_semsql_db_url=ontology_semsql_db_url,
                                                        include_crossrefs_table=include_cross_ontology_references_table,
                                                        primary_ontology=True)
    for ontology in additional_ontologies:
        import_ontology_tables(db_connection, ontology_name=ontology.lower(), ontology_semsql_db_url="",
                               include_crossrefs_table=False, primary_ontology=False)

    # Get details (title, abstract, journal) from PubMed about references in the specified PMID column
    references_table_filename = DB_RESOURCES_FOLDER + dataset_name + "_references.tsv"
    if not os.path.isfile(references_table_filename):
        references_df = get_pubmed_details(metadata_df=metadata_df, dataset_name=dataset_name, pmid_col=pmid_col)
    else:
        # TODO incrementally update the existing table with any new references in the metadata
        references_df = pd.read_csv(references_table_filename, sep="\t")
    import_df_to_db(db_connection, data_frame=references_df, table_name=dataset_name + "_references")

    # Map the values in the specified metadata table column to the specified ontology
    if ontology_mappings_df is None:
        ontology_mappings_df = map_metadata_to_ontologies(metadata_df=metadata_df, dataset_name=dataset_name,
                                                          ontology_url=ontology_url, min_score=mapping_minimum_score,
                                                          source_term_col=resource_col,
                                                          source_term_id_col=resource_id_col,
                                                          base_iris=mapping_base_iris)
        resource_col = text2term_mapping_source_term_col
        resource_id_col = text2term_mapping_source_term_id_col
        ontology_term_iri_col = text2term_mapping_target_term_iri_col
        ontology_mappings_df.columns = ontology_mappings_df.columns.str.replace(' ', '')
    import_df_to_db(db_connection, data_frame=ontology_mappings_df, table_name=dataset_name + "_mappings")

    # Get counts of mappings
    counts_df = get_mapping_counts(mappings_df=ontology_mappings_df, ontology_iri=ontology_url,
                                   source_term_col=resource_col, save_ontology=True,
                                   source_term_id_col=resource_id_col,
                                   mapped_term_iri_col=ontology_term_iri_col)
    counts_df.to_csv(DB_RESOURCES_FOLDER + ontology_name + "_mappings_counts.tsv", sep="\t", index=False)

    # Merge the counts table with the labels table on the "IRI" column
    merged_df = pd.merge(primary_ontology_labels_df, counts_df, on="IRI")

    # Save the merged table to disk and add it to the database
    merged_df.to_csv(DB_RESOURCES_FOLDER + ontology_name + "_labels.tsv", sep="\t", index=False)
    import_df_to_db(db_connection, data_frame=merged_df, table_name=ontology_name + "_labels")

    # Add any additional tables given
    if len(additional_tables) > 0:
        for table_name in additional_tables.keys():
            import_df_to_db(db_connection, data_frame=additional_tables[table_name], table_name=table_name)


def import_ontology_tables(db_connection, ontology_name, ontology_semsql_db_url,
                           include_crossrefs_table, primary_ontology=True):
    # Get SemanticSQL ontology tables and add them to the database
    start = time.time()
    if ontology_semsql_db_url == "":
        ontology_semsql_db_url = "https://s3.amazonaws.com/bbop-sqlite/" + ontology_name + ".db.gz"
    edges_df, entailed_edges_df, labels_df, dbxrefs_df, synonyms_df, ontology_version = \
        get_semsql_tables_for_ontology(
            ontology_url=ontology_semsql_db_url,
            ontology_name=ontology_name.upper(),
            tables_output_folder=DB_RESOURCES_FOLDER,
            db_output_folder=DB_RESOURCES_FOLDER,
            save_tables=True,
            include_disease_locations=primary_ontology)
    print(f"...done ({time.time() - start:.1f} seconds)")
    import_df_to_db(db_connection, data_frame=edges_df, table_name=ontology_name + "_edges")
    import_df_to_db(db_connection, data_frame=entailed_edges_df, table_name=ontology_name + "_entailed_edges")
    import_df_to_db(db_connection, data_frame=synonyms_df, table_name=ontology_name + "_synonyms")
    if include_crossrefs_table:
        import_df_to_db(db_connection, data_frame=dbxrefs_df, table_name=ontology_name + "_dbxrefs")
    if not primary_ontology:
        import_df_to_db(db_connection, data_frame=labels_df, table_name=ontology_name + "_labels")
    return labels_df


dtypes = {'int64': 'INTEGER', 'float64': 'REAL', 'object': 'TEXT', 'datetime64': 'TEXT'}


# Import the given data frame to the SQLite database through the specified connection
# The CREATE TABLE statement is built using the given data frame's column names and inferred data types
def import_df_to_db(connection, data_frame, table_name):
    columns = []
    for column_name, dtype in zip(data_frame.columns, data_frame.dtypes):
        sql_type = dtypes.get(str(dtype), 'TEXT')
        column_name = column_name.replace(":", "_")
        column_name = column_name.replace(" ", "")
        columns.append(f"`{column_name}` {sql_type}")
    create_table_query = f'CREATE TABLE IF NOT EXISTS {table_name} ({", ".join(columns)})'
    connection.cursor().execute(create_table_query)
    data_frame.to_sql(table_name, connection, if_exists="replace", index=False)


# Map values in the specified metadata column to terms in the specified ontology set
def map_metadata_to_ontologies(metadata_df, dataset_name, ontology_url, min_score, source_term_col,
                               source_term_id_col, base_iris=()):
    print(f"Mapping values in metadata column '{source_term_col}' to terms in '{ontology_url}'...")
    start = time.time()
    source_terms = metadata_df[source_term_col].tolist()
    if source_term_id_col != "":
        source_term_ids = metadata_df[source_term_id_col].tolist()
    else:
        source_term_ids = ()
    mappings = text2term.map_terms(source_terms=source_terms, source_terms_ids=source_term_ids,
                                   target_ontology=ontology_url, excl_deprecated=True, save_graphs=False,
                                   max_mappings=1, min_score=min_score, save_mappings=True,
                                   output_file=DB_RESOURCES_FOLDER + dataset_name + "_mappings.csv",
                                   base_iris=base_iris)
    mappings.columns = mappings.columns.str.replace(" ", "")  # remove spaces from column names
    print(f"...done ({time.time() - start:.1f} seconds)")
    return mappings


# Get publication details from PubMed (title, abstract, journal, etc) for the PMIDS in the specified column
def get_pubmed_details(metadata_df, dataset_name, pmid_col):
    print("Fetching publication metadata from PubMed...")
    start = time.time()
    pmids = metadata_df[pmid_col].dropna().unique()
    fetch = PubMedFetcher()
    articles = []
    for pmid in tqdm(pmids):
        article_details = get_pubmed_article_details(fetch, pmid)
        if article_details != "":
            articles.append(article_details)
    references_df = pd.DataFrame(articles, columns=[pmid_col, 'Journal', 'Title', 'Abstract', 'Year', 'URL'])
    references_df.to_csv(DB_RESOURCES_FOLDER + dataset_name + "_references.tsv", sep="\t", index=False)
    print(f"...done ({time.time() - start:.1f} seconds)")
    return references_df


def get_pubmed_article_details(pubmed_fetcher, pmid, repeat=True):
    if pmid != "0" and pmid != "nan":
        try:
            article = pubmed_fetcher.article_by_pmid(pmid)
            title = article.title
            journal = article.journal
            year = article.year
            abstract = article.abstract
            url = article.url
            return pmid, journal, title, abstract, year, url
        except Exception as e:
            # Try to fetch details once more. Sometimes the NCBI API errors out, but a second attempt (usually) succeeds
            if repeat:
                return get_pubmed_article_details(pubmed_fetcher, pmid, repeat=False)
    return ""
