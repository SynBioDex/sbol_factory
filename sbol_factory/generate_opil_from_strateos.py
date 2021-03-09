import argparse
import json
import sbol3
import opil

# Map of unit names to om:Unit instance IRIs
UNITS = {
    'microliter': 'http://www.ontology-of-units-of-measure.org/resource/om-2/microlitre',
    'nanometer' : 'http://www.ontology-of-units-of-measure.org/resource/om-2/nanometre',
    'hour' : 'http://www.ontology-of-units-of-measure.org/resource/om-2/hour'
}


class StrateosOpilGenerator():
    '''
    This class shows how OPIL can be generated from a Strateos protocol
    JSON schema. An OPIL representation of a Strateos protocol is
    essentially just a collection of parameters. The opil:name property
    is used for the parameter so-called dotnames.
    '''

    def __init__(self):
        pass

    def main(self):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "-i",
            "--input",
            dest="in_file",
            help="Input JSON file",
            default='/Users/rmarkelo/Documents/BBN/SD2/time_series_schema.json'
        )
        parser.add_argument(
            "-o",
            "--output",
            dest="out_file",
            help="Output OPIL Turtle file",
            default='TimeSeriesHTC.nt'
        )
        parser.add_argument(
            "-n",
            "--namespace",
            dest="namespace",
            help="Namespace for output file",
            default='http://strateos.com/'
        )
        parser.add_argument(
            "-p",
            "--protocol",
            dest="protocol_name",
            help="Protocol name",
            default='TimeSeriesHTC'
        )
        parser.add_argument(
            "--file_format",
            dest="file_format",
            help="Serialization format of RDF, e.g., nt, ttl",
            default='nt'
        )
        # Generate a dictionary from the command-line arguments
        args_dict = vars(parser.parse_args())

        # Get contents of JSON file
        with open(args_dict['in_file']) as f:
            document_dict = json.load(f)

        # Parse the JSON and return a SBOL document
        print('Generating OPIL from JSON file ', args_dict['in_file'])
        if 'id' in document_dict:
            protocol_id = document_dict['id']
        else:
            protocol_id = None
        if 'inputs' in document_dict:
            protocol_params = document_dict['inputs']
        else:
            protocol_params = document_dict  # TimeSeries schema
        document = self.parse_strateos_json(args_dict['namespace'],
                                            args_dict['protocol_name'], protocol_id,
                                            protocol_params)

        # Write out the document to a file
        document.bind('opil', opil.Query.OPIL)  # Set namespace prefix

        # Use Ntriples serialization to avoid rdflib issue with literal
        # data types that occurs with Turtle serialization
        document.write(args_dict['out_file'], file_format=args_dict['file_format'])

    def parse_strateos_json(self, namespace, protocol_name, protocol_id, inputs_dict):
        # Set the namespace for created instances
        sbol3.set_namespace(namespace)

        # Create the ProtocolInterface instance
        self.protocol = opil.ProtocolInterface(protocol_name)
        self.protocol.name = protocol_name
        if protocol_id:
            self.protocol.strateos_id = sbol3.TextProperty(self.protocol,
                                                           namespace + 'strateos_id', 0, 1,
                                                           None, protocol_id)

        # Create the document and add the ProtocolInterface to it
        self.doc = opil.Document()
        self.doc.add(self.protocol)

        # Create a list of Parameters
        self.param_list = []

        # Iterate through the top-level JSON objects and add Parameters to the list
        for param_name in inputs_dict:
            if type(inputs_dict[param_name]) is not dict:
                continue
            param_dict = inputs_dict[param_name]
            # Parameters are found in 'inputs' JSON objects
            # if 'inputs' in section_dict:
            #     inputs_dict = section_dict['inputs']

            # print(param_name)
            # The 'type' value indicates what Parameter subclass should be used.
            # Form the Strateos dotname from the section name and parameter name
            param_type = param_dict['type']
            self.handle_type(param_type, param_name, param_dict,
                             param_name)

        # Add parameters to ProtocolInterface
        try:
            self.protocol.has_parameter = self.param_list.copy()
            self.param_list = []
        except:
            print(self.param_list)
            raise

        return self.doc

    def handle_type(self, param_type, id_string, param_dict, dotname):
        '''
        The handle_type method selects the method for parsing the parameter JSON object
        based on its type field
        '''

        # Sanitize id
        if id_string[0].isnumeric():
            id_string = '_' + id_string

        if param_type == 'group' or param_type == 'group+':
            self.handle_group(id_string, param_dict, dotname)
        elif param_type == 'group-choice':
            self.handle_group_choice(id_string, param_dict, dotname)
        else:
            handler = StrateosOpilGenerator.type_handlers[param_type]
            param = handler(self, id_string, param_dict, dotname)
            if 'description' in param_dict.keys():
                param.description = param_dict['description']
            self.param_list.append(param)

    def handle_string(self, id_string, param_dict, dotname):
        param = opil.StringParameter(id_string)
        if 'label' in param_dict:
            param.name = param_dict['label']
        self.add_dotname(param, dotname)
        if 'default' in param_dict:
            default = opil.StringValue(id_string + '_default')
            default.value = param_dict['default']
            param.default_value = default
        if 'required' in param_dict:
            param.required = True
        return param

    def handle_integer(self, id_string, param_dict, dotname):
        param = opil.IntegerParameter(id_string)
        if 'label' in param_dict:
            param.name = param_dict['label']
        self.add_dotname(param, dotname)
        if 'default' in param_dict:
            default = opil.IntegerValue(id_string + '_default')
            default.value = param_dict['default']
            param.default_value = default
        if 'required' in param_dict:
            param.required = True
        return param

    def handle_measure(self, id_string, param_dict, dotname):
        '''
        Volume, length, and time types map to MeasureParameters
        Default values are MeasureValue instances with om:Measure
        instances carrying the numerical values and units
        '''
        param = opil.MeasureParameter(id_string)
        if 'label' in param_dict:
            param.name = param_dict['label']
        self.add_dotname(param, dotname)
        if 'default' in param_dict:
            SUCCESS = False
            i = 0
            while not SUCCESS:
                try:
                    default_instance = opil.MeasureValue(id_string + '_default' + str(i))
                    SUCCESS = True
                except ValueError:
                    i += 1
            default_value = param_dict['default']
            if isinstance(default_value, str):

                # Parse the string to get a number and unit name
                string_splits = param_dict['default'].split(':')
                value = float(string_splits[0])
                unit_iri = UNITS[string_splits[1]]
            else:

                # If the default value is a number, not a string,
                # then use the opil:pureNumber Unit instance
                value = default_value
                unit_iri = 'http://bioprotocols.org/opil/v1#pureNumber'
            measure_name = id_string + '_default_measure'
            measure = sbol3.Measure(value, unit_iri, identity=measure_name)
            default_instance.has_measure = measure
            param.default_value = default_instance
        if 'required' in param_dict:
            param.required = True
        return param

    def handle_bool(self, id_string, param_dict, dotname):
        param = opil.BooleanParameter(id_string)
        if 'label' in param_dict:
            param.name = param_dict['label']
        self.add_dotname(param, dotname)
        if 'default' in param_dict:
            default = opil.BooleanValue(id_string + '_default')
            default.value = param_dict['default']
            param.default_value = default
        if 'required' in param_dict:
            param.required = True
        return param

    def handle_group(self, id_string, param_dict, dotname):
        '''
        The group type is basically just a container for other
        input types
        '''
        if 'inputs' in param_dict:
            inputs_dict = param_dict['inputs']
            for key in inputs_dict:
                type = inputs_dict[key]['type']
                self.handle_type(type, key, inputs_dict[key], dotname + '.' + key)

    def handle_choice(self, id_string, param_dict, dotname):
        '''
        Choice type maps to Enumerated parameters
        '''
        param = opil.EnumeratedParameter(id_string)
        if 'label' in param_dict:
            param.name = param_dict['label']
        self.add_dotname(param, dotname)
        options_list = param_dict['options']
        allowed_values = []
        for option in options_list:
            allowed_values.append(option['value'])
        param.allowed_value = allowed_values
        if 'required' in param_dict:
            param.required = True
        return param

    def handle_group_choice(self, id_string, param_dict, dotname):
        '''
        The group-choice type contains an 'options' list of parameters
        '''
        params = []
        if 'options' in param_dict:
             dict_list = param_dict['options']
             param = self.handle_type('choice', id_string, param_dict, dotname)
             for d in dict_list:
                inputs_dict = d['inputs']
                for key in inputs_dict:
                    param_dict = inputs_dict[key]
                    type = param_dict['type']
                    # Use special syntax for choices
                    option_dotname = dotname + '.|.' + d['value'] + '.' + key
                    self.handle_type(type, key, param_dict, option_dotname)

    def add_dotname(self, param, dotname):
        # Add the dotname as an annotation property in Strateos namespace
        param.dotname = sbol3.TextProperty(param, 'http://strateos.com/dotname', 0, 1,
                                           None, dotname)


    # Mappings of JSON object types to methods. Not that aliquot and aliquot+ types
    # become string parameters
    type_handlers = {'choice': handle_choice, 'string': handle_string,
                     'volume': handle_measure, 'time': handle_measure,
                     'length': handle_measure, 'decimal': handle_measure,
                     'bool': handle_bool, 'integer': handle_integer,
                     'aliquot': handle_string, 'aliquot+': handle_string,
                     'container': handle_string}

if __name__ == "__main__":
    opil_generator = StrateosOpilGenerator()
    opil_generator.main()
