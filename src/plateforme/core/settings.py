# plateforme.core.settings
# ------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing settings within the Plateforme
framework.
"""

import string
from collections.abc import Sequence
from enum import Enum
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Callable,
    Coroutine,
    Literal,
    Required,
    Self,
    Union,
)

from pydantic_settings import (
    BaseSettings as _BaseSettings,
    SettingsConfigDict as _SettingsConfig,
)
from typing_extensions import TypedDict

from .api.base import APIManager
from .api.middleware import Middleware
from .api.parameters import DependsInfo
from .api.requests import Request
from .api.responses import JSONResponse, Response
from .api.routing import APIRoute, BaseRoute
from .api.types import ASGIApp, Lifespan
from .loaders import Loader
from .patterns import RegexPattern, parse_email
from .schema.aliases import AliasChoices
from .schema.decorators import model_validator
from .schema.fields import Field
from .schema.models import BaseModel, Model, ModelConfig
from .schema.types import Discriminator
from .types.networks import AnyHttpUrl, Email, EngineMap
from .types.secrets import SecretStr
from .typing import DefaultPlaceholder

__all__ = (
    # Information
    'ContactInfo',
    'ContactInfoDict',
    'LicenseInfo',
    'LicenseInfoDict',
    # Settings
    'APIRouterSettings',
    'APIRouterSettingsDict',
    'APISettings',
    'APISettingsDict',
    'LoggingCustomFormatterSettings',
    'LoggingCustomFormatterSettingsDict',
    'LoggingCustomHandlerSettings',
    'LoggingCustomHandlerSettingsDict',
    'LoggingDefaultFormatterSettings',
    'LoggingDefaultFormatterSettingsDict',
    'LoggingFileHandlerSettings',
    'LoggingFileHandlerSettingsDict',
    'LoggingFormatterSettings',
    'LoggingFormatterSettingsDict',
    'LoggingHandlerSettings',
    'LoggingHandlerSettingsDict',
    'LoggingJsonFormatterSettings',
    'LoggingJsonFormatterSettingsDict',
    'LoggingSettings',
    'LoggingSettingsDict',
    'LoggingSimpleFormatterSettings',
    'LoggingSimpleFormatterSettingsDict',
    'LoggingStreamHandlerSettings',
    'LoggingStreamHandlerSettingsDict',
    'NamespaceSettings',
    'NamespaceSettingsDict',
    'PackageSettings',
    'PackageSettingsDict',
    'Settings',
    'SettingsDict',
    # Utilities
    'generate_secret_key',
    'generate_seed_from_path',
    'generate_title',
    'merge_settings',
)


def generate_secret_key(length: int = 32, secure: bool = False) -> str:
    """Generate a secure alphanumeric secret key of the given length."""
    import secrets

    characters = string.ascii_letters + string.digits
    key = ''.join(secrets.choice(characters) for _ in range(length))
    if not secure:
        return f'insecure={key}'
    return key


def generate_seed_from_path(path: str | None = None) -> int:
    """Generates a reproducible seed from a system path."""
    import hashlib
    import sys

    if path is None:
        path = sys.path[0] if sys.path else ''
    seed = int(hashlib.sha256(path.encode()).hexdigest(), 16)
    return seed


def generate_title() -> str:
    """Generate a random title."""
    from random import Random
    generator = Random(generate_seed_from_path())
    title_adjective: str = generator.choice(ADJECTIVES)
    title_noun: str = generator.choice([
        noun for noun in NOUNS if noun[0] != title_adjective[0]
    ])
    return f'{title_adjective} {title_noun}'


# MARK: Contact Information

class ContactInfoDict(TypedDict, total=False):
    """Contact information dictionary."""

    name: Required[str]
    """The name of the contact person or organization."""

    email: Email
    """The email address of the contact person or organization. It must be
    formatted as a valid email address. Defaults to ``None``."""

    url: AnyHttpUrl
    """A URL pointing to the contact information. It must be formatted as a
    valid URL. Defaults to ``None``."""


class ContactInfo(BaseModel):
    """Contact information."""

    __config__ = ModelConfig(
        title='Contact information',
        strict=False,
    )

    name: str = Field(
        ...,
        title='Name',
        description="""The name of the contact person or organization.""",
        examples=['Average Joe', 'Jane Doe'],
    )

    email: Email | None = Field(
        default=None,
        title='Email',
        description="""The email address of the contact person or organization.
            It must be formatted as a valid email address.""",
        examples=['jane.bloggs@example.com', 'john.doe@example.com'],
    )

    url: AnyHttpUrl | None = Field(
        default=None,
        title='URL',
        description="""A URL pointing to the contact information. It must be
            formatted as a valid URL.""",
        examples=['https://example.com/johndoe'],
    )

    @model_validator(mode='before')
    @classmethod
    def __validator__(cls, obj: Any) -> Any:
        if isinstance(obj, str):
            try:
                name, email = parse_email(obj)
                obj = {'name': name, 'email': email}
            except Exception:
                obj = {'name': obj}
        return obj


class LicenseInfoDict(TypedDict, total=False):
    """License information dictionary."""

    name: Required[str]
    """The license name."""

    identifier: str
    """An SPDX license expression. The `identifier` field is mutually exclusive
    with the `url` field. It is available within OpenAPI since version 3.1.0.
    Defaults to ``None``."""

    url: AnyHttpUrl
    """A URL pointing to the license information. The `url` field is mutually
    exclusive with the `identifier` field. Defaults to ``None``."""


# MARK: License Information

class LicenseInfo(BaseModel):
    """License information."""

    __config__ = ModelConfig(
        title='License information',
        strict=False,
    )

    name: str = Field(
        ...,
        title='Name',
        description="""The license name.""",
        examples=['Apache-2.0', 'MIT'],
    )

    identifier: str | None = Field(
        default=None,
        title='Identifier',
        description="""An SPDX license expression. The `identifier` field is
            mutually exclusive with the `url` field. It is available within
            OpenAPI since version 3.1.0.""",
        examples=['GPL-3.0-or-later'],
    )

    url: AnyHttpUrl | None = Field(
        default=None,
        title='URL',
        description="""A URL pointing to the license information. The `url`
            field is mutually exclusive with the `identifier` field.""",
        examples=['https://opensource.org/licenses/MIT'],
    )

    @model_validator(mode='wrap')
    @classmethod
    def __validator__(cls, obj: Any, handler: Any) -> Any:
        if isinstance(obj, str):
            return {'name': obj}
        obj = handler(obj)
        if getattr(obj, 'identifier', None) is not None \
                and getattr(obj, 'url', None) is not None:
            raise ValueError(
                f"Licence information cannot have both `identifier` and `url` "
                f"fields set. Got: {obj}",
            )
        return obj


# MARK: API Router Settings

class APIRouterSettingsDict(TypedDict, total=False):
    """Plateforme API router settings dictionary."""

    dependencies: Sequence[DependsInfo] | None
    """A collection of dependencies to be applied to all the path operations in
    the router (using `Depends`). Defaults to ``None``."""

    default_response_class: type[Response]
    """The default response class to be used for path operations.
    Defaults to `JSONResponse`."""

    responses: dict[int | str, dict[str, Any]] | None
    """Additional responses to be shown in OpenAPI. It will be added to the
    generated OpenAPI, visible at ``'/docs'``. Defaults to ``None``."""

    callbacks: list[BaseRoute] | None
    """OpenAPI callbacks that should apply to all path operations in the
    router. It will be added to the generated OpenAPI, visible at ``'/docs'``.
    Defaults to ``None``."""

    routes: list[BaseRoute] | None
    """A collection of routes to be included in the router to serve incoming
    HTTP and WebSocket requests. This is not recommended for general use, as it
    bypasses the traditional routing system. Defaults to ``None``."""

    redirect_slashes: bool
    """Whether to redirect requests with a trailing slash to the same path
    without the trailing slash. Defaults to ``True``."""

    default: ASGIApp | None
    """The default function handler to be used for the router. It is used to
    handle ``'404 Not Found'`` errors. Defaults to ``None``."""

    dependency_overrides_provider: Any
    """An optional dependency overrides provider used internally by the router.
    Defaults to ``None``."""

    route_class: type[APIRoute]
    """The request route class to be used for the router."""

    lifespan: Lifespan[APIManager] | None
    """The `Lifespan` context manager handler for events to be executed when
    the router starts up and shuts down. It defines a collection of
    `on_startup` and `on_shutdown` events. Defaults to ``None``."""

    include_in_schema: bool
    """Include (or not) all the path operations in the router in the generated
    OpenAPI schema. This affects the generated OpenAPI, visible at ``'/docs'``.
    Defaults to ``True``."""


class APIRouterSettings(BaseModel):
    """Plateforme API router settings."""

    __config__ = ModelConfig(
        title='Plateforme API router settings',
        strict=False,
    )

    dependencies: Sequence[Annotated[DependsInfo, Loader()]] | None = Field(
        default=None,
        title='Dependencies',
        description="""A collection of dependencies to be applied to all the
            path operations in the router (using `Depends`).""",
    )

    default_response_class: Annotated[type[Response], Loader()] = Field(
        default=JSONResponse,
        title='Default response class',
        description="""The default response class to be used for path
            operations.""",
    )

    responses: dict[int | str, dict[str, Any]] | None = Field(
        default=None,
        title='Responses',
        description="""Additional responses to be shown in OpenAPI. It will be
            added to the generated OpenAPI, visible at `'/docs'`.""",
    )

    callbacks: list[Annotated[BaseRoute, Loader()]] | None = Field(
        default=None,
        title='Callbacks',
        description="""OpenAPI callbacks that should apply to all path
            operations in the router. It will be added to the generated
            OpenAPI, visible at `'/docs'`.""",
    )

    routes: list[Annotated[BaseRoute, Loader()]] | None = Field(
        default=None,
        title='Routes',
        description="""A collection of routes to be included in the router to
            serve incoming HTTP and WebSocket requests. This is not recommended
            for general use, as it bypasses the traditional routing system.""",
    )

    redirect_slashes: bool = Field(
        default=True,
        title='Redirect slashes',
        description="""Whether to redirect requests with a trailing slash to
            the same path without the trailing slash.""",
    )

    default: Annotated[ASGIApp, Loader()] | None = Field(
        default=None,
        title='Default',
        description="""The default function handler to be used for the router.
            It is used to handle `404 Not Found` errors.""",
    )

    dependency_overrides_provider: Any = Field(
        default=None,
        title='Dependency overrides provider',
        description="""An optional dependency overrides provider used
            internally by the router.""",
    )

    route_class: Annotated[type[APIRoute], Loader()] = Field(
        default=APIRoute,
        title='Route class',
        description="""The request route class to be used for the router.""",
    )

    lifespan: Annotated[Lifespan[APIManager], Loader()] | None = Field(
        default=None,
        title='Lifespan',
        description="""The `Lifespan` context manager handler for events to be
            executed when the router starts up and shuts down. It defines a
            collection of `on_startup` and `on_shutdown` events.""",
    )

    include_in_schema: bool = Field(
        default=True,
        title='Include in schema',
        description="""Include (or not) all the path operations in the router
            in the generated OpenAPI schema. This affects the generated
            OpenAPI, visible at `'/docs'`.""",
    )


# MARK: API Settings

class APISettingsDict(TypedDict, total=False):
    """Plateforme API settings dictionary."""

    openapi_url: str | None
    """The URL where the OpenAPI schema will be served from. If you set it to
    ``None``, no OpenAPI schema will be served publicly, and the default
    automatic endpoints ``'/docs'`` and ``'/redoc'`` will also be disabled.
    Defaults to ``'/openapi.json'``."""

    openapi_tags: list[dict[str, Any]] | None
    """A list of tags used by OpenAPI, these are the same `tags` you can set in
    the path operations. The order of the tags can be used to specify the order
    shown in tools like Swagger UI, used in the automatic path ``'/docs'``.
    It's not required to specify all the tags used. The tags that are not
    declared MAY be organized randomly or based on the tool's logic. Each tag
    name in the list MUST be unique.
    The value of each item is a dict containing:
    - `name`: The name of the tag.
    - `description`: A short description of the tag. CommonMark syntax MAY be
        used for rich text representation.
    - `externalDocs`: Additional external documentation for this tag. If
        provided, it would contain a dict with:
        - `description`: A short description of the target documentation.
            CommonMark syntax MAY be used for rich text representation.
        - `url`: The URL for the target documentation. Value MUST be in the form
            of a URL.
    Defaults to ``None``."""

    servers: list[dict[str, Any]] | None
    """A list of dicts with connectivity information to a target server. You
    would use it, for example, if your application is served from different
    domains and you want to use the same Swagger UI in the browser to interact
    with each of them (instead of having multiple browser tabs open). Or if you
    want to leave fixed the possible URLs. If the servers list is not provided,
    or is an empty list, the default value would be a dict with a `url` value
    of ``'/'``. Each item in the list is a dict containing:
    - `url`: A URL to the target host. This URL supports Server Variables and
        MAY be relative, to indicate that the host location is relative to the
        location where the OpenAPI document is being served. Variable
        substitutions will be made when a variable is named inside brackets
        ``{}``.
    - `description`: An optional string describing the host designated by the
        URL. CommonMark syntax MAY be used for rich text representation.
    - `variables`: A dict between a variable name and its value. The value is
        used for substitution in the server's URL template.
    Defaults to ``None``."""

    dependencies: Sequence[DependsInfo] | None
    """A collection of dependencies to be applied to all the path operations in
    the router (using `Depends`). Defaults to ``None``."""

    default_response_class: type[Response]
    """The default response class to be used for path operations.
    Defaults to `JSONResponse`."""

    redirect_slashes: bool
    """Whether to redirect requests with a trailing slash to the same path
    without the trailing slash. Defaults to ``True``."""

    docs_url: str | None
    """The path to the automatic interactive API documentation. It is handled
    in the browser by Swagger UI. The default URL is ``'/docs'``. You can
    disable it by setting it to ``None``. If ``openapi_url`` is set to
    ``None``, this will be automatically disabled. Defaults to ``'/docs'``."""

    redoc_url: str | None
    """The path to the alternative automatic interactive API documentation
    provided by ReDoc. The default URL is ``'/redoc'``. You can disable it by
    setting it to ``None``. If ``openapi_url`` is set to ``None``, this will be
    automatically disabled. Defaults to ``'/redoc'``."""

    swagger_ui_oauth2_redirect_url: str | None
    """The OAuth2 redirect endpoint for the Swagger UI. By default it is
    ``/docs/oauth2-redirect``. This is only used if you use OAuth2
    (with the "Authorize" button) with Swagger UI.
    Defaults to ``'/docs/oauth2-redirect'``."""

    swagger_ui_init_oauth: dict[str, Any] | None
    """OAuth2 configuration for the Swagger UI, by default shown at
    ``'/docs'``. Defaults to ``None``."""

    middleware: Sequence[Middleware] | None
    """A list of middleware to be added when creating the application. You can
    do this with `api.add_middleware()` instead. Defaults to ``None``."""

    exception_handlers: dict[
        int | type[Exception],
        Callable[[Request, Any], Coroutine[Any, Any, Response]]
    ] | None
    """A dictionary with handlers for exceptions. You can use the decorator
    `@api.exception_handler()` instead. Defaults to ``None``."""


    lifespan: Lifespan[APIManager] | None
    """The `Lifespan` context manager handler for events to be executed when
    the router starts up and shuts down. It defines a collection of
    `on_startup` and `on_shutdown` events. Defaults to ``None``."""

    openapi_prefix: str
    """A URL prefix for the OpenAPI URL. Defaults to ``''``."""

    root_path: str
    """A path prefix handled by a proxy that is not seen by the application but
    is seen by external clients, which affects things like Swagger UI.
    Defaults to ``''``."""

    root_path_in_servers: bool
    """To disable automatically generating the URLs in the `servers` field in
    the autogenerated OpenAPI using the `root_path`. Defaults to ``True``."""

    responses: dict[int | str, dict[str, Any]] | None
    """Additional responses to be shown in OpenAPI. It will be added to the
    generated OpenAPI, visible at ``'/docs'``. Defaults to ``None``."""

    callbacks: list[BaseRoute] | None
    """OpenAPI callbacks that should apply to all path operations. It will be
    added to the generated OpenAPI, visible at ``'/docs'``.
    Defaults to ``None``."""

    routes: list[BaseRoute] | None
    """A collection of routes to be included in the router to serve incoming
    HTTP and WebSocket requests. This is not recommended for general use, as it
    bypasses the traditional routing system. Defaults to ``None``."""

    webhooks: APIRoute | None
    """Add OpenAPI webhooks. This is similar to `callbacks` but it doesn't
    require a response. Defaults to ``None``."""

    include_in_schema: bool
    """Whether the API should be included in the OpenAPI schema.
    Defaults to ``True``."""

    swagger_ui_parameters: dict[str, Any] | None
    """Additional parameters to pass to the Swagger UI.
    Defaults to ``None``."""

    separate_input_output_schemas: bool
    """Whether input and output schemas should be separate.
    Defaults to ``True``."""

    extra: dict[str, Any]
    """Additional parameters to pass to the application.
    Defaults to an empty dictionary."""


class APISettings(BaseModel):
    """Plateforme API settings."""

    __config__ = ModelConfig(
        title='Plateforme API settings',
        strict=False,
    )

    openapi_url: str | None = Field(
        default='/openapi.json',
        title='OpenAPI URL',
        description="""The URL where the OpenAPI schema will be served from. If
            you set it to `None`, no OpenAPI schema will be served publicly,
            and the default automatic endpoints `'/docs'` and `'/redoc'` will
            also be disabled.""",
    )

    openapi_tags: list[dict[str, Any]] | None = Field(
        default=None,
        title='OpenAPI tags',
        description="""A list of tags used by OpenAPI, these are the same
            `tags` you can set in the path operations. The order of the tags
            can be used to specify the order shown in tools like Swagger UI,
            used in the automatic path `'/docs'`. It's not required to specify
            all the tags used. The tags that are not declared MAY be organized
            randomly or based on the tool's logic. Each tag name in the list
            MUST be unique. The value of each item is a dict containing:
            - `name`: The name of the tag.
            - `description`: A short description of the tag. CommonMark syntax
                MAY be used for rich text representation.
            - `externalDocs`: Additional external documentation for this tag.
                If provided, it would contain a dict with:
                - `description`: A short description of the target
                    documentation. CommonMark syntax MAY be used for rich text
                    representation.
                - `url`: The URL for the target documentation. Value MUST be in
                    the form of a URL.
            """,
    )

    servers: list[dict[str, Any]] | None = Field(
        default=None,
        title='Servers',
        description="""A list of dicts with connectivity information to a
            target server. You would use it, for example, if your application
            is served from different domains and you want to use the same
            Swagger UI in the browser to interact with each of them (instead of
            having multiple browser tabs open). Or if you want to leave fixed
            the possible URLs. If the servers list is not provided, or is an
            empty list, the default value would be a dict with a `url` value of
            `/`. Each item in the list is a dict containing:
            - `url`: A URL to the target host. This URL supports Server
                Variables and MAY be relative, to indicate that the host
                location is relative to the location where the OpenAPI document
                is being served. Variable substitutions will be made when a
                variable is named inside brackets `{}`.
            - `description`: An optional string describing the host designated
                by the URL. CommonMark syntax MAY be used for rich text
                representation.
            - `variables`: A dict between a variable name and its value. The
                value is used for substitution in the server's URL template.
            """,
    )

    dependencies: Sequence[Annotated[DependsInfo, Loader()]] | None = Field(
        default=None,
        title='Dependencies',
        description="""A list of global dependencies, they will be applied to
            each path operation, including in sub-routers.""",
    )

    default_response_class: Annotated[type[Response], Loader()] = Field(
        default=JSONResponse,
        title='Default response class',
        description="""The default response class to be used.""",
    )

    redirect_slashes: bool = Field(
        default=True,
        title='Redirect slashes',
        description="""Whether to detect and redirect slashes in URLs when the
            client doesn't use the same format.""",
    )

    docs_url: str | None = Field(
        default='/docs',
        title='Docs URL',
        description="""The path to the automatic interactive API documentation.
            It is handled in the browser by Swagger UI. The default URL is
            `'/docs'`. You can disable it by setting it to `None`. If
            `openapi_url` is set to `None`, this will be automatically
            disabled.""",
    )

    redoc_url: str | None = Field(
        default='/redoc',
        title='ReDoc URL',
        description="""The path to the alternative automatic interactive API
            documentation provided by ReDoc. The default URL is `'/redoc'`. You
            can disable it by setting it to `None`. If `openapi_url` is set to
            `None`, this will be automatically disabled.""",
    )

    swagger_ui_oauth2_redirect_url: str | None = Field(
        default='/docs/oauth2-redirect',
        title='Swagger UI OAuth2 redirect URL',
        description="""The OAuth2 redirect endpoint for the Swagger UI. By
            default it is `'/docs/oauth2-redirect'`. This is only used if you
            use OAuth2 (with the "Authorize" button) with Swagger UI.""",
    )

    swagger_ui_init_oauth: dict[str, Any] | None = Field(
        default=None,
        title='Swagger UI init OAuth',
        description="""OAuth2 configuration for the Swagger UI, by default
            shown at `'/docs'`.""",
    )

    middleware: Sequence[Annotated[Middleware, Loader()]] | None = Field(
        default=None,
        title='Middleware',
        description="""A list of middleware to be added when creating the
            application. You can do this with `api.add_middleware()`
            instead.""",
    )

    exception_handlers: Annotated[
        dict[
            int | type[Exception],
            Callable[[Request, Any], Coroutine[Any, Any, Response]],
        ],
        Loader(),
    ] | None = Field(
        default=None,
        title='Exception handlers',
        description="""A dictionary with handlers for exceptions. You can use
            the decorator `@api.exception_handler()` instead.""",
    )

    lifespan: Annotated[Lifespan[APIManager], Loader()] | None = Field(
        default=None,
        title='Lifespan',
        description="""The `Lifespan` context manager handler for events to be
            executed when the router starts up and shuts down. It defines a
            collection of `on_startup` and `on_shutdown` events.""",
    )

    openapi_prefix: str = Field(
        default='',
        title='OpenAPI prefix',
        description="""A URL prefix for the OpenAPI URL.""",
    )

    root_path: str = Field(
        default='',
        title='Root path',
        description="""A path prefix handled by a proxy that is not seen by the
            application but is seen by external clients, which affects things
            like Swagger UI.""",
    )

    root_path_in_servers: bool = Field(
        default=True,
        title='Root path in servers',
        description="""To disable automatically generating the URLs in the
            `servers` field in the autogenerated OpenAPI using the `root_path`.
            Defaults to `True`.""",
    )

    responses: dict[int | str, dict[str, Any]] | None = Field(
        default=None,
        title='Responses',
        description="""Additional responses to be shown in OpenAPI. It will be
            added to the generated OpenAPI, visible at `'/docs'`.""",
    )

    callbacks: list[Annotated[BaseRoute, Loader()]] | None = Field(
        default=None,
        title='Callbacks',
        description="""OpenAPI callbacks that should apply to all path
            operations. It will be added to the generated OpenAPI, visible at
            `'/docs'`.""",
    )

    routes: list[Annotated[BaseRoute, Loader()]] | None = Field(
        default=None,
        title='Routes',
        description="""A collection of routes to be included in the router to
            serve incoming HTTP and WebSocket requests. This is not recommended
            for general use, as it bypasses the traditional routing system.""",
    )

    webhooks: Annotated[APIRoute, Loader()] | None = Field(
        default=None,
        title='Webhooks',
        description="""Add OpenAPI webhooks. This is similar to `callbacks` but
            it doesn't require a response.""",
    )

    include_in_schema: bool = Field(
        default=True,
        title='Include in schema',
        description="""Whether the API should be included in the OpenAPI
            schema.""",
    )

    swagger_ui_parameters: dict[str, Any] | None = Field(
        default=None,
        title='Swagger UI parameters',
        description="""Additional parameters to pass to the Swagger UI.""",
    )

    separate_input_output_schemas: bool = Field(
        default=True,
        title='Separate input output schemas',
        description="""Whether input and output schemas should be separate.""",
    )

    extra: dict[str, Any] = Field(
        default_factory=dict,
        title='Extra',
        description="""Additional parameters to pass to the application.""",
    )


