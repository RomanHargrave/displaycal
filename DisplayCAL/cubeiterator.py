# -*- coding: utf-8 -*-


class Cube3DIterator(object):

	def __init__(self, size=65, start=0, end=None):
		self._size = size
		self._start = start
		self._len = (end or size ** 3) - start
		self._next = 0

	def get(self, i, default=None):
		if i < 0:
			i = self._len + i
		if i < 0 or i > self._len - 1:
			return default
		return self[i]

	def __getitem__(self, i):
		oi = i
		if i < 0:
			i = self._len + i
		if i < 0 or i > self._len - 1:
			raise IndexError("index %i out of range" % oi)
		i += self._start
		return (i // self._size // self._size,
				i // self._size % self._size,
				i % self._size)
	
	def __getslice__(self, i, j):
		if i < 0:
			i = self._len + i
		if j < 0:
			j = self._len + j
		elif j > self._len:
			j = self._len
		return self.__class__(self._size, self._start + i, self._start + j)

	def __len__(self):
		return self._len

	def __repr__(self):
		return (self.__class__.__name__ + "(size=%i, start=%i, end=%i)" %
				(self._size, self._start, self._start + self._len))

	def next(self):
		if self._next == self._len:
			raise StopIteration
		else:
			result = self[self._next]
			self._next += 1
			return result
