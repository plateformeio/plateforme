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

from enum import StrEnum
from typing import Annotated, Literal, Union

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
    OpenIdConnect,
    SecurityScopes,
)

from ..schema.types import Discriminator
from ..types.networks import HttpUrl
from ..types.secrets import SecretStr
from .parameters import Form

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


class OAuth2ClientType(StrEnum):
    """OAuth2 client type."""
    PUBLIC = 'public'
    CONFIDENTIAL = 'confidential'


class OAuth2FlowType(StrEnum):
    """OAuth2 authorization flow type."""
    AUTHORIZATION_CODE = 'authorization_code'
    CLIENT_CREDENTIALS = 'client_credentials'
    EXTENSION = 'extension'
    IMPLICIT = 'implicit'
    PASSWORD = 'password'


class OAuth2GrantType(StrEnum):
    """OAuth2 authorization grant type."""
    AUTHORIZATION_CODE = 'authorization_code'
    CLIENT_CREDENTIALS = 'client_credentials'
    PASSWORD = 'password'
    REFRESH_TOKEN = 'refresh_token'


class OAuth2ResponseType(StrEnum):
    """OAuth2 authorization response type."""
    CODE = 'code'
    TOKEN = 'token'


class OAuth2RevocationType(StrEnum):
    """OAuth2 token revocation type."""
    MANUAL = 'manual'
    EXPIRATION = 'expiration'
    ROTATION = 'rotation'
    SECURITY = 'security'


class OAuth2TokenType(StrEnum):
    """OAuth2 authorization token type."""
    BASIC = 'basic'
    BEARER = 'bearer'
    MAC = 'mac'


OAuth2AuthorizeEndpointRequestForm = Annotated[
    Union[
        'OAuth2AuthorizationCodeRequestForm',
        'OAuth2ImplicitRequestForm',
    ],
    Discriminator('response_type'),
]
"""The OAuth2 authorize endpoint request form schema."""


OAuth2TokenEndpointRequestForm = Annotated[
    Union[
        'OAuth2AuthorizationTokenRequestForm',
        'OAuth2ClientCredentialsRequestForm',
        'OAuth2PasswordRequestForm',
        'OAuth2RefreshTokenRequestForm',
    ],
    Discriminator('grant_type'),
]
"""The OAuth2 token endpoint request form schema."""


class OAuth2AuthorizationCodeRequestForm:
    """The OAuth2 authorization code request form schema.

    This schema is used to validate the OAuth2 authorization code request form
    parameters for the OAuth2 authorization code flow. It is used to request an
    authorization code from the authorization server code endpoint using the
    authorization code grant type.

    Note:
        For more details, see the OAuth 2.0 authorization specifications:
        - https://www.rfc-editor.org/rfc/rfc6749#section-4.1.1
        - https://www.rfc-editor.org/rfc/rfc7636#section-4.3
    """

    def __init__(
        self,
        *,
        response_type: Annotated[
            Literal[OAuth2ResponseType.CODE],
            Form(
                title='Response type',
                description="""The response type set to `code` for the OAuth2
                    authorization code flow. It is used to distinguish between
                    OAuth2 authorization code and implicit grant types.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-3.1
                    """,
            )
        ] = OAuth2ResponseType.CODE,
        client_id: Annotated[
            str,
            Form(
                title='Client identifier',
                description="""The client identifier for the OAuth2
                    authorization code flow. It is used to identify the client
                    application requesting the authorization code. It must be
                    registered with the authorization server for the OAuth2
                    authorization code flow.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-2.2
                    """,
            )
        ],
        redirect_uri: Annotated[
            HttpUrl | None,
            Form(
                title='Redirect URI',
                description="""The redirect URI for the OAuth2 authorization
                    code flow. It must match one of the redirect URI registered
                    with the specified client.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-3.1.2
                    """,
            ),
        ] = None,
        scope: Annotated[
            str | None,
            Form(
                title='Scope',
                description="""The scope for the OAuth2 authorization code
                    flow. It may be used to request specific permissions from
                    the user for the specified client.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-3.3
                    """,
            ),
        ] = None,
        state: Annotated[
            SecretStr | None,
            Form(
                title='State',
                description="""The state for the OAuth2 authorization code
                    flow. It is an opaque value used by the client application
                    to maintain state between the request and callback. It
                    helps to prevent cross-site request forgery (CSRF) attacks.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-10.12
                    """,
            ),
        ] = None,
        code_challenge: Annotated[
            SecretStr | None,
            Form(
                title='Code challenge',
                description="""The code challenge for the OAuth2 authorization
                    code flow. It is a cryptographically random value used to
                    prevent code injection attacks. It must be generated by the
                    client application using the code verifier.
                    See https://www.rfc-editor.org/rfc/rfc7636#section-4
                    """,
            ),
        ] = None,
        code_challenge_method: Annotated[
            Literal['plain', 'S256'],
            Form(
                title='Code challenge method',
                description="""The code challenge method for the OAuth2
                    authorization code flow. It is used to specify the method
                    used to generate the code challenge. It should be set to
                    `S256` for the OAuth2 authorization code flow.
                    See https://www.rfc-editor.org/rfc/rfc7636#section-4
                    """,
            ),
        ] = 'plain',
        username: Annotated[
            str,
            Form(
                title='Username',
                description="""The username for the OAuth2 authorization code
                    flow. It is used to authenticate the user requesting the
                    authorization code.""",
            ),
        ],
        password: Annotated[
            SecretStr,
            Form(
                title='Password',
                description="""The password for the OAuth2 authorization code
                    flow. It is used to authenticate the user requesting the
                    authorization code.""",
            ),
        ],
    ) -> None:
        self.response_type = response_type
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.scope = scope
        self.state = state
        self.code_challenge = code_challenge
        self.code_challenge_method = code_challenge_method
        self.username = username
        self.password = password


