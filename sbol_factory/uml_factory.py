from .query import Query

import sbol3 as sbol
import pylatex
import PyPDF2
if PyPDF2.__version__.split('.')[0] < '3':
   from PyPDF2 import PdfFileReader
else:
   # PdfFileReader is deprecated and was removed in PyPDF2 3.0.0. Use PdfReader instead.
   from PyPDF2 import PdfReader as PdfFileReader

import os
import graphviz
from math import inf
from collections import OrderedDict

GLOBALS = set()

class UMLFactory:
    """
    Class for generating UML diagrams from an ontology file
    """
    namespace_to_prefix = {}

    def __init__(self, ontology_path, ontology_namespace):
        self.namespace = ontology_namespace
        self.query = Query(ontology_path)
        self.tex = pylatex.Document()
        for prefix, ns in self.query.graph.namespaces():
            UMLFactory.namespace_to_prefix[str(ns)] = prefix
        self.prefix = UMLFactory.namespace_to_prefix[self.namespace]

    def generate(self, output_path):
        if not os.path.exists(output_path):
            os.mkdir(output_path)
        for class_uri in self.query.query_classes():
            # Don't try to document classes in the graph
            # that don't belong to this ontology specifically
            if self.namespace not in class_uri:
                continue
            print('Generating ' + class_uri)
            # Skip subclasses in the same ontology, since these
            # will be clustered into the same diagram as the super
            if self.namespace in self.query.query_superclass(class_uri):
                continue

            GLOBALS.add(class_uri)

            class_name = sbol.utils.parse_class_name(class_uri)
            dot = graphviz.Digraph(class_name)
            # dot.graph_attr['splines'] = 'ortho'

            superclass_uri = self.query.query_superclass(class_uri)
            create_inheritance(dot, superclass_uri, class_uri)

            # Order matters here, as the label for an entity
            # will depend on the last rendering method called
            self._generate(class_uri, self.draw_abstraction_hierarchy, 0, class_name, dot)
            self._generate(class_uri, self.draw_class_definition, 0, class_name, dot)

            dot_source_sanitized = dot.source.replace('\\\\', '\\')
            dot_source_sanitized = remove_duplicates(dot_source_sanitized)
            source = graphviz.Source(dot_source_sanitized)
            outfile = f'{class_name}_abstraction_hierarchy'
            source.render(os.path.join(output_path, outfile))
            outfile += '.pdf'
            width = 470  # default \textwidth of LaTeX document
            with open(os.path.join(output_path, outfile), 'rb') as pdf:
                if PyPDF2.__version__.split('.')[0] < '3':
                    # reader.getPage(pageNumber) is deprecated and was removed in PyPDF2 3.0.0. Use reader.pages[page_number] instead.
                    width = PdfFileReader(pdf).getPage(0).mediaBox[2]
                else:
                    width = PdfFileReader(pdf).pages[0].mediabox[2]

            self._generate(class_uri, self.write_class_definition, 0, class_name, output_path, width)

        fname_tex = f'{self.prefix}DataModel'
        self.tex.generate_tex(fname_tex)
        fname_tex += '.tex'
        with open(fname_tex, 'r') as f:
            tex_source = f.read()
        # Strip preamble
        opening_clause = '\\begin{document}'
        closing_clause = '\\end{document}'
        lpos = tex_source.find(opening_clause) + len(opening_clause)
        rpos = tex_source.find(closing_clause)
        tex_source = tex_source[lpos:rpos]
        with open(fname_tex, 'w') as f:
            f.write(tex_source)
        print(f'Wrote ./{fname_tex}')
        print(f'Wrote figures to {output_path}')

    def _generate(self, class_uri, drawing_method_callback, level, fig_ref,  *args):
        superclass_uri = self.query.query_superclass(class_uri)
        drawing_method_callback(class_uri, superclass_uri, level, fig_ref, *args)
        if class_uri in GLOBALS or class_uri in completed or 'sbol' in class_uri:
            return
        print(f'  Generating ' + class_uri)


        child_class_uris = [self.query.query_property_datatype(p, class_uri)[0] for p in self.query.query_compositional_properties(class_uri)]
        for uri in child_class_uris:
            self._generate(uri, drawing_method_callback, level, fig_ref, *args)

        subclass_uris = self.query.query_subclasses(class_uri)
        for uri in subclass_uris:
            level += 1
            self._generate(uri, drawing_method_callback, level, fig_ref, *args)


    def write_class_definition(self, class_uri, superclass_uri, header_level, fig_ref, output_path, figure_width):
        CLASS_URI = class_uri
        CLASS_NAME = sbol.utils.parse_class_name(class_uri)
        SUPERCLASS_NAME = sbol.utils.parse_class_name(superclass_uri)
        FIG_REF = fig_ref
        CMD1 = format_prefix(class_uri)
        CMD2 = format_prefix(superclass_uri)
        HEADER_LEVEL = 'subsection'
        if header_level == 2:
            HEADER_LEVEL = 'subsubsection'
        elif header_level == 3:
            HEADER_LEVEL = 'paragraph'
        elif header_level > 3:
            HEADER_LEVEL = 'subparagraph' 

        self.tex.append(pylatex.NoEscape(f"\{HEADER_LEVEL}{{{CLASS_NAME}}}"))
        self.tex.append(pylatex.NoEscape(f"\label{{sec:{self.prefix}:{CLASS_NAME}}}"))
        tex_description = self.format_description(class_uri)
        if tex_description:
            self.tex.append(pylatex.NoEscape(tex_description))
            self.tex.append(pylatex.NewLine())
            self.tex.append(pylatex.LineBreak())

        if HEADER_LEVEL == 'subsection':
            scaled_figure_width = figure_width / (470 / 0.7)
            if scaled_figure_width > 1.0:
                scaled_figure_width = 1.0
            with self.tex.create(pylatex.Figure(position='h!')) as figure:
                fname = os.path.join(output_path, f'{CLASS_NAME}_abstraction_hierarchy.pdf')
                figure.add_image(fname, width=pylatex.NoEscape(f'{scaled_figure_width}\\textwidth'))
                figure.add_caption(CLASS_NAME)
                self.tex.append(pylatex.NoEscape(f'\label{{fig:{CLASS_NAME}}}'))

        tex_description = f'The \{CMD1}{{{CLASS_NAME}}} class is shown in \\ref{{fig:{FIG_REF}}}. It is derived from \{CMD2}{{{SUPERCLASS_NAME}}}'
        subclasses = [sbol.utils.parse_class_name(p) for p in self.query.query_subclasses(CLASS_URI)]
        if len(subclasses):
            subclasses = [f'\{CMD1}{{{subclass}}}' for subclass in subclasses]
            tex_description += f' and includes the following specializations: ' + ', '.join(subclasses) + '. '
        else:
            tex_description += '.'
        self.tex.append(pylatex.NoEscape(tex_description))


        property_names = [sbol.utils.parse_class_name(p) for p in self.query.query_properties(CLASS_URI)]
        if len(property_names):
            property_names = [f'\{CMD1}{{{pname}}}' for pname in property_names]
            tex_description = f'This class includes the following properties: ' + ', '.join(property_names) + '. '
            self.tex.append(pylatex.NoEscape(tex_description))

        with self.tex.create(pylatex.Itemize()) as items:
            for property_uri in self.query.query_associative_properties(class_uri):
                lower_bound, upper_bound = self.query.query_cardinality(property_uri, class_uri)
                object_class_uri = self.query.query_property_datatype(property_uri, CLASS_URI)[0]
                PNAME = sbol.utils.parse_class_name(property_uri)
                CMD = format_prefix(property_uri)
                OPTIONALITY = 'REQUIRED' if lower_bound == 1 else 'OPTIONAL'
                OBJ_NAME = sbol.utils.parse_class_name(object_class_uri)
                PLURALITY = 'a URI reference to an associated object' if upper_bound == 1 else 'URI references to associated objects'
                tex_description = f'The \{CMD}{{{PNAME}}} property is {OPTIONALITY} and contains {PLURALITY} of type {OBJ_NAME}' 
                tex_description += self.query.query_comment(property_uri)
                items.add_item(pylatex.NoEscape(tex_description))
            for property_uri in self.query.query_compositional_properties(class_uri):
                lower_bound, upper_bound = self.query.query_cardinality(property_uri, class_uri)
                object_class_uri = self.query.query_property_datatype(property_uri, CLASS_URI)[0]
                PNAME = sbol.utils.parse_class_name(property_uri)
                CMD = format_prefix(property_uri)
                OPTIONALITY = 'REQUIRED' if lower_bound == 1 else 'OPTIONAL'
                OBJ_NAME = sbol.utils.parse_class_name(object_class_uri)
                PLURALITY = 'a child object' if upper_bound == 1 else 'child objects'
                tex_description = f'The \{CMD}{{{PNAME}}} property is {OPTIONALITY} that points to {PLURALITY} of type {OBJ_NAME}' 
                tex_description += self.query.query_comment(property_uri)
                items.add_item(pylatex.NoEscape(tex_description))

            # Datatype properties
            property_uris = self.query.query_datatype_properties(CLASS_URI)
            property_names = self.query.query_property_names(property_uris)
            for property_uri, property_name in zip(property_uris, property_names):
                # Get the datatype of this property
                datatypes = self.query.query_property_datatype(property_uri, CLASS_URI)
                if len(datatypes) == 0:
                    continue
                if len(datatypes) > 1:  # This might indicate an error in the ontology
                    raise
                # Get the cardinality of this datatype property
                lower_bound, upper_bound = self.query.query_cardinality(property_uri, class_uri)
                PNAME = sbol.utils.parse_class_name(property_uri)
                CMD = format_prefix(property_uri)
                DT = sbol.utils.parse_class_name(datatypes[0])
                if DT == 'anyURI':
                    DT = 'URI'
                OPTIONALITY = 'REQUIRED' if lower_bound == 1 else 'OPTIONAL'
                PLURALITY = 'has a singleton value' if upper_bound == 1 else 'may contain multiple values'
                tex_description = f'The \{CMD}{{{PNAME}}} property is {OPTIONALITY} and {PLURALITY} of type {DT}' 
                tex_description += self.query.query_comment(property_uri)
                items.add_item(pylatex.NoEscape(tex_description))
        return [output_path, figure_width]

    def draw_abstraction_hierarchy(self, class_uri, superclass_uri, header_level, fig_ref, dot_graph=None):


        #if len(subclass_uris) <= 1:
        #    return

        class_name = sbol.utils.parse_class_name(class_uri)
        if dot_graph:
            dot = dot_graph
        else:
            dot = graphviz.Digraph(class_name)

        qname = format_qname(class_uri)
        label = f'{qname}|'
        label = '{' + label + '}'  # graphviz syntax for record-style label
        create_uml_record(dot, class_uri, label)
        
        #superclass_uri = self.query.query_superclass(class_uri)
        #create_inheritance(dot, superclass_uri, class_uri)
        subclass_uris = self.query.query_subclasses(class_uri)
        for uri in subclass_uris:
            subclass_name = sbol.utils.parse_class_name(uri)
            create_inheritance(dot, class_uri, uri)
            label = self.label_properties(uri)
            create_uml_record(dot, uri, label)
            self.draw_class_definition(uri, class_uri, header_level, fig_ref, dot)
        return [dot_graph]

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

    def draw_class_definition(self, class_uri, superclass_uri, header_level, fig_ref, dot_graph=None):

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

        #create_inheritance(dot, superclass_uri, class_uri)

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
        return [dot_graph]

    def format_description(self, class_uri):
        tex_description = self.query.query_comment(class_uri)
        class_list = self.query.query_classes()
        for uri in class_list:
            prefix = format_prefix(uri)
            if prefix == '':
                continue
            class_name = sbol.utils.parse_class_name(uri)
            qname = format_qname(uri)
            tex_description = tex_description.replace(f' {qname} ', f' \\{prefix}{{{class_name}}} ')
            tex_description = tex_description.replace(f' {qname}.', f' \\{prefix}{{{class_name}}}.')
            tex_description = tex_description.replace(f' {qname},', f' \\{prefix}{{{class_name}}},')

            tex_description = tex_description.replace(f' {class_name} ', f' \\{prefix}{{{class_name}}} ')
            tex_description = tex_description.replace(f' {class_name}.', f' \\{prefix}{{{class_name}}}.')
            tex_description = tex_description.replace(f' {class_name},', f' \\{prefix}{{{class_name}}},')

        return tex_description
            

