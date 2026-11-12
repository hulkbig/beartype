#!/usr/bin/env python3
# --------------------( LICENSE                            )--------------------
# Copyright (c) 2014-2026 Beartype authors.
# See "LICENSE" for further details.

'''
Integration tests for import-hooked :pep:`484` cast expressions.

Each test imports a fresh temporary package in a subprocess, isolating import
hooks, module caches, and changes to the shared :mod:`typing` module.
'''


def _run_cast_module(
    tmp_path, source, conf='BeartypeConf()', module_name=None) -> None:
    '''Import and execute ``source`` with the requested claw configuration.'''
    import os
    import subprocess
    import sys
    from textwrap import dedent
    from beartype_test._util.path.pytpathmain import get_main_repo_dir

    package = tmp_path / 'cast_package'
    package.mkdir(exist_ok=True)
    (package / '__init__.py').write_text('', encoding='utf-8')
    # A unique module avoids stale bytecode when one test tries several imports.
    if module_name is None:
        module_name = 'example_{}'.format(
            len(tuple(package.glob('example_*.py'))))
    if source is not None:
        (package / (module_name + '.py')).write_text(
            dedent(source), encoding='utf-8')
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join((
        str(get_main_repo_dir()), str(tmp_path), env.get('PYTHONPATH', '')))
    result = subprocess.run(
        [sys.executable, '-c', dedent('''
            from beartype import BeartypeConf, BeartypeStrategy, FrozenDict
            from beartype.claw import beartype_package
            conf = {conf}
            beartype_package('cast_package', conf=conf)
            import cast_package.{module_name}
        ''').format(conf=conf, module_name=module_name)],
        cwd=str(tmp_path), env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_claw_cast_import_forms(tmp_path) -> None:
    '''Explicit module and callable aliases all enforce cast hints.'''
    for statement, expression in (
        ('import typing', 'typing.cast'),
        ('import typing as t', 't.cast'),
        ('from typing import cast', 'cast'),
        ('from typing import cast as checked', 'checked'),
        ('import beartype.typing', 'beartype.typing.cast'),
        ('import beartype.typing as t', 't.cast'),
        ('from beartype import typing as t', 't.cast'),
        ('from beartype.typing import cast', 'cast'),
        ('from beartype.typing import cast as checked', 'checked'),
        ('from typing import *', 'cast'),
        ('from beartype.typing import *', 'cast'),
    ):
        _run_cast_module(tmp_path, '''
            {statement}
            from beartype.roar import BeartypeDoorHintViolation
            value = object()
            assert {expression}(object, value) is value
            try:
                {expression}(int, 'not an integer')
            except BeartypeDoorHintViolation:
                pass
            else:
                raise AssertionError('Invalid cast was not checked')
        '''.format(statement=statement, expression=expression))


def test_claw_cast_late_imports(tmp_path) -> None:
    '''Functions preceding imports and function-local imports are checked.'''
    _run_cast_module(tmp_path, '''
        from beartype.roar import BeartypeDoorHintViolation
        def early():
            return cast(int, 'invalid')
        def local():
            from typing import cast as local_cast
            return local_cast(int, 'invalid')
        from typing import cast
        for function in (early, local):
            try:
                function()
            except BeartypeDoorHintViolation:
                pass
            else:
                raise AssertionError('Late import was not checked')
    ''')


def test_claw_cast_shadowing(tmp_path) -> None:
    '''Imported names may be shadowed or rebound to unrelated callables.'''
    _run_cast_module(tmp_path, '''
        import typing
        from typing import cast
        from types import SimpleNamespace
        from beartype.roar import BeartypeDoorHintViolation
        original_cast = typing.cast
        def unrelated(*args, **kwargs):
            return (args, kwargs)
        def shadowed(cast):
            return cast('anything', extra=42)
        assert shadowed(unrelated) == (('anything',), {'extra': 42})
        cast = unrelated
        assert cast(1, 2, 3) == ((1, 2, 3), {})
        cast = original_cast
        try:
            cast(int, 'invalid')
        except BeartypeDoorHintViolation:
            pass
        else:
            raise AssertionError('Restored cast was not checked')
        typing = SimpleNamespace(cast=unrelated)
        assert typing.cast(extra=42) == ((), {'extra': 42})
        import typing as real_typing
        real_typing.cast = unrelated
        assert real_typing.cast(1, 2, 3) == ((1, 2, 3), {})
    ''')


def test_claw_cast_call_semantics(tmp_path) -> None:
    '''Calls retain evaluation order, keyword unpacking, and value identity.'''
    _run_cast_module(tmp_path, '''
        import typing
        from typing import cast
        events = []
        value = object()
        def record(name, result):
            events.append(name)
            return result
        assert cast(record('hint', object), record('value', value)) is value
        assert events == ['hint', 'value']
        events.clear()
        assert cast(val=record('value', value),
                    typ=record('hint', object)) is value
        assert events == ['value', 'hint']
        events.clear()
        assert cast(*record('args', (object,)),
                    **record('kwargs', {'val': value})) is value
        assert events == ['args', 'kwargs']
        assert cast(**{'val': value, 'typ': object}) is value
        # The callable is resolved before arguments may rebind its name.
        def replace_cast():
            global cast
            cast = lambda *args: 'replacement'
            return value
        assert cast(object, replace_cast()) is value
        assert cast(object, value) == 'replacement'
        # Attribute lookup also happens exactly once, before argument evaluation.
        original_cast = typing.cast
        class Provider:
            @property
            def cast(self):
                events.append('callable')
                return original_cast
        typing = Provider()
        events.clear()
        assert typing.cast(record('hint', object),
                           record('value', value)) is value
        assert events == ['callable', 'hint', 'value']
    ''')



def test_claw_cast_argument_binding(tmp_path) -> None:
    '''Unpacking validates values without changing normal argument errors.'''
    _run_cast_module(tmp_path, '''
        from typing import cast
        from beartype.roar import BeartypeDoorHintViolation
        for operation in (
            lambda: cast(typ=int, val='invalid'),
            lambda: cast(*(int, 'invalid')),
            lambda: cast(**{'typ': int, 'val': 'invalid'}),
            lambda: cast(*(int,), **{'val': 'invalid'}),
        ):
            try:
                operation()
            except BeartypeDoorHintViolation:
                pass
            else:
                raise AssertionError('Unpacked invalid cast was not checked')
        for operation in (
            lambda: cast(),
            lambda: cast(int),
            lambda: cast(int, 1, 2),
            lambda: cast(int, 1, val=2),
            lambda: cast(int, 1, unexpected=2),
        ):
            try:
                operation()
            except TypeError:
                pass
            else:
                raise AssertionError('Malformed cast did not raise TypeError')
    ''')

def test_claw_cast_expression_contexts(tmp_path) -> None:
    '''Casts are checked in nested expressions, lambdas, and async functions.'''
    _run_cast_module(tmp_path, '''
        import asyncio
        from typing import cast
        from beartype.roar import BeartypeDoorHintViolation
        identity = object()
        assert [cast(object, value) for value in [identity]] == [identity]
        assert (lambda: cast(object, identity))() is identity
        async def get_value():
            return identity
        async def valid():
            return cast(object, await get_value())
        assert asyncio.run(valid()) is identity
        async def invalid():
            return cast(int, 'invalid')
        for operation in (
            lambda: cast(int, 'invalid'),
            lambda: [cast(int, value) for value in ['invalid']],
            lambda: asyncio.run(invalid()),
        ):
            try:
                operation()
            except BeartypeDoorHintViolation:
                pass
            else:
                raise AssertionError('Expression cast was not checked')
    ''')


def test_claw_cast_warning_policy(tmp_path) -> None:
    '''Warning-configured cast violations warn and return the original value.'''
    _run_cast_module(tmp_path, '''
        import warnings
        from typing import cast
        value = object()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            assert cast(int, value) is value
        assert len(caught) == 1
        assert caught[0].category is UserWarning
    ''', conf='BeartypeConf(violation_door_type=UserWarning)')


def test_claw_cast_opt_out(tmp_path) -> None:
    '''Disabling PEP 484 checks preserves the original unchecked cast.'''
    _run_cast_module(tmp_path, '''
        import typing
        from typing import cast
        from beartype.roar import BeartypeCallHintParamViolation
        value = object()
        assert cast is typing.cast
        assert cast(int, value) is value
        # Other import-hook features must remain enabled.
        def checked(value: int):
            return value
        try:
            checked('invalid')
        except BeartypeCallHintParamViolation:
            pass
        else:
            raise AssertionError('Opt-out disabled unrelated checking')
    ''', conf='BeartypeConf(claw_is_pep484=False)')


def test_claw_cast_strategy_o0(tmp_path) -> None:
    '''The no-check strategy also applies to imported cast expressions.'''
    _run_cast_module(tmp_path, '''
        from typing import cast
        value = object()
        assert cast(int, value) is value
    ''', conf='BeartypeConf(strategy=BeartypeStrategy.O0)')


def test_claw_cast_typing_unchanged(tmp_path) -> None:
    '''Checking calls does not replace the imported cast function globally.'''
    _run_cast_module(tmp_path, '''
        import typing
        import beartype.typing
        from typing import cast
        original = typing.cast
        assert cast is original
        assert beartype.typing.cast is original
        value = object()
        assert cast(object, value) is value
        assert typing.cast is original
        # Code outside the hooked module remains unaffected.
        assert eval("cast(int, value)", {'cast': original, 'value': value}) is value
    ''')


def test_claw_cast_cached_configuration(tmp_path) -> None:
    '''Reused bytecode respects the current process's cast configuration.'''
    configurations = (
        'BeartypeConf(claw_is_pep484=False)',
        'BeartypeConf()',
        'BeartypeConf(violation_door_type=UserWarning)',
    )
    for index, (initial_conf, next_conf) in enumerate((
        (configurations[0], configurations[1]),
        (configurations[1], configurations[0]),
        (configurations[1], configurations[2]),
        (configurations[2], configurations[1]),
    )):
        case_path = tmp_path / str(index)
        case_path.mkdir()
        source = '''
            import __main__
            from typing import cast
            from beartype.roar import BeartypeDoorHintViolation
            value = object()
            if issubclass(__main__.conf.violation_door_type, Warning):
                import warnings
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    assert cast(int, value) is value
                assert len(caught) == 1
                assert caught[0].category is UserWarning
            elif __main__.conf.claw_is_pep484:
                try:
                    cast(int, value)
                except BeartypeDoorHintViolation:
                    pass
                else:
                    raise AssertionError('Cached cast was not checked')
            else:
                assert cast(int, value) is value
        '''
        _run_cast_module(
            case_path, source,
            conf=initial_conf,
            module_name='cached')
        cached_files = tuple(
            (case_path / 'cast_package' / '__pycache__').glob('cached.*.pyc'))
        assert cached_files, 'The first import must create cached bytecode'
        snapshots = {
            path: (path.read_bytes(), path.stat().st_mtime_ns)
            for path in cached_files}
        _run_cast_module(
            case_path, None,
            conf=next_conf,
            module_name='cached')
        assert tuple(
            (case_path / 'cast_package' / '__pycache__').glob('cached.*.pyc')
        ) == cached_files
        for path, snapshot in snapshots.items():
            assert (path.read_bytes(), path.stat().st_mtime_ns) == snapshot


def test_claw_cast_custom_configuration(tmp_path) -> None:
    '''Cast checks inherit hint overrides and the configured exception class.'''
    _run_cast_module(tmp_path, '''
        from typing import cast
        value = 'accepted by the override'
        assert cast(int, value) is value
        try:
            cast(int, 42)
        except RuntimeError as exception:
            assert type(exception) is RuntimeError
        else:
            raise AssertionError('Custom violation exception was not raised')
    ''', conf=(
        'BeartypeConf(hint_overrides=FrozenDict({int: str}), '
        'violation_door_type=RuntimeError)'))


def test_claw_cast_candidate_calls_only() -> None:
    '''Only syntactic candidates have their callable AST nodes wrapped.'''
    import ast
    from beartype import BeartypeConf
    from beartype.claw._ast.clawastmain import BeartypeNodeTransformer

    tree = ast.parse(
        'from typing import cast\n'
        'ordinary(value)\n'
        'unrelated.cast(int, value)\n'
        'cast(int, value)\n')
    ordinary, unrelated, candidate = [node.value for node in tree.body[1:]]
    ordinary_before = ast.dump(ordinary)
    unrelated_before = ast.dump(unrelated)
    candidate_arguments = tuple(candidate.args)
    BeartypeNodeTransformer(
        module_name='cast_package.example', conf=BeartypeConf()).visit(tree)
    assert ast.dump(ordinary) == ordinary_before
    assert ast.dump(unrelated) == unrelated_before
    assert isinstance(candidate.func, ast.Call)
    assert candidate.func.func.id == '__select_cast_beartype__'
    assert tuple(candidate.args) == candidate_arguments


def test_claw_cast_unhashable_shadow(tmp_path) -> None:
    '''Shadowed callables receive their original keywords without collisions.'''
    _run_cast_module(tmp_path, '''
        from typing import cast
        class Unhashable:
            __hash__ = None
            def __eq__(self, other):
                raise AssertionError('Callable equality must not be tested')
            def __call__(self, *, conf, callee):
                return conf, callee
        cast = Unhashable()
        assert cast(conf='configuration', callee='callable') == (
            'configuration', 'callable')
        try:
            cast(conf='configuration', callee='callable', unexpected=True)
        except TypeError:
            pass
        else:
            raise AssertionError('Malformed shadow call must raise TypeError')
    ''')


def test_claw_cast_private_alias_and_frames(tmp_path) -> None:
    '''Private aliases and frame-sensitive builtins retain Python semantics.'''
    _run_cast_module(tmp_path, '''
        from typing import cast
        from beartype.roar import BeartypeDoorHintViolation
        class Private:
            from typing import cast as __cast
            value = __cast(int, 1)
            def invalid(self):
                from typing import cast as __cast
                return __cast(int, 'invalid')
        assert Private.value == 1
        try:
            Private().invalid()
        except BeartypeDoorHintViolation:
            pass
        else:
            raise AssertionError('Private cast alias must be checked')
        # These local bindings cause the module-wide census to consider the
        # builtin spellings elsewhere, but must not wrap their invocation.
        def unused():
            from typing import cast as super
            from typing import cast as locals
        class Base:
            def result(self):
                return 42
        class Derived(Base):
            def result(self):
                marker = 'same frame'
                assert locals()['marker'] == marker
                assert super().result() == 42
                # A super proxy is not an instance of Base. Evaluation must
                # still reach validation, rather than losing the class frame.
                try:
                    cast(Base, super())
                except BeartypeDoorHintViolation:
                    pass
                else:
                    raise AssertionError('Invalid super proxy cast accepted')
                return cast(object, super()).result()
        assert Derived().result() == 42
    ''')
