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
        dot_source_actual = ''
        with open(os.path.join(tmp, 'Activity_abstraction_hierarchy')) as dot_file:
            dot_source_actual = dot_file.read()
        dot_source_expected = '''digraph Activity {
	prov_Activity -> uml_Activity [arrowtail=empty dir=back fontname="Bitstream Vera Sans" fontsize=8]
	prov_Activity [label="{prov:Activity|}" fontname="Bitstream Vera Sans" fontsize=8 shape=record]
	uml_Activity [label="{uml:Activity|}" fontname="Bitstream Vera Sans" fontsize=8 shape=record]
	uml_Activity -> paml_BehaviorExecution [arrowtail=empty dir=back fontname="Bitstream Vera Sans" fontsize=8]
	paml_BehaviorExecution [label="{paml:BehaviorExecution|}" fontname="Bitstream Vera Sans" fontsize=8 shape=record]
}\n'''
        self.assertEqual(dot_source_actual, dot_source_expected) 


if __name__ == '__main__':
    unittest.main()
