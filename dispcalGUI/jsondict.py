#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codecs
import os

import demjson

from config import get_data_path
from debughelpers import handle_error
from util_str import safe_unicode


class JSONDict(dict):

	"""
	JSON dictionary with key -> value mappings.
	
	The actual mappings are loaded from the source JSON file when they
	are accessed.
	
	"""

	def __init__(self, path=None, encoding="UTF-8", errors="strict"):
		dict.__init__(self)
		self._isloaded = False
		self.path = path
		self.encoding = encoding
		self.errors = errors
		
	def __cmp__(self, other):
		self.load()
		return dict.__cmp__(self, other)
	
	def __contains__(self, key):
		self.load()
		return dict.__contains__(self, key)
	
	def __delitem__(self, key):
		self.load()
		dict.__delitem__(self, key)
	
	def __delslice__(self, i, j):
		self.load()
		dict.__delslice__(self, i, j)
	
	def __eq__(self, other):
		self.load()
		return dict.__eq__(self, other)
	
	def __ge__(self, other):
		self.load()
		return dict.__ge__(self, other)

	def __getitem__(self, name):
		self.load()
		return dict.__getitem__(self, name)
	
	def __getslice__(self, i, j):
		self.load()
		return dict.__getslice__(self, i, j)
	
	def __gt__(self, other):
		self.load()
		return dict.__gt__(self, other)

	def __iter__(self):
		self.load()
		return dict.__iter__(self)
	
	def __le__(self, other):
		self.load()
		return dict.__le__(self, other)
	
	def __len__(self):
		self.load()
		return dict.__len__(self)
	
	def __lt__(self, other):
		self.load()
		return dict.__lt__(self, other)
	
	def __ne__(self, other):
		self.load()
		return dict.__ne__(self, other)
	
	def __repr__(self):
		self.load()
		return dict.__repr__(self)

	def __setitem__(self, name, value):
		self.load()
		dict.__setitem__(self, name, value)

	def __sizeof__(self):
		self.load()
		return dict.__sizeof__(self)
	
	def clear(self):
		if not self._isloaded:
			self._isloaded = True
		dict.clear(self)
	
	def copy(self):
		self.load()
		return dict.copy(self)
	
	def get(self, name, fallback=None):
		self.load()
		return dict.get(self, name, fallback)
	
	def has_key(self, name):
		self.load()
		return dict.has_key(self, name)
	
	def items(self):
		self.load()
		return dict.items(self)
	
	def iteritems(self):
		self.load()
		return dict.iteritems(self)
	
	def iterkeys(self):
		self.load()
		return dict.iterkeys(self)
	
	def itervalues(self):
		self.load()
		return dict.itervalues(self)
	
	def keys(self):
		self.load()
		return dict.keys(self)

	def load(self, path=None, encoding=None, errors=None):
		if not self._isloaded and (path or self.path):
			self._isloaded = True
			if not path:
				path = self.path
			if path and not os.path.isabs(path):
				path = get_data_path(path)
			if path and os.path.isfile(path):
				self.path = path
				if encoding:
					self.encoding = encoding
				if errors:
					self.errors = errors
			else:
				handle_error(u"Warning - JSON file '%s' not found" % 
							 safe_unicode(path))
				return
			try:
				jsonfile = codecs.open(path, "rU", self.encoding, self.errors)
				try:
					dict.update(self, demjson.decode(jsonfile.read()))
				except (UnicodeDecodeError, 
						demjson.JSONDecodeError), exception:
					handle_error(
						u"Warning - JSON file '%s': %s" % 
						tuple(safe_unicode(s) for s in 
							  (path, safe_unicode(exception).capitalize() if 
									 isinstance(exception, 
												demjson.JSONDecodeError)
									 else exception)))
			except Exception, exception:
				handle_error(u"Warning - JSON file '%s': %s" % 
							 tuple(safe_unicode(s) for s in (path, 
															 exception)))
			else:
				jsonfile.close()
	
	def pop(self, key, *args):
		self.load()
		return dict.pop(self, key, *args)

	def popitem(self, name, value):
		self.load()
		return dict.popitem(self, name, value)

	def setdefault(self, name, value=None):
		self.load()
		return dict.setdefault(self, name, value)
	
	def update(self, other):
		self.load()
		dict.update(self, other)
	
	def values(self):
		self.load()
		return dict.values(self)
