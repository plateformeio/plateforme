# plateforme.core.modules
# -----------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing modules within the Plateforme
framework.
"""

import ast
import importlib
import importlib.util
import inspect
import os
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, ForwardRef

__all__ = (
    'get_exported_members',
    'get_root_module_name',
    'import_module',
    'import_object',
    'is_namespace',
    'is_package',
    'is_root_module',
    'resolve_file_paths',
    'resolve_forwardref_fullname',
    'resolve_import_statement',
    'resolve_path_from_module_name',
    'resolve_relative_import_name',
)


ROOT_MODULE = 'main'
"""The root module name used as a fallback for top-level modules."""


def get_exported_members(
    module: ModuleType,
    *,
    predicate: Callable[[Any], bool] | None = None,
) -> list[tuple[str, Any]]:
    """Get the exported members of a module.

    It retrieves the exported members of a module by inspecting the module's
    members and filtering them based on the provided predicate.

    If the module defines an ``__all__`` attribute, it uses it to filter the
    exported members. Otherwise, it uses the module's source code to determine
    the exported members, including imported members with aliases and members
    defined in the specified module.

    Args:
        module: The module to get exported members from.
        predicate: An optional callable to filter members.
            Defaults to ``None``.

    Returns:
        The exported members of the module.
    """
    members = inspect.getmembers(module, predicate)

    # Handle explicit exports
    if hasattr(module, '__all__'):
        return [
            (name, value) for name, value in members
            if name in module.__all__
        ]

    # Handle implicit exports
    imported_aliases = set()
    try:
        source = inspect.getsource(module)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            for alias in node.names:
                if alias.asname is not None:
                    imported_aliases.add(alias.name)
    except (OSError, TypeError):
        imported_aliases = set()

    exported_members = []
    for name, member in members:
        # Skip current module
        if member == module:
            continue
        # Skip private members
        if name.startswith('_'):
            continue
        # Add members imported with alias or defined in the module
        if name in imported_aliases or inspect.getmodule(member) == module:
            exported_members.append((name, member))

    return exported_members


def get_root_module_name(*, prefix: str | None = None) -> str:
    """Get the root module name used as a fallback for top-level modules.

    Args:
        prefix: An optional prefix to prepend to the root module name.
            Defaults to ``None``.

    Returns:
        The root module name.
    """
    return f"__{prefix}_{ROOT_MODULE}__" if prefix else f"__{ROOT_MODULE}__"


def import_module(
    name: str,
    package: str | None = None,
    *,
    force_resolution: bool = False,
) -> ModuleType:
    """Import a module.

    The `package` argument is required when performing a relative import. It
    specifies the package to use as the anchor point from which to resolve the
    relative import to an absolute import.

    Args:
        name: The name of the module to import.
        package: The package to use as the anchor point for relative imports.
        force_resolution: When set to ``True``, forces the resolution of the
            empty string module name to ``__main__`` as a fallback if it is
            available. Defaults to ``False``.

    Returns:
        The imported module.

    Note:
        This function is a wrapper around the `importlib.import_module`
        built-in function. It adds the ability to attempt the import of the
        modules ``__main__`` when the given module name is an empty string.
    """
    # Attempt to import the module normally
    if name:
        try:
            return importlib.import_module(name, package=package)
        except ModuleNotFoundError as error:
            raise ImportError(
                f"Could not find module name {name!r}. Make sure the module "
                f"is installed and importable.",
            ) from error

    # Attempt to import "__main__" as a fallback
    if not force_resolution:
        raise ImportError(
            "Empty module name is not allowed without `force_resolution` "
            "enabled."
        )

    try:
        return importlib.import_module(get_root_module_name(), package=package)
    except ModuleNotFoundError as error:
        raise ImportError(
            "Could not find the fallback module `__main__` while attempting "
            "to import an empty module name."
        ) from error


def import_object(
    name: str,
    package: str | None = None,
) -> Any:
    """Import an object.

    The `package` argument is required when performing a relative import. It
    specifies the package to use as the anchor point from which to resolve the
    relative import to an absolute import.

    Args:
        name: The name of the object to import.
        package: The package to use as the anchor point for relative imports.

    Returns:
        The imported object.
    """
    module_parts = name.lstrip('.').split('.')
    module_name = _get_relative_parent_levels(name) + module_parts.pop(0)

    obj = importlib.import_module(module_name, package)

    while module_parts:
        try:
            module_test = f'{module_name}.{module_parts[0]}'
            obj = importlib.import_module(module_test, package)

            module_name = module_test
            module_parts.pop(0)
        except ModuleNotFoundError:
            break

    for part in module_parts:
        try:
            obj = getattr(obj, part)
        except AttributeError:
            raise ImportError(
                f"Object {name!r} not found in module {module_name!r}."
            )

    return obj


def is_namespace(module: ModuleType) -> bool:
    """Whether a module is a valid namespace."""
    if not getattr(module, '__file__', None):
        return True
    return False


def is_package(module: ModuleType, *, allow_root: bool = False) -> bool:
    """Whether a module is a valid package."""
    if getattr(module, '__path__', None):
        return True
    # Handle root module
    if allow_root \
        and not getattr(module, '__package__', None) \
        and is_root_module(module):
            return True
    return False


def is_root_module(module: ModuleType | str) -> bool:
    """Whether a module is the root module."""
    name = module if isinstance(module, str) else module.__name__
    regex = re.compile(rf'^__(?:[a-z]+_)?{ROOT_MODULE}__$')
    return bool(regex.match(name))


def resolve_file_paths(module: ModuleType) -> list[str]:
    """Resolve the filesystem paths of a module.

    It first tries to resolve the filesystem paths from the module's `__path__`
    attribute. If the attribute is not available or contains multiple paths, it
    attempts to resolve the filesystem path from the module's `__file__`
    attribute. If neither is available, it returns an empty list.

    Args:
        module: The module to resolve the filesystem paths from.

    Returns:
        The resolved filesystem paths of the module.
    """
    if is_root_module(module.__name__):
        return [Path.cwd().as_posix()]

    # Convert to list because "__path__" may not support indexing.
    paths: list[str] = list(getattr(module, '__path__', []))

    if len(paths) != 1:
        filename = getattr(module, '__file__', None)
        if filename is not None:
            paths = [os.path.dirname(filename)]
        else:
            # Handle edge case where the list returned by "__path__" contains
            # duplicates that must be removed.
            paths = list(set(paths))

    return paths


def resolve_forwardref_fullname(
    module_name: str,
    forwardref: str | ForwardRef,
    _guard: frozenset[str] = frozenset(),
) -> str | None:
    """Resolves a forward reference to its fully qualified name.

    It resolves a forward reference to its fully qualified name. This function
    is necessary because the Python interpreter does not resolve forward
    references module origin in annotations.

    Args:
        module_name: The module name where the forward reference occurs.
        forwardref: The forward reference to resolve.
        _guard: A set of module names to prevent infinite recursion.

    Returns:
        The fully qualified forward reference name.
    """
    # Check for infinite recursion
    if module_name in _guard:
        return None

    # Retrieve forward reference annotation
    if isinstance(forwardref, ForwardRef):
        annotation = forwardref.__forward_arg__
    else:
        annotation = forwardref

    # Split the forward reference annotation into its different parts
    if '.' in annotation:
        ann_base = '.'.join(annotation.split('.')[:-1])
        ann_root = annotation.split('.')[0]
        ann_name = annotation.split('.')[-1]
    else:
        ann_base = ''
        ann_root = annotation
        ann_name = annotation

    # Retrieve the source code of the module containing the forward reference
    if module_name not in sys.modules:
        file = resolve_path_from_module_name(module_name)
        with open(file, 'r') as f:
            source = f.read()
    else:
        source = inspect.getsource(sys.modules[module_name])

    # Handle import statements
    def handle_import_statement(node: ast.ImportFrom) -> str | None:
        for alias in node.names:
            if alias.name == ann_root or alias.asname == ann_root:
                import_base = resolve_import_statement(module_name, node)
                return resolve_forwardref_fullname(
                    import_base + ann_base,
                    ann_name,
                    _guard | {module_name},
                )
        return None

    # Parse the module source code into an AST walkable tree
    tree = ast.parse(source)
    for node in ast.walk(tree):
        # Check if the node is an import statement inside the `TYPE_CHECKING`
        # block. It's normally from here that forward references are imported.
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == 'TYPE_CHECKING'
        ):
            for if_node in node.body:
                if isinstance(if_node, ast.ImportFrom):
                    if import_statement := handle_import_statement(if_node):
                        return import_statement
        # Check if the node is an import statement outside the `TYPE_CHECKING`
        # block. This is an uncommon case when the forward reference is
        # imported directly in the module.
        elif isinstance(node, ast.ImportFrom):
            if import_statement := handle_import_statement(node):
                return import_statement
        # Check if the node is a class definition with the same name as the
        # forward reference annotation. This stops the forward reference
        # recursive resolution and returns the module name.
        elif isinstance(node, ast.ClassDef) and node.name == annotation:
            return _get_qualname_from_inspect(module_name, ann_name) \
                or _get_qualname_from_ast(module_name, ann_name, source) \
                or '%s.%s' % (module_name, ann_name)

    return None


def resolve_import_statement(
    name: str,
    import_statement: ast.ImportFrom,
) -> str:
    """Resolve an import statement to a fully qualified module name.

    It resolves the fully qualified module name from an import statement
    relative to a specified module name from which the import statement
    originates.

    Args:
        name: The module name against which to resolve the import statement.
        import_statement: The import statement to resolve.

    Returns:
        The import statement fully qualified module name.
    """
    # Check for fully qualified import statement
    if import_statement.level == 0:
        return import_statement.module or ''

    # Otherwise resolve the relative import statement
    module_parts = name.split('.')
    import_base = '.'.join(module_parts[:-import_statement.level])
    import_name = import_statement.module or ''
    return '%s.%s' % (import_base, import_name)


def resolve_path_from_module_name(name: str) -> str:
    """Resolve the file path of a Python module without loading it.

    Args:
        name: The name of the module.

    Returns:
        The file path of the module.
    """
    spec = importlib.util.find_spec(name)
    if spec is not None and spec.origin is not None:
        return spec.origin
    raise ImportError(
        f"Could not find module {name!r}. Make sure the module is installed "
        f"and importable."
    )


def resolve_relative_import_name(from_name: str, to_name: str) -> str:
    """Resolve relative module import name from one module to another."""
    # Handle root module
    if is_root_module(from_name):
        return to_name

    from_parts = from_name.split('.')
    to_parts = to_name.split('.')

    # Find common prefix
    common = 0
    for f, t in zip(from_parts, to_parts):
        if f != t:
            break
        common += 1

    # Construct relative path
    up_levels = len(from_parts) - common
    relative_parts = ['.' * up_levels] if up_levels else []
    relative_parts.extend(to_parts[common:])

    return '.'.join(relative_parts) if relative_parts else '.'


def _get_relative_parent_levels(name: str) -> str:
    """Get the leading parent levels of a relative module name."""
    return '.' * (len(name) - len(name.lstrip('.')))


def _get_qualname_from_inspect(name: str, ann_name: str) -> str | None:
    """Attempt to get the qualname using the inspect module.

    Args:
        name: The module name where the class might be defined.
        ann_name: The name of the class to resolve.

    Returns:
        The qualname of the class, if found.
    """
    module = sys.modules.get(name)
    if module and hasattr(module, ann_name):
        cls = getattr(module, ann_name)
        if inspect.isclass(cls):
            return '%s.%s' % (name, cls.__qualname__)
    return None


def _get_qualname_from_ast(
    name: str, ann_name: str, source: str
) -> str | None:
    """Reconstruct the qualname from AST analysis for classes not yet loaded.

    Args:
        name: The module name where the class might be defined.
        ann_name: The name of the class to resolve.
        source: The source code of the module.

    Returns:
        The reconstructed qualname, if possible.
    """
    tree = ast.parse(source)

    class QualnameFinder(ast.NodeVisitor):
        def __init__(self) -> None:
            self.current_path: list[str] = []
            self.qualname: str | None = None

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            if node.name == ann_name and not self.qualname:
                self.qualname = f'{name}.' \
                    + '.'.join(self.current_path + [node.name])
            self.current_path.append(node.name)
            self.generic_visit(node)
            self.current_path.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.current_path.append(node.name + '.<locals>')
            self.generic_visit(node)
            self.current_path.pop()

    finder = QualnameFinder()
    finder.visit(tree)
    return finder.qualname
