# plateforme.core.api.status
# --------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing status codes within the Plateforme
framework's API using FastAPI and Starlette features.
"""

from typing import Literal

from starlette import status as status

all = (
    'StatusClass',
    'get_status_class',
    'status',
)


StatusClass = Literal['HTTP_1', 'HTTP_2', 'HTTP_3', 'HTTP_4', 'HTTP_5', 'WS_1']
"""A literal type representing the classes of status codes."""


def get_status_class(status_code: int) -> StatusClass | None:
    """Get the status code class for a given status code."""

    if 100 <= status_code < 200:
        return 'HTTP_1'
    elif 200 <= status_code < 300:
        return 'HTTP_2'
    elif 300 <= status_code < 400:
        return 'HTTP_3'
    elif 400 <= status_code < 500:
        return 'HTTP_4'
    elif 500 <= status_code < 600:
        return 'HTTP_5'
    elif 1000 <= status_code < 1100:
        return 'WS_1'

    return None
