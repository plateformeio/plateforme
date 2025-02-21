# plateforme.core.main
# --------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module contains the Plateforme application.
"""

import inspect
import os
import typing
from collections.abc import Iterable
from contextvars import Token
from typing import Any, Callable, Generic, Literal, Self, TypeVar, Unpack
from weakref import WeakValueDictionary

from . import runtime
from .api.base import APIManager
from .api.exceptions import EXCEPTION_HANDLERS
from .api.middleware import BulkMiddleware, Middleware
from .api.routing import APIBaseRouterConfigDict
from .api.types import Receive, Scope, Send
from .api.utils import sort_key_for_routes
from .context import PLATEFORME_CONTEXT
from .database.base import DatabaseManager
from .database.orm import Registry
from .database.routing import DatabaseRouter
from .database.schema import MetaData
from .database.sessions import (
    AsyncSessionFactory,
    SessionFactory,
    async_session_factory,
    session_factory,
)
from .errors import PlateformeError
from .events import EventEmitter, emit
from .logging import logger, setup_logging
from .modules import (
    get_root_module_name,
    import_module,
    resolve_relative_import_name,
)
from .namespaces import NamespaceImpl
from .packages import Package, PackageImpl
from .patterns import to_kebab_case, to_snake_case
from .proxy import CollectionProxy, ProxyConfig
from .resources import ResourceFieldInfo, ResourceType
from .runtime import (
    AppMap,
    Lifecycle,
    NamespaceMap,
    PackageMap,
    ResolvedState,
    ResourceLinkMap,
    ResourceMap,
)
from .settings import (
    NamespaceSettings,
    PackageSettings,
    Settings,
    SettingsDict,
    merge_settings,
)
from .typing import get_parent_frame_namespace

_T = TypeVar('_T', bound=Any)

__all__ = (
    'CALLER_REF',
    'AppProxy',
    'MetaDataProxy',
    'RegistryProxy',
    'Plateforme',
    'PlateformeMeta',
)


CALLER_REF = '$'
"""A special reference to the caller package name."""


# MARK: Plateforme Proxies

class AppProxy(CollectionProxy[_T], Generic[_T]):
    """An application proxy.

    It delegates attribute access to a target object or callable. This class is
    used internally to proxy the Plateforme application metadata and registry.

    Attributes:
        app: The application instance.
    """
    if typing.TYPE_CHECKING:
        app: 'Plateforme'

    __config__ = ProxyConfig(read_only=True)

    def __init__(
        self,
        app: 'Plateforme',
        target: Iterable[_T] | Callable[..., Iterable[_T]],
    ) -> None:
        """Initialize an application proxy instance.

        Args:
            app: The application instance.
            target: The target object or callable to proxy to. If the target is
                a callable, it will be called to retrieve the actual target
                object. The target object can be any iterable type.
        """
        object.__setattr__(self, 'app', app)
        super().__init__(target)

    def __repr__(self) -> str:
        name = self.__class__.__name__
        return f'{name}({self.app})'

    def __str__(self) -> str:
        name = self.__class__.__name__
        return f'{name}({self.app})'


class MetaDataProxy(AppProxy[MetaData]):
    """The application metadata proxy class."""

    def create_all(
        self,
        bind: str = 'default',
        /,
        checkfirst: bool = True,
    ) -> None:
        """Create all tables stored in the application metadata.

        Conditional by default, will not attempt to recreate tables already
        present in the target databases.

        Args:
            bind: An engine alias used to access the database. Defaults to
                ``default``.
            checkfirst: Don't issue ``CREATE` statements for tables already
                present in the target database. Defaults to ``True`.
        """
        # Check if the engine is registered
        if bind not in self.app.database:
            raise PlateformeError(
                f"Cannot create all tables. The engine {bind!r} is not "
                f"registered.",
                code='plateforme-invalid-engine',
            )
        engine = self.app.database.engines[bind]
        # Call proxy methods for create all
        create_all = super().__proxy_getattr__('create_all')
        if callable(create_all):
            create_all(engine, checkfirst=checkfirst)

    def drop_all(
        self,
        bind: str = 'default',
        /,
        checkfirst: bool = True,
    ) -> None:
        """Drop all tables stored in the application metadata.

        Conditional by default, will not attempt to drop tables not present in
        the target database.

        Args:
            bind: An engine alias used to access the database. Defaults to
                ``default``.
            checkfirst: Only issue ``DROP`` statements for tables confirmed to
                be present in the target database.
        """
        # Check if the engine is registered
        if bind not in self.app.database:
            raise PlateformeError(
                f"Cannot drop all tables. The engine {bind!r} is not "
                f"registered.",
                code='plateforme-invalid-engine',
            )
        engine = self.app.database.engines[bind]
        # Call proxy methods for drop all
        drop_all = super().__proxy_getattr__('drop_all')
        if callable(drop_all):
            drop_all(engine, checkfirst=checkfirst)


class RegistryProxy(AppProxy[Registry]):
    """The application registry proxy class."""
    pass


# MARK: Plateforme Metaclass

class PlateformeMeta(type):
    """The Plateforme metaclass."""

    @property
    def apps(cls) -> 'AppMap':
        """Retrieve all initialized apps from the runtime environment."""
        return runtime.apps

    @property
    def namespaces(cls) -> 'NamespaceMap':
        """Retrieve all initialized namespaces from the runtime environment."""
        return runtime.namespaces

    @property
    def packages(cls) -> 'PackageMap':
        """Retrieve all initialized packages from the runtime environment."""
        return runtime.packages

    @property
    def dependencies(cls) -> 'ResourceLinkMap':
        """Retrieve all initialized resource dependencies from the runtime
        environment."""
        return runtime.dependencies

    @property
    def dependents(cls) -> 'ResourceLinkMap':
        """Retrieve all initialized resource dependents from the runtime
        environment."""
        return runtime.dependents

    @property
    def resources(cls) -> 'ResourceMap':
        """Retrieve all initialized resources from the runtime environment."""
        return runtime.resources


# MARK: Plateforme

@typing.final
class Plateforme(EventEmitter, metaclass=PlateformeMeta):
    """The Plateforme application class."""
    if typing.TYPE_CHECKING:
        __plateforme_mounted__: bool
        api: APIManager
        async_session: AsyncSessionFactory
        caller: str
        caller_package: Package
        database: DatabaseManager
        metadata: MetaDataProxy
        namespaces: WeakValueDictionary[str, NamespaceImpl]
        packages: WeakValueDictionary[str, PackageImpl]
        registry: RegistryProxy
        session: SessionFactory
        settings: Settings
        token: Token['Plateforme'] | None

    __slots__ = (
        '__plateforme_mounted__'
        'api',
        'async_session',
        'caller',
        'caller_package',
        'database',
        'metadata',
        'namespaces',
        'packages',
        'registry',
        'session',
        'settings',
        'token',
    )

    @emit()
    def __init__(
        self,
        __settings: Settings | str | None = None,
        **kwargs: Unpack[SettingsDict],
    ) -> None:
        """Initialize the Plateforme application.

        The application settings can be provided either as a `Settings`
        instance, a dictionary, or string path to the settings module.  If the
        settings argument is a `Settings` instance, it will be used as is,
        othersise the provided arguments are used to initialize the settings.

        It is not possible to initialize the Plateforme application with both
        settings and keyword arguments. Please provide either settings or
        keyword arguments, not both.

        Args:
            __settings: The settings to use for the Plateforme application. It
                can be provided either as a `Settings` instance, or a string
                path to the settings module. If the settings argument is a
                `Settings` instance, it will be used as is. If the settings
                argument is a string path to the settings module, it will be
                imported and used to initialize the settings. Finally, if the
                settings argument and keyword arguments are not provided, the
                ``PLATEFORME_SETTINGS`` path environment variable will be used
                to import the settings module or result in default settings if
                the environment variable is not set. Defaults to ``None``.
            **kwargs: The keyword arguments to use for the Plateforme
                application settings. It must adhere to the `SettingsDict`
                dictionary schema.
        """
        super().__init__()
        object.__setattr__(self, '__plateforme_mounted__', False)

        # Get the stack frame of the caller of the constructor and extract its
        # module name and package from the frame information.
        caller_namespace = get_parent_frame_namespace(depth=3, mode='globals')
        caller_namespace = caller_namespace or {}
        caller = caller_namespace.get('__name__', get_root_module_name())
        caller_package = runtime.import_package(caller, force_resolution=True)
        object.__setattr__(self, 'caller', caller)
        object.__setattr__(self, 'caller_package', caller_package)

        # Initialize settings
        if __settings and kwargs:
            raise PlateformeError(
                "Cannot initialize Plateforme application with both settings "
                "and keyword arguments. Please provide either settings or "
                "keyword arguments, not both.",
                code='plateforme-invalid-config',
            )

        settings: Any = __settings or kwargs

        # Validate settings
        if not isinstance(settings, Settings):
            settings_dict: dict[str, Any] = {}

            if isinstance(settings, dict):
                settings_dict = settings
            elif isinstance(settings, str) or settings is None:
                # Retrieve settings path
                if settings is None:
                    settings_path = os.getenv('PLATEFORME_SETTINGS')
                else:
                    settings_path = settings
                # Import settings module if the settings path is specified and
                # build the settings instance from the imported module
                # attributes.
                if settings_path:
                    try:
                        settings_module = import_module(settings_path)
                    except ImportError as error:
                        raise ImportError(
                            f"An error occurred while importing the "
                            f"application settings module {settings_path!r}."
                        ) from error
                    except Exception as error:
                        raise PlateformeError(
                            f"En error occurred while evaluating the "
                            f"application settings module {settings_path!r}."
                        ) from error
                    # Extract settings
                    for key in dir(settings_module):
                        if not key.isupper():
                            continue
                        settings_dict[key.lower()] = \
                            getattr(settings_module, key)

            settings = Settings.model_validate(settings_dict)

        object.__setattr__(self, 'settings', settings)

        # Initialize logging
        if self.settings.logging is True:
            setup_logging()
        elif self.settings.logging is not False:
            setup_logging(self.settings.logging)

        # Initialize namespaces and packages
        object.__setattr__(self, 'namespaces', WeakValueDictionary())
        object.__setattr__(self, 'packages', WeakValueDictionary())
        object.__setattr__(self, 'metadata', MetaDataProxy(
            self, lambda: [p.metadata for p in self.packages.values()]
        ))
        object.__setattr__(self, 'registry', RegistryProxy(
            self, lambda: [p.registry for p in self.packages.values()]
        ))

        # Initialize sessions and database
        routers: list[DatabaseRouter] = []
        for name in self.settings.database_routers:
            router_module = import_module(name)
            for router_name in dir(router_module):
                router = getattr(router_module, router_name)
                if inspect.isclass(router) \
                        and issubclass(router, DatabaseRouter) \
                        and not inspect.isabstract(router):
                    routers.append(router())
                else:
                    raise PlateformeError(
                        f"Cannot import database router {router_name!r} from "
                        f"module {name!r}. The router is not a subclass of "
                        f"`DatabaseRouter`.",
                        code='plateforme-invalid-router',
                    )
        object.__setattr__(self, 'database',
            DatabaseManager(self.settings.database_engines, routers))
        object.__setattr__(self, 'async_session',
            async_session_factory(routing=self.database, scoped=True))
        object.__setattr__(self, 'session',
            session_factory(routing=self.database, scoped=True))
        object.__setattr__(self, 'token', None)

        # Finalize setup
        self.add_namespaces(*self.settings.namespaces)
        self.add_packages(*self.settings.packages)
        self.setup_api(reset=True)

        # Register the application
        from .runtime import __plateforme__
        with __plateforme__.lock('apps'):
            if self.name in __plateforme__.apps:
                raise PlateformeError(
                    f"Application {str(self)!r} is already registered within "
                    f"the runtime environment.",
                    code='plateforme-invalid-application',
                )
            __plateforme__.apps[self.name] = self

        # Set application context
        if self.settings.context:
            PLATEFORME_CONTEXT.set(self)

        logger.info(f"({self}) initialized")

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        """The application entry point.

        It makes the Plateforme instance an asynchronous callable, delegating
        the call to the `APIManager` app.
        """
        # Set application context
        token = PLATEFORME_CONTEXT.set(self)

        # Mount the application
        if not self.__plateforme_mounted__:
            packages = set()
            for package in self.packages.values():
                if package.settings.auto_mount:
                    packages.add(package.name)
            if packages:
                self.mount_packages(*packages, force=False, raise_errors=False)
            object.__setattr__(self, '__plateforme_mounted__', True)

        # Process the request
        await self.api(scope, receive, send)

        # Reset application context
        PLATEFORME_CONTEXT.reset(token)

    def __enter__(self) -> Self:
        # Reinstate the plateforme token when entering the app context
        object.__setattr__(self, 'token', PLATEFORME_CONTEXT.set(self))
        return self

    def __exit__(self, *args: Any) -> None:
        # Clear the plateforme token when exiting the app context
        if self.token:
            PLATEFORME_CONTEXT.reset(self.token)  # type: ignore[arg-type]
            object.__setattr__(self, 'token', None)

    @property
    def name(self) -> str:
        """The application title."""
        return to_snake_case(self.settings.title)

    @property
    def title(self) -> str:
        """The application title."""
        return self.settings.title

    @emit()
    def add_namespaces(
        self,
        /,
        *args: str | tuple[str, NamespaceSettings],
        raise_errors: bool = True,
    ) -> None:
        """Add given namespaces to the application.

        It adds the provided namespace name to the application with optional
        settings. The settings are used to configure the namespace behavior
        within the application.

        Args:
            *args: A list of namespace name with optional settings to add to
                the application. The settings are used to configure the
                namespace behavior within the application.
            raise_errors: Whether to raise errors or fail silently.
                Defaults to ``True``.

        Raises:
            PlateformeError: If a namespace is already installed.
        """
        for arg in args:
            # Unwrap namespace and settings
            if isinstance(arg, tuple):
                name, settings = arg
            else:
                name = arg
                settings = None
            # Check if namespace is already installed
            if name in self.namespaces:
                if not raise_errors:
                    continue
                raise PlateformeError(
                    f"Namespace {name!r} already exists within application "
                    f"{str(self)!r}.",
                    code='plateforme-invalid-namespace',
                )
            # Add namespace
            namespace = runtime.import_namespace(name, create_if_missing=True)
            namespace._add_impl(self, settings=settings)

            logger.info(f"({self}) ns:{name} -> added")

    @emit()
    def remove_namespaces(
        self,
        /,
        *names: str,
        raise_errors: bool = True,
    ) -> None:
        """Remove given namespaces from the application.

        It removes the provided namespace names from the application and cleans
        up the auto-imported dependencies.

        Args:
            *names: A list of namespace names to remove from the application.
            raise_errors: Whether to raise errors or fail silently.
                Defaults to ``True``.

        Raises:
            PlateformeError: If a namespace does not exist within the
                application.
        """
        for name in names:
            if name not in self.namespaces:
                if not raise_errors:
                    continue
                raise PlateformeError(
                    f"Namespace {name!r} does not exist within application "
                    f"{str(self)!r}.",
                    code='plateforme-invalid-namespace',
                )
            impl = self.namespaces.pop(name)
            impl.namespace._remove_impl(self)

            logger.info(f"({self}) ns:{name} -> removed")

    @emit()
    def add_packages(
        self,
        /,
        *args: str | tuple[str, PackageSettings],
        raise_errors: bool = True,
    ) -> None:
        """Add given packages to the application.

        It adds the provided package name to the application with optional
        settings. The settings are used to configure the package behavior
        within the application. Finally, it checks for package dependencies and
        imports them if the ``auto_import_dependencies`` setting is enabled.

        Args:
            *args: A list of package name with optional settings to add to
                the application. The settings are used to configure the package
                behavior within the application.
            raise_errors: Whether to raise errors or fail silently.
                Defaults to ``True``.

        Raises:
            PlateformeError: If a package is already installed or if the
                ``auto_import_dependencies`` setting is disabled and a package
                dependency is not installed.
        """
        # Gather packages to add
        config: dict[str, PackageSettings | None] = dict()
        backlog: dict[str, Package] = dict()

        # Helper function to walk and collect packages
        def walk_dependencies(
            package: Package, guard: frozenset[str] = frozenset()
        ) -> None:
            if package.name in guard:
                return
            backlog[package.name] = package
            package_deps = runtime.get_dependencies(package, kind='packages')
            for package_dep in package_deps:
                if package_dep.name not in self.packages \
                        and not self.settings.auto_import_dependencies:
                    if not raise_errors:
                        continue
                    raise PlateformeError(
                        f"Cannot import package dependency "
                        f"{package_dep.name!r}. The package dependency is not "
                        f"installed and the `auto_import_dependencies` "
                        f"setting is disabled. Please either install the "
                        f"package manually or set the "
                        f"`auto_import_dependencies` setting to `True`.",
                        code='plateforme-invalid-package',
                    )
                walk_dependencies(package_dep, guard | {package.name})

        # Collect packages
        for arg in args:
            # Unwrap package and settings
            if isinstance(arg, tuple):
                name, settings = arg
            else:
                name = arg
                settings = None

            # Handle caller package reference
            if name == CALLER_REF:
                caller_path = resolve_relative_import_name(
                    self.caller_package.name,
                    self.caller
                )
                caller_settings = PackageSettings(
                    api_resources=[caller_path],
                    api_services=[caller_path],
                )
                name = self.caller_package.name
                package = self.caller_package
                settings = merge_settings(caller_settings, settings)
            # Handle normal package import
            else:
                package = runtime.import_package(name, force_resolution=False)

            # Check if provided package name is duplicated
            if name in config:
                raise PlateformeError(
                    f"Duplicated package {name!r} found within provided "
                    f"package names.",
                    code='plateforme-invalid-package',
                )

            # Check if package is already installed
            if name in self.packages:
                if not raise_errors:
                    continue
                raise PlateformeError(
                    f"Package {name!r} already exists within application "
                    f"{str(self)!r}.",
                    code='plateforme-invalid-package',
                )

            config[name] = settings

            walk_dependencies(package)

        # Add packages
        for name, package in reversed(list(backlog.items())):
            # Skip already installed packages
            if name in self.packages:
                continue

            # Check if package has dependencies not planned to be added
            if check_deps := [
                dependency.name
                for dependency
                in runtime.get_dependencies(package, kind='packages')
                if dependency.name not in backlog
            ]:
                if not raise_errors:
                    backlog.pop(name)
                    continue
                raise PlateformeError(
                    f"Cannot add package {name!r} to the application "
                    f"{str(self)!r}. The package has dependencies not planned "
                    f"to be added: {', '.join(check_deps)}.",
                    code='plateforme-invalid-package',
                )

            package._add_impl(
                self,
                settings=config.get(name, None),
                auto_generated=name not in config,
                auto_import_namespace=self.settings.auto_import_namespaces,
            )

            logger.info(f"({self}) pkg:{name} -> added")

    @emit()
    def remove_packages(
        self,
        /,
        *args: str,
        raise_errors: bool = True,
    ) -> None:
        """Remove given packages from the application.

        It removes the provided package names from the application and cleans
        up the auto-imported dependencies.

        Args:
            *args: A list of package module names to remove from the
                application.
            raise_errors: Whether to raise errors or fail silently.
                Defaults to ``True``.

        Raises:
            PlateformeError: If a package does not exist within the application
                or if the package has dependents not planned to be removed.
        """
        # Gather packages to remove
        config: set[str] = set()
        backlog: dict[str, Package] = dict()

        # Helper function to walk and collect packages
        def walk_dependencies(
            package: Package, guard: frozenset[str] = frozenset()
        ) -> None:
            if package.name in guard:
                return
            backlog[package.name] = package
            package_deps = runtime.get_dependencies(package, kind='packages')
            for package_dep in package_deps:
                if not package_dep.impl.auto_generated:
                    continue
                if not all(
                    dependent.name in backlog
                    for dependent
                    in runtime.get_dependents(package_dep, kind='packages')
                ):
                    continue
                walk_dependencies(package_dep, guard | {package.name})

        # Collect packages
        for name in args:
            # Handle caller module reference
            if name == CALLER_REF:
                name = self.caller_package.name

            # Check if provided package name is duplicated
            if name in config:
                raise PlateformeError(
                    f"Duplicated package {name!r} found within provided "
                    f"package names.",
                    code='plateforme-invalid-package',
                )

            # Check if package is installed
            if name not in self.packages:
                if not raise_errors:
                    continue
                raise PlateformeError(
                    f"Package {name!r} does not exist within application "
                    f"{str(self)!r}.",
                    code='plateforme-invalid-package',
                )
            else:
                config.add(name)

            package = self.packages[name].package
            walk_dependencies(package)

        # Remove packages
        for name, package in list(backlog.items()):
            # Check if package has dependents not planned to be removed
            if check_deps := [
                dependent.name
                for dependent
                in runtime.get_dependents(package, kind='packages')
                if dependent.name not in backlog
            ]:
                if not raise_errors:
                    backlog.pop(name)
                    continue
                raise PlateformeError(
                    f"Cannot remove package {name!r} from the application "
                    f"{str(self)!r}. The package has dependents not planned "
                    f"to be removed: {', '.join(check_deps)}.",
                    code='plateforme-invalid-package',
                )

            package._remove_impl(self)

            logger.info(f"({self}) pkg:{name} -> removed")

    @emit()
    def setup_api(self, *, reset: bool = False) -> None:
        """Setup the application API manager.

        Args:
            reset: Whether to reset the application API manager, i.e. clear all
                existing routes from current router. Defaults to ``False``.
        """
        # Resolve base configuration
        debug = self.settings.debug
        title = self.settings.title
        summary = self.settings.summary
        description = self.settings.description
        version = self.settings.version
        terms_of_service = self.settings.terms_of_service
        contact = self.settings.contact
        license_info = self.settings.license
        deprecated = self.settings.deprecated

        # Documentation is available only at the namespace level
        self.settings.api.openapi_url = None

        # Update API middleware
        self.settings.api.middleware = [
            Middleware(BulkMiddleware),
            *(self.settings.api.middleware or []),
        ]

        # Build configuration dictionary
        config: dict[str, Any] = dict(
            debug=debug,
            title=title,
            summary=summary,
            description=description,
            version=version,
            terms_of_service=terms_of_service,
            contact=contact.model_dump() if contact else None,
            license_info=license_info.model_dump() if license_info else None,
            deprecated=deprecated,
            **self.settings.api.model_dump(),
        )

        # Setup manager and include current router if no reset
        router = None
        if not reset:
            router = self.api.router
        object.__setattr__(self, 'api', APIManager(**config))
        if not reset:
            assert router is not None
            self.api.include_router(router)

        # Add exception handlers
        for error, handler in EXCEPTION_HANDLERS.items():
            self.api.add_exception_handler(error, handler)

    @emit()
    def mount_namespaces(
        self,
        *names: str,
        force: bool = False,
        raise_errors: bool = True,
        propagate: bool = False,
        **overrides: Unpack[APIBaseRouterConfigDict],
    ) -> None:
        """Mount given namespaces into the application API manager.

        Args:
            *names: A list of namespace names to mount into the application
                namespace API manager
            force: Whether to force mount the namespaces even if they are
                already mounted. This will not raise an error if a namespace is
                already mounted, otherwise it will replace the existing
                namespace router with a new one. Defaults to ``False``.
            raise_errors: Whether to raise errors or fail silently if a
                namespace is already mounted within the API manager.
                Defaults to ``True``.
            propagate: Whether to propagate the mount operation to the
                namespaces. Defaults to ``False``.
            **overrides: Additional router configuration keyword arguments to
                override the default router configuration when including the
                namespace package routers.
        """
        namespaces = self._validate_namespace_names(
            *names, raise_errors=raise_errors
        )

        # Mount namespaces
        for namespace in namespaces:
            for route in self.api.routes:
                if namespace.slug != getattr(route, 'name', None):
                    continue
                if not force:
                    if not raise_errors:
                        continue
                    raise PlateformeError(
                        f"Namespace {namespace.name!r} is already mounted "
                        f"within application {str(self)!r}.",
                        code='plateforme-invalid-namespace',
                    )
                self.api.routes.remove(route)

            if propagate:
                namespace.mount(
                    force=force,
                    raise_errors=raise_errors,
                    **overrides
                )
            self.api.mount(namespace.path, namespace.api, namespace.slug)
            self._sort_api_routes()

            logger.info(f"({self}) ns:{namespace} -> mounted")

    @emit()
    def unmount_namespaces(
        self,
        *names: str,
        raise_errors: bool = True,
        propagate: bool = False,
    ) -> None:
        """Unmount given namespaces from the application API manager.

        Args:
            *names: A list of namespace names to unmount from the application
                namespace API manager.
            raise_errors: Whether to raise errors or fail silently if a
                namespace is not mounted within the API manager.
                Defaults to ``True``.
            propagate: Whether to propagate the unmount operation to the
                namespaces. Defaults to ``False``.
        """
        namespaces = self._validate_namespace_names(
            *names, raise_errors=raise_errors
        )

        # Unmount namespaces
        for namespace in namespaces:
            has_routes = False
            for route in self.api.routes:
                if namespace.slug != getattr(route, 'name', None):
                    continue
                self.api.routes.remove(route)
                has_routes = True
            if not has_routes and raise_errors:
                raise PlateformeError(
                    f"Namespace {namespace.name!r} is not mounted within "
                    f"application {str(self)!r}.",
                    code='plateforme-invalid-namespace'
                )
            if propagate:
                namespace.unmount(raise_errors=raise_errors)

            logger.info(f"({self}) ns:{namespace} -> unmounted")

    @emit()
    def mount_packages(
        self,
        *names: str,
        force: bool = False,
        raise_errors: bool = True,
        **overrides: Unpack[APIBaseRouterConfigDict],
    ) -> None:
        """Mount given packages into the application API manager.

        Args:
            *names: A list of package module names to mount into the
                application API manager.
            force: Whether to force mount the packages even if they are already
                mounted. This will not raise an error if a package is already
                mounted, otherwise it will replace the existing package router
                with a new one. Defaults to ``False``.
            raise_errors: Whether to raise errors or fail silently if a package
                is already mounted within the API manager.
                Defaults to ``True``.
            **overrides: Additional router configuration keyword arguments to
                override the default router configuration when including the
                package routers.
        """
        packages = self._validate_package_names(
            *names, raise_errors=raise_errors
        )

        # Collect namespaces
        namespaces: dict[NamespaceImpl, set[PackageImpl]] = {}
        for package in packages:
            namespaces[package.namespace] = \
                namespaces.get(package.namespace, set()) | {package}

        # Mount packages
        for namespace, namespace_packages in namespaces.items():
            for route in self.api.routes:
                if namespace.slug != getattr(route, 'name', None):
                    continue
                if not force:
                    if not raise_errors:
                        continue
                    raise PlateformeError(
                        f"Namespace {namespace.name!r} is not mounted within "
                        f"application {str(self)!r}.",
                        code='plateforme-invalid-namespace',
                    )
                self.api.routes.remove(route)
            namespace.mount(
                *[package.name for package in namespace_packages],
                force=force,
                raise_errors=raise_errors,
                **overrides,
            )
            self.api.mount(namespace.path, namespace.api, namespace.name)
            self._sort_api_routes()

    @emit()
    def unmount_packages(
        self,
        *names: str,
        raise_errors: bool = True,
    ) -> None:
        """Unmount given packages from the application API manager.

        Args:
            *names: A list of package module names to unmount from the
                application API manager.
            raise_errors: Whether to raise errors or fail silently if a package
                is not mounted within the API manager.
                Defaults to ``True``.
        """
        packages = self._validate_package_names(
            *names, raise_errors=raise_errors
        )

        # Collect namespaces
        namespaces: dict[NamespaceImpl, set[PackageImpl]] = {}
        for package in packages:
            namespaces[package.namespace] = \
                namespaces.get(package.namespace, set()) | {package}

        # Unmount packages
        for namespace, namespace_packages in namespaces.items():
            has_routes = False
            for route in self.api.routes:
                if namespace.slug != getattr(route, 'name', None):
                    continue
                self.api.routes.remove(route)
                has_routes = True
            if not has_routes and raise_errors:
                raise PlateformeError(
                    f"Namespace {namespace.name!r} is not mounted within a"
                    f"application {str(self)!r}.",
                    code='plateforme-invalid-namespace'
                )
            namespace.unmount(
                *[package.name for package in namespace_packages],
                raise_errors=raise_errors,
            )

    @typing.overload
    def get_dependencies(
        self,
        *,
        kind: Literal['links'],
        status: tuple[Lifecycle, ...] | None = None,
        max_depth: int | None = 1,
    ) -> set[ResourceFieldInfo]:
        ...

    @typing.overload
    def get_dependencies(
        self,
        *,
        kind: Literal['resources'],
        status: tuple[ResolvedState, ...],
        max_depth: int | None = 1,
    ) -> set[ResourceType]:
        ...

    @typing.overload
    def get_dependencies(
        self,
        *,
        kind: Literal['resources'],
        status: tuple[Literal[Lifecycle.UNKNOWN], ...],
        max_depth: int | None = 1,
    ) -> set[str]:
        ...

    @typing.overload
    def get_dependencies(
        self,
        *,
        kind: Literal['resources'],
        status: tuple[Lifecycle, ...] | None = None,
        max_depth: int | None = 1,
    ) -> set['ResourceType | str']:
        ...

    @typing.overload
    def get_dependencies(
        self,
        *,
        kind: Literal['packages'],
        status: tuple[Lifecycle, ...] | None = None,
        max_depth: int | None = 1,
    ) -> set[Package]:
        ...

    def get_dependencies(
        self,
        *,
        kind: Literal['links', 'resources', 'packages'],
        status: tuple[Lifecycle, ...] | None = None,
        max_depth: int | None = 1,
    ) -> (
        set[ResourceFieldInfo]
        | set[ResourceType | str] | set[ResourceType] | set[str]
        | set[Package]
    ):
        """Collect the dependencies of the application.

        This method returns the dependencies of the application based on the
        specified kind. It filters the runtime `dependencies` class dictionary
        to return only the dependencies of this application.

        Args:
            kind: The kind of dependencies to retrieve. It can be one of the
                following values
                - ``'links'``: Returns the linked field dependencies the
                    resources from this application rely on.
                - ``'resources'``: Returns the resource dependencies the
                    resources from this application rely on.
                - ``'packages'``: Returns the package dependencies the
                    resources from this application rely on.
            status: The tuple of dependencies lifecycle status to filter. Note
                that only the ``'links'`` and ``'resources'`` kinds support
                having this argument to include `Lifecycle.UNKNOWN`, where for
                the latter, it returns a set of the fully qualified names of
                the unresolved resources. When set to ``None``, it returns all
                the dependencies regardless of their status, except for the
                kind ``'packages'`` where only resolved dependencies are
                returned. Defaults to ``None``.
            max_depth: The maximum depth of dependencies to retrieve. If set to
                ``None``, it retrieves all dependencies no matter the depth.
                Defaults to ``1``, meaning that it retrieves only the direct
                dependencies.

        Returns:
            The specified kind dependencies of the application.

        Raises:
            ValueError: If the lifecycle status is invalid, i.e. when the
                filter includes `Lifecycle.UNKNOWN` for package dependencies.
        """
        return runtime.get_dependencies(
            [impl.package for impl in self.packages.values()],
            kind=kind,
            status=status,
            max_depth=max_depth,
        )

    @typing.overload
    def get_dependents(
        self,
        *,
        kind: Literal['links'],
        status: tuple[ResolvedState, ...] | None = None,
        max_depth: int | None = 1,
    ) -> set[ResourceFieldInfo]:
        ...

    @typing.overload
    def get_dependents(
        self,
        *,
        kind: Literal['resources'],
        status: tuple[ResolvedState, ...] | None = None,
        max_depth: int | None = 1,
    ) -> set[ResourceType]:
        ...

    @typing.overload
    def get_dependents(
        self,
        *,
        kind: Literal['packages'],
        status: tuple[ResolvedState, ...] | None = None,
        max_depth: int | None = 1,
    ) -> set[Package]:
        ...

    def get_dependents(
        self,
        *,
        kind: Literal['links', 'resources', 'packages'],
        status: tuple[ResolvedState, ...] | None = None,
        max_depth: int | None = 1,
    ) -> (
        set[ResourceFieldInfo]
        | set[ResourceType]
        | set[Package]
    ):
        """Collect the dependents of the application.

        This method returns the dependents of the application based on the
        specified kind. It filters the runtime `dependents` class dictionary
        to return only the dependents of this application.

        Args:
            kind: The kind of dependents to retrieve. It can be one of the
                following values
                - ``'links'``: Returns the linked field dependents that rely on
                    the resources from this application.
                - ``'resources'``: Returns the resource dependents that rely on
                    the resources from this application.
                - ``'packages'``: Returns the package dependents that rely on
                    the resources from this application.
            status: The tuple of dependents lifecycle status to filter. Note
                that the `Lifecycle.UNKNOWN` status is not supported for
                dependents as they are always resolved when evaluated. When set
                to ``None``, it returns all the dependents regardless of their
                lifecycle status. Defaults to ``None``.
            max_depth: The maximum depth of dependents to retrieve. If set to
                ``None``, it retrieves all dependents no matter the depth.
                Defaults to ``1``, meaning that it retrieves only the direct
                dependents.

        Returns:
            The specified kind dependents of the application.
        """
        return runtime.get_dependents(
            [impl.package for impl in self.packages.values()],
            kind=kind,
            status=status,
            max_depth=max_depth,
        )

    def get_resources(self) -> set[ResourceType]:
        """Collect the resources of the application.

        A method that filters the runtime `resources` class dictionary to
        return only the resources of this application.
        """
        return runtime.get_resources(
            [impl.package for impl in self.packages.values()]
        )

    def _sort_api_routes(self) -> None:
        """Sort the API routes based on the route path."""
        self.api.router.routes.sort(key=sort_key_for_routes)

    def _validate_namespace_names(
        self,
        *names: str,
        raise_errors: bool = True,
    ) -> set[NamespaceImpl]:
        """Validate the namespace names against the application.

        Args:
            *names: A list of namespace names to validate against the
                application.
            raise_errors: Whether to raise errors if a namespace name is not
                found in the application. Defaults to ``True``.
        """
        namespaces: set[NamespaceImpl]
        if not names:
            namespaces = set(self.namespaces.values())
        else:
            namespaces = set()
            for name in names:
                if name not in self.namespaces:
                    if not raise_errors:
                        continue
                    raise PlateformeError(
                        f"Namespace {name!r} does not exist within the "
                        f"application {str(self)!r}.",
                        code='plateforme-invalid-namespace',
                    )
                namespaces.add(self.namespaces[name])

        return namespaces

    def _validate_package_names(
        self,
        *names: str,
        raise_errors: bool = True,
    ) -> set[PackageImpl]:
        """Validate the package names against the application.

        Args:
            *names: A list of package module names to validate against the
                application.
            raise_errors: Whether to raise errors if a package name is not
                found in the application. Defaults to ``True``.
        """
        packages: set[PackageImpl]
        if not names:
            packages = set(self.packages.values())
        else:
            packages = set()
            for name in names:
                if name not in self.packages:
                    if not raise_errors:
                        continue
                    raise PlateformeError(
                        f"Package {name!r} does not exist within the "
                        f"application {str(self)!r}.",
                        code='plateforme-invalid-package',
                    )
                packages.add(self.packages[name])

        return packages

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError(
            f"Cannot set attribute {name!r} on class {self!r}. The class "
            f"does not support attribute assignment."
        )

    def __delattr__(self, name: str) -> None:
        raise AttributeError(
            f"Cannot delete attribute {name!r} on class {self!r}. The class "
            f"does not support attribute deletion."
        )

    def __repr__(self) -> str:
        return f"Plateforme('{self}')"

    def __str__(self) -> str:
        return to_kebab_case(self.settings.title)
