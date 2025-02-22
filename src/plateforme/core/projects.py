# plateforme.core.projects
# ------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing project configurations within the
Plateforme framework.
"""

import importlib
import tomllib
import typing
from pathlib import Path
from typing import Any, Self

from .patterns import parse_email
from .representations import ReprArgs
from .schema.core import ValidationInfo
from .schema.decorators import field_validator, model_validator
from .schema.fields import Field
from .schema.models import BaseModel, ModelConfig
from .settings import PackageSettings
from .types.networks import Email
from .types.paths import AnyPath

if typing.TYPE_CHECKING:
    from plateforme import Plateforme

__all__ = (
    'PROJECT_FILES',
    'ProjectInfo',
    'ProjectAppInfo',
    'ProjectContactInfo',
    'ProjectLicenseInfo',
    'import_project_info',
    'resolve_project_path',
)


PROJECT_FILES = ('config.toml', 'pyproject.toml')
"""A list of valid project configuration file names for apps and packages."""


# MARK: Project Information

class ProjectAppInfo(BaseModel):
    """Project application information."""

    __config__ = ModelConfig(
        title='Project application information',
        strict=False,
    )

    scripts: dict[str, str] | None = Field(
        default=None,
        title='Scripts',
        description="""The scripts that can be accessed from the CLI `run`
            command. Each script is a key-value pair where the key is the
            script name and the value is the command to run. The command is
            resolved relatively to the project configuration directory if its
            path is not absolute.""",
        examples=['python scripts/migrations.py', 'python scripts/init.py'],
    )

    build: list[str] | None = Field(
        default=None,
        title='Build',
        description="""The build scripts used to perform the initial necessary
            operations before starting the application, such as installing
            dependencies, creating the database, and running migrations...
            The provided scripts must match the keys of the `scripts` field.
            """,
        examples=['setup', ['setup', 'migrate']],
    )

    start: str = Field(
        ...,
        title='Start',
        description="""The start command arguments to run the application
            instance. The path is resolved relatively to the project
            configuration directory. It needs to be specified using the dotted
            notation with a colon separator for the target application:
            `package.module:app`. Any other uvicorn options can be added after
            the application path.""",
        examples=['main:app', 'main.foo:app --reload'],
    )

    @model_validator(mode='after')
    def __validator__(self) -> Self:
        if self.build and (
            self.scripts is None
            or not all(script in self.scripts for script in self.build)
        ):
            raise ValueError(
                f"Build scripts must match the keys of the `scripts` field. "
                f"Got: {self!r}."
            )
        return self

    def import_app(self) -> 'Plateforme':
        """Import the application instance from the start command."""
        from .main import Plateforme

        args = self.start.split()
        module_path, module_attr = args[0].split(':')
        if not module_path or not module_attr:
            raise ImportError(
                f"Invalid application path provided in the start command: "
                f"{self.start}. Expected format: `package.module:app`"
            )

        try:
            module = importlib.import_module(module_path)
            module_app = getattr(module, module_attr)
        except ImportError as error:
            raise ImportError(
                f"Failed to import the application module from the start "
                f"command: {module_path}"
            ) from error
        except AttributeError as error:
            raise ImportError(
                f"Failed to import the application attribute from the start "
                f"command: {module_attr}"
            ) from error

        if not isinstance(module_app, Plateforme):
            raise ImportError(
                f"Application instance must be a subclass of Plateforme. "
                f"Got: {module_app!r}"
            )

        return module_app


class ProjectContactInfo(BaseModel):
    """Project contact information."""

    __config__ = ModelConfig(
        title='Project contact information',
        strict=False,
    )

    name: str | None = Field(
        default=None,
        title='Name',
        description="""The name of the contact person or organization.""",
        examples=['Average Joe', 'Jane Doe'],
    )

    email: Email | None = Field(
        default=None,
        title='Email',
        description="""The email address of the contact person or organization.
            It must be formatted as a valid email address.""",
        examples=['jane.bloggs@example.com', 'john.doe@example.com'],
    )

    @model_validator(mode='wrap')
    @classmethod
    def __validator__(cls, obj: Any, handler: Any) -> Any:
        if isinstance(obj, str):
            try:
                name, email = parse_email(obj)
                obj = {'name': name, 'email': email}
            except Exception:
                obj = {'name': obj}
        obj = handler(obj)
        if getattr(obj, 'name', None) is None \
                and getattr(obj, 'email', None) is None:
            raise ValueError(
                f"Project contact information must have at least either "
                f"`name` or `email` field set. Got: {obj!r}."
            )
        return obj


class ProjectLicenseInfo(BaseModel):
    """Project license information."""

    __config__ = ModelConfig(
        title='Project license information',
        strict=False,
    )

    text: str | None = Field(
        default=None,
        title='Text',
        description="""A text description of the license. The `text` field is
            mutually exclusive with the `file` field.""",
        examples=['Apache-2.0', 'MIT'],
    )

    file: AnyPath | None = Field(
        default=None,
        title='File',
        description="""A file path pointing to the license information. The
            `file` field is mutually exclusive with the `text` field.""",
        examples=['LICENSE'],
    )

    @model_validator(mode='wrap')
    @classmethod
    def __validator__(cls, obj: Any, handler: Any) -> Any:
        if isinstance(obj, str):
            obj = {'text': obj}
        obj = handler(obj)
        if getattr(obj, 'text', None) is None \
                and getattr(obj, 'file', None) is None:
            raise ValueError(
                f"Project license information must have at least either "
                f"`text` or `file` field set. Got: {obj!r}."
            )
        if getattr(obj, 'text', None) is not None \
                and getattr(obj, 'file', None) is not None:
            raise ValueError(
                f"Project license information cannot have both `text` and "
                f"`file` fields set. Got: {obj!r}."
            )
        return obj


class ProjectInfo(BaseModel):
    """The project information model.

    The project information is resolved from either a ``config.toml`` or
    ``pyproject.toml`` configuration file. For the latter, it merges the
    standard Python project metadata with the ``[tool.plateforme]`` specific
    configuration. The Python standard fields used are:
    - ``name`` (required): The project name.
    - ``version`` (required): The project version.
    - ``authors``: The authors of the project.
    - ``description``: A short description of the project.
    - ``keywords``: A list of keywords that describe the project.
    - ``license``: The license information for the project.
    - ``maintainers``: The maintainers of the project.
    - ``readme``: The path to the project readme file or a string with the
        project readme content.

    For more information, see also:
    https://packaging.python.org/en/latest/specifications/pyproject-toml
    """

    __config__ = ModelConfig(
        title='Project information',
        extra='ignore',
        strict=False,
    )

    name: str = Field(
        ...,
        title='Name',
        description="""The project name. For packages, this is normalized to
            infer the package default `slug` attribute used to reference the
            project within an application.""",
        examples=['my_app'],
    )

    version: str | None = Field(
        default=None,
        title='Version',
        description="""The version of the project. This should follow the
            Python versioning scheme.""",
        examples=['0.1.0', '0.1.0-a1', '2.1.1'],
    )

    dynamic: list[str] | None = Field(
        default=None,
        title='Dynamic fields',
        description="""The dynamic fields of the project information.""",
        examples=['version'],
    )

    authors: list[ProjectContactInfo] | None = Field(
        default=None,
        title='Authors',
        description="""The people or organizations considered to be the
            `authors` of the project. The exact meaning is open to
            interpretation; it may list the original or primary authors,
            or owners of the package."""
    )

    description: str | None = Field(
        default=None,
        title='Description',
        description="""A short description of the project. It is used to
            provide a brief overview of the project.""",
    )

    keywords: list[str] | None = Field(
        default=None,
        title='Keywords',
        description="""A list of keywords that describe the project. It is used
            to categorize the project.""",
    )

    license: ProjectLicenseInfo | None = Field(
        default=None,
        title='License information',
        description="""The license information for the project. It can be
            provided either as a string for the license name or a dictionary
            with several fields.""",
        examples=[
            'Apache 2.0',
            {'name': 'GPL', 'identifier': 'GPL-3.0-or-later'},
            {'name': 'LGPL', 'file': 'LICENSE'},
            {'name': 'MIT', 'url': 'https://opensource.org/licenses/MIT'},
        ],
    )

    maintainers: list[ProjectContactInfo] | None = Field(
        default=None,
        title='Maintainers',
        description="""The people or organizations considered to be the
            `maintainers` of the project."""
    )

    readme: str | None = Field(
        default=None,
        title='Readme',
        description="""The path to the project readme file or a string with the
            project readme content. It is used to provide detailed information
            about the project.""",
    )

    apps: dict[str, ProjectAppInfo] | None = Field(
        default=None,
        title='Applications',
        description="""The project applications settings. It is used to define
            the project applications build and start configurations. Those can
            be accessed using the CLI.
            """,
    )

    package: PackageSettings | None = Field(
        default=None,
        title='Package',
        description="""The package default settings of the project.""",
    )

    directory: Path = Field(
        default=None,
        title='Root directory',
        description="""The root directory of the project. It is used to resolve
            relative paths within the project configuration.""",
    )

    @model_validator(mode='after')
    def __validator__(self, info: ValidationInfo) -> Self:
        # Handle version strict validation
        context = info.context or {}
        if not context.get('strict'):
            return self
        if getattr(self, 'version', None) is None \
                and 'version' not in getattr(self, 'dynamic', []) :
            raise ValueError(
                f"Project information must have a version set either as a "
                f"static or dynamic field. Got: {self!r}."
            )
        return self

    @field_validator('readme', mode='before')
    @classmethod
    def __readme_validator__(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if 'file' in value and 'content' in value:
            raise ValueError(
                f"Readme value cannot contain both `file` and `content`. "
                f"Gave: {value!r}."
            )
        if 'file' in value:
            return value['file']
        if 'content' in value:
            return value['text']
        raise ValueError(
            f"Readme value must contain either `file` or `content`. "
            f"Got: {value!r}."
        )

    def __repr_args__(self) -> ReprArgs:
        return [(None, self.name)]


# MARK: Utilities

def import_project_info(
    dirname: str | None = None, *, force_resolution: bool = True,
) -> ProjectInfo:
    """Import the project information from the given directory.

    It imports the project information from either a ``config.toml`` or
    ``pyproject.toml`` configuration file found in the given path directory.
    The project configuration is then parsed and returned as a `ProjectInfo`
    instance.

    Args:
        dirname: The absolute or relative system path to search from.
            Defaults to current working directory.
        force_resolution: Whether to search recursively up the directory tree
            if the file is not found in the given directory, until the root is
            reached or a valid file is found. Defaults to ``True``.

    Returns:
        The project information parsed from the project configuration file.

    Raises:
        FileExistsError: If multiple project configuration files are found in
            the same directory.
        FileNotFoundError: If no project configuration files are
            found in the given path directory.
        ImportError: If the project configuration file cannot be parsed or has
            no valid project configuration entries.
        NotImplementedError: If the project configuration file is not
            supported.
    """
    project_path = resolve_project_path(
        dirname, force_resolution=force_resolution
    )

    if project_path is None:
        raise FileNotFoundError(
            f"No project configuration files found for the path: "
            f"{project_path or Path.cwd()}."
        )

    try:
        with open(project_path, 'rb') as project_file:
            project_data = tomllib.load(project_file)
    except tomllib.TOMLDecodeError as error:
        raise ImportError(
            f"Failed to parse project configuration file: {project_path}."
        ) from error

    if project_path.name == 'config.toml':
        project_strict = False
        project_config = project_data.get('plateforme', {})
    elif project_path.name == 'pyproject.toml':
        project_strict = True
        project_tool = project_data.get('tool', {})
        project_config = {
            **project_data.get('project', {}),
            **project_tool.get('plateforme', {}),
        }
    else:
        raise NotImplementedError(
            f"Unsupported project configuration file: {project_file}."
        )

    if not project_config:
        raise ImportError(
            f"No valid project configuration entries found in the TOML file: "
            f"{project_path}. Make sure to include either the '[project]' "
            f"section for 'pyproject.toml' files, or the '[plateforme]' "
            f"section for 'config.toml' files."
        )

    project_config['directory'] = project_path.parent
    project_info = ProjectInfo.model_validate(
        project_config,
        strict=project_strict,
    )

    return project_info


def resolve_project_path(
    dirname: str | None = None, *, force_resolution: bool = True,
) -> Path | None:
    """Find the project configuration file path within the given directory.

    It searches for a valid ``config.toml`` or ``pyproject.toml`` file within
    the given directory. If no file is found in the provided directory and
    `force_resolution` is set to ``True``, it will recursively look up the
    directory tree until the root is reached or a valid file is found.
    Otherwise, it will return ``None``.

    Args:
        dirname: The absolute or relative system path to search from.
            Defaults to current working directory.
        force_resolution: Whether to search recursively up the directory tree
            if the file is not found in the given directory, until the root is
            reached or a valid file is found. Defaults to ``True``.

    Returns:
        The path to the project file if found, otherwise ``None``.

    Raises:
        FileNotFoundError: If the provided path does not exist.
        FileExistsError: If multiple project configuration files are found in
            the same directory.
    """
    lookup_path = Path(dirname).resolve() if dirname else Path.cwd()

    # Validate provided path
    if not lookup_path.is_dir():
        lookup_path = lookup_path.parent
    if not lookup_path.exists():
        raise FileNotFoundError(
            f"The provided path does not exist: {lookup_path}."
        )

    # Search for project file path
    while lookup_path != lookup_path.parent:
        project_paths = [lookup_path / filename for filename in PROJECT_FILES]
        project_paths = [path for path in project_paths if path.is_file()]
        if len(project_paths) > 1:
            raise FileExistsError(
                f"Multiple project configuration files found in the same "
                f"directory: {lookup_path}. Given: {PROJECT_FILES!r}."
            )
        elif len(project_paths) == 1:
            return project_paths[0]

        if not force_resolution:
            break
        lookup_path = lookup_path.parent

    return None
