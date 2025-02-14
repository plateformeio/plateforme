# plateforme.core.selectors
# -------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing selectors used in resources within
the Plateforme framework.
"""

import re
import typing
from abc import ABCMeta
from collections.abc import Iterable, Sequence
from copy import copy
from typing import (
    Annotated,
    Any,
    ClassVar,
    Generic,
    Literal,
    Self,
    Type,
    TypeVar,
)

from typing_extensions import TypedDict

from .config import Configurable, ConfigurableMeta, ConfigWrapper
from .database.expressions import ExecutableOption, Select
from .database.sessions import AsyncSession, async_session_manager
from .database.utils import build_query
from .expressions import Filter, Sort, Symbol
from .patterns import WILDCARD, RegexPattern, parse_selection
from .schema import core as core_schema
from .schema.core import (
    CoreSchema,
    GetCoreSchemaHandler,
    SerializationInfo,
    ValidationError,
)
from .schema.fields import ConfigField
from .schema.types import TypeAdapter
from .typing import (
    Deferred,
    classproperty,
    is_annotated,
    is_resource,
    isbaseclass_lenient,
    issubclass_lenient,
)
from .utils import get_meta_namespaces, get_meta_orig_bases

if typing.TYPE_CHECKING:
    from .resources import BaseResource, ResourceType
    from .specs import BaseSpec

_T = TypeVar('_T', bound='BaseResource | BaseSpec')

__all__ = (
    'BaseSelector',
    'SelectorConfig',
    'SelectorMeta',
    'SelectorType',
    'Key',
    'KeyList',
)


SelectorType = Type['BaseSelector[BaseResource]']
"""A type alias for a selector class."""


# MARK: Selector Configuration

class SelectorConfig(ConfigWrapper):
    """A selector configuration."""
    if typing.TYPE_CHECKING:
        __config_owner__: type['BaseSelector[Any]'] = \
            ConfigField(frozen=True, init=False)

    type_: str = ConfigField(default='selector', frozen=True, init=False)
    """The configuration owner type set to ``selector``. It is a protected
    field that is typically used with `check_config` to validate an object type
    without using `isinstance` in order to avoid circular imports."""

    collection: bool | None = ConfigField(default=None, frozen=True)
    """Whether the selection should return a collection or a single instance
    of the underlying resource class. Defaults to ``None``."""


# MARK: Selector Metaclass

class SelectorMeta(ABCMeta, ConfigurableMeta):
    """A metaclass for selector classes."""
    if typing.TYPE_CHECKING:
        __config__: SelectorConfig

    def __new__(
        mcls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        /,
        **kwargs: Any,
    ) -> type:
        """Create a new selector class."""
        # Create the selector class with default configuration
        namespace.setdefault('__config_resource__', None)
        cls = super().__new__(mcls, name, bases, namespace, **kwargs)

        # Return the class directly if it is the base or a key selector class
        # and skip the resource assignment as it should be done using generic
        # arguments within type annotations for inheriting selectors.
        if isbaseclass_lenient(cls, ('BaseSelector', 'Key', 'KeyList')):
            return cls

        # Collect the selector resources from the bases and original bases
        # found within the class namespace and the provided bases.
        resources = cls.collect_resources(bases, namespace)

        # Check if there is at least one selector resource found
        if not resources:
            raise TypeError(
                f"Selector class {cls.__name__!r} must implement or inherit "
                f"a valid resource class to be used as a selector."
            )

        # Check if all resources found are compatible
        resource = resources[0]
        for resource_other in resources[1:]:
            if not issubclass(resource, resource_other):
                raise TypeError(
                    f"All base selector classes must implement compatible "
                    f"resource classes. Got a mismatch between {resource!r} "
                    f"and {resource_other!r}."
                )

        setattr(cls, '__config_resource__', resource)
        return cls

    def collect_resources(
        cls, bases: tuple[type, ...], namespace: dict[str, Any], /,
    ) -> list['ResourceType']:
        """Collect selector resources from the given objects.

        It collects the selector resources from the given bases and namespace
        by extracting the selector resource type from the original bases
        annotation if it is a generic subclass of the base selector class or
        metaclass, and from the resource configuration attribute if present in
        the class and bases namespace.

        Args:
            bases: The class bases.
            namespace: The class namespace.

        Returns:
            A list of selector resource classes found in the given objects.
        """
        resources: list['ResourceType'] = []

        # The collection process is done in two steps to ensure that the
        # resource configuration attribute is extracted from the annotation
        # first, and then from the class and bases namespace.

        # Extract the selector resource class from the annotation if it is a
        # generic subclass of the selector class.
        meta_bases = get_meta_orig_bases(bases, namespace)
        for meta_base in meta_bases:
            origin = typing.get_origin(meta_base)
            if origin is None:
                continue
            if not isbaseclass_lenient(origin, 'BaseSelector'):
                continue
            resource, update = cls.parse_annotation(meta_base)
            if not update:
                if resource is not None:
                    resources.append(resource)
                break
            raise TypeError(
                f"Invalid resource class for resource selector "
                f"{meta_base.__qualname__!r}. The resource class cannot have "
                f"additional metadata update when used with the base selector "
                f"class. Got: {update}."
            )

        # Extract the selector resource class from the resource configuration
        # attribute if present in the class and bases namespace.
        meta_namespaces = get_meta_namespaces(bases, namespace)
        for meta_namespace in meta_namespaces:
            if '__config_resource__' not in meta_namespace:
                continue
            resource = meta_namespace['__config_resource__']
            if resource is None:
                continue
            if is_resource(resource):
                resources.append(resource)
                continue
            raise TypeError(
                f"Invalid selector resource class found in the class and "
                f"bases namespace of {cls.__qualname__!r}. Got: {resource!r}."
            )

        return resources

    @staticmethod
    def parse_annotation(
        annotation: Any
    ) -> tuple['ResourceType | None', dict[str, Any]]:
        """Parse resource and metadata update from a selector annotation."""
        # Extract annotation selector
        annotation_selector = typing.get_origin(annotation)
        if not issubclass(annotation_selector, BaseSelector):
            raise TypeError(
                f"Invalid annotation type for resource selector. "
                f"Got: {annotation!r}. "
            )

        # Extract annotation argument
        annotation_args = typing.get_args(annotation)
        if len(annotation_args) != 1:
            raise TypeError(
                f"Invalid annotation argument for resource selector. "
                f"Got: {annotation!r}. "
            )
        annotation_arg = annotation_args[0]

        # Parse annotation argument
        if is_annotated(annotation_arg):
            annotation_resource, *annotation_metadata = \
                typing.get_args(annotation_arg)
        else:
            annotation_resource = annotation_arg
            annotation_metadata = []

        # Validate annotation resource
        if isinstance(annotation_resource, TypeVar):
            annotation_resource = None
        elif not is_resource(annotation_resource):
            raise TypeError(
                f"Invalid selector resource class found in the annotation "
                f"{annotation!r}. The resource class must be a subclass of "
                f"`BaseResource` class. Got: {annotation_resource}."
            )

        # Validate annotation metadata update
        annotation_update = {}
        for update in annotation_metadata:
            if update is None:
                continue
            elif isinstance(update, str):
                annotation_update[update] = Deferred
            elif isinstance(update, dict):
                annotation_update.update(update)
            else:
                raise TypeError(
                    f"Invalid metadata update type for resource selector "
                    f"{annotation.__qualname__!r}. The metadata update must "
                    f"be either a string or a dictionary. Got: {update}."
                )

        return annotation_resource, annotation_update


# MARK: Base Selector

class BaseSelector(
    dict[str, Any],
    Configurable[SelectorConfig],
    Generic[_T],
    metaclass=SelectorMeta,
):
    """A base selector class to uniquely identify resource instances.

    This class is used as a type annotation to define a resource selector for
    a specific resource class. It is used as a proxy of the `dict` type to
    represent selection assignments for a specific resource type.

    It can be inherited by applying a concrete selector resource class as a
    generic argument to the base selector class.

    Note:
        The route auto-generation system will use this type hint to generate
        if needed the correct path parameter for the resource selector in the
        API routes.
    """
    if typing.TYPE_CHECKING:
        __config__: ClassVar[SelectorConfig]
        __config_resource__ : type[_T] | None

    def __new__(cls, *args: Any, **kwargs: Any) -> Self:
        """Create a new selector instance."""
        # Check if class is directly instantiated
        if cls is BaseSelector:
            raise TypeError(
                "Plateforme base selector cannot be directly instantiated."
            )
        return super().__new__(cls)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize a new selector.

        It initializes a new resource selector with the provided assignment
        arguments and keyword arguments. The selector represents a dictionary
        of aliases and their associated values that identify resource
        instances.

        To validate the selector against a resource class, the `validate`
        method should be called with a specific resource and collection instead
        of directly initializing the selector.

        Args:
            *args: The provided selector assignments as a list of string
                arguments with the following format ``alias=value`` optionally
                separated by semicolons. If an argument is not of string type,
                it is assigned to the wildcard entry ``*``.
            **kwargs: The provided selector assignments as a dictionary of
                assignment values with the aliases as keys.

        Note:
            Only one wildcard entry ``*`` is allowed within the selector
            assignments. The wildcard entry is used to match any field alias in
            a resource selector. If the wildcard entry is provided, it will
            be matched against the selectors of the resource when specified to
            determine the correct field alias.

            A selector assignment value can be `Deferred` to represent an
            entry that should be inferred when initializing a resource
            instance. Those entries can be filtered out when collecting the
            selector assignment entries using the scope ``'set'``.
        """
        # Collect all selector assignments from the given arguments
        for arg in args:
            # Parse selector
            if isinstance(arg, str):
                separator = r'[' + Symbol.STATEMENT + r']'
                selector = parse_selection(arg, separator=separator)
            else:
                selector = {WILDCARD: arg}
            # Validate assignments
            for alias, value in selector.items():
                if alias in self:
                    raise KeyError(
                        f"Duplicate selector assignment aliases found for "
                        f"{alias}` from argument `{arg!r}."
                    )
                self[alias] = value

        # Collect all selector assignments from the given keyword arguments
        for alias, value in kwargs.items():
            # Validate assignment alias
            alias = alias.lower()
            if not re.match(RegexPattern.ALIAS, alias):
                raise ValueError(
                    f"Invalid selector assignment alias {alias!r} found in "
                    f"keyword argument '{alias}={value}'. Aliases must match "
                    f"a specific pattern `ALIAS` defined in the framework's "
                    f"regular expressions repository."
                )
            # Validate assignment value
            if alias in self:
                raise KeyError(
                    f"Duplicate selector assignment aliases found for "
                    f"{alias!r} from keyword argument '{alias}={value}'."
                )
            self[alias] = value

    @classproperty
    def config(cls) -> SelectorConfig:
        """The selector configuration."""
        return cls.__config__

    @property
    def resource(self) -> type[_T]:
        """The resource associated with the selector.

        It is used to validate the selection assignments against this resource
        class and to generate the correct path parameter for the resource
        selector in the API routes.
        """
        if self.__config_resource__ is None:
            raise TypeError(
                f"No valid resource found for the selector instance "
                f"{self.__class__.__qualname__!r}."
            )
        return self.__config_resource__

    def build_query(
        self,
        *,
        filter_criteria: Filter | None = None,
        sort_criteria: Sort | None = None,
        options: Sequence[ExecutableOption] | None = None,
        raise_errors: bool = True,
    ) -> Select[tuple[_T]]:
        """Build a query for the selector.

        Recursively builds a query for the selector by performing a join
        operation on the resource relationships found in the selector and
        filters the query based on the selector assignments. Optionally, the
        function can apply additional filter and sort criteria to the query.

        Args:
            filter_criteria: The filter criteria to apply to the query.
                Defaults to ``None``.
            sort_criteria: The sort criteria to apply to the query.
                Defaults to ``None``.
            options: The options to apply to the query.
                Defaults to ``None``.
            raise_errors: Whether to raise errors when invalid attributes or
                values are found in the selector assignments.
                Defaults to ``True``.

        Returns:
            The built selector query with the applied filter and sort criteria.
        """
        return build_query(
            self.resource,
            selection=self,
            filter_criteria=filter_criteria,
            sort_criteria=sort_criteria,
            raise_errors=raise_errors,
            options=options,
        )

    def copy(self) -> Self:
        """Return a shallow copy of the selector."""
        return copy(self)

    def entries(
        self, *, scope: Literal['all', 'deferred', 'set'] = 'all',
    ) -> dict[str, Any]:
        """Return the selector assignments.

        It returns the assignments dictionary based on the specified scope.

        Args:
            scope: The scope of the selector assignments to return. It can be
                either ``'all'`` to return all selector assignments entries,
                ``'deferred'`` to return all deferred assignments entries, or
                ``'set'`` to return only the assignments entries that have
                been explicitly set. Defaults to ``'all'``.

        Returns:
            A dictionary containing the selector assignments entries based on
            the specified scope.
        """
        if scope == 'deferred':
            return {k: v for k, v in self.items() if v is Deferred}
        elif scope == 'set':
            return {k: v for k, v in self.items() if v is not Deferred}
        else:
            return {k: v for k, v in self.items()}

    async def resolve(
        self,
        __session: AsyncSession | None = None,
        *,
        limit: int | None = None,
        options: Sequence[ExecutableOption] | None = None,
    ) -> Sequence[_T] | _T:
        """Resolve the selector.

        It resolves the selector against the associated resource class and
        returns the matching resource instances. If the selector is not
        associated with a collection, it returns a single resource instance.

        Args:
            __session: The async session to use for the operation. If not
                provided, the session in the current context is used.
                Defaults to ``None``.
            limit: The maximum number of resource instances to return. If not
                provided, all matching resource instances are returned.
                Defaults to ``None``.
            options: The options to apply to the query.
                Defaults to ``None``.

        Returns:
            The resolved resource instances or single instance.

        Note:
            This method is similar to the resource manager `get_one` and
            `get_many` database operations, enforcing at least one matching
            resource instance for the latter.
        """
        async def query(session: AsyncSession) -> Sequence[_T] | _T:
            query = self.build_query(options=options)

            # Handle collection
            if self.config.collection:
                if limit is not None:
                    query = query.limit(limit)
                buffer = await session.execute(query)
                result = buffer.unique().scalars().all()
                if len(result) == 0:
                    raise ValueError(
                        f"Expected at least one resource instance matching "
                        f"the provided selector. Got no instance with "
                        f"selector: {self!r}."
                    )
                return result

            # Handle single instance
            buffer = await session.execute(query.limit(2))
            result = buffer.unique().scalars().all()
            if len(result) != 1:
                raise ValueError(
                    f"Expected exactly one resource instance matching the "
                    f"provided selector. Got {len(result)} instances with "
                    f"selector: {self!r}."
                )
            return result[0]

        if __session:
            return await query(__session)
        async with async_session_manager(on_missing='raise') as session:
            return await query(session)

    async def resolve_lenient(
        self,
        __session: AsyncSession | None = None,
        *,
        limit: int | None = None,
        options: Sequence[ExecutableOption] | None = None,
    ) -> Sequence[_T] | _T | None:
        """Resolve the selector.

        It resolves the selector in a lenient way against the associated
        resource class and returns the matching resource instances. If the
        selector is not associated with a collection, it returns a single
        resource instance.

        Args:
            __session: The async session to use for the operation. If not
                provided, the session in the current context is used.
                Defaults to ``None``.
            limit: The maximum number of resource instances to return. If not
                provided, all matching resource instances are returned.
                Defaults to ``None``.
            options: The options to apply to the query.
                Defaults to ``None``.

        Returns:
            The resolved resource instances or single instance.

        Note:
            This method is similar to the resource manager `get` and `get_many`
            database operations.
        """
        async def query(session: AsyncSession) -> Sequence[_T] | _T | None:
            query = self.build_query(options=options)

            # Handle collection
            if self.config.collection:
                if limit is not None:
                    query = query.limit(limit)
                buffer = await session.execute(query)
                return buffer.unique().scalars().all()

            # Handle single instance
            buffer = await session.execute(query.limit(1))
            return buffer.scalar()

        if __session:
            return await query(__session)
        async with async_session_manager(on_missing='raise') as session:
            return await query(session)

    @classmethod
    def create(cls, resource: type[_T]) -> type[Self]:
        """Create a new selector class for the given resource.

        It constructs a new selector class for the provided resource class and
        set the `__config_resource__` attribute to the resource class.

        Args:
            resource: The resource class to create the selector for.

        Returns:
            The new selector class for the given resource.
        """
        name = cls.__name__
        bases = (cls,)
        namespace = {
            '__module__': __name__,
            '__config_resource__': resource,
        }

        return type(name, bases, namespace)

    @classmethod
    def create_type_adapter(
        cls,
        alias: str,
        *,
        resource: type[_T] | None = None,
    ) -> TypeAdapter[Any]:
        """Create a type adapter for the given alias.

        Args:
            alias: The resource alias to create the type adapter for.
            resource: The resource associated with the selector. If not
                provided, the resource is retrieved from the selector
                class when available. Defaults to ``None``.

        Returns:
            The type adapter for the given alias.
        """
        resource = cls.validate_resource(resource)
        annotation_type = None
        for field in resource.resource_fields.values():
            if field.alias == alias:
                if field.rel_attribute is not None:
                    assert isinstance(field.target, type)
                    annotation_type = Key[
                        Annotated[field.target, field.alias]  # type: ignore
                    ]
                else:
                    annotation_type = field.annotation
                break

        if annotation_type is None:
            raise TypeError(
                f"Invalid alias {alias!r} found when creating a type adapter "
                f"for the resource selector {cls.__qualname__!r}. The alias "
                f"does not match any of the resource field aliases."
            )

        return TypeAdapter(annotation_type)

    @typing.overload
    @classmethod
    def serialize(
        cls,
        obj: dict[str, Any],
        info: SerializationInfo | None = None,
        *,
        mode: Literal['json'],
        scope: Literal['all', 'deferred', 'set'] = 'all',
    ) -> str:
        ...

    @typing.overload
    @classmethod
    def serialize(
        cls,
        obj: dict[str, Any],
        info: SerializationInfo | None = None,
        *,
        mode: Literal['python'] | None = None,
        scope: Literal['all', 'deferred', 'set'] = 'all',
    ) -> dict[str, Any]:
        ...

    @classmethod
    def serialize(
        cls,
        obj: dict[str, Any],
        info: SerializationInfo | None = None,
        *,
        mode: Literal['json', 'python'] | None = None,
        scope: Literal['all', 'deferred', 'set'] = 'all',
    ) -> dict[str, Any] | str:
        """Serialize the selector to a string or a dictionary.

        Args:
            obj: The selector to serialize.
            info: Additional information to pass to the serializer.
                Defaults to ``None``.
            mode: The mode in which the serializer should run:
                - If mode is ``json``, the output is a string that can be
                    used as a resource field reference.
                - If mode is ``python``, the output is a dictionary that
                    can be used to represent the selector object.
                Defaults to ``None`` which resolves to ``python`` if no mode
                is provided in the info.
            scope: The scope of the serialization to perform. It can be either
                ``'all'`` to process all selector assignments entries,
                ``'deferred'`` to process all deferred assignments entries, or
                ``'set'`` to process only the assignments entries that have
                been explicitly set. Defaults to ``'all'``.

        Returns:
            The serialized selector as a string if the serialization mode is
            set to ``json``, otherwise as a dictionary.
        """
        assert isinstance(obj, dict)

        mode = mode or (info and info.mode) or 'python'  # type: ignore

        # Validate scope
        if scope != 'all':
            if not isinstance(obj, cls):
                raise TypeError(
                    f"Invalid selector object found when serializing the "
                    f"selector {cls.__qualname__!r}. The object must be an "
                    f"instance of the selector class when specifying a scope. "
                    f"Got: {obj!r} with scope {scope!r}."
                )
            obj = obj.entries(scope=scope)

        # Serialize selector
        if mode == 'json':
            return ';'.join(
                f'{k}={"?" if v is Deferred else v}'
                for k, v in obj.items()
            )
        else:
            return obj.copy()

    @classmethod
    def validate(
        cls,
        obj: Any,
        *,
        resource: type[_T] | None = None,
        update: dict[str, Any] | None = None,
        validate_assignment: bool | None = None,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> Self:
        """Validate the given object against the selector.

        Args:
            obj: The object to validate.
            resource: The resource associated with the selector. If not
                provided, the resource is retrieved from the selector class.
                Defaults to ``None``.
            update: Values to add/modify within the selector assignments.
                Defaults to ``None``.
            validate_assignment: Whether to validate assignments against the
                resource. Defaults to ``None``.
            strict: Whether to enforce strict validation. Defaults to ``None``.
            context: The context to use for validation. Defaults to ``None``.

        Raises:
            ValidationError: If the object could not be validated.

        Returns:
            A validated selector instance.
        """
        resource = cls.validate_resource(resource)

        # Check validation settings
        if not validate_assignment and (strict or context):
            raise ValueError(
                f"Cannot set `strict` or `context` when assignment validation "
                f"is set to `False`. Got strict={strict} and "
                f"context={context}."
            )

        update = update or {}

        # Create a new selector instance
        if isinstance(obj, dict):
            self = cls(**{**obj, **update})
        else:
            self = cls(obj, **update)

        # Validate aliases and assignments
        setattr(self, '__config_resource__', resource)
        wildcard = self.validate_aliases(strict=strict, context=context)
        if validate_assignment:
            self.validate_assignments(
                strict=strict,
                context=context,
                exclude={wildcard} if wildcard else None,
            )

        return self

    @classmethod
    def validate_resource(cls, resource: type[_T] | None = None) -> type[_T]:
        """Validate a resource against the selector.

        It validates the provided resource against the selector configuration
        resource class. If no resource is provided, it retrieves the resource
        from the selector class configuration if available. Otherwise, it
        raises an error if no resource is found.

        Args:
            resource: The resource to validate. If not provided, the resource
                is retrieved from the selector class configuration if
                available. Defaults to ``None``.

        Returns:
            The validated resource class.

        Raises:
            TypeError: If the resource type is invalid for the selector.
        """
        # Retrieve resource from the selector configuration if not provided
        if resource is None:
            if cls.__config_resource__ is None:
                raise TypeError(
                    f"No resource found for the validation of the resource "
                    f"selector {cls.__qualname__!r}. Please provide a valid "
                    f"resource for the validation."
                )
            resource = cls.__config_resource__

        # Validate the resource type against the selector configuration
        if cls.__config_resource__ is not None \
                and not issubclass(resource, cls.__config_resource__):
            raise TypeError(
                f"Invalid resource type for resource selector "
                f"{cls.__qualname__!r}. The provided resource type must be a "
                f"subclass of the selector configuration resource type. Got "
                f"{resource!r} and expected a subclass of "
                f"{cls.__config_resource__!r}."
            )

        return resource

    def validate_aliases(
        self,
        *,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> str | None:
        """Validate the selector aliases against the resource.

        Args:
            strict: Whether to enforce strict validation. Defaults to ``None``.
            context: The context to use for validation. Defaults to ``None``.

        Returns:
            The wildcard selector resolved alias if found.

        Raises:
            ValidationError: If any alias is invalid.
        """
        # Return for collection selectors with no wildcard
        if self.config.collection and WILDCARD not in self:
            return None

        class SelectorMatch(TypedDict):
            aliases: set[str]
            wildcard: str | None

        # Collect all potential matching selectors
        selectors: list[SelectorMatch] = []
        selectors_check: list[SelectorMatch] = [
            SelectorMatch(aliases=aliases, wildcard=None)
            for aliases in self.resource.resource_identifiers
        ]

        # Filter out selectors that do not match the provided aliases
        selectors_check.sort(key=lambda s: len(s['aliases']), reverse=True)
        for selector in selectors_check:
            # Loop through the selector aliases and append if matched
            remaining = [*selector['aliases']]
            for alias in selector['aliases']:
                if alias in self:
                    remaining.remove(alias)
                elif selector['wildcard'] is None and WILDCARD in self:
                    selector['wildcard'] = alias
                    remaining.remove(alias)
            # Append selector if all aliases are matched
            if len(remaining) == 0:
                selectors.append(selector)

        # Check if at least one matching selector is found
        if len(selectors) == 0:
            raise ValueError(
                f"Invalid resource selector {self!r} for resource class "
                f"{self.resource.__qualname__!r}. No valid resource selectors "
                f"matches the provided aliases."
            )

        # Skip if no wildcard selector assignment is found
        if WILDCARD not in self:
            return None
        value = self.pop(WILDCARD)

        # Validate wildcard selector assignment against resource
        for selector in selectors:
            wildcard = selector['wildcard']
            assert wildcard is not None
            validator = self.create_type_adapter(
                wildcard, resource=self.resource
            )
            try:
                self[wildcard] = validator.validate_python(
                    value, strict=strict, context=context
                )
                return wildcard
            except ValidationError:
                pass

        raise ValueError(
            f"Invalid resource selector {self!r} for resource class "
            f"{self.resource.__qualname__!r}. The type of the wildcard "
            f"selector assignment value {value!r} does not match any of the "
            f"following field aliases: "
            f"{', '.join(str(i['wildcard']) for i in selectors)}."
        )

    def validate_assignments(
        self,
        *,
        strict: bool | None = None,
        context: dict[str, Any] | None = None,
        include: Iterable[str] | None = None,
        exclude: Iterable[str] | None = None,
    ) -> None:
        """Validate the selector assignments against the resource.

        Args:
            strict: Whether to enforce strict validation. Defaults to ``None``.
            context: The context to use for validation. Defaults to ``None``.
            include: The aliases to include in the validation. If not provided,
                all aliases are included. Defaults to ``None``.
            exclude: The aliases to exclude from the validation. If not
                provided, no aliases are excluded. Defaults to ``None``.

        Raises:
            ValidationError: If any assignment is invalid.
        """
        for alias, value in self.items():
            if include is not None and alias not in include:
                continue
            if exclude is not None and alias in exclude:
                continue
            validator = self.create_type_adapter(alias, resource=self.resource)
            try:
                self[alias] = validator.validate_python(
                    value, strict=strict, context=context
                )
            except ValidationError as error:
                raise ValueError(
                    f"Invalid resource selector {self!r} for resource class "
                    f"{self.resource.__qualname__!r}. The selector assignment "
                    f"value {value!r} does not match the expected type for "
                    f"the field {alias!r}."
                ) from error

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        __source: type[Any],
        __handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        # Retrieve resource and metadata update from the selector generic
        # argument if the source is a key or key list selector.
        resource = None
        update = None
        if isbaseclass_lenient(
            __source, ('Key', 'KeyList'), allow_generic=True
        ):
            resource, update = cls.parse_annotation(__source)
            if cls.__config_resource__ is not None \
                    and resource is not None \
                    and not issubclass(resource, cls.__config_resource__):
                raise TypeError(
                    f"Invalid resource class for resource selector "
                    f"{cls.__qualname__!r}. The annotation resource class "
                    f"must be a subclass of the selector configuration "
                    f"resource class. Got: {resource!r} and expected a "
                    f"subclass of {cls.__config_resource__!r}."
                )

        # Handle key validation
        def validate_key(obj: Any) -> Any:
            return cls.validate(
                obj,
                resource=resource,  # type: ignore[arg-type]
                update=update,
                validate_assignment=True,
            )

        # Build key schema
        def build_key_schema(mode: Literal['any', 'inline']) -> CoreSchema:
            # Build json schema
            json_schema = core_schema.no_info_after_validator_function(
                validate_key,
                core_schema.any_schema()
                    if mode == 'any'
                    else core_schema.union_schema([
                        core_schema.int_schema(),
                        core_schema.str_schema(),
                    ]),
            )

            # Build python schema
            python_schema = core_schema.union_schema(
                [
                    core_schema.is_instance_schema(cls),
                    json_schema,
                ],
                strict=True,
                custom_error_type='string_type',
            )

            return core_schema.json_or_python_schema(
                json_schema,
                python_schema,
                serialization=core_schema.plain_serializer_function_ser_schema(
                    cls.serialize,
                    info_arg=True,
                ),
            )

        # Handle annotation source
        if issubclass_lenient(__source, cls, allow_generic=True):
            return build_key_schema(mode='any')
        else:
            if cls.config.collection:
                raise TypeError(
                    f"A collection resource selector {cls.__qualname__!r} "
                    f"cannot be used as a schema field type."
                )
            source_schema = __handler(__source)
            return core_schema.union_schema([
                source_schema,
                build_key_schema(mode='inline'),
            ])

    @classmethod
    def __get_sqlalchemy_data_type__(cls, **kwargs: Any) -> None:
        raise TypeError(
            f"A resource selector {cls.__qualname__!r} cannot be used as a "
            f"SQLAlchemy data type."
        )

    def __repr_source__(self) -> str | None:
        resource = self.__config_resource__
        if resource is None:
            return None
        if self.config.collection:
            return f'{resource.__qualname__}[]'
        return resource.__qualname__

    def __repr__(self) -> str:
        repr_name =  self.__class__.__name__
        repr_source = self.__repr_source__()
        repr_str = self.serialize(self, mode='json')
        if repr_source:
            return f'{repr_name}[{repr_source}]({repr_str})'
        return f'{repr_name}({repr_str})'

    def __str__(self) -> str:
        return self.serialize(self, mode='json')


#  MARK: Key Selectors

@typing.final
class Key(BaseSelector[_T], Generic[_T]):
    """A resource key to uniquely identify a resource instance.

    This class is used as type annotation to define a resource key for a
    specific resource class. It must be used with a generic argument to specify
    the resource class associated with the underlying key within annotations,
    or it should be directly instantiated with the `validate` method by
    providing a resource class as an argument.

    Note:
        The route auto-generation system will use this type hint to generate
        if needed the correct path parameter for the resource selector in the
        API routes.

        This class if final and is not meant to be inherited. Use the base
        selector class instead to create custom selector classes.
    """

    __config__ = SelectorConfig(collection=False)

    async def resolve(
        self,
        __session: AsyncSession | None = None,
        *,
        options: Sequence[ExecutableOption] | None = None,
        **kwargs: Any,
    ) -> _T:
        """Resolve the key."""
        result = await super().resolve(__session, options=options)
        assert not isinstance(result, Sequence)
        return result

    async def resolve_lenient(
        self,
        __session: AsyncSession | None = None,
        *,
        options: Sequence[ExecutableOption] | None = None,
        **kwargs: Any,
    ) -> _T | None:
        """Resolve the key in a lenient way."""
        result = await super().resolve_lenient(__session, options=options)
        assert result is None or not isinstance(result, Sequence)
        return result

    def __repr_source__(self) -> str | None:
        resource = self.__config_resource__
        if resource is None:
            return None
        return resource.__qualname__


@typing.final
class KeyList(BaseSelector[_T], Generic[_T]):
    """A resource key list to identify a list of resource instances.

    This class is used as type annotation to define a resource key list for a
    specific resource class. It must be used with a generic argument to specify
    the resource class associated with the underlying key within annotations,
    or it should be directly instantiated with the `validate` method by
    providing a resource class as an argument.

    Note:
        The route auto-generation system will use this type hint to generate
        if needed the correct path parameter for the resource selector in the
        API routes.

        This class if final and is not meant to be inherited. Use the base
        selector class instead to create custom selector classes.
    """

    __config__ = SelectorConfig(collection=True)

    async def resolve(
        self,
        __session: AsyncSession | None = None,
        *,
        limit: int | None = None,
        options: Sequence[ExecutableOption] | None = None,
        **kwargs: Any,
    ) -> Sequence[_T]:
        """Resolve the key list."""
        result = await super().resolve(__session, limit=limit, options=options)
        assert isinstance(result, Sequence)
        return result

    async def resolve_lenient(
        self,
        __session: AsyncSession | None = None,
        *,
        limit: int | None = None,
        options: Sequence[ExecutableOption] | None = None,
        **kwargs: Any,
    ) -> Sequence[_T]:
        """Resolve the key list in a lenient way."""
        result = await super().resolve_lenient(
            __session, limit=limit, options=options
        )
        assert isinstance(result, Sequence)
        return result

    def __repr_source__(self) -> str | None:
        resource = self.__config_resource__
        if resource is None:
            return None
        return resource.__qualname__
