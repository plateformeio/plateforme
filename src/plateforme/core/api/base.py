# plateforme.core.api.base
# ------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides the foundational components for creating the API of the
Plateforme framework using FastAPI and Starlette features. It includes classes
and utilities for API management and interaction.
"""

from collections.abc import Sequence
from enum import Enum
from typing import Any, Callable, Coroutine, TypeVar, Unpack

from fastapi.applications import FastAPI as _APIManager
from fastapi.openapi.docs import (
    get_redoc_html,
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from typing_extensions import override

from ...framework import URL
from ..typing import Default
from .middleware import Middleware
from .parameters import DependsInfo
from .requests import Request
from .responses import HTMLResponse, JSONResponse, Response
from .routing import APIBaseRouterConfigDict, APIEndpoint, APIRouter, BaseRoute
from .types import Lifespan
from .utils import APIBaseRouteIdentifier, generate_unique_id

all = (
    'APIManager',
    'APIManagerType',
)


APIManagerType = TypeVar("APIManagerType", bound='APIManager')
"""A type variable for the API manager."""


class APIManager(_APIManager):
    """A manager for the API.

    Manages API settings, routes, and lifecycle events for Plateforme. It
    inherits from Starlette and FastAPI to utilize their core features while
    adding custom management capabilities specific to Plateforme's API
    requirements.
    """

    def __init__(
        self: APIManagerType,
        *,
        debug: bool = False,
        routes: list[BaseRoute] | None = None,
        title: str | None = None,
        summary: str | None = None,
        description: str | None = None,
        version: str | None = None,
        openapi_url: str | None = '/openapi.json',
        openapi_tags: list[dict[str, Any]] | None = None,
        servers: list[dict[str, Any]] | None = None,
        dependencies: Sequence[DependsInfo] | None = None,
        default_response_class: type[Response] = Default(JSONResponse),
        redirect_slashes: bool = True,
        docs_url: str | None = '/docs',
        redoc_url: str | None = '/redoc',
        swagger_ui_oauth2_redirect_url: str | None = '/docs/oauth2-redirect',
        swagger_ui_init_oauth: dict[str, Any] | None = None,
        middleware: Sequence[Middleware] | None = None,
        exception_handlers: dict[
            int | type[Exception],
            Callable[[Request, Any], Coroutine[Any, Any, Response]],
        ] | None = None,
        lifespan: Lifespan[APIManagerType] | None = None,
        terms_of_service: str | None = None,
        contact: dict[str, Any] | None = None,
        license_info: dict[str, Any] | None = None,
        openapi_prefix: str = '',
        root_path: str = '',
        root_path_in_servers: bool = True,
        responses: dict[int | str, dict[str, Any]] | None = None,
        callbacks: list[BaseRoute] | None = None,
        webhooks: APIRouter | None = None,
        deprecated: bool | None = None,
        include_in_schema: bool = True,
        swagger_ui_parameters: dict[str, Any] | None = None,
        generate_unique_id_function: APIBaseRouteIdentifier = \
            Default(generate_unique_id),
        separate_input_output_schemas: bool = True,
        **extra: Any,
    ) -> None:
        """Initialize the API manager.

        FIXME: Override routing methods (see router).

        Args:
            debug: Boolean indicating if debug tracebacks should be returned on
                server errors. Defaults to ``False``.
            routes: A collection of routes to be included in the router to
                serve incoming HTTP and WebSocket requests. This is not
                recommended for general use, as it bypasses the traditional
                routing system. Defaults to ``None``.
            title: The title of the API. It will be added to the generated
                OpenAPI (e.g. visible at ``/docs``).
                Defaults to ``'Plateforme'``.
            summary: A short summary of the API. It will be added to the
                generated OpenAPI (e.g. visible at ``/docs``).
                Defaults to ``None``.
            description: A description of the API. Supports Markdown (using
                CommonMark syntax). It will be added to the generated OpenAPI
                (e.g. visible at ``/docs``).
                Defaults to an empty string ``''``.
            version: The version of the API. This is the version of your
                application, not the version of the OpenAPI specification nor
                the version of Plateforme being used. It will be added to the
                generated OpenAPI (e.g. visible at ``/docs``).
                Defaults to ``'0.1.0'``.
            openapi_url: The URL where the OpenAPI schema will be served from.
                If you set it to ``None``, no OpenAPI schema will be served
                publicly, and the default automatic endpoints ``/docs`` and
                ``/redoc`` will also be disabled.
                Defaults to ``'/openapi.json'``.
            openapi_tags: A list of tags used by OpenAPI, these are the same
                ``tags`` you can set in the path operations. The order of the
                tags can be used to specify the order shown in tools like
                Swagger UI, used in the automatic path ``/docs``. It's not
                required to specify all the tags used. The tags that are not
                declared MAY be organized randomly or based on the tool's
                logic. Each tag name in the list MUST be unique. The value of
                each item is a dict containing:
                - ``name``: The name of the tag.
                - ``description``: A short description of the tag. CommonMark
                    syntax MAY be used for rich text representation.
                - ``externalDocs``: Additional external documentation for this
                    tag. If provided, it would contain a dict with:
                    - ``description``: A short description of the target
                        documentation. CommonMark syntax MAY be used for rich
                        text representation.
                    - ``url``: The URL for the target documentation. Value MUST
                        be in the form of a URL.
                Defaults to ``None``.
            servers: A list of dicts with connectivity information to a target
                server. You would use it, for example, if your application is
                served from different domains and you want to use the same
                Swagger UI in the browser to interact with each of them
                (instead of having multiple browser tabs open). Or if you want
                to leave fixed the possible URLs. If the servers list is not
                provided, or is an empty list, the default value would be a
                dict with a ``url`` value of ``/``. Each item in the list is a
                dict containing:
                - ``url``: A URL to the target host. This URL supports Server
                    Variables and MAY be relative, to indicate that the host
                    location is relative to the location where the OpenAPI
                    document is being served. Variable substitutions will be
                    made when a variable is named inside brackets ``{}``.
                - ``description``: An optional string describing the host
                    designated by the URL. CommonMark syntax MAY be used for
                    rich text representation.
                - ``variables``: A dict between a variable name and its value.
                    The value is used for substitution in the server's URL
                    template.
                Defaults to ``None``.
            dependencies: A list of global dependencies, they will be applied
                to each path operation, including in sub-routers.
                Defaults to ``None``.
            default_response_class: The default response class to be used.
                Defaults to ``JSONResponse``.
            redirect_slashes: Whether to detect and redirect slashes in URLs
                when the client doesn't use the same format.
                Defaults to ``True``.
            docs_url: The path to the automatic interactive API documentation.
                It is handled in the browser by Swagger UI. The default URL is
                ``/docs``. You can disable it by setting it to ``None``. If
                ``openapi_url`` is set to ``None``, this will be automatically
                disabled. Defaults to ``'/docs'``.
            redoc_url: The path to the alternative automatic interactive API
                documentation provided by ReDoc. The default URL is ``/redoc``.
                You can disable it by setting it to ``None``. If
                ``openapi_url`` is set to ``None``, this will be automatically
                disabled. Defaults to ``'/redoc'``.
            swagger_ui_oauth2_redirect_url: The OAuth2 redirect endpoint for
                the Swagger UI. By default it is ``/docs/oauth2-redirect``.
                This is only used if you use OAuth2 (with the "Authorize"
                button) with Swagger UI.
                Defaults to ``'/docs/oauth2-redirect'``.
            swagger_ui_init_oauth: OAuth2 configuration for the Swagger UI, by
                default shown at ``/docs``. Defaults to ``None``.
            middleware: List of middleware to be added when creating the
                application. You can do this with ``api.add_middleware()``
                instead. Defaults to ``None``.
            exception_handlers: A dictionary with handlers for exceptions. You
                can use the decorator ``@api.exception_handler()`` instead.
                Defaults to ``None``.
            lifespan: The `Lifespan` context manager handler for events to be
                executed when the router starts up and shuts down. It defines
                a collection of ``on_startup`` and ``on_shutdown`` events.
                Defaults to ``None``.
            terms_of_service: A URL to the Terms of Service for your API. It
                will be added to the generated OpenAPI (e.g. visible at
                ``/docs``). Defaults to ``None``.
            contact: A dictionary with the contact information for the exposed
                API. It can contain several fields:
                - ``name``: (str) The name of the contact person/organization.
                - ``url``: (str) A URL pointing to the contact information.
                    It MUST be in the format of a URL.
                - ``email``: (str) The email address of the contact
                    person/organization. It MUST be in the format of an email
                    address. It will be added to the generated OpenAPI (e.g.
                    visible at ``/docs``). Defaults to ``None``.
            license_info: A dictionary with the license information for the
                exposed API. It can contain several fields:
                - ``name``: (str) **REQUIRED** (if a ``license_info`` is set).
                    The license name used for the API.
                - ``identifier``: (str) An SPDX license expression for the API.
                    The ``identifier`` field is mutually exclusive of the
                    ``url`` field. Available since OpenAPI 3.1.0.
                - ``url``: (str) A URL to the license used for the API. This
                    MUST be the format of a URL. It will be added to the
                    generated OpenAPI (e.g. visible at ``/docs``).
                    Defaults to ``None``.
            openapi_prefix: A URL prefix for the OpenAPI URL. Defaults to an
                empty string ``''``.
            root_path: A path prefix handled by a proxy that is not seen by the
                application but is seen by external clients, which affects
                things like Swagger UI. Defaults to an empty string ``''``.
            root_path_in_servers: To disable automatically generating the URLs
                in the ``servers`` field in the autogenerated OpenAPI using the
                ``root_path``. Defaults to ``True``.
            responses: Additional responses to be shown in OpenAPI. It will be
                added to the generated OpenAPI (e.g. visible at ``/docs``).
                Defaults to ``None``.
            callbacks: OpenAPI callbacks that should apply to all path
                operations. It will be added to the generated OpenAPI (e.g.
                visible at ``/docs``). Defaults to ``None``.
            webhooks: Add OpenAPI webhooks. This is similar to ``callbacks``
                but it doesn't require a response. Defaults to ``None``.
            deprecated: Boolean indicating if the API is deprecated.
                Defaults to ``None``.
            include_in_schema: Boolean indicating if the API should be included
                in the OpenAPI schema. Defaults to ``True``.
            swagger_ui_parameters: Additional parameters to pass to the Swagger
                UI. Defaults to ``None``.
            generate_unique_id_function: A function that generates a unique ID
                for a given route. Defaults to ``generate_unique_id``.
            separate_input_output_schemas: Boolean indicating if input and
                output schemas should be separate. Defaults to ``True``.
            **extra: Additional parameters to pass to the application.
        """
        # Handle default values
        title = title or 'Plateforme'
        description = description or ''
        version = version or '0.1.0'

        # Initialize the FastAPI application.
        super().__init__(
            debug=debug,
            routes=routes,
            title=title,
            summary=summary,
            description=description,
            version=version,
            openapi_url=openapi_url,
            openapi_tags=openapi_tags,
            servers=servers,
            dependencies=dependencies,
            default_response_class=default_response_class,
            redirect_slashes=redirect_slashes,
            docs_url=docs_url,
            redoc_url=redoc_url,
            swagger_ui_oauth2_redirect_url=swagger_ui_oauth2_redirect_url,
            swagger_ui_init_oauth=swagger_ui_init_oauth,
            middleware=middleware,
            exception_handlers=exception_handlers,
            lifespan=lifespan,
            terms_of_service=terms_of_service,
            contact=contact,
            license_info=license_info,
            openapi_prefix=openapi_prefix,
            root_path=root_path,
            root_path_in_servers=root_path_in_servers,
            responses=responses,
            callbacks=callbacks,
            webhooks=webhooks,
            deprecated=deprecated,
            include_in_schema=include_in_schema,
            swagger_ui_parameters=swagger_ui_parameters,
            generate_unique_id_function=
                generate_unique_id_function,  # type: ignore[arg-type]
            separate_input_output_schemas=separate_input_output_schemas,
            **extra,
        )

        # Initialize the manager router.
        self.router: APIRouter = APIRouter(
            routes=self.routes,
            redirect_slashes=redirect_slashes,
            dependency_overrides_provider=self,
            lifespan=lifespan,
            default_response_class=default_response_class,
            dependencies=dependencies,
            callbacks=callbacks,
            deprecated=deprecated,
            include_in_schema=include_in_schema,
            responses=responses,
            generate_unique_id_function=generate_unique_id_function,
        )

    def include_endpoints(
        self,
        *endpoints: APIEndpoint[Any, Any],
        force_resolution: bool = False,
        **kwargs: Unpack[APIBaseRouterConfigDict],
    ) -> None:
        """Include configured endpoints within the manager router.

        It is used to include within the manager router the configured
        endpoint. The specified endpoints must be callables with a valid route
        configuration set within the ``__config_route__`` attribute.

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
            the manager router. It should not be used directly.
        """
        self.router.include_endpoints(
            *endpoints,
            force_resolution=force_resolution,
            **kwargs,
        )

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
            obj: The object for which to include the configured endpoints.
                It can be a type or an instance object.
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
        self.router.include_object(
            obj,
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

    @override
    def setup(self) -> None:
        """Setup API manager documentation."""
        # Setup Open API documentation schema
        if self.openapi_url:
            urls = (server_data.get('url') for server_data in self.servers)
            server_urls = {url for url in urls if url}

            async def openapi(req: Request) -> JSONResponse:
                root_path = req.scope.get('root_path', '').rstrip('/')
                if root_path not in server_urls:
                    if root_path and self.root_path_in_servers:
                        self.servers.insert(0, {'url': root_path})
                        server_urls.add(root_path)
                return JSONResponse(self.openapi())

            self.add_route(self.openapi_url, openapi, include_in_schema=False)

        # Setup Open API documentation page
        if self.openapi_url and self.docs_url:
            async def swagger_ui_html(req: Request) -> HTMLResponse:
                root_path = req.scope.get('root_path', '').rstrip('/')
                openapi_url = root_path + self.openapi_url
                oauth2_redirect_url = self.swagger_ui_oauth2_redirect_url
                if oauth2_redirect_url:
                    oauth2_redirect_url = root_path + oauth2_redirect_url
                return get_swagger_ui_html(
                    openapi_url=openapi_url,
                    title=f'{self.title} - Swagger UI',
                    swagger_favicon_url=URL.FAVICON,
                    oauth2_redirect_url=oauth2_redirect_url,
                    init_oauth=self.swagger_ui_init_oauth,
                    swagger_ui_parameters=self.swagger_ui_parameters,
                )

            self.add_route(
                self.docs_url, swagger_ui_html, include_in_schema=False
            )

            if self.swagger_ui_oauth2_redirect_url:
                async def swagger_ui_redirect(req: Request) -> HTMLResponse:
                    return get_swagger_ui_oauth2_redirect_html()

                self.add_route(
                    self.swagger_ui_oauth2_redirect_url,
                    swagger_ui_redirect,
                    include_in_schema=False,
                )

        # Setup ReDoc documentation page
        if self.openapi_url and self.redoc_url:
            async def redoc_html(req: Request) -> HTMLResponse:
                root_path = req.scope.get('root_path', '').rstrip('/')
                openapi_url = root_path + self.openapi_url
                return get_redoc_html(
                    openapi_url=openapi_url,
                    title=f'{self.title} - ReDoc',
                    redoc_favicon_url=URL.FAVICON,
                )

            self.add_route(self.redoc_url, redoc_html, include_in_schema=False)
