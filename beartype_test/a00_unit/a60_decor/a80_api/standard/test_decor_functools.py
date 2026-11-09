#!/usr/bin/env python3
# --------------------( LICENSE                            )--------------------
# Copyright (c) 2014-2026 Beartype authors.
# See "LICENSE" for further details.

'''
Beartype decorator :mod:`functools`-specific unit tests.

This submodule unit tests the :func:`beartype.beartype` decorator with respect
the standard :mod:`functools` module.
'''

# ....................{ IMPORTS                            }....................
#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# WARNING: To raise human-readable test errors, avoid importing from
# package-specific submodules at module scope.
#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

# ....................{ TESTS                              }....................
def test_decor_functools_partial_arguments() -> None:
    '''Partials type-check both bound and call-time arguments.'''
    from beartype import beartype
    from beartype.roar import BeartypeCallHintParamViolation
    from functools import partial
    from pytest import raises

    def combine(first: str, second: str, *, separator: str = ' ') -> str:
        return separator.join((first, second))

    positional = beartype(partial(combine, 'The'))
    assert positional('bear') == 'The bear'
    with raises(BeartypeCallHintParamViolation):
        positional(42)
    with raises(BeartypeCallHintParamViolation):
        beartype(partial(combine, 42))('bear')

    keyword = beartype(partial(combine, second='bear', separator='-'))
    assert keyword('The') == 'The-bear'
    assert keyword('The', second='fox', separator=' ') == 'The fox'
    with raises(BeartypeCallHintParamViolation):
        keyword('The', separator=42)
    with raises(BeartypeCallHintParamViolation):
        beartype(partial(combine, second=42))('The')
    # An invalid pre-bound keyword may still be replaced by a valid one.
    assert beartype(partial(combine, second=42))('The', second='bear') == (
        'The bear')


def test_decor_functools_partial_returns() -> None:
    '''Partials preserve checks on the wrapped callable's return value.'''
    from beartype import beartype
    from beartype.roar import BeartypeCallHintReturnViolation
    from functools import partial
    from pytest import raises

    def misannotated(value: int) -> str:
        return value  # type: ignore[return-value]

    with raises(BeartypeCallHintReturnViolation):
        beartype(partial(misannotated, 42))()


def test_decor_functools_partial_binding() -> None:
    '''Native partial binding, including nested partials, remains intact.'''
    from beartype import beartype
    from beartype.roar import BeartypeCallHintParamViolation
    from functools import partial
    from pytest import raises

    def collect(first: int, /, *values: int, last: int) -> tuple:
        return first, values, last

    checked = beartype(partial(partial(collect, 1), 2, last=3))
    assert checked(4, 5) == (1, (2, 4, 5), 3)
    assert checked(last=6) == (1, (2,), 6)
    with raises(BeartypeCallHintParamViolation):
        checked('bad')
    with raises(TypeError):
        checked(unexpected=1)
    with raises(TypeError):
        beartype(partial(collect))()

    @beartype
    @partial(partial, second=2)
    def add(first: int, second: int = 2) -> int:
        return first + second

    assert add(1) == 3
    with raises(BeartypeCallHintParamViolation):
        add('bad')


def test_decor_functools_partial_metadata() -> None:
    '''Preserve partial metadata and introspection without mutating the input.'''
    from beartype import beartype
    from functools import partial, update_wrapper
    from inspect import signature

    def add(first: int, second: int = 2) -> int:
        return first + second

    original = partial(add, 1)
    original.description = 'A partial with metadata.'
    checked = beartype(original)
    assert isinstance(checked, partial)
    assert checked is not original
    assert original.func is add
    assert checked.func.__wrapped__ is add
    assert checked.args == original.args
    assert checked.keywords == original.keywords
    assert checked.description == original.description
    assert signature(checked) == signature(original)
    assert not hasattr(checked, '__wrapped__')
    assert beartype(checked) is checked

    wrapped = update_wrapper(partial(add, second=2), add)
    checked_wrapped = beartype(wrapped)
    assert checked_wrapped.__dict__ == wrapped.__dict__
    assert checked_wrapped(1) == 3
    assert signature(checked_wrapped) == signature(wrapped)

    # Instance attributes prevent functools.partial from flattening this
    # nesting, so both partials and the inner metadata must be preserved.
    nested = partial(original, second=3)
    assert nested.func is original
    checked_nested = beartype(nested)
    assert checked_nested() == 4
    assert checked_nested.func.description == original.description
    assert signature(checked_nested) == signature(nested)


