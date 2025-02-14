# plateforme.core.database.schema
# -------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing database schema definitions within
the Plateforme framework using SQLAlchemy features.
"""

from typing import Any, Callable

from sqlalchemy.schema import (
    Column,
    ForeignKey,
    Index,
    MetaData as _MetaData,
    Table,
)

__all__ = (
    'Column',
    'ForeignKey',
    'Index',
    'MetaData',
    'Table',
    'NAMING_CONVENTION',
)


NAMING_CONVENTION = {
    'ix': 'ix_%(column_0_label)s',
    'uq': 'uq_%(table_name)s_%(column_0_name)s',
    'ck': 'ck_%(table_name)s_%(constraint_name)s',
    'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
    'pk': 'pk_%(table_name)s'
}
"""The default naming convention for the database schema."""


class MetaData(_MetaData):
    """A collection of `Table`.

    A collection of `Table` objects and their associated schema constructs. It
    overrides the schema attribute to provide a custom implementation factory
    for the schema name.

    Holds a collection of `Table` objects as well as an optional binding to an
    `Engine` or `Connection`. If bound, the `Table` objects in the collection
    and their columns may participate in implicit SQL execution.

    The `MetaData` class is a thread-safe object for read operations.
    Construction of new tables within a single `MetaData` object, either
    explicitly or via reflection, may not be completely thread-safe.
    """

    def __init__(
        self,
        schema: str | None = None,
        schema_factory: Callable[[], str | None] | None = None,
        info: dict[Any, Any] | None = None,
    ) -> None:
        """Initializes the `MetaData` object.

        Args:
            schema: The default schema name to use for the metadata.
            schema_factory: A callable that returns the schema name to use for
                the metadata. If provided, it will be called to get the schema
                name when needed.
            info: A dictionary of arbitrary data to be associated with the
                metadata.

        Note:
            See SQLAlchemy's documentation for more information on the
            parameters and their usage.
        """
        super().__init__(
            schema=schema,
            quote_schema=True,
            naming_convention=NAMING_CONVENTION,
            info=info,
        )

        # Initialize factory for schema name
        self.schema_factory = schema_factory

    @property  # type: ignore[override, unused-ignore]
    def schema(self) -> str | None:
        """Property getter override for the schema attribute."""
        if self.schema_factory is not None:
            return self.schema_factory()
        return self._schema

    @schema.setter
    def schema(self, value: str | None) -> None:
        """Property setter override for the schema attribute."""
        self._schema = value

    def _add_table(
        self, name: str, schema: str | None, table: Table
    ) -> None:
        """Adds a table object to the metadata collection."""
        # Define custom property getter and setter for the schema attribute
        def schema_getter(table_self: Table) -> str | None:
            if hasattr(table_self, 'metadata'):
                schema_factory = \
                    getattr(table_self.metadata, 'schema_factory', None)
                if schema_factory is not None:
                    return schema_factory()  # type: ignore
            return getattr(table_self, '_schema')  # type: ignore

        def schema_setter(table_self: Table, value: str | None) -> None:
            setattr(table_self, '_schema', value)

        # Set the schema attribute on the table object
        setattr(table, '_schema', schema)
        setattr(Table, 'schema', property(schema_getter, schema_setter))

        # Add the table object to the metadata collection
        self.tables._insert_item(name, table)
        if schema:
            self._schemas.add(schema)
