import unittest
import os
import sys
import tempfile

from sbol_factory import SBOLFactory, UMLFactory


class TestOntologyToModule(unittest.TestCase):

    def setUp(self):
        SBOLFactory.clear()

    def tearDown(self):
        SBOLFactory.clear()

    def test_ontology_to_module(self):
        SBOLFactory('uml',
                    os.path.join(os.path.dirname(os.path.realpath(__file__)), 'test_files/test-modules.ttl'),
                    'http://bioprotocols.org/uml#')
        self.assertTrue('uml' in sys.modules)
        SBOLFactory('paml',
                    os.path.join(os.path.dirname(os.path.realpath(__file__)), 'test_files/test-modules.ttl'),
                    'http://bioprotocols.org/paml#')
        self.assertTrue('paml' in sys.modules)
        import uml
        import paml
        uml.Activity('http://test.org/umlact')
        paml.BehaviorExecution('http://test.org/BX')

    def test_figure_generation(self):
        path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'test_files/test-modules.ttl')
        SBOLFactory('uml', path,'http://bioprotocols.org/uml#')
        figure_maker = UMLFactory(path,'http://bioprotocols.org/uml#')
        # TODO: check whether generated figure is correct
        tmp = tempfile.mkdtemp()
        print(f'Exporting test figures into {tmp}')
        figure_maker.generate(tmp)

if __name__ == '__main__':
    unittest.main()
