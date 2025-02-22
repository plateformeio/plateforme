# plateforme.core.environment
# ---------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module contains utilities for managing environment variables and files
within the Plateforme framework.

The `Environment` class simplifies the management of environment variables, it
offers methods to load variables from dictionaries and files, set and retrieve
environment variables with support for default values and type casting, and
delete variables. It also ensures that variable names adhere to valid patterns
and provides internal mechanisms to avoid circular references when resolving
proxy variables. Additionally, the class includes methods for casting
environment variables to specific data types such as boolean, bytes,
dictionaries, floats, integers, JSON, lists, sets, strings, tuples, and URLs.

Examples:
    Initialize with optional environment mode and variables:
    >>> from plateforme import Environment
    >>> env = Environment(mode='dev', variables={'TITLE': 'My Plateforme'})

    Retrieve an environment variable with optional casting and default:
    >>> debug = env.get_variable('DEBUG', default=True, cast=bool)
    >>> print(debug)
    True

    Set an environment variable:
    >>> env.set_variable('DEBUG', 'False')
    >>> print(env.get_variable('DEBUG'))
    'False'

    Delete an environment variable:
    >>> env.delete_variable('DEBUG')
    >>> print(env.get_variable('DEBUG', default=None))
    None

    This demonstrates the basic functionality of getting, setting, and
    deleting environment variables using the `Environment` class. Note that
    changes to environment variables using `set_variable` and `delete_variable`
    will affect the environment for the current process and any new child
    processes spawned after the change.

Note:
    It loads environment files using the external library `python-dotenv`.
