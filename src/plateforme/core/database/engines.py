# plateforme.core.database.engine
# -------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing database engines within the
Plateforme framework using SQLAlchemy features.
"""

from sqlalchemy.engine import (
    Connection,
    Dialect,
    Engine,
    MappingResult,
    Result,
    Row,
    ScalarResult,
    Transaction,
    TupleResult,
    create_engine,
    create_mock_engine,
    engine_from_config,
)
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncMappingResult,
    AsyncResult,
    AsyncScalarResult,
    AsyncTransaction,
    AsyncTupleResult,
    async_engine_from_config,
    create_async_engine,
)

__all__ = (
    # Async
    'AsyncConnection',
    'AsyncEngine',
    'AsyncMappingResult',
    'AsyncResult',
    'AsyncScalarResult',
    'AsyncTransaction',
    'AsyncTupleResult',
    'async_engine_from_config',
    'create_async_engine',
    # Sync
    'Connection',
    'Dialect',
    'Engine',
    'MappingResult',
    'Result',
    'Row',
    'ScalarResult',
    'Transaction',
    'TupleResult',
    'create_engine',
    'create_mock_engine',
    'engine_from_config',
)
