# plateforme.core.services
# ------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides a collection of classes and utilities to define and
interact with services within the Plateforme framework. It includes base
classes for creating services, utilities for service configuration and
management, and a set of protocols and metaclasses to define service behavior
and characteristics.

The `BaseService` base class provides a base structure for defining services
for all services in the Plateforme framework, providing common functionality
and enforcing a structure for service implementations.

The `BaseServiceWithSpec` base class extends the `BaseService` class to include
the declaration of a resource class or specification associated with the
service.

The `ServiceConfig` class provides a configuration class for services, allowing
services to define and validate configuration options for individual services.
"""

import inspect
import re
import typing
from abc import ABCMeta
from collections.abc import Mapping, Sequence
from copy import deepcopy
from functools import wraps
from typing import (
    Annotated,
    Any,
    Callable,
    ClassVar,
    Generic,
    Literal,
    Protocol,
    Self,
    Type,
    TypeVar,
    Unpack,
)

from typing_extensions import TypedDict

from .api.dependencies import AsyncSessionDep, filter_dependency
from .api.parameters import Body, Depends, Payload, Query, Selection
from .api.routing import APIMethod, APIMode, APIRouteConfig, route
from .config import Configurable, ConfigurableMeta, ConfigWrapper
from .database.orm import InstrumentedAttribute
from .errors import PlateformeError
from .expressions import Filter, IncEx, Sort
from .patterns import RegexPattern, match_any_pattern, to_name_case
from .schema.core import recursion_manager
from .schema.fields import ComputedFieldInfo, ConfigField
from .schema.json import GenerateJsonSchema, JsonSchemaMode, JsonSchemaSource
from .schema.models import BaseModel, DiscriminatedModelType
from .schema.types import TypeAdapterList
from .selectors import Key, KeyList
from .specs import BaseSpec, CRUDSpec, Spec, SpecType, resolve_schema_model
from .typing import (
    Deferred,
    FunctionLenientType,
    WithFunctionTypes,
    getmembers_static,
    is_endpoint,
    is_resource,
    isbaseclass_lenient,
    isfunction_lenient,
    isimplclass_lenient,
)
from .utils import get_meta_orig_bases, make_getattr_resolver

FORBIDDEN_ATTRS = (
    r'exists',
    r'get',
    r'get_one',
    r'get_many',
    r'model',
    r'model_.*',
    r'resource',
    r'resource_.*',
    r'service',
)
PROTECTED_ATTRS = (r'__config__', r'service_.*')

__all__ = (
    'BaseService',
    'BaseServiceConfigDict',
    'BaseServiceWithSpec',
    'CRUDService',
    'Service',
    'ServiceConfig',
    'ServiceConfigDict',
    'ServiceFacade',
    'ServiceWithSpecFacade',
    'ServiceMeta',
    'ServiceType',
    'bind_service',
    'copy_service',
    'load_service',
    'unbind_service',
    'validate_service_method',
)


Service = TypeVar('Service', bound='BaseService')
"""A type variable for service classes."""


ServiceType = Type['BaseService']
"""A type variable for service types."""


# MARK: Service Facade

@typing.runtime_checkable
class ServiceFacade(Protocol):
    """A service facades protocol to manage services."""

    def _add_services(
        cls,
        *services: 'BaseService | ServiceType',
        raise_errors: bool = True,
    ) -> None:
        """Add services to the facade.

        It adds the provided services to the service owner facade and binds
        them to the class. The services are used to extend the owner facade
        with additional functionalities.

        Args:
            *services: The services to add to the service owner facade. It can
                be either a service instance or class that will get
                instantiated.
            raise_errors: Whether to raise errors or fail silently.
                Defaults to ``True``.
        """
        ...

    def _remove_services(
        cls,
        *services: 'BaseService | str',
        raise_errors: bool = True,
    ) -> None:
        """Remove services from the facade.

        It removes the provided services from the service owner facade and
        unbinds them from the instance.

        Args:
            *services: The services to remove from the service owner facade. It
                can be either a service instance or the name of the service.
            raise_errors: Whether to raise errors or fail silently.
                Defaults to ``True``.
        """
        ...


@typing.runtime_checkable
class ServiceWithSpecFacade(ServiceFacade, Protocol):
    """A service facade protocol with specification support."""

    def _add_specs(
        cls,
        *specs: SpecType,
        raise_errors: bool = True,
    ) -> None:
        """Add specifications to the facade.

        It adds the provided specifications to the facade and applies them to
        the class. The specifications are used to extend the facade with
        additional functionalities and model schemas.

        Args:
            *specs: The specifications to add to the facade.
            raise_errors: Whether to raise errors or fail silently.
                Defaults to ``True``.
        """
        ...

    def _remove_specs(
        cls,
        *specs: SpecType,
        raise_errors: bool = True,
    ) -> None:
        """Remove specifications from the facade.

        It removes the provided specifications from the facade and unbinds them
        from the class.

        Args:
            *specs: The specifications to remove from the facade.
            raise_errors: Whether to raise errors or fail silently.
                Defaults to ``True``.
        """
        ...


# MARK: Service Configuration

class BaseServiceConfigDict(TypedDict, total=False):
    """A base service class configuration dictionary."""

    include: list[str] | set[str] | str | None
    """The method names to include when binding the service."""

    exclude: list[str] | set[str] | str | None
    """The method names to exclude when binding the service."""

    include_method: list[APIMethod] | set[APIMethod] | APIMethod | None
    """The HTTP methods to include when binding the service."""

    exclude_method: list[APIMethod] | set[APIMethod] | APIMethod | None
    """The HTTP methods to exclude when binding the service."""

    include_mode: list[APIMode] | set[APIMode] | APIMode | None
    """The method modes to include when binding the service."""

    exclude_mode: list[APIMode] | set[APIMode] | APIMode | None
    """The method modes to exclude when binding the service."""

    limit: int
    """The default page size limit for service queries. It is used to limit the
    number of results returned per page when paginating results."""

    page_size: int
    """The default page size for service queries. It is used to determine the
    number of results returned per page when paginating results."""

    auto_apply_spec: bool
    """Whether to automatically apply the specification when binding the
    service to a facade owner."""


class ServiceConfigDict(BaseServiceConfigDict, total=False):
    """A service class configuration dictionary."""

    name: str
    """The name of the service. It must adhere to a specific ``ALIAS`` pattern
    as defined in the framework's regular expressions repository. It is
    inferred from the snake case version of the service name."""


class ServiceConfig(ConfigWrapper):
    """A service class configuration."""
    if typing.TYPE_CHECKING:
        __config_owner__: ServiceType = ConfigField(frozen=True, init=False)

    __config_mutable__ = True

    type_: str = ConfigField(default='service', frozen=True, init=False)
    """The configuration owner type set to ``service``. It is a protected field
    that is typically used with `check_config` to validate an object type
    without using `isinstance` in order to avoid circular imports."""

    name: str = Deferred
    """The name of the service. It must adhere to a specific ``ALIAS`` pattern
    as defined in the framework's regular expressions repository. It is
    inferred from the snake case version of the service name."""

    include: list[str] | set[str] | str | None = ConfigField(default=None)
    """The method names to include when binding the service."""

    exclude: list[str] | set[str] | str | None = ConfigField(default=None)
    """The method names to exclude when binding the service."""

    include_method: list[APIMethod] | set[APIMethod] | APIMethod | None = \
        ConfigField(default=None)
    """The HTTP methods to include when binding the service."""

    exclude_method: list[APIMethod] | set[APIMethod] | APIMethod | None = \
        ConfigField(default=None)
    """The HTTP methods to exclude when binding the service."""

    include_mode: list[APIMode] | set[APIMode] | APIMode | None = \
        ConfigField(default=None)
    """The method modes to include when binding the service."""

    exclude_mode: list[APIMode] | set[APIMode] | APIMode | None = \
        ConfigField(default=None)
    """The method modes to exclude when binding the service."""

    limit: int = ConfigField(default=20)
    """The default page size limit for service queries. It is used to limit the
    number of results returned per page when paginating results."""

    page_size: int = ConfigField(default=20)
    """The default page size for service queries. It is used to determine the
    number of results returned per page when paginating results."""

    auto_apply_spec: bool = ConfigField(default=True)
    """Whether to automatically apply the specification when binding the
    service to a facade owner."""

    def post_init(self) -> None:
        """Post-initialization steps for the service configuration."""
        # Skip post-initialization if the configuration owner is not set
        service = self.__config_owner__
        if service is None:
            return

        self.setdefault('name', to_name_case(service.__name__, ('all', None)))
        if not re.match(RegexPattern.ALIAS, self.name):
            raise ValueError(
                f"Invalid service name {self.name!r} for service "
                f"configuration {service.__qualname__!r}."
            )

        if self.limit < 1:
            raise ValueError(
                f"Invalid page size limit {self.limit!r} for service "
                f"configuration {service.__qualname__!r}."
            )

        if self.page_size < 1:
            raise ValueError(
                f"Invalid page size {self.page_size!r} for service "
                f"configuration {service.__qualname__!r}."
            )


# MARK: Service Metaclass

class ServiceMeta(ABCMeta, ConfigurableMeta):
    """A metaclass for service classes."""
    if typing.TYPE_CHECKING:
        __config__: ServiceConfig | ServiceConfigDict
        __config_spec__: SpecType | None
        service_config: ServiceConfig
        service_methods: dict[str, FunctionLenientType]

    def __new__(
        mcls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        /,
        **kwargs: Any,
    ) -> type:
        """Create a new service class."""
        # Check for namespace forbidden attributes
        for attr in namespace:
            if match_any_pattern(attr, *FORBIDDEN_ATTRS):
                raise AttributeError(
                    f"Attribute {attr!r} cannot be set on service class "
                    f"{name!r} as it is forbidden."
                )

        # Create the service class
        cls = super().__new__(
            mcls,
            name,
            bases,
            namespace,
            config_attr='service_config',
            **kwargs,
        )

        # Collect the service specification from the original bases found
        # within the class namespace and the provided bases.
        spec = cls.collect_spec(bases, namespace)

        setattr(cls, '__config_spec__', spec)

        # Collect service public method members as a dictionary of callables,
        # including static and class method members, and excluding dunder and
        # private method members. The collected methods are stored and exposed
        # to the service owner facade.
        members = getmembers_static(cls, predicate=isfunction_lenient)
        methods: dict[str, FunctionLenientType] = {}
        for name, method in members:
            # Skip dunder and private method members
            if name.startswith('_'):
                if not is_endpoint(method):
                    continue
                raise AttributeError(
                    f"A dunder or private method cannot be decorated with a "
                    f"route decorator. Got method {name!r} in service class "
                    f"{name!r}."
                )
            # Add method member to dictionary
            assert isinstance(method, WithFunctionTypes)
            methods[name] = method

        setattr(cls, 'service_methods', methods)
        setattr(cls, 'service_owner', None)

        return cls

    def collect_spec(
        cls, bases: tuple[type, ...], namespace: dict[str, Any], /,
    ) -> SpecType | None:
        """Collect the specification from the given bases and namespace.

        It collects the specification from the given bases and namespace by
        extracting the specification from the original bases annotation if
        it is a generic subclass of the base service with specification class.

        Args:
            bases: The class bases.
            namespace: The class namespace.

        Returns:
            The specification if found, otherwise ``None``.
        """
        meta_bases = get_meta_orig_bases(bases, namespace)
        for meta_base in meta_bases:
            origin = typing.get_origin(meta_base)
            if origin is None:
                continue
            if not isbaseclass_lenient(origin, 'BaseServiceWithSpec'):
                continue
            args = typing.get_args(meta_base)
            if len(args) == 1 \
                    and isimplclass_lenient(args[0], BaseSpec, max_depth=1):
                return args[0]  # type: ignore
            raise TypeError(
                f"Generic argument for the `BaseServiceWithSpec` class must "
                f"be a subclass of the `BaseSpec` class. Got: {args}."
            )

        return None


# MARK: Base Service

class BaseService(Configurable[ServiceConfig], metaclass=ServiceMeta):
    """A base class for services.

    It provides a base class for creating service objects that can be attached
    to a service facade owner. Services can be customized through their
    `service_config` attribute and optionally integrated with a specification.

    When combined with a specification, services are augmented with the
    specification specific methods, attributes and model schemas. This allows
    services to have a dynamic behavior based on the provided specification.

    See the `BaseServiceWithSpec` class for more details on how to integrate
    services with a specification.

    Attributes:
        __config__: The configuration class setter for the service.
        __config_spec__: The specification class for the service.

        service_config: The configuration class for the service.
        service_methods: A dictionary of public methods of the service.
        service_owner: The service facade owner of the service.

    Note:
        The service class should not be directly instantiated, and it should be
        subclassed to define a new service class. The service class should
        define public methods that can be bound to the service facade owner.
    """
    if typing.TYPE_CHECKING:
        __config__: ClassVar[ServiceConfig | ServiceConfigDict]
        __config_spec__: ClassVar[SpecType | None]
        service_methods: ClassVar[dict[str, FunctionLenientType]]

        service_config: ServiceConfig
        service_owner: ServiceFacade | ServiceWithSpecFacade | None

    __config__ = ServiceConfig()

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        """Create a new service instance."""
        if cls is BaseService:
            raise TypeError(
                "A base service class cannot be directly instantiated."
            )
        self = super().__new__(cls)
        object.__setattr__(self, 'service_owner', None)
        return self

    def __init__(self, **kwargs: Unpack[ServiceConfigDict]) -> None:
        """Initialize the service.

        Args:
            **kwargs: The service configuration overrides.

        Note:
            When multiple services have the same name and need to be uniquely
            identified, the service name can be updated by providing the `name`
            keyword argument.
        """
        super().__init__()
        self.service_config.update(**kwargs)

    def __post_bind__(
        self, facade: ServiceFacade | ServiceWithSpecFacade
    ) -> None:
        """Hook method called when binding a service to a facade.

        It is called after the service is bound to a service facade owner. The
        method exposes the service owner facade.

        Args:
            facade: The service facade owner.
        """
        ...

    def __post_load__(
        self, facade: ServiceFacade | ServiceWithSpecFacade
    ) -> None:
        """Hook method called when loading the service.

        It is called after the service is loaded within a service facade owner.
        The method exposes the service owner facade.

        Args:
            facade: The service facade owner.
        """
        ...

    def __setattr__(self, name: str, value: Any) -> None:
        # Check for forbidden and protected attributes
        if match_any_pattern(name, *FORBIDDEN_ATTRS, *PROTECTED_ATTRS):
            raise AttributeError(
                f"Attribute {name!r} cannot be set on service instance "
                f"{self!r} as it is either forbidden or protected, and "
                f"reserved for internal use."
            )
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        # Check for forbidden and protected attributes
        if match_any_pattern(name, *FORBIDDEN_ATTRS, *PROTECTED_ATTRS):
            raise AttributeError(
                f"Attribute {name!r} cannot be deleted from service instance "
                f"{self!r} as it is either forbidden or protected, and "
                f"reserved for internal use."
            )
        super().__delattr__(name)

    def __repr__(self) -> str:
        return f'{self.__class__.__qualname__}({self})'

    def __str__(self) -> str:
        return self.service_config.name


# MARK: Base Service with Specification

class BaseServiceWithSpec(BaseService, Generic[Spec]):
    """A base class for services with a specification.

    It provides a base class for creating service objects that can be attached
    to a service facade owner. Services can be customized through their
    `service_config` attribute.

    The provided specification in the generic argument, that much implements
    the base specification protocol such as resources, augments the service
    with specific methods, attributes and model schemas. This allows services
    to have a dynamic behavior.

    Attributes:
        service_config: The configuration class for the service.
        service_methods: A dictionary of public methods of the service.
        service_owner: The service facade owner of the service.

    Note:
        The service class should not be directly instantiated, and it should be
        subclassed to define a new service class. The service class should
        define public methods that can be bound to the service facade owner.
    """
    if typing.TYPE_CHECKING:
        from .packages import Package
        from .resources import ResourceConfig, ResourceFieldInfo

        # Resource class attributes
        resource: type[Spec]
        resource_adapter: TypeAdapterList[Spec]
        resource_attributes: dict[str, InstrumentedAttribute[Any]]
        resource_computed_fields: dict[str, ComputedFieldInfo]
        resource_config: ResourceConfig
        resource_fields: dict[str, ResourceFieldInfo]
        resource_identifiers: tuple[set[str]]
        resource_indexes: tuple[set[str]]
        resource_package: Package
        resource_schemas: dict[str, DiscriminatedModelType] = {}

        # Resource class methods
        @classmethod
        def resource_construct(
            cls,
            _fields_set: set[str] | None = None,
            _model: BaseModel | None = None,
            **data: Any,
        ) -> Spec:
            ...

        @classmethod
        def resource_json_schema(
            cls,
            by_alias: bool = True,
            ref_template: str = ...,
            schema_generator: type[GenerateJsonSchema] = ...,
            mode: 'JsonSchemaMode' = 'validation',
            source: 'JsonSchemaSource' = 'key',
        ) -> dict[str, Any]:
            ...

        @classmethod
        def resource_parametrized_name(
            cls, params: tuple[type[Any], ...]
        ) -> str:
            ...

        @classmethod
        def resource_validate(
            cls,
            obj: Any,
            *,
            strict: bool | None = None,
            from_attributes: bool | None = None,
            context: dict[str, Any] | None = None,
        ) -> Spec:
            ...

        @classmethod
        def resource_validate_json(
            cls,
            json_data: str | bytes | bytearray,
            *,
            strict: bool | None = None,
            context: dict[str, Any] | None = None,
        ) -> Spec:
            ...

        @classmethod
        def resource_validate_strings(
            cls,
            obj: Any,
            *,
            strict: bool | None = None,
            context: dict[str, Any] | None = None,
        ) -> Spec:
            ...

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        """Create a new service with specification instance."""
        if cls is BaseServiceWithSpec:
            raise TypeError(
                "A base service cannot be directly instantiated."
            )
        return super().__new__(cls)

    def __init__(self, **kwargs: Unpack[ServiceConfigDict]) -> None:
        """Initialize the service.

        Args:
            **kwargs: The service configuration overrides.

        Note:
            When multiple services have the same name and need to be uniquely
            identified, the service name can be updated by providing the `name`
            keyword argument.
        """
        super().__init__(**kwargs)

    def __post_bind__(  # type: ignore[override, unused-ignore]
        self, facade: ServiceWithSpecFacade
    ) -> None:
        """Hook method called when binding a service to a facade.

        It is called after the service is bound to a service facade owner. The
        method exposes the service owner facade.

        Args:
            facade: The service facade owner with specification support.
        """
        ...

    # Hide attributes getter from type checkers to prevent MyPy from allowing
    # arbitrary attribute access instead of raising an error if the attribute
    # is not defined in the resource class.
    if not typing.TYPE_CHECKING:
        def __getattr__(self, name: str) -> Any:
            # Redirect resource related attributes to the resource class.
            if name == 'resource' or name.startswith('resource_'):
                if self.service_owner is None:
                    raise PlateformeError(
                        f"Cannot access resource attributes on service "
                        f"{self!r} without a service owner. Service must be "
                        f"bound to a service facade owner.",
                        code='services-not-bound',
                    )
                if name == 'resource':
                    return self.service_owner
                return getattr(self.service_owner, name)
            raise AttributeError(
                f"Service {self!r} has no attribute {name!r}."
            )


# MARK: CRUD Service

class CRUDService(BaseServiceWithSpec[CRUDSpec]):
    """The CRUD services."""

    __config__ = {
        'name': 'crud',
    }

    # MARK:> Create

    @route.post(
        path='',
        response_model=list[CRUDSpec.Read] | None,
        response_model_serialization=False,
    )
    async def create(
        self,
        session: AsyncSessionDep,
        __selection: KeyList[CRUDSpec] = Selection(),
        payload: CRUDSpec.Create | Sequence[CRUDSpec.Create] = Payload(
            apply_selection=True,
            title='Payload',
            description="""The payload to create instances of the associated
                resource, either a single instance or a sequence of instances.
                The payload must adhere to the resource schema for the create
                operation.""",
        ),
        return_result: bool = Body(
            default=True,
            title='Return result',
            description="""Whether to return the created result. If set to
                `False`, the transaction will be executed without returning
                the result.""",
        ),
        include: IncEx | None = Body(
            default=None,
            title='Include fields',
            description="""The fields to include in the query results.""",
            examples=[
                ['user.name', 'user.email'],
                {'user': ['name', 'email'], 'product': False},
            ],
        ),
        exclude: IncEx | None = Body(
            default=None,
            title='Exclude fields',
            description="""The fields to exclude from the query results.""",
            examples=[
                ['user.password', 'product.price'],
                {'user': ['password'], 'product': True},
            ],
        ),
        dry_run: bool = Body(
            default=False,
            title='Dry-run',
            description="""Whether to run the transaction in dry-run mode. If
                set to `True`, the transaction will be rolled back after
                execution.""",
        ),
    ) -> Any | None:
        """Create a single or collection of resource instances.

        Args:
            session: The async session dependency to use for the transaction.
            __selection: The key selection dependency to resolve the query.
            payload: The payload to create instances of the associated
                resource, either a single instance or a sequence of instances.
            return_result: Whether to return the created result.
            include: The fields to include in the query results.
            exclude: The fields to exclude from the query results.
            dry_run: Whether to run the transaction in dry-run mode.

        Returns:
            The created resource instances or ``None`` if return result is
            disabled, i.e., ``return_result=False``.
        """
        async with session.bulk() as bulk:
            # Validate payload
            result = self.resource_adapter.validate_python(
                payload, from_attributes=True
            )
            # Resolve references
            await bulk.resolve(
                raise_errors=True,
                scope='references',
                strategy='hydrate' if return_result else 'bind',
            )
            # Add instances to the session
            session.add_all(result)

        # Commit or rollback the transaction
        if dry_run:
            await session.rollback()
        else:
            if return_result:
                session.sync_session.expire_on_commit = False
            await session.commit()

        # Handle return result
        if not return_result:
            return None
        type_adapter = self.resource_schemas['read'].model_adapter
        with recursion_manager(mode='omit'):
            values = type_adapter.validate_python(result, from_attributes=True)
            return type_adapter.dump_python(
                values,
                mode='json',
                by_alias=True,
                include=include,
                exclude=exclude,
            )

    # MARK:> Read

    @route.get(
        path='',
        response_model=CRUDSpec.Read,
        response_model_serialization=False,
    )
    async def read_one(
        self,
        session: AsyncSessionDep,
        selection: Key[CRUDSpec] = Selection(),
        include: IncEx | None = Body(
            default=None,
            title='Include fields',
            description="""The fields to include in the query results.""",
            examples=[
                ['user.name', 'user.email'],
                {'user': ['name', 'email'], 'product': False},
            ],
        ),
        exclude: IncEx | None = Body(
            default=None,
            title='Exclude fields',
            description="""The fields to exclude from the query results.""",
            examples=[
                ['user.password', 'product.price'],
                {'user': ['password'], 'product': True},
            ],
        ),
    ) -> Any:
        """Read a resource instance.

        Args:
            session: The async session dependency to use for the query.
            selection: The key selection dependency to resolve the query.
            include: The fields to include in the query results.
            exclude: The fields to exclude from the query results.

        Returns:
            The resource instance from the selection.
        """
        result = await selection.resolve(session)

        # Handle result
        type_adapter = self.resource_schemas['read'].model_adapter
        with recursion_manager(mode='omit'):
            values = type_adapter.validate_python(result, from_attributes=True)
            return type_adapter.dump_python(
                values,
                mode='json',
                by_alias=True,
                include=include,
                exclude=exclude,
            )[0]

    @route.get(
        path='',
        response_model=list[CRUDSpec.Read],
        response_model_serialization=False,
    )
    async def read_many(
        self,
        session: AsyncSessionDep,
        selection: KeyList[CRUDSpec] = Selection(),
        include: IncEx | None = Body(
            default=None,
            title='Include fields',
            description="""The fields to include in the query results.""",
            examples=[
                ['user.name', 'user.email'],
                {'user': ['name', 'email'], 'product': False},
            ],
        ),
        exclude: IncEx | None = Body(
            default=None,
            title='Exclude fields',
            description="""The fields to exclude from the query results.""",
            examples=[
                ['user.password', 'product.price'],
                {'user': ['password'], 'product': True},
            ],
        ),
        filter: Annotated[Filter | None, Depends(filter_dependency)] = Body(
            default=None,
            title='Filter criteria',
            description="""The filter criteria to apply to the query. It is
                specified in the request body as a dictionary of field aliases
                with their corresponding filter criteria. Additionally, it can
                be specified directly in the query parameters using a dot
                notation for field aliases and tilde `~` character for filter
                criteria. For example, to filter results where the `user.name`
                field starts with `Al`, the filter criteria can be specified as
                `.user.name=like~Al*` in the query parameters.""",
            examples=[
                '.user.name=like~Al*',
                '.price=gt~1000',
                '.user.name=like~Al*&.price=gt~1000',
                {
                    'user': {'name': {'operator': 'like', 'value': 'Al*'}},
                    'price': {'operator': 'gt', 'value': 1000},
                },
            ],
        ),
        sort: Sort | None = Query(
            default=None,
            title='Sort criteria',
            description="""The sort criteria to apply to the query. It is
                specified in the query parameters as a comma-separated list of
                field aliases with an optional prefix of a minus sign `-` for
                descending order. For example, to sort results by the
                `user.name` field in descending order, the sort criteria can be
                specified as `user.name,-price` in the query parameters.
                Additionally, the direction and nulls position can be piped
                using a colon `:` character. For example, to sort results by
                the `price` field in ascending order with nulls first, the sort
                criteria can be specified as `price:asc:nf` in the query
                parameters.""",
            examples=['user.name,-price', 'price:asc:nf'],
        ),
        limit: int | None = Query(
            default=None,
            gt=0,
            title='Limit',
            description="""The maximum number of results to return. It is
                specified in the query parameters as an integer value. Defaults
                to the service configuration default page size if not
                specified.""",
            examples=[10, 20, 50],
        ),
        offset: int | None = Query(
            default=None,
            ge=0,
            title='Offset',
            description="""The number of results to skip before returning the
                results. It is specified in the query parameters as an integer
                value. Defaults to `0` if not specified.""",
        ),
        page: int | None = Query(
            default=None,
            gt=0,
            title='Page',
            description="""The page number to return results for. It is
                specified in the query parameters as an integer value. Defaults
                to the first page if not specified.""",
        ),
        page_size: int | None = Query(
            default=None,
            gt=0,
            title='Page size',
            description="""The number of results to return per page. It is
                specified in the query parameters as an integer value. The
                maximum page size is defined by the service configuration.
                Defaults to the service configuration default page size if not
                specified.""",
        ),
    ) -> Any:
        """Read a collection of resource instances.

        Args:
            session: The async session dependency to use for the query.
            selection: The key selection dependency to resolve the query.
            include: The fields to include in the query results.
            exclude: The fields to exclude from the query results.
            filter: The filter criteria to apply to the query.
            sort: The sort criteria to apply to the query.
            limit: The maximum number of results to return.
            offset: The number of results to skip before returning the results.
            page: The page number to return results for.
            page_size: The number of results to return per page.

        Returns:
            The collection of resource instances from the selection.
        """
        # Resolve parameters
        limit = (
            limit
            or page_size
            or self.service_config.get(
                'page_size', self.resource_config.api_max_selection
            )
        )
        limit = min(limit, self.resource_config.api_max_selection)
        offset = offset or 0
        page = page or 1
        page_size = page_size or self.service_config.page_size

        # Build query
        query = selection.build_query(
            filter_criteria=filter,
            sort_criteria=sort,
        )
        query = query.offset((page - 1) * page_size + offset)
        query = query.limit(limit)

        # Execute query and return results
        buffer = await session.execute(query)
        result = buffer.unique().scalars().all()

        # Handle result
        type_adapter = self.resource_schemas['read'].model_adapter
        with recursion_manager(mode='omit'):
            values = type_adapter.validate_python(result, from_attributes=True)
            return type_adapter.dump_python(
                values,
                mode='json',
                by_alias=True,
                include=include,
                exclude=exclude,
            )

    # MARK:> Update

    @route.patch(
        path='',
        response_model=CRUDSpec.Read,
        response_model_serialization=False,
    )
    async def update_one(
        self,
        session: AsyncSessionDep,
        selection: Key[CRUDSpec] = Selection(),
        payload: CRUDSpec.Update = Payload(
            apply_selection=False,
            title='Payload',
            description="""The payload to update the instance of the associated
                resource. The payload must adhere to the resource schema for
                the update operation.""",
        ),
        return_result: bool = Body(
            default=True,
            title='Return result',
            description="""Whether to return the updated result. If set to
                `False`, the transaction will be executed without returning
                the result.""",
        ),
        include: IncEx | None = Body(
            default=None,
            title='Include fields',
            description="""The fields to include in the query results.""",
            examples=[
                ['user.name', 'user.email'],
                {'user': ['name', 'email'], 'product': False},
            ],
        ),
        exclude: IncEx | None = Body(
            default=None,
            title='Exclude fields',
            description="""The fields to exclude from the query results.""",
            examples=[
                ['user.password', 'product.price'],
                {'user': ['password'], 'product': True},
            ],
        ),
        dry_run: bool = Body(
            default=False,
            title='Dry-run',
            description="""Whether to run the transaction in dry-run mode. If
                set to `True`, the transaction will be rolled back after
                execution.""",
        ),
    ) -> Any | None:
        """Update a resource instance.

        Args:
            session: The async session dependency to use for the transaction.
            selection: The key selection dependency to resolve the query.
            payload: The payload to update the associated resource instance.
            return_result: Whether to return the updated result.
            include: The fields to include in the query results.
            exclude: The fields to exclude from the query results.
            dry_run: Whether to run the transaction in dry-run mode.

        Returns:
            The updated resource instance or ``None`` if return result is
            disabled, i.e., ``return_result=False``.
        """
        # Prepare update
        update = payload.model_dump(mode='raw', exclude_unset=True)

        # Execute query and update result
        result_source = await selection.resolve(session)
        result_dirty = {**result_source.resource_dump(mode='raw'), **update}

        async with session.bulk() as bulk:
            # Validate payload
            result_staged = self.resource_adapter.validate_python(result_dirty)
            # Resolve references
            await bulk.resolve(
                raise_errors=True,
                scope='references',
                strategy='hydrate' if return_result else 'bind',
            )

        # Merge staged instances into the session
        result: list[CRUDSpec] = []
        for instance_staged in result_staged:
            instance = await session.merge(instance_staged)
            result.append(instance)

        # Commit or rollback the transaction
        if dry_run:
            await session.rollback()
        else:
            if return_result:
                session.sync_session.expire_on_commit = False
            await session.commit()

        # Handle return result
        if not return_result:
            return None
        type_adapter = self.resource_schemas['read'].model_adapter
        with recursion_manager(mode='omit'):
            values = type_adapter.validate_python(result, from_attributes=True)
            return type_adapter.dump_python(
                values,
                mode='json',
                by_alias=True,
                include=include,
                exclude=exclude,
            )[0]

    @route.patch(
        path='',
        response_model=list[CRUDSpec.Read],
        response_model_serialization=False,
    )
    async def update_many(
        self,
        session: AsyncSessionDep,
        selection: KeyList[CRUDSpec] = Selection(),
        payload: CRUDSpec.Update = Payload(
            apply_selection=False,
            title='Payload',
            description="""The payload to update instances of the associated
                resource. The payload must adhere to the resource schema for
                the update operation.""",
        ),
        return_result: bool = Body(
            default=True,
            title='Return result',
            description="""Whether to return the updated result. If set to
                `False`, the transaction will be executed without returning
                the result.""",
        ),
        include: IncEx | None = Body(
            default=None,
            title='Include fields',
            description="""The fields to include in the query results.""",
            examples=[
                ['user.name', 'user.email'],
                {'user': ['name', 'email'], 'product': False},
            ],
        ),
        exclude: IncEx | None = Body(
            default=None,
            title='Exclude fields',
            description="""The fields to exclude from the query results.""",
            examples=[
                ['user.password', 'product.price'],
                {'user': ['password'], 'product': True},
            ],
        ),
        filter: Annotated[Filter | None, Depends(filter_dependency)] = Body(
            default=None,
            title='Filter criteria',
            description="""The filter criteria to apply to the query. It is
                specified in the request body as a dictionary of field aliases
                with their corresponding filter criteria. Additionally, it can
                be specified directly in the query parameters using a dot
                notation for field aliases and tilde `~` character for filter
                criteria. For example, to filter results where the `user.name`
                field starts with `Al`, the filter criteria can be specified as
                `.user.name=like~Al*` in the query parameters.""",
            examples=[
                '.user.name=like~Al*',
                '.price=gt~1000',
                '.user.name=like~Al*&.price=gt~1000',
                {
                    'user': {'name': {'operator': 'like', 'value': 'Al*'}},
                    'price': {'operator': 'gt', 'value': 1000},
                },
            ],
        ),
        sort: Sort | None = Query(
            default=None,
            title='Sort criteria',
            description="""The sort criteria to apply to the query. It is
                specified in the query parameters as a comma-separated list of
                field aliases with an optional prefix of a minus sign `-` for
                descending order. For example, to sort results by the
                `user.name` field in descending order, the sort criteria can be
                specified as `user.name,-price` in the query parameters.
                Additionally, the direction and nulls position can be piped
                using a colon `:` character. For example, to sort results by
                the `price` field in ascending order with nulls first, the sort
                criteria can be specified as `price:asc:nf` in the query
                parameters.""",
            examples=['user.name,-price', 'price:asc:nf'],
        ),
        limit: int | None = Query(
            default=None,
            gt=0,
            title='Limit',
            description="""The maximum number of results to return. It is
                specified in the query parameters as an integer value. Defaults
                to the service configuration default page size if not
                specified.""",
            examples=[10, 20, 50],
        ),
        offset: int | None = Query(
            default=None,
            ge=0,
            title='Offset',
            description="""The number of results to skip before returning the
                results. It is specified in the query parameters as an integer
                value. Defaults to `0` if not specified.""",
        ),
        page: int | None = Query(
            default=None,
            gt=0,
            title='Page',
            description="""The page number to return results for. It is
                specified in the query parameters as an integer value. Defaults
                to the first page if not specified.""",
        ),
        page_size: int | None = Query(
            default=None,
            gt=0,
            title='Page size',
            description="""The number of results to return per page. It is
                specified in the query parameters as an integer value. The
                maximum page size is defined by the service configuration.
                Defaults to the service configuration default page size if not
                specified.""",
        ),
        dry_run: bool = Body(
            default=False,
            title='Dry-run',
            description="""Whether to run the transaction in dry-run mode. If
                set to `True`, the transaction will be rolled back after
                execution.""",
        ),
    ) -> Any | None:
        """Update a collection of resource instances.

        Args:
            session: The async session dependency to use for the transaction.
            selection: The key selection dependency to resolve the query.
            payload: The payload to update instances of the associated
                resource.
            return_result: Whether to return the updated result.
            include: The fields to include in the query results.
            exclude: The fields to exclude from the query results.
            filter: The filter criteria to apply to the query.
            sort: The sort criteria to apply to the query.
            limit: The maximum number of results to return.
            offset: The number of results to skip before returning the results.
            page: The page number to return results for.
            page_size: The number of results to return per page.
            dry_run: Whether to run the transaction in dry-run mode.

        Returns:
            The updated resource instances or ``None`` if return result is
            disabled, i.e., ``return_result=False``.
        """
        # Prepare update
        update = payload.model_dump(mode='raw', exclude_unset=True)

        # Resolve parameters
        limit = (
            limit
            or page_size
            or self.service_config.get(
                'page_size', self.resource_config.api_max_selection
            )
        )
        limit = min(limit, self.resource_config.api_max_selection)
        offset = offset or 0
        page = page or 1
        page_size = page_size or self.service_config.page_size

        # Build query
        query = selection.build_query(
            filter_criteria=filter,
            sort_criteria=sort,
        )
        query = query.offset((page - 1) * page_size + offset)
        query = query.limit(limit)

        # Execute query and update result
        buffer = await session.execute(query)
        result_source = buffer.unique().scalars().all()
        result_dirty: list[dict[str, Any]] = []
        for instance_source in result_source:
            result_dirty.append({
                **instance_source.resource_dump(mode='raw'),
                **update,
            })

        async with session.bulk() as bulk:
            # Validate payload
            result_staged = self.resource_adapter.validate_python(result_dirty)
            # Resolve references
            await bulk.resolve(
                raise_errors=True,
                scope='references',
                strategy='hydrate' if return_result else 'bind',
            )

        # Merge staged instances into the session
        result: list[CRUDSpec] = []
        for instance_staged in result_staged:
            instance = await session.merge(instance_staged)
            result.append(instance)

        # Commit or rollback the transaction
        if dry_run:
            await session.rollback()
        else:
            if return_result:
                session.sync_session.expire_on_commit = False
            await session.commit()

        # Handle return result
        if not return_result:
            return None
        type_adapter = self.resource_schemas['read'].model_adapter
        with recursion_manager(mode='omit'):
            values = type_adapter.validate_python(result, from_attributes=True)
            return type_adapter.dump_python(
                values,
                mode='json',
                by_alias=True,
                include=include,
                exclude=exclude,
            )

    # MARK:> Upsert

    @route.put(
        path='',
        response_model=CRUDSpec.Read | None,
        response_model_serialization=False,
    )
    async def upsert(
        self,
        session: AsyncSessionDep,
        __selection: KeyList[CRUDSpec] = Selection(),
        payload: CRUDSpec.Upsert | Sequence[CRUDSpec.Upsert] = Payload(
            apply_selection=True,
            title='Payload',
            description="""The payload to upsert instances of the associated
                resource, either a single instance or a sequence of instances.
                The payload must adhere to the resource schema for the upsert
                operation.""",
        ),
        on_conflict: Literal['update', 'skip'] = Body(
            default='update',
            title='On conflict',
            description="""The conflict resolution strategy to apply when
                upserting instances. It can be either `update` to update the
                existing instances or `skip` to skip the existing instances.
                """,
        ),
        return_result: bool = Body(
            default=True,
            title='Return result',
            description="""Whether to return the upserted result. If set to
                `False`, the transaction will be executed without returning
                the result.""",
        ),
        include: IncEx | None = Body(
            default=None,
            title='Include fields',
            description="""The fields to include in the query results.""",
            examples=[
                ['user.name', 'user.email'],
                {'user': ['name', 'email'], 'product': False},
            ],
        ),
        exclude: IncEx | None = Body(
            default=None,
            title='Exclude fields',
            description="""The fields to exclude from the query results.""",
            examples=[
                ['user.password', 'product.price'],
                {'user': ['password'], 'product': True},
            ],
        ),
        dry_run: bool = Body(
            default=False,
            title='Dry-run',
            description="""Whether to run the transaction in dry-run mode. If
                set to `True`, the transaction will be rolled back after
                execution.""",
        ),
    ) -> Any | None:
        """Upsert a single or collection of resource instances.

        Args:
            session: The async session dependency to use for the transaction.
            __selection: The key selection dependency to resolve the query.
            payload: The payload to upsert instances of the associated
                resource, either a single instance or a sequence of instances.
            on_conflict: The conflict resolution strategy to apply when
                upserting instances.
            return_result: Whether to return the upserted result.
            include: The fields to include in the query results.
            exclude: The fields to exclude from the query results.
            dry_run: Whether to run the transaction in dry-run mode.

        Returns:
            The upserted resource instances or ``None`` if return result is
            disabled, i.e., ``return_result=False``.
        """
        async with session.bulk() as bulk:
            # Validate payload
            _ = self.resource_adapter.validate_python(
                payload, from_attributes=True
            )
            # Resolve references
            await bulk.resolve(
                raise_errors=True,
                scope='references',
                strategy='hydrate' if return_result else 'bind',
            )
            # Resolve values
            await bulk.resolve(
                raise_errors=False,
                scope='values',
                strategy='hydrate' if return_result else 'bind',
            )
            # Retrieve results
            result_resolved = \
                bulk.get(self.resource, resolved=True, scope='values') \
                if on_conflict == 'update' else []
            result_unresolved = \
                bulk.get(self.resource, resolved=False, scope='values')

        # Flush unresolved transient instances
        session.add_all(result_unresolved)
        await session.flush()

        # Merge resolved instances into the session
        result = result_unresolved
        for instance_staged in result_resolved:
            instance = await session.merge(instance_staged)
            result.append(instance)

        # Commit or rollback the transaction
        if dry_run:
            await session.rollback()
        else:
            if return_result:
                session.sync_session.expire_on_commit = False
            await session.commit()

        # Handle return result
        if not return_result:
            return None
        type_adapter = self.resource_schemas['read'].model_adapter
        with recursion_manager(mode='omit'):
            values = type_adapter.validate_python(result, from_attributes=True)
            return type_adapter.dump_python(
                values,
                mode='json',
                by_alias=True,
                include=include,
                exclude=exclude,
            )

    # MARK:> Delete

    @route.delete(
        path='',
        response_model=CRUDSpec.Read | None,
        response_model_serialization=False,
    )
    async def delete_one(
        self,
        session: AsyncSessionDep,
        selection: Key[CRUDSpec] = Selection(),
        return_result: bool = Body(
            default=False,
            title='Return result',
            description="""Whether to return the deleted result. If set to
                `False`, the transaction will be executed without returning
                the result.""",
        ),
        include: IncEx | None = Body(
            default=None,
            title='Include fields',
            description="""The fields to include in the query results.""",
            examples=[
                ['user.name', 'user.email'],
                {'user': ['name', 'email'], 'product': False},
            ],
        ),
        exclude: IncEx | None = Body(
            default=None,
            title='Exclude fields',
            description="""The fields to exclude from the query results.""",
            examples=[
                ['user.password', 'product.price'],
                {'user': ['password'], 'product': True},
            ],
        ),
        dry_run: bool = Body(
            default=False,
            title='Dry-run',
            description="""Whether to run the transaction in dry-run mode. If
                set to `True`, the transaction will be rolled back after
                execution.""",
        ),
    ) -> Any | None:
        """Delete a resource instance.

        Args:
            session: The async session dependency to use for the query.
            selection: The key selection dependency to resolve the query.
            return_result: Whether to return the deletion result.
            include: The fields to include in the query results.
            exclude: The fields to exclude from the query results.
            dry_run: Whether to run the transaction in dry-run mode.

        Returns:
            The deleted resource instance or ``None`` if return result is
            disabled, i.e., ``return_result=False``.
        """
        result = await selection.resolve(session)

        # Commit or rollback the transaction
        if dry_run:
            await session.rollback()
        else:
            if return_result:
                session.sync_session.expire_on_commit = False
            await session.delete(result)
            await session.commit()

        # Handle return result
        if not return_result:
            return None
        type_adapter = self.resource_schemas['read'].model_adapter
        with recursion_manager(mode='omit'):
            values = type_adapter.validate_python(result, from_attributes=True)
            return type_adapter.dump_python(
                values,
                mode='json',
                by_alias=True,
                include=include,
                exclude=exclude,
            )[0]

    @route.delete(
        path='',
        response_model=list[CRUDSpec.Read] | None,
        response_model_serialization=False,
    )
    async def delete_many(
        self,
        session: AsyncSessionDep,
        selection: KeyList[CRUDSpec] = Selection(),
        return_result: bool = Body(
            default=False,
            title='Return result',
            description="""Whether to return the deleted result. If set to
                `False`, the transaction will be executed without returning
                the result.""",
        ),
        include: IncEx | None = Body(
            default=None,
            title='Include fields',
            description="""The fields to include in the query results.""",
            examples=[
                ['user.name', 'user.email'],
                {'user': ['name', 'email'], 'product': False},
            ],
        ),
        exclude: IncEx | None = Body(
            default=None,
            title='Exclude fields',
            description="""The fields to exclude from the query results.""",
            examples=[
                ['user.password', 'product.price'],
                {'user': ['password'], 'product': True},
            ],
        ),
        filter: Annotated[Filter | None, Depends(filter_dependency)] = Body(
            default=None,
            title='Filter criteria',
            description="""The filter criteria to apply to the query. It is
                specified in the request body as a dictionary of field aliases
                with their corresponding filter criteria. Additionally, it can
                be specified directly in the query parameters using a dot
                notation for field aliases and tilde `~` character for filter
                criteria. For example, to filter results where the `user.name`
                field starts with `Al`, the filter criteria can be specified as
                `.user.name=like~Al*` in the query parameters.""",
            examples=[
                '.user.name=like~Al*',
                '.price=gt~1000',
                '.user.name=like~Al*&.price=gt~1000',
                {
                    'user': {'name': {'operator': 'like', 'value': 'Al*'}},
                    'price': {'operator': 'gt', 'value': 1000},
                },
            ],
        ),
        sort: Sort | None = Query(
            default=None,
            title='Sort criteria',
            description="""The sort criteria to apply to the query. It is
                specified in the query parameters as a comma-separated list of
                field aliases with an optional prefix of a minus sign `-` for
                descending order. For example, to sort results by the
                `user.name` field in descending order, the sort criteria can be
                specified as `user.name,-price` in the query parameters.
                Additionally, the direction and nulls position can be piped
                using a colon `:` character. For example, to sort results by
                the `price` field in ascending order with nulls first, the sort
                criteria can be specified as `price:asc:nf` in the query
                parameters.""",
            examples=['user.name,-price', 'price:asc:nf'],
        ),
        limit: int | None = Query(
            default=None,
            gt=0,
            title='Limit',
            description="""The maximum number of results to return. It is
                specified in the query parameters as an integer value. Defaults
                to the service configuration default page size if not
                specified.""",
            examples=[10, 20, 50],
        ),
        offset: int | None = Query(
            default=None,
            ge=0,
            title='Offset',
            description="""The number of results to skip before returning the
                results. It is specified in the query parameters as an integer
                value. Defaults to `0` if not specified.""",
        ),
        page: int | None = Query(
            default=None,
            gt=0,
            title='Page',
            description="""The page number to return results for. It is
                specified in the query parameters as an integer value. Defaults
                to the first page if not specified.""",
        ),
        page_size: int | None = Query(
            default=None,
            gt=0,
            title='Page size',
            description="""The number of results to return per page. It is
                specified in the query parameters as an integer value. The
                maximum page size is defined by the service configuration.
                Defaults to the service configuration default page size if not
                specified.""",
        ),
        dry_run: bool = Body(
            default=False,
            title='Dry-run',
            description="""Whether to run the transaction in dry-run mode. If
                set to `True`, the transaction will be rolled back after
                execution.""",
        ),
    ) -> Any | None:
        """Delete a collection of resource instances.

        Args:
            session: The async session dependency to use for the query.
            selection: The key selection dependency to resolve the query.
            return_result: Whether to return the deletion result.
            include: The fields to include in the query results.
            exclude: The fields to exclude from the query results.
            filter: The filter criteria to apply to the query.
            sort: The sort criteria to apply to the query.
            limit: The maximum number of results to return.
            offset: The number of results to skip before returning the results.
            page: The page number to return results for.
            page_size: The number of results to return per page.
            dry_run: Whether to run the transaction in dry-run mode.

        Returns:
            The collection of deleted resource instances or ``None`` if return
            result is disabled, i.e., ``return_result=False``.
        """
        # Resolve parameters
        limit = (
            limit
            or page_size
            or self.service_config.get(
                'page_size', self.resource_config.api_max_selection
            )
        )
        limit = min(limit, self.resource_config.api_max_selection)
        offset = offset or 0
        page = page or 1
        page_size = page_size or self.service_config.page_size

        # Build query
        query = selection.build_query(
            filter_criteria=filter,
            sort_criteria=sort,
        )
        query = query.offset((page - 1) * page_size + offset)
        query = query.limit(limit)

        # Execute query and return results
        buffer = await session.execute(query)
        result = buffer.unique().scalars().all()

        # Delete instances
        for instance in result:
            await session.delete(instance)

        # Commit or rollback the transaction
        if dry_run:
            await session.rollback()
        else:
            if return_result:
                session.sync_session.expire_on_commit = False
            await session.commit()

        # Handle return result
        if not return_result:
            return None

        # Handle result
        type_adapter = self.resource_schemas['read'].model_adapter
        with recursion_manager(mode='omit'):
            values = type_adapter.validate_python(result, from_attributes=True)
            return type_adapter.dump_python(
                values,
                mode='json',
                by_alias=True,
                include=include,
                exclude=exclude,
            )


# MARK: Utilities

def bind_service(
    service: BaseService,
    facade: ServiceFacade | ServiceWithSpecFacade,
    *,
    config: Mapping[str, Any] | None = None,
) -> None:
    """Bind the service to a service facade.

    It binds the service to a service facade, allowing the service to be used
    within the context of its facade owner.

    Args:
        service: The service instance to bind to the service facade.
        facade: The service facade to bind the service to.
        config: The service configuration to update when binding the service.
            It is used to override the default service configuration.
            Defaults to ``None``.
    """
    # Validate owner
    owner = service.service_owner
    if owner is facade:
        return
    if owner is not None:
        raise ValueError(
            f"Service instance {service!r} is already bound to a service "
            f"facade {owner.__class__.__qualname__!r}."
        )

    # Validate facade with specification
    spec = service.__config_spec__
    if spec is not None:
        if not isinstance(facade, ServiceWithSpecFacade):
            raise PlateformeError(
                f"Service facade {facade.__class__.__qualname__!r} must "
                f"implement the service with specification facade when a "
                f"service specification is defined.",
                code='services-invalid-config',
            )
        if service.service_config.auto_apply_spec \
                and spec not in getattr(facade, '__config_specs__', ()):
            facade._add_specs(spec)

    # Bind service to the facade and update configuration
    object.__setattr__(service, 'service_owner', facade)
    if config is not None:
        service.service_config.update(config)

    # Call post bind hook
    service.__post_bind__(facade)


def copy_service(service: BaseService) -> BaseService:
    """Copy and unbind the service from a service facade.

    It copies the service instance and unbinds it from the service facade,
    removing the service from the context of its current facade owner.

    Args:
        service: The service instance to unbind from the service facade.

    Returns:
        The copied service instance.
    """
    service = deepcopy(service)

    # Unbind if service is bound to a facade
    if service.service_owner is not None:
        for name, method in service.service_methods.items():
            setattr(service, name, method)
        object.__setattr__(service, 'service_owner', None)
    return service


def load_service(service: BaseService) -> dict[str, Callable[..., Any]] | None:
    """Load the service implementation.

    It loads the service implementation by validating the service owner and
    checking whether the service owner implements the service specification
    protocol. If the service owner is not concrete or does not implement the
    service specification protocol, it raises an error.

    Finally, it wraps the service methods with the appropriate parameter and
    return annotations based on the provided specification and resource.

    Args:
        service: The service instance to load.

    Returns:
        A dictionary of public methods of the service.

    Raises:
        PlateformeError: If the service owner is not concrete or does not
            implement the service specification protocol.
    """
    # Validate owner
    owner = service.service_owner
    if owner is None:
        return None

    # Validate specification and implementation
    spec = service.__config_spec__
    if spec and not isimplclass_lenient(
        owner,
        spec,
        predicate=inspect.isclass,
        resolver=make_getattr_resolver(
            fallback_attr='resource_schemas',
            fallback_condition=inspect.isclass,
            fallback_transformer=lambda s: to_name_case(s, ('all', None)),
        ),
    ):
        raise PlateformeError(
            f"Service owner {owner.__class__.__qualname__!r} must be concrete "
            f"and implement the service specification {spec.__qualname__!r} "
            f"protocol.",
            code='services-invalid-config',
        )

    # Wrap service methods
    if service.service_methods is not None:
        for name, method in service.service_methods.items():
            wrapped_method = _wrap_service_method(service, method)
            setattr(service, name, wrapped_method)

    # Call post load hook
    service.__post_load__(owner)

    return _collect_service_methods(service)


def unbind_service(service: BaseService) -> None:
    """Unbind the service from a service facade.

    It unbinds the service from a service facade, removing the service from the
    context of its current facade owner.

    Args:
        service: The service instance to unbind from the service facade.
    """
    # Check if service is bound to a facade
    if service.service_owner is None:
        raise ValueError(
            f"Service instance {service!r} is not bound to a service facade."
        )

    # Unbind service from the facade and reset configuration
    for name, method in service.service_methods.items():
        setattr(service, name, method)
    object.__setattr__(service, 'service_owner', None)
    service.service_config = service.__config__.copy()


def validate_service_method(
    method: FunctionLenientType,
    config: Mapping[str, Any],
) -> bool:
    """Validate a service method.

    It validates a service method based on the provided configuration and
    returns whether the method should be included or excluded.

    Args:
        method: The service method to validate.
        config: The service configuration to use for method validation.

    Returns:
        Whether the service method should be included or excluded.
    """
    if not config:
        return True

    # Helper function to check whether the value matches the condition
    def check_value(condition: Any, value: str) -> bool | None:
        if condition is None:
            return None
        if isinstance(condition, str):
            return value == condition
        return value in condition

    # Check method name
    name = method.__name__
    if 'include' in config and check_value(config['include'], name) is False:
        return False
    if 'exclude' in config and check_value(config['exclude'], name) is True:
        return False

    # Check method endpoint
    if is_endpoint(method):
        route = getattr(method, '__config_route__')
        assert isinstance(route, APIRouteConfig)

        # Check method mode
        if 'include_mode' in config \
                and check_value(config['include_mode'], route.mode) is False:
            return False
        if 'exclude_mode' in config \
                and check_value(config['exclude_mode'], route.mode) is True:
            return False

        # Check method request
        if route.mode == 'request':
            assert route.methods is not None
            if config.get('include_method', None) is not None and not any(
                check_value(config['include_method'], m)
                for m in route.methods
            ):
                return False
            if config.get('exclude_method', None) is not None and any(
                check_value(config['exclude_method'], m)
                for m in route.methods
            ):
                return False

    return True


def _collect_service_methods(
    service: BaseService,
) -> dict[str, Callable[..., Any]]:
    """Collect the public methods of a service."""
    config = service.service_config.entries()
    methods: dict[str, Callable[..., Any]] = {}
    for name, method in service.service_methods.items():
        if validate_service_method(method, config):
            methods[name] = getattr(service, name)
    return methods


def _wrap_service_method(
    service: BaseService,
    method: FunctionLenientType,
) -> Callable[..., Any]:
    """Wrap a service method.

    It wraps a service method with the appropriate parameter and return
    annotations based on the provided specification and resource.

    Args:
        service: The service to wrap the method for.
        method: The service method to wrap.

    Returns:
        The wrapped service method.
    """
    # Helper to resolve specification schema models in annotations
    def resolve_specs(
        annotation: Any, *, root_schemas: tuple[str, ...] | None = None
    ) -> Any:
        if service.__config_spec__ is None:
            return annotation
        assert is_resource(service.service_owner)
        return resolve_schema_model(
            annotation,
            root_schemas=root_schemas,
            with_spec=(service.__config_spec__, service.service_owner),
        )

    # Retrieve endpoint configuration and method function
    config = getattr(method, '__config_route__', None)
    if isinstance(method, (classmethod, staticmethod)):
        func = method.__func__
    else:
        func = method

    # Update endpoint response model annotation
    if config is not None:
        assert isinstance(config, APIRouteConfig)
        config = config.copy()
        if config.response_model is not None:
            config.response_model = resolve_specs(
                config.response_model, root_schemas=('read', 'model')
            )

    # Retrieve method function signature and parameters
    signature = inspect.signature(func)
    parameters = list(signature.parameters.values())
    if not isinstance(method, staticmethod):
        parameters = parameters[1:]

    # Update method function parameter annotations
    for count, parameter in enumerate(parameters):
        parameters[count] = parameter.replace(
            annotation=resolve_specs(parameter.annotation)
        )

    # Update method function return annotation
    return_annotation = resolve_specs(
        signature.return_annotation, root_schemas=('read', 'model')
    )

    # Wrap method function
    if isinstance(method, staticmethod):
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)
    elif isinstance(method, classmethod):
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(service.__class__, *args, **kwargs)
    else:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(service, *args, **kwargs)  # type: ignore

    # Update configuration and signature
    setattr(wrapper, '__config_owner__', service)
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
