__doc__ = """Generic python utility functions."""

import hashlib
from typing import Any, Union, Protocol, runtime_checkable


@runtime_checkable
class SupportsHashing(Protocol):
    def update(b: bytes) -> None:
        pass
    


def hash_obj(obj: Any, ordered: bool = False, method: str = 'sha256') -> int:
    """
    Hashes the given python object. Recursive-object safe. Can pass pre-made hasher objects for specific args/kwargs
        on creation, and can return the hasher object upon completion instead of hexdigest() if needed.
    :param obj: the object to hash
    :param ordered: if True, then the order of ordered containers (lists, arrays, etc.) matters. Otherwise, order
        doesn't matter
    :param method: the method to use to hash. Can be a string name of a hash method in the hashlib library, or a hashing
        object with both an 'update()' and 'hexdigest()' method, similar to hash objects in the hashlib library.
    :return: string hex hash of the given object
    """
    # Check that method is correct
    if isinstance(method, str):

    return _hash_helper(obj, hasher=hasher, ordered=ordered, method=method, hashed_objects=set(), currently_hashing=set())


def _hash_helper(obj: Any, hasher: SupportsHashing, ordered: bool, method: str, hashed_objects: set[int], currently_hashing: set[int]) -> int:
    """
    Helper method for recursive hashing
    """

    if isinstance(obj, (int)):
        return obj.to_bytes()

    return 1


def check_string_input(input: str, strings: dict[str, Any], case_sensitive: bool = False):
    """
    Checks the given input matches the given requirements, and returns the specified values
    :param input: the string input to check
    :param strings: a dictionary
    """
    ...


class HashableDict(dict):
    """
    A dictionary that is inherently hashable, and can handle some 'non-hashable' keys, but is likely far slower than
        the default dict() and uses more memory.
    """

    def __init__(self, dict_input: Union[dict, None] = None, ordered: bool = False):
        """
        :param dict_input: can be build from a dictionary object, or left as None for an empty one
        :param ordered: if True, then objects that have an order must retain that same order to have the same hash,
            otherwise, order of array-like objects doesn't matter
        """
        if dict_input is not None:
            for k, v in dict_input.items():
                self[k] = v
        
        dict_input.clear
        
        self._object_dict = {}  # Contains the extended object keys
        self._ordered = ordered
        self._hash_method = 'sha256'
    
    def __setitem__(self, key: Any, newvalue: Any) -> None:
        # Set the item both in our _object_dict, and in the inherent dictionary
        key_hash = hash_obj(key, ordered=self._ordered, method=self._hash_method)
        self._object_dict[key_hash] = newvalue
        super().__setitem__(key_hash, newvalue)

    def __getitem__(self, key: Any) -> Any:
        return self._object_dict[hash_obj(key, ordered=self._ordered, method=self._hash_method)]