"""

import json
import os
import re
import typing
from collections.abc import Iterable, Iterator
from typing import Any
from urllib.parse import ParseResult, urlparse

from dotenv import dotenv_values

from .typing import CastFunc, CastObject, Undefined, UndefinedType

__all__ = (
    'Environment',
)


class Environment(Iterable[str]):
    """An environment class to manage environment variables and files.

    Examples:
        >>> from plateforme import Environment
        >>> env = Environment()

    Note:
        The environment class can be used as a namespace to get, set, and
        delete environment variables. Initializing the environment class will
        load the environment variables from the os environment, and the
        environment files found in the process root directory with the
        following order priority (from highest to lowest):
        - The environment ``.env.{mode}.local`` local specific mode file,
        - The environment ``.env.{mode}`` specific mode file,
        - The environment ``.env.local`` local common file,
        - The environment ``.env`` common file.

    Note:
        Specific mode files are loaded based on the environment mode provided:
        - ``'dev'`` and ``'development'`` for development mode,
        - ``'prod'`` and ``'production'`` for production mode,
        - or any other mode name for specific mode.
    """
    namespace: dict[str, str] = {}

    def __init__(
        self,
        mode: str | None = None,
        /,
        files: list[str] | None = None,
        variables: dict[str, str | None] | None = None,
        encoding: str | None = 'utf-8',
        overwrite: bool = False,
    ) -> None:
        """Initialize the environment.

        Args:
            mode: The environment mode. If the mode is not provided, the
                environment mode will be loaded with the value of the
                ``PLATEFORME_ENV`` environment variable, or ``development`` if
                it is not set.
            files: The default environment files to load. The files will be
                loaded in the order they are provided, from lowest to highest
                priority. Defaults to ``None``.
            variables: The default environment variables to load.
                Defaults to ``None``.
            encoding: The encoding of the environment files to load. Defaults
                to ``utf-8``.
            overwrite: Whether to overwrite existing environment variables in
                the namespace with the same key. The overwrite parameter is
                used to determine whether to overwrite existing environment
                variables in the namespace with the same key. If the overwrite
                parameter is set to ``True``, as a side effect, the environment
                variables loading order priority will be reversed.
                Defaults to ``False``.

        Note:
            The environment variables will be loaded with the following
            order priority (from highest to lowest):
            - The os environment variables
            - The environment ``.env.{mode}`` specific mode file
            - The environment ``.env`` common file
            - The default environment files provided in the constructor
            - The default environment variables provided in the constructor
        """
        self.load(
            mode,
            files=files,
            variables=variables,
            encoding=encoding,
            overwrite=overwrite,
        )

    def __call__(
        self,
        key: str,
        /,
        default: Any = Undefined,
        parse_default: bool = False,
        cast: CastObject | None = None,
    ) -> Any:
        """Get an environment variable.

        Args:
            key: The environment variable key to get.
            default: The environment variable default value.
                Defaults to ``Undefined`` (no default value).
            parse_default: Whether to parse the default value with the
                environment variable cast object. Defaults to ``False``.
            cast: The environment variable cast object.
                Defaults to ``None`` (no cast process).

        Note:
            If the environment variable is not found and no default value is
            provided, a `KeyError` will be raised, else the default value will
            be eturned. If the environment variable is found but no cast object
            is provided, the environment variable value will be returned as a
            string.
        """
        return self.get_variable(
            key,
            default=default,
            parse_default=parse_default,
            cast=cast,
        )

    def clear(self) -> None:
        """Clear the environment namespace from all environment variables."""
        self.namespace.clear()

    def load(
        self,
        mode: str | None = None,
        /,
        files: list[str] | None = None,
        variables: dict[str, str | None] | None = None,
        encoding: str | None = 'utf-8',
        overwrite: bool = False,
        reset: bool = False,
    ) -> None:
        """Load the environment variables.

        Args:
            mode: The environment mode. If the mode is not provided, the
                environment mode will be loaded with the value of the
                ``PLATEFORME_ENV`` environment variable, or ``development`` if
                it is not set.
            files: The default environment files to load. The files will be
                loaded in the order they are provided, from lowest to highest
                priority. Defaults to ``None``.
            variables: The default environment variables to load.
                Defaults to ``None``.
            encoding: The encoding of the environment files to load. Defaults
                to ``utf-8``.
            overwrite: Whether to overwrite existing environment variables in
                the namespace with the same key. The overwrite parameter is
                used to determine whether to overwrite existing environment
                variables in the namespace with the same key. If the overwrite
                parameter is set to ``True``, as a side effect, the environment
                variables loading order priority will be reversed.
                Defaults to ``False``.
            reset: Whether to clear the environment namespace before loading
                the environment variables. Defaults to ``False``.

        Note:
            The environment variables will be loaded with the following
            order priority (from highest to lowest):
            - The os environment variables
            - The environment ``.env.{mode}`` specific mode file
            - The environment ``.env`` common file
            - The default environment files provided in the constructor
            - The default environment variables provided in the constructor
        """
        files = files or []
        variables = variables or {}

        # Clear the environment namespace if reset is True
        if reset:
            self.clear()

        # Retrieve the environment mode
        env_mode = mode if mode else os.getenv('PLATEFORME_ENV', 'development')

        # Retrieve the common and mode environment files
        env_files: list[str] = ['.env.local', '.env']
        if env_mode in ('dev', 'development'):
            env_mode = 'development'
            env_files.extend([
                '.env.dev.local',
                '.env.development.local',
                '.env.dev',
                '.env.development',
            ])
        elif env_mode in ('prod', 'production'):
            env_mode = 'production'
            env_files.extend([
                '.env.prod.local',
                '.env.production.local',
                '.env.prod',
                '.env.production',
            ])
        else:
            env_files.extend([
                f'.env.{env_mode}.local',
                f'.env.{env_mode}',
            ])

        # Initialize the environment namespace
        self.clear()
        self.load_from_variables(dict(**os.environ))
        self.load_from_files(env_files, encoding, overwrite)
        self.load_from_files(files, encoding, overwrite, raise_errors=True)
        self.load_from_variables(variables, overwrite)
        self.load_from_variables(dict(PLATEFORME_ENV=env_mode), overwrite=True)

    def get_variable(
        self,
        key: str,
        _guard: frozenset[str] = frozenset(),
        /,
        default: Any = Undefined,
        parse_default: bool = False,
        cast: CastObject | None = None,
    ) -> Any:
        """Get an environment variable.

        Args:
            key: The environment variable key to get.
            _guard: The environment guard set to avoid circular references
                when resolving accessed variables. Defaults to an empty set.
            default: The environment variable default value.
                Defaults to ``Undefined`` (no default value).
            parse_default: Whether to parse the default value with the
                environment variable cast object. Defaults to ``False``.
            cast: The environment variable cast object.
                Defaults to ``None`` (no cast process).

        Note:
            If the environment variable is not found and no default value is
            provided, a `KeyError` will be raised, else the defaultvalue will
            be returned. If the environment variable is found but no cast
            object is provided, the environment variable value will be returned
            as a string.
        """
        # Check if the key is valid
        self.check_key(key, raise_errors=True)

        # Retrieve environment variable
        if key not in self.namespace:
            if default is Undefined:
                raise KeyError(
                    f"Invalid environment variable, {key!r} is not found in "
                    f"the environment variables. To avoid this error, you can "
                    f"use the environment `get` method and provide a "
                    f"`default` value."
                )
            value = default
        else:
            value = self.namespace[key]

        # Resolve proxies
        def _resolve_proxy(match: re.Match[str]) -> str:
            prefix = match.group(1)
            suffix = match.group(2).strip('{}')
            if prefix == '\\':
                # Proxy is escaped
                return f'${suffix}'
            if self.check_key(suffix):
                # Proxy variable name is valid
                if suffix in _guard:
                    raise ValueError(
                        f"Recursion error while resolving proxy variable "
                        f"{match.group(0)!r} found in environment variable "
                        f"{key!r}."
                    )
                return str(self.get_variable(suffix, _guard | {key}))
            else:
                # Proxy variable name is invalid
                raise KeyError(
                    f"Invalid proxy variable name {match.group(0)!r} found in "
                    f"environment variable {key!r}."
                )
        # For each match of the dollar sign "$" in the retrieved value, check
        # the prefix and suffix string to resolve either to a proxy variable or
        # an escaped dollar sign.
        if isinstance(value, str):
            value = re.sub(r'(\\?)\$(\{.*\}|\w*)', _resolve_proxy, value)
        # Handle empty value
        value = None if value == '' and default is None else value

        # Retrieve cast from default value if not provided
        if cast is None and default not in (Undefined, None):
            cast = type(default)
        # Parse value
        if value != default or (parse_default and value is not None):
            value = self.parse(value, cast)

        return value

    def set_variable(self, key: str, value: str) -> None:
        """Set an environment variable.

        Args:
            key: The environment variable key to set.
            value: The environment variable value to set.
        """
        # Check if the key is valid
        self.check_key(key, raise_errors=True)
        # Set the environment variable
        self.namespace[key] = value

    def set_default(self, key: str, default: str) -> str:
        """Set an environment variable if it is not already set.

        Args:
            key: The environment variable key to set.
            default: The environment variable default value to set.
        """
        # Check if the key is valid
        self.check_key(key, raise_errors=True)
        # Set the environment variable if it is not already set
        return self.namespace.setdefault(key, default)

    def delete_variable(self, key: str) -> None:
        """Delete an environment variable.

        Args:
            key: The environment variable key to delete.
        """
        # Check if the key is valid
        self.check_key(key, raise_errors=True)
        # Delete the environment variable
        del self.namespace[key]

    def load_from_variables(
        self,
        variables: dict[str, str | None],
        /,
        overwrite: bool = False,
    ) -> None:
        """Load environment variables from an environment dictionary.

        Args:
            variables: The environment variables to load into the namespace.
            overwrite: Whether to overwrite existing environment variables in
                the namespace with the same key. Defaults to ``False``.
        """
        self.namespace.update({
            key: str(value)
            for key, value in variables.items()
            if (self.check_key(key, raise_errors=True)
                and value is not None
                and (overwrite or key not in self.namespace))
        })

    def load_from_files(
        self,
        files: list[str],
        /,
        encoding: str | None = 'utf-8',
        overwrite: bool = False,
        raise_errors: bool = False,
    ) -> None:
        """Load environment variables from multiple environment files.

        Args:
            files: The environment files path to load into the namespace.
            encoding: The encoding of the environment files to load. Defaults
                to ``utf-8``.
            overwrite: Whether to overwrite existing environment variables in
                the namespace with the same key. Defaults to ``False``.
            raise_errors: Whether to raise an error if a file is not found.
                Defaults to ``False``.
        """
        for file in files:
            if file and os.path.isfile(file):
                self.load_from_variables(
                    dotenv_values(file, encoding=encoding),
                    overwrite=overwrite,
                )
            elif raise_errors:
                raise ValueError(
                    f"Invalid environment file path, {file!r} is not found."
                )

    @classmethod
    def check_key(cls, key: str, /, raise_errors: bool = False) -> bool:
        """Check if an environment variable key is valid.

        Args:
            key: The environment variable key to check.
            raise_errors: Whether to raise an error if the key is invalid.
                Defaults to ``False``.
        """
        # Check if the key is a valid environment variable name
        check = re.match(r'^[a-zA-Z_][\w\(\)]*$', key) is not None
        # Raise an error or return
        if raise_errors and not check:
            raise KeyError(
                f"Invalid environment variable name {key!r}. The environment "
                f"variable name must match the regular expression "
                f"`^[a-zA-Z_][a-zA-Z0-9_]*$`."
            )
        return check

    @classmethod
    def parse(
        cls,
        value: str,
        cast: CastObject | None = None,
    ) -> Any:
        """Parse a string value with the provided cast object.

        Args:
            value: The value to parse.
            cast: The cast object. Defaults to ``None`` (no cast process).

        Note:
            If no cast object is provided, the value will be returned as is.
            Otherwise, the value will be casted using the cast object if it a
            function, else the cast object will be analyzed as an iterable
            instance. The value will be split using the comma separator and
            each resulting value will be casted using the cast function
            provided by the first element of the iterable cast object.
        """
        # Return value if no cast object is provided
        if cast is None:
            return value

        # Instance of dictionary cast functions
        if isinstance(cast, dict):
            values = value.split(',')
            cast_key = cast.get('key', str)
            cast_value = cast.get('value', str)
            cast_value_by_key = cast.get('cast', {})
            return dict(map(
                lambda kv: (
                    cast_key(kv[0]),
                    cls.parse(
                        kv[1],
                        cast_value_by_key.get(kv[0], cast_value)
                    )
                ),
                [v.split('=') for v in values if v]
            ))
        # Instance of list cast functions
        if isinstance(cast, list):
            values = value.split(',')
            return list(map(cast[0], [v for v in values if v]))
        # Instance of set cast functions
        if isinstance(cast, set):
            values = value.strip('{}').split(',')
            return set(map(next(iter(cast)), [v for v in values if v]))
        # Instance of tuple cast functions
        if isinstance(cast, tuple):
            values = value.strip('()').split(',')
            return tuple(map(cast[0], [v for v in values if v]))

        # Boolean cast function
        if cast is bool:
            try:
                return int(value) != 0
            except ValueError:
                return value.lower() in {'true', 'ok', 'on', 'y', 'yes', '1'}
        # Float cast function
        if cast is float:
            # Clean and split string value to avoid thousand separator and
            # different locale comma/dot symbol.
            value = re.sub(r'[^\d,.-]', '', value)
            parts = re.split(r'[,.]', value)
            if len(parts) == 1:
                value = parts[0]
            else:
                value = '{}.{}'.format(''.join(parts[0:-1]), parts[-1])
            return float(value)
        # Dictionary cast function
        if cast is dict:
            values = value.split(',')
            return dict([v.split('=', 1) for v in values if v])
        # List cast function
        if cast is list:
            values = value.split(',')
            return [v for v in values if v]
        # Set cast function
        if cast is set:
            values = value.strip('{}').split(',')
            return {v for v in values if v}
        # Tuple cast function
        if cast is tuple:
            values = value.strip('()').split(',')
            return tuple([v for v in values if v])

        # Use cast as a function if it is callable
        if callable(cast):
            return cast(value)

        # If no specific cast object is matched and the cast object is not a
        # callable, raise a TypeError.
        raise TypeError(
            f"Invalid cast object {cast!r} provided. The cast object does "
            f"not match any specific cast process. Consider providing a "
            f"specific cast object."
        )

    def as_bool(
        self,
        key: str,
        /,
        default: bool | None | UndefinedType = Undefined,
    ) -> bool:
        """Get an environment variable as a boolean.

        Args:
            key: The environment variable key to get.
            default: The environment variable default value.
                Defaults to ``Undefined`` (no default value).
        """
        value = self.get_variable(key, default=default, cast=bool)
        return typing.cast(bool, value)

    def as_bytes(
        self,
        key: str,
        /,
        default: bytes | None | UndefinedType = Undefined,
        encoding: str = 'utf-8',
    ) -> bytes:
        """Get an environment variable as bytes.

        Args:
            key: The environment variable key to get.
            default: The environment variable default value.
                Defaults to ``Undefined`` (no default value).
            encoding: The encoding of the bytes string. Defaults to ``utf-8``.
        """
        value = self.get_variable(key, default=default)
        return typing.cast(str, value).encode(encoding)

    def as_dict(
        self,
        key: str,
        /,
        default: dict[Any, Any] | None | UndefinedType = Undefined,
        cast: CastFunc | None = None,
    ) -> dict[Any, Any]:
        """Get an environment variable as a dictionary.

        Args:
            key: The environment variable key to get.
            default: The environment variable default value.
                Defaults to ``Undefined`` (no default value).
            cast: The environment variable cast function.
                Defaults to ``None`` (no cast process).
        """
        value = self.get_variable(
            key,
            default=default,
            cast=dict if not cast else dict(value=cast),
        )
        return typing.cast(dict[Any, Any], value)

    def as_float(
        self,
        key: str,
        /,
        default: float | None | UndefinedType = Undefined,
    ) -> float:
        """Get an environment variable as a float.

        Args:
            key: The environment variable key to get.
            default: The environment variable default value.
                Defaults to ``Undefined`` (no default value).
        """
        value = self.get_variable(key, default=default, cast=float)
        return typing.cast(float, value)

    def as_int(
        self,
        key: str,
        /,
        default: int | None | UndefinedType = Undefined,
    ) -> int:
        """Get an environment variable as an integer.

        Args:
            key: The environment variable key to get.
            default: The environment variable default value.
                Defaults to ``Undefined`` (no default value).
        """
        value = self.get_variable(key, default=default, cast=int)
        return typing.cast(int, value)

    def as_json(
        self,
        key: str,
        /,
        default: Any = Undefined,
    ) -> Any:
        """Get an environment variable as a boolean.

        Args:
            key: The environment variable key to get.
            default: The environment variable default value.
                Defaults to ``Undefined`` (no default value).
        """
        return self.get_variable(key, default=default, cast=json.loads)

    def as_list(
        self,
        key: str,
        /,
        default: list[Any] | None | UndefinedType = Undefined,
        cast: CastFunc | None = None,
    ) -> list[Any]:
        """Get an environment variable as a list.

        Args:
            key: The environment variable key to get.
            default: The environment variable default value.
                Defaults to ``Undefined`` (no default value).
            cast: The environment variable cast function.
                Defaults to ``None`` (no cast process).
        """
        value = self.get_variable(
            key,
            default=default,
            cast=list if not cast else [cast],
        )
        return typing.cast(list[Any], value)

    def as_set(
        self,
        key: str,
        /,
        default: set[Any] | None | UndefinedType = Undefined,
        cast: CastFunc | None = None,
    ) -> set[Any]:
        """Get an environment variable as a set.

        Args:
            key: The environment variable key to get.
            default: The environment variable default value.
                Defaults to ``Undefined`` (no default value).
            cast: The environment variable cast function.
                Defaults to ``None`` (no cast process).
        """
        value = self.get_variable(
            key,
            default=default,
            cast=set if not cast else {cast},
        )
        return typing.cast(set[Any], value)

    def as_str(
        self,
        key: str,
        /,
        default: str | None | UndefinedType = Undefined,
        multiline: bool = False,
    ) -> str | None:
        """Get an environment variable as a string.

        Args:
            key: The environment variable key to get.
            default: The environment variable default value.
                Defaults to ``Undefined`` (no default value).
            multiline: Whether to return the string as a multiline string. If
                the multiline parameter is set to ``True``, the string will be
                returned with the new line and carriage return characters
                replaced by the corresponding escape sequences.
                Defaults to ``False``.
        """
        value = self.get_variable(key, default=default)
        if multiline:
            return re.sub(r'(\\r)?\\n', r'\n', value)
        return typing.cast(str | None, value)

    def as_tuple(
        self,
        key: str,
        /,
        default: tuple[Any, ...] | None | UndefinedType = Undefined,
        cast: CastFunc | None = None,
    ) -> tuple[Any, ...]:
        """Get an environment variable as a tuple.

        Args:
            key: The environment variable key to get.
            default: The environment variable default value.
                Defaults to ``Undefined`` (no default value).
            cast: The environment variable cast function.
                Defaults to ``None`` (no cast process).
        """
        value = self.get_variable(
            key,
            default=default,
            cast=tuple if not cast else (cast,),
        )
        return typing.cast(tuple[Any, ...], value)

    def as_url(
        self,
        key: str,
        /,
        default: ParseResult | None | UndefinedType = Undefined,
    ) -> ParseResult:
        """Get an environment variable as a URL.

        Args:
            key: The environment variable key to get.
            default: The environment variable default value.
                Defaults to ``Undefined`` (no default value).
        """
        value = self.get_variable(
            key,
            default=default,
            parse_default=True,
            cast=urlparse,
        )
        return typing.cast(ParseResult, value)

    def __contains__(self, key: str) -> bool:
        return key in self.namespace

    def __iter__(self) -> Iterator[str]:
        yield from self.namespace

    def __reversed__(self) -> Iterator[str]:
        yield from reversed(self.namespace)

    def __len__(self) -> int:
        return len(self.namespace)

    def __getitem__(self, key: str) -> str:
        # If the environment variable is not found, a "KeyError" will be
        # raised. Consider using the environment "get" method instead and
        # provide a default value if you want to avoid this error.
        return str(self.get_variable(key))

    def __setitem__(self, key: str, value: str) -> None:
        self.set_variable(key, value)

    def __delitem__(self, key: str) -> None:
        self.delete_variable(key)

    def __repr__(self) -> str:
        return repr(self.namespace)

    def __str__(self) -> str:
        return str(self.namespace)
