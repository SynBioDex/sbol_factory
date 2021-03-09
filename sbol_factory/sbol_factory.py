from .query import Query
from .shacl_validator import ShaclValidator

import sbol3 as sbol
from sbol3 import set_namespace, PYSBOL3_MISSING
from sbol3 import CombinatorialDerivation, Component, Measure, VariableFeature
# pySBOL extension classes are aliased because they are not present in SBOL-OWL
from sbol3 import CustomTopLevel as TopLevel
from sbol3 import CustomIdentified as Identified
from math import inf

import rdflib
import posixpath
import os
import argparse
import graphviz
#import logging

# Expose Document through the OPIL API
class Document(sbol.Document):

    def __init__(self):
        super(Document, self).__init__()
        self._validator = ShaclValidator()        

    def validate(self):
        conforms, results_graph, results_txt = self._validator.validate(self.graph())
        return ValidationReport(conforms, results_txt)


class ValidationReport():

    def __init__(self, is_valid, results_txt):
        self.is_valid = is_valid
        self.results = results_txt
        self.message = ''
        if not is_valid:
            i_message = results_txt.find('Message: ') + 9
            self.message = results_txt[i_message:]

    def __repr__(self):
        return self.message

#logging.basicConfig(level=logging.CRITICAL)


# def help():
#     #logging.getLogger().setLevel(logging.INFO)
#     print(OPILFactory.__doc__)



