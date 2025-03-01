import asyncio
import textwrap
import types
import unittest
from test.support import requires_working_socket, check_syntax_error, run_code

from typing import Generic, Sequence, TypeVar, TypeVarTuple, ParamSpec, get_args


class TypeParamsInvalidTest(unittest.TestCase):
    def test_name_collisions(self):
        check_syntax_error(self, 'def func[**A, A](): ...', "duplicate type parameter 'A'")
        check_syntax_error(self, 'def func[A, *A](): ...', "duplicate type parameter 'A'")
        check_syntax_error(self, 'def func[*A, **A](): ...', "duplicate type parameter 'A'")

        check_syntax_error(self, 'class C[**A, A](): ...', "duplicate type parameter 'A'")
        check_syntax_error(self, 'class C[A, *A](): ...', "duplicate type parameter 'A'")
        check_syntax_error(self, 'class C[*A, **A](): ...', "duplicate type parameter 'A'")

    def test_name_non_collision_02(self):
        ns = run_code("""def func[A](A): return A""")
        func = ns["func"]
        self.assertEqual(func(1), 1)
        A, = func.__type_params__
        self.assertEqual(A.__name__, "A")

    def test_name_non_collision_03(self):
        ns = run_code("""def func[A](*A): return A""")
        func = ns["func"]
        self.assertEqual(func(1), (1,))
        A, = func.__type_params__
        self.assertEqual(A.__name__, "A")

    def test_name_non_collision_04(self):
        # Mangled names should not cause a conflict.
        ns = run_code("""
            class ClassA:
                def func[__A](self, __A): return __A
            """
        )
        cls = ns["ClassA"]
        self.assertEqual(cls().func(1), 1)
        A, = cls.func.__type_params__
        self.assertEqual(A.__name__, "__A")

    def test_name_non_collision_05(self):
        ns = run_code("""
            class ClassA:
                def func[_ClassA__A](self, __A): return __A
            """
        )
        cls = ns["ClassA"]
        self.assertEqual(cls().func(1), 1)
        A, = cls.func.__type_params__
        self.assertEqual(A.__name__, "_ClassA__A")

    def test_name_non_collision_06(self):
        ns = run_code("""
            class ClassA[X]:
                def func(self, X): return X
            """
        )
        cls = ns["ClassA"]
        self.assertEqual(cls().func(1), 1)
        X, = cls.__type_params__
        self.assertEqual(X.__name__, "X")

    def test_name_non_collision_07(self):
        ns = run_code("""
            class ClassA[X]:
                def func(self):
                    X = 1
                    return X
            """
        )
        cls = ns["ClassA"]
        self.assertEqual(cls().func(), 1)
        X, = cls.__type_params__
        self.assertEqual(X.__name__, "X")

    def test_name_non_collision_08(self):
        ns = run_code("""
            class ClassA[X]:
                def func(self):
                    return [X for X in [1, 2]]
            """
        )
        cls = ns["ClassA"]
        self.assertEqual(cls().func(), [1, 2])
        X, = cls.__type_params__
        self.assertEqual(X.__name__, "X")

    def test_name_non_collision_9(self):
        ns = run_code("""
            class ClassA[X]:
                def func[X](self):
                    ...
            """
        )
        cls = ns["ClassA"]
        outer_X, = cls.__type_params__
        inner_X, = cls.func.__type_params__
        self.assertEqual(outer_X.__name__, "X")
        self.assertEqual(inner_X.__name__, "X")
        self.assertIsNot(outer_X, inner_X)

    def test_name_non_collision_10(self):
        ns = run_code("""
            class ClassA[X]:
                X: int
            """
        )
        cls = ns["ClassA"]
        X, = cls.__type_params__
        self.assertEqual(X.__name__, "X")
        self.assertIs(cls.__annotations__["X"], int)

    def test_name_non_collision_13(self):
        ns = run_code("""
            X = 1
            def outer():
                def inner[X]():
                    global X
                    X = 2
                return inner
            """
        )
        self.assertEqual(ns["X"], 1)
        outer = ns["outer"]
        outer()()
        self.assertEqual(ns["X"], 2)

    def test_disallowed_expressions(self):
        check_syntax_error(self, "type X = (yield)")
        check_syntax_error(self, "type X = (yield from x)")
        check_syntax_error(self, "type X = (await 42)")
        check_syntax_error(self, "async def f(): type X = (yield)")
        check_syntax_error(self, "type X = (y := 3)")
        check_syntax_error(self, "class X[T: (yield)]: pass")
        check_syntax_error(self, "class X[T: (yield from x)]: pass")
        check_syntax_error(self, "class X[T: (await 42)]: pass")
        check_syntax_error(self, "class X[T: (y := 3)]: pass")
        check_syntax_error(self, "class X[T](y := Sequence[T]): pass")
        check_syntax_error(self, "def f[T](y: (x := Sequence[T])): pass")
        check_syntax_error(self, "class X[T]([(x := 3) for _ in range(2)] and B): pass")
        check_syntax_error(self, "def f[T: [(x := 3) for _ in range(2)]](): pass")
        check_syntax_error(self, "type T = [(x := 3) for _ in range(2)]")


