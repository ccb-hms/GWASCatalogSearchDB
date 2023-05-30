import pandas as pd
from build_database import build_database
from generate_ontology_tables import get_curie_id_for_term


# TODO there are multiple MAPPED TRAIT URIs for each GWAS Catalog record
if __name__ == "__main__":
    gwascatalog_metadata = pd.read_csv("../resources/gwascatalog_metadata.tsv", sep="\t")
    gwascatalog_metadata["MAPPED_TRAIT_CURIE"] = gwascatalog_metadata["MAPPED_TRAIT_URI"].apply(get_curie_id_for_term)

    build_database(dataset_name="gwascatalog",
                   metadata_df=gwascatalog_metadata,
                   ontology_mappings_df=gwascatalog_metadata,
                   ontology_name="EFO",
                   resource_col="DISEASE.TRAIT",
                   resource_id_col="STUDY.ACCESSION",
                   ontology_term_iri_col="MAPPED_TRAIT_URI",
                   pmid_col="PUBMEDID")
