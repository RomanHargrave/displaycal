# -*- coding: utf-8 -*-

import locale
import sys

if sys.platform == "win32":
	from ctypes import windll

def get_encoding(stream):
	""" Return stream encoding. """
	enc = None
	if stream in (sys.stdin, sys.stdout, sys.stderr):
		if sys.platform == "darwin":
			# There is no way to determine it reliably under OS X 10.4?
			return "UTF-8"
		elif sys.platform == "win32":
			if sys.version_info >= (2, 6):
				# Windows/Python 2.6+: If a locale is set, the actual encoding 
				# of stdio changes, but the encoding attribute isn't updated
				enc = locale.getlocale()[1]
			if not enc:
				try:
					# GetConsoleCP and GetConsoleOutputCP return zero if
					# we're not running as console executable. Fall back
					# to GetOEMCP
					if stream is (sys.stdin):
						enc = "cp%i" % (windll.kernel32.GetConsoleCP() or
										windll.kernel32.GetOEMCP())
					else:
						enc = "cp%i" % (windll.kernel32.GetConsoleOutputCP() or
										windll.kernel32.GetOEMCP())
				except:
					pass
	enc = enc or getattr(stream, "encoding", None) or \
		  locale.getpreferredencoding() or sys.getdefaultencoding()
	return enc


def get_encodings():
	""" Return console encoding, filesystem encoding. """
	enc = get_encoding(sys.stdout)
	fs_enc = sys.getfilesystemencoding() or enc
	return enc, fs_enc
