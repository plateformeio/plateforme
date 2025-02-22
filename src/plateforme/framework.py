# plateforme.framework
# --------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing the Plateforme framework version
and repository information.
"""

import typing
from enum import StrEnum
from typing import Any, Literal

__all__ = (
    'AUTHOR',
    'LICENSE',
    'VERSION',
    'URL',
    'version_info',
    'version_major',
    'version_minor',
    'version_patch',
)


AUTHOR = 'Plateforme'
"""The author of the Plateforme framework."""


LICENSE = 'MIT'
"""The license of the Plateforme framework."""


VERSION = '0.1.0-a2'
"""The version of the Plateforme framework."""


@typing.overload
def version_info(format: Literal['text'] = 'text') -> str:
    ...

@typing.overload
def version_info(format: Literal['json']) -> dict[str, Any]:
    ...

def version_info(
    format: Literal['text', 'json'] = 'text',
) -> str | dict[str, Any]:
    """The version information of the Plateforme framework.

    Returns:
        A string containing the information about the framework and its
        dependencies.

    Examples:
        It returns a string like the following:
        ```
        framework version: 2.1.1
        install path: /path/to/plateforme
        python version: 3.11.0
        operating system: Mac OS X-10.15.7-x86_64-i386-64bit
        related packages: alembic-1.4.3 fastapi-0.61.1 ...
        last commit: 1234567
        ```
    """
    import importlib.metadata
    import os
    import platform
    import sys
    from pathlib import Path

    from .tools import git

    # Get information about packages that are closely related to Plateforme,
    # use Plateforme or often conflict with Plateforme framework.
    package_names = {
        'alembic',
        'fastapi',
        'mypy',
        'pydantic',
        'pydantic-core',
        'pydantic-extra-types',
        'pydantic-settings',
        'pyright',
        'sqlalchemy',
        'typing_extensions',
    }
    related_packages = []

    # Get information about packages
    for dist in importlib.metadata.distributions():
        name = dist.metadata['Name']
        if name in package_names:
            related_packages.append(f'{name}-{dist.version}')

    # Get information about the framework
    plateforme_dir = os.path.abspath(
        os.path.dirname(os.path.dirname(__file__))
    )
    most_recent_commit = (
        git.git_revision(plateforme_dir)
        if git.is_git_repo(plateforme_dir) and git.have_git() else 'unknown'
    )

    # Build information object
    info = {
        'framework version': VERSION,
        'install path': Path(__file__).resolve().parent,
        'python version': sys.version,
        'operating system': platform.platform(),
        'related packages': ' '.join(related_packages),
        'last commit': most_recent_commit,
    }
    if format == 'json':
        return info
    return '\n'.join(
        '{:>18} {}'.format(key + ':', str(value).replace('\n', ' '))
        for key, value in info.items()
    )


def version_major() -> str:
    """The major version of the Plateforme framework.

    Returns:
        The ``major`` part of the Plateforme framework version.

    Examples:
        It returns ``2`` if Plateforme framework version is ``2.1.1``.
    """
    return '.'.join(VERSION.split('.')[:1])


def version_minor() -> str:
    """The minor version of the Plateforme framework.

    Returns:
        The ``major.minor`` part of the Plateforme framework version.

    Examples:
        It returns ``2.1`` if Plateforme framework version is ``2.1.1``.
    """
    return '.'.join(VERSION.split('.')[:2])


def version_patch() -> str:
    """The patch version of the Plateforme framework.

    Returns:
        The ``major.minor.patch`` part of the Plateforme framework version.

    Examples:
        It returns ``2.1.1`` if Plateforme framework version is ``2.1.1``.
    """
    return '.'.join(VERSION.split('.')[:3])


class URL(StrEnum):
    """An enumeration of URLs used within the Plateforme framework."""

    DOCS = f'https://docs.plateforme.io/{version_minor()}/'
    ERRORS = f'https://docs.plateforme.io/{version_minor()}/errors/'
    FAVICON = 'https://docs.plateforme.io/favicon.png'
