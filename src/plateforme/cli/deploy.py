# plateforme.cli.deploy
# ---------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
The deploy command line interface.
"""

import typer

from .utils.context import Context
from .utils.logging import logger

app = typer.Typer()


@app.command()
def deploy(ctx: Context) -> None:
    """Deploy the plateforme project."""
    logger.info(f"Deploying project...")
