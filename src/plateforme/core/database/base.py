
# plateforme.core.database.base
# -----------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module defines the `DatabaseManager` class for controlling database
operations. It provides methods for managing database engine connections and
routing operations using `DatabaseRouter` interfaces for multi-database
environment scenario within the Plateforme framework.
"""

import re
import typing
from collections.abc import Iterable, Iterator
from typing import Any, Literal

from sqlalchemy.exc import MissingGreenlet
from sqlalchemy.inspection import inspect

from ..errors import PlateformeError
from ..patterns import RegexPattern
from ..types.networks import EngineMap, EngineUrl
from .engines import AsyncEngine, Engine, create_async_engine, create_engine
from .routing import DatabaseRouter

__all__ = (
    'DatabaseManager',
    'MissingGreenlet',
    'inspect',
)


class DatabaseManager(Iterable[str]):
    """A utility class for managing database engine connections."""
    if typing.TYPE_CHECKING:
        async_engines: dict[str, AsyncEngine]
        engines: dict[str, Engine]
        routers: list[DatabaseRouter]
        urls: EngineMap

    __slots__ = (
        'async_engines',
        'engines',
        'routers',
        'urls',
    )

    def __init__(self,
        urls: EngineMap,
        routers: list[DatabaseRouter] | None = None,
    ) -> None:
        """Initialize the engine manager.

        Args:
            urls: A dictionary of database engine URLs to be managed.
            routers: A list of database routers to be used for routing
                operations. Defaults to an empty list.
        """
        # Initialize urls
        self.urls = urls
        # Initialize engines
        self.engines = {}
        self.async_engines = {}
        for alias, url in urls.items():
            # Unpack URL
            conn = str(url)
            scheme, address = conn.split('://')
            match = re.match(RegexPattern.ENGINE_SCHEME, scheme)
            assert match is not None
            _, dialect, driver = match.groups()
            assert isinstance(dialect, str) and isinstance(driver, str)
            # Create engines
            self.async_engines[alias] = create_async_engine(conn)
            self.engines[alias] = create_engine(f'{dialect}://{address}')

        # Initialize routers
        self.routers = routers or []

    def get_engine(
        self,
        resource: type[Any] | None = None,
        async_mode: bool = False,
        operation_mode: Literal['read', 'write'] | None = None,
        **kwargs: Any
    ) -> AsyncEngine | Engine:
        """Give a suggestion for the standard engine to use.

        Suggest the standard engine that should be used for read and write
        operations on a given resource clase.

        Args:
            resource: The resource class. Defaults to ``None``.
            async_mode: Whether to return an async engine or a sync engine.
                Defaults to ``False``.
            operation_mode: The mode of operation either ``read``, or
                ``write``. If ``None`` is provided, the standard engine will be
                suggested. Defaults to ``None``.
            **kwargs: Additional information to assist in selecting an engine.

        Returns:
            Either an async engine or a sync engine depending on the chosen
            async mode. Defaults to sync engine.
        """
        # Retrieve the engines
        engines: dict[str, Engine | AsyncEngine] = \
            self.async_engines if async_mode else self.engines  # type: ignore
        # Check if any of the routers have a suggestion
        def suggest(
            mode: Literal['read', 'write'] | None,
        ) -> AsyncEngine | Engine | None:
            for router in self.routers:
                # Retrieve the router method
                method = getattr(
                    router,
                    f'get_{mode}_engine' if mode else 'get_engine',
                    lambda *args, **kwargs: None
                )
                if not callable(method):
                    raise PlateformeError(
                        f"Invalid router method {method!r}. Router methods "
                        f"must be callable.",
                        code='plateforme-invalid-engine',
                    )
                # Retrieve the router suggestion
                if name := method(resource, **kwargs):
                    if not isinstance(name, str) and name not in engines:
                        raise PlateformeError(
                            f"Invalid engine alias {name!r}. The "
                            f"{'async' if async_mode else 'sync'} engine "
                            f"alias is not defined.",
                            code='plateforme-invalid-engine',
                        )
                    return engines[name]
            return None

        # Try to return the suggested engine
        if engine := suggest(operation_mode):
            return engine
        elif operation_mode and (engine := suggest(None)):
            return engine
        elif 'default' in engines:
            return engines['default']

        # Raise an exception if no suggestion was made
        raise PlateformeError(
            "No standard engine suggestion was made by any of the routers and "
            "no `default` engine was specified.",
            code='plateforme-invalid-engine',
        )

    def get_read_engine(
        self,
        resource: type[Any] | None = None,
        async_mode: bool = False,
        **kwargs: Any
    ) -> AsyncEngine | Engine:
        """Give a suggestion for the engine to use for read operations.

        Suggest the engine that should be used for read operations on a
        given resource clase.

        Args:
            resource: The resource class.
            async_mode: Whether to return an async engine or a sync engine.
                Defaults to ``False``.
            **kwargs: Additional information to assist in selecting an engine.

        Returns:
            An engine alias if a suggestion is made, else ``None``.
        """
        return self.get_engine(
            resource, async_mode, operation_mode='read', **kwargs
        )

    def get_write_engine(
        self,
        resource: type[Any] | None = None,
        async_mode: bool = False,
        **kwargs: Any,
    ) -> AsyncEngine | Engine:
        """Give a suggestion for the engine to use for write operations.

        Suggest the engine that should be used for write operations on a
        given resource clase.

        Args:
            resource: The resource class.
            async_mode: Whether to return an async engine or a sync engine.
                Defaults to ``False``.
            **kwargs: Additional information to assist in selecting an engine.

        Returns:
            An engine alias if a suggestion is made, else ``None``.
        """
        return self.get_engine(
            resource, async_mode, operation_mode='write', **kwargs
        )

    def is_migration_allowed(
        self,
        engine: str,
        package: str,
        **kwargs: Any,
    ) -> bool:
        """Flag whether a migration operation is allowed to run.

        Determine if the migration operation is allowed to run on the specified
        database engine alias.

        Args:
            engine: The database engine alias.
            package: The name of the package being migrated.
            **kwargs: Additional information to assist in making a decision.

        Returns:
            ``True`` if operation should run, ``False`` if not. Defaults to
            ``True``.
        """
        # Check if any of the routers have a suggestion
        for router in self.routers:
            is_allowed = router.is_migration_allowed(engine, package, **kwargs)
            if is_allowed is not None:
                return is_allowed
        # Return default
        return True

    def __contains__(self, key: str) -> bool:
        return key in self.urls

    def __iter__(self) -> Iterator[str]:
        yield from self.urls

    def __reversed__(self) -> Iterator[str]:
        yield from reversed(self.urls)

    def __len__(self) -> int:
        return len(self.urls)

    def __getitem__(self, key: str) -> EngineUrl:
        return self.urls[key]

    def __setitem__(self, key: str, url: EngineUrl) -> None:
        self.urls[key] = url

    def __delitem__(self, key: str) -> None:
        del self.urls[key]

    def __repr__(self) -> str:
        return repr(self.urls)

    def __str__(self) -> str:
        return str(self.urls)
