# plateforme.core.runtime
# -----------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides runtime utilities for the Plateforme framework.
"""

import dataclasses
import typing
import warnings
from collections.abc import Sequence
from enum import IntEnum
from threading import Lock, RLock
from types import ModuleType
from typing import Any, Callable, Dict, Literal, Self, Set, Union

if typing.TYPE_CHECKING:
    from .main import Plateforme
    from .namespaces import Namespace, NamespaceImpl
    from .packages import Package, PackageImpl
    from .projects import ProjectInfo
    from .resources import ResourceFieldInfo, ResourceType

__all__ = (
    # Mappings
    'AppMap',
    'NamespaceMap',
    'PackageMap',
    'ResourceMap',
    'ResourceLinkMap',
    # Lifecycle
    'Action',
    'Lifecycle',
    'ResolvedState',
    'ReversibleState',
    'SchedulableState',
    'Task',
    # Registry
    'apps',
    'dependencies',
    'dependents',
    'namespaces',
    'packages',
    'resources',
    # Dependencies
    'get_dependencies',
    'get_dependents',
    'get_resources',
    # Imports
    'import_namespace',
    'import_namespace_impl',
    'import_package',
    'import_package_impl',
    # Utilities
    'clear_cache',
    'info',
)


def __dir__() -> list[str]:
    return list(__all__)


# MARK: Mappings


AppMap = Dict[str, 'Plateforme']
"""A dictionary mapping the application names to their respective application
instance."""


NamespaceMap = Dict[str, 'Namespace']
"""A dictionary mapping the namespace names to their respective namespace
instance."""


PackageMap = Dict[str, 'Package']
"""A dictionary mapping the package module names to their respective package
instance."""


ResourceMap = Dict[str, 'ResourceType | None']
"""A dictionary mapping the resource fully qualified names to either their
respective resource type, or ``None`` if the resource is not yet resolved."""


ResourceLinkMap = Dict[str, Set['ResourceFieldInfo']]
"""A dictionary mapping the resource fully qualified names to their respective
set of resource linked fields."""


# MARK: Lifecycle

@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class Action:
    """A class that represents an action.

    This class is used to store a function with specific arguments and keyword
    arguments for later execution.
    """

    func: Callable[..., Any] = dataclasses.field(kw_only=False)
    """The function to be executed."""

    bound: bool = dataclasses.field(default=False)
    """Whether the function should be bound to the first argument."""

    args: tuple[Any, ...] = dataclasses.field(default_factory=tuple)
    """The positional arguments to be passed to the function."""

    kwargs: dict[str, Any] = dataclasses.field(default_factory=dict)
    """The keyword arguments to be passed to the function."""

    def __call__(self, obj: object | None = None, /) -> Any:
        """Execute the stored function with the provided object if bound."""
        if not self.bound:
            return self.func(*self.args, **self.kwargs)
        if obj:
            return self.func(obj, *self.args, **self.kwargs)

        raise ValueError('Cannot execute bound function without an object.')


class Lifecycle(IntEnum):
    """An enumeration of resources lifecycle states in the runtime."""

    UNKNOWN = 0
    """The resource status is unknown and has not been set. This status is
    returned when the resource state of a dependency is not yet resolved."""

    RESOLVED = 1
    """The resource is resolved and waiting for initialization. This is the
    default state of a resource when it has been first visited and before it is
    initializing, i.e. when not all its resource dependencies are resolved."""

    INITIALIZING = 2
    """The resource is in its initializing transition state, its base model is
    built and declarative model set up, and all the resource dependencies are
    resolved. It will transition to the next state when all its dependencies
    are also in their initializing state."""

    LOADING = 3
    """The resource is in its loading transition state, its objects and schemas
    are loaded, i.e. the resource own defined route endpoint methods, and the
    specifications, schema models and services defined in its configuration are
    loaded. This state is set when all resource dependencies are at least in
    their initializing state, and will transition to the next state when all
    its dependencies are also in their loading state."""

    BUILDING = 4
    """The resource is in its building transition state, its model, objects,
    and schemas are built. The resource is waiting for all its dependencies to
    be also built before finalizing its schema models and type adapter setup,
    and be ready for use. This step is necessary to ensure that all the
    resource dependencies schemas are fully loaded before building its own
    schema models."""

    FINALIZING = 5
    """The resource is in its finalizing transition state, its schema models
    and type adapter build are finalized. The resource is waiting for all its
    dependencies to be also finalized before transitioning to the ready state.
    """

    READY = 6
    """The resource is built and ready for use. Tasks scheduled in this state
    should not make changes that could disrupt dependent resources, as this is
    considered a stable state where the resource is available for use."""

    def previous(self) -> 'ReversibleState':
        """Return the previous state of the current resource status."""
        enums = tuple(self.__class__)
        index = enums.index(self)
        if index <= 1:
            value = self
        else:
            value = enums[index - 1]
        return value  # type: ignore

    def next(self) -> 'SchedulableState':
        """Return the next state of the current resource status."""
        enums = tuple(self.__class__)
        index = enums.index(self)
        if index == len(enums) - 1:
            value = self
        else:
            value = enums[index + 1]
        return value  # type: ignore

    def lower(self) -> tuple['ReversibleState', ...]:
        """Return the lower states of the current resource status."""
        enums = tuple(self.__class__)
        index = enums.index(self)
        return enums[:index]  # type: ignore

    def higher(self) -> tuple['SchedulableState', ...]:
        """Return the higher states of the current resource status."""
        enums = tuple(self.__class__)
        index = enums.index(self)
        return enums[index + 1:]  # type: ignore

    def __str__(self) -> str:
        return self.name.lower()


ResolvedState = Literal[
    Lifecycle.RESOLVED,
    Lifecycle.INITIALIZING,
    Lifecycle.LOADING,
    Lifecycle.BUILDING,
    Lifecycle.FINALIZING,
    Lifecycle.READY,
]
"""A literal type the for the resolved lifecycle states of a resource."""


ReversibleState = Literal[
    Lifecycle.RESOLVED,
    Lifecycle.INITIALIZING,
    Lifecycle.LOADING,
    Lifecycle.BUILDING,
    Lifecycle.FINALIZING,
]
"""A literal type for the reversible lifecycle states of a resource."""


SchedulableState = Literal[
    Lifecycle.INITIALIZING,
    Lifecycle.LOADING,
    Lifecycle.BUILDING,
    Lifecycle.FINALIZING,
    Lifecycle.READY,
]
"""A literal type for the lifecycle states of a resource where tasks can be
scheduled for execution."""


Task = Union[
    Action | Callable[[], Any],
    tuple[Action | Callable[[], Any], SchedulableState],
]
"""A task to be scheduled for execution."""


# MARK: Registry

class RegistryLock:
    """A lock manager for the runtime environment registry."""

    def __init__(self) -> None:
        self.locks: dict[str | None, Lock] = {None: Lock()}
        self.rlocks: dict[str | None, RLock] = {None: RLock()}

    @typing.overload
    def __call__(
        self,
        key: Literal['apps', 'namespaces', 'packages'] | None = None,
        *,
        reentrant: Literal[False] = False,
    ) -> Lock:
        ...

    @typing.overload
    def __call__(
        self,
        key: Literal['apps', 'namespaces', 'packages'] | None = None,
        *,
        reentrant: Literal[True],
    ) -> RLock:
        ...

    def __call__(
        self,
        key: Literal['apps', 'namespaces', 'packages'] | None = None,
        *,
        reentrant: bool = False,
    ) -> Union[Lock, RLock]:
        """Acquire the lock for the specified key.

        Args:
            key: The key to acquire the lock for. If set to ``None``, it
                acquires the default lock for the registry.
            reentrant: Whether to acquire a reentrant lock. Defaults to
                ``False``.
        """
        locks = typing.cast(
            dict[str | None, Any],
            self.rlocks if reentrant else self.locks
        )

        with self.locks[None]:
            if key not in locks:
                lock = RLock() if reentrant else Lock()
                locks[key] = lock
            else:
                lock = locks[key]

        return lock


class Registry:
    """The runtime environment registry internal class.

    Attributes:
        instance: A reference to the singleton instance of the runtime
            environment registry.
        lock: A lock object to ensure that managed class instances in the
            runtime registry are accessed and created in a thread-safe manner.

    Note:
        It enforce a singleton pattern to ensure that only one instance of the
        runtime environment registry is created and managed throughout the
        program. Additionally, it provides a thread-safe mechanism to create
        and access managed class instances in the runtime registry.
    """
    instance: Self | None = None
    lock = RegistryLock()

    def __new__(cls) -> 'Registry':
        """Create a new instance of the runtime environment registry.

        The first thread to acquire the lock, reaches this conditional, goes
        inside and creates the singleton instance. Once it leaves the lock
        block, a thread that might have been waiting for the lock release may
        then enter this section. But since the singleton instance is already
        initialized and assigned, the thread won't create a new object.
        """
        with cls.lock():
            if cls.instance is None:
                self = super().__new__(cls)
                cls.instance = self
            else:
                self = cls.instance

        return self

    def __init__(self) -> None:
        """Initialize the runtime environment registry."""
        self.apps: AppMap = {}
        self.namespaces: NamespaceMap = {}
        self.packages: PackageMap = {}
        self.dependencies: ResourceLinkMap = {}
        self.dependents: ResourceLinkMap = {}
        self.resources: ResourceMap = {}

__plateforme__ = Registry()


apps: AppMap
"""The applications initialized in the runtime environment.

