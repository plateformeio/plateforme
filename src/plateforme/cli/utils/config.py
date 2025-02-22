# plateforme.cli.utils.config
# ---------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
Configuration utilities for the command line interface.
"""

import typing
from typing import Literal

import typer


@typing.overload
def mount(
    app: typer.Typer,
    instance: typer.Typer,
    *,
    merge: Literal[True],
) -> None:
    ...

@typing.overload
def mount(
    app: typer.Typer,
    instance: typer.Typer,
    *,
    merge: Literal[False] = False,
    **kwargs: typing.Any,
) -> None:
    ...

def mount(
    app: typer.Typer,
    instance: typer.Typer,
    *,
    merge: bool = False,
    **kwargs: typing.Any,
) -> None:
    """Mount a Typer instance onto another Typer instance.

    Args:
        app: The Typer instance to mount the other instance onto.
        instance: The Typer instance to mount onto the other instance.
        merge: Whether to merge the commands of the two instances.
            Defaults to ``False``.
        **kwargs: Additional keyword arguments to pass to the `add_typer`
            method if `merge` is set to ``False``.
    """
    if merge:
        # Handle callback
        if instance.registered_callback is not None:
            if app.registered_callback is not None:
                raise ValueError("Cannot merge instances both with callback.")
            app.registered_callback = instance.registered_callback
        # Handle commands and groups
        for command in instance.registered_commands:
            app.registered_commands.append(command)
        for group in instance.registered_groups:
            app.registered_groups.append(group)
    else:
        app.add_typer(instance, **kwargs)
