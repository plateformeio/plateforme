# plateforme.cli.utils.info
# -------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
Information utilities for the command line interface.
"""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from plateforme.framework import VERSION

from .context import Context
from .styles import Styles

console = Console()


def print_info(ctx: Context) -> None:
    """Print the version information."""
    title = Text('🏗  plateforme-cli', style=Styles.TITLE.value)
    version = Text(VERSION, style=Styles.VERSION.value)

    info = Text.assemble(title, ' ', version)

    if ctx.invoked_subcommand:
        info.append(' → ', style='bold')
        info.append(ctx.invoked_subcommand, style=Styles.COMMAND.value)

    panel = Panel(info, border_style='dim', expand=False, padding=(0, 1))

    console.print(panel)
