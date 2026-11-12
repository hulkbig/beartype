#!/usr/bin/env python3
# --------------------( LICENSE                            )--------------------
# Copyright (c) 2014-2026 Beartype authors.
# See "LICENSE" for further details.

'''
Import-hook transformations for explicitly imported :func:`typing.cast` calls.
'''
from ast import Attribute, Call, Import, ImportFrom, Load, Name, walk
from beartype._util.ast.utilastmunge import copy_node_metadata


class BeartypeNodeTransformerCallMixin(object):
    '''
    Recognize cast import spellings without pretending to resolve Python names.

    This module-wide census intentionally overapproximates lexical bindings.
    The runtime selector checks callable identity, so shadowing, conditional
    imports and rebinding cannot accidentally validate an unrelated callable.
    Only matching call spellings incur overhead; arbitrary indirect aliases
    and re-exports are deliberately outside this transformation's contract.
    '''

    def _collect_cast_imports(self, node) -> None:
        self._cast_names = set()
        self._cast_modules = set()
        for child in walk(node):
            if isinstance(child, Import):
                for alias in child.names:
                    if alias.name in ('typing', 'beartype.typing'):
                        self._cast_modules.add(alias.asname or alias.name)
            elif isinstance(child, ImportFrom) and child.level == 0:
                if child.module in ('typing', 'beartype.typing'):
                    for alias in child.names:
                        if alias.name in ('cast', '*'):
                            self._cast_names.add(
                                alias.asname or 'cast')
                elif child.module == 'beartype':
                    for alias in child.names:
                        if alias.name == 'typing':
                            self._cast_modules.add(alias.asname or 'typing')

    def visit_Call(self, node: Call) -> Call:
        # Visit original children once before injecting the selector, which
        # must not itself become a candidate for recursive instrumentation.
        self.generic_visit(node)  # type: ignore[attr-defined]
        callee = node.func
        is_cast = isinstance(callee, Name) and callee.id in self._cast_names
        if isinstance(callee, Attribute) and callee.attr == 'cast':
            parts = []
            module = callee.value
            while isinstance(module, Attribute):
                parts.append(module.attr)
                module = module.value
            if isinstance(module, Name):
                parts.append(module.id)
                is_cast = '.'.join(reversed(parts)) in self._cast_modules
        if not is_cast:
            return node

        selector_name = Name(id='__select_cast_beartype__', ctx=Load())
        # Cached bytecode can be reused under a different hook configuration
        # in another process. Resolve the current configuration even when the
        # configuration at compilation time happens to be the default.
        keywords = [self._make_node_keyword_conf(node)]  # type: ignore[attr-defined]
        selector = Call(func=selector_name, args=[callee], keywords=keywords)
        copy_node_metadata(node_src=node, node_trg=(selector_name, selector))
        # Preserve arguments verbatim: wrapping the outer call or forwarding
        # its keywords through the selector would alter binding/evaluation.
        node.func = selector
        return node