class TypeParamsNonlocalTest(unittest.TestCase):
    def test_nonlocal_disallowed_01(self):
        code = """
            def outer():
                X = 1
                def inner[X]():
                    nonlocal X
                return X
            """
        check_syntax_error(self, code)

    def test_nonlocal_disallowed_02(self):
        code = """
            def outer2[T]():
                def inner1():
                    nonlocal T
        """
        check_syntax_error(self, textwrap.dedent(code))

    def test_nonlocal_disallowed_03(self):
        code = """
            class Cls[T]:
                nonlocal T
        """
        check_syntax_error(self, textwrap.dedent(code))

    def test_nonlocal_allowed(self):
        code = """
            def func[T]():
                T = "func"
                def inner():
                    nonlocal T
                    T = "inner"
                inner()
                assert T == "inner"
        """
        ns = run_code(code)
        func = ns["func"]
        T, = func.__type_params__
        self.assertEqual(T.__name__, "T")


class TypeParamsAccessTest(unittest.TestCase):
    def test_class_access_01(self):
        ns = run_code("""
            class ClassA[A, B](dict[A, B]):
                ...
            """
        )
        cls = ns["ClassA"]
        A, B = cls.__type_params__
        self.assertEqual(types.get_original_bases(cls), (dict[A, B], Generic[A, B]))

    def test_class_access_02(self):
        ns = run_code("""
            class MyMeta[A, B](type): ...
            class ClassA[A, B](metaclass=MyMeta[A, B]):
                ...
            """
        )
        meta = ns["MyMeta"]
        cls = ns["ClassA"]
        A1, B1 = meta.__type_params__
        A2, B2 = cls.__type_params__
        self.assertIsNot(A1, A2)
        self.assertIsNot(B1, B2)
        self.assertIs(type(cls), meta)

    def test_class_access_03(self):
        code = """
            def my_decorator(a):
                ...
            @my_decorator(A)
            class ClassA[A, B]():
                ...
            """

        with self.assertRaisesRegex(NameError, "name 'A' is not defined"):
            run_code(code)

    def test_function_access_01(self):
        ns = run_code("""
            def func[A, B](a: dict[A, B]):
                ...
            """
        )
        func = ns["func"]
        A, B = func.__type_params__
        self.assertEqual(func.__annotations__["a"], dict[A, B])

    def test_function_access_02(self):
        code = """
            def func[A](a = list[A]()):
                ...
            """

        with self.assertRaisesRegex(NameError, "name 'A' is not defined"):
            run_code(code)

    def test_function_access_03(self):
        code = """
            def my_decorator(a):
                ...
            @my_decorator(A)
            def func[A]():
                ...
            """

        with self.assertRaisesRegex(NameError, "name 'A' is not defined"):
            run_code(code)

    def test_method_access_01(self):
        ns = run_code("""
            class ClassA:
                x = int
                def func[T](self, a: x, b: T):
                    ...
            """
        )
        cls = ns["ClassA"]
        self.assertIs(cls.func.__annotations__["a"], int)
        T, = cls.func.__type_params__
        self.assertIs(cls.func.__annotations__["b"], T)

    def test_nested_access_01(self):
        ns = run_code("""
            class ClassA[A]:
                def funcB[B](self):
                    class ClassC[C]:
                        def funcD[D](self):
                            return lambda: (A, B, C, D)
                    return ClassC
            """
        )
        cls = ns["ClassA"]
        A, = cls.__type_params__
        B, = cls.funcB.__type_params__
        classC = cls().funcB()
        C, = classC.__type_params__
        D, = classC.funcD.__type_params__
        self.assertEqual(classC().funcD()(), (A, B, C, D))

    def test_out_of_scope_01(self):
        code = """
            class ClassA[T]: ...
            x = T
            """

        with self.assertRaisesRegex(NameError, "name 'T' is not defined"):
            run_code(code)

    def test_out_of_scope_02(self):
        code = """
            class ClassA[A]:
                def funcB[B](self): ...

                x = B
            """

        with self.assertRaisesRegex(NameError, "name 'B' is not defined"):
            run_code(code)

    def test_class_scope_interaction_01(self):
        ns = run_code("""
            class C:
                x = 1
                def method[T](self, arg: x): pass
        """)
        cls = ns["C"]
        self.assertEqual(cls.method.__annotations__["arg"], 1)

    def test_class_scope_interaction_02(self):
        ns = run_code("""
            class C:
                class Base: pass
                class Child[T](Base): pass
        """)
        cls = ns["C"]
        self.assertEqual(cls.Child.__bases__, (cls.Base, Generic))
        T, = cls.Child.__type_params__
        self.assertEqual(types.get_original_bases(cls.Child), (cls.Base, Generic[T]))

    def test_class_deref(self):
        ns = run_code("""
            class C[T]:
                T = "class"
                type Alias = T
        """)
        cls = ns["C"]
        self.assertEqual(cls.Alias.__value__, "class")

    def test_shadowing_nonlocal(self):
        ns = run_code("""
            def outer[T]():
                T = "outer"
                def inner():
                    nonlocal T
                    T = "inner"
                    return T
                return lambda: T, inner
        """)
        outer = ns["outer"]
        T, = outer.__type_params__
        self.assertEqual(T.__name__, "T")
        getter, inner = outer()
        self.assertEqual(getter(), "outer")
        self.assertEqual(inner(), "inner")
        self.assertEqual(getter(), "inner")

    def test_reference_previous_typevar(self):
        def func[S, T: Sequence[S]]():
            pass

        S, T = func.__type_params__
        self.assertEqual(T.__bound__, Sequence[S])

    def test_super(self):
        class Base:
            def meth(self):
                return "base"

        class Child(Base):
            # Having int in the annotation ensures the class gets cells for both
            # __class__ and __classdict__
            def meth[T](self, arg: int) -> T:
                return super().meth() + "child"

        c = Child()
        self.assertEqual(c.meth(1), "basechild")

    def test_type_alias_containing_lambda(self):
        type Alias[T] = lambda: T
        T, = Alias.__type_params__
        self.assertIs(Alias.__value__(), T)

    def test_class_base_containing_lambda(self):
        # Test that scopes nested inside hidden functions work correctly
        outer_var = "outer"
        class Base[T]: ...
        class Child[T](Base[lambda: (int, outer_var, T)]): ...
        base, _ = types.get_original_bases(Child)
        func, = get_args(base)
        T, = Child.__type_params__
        self.assertEqual(func(), (int, "outer", T))

    def test_comprehension_01(self):
        type Alias[T: ([T for T in (T, [1])[1]], T)] = [T for T in T.__name__]
        self.assertEqual(Alias.__value__, ["T"])
        T, = Alias.__type_params__
        self.assertEqual(T.__constraints__, ([1], T))

    def test_comprehension_02(self):
        type Alias[T: [lambda: T for T in (T, [1])[1]]] = [lambda: T for T in T.__name__]
        func, = Alias.__value__
        self.assertEqual(func(), "T")
        T, = Alias.__type_params__
        func, = T.__bound__
        self.assertEqual(func(), 1)


