# plateforme.cli.utils.info
# -------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
Information utilities for the command line interface.
"""

import os
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.style import Style
from rich.text import Text

from plateforme.framework import VERSION

from .context import Context

TITLE = 'plateforme-cli'
"""The title of the command line interface."""


class Styles(Enum):
    """An enumeration of available style options."""

    COMMAND = Style(color="magenta", bold=True)
    """Style for command text."""

    TITLE = Style(color="blue", bold=True)
    """Style for title text."""

    VERSION = Style(dim=True)
    """Style for version text."""


console = Console()


def print_info(ctx: Context) -> None:
    """Print the version information."""
    emoji = '🏗  ' if supports_utf8() else ''
    title = Text(TITLE, style=Styles.TITLE.value)
    version = Text(VERSION, style=Styles.VERSION.value)
    info = Text.assemble(emoji, title, ' ', version)
    if ctx.invoked_subcommand:
        info.append(' → ', style='bold')
        info.append(ctx.invoked_subcommand, style=Styles.COMMAND.value)

    panel = Panel(info, border_style='dim', expand=False, padding=(0, 1))
    console.print(panel)


def supports_utf8() -> bool:
    """Whether the terminal supports UTF-8 encoding."""
    lang = os.environ.get('LANG', '').lower()
    if 'utf-8' in lang or 'utf8' in lang:
        return True
    return False
