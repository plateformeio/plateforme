# plateforme.core.schema.loaders
# ------------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing loaders used in settings within the
Plateforme framework.

Loaders allow for dynamic importing and initialization of objects based on
their import paths. This is particularly useful for configuration management
where components need to be specified in settings files but instantiated at
runtime.

Examples:
    >>> from typing import Annotated
    ... from plateforme.api import Middleware
    ... from plateforme.schema import BaseModel, Loader

    >>> class Settings(BaseModel):
    ...     middleware: Annotated[type[Middleware], Loader(strict=False)]
    ...     ...

    Create settings by providing the import path of a middleware class:

    >>> settings = Settings(
    ...     middleware='my_app.CustomMiddleware',
    ...     ...
    ... )

    The middleware attribute will be a loader proxy object that behaves like
    the loaded class but also stores the loader information:

    >>> print(settings.middleware)
    <CustomMiddleware>

    When serializing to JSON, the loader information is preserved:

    >>> print(settings.model_dump(mode='json'))
    {'middleware': {'path': 'my_app.CustomMiddleware'}}
"""

import dataclasses
import typing
from typing import Any, TypeVar

from ..modules import import_object
from ..proxy import Proxy
from . import core as core_schema
from .core import (
    CoreSchema,
    GetCoreSchemaHandler,
    SchemaSerializer,
    ValidatorFunctionWrapHandler,
)
from .errors import PydanticSchemaGenerationError

_T = TypeVar('_T')

__all__ = (
    'Loader',
    'LoaderInfo',
    'LoaderProxy',
)


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class LoaderInfo:
    """Loader information used to import an object."""

    path: str = dataclasses.field(kw_only=False)
    """The full path to the object to import."""

    init: bool = False
    """Whether the object should be initialized."""

    args: tuple[Any, ...] | None = None
    """Additional arguments for the object initialization."""

    kwargs: dict[str, Any] | None = None
    """Additional keyword arguments for the object initialization."""

    def __post_init__(self) -> None:
        """Loader information validation."""
        if self.init:
            return
        if self.args is not None or self.kwargs is not None:
            raise ValueError(
                "Cannot provide additional arguments or keyword arguments "
                "when the loader is not initialized."
            )

    def load(
        self,
        *,
        proxy: bool = False,
        validator: ValidatorFunctionWrapHandler | None = None,
    ) -> Any:
        """Load the object from the loader information.

        Args:
            proxy: Whether to return a proxy object.
            validator: An optional validator for the loaded object.

        Returns:
            The loaded object.
        """
        instance = import_object(self.path)
        if self.init:
            try:
                args = self.args or ()
                kwargs = self.kwargs or {}
                instance = instance(*args, **kwargs)
            except Exception as error:
                raise ValueError(
                    f"Failed to initialize object {self.path!r}"
                ) from error

        if validator is not None:
            instance = validator(instance)
        if proxy:
            instance = LoaderProxy(instance, info=self)
        return instance

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source: Any,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        return core_schema.union_schema([
            handler(source),
            core_schema.no_info_after_validator_function(
                lambda obj: LoaderInfo(**obj),
                core_schema.typed_dict_schema({
                    'path': core_schema.typed_dict_field(
                        core_schema.str_schema(),
                        required=True,
                    ),
                    'init': core_schema.typed_dict_field(
                        core_schema.bool_schema(),
                        required=True,
                    ),
                    'args': core_schema.typed_dict_field(
                        core_schema.tuple_variable_schema(
                            core_schema.any_schema()
                        ),
                        required=False,
                    ),
                    'kwargs': core_schema.typed_dict_field(
                        core_schema.dict_schema(
                            core_schema.str_schema(), core_schema.any_schema()
                        ),
                        required=False,
                    ),
                }),
            ),
            core_schema.no_info_after_validator_function(
                lambda obj: LoaderInfo(path=obj),
                core_schema.str_schema(),
            ),
        ])


class LoaderProxy(Proxy[_T]):
    """A proxy object for a loaded object that stores loader information."""

    if typing.TYPE_CHECKING:
        __proxy_info__: LoaderInfo

    def __init__(self, obj: _T, *, info: LoaderInfo) -> None:
        """Initialize the loader proxy."""
        super().__init__(obj, info=info)

    __pydantic_serializer__ = SchemaSerializer(
        core_schema.any_schema(
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda obj, info: obj if info.mode == 'python' \
                    else getattr(obj, '__proxy_info__', {}),
                info_arg=True,
                when_used='always',
            )
        )
    )


class Loader:
    """An object loader for model validation and serialization.

    This class is used to load objects from either a given import path, i.e.
    its module path and fullname, or loader information that contains the
    import path, initialization arguments, and keyword arguments.

    Those information are stored within the loader proxy object, which is
    created when the object is loaded from the loader.

    Attributes:
        strict: Whether to strictly enforce the loader type.
    """

    def __init__(self, *, strict: bool = False) -> None:
        """Initialize the loader."""
        self.strict = strict

    def __get_pydantic_core_schema__(
        self,
        source: Any,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        try:
            source_schema = handler.generate_schema(source)
        except PydanticSchemaGenerationError:
            source_schema = core_schema.is_instance_schema(source)

        loader_schema = core_schema.chain_schema([
            handler.generate_schema(LoaderInfo),
            core_schema.no_info_wrap_validator_function(
                lambda info, fn: info.load(proxy=True, validator=fn),
                source_schema,
            ),
        ])

        def get_loader_schema(strict: bool) -> CoreSchema:
            if strict:
                return loader_schema
            return core_schema.union_schema([
                source_schema,
                loader_schema,
            ])

        return core_schema.lax_or_strict_schema(
            lax_schema=get_loader_schema(strict=self.strict),
            strict_schema=get_loader_schema(strict=True),
        )