class OPILFactory():

    query = None

    def __init__(self, ontology_path, ontology_namespace, verbose=False):
        self.namespace = rdflib.URIRef(ontology_namespace)
        self.doc = ''
        docstring = ''
        OPILFactory.query = Query(ontology_path)
        for class_uri in OPILFactory.query.query_classes():
            docstring += self.generate(class_uri)
        if verbose:
            print(docstring)

    def generate(self, class_uri, log=''):

        if self.namespace not in class_uri: 
            return ''
        superclass_uri = OPILFactory.query.query_superclass(class_uri)
        log += self.generate(superclass_uri, log)  # Recurse into superclasses

        CLASS_URI = class_uri
        CLASS_NAME = sbol.utils.parse_class_name(class_uri)
        SUPERCLASS_NAME = sbol.utils.parse_class_name(superclass_uri)

        if CLASS_NAME in globals().keys():  # Abort if the class has already been generated
            return ''

        #Logging
        log += f'\n{CLASS_NAME}\n'
        log += '-' * (len(CLASS_NAME) - 2) + '\n'

        # Define constructor
        def __init__(self, identity=None, type_uri=CLASS_URI):
            Base = globals()[SUPERCLASS_NAME]
            if SUPERCLASS_NAME == 'CombinatorialDerivation':
                CombinatorialDerivation.__init__(self, identity, PYSBOL3_MISSING, type_uri=CLASS_URI)
            else:
                Base.__init__(self, identity=identity, type_uri=CLASS_URI)
            self.type_uri = CLASS_URI

            # Object properties can be either compositional or associative
            property_uris = OPILFactory.query.query_object_properties(CLASS_URI)
            compositional_properties = OPILFactory.query.query_compositional_properties(CLASS_URI)
            associative_properties = [uri for uri in property_uris if uri not in
                                        compositional_properties]

            # Initialize associative properties
            for property_uri in associative_properties:
                property_name = OPILFactory.query.query_label(property_uri).replace(' ', '_')
                lower_bound, upper_bound = OPILFactory.query.query_cardinality(property_uri, CLASS_URI)
                self.__dict__[property_name] = sbol.ReferencedObject(self, property_uri, lower_bound, upper_bound)

            # Initialize compositional properties
            for property_uri in compositional_properties:
                property_name = OPILFactory.query.query_label(property_uri).replace(' ', '_')
                lower_bound, upper_bound = OPILFactory.query.query_cardinality(property_uri, CLASS_URI)
                self.__dict__[property_name] = sbol.OwnedObject(self, property_uri, lower_bound, upper_bound)

            # Initialize datatype properties
            property_uris = OPILFactory.query.query_datatype_properties(CLASS_URI)
            for property_uri in property_uris:
                property_name = OPILFactory.query.query_label(property_uri).replace(' ', '_')

                # Get the datatype of this property
                datatypes = OPILFactory.query.query_property_datatype(property_uri, CLASS_URI)
                if len(datatypes) == 0:
                    continue
                if len(datatypes) > 1:  # This might indicate an error in the ontology
                    raise

                # Get the cardinality of this datatype property
                lower_bound, upper_bound = OPILFactory.query.query_cardinality(property_uri, CLASS_URI)
                if datatypes[0] == 'http://www.w3.org/2001/XMLSchema#string':
                    self.__dict__[property_name] = sbol.TextProperty(self, property_uri, lower_bound, upper_bound)
                elif datatypes[0] == 'http://www.w3.org/2001/XMLSchema#int':
                    self.__dict__[property_name] = sbol.IntProperty(self, property_uri, lower_bound, upper_bound)                    
                elif datatypes[0] == 'http://www.w3.org/2001/XMLSchema#boolean':
                    self.__dict__[property_name] = sbol.BooleanProperty(self, property_uri, lower_bound, upper_bound)
                elif datatypes[0] == 'http://www.w3.org/2001/XMLSchema#anyURI':
                    self.__dict__[property_name] = sbol.URIProperty(self, property_uri, lower_bound, upper_bound)

        # Instantiate metaclass
        attribute_dict = {}
        attribute_dict['__init__'] = __init__
        Class = type(CLASS_NAME, (globals()[SUPERCLASS_NAME],), attribute_dict)
        globals()[CLASS_NAME] = Class
        sbol.Document.register_builder(str(CLASS_URI), Class)

        # Print out properties -- this is for logging only
        property_uris = OPILFactory.query.query_object_properties(CLASS_URI)
        for property_uri in property_uris:
            property_name = OPILFactory.query.query_label(property_uri).replace(' ', '_')
            datatype = OPILFactory.query.query_property_datatype(property_uri, CLASS_URI)
            if len(datatype):
                datatype = sbol.utils.parse_class_name(datatype[0])
            else:
                datatype = None
            lower_bound, upper_bound = OPILFactory.query.query_cardinality(property_uri, CLASS_URI)
            log += f'\t{property_name}\t{datatype}\t{lower_bound}\t{upper_bound}\n'
        property_uris = OPILFactory.query.query_datatype_properties(CLASS_URI)
        for property_uri in property_uris:
            property_name = OPILFactory.query.query_label(property_uri).replace(' ', '_')
            datatype = OPILFactory.query.query_property_datatype(property_uri, CLASS_URI)
            if len(datatype):
                datatype = sbol.utils.parse_class_name(datatype[0])
            else:
                datatype = None
            lower_bound, upper_bound = OPILFactory.query.query_cardinality(property_uri, CLASS_URI)            
            log += f'\t{property_name}\t{datatype}\t{lower_bound}\t{upper_bound}\n'
        return log

