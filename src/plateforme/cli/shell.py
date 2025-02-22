# plateforme.cli.shell
# --------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
The shell command line interface.
"""

import os
import select
import sys
import traceback
from typing import Any

import typer

from .utils.context import Context
from .utils.logging import logger

app = typer.Typer()


SHELLS = ['ipython', 'bpython', 'python']
"""The available interactive shells."""


@app.command()
def shell(
    ctx: Context,
    no_startup: bool = typer.Option(
        False,
        '--no-startup',
        help=(
            "When using plain Python, it ignores the `PYTHONSTARTUP` "
            "environment variable and `~/.pythonrc.py` script."
        ),
    ),
    interface: str | None = typer.Option(
        None,
        '--interface',
        '-i',
        help=(
            "Specify an interactive interpreter interface. Available options: "
            "`ipython`, `bpython`, and `python`."
        ),
    ),
    command: str | None = typer.Option(
        None,
        '--command',
        '-c',
        '-x',
        help=(
            "Run directly a command and exit instead of opening an "
            "interactive shell."
        ),
    ),
) -> None:
    """Launch a Python interactive interpreter with the plateforme project
    context.

    It tries to use `IPython` or `bpython`, if one of them is available. Any
    standard input is executed as code.
    """
    config, project, project_app = ctx.obj.get_app_config()

    logger.info(f"Starting shell... (from {project}:{project_app})")

    import plateforme

    # Set up a namespace environment for the shell.
    namespace: dict[str, Any] = {
        'app': config.import_app(),
        'plateforme': plateforme,
    }

    def run_ipython() -> None:
        from IPython import start_ipython  # type: ignore
        start_ipython(argv=[], user_ns=namespace)

    def run_bpython() -> None:
        import bpython  # type: ignore
        bpython.embed(locals_=namespace)

    def run_python() -> None:
        import code

        # Honor both "$PYTHONSTARTUP" and ".pythonrc.py" while following system
        # conventions using "$PYTHONSTARTUP" first then "~/.pythonrc.py".
        if not no_startup:
            for pythonrc in (
                os.environ.get("PYTHONSTARTUP"),
                os.path.expanduser("~/.pythonrc.py"),
            ):
                if not pythonrc:
                    continue
                if not os.path.isfile(pythonrc):
                    continue
                with open(pythonrc) as handle:
                    pythonrc_code = handle.read()
                # Match the behavior of the "cpython" shell where an error in
                # "PYTHONSTARTUP" prints an exception and continues.
                try:
                    exec(
                        compile(pythonrc_code, pythonrc, "exec"),
                        namespace,
                    )
                except Exception:
                    traceback.print_exc()

        # By default, the following set up readline to do tab completion and to
        # read and write history to the ".python_history" file. This this can
        # be overridden by "$PYTHONSTARTUP" or "~/.pythonrc.py".
        try:
            hook = sys.__interactivehook__  # type: ignore
        except AttributeError:
            # Match the behavior of the "cpython" shell where a missing
            # "sys.__interactivehook__" is ignored.
            pass
        else:
            try:
                hook()
            except Exception:
                # Match the behavior of the "cpython" shell where an error in
                # "sys.__interactivehook__ "prints a warning with the exception
                # and continues.
                logger.error("Failed calling `sys.__interactivehook__`.")
                traceback.print_exc()

        # Set up tab completion for objects imported by "$PYTHONSTARTUP" or
        # "~/.pythonrc.py".
        try:
            import readline
            import rlcompleter

            readline.set_completer(
                rlcompleter.Completer(namespace).complete
            )
        except ImportError:
            pass

        # Start the interactive interpreter.
        code.interact(local=namespace)

    # Execute the command and exit.
    if command:
        exec(command, globals(), namespace)
        return

    # Execute "stdin" if it has anything to read and exit.
    # Not supported on Windows due to "select.select()" limitations.
    if (
        sys.platform != "win32"
        and not sys.stdin.isatty()
        and select.select([sys.stdin], [], [], 0)[0]
    ):
        exec(sys.stdin.read(), globals(), namespace)
        return

    available_shells = [interface] if interface else SHELLS

    for shell in available_shells:
        try:
            match shell:
                case 'ipython':
                    return run_ipython()
                case 'bpython':
                    return run_bpython()
                case 'python':
                    return run_python()
                case _:
                    raise NotImplementedError(f"Unknown shell: {shell!r}.")
        except ImportError:
            pass

    logger.error(f"Couldn't import {shell!r} interface.")
    raise typer.Exit(code=1)
