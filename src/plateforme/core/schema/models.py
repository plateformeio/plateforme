# plateforme.core.schema.models
# -----------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing models, validation and
serialization within the Plateforme framework using Pydantic features.

The `BaseModel` class is the foundational base for all models within the
Plateforme framework. It extends Pydantic's `BaseModel` with additional
functionality and integrates with the framework resource and service classes.

The `ModelConfig` class is a configuration object used to define various
settings and behaviors for Plateforme models, such as validation rules and
serialization options.

Examples:
    >>> from plateforme import BaseModel, Field
    ...
    >>> class FooModel(BaseModel):
    ...     name: str = Field(
    ...         ...,
    ...         unique=True,
    ...         title='Foo Model',
    ...         description='Name of the foo instance')
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
    See also the `Field` function for more information on modeling features.
"""

import inspect
import re
import typing
from collections.abc import Mapping, Sequence
from copy import copy, deepcopy
from types import UnionType
from typing import (
    Annotated,
    Any,
    Callable,
    ClassVar,
    Generic,
    Literal,
    Optional,
    Self,
    Type,
    TypeVar,
    TypeVarTuple,
    Union,
    Unpack,
)

from pydantic._internal import _mock_val_ser
from pydantic._internal._forward_ref import PydanticRecursiveRef
from pydantic._internal._model_construction import ModelMetaclass as _ModelMeta
from pydantic.main import (
    BaseModel as _BaseModel,
    create_model as _create_model,
)
from typing_extensions import TypedDict

from ..config import Configurable, ConfigurableMeta, ConfigWrapper
from ..context import VALIDATION_CONTEXT
from ..errors import MissingDeferred, PlateformeError
from ..expressions import IncEx, IncExPredicate
from ..patterns import (
    RegexPattern,
    match_any_pattern,
    pluralize,
    to_name_case,
    to_path_case,
    to_title_case,
)
from ..representations import ReprArgs, Representation
from ..typing import (
    ClassMethodType,
    Deferred,
    Undefined,
    classproperty,
    get_object_name,
    has_stub_noop,
    is_annotated,
    is_model,
    is_resource,
    isbaseclass_lenient,
)
from ..utils import get_meta_orig_bases
from . import core as core_schema
from .aliases import AliasGenerator
from .core import (
    CoreSchema,
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
    PydanticOmit,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    ValidationInfo,
    ValidationMode,
    ValidatorFunctionWrapHandler,
    recursion_manager,
    validation_manager,
)
from .fields import (
    ComputedFieldInfo,
    ConfigField,
    Field,
    FieldDefinition,
    FieldInfo,
    FieldLookup,
    PrivateAttr,
)
from .json import (
    DEFAULT_REF_TEMPLATE,
    GenerateJsonSchema,
    JsonEncoder,
    JsonSchemaDict,
    JsonSchemaExtraCallable,
    JsonSchemaMode,
    JsonSchemaSource,
)
from .types import Discriminator, TypeAdapterList

if typing.TYPE_CHECKING:
    from ..resources import ResourceType

FORBIDDEN_ATTRS = (r'Config', r'resource_.*', r'service_.*')
PROTECTED_ATTRS = (r'__config__', r'model_.*')

PROTECTED_NAMESPACES = tuple(
    item.replace('.*', '')
    for item in FORBIDDEN_ATTRS + PROTECTED_ATTRS
    if re.search(r'\.\*$', item)
)

__all__ = (
    'BaseModel',
    'BaseModelConfigDict',
    'DiscriminatedModel',
    'DiscriminatedModelMeta',
    'DiscriminatedModelType',
    'Model',
    'ModelConfig',
    'ModelConfigDict',
    'ModelMeta',
    'ModelFieldInfo',
    'ModelType',
    'NoInitField',
    'RootModel',
    'RootModelMeta',
    'RootModelType',
    'collect_fields',
    'collect_models',
    'create_discriminated_model',
    'create_model',
    'create_root_model',
)


Model = TypeVar('Model', bound='BaseModel')
"""A type variable for a model class."""


ModelType = Type['BaseModel']
"""A type alias for a model class."""


ModelFieldInfo = FieldInfo['BaseModel']
"""A type alias for a model field information."""


RootModelType = Type['RootModel[Any]']
"""A type alias for a root model class."""


DiscriminatedModelType = Type['DiscriminatedModel[BaseModel]']
"""A type alias for a discriminated model class."""


def NoInitField(*, init: Literal[False] = False) -> Any:
    """Only for typing purposes. Used as default value of the attribute
    `__pydantic_fields_set__`, `__pydantic_extra__`, `__pydantic_private__`, so
    they could be ignored when synthesizing the `__init__` signature.

    See Pydantic base model metaclass signature for more information.
    """


# MARK: Model Configuration

class BaseModelConfigDict(TypedDict, total=False):
    """A base model class configuration dictionary."""

    alias: str
    """The alias name of the model. It must adhere to a specific ``ALIAS``
    pattern as defined in the framework's regular expressions repository. It is
    inferred from the snake case version of the resolved model identifier."""

    slug: str
    """The slug name of the model. It must adhere to a specific ``SLUG``
    pattern as defined in the framework's regular expressions repository. It is
    inferred from the pluralized kebab case version of the model identifier."""

    title: str
    """The human-readable name of the model. It must adhere to a specific
    ``TITLE`` pattern as defined in the framework's regular expressions
    repository. It is inferred from the titleized version of the model
    identifier."""

    str_to_lower: bool
    """Whether to convert strings to lowercase. Defaults to ``False``."""

    str_to_upper: bool
    """Whether to convert strings to uppercase. Defaults to ``False``."""

    str_strip_whitespace: bool
    """Whether to strip whitespace from strings. Defaults to ``False``."""

    str_min_length: int
    """The minimum length for strings. Defaults to ``None``."""

    str_max_length: int | None
    """The maximum length for strings. Defaults to ``None``."""

    frozen: bool
    """Whether to freeze the configuration. Defaults to ``False``."""

    populate_by_name: bool
    """Whether to populate fields by name. Defaults to ``False``."""

    use_enum_values: bool
    """Whether to use enum values. Defaults to ``False``."""

    validate_assignment: bool
    """Whether to validate assignments. Defaults to ``False``."""

    arbitrary_types_allowed: bool
    """Whether to allow arbitrary types. Defaults to ``False``."""

    from_attributes: bool
    """Whether to set attributes from the configuration.
    Defaults to ``False``."""

    loc_by_alias: bool
    """Whether to use the alias for error ``loc``s. Defaults to ``True``."""

    alias_generator: Callable[[str], str] | AliasGenerator | None
    """A callable or alias generator to create aliases for the model.
    Defaults to ``None``."""

    ignored_types: tuple[type, ...]
    """A tuple of types to ignore. Defaults to an empty tuple."""

    allow_inf_nan: bool
    """Whether to allow infinity and NaN. Defaults to ``True``."""

    json_schema_extra: JsonSchemaExtraCallable | None
    """Dictionary of extra JSON schema properties. Defaults to ``None``."""

    json_encoders: dict[type[object], JsonEncoder] | None
    """A dictionary of custom JSON encoders for specific types.
    Defaults to ``None``."""

    strict: bool
    """Whether to make the configuration strict. Defaults to ``False``."""

    revalidate_instances: Literal['always', 'never', 'subclass-instances']
    """When and how to revalidate models and dataclasses during validation.
    Defaults to ``never``."""

    ser_json_timedelta: Literal['iso8601', 'float']
    """The format of JSON serialized timedeltas. Defaults to ``iso8601``."""

    ser_json_bytes: Literal['utf8', 'base64']
    """The encoding of JSON serialized bytes. Defaults to ``utf8``."""

    ser_json_inf_nan: Literal['null', 'constants']
    """The encoding of JSON serialized infinity and NaN float values. Accepts
    the string values of ``'null'`` and ``'constants'``.
    Defaults to ``'null'``."""

    validate_default: bool
    """Whether to validate default values during validation.
    Defaults to ``False``."""

    validate_return: bool
    """Whether to validate return values during validation.
    Defaults to ``False``."""

    protected_namespaces: tuple[str, ...]
    """A tuple of strings that prevent models to have field which conflict with
    them. The provided namespaces are added to the internally forbidden and
    protected ones, ``model_``, ``resource_``, and ``service_``.
    Defaults to an empty tuple."""

    hide_input_in_errors: bool
    """Whether to hide inputs when printing errors. Defaults to ``False``."""

    plugin_settings: dict[str, object] | None
    """A dictionary of settings for plugins. Defaults to  ``None``."""

    schema_generator: type[Any] | None
    """A custom core schema generator class to use when generating JSON
    schemas. Defaults to ``None``."""

    json_schema_serialization_defaults_required: bool
    """Whether fields with default values should be marked as required in the
    serialization schema. Defaults to ``False``."""

    json_schema_mode_override: Literal['validation', 'serialization'] | None
    """If not ``None``, the specified mode will be used to generate the JSON
    schema regardless of what `mode` was passed to the function call.
    Defaults to ``None``."""

    coerce_numbers_to_str: bool
    """If ``True``, enables automatic coercion of any `Number` type to `str` in
    ``lax`` (non-strict) mode. Defaults to ``False``."""

    regex_engine: Literal['rust-regex', 'python-re']
    """The regex engine to use for pattern validation.
    Defaults to ``rust-regex``."""

    validation_error_cause: bool
    """If ``True``, Python exceptions that were part of a validation failure
    will be shown as an exception group as a cause. Can be useful for
    debugging. Defaults to ``False``."""

    use_attribute_docstrings: bool
    """Whether docstrings of attributes should be used for field descriptions.
    Defaults to ``False``."""

    cache_strings: bool | Literal['all', 'keys', 'none']
    """Whether to cache strings to avoid constructing new Python objects.
    Enabling this setting should significantly improve validation performance
    while increasing memory usage slightly.
    - ``True`` or ``'all'`` (default): Cache all strings
    - ``'keys'``: Cache only dictionary keys
    - ``False`` or ``'none'``: No caching
    Defaults to ``True``.
    """


class ModelConfigDict(BaseModelConfigDict, total=False):
    """A model class configuration dictionary."""

    defer_build: bool
    """Whether to defer model validator and serializer construction until the
    first model validation. Defaults to ``False``."""

    extra: Literal['allow', 'ignore', 'forbid']
    """Extra values to include in this configuration.
    Defaults to ``forbid``."""


class ModelConfig(ConfigWrapper):
    """A model class configuration."""
    if typing.TYPE_CHECKING:
        __config_owner__: ModelType = ConfigField(frozen=True, init=False)

    type_: str = ConfigField(default='model', frozen=True, init=False)
    """The configuration owner type set to ``model``. It is a protected field
    that is typically used with `check_config` to validate an object type
    without using `isinstance` in order to avoid circular imports."""

    stub: bool = ConfigField(default=False, frozen=True, init=False)
    """Whether the model is a stub model. This is set to ``True`` when a
    collected bare model has a final stub no-operation statement.
    Defaults to ``False``."""

    alias: str = Deferred
    """The alias name of the model. It must adhere to a specific ``ALIAS``
    pattern as defined in the framework's regular expressions repository. It is
    inferred from the snake case version of the resolved model identifier."""

    slug: str = Deferred
    """The slug name of the model. It must adhere to a specific ``SLUG``
    pattern as defined in the framework's regular expressions repository. It is
    inferred from the pluralized kebab case version of the model identifier."""

    title: Annotated[str, 'pydantic'] = Deferred
    """The human-readable name of the model. It must adhere to a specific
    ``TITLE`` pattern as defined in the framework's regular expressions
    repository. It is inferred from the titleized version of the model
    identifier."""

    str_to_lower: Annotated[bool, 'pydantic'] = False
    """Whether to convert strings to lowercase. Defaults to ``False``."""

    str_to_upper: Annotated[bool, 'pydantic'] = False
    """Whether to convert strings to uppercase. Defaults to ``False``."""

    str_strip_whitespace: Annotated[bool, 'pydantic'] = False
    """Whether to strip whitespace from strings. Defaults to ``False``."""

    str_min_length: Annotated[int, 'pydantic'] = 0
    """The minimum length for strings. Defaults to ``None``."""

    str_max_length: Annotated[int | None, 'pydantic'] = None
    """The maximum length for strings. Defaults to ``None``."""

    extra: Annotated[
        Literal['allow', 'ignore', 'forbid'], 'pydantic'
    ] = 'forbid'
    """Extra values to include in this configuration.
    Defaults to ``forbid``."""

    frozen: Annotated[bool, 'pydantic'] = False
    """Whether to freeze the configuration. Defaults to ``False``."""

    populate_by_name: Annotated[bool, 'pydantic'] = False
    """Whether to populate fields by name. Defaults to ``False``."""

    use_enum_values: Annotated[bool, 'pydantic'] = False
    """Whether to use enum values. Defaults to ``False``."""

    validate_assignment: Annotated[bool, 'pydantic'] = False
    """Whether to validate assignments. Defaults to ``False``."""

    arbitrary_types_allowed: Annotated[bool, 'pydantic'] = False
    """Whether to allow arbitrary types. Defaults to ``False``."""

    from_attributes: Annotated[bool, 'pydantic'] = False
    """Whether to set attributes from the configuration.
    Defaults to ``False``."""

    loc_by_alias: Annotated[bool, 'pydantic'] = True
    """Whether to use the alias for error ``loc``s. Defaults to ``True``."""

    alias_generator: Annotated[
        Callable[[str], str] | AliasGenerator | None, 'pydantic'
    ] = to_name_case
    """A callable or alias generator to create aliases for the model.
    Defaults to ``None``."""

    ignored_types: Annotated[tuple[type, ...], 'pydantic'] = ()
    """A tuple of types to ignore. Defaults to an empty tuple."""

    allow_inf_nan: Annotated[bool, 'pydantic'] = True
    """Whether to allow infinity and NaN. Defaults to ``True``."""

    json_schema_extra: Annotated[
        JsonSchemaExtraCallable | None, 'pydantic'
    ] = None
    """Dictionary of extra JSON schema properties. Defaults to ``None``."""

    json_encoders: Annotated[
        dict[type[object], JsonEncoder] | None, 'pydantic'
    ] = None
    """A dictionary of custom JSON encoders for specific types.
    Defaults to ``None``."""

    strict: Annotated[bool, 'pydantic'] = False
    """Whether to make the configuration strict. Defaults to ``False``."""

    revalidate_instances: Annotated[
        Literal['always', 'never', 'subclass-instances'], 'pydantic'
    ] = 'never'
    """When and how to revalidate models and dataclasses during validation.
    Defaults to ``never``."""

    ser_json_timedelta: Annotated[
        Literal['iso8601', 'float'], 'pydantic'
    ] = 'iso8601'
    """The format of JSON serialized timedeltas. Defaults to ``iso8601``."""

    ser_json_bytes: Annotated[Literal['utf8', 'base64'], 'pydantic'] = 'utf8'
    """The encoding of JSON serialized bytes. Defaults to ``utf8``."""

    ser_json_inf_nan: Annotated[
        Literal['null', 'constants'], 'pydantic'
    ] = 'null'
    """The encoding of JSON serialized infinity and NaN float values. Accepts
    the string values of ``'null'`` and ``'constants'``.
    Defaults to ``'null'``."""

    validate_default: Annotated[bool, 'pydantic'] = False
    """Whether to validate default values during validation.
    Defaults to ``False``."""

    validate_return: Annotated[bool, 'pydantic'] = False
    """Whether to validate return values during validation.
    Defaults to ``False``."""

    protected_namespaces: Annotated[
        tuple[str, ...], 'pydantic'
    ] = Deferred
    """A tuple of strings that prevent models to have field which conflict with
    them. The provided namespaces are added to the internally forbidden and
    protected ones, ``model_``, ``resource_``, and ``service_``.
    Defaults to an empty tuple."""

    hide_input_in_errors: Annotated[bool, 'pydantic'] = False
    """Whether to hide inputs when printing errors. Defaults to ``False``."""

    defer_build: Annotated[bool, 'pydantic'] = False
    """Whether to defer model validator and serializer construction until the
    first model validation. Defaults to ``False``."""

    plugin_settings: Annotated[dict[str, object] | None, 'pydantic'] = None
    """A dictionary of settings for plugins. Defaults to  ``None``."""

    schema_generator: Annotated[type[Any] | None, 'pydantic'] = None
    """A custom core schema generator class to use when generating JSON
    schemas. Defaults to ``None``."""

    json_schema_serialization_defaults_required: Annotated[
        bool, 'pydantic'
    ] = False
    """Whether fields with default values should be marked as required in the
    serialization schema. Defaults to ``False``."""

    json_schema_mode_override: Annotated[
        Literal['validation', 'serialization'] | None, 'pydantic'
    ] = None
    """If not ``None``, the specified mode will be used to generate the JSON
    schema regardless of what `mode` was passed to the function call.
    Defaults to ``None``."""

    coerce_numbers_to_str: Annotated[bool, 'pydantic'] = False
    """If ``True``, enables automatic coercion of any `Number` type to `str` in
    ``lax`` (non-strict) mode. Defaults to ``False``."""

    regex_engine: Annotated[
        Literal['rust-regex', 'python-re'], 'pydantic'
    ] = 'rust-regex'
    """The regex engine to use for pattern validation.
    Defaults to ``rust-regex``."""

    validation_error_cause: Annotated[bool, 'pydantic'] = False
    """If ``True``, Python exceptions that were part of a validation failure
    will be shown as an exception group as a cause. Can be useful for
    debugging. Defaults to ``False``."""

    use_attribute_docstrings: Annotated[bool, 'pydantic'] = False
    """Whether docstrings of attributes should be used for field descriptions.
    Defaults to ``False``."""

    cache_strings: Annotated[
        bool | Literal['all', 'keys', 'none'], 'pydantic'
    ] = True
    """Whether to cache strings to avoid constructing new Python objects.
    Enabling this setting should significantly improve validation performance
    while increasing memory usage slightly.
    - ``True`` or ``'all'`` (default): Cache all strings
    - ``'keys'``: Cache only dictionary keys
    - ``False`` or ``'none'``: No caching
    Defaults to ``True``.
    """

    def post_init(self) -> None:
        """Post-initialization steps for the model configuration."""
        # Validate protected namespaces
        self.setdefault('protected_namespaces', PROTECTED_NAMESPACES)
        if self.check('protected_namespaces', scope='set'):
            self.protected_namespaces = tuple(dict.fromkeys(
                PROTECTED_NAMESPACES + self.protected_namespaces
            ))

        # Skip post-initialization if the configuration owner is not set
        if self.__config_owner__ is None:
            return

        cls_name = self.__config_owner__.__name__
        cls_qualname = self.__config_owner__.__qualname__

        # Validate configuration alias
        self.setdefault('alias', to_name_case(cls_name, ('all', None)))
        if not re.match(RegexPattern.ALIAS, self.alias):
            raise PlateformeError(
                f"The model {cls_qualname!r} has an invalid alias "
                f"{self.alias!r} in its configuration. It must match a "
                f"specific pattern `ALIAS` defined in the framework's regular "
                f"expressions repository.",
                code='model-invalid-config',
            )

        # Validate configuration slug
        self.setdefault('slug', to_path_case(pluralize(self.alias)))
        if not re.match(RegexPattern.SLUG, self.slug):
            raise PlateformeError(
                f"The model {cls_qualname!r} has an invalid slug "
                f"{self.slug!r} in its configuration. It must match a "
                f"specific pattern `SLUG` defined in the framework's regular "
                f"expressions repository.",
                code='model-invalid-config',
            )

        # Validate configuration title
        self.setdefault('title', to_title_case(self.alias))
        if not re.match(RegexPattern.TITLE, self.title):
            raise PlateformeError(
                f"The model {cls_qualname!r} has an invalid title "
                f"{self.title!r} in its configuration. It must match a "
                f"specific pattern `TITLE` defined in the framework's regular "
                f"expressions repository.",
                code='model-invalid-config',
            )


# MARK: Model Metaclass

@typing.dataclass_transform(
    kw_only_default=True,
    field_specifiers=(Field, PrivateAttr, NoInitField)
)
class ModelMeta(ConfigurableMeta, _ModelMeta):
    """Meta class for the base model class."""
    if typing.TYPE_CHECKING:
        __config__: ModelConfig | ModelConfigDict
        __pydantic_owner__: Literal['model', 'resource']
        __pydantic_resource__: 'ResourceType | None'
        model_adapter: TypeAdapterList['BaseModel']
        model_config: ModelConfig
        model_fields: dict[str, ModelFieldInfo]

    def __new__(
        mcls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        /,
        __pydantic_owner__: Literal['model', 'resource'] = 'model',
        __pydantic_resource__: 'ResourceType | None' = None,
        __pydantic_generic_metadata__: dict[str, Any] | None = None,
        __pydantic_reset_parent_namespace__: bool = True,
        _create_model_module: str | None = None,
        **kwargs: Any,
    ) -> type:
        """Create a new model meta class.

        Args:
            name: The name of the class to be created.
            bases: The base classes of the class to be created.
            namespace: The attribute dictionary of the class to be created.
            __pydantic_owner__: The owner of the model fields, either the
                model itself or the resource it belongs to.
                Defaults to ``'model'``.
            __pydantic_resource__: The resource that the model belongs to.
            __pydantic_generic_metadata__: Metadata for generic models.
            __pydantic_reset_parent_namespace__: Reset parent namespace.
            _create_model_module: The module of the class to be created, if
                created by `create_model`.
            **kwargs: Configurable metaclass arguments.

        Returns:
            The new model class created by the metaclass.
        """
        # Check if the namespace has any forbidden attributes
        for attr in namespace:
            if match_any_pattern(attr, *FORBIDDEN_ATTRS):
                raise AttributeError(
                    f"Attribute {attr!r} cannot be set on model class "
                    f"{name!r} as it is forbidden."
                )

        # Pop base configuration
        kwargs_config = ModelConfig.__config_fields__
        kwargs_base = {
            key: kwargs.pop(key)
            for key in dict(kwargs)
            if key not in kwargs_config
                or 'pydantic' in kwargs_config[key].metadata
        }

        # It is necessary to ensure that the owner and resource are sets to
        # their default values when the model is first created to avoid
        # conflicts with the schema generation and validation.
        namespace = {
            **namespace,
            '__pydantic_owner__': 'model',
            '__pydantic_resource__': None,
        }

        cls = super().__new__(
            mcls,
            name,
            bases,
            namespace,
            __pydantic_generic_metadata__,
            __pydantic_reset_parent_namespace__,
            _create_model_module,
            config_attr='model_config',
            **kwargs_base
        )

        setattr(cls, '__pydantic_owner__', __pydantic_owner__)
        setattr(cls, '__pydantic_resource__', __pydantic_resource__)

        # Update model configuration
        model_config: ModelConfig = getattr(cls, '__config__')
        model_config.merge(kwargs)

        return cls

    def __init__(
        cls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize a new model meta class."""
        # Retrieve field owner
        if cls.__pydantic_owner__ == 'model':
            field_owner = cls
        elif cls.__pydantic_resource__ is not None:
            field_owner = cls.__pydantic_resource__  # type: ignore
        else:
            raise PlateformeError(
                f"THe model fields owner cannot be set to `resource` without "
                f"providing a resource class for the model {name!r}.",
                code='model-invalid-config',
            )

        # Update fields information
        for key, field in cls.model_fields.items():
            cls.model_fields[key] = \
                FieldInfo.from_field_info(field, owner=field_owner, name=key)

        # Check fields for duplicated associations
        for field_a in cls.model_fields.values():
            for field_b in cls.model_fields.values():
                if field_a is field_b:
                    continue
                if field_a.linked and field_b.linked \
                        and field_a.target == field_b.target \
                        and field_a.association_alias == \
                            field_b.association_alias:
                    raise PlateformeError(
                        f"Link {field_a.alias!r} and {field_b.alias!r} have "
                        f"the same target {field_a.target!r} and association "
                        f"alias {field_a.association_alias!r}.",
                        code='model-invalid-config',
                    )

        # Set the model type adapter
        if not kwargs.get('defer_build', False):
            try:
                adapter = TypeAdapterList(cls)
                setattr(cls, '__pydantic_adapter__', adapter)
            except:
                pass


