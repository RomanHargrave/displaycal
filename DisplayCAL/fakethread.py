# -*- coding: utf-8 -*-

from Queue import Empty

fake_threads = []


class FakeQueue(object):

	""" Fake queue class. """

	def __init__(self):
		self.queue = []

	def close(self):
		pass

	def get(self, block=True, timeout=None):
		try:
			return self.queue.pop()
		except:
			raise Empty

	def join_thread(self):
		pass

	def put(self, item, block=True, timeout=None):
		self.queue.append(item)


class FakeThread(object):

	""" Fake thread class. """

	def __init__(self, target, args=(), name=None):
		self.target = target
		self.args = args
		self.name = name or "FakeThread-%i" % len(fake_threads)
		fake_threads.append(self)

	def is_alive(self):
		return False

	def start(self):
		self.target(*self.args)

	def terminate(self):
		pass
