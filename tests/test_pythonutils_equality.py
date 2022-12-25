"""
Tests for the gstats_utils.pythonutils.equality file.

With regards to testing the `equality` function, I am guided by the following paradigm: test up to the recursive call.

I could theoretically test all combinations of objects, all pairs of sub-objects, sets of sub-sub-objects, and so on,
but that would take way too long both from an implementation and execution standpoint. Instead, I intend to test equality
of objects up to and including the first recursive call, and nothing more after that. For non-container objects, this
has no effect; they will be tested thoroughly. However for objects such as lists, tuples, arrays, etc., I will only
test until I am reasonably certain those objects are checked correctly up until their sub-elements are tested for
equality, and assume those will be tested correctly.
"""

from gstatsutils.pythonutils.equality import EqualityError, equal
from enum import Enum
from itertools import product
import numpy as np
import copy


class _TempEnum(Enum):
    A = 0
    B = 0
    C = 'thing'
    D = 'another_thing'
    E = ['a', 'list', 'of', 'thing']


class _TempHashableEQ:
    def __init__(self, int_val, str_val, list_val=None, list_val2=None):
        self.int_val = int_val
        self.str_val = str_val
        self.list_val = list_val
        self.list_val2 = list_val2
    
    def __hash__(self):
        return hash(self.int_val) + hash(self.str_val)
    
    def __eq__(self, other):
        return isinstance(other, _TempHashableEQ) and self.int_val == other.int_val and self.str_val == other.str_val \
            and equal(self, other, selector='list_val') and equal(self.list_val2, other.list_val2, strict_types=True)
    
    def __str__(self):
        return "_TempHashableEQ(%d, %s)" % (self.int_val, repr(self.str_val))
    
    def __repr__(self):
        return str(self)


_ARR_1 = np.array([['a', 'b', 'c'], range(10), 10, 'apples'], dtype=object)


def _check_equal(*args, expected_value=True, message=None, **kwargs):
    kwargs['raise_err'] = True

    try:
        val = equal(*args, **kwargs)
        if val is not False and val is not True:
            raise TypeError("Equality check returned a non-boolean result: %s" % val)
        if val != expected_value:
            raise ValueError("Equality check returned %s, expected %s" % (val, expected_value))
    except Exception as e:
        # Only re-raise if this is not an EqualityError, or if we were expecting a True value
        if not isinstance(e, EqualityError) or expected_value is not False:
            if message is not None:
                raise AssertionError(message)
            raise


def test_bool():
    """Tests booleans"""
    _check_equal(False, False)
    _check_equal(True, True)


def test_numeric():
    """Tests singular numeric values"""
    _check_equal(1, 1)
    _check_equal(1, 1.0)
    _check_equal(1, complex(1, 0))
    _check_equal(1, np.array([1], dtype=np.int8)[0])
    _check_equal(1, np.array([1], dtype=np.uint8)[0])
    _check_equal(1, np.array([1], dtype=np.int32)[0])
    _check_equal(1, np.array([1], dtype=np.uint32)[0])
    _check_equal(1, np.array([1], dtype=np.int64)[0])
    _check_equal(1, np.array([1], dtype=np.uint64)[0])
    _check_equal(1, np.array([1], dtype=np.float32)[0])
    _check_equal(1, np.array([1], dtype=np.float64)[0])
    _check_equal(1, np.array([1], dtype=np.complex64)[0])
    _check_equal(1, np.array([1], dtype=np.complex128)[0])
    _check_equal(np.array([-100], dtype=np.int32)[0], np.array([-100.0], dtype=np.float64)[0])
    _check_equal(np.array([0, 0, 0], dtype=np.int32)[1], complex(0, 0))
    
    _check_equal(1, 0, expected_value=False)
    _check_equal(np.array([1.0001], dtype=float)[0], np.array([1], dtype=int)[0], expected_value=False)
    _check_equal(np.array([1 + 2j], dtype=complex)[0], np.array([1], dtype=int)[0], expected_value=False)


def test_is():
    """Tests objects that should only be comparible using `is`"""
    _check_equal(None, None)
    _check_equal(Ellipsis, Ellipsis)
    _check_equal(NotImplemented, NotImplemented)
    
    _check_equal(_TempEnum.A, _TempEnum.A)
    _check_equal(_TempEnum.E, _TempEnum.E)
    _check_equal(_TempEnum.A, _TempEnum.B)  # This is true because of how Enum's work


def test_bytes_like():
    """Tests bytes like objects (string, bytes, bytearray, memoryview, etc.)"""
    # Strings
    _check_equal('a', 'a')
    _check_equal('', '')
    _check_equal('a' * 10_000, 'a' * 10_000)
    _check_equal('apples', ''.join(['a', 'p', 'p', 'l', 'e', 's']))

    _check_equal('apples', bytes('apples', 'utf-8'), expected_value=False)
    _check_equal('apples', bytes('apples', 'ascii'), expected_value=False)

    # Bytes and what not
    _check_equal(bytes('a', 'ascii'), bytes('a', 'utf-8'))
    _check_equal(bytes('a', 'ascii'), bytes(b'a'))
    _check_equal(bytes('', 'utf-8'), bytearray('', 'ascii'))
    _check_equal(memoryview(bytes('apples', 'ascii')), b'apples')


def test_types():
    """Tests types, what else did ya think it would do?"""
    _check_equal(int, int)
    _check_equal(float, float)
    _check_equal(type, type)
    _check_equal(_TempEnum, _TempEnum)


