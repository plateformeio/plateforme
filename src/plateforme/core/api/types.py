# plateforme.core.api.types
# -------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides type hints for the Plateforme framework's API using
FastAPI and Starlette features.
"""

from starlette.types import ASGIApp, Lifespan, Message, Receive, Scope, Send

__all__ = (
    'ASGIApp',
    'Lifespan',
    'Message',
    'Receive',
    'Scope',
    'Send',
)
