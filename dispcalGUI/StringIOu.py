#!/usr/bin/env python
# -*- coding: utf-8 -*-

from StringIO import StringIO

def universal_newlines(txt):
	return txt.replace("\r\n", "\n").replace("\r", "\n")

class StringIOu(StringIO):
	def __init__(self, buf = ''):
		StringIO.__init__(self, universal_newlines(buf))
