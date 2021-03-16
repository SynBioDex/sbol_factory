# sbol_factory

The SBOLFactory provides a mechanism for automatically generating an interactive, object-oriented API from a declarative data model specification encoded in OWL. 

## Installation
The  `sbol_factory` package and its dependencies can be installed as follows:
```
pip install sbol_factory
```
Python 3 only is supported.

## SBOLFactory

The SBOLFactory module is an extension of the underlying [pySBOL](https://github.com/SynBioDex/pySBOL3) module. The SBOLFactory will generate an API that is an extension of the pySBOL API. Users who are already familiar with the pySBOL API will find the same patterns and conventions implemented through the SBOLFactory.

Import as follows:

```
import sbol_factory
```

The SBOLFactory will generate an API from an ontology specification ecoded with the Web Ontology Language (OWL). (A Turtle serialization of the OPIL ontology can be found in the 'rdf' directory.) The module's API is dynamically generated directly from this OWL specification immediately upon import of the module into the user's Python environment. The ontology specifies the Python classes, their attributes, their types, and their cardinality.

## Generating an API

To generate an API call the SBOLFactory constructor.  This constructor takes three arguments. The first is the `local()` method.  This tells the factory to populate the automatically generated class definitions into the local scope. The second argument provides the file name containing the ontology specification. The third argument provides the namespace for the ontology.

```
# Import ontology
__factory__ = SBOLFactory(locals(), 'opil.ttl', 'http://bioprotocols.org/opil/v1#')
```
