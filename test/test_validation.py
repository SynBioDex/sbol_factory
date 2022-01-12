import unittest
import sbol3
import test_files

print('**************')
print(sbol3.__file__)

class TestValidation(unittest.TestCase):
    def test_valid_document(self):
        # Set up the document
        doc = sbol3.Document()
        sbol3.set_namespace('https://example.org/test')
        # Add a few empty but valid elements
        doc.add(test_files.Behavior('Provision'))
        doc.add(sbol3.Sequence('genome'))
        doc.add(sbol3.Component('water',sbol3.SBO_SIMPLE_CHEMICAL))
        # confirm validity
        v = doc.validate()
        assert not v.errors and not v.warnings, "".join(str(e) for e in doc.validate().errors)

    def test_invalid_sbol(self):
        # Set up the document
        doc = sbol3.Document()
        sbol3.set_namespace('https://test.org/')
        # Add a few empty but valid elements
        doc.add(test_files.Behavior('Provision'))
        doc.add(sbol3.Sequence('genome'))
        doc.add(sbol3.Component('water',{})) # Add an element that's missing a required property
        # confirm non-validity
        v = doc.validate()
        assert len(v.errors) == 2, f'Expected 2 errors, found {len(v.errors)}'
        assert str(v.errors[0]) == 'https://test.org/water: Too few values for property types. Expected 1, found 0'
        assert str(v.errors[1]) == 'https://test.org/water: http://sbols.org/v3#type: Less than 1 values on <https://test.org/water>->sbol:type'
        assert not v.warnings, "".join(str(e) for e in doc.validate().warnings)

    def test_invalid_extension(self):
        # Set up the document
        doc = sbol3.Document()
        sbol3.set_namespace('https://test.org/')
        # Add a few empty but valid elements
        b = test_files.Behavior('Provision')
        doc.add(b)
        b.parameters.append(test_files.Parameter(name='spec'))
        doc.add(sbol3.Sequence('genome'))
        doc.add(sbol3.Component('water',sbol3.SBO_SIMPLE_CHEMICAL))
        # confirm non-validity
        v = doc.validate()
        assert len(v.errors) == 3, f'Expected 3 errors, found {len(v.errors)}'
        assert {str(e) for e in v.errors} == \
                {'https://test.org/Provision/Parameter1: Too few values for property direction. Expected 1, found 0',
                 'https://test.org/Provision/Parameter1: Too few values for property is_unique. Expected 1, found 0',
                 'https://test.org/Provision/Parameter1: Too few values for property is_ordered. Expected 1, found 0'}
        assert not v.warnings, "".join(str(e) for e in doc.validate().warnings)



if __name__ == '__main__':
    unittest.main()
