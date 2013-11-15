# -*- coding: utf-8 -*-

import gzip
import os
import sys
from StringIO import StringIO
from time import time

from safe_print import safe_print
from util_str import universal_newlines

class Files():

	"""
	Read and/or write from/to several files at once.
	"""

	def __init__(self, files, mode="r"):
		"""
		Return a Files object.
		
		files must be a list or tuple of file objects or filenames
		(the mode parameter is only used in the latter case).
		
		"""
		self.files = []
		for item in files:
			if isinstance(item, basestring):
				self.files.append(open(item, mode))
			else:
				self.files.append(item)
	
	def __iter__(self):
		return iter(self.files)
	
	def close(self):
		for item in self.files:
			item.close()
	
	def flush(self):
		for item in self.files:
			item.flush()

	def seek(self, pos, mode=0):
		for item in self.files:
			item.seek(pos, mode)

	def truncate(self, size=None):
		for item in self.files:
			item.truncate(size)

	def write(self, data):
		for item in self.files:
			item.write(data)

	def writelines(self, str_sequence):
		self.write("".join(str_sequence))


class GzipFileProper(gzip.GzipFile):

	"""
	Proper GZIP file implementation, where the optional filename in the
	header has directory components removed, and is converted to ISO 8859-1
	(Latin-1). On Windows, the filename will also be forced to lowercase.
	
	See RFC 1952 GZIP File Format Specification	version 4.3
	
	"""

	def _write_gzip_header(self):
		self.fileobj.write('\037\213')             # magic header
		self.fileobj.write('\010')                 # compression method
		fname = os.path.basename(self.name)
		if fname.endswith(".gz"):
			fname = fname[:-3]
		elif fname.endswith(".tgz"):
			fname = "%s.tar" % fname[:-4]
		elif fname.endswith(".wrz"):
			fname = "%s.wrl" % fname[:-4]
		flags = 0
		if fname:
			flags = gzip.FNAME
		self.fileobj.write(chr(flags))
		gzip.write32u(self.fileobj, long(time()))
		self.fileobj.write('\002')
		self.fileobj.write('\377')
		if fname:
			if sys.platform == "win32":
				# Windows is case insensitive by default (although it can be
				# set to case sensitive), so according to the GZIP spec, we
				# force the name to lowercase
				fname = fname.lower()
			self.fileobj.write(fname.encode("ISO-8859-1", "replace")
							   .replace("?", "_") + '\000')

	def __enter__(self):
		return self

	def __exit__(self, type, value, tb):
		self.close()


class StringIOu(StringIO):

	"""
	StringIO which converts all new line formats in buf to POSIX newlines.
	"""

	def __init__(self, buf=''):
		StringIO.__init__(self, universal_newlines(buf))


class Tee(Files):

	"""
	Write to a file and stdout.
	"""

	def __init__(self, file_obj):
		Files.__init__((sys.stdout, file_obj))

	def __getattr__(self, name):
		return getattr(self.files[1], name)

	def close(self):
		self.files[1].close()

	def seek(self, pos, mode=0):
		return self.files[1].seek(pos, mode)

	def truncate(self, size=None):
		return self.files[1].truncate(size)
