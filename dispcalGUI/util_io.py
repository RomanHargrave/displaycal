#!/usr/bin/env python
# -*- coding: utf-8 -*-

from safe_print import safe_print

class Files():
	"""
	Read and/or write from/to several files at once.
	"""
	def __init__(self, files, mode = "r"):
		"""
		files must be a list or tuple of file objects or filenames
		(the mode parameter is only used in the latter case).
		"""
		self.files = []
		for item in files:
			if isinstance(item, (str, unicode)):
				self.files.append(open(item, mode))
			elif isinstance(item, file):
				self.files.append(item)
	def seek(self, pos):
		for item in self.files:
			item.seek(pos)
	def write(self, data):
		for item in self.files:
			item.write(data)
	def close(self):
		for item in self.files:
			item.close()

class Tea():
	def __init__(self, file_obj):
		self.file = file_obj
	def __getattr__(self, name):
		return getattr(self.file, name)
	def close(self):
		return self.file.close()
	def fileno(self):
		return self.file.fileno()
	def flush(self):
		self.file.flush()
	def issaty(self):
		return False
	def next(self):
		return self.file.next()
	def read(self):
		return self.file.read()
	def readline(self):
		return self.file.readline()
	def readlines(self):
		return self.file.readlines()
	def seek(self, offset, whence = 0):
		return self.file.seek(offset, whence)
	def tell(self):
		return self.file.tell()
	def truncate(self):
		return self.file.truncate()
	def write(self, str_val):
		self.file.write(str_val)
		if str_val[-1:] == "\n":
			str_val = str_val[:-1]
		if str_val[-1:] == "\r":
			str_val = str_val[:-1]
		safe_print(str_val)
	def writelines(self, str_sequence):
		self.write("".join(str_sequence))
