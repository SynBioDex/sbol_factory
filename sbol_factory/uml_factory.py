from .query import Query

import sbol3 as sbol

from math import inf
import posixpath
import os
import graphviz

class UMLFactory:
    """
    Class for generating UML diagrams from an ontology file
    """
    namespace_to_prefix = {}

    def __init__(self, ontology_path, ontology_namespace):
        self.namespace = ontology_namespace
        self.query = Query(ontology_path)
        for prefix, ns in self.query.graph.namespaces():
            UMLFactory.namespace_to_prefix[str(ns)] = prefix

    def generate(self, output_path):
        if not os.path.exists(output_path):
            os.mkdir(output_path)
        for class_uri in self.query.query_classes():
            if self.namespace not in class_uri:
                continue
            class_name = sbol.utils.parse_class_name(class_uri)
            dot = graphviz.Digraph(class_name)
            # dot.graph_attr['splines'] = 'ortho'

            # Order matters here, as the label for an entity
            # will depend on the last rendering method called
            self._generate(class_uri, self.draw_abstraction_hierarchy, dot)
            self._generate(class_uri, self.draw_class_definition, dot)
            dot_source_sanitized = dot.source.replace('\\\\', '\\')
            source = graphviz.Source(dot_source_sanitized)
            outfile = f'{class_name}_abstraction_hierarchy'
            source.render(posixpath.join(output_path, outfile))

    def _generate(self, class_uri, drawing_method_callback, dot_graph=None):
        if self.namespace not in class_uri:
            return ''
        superclass_uri = self.query.query_superclass(class_uri)
        self._generate(superclass_uri, drawing_method_callback, dot_graph)

        class_name = sbol.utils.parse_class_name(class_uri)

        # if class_name in globals().keys():
        #     return ''

        drawing_method_callback(class_uri, superclass_uri, dot_graph)

    def draw_abstraction_hierarchy(self, class_uri, superclass_uri, dot_graph=None):

        subclass_uris = self.query.query_subclasses(class_uri)
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
        property_uris = self.query.query_object_properties(class_uri)
        compositional_properties = self.query.query_compositional_properties(class_uri)
        associative_properties = [uri for uri in property_uris if uri not in
                                    compositional_properties]

        # Label associative properties
        for property_uri in associative_properties:
            if len(associative_properties) != len(set(associative_properties)):
                print(f'{property_uri} is found more than once')
            property_name = self.query.query_label(property_uri).replace(' ', '_')
            property_name = format_qname(property_uri)
            lower_bound, upper_bound = self.query.query_cardinality(property_uri, class_uri)
            if upper_bound == inf:
                upper_bound = '*'
            object_class_uri = self.query.query_property_datatype(property_uri, class_uri)
            arrow_label = f'{property_name} [{lower_bound}..{upper_bound}]'

        # Label compositional properties
        for property_uri in compositional_properties:
            if len(compositional_properties) != len(set(compositional_properties)):
                print(f'{property_uri} is found more than once')
            property_name = self.query.query_label(property_uri).replace(' ', '_')
            property_name = format_qname(property_uri)
            cardinality = self.query.query_cardinality(property_uri, class_uri)
            lower_bound, upper_bound = self.query.query_cardinality(property_uri, class_uri)
            if upper_bound == inf:
                upper_bound = '*'
            object_class_uri = self.query.query_property_datatype(property_uri, class_uri)
            arrow_label = f'{property_name} [{lower_bound}..{upper_bound}]'

        # Label datatype properties
        property_uris = self.query.query_datatype_properties(class_uri)
        for property_uri in property_uris:
            property_name = self.query.query_label(property_uri).replace(' ', '_')
            property_name = format_qname(property_uri)

            # Get the datatype of this property
            datatypes = self.query.query_property_datatype(property_uri, class_uri)
            if len(datatypes) == 0:
                continue
            if len(datatypes) > 1:  # This might indicate an error in the ontology
                raise
            # Get the cardinality of this datatype property
            lower_bound, upper_bound = self.query.query_cardinality(property_uri, class_uri)
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
        property_uris = self.query.query_object_properties(CLASS_URI)
        compositional_properties = self.query.query_compositional_properties(CLASS_URI)
        associative_properties = [uri for uri in property_uris if uri not in
                                    compositional_properties]

        # Initialize associative properties
        for property_uri in associative_properties:
            if len(associative_properties) != len(set(associative_properties)):
                print(f'{property_uri} is found more than once')
            property_name = self.query.query_label(property_uri).replace(' ', '_')
            property_name = format_qname(property_uri)
            lower_bound, upper_bound = self.query.query_cardinality(property_uri, class_uri)
            if upper_bound == inf:
                upper_bound = '*'
            object_class_uri = self.query.query_property_datatype(property_uri, CLASS_URI)[0]
            arrow_label = f'{property_name} [{lower_bound}..{upper_bound}]'
            create_association(dot, class_uri, object_class_uri, arrow_label)
            # self.__dict__[property_name] = sbol.ReferencedObject(self, property_uri, 0, upper_bound)

        # Initialize compositional properties
        for property_uri in compositional_properties:
            if len(compositional_properties) != len(set(compositional_properties)):
                print(f'{property_uri} is found more than once')
            property_name = self.query.query_label(property_uri).replace(' ', '_')
            property_name = format_qname(property_uri)
            lower_bound, upper_bound = self.query.query_cardinality(property_uri, class_uri)
            if upper_bound == inf:
                upper_bound = '*'
            object_class_uri = self.query.query_property_datatype(property_uri, CLASS_URI)[0]
            arrow_label = f'{property_name} [{lower_bound}..{upper_bound}]'
            create_composition(dot, class_uri, object_class_uri, arrow_label)

        # Initialize datatype properties
        property_uris = self.query.query_datatype_properties(CLASS_URI)
        for property_uri in property_uris:
            property_name = self.query.query_label(property_uri).replace(' ', '_')
            property_name = format_qname(property_uri)

            # Get the datatype of this property
            datatypes = self.query.query_property_datatype(property_uri, CLASS_URI)
            if len(datatypes) == 0:
                continue
            if len(datatypes) > 1:  # This might indicate an error in the ontology
                raise
            # Get the cardinality of this datatype property
            lower_bound, upper_bound = self.query.query_cardinality(property_uri, class_uri)
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
    qname = class_name
    for ns, prefix in UMLFactory.namespace_to_prefix.items():
        if ns in class_uri:
            qname = prefix + ':' + class_name
    #prefix = '' 
    #if str(Query.SBOL) in class_uri:
    #    prefix = 'sbol:'
    #elif str(Query.OM) in class_uri:
    #    prefix = 'om:'
    #qname = prefix + class_name
    return qname

