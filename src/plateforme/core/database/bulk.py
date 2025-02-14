# plateforme.core.database.bulk
# -----------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing database sessions bulk within the
Plateforme framework using SQLAlchemy features.
"""

import dataclasses
import typing
from abc import ABC, abstractmethod
from threading import Lock
from typing import Any, Awaitable, Generator, Generic, Literal, TypeVar

from ..errors import SessionError
from ..typing import is_exception, is_proxy
from .engines import Result
from .expressions import Select, and_, or_, select
from .orm import load_only, make_transient_to_detached

if typing.TYPE_CHECKING:
    from ..resources import BaseResource, ResourceType
    from ..specs import BaseSpec, SpecType
    from .sessions import AsyncSession, Session

_T = TypeVar('_T', 'AsyncSession', 'Session')

__all__ = (
    'Bulk',
    'BulkConditions',
    'BulkData',
    'BulkEntry',
    'BulkHash',
    'BulkMap',
    'BulkProcess',
    'BulkQuery',
    'BulkResult',
    'BulkSignature',
    'BulkValue',
    'BulkResources',
    'generate_hash',
)


BulkData = dict['ResourceType', set['BulkEntry']]
"""A type alias for bulk data used in the bulk manager."""


BulkHash = int
"""A type alias for a bulk hash used in query conditions."""


BulkSignature = frozenset[str]
"""A type alias for bulk fields signature used in query conditions."""


BulkValue = dict[str, Any]
"""A type alias for a bulk value used in query conditions."""


BulkConditions = dict[BulkSignature, list[BulkValue]]
"""A type alias that stores bulk conditions for the resolution."""


BulkMap = dict[BulkHash, list['BulkEntry']]
"""A type alias that maps bulk entries to their hash values."""


BulkQuery = tuple[BulkSignature, Select[Any]]
"""A type alias for a bulk query used for the resolution."""


BulkProcess = list[BulkQuery]
"""A type alias for a bulk process used for the resolution."""


BulkResult = tuple[BulkSignature, Result[Any]]
"""A type alias for a bulk result used for the resolution."""


# MARK: Bulk

@dataclasses.dataclass(frozen=True, kw_only=True)
class BulkEntry:
    """A metadata class for bulk resource entries."""

    instance: 'BaseResource' = dataclasses.field(kw_only=False)
    """The bulk entry resource instance."""

    is_proxy: bool = dataclasses.field(default=False)
    """Whether the bulk entry resource instance is a proxy or not."""

    is_reference: bool = dataclasses.field(default=False)
    """Whether the bulk entry resource instance is a reference or not."""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BulkEntry):
            return NotImplemented
        return self.instance == other.instance

    def __hash__(self) -> int:
        return hash(self.instance)


class Bulk(ABC, Generic[_T]):
    """A bulk registry and operation manager for resources.

    It is used to register resources for bulk operations and commit or rollback
    them in a streamlined manner. The bulk manager can be used to resolve
    resource references and update the resource instances with the resolved
    identifiers.

    Attributes:
        session: The async or sync session used for the bulk operations.
        proxy_reference: Whether resource references should be encapsulated
            with a proxy or not.
        resolved: The resolved resource entries in the bulk.
        unresolved: The unresolved resource entries in the bulk.
    """
    if typing.TYPE_CHECKING:
        session: _T
        proxy_reference: bool
        resolved: BulkData
        unresolved: BulkData

    def __init__(self, session: _T, *, proxy_reference: bool = True):
        """Initialize the session bulk manager.

        The proxy option indicates that the provided resource references should
        be encapsulated with a proxy, this is done when validating the resource
        using the Pydantic core schema. This can be useful to resolve the
        references that target the same resource into a single instance. Thus,
        modifying a resolved instance will affect all references that target
        the same resource.

        Args:
            session: The session to use for the bulk operations.
            proxy_reference: Whether the registered resource references should
                be encapsulated with a proxy or not. Defaults to ``True``.
        """
        self._lock = Lock()

        self.session = session
        self.proxy_reference = proxy_reference

        self.resolved = {}
        self.unresolved = {}

    def add(
        self,
        instance: 'BaseResource | BaseSpec',
        *,
        is_reference: bool = False,
    ) -> None:
        """Add a resource instance to the bulk manager.

        Args:
            instance: The resource instance to add to the bulk manager.
            is_reference: Whether the provided resource instance is a reference
                or not. Defaults to ``False``.
        """
        # Resolve instance entity class
        if is_proxy(instance):
            proxy = instance.__proxy__()
            entity = proxy.__class__
        else:
            proxy = None
            entity = instance.__class__

        # Create instance entry
        entry = BulkEntry(
            instance,  # type: ignore
            is_proxy=proxy is not None,
            is_reference=is_reference,
        )

        # Register instance entry
        with self._lock:
            if entity not in self.resolved:
                self.resolved[entity] = set()
            if entity not in self.unresolved:
                self.unresolved[entity] = set()
            self.unresolved[entity].add(entry)

    def get(
        self,
        entity: 'ResourceType | SpecType',
        *,
        resolved: bool | None = None,
        scope: Literal['all', 'references', 'values'] = 'all',
    ) -> list['BaseResource']:
        """Get the resource instances registered in the bulk manager.

        Args:
            entity: The resource type to get the resource instances for.
            resolved: Whether to get only the resolved resources or not:
                - ``True``: Get only the resolved resources.
                - ``False``: Get only the unresolved resources.
                - ``None``: Get all the resources.
                Defaults to ``None``.
            scope: The scope of the resource instances to get:
                - ``'all'``: Get all the resource instances.
                - ``'references'``: Get only the resource reference instances.
                - ``'values'``: Get only the resource value instances.
                Defaults to ``'all'``.

        Returns:
            The list of resource instances registered in the bulk manager for
            the specified resource type and options.
        """
        entries: set[BulkEntry] = set()

        # Retrieve entries
        if resolved is None or resolved:
            entries.update(self.resolved.get(entity, set()))  # type: ignore
        if resolved is None or not resolved:
            entries.update(self.unresolved.get(entity, set()))  # type: ignore

        # Retrieve instances by scope
        if scope == 'references':
            return [
                entry.instance for entry in entries
                if entry.is_reference
            ]
        elif scope == 'values':
            return [
                entry.instance for entry in entries
                if not entry.is_reference
            ]

        return [entry.instance for entry in entries]

    @abstractmethod
    def resolve(
        self,
        *,
        raise_errors: bool = True,
        scope: Literal['all', 'references', 'values'] = 'all',
        strategy: Literal['bind', 'hydrate'] = 'bind',
    ) -> None | Awaitable[None]:
        """Resolve the specified scope of resource entries in the bulk.

        It must be implemented by the subclass either as a synchronous or
        asynchronous method to resolve the registered resource entries in the
        bulk.

        For resource references, if the `proxy_reference` option is enabled,
        the resolved instances replace the reference proxy targets. Otherwise,
        the resolved instances are used to update the reference proxy target.

        For resource values, the resolved instances are used to update the
        resource instances with the fetched data, no proxy is used.

        Args:
            raise_errors: Whether to raise errors when failing to resolve
                resource references or values. Defaults to ``True``.
            scope: The scope of the resources to resolve, it can be either:
                - ``'all'``: Resolve both the resource references and values.
                - ``'references'``: Resolve only the resource references.
                - ``'values'``: Resolve only the resource values.
                Defaults to ``'all'``.
            strategy: The resolution strategy to use, it can be either:
                - ``'bind'``: Bind the resolved resource references and values
                    to the database session, i.e. only the resolved `id` and
                    `type_` fields are updated and the instances are made
                    transient to detached.
                - ``'hydrate'``: Hydrate the resolved resource references and
                    values with the data fetched from the database, i.e. the
                    instances are updated with the fetched data.
                Defaults to ``'bind'``.
        """
        ...

    def _resolver(
        self,
        *,
        raise_errors: bool = True,
        scope: Literal['all', 'references', 'values'] = 'all',
        strategy: Literal['bind', 'hydrate'] = 'bind',
    ) -> Generator[BulkQuery, BulkResult, None]:
        """Resolution generator for the bulk manager.

        It should be used by the subclass to resolve the registered resource
        entries in the bulk. It yields the resolution queries and results to
        handle the resolution process, thus decoupling the asynchronous or
        synchronous resolution process from the bulk manager.
        """
        with self._lock:
            # Setup and process resolution queue
            queue = _setup_resolution_queue(
                self.unresolved,
                scope=scope,
                strategy=strategy,
            )

            for entity, mapping, process in queue:
                unresolved = set(mapping.keys())

                # Yield and process resolution queries
                for query in process:
                    result = yield query

                    # Validate resolution query result
                    if is_exception(result):
                        if not raise_errors:
                            continue
                        raise SessionError(
                            f"An unexpected error occurred while resolving "
                            f"bulk references for resource type "
                            f"{entity.__name__!r}."
                        ) from result

                    # Handle resolution query
                    unresolved -= _handle_resolution_query(
                        entity,
                        mapping,
                        result,
                        raise_errors=raise_errors,
                        strategy=strategy,
                    )

                # Handle resolution result
                if unresolved and raise_errors:
                    raise SessionError(
                        f"Failed to resolve all references for resource type "
                        f"{entity.__name__!r}."
                    )

                for entry_hash, entries in mapping.items():
                    if entry_hash in unresolved:
                        continue
                    self.unresolved[entity] -= set(entries)
                    self.resolved[entity] |= set(entries)


# MARK: Utilities

def generate_hash(value: BulkValue) -> BulkHash:
    """Generate a hash for the provided value."""
    hash_dict = {**value}

    for hash_key, hash_value in hash_dict.items():
        if not hasattr(hash_value, 'id'):
            continue
        hash_dict[hash_key] = getattr(hash_value, 'id')

    return hash(frozenset(hash_dict.items()))


def _build_resolution_map_and_conditions(
    entity: 'ResourceType',
    *entries: BulkEntry,
) -> tuple[BulkMap, BulkConditions]:
    """Build bulk entity resolution map and conditions.

    It constructs a bulk resolution map and conditions for the given entity
    resource type and the provided entries to resolve. The entries can be
    either resource references or values.

    Args:
        entity: The resource type to resolve the entries for.
        entries: The bulk reference or value entries to resolve.

    Returns:
        A tuple with the bulk entity resolution map and conditions.
    """
    identifying_fields = set.union(*entity.resource_identifiers)

    # Helper function to check if a set of fields is an identifier
    def is_identifier(signature: BulkSignature) -> bool:
        for identifier in entity.resource_identifiers:
            if signature.issuperset(identifier):
                return True
        return False

    # Build mapping and conditions
    conditions: BulkConditions = {}
    mapping: BulkMap = {}

    for entry in entries:
        entry_fields = frozenset(
            field for field in entry.instance.resource_fields_set
            if field in identifying_fields
        )

        # Compute entry value and hash
        entry_value = {
            name: getattr(entry.instance, name)
            for name in entry_fields
        }
        entry_hash = generate_hash(entry_value)

        # Update mapping
        if entry_hash in mapping:
            mapping[entry_hash].append(entry)
            continue  # Skip conditions update
        else:
            mapping[entry_hash] = [entry]

        # Skip entries without identifiers
        if not is_identifier(entry_fields):
            continue

        # Update conditions
        if entry_fields in conditions:
            conditions[entry_fields].append(entry_value)
        else:
            conditions[entry_fields] = [entry_value]

    return mapping, conditions


def _build_resolution_process(
    entity: 'ResourceType',
    conditions: BulkConditions,
    *,
    strategy: Literal['bind', 'hydrate'] = 'bind',
) -> BulkProcess:
    """Build bulk entity resolution process.

    Args:
        entity: The resource type to resolve the entries for.
        conditions: The bulk conditions to resolve.
        strategy: The resolution strategy to use, it can be either:
            - ``'bind'``: Bind the resolved resource references and values to
                the database session, i.e. only the resolved `id` and `type_`
                fields are updated and the instances are made transient to
                detached.
            - ``'hydrate'``: Hydrate the resolved resource references and
                values with the data fetched from the database, i.e. the
                instances are updated with the fetched data.
            Defaults to ``'bind'``.

    Returns:
        A list of tuple with the bulk entity resolution process.
    """
    process = []

    # Build identifier fields
    identifying_attrs = tuple(
        entity.resource_attributes[field] for field in ('id', 'type_')
    )

    for fields, values in conditions.items():
        # Build query conditions
        query_conditions = []
        for value in values:
            query_conditions.append(and_(*(
                getattr(entity, name) == value[name] for name in fields
            )))

        # Build query
        query = select(entity).where(or_(*query_conditions))
        if strategy == 'bind':
            query = query.options(load_only(*identifying_attrs))

        process.append((fields, query))

    return process


def _handle_resolution_query(
    entity: 'ResourceType',
    mapping: BulkMap,
    result: BulkResult,
    *,
    raise_errors: bool = True,
    strategy: Literal['bind', 'hydrate'] = 'bind',
) -> set[int]:
    """Handle a resolution query result for the bulk manager.

    It handles the resolution query result for the bulk manager by updating the
    corresponding resource references and values with the resolved identifiers.

    Args:
        entity: The resource type to resolve the entries for.
        mapping: The associated bulk entries map to handle.
        result: The resolution query result to handle.
        raise_errors: Whether to raise errors when failing to resolve a
            reference or value for a resource type. Defaults to ``True``.
        strategy: The resolution strategy to use, it can be either:
            - ``'bind'``: Bind the resolved resource references and values to
                the database session, i.e. only the resolved `id` and `type_`
                fields are updated and the instances are made transient to
                detached.
            - ``'hydrate'``: Hydrate the resolved resource references and
                values with the data fetched from the database, i.e. the
                instances are updated with the fetched data.
            Defaults to ``'bind'``.

    Returns:
        A set of resolved reference and value hashes.
    """
    fields, buffer = result
    data = buffer.unique().fetchall()

    resolved: set[int] = set()

    for record in data:
        # Unpack record
        assert len(record) == 1, "Expected a single mapped column."
        record = record[0]

        # Retrieve record value and hash
        record_value = {name: getattr(record, name) for name in fields}
        record_hash = generate_hash(record_value)

        # Validate record hash
        if record_hash not in mapping:
            if not raise_errors:
                continue
            raise SessionError(
                f"A resolved entry with hash {record_hash!r} and value "
                f"{record_value!r} was not found in the provided mapping."
            )

        # Update resolved entries
        for entry in mapping[record_hash]:
            if entry.is_reference:
                setattr(entry.instance, '__proxy_target__', record)
            else:
                for name in entity.resource_fields.keys():
                    if name not in ('id', 'type_') \
                            and name in entry.instance.resource_fields_set:
                        continue
                    entry.instance.__dict__[name] = getattr(record, name)
                if strategy == 'bind':
                    make_transient_to_detached(entry.instance)

        resolved.add(record_hash)

    return resolved


def _setup_resolution_queue(
    data: BulkData,
    *,
    scope: Literal['all', 'references', 'values'] = 'all',
    strategy: Literal['bind', 'hydrate'] = 'bind',
) -> list[tuple['ResourceType', BulkMap, BulkProcess]]:
    """Setup a resolution queue for the bulk manager.

    It constructs the resolution queue for the bulk manager by building the
    resolution map and relative process for all unresolved resource entries.

    Args:
        data: The bulk data to resolve.
        scope: The scope of the resources to resolve, it can be either:
            - ``'all'``: Resolve both the resource references and values.
            - ``'references'``: Resolve only the resource references.
            - ``'values'``: Resolve only the resource values.
            Defaults to ``'all'``.
        strategy: The resolution strategy to use, it can be either:
            - ``'bind'``: Bind the resolved resource references and values to
                the database session, i.e. only the resolved `id` and `type_`
                fields are updated and the instances are made transient to
                detached.
            - ``'hydrate'``: Hydrate the resolved resource references and
                values with the data fetched from the database, i.e. the
                instances are updated with the fetched data.
            Defaults to ``'bind'``.

    Returns:
        A list of tuples containing the resource types and their corresponding
        resolution map and process to resolve.
    """
    queue = []

    for entity, entries in data.items():
        # Filter entries by scope
        if scope == 'references':
            entries = {entry for entry in entries if entry.is_reference}
        elif scope == 'values':
            entries = {entry for entry in entries if not entry.is_reference}

        # Build resolution map and process
        mapping, conditions = _build_resolution_map_and_conditions(
            entity, *entries
        )
        process = _build_resolution_process(
            entity, conditions, strategy=strategy
        )

        queue.append((entity, mapping, process))

    return queue
