import os
import posixpath
from sbol_factory import SBOLFactory, UMLFactory

# Import ontology here to make a "test_files" extension package for running tests on
__factory__ = SBOLFactory(locals(),
                          posixpath.join(os.path.dirname(os.path.realpath(__file__)), 'test-ontology.ttl'),
                          'http://bioprotocols.org/uml#')
__umlfactory__ = UMLFactory(__factory__)

