import io
import os
import sys
import tarfile
import time
import requests
import pandas as pd
from datetime import datetime
from generate_ontology_tables import get_curie_id_for_term

__version__ = "0.9.1"

# Specify whether to download the newest versions of the GWAS Catalog Studies and Associations tables
DOWNLOAD_NEWEST = True

# Versions of ontologies and the resulting search database
EFO_VERSION = "3.62.0"
UBERON_VERSION = "2024-01-18"
SEARCH_DB_VERSION = "0.10.0"

# Input tables from GWAS Catalog
GWASCATALOG_STUDIES_TABLE_URL = "https://www.ebi.ac.uk/gwas/api/search/downloads/studies_alternative"
GWASCATALOG_ASSOCIATIONS_TABLE_URL = "https://www.ebi.ac.uk/gwas/api/search/downloads/alternative"

DATASET_NAME = "gwascatalog"
OUTPUT_DATABASE_FILEPATH = os.path.join("..", DATASET_NAME + "_search.db")
RESOURCES_FOLDER = os.path.join("..", "resources")

# Column names of the studies metadata table
INPUT_METADATA_STUDY_ID_COLUMN = "STUDY ACCESSION"
INPUT_METADATA_TABLE_TRAIT_COLUMN = "DISEASE/TRAIT"
PUBMED_ID_COLUMN = "PUBMEDID"

# Column names of ontology mapping details in input metadata (which are also used in the output database)
MAPPED_TRAIT_COLUMN = "MAPPED_TRAIT"
MAPPED_TRAIT_IRI_COLUMN = "MAPPED_TRAIT_URI"
MAPPED_TRAIT_CURIE_COLUMN = "MAPPED_TRAIT_CURIE"

# Column names of the output database, which are different from the input as of the latest version
OUTPUT_DB_STUDY_ID_COLUMN = "STUDY.ACCESSION"
OUTPUT_DB_TRAIT_COLUMN = "DISEASE.TRAIT"


def download_gwascatalog_table(table_url):
    response = requests.get(table_url)
    if response.status_code == 200:
        data = response.content
        df = pd.read_csv(io.StringIO(data.decode('utf-8')), sep="\t", low_memory=False)
        return df
    else:
        print(f"Failed to retrieve GWAS Catalog table from the URL {table_url}")


def get_gwascatalog_studies_table(download_newest=DOWNLOAD_NEWEST):
    if download_newest:
        gwascatalog_studies_df = download_gwascatalog_table(GWASCATALOG_STUDIES_TABLE_URL)
    else:
        gwascatalog_studies_df = pd.read_csv(os.path.join("..", "resources", "gwascatalog_metadata.tsv"), sep="\t")
    gwascatalog_studies_df = gwascatalog_studies_df.drop(gwascatalog_studies_df.columns[0], axis=1)
    gwascatalog_studies_df[MAPPED_TRAIT_CURIE_COLUMN] = gwascatalog_studies_df[MAPPED_TRAIT_IRI_COLUMN].apply(
        get_curie_id_for_term)

    # In studies v1.0.2 the names of columns changed w.r.t. the previous table
    gwascatalog_studies_df = gwascatalog_studies_df.rename(
        columns={INPUT_METADATA_STUDY_ID_COLUMN: OUTPUT_DB_STUDY_ID_COLUMN,
                 INPUT_METADATA_TABLE_TRAIT_COLUMN: OUTPUT_DB_TRAIT_COLUMN})
    gwascatalog_studies_df.to_csv(os.path.join(RESOURCES_FOLDER, "gwascatalog_metadata.tsv"), sep="\t", index=False)
    return gwascatalog_studies_df


def get_gwascatalog_associations_table(download_newest=DOWNLOAD_NEWEST):
    if download_newest:
        gwascatalog_associations_df = download_gwascatalog_table(GWASCATALOG_ASSOCIATIONS_TABLE_URL)
    else:
        gwascatalog_associations_df = pd.read_csv(os.path.join(RESOURCES_FOLDER, "gwascatalog_associations.tsv"),
                                                  sep="\t", low_memory=False)

    gwascatalog_associations_df = gwascatalog_associations_df.rename(
        columns={INPUT_METADATA_STUDY_ID_COLUMN: OUTPUT_DB_STUDY_ID_COLUMN})

    # Reduce the table to columns of interest
    gwascatalog_associations_df = gwascatalog_associations_df[
        ['STUDY.ACCESSION', 'REGION', 'CHR_ID', 'CHR_POS', 'REPORTED GENE(S)', 'MAPPED_GENE', 'UPSTREAM_GENE_ID',
         'DOWNSTREAM_GENE_ID', 'SNP_GENE_IDS', 'UPSTREAM_GENE_DISTANCE', 'DOWNSTREAM_GENE_DISTANCE',
         'STRONGEST SNP-RISK ALLELE', 'SNPS', 'SNP_ID_CURRENT', 'RISK ALLELE FREQUENCY', 'P-VALUE', 'PVALUE_MLOG',
         'MAPPED_TRAIT', 'MAPPED_TRAIT_URI']]

    gwascatalog_associations_df[MAPPED_TRAIT_CURIE_COLUMN] = gwascatalog_associations_df['MAPPED_TRAIT_URI'].apply(
        get_curie_id_for_term)

    gwascatalog_associations_df.to_csv(os.path.join(RESOURCES_FOLDER, "gwascatalog_associations.tsv"), sep="\t", index=False)
    return gwascatalog_associations_df


