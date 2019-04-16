# -*- coding: utf-8 -*-

import codecs
import os

import demjson

from config import get_data_path
from debughelpers import handle_error
from lazydict import LazyDict
from util_str import safe_unicode


class LazyDict_JSON(LazyDict):

	"""
	JSON lazy dictionary
	
	"""

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
				handle_error(UserWarning(u"Warning - JSON file '%s' not found" % 
										 safe_unicode(path)))
				return
			try:
				jsonfile = codecs.open(path, "rU", self.encoding, self.errors)
				try:
					dict.update(self, demjson.decode(jsonfile.read()))
				except (UnicodeDecodeError, 
						demjson.JSONDecodeError), exception:
					handle_error(UserWarning(
						u"Warning - JSON file '%s': %s" % 
						tuple(safe_unicode(s) for s in 
							  (path, safe_unicode(exception).capitalize() if 
									 isinstance(exception, 
												demjson.JSONDecodeError)
									 else exception))))
			except Exception, exception:
				handle_error(UserWarning(u"Warning - JSON file '%s': %s" % 
										 tuple(safe_unicode(s) for s in
											   (path, exception))))
			else:
				jsonfile.close()


JSONDict = LazyDict_JSON
