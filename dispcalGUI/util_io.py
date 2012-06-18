# -*- coding: utf-8 -*-

from StringIO import StringIO

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
