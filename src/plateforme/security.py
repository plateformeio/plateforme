# plateforme.security
# -------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing security within the Plateforme
framework's API using FastAPI and Starlette features.
"""

from .core.api.security import (
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
    OAuth2AuthorizationCodeRequestForm,
    OAuth2AuthorizationTokenRequestForm,
    OAuth2AuthorizeEndpointRequestForm,
    OAuth2ClientCredentialsRequestForm,
    OAuth2ClientType,
    OAuth2FlowType,
    OAuth2GrantType,
    OAuth2ImplicitRequestForm,
    OAuth2PasswordBearer,
    OAuth2PasswordRequestForm,
    OAuth2RefreshTokenRequestForm,
    OAuth2ResponseType,
    OAuth2RevocationType,
    OAuth2TokenEndpointRequestForm,
    OAuth2TokenType,
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
    # OAuth2 (bearers)
    'OAuth2AuthorizationCodeBearer',
    'OAuth2PasswordBearer',
    # OAuth2 (endpoints)
    'OAuth2AuthorizeEndpointRequestForm',
    'OAuth2TokenEndpointRequestForm',
    # OAuth2 (forms)
    'OAuth2AuthorizationCodeRequestForm',
    'OAuth2AuthorizationTokenRequestForm',
    'OAuth2ClientCredentialsRequestForm',
    'OAuth2ImplicitRequestForm',
    'OAuth2PasswordRequestForm',
    'OAuth2RefreshTokenRequestForm',
    # OAuth2 (types)
    'OAuth2ClientType',
    'OAuth2FlowType',
    'OAuth2GrantType',
    'OAuth2ResponseType',
    'OAuth2RevocationType',
    'OAuth2TokenType',
    # Miscellaneous
    'OpenIdConnect',
    'SecurityScopes',
)
