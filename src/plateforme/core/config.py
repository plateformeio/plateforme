# plateforme.core.config
# ----------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing configuration classes within the
Plateforme framework.
"""

import typing
import warnings
from collections.abc import (
    ItemsView,
    Iterable,
    Iterator,
    KeysView,
    Mapping,
    ValuesView,
)
from contextlib import contextmanager
from copy import copy
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    Literal,
    Self,
    Type,
    TypeVar,
    Unpack,
)

from .context import FROZEN_CONTEXT
from .errors import PlateformeError
from .patterns import match_any_pattern
from .representations import ReprArgs, Representation
from .schema.fields import ConfigField, FieldInfo
from .schema.types import TypeAdapter
from .typing import (
    Default,
    DefaultPlaceholder,
    Deferred,
    PickleWeakRef,
    Undefined,
    get_cls_type_hints_lenient,
    get_cls_types_namespace,
    get_parent_frame_namespace,
    get_value_or_default,
    is_required,
    isbaseclass_lenient,
)
from .utils import get_meta_namespaces, get_meta_orig_bases

if typing.TYPE_CHECKING:
    from .resources import ResourceConfigDict, ResourceType
    from .schema.models import ModelConfigDict, ModelType
    from .services import ServiceConfigDict, ServiceType

PROTECTED_ATTRS = (
    r'check',
    r'clear',
    r'context',
    r'copy',
    r'entries',
    r'from_meta',
    r'get',
    r'items',
    r'keys',
    r'merge',
    r'pop',
    r'post_init',
    r'setdefault',
    r'update',
    r'validate',
    r'values',
)

__all__ = (
    'Config',
    'ConfigDict',
    'ConfigFieldInfo',
    'ConfigSource',
    'ConfigType',
    'ConfigWrapper',
    'ConfigWrapperMeta',
    'Configurable',
    'ConfigurableMeta',
    'evaluate_config_field',
    'with_config',
)


Config = TypeVar('Config', bound='ConfigWrapper')
"""A type variable for configuration classes."""


ConfigType = Type['ConfigWrapper']
"""A type alias for configuration classes."""


ConfigFieldInfo = FieldInfo['ConfigType']
"""A type alias for a configuration wrapper field information."""


ConfigSource = Type[Dict[str, Any]]
"""A type alias for configuration dictionary sources."""


# MARK: Configuration Wrapper Metaclass

@typing.dataclass_transform(
    kw_only_default=True, field_specifiers=(ConfigField,)
)
class ConfigWrapperMeta(type):
    """A metaclass for configuration wrappers."""
    if typing.TYPE_CHECKING:
        __config_fields__: dict[str, ConfigFieldInfo]
        __config_validators__: dict[str, TypeAdapter[Any]]

    def __new__(
        mcls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        __reset_parent_namespace: bool = True,
        /,
        sources: tuple[ConfigSource, ...] = (),
        **kwargs: Any,
    ) -> type:
        """Create a new configuration class.

        Args:
            __reset_parent_namespace: Flag indicating whether to reset the
                parent namespace for the configuration wrapper.
                Defaults to ``True``.
            sources: The configuration dictionary sources to collect the fields
                from. These dictionaries must be subclasses of a typed
                dictionary. Defaults to an empty tuple.
            **kwargs: The default values provided in addition to those in the
                configuration wrapper namespace.
        """
        # Check if configuration dictionary sources is iterable
        if not isinstance(sources, tuple):
            raise TypeError(
                f"Configuration dictionary sources to wrap must be provided "
                f"as a tuple. Got: {type(sources).__name__}."
            )

        # Create configuration class with the updated namespace
        cls = super().__new__(mcls, name, bases, namespace)

        # Set parent namespace if reset is enabled (default behavior)
        if __reset_parent_namespace:
            setattr(cls, '__config_parent_namespace__',
                PickleWeakRef.build_dict(get_parent_frame_namespace()))

        # Retrieve parent namespace
        parent_namespace = getattr(cls, '__config_parent_namespace__', None)
        if isinstance(parent_namespace, dict):
            parent_namespace = PickleWeakRef.unpack_dict(parent_namespace)

        # Retrieve parent sources
        parent_sources = getattr(cls, '__config_sources__', ())
        sources = tuple(dict.fromkeys(parent_sources + sources))

        # Collect configuration fields from the configuration dictionary
        # sources and the class namespace, and apply the defaults gathered from
        # the keyword arguments to the configuration fields.
        types_namespace = get_cls_types_namespace(cls, parent_namespace)
        fields = cls.collect_config_fields(
            bases, types_namespace, *sources, **kwargs
        )

        # Create validators for the configuration fields
        validators: dict[str, TypeAdapter[Any]] = {}
        for key, field in fields.items():
            try:
                validators[key] = TypeAdapter(
                    field.annotation,
                    config={'arbitrary_types_allowed': True},
                    _parent_depth=1,
                )
            except Exception:
                pass

        # Set configuration fields and sources
        setattr(cls, '__config_fields__', fields)
        setattr(cls, '__config_sources__', sources)
        setattr(cls, '__config_validators__', validators)

        return cls

    def collect_config_fields(
        cls,
        bases: tuple[type, ...],
        types_namespace: dict[str, Any] | None,
        *sources: ConfigSource,
        **defaults: Any,
    ) -> dict[str, ConfigFieldInfo]:
        """Collect configuration fields for the configuration wrapper.

        The configuration fields are collected from the wrapper class
        definition and the provided configuration dictionary sources. The
        configuration fields are checked for consistency in type across sources
        and for the presence of default values for non-required fields.

        Args:
            bases: The configuration wrapper base classes to collect the
                configuration fields from.
            types_namespace: The types namespace of the configuration wrapper
                to look for type hints.
            *sources: The configuration dictionary sources to collect the
                fields from. These dictionaries must be subclasses of a typed
                dictionary.
            **defaults: Optional default values to provide in addition to those
                in the configuration wrapper namespace. It is typically set
                with keyword arguments in the configuration wrapper definition.

        Returns:
            A dictionary containing the configuration fields collected from the
            wrapper class definition and the configuration dictionary sources.

        Raises:
            AttributeError: If a configuration field conflicts with a protected
                member attribute or is not present in the class namespace when
                setting a default value.
            TypeError: If a configuration dictionary source is not a valid
                subclass of a typed dictionary or if a configuration field has
                different annotations in the configuration dictionary sources.
            ValueError: If a not required configuration field does not have a
                default value.
        """
        fields: dict[str, ConfigFieldInfo] = {}

        # Store the configuration fields to check for default values. This is
        # done to ensure that all non-required fields specified in the
        # configuration dictionary sources have default values.
        check_for_default: set[str] = set()

        # Collect configuration fields from the dictionary sources
        for source in sources:
            # Check if the source is a typed dictionary
            if not issubclass(source, dict):
                raise TypeError(
                    f"A configuration dictionary source must be a subclass "
                    f"of a typed dictionary. Got: {source}."
                )

            # Retrieve annotations and total flag from the dictionary source
            # to determine whether the configuration fields are required.
            total = getattr(source, '__total__', False)
            annotations: dict[str, Any] = \
                getattr(source, '__annotations__', {})

            for name, value in annotations.items():
                # Skip private and dunder attributes
                if name.startswith('_'):
                    continue
                # Check protected attributes
                if match_any_pattern(name, *PROTECTED_ATTRS):
                    raise AttributeError(
                        f"Source configuration field {name!r} conflicts with "
                        f"a protected member attribute."
                    )
                # Check field shadowing in base classes
                for base in bases:
                    if hasattr(base, name):
                        warnings.warn(
                            f"Source configuration field {name!r} shadows an "
                            f"attribute in base class {base.__qualname__!r}.",
                            UserWarning,
                        )

                # Handle required fields and default values check
                if not is_required(value, total):
                    # Add the field to the default value check if it is not
                    # required, as a value may not be provided for it.
                    check_for_default.add(name)
                else:
                    # Remove the field from the default value check if it is
                    # required, as a value must be provided for it.
                    check_for_default.discard(name)

                # Create field information from the annotation
                field_info = ConfigFieldInfo.from_annotation(
                    value, owner=cls, name=name  # type: ignore
                )

                # Check if the configuration field is already defined
                if name in fields \
                        and fields[name].annotation != field_info.annotation:
                    raise TypeError(
                        f"Source configuration field {name!r} must have the "
                        f"same annotation in all configuration sources. Got: "
                        f"{fields[name].annotation!r} and "
                        f"{field_info.annotation!r}."
                    )

                fields[name] = field_info

        # Retrieve type hints and names from the configuration wrapper class
        # definition. The type names derived from annotations keys are used to
        # check if a field is defined in the class or in one of its bases.
        type_hints = get_cls_type_hints_lenient(cls, types_namespace)
        type_names = cls.__dict__.get('__annotations__', {}).keys()

        for name, value in type_hints.items():
            # Skip private and dunder attributes
            if name.startswith('_'):
                continue
            # Check protected attributes
            if match_any_pattern(name, *PROTECTED_ATTRS):
                raise AttributeError(
                    f"Namespace configuration field {name!r} conflicts with a "
                    f"protected member attribute."
                )
            # Check field shadowing in base classes
            for base in bases:
                if hasattr(base, name):
                    warnings.warn(
                        f"Namespace configuration field {name!r} shadows an "
                        f"attribute in base class {base.__qualname__!r}.",
                        UserWarning,
                    )

            try:
                default = getattr(cls, name, Undefined)
                if default is Undefined:
                    raise AttributeError
            except AttributeError:
                if name in type_names:
                    field_info = ConfigFieldInfo.from_annotation(
                        value, owner=cls, name=name  # type: ignore
                    )
                else:
                    # If field has no default value and is not in type names,
                    # then it may be defined in a base class.
                    fields_lookup: dict[str, ConfigFieldInfo] = {}
                    for base in cls.__bases__[::-1]:
                        fields_base = getattr(base, '__config_fields__', {})
                        fields_lookup.update(fields_base)
                    if name in fields_lookup:
                        # The field is present on one or multiple base classes
                        field_info = copy(fields_lookup[name])
                    else:
                        # The field is not found on any base classes
                        field_info = ConfigFieldInfo.from_annotation(
                            value, owner=cls, name=name  # type: ignore
                        )
            else:
                field_info = ConfigFieldInfo.from_annotated_attribute(
                    value, default, owner=cls, name=name  # type: ignore
                )
                # Removed field attributes from the class namespace to match
                # the behaviour of annotation-only fields and to avoid false
                # positives in the attribute check above.
                try:
                    delattr(cls, name)
                except AttributeError:
                    pass  # Indicates the attribute is on a parent class

            # Check if the configuration field is already defined
            if name in fields \
                    and fields[name].annotation != field_info.annotation:
                raise TypeError(
                    f"Namespace configuration field {name!r} must have the "
                    f"same annotation than in all configuration sources. Got: "
                    f"{fields[name].annotation!r} and "
                    f"{field_info.annotation!r}."
                )

            fields[name] = field_info

        # Update the configuration fields with the default values provided in
        # the class keyword arguments.
        for name, value in defaults.items():
            # Check if the default value is provided for a non-existing field
            if name not in fields:
                raise AttributeError(
                    f"Configuration field {name!r} is not present in the "
                    f"wrapped configuration."
                )
            # Check if the default value is of the correct type
            annotation = fields[name].annotation
            if annotation is not None \
                    and not isinstance(value, annotation):
                raise TypeError(
                    f"Default value for configuration field {name!r} must be "
                    f"of type {annotation.__name__!r}. Got: "
                    f"{type(value).__name__!r}."
                )
            fields[name].default = value

        # Check whether all non required fields have default values
        for name in check_for_default:
            if fields[name].default is Undefined \
                    and fields[name].default_factory is None:
                raise ValueError(
                    f"Configuration field {name!r} must have a default value "
                    f"as it is marked as not required in the configuration "
                    f"dictionary sources."
                )

        return fields

    def __len__(cls) -> int:
        return len(cls.__config_fields__)

    def __getitem__(cls, key: str) -> Any:
        return cls.__config_fields__.get(key)

    def __setitem__(cls, key: str, value: Any) -> None:
        raise KeyError(
            f"Configuration key {key!r} cannot be set for wrapper metaclass "
            f"{cls.__qualname__!r}."
        )

    def __delitem__(cls, key: str) -> None:
        raise KeyError(
            f"Configuration key {key!r} cannot be deleted for wrapper "
            f"metaclass {cls.__qualname__!r}."
        )


# MARK: Configuration Wrapper

class ConfigWrapper(Representation, metaclass=ConfigWrapperMeta):
    """A base configuration wrapper class.

    A configuration wrapper class is a class that wraps a configuration
    dictionary and provides a set of configuration fields that can be used to
    define the structure of the configuration dictionary. The configuration
    fields are used to validate the configuration dictionary and to provide
    default values for the configuration keys.

    The configuration wrapper class is typically used as a base class for
    configuration classes that define the configuration structure for models,
    resources, services, and other components in the Plateforme framework.

    Attributes:
        __config_fields__: A dictionary containing the configuration fields
            information for the configuration wrapper class.
        __config_mutable__: A flag indicating whether the configuration
            instance is mutable, i.e., whether owner class instances
            configurations can be modified. Defaults to ``False``.
        __config_parent_namespace__: The parent namespace of the configuration
            wrapper class. It is used to retrieve the type hints and
            annotations of the configuration wrapper class.
            Defaults to ``None``.
        __config_sources__: A tuple containing the configuration dictionary
            sources used to collect the configuration fields for the
            configuration wrapper class. Defaults to an empty tuple.
        __config_validators__: A dictionary containing the type validators for
            the configuration fields of the configuration wrapper class.
    """
    if typing.TYPE_CHECKING:
        __config_fields__: ClassVar[dict[str, ConfigFieldInfo]]
        __config_mutable__: ClassVar[bool]
        __config_parent_namespace__: ClassVar[dict[str, Any] | None]
        __config_sources__: ClassVar[tuple[ConfigSource, ...]]
        __config_validators__: ClassVar[dict[str, TypeAdapter[Any]]]
    else:
        __config_mutable__ = False
        __config_parent_namespace__ = None
        __config_sources__ = ()

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        """Create a new configuration instance."""
        # Check if wrapper is directly instantiated
        if cls is ConfigWrapper:
            raise TypeError(
                "A wrapper configuration class cannot be directly "
                "instantiated."
            )
        return super().__new__(cls)

    def __init__(
        self,
        __owner: Any | None = None,
        __defaults: dict[str, Any] | None = None,
        __partial_init: bool = False,
        /,
        **data: Any,
    ) -> None:
        """Initialize the configuration class with the given data.

        Args:
            __owner: The owner of the configuration instance. It can be any
                object or type that uses the configuration instance.
                Defaults to ``None``.
            __defaults: The default values to initialize the configuration
                instance with. Defaults to ``None``.
            __partial_init: Flag indicating whether  to partially initialize
                the configuration instance. Defaults to ``False``.
            **data: The data as keyword arguments to initialize the
                configuration instance with.
        """
        # Initialize configuration instance
        self.__config_owner__ = __owner \
            or getattr(self, '__config_owner__', None)
        self.__config_defaults__: dict[str, Any] = __defaults or {}
        with self.context(allow_mutation=True):
            self.update(data)

        # Validate configuration instance
        if not __partial_init:
            self.validate()

    def __get__(self, instance: Any, owner: Any) -> Self:
        """Set the configuration wrapper owner if not already set."""
        # Setup configuration owner
        if self.__config_owner__ is None:
            self.__config_owner__ = owner
        elif self.__config_owner__ is not owner:
            raise AttributeError(
                f"Configuration instance {self.__class__.__qualname__!r} "
                f"cannot be accessed from a different owner. It is owned by "
                f"{self.__config_owner__!r}."
            )
        # Handle mutable configuration instances
        if instance is not None and self.__config_mutable__:
            config_attr = getattr(owner, '__config_attr__', None)
            if config_attr is not None:
                assert isinstance(instance, object)
                return instance.__dict__.get(config_attr, self)  # type: ignore
        return self

    def __set__(self, instance: Any, value: Any) -> None:
        # Handle mutable configuration instances
        if not self.__config_mutable__:
            raise AttributeError(
                f"Configuration instance {self.__class__.__qualname__!r} "
                f"cannot be set to an instance attribute as it is immutable."
            )
        if self.__config_owner__ is None \
                or not hasattr(self.__config_owner__, '__config_attr__'):
            raise AttributeError(
                f"Configuration instance {self.__class__.__qualname__!r} "
                f"cannot be set as an instance attribute. The instance must "
                f"be a valid configurable owner with a defined configuration "
                f"attribute. Got: {instance.__class__!r}."
            )
        if not isinstance(instance, self.__config_owner__):
            raise AttributeError(
                f"Configuration instance {self.__class__.__qualname__!r} "
                f"cannot be set to a different owner class. Got: "
                f"{instance.__class__!r} instead of {self.__config_owner__!r}."
            )
        config_attr = getattr(self.__config_owner__, '__config_attr__')
        instance.__dict__[config_attr] = value

    def __delete__(self, instance: Any) -> None:
        raise AttributeError(
            f"Configuration instance {self.__class__.__qualname__!r} cannot "
            f"be deleted from {instance.__class__.__qualname__!r}."
        )

    @classmethod
    def create(
        cls,
        owner: Any | None = None,
        defaults: dict[str, Any] | None = None,
        partial_init: bool = False,
        *,
        data: dict[str, Any] | None = None,
    ) -> Self:
        """Create a new configuration instance.

        This method is typically used internally to create a new configuration
        class with a specific owner and partial initialization flag. It is an
        alternative to the `__init__` method for creating a new configuration
        instance.

        Args:
            owner: The owner of the configuration instance.
            defaults: The default values to initialize the configuration
                instance with. Defaults to ``None``.
            partial_init: Flag indicating whether to partially initialize the
                configuration instance. Defaults to ``False``.
            data: The data to initialize the configuration instance with.
                Defaults to ``None``.

        Returns:
            The new configuration instance created.
        """
        return cls(owner, defaults, partial_init, **(data or {}))

    @classmethod
    def from_meta(
        cls,
        owner: type[Any],
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        /,
        config_attr: str = '__config__',
        partial_init: bool = False,
        data: dict[str, Any] | None = None,
    ) -> Self:
        """Create a new configuration instance from a class constructor.

        This method is typically used internally to create a new configuration
        class from the meta configuration of a model, package, resource, or
        service. It merges the configuration of the given bases, the namespace,
        and the keyword arguments to create a new configuration class.

        Args:
            owner: The owner of the configuration instance. It should be the
                class that is being created from the meta configuration.
            bases: The configurable base classes to merge.
            namespace: The configurable namespace to merge.
            config_attr: The configurable attribute name used to extract the
                configuration dictionary from the bases and the namespace of
                the configurable class. Defaults to ``'__config__'``.
            partial_init: Flag indicating whether to partially initialize the
                configuration instance. Defaults to ``False``.
            data: The data to initialize the configuration instance with.
                Defaults to ``None``.

        Returns:
            The new configuration instance created from the given meta
            configuration.
        """
        with cls.context(allow_mutation=True):
            # Build configuration instance
            config = cls(owner, {}, True)

            for base in bases:
                base_config = getattr(base, config_attr, {})
                if callable(base_config):
                    base_config = base_config()
                config.merge(base_config)

            namespace_config = namespace.get(config_attr, {})
            if callable(namespace_config):
                namespace_config = namespace_config()
            config.merge(namespace_config)

            config.merge(data or {})

            # Validate configuration instance
            if not partial_init:
                config.validate()

        return config

    def post_init(self) -> None:
        """Post-initialization method for the configuration class.

        Override this method to perform additional initialization steps after
        the configuration instance has been created. This method is called
        automatically after the configuration instance has been initialized,
        unless the `partial_init` flag is set to ``True``.

        Note:
            See the `validate` method for more information on the validation
            process of the configuration instance.
        """
        ...

    def validate(
        self,
        *,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Validate the configuration instance.

        It post-initializes the configuration instance, checks for any missing
        required fields and validates the assignments of the configuration
        values based on the configuration fields information and the current
        validation context. This is performed automatically upon initialization
        of the configuration instance.

        Args:
            strict: Whether to enforce strict validation. Defaults to ``None``.
            context: The context to use for validation. Defaults to ``None``.

        Raises:
            ValueError: If the configuration instance has undefined values for
                required fields.
            ValidationError: If the assignment of a value is invalid based on
                the configuration fields information and the current validation
                context.
        """
        # Perform post-initialization
        self.post_init()

        # Validate for missing required fields
        config_missing = [
            key for key, field in self.__config_fields__.items()
            if field.is_required() and self[key] is Undefined
        ]
        if config_missing:
            raise ValueError(
                f"Undefined values for configuration "
                f"{self.__class__.__qualname__!r} required fields: "
                f"{', '.join(config_missing)}."
            )

        # Validate assignments
        for key, value in self.entries(scope='set').items():
            if not strict and value is Deferred:
                continue
            if key in self.__config_validators__:
                validator = self.__config_validators__[key].validate_python
                value = validator(value, strict=strict, context=context)
            self.__dict__[key] = value

    @staticmethod
    @contextmanager
    def context(
        *, allow_mutation: bool | None = None,
    ) -> Iterator[bool]:
        """Context manager for the configuration instance.

        If the frozen mutation flag is not specified, the current frozen
        mutation flag is used if available, otherwise it defaults to ``False``.

        Args:
            allow_mutation: Flag indicating whether to allow frozen mutation
                of the configuration instance. When set to ``False``, it
                prevents any changes by setting the frozen flag to ``True``.
                If not specified, the current frozen mutation flag is used if
                available, otherwise it resolves to ``False``.
                Defaults to ``None``.
        """
        context = FROZEN_CONTEXT.get()

        # Set frozen mutation flag
        if allow_mutation is None:
            if context is not None:
                frozen = context
            frozen = True
        else:
            frozen = not allow_mutation

        # Yield and reset frozen mutation flag
        token = FROZEN_CONTEXT.set(frozen)
        try:
            yield frozen
        finally:
            FROZEN_CONTEXT.reset(token)

    def clear(self) -> None:
        """Clear the configuration dictionary and reset all values."""
        for key in self.__config_fields__:
            self.__dict__.pop(key, None)

    def copy(self) -> Self:
        """Return a shallow copy of the configuration dictionary."""
        return self.__class__(
            self.__config_owner__,
            self.__config_defaults__.copy(),
            False,
            **self.entries(scope='set')
        )

    def merge(
        self,
        *configs: Self | dict[str, Any],
        setdefault: bool = False,
    ) -> None:
        """Merge the configuration with other configurations.

        It merges the configuration with the provided configuration instances
        or dictionaries. The precedence of the rightmost configuration is
        higher than the leftmost configuration. This can be changed by setting
        the `setdefault` argument to ``True``.

        Args:
            *configs: The configuration instances or dictionaries to merge with
                the target configuration dictionary.
            setdefault: Flag indicating whether to set the default values for
                the configuration keys if they are not already set.
                This modifies the behavior of the merge operation, making the
                precedence of the leftmost configuration higher than the
                rightmost configuration.
                Defaults to ``False`` (rightmost precedence).
        """
        for config in configs:
            # Retrieve the configuration dictionary
            if isinstance(config, self.__class__):
                config_dict = {
                    key: value
                    for key, value in config.__dict__.items()
                    if key in config.__config_fields__
                }
            elif isinstance(config, dict):
                config_dict = config.copy()
            else:
                raise TypeError(
                    f"Invalid configuration type {type(config).__name__!r} "
                    f"for {self.__class__.__qualname__!r}, it must be a "
                    f"dictionary or a configuration instance."
                )
            # Merge with the target configuration dictionary
            if setdefault:
                for key, value in config_dict.items():
                    self.setdefault(key, value)
            else:
                self.update(config_dict)

    def check(
        self,
        key: str,
        *,
        scope: Literal['all', 'default', 'set'] = 'all',
        raise_errors: bool = True,
    ) -> bool:
        """Check if the configuration key exists in the given scope.

        Args:
            key: The configuration key to check for.
            scope: The scope to check for the configuration key. It can be
                either ``'all'`` to check in all configuration entries,
                ``'default'`` to check in configuration entries with default
                values not undefined, or ``'set'`` to check in only the
                configuration entries that have been explicitly set.
                Defaults to ``'all'``.
            raise_errors: Flag indicating whether to raise an error if the
                configuration key is not defined for the configuration wrapper.
                Defaults to ``True``.

        Returns:
            A boolean indicating whether the configuration key exists in the
            specified scope.
        """
        if key not in self.__config_fields__:
            if not raise_errors:
                return False
            raise KeyError(
                f"Configuration key {key!r} cannot be checked as it is not "
                f"defined for wrapper {self.__class__.__qualname__!r}."
            )
        if scope == 'default':
            return key not in self.__dict__
        if scope == 'set':
            return key in self.__dict__
        return True

    def entries(
        self,
        *,
        scope: Literal['all', 'default', 'set'] = 'all',
        default_mode: Literal['preserve', 'unwrap', 'wrap'] = 'unwrap',
        include_keys: Iterable[str] | None = None,
        exclude_keys: Iterable[str] | None = None,
        include_metadata: Iterable[Any] | None = None,
        exclude_metadata: Iterable[Any] | None = None,
    ) -> dict[str, Any]:
        """Return the configuration dictionary.

        It returns the configuration dictionary based on the specified scope,
        and keys and extra information to filter the configuration dictionary
        entries.

        Args:
            scope: The scope of the configuration dictionary to return. It can
                be either ``'all'`` to return all configuration entries,
                ``'default'`` to return all configuration entries with their
                default values, or ``'set'`` to return only the configuration
                entries that have been explicitly set. Defaults to ``'all'``.
            default_mode: The default mode to use when returning a default
                entry from the configuration dictionary. It can be either
                ``'preserve'`` to keep the default value as is, ``'unwrap'`` to
                unwrap the default value, or ``'wrap'`` to wrap the default
                value with a default placeholder. Defaults to ``'unwrap'``.
            include_keys: The keys to include from the configuration dictionary
                entries. Defaults to ``None``.
            exclude_keys: The keys to exclude from the configuration dictionary
                entries. Defaults to ``None``.
            include_metadata: The metadata information to include from the
                configuration dictionary entries. Defaults to ``None``.
            exclude_metadata: The metadata information to exclude from the
                configuration dictionary entries. Defaults to ``None``.

        Returns:
            A dictionary containing the configuration entries based on the
            specified scope and extra information.
        """
        # Retrieve the configuration dictionary based on the specified scope
        config_dict: dict[str, Any] = {}
        if scope == 'default':
            for key in self.__config_fields__:
                if key in self.__dict__:
                    continue
                config_dict[key] = self.get(key, default_mode=default_mode)
        elif scope == 'set':
            for key in self.__config_fields__:
                if key not in self.__dict__:
                    continue
                config_dict[key] = self.get(key, default_mode=default_mode)
        else:
            for key in self.__config_fields__:
                config_dict[key] = self.get(key, default_mode=default_mode)

        # Build the keys and metadata sets to include and exclude from the
        # configuration dictionary entries.
        incex_keys = [include_keys, exclude_keys]
        for count, value in enumerate(incex_keys):
            if value is not None:
                if isinstance(value, type) and \
                        issubclass(value, ConfigWrapper):
                    value = value.__config_fields__.keys()
                incex_keys[count] = set(value)

        incex_metadata = [include_metadata, exclude_metadata]
        for count, value in enumerate(incex_metadata):
            if value is not None:
                incex_metadata[count] = set(value)

        # Return directly if no keys or metadata filtering is provided.
        if not any(incex_keys) and not any(incex_metadata):
            return config_dict

        # Filter the configuration dictionary based on the information and keys
        # if provided in the "with" arguments.
        for key in list(config_dict.keys()):
            if incex_keys[0] is not None and key not in incex_keys[0]:
                config_dict.pop(key)
            elif incex_keys[1] is not None and key in incex_keys[1]:
                config_dict.pop(key)
            elif incex_metadata[0] is not None and not all(
                metadata in self.__config_fields__[key].metadata
                for metadata in incex_metadata[0]
            ):
                config_dict.pop(key)
            elif incex_metadata[1] is not None and any(
                metadata in self.__config_fields__[key].metadata
                for metadata in incex_metadata[1]
            ):
                config_dict.pop(key)

        return config_dict

    def keys(self) -> KeysView[str]:
        """Return the configuration keys."""
        return KeysView(self.entries())

    def values(self) -> ValuesView[Any]:
        """Return the configuration values."""
        return ValuesView(self.entries())

    def items(self) -> ItemsView[str, Any]:
        """Return the configuration items."""
        return ItemsView(self.entries())

    @typing.overload
    def get(self, key: str) -> Any: ...

    @typing.overload
    def get(self, key: str, default: Any) -> Any: ...

    @typing.overload
    def get(
        self, key: str,
        default: Any = Undefined,
        *,
        default_mode: Literal['preserve', 'unwrap', 'wrap'] = 'unwrap',
    ) -> Any: ...

    def get(
        self, key: str,
        default: Any = Undefined,
        *,
        default_mode: Literal['preserve', 'unwrap', 'wrap'] = 'unwrap',
    ) -> Any:
        """Get the value for the specified key if set otherwise the default.

        Args:
            key: The configuration key to get the value for.
            default: The default value to return if the key is not set.
            default_mode: The default mode to use when returning a default
                value from the configuration dictionary. It can be either
                ``'preserve'`` to keep the default value as is, ``'unwrap'`` to
                unwrap the default value, or ``'wrap'`` to wrap the default
                value with a placeholder. Defaults to ``'unwrap'``.
        """
        if key not in self.__config_fields__:
            raise KeyError(
                f"Configuration key {key!r} cannot be retrieved as it is not "
                f"defined for wrapper {self.__class__.__qualname__!r}."
            )
        if key in self.__dict__:
            return self.__dict__[key]
        if default is Undefined:
            return self.getdefault(key, mode=default_mode)
        if default_mode == 'wrap':
            return Default(default)
        if default_mode == 'unwrap':
            return get_value_or_default(default)
        return default

    @typing.overload
    def pop(self, key: str) -> Any: ...

    @typing.overload
    def pop(self, key: str, default: Any) -> Any: ...

    @typing.overload
    def pop(
        self,
        key: str,
        default: Any = Undefined,
        *,
        default_mode: Literal['preserve', 'unwrap', 'wrap'] = 'unwrap',
    ) -> Any: ...

    def pop(
        self,
        key: str,
        default: Any = Undefined,
        *,
        default_mode: Literal['preserve', 'unwrap', 'wrap'] = 'unwrap',
    ) -> Any:
        """Pop the specified key if set and return its corresponding value.

        Args:
            key: The configuration key to pop the value for.
            default: The default value to return if the key is not set.
            default_mode: The default mode to use when returning a default
                value from the configuration dictionary. It can be either
                ``'preserve'`` to keep the default value as is, ``'unwrap'`` to
                unwrap the default value, or ``'wrap'`` to wrap the default
                value with a placeholder. Defaults to ``'unwrap'``.
        """
        if key not in self.__config_fields__:
            raise KeyError(
                f"Configuration key {key!r} cannot be popped as it is not "
                f"defined for wrapper {self.__class__.__qualname__!r}."
            )
        if key in self.__dict__:
            return self.__dict__.pop(key)
        if default is Undefined:
            return self.getdefault(key, mode=default_mode)
        if default_mode == 'wrap':
            return Default(default)
        if default_mode == 'unwrap':
            return get_value_or_default(default)
        return default

    def getdefault(
        self,
        key: str,
        *,
        mode: Literal['preserve', 'unwrap', 'wrap'] = 'unwrap',
    ) -> Any:
        """Get the default value for the specified key.

        Args:
            key: The configuration key to get the default value for.
            mode: The mode to use when returning the default value. It can be
                either ``'preserve'`` to keep the default value as is,
                ``'unwrap'`` to unwrap the default value, or ``'wrap'`` to wrap
                the default value with a placeholder. Defaults to ``'unwrap'``.
        """
        if key not in self.__config_fields__:
            raise KeyError(
                f"Default for configuration key {key!r} cannot be retrieved "
                f"as it is not defined for wrapper "
                f"{self.__class__.__qualname__!r}."
            )
        elif key in self.__config_defaults__:
            default = self.__config_defaults__[key]
        else:
            default = self.__config_fields__[key].get_default()

        if mode == 'wrap':
            return Default(default)
        if mode == 'unwrap':
            return get_value_or_default(default)
        return default

    def setdefault(self, key: str, default: Any) -> Any:
        """Set the default value for the specified key.

        Args:
            key: The configuration key to set the default value for.
            default: The default value to set for the key.
        """
        if key not in self.__config_fields__:
            raise KeyError(
                f"Default for configuration key {key!r} cannot be set as it "
                f"is not defined for wrapper {self.__class__.__qualname__!r}."
            )
        self.__config_defaults__[key] = default
        return default

    def update(
        self,
        *args: tuple[str, Any] | Mapping[str, Any],
        **kwargs: Any,
    ) -> None:
        """Update the config dictionary with new data."""
        # Helper function to update configuration entries
        def update_entry(key: str, value: Any) -> None:
            if key not in self.__config_fields__:
                raise KeyError(
                    f"Configuration key {key!r} cannot be updated as it is "
                    f"not defined for wrapper {self.__class__.__qualname__!r}."
                )
            setattr(self, key, value)

        # Update args data
        for arg in args:
            if isinstance(arg, tuple):
                if len(arg) != 2:
                    raise ValueError(
                        f"Configuration update arguments must be provided as "
                        f"key-value pairs. Got: {arg}."
                    )
                update_entry(arg[0], arg[1])
            else:
                for key, value in arg.items():
                    update_entry(key, value)
        # Update kwargs data
        for key, value in kwargs.items():
            update_entry(key, value)

    @classmethod
    def __contains__(cls, key: str) -> bool:
        return key in cls.__config_fields__

    @classmethod
    def __iter__(cls) -> Iterator[str]:
        yield from cls.__config_fields__

    @classmethod
    def __reversed__(cls) -> Iterator[str]:
        yield from reversed(cls.__config_fields__)

    def __len__(self) -> int:
        return len(self.entries(scope='set'))

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def __delitem__(self, key: str) -> None:
        delattr(self, key)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, self.__class__):
            return self.entries() == other.entries()
        if isinstance(other, dict):
            return self.entries(scope='set') == other
        return False

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __or__(self, other: Self | dict[str, Any]) -> Self:
        target = self.copy()
        target.merge(other, setdefault=False)
        return target

    def __ior__(self, other: Self | dict[str, Any]) -> Self:
        self.merge(other, setdefault=False)
        return self

    def __ror__(self, other: Self | dict[str, Any]) -> Self:
        target = self.copy()
        target.merge(other, setdefault=True)
        return target

    def __copy__(self) -> Self:
        return self.copy()

    # Hide attributes getter from type checkers to prevent MyPy from allowing
    # arbitrary attribute access instead of raising an error if the attribute
    # is not defined in the configuration dictionary.
    if not typing.TYPE_CHECKING:
        def __getattribute__(self, name: str) -> Any:
            return super().__getattribute__(name)

        def __getattr__(self, name: str) -> Any:
            # Skip dunder attributes
            if name.startswith('__') and name.endswith('__'):
                return super().__getattr__(name)
            if name not in self.__config_fields__:
                raise KeyError(
                    f"Configuration key {name!r} cannot be accessed as it is "
                    f"not defined for wrapper {self.__class__.__qualname__!r}."
                )
            if name in self.__config_defaults__:
                value = self.__config_defaults__[name]
            else:
                value = self.__config_fields__[name].get_default()
            return get_value_or_default(value)

    def __setattr__(self , name: str, value: Any) -> None:
        # Skip dunder attributes
        if name.startswith('__') and name.endswith('__'):
            super().__setattr__(name, value)
            return
        # Only allow setting of attributes that are defined in the config
        # dictionary. This is to prevent arbitrary attribute access and to
        # enforce the configuration schema.
        if name not in self.__config_fields__:
            raise KeyError(
                f"Configuration key {name!r} cannot be set as it is not "
                f"defined for wrapper {self.__class__.__qualname__!r}."
            )
        field = self.__config_fields__[name]
        # Check if attribute is frozen and mutation is not allowed
        frozen_context = FROZEN_CONTEXT.get()
        if frozen_context and field.frozen:
            raise KeyError(
                f"Configuration key {name!r} is frozen and cannot be set for "
                f"wrapper {self.__class__.__qualname__!r}."
            )
        # Skip silently undefined values as they are equivalent to not setting
        # the attribute at all.
        if value is Undefined:
            return
        # Set attribute value
        if isinstance(value, DefaultPlaceholder):
            self.__config_defaults__[name] = value
        else:
            super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        # Prevent deletion of attributes
        raise KeyError(
            f"Configuration key {name!r} cannot be deleted as deletion of any "
            f"configuration keys is not allowed for wrapper "
            f"{self.__class__.__qualname__!r}."
        )

    def __repr_args__(self) -> ReprArgs:
        yield (None, self.__config_owner__)