def test_decor_functools_partial_methods() -> None:
    '''Partials of bound instance and class methods retain their receiver.'''
    from beartype import beartype
    from beartype.roar import BeartypeCallHintParamViolation
    from functools import partial
    from inspect import signature
    from pytest import raises

    class Adder:
        def add(self, first: int, second: int) -> int:
            return first + second

        @classmethod
        def add_class(cls, first: int, second: int) -> int:
            return first + second

    for method in (Adder().add, Adder.add_class):
        original = partial(method, 1)
        checked = beartype(original)
        assert checked(2) == 3
        assert signature(checked) == signature(original)
        with raises(BeartypeCallHintParamViolation):
            checked('bad')


def test_decor_functools_partial_subclass() -> None:
    '''Custom partial subclasses retain their existing callable handling.'''
    from beartype import beartype
    from beartype.roar import BeartypeCallHintParamViolation
    from functools import partial
    from pytest import raises

    def echo(value: int) -> int:
        return value

    class CustomPartial(partial):
        def __call__(self, value: str) -> str:
            return value

    # The subclass's __call__, not the wrapped function, defines its contract.
    original = CustomPartial(echo)
    checked = beartype(original)
    assert checked('bear') == 'bear'
    with raises(BeartypeCallHintParamViolation):
        checked(42)
    assert original.func is echo


def test_decor_functools_partial_async() -> None:
    '''Partial coroutine functions preserve awaitability and return checking.'''
    from asyncio import run
    from beartype import beartype
    from beartype.roar import (
        BeartypeCallHintParamViolation,
        BeartypeCallHintReturnViolation,
    )
    from functools import partial
    from inspect import iscoroutinefunction
    from pytest import raises

    async def echo(value: int) -> int:
        return value

    checked = beartype(partial(echo, 42))
    assert iscoroutinefunction(checked)
    assert run(checked()) == 42
    with raises(BeartypeCallHintParamViolation):
        run(beartype(partial(echo, 'bad'))())

    async def misannotated() -> int:
        return 'bad'  # type: ignore[return-value]

    with raises(BeartypeCallHintReturnViolation):
        run(beartype(partial(misannotated))())


def test_decor_functools_partial_noop() -> None:
    '''Unannotated, builtin, and explicitly unchecked partials remain noops.'''
    from beartype import BeartypeConf, BeartypeStrategy, beartype
    from functools import partial
    from typing import no_type_check

    def unannotated(value):
        return value

    for original in (partial(unannotated, 42), partial(len, [1, 2])):
        assert beartype(original) is original

    def annotated(value: int) -> int:
        return value

    unchecked = no_type_check(partial(annotated, 'bad'))
    assert beartype(unchecked) is unchecked
    assert unchecked() == 'bad'

    opted_out = partial(no_type_check(annotated), 'bad')
    assert beartype(opted_out) is opted_out

    def disabled(value: int) -> int:
        return value

    original = partial(disabled, 'bad')
    assert beartype(original, conf=BeartypeConf(
        strategy=BeartypeStrategy.O0)) is original


