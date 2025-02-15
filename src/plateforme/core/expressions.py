# plateforme.core.expressions
# ---------------------------
# Copyright (c) 2023 Plateforme
# This module is part of Plateforme and is released under the MIT License.
# For the full license text, see the LICENSE file at the root directory of the
# project repository or visit https://opensource.org/license/mit.

"""
This module provides utilities for managing expressions such as filters and
sorts used in database and API queries within the Plateforme framework.
"""

import dataclasses
import re
import typing
from collections.abc import Mapping, Sequence
from enum import Enum, StrEnum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Literal,
    Self,
    Set,
    Tuple,
    TypeVar,
    Union,
)

from .patterns import RegexPattern
from .representations import ReprArgs, Representation
from .schema import core as core_schema
from .schema.core import CoreSchema, GetCoreSchemaHandler

if typing.TYPE_CHECKING:
    from .database.expressions import BinaryExpression, Select, UnaryExpression
    from .database.orm import InstrumentedAttribute

__all__ = (
    'Condition',
    'ExpressionIssue',
    'Filter',
    'FilterDict',
    'FilterValue',
    'FilterVar',
    'IncEx',
    'IncExDict',
    'IncExKey',
    'IncExObj',
    'IncExPredicate',
    'IncExSet',
    'Operator',
    'OperatorDefinition',
    'Ordering',
    'Sort',
    'SortList',
    'SortValue',
    'SortVar',
    'Symbol',
)


IncExKey = TypeVar('IncExKey', int, str)
"""A type variable for inclusive and exclusive schema keys."""


IncExValue = Union[bool, 'IncExSet[Any]', 'IncExDict[Any]']
"""A type alias for inclusive and exclusive schema values."""


IncExSet = Set[IncExKey]
"""A type alias for inclusive and exclusive schema of field sets."""


IncExDict = Dict[IncExKey, IncExValue]
"""A type alias for inclusive and exclusive schema of field dictionaries."""


IncExObj = Union[IncExSet[IncExKey], IncExDict[IncExKey]]
"""A type alias for inclusive and exclusive schema of field objects."""


IncExPredicate = Union[
    Any,
    Tuple[Sequence[Any], Any],
    Tuple[Mapping[str, Any], Any],
    Tuple[Sequence[Any], Mapping[str, Any], Any],
]
"""A type alias for inclusive and exclusive predicate values.

This type represents different ways to specify matching criteria for values. It
supports both direct value matching and callable predicates with various
argument patterns:

1.  `Any`
    Direct predicate where it checks whether the target matches the value, or
    is contained within the collection if the provided value is a list, set, or
    tuple, e.g.: ``42`` or ``[1, 2, 3]``.

2.  `Tuple[Sequence[Any], Any]`
    Callable predicate with positional arguments where it calls the function
    with the given positional arguments and matches against the value(s), e.g.:
    ``(['foo', 'bar'], 42)`` or ``(['foo', 'bar'], [1, 2, 3])``.

3.  `Tuple[Mapping[str, Any], Any]`
    Callable predicate with keyword arguments where it calls the function with
    the given keyword arguments and matches against the value(s), e.g.:
    ``({'min': 0, 'max': 100}, 42)`` or ``({'foo': 'bar'}, [1, 2, 3])``.

4.  `Tuple[Sequence[Any], Mapping[str, Any], Any]`
    Callable predicate with both positional and keyword arguments where it
    calls the function with both positional and keyword arguments and matches
    against the value(s), e.g.: ``(['foo', 'bar'], {'min': 0}, 42)``.

Note:
    For all forms, the last value can be either a single value or a collection
    (`list`, `set`, `tuple`) of values. The predicate matches if the result
    equals the single value or is contained within the collection.
"""


if typing.TYPE_CHECKING:
    IncEx = Union[
        Set[int],
        Set[str],
        Dict[int, Union[bool, 'IncEx']],
        Dict[str, Union[bool, 'IncEx']],
    ]
    """A type alias for inclusive and exclusive schema of fields."""

