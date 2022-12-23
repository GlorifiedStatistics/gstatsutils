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

from gstats_utils.pythonutils.equality import equal
