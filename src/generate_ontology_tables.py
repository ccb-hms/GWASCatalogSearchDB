import os
import gzip
import shutil
import sqlite3
import urllib.request
import bioregistry
import pandas as pd
from collections import deque

__version__ = "0.11.5"

SUBJECT_COL = "Subject"
OBJECT_COL = "Object"
IRI_COL = "IRI"
ONTOLOGY_COL = "Ontology"
DISEASE_LOCATION_COL = "DiseaseLocation"
IRI_PRIORITY_LIST = ["obofoundry", "default", "bioregistry"]

ONTOLOGY_TABLES_OUTPUT_FOLDER = os.path.join("..", "ontology-tables")
DATABASE_OUTPUT_FOLDER = os.path.join("..", "ontology-db")


def get_semsql_tables_for_ontologies(ontologies,
                                     tables_output_folder=ONTOLOGY_TABLES_OUTPUT_FOLDER,
                                     db_output_folder=DATABASE_OUTPUT_FOLDER,
                                     save_tables=False, single_table_for_all_ontologies=False,
                                     include_disease_locations=False):
    all_edges = all_entailed_edges = all_labels = all_dbxrefs = all_synonyms = pd.DataFrame()
    for ontology in ontologies:
        ontology_url = "https://s3.amazonaws.com/bbop-sqlite/" + ontology.lower() + ".db.gz"
        edges, entailed_edges, labels, dbxrefs, synonyms, version = \
            get_semsql_tables_for_ontology(ontology_url=ontology_url,
                                           ontology_name=ontology,
                                           db_output_folder=db_output_folder,
                                           save_tables=(not single_table_for_all_ontologies),
                                           include_disease_locations=include_disease_locations)
        if single_table_for_all_ontologies:
            labels[ONTOLOGY_COL] = edges[ONTOLOGY_COL] = entailed_edges[ONTOLOGY_COL] = dbxrefs[ONTOLOGY_COL] = \
                synonyms[ONTOLOGY_COL] = ontology
            all_labels = pd.concat([all_labels, labels])
            all_edges = pd.concat([all_edges, edges])
            all_entailed_edges = pd.concat([all_entailed_edges, entailed_edges])
            all_dbxrefs = pd.concat([all_dbxrefs, dbxrefs])
            all_synonyms = pd.concat([all_synonyms, synonyms])

    if save_tables and single_table_for_all_ontologies:
        save_table(all_labels, "ontology_labels.tsv", tables_output_folder)
        save_table(all_edges, "ontology_edges.tsv", tables_output_folder)
        save_table(all_entailed_edges, "ontology_entailed_edges.tsv", tables_output_folder)
        save_table(all_dbxrefs, "ontology_dbxrefs.tsv", tables_output_folder)
        save_table(all_synonyms, "ontology_synonyms.tsv", tables_output_folder)
    return all_edges, all_entailed_edges, all_labels, all_dbxrefs, all_synonyms