else:
    class IncEx(Generic[IncExKey]):
        """Inclusive and exclusive field schema factory.

        This class is used to define the inclusive and exclusive field schema
        with a set or nested dictionary structure of integer field indexes or
        string field keys. For dictionaries, the values can be of type boolean
        to include or exclude the field based on the context.

        Examples:
            - The expression ``{1, 2, 3}`` when inclusive will only include the
                values from the first three fields.
            - The expression ``{'user': {'id': True}, 'groups': True}`` when
                exclusive will exclude the user id and groups field.
        """

        def __init__(self) -> None:
            raise ValueError(
                "Cannot directly instantiate the inclusive/exclusive schema "
                "factory class. Use the `from_args` method instead."
            )

        @typing.overload
        @classmethod
        def from_args(
            cls, *args: IncExKey | IncExSet[IncExKey]
        ) -> IncExSet[IncExKey]: ...

        @typing.overload
        @classmethod
        def from_args(
            cls, *args: IncExKey | IncExDict[IncExKey], **kwargs: IncExValue
        ) -> IncExDict[IncExKey]: ...

        @classmethod
        def from_args(
            cls, *args: IncExKey | IncExObj[IncExKey], **kwargs: IncExValue
        ) -> IncExObj[IncExKey]:
            """Create a new schema from the given arguments.

            Args:
                *args: The inclusive/exclusive set or nested dictionary
                    structure of integer field indexes or string field keys.
                **kwargs: The inclusive/exclusive field keys with either
                    boolean values to include or exclude the field based on the
                    context, or set or nested dictionary structure of integer
                    field indexes or string field keys.
            """
            # Initialize schema and type
            schema: IncExObj[IncExKey]
            schema_type: type[IncExKey] | None
            if kwargs:
                schema = dict()
                schema_type = str  # type: ignore[assignment]
            elif any(isinstance(arg, dict) for arg in args):
                schema = dict()
                schema_type = None
            else:
                schema = set()
                schema_type = None

            # Validate schema type
            def validate_schema_type(*keys: IncExKey) ->  None:
                nonlocal schema_type
                for key in keys:
                    if not isinstance(key, (int, str)):
                        raise ValueError(
                            f"Invalid inclusive/exclusive schema key type: "
                            f"{type(key)!r}."
                        )
                    if schema_type is None:
                        schema_type = type(key)
                    elif not isinstance(key, schema_type):
                        raise ValueError(
                            f"Incompatible inclusive/exclusive schema key "
                            f"types: {schema_type!r} and {type(key)!r}."
                        )

            # Parse schema arguments
            for arg in args:
                if isinstance(arg, dict):
                    validate_schema_type(*arg.keys())
                    assert isinstance(schema, dict)
                    for arg_key, arg_value in arg.items():
                        if isinstance(arg_value, bool):
                            schema[arg_key] = arg_value
                        else:
                            schema[arg_key] = cls.from_args(arg_value)
                elif isinstance(arg, (list, set, tuple)):
                    validate_schema_type(*arg)
                    if isinstance(schema, dict):
                        schema.update({key: True for key in arg})
                    else:
                        schema.update(arg)
                else:
                    validate_schema_type(arg)
                    if isinstance(schema, dict):
                        schema[arg] = True
                    else:
                        schema.add(arg)

            # Parse schema keyword arguments
            assert isinstance(schema, dict)
            for kwarg_key, kwarg_value in kwargs.items():
                if isinstance(kwarg_value, bool):
                    schema[kwarg_key] = kwarg_value  # type: ignore[index]
                else:
                    schema[kwarg_key] = cls.from_args(  # type: ignore[index]
                        kwarg_value
                    )

            return schema

        @classmethod
        def __get_pydantic_core_schema__(
            cls,
            __source: type[Self],
            __handler: GetCoreSchemaHandler,
        ) -> CoreSchema:
            return core_schema.no_info_after_validator_function(
                cls.from_args,
                core_schema.union_schema([
                    core_schema.dict_schema(),
                    core_schema.set_schema(),
                ])
            )


@dataclasses.dataclass(repr=False)
class ExpressionIssue(Representation):
    """An issue with an expression."""

    obj: Any
    """The expression inner object with the issue."""

    message: str
    """The issue message."""


@dataclasses.dataclass(repr=False)
class OperatorDefinition(Representation):
    """An operator definition."""

    symbol: str
    """The symbol of the operator."""

    types: tuple[type, ...]
    """The types of values the operator can be applied to."""

    sql: Callable[['InstrumentedAttribute[Any]', Any], 'BinaryExpression[Any]']
    """The SQL representation of the operator."""


