### Tests ###
#
# Pick some EFO terms, including:
#   (a) search_terms=['EFO:0005140'] (autoimmune disease) which has 5 direct and 311 inherited mappings
#   (b) search_terms=['EFO:0000001'] (experimental factor) has 0 direct and 27844 inherited mappings
#   (c) search_terms=['EFO:0009605','EFO:0005741'] (pancreas , infectious disease)

# 1) Check that the count of direct mappings reported in efo_labels table for term Q is the same as
#    the number of results obtained when doing the SQL query through the function:
#       query_database.resources_annotated_with_term(search_terms=Q,
#                                                    include_subclasses=False,
#                                                    direct_subclasses_only=False)
#       where Q = (a) and when Q = (b)
# TODO

# 2) Check that the count of inherited mappings reported in efo_labels table for term Q is the same as
#    the number of results obtained when doing the SQL query through the function:
#       query_database.resources_annotated_with_term(search_terms=Q,
#                                                    include_subclasses=True,
#                                                    direct_subclasses_only=False)
#       where Q = (a) and when Q = (b)
# TODO

# 3) Check that every value of MAPPED_TRAIT_CURIE in gwascatalog_metadata table also exists in the efo_labels table
#       if some CURIE is not in efo_labels, it is likely there is a naming discrepancy between CURIEs in the ontology
#       tables and CURIEs generated by text2term+bioregistry
# TODO

# 4) Check that the result set of a query with multiple search terms returns resources mapped to any one of the terms
# query_database.resources_annotated_with_term(search_terms=Q,
#                                              include_subclasses=True,
#                                              direct_subclasses_only=False)
#       where Q = (c)
# TODO