class OAuth2AuthorizationTokenRequestForm:
    """The OAuth2 authorization access token request form schema.

    This schema is used to validate the OAuth2 authorization access token
    request form parameters for the OAuth2 authorization code flow. It is used
    to request an access token from the authorization server token endpoint
    using the authorization code grant type.

    Note:
        For more details, see the OAuth 2.0 authorization specifications:
        - https://www.rfc-editor.org/rfc/rfc6749#section-4.1.3
    """

    def __init__(
        self,
        *,
        grant_type: Annotated[
            Literal[OAuth2GrantType.AUTHORIZATION_CODE],
            Form(
                title='Grant type',
                description="""The grant type set to `authorization_code` for
                    the OAuth2 authorization code flow. It is used to
                    distinguish between OAuth2 grant types.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-4.1.3
                    """,
            )
        ] = OAuth2GrantType.AUTHORIZATION_CODE,
        code: Annotated[
            SecretStr,
            Form(
                title='Code',
                description="""The code for the OAuth2 authorization code flow.
                    It is used to exchange the authorization code for an access
                    token.""",
            ),
        ],
        redirect_uri: Annotated[
            HttpUrl | None,
            Form(
                title='Redirect URI',
                description="""The redirect URI for the OAuth2 authorization
                    code flow. It must match one of the redirect URI registered
                    with the specified client.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-3.1.2
                    """,
            ),
        ] = None,
        client_id: Annotated[
            str | None,
            Form(
                title='Client identifier',
                description="""The client identifier for the OAuth2
                    authorization code flow. It is used to identify the client
                    application requesting the access token. It must be
                    registered with the authorization server for the OAuth2
                    authorization code flow. For confidential clients, using
                    basic authentication instead of including the client
                    credentials in the request body is recommended.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-2.2
                    """,
            ),
        ] = None,
        client_secret: Annotated[
            SecretStr | None,
            Form(
                title='Client secret',
                description="""The client secret for the OAuth2 authorization
                    code flow. It is used to authenticate the client
                    application requesting the access token. It must be
                    registered with the authorization server for the OAuth2
                    authorization code flow. For confidential clients, using
                    basic authentication instead of including the client
                    credentials in the request body is recommended.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-2.3.1
                    """,
            ),
        ] = None,
        code_verifier: Annotated[
            SecretStr | None,
            Form(
                title='Code verifier',
                description="""The code verifier for the OAuth2 authorization
                    code flow. It is used to verify the code challenge sent
                    during the authorization code request.
                    See https://www.rfc-editor.org/rfc/rfc7636#section-4
                    """,
            ),
        ] = None,
    ) -> None:
        self.grant_type = grant_type
        self.code = code
        self.redirect_uri = redirect_uri
        self.client_id = client_id
        self.client_secret = client_secret
        self.code_verifier = code_verifier


