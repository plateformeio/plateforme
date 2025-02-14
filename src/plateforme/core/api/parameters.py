# plateforme.core.api.parameters
# ------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing parameters within the Plateforme
framework's API using FastAPI and Starlette features.
"""

from typing import Any, Literal, Unpack

from fastapi.param_functions import (
    Body,
    Cookie,
    Depends,
    File,
    Form,
    Header,
    Path,
    Query,
    Security,
)
from fastapi.params import (
    Body as BodyInfo,
    Cookie as CookieInfo,
    Depends as DependsInfo,
    File as FileInfo,
    Form as FormInfo,
    Header as HeaderInfo,
    Path as PathInfo,
    Query as QueryInfo,
    Security as SecurityInfo,
)

from ..schema.fields import BaseFieldInfoDict
from ..selectors import Key

__all__ = (
    'Body',
    'BodyInfo',
    'Cookie',
    'CookieInfo',
    'Depends',
    'DependsInfo',
    'File',
    'FileInfo',
    'Form',
    'FormInfo',
    'Header',
    'HeaderInfo',
    'Path',
    'PathInfo',
    'Payload',
    'PayloadInfo',
    'Query',
    'QueryInfo',
    'Security',
    'SecurityInfo',
    'Selection',
    'SelectionInfo',
)


class PayloadInfo(BodyInfo):
    """A resource payload information for an endpoint parameter."""

    __slots__ = (
        'apply_selection',
        'on_conflict',
    )

    def __init__(
        self,
        *,
        apply_selection: bool = True,
        on_conflict: Literal['lax', 'omit', 'raise'] = 'raise',
        **kwargs: Unpack[BaseFieldInfoDict],
    ):
        super().__init__(..., **kwargs)  # type: ignore
        self.apply_selection = apply_selection
        self.on_conflict = on_conflict


def Payload(
    *,
    apply_selection: bool = False,
    on_conflict: Literal['lax', 'omit', 'raise'] = 'raise',
    **kwargs: Unpack[BaseFieldInfoDict],
) -> Any:
    """Create a resource payload information for an endpoint parameter.

    Used to mark an endpoint parameter as a resource payload field and provide
    extra information about the parameter. Only one payload parameter is
    allowed per endpoint, and no default value is accepted.

    The payload parameter annotation content type must be a valid schema model
    from the resource it will be evaluated against at runtime.

    Args:
        apply_selection: A flag indicating whether to apply selection fields
            values to the payload. Defaults to ``False``.
        on_conflict: The selection conflict handling mode for the parameter. It
            determines how selection fields in the payload are handled when
            they conflict with the selection values:
            - ``'lax'``: Allow the payload to contain selection fields.
            - ``'omit'``: Omit payload entries that contain selection fields.
            - ``'raise'``: Raise an error if a selection field is present in
                the payload.
            Defaults to ``raise``.
        **kwargs: Additional keyword arguments. See the field information
            configuration dictionary `BaseFieldInfoDict` for more information
            on the expected keyword arguments.

    Returns:
        The payload information instance for the endpoint parameter.
    """
    return PayloadInfo(
        apply_selection=apply_selection,
        on_conflict=on_conflict,
        **kwargs,
    )


class SelectionInfo(BodyInfo):
    """A resource selection information for an endpoint parameter."""

    def __init__(self,  **kwargs: Unpack[BaseFieldInfoDict]):
        super().__init__(default=Key(), **kwargs)  # type: ignore


def Selection(**kwargs: Unpack[BaseFieldInfoDict]) -> Any:
    """Create a resource selection information for an endpoint parameter.

    Used to mark an endpoint parameter as a resource selection field and
    provide extra information about the parameter. Only one selection parameter
    is allowed per endpoint, and no default value is accepted.

    Args:
        **kwargs: Additional keyword arguments. See the field information
            configuration dictionary `BaseFieldInfoDict` for more information
            on the expected keyword arguments.
    """
    return SelectionInfo(**kwargs)
