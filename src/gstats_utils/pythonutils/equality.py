"""
Utils for determining equality of objects
"""
from typing import Any


def equal(a: Any, b: Any) -> bool:
    """
    Determines whether a == b or not, generalizing for more objects and capabilities than default __eq__() method.
    Equal() is an equivalence relation, and thus:
        1. equal(a, a) is always True
        2. equal(a, b) -> equal(b, a)
        3. equal(a, b) and equal(b, c) -> equal(a, c)
    """
    pass


def all_equal(*objs: Any) -> bool:
    """
    Return True if all objects are equal to one another (using the equal() function), False otherwise
    """
    for i in range(len(objs) - 1):
        if not equal(objs[i], objs[i + 1]):
            return False
    return True
