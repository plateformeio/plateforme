# plateforme.core.events
# ----------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides a foundational pattern for event-driven programming
within the Plateforme framework, enabling objects to emit and respond to
events.

The `EventEmitter` class, serving as a mixin, endows any object with the
ability to handle events. It allows for registering event listeners, emitting
events, and invoking these listeners upon event occurrences. This class is
designed to be integrated with other objects to facilitate event-driven
architecture.

The module also includes a decorator, `emit`, which enhances methods to emit
events at specified points in their execution, such as before, after, or upon
encountering an error. This decorator allows for a clean and declarative way to
attach event emission to method invocations, further promoting a modular and
flexible event-driven design.

Examples:
    >>> class MyComponent(EventEmitter):
    ...     @emit(events=['before', 'after'])
    ...     def perform_action(self):
    ...         print("Action performed")

    >>> component = MyComponent()
    >>> component.on('perform_action_before', lambda: print("Before action"))
    >>> component.on('perform_action_after', lambda: print("After action"))
    >>> component.perform_action()
    'Before action'
    'Action performed'
    'After action'
"""

from functools import wraps
from typing import Any, Callable, Concatenate, Literal, ParamSpec, TypeVar

_T = TypeVar('_T', bound='EventEmitter')
_P = ParamSpec('_P')
_R = TypeVar('_R', covariant=True)

__all__ = (
    'EventEmitter',
    'EventSource',
    'EventType',
    'emit',
)


EventSource = Callable[Concatenate[_T, _P], _R]
"""A type alias for a source of events."""


EventType = Literal['before', 'after', 'error']
"""A type alias for event types."""


class EventEmitter:
    """A mixin class to add event handling capabilities to any object."""

    _listeners: dict[str, list[Callable[..., Any]]] = {}

    def on(self, event: str, listener: Callable[..., Any]) -> None:
        """Registers a listener for a given event.

        Args:
            event: The name of the event.
            listener: The callback function to invoke when the event is
                emitted.
        """
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(listener)

        if event not in self._listeners:
            self._listeners[event] = []
        if listener not in self._listeners[event]:
            self._listeners[event].append(listener)

    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Emits an event, calling all registered listeners for this event.

        Args:
            event: The name of the event.
            args: Positional arguments to pass to the listener.
            kwargs: Keyword arguments to pass to the listener.
        """
        for listener in self._listeners.get(event, []):
            listener(*args, **kwargs)


def emit(
    events: list[EventType] | None = None
) -> Callable[[EventSource[_T, _P, _R]], EventSource[_T, _P, _R]]:
    """A decorator to add event emission.

    It adds event emission before, after or on error of a function execution.
    This decorator is designed to be used with methods of classes that inherit
    from `EventEmitter` class.

    Args:
        events: List of events to emit. The possible values are:
            - ``'before'``: Emit the event before the function execution,
            - ``'after'``: Emit the event after the function execution,
            - ``'error'``: Emit the event on error during the function
                execution.
            Defaults to ``None`` (all events).
    """
    def decorator(func: EventSource[_T, _P, _R]) -> EventSource[_T, _P, _R]:

        @wraps(func)
        def wrapper(self: _T, /, *args: _P.args, **kwargs: _P.kwargs) -> _R:
            name = func.__name__.strip('_')
            try:
                # Emit "before" event
                if events is None or 'before' in events:
                    self.emit(f'{name}_before', *args, **kwargs)

                result = func(self, *args, **kwargs)

                # Emit "after" event
                if events is None or 'after' in events:
                    self.emit(f'{name}_after', *args, **kwargs)
                return result

            except Exception as error:
                # Emit "error" event
                if events is None or 'error' in events:
                    self.emit(f'{name}_error', error, *args, **kwargs)
                raise error

        return wrapper

    return decorator
