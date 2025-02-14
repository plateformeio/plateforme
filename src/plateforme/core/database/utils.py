# plateforme.core.database.utils
# ------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utility functions for working with database and queries
within the Plateforme framework.
"""

from collections.abc import Sequence
from typing import Any, TypeVar

from ..expressions import Filter, Sort, Symbol
from .expressions import ExecutableOption, Select, select
from .orm import (
    ColumnProperty,
    InstrumentedAttribute,
    RelationshipProperty,
    selectinload,
)

_T = TypeVar("_T", bound=Any)

__all__ = (
    'apply_filter',
    'apply_reference',
    'apply_sort',
    'build_options',
    'build_query',
)


def apply_filter(
    query: Select[tuple[_T]],
    criteria: Filter,
    *,
    entity: type[Any] | None = None,
    refs: dict[str, InstrumentedAttribute[Any]] | None = None,
    raise_errors: bool = True,
) -> Select[tuple[_T]]:
    """Apply the filter criteria to the given query.

    Recursively builds and applies a filter to the provided query based on the
    given criteria. The function constructs a filter for the inferred or
    specified target entity, performs join operations on entity relationships
    specified in the criteria, and updates the query with the filter value
    assignments.

    Args:
        query: The query to build and update recursively with the filter
            assignments.
        criteria: The filter dictionary containing the conditions to build
            the query with.
        entity: The entity class used to build the filter query. When not
            provided, the function attempts to infer the entity from the query
            column descriptions. Defaults to ``None``.
        refs: The reference attributes mapping used to resolve the reference
            values in the filter conditions. Defaults to ``None``.
        raise_errors: Whether to raise errors when invalid attributes or values
            are found in the criteria. Defaults to ``True``.

    Returns:
        The updated query with the applied filters.
    """
    if entity is None:
        entity = next((c['entity'] for c in query.column_descriptions), None)
    if not isinstance(entity, type):
        if not raise_errors:
            return query
        raise ValueError(
            f"Invalid entity to filter for the given query. Expected a "
            f"selectable entity class, but got: {entity!r}."
        )

    relationships: dict[InstrumentedAttribute[Any],  Any] = {}

    # Apply filter criteria
    for key, criterion in criteria.items():
        # Handle spread operator
        if key.endswith(Symbol.SPREAD):
            key = key[:-1]
            uselist = True
        else:
            uselist = False

        # Resolve attribute
        attr = getattr(entity, key, None)
        if not isinstance(attr, InstrumentedAttribute):
            if not raise_errors:
                continue
            raise KeyError(
                f"Invalid attribute {key!r} found in the filter criteria for "
                f"entity {entity.__qualname__!r}. Got: {criteria!r}."
            )

        # Handle relationship property
        if isinstance(attr.property, RelationshipProperty):
            if not isinstance(criterion, dict):
                if not raise_errors:
                    continue
                raise ValueError(
                    f"Invalid criterion found for relationship attribute "
                    f"{key!r} in the filter for entity "
                    f"{entity.__qualname__!r}. Expected a dictionary, but "
                    f"got: {criterion!r}."
                )
            if uselist and not attr.property.uselist:
                if not raise_errors:
                    continue
                raise KeyError(
                    f"Invalid criterion key {key!r} found in the filter "
                    f"criteria for entity {entity.__qualname__!r}. The spread "
                    f"operator `*` is not supported for single relationships."
                )
            elif not uselist and attr.property.uselist:
                if not raise_errors:
                    continue
                raise KeyError(
                    f"Invalid criterion key {key!r} found in the filter "
                    f"criteria for entity {entity.__qualname__!r}. The spread "
                    f"operator `*` is required for many relationships."
                )
            relationships[attr] = criterion

        # Handle column attribute
        elif isinstance(attr.property, ColumnProperty):
            if isinstance(criterion, dict):
                if not raise_errors:
                    continue
                raise ValueError(
                    f"Invalid criterion found for column attribute {key!r} in "
                    f"the filter for entity {entity.__qualname__!r}. Expected "
                    f"a list of conditions, but got: {criterion!r}."
                )
            if uselist:
                if not raise_errors:
                    continue
                raise KeyError(
                    f"Invalid criterion key {key!r} found in the filter "
                    f"criteria for entity {entity.__qualname__!r}. The spread "
                    f"operator `*` is not supported for column attributes."
                )
            for condition in criterion:
                query = condition.apply(query, attr, refs=refs)

        # Handle invalid attribute
        else:
            if not raise_errors:
                continue
            raise ValueError(
                f"Invalid criterion found for attribute {key!r} in the filter "
                f"for entity {entity.__qualname__!r}. Got: {criteria!r}."
            )

    # Apply filter recursively for relationship attributes
    for attr, value in relationships.items():
        assert isinstance(attr.property, RelationshipProperty)
        class_ = attr.property.mapper.class_
        query = query.join(class_, attr)
        query = apply_filter(
            query,
            value,
            entity=class_,
            refs=refs,
            raise_errors=raise_errors,
        )

    return query


def apply_reference(
    query: Select[tuple[_T]],
    keys: list[str],
    *,
    entity: type[Any] | None = None,
    raise_errors: bool = True,
) -> tuple[Select[tuple[_T]], dict[str, InstrumentedAttribute[Any]]]:
    """Apply and resolve the reference mapping against the given query.

    Builds and applies the reference mapping to the provided query based on
    the given keys. The function constructs a mapping of reference attributes
    for the inferred or specified target entity, performs join operations on
    entity relationships specified in the keys, and returns the updated query
    with the reference attribute assignments.

    Args:
        query: The query to build and update recursively with the reference
            assignments.
        keys: The reference keys to resolve and apply to the query.
        entity: The entity class used to build the reference query. When not
            provided, the function attempts to infer the entity from the query
            column descriptions. Defaults to ``None``.
        raise_errors: Whether to raise errors when invalid attributes or values
            are found in the keys. Defaults to ``True``.
    """
    references: dict[str, InstrumentedAttribute[Any]] = {}

    if entity is None:
        entity = next((c['entity'] for c in query.column_descriptions), None)
    if not isinstance(entity, type):
        if not raise_errors:
            return query, references
        raise ValueError(
            f"Invalid entity to reference for the given query. Expected a "
            f"selectable entity class, but got: {entity!r}."
        )

    # Apply and resolve reference keys
    for key in keys:
        segments = key.split('.')
        class_ = entity

        for count, segment in enumerate(segments):
            # Resolve attribute
            attr = getattr(class_, segment, None)
            if not isinstance(attr, InstrumentedAttribute):
                if not raise_errors:
                    continue
                raise KeyError(
                    f"Invalid attribute {segment!r} found in the reference "
                    f"key for entity {class_.__qualname__!r}. Got: {key!r}."
                )

            # Handle relationship property
            if count < len(segments) - 1:
                if not isinstance(attr.property, RelationshipProperty):
                    if not raise_errors:
                        continue
                    raise ValueError(
                        f"Invalid attribute {segment!r} found in the "
                        f"reference key for entity {class_.__qualname__!r}. "
                        f"Expected a relationship property, but got: {attr!r}."
                    )
                elif attr.property.uselist:
                    if not raise_errors:
                        continue
                    raise KeyError(
                        f"Invalid attribute {segment!r} found in the "
                        f"reference key for entity {class_.__qualname__!r}. "
                        f"Many relationships are not supported."
                    )
                class_ = attr.property.mapper.class_
                query = query.join(class_, attr)

            # Handle column attribute
            else:
                if not isinstance(attr.property, ColumnProperty):
                    if not raise_errors:
                        continue
                    raise ValueError(
                        f"Invalid attribute {segment!r} found in the "
                        f"reference key for entity {class_.__qualname__!r}. "
                        f"Expected a column attribute, but got: {attr!r}."
                    )
                references[key] = attr

    return query, references


def apply_sort(
    query: Select[tuple[_T]],
    criteria: Sort,
    *,
    entity: type[Any] | None = None,
    raise_errors: bool = True,
) -> Select[tuple[_T]]:
    """Apply the sort criteria to the given query.

    Builds and applies a sort to the provided query based on the given
    criteria. The function constructs a sort for the inferred or specified
    target entity, performs join operations on entity relationships specified
    in the criteria, and updates the query with the sort value assignments.

    Args:
        query: The query to build and update recursively with the sort
            assignments.
        criteria: The sort list containing the criteria to build the query
            with.
        entity: The entity class used to build the sort query. When not
            provided, the function attempts to infer the entity from the query
            column descriptions. Defaults to ``None``.
        raise_errors: Whether to raise errors when invalid attributes or values
            are found in the criteria. Defaults to ``True``.
    """
    if entity is None:
        entity = next((c['entity'] for c in query.column_descriptions), None)
    if not isinstance(entity, type):
        if not raise_errors:
            return query
        raise ValueError(
            f"Invalid entity to sort for the given query. Expected a "
            f"selectable entity class, but got: {entity!r}."
        )

    # Apply sort criteria
    for criterion in criteria:
        key, ordering = criterion

        segments = key.split('.')
        class_ = entity

        for count, segment in enumerate(segments):
            # Handle spread operator
            if segment.endswith(Symbol.SPREAD):
                segment = segment[:-1]
                uselist = True
            else:
                uselist = False

            # Resolve attribute
            attr = getattr(class_, segment, None)
            if not isinstance(attr, InstrumentedAttribute):
                if not raise_errors:
                    continue
                raise KeyError(
                    f"Invalid attribute {segment!r} found in the sort "
                    f"criteria for entity {class_.__qualname__!r}. Got: "
                    f"{criteria!r}."
                )

            # Handle relationship property
            if count < len(segments) - 1:
                if not isinstance(attr.property, RelationshipProperty):
                    if not raise_errors:
                        continue
                    raise ValueError(
                        f"Invalid criterion key {segment!r} found in the sort "
                        f"criteria for entity {class_.__qualname__!r}. "
                        f"Expected a relationship property, but got: {attr!r}."
                    )
                if uselist and not attr.property.uselist:
                    if not raise_errors:
                        continue
                    raise KeyError(
                        f"Invalid criterion key {segment!r} found in the sort "
                        f"criteria for entity {class_.__qualname__!r}. The "
                        f"spread operator `*` is not supported for single "
                        f"relationships."
                    )
                elif not uselist and attr.property.uselist:
                    if not raise_errors:
                        continue
                    raise KeyError(
                        f"Invalid criterion key {segment!r} found in the sort "
                        f"criteria for entity {class_.__qualname__!r}. The "
                        f"spread operator `*` is required for many "
                        f"relationships."
                    )
                class_ = attr.property.mapper.class_
                query = query.join(class_, attr)

            # Handle column attribute
            else:
                if not isinstance(attr.property, ColumnProperty):
                    if not raise_errors:
                        continue
                    raise ValueError(
                        f"Invalid criterion key {segment!r} found in the sort "
                        f"criteria for entity {class_.__qualname__!r}. "
                        f"Expected a column attribute, but got: {attr!r}."
                    )
                if uselist:
                    if not raise_errors:
                        continue
                    raise KeyError(
                        f"Invalid criterion key {segment!r} found in the sort "
                        f"criteria for entity {class_.__qualname__!r}. The "
                        f"spread operator `*` is not supported for column "
                        f"attributes."
                    )
                query = ordering.apply(query, attr)

    return query


def build_options(
    entity: type[Any],
    *,
    eager_load: set[str] | None = None,
    raise_errors: bool = True,
) -> list[ExecutableOption]:
    """Builds query options from the given configuration.

    Args:
        entity: The entity class to build the query options for.
        eager_load: The set of relationship attributes to eagerly load in the
            executable operation. Defaults to ``None``.
        raise_errors: Whether to raise errors when invalid attributes or values
            are found in the configuration. Defaults to ``True``.

    Returns:
        The list of query options to apply to the executable operation.
    """
    options: list[ExecutableOption] = []

    # Eager load specified relationships
    for key in eager_load or []:
        attr = getattr(entity, key, None)
        if not isinstance(attr, InstrumentedAttribute):
            if not raise_errors:
                continue
            raise KeyError(
                f"Invalid relationship {key!r} specified for eager "
                f"loading on entity {entity.__qualname__!r}."
            )
        if isinstance(attr.property, RelationshipProperty):
            options.append(selectinload(attr))

    return options


def build_query(
    entity: type[_T],
    selection: dict[str, Any],
    __query: Select[tuple[_T]] | None = None,
    *,
    filter_criteria: Filter | None = None,
    sort_criteria: Sort | None = None,
    options: Sequence[ExecutableOption] | None = None,
    raise_errors: bool = True,
) -> Select[tuple[_T]]:
    """Builds a query for the given entity and selection.

    Recursively builds a query for the given entity and selection dictionary,
    by performing a join operation on the entity relationships found in the
    selection and filtering the query based on the selection value assignments.
    Optionally, the function can apply filter and sort criteria to the query.

    Args:
        entity: The entity class to build the query for.
        selection: The selection dictionary containing the conditions to build
            the query with.
        __query: The query to build and update recursively with the selection
            assignments. Defaults to ``None``.
        filter_criteria: The filter criteria to apply to the query.
            Defaults to ``None``.
        sort_criteria: The sort criteria to apply to the query.
            Defaults to ``None``.
        options: The options to apply to the query.
            Defaults to ``None``.
        raise_errors: Whether to raise errors when invalid attributes or values
            are found in the selection. Defaults to ``True``.

    Returns:
        The built query for the given entity and selection with the applied
        filter and sort criteria.
    """
    query = __query if __query is not None else select(entity)

    relationships: dict[InstrumentedAttribute[Any],  Any] = {}

    # Build query for selection
    for key, value in selection.items():
        attr = getattr(entity, key, None)
        if not isinstance(attr, InstrumentedAttribute):
            if not raise_errors:
                continue
            raise KeyError(
                f"Invalid attribute {key!r} found in the selection for entity "
                f"{entity.__qualname__!r}. Got: {selection!r}."
            )

        # Handle column attributes
        if isinstance(attr.property, ColumnProperty):
            if isinstance(value, dict):
                if not raise_errors:
                    continue
                raise ValueError(
                    f"Invalid value found for column attribute {key!r} in the "
                    f"selection for entity {entity.__qualname__!r}. Expected "
                    f"a raw value, but got: {value!r}."
                )
            query = query.filter(attr == value)
            continue

        # Handle relationship attributes
        if isinstance(attr.property, RelationshipProperty):
            if not isinstance(value, dict):
                if not raise_errors:
                    continue
                raise ValueError(
                    f"Invalid value {value!r} found for relationship "
                    f"attribute {key!r} in the selection for entity "
                    f"{entity.__qualname__!r}. Expected a dictionary, but "
                    f"got: {value!r}."
                )
            relationships[attr] = value
            continue

        if not raise_errors:
            continue
        raise ValueError(
            f"Invalid value found for attribute {key!r} in the selection for "
            f"entity {entity.__qualname__!r}. Got: {selection!r}."
        )

    # Build query recursively for relationship attributes
    for attr, value in relationships.items():
        assert isinstance(attr.property, RelationshipProperty)
        class_ = attr.property.mapper.class_
        query = query.join(class_, attr)
        query = build_query(class_, value, query)

    # Apply filter and sort criteria
    if filter_criteria:
        query, refs = apply_reference(
            query,
            filter_criteria.references,
            entity=entity,
            raise_errors=raise_errors,
        )
        query = apply_filter(
            query,
            filter_criteria,
            entity=entity,
            refs=refs,
            raise_errors=raise_errors,
        )
    if sort_criteria:
        query = apply_sort(
            query,
            sort_criteria,
            entity=entity,
            raise_errors=raise_errors,
        )

    # Apply query options
    if options:
        query = query.options(*options)

    return query
