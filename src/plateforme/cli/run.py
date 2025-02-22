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


@app.command()
def run(
    ctx: Context,
    script: str = typer.Argument(..., help="The script to run."),
) -> None:
    """Run the plateforme project script."""
    config, project, project_app = ctx.obj.get_app_config()

    logger.info(f"Running project script...(from {project}:{project_app})")

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
