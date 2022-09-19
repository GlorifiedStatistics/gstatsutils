"""
Utility functions involving hashing
"""

import hashlib
import copy
import re
from .equality import equal
from _collections_abc import dict_values
from typing import Any, Iterable, Iterator, NoReturn, Sequence, Union, Protocol, runtime_checkable, Optional
from typing_extensions import Self


@runtime_checkable
class SupportsHashing(Protocol):
    def update(b: bytes) -> None:
        pass

    def hexdigest() -> str:
        pass
    


def hash_object(obj: Any, ordered: bool = False, method: str = 'sha256') -> int:
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
    # Check that method is correct
    if isinstance(method, str):
        ...

    return _hash_helper(obj, hasher=hasher, ordered=ordered, method=method, hashed_objects=set(), currently_hashing=set())


def _hash_helper(obj: Any, hasher: SupportsHashing, ordered: bool, method: str, hashed_objects: set[int], currently_hashing: set[int]) -> int:
    """
    Helper method for recursive hashing
    """

    if isinstance(obj, (int)):
        return obj.to_bytes()

    return 1


# Special object/class to raise an error if there is no matching key for HashableDict.pop() method
class _RaiseErrorOnNoKey:
    pass
_RAISE_ERR_ON_NO_KEY = _RaiseErrorOnNoKey()

# Special object for get() to set a default value that could not exist in the dictionary anyways
_OBJECT_MISSING = object()

HashDictLike = Union[dict[Any, Any], Iterable[Sequence[Any, Any]]]
ConflictMethod = Union[str, int]


