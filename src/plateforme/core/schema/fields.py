# plateforme.core.schema.fields
# -----------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing fields information for
configuration wrappers, models and resources within the Plateforme framework
using Pydantic features.

The `FieldInfo` class is an extension of Pydantic's field information, it
incorporates additional parameters like `unique`, `linked`, `target`, and
others, enabling the definition of fields with extended behaviors specific to
the Plateforme framework.

The `Field` and `ConfigField` function creates and extends field information
with Pydantic's validation system, it allows the definition of configuration
wrappers, models and resources attributes with additional behaviors specific to
the Plateforme framework.

Examples:
    >>> from plateforme import BaseModel, Field
    ...
    >>> class FooModel(BaseModel):
    ...     name: str = Field(
    ...         ...,
    ...         unique=True,
    ...         title='Foo Model',
    ...         description='Name of the foo instance',
    ...     )
    ...
    >>> class BarModel(BaseModel):
    ...     name: str = Field(
    ...         ...,
    ...         unique=True,
    ...         title='Bar Model',
    ...         description='Name of the bar instance',
    ...     )
    ...     foo: FooModel | None = Field(title='Foo Reference')

Note:
    See also then`BaseModel` and `BaseResource` for more information on data
    modeling features, including associations between models implemented into
    the field information.
"""

import dataclasses
import inspect
import re
import typing
from collections.abc import Iterable
from copy import copy
from types import NoneType, UnionType
from typing import (
    AbstractSet,
    Annotated,
    Any,
    Callable,
    ClassVar,
    Final,
    ForwardRef,
    Generic,
    Literal,
    Self,
    TypeVar,
    Union,
    Unpack,
)

from pydantic._internal import _decorators
from pydantic.fields import (
    ComputedFieldInfo as _ComputedFieldInfo,
    FieldInfo as _FieldInfo,
    PrivateAttr,
)
from typing_extensions import TypedDict

from ..database.orm import CascadeRule, LoadRule, RelationshipProperty
from ..database.schema import Column
from ..database.types import BaseTypeEngine, TypeEngine
from ..deprecated import Deprecated
from ..errors import PlateformeError
from ..expressions import IncExPredicate
from ..modules import resolve_forwardref_fullname
from ..patterns import RegexPattern, to_name_case, to_path_case, to_title_case
from ..representations import PlainRepresentation, ReprArgs, Representation
from ..types.utils import resolve_data_type_engine
from ..typing import (
    Annotation,
    Deferred,
    Object,
    Undefined,
    eval_type_lenient_deep,
    has_forwardref,
    has_resource,
    is_abstract,
    is_annotated,
    is_finalvar,
    is_model,
    is_optional,
    is_private,
    is_resource,
    is_selector,
)
from ..utils import get_config
from .aliases import AliasChoices, AliasGenerator, AliasPath
from .json import JsonSchemaDict, JsonSchemaExtra
from .types import Discriminator, Schema

if typing.TYPE_CHECKING:
    from ..associations import Association
    from ..resources import ResourceFieldInfo, ResourceType

# This should be replaced by "property[T]" and "cached_property[T]" for
# computed fields but "property" is not generic unlike "cached_property".
# See https://github.com/python/typing/issues/985 for more information.
_TProperty = TypeVar('_TProperty')

__all__ = (
    'ComputedFieldInfo',
    'ConfigField',
    'Field',
    'FieldDefinition',
    'FieldInfo',
    'FieldInfoDict',
    'FieldInfoMeta',
    'FieldLookup',
    'BackrefFieldInfoDict',
    'PrivateAttr',
    'computed_field',
)


FieldDefinition = tuple[type[Any], 'Any | FieldInfo[Any]']
"""A type alias for a field definition."""


# MARK: Field Configuration

class SourceFieldInfoDict(TypedDict, Generic[Object], total=False):
    """A source field information dictionary.

    A dictionary that holds the source configuration parameters for a field
    information instance. It is not meant to be exposed for parameterization
    to the user directly.
    """

    source: str | None
    """The source representation of the field definition.
    Defaults to ``None``."""

    owner: type[Object] | None
    """The owner of the field. It is inferred from the class where the field is
    defined if available else it defaults to ``None``."""

    name: str | None
    """The name of the field. It must adhere to a specific ``ALIAS`` pattern as
    defined in the framework's regular expressions repository.
    Defaults to ``None``."""

    annotation: type[Any] | None
    """The type annotation of the field. Defaults to ``Undefined``."""

    default: Any
    """The default value of the field. If not set and no default factory is
    provided, the field is considered required. Defaults to ``Undefined``."""

    linked: bool | None
    """Whether or not the field is linked. Defaults to ``None``."""

    collection: Literal['list', 'set'] | None
    """The collection type of the target association. It can be either an
    unconstrained collection ``list``, or a collection of unique elements
    ``set``, otherwise it defaults to ``None`` if the  association is not a
    collection."""

    target: 'ResourceType | str | None'
    """The linked field target `BaseResource` object type.
    Defaults to ``None``."""

    association: 'Association | None'
    """The `Association` object that defines the association between the owner
    and target resources. Defaults to ``None``."""


class BaseFieldInfoDict(TypedDict, total=False):
    """A base field information dictionary.

    A dictionary that holds the base configuration parameters for a field
    information instance. It includes the basic parameters that are common to
    all field information instances.
    """

    default_factory: Callable[[], Any] | None
    """The factory function used to construct the default value of the field.
    If both the default value and the default factory are set, an error is
    raised. Defaults to ``None``."""

    alias: str | None
    """The alias name of the field. It must adhere to a specific ``ALIAS``
    pattern as defined in the framework's regular expressions repository.
    Defaults to ``None``."""

    alias_priority: int | None
    """The priority of the field's alias. This affects whether an alias
    generator is used or not. Defaults to ``None``."""

    title: str | None
    """The human-readable name of the field. It must adhere to a specific
    ``TITLE`` pattern as defined in the framework's regular expressions
    repository. Defaults to ``None``."""

    description: str | None
    """The description of the field. Defaults to ``None`` and uses the
    function's docstring if available."""

    examples: list[Any] | None
    """List of examples of the field. Defaults to ``None``."""

    deprecated: Deprecated | str | bool | None
    """A deprecation message, an instance of `Deprecated`, or a boolean. If
    ``True``, a default deprecation message will be emitted when accessing the
    field. Defaults to ``None``."""

    frozen: bool | None
    """Whether or not the field is frozen. Defaults to ``None``."""

    repr: bool
    """Whether or not to include the field in the representation.
    Defaults to ``True``."""

    init: bool
    """Whether the field should be included in the constructor of the
    dataclass. Defaults to ``True``."""

    init_var: bool | None
    """Whether the field should only be included in the constructor of the
    dataclass, and not stored. Defaults to ``None``."""

    kw_only: bool | None
    """Whether or not the field should be a keyword-only argument in the
    constructor of the model. Defaults to ``None``."""


class ModelFieldInfoDict(TypedDict, total=False):
    """A model field information dictionary.

    A dictionary that holds the model configuration parameters for a field
    information instance. It includes additional parameters that are specific
    to Pydantic field information.
    """

    validation_alias: str | AliasPath | AliasChoices | None
    """The validation alias name of the field. It must adhere to a specific
    ``ALIAS`` pattern as defined in the framework's regular expressions
    repository. Defaults to ``None`` (alias name of the field)."""

    serialization_alias: str | None
    """The serialization alias name of the field. It must adhere to a specific
    ``ALIAS`` pattern as defined in the framework's regular expressions
    repository. Defaults to ``None`` (alias name of the field)."""

    exclude: bool | None
    """Whether or not to exclude the field from the model serialization.
    Defaults to ``None``."""

    discriminator: str | Discriminator | None
    """Field name for discriminating the type in a tagged union.
    Defaults to ``None``."""

    json_schema_extra: JsonSchemaExtra | None
    """Dictionary or callable to provide extra JSON schema properties.
    Defaults to ``None``."""

    validate_default: bool | None
    """Whether or not to validate the default value of the field.
    Defaults to ``None``."""

    pattern: str | None
    """A regular expression pattern that the field value must match.
    Defaults to ``None``."""

    strict: bool | None
    """Whether or not to enforce strict validation of the field value.
    Defaults to ``None``."""

    gt: float | None
    """The minimum value of the field. Defaults to ``None``."""

    ge: float | None
    """The minimum value of the field, inclusive. Defaults to ``None``."""

    lt: float | None
    """The maximum value of the field. Defaults to ``None``."""

    le: float | None
    """The maximum value of the field, inclusive. Defaults to ``None``."""

    multiple_of: float | None
    """The value must be a multiple of this number. Defaults to ``None``."""

    allow_inf_nan: bool | None
    """Whether or not to allow infinity and NaN values.
    Defaults to ``None``."""

    max_digits: int | None
    """The maximum number of digits in the field value.
    Defaults to ``None``."""

    decimal_places: int | None
    """The number of decimal places in the field value.
    Defaults to ``None``."""

    min_length: int | None
    """The minimum length of the field value. Defaults to ``None``."""

    max_length: int | None
    """The maximum length of the field value. Defaults to ``None``."""

    union_mode: Literal['smart', 'left_to_right'] | None
    """The union mode for the field value. Defaults to ``None``."""

    recursive_guard: str | None
    """A recursive guard to handle infinite recursion when validating and
    serializing fields. Defaults to ``None``."""


class ResourceFieldInfoDict(TypedDict, total=False):
    """A resource field information dictionary.

    A dictionary that holds the resource configuration parameters for a field
    information instance. It includes additional parameters that are specific
    to resource field information within the Plateforme framework.
    """

    slug: str | None
    """The slug name of the field. It must adhere to a specific ``SLUG``
    pattern as defined in the framework's regular expressions repository.
    Defaults to ``None``."""

    unique: bool | None
    """Whether or not the field is unique. Defaults to ``None``."""

    indexed: bool | None
    """Whether or not the field is indexed. Defaults to ``None``."""

    target_ref: bool | None
    """Whether the field can accept a reference to the target resource instead
    of the resource schema model itself. Defaults to ``None``."""

    target_schemas: tuple[str, ...] | bool | None
    """Either a tuple of the linked field target `DiscriminatedModel` schema
    models to use for the annotation resolution, or a boolean to indicate
    whether the target schema models should be resolved.
    Defaults to ``None``."""

    association_alias: str | None
    """The association alias identifier. By default, this is determined by
    concatenating the owner and target resource alias with an underscore (see
    the `Association` class). Defaults to ``None``."""

    rel_attribute: str | None
    """The attribute name of the foreign key column implemented within the
    owner resource. This is optional and only applies in a scenario where a
    foreign key column is required for managing the association. If the field
    is not linked or the association (like a many-to-many association) does not
    require a direct foreign key column, this parameter defaults to ``None``.
    Conversely, if a link exists and the association necessitates a foreign key
    column (as per the two-way association analysis), this parameter defaults
    to the alias of the linked field, appended with ``_id``.
    Defaults to ``None``."""

    rel_backref: 'BackrefFieldInfoDict | None'
    """The corresponding back referencing target linked field counterpart of
    the association. This argument can be used to define a back reference
    configuration using a `BackrefFieldInfoDict` dictionary when no counterpart
    exists in the target resource. This is useful in scenarios where there is
    no control over the target resource definition, and the back reference must
    be implemented in the owner resource. Otherwise, it is recommended to
    define the back reference directly in the target resource.
    If the target resource does not have a counterpart linked field defined for
    the given association, the field information attribute initializes to
    ``None``, otherwise it stores the target counterpart `ResourceFieldInfo`
    instance, either generated from the target resourcedefinition, or by the
    provided back reference dictionary configuration. Defaults to ``None``."""

    rel_cascade: str | bool | None
    """The cascade options for the relationship. The possible cascading options
    are ``'delete'``, ``'delete-orphan'``, ``'expunge'``, ``'merge'``,
    ``'refresh-expire'``, ``'save-update'``, and ``all``, where the latter is a
    shorthand for ``'save-update, merge, refresh-expire, expunge, delete'``,
    and is often used as in ``'all, delete-orphan'`` to indicate that related
    objects should follow along with the parent object in all cases, and be
    deleted when de-associated.
    Defaults to ``None`` for non-linked fields, otherwise ``True`` for linked
    fields which resolves to:
    - ``'save-update, merge'`` when the association is bidirectional,
    - ``'..., delete, delete-orphan'`` when the target resource link is
        identifying,
    - ``'..., refresh-expire, expunge'`` when the target resource link is
        indexing."""

    rel_load: LoadRule | bool | None
    """The lazy loading options for the relationship.
    Defaults to ``None`` for non-linked fields, otherwise ``True`` for linked
    fields which resolves to:
    - ``'joined'`` when the association is indexing one of the resources,
    - ``'selectin'`` when the resource owner field is not a collection,
    - ``'select'`` otherwise (lazy loading)."""

    rel_extra: dict[str, Any] | None
    """Additional association relationship configuration parameters.
    Defaults to ``None``."""

    column_extra: dict[str, Any] | None
    """Additional column configuration parameters. Defaults to ``None``."""

    data_type: TypeEngine | None
    """The data type engine to use for the field. It is automatically inferred
    from the field annotation if not explicitly set. Defaults to ``None``."""

    data_collation: str | None
    """The collation of the field used for strings within the database.
    Defaults to ``None``."""

    data_none_as_null: bool | None
    """Whether or not to treat ``None`` as ``NULL`` in the database for JSON
    data types. Defaults to ``None``."""

    data_extra: dict[str, Any] | None
    """Additional data column configuration parameters.
    Defaults to ``None``."""