class Operator(Enum):
    """An enumeration of operators used in expressions."""

    EQUAL = OperatorDefinition(
        symbol='eq',
        types=(float, int, str),
        sql=lambda attr, comp: attr == comp,
    )
    """Equal to (default)"""

    NOT_EQUAL = OperatorDefinition(
        symbol='ne',
        types=(float, int, str),
        sql=lambda attr, comp: attr != comp,
    )
    """Not equal to"""

    GREATER_THAN = OperatorDefinition(
        symbol='gt',
        types=(float, int, str),
        sql=lambda attr, comp: attr > comp,
    )
    """Greater than"""

    GREATER_THAN_OR_EQUAL = OperatorDefinition(
        symbol='ge',
        types=(float, int, str),
        sql=lambda attr, comp: attr >= comp,
    )
    """Greater than or equal to"""

    LESS_THAN = OperatorDefinition(
        symbol='lt',
        types=(float, int, str),
        sql=lambda attr, comp: attr < comp,
    )
    """Less than"""

    LESS_THAN_OR_EQUAL = OperatorDefinition(
        symbol='le',
        types=(float, int, str),
        sql=lambda attr, comp: attr <= comp,
    )
    """Less than or equal to"""

    LIKE = OperatorDefinition(
        symbol='like',
        types=(str,),
        sql=lambda attr, comp: attr.like(
            comp.replace('*', '%') if isinstance(comp, str) else comp
        ),
    )
    """Matching the like pattern"""

    NOT_LIKE = OperatorDefinition(
        symbol='nlike',
        types=(str,),
        sql=lambda attr, comp: ~attr.like(
            comp.replace('*', '%') if isinstance(comp, str) else comp
        ),
    )
    """Not matching the like pattern"""

    IN = OperatorDefinition(
        symbol='in',
        types=(list,),
        sql=lambda attr, comp: attr.in_(comp),
    )
    """In the list of"""

    NOT_IN = OperatorDefinition(
        symbol='nin',
        types=(list,),
        sql=lambda attr, comp: ~attr.in_(comp),
    )
    """Not in the list of"""

    @staticmethod
    def get(symbol: str) -> 'Operator':
        """Get the operator associated with the given symbol."""
        for operator in Operator:
            if operator.value.symbol == symbol:
                return operator
        raise ValueError(f"Invalid operator symbol: {symbol!r}.")

    def __repr__(self) -> str:
        return f"'{self.value.symbol}'"

    def __str__(self) -> str:
        return self.value.symbol


class Symbol(StrEnum):
    """An enumeration of symbols used in expressions."""

    AND = '&'
    """The query separator symbol."""

    ASSIGNMENT = '='
    """The assignment symbol."""

    LIST = ','
    """The list separator symbol."""

    OPERATOR = '~'
    """The operator separator symbol."""

    PIPE = ':'
    """The pipe symbol."""

    REFERENCE = '$'
    """The field reference symbol."""

    SPREAD = '*'
    """The spread symbol."""

    STATEMENT = ';'
    """The statement separator symbol."""


@dataclasses.dataclass(repr=False)
class Condition(Representation):
    """Condition options for a filter clause in a query."""

    value: Any
    """The value to filter the field."""

    operator: Operator = Operator.EQUAL
    """The operator to filter the field."""

    reference: bool = dataclasses.field(default=False, init=False)
    """Whether the value is a reference to another field."""

    def apply(
        self,
        query: 'Select[Any]',
        attr: 'InstrumentedAttribute[Any]',
        *,
        refs: dict[str, 'InstrumentedAttribute[Any]'] | None = None,
    ) -> 'Select[Any]':
        """Apply the filtering condition to the given query and attribute.

        Args:
            query: The query to apply the filtering condition to.
            attr: The attribute to apply the filtering condition to.
            refs: The reference attributes mapping used to resolve the
                condition reference value.

        Returns:
            The query with the filtering condition applied.

        Raises:
            ValueError: When the condition reference value does not exist in
                the reference attributes mapping.
        """
        # Resolve condition value
        if self.reference:
            if refs is None or self.value not in refs:
                raise ValueError(
                    f"The reference field {self.value!r} does not exist in "
                    f"the references mapping."
                )
            value = refs[self.value]
        else:
            value = self.value

        return query.filter(self.operator.value.sql(attr, value))

    def __post_init__(self) -> None:
        if isinstance(self.value, str) \
                and self.value.startswith(Symbol.REFERENCE):
            self.value = self.value[1:]
            self.reference = True

    def __repr_args__(self) -> ReprArgs:
        yield (None, self.value)
        if self.operator is not Operator.EQUAL:
            yield ('operator', self.operator)
        if self.reference is True:
            yield ('reference', self.reference)