# MARK: Logging Formatter Settings

LoggingFormatterSettingsDict = Union[
    'LoggingCustomFormatterSettingsDict',
    'LoggingDefaultFormatterSettingsDict',
    'LoggingJsonFormatterSettingsDict',
    'LoggingSimpleFormatterSettingsDict',
]
"""Plateforme logging formatter settings dictionary."""


LoggingFormatterSettings = Union[
    'LoggingCustomFormatterSettings',
    'LoggingDefaultFormatterSettings',
    'LoggingJsonFormatterSettings',
    'LoggingSimpleFormatterSettings',
]
"""Plateforme logging formatter settings."""


# MARK:> Custom Formatter

class LoggingCustomFormatterSettingsDict(TypedDict, total=False):
    """Plateforme logging custom formatter settings dictionary."""

    type: Required[Literal['custom']]
    """The type of the formatter set as ``'custom'`` and used to discriminate
    between different formatter types."""

    cls: Required[str]
    """The fully qualified name of the custom formatter class to use. This
    should be a subclass of `logging.Formatter`."""

    extra: dict[str, Any] | None
    """Extra parameters to pass to the custom formatter."""


class LoggingCustomFormatterSettings(BaseModel):
    """Plateforme logging custom formatter settings."""

    __config__ = ModelConfig(
        title='Logging custom formatter settings',
        extra='allow',
        frozen=True,
        strict=False,
    )

    type_: Literal['custom'] = Field(
        default='custom',
        alias='type',
        title='Formatter type',
        description="""The type of the formatter set as `'custom'` and used to
            discriminate between different formatter types.""",
        init=False,
    )

    cls: str = Field(
        ...,
        alias='class',
        validation_alias=AliasChoices('class', 'cls'),
        title='Formatter class',
        description="""The fully qualified name of the custom formatter class
            to use. This should be a subclass of `logging.Formatter`.""",
        examples=['my_module.MyCustomFormatter'],
    )

    @model_validator(mode='before')
    @classmethod
    def __validator__(cls, obj: Any) -> Any:
        if isinstance(obj, dict):
            # Handle extra parameters
            extra = obj.pop('extra', {})
            obj.update(extra)
        return obj