# MARK: Configurable Metaclass

class ConfigurableMeta(type):
    """A metaclass for configurable classes."""

    def __new__(
        mcls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        /,
        *args: Any,
        config_attr: str | None = None,
        partial_init: bool = False,
        **kwargs: Any,
    ) -> type:
        """Create a new configurable class.

        Args:
            config_attr: The public configurable attribute name used to expose
                the configuration dictionary. This is also used to extract the
                configuration dictionary from the base configurable classes.
                When configuring a class, custom configuration attribute should
                not be present in the class namespace, instead the default
                configuration attribute ``__config__`` should be used.
                Defaults to ``None``.
            partial_init: Flag indicating whether to partially initialize the
                configuration instance. Defaults to ``False``.
            **kwargs: Additional keyword arguments to pass to the metaclass.
        """
        # Return the class directly if it is the base configurable class
        if name == 'Configurable' and len(bases) == 1:
            return super().__new__(
                mcls, name, bases, namespace, *args, **kwargs
            )

        # Collect the configuration attribute from the class namespace and the
        # provided bases.
        config_attrs = [config_attr]
        config_attrs.append(namespace.get('__config_attr__', None))
        for base in bases:
            config_attrs.append(getattr(base, '__config_attr__', None))
        config_attrs = [attr for attr in config_attrs if attr is not None]

        # Validate the configuration attribute
        if not config_attrs:
            config_attr = '__config__'
        else:
            # Check if there is only one configuration attribute
            config_attr = config_attrs[0]
            if any(attr != config_attr for attr in config_attrs[1:]):
                raise TypeError(
                    f"Configurable class {name!r} must have a unique "
                    f"configuration attribute. Got multiple configuration "
                    f"attributes: {', '.join(set(*config_attrs))}."
                )
            assert isinstance(config_attr, str)

        if config_attr != '__config__':
            if config_attr in namespace:
                raise PlateformeError(
                    f"Public configuration attribute {config_attr!r} cannot "
                    f"be defined in the class namespace. The default "
                    f"configuration attribute `__config__` should be used "
                    f"instead.",
                    code='attribute-invalid-config',
                )

        # Expose the configuration through its public attribute for base class
        # consumption. This decouples the configuration from the class
        # creation process and is crucial to avoid any changes that could be
        # made to the configuration during the class creation process. This is
        # typically the case with Pydantic models that modify the configuration
        # attribute upon class creation.
        if '__config__' in namespace:
            namespace[config_attr] = namespace['__config__']

        # Create the configurable class with the provided config attribute.
        cls = super().__new__(mcls, name, bases, namespace, *args, **kwargs)

        # Rollback the namespace configuration to its original value
        if '__config__' in namespace:
            namespace[config_attr] = namespace['__config__']

        # Collect the configuration wrappers from the bases and original bases
        # found within the class namespace and the provided bases.
        config_wrappers = cls.collect_config_wrappers(bases, namespace)

        # Check if there is at least one configuration wrapper
        if not config_wrappers:
            raise TypeError(
                f"Configurable class {cls.__qualname__!r} must implement at "
                f"least one configuration wrapper. It's most likely that the "
                f"class being configured does not inherit from the base "
                f"`Configurable` class."
            )

        # Check if all configuration wrappers inherit from a same base wrapper
        config_wrapper = config_wrappers[0]
        for config_other in config_wrappers[1:]:
            if not issubclass(config_wrapper, config_other):
                raise TypeError(
                    f"All configurable classes must inherit the same type of "
                    f"configuration wrapper. Got multiple configuration "
                    f"wrappers: {', '.join(set(*config_wrappers))}."
                )

        # Set the configuration attribute
        setattr(cls, '__config_attr__', config_attr)

        # Create the configuration class
        config = config_wrapper.from_meta(
            cls,
            bases,
            namespace,
            config_attr=config_attr,
            partial_init=partial_init,
            data=kwargs,
        )

        # Set the configuration class
        setattr(cls, '__config__', config)
        if config_attr != '__config__':
            setattr(cls, config_attr, config)

        return cls

    def collect_config_wrappers(
        cls, bases: tuple[type, ...], namespace: dict[str, Any], /,
    ) -> list[ConfigType]:
        """Collect configuration wrappers from the given bases and namespace.

        It collects the configuration wrappers from the given bases and
        namespace by extracting the configuration wrapper type from the
        original bases annotation if it is a generic subclass of the
        configurable class or metaclass, and from the configuration attribute
        if present in the class and bases namespace.

        Args:
            bases: The class bases.
            namespace: The class namespace.

        Returns:
            A list of configuration wrapper classes found in the given bases
            and namespace.
        """
        config_attr = getattr(cls, '__config_attr__', '__config__')
        config_wrappers: list[ConfigType] = []

        # The collection process is done in two steps to ensure that the
        # configuration attribute is extracted from the annotation first, and
        # then from the class and bases namespace.

        # Extract the configuration wrapper type from the annotation if it is a
        # generic subclass of the configurable class.
        meta_bases = get_meta_orig_bases(bases, namespace)
        for meta_base in meta_bases:
            origin = typing.get_origin(meta_base)
            if origin is None:
                continue
            if not isbaseclass_lenient(origin, 'Configurable'):
                continue
            args = typing.get_args(meta_base)
            if len(args) == 1:
                if isinstance(args[0], TypeVar):
                    break
                if issubclass(args[0], ConfigWrapper):
                    config_wrappers.append(args[0])
                    break
            raise TypeError(
                f"Generic argument for the `Configurable` class must be a "
                f"subclass of the base configuration wrapper. Got: {args}."
            )

        # Extract the configuration wrapper type from the configuration
        # attribute if present in the class and bases namespace.
        meta_namespaces = get_meta_namespaces(bases, namespace)
        for meta_namespace in meta_namespaces:
            if config_attr not in meta_namespace:
                continue
            config_wrapper = meta_namespace[config_attr]
            if callable(config_wrapper):
                config_wrapper = config_wrapper()
            if isinstance(config_wrapper, ConfigWrapper):
                config_wrappers.append(config_wrapper.__class__)
                continue
            if isinstance(config_wrapper, dict):
                continue
            raise TypeError(
                f"Configuration attribute must be a dictionary or an "
                f"instance of the base configuration wrapper. Got: "
                f"{type(config_wrapper).__qualname__}."
            )

        return config_wrappers