class BackrefFieldInfoDict(TypedDict, total=False):
    """A backref field information configuration dictionary.

    A dictionary that holds the configuration parameters for a field
    information back reference instance. It is used to define the keyword
    arguments when creating a field information in a scenario where the target
    resource does not have a counterpart linked field for a given association.
    """

    name: str | None
    """The name of the field. It must adhere to a specific ``ALIAS`` pattern as
    defined in the framework's regular expressions repository.
    Defaults to ``None``."""

    default: Any
    """The default value of the field. If not set and no default factory is
    provided, the field is considered required. Defaults to ``Undefined``."""

    default_factory: Callable[[], Any] | None
    """The factory function used to construct the default value of the field.
    If both the default value and the default factory are set, an error is
    raised. Defaults to ``None``."""

    alias: str | None
    """The alias name of the field. It must adhere to a specific ``ALIAS``
    pattern as defined in the framework's regular expressions repository.
    Defaults to ``None``."""

    alias_priority: int | None
    """The priority of the field's alias. This affects whether an alias
    generator is used or not. Defaults to ``None``."""

    title: str | None
    """The human-readable name of the field. It must adhere to a specific
    ``TITLE`` pattern as defined in the framework's regular expressions
    repository. Defaults to ``None``."""

    description: str | None
    """The description of the field. Defaults to ``None`` and uses the
    function's docstring if available."""

    examples: list[Any] | None
    """List of examples of the field. Defaults to ``None``."""

    deprecated: Deprecated | str | bool | None
    """A deprecation message, an instance of `Deprecated`, or a boolean. If
    ``True``, a default deprecation message will be emitted when accessing the
    field. Defaults to ``None``."""

    frozen: bool | None
    """Whether or not the field is frozen. Defaults to ``None``."""

    repr: bool
    """Whether or not to include the field in the representation.
    Defaults to ``True``."""

    init: bool
    """Whether the field should be included in the constructor of the
    dataclass. Defaults to ``True``."""

    init_var: bool | None
    """Whether the field should only be included in the constructor of the
    dataclass, and not stored. Defaults to ``None``."""

    kw_only: bool | None
    """Whether or not the field should be a keyword-only argument in the
    constructor of the model. Defaults to ``None``."""

    validation_alias: str | AliasPath | AliasChoices | None
    """The validation alias name of the field. It must adhere to a specific
    ``ALIAS`` pattern as defined in the framework's regular expressions
    repository. Defaults to ``None`` (alias name of the field)."""

    serialization_alias: str | None
    """The serialization alias name of the field. It must adhere to a specific
    ``ALIAS`` pattern as defined in the framework's regular expressions
    repository. Defaults to ``None`` (alias name of the field)."""

    exclude: bool | None
    """Whether or not to exclude the field from the model serialization.
    Defaults to ``None``."""

    discriminator: str | Discriminator | None
    """Field name for discriminating the type in a tagged union.
    Defaults to ``None``."""

    json_schema_extra: JsonSchemaExtra | None
    """Dictionary or callable to provide extra JSON schema properties.
    Defaults to ``None``."""

    validate_default: bool | None
    """Whether or not to validate the default value of the field.
    Defaults to ``None``."""

    recursive_guard: str | None
    """A recursive guard to handle infinite recursion when validating and
    serializing fields. Defaults to ``None``."""

    slug: str | None
    """The slug name of the field. It must adhere to a specific ``SLUG``
    pattern as defined in the framework's regular expressions repository.
    Defaults to ``None``."""

    unique: bool | None
    """Whether or not the field is unique. Defaults to ``None``."""

    indexed: bool | None
    """Whether or not the field is indexed. Defaults to ``None``."""

    collection: Literal['list', 'set'] | None
    """The collection type of the target association. It can be either an
    unconstrained collection ``list``, or a collection of unique elements
    ``set``, otherwise it defaults to ``None`` if the association is not a
    collection."""

    rel_attribute: str | None
    """The attribute name of the foreign key column implemented within the
    owner resource. This is optional and only applies in a scenario where a
    foreign key column is required for managing the association. If the field
    is not linked or the association (like a many-to-many association) does not
    require a direct foreign key column, this parameter defaults to ``None``.
    Conversely, if a link exists and the association necessitates a foreign key
    column (as per the two-way association analysis), this parameter defaults
    to the alias of the linked field, appended with ``_id``.
    Defaults to ``None``."""

    rel_cascade: str | bool | None
    """The cascade options for the relationship. The possible cascading options
    are ``'delete'``, ``'delete-orphan'``, ``'expunge'``, ``'merge'``,
    ``'refresh-expire'``, ``'save-update'``, and ``all``, where the latter is a
    shorthand for ``'save-update, merge, refresh-expire, expunge, delete'``,
    and is often used as in ``'all, delete-orphan'`` to indicate that related
    objects should follow along with the parent object in all cases, and be
    deleted when de-associated.
    Defaults to ``None`` for non-linked fields, otherwise ``True`` for linked
    fields which resolves to:
    - ``'save-update, merge'`` when the association is bidirectional,
    - ``'..., delete, delete-orphan'`` when the target resource link is
        identifying,
    - ``'..., refresh-expire, expunge'`` when the target resource link is
        indexing."""

    rel_load: LoadRule | bool | None
    """The lazy loading options for the relationship.
    Defaults to ``None`` for non-linked fields, otherwise ``True`` for linked
    fields which resolves to:
    - ``'joined'`` when the association is indexing one of the resources,
    - ``'selectin'`` when the resource owner field is not a collection,
    - ``'select'`` otherwise (lazy loading)."""

    rel_extra: dict[str, Any] | None
    """Additional association relationship configuration parameters.
    Defaults to ``None``."""

    column_extra: dict[str, Any] | None
    """Additional column configuration parameters. Defaults to ``None``."""


class FieldInfoDict(
    SourceFieldInfoDict[Object],
    BaseFieldInfoDict,
    ModelFieldInfoDict,
    ResourceFieldInfoDict,
    Generic[Object],
    total=False,
):
    """A global field information configuration dictionary.

    A dictionary that provides all the configuration parameters for a field
    information instance within the Plateforme framework. It combines the
    `SourceFieldInfoDict`, `BaseFieldInfoDict`,  `ModelFieldInfoDict`, and
    `ResourceFieldInfoDict` configuration dictionaries into a single
    comprehensive dictionary.
    """
    pass


class FieldInfoFromConfigDict(
    BaseFieldInfoDict,
    total=False,
):
    """A field information configuration dictionary for a config function.

    It is used to define a field information instance with the `ConfigField`
    function for configuration wrappers.
    """
    pass


class FieldInfoFromFieldDict(
    BaseFieldInfoDict,
    ModelFieldInfoDict,
    ResourceFieldInfoDict,
    total=False,
):
    """A field information configuration dictionary for a field function.

    It is used to define a field information instance with the `Field` function
    for models and resources.
    """
    pass


# MARK: Field Information Metaclass

