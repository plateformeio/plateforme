# plateforme.core.database.sessions
# ---------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing database sessions within the
Plateforme framework using SQLAlchemy features.
"""

import asyncio
from collections.abc import AsyncGenerator, Generator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, Callable, Literal, TypeVar, Union

from sqlalchemy.ext.asyncio import (
    AsyncSession as _AsyncSession,
    async_scoped_session as _async_scoped_session,
    async_sessionmaker as _async_sessionmaker,
)
from sqlalchemy.orm import (
    Session as _Session,
    scoped_session as _scoped_session,
    sessionmaker as _sessionmaker,
)

from ..context import PLATEFORME_CONTEXT, SESSION_BULK_CONTEXT, SESSION_CONTEXT
from ..errors import DatabaseError, SessionError
from .base import DatabaseManager
from .bulk import Bulk
from .engines import AsyncConnection, AsyncEngine, Connection, Engine
from .orm import Mapper

_T = TypeVar('_T', bound=object)

__all__ = (
    'AnySession',
    'AnySessionBulk',
    'AnySessionFactory',
    # Session (async)
    'AsyncSession',
    'AsyncSessionBulk',
    'AsyncSessionFactory',
    'async_session_factory',
    'async_session_manager',
    # Session (sync)
    'Session',
    'SessionBulk',
    'SessionFactory',
    'session_factory',
    'session_manager',
    # Utilities
    'set_expire_on_commit',
)


AnySession = Union['AsyncSession', 'Session']
"""A type alias for a session that can be either async or sync."""


AnySessionBulk = Union['AsyncSessionBulk', 'SessionBulk']
"""A type alias for a session bulk that can be either async or sync."""


AnySessionFactory = Union['AsyncSessionFactory', 'SessionFactory']
"""A type alias for a session factory that can be either async or sync."""


AsyncSessionFactory = _async_sessionmaker['AsyncSession'] \
    | _async_scoped_session['AsyncSession']
"""A type alias for an async session factory for async session objects."""


SessionFactory = _sessionmaker['Session'] \
    | _scoped_session['Session']
"""A type alias for a sync session factory for sync session objects."""


# MARK: Async Session

class AsyncSession(_AsyncSession):
    """Manages persistence operations asynchronously for ORM-mapped objects.

    Asyncio version of the `Session`. It is a proxy for a traditional class
    `Session` instance.
    """

    def __init__(
        self,
        bind: AsyncConnection | AsyncEngine | None = None,
        routing: DatabaseManager | None = None,
        *args: Any,
        **kwargs: Any,
    ):
        """Initialize the async session.

        See also the `async_session_factory` function which is used to generate
        an `AsyncSession`-producing callable with a given set of arguments.

        Args:
            bind: An optional `AsyncEngine` or `AsyncConnection` to which this
                `AsyncSession` should be bound. When specified, all SQL
                operations performed by this async session will execute via
                this connectable.
            routing: An optional `DatabaseManager` instance to use for the
                database routing.

        Note:
            All other keyword arguments are passed to the constructor of the
            SQLAlchemy parent session class.
        """
        super().__init__(
            bind,
            *args,
            routing=routing,
            sync_session_class=Session,
            **kwargs,
            proxy=self,
        )
        self.routing = routing

    @asynccontextmanager
    async def bulk(
        self, *, proxy_reference: bool = True,
    ) -> AsyncGenerator['AsyncSessionBulk', None]:
        """An async session bulk context manager for `AsyncSession` objects.

        The proxy option indicates that the provided resource references should
        be encapsulated with a proxy, this is done when validating the resource
        using the Pydantic core schema. This can be useful to resolve the
        references that target the same resource into a single instance. Thus,
        modifying a resolved instance will affect all references that target
        the same resource.

        Args:
            proxy_reference: Whether the registered resource references should
                be encapsulated with a proxy or not. Defaults to ``True``.

        Returns:
            An `AsyncSessionBulk` instance.
        """
        bulk = AsyncSessionBulk(self, proxy_reference=proxy_reference)
        token = SESSION_BULK_CONTEXT.set(bulk)
        try:
            yield bulk
        finally:
            SESSION_BULK_CONTEXT.reset(token)

    async def commit(self, *, expire: bool | None = None) -> None:
        """Flush pending changes and commit the current transaction.

        Args:
            expire: Whether to expire all instances after the commit, so that
                all attribute/object access subsequent to a completed
                transaction will load from the most recent database state.
                Defaults to ``None``.
        """
        if expire is None:
            return await super().commit()
        with set_expire_on_commit(expire, session=self):
            return await super().commit()


class AsyncSessionBulk(Bulk[AsyncSession]):
    """An async bulk operation manager for resources.

    It is used to register resources for bulk operations and commit or rollback
    them in a single operation within an async session.
    """

    async def resolve(
        self,
        *,
        raise_errors: bool = True,
        scope: Literal['all', 'references', 'values'] = 'all',
        strategy: Literal['bind', 'hydrate'] = 'bind',
    ) -> None:
        """Resolve the specified scope of resource entries in the bulk.

        For resource references, if the `proxy_reference` option is enabled,
        the resolved instances replace the reference proxy targets. Otherwise,
        the resolved instances are used to update the reference proxy target.

        For resource values, the resolved instances are used to update the
        resource instances with the fetched data, no proxy is used.

        Args:
            raise_errors: Whether to raise errors when failing to resolve
                resource references or values. Defaults to ``True``.
            scope: The scope of the resources to resolve, it can be either:
                - ``'all'``: Resolve both the resource references and values.
                - ``'references'``: Resolve only the resource references.
                - ``'values'``: Resolve only the resource values.
                Defaults to ``'all'``.
            strategy: The resolution strategy to use, it can be either:
                - ``'bind'``: Bind the resolved resource references and values
                    to the database session, i.e. only the resolved `id` and
                    `type_` fields are updated and the instances are made
                    transient to detached.
                - ``'hydrate'``: Hydrate the resolved resource references and
                    values with the data fetched from the database, i.e. the
                    instances are updated with the fetched data.
                Defaults to ``'bind'``.
        """
        resolver = self._resolver(
            raise_errors=raise_errors, scope=scope, strategy=strategy
        )

        try:
            context = next(resolver)
            while True:
                fields, statement = context
                result = await self.session.execute(statement)
                context = resolver.send((fields, result))
        except StopIteration:
            pass


# MARK: Session

class Session(_Session):
    """Manages persistence operations synchronously for ORM-mapped objects."""

    def __init__(
        self,
        bind: Connection | Engine | None = None,
        routing: DatabaseManager | None = None,
        proxy: AsyncSession | None = None,
        *args: Any,
        **kwargs: Any,
    ):
        """Initialize the session.

        See also the `session_factory` function which is used to generate a
        `Session`-producing callable with a given set of arguments.

        Args:
            bind: An optional `Engine` or `Connection` to which this `Session`
                should be bound. When specified, all SQL operations performed
                by this session will execute via this connectable.
            routing: An optional `DatabaseManager` instance to use for the
                database routing.
            proxy: An optional `AsyncSession` instance to use as a proxy for
                the async session. This is used within the `get_bind` method to
                determine the correct engine to use for the session.

        Note:
            All other keyword arguments are passed to the constructor of the
            SQLAlchemy parent session class.
        """
        super().__init__(bind, *args, **kwargs)
        self.routing = routing
        self.proxy = proxy

    @property
    def async_mode(self) -> bool:
        """Whether the session is in async mode or not."""
        return self.proxy is not None

    def get_bind(
        self,
        mapper: Mapper[_T] | type[_T] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> Connection | Engine:
        """Return a ``bind`` to which this `Session` is bound.

        Args:
            mapper: Optional mapped class or corresponding `Mapper` instance.
                The bind can be derived from a `Mapper` first by consulting the
                ``binds`` map associated with this `Session`, and secondly by
                consulting the `MetaData` associated with the `Table` to which
                the `Mapper` is mapped for a bind.

        Returns:
            The `Engine` or `Connection` to which this `Session` is bound.
        """
        # Handle custom routing logic based on the router attribute
        if self.bind is not None:
            return self.bind
        if self.routing is not None:
            # Retrieve resource type
            resource = mapper.class_ if isinstance(mapper, Mapper) else mapper
            # Check if the session is flushing (i.e. committing)
            if self._flushing:
                # Use the write engine for flushing operations
                engine = self.routing.get_write_engine(
                    resource, async_mode=self.async_mode, **kwargs
                )
            else:
                # Use the read engine for all other operations
                engine = self.routing.get_read_engine(
                    resource, async_mode=self.async_mode, **kwargs
                )
            # Try the default engine if no suggestion is made
            if engine is None:
                engine = self.routing.get_engine(
                    resource, async_mode=self.async_mode, **kwargs
                )
            # Finally return the engine if a suggestion is made
            if engine is not None:
                if isinstance(engine, AsyncEngine):
                    return engine.sync_engine
                return engine
        # Fallback to default behavior
        return super().get_bind(mapper, *args, **kwargs)

    @contextmanager
    def bulk(
        self, *, proxy_reference: bool = True,
    ) -> Generator['SessionBulk', None, None]:
        """A session bulk context manager for `Session` objects.

        The proxy option indicates that the provided resource references should
        be encapsulated with a proxy, this is done when validating the resource
        using the Pydantic core schema. This can be useful to resolve the
        references that target the same resource into a single instance. Thus,
        modifying a resolved instance will affect all references that target
        the same resource.

        Args:
            proxy_reference: Whether the registered resource references should
                be encapsulated with a proxy or not. Defaults to ``True``.

        Returns:
            A `SessionBulk` instance.
        """
        bulk = SessionBulk(self, proxy_reference=proxy_reference)
        token = SESSION_BULK_CONTEXT.set(bulk)
        try:
            yield bulk
        finally:
            SESSION_BULK_CONTEXT.reset(token)

    def commit(self, *, expire: bool | None = None) -> None:
        """Flush pending changes and commit the current transaction.

        Args:
            expire: Whether to expire all instances after the commit, so that
                all attribute/object access subsequent to a completed
                transaction will load from the most recent database state.
                Defaults to ``None``.
        """
        if expire is None:
            return super().commit()
        with set_expire_on_commit(expire, session=self):
            return super().commit()


class SessionBulk(Bulk[Session]):
    """A bulk operation manager for resources.

    It is used to register resources for bulk operations and commit or rollback
    them in a single operation within a session.
    """

    def resolve(
        self,
        *,
        raise_errors: bool = True,
        scope: Literal['all', 'references', 'values'] = 'all',
        strategy: Literal['bind', 'hydrate'] = 'bind',
    ) -> None:
        """Resolve the specified scope of resource entries in the bulk.

        For resource references, if the `proxy_reference` option is enabled,
        the resolved instances replace the reference proxy targets. Otherwise,
        the resolved instances are used to update the reference proxy target.

        For resource values, the resolved instances are used to update the
        resource instances with the fetched data, no proxy is used.

        Args:
            raise_errors: Whether to raise errors when failing to resolve
                resource references or values. Defaults to ``True``.
            scope: The scope of the resources to resolve, it can be either:
                - ``'all'``: Resolve both the resource references and values.
                - ``'references'``: Resolve only the resource references.
                - ``'values'``: Resolve only the resource values.
                Defaults to ``'all'``.
            strategy: The resolution strategy to use, it can be either:
                - ``'bind'``: Bind the resolved resource references and values
                    to the database session, i.e. only the resolved `id` and
                    `type_` fields are updated and the instances are made
                    transient to detached.
                - ``'hydrate'``: Hydrate the resolved resource references and
                    values with the data fetched from the database, i.e. the
                    instances are updated with the fetched data.
                Defaults to ``'bind'``.
        """
        resolver = self._resolver(
            raise_errors=raise_errors, scope=scope, strategy=strategy
        )

        try:
            context = next(resolver)
            while True:
                fields, statement = context
                result = self.session.execute(statement)
                context = resolver.send((fields, result))
        except StopIteration:
            pass


# MARK: Factories

def async_session_factory(
    bind: AsyncConnection | AsyncEngine | None = None,
    *,
    routing: DatabaseManager | None = None,
    scoped: bool = False,
    scopefunc: Callable[[], Any] = asyncio.current_task,
    autoflush: bool = True,
    expire_on_commit: bool = True,
    info: dict[Any, Any] | None = None,
    **kwargs: Any,
) -> AsyncSessionFactory:
    """Create an async session factory for `Session` objects.

    Args:
        bind: An optional `AsyncEngine` or `AsyncConnection` to which this
            `AsyncSession` should be bound. When specified, all SQL operations
            performed by this session will execute via this connectable.
            Defaults to ``None``.
        routing: An optional `DatabaseManager` instance to use for the database
            routing. Defaults to ``None``.
        scoped: Whether to use a scoped session or not. The scoped session
            factory ensures that the session is thread-safe.
            Defaults to ``False``.
        scopefunc: An optional callable that returns a hashable token that
            identifies the current scope. Defaults to `asyncio.current_task`.
        autoflush: Whether to enable autoflush or not. Defaults to ``True``.
        expire_on_commit: Whether to expire all instances after the commit.
            Defaults to ``True``.
        info: An optional dictionary of arbitrary data to be associated with
            this async session. Defaults to ``None``.

    Returns:
        An `AsyncSessionFactory` instance for creating `AsyncSession` objects.

    Note: All other keyword arguments are passed to the constructor of the
        parent SQLAlchemy `async_sessionmaker` class.
    """
    # Build session factory
    factory = _async_sessionmaker(
        bind,
        class_=AsyncSession,
        routing=routing,
        autoflush=autoflush,
        expire_on_commit=expire_on_commit,
        info=info,
        **kwargs,
    )
    # Wrap the factory in a scoped async session manager if requested. The
    # scoped async session factory ensures that the async session is
    # thread-safe.
    return _async_scoped_session(factory, scopefunc) if scoped else factory


def session_factory(
    bind: Connection | Engine | None = None,
    *,
    routing: DatabaseManager | None = None,
    scoped: bool = False,
    autoflush: bool = True,
    expire_on_commit: bool = True,
    info: dict[Any, Any] | None = None,
    **kwargs: Any,
) -> SessionFactory:
    """Create a sync session factory for `Session` objects.

    Args:
        bind: An optional `Engine` or `Connection` to which this `Session`
            should be bound. When specified, all SQL operations performed by
            this session will execute via this connectable.
            Defaults to ``None``.
        routing: An optional `DatabaseManager` instance to use for the database
            routing. Defaults to ``None``.
        scoped: Whether to use a scoped session or not. The scoped session
            factory ensures that the session is thread-safe.
            Defaults to ``False``.
        autoflush: Whether to enable autoflush or not. Defaults to ``True``.
        expire_on_commit: Whether to expire all instances after the commit.
            Defaults to ``True``.
        info: An optional dictionary of arbitrary data to be associated with
            this session. Defaults to ``None``.

    Returns:
        A `SessionFactory` instance for creating `Session` objects.

    Note:
        All other keyword arguments are passed to the constructor of the parent
        SQLAlchemy `sessionmaker` class.
    """
    # Build session factory
    factory = _sessionmaker(
        bind,
        class_=Session,
        routing=routing,
        autoflush=autoflush,
        expire_on_commit=expire_on_commit,
        info=info,
        **kwargs,
    )
    # Wrap the factory in a scoped session manager if requested. The scoped
    # session factory ensures that the session is thread-safe.
    return _scoped_session(factory) if scoped else factory


# MARK: Context Managers

@asynccontextmanager
async def async_session_manager(
    *,
    using: AsyncSessionFactory | None = None,
    new: bool = False,
    on_missing: Literal['create', 'raise'] = 'create',
    on_exit: Literal['commit', 'flush', 'rollback'] | None = None,
    expire: bool | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    """An async session context manager for `AsyncSession` objects.

    Provide a transactional async session context around a series of
    operations. It manages the async session lifecycle and commits or rollbacks
    the async session automatically based on the context.

    Args:
        using: An optional `AsyncSessionFactory` instance to use instead of
            the application context factory. Defaults to ``None``.
        new: Whether to create a new session or not. If set to ``True``, a new
            session is created. If set to ``False``, the current session is
            used if available, otherwise it follows the `on_missing` behavior.
            Defaults to ``False``.
        on_missing: The behavior to follow when no current session is
            available, either to create a new session or raise an error.
            Defaults to ``'create'``.
        on_exit: The action to perform after the operation completes. If set to
            ``None``, no action is performed after the operation. Otherwise, it
            can be set to either ``'commit'``, ``'flush'``, or ``'rollback'``.
            Defaults to ``None``.
        expire: Whether to expire all instances after the commit. If set to
            ``True``, all instances are expired after the commit. If set to
            ``False``, all instances are preserved after the commit. Otherwise,
            the session default behavior is used. Defaults to ``None``.

    Returns:
        An `AsyncSession` instance.

    Note:
        If neither an application nor a factory are provided and no current
        session is available, the manager will look for a session factory in
        the current context.
    """
    session = SESSION_CONTEXT.get()

    # Helper function to finalize the session
    async def finalize(_session: AsyncSession) -> None:
        if on_exit == 'commit':
            await _session.commit(expire=expire)
        elif on_exit == 'flush':
            await _session.flush()
        elif on_exit == 'rollback':
            await _session.rollback()

    # Retrieve session
    if new is False:
        if session is not None:
            if isinstance(session, AsyncSession):
                yield session
                await finalize(session)
                return
            raise RuntimeError(
                f"Invalid session type found in the current context. Expected "
                f"an `AsyncSession` instance but found {type(session)!r}."
            )
        elif on_missing == 'raise':
            raise RuntimeError(
                "No async session available in the current context where "
                "creating a new session is not allowed `on_missing='raise'`."
            )

    # Retrieve factory
    factory: AsyncSessionFactory | None = None
    if using is not None:
        factory = using
    else:
        app = PLATEFORME_CONTEXT.get()
        if app is not None:
            factory = app.async_session
    # Check factory
    if factory is None:
        raise SessionError(
            "No session factory available in the current context."
        )

    # Retrieve async session
    session = factory()
    token = SESSION_CONTEXT.set(session)

    # Execute operation
    try:
        yield session
    except Exception as error:
        await session.rollback()
        raise DatabaseError(
            "An error occurred while executing a database operation."
        ) from error
    else:
        await finalize(session)
    finally:
        SESSION_CONTEXT.reset(token)
        if isinstance(factory, _async_scoped_session):
            await factory.remove()
        else:
            await session.close()


@contextmanager
def session_manager(
    *,
    using: SessionFactory | None = None,
    new: bool = False,
    on_missing: Literal['create', 'raise'] = 'create',
    on_exit: Literal['commit', 'flush', 'rollback'] | None = None,
    expire: bool | None = None,
) -> Generator[Session, None, None]:
    """A sync session context manager for `Session` objects.

    Provide a transactional session context around a series of operations. It
    manages the session lifecycle and commits or rollbacks the session
    automatically based on the context.

    Args:
        using: An optional `SessionFactory` instance to use instead of the
            application context factory. Defaults to ``None``.
        new: Whether to create a new session or not. If set to ``True``, a new
            session is created. If set to ``False``, the current session is
            used if available, otherwise it follows the `on_missing` behavior.
            Defaults to ``False``.
        on_missing: The behavior to follow when no current session is
            available, either to create a new session or raise an error.
            Defaults to ``'create'``.
        on_exit: The action to perform after the operation completes. If set to
            ``None``, no action is performed after the operation. Otherwise, it
            can be set to either ``'commit'``, ``'flush'``, or ``'rollback'``.
            Defaults to ``None``.
        expire: Whether to expire all instances after the commit. If set to
            ``True``, all instances are expired after the commit. If set to
            ``False``, all instances are preserved after the commit. Otherwise,
            the session default behavior is used. Defaults to ``None``.

    Returns:
        A `Session` instance.

    Note:
        If neither an application nor a factory are provided and no current
        session is available, the manager will look for a session factory in
        the current context.
    """
    session = SESSION_CONTEXT.get()

    # Helper function to finalize the session
    def finalize(_session: Session) -> None:
        if on_exit == 'commit':
            _session.commit(expire=expire)
        elif on_exit == 'flush':
            _session.flush()
        elif on_exit == 'rollback':
            _session.rollback()

    # Retrieve session
    if new is False:
        if session is not None:
            if isinstance(session, Session):
                yield session
                finalize(session)
                return
            raise RuntimeError(
                f"Invalid session type found in the current context. Expected "
                f"a `Session` instance but found {type(session)!r}."
            )
        elif on_missing == 'raise':
            raise RuntimeError(
                f"No session available in the current context where creating "
                f"a new session is not allowed `on_missing='raise'`."
            )

    # Retrieve factory
    factory: SessionFactory | None
    if using is not None:
        factory = using
    else:
        app = PLATEFORME_CONTEXT.get()
        if app is not None:
            factory = app.session
    # Check factory
    if factory is None:
        raise SessionError(
            "No session factory available in the current context."
        )

    # Retrieve sync session
    session = factory()
    token = SESSION_CONTEXT.set(session)

    # Execute operation
    try:
        yield session
    except Exception as error:
        session.rollback()
        raise DatabaseError(
            "An error occurred while executing a database operation."
        ) from error
    else:
        finalize(session)
    finally:
        SESSION_CONTEXT.reset(token)
        if isinstance(factory, _scoped_session):
            factory.remove()
        else:
            session.close()


# MARK: Utilities

@contextmanager
def set_expire_on_commit(
    value: bool, *, session: AnySession | None = None
) -> Iterator[None]:
    """Temporarily set expire_on_commit to a specific value."""
    # Resolve sync session
    if session is None:
        session = SESSION_CONTEXT.get()
    if session is None:
        raise ValueError(
            "No session available in the current context. A valid session "
            "instance must be provided."
        )
    if hasattr(session, 'sync_session'):
        session = getattr(session, 'sync_session')

    # Handle expire on commit
    assert isinstance(session, _Session)
    session_expire_on_commit = session.expire_on_commit
    session.expire_on_commit = value
    try:
        yield
    finally:
        session.expire_on_commit = session_expire_on_commit
