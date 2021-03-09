import json
from collections import OrderedDict
from decimal import Decimal

from rdflib import Graph

class OpilJsonGenerator:
        '''This class shows how JSON can be generated from an RDF
        representation of an experimental request using the OPIL ontology. 
        '''

        def main(self):

            # Load Turtle files into a RDF graph
            print('Loading RDF files...')
            g = Graph()
            g.parse('rdf/sbol3.ttl', format='ttl')
            g.parse('rdf/opil.ttl', format='ttl')
            g.parse('rdf/sd2.ttl', format='ttl')
            g.parse('rdf/TimeSeriesProtocol.ttl', format='ttl')
            g.parse('rdf/YeastSTATES_1.0_Time_Series_Round_1.ttl', format='ttl')
            g.parse('rdf/om-2.0.rdf')

            # Load the various SPARQL queries
            metadata_query = self.load_sparql('sparql/metadata.sparql')
            ss_query = self.load_sparql('sparql/sampleSet.sparql')
            param_query = self.load_sparql('sparql/parameters.sparql')
            m_t_query = self.load_sparql('sparql/measurementType.sparql')
            rep_query = self.load_sparql('sparql/replicates.sparql')
            ft_query = self.load_sparql('sparql/fileType.sparql')
            var_comp_query = self.load_sparql('sparql/variableComponents.sparql')
            om_measure_query = self.load_sparql('sparql/omMeasures.sparql')
            strains_query = self.load_sparql('sparql/strains.sparql')
            media_query = self.load_sparql('sparql/media.sparql')
            timepoints_query = self.load_sparql('sparql/timepoints.sparql')
            
            # Execute SPARQL query to find all sample sets
            sample_set_iris = []
            for row in g.query(ss_query):
                sample_set_iris.append(row.ss)

            # Execute SPARQL query to find all parameters
            param_list = []
            parameters = {}
            for row in g.query(param_query):
                if not row.value is None:
                    parameters.update({row.paramName.value: row.value.value})
                elif not row.numericalValue is None and not row.unitName is None:
                    paramValue = str(row.numericalValue.value)
                    if len(row.unitName.value) > 0:
                        paramValue+= ':' + row.unitName.value
                    parameters.update({row.paramName.value: paramValue})
            param_list.append(parameters)

            # Generate the JSON
            print('Generating JSON...')
            experimental_request = OrderedDict()

            # Get the experimental request metadata
            for row in g.query(metadata_query):
                experimental_request.update({'name': row.name.value})
                experimental_request.update({'experiment_id': row.id.value})
                experimental_request.update({'challenge_problem': row.cp.value})
                experimental_request.update({'experiment_reference': row.ref.value})
                experimental_request.update({'experiment_reference_url': row.url.value})
                experimental_request.update({'experiment_version': row.ver.value})
                experimental_request.update({'lab': row.lab.value})

            experimental_request.update({'runs' : []})
            measurements = []

            # Iterate over sample sets
            for ss_iri in sample_set_iris:
                sample_set_dict = {}

                # Get measurement type for this sample set. Measurement types
                # are labels for the MeasurementType instances in the protocol
                # definition that correspond to the measurements for this sample set
                query = m_t_query.format(iri=ss_iri)
                for row in g.query(query):
                    sample_set_dict.update({'measurement_type': row.type.value})

                # Get number of replicates for this sample set
                query = rep_query.format(iri=ss_iri)
                for row in g.query(query):
                    sample_set_dict.update({'replicates': row.rep.value})

                # Get file types for this sample set
                query = ft_query.format(iri=ss_iri)
                file_types = []
                for row in g.query(query):
                    file_types.append(row.fileType.value)
                sample_set_dict.update({'file_type': file_types})

                # Get all VariableComponents for this SampleSet
                var_comp_iris = []
                query = var_comp_query.format(iri=ss_iri)
                for row in g.query(query):
                    var_comp_iris.append(row.varComp)

               # Iterate over VariableComponents
                for vc_iri in var_comp_iris:

                    # Get variants that are om:Measures with units and values
                    query = om_measure_query.format(iri=vc_iri)
                    for row in g.query(query):
                        variableName = row.label.value
                        if variableName in sample_set_dict:
                            numerical_values_and_units = sample_set_dict[variableName]
                        else:
                            numerical_values_and_units = []
                        measures = {}
                        if type(row.numericalValue.value) == Decimal:
                            numerical_value = float(row.numericalValue.value)
                        else:
                            numerical_value = row.numericalValue.value
                        measures.update({'value': numerical_value,
                                        'unit': row.unitName.value})
                        numerical_values_and_units.append(measures)
                        sample_set_dict.update({variableName: numerical_values_and_units})

                    # Get variants that are strains
                    query = strains_query.format(iri=vc_iri)
                    strains = []
                    for row in g.query(query):
                        variableName = row.label.value
                        strain = {}
                        strain.update({'sbh_uri': row.uri.value,
                                        'label': row.strain_label.value,
                                        'lab_id': row.lab_id.value})
                        strains.append(strain)
                        sample_set_dict.update({variableName: strains})

                    # Get variants that are media. Conform to the legacy JSON format
                    query = media_query.format(iri=vc_iri)
                    media = []
                    for row in g.query(query):
                        variableName = row.label.value
                        value = row.value.value
                        medium = { 'name' : { 'label': variableName }, 'value': value }
                        media.append(medium)
                    contents = []
                    if media:
                        contents.append(media)
                        sample_set_dict.update({'contents': contents})

                # Get the timepoints for this SampleSet's Measurement
                query = timepoints_query.format(iri=ss_iri)
                timepoints = []
                for row in g.query(query):
                    numerical_value = float(row.value.value)
                    timepoint_dict = {'value': numerical_value, 'unit': row.unitName.value}
                    timepoints.append(timepoint_dict)

                sample_set_dict.update({'timepoints': timepoints})
                measurements.append(sample_set_dict)

            experimental_request.get('runs').append({'measurements': measurements})

            # Add the parameters
            experimental_request.update({'parameters': param_list})

            print(json.dumps(experimental_request, indent=4, sort_keys=False))

        def load_sparql(self, file_path):
            with open(file_path, 'r') as query_file:
                # Strip newline characters and concatenate lines
                query = ' '.join([line.strip() for line in query_file])
            return query

if __name__ == "__main__":
    json_generator = OpilJsonGenerator()
    json_generator.main()
