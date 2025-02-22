# plateforme.cli.build
# --------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
The build command line interface.
"""

import os
import subprocess

import typer

from .utils.context import Context
from .utils.logging import logger

app = typer.Typer()


@app.command()
def build(ctx: Context) -> None:
    """Build the plateforme project application."""
    config, project, project_app = ctx.obj.get_app_config()

    logger.info(f"Building application... (from {project}:{project_app})")

    if config.build is None:
        logger.warning(f"No build command found")
        return

    if config.scripts is None:
        logger.error("No scripts found")
        raise typer.Exit(code=1)

    for script in config.build:
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
        except subprocess.CalledProcessError:
            logger.error(f"An error occurred while running script {script!r}")
            logger.error(f"Failed to build application {project_app!r}")
            raise typer.Exit(code=1)

    logger.info(f"Application {project_app!r} built successfully")
