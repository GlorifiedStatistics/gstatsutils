"""
Contains methods involving memory in python.
"""

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from typing import Any, Set


def memory_usage(*objs: 'Any', _checked_objs: 'Set[int]' = None) -> 'int':
    """Returns the memory usage in bytes of all of the given objects

    

    

    Args:
        _checked_objs (Set[int], optional): set of object id's that have already been checked

    Returns:
        int: _description_
    """
    pass