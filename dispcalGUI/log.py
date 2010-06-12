#!/usr/bin/env python
# -*- coding: utf-8 -*-

from codecs import EncodedFile
import logging
import logging.handlers
import os
import re
import sys
from time import localtime, strftime

from config import logdir
from meta import name as appname
from safe_print import SafePrinter, safe_print as _safe_print
from util_io import StringIOu as StringIO
from util_str import safe_unicode, universal_newlines
import config

logbuffer = EncodedFile(StringIO(), "UTF-8", errors="replace")

class Log():
	
	def __call__(self, msg, fn=None):
		"""
		Log a message.
		
		Optionally use function 'fn' instead of logging.info.
		
		"""
		if fn is None and logging.root.handlers:
			fn = logging.info
		if fn:
			for line in universal_newlines(msg).split("\n"):
				fn(line)
		if "wx" in sys.modules:
			if not "wx" in globals():
				global wx
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


def setup_logging():
	"""
	Setup the logging facility.
	"""
	logfile = os.path.join(logdir, appname + ".log")
	backupCount = 5
	if not os.path.exists(logdir):
		try:
			os.makedirs(logdir)
		except Exception, exception:
			safe_print(u"Warning - log directory '%s' could not be created: %s" 
					   % tuple(safe_unicode(s) for s in (logdir, exception)))
	if os.path.exists(logfile):
		try:
			logstat = os.stat(logfile)
		except Exception, exception:
			safe_print(u"Warning - os.stat('%s') failed: %s" % 
					   tuple(safe_unicode(s) for s in (logfile, exception)))
		else:
			# rollover needed?
			mtime = localtime(logstat.st_mtime)
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
	logger = logging.getLogger()
	logger.setLevel(logging.DEBUG)
	if os.path.exists(logdir):
		try:
			filehandler = logging.handlers.TimedRotatingFileHandler(logfile, 
				when = "midnight", backupCount = backupCount)
			fileformatter = logging.Formatter("%(asctime)s %(message)s")
			filehandler.setFormatter(fileformatter)
			logger.addHandler(filehandler)
		except Exception, exception:
			safe_print(u"Warning - logging to file '%s' not possible: %s" % 
					   tuple(safe_unicode(s) for s in (logfile, exception)))
	log("=" * 80)
	streamhandler = logging.StreamHandler(logbuffer)
	streamformatter = logging.Formatter("%(message)s")
	streamhandler.setFormatter(streamformatter)
	logger.addHandler(streamhandler)
