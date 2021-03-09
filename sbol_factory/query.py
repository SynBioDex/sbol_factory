import rdflib
import os
import posixpath
from math import inf

class Query():

    OWL = rdflib.URIRef('http://www.w3.org/2002/07/owl#')
    RDF = rdflib.URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#')
    SBOL = rdflib.URIRef('http://sbols.org/v2#')
    OPIL = rdflib.URIRef('http://bioprotocols.org/opil/v1#')
    RDFS = rdflib.URIRef('http://www.w3.org/2000/01/rdf-schema#')
    XSD = rdflib.URIRef('http://www.w3.org/2001/XMLSchema#')
    OM = rdflib.URIRef('http://www.ontology-of-units-of-measure.org/resource/om-2/')

    def __init__(self, ontology_path):
        graph = rdflib.Graph()
        graph.parse(ontology_path, format=rdflib.util.guess_format(ontology_path))
        graph.parse(posixpath.join(os.path.dirname(os.path.realpath(__file__)), 'rdf/sbol3.ttl'), format ='ttl')
        graph.namespace_manager.bind('sbol', Query.SBOL)
        graph.namespace_manager.bind('opil', Query.OPIL)
        graph.namespace_manager.bind('owl', Query.OWL)
        graph.namespace_manager.bind('rdfs', Query.RDFS)
        graph.namespace_manager.bind('rdf', Query.RDF)
        graph.namespace_manager.bind('xsd', Query.XSD)
        graph.namespace_manager.bind('om', Query.OM)
        self.graph = graph

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
            {{
                ?cls rdf:type owl:Class . 
            }}
            '''.format(str(Query.OPIL))
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
            raise Exception('{} has more than one superclass'.format(subclass))
        for row in response:
            superclass = str(row[0])
        return superclass

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

    def query_compositional_properties(self, class_uri):
        query = '''
            SELECT distinct ?property_uri
            WHERE 
            {{
                ?property_uri rdf:type owl:ObjectProperty .
                ?property_uri rdfs:subPropertyOf opil:compositionalProperty .
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
                ?property_uri rdfs:subPropertyOf opil:compositionalProperty .
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
        # The OPIL ontology does not explicitly specify cardinality restrictions
        # for every property, so some assumptions about defaults must be made
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
        query = '''
            SELECT distinct ?datatype
            WHERE 
            {{
                <{}> rdfs:domain <{}> .
                <{}> rdfs:range ?datatype 
            }}
            '''.format(property_uri, class_uri, property_uri)    
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