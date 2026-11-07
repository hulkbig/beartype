#!/usr/bin/env python3
# --------------------( LICENSE                            )--------------------
# Copyright (c) 2014-2026 Beartype authors.
# See "LICENSE" for further details.

'''
Partial predicates accepted by the :mod:`beartype.vale.Is` factory.
'''


def test_api_vale_is_partial_c() -> None:
    '''C-based partials validate objects and compose like Python predicates.'''
    from beartype.vale import Is
    from functools import partial
    import operator

    for comparison in (
        operator.lt, operator.le, operator.eq,
        operator.ne, operator.ge, operator.gt,
    ):
        validator = Is[partial(comparison, 1)]
        for value in (0, 1, 2):
            assert validator.is_valid(value) is comparison(1, value)

    # Nested partials, positional-only builtins, bound C methods, and optional
    # keyword-only arguments all retain their normal calling semantics.
    assert Is[partial(partial(operator.le), 1)].is_valid(2)
    assert Is[partial(len)].is_valid([1])
    assert not Is[partial(len)].is_valid([])
    assert Is[partial([1, 2].count)].is_valid(1)
    assert Is[partial(sorted, reverse=True)].is_valid([1])
    assert not Is[partial(sorted, reverse=True)].is_valid([])

    lower = Is[partial(operator.le, 1)]
    upper = Is[partial(operator.gt, 4)]
    between = lower & upper
    assert between.is_valid(2)
    assert not between.is_valid(0)
    assert not between.is_valid(4)
    assert (~lower | upper).is_valid(0)
    assert 'partial' in repr(lower)
    assert 'le' in repr(lower)
    assert 'False' in between.get_diagnosis(
        obj=0, indent_level_outer='', indent_level_inner='')


def test_api_vale_is_partial_decor() -> None:
    '''The reported Annotated use case checks both parameters and returns.'''
    from beartype import beartype
    from beartype.roar import (
        BeartypeCallHintParamViolation,
        BeartypeCallHintReturnViolation,
    )
    from beartype.vale import Is
    from functools import partial
    from operator import le
    from pytest import raises
    from typing import Annotated

    positive = Annotated[int, Is[partial(le, 1)]]

    @beartype
    def identity(value: positive) -> positive:
        return value

    @beartype
    def negate(value: positive) -> positive:
        return -value

    assert identity(1) == 1
    assert identity(2) == 2
    with raises(BeartypeCallHintParamViolation, match='partial'):
        identity(0)
    with raises(BeartypeCallHintParamViolation):
        identity('1')
    with raises(BeartypeCallHintReturnViolation, match='partial'):
        negate(1)


def test_api_vale_is_partial_no_call() -> None:
    '''Constructing a validator must not execute its C-based predicate.'''
    from beartype.vale import Is
    from functools import partial
    from operator import contains

    class Container:
        calls = 0

        def __contains__(self, value):
            self.calls += 1
            return value == 1

    container = Container()
    validator = Is[partial(contains, container)]
    assert container.calls == 0
    assert validator.is_valid(1)
    assert container.calls == 1


def test_api_vale_is_partial_python() -> None:
    '''Existing Python partials and bound methods retain their behavior.'''
    from beartype.vale import Is
    from functools import partial

    def above(threshold, value):
        return value > threshold

    def below(value, threshold):
        return value < threshold

    class Predicate:
        def above(self, threshold, value):
            return value > threshold

    for predicate in (partial(above, 1), partial(Predicate().above, 1)):
        validator = Is[predicate]
        assert validator.is_valid(2)
        assert not validator.is_valid(1)
    assert Is[partial(below, threshold=3)].is_valid(2)


def test_api_vale_is_partial_fail() -> None:
    '''Invalid or uninspectable partial signatures fail at subscription time.'''
    from beartype.roar import BeartypeValeSubscriptionException
    from beartype.vale import Is
    from functools import partial
    from operator import le
    from pytest import raises

    for predicate in (
        partial(le),
        partial(le, 1, 2),
        partial(le, 1, 2, 3),
        partial(le, 1, unknown=True),
        partial(le, a=1),
        partial(iter),
    ):
        with raises(BeartypeValeSubscriptionException, match='partial'):
            Is[predicate]

    # Non-partial predicates retain the existing fast-path rejection behavior.
    for predicate in (le, iter, lambda: True, lambda a, b: True):
        with raises(BeartypeValeSubscriptionException):
            Is[predicate]


def test_api_vale_is_partial_wrapped() -> None:
    '''Copied wrapper metadata must not hide the partial's effective arity.'''
    from beartype.vale import Is
    from functools import partial, update_wrapper
    from operator import le

    predicate = update_wrapper(partial(le, 1), le)
    validator = Is[predicate]
    assert validator.is_valid(2)
    assert not validator.is_valid(0)


def test_api_vale_is_partial_keyword_only() -> None:
    '''Fallback signatures check required and optional keyword-only values.'''
    from beartype.roar import BeartypeValeSubscriptionException
    from beartype.vale import Is
    from functools import partial
    from pytest import raises

    calls = []

    def below(value, *, threshold, enabled=True):
        calls.append(value)
        return enabled and value < threshold

    # Binding keywords makes the legacy positional-argument count reject these
    # valid partials, so their effective signature must be checked instead.
    for predicate in (
        partial(below, threshold=3),
        partial(below, threshold=3, enabled=True),
    ):
        validator = Is[predicate]
        assert not calls
        assert validator.is_valid(2)
        assert not validator.is_valid(3)
        calls.clear()

    # A remaining required keyword-only argument cannot be supplied by Is.
    with raises(BeartypeValeSubscriptionException, match='threshold'):
        Is[partial(below, enabled=True)]
    assert not calls


def test_api_vale_is_partial_positional_boundary() -> None:
    '''The fallback accepts exactly one, not merely one required, position.'''
    from beartype.roar import BeartypeValeSubscriptionException
    from beartype.vale import Is
    from functools import partial
    from pytest import raises

    # pow's optional third positional parameter still counts toward arity.
    with raises(BeartypeValeSubscriptionException, match='positional'):
        Is[partial(pow, 2)]

    # Binding that parameter by keyword makes it keyword-only in the partial.
    validator = Is[partial(pow, 2, mod=3)]
    assert validator.is_valid(1)
    assert not Is[partial(pow, 3, mod=3)].is_valid(1)

    # Binding the first parameter by keyword prevents any positional call.
    with raises(BeartypeValeSubscriptionException, match='partial'):
        Is[partial(pow, base=2)]