# MARK:> Default Formatter

class LoggingDefaultFormatterSettingsDict(TypedDict, total=False):
    """Plateforme logging default formatter settings dictionary."""

    type: Required[Literal['default']]
    """The type of the formatter set as ``'default'`` and used to discriminate
    between different formatter types."""

    asctime: bool
    """Human-readable time when the `LogRecord` was created. By default this is
    of the form ``'2003-07-08T16:49:45+0100'``. Format: ``'%(asctime)s'``.
    Defaults to ``False``."""

    use_colors: bool
    """Whether to use colors in the log output. This is only available in the
    default formatter. Defaults to ``False``."""


class LoggingDefaultFormatterSettings(BaseModel):
    """Plateforme logging default formatter settings."""

    __config__ = ModelConfig(
        title='Logging default formatter settings',
        frozen=True,
        strict=False,
    )

    type_: Literal['default'] = Field(
        default='default',
        alias='type',
        title='Formatter type',
        description="""The type of the formatter set as `'default'` and used to
            discriminate between different formatter types.""",
        init=False,
    )

    asctime: bool = Field(
        default=False,
        title='Asctime',
        description="""Human-readable time when the `LogRecord` was created. By
            default this is of the form `'2003-07-08T16:49:45+0100'`.
            Format: `'%(asctime)s'`""",
    )

    use_colors: bool = Field(
        default=False,
        title='Use colors',
        description="""Whether to use colors in the log output. This is only
            available in the default formatter.""",
    )


# MARK:> JSON Formatter

class LoggingJsonFormatterSettingsDict(TypedDict, total=False):
    """Plateforme logging JSON formatter settings dictionary."""

    type: Required[Literal['json']]
    """The type of the formatter set as ``'json'`` and used to discriminate
    between different formatter types."""

    levelname: bool
    """Text logging level for the message (``'DEBUG'``, ``'INFO'``,
    ``'WARNING'``, ``'ERROR'``, ``'CRITICAL'``). Defaults to ``True``."""

    levelno: bool
    """Numeric logging level for the message (``DEBUG``, ``INFO``, ``WARNING``,
    ``ERROR``, ``CRITICAL``). Defaults to ``False``."""

    message: bool
    """The logged message, computed as ``msg % args``. This is set when
    ``Formatter.format()`` is invoked. Defaults to ``True``."""

    timestamp: bool
    """Human-readable timestamp when the `LogRecord` was created with timezone
    information. This is of the form ``'2024-01-19T03:04:40.131729+00:00'``
    (the numbers after the dot are millisecond portion of the time, and the
    timezone is UTC). Defaults to ``True``."""

    asctime: bool
    """Human-readable time when the `LogRecord` was created. By default this is
    of the form ``'2003-07-08T16:49:45+0100'``. Defaults to ``False``."""

    created: bool
    """Time when the `LogRecord` was created
    (as returned by `time.time_ns() / 1e9`). Defaults to ``False``."""

    msecs: bool
    """Millisecond portion of the time when the `LogRecord` was created.
    Defaults to ``False``."""

    name: bool
    """Name of the logger used to log the call. Defaults to ``True``."""

    module: bool
    """Module (name portion of `filename`). Defaults to ``True``."""

    funtion: bool
    """Name of function containing the logging call. Defaults to ``True``."""

    lineno: bool
    """Source line number where the logging call was issued (if available).
    Defaults to ``True``."""

    args: bool
    """The tuple of arguments merged into `msg` to produce `message`, or a dict
    whose values are used for the merge (when there is only one argument, and
    it is a dictionary). Defaults to ``False``."""

    msg: bool
    """The format string passed in the original logging call. Merged with
    `args` to produce `message`, or an arbitrary object.
    Defaults to ``False``."""

    pathname: bool
    """Full pathname of the source file where the logging call was issued
    (if available). Defaults to ``False``."""

    filename: bool
    """Filename portion of `pathname`. Defaults to ``False``."""

    process: bool
    """Process ID (if available). Defaults to ``False``."""

    process_name: bool
    """Process name (if available). Defaults to ``False``."""

    relative_created: bool
    """Time in milliseconds when the `LogRecord` was created, relative to the
    time the logging module was loaded. Defaults to ``False``."""

    exc_info: bool
    """Exception tuple (like `sys.exc_info`) or, if no exception has occurred,
    `None`. Defaults to ``False``."""

    stack_info: bool
    """Stack frame information (where available) from the bottom of the stack
    in the current thread, up to and including the stack frame of the logging
    call. Defaults to ``False``."""

    task_name: bool
    """A `asyncio.Task` name (if available). Defaults to ``False``."""

    thread: bool
    """Thread ID (if available). Defaults to ``False``."""

    thread_name: bool
    """Thread name (if available). Defaults to ``False``."""

    extra: bool
    """Wheiher to include all the user-defined extra fields in the log record.
    If ``True``, the extra attributes of the log record will be serialized as a
    dictionary and included in the log record. Otherwise, the extra attributes
    will be ignored. Defaults to ``True``."""


