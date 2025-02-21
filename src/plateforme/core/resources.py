# plateforme.core.resources
# -------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing resources within the Plateforme
framework's. It integrates with other core components of the framework, such as
model validation and serialization, database interaction, and API routing.

The `BaseResource` class is the foundational base for all resources within the
framework. It provides a common interface for defining resources and managing
their lifecycle. Resources are used to represent entities within the system,
such as users, products, or orders. They are used to define the structure of
the data, the business logic, and the API endpoints.

Note:
    See also the `Field` function for more information on modeling features.
"""

import dataclasses
import inspect
import typing
import uuid
from abc import ABCMeta
from collections import deque
from collections.abc import (
    Generator,
    ItemsView,
    Iterable,
    Iterator,
    KeysView,
    Mapping,
    Sequence,
    ValuesView,
)
from copy import deepcopy
from enum import Enum
from functools import wraps
from inspect import Parameter, Signature
from types import EllipsisType
from typing import (
    Annotated,
    Any,
    Callable,
    ClassVar,
    Coroutine,
    ForwardRef,
    Generic,
    Literal,
    Required,
    Self,
    Type,
    TypeVar,
    Union,
    Unpack,
)

from typing_extensions import TypedDict

from . import runtime
from .api.parameters import Path, PayloadInfo, SelectionInfo
from .api.requests import Request
from .api.responses import JSONResponse, Response
from .api.routing import (
    APIEndpoint,
    APIRouteConfig,
    APIRouter,
    APIRouterConfigDict,
)
from .api.status import status
from .api.utils import generate_unique_id, sort_key_for_routes
from .config import Configurable, ConfigurableMeta, evaluate_config_field
from .context import CALLER_CONTEXT, SESSION_BULK_CONTEXT, VALIDATION_CONTEXT
from .database.base import MissingGreenlet
from .database.expressions import select
from .database.orm import (
    ClassManager,
    DeclarativeMeta,
    InstanceState,
    InstrumentedAttribute,
    ORMOption,
    Registry,
    is_instrumented,
    set_instrumented_value,
)
from .database.schema import NAMING_CONVENTION, Column, ForeignKey, Index
from .database.sessions import AsyncSession, async_session_manager
from .database.types import IntegerEngine, StringEngine, UuidEngine
from .errors import PlateformeError
from .expressions import IncEx
from .functions import make_async, make_kw_only
from .logging import logger
from .managers import Manager
from .patterns import match_any_pattern, to_name_case, to_path_case
from .proxy import Proxy
from .representations import ReprArgs, Representation
from .runtime import (
    Action,
    Lifecycle,
    ResolvedState,
    SchedulableState,
    Task,
)
from .schema import core as core_schema
from .schema.aliases import AliasChoices
from .schema.core import (
    CoreSchema,
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
    ValidationMode,
    recursion_manager,
    validation_manager,
)
from .schema.decorators import RecursiveGuard
from .schema.fields import (
    ComputedFieldInfo,
    ConfigField,
    Field,
    FieldDefinition,
    FieldInfo,
    FieldLookup,
    PrivateAttr,
)
from .schema.json import (
    DEFAULT_REF_TEMPLATE,
    GenerateJsonSchema,
    JsonSchemaDict,
    JsonSchemaMode,
    JsonSchemaSource,
)
from .schema.models import (
    BaseModel,
    BaseModelConfigDict,
    DiscriminatedModel,
    DiscriminatedModelType,
    ModelConfig,
    ModelFieldInfo,
    ModelMeta,
    ModelType,
    NoInitField,
    RootModel,
    collect_fields,
    collect_models,
    create_discriminated_model,
    create_model,
)
from .schema.types import TypeAdapterList
from .selectors import BaseSelector, Key, KeyList
from .services import (
    BaseService,
    BaseServiceConfigDict,
    CRUDService,
    ServiceType,
    bind_service,
    copy_service,
    load_service,
    unbind_service,
)
from .specs import (
    BaseSpec,
    CRUDSpec,
    SpecType,
    apply_spec,
    resolve_schema_model,
)
from .types.uuid import UUID4
from .typing import (
    Annotation,
    ClassMethodType,
    Deferred,
    FunctionLenientType,
    Undefined,
    WithFunctionTypes,
    classproperty,
    eval_type_lenient,
    get_object_name,
    getmembers_static,
    is_abstract,
    is_endpoint,
    is_model,
    is_resource,
    isbaseclass_lenient,
    isfunction_lenient,
    issubclass_lenient,
)
from .utils import check_config, get_subclasses

if typing.TYPE_CHECKING:
    from .packages import Package

MANAGED_ATTRS = (r'id', r'key', r'type', r'type_')
FORBIDDEN_ATTRS = (
    r'Config',
    r'Model',
    r'objects',
    r'model_.*',
    r'service_.*',
    r'_add_services',
    r'_get_service',
    r'_remove_services',
    r'_add_specs',
    r'_remove_specs',
    r'_collect_fields',
    r'_create_path',
    r'_create_router',
    r'_rebuild_adapter',
    r'_rebuild_schemas',
    r'_register_schema',
)
PROTECTED_ATTRS = (r'__config__', r'resource_.*')

ALL_ATTRS = (*MANAGED_ATTRS, *FORBIDDEN_ATTRS, *PROTECTED_ATTRS)

__all__ = (
    'BaseResource',
    'CRUDResource',
    'Resource',
    'ResourceConfig',
    'ResourceConfigDict',
    'ResourceDict',
    'ResourceFieldInfo',
    'ResourceIndex',
    'ResourceManager',
    'ResourceMeta',
    'ResourceNode',
    'ResourcePath',
    'ResourcePathInfo',
    'ResourceProxy',
    'ResourceState',
    'ResourceType',
)


Resource = TypeVar('Resource', bound='BaseResource')
"""A type variable for a resource class."""


ResourceType = Type['BaseResource']
"""A type alias for a resource class."""


ResourceFieldInfo = FieldInfo['BaseResource']
"""A type alias for a resource field information."""


class ResourceIndex(TypedDict, total=False):
    """A configuration dictionary for defining indexes on resource fields."""

    name: str
    """The name of the index. It can be used to customize the generated index
    name using the index registy naming convention. Defaults to the snake-cased
    concatenation of the resource alias and specified field aliases."""

    aliases: Required[set[str]]
    """The required resource field aliases to include in the index. The field
    aliases must be defined in the underlying resource model."""

    unique: bool
    """Whether the index is unique. Defaults to ``True``."""


# MARK: Resource Configuration

class ResourceConfigDict(BaseModelConfigDict, total=False):
    """A resource class configuration dictionary."""

    tags: list[str | Enum] | None
    """A list of tags to associate with the resource. Tags are used to group
    resources and provide additional metadata. It will be added to the
    generated OpenAPI, visible at `/docs`. If not provided, the resource slug
    will be used as the default tag. Defaults to ``None``."""

    api_max_depth: int
    """The maximum depth to walk through the resource path to collect manager
    methods from resource dependencies. It is used to generate API routes.
    Defaults to ``2``."""

    api_max_selection: int
    """The limit of resources to return for the API route selections. It is
    used when generating the API routes for resources within the application
    to avoid too many resources being returned. Defaults to ``20``.
    """

    id_strategy: Literal['auto', 'manual', 'hybrid']
    """The identifier strategy to use for the resource. It defines how the
    identifier is generated for the resource and can be set to one of the
    following values:
    - ``auto``: Enforce automatic generation of the resource identifier.
    - ``manual``: Enforce manual specification of the resource identifier.
    - ``hybrid``: Allow both automatic and manual generation of the resource
        identifier.
    Defaults to ``auto``.
    """

    id_type: Literal['integer', 'uuid']
    """The identifier type to use for the resource. It defines the data type of
    the resource identifier and can be set to one of the following values:
    - ``integer``: Use an integer data type engine for the resource identifier.
    - ``uuid``: Use a UUID data type engine for the resource identifier.
    Defaults to ``integer``.
    """

    mapper_args: dict[str, Any]
    """A dictionary of additional arguments to pass to the resource declarative
    mapper during the resource configuration, i.e. the dictionary of arguments
    to add to the ``__mapper_args__`` attribute of the resource class.
    Defaults to an empty dictionary."""

    use_single_table_inheritance: bool
    """It defines the inheritance design pattern to use for database ORM.
    Defaults to ``False``, using joined table inheritance with separate tables
    for parent and child classes linked by a foreign key. This approach is
    generally preferred for its normalization benefits. Setting this to
    ``True`` enables single table inheritance, creating a single table for both
    parent and child classes with a discriminator column.

    Note:
        Single table inheritance can lead to sparse tables and may impact
        performance for large and complex hierarchies.
    """

    indexes: Sequence[ResourceIndex | set[str]]
    """A sequence or list of resource indexes configurations that define
    indexing for resource model fields. An index is defined either as a set of
    field aliases or as a dictionary with the following keys:
    - ``aliases``: A tuple of strings representing the resource field aliases
        to include in the index.
    - ``unique``: Whether the index is unique. Defaults to ``True``.
    Defaults to an empty sequence."""

    endpoints: BaseServiceConfigDict | None
    """A base configuration for the resource service endpoints that allows to
    select specific endpoint methods to include or exclude from the services,
    and configure their default behavior. Defaults to ``None``."""

    services: Sequence[BaseService | EllipsisType | ServiceType]
    """A sequence of services to bind to the resource. The services are used to
    define the business logic and data access methods for the resource. The
    services can be defined as instances of ``BaseService`` or as service
    types. The ellipsis ``...`` can be used to insert all services from the
    parent resource. Defaults to an empty sequence."""

    specs: Sequence[SpecType]
    """A sequence of specifications to apply to the resource. The
    specifications are used to define additional resource configurations,
    schemas, and behaviors. All the specifications from the parent resource are
    merged with the provided configuration, .i.e. a child resource must inherit
    all the specifications from the parent resource.
    Defaults to an empty sequence."""

    deprecated: bool | None
    """A flag indicating whether the resource is deprecated.
    Defaults to ``None``."""


class ResourceConfig(ModelConfig):
    """A resource class configuration."""
    if typing.TYPE_CHECKING:
        __config_owner__: ResourceType = \
            ConfigField(frozen=True, init=False)  # type: ignore[assignment]

    type_: str = ConfigField(default='resource', frozen=True, init=False)
    """The configuration owner type set to ``resource``. It is a protected
    field that is typically used with `check_config` to validate an object type
    without using `isinstance` in order to avoid circular imports."""

    extra: Annotated[
        Literal['allow', 'ignore', 'forbid'], 'pydantic'
    ] = ConfigField(default='forbid', frozen=True, init=False)
    """Extra values are not allowed within a resource instance. This attribute
    is protected and will initialize to its default value ``forbid``."""

    defer_build: Annotated[bool, 'pydantic'] = \
        ConfigField(default=True, frozen=True, init=False)
    """Defer building is not allowed for resource instances. This attribute is
    protected and will initialize to its default value ``True``."""

    tags: list[str | Enum] | None = None
    """A list of tags to associate with the resource. Tags are used to group
    resources and provide additional metadata. It will be added to the
    generated OpenAPI, visible at `/docs`. If not provided, the resource slug
    will be used as the default tag. Defaults to ``None``."""

    api_max_depth: int = 2
    """The maximum depth to walk through the resource path to collect manager
    methods from resource dependencies. It is used to generate API routes.
    Defaults to ``2``."""

    api_max_selection: int = 20
    """The limit of resources to return for the API route selections. It is
    used when generating the API routes for resources within the application
    to avoid too many resources being returned. Defaults to ``20``.
    """

    id_strategy: Literal['auto', 'manual', 'hybrid'] = 'auto'
    """The identifier strategy to use for the resource. It defines how the
    identifier is generated for the resource and can be set to one of the
    following values:
    - ``auto``: Enforce automatic generation of the resource identifier.
    - ``manual``: Enforce manual specification of the resource identifier.
    - ``hybrid``: Allow both automatic and manual generation of the resource
        identifier.
    Defaults to ``auto``.
    """

    id_type: Literal['integer', 'uuid'] = 'integer'
    """The identifier type to use for the resource. It defines the data type of
    the resource identifier and can be set to one of the following values:
    - ``integer``: Use an integer data type engine for the resource identifier.
    - ``uuid``: Use a UUID data type engine for the resource identifier.
    Defaults to ``integer``.
    """

    mapper_args: dict[str, Any] = {}
    """A dictionary of additional arguments to pass to the resource declarative
    mapper during the resource configuration, i.e. the dictionary of arguments
    to add to the ``__mapper_args__`` attribute of the resource class.
    Defaults to an empty dictionary."""

    use_single_table_inheritance: bool = False
    """It defines the inheritance design pattern to use for database ORM.
    Defaults to ``False``, using joined table inheritance with separate tables
    for parent and child classes linked by a foreign key. This approach is
    generally preferred for its normalization benefits. Setting this to
    ``True`` enables single table inheritance, creating a single table for both
    parent and child classes with a discriminator column.

    Note:
        Single table inheritance can lead to sparse tables and may impact
        performance for large and complex hierarchies.
    """

    indexes: tuple[ResourceIndex, ...] = ()
    """A tuple of resource indexes configurations that define indexing for
    resource model fields. An index is defined as a dictionary with the
    following keys:
    - ``aliases``: A tuple of strings representing the resource field aliases
        to include in the index.
    - ``unique``: Whether the index is unique. Defaults to ``True``.
    Defaults to an empty tuple.
    """

    endpoints: BaseServiceConfigDict | None = None
    """A base configuration for the resource service endpoints that allows to
    select specific endpoint methods to include or exclude from the services,
    and configure their default behavior. Defaults to ``None``."""

    services: tuple[BaseService | EllipsisType | ServiceType, ...] = ()
    """A tuple of services to bind to the resource. The services are used to
    define the business logic and data access methods for the resource. The
    services can be defined as instances of ``BaseService`` or as service
    types. The ellipsis ``...`` can be used to insert all services from the
    parent resource. Defaults to an empty tuple."""

    specs: tuple[SpecType, ...] = ()
    """A tuple of specifications to apply to the resource. The specifications
    are used to define additional resource configurations, schemas, and
    behaviors. All the specifications from the parent resource are merged with
    the provided configuration, .i.e. a child resource must inherit all the
    specifications from the parent resource. Defaults to an empty tuple."""

    deprecated: bool | None = None
    """A flag indicating whether the resource is deprecated.
    Defaults to ``None``."""

    @property
    def id_autoincrement(self) -> bool | Literal['auto']:
        """Whether the resource identifier is autoincremented."""
        if self.id_type != 'integer':
            return False
        if self.id_strategy == 'manual':
            return False
        if self.id_strategy == 'auto':
            return True
        return 'auto'

    @property
    def id_engine(self) -> type[IntegerEngine | UuidEngine[UUID4]]:
        """The identifier engine to use for the resource."""
        if self.id_type == 'uuid':
            return UuidEngine[UUID4]
        return IntegerEngine

    def post_init(self) -> None:
        """Post-initialization steps for the resource configuration."""
        # Skip post-initialization if the configuration owner is not set
        resource = self.__config_owner__
        if resource is None:
            return

        # Model post-initialization
        super().post_init()

        # Resource post-initialization
        fields = resource.resource_fields
        aliases = [field.alias for field in fields.values()]
        indexes: list[ResourceIndex] = []

        # Collect configuration indexes
        for index in self.indexes:
            # Validate index type
            if isinstance(index, (list, set)):
                index = {'aliases': set(index)}
            elif not isinstance(index, dict):
                raise PlateformeError(
                    f"The resource {resource.__qualname__!r} has an invalid "
                    f"index configuration for entry {index!r}. An index must "
                    f"be a dictionary.",
                    code='resource-invalid-config',
                )

            # Validate index field aliases length
            if len(index['aliases']) < 2:
                raise PlateformeError(
                    f"The resource {resource.__qualname__!r} has an invalid "
                    f"index configuration for entry {index!r}. Composite "
                    f"indexes defined in the resource configuration must have "
                    f"at least two field aliases. Use ``indexed=True`` or "
                    f"``unique=True`` for single field indexes.",
                    code='resource-invalid-config',
                )

            # Validate index field aliases existence
            for alias in index['aliases']:
                if alias == 'id':
                    raise PlateformeError(
                        f"The resource {resource.__qualname__!r} has an "
                        f"invalid index configuration for entry {index!r}. "
                        f"The field alias {alias!r} is reserved and cannot be "
                        f"used in indexes.",
                        code='resource-invalid-config',
                    )
                if alias not in aliases:
                    raise PlateformeError(
                        f"The resource {resource.__qualname__!r} has an "
                        f"invalid index configuration for entry {index!r}. "
                        f"The field alias {alias!r} is not defined in the "
                        f"resource model.",
                        code='resource-invalid-config',
                    )

            # Set alias default name and unique flag
            default_name = self.alias + '_' + '_'.join(index['aliases'])
            index.setdefault('name', default_name)
            index.setdefault('unique', True)

            indexes.append(index)

        # Check for duplicate indexes
        indexes_check = set()
        for index in indexes:
            index_check = frozenset(index['aliases'])
            if index_check in indexes_check:
                raise PlateformeError(
                    f"The resource {self.__config_owner__.__qualname__!r} has "
                    f"a duplicate index configuration for {index_check!r}.",
                    code='resource-invalid-config',
                )
            indexes_check.add(index_check)

        # Update indexes
        if indexes:
            self.indexes = tuple(indexes)


# MARK: Resource Dictionary

class ResourceDict(dict[str, Any]):
    """A custom dictionary class for the resource instance."""

    def __init__(self, __model: BaseModel, *args: Any, **kwargs: Any) -> None:
        """Initialize a new resource dictionary with the provided model."""
        super().__init__(*args, **kwargs)
        self.model = __model

    def clear(self) -> None:
        """Clear the inner dictionary and reset all values."""
        self.model.__dict__.clear()
        super().clear()

    def copy(self) -> Self:
        """Return a shallow copy of the inner dictionary."""
        return self.__class__(self.model, super().copy())

    def keys(self) -> KeysView[str]:  # type: ignore[override]
        """Return the inner dictionary keys."""
        return KeysView(self.__dict__)

    def values(self) -> ValuesView[Any]:  # type: ignore[override]
        """Return the inner dictionary values."""
        return ValuesView(self.__dict__)

    def items(self) -> ItemsView[str, Any]:  # type: ignore[override]
        """Return the inner dictionary items."""
        return ItemsView(self.__dict__)

    @typing.overload
    def get(self, key: str) -> Any: ...

    @typing.overload
    def get(self, key: str, default: Any) -> Any: ...

    def get(self, key: str, default: Any = Undefined) -> Any:
        """Get the value for the specified key."""
        if default is Undefined:
            return self.__dict__.get(key)
        return self.__dict__.get(key, default)

    @typing.overload
    def pop(self, key: str) -> Any: ...

    @typing.overload
    def pop(self, key: str, default: Any) -> Any: ...

    def pop(self, key: str, default: Any = Undefined) -> Any:
        """Pop the specified key from the inner dictionary."""
        # Check if key is in the model instance dictionary
        if key in self.model.__dict__:
            if default is Undefined:
                return self.model.__dict__.pop(key)
            return self.model.__dict__.pop(key, default)
        # Fallback to the resource dictionary
        if default is Undefined:
            return super().pop(key)
        return super().pop(key, default)

    def setdefault(  # type: ignore[override]
        self, key: str, default: Any
    ) -> Any:
        """Set the default value for the specified key if not set."""
        if key not in self:
            self[key] = default
            return default
        return self[key]

    def update(  # type: ignore[override]
        self,
        *args: tuple[str, Any] | Mapping[str, Any],
        **kwargs: Any,
    ) -> None:
        """Update the config dictionary with new data."""
        # Update args data
        for arg in args:
            if isinstance(arg, tuple):
                self[arg[0]] = arg[1]
            else:
                for key, value in arg.items():
                    self[key] = value
        # Update kwargs data
        for key, value in kwargs.items():
            self[key] = value

    @property
    def __dict__(self) -> dict[str, Any]:
        # Return the combined resource and model dictionary
        return dict(super().items()) | self.model.__dict__

    @__dict__.setter
    def __dict__(self, value: dict[str, Any]) -> None:
        raise AttributeError(
            f"Cannot set the `__dict__` attribute on the resource "
            f"instance {self.__class__.__qualname__!r}."
        )

    @__dict__.deleter
    def __dict__(self) -> None:
        raise AttributeError(
            f"Cannot delete the `__dict__` attribute on the resource "
            f"instance {self.__class__.__qualname__!r}."
        )

    def __contains__(self, key: object) -> bool:
        return key in self.__dict__

    def __iter__(self) -> Iterator[str]:
        yield from self.__dict__

    def __reversed__(self) -> Iterator[str]:
        yield from reversed(self.__dict__)

    def __len__(self) -> int:
        return len(self.__dict__)

    def __getitem__(self, key: str) -> Any:
        if hasattr(self.model, key):
            return getattr(self.model, key)
        return super().__getitem__(key)

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self.model.model_fields:
            self.model.__dict__[key] = value
            return
        super().__setitem__(key, value)

    def __delitem__(self, key: str) -> None:
        if key in self.model.model_fields:
            self.model.__dict__.pop(key)
            return
        super().__delitem__(key)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        if isinstance(other, dict):
            return self.__dict__ == other
        return False

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __or__(  # type: ignore[override]
        self, other: Self | dict[str, Any]
    ) -> Self:
        target = self.copy()
        target.update(other)
        return target

    def __ior__(  # type: ignore[override]
        self, other: Self | dict[str, Any]
    ) -> Self:
        self.update(other)
        return self

    def __ror__(  # type: ignore[override]
        self, other: Self | dict[str, Any]
    ) -> Self:
        target = self.copy()
        for key, value in other.items():
            target.setdefault(key, value)
        return target

    def __repr__(self) -> str:
        return repr(self.__dict__)

    def __str__(self) -> str:
        return str(self.__dict__)


# MARK: Resource Node

class ResourceNode(Generic[Resource]):
    """A resource node within the resources graph.

    The resource node represents a ``segment`` within the resources graph. It
    is associated with a specific resource and a linked field accessor. The
    node is used to build resource paths and navigate the resources graph.

    Attributes:
        resource: The resource associated with the node.
        accessor: The linked field accessor associated with the node.

    Note:
        The identifiers generated from the unique indexes of the resource are
        used to identify a specific resource instance within this node. Thus,
        it can be used within a resource path to navigate the resources graph.
    """

    def __init__(
        self,
        resource: type[Resource],
        accessor: ResourceFieldInfo | None = None,
    ) -> None:
        """Initialize a new resource node.

        It initializes a new resource node with the provided resource and
        linked field accessor. It serves as a building block for constructing
        resource paths and navigating the resources graph.

        Args:
            resource: The resource associated with the node.
            accessor: The linked field accessor associated with the node.
        """
        # Initialize with default identifier
        self.resource = resource
        self.accessor = accessor

    @property
    def backref(self) -> ResourceFieldInfo | None:
        """The accessor association backref of the resource node."""
        if self.accessor and self.accessor.rel_backref:
            field = self.accessor.rel_backref
            return field
        return None

    @property
    def config(self) -> ResourceConfig:
        """The config of the node resource."""
        return self.resource.resource_config

    @property
    def segment(self) -> str | None:
        """The accessor segment alias of the resource node."""
        if self.accessor:
            return self.accessor.alias
        return None

    def __eq__(self, value: object) -> bool:
        return (
            self.resource is getattr(value, 'resource', None) and
            self.accessor is getattr(value, 'accessor', None)
        )

    def __ne__(self, value: object) -> bool:
        return not self.__eq__(value)

    def __hash__(self) -> int:
        return hash((self.resource, self.accessor))

    def __deepcopy__(self, memo: dict[int, Any]) -> Self:
        return self.__class__(self.resource, self.accessor)

    def __repr__(self) -> str:
        return f'ResourceNode({self})'

    def __str__(self) -> str:
        owner_alias = self.accessor.owner.resource_config.alias \
            if self.accessor else None
        target_alias = self.resource.resource_config.alias
        if not self.segment:
            return target_alias
        return f'{owner_alias}.{self.segment} -> {target_alias}'


# MARK: Resource Path

@dataclasses.dataclass(frozen=True, kw_only=True)
class ResourcePathInfo:
    """A resource path information class.

    It provides information about the resource path, including the path string,
    and the parameters required to resolve the resource path, and the resolver
    function used to fetch and validate a single resource instance or a
    collection of resource instances.
    """
    path: str
    """The path string for the resource path."""

    parameters: dict[str, Parameter]
    """A dictionary of parameters required to resolve the resource path."""


class ResourcePath(Iterable[ResourceNode['BaseResource']]):
    """A resource path within the resources graph.

    The resource path represents a sequence of linked fields within the
    resources graph. It is used to navigate the resources graph and build API
    paths to interact with the resources.

    Attributes:
        nodes: A list of `ResourceNode` objects, each item representing a
            resource node within the resources graph.
    """

    def __init__(self, root: ResourceType, *path: str) -> None:
        """Initialize a new resource path.

        It initializes a new resource path with the provided root resource and
        path segments. The path segments represent a sequence of linked fields
        within the resources graph, and together with the root resource they
        define a resource path.

        Args:
            root: The root resource of the API path serving as the starting
                point in the resources graph.
            *path: Variable length argument list representing the path segments
                of the resource path. Each segment corresponds to a linked
                field alias within the resources graph.
        """
        # Initialize with the root resource
        self.nodes = [ResourceNode(root)]

        # Navigate to the provided path
        self.goto(*path, in_place=True)

    @property
    def is_root(self) -> bool:
        """Whether the resource path is at the root level."""
        return len(self.nodes) == 1

    @property
    def root(self) -> ResourceType:
        """The root resource of the resource path."""
        return self.nodes[0].resource

    @property
    def target(self) -> ResourceType:
        """The target resource of the resource path."""
        return self.nodes[-1].resource

    def goto(
        self,
        *path: str,
        in_place: bool = True,
    ) -> Self:
        """Navigate to the provided path segments.

        It navigates to the provided path segments within the resources graph.
        Each segment is checked to match a linked field alias within the
        resource hierarchy. If any segment fails to match a field alias in the
        resource hierarchy, an error is raised.

        Args:
            *path: Variable length argument list representing the path segments
                to navigate within the resources graph. Each segment
                corresponds to a linked field alias within the resources graph.
            in_place: A flag indicating whether to navigate in place or create
                a new resource path. Defaults to ``True``. If set to ``False``,
                a new resource path is created and returned, not modifying the
                current resource path.

        Raises:
            ValueError: If any of the provided segments do not correspond to a
                linked field alias in the resource hierarchy.

        Note:
            A provided path arg can be a dot-separated string representing
            multiple segments. For example, the path arg `foo.bar` is split
            into two segments `foo` and `bar`.
        """
        # Collect all segments from the path arguments
        segments = [
            segment
            for arg in path
            for segment in arg.split('.') if segment
        ]

        # Initialize the resource path object
        obj = self
        if not in_place:
            obj = deepcopy(self)

        # Retrieve the linked field for each provided segment alias. It looks
        # for field aliases within the resource hierarchy and checks whether
        # linked fields are valid.
        resource = obj.target
        for segment in segments:
            # Look for a linked field matching the segment alias
            accessor: ResourceFieldInfo | None = None
            for field in resource.resource_fields.values():
                # Skip non-matching field aliases
                if segment != field.alias:
                    continue
                # Check if field is a linked field
                if not field.linked:
                    raise ValueError(
                        f"Segment {segment!r} in the resource path does not "
                        f"correspond to a linked field alias. Got: "
                        f"{field!r}."
                    )
                # Check if field target is a valid resource type
                if not field.target or isinstance(field.target, str):
                    raise ValueError(
                        f"Segment {segment!r} in the resource path does not "
                        f"have a valid target resource type. Got: "
                        f"{field.target!r}."
                    )
                # Update resource and accessor
                resource = field.target
                accessor = field
                break

            # Raise an error if no matching field is found
            if accessor is None:
                raise ValueError(
                    f"Segment {segment!r} in the resource path does not match "
                    f"any field alias within the resource "
                    f"{resource.__class__.__qualname__!r}."
                )

            # Initialize the resource node and check for duplicates
            node = ResourceNode(resource, accessor)
            if any(node == other_node for other_node in self.nodes):
                raise ValueError(
                    f"Segment {segment!r} in the resource path is a duplicate "
                    f"and has already been used in the resource "
                    f"{resource.__class__.__qualname__!r}."
                )

            # Append the resource node to the resource path
            obj.nodes.append(node)

        return obj

    def walk(
        self,
        _guard: frozenset[str] = frozenset(),
        /,
        max_depth: int = 2,
        skip_root: bool = False,
    ) -> Generator[Self, None, None]:
        """Walk the resource graph and yield all possible sub-paths.

        It recursively walks the resource graph and yields all possible
        sub-paths up to the specified maximum depth. The maximum depth is used
        to limit the recursion depth and avoid infinite loops when walking the
        resource graph. Already walked paths are skipped to avoid duplicates.

        Args:
            _guard: A set of already walked resource association alias. It
                should not be used directly and is only meant to be used
                internally for recursion.
            max_depth: The maximum depth to walk the resource graph. It limits
                the recursion depth and avoids infinite loops.
                Defaults to ``1``.
            skip_root: A flag indicating whether to skip the root resource
                path. Defaults to ``False``.

        Yields:
            All possible sub-paths up to the specified maximum depth.
        """
        # Yield the root resource path if not skipped
        if len(_guard) == 0:
            if not skip_root:
                yield self

        # Stop the recursion if the maximum depth is reached
        if len(_guard) >= max_depth - 1:
            return

        # Otherwise, walk the resource graph
        for field in self.target.resource_fields.values():
            # Skip already walked paths
            if field.recursive_guard is None \
                    or field.recursive_guard in _guard:
                continue
            # Skip non-linked fields
            if not field.linked:
                continue
            # Skip non-backref fields
            if field.rel_backref is None:
                continue
            # Skip lazy loaded fields
            if field.is_eagerly() is not True:
                continue
            # Get the resource path object
            obj = self.goto(
                field.alias,
                in_place=False,
            )
            # Yield the resource path and walk its sub-paths
            yield obj
            yield from obj.walk(
                _guard | {field.recursive_guard},
                max_depth=max_depth,
            )

    def _create_path_info(
        self, *, skip_last_node: bool = False
    ) -> ResourcePathInfo:
        """Create a path information object for the resource path.

        It is used internally to generate the path string and collect all
        parameters within the resource path to serve the resolver function. The
        parameters are then used to resolve to a single resource instance or a
        collection of resource instances.

        Args:
            skip_last_node: Whether to skip the target last node when creating
                the path information. Defaults to ``False``.

        Returns:
            A resource path information object containing the path string and
            the parameters required to resolve the resource path.
        """
        # Collect keys from each node alias, suffixed with "_key", and prefixed
        # with "_" to indicate that they are dynamically generated and avoid
        # conflicts with user-defined parameters (e.g. "_foo_key").
        keys = ['_%s_key' % node.config.alias for node in self.nodes]

        path = ''
        parameters: dict[str, Parameter] = {}

        for count, (node, key) in enumerate(zip(self.nodes, keys)):
            # Add the node slug to the path if it has an accessor
            if count > 0:
                assert node.accessor is not None
                path += f'/{node.accessor.slug}'

            # Skip last node if specified
            if skip_last_node and count == len(self.nodes) - 1:
                break

            # Skip parameter definition if the node is not associated with a
            # collection accessor (e.g. an "unknown-to-one" relationship).
            if node.accessor and node.accessor.collection is None:
                continue

            # For segments with same alias, add an index to the parameter key
            # to avoid duplicates (e.g. "_foo1_key", "_foo2_key").
            if keys.count(key) > 1:
                key = key[:-4] + str(keys[:count].count(key)) + key[-4:]

            # Add parameter definition
            path += f'/{{{key}}}'
            parameters[key] = Parameter(
                name=key,
                kind=Parameter.POSITIONAL_ONLY,
                annotation=Annotated[str, Path(
                    json_schema_extra={'auto_generated': True},
                )],
            )

        return ResourcePathInfo(path=path, parameters=parameters)

    def _create_resolver(
        self,
        __session: AsyncSession | None = None,
        *,
        handler: type[Any] | None = None,
        metadata: tuple[Any, ...] | None = None,
        max_selection: int | None = None,
    ) -> tuple[
        ResourcePathInfo,
        Callable[..., Coroutine[Any, Any, Any]],
    ]:
        """Create a resolver function for the resource path.

        It creates a resolver function that is used to fetch and validate a
        single resource instance or a collection of resource instances.

        Args:
            __session: The async session to use for the resolution. If not
                provided, the session in the current context is used.
                Defaults to ``None``.
            handler: The handler type for the resolution. If not provided, the
                resolver will return the matching target resource instances.
                It can be set to a selector type such as `Key` or `KeyList`, or
                an iterable container type to resolve to a collection of
                resource instances. Defaults to ``None``.
            metadata: Additional metadata to pass to the resolver function. It
                is used with the `Annotated` type to pass additional metadata
                to the resolver function. Defaults to ``None``.
            max_selection: The maximum number of resources to return for the
                selection. Defaults to ``None``.

        Returns:
            A tuple containing the resource path information object with the
            path string and parameters required to resolve the resource path,
            and the resolver function itself that is used to resolve to a
            single resource instance or a collection of resource  instances
            based on the provided parameters.
        """
        # Validate handler
        if handler is None:
            return_handler = False
            skip_last_node = False
        elif issubclass_lenient(handler, BaseSelector):
            return_handler = True
            if check_config(handler, collection=True):
                skip_last_node = True
            else:
                skip_last_node = False
        elif issubclass_lenient(handler, Iterable):
            return_handler = False
            skip_last_node = True
        else:
            raise TypeError(
                f"Invalid handler type for the resource path {self!r}. The "
                f"handler when provided must be a selector class such as "
                f"`Key` or `KeyList`, or an iterable container type to "
                f"resolve to a collection of resource instances. Got: "
                f"{handler!r}."
            )

        # Create path information
        info = self._create_path_info(skip_last_node=skip_last_node)

        # Create resolver function signature
        return_annotation = Annotation.serialize(
            self.target, origin=handler, metadata=metadata
        )
        signature = Signature(
            parameters=list(info.parameters.values()),
            return_annotation=return_annotation,
        )

        # Resolve the resource instance or collection of resource based on the
        # provided arguments and path parameter definitions.
        async def resolver(*args: str) -> Any:
            args_queue = deque(args)
            nodes_queue = deque(self.nodes)
            selector: Key[Any] | KeyList[Any] | None = None

            while nodes_queue:
                node = nodes_queue.popleft()
                has_remaining_nodes = True if nodes_queue else False

                # Handle last node for collection resolution
                if skip_last_node and not has_remaining_nodes:
                    if selector is None:
                        selector = KeyList.validate({}, resource=node.resource)
                    else:
                        assert node.backref is not None
                        selector = KeyList.validate(
                            {node.backref.alias: selector.entries()},
                            resource=node.resource,
                        )
                    break

                # Resolve resource directly for "unknown-to-one" relationships
                if node.accessor and node.accessor.collection is None:
                    assert node.backref is not None and selector is not None
                    selector = Key.validate(
                        {node.backref.alias: selector.entries()},
                        resource=node.resource,
                    )
                    continue

                # Retrieve next argument
                if not args_queue:
                    raise ValueError(
                        f"Resource path {self!r} requires additional selector "
                        f"arguments to be resolved. Got: {args!r}."
                    )
                arg = args_queue.popleft()

                # Resolve selector
                if selector is None:
                    if has_remaining_nodes:
                        selector = KeyList.validate(
                            arg, resource=node.resource
                        )
                    else:
                        selector = Key.validate(arg, resource=node.resource)
                else:
                    assert node.backref is not None
                    if has_remaining_nodes:
                        selector = KeyList.validate(
                            arg,
                            resource=node.resource,
                            update={node.backref.alias: selector.entries()},
                        )
                    else:
                        selector = Key.validate(
                            arg,
                            resource=node.resource,
                            update={node.backref.alias: selector.entries()},
                        )

            if args_queue:
                raise ValueError(
                    f"Resource path {self!r} has additional selector "
                    f"arguments that are not required to be resolved. "
                    f"Got: {args!r}."
                )

            assert selector is not None
            if return_handler:
                if handler in (Key, KeyList):
                    return selector
                return handler(**selector)  # type: ignore[misc]

            if __session:
                return await selector.resolve(__session, limit=max_selection)
            async with async_session_manager(on_missing='raise') as session:
                return await selector.resolve(session, limit=max_selection)

        setattr(resolver, '__signature__', signature)
        return info, resolver

    def __eq__(self, value: object) -> bool:
        return all(
            node == other_node
            for node, other_node
            in zip(self.nodes, getattr(value, 'nodes', []))
        )

    def __ne__(self, value: object) -> bool:
        return not self.__eq__(value)

    def __contains__(self, obj: object) -> bool:
        return obj in self.nodes

    def __iter__(self) -> Iterator[ResourceNode['BaseResource']]:
        yield from self.nodes

    def __reversed__(self) -> Iterator[ResourceNode['BaseResource']]:
        yield from reversed( self.nodes)

    def __len__(self) -> int:
        return len(self.nodes)

    def __getitem__(self, index: int) -> ResourceNode['BaseResource']:
        return self.nodes[index]

    def __hash__(self) -> int:
        return hash((self.root, *self.nodes))

    def __deepcopy__(self, memo: dict[int, Any]) -> Self:
        return self.__class__(
            self.root,
            *[node.segment for node in self.nodes if node.segment]
        )

    def __repr__(self) -> str:
        return f'ResourcePath({self})'

    def __str__(self) -> str:
        root_alias = self.root.resource_config.alias
        if len(self.nodes) == 1:
            return root_alias
        return '%s:%s' % (
            root_alias,
            '/'.join([node.segment for node in self.nodes if node.segment]),
        )


# MARK: Resource Manager

class ResourceManager(Manager[Resource]):
    """A resource class manager.

    It provides a common interface to access and manage the service methods
    associated with a resource class.
    """
    if typing.TYPE_CHECKING:
        __config_managed__: type[Resource]

    def __init__(self, resource: type[Resource]) -> None:
        """Initialize the resource manager.

        It initializes the resource manager with the provided resource class,
        and collects all resource public instance methods decorated with the
        route decorator.

        Args:
            resource: The resource class to manage.
        """
        # Set the resource class
        super().__init__(resource)

        # Schedule public resource methods gathering
        self.resource.__state__.schedule(
            self._add_resource_methods, when=Lifecycle.LOADING,
        )

    def _add_resource_methods(self) -> None:
        """Add resource methods to the manager."""
        # Collect and add to the manager resource public method members
        # decorated with the route decorator, including static and class method
        # members, and excluding dunder and private method members.
        members = \
            getmembers_static(self.resource, predicate=isfunction_lenient)
        for name, method in members:
            # Skip undecorated methods
            if not is_endpoint(method):
                continue
            # Skip dunder and private method members
            if name.startswith('_'):
                raise AttributeError(
                    f"A dunder or private method cannot be decorated with a "
                    f"route decorator. Got method {name!r} in resource class "
                    f"{name!r}."
                )
            # Add method member to dictionary
            assert isinstance(method, WithFunctionTypes)
            wrapped_method = _wrap_resource_method(self.resource, method)
            self._add_method(name, wrapped_method)

    @property
    def resource(self) -> type[Resource]:
        return self.__config_managed__

    async def exists(
        self,
        __session: AsyncSession | None = None,
        /,
        **kwargs: Any,
    ) -> bool:
        """Check if a resource instance exist based on the given filters.

        Args:
            __session: The async session to use for the operation. If not
                provided, the session in the current context is used.
                Defaults to ``None``.
            **kwargs: The filters to apply when querying the resource
                instances as keyword arguments with the field aliases as keys
                and the values to filter by as values.

        Returns:
            ``True`` if a resource instance exists that matches the provided
            filters, otherwise ``False``.
        """
        async def query(session: AsyncSession) -> bool:
            query = select(select(self.resource).where(**kwargs).exists())
            buffer = await session.execute(query)
            return buffer.scalar() or False

        if __session:
            return await query(__session)
        async with async_session_manager(on_missing='raise') as session:
            return await query(session)

    async def get(
        self,
        __session: AsyncSession | None = None,
        /,
        **kwargs: Any,
    ) -> Resource | None:
        """Get a single resource instance based on the given filters.

        Args:
            __session: The async session to use for the operation. If not
                provided, the session in the current context is used.
                Defaults to ``None``.
            **kwargs: The filters to apply when querying the resource
                instances as keyword arguments with the field aliases as keys
                and the values to filter by as values.

        Returns:
            A single resource instance that matches the provided filters, or
            ``None`` if no resource instance is found.

        Note:
            This method is equivalent to the `get_one` method, but it returns
            ``None`` if no resource instance is found for the provided filters
            instead of raising an exception.
        """
        async def query(session: AsyncSession) -> Resource | None:
            query = select(self.resource).filter_by(**kwargs).limit(1)
            buffer = await session.execute(query)
            return buffer.scalar()

        if __session:
            return await query(__session)
        async with async_session_manager(on_missing='raise') as session:
            return await query(session)

    async def get_many(
        self,
        __session: AsyncSession | None = None,
        /,
        **kwargs: Any,
    ) -> Sequence[Resource]:
        """Get a collection of resource instances based on the given filters.

        Args:
            __session: The async session to use for the operation. If not
                provided, the session in the current context is used.
                Defaults to ``None``.
            **kwargs: The filters to apply when querying the resource
                instances as keyword arguments with the field aliases as keys
                and the values to filter by as values.

        Returns:
            A collection of resource instances that match the provided filters.
        """
        async def query(session: AsyncSession) -> Sequence[Resource]:
            query = select(self.resource).filter_by(**kwargs)
            buffer = await session.execute(query)
            return buffer.unique().scalars().all()

        if __session:
            return await query(__session)
        async with async_session_manager(on_missing='raise') as session:
            return await query(session)

    async def get_one(
        self,
        __session: AsyncSession | None = None,
        /,
        **kwargs: Any,
    ) -> Resource:
        """Get exactly one resource instance based on the given filters.

        It returns exactly one resource instance that matches the provided
        filters, or raises an exception if no resource instance is found.

        Args:
            __session: The async session to use for the operation. If not
                provided, the session in the current context is used.
                Defaults to ``None``.
            **kwargs: The filters to apply when querying the resource
                instances as keyword arguments with the field aliases as keys
                and the values to filter by as values.

        Raises:
            ValueError: If no resource instance is found.

        Returns:
            A single resource instance that matches the provided filters.

        Note:
            This method is equivalent to the `get` method, but it raises an
            exception if no resource instance is found for the provided filters
            instead of returning ``None``.
        """
        async def query(session: AsyncSession) -> Resource:
            query = select(self.resource).filter_by(**kwargs).limit(2)
            buffer = await session.execute(query)
            result = buffer.unique().scalars().all()
            if len(result) != 1:
                raise ValueError(
                    f"Expected exactly one resource instance matching the "
                    f"provided filters. Got: {len(result)} instances with "
                    f"filters: {kwargs}."
                )
            return result[0]

        if __session:
            return await query(__session)
        async with async_session_manager(on_missing='raise') as session:
            return await query(session)

    def __repr__(self) -> str:
        return self.resource.__qualname__ + 'Manager'


# MARK: Resource State

class ResourceState(Generic[Resource]):
    """A resource class state.

    It provides utilities to manage the state of a resource class, including
    its lifecycle status and scheduled tasks associated with the resource class
    build.
    """
    if typing.TYPE_CHECKING:
        owner: type[Resource]
        status: ResolvedState
        tasks: dict[SchedulableState, list[Action]]

    def __init__(self, resource: type[Resource]) -> None:
        """Initialize the resource state.

        It initializes the resource state with the provided resource class and
        sets the lifecycle status to ``RESOLVED``.

        Args:
            resource: The resource class owner of the state.
        """
        self.owner = resource

        # Initialize lifecycle status and scheduled tasks
        self.status = Lifecycle.RESOLVED
        self.tasks = {
            Lifecycle.INITIALIZING: [],
            Lifecycle.LOADING: [],
            Lifecycle.BUILDING: [],
            Lifecycle.FINALIZING: [],
            Lifecycle.READY: [],
        }

    def flush(
        self,
        _check_guard: set[str] | None = None,
        _flush_guard: set[str] | None = None,
        *,
        until: SchedulableState | None = None,
    ) -> bool | None:
        """Advance the resource through its lifecycle states.

        This method handles the transition through lifecycle states while
        managing dependencies and preventing circular references. For each
        state transition, it ensures all dependencies have reached the required
        state, executes any scheduled tasks, and propagates the state change to
        dependent resources.

        The flush operation follows these steps:
        1. Check and handle any base resources (inheritance-based dependencies)
        2. Verify all resource dependencies have reached the required state
        3. Execute scheduled tasks for the next state
        4. Update the resource state
        5. Propagate state changes to dependent resources

        Args:
            _check_guard: Internal set to prevent circular dependency checks.
                Used to track which resources have been processed during
                dependency validation. Defaults to an empty set.
            _flush_guard: Internal set to prevent recursive flush operations.
                Used to detect and break circular flush attempts between
                interdependent resources. Defaults to an empty set.
            until: The target lifecycle state to reach. The flush operation
                will advance the resource state up to this point but not
                beyond. If not specified, attempts to reach the ``READY``
                state. Defaults to ``None``.

        Returns:
            ``False`` if dependencies prevent state advancement, ``None`` if no
            state change is needed (already at target state or detected
            recursion), or recursively continues flushing until target state is
            reached. Otherwise, returns ``True`` to indicate a successful state
            advancement.
        """
        # Initialize recursion guards
        _check_guard = set() if _check_guard is None else _check_guard
        _flush_guard = set() if _flush_guard is None else _flush_guard

        name = get_object_name(self.owner, fullname=True)
        if name in _flush_guard:
            return None
        _flush_guard.add(name)

        # Validate flush lifecycle status
        until = until or Lifecycle.READY
        if self.status >= until:
            return None

        next_status = self.status.next()

        # Helper function to flush bases
        def flush_bases() -> bool:
            for base in self.owner.__bases__:
                if not is_resource(base) or is_abstract(base):
                    continue
                if base.__state__.flush(
                    _check_guard,
                    _flush_guard,
                    until=next_status,
                ) is False:
                    return False
            return True

        # Helper function to check dependencies
        def check_dependencies() -> bool:
            if runtime.get_dependencies(
                self.owner,
                _check_guard,
                kind='resources',
                status=self.status.lower(),
                max_depth=None,
            ):
                return False
            return True

        # Check for pending dependencies
        if not flush_bases() or not check_dependencies():
            return False

        # Process and clear scheduled tasks
        for scheduled_task in self.tasks[next_status]:
            scheduled_task(self.owner)
        self.tasks[next_status].clear()

        self.status = next_status

        logger.debug(
            f"rsc:{self.owner.resource_config.alias} -> {self.status}"
        )

        # Recursively flush dependents
        for dependent in runtime.get_dependents(self.owner, kind='resources'):
            dependent.__state__.flush(
                _check_guard.copy(),
                _flush_guard,
                until=next_status,
            )

        # Recursively flush children
        for sub in get_subclasses(self.owner):
            assert is_resource(sub)
            sub.__state__.flush(
                _check_guard.copy(),
                _flush_guard,
                until=next_status,
            )

        return self.flush(until=until)

    def schedule(
        self,
        *tasks: Task,
        _guard: set[str] | None = None,
        when: SchedulableState | None = None,
        when_reached: Literal['fallback', 'run', 'skip'] = 'run',
        when_future: Literal['await', 'skip'] = 'await',
        propagate: bool = False,
    ) -> None:
        """Schedule tasks for execution.

        It schedules tasks for immediate or future execution based on resource
        lifecycle states. Each task can target a specific state, with
        configurable behavior for handling already reached states using the
        `when_reached` option, and future states using the `when_future`
        option. Both strategies can be used concurrently to handle different
        scenarios. Tasks scheduled for the same lifecycle state execute
        sequentially in the order they were added.

        Args:
            *tasks: The tasks to execute or schedule for the resource state.
                Multiple tasks scheduled for the same state are executed
                sequentially in the order they were added.
            _guard: Internal set to prevent recursive schedule propagation
                operations. Used to detect and break circular schedule attempts
                between interdependent resources. Defaults to an empty set.
            when: Default scheduling state for the provided tasks. If a task
                doesn't specify its own lifecycle state to schedule for, this
                value is used. When ``None``, tasks are scheduled for the next
                resource lifecycle state. Defaults to ``None``.
            when_reached: The strategy to apply when a task is scheduled for a
                state that has already been reached. It can be set to one of
                the following values:
                - ``'fallback'``: Fallback to the previous state and schedule
                    the task for execution,
                - ``'run'``: Run the task immediately,
                - ``'skip'``: Skip the task and do not execute it.
                Defaults to ``'run'``.
            when_future: The strategy to apply when a task is scheduled for a
                future state. It can be set to one of the following values:
                - ``'await'``: Await the state transition and execute the task
                    when the state is reached,
                - ``'skip'``: Skip the task and do not execute it.
                Defaults to ``'await'``.
            propagate: Whether to propagate and apply the same scheduled tasks
                to all dependent and child resources. Defaults to ``False``.
        """
        # Initialize recursion guard
        _guard = set() if _guard is None else _guard

        name = get_object_name(self.owner, fullname=True)
        if name in _guard:
            return
        _guard.add(name)

        # Validate default scheduling state
        when = when or self.status.next()

        # Collect and sort tasks based on lifecycle state
        scheduled_tasks: list[tuple[Action, SchedulableState]]
        if len(_guard) == 1:
            scheduled_tasks = []
            for task in tasks:
                if isinstance(task, tuple):
                    task_action, task_when = task
                else:
                    task_action = task
                    task_when = when or self.status  # type: ignore
                if not isinstance(task_action, Action):
                    task_action = Action(task_action)
                scheduled_tasks.append((task_action, task_when))
            scheduled_tasks = sorted(scheduled_tasks, key=lambda task: task[1])
        else:
            scheduled_tasks = tasks  # type: ignore

        # Schedule or execute tasks based on trigger state
        for task_action, task_when in scheduled_tasks:
            # Handle reached state
            if task_when <= self.status:
                if when_reached == 'skip':
                    continue
                if when_reached == 'run':
                    task_action(self.owner)
                    continue
                # Fallback
                self.status = min(self.status.previous(), task_when)
                self.tasks[task_when].append(task_action)

            # Handle future state
            else:
                if when_future == 'skip':
                    continue
                # Await
                self.tasks[task_when].append(task_action)

        # Skip propagation if not required
        if not propagate:
            return

        # Recursively schedule dependents
        for dependent in runtime.get_dependents(self.owner, kind='resources'):
            dependent.__state__.schedule(
                *scheduled_tasks,
                _guard=_guard,
                when=when,
                when_reached=when_reached,
                when_future=when_future,
                propagate=propagate,
            )

        # Recursively schedule children
        for sub in get_subclasses(self.owner):
            assert is_resource(sub)
            sub.__state__.schedule(
                *scheduled_tasks,
                _guard=_guard,
                when=when,
                when_reached=when_reached,
                when_future=when_future,
                propagate=propagate,
            )

    def __repr__(self) -> str:
        return self.owner.__qualname__ + 'State'


# MARK: Helpers (base)

def _extract_base_fields_namespace(
    namespace: dict[str, Any], /
) -> dict[str, Any]:
    """Extract base fields namespace from the resource class namespace."""
    annotations: dict[str, Any] = namespace.get('__annotations__', {})

    fields_annotations: dict[str, Any] = {}
    fields_namespace: dict[str, Any] = {
        '__annotations__': fields_annotations,
        '__doc__': namespace.get('__doc__', None),
        '__module__': namespace.get('__module__', None),
    }

    # Extract annotations
    for key, value in list(annotations.items()):
        # Skip dunder attributes
        if key.startswith('__') and key.endswith('__'):
            continue
        # Skip forbidden and protected attributes
        if match_any_pattern(key, *FORBIDDEN_ATTRS, *PROTECTED_ATTRS):
            continue
        fields_annotations[key] = annotations.pop(key)

    # Extract namespace
    for key, value in list(namespace.items()):
        # Skip dunder attributes
        if key.startswith('__') and key.endswith('__'):
            continue
        # Skip forbidden and protected attributes
        if match_any_pattern(key, *FORBIDDEN_ATTRS, *PROTECTED_ATTRS):
            continue
        # Skip class attributes
        if inspect.isclass(value):
            continue
        # Skip functions
        if isfunction_lenient(value):
            continue
        # Skip SQLAlchemy attributes
        if key.startswith('_sa_'):
            continue
        fields_namespace[key] = namespace.pop(key)

    return fields_namespace


def _init_base_identity_and_type(cls: 'ResourceMeta', /) -> None:
    """Initialize the base identity and type fields for the resource class."""
    # Identity field setup
    id = cls.resource_fields['id']
    id_strategy = cls.resource_config.id_strategy
    id_type = cls.resource_config.id_type

    # Helper to handle identity field auto strategy setup
    def handle_auto_strategy() -> None:
        if id_type == 'integer':
            return id._update(annotation=int, init=False)
        if id_type == 'uuid':
            return id._update(
                annotation=UUID4,
                default=Undefined,
                default_factory=uuid.uuid4,
                init=False,
            )
        raise NotImplementedError(f"Unsupported identity type: {id_type!r}.")

    # Helper to handle identity field manual strategy setup
    def handle_manual_strategy() -> None:
        if id_type == 'integer':
            return id._update(annotation=int, default=Undefined)
        if id_type == 'uuid':
            return id._update(annotation=UUID4, default=Undefined)
        raise NotImplementedError(f"Unsupported identity type: {id_type!r}.")

    # Helper to handle identity field hybrid strategy setup
    def handle_hybrid_strategy() -> None:
        if id_type == 'integer':
            return id._update(annotation=int)
        if id_type == 'uuid':
            return id._update(
                annotation=UUID4,
                default=Undefined,
                default_factory=uuid.uuid4,
            )
        raise NotImplementedError(f"Unsupported identity type: {id_type!r}.")

    # Handle identity field setup
    match id_strategy:
        case 'auto':
            handle_auto_strategy()
        case 'manual':
            handle_manual_strategy()
        case 'hybrid':
            handle_hybrid_strategy()
        case _:
            raise NotImplementedError(
                f"Unsupported identity strategy: {id_strategy!r}."
            )

    # Type field setup
    type_ = cls.resource_fields['type_']
    type_alias = cls.resource_config.alias
    type_._update(
        annotation=Literal[type_alias],  # type: ignore
        default=type_alias,
    )


def _init_base_model_and_configuration(
    cls: 'ResourceMeta',
    bases: tuple[type, ...],
    fields_namespace: dict[str, Any],
    /,
    *args: Any,
) -> None:
    """Initialize the base model for the resource class."""
    model_name = 'Model'
    model_qualname = f'{cls.__qualname__}.Model'

    model_bases = (BaseModel,)
    for base in bases:
        model_base = getattr(base, 'Model', None)
        if not model_base or not issubclass(model_base, BaseModel):
            continue
        model_bases = (model_base,)
        break

    model_namespace: dict[str, Any] = {
        **fields_namespace,
        '__name__': model_name,
        '__qualname__': model_qualname,
        '__config__': cls.resource_config.entries(
            scope='set',
            include_keys=ModelConfig,
        ),
    }

    # Create resource model
    model: ModelType = ModelMeta(  # type: ignore[assignment]
        model_name,
        model_bases,
        model_namespace,
        __pydantic_owner__='resource',
        __pydantic_resource__=cls,
        *args,
        defer_build=True,
    )

    # Validate model configuration
    model.model_config.validate()

    # Set resource model
    setattr(cls, 'Model', model)

    # Validate resource configuration and initialize identity and type
    cls.resource_config.validate()

    if not is_abstract(cls):
        _init_base_identity_and_type(cls)


def _build_base_model(cls: 'ResourceMeta', /) -> None:
    """Build the base model for the resource class."""
    cls.Model.model_rebuild(force=True)


# MARK: Helpers (declarative)

def _init_declarative_fields(
    cls: 'ResourceMeta', bases: tuple[type, ...], /
) -> None:
    """Initialize the declarative fields for the resource class."""
    # Skip if abstract
    if is_abstract(cls):
        return

    # Clean up empty resources which implements no field definitions and may
    # only contains the pass or ellipsis statement. Those classes usually bear
    # the same annotations as the parent class.
    if _is_empty_definition(cls, bases):
        cls.__annotations__ = {}

    # Update concrete resources fields
    for key, field in cls.resource_fields.items():
        # Check if field shadows a forbidden or protected attribute
        if match_any_pattern(key, *ALL_ATTRS):
            if key in cls.__annotations__:
                raise PlateformeError(
                    f"Invalid field {key!r} for resource "
                    f"{cls.__qualname__!r}. The field shadows either a "
                    f"forbidden or protected attribute.",
                    code='field-invalid-config',
                )
            continue

        # Check if field shadows a concrete base attribute
        if base_match := next((
            base for base in bases
            if key in getattr(base, 'resource_attributes', {}).keys()
        ), None):
            if key in cls.__annotations__:
                raise PlateformeError(
                    f"Invalid field {key!r} for resource "
                    f"{cls.__qualname__!r}. The field shadows an attribute in "
                    f"parent class {base_match.__qualname__!r}.",
                    code='field-invalid-config',
            )
            continue

        # Check if field is valid
        if not isinstance(field, FieldInfo):
            raise PlateformeError(
                f"Invalid field {key!r} for resource "
                f"{cls.__qualname__!r}. A field must be an instance of the "
                f"`FieldInfo` class.",
                code='field-invalid-config',
            )

        # Process field definition
        if field.linked:
            cls.resource_package._add_resource_dependency(field)
        else:
            setattr(cls, key, field.create_column())

        # Remove field annotation
        cls.__annotations__.pop(key, None)


def _init_declarative_composite_indexes(cls: 'ResourceMeta', /) -> None:
    """Initialize the declarative composite indexes for the resource class.

    It collects the resource composite indexes defined in the resource
    configuration and creates the corresponding SQLAlchemy indexes for the
    resource class. This initialization is delayed to ensure that all resource
    attributes are defined before creating the indexes, especially the indexes
    configured on association fields.
    """
    for index in cls.resource_config.indexes:
        # Resolve index expressions
        index_expressions: tuple[InstrumentedAttribute[Any], ...] = ()
        for field_alias in index['aliases']:
            index_field = cls.resource_fields[field_alias]
            index_alias = index_field.rel_attribute or field_alias
            if index_alias not in cls.resource_attributes:
                raise PlateformeError(
                    f"Invalid index field {index_alias!r} for resource "
                    f"{cls.__qualname__!r}. The field does not exist in the "
                    f"resource attributes.",
                    code='resource-invalid-config',
                )
            index_expressions += (cls.resource_attributes[index_alias],)
        # Build index
        Index(
            NAMING_CONVENTION['ix'] % {'column_0_label': index['name']},
            *index_expressions,
            unique=index['unique'],
        )


def _init_declarative_model(
    cls: 'ResourceMeta', bases: tuple[type, ...], /
) -> None:
    """Initialize the declarative model for the resource class."""
    # Retrieve parent resource
    parent: type | None = None
    for base in bases:
        if base in (Configurable, Representation):
            continue
        if is_abstract(base):
            continue
        parent = base
        break

    # Skip if abstract
    if is_abstract(cls):
        if parent:
            raise PlateformeError(
                f"Invalid resource {cls.__qualname__!r}. Abstract resource "
                f"cannot inherit from another concrete resource.",
                code='resource-invalid-config',
            )
        return

    # Otherwise handle concrete resource...

    # Initialize declarative attributes. Allow unmapped attributes to be
    # defined on the resource class. This is necessary to allow the definition
    # of associations on the resource class without triggering any non-mapped
    # attribute errors.
    setattr(cls, '__allow_unmapped__', True)
    setattr(cls, '_sa_registry', cls.resource_package.registry)

    # Set declarative arguments
    declarative_args: tuple[Any, ...] = (
        {
            # Database schema set to none as this is handled dynamically by
            # the Plateforme application.
            'schema': None,
            # Information about the table
            'info': {'type': 'resource'},
        },
    )

    # Handle variant resource
    if parent:
        # Set polymorphic identity for table inheritance
        setattr(cls, '__mapper_args__', {
            'polymorphic_identity': cls.resource_config.alias,
            'polymorphic_load': 'inline',
            **cls.resource_config.mapper_args,
        })
        # Handle joined table inheritance (single table inheritance does
        # not require any additional setup).
        parent_config: ResourceConfig = getattr(parent, 'resource_config')
        parent_attributes: dict[str, InstrumentedAttribute[Any]] = \
            getattr(parent, 'resource_attributes')
        if not parent_config.use_single_table_inheritance:
            setattr(cls, '__tablename__', cls.resource_config.alias)
            setattr(cls, '__table_args__', declarative_args)
            setattr(cls, 'id', Column(
                ForeignKey(parent_attributes['id']),
                name='id',
                type_=parent_config.id_engine,
                primary_key=True,
                nullable=False,
            ))

    # Handle base resource
    else:
        # Set table name and arguments
        setattr(cls, '__tablename__', cls.resource_config.alias)
        setattr(cls, '__table_args__', declarative_args)
        # Set polymorphic identity for table inheritance
        setattr(cls, '__mapper_args__', {
            'polymorphic_identity': cls.resource_config.alias,
            'polymorphic_on': 'type_',
            **cls.resource_config.mapper_args,
        })
        # Set table managed columns
        setattr(cls, 'id', Column(
            name='id',
            type_=cls.resource_config.id_engine,
            autoincrement=cls.resource_config.id_autoincrement,
            primary_key=True,
            nullable=False,
        ))
        setattr(cls, 'type_', Column(
            name='type',
            type_=StringEngine,
            nullable=False,
        ))


# MARK: Helpers (identifiers and indexes)

def _init_identifiers_and_indexes(cls: 'ResourceMeta', /) -> None:
    """Initialize the identifiers and indexes for the resource class.

    It collects the identifiers and indexes as sets of field aliases that
    respectively uniquely identify or index the resource class. It sets
    ``{'id'}`` by default for both, and then looks for unique and indexed
    singular or composite field definitions.
    """
    assert not is_abstract(cls)

    # Initialize identifiers and indexes with default "id" field
    identifiers: list[set[str]] = [{'id'}]
    indexes: list[set[str]] = [{'id'}]

    # Update identifiers and indexes with field definitions
    for field in cls.resource_fields.values():
        if field.unique:
            identifiers.append({field.alias})
        if field.indexed:
            indexes.append({field.alias})

    # Update identifiers and indexes with composite definitions
    for index in cls.resource_config.indexes:
        if index['unique']:
            identifiers.append(index['aliases'])
        indexes.append(index['aliases'])

    # Set identifiers and indexes
    setattr(cls, 'resource_identifiers', tuple(identifiers))
    setattr(cls, 'resource_indexes', tuple(indexes))


# MARK: Helpers (package)

def _init_package(cls: 'ResourceMeta', /) -> None:
    """Initialize the package for the resource class."""
    if is_abstract(cls):
        return
    package = runtime.import_package(cls.__module__, force_resolution=True)
    setattr(cls, 'resource_package', package)


# MARK: Helpers (schemas)

def _init_schemas(cls: 'ResourceMeta', /) -> None:
    """Initialize the schema models for the resource class."""
    assert not is_abstract(cls)

    models = collect_models(cls)
    for model in models:
        cls._register_schema(model.__name__, __owner__=cls, __base__=model)


def _create_schema_base_model(
    cls: 'ResourceMeta',
    __model_name: str,
    __schema_alias: str,
    __schema_lookup: tuple[str, ...],
    *,
    __doc__: str | None = None,
    __base__: ModelType | tuple[ModelType, ...] | None = None,
    __module__: str | None = None,
    __validators__: dict[str, ClassMethodType] | None = None,
    __cls_kwargs__: dict[str, Any] | None = None,
    __collect__: tuple[FieldLookup, ...] | None = None,
    **field_definitions: FieldDefinition,
) -> None:
    """Create a new resource schema base model.

    It constructs a new resource schema base model based on the provided field
    definitions and lookup filters.

    Args:
        __model_name: The name of the new resource schema base model.
        __schema_alias: The alias of the resource schema the new base model is
            created for.
        __schema_lookup: The schema lookup aliases used to resolve the schema
            references within the resource schema base model.
        __doc__: The docstring of the new model.
        __base__: The base class or classes for the new model.
        __module__: The name of the module that the model belongs to. If
            ``None``, the value is retrieved from ``sys._getframe(1)``.
        __validators__: A dictionary of class methods that validate fields.
        __cls_kwargs__: A dictionary of keyword arguments for class creation,
            such as ``metaclass``.
        __collect__: The field lookup filters to collect fields from the
            resource schema model. Defaults to ``None``.
        **field_definitions: Attributes of the new model. They should be passed
            in the format: ``<name>=(<type>, <default value>)`` or
            ``<name>=(<type>, <FieldInfo>)``.

    Raises:
        PlateformeError: If the resource schema model cannot be resolved.

    Note:
        See the `register_schema` method of the `ResourceMeta` metaclass for
        more information on the keyword arguments and their usage.
    """
    # Base field definitions
    base_field_definitions = {}
    if __base__:
        if not isinstance(__base__, tuple):
            __base__ = (__base__,)
        for base in __base__:
            base_field_definitions.update(collect_fields(base))

    # Collect field definitions
    if __collect__:
        collect_field_definitions = {}
        for lookup in __collect__:
            collect_field_definitions.update(cls._collect_fields(**lookup))
    else:
        collect_field_definitions = {}

    # Merge field definitions
    field_definitions = {
        **base_field_definitions,
        **collect_field_definitions,
        **field_definitions,
    }

    # Update field information
    for name, (annotation, field) in field_definitions.items():
        if not isinstance(field, FieldInfo):
            continue
        if field.target is None:
            continue
        field._default(target_ref=True)
        field._default(target_schemas=__schema_lookup)
        field_definitions[name] = (annotation, field)

    # Resolve base model
    base_model = None
    for base in cls.__bases__:
        base_schema = getattr(base, 'resource_schemas', {})
        if base_discriminated:= base_schema.get(__schema_alias):
            assert issubclass(base_discriminated, DiscriminatedModel)
            base_model = base_discriminated.get_root_base()
            break

    # Create model
    model = create_model(
        __model_name,
        __config__=None,
        __doc__=__doc__,
        __base__=base_model,
        __module__=cls.__module__,
        __validators__=__validators__,
        __cls_kwargs__={
            **(__cls_kwargs__ or {}),
            '__pydantic_resource__': cls,
        },
        **field_definitions,
    )

    # Update and rebuild resource schema
    cls.resource_schemas[__schema_alias].update_root_members(base=model)
    cls._rebuild_schemas(__schema_alias, force=True)


def _build_schemas_and_adapter(cls: 'ResourceMeta', /) -> None:
    """Build the schemas and adapter for the resource class."""
    cls._rebuild_adapter()
    cls._rebuild_schemas()

    # Update all base resource adapter and schema with this new variant
    for base in cls.__bases__:
        if not issubclass(base, BaseResource):
            continue
        if is_abstract(base) or not base.__pydantic_complete__:
            break
        base._rebuild_adapter()
        base._rebuild_schemas()


# MARK: Helpers (specs and services)

def _init_specs_and_services(
    cls: 'ResourceMeta', bases: tuple[type, ...], /
) -> None:
    """Initialize the specs and services for the resource class."""
    # Initialize specs
    specs: tuple[SpecType, ...] = (CRUDSpec,)
    for base in bases:
        if specs_base := getattr(base, '__config_specs__', None):
            specs += specs_base
    specs += cls.resource_config.specs
    # Use dict to remove duplicates instead of set to preserve order of the
    # specifications and add them to the resource.
    specs = tuple(dict.fromkeys(specs))

    setattr(cls, '__config_specs__', specs)

    # Retrieve services and ellipsis index
    services: tuple[BaseService | ServiceType, ...] = ()
    ellipsis: list[int] = []
    for count, service in enumerate(cls.resource_config.services):
        if service is Ellipsis:
            ellipsis.append(count)
        elif isinstance(service, type):
            services += (service,)
        else:
            services += (copy_service(service),)

    # Validate ellipsis usage
    if len(ellipsis) > 1:
        raise PlateformeError(
            f"Invalid services configuration for resource "
            f"{cls.__qualname__!r}. Ellipsis can only be used once in the "
            f"provided services list.",
            code='services-invalid-config',
        )

    # Inherit services from parent resources based on the ellipsis index
    elif len(ellipsis) == 1:
        # Resolve base services
        services_base = None
        for base in bases:
            if services_base := getattr(base, '__config_services__', None):
                break
        if services_base is None:
            raise PlateformeError(
                f"Invalid ellipsis services configuration for resource "
                f"{cls.__qualname__!r}. No base services found.",
                code='services-invalid-config',
            )

        # Resolve services
        services_left = services[:ellipsis[0]]
        services_right = services[ellipsis[0]:]
        # Use dict to remove duplicates instead of set to preserve order of the
        # services and add them to the resource.
        services = tuple(dict.fromkeys([
            *services_left, *services_base, *services_right
        ]))

    setattr(cls, '__config_services__', services)

    # Skip if not abstract
    if is_abstract(cls):
        return

    # Schedule specifications registration
    cls.__state__.schedule(
        Action(setattr, bound=True, args=('__config_specs__', ())),
        Action(cls._add_specs, args=specs),
        when=Lifecycle.LOADING,
    )

    # Schedule services registration
    cls.__state__.schedule(
        Action(setattr, bound=True, args=('__config_services__', ())),
        Action(cls._add_services, args=services),
        when=Lifecycle.LOADING,
    )


# MARK: Resource Metaclass

@typing.dataclass_transform(
    kw_only_default=True,
    field_specifiers=(Field, PrivateAttr, NoInitField)
)
class ResourceMeta(ABCMeta, ConfigurableMeta, DeclarativeMeta):
    """Meta class for the base resource class."""
    if typing.TYPE_CHECKING:
        __config__: ResourceConfig | ResourceConfigDict
        __config_services__: tuple[BaseService, ...]
        __config_specs__: tuple[SpecType, ...]
        __tablename__: str | None
        __table_args__: Any
        __mapper_args__: Any
        __pydantic_complete__: bool
        __manager__: ResourceManager['BaseResource']
        __state__: ResourceState['BaseResource']
        _sa_class_manager: ClassManager['BaseResource']
        _sa_registry: Registry
        resource_adapter: TypeAdapterList['BaseResource']
        resource_attributes: dict[str, InstrumentedAttribute[Any]]
        resource_computed_fields: dict[str, ComputedFieldInfo]
        resource_config: ResourceConfig
        resource_fields: dict[str, ResourceFieldInfo]
        resource_identifiers: tuple[set[str], ...]
        resource_indexes: tuple[set[str], ...]
        resource_package: 'Package'
        resource_path: str
        resource_schemas: dict[str, DiscriminatedModelType]

        # Model schema
        Model: ModelType

    def __new__(
        mcls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> type:
        """Create a new resource meta class.

        Args:
            name: The name of the class to be created.
            bases: The base classes of the class to be created.
            namespace: The attribute dictionary of the class to be created.
            *args: Pydantic metaclass arguments:
                - `__pydantic_generic_metadata__`: Metadata for generic
                    models.
                - `__pydantic_reset_parent_namespace__`: Reset parent
                    namespace.
                - `_create_model_module`: The module of the class to be
                    created, if created by `create_model`.
            **kwargs: Configurable metaclass arguments.

        Returns:
            The new resource class created by the metaclass.
        """
        # Check if the namespace has any forbidden attributes
        for attr in namespace:
            if match_any_pattern(attr, *FORBIDDEN_ATTRS):
                raise AttributeError(
                    f"Attribute {attr!r} cannot be set on resource class "
                    f"{name!r} as it is forbidden."
                )

        # Collect fields namespace
        fields_namespace = _extract_base_fields_namespace(namespace)

        # Create the configuration class
        cls = super().__new__(
            mcls,
            name,
            bases,
            namespace,
            config_attr='resource_config',
            partial_init=True,
            *args,
            **kwargs
        )

        # Initialize resource attributes
        setattr(cls, '__config_services__', ())
        setattr(cls, '__config_specs__', ())
        setattr(cls, '__state__', ResourceState(cls))
        setattr(cls, '__manager__', ResourceManager(cls))
        setattr(cls, 'resource_attributes', {})
        setattr(cls, 'resource_schemas', {})

        # Initialize resource base model
        _init_base_model_and_configuration(cls, bases, fields_namespace, *args)

        # Set resource post init method name
        if not isbaseclass_lenient(cls, 'BaseResource') \
                and 'resource_post_init' in namespace:
            post_init = namespace['resource_post_init']
            post_init_name = None if not post_init else 'resource_post_init'
            setattr(cls, '__pydantic_post_init__', post_init_name)

        return cls

    def __init__(
        cls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        /,
        **kwargs: Any,
    ) -> None:
        """Initialize the resource meta class."""
        # Initialize resource package
        _init_package(cls)

        # Initialize resource declarative model
        _init_declarative_model(cls, bases)
        _init_declarative_fields(cls, bases)

        # Initialize resource services
        _init_specs_and_services(cls, bases)

        # Skip if abstract
        if is_abstract(cls):
            return

        # Initialize SQLAlchemy declarative meta and add the created
        # instrumented attributes to the resource attributes dictionary.
        super().__init__(name, bases, namespace, **kwargs)
        for key, value in list(cls.__dict__.items()):
            # Skip dunder attributes
            if key.startswith('__') and key.endswith('__'):
                continue
            if isinstance(value, InstrumentedAttribute):
                cls.resource_attributes[key] = value

        # Initialize resource identifiers and schemas
        _init_identifiers_and_indexes(cls)
        _init_schemas(cls)

        # Add resource to its package
        cls.resource_package._add_resource(cls)  # type: ignore

        # Schedule initialization build tasks
        cls.__state__.schedule(
            Action(_build_base_model, bound=True),
            Action(_init_declarative_composite_indexes, bound=True),
            when=Lifecycle.INITIALIZING,
        )

        # Schedule finalization build tasks
        cls.__state__.schedule(
            Action(_build_schemas_and_adapter, bound=True),
            when=Lifecycle.READY,
        )

        logger.debug(f"rsc:{cls.resource_config.alias} -> created")

        cls.__state__.flush()

    @property
    def objects(cls) -> ResourceManager['BaseResource']:
        """The resource manager that provides service methods on objects."""
        return cls.__manager__

    def _add_services(
        cls,
        *services: BaseService | ServiceType,
        raise_errors: bool = True,
    ) -> None:
        """Add services to the resource.

        It adds the provided services to the resource and binds them to the
        class. The services are used to extend the resource with additional
        functionalities.

        Args:
            *services: The services to add to the resource. It can be either a
                service instance or class that will get instantiated.
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
                    f"Invalid service {service!r} for resource "
                    f"{cls.__qualname__!r}. The service must be an instance "
                    f"of `BaseService`."
                )
            # Check if service is already bound to resource
            if any(type(s) is type(service) for s in cls.__config_services__) \
                    or cls._get_service(service.service_config.name):
                if not raise_errors:
                    continue
                raise PlateformeError(
                    f"Service {service!r} is already bound to resource "
                    f"{cls.__qualname__!r}.",
                    code='services-already-bound',
                )
            # Bind service to resource
            bind_service(service, cls, config=cls.resource_config.endpoints)
            # Add service to resource
            cls.__config_services__ += (service,)
            # Add service wrapped methods to resource manager
            methods = load_service(service)
            assert methods is not None
            for name, method in methods.items():
                cls.objects._add_method(name, method)

    def _get_service(cls, name: str) -> BaseService | None:
        """Get a service from the resource.

        It looks up each service within the resource and tries to retrieve a
        service with the provided name.

        Args:
            name: The name of the service to retrieve.

        Returns:
            The service with the provided name if found, ``None`` otherwise.
        """
        for service in cls.__config_services__:
            if service.service_config.name == name:
                return service
        return None

    def _remove_services(
        cls,
        *services: BaseService | str,
        raise_errors: bool = True,
    ) -> None:
        """Remove services from the resource.

        It removes the provided services from the resource and unbinds them
        from the class.

        Args:
            *services: The services to remove from the resource. It can be
                either a service instance or the name of the service.
            raise_errors: Whether to raise errors or fail silently.
                Defaults to ``True``.
        """
        for service in services:
            # Retrieve service if name is provided
            if isinstance(service, str):
                service = cls._get_service(service)  # type: ignore
            # Check if service exists
            if service is None or service not in cls.__config_services__:
                if not raise_errors:
                    continue
                raise PlateformeError(
                    f"Service {service!r} does not exist for resource "
                    f"{cls.__qualname__!r}.",
                    code='services-not-bound',
                )
            assert isinstance(service, BaseService)
            # Unbind service from resource
            unbind_service(service)
            # Clean up resource services
            cls.__config_services__ = tuple(
                s for s in cls.__config_services__ if s is not service
            )
            # Remove service wrapped methods from resource manager
            methods = cls.objects._collect_methods(owner=service)
            for name in methods:
                cls.objects._remove_method(name)

    def _add_specs(
        cls,
        *specs: SpecType,
        raise_errors: bool = True,
    ) -> None:
        """Add specifications to the resource.

        It adds the provided specifications to the resource and applies them
        to the class. The specifications are used to extend the resource with
        additional functionalities and model schemas.

        Args:
            *specs: The specifications to add to the resource.
            raise_errors: Whether to raise errors or fail silently.
                Defaults to ``True``.
        """
        for spec in specs:
            # Check if specification is already applied to resource
            if spec is BaseSpec or spec in cls.__config_specs__:
                if not raise_errors:
                    continue
                raise PlateformeError(
                    f"Specification {spec!r} is already applied to resource "
                    f"{cls.__qualname__!r}.",
                    code='spec-already-applied',
                )
            # Add specification to resource
            cls.__config_specs__ += (spec,)
            # Bind specification to resource and validate services
            apply_spec(spec, cls)

    def _remove_specs(
        cls,
        *specs: SpecType,
        raise_errors: bool = True,
    ) -> None:
        """Remove specifications from the resource.

        It removes the provided specifications from the resource and unbinds
        them from the class.

        Args:
            *specs: The specifications to remove from the resource.
            raise_errors: Whether to raise errors or fail silently.
                Defaults to ``True``.
        """
        # Helper function to check if specification is applied to a base
        def check_bases(spec: SpecType) -> bool:
            for base in cls.__bases__:
                if base_specs := getattr(base, '__config_specs__', None):
                    if spec in base_specs:
                        return True
            return False

        for spec in specs:
            # Check if specification is applied to resource
            if spec not in cls.__config_specs__:
                if not raise_errors:
                    continue
                raise PlateformeError(
                    f"Specification {spec!r} is not applied to resource "
                    f"{cls.__qualname__!r}.",
                    code='spec-not-applied',
                )
            # Check if specification is applied to a base
            if check_bases(spec):
                if not raise_errors:
                    continue
                raise PlateformeError(
                    f"Specification {spec!r} is applied to a base class of "
                    f"resource {cls.__qualname__!r}.",
                    code='spec-applied-to-base',
                )
            # Remove specification from resource
            cls.__config_specs__ = tuple(
                s for s in cls.__config_specs__ if s is not spec
            )
            # Clean up resource model schemas
            for name, schema in list(cls.resource_schemas.items()):
                if schema.__registrant__ == id(spec):
                    cls.resource_schemas.pop(name)

    def _collect_fields(
        cls, **lookup: Unpack[FieldLookup]
    ) -> dict[str, tuple[type[Any], ModelFieldInfo]]:
        """Collect the resource model field definitions.

        It collects the resource model field definitions based on the provided
        filters to include or exclude specific fields. The collected fields
        annotations are updated with the provided optional flag and update
        dictionary.

        Args:
            include: The filters to include specific fields based on the field
                attributes as a dictionary with the field attribute names as
                keys and the values to include as values. Defaults to ``None``.
            exclude: The filters to exclude specific fields based on the field
                attributes as a dictionary with the field attribute names as
                keys and the values to exclude as values. Defaults to ``None``.
            optional: A flag indicating whether to mark the field annotations
                as optional. Defaults to ``None``.
            update: The dictionary of field attributes to update.
                Defaults to ``None``.

        Returns:
            A dictionary of field names with the corresponding field
            annotations and field information.
        """
        return collect_fields(getattr(cls, 'Model'), **lookup)

    def _create_path(cls, *path: str) -> ResourcePath:
        """Create a new resource path from the resource.

        It creates a new resource path from the resource with the provided path
        segments. The path segments are used to navigate the resources graph.

        Args:
            path: The path segments used to navigate the resources graph.
                Defaults to an empty path generating a root resource path.

        Returns:
            A new resource path created from the current resource with the
            provided path segments.
        """
        return ResourcePath(cls, *path)  # type: ignore

    def _create_router(
        cls, **overrides: Unpack[APIRouterConfigDict]
    ) -> APIRouter:
        """Create a new resource API router with optional overrides.

        Args:
            **overrides: Additional keyword arguments to override the resource
                API router configuration.
            max_depth: The maximum depth to walk through the resource path.
                Defaults to ``None`` which uses the default maximum depth from
                the resource configuration.

        Returns:
            A new resource API router with the provided maximum depth.
        """
        assert issubclass(cls, BaseResource)

        # Build configuration dictionary
        config: dict[str, Any] = dict(
            prefix=f'/{cls.resource_config.slug}',
            tags=cls.resource_config.tags or [cls.resource_config.slug],
            deprecated=cls.resource_config.deprecated,
            generate_unique_id_function=lambda route: \
                generate_unique_id(route, resource=cls),
        )
        config.update(overrides)

        # Create router
        router = APIRouter(**config)

        # Evaluate maximum depth and selection
        def evaluate_setting(name: str) -> Any:
            return evaluate_config_field(
                cls.resource_config,
                name=name,
                parents=[
                    cls.resource_package.impl.settings,
                    cls.resource_package.impl.namespace.settings,
                    cls.resource_package.impl.context.settings
                        if cls.resource_package.impl.context else None,
                ],
            )
        max_depth: int = evaluate_setting('api_max_depth')
        max_selection: int = evaluate_setting('api_max_selection')

        # Walk through the resource path and collect resource endpoints
        endpoints: list[APIEndpoint[Any, Any]] = []
        root_path: ResourcePath = cls._create_path()
        for path in root_path.walk(max_depth=max_depth):
            # Retrieve target resource endpoint methods
            methods = path.target.objects._collect_methods(
                scope='endpoint',
                config=cls.resource_config.endpoints,
            )
            for method in methods.values():
                if endpoint := _create_resource_endpoint(
                    path, method, max_selection=max_selection
                ):
                    endpoints.append(endpoint)

        # Include resource endpoints in the API router
        router.include_endpoints(*endpoints, force_resolution=True)

        # Sort routes
        router.routes.sort(key=sort_key_for_routes)

        return router

    def _rebuild_adapter(
        cls,
        force: bool = False,
        raise_errors: bool = True,
    ) -> bool | None:
        """Rebuild the resource adapter.

        It rebuilds the resource adapter by updating the resource adapter with
        the current resource class and its subclasses. It is called when a
        subclass is added to the resource class hierarchy to ensure that the
        resource adapter is correctly updated.

        Args:
            force: Whether to force the rebuilding of the resource adapter even
                if the resource is not complete. Defaults to ``False``.
            raise_errors: Whether to raise errors or fail silently.
                Defaults to ``True``.

        Returns:
            Whether the resource adapter were successfully rebuilt.

        Raises:
            PlateformeError: If the resource adapter cannot be rebuilt.
        """
        # Skip if resource is not complete
        if not force and not cls.__pydantic_complete__:
            return None

        # Retrieve resource subclasses used for polymorphic identity
        resource_subclasses: tuple[ResourceType, ...] = get_subclasses(cls)

        try:
            # Update resource adapter
            adapter: TypeAdapterList[Any]
            if resource_subclasses:
                discriminated_union: type[Any] = \
                    Union[cls, *resource_subclasses]  # type: ignore
                discriminated = create_discriminated_model(
                    'Discriminated' + cls.__name__,
                    discriminator='type',
                    root=(discriminated_union, ...),
                )
                adapter = TypeAdapterList(discriminated)
            else:
                adapter = TypeAdapterList(cls)

            setattr(cls, '__pydantic_adapter__', adapter)

        except Exception as error:
            if not raise_errors:
                return False
            raise PlateformeError(
                f"Failed to rebuild resource adapter for {cls.__name__!r}.",
                code='resource-build-failed',
            ) from error

        return True

    def _rebuild_schemas(
        cls,
        *names: str,
        force: bool = False,
        raise_errors: bool = True,
        _parent_namespace_depth: int = 2,
        _types_namespace: dict[str, Any] | None = None,
    ) -> bool | None:
        """Rebuild the resource schemas information.

        It rebuilds the resource schemas by collecting and adding all the
        relative resource schema variants to the resource schema model. It is
        called when a subclass is added to the resource class hierarchy to
        ensure that the resource schemas are correctly updated.

        Args:
            *names: The names of the resource model schemas to update. If no
                names are provided, all resource model schemas are updated.
            force: Whether to force the rebuilding of the resource schemas even
                if the resource is not complete. Defaults to ``False``.
            raise_errors: Whether to raise errors or fail silently.
                Defaults to ``True``.
            _parent_namespace_depth: The depth level of the parent namespace.
                Defaults to 2.
            _types_namespace: The types namespace. Defaults to ``None``.

        Returns:
            Whether the resource schemas were successfully rebuilt.

        Raises:
            PlateformeError: If the resource schemas cannot be rebuilt.
        """
        # Retrieve resource subclasses used for polymorphic identity
        resource_subclasses: tuple[ResourceType, ...] = get_subclasses(cls)

        build_status: bool | None = None

        # Update resource schemas
        for name in names or cls.resource_schemas.keys():
            schema = cls.resource_schemas[name]

            # Retrieve and update the resource schema variants
            variants: list[ModelType] = []
            for resource in resource_subclasses:
                variant = resource.resource_schemas[name]
                variants.append(variant.get_root_base())

            if not force and not cls.__pydantic_complete__:
                continue

            schema.update_root_members(variants=variants)

            build_status = schema.model_rebuild(
                force=True,
                raise_errors=raise_errors,
                _parent_namespace_depth=_parent_namespace_depth,
                _types_namespace=_types_namespace,
            )
            if build_status is False:
                return False

        return build_status

    def _register_schema(
        cls,
        __schema_name: str,
        __schema_fallback: tuple[str, ...] | None = None,
        *,
        __force__: bool = False,
        __owner__: object | int | None = None,
        __stub__: bool | None = None,
        __doc__: str | None = None,
        __base__: ModelType | tuple[ModelType, ...] | None = None,
        __module__: str | None = None,
        __validators__: dict[str, ClassMethodType] | None = None,
        __cls_kwargs__: dict[str, Any] | None = None,
        __collect__: tuple[FieldLookup, ...] | None = None,
        **field_definitions: FieldDefinition,
    ) -> None:
        """Register a resource schema within the resource class.

        It constructs a new resource schema model based on the provided field
        definitions and lookup filters. The resource schema model is registered
        within the resource class and can be used by services to interact with
        the resource instances.

        Args:
            __schema_name: The name of the new resource schema model.
            __schema_fallback: The fallback schema aliases to use when
                resolving the resource schema model. Defaults to ``None``.
            __force__: Whether to force the registration of the resource schema
                model even if it already exists and the original owner is not
                the current resource class. Defaults to ``False``.
            __owner__: The owner object or identifier to use as the registrant
                of the new resource schema model. If an object is provided,
                the object's identifier is used. If an integer is provided, the
                integer is used. Otherwise, the caller stack context is used to
                determine the owner when available. Defaults to ``None``.
            __stub__: Whether to mark the resource schema model as a stub model
                that can accept merging with other schema models from different
                sources. When set to ``None``, the value is inferred from the
                base models if provided, i.e. if all models are stub models,
                otherwise resolves to ``True``. Defaults to ``None``.
            __doc__: The docstring of the new model.
            __base__: The base class or classes for the new model.
            __module__: The name of the module that the model belongs to.
                If ``None``, the value is retrieved from ``sys._getframe(1)``.
            __validators__: A dictionary of class methods that validate fields.
            __cls_kwargs__: A dictionary of keyword arguments for class
                creation, such as ``metaclass``.
            __collect__: The field lookup filters to collect fields from the
                resource schema model. Defaults to ``None``.
            **field_definitions: Attributes of the new model. They should be
                passed in the format: ``<name>=(<type>, <default value>)`` or
                ``<name>=(<type>, <FieldInfo>)``.

        Raises:
            PlateformeError: If the resource schema model cannot be resolved.
        """
        # Retrieve registrant identifier
        if isinstance(__owner__, int):
            registrant = __owner__
        elif __owner__ is not None:
            registrant = id(__owner__)
        elif caller_stack := CALLER_CONTEXT.get():
            registrant = caller_stack[-1]
        else:
            registrant = None

        # Validate base models
        if __base__ is None:
            __base__ = ()
        elif not isinstance(__base__, tuple):
            __base__ = (__base__,)

        # Validate stub flag
        if __stub__ is None:
            __stub__ = all(base.model_config.stub for base in __base__)

        # Validate schema
        if not __schema_name:
            raise PlateformeError(
                f"Invalid resource schema name {__schema_name!r}. The schema "
                f"name must be at least one character long."
            )
        __schema_name = __schema_name[0].upper() + __schema_name[1:]

        schema_alias = to_name_case(__schema_name)
        schema_lookup = tuple(dict.fromkeys(
            [schema_alias, *(__schema_fallback or ()), 'model']
        ))

        # Validate schema registration
        if schema_alias in cls.resource_schemas:
            schema_base = cls.resource_schemas[schema_alias]
            schema_config = schema_base.model_config
            schema_registrant = schema_base.__registrant__

            # For same registrant, merge both schema models if the provided
            # model is a stub, otherwise override the current schema model with
            # the new one.
            if schema_registrant is registrant or __force__:
                if __stub__:
                    __base__ += (schema_base,)

            # If current schema model is not a stub, skip the registration
            # silently if the provided model schema is a stub and the current
            # schema registrant is the resource class itself, otherwise raise
            # an error.
            elif not schema_config.stub:
                if __stub__ and schema_registrant == id(cls):
                    return
                raise PlateformeError(
                    f"Resource schema alias {schema_alias!r} is already "
                    f"registered and cannot be merged or overridden.",
                    code='schema-already-registered',
                )

            # If provided schema model is not a stub, override the current
            # schema model with the new one only if the provided schema
            # registrant is the resource class itself, otherwise raise an
            # error.
            elif not __stub__:
                if registrant == id(cls):
                    pass
                raise PlateformeError(
                    f"Resource schema alias {schema_alias!r} is already "
                    f"registered and cannot be merged or overridden.",
                    code='schema-already-registered',
                )

            # If both schema models are stubs, merge them together.
            else:
                __base__ += (schema_base,)

        model_name = cls.__name__ + __schema_name

        # Create schema model
        if __force__ or schema_alias not in cls.resource_schemas:
            discriminated_name = 'Discriminated' + model_name
            discriminated = create_discriminated_model(
                discriminated_name,
                __owner__=registrant,
                __cls_kwargs__={
                    '__pydantic_resource__': cls,
                    'defer_build': not cls.__pydantic_complete__,
                    'stub': __stub__,
                },
                discriminator='type',
                root=(BaseModel, ...),
            )
            cls.resource_schemas[schema_alias] = discriminated

        # Schedule schema base model creation
        cls.__state__.schedule(
            Action(
                _create_schema_base_model,
                bound=True,
                args=(
                    model_name,
                    schema_alias,
                    schema_lookup,
                ),
                kwargs={
                    '__doc__': __doc__,
                    '__base__': __base__,
                    '__module__': __module__,
                    '__validators__': __validators__,
                    '__cls_kwargs__': __cls_kwargs__,
                    '__collect__': __collect__,
                    **field_definitions,
                },
            ),
            when=Lifecycle.BUILDING,
        )

    # Hide attributes getter from type checkers to prevent MyPy from allowing
    # arbitrary attribute access instead of raising an error if the attribute
    # is not defined in the resource class.
    if not typing.TYPE_CHECKING:
        def __getattr__(cls, name: str) -> Any:
            # Redirect Pydantic and model related attributes to the resource
            # model class. This is necessary to allow the pydantic core schema
            # functionality to work with the resource model class.
            if name.startswith('__pydantic_') \
                    or name.startswith('model_'):
                model = getattr(cls, 'Model')
                return getattr(model, name)
            raise AttributeError(
                f"Resource {cls.__qualname__!r} has no attribute {name!r}."
            )

    def __setattr__(cls, name: str, value: Any) -> None:
        # Replicate SQLAlchemy behavior
        DeclarativeMeta.__setattr__(cls, name, value)
        # Check if mapper is configured and if attribute is a SQLAlchemy
        # instrumented attribute and add it to the resource attributes. This is
        # necessary for attributes defined after the class is initialized, in
        # particular for associations.
        if '__mapper__' in cls.__dict__ \
                and isinstance(value, InstrumentedAttribute):
            cls.resource_attributes[name] = value

    def __delattr__(cls, name: str) -> None:
        # Check if mapper is configured and if attribute has been set in the
        # resource attributes and remove it before deleting the attribute.
        if '__mapper__' in cls.__dict__ \
                and name in cls.resource_attributes:
            cls.resource_attributes.pop(name)
        # Replicate SQLAlchemy behavior
        DeclarativeMeta.__delattr__(cls, name)


