"""
A better implementation of the python builtin dictionary with more features (but a bit slower).
"""

import copy
import re
from ..equality import equal, all_equal
from ..hashing import HashableObject, hash_object
from _collections_abc import dict_values
from enum import Enum, unique as enum_unique
from typing import Any, Iterable, Iterator, NoReturn, Sequence, Union, Optional, Callable
from typing_extensions import Self


# Type aliases for type hinting
BetterDictObject = HashableObject  # In case I want to add in a specific type hint for objects that can act as keys in BetterDict
BetterDictKeyValuePair = tuple[BetterDictObject, BetterDictObject]
BetterDictLike = Union['BetterDict', dict[BetterDictObject, BetterDictObject], Iterable[BetterDictKeyValuePair]]
ConflictMethod = Union['BetterDict.ConflictMethodsEnum', Callable[[Iterable[BetterDictObject]]], BetterDictObject]
_ConflictMethodInput = Union[str, int, ConflictMethod]


# Special object/class to raise an error if there is no matching key for BetterDict.pop() method
class _RaiseErrorOnNoKey:
    pass
_RAISE_ERR_ON_NO_KEY = _RaiseErrorOnNoKey()

# Special object for get() to set a default value that could not exist in the dictionary anyways
_OBJECT_MISSING = object()