class UMLFactory():

    def __init__(self, opil_factory, output_path):
        self.opil_factory = opil_factory
        OPILFactory.query = opil_factory.query
        for class_uri in OPILFactory.query.query_classes():
            if self.opil_factory.namespace not in class_uri:
                continue
            class_name = sbol.utils.parse_class_name(class_uri)
            dot = graphviz.Digraph(class_name)
            # dot.graph_attr['splines'] = 'ortho'

            # Order matters here, as the label for an entity
            # will depend on the last rendering method called
            self.generate(class_uri, self.draw_abstraction_hierarchy, dot)
            self.generate(class_uri, self.draw_class_definition, dot)
            source = graphviz.Source(dot.source.replace('\\\\', '\\'))
            outfile = f'{class_name}_abstraction_hierarchy'
            source.render(posixpath.join(output_path, outfile))

    def generate(self, class_uri, drawing_method_callback, dot_graph=None):
        if self.opil_factory.namespace not in class_uri:
            return ''
        superclass_uri = OPILFactory.query.query_superclass(class_uri)
        self.generate(superclass_uri, drawing_method_callback, dot_graph)

        class_name = sbol.utils.parse_class_name(class_uri)

        # if class_name in globals().keys():
        #     return ''

        drawing_method_callback(class_uri, superclass_uri, dot_graph)

    def draw_abstraction_hierarchy(self, class_uri, superclass_uri, dot_graph=None):

        subclass_uris = OPILFactory.query.query_subclasses(class_uri)
        if len(subclass_uris) <= 1:
            return 

        class_name = sbol.utils.parse_class_name(class_uri)
        if dot_graph:
            dot = dot_graph
        else:
            dot = graphviz.Digraph(class_name)

        qname = format_qname(class_uri)
        label = f'{qname}|'
        label = '{' + label + '}'  # graphviz syntax for record-style label
        create_uml_record(dot, class_uri, label)

        for uri in subclass_uris:
            subclass_name = sbol.utils.parse_class_name(uri)
            #create_inheritance(dot, class_uri, uri)
            label = self.label_properties(uri)
            create_uml_record(dot, uri, label)
            self.draw_class_definition(uri, class_uri, dot)
        # if not dot_graph:
        #     source = graphviz.Source(dot.source.replace('\\\\', '\\'))
        #     source.render(f'./uml/{class_name}_abstraction_hierarchy')
        return

    def label_properties(self, class_uri):
        class_name = sbol.utils.parse_class_name(class_uri)
        qname = format_qname(class_uri)
        label = f'{qname}|'

        # Object properties can be either compositional or associative
        property_uris = OPILFactory.query.query_object_properties(class_uri)
        compositional_properties = OPILFactory.query.query_compositional_properties(class_uri)
        associative_properties = [uri for uri in property_uris if uri not in
                                    compositional_properties]

        # Label associative properties
        for property_uri in associative_properties:
            if len(associative_properties) != len(set(associative_properties)):
                print(f'{property_uri} is found more than once')
            property_name = OPILFactory.query.query_label(property_uri).replace(' ', '_')
            property_name = format_qname(property_uri)
            lower_bound, upper_bound = OPILFactory.query.query_cardinality(property_uri, class_uri)
            if upper_bound == inf:
                upper_bound = '*'
            object_class_uri = OPILFactory.query.query_property_datatype(property_uri, class_uri)
            arrow_label = f'{property_name} [{lower_bound}..{upper_bound}]'

        # Label compositional properties
        for property_uri in compositional_properties:
            if len(compositional_properties) != len(set(compositional_properties)):
                print(f'{property_uri} is found more than once')
            property_name = OPILFactory.query.query_label(property_uri).replace(' ', '_')
            property_name = format_qname(property_uri)
            cardinality = OPILFactory.query.query_cardinality(property_uri, class_uri)
            lower_bound, upper_bound = OPILFactory.query.query_cardinality(property_uri, class_uri)
            if upper_bound == inf:
                upper_bound = '*'
            object_class_uri = OPILFactory.query.query_property_datatype(property_uri, class_uri)
            arrow_label = f'{property_name} [{lower_bound}..{upper_bound}]'

        # Label datatype properties
        property_uris = OPILFactory.query.query_datatype_properties(class_uri)
        for property_uri in property_uris:
            property_name = OPILFactory.query.query_label(property_uri).replace(' ', '_')
            property_name = format_qname(property_uri)

            # Get the datatype of this property
            datatypes = OPILFactory.query.query_property_datatype(property_uri, class_uri)
            if len(datatypes) == 0:
                continue
            if len(datatypes) > 1:  # This might indicate an error in the ontology
                raise
            # Get the cardinality of this datatype property
            lower_bound, upper_bound = OPILFactory.query.query_cardinality(property_uri, class_uri)
            if upper_bound == inf:
                upper_bound = '*'
            datatype = sbol.utils.parse_class_name(datatypes[0])
            if datatype == 'anyURI':
                datatype = 'URI'
            label += f'{property_name} [{lower_bound}..{upper_bound}]: {datatype}\\l'
        label = '{' + label + '}'  # graphviz syntax for record-style label
        return label

    def draw_class_definition(self, class_uri, superclass_uri, dot_graph=None):

        CLASS_URI = class_uri
        CLASS_NAME = sbol.utils.parse_class_name(class_uri)
        SUPERCLASS_NAME = sbol.utils.parse_class_name(superclass_uri)

        log = ''
        prefix = ''
        qname = format_qname(class_uri)
        label = f'{qname}|'

        if dot_graph:
            dot = dot_graph
        else:
            dot = graphviz.Digraph(CLASS_NAME)

        create_inheritance(dot, superclass_uri, class_uri)

        # Object properties can be either compositional or associative
        property_uris = OPILFactory.query.query_object_properties(CLASS_URI)
        compositional_properties = OPILFactory.query.query_compositional_properties(CLASS_URI)
        associative_properties = [uri for uri in property_uris if uri not in
                                    compositional_properties]

        # Initialize associative properties
        for property_uri in associative_properties:
            if len(associative_properties) != len(set(associative_properties)):
                print(f'{property_uri} is found more than once')
            property_name = OPILFactory.query.query_label(property_uri).replace(' ', '_')
            property_name = format_qname(property_uri)
            lower_bound, upper_bound = OPILFactory.query.query_cardinality(property_uri, class_uri)
            if upper_bound == inf:
                upper_bound = '*'
            object_class_uri = OPILFactory.query.query_property_datatype(property_uri, CLASS_URI)[0]
            arrow_label = f'{property_name} [{lower_bound}..{upper_bound}]'
            create_association(dot, class_uri, object_class_uri, arrow_label)
            # self.__dict__[property_name] = sbol.ReferencedObject(self, property_uri, 0, upper_bound)

        # Initialize compositional properties
        for property_uri in compositional_properties:
            if len(compositional_properties) != len(set(compositional_properties)):
                print(f'{property_uri} is found more than once')
            property_name = OPILFactory.query.query_label(property_uri).replace(' ', '_')
            property_name = format_qname(property_uri)
            lower_bound, upper_bound = OPILFactory.query.query_cardinality(property_uri, class_uri)
            if upper_bound == inf:
                upper_bound = '*'
            object_class_uri = OPILFactory.query.query_property_datatype(property_uri, CLASS_URI)[0]
            arrow_label = f'{property_name} [{lower_bound}..{upper_bound}]'
            create_composition(dot, class_uri, object_class_uri, arrow_label)

        # Initialize datatype properties
        property_uris = OPILFactory.query.query_datatype_properties(CLASS_URI)
        for property_uri in property_uris:
            property_name = OPILFactory.query.query_label(property_uri).replace(' ', '_')
            property_name = format_qname(property_uri)

            # Get the datatype of this property
            datatypes = OPILFactory.query.query_property_datatype(property_uri, CLASS_URI)
            if len(datatypes) == 0:
                continue
            if len(datatypes) > 1:  # This might indicate an error in the ontology
                raise
            # Get the cardinality of this datatype property
            lower_bound, upper_bound = OPILFactory.query.query_cardinality(property_uri, class_uri)
            if upper_bound == inf:
                upper_bound = '*'

            datatype = sbol.utils.parse_class_name(datatypes[0])
            if datatype == 'anyURI':
                datatype = 'URI'
            label += f'{property_name} [{lower_bound}..{upper_bound}]: {datatype}\\l'
        label = '{' + label + '}'  # graphviz syntax for record-style label
        create_uml_record(dot, class_uri, label)
        # if not dot_graph:
        #     source = graphviz.Source(dot.source.replace('\\\\', '\\'))
        #     source.render(f'./uml/{CLASS_NAME}')
        return log