class LoggingJsonFormatterSettings(BaseModel):
    """Plateforme logging JSON formatter settings."""

    __config__ = ModelConfig(
        title='Logging JSON formatter settings',
        frozen=True,
        strict=False,
    )

    type_: Literal['json'] = Field(
        default='json',
        alias='type',
        title='Formatter type',
        description="""The type of the formatter set as `'json'` and used to
            discriminate between different formatter types.""",
        init=False,
    )

    levelname: bool = Field(
        default=True,
        title='Level name',
        description="""Text logging level for the message
            (`'DEBUG'`, `'INFO'`, `'WARNING'`, `'ERROR'`, `'CRITICAL'`).
            Format: `'%(levelname)s'`""",
    )

    levelno: bool = Field(
        default=False,
        title='Level number',
        description="""Numeric logging level for the message
            (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
            Format: `'%(levelno)s'`""",
    )

    message: bool = Field(
        default=True,
        title='Message',
        description="""The logged message, computed as `msg % args`. This is
            set when `Formatter.format()` is invoked.
            Format: `'%(message)s'`""",
    )

    timestamp: bool = Field(
        default=True,
        title='Timestamp',
        description="""Human-readable timestamp when the `LogRecord` was
            created with timezone information. This is of the form
            `'2024-01-19T03:04:40.131729+00:00'` (the numbers after the dot are
            millisecond portion of the time, and the timezone is UTC)."""
    )

    asctime: bool = Field(
        default=False,
        title='Asctime',
        description="""Human-readable time when the `LogRecord` was created. By
            default this is of the form `'2003-07-08T16:49:45+0100'`.
            Format: `'%(asctime)s'`""",
    )

    created: bool = Field(
        default=False,
        title='Created',
        description="""Time when the `LogRecord` was created (as returned by
            `time.time_ns()` / 1e9).
            Format: `'%(created)f'`""",
    )

    msecs: bool = Field(
        default=False,
        title='Milliseconds',
        description="""Millisecond portion of the time when the `LogRecord` was
            created.
            Format: `'%(msecs)d'`""",
    )

    name: bool = Field(
        default=True,
        title='Name',
        description="""Name of the logger used to log the call.
            Format: `'%(name)s'`""",
    )

    module: bool = Field(
        default=True,
        title='Module',
        description="""Module (name portion of `filename`).
            Format: `'%(module)s'`""",
    )

    funtion: bool = Field(
        default=True,
        title='Function name',
        description="""Name of function containing the logging call.
            Format: `'%(funcName)s'`""",
    )

    lineno: bool = Field(
        default=True,
        title='Line number',
        description="""Source line number where the logging call was issued
            (if available).
            Format: `'%(lineno)d'`""",
    )

    args: bool = Field(
        default=False,
        title='Arguments',
        description="""The tuple of arguments merged into `msg` to produce
            `message`, or a dict whose values are used for the merge (when
            there is only one argument, and it is a dictionary).""",
    )

    msg: bool = Field(
        default=False,
        title='Message',
        description="""The format string passed in the original logging call.
            Merged with `args` to produce `message`, or an arbitrary
            object.""",
    )

    pathname: bool = Field(
        default=False,
        title='Pathname',
        description="""Full pathname of the source file where the logging call
            was issued (if available).
            Format: `'%(pathname)s'`""",
    )

    filename: bool = Field(
        default=False,
        title='File name',
        description="""Filename portion of `pathname`.
            Format: `'%(filename)s'`""",
    )

    process: bool = Field(
        default=False,
        title='Process',
        description="""Process ID (if available).
            Format: `'%(process)d'`""",
    )

    process_name: bool = Field(
        default=False,
        title='Process name',
        description="""Process name (if available).
            Format: `'%(processName)s'`""",
    )

    relative_created: bool = Field(
        default=False,
        title='Relative created',
        description="""Time in milliseconds when the LogRecord was created,
            relative to the time the logging module was loaded.
            Format: `'%(relativeCreated)d'`""",
    )

    exc_info: bool = Field(
        default=False,
        title='Exception information',
        description="""Exception tuple (like `sys.exc_info`) or, if no
            exception has occurred, `None`.""",
    )

    stack_info: bool = Field(
        default=False,
        title='Stack information',
        description="""Stack frame information (where available) from the
            bottom of the stack in the current thread, up to and including the
            stack frame of the logging call which resulted in the creation of
            this record.""",
    )

    task_name: bool = Field(
        default=False,
        title='Task name',
        description="""A `asyncio.Task` name (if available).
            Format: `'%(taskName)s'`""",
    )

    thread: bool = Field(
        default=False,
        title='Thread',
        description="""Thread ID (if available).
            Format: `'%(thread)d'`""",
    )

    thread_name: bool = Field(
        default=True,
        title='Thread name',
        description="""Thread name (if available).
            Format: `'%(threadName)s'`""",
    )

    extra: bool = Field(
        default=True,
        title='Extra',
        description="""Wheiher to include all the user-defined extra fields in
            the log record. If `True`, the extra attributes of the log record
            will be serialized as a dictionary and included in the log record.
            Otherwise, the extra attributes will be ignored.""",
    )


# MARK:> Simple Formatter

class LoggingSimpleFormatterSettingsDict(TypedDict, total=False):
    """Plateforme logging simple formatter settings dictionary."""

    type: Required[Literal['simple']]
    """The type of the formatter set as ``'simple'`` and used to discriminate
    between different formatter types."""

    format: str
    """A format string in the given style for the logged output as a whole. The
    possible mapping keys are drawn from the `LogRecord` object's attributes.
    If not specified, ``'%(message)s'`` is used, which is just the logged
    message. Defaults to
    ``'[%(asctime)s] %(levelname)-8s: %(module)s:%(lineno)d - %(message)s'``.
    """

    datefmt: str
    """A format string in the given style for the date/time portion of the
    logged output. If not specified, the default described in `formatTime()` is
    used. Defaults to ``'%Y-%m-%dT%H:%M:%S%z'``."""

    style: Literal['%', '{', '$']
    """Can be one of ``'%'``, ``'{'``, or ``'$'`` and determines how the format
    string will be merged with its data: using one of printf-style String
    Formatting (%), `str.format()` ({) or `string.Template` ($). This only
    applies to fmt and datefmt (e.g. ``'%(message)s'`` versus ``'{message}'``),
    not to the actual log messages passed to the logging methods. However,
    there are other ways to use ``'{'``- and ``'$'``-formatting for log
    messages. Defaults to ``'%'``."""

    raise_errors: bool
    """If ``True``, incorrect or mismatched `format` and `style` will raise a
    ValueError. Defaults to ``True``."""

    defaults: dict[str, Any] | None
    """A dictionary with default values to use in custom fields.
    Defaults to ``None``."""


class LoggingSimpleFormatterSettings(BaseModel):
    """Plateforme logging simple formatter settings."""

    __config__ = ModelConfig(
        title='Logging simple formatter settings',
        frozen=True,
        strict=False,
    )

    type_: Literal['simple'] = Field(
        default='simple',
        alias='type',
        title='Formatter type',
        description="""The type of the formatter set as `'simple'` and used to
            discriminate between different formatter types.""",
        init=False,
    )

    format: str = Field(
        default=(
            '[%(asctime)s] %(levelname)-8s: '
            + '%(module)s:%(lineno)d - %(message)s'
        ),
        title='Format',
        description="""A format string in the given style for the logged
            output as a whole. The possible mapping keys are drawn from the
            `LogRecord` object's attributes. If not specified, `'%(message)s'`
            is used, which is just the logged message.""",
        examples=['%(asctime)s - %(message)s'],
    )

    datefmt: str = Field(
        default='%Y-%m-%dT%H:%M:%S%z',
        title='Date format',
        description="""A format string in the given style for the date/time
            portion of the logged output. If not specified, the default
            described in `formatTime()` is used.
            Defaults to `'%Y-%m-%dT%H:%M:%S%z'`""",
        examples=['%Y-%m-%d', '%Y-%m-%d %H:%M:%S'],
    )

    style: Literal['%', '{', '$'] = Field(
        default='%',
        title='Style',
        description="""Can be one of `'%'`, `'{'`, or `'$'` and determines how
            the format string will be merged with its data: using one of
            printf-style String Formatting (%), `str.format()` ({) or
            `string.Template` ($). This only applies to fmt and datefmt (e.g.
            `'%(message)s'` versus `'{message}'`), not to the actual log
            messages passed to the logging methods. However, there are other
            ways to use `'{'`- and `'$'`-formatting for log messages.""",
    )

    raise_errors: bool  = Field(
        default=True,
        alias='validate',
        title='Validate and raise errors',
        description="""If `True`, incorrect or mismatched `format` and `style`
            will raise a ValueError.""",
    )

    defaults: dict[str, Any] | None = Field(
        default=None,
        title='Defaults',
        description="""A dictionary with default values to use in custom
            fields.""",
    )


# MARK: Logging Handler Settings

LoggingHandlerSettingsDict = Union[
    'LoggingCustomHandlerSettingsDict',
    'LoggingFileHandlerSettingsDict',
    'LoggingStreamHandlerSettingsDict',
]
"""Plateforme logging handler settings dictionary."""


LoggingHandlerSettings = Union[
    'LoggingCustomHandlerSettings',
    'LoggingFileHandlerSettings',
    'LoggingStreamHandlerSettings',
]
"""Plateforme logging handler settings."""


# MARK:> Custom Handler

class LoggingCustomHandlerSettingsDict(TypedDict, total=False):
    """Plateforme logging custom handler settings dictionary."""

    type: Required[Literal['custom']]
    """The type of the handler set as ``'custom'`` and used to discriminate
    between different handler types."""

    cls: Required[str]
    """The fully qualified name of the custom handler class to use. This should
    be a subclass of `logging.Handler`."""

    level: Literal[
        'DEBUG',
        'INFO',
        'WARNING',
        'ERROR',
        'CRITICAL',
    ] | None
    """The logging level for the custom handler. Defaults to ``None``."""

    filters: list[str] | None
    """A list of logging filters to use for the custom handler. Each filter
    should be a fully qualified name of the filter class.
    Defaults to ``None``."""

    formatter: str
    """The formatter name to use for the custom handler.
    Defaults to ``'default'``."""

    extra: dict[str, Any] | None
    """Extra parameters to pass to the custom handler."""