def get_semsql_tables_for_ontology(ontology_url, ontology_name, tables_output_folder=ONTOLOGY_TABLES_OUTPUT_FOLDER,
                                   db_output_folder=DATABASE_OUTPUT_FOLDER, save_tables=False,
                                   include_disease_locations=False):
    db_file = os.path.join(db_output_folder, ontology_name.lower() + ".db")
    db_gz_file = db_file + ".gz"
    if not os.path.exists(db_output_folder):
        os.makedirs(db_output_folder)
    print(f"Downloading database file for {ontology_name} from {ontology_url}...")
    urllib.request.urlretrieve(ontology_url, db_gz_file)
    with gzip.open(db_gz_file, "rb") as file_in, open(db_file, "wb") as file_out:
        shutil.copyfileobj(file_in, file_out)
    print(f"Generating tables for {ontology_name}...")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    if include_disease_locations:
        _add_views(cursor)  # add database views needed for disease location retrieval
    edges_df = _get_edges_table(cursor)
    entailed_edges_df = _get_entailed_edges_table(cursor)
    labels_df = _get_labels_table(cursor, ontology_name=ontology_name, include_disease_locations=include_disease_locations)
    dbxrefs_df = _get_db_cross_references_table(cursor)
    synonyms_df = _get_synonyms_table(cursor)
    onto_version = _get_ontology_version(cursor)
    if onto_version != "":
        print(f"\t{ontology_name} version: {onto_version}")
    cursor.close()
    conn.close()
    if save_tables:
        save_table(labels_df, ontology_name.lower() + "_labels.tsv", tables_output_folder)
        save_table(edges_df, ontology_name.lower() + "_entailed_edges.tsv", tables_output_folder)
        save_table(entailed_edges_df, ontology_name.lower() + "_edges.tsv", tables_output_folder)
        save_table(dbxrefs_df, ontology_name.lower() + "_dbxrefs.tsv", tables_output_folder)
        save_table(synonyms_df, ontology_name.lower() + "_synonyms.tsv", tables_output_folder)
    return edges_df, entailed_edges_df, labels_df, dbxrefs_df, synonyms_df, onto_version


def _add_views(cursor):
    # In EFO, some disease locations are expressed in universal restrictions—for example:
    # pancreatitis (EFO:0000278) has_disease_location only pancreas
    # Currently there are no views in the SemanticSQL build of EFO for universal restrictions, only for existential ones

    # Create a view that mimics the existing view 'owl_some_values_from' but for universal restrictions instead
    create_owl_only_values_from_view = "CREATE VIEW IF NOT EXISTS owl_only_values_from AS " \
                                       "SELECT onProperty.subject AS id, onProperty.object AS on_property, f.object AS filler " + \
                                       "FROM statements AS onProperty, statements AS f " + \
                                       "WHERE onProperty.predicate = 'owl:onProperty' AND onProperty.subject=f.subject " + \
                                       "AND f.predicate='owl:allValuesFrom';"
    cursor.execute(create_owl_only_values_from_view)

    # Use the view just created to add another convenience view that mimics the existing view
    # 'owl_subclass_of_some_values_from', but again, for universal restrictions instead
    create_owl_subclass_of_only_values_from_view = "CREATE VIEW IF NOT EXISTS owl_subclass_of_only_values_from AS " + \
                                                   "SELECT subClassOf.stanza, subClassOf.subject, svf.on_property AS predicate, svf.filler AS object " + \
                                                   "FROM statements AS subClassOf, owl_only_values_from AS svf " + \
                                                   "WHERE subClassOf.predicate = 'rdfs:subClassOf' AND svf.id=subClassOf.object;"
    cursor.execute(create_owl_subclass_of_only_values_from_view)


def _get_ontology_version(cursor):
    cursor.execute("SELECT `value` FROM statements WHERE predicate='owl:versionInfo'")
    ontology_version = cursor.fetchall()
    if len(ontology_version) > 0:
        return ontology_version.pop()[0]
    return ""


def _get_edges_table(cursor):
    cursor.execute("SELECT * FROM edge WHERE predicate='rdfs:subClassOf'")
    edge_columns = [x[0] for x in cursor.description]
    edge_data = cursor.fetchall()
    edges_df = pd.DataFrame(edge_data, columns=edge_columns)
    edges_df = edges_df.drop(columns=["predicate"])
    edges_df = edges_df.rename(columns={'object': OBJECT_COL, 'subject': SUBJECT_COL})
    edges_df = edges_df.drop_duplicates()
    edges_df = fix_identifiers(edges_df, columns=[SUBJECT_COL, OBJECT_COL])
    return edges_df


