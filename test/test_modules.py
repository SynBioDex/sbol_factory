import unittest
import os, sys

from sbol_factory import SBOLFactory


class TestOntologyToModule(unittest.TestCase):

    def test_ontology_to_module(self):
        SBOLFactory(locals(),
                          os.path.join(os.path.dirname(os.path.realpath(__file__)),
                          'test_files/test-modules.ttl'),
                          'http://bioprotocols.org/uml#')
        self.assertTrue('uml' in sys.modules)
        SBOLFactory(locals(),
                    os.path.join(os.path.dirname(os.path.realpath(__file__)),
                    'test_files/test-modules.ttl'),
                    'http://bioprotocols.org/paml#')
        self.assertTrue('paml' in sys.modules)
        import uml
        import paml

    def test_import(self):
        self.assertTrue('uml' in sys.modules)
        import uml

if __name__ == '__main__':
    unittest.main()
