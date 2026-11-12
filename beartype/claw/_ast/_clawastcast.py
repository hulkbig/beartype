#!/usr/bin/env python3
# --------------------( LICENSE                            )--------------------
# Copyright (c) 2014-2026 Beartype authors.
# See "LICENSE" for further details.

'''
Private runtime support for import-hooked :func:`typing.cast` calls.
'''
from typing import cast as _typing_cast
from beartype._conf.confmain import BeartypeConf
from beartype._conf.confcommon import BEARTYPE_CONF_DEFAULT
from beartype._conf.confenum import BeartypeStrategy
from beartype._util.cache.func.utilcachefunc import callable_cached
from beartype.door._func.doorfunc import die_if_unbearable


def select_cast(callee, *, conf: BeartypeConf = BEARTYPE_CONF_DEFAULT):
    '''
    Return a checked cast if this callable is the original :func:`typing.cast`,
    or preserve this callable otherwise. Never cache arbitrary user callables:
    they need not be hashable and may define side-effectful equality methods.

    Selecting the callable before evaluating its arguments preserves Python's
    callable-first evaluation, including rebinding during argument evaluation.
    '''
    return (
        _make_cast_checker(conf)
        if (
            callee is _typing_cast and conf.claw_is_pep484 and
            conf.strategy is not BeartypeStrategy.O0
        ) else callee
    )


@callable_cached
def _make_cast_checker(conf: BeartypeConf):
    '''Cache one cast checker per configuration, rather than per call site.'''

    def cast(typ, val):
        # Match typing.cast's two flexible parameter names, including keyword
        # calls and Python's normal argument-binding errors. Return identity
        # also matters when a configured violation emits a warning.
        die_if_unbearable(val, typ, conf=conf, exception_prefix='typing.cast() ')
        return val

    return cast
