# plateforme.core.api.authentication
# ----------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing authentication within the
Plateforme framework's API using FastAPI and Starlette features.
"""

import dataclasses
from abc import ABC, abstractmethod
from typing import Annotated, Any

from starlette.authentication import requires
from typing_extensions import override

from ..schema.aliases import AliasChoices
from ..schema.fields import Field
from ..schema.models import BaseModel

__all__ = (
    'BaseUser',
    'AuthClaim',
    'AuthCredentials',
    'AuthUser',
    'GuestUser',
    'requires',
)


class AuthClaim(BaseModel, extra='allow', frozen=True):
    """An authentication claim.

    This claim is used for JSON Web Token (JWT) authentication. It follows
    the RFC 7519 JSON Web Token specification for authentication and helps
    to validate and verify the integrity of the token data.

    Note:
        See JSON Web Token (JWT) specification for more details:
        https://www.rfc-editor.org/rfc/rfc7519
    """

    issuer: Annotated[str | None, 'secure'] = Field(
        default=None,
        validation_alias=AliasChoices('iss', 'issuer'),
        serialization_alias='iss',
        title='Issuer',
        description='The principal that issued the token.',
        repr=False,
        min_length=2,
        max_length=128,
    )

    subject: Annotated[str | None, 'secure'] = Field(
        default=None,
        validation_alias=AliasChoices('sub', 'subject'),
        serialization_alias='sub',
        title='Subject',
        description='The principal identifier whom the token refers to.',
        repr=False,
        min_length=2,
        max_length=128,
    )

    audience: Annotated[list[str] | str | None, 'secure'] = Field(
        default=None,
        validation_alias=AliasChoices('aud', 'audience'),
        serialization_alias='aud',
        title='Audience',
        description='The audience that the token is intended for.',
        repr=False,
        min_length=2,
        max_length=128,
    )

    expiration: Annotated[int | None, 'secure'] = Field(
        default=None,
        validation_alias=AliasChoices('exp', 'expiration'),
        serialization_alias='exp',
        title='Expiration time',
        description='An expiration timestamp for the token.',
        repr=False,
    )

    not_before: Annotated[int | None, 'secure'] = Field(
        default=None,
        validation_alias=AliasChoices('nbf', 'not_before'),
        serialization_alias='nbf',
        title='Not before',
        description='A timestamp when the token is valid from.',
        repr=False,
    )

    issued_at: Annotated[int | None, 'secure'] = Field(
        default=None,
        validation_alias=AliasChoices('iat', 'issued_at'),
        serialization_alias='iat',
        title='Issued at',
        description='A timestamp when the token was issued.',
        repr=False,
    )

    token_id: Annotated[str | None, 'secure'] = Field(
        default=None,
        validation_alias=AliasChoices('jti', 'jwt_id', 'token_id'),
        serialization_alias='jti',
        title='Token identifier',
        description='The access token identifier.',
        repr=False,
        min_length=2,
        max_length=255,
    )

    scope: str | None = Field(
        default=None,
        validation_alias=AliasChoices('scp', 'scope'),
        serialization_alias='scp',
        title='Scope',
        description='The permission scopes of the token (space-separated).',
        min_length=2,
        max_length=1024,
    )

    name: str = Field(
        ...,
        title='Principal',
        description='The principal name whom the token refers to.',
        min_length=2,
        max_length=255,
    )

    roles: list[str] | None = Field(
        default=None,
        title='Roles',
        description='The roles assigned to the principal.',
    )

    @property
    def scopes(self) -> list[str]:
        """The permission scopes of the token."""
        return self.scope.split() if self.scope is not None else []

    @override
    def model_dump(
        self, *, secure: bool | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Generate a dictionary representation of the authentication claim.

        Args:
            secure: A flag to indicate whether to include secure fields. If
                ``True``, only secure fields are included. If ``False``, only
                non-secure fields are included. If ``None``, all claim fields
                are included. Defaults to ``None``.
            **kwargs: Additional keyword arguments to pass to the model dump.
                See `BaseModel.model_dump` for more details.

        Returns:
            A dictionary representation of the authentication claim.
        """
        # Skip secure fields if not specified
        if secure is None:
            return super().model_dump(**kwargs)
        # Dump all fields and filter by secure flag
        result_dump = super().model_dump(**kwargs, by_alias=False)
        result = {}
        for field_name, field_value in result_dump.items():
            if field_name in self.model_fields:
                field_info = self.model_fields[field_name]
                if secure != ('secure' in field_info.metadata):
                    continue
            elif not secure and field_name in self.model_computed_fields:
                field_info = \
                    self.model_computed_fields[field_name]  # type: ignore
            else:
                continue
            if 'by_alias' in kwargs:
                result[field_info.alias] = field_value
            else:
                result[field_name] = field_value
        return result


@dataclasses.dataclass(frozen=True, slots=True)
class AuthCredentials:
    """A user credentials for the authentication middleware."""

    scopes: list[str] = dataclasses.field(default_factory=list)
    """The scopes of the authentication credentials."""


@dataclasses.dataclass(frozen=True, slots=True)
class BaseUser(ABC):
    """A base user for the authentication middleware."""

    @property
    @abstractmethod
    def is_authenticated(self) -> bool:
        raise NotImplementedError()

    @property
    @abstractmethod
    def display_name(self) -> str:
        raise NotImplementedError()


@dataclasses.dataclass(frozen=True, slots=True)
class AuthUser(BaseUser):
    """An authenticated user for the authentication middleware."""

    username: str
    """The username of the authenticated user."""

    roles: list[str] | None = dataclasses.field(default=None, kw_only=True)
    """The roles of the authenticated user."""

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self.username


@dataclasses.dataclass(frozen=True, slots=True)
class GuestUser(BaseUser):
    """A guest user for the authentication middleware."""

    @property
    def is_authenticated(self) -> bool:
        return False

    @property
    def display_name(self) -> str:
        return ''
