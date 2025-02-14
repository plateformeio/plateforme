"""
FIXME: Add mypy plugin

from mypy.plugin import Plugin, ClassDefContext
from mypy.nodes import TypeInfo, FuncDef, Argument, ARG_POS
from mypy.types import CallableType, TypeVarType, TypeVarDef, AnyType, TypeOfAny

class DynamicMethodPlugin(Plugin):
    def get_base_class_hook(self, fullname: str):
        if fullname == 'your_module.BaseResource':
            return self.dynamic_method_hook
        return None

    def dynamic_method_hook(self, ctx: ClassDefContext):
        # This method is called when a subclass of BaseResource is defined
        cls_info = ctx.cls.info

        # Iterate over annotations to find indexed fields
        for var in cls_info.names.values():
            if var.node and isinstance(var.node, Var) and isinstance(var.node.type, Instance):
                if var.node.type.type.fullname() == 'your_module.Field' and var.node.type.args[0].literal == True:
                    method_name = f'get_by_{var.name}'
                    # Create a method type here
                    method_type = self.create_method_type(var.name, var.node.type)
                    # Add the method to the TypeInfo of the Manager class
                    cls_info.names[method_name] = SymbolTableNode(MDEF, FuncDef(method_name, [], Block([]), method_type))

    def create_method_type(self, field_name: str, field_type: Type):
        # Create a method type for the dynamically added method
        # This is a simplified example and should be expanded to handle different field types and return types
        return_type = AnyType(TypeOfAny.unannotated)
        arg_type = field_type
        arg = Argument(Var('value', arg_type), arg_type, None, ARG_POS)
        func_type = CallableType([arg], [ARG_POS], [None], return_type, TypeVarDef('R', 'R', 1, [], return_type))
        return func_type

def plugin(version):
    return DynamicMethodPlugin
"""
