# plateforme.core.context
# -----------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities to interact with the application context.
"""

import typing
from contextvars import ContextVar

if typing.TYPE_CHECKING:
    from .database.sessions import (
        AsyncSession,
        AsyncSessionBulk,
        Session,
        SessionBulk,
    )
    from .main import Plateforme
    from .schema.core import RecursionState, ValidationMode

__all__ = (
    'CALLER_CONTEXT',
    'FROZEN_CONTEXT',
    'PLATEFORME_CONTEXT',
    'RECURSION_CONTEXT',
    'SESSION_BULK_CONTEXT',
    'SESSION_CONTEXT',
    'VALIDATION_CONTEXT',
)


CALLER_CONTEXT: ContextVar[tuple[int, ...] | None] = \
    ContextVar('caller_stack', default=None)
"""The context variable for the current caller stack."""


FROZEN_CONTEXT: ContextVar[bool | None] = \
    ContextVar('protect_attributes', default=None)
"""The context variable for the frozen state of the application."""


PLATEFORME_CONTEXT: ContextVar['Plateforme | None'] = \
    ContextVar('current_app', default=None)
"""The context variable for the current application instance."""


RECURSION_CONTEXT: ContextVar['RecursionState | None'] = \
    ContextVar('recursive_guard', default=None)
"""The context variable for the recursive guard when validating."""


SESSION_BULK_CONTEXT: ContextVar['AsyncSessionBulk | SessionBulk | None'] \
    = ContextVar('current_session_bulk', default=None)
"""The context variable for the current async or sync session bulk."""


SESSION_CONTEXT: ContextVar['AsyncSession | Session | None'] \
    = ContextVar('current_session', default=None)
"""The context variable for the current async or sync session."""


VALIDATION_CONTEXT: ContextVar['ValidationMode | None'] = \
    ContextVar('validation_mode', default=None)
"""The context variable for the validation mode when initializing."""
