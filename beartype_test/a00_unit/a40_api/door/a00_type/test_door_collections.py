#!/usr/bin/env python3
# --------------------( LICENSE                            )--------------------
# Copyright (c) 2014-2026 Beartype authors.
# See "LICENSE" for further details.

'''DOOR mapping projections and collection wrapper regression tests.'''


def test_door_mapping_keys() -> None:
    '''Two-child mappings project only keys onto one-child interfaces.'''
    from beartype.door import is_subhint
    from collections import ChainMap, OrderedDict, defaultdict
    from collections.abc import (
        Collection, Container, Iterable, Mapping, MutableMapping, Reversible,
        Sequence, Sized)
    import typing

    mappings = (
        dict, Mapping, MutableMapping, defaultdict, OrderedDict, ChainMap,
        typing.Dict, typing.Mapping, typing.MutableMapping,
        typing.DefaultDict, typing.OrderedDict, typing.ChainMap)
    targets = (
        Collection, Container, Iterable,
        typing.Collection, typing.Container, typing.Iterable)
    for mapping in mappings:
        for target in targets:
            for key, expected in ((str, True), (object, True), (int, False)):
                assert is_subhint(mapping[str, int], target[key]) is expected
                assert not is_subhint(target[key], mapping[str, int])
            # Values cannot leak into the key comparison, even when nested.
            assert is_subhint(mapping[str, list[bytes]], target[str])
            assert not is_subhint(mapping[str, list[bytes]], target[bytes])
            assert is_subhint(mapping[str, int], target[typing.Any])
            assert is_subhint(mapping[typing.Any, int], target[str])
            assert is_subhint(mapping[str, int], target)
        assert is_subhint(mapping[str, int], Sized)
        assert not is_subhint(mapping[str, int], Sequence[str])
        assert not is_subhint(mapping[str, int], list[str])

    # Reversibility belongs to concrete dicts, not the Mapping ABC.
    for mapping in (dict, defaultdict, OrderedDict, typing.Dict,
                    typing.DefaultDict, typing.OrderedDict):
        assert is_subhint(mapping[str, int], Reversible[str])
        assert not is_subhint(mapping[str, int], Reversible[int])
    for mapping in (Mapping, MutableMapping, ChainMap):
        assert not is_subhint(mapping[str, int], Reversible[str])


def test_door_mapping_to_mapping() -> None:
    '''Retain child-wise comparisons and enforce origin direction first.'''
    from beartype.door import is_subhint
    from collections import ChainMap, OrderedDict, defaultdict
    from collections.abc import Mapping, MutableMapping
    from typing import Any, Dict

    factories = (dict, defaultdict, OrderedDict, ChainMap, Mapping, MutableMapping)
    for source in factories:
        for target in factories:
            expected = issubclass(source, target)
            assert is_subhint(source[str, int], target[str, int]) is expected
            assert is_subhint(source[str, int], target[object, object]) is expected
            assert is_subhint(source[str, int], target[str, Any]) is expected
            assert not is_subhint(source[str, int], target[int, int])
            assert not is_subhint(source[str, int], target[str, str])
    assert is_subhint(dict[str, int], Dict[str, int])
    assert is_subhint(Dict[str, int], dict[str, int])
    assert is_subhint(dict[str, dict[str, int]], Mapping[str, Mapping[str, int]])
    assert not is_subhint(dict[str, dict[str, int]], Mapping[str, Mapping[int, int]])


def test_door_collection_regressions() -> None:
    '''New wrappers preserve unrelated same-arity and unsupported relations.'''
    from beartype.door import is_subhint
    from beartype.roar import BeartypeDoorIsSubhintException
    from collections import Counter
    from collections.abc import (
        Collection, Container, Iterable, Iterator, Generator, Mapping,
        Reversible, Sequence)
    from pytest import raises

    for target in (Collection, Container, Iterable):
        for source in (list, set, Counter):
            assert is_subhint(source[str], target[str])
            assert not is_subhint(source[str], target[int])
    assert is_subhint(Collection[str], Iterable[str])
    assert is_subhint(Collection[str], Container[str])
    assert is_subhint(Reversible[str], Iterable[str])
    assert is_subhint(Sequence[str], Collection[str])
    assert not is_subhint(Container[str], Iterable[str])
    assert not is_subhint(Iterable[str], Container[str])
    assert not is_subhint(Iterable[str], Mapping[str, int])
    assert not is_subhint(dict[str, int], Iterator[str])
    # Counter's implicit int value and generator projections are separate work.
    with raises(BeartypeDoorIsSubhintException):
        is_subhint(Counter[str], Mapping[str, int])
    with raises(BeartypeDoorIsSubhintException):
        is_subhint(Generator[int, None, None], Iterator[int])