def global_generic_func[T]():
    pass

class GlobalGenericClass[T]:
    pass


class TypeParamsLazyEvaluationTest(unittest.TestCase):
    def test_qualname(self):
        class Foo[T]:
            pass

        def func[T]():
            pass

        self.assertEqual(Foo.__qualname__, "TypeParamsLazyEvaluationTest.test_qualname.<locals>.Foo")
        self.assertEqual(func.__qualname__, "TypeParamsLazyEvaluationTest.test_qualname.<locals>.func")
        self.assertEqual(global_generic_func.__qualname__, "global_generic_func")
        self.assertEqual(GlobalGenericClass.__qualname__, "GlobalGenericClass")

    def test_recursive_class(self):
        class Foo[T: Foo, U: (Foo, Foo)]:
            pass

        type_params = Foo.__type_params__
        self.assertEqual(len(type_params), 2)
        self.assertEqual(type_params[0].__name__, "T")
        self.assertIs(type_params[0].__bound__, Foo)
        self.assertEqual(type_params[0].__constraints__, ())

        self.assertEqual(type_params[1].__name__, "U")
        self.assertIs(type_params[1].__bound__, None)
        self.assertEqual(type_params[1].__constraints__, (Foo, Foo))

    def test_evaluation_error(self):
        class Foo[T: Undefined, U: (Undefined,)]:
            pass

        type_params = Foo.__type_params__
        with self.assertRaises(NameError):
            type_params[0].__bound__
        self.assertEqual(type_params[0].__constraints__, ())
        self.assertIs(type_params[1].__bound__, None)
        with self.assertRaises(NameError):
            type_params[1].__constraints__

        Undefined = "defined"
        self.assertEqual(type_params[0].__bound__, "defined")
        self.assertEqual(type_params[0].__constraints__, ())

        self.assertIs(type_params[1].__bound__, None)
        self.assertEqual(type_params[1].__constraints__, ("defined",))


