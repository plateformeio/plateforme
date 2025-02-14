# plateforme.cli.utils.styles
# ---------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
Style utilities for the command line interface.
"""

from enum import Enum

from rich.style import Style


class Styles(Enum):
    """An enumeration of available style options."""

    COMMAND = Style(color="magenta", bold=True)
    """Style for command text."""

    TITLE = Style(color="blue", bold=True)
    """Style for title text."""

    VERSION = Style(dim=True)
    """Style for version text."""