class OAuth2ClientCredentialsRequestForm:
    """The OAuth2 client credentials request form schema.

    This schema is used to validate the OAuth2 client credentials request form
    parameters for the OAuth2 client credentials flow. It is used to request an
    access token from the authorization server token endpoint using the client
    credentials grant type.

    Note:
        For more details, see the OAuth 2.0 authorization specifications:
        - https://www.rfc-editor.org/rfc/rfc6749#section-4.4
    """

    def __init__(
        self,
        *,
        grant_type: Annotated[
            Literal[OAuth2GrantType.CLIENT_CREDENTIALS],
            Form(
                title='Grant type',
                description="""The grant type set to `client_credentials` for
                    the OAuth2 client credentials flow. It is used to
                    distinguish between OAuth2 grant types.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-4.4
                    """,
            )
        ] = OAuth2GrantType.CLIENT_CREDENTIALS,
        client_id: Annotated[
            str | None,
            Form(
                title='Client identifier',
                description="""The client identifier for the OAuth2 client
                    credentials flow. It is used to identify the client
                    application requesting the access token. It must be
                    registered with the authorization server for the OAuth2
                    client credentials flow. For confidential clients, using
                    basic authentication instead of including the client
                    credentials in the request body is recommended.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-2.2
                    """,
            ),
        ] = None,
        client_secret: Annotated[
            SecretStr | None,
            Form(
                title='Client secret',
                description="""The client secret for the OAuth2 client
                    credentials flow. It is used to authenticate the client
                    application requesting the access token. It must be
                    registered with the authorization server for the OAuth2
                    client credentials flow. For confidential clients, using
                    basic authentication instead of including the client
                    credentials in the request body is recommended.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-2.3.1
                    """,
            ),
        ] = None,
        scope: Annotated[
            str | None,
            Form(
                title='Scope',
                description="""The scope for the OAuth2 client credentials
                    flow. It may be used to request specific permissions from
                    the user for the specified client.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-3.3
                    """,
            ),
        ] = None,
    ) -> None:
        self.grant_type = grant_type
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope


class OAuth2ImplicitRequestForm:
    """The OAuth2 implicit request form schema.

    This schema is used to validate the OAuth2 implicit request form parameters
    for the OAuth2 implicit flow. It is used to request an access token from
    the authorization server code endpoint using the implicit grant type.

    Note:
        For more details, see the OAuth 2.0 authorization specifications:
        - https://www.rfc-editor.org/rfc/rfc6749#section-4.2.1
    """

    def __init__(
        self,
        *,
        response_type: Annotated[
            Literal[OAuth2ResponseType.TOKEN],
            Form(
                title='Response type',
                description="""The response type set to `token` for the OAuth2
                    implicit flow. It is used to distinguish between OAuth2
                    authorization code and implicit grant types.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-3.1
                    """,
            )
        ] = OAuth2ResponseType.TOKEN,
        client_id: Annotated[
            str,
            Form(
                title='Client identifier',
                description="""The client identifier for the OAuth2 implicit
                    flow. It is used to identify the client application
                    requesting the access token. It must be registered with the
                    authorization server for the OAuth2 implicit flow.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-2.2
                    """,
            )
        ],
        redirect_uri: Annotated[
            HttpUrl | None,
            Form(
                title='Redirect URI',
                description="""The redirect URI for the OAuth2 implicit flow.
                    It must match one of the redirect URI registered with the
                    specified client.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-3.1.2
                    """,
            ),
        ] = None,
        scope: Annotated[
            str | None,
            Form(
                title='Scope',
                description="""The scope for the OAuth2 implicit flow. It
                    may be used to request specific permissions from the user
                    for the specified client.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-3.3
                    """,
            ),
        ] = None,
        state: Annotated[
            SecretStr | None,
            Form(
                title='State',
                description="""The state for the OAuth2 implicit flow. It is an
                    opaque value used by the client application to maintain
                    state between the request and callback. It helps to prevent
                    cross-site request forgery (CSRF) attacks.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-10.12
                    """,
            ),
        ] = None,
        username: Annotated[
            str,
            Form(
                title='Username',
                description="""The username for the OAuth2 implicit flow. It
                    is used to authenticate the user requesting the access
                    token.""",
            ),
        ],
        password: Annotated[
            SecretStr,
            Form(
                title='Password',
                description="""The password for the OAuth2 implicit flow. It
                    is used to authenticate the user requesting the access
                    token.""",
            ),
        ],
    ) -> None:
        self.response_type = response_type
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.scope = scope
        self.state = state
        self.username = username
        self.password = password


