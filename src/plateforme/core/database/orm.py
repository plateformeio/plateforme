# plateforme.core.database.orm
# ----------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing database object-relational mapping
(ORM) capabilities within the Plateforme framework using SQLAlchemy features.
"""

from typing import Literal

from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.ext.mutable import Mutable
from sqlalchemy.orm import (
    ClassManager,
    ColumnProperty as ColumnProperty,
    DeclarativeMeta,
    InstanceState,
    InstrumentedAttribute,
    Mapped,
    Mapper,
    Query,
    RelationshipProperty as RelationshipProperty,
    make_transient,
    make_transient_to_detached,
    registry as Registry,
    relationship as Relationship,
    with_polymorphic,
)
from sqlalchemy.orm.attributes import (
    set_attribute as set_instrumented_value,
    set_committed_value,
)
from sqlalchemy.orm.collections import (
    InstrumentedDict,
    InstrumentedList,
    InstrumentedSet,
)
from sqlalchemy.orm.instrumentation import is_instrumented
from sqlalchemy.orm.interfaces import ORMOption
from sqlalchemy.orm.strategy_options import (
    Load,
    contains_eager,
    defaultload,
    defer,
    immediateload,
    joinedload,
    lazyload,
    load_only,
    noload,
    raiseload,
    selectin_polymorphic,
    selectinload,
    subqueryload,
    undefer,
    undefer_group,
    with_expression,
)

__all__ = (
    'AsyncAttrs',
    'CascadeRule',
    'ClassManager',
    'ColumnProperty',
    'DeclarativeMeta',
    'InstanceState',
    'InstrumentedAttribute',
    'InstrumentedDict',
    'InstrumentedList',
    'InstrumentedSet',
    'Load',
    'LoadRule',
    'Mapped',
    'Mapper',
    'Mutable',
    'ORMOption',
    'Query',
    'Registry',
    'Relationship',
    'RelationshipProperty',
    'contains_eager',
    'defaultload',
    'defer',
    'immediateload',
    'is_instrumented',
    'joinedload',
    'lazyload',
    'load_only',
    'make_transient',
    'make_transient_to_detached',
    'noload',
    'raiseload',
    'selectin_polymorphic',
    'selectinload',
    'set_committed_value',
    'set_instrumented_value',
    'subqueryload',
    'undefer',
    'undefer_group',
    'with_expression',
    'with_polymorphic',
)


CascadeRule = Literal[
    'all',
    'delete',
    'delete-orphan',
    'expunge',
    'merge',
    'refresh-expire',
    'save-update',
]
"""A type alias for the cascade rules that can be used in relationships. The
``'all'`` option indicates a shorthand that is equivalent to the following
``'save-update, merge, refresh-expire, expunge, delete'``."""


LoadRule = Literal[
    'joined',
    'noload',
    'select',
    'selectin',
    'raise',
    'raise_on_sql',
    'write_only',
]
"""A type alias for the load rules that can be used in relationships."""
