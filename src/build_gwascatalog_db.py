import os
import sys
import time
import pandas as pd
from generate_ontology_tables import get_curie_id_for_term

__version__ = "0.2.0"


def get_text2term_mappings_table(metadata_df):
    ontology_mappings_df = pd.DataFrame()
    ontology_mappings_df["SourceTermID"] = metadata_df["STUDY.ACCESSION"]
    ontology_mappings_df["SourceTerm"] = metadata_df["DISEASE.TRAIT"]
    ontology_mappings_df["MappedTermLabel"] = metadata_df["MAPPED_TRAIT"]
    ontology_mappings_df["MappedTermCURIE"] = metadata_df["MAPPED_TRAIT_URI"].apply(get_curie_id_for_term)
    ontology_mappings_df["MappedTermIRI"] = metadata_df["MAPPED_TRAIT_URI"]
    ontology_mappings_df.to_csv("../resources/gwascatalog_mappings.tsv", sep="\t", index=False)
    return ontology_mappings_df


if __name__ == "__main__":
    gwascatalog_metadata = pd.read_csv("../resources/gwascatalog_metadata.tsv", sep="\t")
    gwascatalog_metadata = gwascatalog_metadata.drop(gwascatalog_metadata.columns[0], axis=1)

    # Generate and save a text2term-formatted table of ontology mappings in the GWAS Catalog metadata table
    ontology_mappings = get_text2term_mappings_table(gwascatalog_metadata)

    # Check if an NCBI API Key is provided
    if len(sys.argv) > 1:
        os.environ["NCBI_API_KEY"] = sys.argv[1]
        print(f"Using NCBI API Key: {os.environ.get('NCBI_API_KEY')}")
    else:
        print("NCBI API Key not provided—PubMed queries will be slower. Provide API Key as a parameter to this module.")

    # Build the database
    start = time.time()
    from build_database import build_database
    build_database(dataset_name="gwascatalog",
                   metadata_df=gwascatalog_metadata,
                   ontology_mappings_df=ontology_mappings,
                   ontology_name="EFO",
                   pmid_col="PUBMEDID")
    print(f"Finished building database ({time.time() - start:.1f} seconds)")
