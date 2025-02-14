# plateforme.core.api.dependencies
# --------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing dependencies within the Plateforme
framework.
"""

from typing import Annotated, AsyncGenerator, Generator

from ..database.sessions import (
    AsyncSession,
    Session,
    async_session_manager,
    session_manager,
)
from ..expressions import Filter
from .parameters import Depends
from .requests import Request

__all__ = (
    'AsyncSessionDep',
    'SessionDep',
    'async_session_dependency',
    'filter_dependency',
    'session_dependency'
)


# MARK: Function Dependencies

def filter_dependency(
    request: Request, filter: Filter | None = None
) -> Filter | None:
    """Get a filter query parameters injection dependency."""
    criteria = {}
    for key, value in request.query_params.items():
        # Skip non-filter parameters
        if not key.startswith('.'):
            continue
        criteria[key[1:]] = value

    if not criteria:
        return filter
    return Filter(filter or {}, **criteria)


async def async_session_dependency() -> AsyncGenerator[AsyncSession, None]:
    """Get an async session dependency."""
    async with async_session_manager() as session:
        yield session


def session_dependency() -> Generator[Session, None, None]:
    """Get a session dependency."""
    with session_manager() as session:
        yield session


# MARK: Type Dependencies

AsyncSessionDep = Annotated[AsyncSession, Depends(async_session_dependency)]
"""An async session dependency for use in API route handlers."""


SessionDep = Annotated[Session, Depends(session_dependency)]
"""A session dependency for use in API route handlers."""
