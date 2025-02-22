# plateforme.cli.main
# -------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
The main command line interface entry point.
"""

import os
import sys

import typer

from plateforme.core.projects import import_project_info

from . import (
    build,
    clean,
    deploy,
    drop,
    init,
    inspect,
    install,
    migrate,
    publish,
    run,
    shell,
    start,
)
from .utils.config import mount
from .utils.context import Context, ContextInfo
from .utils.info import print_info
from .utils.logging import logger

app = typer.Typer()

mount(app, build.app, merge=True)
mount(app, clean.app, merge=True)
mount(app, deploy.app, merge=True)
mount(app, drop.app, merge=True)
mount(app, init.app, merge=True)
mount(app, inspect.app, merge=True)
mount(app, install.app, merge=True)
mount(app, migrate.app, merge=True)
mount(app, publish.app, merge=True)
mount(app, run.app, merge=True)
mount(app, shell.app, merge=True)
mount(app, start.app, merge=True)


@app.callback()
def main(
    ctx: Context,
    project: str | None = typer.Option(
        None,
        '--project',
        '-p',
        help=(
            "Path to the project root directory. If not provided, it will "
            "search for a project root directory in the current working "
            "directory or its parent directories."
        ),
    ),
    project_app: str | None = typer.Option(
        None,
        '--app',
        '-a',
        help=(
            "The application to run the command for. If not provided and a "
            "project is found, it will be set to the default project "
            "application."
        ),
    ),
) -> None:
    """Command line interface main entry point."""
    # Add current working directory to the Python path
    sys.path.insert(0, os.getcwd())

    # Print information
    print_info(ctx)

    # Resolve project
    try:
        project_info = import_project_info(project)
    except Exception as error:
        if project is not None:
            logger.error(error)
            raise typer.Exit(code=1)
        project_info = None

    # Initialize context information
    ctx.obj = ContextInfo(
        project=project_info,
        project_app=project_app,
    )
