"""
Utils for determining equality of objects

Handled types:
    - None, Ellipsis, NotImplemented
    - bool
    - int, float, np.number, complex
    - bytes, bytearray, memoryview
    - str
    - range
    - type
    - list, tuple
    - numpy ndarray
    - set, frozenset
    - dict, dict_keys, dict_values (computes dict_keys equality with '==', dict_values with 'equal(..., unordered=True)')
    - enum

Future planned types:
    - pytorch tensors/other types
    - pandas dataframes/series'
    - scipy things?
    - more builtin types, both C and Python ones
"""

import numpy as np
from enum import Enum
from .backport_types import GeneratorType, DictKeysType, DictValuesType
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from typing import Any, Optional


_MAX_STR_LEN = 1000


def equal(a: 'Any', b: 'Any', selector: 'Optional[str]' = None, strict_types: 'bool' = False, unordered: 'bool' = False, 
    raise_err: 'bool' = False) -> 'bool':
    """
    Determines whether a == b, generalizing for more objects and capabilities than default __eq__() method.
    Equal() is an equivalence relation, and thus:

        1. equal(a, a) is always True                       (reflexivity)
        2. equal(a, b) implies equal(b, a)                  (symmetric)
        3. equal(a, b) and equal(b, c) implies equal(a, c)  (transitivity)
    
    Args:
        a (Any): object to check equality
        b (Any): object to check equality
        selector (Optional[str]): if not None, then a string that determines the 'selector' to use on both objects for
            determining equality. It should start with either a letter (case-sensitive), underscore '_', dot '.' or
            bracket '['. This string will essentially be appended to each object to get some attribute to determine
            equality of instead of the objects themselves. For example, if you have two lists, but only want to check
            if their element at index '2' are equal, you could pass `selector='[2]'`. This is useful for debugging purposes
            as the error messages on unequal objects will be far more informative. Defaults to None.

            NOTE: if you pass a `selector` string that starts with an alphabetical character, it will be assumed to be
            an attribute, and this will check equality on `a.SELECTOR` and `b.SELECTOR`
        strict_types (bool): if True, then the types of both objects must exactly match. Otherwise objects which are 
            equal but of different types will be considered equal. Defaults to False.
        unordered (bool): if True, then all known sequential objects (list, tuple, numpy array, etc.) will be considered
            equal even if elements are in a different order (eg: a multiset equality). Otherwise, sequential objects are
            expected to have their subelements appear in the same order. If the passed objects are not sequential, then
            this has no effect. Defaults to False.
        raise_err (bool): if True, then an ``EqualityError`` will be raised whenever `a` and `b` are unequal, along with
            an informative stack trace as to why they were determined to be unequal. Defaults to False.
    """
    # Get the right selector, raising an error if it's bad
    if selector is not None:
        if not isinstance(selector, str):
            raise TypeError("`selector` arg must be str, not %s" % repr(type(selector).__name__))
        if selector == '':
            selector = None
        elif selector[0].isalpha():
            selector = '.' + selector
        elif selector[0] not in '._[':
            raise ValueError("`selector` string must start with a '.', '_', '[', or alphabetic character: %s" % repr(selector))
    
    # Use `selector` if needed
    if selector is not None:
        try:
            _failed_obj_name = 'a'
            _check_a = eval('a' + selector)
            _failed_obj_name = 'b'
            _check_b = eval('b' + selector)
            _failed_obj_name = None

            return equal(_check_a, _check_b, selector=None, strict_types=strict_types, unordered=unordered, raise_err=raise_err)
        except EqualityError:
            raise EqualityError(a, b, "Objects had different sub-objects using `selector` %s" % repr(selector))
        except Exception:
            if _failed_obj_name is None:
                raise EqualityCheckingError("Could not determine equality between objects a and b using `selector` %s\na: %s\nb: %s" %
                    (repr(selector), _limit_str(a), _limit_str(b)))
            raise EqualityCheckingError("Could not use `selector` with value %s on object `%s`" % (repr(selector), _failed_obj_name))

    # Wrap everything in a try/catch in case there is an error, so it will be easier to spot
    try:

        # Do a quick first check for 'is' as they should always be equal, no matter what
        if a is b:
            return True
        
        # Check if there are strict types
        if strict_types and type(a) != type(b):
            return _eq_check(False, a, b, selector, raise_err, message='Objects are of different types and `strict_types=True`.')
        
        ##################
        # Checking types #
        ##################

        # We already checked 'is', so this must be an error
        if a in [None, Ellipsis, NotImplemented] or isinstance(a, Enum):
            return _eq_check(False, a, b, raise_err)
        
        # Check for bool first that way int's and bool's cannot be equal
        elif isinstance(a, bool):
            # Enforce that this is a bool no matter what. Bool's are NOT int's. I will die on this hill...
            if not _eq_enforce_types(bool, a, b, raise_err):
                return False
            return _eq_check(a == b, a, b, raise_err, message=None)
        
        # Check for objects using '=='
        elif isinstance(a, (int, float, np.number, complex, bytes, bytearray, memoryview, str, range, type, set,
                frozenset, DictKeysType)):
            return _eq_check(a == b, a, b, raise_err, message=None)
        
        # Check for sequences list/tuple
        elif isinstance(a, (list, tuple)):
            
            # Check that b is something that could be converted into a list/tuple nicely

            # If check_b is a numpy array, convert check_a to one and do a numpy comparison
            if isinstance(b, np.ndarray):
                # Check if check_b is an object array, and if so, use lists, otherwise use numpy
                if b.dtype == object:
                    return _check_with_conversion(a, None, b, list, unordered, raise_err, strict_types)
                return _check_with_conversion(a, np.ndarray, b, None, unordered, raise_err)

            # Check for things to convert to list
            elif isinstance(b, (GeneratorType, DictKeysType)):
                return _check_with_conversion(a, None, b, list, unordered, raise_err)
            
            # Otherwise, make sure check_b is a list/tuple
            elif not isinstance(b, (list, tuple)):
                return _eq_check(False, a, b, raise_err, message="checked b type could not be converted into list/tuple")
            
            # This is where we handle the actual checking.
            # Check that they are the same length
            if len(a) != len(b):
                return _eq_check(False, a, b, raise_err, message="Objects had different lengths: %d != %d" % (len(a), len(b)))
            
            # If we are using ordered, then we can just naively check, otherwise, we have to do some other things...
            if not unordered:
                # Check each element in the lists
                for i, (_checking_a, _checking_b) in enumerate(zip(a, b)):
                    try:
                        # It will have returned an error if raise_err, so just return False
                        if not equal(_checking_a, _checking_b, selector=None, strict_types=strict_types, unordered=unordered, raise_err=raise_err):
                            return False
                    except EqualityError:  # If we get an equality error, then raise_err must be true
                        raise EqualityError(a, b, "Values at index %d were not equal" % i)
                    except Exception:
                        raise EqualityCheckingError("Could not determine equality between elements at index %d" % i)
                
                # Now we can return True
                return True

            # Unordered list checking
            else:
                raise NotImplementedError
        
        # Check for numpy array
        elif isinstance(a, np.ndarray):

            # Ensure the other value can be converted into an array
            if not isinstance(b, np.ndarray):
                # If check_a is an object array, then just convert it to a list now and have that check it
                if a.dtype == object:
                    return _check_with_conversion(a, list, b, None, raise_err=raise_err, strict_types=strict_types)
                
                # Otherwise, if it is a known convertible, convert it
                if isinstance(b, (list, tuple, GeneratorType)):
                    return _check_with_conversion(a, None, b, np.array, unordered, raise_err, strict_types=strict_types)
                
                # Otherwise, assume not equal
                return _eq_check(False, a, b, raise_err, message="Could not convert b object of type %s to numpy array" % type(b).__name__)

            # Check if we are using objects or a different dtype
            if a.dtype == object:
                # Attempt to check using lists at this point
                return _check_with_conversion(a, list, b, list, raise_err=raise_err, strict_types=strict_types)

            # Otherwise, check if we are doing unordered or ordered.
            if not unordered:
                # we can use the builtin numpy assert equal thing
                try:
                    np.testing.assert_equal(a, b)
                except AssertionError as e:
                    return _eq_check(False, a, b, raise_err, message='Numpy assert_equal found discrepancies:\n%s' % e)
            
            # Otherwise we need to do an unordered equality check. Just convert to a list at this point and check it
            else:
                return _check_with_conversion(a, list, b, list, unordered, raise_err, strict_types)
        
        # Check for dictionaries
        elif isinstance(a, dict):
            # b must be a dictionary
            if not _eq_enforce_types(dict, a, b, raise_err, message='Dictionaries must be same type to compare'):
                return False
            
            # Check all the keys are the same
            try:
                if not equal(a.keys(), b.keys(), selector=None, strict_types=strict_types, unordered=unordered, raise_err=raise_err):
                    return False
            except EqualityError:  # If we get an equality error, then raise_err must be true
                raise EqualityError(a, b, message="Dictionaries had different .keys()")
            except Exception:
                raise EqualityCheckingError("Could not determine equality between dictionary keys\na: %s\nb: %s" %
                    (_limit_str(a.keys()), _limit_str(b.keys())))
            
            # Check all the values are the same
            for k in a:
                try:
                    if not equal(a[k], b[k], selector=None, strict_types=strict_types, unordered=unordered, raise_err=raise_err):
                        return False
                except EqualityError:  # If we get an equality error, then raise_err must be true
                    raise EqualityError(a, b, message="Values at key %s differ" % repr(k))
                except Exception:
                    raise EqualityCheckingError("Could not determine equality between dictionary values at key %s" % repr(k))
            
            # Now we can return True
            return True
        
        # Check for dict_values. These can call the equality with list and unordered 
        elif isinstance(a, DictValuesType):
            return _check_with_conversion(a, list, b, None, unordered=True, raise_err=raise_err, strict_types=strict_types)
        
        else:
            raise NotImplementedError
    
    except EqualityError:
        raise
    except Exception:
        raise EqualityCheckingError("Could not determine equality between objects\na: %s\nb: %s" % (_limit_str(a), _limit_str(b)))


