# -*- coding: utf-8 -*-

import demjson

from lazydict import LazyDict


class LazyDict_JSON(LazyDict):

	"""
	JSON lazy dictionary
	
	"""
	
	def parse(self, fileobj):
		dict.update(self, demjson.decode(fileobj.read()))


JSONDict = LazyDict_JSON