def get_text2term_mappings_table(metadata_df):
    mappings_list = []
    for _, row in metadata_df.iterrows():
        mapped_trait_uri = row[MAPPED_TRAIT_IRI_COLUMN]
        # TODO split the comma-separated labels as well, or obtain the label for each split out IRI
        if mapped_trait_uri != "" and not pd.isna(mapped_trait_uri):
            if "," in mapped_trait_uri:
                iris_list = mapped_trait_uri.split(',')
            else:
                iris_list = [mapped_trait_uri]
            # Add a new row to the "mappings_df" for each IRI in the list
            for iri in iris_list:
                iri = iri.strip()
                mappings = {OUTPUT_DB_STUDY_ID_COLUMN: row[OUTPUT_DB_STUDY_ID_COLUMN],
                            OUTPUT_DB_TRAIT_COLUMN: row[OUTPUT_DB_TRAIT_COLUMN],
                            MAPPED_TRAIT_COLUMN: row[MAPPED_TRAIT_COLUMN],
                            MAPPED_TRAIT_IRI_COLUMN: iri,
                            MAPPED_TRAIT_CURIE_COLUMN: get_curie_id_for_term(iri),
                            "Tags": "None",
                            "Source": "GWASCatalog"}
                mappings_list.append(mappings)
    mappings_df = pd.DataFrame(mappings_list)
    mappings_df.to_csv(os.path.join(RESOURCES_FOLDER, "gwascatalog_mappings.tsv"), sep="\t", index=False)
    return mappings_df


def get_version_info_table(studies_timestamp, associations_timestamp):
    data = [("SearchDB", SEARCH_DB_VERSION),
            ("EFO", EFO_VERSION),
            ("UBERON", UBERON_VERSION),
            ("Studies", studies_timestamp),
            ("Associations", associations_timestamp)]
    df = pd.DataFrame(data, columns=["Resource", "Version"])
    return df


def create_tar_archive(source_file):
    base_filename = os.path.basename(source_file)

    # Create a tar archive using XZ compression
    with tarfile.open(source_file + ".tar.xz", "w:xz") as tar:
        tar.add(source_file, arcname=base_filename)


if __name__ == "__main__":
    print("Downloading GWAS Catalog Studies table...")
    studies_df = get_gwascatalog_studies_table()  # get studies metadata table
    studies_download_timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    print("Downloading GWAS Catalog Associations table...")
    associations_df = get_gwascatalog_associations_table()  # get associations table
    associations_download_timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    version_info_df = get_version_info_table(studies_download_timestamp, associations_download_timestamp)

    extra_tables = {"version_info": version_info_df,
                    "gwascatalog_associations": associations_df}

    # Generate and save a text2term-formatted table of ontology mappings in the GWAS Catalog metadata table
    ontology_mappings = get_text2term_mappings_table(studies_df)

    # Check if an NCBI API Key is provided
    if len(sys.argv) > 1:
        os.environ["NCBI_API_KEY"] = sys.argv[1]
        print(f"Using NCBI API Key: {os.environ.get('NCBI_API_KEY')}")
    else:
        print("NCBI API Key not provided—PubMed queries will be slower. Provide API Key as a parameter to this module.")

    start = time.time()
    from build_database import build_database
    build_database(metadata_df=studies_df,
                   output_database_filepath=OUTPUT_DATABASE_FILEPATH,
                   ontology_mappings_df=ontology_mappings,
                   compute_mappings=True,
                   include_cross_ontology_references_table=True,
                   min_mapping_score=0.1,
                   max_mappings=1,
                   ontology_url=f"http://www.ebi.ac.uk/efo/releases/v{EFO_VERSION}/efo.owl",
                   resource_col=OUTPUT_DB_TRAIT_COLUMN,
                   resource_id_col=OUTPUT_DB_STUDY_ID_COLUMN,
                   ontology_term_col=MAPPED_TRAIT_COLUMN,
                   ontology_term_iri_col=MAPPED_TRAIT_IRI_COLUMN,
                   ontology_term_curie_col=MAPPED_TRAIT_CURIE_COLUMN,
                   pmid_col=PUBMED_ID_COLUMN,
                   mapping_base_iris=("http://www.ebi.ac.uk/efo/", "http://purl.obolibrary.org/obo/MONDO",
                                      "http://purl.obolibrary.org/obo/HP", "http://www.orpha.net/ORDO",
                                      "http://purl.obolibrary.org/obo/DOID"),
                   additional_tables=extra_tables,
                   additional_ontologies=["UBERON"]
                   )
    create_tar_archive(source_file=OUTPUT_DATABASE_FILEPATH)
    print(f"Finished building database ({time.time() - start:.1f} seconds)")
