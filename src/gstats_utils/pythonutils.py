"""
Generic python utility functions.
"""

import hashlib
from typing import Any, Union


def hash_obj(obj: Any, ordered: bool = False, method: str = 'sha256') -> int:
    """
    Hashes the given python object. Recursive-object safe.
  +  :param obj: the object to hash
    :param ordered: if True, then the order of ordered containers (lists, arrays, etc.) matters. Otherwise, order
        doesn't matter
    :param method: the method to use to hash. Can be a string name of a hash method in the hashlib library, or a hashing
        object with both an 'update()' and 'hexdigest()' method, similar to hash objects in the hashlib library.
    :return: string hex hash of the given object
    """
    return _hash_helper(obj, ordered=ordered, method=method)


def _hash_helper(obj: Any, ordered: bool, method: str, hashed_objects: Union[set[int], None] = None, 
    currently_hashing: Union[set[int], None] = None) -> int:
    """
    Helper method for recursive hashing
    """
    # Keeping track of which objects we have hashed
    hashed_objects = set() if hashed_objects is None else hashed_objects
    currently_hashing = set() if currently_hashing is None else currently_hashing

    if isinstance(obj, (int)):
        return 1

    return 1
