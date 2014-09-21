# -*- coding: utf-8 -*-

from codecs import EncodedFile
from hashlib import md5
import logging
import logging.handlers
import os
import re
import sys
from time import localtime, strftime, time

from meta import name as appname
from safe_print import SafePrinter, safe_print as _safe_print
from util_io import StringIOu as StringIO
from util_str import safe_str, safe_unicode

logging.raiseExceptions = 0

logbuffer = EncodedFile(StringIO(), "UTF-8", errors="replace")

class DummyLogger():

	def critical(self, msg, *args, **kwargs):
		pass

	def debug(self, msg, *args, **kwargs):
		pass

	def error(self, msg, *args, **kwargs):
		pass

	def exception(self, msg, *args, **kwargs):
		pass

	def info(self, msg, *args, **kwargs):
		pass

	def log(self, level, msg, *args, **kwargs):
		pass

	def warning(self, msg, *args, **kwargs):
		pass


class Log():
	
	def __call__(self, msg, fn=None):
		"""
		Log a message.
		
		Optionally use function 'fn' instead of logging.info.
		
		"""
		global logger
		msg = msg.replace("\r\n", "\n").replace("\r", "")
		if fn is None and logger.handlers:
			fn = logger.info
		if fn:
			for line in msg.split("\n"):
				fn(line)
		if "wx" in sys.modules:
			from wxaddons import wx
			if wx.GetApp() is not None and \
			   hasattr(wx.GetApp(), "frame") and \
			   hasattr(wx.GetApp().frame, "infoframe"):
				wx.CallAfter(wx.GetApp().frame.infoframe.Log, msg)
	
	def flush(self):
		pass
	
	def write(self, msg):
		self(msg.rstrip())

log = Log()


class LogFile():
	
	def __init__(self, filename, logdir):
		self._logger = get_file_logger(md5(safe_str(filename,
													"UTF-8")).hexdigest(),
									   logdir=logdir, filename=filename)
	
	def close(self):
		for handler in reversed(self._logger.handlers):
			handler.close()
			self._logger.removeHandler(handler)
	
	def flush(self):
		for handler in self._logger.handlers:
			handler.flush()

	def write(self, msg):
		for line in msg.rstrip().replace("\r\n", "\n").replace("\r", "").split("\n"):
			self._logger.info(line)


class SafeLogger(SafePrinter):
	
	"""
	Print and log safely, avoiding any UnicodeDe-/EncodingErrors on strings 
	and converting all other objects to safe string representations.
	
	"""
	
	def __init__(self, log=True, print_=hasattr(sys.stdout, "isatty") and 
										sys.stdout.isatty()):
		SafePrinter.__init__(self)
		self.log = log
		self.print_ = print_
	
	def write(self, *args, **kwargs):
		if kwargs.get("print_", self.print_):
			_safe_print(*args, **kwargs)
		if kwargs.get("log", self.log):
			kwargs.update(fn=log, encoding=None)
			_safe_print(*args, **kwargs)

safe_log = SafeLogger(print_=False)
safe_print = SafeLogger()


def get_file_logger(name, level=logging.DEBUG, when="midnight", backupCount=0,
					logdir=None, filename=None):
	global _logdir
	if logdir is None:
		logdir = _logdir
	logger = logging.getLogger(name)
	logger.propagate = 0
	logger.setLevel(level)
	if not filename:
		filename = name
	logfile = os.path.join(logdir, filename + ".log")
	for handler in logger.handlers:
		if (isinstance(handler, logging.handlers.TimedRotatingFileHandler) and
			handler.baseFilename == os.path.abspath(logfile)):
			return logger
	if not os.path.exists(logdir):
		try:
			os.makedirs(logdir)
		except Exception, exception:
			safe_print(u"Warning - log directory '%s' could not be created: %s" 
					   % tuple(safe_unicode(s) for s in (logdir, exception)))
	elif os.path.exists(logfile):
		try:
			logstat = os.stat(logfile)
		except Exception, exception:
			safe_print(u"Warning - os.stat('%s') failed: %s" % 
					   tuple(safe_unicode(s) for s in (logfile, exception)))
		else:
			# rollover needed?
			try:
				mtime = localtime(logstat.st_mtime)
			except ValueError, exception:
				# This can happen on Windows because localtime() is buggy on
				# that platform. See:
				# http://stackoverflow.com/questions/4434629/zipfile-module-in-python-runtime-problems
				# http://bugs.python.org/issue1760357
				# To overcome this problem, we ignore the real modification
				# date and force a rollover
				mtime = localtime(time() - 60 * 60 * 24)
			if localtime()[:3] > mtime[:3]:
				# do rollover
				logbackup = logfile + strftime(".%Y-%m-%d", mtime)
				if os.path.exists(logbackup):
					try:
						os.remove(logbackup)
					except Exception, exception:
						safe_print(u"Warning - logfile backup '%s' could not "
								   u"be removed during rollover: %s" % 
								   tuple(safe_unicode(s) for s in (logbackup, 
																   exception)))
				try:
					os.rename(logfile, logbackup)
				except Exception, exception:
					safe_print(u"Warning - logfile '%s' could not be renamed "
							   u"to '%s' during rollover: %s" % 
							   tuple(safe_unicode(s) for s in 
									 (logfile, os.path.basename(logbackup), 
									  exception)))
				# Adapted from Python 2.6's 
				# logging.handlers.TimedRotatingFileHandler.getFilesToDelete
				extMatch = re.compile(r"^\d{4}-\d{2}-\d{2}$")
				baseName = os.path.basename(logfile)
				try:
					fileNames = os.listdir(logdir)
				except Exception, exception:
					safe_print(u"Warning - log directory '%s' listing failed "
							   u"during rollover: %s" % 
							   tuple(safe_unicode(s) for s in (logdir, 
															   exception)))
				else:
					result = []
					prefix = baseName + "."
					plen = len(prefix)
					for fileName in fileNames:
						if fileName[:plen] == prefix:
							suffix = fileName[plen:]
							if extMatch.match(suffix):
								result.append(os.path.join(logdir, fileName))
					result.sort()
					if len(result) > backupCount:
						for logbackup in result[:len(result) - backupCount]:
							try:
								os.remove(logbackup)
							except Exception, exception:
								safe_print(u"Warning - logfile backup '%s' "
										   u"could not be removed during "
										   u"rollover: %s" % 
										   tuple(safe_unicode(s) for s in 
												 (logbackup, exception)))
	if os.path.exists(logdir):
		try:
			filehandler = logging.handlers.TimedRotatingFileHandler(logfile,
																	when=when,
																	backupCount=backupCount)
			fileformatter = logging.Formatter("%(asctime)s %(message)s")
			filehandler.setFormatter(fileformatter)
			logger.addHandler(filehandler)
		except Exception, exception:
			safe_print(u"Warning - logging to file '%s' not possible: %s" % 
					   tuple(safe_unicode(s) for s in (logfile, exception)))
	return logger


def setup_logging(logdir, name=appname):
	"""
	Setup the logging facility.
	"""
	global _logdir, logger
	_logdir = logdir
	logger = get_file_logger(name, logging.DEBUG, "midnight",
							 5 if name == appname else 0)
	streamhandler = logging.StreamHandler(logbuffer)
	streamformatter = logging.Formatter("%(message)s")
	streamhandler.setFormatter(streamformatter)
	logger.addHandler(streamhandler)
