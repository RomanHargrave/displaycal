# -*- coding: utf-8 -*-


class Cube3DIterator(object):

	def __init__(self, size=65, start=0, end=None,
				 start_column0=0, start_column1=0, start_column2=0,
				 end_column0=None, end_column1=None, end_column2=None):
		self._size = size
		self._start = start
		self._end = end or size ** 3
		self._start_column0 = start_column0
		self._start_column1 = start_column1
		self._start_column2 = start_column2
		self._end_column0 = end_column0 or size
		self._end_column1 = end_column1 or size
		self._end_column2 = end_column2 or size
		self._len = self._end - start
		self._column0 = start_column0
		self._column1 = start_column1
		self._column2 = start_column2
		self._current = start

	# def _get_point(self, i, start=0, start_column0=0, start_column1=0, start_column2=0):
		# if i < 0:
			# i = self._len + i
		# elif i > self._len:
			# return (self._len, self._end_column0 - 1, self._end_column1 - 1, self._end_column2 - 1)
		# n = start
		# found = False
		# for column0 in xrange(start_column0, self._end_column0):
			# for column1 in xrange(start_column1, self._end_column1):
				# for column2 in xrange(start_column2, self._end_column2):
					# if n == i:
						# found = True
						# break
					# n += 1
				# if found:
					# break
			# if found:
				# break
		# return i, column0, column1, column2

	def __getitem__(self, i):
		if not self._len:
			raise IndexError("index %i out of range" % i)
		if i < 0:
			i = self._len + i
		if i + self._start != self._current:
			# Optimize for consecutive iteration speed
			if i + self._start < self._current:
				self._column0 = self._start_column0
				self._column1 = self._start_column1
				self._column2 = self._start_column2
				self._current = self._start
				start = 0
			else:
				start = self._current - self._start
			i -= start
			while i:
				self.next()
				i -= 1
		return self._column0, self._column1, self._column2
	
	def __getslice__(self, i, j):
		if i < 0:
			i = self._len + i
		if j < 0:
			j = self._len + j
		elif j > self._len:
			j = self._len
		start_column0, start_column1, start_column2 = self[i]
		end_column0, end_column1, end_column2 = self[j - 1]
		return self.__class__(self._size, i, j,
							  start_column0, start_column1, start_column2,
							  end_column0 + 1, end_column1 + 1, end_column2 + 1)

	def __len__(self):
		return self._len

	def __repr__(self):
		return (self.__class__.__name__ +
				"(size=%i, start=%i, end=%i,"
				" start_column0=%i, start_column1=%i, start_column2=%i,"
				" end_column0=%i, end_column1=%i, end_column2=%i)" %
				(self._size, self._start, self._end,
				 self._column0, self._column1, self._column2,
				 self._end_column0, self._end_column1, self._end_column2))

	def next(self):
		if self._current == self._end - 1:
			raise StopIteration
		else:
			result = self._column0, self._column1, self._column2
			if self._column2 < self._size - 1:
				self._column2 += 1
			else:
				self._column2 = 0
				if self._column1 < self._size - 1:
					self._column1 += 1
				else:
					self._column1 = 0
					self._column0 += 1
			self._current += 1
			return result
