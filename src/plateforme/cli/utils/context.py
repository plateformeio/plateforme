# plateforme.cli.utils.context
# ----------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
Context utilities for the command line interface.
"""

import typer
from typing_extensions import TypedDict

from plateforme.core.projects import ProjectInfo


class ContextObj(TypedDict, total=False):
    project: ProjectInfo | None


class Context(typer.Context):
    obj: ContextObj