# MARK: Configurable

class Configurable(Generic[Config], metaclass=ConfigurableMeta):
    """A base configurable class.

    A base class that provides a configuration wrapper to manage the
    configuration of the class and its subclasses.

    Attributes:
        __config__: The configuration instance for the configurable class.
        __config_attr__: The configurable attribute name used to extract the
            configuration dictionary from the bases and the namespace of the
            configurable class.
    """
    if typing.TYPE_CHECKING:
        __config__: ClassVar[ConfigWrapper | Mapping[str, Any]]
        __config_attr__: ClassVar[str]

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        """Create a new configurable instance."""
        # Check if class is directly instantiated
        if cls is Configurable:
            raise TypeError(
                "A base configurable class cannot be directly instantiated."
            )
        self = super().__new__(cls)

        # Handle mutable configuration instances
        config: ConfigWrapper = getattr(cls, '__config__')
        if config.__config_mutable__:
            config = config.copy()
            config_attr = getattr(cls, '__config_attr__')
            object.__setattr__(self, config_attr, config)

        return self

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # Prevent passing keyword arguments to parent classes.
        super().__init_subclass__()


# MARK: Configuration Dictionary

@typing.overload
def ConfigDict(
    type_: Literal['resource'] = 'resource',
    **kwargs: Unpack['ResourceConfigDict'],
) -> 'ResourceConfigDict':
    ...