class FieldInfoMeta(type):
    """Meta class for the field information class."""

    def __new__(
        mcls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> type:
        """Create a new field information meta class."""
        cls = super().__new__(mcls, name, bases, namespace, *args, **kwargs)

        # Helper function to extract configuration attributes from slots
        def extract_attributes(slots: Iterable[str] | None) -> set[str]:
            extracted: set[str] = set()
            if slots is None:
                return extracted
            for slot in slots:
                if not slot.startswith('_'):
                    extracted.add(slot)
            return extracted

        # Extract configuration attributes from slots
        attributes: set[str] = set()
        if hasattr(cls, '__slots__'):
            attributes = extract_attributes(cls.__slots__)
        for base in bases:
            if hasattr(base, '__slots__'):
                attributes |= extract_attributes(base.__slots__)

        setattr(cls, '__attributes__', attributes)

        return cls


# MARK: Field Information

class FieldInfo(
    Representation,
    _FieldInfo,
    Generic[Object],
    metaclass=FieldInfoMeta,
):
    """A field information.

    A class that holds information about a field. The `FieldInfo` class is used
    however a field is defined, whether or not a field function is explicitly
    used within a `BaseModel`, `BaseResource`, or `ConfigWrapper` subclass.

    Attributes:
        source: The source representation of the field definition.
            Defaults to ``None``.
        owner: The owner of the field. It is inferred from the class where the
            field is defined if available else it defaults to ``None``.
        name: The name of the field. It must adhere to a specific ``ALIAS``
            pattern as defined in the framework's regular expressions
            repository. It is inferred from the owner class field attribute
            name converted to snake case.
        annotation: The type annotation of the field.
            Defaults to ``Undefined``.
        default: The default value of the field. If not set and no default
            factory is provided, the field is considered required.
            Defaults to ``Undefined``.
        default_factory: The factory function used to construct the default
            value of the field. If both the default value and the default
            factory are set, an error is raised. Defaults to ``None``.
        alias: The alias name of the field. It must adhere to a specific
            ``ALIAS`` pattern as defined in the framework's regular expressions
            repository. It is inferred from the snake case version of the field
            identifier.
        alias_priority: The priority of the field's alias. This affects whether
            an alias generator is used or not. Defaults to ``None``.
        title: The human-readable name of the field. It must adhere to a
            specific ``TITLE`` pattern as defined in the framework's regular
            expressions repository. It is inferred from the titleized version
            of the field identifier.
        description: The description of the field. Defaults to ``None`` and
            uses the function's docstring if available.
        examples: List of examples of the field. Defaults to ``None``.
        deprecated: A deprecation message, an instance of `Deprecated`, or a
            boolean. If ``True``, a default deprecation message will be emitted
            when accessing the field. Defaults to ``None``.
        frozen: Whether or not the field is frozen. Defaults to ``None``.
        repr: Whether or not to include the field in the representation.
            Defaults to ``True``.
        init: Whether the field should be included in the constructor of the
            dataclass. Defaults to ``True``.
        init_var: Whether the field should only be included in the constructor
            of the dataclass, and not stored. Defaults to ``None``.
        kw_only: Whether or not the field should be a keyword-only argument in
            the constructor of the model. Defaults to ``None``.
        validation_alias: The validation alias name of the field. It must
            adhere to a specific ``ALIAS`` pattern as defined in the
            framework's regular expressions repository.
            Defaults to ``None`` (alias name of the field).
        serialization_alias: The serialization alias name of the field. It
            must adhere to a specific ``ALIAS`` pattern as defined in the
            framework's regular expressions repository. Defaults to ``None``
            (alias name of the field).
        exclude: Whether or not to exclude the field from the model
            serialization. Defaults to ``None``.
        discriminator: Field name for discriminating the type in a tagged
            union. Defaults to ``None``.
        json_schema_extra: Dictionary or callable to provide extra JSON schema
            properties. Defaults to ``None``.
        validate_default: Whether or not to validate the default value of the
            field. Defaults to ``None``.
        metadata: List of metadata constraints. Defaults to an empty list.
        recursive_guard: A recursive guard to handle infinite recursion when
            validating and serializing fields. Defaults to ``None``.
        slug: The slug name of the field. It must adhere to a specific ``SLUG``
            pattern as defined in the framework's regular expressions
            repository. It is inferred from the kebab case version of the field
            identifier.
        unique: Whether or not the field is unique. Defaults to ``None``.
        indexed: Whether or not the field is indexed. Defaults to ``None``.
        linked: Whether or not the field is linked. Defaults to ``None``.
        collection: The collection type of the target association. It can be
            either an unconstrained collection ``list``, or a collection of
            unique elements ``set``, otherwise it defaults to ``None`` if the
            association is not a collection.
        target: The linked field target `BaseResource` object type.
            Defaults to ``None``.
        target_ref: Whether the field can accept a reference to the target
            resource instead of the resource schema model itself.
            Defaults to ``None``.
        target_schemas: Either a tuple of the linked field target
            `DiscriminatedModel` schema models to use for the annotation
            resolution, or a boolean to indicate whether the target schema
            models should be resolved. Defaults to ``None``.
        association: The `Association` object that defines the association
            between the owner and target resources. Defaults to ``None``.
        association_alias: The association alias identifier. By default, this
            is determined by concatenating the owner and target resource alias
            with an underscore (see the `Association` class).
            Defaults to ``None``.
        rel_attribute: The attribute name of the foreign key column implemented
            within the owner resource. This is optional and only applies in a
            scenario where a foreign key column is required for managing the
            association. If the field is not linked or the association (like a
            many-to-many association) does not require a direct foreign key
            column, this parameter defaults to ``None``. Conversely, if a link
            exists and the association necessitates a foreign key column (as
            per the two-way association analysis), this parameter defaults to
            the alias of the linked field, appended with ``_id``.
            Defaults to ``None``.
        rel_backref: The corresponding back referencing target linked field
            counterpart of the association. If the target resource does not
            have a counterpart linked field defined for the given association,
            it initializes to ``None``, otherwise it stores the target
            counterpart `ResourceFieldInfo` instance, either generated from the
            target resource definition, or by the provided back reference
            `BackrefFieldInfoDict` dictionary configuration.
            Defaults to ``None``.
        rel_cascade: The cascade options for the relationship. The possible
            cascading options are ``'delete'``, ``'delete-orphan'``,
            ``'expunge'``, ``'merge'``, ``'refresh-expire'``,
            ``'save-update'``, and ``all``, where the latter is a shorthand for
            ``'save-update, merge, refresh-expire, expunge, delete'``, and is
            often used as in ``'all, delete-orphan'`` to indicate that related
            objects should follow along with the parent object in all cases,
            and be deleted when de-associated.
            Defaults to ``None`` for non-linked fields, otherwise ``True`` for
            linked fields which resolves to:
            - ``'save-update, merge'`` when the association is bidirectional,
            - ``'..., delete, delete-orphan'`` when the target resource link is
                identifying,
            - ``'..., refresh-expire, expunge'`` when the target resource link
                is indexing.
        rel_load: The lazy loading options for the relationship.
            Defaults to ``None`` for non-linked fields, otherwise ``True`` for
            linked fields which resolves to:
            - ``'joined'`` when the association is indexing one of the
                resources,
            - ``'selectin'`` when the resource owner field is not a
                collection,
            - ``'select'`` otherwise (lazy loading).
        rel_extra: Additional association relationship configuration
            parameters. Defaults to ``None``.
        column_extra: Additional column configuration parameters.
            Defaults to ``None``.
        data_type: The data type engine to use for the field. It is
            automatically inferred from the field annotation if not explicitly
            set. Defaults to ``None``.
        data_collation: The collation of the field used for strings within the
            database. Defaults to ``None``.
        data_none_as_null: Whether or not to treat ``None`` as ``NULL`` in the
            database for JSON data types. Defaults to ``None``.
        data_extra: Additional data column configuration parameters.
            Defaults to ``None``.
    """
    if typing.TYPE_CHECKING:
        __attributes__: ClassVar[set[str]]

    # Internal
    _attributes_set: dict[str, Any]
    _complete: bool
    # Source field information
    source: str | None
    owner: type[Object]
    name: str
    annotation: type[Any] | None
    default: Any
    # Base field information
    default_factory: Callable[[], Any] | None
    alias: str
    alias_priority: int | None
    title: str
    description: str | None
    examples: list[Any] | None
    deprecated: Deprecated | str | bool | None
    frozen: bool | None
    repr: bool
    init: bool
    init_var: bool | None
    kw_only: bool | None
    # Model field information
    validation_alias: str | AliasPath | AliasChoices | None
    serialization_alias: str | None
    exclude: bool | None
    discriminator: str | Discriminator | None
    json_schema_extra: JsonSchemaExtra | None
    validate_default: bool | None
    metadata: list[Any]
    recursive_guard: str | None
    # Resource field information
    slug: str
    unique: bool | None
    indexed: bool | None
    linked: bool | None
    collection: Literal['list', 'set'] | None
    target: 'ResourceType | str | None'
    target_ref: bool | None
    target_schemas: tuple[str, ...] | bool | None
    association: 'Association | None'
    association_alias: str | None
    rel_attribute: str | None
    rel_backref: 'ResourceFieldInfo | None'
    rel_cascade: str | bool | None
    rel_load: LoadRule | bool | None
    rel_extra: dict[str, Any] | None
    column_extra: dict[str, Any] | None
    data_type: TypeEngine | None
    data_collation: str | None
    data_none_as_null: bool | None
    data_extra: dict[str, Any] | None

    __slots__ = (
        # Weakref support is necessary to allow garbage collection of fields.
        '__weakref__',
        '_attributes_set',
        '_complete',
        # Source field information
        'source',
        'owner',
        'name',
        'annotation',
        'default',
        # Base field information
        'default_factory',
        'alias',
        'alias_priority',
        'title',
        'description',
        'examples',
        'deprecated',
        'frozen',
        'repr',
        'init',
        'init_var',
        'kw_only',
        # Model field information
        'validation_alias',
        'serialization_alias',
        'exclude',
        'discriminator',
        'json_schema_extra',
        'validate_default',
        'metadata',
        'recursive_guard',
        # Resource field information
        'slug',
        'unique',
        'indexed',
        'linked',
        'collection',
        'target',
        'target_ref',
        'target_schemas',
        'association',
        'association_alias',
        'rel_attribute',
        'rel_backref',
        'rel_cascade',
        'rel_load',
        'rel_extra',
        'column_extra',
        'data_type',
        'data_collation',
        'data_none_as_null',
        'data_extra',
    )

    def __init__(self, **kwargs: Unpack[FieldInfoDict[Any]]) -> None:
        """Initialize the field information.

        It initializes the field information instance with the given keyword
        arguments. This constructor is not meant to be called directly, use the
        field functions like `Field` for models and resources, or `ConfigField`
        for configuration wrappers instead to create a field information
        instance.

        Args:
            **kwargs: Additional keyword arguments. See the field information
                configuration dictionary `FieldInfoDict` for more information
                on the expected keyword arguments.
        """
        # Clean up undefined keyword arguments
        kwargs_set = {k: v for k, v in kwargs.items() if v is not Undefined}
        kwargs_copy: dict[str, Any] = {**kwargs_set}

        # Store attributes set
        self._attributes_set = kwargs_set
        self._complete = False

        # Set field default values
        self.default = kwargs_copy.pop('default', Undefined)
        self.default_factory = kwargs_copy.pop('default_factory', None)
        # Check if default values are valid
        if self.default is Ellipsis:
            self.default = Undefined
        if self.default is not Undefined and self.default_factory is not None:
            raise TypeError(
                "Cannot specify both `default` and `default_factory`."
            )

        # Extract field namespace and ownership
        owner = kwargs_copy.pop('owner', None)
        name = kwargs_copy.pop('name', None)
        alias = kwargs_copy.pop('alias', None)
        slug = kwargs_copy.pop('slug', None)
        title = kwargs_copy.pop('title', None)

        # Set field namespace and ownership
        self.owner = owner if owner is not None else Deferred
        self.name = name if name is not None else Deferred
        self.alias = alias if alias is not None else Deferred
        self.slug = slug if slug is not None else Deferred
        self.title = title if title is not None else Deferred

        # Set field annotation and metadata
        annotation, annotation_metadata = \
            self._extract_metadata(kwargs_copy.pop('annotation', None))
        self.metadata = \
            self._collect_metadata(kwargs_copy)
        self.metadata += annotation_metadata
        self.annotation = \
            eval_type_lenient_deep(annotation, globals(), locals())

        # Set field information
        self.source = kwargs_copy.pop('source', None)
        self.alias_priority = kwargs_copy.pop('alias_priority', None)
        self.description = kwargs_copy.pop('description', None)
        self.examples = kwargs_copy.pop('examples', None)
        self.deprecated = kwargs_copy.pop('deprecated', None)
        self.frozen = kwargs_copy.pop('frozen', None)
        self.repr = kwargs_copy.pop('repr', True)
        self.init = kwargs_copy.pop('init', True)
        self.init_var = kwargs_copy.pop('init_var', None)
        self.kw_only = kwargs_copy.pop('kw_only', None)
        self.validation_alias = kwargs_copy.pop('validation_alias', None)
        self.serialization_alias = kwargs_copy.pop('serialization_alias', None)
        self.exclude = kwargs_copy.pop('exclude', None)
        self.discriminator = kwargs_copy.pop('discriminator', None)
        self.json_schema_extra = kwargs_copy.pop('json_schema_extra', None)
        self.validate_default = kwargs_copy.pop('validate_default', None)
        self.recursive_guard = kwargs_copy.pop('recursive_guard', None)
        self.unique = kwargs_copy.pop('unique', None)
        self.indexed = kwargs_copy.pop('indexed', None)
        self.linked = kwargs_copy.pop('linked', None)
        self.collection = kwargs_copy.pop('collection', None)
        self.target = kwargs_copy.pop('target', None)
        self.target_ref = kwargs_copy.pop('target_ref', None)
        self.target_schemas = kwargs_copy.pop('target_schemas', None)
        self.association = kwargs_copy.pop('association', None)
        self.association_alias = kwargs_copy.pop('association_alias', None)
        self.rel_attribute = kwargs_copy.pop('rel_attribute', None)
        self.rel_backref = kwargs_copy.pop('rel_backref', None)
        self.rel_cascade = kwargs_copy.pop('rel_cascade', None)
        self.rel_load = kwargs_copy.pop('rel_load', None)
        self.rel_extra = kwargs_copy.pop('rel_extra', None)
        self.column_extra = kwargs_copy.pop('column_extra', None)
        self.data_type = kwargs_copy.pop('data_type', None)
        self.data_collation = kwargs_copy.pop('data_collation', None)
        self.data_none_as_null = kwargs_copy.pop('data_none_as_null', None)
        self.data_extra = kwargs_copy.pop('data_extra', None)

        # Check for remaining keyword arguments
        if kwargs_copy:
            raise TypeError(
                f"Unexpected remaining keyword arguments: "
                f"{', '.join(kwargs_copy)}."
            )

        # Initialize field information namespace and ownership
        self._init_field_info_namespace()
        self._init_field_info_ownership_and_association()
        self._init_field_info_target()

        # Finalize field information annotation build
        if self.owner is Deferred:
            return
        if config := get_config(self.owner):
            if config.get('defer_build', False):
                return
        self.build()

    @classmethod
    def from_annotation(  # type: ignore[override, unused-ignore]
        cls,
        annotation: type[Any],
        *,
        owner: type[Object] | None = Undefined,
        name: str | None = Undefined,
    ) -> Self:
        """Creates a field info instance from a bare annotation.

        Examples:
            It is used internally to create a `FieldInfo` from a bare
            annotation like this:

            >>> from plateforme import BaseModel
            ... class MyModel(BaseModel):
            ...     foo: int  # <-- like this

            We also account for the case where the annotation can be an
            instance of `Annotated` and where one of the (not first) arguments
            in `Annotated` is an instance of `FieldInfo`, e.g.:

            >>> import annotated_types
            ... from typing import Annotated
            ... from plateforme import BaseModel, Field

            >>> class MyModel(BaseModel):
            ...     foo: Annotated[int, annotated_types.Gt(42)]
            ...     bar: Annotated[int, Field(gt=42)]

        Args:
            annotation: An annotation object.
            owner: The owner of the field. Defaults to ``Undefined``.
            name: The name of the field. Defaults to ``Undefined``.

        Returns:
            A new field info instance with the given annotation and metadata.
        """
        # Check if the annotation is a final variable
        final: bool = Undefined
        if is_finalvar(annotation):
            final = True
            if annotation is not Final:  # type: ignore[comparison-overlap]
                annotation = typing.get_args(annotation)[0]

        # Handle annotated type
        if is_annotated(annotation):
            annotation_type, *extra_args = typing.get_args(annotation)
            if is_finalvar(annotation_type):
                final = True
            annotation_metadata: list[Any] = []
            for arg in extra_args:
                if not isinstance(arg, _FieldInfo):
                    annotation_metadata.append(arg)
                else:
                    annotation_metadata.extend(arg.metadata)
            field_info = cls.merge_field_infos(
                *[a for a in extra_args if isinstance(a, _FieldInfo)],
                source='from_annotation',
                owner=owner,
                name=name,
                annotation=annotation_type,
                frozen=final,
            )
            field_info.metadata = annotation_metadata
            return field_info

        # Handle standard case
        return cls(
            source='from_annotation',
            owner=owner,
            name=name,
            annotation=annotation,
            frozen=final,
        )

    @classmethod
    def from_annotated_attribute(  # type: ignore[override, unused-ignore]
        cls,
        annotation: type[Any],
        default: Any,
        *,
        owner: type[Object] | None = Undefined,
        name: str | None = Undefined,
    ) -> Self:
        """Create a field info instance from an annotation with default value.

        Examples:
            It is used internally to create a `FieldInfo` from an annotated
            attribute like this:

            >>> import annotated_types
            ... from typing import Annotated
            ... from plateforme import BaseModel, Field

            >>> class MyModel(BaseModel):
            ...     foo: int = 4  # <-- like this
            ...     baz: int = Field(4, gt=4)  # or this
            ...     baz: Annotated[int, annotated_types.Gt(4)] = 4  # or this

        Args:
            annotation: The type annotation of the field.
            default: The default value of the field.
            owner: The owner of the field. Defaults to ``Undefined``.
            name: The name of the field. Defaults to ``Undefined``.

        Returns:
            A new field info instance with the given annotation and default
            value.
        """
        # Check if the annotation is the same as the default value
        if annotation is default:
            raise PlateformeError(
                f"Error when building FieldInfo from annotated attribute "
                f"{annotation!r} with default value {default!r}. Make sure "
                f"you don't have any field name clashing with a type "
                f"annotation.",
                code='field-invalid-config',
            )

        # Check if the annotation is a final variable
        final: bool = Undefined
        if is_finalvar(annotation):
            final = True
            if annotation is not Final:  # type: ignore[comparison-overlap]
                annotation = typing.get_args(annotation)[0]

        # Handle default value as field info instance
        if isinstance(default, _FieldInfo):
            annotation_type, annotation_metadata = \
                FieldInfo._extract_metadata(annotation)
            field_info = cls.merge_field_infos(
                *[x for x in annotation_metadata if isinstance(x, _FieldInfo)],
                default,
                source='from_annotated_attribute',
                owner=owner,
                name=name,
                annotation=annotation_type,
                frozen=final,
            )
            field_info.metadata += annotation_metadata
            return field_info

        # Handle default value as dataclass field
        elif isinstance(default, dataclasses.Field):
            init_var = False
            if annotation is dataclasses.InitVar:
                init_var = True
                annotation = Any  # type: ignore[assignment]
            elif isinstance(annotation, dataclasses.InitVar):
                init_var = True
                annotation = annotation.type
            annotation_type, annotation_metadata = \
                FieldInfo._extract_metadata(annotation)
            field_info = cls.merge_field_infos(
                *[x for x in annotation_metadata if isinstance(x, _FieldInfo)],
                cls._from_dataclass_field(default),
                source='from_annotated_attribute',
                owner=owner,
                name=name,
                annotation=annotation_type,
                frozen=final,
                init_var=init_var,
            )
            field_info.metadata += annotation_metadata
            return field_info

        # Handle annotated type
        elif is_annotated(annotation):
            annotation_type, *extra_args = typing.get_args(annotation)
            annotation_metadata = []
            for arg in extra_args:
                if not isinstance(arg, _FieldInfo):
                    annotation_metadata.append(arg)
                else:
                    annotation_metadata.extend(arg.metadata)
            field_info = cls.merge_field_infos(
                *[a for a in extra_args if isinstance(a, _FieldInfo)],
                source='from_annotated_attribute',
                owner=owner,
                name=name,
                annotation=annotation_type,
                default=default,
                frozen=final,
            )
            field_info.metadata = annotation_metadata
            return field_info

        # Handle standard case
        return cls(
            source='from_annotated_attribute',
            owner=owner,
            name=name,
            annotation=annotation,
            default=default,
            frozen=final,
        )

    @classmethod
    def from_field(  # type: ignore[override, unused-ignore]
        cls, default: Any = Undefined, **kwargs: Unpack[FieldInfoFromFieldDict]
    ) -> Self:
        """Create a field info object instance with a field function.

        Args:
            default: Since this is replacing the field's default, its first
                argument is used to set the default, use ellipsis ``...`` to
                indicate the field is required.
            **kwargs: Additional keyword arguments. See the field information
                configuration dictionary `FieldInfoFromFieldDict` for more
                information on the expected keyword arguments.

        Raises:
            TypeError: If `annotation`, `owner`, or `name` is passed as a
                keyword argument.

        Returns:
            A new field info instance with the given parameters.
        """
        # Check keyword arguments
        for key in ('owner', 'name', 'annotation'):
            if key in kwargs:
                raise TypeError(
                    f"The keyword argument {key!r} is not permitted for a "
                    f"field function keyword argument."
                )
        # Create field info instance
        return cls(source='from_field', default=default, **kwargs)

    @classmethod
    def from_field_info(
        cls, base: _FieldInfo, **overrides: Unpack[FieldInfoDict[Any]]
    ) -> Self:
        """Create a field info object instance from a base field info.

        It constructs a new field info instance from a base field info instance
        with additional keyword arguments to override the base field info
        attributes.

        Args:
            base: The base field info to create the field info instance from.
            **overrides: Additional keyword arguments to override the base
                field info attributes. See the field information configuration
                dictionary `FieldInfoDict` for more information on the expected
                keyword arguments.

        Returns:
            A new field info instance with the given parameters.
        """
        # Clean up override arguments
        overrides = {  # type: ignore[assignment]
            k: v for k, v in overrides.items() if v is not Undefined
        }

        # Retrieve keyword arguments and metadata from base field info
        kwargs: dict[str, Any] = base._attributes_set
        metadata = {}
        for constraint in base.metadata:
            if not isinstance(constraint, _FieldInfo):
                metadata[type(constraint)] = constraint
        kwargs.update(overrides)
        kwargs.setdefault('source', 'from_field_info')

        # Create field info instance
        field_info = cls(**kwargs)
        field_info.metadata += list(metadata.values())
        return field_info

    @classmethod
    def merge_field_infos(  # type: ignore[override, unused-ignore]
        cls, *field_infos: _FieldInfo, **overrides: Unpack[FieldInfoDict[Any]]
    ) -> Self:
        """Merge field info instances keeping only explicitly set attributes.

        It merges multiple `FieldInfo` instances into a single one, keeping
        only the attributes that are explicitly set in each instance. The later
        `FieldInfo` instances override the earlier ones, while the `overrides`
        keyword arguments are applied to the merged `FieldInfo` instance.

        FIXME: When multiple field info instances are merged, Pydantic uses its
        own `FieldInfo` class to merge them. This is not ideal as it does not
        take into account the `FieldInfo` class hierarchy. This impacts
        typically fields with annotation that uses the `Field` functions.

        Args:
            *field_infos: The field info instances to merge.
            **overrides: Additional keyword arguments to override the merged
                field info attributes. See the field information configuration
                dictionary `FieldInfoDict` for more information on the expected
                keyword arguments.

        Returns:
            A new field info instance with the merged attributes.
        """
        # Flatten field infos
        flattened_field_infos: list[_FieldInfo] = []
        for field_info in field_infos:
            flattened_field_infos.extend(
                x for x in field_info.metadata if isinstance(x, _FieldInfo)
            )
            flattened_field_infos.append(field_info)
        field_infos = tuple(flattened_field_infos)

        # Retrieve the field info consructor class. If there are multiple field
        # info instances, use the last one that is a subclass of this class. If
        # there are no subclasses, use this class.
        field_info_cls = cls
        for field_info in field_infos:
            if isinstance(field_info, cls):
                field_info_cls = type(field_info)

        # Check if there is only one field info instance to merge and apply
        # the overrides if necessary.
        if len(field_infos) == 1:
            return field_info_cls.from_field_info(field_infos[0], **overrides)

        # Clean up override arguments
        overrides = {  # type: ignore[assignment]
            k: v for k, v in overrides.items() if v is not Undefined
        }

        # Retrieve keyword arguments and metadata from field infos
        kwargs: dict[str, Any] = {}
        metadata = {}
        for field_info in field_infos:
            kwargs.update(field_info._attributes_set)
            for constraint in field_info.metadata:
                if not isinstance(constraint, _FieldInfo):
                    metadata[type(constraint)] = constraint
        kwargs.update(overrides)

        # Create field info instance
        field_info = field_info_cls(**kwargs)
        field_info.metadata = list(metadata.values())
        return field_info

    def build(
        self,
        *,
        force: bool = False,
        raise_errors: bool = True,
    ) -> bool | None:
        """Build the field information target and annotation.

        Args:
            force: Whether to force the field information building even if it
                is already complete. Defaults to ``False``.
            raise_errors: Whether to raise errors if the field information
                cannot be built. Defaults to ``True``.

        Returns:
            ``True`` if the field information is successfully built, ``False``
            if the field information cannot be built, and ``None`` if the field
            information is already complete.

        Raises:
            PlateformeError: If the target is not a valid resource or if the
                target schema is not found in the target resource.
        """
        # Check if field information is already complete
        if self._complete and not force:
            return None
        elif self.target is None:
            self._complete = True
            return True
        else:
            self._complete = False

        # Validate target resource
        if isinstance(self.target, str):
            if not raise_errors:
                return False
            raise PlateformeError(
                f"Cannot build field information for field {self.name!r} of "
                f"resource {self.owner.__qualname__!r}. The target must be a "
                f"valid resource. Got: {self.target!r}.",
                code='field-invalid-config',
            )

        # Update target annotation
        if target_annotation := self.build_target_annotation():
            target_type, *target_metadata = target_annotation

            def ann_test(ann: Any) -> bool:
                assert isinstance(self.target, type)
                if isinstance(ann, str):
                    return True
                if isinstance(ann, ForwardRef):
                    return True
                if isinstance(ann, type) and issubclass(ann, self.target):
                    return True
                return False

            def ann_resolver(_: Any) -> Any:
                if target_metadata:
                    return Annotated[target_type, *target_metadata]
                return target_type

            if ann_test(self.annotation):
                self.metadata += target_metadata
                self.annotation = target_type
            else:
                try:
                    annotation = Annotation.replace(
                        self.annotation,
                        test=ann_test,
                        resolver=ann_resolver,
                    )
                except PlateformeError as error:
                    if raise_errors:
                        raise error
                    return False

                self.annotation = annotation

        # Update recursive guard
        if recursive_guard := self.build_recursive_guard():
            self.recursive_guard = recursive_guard

        self._complete = True

        return True

    def build_recursive_guard(self) -> str | None:
        """Build the field information recursive guard."""
        # Check if recursive guard is already set
        if self.recursive_guard is not None:
            return self.recursive_guard

        # Try to infer recursive guard from owner resource
        if is_model(self.owner):
            resource = self.owner.__pydantic_resource__
            if resource is None:
                return None
        elif is_resource(self.owner):
            resource = self.owner
        else:
            return None

        resource_field = resource.resource_fields.get(self.name, None)
        if resource_field is None:
            return None
        return resource_field.association_alias

    def build_target_annotation(self) -> tuple[Any, ...] | None:
        """Build the field information target annotation and metadata.

        For fields that are linked to another resource, this method returns
        either a tuple containing the target type itself or a selector
        reference to the target type, or a tuple containing the target schema
        model with optional selector reference annotation when `target_schemas`
        and `target_ref` are both set.

        Returns:
            A tuple containing the field information target annotation and
            metadata, or ``None`` if the field is not linked.

        Raises:
            PlateformeError: If no resource schema models matches the specified
                target schema models of the field information.
        """
        from ..selectors import Key

        # Skip if target is not a resource
        if self.target is None or isinstance(self.target, str):
            return None

        if not self.target_ref and not self.target_schemas:
            return (self.target,)

        # Retrieve target schema model
        target_model = None
        if self.target_schemas is True:
            self.target_schemas = ('model',)
        if self.target_schemas:
            for target_schema in self.target_schemas:
                if schema := self.target.resource_schemas.get(target_schema):
                    target_model = schema
                    break
            if target_model is None:
                raise PlateformeError(
                    f"Cannot resolve target schema for field {self.name!r} "
                    f"of {self.owner.__qualname__!r}. "
                    f"Got: {self.target_schemas!r}.",
                    code='field-invalid-config',
                )

        # Return target annotation and metadata
        if self.target_ref and self.target_schemas:
            return (target_model, Key.create(self.target))
        elif self.target_ref:
            return (Key.create(self.target),)
        else:
            return (target_model,)

    def create_column(self) -> Column[Any]:
        """Create a SQLAlchemy column object from the field information.

        Raises:
            TypeError: If the field is linked.
            ValueError: If the owner is not a valid resource.
            PlateformeError: If the field annotation or data type engine is
                invalid.
        """
        # Validate field information
        if not is_resource(self.owner):
            raise ValueError(
                f"Cannot create a column for field {self.name!r} of "
                f"{self.owner.__qualname__!r}. The owner must be a valid "
                f"resource.",
            )
        if self.linked:
            raise TypeError(
                f"Cannot create a column for linked field {self.name!r} of "
                f"{self.owner.__qualname__!r}. Linked fields are not "
                f"supported by the `create_column` method.",
            )

        # Resolve data type engine from annotation
        try:
            if self.data_type is not None:
                type_engine = self.data_type
            else:
                type_engine = resolve_data_type_engine(
                    self.annotation,
                    self.owner.resource_config.arbitrary_types_allowed,
                    **{
                        k: v for k, v in self._attributes_set.items()
                        if k.startswith('data_')
                    },
                )
        except TypeError as error:
            raise PlateformeError(
                f"Field {self.name!r} of resource {self.owner.__qualname__!r} "
                f"has an invalid annotation {self.annotation!r}.",
                code='field-invalid-config',
            ) from error

        # Instantiate data type engine if necessary
        if isinstance(type_engine, type):
            type_engine = type_engine()

        # Validate data type engine
        if not isinstance(type_engine, BaseTypeEngine):
            raise PlateformeError(
                f"Field {self.name!r} of resource {self.owner.__qualname__!r} "
                f"has an invalid data type engine {type_engine!r}.",
                code='field-invalid-config',
            )

        return Column(
            name=self.name,
            type_=type_engine,
            index=self.indexed or False,
            unique=self.unique or False,
            nullable=self.is_nullable(),
            **(self.column_extra or {}),
        )

    def entries(
        self, *, scope: Literal['all', 'set'] = 'all'
    ) -> dict[str, Any]:
        """Return the field information entries based on the specified scope.

        Args:
            scope: The scope of the field information dictionary to return. It
                can be either ``'all'`` to return all entries, or ``'set'`` to
                return only the field information entries that have been
                explicitly set. Defaults to ``'all'``.

        Returns:
            A dictionary containing the field information entries based on the
            specified scope.
        """
        if scope == 'set':
            return self._attributes_set
        return {
            key: getattr(self, key)
            for key in self.__attributes__ if not key.startswith('_')
        }

    def is_cascading(self, *options: CascadeRule) -> bool | None:
        """Check if the field association cascades the provided options.

        It defines whether or not to cascade operations to the field associated
        target resource. This determines if operations on the field owner
        resource should extend to its target resource. It is used to infer if
        it is possible to simultaneously create, read, update, upsert, or
        delete associated target resource through the same endpoint,
        effectively treating the associated target data as part of the owner
        resource's data model.

        Args:
            *options: The cascade rules to check against. The possible
                options are ``'delete'``, ``'delete-orphan'``, ``'expunge'``,
                ``'merge'``, ``'refresh-expire'``, ``'save-update'``, and
                ``all``, where the latter is a shorthand for
                ``'save-update, merge, refresh-expire, expunge, delete'``, and
                is often used as in ``'all, delete-orphan'`` to indicate that
                related objects should follow along with the parent object in
                all cases, and be deleted when de-associated.

                Those can be set using the `rel_cascade` field information
                attribute. If not set, it resolves with the following options:
                - ``'save-update, merge'`` when the association is
                    bidirectional,
                - ``'delete, delete-orphan'`` when the target resource link is
                    identifying,
                - ``'refresh-expire, expunge'`` when the target resource link is
                    indexing.

        Returns:
            Whether the field association cascades the provided options, or
            ``None`` if the field is not linked.

        Raises:
            ValueError: If the field `rel_cascade` corresponding resource
                relationship property is not defined.
        """
        if is_model(self.owner):
            resource = self.owner.__pydantic_resource__
        elif is_resource(self.owner):
            resource = self.owner

        if resource is None or not self.linked:
            return None

        rel_attr = resource.resource_attributes.get(self.name, None)
        if rel_attr is None:
            raise ValueError(
                f"Cannot determine if the field {self.name!r} of "
                f"{resource.__qualname__!r} is cascading. The corresponding "
                f"resource relationship property is not yet defined.",
            )
        rel_prop = rel_attr.property
        assert isinstance(rel_prop, RelationshipProperty)

        options_set = set(options)
        if 'all' in options_set:
            options_set.remove('all')
            options_set.update({
                'delete',
                'expunge',
                'merge',
                'refresh-expire',
                'save-update',
            })

        for option in options_set:
            match option:
                case 'delete':
                    if not rel_prop.cascade.delete:
                        return False
                case 'delete-orphan':
                    if not rel_prop.cascade.delete_orphan:
                        return False
                case 'expunge':
                    if not rel_prop.cascade.expunge:
                        return False
                case 'merge':
                    if not rel_prop.cascade.merge:
                        return False
                case 'refresh-expire':
                    if not rel_prop.cascade.refresh_expire:
                        return False
                case 'save-update':
                    if not rel_prop.cascade.save_update:
                        return False
                case _:
                    raise NotImplementedError(
                        f"Unsupported option: {option!r}."
                    )

        return True

    def is_eagerly(self) -> bool | None:
        """Check if the field association loading is eager.

        It defines whether or not to load eagerly the field associated target
        resource data when loading the field owner resource. It is used in
        resource schemas and endpoints to infer if the target resource data
        should be returned and traversed along with the owner resource data.

        Returns:
            Whether the field association loading is eager, or ``None`` if the
            field is not linked.

        Raises:
            ValueError: If the field `rel_load` corresponding resource
                relationship property is not defined.
        """
        if is_model(self.owner):
            resource = self.owner.__pydantic_resource__
        elif is_resource(self.owner):
            resource = self.owner

        if resource is None or not self.linked:
            return None

        rel_attr = resource.resource_attributes.get(self.name, None)
        if rel_attr is None:
            raise ValueError(
                f"Cannot determine if the field {self.name!r} of "
                f"{resource.__qualname__!r} is eagerly loaded. The "
                f"corresponding resource relationship property is not yet "
                f"defined.",
            )
        rel_prop = rel_attr.property
        assert isinstance(rel_prop, RelationshipProperty)

        return rel_prop.lazy in ('joined', 'selectin')

    def is_identifying(self) -> bool | None:
        """Check if the field exists within its owner identifiers.

        The field is considered identifying if either the field `unique`
        attribute is set to ``True``, or if the field `alias` is found within a
        composite identifier of its owner resource.

        Returns:
            Whether the field is identifying its owner, or ``None`` if the
            field is not attached to a resource.
        """
        if self.unique:
            return True

        if is_model(self.owner):
            resource = self.owner.__pydantic_resource__
            if resource is None:
                return None
        elif is_resource(self.owner):
            resource = self.owner
        else:
            return None

        return any(
            self.alias in identifier
            for identifier in resource.resource_identifiers
        )

    def is_indexing(self) -> bool | None:
        """Check if the field exists within its owner indexes.

        The field is considered indexing if either the field `indexed` or
        `unique` attribute is set to ``True``, or if the field `alias` is found
        within a composite index of its owner resource.

        Returns:
            Whether the field is indexing its owner, or ``None`` if the field
            is not attached to a resource.
        """
        if self.indexed:
            return True

        if is_model(self.owner):
            resource = self.owner.__pydantic_resource__
            if resource is None:
                return None
        elif is_resource(self.owner):
            resource = self.owner
        else:
            return None

        return any(
            self.alias in index
            for index in resource.resource_indexes
        )

    def is_nullable(self) -> bool:
        """Check if the field is nullable.

        It is considered nullable if the field accepts ``None`` as a value.

        Returns:
            Whether the field is nullable.
        """
        return self.annotation is NoneType or is_optional(self.annotation)

    def is_required(self) -> bool:
        """Check if the field is required.

        It is considered required if it does not have a default value, i.e. it
        is not set to ``Undefined`` and does not have a default factory.

        Returns:
            Whether the field is required.
        """
        if self.default is Undefined and self.default_factory is None:
            return True
        return super().is_required()

    @classmethod
    def _from_dataclass_field(  # type: ignore[override, unused-ignore]
        cls, dc_field: dataclasses.Field[Any]
    ) -> Self:
        """Create a field info instance from a dataclass field one.

        It is used internally to create a `FieldInfo` from a dataclass field.

        Args:
            dc_field: The `dataclasses.Field` instance to convert.

        Returns:
            The corresponding field info instance.

        Raises:
            TypeError: If any of the `FieldInfo` keyword arguments does not
                match the `dataclass.Field` ones.
        """
        # Retrieve default value
        default = dc_field.default
        if default is dataclasses.MISSING:
            default = Undefined
        # Retrieve default factory
        if dc_field.default_factory is dataclasses.MISSING:
            default_factory: Callable[[], Any] | None = None
        else:
            default_factory = dc_field.default_factory

        # Retrieve keyword arguments from dataclass field
        kwargs = {
            key: value
            for key, value in dc_field.metadata.items()
            if key in set(inspect.signature(Field).parameters)
        }

        # Create field info instance using the field function so incorrect
        # keyword arguments are caught and an error is raised.
        return Field(  # type: ignore[no-any-return]
            default,
            default_factory=default_factory,
            repr=getattr(dc_field, 'repr', True),
            init=getattr(dc_field, 'init', True),
            kw_only=getattr(dc_field, 'kw_only', None),
            **kwargs,
        )

    @classmethod
    def _from_field_info_backref(
        cls, field_info: 'ResourceFieldInfo'
    ) -> 'ResourceFieldInfo':
        """Create field info backref instance from an association.

        Args:
            kwargs: Additional keyword arguments.

        Returns:
            A new field info instance.
        """
        from ..resources import _build_base_model, _build_schemas_and_adapter
        from ..runtime import Action, Lifecycle

        # Validate owner and target resources
        backref_owner = field_info.target
        backref_target = field_info.owner
        if not is_resource(backref_owner) or not is_resource(backref_target):
            raise PlateformeError(
                f"Cannot create backref field info for field "
                f"{field_info.name!r}. The owner and target must be valid "
                f"resources.",
                code='field-invalid-config',
            )

        # Validate backref configuration
        if field_info.rel_backref is None \
                or not isinstance(field_info.rel_backref, dict) \
                or 'name' not in field_info.rel_backref \
                or field_info.rel_backref['name'] \
                    in backref_owner.resource_fields:
            raise PlateformeError(
                f"Cannot create backref field info for field "
                f"{field_info.name!r}. The relationship backref must be a "
                f"dictionary with a valid name set to a non-existing field "
                f"within the target resource.",
                code='field-invalid-config',
            )

        # Build backref annotation
        kwargs = typing.cast(BackrefFieldInfoDict, {**field_info.rel_backref})

        annotation: type[Any] = backref_target
        collection = kwargs.pop('collection', None)
        if collection == 'list':
            annotation = list[annotation]  # type: ignore[valid-type]
        elif collection == 'set':
            annotation = set[annotation]  # type: ignore[valid-type]

        # Create backref field info instance
        backref: 'ResourceFieldInfo' = cls(  # type: ignore[assignment]
            source='from_field_info_backref',
            owner=backref_owner,
            name=kwargs.pop('name', Undefined),
            annotation=annotation,
            default=kwargs.pop('default', Undefined),
            default_factory=kwargs.pop('default_factory', Undefined),
            alias=kwargs.pop('alias', Undefined),
            alias_priority=kwargs.pop('alias_priority', Undefined),
            title=kwargs.pop('title', Undefined),
            description=kwargs.pop('description', Undefined),
            examples=kwargs.pop('examples', Undefined),
            deprecated=kwargs.pop('deprecated', Undefined),
            frozen=kwargs.pop('frozen', Undefined),
            repr=kwargs.pop('repr', Undefined),
            init=kwargs.pop('init', Undefined),
            init_var=kwargs.pop('init_var', Undefined),
            kw_only=kwargs.pop('kw_only', Undefined),
            validation_alias=kwargs.pop('validation_alias', Undefined),
            serialization_alias=kwargs.pop('serialization_alias', Undefined),
            exclude=kwargs.pop('exclude', Undefined),
            discriminator=kwargs.pop('discriminator', Undefined),
            json_schema_extra=kwargs.pop('json_schema_extra', Undefined),
            validate_default=kwargs.pop('validate_default', Undefined),
            recursive_guard=kwargs.pop('recursive_guard', Undefined),
            slug=kwargs.pop('slug', Undefined),
            unique=kwargs.pop('unique', Undefined),
            indexed=kwargs.pop('indexed', Undefined),
            association=field_info.association,
            association_alias=field_info.association_alias,
            rel_attribute=kwargs.pop('rel_attribute', Undefined),
            rel_backref=field_info,  # type: ignore[arg-type]
            rel_cascade=kwargs.pop('rel_cascade', Undefined),
            rel_load=kwargs.pop('rel_load', Undefined),
            rel_extra=kwargs.pop('rel_extra', Undefined),
            column_extra=kwargs.pop('column_extra', Undefined),
        )

        # Update field information and backref owner
        field_info._update(rel_backref=backref)  # type: ignore[arg-type]

        backref_owner.resource_fields[backref.name] = backref
        backref_owner.resource_package._add_resource_dependency(backref)
        backref_owner.__state__.schedule(
            (
                Action(_build_base_model, bound=True),
                Lifecycle.INITIALIZING
            ),
            (
                Action(_build_schemas_and_adapter, bound=True),
                Lifecycle.FINALIZING
            ),
            when_reached='fallback',
            when_future='skip',
            propagate=True,
        )

        return backref

    def _init_field_info_namespace(self) -> None:
        """Initialize the field information namespace."""
        # Check for valid field information owner and name attributes
        if (self.owner is Deferred and self.name) \
                or (self.owner is not Deferred and not self.name):
            raise PlateformeError(
                f"Field information must have a valid owner and name, either "
                f"both are defined or both are undefined. Got owner "
                f"{self.owner!r} and name {self.name!r}.",
                code='field-invalid-config',
            )

        # Retrieve owner config
        config = get_config(self.owner) or {}

        # Collect field information aliases
        is_alias_set = any(
            alias is not None
            for alias
            in (self.alias, self.validation_alias, self.serialization_alias)
        )
        alias: str | None = None
        validation_alias: str | AliasPath | AliasChoices | None = None
        serialization_alias: str | None = None
        alias_generator = config.get('alias_generator', None)
        if alias_generator is not None:
            assert isinstance(self.owner, type)
            assert isinstance(self.name, str)
            if isinstance(alias_generator, AliasGenerator):
                alias, validation_alias, serialization_alias = \
                    alias_generator.generate_aliases(self.name)
            elif callable(alias_generator):
                alias = validation_alias = serialization_alias = \
                    alias_generator(self.name)
            else:
                raise PlateformeError(
                    f"Field information owner {self.owner.__qualname__!r} has "
                    f"an invalid alias generator {alias_generator!r}. The "
                    f"alias generator must be a callable or an instance of "
                    f"`AliasGenerator` class.",
                    code='field-invalid-config',
                )

        # Update field information aliases
        if self.alias_priority is None and is_alias_set:
            self.alias_priority = 2

        # Helper function to set default aliases
        def setdefault_alias(key: str, value: Any) -> None:
            if getattr(self, key) is not None or value is None:
                return
            if value == self.name:
                # Set default value
                setattr(self, key, value)
            else:
                # Set default value and mark as set
                self._update(**{key: value})

        setdefault_alias('alias', alias)
        setdefault_alias('validation_alias', validation_alias)
        setdefault_alias('serialization_alias', serialization_alias)

        # Retrieve field information identifier
        identifier = to_name_case(
            self.name
            or self.alias
            or self.slug
            or self.title
            or self.serialization_alias
            or self.validation_alias.convert_to_alias() if isinstance(
                self.validation_alias, (AliasPath, AliasChoices)
            ) else self.validation_alias
            or ''
        )

        # Check if identifier is valid
        if not identifier:
            # Return silently if no identifier is found as it is not necessary
            # to populate and validate the field info namespace yet.
            return

        # Update field information namespace
        self.name = self.name or identifier
        self.alias = self.alias or identifier
        self.slug = self.slug or to_path_case(identifier)
        self.title = self.title or to_title_case(identifier)

        # Validate field information namespace
        def validate(key: str, pattern: str, value: str | None) -> None:
            if value is not None \
                    and not value == 'type_' \
                    and not re.match(pattern, value):
                raise PlateformeError(
                    f"The field with identifier {identifier!r} has an invalid "
                    f"attribute {key} {value!r} in its configuration. It must "
                    f"match a specific pattern defined in the framework "
                    f"regular expressions repository.",
                    code='field-invalid-config',
                )
        validate('name', RegexPattern.ALIAS, self.name)
        validate('alias', RegexPattern.ALIAS, self.alias)
        validate('slug', RegexPattern.SLUG, self.slug)
        validate('title', RegexPattern.TITLE, self.title)

    def _init_field_info_ownership_and_association(self) -> None:
        """Initialize the field information ownership and association."""
        # Validate field information owner
        if self.owner and not isinstance(self.owner, type):
            raise PlateformeError(
                f"Field owner must be a valid type. Got: "
                f"{type(self.owner).__qualname__!r}.",
                code='field-invalid-config',
            )

        # Handle field information association
        if is_resource(self.owner):
            # Handle linked fields
            if has_forwardref(self.annotation) \
                    or has_resource(self.annotation):
                self._update(linked=True)

                try:
                    # Resolve target resource from annotation
                    collection, target = _resolve_target_from_annotation(
                        self.owner, self.annotation
                    )
                    self._update(collection=collection)
                    self._update(target=target)
                except PlateformeError as error:
                    raise PlateformeError(
                        f"Field {self.name!r} of resource "
                        f"{self.owner.__qualname__!r} has an invalid "
                        f"annotation {self.annotation!r}.",
                        code='field-invalid-config',
                    ) from error

                # Check if target is abstract
                if is_abstract(self.target):
                    assert isinstance(self.target, type)
                    raise PlateformeError(
                        f"Field {self.name!r} of resource "
                        f"{self.owner.__qualname__!r} has an invalid "
                        f"annotation {self.annotation!r}. Target resource "
                        f"{self.target.__qualname__!r} is abstract.",
                        code='field-invalid-config',
                    )

                # Check for forbidden attributes
                for attr in self.__attributes__:
                    if not attr.startswith('data_'):
                        continue
                    if getattr(self, attr) is None:
                        continue
                    raise PlateformeError(
                        f"Field {self.name!r} of resource "
                        f"{self.owner.__qualname__!r} has an invalid "
                        f"configuration. Linked fields cannot specify data "
                        f"related attributes. Got a value for {attr!r}.",
                        code='field-invalid-config',
                    )

            # Handle non-linked fields
            else:
                self._update(linked=False)

                # Check for forbidden attributes
                for attr in self.__attributes__:
                    if not attr.startswith('association') \
                            and not attr.startswith('rel_'):
                        continue
                    if getattr(self, attr) is None:
                        continue
                    raise PlateformeError(
                        f"Field {self.name!r} of resource "
                        f"{self.owner.__qualname__!r} has an invalid "
                        f"configuration. Non-linked fields cannot specify "
                        f"association or relationship related attributes. "
                        f"Got a value for {attr!r}.",
                        code='field-invalid-config',
                    )

        # Update indexing options
        if self.unique:
            self.indexed = True

        # Update relationship cascading and loading options
        if self.linked:
            if 'rel_cascade' not in self._attributes_set:
                self.rel_cascade = True
            if 'rel_load' not in self._attributes_set:
                self.rel_load = True

    def _init_field_info_target(self) -> None:
        """Initialize the field information target."""
        # Collect field information metadata target schemas and selectors
        target_schemas: set[str] = set()
        target_selectors: set[Any] = set()

        for value in self.metadata:
            if isinstance(value, Schema):
                target_schemas.add(value.model)
            elif is_selector(value):
                target_selectors.add(value)

        # Validate target schemas
        if target_schemas:
            if self.target_schemas is True:
                target_schemas.add('model')
            elif self.target_schemas:
                target_schemas.update(self.target_schemas)
            elif self.target_schemas is False:
                raise PlateformeError(
                    f"Field information with schema models cannot have "
                    f"target schema models disabled. Got: {target_schemas!r}.",
                    code='field-invalid-config',
                )
            self.target_schemas = tuple(target_schemas)
        if self.target_schemas is not None and self.target is None:
            raise PlateformeError(
                f"Field information with schema models must have a valid "
                f"target resource. Got: {self.target_schemas!r}.",
                code='field-invalid-config',
            )

        # Validate target selectors
        if target_selectors:
            if self.target_ref is False:
                raise PlateformeError(
                    f"Field information with selector metadata cannot have "
                    f"target reference disabled. Got: {target_selectors!r}.",
                    code='field-invalid-config',
                )
            if self.target_schemas is None:
                raise PlateformeError(
                    f"Field information with selector metadata must have "
                    f"target schema models specified. "
                    f"Got: {target_selectors!r}.",
                    code='field-invalid-config',
                )
            self.target_ref = True
        if self.target_ref is not None and self.target is None:
            raise PlateformeError(
                f"Field information with selector must have a valid target "
                f"resource. Got: {target_selectors!r}.",
                code='field-invalid-config',
            )

    def _create_field_definition(self) -> FieldDefinition:
        """Create a field definition from the field information."""
        # Retrieve annotation from field information
        annotation = typing.cast(type, copy(self.annotation))
        # Retrieve raw field information
        field = copy(self)
        field._update(annotation=None, owner=Undefined, name=Undefined)
        return annotation, field

    def _default(self, **kwargs: Unpack[FieldInfoDict[Any]]) -> None:
        """Update default and set the field information.

        The provided keyword arguments are used to update the field information
        attributes. The update is performed in-place with the `_attributes_set`
        dictionary attribute updated accordingly for non set values.

        If a non-default value exists, it is persisted in the `_attributes_set`
        dictionary, otherwise the `_attributes_set` dictionary is updated with
        the provided default value.

        Args:
            **kwargs: Additional keyword arguments. See the field information
                configuration dictionary `FieldInfoDict` for more information
                on the expected keyword arguments.

        Note:
            This method is used internally to update the field information
            default values and should not be used directly.
        """
        for key, default in kwargs.items():
            if key in self._attributes_set:
                continue
            value = getattr(self, key, None)
            if value in (Undefined, None):
                value = default
                setattr(self, key, value)
            if value is Undefined:
                self._attributes_set.pop(key, None)
            else:
                self._attributes_set[key] = value

    def _update(self, **kwargs: Unpack[FieldInfoDict[Any]]) -> None:
        """Update and set the field information.

        The provided keyword arguments are used to update the field information
        attributes. The update is performed in-place with the `_attributes_set`
        dictionary attribute updated accordingly for non ``Undefined`` values.

        Args:
            **kwargs: Additional keyword arguments. See the field information
                configuration dictionary `FieldInfoDict` for more information
                on the expected keyword arguments.

        Note:
            This method is used internally to update the field information and
            should not be used directly.
        """
        for key, value in kwargs.items():
            setattr(self, key, value)
            if value is Undefined:
                self._attributes_set.pop(key, None)
            else:
                self._attributes_set[key] = value

    def __setattr__(self, name: str, value: Any) -> None:
        # Validate attribute name
        if not name.startswith('_') and name not in self.__attributes__:
            raise AttributeError(
                f"Invalid attribute {name!r} for field information, only "
                f"attributes defined within the field information slots are "
                f"allowed.",
            )
        return super().__setattr__(name, value)

    def __copy__(self) -> Self:
        """Returns a shallow copy of the field."""
        cls = type(self)
        field = cls.__new__(cls)
        for name in cls.__slots__:
            if name == '__weakref__':
                continue
            value = getattr(self, name)
            if name == '_attributes_set':
                value = {**value}
            object.__setattr__(field, name, value)
        return field

    def __repr_args__(self) -> ReprArgs:
        for name, value in super().__repr_args__():
            if name in (
                'source',
                'owner',
                'linked',
                'collection',
                'association',
                'association_alias',
                'rel_attribute',
                'rel_backref',
                'rel_cascade',
                'rel_load',
                'rel_extra',
                'column_extra',
                'data_type',
                'data_collation',
                'data_none_as_null',
                'data_extra',
            ):
                continue
            elif name == 'target':
                if isinstance(value, type):
                    value = value.__qualname__
                yield 'target', PlainRepresentation(value)
            elif name not in self._attributes_set:
                continue
            else:
                yield name, value


def ConfigField(
    default: Any = Undefined, **kwargs: Unpack[FieldInfoFromConfigDict]
) -> Any:
    """Create a field information instance for a configuration field.

    Used to provide extra information about a configuration field for a
    configuration wrapper.

    Args:
        default: Since this is replacing the field's default, its first
            argument is used to set the default, use ellipsis ``...`` to
            indicate the field is required.
        **kwargs: Additional keyword arguments. See the field information
            configuration dictionary `FieldInfoFromConfigDict` for more
            information on the expected keyword arguments.
    """
    return FieldInfo.from_field(default=default, **kwargs)


# MARK: Field

def Field(
    default: Any = Undefined, **kwargs: Unpack[FieldInfoFromFieldDict]
) -> Any:
    """Create a field information instance for a model or resource field.

    Used to provide extra information about a field, either for the model or
    resource schema, or complex validation. Some arguments apply only to number
    fields (`int`, `float`, `Decimal`) and some apply only to `str`.

    Args:
        default: Since this is replacing the field's default, its first
            argument is used to set the default, use ellipsis ``...`` to
            indicate the field is required.
        **kwargs: Additional keyword arguments. See the field information
            configuration dictionary `FieldInfoFromFieldDict` for more
            information on the expected keyword arguments.
    """
    return FieldInfo.from_field(default=default, **kwargs)


# MARK: Computed Field Information

@dataclasses.dataclass(kw_only=True, slots=True)
class ComputedFieldInfo(_ComputedFieldInfo):
    """A computed field information.

    A container for data from ``@computed_field`` so it can access while
    building the `pydantic-core` schema.

    Attributes:
        decorator_repr: A class variable representing the decorator string
            ``@computed_field``.
        wrapped_property: The wrapped computed field property.
        name: The name of the field. It must adhere to a specific ``ALIAS``
            pattern as defined in the framework's regular expressions
            repository. When created from the decorator ``@computed_field``, it
            is inferred from the wrapped property name snake cased.
        return_type: An optional return type for serialization logic to expect
            when serializing to JSON. If included, this must be correct,
            otherwise a ``TypeError`` is raised. If no return type is specified
            ``Any`` is used, which does runtime introspection to handle
            arbitrary objects.
        alias: The alias name of the field. It must adhere to a specific
            ``ALIAS`` pattern as defined in the framework's regular expressions
            repository. When created from the decorator ``@computed_field``, it
            is inferred from the wrapped property identifier snake cased. It is
            used when serializing the computed field if ``by_alias=True``.
        alias_priority: The priority of the field's alias. This affects whether
            an alias generator is used or not. Defaults to ``None``.
        slug: The slug name of the field. It must adhere to a specific ``SLUG``
            pattern as defined in the framework's regular expressions
            repository. When created from the decorator ``@computed_field``, it
            is inferred from the wrapped property identifier kebab cased.
        title: The human-readable name of the field. It must adhere to a
            specific ``TITLE`` pattern as defined in the framework's regular
            expressions repository. When created from the decorator
            ``@computed_field``, it is inferred from the wrapped property
            identifier titleized.
        description: The description of the field. Defaults to ``None`` and
            uses the function's docstring if available.
        examples: List of examples of the field. Defaults to ``None``.
        deprecated: A deprecation message, an instance of `Deprecated`, or a
            boolean. If ``True``, a default deprecation message will be emitted
            when accessing the field. Defaults to ``None``.
        repr: Whether or not to include the field in the representation.
            Defaults to ``False`` for private properties and ``True`` for
            public properties.
        json_schema_extra: Dictionary or callable to provide extra JSON schema
            properties. Defaults to ``None``.
    """
    decorator_repr: ClassVar[str] = '@computed_field'

    # Source computed field information
    wrapped_property: property
    name: str
    # Computed field information
    return_type: Any
    alias: str
    alias_priority: int | None
    slug: str
    title: str
    description: str | None
    examples: list[Any] | None
    deprecated: Deprecated | str | bool | None
    repr: bool
    json_schema_extra: JsonSchemaDict | Callable[[JsonSchemaDict], None] | None

    def _create_field_definition(self) -> FieldDefinition:
        """Create a field definition from the computed field information."""
        # Retrieve annotation from field information or property getter
        if self.return_type is not Undefined:
            annotation = self.return_type
        else:
            prop_func = getattr(self.wrapped_property, 'fget', None)
            prop_annotations = getattr(prop_func, '__annotations__', {})
            annotation = prop_annotations.get('return', None)
            if annotation is None:
                raise PlateformeError(
                    f"Cannot create field definition for computed field "
                    f"{self.name!r}. The wrapped property must have a getter "
                    f"function with a return type annotation.",
                    code='field-invalid-config',
                )

        # Retrieve raw field information from computed field attributes
        field = Field(
            ...,
            alias=self.alias,
            alias_priority=self.alias_priority,
            slug=self.slug,
            title=self.title,
            description=self.description,
            examples=self.examples,
            deprecated=self.deprecated,
            repr=self.repr,
            json_schema_extra=self.json_schema_extra,
        )

        return annotation, field


@typing.overload
def computed_field(__func: _TProperty) -> _TProperty:
    ...

@typing.overload
def computed_field(
    *,
    return_type: Any = Undefined,
    alias: str | None = None,
    alias_priority: int | None = None,
    slug: str | None = None,
    title: str | None = None,
    description: str | None = None,
    examples: list[Any] | None = None,
    deprecated: Deprecated | str | bool | None = None,
    repr: bool = True,
    json_schema_extra: JsonSchemaDict \
        | Callable[[JsonSchemaDict], None] | None = None,
) -> Callable[[_TProperty], _TProperty]:
    ...

def computed_field(
    __func: _TProperty | None = None,
    *,
    return_type: Any = Undefined,
    alias: str | None = None,
    alias_priority: int | None = None,
    slug: str | None = None,
    title: str | None = None,
    description: str | None = None,
    examples: list[Any] | None = None,
    deprecated: Deprecated | str | bool | None = None,
    repr: bool | None = None,
    json_schema_extra: JsonSchemaDict \
        | typing.Callable[[JsonSchemaDict], None] | None = None,
) -> _TProperty | Callable[[_TProperty], _TProperty]:
    """A decorator for computed fields.

    It is used to include `property` and `cached_property` when serializing
    models or dataclasses. This is useful for fields that are computed from
    other fields, or for fields that are expensive to compute and should be
    cached.

    Args:
        __func: The property function to wrap. Defaults to ``None``.
        return_type: An optional return type for serialization logic to expect
            when serializing to JSON. If included, this must be correct,
            otherwise a ``TypeError`` is raised. If no return type is specified
            ``Any`` is used, which does runtime introspection to handle
            arbitrary objects.
        alias: The alias name of the field. It must adhere to a specific
            ``ALIAS`` pattern as defined in the framework's regular expressions
            repository. It is used when serializing the computed field if
            ``by_alias=True``. Defaults to ``None``.
        alias_priority: The priority of the field's alias. This affects whether
            an alias generator is used or not. Defaults to ``None``.
        slug: The slug name of the field. It must adhere to a specific ``SLUG``
            pattern as defined in the framework's regular expressions
            repository. Defaults to ``None``.
        title: The human-readable name of the field. It must adhere to a
            specific ``TITLE`` pattern as defined in the framework's regular
            expressions repository. Defaults to ``None``.
        description: The description of the field. Defaults to ``None`` and
            uses the function's docstring if available.
        examples: List of examples of the field. Defaults to ``None``.
        deprecated: A deprecation message, an instance of `Deprecated`, or a
            boolean. If ``True``, a default deprecation message will be emitted
            when accessing the field. Defaults to ``None``.
        repr: Whether or not to include the field in the representation.
            Defaults to ``False`` for private properties and ``True`` for
            public properties.
        json_schema_extra: Dictionary or callable to provide extra JSON schema
            properties. Defaults to ``None``.

    Returns:
        A proxy wrapper for the property.

    Raises:
        PlateformeError: At least one identifier must be either inferred from
            the function name or provided as an argument. If none are provided,
            an error iis raised. The identifier is used to generate the field's
            ``name``, ``alias``, ``title``, and ``slug``. Eacb must adhere to
            specific regular expression patterns defined in the framework's
            regular expressions repository.

    Examples:
        >>> from plateforme import BaseModel, computed_field
        >>> class Rectangle(BaseModel):
        ...     width: int
        ...     length: int
        ...
        ...     @computed_field
        ...     @property
        ...     def area(self) -> int:
        ...         return self.width * self.length

        >>> print(Rectangle(width=3, length=2).model_dump())
        {'width': 3, 'length': 2, 'area': 6}

        If applied to functions not yet decorated with ``@property`` or
        ``@cached_property``, the function is automatically wrapped with
        `property`. Although this is more concise, you will lose intellisense
        in your IDE, and confuse static type checkers, thus explicit use of
        `@property` is recommended.

        >>> from plateforme import BaseModel, computed_field
        >>> class Square(BaseModel):
        ...    width: float
        ...
        ...    # converted to a "property" by "computed_field"
        ...    @computed_field
        ...    def area(self) -> float:
        ...        return round(self.width**2, 2)
        ...
        ...   @area.setter
        ...   def area(self, new_area: float) -> None:
        ...       self.width = new_area**0.5
        ...
        ...   @computed_field(alias='the magic number', repr=False)
        ...   def random_number(self) -> int:
        ...       return random.randint(0, 1000)

        >>> square = Square(width=1.3)
        ... print(repr(square))
        Square(width=1.3, area=1.69)

        >>> print(square.random_number)
        3

        >>> square.area = 4
        ... print(square.model_dump_json(by_alias=True))
        {"width": 2.0, "area": 4.0, "the magic number": 3}

        It is not possible to override a field from a parent class with a
        `computed_field` in the child class. MyPy complains about this behavior
        if allowed, and `dataclasses` doesn't allow this pattern either as
        shown in the example below:

        >>> from plateforme import BaseModel, computed_field
        >>> class Parent(BaseModel):
        ...     a: str

        >>> try:
        ...     class Child(Parent):
        ...         @computed_field
        ...         @property
        ...         def a(self) -> str:
        ...             return 'new a'
        ... except ValueError as e:
        ...     print(repr(e))
        ValueError('you can't override a field with a computed field')

        The private properties decorated with ``@computed_field`` have their
        representation set to false ``repr=False`` by default:

        >>> from functools import cached_property
        >>> from plateforme import BaseModel, computed_field
        >>> class Model(BaseModel):
        ...     foo: int
        ...
        ...     @computed_field
        ...     @cached_property
        ...     def _private_cached_property(self) -> int:
        ...         return -self.foo
        ...
        ...     @computed_field
        ...     @property
        ...     def _private_property(self) -> int:
        ...         return -self.foo

        >>> model = Model(foo=1)
        ... print(repr(model))
        Model(foo=1)

    Note:
        Using MyPy, even with the ``@property`` or ``@cached_property`` applied
        to your function before ``@computed_field``, it may throw a "Decorated
        property not supported" error.
        See https://github.com/python/mypy/issues/1362
    """

    def wrapper(func: Any) -> Any:
        nonlocal alias, alias_priority, slug, title, description, repr

        # Collect computed field information alias priority
        alias_priority = (alias_priority or 2) if alias is not None else None

        # Retrieve computed field information identifier
        name: str | None
        if isinstance(func, property):
            name = getattr(func.fget, '__name__', None)
        else:
            name = getattr(func, '__name__', None)
        identifier = to_name_case(name or alias or slug or title or '')

        # Check if identifier is valid
        if not identifier:
            # Unlike standard fields, computed fields must have a valid
            # identifier to be used in the field information namespace.
            raise PlateformeError(
                "A computed field must have a valid identifier. Either ensure "
                "the decorated function has a name or provide a valid "
                "`alias`, `slug`, or `title` argument.",
                code='field-invalid-config',
            )

        # Update computed field information namespace
        name = name or identifier
        alias = alias or identifier
        slug = slug or to_path_case(identifier)
        title = title or to_title_case(identifier)

        # Validate computed field information namespace
        def validate(key: str, pattern: str, value: str) -> None:
            if re.match(pattern, value):
                return
            raise PlateformeError(
                f"The computed field with identifier {identifier!r} has an "
                f"invalid attribute {key} {value!r} in its configuration. It "
                f"must match a specific pattern defined in the framework "
                f"regular expressions repository.",
                code='field-invalid-config',
            )
        validate('name', RegexPattern.ALIAS, name)
        validate('alias', RegexPattern.ALIAS, alias)
        validate('slug', RegexPattern.SLUG, slug)
        validate('title', RegexPattern.TITLE, title)

        # Unwrap the function and update documentation
        unwrapped = _decorators.unwrap_wrapped_function(func)
        if description is None and unwrapped.__doc__:
            description = inspect.cleandoc(unwrapped.__doc__)

        # Wrap the function if it is not already decorated with "@property"
        # (or another descriptor).
        wrapped_property = _decorators.ensure_property(func)

        # Update reprerentation if not set
        if repr is None:
            repr = False if is_private(prop=wrapped_property) else True

        wrapper_info = ComputedFieldInfo(
            wrapped_property=wrapped_property,
            name=name,
            return_type=return_type,
            alias=alias,
            alias_priority=alias_priority,
            slug=slug,
            title=title,
            description=description,
            examples=examples,
            deprecated=deprecated,
            repr=repr,
            json_schema_extra=json_schema_extra,
        )

        return _decorators.PydanticDescriptorProxy(
            wrapped_property, wrapper_info
        )

    if __func is None:
        return wrapper
    else:
        return wrapper(__func)  # type: ignore[no-any-return]


# MARK: Utilities

class FieldLookup(TypedDict, total=False):
    """A model field lookup configuration."""

    computed: bool | None
    """Whether to include computed fields in the lookup configuration. When
    set to ``True``, field definitions for computed fields are included in the
    lookup configuration. Defaults to ``None``."""

    include: dict[str, IncExPredicate] | None
    """The filters for including specific fields as a dictionary with the field
    attribute names as keys and the values to match. Specified keys can use
    the ``.`` notation to access nested attributes. Additionally, the lookup
    attributes can be callables without arguments. Defaults to ``None``."""

    exclude: dict[str, IncExPredicate] | None
    """The filters for excluding specific fields as a dictionary with the field
    attribute names as keys and the values to not match. Specified keys can use
    the ``.`` notation to access nested attributes. Additionally, the lookup
    attributes can be callable without arguments. Defaults to ``None``."""

    partial: bool | None
    """Whether to mark the field annotations as optional.
    Defaults to ``None``."""

    default: dict[str, Any] | None
    """The default to apply and set within the field information.
    Defaults to ``None``."""

    update: dict[str, Any] | None
    """The update to apply and set within the field information.
    Defaults to ``None``."""

    override: 'FieldLookup | None'
    """The field lookup configuration to override the current configuration.
    This can be used to narrow down the field lookup configuration to specific
    fields. Multiple levels of nested configurations can be provided and will
    be resolved recursively. Defaults to ``None``."""


def _resolve_target_from_annotation(
    owner: Any,
    annotation: Any,
) -> tuple[Literal['list', 'set'] | None, 'ResourceType | str']:
    """Resolve the target resource for a given field annotation.

    This function is designed to interpret the type annotations used in
    resource fields, determining the associated target resource type or a
    string identifier. It handles various annotation formats, including forward
    references, optional types, and collections. The function also identifies
    if the target annotation implies a one-to-many relationship.

    Args:
        owner: The owner resource of the field for which to resolve the target
            resource, it is used to resolve relative forward references.
        annotation: The annotation to resolve the target resource from.

    Returns:
        A tuple where the first element is a literal indicating the collection
        type of the target association (i.e., ``list`` or ``set``), or ``None``
        if the association is not a collection. The second element is the
        resolved target resource type or identifier.

    Raises:
        PlateformeError: If the annotation cannot be resolved due to incorrect
            configuration or if the annotation is a union with incompatible
            types.
        TypeError: If the target resource cannot be determined from the
            annotation, typically when the annotation does not conform to
            expected formats (e.g., unsupported collection types or invalid
            forward references).

    Note:
        This function is intended for internal use within a framework or
        library that deals with resource relationships defined through
        annotations.
    """
    from ..runtime import __plateforme__

    collection: Literal['list', 'set'] | None = None
    target = annotation
    args = typing.get_args(target)
    origin = typing.get_origin(target)

    # Check if annotation is a union
    if origin in (Union, UnionType):
        args = tuple(arg for arg in args if arg != NoneType)
        if len(args) != 1:
            raise TypeError(
                f"Cannot resolve target name from union annotation "
                f"{annotation!r} except when using `None` as an optional "
                f"argument."
            )
        target = args[0]
        origin = typing.get_origin(target)
        args = typing.get_args(target)

    # Check if annotation is a collection
    if isinstance(origin, type) and issubclass(origin, Iterable):
        if len(args) != 1:
            raise TypeError(
                f"Cannot resolve target name from collection annotation "
                f"{annotation!r} with multiple generic arguments."
            )
        collection = 'set' if issubclass(origin, AbstractSet) else 'list'
        target = args[0]
        origin = typing.get_origin(target)
        args = typing.get_args(target)

    # Check if target is a valid forward reference or a standard type with a
    # valid configuration owner type. Forward references are resolved using the
    # owner's module name.
    if origin is None:
        if is_resource(target):
            return collection, target
        if isinstance(target, ForwardRef):
            # Check if forward reference exists in the runtime
            if target.__forward_arg__ in __plateforme__.resources:
                return collection, target.__forward_arg__
            # Resolve forward reference
            forwardref = resolve_forwardref_fullname(owner.__module__, target)
            if forwardref:
                target.__forward_arg__ = forwardref
            else:
                raise TypeError(
                    f"Cannot resolve target name from forward reference "
                    f"{target!r} in annotation {annotation!r} for "
                    f"resource {owner.__qualname__!r}."
                )
            return collection, forwardref

    raise TypeError(
        f"Cannot resolve target name from annotation {annotation!r}. "
        f"Annotation must be a standard type or a generic collection of a "
        f"standard type (optionals are allowed)."
    )
