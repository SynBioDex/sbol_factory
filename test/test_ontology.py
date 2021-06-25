import tempfile
import os
import unittest
import filecmp
import sbol3
from sbol_factory import SBOLFactory, UMLFactory
import posixpath

__factory__ = SBOLFactory(locals(),
                          posixpath.join(os.path.dirname(os.path.realpath(__file__)),
                                         'test_files', 'test-ontology.ttl'),
                          'http://bioprotocols.org/uml#')
__umlfactory__ = UMLFactory(__factory__)

# Functions monkey-patched into classes from the test ontology for user in the construction test
def behavior_add_parameter(self, name: str, param_type: str, direction: str, optional: bool = False):
    param = Parameter(name=name, type=param_type, direction=direction, is_ordered=True, is_unique=True)
    self.parameters.append(param)
    param.upper_value = LiteralInteger(value=1)  # all parameters are assumed to have cardinality [0..1] or 1 for now
    if optional:
        param.lower_value = LiteralInteger(value=0)
    else:
        param.lower_value = LiteralInteger(value=1)
    return param
Behavior.add_parameter = behavior_add_parameter  # Add to class via monkey patch

def behavior_add_input(self, name: str, param_type: str, optional=False):
    return self.add_parameter(name, param_type, 'http://bioprotocols.org/uml#in', optional)
Behavior.add_input = behavior_add_input  # Add to class via monkey patch


def behavior_add_output(self, name, param_type):
    return self.add_parameter(name, param_type, 'http://bioprotocols.org/uml#out')
Behavior.add_output = behavior_add_output  # Add to class via monkey patch


class TestOntologyActions(unittest.TestCase):
    def test_build_with_ontology(self):
        #############################################
        # Set up the document
        doc = sbol3.Document()
        sbol3.set_namespace('https://example.org/test')

        #############################################
        # Create the primitives
        print('Making primitives for test library')

        p = Behavior('Provision')
        p.description = 'Place a measured amount (mass or volume) of a specified component into a location.'
        p.add_input('resource', sbol3.SBOL_COMPONENT)
        p.add_input('destination', 'http://bioprotocols.org/paml#Location')
        p.add_input('amount', sbol3.OM_MEASURE)  # Can be mass or volume
        p.add_input('dispenseVelocity', sbol3.OM_MEASURE, True)
        p.add_output('samples', 'http://bioprotocols.org/paml#LocatedSamples')
        doc.add(p)

        p = Behavior('Transfer')
        p.description = 'Move a measured volume taken from a collection of source samples to a location'
        p.add_input('source', 'http://bioprotocols.org/paml#LocatedSamples')
        p.add_input('destination', 'http://bioprotocols.org/paml#Location')
        p.add_input('amount', sbol3.OM_MEASURE)  # Must be volume
        p.add_input('dispenseVelocity', sbol3.OM_MEASURE, True)
        p.add_output('samples', 'http://bioprotocols.org/paml#LocatedSamples')
        doc.add(p)

        print('Library construction complete')

        ########################################
        # Validate and write the document
        print('Validating and writing protocol')
        v = doc.validate()
        assert not v.errors and not v.warnings, "".join(str(e) for e in doc.validate().errors)

        temp_name = os.path.join(tempfile.gettempdir(), 'mini_library.nt')
        doc.write(temp_name, sbol3.SORTED_NTRIPLES)
        print(f'Wrote file as {temp_name}')

        comparison_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'test_files', 'mini_library.nt')
        print(f'Comparing against {comparison_file}')
        assert filecmp.cmp(temp_name, comparison_file), "Files are not identical"
        print('File identical with test file')

    def test_round_trip_with_ontology(self):
        original_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'test_files', 'mini_library.nt')
        doc = sbol3.Document()
        print(f'Reading test file {original_file}')
        doc.read(original_file, sbol3.SORTED_NTRIPLES)

        print('Validating and writing out')
        v = doc.validate()
        assert not v.errors and not v.warnings, "".join(str(e) for e in doc.validate().errors)

        temp_name = os.path.join(tempfile.gettempdir(), 'mini_library.nt')
        doc.write(temp_name, sbol3.SORTED_NTRIPLES)
        print(f'Wrote file as {temp_name}')

        print(f'Comparing against {original_file}')
        assert filecmp.cmp(temp_name, original_file), "Files are not identical"
        print('Written out file identical with original file')


if __name__ == '__main__':
    unittest.main()