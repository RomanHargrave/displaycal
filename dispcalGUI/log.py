# -*- coding: utf-8 -*-

from codecs import EncodedFile
from hashlib import md5
import logging
import logging.handlers
import os
import re
import sys
import warnings
from time import localtime, strftime, time

from meta import name as appname
from options import debug
from safe_print import SafePrinter, safe_print as _safe_print
from util_io import StringIOu as StringIO
from util_str import safe_str, safe_unicode

logging.raiseExceptions = 0

logging._warnings_showwarning = warnings.showwarning

if debug:
	loglevel = logging.DEBUG
else:
	loglevel = logging.INFO

logger = None


def showwarning(message, category, filename, lineno, file=None, line=""):
	"""
	Implementation of showwarnings which redirects to logging, which will first
	check to see if the file parameter is None. If a file is specified, it will
	delegate to the original warnings implementation of showwarning. Otherwise,
	it will call warnings.formatwarning and will log the resulting string to a
	warnings logger named "py.warnings" with level logging.WARNING.
	
	UNlike the default implementation, the line is omitted from the warning,
	and the warning does not end with a newline.
	"""
	if file is not None:
		if logging._warnings_showwarning is not None:
			logging._warnings_showwarning(message, category, filename, lineno,
										  file, line)
	else:
		s = warnings.formatwarning(message, category, filename, lineno, line)
		logger = logging.getLogger("py.warnings")
		if not logger.handlers:
			if hasattr(sys.stderr, "isatty") and sys.stderr.isatty():
				handler = logging.StreamHandler()
			else:
				handler = logging.NullHandler()
			logger.addHandler(handler)
		logger.warning("%s", s.strip())

warnings.showwarning = showwarning

logbuffer = EncodedFile(StringIO(), "UTF-8", errors="replace")


def wx_log(logwindow):
	if logwindow.IsShownOnScreen():
		logbuffer.seek(0)
		logwindow.Log(logbuffer.read().rstrip().decode("UTF-8", "replace"))
		logbuffer.truncate(0)


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
		if fn is None and logger and logger.handlers:
			fn = logger.info
		if fn:
			for line in msg.split("\n"):
				fn(line)
		if "wx" in sys.modules:
			from wxaddons import wx
			if wx.GetApp() is not None and \
			   hasattr(wx.GetApp(), "frame") and \
			   hasattr(wx.GetApp().frame, "infoframe"):
				wx.CallAfter(wx_log, wx.GetApp().frame.infoframe)
	
	def flush(self):
		pass
	
	def write(self, msg):
		self(msg.rstrip())

log = Log()


class LogFile():
	
	""" Logfile class. Default is to not rotate. """
	
	def __init__(self, filename, logdir, when="never", backupCount=0):
		self._logger = get_file_logger(md5(safe_str(filename,
													"UTF-8")).hexdigest(),
									   when=when, backupCount=backupCount,
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


def get_file_logger(name, level=loglevel, when="midnight", backupCount=5,
					logdir=None, filename=None):
	""" Return logger object.
	
	A TimedRotatingFileHandler (if when == "never") or FileHandler will be used.
	
	"""
	global _logdir
	if logdir is None:
		logdir = _logdir
	logger = logging.getLogger(name)
	if not filename:
		filename = name
	logfile = os.path.join(logdir, filename + ".log")
	for handler in logger.handlers:
		if (isinstance(handler, logging.FileHandler) and
			handler.baseFilename == os.path.abspath(logfile)):
			return logger
	logger.propagate = 0
	logger.setLevel(level)
	if not os.path.exists(logdir):
		try:
			os.makedirs(logdir)
		except Exception, exception:
			safe_print(u"Warning - log directory '%s' could not be created: %s" 
					   % tuple(safe_unicode(s) for s in (logdir, exception)))
	elif when != "never" and os.path.exists(logfile):
		try:
			logstat = os.stat(logfile)
		except Exception, exception:
			safe_print(u"Warning - os.stat('%s') failed: %s" % 
					   tuple(safe_unicode(s) for s in (logfile, exception)))
		else:
			# rollover needed?
			t = logstat.st_mtime
			try:
				mtime = localtime(t)
			except ValueError, exception:
				# This can happen on Windows because localtime() is buggy on
				# that platform. See:
				# http://stackoverflow.com/questions/4434629/zipfile-module-in-python-runtime-problems
				# http://bugs.python.org/issue1760357
				# To overcome this problem, we ignore the real modification
				# date and force a rollover
				t = time() - 60 * 60 * 24
				mtime = localtime(t)
			# Deal with DST
			now = localtime()
			dstNow = now[-1]
			dstThen = mtime[-1]
			if dstNow != dstThen:
				if dstNow:
					addend = 3600
				else:
					addend = -3600
				mtime = localtime(t + addend)
			if now[:3] > mtime[:3]:
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
			if when != "never":
				filehandler = logging.handlers.TimedRotatingFileHandler(logfile,
																		when=when,
																		backupCount=backupCount)
			else:
				filehandler = logging.FileHandler(logfile)
			fileformatter = logging.Formatter("%(asctime)s %(message)s")
			filehandler.setFormatter(fileformatter)
			logger.addHandler(filehandler)
		except Exception, exception:
			safe_print(u"Warning - logging to file '%s' not possible: %s" % 
					   tuple(safe_unicode(s) for s in (logfile, exception)))
	return logger


def setup_logging(logdir, name=appname, backupCount=5):
	"""
	Setup the logging facility.
	"""
	global _logdir, logger
	_logdir = logdir
	if name.startswith(appname):
		logger = get_file_logger(None, loglevel, "midnight",
								 backupCount, filename=name)
		streamhandler = logging.StreamHandler(logbuffer)
		streamformatter = logging.Formatter("%(asctime)s %(message)s")
		streamhandler.setFormatter(streamformatter)
		logger.addHandler(streamhandler)
