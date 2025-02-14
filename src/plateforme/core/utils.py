# plateforme.core.utils
# ---------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utility functions for working with base and configuration
attributes within the Plateforme framework.
"""

import typing
from collections import deque
from collections.abc import Iterable
from itertools import islice
from typing import Any, Callable, Protocol, is_typeddict

_Sentinel = object()

__all__ = (
    'AttributeResolver',
    'check_config',
    'get_attribute_from_bases',
    'get_bases',
    'get_config',
    'get_meta_namespaces',
    'get_meta_orig_bases',
    'get_subclasses',
    'make_getattr_resolver',
    'mro',
    'mro_for_bases'
)


class AttributeResolver(Protocol):
    """Resolve an attribute on an object using a resolution strategy.

    If the attribute is not found on the object, the resolution strategy
    will check if the condition is met with the provided value. If the
    condition is met, the strategy will resolve the attribute on the
    fallback object.

    Args:
        obj: The object to resolve the attribute on.
        name: The attribute name to resolve.
        condition: The condition value to check if the fallback should be
            resolved. Defaults to ``None``.

    Returns:
        A tuple containing a boolean indicating if the attribute was resolved
        and the resolved value.
    """

    def __call__(
        self,
        obj: Any,
        name: str,
        *,
        condition: Any | None = None,
    ) -> tuple[bool, Any]:
        ...


def check_config(
    __type: Any, __lookup: bool = False, /, **kwargs: Any | set[Any]
) -> bool:
    """Check specific configuration values for a given type annotation.

    This function checks if the specified key-value pairs in `kwargs` match the
    configuration fetched from the type annotation `__type`. If configuration
    is not found directly on the type and `__lookup` is set to ``True``, the
    function supports recursive lookup through generic arguments.

    Args:
        __type: The type annotation from which to check the configuration.
        __lookup: Flag indicating whether to recursively look up the
            configuration in generic arguments if not found on `__type`.
            Defaults to ``False``.
        **kwargs: Key-value pairs to check against the fetched configuration.

    Returns:
        ``True`` if all specified key-value pairs match the configuration;
        ``False`` otherwise, including when the configuration is not found.

    Raises:
        ValueError: If no check key-value pairs are provided.
    """
    # Check for key-value pairs
    if not kwargs:
        raise ValueError(
            f"Expected at least one keyword argument to check configuration "
            f"for type {__type.__qualname__!r}."
        )

    # Fetch the configuration from the type annotation specified attribute
    config = get_config(__type, __lookup)
    if config is None:
        return False

    # Check the configuration key-value pairs
    for key, value in kwargs.items():
        if key not in config:
            return False
        if value is not None and not (
            config[key] in value
            if isinstance(value, set)
            else config[key] == value
        ):
            return False

    return True


def get_attribute_from_bases(
    type_: type[Any] | tuple[type[Any], ...], name: str
) -> Any:
    """Get the attribute from bases using the MRO.

    It retrieve the attribute from the next class in the MRO that has it,
    aiming to simulate calling the method on the actual class.

    The reason for iterating over the mro instead of just getting the attribute
    is to support `TypedDict`, which lacks a real `__mro__` method, but can
    have a virtual one constructed from its bases (as done here).

    Args:
        type_: The type or class to search for the attribute. If a tuple, this
            is treated as a set of base classes.
        name: The name of the attribute to retrieve.

    Returns:
        Any: The attribute value, if found.

    Raises:
        AttributeError: If the attribute is not found in any class in the MRO.
    """
    if isinstance(type_, tuple):
        for base in mro_for_bases(type_):
            attribute = base.__dict__.get(name, _Sentinel)
            if attribute is not _Sentinel:
                attribute_get = getattr(attribute, '__get__', None)
                if attribute_get is not None:
                    return attribute_get(None, type_)
                return attribute
        raise AttributeError(f'{name} not found in {type_}')
    else:
        try:
            return getattr(type_, name)
        except AttributeError:
            return get_attribute_from_bases(mro(type_), name)


def get_bases(type_: type[Any]) -> tuple[type[Any], ...]:
    """Get the base classes of a class or typed dictionary.

    Args:
        type_: The type or class to get the bases.

    Returns:
        The base classes.
    """
    if is_typeddict(type_):
        return type_.__orig_bases__  # type: ignore[no-any-return]
    try:
        return type_.__bases__
    except AttributeError:
        return ()


def get_config(
    __type: Any, __lookup: bool = False, /
) -> dict[str, Any] | None:
    """Retrieve the configuration from a given type annotation.

    This function fetches a configuration from the type annotation `__type`. If
    the configuration attribute is an instance of a `ConfigWrapper` class, its
    entries are returned. If it's a dictionary, the dictionary is returned
    directly. The function supports recursive lookup through generic arguments
    if the configuration is not found directly on the type and `__lookup` is
    set to ``True``.

    Args:
        __type: The type annotation from which to retrieve the configuration.
        __lookup: Flag indicating whether to recursively look up the
            configuration in generic arguments if not found on `__type`.
            Defaults to ``False``.

    Returns:
        A dictionary containing the configuration, or ``None`` if the
        configuration is not found or the attribute is not a `ConfigWrapper` or
        a dictionary instance.

    Raises:
        TypeError: If the configuration attribute is found but is neither a
            `ConfigWrapper` nor a dictionary instance.
    """
    # Fetch the configuration from the type annotation
    config = getattr(__type, '__config__', None)
    if callable(config):
        config = config()

    # Check for valid configuration types
    if hasattr(config, 'entries'):
        entries = getattr(config, 'entries')
        if callable(entries):
            config = entries()
    if isinstance(config, dict):
        return config
    if config is not None:
        raise TypeError(
            f"Type {__type.__qualname__!r} configuration must be a dictionary "
            f"or a configuration instance. Got: {type(config).__qualname__}."
        )

    # Recursively look up for a configuration in generic arguments
    if __lookup:
        args = typing.get_args(__type)
        for arg in args:
            config = get_config(arg)
            if config is not None:
                return config

    return None


def get_meta_namespaces(
    bases: tuple[type, ...],
    namespace: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Get the namespaces from the metaclass bases and namespace.

    Args:
        bases: A tuple of base classes.
        namespace: A class namespace.

    Returns:
        The metaclass namespaces.
    """
    objects: tuple[dict[str, Any], ...] = (namespace,)

    # Collect the namespaces from the bases
    for base in bases:
        if not hasattr(base, '__dict__'):
            continue
        objects += (dict(base.__dict__),)

    return tuple(objects)


