# plateforme.core.typing
# ----------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides extra utilities for managing typings within the Plateforme
framework.
"""

import dataclasses
import inspect
import re
import sys
import typing
import weakref
from asyncio import Future
from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from functools import cached_property
from types import (
    FunctionType,
    GenericAlias,
    GetSetDescriptorType,
    MethodType,
    NoneType,
    UnionType,
)
from typing import (
    Annotated,
    Any,
    Awaitable,
    Callable,
    Dict,
    Final,
    ForwardRef,
    Generic,
    List,
    Literal,
    NotRequired,
    Required,
    Self,
    Set,
    Tuple,
    TypeVar,
    Union,
)
from weakref import ReferenceType

from fastapi.datastructures import DefaultPlaceholder as _DefaultPlaceholder
from pydantic_core import PydanticUndefined, PydanticUndefinedType
from typing_extensions import TypeIs

from .modules import get_root_module_name, import_module
from .representations import Representation
from .utils import AttributeResolver, check_config, make_getattr_resolver

if typing.TYPE_CHECKING:
    from .config import Configurable
    from .proxy import ProxyProtocol
    from .resources import ResourceType
    from .schema.models import ModelType
    from .selectors import SelectorType

_CT = TypeVar('_CT')
_RT = TypeVar('_RT')
_T = TypeVar('_T')

__all__ = (
    'classproperty',
    'staticproperty',
    'Annotation',
    'CastFunc',
    'CastObject',
    'ClassMethodType',
    'Default',
    'DefaultPlaceholder',
    'DefaultType',
    'Deferred',
    'DeferredType',
    'FunctionLenientType',
    'Object',
    'PickleWeakRef',
    'StaticMethodType',
    'Undefined',
    'UndefinedType',
    'WithArgsTypes',
    'WithFunctionTypes',
    'add_module_globals',
    'eval_type_lenient',
    'eval_type_lenient_deep',
    'get_cls_hierarchy',
    'get_cls_type_hints_lenient',
    'get_cls_types_namespace',
    'get_object_name',
    'get_parent_frame_namespace',
    'get_value_or_default',
    'getmembers_static',
    'has_forwardref',
    'has_resource',
    'has_stub_noop',
    'is_abstract',
    'is_annotated',
    'is_async',
    'is_configurable',
    'is_endpoint',
    'is_exception',
    'is_finalvar',
    'is_iterable',
    'is_model',
    'is_optional',
    'is_private',
    'is_protocol',
    'is_proxy',
    'is_required',
    'is_resource',
    'is_selector',
    'is_union',
    'isbaseclass_lenient',
    'isfunction_lenient',
    'isimplclass_lenient',
    'issubclass_lenient',
)


CastFunc = Callable[[Any], Any]
"""A cast function type to cast a value to a specific data type."""


CastObject = Union[
    CastFunc,
    Dict[str, Any],
    List[CastFunc],
    Set[CastFunc],
    Tuple[CastFunc, ...],
]
"""A cast object type to cast a value to a specific data type."""


if typing.TYPE_CHECKING:
    ClassMethodType = classmethod[Any, Any, Any]
    """A type alias for class method types."""

    StaticMethodType = staticmethod[Any, Any]
    """A type alias for static method types."""

else:
    ClassMethodType = classmethod
    StaticMethodType = staticmethod


FunctionLenientType = Union[
    ClassMethodType, StaticMethodType, FunctionType, MethodType
]
"""A type alias for lenient function types including class and static methods,
and standard functions with any arguments."""


Object = TypeVar('Object', bound=object)
"""A type variable for any object class."""


WithArgsTypes = (GenericAlias, UnionType)
"""A type alias for types that can have arguments."""


WithFunctionTypes = (classmethod, staticmethod, FunctionType, MethodType)
"""A type alias for types that implement a function."""


# MARK: Properties

if typing.TYPE_CHECKING:
    class classproperty(Generic[_CT, _RT]):
        """A class property descriptor.

        It is a read-only property that can be accessed from the class itself.
        It is similar to a class method, but it is accessed as an attribute
        instead of a method.
        """
        def __init__(self, fget: Callable[[_CT], _RT]) -> None:
            ...

        def __get__(self, instance: Any, owner: Any, /) -> _RT:
            ...

else:
    class classproperty(property, Generic[_CT, _RT]):
        def __init__(self, fget: Callable[[type[_CT]], _RT]) -> None:
            self._fget = fget

        @property
        def fget(self) -> Callable[[type[_CT]], _RT]:  # type: ignore
            return self._fget

        def __get__(self, instance: _CT | None, owner: type[_CT], /) -> _RT:
            if isinstance(owner, type):
                return self.fget(owner)
            raise AttributeError('Cannot access class property from instance.')

        def __set__(self, instance: Any, value: Any, /) -> None:
            raise AttributeError('Cannot set class property.')

        def __delete__(self, instance: Any, /) -> None:
            raise AttributeError('Cannot delete class property.')


class staticproperty(property, Generic[_RT]):
    """A static property descriptor.

    It is a read-only property that can be accessed from the class itself. It
    is similar to a static method, but it is accessed as an attribute instead
    of a method.
    """
    def __init__(self, fget: Callable[..., _RT]) -> None:
            self._fget = fget

    @property
    def fget(self) -> Callable[..., _RT]:  # type: ignore
        return self._fget

    def __get__(self, instance: Any, owner: type | None = None, /) -> _RT:
        return self.fget()

    def __set__(self, instance: Any, value: Any, /) -> None:
        raise AttributeError('Cannot set static property.')

    def __delete__(self, instance: Any, /) -> None:
        raise AttributeError('Cannot delete static property.')


# MARK: Annotations

@dataclasses.dataclass(frozen=True, slots=True)
class Annotation(Representation):
    """An annotation.

    A data structure to hold information about a parsed annotation. It provides
    utilities to parse, serialize, and replace annotations.
    """

    annotation: Any
    """The original annotation provided to the parser."""

    optional: bool
    """Whether the annotation is an optional type."""

    origin: Any
    """The origin type of the annotation if one was applicable, otherwise
    ``None``. An origin type is a generic type that defines the behavior of the
    parsing process by extracting additional arguments information from the
    annotation. A list of generic types can be provided to the parser to
    restrict the origin type to one of the generic types or their subclasses.
    """

    args: tuple[Any, ...]
    """The content directly associated with the annotation or generic variadic
    arguments extracted from the annotation, stored as a tuple or a single
    value when only one argument is present."""

    metadata: tuple[Any, ...]
    """Additional metadata extracted from annotated types."""

    @property
    def content(self) -> Any:
        """The inner content of the annotation."""
        if len(self.args) == 1:
            return self.args[0]
        return self.args

    @staticmethod
    def parse_annotated(annotation: Any) -> tuple[Any, tuple[Any, ...]]:
        """Check if the given annotation is an annotated type and parse it."""
        if is_annotated(annotation):
            annotation_type, *annotation_metadata = typing.get_args(annotation)
            return annotation_type, tuple(annotation_metadata)
        return annotation, ()

    @staticmethod
    def parse_origin(
        annotation: Any, generics: Sequence[Any] | None = None
    ) -> tuple[Any, tuple[Any, ...]]:
        """Check if the given annotation has a generic origin and parse it."""
        origin = typing.get_origin(annotation)

        if origin is None:
            return None, (annotation,)
        if generics is not None and not any(
            origin is generic or issubclass_lenient(origin, generic)
            for generic in generics
        ):
            return None, (annotation,)

        args = typing.get_args(annotation)
        return origin, args

    @staticmethod
    def parse_optional(
        annotation: Any,
    ) -> tuple[bool, Any]:
        """Check if the given annotation is an optional type and parse it."""
        if is_optional(annotation):
            args = typing.get_args(annotation)
            return True, args[0]
        return False, annotation

    @classmethod
    def parse(
        cls,
        annotation: Any,
        generics: Sequence[Any] | None = None,
    ) -> Self:
        """Parse the given annotation.

        Args:
            annotation: The annotation to parse.
            *generics: Generic types to consider as valid origins for the
                annotation parsing. If provided, the origin of the annotation
                must match one of the generic types or be a subclass of one of
                the generic types.

        Returns:
            The parsed annotation.
        """
        # Parse annotation
        parsed, metadata = cls.parse_annotated(annotation)
        optional, parsed = cls.parse_optional(parsed)
        origin, args = cls.parse_origin(parsed, generics)

        return cls(
            annotation=annotation,
            optional=optional,
            origin=origin,
            args=args,
            metadata=metadata,
        )

    @classmethod
    def replace(
        cls,
        annotation: Any,
        _guard: frozenset[int] = frozenset(),
        *,
        test: Callable[[Any], bool | tuple[bool, Any]],
        resolver: Callable[[Any], Any] | Callable[[Any, Any], Any],
    ) -> Any:
        """Parse the annotation and replace recursively its content.

        It recursively replaces the content arguments of the annotation using
        the provided test and resolver functions. The test function checks if
        an argument should be replaced, and the resolver function replaces the
        argument if needed. The recursive guard is used to prevent infinite
        recursion by tracking the annotations that have already been replaced.

        Args:
            annotation: The annotation to parse and replace.
            _guard: The set of annotation ids to guard against recursion.
            test: The test function to check if an argument should be replaced.
            resolver: The resolver function to replace the argument.

        Returns:
            The serialized annotation with the replaced content.
        """
        # Guard against recursive annotations
        annotation_id = id(annotation)
        if annotation_id in _guard:
            return annotation

        # Test and resolve the annotation
        check = test(annotation)
        if isinstance(check, tuple):
            check, info = check
            if check:
                return resolver(annotation, info)  # type: ignore
        elif check:
            return resolver(annotation)  # type: ignore

        # Recursively replace the annotation
        parsed = cls.parse(annotation)
        parsed_args = tuple(
            cls.replace(
                arg,
                _guard | {annotation_id},
                test=test,
                resolver=resolver,
            )
            for arg in parsed.args
        )

        # Serialize the replaced annotation
        return cls.serialize(
            parsed_args if len(parsed_args) > 1 else parsed_args[0],
            optional=parsed.optional,
            origin=parsed.origin,
            metadata=parsed.metadata,
        )

    @classmethod
    def serialize(
        cls,
        content: Self | Any,
        *,
        optional: bool | None = None,
        origin: Any | None = None,
        metadata: tuple[Any, ...] | None = None,
    ) -> Any:
        """Serialize the provided annotation information."""
        # Validate annotation content
        if isinstance(content, Annotation):
            annotation = content.content
            origin = origin if origin is not None else content.origin
            optional = optional if optional is not None else content.optional
            metadata = metadata if metadata is not None else content.metadata
        else:
            annotation = content

        # Serialize the annotation
        if origin:
            if origin is UnionType:
                annotation = Union[annotation]
            else:
                annotation = origin[annotation]
        if optional:
            annotation = Union[annotation, NoneType]
        if metadata:
            annotation = Annotated[annotation, *metadata]
        return annotation


# MARK: Deferred Type

@typing.final
class DeferredType:
    """The deferred type."""
    instance: Self | None = None

    def __new__(cls) -> Self:
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self) -> None:
        from .schema import core as core_schema
        from .schema.core import SchemaSerializer, SerializationInfo

        cls = self.__class__

        def serialize(value: Any, info: SerializationInfo) -> Any:
            return '?' if info.mode == 'json' else value

        schema = core_schema.json_or_python_schema(
            json_schema=core_schema.no_info_after_validator_function(
                lambda _: cls(),
                core_schema.str_schema(pattern=r'^\?$'),
            ),
            python_schema=core_schema.is_instance_schema(cls),
            serialization=core_schema.plain_serializer_function_ser_schema(
                serialize,
                info_arg=True,
            ),
        )

        setattr(cls, '__pydantic_serializer__', SchemaSerializer(schema))

    def __copy__(self) -> Self:
        return self

    def __deepcopy__(self, memo: Any) -> Self:
        return self

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return 'Deferred'

    def __str__(self) -> str:
        return '?'


Deferred: Any = DeferredType()
"""The deferred singleton instance."""


# MARK: Undefined Type

UndefinedType = PydanticUndefinedType
"""The undefined type."""


Undefined: Any = PydanticUndefined
"""The undefined singleton instance."""


# MARK: Default Type

DefaultType = TypeVar('DefaultType')
"""A type variable for default values."""


@typing.final
class DefaultPlaceholder(_DefaultPlaceholder, Generic[DefaultType]):
    """A default placeholder.

    It's used internally to recognize when a default value has been
    overwritten, even if the overridden default value was truthy.
    """

    def __init__(self, value: DefaultType) -> None:
        self.value = value

    def __bool__(self) -> bool:
        return bool(self.value)

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, DefaultPlaceholder)
            and self.value == other.value
        )

    def __repr__(self) -> str:
        return f'Default({repr(self.value)})'

    def __str__(self) -> str:
        return str(self.value)


def Default(value: DefaultType = Undefined) -> DefaultType:
    """The default function.

    It's used internally to recognize when a default value has been
    overwritten, even if the overridden default value was truthy.
    """
    if isinstance(value, DefaultPlaceholder):
        return DefaultPlaceholder(value.value)  # type: ignore[return-value]
    return DefaultPlaceholder(value)  # type: ignore[return-value]


# MARK: Pickle Weak Reference

class PickleWeakRef:
    """Pickle-serializable weak reference.

    It is a wrapper for `weakref.ref` that enables ``pickle`` serialization.

    Cloudpickle fails to serialize `weakref.ref` objects due to an arcane error
    related to abstract base classes (`abc.ABC`). This class works around the
    issue by wrapping `weakref.ref` instead of subclassing it.

    See https://github.com/pydantic/pydantic/issues/6763 for context.

    Note:
        - If not pickled, behaves the same as a `weakref.ref`.
        - If pickled along with the referenced object, the same `weakref.ref`
            behavior will be maintained between them after unpickling.
        - If pickled without the referenced object, after unpickling the
            underlying reference will be cleared (``__call__`` will always
            return ``None``).
    """

    def __init__(self, obj: Any):
        if obj is None:
            # The object will be "None" upon deserialization if the serialized
            # weakref had lost its underlying object.
            self.value = None
        else:
            self.value = weakref.ref(obj)

    def __call__(self) -> Any:
        if self.value is None:
            return None
        else:
            return self.value()

    def __reduce__(self) -> tuple[
        Callable[..., Any], tuple[ReferenceType[Any] | None]
    ]:
        return PickleWeakRef, (self(),)

    @staticmethod
    def build_dict(
        dictionary: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """Build a lenient weak value dictionary.

        It takes an input dictionary, and produces a new value that invertibly
        replaces the values with weakrefs. The `unpack_dict` function can be
        used to reverse this operation.

        Note:
            We can't just use a `weakref.WeakValueDictionary` because many
            types (including `int`, `str`, etc.) can't be stored as values in a
            weak value dictionary.
        """
        if dictionary is None:
            return None
        result = {}
        for key, value in dictionary.items():
            try:
                proxy = PickleWeakRef(value)
            except TypeError:
                proxy = value
            result[key] = proxy
        return result

    @staticmethod
    def unpack_dict(
        dictionary: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        """Unpacks a lenient weak value dictionary.

        It inverts the transform performed by the `build_dict` function.
        """
        if dictionary is None:
            return None

        result = {}
        for key, value in dictionary.items():
            if isinstance(value, PickleWeakRef):
                value = value()
                if value is not None:
                    result[key] = value
            else:
                result[key] = value
        return result


# MARK: Utilities

def add_module_globals(
    obj: Any, globalns: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Add the globals of the module where the given object is defined."""
    module_name = getattr(obj, '__module__', None)
    if module_name:
        try:
            module = import_module(module_name)
            module_globalns = module.__dict__
        except KeyError:
            # Leniently ignore if the module is not found
            pass
        else:
            if globalns:
                return {**module_globalns, **globalns}
            else:
                # Copy module globals to make sure it can't be updated later
                return module_globalns.copy()

    return globalns or {}


