#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import locale
import sys

if sys.platform == "darwin":
	enc = "UTF-8" 
else:
	enc = sys.stdout.encoding or locale.getpreferredencoding() or "ASCII"

def expanduseru(path):
	return unicode(os.path.expanduser(path), enc)

def expandvarsu(path):
	return unicode(os.path.expandvars(path), enc)

def getenvu(key, default = None):
	var = os.getenv(key, default)
	return var if isinstance(var, unicode) else unicode(var, enc)

def putenvu(key, value):
	os.environ[key] = value.encode(enc)
