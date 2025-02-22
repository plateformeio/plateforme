# plateforme.cli.init
# -------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
The initialization command line interface subgroup.
"""

import os
from pathlib import Path

import questionary
import typer

from plateforme.core.patterns import (
    to_kebab_case,
    to_snake_case,
    to_title_case,
)
from plateforme.core.settings import generate_secret_key

from .utils.context import Context
from .utils.logging import logger
from .utils.templates import render_path, render_template

dirname = Path(__file__).parent

app = typer.Typer()


@app.command()
def init(
    ctx: Context,
    root: str = typer.Argument('.', help="The project root directory."),
    python_version: str = typer.Option(
        '3.11',
        '--python',
        help="Python version to be used.",
    ),
    experimental: bool = typer.Option(
        False,
        '--experimental',
        help="Activate experimental features.",
    ),
) -> None:
    """Initialize a new Plateforme project.

    Args:
        cwd: The current working directory to use for the project.
        python_version: The Python version to be used.
        experimental: Whether to activate experimental features.
    """
    try:
        # Project configuration
        project_name = questionary.text(
            'Project name:',
            validate=lambda t: True if len(t) > 0 else "Please enter a name",
        ).unsafe_ask()
        project_name = to_snake_case(project_name)

        project_version = questionary.text(
            'Version:', default='0.1.0'
        ).unsafe_ask()
        project_description = questionary.text('Description:').unsafe_ask()
        project_author_name = questionary.text('Author (name):').unsafe_ask()
        project_author_email = questionary.text('Author (email):').unsafe_ask()

        # Project template
        project_template = questionary.select(
            'Template:', choices=['Enterprise', 'Hero'], default='Hero'
        ).unsafe_ask()

        # Project directory
        project_dir = Path(root).resolve()
        if questionary.confirm(
            'Create a new directory for the project?', default=True
        ).unsafe_ask():
            project_dir /= project_name

        # Build project configuration
        config = {
            'project_name': project_name,
            'project_slug': to_kebab_case(project_name),
            'project_title': to_title_case(project_name),
            'project_version': project_version,
            'project_description': project_description,
            'project_author_name': project_author_name,
            'project_author_email': project_author_email,
            'project_template': project_template,
            'project_secret': generate_secret_key(),
            'python_version': python_version,
            'experimental': experimental,
        }

        # Confirm the project creation
        if not questionary.confirm(
            f'Create project in {project_dir.as_posix()!r} directory?'
        ).unsafe_ask():
            raise typer.Exit()

    except KeyboardInterrupt:
        logger.info('Operation cancelled by the user.')
        raise typer.Exit()

    # Create the project directory
    project_dir.mkdir(parents=True, exist_ok=True)

    # Render template
    template_dir = dirname / 'templates/bases' / str(project_template).lower()
    for template_path in template_dir.glob('**/*.jinja'):
        if not template_path.is_file():
            continue
        template_name = template_path.relative_to(template_dir)
        template_name = template_name.with_name(template_name.stem)
        target_path = project_dir / render_path(template_name, **config)
        render_template(template_path, target_path, **config)

    # Navigate into the new project directory
    os.chdir(project_dir)

    logger.info('Project initialized successfully!')
