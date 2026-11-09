#!/usr/bin/env python3
# --------------------( LICENSE                            )--------------------
# Copyright (c) 2014-2026 Beartype authors.
# See "LICENSE" for further details.

'''
Beartype **standard Python library decorators** (i.e., low-level private
decorators internally called by the high-level public :mod:`beartype` decorator
to decorate low-level objects created and returned by decorators defined by
modules in Python's standard library).

This private submodule is *not* intended for importation by downstream callers.
'''

# ....................{ IMPORTS                            }....................
from beartype.roar import BeartypeDecorWrappeeException
from beartype._data.typing.datatyping import BeartypeableT
from beartype._util.api.standard.utilfunctools import (
    is_func_functools_lru_cache)
from beartype._util.func.pep.utilfuncpep702 import (
    die_unless_func_pep702_deprecated,
    make_func_pep702_deprecated,
)
from beartype._util.func.pep.utilfuncpep484 import (
    is_func_pep484_notypechecked)
from beartype._util.func.utilfuncwrap import unwrap_func_once
from collections.abc import Callable
from functools import lru_cache, partial
from types import BuiltinFunctionType

# ....................{ DECORATORS ~ contextlib            }....................
def beartype_func_contextlib_contextmanager(
    func: BeartypeableT, func_contextmanager: Callable, **kwargs) -> (
    BeartypeableT):
    '''
    Decorate the passed :mod:`contextlib`-based **isomorphic decorator closure**
    (i.e., closure created and returned by either the standard
    :func:`contextlib.asynccontextmanager` or :func:`contextlib.contextmanager`
    decorator such that that closure isomorphically preserves both the number
    and types of all passed parameters and returns by accepting only a variadic
    positional argument and variadic keyword argument) with dynamically
    generated type-checking.

    Parameters
    ----------
    func : BeartypeableT
        Decorator closure to be decorated by :func:`beartype.beartype`.
    func_contextmanager : Callable
        Either:

        * If this context manager is a
          :func:`contextlib.asynccontextmanager`-based isomorphic decorator
          closure, :func:`contextlib.asynccontextmanager`.
        * Else, this context manager is a
          :func:`contextlib.contextmanager`-based isomorphic decorator closure.
          In this case, :func:`contextlib.contextmanager`.

    All remaining keyword parameters are passed as is to the lower-level
    :func:`beartype._decor._nontype.decornontype.beartype_nontype` decorator
    internally called by this higher-level decorator on the pure-Python function
    encapsulated in this descriptor.

    Returns
    -------
    BeartypeableT
        New pure-Python callable wrapping this context manager with
        type-checking.
    '''
    assert callable(func_contextmanager), (
        f'{repr(func_contextmanager)} uncallable.')
    # print(f'Redecorating {repr(func_contextmanager)}-decorated callable {repr(func)}...')

    # Avoid circular import dependencies.
    from beartype._decor._nontype.decornontype import beartype_nontype

    # Original pure-Python generator factory function decorated by either the
    # @contextlib.asynccontextmanager or @contextlib.contextmanager decorator.
    generator = unwrap_func_once(func)  # type: ignore[arg-type]

    # Decorate this generator factory function with type-checking.
    generator_checked = beartype_nontype(obj=generator, **kwargs)

    # Re-decorate this generator factory function by the same decorator.
    generator_checked_contextmanager = func_contextmanager(generator_checked)

    # Return this context manager.
    return generator_checked_contextmanager  # type: ignore[return-value]

# ....................{ DECORATORS ~ functools             }....................
def beartype_func_functools_partial(
    pseudofunc: partial, **kwargs) -> partial:
    '''
    Decorate the callable wrapped by a :class:`functools.partial`, preserving
    the arguments and instance attributes of that partial.

    Type-checking the wrapped callable rather than the partial ensures that
    both pre-bound and subsequently passed arguments are checked against the
    original annotations. Argument binding remains the responsibility of
    :class:`functools.partial`, including call-time keyword overrides.

    All remaining keyword parameters are passed to the lower-level
    :func:`beartype._decor.decorcore.beartype_object` decorator.
    '''
    assert type(pseudofunc) is partial, f'{repr(pseudofunc)} not partial.'

    # Avoid circular import dependencies.
    from beartype._decor.decorcore import beartype_object

    # Respect an opt-out on the partial itself. Builtin functions and bound
    # builtin methods have no annotations to enforce and need no wrapper.
    if (
        is_func_pep484_notypechecked(pseudofunc) or
        isinstance(pseudofunc.func, BuiltinFunctionType)
    ):
        return pseudofunc

    func_checked = beartype_object(pseudofunc.func, **kwargs)

    # Preserve identity when the wrapped callable requires no new wrapper.
    if func_checked is pseudofunc.func:
        return pseudofunc

    pseudofunc_checked = partial(
        func_checked, *pseudofunc.args, **pseudofunc.keywords)

    # Do not use update_wrapper(): adding __wrapped__ would hide the partial's
    # reduced signature from inspect.signature(). Preserve only existing
    # caller-defined attributes, including an explicitly supplied __wrapped__.
    pseudofunc_checked.__dict__.update(pseudofunc.__dict__)
    return pseudofunc_checked


