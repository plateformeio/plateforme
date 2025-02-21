# plateforme.core.logging
# -----------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides the logging features of the Plateforme framework. It
contains the loggers and `setup_logging` logic to configure the logging system,
as well as the specific formatters and filters used by the framework.
"""

import atexit
import json
import logging
import logging.handlers
import os
import sys
import typing
from datetime import datetime, timezone
from enum import StrEnum
from logging.config import dictConfig as buildConfig
from logging.handlers import QueueHandler, QueueListener
from queue import Queue
from typing import Any

from typing_extensions import override

from .patterns import to_camel_case

if typing.TYPE_CHECKING:
    from .settings import LoggingSettings

__all__ = (
    'logger'
    'setup_logging',
    # Filters
    'NoErrorFilter',
    # Formatters
    'DefaultFormatter',
    'JsonFormatter',
    # Handlers
    'FileHandler',
    'StreamHandler',
    # Utilities
    'COLOR_MAP',
    'LOG_RECORD_MAP',
    'Color',
    'supports_ansi_colors',
)


logger = logging.getLogger('plateforme')
"""The main logger of the Plateforme framework."""


def setup_logging(settings: 'LoggingSettings | None' = None) -> None:
    """Setup the logging system with the provided settings."""
    from .settings import LoggingSettings

    settings = settings or LoggingSettings()

    # Resolve filters settings
    settings_filters: dict[str, Any] = {}
    for key, filter in settings.filters.items():
        settings_filters[key] = {'()': filter}

    # Resolve formatters settings
    settings_formatters: dict[str, Any] = {}
    for key, formatter in settings.formatters.items():
        if formatter.type_ not in ('custom', 'default', 'json', 'simple'):
            raise NotImplementedError(
                f"Formatter settings {formatter!r} for key {key!r} is not "
                f"supported."
            )

        formatter_dump = formatter.model_dump(exclude={'type_', 'cls'})

        if formatter.type_ == 'custom':
            settings_formatters[key] = {
                '()': formatter.cls,
                'fmt_keys': formatter_dump,
            }
        elif formatter.type_ == 'default':
            settings_formatters[key] = {
                '()': 'plateforme.logging.DefaultFormatter',
                'fmt_keys': formatter_dump,
            }
        elif formatter.type_ == 'json':
            settings_formatters[key] = {
                '()': 'plateforme.logging.JsonFormatter',
                'fmt_keys': formatter_dump,
            }
        elif formatter.type_ == 'simple':
            settings_formatters[key] = {
                to_camel_case(key): value
                for key, value in formatter_dump.items()
            }

    # Resolve handlers settings
    settings_handlers: dict[str, Any] = {}
    for key, handler in settings.handlers.items():
        if handler.type_ not in ('custom', 'file', 'stream'):
            raise NotImplementedError(
                f"Handler settings {handler!r} for key {key!r} is not "
                f"supported."
            )

        handler_dump = handler.model_dump(exclude={'type_'})
        if handler.type_ == 'file':
            handler_dump['class'] = 'plateforme.logging.FileHandler'
        if handler.type_ == 'stream':
            handler_dump['class'] = 'plateforme.logging.StreamHandler'

        settings_handlers[key] = {
            to_camel_case(key): value
            for key, value in handler_dump.items()
        }

    # Build logging configuration
    buildConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'filters': settings_filters,
        'formatters': settings_formatters,
        'handlers': settings_handlers,
        'loggers': {
            'root': {
                'level': settings.level,
            },
        },
    })

    handlers: list[logging.Handler] = []
    for name in settings_handlers.keys():
        handlers.append(logging._handlers.get(name))  # type: ignore

    queue = Queue(maxsize=-1)  # type: ignore
    queue_handler = QueueHandler(queue)

    root_logger = logging.getLogger()
    root_logger.addHandler(queue_handler)

    listener = QueueListener(queue, *handlers, respect_handler_level=True)
    listener.start()
    atexit.register(listener.stop)


# MARK: Formatters

class DefaultFormatter(logging.Formatter):
    """A default log formatter."""

    if typing.TYPE_CHECKING:
        include: tuple[str, ...]
        asctime: bool
        use_colors: bool

    def __init__(
        self, *, fmt_keys: dict[str, bool] | None = None,
    ) -> None:
        """Initialize the default log formatter."""
        super().__init__()

        fmt_keys = fmt_keys.copy() if fmt_keys else {}
        self.asctime = fmt_keys.pop('asctime', False)
        self.use_colors = fmt_keys.pop('use_colors', False) \
            and supports_ansi_colors()

    @override
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as a text string."""
        color_start = COLOR_MAP.get(record.levelname, Color.RESET)
        color_end = Color.RESET

        message = ''
        if self.asctime:
            message = f'[{record.asctime}] '
        if self.use_colors:
            levelname = f'{color_start}{record.levelname}{color_end}:'
            message += levelname.ljust(len(color_start + color_end) + 10)
        else:
            levelname = f'{record.levelname}:'
            message += levelname.ljust(10)
        message += f'{record.module}:{record.lineno} - {record.message}'

        return message

