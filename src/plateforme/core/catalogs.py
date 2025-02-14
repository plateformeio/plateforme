# plateforme.core.catalogs
# ------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing catalogs of resources along with
their associations, and services used within the Plateforme framework.
"""

import re
import typing
from collections.abc import Iterable, Iterator
from typing import Any, Callable, Literal, TypeAlias
from weakref import WeakSet, WeakValueDictionary

from .patterns import RegexPattern

if typing.TYPE_CHECKING:
    from .associations import Association
    from .resources import ResourceType

__all__ = (
    'Catalog',
    'CatalogObject',
    'WeakCatalogMap',
    'WeakCatalogSet',
)


CatalogObject: TypeAlias = 'ResourceType | Association | Callable[..., Any]'
"""A type alias for an alias object that can be either a resource type, an
association, or a service method."""


WeakCatalogMap = WeakValueDictionary[str, CatalogObject]
"""A weak dictionary mapping an alias or a slug key to the object, either a
resource type, an association, or a service method within a catalog."""


WeakCatalogSet = WeakSet[CatalogObject]
"""A weak set of objects, either a resource type, an association, or a service
method within a catalog."""


class Catalog(Iterable[CatalogObject]):
    """A catalog of resources, associations, and services.

    Attributes:
        owner: The owner of the catalog.
        objects: A weak set of objects, either a resource type, an association,
            or a service method within the catalog.
        aliases: A weak dictionary mapping an alias key to the object instance,
            either a resource type, an association, or a service method within
            the catalog.
        slugs: A weak dictionary mapping a slug key to the object instance,
            either a resource type, an association, or a service method within
            the catalog.
    """

    def __init__(self, owner: Any) -> None:
        """Initialize the catalog.

        Args:
            owner: The owner of the catalog.
        """
        self.owner = owner
        self.objects: WeakCatalogSet = WeakSet()
        self.aliases: WeakCatalogMap = WeakValueDictionary()
        self.slugs: WeakCatalogMap = WeakValueDictionary()

    def __call__(
        self, *, scope: Literal['alias', 'slug']
    ) -> dict[str, CatalogObject]:
        """Get the catalog items based on the given scope.

        Args:
            scope: The scope of the catalog items to retrieve. It can be either
                ``alias`` or ``slug``.
        """
        if scope == 'alias':
            return {**self.aliases}
        else:
            return {**self.slugs}

    def _add(self, obj: CatalogObject, *, alias: str, slug: str) -> None:
        """Add an object to the catalog.

        It adds the object with the given alias and slug keys to the catalog.
        The provided alias and slug keys must be unique within the catalog and
        match the specific patterns defined in the framework's regular for
        aliases and slugs.

        Args:
            obj: The object to add to the catalog, it can be a resource type,
                an association, or a service method.
            alias: The alias key to associate with the object.
            slug: The slug key to associate with the object.
        """
        # Validate alias
        if alias and not re.match(RegexPattern.ALIAS, alias):
            raise KeyError(
                f"Alias {alias!r} is invalid. It must match a specific "
                f"pattern `ALIAS` defined in the framework's regular "
                f"expressions repository."
            )
        if alias in self.aliases:
            raise KeyError(
                f"Alias {alias!r} already exists within the catalog of "
                f"{self.owner!r}."
            )

        # Validate slug
        if slug and not re.match(RegexPattern.SLUG, slug):
            raise KeyError(
                f"Slug {slug!r} is invalid. It must match a specific pattern "
                f"`SLUG` defined in the framework's regular expressions "
                f"repository."
            )
        if slug in self.slugs:
            raise KeyError(
                f"Slug {slug!r} already exists within the catalog of "
                f"{self.owner!r}."
            )

        # Add object to catalog
        self.aliases[alias] = obj
        self.slugs[slug] = obj
        self.objects.add(obj)

    def _remove(self, obj: CatalogObject) -> None:
        """Remove an object from the catalog.

        Args:
            obj: The object to remove from the catalog, it can be a resource
                type, an association, or a service method.
        """
        for key, value in self.aliases.items():
            if value == obj:
                del self.aliases[key]
                break
        for key, value in self.slugs.items():
            if value == obj:
                del self.slugs[key]
                break
        self.objects.discard(obj)

    def __contains__(self, obj: CatalogObject) -> bool:
        return obj in self.objects

    def __iter__(self) -> Iterator[CatalogObject]:
        yield from self.objects

    def __reversed__(self) -> Iterator[CatalogObject]:
        yield from reversed([*self.objects])

    def __len__(self) -> int:
        return len(self.objects)
