# plateforme.core.api.utils
# -------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing API routes within the Plateforme
framework using FastAPI and Starlette features.
"""

import re
import typing
from typing import Protocol

from ..patterns import RegexPattern, to_path_case, to_snake_case

if typing.TYPE_CHECKING:
    from ..packages import Package
    from ..resources import ResourceType
    from .routing import APIBaseRoute, BaseRoute

__all__ = (
    'APIBaseRouteIdentifier',
    'generate_unique_id',
    'parse_unique_id',
    'sort_key_for_routes',
)


class APIBaseRouteIdentifier(Protocol):
    """A protocol for unique ID generators for API routes."""

    def __call__(
        self,
        route: 'APIBaseRoute',
        /,
        package: 'Package | None' = None,
        resource: 'ResourceType | None' = None,
    ) -> str:
        ...


def generate_unique_id(
    route: 'APIBaseRoute',
    /,
    package: 'Package | None' = None,
    resource: 'ResourceType | None' = None,
) -> str:
    """Generate a unique ID for the given route.

    If a package is provided, the unique ID is generated based on the package
    slug and the route attributes. If a resource is provided, the unique ID is
    generated based on the package slug, the resource slug, and the route
    attributes. If neither a package nor a resource is provided, the unique ID
    is generated based on the route attributes only.

    Args:
        route: The API route for which to generate a unique ID.
        package: The package to which the route belongs.
        resource: The resource to which the route belongs.

    Returns:
        The unique ID for the given route.

    Examples:
        Multiple types of unique IDs can be generated, either ones based on the
        package and resource slugs, or ones based directly on the route path:
        - Format based on packages:
            ``package://path-segment:name[methods|...]``
        - Format based on resources:
            ``package://resource/path-segments/...:name[methods|...]``
        - Format based directly on the route path:
            ``/namespace/path-segments/{segment_id}/...:name[methods|...]``

    Raises:
        ValueError: If both a package and a resource are provided and they do
            not match.
    """
    # Check if both package and resource are specified at the same time
    # and raise an error if they do not match.
    if package is not None and resource is not None \
            and package != resource.resource_package:
        raise ValueError(
            f"Provided package {package.name!r} does not match the resource's "
            f"package {resource.resource_package.name!r}."
        )
    elif resource is not None:
        package = resource.resource_package

    # Generate unique ID based on formatted route path and name
    operation_id = to_path_case(
        f'{route.path_format}:{route.name}', ('curly', to_snake_case)
    )

    # Update unique ID based on provided package
    if package is not None:
        operation_id = package.impl.path + operation_id
        operation_id = f'{package.name}:/{operation_id.lstrip("/")}'

    # Append HTTP methods to the operation ID
    operation_id = operation_id.lower()
    if methods := getattr(route, 'methods', None):
        operation_id = f'{operation_id}[{"|".join(methods).lower()}]'

    return operation_id


def parse_unique_id(id: str) -> tuple[
    str | None, str, str, tuple[str, ...]
]:
    """Parse the unique ID into its components.

    Args:
        id: The unique ID to be parsed.

    Returns:
        A tuple containing:
        - `package`: The package name if available, ``None`` otherwise.
        - `path`: The route path.
        - `name`: The route name.
        - `methods`: A tuple of the HTTP methods.

    Raises:
        ValueError: If the ID format is incorrect.
    """
    # Initialize variables
    package = None
    remaining = id

    # Handle unique ID with a scheme (package name)
    if '://' in remaining:
        package, remaining = id.split(':/', 1)

    # Extract the path and methods from the remaining ID
    match = re.match(r'([^\[\]:]+):([^\[\]]+)\[([^\[\]]+)\]', remaining)
    if not match:
        raise ValueError(
            f"Invalid unique ID format. Got: {id}."
        )
    path, name, methods = match.groups()

    # Check if the path format is valid
    if not re.match(RegexPattern.PATH, path):
        raise ValueError(
            f"Invalid unique ID path format. Got: {path}"
        )

    return package, path, name, tuple(methods.split('|'))


def sort_key_for_routes(route: 'BaseRoute') -> tuple[bool, str]:
    """Get the sort key for the given route."""
    path = getattr(route, 'path', None)
    path_flag = path is None
    path_key = (path or '') + '/~'
    return path_flag, path_key