def _get_entailed_edges_table(cursor):
    cursor.execute("SELECT * FROM entailed_edge WHERE predicate='rdfs:subClassOf'")
    entailed_edge_columns = [x[0] for x in cursor.description]
    entailed_edge_data = cursor.fetchall()
    entailed_edges_df = pd.DataFrame(entailed_edge_data, columns=entailed_edge_columns)
    entailed_edges_df = entailed_edges_df.drop(columns=["predicate"])
    entailed_edges_df = entailed_edges_df.rename(columns={'object': OBJECT_COL, 'subject': SUBJECT_COL})
    entailed_edges_df = entailed_edges_df.drop_duplicates()
    entailed_edges_df = fix_identifiers(entailed_edges_df, columns=[SUBJECT_COL, OBJECT_COL])
    return entailed_edges_df


def _get_labels_table(cursor, ontology_name, include_disease_locations=False):
    # Get rdfs:label statements for ontology classes that are not deprecated
    labels_query = "SELECT * FROM statements WHERE predicate='rdfs:label' AND subject IN " + \
                   "(SELECT subject FROM statements WHERE predicate='rdf:type' AND object='owl:Class') " + \
                   "AND subject NOT IN " + \
                   "(SELECT subject FROM statements WHERE predicate='owl:deprecated' AND value='true')"
    cursor.execute(labels_query)
    labels_columns = [x[0] for x in cursor.description]
    labels_data = cursor.fetchall()
    labels_df = pd.DataFrame(labels_data, columns=labels_columns)
    labels_df = labels_df.drop(columns=["stanza", "predicate", "object", "datatype", "language", "graph"])
    labels_df = labels_df.rename(columns={'value': OBJECT_COL, 'subject': SUBJECT_COL})
    labels_df = labels_df.drop_duplicates(subset=[SUBJECT_COL])  # remove all but one label for each subject/term
    labels_df = labels_df[labels_df[SUBJECT_COL].str.startswith("_:") == False]  # remove blank nodes
    labels_df = fix_identifiers(labels_df, columns=[SUBJECT_COL])
    labels_df[OBJECT_COL] = labels_df[OBJECT_COL].str.strip()
    labels_df[IRI_COL] = labels_df[SUBJECT_COL].apply(get_iri)
    if include_disease_locations:
        labels_df[DISEASE_LOCATION_COL] = labels_df[SUBJECT_COL].apply(
            _get_disease_location_for_term, connection=cursor.connection, ontology=ontology_name)
    return labels_df


def _get_db_cross_references_table(cursor):
    cursor.execute("SELECT * FROM has_dbxref_statement")
    db_xrefs_columns = [x[0] for x in cursor.description]
    db_xrefs_data = cursor.fetchall()
    db_xrefs = pd.DataFrame(db_xrefs_data, columns=db_xrefs_columns)
    db_xrefs = db_xrefs.drop(columns=["stanza", "predicate", "object", "datatype", "language", "graph"])
    db_xrefs = db_xrefs.rename(columns={'value': OBJECT_COL, 'subject': SUBJECT_COL})
    db_xrefs = db_xrefs.drop_duplicates()
    db_xrefs = db_xrefs[db_xrefs[SUBJECT_COL].str.startswith("_:") == False]  # remove blank nodes
    db_xrefs = fix_identifiers(db_xrefs, columns=[SUBJECT_COL])
    return db_xrefs


def _get_synonyms_table(cursor):
    cursor.execute("SELECT * FROM has_exact_synonym_statement")
    synonyms_df_columns = [x[0] for x in cursor.description]
    synonyms_df_data = cursor.fetchall()
    synonyms_df = pd.DataFrame(synonyms_df_data, columns=synonyms_df_columns)
    synonyms_df = synonyms_df.drop(columns=["stanza", "predicate", "object", "datatype", "language", "graph"])
    synonyms_df = synonyms_df.rename(columns={'value': OBJECT_COL, 'subject': SUBJECT_COL})
    synonyms_df = synonyms_df.drop_duplicates()
    synonyms_df = synonyms_df[synonyms_df[SUBJECT_COL].str.startswith("_:") == False]  # remove blank nodes
    synonyms_df = fix_identifiers(synonyms_df, columns=[SUBJECT_COL])
    return synonyms_df