@typing.overload
def ConfigDict(
    type_: Literal['model'],
    **kwargs: Unpack['ModelConfigDict'],
) -> 'ModelConfigDict':
    ...

@typing.overload
def ConfigDict(
    type_: Literal['service'],
    **kwargs: Unpack['ServiceConfigDict'],
) -> 'ServiceConfigDict':
    ...

def ConfigDict(
    type_: Literal['resource', 'model', 'service'] = 'resource',
    **kwargs: Any,
) -> 'ResourceConfigDict | ModelConfigDict | ServiceConfigDict':
    return kwargs  # type: ignore


# MARK: Utilities

def evaluate_config_field(
    config: ConfigWrapper, /, name: str, *, parents: Any
) -> Any:
    """Evaluate a configuration field from the provided sources.

    It evaluates the configuration field from the provided configuration
    sources, which can be any object that has a configuration wrapper or a
    configuration dictionary. The evaluation is done by taking the first
    defined value from the sources (non default), where the first parent has
    the highest precedence.

    Args:
        name: The name of the field to evaluate.
        config: The configuration object to evaluate the field from.
        *parents: The parents to evaluate the field from. The first parent
            has the highest precedence.

    Returns:
        The evaluated configuration field.
    """
    if name not in config.__config_fields__:
        raise KeyError(
            f"Configuration field {name!r} is not defined in the "
            f"configuration wrapper {config.__class__.__qualname__!r}."
        )
    values = [config.get(name, default_mode='wrap')]
    for parent in parents:
        if isinstance(parent, ConfigWrapper):
            values.append(parent.get(name, default_mode='wrap'))
        else:
            values.append(getattr(parent, name, Default()))
    return get_value_or_default(*values)