# MARK: Base Resource

class BaseResource(
    Representation, Configurable[ResourceConfig], metaclass=ResourceMeta
):
    """Base class for all resources.

    It exposes the base class for all resources within the Plateforme
    framework. A resource owns a data model and provides a set of services to
    interact with.

    FIXME: Fix MyPy stub schema models typing.
    FIXME: Fix MyPy SQLAlchemy instrumented attributes typing.

    Attributes:
        __config__: The configuration class setter for the resource.
        __config_services__: The services configured for the resource.
        __config_specs__: The specifications applied to the resource.

        __manager__: The resource manager used to access and manage the service
            methods associated with the resource class.
        __state__: The resource state used to manage the resource lifecycle
            operations, such as creating, initializing, and building the
            resource class and its dependencies. Additionally, it is used to
            manage the tasks needed to complete the resource class building
            process.
        __tablename__: The name of the table in the database.
        __table_args__: The arguments for the table in the database.
        __mapper_args__: The arguments for the mapper in the database.

        _sa_class_manager: The SQLAlchemy class manager of the resource.
        _sa_instance_state: The SQLAlchemy instance state of the resource used
            for ORM operations.
        _sa_registry: The SQLAlchemy registry of the resource. It is handled
            dynamically by the Plateforme application.

        __class_vars__: The names of classvars defined on the model.
        __private_attributes__: Metadata about the private attributes of the
            model.
        __signature__: The signature for instantiating the model.

        __pydantic_complete__: Whether resource model building is completed, or
            if there are still undefined fields.
        __pydantic_validated__: Whether the resource model has been validated
            or directly constructed.
        __pydantic_core_schema__: The pydantic-core schema used to build the
            `SchemaValidator` and `SchemaSerializer`.
        __pydantic_model_schema__: The pydantic-core schema used to build the
            underlying resource model.
        __pydantic_custom_init__: Whether the resource model has a custom
            `__init__` function.
        __pydantic_decorators__: Metadata containing the decorators defined on
            the resource model.
        __pydantic_generic_metadata__: Metadata for generic resource models, it
            contains data used for a similar purpose to `__args__`,
            `__origin__`, and `__parameters__` in typing-module generics. May
            eventually be replaced by these.
        __pydantic_parent_namespace__: Parent namespace of the resource model,
            used for automatic rebuilding of resource models.
        __pydantic_post_init__: The name of the post-init method for the
            resource model, if defined.
        __pydantic_root_model__: Whether the resource model is an
            implementation of the `RootModel` class.
        __pydantic_adapter__: The pydantic `TypeAdapterList` used to validate
            and serialize collections of instances of the resource model.
        __pydantic_serializer__: The pydantic-core `SchemaSerializer` used to
            dump instances of the resource model.
        __pydantic_validator__: The pydantic-core `SchemaValidator` used to
            validate instances of the resource model.
        __pydantic_extra__: An instance attribute with the values of extra
            fields from validation when `resource_config['extra'] == 'allow'`.
        __pydantic_fields_set__: An instance attribute with the names of fields
            explicitly set.
        __pydantic_private__: Instance attribute with the values of private
            attributes set on the resource model instance.
    """
    if typing.TYPE_CHECKING:
        __config__: ClassVar[ResourceConfig | ResourceConfigDict]
        __config_services__: ClassVar[tuple[BaseService, ...]]
        __config_specs__: ClassVar[tuple[SpecType, ...]]
        __pydantic_adapter__: ClassVar[TypeAdapterList['BaseResource']]
        __pydantic_complete__: ClassVar[bool]
        __pydantic_model_schema__: ClassVar[CoreSchema]
        __pydantic_post_init__: ClassVar[None | Literal['resource_post_init']]
        __tablename__: ClassVar[str | None]
        __table_args__: ClassVar[Any]
        __mapper_args__: ClassVar[Any]
        _sa_class_manager: ClassVar[ClassManager[Self]]
        _sa_registry: ClassVar[Registry]
        resource_attributes: ClassVar[dict[str, InstrumentedAttribute[Any]]]
        resource_config: ClassVar[ResourceConfig]
        resource_identifiers: ClassVar[tuple[set[str], ...]]
        resource_indexes: ClassVar[tuple[set[str], ...]]
        resource_package: ClassVar['Package']
        resource_schemas: ClassVar[dict[str, DiscriminatedModelType]]

        # Model schema
        Model: ClassVar[ModelType]

        # The non-existent keyword argument "init=False" is used below so that
        # "@dataclass_transform" doesn't pass these attributes as valid
        # keyword arguments to the class initializer.
        _sa_instance_state: InstanceState[Self] = \
            Field(init=False, repr=False)

        resource_model: BaseModel = Field(init=False, repr=False)

    # Set declarative abstraction
    __abstract__ = True

    # Set resource attributes
    __config__ = ResourceConfig()
    resource_model = Deferred
    resource_package = Deferred

    # Weakref support is necessary to allow garbage collection of resources
    # within the Plateforme framework, and is also required by SQLAlchemy.
    # It is not necessary to define the "__weakref__" attribute here as it is
    # already defined in the configurable class.
    __slots__ = ()

    # Base resource fields
    id: int | UUID4 | None = Field(
        default=Deferred,
        validate_default=False,
        title='ID',
        description='Resource identifier',
        frozen=True,
    )
    type_: str = Field(
        default=Deferred,
        validate_default=False,
        alias='type',
        validation_alias=AliasChoices('type', 'type_'),
        title='Type',
        description='Resource polymorphic type',
        init=False,
        frozen=True,
    )

    if typing.TYPE_CHECKING:
        def __init_subclass__(
            cls, **kwargs: Unpack[ResourceConfigDict]
        ) -> None:
            """Expose to type checkers the resource configuration class.

            This signature is included purely to help type-checkers check
            arguments to class declaration, which provides a way to
            conveniently set resource configuration key/value pairs.

            Examples:
                >>> class MyResource(BaseResource, alias='my-resource'):
                ...     pass
            """

    def __new__(
        cls,
        __model: BaseModel | None = None,
        __context: dict[str, Any] | None = None,
        /,
        **data: Any,
    ) -> Self:
        """Create a new resource instance.

        It creates a new resource instance by parsing and validating input data
        from the `data` keyword arguments or by using an existing model
        instance.

        Args:
            __model: The model instance to use to create the resource instance.
            __context: The context dictionary to use to initialize the resource
                instance. It is passed to the post-init method.
            **data: The input data to initialize the resource instance if no
                model instance is provided. Note that ``cls`` is explicitly
                positional-only to allow a same-named field to be defined in
                the resource model.

        Returns:
            A new resource instance.

        Raises:
            TypeError: If the resource class is directly instantiated or if the
                provided model instance is not of the expected type.
            ValueError: If both a model and data are provided.
            PlateformeError: If the resource instance could not be initialized
                from the provided input data.
        """
        # Check if class is directly instantiated
        if cls is BaseResource:
            raise TypeError(
                "Plateforme base resource cannot be directly instantiated."
            )

        # Check if underlying model is provided and valid
        if __model is not None:
            if not isinstance(__model, cls.Model):
                raise TypeError(
                    f"Cannot create a resource instance with a model instance "
                    f"of type {__model.__class__.__qualname__!r}. Expected "
                    f"model instance of type {cls.Model.__qualname__!r}."
                )
            if data:
                raise ValueError(
                    f"Cannot create a resource instance with both a model and "
                    f"data provided. Either provide a model instance or data "
                    f"to create a new resource instance. Got: model "
                    f"{__model.__class__.__qualname__!r} and data {data!r}."
                )

        # Check resource status
        if cls.__state__.status != Lifecycle.READY:
            raise PlateformeError(
                f"Failed to initialize resource {cls.__qualname__!r}. The "
                f"resource is not built and cannot be instantiated.",
                code='resource-initalization-failed',
            )

        # Create new resource instance
        self = super().__new__(cls)

        # Handle the proxying of the resource instance data to the resource
        # model instance. This is necessary as SQLAlchemy omits the invocation
        # of "__init__" on the base class and sets the fields data directly on
        # the instance dictionary when querying from the database. This
        # instance dictionary intercepts the data access and sets the data on
        # the resource model instance.
        resource_model = __model or self.Model.model_construct()

        # Set resource dictionary and model instance
        resource_dict = ResourceDict(resource_model, **self.__dict__)
        object.__setattr__(self, '__dict__', resource_dict)
        object.__setattr__(self, 'resource_model', resource_model)

        return self

    def __init__(
        self,
        __model: BaseModel | None = None,
        __context: dict[str, Any] | None = None,
        /,
        **data: Any,
    ) -> None:
        """Initialize a resource instance.

        It initializes a resource instance by parsing and validating input data
        from the `data` keyword arguments.

        Args:
            __model: The model instance to use to create the resource instance.
                This lets the resource instance be created with an existing
                model instance within the `__new__` method. It is ignored here.
            __context: The context dictionary to use to initialize the resource
                instance. It is passed to the post-init method.
            **data: The input data to initialize the resource instance if no
                model instance is provided. Note that ``self`` is explicitly
                positional-only to allow a same-named field to be defined in
                the resource model.

        Note:
            The mangled arguments are injected by SQLAlchemy internal behavior
            within the keyword arguments. Hence, they need to be parsed and
            removed from the data dictionary before initializing the resource
            instance.

            The validation can be strictly enforced or skipped using the
            validation context manager `validation_manager` defined in the
            schema core module. This can be necessary to allow the resource to
            be initialized with an already validated model instance and avoid
            triggering the Pydantic validation logic.

            When a resource is created directly by SQLAlchemy, while querying
            the database for instance, the `__init__` method is not called and
            the data is set directly on the model instance without validation.

        Raises:
            PlateformeError: If the resource instance could not be initialized
                from the provided input data. For instance, if the input data
                is invalid and raises a `ValidationError`.
            AttributeError: If an attribute is not an instrumented attribute of
                the resource instance while it is defined as a model field.
        """
        # Tell pytest to hide this function from tracebacks
        __tracebackhide__ = True

        # Store and clean up mangled arguments from the data dictionary. This
        # is necessary to avoid SQLAlchemy from populating the model instance
        # with the mangled attributes.
        mangling_prefix = f'_{BaseResource.__name__}'
        __model = data.pop(f'{mangling_prefix}__model', __model)
        __context = data.pop(f'{mangling_prefix}__context', __context)

        # Retrieve validation mode
        validation_mode = VALIDATION_CONTEXT.get()

        # Retrieve resource model
        model = self.resource_model

        # Validate input data if validation mode is not disabled. There are
        # scenarios where the resource is partially initialized by SQLAlchemy
        # from a database query with data already validated. In this case, the
        # data is set directly on the model instance without triggering any
        # Pydantic validation logic.
        if validation_mode != ValidationMode.DISABLED:
            # Merge initial dictionary with data
            model_dict = {
                **model.model_dump(
                    exclude=set(model.model_computed_fields),
                    exclude_unset=True,
                ),
                **data,
            }
            strict = True if validation_mode == ValidationMode.STRICT \
                else False
            try:
                model.__pydantic_validator__.validate_python(
                    model_dict,
                    strict=strict,
                    context=__context,
                    self_instance=model,
                )
            except Exception as error:
                raise PlateformeError(
                    f"Failed to initialize resource "
                    f"{self.__class__.__qualname__!r}.",
                    code='resource-initalization-failed',
                ) from error

        # Call post-init method if defined
        if self.__pydantic_post_init__:
            self.resource_post_init(__context)
            # Update private attributes with values set
            if hasattr(model, '__pydantic_private__') \
                    and model.__pydantic_private__ is not None:
                for key, value in data.items():
                    if key not in model.__private_attributes__:
                        continue
                    model.__pydantic_private__[key] = value

        # Copy and replace the model instance dictionary so that SQLAlchemy can
        # track the changes made to the model instance fields.
        model_dict = model.__dict__.copy()
        object.__setattr__(model, '__dict__', {})
        # Set instrumented attributes for populated model instance fields to
        # trigger SQLAlchemy history tracking of events and updates.
        for key, value in model_dict.items():
            # Skip dunders attributes
            if key.startswith('__') and key.endswith('__'):
                continue
            # Skip deferred attributes
            if value is Deferred:
                continue
            if is_instrumented(self, key):  # type: ignore[no-untyped-call]
                set_instrumented_value(self, key, value)
            else:
                model.__dict__[key] = value

    @classproperty
    def resource_adapter(cls) -> TypeAdapterList['BaseResource']:
        """Get the resource type adapter.

        Returns:
            The resource type adapter used to validate and serialize instances
            of the resource model.
        """
        if not hasattr(cls, '__pydantic_adapter__'):
            raise AttributeError(
                "The resource type adapter is not defined. This may be due to "
                "the resource not being fully built or an error occurred "
                "during resource construction."
            )
        return cls.__pydantic_adapter__

    @classproperty
    def resource_computed_fields(cls) -> dict[str, ComputedFieldInfo]:
        """Get computed fields defined on this resource class.

        Returns:
            A metadata dictionary of computed field names and their
            corresponding `ComputedFieldInfo` objects.
        """
        return cls.Model.model_computed_fields

    @classproperty
    def resource_fields(cls) -> dict[str, ResourceFieldInfo]:
        """Get fields defined on this resource class.

        Returns:
            A metadata dictionary of field names and their corresponding
            `FieldInfo` objects.
        """
        return cls.Model.model_fields  # type: ignore[return-value]

    @classproperty
    def resource_path(cls) -> str:
        """Get the resource API route path."""
        return f'{cls.resource_package.impl.path}/{cls.resource_config.slug}'

    @property
    def resource_extra(self) -> dict[str, Any] | None:
        """Get extra fields set during validation on this resource instance.

        Returns:
            A dictionary of extra fields, or ``None`` if
            `resource_config.extra` is not set to ``"allow"``.
        """
        return self.resource_model.model_extra

    @property
    def resource_fields_set(self) -> set[str]:
        """Get fields that have been explicitly set on this resource instance.

        Returns:
            A set of strings representing the fields that have been set,
            i.e. that were not filled from defaults.
        """
        return self.resource_model.model_fields_set

    async def resource_add(
        self, *, session: AsyncSession | None = None
    ) -> None:
        """Add the resource instance to the database.

        It places an object into the current `AsyncSession`.

        Objects that are in the ``transient`` state when passed to the
        `session.add` method will move to the ``pending`` state, until the next
        flush, at which point they will move to the ``persistent`` state.

        Objects that are in the ``detached`` state when passed to the
        `session.add` method will move to the ``persistent`` state directly.

        If the transaction used by the `AsyncSession` is rolled back, objects
        which were transient when they were passed to `session.add` will be
        moved back to the ``transient`` state, and will no longer be present
        within this `AsyncSession`.

        Args:
            session: The session to use for the operation. If not provided, the
                session in the current context is used.
                Defaults to ``None``.

        Raises:
            PlateformeError: If the resource instance could not be added to the
                database.
        """
        try:
            if session:
                session.add(self)
                return
            async with async_session_manager(on_missing='raise') as session:
                session.add(self)
        except Exception as error:
            raise PlateformeError(
                f"Failed to add resource {self!r} to the database.",
                code='resource-add-failed',
            ) from error

    @classmethod
    def resource_construct(
        cls: type[Resource],
        _fields_set: set[str] | None = None,
        _model: BaseModel | None = None,
        **data: Any,
    ) -> Resource:
        """Creates a new instance of the resource class with validated data.

        Creates a new resource setting underlying model `__dict__` and
        `__pydantic_fields_set__` from trusted or pre-validated data. Default
        values are respected, but no other validation is performed. It behaves
        as if `resource_config.extra = 'allow'` was set since it adds all
        passed values.

        Args:
            _fields_set: The set of field names accepted by the resource
                instance.
            _model: The model instance to use to create the resource instance.
                If not provided, a new model instance is created.
            **data: Trusted or pre-validated input data to initialize the
                resource. It is used to set the `__dict__` attribute of the
                underlying model. If a model instance is provided, the data is
                merged with the existing model data.

        Returns:
            A new instance of the resource class with validated data.
        """
        # Retrieve the model instance from the provided model and data
        if _model is None:
            model = cls.Model.model_construct(_fields_set, **data)
        elif data:
            model = cls.Model.model_construct(
                _fields_set, **_model.model_dump(), **data
            )
        else:
            model = _model

        # Return a new resource instance without triggering validation
        with validation_manager(mode='disabled'):
            return cls(model)

    def resource_copy(
        self: Resource,
        *,
        update: dict[str, Any] | None = None,
        deep: bool = False,
    ) -> Resource:
        """Returns a copy of the resource.

        Args:
            update: Values to add/modify within the resource. Note that if
                assignment validation is not set to ``True``, the integrity of
                the data is not validated when updating the resource. Data
                should be trusted or pre-validated in this case.
                Defaults to ``None``.
            deep: Set to ``True`` to make a deep copy of the model.

        Returns:
            A new copy of the model instance with the updated values.
        """
        # Copy the model instance
        model = self.resource_model.model_copy(update=update, deep=deep)

        # Return a new resource instance without triggering validation
        cls = self.__class__
        with validation_manager(mode='disabled'):
            return cls(model)

    async def resource_delete(
        self, *, session: AsyncSession | None = None,
    ) -> None:
        """Delete the resource instance from the database.

        It marks an instance as deleted.

        The object is assumed to be either ``persistent`` or ``detached`` when
        passed; after the method is called, the object will remain in the
        ``persistent`` state until the next flush proceeds. During this time,
        the object will also be a member of the `session.deleted` collection.

        When the next flush proceeds, the object will move to the ``deleted``
        state, indicating a ``DELETE`` statement was emitted for its row within
        the current transaction. When the transaction is successfully
        committed, the deleted object is moved to the ``detached`` state and is
        no longer present within this `AsyncSession`.

        Args:
            session: The session to use for the operation. If not provided, the
                session in the current context is used.
                Defaults to ``None``.

        Raises:
            PlateformeError: If the resource instance could not be deleted from
                the database.
        """
        try:
            if session:
                await session.delete(self)
                return
            async with async_session_manager(on_missing='raise') as session:
                await session.delete(self)
        except Exception as error:
            raise PlateformeError(
                f"Failed to delete resource {self!r} from the database.",
                code='resource-delete-failed',
            ) from error

    def resource_dump(
        self,
        *,
        mode: Literal['json', 'python', 'raw'] | str = 'python',
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool = True,
    ) -> dict[str, Any]:
        """Generate a dictionary representation of the resource.

        It is used to dump the resource instance to a dictionary representation
        of the resource, optionally specifying which fields to include or
        exclude.

        Args:
            mode: The mode in which `to_python` should run:
                - If mode is ``json``, the output will only contain JSON
                    serializable types.
                - If mode is ``python``, the output may contain non JSON
                    serializable Python objects.
                - If mode is ``raw``, the output will contain raw values.
                Defaults to ``python``.
            include: A list of fields to include in the output.
                Defaults to ``None``.
            exclude: A list of fields to exclude from the output.
                Defaults to ``None``.
            by_alias: Whether to use the field's alias in the dictionary key if
                defined. Defaults to ``False``.
            exclude_unset: Whether to exclude fields that have not been
                explicitly set. Defaults to ``False``.
            exclude_defaults: Whether to exclude fields that are set to their
                default value. Defaults to ``False``.
            exclude_none: Whether to exclude fields that have a value of
                ``None``. Defaults to ``False``.
            round_trip: If ``True``, dumped values should be valid as input for
                non-idempotent types such as `Json[T]`. Defaults to ``False``.
            warnings: Whether to log warnings when invalid fields are
                encountered. Defaults to ``True``.

        Returns:
            A dictionary representation of the resource.
        """
        return self.resource_model.model_dump(
            mode=mode,
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
        )

    def resource_dump_json(
        self,
        *,
        indent: int | None = None,
        include: IncEx | None = None,
        exclude: IncEx | None = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool = True,
    ) -> str:
        """Generate a JSON representation of the resource.

        It is used to dump the resource instance to a JSON representation of
        the resource using Pydantic's `to_json` method, optionally specifying
        which fields to include or exclude.

        Args:
            indent: Indentation to use in the JSON output. If ``None`` is
                passed, the output will be compact. Defaults to ``None``.
            include: A list of fields to include in the JSON output.
                Defaults to ``None``.
            exclude: A list of fields to exclude from the JSON output.
                Defaults to ``None``.
            by_alias: Whether to use the field's alias in the dictionary key if
                defined. Defaults to ``False``.
            exclude_unset: Whether to exclude fields that have not been
                explicitly set. Defaults to ``False``.
            exclude_defaults: Whether to exclude fields that are set to their
                default value. Defaults to ``False``.
            exclude_none: Whether to exclude fields that have a value of
                ``None``. Defaults to ``False``.
            round_trip: If ``True``, dumped values should be valid as input for
                non-idempotent types such as `Json[T]`. Defaults to ``False``.
            warnings: Whether to log warnings when invalid fields are
                encountered. Defaults to ``True``.

        Returns:
            A JSON string representation of the resource.
        """
        return self.resource_model.model_dump_json(
            indent=indent,
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
        )

    @classmethod
    def resource_json_schema(
        cls,
        by_alias: bool = True,
        ref_template: str = DEFAULT_REF_TEMPLATE,
        schema_generator: type[GenerateJsonSchema] = GenerateJsonSchema,
        mode: JsonSchemaMode = 'validation',
        source: JsonSchemaSource = 'key',
    ) -> dict[str, Any]:
        """Generates a JSON schema for a resource class.

        Args:
            by_alias: Whether to use field aliases when generating the schema,
                i.e. if ``True``, fields will be serialized according to their
                alias, otherwise according to their attribute name.
                Defaults to ``True``.
            ref_template: The template format string used when generating
                reference names. Defaults to ``DEFAULT_REF_TEMPLATE``.
            schema_generator: The class to use for generating the JSON Schema.
            mode: The mode to use for generating the JSON Schema. It can be
                either ``validation`` or ``serialization`` where respectively
                the schema is generated for validating data or serializing
                data. Defaults to ``validation``.
            source: The source type to use for generating the resources JSON
                schema. It can be either ``key`` , ``model``, or ``both`` where
                the latter accepts, when applicable, integer and string values
                for key identifiers in addition to the standard model schema
                generation. Defaults to ``key``.

        Returns:
            The generated JSON schema of the resource class.

        Note:
            The schema generator class can be overridden to customize the
            logic used to generate the JSON schema. This can be done by
            subclassing the `GenerateJsonSchema` class and passing the subclass
            as the `schema_generator` argument.
        """
        return cls.Model.model_json_schema(
            by_alias=by_alias,
            ref_template=ref_template,
            schema_generator=schema_generator,
            mode=mode,
            source=source,
        )

    def resource_keychain(self) -> tuple[Key[Self], ...]:
        """Collect all keys set on the resource instance."""
        keychain: tuple[Key[Self], ...] = ()

        for identifier in self.resource_identifiers:
            assignments = {
                field_alias: getattr(self, field_alias)
                for field_alias in identifier
            }
            key = Key.validate(
                assignments,
                resource=self.__class__,
                validate_assignment=False,
            )
            keychain += (key,)

        return keychain

    async def resource_merge(
        self: Resource,
        *,
        load: bool = True,
        options: Sequence[ORMOption] | None = None,
        session: AsyncSession | None = None,
    ) -> Resource:
        """Merge the resource instance with the database.

        It copies the state of the resource instance into a corresponding
        instance in the database within the current `AsyncSession`.

        First, it examines the primary key attributes if available, otherwise
        the resource identifier keychain, and attempts to reconcile it with an
        instance of the same identifier in the session. If not found locally,
        it attempts to load the object from the database based on the
        identifier, and if none can be located, creates a new instance in the
        session. The state of each attribute on the source instance is then
        copied to the target instance. The resulting target instance is then
        returned by the `resource_merge` method; the original source instance
        is left unmodified, and un-associated with the `AsyncSession` if not
        already.

        This operation cascades to associated instances if the association is
        mapped with ``cascade='merge'``.

        Args:
            load: Whether to load the resource instance from the database if
                not found in the session. Defaults to ``True``.

                When ``False``, the method switches into a "high performance"
                mode which causes it to forego emitting history events as well
                as all database access. This flag is used for cases such as
                transferring graphs of objects into an `AsyncSession` from a
                second level cache, or to transfer just-loaded objects into the
                `AsyncSession` owned by a worker thread or process without
                re-querying the database.

                The ``load=False`` use case adds the caveat that the given
                object has to be in a "clean" state, that is, has no pending
                changes to be flushed - even if the incoming object is detached
                from any `AsyncSession`. This is so that when the merge
                operation populates local attributes and cascades to related
                objects and collections, the values can be "stamped" onto the
                target object as is, without generating any history or
                attribute events, and without the need to reconcile the
                incoming data with any existing related objects or collections
                that might not be loaded. The resulting objects from
                ``load=False`` are always produced as "clean", so it is only
                appropriate that the given objects should be "clean" as well,
                else this suggests a mis-use of the method.
            options: Optional sequence of loader options which will be applied
                to the `session.get` method when the merge operation loads the
                existing version of the object from the database.
            session: The session to use for the operation. If not provided, the
                session in the current context is used.
                Defaults to ``None``.

        Returns:
            The merged resource instance.
        """
        try:
            if session:
                return await session.merge(self, load=load, options=options)
            async with async_session_manager(on_missing='raise') as session:
                return await session.merge(self, load=load, options=options)
        except Exception as error:
            raise PlateformeError(
                f"Failed to merge resource {self!r} within the "
                f"database.",
                code='resource-merge-failed',
            ) from error

    @classmethod
    def resource_parametrized_name(cls, params: tuple[type[Any], ...]) -> str:
        """Compute the class name for parametrizations of generic classes.

        This method can be overridden to achieve a custom naming scheme for
        generic Base resopurces.

        Args:
            params: Tuple of types of the class. Given a generic class
                `Resource` with 2 type variables and a concrete resource
                `Resource[str, int]`, the value ``(str, int)`` would be passed
                to `params`.

        Returns:
            String representing the new class where `params` are passed to
            `cls` as type variables.

        Raises:
            TypeError: Raised when trying to generate concrete names for
                non-generic resources.
        """
        if not issubclass(cls, Generic):  # type: ignore[arg-type]
            raise TypeError(
                "Concrete names should only be generated for generic "
                "resources."
            )
        return cls.Model.model_parametrized_name(params)

    def resource_post_init(
        self, __context: dict[str, Any] | None = None
    ) -> None:
        """Post-initialization method for the resource class.

        Override this method to perform additional initialization after the
        `__init__` and `resource_construct` methods have been called. This is
        useful in scenarios where it is necessary to perform additional
        initialization steps after the resource has been fully initialized.

        Args:
            __context: The context object passed to the resource instance.
        """
        ...

    @classmethod
    def resource_rebuild(
        cls,
        *,
        force: bool = False,
        raise_errors: bool = True,
        _parent_namespace_depth: int = 2,
        _types_namespace: dict[str, Any] | None = None,
    ) -> bool | None:
        """Rebuild the pydantic-core schema for the resource.

        This may be necessary when one of the annotations is a `ForwardRef`
        which could not be resolved during the initial attempt to build the
        schema, and automatic rebuilding fails.

        Args:
            force: Whether to force the rebuilding of the resource schema.
                Defaults to ``False``.
            raise_errors: Whether to raise errors or fail silently.
                Defaults to ``True``.
            _parent_namespace_depth: The depth level of the parent namespace.
                Defaults to 2.
            _types_namespace: The types namespace. Defaults to ``None``.

        Raises:
            PlateformeError: If the resource adapter or schema could not be
                rebuilt and `raise_errors` is set to ``True``.
            PydanticUndefinedAnnotation: If `PydanticUndefinedAnnotation`
                occurs in`__get_pydantic_core_schema__` and `raise_errors` is
                set to ``True``.

        Returns:
            Returns ``None`` if the schema is already "complete" and rebuilding
            was not required. If rebuilding was required, returns ``True`` if
            rebuilding was successful, otherwise ``False`` if an error
            occurred and `raise_errors` is set to ``False``.
        """
        build_status = None

        # Rebuild resource model
        build_status = cls.Model.model_rebuild(
            force=force,
            raise_errors=raise_errors,
            _parent_namespace_depth=_parent_namespace_depth,
            _types_namespace=_types_namespace,
        )

        # Rebuild resource schema
        if build_status:
            build_status = cls._rebuild_schemas(
                raise_errors=raise_errors,
                _parent_namespace_depth=_parent_namespace_depth,
                _types_namespace=_types_namespace,
            )

        # Rebuild resource adapter
        if build_status:
            build_status = cls._rebuild_adapter(raise_errors=raise_errors)

        return build_status

    def resource_revalidate(
        self,
        *,
        force: bool = False,
        raise_errors: bool = True,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> bool | None:
        """Revalidate the resource instance.

        It revalidates the resource instance in place, enforcing the types
        strictly if specified. If the resource instance has already been
        validated, it will not be revalidated unless the `force` argument is
        set to ``True``.

        Args:
            force: Whether to force the revalidation of the resource instance.
                Defaults to ``False``.
            raise_errors: Whether to raise errors or fail silently.
                Defaults to ``True``.
            strict: Whether to enforce types strictly.
            context: Extra variables to pass to the validator.

        Raises:
            ValidationError: If the resource instance could not be validated
                and `raise_errors` is set to ``True``.

        Returns:
            Returns ``None`` if the resource instance is already "validated"
            and revalidation was not required. If validation was required,
            returns ``True`` if validation was successful, otherwise ``False``
            if an error occurred and `raise_errors` is set to ``False``.
        """
        return self.resource_model.model_revalidate(
            force=force,
            raise_errors=raise_errors,
            strict=strict,
            context=context,
        )

    def resource_update(
        self,
        obj: Any,
        *,
        update: dict[str, Any] | None = None,
        from_attributes: bool | None = None,
    ) -> None:
        """Update the resource with the given object and update dictionary.

        Args:
            obj: The object to update the resource with. It can be a dictionary
                or an object with attributes (if `from_attributes` is set to
                ``True``). If it is a dictionary, the keys must match the
                resource field names if extra fields are not allowed.
            update: Values to add/modify within the resource. Note that if
                assignment validation is not set to ``True``, the integrity of
                the data is not validated when updating the resource. Data
                should be trusted or pre-validated in this case.
                Defaults to ``None``.
            from_attributes: Whether to extract data from object attributes.
                Defaults to ``None``.

        Raises:
            ValidationError: If the object could not be validated.
            ValueError: If `strict` or `context` are set when
                `validate_assignment` is set to ``False``.
        """
        # Collect update
        update = (update or {}).copy()
        if from_attributes:
            for field_name in self.resource_fields:
                if hasattr(obj, field_name):
                    update.setdefault(field_name, getattr(obj, field_name))
        elif isinstance(obj, dict):
            update = {**obj, **update}

        # Process update
        for key, value in update.items():
            setattr(self, key, value)

    @classmethod
    def resource_validate(
        cls: type[Resource],
        obj: Any,
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> Resource:
        """Validate the given object against the resource.

        It validates the provided object against the resource model and returns
        the validated resource instance. The validation can be strictly
        enforced or skipped using the `strict` argument. The data can be
        extracted from the object attributes using the `from_attributes`
        argument. Additional context can be passed to the validator using the
        `context` argument.

        Args:
            obj: The object to validate.
            strict: Whether to enforce types strictly.
            from_attributes: Whether to extract data from the object
                attributes.
            context: Extra variables to pass to the validator.

        Returns:
            A validated resource instance.

        Raises:
            ValidationError: If the object could not be validated.
        """
        # Validate a new model instance from the provided object
        model = cls.Model.model_validate(
            obj,
            strict=strict,
            from_attributes=from_attributes,
            context=context,
        )

        # Return a new resource instance without triggering validation
        with validation_manager(mode='disabled'):
            return cls(model, context)

    @classmethod
    def resource_validate_many(
        cls: type[Resource],
        obj: Any,
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> Sequence[Resource]:
        """Validate the given object collection against the resource.

        It validates the provided object collection against the resource model
        and returns the validated resource instances. The validation can be
        strictly enforced or skipped using the `strict` argument. The data can
        be extracted from the object items attributes using the
        `from_attributes` argument. Additional context can be passed to the
        validator using the `context` argument.

        Args:
            obj: The object collection to validate.
            strict: Whether to enforce types strictly.
            from_attributes: Whether to extract data from the object
                collection items attributes.
            context: Extra variables to pass to the validator.

        Returns:
            A validated collection of resource instances.

        Raises:
            ValidationError: If the object collection could not be validated.
        """
        # Tell pytest to hide this function from tracebacks
        __tracebackhide__ = True

        return cls.resource_adapter.validate_python(  # type: ignore
            obj,
            strict=strict,
            from_attributes=from_attributes,
            context=context,
        )

    @classmethod
    def resource_validate_json(
        cls: type[Resource],
        json_data: str | bytes | bytearray,
        *,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> Resource:
        """Validate the given JSON data against the resource.

        Args:
            json_data: The JSON data to validate.
            strict: Whether to enforce types strictly.
            context: Extra variables to pass to the validator.

        Returns:
            A validated resource instance.

        Raises:
            ValueError: If `json_data` is not a JSON string.
            ValidationError: If the object could not be validated.
        """
        # Validate a new resource instance from the provided data
        model = cls.Model.model_validate_json(
            json_data, strict=strict, context=context
        )

        # Return a new resource instance without triggering validation
        with validation_manager(mode='disabled'):
            return cls(model, context)

    @classmethod
    def resource_validate_json_many(
        cls: type[Resource],
        json_data: str | bytes | bytearray,
        *,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> Sequence[Resource]:
        """Validate the given JSON data collection against the resource.

        Args:
            json_data: The JSON data collection to validate.
            strict: Whether to enforce types strictly.
            context: Extra variables to pass to the validator.

        Returns:
            A validated collection of resource instances.

        Raises:
            ValueError: If `json_data` is not a JSON string.
            ValidationError: If the object collection could not be validated.
        """
        # Tell pytest to hide this function from tracebacks
        __tracebackhide__ = True

        return cls.resource_adapter.validate_json(  # type: ignore
            json_data, strict=strict, context=context
        )

    @classmethod
    def resource_validate_strings(
        cls: type[Resource],
        obj: Any,
        *,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> Resource:
        """Validate the given string object against the resource.

        Args:
            obj: The string object to validate.
            strict: Whether to enforce types strictly.
            context: Extra variables to pass to the validator.

        Returns:
            A validated resource instance.

        Raises:
            ValidationError: If the object could not be validated.
        """
        # Validate a new resource instance from the provided string object
        model = cls.Model.model_validate_strings(
            obj, strict=strict, context=context
        )

        # Return a new resource instance without triggering validation
        with validation_manager(mode='disabled'):
            return cls(model, context)

    @classmethod
    def resource_validate_strings_many(
        cls: type[Resource],
        obj: Any,
        *,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> Sequence[Resource]:
        """Validate the given string object collection against the resource.

        Args:
            obj: The string object collection to validate.
            strict: Whether to enforce types strictly.
            context: Extra variables to pass to the validator.

        Returns:
            A validated collection of resource instances.

        Raises:
            ValidationError: If the object collection could not be validated.
        """
        # Tell pytest to hide this function from tracebacks
        __tracebackhide__ = True

        return cls.resource_adapter.validate_strings(  # type: ignore
            obj, strict=strict, context=context
        )

    @classmethod
    def __get_pydantic_core_schema__(
        cls: type[Resource],
        __source: ResourceType,
        __handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Hook into generating the resource's core schema.

        Args:
            __source: The class that the core schema is being generated for.
                This argument is ignored for resources as it is the underlying
                model source class ``cls.Model`` that is used to generate the
                core schema.
            __handler: Call into Pydantic's internal core schema generation.

        Returns:
            A `pydantic-core` core schema.
        """
        # Handle key validation
        def validate_key(obj: int | str) -> Key[Resource]:
            return Key.validate(obj, resource=cls, validate_assignment=True)

        # Build key schema
        key_schema = core_schema.no_info_after_validator_function(
            validate_key,
            core_schema.union_schema([
                core_schema.int_schema(),
                core_schema.str_schema(),
            ])
        )

        # Build model schema
        model_schema = __handler.generate_schema(cls.Model)

        # Build json schema
        json_schema = core_schema.no_info_after_validator_function(
            cls.__pydantic_after_validator__,
            core_schema.union_schema([
                key_schema,
                model_schema,
            ]),
        )

        # Build python schema
        python_schema = core_schema.chain_schema([
            # Root schema
            core_schema.union_schema([
                core_schema.no_info_after_validator_function(
                    lambda obj: getattr(obj, 'root'),
                    core_schema.is_instance_schema(RootModel),
                ),
                core_schema.any_schema(),
            ]),
            # Validation schema
            core_schema.union_schema([
                core_schema.is_instance_schema(cls),
                core_schema.no_info_after_validator_function(
                    cls.__pydantic_after_validator__,
                    core_schema.union_schema([
                        core_schema.is_instance_schema(Key),
                        key_schema,
                        model_schema,
                    ]),
                ),
            ]),
        ])

        # Build schema
        schema = core_schema.json_or_python_schema(
            json_schema,
            python_schema,
            serialization=core_schema.wrap_serializer_function_ser_schema(
                lambda obj, _: getattr(obj, 'resource_model'),
                is_field_serializer=False,
                info_arg=False,
                return_schema=model_schema,
            ),
        )

        # Set resource model schema
        setattr(cls, '__pydantic_model_schema__', model_schema)

        return schema

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        __core_schema: CoreSchema,
        __handler: GetJsonSchemaHandler,
    ) -> JsonSchemaDict:
        """Hook into generating the resource's JSON schema.

        Args:
            __core_schema: A ``pydantic-core`` core schema. You can ignore this
                argument and call the handler with a new core schema, wrap this
                core schema ``{'type': 'nullable', 'schema': current_schema}``,
                or just call the handler with the original schema.
            __handler: Call into Pydantic's internal JSON schema generation.
                This will raise a `PydanticInvalidForJsonSchema` if JSON schema
                generation fails. Since this gets called by
                `BaseResource.resource_json_schema` you can override the
                `schema_generator` argument to that function to change JSON
                schema generation globally for a type.

        Returns:
            A JSON schema (as a python dictionary)
        """
        # Retrieve the JSON schema generator from the handler
        schema_generator = getattr(__handler, 'generate_json_schema', None)
        if schema_generator is None:
            raise PlateformeError(
                "Invalid JSON schema generator for resource "
                f"{cls.__qualname__!r}. The JSON schema generator must be an "
                "instance of the `GenerateJsonSchema` class.",
                code='resource-invalid-config',
            )

        # Retrieve the source type from the schema generator
        source = getattr(schema_generator, '_source', 'key')

        # Generate the JSON schema
        int_schema = dict(type='integer')
        str_schema = dict(type='string')
        ref_schema = dict(cls.__pydantic_model_schema__)
        model_schema = __handler.resolve_ref_schema(ref_schema)

        schema: dict[str, Any]
        if source == 'model':
            schema = model_schema
        elif source == 'both':
            schema = {'anyOf': [int_schema, str_schema, model_schema]}
        else:
            schema = {'anyOf': [int_schema, str_schema]}

        # Add resource specific JSON schema properties
        schema.update(alias=cls.resource_config.alias)
        return schema

    @classmethod
    def __pydantic_after_validator__(
        cls: type[Resource],
        obj: Key[Resource] | BaseModel
    ) -> Resource:
        """The inner resource after validator function.

        It is used within the pydantic-core `SchemaValidator` to construct
        instances of the resource from the provided object which can be either
        a key or a validated model instance.

        Args:
            obj: The object to validate.

        Raises:
            ValidationError: If the object could not be created.

        Returns:
            The created resource instance.
        """
        # Retrieve session bulk
        bulk = SESSION_BULK_CONTEXT.get()

        if isinstance(obj, Key):
            # Construct a new resource instance from the key entries
            instance = cls.resource_construct(set(obj.keys()), **obj)
            if bulk is not None:
                if bulk.proxy_reference:
                    instance = ResourceProxy(instance)  # type: ignore
                bulk.add(instance, is_reference=True)
        else:
            # Construct a new resource instance from the provided model
            instance = cls.resource_construct(obj.model_fields_set, obj)
            if bulk is not None:
                bulk.add(instance)

        return instance

    # Hide attributes getter from type checkers to prevent MyPy from allowing
    # arbitrary attribute access instead of raising an error if the attribute
    # is not defined in the resource instance.
    if not typing.TYPE_CHECKING:
        def __getattribute__(self, name: str) -> Any:
            try:
                return object.__getattribute__(self, name)
            except MissingGreenlet as error:
                # Skip only if the validation context is default
                if VALIDATION_CONTEXT.get() == ValidationMode.DEFAULT:
                    raise AttributeError("Skipping missing greenlet.")
                raise error

        def __getattr__(self, name: str) -> Any:
            # Redirect model and Pydantic related attributes to the resource
            # model instance if not found on the resource instance. This is
            # necessary to allow the pydantic core schema feature to work
            # with the resource model instance.
            try:
                model = object.__getattribute__(self, 'resource_model')
                return getattr(model, name)
            except AttributeError as error:
                raise AttributeError(
                    f"Attribute {name!r} not found on resource instance "
                    f"{self!r}."
                ) from error

    def __setattr__(self, name: str, value: Any) -> None:
        # Guard against setting forbidden or protected attributes
        if _guard_attribute(self, name):
            raise AttributeError(
                f"Attribute {name!r} cannot be set on resource instance "
                f"{self.__class__.__name__!r} as it is either forbidden or "
                f"protected, and reserved for internal use."
            )
        # Delegate the attribute setting to the resource dictionary instance
        # to ensure that the attribute is set on the resource model instance
        # if the attribute name is found within the model fields.
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> Any:
        # Guard against setting forbidden or protected attributes
        if _guard_attribute(self, name):
            raise AttributeError(
                f"Attribute {name!r} cannot be deleted on resource instance "
                f"{self.__class__.__name__!r} as it is either forbidden or "
                f"protected, and reserved for internal use."
            )
        # Delegate the attribute deletion to the resource dictionary instance
        # to ensure that the attribute is deleted from the resource model
        # instance if the attribute name is found within the model fields.
        super().__delattr__(name)

    def __repr_args__(self) -> ReprArgs:
        # Yield only the resource indexed fields
        indexed_fields = set.union(*self.resource_indexes)
        for name, value in self.resource_model.__repr_args__():
            if name not in indexed_fields:
                continue
            yield name, value


# MARK: CRUD Resource

class CRUDResource(BaseResource):
    """A CRUD resource.

    It inherits directly from the `BaseResource` and adds the `CRUDService`
    to its configuration services. This enables all CRUD operations on the
    resource instances.
    """
    if typing.TYPE_CHECKING:
        __config__: ClassVar[ResourceConfig | ResourceConfigDict]

    __abstract__ = True
    __config__ = ResourceConfig(services=(CRUDService,))


# MARK: Resource Proxy

if typing.TYPE_CHECKING:
    class ResourceProxy(BaseResource, Generic[Resource]):
        """A resource proxy.

        It delegates attribute access to a resource. This class is used within
        session bulks to resolve resource instances in place.
        """
        pass

else:
    class ResourceProxy(Proxy[Resource], Generic[Resource]):
        pass


# MARK: Utilities

def _create_resource_endpoint(
    resource_path: ResourcePath,
    method: Callable[..., Any],
    *,
    max_selection: int | None = None,
    session: AsyncSession | None = None,
) -> APIEndpoint[Any, Any] | None:
    """Create a resource endpoint from the provided resource path and method.

    Args:
        resource_path: The resource path to create the endpoint for.
        method: The method to create the endpoint for.
        max_selection: The limit of resources to return for the selection.
            Defaults to ``None``.
        session: The async session factory to use for the resolution. If not
            provided, the session in the current context is used.
            Defaults to ``None``.

    Returns:
        The created resource endpoint or ``None`` if the endpoint could not be
        created, i.e. the method selection is a collection and the resource
        last node is a single instance. Otherwise, it would overlap with the
        single instance endpoints.

    Note:
        The resource endpoints introduce a ``selection`` concept that allows
        chaining nested resource target methods with a given resource path,
        i.e. ``/root/{key}/../target/{key}/method``.

        This process either redirects the method to the target resource root
        path when no valid selector candidate is available within the method
        signature; or wraps the method with a selection resolver for the given
        resource path.

        The selection argument can be manually specified using the `Selection`
        API parameter function, either by setting the default value of a
        method argument, or by using the `Annotated` type hint, where the
        `Selection` function is included as one of the arguments. An error will
        be raised if the selection is not valid.

        Only one selection argument per endpoint is allowed. If not set, the
        selection will be inferred from the first non-optional selector
        argument within the method signature that is compatible with the
        resource path target type, such as the target resource type itself, a
        sequence of the target resource type, or a selector like `Key` or
        `KeyList`.

        When the target resource type is directly used for the selection, the
        selector will automatically be resolved to target resource instances.

    ---

    The resource endpoint construction is described bellow for single and
    collection selector candidates, based on the resource path level and the
    selector candidate argument annotation:
    - ``Root``: Whether the resource path is the root path.
    - ``List``: Whether the selector candidate argument is a list.
    - ``None``: Whether the selector candidate argument is optional.
    - ``Fwd``: Whether to redirect the method to the target resource root path.
    - ``Use``: Whether the selector argument is a valid selection candidate and
        is used to resolve the resource path target.
    - ``Param``: The API parameter type of the selector candidate argument.
        When not provided, argument is hidden from the API.
    - ``Path``: The inferred endpoint route path.

    Single selector candidate:

    Root | List | None | Fwd  | Use  | Param  | Path
    ---- | ---- | ---- | ---- | ---- | ------ | ---------------------------
    [X]  | [ ]  | [ ]  |      | [X]  | `path` | ``/{key}/name``
    [X]  | [ ]  | [X]  |      | [ ]  | `body` | ``/name``
    [ ]  | [ ]  | [ ]  | [ ]  | [X]  | `path` | ``../{key}/name``
    [ ]  | [ ]  | [X]  | [X]  | [ ]  | `body` | ``../name`` -> ``/name``

    List selector candidate:

    Root | List | None | Fwd  | Use  | Param  | Path
    ---- | ---- | ---- | ---- | ---- | ------ | ---------------------------
    [X]  | [X]  | [ ]  |      | [X]  | `body` | ``/name``
    [X]  | [X]  | [X]  |      | [ ]  | `body` | ``/name``
    [ ]  | [X]  | [ ]  | [ ]  | [X]  |        | ``../name``
    [ ]  | [X]  | [X]  | [X]  | [ ]  | `body` | ``../name`` -> ``/name``
    """
    # Resolve endpoint owner
    owner = getattr(method, '__config_owner__', resource_path.root)

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
    parameters = dict(signature.parameters)

    # Update method parameter annotations
    for name, parameter in parameters.items():
        parameters[name] = parameter.replace(
            annotation=resolve_types(parameter.annotation)
        )

    # Update method return annotation
    return_annotation = resolve_types(
        signature.return_annotation, root_schemas=('read', 'model')
    )

    # Resolve selection and payload parameters
    target, selection, payload = _extract_resource_endpoint_parameters(
        resource_path.target, *parameters.values()
    )

    skip_last_node = not _is_item_selector(target)
    # Return directly if the method selection is a collection and the resource
    # path last node is a single resource, i.e the accessor collection is set
    # to none. Otherwise, it would overlap with the single instance endpoints.
    if skip_last_node:
        accessor = resource_path.nodes[-1].accessor
        if accessor and accessor.collection is None:
            return None

    # Prepare method with async and keyword-only arguments
    wrapped_method = make_async(make_kw_only(method))

    def create_redirect() -> APIEndpoint[Any, Any]:
        info = resource_path._create_path_info(skip_last_node=skip_last_node)

        # Resolve redirect location
        location = resource_path.target.resource_path + (config.path or '')

        @wraps(method)
        async def endpoint(
            __request: Request, **data: Any
        ) -> Any:
            headers = {
                key: value
                for key, value in __request.headers.items()
                if key.lower() != 'content-length'
            }
            headers.update({'location': location})

            method_data = {
                k: v for k, v in data.items()
                if k not in info.parameters
            }
            response = await wrapped_method(**method_data)

            if isinstance(response, Response):
                response.headers.update({'location': location})
                response.status_code = status.HTTP_307_TEMPORARY_REDIRECT
                return response
            return JSONResponse(
                content=response,
                headers=headers,
                status_code=status.HTTP_307_TEMPORARY_REDIRECT
            )

        config.path = info.path + (config.path or '')

        endpoint_parameters = [
            Parameter(
                name='__request',
                kind=Parameter.POSITIONAL_ONLY,
                annotation=Request
            ),
            *info.parameters.values(),
            *parameters.values(),
        ]
        endpoint_signature = signature.replace(
            parameters=endpoint_parameters,
            return_annotation=return_annotation,
        )

        setattr(endpoint, '__config_route__', config)
        setattr(endpoint, '__signature__', endpoint_signature)
        assert isinstance(endpoint, APIEndpoint)

        return endpoint

    def create_root_endpoint() -> APIEndpoint[Any, Any]:
        info = resource_path._create_path_info(skip_last_node=True)

        @wraps(method)
        async def endpoint(**data: Any) -> Any:
            return await wrapped_method(**data)

        config.path = info.path + (config.path or '')

        endpoint_parameters = [*info.parameters.values(), *parameters.values()]
        endpoint_signature = signature.replace(
            parameters=endpoint_parameters,
            return_annotation=return_annotation,
        )

        setattr(endpoint, '__config_route__', config)
        setattr(endpoint, '__signature__', endpoint_signature)
        assert isinstance(endpoint, APIEndpoint)

        return endpoint

    def create_path_endpoint() -> APIEndpoint[Any, Any]:
        assert selection is not None
        assert target is not None
        info, resolver = resource_path._create_resolver(
            session,
            handler=target.origin,
            metadata=target.metadata,
            max_selection=max_selection,
        )

        # Retrieve backref information
        if resource_path.is_root:
            backref = None
            recursive_guard = None
        else:
            backref = resource_path.nodes[-1].backref
            recursive_guard = backref.recursive_guard if backref else None

        # Update payload annotation with recursive guard
        if backref and payload:
            parameters[payload.name] = payload.replace(
                annotation=Annotation.replace(
                    payload.annotation,
                    test=is_model,
                    resolver=lambda ann: Annotated[
                        ann,
                        RecursiveGuard(
                            recursive_guard,
                            mode=getattr(payload.default, 'on_conflict'),
                        )
                    ],
                ),
            )

        resolve_selector = _is_instance_selector(target)

        @wraps(method)
        async def endpoint(**data: Any) -> Any:
            resolver_data = {
                k: data[k] for k in info.parameters
                if k in data
            }
            method_data = {
                k: v for k, v in data.items()
                if k not in info.parameters
            }

            async def process() -> Any:
                selection_value = await resolver(*resolver_data.values())
                # Update selection parameter
                method_data[selection.name] = selection_value
                # Update payload parameter with selection data
                if backref and payload \
                        and getattr(payload.default, 'apply_selection'):
                    method_data[payload.name] = \
                        _resolve_payload_data_with_selection(
                            method_data[payload.name],
                            selection_value,
                        )
                with recursion_manager(recursive_guard, mode='lax', new=True):
                    return await wrapped_method(**method_data)

            if resolve_selector and not session:
                async with async_session_manager():
                    return await process()
            return await process()

        config.path = info.path + (config.path or '')

        endpoint_parameters = [
            *info.parameters.values(),
            *[p for p in parameters.values() if p.name != selection.name],
        ]
        endpoint_signature = signature.replace(
            parameters=endpoint_parameters,
            return_annotation=return_annotation,
        )

        setattr(endpoint, '__config_route__', config)
        setattr(endpoint, '__signature__', endpoint_signature)
        assert isinstance(endpoint, APIEndpoint)

        return endpoint

    # Handle root path endpoint creation, either create the root endpoint if no
    # selection is available, or the path endpoint with the selection resolver.
    if resource_path.is_root:
        if selection is None:
            return create_root_endpoint()
        return create_path_endpoint()

    # Handle nested path endpoint creation, either create the redirect endpoint
    # if no selection is available, or the path endpoint with the selection
    # resolver.
    if selection is None:
        return create_redirect()
    return create_path_endpoint()


def _extract_resource_endpoint_parameters(
    resource: ResourceType, *parameters: Parameter
) -> tuple[Annotation | None, Parameter | None, Parameter | None]:
    """Extract the resource endpoint parameters.

    It searches for the selection and payload information within the provided
    endpoint method parameters. Additionally, it validates the parameter
    metadata to ensure that no resource endpoint parameter information is
    included within the metadata and no default value is set for the selection
    and payload information.

    Args:
        resource: The resource type to check for selection candidates.
        *parameters: The method parameters to retrieve the selection and
            payload information from.

    Returns:
        A tuple containing the selection and payload information:
        - The extracted selection target resource annotation,
        - The extracted selection parameter,
        - The extracted payload parameter.
    """
    candidates: list[tuple[Annotation, Parameter]] = []
    selections: list[tuple[Annotation, Parameter]] = []

    payloads: list[Parameter] = []

    for param in parameters:
        ann = Annotation.parse(
            param.annotation,
            generics=(BaseSelector, Iterable, Union),
        )
        ann_args = [
            Annotation.parse(arg, generics=(Sequence,))
            for arg in ann.args
        ]

        # Check for payload information
        if isinstance(param.default, PayloadInfo):
            if not any(
                is_model(ann_arg.content)
                and resource is ann_arg.content.__pydantic_resource__
                for ann_arg in ann_args
            ):
                raise PlateformeError(
                    f"Payload annotation content type for resource endpoint "
                    f"methods must be valid schema models from the resource "
                    f"it is evaluated for. Got an invalid annotation for "
                    f"{param.name!r}: {ann!r}.",
                    code='resource-endpoint-parameter',
                )
            if not any(
                ann_arg.origin is None or issubclass(ann_arg.origin, Sequence)
                for ann_arg in ann_args
            ):
                raise PlateformeError(
                    f"Payload annotation for resource endpoint methods must "
                    f"be either a single or sequence of valid schema models. "
                    f"Got an invalid annotation for {param.name!r}: {ann!r}.",
                    code='resource-endpoint-parameter',
                )
            payloads.append(param)

        # Check for selection information
        elif isinstance(param.default, SelectionInfo):
            if resource is not ann.content:
                raise PlateformeError(
                    f"Selection annotation content type for resource endpoint "
                    f"methods must be the resource type it is evaluated for. "
                    f"Got an invalid annotation for {param.name!r}: {ann!r}.",
                    code='resource-endpoint-parameter',
                )
            if ann.optional or not issubclass(ann.origin, BaseSelector):
                raise PlateformeError(
                    f"Selection annotation for resource endpoint methods must "
                    f"be a selector. Got an invalid annotation for "
                    f"{param.name!r}: {ann!r}.",
                    code='resource-endpoint-parameter',
                )
            selections.append((ann, param))

        # Check for selection information candidates
        elif resource is ann.content and not ann.optional:
            candidates.append((ann, param))

        # Validate parameter metadata
        for info in ann.metadata:
            if not isinstance(info, (SelectionInfo, PayloadInfo)):
                continue
            raise PlateformeError(
                f"Resource endpoint parameter information within metadata is "
                f"not allowed. Got invalid metadata for argument "
                f"{param.name!r} of resource {resource}: {info!r}.",
                code='resource-endpoint-parameter',
            )

    # Validate selection
    selection: tuple[Annotation | None, Parameter | None]

    if selections:
        if len(selections) == 1:
            selection = selections[0]
        else:
            raise PlateformeError(
                f"Multiple selection arguments found for resource {resource}. "
                f"Got: {' '.join([param.name for _, param in selections])}.",
                code='resource-endpoint-parameter',
            )
    elif candidates:
        selection = candidates[0]
    else:
        selection = None, None

    # Validate payload
    payload: Parameter | None

    if payloads:
        if len(payloads) == 1:
            payload = payloads[0]
        else:
            raise PlateformeError(
                f"Multiple payload arguments found for resource {resource}. "
                f"Got: {' '.join([param.name for param in payloads])}.",
                code='resource-endpoint-parameter',
            )
    else:
        payload = None

    return *selection, payload


def _guard_attribute(resource: BaseResource, name: str) -> bool:
    """Guard the attribute from being set or deleted."""
    # Guard identifier based on strategy configuration
    if name == 'id':
        if resource.resource_config.id_strategy != 'auto':
            return False
        return True
    # Guard protected attributes
    if match_any_pattern(name, *ALL_ATTRS):
        return True
    return False


def _is_empty_definition(cls: ResourceMeta, bases: tuple[type, ...]) -> bool:
    """Whether the resource definition resolved to an empty base resource."""
    for base in bases:
        if not issubclass_lenient(base, BaseResource):
            continue
        if cls.__annotations__ == base.__annotations__:
            return True
        return False
    return False


def _is_item_selector(annotation: Annotation | None) -> bool:
    """Whether the annotation is an item selector."""
    if annotation is None:
        return False
    origin = annotation.origin
    if issubclass_lenient(origin, BaseSelector):
        if check_config(origin, collection=False):
            return True
        return False
    if issubclass_lenient(origin, Iterable):
        return False
    return True


def _is_instance_selector(annotation: Annotation | None) -> bool:
    """Whether the annotation is an instance selector."""
    if annotation is None:
        return False
    if issubclass_lenient(annotation.origin, BaseSelector):
        return False
    return True


def _resolve_payload_data_with_selection(data: Any, selection: Any) -> Any:
    """Resolve the payload data for the resource endpoint method.

    Args:
        data: The data to resolve the payload for.
        selection: The selection value to use for the resolution.
    """
    if data is None:
        return None

    # Serialize selection
    assert isinstance(selection, dict)
    selection_dict = {
        k: Key.serialize(v, mode='json') for k, v in selection.items()
    }

    # Helper to update payload item data
    def update_with_selection(obj: Any) -> None:
        if hasattr(obj, '__dict__'):
            obj_dict = obj.__dict__
        else:
            obj_dict = obj
        assert isinstance(obj_dict, dict)
        obj_dict.update(selection_dict)

    # Update data with selection
    if isinstance(data, Sequence):
        for item in data:
            update_with_selection(item)
    else:
        update_with_selection(data)

    return data


def _wrap_resource_method(
    resource: ResourceType, method: FunctionLenientType,
) -> Callable[..., Any]:
    """Wrap a resource instance method.

    It is a utility function to wrap a resource instance method and expose it
    as a public method of the resource manager.

    Args:
        resource: The resource type to wrap the method for.
        method: The method to wrap for the resource.

    Returns:
        The wrapped resource instance method.
    """
    # Helper to resolve self in method signature annotations
    def resolve_self(annotation: Any) -> Any:
        return Annotation.replace(
            annotation,
            test=lambda ann: ann is Self,
            resolver=lambda _: resource,
        )

    # Retrieve method configuration and function
    config = getattr(method, '__config_route__', None)
    if isinstance(method, (classmethod, staticmethod)):
        func = method.__func__
    else:
        func = method

    # Retrieve function signature and parameters
    signature = inspect.signature(func)
    parameters = list(signature.parameters.values())
    if not isinstance(method, staticmethod):
        parameters = parameters[1:]
        if not isinstance(method, (classmethod, staticmethod)):
            parameters.insert(0, Parameter(
                name='__%s' % resource.resource_config.alias,
                kind=Parameter.POSITIONAL_ONLY,
                annotation=resource,
            ))

    # Update method parameter annotations
    for count, parameter in enumerate(parameters):
        parameters[count] = parameter.replace(
            annotation=resolve_self(parameter.annotation)
        )

    # Update method return annotation
    return_annotation = resolve_self(signature.return_annotation)

    # Wrap the method
    if isinstance(method, staticmethod):
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)
    elif isinstance(method, classmethod):
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(resource, *args, **kwargs)
    else:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

    # Update configuration and signature
    setattr(wrapper, '__config_owner__', resource)
    if config is not None:
        setattr(wrapper, '__config_route__', config)
    setattr(
        wrapper,
        '__signature__',
        signature.replace(
            parameters=parameters,
            return_annotation=return_annotation,
        ),
    )

    return wrapper