def format_qname(class_uri):
    class_name = sbol.utils.parse_class_name(class_uri)
    qname = class_name
    prefix = format_prefix(class_uri)
    if prefix:
        qname = prefix + ':' + class_name
    return qname


def format_prefix(class_uri):
    for ns, prefix in UMLFactory.namespace_to_prefix.items():
        if ns in class_uri:
            return prefix
    return ''
    

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
            'xlabel' : None,
            'arrowtail' : 'odiamond',
            'arrowhead' : 'vee',
            'fontname' : 'Bitstream Vera Sans',
            'fontsize' : '8',
            'dir' : 'both'
        }
    association_relationship['xlabel'] = label
    dot_graph.edge(subject_node, object_node, **association_relationship)
    qname = format_qname(object_uri)
    label = '{' + qname + '|}'
    create_uml_record(dot_graph, object_uri, label)

def create_composition(dot_graph, subject_uri, object_uri, label):
    subject_node = format_qname(subject_uri).replace(':', '_')
    object_node = format_qname(object_uri).replace(':', '_')
    composition_relationship = {
            'xlabel' : None,
            'arrowtail' : 'diamond',
            'arrowhead' : 'vee',
            'fontname' : 'Bitstream Vera Sans',
            'fontsize' : '8',
            'dir' : 'both'
        }
    composition_relationship['xlabel'] = label
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

def remove_duplicates(dot_source):
    d = OrderedDict()
    entries = dot_source.split('\n')
    for e in entries:
        d[e] = None
    dot_source = '\n'.join(list(d.keys()))
    return dot_source
