# plateforme.core.package
# -----------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides functionality for managing packages within the Plateforme
framework. It includes classes and functions for importing modules, retrieving
package configurations, and initializing the package catalog.

The `Package` class lifecycle is managed by the framework runtime environment
that enforces a singleton behavior for package instances. It is initialized
with a Python module name and provides access to the package's configuration,
metadata, and resources.

The `PackageImpl` class is a proxy object that provides access to the
implementation of a package within a given application context. It includes
additional configuration settings such as the namespace, slug, and file
system path.
"""

import inspect
import typing
from collections.abc import Iterable
from functools import wraps
from types import ModuleType
from typing import Any, Callable, ForwardRef, Self, Unpack

from . import runtime
from .api.routing import (
    APIEndpoint,
    APIRouteConfig,
    APIRouter,
    APIRouterConfigDict,
)
from .api.utils import generate_unique_id, sort_key_for_routes
from .associations import Association
from .catalogs import Catalog
from .context import PLATEFORME_CONTEXT
from .database.orm import Registry
from .database.schema import MetaData
from .errors import PlateformeError
from .managers import Manager
from .modules import get_exported_members, import_object, resolve_file_paths
from .namespaces import NamespaceImpl
from .patterns import to_name_case, to_path_case
from .proxy import Proxy, ProxyConfig
from .representations import ReprArgs, Representation
from .runtime import __plateforme__
from .services import (
    BaseService,
    BaseServiceWithSpec,
    ServiceType,
    bind_service,
    load_service,
    unbind_service,
)
from .settings import PackageSettings, merge_settings
from .specs import resolve_schema_model
from .typing import (
    Annotation,
    eval_type_lenient,
    get_object_name,
    get_parent_frame_namespace,
    is_abstract,
    is_resource,
)

if typing.TYPE_CHECKING:
    from .main import Plateforme
    from .resources import ResourceFieldInfo, ResourceType

__all__ = (
    'Package',
    'PackageImpl',
    'collect_api_resources',
    'collect_api_services',
)


# MARK: Package

@typing.final
class Package(Representation):
    """A package within the Plateforme framework.

    It is initialized with a python module name. It checks for a package
    configuration to ensure the given module name corresponds to an importable
    package within the Plateforme framework. Each package is uniquely
    represented as a singleton object, identified by its module name. This
    process guarantees the consistent and correct identification of Plateforme
    packages for further operations.

    The package class exposes a `catalog` attribute that maps the alias and
    slug names within the package namespace to their respective objects, either
    a resource type, an association (i.e. a tuple of one or two linked fields),
    or a service method. It also provides access to the package resources,
    dependencies, and dependents, as well as the package implementations within
    the current application context.

    Attributes:
        _impls: The registered package implementations as a dictionary
            mapping the application context to the package implementation.

        module: The package module object.
        name: The package module name that is unique within the entire runtime
            environment.
        info: Additional information about the package.
        catalog: A dictionary mapping the alias and slug names within the
            package namespace to their respective objects, either a resource
            type, an association, or a service method.
        metadata: The package resource metadata.
        registry: The package resource registry.
    """
    if typing.TYPE_CHECKING:
        _impls: dict['Plateforme | None', 'PackageImpl']
        module: ModuleType
        name: str
        info: dict[Any, Any] | None
        catalog: Catalog
        metadata: MetaData
        registry: Registry

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        """Create a new package instance.

        The `import_package` method should be used to retrieve a package
        instance based on the provided module name.

        This method prevents the instantiation of a package directly and raises
        an error if the user tries to create a package instance. It is intended
        to be used internally, it is called by the `import_package` method
        from the `runtime` module to create a package instance based on the
        specified module name when the package is not already registered in the
        runtime cache.
        """
        # Validate the method caller
        caller = get_parent_frame_namespace(depth=2, mode='globals') or {}
        if caller.get('__name__') != runtime.__name__:
            raise RuntimeError(
                "Cannot instantiate a package directly. Use the runtime "
                "`import_package` method to retrieve a package instance."
            )

        return super().__new__(cls)

    def __init__(
        self,
        name: str,
        module: ModuleType,
        *,
        info: dict[Any, Any] | None = None,
        settings: PackageSettings | None = None,
    ) -> None:
        """Initialize a package.

        Note:
            The `import_package` method should be used to retrieve a package
            instance based on the provided module name.
        """
        object.__setattr__(self, '_impls', {})
        object.__setattr__(self, 'module', module)
        object.__setattr__(self, 'name', name)
        object.__setattr__(self, 'info', info)

        self._add_impl(None, settings=settings, auto_generated=True)

        catalog = Catalog(self)
        metadata = MetaData(
            schema=self.impl.settings.namespace,
            schema_factory=lambda: self.impl.namespace.alias,
            info=info,
        )
        registry = Registry(metadata=metadata)

        object.__setattr__(self, 'catalog', catalog)
        object.__setattr__(self, 'metadata', metadata)
        object.__setattr__(self, 'registry', registry)

    @property
    def impl(self) -> 'PackageImpl':
        """The current package implementation based on the app context.

        A read-only property that returns the package implementation based on
        the application context. If no context is available, it returns the
        package default implementation. Otherwise, it raises an error if the
        package implementation is not available in the current application
        context.
        """
        context = PLATEFORME_CONTEXT.get()
        if context not in self._impls:
            assert context is not None
            raise PlateformeError(
                f"Package {self.name!r} is not available in the current "
                f"application context {str(context)!r}.",
                code='package-not-available',
            )
        return self._impls[context]

    def _add_impl(
        self,
        context: 'Plateforme | None',
        *,
        settings: PackageSettings | None = None,
        auto_generated: bool = False,
        auto_import_namespace: bool = True,
    ) -> 'PackageImpl':
        """Add a package implementation within the package.

        Args:
            context: The application context to associate with the package
                implementation.
            settings: The package settings to use. Defaults to an empty
                `PackageSettings` object.
            auto_generated: Whether the package implementation is
                auto-generated and should not be persisted when removing
                dependent packages. Defaults to ``False``.
            auto_import_namespace: Whether to automatically import and create
                the namespace for the package implementation.
                Defaults to ``True``.
        """
        # Check for existing implementation
        if context in self._impls:
            raise PlateformeError(
                f"Invalid package implementation for package {self.name!r}. "
                f"The implementation is already registered for the "
                f"application context {str(context)!r}.",
                code='package-invalid-implementation',
            )

        # Add package implementation
        impl = PackageImpl(
            self,
            context,
            settings=settings,
            auto_generated=auto_generated,
            auto_import_namespace=auto_import_namespace,
        )
        if context:
            context.packages[self.name] = impl
        self._impls[context] = impl

        return impl

    def _remove_impl(self, context: 'Plateforme | None') -> None:
        """Remove a package implementation from the package.

        Args:
            context: The application context to remove the package
                implementation from.
        """
        # Check for existing implementation
        if context not in self._impls:
            raise PlateformeError(
                f"Invalid package implementation for package {self.name!r}. "
                f"The implementation is not registered for the application "
                f"context {str(context)!r}.",
                code='package-invalid-implementation',
            )

        # Remove package implementation
        for impl in list(self._impls.values()):
            impl.namespace._remove_package(self.name)
        if context:
            del context.packages[self.name]
        del self._impls[context]

    def _add_resource(self, resource: 'ResourceType') -> None:
        """Add a resource to the package.

        It processes all dependencies and dependents of the resource to ensure
        that all linked fields are properly registered within the package.

        If the target resource is not yet referenced within the package, the
        association build will be postponed until the target resource is
        initialized. This is used to ensure that both resources within an
        association are loaded before attempting to build it.

        Args:
            resource: The resource to add.
        """
        with __plateforme__.lock('packages', reentrant=True):
            # Add and check resource fully qualified name for duplicate key
            name = get_object_name(resource, fullname=True)
            if __plateforme__.resources.get(name) is not None:
                raise PlateformeError(
                    f"Invalid duplicate name {name!r} in the package "
                    f"{self.name!r}. Another resource with the same name is "
                    f"already registered.",
                    code='resource-invalid-config',
                )
            __plateforme__.resources[name] = resource

            # Add resource to catalog
            try:
                self.catalog._add(
                    resource,
                    alias=resource.resource_config.alias,
                    slug=resource.resource_config.slug,
                )
            except KeyError as error:
                raise PlateformeError(
                    f"Invalid duplicate catalog entry in the package "
                    f"{self.name!r}. Another resource or association with the "
                    f"same alias is already registered.",
                    code='resource-invalid-config',
                ) from error

            # Resolve dependencies target forward references
            for field in __plateforme__.dependencies.get(name, set()):
                # Skip resolved dependencies
                if not isinstance(field.target, str):
                    continue
                target = __plateforme__.resources.get(field.target, None)
                # Skip unresolved forward references
                if target is None:
                    continue
                field._update(target=target)

            # Resolve dependents target forward references
            for field in __plateforme__.dependents.get(name, set()):
                # Skip self-referencing dependent fields
                if field.target is field.owner:
                    continue
                # Check for invalid dependent field
                if not isinstance(field.target, str):
                    raise TypeError(
                        f"Invalid dependent field {field.alias!r} in resource "
                        f"{field.owner.__qualname__!r} with target "
                        f"{str(field.target)!r} in the package {self.name!r}. "
                        f"The dependent field must define a target resource "
                        f"name.",
                    )
                field._update(target=resource)

            # Process resource dependencies and dependents
            dependencies = __plateforme__.dependencies.get(name, set()).copy()
            dependents = __plateforme__.dependents.get(name, set()).copy()

            # Process resource associations
            associations: list[Association] = []

            # Retrieve associations for common dependencies and dependents
            for dependency in set(dependencies):
                for dependent in set(dependents):
                    if dependency.owner == dependent.target \
                            and dependency.target == dependent.owner \
                            and dependency.association_alias == \
                                dependent.association_alias:
                        associations.append(Association(dependency, dependent))
                        dependencies.remove(dependency)
                        dependents.remove(dependent)

            # Retrieve associations for standalone dependencies. Dependencies
            # without a resolved target resource (i.e. forward references) are
            # skipped and will be processed when the target resource is
            # initialized.
            for dependency in set(dependencies):
                if dependency.target \
                        and not isinstance(dependency.target, str):
                    associations.append(Association(dependency))
                    dependencies.remove(dependency)

            # Retrieve associations for standalone dependents
            for dependent in set(dependents):
                associations.append(Association(dependent))
                dependents.remove(dependent)

            # Build associations
            for association in associations:
                association.build()

    def _add_resource_dependency(self, field: 'ResourceFieldInfo') -> None:
        """Add a linked field to the package dependencies and dependents.

        The linked field is added to the dependencies of the owner resource and
        to the dependents of the target resource. It ensures that the linked
        field is properly registered within the package and that the package
        resources are correctly linked.

        Args:
            field: The linked field to add as a dependency and a
            dependent.
        """
        # Check for invalid dependency
        if not is_resource(field.owner) or field.target is None:
            raise PlateformeError(
                f"Invalid field for resource {field.owner.__qualname__!r} and "
                f"field {field.alias!r} with target {str(field.target)!r} in "
                f"the package {self.name!r}. The linked field must define an "
                f"owner and a target resources.",
                code='field-invalid-config',
            )

        with __plateforme__.lock('packages', reentrant=True):
            # Add dependency to package
            assert field.owner is not None
            owner_name = get_object_name(field.owner, fullname=True)
            __plateforme__.dependencies.setdefault(owner_name, set())
            __plateforme__.dependencies[owner_name].add(field)

            # Add dependent to package
            assert field.target is not None
            target_name = get_object_name(field.target, fullname=True)
            __plateforme__.dependents.setdefault(target_name, set())
            __plateforme__.dependents[target_name].add(field)
            __plateforme__.resources.setdefault(target_name, None)

    def _remove_resource(self, name: str) -> None:
        """Remove a resource from the package.

        It also handles resource weak reference finalization ensuring that the
        catalog, resources, dependencies, and dependents entries of the
        resource are properly cleaned up.

        Args:
            name: The fully qualified name of the resource to remove.

        Note:
            This method is an internal function and should not be called
            directly by the user outside of the package context.
        """
        # Check for existing resource
        if name not in __plateforme__.resources:
            raise PlateformeError(
                f"Invalid resource name {name!r} in the package "
                f"{self.name!r}. The resource is not registered.",
                code='resource-invalid-config',
            )

        with __plateforme__.lock('packages', reentrant=True):
            # Remove objects
            for obj in list(self.catalog.objects):
                if isinstance(obj, Association):
                    if any(
                        get_object_name(link.owner, fullname=True) == name
                        for link in obj.links
                    ):
                        self.catalog._remove(obj)
                elif get_object_name(obj, fullname=True) == name:
                    self.catalog._remove(obj)

            # Remove resource
            __plateforme__.resources.pop(name, None)
            # Update resource
            for field in __plateforme__.dependents.get(name, set()):
                field._update(target=name)
            # Remove dependencies and dependents
            for field in __plateforme__.dependencies.get(name, set()):
                target_name = get_object_name(field.target, fullname=True)
                if target_name in __plateforme__.dependents:
                    __plateforme__.dependents[target_name].remove(field)
                    if not __plateforme__.dependents[target_name]:
                        __plateforme__.dependents.pop(target_name)
            __plateforme__.dependencies.pop(name, None)

    def _clear_cache(self) -> None:
        """Clear the package cache.

        It removes all resources instances from the package, clears and
        disposes the SQLAlchemy metadata and registry, and cleans up internal
        package implementations.

        Note:
            This method should be used with caution, as it permanently clears
            the package from all its associated catalog objects. It is intended
            for testing or debugging scenarios where the package and resources
            instances need to be reset.
        """
        import gc

        gc.collect()

        contexts = self._impls.keys()
        for context in contexts:
            if context is None:
                continue
            self._remove_impl(context)

        for resource in runtime.get_resources():
            name = get_object_name(resource, fullname=True)
            self._remove_resource(name)

        self.metadata.clear()
        self.registry.dispose()

    def __setattr__(self, name: str, value: Any) -> None:
        # Only allow setting private and dunder attributes
        if not name.startswith('_'):
            raise AttributeError(
                f"Cannot set attribute {name!r} on class {self!r}. The "
                f"package class does not support attribute setting for public "
                f"attributes."
            )
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        # Only allow deleting private and dunder attributes
        if not name.startswith('_'):
            raise AttributeError(
                f"Cannot delete attribute {name!r} on class {self!r}. The "
                f"package class does not support attribute deletion for "
                f"public attributes."
            )
        super().__delattr__(name)

    def __repr_args__(self) -> ReprArgs:
        yield (None, self.name)


# MARK: Package Manager

class PackageManager(Manager['PackageImpl']):
    """A package implementation manager.

    It provides a common interface to access and manage the service methods
    associated with a package implementation.
    """
    if typing.TYPE_CHECKING:
        __config_managed__: 'PackageImpl'

    @property
    def package(self) -> 'PackageImpl':
        return self.__config_managed__

    def _add_method(self, name: str, method: Callable[..., Any]) -> None:
        """Add a method to the manager.

        Args:
            name: The name of the method to add.
            method: The method to add to the manager.

        Raises:
            AttributeError: If the method already exists within the manager of
                the managed instance or type, or if the method is private.
        """
        if isinstance(method, APIEndpoint):
            self.package.catalog._add(
                method,
                alias=method.__config_route__.alias,
                slug=method.__config_route__.slug,
            )
        super()._add_method(name, method)

    def _remove_method(self, name: str) -> None:
        """Remove a method from the manager.

        Args:
            name: The name of the method to remove.

        Raises:
            AttributeError: If the method does not exist within the manager of
                the managed instance or type.
        """
        method = self.__dict__.get(name, None)
        if isinstance(method, APIEndpoint):
            self.package.catalog._remove(method)
        super()._remove_method(name)

    def __repr__(self) -> str:
        return f'PackageManager({self})'


# MARK: Package Implementation

class PackageImpl(Proxy[Package], Representation):
    """A package implementation proxy class.

    It defines the implementation details of a package within the Plateforme
    framework. It extends the `Proxy` class and adds additional information
    about the package.

    Attributes:
        context: The application context associated with the package
            implementation.
        namespace: The package namespace used to load the package and its
            resources within an application and to group resources to avoid
            alias collisions.
        objects: The package manager to access and manage the service methods
            associated with the package implementation.
        services: The service instances associated with the package
            implementation.
        settings: The package settings to use for the implementation.
        auto_generated: Whether the package implementation is auto-generated
            and should not be persisted when removing dependent packages.
        file_path: A string that defines the filesystem path of the package
            module. It is used to load package related assets from the
            filesystem. When not provided, it is resolved from the package
            module.
    """
    if typing.TYPE_CHECKING:
        # Package proxy
        _impls: dict['Plateforme | None', Self]
        module: ModuleType
        name: str
        info: dict[Any, Any] | None
        catalog: Catalog
        metadata: MetaData
        registry: Registry

        # Implementation
        context: 'Plateforme | None'
        namespace: NamespaceImpl
        objects: PackageManager
        services: tuple[BaseService, ...]
        settings: PackageSettings
        auto_generated: bool
        file_path: str

    __config__ = ProxyConfig(read_only=True)

    def __init__(
        self,
        package: Package,
        context: 'Plateforme | None',
        *,
        settings: PackageSettings | None = None,
        auto_generated: bool = False,
        auto_import_namespace: bool = True,
    ) -> None:
        """Initialize a package implementation proxy instance.

        Args:
            package: The package instance to proxy.
            context: The application context to associate with the package
                implementation.
            settings: The package settings to use. Defaults to an empty
                `PackageSettings` object.
            auto_generated: Whether the package implementation is
                auto-generated and should not be persisted when removing
                dependent packages. Defaults to ``False``.
            auto_import_namespace: Whether to automatically import and create
                the namespace for the package implementation.
                Defaults to ``True``.
        """
        super().__init__(package)
        object.__setattr__(self, 'context', context)
        object.__setattr__(self, 'objects', PackageManager(self))
        object.__setattr__(self, 'auto_generated', auto_generated)

        # Merge default implementation settings using "getattr" method to
        # avoid circular import issues when the default implementation is
        # initialized within the package module.
        settings = settings or PackageSettings()
        default_impl: PackageImpl | None = \
            package._impls.get(None, None)
        if default_impl is not None:
            settings = merge_settings(default_impl.settings, settings)
        object.__setattr__(self, 'settings', settings)

        # Validate file path
        file_path = settings.file_path or self._resolve_file_path()
        object.__setattr__(self, 'file_path', file_path)

        # Initialize namespace implementation
        namespace = runtime.import_namespace(
            self.settings.namespace or '',
            create_if_missing=auto_import_namespace,
        )
        if self.context in namespace._impls:
            namespace_impl = namespace._impls[self.context]
        elif not auto_import_namespace:
            raise PlateformeError(
                f"Invalid package implementation for package "
                f"{package.name!r}. The namespace {namespace.name!r} is not "
                f"available in the current application context "
                f"{str(context)!r}.",
                code='package-invalid-implementation',
            )
        else:
            namespace_impl = namespace._add_impl(
                self.context, auto_generated=auto_generated
            )
        namespace_impl._add_package(self)
        object.__setattr__(self, 'namespace', namespace_impl)

        # Initialize services
        object.__setattr__(self, 'services', ())
        services = collect_api_services(self)
        for service in services:
            self._add_services(service)

        package._impls[context] = self

    @property
    def package(self) -> Package:
        """The package associated with the implementation."""
        return self.__proxy__()

    @property
    def path(self) -> str:
        """The package API route path.

        It specifies the API route path of the package within an application.

        Examples:
            - ``/my-namespace``
        """
        return self.namespace.path

    def _add_services(
        self,
        *services: BaseService | ServiceType,
        raise_errors: bool = True,
    ) -> None:
        """Add services to the package implementation.

        It adds the provided services to the package implementation and binds
        them to the instance. The services are used to extend the package
        implementation with additional functionalities.

        Args:
            *services: The services to add to the package implementation. It
                can be either a service instance or class that will get
                instantiated. Services that implement a schema are forbidden.
            raise_errors: Whether to raise errors or fail silently.
                Defaults to ``True``.
        """
        for service in services:
            # Initialize service if necessary
            if isinstance(service, type):
                service = service()
            # Check if service is valid
            if not isinstance(service, BaseService):
                raise TypeError(
                    f"Invalid service {service!r} for package {self.name!r} "
                    f"within the application context {str(self.context)!r}. "
                    f"The service must be an instance of `BaseService`."
                )
            # Check if service is already bound to package
            if any(type(s) is type(service) for s in self.services) \
                    or self._get_service(service.service_config.name):
                if not raise_errors:
                    continue
                raise PlateformeError(
                    f"Service {service!r} is already bound to package "
                    f"{self.name!r} within the application context "
                    f"{str(self.context)!r}.",
                    code='services-already-bound',
                )
            # Bind service to package
            bind_service(service, self)
            # Add service to package
            self.services += (service,)
            # Add service wrapped methods to package manager
            methods = load_service(service)
            assert methods is not None
            for name, method in methods.items():
                self.objects._add_method(name, method)

    def _get_service(self, name: str) -> BaseService | None:
        """Get a service from the package implementation.

        It looks up each service within the package implementation and tries to
        retrieve a service with the provided name.

        Args:
            name: The name of the service to retrieve.

        Returns:
            The service with the provided name if found, ``None`` otherwise.
        """
        for service in self.services:
            if service.service_config.name == name:
                return service
        return None

    def _remove_services(
        self,
        *services: BaseService | str,
        raise_errors: bool = True,
    ) -> None:
        """Remove services from the package implementation.

        It removes the provided services from the package implementation and
        unbinds them from the instance.

        Args:
            *services: The services to remove from the package implementation.
                It can be either a service instance or the name of the service.
            raise_errors: Whether to raise errors or fail silently.
                Defaults to ``True``.
        """
        for service in services:
            # Retrieve service if name is provided
            if isinstance(service, str):
                service = self._get_service(service)  # type: ignore
            # Check if service exists
            if service is None or service not in self.services:
                if not raise_errors:
                    continue
                raise PlateformeError(
                    f"Service {service!r} does not exist for package "
                    f"implementation {self.name!r} within the application "
                    f"context {str(self.context)!r}.",
                    code='services-not-bound',
                )
            assert isinstance(service, BaseService)
            # Unbind service from package
            unbind_service(service)
            # Remove service from package
            object.__setattr__(self, 'services', tuple(
                s for s in self.services if s != service
            ))
            # Clean up resource manager wrapped methods
            # Remove service wrapped methods from package manager
            methods = self.objects._collect_methods(owner=service)
            for name in methods:
                self.objects._remove_method(name)

    def _collect_api_resources(self) -> set['ResourceType']:
        """Collect the top-level resources exposed to the API."""
        return collect_api_resources(self)

    def _collect_api_services(self) -> set[BaseService]:
        """Collect the services exposed to the API."""
        return collect_api_services(self)

    def _create_router(
        self, **overrides: Unpack[APIRouterConfigDict]
    ) -> APIRouter:
        """Create a new package API router with optional overrides.

        Args:
            **overrides: Additional keyword arguments to override the package
                API router configuration.
        """
        # Build configuration dictionary
        config: dict[str, Any] = dict(
            tags=self.settings.tags,
            deprecated=self.settings.deprecated,
            generate_unique_id_function=lambda route: \
                generate_unique_id(route, package=self.package),
            **self.settings.api.model_dump(),
        )
        config.update(overrides)

        # Create router and include resources and services
        router = APIRouter(**config)

        # Include resources
        for resource in self._collect_api_resources():
            router.include_router(resource._create_router())

        # Include services
        endpoints: list[APIEndpoint[Any, Any]] = []
        methods = self.objects._collect_methods(scope='endpoint')
        for method in methods.values():
            endpoint = _create_package_endpoint(self, method)
            endpoints.append(endpoint)
        router.include_endpoints(*endpoints, force_resolution=True)

        # Sort routes
        router.routes.sort(key=sort_key_for_routes)

        return router

    def _resolve_file_path(self) -> str:
        """Resolve the filesystem path of the package.

        It is used internally to resolve the filesystem path of the package
        module. If no valid path can be resolved, it raises an error.

        Returns:
            The filesystem path of the package module.

        Raises:
            PlateformeError: If the package module has no filesystem location
                or multiple filesystem locations.
        """
        paths = resolve_file_paths(self.module)

        if len(paths) > 1:
            raise PlateformeError(
                f"The package module {self.module!r} has multiple filesystem "
                f"locations ({paths!r}); you must configure this package with "
                f"a valid `path` attribute.",
                code='package-invalid-implementation',
            )
        if len(paths) == 0:
            raise PlateformeError(
                f"The package module {self.module!r} has no filesystem "
                f"location; you must configure this package with a valid "
                f"`path` attribute.",
                code='package-invalid-implementation',
            )

        return paths[0]

    def __repr_args__(self) -> ReprArgs:
        yield (None, self.name)
        if self.context is not None:
            yield ('app', self.context)


# MARK: Utilities

def collect_api_resources(
    package: PackageImpl,
    *,
    include: Iterable[str] | None = None,
    exclude: Iterable[str] | None = None,
) -> set['ResourceType']:
    """Collect API resources from a package.

    Args:
        package: The package to collect API resources from.
        include: An iterable of module or resource names that should be
            included in the collection. If provided, only the resources with
            the specified names are included. Defaults to ``None``.
        exclude: An iterable of module or resource names that should be
            excluded from the collection. If provided, the resources with the
            specified names are excluded. Defaults to ``None``.

    Returns:
        A set containing the matched resources based on the filter criteria.
    """
    modules: set[ModuleType] = set()
    resources: set['ResourceType'] = set()

    # Helper function to check if the object should be included
    def check(obj: Any) -> bool:
        name = get_object_name(obj, fullname=True)
        if include is not None and name not in include:
            return False
        if exclude is not None and name in exclude:
            return False
        return True

    # Helper function to filter resources
    def predicate(obj: Any) -> bool:
        return is_resource(obj) and not is_abstract(obj) and check(obj)

    # Helper function to collect resources
    def collect(module: ModuleType) -> None:
        if module in modules:
            return
        modules.add(module)
        members = get_exported_members(module)
        for _, member in members:
            if inspect.ismodule(member):
                collect(member)
            elif predicate(member):
                resources.add(member)

    # Retrieve lookup settings
    if settings := package.settings.api_resources:
        lookup = ['.'] if settings is True else list(settings)
    else:
        return set()

    # Import objects from lookup names
    objects = []
    for name in lookup:
        try:
            obj = import_object(name.ljust(1, '.'), package=package.name)
            if check(obj):
                objects.append(obj)
        except ImportError:
            pass

    # Collect resources
    for obj in objects:
        if inspect.ismodule(obj):
            collect(obj)
        elif predicate(obj):
            resources.add(obj)
        else:
            raise PlateformeError(
                f"Invalid API resource settings for package {package.name!r}. "
                f"The provided resource {obj!r} is not a valid resource.",
                code='package-invalid-config',
            )

    return resources


def collect_api_services(
    package: PackageImpl,
    *,
    include: Iterable[str] | None = None,
    exclude: Iterable[str] | None = None,
) -> set[BaseService]:
    """Collect API services from a package.

    Args:
        package: The package to collect API services from.
        include: An iterable of module or service names that should be included
            in the collection. If provided, only the services with the
            specified names are included. Defaults to ``None``.
        exclude: An iterable of module or service names that should be excluded
            from the collection. If provided, the services with the specified
            names are excluded. Defaults to ``None``.

    Returns:
        A set containing the matched services based on the filter criteria.
    """
    modules: set[ModuleType] = set()
    services: set[BaseService] = set()

    # Helper function to check if the object should be included
    def check(obj: Any) -> bool:
        name = get_object_name(obj, fullname=True)
        if include is not None and name not in include:
            return False
        if exclude is not None and name in exclude:
            return False
        return True

    # Helper function to filter services
    def predicate(obj: Any) -> bool:
        if isinstance(obj, type):
            if obj is BaseService:
                return False
            return issubclass(obj, BaseService) \
                and not issubclass(obj, BaseServiceWithSpec) \
                and check(obj)
        else:
            return isinstance(obj, BaseService) \
                and not isinstance(obj, BaseServiceWithSpec) \
                and check(obj)

    # Helper function to collect services
    def collect(module: ModuleType) -> None:
        if module in modules:
            return
        modules.add(module)
        members = get_exported_members(module)
        for _, member in members:
            if inspect.ismodule(member):
                collect(member)
            elif predicate(member):
                if isinstance(member, type):
                    member = member()
                services.add(member)

    # Retrieve lookup settings
    if settings := package.settings.api_services:
        lookup = ['.'] if settings is True else list(settings)
    else:
        return set()

    # Import objects from lookup names
    objects = []
    for name in lookup:
        try:
            obj = import_object(name.ljust(1, '.'), package=package.name)
            if check(obj):
                objects.append(obj)
        except ImportError:
            pass

    # Collect services
    for obj in objects:
        if inspect.ismodule(obj):
            collect(obj)
        elif predicate(obj):
            if isinstance(obj, type):
                obj = obj()
            services.add(obj)
        else:
            raise PlateformeError(
                f"Invalid API service settings for package {package.name!r}. "
                f"The provided service {obj!r} is not a valid service.",
                code='package-invalid-config',
            )

    return services


def _create_package_endpoint(
    package: PackageImpl,
    method: Callable[..., Any],
) -> APIEndpoint[Any, Any]:
    """Create a package endpoint from the provided package and method.

    Args:
        package: The package to create the endpoint for.
        method: The method to create the endpoint for.

    Returns:
        The created package endpoint.
    """
    # Resolve endpoint owner
    owner = getattr(method, '__config_owner__', package)

    # Helper to resolve forward refs and resource schema models in annotations
    def resolve_types(
        annotation: Any, *, root_schemas: tuple[str, ...] | None = None
    ) -> Any:
        if isinstance(annotation, str):
            annotation = ForwardRef(annotation)
        annotation = Annotation.replace(
            annotation,
            test=lambda ann: isinstance(ann, ForwardRef),
            resolver=lambda ann: eval_type_lenient(
                ann,
                fallback=True,
                fallback_module=getattr(owner, '__module__', None)
            ),
        )
        return resolve_schema_model(annotation, root_schemas=root_schemas)

    # Retrieve endpoint configuration
    if isinstance(method, APIEndpoint):
        config = method.__config_route__.copy()
    else:
        config = APIRouteConfig(
            path='/' + to_path_case(method.__name__),
            name=to_name_case(method.__name__),
        )

    # Update endpoint response model annotation
    if config.response_model is not None:
        config.response_model = resolve_types(
            config.response_model, root_schemas=('read', 'model')
        )

    # Retrieve method signature and parameters
    signature = inspect.signature(method)
    parameters = list(signature.parameters.values())

    # Update method parameter annotations
    for count, parameter in enumerate(parameters):
        parameters[count] = parameter.replace(
            annotation=resolve_types(parameter.annotation)
        )

    # Update method return annotation
    return_annotation = resolve_types(
        signature.return_annotation, root_schemas=('read', 'model')
    )

    # Wrap endpoint method
    @wraps(method)
    def endpoint(*args: Any, **kwargs: Any) -> Any:
        return method(*args, **kwargs)

    endpoint_signature = signature.replace(
        parameters=parameters,
        return_annotation=return_annotation,
    )

    # Update endpoint configuration and signature
    setattr(endpoint, '__config_route__', config)
    setattr(endpoint, '__signature__', endpoint_signature)
    assert isinstance(endpoint, APIEndpoint)

    return endpoint
