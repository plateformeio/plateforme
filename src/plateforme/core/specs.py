# plateforme.core.specs
# ---------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing schema within the Plateforme
framework using Pydantic features.
"""

import typing
import uuid
from collections.abc import Sequence
from typing import Any, Literal, Protocol, Self, Type, TypeVar

from .errors import PlateformeError
from .functions import with_caller_context
from .patterns import to_name_case
from .schema.fields import ComputedFieldInfo, FieldDefinition, FieldLookup
from .schema.json import GenerateJsonSchema, JsonSchemaMode, JsonSchemaSource
from .schema.models import (
    BaseModel,
    DiscriminatedModelType,
    ModelType,
    collect_models,
)
from .schema.types import TypeAdapterList
from .typing import (
    Annotation,
    ClassMethodType,
    get_cls_hierarchy,
    is_resource,
)

if typing.TYPE_CHECKING:
    from .database.orm import InstrumentedAttribute, ORMOption
    from .database.sessions import AsyncSession
    from .expressions import IncEx
    from .packages import Package
    from .resources import (
        BaseResource,
        ResourceConfig,
        ResourceFieldInfo,
        ResourceType,
    )
    from .selectors import Key

__all__ = (
    'BaseSpec',
    'CRUDSpec',
    'Spec',
    'SpecFacade',
    'SpecType',
    'apply_spec',
    'resolve_schema_model',
)


Spec = TypeVar('Spec', bound='BaseSpec')
"""A type variable for a specification class."""


SpecType = Type['BaseSpec']
"""A type alias for a specification class."""


# MARK: Service Facade

@typing.runtime_checkable
class SpecFacade(Protocol):
    """A specification facade protocol."""

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
        """Register a schema within the facade.

        It constructs a new resource schema model based on the provided field
        definitions and lookup filters. The resource schema model is registered
        within the facade and can be used by services to interact with the
        facade instances.

        Args:
            __schema_name: The name of the new resource schema model.
            __schema_fallback: The fallback schema aliases to use when
                resolving the resource schema model. Defaults to ``None``.
            __force__: Whether to force the registration of the resource schema
                model even if it already exists and the original owner is not
                the current facade. Defaults to ``False``.
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
        ...


# MARK: Base Specification