def get_iri(curie):
    if "DBR" in curie:
        term_id = curie.split(":")[1]
        return "http://dbpedia.org/resource/" + term_id
    else:
        return bioregistry.get_iri(curie, priority=IRI_PRIORITY_LIST)


def fix_identifiers(df, columns=()):
    for column in columns:
        df[column] = df[column].apply(get_curie_id_for_term)
    return df


def get_curie_id_for_term(term):
    if (not pd.isna(term)) and ("<" in term or "http" in term):
        term = term.replace("<", "")
        term = term.replace(">", "")
        if "," in term:
            tokens = term.split(",")
            curies = [_get_curie(token.strip()) for token in tokens]
            curies = ",".join(curies)
            return curies
        else:
            return _get_curie(term)
    return term


def _get_curie(term):
    curie = bioregistry.curie_from_iri(term)
    if curie is None:
        if "http://dbpedia.org" in term:
            return "DBR:" + term.rsplit('/', 1)[1]
        else:
            return term
    curie = curie.upper()
    if "OBO:" in curie:
        curie = curie.replace("OBO:", "obo:")
    if "NCBITAXON:" in curie:
        curie = curie.replace("NCBITAXON:", "NCBITaxon:")
    if "ORPHANET.ORDO" in curie:
        curie = curie.replace("ORPHANET.ORDO", "ORDO")
    return curie


def _get_disease_locations(connection, subject, table, ontology):
    if ontology == "EFO":
        predicate = "EFO:0000784"
    elif ontology == "NCIT":
        predicate = "NCIT:R101"
    else:
        # default to RO:0001025 ('located in') from Relations Ontology
        predicate = "RO:0001025"
    disease_location_query = f"SELECT object FROM {table} " \
                             f"WHERE predicate='{predicate}' AND subject='{subject}'"
    locations = pd.read_sql_query(disease_location_query, connection)
    locations = locations[~locations['object'].str.startswith("_")]  # remove rows where locations are blank nodes
    return locations["object"].tolist()


def _get_parents(connection, subject):
    parents_query = f"SELECT object FROM edge WHERE subject='{subject}' AND predicate='rdfs:subClassOf'"
    parents = pd.read_sql_query(parents_query, connection)
    parents = parents[~parents['object'].str.startswith("_")]  # remove blank nodes
    return parents["object"].tolist()


def _get_disease_location_for_term(subject, connection, ontology):
    queue = deque([subject])  # Initialize a queue to perform a BFS
    while queue:
        current_term = queue.popleft()
        # first check if a location is stated in existential restrictions (most common)
        locations = _get_disease_locations(connection, current_term, "owl_subclass_of_some_values_from", ontology)
        if locations:
            return locations[0] if len(locations) == 1 else ",".join(locations)
        else:
            # then check if a location is stated in universal restrictions
            locations = _get_disease_locations(connection, current_term, "owl_subclass_of_only_values_from", ontology)
            if locations:
                return locations[0] if len(locations) == 1 else ",".join(locations)
            else:
                # otherwise check if a parent has a stated disease location
                parents = [parent for parent in _get_parents(connection, current_term) if parent != "owl:Thing"]
                queue.extend(parents)
    return pd.NA


def save_table(df, output_filename, tables_output_folder):
    if not os.path.exists(tables_output_folder):
        os.makedirs(tables_output_folder)
    output_file = os.path.join(tables_output_folder, output_filename)
    df.to_csv(output_file, index=False, sep="\t", mode="w")


if __name__ == "__main__":
    get_semsql_tables_for_ontologies(ontologies=["EFO", "FOODON", "NCIT"], save_tables=True,
                                     single_table_for_all_ontologies=True, include_disease_locations=True)
