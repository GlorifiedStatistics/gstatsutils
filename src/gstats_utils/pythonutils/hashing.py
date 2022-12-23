"""
Utility functions involving hashing
"""

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Protocol, runtime_checkable


    # Type aliases for type hinting
    HashableObject = 'Any'  # In case I want to add in a specific type hint for objects that can be hashed

    class SupportsHashing(Protocol):
        def update(b: bytes) -> None:
            pass

        def hexdigest() -> str:
            pass


def hash_object(obj: 'HashableObject', method: str = 'sha256') -> int:
    """
    Hashes the given python object. Recursive-object safe. Can pass pre-made hasher objects for specific args/kwargs
        on creation, and can return the hasher object upon completion instead of hexdigest() if needed.
    :param obj: the object to hash
    :param ordered: if True, then the order of ordered containers (lists, arrays, etc.) matters. Otherwise, order
        doesn't matter
    :param method: the method to use to hash. Can be a string name of a hash method in the hashlib library, or a hashing
        object with both an 'update()' and 'hexdigest()' method, similar to hash objects in the hashlib library.
        NOTE: the update() method should take in one argument: a bytes() object, and hexdigest() should take in no arguments
            and return a string
    :return: string hex hash of the given object
    """
    pass
