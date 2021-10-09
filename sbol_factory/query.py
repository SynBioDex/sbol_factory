import rdflib
import os
import posixpath
from math import inf
from sbol3 import SBOL_IDENTIFIED, SBOL_TOP_LEVEL, PROV_ACTIVITY, PROV_PLAN, PROV_AGENT

class Query():

    graph = None
    OWL = rdflib.URIRef('http://www.w3.org/2002/07/owl#')
    RDF = rdflib.URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#')
    SBOL = rdflib.URIRef('http://sbols.org/v3#')
    RDFS = rdflib.URIRef('http://www.w3.org/2000/01/rdf-schema#')
    XSD = rdflib.URIRef('http://www.w3.org/2001/XMLSchema#')
    OM = rdflib.URIRef('http://www.ontology-of-units-of-measure.org/resource/om-2/')
    PROVO = rdflib.URIRef('http://www.w3.org/ns/prov#')

    def __init__(self, ontology_path):
        if not Query.graph:
            Query.graph = rdflib.Graph()
            Query.graph.parse(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'rdf/sbolowl3.rdf'))
            Query.graph.parse(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'rdf/prov-o.owl'), format ='xml')
            Query.graph.namespace_manager.bind('sbol', Query.SBOL)
            Query.graph.namespace_manager.bind('rdfs', Query.RDFS)
            Query.graph.namespace_manager.bind('rdf', Query.RDF)
            Query.graph.namespace_manager.bind('xsd', Query.XSD)
            Query.graph.namespace_manager.bind('om', Query.OM)
            Query.graph.namespace_manager.bind('prov', Query.PROVO)

        Query.graph.parse(ontology_path, format=rdflib.util.guess_format(ontology_path))
        self.graph = Query.graph

    def query_base_class(self, cls):
        try:
            superclass = self.query_superclass(cls)
            return self.query_base_class(superclass)
        except Exception as e:
            return cls

    def query_base_classes(self):
        class_list = self.query_classes()
        base_classes = set()
        for cls in class_list:
            base_class = self.query_base_class(cls)
            base_classes.add(base_class)
        return list(base_classes)

    def query_classes(self):
        query = '''
            SELECT distinct ?cls 
            WHERE 
            {
                ?cls rdf:type owl:Class . 
            }
            '''
        response = self.graph.query(query)
        sbol_types = [str(row[0]) for row in response]
        return sbol_types

    def query_subclasses(self, superclass):
        query = '''
            SELECT distinct ?subclass 
            WHERE 
            {{
                ?subclass rdf:type owl:Class .
                ?subclass rdfs:subClassOf <{}>
            }}
            '''.format(superclass)
        response = self.graph.query(query)
        subclasses = [row[0] for row in response]
        return subclasses

    def query_superclass(self, subclass):
        query = '''
            SELECT distinct ?superclass 
            WHERE 
            {{
                ?superclass rdf:type owl:Class .
                <{}> rdfs:subClassOf ?superclass
            }}
            '''.format(subclass)
        response = self.graph.query(query)
        if len(response) == 0:
            raise Exception('{} has no superclass'.format(subclass))
        if len(response) > 1:
            for r in response:
                print(r)
            raise Exception('{} has more than one {} superclass {}'.format(subclass, response, len(response)))
        for row in response:
            superclass = str(row[0])
        return superclass

    def query_ancestors(self, class_uri):
        query = f'''
            SELECT distinct ?superclass
            WHERE 
            {{{{
                <{class_uri}> rdfs:subClassOf* ?superclass .
                ?superclass rdf:type owl:Class .
            }}}}
            '''
        response = self.graph.query(query)
        if len(response) == 0:
            raise Exception('{} has no ancestors'.format(subclass))
        return [str(row[0]) for row in response]


    def query_descendants(self, class_uri):
        query = f'''
            SELECT distinct ?descendant
            WHERE 
            {{{{
                ?descendant rdf:type owl:Class .
                ?descendant rdfs:subClassOf* <{class_uri}>
            }}}}
            '''
        response = self.graph.query(query)
        if len(response) == 0:
            raise Exception('{} has no superclass'.format(subclass))
        return [str(row[0]) for row in response]



    def query_object_properties(self, class_uri):
        query =     '''
            SELECT distinct ?property_uri
            WHERE 
            {{
                ?property_uri rdf:type owl:ObjectProperty .
                ?property_uri rdfs:domain/(owl:unionOf/rdf:rest*/rdf:first)* <{}>.
            }}
            '''.format(class_uri)
        response = self.graph.query(query)
        response = [str(row[0]) for row in response]
        property_types = response

        # The type of inherited properties are sometimes overridden 
        query = '''
            SELECT distinct ?property_uri
            WHERE 
            {{
                ?property_uri rdf:type owl:ObjectProperty .
                <{}> rdfs:subClassOf ?restriction .
                ?restriction owl:onProperty ?property_uri .
            }}
            '''.format(class_uri) 
        response = self.graph.query(query)
        response = [str(row[0]) for row in response]
        property_types.extend(response)
        return list(set(property_types))

    def query_associative_properties(self, class_uri):
        properties = self.query_object_properties(class_uri)
        compositional_properties = self.query_compositional_properties(class_uri)
        associative_property_uris = [uri for uri in properties if uri not in
                                    compositional_properties]
        return associative_property_uris

    def query_properties(self, class_uri):
        return self.query_datatype_properties(class_uri) + self.query_object_properties(class_uri)

    def query_property_names(self, property_uris):
        return [self.query_label(p).replace(' ', '_') for p in property_uris] 

    def query_compositional_properties(self, class_uri):
        query = '''
            SELECT distinct ?property_uri
            WHERE 
            {{
                ?property_uri rdf:type owl:ObjectProperty .
                ?property_uri rdfs:subPropertyOf sbol:directlyComprises .
                ?property_uri rdfs:domain/(owl:unionOf/rdf:rest*/rdf:first)* <{}>.
            }}
            '''.format(class_uri)

        response = self.graph.query(query)
        response = [str(row[0]) for row in response]
        property_types = response

        # The type of inherited properties are sometimes overridden 
        query = '''
            SELECT distinct ?property_uri
            WHERE 
            {{
                ?property_uri rdf:type owl:ObjectProperty .
                ?property_uri rdfs:subPropertyOf sbol:directlyComprises .
                <{}> rdfs:subClassOf ?restriction .
                ?restriction owl:onProperty ?property_uri .
            }}
            '''.format(class_uri)
        response = self.graph.query(query)
        response = [str(row[0]) for row in response]
        property_types.extend(response) 
        return list(set(property_types))

    def query_datatype_properties(self, class_uri):
        query =     '''
            SELECT distinct ?property_uri
            WHERE 
            {{
                ?property_uri rdf:type owl:DatatypeProperty .
                ?property_uri rdfs:domain/(owl:unionOf/rdf:rest*/rdf:first)* <{}>.
            }}
            '''.format(class_uri)
        response = self.graph.query(query)
        response = [str(row[0]) for row in response]
        property_types = response

        # The type of inherited properties are sometimes overridden 
        query = '''
            SELECT distinct ?property_uri
            WHERE 
            {{
                ?property_uri rdf:type owl:DatatypeProperty .
                <{}> rdfs:subClassOf ?restriction .
                ?restriction owl:onProperty ?property_uri .
            }}
            '''.format(class_uri) 
        response = self.graph.query(query)
        response = [str(row[0]) for row in response]
        property_types.extend(response)
        return list(set(property_types))

    def query_cardinality(self, property_uri, class_uri):
        lower_bound = 0
        upper_bound = inf
        query = '''
            SELECT distinct ?cardinality
            WHERE 
            {{{{
                <{}> rdfs:subClassOf ?restriction .
                ?restriction rdf:type owl:Restriction .
                ?restriction owl:onProperty <{}> .
                ?restriction {{}} ?cardinality .
            }}}}
            '''.format(class_uri, property_uri)
        response = self.graph.query(query.format('owl:minCardinality'))
        response = [str(row[0]) for row in response]
        if len(response):
            lower_bound = int(response[0])
        response = self.graph.query(query.format('owl:maxCardinality'))
        response = [str(row[0]) for row in response]
        if len(response):
            upper_bound = int(response[0])
        return (lower_bound, upper_bound)

    def query_property_datatype(self, property_uri, class_uri):
        # Check for a restriction first on a specific property of a specific class
        query = '''
            SELECT distinct ?datatype
            WHERE 
            {{
                <{}> rdfs:subClassOf ?restriction .
                ?restriction rdf:type owl:Restriction .
                ?restriction owl:allValuesFrom ?datatype .
                ?restriction owl:onProperty <{}> .
            }}
            '''.format(class_uri, property_uri)    
        response = self.graph.query(query)
        response = [str(row[0]) for row in response]
        datatypes = response
        if len(datatypes) > 1:
            raise Exception(f'Conflicting owl:allValuesFrom restrictions found for values of {property_uri} property')
        if len(datatypes) == 1:
            return datatypes
        # If no restrictions are found, then search for ranges.
        # Ranges are more permissive, so more than one can range for a property can be found
        # query = '''
        #     SELECT distinct ?datatype
        #     WHERE 
        #     {{
        #         <{}> rdfs:domain <{}> .
        #         <{}> rdfs:range ?datatype 
        #     }}
        #     '''.format(property_uri, class_uri, property_uri)   
        query = '''
            SELECT distinct ?datatype
            WHERE 
            {{
                <{}> rdfs:range ?datatype 
            }}
            '''.format(property_uri)   

        response = self.graph.query(query)
        response = [str(row[0]) for row in response]
        if len(datatypes) > 1:
            raise Exception(f'Multiple ranges found for {property_uri} property. '
                            'Please specify owl:allValuesFrom restrictions for each domain class')
        datatypes = response
        return datatypes

    def query_label(self, property_uri):
        query =     '''
            SELECT distinct ?property_name
            WHERE 
            {{
                <{}> rdfs:label ?property_name
            }}
            '''.format(property_uri)    
        response = self.graph.query(query)
        response = [str(row[0]) for row in response]
        if len(response) == 0:
            raise Exception(f'{property_uri} has no label')
        if len(response) > 1:
            raise Exception(f'{property_uri} has more than one label')
        property_name = response[0]
        return property_name

    def query_comment(self, uri):
        query =     '''
            SELECT distinct ?comment
            WHERE 
            {{
                <{}> rdfs:comment ?comment
            }}
            '''.format(uri)    
        response = self.graph.query(query)
        response = [str(row[0]) for row in response]
        if len(response) == 0:
            return ''
            #raise Exception(f'{uri} has no comment')
        if len(response) > 1:
            raise Exception(f'{uri} has more than one comment')
        property_name = response[0]
        return property_name

    def is_top_level(self, class_uri):
        query = '''
            SELECT ?type
            WHERE {
              ?type rdfs:subClassOf* sbol:TopLevel.
            }'''
        response = self.graph.query(query)
        response = [str(row[0]) for row in response]
        return class_uri in response

    def query_required_properties(self, class_uri):
        inherited_required = []

        # Currently we cannot perform inference on PROV-O classes.
        # See #22
        if class_uri != SBOL_IDENTIFIED and Query.PROVO not in class_uri:
            superclass_uri = self.query_superclass(class_uri)
            inherited_required = self.query_required_properties(superclass_uri)
        if class_uri == SBOL_TOP_LEVEL or class_uri == PROV_ACTIVITY or class_uri == PROV_AGENT or class_uri == PROV_PLAN:
            return ['identity']

        required = []
        properties = self.query_datatype_properties(class_uri)
        properties += self.query_object_properties(class_uri)
        for p in properties:
            lb, ub = self.query_cardinality(p, class_uri)
            if lb == 1:
                label = self.query_label(p)
                required.append(label)
        # Remove duplicate required arguments. This can happen if the ontology places
        # a restriction on the same property in both the superclass and subclass.
        required = [arg for arg in required if arg not in inherited_required]
        # if len(required) > 1:
        #     raise Exception(f'Required arguments must have an order specified.')
        inherited_required.extend(required)
        return inherited_required

    # def query_required_properties(self, class_uri, required=[]):
    #     if class_uri != SBOL_IDENTIFIED:
    #         superclass_uri = self.query_superclass(class_uri)
    #         required = self.query_required_properties(superclass_uri, required)
    #     if class_uri == SBOL_TOP_LEVEL:
    #         return ['identity']

    #     properties = self.query_datatype_properties(class_uri)
    #     properties += self.query_object_properties(class_uri)
    #     for p in properties:
    #         lb, ub = self.query_cardinality(p, class_uri)
    #         if lb == 1:
    #             label = self.query_label(p)
    #             required.append(label)
    #             print(label)
    #     return required

    def query_inheritance_hierarchy(self, class_uri):
        query = '''
            SELECT distinct ?superclass 
            WHERE 
            {{
                <{}> rdfs:subClassOf* ?superclass .
                ?superclass rdf:type owl:Class .
            }}
            '''.format(class_uri)
        response = self.graph.query(query)
        subclasses = [row[0] for row in response]
        return subclasses