def format_qname(class_uri):
    class_name = sbol.utils.parse_class_name(class_uri)
    prefix = ''
    if str(Query.SBOL) in class_uri:
        prefix = 'sbol:'
    elif str(Query.OM) in class_uri:
        prefix = 'om:'
    qname = prefix + class_name
    return qname

def create_uml_record(dot_graph, class_uri, label):
    class_name = sbol.utils.parse_class_name(class_uri)
    node_format = {
        'label' : None,
        'fontname' : 'Bitstream Vera Sans',
        'fontsize' : '8',
        'shape': 'record'
        }
    node_format['label'] = label
    dot_graph.node(class_name, **node_format)

def create_association(dot_graph, subject_uri, object_uri, label):
    subject_class = sbol.utils.parse_class_name(subject_uri)
    object_class = sbol.utils.parse_class_name(object_uri)
    association_relationship = {
            'label' : None,
            'arrowtail' : 'odiamond',
            'arrowhead' : 'vee',
            'fontname' : 'Bitstream Vera Sans',
            'fontsize' : '8',
            'dir' : 'both'
        } 
    association_relationship['label'] = label
    dot_graph.edge(subject_class, object_class, **association_relationship)
    qname = format_qname(object_uri)
    label = '{' + qname + '|}'
    create_uml_record(dot_graph, object_uri, label)

