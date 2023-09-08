import os
import sqlite3
import tarfile
import pandas as pd

__version__ = "0.3.0"


def resources_annotated_with_terms(db_cursor, search_terms, include_subclasses=True, direct_subclasses_only=False):
    """
    Retrieve resources annotated with the given search terms and (optionally) subclasses of that term, by specifying
    include_subclasses=True. The argument direct_subclasses_only dictates whether to include only direct subclasses or
    all inferred/indirect subclasses

    :param db_cursor:  cursor for database connection
    :param search_terms:  the ontology terms to search on
    :param include_subclasses:  include resources annotated with subclasses of the given search term,
        otherwise only resources explicitly annotated with that term are returned
    :param direct_subclasses_only:  include only the direct subclasses of the given search term,
        otherwise all the resources annotated with inferred subclasses of the given term are returned
    :return: data frame containing IDs and traits of the GWAS Catalog records found to be annotated with the give term

    An example full-formed SQL query for some example parameters is specified below.

    Function parameters:
    search_terms=['EFO:0009605','EFO:0005741']
    include_subclasses=True
    direct_subclasses_only=False

    SQL query:
    SELECT DISTINCT
        study.`STUDY.ACCESSION`,
        study.`DISEASE.TRAIT`,
        study.MAPPED_TRAIT,
        study.MAPPED_TRAIT_URI
    FROM
        `gwascatalog_metadata` study
    WHERE
        study.`STUDY.ACCESSION` IN (
            SELECT DISTINCT mapping.`STUDY.ACCESSION`
            FROM `gwascatalog_mappings` mapping
                     LEFT JOIN efo_entailed_edges ee ON (mapping.MAPPED_TRAIT_CURIE = ee.Subject)
            WHERE (mapping.MAPPED_TRAIT_CURIE = 'EFO:0005140' OR ee.Object = 'EFO:0005140')
        );
    """
    if include_subclasses:
        if direct_subclasses_only:
            ontology_table = "efo_edges"
        else:
            ontology_table = "efo_entailed_edges"
    else:
        ontology_table = "efo_edges"

    query = '''SELECT DISTINCT
                    study.`STUDY.ACCESSION`,
                    study.`DISEASE.TRAIT`,
                    study.MAPPED_TRAIT,
                    study.MAPPED_TRAIT_URI
                FROM
                    `gwascatalog_metadata` study
                WHERE
                    study.`STUDY.ACCESSION` IN (
                        SELECT DISTINCT mapping.`STUDY.ACCESSION`
                        FROM `gwascatalog_mappings` mapping
                            LEFT JOIN ''' + ontology_table + ''' ee ON (mapping.MAPPED_TRAIT_CURIE = ee.Subject)'''
    index = 0
    where_clause = "\nWHERE ("
    for term in search_terms:
        if index == 0:
            where_clause += "mapping.MAPPED_TRAIT_CURIE = \'" + term + "\'"
        else:
            where_clause += " OR mapping.MAPPED_TRAIT_CURIE = \'" + term + "\'"
        if include_subclasses:
            where_clause += " OR ee.Object = \'" + term + "\'"
        index += 1
    query += where_clause + "))"

    print(query + "\n")

    results = db_cursor.execute(query).fetchall()
    results_columns = [x[0] for x in db_cursor.description]
    return pd.DataFrame(results, columns=results_columns)


if __name__ == '__main__':
    tar_file_path = os.path.join("..", "gwascatalog_search.db.tar.xz")
    database_file_name = "gwascatalog_search.db"

    with tarfile.open(tar_file_path, "r:xz") as tar:
        tar.extract(database_file_name, path="..")

    connection = sqlite3.connect(os.path.join("..", database_file_name))
    cursor = connection.cursor()

    # Search for GWASCatalog studies mapped to either EFO:0009605 (pancreas disease) or EFO:0005741 (infectious disease)
    df = resources_annotated_with_terms(db_cursor=cursor,
                                        search_terms=['EFO:0009605', 'EFO:0005741'],
                                        include_subclasses=True,
                                        direct_subclasses_only=False)
    output_file = os.path.join("..", "test", "query_output.tsv")
    df.to_csv(output_file, sep="\t", index=False)

    print(df)
    print("Query results saved to: " + output_file)

    cursor.close()
    connection.close()