class TypeParamsClassScopeTest(unittest.TestCase):
    def test_alias(self):
        class X:
            T = int
            type U = T
        self.assertIs(X.U.__value__, int)

        ns = run_code("""
            glb = "global"
            class X:
                cls = "class"
                type U = (glb, cls)
        """)
        cls = ns["X"]
        self.assertEqual(cls.U.__value__, ("global", "class"))

    def test_bound(self):
        class X:
            T = int
            def foo[U: T](self): ...
        self.assertIs(X.foo.__type_params__[0].__bound__, int)

        ns = run_code("""
            glb = "global"
            class X:
                cls = "class"
                def foo[T: glb, U: cls](self): ...
        """)
        cls = ns["X"]
        T, U = cls.foo.__type_params__
        self.assertEqual(T.__bound__, "global")
        self.assertEqual(U.__bound__, "class")

    def test_modified_later(self):
        class X:
            T = int
            def foo[U: T](self): ...
            type Alias = T
        X.T = float
        self.assertIs(X.foo.__type_params__[0].__bound__, float)
        self.assertIs(X.Alias.__value__, float)

    def test_binding_uses_global(self):
        ns = run_code("""
            x = "global"
            def outer():
                x = "nonlocal"
                class Cls:
                    type Alias = x
                    val = Alias.__value__
                    def meth[T: x](self, arg: x): ...
                    bound = meth.__type_params__[0].__bound__
                    annotation = meth.__annotations__["arg"]
                    x = "class"
                return Cls
        """)
        cls = ns["outer"]()
        self.assertEqual(cls.val, "global")
        self.assertEqual(cls.bound, "global")
        self.assertEqual(cls.annotation, "global")

    def test_no_binding_uses_nonlocal(self):
        ns = run_code("""
            x = "global"
            def outer():
                x = "nonlocal"
                class Cls:
                    type Alias = x
                    val = Alias.__value__
                    def meth[T: x](self, arg: x): ...
                    bound = meth.__type_params__[0].__bound__
                return Cls
        """)
        cls = ns["outer"]()
        self.assertEqual(cls.val, "nonlocal")
        self.assertEqual(cls.bound, "nonlocal")
        self.assertEqual(cls.meth.__annotations__["arg"], "nonlocal")

    def test_explicit_global(self):
        ns = run_code("""
            x = "global"
            def outer():
                x = "nonlocal"
                class Cls:
                    global x
                    type Alias = x
                Cls.x = "class"
                return Cls
        """)
        cls = ns["outer"]()
        self.assertEqual(cls.Alias.__value__, "global")

    def test_explicit_global_with_no_static_bound(self):
        ns = run_code("""
            def outer():
                class Cls:
                    global x
                    type Alias = x
                Cls.x = "class"
                return Cls
        """)
        ns["x"] = "global"
        cls = ns["outer"]()
        self.assertEqual(cls.Alias.__value__, "global")

    def test_explicit_global_with_assignment(self):
        ns = run_code("""
            x = "global"
            def outer():
                x = "nonlocal"
                class Cls:
                    global x
                    type Alias = x
                    x = "global from class"
                Cls.x = "class"
                return Cls
        """)
        cls = ns["outer"]()
        self.assertEqual(cls.Alias.__value__, "global from class")

    def test_explicit_nonlocal(self):
        ns = run_code("""
            x = "global"
            def outer():
                x = "nonlocal"
                class Cls:
                    nonlocal x
                    type Alias = x
                    x = "class"
                return Cls
        """)
        cls = ns["outer"]()
        self.assertEqual(cls.Alias.__value__, "class")