class HashableDict(dict):
    """
    A dictionary that is inherently hashable, and can handle some 'non-hashable' keys, but is likely far slower than
        the default dict() and uses more memory.
    
    Features:
        - Hashable
        - Can use 'any' object as keys (many commonly used objects have special hashing functions, otherwise attempts to call hash())
        - Order can matter or not matter for sequenced keys
        - Can initialize empty, with a dictionary, or with an iterable of (key, value) pairs
    
    Inner Workings:
    This is essentially just two dictionaries: one to keep track of key hashes (and map them to their associated key
        objects), and one to keep track of values (which are mapped to by those same key hashes). Since this object
        inherits from dict(), one of those dictionaries can exist inherently as self (this is the 'values' dictionary).
        The other dictinary (the 'keys' dictionary) is save in the self._key_hashes_to_keys dictionary. So:

        self: a dictionary that maps key_hashes -> values
        self._key_hashes_to_keys: a dictionary that maps key_hashes -> keys

        Where key_hashes is always a string hash of the keys and thus can be used as a normal dictionary's key
    
    There is ~some~ extra memory taken up due to using multiple dictionaries, but it should be relatively small since
        the key hashes are immutable strings and the same reference is used when inserting objects, thus only the
        reference is copied as a key in both dictionaries, not the entire string.
    """
    CONFLICT_RAISE_ERROR = 0
    CONFLICT_KEEP_LEFT = 1
    CONFLICT_KEEP_RIGHT = 2
    CONFLICT_KEEP_BOTH = 3
    CONFLICT_KEEP_SAME = 4

    def __init__(self, dict_input: Optional[HashDictLike] = None, ordered: bool = False) -> None:
        """
        :param dict_input: if not None, then a dictionary-like object or a sequence of length-2 sequences like:
            [(key1, value1), (key2, value2), ...] to build the dictionary from. Otherwise if None, this dictionary will
            be initialized empty.
            NOTE: this input will be deep-copied if deep_copy_input is True, otherwise only references will be copied
        :param ordered: if True, then objects that have an order must retain that same order to have the same hash,
            otherwise, order of array-like objects doesn't matter.
            NOTE: this does not apply to objects that are inherently unordered like sets and dictionary keys
        """
        if dict_input is not None:
            iterator = dict_input.items() if isinstance(dict_input, dict) else dict_input
            try:
                for t in iterator:
                    if len(t) != 2:
                        raise ValueError("Attempted to build HashableDict from interable of sequences of length 2, but found a sequence of length %d" % len(t))
                    self[t[0]] = t[1]
            except TypeError:
                raise TypeError("Cannot build HashableDict from input of type '%s', only None, dict, or iterable of length-2 sequences are allowed" % type(dict_input))
        
        self._key_hashes_to_keys = {}  # Contains the extended object keys
        self._ordered = ordered
        self._hash_method = 'sha256'
    
    def copy(self) -> Self:
        """
        Returns a copy of this dictionary and all the values in it
        :param deep: if True, then this will be a deep copy, otherwise keys and values will only be copied as references
        """
        return copy.deepcopy(self)
    
    def clear(self) -> None:
        self._key_hashes_to_keys.clear()
        super().clear()
    
    def keys(self) -> dict_values:
        return self._key_hashes_to_keys.values()
    
    def values(self) -> dict_values:
        return super().values()
    
    def items(self) -> zip[tuple[Any, Any]]:
        return zip(self._key_hashes_to_keys.values(), self.values())
    
    def _items_with_key_hashes(self) -> zip[tuple[Any, Any, str]]:
        return zip(self._key_hashes_to_keys.values(), self.values(), self._key_hashes_to_keys.keys())
    
    def _hash_key(self, key: Any) -> str:
        """
        Returns the string hash of the given key
        """
        return hash_object(key, ordered=self._ordered, method=self._hash_method)
    
    def _set_key_with_hash(self, key: Any, newvalue: Any, key_hash: str) -> None:
        """
        Sets the given key to the given value, using the given key_hash. This saves us from having to hash the key
            multiple times in some instances. We deep copy the key as it should be "immutable"
        """
        self._key_hashes_to_keys[key_hash] = copy.deepcopy(key)
        super().__setitem__(key_hash, newvalue)
    
    def _get_value_with_hash(self, key: Any, key_hash: str, default: Union[Any, _RaiseErrorOnNoKey] = _RAISE_ERR_ON_NO_KEY) -> Any:
        """
        Gets the value with the given key_hash. This saves us from having to hash the key multiple times in some instances.
            Need the key in case we raise an error.
        :param key: the key
        :param key_hash: the key hash
        :param default: if a value is passed to default, then this value will be returned if the key does not exist. 
            Otherwise if nothing is passed and the key does not exist, then a KeyError will be raised
        """
        try:
            return self._key_hashes_to_keys[key_hash]
        except KeyError:
            if default is _RAISE_ERR_ON_NO_KEY:
                self._raise_key_error(key)
            return default
    
    def _del_with_hash(self, key: Any, key_hash: str, raise_err: bool = True) -> None:
        """
        Deletes the key/value with the given key_hash. This saves us from having to hash the key multiple times in some 
            instances. Need the key in case we raise an error.
        :param key: the key
        :param key_hash: the key hash
        :param raise_err: if True, will raise an error if the key does not exist. Otherwise no error will be raised
            and nothing will be deleted if the key does not exist in this dictionary
        """
        try:
            del self._key_hashes_to_keys[key_hash]
            super().__delitem__(key_hash)
        except KeyError:
            if raise_err:
                self._raise_key_error(key)
    
    def _contains_key_hash(self, key_hash: str) -> bool:
        """
        Returns true if this dictionary contains the given key_hash, false otherwise
        """
        return key_hash in self._key_hashes_to_keys
    
    def _create_dict_with_same_kwargs(self, __other: Optional[HashDictLike] = None) -> Self:
        """
        Returns a new dictionary with the same kwargs this dictionary was given. Optionally can pass __other HashDictLike
            to fill this new dictionary with those values, otherwise will initialize empty.
        """
        return HashableDict(__other, ordered=self.ordered)

    def __setitem__(self, key: Any, newvalue: Any) -> None:
        """
        We deep copy the key as it should be "immutable"
        """
        self._set_key_with_hash(key, newvalue, self._hash_key(key))

    def __getitem__(self, key: Any) -> Any:
        return self._get_value_with_hash(key, self._hash_key(key))
    
    def __delitem__(self, key: Any) -> None:
        self._del_with_hash(self._hash_key(key))
    
    def __contains__(self, key: Any) -> bool:
        return self._contains_key_hash(self._hash_key(key))
    
    def __len__(self) -> int:
        return len(self._key_hashes_to_keys)
    
    @classmethod
    def fromkeys(cls, keys: Iterable[Any], value: Optional[Any] = None, ordered: bool = False) -> Self:
        """
        Generates a new HashableDict from the given list of key objects. A value can optionally be passed as well which
            will be used for each key (otherwise, values will be None).
        :param keys: an iterable of key objects to use
        :param value: if not None, then a single object to use as a value for all the keys. Otherwise if None, then all
            keys will have None as their value
        :param ordered: whether or not this HashableDict should be ordered
        """
        try:
            dict_input = [(k, value) for k in keys]
        except TypeError:
            raise TypeError("Could not iterate through non-iterable type '%s' to generate keys." % type(keys))
        
        return HashableDict(dict_input=dict_input, ordered=ordered)
    
    def get(self, key: Any, default: Union[Any, _RaiseErrorOnNoKey] = _RAISE_ERR_ON_NO_KEY) -> Any:
        """
        Attempts to get the value associated with the given key. If that key does not exist, then an error is raised 
            (unless default is passed, then that value will be returned)
        :param key: the key to get the value of
        :param default: if a value is passed to default, then this value will be returned if the key does not exist. 
            Otherwise if nothing is passed and the key does not exist, then a KeyError will be raised
        """
        try:
            return self[key]
        except KeyError:
            if default is _RAISE_ERR_ON_NO_KEY:
                self._raise_key_error(key)
            return default
    
    def pop(self, key: Any, default: Union[Any, _RaiseErrorOnNoKey] = _RAISE_ERR_ON_NO_KEY) -> Any:
        """
        Attempts to get the value associated with the given key, and subsequently delete it from this dictionary. If
            that key does not exist, then an error is raised (unless default is passed, then that value will be returned)
        :param key: the key to pop
        :param default: if a value is passed to default, then this value will be returned if the key does not exist (and 
            nothing will be popped/deleted). Otherwise if nothing is passed and the key does not exist, then a KeyError 
            will be raised
        """
        try:
            key_hash = self._hash_key(key)
            ret = self._get_value_with_hash(key, key_hash)
            self._del_with_hash(key, key_hash)
            return ret
        except KeyError:
            if default is _RAISE_ERR_ON_NO_KEY:
                self._raise_key_error(key)
            return default
    
    def __iter__(self) -> Iterator[Any]:
        return iter(self.keys())
    
    def __reversed__(self) -> Iterator[Any]:
        return reversed(self.keys())
    
    def __or__(self, __value: HashDictLike) -> Self:
        """
        Returns the union of this dictionary with another. Returns a copy. If there are any conflicts, then
            the key in the right-side dictionary (IE: __value) will be kept (much like dict.update()).
        """
        return self.union(__value, inplace=False, conflict_method='keep_right')
    
    def __ior__(self, __value: HashDictLike) -> Self:
        """
        Returns the in-place union of this dictionary with another. Modifies in-place. If there are any 
            conflicts, then the key in the right-side dictionary (IE: __value) will be kept (much like dict.update()).
        """
        return self.union(__value, inplace=True, conflict_method='keep_right')
    
    def __ror__(self, __value: HashDictLike) -> Self:
        """
        Returns the union of this dictionary with another, reversed (if there are any conflicts, then the key in the
            left-side dictionary (IE: self) will be kept instead of the right-side one). Returns a copy.
        """
        return self.union(__value, inplace=False, conflict_method='keep_left')

    def __add__(self, __value: HashDictLike) -> Self:
        """
        Returns the union of this dictionary with another. Returns a copy. If there are any conflicts, then
            both keys will be kept in a tuple of (left_side, right_side).
        """
        return self.union(__value, inplace=False, conflict_method='keep_both')
    
    def __iadd__(self, __value: HashDictLike) -> Self:
        """
        Returns the in-place union of this dictionary with another. Modifies in-place. If there are any 
            conflicts, then both keys will be kept in a tuple of (left_side, right_side).
        """
        return self.union(__value, inplace=True, conflict_method='keep_both')
    
    def __radd__(self, __value: HashDictLike) -> Self:
        """
        Returns the union of this dictionary with another, reversed. Returns a copy. If there are any conflicts, then
            both keys will be kept in a tuple of (left_side, right_side).
        """
        return self.union(__value, inplace=False, conflict_method='keep_both')
    
    def __inv__(self) -> Self:
        """
        Alias for __invert__(). Flips the keys and values of this dictionary. Returns a copy.
        """
        return self.__invert__()
    
    def __invert__(self) -> Self:
        """
        Flips the keys and values of this dictionary. Returns a copy.
        """
        return self.flip(inplace=False)
    
    def __and__(self, __value: HashDictLike) -> Self:
        """
        Returns the intersection of this dictionary with another. Will keep both values as the tuple (left_value, right_value).
            Returns a copy.
        """
        return self.intersection(__value, inplace=False, keep_value_method='keep_both')
    
    def __iand__(self, __value: HashDictLike) -> Self:
        """
        Returns the intersection of this dictionary with another. Will keep both values as the tuple (left_value, right_value). 
            Modifies in-place.
        """
        return self.intersection(__value, inplace=True, keep_value_method='keep_both')
    
    def __rand__(self, __value: HashDictLike) -> Self:
        """
        Returns the intersection of this dictionary with another, reversed. Will keep both values as the tuple 
            (left_value, right_value). Returns a copy.
        """
        return self.intersection(__value, inplace=False, keep_value_method='keep_both')
    
    def __sub__(self, __value: HashDictLike) -> Self:
        """
        Returns the set difference of this set and another. (IE: all keys/values that are in this dictionary (left-side 
            dictionary) and are not in the other dictionary (right-side one)). Returns a copy.
        """
        return self.difference(__value, inplace=False)
    
    def __isub__(self, __value: HashDictLike) -> Self:
        """
        Returns the set difference of this set and another. (IE: all keys/values that are in this dictionary (left-side 
            dictionary) and are not in the other dictionary (right-side one)). Modifies in-place.
        """
        return self.difference(__value, inplace=True)
    
    def __rsub__(self, __value: HashDictLike) -> Self:
        """
        Returns the set difference of another set and this one. (IE: all keys/values that are in THE OTHER dictionary 
            (right-side dictionary) and are NOT IN THIS dictionary (left-side one)). Returns a copy.
        """
        return self.difference(__value, inplace=False, flip_operands=True)
    
    def __truediv__(self, __value: HashDictLike) -> Self:
        """
        Returns the set difference of this set and another. (IE: all keys/values that are in this dictionary (left-side 
            dictionary) and are not in the other dictionary (right-side one)). Returns a copy.
        """
        return self.difference(__value, inplace=False)
    
    def __itruediv__(self, __value: HashDictLike) -> Self:
        """
        Returns the set difference of this set and another. (IE: all keys/values that are in this dictionary (left-side 
            dictionary) and are not in the other dictionary (right-side one)). Modifies in-place.
        """
        return self.difference(__value, inplace=True)
    
    def __rtruediv__(self, __value: HashDictLike) -> Self:
        """
        Returns the set difference of another set and this one. (IE: all keys/values that are in THE OTHER dictionary 
            (right-side dictionary) and are NOT IN THIS dictionary (left-side one)). Returns a copy.
        """
        return self.difference(__value, inplace=False, flip_operands=True)
    
    def flip(self, inplace: bool = False) -> Self:
        """
        Flips the keys and values of this dictionary. (IE: essentially returns {v: k for k, v in self.items()})
        :param inplace: if True, will modify this dict to flip keys. Otherwise will return a copy.
        """
        other = self._create_dict_with_same_kwargs([(v, k) for k, v in self.items()])
        if inplace:
            self.clear()
            self.update(other)
            return self
        return other
    
    def invert(self, inplace: bool = False) -> Self:
        """
        Alias for flip(). Flips the keys and values of this dictionary.
        :param inplace: if True, will modify this dict to flip keys. Otherwise will return a copy.
        """
        return self.flip(inplace=inplace)
    
    def union(self, __other: HashDictLike, inplace: bool = False, conflict_method: ConflictMethod = 'keep_right') -> Self:
        """
        Returns the union of this dictionary with another
        :param __other: the other dictionary
        :param inplace: if True, then this dictionary object will be modified inplace, otherwise a copy will be created,
            modified, and returned
        :param conflict_method: a string method for how to resolve conflicts. Possible values are:
            - 'raise', 'err', 'raise_error', ... : raise an error on a key conflict (will be KeyError)
                NOTE: will not raise an error if the two objects are equal. Will call gstats_utils.pythonutils.equal() 
                    to determine equality
            - 'left', 'keep_left', 'self', ... : keep the value in this object, reject the value in other
            - 'right', 'keep_right', 'other', ... : keep the value in the other (right) object, reject the value in this
                object (same functionality as self.update())
            - 'both', 'keep_both', 'tuple' : keep both values as a tuple of (this_value, other_value)
            Could also be the associated HashableDict.[CONFLICT_METHOD] constant (EG: HashableDict.CONFLICT_RAISE_ERROR)
        """
        __other: HashableDict = self._ensure_compatible_kwargs(__other)
        clean_cm = _get_hashable_dict_conflict_method(conflict_method, dont_allow='same')
        
        # Copy this dictionary if needed, then add all the keys/values of __other
        working_dict = self if inplace else self.copy()
        for k, v, key_hash in __other._items_with_key_hashes():

            # This saves us from having to hash the key multiple times
            self_v = self._get_value_with_hash(k, key_hash, default=_OBJECT_MISSING)
            
            if clean_cm != HashableDict.CONFLICT_KEEP_RIGHT and self_v is not _OBJECT_MISSING:
                if clean_cm == HashableDict.CONFLICT_KEEP_LEFT:
                    continue
                elif clean_cm == HashableDict.CONFLICT_KEEP_BOTH:
                    working_dict._set_key_with_hash(k, (self_v, v), key_hash)
                elif clean_cm == HashableDict.CONFLICT_RAISE_ERROR:
                    if equal(self_v, v):  # Don't raise error if the values are equal
                        continue
                    self._raise_key_error(k, err_message="Key exists in both left and right HashableDict's on union: %s")
                else:
                    raise NotImplementedError

            # If self_v is _OBJECT_MISSING, then the given key 'k' in __other does not exist in this dictionary and we. Or,
            #   if clean_cm is HashableDict.CONFLICT_KEEP_RIGHT
            else:
                working_dict._set_key_with_hash(k, v, key_hash)

        return working_dict
    
    def update(self, __other: HashDictLike) -> Self:
        """
        In-place (IE: not copied) updating with the __other HashableDict
        """
        return self.union(__other, inplace=True, conflict_method='keep_right')
    
    def intersection(self, __other: HashDictLike, inplace: bool = False, keep_value_method: ConflictMethod = 'keep_right') -> Self:
        """
        Returns the intersection of this dictionary with another (IE: a HashableDict with only the keys/values that
            are in both dictionaries).
        :param __other: the other object
        :param inplace: if False, will return a copy of the kept keys/values. Otherwise will modify this dictionary
            in-place (IE: will delete the keys/values that are in this dictionary but not in __other)
        :param keep_value_method: the method to use to determine how to keep the values that are in both dictionaries.
            Possible values are:
                - 'left', 'keep_left', 'self', ... : keep the value in this object, reject the value in other
                - 'right', 'keep_right', 'other', ... : keep the value in the other (right) object, reject the value in 
                    this object
                - 'both', 'keep_both', 'tuple' : keep both values as a tuple of (this_value, other_value)
                - 'same', 'keep_same': keep only the values that are the same in both dictionaries. Will call 
                    gstats_utils.pythonutils.equal() to determine equality
            Could also be the associated HashableDict.[CONFLICT_METHOD] constant (EG: HashableDict.CONFLICT_RAISE_ERROR)
        """
        __other: HashableDict = self._ensure_compatible_kwargs(__other)
        clean_cm = _get_hashable_dict_conflict_method(keep_value_method, dont_allow='raise')
        
        working_dict = self._create_dict_with_same_kwargs()
        for k, v, key_hash in self._items_with_key_hashes():
            other_v = __other._get_value_with_hash(k, key_hash, default=_OBJECT_MISSING)

            if other_v is not _OBJECT_MISSING:
                if clean_cm == HashableDict.CONFLICT_KEEP_LEFT:
                    new_v = v
                elif clean_cm == HashableDict.CONFLICT_KEEP_RIGHT:
                    new_v = other_v
                elif clean_cm == HashableDict.CONFLICT_KEEP_BOTH:
                    new_v = (v, other_v)
                elif clean_cm == HashableDict.CONFLICT_KEEP_SAME:
                    if not equal(v, other_v):
                        continue
                    new_v = v
                else:
                    raise NotImplementedError
                working_dict._set_key_with_hash(k, new_v, key_hash)
        
        if inplace:
            self.clear()
            self.update(working_dict)
            return self
        return working_dict
    
    def intersect(self, __other: HashDictLike, inplace: bool = False, keep_value_method: ConflictMethod = 'keep_right') -> Self:
        """
        Alias for intersection()
        """
        return self.intersection(__other, inplace=inplace, keep_value_method=keep_value_method)
    
    def difference(self, __other: HashDictLike, inplace: bool = False, flip_operands: bool = False) -> Self:
        """
        Returns the set difference between this set and another. (IE: all keys/values that are in this dictionary [the
            left-side one], but not in the other [the right-side one])
        :param __other: the other object
        :param inplace: if False, will return a copy of the kept keys/values. Otherwise will modify this dictionary
            in-place (IE: will delete the keys/values that are in this dictionary but not in __other)
        :param flip_operands: if True, will flip the operands. IE: will instead return all keys/values that are in
            THE OTHER dictionary (the right-side one), but not in this one (the left-side one).
            NOTE: if you flip_operands, but __other is not a HashableDict, then a copy will be returned anyways, no
                matter the inplace value.
        """
        __other: HashableDict = self._ensure_compatible_kwargs(__other)
        
        if flip_operands:
            return __other.difference(self, inplace=inplace, flip_operands=False)
        
        if inplace:
            ret = self
            for k, _, key_hash in __other._items_with_key_hashes():
                self._del_with_hash(k, key_hash, raise_err=False)
        else:
            ret = self._create_dict_with_same_kwargs()
            for k, v, key_hash in self._items_with_key_hashes():
                if not __other._contains_key_hash(k, key_hash):
                    ret._set_key_with_hash(k, v, key_hash)

        return ret
    
    def diff(self, __other: HashDictLike, inplace: bool = False, flip_operands: bool = False) -> Self:
        """
        Alias for difference()
        """
        return self.difference(__other, inplace=inplace, flip_operands=flip_operands)
    
    def symmetric_difference(self, __other: HashDictLike, inplace: bool = False) -> Self:
        """
        Returns the symmetric difference of this dictionary and another (IE: all of the keys/values that only exist
            in one of the two dictionaries, not both). Essentially the xor operation applied to dictionaries.
        :param __other: the other object
        :param inplace: if False, will return a copy of the kept keys/values. Otherwise will modify this dictionary
            in-place (IE: will delete the keys/values that are in this dictionary but not in __other)
        """
        __other: HashableDict = self._ensure_compatible_kwargs(__other)

        working_dict = self._create_dict_with_same_kwargs()
        for k, v, key_hash in self._items_with_key_hashes():
            if not __other._contains_key_hash(key_hash):
                working_dict._set_key_with_hash(k, v, key_hash)
        for k, v, key_hash in __other._items_with_key_hashes():
            if not self._contains_key_hash(key_hash):
                working_dict._set_key_with_hash(k, v, key_hash)
        
        if inplace:
            self.clear()
            self.update(working_dict)
            return self
        return working_dict
    
    def xor(self, __other: HashDictLike, inplace: bool = False) -> Self:
        """
        Alias for symmetric_difference()
        """
        return self.symmetric_difference(self, __other, inplace=inplace)

    def _raise_key_error(self, key: Any, err_message: Optional[str] = None) -> NoReturn:
        # Raise a KeyError with the string of the key, making sure the string isn't too large
        key_error_str = str(key)
        if len(key_error_str) > 200:
            key_error_str = key_error_str[:200]
        err_message = "%s" if err_message is None else err_message
        raise KeyError(err_message % repr(key_error_str))  # Do repr to convert to string that could be parsed nicely
    
    def _ensure_compatible_kwargs(self, __other: HashDictLike) -> Self:
        """
        Makes sure the the given __other object either is a HashableDict, or is turned into one, and that it has kwargs
            that allow for operations between it and this HashableDict
        """
        if not isinstance(__other, HashableDict):
            __other = self._create_dict_with_same_kwargs(__other)
        elif __other._ordered != self._ordered:
            raise ValueError("Cannot perform operations on dictionaries with different 'ordered' kwarg. "
                "Self: %s, other: %s" % (self._ordered, __other._ordered))
        
        return __other



