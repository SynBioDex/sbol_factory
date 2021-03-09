import argparse
from rdflib import Graph, plugin

class JsonLdWriter:
    ''' Reads in a RDF file in Turtle format and writes it out as JSON-LD
    '''
    def main(self):

        # Parse the arguments
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "-i",
            "--input",
            dest="input",
            help="Input Turtle file"
        )
        parser.add_argument(
            '-o',
            '--output',
            dest='output',
            help='Output JSON-LD file',
        )

        # Generate a dict from the command-line arguments
        args_dict = vars(parser.parse_args())

        # Load RDF files
        g = Graph()
        g.parse(args_dict['input'], format='ttl')

        # Define contexts
        context = {'@timeseries': 'http://bbn.com/synbio/sd2/timeseries#',
                   '@ncit': 'http://ncicb.nci.nih.gov/xml/owl/EVS/Thesaurus.owl#',
                   '@opil': 'http://bioprotocols.org/opil/v1#',
                   '@om' : 'http://www.ontology-of-units-of-measure.org/resource/om-2/',
                   '@rdfs' : 'http://www.w3.org/2000/01/rdf-schema#',
                   '@abox' : 'http://bbn.com/synbio/sd2/abox#',
                   '@xsd' : 'http://www.w3.org/2001/XMLSchema#',
                   '@sd2' : 'http://bbn.com/synbio/sd2#',
                   '@sbol3' : 'http://sbols.org/v3#',
                   '@owl' : 'http://www.w3.org/2002/07/owl#' }
        g.serialize(destination=args_dict['output'],
                    format='json-ld', context=context, indent=4)


if __name__ == "__main__":
    json_ls_writer = JsonLdWriter()
    json_ls_writer.main()
