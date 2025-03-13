# plateforme.core.proxy
# ---------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module implements the `Proxy` and `CollectionProxy` classes for attribute
delegation to objects or callables. It enables creating wrappers with dynamic
redirection of attribute access.
"""

import typing
from collections.abc import Iterable, Iterator
from typing import Any, ClassVar, Generic, Protocol, TypeVar

from .config import Configurable, ConfigurableMeta, ConfigWrapper
from .patterns import match_any_pattern
from .schema.fields import ConfigField
from .typing import isbaseclass_lenient
from .utils import get_meta_orig_bases

MANAGED_ATTRS = (
    r'__call__',
    r'__config__',
    r'__init__',
    r'__new__',
    r'__proxy__',
    r'__proxy_getattr__',
    r'__proxy_info__',
    r'__proxy_target__',
    r'__proxy_type__',
)

_T = TypeVar('_T', bound=Any)

__all__ = (
    'Proxy',
    'ProxyConfig',
    'ProxyProtocol',
    'CollectionProxy',
)


# MARK: Proxy Configuration

class ProxyConfig(ConfigWrapper):
    """A selector configuration."""
    if typing.TYPE_CHECKING:
        __config_owner__: type['Proxy[Any] | CollectionProxy[Any]'] = \
            ConfigField(frozen=True, init=False)

    type_: str = ConfigField(default='proxy', frozen=True, init=False)
    """The configuration owner type set to ``proxy``. It is a protected field
    that is typically used with `check_config` to validate an object type
    without using `isinstance` in order to avoid circular imports."""

    read_only: bool | None = ConfigField(default=None, frozen=True)
    """Whether the proxy is read-only. Defaults to ``None``."""


# MARK: Proxy Protocol

class ProxyProtocol(Protocol):
    def __init__(self, target: Any, *args: Any, **kwargs: Any) -> None:
        """Initialize a new proxy instance.

        Args:
            target: The target object or callable to proxy to. If the target is
                a callable, it will be called to retrieve the actual target
                object. The target object can be any type.
        """
        ...

    def __proxy__(self) -> Any:
        """Return the proxy object computed from the target."""
        ...

    def __proxy_getattr__(self, name: str) -> Any:
        """Get the target object from the proxy instance.

        This should be used instead of the attribute `__getattr__` to avoid
        type checker errors.
        """
        ...


# MARK: Proxy Metaclass

class ProxyMeta(ConfigurableMeta):
    """A metaclass for proxy classes."""
    if typing.TYPE_CHECKING:
        __config__: ProxyConfig
        __proxy_type__: type[Any] | None

    def __new__(
        mcls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> type:
        """Create a new proxy class."""
        cls = super().__new__(mcls, name, bases, namespace, *args, **kwargs)

        # Collect the proxy target type from the original bases found within
        # the class namespace and the provided bases.
        proxy_type: type[Any] | None = None

        meta_bases = get_meta_orig_bases(bases, namespace)
        for meta_base in meta_bases:
            origin = typing.get_origin(meta_base)
            if origin is None:
                continue
            if not isbaseclass_lenient(origin, ('Proxy', 'CollectionProxy')):
                continue
            args = typing.get_args(meta_base)
            if len(args) == 1:
                if isinstance(args[0], TypeVar):
                    break
                if isinstance(args[0], type):
                    proxy_type = args[0]
                    break
            raise TypeError(
                f"Generic argument for the `Proxy` and `CollectionProxy` "
                f"classes must be a strict type. Got: {args}."
            )

        setattr(cls, '__proxy_type__', proxy_type)

        return cls

    # Hide attributes getter from type checkers to prevent MyPy from allowing
    # arbitrary attribute access instead of raising an error if the attribute
    # is not defined in the resource instance.
    if not typing.TYPE_CHECKING:
        def __getattr__(cls, name: str) -> Any:
            # Check for managed attributes
            if match_any_pattern(name, *MANAGED_ATTRS):
                raise AttributeError(
                    f"Cannot access attribute {name!r}. The attribute is "
                    f"managed by the proxy metaclass."
                )
            # Proxy attribute access to the target object
            proxy_type = object.__getattribute__(cls, '__proxy_type__')
            if proxy_type is None:
                raise AttributeError(
                    f"Cannot access attribute {name!r}. The proxy type is "
                    f"not defined."
                )
            return getattr(proxy_type, name)


# MARK: Proxies

class Proxy(Configurable[ProxyConfig], Generic[_T], metaclass=ProxyMeta):
    """A proxy for a single object.

    It delegates attribute access to a target proxied object.

    Attributes:
        __config__: The configuration class for the proxy.
        __proxy_info__: Additional information about the proxy target object.
        __proxy_target__: The proxy target object.
        __proxy_type__: The type of the proxy target object.
    """
    if typing.TYPE_CHECKING:
        __config__: ClassVar[ProxyConfig]
        __proxy_type__: ClassVar[type[Any] | None]

    def __init__(
        self, target: _T | None = None, *, info: Any | None = None
    ) -> None:
        """Initialize a new proxy instance with a target object."""
        self.__proxy_info__ = info
        self.__proxy_target__ = target

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Invoke the proxy target object."""
        return self.__proxy__()(*args, **kwargs)

    def __proxy__(self) -> _T:
        """Get the proxy target object."""
        if self.__proxy_target__ is None:
            raise AttributeError("The proxy target is not set.")
        return self.__proxy_target__

    def __proxy_getattr__(self, name: str) -> Any:
        """Get an attribute from the proxy target object.

        This should be used instead of the attribute `__getattr__` to avoid
        type checker errors.
        """
        return self.__getattr__(name)  # type: ignore[attr-defined]

    # Hide attributes getter from type checkers to prevent MyPy from allowing
    # arbitrary attribute access instead of raising an error if the attribute
    # is not defined in the resource instance.
    if not typing.TYPE_CHECKING:
        def __getattribute__(self, name: str) -> Any:
            # Check for managed attributes
            if match_any_pattern(name, *MANAGED_ATTRS):
                return object.__getattribute__(self, name)
            # Handle subclasses attribute overrides
            return super(Proxy, self).__getattribute__(name)

        def __getattr__(self, name: str) -> Any:
            # Check for managed attributes
            if match_any_pattern(name, *MANAGED_ATTRS):
                raise AttributeError(
                    f"Cannot access attribute {name!r}. The attribute is "
                    f"managed by the proxy class."
                )
            # Proxy attribute access to the target object
            proxy = object.__getattribute__(self, '__proxy__')
            if not callable(proxy):
                raise AttributeError(
                    f"Cannot access attribute {name!r}. The proxy target is "
                    f"not callable."
                )
            return getattr(proxy(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        # Check for managed attributes
        if match_any_pattern(name, *MANAGED_ATTRS):
            object.__setattr__(self, name, value)
            return
        # Proxy attribute access to the target object
        if self.__config__.read_only:
            raise AttributeError(
                f"Cannot set attribute {name!r}. The proxy is read-only."
            )
        setattr(self.__proxy__(), name, value)

    def __delattr__(self, name: str) -> None:
        # Check for managed attributes
        if match_any_pattern(name, *MANAGED_ATTRS):
            object.__delattr__(self, name)
            return
        # Proxy attribute access to the target object
        if self.__config__.read_only:
            raise AttributeError(
                f"Cannot delete attribute {name!r}. The proxy is read-only."
            )
        delattr(self.__proxy__(), name)

    def __repr__(self) -> str:
        return repr(self.__proxy__())

    def __str__(self) -> str:
        return str(self.__proxy__())


# MARK: Collection Proxy

class CollectionProxy(
    Configurable[ProxyConfig], Generic[_T], metaclass=ProxyMeta
):
    """A proxy for an iterable object.

    It delegates attribute access to a target proxied iterable object.

    Attributes:
        __config__: The configuration class for the proxy.
        __proxy_info__: Additional information about the proxy target object.
        __proxy_target__: The proxy target object.
        __proxy_type__: The type of the proxy target objects.
    """
    if typing.TYPE_CHECKING:
        __config__: ClassVar[ProxyConfig]
        __proxy_type__: ClassVar[type[Any] | None]

    def __init__(
        self, target: Iterable[_T] | None = None, *, info: Any | None = None
    ) -> None:
        """Initialize a new proxy instance with a target iterable object."""
        self.__proxy_info__ = info
        # Check that all items in the target iterable are of the same type and
        # that they all have the same attribute name.
        if target is None:
            self.__proxy_target__ = None
        else:
            target_type = self.__proxy_type__
            for item in target:
                if not target_type:
                    target_type = type(item)
                elif not isinstance(item, target_type):
                    raise TypeError(
                        f"Target items must all be of the same type. "
                        f"Expected {target_type.__name__!r}, got "
                        f"{type(item).__name__!r}."
                    )
            self.__proxy_target__ = list(target)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Invoke the proxy target iterable object."""
        return [item(*args, **kwargs) for item in self.__proxy__()]

    def __proxy__(self) -> list[_T]:
        """Get the proxy target iterable object."""
        if self.__proxy_target__ is None:
            raise AttributeError("The proxy target is not set.")
        return self.__proxy_target__

    def __proxy_getattr__(self, name: str) -> Any:
        """Get an attribute from the proxy target iterable object.

        This should be used instead of the attribute `__getattr__` to avoid
        type checker errors.
        """
        return self.__getattr__(name)  # type: ignore[attr-defined]

    # Hide attributes getter from type checkers to prevent MyPy from allowing
    # arbitrary attribute access instead of raising an error if the attribute
    # is not defined in the resource instance.
    if not typing.TYPE_CHECKING:
        def __getattribute__(self, name: str) -> Any:
            # Check for managed attributes
            if match_any_pattern(name, *MANAGED_ATTRS):
                return object.__getattribute__(self, name)
            # Handle subclasses attribute overrides
            return super(CollectionProxy, self).__getattribute__(name)

        def __getattr__(self, name: str) -> Any:
            # Check for managed attributes
            if match_any_pattern(name, *MANAGED_ATTRS):
                raise AttributeError(
                    f"Cannot access attribute {name!r}. The attribute is "
                    f"managed by the proxy class."
                )
            # Proxy attribute access to the target object
            proxy = object.__getattribute__(self, '__proxy__')
            if not callable(proxy):
                raise AttributeError(
                    f"Cannot access attribute {name!r}. The proxy target is "
                    f"not callable."
                )
            # Retrieve attribute from all proxy items
            proxy_items = []
            for item in proxy():
                proxy_items.append(getattr(item, name))
            # Return a callable that calls the attribute on all proxy items if
            # the attribute from proxy is callable.
            if proxy_items and callable(proxy_items[0]):
                def method(*args: Any, **kwargs: Any) -> Any:
                    return [item(*args, **kwargs) for item in proxy_items]
                return method
            return proxy_items

    def __setattr__(self, name: str, value: Any) -> None:
        # Check for managed attributes
        if match_any_pattern(name, *MANAGED_ATTRS):
            object.__setattr__(self, name, value)
            return
        # Proxy attribute access to the target object
        if self.__config__.read_only:
            raise AttributeError(
                f"Cannot set attribute {name!r}. The proxy is read-only."
            )
        for item in self.__proxy__():
            setattr(item, name, value)

    def __delattr__(self, name: str) -> None:
        # Check for managed attributes
        if match_any_pattern(name, *MANAGED_ATTRS):
            object.__delattr__(self, name)
            return
        # Proxy attribute access to the target object
        if self.__config__.read_only:
            raise AttributeError(
                f"Cannot delete attribute {name!r}. The proxy is read-only."
            )
        for item in self.__proxy__():
            delattr(item, name)

    def __getitem__(self, index: int) -> _T:
        proxy = self.__proxy__()
        return proxy[index]

    def __setitem__(self, index: int, value: _T) -> None:
        raise TypeError(
            f"Cannot set item {index!r}. The proxy is not mutable."
        )

    def __delitem__(self, index: int) -> None:
        raise TypeError(
            f"Cannot delete item {index!r}. The proxy is not mutable."
        )

    def __contains__(self, obj: object) -> bool:
        return obj in self.__proxy__()

    def __iter__(self) -> Iterator[_T]:
        yield from self.__proxy__()

    def __reversed__(self) -> Iterator[_T]:
        yield from reversed(self.__proxy__())

    def __len__(self) -> int:
        return len(self.__proxy__())

    def __repr__(self) -> str:
        return repr(self.__proxy__())

    def __str__(self) -> str:
        return str(self.__proxy__())