class LoggingCustomHandlerSettings(BaseModel):
    """Plateforme logging custom handler settings."""

    __config__ = ModelConfig(
        title='Logging custom handler settings',
        extra='allow',
        frozen=True,
        strict=False,
    )

    type_: Literal['custom'] = Field(
        default='custom',
        alias='type',
        title='Handler type',
        description="""The type of the handler set as `'custom'` and used to
            discriminate between different handler types.""",
        init=False,
    )

    cls: str = Field(
        ...,
        alias='class',
        validation_alias=AliasChoices('class', 'cls'),
        title='Handler class',
        description="""The fully qualified name of the custom handler class
            to use. This should be a subclass of `logging.Handler`.""",
        examples=['my_module.MyCustomHandler'],
    )

    level: Literal[
        'DEBUG',
        'INFO',
        'WARNING',
        'ERROR',
        'CRITICAL',
    ] | None = Field(
        default=None,
        title='Level',
        description="""The logging level for the custom handler.""",
        examples=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
    )

    filters: list[str] | None = Field(
        default=None,
        title='Filters',
        description="""A list of logging filters to use for the custom handler.
            Each filter should be a fully qualified name of the filter
            class.""",
        examples=['my_module.MyCustomFilter'],
    )

    formatter: str = Field(
        default='default',
        title='Formatter',
        description="""The formatter name to use for the custom handler.""",
        examples=['default', 'color', 'json', 'my_custom'],
    )

    @model_validator(mode='before')
    @classmethod
    def __validator__(cls, obj: Any) -> Any:
        if isinstance(obj, dict):
            # Handle extra parameters
            extra = obj.pop('extra', {})
            obj.update(extra)
        return obj


# MARK:> File Handler

class LoggingFileHandlerSettingsDict(TypedDict, total=False):
    """Plateforme logging file handler settings dictionary."""

    type: Required[Literal['file']]
    """The type of the handler set as ``'file'`` and used to discriminate
    between different handler types."""

    level: Literal[
        'DEBUG',
        'INFO',
        'WARNING',
        'ERROR',
        'CRITICAL',
    ] | None
    """The logging level for the file handler. Defaults to ``None``."""

    filters: list[str] | None
    """A list of logging filters to use for the file handler. Each filter
    should be a fully qualified name of the filter class.
    Defaults to ``None``."""

    formatter: str
    """The formatter name to use for the file handler.
    Defaults to ``'json'``."""

    filename: str | None
    """The filename to use for the handler. If not provided, the handler will
    use the default filename ``'logs/plateforme.log'``, or
    ``'logs/plateforme.jsonl'`` if the JSON formatter is used.
    Defaults to ``None``."""

    max_bytes: int
    """The maximum number of bytes to store in the log file before rotating the
    file. Defaults to ``10485760``."""

    backup_count: int
    """The number of backup files to keep when rotating the log file.
    Defaults to ``5``."""


class LoggingFileHandlerSettings(BaseModel):
    """Plateforme logging file handler settings."""

    __config__ = ModelConfig(
        title='Logging file hHandler settings',
        frozen=True,
        strict=False,
    )

    type_: Literal['file'] = Field(
        default='file',
        alias='type',
        title='Handler type',
        description="""The type of the handler set as `'file'` and used to
            discriminate between different handler types.""",
        init=False,
    )

    level: Literal[
        'DEBUG',
        'INFO',
        'WARNING',
        'ERROR',
        'CRITICAL',
    ] | None = Field(
        default=None,
        title='Level',
        description="""The logging level for the file handler.""",
        examples=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
    )

    filters: list[str] | None = Field(
        default=None,
        title='Filters',
        description="""A list of logging filters to use for the file handler.
            Each filter should be a fully qualified name of the filter
            class.""",
        examples=['my_module.MyCustomFilter'],
    )

    formatter: str = Field(
        default='json',
        title='Formatter',
        description="""The formatter name to use for the file handler.""",
        examples=['default', 'color', 'json', 'my_custom'],
    )

    filename: str | None = Field(
        default=None,
        title='Filename',
        description="""The filename to use for the handler. If not provided,
            the handler will use the default filename `'logs/plateforme.log'`,
            or `'logs/plateforme.jsonl'` if the JSON formatter is used.""",
        examples=['my_app_errors.log', 'my_app.jsonl'],
    )

    max_bytes: int = Field(
        default=10485760,
        title='Max bytes',
        description="""The maximum number of bytes to store in the log file
            before rotating the file.""",
        examples=[5242880, 10485760, 52428800],
    )

    backup_count: int = Field(
        default=5,
        title='Backup count',
        description="""The number of backup files to keep when rotating the log
            file.""",
        examples=[3, 5, 10],
    )

    @model_validator(mode='after')
    def __validator__(self) -> Self:
        if self.filename is None:
            if self.formatter == 'json':
                self.__dict__['filename'] = 'logs/plateforme.jsonl'
            else:
                self.__dict__['filename'] = 'logs/plateforme.log'
        return self


# MARK:> Stream Handler

class LoggingStreamHandlerSettingsDict(TypedDict, total=False):
    """Plateforme logging stream handler settings dictionary."""

    type: Required[Literal['stream']]
    """The type of the handler set as ``'stream'`` and used to discriminate
    between different handler types."""

    level: Literal[
        'DEBUG',
        'INFO',
        'WARNING',
        'ERROR',
        'CRITICAL',
    ] | None
    """The logging level for the stream handler. Defaults to ``None``."""

    filters: list[str] | None
    """A list of logging filters to use for the stream handler. Each filter
    should be a fully qualified name of the filter class.
    Defaults to ``None``."""

    formatter: str
    """The formatter name to use for the stream handler.
    Defaults to ``'default'``."""

    stream: str
    """The stream to use for the handler.
    Defaults to ``'ext://sys.stdout'``."""


class LoggingStreamHandlerSettings(BaseModel):
    """Plateforme logging stream handler settings."""

    __config__ = ModelConfig(
        title='Logging stream handler settings',
        frozen=True,
        strict=False,
    )

    type_: Literal['stream'] = Field(
        default='stream',
        alias='type',
        title='Handler type',
        description="""The type of the handler set as `'stream'` and used to
            discriminate between different handler types.""",
        init=False,
    )

    level: Literal[
        'DEBUG',
        'INFO',
        'WARNING',
        'ERROR',
        'CRITICAL',
    ] | None = Field(
        default=None,
        title='Level',
        description="""The logging level for the stream handler.""",
        examples=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
    )

    filters: list[str] | None = Field(
        default=None,
        title='Filters',
        description="""A list of logging filters to use for the stream handler.
            Each filter should be a fully qualified name of the filter
            class.""",
        examples=['my_module.MyCustomFilter'],
    )

    formatter: str = Field(
        default='default',
        title='Formatter',
        description="""The formatter name to use for the stream handler.""",
        examples=['default', 'color', 'json', 'my_custom'],
    )

    stream: str = Field(
        default='ext://sys.stdout',
        title='Stream',
        description="""The stream to use for the handler.""",
        examples=['ext://sys.stdout', 'ext://sys.stderr'],
    )


# MARK: Logging Settings

class LoggingSettingsDict(TypedDict, total=False):
    """Plateforme logging settings dictionary."""

    level: Literal[
        'DEBUG',
        'INFO',
        'WARNING',
        'ERROR',
        'CRITICAL',
    ]
    """The logging level for the application. Defaults to ``'INFO'``."""

    filters: dict[str, str]
    """A dictionary of logging filters used in the application with their names
    as keys and the fully qualified name of the filter class as values. By
    default, it includes one built-in filter under the key ``'no_errors'`` that
    can be overridden. If provided, the custom filters are merged with these
    defaults. Defaults to an empty dictionary."""

    formatters: dict[
        str, LoggingFormatterSettings | LoggingFormatterSettingsDict
    ]
    """A dictionary of logging formatters used in the application. By default,
    it includes three built-in formatters under the keys ``'default'``,
    ``'color'``, and ``'json'`` that can be overridden. If provided, the custom
    formatters are merged with these defaults.
    Defaults to an empty dictionary."""

    handlers: dict[
        str, LoggingHandlerSettings | LoggingHandlerSettingsDict
    ]
    """A dictionary of logging handlers used in the application. By default, it
    includes two built-in handlers under the keys ``'stdout'`` and ``'stderr'``
    that can be overridden. If provided, the custom handlers are merged with
    these defaults. Defaults to an empty dictionary."""


class LoggingSettings(BaseModel):
    """Plateforme logging settings."""

    __config__ = ModelConfig(
        title='Plateforme logging settings',
        frozen=True,
        strict=False,
    )

    level: Literal[
        'DEBUG',
        'INFO',
        'WARNING',
        'ERROR',
        'CRITICAL',
    ] = Field(
        default='INFO',
        title='Level',
        description="""The logging level for the application.""",
        examples=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
    )

    filters: dict[str, str] = Field(
        default_factory=dict,
        title='Filters',
        description="""A dictionary of logging filters used in the application
            with their names as keys and the fully qualified name of the filter
            class as values. By default, it includes one built-in filter under
            the key `'no_errors'` that can be overridden. If provided, the
            custom filters are merged with these defaults.""",
        examples=[
            {'my_custom': 'my_module.MyCustomFilter'},
            {'no_errors': 'my_module.MyCustomNoErrorFilter'},
        ],
    )

    formatters: dict[
        str, Annotated[LoggingFormatterSettings, Discriminator('type_')]
    ] = Field(
        default_factory=dict,
        title='Formatters',
        description="""A dictionary of logging formatters used in the
            application. By default, it includes three built-in formatters
            under the keys `'default'`, `'color'`, and `'json'` that can be
            overridden. If provided, the custom formatters are merged with
            these defaults.""",
        examples=[
            {'my_custom': 'LoggingCustomFormatterSettings(...)'},
            {'default': 'LoggingSimpleFormatterSettings(...)'},
            {'json': 'LoggingCustomFormatterSettings(...)'},
        ],
    )

    handlers: dict[
        str, Annotated[LoggingHandlerSettings, Discriminator('type_')]
    ] = Field(
        default_factory=dict,
        title='Handlers',
        description="""A dictionary of logging handlers used in the
            application. By default, it includes two built-in handlers under
            the keys `'stdout'` and `'stderr'` that can be overridden. If
            provided, the custom handlers are merged with these defaults.""",
        examples=[
            {'my_custom': 'LoggingCustomHandlerSettings(...)'},
            {'stdout': 'LoggingStreamHandlerSettings(...)'},
        ],
    )

    @model_validator(mode='after')
    def __validator__(self) -> Self:
        # Set default filters
        self.filters.setdefault(
            'no_errors', 'plateforme.logging.NoErrorFilter'
        )
        # Set default formatters
        self.formatters.setdefault(
            'default', LoggingDefaultFormatterSettings()
        )
        self.formatters.setdefault(
            'color', LoggingDefaultFormatterSettings(use_colors=True)
        )
        self.formatters.setdefault(
            'json', LoggingJsonFormatterSettings()
        )
        # Set default handlers
        self.handlers.setdefault('stdout', LoggingStreamHandlerSettings(
            level=None,
            stream='ext://sys.stdout',
            filters=['no_errors'],
            formatter='color',
        ))
        self.handlers.setdefault('stderr', LoggingStreamHandlerSettings(
            level='WARNING',
            stream='ext://sys.stderr',
            formatter='color',
        ))
        return self