def _check_with_conversion(a, type_a, b, type_b, unordered, raise_err, strict_types=False):
    """Attempts to convert check_a into type_a and check_b into type_b (by calling the types), then check equality on those
    
    Gives better error messages when things go wrong. You can pass None to one of the types to not change type. Pass the
    type itself (instead of a function) for better nameing on error messages about what they were being converted into.
    The name is given by type_a.__name__ if type_a is a type, or 'a lambda function' if it is an annonymus function, or
    the module + function name if a function
    """
    ca_type, check_a_str = _get_check_type(type_a)
    cb_type, check_b_str = _get_check_type(type_b)

    conversion_str = ('(with a value being converted using %s and b value being converted using %s)' % (check_a_str, check_b_str))\
            if check_a_str and check_b_str else \
        ('(with a value being converted using %s)' % check_a_str) if check_a_str else \
        ('(with b value being converted using %s)' % check_b_str) if check_b_str else \
        ''

    try:
        return equal(ca_type(a), cb_type(b), selector=None, strict_types=strict_types, unordered=unordered, raise_err=raise_err)
    except EqualityCheckingError:
        raise
    except Exception:
        _eq_check(False, a, b, raise_err, message="Values were not equal %s" % conversion_str)


def _get_check_type(t):
    """Returns a function to call and a string describing what is being used to convert type given the type to convert
    
    Returns a tuple of (conversion_callable, type_description_string). The string will be empty if the conversion is
    the identity, t.__name__ if t is a type, 'a lambda function' if it is an anonymous function, or the module + 
    function/class name if it is a callable.
    """
    if not callable(t):
        raise EqualityCheckingError("Cannot convert object types as given `type` is not callable: %s" % repr(t))
    
    if t is None:
        return lambda x: x, ''
    
    return t, ('type ' + repr(t.__name__)) if isinstance(t, type) else repr(t)


def _eq_enforce_types(types, a, b, raise_err, message=None):
    """enforces check_b is of the given types using isinstance"""
    if not isinstance(b, types):
        return _eq_check(False, a, b, raise_err, 'Objects were of incompatible types.')
    return True


def _eq_check(checked, a, b, raise_err, message=None):
    """bool equal check, determine whether or not we need to raise an error with info, or just return true/false"""
    if not checked:
        if raise_err:
            raise EqualityError(a, b, message)
        return False
    return True


def _limit_str(a, limit=_MAX_STR_LEN):
    a_str = repr(a)
    return a_str if len(a_str) < limit else (a[:limit] + '...')


class EqualityError(Exception):
    """Error raised whenever an :func:`~gstats_utils.pythonutils.equality.equal` check returns false and `raise_err=True`"""

    def __init__(self, a, b, message=None):
        message = "Values are not equal" if message is None else message
        super().__init__("Object a (%s) is not equal to object b (%s)\na: %s\nb: %s\nMessage: %s" % \
            (repr(type(a).__name__), repr(type(b).__name__), _limit_str(a), _limit_str(b), message))


class EqualityCheckingError(Exception):
    """Error raised whenever there is an unexpected problem attempting to check equality between two objects"""