def eval_type_lenient(
    annotation: Any,
    globalns: dict[str, Any] | None = None,
    localns: Mapping[str, Any] | None = None,
    *,
    fallback: bool = False,
    fallback_module: str | None = None,
) -> Any:
    """Evaluate a type annotation.

    It is a lenient version of `typing._eval_type` that will not error out if a
    forward reference is not resolvable. In addition, it provides an optional
    fallback mechanism when evaluation fails where it attempts to evaluate
    forward references by:
    1.  Resolving the forward reference's fully qualified name using the
        provided fallback module.
    2.  Importing the object from the resolved fully qualified name.

    Args:
        annotation: The annotation to evaluate.
        globalns: The globals namespace to use for evaluation.
        localns: The locals namespace to use for evaluation.
        fallback: Whether to attempt to evaluate forward references using the
            fallback mechanism when evaluation fails. Defaults to ``False``.
        fallback_module: The module to use for the fallback mechanism when
            evaluating forward references. Defaults to ``None``.

    Returns:
        The evaluated annotation.
    """
    try:
        return typing._eval_type(  # type: ignore[attr-defined]
            annotation, globalns, localns
        )
    except NameError:
        pass

    # Attempt to evaluate forward references using the fallback mechanism
    if fallback and isinstance(annotation, ForwardRef):
        from .modules import import_object, resolve_forwardref_fullname

        if fallback_module is None:
            fallback_localns = localns or {}
            fallback_module = \
                fallback_localns.get('__name__', get_root_module_name())
        assert fallback_module is not None
        forwardref = resolve_forwardref_fullname(fallback_module, annotation)
        if forwardref is None:
            return annotation

        try:
            return import_object(forwardref)
        except (AttributeError, ImportError):
            pass

    return annotation