def get_meta_orig_bases(
    bases: tuple[type, ...],
    namespace: dict[str, Any],
) -> tuple[type[Any], ...]:
    """Get the original base classes from the metaclass bases and namespace.

    Args:
        bases: A tuple of base classes.
        namespace: A class namespace.

    Returns:
        The metaclass original base classes.
    """
    objects: dict[type[Any], None] = {}

    # Collect the original bases from the namespace
    if '__orig_bases__' in namespace:
        orig_bases = dict.fromkeys(namespace['__orig_bases__'])
        objects.update(orig_bases)

    # Collect the original bases from the bases
    for base in bases:
        if not hasattr(base, '__orig_bases__'):
            continue
        orig_bases = dict.fromkeys(getattr(base, '__orig_bases__'))
        objects.update(orig_bases)

    return tuple(objects)


def get_subclasses(type_: type[Any]) -> tuple[type[Any], ...]:
    """Get recursively the subclasses of a class or typed dictionary.

    Args:
        type_: The type or class to get the subclasses.

    Returns:
        The subclasses.
    """
    try:
        return tuple(set(type_.__subclasses__()).union([
            sub for base in type_.__subclasses__()
            for sub in get_subclasses(base)
        ]))
    except AttributeError:
        return ()


def make_getattr_resolver(
    *,
    fallback_attr: str | None = None,
    fallback_condition: Callable[[Any], bool] | bool = False,
    fallback_transformer: Callable[[str], str] = lambda x: x
) -> AttributeResolver:
    """Create a resolution strategy for resolving attributes.

    If the attribute is not found on the object, the resolution strategy will
    check if the fallback condition is met. If the condition is met, the
    strategy will resolve the attribute on the fallback object. This is used by
    the `isimplclass_lenient` function to resolve attributes on objects.

    Args:
        fallback_attr: The attribute name to resolve on the fallback object.
            Defaults to ``None``.
        fallback_condition: The condition to check if the fallback should be
            resolved. If the condition is met, the strategy will resolve the
            attribute on the fallback object. Defaults to ``False``.
        fallback_transformer: The transformer function to apply to the
            attribute name before resolving it on the fallback object.
            Defaults to the identity function.

    Returns:
        A resolution strategy function that resolves attributes on the object.
        The function takes the object, a value to check the fallback condition,
        and the attribute name to resolve. The function returns a tuple
        containing a boolean indicating if the attribute was resolved and the
        resolved value.
    """
    def resolver(obj: Any, name: str, *, condition: Any | None = None) -> Any:
        if hasattr(obj, name):
            return True, getattr(obj, name)

        # Check if the fallback condition is met
        if callable(fallback_condition) and not fallback_condition(condition):
            return False, None
        elif not fallback_condition:
            return False, None

        # Resolve the fallback object
        resolved_obj = obj
        if fallback_attr is not None:
            if not hasattr(obj, fallback_attr):
                return False, None
            resolved_obj = getattr(obj, fallback_attr)

        # Resolve the fallback attribute name
        resolved_name = fallback_transformer(name)
        if resolved_name in resolved_obj:
            return True, resolved_obj[resolved_name]
        if hasattr(resolved_obj, resolved_name):
            return True, getattr(resolved_obj, resolved_name)

        return False, None

    return resolver


