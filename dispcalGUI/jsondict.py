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

	def __init__(self, path, encoding="UTF-8"):
		dict.__init__(self)
		self._isloaded = False
		self.path = path
		self.encoding = encoding
	
	def __contains__(self, key):
		self.load()
		return dict.__contains__(self, key)

	def __getitem__(self, name):
		self.load()
		return dict.__getitem__(self, name)

	def __iter__(self):
		self.load()
		return dict.__iter__(self)
	
	def get(self, name, fallback=None):
		self.load()
		return dict.get(self, name, fallback)

	def load(self):
		if not self._isloaded:
			self._isloaded = True
			if not os.path.isabs(self.path):
				path = get_data_path(self.path)
				if path:
					self.path = path
				else:
					handle_error(u"Warning - JSON file '%s' not found" % 
								 safe_unicode(self.path))
					return
			try:
				jsonfile = codecs.open(self.path, "rU", self.encoding)
				try:
					self.update(demjson.decode(jsonfile.read()))
				except (UnicodeDecodeError, 
						demjson.JSONDecodeError), exception:
					handle_error(
						u"Warning - JSON file '%s': %s" % 
						tuple(safe_unicode(s) for s in 
							  (self.path, exception.args[0].capitalize() if 
										  isinstance(exception, 
													 demjson.JSONDecodeError)
										  else exception)))
			except Exception, exception:
				handle_error(u"Warning - JSON file '%s': %s" % 
							 tuple(safe_unicode(s) for s in (self.path, 
															 exception)))
			else:
				jsonfile.close()
