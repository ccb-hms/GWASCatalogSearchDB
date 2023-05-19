import pandas as pd
from owlready2 import *

__version__ = "0.5.0"

BASE_IRI = "https://computationalbiomed.hms.harvard.edu/ontology/"

TERM_BLOCKLIST = ("BFO_", "CHEBI_", "PATO_", "NCBITaxon_", "dbpedia.org", "CL_", "CLO_", "UO_", "GO_", "BAO_", "BTO_",
                  "IAO_", "EO_", "FBbt_", "FMA_", "UBERON_", "IDO_", "MA_", "FBdv_")

SOURCE_TERM_ID_COL = 'SourceTermID'
SOURCE_TERM_2ND_ID_COL = ''
SOURCE_TERM_COL = "SourceTerm"
MAPPED_TERM_IRI_COL = "MappedTermIRI"
ONTOLOGY_COL = "Ontology"
SAVE_ONTOLOGY = False
USE_REASONING = False


def get_mapping_counts_to_ontologies(mappings_df, ontologies_df,
                                     source_term_id_col=SOURCE_TERM_ID_COL,
                                     source_term_secondary_id_col=SOURCE_TERM_2ND_ID_COL,
                                     source_term_col=SOURCE_TERM_COL,
                                     mapped_term_iri_col=MAPPED_TERM_IRI_COL,
                                     save_ontology=SAVE_ONTOLOGY,
                                     use_reasoning=USE_REASONING,
                                     ontology_term_blocklist=TERM_BLOCKLIST):
    all_mappings = pd.DataFrame()
    for index, row in ontologies_df.iterrows():
        ontology_name = row['acronym']
        ontology_iri = row['url']
        ontology_mappings_df = mappings_df[mappings_df[ONTOLOGY_COL] == ontology_name]
        ontology_mappings_counts = get_mapping_counts(mappings_df=ontology_mappings_df,
                                                      ontology_iri=ontology_iri,
                                                      ontology_name=ontology_name,
                                                      source_term_id_col=source_term_id_col,
                                                      source_term_secondary_id_col=source_term_secondary_id_col,
                                                      source_term_col=source_term_col,
                                                      mapped_term_iri_col=mapped_term_iri_col,
                                                      save_ontology=save_ontology,
                                                      use_reasoning=use_reasoning,
                                                      ontology_term_blocklist=ontology_term_blocklist)
        ontology_mappings_counts[ONTOLOGY_COL] = ontology_name
        all_mappings = pd.concat([all_mappings, ontology_mappings_counts])
    return all_mappings


def get_mapping_counts(mappings_df, ontology_iri, ontology_name,
                       source_term_id_col=SOURCE_TERM_ID_COL,
                       source_term_secondary_id_col=SOURCE_TERM_2ND_ID_COL,
                       source_term_col=SOURCE_TERM_COL,
                       mapped_term_iri_col=MAPPED_TERM_IRI_COL,
                       save_ontology=SAVE_ONTOLOGY,
                       use_reasoning=USE_REASONING,
                       ontology_term_blocklist=TERM_BLOCKLIST):
    print(f"Computing counts of direct and inherited mappings to {ontology_name}...")
    mappings_df.columns = mappings_df.columns.str.replace(' ', '')  # remove spaces from column names
    start = time.time()
    ontology = get_ontology(ontology_iri).load()
    _create_instances(ontology, ontology_name, mappings_df, save_ontology=save_ontology, use_reasoning=use_reasoning,
                      source_term_id_col=source_term_id_col, source_term_secondary_id_col=source_term_secondary_id_col,
                      source_term_col=source_term_col, mapped_term_iri_col=mapped_term_iri_col)
    output = []
    for term in ontology.classes():
        if not any([iri_bit in term.iri for iri_bit in ontology_term_blocklist]):
            term_df = mappings_df[mappings_df[mapped_term_iri_col] == term.iri]
            direct_mappings = term_df.shape[0]
            instances = term.instances()
            local_instances = []
            for instance in instances:
                if BASE_IRI in instance.iri:
                    local_instances.append(instance)
            inferred_mappings = len(local_instances)
            output.append((term.iri, direct_mappings, inferred_mappings))
    output_df = pd.DataFrame(data=output, columns=['IRI', 'Direct', 'Inherited'])
    print(f"...done ({time.time() - start:.1f} seconds)")
    return output_df


def _create_instances(ontology, ontology_name, mappings_df, source_term_id_col, source_term_secondary_id_col,
                      source_term_col, mapped_term_iri_col, save_ontology, use_reasoning):
    with ontology:
        if source_term_secondary_id_col != '':
            class resource_secondary_id(Thing >> str):
                pass

        class resource_id(Thing >> str):
            pass
    for index, row in mappings_df.iterrows():
        source_term = row[source_term_col]
        source_term_id = row[source_term_id_col]
        ontology_term_iri = row[mapped_term_iri_col]
        ontology_term = IRIS[ontology_term_iri]

        if ontology_term is not None:
            if source_term_secondary_id_col != '':
                source_term_secondary_id = row[source_term_secondary_id_col]
                new_instance_iri = BASE_IRI + source_term_secondary_id + "-" + source_term_id
            else:
                new_instance_iri = BASE_IRI + source_term_id

            if IRIS[new_instance_iri] is not None:
                labels = IRIS[new_instance_iri].label
                if source_term not in labels:
                    labels.append(source_term)
            else:
                # create OWL instance to represent mapping
                new_instance = ontology_term(label=source_term, iri=new_instance_iri)
                new_instance.resource_id.append(source_term_id)

                if source_term_secondary_id_col != '':
                    new_instance.resource_secondary_id.append(source_term_secondary_id)
    if save_ontology:
        ontology.save(ontology_name + "_mappings.owl")

    if use_reasoning:
        print("...reasoning over ontology...")
        owlready2.reasoning.JAVA_MEMORY = 20000  # TODO: even so the HermiT reasoner performs poorly on EFO+mappings
        with ontology:
            sync_reasoner()