class JsonFormatter(logging.Formatter):
    """A JSON log formatter."""

    if typing.TYPE_CHECKING:
        include: tuple[str, ...]
        extra: bool

    def __init__(
        self, *, fmt_keys: dict[str, bool] | None = None,
    ) -> None:
        """Initialize the JSON log formatter."""
        super().__init__()

        fmt_keys = fmt_keys.copy() if fmt_keys else {}
        self.extra = fmt_keys.pop('extra', True)
        self.include = tuple(dict.fromkeys([
            key for key, value in fmt_keys.items() if value is True
        ]))

    @override
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as a JSON object."""
        message = self.validate(record)
        return json.dumps(message, default=str)

    def validate(self, record: logging.LogRecord) -> dict[str, Any]:
        """Validate the log record as a JSON-serializable dictionary."""
        message: dict[str, Any] = {}

        for key in self.include:
            if key == 'message':
                message[key] = record.getMessage()
            elif key == 'timestamp':
                message[key] = datetime.fromtimestamp(
                    record.created,
                    tz=timezone.utc
                ).isoformat()
            elif key == 'exc_info' and record.exc_info is not None:
                message[key] = self.formatException(record.exc_info)
            elif key == 'stack_info' and record.stack_info is not None:
                message[key] = self.formatStack(record.stack_info)
            else:
                message[key] = getattr(record, LOG_RECORD_MAP[key])

        if self.extra:
            for key, val in record.__dict__.items():
                if key in LOG_RECORD_MAP:
                    continue
                message[key] = val

        return message


# MARK: Handlers

class FileHandler(logging.handlers.RotatingFileHandler):
    """A file log handler."""

    def __init__(
        self,
        filename: str,
        mode: str = 'a',
        maxBytes: int = 0,
        backupCount: int = 0,
        encoding: str | None = None,
        delay: bool = False,
        errors: str | None = None,
    ) -> None:
        """Initialize the file log handler."""
        dirname = os.path.dirname(filename)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname, exist_ok=True)

        super().__init__(
            filename=filename,
            mode=mode,
            maxBytes=maxBytes,
            backupCount=backupCount,
            encoding=encoding,
            delay=delay,
            errors=errors,
        )


class StreamHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """A stream log handler."""
    pass


# MARK: Filters

class NoErrorFilter(logging.Filter):
    """A filter that only allows log records with a level of INFO or lower."""

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log records with a level of INFO or lower."""
        return record.levelno <= logging.INFO


# MARK: Utilities

class Color(StrEnum):
    """An enumeration of ANSI color codes for log levels."""
    RESET = '\033[0m'
    CYAN = '\033[36m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    RED = '\033[31m'
    MAGENTA = '\033[35m'


COLOR_MAP = {
    'DEBUG': Color.CYAN,
    'INFO': Color.GREEN,
    'WARNING': Color.YELLOW,
    'ERROR': Color.RED,
    'CRITICAL': Color.MAGENTA,
}
"""The color map for log levels."""


LOG_RECORD_MAP = {
    'args': 'args',
    'asctime': 'asctime',
    'created': 'created',
    'exc_info': 'exc_info',
    'exc_text': 'exc_text',
    'filename': 'filename',
    'funtion': 'funcName',
    'levelname': 'levelname',
    'levelno': 'levelno',
    'lineno': 'lineno',
    'module': 'module',
    'msecs': 'msecs',
    'message': 'message',
    'msg': 'msg',
    'name': 'name',
    'pathname': 'pathname',
    'process': 'process',
    'process_name': 'processName',
    'relative_created': 'relativeCreated',
    'stack_info': 'stack_info',
    'task_name': 'taskName',
    'thread': 'thread',
    'thread_name': 'threadName',
    'timestamp': 'timestamp',
}
"""The log record built-in attributes mapping."""


def supports_ansi_colors() -> bool:
    """Whether the terminal supports ANSI escape codes."""
    if not sys.stdout.isatty():
        return False

    # Check environment flags
    if 'NO_COLOR' in os.environ or 'NOCOLOR' in os.environ:
        return False
    if 'FORCE_COLOR' in os.environ:
        return True
    if 'CLICOLOR_FORCE' in os.environ and os.environ['CLICOLOR_FORCE'] != '0':
        return True
    if 'CLICOLOR' in os.environ and os.environ['CLICOLOR'] == '0':
        return False
    if 'COLORTERM' in os.environ:
        return True

    # Check environment terms
    term = os.environ.get('TERM', '').lower()
    if term in ('dumb', ''):
        return False
    supported_terms = ('xterm', 'xterm-256color', 'screen', 'vt100', 'linux')
    if any(t in term for t in supported_terms):
        return True

    # Check Windows terminal support
    if sys.platform == "win32":
        if 'WT_SESSION' in os.environ or 'TERM_PROGRAM' in os.environ:
            return True
        try:
            from ctypes import byref, c_int, windll
            handle = windll.kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = c_int()
            if not windll.kernel32.GetConsoleMode(handle, byref(mode)):
                return False
            value = mode.value & 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
            return bool(value)
        except (ImportError, OSError, AttributeError):
            return False

    return True
