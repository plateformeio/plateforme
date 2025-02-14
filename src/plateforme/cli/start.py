# plateforme.cli.start
# --------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
The start command line interface.
"""

import os
import subprocess

import typer

from .utils.context import Context
from .utils.logging import logger

app = typer.Typer()


@app.callback(invoke_without_command=True)
def start(
    ctx: Context,
    app: str = typer.Argument(
        'default',
        help=(
            "The application to start. If not provided, it will start the "
            "default application."
        ),
    ),
) -> None:
    """Start the plateforme project application."""
    logger.info(f"Starting application... (from {ctx.obj['project']})")

    project = ctx.obj['project']
    if not project:
        logger.error("No project found")
        raise typer.Exit(code=1)
    if not project.apps or app not in project.apps:
        logger.error(f"No application configuration found for {app!r}")
        raise typer.Exit(code=1)

    config = project.apps[app]

    command = ['uvicorn', *config.start.split()]

    try:
        subprocess.run(
            command,
            check=True,
            cwd=project.directory,
            env={
                **os.environ,
                "PYTHONPATH": str(project.directory),
            },
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to start application {app!r}")
        raise typer.Exit(code=1)
