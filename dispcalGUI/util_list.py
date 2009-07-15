#!/usr/bin/env python
# -*- coding: utf-8 -*-

def floatlist(alist):
	""" Convert all list items to floats (0.0 on error) """
	result = []
	for item in alist:
		try:
			result.append(float(item))
		except ValueError:
			result.append(0.0)
	return result

def indexi(self, value, start = None, stop = None):
	""" Case-insensitive version of list.index """
	items = [(item.lower() if isinstance(item, (str, unicode)) else item) for item in self]
	args = [value.lower()]
	if start is not None:
		args += [start]
	if stop is not None:
		args += [stop]
	return items.index(*args)

def strlist(alist):
	""" Convert all list items to strings """
	return [str(item) for item in alist]
