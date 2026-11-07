#!/usr/bin/env python3
# --------------------( LICENSE                            )--------------------
# Copyright (c) 2014-2026 Beartype authors.
# See "LICENSE" for further details.

'''
**Beartype validator callable utilities** (i.e., callables performing low-level
callable-centric operations on behalf of higher-level beartype validators).

This private submodule is *not* intended for importation by downstream callers.
'''

# ....................{ IMPORTS                            }....................
from beartype.roar import BeartypeValeSubscriptionException
from beartype._cave._cavefast import CallableFunctoolsPartialType
from beartype.vale._util._valeutiltyping import BeartypeValidatorTester
from beartype._util.func.arg.utilfuncargtest import (
    die_unless_func_args_len_flexible_equal)

# ....................{ FORMATTERS                         }....................
def die_unless_validator_tester(
    validator_tester: BeartypeValidatorTester) -> None:
    '''
    Raise an exception unless the passed object is a **validator tester** (i.e.,
    caller-defined callable accepting a single arbitrary object and returning
    either :data:`True` if that object satisfies an arbitrary constraint *or*
    :data:`False` otherwise).

    Parameters
    ----------
    validator_tester : BeartypeValidatorTester
        Object to be validated.

    Raises
    ------
    beartype.roar.BeartypeValeSubscriptionException
        If that object is either:

        * *Not* callable.
        * A C-based callable other than a partial exposing a signature with
          exactly one positional parameter and no unbound required keywords.
        * A pure-Python callable accepting two or more arguments.
    '''

    # Prefer the existing code-object check for pure-Python predicates.
    try:
        die_unless_func_args_len_flexible_equal(
            func=validator_tester,
            func_args_len_flexible=1,
            exception_cls=BeartypeValeSubscriptionException,
        )
    except BeartypeValeSubscriptionException:
        # Preserve the fast code-object check and all previously supported
        # predicates. C-based wrappees have no code objects, but some expose
        # signatures that inspect can safely adjust for partial arguments.
        if not isinstance(validator_tester, CallableFunctoolsPartialType):
            raise

        # Defer this comparatively heavyweight fallback until actually needed.
        from inspect import Parameter, signature

        try:
            validator_signature = signature(
                validator_tester, follow_wrapped=False)
            validator_args_len = sum(
                parameter.kind in (
                    Parameter.POSITIONAL_ONLY,
                    Parameter.POSITIONAL_OR_KEYWORD,
                )
                for parameter in validator_signature.parameters.values()
            )
            if validator_args_len != 1:
                raise ValueError('expected exactly one positional parameter')

            # Bind a placeholder, without calling the predicate, to also reject
            # remaining required keyword-only parameters and invalid partials.
            validator_signature.bind(object())
        except (TypeError, ValueError) as exception:
            raise BeartypeValeSubscriptionException(
                f'{validator_tester!r} not a partial with an inspectable '
                f'single-argument signature: {exception}.') from exception
    # This validator accepts one parameter. Since no further validation can be
    # performed without unsafely calling it, we accept this callable as is.
    #
    # Note that we *COULD* technically inspect annotations if defined on
    # this callable as well. Since this callable is typically defined as a
    # lambda, annotations are typically *NOT* defined on this callable.
