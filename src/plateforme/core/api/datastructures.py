# plateforme.core.api.datastructures
# ----------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing data structures within the
Plateforme framework's API using FastAPI and Starlette features.
"""

import dataclasses

from fastapi.datastructures import UploadFile
from starlette.datastructures import (
    URL,
    Address,
    FormData,
    Headers,
    MutableHeaders,
    QueryParams,
    State,
    URLPath,
)

__all__ = (
    'Address',
    'FormData',
    'Headers',
    'JWT',
    'MutableHeaders',
    'QueryParams',
    'State',
    'UploadFile',
    'URL',
    'URLPath',
)


@dataclasses.dataclass(frozen=True, slots=True)
class JWT:
    """A data structure representing a JSON Web Token (JWT)."""

    header: str
    """The header of the token."""

    payload: str
    """The payload of the token storing the claims."""

    signature: str
    """The signature of the token used for verification."""

    def __init__(self, token: str) -> None:
        """Split a JWT token into its header, payload, and signature parts."""
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError('Invalid JWT token format')
        object.__setattr__(self, 'header', parts[0])
        object.__setattr__(self, 'payload', parts[1])
        object.__setattr__(self, 'signature', parts[2])

    def __repr__(self) -> str:
        return "JWT('**********')"

    def __str__(self) -> str:
        return '**********'