@dataclasses.dataclass(repr=False)
class Ordering(Representation):
    """Options to sort a field in a query."""

    direction: Literal['asc', 'desc'] = 'asc'
    """The direction to sort the field."""

    nulls: Literal['first', 'last'] | None = None
    """The position of null values in the sorted results."""

    def apply(
        self, query: 'Select[Any]', attr: 'InstrumentedAttribute[Any]'
    ) -> 'Select[Any]':
        """Apply the ordering options to the given query and attribute.

        Args:
            query: The query to apply the ordering options to.
            attr: The attribute to apply the ordering options to.

        Returns:
            The query with the ordering options applied.
        """
        expression: UnaryExpression[Any]

        # Add direction clause
        if self.direction == 'asc':
            expression = attr.asc()
        else:
            expression = attr.desc()

        # Add nulls clause
        if self.nulls == 'first':
            expression = expression.nullsfirst()
        elif self.nulls == 'last':
            expression = expression.nullslast()

        return query.order_by(expression)

    def __repr_args__(self) -> ReprArgs:
        yield (None, self.direction)
        if self.nulls is not None:
            yield ('nulls', self.nulls)


FilterDict = Dict[str, 'FilterValue']
"""A type alias for a filter criteria dictionary."""


FilterValue = Union[List[Condition], FilterDict]
"""A type alias for a filter criterion or nested criteria dictionary."""


FilterVar = TypeVar('FilterVar', FilterDict, FilterValue)
"""A type variable for a filter dictionary or value."""