@typing.overload
def with_config(
    type_: Literal['model'],
    **kwargs: Unpack['ModelConfigDict'],
) -> Callable[[type[Any]], 'ModelType']:
    ...

@typing.overload
def with_config(
    type_: Literal['resource'],
    **kwargs: Unpack['ResourceConfigDict'],
) -> Callable[[type[Any]], 'ResourceType']:
    ...

@typing.overload
def with_config(
    type_: Literal['service'],
    **kwargs: Unpack['ServiceConfigDict'],
) -> Callable[[type[Any]], 'ServiceType']:
    ...

def with_config(
    type_: Literal['model', 'resource', 'service'],
    **kwargs: Any,
) -> Callable[[type[Any]], type[Any]]:
    """Decorator to apply configuration to a class.

    It transforms the decorated class into the specified configuration class
    type and applies the provided configuration to the class.

    Args:
        type_: The configuration type to apply. It can be one of: ``'model'``,
            ``'resource'``, or ``'service'``. This determines both the type of
            class to create and the type of configuration to apply.
        **kwargs: The keyword arguments to pass to the configuration instance.

    Returns:
        A decorator to apply the configuration to the class.

    Raises:
        NotImplementedError: If the configuration type is not supported.
    """

    def decorator(cls: type[Any]) -> type[Any]:
        # Validate configuration type
        config: ConfigWrapper
        config_type: type[Configurable[Any]]

        match type_:
            case 'model':
                from .schema.models import BaseModel, ModelConfig
                config = ModelConfig(**kwargs)
                config_type = BaseModel
            case 'resource':
                from .resources import BaseResource, ResourceConfig
                config = ResourceConfig(**kwargs)
                config_type = BaseResource
            case 'service':
                from .services import BaseService, ServiceConfig
                config = ServiceConfig(**kwargs)
                config_type = BaseService
            case _:
                raise NotImplementedError(
                    f"Unsupported configuration type: '{type_}'."
                )

        # FUTURE: Add support for configuration decorator style
        raise NotImplementedError('Not implemented yet...')

    return decorator