def beartype_func_functools_lru_cache(
    pseudofunc: BeartypeableT, **kwargs) -> BeartypeableT:
    '''
    Monkey-patch the passed :func:`functools.lru_cache`-memoized
    **pseudo-callable** (i.e., low-level C-based callable object both created
    and returned by the standard :func:`functools.lru_cache` decorator) with
    dynamically generated type-checking.

    Parameters
    ----------
    pseudofunc : BeartypeableT
        Pseudo-callable to be monkey-patched by :func:`beartype.beartype`.

    All remaining keyword parameters are passed as is to the lower-level
    :func:`beartype._decor._nontype.decornontype.beartype_nontype` decorator
    internally called by this higher-level decorator on the pure-Python function
    encapsulated in this descriptor.

    Returns
    -------
    BeartypeableT
        New pseudo-callable monkey-patched by :func:`beartype.beartype`.
    '''

    # Avoid circular and third-party import dependencies.
    from beartype._decor._nontype.decornontype import beartype_nontype

    # If this pseudo-callable is *NOT* actually a @functools.lru_cache-memoized
    # callable, raise an exception.
    if not is_func_functools_lru_cache(pseudofunc):  # pragma: no cover
        raise BeartypeDecorWrappeeException(
            f'@functools.lru_cache-memoized callable {repr(pseudofunc)} not  '
            f'decorated by @functools.lru_cache.'
        )
    # Else, this pseudo-callable is a @functools.lru_cache-memoized callable.

    # Original pure-Python callable decorated by @functools.lru_cache.
    func = unwrap_func_once(pseudofunc)  # pyright: ignore

    # Decorate that callable with type-checking.
    func_checked = beartype_nontype(obj=func, **kwargs)

    # Dictionary mapping the names to values of all parameters originally passed
    # by the caller to that decorator, enabling the re-decoration of that
    # callable. Thankfully, that decorator preserves these parameters via the
    # decorator-specific "cache_parameters" instance variable whose value is a
    # bizarre argumentless lambda function (...for unknown reasons that are
    # probably indefensible) creating and returning this dictionary: e.g.,
    #     >>> from functools import lru_cache
    #     >>> @lru_cache(maxsize=3)
    #     ... def plus_one(n: int) -> int: return n +1
    #     >>> plus_one.cache_parameters()
    #     {'maxsize': 3, 'typed': False}
    lru_cache_kwargs = pseudofunc.cache_parameters()  # type: ignore[attr-defined]

    # Closure defined and returned by the @functools.lru_cache decorator when
    # passed these keyword parameters.
    lru_cache_configured = lru_cache(**lru_cache_kwargs)

    # Re-decorate that callable by @functools.lru_cache by the same parameters
    # originally passed by the caller to that decorator.
    pseudofunc_checked = lru_cache_configured(func_checked)

    # Return that new pseudo-callable.
    return pseudofunc_checked  # pyright: ignore

# ....................{ DECORATORS ~ warnings              }....................
def beartype_func_warnings_deprecated(
    func: BeartypeableT, **kwargs) -> BeartypeableT:
    '''
    Decorate the passed :func:`warnings.deprecated`-based **isomorphic decorator
    closure** (i.e., closure created and returned by the standard
    :func:`warnings.deprecated` decorator such that that closure isomorphically
    preserves both the number and types of all passed parameters and returns by
    accepting only a variadic positional argument and variadic keyword argument)
    with dynamically generated type-checking.

    Parameters
    ----------
    func : BeartypeableT
        Decorator closure to be decorated by :func:`beartype.beartype`.

    All remaining keyword parameters are passed as is to the lower-level
    :func:`beartype._decor._nontype.decornontype.beartype_nontype` decorator
    internally called by this higher-level decorator on the pure-Python function
    encapsulated in this descriptor.

    Returns
    -------
    BeartypeableT
        New pure-Python callable wrapping this context manager with
        type-checking.
    '''
    # print(f"Redecorating @{deprecated_source}.deprecated-decorated callable {repr(func)}...")

    # Avoid circular and third-party import dependencies.
    from beartype._decor._nontype.decornontype import beartype_nontype

    # If that callable is *NOT* a closure created and returned by the
    # @warnings.deprecated decorator, raise an exception.
    die_unless_func_pep702_deprecated(func)  # type: ignore[arg-type]
    # Else, that callable is a closure created and returned by the
    # @warnings.deprecated decorator.

    # Original pure-Python callable decorated by @warnings.deprecated.
    func_wrapped = unwrap_func_once(func)  # type: ignore[arg-type]

    # Decorate that callable with type-checking.
    func_wrapped_checked = beartype_nontype(obj=func_wrapped, **kwargs)

    # @warnings.deprecated decorator initialized with all parameters originally
    # passed to the passed @warnings.deprecated-based closure.
    deprecated_configured = make_func_pep702_deprecated(
        func=func, exception_cls=BeartypeDecorWrappeeException)  # type: ignore[arg-type]

    # Re-decorate that callable by @warnings.deprecated with the same parameters
    # originally passed by the caller to that decorator.
    deprecated_checked = deprecated_configured(func_wrapped_checked)

    # Return that new callable.
    return deprecated_checked  # type: ignore[return-value]