A read-only module property that returns a dictionary mapping the application
names to their respective application instances.
"""


dependencies: ResourceLinkMap
"""The resource dependencies initialized in the runtime environment.

A read-only module property that returns a dictionary mapping the fully
qualified names of all resources to their weak sets of linked resource fields
they rely on ("dependencies"). Essentially, this attribute tracks what linked
fields each resource needs to function properly, with each linked field `owner`
attribute being the resource itself and its name the mapping entry.
"""


dependents: ResourceLinkMap
"""The resource dependents initialized in the runtime environment.

A read-only module property that returns a dictionary mapping the fully
qualified names of all resources to a weak sets of linked resource fields that
rely on those ("dependents"). Essentially, this attribute tracks what linked
fields will be affected if a resource is modified or made unavailable, with
each linked field `target` attribute being the resource itself and its name the
mapping entry.
"""


namespaces: NamespaceMap
"""The namespaces initialized in the runtime environment.

A read-only module property that returns a dictionary mapping the namespace
aliases to their respective namespace instances.
"""


packages: PackageMap
"""The packages initialized in the runtime environment.

A read-only module property that returns a dictionary mapping the package
module names to their respective package instances.
"""


resources: ResourceMap
"""The resources initialized in the runtime environment.

A read-only module property that returns a weak dictionary mapping the
resource fully qualified names to their respective resource type, or ``None``
if the resource is not yet resolved."""


def __getattr__(name: str) -> object:
    from copy import copy
    if name in __all__:
        return copy(getattr(__plateforme__, name))

    raise AttributeError(
        f"Module {__name__!r} has no attribute {name!r}."
    )


def __setattr__(name: str, value: object) -> None:
    raise AttributeError(
        f"Cannot set attribute {name!r} on module {__name__!r}."
    )


def __delattr__(name: str) -> None:
    raise AttributeError(
        f"Cannot delete attribute {name!r} on module {__name__!r}."
    )


# MARK: Dependencies

@typing.overload
def get_dependencies(
    scope: 'ResourceType | Package | Sequence[ResourceType | Package]',
    _guard: set[str] | None = None,
    *,
    kind: Literal['links'],
    status: tuple[Lifecycle, ...] | None = None,
    max_depth: int | None = 1,
) -> set['ResourceFieldInfo']:
    ...

@typing.overload
def get_dependencies(
    scope: 'ResourceType | Package | Sequence[ResourceType | Package]',
    _guard: set[str] | None = None,
    *,
    kind: Literal['resources'],
    status: tuple[ResolvedState, ...],
    max_depth: int | None = 1,
) -> set['ResourceType']:
    ...

@typing.overload
def get_dependencies(
    scope: 'ResourceType | Package | Sequence[ResourceType | Package]',
    _guard: set[str] | None = None,
    *,
    kind: Literal['resources'],
    status: tuple[Literal[Lifecycle.UNKNOWN], ...],
    max_depth: int | None = 1,
) -> set[str]:
    ...

@typing.overload
def get_dependencies(
    scope: 'ResourceType | Package | Sequence[ResourceType | Package]',
    _guard: set[str] | None = None,
    *,
    kind: Literal['resources'],
    status: tuple[Lifecycle, ...] | None = None,
    max_depth: int | None = 1,
) -> set['ResourceType | str']:
    ...

@typing.overload
def get_dependencies(
    scope: 'ResourceType | Package | Sequence[ResourceType | Package]',
    _guard: set[str] | None = None,
    *,
    kind: Literal['packages'],
    status: tuple[Lifecycle, ...] | None = None,
    max_depth: int | None = 1,
) -> set['Package']:
    ...

def get_dependencies(
    scope: 'ResourceType | Package | Sequence[ResourceType | Package]',
    _guard: set[str] | None = None,
    *,
    kind: Literal['links', 'resources', 'packages'],
    status: tuple[Lifecycle, ...] | None = None,
    max_depth: int | None = 1,
) -> (
    set['ResourceFieldInfo']
    | set['ResourceType | str'] | set['ResourceType'] | set[str]
    | set['Package']
):
    """Collect the dependencies from the provided scope.

    This method returns the dependencies of the provided scope based on the
    specified kind. It filters the runtime `dependencies` class dictionary to
    return only the dependencies of the scope.

    Args:
        scope: The scope to retrieve the dependencies from. It can be a single
            resource class, a package, or a sequence of resource classes or
            packages. If a package is provided, it retrieves the dependencies
            of all the resource classes within the package.
        kind: The kind of dependencies to retrieve. It can be one of the
            following values
            - ``'links'``: Returns the linked field dependencies the resource
                classes within the scope relies on.
            - ``'resources'``: Returns the resource dependencies the resource
                classes within the scope relies on.
            - ``'packages'``: Returns the package dependencies the resource
                classes within the scope relies on.
        _guard: A set of fully qualified names of resources to guard against
            cyclic dependencies. It is used internally to prevent infinite
            recursion. Defaults to an empty set.
        status: The tuple of dependencies lifecycle status to filter. Note that
            only the ``'links'`` and ``'resources'`` kinds support having this
            argument to include `Lifecycle.UNKNOWN`, where for the latter, it
            returns a set of the fully qualified names of the unresolved
            resources. When set to ``None``, it returns all the dependencies
            regardless of their status, except for the kind ``'packages'``
            where only resolved dependencies are returned.
            Defaults to ``None``.
        max_depth: The maximum depth of dependencies to retrieve. If set to
            ``None``, it retrieves all dependencies no matter the depth.
            Defaults to ``1``, meaning that it retrieves only the direct
            dependencies.

    Returns:
        The specified kind dependencies of the provided scope.

    Raises:
        ValueError: If the lifecycle status is invalid, i.e. when the
            filter includes `Lifecycle.UNKNOWN` for package dependencies.
    """
    from .typing import get_object_name, is_resource

    # Validate lifecycle status
    if kind == 'packages' and status and Lifecycle.UNKNOWN in status:
        raise ValueError(
            f"Invalid dependency lifecycle status filter. The provided "
            f"lifecycle status cannot target unresolved resources for package "
            f"dependencies.",
        )

    # Set unresolved flag
    if kind == 'packages':
        accept_unresolved = False
    elif status is None or Lifecycle.UNKNOWN in status:
        accept_unresolved = True
    else:
        accept_unresolved = False

    # Collect resources from the specified scope
    resources: set[ResourceType] = set()
    if not isinstance(scope, Sequence):
        scope = [scope]
    for item in scope:
        if is_resource(item):
            resources.add(item)
        else:
            resources.update([
                value for value in get_resources(item) if value is not None
            ])

    # Initialize recursion guard
    _guard = set() if _guard is None else _guard

    # Helper function to walk and collect resource dependencies
    def walk_dependencies(cls: 'ResourceType', depth: int = 1) -> set[Any]:
        name = get_object_name(cls, fullname=True)
        if name in _guard:
            return set()
        _guard.add(name)

        # Retrieve linked field dependencies
        link_deps: set['ResourceFieldInfo'] = set()
        for link_dep in __plateforme__.dependencies.get(name, []):
            assert link_dep.target is not None
            if isinstance(link_dep.target, str):
                # Skip unresolved dependencies if specified
                if not accept_unresolved:
                    continue
                link_deps.add(link_dep)
            else:
                # Filter by status if specified
                if status and link_dep.target.__state__.status not in status:
                    continue
                link_deps.add(link_dep)

        # Collect dependencies based on specified kind
        walked_deps: set[Any] = set()

        if kind == 'links':
            walked_deps.update(link_deps)

        elif kind == 'resources':
            for link_dep in link_deps:
                assert link_dep.target is not None
                if link_dep.target is cls:
                    continue
                walked_deps.add(link_dep.target)

        elif kind == 'packages':
            for link_dep in link_deps:
                assert is_resource(link_dep.target)
                package_dep = link_dep.target.resource_package
                if package_dep is cls.resource_package:
                    continue
                walked_deps.add(package_dep)

        # Collect dependencies recursively if max depth is not reached
        if max_depth and depth < max_depth:
            walked_deps.update([
                walk_dependencies(link_dep.target, depth + 1)
                for link_dep in link_deps
                if is_resource(link_dep.target)
            ])

        return walked_deps

    # Collect dependencies based on specified kind
    dependencies: set[Any] = set()
    for resource in resources:
        dependencies.update(walk_dependencies(resource))

    return dependencies


@typing.overload
def get_dependents(
    scope: 'ResourceType | Package | Sequence[ResourceType | Package]',
    _guard: set[str] | None = None,
    *,
    kind: Literal['links'],
    status: tuple[ResolvedState, ...] | None = None,
    max_depth: int | None = 1,
) -> set['ResourceFieldInfo']:
    ...

@typing.overload
def get_dependents(
    scope: 'ResourceType | Package | Sequence[ResourceType | Package]',
    _guard: set[str] | None = None,
    *,
    kind: Literal['resources'],
    status: tuple[ResolvedState, ...] | None = None,
    max_depth: int | None = 1,
) -> set['ResourceType']:
    ...

@typing.overload
def get_dependents(
    scope: 'ResourceType | Package | Sequence[ResourceType | Package]',
    _guard: set[str] | None = None,
    *,
    kind: Literal['packages'],
    status: tuple[ResolvedState, ...] | None = None,
    max_depth: int | None = 1,
) -> set['Package']:
    ...

def get_dependents(
    scope: 'ResourceType | Package | Sequence[ResourceType | Package]',
    _guard: set[str] | None = None,
    *,
    kind: Literal['links', 'resources', 'packages'],
    status: tuple[ResolvedState, ...] | None = None,
    max_depth: int | None = 1,
) -> (
    set['ResourceFieldInfo']
    | set['ResourceType']
    | set['Package']
):
    """Collect the dependents from the provided scope.

    This method returns the dependents of the provided scope based on the
    specified kind. It filters the runtime `dependents` class dictionary to
    return only the dependents of the scope.

    Args:
        scope: The scope to retrieve the dependents from. It can be a single
            resource class, a package, or a sequence of resource classes or
            packages. If a package is provided, it retrieves the dependents
            of all the resource classes within the package.
        kind: The kind of dependents to retrieve. It can be one of the
            following values
            - ``'links'``: Returns the linked field dependents that rely on the
                resource classes within the scope.
            - ``'resources'``: Returns the resource dependents that rely on the
                resource classes within the scope.
            - ``'packages'``: Returns the package dependents that rely on the
                resource classes within the scope.
        _guard: A set of fully qualified names of resources to guard
            against cyclic dependents. It is used internally to prevent
            infinite recursion. Defaults to an empty set.
        status: The tuple of dependents lifecycle status to filter. Note that
            the `Lifecycle.UNKNOWN` status is not supported for dependents as
            they are always resolved when evaluated. When set to ``None``, it
            returns all the dependents regardless of their status.
            Defaults to ``None``.
        max_depth: The maximum depth of dependents to retrieve. If set to
            ``None``, it retrieves all dependents no matter the depth.
            Defaults to ``1``, meaning that it retrieves only the direct
            dependents.

    Returns:
        The specified kind dependents of the provided scope.
    """
    from .typing import get_object_name, is_resource

    # Collect resources from the specified scope
    resources: set[ResourceType] = set()
    if not isinstance(scope, Sequence):
        scope = [scope]
    for item in scope:
        if is_resource(item):
            resources.add(item)
        else:
            resources.update([
                value for value in get_resources(item) if value is not None
            ])

    # Initialize recursion guard
    _guard = set() if _guard is None else _guard

    # Helper function to walk and collect resource dependents
    def walk_dependents(cls: 'ResourceType', depth: int = 1) -> set[Any]:
        name = get_object_name(cls, fullname=True)
        if name in _guard:
            return set()
        _guard.add(name)

        # Retrieve linked field dependents
        link_deps: set['ResourceFieldInfo'] = set()
        for link_dep in __plateforme__.dependents.get(name, []):
            # Filter by status if specified
            if status and link_dep.owner.__state__.status not in status:
                continue
            # Add dependent
            link_deps.add(link_dep)

        # Collect dependents based on specified kind
        walked_deps: set[Any] = set()

        if kind == 'links':
            walked_deps.update(link_deps)

        elif kind == 'resources':
            for link_dep in link_deps:
                if link_dep.owner is cls:
                    continue
                walked_deps.add(link_dep.owner)

        elif kind == 'packages':
            for link_dep in link_deps:
                package_dep = link_dep.owner.resource_package
                if package_dep is cls.resource_package:
                    continue
                walked_deps.add(package_dep)

        # Collect dependents recursively if max depth is not reached
        if max_depth and depth < max_depth:
            walked_deps.update([
                walk_dependents(link_dep.owner, depth + 1)
                for link_dep in link_deps
            ])

        return walked_deps

    # Collect dependents based on specified kind
    dependents: set[Any] = set()
    for resource in resources:
        dependents.update(walk_dependents(resource))

    return dependents


def get_resources(
    scope: 'Package | Sequence[Package] | None' = None,
) -> set['ResourceType']:
    """Collect the resources within the specified scope.

    A method that filters the runtime `resources` class dictionary with the
    provided scope to return only the matching resources.

    Args:
        scope: The scope to retrieve the resources from. It can be a package,
            a sequence of packages, or ``None`` to retrieve all the resources.
            Defaults to ``None``.

    Returns:
        The resources within the specified scope.
    """
    if scope and not isinstance(scope, Sequence):
        scope = [scope]

    return set(
        resource
        for resource in __plateforme__.resources.values()
        if resource is not None and (
            scope is None or resource.resource_package in scope
        )
    )


# MARK: Imports

def import_namespace(
    name: str, *, create_if_missing : bool = False,
) -> 'Namespace':
    """Import a namespace.

    It resolves the namespace name to either an existing namespace instance, or
    creates a new namespace with the specified name if it is not available in
    the runtime environment and `create_if_missing` flag is set to ``True``.

    Args:
        name: The name of the namespace to be resolved.
        create_if_missing: When set to ``True``, creates a new namespace with
            the specified name if it is not available in the runtime
            environment. If ``False``, the function raises an error for
            non-existent namespaces. Defaults to ``False``.

    Returns:
        The namespace instance associated with the specified name.
    """
    from .namespaces import Namespace

    with __plateforme__.lock('namespaces', reentrant=True):
        if name in __plateforme__.namespaces:
            return __plateforme__.namespaces[name]

        if not create_if_missing:
            raise ImportError(
                f"Namespace {name!r} is not available in the runtime "
                f"environment. Consider using `create_if_missing=True` to "
                f"create a new namespace."
            )

        # Create namespace instance
        namespace = Namespace(name)
        __plateforme__.namespaces[name] = namespace

    return namespace


def import_namespace_impl(
    name: str, context: 'Plateforme | None' = None
) -> 'NamespaceImpl':
    """Import a namespace implementation.

    Args:
        name: The name of the namespace implementation to be resolved.
        context: The application context to use for the namespace
            implementation. Defaults to ``None``.

    Returns:
        The namespace implementation associated with the specified name and
        application context.
    """
    namespace = import_namespace(name)

    if context not in namespace._impls:
        raise ImportError(
            f"Namespace {namespace.name!r} does not have an implementation "
            f"for the context provided {str(context)!r}."
        )

    return namespace._impls[context]


def import_package(
    name: str,
    module: str | None = None,
    *,
    force_resolution: bool = False,
    raise_warnings: bool = True,
) -> 'Package':
    """Import the package from the specified module name.

    When the module name is not recognized as a valid package module name, it
    raises an error if the resolution is not forced. Otherwise, it tries to
    resolve the specified module name to a valid one (i.e. a parent module that
    defines a project configuration file).

    Args:
        name: The exact name of the package module to be resolved.
        module: The module to use as the anchor point for relative imports.
        force_resolution: When set to ``True``, forces the resolution of an
            unrecognized module name to a valid package module name. If
            ``False``, the function raises an error for invalid names.
            Defaults to ``False``.
        raise_warnings: Whether to log warnings when invalid package
            configurations are encountered. Defaults to ``True``.

    Returns:
        The package instance associated with the specified module name.
    """
    from .modules import (
        get_root_module_name,
        import_module,
        is_package,
        resolve_file_paths,
    )
    from .packages import Package
    from .projects import import_project_info

    # Helper function to collect projects information
    def collect_info(
        mod: ModuleType, only_package: bool = False
    ) -> list['ProjectInfo']:
        projects: list['ProjectInfo'] = []
        for path in resolve_file_paths(mod):
            try:
                project = import_project_info(
                    path, force_resolution='.' not in mod.__name__,
                )
                if (
                    not only_package
                    or path.endswith('config.toml')
                    or bool(project.package)
                ):
                    projects.append(project)
            except (
                FileExistsError,
                ImportError,
                NotImplementedError,
            ) as error:
                raise error
            except FileNotFoundError:
                pass
        return projects

    # Validate module name
    if module:
        module = module.rpartition('.')[0]
        if not module:
            name = name.lstrip('.')

    # Import package module
    package_module = import_module(
        name, package=module, force_resolution=force_resolution,
    )

    # Update name for proxy modules
    name = getattr(package_module, '__name__', name)

    # Handle invalid package module
    if not is_package(package_module, allow_root=True):
        # Recursively resolve parent package if forced
        if not force_resolution:
            raise ImportError(
                f"Invalid package module name {name!r}. The module is not a "
                f"valid package.",
            )
        return import_package(
            name.rpartition('.')[0],
            force_resolution=force_resolution,
            raise_warnings=raise_warnings,
        )

    with __plateforme__.lock('packages', reentrant=True):
        # Check if package is already imported
        package_name = getattr(package_module, '__package__', None)
        package_name = package_name or get_root_module_name()
        if package_name in __plateforme__.packages:
            return __plateforme__.packages[package_name]

        # Collect and validate project information
        projects = collect_info(package_module)

        if len(projects) > 1:
            raise ImportError(
                f"Multiple package configurations found for package module "
                f"{name!r}. Make sure the module defines only one "
                f"configuration, either a `config.toml` or `pyproject.toml` "
                f"file.",
            )
        elif len(projects) == 1:
            project = projects[0]
        else:
            parent_name = name.rpartition('.')[0]
            if parent_name:
                if force_resolution:
                    # Recursively resolve parent module
                    return import_package(
                        parent_name,
                        force_resolution=force_resolution,
                        raise_warnings=raise_warnings,
                    )
                raise ImportError(
                    f"Could not find configuration for package module "
                    f"{name!r}. Make sure the module defines either a "
                    f"`config.toml` or `pyproject.toml` file when it's not a "
                    f"top-level module.",
                )
            project = None

        # Warn if package configurations are defined in parent module
        if raise_warnings:
            parts = name.split('.')
            for i in range(len(parts) - 1, 0, -1):
                parent_name = '.'.join(parts[:i])
                try:
                    warns = False
                    parent_module = import_module(parent_name)
                    parent_projects = \
                        collect_info(parent_module, only_package=True)
                except Exception:
                    warns = True
                if warns or parent_projects:
                    warnings.warn(
                        f"One or more package configurations are defined in "
                        f"parent module {parent_name!r} of package module "
                        f"{name!r}.",
                        UserWarning,
                    )

        # Parse project information
        if project is None:
            package = Package(package_name, package_module)
        else:
            package = Package(
                package_name,
                package_module,
                info=project.model_dump(
                    include={
                        'name',
                        'version',
                        'authors',
                        'description',
                        'keywords',
                        'license',
                        'maintainers',
                        'readme',
                    }
                ),
                settings=project.package,
            )

        # Create package instance
        __plateforme__.packages[package_name] = package

    return package


def import_package_impl(
    name: str,
    context: 'Plateforme | None' = None,
) -> 'PackageImpl':
    """Import a package module name implementation.

    Args:
        name: The exact name of the package module to be resolved.
        context: The application context to use for the package implementation.
            Defaults to ``None``.

    Returns:
        The package implementation associated with the specified module name
        and application context.
    """
    package = import_package(name)

    if context not in package._impls:
        raise ImportError(
            f"Package {package.name!r} does not have an implementation "
            f"for the context {str(context)!r}."
        )

    return package._impls[context]


# MARK: Utilities

def clear_cache() -> None:
    """Clear the runtime cache for debugging and testing purposes."""
    # Clear packages
    for package in __plateforme__.packages.values():
        package._clear_cache()
    __plateforme__.packages.clear()

    # Clear namespaces
    for namespace in __plateforme__.namespaces.values():
        namespace._clear_cache()
    __plateforme__.namespaces.clear()


def info() -> str:
    """Prints detailed information about the runtime environment."""
    from .. import framework

    def build_info(key: str, registry: dict[Any, Any]) -> tuple[str, str]:
        return (
            f'{key}[{len(registry)}]:',
            ' '.join(repr(name) for name in registry.keys())
        )

    info = [
        build_info('namespaces', __plateforme__.namespaces),
        build_info('packages', __plateforme__.packages),
        build_info('resources', __plateforme__.resources),
    ]

    return (
        framework.version_info()
        + '\n\n'
        + '\n'.join(
            '{:>30} {}'.format(key, str(value).replace('\n', ' '))
            for key, value in info
        )
    )
