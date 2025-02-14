
# plateforme.core.database.routing
# --------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module defines the `DatabaseRouter` abstract class for controlling
database operations in a multi-database environment scenario within the
Plateforme framework.

It provides methods to determine the appropriate database for read and write
operations, and to assess if a migration operation should be executed on a
specific database.
"""

from abc import ABC
from typing import Any

__all__ = (
    'DatabaseRouter'
)


class DatabaseRouter(ABC):
    """Database engine router for controlling database operations.

    A database engine router abstract class to control database operations on
    models within a multi-database setup.

    Note:
        This class should be used as an interface for database engine routing
        operations within the Plateforme framework.
    """

    def get_engine(
        self, resource: type[Any] | None = None, **kwargs: Any
    ) -> str | None:
        """Give a suggestion for the standard engine to use.

        Suggest the standard engine that should be used for read and write
        operations on a given resource clase.

        Args:
            resource: The resource class.
            kwargs: Additional information to assist in selecting an engine.

        Returns:
            An engine alias if a suggestion is made, else ``None``.
        """
        # Implement custom logic to decide which engine to use for read and
        # write operations...
        return None

    def get_read_engine(
        self, resource: type[Any] | None = None, **kwargs: Any
    ) -> str | None:
        """Give a suggestion for the engine to use for read operations.

        Suggest the engine that should be used for read operations on a
        given resource clase.

        Args:
            resource: The resource class.
            kwargs: Additional information to assist in selecting an engine.

        Returns:
            An engine alias if a suggestion is made, else ``None``.
        """
        # Implement custom logic to decide which engine to use for read
        # operations...
        return None

    def get_write_engine(
        self, resource: type[Any] | None = None, **kwargs: Any
    ) -> str | None:
        """Give a suggestion for the engine to use for write operations.

        Suggest the engine that should be used for write operations on a
        given resource clase.

        Args:
            resource: The resource class.
            kwargs: Additional information to assist in selecting an engine.

        Returns:
            An engine alias if a suggestion is made, else ``None``.
        """
        # Implement custom logic to decide which engine to use for write
        # operations...
        return None

    def is_migration_allowed(
        self,
        engine: str,
        package: str,
        **kwargs: Any,
    ) -> bool | None:
        """Flag whether a migration operation is allowed to run.

        Determine if the migration operation is allowed to run on the specified
        database engine alias.

        Args:
            engine: The database engine alias.
            package: The name of the package being migrated.
            kwargs: Additional information to assist in making a decision.

        Returns:
            ``True`` if operation should run, ``False`` if not, ``None`` if no
            opinion.
        """
        # Implement custom logic to determine if a migration operation should
        # run on a given database engine...
        return None
