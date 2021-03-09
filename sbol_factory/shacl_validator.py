from rdflib import Graph
from pyshacl import validate
import os
import posixpath

def abs_path(relative_path):  # Expand path based on module installation directory
    return posixpath.join(os.path.dirname(os.path.realpath(__file__)), relative_path)

class ShaclValidator:

    def __init__(self):
        self.g = Graph()
        self.g.parse(abs_path('rdf/sbol3.ttl'), format='ttl')
        self.g.parse(abs_path('rdf/opil.ttl'), format='ttl')
        self.g.parse(abs_path('rdf/sd2.ttl'), format='ttl')
        self.g.parse(abs_path('rdf/om-2.0.rdf'))
        self.g.parse(abs_path('rdf/opil-shacl.shapes.ttl'), format='ttl')

    def main(self):

        # Load Turtle files into a RDF graph
        print('Loading RDF files...')

        #self.g.parse('rdf/TimeSeriesProtocol.ttl', format='ttl')
        self.g.parse(abs_path('../TimeSeriesHTC.ttl'), format='ttl')
        #self.g.parse('rdf/YeastSTATES_1.0_Time_Series_Round_1.ttl', format='ttl')
        self.g.parse('rdf/TestER.ttl', format='ttl')

        # Do the validation
        print('Validating graph...')
        conforms, results_graph, results_text = \
            validate(self.g, shacl_graph=None, ont_graph=None, inference='rdfs',
                     abort_on_error=False, meta_shacl=False,
                     advanced=True, debug=False)

        if conforms:
            print('Graph is valid')
        else:
            print('Graph is invalid:\n')
            print(results_text)

        # Query the results graph to find the problem instances
        # bad_things_query = self.load_sparql('sparql/badInstances.sparql')
        # query_results = results_graph.query(bad_things_query)

        # if query_results:
            # for row in query_results:
            #     print('{}: {}'.format(row.msg.value, row.bad))

    def load_sparql(self, file_path):
        with open(file_path, 'r') as query_file:
            # Strip newline characters and concatenate lines
            query = ' '.join([line.strip() for line in query_file])
        return query

    def validate(self, graph_to_validate):
        g = graph_to_validate + self.g
        return validate(g, shacl_graph=None, ont_graph=None,
                        inference='rdfs', abort_on_error=False, meta_shacl=False,
                        advanced=True, debug=False)


if __name__ == "__main__":
    validator = ShaclValidator()
    validator.main()
