from .query import Query
from .shacl_validator import ShaclValidator
from .loader import OntologyLoader

import sbol3 as sbol
from sbol3 import set_namespace, PYSBOL3_MISSING, SBOL_TOP_LEVEL, SBOL_IDENTIFIED
from sbol3 import CombinatorialDerivation, Component, Measure, VariableFeature

# pySBOL extension classes are aliased because they are not present in SBOL-OWL
from sbol3 import CustomTopLevel as TopLevel
from sbol3 import CustomIdentified as Identified

from math import inf
import rdflib
import posixpath
import os
import sys
import argparse
import graphviz
import importlib


SBOL = 'http://sbols.org/v3#'
OM = 'http://www.ontology-of-units-of-measure.org/resource/om-2/'
PROVO = 'http://www.w3.org/ns/prov#'


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
#     print(SBOLFactory.__doc__)



class SBOLFactory():

    graph = rdflib.Graph()
    graph.parse(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'rdf/sbol3.ttl'), format ='ttl')
    graph.parse(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'rdf/prov-o.owl'), format ='xml')
    graph.namespace_manager.bind('sbol', Query.SBOL)
    graph.namespace_manager.bind('opil', Query.OPIL)
    graph.namespace_manager.bind('owl', Query.OWL)
    graph.namespace_manager.bind('rdfs', Query.RDFS)
    graph.namespace_manager.bind('rdf', Query.RDF)
    graph.namespace_manager.bind('xsd', Query.XSD)
    graph.namespace_manager.bind('om', Query.OM)
    graph.namespace_manager.bind('prov', Query.PROVO)

    # Prefixes are used to automatically generate module names
    namespace_to_prefix = {}

    def __new__(cls, module_name, ontology_path, ontology_namespace, verbose=False):
        SBOLFactory.graph.parse(ontology_path, format=rdflib.util.guess_format(ontology_path))
        for prefix, ns in SBOLFactory.graph.namespaces():
            SBOLFactory.namespace_to_prefix[str(ns)] = prefix
            # TODO: handle namespace with conflicting prefixes

        # Use ontology prefix as module name
        ontology_namespace = ontology_namespace
        SBOLFactory.query = Query(ontology_path)
        symbol_table = {}
        for class_uri in SBOLFactory.query.query_classes():
            symbol_table = SBOLFactory.generate(class_uri, symbol_table, ontology_namespace)

        spec = importlib.util.spec_from_loader(
            module_name,
            OntologyLoader(symbol_table)
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules[module_name] = module
        return module


    def __init__(self, namespace, module_scope, verbose):
        self.namespace = rdflib.URIRef(ontology_namespace)
        self.graph = SBOLFactory.graph
        self.symbol_table = module_scope
        self.doc = ''

    @staticmethod
    def generate(class_uri, symbol_table, ontology_namespace):
        log = ''
        if ontology_namespace not in class_uri: 
            return symbol_table

        # Recurse into superclass
        superclass_uri = SBOLFactory.query.query_superclass(class_uri)
        symbol_table = SBOLFactory.generate(superclass_uri, symbol_table, ontology_namespace)

        CLASS_URI = class_uri
        CLASS_NAME = sbol.utils.parse_class_name(class_uri)

        if SBOLFactory.get_constructor(class_uri, symbol_table):  # Abort if the class has already been generated
            return symbol_table

        Super = SBOLFactory.get_constructor(superclass_uri, symbol_table)
        if not Super:
            raise Exception('Superclass {} does not have a constructor'.format(superclass_uri))

        #Logging
        log += f'\n{CLASS_NAME}\n'
        log += '-' * (len(CLASS_NAME) - 2) + '\n'

        # Collect property information for constructor, cached outside for speed
        # Object properties can be either compositional or associative
        property_uris = SBOLFactory.query.query_object_properties(CLASS_URI)
        compositional_properties = SBOLFactory.query.query_compositional_properties(CLASS_URI)
        associative_properties = [uri for uri in property_uris if uri not in
                                  compositional_properties]
        datatype_properties = SBOLFactory.query.query_datatype_properties(CLASS_URI)
        property_names = [SBOLFactory.query.query_label(uri) for uri in property_uris]
        property_names.extend([SBOLFactory.query.query_label(uri) for uri in datatype_properties])
        property_names = [name.replace(' ', '_') for name in property_names]
        class_is_top_level = SBOLFactory.query.is_top_level(CLASS_URI)
        all_property_uris = property_uris + datatype_properties
        property_uri_to_name = {uri: SBOLFactory.query.query_label(uri).replace(' ', '_') for uri in all_property_uris}
        property_cardinalities = {uri: SBOLFactory.query.query_cardinality(uri, CLASS_URI) for uri in all_property_uris}
        property_datatypes = {uri: SBOLFactory.query.query_property_datatype(uri, CLASS_URI) for uri in datatype_properties}



        # Define constructor
        def __init__(self, *args, **kwargs):
            base_kwargs = {kw: val for kw, val in kwargs.items() if kw not in property_names}
            if 'type_uri' not in base_kwargs:
                base_kwargs['type_uri'] = CLASS_URI
            Super.__init__(self, *args, **base_kwargs)
            if 'http://sbols.org/v3#' in superclass_uri and not superclass_uri == SBOL_TOP_LEVEL and not superclass_uri == SBOL_IDENTIFIED:
                if class_is_top_level:
                    self._rdf_types.append(SBOL_TOP_LEVEL)
                else:
                    self._rdf_types.append(SBOL_IDENTIFIED)

            # Initialize associative properties
            for property_uri in associative_properties:
                property_name = property_uri_to_name[property_uri]
                lower_bound, upper_bound = property_cardinalities[property_uri]
                self.__dict__[property_name] = sbol.ReferencedObject(self, property_uri, lower_bound, upper_bound)

            # Initialize compositional properties
            for property_uri in compositional_properties:
                property_name = property_uri_to_name[property_uri]
                lower_bound, upper_bound = property_cardinalities[property_uri]
                self.__dict__[property_name] = sbol.OwnedObject(self, property_uri, lower_bound, upper_bound)

            # Initialize datatype properties
            for property_uri in datatype_properties:
                # TODO: Cache query information outside of constructor
                property_name = property_uri_to_name[property_uri]
                # Get the datatype of this property
                datatypes = property_datatypes[property_uri]
                if len(datatypes) == 0:
                    continue
                if len(datatypes) > 1:  # This might indicate an error in the ontology
                    raise

                # Get the cardinality of this datatype property
                lower_bound, upper_bound = property_cardinalities[property_uri]
                if datatypes[0] == 'http://www.w3.org/2001/XMLSchema#string':
                    self.__dict__[property_name] = sbol.TextProperty(self, property_uri, lower_bound, upper_bound)
                elif datatypes[0] == 'http://www.w3.org/2001/XMLSchema#integer':
                    self.__dict__[property_name] = sbol.IntProperty(self, property_uri, lower_bound, upper_bound)                    
                elif datatypes[0] == 'http://www.w3.org/2001/XMLSchema#boolean':
                    self.__dict__[property_name] = sbol.BooleanProperty(self, property_uri, lower_bound, upper_bound)
                elif datatypes[0] == 'http://www.w3.org/2001/XMLSchema#anyURI':
                    self.__dict__[property_name] = sbol.URIProperty(self, property_uri, lower_bound, upper_bound)
                elif datatypes[0] == 'http://www.w3.org/2001/XMLSchema#dateTime':
                    self.__dict__[property_name] = sbol.DateTimeProperty(self, property_uri, lower_bound, upper_bound)

            for kw, val in kwargs.items():
                if kw == 'type_uri':
                    continue
                if kw in self.__dict__:
                    try:
                        self.__dict__[kw].set(val)
                    except:
                        pass
                        # print(kw, val, type(self.__dict__[kw]))
                        # raise

        def accept(self, visitor):
            visitor_method = f'visit_{CLASS_NAME}'.lower()
            getattr(visitor, visitor_method)(self)

        # Instantiate metaclass
        attribute_dict = {}
        attribute_dict['__init__'] = __init__
        attribute_dict['accept'] = accept
        Class = type(CLASS_NAME, (Super,), attribute_dict)

        #globals()[CLASS_NAME] = Class
        #self.symbol_table[CLASS_NAME] = Class
        symbol_table[CLASS_NAME] = Class
        arg_names = SBOLFactory.query.query_required_properties(CLASS_URI)  # moved outside of builder for speed
        kwargs = {arg.replace(' ', '_'): PYSBOL3_MISSING for arg in arg_names}

        def builder(identity, type_uri):
            kwargs['identity'] = identity
            kwargs['type_uri'] = type_uri
            return Class(**kwargs)

        sbol.Document.register_builder(str(CLASS_URI), builder)

        # Print out properties -- this is for logging only
        property_uris = SBOLFactory.query.query_object_properties(CLASS_URI)
        for property_uri in property_uris:
            property_name = SBOLFactory.query.query_label(property_uri).replace(' ', '_')
            datatype = SBOLFactory.query.query_property_datatype(property_uri, CLASS_URI)
            if len(datatype):
                datatype = sbol.utils.parse_class_name(datatype[0])
            else:
                datatype = None
            lower_bound, upper_bound = SBOLFactory.query.query_cardinality(property_uri, CLASS_URI)
            log += f'\t{property_name}\t{datatype}\t{lower_bound}\t{upper_bound}\n'
        property_uris = SBOLFactory.query.query_datatype_properties(CLASS_URI)
        for property_uri in property_uris:
            property_name = SBOLFactory.query.query_label(property_uri).replace(' ', '_')
            datatype = SBOLFactory.query.query_property_datatype(property_uri, CLASS_URI)
            if len(datatype):
                datatype = sbol.utils.parse_class_name(datatype[0])
            else:
                datatype = None
            lower_bound, upper_bound = SBOLFactory.query.query_cardinality(property_uri, CLASS_URI)            
            log += f'\t{property_name}\t{datatype}\t{lower_bound}\t{upper_bound}\n'
        return symbol_table

    @staticmethod
    def get_constructor(class_uri, symbol_table):

        if class_uri == SBOL_IDENTIFIED:
            return sbol.CustomIdentified
        if class_uri == SBOL_TOP_LEVEL:
            return sbol.CustomTopLevel

        # First look in the module we are generating
        class_name = sbol.utils.parse_class_name(class_uri)
        if class_name in symbol_table:
            return symbol_table[class_name]

        # Look in submodule
        namespace = None
        if '#' in class_uri:
            namespace = class_uri[:class_uri.rindex('#')+1]
        elif '/' in class_uri:
            namespace = class_uri[:class_uri.rindex('/')+1]
        else:
            raise ValueError(f'Cannot parse namespace from {class_uri}. URI must use either / or # as a delimiter.')

        # Look in the sbol module 
        if namespace == SBOL or namespace == PROVO or namespace == OM:
            return sbol.__dict__[class_name]

        # Look in other ontologies
        module_name = SBOLFactory.namespace_to_prefix[namespace]
        if module_name in sys.modules and class_name in sys.modules[module_name].__dict__:
            return sys.modules[module_name].__dict__[class_name]

        #if class_name in globals():
        #    if class_name == 'BehaviorExecution':
        #        print('BehaviorExecution in globals')
        #    return globals()[class_name]
        return None



    @staticmethod
    def clear():
        Query.graph = None
        modules = []
        ontology_modules = []
        for name, module in sys.modules.items():
            modules.append((name, module))
        for name, module in modules:
            if '__loader__' in module.__dict__ and type(module.__loader__) is OntologyLoader:
                ontology_modules.append(name)
        for name in ontology_modules:
            del sys.modules[name]

    @staticmethod
    def delete(symbol):
        del globals()[symbol]

class UMLFactory:

    def __init__(self, factory):
        self.factory = factory

    def generate(self, output_path):
        if not os.path.exists(output_path):
            os.mkdir(output_path)
        for class_uri in SBOLFactory.query.query_classes():
            if self.factory.namespace not in class_uri:
                continue
            class_name = sbol.utils.parse_class_name(class_uri)
            dot = graphviz.Digraph(class_name)
            # dot.graph_attr['splines'] = 'ortho'

            # Order matters here, as the label for an entity
            # will depend on the last rendering method called
            self._generate(class_uri, self.draw_abstraction_hierarchy, dot)
            self._generate(class_uri, self.draw_class_definition, dot)
            source = graphviz.Source(dot.source.replace('\\\\', '\\'))
            outfile = f'{class_name}_abstraction_hierarchy'
            source.render(posixpath.join(output_path, outfile))

    def _generate(self, class_uri, drawing_method_callback, dot_graph=None):
        if self.factory.namespace not in class_uri:
            return ''
        superclass_uri = SBOLFactory.query.query_superclass(class_uri)
        self._generate(superclass_uri, drawing_method_callback, dot_graph)

        class_name = sbol.utils.parse_class_name(class_uri)

        # if class_name in globals().keys():
        #     return ''

        drawing_method_callback(class_uri, superclass_uri, dot_graph)

    def draw_abstraction_hierarchy(self, class_uri, superclass_uri, dot_graph=None):

        subclass_uris = SBOLFactory.query.query_subclasses(class_uri)
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
        property_uris = SBOLFactory.query.query_object_properties(class_uri)
        compositional_properties = SBOLFactory.query.query_compositional_properties(class_uri)
        associative_properties = [uri for uri in property_uris if uri not in
                                    compositional_properties]

        # Label associative properties
        for property_uri in associative_properties:
            if len(associative_properties) != len(set(associative_properties)):
                print(f'{property_uri} is found more than once')
            property_name = SBOLFactory.query.query_label(property_uri).replace(' ', '_')
            property_name = format_qname(property_uri)
            lower_bound, upper_bound = SBOLFactory.query.query_cardinality(property_uri, class_uri)
            if upper_bound == inf:
                upper_bound = '*'
            object_class_uri = SBOLFactory.query.query_property_datatype(property_uri, class_uri)
            arrow_label = f'{property_name} [{lower_bound}..{upper_bound}]'

        # Label compositional properties
        for property_uri in compositional_properties:
            if len(compositional_properties) != len(set(compositional_properties)):
                print(f'{property_uri} is found more than once')
            property_name = SBOLFactory.query.query_label(property_uri).replace(' ', '_')
            property_name = format_qname(property_uri)
            cardinality = SBOLFactory.query.query_cardinality(property_uri, class_uri)
            lower_bound, upper_bound = SBOLFactory.query.query_cardinality(property_uri, class_uri)
            if upper_bound == inf:
                upper_bound = '*'
            object_class_uri = SBOLFactory.query.query_property_datatype(property_uri, class_uri)
            arrow_label = f'{property_name} [{lower_bound}..{upper_bound}]'

        # Label datatype properties
        property_uris = SBOLFactory.query.query_datatype_properties(class_uri)
        for property_uri in property_uris:
            property_name = SBOLFactory.query.query_label(property_uri).replace(' ', '_')
            property_name = format_qname(property_uri)

            # Get the datatype of this property
            datatypes = SBOLFactory.query.query_property_datatype(property_uri, class_uri)
            if len(datatypes) == 0:
                continue
            if len(datatypes) > 1:  # This might indicate an error in the ontology
                raise
            # Get the cardinality of this datatype property
            lower_bound, upper_bound = SBOLFactory.query.query_cardinality(property_uri, class_uri)
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
        property_uris = SBOLFactory.query.query_object_properties(CLASS_URI)
        compositional_properties = SBOLFactory.query.query_compositional_properties(CLASS_URI)
        associative_properties = [uri for uri in property_uris if uri not in
                                    compositional_properties]

        # Initialize associative properties
        for property_uri in associative_properties:
            if len(associative_properties) != len(set(associative_properties)):
                print(f'{property_uri} is found more than once')
            property_name = SBOLFactory.query.query_label(property_uri).replace(' ', '_')
            property_name = format_qname(property_uri)
            lower_bound, upper_bound = SBOLFactory.query.query_cardinality(property_uri, class_uri)
            if upper_bound == inf:
                upper_bound = '*'
            object_class_uri = SBOLFactory.query.query_property_datatype(property_uri, CLASS_URI)[0]
            arrow_label = f'{property_name} [{lower_bound}..{upper_bound}]'
            create_association(dot, class_uri, object_class_uri, arrow_label)
            # self.__dict__[property_name] = sbol.ReferencedObject(self, property_uri, 0, upper_bound)

        # Initialize compositional properties
        for property_uri in compositional_properties:
            if len(compositional_properties) != len(set(compositional_properties)):
                print(f'{property_uri} is found more than once')
            property_name = SBOLFactory.query.query_label(property_uri).replace(' ', '_')
            property_name = format_qname(property_uri)
            lower_bound, upper_bound = SBOLFactory.query.query_cardinality(property_uri, class_uri)
            if upper_bound == inf:
                upper_bound = '*'
            object_class_uri = SBOLFactory.query.query_property_datatype(property_uri, CLASS_URI)[0]
            arrow_label = f'{property_name} [{lower_bound}..{upper_bound}]'
            create_composition(dot, class_uri, object_class_uri, arrow_label)

        # Initialize datatype properties
        property_uris = SBOLFactory.query.query_datatype_properties(CLASS_URI)
        for property_uri in property_uris:
            property_name = SBOLFactory.query.query_label(property_uri).replace(' ', '_')
            property_name = format_qname(property_uri)

            # Get the datatype of this property
            datatypes = SBOLFactory.query.query_property_datatype(property_uri, CLASS_URI)
            if len(datatypes) == 0:
                continue
            if len(datatypes) > 1:  # This might indicate an error in the ontology
                raise
            # Get the cardinality of this datatype property
            lower_bound, upper_bound = SBOLFactory.query.query_cardinality(property_uri, class_uri)
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