class BetterDict(dict[BetterDictObject, BetterDictObject]):
    """
    A dictionary that is inherently hashable, and can handle some 'non-hashable' keys, but is likely far slower than
        the default dict() and uses more memory.
    
    Currently using type hints of BetterDictObjects for keys, as well as values due to the flip()/invert() operation. This
        is currently just an alias for Any, but that may change in the future. This inherets from dict instead of a
        plain MutableMapping just because I want isinstance(BetterDict(), dict) to be True.
    
    Features:
        - Hashable
        - Can use 'any' object as keys (many commonly used objects have special hashing functions, otherwise attempts to call hash())
        - Order can matter or not matter for sequenced keys
        - Can initialize empty, with a dictionary, or with an iterable of (key, value) pairs
    
    Inner Workings:
    This is essentially just two dictionaries: one to keep track of key hashes (and map them to their associated key
        objects), and one to keep track of values (which are mapped to by those same key hashes).
    
    There is ~some~ extra memory taken up due to using multiple dictionaries, but it should be relatively small since
        the key hashes are immutable strings and the same reference is used when inserting objects, thus only the
        reference is copied as a key in both dictionaries, not the entire string.
    """
    @enum_unique
    class ConflictMethodsEnum(Enum):
        RAISE_ERROR = r'(err(or)?|raise[ _-]?(err(or)?)?)'
        KEEP_LEFT = r'(keep[ -_]?)?(left|self)'
        KEEP_RIGHT = r'(keep[ -_]?)?(right|other)'
        KEEP_ALL = r'(keep[ -_]?)?(both|tuple|all)'
        KEEP_SAME = r'(keep[ -_]?)?(same)'

    def __init__(self, dict_input: Optional[BetterDictLike] = None) -> None:
        """
        :param dict_input: if not None, then a dictionary-like object or a sequence of length-2 sequences like:
            [(key1, value1), (key2, value2), ...] to build the dictionary from. Otherwise if None, this dictionary will
            be initialized empty.
            NOTE: this input will be deep-copied if deep_copy_input is True, otherwise only references will be copied
        """
        if dict_input is not None:
            iterator = dict_input.items() if isinstance(dict_input, dict) else dict_input
            try:
                for t in iterator:
                    if len(t) != 2:
                        raise ValueError("Attempted to build BetterDict from interable of sequences of length 2, but found a sequence of length %d" % len(t))
                    self[t[0]] = t[1]
            except TypeError:
                raise TypeError("Cannot build BetterDict from input of type '%s', only None, dict, or iterable of length-2 sequences are allowed" % type(dict_input))
        
        self._keys: dict[str, BetterDictObject] = {}
        self._values: dict[str, BetterDictObject] = {}
        self._hash_method = 'sha256'
    
    def copy(self) -> Self:
        """
        Returns a deep copy of this dictionary, including copying the keys and values
        """
        return copy.deepcopy(self)
    
    def get_subset(self, keys: Iterable[Any], default: Union[Any, _RaiseErrorOnNoKey] = _RAISE_ERR_ON_NO_KEY) -> BetterDictObject:
        """
        Returns a new dictionary built from this dictionary using the given keys.
        :param keys: an iterable of key objects
        :param default: if a value is passed to default, then this value will be returned if the key does not exist. 
            Otherwise if nothing is passed and the key does not exist, then a KeyError will be raised
        """
        ret = self.__class__()
        for key in keys:
            key_hash = self._hash_key(key)
            ret._set_key_with_hash(key, self._get_value_with_hash(key, key_hash, default=default), key_hash)
        return ret
    
    def to_dict(self) -> dict:
        """
        Attempts to convert this dictionary to plain dictionary. If it cannot be converted due to a key that normal
            python dictionaries cannot handle, then a TypeError will be raised.
        """
        try:
            return {key: value for key, value in self.items()}
        except TypeError as e:
            raise TypeError("Could not convert %s to dict() due to error: %s" % (self.__class__.__name__, e))
    
    def __dict__(self) -> dict:
        return self.to_dict()
    
    def clear(self) -> None:
        self._keys.clear()
        self._values.clear()
    
    def keys(self) -> dict_values:
        return self._keys.values()
    
    def values(self) -> dict_values:
        return self._values.values()
    
    def items(self) -> zip[tuple[BetterDictObject, BetterDictObject]]:
        return zip(self._keys.values(), self._values.values())
    
    def _items_with_key_hashes(self) -> zip[tuple[BetterDictObject, BetterDictObject, str]]:
        return zip(self._keys.values(), self._values.values(), self._keys.keys())
    
    def _hash_key(self, key: BetterDictObject) -> str:
        """
        Returns the string hash of the given key
        """
        return hash_object(key, method=self._hash_method)
    
    def _set_key_with_hash(self, key: BetterDictObject, newvalue: BetterDictObject, key_hash: str) -> None:
        """
        Sets the given key to the given value, using the given key_hash. This saves us from having to hash the key
            multiple times in some instances. We deep copy the key as it should be "immutable"
        """
        self._keys[key_hash] = copy.deepcopy(key)
        self._values[key_hash] = newvalue
    
    def _get_value_with_hash(self, key: BetterDictObject, key_hash: str, 
        default: Union[Any, _RaiseErrorOnNoKey] = _RAISE_ERR_ON_NO_KEY) -> BetterDictObject:
        """
        Gets the value with the given key_hash. This saves us from having to hash the key multiple times in some instances.
            Need the key in case we raise an error.
        :param key: the key
        :param key_hash: the key hash
        :param default: if a value is passed to default, then this value will be returned if the key does not exist. 
            Otherwise if nothing is passed and the key does not exist, then a KeyError will be raised
        """
        try:
            return self._values[key_hash]
        except KeyError:
            if default is _RAISE_ERR_ON_NO_KEY:
                self._raise_key_error(key)
            return default
    
    def _del_with_hash(self, key: BetterDictObject, key_hash: str, raise_err: bool = True) -> None:
        """
        Deletes the key/value with the given key_hash. This saves us from having to hash the key multiple times in some 
            instances. Need the key in case we raise an error.
        :param key: the key
        :param key_hash: the key hash
        :param raise_err: if True, will raise an error if the key does not exist. Otherwise no error will be raised
            and nothing will be deleted if the key does not exist in this dictionary
        """
        try:
            del self._keys[key_hash], self._values[key_hash]
        except KeyError:
            if raise_err:
                self._raise_key_error(key)
    
    def _del_known_key_hashes(self, key_hashes: Iterable[str]) -> None:
        """
        Deletes all key hashes from self, while knowing that they for sure exist in self
        """
        for key_hash in key_hashes:
            del self._keys[key_hash], self._values[key_hash]
    
    def _contains_key_hash(self, key_hash: str) -> bool:
        """
        Returns true if this dictionary contains the given key_hash, false otherwise
        """
        return key_hash in self._keys

    def __setitem__(self, key: BetterDictObject, newvalue: BetterDictObject) -> None:
        """
        We deep copy the key as it should be "immutable"
        """
        self._set_key_with_hash(key, newvalue, self._hash_key(key))

    def __getitem__(self, key: BetterDictObject) -> BetterDictObject:
        return self._get_value_with_hash(key, self._hash_key(key))
    
    def __delitem__(self, key: BetterDictObject) -> None:
        self._del_with_hash(self._hash_key(key))
    
    def __contains__(self, key: BetterDictObject) -> bool:
        return self._contains_key_hash(self._hash_key(key))
    
    def __len__(self) -> int:
        return len(self._keys)
    
    def get(self, key: BetterDictObject, default: Union[Any, _RaiseErrorOnNoKey] = _RAISE_ERR_ON_NO_KEY) -> Union[BetterDictObject, Any]:
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
    
    def pop(self, key: BetterDictObject, default: Union[Any, _RaiseErrorOnNoKey] = _RAISE_ERR_ON_NO_KEY) -> Union[BetterDictObject, Any]:
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
    
    def __iter__(self) -> Iterator[BetterDictObject]:
        return iter(self.keys())
    
    def __reversed__(self) -> Iterator[BetterDictObject]:
        return reversed(self.keys())
    
    def __or__(self, __value: BetterDictLike) -> Self:
        """
        Returns the union of this dictionary with another. Returns a copy. If there are any conflicts, then
            the key in the right-side dictionary (IE: __value) will be kept (much like dict.update()).
        """
        return self.union(__value, inplace=False, conflict_method='keep_right')
    
    def __ior__(self, __value: BetterDictLike) -> Self:
        """
        Returns the in-place union of this dictionary with another. Modifies in-place. If there are any 
            conflicts, then the key in the right-side dictionary (IE: __value) will be kept (much like dict.update()).
        """
        return self.union(__value, inplace=True, conflict_method='keep_right')
    
    def __ror__(self, __value: BetterDictLike) -> Self:
        """
        Returns the union of this dictionary with another, reversed (if there are any conflicts, then the key in the
            left-side dictionary (IE: self) will be kept instead of the right-side one). Returns a copy.
        """
        return self.union(__value, inplace=False, conflict_method='keep_left')

    def __add__(self, __value: BetterDictLike) -> Self:
        """
        Returns the union of this dictionary with another. Returns a copy. If there are any conflicts, then
            both keys will be kept in a tuple of (left_side, right_side).
        """
        return self.union(__value, inplace=False, conflict_method='keep_both')
    
    def __iadd__(self, __value: BetterDictLike) -> Self:
        """
        Returns the in-place union of this dictionary with another. Modifies in-place. If there are any 
            conflicts, then both keys will be kept in a tuple of (left_side, right_side).
        """
        return self.union(__value, inplace=True, conflict_method='keep_both')
    
    def __radd__(self, __value: BetterDictLike) -> Self:
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
    
    def __and__(self, __value: BetterDictLike) -> Self:
        """
        Returns the intersection of this dictionary with another. Will keep both values as the tuple (left_value, right_value).
            Returns a copy.
        """
        return self.intersection(__value, inplace=False, keep_value_method='keep_both')
    
    def __iand__(self, __value: BetterDictLike) -> Self:
        """
        Returns the intersection of this dictionary with another. Will keep both values as the tuple (left_value, right_value). 
            Modifies in-place.
        """
        return self.intersection(__value, inplace=True, keep_value_method='keep_both')
    
    def __rand__(self, __value: BetterDictLike) -> Self:
        """
        Returns the intersection of this dictionary with another, reversed. Will keep both values as the tuple 
            (left_value, right_value). Returns a copy.
        """
        return self.intersection(__value, inplace=False, keep_value_method='keep_both')
    
    def __sub__(self, __value: BetterDictLike) -> Self:
        """
        Returns the set difference of this set and another. (IE: all keys/values that are in this dictionary (left-side 
            dictionary) and are not in the other dictionary (right-side one)). Returns a copy.
        """
        return self.difference(__value, inplace=False)
    
    def __isub__(self, __value: BetterDictLike) -> Self:
        """
        Returns the set difference of this set and another. (IE: all keys/values that are in this dictionary (left-side 
            dictionary) and are not in the other dictionary (right-side one)). Modifies in-place.
        """
        return self.difference(__value, inplace=True)
    
    def __rsub__(self, __value: BetterDictLike) -> Self:
        """
        Returns the set difference of another set and this one. (IE: all keys/values that are in THE OTHER dictionary 
            (right-side dictionary) and are NOT IN THIS dictionary (left-side one)). Returns a copy.
        """
        return self.difference(__value, inplace=False, flip_operands=True)
    
    def __truediv__(self, __value: BetterDictLike) -> Self:
        """
        Returns the set difference of this set and another. (IE: all keys/values that are in this dictionary (left-side 
            dictionary) and are not in the other dictionary (right-side one)). Returns a copy.
        """
        return self.difference(__value, inplace=False)
    
    def __itruediv__(self, __value: BetterDictLike) -> Self:
        """
        Returns the set difference of this set and another. (IE: all keys/values that are in this dictionary (left-side 
            dictionary) and are not in the other dictionary (right-side one)). Modifies in-place.
        """
        return self.difference(__value, inplace=True)
    
    def __rtruediv__(self, __value: BetterDictLike) -> Self:
        """
        Returns the set difference of another set and this one. (IE: all keys/values that are in THE OTHER dictionary 
            (right-side dictionary) and are NOT IN THIS dictionary (left-side one)). Returns a copy.
        """
        return self.difference(__value, inplace=False, flip_operands=True)
    
    def flip(self, inplace: bool = False) -> Self:
        """
        Flips the keys and values of this dictionary. (IE: essentially returns {v: k for k, v in self.items()})
        :param inplace: if False, will return a new object. Otherwise will modify this dictionary in-place
        """
        if inplace:
            new_k_v = [(v, k) for k, v in self.items()]
            self.clear()
            for new_k, new_v in new_k_v:
                self[new_k] = new_v
        return self.__class__([(v, k) for k, v in self.items()])
    
    def invert(self, inplace: bool = False) -> Self:
        """
        Alias for flip(). Flips the keys and values of this dictionary.
        :param inplace: if False, will return a new object. Otherwise will modify this dictionary in-place
        """
        return self.flip(inplace=inplace)
    
    def union(self, *dicts: BetterDictLike, inplace: bool = False, conflict_method: _ConflictMethodInput = 'keep_right') -> Self:
        """
        Returns the union of this dictionary with another
        :param dicts: one or more BetterDictLike objects
        :param inplace: if False, will return a new object. Otherwise will modify this dictionary in-place
        :param conflict_method: the method to use to resolve key/value conflicts. Can be:
            *a string method for how to resolve conflicts. Possible values are:
                - 'raise', 'err', 'raise_error', ... : raise an error on a key conflict (will be KeyError)
                    NOTE: will not raise an error if all the objects are equal. Will call gstats_utils.pythonutils.equal() 
                        to determine equality
                - 'left', 'keep_left', 'self', ... : keep the value in the leftmost object in which that key appears
                - 'right', 'keep_right', 'other', ... : keep the value in the rightmost object in which that key appears
                - 'all', 'keep_all', 'both', 'keep_both', 'tuple' : keep all values as a tuple of (self_val, dicts_val1,
                    dicts_val2, ...). Values for dicts will be in the same order they were passed to this function.
                    NOTE: The return type will be a _KeepAllTuple type which is a subclass of tuple
            * the associated BetterDict.ConflictMethodsEnum constant (EG: BetterDict.ConflictMethodsEnum.RAISE_ERROR)
            * a callable that takes in a tuple of values, and returns the final value
        """
        # In case the user doesn't pass anything, or passes one dict
        if len(dicts) == 0:
            return self if inplace else self.__class__(self)
        
        conflict_method = _get_better_dict_conflict_method(conflict_method, dont_allow='same')
        dicts = self._ensure_better_dicts(dicts)

        working_dict = self if inplace else self.__class__(self)

        for d in dicts:            
            for k, v, key_hash in d._items_with_key_hashes():
                curr_v = working_dict._get_value_with_hash(k, key_hash, default=_OBJECT_MISSING)
                if conflict_method is not BetterDict.ConflictMethodsEnum.KEEP_RIGHT and curr_v is not _OBJECT_MISSING:

                    if conflict_method is BetterDict.ConflictMethodsEnum.KEEP_LEFT:
                        continue

                    elif conflict_method is BetterDict.ConflictMethodsEnum.KEEP_ALL:
                        # Have to do something a little different because we want to keep ALL values, and not let user-passed
                        #   tuples mess things up
                        working_dict[key_hash] = (curr_v + (v,)) if type(curr_v) is _KeepAllTuple else _KeepAllTuple((curr_v, v))

                    elif conflict_method is BetterDict.ConflictMethodsEnum.RAISE_ERROR:
                        if not equal(curr_v, v):  # Don't raise error if the values are equal
                            self._raise_key_error(k, err_message="Key exists in multiple BetterDict's on union_all: %s")

                else:
                    working_dict._set_key_with_hash(k, v, key_hash)
        
        # Call the conflict_method on all _KeepAllTuple's if it is a callable
        if not isinstance(conflict_method, BetterDict.ConflictMethodsEnum):
            for k, v, key_hash in self._items_with_key_hashes():
                if isinstance(v, _KeepAllTuple):
                    self._set_key_with_hash(k, conflict_method(v), key_hash)
        
        return working_dict
    
    def update(self, *dicts: BetterDictLike) -> Self:
        """
        In-place (IE: not copied) updating with the __other BetterDict
        """
        return self.union(*dicts, inplace=True, conflict_method='keep_right')
    
    def intersection(self, *dicts: BetterDictLike, inplace: bool = False, keep_value_method: _ConflictMethodInput = 'keep_right') -> Self:
        """
        Returns the intersection of this dictionary with another (IE: a BetterDict with only the keys/values that
            are in both dictionaries).
        :param dicts: one or more BetterDictLike objects
        :param inplace: if False, will return a new object. Otherwise will modify this dictionary in-place
        :param keep_value_method: the method to use to decide how to keep values. Can be:
            *a string method for how to resolve conflicts. Possible values are:
                - 'left', 'keep_left', 'self', ... : keep the value in the leftmost object in which that key appears
                - 'right', 'keep_right', 'other', ... : keep the value in the rightmost object in which that key appears
                - 'all', 'keep_all', 'both', 'keep_both', 'tuple' : keep all values as a tuple of (self_val, dicts_val1,
                    dicts_val2, ...). Values for dicts will be in the same order they were passed to this function.
                    NOTE: The return type will be a _KeepAllTuple type which is a subclass of tuple
                - 'same', 'keep_same': keep only the values that are the same in all dictionaries. Will call 
                    gstats_utils.pythonutils.equal() to determine equality
            * the associated BetterDict.ConflictMethodsEnum constant (EG: BetterDict.ConflictMethodsEnum.RAISE_ERROR)
            * a callable that takes in a tuple of values, and returns the final value
        """
        # In case the user doesn't pass anything
        if len(dicts) == 0:
            return self if inplace else self.__class__(self)
        
        conflict_method = _get_better_dict_conflict_method(conflict_method, dont_allow='same')

        # Get all of the key hashes that exist in all dictionaries
        dicts = self._ensure_better_dicts(dicts)
        similar_key_hashes = set.intersection(d._keys.keys() for d in ((self,) + dicts))

        # If we are operating inplace, edit this dictionary
        # NOTE: it is split up like this to save us from having to deepcopy keys multiple times
        if inplace:
            
            # No matter what, remove all keys in self that are not in the intersection
            self._del_known_key_hashes(set(self._keys.keys()).difference(similar_key_hashes))

            # If we are KEEP_LEFT, do nothing
            if keep_value_method is BetterDict.ConflictMethodsEnum.KEEP_LEFT:
                pass

            # Elif we are KEEP_RIGHT, move all the values from dicts[-1] over to self
            elif keep_value_method is BetterDict.ConflictMethodsEnum.KEEP_RIGHT:
                for key_hash in similar_key_hashes:
                    self._values[key_hash] = dicts[-1]._values[key_hash]
            
            # Otherwise we are either KEEP_SAME/KEEP_ALL/a callable, and we have to get all the values in all dicts
            else:
                # Go through all of the key hashes keeping those values stored in a list in a dictionary
                ret_vals = {key_hash: tuple(d._values[key_hash] for d in dicts) for key_hash in similar_key_hashes}
                
                # If we are using KEEP_SAME, then we need to check for equality
                if conflict_method is BetterDict.ConflictMethodsEnum.KEEP_SAME:
                    ret_vals = {key_hash: values[0] for key_hash, values in ret_vals.items() if all_equal(*values)}

                    # Remove all excess keys again
                    self._del_known_key_hashes(set(self._keys.keys()).difference(ret_vals.keys()))
                
                # If we are using KEEP_ALL, do nothing
                elif conflict_method is BetterDict.ConflictMethodsEnum.KEEP_ALL:
                    pass

                # Otherwise the conflict_method is a callable, call it on all the values
                else:
                    ret_vals = {key_hash: conflict_method(values) for key_hash, values in ret_vals.items()}

                # Set self's value to its ret_vals value
                for key_hash, v in ret_vals.items():
                    self._values[key_hash] = v

            return self

        # Otherwise we can make and return a new object
        else:

            # If we are doing KEEP_LEFT or KEEP_RIGHT, we can just return the first or last dictionaries respectively, minus
            #   all of the keys we are not keeping
            if keep_value_method in [BetterDict.ConflictMethodsEnum.KEEP_LEFT, BetterDict.ConflictMethodsEnum.KEEP_RIGHT]:
                d = (dicts[0] if keep_value_method is BetterDict.ConflictMethodsEnum.KEEP_LEFT else dicts[-1])
                return self._from_keys_and_hashes((k, v, h) for (k, v, h) in d._items_with_key_hashes() if h in similar_key_hashes)
            
            # Otherwise we are using either KEEP_ALL or KEEP_SAME. Go through all of the key hashes keeping those values
            #   stored in a list in a dictionary
            ret_vals = {key_hash: (dicts[0]._keys[key_hash], tuple(d._values[key_hash] for d in dicts)) for key_hash in similar_key_hashes}
            
            # If we are using KEEP_SAME, then we need to check for equality
            if conflict_method is BetterDict.ConflictMethodsEnum.KEEP_SAME:
                ret_vals = {key_hash: (key, values[0]) for key_hash, (key, values) in ret_vals.items() if all_equal(*values)}
                
            # If we are using KEEP_ALL, do nothing
            elif conflict_method is BetterDict.ConflictMethodsEnum.KEEP_ALL:
                pass

            # Otherwise the conflict_method is a callable, call it on all the values
            else:
                ret_vals = {key_hash: conflict_method(values) for key_hash, values in ret_vals.items()}
            
            # Now build that into an object and return
            return self._from_keys_and_hashes((k, v, h) for h, (k, v) in ret_vals.items())
    
    def intersect(self, *dicts: BetterDictLike, inplace: bool = False, keep_value_method: _ConflictMethodInput = 'keep_right') -> Self:
        """
        Alias for intersection()
        """
        return self.intersection(*dicts, inplace=inplace, keep_value_method=keep_value_method)
    
    def difference(self, *dicts: BetterDictLike, inplace: bool = False, flip_operands: bool = False) -> Self:
        """
        Returns the set difference between this set and another. (IE: all keys/values that are in this dictionary [the
            left-side one], but not in the other [the right-side one])
        :param dicts: one or more BetterDictLike objects
        :param inplace: if False, will return a new object. Otherwise will modify this dictionary in-place
        :param flip_operands: if True, will flip the operands. IE: will instead return all keys/values that are in
            THE OTHER dictionary (the right-side one), but not in this one (the left-side one).
            NOTE: if you flip_operands, but __other is not a BetterDict, then a copy will be returned anyways, no
                matter the inplace value.
        """
        # In case the user doesn't pass anything
        if len(dicts) == 0:
            return self if inplace else self.__class__(self)

        dicts = self._ensure_better_dicts(dicts)
        
        if flip_operands:
            return dicts[-1].difference(reversed(dicts[:-1]) + (self,), inplace=inplace, flip_operands=False)
        
        # Find the union of all keys in dicts (not self)
        dicts_keys = set.union(*[d._keys.keys() for d in dicts])
        
        # If we are inplace, then we can remove all extra keys
        if inplace:
            # Find all of the key hashes to remove (IE: the keys in our dict intersect the union of all keys in all other dicts)
            self._del_known_key_hashes(set(self._keys.keys()).intersection(dicts_keys))            
            return self
        
        # Otherwise we can add our kept keys to a new dictionary
        else:
            # Find all of the key hashes to keep (IE: the keys in our dict minus the union of all keys in all other dicts)
            keep_hashes = set(self._keys.keys()).difference(dicts_keys)

            return self._from_keys_and_hashes([(self._keys[key_hash], self._values[key_hash], key_hash) for key_hash in keep_hashes])
    
    def diff(self, *dicts: BetterDictLike, inplace: bool = False, flip_operands: bool = False) -> Self:
        """
        Alias for difference()
        """
        return self.difference(*dicts, inplace=inplace, flip_operands=flip_operands)
    
    def symmetric_difference(self, *dicts: BetterDictLike, inplace: bool = False) -> Self:
        """
        Returns the symmetric difference of this dictionary and one or more others (IE: all of the keys/values that only
            exist in exactly one of the dictionaries). Essentially the xor operation when applied to two dictionaries.
        :param dicts: one or more BetterDictLike objects
        :param inplace: if False, will return a new object. Otherwise will modify this dictionary in-place
        """
        # In case the user doesn't pass anything
        if len(dicts) == 0:
            return self if inplace else self.__class__(self)

        dicts = self._ensure_better_dicts(dicts)

        # Get the key hashes that exist in exactly one dictionary
        unique_key_hashes = set()
        for d in dicts:
            unique_key_hashes = unique_key_hashes.symmetric_difference(d._keys.keys())

        # If we are inplace, then we can edit this first dictionary
        if inplace:
            working_dict = self

            # Remove all the duplicate key hashes
            for key_hash in working_dict._keys:
                if key_hash not in unique_key_hashes:
                    working_dict._del_with_hash(None, key_hash)
        
        # Otherwise we create a new dictionary and add to it
        else:
            working_dict = self.__class__(self)

        # Remove all the keys in self since those are already accounted for
        unique_key_hashes = unique_key_hashes.difference(self._keys.keys())
        
        # Get all the keys/values/key_hashes from each dictionary where the key_hash is not in similar_key_hashes
        # Doing it like this since each key, once used once, doesn't need to be searched for and can save time on
        #   searching for keys
        for d in dicts:
            removes = set()
            for key_hash in unique_key_hashes:
                v = d._get_value_with_hash(None, key_hash, default=_OBJECT_MISSING)
                if d is not _OBJECT_MISSING:
                    working_dict._set_key_with_hash(d._keys[key_hash], v, key_hash)
                    removes.add(key_hash)
            unique_key_hashes = unique_key_hashes.difference(removes)

        return working_dict
    
    def xor(self, *dicts: BetterDictLike, inplace: bool = False) -> Self:
        """
        Alias for symmetric_difference()
        """
        return self.symmetric_difference(self, *dicts, inplace=inplace)
    
    def apply(self, func: Callable[[BetterDictObject, BetterDictObject], BetterDictObject], inplace: bool = False) -> Self:
        """
        Applies the given function to all values in the dictionary.
        :param func: a callable that should take in args key and value, and output a new value
        :param inplace: if False, will return a new object. Otherwise will modify this dictionary in-place
        """
        if inplace:
            for k, v, key_hash in self._items_with_key_hashes():
                self._set_key_with_hash(k, func(k, v), key_hash)
            return self
        return self._from_keys_and_hashes([(k, func(k, v), key_hash) for k, v, key_hash in self._items_with_key_hashes()])
    
    def aggregate_values(self, func: Optional[Callable[[list[BetterDictObject]], Any]] = None) -> Any:
        """
        Aggregates all values in this dictionary into a list, then calls func() on them
        :param func: a callable that should take in a list of values, and return the aggregated operation on that list.
            If func is None, then it will be the identity function (IE: this method would return just a list of the values)
        """
        if func is None:
            func = lambda x: x
        return func(list(self.values()))

    @staticmethod
    def _raise_key_error(key: BetterDictObject, err_message: Optional[str] = None) -> NoReturn:
        # Raise a KeyError with the string of the key, making sure the string isn't too large
        key_error_str = str(key)
        if len(key_error_str) > 200:
            key_error_str = key_error_str[:200]
        err_message = "%s" if err_message is None else err_message
        raise KeyError(err_message % repr(key_error_str))  # Do repr to convert to string that could be parsed nicely
    
    @classmethod
    def _ensure_better_dicts(cls, *dicts: BetterDictLike) -> Self:
        """
        Makes sure all of the given BetterDictLike objects either are self.__class__, or are turned into one.
        """
        return [d if isinstance(d, cls) else cls(d) for d in dicts]
    
    @classmethod
    def fromkeys(cls, keys: Iterable[BetterDictObject], value: Optional[BetterDictObject] = None) -> Self:
        """
        Generates a new BetterDict from the given list of key objects. A value can optionally be passed as well which
            will be used for each key (otherwise, values will be None).
        :param keys: an iterable of key objects to use
        :param value: if not None, then a single object to use as a value for all the keys. Otherwise if None, then all
            keys will have None as their value
        """
        try:
            dict_input = [(k, value) for k in keys]
        except TypeError:
            raise TypeError("Could not iterate through non-iterable type '%s' to generate keys." % type(keys))
        
        return cls(dict_input=dict_input)
    
    @classmethod
    def _from_keys_and_hashes(cls, kvh: Iterable[tuple(BetterDictObject, BetterDictObject, str)]):
        """
        Builds a new instance of cls using keys, values, and key_hashes. Expects input in the same way it would be
            recieved from cls()._items_with_key_hashes().
        """
        ret = cls()
        for k, v, key_hash in kvh:
            ret._set_key_with_hash(k, v, key_hash)
        return ret
    