class OAuth2PasswordRequestForm:
    """The OAuth2 password request form schema.

    This schema is used to validate the OAuth2 password request form parameters
    for the OAuth2 password flow. It is used to request an access token from
    the authorization server token endpoint using the password grant type.

    Note:
        For more details, see the OAuth 2.0 authorization specifications:
        - https://www.rfc-editor.org/rfc/rfc6749#section-4.3
    """

    def __init__(
        self,
        *,
        grant_type: Annotated[
            Literal[OAuth2GrantType.PASSWORD],
            Form(
                title='Grant type',
                description="""The grant type set to `password` for the OAuth2
                    password flow. It is used to distinguish between OAuth2
                    grant types.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-4.3
                    """,
            )
        ] = OAuth2GrantType.PASSWORD,
        client_id: Annotated[
            str | None,
            Form(
                title='Client identifier',
                description="""The client identifier for the OAuth2 password
                    flow. It is used to identify the client application
                    requesting the access token. It must be registered with the
                    authorization server for the OAuth2 password flow. For
                    confidential clients, using basic authentication instead of
                    including the client credentials in the request body is
                    recommended.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-2.2
                    """,
            )
        ] = None,
        client_secret: Annotated[
            SecretStr | None,
            Form(
                title='Client secret',
                description="""The client secret for the OAuth2 password flow.
                    It is used to authenticate the client application
                    requesting the access token. It must be registered with the
                    authorization server for the OAuth2 password flow. For
                    confidential clients, using basic authentication instead of
                    including the client credentials in the request body is
                    recommended.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-2.3.1
                    """,
            ),
        ] = None,
        scope: Annotated[
            str | None,
            Form(
                title='Scope',
                description="""The scope for the OAuth2 password flow. It may
                    be used to request specific permissions from the user for
                    the specified client.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-3.3
                    """,
            ),
        ] = None,
        username: Annotated[
            str,
            Form(
                title='Username',
                description="""The username for the OAuth2 password flow. It is
                    used to authenticate the user requesting the access token.
                    """,
            ),
        ],
        password: Annotated[
            SecretStr,
            Form(
                title='Password',
                description="""The password for the OAuth2 password flow. It is
                    used to authenticate the user requesting the access token.
                    """,
            ),
        ],
    ) -> None:
        self.grant_type = grant_type
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self.username = username
        self.password = password


class OAuth2RefreshTokenRequestForm:
    """The OAuth2 refresh token request form schema.

    This schema is used to validate the OAuth2 refresh token request form
    parameters for the OAuth2 flows. It is used to request a new access token
    from the authorization server using the refresh token grant type.

    Note:
        For more details, see the OAuth 2.0 authorization specifications:
        - https://www.rfc-editor.org/rfc/rfc6749#section-6
    """

    def __init__(
        self,
        *,
        grant_type: Annotated[
            Literal[OAuth2GrantType.REFRESH_TOKEN],
            Form(
                title='Grant type',
                description="""The grant type set to `refresh_token` for the
                    OAuth2 authorization flows. It is used to distinguish
                    between OAuth2 grant types.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-6
                    """,
            )
        ] = OAuth2GrantType.REFRESH_TOKEN,
        refresh_token: Annotated[
            SecretStr,
            Form(
                title='Refresh token',
                description="""The refresh token for the OAuth2 authorization
                    flows. It is used to exchange the refresh token for a new
                    access token.""",
            ),
        ],
        client_id: Annotated[
            str | None,
            Form(
                title='Client identifier',
                description="""The client identifier for the OAuth2 refresh
                    token. It is used to identify the client application
                    requesting the access token. It must be the same as the
                    client identifier used to obtain the refresh token. For
                    confidential clients, using basic authentication instead of
                    including the client credentials in the request body is
                    recommended.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-2.2
                    """,
            ),
        ],
        client_secret: Annotated[
            SecretStr | None,
            Form(
                title='Client secret',
                description="""The client secret for the OAuth2 refresh token.
                    It is used to authenticate the client application
                    requesting the access token. For confidential clients,
                    using basic authentication instead of including the client
                    credentials in the request body is recommended.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-2.3.1
                    """,
            ),
        ] = None,
        scope: Annotated[
            str,
            Form(
                title='Scope',
                description="""The scope for the OAuth2 access request. It may
                    be used to request specific permissions from the user for
                    the client application. The requested scope must not
                    include any scope not originally granted by the resource
                    owner, and if omitted is treated as equal to the scope
                    originally granted by the resource owner.
                    See https://www.rfc-editor.org/rfc/rfc6749#section-3.3
                    """,
            ),
        ] = '',
    ) -> None:
        self.grant_type = grant_type
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
