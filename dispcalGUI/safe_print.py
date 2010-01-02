#!/usr/bin/env python
# -*- coding: utf-8 -*-

import locale
import os
import sys

def safe_print(*args, **kwargs):
	"""
	Print safely, avoiding any UnicodeDe-/EncodingErrors.
	
	safe_print(value, ..., pad=False, padchar=' ', sep=' ', end='\\n', 
			   file=sys.stdout, fn=None)
	
	Prints the values to a stream, or to sys.stdout (default), honoring its 
	encoding and replacing characters not present in the encoding with 
	question marks silently.
	
	Optional keyword arguments:
	pad:     pad the lines to n chars, or os.getenv('COLUMNS') if True.
	padchar: character to use for padding, default a space.
	sep:     string inserted between values, default a space.
	end:     string appended after the last value, default a newline.
	file:    a file-like object (stream); defaults to the sys.stdout.
	fn:      a function to execute instead of printing.
	"""
	if "pad" in kwargs:
		pad = kwargs["pad"]
	else:
		pad = False
	if "padchar" in kwargs:
		padchar = kwargs["padchar"]
	else:
		padchar = " "
	if "sep" in kwargs:
		sep = kwargs["sep"]
	else:
		sep = " "
	if "end" in kwargs:
		end = kwargs["end"]
	else:
		end = "\n"
	if "file" in kwargs:
		file_ = kwargs["file"]
	elif kwargs.get("fn") is None:
		file_ = sys.stdout
	else:
		file_ = None
	strargs = []
	for arg in args:
		if type(arg) not in (str, unicode):
			arg = str(arg)
		elif type(arg) == unicode and (file_ is not None or 
									   kwargs.get("encoding") is not None):
			if kwargs.get("encoding"):
				encoding = kwargs["encoding"]
			elif file_ not in (sys.stdout, sys.stderr) and \
				 hasattr(file_, "encoding") and file_.encoding:
				encoding = file_.encoding
			elif sys.platform == "darwin":
				encoding = "UTF-8"
			elif sys.stdout.encoding:
				encoding = sys.stdout.encoding
			else:
				encoding = locale.getpreferredencoding() or \
						   sys.getdefaultencoding()
			arg = arg.encode(encoding, "replace")
		strargs += [arg]
	line = sep.join(strargs)
	if pad is not False:
		if pad is True:
			try:
				width = int(os.getenv("COLUMNS"))
			except (TypeError, ValueError):
				width = 80
		else:
			width = int(pad)
		line = line.ljust(width, padchar)
	if "fn" in kwargs and hasattr(kwargs["fn"],  "__call__"):
		kwargs["fn"](line)
	else:
		file_.write(line)
		if sys.platform != "win32" or len(line) != 80 or file_ not in \
		   (sys.stdout,  sys.stderr) or end != "\n":
			# On Windows, if a line is exactly the width of the buffer, a line 
			# break would insert an empty line between this line and the next.
			# To avoid this, skip the newline in that case.
			file_.write(end)

if __name__ == '__main__':
	
	if sys.platform == "darwin":
		enc = "UTF-8"
	else:
		enc = sys.stdout.encoding or locale.getpreferredencoding() or \
			  sys.getdefaultencoding()
	fs_enc = sys.getfilesystemencoding() or enc
	for arg in sys.argv[1:]:
		safe_print(arg.decode(fs_enc))