def create_composition(dot_graph, subject_uri, object_uri, label):
    subject_class = sbol.utils.parse_class_name(subject_uri)
    object_class = sbol.utils.parse_class_name(object_uri)
    composition_relationship = {
            'label' : None,
            'arrowtail' : 'diamond',
            'arrowhead' : 'vee',
            'fontname' : 'Bitstream Vera Sans',
            'fontsize' : '8',
            'dir' : 'both'
        } 
    composition_relationship['label'] = label
    dot_graph.edge(subject_class, object_class, **composition_relationship)
    qname = format_qname(object_uri)
    label = '{' + qname + '|}'
    create_uml_record(dot_graph, object_uri, label)

def create_inheritance(dot_graph, superclass_uri, subclass_uri):
    superclass = sbol.utils.parse_class_name(superclass_uri)
    subclass = sbol.utils.parse_class_name(subclass_uri)
    inheritance_relationship = {
            'label' : None,
            'arrowtail' : 'empty',
            'fontname' : 'Bitstream Vera Sans',
            'fontsize' : '8',
            'dir' : 'back'
        } 
    dot_graph.edge(superclass, subclass, **inheritance_relationship)
    qname = format_qname(superclass_uri)
    label = '{' + qname + '|}'
    create_uml_record(dot_graph, superclass_uri, label)


MODULE_PATH = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument(
    "-i",
    "--input",
    help="Input ontology",
)
parser.add_argument(
    "-n",
    "--namespace",
    help="Ontology namespace",
)
parser.add_argument(
    "-d",
    "--documentation",
    help="Output directory for UML"
)
parser.add_argument(
    "-v",
    "--verbose",
    help="Print data model as it is generated",
    default=False,
    action='store_true'
)

# Generate a dictionary from the command-line arguments
args_dict = vars(parser.parse_args())
if args_dict['input'] and not args_dict['namespace']:
    raise Exception('If specifying an input ontology, a namespace must also be specified')

# Import ontology
default_ontology = posixpath.join(MODULE_PATH, 'rdf/opil.ttl')
opil_path = posixpath.join(os.path.dirname(os.path.realpath(__file__)), 'rdf/opil.ttl')
if not args_dict['input']:
    opil_factory = OPILFactory(opil_path, Query.OPIL, args_dict['verbose'])
else:
    opil_factory = OPILFactory(args_dict['input'], args_dict['namespace'], args_dict['verbose'])

# Generate documentation
if args_dict['documentation']:
    OUTPUT_PATH = args_dict['documentation']
    if not os.path.exists(OUTPUT_PATH):
        os.mkdir(OUTPUT_PATH)
    UMLFactory(opil_factory, OUTPUT_PATH)
