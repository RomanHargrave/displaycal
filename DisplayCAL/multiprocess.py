# -*- coding: utf-8 -*-

from Queue import Empty
import math
import multiprocessing as mp
import multiprocessing.managers
import multiprocessing.pool
import threading


manager = None


def pool_map(func, data_in, args=(), kwds={}, num_workers=None,
			 thread_abort=None, logfile=None):
	"""
	Wrapper around multiprocessing.Pool.apply_async

	Processes data_in in slices.
	
	Progress percentage is written to optional logfile.
	Note that each subproccess is supposed to periodically put its progress
	percentage into the queue which is the first argument to 'func'.
	
	"""
	global manager

	if num_workers is None:
		num_workers = mp.cpu_count()
	num_workers = max(min(num_workers, len(data_in)), 1)

	if num_workers > 1:
		Pool = NonDaemonicPool
		if not manager:
			manager = mp.Manager()
		if thread_abort is not None and not isinstance(thread_abort.event,
													   mp.managers.EventProxy):
			# Replace the event with a managed instance that is compatible
			# with pool
			event = thread_abort.event
			thread_abort.event = manager.Event()
			if event.is_set():
				thread_abort.event.set()
		Queue = manager.Queue
	else:
		# Do it all in in the main thread of the current instance
		Pool = FakePool
		Queue = FakeQueue

	progress_queue = Queue()

	if logfile:
		def progress_logger(num_workers):
			eof_count = 0
			progress = 0
			while progress < 100 * num_workers:
				try:
					inc = progress_queue.get(True, 0.1)
					if isinstance(inc, Exception):
						raise inc
					progress += inc
				except Empty:
					continue
				except IOError:
					break
				except EOFError:
					eof_count += 1
					if eof_count == num_workers:
						break
				logfile.write("\r%i%%" % (progress / num_workers))

		threading.Thread(target=progress_logger, args=(num_workers, ),
						 name="ProcessProgressLogger").start()

	pool = Pool(num_workers)
	results = []
	start = 0
	chunksize = float(len(data_in)) / num_workers
	for i in xrange(num_workers):
		end = int(math.ceil(chunksize * (i + 1)))
		results.append(pool.apply_async(func, (data_in[start:end],
											   thread_abort.event,
											   progress_queue) + args, kwds))
		start = end
	pool.close()

	# Get results
	exception = None
	data_out = []
	for result in results:
		result = result.get()
		if isinstance(result, Exception):
			exception = result
			continue
		data_out.append(result)

	if exception:
		raise exception

	return data_out


class Mapper(object):

	"""
	Wrap 'func' with optional arguments.
	
	To be used as function argument for Pool.map
	
	"""
    
	def __init__(self, func, *args, **kwds):
		self.func = func
		self.args = args
		self.kwds = kwds

	def __call__(self, iterable):
		return self.func(iterable, *self.args, **self.kwds)


class NonDaemonicProcess(mp.Process):

	daemon = property(lambda self: False, lambda self, daemonic: None)


class NonDaemonicPool(mp.pool.Pool):

	""" Pool that has non-daemonic workers """

	Process = NonDaemonicProcess


class FakeManager(object):

	""" Fake manager """

	def Queue(self):
		return FakeQueue()

	def Value(self, typecode, *args, **kwds):
		return mp.managers.Value(typecode, *args, **kwds)

	def shutdown(self):
		pass


class FakePool(object):

	""" Fake pool """

	def __init__(self, processes=None, initializer=None, initargs=(),
				 maxtasksperchild=None):
		pass

	def apply_async(self, func, args, kwds):
		return Result(func(*args, **kwds))

	def close(self):
		pass

	def map(self, func, iterable, chunksize=None):
		return func(iterable)


class FakeQueue(object):

	""" Fake queue """

	def __init__(self):
		self.queue = []

	def get(self, block=True, timeout=None):
		try:
			return self.queue.pop()
		except:
			raise Empty

	def join(self):
		pass

	def put(self, item, block=True, timeout=None):
		self.queue.append(item)


class Result(object):

	""" Result proxy """

	def __init__(self, result):
		self.result = result

	def get(self):
		return self.result
