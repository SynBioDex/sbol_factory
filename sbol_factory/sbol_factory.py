from .query import Query
from .shacl_validator import ShaclValidator
from .loader import OntologyLoader

import sbol3 as sbol
from sbol3 import PYSBOL3_MISSING, SBOL_TOP_LEVEL, SBOL_IDENTIFIED

# pySBOL extension classes are aliased because they are not present in SBOL-OWL
from sbol3 import CustomTopLevel as TopLevel
from sbol3 import CustomIdentified as Identified

import rdflib
import os
import sys
import importlib
import logging


SBOL = 'http://sbols.org/v3#'
OM = 'http://www.ontology-of-units-of-measure.org/resource/om-2/'
PROVO = 'http://www.w3.org/ns/prov#'


logging.basicConfig()
LOGGER = logging.getLogger(__name__)

# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(logging.Formatter('%(message)s'))
LOGGER.addHandler(ch)
ch2 = logging.StreamHandler()
ch2.setLevel(logging.ERROR)
ch2.setFormatter(logging.Formatter('[%(levelname)s] %(filename)s %(lineno)d: %(message)s'))
LOGGER.addHandler(ch2)


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


class SBOLFactory():

    graph = rdflib.Graph()
    graph.parse(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'rdf/sbolowl3.rdf'), format ='xml')
    graph.parse(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'rdf/prov-o.owl'), format ='xml')
    graph.namespace_manager.bind('sbol', Query.SBOL)
    graph.namespace_manager.bind('owl', Query.OWL)
    graph.namespace_manager.bind('rdfs', Query.RDFS)
    graph.namespace_manager.bind('rdf', Query.RDF)
    graph.namespace_manager.bind('xsd', Query.XSD)
    graph.namespace_manager.bind('om', Query.OM)
    graph.namespace_manager.bind('prov', Query.PROVO)

    # Prefixes are used to automatically generate module names
    namespace_to_prefix = {}

    def __new__(cls, module_name, ontology_path, ontology_namespace, verbose=False):
        if verbose is False:
            logging.disable(logging.INFO)
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
        LOGGER.info(f'\n{CLASS_NAME}\n')
        LOGGER.info('-' * (len(CLASS_NAME) - 2) + '\n')

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
            LOGGER.info(f'\t{property_name}\t{datatype}\t{lower_bound}\t{upper_bound}\n')
        property_uris = SBOLFactory.query.query_datatype_properties(CLASS_URI)
        for property_uri in property_uris:
            property_name = SBOLFactory.query.query_label(property_uri).replace(' ', '_')
            datatype = SBOLFactory.query.query_property_datatype(property_uri, CLASS_URI)
            if len(datatype):
                datatype = sbol.utils.parse_class_name(datatype[0])
            else:
                datatype = None
            lower_bound, upper_bound = SBOLFactory.query.query_cardinality(property_uri, CLASS_URI)            
            LOGGER.info(f'\t{property_name}\t{datatype}\t{lower_bound}\t{upper_bound}\n')
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


