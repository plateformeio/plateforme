# plateforme.cli.main
# -------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
The main command line interface entry point.
"""

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
from .utils.context import Context
from .utils.info import print_info
from .utils.logging import logger

app = typer.Typer()

app.add_typer(build.app, name='build')
app.add_typer(clean.app, name='clean')
app.add_typer(deploy.app, name='deploy')
app.add_typer(drop.app, name='drop')
app.add_typer(init.app, name='init')
app.add_typer(inspect.app, name='inspect')
app.add_typer(install.app, name='install')
app.add_typer(migrate.app, name='migrate')
app.add_typer(publish.app, name='publish')
app.add_typer(run.app, name='run')
app.add_typer(shell.app, name='shell')
app.add_typer(start.app, name='start')


@app.callback()
def main(
    ctx: Context,
    project: str | None = typer.Option(
        None,
        '--project', '-p',
        help=(
            "Path to the project root directory. If not provided, it will "
            "search for the project root directory in the current working "
            "directory."
        ),
    ),
) -> None:
    """Command line interface main entry point."""
    print_info(ctx)

    try:
        project_info = import_project_info(project)
    except Exception as error:
        if project is not None:
            logger.error(error)
            raise typer.Exit(code=1)
        project_info = None

    ctx.obj = {'project': project_info}
