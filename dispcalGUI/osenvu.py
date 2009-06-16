#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

def expanduseru(path):
	return unicode(os.path.expanduser(path), sys.getfilesystemencoding())

def expandvarsu(path):
	return unicode(os.path.expandvars(path), sys.getfilesystemencoding())

def getenvu(key, default = None):
	var = os.getenv(key, default)
	return var if isinstance(var, unicode) else unicode(var, sys.getfilesystemencoding())

def putenvu(key, value):
	os.environ[key] = value.encode(sys.getfilesystemencoding())
