from .query import Query
from .shacl_validator import ShaclValidator

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
#     print(SBOLFactory.__doc__)



class SBOLFactory():

    query = None

    def __init__(self, module_scope, ontology_path, ontology_namespace, verbose=False):
        self.namespace = rdflib.URIRef(ontology_namespace)
        self.symbol_table = module_scope
        self.doc = ''
        docstring = ''
        SBOLFactory.query = Query(ontology_path)
        for class_uri in SBOLFactory.query.query_classes():
            docstring += self.generate(class_uri)
        if verbose:
            print(docstring)

    def generate(self, class_uri, log=''):

        if self.namespace not in class_uri: 
            return ''
        superclass_uri = SBOLFactory.query.query_superclass(class_uri)
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
        def __init__(self, *args, **kwargs):

            # required_args = SBOLFactory.query.query_required_properties(CLASS_URI)
            # if len(args) != len(required_args):
            #     raise('TypeError: method() takes exactly 1 positional argument (2 given)')

            #     for arg in required_args:
            #         if arg not in kwargs:
            #             raise Exception(f'{arg} is a required argument' )

            # Object properties can be either compositional or associative
            property_uris = SBOLFactory.query.query_object_properties(CLASS_URI)
            compositional_properties = SBOLFactory.query.query_compositional_properties(CLASS_URI)
            associative_properties = [uri for uri in property_uris if uri not in
                                        compositional_properties]
            datatype_properties = SBOLFactory.query.query_datatype_properties(CLASS_URI)
            property_names = [SBOLFactory.query.query_label(uri) for uri in property_uris]
            property_names.extend([SBOLFactory.query.query_label(uri) for uri in datatype_properties])
            property_names = [name.replace(' ', '_') for name in property_names]
            base_kwargs = {kw: val for kw, val in kwargs.items() if kw not in property_names}
            if 'type_uri' not in base_kwargs:
                base_kwargs['type_uri'] = CLASS_URI
            Base = globals()[SUPERCLASS_NAME]
            Base.__init__(self, *args, **base_kwargs)
            if 'http://sbols.org/v3#' in superclass_uri and not superclass_uri == SBOL_TOP_LEVEL and not superclass_uri == SBOL_IDENTIFIED:
                if SBOLFactory.query.is_top_level(CLASS_URI):
                    self._rdf_types.append(SBOL_TOP_LEVEL)
                else:
                    self._rdf_types.append(SBOL_IDENTIFIED)

            # Initialize associative properties
            for property_uri in associative_properties:
                property_name = SBOLFactory.query.query_label(property_uri).replace(' ', '_')
                lower_bound, upper_bound = SBOLFactory.query.query_cardinality(property_uri, CLASS_URI)
                self.__dict__[property_name] = sbol.ReferencedObject(self, property_uri, lower_bound, upper_bound)

            # Initialize compositional properties
            for property_uri in compositional_properties:
                property_name = SBOLFactory.query.query_label(property_uri).replace(' ', '_')
                lower_bound, upper_bound = SBOLFactory.query.query_cardinality(property_uri, CLASS_URI)
                self.__dict__[property_name] = sbol.OwnedObject(self, property_uri, lower_bound, upper_bound)

            # Initialize datatype properties
            property_uris = SBOLFactory.query.query_datatype_properties(CLASS_URI)
            for property_uri in property_uris:
                property_name = SBOLFactory.query.query_label(property_uri).replace(' ', '_')
                # Get the datatype of this property
                datatypes = SBOLFactory.query.query_property_datatype(property_uri, CLASS_URI)
                if len(datatypes) == 0:
                    continue
                if len(datatypes) > 1:  # This might indicate an error in the ontology
                    raise

                # Get the cardinality of this datatype property
                lower_bound, upper_bound = SBOLFactory.query.query_cardinality(property_uri, CLASS_URI)
                if datatypes[0] == 'http://www.w3.org/2001/XMLSchema#string':
                    self.__dict__[property_name] = sbol.TextProperty(self, property_uri, lower_bound, upper_bound)
                elif datatypes[0] == 'http://www.w3.org/2001/XMLSchema#integer':
                    self.__dict__[property_name] = sbol.IntProperty(self, property_uri, lower_bound, upper_bound)                    
                elif datatypes[0] == 'http://www.w3.org/2001/XMLSchema#boolean':
                    self.__dict__[property_name] = sbol.BooleanProperty(self, property_uri, lower_bound, upper_bound)
                elif datatypes[0] == 'http://www.w3.org/2001/XMLSchema#anyURI':
                    self.__dict__[property_name] = sbol.URIProperty(self, property_uri, lower_bound, upper_bound)

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
        Class = type(CLASS_NAME, (globals()[SUPERCLASS_NAME],), attribute_dict)
        globals()[CLASS_NAME] = Class
        self.symbol_table[CLASS_NAME] = Class

        def builder(identity, type_uri):
            arg_names = SBOLFactory.query.query_required_properties(CLASS_URI)
            kwargs = {arg.replace(' ', '_'): PYSBOL3_MISSING for arg in arg_names}
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
        return log

class UMLFactory:

    def __init__(self, factory):
        self.factory = factory
        SBOLFactory.query = factory.query

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

