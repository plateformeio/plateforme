# plateforme.core.api.exceptions
# ------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing exceptions within the Plateforme
framework's API using FastAPI and Starlette features.
"""

from typing import Callable

from fastapi.exceptions import HTTPException, WebSocketException

from .. import errors
from .requests import Request
from .responses import JSONResponse, Response
from .status import status

__all__ = (
    'HTTPException',
    'WebSocketException',
    'database_exception_handler',
    'session_exception_handler',
    'EXCEPTION_HANDLERS',
)


# MARK: Database Handlers

def database_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handle database exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={'message': "An error occurred while handling the database."},
    )


def session_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Handle database session exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={'message': "An error occurred while handling the session."},
    )


# MARK: Exception Handlers Mapping

EXCEPTION_HANDLERS: dict[
    type[Exception],
    Callable[[Request, Exception], Response],
] = {
    errors.DatabaseError: database_exception_handler,
    errors.SessionError: session_exception_handler,
}
"""A dictionary of exception handlers for the Plateforme application."""
