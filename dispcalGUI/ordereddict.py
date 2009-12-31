#!/usr/bin/env python
# -*- coding: utf-8 -*-

class OrderedDict(dict):
	
	"""
	Simple ordered dictionary.
	
	"""
	
	def __init__(self, *args):
		self.clear()
		dict.__init__(self, *args)
	
	def __delitem__(self, key):
		index = self._key2index[key]
		del self._ordered[index]
		del self._key2index[key]
		if len(self._ordered) > index:
			for i in range(index, len(self._ordered)):
				self._key2index[self._ordered[i][0]] -= 1
		dict.__delitem__(self, key)
	
	def __iter__(self):
		for key, value in self._ordered:
			yield key
	
	def __setitem__(self, key, value):
		self._key2index.setdefault(key, len(self._ordered))
		if key in self:
			self._ordered[self._key2index[key]] = (key, value)
		else:
			self._ordered.append((key, value))
		dict.__setitem__(self, key, value)
	
	def clear(self):
		self._key2index = {}
		self._ordered = []
		dict.clear(self)
	
	def fromkeys(self, keys, value=None):
		self.clear()
		for key in keys:
			self[key] = value
	
	def items(self):
		return self._ordered
	
	def iteritems(self):
		for key, value in self._ordered:
			yield key, value
	
	def iterkeys(self):
		return self.__iter__()
	
	def itervalues(self):
		for key, value in self._ordered:
			yield value
	
	def keys(self):
		keys = []
		for key, value in self._ordered:
			keys.append(key)
		return keys
	
	def pop(self, key, *args):
		value = self.get(key, *args)
		del self[key]
		return value
	
	def popitem(self):
		key, value = self._ordered[-1]
		del self[key]
		return key, value
	
	def setdefault(self, key, value=None):
		if not key in self:
			self[key] = value
		return self.get(key, value)
	
	def update(self, obj):
		if isinstance(obj, dict):
			for key in obj:
				self[key] = obj[key]
		else:
			for key, value in obj:
				self[key] = value
	
	def values(self):
		values = []
		for key, value in self._ordered:
			values.append(value)
		return values