class _KeepAllTuple(tuple):
    """
    Class to use for union_all and intersect_all to keep track of conflicting values when conflict_method is
        BetterDict.ConflictMethodsEnum.KEEP_ALL, without having to worry about the values themselves being tuples. Works
        exactly the same as a normal tuple(), just with a different class name.
    """
    pass


# Get the conflict_method values and names
_CONFLICT_METHOD_DICT = {getattr(BetterDict, k): k for k in dir(BetterDict) if k.startswith('CONFLICT_')}
def _get_better_dict_conflict_method(conflict_method: _ConflictMethodInput, 
    dont_allow: Optional[Union[_ConflictMethodInput, Sequence[_ConflictMethodInput]]] = None) -> ConflictMethod:
    """
    Returns one of BetterDict.[CONFLICT_RAISE_ERROR, CONFLICT_KEEP_LEFT, CONFLICT_KEEP_RIGHT, CONFLICT_KEEP_BOTH]
        depending on the conflict_method input, and sanitizes
    :param conflict_method:
    :param dont_allow: a list of BetterDict.[CONFLICT METHODS] that are NOT allowed, and will raise an error
    """

    # Parse how to deal with key conflicts
    if isinstance(conflict_method, str):
        clean_cm = conflict_method.lower().strip()
        for cm in BetterDict.ConflictMethodsEnum:
            if re.fullmatch(cm.value, clean_cm) is not None:
                clean_cm = cm
                break
        else:
            raise ValueError("Unknown conflict_method string: '%s'" % conflict_method)
    elif isinstance(conflict_method, BetterDict.ConflictMethodsEnum):
        clean_cm = conflict_method
    elif callable(conflict_method):
        clean_cm = conflict_method
    else:
        raise TypeError("Conflict_method must be of type str or int, not '%s'" % type(conflict_method))
    
    # Check for dont_allow values
    dont_allow = [dont_allow] if isinstance(dont_allow, (int, str)) else [] if dont_allow is None else dont_allow
    dont_allow = [_get_better_dict_conflict_method(cm) for cm in dont_allow]
    if clean_cm in dont_allow:
        raise ValueError("Cannot use method %s for this function" % _CONFLICT_METHOD_DICT[clean_cm])

    return clean_cm
    