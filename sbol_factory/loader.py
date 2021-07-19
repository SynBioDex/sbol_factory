import importlib.abc
import importlib.util


class OntologyLoader(importlib.abc.Loader):

    def __init__(self, symbol_table):
        super().__init__()
        self.symbol_table = symbol_table

    def create_module(self, spec):
        return None
    
    def exec_module(self, module):
        for symbol, obj in self.symbol_table.items():
            module.__dict__[symbol] = obj
        # TODO: delete symbol_table?  it is not needed after call to exec_module
