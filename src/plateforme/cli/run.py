# plateforme.cli.run
# ------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
The run command line interface.
"""

import os
import subprocess

import typer

from .utils.context import Context
from .utils.logging import logger

app = typer.Typer()


@app.callback(invoke_without_command=True)
def run(
    ctx: Context,
    script: str = typer.Argument(..., help="The script to run."),
    app: str = typer.Option(
        'default',
        '--app', '-a',
        help=(
            "The application to run the script for. If not provided, it will "
            "run the script for the default application."
        ),
    ),
) -> None:
    """Run the plateforme project script."""
    logger.info(f"Running project script... (from {ctx.obj['project']})")

    project = ctx.obj['project']
    if not project:
        logger.error("No project found")
        raise typer.Exit(code=1)
    if not project.apps or app not in project.apps:
        logger.error(f"No application configuration found for {app!r}")
        raise typer.Exit(code=1)

    config = project.apps[app]
    if not config.scripts or script not in config.scripts:
        logger.warning(f"No script found for {script!r}")
        return

    command = config.scripts[script].split()
    if not command:
        logger.error(f"Empty script command for {script!r}")
        raise typer.Exit(code=1)

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
        logger.error(f"Failed to run script {script!r}")
        raise typer.Exit(code=1)

    logger.info(f"Script {script!r} ran successfully")