def mro(type_: type[Any]) -> tuple[type[Any], ...]:
    """Calculate the method resolution order (MRO) using the C3 algorithm.

    It tries to use the existing mro, for performance mainly but also because
    it helps verify the implementation below.

    Note:
        See https://www.python.org/download/releases/2.3/mro/
    """
    if not is_typeddict(type_):
        try:
            return type_.__mro__
        except AttributeError:
            # Generic alias and some other cases
            pass

    bases = get_bases(type_)
    return (type_,) + mro_for_bases(bases)


def mro_for_bases(bases: tuple[type[Any], ...]) -> tuple[type[Any], ...]:
    """Calculate the method resolution order (MRO) for a given set of base
    classes using the C3 linearization algorithm.

    This function computes the MRO by creating a list of method resolution
    orders for each base class, plus a single list containing the `bases`
    themselves, and then merging these lists into a single MRO list.

    Args:
        bases: A tuple of the base classes for which the MRO is to be
            calculated.

    Returns:
        A tuple representing the MRO of the provided bases.

    Raises:
        TypeError: If no consistent hierarchy can be found, implying that no
            valid C3 linearization exists.

    """
    def merge_seqs(seqs: list[deque[type[Any]]]) -> Iterable[type[Any]]:
        # Merge sequences according to the rules of the C3 linearization
        # algorithm. This helper function performs the merging operation of the
        # MRO sequences. It repeatedly selects the first candidate from the
        # non-empty sequences that is not in the tail of any other sequences.
        # If such a candidate cannot be found, it indicates that the sequences
        # do not form a consistent hierarchy, and an error is raised.
        while True:
            non_empty = [seq for seq in seqs if seq]
            if not non_empty:
                # Nothing left to process...
                return
            candidate: type[Any] | None = None
            # Find merge candidates among seq heads
            for seq in non_empty:
                candidate = seq[0]
                not_head = [
                    s for s in non_empty
                    if candidate in islice(s, 1, None)
                ]
                if not_head:
                    # Reject the candidate.
                    candidate = None
                else:
                    break
            if not candidate:
                raise TypeError(
                    'Inconsistent hierarchy, no C3 MRO is possible.'
                )
            yield candidate
            for seq in non_empty:
                # Remove candidate
                if seq[0] == candidate:
                    seq.popleft()

    seqs = [deque(mro(base)) for base in bases] + [deque(bases)]
    return tuple(merge_seqs(seqs))
