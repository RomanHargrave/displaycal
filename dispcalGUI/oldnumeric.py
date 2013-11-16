# -*- coding: utf-8 -*-

"""
Compatibility module for wxenhancedplot
This is NOT a complete replacement for oldnumeric
The oldnumeric module will be dropped in Numpy 1.9

"""

from numpy import (add, arange, argmin, array, ceil, compress, concatenate, cos,
				   fabs, floor, log10, maximum, minimum, pi, power, repeat, sin,
				   sometrue, sqrt, transpose, zeros)

typecodes = {'Integer':'bhil', 'Float':'fd'}

def _get_precisions(typecodes):
    lst = []
    for t in typecodes:
        lst.append( (zeros( (1,), t ).itemsize*8, t) )
    return lst

def _fill_table(typecodes, table={}):
    for key, value in typecodes.items():
        table[key] = _get_precisions(value)
    return table

_code_table = _fill_table(typecodes)

class PrecisionError(Exception):
    pass

def _lookup(table, key, required_bits):
    lst = table[key]
    for bits, typecode in lst:
        if bits >= required_bits:
            return typecode
    raise PrecisionError, key+" of "+str(required_bits)+" bits not available on this system"

try:
    Int32 = _lookup(_code_table, 'Integer', 32)
except(PrecisionError):
    pass

try:
    Float64 = _lookup(_code_table, 'Float', 64)
except(PrecisionError):
    pass
Float = 'd'
