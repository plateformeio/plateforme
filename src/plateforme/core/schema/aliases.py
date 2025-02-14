# plateforme.core.schema.aliases
# ------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing schema aliases within the
Plateforme framework using Pydantic features.
"""

import dataclasses
from typing import Callable, Literal

from pydantic.aliases import (
    AliasChoices as _AliasChoices,
    AliasGenerator as _AliasGenerator,
    AliasPath as _AliasPath,
)

__all__ = (
    'AliasChoices',
    'AliasGenerator',
    'AliasPath',
)


@dataclasses.dataclass(slots=True)
class AliasPath(_AliasPath):
    """A data class to specify a path to a model field using aliases.

    This class is used in models and resources to specify a path to a field
    using aliases. It is typically used for indexing into nested data
    structures like lists or dictionaries within JSON payloads.

    Attributes:
        path: A list representing the path to the target field using string
            keys for dictionary access or integer indices for list access.

    Examples:
        >>> from plateforme import BaseModel, Field
        >>> class User(BaseModel):
        ...     first_name: str = Field(validation_alias=AliasPath('names', 0))
        ...     last_name: str = Field(validation_alias=AliasPath('names', 1))

        >>> user_data = {'names': ['John', 'Doe']}
        >>> user = User.model_validate(user_data)

        >>> print(user)
        first_name='John' last_name='Doe'
    """

    path: list[int | str]

    def __init__(self, entry: str | int, *extra: str | int) -> None:
        self.path = [entry] + list(extra)

    def convert_to_alias(self) -> str:
        """Converts arguments to an alias string.

        It joins the path elements with underscores to create a single string
        representing the alias path.

        Returns:
            The alias path as an alias string.
        """
        return '_'.join(map(str, self.path))

    def __repr__(self) -> str:
        repr_name = self.__class__.__name__
        repr_args = ', '.join(map(repr, self.path))
        return f'{repr_name}({repr_args})'

    def __str__(self) -> str:
        return str(self.path)


@dataclasses.dataclass(slots=True)
class AliasChoices(_AliasChoices):
    """A data class to specify a list of possible aliases for a model field.

    This class is used in models and resources to specify one or multiple
    possible aliases for a field, allowing the model to accept different
    payload structures with variable field names but identical meanings.

    Attributes:
        choices: A list of strings representing the alternative names for the
            model field. It can also include `AliasPath` objects for more
            complex aliasing scenarios.

    Examples:
        >>> from plateforme import BaseModel, Field
        >>> class User(BaseModel):
        ...     first_name: str = Field(
        ...         validation_alias=AliasChoices('first_name', 'fname'))
        ...     last_name: str = Field(
        ...         validation_alias=AliasChoices('last_name', 'lname'))

        >>> user_data = {'fname': 'John', 'lname': 'Doe'}
        >>> user = User.model_validate(user_data)
        >>> print(user)
        first_name='John' last_name='Doe'

        >>> user_data_alt = {'first_name': 'John', 'lname': 'Doe'}
        >>> user = User.model_validate(user_data_alt)
        >>> print(user)
        first_name='John' last_name='Doe'
    """

    choices: list[str | AliasPath]  # type: ignore[assignment]

    def __init__(
        self, choice: str | AliasPath, *extra: str | AliasPath,
    ) -> None:
        self.choices = [choice] + list(extra)

    def convert_to_alias(self) -> str:
        """Converts arguments to an alias string.

        It returns the first choice as an alias string. If the first choice
        is an `AliasPath`, it converts it to an alias string.

        Returns:
            The first choice as an alias string.
        """
        first_choice = self.choices[0]
        if isinstance(first_choice, AliasPath):
            return first_choice.convert_to_alias()
        return str(first_choice)

    def __repr__(self) -> str:
        repr_name = self.__class__.__name__
        repr_args = ', '.join(map(repr, self.choices))
        return f'{repr_name}({repr_args})'

    def __str__(self) -> str:
        return str(self.choices)


@dataclasses.dataclass(slots=True)
class AliasGenerator(_AliasGenerator):
    """A data class used to specify generators to create various aliases.

    It is a class that allows to specify multiple alias generators for a models
    and resources. It can be used to specify different alias generators for
    ``validation`` and ``serialization``.

    This is particularly useful in scenarios where it is necessary to generate
    different naming conventions for loading and saving data, but it is not
    desired to specify the validation and serialization aliases for each field
    individually.

    Attributes:
        alias: A callable that takes a field name and returns an alias for it.
        validation_alias: A callable that takes a field name and returns a
            validation alias for it.
        serialization_alias: A callable that takes a field name and returns a
            serialization alias for it.
    """

    alias: Callable[[str], str] | None = None
    validation_alias: Callable[
        [str], str | AliasPath | AliasChoices
    ] | None = None
    serialization_alias: Callable[[str], str] | None = None

    def _generate_alias(  # type: ignore[override, unused-ignore]
        self,
        alias_kind: \
            Literal['alias', 'validation_alias', 'serialization_alias'],
        allowed_types: \
            tuple[type[str] | type[AliasPath] | type[AliasChoices], ...],
        field_name: str,
    ) -> str | AliasPath | AliasChoices | None:
        """Generate an alias of the specified kind.

        It returns ``None`` if the alias generator is not defined.

        Raises:
            TypeError: If the alias generator produces an invalid type.
        """
        alias = None
        if alias_generator := getattr(self, alias_kind):
            alias = alias_generator(field_name)
            if alias and not isinstance(alias, allowed_types):
                raise TypeError(
                    f"Invalid type for generator {alias_kind!r}. It must "
                    f"produce one of {allowed_types!r}"
                )
        return alias

    def generate_aliases(self, field_name: str) -> tuple[
        str | None,
        str | AliasPath | AliasChoices | None,
        str | None
    ]:
        """Generate aliases for a field.

        It generates `alias`, `validation_alias`, and `serialization_alias`
        for a field using the class generators.

        Returns:
            A tuple of three aliases - validation, alias, and serialization.
        """
        alias = self._generate_alias('alias', (str,), field_name)
        validation_alias = self._generate_alias(
            'validation_alias', (str, AliasChoices, AliasPath), field_name
        )
        serialization_alias = self._generate_alias(
            'serialization_alias', (str,), field_name
        )

        return alias, validation_alias, serialization_alias  # type: ignore