# MARK: Namespace Settings

class NamespaceSettingsDict(TypedDict, total=False):
    """Plateforme namespace settings dictionary."""

    alias: str | None
    """The namespace alias used to define which database schema should store
    its resources in an application. Multiple namespaces can share the same
    alias within an application. It must be formatted to snake case and
    defaults to the namespace unique name (e.g. ``'my_namespace'`` for
    ``'my_namespace'``). Defaults to ``None``."""

    slug: str | None
    """The namespace slug used to define which URL path should be used to
    access the namespace resources in an API. Multiple namespaces can share the
    same slug within an application. It must be formatted to kebab case and
    defaults to the kebab case of the namespace unique name
    (e.g. ``'my-namespace'`` for ``'my_namespace'``). Defaults to ``None``."""

    title: str | None
    """The namespace human-readable title that is used to display the namespace
    verbose name within an application. It defaults to the titleized version of
    the namespace unique name (e.g. ``'My Namepsace'`` for ``'my_namespace'``).
    It is used within the API and will be added to the generated OpenAPI,
    visible at ``'/docs'``. Defaults to ``None``."""

    summary: str | None
    """A short summary of the namespace. It will be added to the generated
    OpenAPI, visible at ``'/docs'``. Defaults to ``None``."""

    description: str | None
    """A description of the namespace. Supports Markdown (using CommonMark
    syntax). It will be added to the generated OpenAPI, visible at ``'/docs'``.
    Defaults to ``None``."""

    version: str | None
    """The namespace version. It is used to define the version of the
    namespace, not the version of the OpenAPI specification or the version of
    the Plateforme framework being used. It will be added to the generated
    OpenAPI, visible at ``'/docs'``. If not set, it will defaults to the
    application version. Defaults to ``None``."""

    contact: ContactInfo | ContactInfoDict | str | None
    """The contact information for the namespace exposed API. It can be
    provided either as a string with the contact name and optionally an email
    address, or as a dictionary. The following fields will be added to the
    generated OpenAPI, visible at ``'/docs'``:
    - `name` (str): The name of the contact person or organization. If not
        provided, it defaults to an empty string.
    - `url` (str): An URL pointing to the contact information. It must be
        formatted as a valid URL.
    - `email` (str): The email address of the contact person or organization.
        It must be formatted as a valid email address.
    Defaults to ``None``."""

    license: LicenseInfo | LicenseInfoDict | str | None
    """The license information for the namespace exposed API. It can be
    provided either as a string with the license name, or as a dictionary. The
    following fields will be added to the generated OpenAPI, visible at
    ``'/docs'``:
    - `name` (str): The license name used for the API.
    - `identifier` (str): An SPDX license expression for the API. The
        `identifier` field is mutually exclusive of the `url` field.
        Available since OpenAPI 3.1.0.
    - `url` (str): An URL to the license used for the API. This must be
        formatted as a valid URL.
    Defaults to ``None``."""

    terms_of_service: str | None
    """A URL to the Terms of Service for the namespace exposed API. It will be
    added to the generated OpenAPI, visible at ``'/docs'``.
    Defaults to ``None``."""

    api: APISettings | APISettingsDict
    """The namespace API settings. Defaults to an empty dictionary."""

    api_max_depth: int
    """The maximum depth to walk through the resource path to collect manager
    methods from resource dependencies. It is used to generate the API routes
    for resources within the namespace. Defaults to ``2``."""

    api_max_selection: int
    """The limit of resources to return for the API route selections. It is
    used when generating the API routes for resources within the namespace to
    avoid too many resources being returned. Defaults to ``20``."""

    deprecated: bool | None
    """Whether the namespace is deprecated. Defaults to ``None``."""


class NamespaceSettings(BaseModel):
    """Plateforme namespace settings."""

    __config__ = ModelConfig(
        title='Plateforme namespace settings',
        strict=False,
    )

    alias: str | None = Field(
        default=None,
        title='Alias',
        description="""The namespace alias used to define which database schema
            should store its resources in an application. Multiple namespaces
            can share the same alias within an application. It must be
            formatted to snake case and defaults to the namespace unique name
            (e.g. `my_namespace` for `my_namespace`).""",
        examples=['my_namespace'],
        max_length=63,
        pattern=r'^$|' + RegexPattern.ALIAS,
    )

    slug: str | None = Field(
        default=None,
        title='Slug',
        description="""The namespace slug used to define which URL path should
            be used to access the namespace resources in an API. Multiple
            namespaces can share the same slug within an application. It must
            be formatted to kebab case and defaults to the kebab case of the
            namespace unique name (e.g. `my-namespace` for `my_namespace`).""",
        examples=['my-namepsace'],
        max_length=63,
        pattern=r'^$|' + RegexPattern.SLUG,
    )

    title: str | None = Field(
        default=None,
        title='Title',
        description="""The namespace human-readable title that is used to
            display the namespace verbose name within an application. It
            defaults to the titleized version of the namespace unique name
            (e.g. `My Namepsace` for `my_namespace`). It is used within the API
            and will be added to the generated OpenAPI, visible at `'/docs'`.
            """,
        examples=['My Namespace'],
        min_length=1,
        max_length=63,
        pattern=RegexPattern.TITLE,
    )

    summary: str | None = Field(
        default=None,
        title='Summary',
        description="""A short summary of the namespace. It will be added to
            the generated OpenAPI, visible at `'/docs'`.""",
        examples=['This is a namespace summary'],
    )

    description: str | None = Field(
        default=None,
        title='Description',
        description="""A description of the namespace. Supports Markdown (using
            CommonMark syntax). It will be added to the generated OpenAPI,
            visible at `'/docs'`.""",
        examples=['This is a namespace description.'],
    )

    version: str | None = Field(
        default=None,
        title='Version',
        description="""The namespace version. It is used to define the version
            of the namespace, not the version of the OpenAPI specification or
            the version of the Plateforme framework being used. It will be
            added to the generated OpenAPI, visible at `'/docs'`. If not set,
            it will defaults to the application version.""",
        examples=['0.1.0', '0.1.0-a1', '2.1.1'],
        pattern=RegexPattern.VERSION,
    )

    contact: ContactInfo | None = Field(
        default=None,
        title='Contact',
        description="""The contact information for the namespace exposed API.
            It can be provided either as a string with the contact name and
            optionally an email address, or as a dictionary. The following
            fields will be added to the generated OpenAPI, visible at
            `'/docs'`:
            - `name` (str): The name of the contact person or organization. If
                not provided, it defaults to an empty string.
            - `url` (str): An URL pointing to the contact information. It must
                be formatted as a valid URL.
            - `email` (str): The email address of the contact person or
                organization. It must be formatted as a valid email address.
            """,
        examples=[
            'Average Joe',
            'Jane Bloggs <jane.bloggs@example.com>',
            {'name': 'John Doe', 'email': 'john.doe@example.com'},
        ],
    )

    license: LicenseInfo | None = Field(
        default=None,
        title='License information',
        description="""The license information for the namespace exposed API.
            It can be provided either as a string with the license name, or as
            a dictionary. The following fields will be added to the generated
            OpenAPI, visible at `'/docs'`:
            - `name` (str): The license name used for the API.
            - `identifier` (str): An SPDX license expression for the API. The
                `identifier` field is mutually exclusive of the `url` field.
                Available since OpenAPI 3.1.0.
            - `url` (str): An URL to the license used for the API. This must be
                formatted as a valid URL.
            """,
        examples=[
            'Apache 2.0',
            {'name': 'GPL', 'identifier': 'GPL-3.0-or-later'},
            {'name': 'LGPL', 'file': 'LICENSE'},
            {'name': 'MIT', 'url': 'https://opensource.org/licenses/MIT'},
        ],
    )

    terms_of_service: str | None = Field(
        default=None,
        title='Terms of service',
        description="""A URL to the Terms of Service for the namespace exposed
            API. It will be added to the generated OpenAPI, visible at
            `'/docs'`.""",
        examples=['https://example.com/terms-of-service'],
    )

    api: APISettings = Field(
        default=APISettings(),
        title='API',
        description="""The namespace API settings.""",
    )

    api_max_depth: int = Field(
        default=2,
        title='API maximum route depth',
        gt=0,
        description="""The maximum depth to walk through the resource path to
            collect manager methods from resource dependencies. It is used to
            generate the API routes for resources within the namespace.""",
    )

    api_max_selection: int = Field(
        default=20,
        title='API maximum route selection',
        gt=0,
        description="""The limit of resources to return for the API route
            selections. It is used when generating the API routes for resources
            within the namespace to avoid too many resources being returned.
            """,
    )

    deprecated: bool | None = Field(
        default=None,
        title='Deprecated',
        description="""Whether the namespace is deprecated.""",
    )


# MARK: Package Settings

class PackageSettingsDict(TypedDict, total=False):
    """Plateforme package settings dictionary."""

    namespace: str | None
    """The package namespace name that is used to load the package and its
    resources within an application. It is used to group resources and avoid
    name collisions. Defaults to ``None``."""

    tags: list[str | Enum] | None
    """A list of tags to be applied to all the path operations in the package
    router. It will be added to the generated OpenAPI, visible at ``'/docs'``.
    If not provided, it defaults to the package slug. Defaults to ``None``."""

    auto_mount: bool
    """Whether to automatically mount the package within the API. When
    disabled, the package must be manually mounted. Defaults to ``True``."""

    api: APIRouterSettings | APIRouterSettingsDict
    """The package API settings. Defaults to an empty dictionary."""

    api_max_depth: int
    """The maximum depth to walk through the resource path to collect manager
    methods from resource dependencies. It is used to generate the API routes
    for resources within the package. Defaults to ``2``."""

    api_max_selection: int
    """The limit of resources to return for the API route selections. It is
    used when generating the API routes for resources within the package to
    avoid too many resources being returned. Defaults to ``20``."""

    api_resources: bool | Sequence[str]
    """A boolean, or a list of module or resource fully qualified names
    relative to the package that declares the top-level resources to include
    from the package within the API. When set to ``True``, it includes all
    resources exposed within the ``__init__.py`` file of the package. When set
    to ``False``, the API will not include any resources from the package.
    Permissions and access control can be applied to these resources.
    Defaults to ``True``."""

    api_services: bool | Sequence[str]
    """A boolean, or a list of module or service fully qualified names relative
    to the package that declares the services to include from the package
    within the API. When set to ``True``, it includes all services exposed
    within the ``__init__.py`` file of the package. When set to ``False``, the
    API will not include any services from the package. Permissions and access
    control can be applied to these services. Defaults to ``True``."""

    deprecated: bool | None
    """Whether the package is deprecated. Defaults to ``None``."""

    file_path: str | None
    """A string that defines the filesystem path of the package module. It is
    used to load package related assets from the filesystem. It defaults to the
    resolved package module path when not provided. Defaults to ``None``."""


