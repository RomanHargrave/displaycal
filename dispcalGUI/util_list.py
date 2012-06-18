# -*- coding: utf-8 -*-

import re

def floatlist(alist):
	""" Convert all list items to floats (0.0 on error) """
	result = []
	for item in alist:
		try:
			result.append(float(item))
		except ValueError:
			result.append(0.0)
	return result


def index_ignorecase(self, value, start = None, stop = None):
	""" Case-insensitive version of list.index """
	items = [(item.lower() if isinstance(item, (str, unicode)) else item) 
			 for item in self]
	return items.index(value, start or 0, stop or len(self))


def index_fallback_ignorecase(self, value, start = None, stop = None):
	""" Return index of value in list. Prefer a case-sensitive match. """
	if value in self:
		return self.index(value, start or 0, stop or len(self))
	return index_ignorecase(self, value, start or 0, stop or len(self))


def intlist(alist):
	""" Convert all list items to ints (0 on error) """
	result = []
	for item in alist:
		try:
			result.append(int(item))
		except ValueError:
			result.append(0)
	return result


def natsort(list_in):
	""" Sort a list which (also) contains integers naturally. """
	list_out = []
	# decorate
	alphanumeric = re.compile("\D+|\d+")
	numeric = re.compile("^\d+$")
	for i in list_in:
		match = alphanumeric.findall(i)
		tmp = []
		for j in match:
			if numeric.match(j):
				tmp.append((int(j), j))
			else:
				tmp.append((j, None))
		list_out.append(tmp)
	list_out.sort()
	list_in = list_out
	list_out = []
	# undecorate
	for i in list_in:
		tmp = []
		for j in i:
			if type(j[0]) in (int, long):
				tmp.append(j[1])
			else:
				tmp.append(j[0])
		list_out.append("".join(tmp))
	return list_out


def strlist(alist):
	""" Convert all list items to strings """
	return [str(item) for item in alist]
