# plateforme.core.associations
# ----------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities to represent and manage associations between
resources in the Plateforme framework.
"""

import typing
from typing import Any

from .database.orm import InstrumentedList, InstrumentedSet, Relationship
from .database.schema import Column, ForeignKey, Table
from .errors import PlateformeError
from .patterns import to_path_case
from .representations import Representation
from .runtime import Action, Lifecycle

if typing.TYPE_CHECKING:
    from .resources import ResourceFieldInfo, ResourceType

__all__ = (
    'Association',
)


# MARK: Association

class Association(Representation):
    """Represents the association between two resources.

    This class is used to define how two resources are linked to each other,
    typically in a database or a similar structured data format. It captures
    the definition of the association, including its alias, the linked fields,
    and, if applicable, the association table for many-to-many associations.

    Attributes:
        alias: The alias name of the association. It must adhere to a specific
            ``ALIAS`` pattern as defined in the framework's regular expressions
            repository. Defaults to the concatenated aliases of the two linked
            resources based on links sorting order.
        links: A tuple containing one or two linked resource fields instances.
            These linked fields define the association, they are sorted based
            on three criteria:
            - ``many``: The "one" side of the association is placed first;
            - ``rel_attribute``: The link implementing the association
                relationship attribute in a one-to-one scenario is placed
                first;
            - ``owner.__qualname__``: Linked fields are sorted alphabetically
                based on the fully qualified name of the resource owner.
            This ensures a consistent and predictable order of linked fields
            and their implementation in the database.
        packages: A set containing the `Package` classes that contain the
            linked resources. This attribute is used to manage the association
            and ensure that it is added to the correct package objects
            namespace.
        table: The SQLAlchemy `Table` object representing the association
            table. This attribute is only relevant and required for
            many-to-many associations. It links the two resources through an
            intermediate table. For other types of associations, this should
            be set to ``None``.
    """
    __slots__ = (
        '__weakref__',
        'alias',
        'links',
        'packages',
        'table',
    )

    def __init__(self, *links: 'ResourceFieldInfo') -> None:
        """Initialize the association.

        It creates an association of one or two linked fields using either the
        `association_alias` attribute if specified or by joining with an
        underscore the sorted linked fields by their owner resource fully
        qualified name. The association is added to their relative package
        objects dictionary.

        Args:
            links: The linked resource fields that define the association.

        Note:
            For scenarios where an association table is required, the sorted
            first linked field package is considered the "owner" of the
            association, i.e. the table is created within the package metadata
            of the first linked field. This is a design choice to ensure a
            consistent and predictable order of linked fields and their
            implementation in the database.
        """
        # Validate linked fields length
        if 1 < len(links) > 2:
            raise PlateformeError(
                f"Invalid number of associated linked fields. An association "
                f"must have one or two linked fields. Got {len(links)} linked "
                f"fields: {', '.join(map(str, links))}.",
                code='association-invalid-config',
            )

        # Initialize links and alias
        self.links = _sort_links(*links)
        self.alias = self.links[0].association_alias or '%s_%s' % (
            self.links[0].owner.resource_config.alias,
            self.links[0].target.resource_config.alias,  # type: ignore
        )

        # Handle backref definition
        if len(self.links) == 1 and self.links[0].rel_backref is not None:
            backref = self.links[0]._from_field_info_backref(self.links[0])
            self.links += (backref,)

        # Initialize packages and add association to catalogs
        packages = [link.owner.resource_package for link in self.links]
        self.packages = tuple(dict.fromkeys(packages))
        for package in self.packages:
            try:
                package.catalog._add(self, alias=self.alias, slug=self.slug)
            except KeyError as error:
                raise PlateformeError(
                    f"Invalid duplicate catalog entry for resource "
                    f"association {self.alias!r} in the package "
                    f"{package.name!r}.",
                    code='association-invalid-config',
                ) from error

        # Initialize table
        self.table: Table | None = None

        # Validate linked fields configuration
        if len(self.links) == 2 and (
            self.links[0].owner != self.links[1].target or
            self.links[0].target != self.links[1].owner or
            self.links[0].association_alias != self.links[1].association_alias
        ):
            raise PlateformeError(
                f"Associated linked fields must be related to each other, "
                f"i.e., the owner of the first linked field must be the "
                f"target of the second linked field and vice versa, and they "
                f"must have the same association alias. "
                f"Got: {', '.join(map(str, links))}.",
                code='association-invalid-config',
            )

        # Finalize association initialization
        for link_a, link_b in zip(self.links, reversed(self.links)):
            link_a._default(association=self)
            link_a._default(association_alias=self.alias)
            if len(self.links) == 1:
                continue
            link_a._default(rel_backref=link_b)  # type: ignore[arg-type]
            if link_a.rel_backref is link_b:
                continue
            raise ValueError(
                f"Invalid association implementation for {self.alias!r} "
                f"between resource {link_a.owner.__qualname__!r} and resource "
                f"{link_b.owner.__qualname__!r}. An invalid back reference "
                f"was set for the association linked fields.",
            )

    @property
    def slug(self) -> str:
        """Return the slug representation of the association."""
        return to_path_case(self.alias)

    def build(self) -> None:
        """Build the association between resources.

        This process handles all types of associations such as many-to-unknown,
        many-to-many, one-to-unknown, one-to-many, many-to-one, and one-to-one.
        It performs the necessary logic to establish these associations, which
        may involve creating an association tables, foreign key columns, and
        validating resource indexes and association configurations.

        Note:
            This method is an internal function and should not be called
            directly outside of class context.
        """
        # Retrieve association owner to handle different logics
        package = self.packages[0]
        owner_link = self.links[0]
        owner: ResourceType = owner_link.owner

        # Retrieve association target to handle different logics
        target_link: ResourceFieldInfo | None
        if len(self.links) == 2:
            target_link = self.links[1]
        elif owner_link.rel_backref is not None:
            target_link = owner_link.rel_backref
        else:
            target_link = None
        target: ResourceType = owner_link.target  # type: ignore

        # Store association columns for relationship configuration
        columns: list[Column[Any]] = []

        # For many-to-many and many-to-unknown associations, an association
        # table is required. If neither side has a foreign key column
        # ("rel_attribute" is "None" for both), an association table is created
        # to manage this association, else an error is raised.
        if all(link.collection for link in self.links):
            if any(link.rel_attribute is not None for link in self.links):
                raise PlateformeError(
                    f"Invalid association implementation for {self.alias!r} "
                    f"between resource {owner.__qualname__!r} and resource "
                    f"{target.__qualname__!r} in the package "
                    f"{package.name!r}. A many-to-many or many-to-unknown "
                    f"association requires that both sides have no "
                    f"relationship attribute defined.",
                    code='field-invalid-config',
                )

            # Create association columns
            for count, (resource, link) in \
                    enumerate(zip((owner, target), (owner_link, target_link))):
                # Handle association column naming
                alias = resource.resource_config.alias
                if owner is target:
                    name = f'{alias}_{count}_id'
                else:
                    name = f'{alias}_id'

                # Handle association column configuration
                if link is not None:
                    unique = link.collection == 'set'
                    col_extra = {**(link.column_extra or {})}
                    key_extra = col_extra.pop('foreign_key', {})
                else:
                    unique = None
                    col_extra = {}
                    key_extra = {}

                columns.append(
                    Column(
                        name,
                        resource.resource_config.id_engine,
                        ForeignKey(
                            resource.resource_attributes['id'],
                            ondelete='cascade',
                            **key_extra,
                        ),
                        primary_key=True,
                        unique=unique,
                        **col_extra,
                    )
                )

            # Create association table
            self.table = Table(
                self.alias,
                package.metadata,
                *columns,
                info={'type': 'link'},
            )

        # For one-to-unknown, one-to-many, many-to-one, or one-to-one
        # association, only one of the "one" side resource requires a foreign
        # key column. If not explicitly set ("rel_attribute" is "None"), the
        # default name is assigned, which is the alias of the linked field
        # suffixed with "_id". A foreign key column with this name is then
        # created in the determined "one" side resource.
        else:
            if target_link and target_link.rel_attribute is not None:
                raise PlateformeError(
                    f"Invalid association implementation for {self.alias!r} "
                    f"between resource {owner.__qualname__!r} and resource "
                    f"{target.__qualname__!r} in the package "
                    f"{package.name!r}. A one-to-unknown, one-to-many, "
                    f"many-to-one, or one-to-one association requires that "
                    f"only one of the `one` side resource has an association "
                    f"attribute defined.",
                    code='field-invalid-config',
                )

            # Retrieve association relationship attribute
            rel_attribute = owner_link.rel_attribute \
                or f'{owner_link.alias}_id'
            if hasattr(owner, rel_attribute):
                raise PlateformeError(
                    f"Invalid association implementation for {self.alias!r} "
                    f"between resource {owner.__qualname__!r} and resource "
                    f"{target.__qualname__!r} in the package "
                    f"{package.name!r}. The `one` side resource already has "
                    f"an attribute with the same name {rel_attribute!r} than "
                    f"the relationship attribute.",
                    code='field-invalid-config',
                )

            # Create association columns
            col_extra = {**(owner_link.column_extra or {})}
            key_extra = col_extra.pop('foreign_key', {})

            columns.append(
                Column(
                    rel_attribute,
                    target.resource_config.id_engine,
                    ForeignKey(
                        target.resource_attributes['id'],
                        ondelete='cascade',
                        **key_extra,
                    ),
                    index=owner_link.indexed or False,
                    unique=owner_link.unique or False,
                    nullable=owner_link.is_nullable(),
                    **col_extra,
                )
            )

            # Update owner association relationship attribute
            owner_link._update(rel_attribute=rel_attribute)
            # Add association relationship column to owner resource
            setattr(owner, rel_attribute, columns[0])

        # Validate resource link implementation and associated indexes
        # configuration. If the link is implemented in the resource, the
        # indexes can contain the link implementation field. Else, the indexes
        # must not contain the link implementation field.
        for link in self.links:
            # Validate link implementation
            if (link.indexed or link.unique) \
                    and not link.rel_attribute \
                    and link is not owner_link:
                raise TypeError(
                    f"Invalid linked field {link.alias!r} for resource "
                    f"{link.owner.__qualname__!r} in the package "
                    f"{package.name!r}. The linked field cannot be indexed or "
                    f"unique as the association {self.alias!r} is not "
                    f"implemented in this resource."
                )

            # Validate indexes configuration
            for index in link.owner.resource_config.indexes:
                if link.alias in index['aliases'] \
                        and not link.rel_attribute \
                        and link is not owner_link:
                    raise TypeError(
                        f"Invalid index for resource "
                        f"{link.owner.__qualname__!r} in the package "
                        f"{package.name!r}. The index cannot contain the "
                        f"linked field `{link.alias}` as the association "
                        f"{self.alias!r} is not implemented in this resource."
                    )

        # Schedule association relationships building
        for count, (link_a, link_b) in enumerate(
            zip((owner_link, target_link), (target_link, owner_link))
        ):
            # Skip if no link is provided
            if link_a is None:
                continue

            # Resolve foreign keys configuration
            if self.table is None:
                foreign_keys = columns[count:]
            else:
                foreign_keys = [columns[count], columns[1 - count]]

            # Schedule relationship building
            args = (link_a, link_b, self.table, *foreign_keys)
            link_a.owner.__state__.schedule(
                Action(_build_relationship, args=args),
                when=Lifecycle.INITIALIZING,
            )


# MARK: Utilities

def _build_relationship(
    link_a: 'ResourceFieldInfo',
    link_b: 'ResourceFieldInfo | None' = None,
    secondary: Table | None = None,
    *foreign_keys: Column[Any],
) -> None:
    """Build the relationship between two resources.

    This function handles the creation of the relationship between two
    resources based on the provided linked fields. It creates the necessary
    SQLAlchemy relationship attributes and configurations to establish the
    association between the resources.

    Args:
        link_a: The first linked field that defines the relationship.
        link_b: The second linked field that defines the relationship. This
            argument is optional and defaults to ``None``. If provided, the
            relationship is built between the two linked fields.
        secondary: The association table that links the two resources. This
            argument is optional and defaults to ``None``. It is only relevant
            and required for many-to-many associations.
        *foreign_keys: The foreign key columns that define the relationship
            between the two resources. This argument is required and must be
            a list containing the foreign key columns for the relationship.
    """
    # Primary and secondary join configuration
    owner_id = link_a.owner.resource_attributes['id']
    if secondary is None:
        primaryjoin = secondaryjoin = None
    else:
        assert isinstance(link_a.target, type)
        owner_id = link_a.owner.resource_attributes['id']
        taget_id = link_a.target.resource_attributes['id']
        assert len(foreign_keys) == 2
        primaryjoin = foreign_keys[0] == owner_id
        secondaryjoin = foreign_keys[1] == taget_id

    # Backref configuration
    if link_b is not None:
        if not hasattr(link_b.owner, link_b.alias):
            attr = Relationship(link_b.target)
            setattr(link_b.owner, link_b.alias, attr)
        back_populates = link_b.alias
    else:
        back_populates = None

    # Cascade configuration
    if link_a.rel_cascade is not True:
        cascade = link_a.rel_cascade or ''
    else:
        if link_b is not None:
            cascade = 'save-update, merge'
            if link_b.is_identifying():
                cascade += ', delete-orphan'
            if link_b.is_indexing():
                cascade += ', delete, refresh-expire, expunge'
        else:
            cascade = 'merge'

    # Collection configuration
    if link_a.collection is None:
        collection_class: Any = None
    elif link_a.collection == 'list':
        collection_class = InstrumentedList
    elif link_a.collection == 'set':
        collection_class = InstrumentedSet
    else:
        raise NotImplementedError

    # Loading configuration
    if link_a.rel_load is not True:
        lazy = link_a.rel_load
    else:
        if link_a.is_indexing():
            lazy = 'joined'
        elif  link_b is not None and link_b.is_indexing():
            lazy = 'joined'
        elif link_a.collection is None:
            lazy = 'selectin'
        else:
            lazy = 'select'

    # Extra configuration
    rel_extra = link_a.rel_extra or {}

    setattr(
        link_a.owner,
        link_a.alias,
        Relationship(
            link_a.target,
            secondary=secondary,
            collection_class=collection_class,
            primaryjoin=primaryjoin,
            secondaryjoin=secondaryjoin,
            back_populates=back_populates,
            cascade=cascade,
            lazy=lazy,
            foreign_keys=foreign_keys,
            **rel_extra,
        ),
    )


def _sort_links(*links: 'ResourceFieldInfo') -> tuple['ResourceFieldInfo', ...]:
    """Sort the given linked fields based on their configuration."""
    # Assign collection type to integer mapping
    collection_map = {None: 0, 'set': 1, 'list': 2}

    return tuple(sorted(
        links,
        key=lambda link: (
            collection_map.get(link.collection, 3),
            link.rel_attribute,
            link.owner.__qualname__
        ),
    ))
