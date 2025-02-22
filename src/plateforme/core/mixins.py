# plateforme.core.mixins
# ----------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides resource mixin classes for the Plateforme framework.
"""

__all__ = (
    'Archivable',
    'Auditable',
    'Encrypted',
)

from datetime import datetime, timezone

from .resources import BaseResource
from .schema.fields import Field


class Archivable:
    """Archivable mixin for resource class.

    FUTURE: Implement archivable mixin for resource class.
    """
    pass


class Auditable(BaseResource):
    """Auditable mixin for resource class.

    FIXME: Implement auditable mixin for resource class.
    """

    __abstract__ = True

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        title="Created at",
        description="Date and time the resource was created.",
        examples=["2023-01-01T00:00:00Z"],
        init=False,
        frozen=True,
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        title="Updated at",
        description="Date and time the resource was last updated.",
        examples=["2023-01-01T00:00:00Z"],
        init=False,
    )
    created_by: str | None = Field(
        default=None,
        title="Created by",
        description="User who created the resource.",
        examples=['admin', '123456'],
        init=False,
        frozen=True,
    )
    updated_by: str | None = Field(
        default=None,
        title="Updated by",
        description="User who last updated the resource.",
        examples=['admin', '123456'],
    )


class Encrypted:
    """Encrypted mixin for resource class.

    FUTURE: Implement encrypted mixin for resource class.
    """
    pass