class Filter(FilterDict):
    """A filter object to be used in a query.

    It is used to filter the results of a query based on the given criteria.
    The filter criteria can be validated from nested dictionaries and list of
    conditions, or from raw strings formatted as a semicolon separated list of
    conditions and optionally prefixed with an operator, separated by a tilde
    character. Additionally, a filter condition can reference another field by
    prefixing the target field key value with a dollar character.

    Attributes:
        references: A list of reference attributes used within the filter
            criteria to resolve the reference values.

    Examples:
        The expression ``{'price': 'gt~0;lt~1', 'cost': 'le~$price'}``
        will be parsed into:
        >>> {
        ...     'price': [
        ...         {'value': 0, 'operator': 'gt'},
        ...         {'value': 1, 'operator': 'lt'},
        ...     ],
        ...     'cost': [
        ...         {'value': 'price', 'operator': 'le', 'reference': True},
        ...     ],
        ... }

        The expression ``{'user.name': 'like~Al*', user.groups*: 'foo'}``
        will be parsed into:
        >>> {
        ...     'user': {
        ...         'name': [
        ...             {'value': 'Al*', 'operator': 'like'},
        ...         ],
        ...         'groups*': [
        ...             {'value': 'foo', 'operator': 'eq'},
        ...         ],
        ...     },
        ... }
    """

    def __init__(
        self, *criteria: FilterDict, **update: FilterValue | str
    ) -> None:
        """Initialize the filter object with the given criteria and updates."""
        # Merge filter criteria
        result: FilterDict = {}
        for obj in criteria:
            result = self.merge(result, obj)

        # Update filter criteria
        for key, value in update.items():
            if isinstance(value, str):
                try:
                    result[key] = self.parse_criteria(value)
                except ValueError:
                    result[key] = self.parse_criterion(value)
            else:
                result[key] = value

        result = self.unflatten(result)

        issues, references = self.inspect(result)
        if issues:
            raise ValueError(
                "The provided filter criteria have the following issues:\n"
                "\n".join(f'- {issue}' for issue in issues)
            )

        self.references = references
        self.update(result)

    @staticmethod
    def inspect(value: FilterValue) -> tuple[list[ExpressionIssue], list[str]]:
        """Inspect the filter criteria from the given value.

        Args:
            value: The filter criteria to inspect.

        Returns:
            A tuple with a list of issues with the filter criteria and a list
            of references used in the filter criteria.
        """
        issues: list[ExpressionIssue] = []
        references: list[str] = []

        # Inspect dictionary criteria
        if value and isinstance(value, dict):
            for alias, value in value.items():
                if not re.match(RegexPattern.ALIAS_EXP, alias):
                    issues.append(ExpressionIssue(
                        tuple([alias, value]),
                        f"Invalid filter field alias: {alias!r}.",
                    ))
                    continue
                inner_issues, inner_references = Filter.inspect(value)
                issues.extend(inner_issues)
                references.extend(inner_references)

        # Inspect list criteria
        elif value and isinstance(value, list):
            for condition in value:
                if not isinstance(condition, Condition):
                    issues.append(ExpressionIssue(
                        condition,
                        f"Invalid filter condition: {condition!r}.",
                    ))
                    continue
                if condition.reference:
                    references.append(condition.value)

        # Invalid criteria
        else:
            issues.append(ExpressionIssue(
                value,
                f"Invalid filter criteria. Expected a non-empty dictionary or "
                f"list, but got {value!r}.",
            ))

        return issues, list(dict.fromkeys(references))

    @staticmethod
    def merge(obj: FilterVar, other: FilterVar) -> FilterVar:
        """Copy and merge the given filter criteria."""
        # Merge dictionary criteria
        if isinstance(obj, dict):
            if not isinstance(other, dict):
                raise ValueError(
                    f"Incompatible filter criteria. Expected a dictionary to "
                    f"merge with {obj!r}, but got {other!r}."
                )
            result = obj.copy()
            for key, value in other.items():
                if key in obj:
                    result[key] = Filter.merge(obj[key], value)
                else:
                    result[key] = value
            return result

        # Merge list criteria
        if isinstance(obj, list):
            if not isinstance(other, list):
                raise ValueError(
                    f"Incompatible filter criteria. Expected a list to merge "
                    f"with {obj!r}, but got {other!r}."
                )
            return [*obj, *other]

        raise ValueError(
            f"Incompatible filter criteria. Expected a dictionary or a list "
            f"but got {obj!r} and {other!r}."
        )

    @staticmethod
    def flatten(obj: FilterDict) -> FilterDict:
        """Flatten a nested dictionary of filter criteria."""
        result: FilterDict = {}
        for alias, value in obj.items():
            if isinstance(value, dict):
                value = Filter.flatten(value)
                for key, conditions in value.items():
                    result[f'{alias}.{key}'] = conditions
            else:
                result[alias] = value
        return result

    @staticmethod
    def unflatten(obj: FilterDict) -> FilterDict:
        """Unflatten a dictionary of filter criteria."""
        result: FilterDict = {}

        for key, value in obj.items():
            # Validate alias
            node = result
            aliases = key.split('.')
            for alias in aliases[:-1]:
                if alias not in node:
                    node[alias] = {}
                elif not isinstance(node[alias], dict):
                    raise ValueError(
                        f"Incompatible filter criteria for alias {alias!r}. "
                        f"Expected a dictionary, but got {node[alias]!r}."
                    )
                node = node[alias]  # type: ignore[assignment]
            alias = aliases[-1]

            # Validate value
            if isinstance(value, dict):
                value = Filter.unflatten(value)
            if alias in node:
                node[alias] = Filter.merge(node[alias], value)
            else:
                node[alias] = value

        return result

    @staticmethod
    def parse_criterion(string: str) -> list[Condition]:
        """Parse the filter criterion conditions from the given string."""
        pattern = (
            r'^(?:(?P<operator>[a-z]+)' + Symbol.OPERATOR + ')?'
            r'(?P<value>.+)$'
        )

        # Parse filter criterion
        conditions = []
        for condition in string.split(Symbol.STATEMENT):
            # Validate filter condition
            match = re.match(pattern, condition.strip())
            if not match:
                raise ValueError(f"Invalid filter condition: {condition!r}.")

            # Validate filter operator and value
            operator = Operator.get(match['operator'] or 'eq')
            value = match['value'].split(Symbol.LIST)
            if len(value) == 1:
                value = value[0]
            if not isinstance(value, operator.value.types):
                raise ValueError(
                    f"Invalid filter value for {operator!r}: {value!r}."
                )

            conditions.append(Condition(value, operator=operator))

        return conditions

    @staticmethod
    def parse_criteria(string: str) -> FilterDict:
        """Parse the filter criteria from the given string."""
        return {
            key: Filter.parse_criterion(value)
            for key, value in [
                criterion.split(Symbol.ASSIGNMENT)
                for criterion in string.split(Symbol.AND)
            ]
        }

    @classmethod
    def validate(cls, obj: Any) -> Self:
        """Validate the filter criteria from the given object."""
        if isinstance(obj, dict):
            return cls(**obj)
        elif isinstance(obj, str):
            return cls(**cls.parse_criteria(obj))
        raise ValueError(f"Invalid filter criteria: {obj!r}")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        __source: type[Self],
        __handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.dict_schema(),
        )