# Get the conflict_method values and names
_CONFLICT_METHOD_DICT = {getattr(HashableDict, k): k for k in dir(HashableDict) if k.startswith('CONFLICT_')}
def _get_hashable_dict_conflict_method(conflict_method: ConflictMethod, dont_allow: Optional[Union[ConflictMethod, Sequence[ConflictMethod]]]=None) -> int:
    """
    Returns one of HashableDict.[CONFLICT_RAISE_ERROR, CONFLICT_KEEP_LEFT, CONFLICT_KEEP_RIGHT, CONFLICT_KEEP_BOTH]
        depending on the conflict_method input, and sanitizes
    :param conflict_method:
    :param dont_allow: a list of HashableDict.[CONFLICT METHODS] that are NOT allowed, and will raise an error
    """

    # Parse how to deal with key conflicts
    if isinstance(conflict_method, str):
        clean_cm = conflict_method.lower().strip()
        if re.fullmatch(r'(err(or)?|raise[ _-]?(err(or)?)?)', clean_cm) is not None:
            clean_cm = HashableDict.CONFLICT_RAISE_ERROR
        elif re.fullmatch(r'(keep[ -_]?)?(left|self)', clean_cm) is not None:
            clean_cm = HashableDict.CONFLICT_KEEP_LEFT
        elif re.fullmatch(r'(keep[ -_]?)?(right|other)', clean_cm) is not None:
            clean_cm = HashableDict.CONFLICT_KEEP_RIGHT
        elif re.fullmatch(r'(keep[ -_]?)?(both|tuple)', clean_cm) is not None:
            clean_cm = HashableDict.CONFLICT_KEEP_BOTH
        elif re.fullmatch(r'(keep[ -_]?)?(same)', clean_cm) is not None:
            clean_cm = HashableDict.CONFLICT_KEEP_SAME
        else:
            raise ValueError("Unknown conflict_method string: '%s'" % conflict_method)
    elif isinstance(conflict_method, int):
        if conflict_method not in _CONFLICT_METHOD_DICT:
            raise ValueError("Unknown conflict_method int with value: %d" % conflict_method)
        clean_cm = conflict_method
    else:
        raise TypeError("Conflict_method must be of type str or int, not '%s'" % type(conflict_method))
    
    # Check for dont_allow values
    dont_allow = [dont_allow] if isinstance(dont_allow, (int, str)) else [] if dont_allow is None else dont_allow
    dont_allow = [_get_hashable_dict_conflict_method(cm) for cm in dont_allow]
    if clean_cm in dont_allow:
        raise ValueError("Cannot use method %s for this function" % _CONFLICT_METHOD_DICT[clean_cm])

    return clean_cm
    