def eval_type_lenient_deep(
    annotation: Any,
    globalns: dict[str, Any] | None = None,
    localns: Mapping[str, Any] | None = None,
    _origin: Any | None = None,
) -> Any:
    """Evaluate a type annotation recursively.

    It recursively checks for forward references in the annotation and attempts
    to evaluate them using the provided globals and locals dictionaries. If a
    forward reference cannot be evaluated directly, either the forward argument
    is a generic annotation where the generic origin is evaluated with its
    arguments recursively, or it returns the forward reference itself (e.g.
    ``'list[MyForwardRef]'`` would results in ``list['MyForwardRef']``).

    Args:
        annotation: The annotation to evaluate.
        globalns: The globals namespace to use for evaluation.
        localns: The locals namespace to use for evaluation.
        _origin: The recursive origin of the annotation. This argument is used
            internally to handle generic aliases and should not be provided by
            the user.

    Returns:
        The evaluated annotation.
    """
    # Create a union type from a list of annotation parts
    def create_union(annotation_parts: list[Any]) -> Any:
        if len(annotation_parts) == 1:
            return annotation_parts[0]
        return Union[tuple(annotation_parts)]

    # Extracts the union arguments from a string annotation using the pipe `|`
    # character as a separator.
    def extract_union(annotation: str) -> list[str]:
        pattern = r'[^\s\|\[]+(?:\[[^\]]*\])?'
        return re.findall(pattern, annotation)

    # Extracts the origin and arguments parts from a string annotation. For a
    # standard annotation, the origin is the annotation itself and the
    # arguments are an empty list. For a generic annotation, the origin is the
    # annotation up to the first `[` character and the arguments are the
    # annotation within the brackets.
    def extract_annotation(annotation: str) -> tuple[str, list[str]]:
        pattern = r'^([^\[]+)(?:\[([^\]]+)\])?$'
        match = re.match(pattern, annotation)
        if match:
            match_origin: str = match.group(1)
            match_args: str = match.group(2)
            return (
                match_origin,
                [arg.strip() for arg in match_args.split(',')]
                if match_args else [],
            )
        else:
            raise TypeError(
                f"Could not extract origin and arguments from annotation "
                f"{annotation!r}. Please make sure the annotation is a valid "
                f"standard or generic string annotation."
            )

    # Check for forward references
    if isinstance(annotation, ForwardRef):
        annotation = annotation.__forward_arg__

    # Evaluate string annotations for generic aliases
    if isinstance(annotation, str) and (
        _origin is None or isinstance(_origin[None], GenericAlias)
    ):
        try:
            return eval_type_lenient_deep(
                eval(annotation, globalns, localns),
                globalns,
                localns,
            )
        except TypeError as error:
            raise TypeError(
                f"Could not evaluate annotation {annotation!r}. Please make "
                f"sure the annotation is a valid Python expression. "
            ) from error
        except NameError:
            pass

        # Extract annotation parts
        annotation_parts: list[Any] = []
        union_args = extract_union(annotation)
        for union_arg in union_args:
            ann_origin, ann_args = extract_annotation(union_arg)

            # Handle generic annotations
            if ann_args:
                generic_origin = eval_type_lenient_deep(
                    ann_origin, globalns, localns
                )
                generic_args = tuple(
                    eval_type_lenient_deep(
                        arg, globalns, localns, generic_origin
                    )
                    for arg in ann_args
                )
                annotation_parts.append(generic_origin[*generic_args])

            # Handle standard annotations
            else:
                try:
                    annotation_parts.append(
                        eval(ann_origin, globalns, localns)
                    )
                except TypeError as error:
                    raise TypeError(
                        f"Could not evaluate annotation {annotation!r}. "
                        f"Please make sure the annotation is a valid Python "
                        f"expression."
                    ) from error
                except NameError:
                    annotation_parts.append(ForwardRef(ann_origin))

        # Return annotation
        if len(annotation_parts) == 1:
            return annotation_parts[0]
        return create_union(annotation_parts)

    # Otherwise retrieve origin and resolve arguments recursively
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin and args:
        resolved_args = [
            eval_type_lenient_deep(arg, globalns, localns, origin)
            for arg in args
        ]
        if origin is UnionType:  # PEP-604 syntax (e.g. list | str)
            return create_union(resolved_args)
        return origin[*resolved_args]

    return annotation


