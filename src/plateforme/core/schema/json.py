# plateforme.core.schema.json
# ---------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing JSON schema within the Plateforme
framework using Pydantic features.
"""

from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Type,
    Union,
)

from pydantic.json_schema import (
    GenerateJsonSchema as _GenerateJsonSchema,
    JsonSchemaKeyT,
)

from .core import CoreSchema

__all__ = (
    'DEFAULT_REF_TEMPLATE',
    'GenerateJsonSchema',
    'JsonEncoder',
    'JsonSchemaDict',
    'JsonSchemaExtra',
    'JsonSchemaExtraCallable',
    'JsonSchemaKeyT',
    'JsonSchemaMode',
    'JsonSchemaSource',
    'JsonSchemaValue',
)


DEFAULT_REF_TEMPLATE = '#/$defs/{model}'
"""The default format string for generating reference names in JSON schemas."""


JsonEncoder = Callable[[Any], Any]
"""A type alias for the JSON encoder function."""


JsonSchemaDict = Dict[str, 'JsonSchemaValue']
"""A type alias for a JSON schema dictionary."""


JsonSchemaExtra = Union[
    JsonSchemaDict,
    Callable[[JsonSchemaDict], None],
]
"""A type alias for the extra JSON schema data."""


JsonSchemaExtraCallable = Union[
    JsonSchemaExtra,
    Callable[[JsonSchemaDict, Type[Any]], None],
]
"""A type alias for the extra JSON schema data callable."""


JsonSchemaMode = Literal['validation', 'serialization']
"""A type alias for the mode of a JSON schema.

For some types, the inputs for ``validation`` differ from the outputs of
``serialization``. For example, computed fields will only be present when
serializing, and should not be provided when validating. This flag provides a
way to indicate whether you want the JSON schema required for validation
inputs, or that will be matched by serialization outputs.
"""


JsonSchemaSource = Literal['key', 'model', 'both']
"""A type alias for the source of a JSON schema.

It describes the source type to use for generating the resources JSON schema.
It can be either ``key`` , ``model``, or ``both`` where the latter accepts,
when applicable, integer and string values for key identifiers in addition to
the standard model schema generation.
"""


JsonSchemaValue = Union[
    int, float, str, bool, None, List['JsonSchemaValue'], JsonSchemaDict
]
"""A type alias for a JSON schema value."""


class GenerateJsonSchema(_GenerateJsonSchema):
    """A class for generating JSON schemas.

    This class generates JSON schemas based on configured parameters. The
    default schema dialect is https://json-schema.org/draft/2020-12/schema.
    The class uses `by_alias` to configure how fields with multiple names are
    handled, `ref_template` to format reference names and `source` to determine
    the source type of the schema when applicable.

    Attributes:
        schema_dialect: The JSON schema dialect used to generate the schema.
        ignored_warning_kinds: Warnings to ignore when generating the schema.
            A ``self.render_warning_message`` will do nothing if its argument
            ``kind`` is in `ignored_warning_kinds`; this value can be modified
            on subclasses to easily control which warnings are emitted.
        by_alias: Whether to use field aliases when generating the schema, i.e.
            if ``True``, fields will be serialized according to their alias,
            otherwise according to their attribute name. Defaults to ``True``.
        ref_template: The template format string to use when generating
            reference names. Defaults to ``DEFAULT_REF_TEMPLATE``.
        source: The source type of the schema. It can be either ``model`` or
            ``resource`` where the latter accepts, when applicable, string
            values for identifiers in addition to the standard model schema
            generation. Defaults to ``model``.
        core_to_json_refs: A mapping of core refs to JSON refs.
        core_to_defs_refs: A mapping of core refs to definition refs.
        defs_to_core_refs: A mapping of definition refs to core refs.
        json_to_defs_refs: A mapping of JSON refs to definition refs.
        definitions: Definitions in the schema.

    Raises:
        JsonSchemaError: If the instance of the class is inadvertently re-used
            after generating a schema.

    Note:
        See documentation bellow for more information about schema dialects:
        https://json-schema.org/understanding-json-schema/reference/schema.html
    """

    def __init__(self,
        by_alias: bool = True,
        ref_template: str = DEFAULT_REF_TEMPLATE,
    ):
        """Initialize the JSON schema generator.

        Args:
            by_alias: Whether to use field aliases when generating the schema,
                i.e. if ``True``, fields will be serialized according to their
                alias, otherwise according to their attribute name.
                Defaults to ``True``.
            ref_template: The template format string to use when generating
                reference names. Defaults to ``DEFAULT_REF_TEMPLATE``.
        """
        super().__init__(by_alias=by_alias, ref_template=ref_template)
        self._source: JsonSchemaSource = 'model'

    def generate(
        self,
        schema: CoreSchema,
        mode: JsonSchemaMode = 'validation',
        source: JsonSchemaSource = 'model',
    ) -> JsonSchemaDict:
        """Generates a JSON schema for a specified core schema.

        It generates a JSON schema for a specified core schema using the
        configured parameters. The schema is generated based on the specified
        mode and source type.

        Args:
            schema: A ``pydantic-core`` model core schema.
            mode: The mode to use for generating the JSON Schema. It can be
                either ``validation`` or ``serialization`` where respectively
                the schema is generated for validating data or serializing
                data. Defaults to ``validation``.
            source: The source type to use for generating the resources JSON
                schema. It can be either ``key`` , ``model``, or ``both`` where
                the latter accepts, when applicable, integer and string values
                for key identifiers in addition to the standard model schema
                generation. Defaults to ``model``.

        Returns:
            A generated JSON schema representing the given model core schema.

        Raises:
            PydanticUserError: If the JSON schema generator has already been
                used to generate a JSON schema.
        """
        self._mode = mode
        self._source = source
        return super().generate(schema, mode)
