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
        self.assertTrue(check_namespaces())
        SBOLFactory('uml',
                    os.path.join(os.path.dirname(os.path.realpath(__file__)), 'test_files/test-modules.ttl'),
                    'http://bioprotocols.org/uml#')
        self.assertTrue('uml' in sys.modules)
        self.assertTrue(check_namespaces())
        SBOLFactory('paml',
                    os.path.join(os.path.dirname(os.path.realpath(__file__)), 'test_files/test-modules.ttl'),
                    'http://bioprotocols.org/paml#')
        self.assertTrue('paml' in sys.modules)
        self.assertTrue(check_namespaces())
        import uml
        import paml
        uml.Activity('http://test.org/umlact')
        paml.BehaviorExecution('http://test.org/BX')

    def test_figure_generation(self):
        path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'test_files')
        SBOLFactory('uml', os.path.join(path, 'test-modules.ttl'), 'http://bioprotocols.org/uml#')
        figure_maker = UMLFactory(os.path.join(path, 'test-modules.ttl'), 'http://bioprotocols.org/uml#')
        # TODO: check whether generated figure is correct
        tmp = tempfile.mkdtemp()
        print(f'Exporting test figures into {tmp}')
        figure_maker.generate(tmp)
        dot_source_actual = ''
        with open(os.path.join(tmp, 'Activity_abstraction_hierarchy')) as dot_file:
            dot_source_actual = dot_file.read().replace(' ', '')
        with open(os.path.join(path, 'Activity_abstraction_hierarchy.dot')) as dot_file:
            dot_source_expected = dot_file.read().replace(' ', '')
        self.assertEqual(dot_source_actual, dot_source_expected) 

    def test_figure_generation2(self):
        # This figure includes compositional properties
        path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'test_files')
        SBOLFactory('minimal', os.path.join(path, 'test-minimal-ontology.ttl'), 'http://bioprotocols.org/test#')
        figure_maker = UMLFactory(os.path.join(path, 'test-minimal-ontology.ttl'), 'http://bioprotocols.org/test#')
        # TODO: check whether generated figure is correct
        tmp = tempfile.mkdtemp()
        print(f'Exporting test figures into {tmp}')
        figure_maker.generate(tmp)
        dot_source_actual = ''
        with open(os.path.join(tmp, 'Base_abstraction_hierarchy')) as dot_file:
            dot_source_actual = dot_file.read().replace(' ', '')
        with open(os.path.join(path, 'Base_abstraction_hierarchy.dot')) as dot_file:
            dot_source_expected = dot_file.read().replace(' ', '')
        self.assertEqual(dot_source_actual, dot_source_expected) 

def check_namespaces():
    prefixes = [p for p, ns in SBOLFactory.graph.namespaces()]
    if 'default1' in prefixes:
        print(prefixes)
        return False
    return True

if __name__ == '__main__':
    unittest.main()