def test_decor_functools_partial_configuration() -> None:
    '''Configuration reaches the callable inside a partial.'''
    from beartype import BeartypeConf, beartype
    from functools import partial
    from pytest import warns

    def echo(value: int) -> int:
        return value

    checked = beartype(partial(echo), conf=BeartypeConf(
        violation_type=UserWarning))
    with warns(UserWarning):
        assert checked('bad') == 'bad'


def test_decor_functools_lru_cache() -> None:
    '''
    Test the :func:`beartype.beartype` decorator on
    :func:`functools.lru_cache`-based **memoized callables** (i.e., pure-Python
    callables decorated by that standard decorator, which then creates and
    returns low-level C-based callable objects memoizing those callables).
    '''

    # ....................{ IMPORTS                        }....................
    # Defer test-specific imports.
    from beartype import beartype
    from beartype.roar import (
        BeartypeCallHintParamViolation,
        # BeartypeDecorWrappeeException,
    )
    from functools import lru_cache
    from pytest import raises

    # ....................{ IDEAL                          }....................
    @lru_cache(maxsize=3)
    @beartype
    def increment_int_goodly(n: int) -> int:
        '''
        Arbitrary :func:`functools.lru_cache`-memoized callable decorated by
        :func:`beartype.beartype` in the ideal order.
        '''

        return n + 1


    # Assert that the ideal memoized callable when passed a valid parameter
    # returns the expected return.
    assert increment_int_goodly(42) == 43

    # Assert that the ideal memoized callable when passed an invalid parameter
    # raises the expected exception.
    with raises(BeartypeCallHintParamViolation):
        increment_int_goodly('The lone couch of his everlasting sleep:—')

    # ....................{ NON-IDEAL                      }....................
    @beartype
    @lru_cache(maxsize=3)
    def increment_int_badly(n: int) -> int:
        '''
        Arbitrary :func:`functools.lru_cache`-memoized callable decorated by
        :func:`beartype.beartype` in a non-ideal order.
        '''

        return n + 1

    # Assert that the non-ideal memoized callable when passed a valid parameter
    # returns the expected value.
    assert increment_int_badly(24) == 25

    # Assert that the non-ideal memoized callable when passed an invalid
    # parameter raises the expected exception.
    with raises(BeartypeCallHintParamViolation):
        increment_int_badly('Gentle, and brave, and generous,—no lorn bard')

    # ....................{ CLASSES                        }....................
    @beartype
    class IntIncrementer(object):
        '''
        Arbitrary :func:`beartype.beartype`-decorated class defining various
        :func:`functools.lru_cache`-memoized methods exercising edge cases.
        '''

        # ....................{ NON-IDEAL ~ static         }....................
        @staticmethod
        @lru_cache(maxsize=3)
        def increment_int_badly_statically(n: int) -> int:
            '''
            Arbitrary :func:`functools.lru_cache`-memoized static method
            implicitly decorated by :func:`beartype.beartype` in a non-ideal
            order.

            This static method exercises an edge cases, as:

            #. The :func:`.lru_cache` decorator creates and returns a
               **pseudo-callable object** (i.e., object callable only due to the
               type of that object defining the ``__call__()`` dunder method)
               rather than a pure-Python function.
            #. The builtin :class:`staticmethod` type then creates and returns a
               C-based descriptor object calling that pseudo-callable object.
            #. The :func:`beartype.beartype` decorator then:

               #. Unwraps that C-based descriptor object to access that
                  pseudo-callable object.
               #. Recreates that C-based descriptor object to instead wrap a
                  dynamically generated type-checking wrapper function calling
                  that pseudo-callable object.

            In short, madness.
            '''

            return n + 1

    # Assert that the non-ideal memoized callable when passed a valid parameter
    # returns the expected value.
    assert IntIncrementer.increment_int_badly_statically(42) == 43

    # Assert that the non-ideal memoized callable when passed an invalid
    # parameter raises the expected exception.
    with raises(BeartypeCallHintParamViolation):
        IntIncrementer.increment_int_badly_statically(
            'As if the ebbing air had but one wave;')