def get_cls_hierarchy(cls: type[Any]) -> dict[str, type[Any]]:
    """Get the class hierarchy by traversing its qualified name path.

    This function builds a mapping of each class qualified name relative to the
    root class in the hierarchy to its corresponding class object, starting
    from the root class and including all nested classes. It traverses the
    hierarchy using the class's qualified name nd module location.

    Args:
        cls: The class to analyze. Must be a type with a `__qualname__` and
            `__module__` attribute.

    Returns:
        A dictionary mapping class qualified name relative to the root class to
        their corresponding class objects.

    Raises:
        TypeError: If any class in the hierarchy cannot be found in its
            expected location within the module.

    Example:
        >>> class Root:
        ...     class Nested:
        ...         class DeeplyNested:
        ...             pass
        >>> hierarchy = get_cls_hierarchy(Root.Inner)
        >>> hierarchy
        {
            '': <class Root>,
            'Nested': <class Root.Nested>,
            'Nested.DeeplyNested': <class Root.Nested.DeeplyNested>,
        }
    """
    module = import_module(cls.__module__)

    try:
        hierarchy: dict[str, type[Any]] = {}

        index = 0
        qualname = ''
        obj = module
        remaining = deque(cls.__qualname__.split('.'))

        # Traverse the class hierarchy path
        while remaining:
            name = remaining.popleft()
            obj = getattr(obj, name)
            if index > 0:
                qualname = f'{qualname}.{name}'.lstrip('.')
            index += 1

            hierarchy[qualname] = obj  # type: ignore

    except AttributeError as error:
        if index == 0:
            return {'': cls}
        raise TypeError(
            f"Unable to navigate to the class hierarchy for {cls!r}."
        ) from error

    return hierarchy