class PackageSettings(BaseModel):
    """Plateforme package settings."""

    __config__ = ModelConfig(
        title='Plateforme package settings',
        strict=False,
    )

    namespace: str | None = Field(
        default=None,
        title='Namespace',
        description="""The package namespace name that is used to load the
            package and its resources within an application. It is used to
            group resources and avoid name collisions.""",
        examples=[None, 'users', 'my_app'],
        max_length=63,
        pattern=r'^$|' + RegexPattern.ALIAS,
    )

    tags: list[str | Enum] | None = Field(
        default=None,
        title='Tags',
        description="""A list of tags to be applied to all the path operations
            in the package router. It will be added to the generated OpenAPI,
            visible at `'/docs'`. If not provided, it defaults to the package
            slug.""",
        examples=[['products'], ['auth', 'users']],
    )

    auto_mount: bool = Field(
        default=True,
        title='Auto mount',
        description="""Whether to automatically mount the package within the
            API. When disabled, the package must be manually mounted.""",
    )

    api: APIRouterSettings = Field(
        default=APIRouterSettings(),
        title='API',
        description="""The package API settings.""",
    )

    api_max_depth: int = Field(
        default=2,
        title='API maximum route depth',
        gt=0,
        lt=5,
        description="""The maximum depth to walk through the resource path to
            collect manager methods from resource dependencies. It is used to
            generate the API routes for resources within the package.""",
    )

    api_max_selection: int = Field(
        default=20,
        title='API maximum route selection',
        gt=0,
        description="""The limit of resources to return for the API route
            selections. It is used when generating the API routes for resources
            within the package to avoid too many resources being returned.
            """,
    )

    api_resources: bool | Sequence[str] = Field(
        default=True,
        title='Top-level resources exposed to the API',
        description="""A boolean, or a list of module or resource fully
            qualified names relative to the package that declares the top-level
            resources to include from the package within the API. When set to
            `True`, it includes all resources exposed within the `__init__.py`
            file of the package. When set to `False`, the API will not include
            any resources from the package. Permissions and access control can
            be applied to these resources.
            """,
        examples=[True, False, ['users.User', 'users.UserGroup']],
    )

    api_services: bool | Sequence[str] = Field(
        default=True,
        title='Services exposed to the API',
        description="""A boolean, or a list of module or service fully
            qualified names relative to the package that declares the services
            to include from the package within the API. When set to `True`, it
            includes all services exposed within the `__init__.py` file of the
            package. When set to `False`, the API will not include any services
            from the package. Permissions and access control can be applied to
            these services.""",
        examples=[True, False, ['AuthService', 'users.UserService']],
    )

    deprecated: bool | None = Field(
        default=None,
        title='Deprecated',
        description="""Whether the package is deprecated.""",
    )

    file_path: str | None = Field(
        default=None,
        title='File path',
        description="""A string that defines the filesystem path of the package
            module. It is used to load package related assets from the
            filesystem. It defaults to the resolved package module path when
            not provided.""",
        examples=['/path/to/my_app/core/items'],
    )


# MARK: Settings

class SettingsDict(TypedDict, total=False):
    """Plateforme application settings dictionary."""

    # Environment
    context: bool
    """Whether to set up and maintain the application context in the current
    thread when creating the instance. When enabled, the application context
    will be set to the current application being initialized, and won't require
    an explicit context manager. Defaults to ``True``."""

    debug: bool
    """Whether to run the application in debug mode. When debug mode is
    enabled, debug tracebacks will be returned on server and the application
    will automatically reload when changes are detected in the underlying code.
    Defaults to ``False``."""

    secret_key: SecretStr | str
    """The application secret key. If not provided, a random alphanumeric
    secret key marked as insecure will be generated. Please note that it must
    be kept secret and should not be shared, it's insecure to use a secret key
    in a public repository. Consider using an environment variable instead.
    Defaults to a random secret key."""

    # Information
    title: str
    """The application human-readable title that is used to display the
    application verbose name and will be added to the generated OpenAPI,
    visible at ``'/docs'``. When not provided, a random title will be
    generated. Defaults to a random title."""

    summary: str | None
    """A short summary of the application. It will be added to the generated
    OpenAPI, visible at ``'/docs'``. Defaults to ``None``."""

    description: str | None
    """A description of the application. Supports Markdown (using CommonMark
    syntax). It will be added to the generated OpenAPI, visible at ``'/docs'``.
    Defaults to ``None``."""

    version: str
    """The application version. It is used to define the version of the
    application, not the version of the OpenAPI specification or the version
    of the Plateforme framework being used. It will be added to the generated
    OpenAPI, visible at ``'/docs'``. Defaults to ``'0.1.0'``."""

    contact: ContactInfo | ContactInfoDict | str | None
    """The contact information for the application exposed API. It can be
    provided either as a string with the contact name and optionally an email
    address, or as a dictionary. The following fields will be added to the
    generated OpenAPI, visible at ``'/docs'``:
    - `name` (str): The name of the contact person or organization. If not
        provided, it defaults to an empty string.
    - `url` (str): An URL pointing to the contact information. It must be
        formatted as a valid URL.
    - `email` (str): The email address of the contact person or organization.
        It must be formatted as a valid email address.
    Defaults to ``None``."""

    license: LicenseInfo | LicenseInfoDict | str | None
    """The license information for the application exposed API. It can be
    provided either as a string with the license name, or as a dictionary. The
    following fields will be added to the generated OpenAPI, visible at
    ``'/docs'``:
    - `name` (str): The license name used for the API.
    - `identifier` (str): An SPDX license expression for the API. The
        `identifier` field is mutually exclusive of the `url` field.
        Available since OpenAPI 3.1.0.
    - `url` (str): An URL to the license used for the API. This must be
        formatted as a valid URL.
    Defaults to ``None``."""

    terms_of_service: str | None
    """A URL to the Terms of Service for the application exposed API. It will
    be added to the generated OpenAPI, visible at ``'/docs'``.
    Defaults to ``None``."""

    # Internationalization
    language: str
    """The application language code. Defaults to ``'en'``."""

    timezone: str
    """The application time zone code. Defaults to ``'UTC'``."""

    # Application
    auto_import_dependencies: bool
    """Whether to automatically import dependencies of the application
    packages. Auto-imported package dependencies are implemented with their
    default settings. Defaults to ``True``."""

    auto_import_namespaces: bool
    """Whether to automatically import and create missing namespace
    configurations for packages within the application.
    Defaults to ``True``."""

    namespaces: Sequence[
        str | tuple[str, NamespaceSettings | NamespaceSettingsDict]
    ]
    """The application namespaces to load. Each namespace can be provided
    either as a string for the namespace name or a tuple with the namespace
    name and its settings. The namespace name is used to group package
    resources and services within the application to avoid name collisions.
    The default namespace uses the empty string as its name ``''``. The
    namespace settings are used to override the default namespace
    implementation configuration. Defaults to an empty list."""

    packages: Sequence[
        str | tuple[str, PackageSettings | PackageSettingsDict]
    ]
    """The application packages to load. Each package can be provided either
    as a string for the package name or a tuple with the package name and its
    settings. The package name is used to load the package with its resources
    and services within the application. The package settings are used to
    override the default package implementation configuration. The default
    special package symbol ``$`` is used to reference the application caller
    package and load its module resources and services.
    Defaults to a list with the special package symbol ``'$'``."""

    api: APISettings | APISettingsDict
    """The API settings. Defaults to the default API settings."""

    api_max_depth: int
    """The maximum depth to walk through the resource path to collect manager
    methods from resource dependencies. It is used to generate the API routes
    for resources within the application. Defaults to ``2``."""

    api_max_selection: int
    """The limit of resources to return for the API route selections. It is
    used when generating the API routes for resources within the application
    to avoid too many resources being returned. Defaults to ``20``."""

    database_engines: EngineMap | dict[str, Path | str] | Path | str
    """The application database engines. It accepts either:
    - A string with the database engine URL such as ``':memory:'`` for an
        in-memory SQLite database, a path to a SQLite database file, or a
        database URL for other database engines.
    - A dictionary with the database engine URL for the default engine and
        other engines.
    Defaults to ``':memory:'``."""

    database_routers: Sequence[str]
    """The application database routers. A list of either module names from
    which to import database routers, or fully qualified names of database
    routers. Defaults to an empty list."""

    logging: LoggingSettings | LoggingSettingsDict | bool
    """Whether to enable logging in the application. When enabled, the
    application will log messages to the configured handlers. It accepts either
    a boolean to enable or disable default logging settings or a dictionary
    with custom logging settings. Defaults to ``True``."""

    deprecated: bool | None
    """Whether the application is deprecated. Defaults to ``None``."""


