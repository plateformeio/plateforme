# plateforme.core.api.middleware
# ------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing middleware within the Plateforme
framework's API using FastAPI and Starlette features.
"""

from functools import wraps
from typing import Any, Callable, TypeVar

from starlette.middleware import Middleware
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)

from ..context import SESSION_BULK_CONTEXT
from ..database.sessions import async_session_manager
from ..typing import is_async
from .exceptions import HTTPException
from .requests import Request
from .responses import Response
from .status import get_status_class

_C = TypeVar('_C', bound=Callable[..., Any])

__all__ = (
    'BaseHTTPMiddleware',
    'BulkMiddleware',
    'Middleware',
    'resolve_bulk_middleware',
)


# MARK: Bulk Middleware

class BulkMiddleware(BaseHTTPMiddleware):
    """Middleware for managing bulk operations on resources."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Handle bulk operations on resources."""

        async with async_session_manager(new=True) as session:
            async with session.bulk():
                response = await call_next(request)

            try:
                status = response.status_code
                if get_status_class(status) == 'HTTP_2':
                    await session.commit()
                else:
                    await session.rollback()

            except Exception as error:
                await session.rollback()
                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"An error occurred while finalizing the session: "
                        f"{error}"
                    ),
                )

            return response


# MARK: Utilities

def resolve_bulk_middleware(func: _C, /) -> _C:
    """Middleware decorator for resolving bulk operations on resources."""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Resolve resource references within the bulk context
        if bulk := SESSION_BULK_CONTEXT.get():
            resolver = bulk.resolve(
                raise_errors=True,
                scope='references',
                strategy='hydrate',
            )

            if is_async(bulk.resolve):
                await resolver

        return await func(*args, **kwargs)

    return wrapper  # type: ignore