def get_cls_type_hints_lenient(
    cls: type[Any],
    globalns: dict[str, Any] | None = None,
    localns: Mapping[str, Any] | None = None,
    *,
    include_extras: bool = False,
) -> dict[str, Any]:
    """Return type hints for a class.

    It is a lenient version of `typing.get_type_hints` that will not error out
    if a forward reference is not resolvable. It collects annotations from the
    class MRO, including those from parent classes.
    """
    if getattr(cls, '__no_type_check__', None):
        return {}
    if isinstance(cls, type):
        hints = {}
        for base in reversed(cls.__mro__):
            if globalns is None:
                base_module = sys.modules.get(base.__module__, None)
                base_globals = getattr(base_module, '__dict__', {})
            else:
                base_globals = globalns
            ann = base.__dict__.get('__annotations__', {})
            if isinstance(ann, GetSetDescriptorType):
                ann = {}
            base_locals = dict(vars(base)) if localns is None else localns
            if localns is None and globalns is None:
                base_globals, base_locals = base_locals, base_globals
            for name, value in ann.items():
                if value is None:
                    value = type(None)
                if isinstance(value, str):
                    value = ForwardRef(value, is_argument=False, is_class=True)
                value = eval_type_lenient(value, base_globals, base_locals)
                hints[name] = value
        return (
            hints if include_extras
            else {
                k: typing._strip_annotations(t)  # type: ignore[attr-defined]
                for k, t in hints.items()
            }
        )
    raise TypeError(f"Expected a class, got {cls!r}.")