@typing.runtime_checkable
class BaseSpec(Protocol):
    """The base specification protocol for resources.

    This protocol is used to define the specification for resources. It can be
    derived to define custom model schemas either by specifying static nested
    model classes within the base specification, or by implementing the
    `__apply__` method to dynamically generate model schemas based on the
    resource provided by the specification facade or add custom logic.

    Those models are then used to define the validation, serialization, and
    deserialization logic for resources within services.
    """

    @classmethod
    def __apply__(cls, facade: SpecFacade) -> None:
        """Hook method called when applying the specifications to a facade.

        Subclasses can override this method to dynamically generate model
        schemas for the service facade or add custom logic to the facade.

        Args:
            owner: The service facade owner to bind the model schemas to.

        Note:
            This method is invoked before a service that implements the
            specification is bound to a service facade when the
            `auto_apply_spec` configuration is enabled.
        """
        models = collect_models(cls)
        for model in models:
            facade._register_schema(model.__qualname__, __base__=model)

    # Class fields
    id: int | uuid.UUID | None
    type_: str

    # Class attributes
    resource_adapter: TypeAdapterList['BaseResource']
    resource_attributes: dict[str, 'InstrumentedAttribute[Any]']
    resource_computed_fields: dict[str, ComputedFieldInfo]
    resource_config: 'ResourceConfig'
    resource_fields: dict[str, 'ResourceFieldInfo']
    resource_identifiers: tuple[set[str]]
    resource_indexes: tuple[set[str]]
    resource_package: 'Package'
    resource_schemas: dict[str, DiscriminatedModelType] = {}

    # Instance attributes
    resource_extra: dict[str, Any] | None
    resource_fields_set: set[str]
    resource_model: BaseModel

    # Class methods
    @classmethod
    def resource_construct(
        cls,
        _fields_set: set[str] | None = None,
        _model: BaseModel | None = None,
        **data: Any,
    ) -> Self:
        ...

    @classmethod
    def resource_json_schema(
        cls,
        by_alias: bool = True,
        ref_template: str = ...,
        schema_generator: type[GenerateJsonSchema] = ...,
        mode: JsonSchemaMode = 'validation',
        source: JsonSchemaSource = 'key',
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
    ) -> Self:
        ...

    @classmethod
    def resource_validate_json(
        cls,
        json_data: str | bytes | bytearray,
        *,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> Self:
        ...

    @classmethod
    def resource_validate_strings(
        cls,
        obj: Any,
        *,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> Self:
        ...

    # Instance methods
    async def resource_add(
        self, *, session: 'AsyncSession | None' = None
    ) -> None:
        ...

    def resource_copy(
        self,
        *,
        update: dict[str, Any] | None = None,
        deep: bool = False,
    ) -> Self:
        ...

    async def resource_delete(
        self, *, session: 'AsyncSession | None' = None,
    ) -> None:
        ...

    def resource_dump(
        self,
        *,
        mode: Literal['json', 'python', 'raw'] | str = 'python',
        include: 'IncEx | None' = None,
        exclude: 'IncEx | None' = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool = True,
    ) -> dict[str, Any]:
        ...

    def resource_dump_json(
        self,
        *,
        indent: int | None = None,
        include: 'IncEx | None' = None,
        exclude: 'IncEx | None' = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: bool = True,
    ) -> str:
        ...

    def resource_keychain(self) -> tuple['Key[Self]', ...]:
        ...

    async def resource_merge(
        self,
        *,
        load: bool = True,
        options: Sequence['ORMOption'] | None = None,
        session: 'AsyncSession | None' = None,
    ) -> Self:
        ...

    def resource_post_init(
        self, __context: dict[str, Any] | None = None
    ) -> None:
        ...

    def resource_revalidate(
        self,
        *,
        force: bool = False,
        raise_errors: bool = True,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> bool | None:
        ...

    def resource_update(
        self,
        obj: Any,
        *,
        update: dict[str, Any] | None = None,
        from_attributes: bool | None = None,
    ) -> None:
        ...

    # Schemas
    class Model:
        id: int | uuid.UUID | None
        type_: str | None
        ...


# MARK: CRUD Specification

class CRUDSpec(BaseSpec):
    """The CRUD specification."""

    class Create(BaseModel):
        id: int | uuid.UUID | None
        type_: str | None
        ...

    class Read(BaseModel):
        id: int | uuid.UUID | None
        type_: str | None
        ...

    class Update(BaseModel):
        ...

    class Upsert(BaseModel):
        id: int | uuid.UUID | None
        type_: str | None
        ...

    @classmethod
    def __apply__(cls, facade: SpecFacade) -> None:
        """Registers the CRUD specification for the specification facade."""

        # Create schema
        facade._register_schema(
            'Create',
            __collect__=(
                {
                    'include': {'alias': 'type'},
                    'partial': True,
                },
                {
                    'exclude': {'init': False},
                    'override': {
                        'include': {
                            'is_cascading': (['save-update'], False),
                        },
                        'update': {
                            'target_ref': True,
                            'target_schemas': False,
                        },
                    },
                },
            ),
        )

        # Read schema
        facade._register_schema(
            'Read',
            __collect__=(
                {
                    'computed': True,
                    'exclude': {
                        'exclude': True,
                        'is_eagerly': False,
                    },
                    'partial': True,
                    'override': {
                        'include': {'linked': True},
                        'default': {'target_ref': False},
                    },
                },
            ),
        )

        # Update schema
        facade._register_schema(
            'Update',
            __collect__=(
                {
                    'exclude': {'frozen': False},
                    'partial': True,
                    'override': {
                        'include': {
                            'is_cascading': (['save-update'], False),
                        },
                        'update': {
                            'target_ref': True,
                            'target_schemas': False,
                        },
                    },
                },
            ),
        )

        # Upsert schema
        facade._register_schema(
            'Upsert',
            __collect__=(
                {
                    'include': {'alias': 'type'},
                    'partial': True,
                },
                {
                    'exclude': {'init': False},
                    'partial': True,
                    'override': {
                        'include': {
                            'is_cascading': (['save-update'], False),
                        },
                        'update': {
                            'target_ref': True,
                            'target_schemas': False,
                        },
                    },
                },
            ),
        )


# MARK: Utilities

@with_caller_context
def apply_spec(spec: SpecType, facade: SpecFacade) -> None:
    """Apply the specification to the facade.

    Args:
        spec: The specification to apply.
        facade: The facade to apply the specification to.
    """
    spec.__apply__(facade)


def resolve_schema_model(
    annotation: Any,
    *,
    root_schemas: tuple[str, ...] | None = None,
    with_spec: tuple['SpecType', 'ResourceType'] | None = None,
) -> Any:
    """Resolve the schema models from the annotation.

    Args:
        annotation: The annotation to resolve.
        root_schemas: The schema model aliases to use as the root schema. When
            the resolved path is empty, the resolved root type is returned if
            set to ``None``, otherwise the root schemas are used in order of
            precedence to match a valid schema model. Defaults to ``None``.
        with_spec: The specification and resource type to use for resolving
            the schema models. When provided, it should be a tuple containing
            the specification and the resource type to use for resolving the
            schema models. When set to ``None``, the schema models within the
            annotation are resolved for all resources. Defaults to ``None``.

    Returns:
        The annotation with the resolved schema models.
    """
    if with_spec:
        spec, resource = with_spec

    def ann_test(ann: Any) -> tuple[bool, Any]:
        if not isinstance(ann, type):
            return False, ...

        hierarchy = get_cls_hierarchy(ann)
        root = next(iter(hierarchy.values()))
        path = next(reversed(hierarchy.keys()))

        if with_spec:
            return root is spec, (root, path)
        return is_resource(root), (root, path)

    def ann_resolver(_: Any, info: tuple[Any, str]) -> Any:
        root, path = info
        owner = resource if with_spec else root

        if path == '':
            if root_schemas is None:
                return owner
            schema_lookup = root_schemas
        else:
            schema_lookup = (to_name_case(path),)

        for schema_alias in schema_lookup:
            if schema_alias not in owner.resource_schemas:
                continue
            return owner.resource_schemas[schema_alias]

        raise PlateformeError(
            f"Schema owner {owner.__qualname__!r} does not define a valid "
            f"schema model for alias {schema_alias!r}.",
            code='schema-resolution-failed',
        )

    return Annotation.replace(
        annotation, test=ann_test, resolver=ann_resolver,
    )
