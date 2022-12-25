"""
Utility functions involving hashing.

Tested with the following types:
    - singleton objects (None, Ellipsis, NotImplemented, etc.)
    - int, float, complex, np.number
    - Enum
"""

import hashlib
import numpy as np
from enum import Enum
from .pytypes import SingletonObjects
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from typing import Any, Union


def hash_object(obj: 'Any', method: 'str' = 'sha256', ret_type: 'Union[type, str]' = str,
    strict_types: bool = False) -> 'Union[int, str, Any]':
    """Hashes the given object.

    NOTE: this will generally take into account the type of the given object (either explicitly or implicitly)

    Args:
        obj (Any): the object to hash
        method (Union[str, Hasher]): the string method to use to hash (a string name of a hasher object in hashlib)
        ret_type (Union[type, str]): the type to return the hash as. Can be a type (that will be called with the string
            .hexdigest() output), or a string for the type to use ('int', 'str', etc.)
        strict_types (bool): if True, then enforces objects to have the same types.
    
    Returns:
        Union[int, str, Any]: the hash of the given object
    """
    # Make sure `ret_type` is good
    if isinstance(ret_type, str):
        ret_type = ret_type.lower()
    elif not callable(ret_type):
        raise TypeError("`ret_type` should be a type or a str, not %s" % repr(type(ret_type).__name__))
    
    # Make sure `method` is good and get the method from hashlib if using
    if isinstance(method, str):
        if method not in hashlib.algorithms_available:
            raise ValueError("Unknown hasher method: %s" % repr(method))
        hasher = getattr(hashlib, method)()
    else:
        raise TypeError("`method` should be a str object, not %s" % repr(type(method).__name__))
    
    # Check for strict types
    if strict_types:
        hasher.update(("(%s) " % repr(type(obj).__name__)).encode('utf-8'))

    # Check types to hash
    # Built-in singleton objects
    if any(obj is x for x in SingletonObjects):
        hasher.update(("(%s)" % repr(type(obj).__name__)).encode('utf-8'))

    # Numeric types
    elif isinstance(obj, (int, float, complex, np.number)):
        # Make sure objects are converted to complex's if needed that way all values are equal no matter format
        hasher.update(("(Numeric) %s" % str(complex(obj))).encode('utf-8'))
    
    # Enum's
    elif isinstance(obj, Enum):
        hasher.update(("(Enum) %s %s" % (repr(type(obj).__name__), obj.name)).encode('utf-8'))

    # Get the hash, and convert into the expected type
    if ret_type is str or ret_type in ['str', 'string']:
        return hasher.hexdigest()
    elif ret_type is int or ret_type in ['int', 'integer']:
        return int(hasher.hexdigest(), 16)
    elif ret_type is bytes or ret_type in ['byte', 'bytes']:
        return hasher.digest()
    elif not isinstance(ret_type, str):
        return ret_type(hasher.hexdigest())
    else:
        raise ValueError("Unknown ret_type: %s" % repr(ret_type))