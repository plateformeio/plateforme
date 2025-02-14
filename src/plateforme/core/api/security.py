# plateforme.core.api.security
# ----------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing security within the Plateforme
framework's API using FastAPI and Starlette features.
"""

from fastapi.security import (
    APIKeyCookie,
    APIKeyHeader,
    APIKeyQuery,
    HTTPAuthorizationCredentials,
    HTTPBasic,
    HTTPBasicCredentials,
    HTTPBearer,
    HTTPDigest,
    OAuth2,
    OAuth2AuthorizationCodeBearer,
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
    OAuth2PasswordRequestFormStrict,
    OpenIdConnect,
    SecurityScopes,
)

__all__ = (
    # API
    'APIKeyCookie',
    'APIKeyHeader',
    'APIKeyQuery',
    # HTTP
    'HTTPAuthorizationCredentials',
    'HTTPBasic',
    'HTTPBasicCredentials',
    'HTTPBearer',
    'HTTPDigest',
    # OAuth2
    'OAuth2',
    'OAuth2AuthorizationCodeBearer',
    'OAuth2PasswordBearer',
    'OAuth2PasswordRequestForm',
    'OAuth2PasswordRequestFormStrict',
    # Miscellaneous
    'OpenIdConnect',
    'SecurityScopes',
)
