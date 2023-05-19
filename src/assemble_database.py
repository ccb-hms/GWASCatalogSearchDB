import sqlite3
import pandas as pd
from pathlib import Path
from generate_semql_ontology_tables import get_semsql_tables_for_ontology, get_curie_id_for_term
from generate_mapping_report import get_mapping_counts

__version__ = "0.1.0"


# Assemble a SQLite database that contains:
# 1) The original GWAS Catalog metadata table
# 3) SemanticSQL tables of EFO that enable searching over traits by leveraging the EFO class hierarchy
# 4) Counts of how many traits in the metadata were mapped—either directly or indirectly—to each ontology term
def assemble_database(metadata_df, dataset_name):
    target_ontology_name = "EFO"

    # Get SemanticSQL EFO tables
    edges_df, entailed_edges_df, labels_df, dbxrefs_df, ontology_version = get_semsql_tables_for_ontology(
        ontology_url="https://s3.amazonaws.com/bbop-sqlite/efo.db",
        ontology_name=target_ontology_name,
        tables_output_folder="../resources/",
        db_output_folder="../resources/",
        save_tables=True)
    print("...working with EFO v" + ontology_version)

    # Create SQLite database
    db_name = "../" + dataset_name + "_search.db"
    Path(db_name).touch()
    db_connection = sqlite3.connect(db_name)

    # Add metadata table to the database
    metadata_tbl_cols = "`STUDY.ACCESSION`,`DISEASE.TRAIT`,MAPPED_TRAIT,MAPPED_TRAIT_URI,STUDY," \
                        "`GENOTYPING.TECHNOLOGY`,PUBMEDID,DATE,MAPPED_TRAIT_CURIE"
    import_df_to_db(db_connection, data_frame=metadata_df, table_name=dataset_name + "_metadata", table_columns=metadata_tbl_cols)

    # Add SemanticSQL tables to the database
    semsql_tbl_cols = "Subject TEXT,Object TEXT"
    import_df_to_db(db_connection, data_frame=edges_df, table_name="efo_edges", table_columns=semsql_tbl_cols)
    import_df_to_db(db_connection, data_frame=entailed_edges_df, table_name="efo_entailed_edges", table_columns=semsql_tbl_cols)
    import_df_to_db(db_connection, data_frame=dbxrefs_df, table_name="efo_dbxrefs", table_columns=semsql_tbl_cols)

    # Use the same version of EFO as used in the SemanticSQL distribution of EFO
    efo_url = "https://github.com/EBISPOT/efo/releases/download/v" + ontology_version + "/efo.owl"

    # Get counts of mappings
    counts_df = get_mapping_counts(mappings_df=metadata_df, ontology_name=target_ontology_name, ontology_iri=efo_url,
                                   source_term_col="DISEASE.TRAIT",
                                   source_term_id_col="STUDY.ACCESSION",
                                   mapped_term_iri_col="MAPPED_TRAIT_URI")
    counts_df.to_csv("../resources/efo_mappings_counts.tsv", sep="\t", index=False)

    # Merge the counts table with the labels table on the "iri" column, and add the merged table to the database
    merged_df = pd.merge(labels_df, counts_df, on="IRI")
    labels_tbl_cols = semsql_tbl_cols + ",IRI TEXT,Direct INT,Inherited INT"
    import_df_to_db(db_connection, data_frame=merged_df, table_name="efo_labels", table_columns=labels_tbl_cols)


# Import the given data frame to the SQLite database through the specified connection
def import_df_to_db(connection, data_frame, table_name, table_columns):
    create_table_query = '''CREATE TABLE IF NOT EXISTS ''' + table_name + ''' (''' + table_columns + ''')'''
    connection.cursor().execute(create_table_query)
    data_frame.to_sql(table_name, connection, if_exists="replace", index=False)


# TODO there are multiple MAPPED TRAIT URIs for each GWAS Catalog record
if __name__ == "__main__":
    gwascatalog_metadata = pd.read_csv("../resources/gwascatalog_metadata.tsv", sep="\t")
    gwascatalog_metadata["MAPPED_TRAIT_CURIE"] = gwascatalog_metadata["MAPPED_TRAIT_URI"].apply(get_curie_id_for_term)
    assemble_database(metadata_df=gwascatalog_metadata, dataset_name="gwascatalog")