def test_door_mapping_identity() -> None:
    '''Publish the hierarchy without altering equality, hash or bare hints.'''
    from beartype.door import (
        TypeHint, DictTypeHint, MutableMappingTypeHint, MappingTypeHint,
        CollectionTypeHint, IterableTypeHint, ContainerTypeHint,
        ReversibleTypeHint, is_subhint)
    from collections import ChainMap, OrderedDict, defaultdict
    from collections.abc import (
        Mapping, MutableMapping, Collection, Iterable, Container, Reversible)
    import typing

    wrappers = (
        (dict[str, int], DictTypeHint),
        (typing.Dict[str, int], DictTypeHint),
        (defaultdict[str, int], DictTypeHint),
        (OrderedDict[str, int], DictTypeHint),
        (ChainMap[str, int], MutableMappingTypeHint),
        (MutableMapping[str, int], MutableMappingTypeHint),
        (Mapping[str, int], MappingTypeHint),
        (Collection[str], CollectionTypeHint),
        (Iterable[str], IterableTypeHint),
        (Container[str], ContainerTypeHint),
        (Reversible[str], ReversibleTypeHint))
    for hint, cls in wrappers:
        assert type(TypeHint(hint)) is cls
        assert cls.__module__ == 'beartype.door'
        assert TypeHint(hint) is TypeHint(hint)
    assert issubclass(DictTypeHint, MutableMappingTypeHint)
    assert issubclass(MutableMappingTypeHint, MappingTypeHint)
    assert issubclass(MappingTypeHint, CollectionTypeHint)
    assert issubclass(CollectionTypeHint, IterableTypeHint)
    assert issubclass(CollectionTypeHint, ContainerTypeHint)
    assert not issubclass(ContainerTypeHint, IterableTypeHint)

    for left, right in (
        (dict[str, int], typing.Dict[str, int]),
        (Mapping[str, int], typing.Mapping[str, int]),
        (dict, dict[typing.Any, typing.Any]),
        (typing.Dict, dict[object, object]),
        (Mapping, typing.Mapping[typing.Any, typing.Any]),
        (Collection, typing.Collection[typing.Any])):
        assert TypeHint(left) == TypeHint(right)
        assert hash(TypeHint(left)) == hash(TypeHint(right))
    assert not is_subhint(dict, dict[str, int])
    assert not is_subhint(typing.Dict, typing.Mapping[str, int])
    assert is_subhint(dict, Mapping)
    assert is_subhint(dict[typing.Any, typing.Any], dict[str, int])
    assert is_subhint(dict[str, int], typing.Union[Iterable[str], int])
    assert not is_subhint(dict[str, int], typing.Union[Iterable[int], int])
    assert is_subhint(dict[str, int], typing.Annotated[Iterable[str], 'keys']) is False


def test_door_collection_virtual_mapping() -> None:
    '''Virtual ABC registration must not silently discard a mapping value.'''
    import subprocess
    import sys

    # A fresh interpreter prevents irreversible ABC registration from changing
    # other tests. Both false and true would conceal an unsupported relation.
    subprocess.run([sys.executable, '-c', '''
from collections.abc import Mapping, Reversible
from beartype.door import is_subhint
from beartype.roar import BeartypeDoorIsSubhintException
Mapping.register(Reversible)
try:
    is_subhint(Reversible[str], Mapping[str, int])
except BeartypeDoorIsSubhintException:
    pass
else:
    raise AssertionError('An unsupported value projection was silently ignored')
'''], check=True)


def test_door_collection_invalid_arity() -> None:
    '''Specialized wrappers retain existing generic-alias arity validation.'''
    from beartype.door import TypeHint
    from beartype.roar import BeartypeDoorPepArgsLenException
    from collections.abc import Mapping, Iterable, Collection, Container
    from pytest import raises

    for hint in (dict[str], Mapping[str, int, bytes], Iterable[str, int],
                 Collection[str, int], Container[str, int]):
        with raises(BeartypeDoorPepArgsLenException):
            TypeHint(hint)
