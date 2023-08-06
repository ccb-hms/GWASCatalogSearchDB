import os
import sys
import time
import pandas as pd
from generate_ontology_tables import get_curie_id_for_term

__version__ = "0.3.0"


def get_text2term_mappings_table(metadata_df):
    mappings_list = []
    for _, row in metadata_df.iterrows():
        # Split the comma-separated URIs in "MAPPED_TRAIT_URI" into separate rows
        mapped_trait_uri = row['MAPPED_TRAIT_URI']
        if mapped_trait_uri != "" and not pd.isna(mapped_trait_uri):
            if "," in mapped_trait_uri:
                iris_list = mapped_trait_uri.split(',')
            else:
                iris_list = [mapped_trait_uri]
            # Add a new row to the "mappings_df" for each IRI in the list
            for iri in iris_list:
                iri = iri.strip()
                mappings = {'STUDY.ACCESSION': row['STUDY.ACCESSION'],
                            'DISEASE.TRAIT': row['DISEASE.TRAIT'],
                            'MAPPED_TRAIT': row['MAPPED_TRAIT'],
                            'MAPPED_TRAIT_URI': iri,
                            'MAPPED_TRAIT_CURIE': get_curie_id_for_term(iri)}
                mappings_list.append(mappings)
    mappings_df = pd.DataFrame(mappings_list)
    mappings_df.to_csv("../resources/gwascatalog_mappings.tsv", sep="\t", index=False)
    return mappings_df


if __name__ == "__main__":
    gwascatalog_metadata = pd.read_csv("../resources/gwascatalog_metadata.tsv", sep="\t")
    gwascatalog_metadata = gwascatalog_metadata.drop(gwascatalog_metadata.columns[0], axis=1)
    gwascatalog_metadata["MAPPED_TRAIT_CURIE"] = gwascatalog_metadata["MAPPED_TRAIT_URI"].apply(get_curie_id_for_term)

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
                   resource_col="DISEASE.TRAIT",
                   resource_id_col="STUDY.ACCESSION",
                   ontology_term_iri_col="MAPPED_TRAIT_URI",
                   pmid_col="PUBMEDID")
    print(f"Finished building database ({time.time() - start:.1f} seconds)")
