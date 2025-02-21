# plateforme.core.managers
# ------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for manager classes used in packages and
resources within the Plateforme framework.
"""

import typing
from collections.abc import Iterable, Iterator, Mapping
from typing import Any, Callable, Generic, Literal, TypeVar

__all__ = (
    'Managed',
    'Manager',
)


Managed = TypeVar('Managed', bound='Any')
"""A type variable for a managed instance or type."""


class Manager(Iterable[str], Generic[Managed]):
    """An instance or type manager.

    It provides a common interface to access and manage the service methods
    associated with an instance or type, including the endpoints and helper
    methods.

    Attributes:
        __config_managed__: The managed instance or type associated with the
            manager.
    """
    if typing.TYPE_CHECKING:
        __config_managed__: Managed | type[Managed]

    def __init__(self, managed: Managed | type[Managed]) -> None:
        """Initialize a new manager instance."""
        self.__config_managed__ = managed

    def _add_method(self, name: str, method: Callable[..., Any]) -> None:
        """Add a method to the manager.

        Args:
            name: The name of the method to add.
            method: The method to add to the manager.

        Raises:
            AttributeError: If the method already exists within the manager of
                the managed instance or type, or if the method is private.
        """
        # Check if method already exists
        if name in self.__dict__:
            raise AttributeError(
                f"Method {name!r} already exists within the manager of "
                f"{str(self.__config_managed__)!r}."
            )
        # Check if method is private
        if name.startswith('_'):
            raise AttributeError(
                f"Method {name!r} must be public and cannot start with an "
                f"underscore for manager of {str(self.__config_managed__)!r}."
            )
        self.__dict__[name] = method

    def _collect_methods(
        self,
        *,
        owner: Any | None = None,
        scope: Literal['endpoint', 'helper', 'all'] = 'all',
        config: Mapping[str, Any] | None = None,
    ) -> dict[str, Callable[..., Any]]:
        """Collect all methods from the manager.

        It collects methods from the manager and returns them as a dictionary
        with the method name as the key and the callable method as the value.
        A scope can be provided to filter the methods collected.

        Args:
            owner: The owner of the methods to collect. It can be set to a
                specific instance or type to collect only methods that belong
                to the owner. Defaults to ``None``.
            scope: The scope of the methods to collect. It can be set either to
                ``endpoint`` to collect only methods marked as endpoints, i.e.
                methods with the `__config_route__` attribute, or ``helper``
                to collect only internal methods, or ``all`` to collect all
                methods. Defaults to ``all``.
            config: The configuration to use for the methods collection. It can
                be used to filter methods based on the configuration attributes
                of the methods. Defaults to ``None``.

        Returns:
            A dictionary of methods from the manager.
        """
        from .services import validate_service_method

        methods: dict[str, Callable[..., Any]] = {}

        for name, method in self.__dict__.items():
            if not callable(method):
                continue
            # Check scope
            method_scopes = {'all'}
            if hasattr(method, '__config_route__'):
                method_scopes.add('endpoint')
            else:
                method_scopes.add('helper')
            if scope not in method_scopes:
                continue
            # Check owner
            method_owner = getattr(method, '__config_owner__', None)
            if owner is not None and owner != method_owner:
                continue
            # Check configuration
            if config and not validate_service_method(method, config):
                continue
            # Add method
            methods[name] = method

        return methods

    def _remove_method(self, name: str) -> None:
        """Remove a method from the manager.

        Args:
            name: The name of the method to remove.

        Raises:
            AttributeError: If the method does not exist within the manager of
                the managed instance or type.
        """
        # Check if method does not exist
        if name not in self.__dict__:
            raise AttributeError(
                f"Method {name!r} does not exist within the manager of "
                f"{str(self.__config_managed__)!r}."
            )
        del self.__dict__[name]

    def __contains__(self, key: str) -> bool:
        return key in self._collect_methods()

    def __iter__(self) -> Iterator[str]:
        yield from self._collect_methods()

    def __reversed__(self) -> Iterator[str]:
        yield from reversed(self._collect_methods())

    def __len__(self) -> int:
        return len(self._collect_methods())

    def __getitem__(self, key: str) -> Callable[..., Any]:
        return self._collect_methods()[key]

    def __setitem__(self, key: str, value: Any) -> None:
        raise AttributeError(
            f"The method {key!r} cannot be directly set on the manager of "
            f"{str(self.__config_managed__)!r}. Use the '_add_method' method "
            f"instead to add a new method."
        )

    def __delitem__(self, key: str) -> None:
        raise AttributeError(
            f"The method {key!r} cannot be directly deleted from the manager "
            f"of {str(self.__config_managed__)!r}. Use the '_remove_method' "
            f"method instead to remove it."
        )

    def __setattr__(self, name: str, value: Any) -> None:
        # Skip dunder methods and attributes
        if name.startswith('__') and name.endswith('__'):
            super().__setattr__(name, value)
            return
        raise AttributeError(
            f"The method {name!r} cannot be directly set on the manager of "
            f"{str(self.__config_managed__)!r}. Use the '_add_method' method "
            f"instead to add a new method."
        )

    def __delattr__(self, name: str) -> None:
        raise AttributeError(
            f"The method {name!r} cannot be directly deleted from the manager "
            f"of {str(self.__config_managed__)!r}. Use the '_remove_method' "
            f"method instead to remove it."
        )

    def __repr__(self) -> str:
        return f'Manager({self})'

    def __str__(self) -> str:
        return str(self.__config_managed__)