# MARK: Base Model

class BaseModel(_BaseModel, Configurable[ModelConfig], metaclass=ModelMeta):
    """Base class for all Plateforme models.

    It exposes the base class for all models within the Plateforme framework.

    Attributes:
        __config__: The configuration class for the model.

        __pydantic_owner__: The owner of the model fields, either the model
            itself or the resource it belongs to. Defaults to ``'model'``.
        __pydantic_resource__: The resource that the model belongs to.

        __class_vars__: The names of classvars defined on the model.
        __private_attributes__: Metadata about the private attributes of the
            model.
        __signature__: The signature for instantiating the model.

        __pydantic_complete__: Whether model building is completed, or if there
            are still undefined fields.
        __pydantic_validated__: Whether the model has been validated or
            directly constructed.
        __pydantic_core_schema__: The pydantic-core schema used to build the
            `SchemaValidator` and `SchemaSerializer`.
        __pydantic_custom_init__: Whether the model has a custom `__init__`
            function.
        __pydantic_decorators__: Metadata containing the decorators defined on
            the model.
        __pydantic_generic_metadata__: Metadata for generic models, it contains
            data used for a similar purpose to `__args__`, `__origin__`, and
            `__parameters__` in typing-module generics. May eventually be
            replaced by these.
        __pydantic_parent_namespace__: Parent namespace of the model, used for
            automatic rebuilding of models.
        __pydantic_post_init__: The name of the post-init method for the model,
            if defined.
        __pydantic_discriminated_model__: Whether the model is an
            implementation of the `DiscriminatedModel` class.
        __pydantic_root_model__: Whether the model is an implementation
            of the `RootModel` class.
        __pydantic_adapter__: The pydantic `TypeAdapterList` used to validate
            and serialize collections of instances of the model.
        __pydantic_serializer__: The pydantic-core `SchemaSerializer` used to
            dump instances of the model.
        __pydantic_validator__: The pydantic-core `SchemaValidator` used to
            validate instances of the model.
        __pydantic_extra__: An instance attribute with the values of extra
            fields from validation when `resource_config['extra'] == 'allow'`.
        __pydantic_fields_set__: An instance attribute with the names of fields
            explicitly set.
        __pydantic_private__: Instance attribute with the values of private
            attributes set on the model instance.
    """
    if typing.TYPE_CHECKING:
        __config__: ClassVar[ModelConfig | ModelConfigDict]
        __pydantic_owner__: ClassVar[Literal['model', 'resource']]
        __pydantic_resource__: ClassVar['ResourceType | None']
        __pydantic_adapter__: ClassVar[TypeAdapterList['BaseModel']]
        __pydantic_discriminated_model__: ClassVar[bool]
        model_config: ClassVar[ModelConfig]  # type: ignore
        model_computed_fields: ClassVar[  # type: ignore
            dict[str, ComputedFieldInfo]
        ]
        model_fields: ClassVar[dict[str, ModelFieldInfo]]  # type: ignore

        # Instance attributes
        # The non-existent keyword argument "init=False" is used below so that
        # "@dataclass_transform" doesn't pass these attributes as valid
        # keyword arguments to the class initializer.
        __pydantic_validated__: bool = PrivateAttr(default=False)

    # Set model attributes
    __config__ = ModelConfig()
    __pydantic_discriminated_model__ = False
    __pydantic_root_model__ = False
    __pydantic_validated__ = False

    if typing.TYPE_CHECKING:
        def __init_subclass__(
            cls, **kwargs: Unpack[ModelConfigDict]
        ) -> None:
            """Expose to type checkers the model configuration class.

            This signature is included purely to help type-checkers check
            arguments to class declaration, which provides a way to
            conveniently set model configuration key/value pairs.

            Args:
                **kwargs: Model configuration options.

            Examples:
                >>> class MyModel(BaseModel, alias='my-resource'):
                ...     pass
            """

    def __new__(cls, /, **data: Any) -> Self:
        """Create a new model instance.

        It creates a new model instance by parsing and validating input data
        from the `data` keyword arguments.

        Args:
            **data: The input data to initialize the model instance. Note that
                ``cls`` is explicitly positional-only to allow ``cls`` as a
                field name and data keyword argument.
        """
        # Check if class is directly instantiated
        if cls is BaseModel:
            raise TypeError(
                "Plateforme base model cannot be directly instantiated."
            )
        return super().__new__(cls)

    def __init__(self, /, **data: Any) -> None:
        """Initialize a model instance.

        It initializes a model instance by parsing and validating input data
        from the `data` keyword arguments.

        Args:
            **data: The input data to initialize the model instance.

        Raises:
            ValidationError: If the object could not be validated.

        Note:
            The argument ``self`` is explicitly positional-only to allow
            ``self`` as a field name and data keyword argument.
        """
        # Tell pytest to hide this function from tracebacks
        __tracebackhide__ = True

        self.__pydantic_validator__.validate_python(data, self_instance=self)

    @classproperty
    def model_adapter(cls) -> TypeAdapterList['BaseModel']:
        """Get the model type adapter."""
        if not hasattr(cls, '__pydantic_adapter__'):
            raise AttributeError(
                "The model type adapter is not defined. This may be due to "
                "the model not being fully built or an error occurred during "
                "model construction."
            )
        return cls.__pydantic_adapter__

    @classmethod
    def model_construct(  # type: ignore[override, unused-ignore]
        cls: type[Model],
        _fields_set: set[str] | None = None,
        **data: Any,
    ) -> Model:
        """Creates a new instance of the model class with validated data.

        Creates a new model setting `__dict__` and `__pydantic_fields_set__`
        from trusted or pre-validated data. Default values are respected, but
        no other validation is performed. It behaves as if
        `model_config.extra = 'allow'` was set since it adds all passed values.

        Args:
            _fields_set: The set of field names accepted by the model instance.
            **data: Trusted or pre-validated input data to initialize the
                model. It is used to set the `__dict__` attribute of the model.

        Returns:
            A new instance of the model class with validated data.
        """
        model = super().model_construct(_fields_set, **data)

        # Remove default initialization of instrumented resource fields, as
        # they are not needed when constructing a resource instance directly,
        # i.e. defaults are already set and stored in the database.
        if cls.__pydantic_owner__ == 'resource':
            resource = cls.__pydantic_resource__
            for name in getattr(resource, 'resource_attributes'):
                if _fields_set and name in _fields_set:
                    continue
                model.__dict__.pop(name, None)

        return model

    def model_copy(  # type: ignore[override, unused-ignore]
        self: Model,
        *,
        update: dict[str, Any] | None = None,
        deep: bool = False,
    ) -> Model:
        """Returns a copy of the model.

        Args:
            update: Values to add/modify within the new model. Note that if
                assignment validation is not set to ``True``, the integrity of
                the data is not validated when creating the new model. Data
                should be trusted or pre-validated in this case.
            deep: Set to ``True`` to make a deep copy of the model.

        Returns:
            A new copy of the model instance with the updated values.

        Raises:
            ValidationError: If the object could not be validated.
            ValueError: If `strict` or `context` are set when
                `validate_assignment` is set to ``False``.
        """
        copied = self.__deepcopy__() if deep else self.__copy__()
        if update:
            copied.model_update(update, from_attributes=False)
        return copied

    def model_dump(  # type: ignore[override, unused-ignore]
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
        """Generate a dictionary representation of the model.

        It is used to dump the model instance to a dictionary representation of
        the model, optionally specifying which fields to include or exclude.

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
            A dictionary representation of the model.
        """
        if mode != 'raw':
            return self.__pydantic_serializer__.to_python(  # type: ignore
                self,
                mode=mode,
                by_alias=by_alias,
                include=include,  # type: ignore
                exclude=exclude,  # type: ignore
                exclude_unset=exclude_unset,
                exclude_defaults=exclude_defaults,
                exclude_none=exclude_none,
                round_trip=round_trip,
                warnings=warnings,
            )

        # Handle raw mode
        result: dict[str, Any] = {}
        for field_name, field_info in self.model_fields.items():
            if not hasattr(self, field_name):
                continue
            value = getattr(self, field_name)
            # Skip excluded fields
            if include is not None and field_name not in include:
                continue
            if exclude is not None and field_name in exclude:
                continue
            if exclude_unset and field_name not in self.model_fields_set:
                continue
            if exclude_defaults and value == field_info.default:
                continue
            if exclude_none and value is None:
                continue
            # Add field value
            if by_alias and field_info.alias:
                result[field_info.alias] = value
            else:
                result[field_name] = value
        return result

    @classmethod
    def model_json_schema(  # type: ignore[override, unused-ignore]
        cls,
        by_alias: bool = True,
        ref_template: str = DEFAULT_REF_TEMPLATE,
        schema_generator: type[GenerateJsonSchema] = GenerateJsonSchema,
        mode: JsonSchemaMode = 'validation',
        source: JsonSchemaSource = 'model',
    ) -> dict[str, Any]:
        """Generates a JSON schema for a model class.

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
                generation. Defaults to ``model``.

        Returns:
            The generated JSON schema of the model class.

        Note:
            The schema generator class can be overridden to customize the
            logic used to generate the JSON schema. This can be done by
            subclassing the `GenerateJsonSchema` class and passing the subclass
            as the `schema_generator` argument.
        """
        schema_generator_instance = schema_generator(
            by_alias=by_alias, ref_template=ref_template
        )
        if isinstance(cls.__pydantic_validator__, _mock_val_ser.MockValSer):
            cls.__pydantic_validator__.rebuild()
        return schema_generator_instance.generate(
            cls.__pydantic_core_schema__, mode=mode, source=source
        )

    def model_post_init(self, __context: Any) -> None:
        """Post-initialization method for the model class.

        Override this method to perform additional initialization after the
        `__init__` and `model_construct` methods have been called. This is
        useful in scenarios where it is necessary to perform additional
        initialization steps after the model has been fully initialized.

        Args:
            __context: The context object passed to the model instance.
        """
        ...

    @classmethod
    def model_rebuild(  # type: ignore[override, unused-ignore]
        cls,
        *,
        force: bool = False,
        raise_errors: bool = True,
        _parent_namespace_depth: int = 2,
        _types_namespace: dict[str, Any] | None = None,
    ) -> bool | None:
        """Try to rebuild the pydantic-core schema for the model.

        This may be necessary when one of the annotations is a `ForwardRef`
        which could not be resolved during the initial attempt to build the
        schema, and automatic rebuilding fails.

        Args:
            force: Whether to force the rebuilding of the model schema.
                Defaults to ``False``.
            raise_errors: Whether to raise errors or fail silently.
                Defaults to ``True``.
            _parent_namespace_depth: The depth level of the parent namespace.
                Defaults to 2.
            _types_namespace: The types namespace. Defaults to ``None``.

        Raises:
            PlateformeError: If an error occurred while rebuilding the model
                adapter and `raise_errors` is set to ``True``.
            PydanticUndefinedAnnotation: If `PydanticUndefinedAnnotation`
                occurs in`__get_pydantic_core_schema__` and `raise_errors` is
                set to ``True``.

        Returns:
            Returns ``None`` if the schema is already "complete" and rebuilding
            was not required. If rebuilding was required, returns ``True`` if
            rebuilding was successful, otherwise ``False`` if an error
            occurred and `raise_errors` is set to ``False``.
        """
        build_status: bool | None = None

        # Rebuild model
        build_status = super().model_rebuild(
            force=build_status or force,
            raise_errors=raise_errors,
            _parent_namespace_depth=_parent_namespace_depth,
            _types_namespace=_types_namespace,
        )

        # Rebuild model adapter
        if build_status:
            try:
                adapter = TypeAdapterList(cls)
                setattr(cls, '__pydantic_adapter__', adapter)
            except Exception as error:
                if not raise_errors:
                    return False
                raise PlateformeError(
                    f"Failed to rebuild model adapter for {cls.__name__!r}.",
                    code='model-build-failed',
                )

        if build_status is not False:
            cls.model_config.pop('defer_build')

        return build_status

    def model_revalidate(
        self,
        *,
        force: bool = False,
        raise_errors: bool = True,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> bool | None:
        """Revalidate the model instance.

        It revalidates the model instance in place, enforcing the types
        strictly if specified. If the model instance has already been
        validated, it will not be revalidated unless the `force` argument is
        set to ``True``.

        Args:
            force: Whether to force the revalidation of the model instance.
                Defaults to ``False``.
            raise_errors: Whether to raise errors or fail silently.
                Defaults to ``True``.
            strict: Whether to enforce types strictly.
            context: Extra variables to pass to the validator.

        Raises:
            ValidationError: If the model instance could not be validated and
                `raise_errors` is set to ``True``.

        Returns:
            Returns ``None`` if the model instance is already "validated" and
            revalidation was not required. If validation was required, returns
            ``True`` if validation was successful, otherwise ``False`` if an
            error occurred and `raise_errors` is set to ``False``.
        """
        # Tell pytest to hide this function from tracebacks
        __tracebackhide__ = True

        if not force and self.__pydantic_validated__:
            return None
        else:
            try:
                self.__pydantic_validated__ = False
                self.__pydantic_validator__.validate_python(
                    self,
                    strict=strict,
                    from_attributes=True,
                    context=context,
                    self_instance=self,
                )
            except Exception as error:
                if raise_errors:
                    raise error
                return False
            return True

    def model_update(
        self,
        obj: Any,
        *,
        update: dict[str, Any] | None = None,
        from_attributes: bool | None = None,
    ) -> None:
        """Update the model with the given object and update dictionary.

        Args:
            obj: The object to update the model with. It can be a dictionary
                or an object with attributes (if `from_attributes` is set to
                ``True``). If it is a dictionary, the keys must match the model
                field names if extra fields are not allowed.
            update: Values to add/modify within the model. Note that if
                assignment validation is not set to ``True``, the integrity of
                the data is not validated when updating the model. Data should
                be trusted or pre-validated in this case. Defaults to ``None``.
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
            for field_name in self.model_fields:
                if hasattr(obj, field_name):
                    update.setdefault(field_name, getattr(obj, field_name))
        elif isinstance(obj, dict):
            update = {**obj, **update}

        # Process update
        for key, value in update.items():
            if key in self.model_fields:
                self.__dict__[key] = value
            else:
                if self.model_config.extra == 'allow':
                    if self.__pydantic_extra__ is None:
                        self.__pydantic_extra__ = {}
                    self.__pydantic_extra__[key] = value
                elif self.model_config.extra == 'ignore':
                    self.__dict__[key] = value
                else:
                    raise ValueError(
                        f"Extra field {key!r} is not permitted on the "
                        f"model {self.__class__.__qualname__!r}."
                    )

        # Update fields set
        self.__pydantic_fields_set__.update(update.keys())

    @classmethod
    def model_validate(  # type: ignore[override, unused-ignore]
        cls: type[Model],
        obj: Any,
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> Model:
        """Validate the given object against the model.

        Args:
            obj: The object to validate.
            strict: Whether to enforce types strictly.
            from_attributes: Whether to extract data from the object
                attributes.
            context: Extra variables to pass to the validator.

        Returns:
            A validated model instance.

        Raises:
            ValidationError: If the object could not be validated.
        """
        # Tell pytest to hide this function from tracebacks
        __tracebackhide__ = True

        return cls.__pydantic_validator__.validate_python(  # type: ignore
            obj,
            strict=strict,
            from_attributes=from_attributes,
            context=context,
        )

    @classmethod
    def model_validate_many(
        cls: type[Model],
        obj: Any,
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> Sequence[Model]:
        """Validate the given object collection against the model.

        Args:
            obj: The object collection to validate.
            strict: Whether to enforce types strictly.
            from_attributes: Whether to extract data from the object
                collection items attributes.
            context: Extra variables to pass to the validator.

        Returns:
            A validated collection of model instances.

        Raises:
            ValidationError: If the object collection could not be validated.
        """
        # Tell pytest to hide this function from tracebacks
        __tracebackhide__ = True

        return cls.model_adapter.validate_python(  # type: ignore
            obj,
            strict=strict,
            from_attributes=from_attributes,
            context=context,
        )

    @classmethod
    def model_validate_json(  # type: ignore[override, unused-ignore]
        cls: type[Model],
        json_data: str | bytes | bytearray,
        *,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> Model:
        """Validate the given JSON data against the model.

        Args:
            json_data: The JSON data to validate.
            strict: Whether to enforce types strictly.
            context: Extra variables to pass to the validator.

        Returns:
            A validated model instance.

        Raises:
            ValueError: If `json_data` is not a JSON string.
            ValidationError: If the object could not be validated.
        """
        # Tell pytest to hide this function from tracebacks
        __tracebackhide__ = True

        return cls.__pydantic_validator__.validate_json(  # type: ignore
            json_data, strict=strict, context=context
        )

    @classmethod
    def model_validate_json_many(
        cls: type[Model],
        json_data: str | bytes | bytearray,
        *,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> Sequence[Model]:
        """Validate the given JSON data collection against the model.

        Args:
            json_data: The JSON data collection to validate.
            strict: Whether to enforce types strictly.
            context: Extra variables to pass to the validator.

        Returns:
            A validated collection of model instances.

        Raises:
            ValueError: If `json_data` is not a JSON string.
            ValidationError: If the object collection could not be validated.
        """
        # Tell pytest to hide this function from tracebacks
        __tracebackhide__ = True

        return cls.model_adapter.validate_json(  # type: ignore
            json_data, strict=strict, context=context
        )

    @classmethod
    def model_validate_strings(  # type: ignore[override, unused-ignore]
        cls: type[Model],
        obj: Any,
        *,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> Model:
        """Validate the given string object against the model.

        Args:
            obj: The string object to validate.
            strict: Whether to enforce types strictly.
            context: Extra variables to pass to the validator.

        Returns:
            A validated model instance.

        Raises:
            ValidationError: If the object could not be validated.
        """
        # Tell pytest to hide this function from tracebacks
        __tracebackhide__ = True

        return cls.__pydantic_validator__.validate_strings(  # type: ignore
            obj, strict=strict, context=context
        )

    @classmethod
    def model_validate_strings_many(
        cls: type[Model],
        obj: Any,
        *,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> Sequence[Model]:
        """Validate the given string object collection against the model.

        Args:
            obj: The string object collection to validate.
            strict: Whether to enforce types strictly.
            context: Extra variables to pass to the validator.

        Returns:
            A validated collection of model instances.

        Raises:
            ValidationError: If the object collection could not be validated.
        """
        # Tell pytest to hide this function from tracebacks
        __tracebackhide__ = True

        return cls.model_adapter.validate_strings(  # type: ignore
            obj, strict=strict, context=context
        )

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        """Initialize subclass hook after Pydantic full initialization.

        Override this method to perform additional initialization after the
        Pydantic full initialization of the subclass. This is for advanced
        use cases and should not normally be needed.
        """
        ...

    @classmethod
    def __get_pydantic_core_schema__(  # type: ignore[override, unused-ignore]
        cls,
        __source: ModelType,
        __handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Hook into generating the model's core schema.

        Args:
            __source: The class that the core schema is being generated for.
                This will generally be the same as the `cls` argument if this
                is a `classmethod`.
            __handler: Call into Pydantic's internal core schema generation.

        Returns:
            A `pydantic-core` core schema.

        Note:
            For resource models, the default recursion context mode is set to
            ``'omit'``. It can be overridden with either the ``'lax'`` mode,
            or ``'raise'``to throw an error when a recursion is detected.
        """
        # Fetch underlying models
        if cls.__pydantic_discriminated_model__:
            assert issubclass(cls, DiscriminatedModel)
            models = cls.get_root_members()
        else:
            models = (cls,)

        # Build underlying models fields
        for model in models:
            if model.__pydantic_complete__:
                continue
            for field in model.model_fields.values():
                if not hasattr(field, 'build'):
                    continue
                field.build(force=True)

        # Generate core schema
        schema = __handler(__source)

        # Helper factory to wrap field schema for recursion
        def wrap_field_schema(
            field_name: str,
            field_schema: CoreSchema
        ) -> CoreSchema:
            field = cls.model_fields[field_name]

            # Handle guard
            field_guard = field.recursive_guard

            # Handle default and deferrable
            field_default: Callable[[], Any]
            field_validate_default = field.validate_default
            field_deferrable = field.is_identifying()
            field_required = field.is_required()

            if field_required:
                field_default = lambda: None
            elif field.default_factory is None:
                field_default = lambda: field.default
            else:
                field_default = field.default_factory

            def validate_field(
                value: Any,
                handler: ValidatorFunctionWrapHandler,
                info: ValidationInfo,
            ) -> Any:
                context = info.context or {}
                # Do not re-enter recursion when validating deferrables
                if value is Deferred:
                    if not context.get('strict'):
                        return Deferred
                    raise ValueError(f"Forbidden deferral for {field_name!r}.")
                # Do not re-enter recursion when validating defaults
                if value is field_default:
                    return handler(value)
                # Handle recursion
                with recursion_manager(field_guard, on_missing='create'):
                    return handler(value)

            def serialize_field(
                _: Any,
                value: Any,
                handler: SerializerFunctionWrapHandler,
                info: SerializationInfo,
            ) -> Any:
                # Handle recursion
                try:
                    with recursion_manager(field_guard, on_missing='create'):
                        if value is Deferred:
                            if info.mode == 'python':
                                return Deferred
                            return str(value)
                        return handler(value)
                except PydanticOmit:
                    return '\0'

            def default_factory() -> Any:
                with recursion_manager(on_missing='create') as guard:
                    if field_guard in guard.state:
                        return Deferred
                if not field_required:
                    return field_default()
                if field_deferrable:
                    return Deferred
                raise ValueError(f"A value is required for {field_name!r}.")

            return core_schema.with_default_schema(
                core_schema.with_info_wrap_validator_function(
                    validate_field,
                    field_schema,
                    field_name=field_name,
                    serialization=
                        core_schema.wrap_serializer_function_ser_schema(
                            serialize_field,
                            is_field_serializer=True,
                            info_arg=True,
                        ),
                ),
                default_factory=default_factory,
                validate_default=field_validate_default,
            )

        # Wrap field schema for resource models
        if getattr(cls, '__pydantic_resource__', None):
            for key, value in schema['schema'].get('fields', {}).items():
                value['schema'] = wrap_field_schema(key, value['schema'])

        # Helper function to set validation context and flag
        def validate(
            value: Any,
            handler: ValidatorFunctionWrapHandler,
            info: ValidationInfo,
        ) -> Any:
            # Validate with context
            context = info.context or {}
            if VALIDATION_CONTEXT.get() == ValidationMode.STRICT:
                obj = handler(value)
            else:
                mode = 'strict' if context.get('strict') else 'default'
                with validation_manager(mode=mode):  # type: ignore
                    obj = handler(value)
            # Set validated flag
            if isinstance(obj, cls):
                setattr(obj, '__pydantic_validated__', True)
            return obj

        def serialize(
            value: Any,
            handler: SerializerFunctionWrapHandler,
            info: SerializationInfo,
        ) -> Any:
            obj = handler(value)
            if info.mode == 'json' and isinstance(obj, dict):
                obj = {k: v for k, v in obj.items() if v != '\0'}
            return obj

        return core_schema.with_info_wrap_validator_function(
            validate,
            schema,
            serialization=core_schema.wrap_serializer_function_ser_schema(
                serialize,
                info_arg=True,
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        __core_schema: CoreSchema,
        __handler: GetJsonSchemaHandler,
    ) -> JsonSchemaDict:
        """Hook into generating the model's JSON schema.

        Args:
            __core_schema: A ``pydantic-core`` core schema. You can ignore this
                argument and call the handler with a new core schema, wrap this
                core schema ``{'type': 'nullable', 'schema': current_schema}``,
                or just call the handler with the original schema.
            __handler: Call into Pydantic's internal JSON schema generation.
                This will raise a `PydanticInvalidForJsonSchema` if JSON schema
                generation fails. Since this gets called by
                `BaseModel.model_json_schema` you can override the
                `schema_generator` argument to that function to change JSON
                schema generation globally for a type.

        Returns:
            A JSON schema (as a python dictionary).
        """
        return __handler(__core_schema)

    # Hide attributes getter from type checkers to prevent MyPy from allowing
    # arbitrary attribute access instead of raising an error if the attribute
    # is not defined in the resource instance.
    if not typing.TYPE_CHECKING:
        def __getattribute__(self, name: str) -> Any:
            # Handle deferred value if accessed in strict mode
            value = object.__getattribute__(self, name)
            if value is Deferred \
                    and VALIDATION_CONTEXT.get() == ValidationMode.STRICT:
                raise MissingDeferred(
                    f"Attribute {name!r} is deferred and not available on "
                    f"the model instance {self!r}."
                )
            return value

    def __setattr__(self, name: str, value: Any) -> None:
        # Check for forbidden and protected attributes
        if match_any_pattern(name, *FORBIDDEN_ATTRS, *PROTECTED_ATTRS):
            raise AttributeError(
                f"Attribute {name!r} cannot be set on model instance "
                f"{self.__class__.__name__!r} as it is either forbidden or "
                f"protected, and reserved for internal use."
            )
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        # Check for forbidden and protected attributes
        if match_any_pattern(name, *FORBIDDEN_ATTRS, *PROTECTED_ATTRS):
            raise AttributeError(
                f"Attribute {name!r} cannot be deleted on model instance "
                f"{self.__class__.__name__!r} as it is either forbidden or "
                f"protected, and reserved for internal use."
            )
        super().__delattr__(name)

    def __repr_args__(self) -> ReprArgs:
        for name in self.model_fields:
            if name == 'type_':
                continue
            if name not in self.__dict__:
                continue
            yield name, getattr(self, name)

    # Add representation logic without inheritance to avoid side effects
    __repr_name__ = Representation.__repr_name__
    __repr_str__ = Representation.__repr_str__  # type: ignore
    __str__ = Representation.__str__  # type: ignore[override, unused-ignore]
    __repr__ = Representation.__repr__  # type: ignore[override, unused-ignore]
    __pretty__ = Representation.__pretty__
    __rich_repr__ = Representation.__rich_repr__

# Set the "__pydantic_base_init__" attribute of the "__init__" method of the
# "BaseModel" class to "True" to make Pydantic behave as if the method has not
# been overridden. This is necessary to avoid issues with Pydantic's internal
# initialization process.
setattr(BaseModel.__init__, '__pydantic_base_init__', True)


@typing.overload
def create_model(
    __model_name: str,
    *,
    __config__: ModelConfig | None = None,
    __doc__: str | None = None,
    __base__: None = None,
    __module__: str = __name__,
    __validators__: dict[str, ClassMethodType] | None = None,
    __cls_kwargs__: dict[str, Any] | None = None,
    **field_definitions: FieldDefinition,
) -> ModelType:
    ...

@typing.overload
def create_model(
    __model_name: str,
    *,
    __config__: ModelConfig | None = None,
    __doc__: str | None = None,
    __base__: type[Model] | tuple[type[Model], ...],
    __module__: str = __name__,
    __validators__: dict[str, ClassMethodType] | None = None,
    __cls_kwargs__: dict[str, Any] | None = None,
    **field_definitions: FieldDefinition,
) -> type[Model]:
    ...

def create_model(
    __model_name: str,
    *,
    __config__: ModelConfig | None = None,
    __doc__: str | None = None,
    __base__: type[Model] | tuple[type[Model], ...] | None = None,
    __module__: str | None = None,
    __validators__: dict[str, ClassMethodType] | None = None,
    __cls_kwargs__: dict[str, Any] | None = None,
    **field_definitions: FieldDefinition,
) -> type[Model]:
    """Dynamically creates and returns a new model class.

    It is used to dynamically create a subclass of the `BaseModel` class.

    Args:
        __model_name: The name of the newly created model.
        __config__: The configuration of the new model.
        __doc__: The docstring of the new model.
        __base__: The base class or classes for the new model.
        __module__: The name of the module that the model belongs to.
            If ``None``, the value is retrieved from ``sys._getframe(1)``.
        __validators__: A dictionary of class methods that validate fields.
        __cls_kwargs__: A dictionary of keyword arguments for class creation,
            such as ``metaclass``.
        **field_definitions: Attributes of the new model. They should be passed
            in the format: ``<name>=(<type>, <default value>)`` or
            ``<name>=(<type>, <FieldInfo>)``.

    Returns:
        The new `BaseModel` class.

    Raises:
        ValueError: If `__base__` and `__config__` are both passed.
    """
    # Create factory model class and update configuration
    if __base__ is None:
        model_config = __config__ or ModelConfig()
        class FactoryModel(BaseModel):
            __config__ = model_config
        __config__ = None
        __base__ = typing.cast(type[Model], FactoryModel)

    # Validate configuration
    elif __config__ is not None:
        raise ValueError(
            "The `__config__` and `__base__` arguments cannot be used "
            "together when creating a model."
        )

    # Validate model name
    model_qualname = __model_name
    model_name = __model_name.split('.')[-1]

    # Create model using Pydantic factory with updated configuration
    model = _create_model(  # type: ignore
        model_name,
        __config__=__config__,
        __doc__=__doc__,
        __base__=__base__,
        __module__=__module__,  # type: ignore[arg-type]
        __validators__=__validators__,
        __cls_kwargs__=__cls_kwargs__,
        __slots__=None,
        **field_definitions,
    )

    setattr(model, '__qualname__', model_qualname)

    return model


# MARK: Root Model Metaclass

if typing.TYPE_CHECKING:
    # Dataclass transformation could be applied to the root model directly, but
    # `ModelMeta`'s dataclass transformation takes priority. Here, only the
    # type checkers will interpret the transformation as applied to the root
    # model directly.
    @typing.dataclass_transform(
        kw_only_default=False,
        field_specifiers=(Field, PrivateAttr)
    )
    class RootModelMeta(ModelMeta):
        """A metaclass for root model classes."""
        ...

else:
    RootModelMeta = ModelMeta


# MARK: Root Model

if typing.TYPE_CHECKING:
    _TRoot = TypeVar('_TRoot', default=Any)
else:
    _TRoot = TypeVar('_TRoot')

class RootModel(BaseModel, Generic[_TRoot], metaclass=RootModelMeta):
    """A root model class.

    A model used to store a single root object.

    a specialized model class used to define and validate a single root object.
    It's particularly useful for scenarios involving a top-level data structure
    that doesn't fit neatly into a typical dictionary or list format. The roo
    model ensures type safety and data validation for this singular, primary
    object, and allows dynamic type updates without losing references within
    other models.

    Attributes:
        root: The root object of the model.
    """
    if typing.TYPE_CHECKING:
        model_config: ClassVar[ModelConfig]
        model_computed_fields: ClassVar[dict[str, ComputedFieldInfo]]
        model_fields: ClassVar[dict[str, ModelFieldInfo]]

    __pydantic_root_model__ = True
    __pydantic_private__ = None
    __pydantic_extra__ = None

    root: _TRoot

    if typing.TYPE_CHECKING:
        def __init_subclass__(
            cls, **kwargs: Unpack[ModelConfigDict]
        ) -> None:
            """Expose to type checkers the model configuration class.

            This signature is included purely to help type-checkers check
            arguments to class declaration, which provides a way to
            conveniently set root model configuration key/value pairs.

            Args:
                **kwargs: Model configuration options.

            Note:
                The `extra` configuration option is not supported for root
                models. If the `extra` configuration option is set, a
                `PlateformeError` is raised.

            Examples:
                >>> class MyModel(RootModel, alias='my-resource'):
                ...     pass
            """

    else:
        def __init_subclass__(cls, **kwargs: Any) -> None:
            extra = cls.model_config.get('extra')
            if extra is not None:
                raise PlateformeError(
                    f"A root model does not support setting the 'extra' "
                    f"configuration option. Got: {extra!r}",
                    code='model-invalid-config'
                )
            super().__init_subclass__(**kwargs)

    def __init__(self, /, root: _TRoot = Undefined, **data: Any) -> None:
        """Initialize a root model instance.

        It initializes a model instance by parsing and validating input data
        from the `root` argument or `data` keyword arguments.

        Args:
            root: The root object of the model.
            **data: The input data to initialize the model instance.

        Raises:
            ValidationError: If the object could not be validated.

        Note:
            The argument ``self`` is explicitly positional-only to allow
            ``self`` as a field name and data keyword argument.
        """
        # Tell pytest to hide this function from tracebacks
        __tracebackhide__ = True

        if data:
            if root is not Undefined:
                raise ValueError(
                    f"Root model `__init__` accepts either a single "
                    f"positional argument or arbitrary keyword arguments. "
                    f"Got both: root={root!r}, data={data!r}"
                )
            root = data  # type: ignore

        self.__pydantic_validator__.validate_python(root, self_instance=self)

    @classmethod
    def model_construct(  # type: ignore[override, unused-ignore]
        cls, root: _TRoot, _fields_set: set[str] | None = None
    ) -> Self:
        """Create a new model using the provided root object and update fields
        set with the given set of fields.

        Args:
            root: The root object of the model.
            _fields_set: The set of fields to be updated.

        Returns:
            The new model.

        Raises:
            NotImplemented: If the model is not a subclass of `RootModel`.
        """
        return super().model_construct(_fields_set, root=root)

    if typing.TYPE_CHECKING:
        def model_dump(  # type: ignore
            self,
            *,
            mode: Literal['json', 'python', 'raw'] | str = 'python',
            include: Any | None = None,
            exclude: Any | None = None,
            by_alias: bool = False,
            exclude_unset: bool = False,
            exclude_defaults: bool = False,
            exclude_none: bool = False,
            round_trip: bool = False,
            warnings: bool = True,
        ) -> Any:
            """This method is included just to get a more accurate return type
            for type checkers. It is included in this `if TYPE_CHECKING:` block
            since no override is actually necessary.

            See the documentation of base model `model_dump` for more details
            about the arguments.

            Generally, this method will have a return type of `_TRoot`,
            assuming that `_TRoot` is not a `BaseModel` subclass. If `_TRoot`
            is a `BaseModel` subclass, then the return type will likely be
            `dict[str, Any]`, as `model_dump` calls are recursive. The return
            type could even be something different, in the case of a custom
            serializer. Thus, `Any` is used here to catch all of these cases.
            """
            ...

    def __getstate__(self) -> dict[Any, Any]:
        return {
            '__dict__': self.__dict__,
            '__pydantic_fields_set__': self.__pydantic_fields_set__,
        }

    def __setstate__(self, state: dict[Any, Any]) -> None:
        object.__setattr__(
            self, '__pydantic_fields_set__', state['__pydantic_fields_set__']
        )
        object.__setattr__(self, '__dict__', state['__dict__'])

    def __copy__(self) -> Self:
        """Returns a shallow copy of the model."""
        cls = type(self)
        model = cls.__new__(cls)

        model_dict = copy(self.__dict__)
        object.__setattr__(model, '__dict__', model_dict)

        model_fields_set = copy(self.__pydantic_fields_set__)
        object.__setattr__(model, '__pydantic_fields_set__', model_fields_set)

        return model

    def __deepcopy__(self, memo: dict[int, Any] | None = None) -> Self:
        """Returns a deep copy of the model."""
        cls = type(self)
        model = cls.__new__(cls)

        model_dict = deepcopy(self.__dict__, memo=memo)
        object.__setattr__(model, '__dict__', model_dict)

        # The next line doesn't need deepcopy because "__pydantic_fields_set__"
        # is a set[str], and attempting a deepcopy would be marginally slower.
        model_fields_set = copy(self.__pydantic_fields_set__)
        object.__setattr__(model, '__pydantic_fields_set__', model_fields_set)

        return model

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, RootModel):
            return NotImplemented
        return self.model_fields['root'].annotation \
            == other.model_fields['root'].annotation and super().__eq__(other)

    def __repr_args__(self) -> ReprArgs:
        if self.model_fields['root'].repr:
            yield 'root', self.root

# Set the "__pydantic_base_init__" attribute of the "__init__" method of the
# "RootModel" class to "True" to make Pydantic behave as if the method has not
# been overridden. This is necessary to avoid issues with Pydantic's internal
# initialization process.
setattr(RootModel.__init__, '__pydantic_base_init__', True)


def create_root_model(
    __model_name: str,
    *,
    __config__: ModelConfig | None = None,
    __doc__: str | None = None,
    __module__: str | None = None,
    __validators__: dict[str, ClassMethodType] | None = None,
    __cls_kwargs__: dict[str, Any] | None = None,
    root: tuple[type[_TRoot], Any | ModelFieldInfo]
) -> type[RootModel[_TRoot]]:
    """Dynamically creates and returns a new model class.

    It is used to dynamically create a subclass of the `BaseModel` class.

    Args:
        __model_name: The name of the newly created model.
        __config__: The configuration of the new model.
        __doc__: The docstring of the new model.
        __module__: The name of the module that the model belongs to.
            If ``None``, the value is retrieved from ``sys._getframe(1)``.
        __validators__: A dictionary of class methods that validate fields.
        __cls_kwargs__: A dictionary of keyword arguments for class creation,
            such as ``metaclass``.
        root: Root attributes of the new model. It should be passed in
            the format: ``<name>=(<type>, <default value>)`` or
            ``<name>=(<type>, <FieldInfo>)``.

    Returns:
        The new `RootModel` class.

    Raises:
        ValueError: If `__base__` and `__config__` are both passed.
    """
    # Create the factory model class and update configuration
    model_config = __config__ or ModelConfig()
    class FactoryModel(RootModel[_TRoot]):
        __config__ = model_config
    __base__ = typing.cast(type[RootModel[_TRoot]], FactoryModel)

    # Create model using Pydantic factory with updated configuration
    return _create_model(
        __model_name,
        __doc__=__doc__,
        __base__=__base__,
        __module__=__module__,  # type: ignore[arg-type]
        __validators__=__validators__,
        __cls_kwargs__=__cls_kwargs__,
        __slots__=None,
        root=root,
    )


# MARK: Discriminated Model Metaclass

if typing.TYPE_CHECKING:
    # Dataclass transformation could be applied to the discriminated model
    # directly, but `RootModelMeta`'s dataclass transformation takes priority.
    # Here, only the type checkers will interpret the transformation as applied
    # to the discriminated model directly.
    @typing.dataclass_transform(
        kw_only_default=False,
        field_specifiers=(Field, PrivateAttr)
    )
    class DiscriminatedModelMeta(RootModelMeta):
        """A metaclass for discriminated model classes."""
        __registrant__: int | None

        def collect_typevar_values(
            cls, bases: tuple[type, ...], namespace: dict[str, Any], /,
        ) -> tuple[type[Any], ...] | None:
            """Collect the root typevar values.

            It collects the typevar values of the root type annotation from the
            given objects. It looks for the discriminated model class, and if
            found and implemented, extracts and returns the generic metadata.

            Args:
                bases: The class bases.
                namespace: The class namespace.

            Returns:
                The root typevar values.
            """
            ...

        def get_root_members(cls) -> tuple[ModelType, ...]:
            """Get the base and variant classes of the discriminated model."""
            ...

        def get_root_base(cls) -> ModelType:
            """Get the base class of the discriminated model."""
            ...

        def get_root_variants(cls) -> tuple[ModelType, ...]:
            """Get the variant classes of the discriminated model."""
            ...

        def update_root_members(
            cls,
            *,
            base: type[Any] | None = None,
            variants: Sequence[type[Any]] | None = None,
        ) -> tuple[ModelType, ...]:
            """Update the discriminator with the given models.

            Provided variant models must be subclasses of the base model. This
            method updates the root field union annotation with the base and
            variant models, and finally rebuilds the model.

            Args:
                base: The base model to update the discriminated model with.
                    Defaults the root base model if not provided.
                variants: The variant models to update the discriminated model
                    with. Defaults to ``None``.

            Returns:
                The updated base and variant models.

            Raises:
                TypeError: If the variants are not subclasses of the root base
                    model or the root base model is provided as a variant.
            """
            ...

        def update_root_metadata(cls, *metadata: Any) ->  tuple[Any, ...]:
            """Update root type metadata.

            The provided metadata should be similar to the one used in the
            `Annotated` type. Any string value is considered a discriminator.

            Args:
                *metadata: The metadata to update the root type with.

            Returns:
                The updated metadata.
            """
            ...

        def validate_root(cls, annotation: Any) -> ModelType:
            """Validate the root type annotation of the discriminated model.

            It ensures that the root type annotation is either a base model or
            a tuple of base model where the first element is the base model and
            the rest are its subclasses.

            Args:
                annotation: The root type annotation to validate.

            Returns:
                The validated root type annotation.
            """
            ...

else:
    class DiscriminatedModelMeta(RootModelMeta):
        """A metaclass for discriminated model classes."""
        if typing.TYPE_CHECKING:
            model_fields: dict[str, ModelFieldInfo]
            model_rebuild: Callable[..., None]

        __registrant__ = None

        def __new__(
            mcls,
            name: str,
            bases: tuple[type, ...],
            namespace: dict[str, Any],
            /,
            *args: Any,
            discriminator: str | Discriminator | None = None,
            **kwargs: Any,
        ) -> type:
            """Create a new discriminated model meta class."""
            cls = super().__new__(
                mcls, name, bases, namespace, *args, **kwargs
            )

            model_fields: dict[str, ModelFieldInfo] = \
                getattr(cls, 'model_fields')

            # Set the root type discriminator
            if discriminator is not None:
                annotation = model_fields['root'].annotation
                annotation_metadata = Field(..., discriminator=discriminator)
                model_fields['root'] = FieldInfo.from_annotation(
                    Annotated[annotation, annotation_metadata]  # type: ignore
                )

            return cls

        def __init__(
            cls,
            name: str,
            bases: tuple[type, ...],
            namespace: dict[str, Any],
            /,
            *args: Any,
            **kwargs: Any,
        ) -> None:
            """Initialize a new discriminated model meta class."""
            super().__init__(
                name, bases, namespace, *args, **kwargs  # type: ignore
            )

            # Skip remaining initialization for the base class
            if isbaseclass_lenient(cls, 'DiscriminatedModel'):
                return

            # Collect the typevar values from the original bases found within
            # the class namespace and the provided bases.
            typevar_values = cls.collect_typevar_values(bases, namespace)

            # Retrieve discriminated model root type annotation
            if typevar_values is None:
                annotation = cls.model_fields['root'].annotation
            else:
                annotation = Union[typevar_values] \
                    if len(typevar_values) > 1 \
                    else typevar_values[0]  # type: ignore

            # Skip attribute initialization if generics still exist
            if isinstance(annotation, TypeVar):
                return

            # Set discriminated model root type annotation
            cls.model_fields['root'].annotation = cls.validate_root(annotation)

        def collect_typevar_values(
            cls, bases: tuple[type, ...], namespace: dict[str, Any], /,
        ) -> tuple[type[Any], ...] | None:
            """Collect the root typevar values."""
            generic_attr = '__pydantic_generic_metadata__'

            meta_bases = get_meta_orig_bases(bases, namespace)
            for meta_base in meta_bases:
                generic = getattr(meta_base, generic_attr, {})
                origin = generic.get('origin', meta_base)
                if origin is None:
                    continue
                if not isbaseclass_lenient(origin, 'DiscriminatedModel'):
                    continue
                args = generic.get('args', ())
                if any(isinstance(arg, TypeVar) for arg in args):
                    break
                return args  # type: ignore

            return None

        def get_root_members(cls) -> tuple[ModelType, ...]:
            """Get the base and variant classes of the discriminated model."""
            annotation = cls.model_fields['root'].annotation
            members = typing.get_args(annotation) or (annotation,)
            return tuple([
                member for member in members
                if isinstance(member, type) and issubclass(member, BaseModel)
            ])

        def get_root_base(cls) -> ModelType:
            """Get the base class of the discriminated model."""
            members = cls.get_root_members()
            if len(members) == 0:
                raise TypeError(
                    f"Root base model not found for the `DiscriminatedModel` "
                    f"class. Got: {members}."
                )
            return members[0]

        def get_root_variants(cls) -> tuple[ModelType, ...]:
            """Get the variant classes of the discriminated model."""
            members = cls.get_root_members()
            if len(members) == 0:
                raise TypeError(
                    f"Root base model not found for the `DiscriminatedModel` "
                    f"class. Got: {members}."
                )
            return members[1:]

        def update_root_members(
            cls,
            *,
            base: type[Any] | None = None,
            variants: Sequence[type[Any]] | None = None,
        ) -> tuple[ModelType, ...]:
            """Update the discriminator with the given models."""
            if base is None:
                base = cls.get_root_base()  # type: ignore
                assert base is not None
            if variants is None:
                variants = ()

            if not all(issubclass(variant, base) for variant in variants):
                raise TypeError(
                    f"Model variants must be subclasses of the root base "
                    f"model. Got: {variants}."
                )
            if any(variant is base for variant in variants):
                raise TypeError(
                    f"Cannot provide the root base model as a variant. "
                    f"Got: {variants}."
                )

            models = (base, *variants)
            cls.model_fields['root'].annotation = Union[models]  # type: ignore

            return models

        def update_root_metadata(cls, *metadata: Any) -> tuple[Any, ...]:
            """Update root type metadata."""
            annotation = cls.model_fields['root'].annotation
            annotation_metadata = tuple(
                Field(..., discriminator=meta)
                for meta in metadata
                if isinstance(meta, (str, Discriminator)) or meta
            )
            cls.model_fields['root'] = FieldInfo.from_field_info(
                cls.model_fields['root'],
                annotation=Annotated[
                    annotation, *annotation_metadata  # type: ignore
                ],
            )

            return annotation_metadata

        def validate_root(cls, annotation: Any) -> ModelType:
            """Validate the root type annotation of the discriminated model."""
            # Parse the root type annotation
            origin = typing.get_origin(annotation)
            if origin in (Union, UnionType):
                args = typing.get_args(annotation)
            else:
                args = (annotation,)

            # Validate the root type annotation
            if not is_model(args[0]) and not is_resource(args[0]):
                raise TypeError(
                    f"The root base type for the `DiscriminatedModel` class "
                    f"must be a subclass of the `BaseModel` or `BaseResource` "
                    f"class. Got: {args[0]}."
                )
            if not all(issubclass(arg, args[0]) for arg in args[1:]):
                raise TypeError(
                    f"The root variant types for the `DiscriminatedModel` "
                    f"class must be subclasses of the root base type. "
                    f"Got: {args[1:]}."
                )

            return annotation  # type: ignore


# MARK: Discriminated Model

if typing.TYPE_CHECKING:
    _TBase = TypeVar('_TBase', default=Any)
    _TSubs = TypeVarTuple('_TSubs', default=Unpack[Any])
else:
    _TBase = TypeVar('_TBase')
    _TSubs = TypeVarTuple('_TSubs')

class DiscriminatedModel(
    RootModel[_TBase],
    Generic[_TBase, *_TSubs],
    metaclass=DiscriminatedModelMeta
):
    """A discriminated model class."""
    if typing.TYPE_CHECKING:
        model_config: ClassVar[ModelConfig]
        model_computed_fields: ClassVar[dict[str, ComputedFieldInfo]]
        model_fields: ClassVar[dict[str, ModelFieldInfo]]
        root: Union[tuple[_TBase, *_TSubs]]  # type: ignore

    __pydantic_discriminated_model__ = True

    if typing.TYPE_CHECKING:
        def __init_subclass__(
            cls,
            *,
            discriminator: str | Discriminator | None = None,
            **kwargs: Unpack[ModelConfigDict],
        ) -> None:
            """Expose to type checkers the model configuration class.

            This signature is included purely to help type-checkers check
            arguments to class declaration, which provides a way to
            conveniently set discriminated model configuration key/value pairs.

            Args:
                discriminator: The discriminator of the union root type use for
                    the validation, provided either as a string or a
                    discriminator object.
                **kwargs: Model configuration options.

            Examples:
                >>> class MyModel(DiscriminatedModel, alias='my-resource)
                ...     pass
            """

    else:
        def __init_subclass__(
            cls,
            *,
            discriminator: str | Discriminator | None = None,
            **kwargs: Unpack[ModelConfigDict],
        ) -> None:
            return super().__init_subclass__(**kwargs)

    def __class_getitem__(
        cls, typevar_values: type[Any] | tuple[type[Any], ...]
    ) -> ModelType | PydanticRecursiveRef:
        """Get the class item with the given type parameter values.

        It processes the type parameter values to update the discriminated
        model metadata with and calls the parent class method to get the
        class item with the updated type parameter values as a tuple of
        the root base model and its subclasses.

        Args:
            typevar_values: The generic type parameter values to process.

        Returns:
            The class item with the given type parameter values.
        """
        values: type[Any] | tuple[type[Any], ...]

        # Update the metadata with the provided type parameter values
        if is_annotated(typevar_values):
            values, *metadata = typing.get_args(typevar_values)
            if metadata:
                cls.update_root_metadata(*metadata)
        else:
            values = typevar_values

        # Parse the type parameter values and call the parent class method
        # to get the class item with the updated type parameter values.
        origin = typing.get_origin(values)
        if origin in (Union, UnionType):
            values = typing.get_args(values)
        if isinstance(values, tuple):
            model_typevar_values = (values[0], values[1:])
        else:
            model_typevar_values = (values, ())
        return super().__class_getitem__(model_typevar_values)  # type: ignore

    @classmethod
    def __get_pydantic_core_schema__(  # type: ignore[override, unused-ignore]
        cls,
        __source: DiscriminatedModelType,
        __handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Hook into generating the discriminated model's core schema.

        Args:
            __source: The class that the core schema is being generated for.
                This will generally be the same as the `cls` argument if this
                is a `classmethod`.
            __handler: Call into Pydantic's internal core schema generation.

        Returns:
            A `pydantic-core` core schema.
        """
        validation_schema = __handler(__source)
        serialization_schema = __handler.generate_schema(
            Annotated[
                cls.model_fields['root'].annotation,
                cls.model_fields['root'],
            ]
        )

        def serialize(
            obj: Any, handler: SerializerFunctionWrapHandler,
        ) -> Any:
            if isinstance(obj, DiscriminatedModel):
                obj = obj.root
            return handler(obj)

        schema = core_schema.no_info_after_validator_function(
            lambda obj: getattr(obj, 'root'),
            validation_schema,
            serialization=core_schema.wrap_serializer_function_ser_schema(
                serialize,
                is_field_serializer=False,
                info_arg=False,
                schema=serialization_schema,
            ),
        )

        return schema

# Set the "__pydantic_base_init__" attribute of the "__init__" method of the
# "DiscriminatedModel" class to "True" to make Pydantic behave as if the method
# has not been overridden. This is necessary to avoid issues with Pydantic's
# internal initialization process.
setattr(DiscriminatedModel.__init__, '__pydantic_base_init__', True)


@typing.overload
def create_discriminated_model(
    __model_name: str,
    *,
    __owner__: object | int | None = None,
    __config__: ModelConfig | None = None,
    __doc__: str | None = None,
    __module__: str | None = None,
    __validators__: dict[str, ClassMethodType] | None = None,
    __cls_kwargs__: dict[str, Any] | None = None,
    discriminator: str | Discriminator | None = None,
    root: tuple[type[_TBase], Any | ModelFieldInfo]
) -> type[DiscriminatedModel[_TBase]]:
    ...

@typing.overload
def create_discriminated_model(
    __model_name: str,
    *,
    __owner__: object | int | None = None,
    __config__: ModelConfig | None = None,
    __doc__: str | None = None,
    __module__: str | None = None,
    __validators__: dict[str, ClassMethodType] | None = None,
    __cls_kwargs__: dict[str, Any] | None = None,
    discriminator: str | Discriminator | None = None,
    root: tuple[tuple[type[_TBase], ...], Any | ModelFieldInfo]
) -> type[DiscriminatedModel[*tuple[_TBase, ...]]]:
    ...

def create_discriminated_model(
    __model_name: str,
    *,
    __owner__: object | int | None = None,
    __config__: ModelConfig | None = None,
    __doc__: str | None = None,
    __module__: str | None = None,
    __validators__: dict[str, ClassMethodType] | None = None,
    __cls_kwargs__: dict[str, Any] | None = None,
    discriminator: str | Discriminator | None = None,
    root: tuple[type[_TBase] | tuple[type[_TBase], ...], Any | ModelFieldInfo]
) -> type[DiscriminatedModel[*tuple[_TBase, ...]]]:
    """Dynamically creates and returns a new model class.

    It is used to dynamically create a subclass of the `BaseModel` class.

    Args:
        __model_name: The name of the newly created model.
        __owner__: The owner object or identifier to use as the registrant of
            the new model. If an object is provided, the object's identifier
            is used. If an integer is provided, the integer is used.
            Defaults to ``None``.
        __config__: The configuration of the new model.
        __doc__: The docstring of the new model.
        __module__: The name of the module that the model belongs to.
            If ``None``, the value is retrieved from ``sys._getframe(1)``.
        __validators__: A dictionary of class methods that validate fields.
        __cls_kwargs__: A dictionary of keyword arguments for class creation,
            such as ``metaclass``.
        discriminator: The discriminator either as a string or an object use
            for the validation of the discriminated root type.
        root: Root attributes of the new model. It should be passed in
            the format: ``<name>=(<type>, <default value>)`` or
            ``<name>=(<type>, <FieldInfo>)``.

    Returns:
        The new `DiscriminatedModel` class.

    Raises:
        ValueError: If `__base__` and `__config__` are both passed.
    """
    # Create the factory model class and update configuration
    model_config = __config__ or ModelConfig()
    class FactoryModel(
        DiscriminatedModel[*tuple[_TBase, ...]],
        discriminator=discriminator,
    ):
        __config__ = model_config
        __registrant__ = (
            id(__owner__)
            if __owner__ and not isinstance(__owner__, int)
            else __owner__
        )

    __base__ = typing.cast(
        type[DiscriminatedModel[*tuple[_TBase, ...]]],
        FactoryModel,
    )

    # Create model using Pydantic factory with updated configuration
    return _create_model(
        __model_name,
        __doc__=__doc__,
        __base__=__base__,
        __module__=__module__,  # type: ignore[arg-type]
        __validators__=__validators__,
        __cls_kwargs__=__cls_kwargs__,
        __slots__=None,
        root=root,
    )


# MARK: Utilities

def collect_fields(
    __model: ModelType, **kwargs: Unpack[FieldLookup],
) -> dict[str, FieldDefinition]:
    """Collect the model field definitions from the provided model.

    It collects the model fields based on the provided model and keyword
    arguments lookup configuration to include or exclude specific fields. The
    collected fields annotations are updated with the provided `partial` flag,
    and the field information is updated with the provided `default` and
    `update` values. The field lookup configuration can be overridden to narrow
    down the field lookup configuration to specific fields.

    Args:
        __model: The model class to collect the fields from.
        **kwargs: The field lookup configuration to collect the fields.
            - `computed`: Whether to include computed fields. When set to
                ``True``, field definitions for computed fields are included.
                Defaults to ``None``.
            - `include`: The filters to include specific fields based on the
                field attributes as a dictionary with the field attribute names
                as keys and the predicates to include as values.
                Defaults to ``None``.
            - `exclude`: The filters to exclude specific fields based on the
                field attributes as a dictionary with the field attribute names
                as keys and the predicates to exclude as values.
                Defaults to ``None``.
            - `partial`: Whether to mark the field annotations as optional.
                Defaults to ``None``.
            - `default`: The default to apply and set within the field
                information. Defaults to ``None``.
            - `update`: The update to apply and set within the field
                information. Defaults to ``None``.
            - `override`: The field lookup configuration to override the
                current configuration. This can be used to narrow down the
                field lookup configuration to specific fields. Multiple levels
                of nested configurations can be provided and will be resolved
                recursively. Defaults to ``None``.

    Returns:
        A dictionary of field names with the corresponding field annotations
        and field information.
    """
    field_definitions: dict[str, FieldDefinition] = {}

    if issubclass(__model, DiscriminatedModel):
        __model = __model.get_root_base()

    model_fields: dict[str, ComputedFieldInfo | ModelFieldInfo] = {
        **__model.model_fields,
        **__model.model_computed_fields,
    }

    # Helper function to check if a field should be included or excluded
    def check(
        field: ComputedFieldInfo | ModelFieldInfo,
        key: str,
        predicate: IncExPredicate,
    ) -> bool:
        # Retrieve field target attribute
        attr = field
        key_segments = key.split('.')
        for key_segment in key_segments:
            if not hasattr(attr, key_segment):
                return False
            attr = getattr(attr, key_segment)

        # Retrieve predicate information
        if isinstance(predicate, tuple):
            *check_callable, check_value = predicate
            if len(check_callable) == 2:
                check_args, check_kwargs = check_callable
            else:
                check_callable = check_callable[0]
                if isinstance(check_callable, Sequence):
                    check_args = check_callable
                    check_kwargs = {}
                elif isinstance(check_callable, Mapping):
                    check_args = ()
                    check_kwargs = check_callable
        else:
            check_args = ()
            check_kwargs = {}
            check_value = predicate

        # Check attribute value against the predicate
        if callable(attr):
            attr_value = attr(*check_args, **check_kwargs)
        else:
            attr_value = attr

        return bool(
            check_value in attr_value
            if isinstance(attr_value, (list, set, tuple))
            else check_value == attr_value
        )

    # Recursive function to process field lookup configuration
    def process_fields(lookup: FieldLookup, *field_names: str) -> None:
        computed = lookup.get('computed', None)
        include = lookup.get('include', None)
        exclude = lookup.get('exclude', None)
        partial = lookup.get('partial', None)
        default = lookup.get('default', None)
        update = lookup.get('update', None)
        override = lookup.get('override', None)

        check_names: set[str] = set()

        for field_name in field_names:
            model_field = model_fields[field_name]

            # Skip computed fields if not requested
            if isinstance(model_field, ComputedFieldInfo) and not computed:
                continue

            # Skip fields if not matching include or exclude filters
            if include is not None and not all(
                check(model_field, k, v) for k, v in include.items()
            ):
                continue
            if exclude is not None and any(
                check(model_field, k, v) for k, v in exclude.items()
            ):
                continue

            # Retrieve field definition
            if field_name not in field_definitions:
                annotation, field = model_field._create_field_definition()
            else:
                annotation, field = field_definitions[field_name]

            # Update field definition
            if default:
                field._default(**default)
            if update:
                field._update(**update)
            if partial is True:
                annotation = Optional[annotation]  # type: ignore
                if field.default is Undefined \
                        and field.default_factory is None:
                    field._update(default=None)

            field_definitions[field_name] = (annotation, field)

            check_names.add(field_name)

        # Process nested field lookup configuration
        if check_names and override is not None:
            process_fields(override, *check_names)

    process_fields(kwargs, *model_fields.keys())

    return field_definitions


def collect_models(
    __obj: Any,
    *,
    __config__: ModelConfig | None = None,
    __base__: ModelType | tuple[ModelType, ...] | None = None,
    __module__: str | None = None,
    __validators__: dict[str, ClassMethodType] | None = None,
    __cls_kwargs__: dict[str, Any] | None = None,
    __namespace__: str | None = None,
) -> list[ModelType]:
    """Collect and build recursively all nested models in a given object.

    It recursively collect all nested classes in a given object and build the
    associated models. The `__namespace__` argument is used recursively to
    determine the root namespace under which the models are collected.

    Args:
        __obj: The object to inspect for nested classes.
        __config__: The configuration of the new models.
        __base__: The base class or classes for the new models.
        __module__: The name of the module that the models belongs to.
            If ``None``, the value is retrieved from ``sys._getframe(1)``.
        __validators__: A dictionary of class methods that validate fields.
        __cls_kwargs__: A dictionary of keyword arguments for class creation,
            such as ``metaclass``.
        __namespace__: The namespace of the object to collect models from.

    Returns:
        A dictionary with the generated `BaseModel` classes.

    Raises:
        ValueError: If `__base__` and `__config__` are both passed.
    """
    # Retrieve object namespace
    obj_namespace = get_object_name(__obj, fullname=True) + '.'

    # Validate root and object namespace
    if __namespace__ is None:
        __namespace__ = obj_namespace
    if not obj_namespace.startswith(__namespace__):
        raise ValueError(
            f"Object namespace {obj_namespace!r} does not belong to the "
            f"specified namespace {__namespace__!r}."
        )

    models: list[ModelType] = []

    for name in dir(__obj):
        # Skip private and dunder attributes
        if name.startswith('_'):
            continue

        attr = getattr(__obj, name, None)

        # Skip non-class objects
        if not inspect.isclass(attr):
            continue

        # Skip non-defined classes
        attr_name = get_object_name(attr, fullname=True)
        if not attr_name.startswith(obj_namespace):
            continue

        # Build model
        model_name = attr_name[len(__namespace__):]
        if issubclass(attr, BaseModel):
            model = attr
        else:
            field_definitions = {}
            for field_name, field_type in attr.__annotations__.items():
                if field_name.startswith('_'):
                    continue
                field_value = ...
                if hasattr(attr, field_name):
                    field_value = getattr(attr, field_name)
                field_definitions[field_name] = (field_type, field_value)

            model = create_model(  # type: ignore
                model_name,
                __config__=__config__,
                __doc__=getattr(attr, '__doc__', None),
                __base__=__base__,  # type: ignore[arg-type]
                __module__=__module__,  # type: ignore[arg-type]
                __validators__=__validators__,
                __cls_kwargs__={
                    **(__cls_kwargs__ or {}),
                    'stub': has_stub_noop(attr),
                },
                **field_definitions,
            )

        # Add model
        models.append(model)

        # Add nested models
        nested_models = collect_models(
            attr,
            __config__=__config__,
            __base__=__base__,
            __module__=__module__,
            __validators__=__validators__,
            __cls_kwargs__=__cls_kwargs__,
            __namespace__=__namespace__,
        )
        models.extend(nested_models)

    return models
