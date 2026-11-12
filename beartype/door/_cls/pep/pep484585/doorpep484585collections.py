#!/usr/bin/env python3
# --------------------( LICENSE                            )--------------------
# Copyright (c) 2014-2026 Beartype authors.
# See "LICENSE" for further details.

'''
DOOR wrappers for iterable, collection, and mapping type hints.

Mappings expose their keys, rather than key-value pairs, through their
collection interfaces. The wrapper hierarchy models that projection without
changing the existing child-wise subhint relation for mapping-to-mapping
comparisons.
'''

from beartype.door._cls.doorabc import TypeHint
from beartype.door._cls.doorsubbed import SubscriptedTypeHint
from beartype.roar import BeartypeDoorIsSubhintException


class _ContainerTypeHint(SubscriptedTypeHint):
    '''Shared comparison for single-child container interfaces.'''

    def _is_subhint_branch(self, branch: TypeHint) -> bool:
        # A wrapper's Python inheritance is not the inheritance of its origin.
        # In particular, a more specific wrapper can target a less specific
        # wrapper, so the default same-wrapper-class guard cannot decide this.
        if not issubclass(self._origin_type, branch._origin_type):
            return False
        elif branch._is_args_ignorable:
            return True
        elif isinstance(branch, _ContainerTypeHint):
            # ABC registration can introduce origin relations absent from this
            # wrapper hierarchy. Never silently discard a mapping value when
            # a single-child interface is registered as a virtual mapping.
            if len(branch._args_wrapped_tuple) != 1:
                raise BeartypeDoorIsSubhintException(
                    f'{self} <= {branch} undecidable, as '
                    f'{self._hint} and {branch._hint} subscripted by '
                    f'differing number of child type hints '
                    f'(i.e., {len(self._args_wrapped_tuple)} != '
                    f'{len(branch._args_wrapped_tuple)}).'
                )
            return self._args_wrapped_tuple[0].is_subhint(
                branch._args_wrapped_tuple[0])
        return super()._is_subhint_branch(branch)


class IterableTypeHint(_ContainerTypeHint):
    '''Wrapper for subscripted :class:`collections.abc.Iterable` hints.'''


class ContainerTypeHint(_ContainerTypeHint):
    '''Wrapper for subscripted :class:`collections.abc.Container` hints.'''


class ReversibleTypeHint(IterableTypeHint):
    '''Wrapper for subscripted :class:`collections.abc.Reversible` hints.'''


class CollectionTypeHint(IterableTypeHint, ContainerTypeHint):
    '''Wrapper for subscripted :class:`collections.abc.Collection` hints.'''


class MappingTypeHint(CollectionTypeHint):
    '''Wrapper for subscripted :class:`collections.abc.Mapping` hints.'''

    def _is_subhint_branch(self, branch: TypeHint) -> bool:
        if not issubclass(self._origin_type, branch._origin_type):
            return False
        elif branch._is_args_ignorable:
            return True
        elif isinstance(branch, MappingTypeHint):
            return (
                self._args_wrapped_tuple[0].is_subhint(
                    branch._args_wrapped_tuple[0]) and
                self._args_wrapped_tuple[1].is_subhint(
                    branch._args_wrapped_tuple[1])
            )
        # The inherited iterable/container comparison projects the key. The
        # origin check also distinguishes reversible dicts from Mapping ABCs.
        return super()._is_subhint_branch(branch)


class MutableMappingTypeHint(MappingTypeHint):
    '''Wrapper for subscripted :class:`collections.abc.MutableMapping` hints.

    Child comparisons retain DOOR's existing semantics; this does not impose
    a new static-checker variance policy on mutable mappings.
    '''


class DictTypeHint(MutableMappingTypeHint):
    '''Wrapper for subscripted dict, defaultdict, and OrderedDict hints.'''