def get_cls_types_namespace(
    cls: type[Any], parent_namespace: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Return the namespace of a class with its type as a key."""
    namespace = add_module_globals(cls, parent_namespace)
    namespace[cls.__name__] = cls
    return namespace


def get_object_name(
    obj: Any,
    *,
    fullname: bool = False,
    handler: Callable[[str], str] = lambda x: x,
) -> str:
    """Retrieve the name of an object.

    It retrieves the name of the object, including the module name and the
    qualified name if the `fullname` argument is set to ``True``. The `handler`
    argument can be used to format the name of the object before returning it.

    Args:
        obj: The object to retrieve the name from.
        fullname: Whether to retrieve the full name of the object.
            Defaults to ``False``.
        handler: A handler to format the name of the object before returning
            it. Defaults to a lambda function that returns the name as is.

    Returns:
        The name of the object.

    Raises:
        ValueError: If the name of the object could not be resolved.
    """
    # Handle modules and strings directly
    if inspect.ismodule(obj):
        return handler(obj.__name__)
    if isinstance(obj, str):
        return handler(obj)

    # Retrieve the wrapped object if applicable
    if isinstance(obj, property):
        obj = obj.fget
    elif not inspect.isroutine(obj) and not isinstance(obj, type):
        obj = type(obj)

    # Retrieve the name of the object
    try:
        if fullname:
            return handler('%s.%s' % (obj.__module__, obj.__qualname__))
        else:
            return handler(obj.__name__)
    except AttributeError as error:
        raise ValueError(
            f"Failed to retrieve the name of the object {obj!r}."
        ) from error


def get_parent_frame_namespace(
    *,
    depth: int = 2,
    mode: Literal['globals', 'locals'] = 'locals',
) -> dict[str, Any] | None:
    """Get the namespace of the parent frame.

    It allows the use of items in parent namespace to get around the issue with
    `typing.get_type_hints` only looking in the global module namespace.

    See https://github.com/pydantic/pydantic/issues/2678 for context.

    Args:
        depth: The depth of the parent frame to retrieve the namespace from.
            Defaults to ``2``.
        mode: The mode to retrieve the namespace from. It can be either
            ``'globals'`` or ``'locals'``. Defaults to ``'locals'``.

    Note:
        The specific location where this is called is important. By default,
        this function will build a namespace from the parent of where it is
        called.
    """
    frame = sys._getframe(depth)
    # Check if the frame is the global module namespace
    if frame.f_back is None:
        return None

    if mode == 'globals':
        return frame.f_globals
    else:
        return frame.f_locals


def get_value_or_default(
    first_arg: DefaultType | DefaultPlaceholder[DefaultType],
    *extra_args: DefaultType | DefaultPlaceholder[DefaultType],
) -> DefaultType:
    """Get the first non-default value from the given arguments; if all are
    default, return the first argument."""
    def is_default_placeholder(
        value: DefaultType | DefaultPlaceholder[DefaultType]
    ) -> TypeIs[DefaultPlaceholder[DefaultType]]:
        return isinstance(value, DefaultPlaceholder)

    args = (first_arg,) + extra_args
    for arg in args:
        if arg is not Undefined and not is_default_placeholder(arg):
            return arg
    if is_default_placeholder(first_arg):
        return first_arg.value  # type: ignore[no-any-return]
    raise ValueError('All arguments are undefined.')


def getmembers_static(
    obj: Any, predicate: Callable[[Any], bool] | None = None
) -> list[tuple[str, Any]]:
    from inspect import _getmembers  # type: ignore[attr-defined]

    def getter(obj: Any, key: str) -> Any:
        # Raise an attribute error to force the underlying "_getmembers"
        # method to resolve the attribute from a base classe's dictionary.
        raise AttributeError()

    return _getmembers(obj, predicate, getter)  # type: ignore[no-any-return]


def has_forwardref(annotation: Any, _origin: Any | None = None) -> bool:
    """Check if the given annotation contains a forward reference.

    Args:
        annotation: The annotation to check.
        _origin: The recursive parent origin of the annotation. This argument
            is used internally to handle generic aliases and should not be
            provided by the user.

    Returns:
        Whether the annotation contains a forward reference.
    """
    if isinstance(annotation, str) and (
        _origin is None or isinstance(_origin[None], GenericAlias)
    ):
        return True
    if isinstance(annotation, ForwardRef):
        return True
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin and args:
        for arg in args:
            if has_forwardref(arg, origin):
                return True
    return False


def has_resource(annotation: Any) -> bool:
    """Check if the given annotation contains a resource type."""
    return check_config(annotation, True, type_='resource')


def has_stub_noop(obj: Any) -> bool:
    """Check if the given object has a final stub no-operation statement."""
    try:
        # Retrieve object source
        source = inspect.getsource(obj)
        lines = [line for line in source.split('\n') if line]

        # Check if the object has a final no-operation statement
        if not lines:
            return True
        indent = len(lines[0]) - len(lines[0].lstrip()) + 4
        if re.match(r'^class\s.+:\s*(?:\.{3}|pass)$', lines[0].strip()):
            return True
        if re.match(rf'^\s{{{indent}}}(?:\.{{3}}|pass)$', lines[-1].rstrip()):
            return True
        return False

    except (TypeError, OSError):
        return False


def is_abstract(obj: Any) -> bool:
    """Check if the given object is abstract."""
    if hasattr(obj, '__dict__'):
        try:
            return bool(obj.__dict__.get('__abstract__', False))
        except:
            pass
    return False


def is_annotated(annotation: Any) -> bool:
    """Check if the given annotation is an annotated type."""
    origin = typing.get_origin(annotation)
    return origin is not None and issubclass_lenient(origin, Annotated)


def is_async(obj: Any) -> TypeIs[Awaitable[Any]]:
    """Check if the given object is an asynchronous function or coroutine."""
    if isinstance(obj, Future):
        return True
    if inspect.iscoroutine(obj) or inspect.iscoroutinefunction(obj):
        return True
    if hasattr(obj, '__wrapped__'):
        return is_async(obj.__wrapped__)
    return False


def is_async_function(obj: Any) -> TypeIs[Awaitable[Any]]:
    """Check if the given object is an asynchronous function or coroutine."""
    return inspect.iscoroutine(obj) or isinstance(obj, Future)


def is_configurable(obj: Any) -> TypeIs['Configurable[Any]']:
    return hasattr(obj, '__config__')


def is_endpoint(obj: Any) -> TypeIs[Callable[..., Any]]:
    """Check if the given object is an endpoint."""
    return hasattr(obj, '__config_route__')


def is_exception(obj: Any) -> TypeIs[BaseException | Exception]:
    """Check if the given object is an exception."""
    return isinstance(obj, (BaseException, Exception))


def is_finalvar(annotation: Any) -> bool:
    """Check if the given annotation is a final type."""

    def _check_finalvar(v: Any) -> bool:
        if v is None:
            return False
        return v.__class__ == Final.__class__  \
            and getattr(v, '_name', None) == 'Final'

    return _check_finalvar(annotation) \
        or _check_finalvar(typing.get_origin(annotation))


def is_iterable(annotation: Any) -> TypeIs[Iterable[Any]]:
    """Check if the given annotation is an iterable type."""
    origin = typing.get_origin(annotation)
    return origin is not None and issubclass_lenient(origin, Iterable)


def is_model(obj: Any) -> TypeIs['ModelType']:
    """Check if the given object is a model type."""
    if not isinstance(obj, type):
        return False
    if check_config(obj, type_='model'):
        return True
    return False


def is_optional(annotation: Any) -> bool:
    """Check if the given annotation is an optional type."""
    args = typing.get_args(annotation)
    if NoneType in args:
        return True
    return False


def is_private(prop: cached_property[Any] | property) -> bool:
    """Check if the given property is private."""
    name: str = ''

    if isinstance(prop, property):
        name = getattr(prop.fget, '__name__', '')
    elif isinstance(prop, cached_property):
        name = getattr(prop.func, '__name__', '')

    return name.startswith('_') and not name.startswith('__')


def is_protocol(obj: Any) -> bool:
    """Check if the given object is a protocol."""
    if not isinstance(obj, type):
        return False
    if getattr(obj, '_is_protocol', False):
        return True
    if getattr(obj, '_is_runtime_protocol', False):
        return True
    return False


def is_proxy(obj: Any) -> TypeIs['ProxyProtocol']:
    """Check if the given object is a proxy."""
    if isinstance(obj, type) and hasattr(obj, '__proxy_type__'):
        return True
    if isinstance(obj, object) and hasattr(obj, '__proxy__'):
        return hasattr(obj, '__proxy__')
    return False


def is_required(annotation: Any, total: bool = True) -> bool:
    """Check if the given annotation is a required type."""
    if is_annotated(annotation):
        origin = typing.get_origin(typing.get_args(annotation)[0])
    else:
        origin = typing.get_origin(annotation)

    # If total flag is true (see typed dictionaries), we consider the
    # annotation as required if and only if its origin is not "NotRequired".
    # Otherwise, we consider the annotation as required if and only if its
    # origin is "Required".
    return  origin is not NotRequired if total else origin is Required


def is_resource(obj: Any) -> TypeIs['ResourceType']:
    """Check if the given object is a resource type."""
    if not isinstance(obj, type):
        return False
    if check_config(obj, type_='resource'):
        return True
    return False


def is_selector(obj: Any) -> TypeIs['SelectorType']:
    """Check if the given object is a selector type."""
    if not isinstance(obj, type):
        return False
    if check_config(obj, type_='selector'):
        return True
    return False


def is_union(annotation: Any) -> bool:
    """Check if the given annotation is a union type."""
    origin = typing.get_origin(annotation)
    return origin is not None and issubclass_lenient(origin, Union)


def isbaseclass_lenient(
    cls: Any,
    name_or_tuple: str | tuple[str, ...],
    *,
    allow_generic: bool = False,
) -> bool:
    """Check if the given class is of the given type names.

    It checks the provided class type against the given type names. It first
    checks if the given type names can be resolved in the parent namespace. If
    not, it checks if the class module and name match the type.

    Args:
        cls: The class type to check.
        name_or_tuple: The type names to check for.
        allow_generic: Whether to allow generic aliases. Defaults to ``False``.

    Returns:
        Whether the object is of the given type names.
    """
    # Validate class type
    if isinstance(cls, WithArgsTypes):
        if isinstance(cls, UnionType) or not allow_generic:
            return False
        origin = typing.get_origin(cls)
        if origin is None:
            raise TypeError(f"Could not infer the class type. Got: {cls!r}.")
        cls = origin

    # Resolve parent namespace and module
    parent_namespace = get_parent_frame_namespace(mode='globals')
    if parent_namespace is None:
        raise ValueError("Could not resolve the parent namespace.")
    parent_module = parent_namespace.get('__name__')

    # Helper function to check if the class matches the given type name
    def check(name: str) -> bool:
        # Check if the class matches the resolved type
        if name in parent_namespace:
            return cls is parent_namespace[name]
        # Otherwise, check if the class module and name match the type name
        cls_module = getattr(cls, '__module__',)
        if hasattr(cls, '__qualname__'):
            cls_name = cls.__qualname__
        elif hasattr(cls, '__name__'):
            cls_name = cls.__name__
        else:
            raise TypeError(f"Could not infer the class name. Got: {cls!r}.")
        return bool(cls_module == parent_module and cls_name == name)

    # Perform the check for the given type names
    if isinstance(name_or_tuple, str):
        return check(name_or_tuple)
    return any(check(name) for name in name_or_tuple)


def isfunction_lenient(obj: Any) -> bool:
    """Check if the given object is a function, method or property."""
    return isinstance(obj, (
        classmethod, staticmethod, FunctionType, MethodType
    ))


def isimplclass_lenient(
    obj: Any,
    spec: Any,
    _guard: frozenset[int] = frozenset(),
    *,
    max_depth: int = 2,
    predicate: Callable[[Any], bool] | None = None,
    resolver: AttributeResolver | None = None,
) -> bool:
    """Check if a given object implements the provided specification.

    The function will check if the object implements the provided specification
    by comparing the attributes and methods of the object.

    Args:
        obj: The object to check for implementation.
        spec: The specification to check against.
        _guard: The set of recursive guard object ids to prevent infinite
            recursion. Defaults to an empty set.
        max_depth: The maximum depth to check for recursive class
            implementations. Defaults to ``2``.
        predicate: The predicate function to filter the attributes and methods
            of the object. The function should take an attribute or method and
            return a boolean indicating if the attribute should be included in
            the check. Defaults to ``None``.
        resolver: The resolution strategy to use with an optional fallback
            logic if the attribute is not found on the object. The strategy
            should be a callable that takes the object, the attribute name to
            resolve, and an optional value to check the fallback condition. The
            function should return a tuple containing a boolean indicating if
            the attribute was resolved and the resolved value. See the
            `make_getattr_resolver` function for creating a resolution
            strategy. Defaults to ``None``.

    Returns:
        Whether the object implements the provided specification.
    """
    # Retrieve the resolution strategy
    if resolver is None:
        resolver = make_getattr_resolver()

    # Validate attributes
    obj_types = get_cls_type_hints_lenient(obj)
    spec_types = get_cls_type_hints_lenient(spec)
    for name in spec_types:
        if name not in obj_types \
                and not resolver(obj, name, condition=spec_types[name]):
            return False

    # Validate class and methods
    for name in dir(spec):
        # Skip dunder and private class and methods
        if name.startswith('_'):
            continue

        spec_value = getattr(spec, name)

        # Skip class and methods not matching the predicate
        if predicate is not None and not predicate(spec_value):
            continue

        # Skip deprecated attributes
        if hasattr(spec_value, '__deprecated__'):
            continue

        resolved, obj_value = resolver(obj, name, condition=spec_value)

        if not resolved:
            return False
        if inspect.isclass(spec_value):
            if not inspect.isclass(obj_value):
                return False
            # Check for recursive class implementations
            spec_id = id(spec_value)
            if spec_id in _guard:
                continue
            if len(_guard) >= max_depth - 1:
                continue
            if not isimplclass_lenient(
                obj_value,
                spec_value,
                _guard | {spec_id},
                predicate=predicate,
                max_depth=max_depth,
                resolver=resolver,
            ):
                return False
        elif callable(spec_value) and not callable(obj_value):
            return False

    return True


def issubclass_lenient(
    cls: Any,
    class_or_tuple: Any,
    *,
    allow_generic: bool = False,
) -> bool:
    """Check if the given class is a subclass of the given class or tuple.

    It is a lenient version of `issubclass` that will not error out if the
    first argument is not a class.

    Args:
        cls: The class type to check.
        name_or_tuple: The types to check for.
        allow_generic: Whether to allow generic aliases. Defaults to ``False``.

    Returns:
        Whether the object is of the given types.
    """
    # Validate class type
    if isinstance(cls, WithArgsTypes):
        if isinstance(cls, UnionType) or not allow_generic:
            return False
        origin = typing.get_origin(cls)
        if origin is None:
            raise TypeError(f"Could not infer the class type. Got: {cls!r}.")
        cls = origin

    # Perform the check for the given types
    return isinstance(cls, type) and issubclass(cls, class_or_tuple)
