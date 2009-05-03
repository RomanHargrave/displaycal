#!/usr/bin/env python
# -*- coding: utf-8 -*-

import locale, os, sys

def safe_print(*args, **kwargs):
	"""
	safe_print(value, ..., pad=False, padchar=' ', sep=' ', end='\\n', 
		file=sys.stdout, fn=None)
	
	Prints the values to a stream, or to sys.stdout by default, honoring its 
	encoding and replacing characters not present in the encoding with 
	question marks silently.
	Optional keyword arguments:
	pad:     pad the lines by n chars, or os.getenv('COLUMNS') if True.
	padchar: character to use for padding, default a space.
	sep:     string inserted between values, default a space.
	end:     string appended after the last value, default a newline.
	file:    a file-like object (stream); defaults to the current sys.stdout.
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
		elif type(arg) == unicode and (file_ is not None or kwargs.get("encoding") is not None):
			arg = arg.encode(kwargs.get("encoding") or (file_.encoding if file_ not in (sys.stdout, sys.stderr) else ("UTF-8" if sys.platform == "darwin" else sys.stdout.encoding or locale.getpreferredencoding() or "ASCII")), "replace")
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
		if sys.platform != "win32" or (len(line) != 80 or file_ not in (sys.stdout,  sys.stderr) or end != "\n"):
			# On Windows, if a line is exactly the width of the buffer, 
			# a line break would insert an empty line between this line and the next.
			# To avoid this, skip the newline in that case.
			file_.write(end)

if __name__ == '__main__':
	for arg in sys.argv[1:]:
		safe_print(arg)
