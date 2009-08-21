#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import logging.handlers
import os
import re
import sys
from time import localtime, strftime

from config import logdir
from meta import name as appname
from safe_print import safe_print as _safe_print
from util_io import StringIOu as StringIO
from util_str import universal_newlines
import config

logbuffer = StringIO()

def log(msg, fn=None):
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
			import wx
		if wx.GetApp() is not None and \
		   hasattr(wx.GetApp(), "frame") and \
		   hasattr(wx.GetApp().frame, "infoframe"):
			wx.GetApp().frame.infoframe.Log(msg)


def safe_print(*args, **kwargs):
	"""
	Print and log safely, avoiding any UnicodeDe-/EncodingErrors.
	"""
	_safe_print(*args, **kwargs)
	kwargs["fn"] = log
	_safe_print(*args, **kwargs)


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
			safe_print("Warning - log directory '%s' could not be created: %s" 
					   % (logdir, str(exception)))
	if os.path.exists(logfile):
		try:
			logstat = os.stat(logfile)
		except Exception, exception:
			safe_print("Warning - os.stat('%s') failed: %s" % (logfile, 
															   str(exception)))
		else:
			# rollover needed?
			mtime = localtime(logstat.st_mtime)
			if localtime()[:3] > mtime[:3]:
				# do rollover
				logbackup = logfile + strftime(".%Y-%m-%d", mtime)
				if os.path.exists(logbackup):
					try:
						os.remove(logbackup)
					except:
						safe_print("Warning - logfile backup '%s' could not "
								   "be removed during rollover: %s" % 
								   (logbackup, str(exception)))
				try:
					os.rename(logfile, logbackup)
				except:
					safe_print("Warning - logfile '%s' could not be renamed "
							   "to '%s' during rollover: %s" % 
							   (logfile, os.path.basename(logbackup), 
							    str(exception)))
				# Adapted from Python 2.6's 
				# logging.handlers.TimedRotatingFileHandler.getFilesToDelete
				extMatch = re.compile(r"^\d{4}-\d{2}-\d{2}$")
				baseName = os.path.basename(logfile)
				try:
					fileNames = os.listdir(logdir)
				except Exception, exception:
					safe_print("Warning - log directory '%s' listing failed "
							   "during rollover: %s" % (logdir, 
														str(exception)))
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
							except:
								safe_print("Warning - logfile backup '%s' "
										   "could not be removed during "
										   "rollover: %s" % (logbackup, 
															 str(exception)))
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
			safe_print("Warning - logging to file '%s' not possible: %s" % 
					   (logfile, str(exception)))
	log("=" * 80)
	streamhandler = logging.StreamHandler(logbuffer)
	streamformatter = logging.Formatter("%(message)s")
	streamhandler.setFormatter(streamformatter)
	logger.addHandler(streamhandler)
