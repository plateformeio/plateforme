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


@app.command(
    context_settings={
        'allow_extra_args': True,
        'ignore_unknown_options': True,
    },
)
def start(
    ctx: Context,
    nargs: list[str] | None = typer.Argument(
        None,
        help=(
            "Arguments to pass to the uvicorn command. "
            "Try 'plateforme start --help-nargs' for more information."
        ),
    ),
    help_nargs: bool = typer.Option(
        False,
        '--help-nargs',
        help="Show help message for the uvicorn 'nargs' arguments.",
    ),
) -> None:
    """Start the plateforme project application."""
    if help_nargs:
        try:
            subprocess.run(['uvicorn', '--help'], check=True)
        except subprocess.CalledProcessError:
            logger.error("Failed to run 'uvicorn --help'")
            raise typer.Exit(code=1)
        raise typer.Exit()

    config, project, project_app = ctx.obj.get_app_config()

    logger.info(f"Starting application... (from {project}:{project_app})")

    command = ['uvicorn', *config.start.split()]
    command.extend(nargs or [])

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
        logger.error(f"Failed to start application {project_app!r}")
        raise typer.Exit(code=1)
