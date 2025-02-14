# plateforme.core.errors
# ----------------------
# Copyright (c) 2018 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module defines error and exception types specific to the Plateforme
framework. Those classes can be used to handle exceptions and errors that may
occur during the execution of the framework.
"""

from typing import Any, Literal, Self

from ..framework import URL

__all__ = (
    # Plateforme
    'ERROR_CODES',
    'BaseError',
    'PlateformeError',
    # Database
    'DatabaseError',
    'SessionError',
    'MissingDeferred',
)


# MARK: Plateforme

ERROR_CODES = Literal[
    # Framework errors
    'database-error',
    'session-error',
    'missing-deferred',
    # User errors
    'association-invalid-config',
    'attribute-invalid-config',
    'authentication-failed',
    'authorization-failed',
    'field-invalid-config',
    'field-not-found',
    'migration-failed',
    'model-build-failed',
    'model-invalid-config',
    'namespace-invalid-config',
    'namespace-invalid-implementation',
    'namespace-invalid-package',
    'namespace-not-found',
    'package-not-available',
    'package-not-found',
    'package-invalid-app',
    'package-invalid-config',
    'package-invalid-implementation',
    'plateforme-invalid-application',
    'plateforme-invalid-config',
    'plateforme-invalid-engine',
    'plateforme-invalid-module',
    'plateforme-invalid-namespace',
    'plateforme-invalid-package',
    'plateforme-invalid-router',
    'request-failed',
    'resource-add-failed',
    'resource-build-failed',
    'resource-delete-failed',
    'resource-endpoint-parameter',
    'resource-initalization-failed',
    'resource-invalid-config',
    'resource-merge-failed',
    'resource-not-found',
    'route-invalid-config',
    'route-invalid-name',
    'route-invalid-parameter',
    'schema-already-registered',
    'schema-resolution-failed',
    'services-already-bound',
    'services-invalid-config',
    'services-not-bound',
    'spec-already-applied',
    'spec-not-applied',
    'spec-applied-to-base',
]
"""An enumeration of all Plateforme error codes typically used to identify
documentation url for specific errors."""


class BaseError(Exception):
    """Raised when an error occurs within the framework."""

    code: str | None

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        if cls is BaseError:
            raise TypeError("Base error cannot be directly instantiated.")
        return super().__new__(cls, *args, **kwargs)

    def __init__(self, *args: Any) -> None:
        """Initialize a new base error."""
        if len(args) == 0:
            raise TypeError("Base error must have a message.")
        if not hasattr(self, 'code'):
            raise TypeError("Base error must have a code attribute set.")
        super().__init__(*args)

    def message(self) -> str:
        """Return the error message."""
        if len(self.args) == 1:
            return str(self.args[0])
        else:
            return str(self.args)

    def __str__(self) -> str:
        """Return a string representation of the error."""
        message = self.message()
        if self.code is None:
            return message
        message += "\n\n"
        message += f"For further information visit {URL.ERRORS}{self.code}"
        return message


class PlateformeError(BaseError):
    """Raised when a user error occurs within the framework."""

    def __init__(
        self,
        *args: Any,
        code: ERROR_CODES | None = None,
    ) -> None:
        """Initialize a new Plateforme with an optional error code."""
        self.code = code
        super().__init__(*args)


# MARK: Database

class DatabaseError(BaseError):
    """Raised when an error occurs with the database."""

    code = 'database-error'


class SessionError(BaseError):
    """Raised when an error occurs with a database session."""

    code = 'session-error'


class MissingDeferred(BaseError):
    """Raised when a deferred attribute is accessed before it is loaded."""

    code = 'missing-deferred'