class TypeParamsManglingTest(unittest.TestCase):
    def test_mangling(self):
        class Foo[__T]:
            param = __T
            def meth[__U](self, arg: __T, arg2: __U):
                return (__T, __U)
            type Alias[__V] = (__T, __V)

        T = Foo.__type_params__[0]
        self.assertEqual(T.__name__, "__T")
        U = Foo.meth.__type_params__[0]
        self.assertEqual(U.__name__, "__U")
        V = Foo.Alias.__type_params__[0]
        self.assertEqual(V.__name__, "__V")

        anno = Foo.meth.__annotations__
        self.assertIs(anno["arg"], T)
        self.assertIs(anno["arg2"], U)
        self.assertEqual(Foo().meth(1, 2), (T, U))

        self.assertEqual(Foo.Alias.__value__, (T, V))


class TypeParamsComplexCallsTest(unittest.TestCase):
    def test_defaults(self):
        # Generic functions with both defaults and kwdefaults trigger a specific code path
        # in the compiler.
        def func[T](a: T = "a", *, b: T = "b"):
            return (a, b)

        T, = func.__type_params__
        self.assertIs(func.__annotations__["a"], T)
        self.assertIs(func.__annotations__["b"], T)
        self.assertEqual(func(), ("a", "b"))
        self.assertEqual(func(1), (1, "b"))
        self.assertEqual(func(b=2), ("a", 2))

    def test_complex_base(self):
        class Base:
            def __init_subclass__(cls, **kwargs) -> None:
                cls.kwargs = kwargs

        kwargs = {"c": 3}
        # Base classes with **kwargs trigger a different code path in the compiler.
        class C[T](Base, a=1, b=2, **kwargs):
            pass

        T, = C.__type_params__
        self.assertEqual(T.__name__, "T")
        self.assertEqual(C.kwargs, {"a": 1, "b": 2, "c": 3})

        bases = (Base,)
        class C2[T](*bases, **kwargs):
            pass

        T, = C2.__type_params__
        self.assertEqual(T.__name__, "T")
        self.assertEqual(C2.kwargs, {"c": 3})


class TypeParamsTraditionalTypeVarsTest(unittest.TestCase):
    def test_traditional_01(self):
        code = """
            from typing import Generic
            class ClassA[T](Generic[T]): ...
        """

        with self.assertRaisesRegex(TypeError, r"Cannot inherit from Generic\[...\] multiple times."):
            run_code(code)

    def test_traditional_02(self):
        from typing import TypeVar
        S = TypeVar("S")
        with self.assertRaises(TypeError):
            class ClassA[T](dict[T, S]): ...

    def test_traditional_03(self):
        # This does not generate a runtime error, but it should be
        # flagged as an error by type checkers.
        from typing import TypeVar
        S = TypeVar("S")
        def func[T](a: T, b: S) -> T | S:
            return a


class TypeParamsTypeVarTest(unittest.TestCase):
    def test_typevar_01(self):
        def func1[A: str, B: str | int, C: (int, str)]():
            return (A, B, C)

        a, b, c = func1()

        self.assertIsInstance(a, TypeVar)
        self.assertEqual(a.__bound__, str)
        self.assertTrue(a.__infer_variance__)
        self.assertFalse(a.__covariant__)
        self.assertFalse(a.__contravariant__)

        self.assertIsInstance(b, TypeVar)
        self.assertEqual(b.__bound__, str | int)
        self.assertTrue(b.__infer_variance__)
        self.assertFalse(b.__covariant__)
        self.assertFalse(b.__contravariant__)

        self.assertIsInstance(c, TypeVar)
        self.assertEqual(c.__bound__, None)
        self.assertEqual(c.__constraints__, (int, str))
        self.assertTrue(c.__infer_variance__)
        self.assertFalse(c.__covariant__)
        self.assertFalse(c.__contravariant__)

    def test_typevar_generator(self):
        def get_generator[A]():
            def generator1[C]():
                yield C

            def generator2[B]():
                yield A
                yield B
                yield from generator1()
            return generator2

        gen = get_generator()

        a, b, c = [x for x in gen()]

        self.assertIsInstance(a, TypeVar)
        self.assertEqual(a.__name__, "A")
        self.assertIsInstance(b, TypeVar)
        self.assertEqual(b.__name__, "B")
        self.assertIsInstance(c, TypeVar)
        self.assertEqual(c.__name__, "C")

    @requires_working_socket()
    def test_typevar_coroutine(self):
        def get_coroutine[A]():
            async def coroutine[B]():
                return (A, B)
            return coroutine

        co = get_coroutine()

        self.addCleanup(asyncio.set_event_loop_policy, None)
        a, b = asyncio.run(co())

        self.assertIsInstance(a, TypeVar)
        self.assertEqual(a.__name__, "A")
        self.assertIsInstance(b, TypeVar)
        self.assertEqual(b.__name__, "B")


