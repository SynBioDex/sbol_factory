import os
import posixpath
from sbol_factory import SBOLFactory, UMLFactory

# Import ontology here to make a "test_files" extension package for running tests on
SBOLFactory('uml',
            posixpath.join(os.path.dirname(os.path.realpath(__file__)), 'test-ontology.ttl'),
            'http://bioprotocols.org/uml#')
from uml import *