def create_uml_record(dot_graph, class_uri, label):
    #class_name = sbol.utils.parse_class_name(class_uri)
    qname = format_qname(class_uri)
    node_name = qname.replace(':', '_')
    node_format = {
        'label' : None,
        'fontname' : 'Bitstream Vera Sans',
        'fontsize' : '8',
        'shape': 'record'
        }
    node_format['label'] = label
    dot_graph.node(node_name, **node_format)

def create_association(dot_graph, subject_uri, object_uri, label):
    subject_node = format_qname(subject_uri).replace(':', '_')
    object_node = format_qname(object_uri).replace(':', '_')
    association_relationship = {
            'label' : None,
            'arrowtail' : 'odiamond',
            'arrowhead' : 'vee',
            'fontname' : 'Bitstream Vera Sans',
            'fontsize' : '8',
            'dir' : 'both'
        }
    association_relationship['label'] = label
    dot_graph.edge(subject_node, object_node, **association_relationship)
    qname = format_qname(object_uri)
    label = '{' + qname + '|}'
    create_uml_record(dot_graph, object_uri, label)

def create_composition(dot_graph, subject_uri, object_uri, label):
    subject_node = format_qname(subject_uri).replace(':', '_')
    object_node = format_qname(object_uri).replace(':', '_')
    composition_relationship = {
            'label' : None,
            'arrowtail' : 'diamond',
            'arrowhead' : 'vee',
            'fontname' : 'Bitstream Vera Sans',
            'fontsize' : '8',
            'dir' : 'both'
        }
    composition_relationship['label'] = label
    dot_graph.edge(subject_node, object_node, **composition_relationship)
    qname = format_qname(object_uri)
    label = '{' + qname + '|}'
    create_uml_record(dot_graph, object_uri, label)

def create_inheritance(dot_graph, superclass_uri, subclass_uri):
    superclass_node = format_qname(superclass_uri).replace(':', '_')
    subclass_node = format_qname(subclass_uri).replace(':', '_')
    inheritance_relationship = {
            'label' : None,
            'arrowtail' : 'empty',
            'fontname' : 'Bitstream Vera Sans',
            'fontsize' : '8',
            'dir' : 'back'
        }
    dot_graph.edge(superclass_node, subclass_node, **inheritance_relationship)
    qname = format_qname(superclass_uri)
    label = '{' + qname + '|}'
    create_uml_record(dot_graph, superclass_uri, label)

