# plateforme.tools.mypy.main
# --------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides the mypy plugin for type checking Plateforme objects.
"""

from typing import Callable

from mypy.nodes import TypeInfo
from mypy.plugin import ClassDefContext, Plugin
from mypy.types import Instance
from pydantic.mypy import PydanticPlugin

BASETYPE_FULLNAME = 'plateforme.types.base.BaseType'


class PlateformePlugin(PydanticPlugin):
    """The mypy plugin for type checking Plateforme objects."""

    def get_base_class_hook(  # type: ignore
        self, fullname: str
    ) -> Callable[[ClassDefContext], None] | None:
        sym = self.lookup_fully_qualified(fullname)
        if sym and isinstance(sym.node, TypeInfo):  # pragma: no branch
            # No branching may occur if the mypy cache has not been cleared
            if any(base.fullname == BASETYPE_FULLNAME
                    for base in sym.node.mro):
                return self._plateforme_type_class_maker_callback  # type: ignore
        return super().get_base_class_hook(fullname)  # type: ignore

    def _plateforme_type_class_maker_callback(
        self, ctx: ClassDefContext
    ) -> bool:
        # Check and transform  info
        def check_info(info: TypeInfo, base: Instance, fullname: str) -> bool:
            if base.type == ctx.api.builtin_type(fullname).type:
                info.bases = [ctx.api.named_type(fullname, [])]
                return True
            return False
        # Process info
        info = ctx.cls.info
        for base in info.bases:
            if isinstance(base, Instance):
                if check_info(info, base, 'builtins.bool'):
                    return True
                if check_info(info, base, 'builtins.bytes'):
                    return True
                if check_info(info, base, 'builtins.float'):
                    return True
                if check_info(info, base, 'builtins.int'):
                    return True
                if check_info(info, base, 'builtins.str'):
                    return True
        return False


def plugin(version: str) -> type[Plugin]:
    """Return the plugin class for the given mypy version.

    Args:
        version: The mypy version string.

    Note:
        We might want to use this to print a warning if the mypy version being
        used is newer, or especially older, than we expect (or need).
    """
    return PlateformePlugin
