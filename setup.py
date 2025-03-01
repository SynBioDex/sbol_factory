from setuptools import setup

# This version includes a patch that squelches logging in
# the opil factory, which was conflicting with logging in
# other modules

setup(name='sbol_factory',
      description='Ontology-driven data modeling',
      version='1.1.2',
      install_requires=[
            'sbol3>=1.0b12',  # Note: implicitly includes rdflib
            'sparqlwrapper>=1.8.5',
            'pyshacl>=0.13.3',
            'python-dateutil>=2.9',
            'requests',
            'graphviz',
            'pylatex',
            'PyPDF2'
      ],
      packages=['sbol_factory'],
      package_data={'sbol_factory': ['rdf/*', 'sparql/*']},
      include_package_data=True,
#      entry_points = {
#            'rdf.plugins.sparqleval': [
#            'custom_eval =  custom_eval:customEval',
#        ],
#      }
)