class Settings(_BaseSettings):
    """Plateforme application settings."""

    __config__ = _SettingsConfig(
        title='Plateforme settings',
        strict=True,
        env_prefix='PLATEFORME_',
    )

    # Environment
    context: bool = Field(
        default=True,
        title='Context',
        description="""Whether to set up and maintain the application context
            in the current thread when creating the instance. When enabled, the
            application context will be set to the current application being
            initialized, and won't require an explicit context manager.""",
    )

    debug: bool = Field(
        default=False,
        title='Debug',
        description="""Whether to run the application in debug mode. When debug
            mode is enabled, debug tracebacks will be returned on server and
            the application will automatically reload when changes are detected
            in the underlying code.""",
    )

    secret_key: SecretStr = Field(
        default_factory=generate_secret_key,
        title='Secret key',
        description="""The application secret key. If not provided, a random
            alphanumeric secret key marked as insecure will be generated.
            Please note that it must be kept secret and should not be shared,
            it's insecure to use a secret key in a public repository. Consider
            using an environment variable instead.""",
        examples=[
            'insecure=Hem0LXHceecXptMNngpewGLYMpVKybKf',
            '92MVatlzf3xRhrNSDLzPOi2kbSs3q0Da',
        ],
        min_length=8,
        max_length=1024,
    )

    # Information
    title: str = Field(
        default_factory=generate_title,
        title='Title',
        description="""The application human-readable title that is used to
            display the application verbose name and will be added to the
            generated OpenAPI, visible at `'/docs'`. When not provided, a
            random title will be generated.""",
        examples=['My Plateforme'],
        min_length=1,
        max_length=63,
        pattern=RegexPattern.TITLE,
    )

    summary: str | None = Field(
        default=None,
        title='Summary',
        description="""A short summary of the application. It will be added to
            the generated OpenAPI, visible at `'/docs'`.""",
        examples=['My Plateforme application summary'],
    )

    description: str | None = Field(
        default=None,
        title='Description',
        description="""A description of the application. Supports Markdown
            (using CommonMark syntax). It will be added to the generated
            OpenAPI, visible at `'/docs'`.""",
        examples=['This is a Plateforme application description.'],
    )

    version: str = Field(
        default='0.1.0',
        title='Version',
        description="""The application version. It is used to define the
            version of the application, not the version of the OpenAPI
            specification or the version of the Plateforme framework being
            used. It will be added to the generated OpenAPI, visible at
            `'/docs'`.""",
        examples=['0.1.0', '0.1.0-a1', '2.1.1'],
        pattern=RegexPattern.VERSION,
    )

    contact: ContactInfo | None = Field(
        default=None,
        title='Contact',
        description="""The contact information for the application exposed API.
            It can be provided either as a string with the contact name and
            optionally an email address, or as a dictionary. The following
            fields will be added to the generated OpenAPI, visible at
            `'/docs'`:
            - `name` (str): The name of the contact person or organization. If
                not provided, it defaults to an empty string.
            - `url` (str): An URL pointing to the contact information. It must
                be formatted as a valid URL.
            - `email` (str): The email address of the contact person or
                organization. It must be formatted as a valid email address.
            """,
        examples=[
            'Average Joe',
            'Jane Bloggs <jane.bloggs@example.com>',
            {'name': 'John Doe', 'email': 'john.doe@example.com'},
        ],
    )

    license: LicenseInfo | None = Field(
        default=None,
        title='License information',
        description="""The license information for the application exposed API.
            It can be provided either as a string with the license name, or as
            a dictionary. The following fields will be added to the generated
            OpenAPI, visible at `'/docs'`:
            - `name` (str): The license name used for the API.
            - `identifier` (str): An SPDX license expression for the API. The
                `identifier` field is mutually exclusive of the `url` field.
                Available since OpenAPI 3.1.0.
            - `url` (str): An URL to the license used for the API. This must be
                formatted as a valid URL.
            """,
        examples=[
            'Apache 2.0',
            {'name': 'GPL', 'identifier': 'GPL-3.0-or-later'},
            {'name': 'LGPL', 'file': 'LICENSE'},
            {'name': 'MIT', 'url': 'https://opensource.org/licenses/MIT'},
        ],
    )

    terms_of_service: str | None = Field(
        default=None,
        title='Terms of service',
        description="""A URL to the Terms of Service for the application
            exposed API. It will be added to the generated OpenAPI, visible at
            `'/docs'`.""",
        examples=['https://example.com/terms-of-service'],
    )

    # Internationalization
    language: str = Field(
        default='en',
        title='Language',
        description="""The application language code.""",
        examples=['en-US', 'fr'],
        pattern=RegexPattern.LANGUAGE,
    )

    timezone: str = Field(
        default='UTC',
        title='Time zone',
        description="""The application time zone code.""",
        examples=['UTC', 'Europe/Paris'],
        max_length=63,
    )

    # Application
    auto_import_dependencies: bool = Field(
        default=True,
        title='Auto import package dependencies',
        description="""Whether to automatically import dependencies of the
            application packages. Auto-imported package dependencies are
            implemented with their default settings.""",
    )

    auto_import_namespaces: bool = Field(
        default=True,
        title='Auto import namespaces',
        description="""Whether to automatically import and create missing
            namespace configurations for packages within the application.""",
    )

    namespaces: Sequence[str | tuple[str, NamespaceSettings]] = Field(
        default_factory=list,
        title='Namespaces',
        description="""The application namespaces to load. Each namespace can
            be provided either as a string for the namespace name or a tuple
            with the namespace name and its settings. The namespace name is
            used to group package resources and services within the application
            to avoid name collisions. The default namespace uses the empty
            string as its name `''`. The namespace settings are used to
            override the default namespace implementation configuration.""",
        examples=['', ('items', {'api_max_depth': 3})],
    )

    packages: Sequence[str | tuple[str, PackageSettings]] = Field(
        default_factory=lambda: ['$'],
        title='Packages',
        description="""The application packages to load. Each package can be
            provided either as a string for the package name or a tuple with
            the package name and its settings. The package name is used to load
            the package with its resources and services within the application.
            The package settings are used to override the default package
            implementation configuration. The default special package symbol
            `$` is used to reference the application caller package and load
            its module resources and services.""",
        examples=[
            'plateforme.users',
            ('my_app', {'namespace': 'my_app'}),
        ],
    )

    api: APISettings = Field(
        default=APISettings(),
        title='API',
        description="""The API settings.""",
    )

    api_max_depth: int = Field(
        default=2,
        title='API maximum route depth',
        gt=0,
        lt=5,
        description="""The maximum depth to walk through the resource path to
            collect manager methods from resource dependencies. It is used to
            generate the API routes for resources within the application.""",
    )

    api_max_selection: int = Field(
        default=20,
        title='API maximum route selection',
        gt=0,
        description="""The limit of resources to return for the API route
            selections. It is used when generating the API routes for resources
            within the application to avoid too many resources being returned.
            """,
    )

    database_engines: EngineMap = Field(
        default=':memory:',
        validate_default=True,
        title='Database engines',
        description="""The application database engines.""",
        examples=[
            ':memory:',
            'path/to/my_database.db',
            'sqlite:///path/to/my_database.db',
            'postgresql://postgres:postgres@localhost:5432/my_database',
            {
                'default': 'my_database.db',
                'other': 'my_other_database.db',
            },
            {
                'default': {
                    'scheme': 'postgresql',
                    'user': 'postgres',
                    'password': 'postgres',
                    'host': 'localhost',
                    'port': 5432,
                    'database': 'my_database',
                },
                'other': {
                    'scheme': 'sqlite',
                    'database': 'my_other_database.db',
                },
            },
        ],
    )

    database_routers: Sequence[str] = Field(
        default=[],
        title='Database routers',
        description="""The application database routers. A list of either
            module names from which to import database routers, or fully
            qualified names of database routers.""",
    )

    logging: LoggingSettings | bool = Field(
        default=True,
        title='Logging',
        description="""Whether to enable logging in the application. When
            enabled, the application will log messages to the configured
            handlers. It accepts either a boolean to enable or disable default
            logging settings or a dictionary with custom logging settings.""",
        examples=[
            True,
            False,
            {
                'level': 'DEBUG',
                'handlers': {
                    'file_json': {
                        'type': 'file',
                        'formatter': 'json',
                        'filename': 'my_app.jsonl',
                    },
                    'file_text': {
                        'type': 'file',
                        'level': 'ERROR',
                        'formatter': 'default',
                        'filename': 'my_app_errors.log',
                    },
                },
            },
        ],
    )

    deprecated: bool | None = Field(
        default=None,
        title='Deprecated',
        description="""Whether the application is deprecated.""",
    )


# MARK: Utilities

def merge_settings(
    settings: Model,
    *others: BaseModel | None,
    **update: Any,
) -> Model:
    """Merge multiple settings into a single settings instance.

    It copies the provided settings model instance and merges other settings
    model instances into for matching fields. The last settings model instance
    has precedence over the previous ones. Additional settings can be provided
    as keyword arguments, where a `DefaultPlaceholder` can be used to set a
    default value for a field when no previous settings have set it.

    Args:
        settings: The settings model instance to copy and use as a base.
        *others: The other settings model instances to merge into the base.
        **update: Values to add/modify within the new model. Note that the
            integrity of the data is not validated when creating the new model.
            Data should be trusted or pre-validated in this case. Additionaly
            it can include `DefaultPlaceholder` values to set default values
            for settings model fields.

    Returns:
        The merged settings model instance.

    Raises:
        ValidationError: If the merged settings are invalid.
    """
    # Create a new settings model instance
    data = settings.model_dump(exclude_defaults=True)

    # Merge other settings
    for other in others:
        if other is None:
            continue
        for key in other.model_fields_set:
            if key not in settings.model_fields:
                continue
            settings_field = settings.model_fields[key]
            other_field = other.model_fields[key]
            if settings_field.annotation == other_field.annotation:
                data[key] = getattr(other, key)

    # Update settings
    for key, value in update.items():
        if key not in settings.model_fields:
            continue
        if isinstance(value, DefaultPlaceholder):
            if key in data:
                continue
            data[key] = value.value
        else:
            data[key] = value

    # Validate settings
    return settings.model_construct(**data)


ADJECTIVES = (
    'Apex', 'Arc', 'Astro', 'Atomic', 'Black', 'Blue', 'Call', 'Cold',
    'Core', 'Cyber', 'Dark', 'Data', 'Deep', 'Delta', 'Dual', 'Edge',
    'Epsilon', 'Fast', 'Flat', 'Flow', 'Flux', 'Gamma', 'Gen', 'Gray',
    'Grid', 'Hard', 'Hash', 'Heavy', 'High', 'Hot', 'Hyper', 'Iron',
    'Kappa', 'Lab', 'Lambda', 'Late', 'Lead', 'Lens', 'Line', 'Mod',
    'Mass', 'Max', 'Mega', 'Nano', 'Neo', 'Net', 'Neural', 'Nova',
    'Omega', 'Port', 'Prime', 'Proto', 'Pull', 'Quad', 'Raw', 'Red',
    'Sharp', 'Sigma', 'Solid', 'Sub', 'Tech', 'Var', 'Wire', 'Zeta',
)
"""A list of adjectives used to generate random application titles."""


NOUNS = (
    'Array', 'Axis', 'Base', 'Bit', 'Block', 'Bool', 'Boot', 'Buffer',
    'Bus', 'Byte', 'Cache', 'Cell', 'Chain', 'Cube', 'Dict', 'Diff',
    'Disk', 'Dock', 'Eval', 'Exec', 'File', 'Flag', 'Frame', 'Func',
    'Gate', 'Graph', 'Group', 'Heap', 'Hook', 'Host', 'Hub', 'Init',
    'Int', 'Item', 'Join', 'Key', 'Link', 'List', 'Loop', 'Map',
    'Mesh', 'Mode', 'Num', 'Node', 'Null', 'Page', 'Path', 'Pipe',
    'Pod', 'Pool', 'Proc', 'Queue', 'Ram', 'Ring', 'Root', 'Scan',
    'Set', 'Shell', 'Stack', 'Sync', 'Task', 'Term', 'Tree', 'Word',
)
"""A list of nouns used to generate random application titles."""