SortList = List['SortValue']
"""A type alias for a sort criteria list."""


SortValue = Tuple[str, Ordering]
"""A type alias for a sort criterion value."""


SortVar = TypeVar('SortVar', SortList, SortValue)
"""A type variable for a sort list or a sort value."""


class Sort(SortList):
    """A sort object to be used in a query.

    It is used to store the sort criteria to order the results of a query. It
    can be validated from a raw string formatted as a comma or semicolon
    separated list of field key as alias fullnames; optionally prefixed with a
    plus or minus character for respectively ascending or descending order, and
    suffixed with direction and nulls clauses piped with a colon character.

    The direction can be specified as ``asc`` or ``desc`` and the nulls as
    ``first`` and ``last``. By default, the direction is set to ``asc`` and the
    nulls to ``None``,  i.e. the default database provider behavior.

    Examples:
        The expression ``price:nf`` will be parsed into:
        >>> [('price', {'direction': 'asc', 'nulls': 'first'})

        The expression ``user.name:asc:nl,-created_at`` will be parsed into:
        >>> [
        ...     ('user.name', {'direction': 'asc', 'nulls': 'last'}),
        ...     ('created_at', {'direction': 'desc', 'nulls': None}),
        ... ]
    """

    def __init__(self, *criteria: SortValue | str) -> None:
        """Initialize the sort object with the given criteria."""
        result = []
        for obj in criteria:
            if isinstance(obj, str):
                try:
                    result.extend(self.parse_criteria(obj))
                except ValueError:
                    result.append(self.parse_criterion(obj))
            else:
                result.append(obj)

        issues = self.inspect(result)
        if issues:
            raise ValueError(
                "The provided sort criteria have the following issues:\n"
                "\n".join(f'- {issue}' for issue in issues)
            )

        self.extend(result)

    @staticmethod
    def inspect(criteria: SortList) -> list[ExpressionIssue]:
        """Inspect the sort criterion key and options from the given criteria.

        Args:
            criteria: The sort criteria to inspect.

        Returns:
            A list of issues with the sort criteria.
        """
        issues: list[ExpressionIssue] = []

        # Inspect list criteria
        for criterion in criteria:
            if not isinstance(criterion, tuple) or len(criterion) != 2:
                issues.append(ExpressionIssue(
                    criterion,
                    "Invalid sort criterion. Expected a tuple of field key "
                    "and options, but got {criterion!r}.",
                ))
                continue

            key, options = criterion
            if not re.match(RegexPattern.NAME_EXP, key):
                issues.append(ExpressionIssue(
                    criterion,
                    f"Invalid sort field key: {key!r}.",
                ))
            if not isinstance(options, Ordering):
                issues.append(ExpressionIssue(
                    criterion,
                    f"Invalid sort options: {options!r}.",
                ))

        return issues

    @staticmethod
    def parse_criterion(string: str) -> SortValue:
        """Parse the sort criterion key and options from the given string."""
        pattern = (
            r'^(?P<sign>[+-])?'
            r'(?P<key>' + RegexPattern.NAME_EXP[1:-1] + r')'
            r'(?::(?:(?P<direction>asc|desc)|(?P<nulls>nf|nl)))?$'
        )

        # Parse sort criterion
        match = re.match(pattern, string.strip())
        if not match:
            raise ValueError(f"Invalid sort criterion: {string!r}.")
        sign = -1 if match['sign'] == '-' else 1
        sign *= -1 if match['direction'] == 'desc' else 1

        return (
            match['key'],
            Ordering(
                direction='asc' if sign == 1 else 'desc',
                nulls='first' if match['nulls'] == 'nf'
                    else 'last' if match['nulls'] == 'nl'
                    else None,
            ),
        )

    @staticmethod
    def parse_criteria(string: str) -> SortList:
        """Parse the sort criteria from the given string."""
        separators = r'[' + Symbol.LIST + Symbol.STATEMENT + r']'
        return [Sort.parse_criterion(c) for c in string.split(separators)]

    @classmethod
    def validate(cls, obj: Any) -> Self:
        """Validate the sort criteria from the given object."""
        if isinstance(obj, (list, set, tuple)):
            return cls(*obj)
        elif isinstance(obj, str):
            return cls(*cls.parse_criteria(obj))
        raise ValueError(f"Invalid sort criteria: {obj!r}")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        __source: type[Self],
        __handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.list_schema(),
        )
