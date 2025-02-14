# plateforme.cli.utils.template
# -----------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
Templating utilities for the command line interface.
"""

import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


def render_template(
    template_path: Path | str,
    target_path: Path | str,
    **context: Any,
) -> None:
    """Render a template file to the target path.

    It renders a template file with the given context and save it to the output
    path (relative to the templates directory).

    Args:
        template_path: Path to the template file.
        target_path: Path to the target file.
        **extra: Context dictionary to be used for rendering.
    """
    if isinstance(template_path, str):
        template_path = Path(template_path)
    if isinstance(target_path, str):
        target_path = Path(target_path)

    # Setup the templating environment
    env = Environment(
        loader=FileSystemLoader(searchpath=template_path.parent),
        autoescape=select_autoescape(['html', 'xml'])
    )

    # Render template
    template = env.get_template(template_path.name)
    rendered = template.render(context)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, 'w') as f:
        f.write(rendered)


def render_path(path: Path | str, **context: Any) -> Path:
    """Replace placeholders in a string with the given context.

    Args:
        value: The string to replace placeholders in.
        **context: The context dictionary to use for replacement.

    Returns:
        The path with placeholders replaced by their context values.
    """
    rendered = re.sub(
        r'{{\s*(\w+)\s*}}',
        lambda m: context.get(m.group(1), m.group(0)),
        str(path),
    )

    return Path(rendered)
