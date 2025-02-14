# plateforme.core.namespaces
# --------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing namespaces within the Plateforme
framework.
"""

import re
import typing
from typing import Any, Self, Unpack

from . import runtime
from .api.base import APIManager
from .api.routing import APIBaseRoute, APIBaseRouterConfigDict
from .api.utils import parse_unique_id
from .context import PLATEFORME_CONTEXT
from .errors import PlateformeError
from .patterns import RegexPattern, to_kebab_case, to_title_case
from .proxy import Proxy, ProxyConfig
from .representations import ReprArgs, Representation
from .settings import APISettings, NamespaceSettings, Settings, merge_settings
from .typing import get_parent_frame_namespace

if typing.TYPE_CHECKING:
    from .main import Plateforme
    from .packages import PackageImpl

__all__ = (
    'Namespace',
    'NamespaceImpl',
)


# MARK: Namespace

@typing.final
class Namespace(Representation):
    """A namespace placeholder for packages within the Plateforme framework.

    A namespace is a container for packages. It provides a way to group related
    packages together and manage their resources, routes, and API endpoints.

    Attributes:
        _impls: The registered namespace implementations as a dictionary
            mapping the application context to the namespace implementation.

        name: The name of the namespace that is unique within the entire
            runtime environment. It can be ``None`` for the default namespace,
            otherwise it must be a snake case formatted string of max 63
            characters.
    """
    if typing.TYPE_CHECKING:
        _impls: dict['Plateforme | None', 'NamespaceImpl']
        name: str

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        """Create a new namespace instance.

        The `import_namespace` method should be used to retrieve a namespace
        instance based on the provided name.

        This method prevents the instantiation of a namespace directly and
        raises an error if the user tries to create a namespace instance. It is
        intended to be used internally, it is called by the `import_namespace`
        method from the `runtime` module to create a namespace instance based
        on the specified name when the namespace is not already registered in
        the runtime cache.
        """
        # Validate the method caller
        caller = get_parent_frame_namespace(depth=2, mode='globals') or {}
        if caller.get('__name__') != runtime.__name__:
            raise RuntimeError(
                "Cannot instantiate a namespace directly. Use the runtime "
                "`import_namespace` method to retrieve a namespace instance."
            )

        return super().__new__(cls)

    def __init__(self, name: str):
        """Initialize a namespace.

        Note:
            The `import_namespace` method should be used to retrieve a
            namespace instance based on the provided name.
        """
        # Validate namespace name
        if name and (
            not re.match(RegexPattern.ALIAS, name)
            or len(name) > 63
        ):
            raise PlateformeError(
                f"Invalid namespace provided name {name!r}, it must be a "
                f"snake case formatted string of max 63 characters or `''`.",
                code='namespace-invalid-config',
            )

        object.__setattr__(self, '_impls', {})
        object.__setattr__(self, 'name', name)

    @property
    def impl(self) -> 'NamespaceImpl':
        """The current namespace implementation based on the app context.

        A read-only property that returns the namespace implementation based on
        the application context. If no context is available, it returns the
        namespace default implementation. Otherwise, it raises an error if the
        namespace implementation is not available in the current application
        context.
        """
        context = PLATEFORME_CONTEXT.get()
        if context not in self._impls:
            assert context is not None
            raise PlateformeError(
                f"Namespace {self.name!r} is not found in the current "
                f"application context {str(context)!r}.",
                code='namespace-not-found',
            )
        return self._impls[context]

    def _add_impl(
        self,
        context: 'Plateforme | None',
        *,
        settings: NamespaceSettings | None = None,
        auto_generated: bool = False,
    ) -> 'NamespaceImpl':
        """Add a namespace implementation within the namespace.

        Args:
            context: The application context to associate with the namespace
                implementation.
            settings: The namespace settings to use. Defaults to an empty
                `NamespaceSettings` object.
            auto_generated:
            auto_generated: Whether the namespace implementation is
                auto-generated and should not be persisted when removing
                dependent packages. Defaults to ``False``.
        """
        # Check for existing implementation
        if context in self._impls:
            raise PlateformeError(
                f"Invalid namespace implementation for namespace "
                f"{self.name!r}. The implementation is already registered for "
                f"the application context {str(context)!r}.",
                code='namespace-invalid-implementation',
            )

        # Add namespace implementation
        impl = NamespaceImpl(
            self, context, settings=settings, auto_generated=auto_generated
        )
        if context:
            context.namespaces[self.name] = impl
        self._impls[context] = impl

        return impl

    def _remove_impl(self, context: 'Plateforme | None') -> None:
        """Remove a namespace implementation from the namespace.

        Args:
            context: The application context to remove the namespace
                implementation from.
        """
        # Check for existing implementation
        if context not in self._impls:
            raise PlateformeError(
                f"Invalid namespace implementation for namespace "
                f"{self.name!r}. The implementation is not registered for the "
                f"application context {str(context)!r}.",
                code='namespace-invalid-implementation',
            )

        # Check for existing packages
        impl = self._impls[context]
        if impl.packages:
            raise PlateformeError(
                f"Cannot remove namespace implementation for namespace "
                f"{self.name!r} within the application context "
                f"{str(context)!r}. The implementation has packages assigned "
                f"to it.",
                code='namespace-invalid-implementation',
            )

        # Remove namespace implementation
        if context:
            del context.namespaces[self.name]
        del self._impls[context]

    def _clear_cache(self) -> None:
        """Clear the namespace cache.

        It cleans up internal namespace implementations.

        Note:
            This method should be used with caution, as it permanently clears
            the namespace from all its associated objects. It is intended for
            testing or debugging scenarios where the namespace instances need
            to be reset.
        """
        import gc

        gc.collect()
        for context in list(self._impls.keys()):
            if context is None:
                continue
            self._remove_impl(context)

    def __setattr__(self, name: str, value: Any) -> None:
        # Only allow setting private and dunder attributes
        if not name.startswith('_'):
            raise AttributeError(
                f"Cannot set attribute {name!r} on class {self!r}. The "
                f"namespace class does not support attribute setting for "
                f"public attributes."
            )
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        # Only allow deleting private and dunder attributes
        if not name.startswith('_'):
            raise AttributeError(
                f"Cannot delete attribute {name!r} on class {self!r}. The "
                f"namespace class does not support attribute deletion for "
                f"public attributes."
            )

    def __repr_args__(self) -> ReprArgs:
        yield (None, self.name)


# MARK: Namespace Implementation

class NamespaceImpl(Proxy[Namespace]):
    """A namespace implementation proxy class.

    It defines the implementation details of a namespace within the Plateforme
    framework. It extends the `Proxy` class and adds additional information
    about the namespace.

    Attributes:
        context: The application context associated with the namespace
            implementation.
        packages: A dictionary of packages implemented within the namespace.
        settings: The namespace settings to use for the implementation.
        auto_generated: Whether the namespace implementation is auto-generated
            and should not be persisted when removing dependent packages.
        api: The API manager of the namespace implementation.
    """
    if typing.TYPE_CHECKING:
        # Namespace proxy
        _impls: dict['Plateforme | None', Self]
        name: str

        # Implementation
        context: 'Plateforme | None'
        packages: dict[str, 'PackageImpl']
        settings: NamespaceSettings
        auto_generated: bool
        api: APIManager

    __config__ = ProxyConfig(read_only=True)

    def __init__(
        self,
        namespace: Namespace,
        context: 'Plateforme | None',
        *,
        settings: NamespaceSettings | None = None,
        auto_generated: bool = False,
    ):
        """Initialize a namespace implementation proxy instance.

        Args:
            namespace: The namespace instance to proxy.
            context: The application context to associate with the namespace
                implementation.
            settings: The namespace settings to use. Defaults to an empty
                `NamespaceSettings` object.
            auto_generated: Whether the namespace implementation is
                auto-generated and should not be persisted when removing
                dependent packages. Defaults to ``False``.
        """
        super().__init__(namespace)
        object.__setattr__(self, 'context', context)
        object.__setattr__(self, 'packages', {})
        object.__setattr__(self, 'auto_generated', auto_generated)

        # Merge default implementation settings using "getattr" method to
        # avoid circular import issues when the default implementation is
        # initialized within the namespace module.
        settings = settings or NamespaceSettings()
        default_impl: NamespaceImpl | None = namespace._impls.get(None, None)
        if default_impl is not None:
            settings = merge_settings(default_impl.settings, settings)
        object.__setattr__(self, 'settings', settings)

        self.setup_api(reset=True)

        namespace._impls[context] = self

    @property
    def namespace(self) -> Namespace:
        """The namespace associated with the implementation."""
        return self.__proxy__()

    @property
    def alias(self) -> str:
        """The namespace alias.

        It is used to to define which database schema should store its
        resources in an application. Multiple namespaces can share the same
        alias within an application. It must be formatted to snake case and
        defaults to the namespace name.

        Examples:
            - ``my_namespace``
        """
        if self.settings.alias is not None:
            return self.settings.alias
        return self.name

    @property
    def path(self) -> str:
        """The namespace API route path.

        It specifies the API route path of the namespace within an application.

        Examples:
            - ``/my-namespace``
        """
        return f'/{self.slug}' if self.slug else ''

    @property
    def slug(self) -> str:
        """The namespace slug.

        It is used to define which URL path should be used to access the
        namespace resources in an API. Multiple namespaces can share the same
        slug within an application. It must be formatted to kebab case and
        defaults to the kebab case of the namespace name.

        Examples:
            - ``my-namespace`` for ``my_namespace``
        """
        if self.settings.slug is not None:
            return self.settings.slug
        return to_kebab_case(self.name)

    @property
    def title(self) -> str | None:
        """The namespace human-readable title.

        It is used to display the namespace verbose name within an application.
        It defaults to the titleized version of the namespace alias.

        Examples:
            - ``My Namespace`` for ``my_namespace``
        """
        if self.settings.title is not None:
            return self.settings.title or None
        return to_title_case(self.alias) if self.alias else None

    def setup_api(self, *, reset: bool = False) -> None:
        """Setup the namespace API manager.

        Args:
            reset: Whether to reset the namespace API manager, i.e. clear all
                existing routes from current router. Defaults to ``False``.
        """
        # Resolve settings
        settings_base: Settings | NamespaceSettings = \
            self.context.settings if self.context else self.settings
        settings_api = merge_settings(
            APISettings(),
            self.context.settings.api if self.context else None,
            self.settings.api,
        )

        # Resolve base configuration
        debug = self.context.settings.debug if self.context else False
        title = self.title or settings_base.title
        summary = self.settings.summary or settings_base.summary
        description = self.settings.description or settings_base.description
        version = self.settings.version or settings_base.version
        terms_of_service = self.settings.terms_of_service \
            or settings_base.terms_of_service
        contact = self.settings.contact or settings_base.contact
        license_info = self.settings.license or settings_base.license
        deprecated = self.settings.deprecated or settings_base.deprecated

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
            **settings_api.model_dump(),
        )

        # Setup manager and include current router if no reset
        router = None
        if not reset:
            router = self.api.router
        object.__setattr__(self, 'api', APIManager(**config))
        if not reset:
            assert router is not None
            self.api.include_router(router)

    def mount(
        self,
        *names: str,
        force: bool = False,
        raise_errors: bool = True,
        **overrides: Unpack[APIBaseRouterConfigDict],
    ) -> None:
        """Mount given packages into the namespace API manager.

        Args:
            *names: A list of package module names to mount into the
                application namespace API manager.
            force: Whether to force mount the packages even if they are already
                mounted. This will not raise an error if a package is already
                mounted, otherwise it will replace the existing package router
                with a new one. Defaults to ``False``.
            raise_errors: Whether to raise errors or fail silently if a
                package is already mounted within the API manager.
                Defaults to ``True``.
            **overrides: Additional router configuration keyword arguments to
                override the default router configuration when including the
                package routers.
        """
        packages = self._validate_package_names(
            *names, raise_errors=raise_errors
        )

        # Mount packages
        for package in packages:
            for route in self.api.routes:
                if not isinstance(route, APIBaseRoute):
                    continue
                route_package, *_ = parse_unique_id(route.unique_id)
                if route_package != package.name:
                    continue
                if not force:
                    if not raise_errors:
                        continue
                    raise PlateformeError(
                        f"Package {package.name!r} is already mounted in the "
                        f"namespace {self.name!r} within application "
                        f"{str(self.context)!r}.",
                        code='namespace-invalid-package',
                    )
                self.api.routes.remove(route)

            router = package._create_router()
            self.api.include_router(router, **overrides)

    def unmount(
        self,
        *names: str,
        raise_errors: bool = True,
    ) -> None:
        """Unmount given packages from the namespace API manager.

        Args:
            *names: A list of package module names to unmount from the
                application namespace API manager.
            raise_errors: Whether to raise errors or fail silently if a
                package is not mounted within the API manager.
                Defaults to ``True``.
        """
        packages = self._validate_package_names(
            *names, raise_errors=raise_errors
        )

        # Unmount packages
        for package in packages:
            has_routes = False
            for route in self.api.routes:
                if not isinstance(route, APIBaseRoute):
                    continue
                route_package, *_ = parse_unique_id(route.unique_id)
                if route_package == package.name:
                    self.api.routes.remove(route)
                    has_routes = True
            if not has_routes and raise_errors:
                raise PlateformeError(
                    f"Package {package.name!r} is not mounted in the "
                    f"namespace {self.name!r} within application "
                    f"{str(self.context)!r}.",
                    code='namespace-invalid-package',
                )

    def _add_package(self, package: 'PackageImpl') -> None:
        """Add a package implementation to the namespace.

        Args:
            package: The package implementation instance to add to the
                namespace implementation.
        """
        if package.name in self.packages.keys() \
                or package in self.packages.values():
            raise PlateformeError(
                f"Package {package.name!r} already exists in the namespace "
                f"{self.name!r} within application {str(self.context)!r}.",
                code='namespace-invalid-package',
            )
        self.packages[package.name] = package

    def _remove_package(self, name: str) -> None:
        """Remove a package implementation from the namespace.

        Args:
            package: The package implementation instance to remove from the
                namespace implementation.
        """
        if name not in self.packages:
            raise PlateformeError(
                f"Package {name!r} does not exist in the namespace "
                f"{self.name!r} within application {str(self.context)!r}.",
                code='namespace-invalid-package',
            )
        self.packages.pop(name)

    def _validate_package_names(
        self,
        *names: str,
        raise_errors: bool = True,
    ) -> set['PackageImpl']:
        """Validate the package names against the namespace implementation.

        Args:
            *names: A list of package module names to validate against the
                namespace implementation.
            raise_errors: Whether to raise errors if a package name is not
                found in the namespace implementation. Defaults to ``True``.
        """
        packages: set['PackageImpl']
        if not names:
            packages = set(self.packages.values())
        else:
            packages = set()
            for name in names:
                if name not in self.packages:
                    if not raise_errors:
                        continue
                    raise PlateformeError(
                        f"Package {name!r} does not exist in the namespace "
                        f"{self.name!r} within application "
                        f"{str(self.context)!r}.",
                        code='namespace-invalid-package',
                    )
                packages.add(self.packages[name])

        return packages

    def __repr_args__(self) -> ReprArgs:
        yield (None, self.name)
        if self.context is not None:
            yield ('context', self.context)