class TypeParamsTypeVarTupleTest(unittest.TestCase):
    def test_typevartuple_01(self):
        code = """def func1[*A: str](): pass"""
        check_syntax_error(self, code, "cannot use bound with TypeVarTuple")
        code = """def func1[*A: (int, str)](): pass"""
        check_syntax_error(self, code, "cannot use constraints with TypeVarTuple")
        code = """class X[*A: str]: pass"""
        check_syntax_error(self, code, "cannot use bound with TypeVarTuple")
        code = """class X[*A: (int, str)]: pass"""
        check_syntax_error(self, code, "cannot use constraints with TypeVarTuple")
        code = """type X[*A: str] = int"""
        check_syntax_error(self, code, "cannot use bound with TypeVarTuple")
        code = """type X[*A: (int, str)] = int"""
        check_syntax_error(self, code, "cannot use constraints with TypeVarTuple")

    def test_typevartuple_02(self):
        def func1[*A]():
            return A

        a = func1()
        self.assertIsInstance(a, TypeVarTuple)


class TypeParamsTypeVarParamSpecTest(unittest.TestCase):
    def test_paramspec_01(self):
        code = """def func1[**A: str](): pass"""
        check_syntax_error(self, code, "cannot use bound with ParamSpec")
        code = """def func1[**A: (int, str)](): pass"""
        check_syntax_error(self, code, "cannot use constraints with ParamSpec")
        code = """class X[**A: str]: pass"""
        check_syntax_error(self, code, "cannot use bound with ParamSpec")
        code = """class X[**A: (int, str)]: pass"""
        check_syntax_error(self, code, "cannot use constraints with ParamSpec")
        code = """type X[**A: str] = int"""
        check_syntax_error(self, code, "cannot use bound with ParamSpec")
        code = """type X[**A: (int, str)] = int"""
        check_syntax_error(self, code, "cannot use constraints with ParamSpec")

    def test_paramspec_02(self):
        def func1[**A]():
            return A

        a = func1()
        self.assertIsInstance(a, ParamSpec)
        self.assertTrue(a.__infer_variance__)
        self.assertFalse(a.__covariant__)
        self.assertFalse(a.__contravariant__)


class TypeParamsTypeParamsDunder(unittest.TestCase):
    def test_typeparams_dunder_class_01(self):
        class Outer[A, B]:
            class Inner[C, D]:
                @staticmethod
                def get_typeparams():
                    return A, B, C, D

        a, b, c, d = Outer.Inner.get_typeparams()
        self.assertEqual(Outer.__type_params__, (a, b))
        self.assertEqual(Outer.Inner.__type_params__, (c, d))

        self.assertEqual(Outer.__parameters__, (a, b))
        self.assertEqual(Outer.Inner.__parameters__, (c, d))

    def test_typeparams_dunder_class_02(self):
        class ClassA:
            pass

        self.assertEqual(ClassA.__type_params__, ())

    def test_typeparams_dunder_class_03(self):
        code = """
            class ClassA[A]():
                pass
            ClassA.__type_params__ = ()
            params = ClassA.__type_params__
        """

        ns = run_code(code)
        self.assertEqual(ns["params"], ())

    def test_typeparams_dunder_function_01(self):
        def outer[A, B]():
            def inner[C, D]():
                return A, B, C, D

            return inner

        inner = outer()
        a, b, c, d = inner()
        self.assertEqual(outer.__type_params__, (a, b))
        self.assertEqual(inner.__type_params__, (c, d))

    def test_typeparams_dunder_function_02(self):
        def func1():
            pass

        self.assertEqual(func1.__type_params__, ())

    def test_typeparams_dunder_function_03(self):
        code = """
            def func[A]():
                pass
            func.__type_params__ = ()
        """

        ns = run_code(code)
        self.assertEqual(ns["func"].__type_params__, ())
