# plateforme.core.api.routing
# ---------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides routing mechanisms for the Plateforme API, extending
FastAPI and Starlette features. It includes the standard route decorators for
the API route configurations, and a router to organize and manage API
endpoints.
"""

import asyncio
import inspect
import re
import typing
from collections.abc import Sequence
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Callable,
    Generic,
    Literal,
    ParamSpec,
    Pattern,
    Protocol,
    TypeVar,
    Union,
    Unpack,
)

from fastapi.routing import (
    APIRoute as _APIRoute,
    APIRouter as _APIRouter,
    APIWebSocketRoute as _APIWebSocketRoute,
)
from starlette.concurrency import run_in_threadpool
from starlette.convertors import Convertor
from starlette.routing import BaseRoute, Route
from typing_extensions import TypedDict

from ..config import ConfigWrapper
from ..errors import PlateformeError
from ..expressions import IncEx
from ..logging import logger
from ..patterns import RegexPattern, to_name_case, to_path_case
from ..typing import (
    Default,
    DefaultPlaceholder,
    Undefined,
    get_object_name,
    get_value_or_default,
)
from .middleware import resolve_bulk_middleware
from .parameters import DependsInfo
from .responses import JSONResponse, Response
from .types import ASGIApp, Lifespan
from .utils import APIBaseRouteIdentifier, generate_unique_id

_C = TypeVar('_C', bound=Callable[..., Any])
_P = ParamSpec('_P')
_R = TypeVar('_R', covariant=True)

__all__ = (
    # Routing
    'APIBaseRoute',
    'APIEndpoint',
    'APIMethod',
    'APIMode',
    'APIRoute',
    'APIRouteConfig',
    'APIRouteDecorator',
    'APIRouter',
    'APIWebSocketRoute',
    'BaseRoute',
    'Route',
    # Configurations
    'APIRouteConfigDict',
    'APIBaseRouterConfigDict',
    'APIRequestRouteConfigDict',
    'APIWebSocketRouteConfigDict',
    'APIRouterConfigDict',
    'APIBaseRouterConfigDict',
    'APIExtraRouterConfigDict',
    # Decorators
    'route',
)


APIMethod = Literal[
    'DELETE',
    'GET',
    'HEAD',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
    'TRACE'
]
"""A literal type for the API HTTP methods."""


APIMode = Literal['request', 'websocket']
"""A literal type for the API modes."""


# MARK: API Endpoint

@typing.runtime_checkable
class APIEndpoint(Protocol, Generic[_P, _R]):
    """An API endpoint protocol."""

    __config_route__: 'APIRouteConfig'
    """The configuration for the API route."""

    __name__: str
    """The name of the API endpoint."""

    def __call__(self, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        """Call the API endpoint."""
        ...


# MARK: API Base Route

@typing.runtime_checkable
class APIBaseRoute(Protocol):
    """An API base route protocol."""

    path: str
    """The path for the operation. If not provided, it is automatically
    generated from the endpoint name."""

    path_regex: Pattern[str]
    """The path regex for the operation with format ``/(?P<username>[^/]+)``"""

    path_format: str
    """The path format for the operation with format ``/{username}``"""

    param_convertors: dict[str, Convertor[Any]]
    """The path parameter convertors for the operation with format
    ``{"username": StringConvertor()}``"""

    endpoint: Callable[..., Any]
    """The method endpoint for the path operation."""

    dependencies: list[DependsInfo]
    """A list of dependencies to be applied to the path operation (using
    `Depends` function). Defaults to ``None``."""

    name: str
    """The name of the path operation. It is used internally to identify the
    path operation."""

    operation_id: str | None
    """The operation ID to be used for the path operation. By default, it is
    generated automatically. If you provide a custom operation ID, you need to
    make sure it is unique for the whole API. You can customize the operation
    ID generation with the parameter `generate_unique_id_function`.
    Defaults to ``None``."""

    generate_unique_id_function: Union[
        APIBaseRouteIdentifier, DefaultPlaceholder[APIBaseRouteIdentifier]
    ]
    """A function that generates a unique ID for a given route.
    Defaults to ``generate_unique_id``."""

    unique_id: str
    """The unique ID for the path operation inferred from the operation ID
    or the given `generate_unique_id_function` function."""


# MARK: API Route Configuration

class APIBaseRouteConfigDict(TypedDict, total=False):
    """A base API route configuration dictionary."""

    path: str | None
    """The path for the operation. If not provided, it is automatically
    generated from the endpoint name. Defaults to ``None``."""

    mode: APIMode
    """The mode used for the path operation. Can be either ``request`` or
    ``websocket``. Defaults to ``request``."""

    methods: list[APIMethod] | set[APIMethod] | None
    """A list of HTTP methods to be used for the path operation (e.g.
    ``GET``, ``POST``, ``PUT``, ``DELETE``, etc.). Defaults to ``None``."""

    operation_id: str | None
    """The operation ID to be used for the path operation. By default, it is
    generated automatically. If you provide a custom operation ID, you need to
    make sure it is unique for the whole API. You can customize the operation
    ID generation with the parameter `generate_unique_id_function`.
    Defaults to ``None``."""

    generate_unique_id_function: Union[
        APIBaseRouteIdentifier, DefaultPlaceholder[APIBaseRouteIdentifier]
    ]
    """A function that generates a unique ID for a given route.
    Defaults to ``generate_unique_id``."""


class APIRequestRouteConfigDict(TypedDict, total=False):
    """A request API route configuration dictionary."""

    dependencies: Sequence[DependsInfo] | None
    """A list of dependencies to be applied to the path operation (using
    `Depends` function). Defaults to ``None``."""

    tags: list[str | Enum] | None
    """A list of tags to be applied to the path operation.
    Defaults to ``None``."""

    summary: str | None
    """A summary for the path operation. Defaults to ``None``."""

    description: str | None
    """A description for the path operation. Defaults to ``None``."""

    status_code: int | None
    """The default status code to be used for the response.
    Defaults to ``None``."""

    response_description: str
    """The description for the default response.
    Defaults to ``"Successful Response"``."""

    responses: dict[int | str, dict[str, Any]] | None
    """Additional responses that could be returned by the path operation.
    Defaults to ``None``."""

    deprecated: bool | None
    """Mark this path operation as deprecated. Defaults to ``None``."""

    response_class: Union[
        type[Response], DefaultPlaceholder[type[Response]]
    ]
    """Response class to be used for this path operation.
    Defaults to `JSONResponse`."""

    response_model: Any
    """The type to use for the response. Defaults to ``None``."""

    response_model_include: IncEx | None
    """Configuration passed to the model to include only certain fields in the
    response data. Defaults to ``None``."""

    response_model_exclude: IncEx | None
    """Configuration passed to the model to exclude certain fields in the
    response data. Defaults to ``None``."""

    response_model_by_alias: bool
    """Configuration passed to the model to define if the response model should
    be serialized by alias when an alias is used. Defaults to ``True``."""

    response_model_exclude_unset: bool
    """Configuration passed to the model to define if the response data should
    have all the fields, including the ones that were not set and have their
    default values. Defaults to ``False``."""

    response_model_exclude_defaults: bool
    """Configuration passed to the model to define if the response data should
    have all the fields, including the ones that have the same value as the
    default. Defaults to ``False``."""

    response_model_exclude_none: bool
    """Configuration passed to the model to define if the response data should
    exclude fields set to ``None``. Defaults to ``False``."""

    response_model_serialization: bool
    """Whether to serialize the response model. When disabled, the response
    model configuration is only used for specification purposes and is ignored
    when generating the response. This is useful when the response model is
    needed for OpenAPI documentation but the response data should not be
    serialized. Defaults to ``True``."""

    callbacks: list[BaseRoute] | None
    """List of path operations that will be used as OpenAPI callbacks.
    Defaults to ``None``."""

    include_in_schema: bool
    """Include this path operation in the generated OpenAPI schema.
    Defaults to ``True``."""

    name: str | None
    """The name of the path operation. It is used internally to identify the
    path operation. Defaults to ``None``."""

    openapi_extra: dict[str, Any] | None
    """Extra metadata to be included in the OpenAPI schema for this path
    operation. Defaults to ``None``."""


class APIWebSocketRouteConfigDict(TypedDict, total=False):
    """A websocket API route configuration dictionary."""

    dependencies: Sequence[DependsInfo] | None
    """A list of dependencies to be applied to the path operation (using
    `Depends` function). Defaults to ``None``."""

    name: str | None
    """The name of the path operation. It is used internally to identify the
    path operation. Defaults to ``None``."""


class APIRouteConfigDict(  # type: ignore[misc]
    APIBaseRouteConfigDict,
    APIRequestRouteConfigDict,
    APIWebSocketRouteConfigDict,
    total=False,
):
    """An API route configuration dictionary.

    This configuration extends the `APIBaseRouteConfigDict`,
    `APIRequestRouteConfigDict`, and `APIWebSocketRouteConfigDict` dictionaries
    to provide a common configuration for both request and websocket API
    routes.
    """
    pass


class APIRouteConfig(ConfigWrapper, sources=(APIRouteConfigDict,)):
    """An API route configuration."""

    path: str | None = None
    mode: APIMode = 'request'
    methods: list[APIMethod] | set[APIMethod] | None = ['GET']
    dependencies: Sequence[DependsInfo] | None = None
    tags: list[str | Enum] | None = None
    summary: str | None = None
    description: str | None = None
    status_code: int | None = None
    response_description: str = 'Successful Response'
    responses: dict[int | str, dict[str, Any]] | None = None
    deprecated: bool | None = None
    response_class: Union[
        type[Response], DefaultPlaceholder[type[Response]]
    ] = Default(JSONResponse)
    response_model: Any = Default(None)
    response_model_include: IncEx | None = None
    response_model_exclude: IncEx | None = None
    response_model_by_alias: bool = True
    response_model_exclude_unset: bool = False
    response_model_exclude_defaults: bool = False
    response_model_exclude_none: bool = False
    response_model_serialization: bool = True
    callbacks: list[BaseRoute] | None = None
    include_in_schema: bool = True
    name: str | None = None
    openapi_extra: dict[str, Any] | None = None
    operation_id: str | None = None
    generate_unique_id_function: Union[
        APIBaseRouteIdentifier, DefaultPlaceholder[APIBaseRouteIdentifier]
    ] = Default(generate_unique_id)

    def __init__(
        self, *args: Any, **kwargs: Unpack[APIRouteConfigDict]
    ) -> None:
        """Initialize the API route configuration."""
        super().__init__(*args, **kwargs)

    @property
    def alias(self) -> str:
        """The alias for the route configuration."""
        return self.name or ''

    @property
    def slug(self) -> str:
        """The slug for the route configuration."""
        if self.path is not None:
            if match := re.match(r'^\/([a-ZA-Z0-9-]+)(?:\/|$)', self.path):
                return match.group(1)
        return to_path_case(self.alias)

    def post_init(self) -> None:
        """Post-initialization steps for the API route configuration."""

        # Check if the route mode is valid
        if self.mode not in ('request', 'websocket'):
            raise ValueError(
                f"Invalid route mode {self.mode!r} provided for the route "
                f"configuration. It must be either `request` or `websocket`."
            )

        # Clean up route configuration
        if self.mode == 'request':
            # Pop invalid keys in the request route configuration
            request_keys = (
                APIBaseRouteConfigDict.__annotations__.keys()
                | APIRequestRouteConfigDict.__annotations__.keys()
            )
            for key in self.entries(scope='set'):
                if key not in request_keys:
                    self.pop(key)
        else:
            # Pop invalid keys in the websocket route configuration
            websocket_keys = (
                APIBaseRouteConfigDict.__annotations__.keys()
                | APIWebSocketRouteConfigDict.__annotations__.keys()
            )
            for key in self.entries(scope='set'):
                if key not in websocket_keys or key == 'methods':
                    self.pop(key)

        # Validate route name
        if self.name and not re.match(RegexPattern.ALIAS, self.name):
            raise PlateformeError(
                f"Invalid route name {self.name!r} provided for the route "
                f"configuration. It must match a specific pattern `ALIAS` "
                f"defined in the framework's regular expressions repository.",
                code='route-invalid-config',
            )

        # Validate route path
        if self.path and not re.match(RegexPattern.PATH, self.path):
            raise PlateformeError(
                f"Invalid route path {self.path!r} provided for the route "
                f"configuration. It must match a specific pattern `PATH` "
                f"defined in the framework's regular expressions repository.",
                code='route-invalid-config',
            )


# MARK: API Route Decorator

class APIRouteDecorator:
    """A base class for endpoint API route decorators."""

    def __init__(
        self, /, **kwargs: Unpack[APIRouteConfigDict]
    ) -> None:
        """Initialize an endpoint API route decorator with default values.

        Args:
            **kwargs: The default values to be used for the route
                configuration. If undefined, the API router defaults will be
                used instead.

        Note:
            See also the `APIRouteConfigDict` dictionary for the available
            configuration options used for the route creation within the API.
        """
        self.defaults = APIRouteConfig(**kwargs)

    def __call__(
        self, /, **kwargs: Unpack[APIRouteConfigDict]
    ) -> Callable[[_C], _C]:
        """Decorate a callable endpoint with a path operation.

        It applies a ``path operation`` with the specified route configuration
        to an underlying callable endpoint, typically a method within a class
        that implements either `BaseResource`, or `BaseService`. The
        configuration is stored as an attribute of the callable and is used to
        create a route within the API.

        Args:
            **kwargs: The configuration options for the route operation.

        Returns:
            A route decorator.

        Note:
            This method is used internally to apply a route decorator. It is
            not meant to be called directly. Instead, use the appropriate
            method for the type of route you want to create.
            See also the `APIRouteConfigDict` dictionary for the available
            configuration options used for the route creation within the API.
        """
        config = self.defaults.copy()
        config.update(kwargs)
        config.post_init()

        # Set the route configuration
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            name = get_object_name(func, handler=to_name_case)
            if name.startswith('_'):
                raise TypeError(
                    f"An endpoint must be public and cannot start with an "
                    f"underscore. Got: {name!r}"
                )
            config.setdefault('path', '/' + to_path_case(name))
            config.setdefault('name', to_name_case(name))
            setattr(func, '__config_route__', config)
            return func

        return decorator  # type: ignore[return-value]

    def delete(
        self,
        path: str = Undefined,
        **kwargs: Unpack[APIRequestRouteConfigDict],
    ) -> Callable[[_C], _C]:
        """Decorate a callable with a ``HTTP-DELETE`` path operation.

        Args:
            path: The path for operation. It is automatically generated from
                the endpoint name if not provided.
            **kwargs: The configuration options for the route operation.

        Returns:
            A route decorator for a ``HTTP-DELETE`` path operation.

        Note:
            See also the `APIRequestRouteConfigDict` dictionary for the available
            configuration options used for the request route creation within
            the API.
        """
        return self(
            path=path,
            mode='request',
            methods=['DELETE'],
            **kwargs,
        )

    def get(
        self,
        path: str = Undefined,
        **kwargs: Unpack[APIRequestRouteConfigDict],
    ) -> Callable[[_C], _C]:
        """Decorate a callable with a ``HTTP-GET`` path operation.

        Args:
            path: The path for operation. It is automatically generated from
                the endpoint name if not provided.
            **kwargs: The configuration options for the route operation.

        Returns:
            A route decorator for a ``HTTP-GET`` path operation.

        Note:
            See also the `APIRequestRouteConfigDict` dictionary for the available
            configuration options used for the request route creation within
            the API.
        """
        return self(
            path=path,
            mode='request',
            methods=['GET'],
            **kwargs,
        )

    def head(
        self,
        path: str = Undefined,
        **kwargs: Unpack[APIRequestRouteConfigDict],
    ) -> Callable[[_C], _C]:
        """Decorate a callable with a ``HTTP-HEAD`` path operation.

        Args:
            path: The path for operation. It is automatically generated from
                the endpoint name if not provided.
            **kwargs: The configuration options for the route operation.

        Returns:
            A route decorator for a ``HTTP-HEAD`` path operation.

        Note:
            See also the `APIRequestRouteConfigDict` dictionary for the available
            configuration options used for the request route creation within
            the API.
        """
        return self(
            path=path,
            mode='request',
            methods=['HEAD'],
            **kwargs,
        )

    def options(
        self,
        path: str = Undefined,
        **kwargs: Unpack[APIRequestRouteConfigDict],
    ) -> Callable[[_C], _C]:
        """Decorate a callable with a ``HTTP-OPTIONS`` path operation.

        Args:
            path: The path for operation. It is automatically generated from
                the endpoint name if not provided.
            **kwargs: The configuration options for the route operation.

        Returns:
            A route decorator for a ``HTTP-OPTIONS`` path operation.

        Note:
            See also the `APIRequestRouteConfigDict` dictionary for the available
            configuration options used for the request route creation within
            the API.
        """
        return self(
            path=path,
            mode='request',
            methods=['OPTIONS'],
            **kwargs,
        )

    def patch(
        self,
        path: str = Undefined,
        **kwargs: Unpack[APIRequestRouteConfigDict],
    ) -> Callable[[_C], _C]:
        """Decorate a callable with a ``HTTP-PATCH`` path operation.

        Args:
            path: The path for operation. It is automatically generated from
                the endpoint name if not provided.
            **kwargs: The configuration options for the route operation.

        Returns:
            A route decorator for a ``HTTP-PATCH`` path operation.

        Note:
            See also the `APIRequestRouteConfigDict` dictionary for the available
            configuration options used for the request route creation within
            the API.
        """
        return self(
            path=path,
            mode='request',
            methods=['PATCH'],
            **kwargs,
        )

    def post(
        self,
        path: str = Undefined,
        **kwargs: Unpack[APIRequestRouteConfigDict],
    ) -> Callable[[_C], _C]:
        """Decorate a callable with a ``HTTP-POST`` path operation.

        Args:
            path: The path for operation. It is automatically generated from
                the endpoint name if not provided.
            **kwargs: The configuration options for the route operation.

        Returns:
            A route decorator for a ``HTTP-POST`` path operation.

        Note:
            See also the `APIRequestRouteConfigDict` dictionary for the available
            configuration options used for the request route creation within
            the API.
        """
        return self(
            path=path,
            mode='request',
            methods=['POST'],
            **kwargs,
        )

    def put(
        self,
        path: str = Undefined,
        **kwargs: Unpack[APIRequestRouteConfigDict],
    ) -> Callable[[_C], _C]:
        """Decorate a callable with a ``HTTP-PUT`` path operation.

        Args:
            path: The path for operation. It is automatically generated from
                the endpoint name if not provided.
            **kwargs: The configuration options for the route operation.

        Returns:
            A route decorator for a ``HTTP-PUT`` path operation.

        Note:
            See also the `APIRequestRouteConfigDict` dictionary for the available
            configuration options used for the request route creation within
            the API.
        """
        return self(
            path=path,
            mode='request',
            methods=['PUT'],
            **kwargs,
        )

    def trace(
        self,
        path: str = Undefined,
        **kwargs: Unpack[APIRequestRouteConfigDict],
    ) -> Callable[[_C], _C]:
        """Decorate a callable with a ``HTTP-TRACE`` path operation.

        Args:
            path: The path for operation. It is automatically generated from
                the endpoint name if not provided.
            **kwargs: The configuration options for the route operation.

        Returns:
            A route decorator for a ``HTTP-TRACE`` path operation.

        Note:
            See also the `APIRequestRouteConfigDict` dictionary for the available
            configuration options used for the request route creation within
            the API.
        """
        return self(
            path=path,
            mode='request',
            methods=['TRACE'],
            **kwargs,
        )

    def websocket(
        self,
        path: str = Undefined,
        **kwargs: Unpack[APIWebSocketRouteConfigDict],
    ) -> Callable[[_C], _C]:
        """Decorate a callable with a websocket path operation.

        Args:
            path: The path for operation. It is automatically generated from
                the endpoint name if not provided.
            **kwargs: The configuration options for the route operation.

        Returns:
            A route decorator for a websocket path operation.

        Note:
            See also the `APIWebSocketRouteConfigDict` dictionary for the available
            configuration options used for the websocket route creation within
            the API.
        """
        return self(
            path=path,
            mode='websocket',
            **kwargs,
        )


route = APIRouteDecorator()
"""The standard decorator for routing operations."""


# MARK: API Route

class APIRoute(_APIRoute):
    """An API route."""
    if typing.TYPE_CHECKING:
        response_class: Union[
            type[Response], DefaultPlaceholder[type[Response]]
        ]
        generate_unique_id_function: Union[  # type: ignore
            APIBaseRouteIdentifier, DefaultPlaceholder[APIBaseRouteIdentifier]
        ]

    def __init__(
        self,
        path: str,
        endpoint: Callable[..., Any],
        *,
        response_model: Any = Default(None),
        status_code: int | None = None,
        tags: list[str | Enum] | None = None,
        dependencies: Sequence[DependsInfo] | None = None,
        summary: str | None = None,
        description: str | None = None,
        response_description: str = 'Successful Response',
        responses: dict[int | str, dict[str, Any]] | None = None,
        deprecated: bool | None = None,
        name: str | None = None,
        methods: list[APIMethod] | set[APIMethod] | None = None,
        operation_id: str | None = None,
        response_model_include: IncEx | None = None,
        response_model_exclude: IncEx | None = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        response_model_serialization: bool = True,
        include_in_schema: bool = True,
        response_class: Union[
            type[Response], DefaultPlaceholder[type[Response]]
        ] = Default(JSONResponse),
        dependency_overrides_provider: Any | None = None,
        callbacks: list[BaseRoute] | None = None,
        openapi_extra: dict[str, Any] | None = None,
        generate_unique_id_function: Union[
            APIBaseRouteIdentifier, DefaultPlaceholder[APIBaseRouteIdentifier]
        ] = Default(generate_unique_id),
    ) -> None:
        """Initialize an API route."""
        # Wrap endpoint return value in a response model if no serialization
        # is required. This prevents FastAPI from serializing the response
        # model and allows the response model to be used for OpenAPI
        # documentation only.
        if response_model_serialization:
            wrapped_endpoint = endpoint
        else:
            wrapped_endpoint = _wrap_endpoint_with_response(
                endpoint,
                status_code=status_code,
                response_class=response_class,
            )

        # Initialize the API route
        super().__init__(
            path,
            wrapped_endpoint,
            response_model=response_model,
            status_code=status_code,
            tags=tags,
            dependencies=dependencies,
            summary=summary,
            description=description,
            response_description=response_description,
            responses=responses,
            deprecated=deprecated,
            name=name,
            methods={*methods} if methods else None,
            operation_id=operation_id,
            response_model_include=response_model_include,
            response_model_exclude=response_model_exclude,
            response_model_by_alias=response_model_by_alias,
            response_model_exclude_unset=response_model_exclude_unset,
            response_model_exclude_defaults=response_model_exclude_defaults,
            response_model_exclude_none=response_model_exclude_none,
            include_in_schema=include_in_schema,
            response_class=response_class,
            dependency_overrides_provider=dependency_overrides_provider,
            callbacks=callbacks,
            openapi_extra=openapi_extra,
            generate_unique_id_function=
                generate_unique_id_function,  # type: ignore[arg-type]
        )

        # Update route configuration
        self.name = get_object_name(endpoint, handler=to_name_case) \
            if name is None else name
        self.response_model_serialization = response_model_serialization


# MARK: API WebSocket Route

class APIWebSocketRoute(_APIWebSocketRoute):
    """An API websocket route."""
    if typing.TYPE_CHECKING:
        generate_unique_id_function: Union[
            APIBaseRouteIdentifier, DefaultPlaceholder[APIBaseRouteIdentifier]
        ]

    def __init__(
        self,
        path: str,
        endpoint: Callable[..., Any],
        *,
        name: str | None = None,
        dependencies: Sequence[DependsInfo] | None = None,
        dependency_overrides_provider: Any | None = None,
        operation_id: str | None = None,
        generate_unique_id_function: Union[
            APIBaseRouteIdentifier, DefaultPlaceholder[APIBaseRouteIdentifier]
        ] = Default(generate_unique_id),
    ) -> None:
        """Initialize an API websocket route."""
        super().__init__(
            path,
            endpoint,
            name=name,
            dependencies=dependencies,
            dependency_overrides_provider=dependency_overrides_provider,
        )

        # Update route configuration
        self.name = get_object_name(endpoint, handler=to_name_case) \
            if name is None else name
        self.operation_id = operation_id
        self.generate_unique_id_function = generate_unique_id_function
        self.unique_id = self.operation_id or \
            get_value_or_default(generate_unique_id_function)(self)


# MARK: API Router Configuration

class APIBaseRouterConfigDict(TypedDict, total=False):
    """A base API router configuration dictionary."""

    prefix: str
    """An optional path prefix for the router.
    Defaults to an empty string ``''``."""

    tags: list[str | Enum] | None
    """A list of tags to be applied to all the path operations in this router.
    Defaults to ``None``."""

    dependencies: Sequence[DependsInfo] | None
    """A collection of dependencies to be applied to all the path operations in
    this router (using `Depends`). Defaults to ``None``."""

    default_response_class: type[Response]
    """The default response class to be used. Defaults to `JSONResponse`."""

    responses: dict[int | str, dict[str, Any]] | None
    """Additional responses to be shown in OpenAPI. It will be added to the
    generated OpenAPI (e.g. visible at ``/docs``). Defaults to ``None``."""

    callbacks: list[BaseRoute] | None
    """OpenAPI callbacks that should apply to all path operations in this
    router. It will be added to the generated OpenAPI (e.g. visible at
    ``/docs``). Defaults to ``None``."""

    deprecated: bool | None
    """Mark all path operations in this router as deprecated. It will be added
    to the generated OpenAPI (e.g. visible at ``/docs``).
    Defaults to ``None``."""

    include_in_schema: bool
    """Include (or not) all the path operations in this router in the generated
    OpenAPI schema. This affects the generated OpenAPI (e.g. visible at
    ``/docs``). Defaults to ``True``."""

    generate_unique_id_function: APIBaseRouteIdentifier
    """A function that generates a unique ID for a given route.
    Defaults to ``generate_unique_id``."""


class APIExtraRouterConfigDict(TypedDict, total=False):
    """An extra API router configuration dictionary."""

    routes: list[BaseRoute] | None
    """A collection of routes to be included in the router to serve incoming
    HTTP and WebSocket requests. This is not recommended for general use, as it
    bypasses the traditional routing system. Defaults to ``None``."""

    redirect_slashes: bool
    """Whether to redirect requests with a trailing slash to the same path
    without the trailing slash. Defaults to ``True``."""

    default: ASGIApp | None
    """The default function handler to be used for the router. It is used to
    handle ``404 Not Found`` errors. Defaults to ``None``."""

    dependency_overrides_provider: Any
    """An optional dependency overrides provider used internally by the router.
    Defaults to ``None``."""

    route_class: type[APIRoute]
    """The request route class to be used for the router.
    Defaults to `APIRoute`."""

    lifespan: Lifespan[Any] | None
    """The `Lifespan` context manager handler for events to be executed when
    the router starts up and shuts down. It defines a collection of
    ``on_startup`` and ``on_shutdown`` events. Defaults to ``None``."""


class APIRouterConfigDict(
    APIBaseRouterConfigDict,
    APIExtraRouterConfigDict,
    total=False,
):
    """An API router configuration dictionary.

    This configuration extends the `APIBaseRouterConfigDict` and
    `APIExtraRouterConfigDict` dictionaries to provide a configuration for the
    API router initialization method.
    """
    pass


# MARK: API Router

class APIRouter(_APIRouter):
    """An API router to group path operations.

    It is used to group ``path operations``, for example to structure an app in
    multiple files. It would then be included in an `APIManager` class (i.e. a
    subclass of the `FastAPI` application), or in another `APIRouter` class
    (ultimately included in a manager).

    Examples:
        >>> from plateforme.api import APIManager, APIRouter
        ... manager = APIManager()
        ... router = APIRouter()

        >>> @router.get("/users/", tags=["users"])
        ... async def read_users():
        ...     return [{"username": "Rick"}, {"username": "Morty"}]

        >>> manager.include_router(router)

    Note:
        This class is used internally within the framework and should not be
        used directly except for advanced use cases.
    """
    if typing.TYPE_CHECKING:
        default_response_class: Union[  # type: ignore
            type[Response], DefaultPlaceholder[type[Response]]
        ]
        route_class: type[APIRoute]
        generate_unique_id_function: Union[  # type: ignore
            APIBaseRouteIdentifier, DefaultPlaceholder[APIBaseRouteIdentifier]
        ]

    def __init__(self,  **kwargs: Unpack[APIRouterConfigDict]) -> None:
        """Initialize an API router.

        Args:
            **kwargs: The configuration options for the API router.
        """
        super().__init__(
            prefix=kwargs.get('prefix', ''),
            tags=kwargs.get('tags', None),
            dependencies=kwargs.get('dependencies', None),
            default_response_class=
                kwargs.get('default_response_class', Default(JSONResponse)),
            responses=kwargs.get('responses', None),
            callbacks=kwargs.get('callbacks', None),
            routes=kwargs.get('routes', None),
            redirect_slashes=kwargs.get('redirect_slashes', True),
            default=kwargs.get('default', None),
            dependency_overrides_provider=
                kwargs.get('dependency_overrides_provider', None),
            route_class=kwargs.get('route_class', APIRoute),
            lifespan=kwargs.get('lifespan', None),
            deprecated=kwargs.get('deprecated', None),
            include_in_schema=kwargs.get('include_in_schema', True),
            generate_unique_id_function=kwargs.get(  # type: ignore[arg-type]
                'generate_unique_id_function', Default(generate_unique_id)
            ),
        )

    def add_api_route(  # type: ignore[override, unused-ignore]
        self,
        path: str,
        endpoint: Callable[..., Any],
        *,
        response_model: Any = Default(None),
        status_code: int | None = None,
        tags: list[str | Enum] | None = None,
        dependencies: Sequence[DependsInfo] | None = None,
        summary: str | None = None,
        description: str | None = None,
        response_description: str = 'Successful Response',
        responses: dict[int | str, dict[str, Any]] | None = None,
        deprecated: bool | None = None,
        name: str | None = None,
        methods: list[APIMethod] | set[APIMethod] | None = None,
        operation_id: str | None = None,
        response_model_include: IncEx | None = None,
        response_model_exclude: IncEx | None = None,
        response_model_by_alias: bool = True,
        response_model_exclude_unset: bool = False,
        response_model_exclude_defaults: bool = False,
        response_model_exclude_none: bool = False,
        response_model_serialization: bool = True,
        include_in_schema: bool = True,
        response_class: Union[
            type[Response], DefaultPlaceholder[type[Response]]
        ] = Default(JSONResponse),
        route_class_override: type[APIRoute] | None = None,
        callbacks: list[BaseRoute] | None = None,
        openapi_extra: dict[str, Any] | None = None,
        generate_unique_id_function: Union[
            APIBaseRouteIdentifier, DefaultPlaceholder[APIBaseRouteIdentifier]
        ] = Default(generate_unique_id),
        force_resolution: bool = False,
    ) -> None:
        route_class = route_class_override or self.route_class
        responses = responses or {}
        combined_responses = {**self.responses, **responses}
        current_response_class = get_value_or_default(
            response_class, self.default_response_class
        )
        current_tags = self.tags.copy()
        if tags:
            current_tags.extend(tags)
        current_dependencies = self.dependencies.copy()
        if dependencies:
            current_dependencies.extend(dependencies)
        current_callbacks = self.callbacks.copy()
        if callbacks:
            current_callbacks.extend(callbacks)
        current_generate_unique_id = get_value_or_default(
            generate_unique_id_function, self.generate_unique_id_function
        )
        if force_resolution:
            endpoint = resolve_bulk_middleware(endpoint)

        route = route_class(
            self.prefix + path,
            endpoint,
            response_model=response_model,
            status_code=status_code,
            tags=current_tags,
            dependencies=current_dependencies,
            summary=summary,
            description=description,
            response_description=response_description,
            responses=combined_responses,
            deprecated=deprecated or self.deprecated,
            methods=methods,
            operation_id=operation_id,
            response_model_include=response_model_include,
            response_model_exclude=response_model_exclude,
            response_model_by_alias=response_model_by_alias,
            response_model_exclude_unset=response_model_exclude_unset,
            response_model_exclude_defaults=response_model_exclude_defaults,
            response_model_exclude_none=response_model_exclude_none,
            response_model_serialization=response_model_serialization,
            include_in_schema=include_in_schema and self.include_in_schema,
            response_class=current_response_class,
            name=name,
            dependency_overrides_provider=self.dependency_overrides_provider,
            callbacks=current_callbacks,
            openapi_extra=openapi_extra,
            generate_unique_id_function=current_generate_unique_id,
        )

        self.routes.append(route)

    def add_api_websocket_route(  # type: ignore[override, unused-ignore]
        self,
        path: str,
        endpoint: Callable[..., Any],
        *,
        name: str | None = None,
        dependencies: Sequence[DependsInfo] | None = None,
        operation_id: str | None = None,
        generate_unique_id_function: Union[
            APIBaseRouteIdentifier, DefaultPlaceholder[APIBaseRouteIdentifier]
        ] = Default(generate_unique_id),
        force_resolution: bool = False,
    ) -> None:
        """Add a websocket route to the router."""
        current_dependencies = self.dependencies.copy()
        if dependencies:
            current_dependencies.extend(dependencies)
        if force_resolution:
            endpoint = resolve_bulk_middleware(endpoint)

        route = APIWebSocketRoute(
            self.prefix + path,
            endpoint,
            name=name,
            dependencies=current_dependencies,
            dependency_overrides_provider=self.dependency_overrides_provider,
            operation_id=operation_id,
            generate_unique_id_function=generate_unique_id_function,
        )

        self.routes.append(route)

    def include_endpoints(
        self,
        *endpoints: APIEndpoint[Any, Any],
        force_resolution: bool = False,
        **kwargs: Unpack[APIBaseRouterConfigDict],
    ) -> None:
        """Include configured endpoints within the router.

        It is used to include within the router the configured endpoint. The
        specified endpoints must be callables with a valid route configuration
        set within the ``__config_route__`` attribute.

        Args:
            *endpoints: The endpoints to include within the router. It must be
                an iterable of callables with a valid route configuration (i.e.
                it must have a ``__config_route__`` attribute).
            force_resolution: Whether to force the resolution of the endpoint
                resource type annotated arguments and keyword arguments against
                the database. Defaults to ``False``.
            **kwargs: The configuration options for the API router.

        Raises:
            PlateformeError: If the route configuration is missing, invalid, or
                the ``mode`` key is missing.

        Note:
            This method is used internally to include configured endpoints in
            the router.
        """
        for endpoint in endpoints:
            # Check if the endpoint is valid
            if not isinstance(endpoint, APIEndpoint):
                raise PlateformeError(
                    f"Route configuration is missing for the provided "
                    f"endpoint. (i.e. the endpoint callable does not have a "
                    f"`__config_route__` attribute). Please use a routing "
                    f"decorator to define a route configuration for the "
                    f"endpoint or use directly an appropriate routing method "
                    f"(e.g. `add_api_route` or `add_api_websocket_route`). "
                    f"Got: {endpoint!r}",
                    code='route-invalid-config',
                )

            # Retrieve the endpoint route configuration
            config: APIRouteConfig = getattr(endpoint, '__config_route__')
            config_dict = config.entries(default_mode='preserve')

            # Retrieve the endpoint route mode
            config_mode = config_dict.pop('mode', None)
            if config_mode not in ('request', 'websocket'):
                raise PlateformeError(
                    f"Invalid route configuration. The route `mode` is "
                    f"missing or invalid. Got: {config_mode!r}",
                    code='route-invalid-config',
                )

            # Combine common configuration options
            path = kwargs.pop('prefix', '') + config_dict.pop('path', '')
            dependencies = [
                *(kwargs.pop('dependencies', None) or []),
                *(config_dict.pop('dependencies', None) or []),
            ]
            generate_unique_id = get_value_or_default(
                config_dict.pop('generate_unique_id_function'),
                kwargs.pop('generate_unique_id_function', None)
                    or self.generate_unique_id_function,
            )

            # Add the endpoint route to the new router
            if config_mode == 'request':
                tags = [
                    *(kwargs.pop('tags', None) or []),
                    *(config_dict.pop('tags', None) or []),
                ]
                response_class = get_value_or_default(
                    config_dict.pop('response_class'),
                    kwargs.pop('default_response_class', None)
                        or self.default_response_class,
                )
                response = {
                    **(kwargs.pop('responses', None) or {}),
                    **(config_dict.pop('responses', None) or {}),
                }
                callbacks = [
                    *(kwargs.pop('callbacks', None) or []),
                    *(config_dict.pop('callbacks', None) or []),
                ]
                deprecated = (
                    config_dict.pop('deprecated', None)
                    or kwargs.pop('deprecated', None)
                    or self.deprecated
                )
                include_in_schema = (
                    config_dict.pop('include_in_schema', True)
                    and kwargs.pop('include_in_schema', True)
                    and self.include_in_schema
                )
                self.add_api_route(
                    path,
                    endpoint,
                    tags=tags,
                    dependencies=dependencies,
                    response_class=response_class,
                    responses=response,
                    callbacks=callbacks,
                    deprecated=deprecated,
                    include_in_schema=include_in_schema,
                    generate_unique_id_function=generate_unique_id,
                    force_resolution=force_resolution,
                    **config_dict,
                )
            else:
                self.add_api_websocket_route(
                    path,
                    endpoint,
                    dependencies=dependencies,
                    generate_unique_id_function=generate_unique_id,
                    force_resolution=force_resolution,
                    **config_dict,
                )

            route_id = getattr(self.routes[-1], 'unique_id')

            logger.debug(f"api:{route_id} -> added ")

    def include_object(
        self,
        obj: object,
        force_resolution: bool = False,
        **kwargs: Unpack[APIBaseRouterConfigDict],
    ) -> None:
        """Include a type or an instance object within the router.

        It is used to include within the router the configured endpoint members
        of a type or an instance object. Each callable member of the object
        implementing a configured route will be included within the router as
        an API route.

        Args:
            obj: The object for which to include the configured endpoints. It
                can be a type or an instance object.
            force_resolution: Whether to force the resolution of the endpoint
                resource type annotated arguments and keyword arguments against
                the database. Defaults to ``False``.
            **kwargs: The configuration options for the API router.

        Raises:
            PlateformeError: If the route configuration is missing, invalid, or
                the ``mode`` key is missing.

        Note:
            This method is used internally to include configured endpoints in
            the router. It should not be used directly.
        """
        # Collect all configured endpoints from the object
        endpoints = [
            member for _, member in inspect.getmembers(obj)
            if isinstance(member, APIEndpoint)
        ]

        # Include endpoints within the router
        self.include_endpoints(
            *endpoints,
            force_resolution=force_resolution,
            **kwargs,
        )

    def include_router(  # type: ignore[override, unused-ignore]
        self,
        router: 'APIRouter',
        *,
        prefix: str = '',
        tags: list[str | Enum] | None = None,
        dependencies: Sequence[DependsInfo] | None = None,
        default_response_class: type[Response] = Default(JSONResponse),
        responses: dict[int | str, dict[str, Any]] | None = None,
        callbacks: list[BaseRoute] | None = None,
        deprecated: bool | None = None,
        include_in_schema: bool = True,
        generate_unique_id_function: APIBaseRouteIdentifier = \
            Default(generate_unique_id),
    ) -> None:
        """Include another router within the current router.

        It is used to include within the router an existing `APIRouter`. Each
        route operation within the included router will be added to the current
        router.

        FIXME: MyPy crashes when using kwargs unpacking with inheritance.
        FIXME: FastAPI does not implement `generate_unique_id_function`
            function within websockets.

        Args:
            router: The `APIRouter` to include.
            prefix: An optional path prefix for the router. Defaults to an
                empty string ``''``.
            tags: A list of tags to be applied to all the path operations in
                this router. It will be added to the generated OpenAPI (e.g.
                visible at ``/docs``). Defaults to ``None``.
            dependencies: A collection of dependencies to be applied to all the
                path operations in this router (using `Depends`).
                Defaults to ``None``.
            default_response_class: The default response class to be used.
                Defaults to `JSONResponse`.
            responses: Additional responses to be shown in OpenAPI. It will be
                added to the generated OpenAPI (e.g. visible at ``/docs``).
                Defaults to ``None``.
            callbacks: OpenAPI callbacks that should apply to all path
                operations in this router. It will be added to the generated
                OpenAPI (e.g. visible at ``/docs``). Defaults to ``None``.
            deprecated: Mark all path operations in this router as deprecated.
                It will be added to the generated OpenAPI (e.g. visible at
                ``/docs``). Defaults to ``None``.
            include_in_schema: Include (or not) all the path operations in this
                router in the generated OpenAPI schema. This affects the
                generated OpenAPI (e.g. visible at ``/docs``).
                Defaults to ``True``.
            generate_unique_id_function: A function that generates a unique ID
                for a given route. Defaults to ``generate_unique_id``.
        """
        # Include endpoints within the router
        super().include_router(
            router,
            prefix=prefix,
            tags=tags,
            dependencies=dependencies,
            default_response_class=default_response_class,
            responses=responses,
            callbacks=callbacks,
            deprecated=deprecated,
            include_in_schema=include_in_schema,
            generate_unique_id_function=
                generate_unique_id_function,  # type: ignore[arg-type]
        )


# MARK: Utilities

def _wrap_endpoint_with_response(
    endpoint: Callable[..., Any],
    *,
    status_code: int | None = None,
    response_class: Union[
        type[Response], DefaultPlaceholder[type[Response]]
    ] = Default(JSONResponse),
) -> Callable[..., Any]:
    """Wrap an API route endpoint to return directly a response model.

    Args:
        endpoint: The endpoint callable to wrap.
        status_code: An optional status code for the response. Defaults to
            ``None``.
        response_class: The response class to use for the response model.
            Defaults to `JSONResponse`.

    Returns:
        A wrapped endpoint callable that returns a response model.
    """
    signature = inspect.signature(endpoint)
    return_annotation = signature.return_annotation

    if isinstance(return_annotation, type) \
            and issubclass(return_annotation, Response):
        return endpoint

    actual_response_class = get_value_or_default(response_class)

    @wraps(endpoint)
    async def wrapper(**kwargs: Any) -> Callable[..., Any] | None:
        if asyncio.iscoroutinefunction(endpoint):
            result = await endpoint(**kwargs)
        else:
            result = await run_in_threadpool(endpoint, **kwargs)

        if isinstance(result, Response):
            return result

        response_args: dict[str, Any] = {}
        if status_code is not None:
            response_args["status_code"] = int(status_code)
        return actual_response_class(content=result, **response_args)

    setattr(
        wrapper,
        '__signature__',
        signature.replace(return_annotation=actual_response_class),
    )

    return wrapper
