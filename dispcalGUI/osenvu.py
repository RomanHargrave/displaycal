#!/usr/bin/env python
# -*- coding: utf-8 -*-

import locale
import os
import sys

if sys.platform == "darwin":
    enc = "UTF-8"
else:
    enc = sys.stdout.encoding or locale.getpreferredencoding() or "ASCII"
fs_enc = sys.getfilesystemencoding() or enc

def expanduseru(path):
	return unicode(os.path.expanduser(path), fs_enc)

def expandvarsu(path):
	return unicode(os.path.expandvars(path), fs_enc)

def getenvu(key, default = None):
	var = os.getenv(key, default)
	return var if isinstance(var, unicode) else unicode(var, fs_enc)

def putenvu(key, value):
	os.environ[key] = value.encode(fs_enc)
