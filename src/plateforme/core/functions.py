# plateforme.core.functions
# -------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for functions within the Plateforme framework.
"""

import inspect
import typing
from contextlib import contextmanager
from functools import wraps
from inspect import Parameter
from typing import Any, Awaitable, Callable, Iterator, ParamSpec, TypeVar

from .context import CALLER_CONTEXT
from .typing import is_async

_C = TypeVar('_C', bound=Callable[..., Any])
_P = ParamSpec('_P')
_R = TypeVar('_R', covariant=True)

__all__ = (
    'caller_manager',
    'make_async',
    'make_kw_only',
    'with_caller_context',
)


@typing.overload
@contextmanager
def caller_manager(
    caller: object | int,
    *,
    salt: str | None = None,
) -> Iterator[tuple[int, ...]]:
    ...

@typing.overload
@contextmanager
def caller_manager(
    caller: None = None,
    *,
    salt: None = None,
) -> Iterator[tuple[int, ...] | None]:
    ...

@contextmanager
def caller_manager(
    caller: object | int | None = None,
    *,
    salt: str | None = None,
) -> Iterator[tuple[int, ...] | None]:
    """A caller context manager for tracking the current caller stack.

    Args:
        caller: The caller object or identifier to add to the caller stack
            context. If an object is provided, the object's identifier is used.
            If an integer is provided, the integer is used.
            Defaults to ``None``.
        salt: An optional salt to add to the caller stack context. If provided,
            the salt is hashed with the caller identifier to create a unique
            stack entry. Defaults to ``None``.
    """
    context = CALLER_CONTEXT.get()

    # Update caller stack context
    if caller is None:
        if salt is not None:
            raise ValueError(
                "Cannot add salt to the caller stack without a caller "
                f"provided. Got: {salt!r}."
            )
        caller_stack = context
    else:
        caller_id = caller if isinstance(caller, int) else id(caller)
        if salt is not None:
            caller_id = hash((caller_id, salt))
        if context is None:
            caller_stack = (caller_id,)
        else:
            caller_stack = context + (caller_id,)

    # Yield and reset caller stack context
    token = CALLER_CONTEXT.set(caller_stack)
    try:
        yield caller_stack
    finally:
        CALLER_CONTEXT.reset(token)


def make_async(func: Callable[_P, _R]) -> Callable[_P, Awaitable[_R]]:
    """Wrap a function to convert it to an asynchronous function.

    It is useful when a function needs to be used in an asynchronous context
    but is synchronous. This decorator allows the function to be used in both
    synchronous and asynchronous contexts.

    Args:
        func: The synchronous function to be converted.

    Returns:
        An asynchronous function that wraps the original synchronous function.

    Examples:
        >>> def sync_function():
        ...     return 'Hello, World!'

        >>> async_function = make_async(sync_function)
        >>> async_function()
        'Hello, World!'
    """
    if is_async(func):
        return func

    @wraps(func)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    return async_wrapper


def make_kw_only(
    func: _C,
    /,
    replacements: dict[str, Callable[[], Any]] | None = None,
) -> _C:
    """Wrap a function to accept only keyword arguments and apply replacements.

    It modifies the input function's signature to accept only keyword arguments
    and applies replacements to specified parameters using provided callables.

    This function is useful for transforming functions to handle data payloads
    consisting solely of keyword arguments, with specific parameters being
    dynamically replaced by values from callables.

    Args:
        func: The original function to be modified.
        replacements: A dictionary where keys are parameter names to be
            replaced and values are callables that provide the replacement
            values. Defaults to ``None``.

    Returns:
        A new function with the modified signature that accepts only keyword
        arguments and incorporates the specified replacements.

    Raises:
        ValueError: If a parameter specified in `replacements` is also provided
            in the data, or if a required parameter is missing from the data
            and not covered by the `replacements`.

    Note:
        The replacement map is not meant to be used when decorating functions,
        but rather when dynamically calling the wrapped function, as shown in
        the examples below.

    Examples:
        >>> @make_kw_only
        ... def example(a, b, c):
        ...     return a + b + c
        >>> wrapped(a=1, b=10, c=20)
        31

        >>> def example_with_replacements(a, b, c):
        ...     return a + b + c
        >>> replacements = {'b': lambda: 10, 'c': lambda: 20}
        ... wrapped = make_kw_only(example_with_replacements, replacements)
        >>> wrapped(a=1)
        31
    """
    signature = inspect.signature(func)
    parameters_in = dict(signature.parameters)
    parameters_out = dict(signature.parameters)
    replacements = replacements or {}

    for key, param in parameters_in.items():
        if key in replacements:
            del parameters_out[key]
            continue
        parameters_out[key] = param.replace(kind=Parameter.KEYWORD_ONLY)

    signature.replace(parameters=list(parameters_out.values()))

    @wraps(func)
    def wrapper(**data: Any) -> Any:
        args: list[Any] = []
        kwargs: dict[str, Any] = {}

        remaining_data = data.copy()

        for key, param in parameters_in.items():
            # Resolve parameter value
            if key in remaining_data:
                if key in replacements:
                    raise ValueError(
                        f"Argument {key!r} cannot be provided in the function "
                        f"parameters when it has a replacement map."
                    )
                value = remaining_data.pop(key)
            elif key in replacements:
                value = replacements[key]()
            elif param.default is not Parameter.empty:
                value = param.default
            else:
                raise ValueError(
                    f"Parameter {key!r} is required but not provided."
                )

            # Assign parameter value
            if param.kind == Parameter.POSITIONAL_ONLY:
                args.append(value)
            else:
                kwargs[key] = value

        if remaining_data:
            raise ValueError(
                f"Provided data contains unexpected arguments: "
                f"{', '.join(remaining_data.keys())}."
            )

        return func(*args, **kwargs)

    setattr(wrapper, '__signature__', signature)
    return wrapper  # type: ignore


def with_caller_context(func: _C) -> _C:
    """Wrap a function to set the current caller object instance.

    It uses the first argument of the function as the caller object instance
    and adds it to the caller stack context. This decorator is useful for
    tracking the caller object instance in the current context.

    Args:
        func: The function to wrap with the caller context.

    Returns:
        A new function that sets the caller object instance in the context.
    """
    # Wrap sync function with caller context
    def sync_wrapper(f_sync: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(f_sync)
        def wrapper(caller: object, *args: Any, **kwargs: Any) -> Any:
            with caller_manager(caller):
                return f_sync(caller, *args, **kwargs)
        return wrapper

    # Wrap async function with caller context
    def async_wrapper(f_async: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(f_async)
        async def wrapper(caller: object, *args: Any, **kwargs: Any) -> Any:
            with caller_manager(caller):
                return await f_async(caller, *args, **kwargs)
        return wrapper

    # Validate object and wrap with caller context
    signature = inspect.signature(func)
    parameters = list(signature.parameters)

    if not parameters:
        raise TypeError(
            f"Only functions with at least one argument are supported. "
            f"Got: {func!r}."
        )

    if inspect.iscoroutinefunction(func):
        return async_wrapper(func)  # type: ignore
    else:
        return sync_wrapper(func)  # type: ignore
