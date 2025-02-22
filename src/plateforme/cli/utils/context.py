# plateforme.cli.utils.context
# ----------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
Context utilities for the command line interface.
"""

import dataclasses

import typer

from plateforme.core.projects import ProjectAppInfo, ProjectInfo

from .logging import logger


@dataclasses.dataclass(kw_only=True, slots=True)
class ContextInfo:
    """Context information for the command line interface."""
    project: ProjectInfo | None
    project_app: str | None

    def __post_init__(self) -> None:
        """Validate context information."""
        if self.project is not None:
            if self.project_app is None and self.project.apps:
                if 'default' in self.project.apps:
                    self.project_app = 'default'
                else:
                    self.project_app = next(iter(self.project.apps))
            elif self.project_app is not None \
                    and self.project_app not in (self.project.apps or {}):
                logger.error(
                    f"No project application configuration found for "
                    f"{self.project_app!r}"
                )
                raise typer.Exit(code=1)
        elif self.project_app is not None:
            logger.error("Cannot specify an application without a project")
            raise typer.Exit(code=1)

    def get_app_config(self) -> tuple[ProjectAppInfo, ProjectInfo, str]:
        """Get the project application configuration."""
        if self.project is None:
            logger.error("No project found")
            raise typer.Exit(code=1)
        if self.project_app is None:
            logger.error("No project application found")
            raise typer.Exit(code=1)
        if self.project.apps is None:
            logger.error("No project application configuration found")
            raise typer.Exit(code=1)
        config = self.project.apps[self.project_app]

        return config, self.project, self.project_app


class Context(typer.Context):
    """The command line interface context."""
    obj: ContextInfo