def test_range():
    """Wubbalubbadubdub boys and girls, this tests ranges (I'm a little drunk rn lol)"""
    _check_equal(range(0), range(0))
    _check_equal(range(1), range(0, 1))
    _check_equal(range(-3, 103, 7), range(-3, 103, 7))
    _check_equal(range(0), range(0, 0, 2))


def test_sequences():
    """Tests sequences that should all be interchangeable type-wise"""
    # Checking object types
    vals = [
        [],
        [1],
        [1, 2, 3, (4, 3, 5), np.array([]), [1, 2, 3], _ARR_1, tuple(), [], _TempHashableEQ(87, '')],
        np.arange(16).reshape(2, 2, 4),
    ]

    types = (list, tuple, lambda x: np.array(x, dtype=object))

    for t1, t2 in product(types, repeat=2):
        for v in vals:
            _check_equal(t1(v), t2(copy.deepcopy(v)), raise_err=True)
    
    # Checking numpy sequences
    _check_equal(np.array([1, 2, 3], dtype=np.int32), np.array([1, 2, 3], dtype=np.float64))
    _check_equal(np.array([1, 2, 3], dtype=np.complex128), np.array([1, 2, 3], dtype=np.float64))


def test_sets():
    "Whoopdiedoo, tests some sets"
    set_vals = [
        set(),
        set(range(10)),
        set([(1, 2, 3), (4, 5), 6, 7, 'apples']),
        set((_TempHashableEQ(10, 'aa'), _TempHashableEQ(1000, 'sddd'))),
    ]

    _check_equal(set(range(10)), set([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]))

    for s in set_vals:
        for t1, t2 in product([set, frozenset], repeat=2):
            for strict_types, unordered in product([True, False], [False]):
                exp = t1 is t2 or not strict_types
                _check_equal(t1(s), t2(copy.deepcopy(s)), strict_types=strict_types, unordered=unordered, expected_value=exp, 
                    message="used strict_types=%s with types '%s' and '%s' and thus expected value: %s"
                        % (strict_types, t1.__name__, t2.__name__, not strict_types))


def test_dictionaries():
    "Tests dictionaries"
    dict_vals = [
        {},
        {1: '1', '2': 2},
        {'x': [0, 3, 2], 'a': {(1, 2, 3): 'aaa', 'a': {}}},
    ]

    for d in dict_vals:
        for strict_types, unordered in product([True, False], [False]):
            _check_equal(d, copy.deepcopy(d), strict_types=strict_types, unordered=unordered)


def test_custom_eq():
    """Tests an object with a custom equality measure"""
    _check_equal(_TempHashableEQ(2, ''), 2, expected_value=False)
    _check_equal(_TempHashableEQ(2, ''), _TempHashableEQ(2, ''))
    _check_equal(_TempHashableEQ(2, ''), _TempHashableEQ(2, 'a'), expected_value=False)


def test_passing_kwargs_to_subcalls():
    """Tests how passing kwargs to subcalls of equal() works"""
    _check_equal(_TempHashableEQ(16, 'aa', [1, 2, 3]), _TempHashableEQ(16, 'aa', [1, 2, np.array([3])[0]]), strict_types=False)
    _check_equal(_TempHashableEQ(16, 'aa', [1, 2, 3]), _TempHashableEQ(16, 'aa', [1, 2, np.array([3])[0]]), strict_types=True, expected_value=False)
    _check_equal(_TempHashableEQ(16, 'aa', [1, 2, 3], [1, 2]), _TempHashableEQ(16, 'aa', [1, 2, np.array([3])[0]], [1, np.array([2])[0]]), strict_types=False, expected_value=False)


def test_not_equal():
    """Tests that all of these objects are definitively not equal to eachother"""
    olists = [
        [None, False, Ellipsis, NotImplemented, 0, '', bytes('', 'utf-8'), 1.0, True, complex(1, 1.0), 
        bytearray(b"apples"), 'a', 'bananas', 1.000001, _TempEnum.A, _TempEnum.E, _TempEnum.C, _TempEnum.D, 
        memoryview(bytes('things', 'ascii')), list, tuple, dict, int, float, complex, type, _TempEnum, Enum, 
        range(1, 2), range(-3, 2, 2), range(0), range(0, 1, 2), [], (1, 2, 3), np.array([1.2, 3.7, [], tuple()], dtype=object),
        _ARR_1, np.arange(16).reshape(2, 2, 4), set(), set(range(100)), set([_TempHashableEQ(10, 'aa'), _TempHashableEQ(-3, '')]),
        frozenset([8, 7, 6]), {}, {1: '1', '2': 2}, {'1': '1', '2': 2}, {'a': [1, 2, 3], 'b': {}}, {'a': [1, 2, 4], 'b': {}},
        _TempHashableEQ(222, "apples"), _TempHashableEQ(221, "apples"), _TempHashableEQ(0, ''), 
        _TempHashableEQ(16, 'aa', [1, 2, 3], [1, 2]), _TempHashableEQ(16, 'aa', [1, 2, np.array([3])[0]], [1, np.array([2])[0]])
        ]
    ]

    for li, olist in enumerate(olists):
        for i in range(len(olist)):
            for j in range(len(olist)):
                if i == j:
                    continue

                for strict_types, unordered in product([True, False], [False]):
                    _check_equal(olist[i], olist[j], strict_types=strict_types, unordered=unordered, expected_value=False,
                        message="Values were equal when they shouldn't be (list index=%d, strict_types=%s, unordered=%s):\n(%d): %s\n(%d): %s"
                            % (li, strict_types, unordered, i, repr(olist[i]), j, repr(olist[j])))
    