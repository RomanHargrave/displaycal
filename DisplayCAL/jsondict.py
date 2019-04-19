# -*- coding: utf-8 -*-

import demjson_compat

from lazydict import LazyDict


class LazyDict_JSON(LazyDict):

	"""
	JSON lazy dictionary
	
	"""
	
	def parse(self, fileobj):
		dict.update(self, demjson_compat.decode(fileobj.read()))


JSONDict = LazyDict_JSON
