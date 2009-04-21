#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
dispcalGUI

A graphical user interface for the Argyll CMS display calibration utilities

Copyright (C) 2008, 2009 Florian Hoech

This program is free software; you can redistribute it and/or modify it 
under the terms of the GNU General Public License as published by the 
Free Software Foundation; either version 3 of the License, or (at your 
option) any later version.

This program is distributed in the hope that it will be useful, but 
WITHOUT ANY WARRANTY; without even the implied warranty of 
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU 
General Public License for more details.

You should have received a copy of the GNU General Public License along 
with this program; if not, see <http://www.gnu.org/licenses/>
"""

# version check
import sys
pyver = map(int, sys.version.split()[0].split("."))
if pyver < [2, 5] or pyver >= [3]:
	raise RuntimeError("Need Python version >= 2.5 < 3.0, got %s" % 
	   ".".join(pyver))

# standard modules
import ConfigParser
ConfigParser.DEFAULTSECT = "Default"
import codecs
import decimal
from distutils.sysconfig import get_python_lib
import getpass
import locale
import logging
import logging.handlers
import math
import os
import random
import re
import shutil26 as shutil
import subprocess26 as sp
import tempfile26 as tempfile
import textwrap
import traceback
Decimal = decimal.Decimal
from StringIOu import StringIOu as StringIO, universal_newlines
from thread import start_new_thread
from time import gmtime, localtime, sleep, strftime, time, timezone

# 3rd party modules
import demjson
import wx
import wx.grid
import wx.lib.delayedresult as delayedresult
import wx.lib.hyperlink

# custom modules
import CGATS
import ICCProfile
ICCP = ICCProfile
import RealDisplaySizeMM as RDSMM
from argyllRGB2XYZ import argyllRGB2XYZ
from argyll_instruments import instruments
from colormath import CIEDCCT2xyY, xyY2CCT, XYZ2CCT, XYZ2RGB, XYZ2xyY
from natsort import natsort
import pyi_md5pickuphelper
from safe_print import safe_print as _safe_print
from trash import trash

# helper functions
def indexi(self, value, start = None, stop = None):
	items = [(item.lower() if isinstance(item, (str, unicode)) else item) for item in self]
	args = [value.lower()]
	if start is not None:
		args += [start]
	if stop is not None:
		args += [stop]
	return items.index(*args)

def asciize(exception):
	chars = {
		u"\u00a9": u"(C)", # U+00A9 copyright sign
		u"\u00ae": u"(R)", # U+00AE registered sign
		u"\u00b2": u"2", # U+00B2 superscript two
		u"\u00b3": u"3", # U+00B3 superscript three
		u"\u00b9": u"1", # U+00B9 superscript one
		u"\u00d7": u"x", # U+00D7 multiplication sign
		u"\u2013": u"-", # U+2013 en dash
		u"\u2014": u"-", # U+2014 em dash
		u"\u2015": u"-", # U+2015 horizontal bar
		u"\u2026": u"...", # U+2026 ellipsis
		u"\u2212": u"-", # U+2212 minus sign
	}
	return chars.get(exception.object[exception.start:exception.end], u"_"), exception.end

codecs.register_error("asciize", asciize)

# init
appname = "dispcalGUI"
version = "v0.2.2b" # app version string

isexe = sys.platform != "darwin" and hasattr(sys, "frozen") and sys.frozen

if isexe:
	pypath = os.path.abspath(sys.executable)
else:
	pypath = os.path.abspath(__file__)

pydir = os.path.dirname(pypath)

pyname, pyext = os.path.splitext(os.path.basename(pypath))
exedir = os.path.dirname(sys.executable)
isapp = sys.platform == "darwin" and \
   sys.executable.split(os.path.sep)[-3:-1] == ["Contents", "MacOS"] and \
   os.path.isfile(os.path.join(exedir, pyname))

if isexe and os.getenv("_MEIPASS2"):
	os.environ["_MEIPASS2"] = os.getenv("_MEIPASS2").replace("/", os.path.sep)

data_dirs = [os.getcwdu()] if not isexe or os.getcwdu() != pydir else []
if sys.platform == "win32":
	from SendKeys import SendKeys
	from win32com.shell import shell, shellcon
	import _winreg
	import pythoncom
	import win32con
	btn_width_correction = 20
	cmdfile_ext = ".cmd"
	scale_adjustment_factor = 1.0
	# environment variable APPDATA will not be defined if using "Run as..."
	appdata = shell.SHGetSpecialFolderPath(0, shellcon.CSIDL_APPDATA)
	commonappdata = shell.SHGetSpecialFolderPath(0, shellcon.CSIDL_COMMON_APPDATA)
	commonprogramfiles = shell.SHGetSpecialFolderPath(0, shellcon.CSIDL_PROGRAM_FILES_COMMON)
	confighome = os.path.join(appdata, appname)
	autostart = shell.SHGetSpecialFolderPath(0, shellcon.CSIDL_COMMON_STARTUP)
	autostart_home = shell.SHGetSpecialFolderPath(0, shellcon.CSIDL_STARTUP)
	datahome = os.path.join(appdata, appname)
	data_dirs += [datahome, os.path.join(commonappdata, appname), 
				  os.path.join(commonprogramfiles, appname)]
	iccprofiles_home = iccprofiles = os.path.join(shell.SHGetSpecialFolderPath(0, 
		shellcon.CSIDL_SYSTEM), "spool", "drivers", "color")
	exe_ext = ".exe"
	profile_ext = ".icm"
else:
	btn_width_correction = 10
	if sys.platform == "darwin":
		try:
			import appscript
		except ImportError: # we can fall back to osascript shell command
			appscript = None
		cmdfile_ext = ".command"
		mac_create_app = True
		scale_adjustment_factor = 1.0
		confighome = datahome = os.path.join(os.path.expanduser("~"), "Library", 
			"Application Support", appname)
		data_dirs += [datahome, os.path.join(os.path.sep, "Library", 
			"Application Support", appname)]
		iccprofiles = os.path.join(os.path.sep, "Library", 
			"ColorSync", "Profiles")
		iccprofiles_home = os.path.join(os.path.expanduser("~"), "Library", 
			"ColorSync", "Profiles")
	else:
		cmdfile_ext = ".sh"
		scale_adjustment_factor = 1.0
		xdg_config_home = os.getenv("XDG_CONFIG_HOME",
		   os.path.join(os.path.expanduser("~"), ".config"))
		xdg_config_dirs = os.getenv("XDG_CONFIG_DIRS", "/etc/xdg").split(os.pathsep)
		xdg_data_home = os.getenv("XDG_DATA_HOME",
		   os.path.join(os.path.expanduser("~"), ".local", "share"))
		xdg_data_dirs = os.getenv(
			"XDG_DATA_DIRS", os.pathsep.join((os.path.join("usr", "local", 
			"share"), os.path.join("usr", "share")))
			).split(os.pathsep)
		confighome = os.path.join(xdg_config_home, appname)
		autostart = os.path.join(xdg_config_dirs[0], "autostart")
		autostart_home = os.path.join(xdg_config_home, "autostart")
		datahome = os.path.join(xdg_data_home, appname)
		data_dirs += [datahome]
		data_dirs += [os.path.join(dir_, appname) for dir_ in xdg_data_dirs]
		data_dirs += [os.path.join(get_python_lib(plat_specific = True), appname)]
		iccprofiles = os.path.join(xdg_data_dirs[0], "color", "icc", 
			"devices", "display")
		iccprofiles_home = os.path.join(xdg_data_home, "color", "icc", 
			"devices", "display")
	exe_ext = ""
	profile_ext = ".icc"
data_dirs += [os.path.join(get_python_lib(), appname)]
if isapp:
	data_dirs += [os.path.join(pydir, "..", "..", "..")]
	runtype = ".app"
else:
	if (os.getenv("_MEIPASS2", pydir) if isexe else pydir) not in data_dirs:
		data_dirs += [os.getenv("_MEIPASS2", pydir) if isexe else pydir]
	if isexe:
		runtype = exe_ext
	else:
		runtype = ".py"
storage = os.path.join(datahome, "storage")
if "--ascii" in sys.argv[1:]:
	enc = fs_enc = "ASCII"
else:
	enc = "UTF-8" if sys.platform == "darwin" else sys.stdout.encoding or \
	   locale.getpreferredencoding() or "ASCII"
	fs_enc = sys.getfilesystemencoding() or enc

if "-d2" in sys.argv[1:] or "--debug=2" in sys.argv[1:]:
	debug = 2
elif "-d1" in sys.argv[1:] or "--debug=1" in sys.argv[1:] or \
	 "-d" in sys.argv[1:] or "--debug" in sys.argv[1:]:
	debug = 1
else:
	debug = 0 # >= 1 prints debug messages
test = "-t" in sys.argv[1:] or "--test" in sys.argv[1:] # aid testing new features
if "-v2" in sys.argv[1:] or "--verbose=2" in sys.argv[1:]:
	verbose = 2
elif "-v0" in sys.argv[1:] or "--verbose=0" in sys.argv[1:]:
	verbose = 0
else:
	verbose = 1 # >= 1 prints some status information
tc_use_alternate_preview = "-ap" in sys.argv[1:]
build = "%s%s%s" % (
		strftime("%Y-%m-%dT%H:%M:%S", gmtime(os.stat(pypath).st_mtime)), 
		"+" if str(timezone)[0] == "-" else "-", 
		strftime("%H:%M", gmtime(abs(timezone)))
	) if pypath and os.path.exists(pypath) else ""
resfiles = [
	"lang/en.json",
	"theme/header.png",
	"theme/header-about.png",
	"theme/icons/32x32/zoom-best-fit.png",
	"theme/icons/32x32/zoom-in.png",
	"theme/icons/32x32/zoom-original.png",
	"theme/icons/32x32/zoom-out.png",
	"theme/icons/32x32/dialog-error.png",
	"theme/icons/32x32/dialog-information.png",
	"theme/icons/32x32/dialog-question.png",
	"theme/icons/32x32/dialog-warning.png",
	"theme/icons/32x32/window-center.png",
	"theme/icons/16x16/dialog-information.png",
	# "theme/icons/16x16/dialog-warning.png",
	"theme/icons/16x16/document-open.png",
	"theme/icons/16x16/edit-delete.png",
	"theme/icons/16x16/install.png",
	"theme/icons/16x16/media-floppy.png",
	"theme/icons/16x16/%s.png" % appname,
	"theme/icons/16x16/rgbsquares.png",
	"theme/icons/16x16/stock_lock.png",
	"theme/icons/16x16/stock_lock-open.png",
	# "theme/icons/16x16/stock_refresh.png",
	"ti1/d3-e4-s0-g16-m4-f0-crossover.ti1",
	"ti1/d3-e4-s0-g52-m4-f0-crossover.ti1",
	"ti1/d3-e4-s0-g52-m4-f500-crossover.ti1",
	"ti1/d3-e4-s0-g52-m4-f3000-crossover.ti1",
	"test.cal"
]

globalconfig = {
	"app": None,
	"log": StringIO()
}

def get_data_path(relpath, rex = None):
	""" return full path as string for files and a list of files in the 
	intersection of searched directories for dirs """
	intersection = []
	paths = []
	for dir_ in data_dirs:
		curpath = os.path.join(dir_, relpath)
		if os.path.exists(curpath):
			if os.path.isdir(curpath):
				try:
					filelist = listdir(curpath, rex)
				except Exception, exception:
					if debug: safe_print("Error - directory '%s' listing failed: %s" % (curpath, str(exception)))
				else:
					for filename in filelist:
						if not filename in intersection:
							intersection += [filename]
							paths += [os.path.join(curpath, filename)]
			else:
				return curpath
	return None if len(paths) == 0 else paths

def get_w3c_dtf_timestamp(time_ = None, timezone_ = None):
	if time_ is None:
		time_ = gmtime()
	if timezone_ is None:
		timezone_ = timezone
	return strftime("%Y-%m-%dT%H:%M:%S", time_) + \
	   ("+" if str(timezone_)[0] == "-" else "-") + \
	   strftime("%H:%M", gmtime(abs(timezone_)))

def log(msg, fn = None):
	if fn is None and logging.root.handlers:
		fn = logging.info
	if fn:
		for line in universal_newlines(msg).split("\n"):
			fn(line)
	if globalconfig["app"] is not None and \
	   hasattr(globalconfig["app"], "frame") and \
	   hasattr(globalconfig["app"].frame, "infoframe"):
	   globalconfig["app"].frame.info_print(msg)

def setup_logging():
	logdir = os.path.join(datahome, "logs")
	logfile = os.path.join(logdir, appname + ".log")
	backupCount = 5
	if not os.path.exists(logdir):
		try:
			os.makedirs(logdir)
		except Exception, exception:
			safe_print("Warning - log directory '%s' could not be created: %s" % (logdir, str(exception)))
	if os.path.exists(logfile):
		try:
			logstat = os.stat(logfile)
		except Exception, exception:
			safe_print("Warning - os.stat('%s') failed: %s" % (logfile, str(exception)))
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
						safe_print("Warning - logfile backup '%s' could not be removed during rollover: %s" % (logbackup, str(exception)))
				try:
					os.rename(logfile, logbackup)
				except:
					safe_print("Warning - logfile '%s' could not be renamed to '%s' during rollover: %s" % (logfile, os.path.basename(logbackup), str(exception)))
				# adapted from Python 2.6 
				# logging.handlers.TimedRotatingFileHandler.getFilesToDelete
				extMatch = re.compile(r"^\d{4}-\d{2}-\d{2}$")
				baseName = os.path.basename(logfile)
				try:
					fileNames = os.listdir(logdir)
				except Exception, exception:
					safe_print("Warning - log directory '%s' listing failed during rollover: %s" % (logdir, str(exception)))
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
								safe_print("Warning - logfile backup '%s' could not be removed during rollover: %s" % (logbackup, str(exception)))
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
			safe_print("Warning - logging to file '%s' not possible: %s" % (logfile, str(exception)))
	log("=" * 80)
	streamhandler = globalconfig["logging.StreamHandler"] = \
	   logging.StreamHandler(globalconfig["log"])
	streamformatter = logging.Formatter("%(message)s")
	streamhandler.setFormatter(streamformatter)
	logger.addHandler(streamhandler)

def safe_print(*args, **kwargs):
	_safe_print(*args, **kwargs)
	kwargs["fn"] = log
	_safe_print(*args, **kwargs)

def handle_error(errstr, parent = None, silent = False):
	safe_print(errstr)
	if not silent:
		try:
			if globalconfig["app"] is None and parent is None:
				app = wx.App(redirect = False)
			dlg = wx.MessageDialog(parent if parent not in (False, None) and 
				parent.IsShownOnScreen() else None, errstr if type(errstr) == 
				unicode else unicode(errstr, enc, "replace"), appname, wx.OK | 
				wx.ICON_ERROR)
			dlg.ShowModal()
			dlg.Destroy()
		except Exception, exception:
			safe_print("Warning: handle_error():", str(exception))

def _excepthook(type, value, tb):
	handle_error("".join(traceback.format_exception(type, value, tb)))

sys.excepthook = _excepthook

ldict = {} # language strings dictionary (will be auto-populated)

def init_languages():
	langdirs = []
	for dir_ in data_dirs:
		langdirs += [os.path.join(dir_, "lang")]
	for langdir in langdirs:
		if os.path.exists(langdir) and os.path.isdir(langdir):
			try:
				langfiles = os.listdir(langdir)
			except Exception, exception:
				safe_print("Warning - directory '%s' listing failed: %s" % (langdir, str(exception)))
			else:
				for filename in langfiles:
					name, ext = os.path.splitext(filename)
					if ext.lower() == ".json" and name.lower() not in ldict:
						langfilename = os.path.join(langdir, filename)
						try:
							langfile = open(langfilename, "rU")
							try:
								ltxt = unicode(langfile.read(), "UTF-8")
								ldict[name.lower()] = demjson.decode(ltxt)
							except (UnicodeDecodeError, demjson.JSONDecodeError), \
							   exception:
								handle_error("Warning - language file '%s': %s" % 
									(langfilename, 
									exception.args[0].capitalize() if type(exception) == 
									demjson.JSONDecodeError else 
									str(exception))
									)
						except Exception, exception:
							handle_error("Warning - language file '%s': %s" % 
								(langfilename, str(exception)))
						else:
							langfile.close()
	if len(ldict) == 0:
		handle_error("Warning: No valid language files found. The following "
			"places have been searched:\n%s" % "\n".join(langdirs))



# debugging helpers BEGIN

if debug:

	wxEventTypes = {}

	def getWxEventTypes():
		try:
			for name in dir(wx):
				if name.find("EVT_") == 0:
					attr = getattr(wx, name)
					if hasattr(attr, "typeId"):
						wxEventTypes[attr.typeId] = name
		except Exception, exception:
			pass

	getWxEventTypes()

	def getevttype(event):
		typeId = event.GetEventType()
		if typeId in wxEventTypes:
			return wxEventTypes[typeId]

	def getevtobjname(event, window = None):
		try:
			event_object = event.GetEventObject()
			if not event_object and window:
				event_object = window.FindWindowById(event.GetId())
			if event_object and hasattr(event_object, "GetName"):
				return event_object.GetName()
		except Exception, exception:
			pass

# debugging helpers END



def get_ti1_1(cgats):
	required = ("SAMPLE_ID", "RGB_R", "RGB_B", "RGB_G", "XYZ_X", "XYZ_Y", 
		"XYZ_Z")
	ti1_1 = cgats.queryi1(required)
	if ti1_1 and ti1_1.parent and ti1_1.parent.parent:
		ti1_1 = ti1_1.parent.parent
		if ti1_1.queryv1("NUMBER_OF_SETS"):
			if ti1_1.queryv1("DATA_FORMAT"):
				for field in required:
					if not field in ti1_1.queryv1("DATA_FORMAT").values():
						if verbose >= 2: safe_print("Missing required field:", 
							field)
						return None
				for field in ti1_1.queryv1("DATA_FORMAT").values():
					if not field in required:
						if verbose >= 2: safe_print("Unknown field:", field)
						return None
			else:
				if verbose >= 2: safe_print("Missing DATA_FORMAT")
				return None
		else:
			if verbose >= 2: safe_print("Missing DATA")
			return None
		ti1_1.filename = cgats.filename
		return ti1_1
	else:
		if verbose >= 2: safe_print("Invalid TI1")
		return None

cals = {}
def can_update_cal(path):
	try:
		calstat = os.stat(path)
	except Exception, exception:
		safe_print("Warning - os.stat('%s') failed: %s" % (path, str(exception)))
	if not path in cals or cals[path].mtime != calstat.st_mtime:
		try:
			cal = CGATS.CGATS(path)
		except (IOError, CGATS.CGATSInvalidError, 
			CGATS.CGATSInvalidOperationError, CGATS.CGATSKeyError, 
			CGATS.CGATSTypeError, CGATS.CGATSValueError), exception:
			cals[path] = False
			safe_print("Warning - couldn't process CGATS file '%s': %s" % (path, str(exception)))
		else:
			cals[path] = cal.queryv1("DEVICE_TYPE") in ("CRT", "LCD") and \
			   not None in (cal.queryv1("TARGET_WHITE_XYZ"), 
			   cal.queryv1("TARGET_GAMMA"), 
			   cal.queryv1("BLACK_POINT_CORRECTION"), 
			   cal.queryv1("QUALITY"))
	return cals[path]

def listdir(path, rex = None):
	files = os.listdir(path)
	if rex:
		rex = re.compile(rex, re.IGNORECASE)
		files = filter(rex.search, files)
	return files

def floatlist(alist):
	result = []
	for item in alist:
		try:
			result.append(float(item))
		except ValueError:
			result.append(0.0)
	return result

def strlist(alist):
	return [str(item) for item in alist]

def extract_cal(ti3_data):
	if isinstance(ti3_data, (str, unicode)):
		ti3 = StringIO(ti3_data)
	else:
		ti3 = ti3_data
	cal = False
	cal_lines = []
	for line in ti3:
		line = line.strip()
		if line == "CAL":
			line = "CAL    " # Make sure CGATS file identifiers are always a minimum of 7 characters
			cal = True
		if cal:
			cal_lines += [line]
			if line == 'END_DATA':
				break
	if isinstance(ti3, file):
		ti3.close()
	return "\n".join(cal_lines)

def ti3_to_ti1(ti3_data):
	if isinstance(ti3_data, (str, unicode)):
		ti3 = StringIO(ti3_data)
	else:
		ti3 = ti3_data
	ti1_lines = []
	for line in ti3:
		line = line.strip()
		if line == "CTI3":
			line = 'CTI1   ' # Make sure CGATS file identifiers are always a minimum of 7 characters
		else:
			values = line.split()
			if len(values) > 1:
				if len(values) == 2:
					values[1] = values[1].strip('"')
					if values[0] == "DESCRIPTOR":
						values[1] = ("Argyll Calibration Target chart "
							"information 1")
					elif values[0] == "ORIGINATOR":
						values[1] = "Argyll targen"
					elif values[0] == "COLOR_REP":
						values[1] = values[1].split('_')[0]
				if "DEVICE_CLASS" in values or "LUMINANCE_XYZ_CDM2" in values:
					continue
				if len(values) > 2:
					line = " ".join(values)
				else:
					line = '%s "%s"' % tuple(values)
		ti1_lines += [line]
		if line == 'END_DATA':
			break
	if isinstance(ti3, file):
		ti3.close()
	return "\n".join(ti1_lines)

def get_display(window):
	display_no = wx.Display.GetFromWindow(window)
	if display_no < 0: # window outside visible area
		display_no = 0
	return wx.Display(display_no)

def set_position(window, x = None, y = None, w = None, h = None):
	if not None in (x, y):
		# first, move to coordinates given
		window.SetPosition((x, y)) 
	# returns the first display's client area if the window 
	# is completely outside the client area of all displays
	display_client_rect = get_display(window).ClientArea 
	if sys.platform not in ("darwin", "win32"): # Linux
		safety_margin = 45
	else:
		safety_margin = 20
	if not None in (w, h):
		# set given size, but resize if needed to fit inside client area
		window.SetSize((min(display_client_rect[2] - safety_margin, w), 
			min(display_client_rect[3] - safety_margin, h))) 
	if not None in (x, y):
		if not display_client_rect.ContainsXY(x, y) or \
		   not display_client_rect.ContainsRect((x, y, 100, 100)):
			# if outside client area or near the borders,
			# move to leftmost / topmost coordinates of client area
			window.SetPosition(display_client_rect[0:2]) 

def which(name):
	path = os.getenv("PATH", os.defpath)
	for cur_dir in path.split(os.pathsep):
		filename = os.path.join(cur_dir, name)
		if os.path.isfile(filename):
			try:
				if os.access(filename, os.X_OK):
					return filename
			except Exception, exception:
				pass
	return None

def get_sudo():
	# for name in ["gnomesu", "kdesu", "gksu", "sudo"]:
		# if which(name):
			# return name
	return which("sudo")

def putenv(varname, value):
	os.environ[varname] = value

def escargs(args):
	args_out = []
	for arg in args:
		if re.search("[\^!$%&()[\]\s]", arg):
			arg = '"' + arg + '"'
		args_out += [arg]
	return args_out

def printcmdline(cmd, args = None, fn = None, cwd = None):
	if args is None:
		args = []
	if cwd is None:
		cwd = os.getcwdu()
	safe_print("  " + cmd, fn = fn)
	i = 0
	lines = []
	for item in args:
		ispath = False
		if item.find(os.path.sep) > -1:
			if os.path.dirname(item) == cwd:
				item = os.path.basename(item)
			ispath = True
		if re.search("[\^!$%&()[\]\s]", item):
			item = '"' + item + '"'
		if item[0] != "-" and len(lines) and i < len(args) - 1:
			lines[-1] += "\n      " + item
		else:
			lines.append(item)
		i += 1
	for line in lines:
		safe_print(textwrap.fill(line, 80, expand_tabs = False, 
			replace_whitespace = False, initial_indent = "    ", 
			subsequent_indent = "      "), fn = fn)

def stripzeroes(n):
	try:
		Decimal(str(n))
		n = str(n)
		if n.find(".") < 0:
			n += "."
		return Decimal(n.rstrip("0"))
	except decimal.InvalidOperation, exception:
		pass
	return n

def wrap(text, width = 70):
	"""
	A word-wrap function that preserves existing line breaks
	and most spaces in the text. Expects that existing line
	breaks are posix newlines (\\n).
	"""
	return reduce(lambda line, word, width=width: '%s%s%s' %
		(line,
		' \n'[(len(line)-line.rfind('\n')-1
			+ len(word.split('\n',1)[0]
				) >= width)],
		word),
		text.split(' ')
		)

def center(text, width = None):
	text = text.split("\n")
	if width is None:
		width = 0
		for line in text:
			if len(line) > width:
				width = len(line)
	i = 0
	for line in text:
		text[i] = line.center(width)
		i += 1
	return "\n".join(text)

# get children of window and its subwindows
def GetAllChildren(self):
	children = self.GetChildren()
	allchildren = []
	for child in children:
		allchildren += [child]
		if hasattr(child, "GetAllChildren") and callable(child.GetAllChildren):
			allchildren += child.GetAllChildren()
	return allchildren

wx.Window.GetAllChildren = GetAllChildren

# update tooltip string correctly
def UpdateToolTipString(self, string):
	wx.Window.SetToolTip(self, None)
	wx.Window.SetToolTipString(self, string)

wx.Window.UpdateToolTipString = UpdateToolTipString

# avoid flickering
def SetBitmapLabelIfNot(self, bitmap):
	if self.GetBitmapLabel() != bitmap:
		self.SetBitmapLabel(bitmap)

wx.BitmapButton.SetBitmapLabelIfNot = SetBitmapLabelIfNot

# circumvent repainting issues (bitmap does not change on button state change)
def BitmapButtonEnableAndRefresh(self, enable = True):
	wx.Button.Enable(self, enable)
	if not hasattr(self, "_bitmaplabel"):
		self._bitmaplabel = self.GetBitmapLabel()
	if not hasattr(self, "_bitmapdisabled"):
		self._bitmapdisabled = self.GetBitmapDisabled()
	if enable:
		if not self._bitmaplabel.IsNull():
			self.SetBitmapLabelIfNot(self._bitmaplabel)
	else:
		if not self._bitmapdisabled.IsNull():
			self.SetBitmapLabelIfNot(self._bitmapdisabled)

def BitmapButtonDisableAndRefresh(self):
	self.Enable(False)

wx.BitmapButton.Enable = BitmapButtonEnableAndRefresh
wx.BitmapButton.Disable = BitmapButtonDisableAndRefresh

# get selected block and cells
def GridGetSelection(self):
	sel = []
	numrows = self.GetNumberRows()
	numcols = self.GetNumberCols()
	# rows
	rows = self.GetSelectedRows()
	for row in rows:
		if row > -1 and row < numrows:
			for i in range(numcols):
				if not (row, i) in sel:
					sel += [(row, i)]
	# cols
	cols = self.GetSelectedCols()
	for col in cols:
		if col > -1 and col < numcols:
			for i in range(numrows):
				if not (i, col) in sel:
					sel += [(i, col)]
	# block
	tl = self.GetSelectionBlockTopLeft()
	br = self.GetSelectionBlockBottomRight()
	if tl and br:
		for n in range(min(len(tl), len(br))):
			for i in range(tl[n][0], br[n][0] + 1): # rows
				if i > -1 and i < numrows:
					for j in range(tl[n][1], br[n][1] + 1): # cols
						if j > -1 and j < numcols and not (i, j) in sel:
							sel += [(i, j)]
	# single selected cells
	cells = self.GetSelectedCells()
	for cell in cells:
		if not -1 in cell and cell[0] < numrows and cell[1] < numcols and \
		   cell not in sel:
			sel += [cell]
	sel.sort()
	return sel

wx.grid.Grid.GetSelection = GridGetSelection

def GridGetSelectedRowsFromSelection(self):
	""" Return the number of fully selected rows.
	Unlike GetSelectedRows, include rows that have been selected
	by chosing individual cells """
	sel = self.GetSelection()
	numcols = self.GetNumberCols()
	rows = []
	i = -1
	for cell in sel:
		row, col = cell
		if row > i:
			i = row
			rownumcols = 0
		rownumcols += 1
		if rownumcols == numcols:
			rows += [row]
	return rows

wx.grid.Grid.GetSelectedRowsFromSelection = GridGetSelectedRowsFromSelection

def GridGetSelectionRows(self):
	"""  Return the rows a selection spans, 
	even if not all cells in a row are selected """
	sel = self.GetSelection()
	rows = []
	i = -1
	for cell in sel:
		row, col = cell
		if row > i:
			i = row
			rows += [row]
	return rows

wx.grid.Grid.GetSelectionRows = GridGetSelectionRows

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

class FileDrop(wx.FileDropTarget):
	def __init__(self, drophandlers = None):
		wx.FileDropTarget.__init__(self)
		if drophandlers is None:
			drophandlers = {}
		self.drophandlers = drophandlers
		self.unsupported_handler = None

	def OnDropFiles(self, x, y, filenames):
		self._files = {}

		for filename in filenames:
			name, ext = os.path.splitext(filename)
			if ext.lower() in self.drophandlers:
				self._files[ext.lower()] = filename

		if len(self._files):
			for key in self._files:
				self.drophandlers[key](self._files[key])
		elif self.unsupported_handler:
			self.unsupported_handler()

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

class CustomEvent(wx.PyEvent):
	def __init__(self, typeId, object, window = None):
		wx.PyEvent.__init__(self, typeId, object.GetId())
		self.typeId = typeId
		self.object = object
		self.window = window
	def GetEventObject(self):
		return self.object
	def GetEventType(self):
		return self.typeId
	def GetWindow(self):
		return self.window

class CustomGridCellEvent(CustomEvent):
	def __init__(self, typeId, object, row = -1, col = -1, window = None):
		CustomEvent.__init__(self, typeId, object, window)
		self.row = row
		self.col = col
	def GetRow(self):
		return self.row
	def GetCol(self):
		return self.col

class AboutDialog(wx.Dialog):
	def __init__(self, *args, **kwargs):
		kwargs["style"] = wx.DEFAULT_DIALOG_STYLE & ~(wx.RESIZE_BORDER | 
		   wx.RESIZE_BOX | wx.MAXIMIZE_BOX)
		wx.Dialog.__init__(self, *args, **kwargs)

		self.__set_properties()

		self.sizer = wx.BoxSizer(wx.VERTICAL)
		self.SetSizer(self.sizer)

	def __set_properties(self):
		_icon = wx.EmptyIcon()
		self.SetIcon(_icon)

	def Layout(self):
		self.sizer.SetSizeHints(self)
		self.sizer.Layout()

	def add_items(self, items):
		pointsize = 10
		for item in items:
			font = item.GetFont()
			if item.GetLabel() and font.GetPointSize() > pointsize:
				font.SetPointSize(pointsize)
				item.SetFont(font)
			self.sizer.Add(item, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 0)

class InfoDialog(wx.Dialog):
	def __init__(self, oparent = None, id = -1, title = appname, msg = "", 
	   ok = "OK", bitmap = None, pos = (-1, -1), size = (400, -1), 
	   show = True, logit = True):
		if oparent:
			gparent = oparent.GetGrandParent()
			if gparent is None:
				gparent = oparent
			if hasattr(gparent, "progress_parent") and \
			   (gparent.progress_parent.progress_start_timer.IsRunning() or \
			   gparent.progress_parent.progress_timer.IsRunning()):
				gparent.progress_parent.progress_start_timer.Stop()
				if hasattr(gparent.progress_parent, "progress_dlg"):
					gparent.progress_parent.progress_timer.Stop()
					wx.CallAfter(gparent.progress_parent.progress_dlg.Hide)
				wx.CallAfter(self.__init__, oparent, id, title, msg, ok, 
				   bitmap, pos, size)
				return
			if not oparent.IsShownOnScreen():
				parent = None # do not center on parent if not visible
			else:
				parent = oparent
				pos = list(pos)
				i = 0
				for coord in pos:
					if coord > -1:
						pos[i] += parent.GetScreenPosition()[i]
					i += 1
				pos = tuple(pos)
		else:
			parent = None
		wx.Dialog.__init__(self, parent, id, title, pos, size)
		self.SetPosition(pos) # yes, this is needed
		self.Bind(wx.EVT_SHOW, self.OnShow, self)

		margin = 12

		self.sizer0 = wx.BoxSizer(wx.VERTICAL)
		self.SetSizer(self.sizer0)
		if bitmap:
			self.sizer1 = wx.FlexGridSizer(1, 2)
		else:
			self.sizer1 = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer2 = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer3 = wx.BoxSizer(wx.VERTICAL)
		self.sizer0.Add(self.sizer1, flag = wx.ALIGN_CENTER | wx.TOP | 
		   wx.RIGHT | wx.LEFT, border = margin)
		self.sizer0.Add(self.sizer2, flag = wx.ALIGN_RIGHT | wx.ALL, 
		   border = margin)

		if bitmap:
			self.bitmap = wx.StaticBitmap(self, -1, bitmap, size = (32, 32))
			self.sizer1.Add(self.bitmap, flag = wx.RIGHT, border = margin)

		# if logit: safe_print(msg)
		
		self.sizer1.Add(self.sizer3, flag = wx.ALIGN_LEFT)
		self.message = wx.StaticText(self, -1, wrap(msg))
		self.sizer3.Add(self.message)

		btnwidth = 80

		self.ok = wx.Button(self, wx.ID_OK, ok)
		self.ok.SetInitialSize((self.ok.GetSize()[0] + btn_width_correction, 
		   -1))
		self.sizer2.Add(self.ok)
		self.Bind(wx.EVT_BUTTON, self.OnClose, id = wx.ID_OK)

		self.ok.SetDefault()

		self.sizer0.SetSizeHints(self)
		self.sizer0.Layout()
		if not pos or pos == (-1, -1):
			self.Center(wx.BOTH)
		elif pos[0] == -1:
			self.Center(wx.HORIZONTAL)
		elif pos[1] == -1:
			self.Center(wx.VERTICAL)
		if sys.platform == "darwin" and oparent and \
		   hasattr(oparent, "app") and (not oparent.app.IsActive() or \
		   (hasattr(oparent.app, "frame") and not oparent.app.frame.IsShownOnScreen())):
			start_new_thread(mac_app_activate, (.25, oparent.app.GetAppName()))
		if show:
			self.ShowModalThenDestroy(oparent)

	def ShowModalThenDestroy(self, oparent = None):
		if oparent:
			if hasattr(oparent, "modaldlg") and oparent.modaldlg != None:
				wx.CallLater(250, self.ShowModalThenDestroy, oparent)
				return
			oparent.modaldlg = self
		self.ShowModal()
		if oparent:
			oparent.modaldlg = None
		self.Destroy()

	def OnShow(self, event):
		self.SetFocus()

	def OnClose(self, event):
		self.Close(True)

class ConfirmDialog(wx.Dialog):
	def __init__(self, oparent = None, id = -1, title = appname, msg = "", 
	   ok = "OK", cancel = "Cancel", bitmap = None, pos = (-1, -1), 
	   size = (400, -1)):
		if oparent:
			if not oparent.IsShownOnScreen():
				parent = None # do not center on parent if not visible
			else:
				parent = oparent
				pos = list(pos)
				i = 0
				for coord in pos:
					if coord > -1:
						pos[i] += parent.GetScreenPosition()[i]
					i += 1
				pos = tuple(pos)
		else:
			parent = None
		wx.Dialog.__init__(self, parent, id, title, pos, size)
		self.SetPosition(pos) # yes, this is needed
		self.Bind(wx.EVT_CLOSE, self.OnClose, self)
		self.Bind(wx.EVT_SHOW, self.OnShow, self)

		margin = 12

		self.sizer0 = wx.BoxSizer(wx.VERTICAL)
		self.SetSizer(self.sizer0)
		if bitmap:
			self.sizer1 = wx.FlexGridSizer(1, 2)
		else:
			self.sizer1 = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer2 = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer3 = wx.BoxSizer(wx.VERTICAL)
		self.sizer0.Add(self.sizer1, flag = wx.ALIGN_LEFT | wx.TOP | 
		   wx.RIGHT | wx.LEFT, border = margin)
		self.sizer0.Add(self.sizer2, flag = wx.ALIGN_RIGHT | wx.ALL, 
		   border = margin)

		if bitmap:
			self.bitmap = wx.StaticBitmap(self, -1, bitmap, size = (32, 32))
			self.sizer1.Add(self.bitmap, flag = wx.RIGHT, border = margin)

		self.sizer1.Add(self.sizer3, flag = wx.ALIGN_LEFT)
		self.message = wx.StaticText(self, -1, wrap(msg))
		self.sizer3.Add(self.message)

		btnwidth = 80

		self.cancel = wx.Button(self, wx.ID_CANCEL, cancel)
		self.cancel.SetInitialSize((self.cancel.GetSize()[0] + 
		   btn_width_correction, -1))
		self.sizer2.Add(self.cancel)
		self.Bind(wx.EVT_BUTTON, self.OnClose, id = wx.ID_CANCEL)

		self.cancel.SetDefault()

		self.sizer2.Add((margin, margin))

		self.ok = wx.Button(self, wx.ID_OK, ok)
		self.ok.SetInitialSize((self.ok.GetSize()[0] + btn_width_correction, 
		   -1))
		self.sizer2.Add(self.ok)
		self.Bind(wx.EVT_BUTTON, self.OnClose, id = wx.ID_OK)

		self.sizer0.SetSizeHints(self)
		self.sizer0.Layout()
		if not pos or pos == (-1, -1):
			self.Center(wx.BOTH)
		elif pos[0] == -1:
			self.Center(wx.HORIZONTAL)
		elif pos[1] == -1:
			self.Center(wx.VERTICAL)
		if sys.platform == "darwin" and oparent and \
		   hasattr(oparent, "app") and (not oparent.app.IsActive() or \
		   (hasattr(oparent.app, "frame") and not oparent.app.frame.IsShownOnScreen())):
			start_new_thread(mac_app_activate, (.25, oparent.app.GetAppName()))

	def OnShow(self, event):
		self.SetFocus()

	def OnClose(self, event):
		if event.GetEventObject() == self:
			id = wx.ID_CANCEL
		else:
			id = event.GetId()
		self.EndModal(id)

class UndeletableFrame(wx.Frame):
	def __init__(self, parent = None, id = -1, title = "", pos = None, 
	   size = None, style = wx.DEFAULT_FRAME_STYLE):
		wx.Frame.__init__(self, parent, id, title, pos, size, style)
		self.Bind(wx.EVT_CLOSE, self.OnClose, self)

	def OnClose(self, event):
		self.Hide()

class InfoWindow(UndeletableFrame):
	def __init__(self, parent = None, id = -1, title = appname, msg = "", 
	   bitmap = None, pos = (-1, -1), size = (400, -1), 
	   style = wx.DEFAULT_FRAME_STYLE | wx.FRAME_TOOL_WINDOW):
		UndeletableFrame.__init__(self, parent, id, title, pos, size, style)
		self.SetPosition(pos) # yes, this is needed

		margin = 12
		
		self.panel = wx.Panel(self, -1)
		self.sizer0 = wx.BoxSizer(wx.VERTICAL)
		self.panel.SetSizer(self.sizer0)
		if bitmap:
			self.sizer1 = wx.FlexGridSizer(1, 2)
		else:
			self.sizer1 = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer0.Add(self.sizer1, flag = wx.ALIGN_CENTER | wx.ALL, 
		   border = margin)

		if bitmap:
			self.bitmap = wx.StaticBitmap(self.panel, -1, bitmap, 
			   size = (32, 32))
			self.sizer1.Add(self.bitmap, flag = wx.RIGHT, border = margin)

		self.message = wx.StaticText(self.panel, -1, wrap(msg))
		self.sizer1.Add(self.message)

		self.sizer0.SetSizeHints(self)
		self.sizer0.Layout()
		if not pos or pos == (-1, -1):
			self.Center(wx.BOTH)
		elif pos[0] == -1:
			self.Center(wx.HORIZONTAL)
		elif pos[1] == -1:
			self.Center(wx.VERTICAL)
		self.Show()
		self.Raise()

def isSizer(item):
	return isinstance(item, wx.Sizer)

class DisplayCalibratorGUI(wx.Frame):

	def __init__(self, app):
		try:
			if sys.platform == "win32":
				sp.call("color 0F", shell = True)
			else:
				if sys.platform == "darwin":
					mac_terminal_set_colors(text = "white", text_bold = "white")
				else:
					sp.call('echo -e "\\033[40;22;37m"', shell = True)
				sp.call('clear', shell = True)
		except Exception, exception:
			safe_print("Info - could not set terminal colors:", str(exception))
		self.app = app
		self.init_cfg()
		if verbose >= 1: safe_print(self.getlstr("startup"))
		self.init_frame()
		self.init_defaults()
		self.init_gamapframe()
		self.init_infoframe()
		self.init_measureframe()
		self.enumerate_displays_and_ports()
		if verbose >= 1: safe_print(self.getlstr("initializing_gui"))
		self.init_menus()
		self.init_controls()
		self.fixup()
		self.framesizer.SetSizeHints(self)
		self.framesizer.Layout()
		# we add the header and settings list after layout so it won't stretch the window further than necessary
		self.header = wx.StaticBitmap(self.headercontainer, -1, self.bitmaps["theme/header"])
		self.calibration_file_ctrl.SetItems([self.getlstr("settings.new")] + [("* " if cal == self.getcfg("calibration.file") and self.getcfg("settings.changed") else "") + self.getlstr(os.path.basename(cal)) for cal in self.recent_cals[1:]])
		self.calpanel.SetScrollRate(0, 20)
		self.update_controls(update_profile_name = False)
		if verbose >= 1: safe_print(self.getlstr("success"))
		self.update_displays()
		self.update_comports()
		self.update_profile_name()
		set_position(self, int(self.getcfg("position.x")), int(self.getcfg("position.y")))
		wx.CallAfter(self.ShowAll)
		if len(self.displays):
			if self.getcfg("calibration.file"):
				self.load_cal(silent = True) # load LUT curves from last used .cal file
			else:
				self.load_display_profile_cal(None) # load LUT curves from current display profile (if any, and if it contains curves)
		if verbose >= 1: safe_print(self.getlstr("ready"))
		logging.getLogger("").removeHandler(globalconfig["logging.StreamHandler"])
		globalconfig["log"].seek(0)
		self.infotext.SetValue("".join(line for line in globalconfig["log"]))

	def init_cfg(self):
		self.cfg = ConfigParser.RawConfigParser()
		try:
			self.cfg.read([os.path.join(confighome, appname + ".ini")])
		except Exception, exception:
			safe_print("Warning - could not parse configuration file '%s'" % appname + ".ini")
		self.cfg.optionxform = str
		
		if not self.cfg.has_option(ConfigParser.DEFAULTSECT, "lang"):
			self.cfg.set(ConfigParser.DEFAULTSECT, "lang", "en")
		self.lang = self.cfg.get(ConfigParser.DEFAULTSECT, "lang")
	
	def write_cfg(self):
		try:
			cfgfile = open(os.path.join(confighome, appname + ".ini"), "wb")
			io = StringIO()
			self.cfg.write(io)
			io.seek(0)
			l = io.read().strip("\n").split("\n")
			l.sort()
			cfgfile.write("\n".join(l))
			cfgfile.close()
		except Exception, exception:
			handle_error("Warning - could not write configuration file: %s" % (str(exception)), parent = self)

	def init_defaults(self):
		# defaults
		self.defaults = {
			"argyll.dir": os.path.expanduser("~"), # directory
			"calibration.ambient_viewcond_adjust": 0,
			"calibration.ambient_viewcond_adjust.lux": 500.0,
			"calibration.black_luminance": 0.5,
			"calibration.black_output_offset": 0.0,
			"calibration.black_point_correction": 0.0,
			"calibration.black_point_correction_choice.show": 1,
			"calibration.black_point_rate": 4.0,
			"calibration.black_point_rate.enabled": 0,
			"calibration.interactive_display_adjustment": 1,
			"calibration.luminance": 120.0,
			"calibration.quality": "m",
			"calibration.update": 0,
			"comport.number": 1,
			"dimensions.measureframe": "0.5,0.5,1.0",
			"dimensions.measureframe.unzoomed": "0.5,0.5,1.0",
			"display.number": 1,
			"measurement_mode": "l",
			"display_lut.link": 1,
			"display_lut.number": 1,
			"gamap_profile": "",
			"gamap_perceptual": 0,
			"gamap_saturation": 0,
			"gamap_src_viewcond": "pp",
			"gamap_out_viewcond": "mt",
			"gamma": 2.4,
			"last_cal_path": os.path.join(storage, self.getlstr("unnamed")),
			"last_cal_or_icc_path": os.path.join(storage, self.getlstr("unnamed")),
			"last_filedialog_path": os.path.join(storage, self.getlstr("unnamed")),
			"last_icc_path": os.path.join(storage, self.getlstr("unnamed")),
			"last_ti1_path": os.path.join(storage, self.getlstr("unnamed")),
			"last_ti3_path": os.path.join(storage, self.getlstr("unnamed")),
			"measure.darken_background": 0,
			"measure.darken_background.show_warning": 1,
			"position.info.x": get_display(self).ClientArea[0] + 20,
			"position.info.y": get_display(self).ClientArea[1] + 40,
			"position.x": get_display(self).ClientArea[0] + 10,
			"position.y": get_display(self).ClientArea[1] + 30,
			"profile.install_scope": "l" if (sys.platform != "win32" and 
										os.geteuid() == 0) or 
										(sys.platform == "win32" and 
										sys.getwindowsversion() >= (6, )) else 
										"u", # Linux, OSX or Vista and later
			"profile.name": u" ".join([
				u"%dn",
				u"%Y-%m-%d",
				# # u"%in",
				# # u"%im",
				# self.getlstr("white"),
				u"%cb",
				u"%wp",
				# self.getlstr("black"),
				u"%cB",
				u"%ck",
				# # u"%cA",
				u"%cg",
				# u"%cf",
				# # u"%ca",
				u"%cq-%pq",
				u"%pt"
			]),
			"profile.quality": "m",
			"profile.save_path": storage, # directory
			"profile.type": "s",
			"profile.update": 0,
			"projector_mode": 0,
			"recent_cals": "",
			"recent_cals_max": 15,
			"settings.changed": 0,
			"size.info.w": 512,
			"size.info.h": 384,
			"tc_white_patches": 4,
			"tc_single_channel_patches": 0,
			"tc_gray_patches": 9,
			"tc_multi_steps": 3,
			"tc_fullspread_patches": 0,
			"tc_algo": "",
			"tc_angle": 0.3333,
			"tc_adaption": 0.0,
			"tc_precond": 0,
			"tc_precond_profile": "",
			"tc_filter": 0,
			"tc_filter_L": 50,
			"tc_filter_a": 0,
			"tc_filter_b": 0,
			"tc_filter_rad": 255,
			"tc_vrml": 0,
			"tc_vrml_lab": 0,
			"tc_vrml_device": 1,
			"trc": 2.4,
			"trc.should_use_viewcond_adjust.show_msg": 1,
			"trc.type": "g",
			"whitepoint.colortemp": 5000.0,
			"whitepoint.colortemp.locus": "t",
			"whitepoint.x": 0.345741,
			"whitepoint.y": 0.358666
		}
		
		self.argyll_version = [0, 0, 0]

		self.lut_access = [] # displays where lut access works

		self.options_dispcal = []
		self.options_targen = []
		if verbose >= 2: safe_print("Setting targen options:", *self.options_targen)
		self.options_dispread = []
		self.options_colprof = []
		
		self.dispread_after_dispcal = None

		self.recent_cals = self.getcfg("recent_cals").split(os.pathsep)
		if not "" in self.recent_cals:
			self.recent_cals = [""] + self.recent_cals
		self.presets = []
		presets = get_data_path("presets", ".*\.(?:icc|icm)$")
		if isinstance(presets, list):
			self.presets = natsort(presets)
			self.presets.reverse()
			for preset in self.presets:
				if not preset in self.recent_cals:
					self.recent_cals.insert(1, preset)
		self.static_labels = []
		self.updatingctrls = False
		self.whitepoint_colortemp_loci = [
			self.getlstr("whitepoint.colortemp.locus.daylight"),
			self.getlstr("whitepoint.colortemp.locus.blackbody")
		]
		# left side - internal enumeration, right side - commmandline
		self.whitepoint_colortemp_loci_ab = {
			0: "t",
			1: "T"
		}
		# left side - commmandline, right side - internal enumeration
		self.whitepoint_colortemp_loci_ba = {
			"t": 0,
			"T": 1
		}
		self.comports = []
		self.displays = []
		# left side - internal enumeration, right side - commmandline
		self.measurement_modes_ab = {
			"color": {
				0: "c",
				1: "l",
				2: "cp",
				3: "lp"
			},
			"spect": {
				0: None,
				1: "p"
			}
		}
		# left side - commmandline, right side - internal enumeration
		self.measurement_modes_ba = {
			"color": {
				"c": 0,
				"l": 1,
				None: 1,
				"cp": 2,
				"lp": 3
			},
			"spect": {
				"c": 0,
				"l": 0,
				None: 0,
				"cp": 1,
				"lp": 1,
				"p": 1
			}
		}

		self.bitmaps = {"transparent16x16": wx.EmptyBitmap(16, 16, depth = -1)}
		dc = wx.MemoryDC()
		dc.SelectObject(self.bitmaps["transparent16x16"])
		dc.SetBackground(wx.Brush("black"))
		dc.Clear()
		dc.SelectObject(wx.NullBitmap)
		self.bitmaps["transparent16x16"].SetMaskColour("black")
		for filename in resfiles:
			name, ext = os.path.splitext(filename)
			if ext.lower() in (".png"):
				self.bitmaps[name.lower()] = wx.Bitmap(get_data_path(os.path.sep.join(filename.split("/"))))

		self.profile_types = [
			"LUT",
			"Matrix"
		]
		# left side - internal enumeration, right side - commmandline
		self.profile_types_ab = {
			0: "l",
			1: "s"
		}
		# left side - commmandline, right side - internal enumeration
		self.profile_types_ba = {
			"l": 0,
			"s": 1
		}
		# left side - commmandline, right side - internal enumeration
		self.quality_ab = {
			1: "l",
			2: "m",
			3: "h",
			4: "u"
		}
		# left side - commmandline, right side - internal enumeration
		self.quality_ba = {
			"l": 1,
			"m": 2,
			"h": 3,
			"u": 4
		}
		self.testchart_defaults = {
			None: {
				"s": "d3-e4-s0-g16-m4-f0-crossover.ti1", # CRT shaper / matrix
				"l": "d3-e4-s0-g52-m4-f0-crossover.ti1", # CRT lut
			},
			"c": {
				"s": "d3-e4-s0-g16-m4-f0-crossover.ti1", # CRT shaper / matrix
				"l": "d3-e4-s0-g52-m4-f0-crossover.ti1", # CRT lut
			},
			"l": {
				"s": "d3-e4-s0-g16-m4-f0-crossover.ti1", # LCD shaper / matrix
				"l": "d3-e4-s0-g52-m4-f0-crossover.ti1", # LCD lut
			},
			"cp": {
				"s": "d3-e4-s0-g16-m4-f0-crossover.ti1", # CRT projector shaper / matrix
				"l": "d3-e4-s0-g52-m4-f0-crossover.ti1", # CRT projector lut
			},
			"lp": {
				"s": "d3-e4-s0-g16-m4-f0-crossover.ti1", # LCD projector shaper / matrix
				"l": "d3-e4-s0-g52-m4-f0-crossover.ti1", # LCD projector lut
			},
			"p": {
				"s": "d3-e4-s0-g16-m4-f0-crossover.ti1", # projector shaper / matrix
				"l": "d3-e4-s0-g52-m4-f0-crossover.ti1", # projector lut
			}
		}
		self.defaults["testchart.file"] = get_data_path(os.path.join("ti1", self.testchart_defaults[self.defaults["measurement_mode"]][self.defaults["profile.type"]]))
		self.set_testchart_names()
		self.testcharts = []
		self.testchart_names = []
		# left side - commmandline, right side - .cal file
		self.trc_ab = {
			"l": "L_STAR",
			"709": "REC709",
			"s": "sRGB",
			"240": "SMPTE240M"
		}
		# left side - .cal file, right side - commmandline
		self.trc_ba = {
			"L_STAR": "l",
			"REC709": "709",
			"sRGB": "s",
			"SMPTE240M": "240"
		}
		self.trc_types = [
			self.getlstr("trc.type.relative"),
			self.getlstr("trc.type.absolute")
		]
		# left side - internal enumeration, right side - commmandline
		self.trc_types_ab = {
			0: "g",
			1: "G"
		}
		# left side - commmandline, right side - internal enumeration
		self.trc_types_ba = {
			"g": 0,
			"G": 1
		}
		self.trc_presets = [
			"1.8",
			"2.0",
			"2.2",
			"2.4"
		]
		self.whitepoint_presets = [
			"5000",
			"5500",
			"6000",
			"6500"
		]

		self.tc_algos_ab = {
			"": self.getlstr("tc.ofp"),
			"t": self.getlstr("tc.t"),
			"r": self.getlstr("tc.r"),
			"R": self.getlstr("tc.R"),
			"q": self.getlstr("tc.q"),
			"i": self.getlstr("tc.i"),
			"I": self.getlstr("tc.I")
		}

		self.tc_algos_ba = {
			self.getlstr("tc.ofp"): "",
			self.getlstr("tc.t"): "t",
			self.getlstr("tc.r"): "r",
			self.getlstr("tc.R"): "R",
			self.getlstr("tc.q"): "q",
			self.getlstr("tc.i"): "i",
			self.getlstr("tc.I"): "I"
		}

		self.viewconds = [
			"pp",
			"pe",
			"mt",
			"mb",
			"md",
			"jm",
			"jd",
			"pcd",
			"ob",
			"cx"
		]
		self.viewconds_ab = {}
		self.viewconds_ba = {}
		self.viewconds_out_ab = {}

		for v in self.viewconds:
			lstr = self.getlstr("gamap.viewconds.%s" % v)
			self.viewconds_ab[v] = lstr
			self.viewconds_ba[lstr] = v
			if v not in ("pp", "pe", "pcd", "ob", "cx"):
				self.viewconds_out_ab[v] = lstr

		self.pwd = None

	def set_testchart_names(self):
		self.default_testchart_names = []
		for measurement_mode in self.testchart_defaults:
			for profile_type in self.testchart_defaults[measurement_mode]:
				if not self.testchart_defaults[measurement_mode][profile_type] in self.default_testchart_names:
					self.default_testchart_names += [self.getlstr(self.testchart_defaults[measurement_mode][profile_type])]

	def init_frame(self):
		# window frame
		wx.Frame.__init__(self, None, -1, "%s %s build %s" % (appname, version, build), size = wx.Size(480, 748), style = wx.DEFAULT_FRAME_STYLE & ~(wx.RESIZE_BORDER | wx.RESIZE_BOX | wx.MAXIMIZE_BOX))
		self.SetIcon(wx.Icon(get_data_path(os.path.join("theme", "icons", "16x16", appname + ".png")), wx.BITMAP_TYPE_PNG))
		self.Bind(wx.EVT_CLOSE, self.OnClose, self)
		self.Bind(wx.EVT_SHOW, self.OnShow, self)
		self.Bind(wx.EVT_MOVE, self.OnMove, self)
		self.plugplay_timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self.plugplay_timer_handler, self.plugplay_timer)
		self.update_profile_name_timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self.update_profile_name, self.update_profile_name_timer)
		self.droptarget = FileDrop()
		self.droptarget.drophandlers = {
			".cal": self.cal_drop_handler,
			".icc": self.cal_drop_handler,
			".icm": self.cal_drop_handler,
			".ti1": self.ti1_drop_handler,
			".ti3": self.ti3_drop_handler
		}
		self.droptarget.unsupported_handler = self.drop_unsupported_handler

		# panel & sizers
		self.framesizer = wx.BoxSizer(wx.VERTICAL)
		self.SetSizer(self.framesizer)
		self.panel = wx.Panel(self, -1)
		self.panel.SetDropTarget(self.droptarget)
		self.framesizer.Add(self.panel, 1, wx.EXPAND)
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		self.subsizer = []
		self.panel.SetSizer(self.sizer)

	def OnMove(self, event):
		if self.IsShownOnScreen() and not self.IsMaximized() and not self.IsIconized():
			x, y = self.GetScreenPosition()
			self.setcfg("position.x", x)
			self.setcfg("position.y", y)
		display_client_rect = get_display(self).ClientArea
		if hasattr(self, "calpanel") and (not hasattr(self, "display_client_rect") or self.display_client_rect != display_client_rect):
			if verbose >= 2: safe_print("We just moved to this workspace:", ", ".join(map(str, display_client_rect)))
			size = self.GetSize()
			if sys.platform not in ("darwin", "win32"): # Linux
				safety_margin = 45
			else:
				safety_margin = 20
			vsize = self.calpanel.GetVirtualSize()
			fullheight = size[1] - self.calpanel.GetSize()[1] + vsize[1]
			maxheight = None
			if size[1] > display_client_rect[3] - safety_margin or fullheight > display_client_rect[3] - safety_margin:
				if verbose >= 2: safe_print("Our full height (w/o scrollbars: %s) is too tall for that workspace! Adjusting..." % fullheight)
				vsize = self.calpanel.GetSize()
				maxheight = vsize[1] - (size[1] - display_client_rect[3] + safety_margin)
			elif size[1] < fullheight:
				if verbose >= 2: safe_print("Our full height (w/o scrollbars: %s) fits on that workspace. Adjusting..." % fullheight)
				maxheight = vsize[1]
			self.display_client_rect = display_client_rect
			if maxheight:
				newheight = size[1] - self.calpanel.GetSize()[1] + maxheight
				if debug:
					safe_print("Panel virtual height:", vsize[1])
					safe_print("New panel height:", maxheight)
					safe_print("New height:", newheight)
				wx.CallAfter(self.frame_fit, fullheight, vsize[1], maxheight, newheight)
			event.Skip()

	def frame_fit(self, fullheight, virtualheight, height, newheight):
		size = self.GetSize()
		self.Freeze()
		self.SetMaxSize((size[0], fullheight))
		self.calpanel.SetMaxSize((-1, virtualheight))
		self.calpanel.SetMinSize((-1, height))
		self.calpanel.SetMaxSize((-1, height))
		self.calpanel.SetSize((-1, height))
		if debug:
			safe_print("New framesizer min height:", self.framesizer.GetMinSize()[1])
			safe_print("New framesizer height:", self.framesizer.GetSize()[1])
		self.SetMinSize((size[0], newheight))
		if newheight < fullheight:
			self.SetMaxSize((size[0], newheight))
		self.Fit()
		self.Thaw()

	def cal_drop_handler(self, path):
		if not self.is_working():
			self.load_cal_handler(None, path)

	def ti1_drop_handler(self, path):
		if not self.is_working():
			self.testchart_btn_handler(None, path)

	def ti3_drop_handler(self, path):
		if not self.is_working():
			self.create_profile_handler(None, path)

	def drop_unsupported_handler(self):
		if not self.is_working():
			InfoDialog(self, msg = self.getlstr("error.file_type_unsupported"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])

	def enumerate_displays_and_ports(self, silent = False):
		if (silent and self.check_argyll_bin()) or (not silent and self.check_set_argyll_bin()):
			displays = list(self.displays)
			if verbose >= 1 and not silent: safe_print(self.getlstr("enumerating_displays_and_comports"))
			self.exec_cmd(self.get_argyll_util("dispcal"), [], capture_output = True, skip_cmds = True, silent = True, log_output = False)
			arg = None
			self.displays = []
			self.comports = []
			self.defaults["calibration.black_point_rate.enabled"] = 0
			n = -1
			for line in self.output:
				if type(line) in (str, unicode):
					n += 1
					line = line.strip()
					if n == 0 and "version" in line.lower():
						version = line[line.lower().find("version")+8:]
						version = re.findall("(\d+|[^.\d]+)", version)
						for i in range(len(version)):
							try:
								version[i] = int(version[i])
							except ValueError:
								version[i] = version[i]
						self.argyll_version = version
						if verbose >= 2: safe_print("Argyll CMS version", repr(version))
						continue
					line = line.split(None, 1)
					if len(line) and line[0][0] == "-":
						arg = line[0]
						if arg == "-A":
							# Rate of blending from neutral to black point. Default 8.0
							self.defaults["calibration.black_point_rate.enabled"] = 1
					elif len(line) > 1 and line[1][0] == "=":
						value = line[1].strip(" ='")
						if arg == "-d":
							match = re.findall("(.+?),? at (-?\d+), (-?\d+), width (\d+), height (\d+)", value)
							if len(match):
								display = "%s @ %s, %s, %sx%s" % match[0]
								if " ".join(value.split()[-2:]) == "(Primary Display)":
									display += " " + self.getlstr("display.primary")
								self.displays.append(display)
						elif arg == "-c":
							value = value.split(None, 1)
							if len(value) > 1:
								value = value[1].strip("()")
							else:
								value = value[0]
							self.comports.append(value)
			if test:
				inames = instruments.keys()
				inames.sort()
				for iname in inames:
					self.comports.append(iname)
			if verbose >= 1 and not silent: safe_print(self.getlstr("success"))
			if displays != self.displays:
				# check lut access
				i = 0
				for disp in self.displays:
					if verbose >= 1 and not silent: safe_print(self.getlstr("checking_lut_access", (i + 1)))
					# load test.cal
					self.exec_cmd(self.get_argyll_util("dispwin"), ["-d%s" % (i +1), "-c", get_data_path("test.cal")], capture_output = True, skip_cmds = True, silent = True)
					# check if LUT == test.cal
					self.exec_cmd(self.get_argyll_util("dispwin"), ["-d%s" % (i +1), "-V", get_data_path("test.cal")], capture_output = True, skip_cmds = True, silent = True)
					retcode = -1
					for line in self.output:
						if line.find("IS loaded") >= 0:
							retcode = 0
							break
					# reset LUT & load profile cal (if any)
					self.exec_cmd(self.get_argyll_util("dispwin"), ["-d%s" % (i +1), "-c", "-L"], capture_output = True, skip_cmds = True, silent = True)
					self.lut_access += [retcode == 0]
					if verbose >= 1 and not silent:
						if retcode == 0:
							safe_print(self.getlstr("success"))
						else:
							safe_print(self.getlstr("failure"))
					i += 1

	def init_gamapframe(self):
		gamap = self.gamapframe = UndeletableFrame(self, -1, self.getlstr("gamapframe.title"), pos = (-1, 100), style = (wx.DEFAULT_FRAME_STYLE | wx.FRAME_NO_TASKBAR) & ~(wx.RESIZE_BORDER | wx.RESIZE_BOX | wx.MAXIMIZE_BOX | wx.MINIMIZE_BOX))
		gamap.SetIcon(wx.Icon(get_data_path(os.path.join("theme", "icons", "16x16", appname + ".png")), wx.BITMAP_TYPE_PNG))

		panel = gamap.panel = wx.Panel(gamap, -1)
		sizer = self.gamapframe.sizer = wx.BoxSizer(wx.VERTICAL)
		gamap.panel.SetSizer(gamap.sizer)

		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(hsizer, flag = wx.ALL & ~wx.BOTTOM | wx.EXPAND, border = 12)
		hsizer.Add(wx.StaticText(panel, -1, self.getlstr("gamap.profile")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		self.gamap_profile = wx.FilePickerCtrl(panel, -1, "", message = self.getlstr("gamap.profile"), wildcard = self.getlstr("filetype.icc") + "|*.icc;*.icm")
		gamap.Bind(wx.EVT_FILEPICKER_CHANGED, self.gamap_profile_handler, id = self.gamap_profile.GetId())
		hsizer.Add(self.gamap_profile, 1, flag = wx.ALIGN_CENTER_VERTICAL)

		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(hsizer, flag = wx.ALL & ~wx.BOTTOM | wx.EXPAND, border = 12)
		self.gamap_perceptual_cb = wx.CheckBox(gamap.panel, -1, self.getlstr("gamap.perceptual"))
		gamap.Bind(wx.EVT_CHECKBOX, self.gamap_perceptual_cb_handler, id = self.gamap_perceptual_cb.GetId())
		hsizer.Add(self.gamap_perceptual_cb)

		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(hsizer, flag = wx.ALL & ~wx.BOTTOM | wx.EXPAND, border = 12)
		self.gamap_saturation_cb = wx.CheckBox(gamap.panel, -1, self.getlstr("gamap.saturation"))
		gamap.Bind(wx.EVT_CHECKBOX, self.gamap_saturation_cb_handler, id = self.gamap_saturation_cb.GetId())
		hsizer.Add(self.gamap_saturation_cb)

		hsizer = wx.FlexGridSizer(3, 2)
		sizer.Add(hsizer, flag = wx.ALL | wx.EXPAND, border = 12)

		hsizer.Add(wx.StaticText(panel, -1, self.getlstr("gamap.src_viewcond")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		self.gamap_src_viewcond_ctrl = wx.ComboBox(panel, -1, choices = sorted(self.viewconds_ab.values()), style = wx.CB_READONLY)
		gamap.Bind(wx.EVT_COMBOBOX, self.gamap_src_viewcond_handler, id = self.gamap_src_viewcond_ctrl.GetId())
		hsizer.Add(self.gamap_src_viewcond_ctrl, 1, flag = wx.ALIGN_CENTER_VERTICAL)

		hsizer.Add((0, 8))
		hsizer.Add((0, 8))

		hsizer.Add(wx.StaticText(panel, -1, self.getlstr("gamap.out_viewcond")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		self.gamap_out_viewcond_ctrl = wx.ComboBox(panel, -1, choices = sorted(self.viewconds_out_ab.values()), style = wx.CB_READONLY)
		gamap.Bind(wx.EVT_COMBOBOX, self.gamap_out_viewcond_handler, id = self.gamap_out_viewcond_ctrl.GetId())
		hsizer.Add(self.gamap_out_viewcond_ctrl, 1, flag = wx.ALIGN_CENTER_VERTICAL)

		for child in gamap.GetAllChildren():
			if hasattr(child, "SetFont"):
				self.set_font_size(child)

		gamap.sizer.SetSizeHints(gamap)
		gamap.sizer.Layout()

	def gamap_profile_handler(self, event = None):
		v = self.gamap_profile.GetPath()
		p = bool(v) and os.path.exists(v)
		if p:
			try:
				profile = ICCP.ICCProfile(v)
			except (IOError, ICCP.ICCProfileInvalidError), exception:
				p = False
				InfoDialog(self.gamapframe, msg = self.getlstr("profile.invalid"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
		self.gamap_perceptual_cb.Enable(p)
		self.gamap_saturation_cb.Enable(p)
		c = self.gamap_perceptual_cb.GetValue() or self.gamap_saturation_cb.GetValue()
		self.gamap_src_viewcond_ctrl.Enable(p and c)
		self.gamap_out_viewcond_ctrl.Enable(p and c)
		if v != self.getcfg("gamap_profile"):
			self.profile_settings_changed()
		self.setcfg("gamap_profile", v)

	def gamap_perceptual_cb_handler(self, event = None):
		v = self.gamap_perceptual_cb.GetValue()
		if not v:
			self.gamap_saturation_cb.SetValue(False)
			self.gamap_saturation_cb_handler()
		if int(v) != self.getcfg("gamap_perceptual"):
			self.profile_settings_changed()
		self.setcfg("gamap_perceptual", int(v))
		self.gamap_profile_handler()

	def gamap_saturation_cb_handler(self, event = None):
		v = self.gamap_saturation_cb.GetValue()
		if v:
			self.gamap_perceptual_cb.SetValue(True)
			self.gamap_perceptual_cb_handler()
		if int(v) != self.getcfg("gamap_saturation"):
			self.profile_settings_changed()
		self.setcfg("gamap_saturation", int(v))
		self.gamap_profile_handler()

	def gamap_src_viewcond_handler(self, event = None):
		v = self.viewconds_ba[self.gamap_src_viewcond_ctrl.GetStringSelection()]
		if v != self.getcfg("gamap_src_viewcond"):
			self.profile_settings_changed()
		self.setcfg("gamap_src_viewcond", v)

	def gamap_out_viewcond_handler(self, event = None):
		v = self.viewconds_ba[self.gamap_out_viewcond_ctrl.GetStringSelection()]
		if v != self.getcfg("gamap_out_viewcond"):
			self.profile_settings_changed()
		self.setcfg("gamap_out_viewcond", v)

	def init_infoframe(self):
		self.infoframe = UndeletableFrame(self, -1, self.getlstr("infoframe.title"), pos = (int(self.getcfg("position.info.x")), int(self.getcfg("position.info.y"))), style = wx.DEFAULT_FRAME_STYLE | wx.FRAME_TOOL_WINDOW)
		self.infoframe.last_visible = False
		self.infoframe.panel = wx.Panel(self.infoframe, -1)
		self.infoframe.sizer = wx.BoxSizer(wx.VERTICAL)
		self.infoframe.panel.SetSizer(self.infoframe.sizer)
		self.infotext = wx.TextCtrl(self.infoframe.panel, -1, "", style = wx.TE_MULTILINE | wx.TE_READONLY)
		if sys.platform == "win32":
			font = wx.Font(8, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
		else:
			font = wx.Font(11, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
		self.infotext.SetFont(font)
		self.infoframe.sizer.Add(self.infotext, 1, flag = wx.ALL | wx.EXPAND, border = 4)
		self.infoframe.btnsizer = wx.BoxSizer(wx.HORIZONTAL)
		self.infoframe.sizer.Add(self.infoframe.btnsizer)
		self.infoframe.save_as_btn = wx.BitmapButton(self.infoframe.panel, -1, self.bitmaps["theme/icons/16x16/media-floppy"], style = wx.NO_BORDER)
		self.infoframe.save_as_btn.Bind(wx.EVT_BUTTON, self.info_save_as_handler)
		self.infoframe.save_as_btn.UpdateToolTipString(self.getlstr("save_as"))
		self.infoframe.btnsizer.Add(self.infoframe.save_as_btn, flag = wx.ALL, border = 4)
		self.infoframe.clear_btn = wx.BitmapButton(self.infoframe.panel, -1, self.bitmaps["theme/icons/16x16/edit-delete"], style = wx.NO_BORDER)
		self.infoframe.clear_btn.Bind(wx.EVT_BUTTON, self.info_clear_handler)
		self.infoframe.clear_btn.UpdateToolTipString(self.getlstr("clear"))
		self.infoframe.btnsizer.Add(self.infoframe.clear_btn, flag = wx.ALL, border = 4)
		self.infoframe.SetMinSize((self.defaults["size.info.w"], self.defaults["size.info.h"]))
		set_position(self.infoframe, int(self.getcfg("position.info.x")), int(self.getcfg("position.info.y")), int(self.getcfg("size.info.w")), int(self.getcfg("size.info.h")))
		self.infoframe.Bind(wx.EVT_MOVE, self.infoframe_move_handler)
		self.infoframe.Bind(wx.EVT_SIZE, self.infoframe_size_handler)

		self.infoframe.Children[0].Bind(wx.EVT_WINDOW_DESTROY, self.infoframe_destroy_handler)

	def infoframe_move_handler(self, event = None):
		if self.infoframe.IsShownOnScreen() and not self.infoframe.IsMaximized() and not self.infoframe.IsIconized():
			x, y = self.infoframe.GetScreenPosition()
			self.setcfg("position.info.x", x)
			self.setcfg("position.info.y", y)
		if event:
			event.Skip()

	def infoframe_size_handler(self, event = None):
		if self.infoframe.IsShownOnScreen() and not self.infoframe.IsMaximized() and not self.infoframe.IsIconized():
			w, h = self.infoframe.GetSize()
			self.setcfg("size.info.w", w)
			self.setcfg("size.info.h", h)
		if event:
			event.Skip()

	def infoframe_destroy_handler(self, event):
		event.Skip()

	def init_measureframe(self):
		self.measureframe = UndeletableFrame(self, -1, self.getlstr("measureframe.title"), style = wx.DEFAULT_FRAME_STYLE & ~(wx.RESIZE_BORDER | wx.RESIZE_BOX | wx.MAXIMIZE_BOX))
		self.measureframe.SetIcon(wx.Icon(get_data_path(os.path.join("theme", "icons", "16x16", appname + ".png")), wx.BITMAP_TYPE_PNG))
		self.measureframe.Bind(wx.EVT_CLOSE, self.measureframe_close_handler, self.measureframe)
		self.measureframe.Bind(wx.EVT_SIZE, self.measureframe_size_handler, self.measureframe)
		self.measureframe.panel = wx.Panel(self.measureframe, -1)
		self.measureframe.sizer = wx.GridSizer(3, 1)
		self.measureframe.panel.SetSizer(self.measureframe.sizer)

		self.measureframe.hsizer = wx.BoxSizer(wx.HORIZONTAL)
		self.measureframe.sizer.Add(self.measureframe.hsizer, flag = wx.ALIGN_CENTER_HORIZONTAL | wx.ALL | wx.ALIGN_TOP, border = 10)

		self.measureframe.zoommaxbutton = wx.BitmapButton(self.measureframe.panel, -1, self.bitmaps["theme/icons/32x32/zoom-best-fit"], style = wx.NO_BORDER)
		self.measureframe.Bind(wx.EVT_BUTTON, self.measureframe_zoommax_handler, self.measureframe.zoommaxbutton)
		self.measureframe.hsizer.Add(self.measureframe.zoommaxbutton, flag = wx.ALIGN_CENTER)
		self.measureframe.zoommaxbutton.UpdateToolTipString(self.getlstr("measureframe.zoommax"))

		self.measureframe.hsizer.Add((2, 1))

		self.measureframe.zoominbutton = wx.BitmapButton(self.measureframe.panel, -1, self.bitmaps["theme/icons/32x32/zoom-in"], style = wx.NO_BORDER)
		self.measureframe.Bind(wx.EVT_BUTTON, self.measureframe_zoomin_handler, self.measureframe.zoominbutton)
		self.measureframe.hsizer.Add(self.measureframe.zoominbutton, flag = wx.ALIGN_CENTER)
		self.measureframe.zoominbutton.UpdateToolTipString(self.getlstr("measureframe.zoomin"))

		self.measureframe.hsizer.Add((2, 1))

		self.measureframe.zoomnormalbutton = wx.BitmapButton(self.measureframe.panel, -1, self.bitmaps["theme/icons/32x32/zoom-original"], style = wx.NO_BORDER)
		self.measureframe.Bind(wx.EVT_BUTTON, self.measureframe_zoomnormal_handler, self.measureframe.zoomnormalbutton)
		self.measureframe.hsizer.Add(self.measureframe.zoomnormalbutton, flag = wx.ALIGN_CENTER)
		self.measureframe.zoomnormalbutton.UpdateToolTipString(self.getlstr("measureframe.zoomnormal"))

		self.measureframe.hsizer.Add((2, 1))

		self.measureframe.zoomoutbutton = wx.BitmapButton(self.measureframe.panel, -1, self.bitmaps["theme/icons/32x32/zoom-out"], style = wx.NO_BORDER)
		self.measureframe.Bind(wx.EVT_BUTTON, self.measureframe_zoomout_handler, self.measureframe.zoomoutbutton)
		self.measureframe.hsizer.Add(self.measureframe.zoomoutbutton, flag = wx.ALIGN_CENTER)
		self.measureframe.zoomoutbutton.UpdateToolTipString(self.getlstr("measureframe.zoomout"))

		self.measureframe.centerbutton = wx.BitmapButton(self.measureframe.panel, -1, self.bitmaps["theme/icons/32x32/window-center"], style = wx.NO_BORDER)
		self.measureframe.Bind(wx.EVT_BUTTON, self.measureframe_center_handler, self.measureframe.centerbutton)
		self.measureframe.sizer.Add(self.measureframe.centerbutton, flag = wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT, border = 10)
		self.measureframe.centerbutton.UpdateToolTipString(self.getlstr("measureframe.center"))

		self.measureframe.vsizer = wx.BoxSizer(wx.VERTICAL)
		self.measureframe.sizer.Add(self.measureframe.vsizer, flag = wx.ALIGN_BOTTOM | wx.ALIGN_CENTER_HORIZONTAL)

		self.measure_darken_background_cb = wx.CheckBox(self.measureframe.panel, -1, self.getlstr("measure.darken_background"))
		self.measure_darken_background_cb.SetValue(bool(int(self.getcfg("measure.darken_background"))))
		self.Bind(wx.EVT_CHECKBOX, self.measure_darken_background_ctrl_handler, id = self.measure_darken_background_cb.GetId())
		self.measureframe.vsizer.Add(self.measure_darken_background_cb, flag = wx.ALIGN_BOTTOM | wx.ALIGN_CENTER_HORIZONTAL | wx.LEFT | wx.RIGHT | wx.TOP, border = 10)

		self.measureframe.measurebutton = wx.Button(self.measureframe.panel, -1, self.getlstr("measureframe.measurebutton"))
		self.measureframe.Bind(wx.EVT_BUTTON, self.measureframe_measure_handler, self.measureframe.measurebutton)
		self.measureframe.vsizer.Add(self.measureframe.measurebutton, flag = wx.ALIGN_BOTTOM | wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, border = 10)
		self.set_font_size(self.measureframe.measurebutton)
		self.measureframe.measurebutton.SetInitialSize((self.measureframe.measurebutton.GetSize()[0] + btn_width_correction, -1))

		min_size = max(self.measureframe.sizer.GetMinSize())
		self.measureframe.SetMinSize((min_size, min_size)) # make sure the min size is quadratic and large enough to accomodate all controls
		self.measureframe.SetMaxSize((20000, 20000))

	def measure_darken_background_ctrl_handler(self, event):
		if debug: safe_print("measure_darken_background_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		if self.measure_darken_background_cb.GetValue() and self.getcfg("measure.darken_background.show_warning"):
			dlg = ConfirmDialog(self.measureframe, msg = self.getlstr("measure.darken_background.warning"), ok = self.getlstr("ok"), cancel = self.getlstr("cancel"), bitmap = self.bitmaps["theme/icons/32x32/dialog-warning"])
			chk = wx.CheckBox(dlg, -1, self.getlstr("dialog.do_not_show_again"))
			dlg.Bind(wx.EVT_CHECKBOX, self.measure_darken_background_warning_handler, id = chk.GetId())
			dlg.sizer3.Add(chk, flag = wx.TOP | wx.ALIGN_LEFT, border = 12)
			dlg.sizer0.SetSizeHints(dlg)
			dlg.sizer0.Layout()
			rslt = dlg.ShowModal()
			if rslt == wx.ID_CANCEL:
				self.measure_darken_background_cb.SetValue(False)
		self.setcfg("measure.darken_background", int(self.measure_darken_background_cb.GetValue()))
	
	def measure_darken_background_warning_handler(self, event):
		self.setcfg("measure.darken_background.show_warning", int(not event.GetEventObject().GetValue()))

	def measureframe_info_handler(self, event):
		InfoDialog(self.measureframe, msg = self.getlstr("measureframe.info"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-information"], logit = False)

	def measureframe_measure_handler(self, event):
		self.call_pending_function()

	def measureframe_show(self, show = True):
		if debug: safe_print("measureframe_show", show)
		if show:
			display_no = self.display_ctrl.GetSelection()
			if display_no < 0 or display_no > wx.Display.GetCount() - 1:
				display_no = 0
			x, y = wx.Display(display_no).Geometry[:2]
			self.measureframe.SetPosition((x, y)) # place measure frame on correct display
			self.measureframe_place_n_zoom(*floatlist(self.getcfg("dimensions.measureframe").split(",")))
		else:
			self.setcfg("dimensions.measureframe", self.get_measureframe_dimensions())
			display_no = wx.Display.GetFromWindow(self.measureframe)
			if display_no < 0 or display_no > wx.Display.GetCount() - 1:
				display_no = 0
			self.display_ctrl.SetSelection(display_no)
			self.display_ctrl_handler(CustomEvent(wx.EVT_COMBOBOX.typeId, self.display_ctrl))
		wx.CallAfter(self.measureframe.Show, show)

	def measureframe_hide(self):
		self.measureframe_show(False)

	def measureframe_place_n_zoom(self, x = None, y = None, scale = None):
		if debug: safe_print("measureframe_place_n_zoom")
		cur_x, cur_y, cur_scale = floatlist(self.get_measureframe_dimensions().split(","))
		if None in (x, y, scale):
			if x is None:
				x = cur_x
			if y is None:
				y = cur_y
			if scale is None:
				scale = cur_scale
		if scale > 50.0: # Argyll max
			scale = 50
		if debug: safe_print(" x:", x)
		if debug: safe_print(" y:", y)
		if debug: safe_print(" scale:", scale)
		if debug: safe_print(" scale_adjustment_factor:", scale_adjustment_factor)
		scale /= scale_adjustment_factor
		if debug: safe_print(" scale / scale_adjustment_factor:", scale)
		display = get_display(self.measureframe)
		display_client_rect = display.ClientArea
		if debug: safe_print(" display_client_rect:", display_client_rect)
		display_client_size = display_client_rect[2:]
		if debug: safe_print(" display_client_size:", display_client_size)
		measureframe_min_size = list(self.measureframe.GetMinSize())
		if debug: safe_print(" measureframe_min_size:", measureframe_min_size)
		measureframe_size = [min(display_client_size[0], self.getdefault("size.measureframe") * scale), min(display_client_size[1], self.getdefault("size.measureframe") * scale)]
		if measureframe_min_size[0] > measureframe_size[0]:
			measureframe_size = measureframe_min_size
		if measureframe_size[0] > display_client_size[0]:
			measureframe_size[0] = display_client_size[0]
		if measureframe_size[1] > display_client_size[1]:
			measureframe_size[1] = display_client_size[1]
		if max(measureframe_size) >= max(display_client_size):
			scale = 50
		if debug: safe_print(" measureframe_size:", measureframe_size)
		self.measureframe.SetSize(measureframe_size)
		display_rect = display.Geometry
		if debug: safe_print(" display_rect:", display_rect)
		display_size = display_rect[2:]
		if debug: safe_print(" display_size:", display_size)
		measureframe_pos = [display_rect[0] + round((display_size[0] - measureframe_size[0]) * x), display_rect[1] + round((display_size[1] - measureframe_size[1]) * y)]
		if measureframe_pos[0] < display_client_rect[0]:
			measureframe_pos[0] = display_client_rect[0]
		if measureframe_pos[1] < display_client_rect[1]:
			measureframe_pos[1] = display_client_rect[1]
		if debug: safe_print(" measureframe_pos:", measureframe_pos)
		self.setcfg("dimensions.measureframe", ",".join(strlist((x, y, scale))))
		wx.CallAfter(self.measureframe.SetPosition, measureframe_pos)

	def measureframe_zoomin_handler(self, event):
		if debug: safe_print("measureframe_zoomin_handler")
		# we can't use self.get_measureframe_dimensions() here because if we are near fullscreen, next magnification step will be larger than normal
		display = get_display(self.measureframe)
		display_size = display.Geometry[2:]
		default_measureframe_size = self.getdefault("size.measureframe"), self.getdefault("size.measureframe")
		measureframe_size = floatlist(self.measureframe.GetSize())
		x, y = None, None
		self.measureframe_place_n_zoom(x, y, scale = (display_size[0] / default_measureframe_size[0]) / (display_size[0] / measureframe_size[0]) + .125)

	def measureframe_zoomout_handler(self, event):
		if debug: safe_print("measureframe_zoomout_handler")
		# we can't use self.get_measureframe_dimensions() here because if we are fullscreen, scale will be 50, thus changes won't be visible quickly
		display = get_display(self.measureframe)
		display_size = display.Geometry[2:]
		default_measureframe_size = self.getdefault("size.measureframe"), self.getdefault("size.measureframe")
		measureframe_size = floatlist(self.measureframe.GetSize())
		x, y = None, None
		self.measureframe_place_n_zoom(x, y, scale = (display_size[0] / default_measureframe_size[0]) / (display_size[0] / measureframe_size[0]) - .125)

	def measureframe_zoomnormal_handler(self, event):
		if debug: safe_print("measureframe_zoomnormal_handler")
		x, y = None, None
		self.measureframe_place_n_zoom(x, y, scale = floatlist(self.defaults["dimensions.measureframe"].split(","))[2])

	def measureframe_zoommax_handler(self, event):
		if debug: safe_print("measureframe_zoommax_handler")
		display = get_display(self.measureframe)
		display_client_rect = display.ClientArea
		if debug: safe_print(" display_client_rect:", display_client_rect)
		display_client_size = display.ClientArea[2:]
		if debug: safe_print(" display_client_size:", display_client_size)
		measureframe_size = self.measureframe.GetSize()
		if debug: safe_print(" measureframe_size:", measureframe_size)
		if max(measureframe_size) >= max(display_client_size) - 50:
			self.measureframe_place_n_zoom(*floatlist(self.getcfg("dimensions.measureframe.unzoomed").split(",")))
		else:
			self.setcfg("dimensions.measureframe.unzoomed", self.get_measureframe_dimensions())
			self.measureframe_place_n_zoom(x = .5, y = .5, scale = 50.0)

	def measureframe_center_handler(self, event):
		if debug: safe_print("measureframe_center_handler")
		x, y = floatlist(self.defaults["dimensions.measureframe"].split(","))[:2]
		self.measureframe_place_n_zoom(x, y)

	def measureframe_close_handler(self, event):
		if debug: safe_print("measureframe_close_handler")
		self.measureframe_hide()
		self.ShowAll()

	def measureframe_sizing_handler(self, event):
		if debug: safe_print("measureframe_sizing_handler")

	def measureframe_size_handler(self, event):
		if debug: safe_print("measureframe_size_handler")
		display = get_display(self.measureframe)
		display_client_size = display.ClientArea[2:]
		measureframe_size = self.measureframe.GetSize()
		if debug:
			safe_print(" display_client_size:", display_client_size)
			safe_print(" measureframe_size:", measureframe_size)
			measureframe_pos = self.measureframe.GetScreenPosition()
			safe_print(" measureframe_pos:", measureframe_pos)
		if min(measureframe_size) < min(display_client_size) - 50 and measureframe_size[0] != measureframe_size[1]:
			if sys.platform != "win32":
				wx.CallAfter(self.measureframe.SetSize, (min(measureframe_size), min(measureframe_size)))
			else:
				self.measureframe.SetSize((min(measureframe_size), min(measureframe_size)))
			if debug: wx.CallAfter(self.get_measureframe_dimensions)
		event.Skip()

	def init_menus(self):
		# menu
		menubar = wx.MenuBar()

		file_ = wx.Menu()
		menuitem = file_.Append(-1, "&" + self.getlstr("calibration.load") + "\tCtrl+O")
		self.Bind(wx.EVT_MENU, self.load_cal_handler, menuitem)
		menuitem = file_.Append(-1, "&" + self.getlstr("testchart.set"))
		self.Bind(wx.EVT_MENU, self.testchart_btn_handler, menuitem)
		menuitem = file_.Append(-1, "&" + self.getlstr("testchart.edit"))
		self.Bind(wx.EVT_MENU, self.create_testchart_btn_handler, menuitem)
		menuitem = file_.Append(-1, "&" + self.getlstr("profile.set_save_path"))
		self.Bind(wx.EVT_MENU, self.profile_save_path_btn_handler, menuitem)
		if sys.platform != "darwin":
			file_.AppendSeparator()
		menuitem = file_.Append(-1, "&" + self.getlstr("menuitem.set_argyll_bin"))
		self.Bind(wx.EVT_MENU, self.set_argyll_bin_handler, menuitem)
		if sys.platform == "darwin":
			self.app.SetMacPreferencesMenuItemId(menuitem.GetId())
		if sys.platform != "darwin":
			file_.AppendSeparator()
		menuitem = file_.Append(-1, "&" + self.getlstr("menuitem.quit") + "\tCtrl+Q")
		self.Bind(wx.EVT_MENU, self.OnClose, menuitem)
		if sys.platform == "darwin":
			self.app.SetMacExitMenuItemId(menuitem.GetId())
		menubar.Append(file_, "&" + self.getlstr("menu.file"))

		extra = wx.Menu()
		menuitem = extra.Append(-1, "&" + self.getlstr("create_profile"))
		menuitem.Enable(bool(len(self.displays)))
		self.Bind(wx.EVT_MENU, self.create_profile_handler, menuitem)
		menuitem = extra.Append(-1, "&" + self.getlstr("install_display_profile"))
		menuitem.Enable(bool(len(self.displays)))
		self.Bind(wx.EVT_MENU, self.install_profile_handler, menuitem)
		menuitem = extra.Append(-1, "&" + self.getlstr("calibration.load_from_cal_or_profile"))
		menuitem.Enable(bool(len(self.displays)))
		self.Bind(wx.EVT_MENU, self.load_profile_cal_handler, menuitem)
		menuitem = extra.Append(-1, "&" + self.getlstr("calibration.load_from_display_profile"))
		menuitem.Enable(bool(len(self.displays)))
		self.Bind(wx.EVT_MENU, self.load_display_profile_cal, menuitem)
		menuitem = extra.Append(-1, "&" + self.getlstr("calibration.reset"))
		menuitem.Enable(bool(len(self.displays)))
		self.Bind(wx.EVT_MENU, self.reset_cal, menuitem)
		menuitem = extra.Append(-1, "&" + self.getlstr("report.calibrated"))
		menuitem.Enable(bool(len(self.displays)) and bool(len(self.comports)))
		self.Bind(wx.EVT_MENU, self.report_calibrated_handler, menuitem)
		menuitem = extra.Append(-1, "&" + self.getlstr("report.uncalibrated"))
		menuitem.Enable(bool(len(self.displays)) and bool(len(self.comports)))
		self.Bind(wx.EVT_MENU, self.report_uncalibrated_handler, menuitem)
		menuitem = extra.Append(-1, "&" + self.getlstr("calibration.verify"))
		menuitem.Enable(bool(len(self.displays)) and bool(len(self.comports)))
		self.Bind(wx.EVT_MENU, self.verify_calibration_handler, menuitem)
		extra.AppendSeparator()
		menuitem = extra.Append(-1, "&" + self.getlstr("detect_displays_and_ports"))
		self.Bind(wx.EVT_MENU, self.check_update_controls, menuitem)
		extra.AppendSeparator()
		menuitem = extra.Append(-1, "&" + self.getlstr("enable_spyder2"))
		self.Bind(wx.EVT_MENU, self.enable_spyder2_handler, menuitem)
		extra.AppendSeparator()
		menuitem = extra.Append(-1, "&" + self.getlstr("restore_defaults"))
		self.Bind(wx.EVT_MENU, self.restore_defaults_handler, menuitem)
		extra.AppendSeparator()
		menuitem = extra.Append(-1, "&" + self.getlstr("infoframe.toggle"))
		self.Bind(wx.EVT_MENU, self.infoframe_toggle_handler, menuitem)
		menubar.Append(extra, "&" + self.getlstr("menu.extra"))

		languages = wx.Menu()
		for lang in ldict:
			if self.lang == lang:
				kind = wx.ITEM_RADIO
			else:
				kind = wx.ITEM_NORMAL
			menuitem = languages.Append(-1, "&" + self.getlstr("language", lang = lang), kind = kind)
			ldict[lang]["id"] = menuitem.GetId() # map numerical event id to language string
			self.Bind(wx.EVT_MENU, self.set_language_handler, menuitem)
		menubar.Append(languages, "&" + self.getlstr("menu.language"))

		help = wx.Menu()
		menuitem = help.Append(-1, "&" + self.getlstr("menu.about"))
		self.Bind(wx.EVT_MENU, self.aboutdialog_handler, menuitem)
		if sys.platform == "darwin":
			self.app.SetMacAboutMenuItemId(menuitem.GetId())
			self.app.SetMacHelpMenuTitleName(self.getlstr("menu.help"))
		menubar.Append(help, "&" + self.getlstr("menu.help"))

		self.SetMenuBar(menubar)


	def init_controls(self):

		# logo
		self.AddToSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.EXPAND)
		self.headercontainer = wx.ScrolledWindow(self.panel, -1, size = (585, 60), style = wx.VSCROLL)
		self.headercontainer.SetScrollRate(0, 0)
		self.AddToSubSizer(self.headercontainer, 1)



		self.AddToSizer(wx.FlexGridSizer(0, 2), flag = wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border = 18)
		self.subsizer[-1].AddGrowableCol(1, 1)

		# calibration file (.cal)
		self.calibration_file_label = wx.StaticText(self.panel, -1, self.getlstr("calibration.file"))
		self.AddToSubSizer(self.calibration_file_label, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border = 8)

		self.calibration_file_ctrl = wx.ComboBox(self.panel, -1, choices = [], style = wx.CB_READONLY)
		self.Bind(wx.EVT_COMBOBOX, self.calibration_file_ctrl_handler, id = self.calibration_file_ctrl.GetId())
		self.AddToSubSizer(self.calibration_file_ctrl, 1, flag = wx.ALIGN_CENTER_VERTICAL)

		self.AddToSubSizer((8, 0))

		self.calibration_file_btn = wx.BitmapButton(self.panel, -1, self.bitmaps["theme/icons/16x16/document-open"], style = wx.NO_BORDER)
		self.Bind(wx.EVT_BUTTON, self.load_cal_handler, id = self.calibration_file_btn.GetId())
		self.AddToSubSizer(self.calibration_file_btn, flag = wx.ALIGN_CENTER_VERTICAL)
		self.calibration_file_btn.UpdateToolTipString(self.getlstr("calibration.load"))

		self.AddToSubSizer((8, 0))

		self.delete_calibration_btn = wx.BitmapButton(self.panel, -1, self.bitmaps["theme/icons/16x16/edit-delete"], style = wx.NO_BORDER)
		self.delete_calibration_btn.SetBitmapDisabled(self.bitmaps["transparent16x16"])
		self.Bind(wx.EVT_BUTTON, self.delete_calibration_handler, id = self.delete_calibration_btn.GetId())
		self.AddToSubSizer(self.delete_calibration_btn, flag = wx.ALIGN_CENTER_VERTICAL)
		self.delete_calibration_btn.UpdateToolTipString(self.getlstr("delete"))

		self.AddToSubSizer((8, 0))

		self.install_profile_btn = wx.BitmapButton(self.panel, -1, self.bitmaps["theme/icons/16x16/install"], style = wx.NO_BORDER)
		self.install_profile_btn.SetBitmapDisabled(self.bitmaps["transparent16x16"])
		self.Bind(wx.EVT_BUTTON, self.install_cal_handler, id = self.install_profile_btn.GetId())
		self.AddToSubSizer(self.install_profile_btn, flag = wx.ALIGN_CENTER_VERTICAL)
		self.install_profile_btn.UpdateToolTipString(self.getlstr("profile.install"))

		self.subsizer.pop()

		self.AddToSubSizer(wx.StaticText(self.panel, -1, "")) # empty cell

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 8)

		# update calibration?
		self.calibration_update_cb = wx.CheckBox(self.panel, -1, self.getlstr("calibration.update"))
		self.calibration_update_cb.SetValue(bool(int(self.getcfg("calibration.update"))))
		self.Bind(wx.EVT_CHECKBOX, self.calibration_update_ctrl_handler, id = self.calibration_update_cb.GetId())
		self.AddToSubSizer(self.calibration_update_cb, flag = wx.ALIGN_CENTER_VERTICAL)

		self.AddToSubSizer((8, 0))

		# update corresponding profile?
		self.profile_update_cb = wx.CheckBox(self.panel, -1, self.getlstr("profile.update"))
		self.profile_update_cb.SetValue(bool(int(self.getcfg("profile.update"))))
		self.Bind(wx.EVT_CHECKBOX, self.profile_update_ctrl_handler, id = self.profile_update_cb.GetId())
		self.AddToSubSizer(self.profile_update_cb, flag = wx.ALIGN_CENTER_VERTICAL)



		# display & instrument
		self.AddToSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.EXPAND)



		# display
		self.AddToSubSizer(wx.StaticBoxSizer(wx.StaticBox(self.panel, -1, self.getlstr("display")), wx.VERTICAL), 1, flag = wx.ALL | wx.EXPAND, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), 1, flag = wx.ALIGN_CENTER_VERTICAL | wx.ALL | wx.EXPAND, border = 5)

		show_lut_ctrl = (len(self.displays) > 1 and False in self.lut_access and True in self.lut_access) or test

		if show_lut_ctrl:
			self.AddToSubSizer(wx.FlexGridSizer(3, 3), 1, flag = wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
			self.subsizer[-1].AddGrowableCol(2, 1)
			self.display_label = wx.StaticText(self.panel, -1, self.getlstr("measure"))
			self.AddToSubSizer(self.display_label, flag = wx.ALIGN_CENTER_VERTICAL)
			self.AddToSubSizer((8, 1))

		self.display_ctrl = wx.ComboBox(self.panel, -1, choices = [], style = wx.CB_READONLY)
		self.Bind(wx.EVT_COMBOBOX, self.display_ctrl_handler, id = self.display_ctrl.GetId())
		if show_lut_ctrl:
			self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), 1, flag = wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
		self.AddToSubSizer(self.display_ctrl, 1, flag = wx.ALIGN_CENTER_VERTICAL)
		if show_lut_ctrl:
			self.subsizer.pop()

		if show_lut_ctrl:
			self.AddToSubSizer((1, 8))
			self.AddToSubSizer((1, 8))
			self.AddToSubSizer((1, 8))
			self.lut_label = wx.StaticText(self.panel, -1, self.getlstr("lut_access"))
			self.AddToSubSizer(self.lut_label, flag = wx.ALIGN_CENTER_VERTICAL)
			self.AddToSubSizer((8, 1))
			self.display_lut_ctrl = wx.ComboBox(self.panel, -1, choices = [], style = wx.CB_READONLY)
			self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), 1, flag = wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
			self.Bind(wx.EVT_COMBOBOX, self.display_lut_ctrl_handler, id = self.display_lut_ctrl.GetId())
			self.AddToSubSizer(self.display_lut_ctrl, 1, flag = wx.ALIGN_CENTER_VERTICAL)
			self.subsizer.pop()
			self.subsizer.pop()
			self.display_lut_link_ctrl = wx.BitmapButton(self.panel, -1, self.bitmaps["theme/icons/16x16/stock_lock-open"], style = wx.NO_BORDER)
			self.Bind(wx.EVT_BUTTON, self.display_lut_link_ctrl_handler, id = self.display_lut_link_ctrl.GetId())
			self.AddToSubSizer(self.display_lut_link_ctrl, flag = wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border = 8)
			self.display_lut_link_ctrl.UpdateToolTipString(self.getlstr("display_lut.link"))

		self.subsizer.pop()

		self.subsizer.pop()



		# instrument
		self.AddToSubSizer(wx.StaticBoxSizer(wx.StaticBox(self.panel, -1, self.getlstr("instrument")), wx.VERTICAL), flag = wx.ALL | wx.EXPAND, border = 8)

		if show_lut_ctrl:
			self.AddToSubSizer(wx.BoxSizer(wx.VERTICAL), 1, flag = wx.ALL | wx.EXPAND, border = 5)
			self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), 1, flag = wx.EXPAND)
		else:
			self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), 1, flag = wx.ALL | wx.EXPAND, border = 5)

		self.comport_ctrl = wx.ComboBox(self.panel, -1, choices = [], style = wx.CB_READONLY, size = (175, -1))
		self.Bind(wx.EVT_COMBOBOX, self.comport_ctrl_handler, id = self.comport_ctrl.GetId())
		self.AddToSubSizer(self.comport_ctrl, 1, flag = wx.ALIGN_CENTER_VERTICAL)

		if show_lut_ctrl:
			self.subsizer.pop()
			self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP, border = 8)

		self.measurement_mode_label = wx.StaticText(self.panel, -1, self.getlstr("measurement_mode"))
		if show_lut_ctrl:
			borders = wx.RIGHT
		else:
			borders = wx.LEFT | wx.RIGHT
		self.AddToSubSizer(self.measurement_mode_label, flag = borders | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.measurement_mode_ctrl = wx.ComboBox(self.panel, -1, size = (65, -1), choices = [""] * 4, style = wx.CB_READONLY)
		self.Bind(wx.EVT_COMBOBOX, self.measurement_mode_ctrl_handler, id = self.measurement_mode_ctrl.GetId())
		self.AddToSubSizer(self.measurement_mode_ctrl, flag = wx.ALIGN_CENTER_VERTICAL)



		# calibration settings sizer
		self.AddToSizer(wx.StaticBoxSizer(wx.StaticBox(self.panel, -1, self.getlstr("calibration.settings")), wx.VERTICAL), 1, flag = wx.RIGHT | wx.LEFT | wx.EXPAND, border = 8)
		self.calpanel = wx.ScrolledWindow(self.panel, -1, style = wx.VSCROLL)
		self.AddToSubSizer(self.calpanel, 1, flag = wx.RIGHT | wx.LEFT | wx.EXPAND, border = 5)
		self.calpanel.sizer = wx.FlexGridSizer(0, 2)
		self.subsizer.append(self.calpanel.sizer)
		self.calpanel.SetSizer(self.calpanel.sizer)



		# whitepoint
		self.whitepoint_label = wx.StaticText(self.calpanel, -1, self.getlstr("whitepoint"))
		self.AddToSubSizer(self.whitepoint_label, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.whitepoint_native_rb = wx.RadioButton(self.calpanel, -1, self.getlstr("native"), (10, 10), style = wx.RB_GROUP)
		self.Bind(wx.EVT_RADIOBUTTON, self.whitepoint_ctrl_handler, id = self.whitepoint_native_rb.GetId())
		self.AddToSubSizer(self.whitepoint_native_rb, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.whitepoint_colortemp_rb = wx.RadioButton(self.calpanel, -1, self.getlstr("whitepoint.colortemp"), (10, 10))
		self.Bind(wx.EVT_RADIOBUTTON, self.whitepoint_ctrl_handler, id = self.whitepoint_colortemp_rb.GetId())
		self.AddToSubSizer(self.whitepoint_colortemp_rb, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.whitepoint_colortemp_textctrl = wx.ComboBox(self.calpanel, -1, "", size = (75, -1), choices = self.whitepoint_presets)
		self.Bind(wx.EVT_COMBOBOX, self.whitepoint_ctrl_handler, id = self.whitepoint_colortemp_textctrl.GetId())
		self.whitepoint_colortemp_textctrl.Bind(wx.EVT_KILL_FOCUS, self.whitepoint_ctrl_handler)
		self.AddToSubSizer(self.whitepoint_colortemp_textctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 0)

		self.whitepoint_colortemp_label = wx.StaticText(self.calpanel, -1, u"° K")
		self.AddToSubSizer(self.whitepoint_colortemp_label, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.whitepoint_colortemp_locus_ctrl = wx.ComboBox(self.calpanel, -1, size = (110, -1), choices = self.whitepoint_colortemp_loci, style = wx.CB_READONLY)
		self.Bind(wx.EVT_COMBOBOX, self.whitepoint_colortemp_locus_ctrl_handler, id = self.whitepoint_colortemp_locus_ctrl.GetId())
		self.AddToSubSizer(self.whitepoint_colortemp_locus_ctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 0)

		self.subsizer.pop()

		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, "")) # empty cell

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.whitepoint_xy_rb = wx.RadioButton(self.calpanel, -1, self.getlstr("whitepoint.xy"), (10, 10))
		self.Bind(wx.EVT_RADIOBUTTON, self.whitepoint_ctrl_handler, id = self.whitepoint_xy_rb.GetId())
		self.AddToSubSizer(self.whitepoint_xy_rb, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.whitepoint_x_textctrl = wx.TextCtrl(self.calpanel, -1, "", size = (70, -1))
		self.whitepoint_x_textctrl.Bind(wx.EVT_KILL_FOCUS, self.whitepoint_ctrl_handler)
		self.AddToSubSizer(self.whitepoint_x_textctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 0)

		self.whitepoint_x_label = wx.StaticText(self.calpanel, -1, u"x")
		self.AddToSubSizer(self.whitepoint_x_label, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.whitepoint_y_textctrl = wx.TextCtrl(self.calpanel, -1, "", size = (70, -1))
		self.whitepoint_y_textctrl.Bind(wx.EVT_KILL_FOCUS, self.whitepoint_ctrl_handler)
		self.AddToSubSizer(self.whitepoint_y_textctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 0)

		self.whitepoint_y_label = wx.StaticText(self.calpanel, -1, u"y")
		self.AddToSubSizer(self.whitepoint_y_label, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.subsizer.pop()



		# white luminance
		self.calibration_luminance_label = wx.StaticText(self.calpanel, -1, self.getlstr("calibration.luminance"))
		self.AddToSubSizer(self.calibration_luminance_label, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.luminance_max_rb = wx.RadioButton(self.calpanel, -1, self.getlstr("maximal"), (10, 10), style = wx.RB_GROUP)
		self.Bind(wx.EVT_RADIOBUTTON, self.luminance_ctrl_handler, id = self.luminance_max_rb.GetId())
		self.AddToSubSizer(self.luminance_max_rb, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.luminance_cdm2_rb = wx.RadioButton(self.calpanel, -1, "", (10, 10))
		self.Bind(wx.EVT_RADIOBUTTON, self.luminance_ctrl_handler, id = self.luminance_cdm2_rb.GetId())
		self.AddToSubSizer(self.luminance_cdm2_rb, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.luminance_textctrl = wx.TextCtrl(self.calpanel, -1, "", size = (50, -1))
		self.luminance_textctrl.Bind(wx.EVT_KILL_FOCUS, self.luminance_ctrl_handler)
		self.AddToSubSizer(self.luminance_textctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 0)

		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, u"cd/m²"), flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.subsizer.pop()



		# black luminance
		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, self.getlstr("calibration.black_luminance")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.black_luminance_min_rb = wx.RadioButton(self.calpanel, -1, self.getlstr("minimal"), (10, 10), style = wx.RB_GROUP)
		self.Bind(wx.EVT_RADIOBUTTON, self.black_luminance_ctrl_handler, id = self.black_luminance_min_rb.GetId())
		self.AddToSubSizer(self.black_luminance_min_rb, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.black_luminance_cdm2_rb = wx.RadioButton(self.calpanel, -1, "", (10, 10))
		self.Bind(wx.EVT_RADIOBUTTON, self.black_luminance_ctrl_handler, id = self.black_luminance_cdm2_rb.GetId())
		self.AddToSubSizer(self.black_luminance_cdm2_rb, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.black_luminance_textctrl = wx.TextCtrl(self.calpanel, -1, "", size = (50, -1))
		self.black_luminance_textctrl.Bind(wx.EVT_KILL_FOCUS, self.black_luminance_ctrl_handler)
		self.AddToSubSizer(self.black_luminance_textctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 0)

		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, u"cd/m²"), flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.subsizer.pop()



		# trc
		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, self.getlstr("trc")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.trc_g_rb = wx.RadioButton(self.calpanel, -1, self.getlstr("trc.gamma"), (10, 10), style = wx.RB_GROUP)
		self.Bind(wx.EVT_RADIOBUTTON, self.trc_ctrl_handler, id = self.trc_g_rb.GetId())
		self.AddToSubSizer(self.trc_g_rb, 1, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.trc_textctrl = wx.ComboBox(self.calpanel, -1, str(self.defaults["gamma"]), size = (60, -1), choices = self.trc_presets)
		self.Bind(wx.EVT_COMBOBOX, self.trc_ctrl_handler, id = self.trc_textctrl.GetId())
		self.trc_textctrl.Bind(wx.EVT_KILL_FOCUS, self.trc_ctrl_handler)
		self.AddToSubSizer(self.trc_textctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 0)

		self.AddToSubSizer((8, 0))

		self.trc_type_ctrl = wx.ComboBox(self.calpanel, -1, size = (100, -1), choices = self.trc_types, style = wx.CB_READONLY)
		self.Bind(wx.EVT_COMBOBOX, self.trc_type_ctrl_handler, id = self.trc_type_ctrl.GetId())
		self.AddToSubSizer(self.trc_type_ctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 0)

		self.subsizer.pop()

		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, "")) # empty cell

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.trc_l_rb = wx.RadioButton(self.calpanel, -1, self.getlstr("trc.lstar"), (10, 10))
		self.Bind(wx.EVT_RADIOBUTTON, self.trc_ctrl_handler, id = self.trc_l_rb.GetId())
		self.AddToSubSizer(self.trc_l_rb, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.trc_rec709_rb = wx.RadioButton(self.calpanel, -1, self.getlstr("trc.rec709"), (10, 10))
		self.Bind(wx.EVT_RADIOBUTTON, self.trc_ctrl_handler, id = self.trc_rec709_rb.GetId())
		self.AddToSubSizer(self.trc_rec709_rb, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.trc_smpte240m_rb = wx.RadioButton(self.calpanel, -1, self.getlstr("trc.smpte240m"), (10, 10))
		self.Bind(wx.EVT_RADIOBUTTON, self.trc_ctrl_handler, id = self.trc_smpte240m_rb.GetId())
		self.AddToSubSizer(self.trc_smpte240m_rb, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.trc_srgb_rb = wx.RadioButton(self.calpanel, -1, self.getlstr("trc.srgb"), (10, 10))
		self.Bind(wx.EVT_RADIOBUTTON, self.trc_ctrl_handler, id = self.trc_srgb_rb.GetId())
		self.AddToSubSizer(self.trc_srgb_rb, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.subsizer.pop()



		# viewing condition adjustment for ambient in Lux
		self.ambient_viewcond_adjust_cb = wx.CheckBox(self.calpanel, -1, self.getlstr("calibration.ambient_viewcond_adjust"))
		self.AddToSubSizer(self.ambient_viewcond_adjust_cb, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.Bind(wx.EVT_CHECKBOX, self.ambient_viewcond_adjust_ctrl_handler, id = self.ambient_viewcond_adjust_cb.GetId())

		self.ambient_viewcond_adjust_textctrl = wx.TextCtrl(self.calpanel, -1, "", size = (50, -1))
		self.ambient_viewcond_adjust_textctrl.Bind(wx.EVT_KILL_FOCUS, self.ambient_viewcond_adjust_ctrl_handler)
		self.AddToSubSizer(self.ambient_viewcond_adjust_textctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 0)

		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, "Lux"), flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.ambient_viewcond_adjust_info = wx.BitmapButton(self.calpanel, -1, self.bitmaps["theme/icons/16x16/dialog-information"], style = wx.NO_BORDER)
		self.ambient_viewcond_adjust_info.SetBitmapDisabled(self.bitmaps["transparent16x16"])
		self.Bind(wx.EVT_BUTTON, self.ambient_viewcond_adjust_info_handler, id = self.ambient_viewcond_adjust_info.GetId())
		self.AddToSubSizer(self.ambient_viewcond_adjust_info, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		self.ambient_viewcond_adjust_info.UpdateToolTipString(wrap(self.getlstr("calibration.ambient_viewcond_adjust.info"), 76))

		self.subsizer.pop()



		# black level output offset
		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, self.getlstr("calibration.black_output_offset")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 3)

		self.black_output_offset_ctrl = wx.Slider(self.calpanel, -1, 0, 0, 100, size = (128, -1))
		self.Bind(wx.EVT_SLIDER, self.black_output_offset_ctrl_handler, id = self.black_output_offset_ctrl.GetId())
		self.AddToSubSizer(self.black_output_offset_ctrl, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.black_output_offset_intctrl = wx.SpinCtrl(self.calpanel, -1, initial = 0, size = (65, -1), min = 0, max = 100)
		self.Bind(wx.EVT_TEXT, self.black_output_offset_ctrl_handler, id = self.black_output_offset_intctrl.GetId())
		self.AddToSubSizer(self.black_output_offset_intctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, "%"), flag = wx.ALIGN_CENTER_VERTICAL)

		self.subsizer.pop()



		# black point hue correction
		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, self.getlstr("calibration.black_point_correction")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 2)

		self.black_point_correction_ctrl = wx.Slider(self.calpanel, -1, 0, 0, 100, size = (128, -1))
		self.Bind(wx.EVT_SLIDER, self.black_point_correction_ctrl_handler, id = self.black_point_correction_ctrl.GetId())
		self.AddToSubSizer(self.black_point_correction_ctrl, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.black_point_correction_intctrl = wx.SpinCtrl(self.calpanel, -1, initial = 0, size = (65, -1), min = 0, max = 100)
		self.Bind(wx.EVT_TEXT, self.black_point_correction_ctrl_handler, id = self.black_point_correction_intctrl.GetId())
		self.AddToSubSizer(self.black_point_correction_intctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, "%"), flag = wx.ALIGN_CENTER_VERTICAL)

		# rate
		if self.defaults["calibration.black_point_rate.enabled"]:
			self.AddToSubSizer(wx.StaticText(self.calpanel, -1, self.getlstr("calibration.black_point_rate")), flag = wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.LEFT, border = 8)
			self.black_point_rate_ctrl = wx.Slider(self.calpanel, -1, 400, 5, 2000, size = (64, -1))
			self.Bind(wx.EVT_SLIDER, self.black_point_rate_ctrl_handler, id = self.black_point_rate_ctrl.GetId())
			self.AddToSubSizer(self.black_point_rate_ctrl, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 4)
			self.black_point_rate_intctrl = wx.SpinCtrl(self.calpanel, -1, initial = 400, size = (55, -1), min = 5, max = 2000)
			self.Bind(wx.EVT_TEXT, self.black_point_rate_ctrl_handler, id = self.black_point_rate_intctrl.GetId())
			self.AddToSubSizer(self.black_point_rate_intctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.subsizer.pop()



		# calibration quality
		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, self.getlstr("calibration.quality")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 3)

		self.calibration_quality_ctrl = wx.Slider(self.calpanel, -1, 2, 1, 3, size = (64, -1))
		self.Bind(wx.EVT_SLIDER, self.calibration_quality_ctrl_handler, id = self.calibration_quality_ctrl.GetId())
		self.AddToSubSizer(self.calibration_quality_ctrl, 1, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.calibration_quality_info = wx.StaticText(self.calpanel, -1, "-", size = (50, -1))
		self.AddToSubSizer(self.calibration_quality_info, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		# interactive display adjustment?
		self.interactive_display_adjustment_cb = wx.CheckBox(self.calpanel, -1, self.getlstr("calibration.interactive_display_adjustment"))
		self.Bind(wx.EVT_CHECKBOX, self.interactive_display_adjustment_ctrl_handler, id = self.interactive_display_adjustment_cb.GetId())
		self.AddToSubSizer(self.interactive_display_adjustment_cb, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 10)

		self.subsizer.pop()



		# profiling settings
		self.AddToSizer(wx.StaticBoxSizer(wx.StaticBox(self.panel, -1, self.getlstr("profile.settings")), wx.VERTICAL), flag = wx.TOP | wx.RIGHT | wx.LEFT | wx.EXPAND, border = 8)
		self.AddToSubSizer(wx.FlexGridSizer(0, 2), flag = wx.RIGHT | wx.LEFT | wx.EXPAND, border = 5)
		self.subsizer[-1].AddGrowableCol(1, 1)


		# testchart file
		self.AddToSubSizer(wx.StaticText(self.panel, -1, self.getlstr("testchart.file")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border = 5)

		self.testchart_ctrl = wx.ComboBox(self.panel, -1, choices = [], style = wx.CB_READONLY)
		self.Bind(wx.EVT_COMBOBOX, self.testchart_ctrl_handler, id = self.testchart_ctrl.GetId())
		self.AddToSubSizer(self.testchart_ctrl, 1, flag = wx.ALIGN_CENTER_VERTICAL)

		self.AddToSubSizer((8, 0))

		self.testchart_btn = wx.BitmapButton(self.panel, -1, self.bitmaps["theme/icons/16x16/document-open"], style = wx.NO_BORDER)
		self.testchart_btn.SetBitmapDisabled(self.bitmaps["transparent16x16"])
		self.Bind(wx.EVT_BUTTON, self.testchart_btn_handler, id = self.testchart_btn.GetId())
		self.AddToSubSizer(self.testchart_btn, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		self.testchart_btn.UpdateToolTipString(self.getlstr("testchart.set"))

		self.create_testchart_btn = wx.BitmapButton(self.panel, -1, self.bitmaps["theme/icons/16x16/rgbsquares"], style = wx.NO_BORDER)
		self.create_testchart_btn.SetBitmapDisabled(self.bitmaps["transparent16x16"])
		self.Bind(wx.EVT_BUTTON, self.create_testchart_btn_handler, id = self.create_testchart_btn.GetId())
		self.AddToSubSizer(self.create_testchart_btn, flag = wx.ALIGN_CENTER_VERTICAL)
		self.create_testchart_btn.UpdateToolTipString(self.getlstr("testchart.edit"))

		self.testchart_patches_amount = wx.StaticText(self.panel, -1, " ", size = (50, -1))
		self.AddToSubSizer(self.testchart_patches_amount, flag = wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		self.testchart_patches_amount.UpdateToolTipString(self.getlstr("testchart.info"))

		self.subsizer.pop()



		# profile quality
		self.AddToSubSizer(wx.StaticText(self.panel, -1, self.getlstr("profile.quality")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 2)

		self.profile_quality_ctrl = wx.Slider(self.panel, -1, 2, 1, 3, size = (64, -1))
		self.Bind(wx.EVT_SLIDER, self.profile_quality_ctrl_handler, id = self.profile_quality_ctrl.GetId())
		self.AddToSubSizer(self.profile_quality_ctrl, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.profile_quality_info = wx.StaticText(self.panel, -1, "-", size = (50, -1))
		self.AddToSubSizer(self.profile_quality_info, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 20)

		# profile type
		self.AddToSubSizer(wx.StaticText(self.panel, -1, self.getlstr("profile.type")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		self.profile_type_ctrl = wx.ComboBox(self.panel, -1, size = (85, -1), choices = self.profile_types, style = wx.CB_READONLY)
		self.Bind(wx.EVT_COMBOBOX, self.profile_type_ctrl_handler, id = self.profile_type_ctrl.GetId())
		self.AddToSubSizer(self.profile_type_ctrl, flag = wx.ALIGN_CENTER_VERTICAL)

		self.AddToSubSizer((8, 0))

		# advanced (gamut mapping)
		label = self.getlstr("profile.advanced_gamap")
		self.gamap_btn = wx.Button(self.panel, -1, label)
		self.gamap_btn.SetInitialSize((self.gamap_btn.GetSize()[0] + btn_width_correction, -1))
		self.Bind(wx.EVT_BUTTON, self.gamap_btn_handler, id = self.gamap_btn.GetId())
		self.AddToSubSizer(self.gamap_btn, flag = wx.ALIGN_CENTER_VERTICAL)

		self.subsizer.pop()



		# profile name
		self.AddToSubSizer(wx.StaticText(self.panel, -1, self.getlstr("profile.name")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border = 4)

		self.profile_name_textctrl = wx.TextCtrl(self.panel, -1, "")
		self.Bind(wx.EVT_TEXT, self.profile_name_ctrl_handler, id = self.profile_name_textctrl.GetId())
		self.AddToSubSizer(self.profile_name_textctrl, 1, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		# self.profile_name_textctrl.UpdateToolTipString(wrap(self.profile_name_info(), 76))

		self.profile_name_info_btn = wx.BitmapButton(self.panel, -1, self.bitmaps["theme/icons/16x16/dialog-information"], style = wx.NO_BORDER)
		self.profile_name_info_btn.SetBitmapDisabled(self.bitmaps["transparent16x16"])
		self.Bind(wx.EVT_BUTTON, self.profile_name_info_btn_handler, id = self.profile_name_info_btn.GetId())
		self.AddToSubSizer(self.profile_name_info_btn, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		self.profile_name_info_btn.UpdateToolTipString(wrap(self.profile_name_info(), 76))

		self.profile_save_path_btn = wx.BitmapButton(self.panel, -1, self.bitmaps["theme/icons/16x16/media-floppy"], style = wx.NO_BORDER)
		self.profile_save_path_btn.SetBitmapDisabled(self.bitmaps["transparent16x16"])
		self.Bind(wx.EVT_BUTTON, self.profile_save_path_btn_handler, id = self.profile_save_path_btn.GetId())
		self.AddToSubSizer(self.profile_save_path_btn, flag = wx.ALIGN_CENTER_VERTICAL)
		self.profile_save_path_btn.UpdateToolTipString(self.getlstr("profile.set_save_path"))

		self.AddToSubSizer(wx.StaticText(self.panel, -1, "", size = (50, -1)), flag = wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.subsizer.pop()

		self.AddToSubSizer(wx.StaticText(self.panel, -1, ""), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		
		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border = 4)
		
		self.profile_name = wx.StaticText(self.panel, -1, " ")
		self.AddToSubSizer(self.profile_name, 1, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		# self.create_profile_name_btn = wx.BitmapButton(self.panel, -1, self.bitmaps["theme/icons/16x16/stock_refresh"], style = wx.NO_BORDER)
		# self.create_profile_name_btn.SetBitmapDisabled(self.bitmaps["transparent16x16"])
		# self.Bind(wx.EVT_BUTTON, self.create_profile_name_btn_handler, id = self.create_profile_name_btn.GetId())
		# self.AddToSubSizer(self.create_profile_name_btn, flag = wx.ALIGN_CENTER_VERTICAL)
		# self.create_profile_name_btn.UpdateToolTipString(self.getlstr("profile.name.create"))

		# self.AddToSubSizer(wx.StaticText(self.panel, -1, "", size = (50, -1)), flag = wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		
		self.subsizer.pop()



		# buttons
		self.AddToSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER, border = 16)

		# NOTE on the commented out lines below: If we ever get a working wexpect (pexpect for Windows), we could implement those

		#self.blacklevel_btn = wx.BitmapButton(self.panel, -1, self.bitmaps["theme/icons/16x16/blacklevel"], style = wx.NO_BORDER)
		#self.Bind(wx.EVT_BUTTON, self.blacklevel_btn_handler, id = self.blacklevel_btn.GetId())
		#self.AddToSubSizer(self.blacklevel_btn, flag = wx.ALIGN_CENTER_VERTICAL)

		#self.AddToSubSizer((16, 0))

		#self.whitelevel_btn = wx.BitmapButton(self.panel, -1, self.bitmaps["theme/icons/16x16/whitelevel"], style = wx.NO_BORDER)
		#self.Bind(wx.EVT_BUTTON, self.whitelevel_btn_handler, id = self.whitelevel_btn.GetId())
		#self.AddToSubSizer(self.whitelevel_btn, flag = wx.ALIGN_CENTER_VERTICAL)

		#self.AddToSubSizer((16, 0))

		#self.whitepoint_btn = wx.BitmapButton(self.panel, -1, self.bitmaps["theme/icons/16x16/whitepoint"], style = wx.NO_BORDER)
		#self.Bind(wx.EVT_BUTTON, self.whitepoint_btn_handler, id = self.whitepoint_btn.GetId())
		#self.AddToSubSizer(self.whitepoint_btn, flag = wx.ALIGN_CENTER_VERTICAL)

		#self.AddToSubSizer((16, 0))

		#self.blackpoint_btn = wx.BitmapButton(self.panel, -1, self.bitmaps["theme/icons/16x16/blackpoint"], style = wx.NO_BORDER)
		#self.Bind(wx.EVT_BUTTON, self.blackpoint_btn_handler, id = self.blackpoint_btn.GetId())
		#self.AddToSubSizer(self.blackpoint_btn, flag = wx.ALIGN_CENTER_VERTICAL)

		#self.AddToSubSizer((16, 0))

		label = self.getlstr("button.calibrate")
		self.calibrate_btn = wx.Button(self.panel, -1, label)
		self.calibrate_btn.SetInitialSize((self.calibrate_btn.GetSize()[0] + btn_width_correction, -1))
		self.Bind(wx.EVT_BUTTON, self.calibrate_btn_handler, id = self.calibrate_btn.GetId())
		self.AddToSubSizer(self.calibrate_btn, flag = wx.ALIGN_CENTER_VERTICAL)

		self.AddToSubSizer((16, 0))

		label = self.getlstr("button.calibrate_and_profile")
		self.calibrate_and_profile_btn = wx.Button(self.panel, -1, label)
		self.calibrate_and_profile_btn.SetInitialSize((self.calibrate_and_profile_btn.GetSize()[0] + btn_width_correction, -1))
		self.Bind(wx.EVT_BUTTON, self.calibrate_and_profile_btn_handler, id = self.calibrate_and_profile_btn.GetId())
		self.AddToSubSizer(self.calibrate_and_profile_btn, flag = wx.ALIGN_CENTER_VERTICAL)

		self.AddToSubSizer((16, 0))

		label = self.getlstr("button.profile")
		self.profile_btn = wx.Button(self.panel, -1, label)
		self.profile_btn.SetInitialSize((self.profile_btn.GetSize()[0] + btn_width_correction, -1))
		self.Bind(wx.EVT_BUTTON, self.profile_btn_handler, id = self.profile_btn.GetId())
		self.AddToSubSizer(self.profile_btn, flag = wx.ALIGN_CENTER_VERTICAL)

		self.Children[0].Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
	
	def fixup(self):
		"""
		fixup will try to work around ComboBox issues (does not receive focus events) under Mac OS X and also decrease default fontsize of most controls if beyond 11pt.
		In the process, it also gives most controls (sans StaticTexts) unique names.
		"""
		for item in self.static_labels:
			self.set_font_size(item)
		for name in dir(self):
			if name[-4:] in ("ctrl", "_btn") or name[-3:] in ("_cb", "_rb"):
				attr = getattr(self, name)
				attr.SetName(name)
				self.set_font_size(attr)
				if sys.platform == "darwin" or debug:
					if isinstance(attr, wx.ComboBox):
						if attr.IsEditable():
							if debug: safe_print("Binding EVT_TEXT to", name)
							attr.Bind(wx.EVT_TEXT, self.focus_handler)
					else:
						attr.Bind(wx.EVT_SET_FOCUS, self.focus_handler)

	def focus_handler(self, event):
		if hasattr(self, "last_focused_object") and self.last_focused_object and self.last_focused_object != event.GetEventObject():
			catchup_event = wx.FocusEvent(wx.EVT_KILL_FOCUS.typeId, self.last_focused_object.GetId())
			if debug: safe_print("last_focused_object ID %s %s ProcessEvent TYPE %s %s" % (self.last_focused_object.GetId(), self.last_focused_object.GetName(), catchup_event.GetEventType(), getevttype(catchup_event)))
			if self.last_focused_object.ProcessEvent(catchup_event):
				if debug: safe_print("last_focused_object.ProcessEvent(catchup_event) TRUE")
				event.Skip()
				event = CustomEvent(event.GetEventType(), event.GetEventObject(), self.last_focused_object)
		if hasattr(event.GetEventObject, "GetId") and callable(event.GetEventObject.GetId):
			self.last_focused_object = event.GetEventObject()
		if debug:
			if hasattr(event, "GetWindow") and event.GetWindow():
				safe_print("focus_handler TO-ID %s %s FROM-ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetWindow().GetId(), event.GetWindow().GetName(), event.GetEventType(), getevttype(event)))
			else:
				safe_print("focus_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		event.Skip()

	def set_font_size(self, item):
		pointsize = 11
		font = item.GetFont()
		if font.GetPointSize() > pointsize:
			font.SetPointSize(pointsize)
			item.SetFont(font)

	def AddToSizer(self, item, proportion = 0, flag = 0, border = 0, userData = None):
		self.sizer.Add(item, proportion, flag, border, userData)
		if isSizer(item):
			self.subsizer.append(item)
		elif isinstance(item, wx.StaticText):
			self.static_labels += [item]
		return item

	def AddToSubSizer(self, item, proportion = 0, flag = 0, border = 0, userData = None):
		self.subsizer[-1].Add(item, proportion, flag, border, userData)
		if isSizer(item):
			self.subsizer.append(item)
		elif isinstance(item, wx.StaticText):
			self.static_labels += [item]
		return item

	def getlstr(self, id_str, strvars = None, lang = None):
		if not lang:
			lang = self.lang
		if not lang in ldict or not id_str in ldict[lang]:
			# fall back to english
			lang = "en"
		if lang in ldict and id_str in ldict[lang]:
			lstr = ldict[lang][id_str]
			if strvars:
				if type(strvars) not in (list, tuple):
					strvars = (strvars, )
				if lstr.count("%s") == len(strvars):
					lstr %= strvars
			return lstr
		else:
			return id_str

	def set_language_handler(self, event):
		for lang in ldict:
			if ldict[lang]["id"] == event.GetId():
				self.setcfg("lang", lang)
				self.write_cfg()
				InfoDialog(self, msg = self.getlstr("app.restart_request"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-information"], logit = False)
				break

	def restore_defaults_handler(self, event = None, include = (), exclude = ()):
		if event:
			dlg = ConfirmDialog(self, msg = self.getlstr("app.confirm_restore_defaults"), ok = self.getlstr("ok"), cancel = self.getlstr("cancel"), bitmap = self.bitmaps["theme/icons/32x32/dialog-warning"])
			result = dlg.ShowModal()
			dlg.Destroy()
			if result != wx.ID_OK: return
		skip = [
			"argyll.dir",
			"gamap_profile",
			"gamma",
			"last_cal_path",
			"last_cal_or_icc_path",
			"last_filedialog_path",
			"last_icc_path",
			"last_ti1_path",
			"last_ti3_path",
			"profile.save_path",
			"position.x",
			"position.y",
			"position.info.x",
			"position.info.y",
			"recent_cals",
			"tc_precond_profile"
		]
		override = {
			"calibration.black_luminance": None,
			"calibration.file": None,
			"calibration.luminance": None,
			"trc": self.defaults["gamma"],
			"whitepoint.colortemp": None,
			"whitepoint.x": None,
			"whitepoint.y": None
		}
		for name in self.defaults:
			if name not in skip and name not in override:
				if (len(include) == 0 or False in [name.find(item) < 0 for item in include]) and (len(exclude) == 0 or not (False in [name.find(item) < 0 for item in exclude])):
					if verbose >= 2: safe_print("Restoring %s to %s" % (name, self.defaults[name]))
					self.setcfg(name, self.defaults[name])
		for name in override:
			if (len(include) == 0 or False in [name.find(item) < 0 for item in include]) and (len(exclude) == 0 or not (False in [name.find(item) < 0 for item in exclude])):
				self.setcfg(name, override[name])
		if event:
			self.write_cfg()
			self.update_displays()
			self.update_controls()
			if hasattr(self, "tcframe"):
				self.tc_update_controls()

	def cal_changed(self, setchanged = True):
		if not self.updatingctrls:
			if setchanged:
				self.setcfg("settings.changed", 1)
			self.options_dispcal = []
			if debug: safe_print("cal_changed")
			if self.getcfg("calibration.file"):
				self.setcfg("calibration.file", None)
				self.load_display_profile_cal(None) # load LUT curves from current display profile (if any, and if it contains curves)
			self.calibration_file_ctrl.SetStringSelection(self.getlstr("settings.new"))
			self.calibration_file_ctrl.SetToolTip(None)
			self.delete_calibration_btn.Disable()
			self.install_profile_btn.Disable()
			do_update_controls = self.calibration_update_cb.GetValue() or self.profile_update_cb.GetValue()
			self.calibration_update_cb.SetValue(False)
			self.calibration_update_cb.Disable()
			self.profile_update_cb.SetValue(False)
			self.profile_update_cb.Disable()
			if do_update_controls:
				self.update_controls()
			self.settings_discard_changes(keep_changed_state = True)

	def update_displays(self):
		self.display_ctrl.Freeze()
		self.display_ctrl.SetItems(self.displays)
		display_ctrl_enable = bool(len(self.displays))
		display_no = int(self.getcfg("display.number")) - 1
		self.display_ctrl.SetSelection(min(len(self.displays) - 1, display_no))
		self.display_ctrl.Enable(display_ctrl_enable)
		if hasattr(self, "display_lut_ctrl"):
			self.display_lut_ctrl.Clear()
			i = 0
			for disp in self.displays:
				if self.lut_access[i]:
					self.display_lut_ctrl.Append(disp)
				i += 1
			self.display_lut_link_ctrl_handler(CustomEvent(wx.EVT_BUTTON.typeId, self.display_lut_link_ctrl), bool(int(self.getcfg("display_lut.link"))))
		self.display_ctrl.Thaw()

	def update_comports(self):
		self.comport_ctrl.Freeze()
		self.comport_ctrl.SetItems(self.comports)
		self.comport_ctrl.SetSelection(min(len(self.comports) - 1, int(self.getcfg("comport.number")) - 1))
		self.comport_ctrl.Enable(bool(len(self.comports)))
		self.comport_ctrl.Thaw()
		self.update_measurement_modes()
	
	def update_measurement_modes(self):
		measurement_modes = {
			"color": [
				"CRT",
				"LCD"
			],
			"spect": [
				self.getlstr("default")
			]
		}
		instrument_type = self.get_instrument_type()
		instrument_features = self.get_instrument_features()
		if instrument_features.get("projector_mode"):
			if instrument_type == "spect":
				measurement_modes[instrument_type] += [
					self.getlstr("projector")
				]
			else:
				measurement_modes[instrument_type] += [
					"CRT-" + self.getlstr("projector"),
					"LCD-" + self.getlstr("projector")
				]
		self.measurement_mode_ctrl.Freeze()
		self.measurement_mode_ctrl.SetItems(measurement_modes[instrument_type])
		measurement_mode = self.getcfg("measurement_mode") or self.defaults["measurement_mode"]
		if self.getcfg("projector_mode"):
			measurement_mode += "p"
		self.measurement_mode_ctrl.SetSelection(min(self.measurement_modes_ba[instrument_type].get(measurement_mode, 0), len(measurement_modes[instrument_type]) - 1))
		self.measurement_mode_ctrl.Enable(len(measurement_modes[instrument_type]) > 1)
		self.measurement_mode_ctrl.Thaw()

	def update_main_controls(self):
		update_cal = self.calibration_update_cb.GetValue()
		enable_cal = not(update_cal)

		self.measurement_mode_ctrl.Enable(enable_cal and bool(len(self.displays)) and bool(len(self.measurement_mode_ctrl.GetItems()) > 1))

		update_profile = self.profile_update_cb.GetValue()
		enable_profile = not(update_profile)

		self.calibrate_btn.Enable(bool(len(self.displays)) and True in self.lut_access and bool(len(self.comports)))
		self.calibrate_and_profile_btn.Enable(enable_profile and bool(len(self.displays)) and True in self.lut_access and bool(len(self.comports)))
		self.profile_btn.Enable(enable_profile and bool(len(self.displays)) and bool(len(self.comports)))

	def update_controls(self, update_profile_name = True):
		self.updatingctrls = True
		cal = self.getcfg("calibration.file")

		if cal and self.check_file_isfile(cal):
			filename, ext = os.path.splitext(cal)
			if not cal in self.recent_cals:
				if len(self.recent_cals) > self.getcfg("recent_cals_max"):
					self.recent_cals.remove(self.recent_cals[len(self.presets)])
					self.calibration_file_ctrl.Delete(len(self.presets))
				self.recent_cals.append(cal)
				recent_cals = []
				for recent_cal in self.recent_cals:
					if recent_cal not in self.presets:
						recent_cals += [recent_cal]
				self.setcfg("recent_cals", os.pathsep.join(recent_cals))
				self.calibration_file_ctrl.Append(self.getlstr(os.path.basename(cal)))
			# the case-sensitive index could fail because of case insensitive file systems
			# e.g. the filename string from the cfg is "C:\Users\Name\AppData\dispcalGUI\storage\MyFile",
			# but the actual filename is "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
			# (maybe because the user manually renamed the file)
			try:
				idx = self.recent_cals.index(cal)
			except ValueError, exception:
				idx = indexi(self.recent_cals, cal)
			self.calibration_file_ctrl.SetSelection(idx)
			self.calibration_file_ctrl.UpdateToolTipString(cal)
			if ext.lower() in (".icc", ".icm"):
				profile_path = cal
			else:
				profile_path = filename + profile_ext
			profile_exists = os.path.exists(profile_path)
		else:
			if cal in self.recent_cals:
				# the case-sensitive index could fail because of case insensitive file systems
				# e.g. the filename string from the cfg is "C:\Users\Name\AppData\dispcalGUI\storage\MyFile",
				# but the actual filename is "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
				# (maybe because the user manually renamed the file)
				try:
					idx = self.recent_cals.index(cal)
				except ValueError, exception:
					idx = indexi(self.recent_cals, cal)
				self.recent_cals.remove(cal)
				self.calibration_file_ctrl.Delete(idx)
			cal = None
			self.calibration_file_ctrl.SetStringSelection(self.getlstr("settings.new"))
			self.calibration_file_ctrl.SetToolTip(None)
			self.calibration_update_cb.SetValue(False)
			self.setcfg("calibration.file", None)
			self.setcfg("calibration.update", "0")
			profile_path = None
			profile_exists = False
		self.delete_calibration_btn.Enable(bool(cal) and cal not in self.presets)
		self.install_profile_btn.Enable(profile_exists and cal not in self.presets)
		enable_update = bool(cal) and os.path.exists(filename + ".cal")
		if not enable_update:
			self.calibration_update_cb.SetValue(False)
		self.calibration_update_cb.Enable(enable_update)

		update_cal = self.calibration_update_cb.GetValue()
		enable_cal = not(update_cal)

		if not update_cal or not profile_exists:
			self.profile_update_cb.SetValue(False)
			self.setcfg("profile.update", "0")
		self.profile_update_cb.Enable(update_cal and profile_exists)

		update_profile = self.profile_update_cb.GetValue()
		enable_profile = not(update_profile)

		self.whitepoint_native_rb.Enable(enable_cal)
		self.whitepoint_colortemp_rb.Enable(enable_cal)
		self.whitepoint_colortemp_locus_ctrl.Enable(enable_cal)
		self.whitepoint_xy_rb.Enable(enable_cal)
		self.luminance_max_rb.Enable(enable_cal)
		self.luminance_cdm2_rb.Enable(enable_cal)
		self.black_luminance_min_rb.Enable(enable_cal)
		self.black_luminance_cdm2_rb.Enable(enable_cal)
		self.trc_g_rb.Enable(enable_cal)
		self.trc_l_rb.Enable(enable_cal)
		self.trc_rec709_rb.Enable(enable_cal)
		self.trc_smpte240m_rb.Enable(enable_cal)
		self.trc_srgb_rb.Enable(enable_cal)
		self.ambient_viewcond_adjust_cb.Enable(enable_cal)
		self.ambient_viewcond_adjust_info.Enable(enable_cal)
		self.black_output_offset_ctrl.Enable(enable_cal)
		self.black_output_offset_intctrl.Enable(enable_cal)
		self.black_point_correction_ctrl.Enable(enable_cal)
		self.black_point_correction_intctrl.Enable(enable_cal)
		if hasattr(self, "black_point_rate_ctrl"):
			self.black_point_rate_ctrl.Enable(enable_cal and self.getcfg("calibration.black_point_correction") < 1 and self.defaults["calibration.black_point_rate.enabled"])
			self.black_point_rate_intctrl.Enable(enable_cal and self.getcfg("calibration.black_point_correction") < 1 and self.defaults["calibration.black_point_rate.enabled"])
		self.interactive_display_adjustment_cb.Enable(enable_cal)

		self.testchart_btn.Enable(enable_profile)
		self.create_testchart_btn.Enable(enable_profile)
		self.profile_quality_ctrl.Enable(enable_profile)
		self.profile_type_ctrl.Enable(enable_profile)

		measurement_mode = self.getcfg("measurement_mode") or self.defaults["measurement_mode"]
		if self.getcfg("projector_mode"):
			measurement_mode += "p"
		self.measurement_mode_ctrl.SetSelection(min(self.measurement_modes_ba[self.get_instrument_type()].get(measurement_mode, 0), len(self.measurement_mode_ctrl.GetItems()) - 1))

		self.whitepoint_colortemp_locus_ctrl.SetSelection(self.whitepoint_colortemp_loci_ba.get(self.getcfg("whitepoint.colortemp.locus"), 
			self.whitepoint_colortemp_loci_ba.get(self.defaults["whitepoint.colortemp.locus"])))
		if self.getcfg("whitepoint.colortemp", False):
			self.whitepoint_colortemp_rb.SetValue(True)
			self.whitepoint_colortemp_textctrl.SetValue(str(self.getcfg("whitepoint.colortemp")))
			self.whitepoint_ctrl_handler(CustomEvent(wx.EVT_RADIOBUTTON.typeId, self.whitepoint_colortemp_rb), False)
			self.whitepoint_colortemp_locus_ctrl.Enable(enable_cal)
		elif self.getcfg("whitepoint.x", False) and self.getcfg("whitepoint.y", False):
			self.whitepoint_xy_rb.SetValue(True)
			self.whitepoint_x_textctrl.ChangeValue(str(self.getcfg("whitepoint.x")))
			self.whitepoint_y_textctrl.ChangeValue(str(self.getcfg("whitepoint.y")))
			self.whitepoint_ctrl_handler(CustomEvent(wx.EVT_RADIOBUTTON.typeId, self.whitepoint_xy_rb), False)
			self.whitepoint_colortemp_locus_ctrl.Disable()
		else:
			self.whitepoint_native_rb.SetValue(True)
		self.whitepoint_colortemp_textctrl.Enable(enable_cal and bool(self.getcfg("whitepoint.colortemp", False)))
		self.whitepoint_x_textctrl.Enable(enable_cal and bool(self.getcfg("whitepoint.x", False)))
		self.whitepoint_y_textctrl.Enable(enable_cal and bool(self.getcfg("whitepoint.y", False)))

		if self.getcfg("calibration.luminance", False):
			self.luminance_cdm2_rb.SetValue(True)
		else:
			self.luminance_max_rb.SetValue(True)
		self.luminance_textctrl.ChangeValue(str(self.getcfg("calibration.luminance")))
		self.luminance_textctrl.Enable(enable_cal and bool(self.getcfg("calibration.luminance", False)))

		if self.getcfg("calibration.black_luminance", False):
			self.black_luminance_cdm2_rb.SetValue(True)
		else:
			self.black_luminance_min_rb.SetValue(True)
		self.black_luminance_textctrl.ChangeValue(str(self.getcfg("calibration.black_luminance")))
		self.black_luminance_textctrl.Enable(enable_cal and bool(self.getcfg("calibration.black_luminance", False)))

		trc = self.getcfg("trc")
		if trc in ("l", "709", "240", "s"):
			self.trc_textctrl.Disable()
			self.trc_type_ctrl.SetSelection(0)
			self.trc_type_ctrl.Disable()
		if trc == "l":
			self.trc_l_rb.SetValue(True)
		elif trc == "709":
			self.trc_rec709_rb.SetValue(True)
		elif trc == "240":
			self.trc_smpte240m_rb.SetValue(True)
		elif trc == "s":
			self.trc_srgb_rb.SetValue(True)
		elif trc:
			self.trc_g_rb.SetValue(True)
			self.trc_textctrl.SetValue(str(trc))
			self.trc_textctrl.Enable(enable_cal)
			self.trc_type_ctrl.SetSelection(self.trc_types_ba.get(self.getcfg("trc.type"), self.trc_types_ba.get(self.defaults["trc.type"])))
			self.trc_type_ctrl.Enable(enable_cal)

		self.ambient_viewcond_adjust_cb.SetValue(bool(int(self.getcfg("calibration.ambient_viewcond_adjust"))))
		self.ambient_viewcond_adjust_textctrl.ChangeValue(str(self.getcfg("calibration.ambient_viewcond_adjust.lux")))
		self.ambient_viewcond_adjust_textctrl.Enable(enable_cal and bool(int(self.getcfg("calibration.ambient_viewcond_adjust"))))

		self.profile_type_ctrl.SetSelection(self.profile_types_ba.get(self.getcfg("profile.type"), self.profile_types_ba.get(self.defaults["profile.type"])))

		self.black_output_offset_ctrl.SetValue(int(Decimal(str(self.getcfg("calibration.black_output_offset"))) * 100))
		self.black_output_offset_intctrl.SetValue(int(Decimal(str(self.getcfg("calibration.black_output_offset"))) * 100))

		self.black_point_correction_ctrl.SetValue(int(Decimal(str(self.getcfg("calibration.black_point_correction"))) * 100))
		self.black_point_correction_intctrl.SetValue(int(Decimal(str(self.getcfg("calibration.black_point_correction"))) * 100))

		if hasattr(self, "black_point_rate_ctrl"):
			self.black_point_rate_ctrl.SetValue(int(Decimal(str(self.getcfg("calibration.black_point_rate"))) * 100))
			self.black_point_rate_intctrl.SetValue(int(Decimal(str(self.getcfg("calibration.black_point_rate"))) * 100))

		q = self.quality_ba.get(self.getcfg("calibration.quality"), self.quality_ba.get(self.defaults["calibration.quality"]))
		self.calibration_quality_ctrl.SetValue(q)
		if q == 1:
			self.calibration_quality_info.SetLabel(self.getlstr("calibration.quality.low"))
		elif q == 2:
			self.calibration_quality_info.SetLabel(self.getlstr("calibration.quality.medium"))
		elif q == 3:
			self.calibration_quality_info.SetLabel(self.getlstr("calibration.quality.high"))

		self.interactive_display_adjustment_cb.SetValue(enable_cal and bool(int(self.getcfg("calibration.interactive_display_adjustment"))))

		self.testchart_ctrl.Enable(enable_profile)
		if self.set_default_testchart() is None:
			self.set_testchart()

		q = self.quality_ba.get(self.getcfg("profile.quality"), self.quality_ba.get(self.defaults["profile.quality"]))
		self.profile_quality_ctrl.SetValue(q)
		if q == 1:
			self.profile_quality_info.SetLabel(self.getlstr("calibration.quality.low"))
		elif q == 2:
			self.profile_quality_info.SetLabel(self.getlstr("calibration.quality.medium"))
		elif q == 3:
			self.profile_quality_info.SetLabel(self.getlstr("calibration.quality.high"))
		elif q == 4:
			self.profile_quality_info.SetLabel(self.getlstr("calibration.quality.ultra"))

		enable_gamap = self.get_profile_type() in ("l", "x")
		self.gamap_btn.Enable(enable_profile and enable_gamap)

		self.gamap_profile.SetPath(self.getcfg("gamap_profile"))
		self.gamap_perceptual_cb.SetValue(self.getcfg("gamap_perceptual"))
		self.gamap_saturation_cb.SetValue(self.getcfg("gamap_saturation"))
		self.gamap_src_viewcond_ctrl.SetStringSelection(self.viewconds_ab.get(self.getcfg("gamap_src_viewcond"), self.viewconds_ab.get(self.defaults["gamap_src_viewcond"])))
		self.gamap_out_viewcond_ctrl.SetStringSelection(self.viewconds_ab.get(self.getcfg("gamap_out_viewcond"), self.viewconds_ab.get(self.defaults["gamap_out_viewcond"])))
		self.gamap_profile_handler()

		if bool(int(self.getcfg("measure.darken_background"))):
			self.measure_darken_background_cb.SetValue(True)

		self.updatingctrls = False

		if update_profile_name:
			self.profile_name_textctrl.ChangeValue(self.getcfg("profile.name"))
			self.update_profile_name()

		self.update_main_controls()

	def calibration_update_ctrl_handler(self, event):
		if debug: safe_print("calibration_update_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		self.setcfg("calibration.update", int(self.calibration_update_cb.GetValue()))
		self.update_controls()

	def enable_spyder2_handler(self, event):
		if self.check_set_argyll_bin():
			cmd, args = self.get_argyll_util("spyd2en"), ["-v"]
			result = self.exec_cmd(cmd, args, capture_output = True, skip_cmds = True, silent = True)
			if result:
				InfoDialog(self, msg = self.getlstr("enable_spyder2_success"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-information"])
			else:
				# prompt for setup.exe
				defaultDir, defaultFile = os.path.expanduser("~"), "setup.exe"
				dlg = wx.FileDialog(self, self.getlstr("locate_spyder2_setup"), defaultDir = defaultDir, defaultFile = defaultFile, wildcard = "*", style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
				dlg.Center(wx.BOTH)
				result = dlg.ShowModal()
				path = dlg.GetPath()
				dlg.Destroy()
				if result == wx.ID_OK:
					if not os.path.exists(path):
						InfoDialog(self, msg = self.getlstr("file.missing", path), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
						return
					result = self.exec_cmd(cmd, args + [path], capture_output = True, skip_cmds = True, silent = True)
					if result:
						InfoDialog(self, msg = self.getlstr("enable_spyder2_success"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-information"])
					else:
						InfoDialog(self, msg = self.getlstr("enable_spyder2_failure"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])

	def profile_update_ctrl_handler(self, event):
		if debug: safe_print("profile_update_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		self.setcfg("profile.update", int(self.profile_update_cb.GetValue()))
		self.update_controls()

	def profile_quality_warning_handler(self, event):
		q = self.get_profile_quality()
		if q == "u":
			InfoDialog(self, msg = self.getlstr("quality.ultra.warning"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-warning"], logit = False)

	def profile_quality_ctrl_handler(self, event):
		if debug: safe_print("profile_quality_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		q = self.get_profile_quality()
		if q == "l":
			self.profile_quality_info.SetLabel(self.getlstr("calibration.quality.low"))
		elif q == "m":
			self.profile_quality_info.SetLabel(self.getlstr("calibration.quality.medium"))
		elif q == "h":
			self.profile_quality_info.SetLabel(self.getlstr("calibration.quality.high"))
		if q == "u":
			self.profile_quality_info.SetLabel(self.getlstr("calibration.quality.ultra"))
		if q != self.getcfg("profile.quality"):
			self.profile_settings_changed()
		self.setcfg("profile.quality", q)
		self.update_profile_name()
		self.set_default_testchart(False)

	def calibration_file_ctrl_handler(self, event):
		if debug: safe_print("calibration_file_ctrl ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		sel = self.calibration_file_ctrl.GetSelection()
		if sel > 0:
			self.load_cal_handler(None, path = self.recent_cals[sel])
		else:
			self.cal_changed(setchanged = False)
	
	def settings_discard_changes(self, sel = None, keep_changed_state = False):
		if sel is None:
			sel = self.calibration_file_ctrl.GetSelection()
		if not keep_changed_state: self.setcfg("settings.changed", 0)
		items = self.calibration_file_ctrl.GetItems()
		changed = False
		for j in range(len(items)):
			#if j != sel and items[j][0] == "*":
			if items[j][0] == "*":
				items[j] = items[j][2:]
				changed = True
		if changed:
			self.calibration_file_ctrl.Freeze()
			self.calibration_file_ctrl.SetItems(items)
			self.calibration_file_ctrl.SetSelection(sel)
			self.calibration_file_ctrl.Thaw()
			
	def settings_confirm_discard(self):
		sel = self.calibration_file_ctrl.GetSelection()
		# the case-sensitive index could fail because of case insensitive file systems
		# e.g. the filename string from the cfg is "C:\Users\Name\AppData\dispcalGUI\storage\MyFile",
		# but the actual filename is "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
		# (maybe because the user manually renamed the file)
		try:
			idx = self.recent_cals.index(self.getcfg("calibration.file") or "")
		except ValueError, exception:
			idx = indexi(self.recent_cals, self.getcfg("calibration.file") or "")
		self.calibration_file_ctrl.SetSelection(idx)
		dlg = ConfirmDialog(self, msg = self.getlstr("warning.discard_changes"), ok = self.getlstr("ok"), cancel = self.getlstr("cancel"), bitmap = self.bitmaps["theme/icons/32x32/dialog-warning"])
		result = dlg.ShowModal()
		dlg.Destroy()
		if result != wx.ID_OK: return False
		self.settings_discard_changes(sel)
		return True

	def calibration_quality_ctrl_handler(self, event):
		if debug: safe_print("calibration_quality_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		q = self.get_calibration_quality()
		if q == "l":
			self.calibration_quality_info.SetLabel(self.getlstr("calibration.quality.low"))
		elif q == "m":
			self.calibration_quality_info.SetLabel(self.getlstr("calibration.quality.medium"))
		elif q == "h":
			self.calibration_quality_info.SetLabel(self.getlstr("calibration.quality.high"))
		if q != self.getcfg("calibration.quality"):
			self.profile_settings_changed()
		self.setcfg("calibration.quality", q)
		self.update_profile_name()

	def interactive_display_adjustment_ctrl_handler(self, event):
		if debug: safe_print("interactive_display_adjustment_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		v = self.get_interactive_display_adjustment()
		if v != str(self.getcfg("calibration.interactive_display_adjustment")):
			self.profile_settings_changed()
		self.setcfg("calibration.interactive_display_adjustment", v)

	def black_point_correction_ctrl_handler(self, event):
		if debug: safe_print("black_point_correction_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		if event.GetId() == self.black_point_correction_intctrl.GetId():
			self.black_point_correction_ctrl.SetValue(self.black_point_correction_intctrl.GetValue())
		else:
			self.black_point_correction_intctrl.SetValue(self.black_point_correction_ctrl.GetValue())
		v = self.get_black_point_correction()
		if float(v) != self.getcfg("calibration.black_point_correction"):
			self.cal_changed()
		self.setcfg("calibration.black_point_correction", v)
		if hasattr(self, "black_point_rate_ctrl"):
			self.black_point_rate_ctrl.Enable(self.getcfg("calibration.black_point_correction") < 1 and self.defaults["calibration.black_point_rate.enabled"])
			self.black_point_rate_intctrl.Enable(self.getcfg("calibration.black_point_correction") < 1 and self.defaults["calibration.black_point_rate.enabled"])
		self.update_profile_name()

	def black_point_rate_ctrl_handler(self, event):
		if debug: safe_print("black_point_rate_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		if event.GetId() == self.black_point_rate_intctrl.GetId():
			self.black_point_rate_ctrl.SetValue(self.black_point_rate_intctrl.GetValue())
		else:
			self.black_point_rate_intctrl.SetValue(self.black_point_rate_ctrl.GetValue())
		v = self.get_black_point_rate()
		if v != str(self.getcfg("calibration.black_point_rate")):
			self.cal_changed()
		self.setcfg("calibration.black_point_rate", v)
		self.update_profile_name()

	def black_output_offset_ctrl_handler(self, event):
		if debug: safe_print("black_output_offset_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		if event.GetId() == self.black_output_offset_intctrl.GetId():
			self.black_output_offset_ctrl.SetValue(self.black_output_offset_intctrl.GetValue())
		else:
			self.black_output_offset_intctrl.SetValue(self.black_output_offset_ctrl.GetValue())
		v = self.get_black_output_offset()
		if float(v) != self.getcfg("calibration.black_output_offset"):
			self.cal_changed()
		self.setcfg("calibration.black_output_offset", v)
		self.update_profile_name()

	def ambient_viewcond_adjust_ctrl_handler(self, event):
		if event.GetId() == self.ambient_viewcond_adjust_textctrl.GetId() and (not self.ambient_viewcond_adjust_cb.GetValue() or str(float(self.getcfg("calibration.ambient_viewcond_adjust.lux"))) == self.ambient_viewcond_adjust_textctrl.GetValue()):
			event.Skip()
			return
		if debug: safe_print("ambient_viewcond_adjust_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		if event.GetId() == self.ambient_viewcond_adjust_textctrl.GetId():
			if self.ambient_viewcond_adjust_textctrl.GetValue():
				self.ambient_viewcond_adjust_cb.SetValue(True)
			else:
				self.ambient_viewcond_adjust_cb.SetValue(False)
		if self.ambient_viewcond_adjust_cb.GetValue():
			self.ambient_viewcond_adjust_textctrl.Enable()
			value = self.ambient_viewcond_adjust_textctrl.GetValue()
			if value:
				try:
					v = float(value.replace(",", "."))
					if v < 0.000001 or v > 100000:
						raise ValueError()
					self.ambient_viewcond_adjust_textctrl.ChangeValue(str(v))
				except ValueError:
					wx.Bell()
					self.ambient_viewcond_adjust_textctrl.ChangeValue(str(self.getcfg("calibration.ambient_viewcond_adjust.lux")))
			if event.GetId() == self.ambient_viewcond_adjust_cb.GetId():
				self.ambient_viewcond_adjust_textctrl.SetFocus()
				self.ambient_viewcond_adjust_textctrl.SelectAll()
		else:
			self.ambient_viewcond_adjust_textctrl.Disable()
		v1 = int(self.ambient_viewcond_adjust_cb.GetValue())
		v2 = self.ambient_viewcond_adjust_textctrl.GetValue()
		if v1 != self.getcfg("calibration.ambient_viewcond_adjust") or v2 != str(self.getcfg("calibration.ambient_viewcond_adjust.lux", False)):
			self.cal_changed()
		self.setcfg("calibration.ambient_viewcond_adjust", v1)
		self.setcfg("calibration.ambient_viewcond_adjust.lux", v2)
		self.update_profile_name()
		if event.GetEventType() == wx.EVT_KILL_FOCUS.typeId:
			event.Skip()

	def ambient_viewcond_adjust_info_handler(self, event):
		InfoDialog(self, msg = self.getlstr("calibration.ambient_viewcond_adjust.info"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-information"], logit = False)

	def black_luminance_ctrl_handler(self, event):
		if event.GetId() == self.black_luminance_textctrl.GetId() and (not self.black_luminance_cdm2_rb.GetValue() or str(float(self.getcfg("calibration.black_luminance"))) == self.black_luminance_textctrl.GetValue()):
			event.Skip()
			return
		if debug: safe_print("black_luminance_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		if self.black_luminance_cdm2_rb.GetValue(): # cd/m2
			self.black_luminance_textctrl.Enable()
			try:
				v = float(self.black_luminance_textctrl.GetValue().replace(",", "."))
				if v < 0.000001 or v > 100000:
					raise ValueError()
				self.black_luminance_textctrl.ChangeValue(str(v))
			except ValueError:
				wx.Bell()
				self.black_luminance_textctrl.ChangeValue(str(self.getcfg("calibration.black_luminance")))
			if event.GetId() == self.black_luminance_cdm2_rb.GetId():
				self.black_luminance_textctrl.SetFocus()
				self.black_luminance_textctrl.SelectAll()
		else:
			self.black_luminance_textctrl.Disable()
		v = self.get_black_luminance()
		if v != str(self.getcfg("calibration.black_luminance", False)):
			self.cal_changed()
		self.setcfg("calibration.black_luminance", v)
		self.update_profile_name()
		if event.GetEventType() == wx.EVT_KILL_FOCUS.typeId:
			event.Skip()

	def luminance_ctrl_handler(self, event):
		if event.GetId() == self.luminance_textctrl.GetId() and (not self.luminance_cdm2_rb.GetValue() or str(float(self.getcfg("calibration.luminance"))) == self.luminance_textctrl.GetValue()):
			event.Skip()
			return
		if debug: safe_print("luminance_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		if self.luminance_cdm2_rb.GetValue(): # cd/m2
			self.luminance_textctrl.Enable()
			try:
				v = float(self.luminance_textctrl.GetValue().replace(",", "."))
				if v < 0.000001 or v > 100000:
					raise ValueError()
				self.luminance_textctrl.ChangeValue(str(v))
			except ValueError:
				wx.Bell()
				self.luminance_textctrl.ChangeValue(str(self.getcfg("calibration.luminance")))
			if event.GetId() == self.luminance_cdm2_rb.GetId():
				self.luminance_textctrl.SetFocus()
				self.luminance_textctrl.SelectAll()
		else:
			self.luminance_textctrl.Disable()
		v = self.get_luminance()
		if v != str(self.getcfg("calibration.luminance", False)):
			self.cal_changed()
		self.setcfg("calibration.luminance", v)
		self.update_profile_name()
		if event.GetEventType() == wx.EVT_KILL_FOCUS.typeId:
			event.Skip()

	def whitepoint_colortemp_locus_ctrl_handler(self, event):
		if debug: safe_print("whitepoint_colortemp_locus_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		v = self.get_whitepoint_locus()
		if v != self.getcfg("whitepoint.colortemp.locus"):
			self.cal_changed()
		self.setcfg("whitepoint.colortemp.locus", v)
		self.update_profile_name()

	def whitepoint_ctrl_handler(self, event, cal_changed = True):
		if event.GetId() == self.whitepoint_colortemp_textctrl.GetId() and (not self.whitepoint_colortemp_rb.GetValue() or str(float(self.getcfg("whitepoint.colortemp"))) == self.whitepoint_colortemp_textctrl.GetValue()):
			event.Skip()
			return
		if event.GetId() == self.whitepoint_x_textctrl.GetId() and (not self.whitepoint_xy_rb.GetValue() or str(float(self.getcfg("whitepoint.x"))) == self.whitepoint_x_textctrl.GetValue()):
			event.Skip()
			return
		if event.GetId() == self.whitepoint_y_textctrl.GetId() and (not self.whitepoint_xy_rb.GetValue() or str(float(self.getcfg("whitepoint.y"))) == self.whitepoint_y_textctrl.GetValue()):
			event.Skip()
			return
		if debug: safe_print("whitepoint_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		if self.whitepoint_xy_rb.GetValue(): # x,y chromaticity coordinates
			self.whitepoint_colortemp_locus_ctrl.Disable()
			self.whitepoint_colortemp_textctrl.Disable()
			self.whitepoint_x_textctrl.Enable()
			self.whitepoint_y_textctrl.Enable()
			try:
				v = float(self.whitepoint_x_textctrl.GetValue().replace(",", "."))
				if v < 0 or v > 1:
					raise ValueError()
				self.whitepoint_x_textctrl.ChangeValue(str(v))
			except ValueError:
				wx.Bell()
				self.whitepoint_x_textctrl.ChangeValue(str(self.getcfg("whitepoint.x")))
			try:
				v = float(self.whitepoint_y_textctrl.GetValue().replace(",", "."))
				if v < 0 or v > 1:
					raise ValueError()
				self.whitepoint_y_textctrl.ChangeValue(str(v))
			except ValueError:
				wx.Bell()
				self.whitepoint_y_textctrl.ChangeValue(str(self.getcfg("whitepoint.y")))
			x = self.whitepoint_x_textctrl.GetValue().replace(",", ".")
			y = self.whitepoint_y_textctrl.GetValue().replace(",", ".")
			k = xyY2CCT(float(x), float(y), 1.0)
			if k:
				self.whitepoint_colortemp_textctrl.SetValue(str(stripzeroes(math.ceil(k))))
			else:
				self.whitepoint_colortemp_textctrl.SetValue("")
			if cal_changed:
				if not self.getcfg("whitepoint.colortemp") and float(x) == self.getcfg("whitepoint.x") and float(y) == self.getcfg("whitepoint.y"):
					cal_changed = False
			self.setcfg("whitepoint.colortemp", None)
			self.setcfg("whitepoint.x", x)
			self.setcfg("whitepoint.y", y)
			if event.GetId() == self.whitepoint_xy_rb.GetId() and not self.updatingctrls:
				self.whitepoint_x_textctrl.SetFocus()
				self.whitepoint_x_textctrl.SelectAll()
		elif self.whitepoint_colortemp_rb.GetValue():
			self.whitepoint_colortemp_locus_ctrl.Enable()
			self.whitepoint_colortemp_textctrl.Enable()
			self.whitepoint_x_textctrl.Disable()
			self.whitepoint_y_textctrl.Disable()
			try:
				v = float(self.whitepoint_colortemp_textctrl.GetValue().replace(",", "."))
				if v < 1000 or v > 15000:
					raise ValueError()
				self.whitepoint_colortemp_textctrl.SetValue(str(v))
			except ValueError:
				wx.Bell()
				self.whitepoint_colortemp_textctrl.SetValue(str(self.getcfg("whitepoint.colortemp")))
			xyY = CIEDCCT2xyY(float(self.whitepoint_colortemp_textctrl.GetValue().replace(",", ".")))
			if xyY:
				self.whitepoint_x_textctrl.ChangeValue(str(stripzeroes(round(xyY[0], 6))))
				self.whitepoint_y_textctrl.ChangeValue(str(stripzeroes(round(xyY[1], 6))))
			else:
				self.whitepoint_x_textctrl.ChangeValue("")
				self.whitepoint_y_textctrl.ChangeValue("")
			if cal_changed:
				v = float(self.whitepoint_colortemp_textctrl.GetValue())
				if self.getcfg("whitepoint.colortemp") == v and not self.getcfg("whitepoint.x") and not self.getcfg("whitepoint.y"):
					cal_changed = False
			self.setcfg("whitepoint.colortemp", v)
			self.setcfg("whitepoint.x", None)
			self.setcfg("whitepoint.y", None)
			if event.GetId() == self.whitepoint_colortemp_rb.GetId() and not self.updatingctrls:
				self.whitepoint_colortemp_textctrl.SetFocus()
				self.whitepoint_colortemp_textctrl.SelectAll()
		else:
			self.whitepoint_colortemp_locus_ctrl.Enable()
			self.whitepoint_colortemp_textctrl.Disable()
			self.whitepoint_x_textctrl.Disable()
			self.whitepoint_y_textctrl.Disable()
			if not self.getcfg("whitepoint.colortemp") and not self.getcfg("whitepoint.x") and not self.getcfg("whitepoint.y"):
				cal_changed = False
			self.setcfg("whitepoint.colortemp", None)
			self.setcfg("whitepoint.x", None)
			self.setcfg("whitepoint.y", None)
		if cal_changed and not self.updatingctrls:
			self.cal_changed()
			self.update_profile_name()
		if event.GetEventType() == wx.EVT_KILL_FOCUS.typeId:
			event.Skip()

	def trc_type_ctrl_handler(self, event):
		if debug: safe_print("trc_type_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		v = self.get_trc_type()
		if v != self.getcfg("trc.type"):
			self.cal_changed()
		self.setcfg("trc.type", v)
		self.update_profile_name()

	def trc_ctrl_handler(self, event, cal_changed = True):
		if event.GetId() == self.trc_textctrl.GetId() and (not self.trc_g_rb.GetValue() or stripzeroes(self.getcfg("trc")) == stripzeroes(self.trc_textctrl.GetValue())):
			event.Skip()
			return
		if debug: safe_print("trc_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		if self.trc_g_rb.GetValue():
			self.trc_textctrl.Enable()
			self.trc_type_ctrl.Enable()
			try:
				v = float(self.trc_textctrl.GetValue().replace(",", "."))
				if v == 0 or v > 10:
					raise ValueError()
				self.trc_textctrl.SetValue(str(v))
			except ValueError:
				wx.Bell()
				self.trc_textctrl.SetValue(str(self.getcfg("trc")))
			if event.GetId() == self.trc_g_rb.GetId():
				self.trc_textctrl.SetFocus()
				self.trc_textctrl.SelectAll()
		else:
			self.trc_textctrl.Disable()
			self.trc_type_ctrl.Disable()
		trc = self.get_trc()
		if cal_changed:
			if trc != str(self.getcfg("trc")):
				self.cal_changed()
		self.setcfg("trc", trc)
		if cal_changed:
			self.update_profile_name()
		if event.GetEventType() == wx.EVT_KILL_FOCUS.typeId:
			event.Skip()
		if trc in ("240", "709", "s") and not (bool(int(self.getcfg("calibration.ambient_viewcond_adjust"))) and self.getcfg("calibration.ambient_viewcond_adjust.lux")) and self.getcfg("trc.should_use_viewcond_adjust.show_msg"):
			dlg = InfoDialog(self, msg = self.getlstr("trc.should_use_viewcond_adjust"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-information"], show = False, logit = False)
			chk = wx.CheckBox(dlg, -1, self.getlstr("dialog.do_not_show_again"))
			dlg.Bind(wx.EVT_CHECKBOX, self.should_use_viewcond_adjust_handler, id = chk.GetId())
			dlg.sizer3.Add(chk, flag = wx.TOP | wx.ALIGN_LEFT, border = 12)
			dlg.sizer0.SetSizeHints(dlg)
			dlg.sizer0.Layout()
			dlg.ShowModalThenDestroy()

	def should_use_viewcond_adjust_handler(self, event):
		self.setcfg("trc.should_use_viewcond_adjust.show_msg", int(not event.GetEventObject().GetValue()))

	def check_create_dir(self, path, parent = None):
		if parent is None:
			parent = self
		if not os.path.exists(path):
			try:
				os.makedirs(path)
			except Exception, exception:
				InfoDialog(parent, pos = (-1, 100), msg = self.getlstr("error.dir_creation", path) + "\n\n" + unicode(str(exception), enc, "replace"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
				return False
		if not os.path.isdir(path):
			InfoDialog(parent, pos = (-1, 100), msg = self.getlstr("error.dir_notdir", path), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
			return False
		return True

	def check_cal_isfile(self, cal = None, missing_msg = None, notfile_msg = None, parent = None, silent = False):
		if not silent:
			if not missing_msg:
				missing_msg = self.getlstr("error.calibration.file_missing", cal)
			if not notfile_msg:
				notfile_msg = self.getlstr("error.calibration.file_notfile", cal)
		return self.check_file_isfile(cal, missing_msg, notfile_msg, parent, silent)

	def check_profile_isfile(self, profile_path = None, missing_msg = None, notfile_msg = None, parent = None, silent = False):
		if not silent:
			if not missing_msg:
				missing_msg = self.getlstr("error.profile.file_missing", profile_path)
			if not notfile_msg:
				notfile_msg = self.getlstr("error.profile.file_notfile", profile_path)
		return self.check_file_isfile(profile_path, missing_msg, notfile_msg, parent, silent)

	def check_file_isfile(self, filename, missing_msg = None, notfile_msg = None, parent = None, silent = False):
		if parent is None:
			parent = self
		if not os.path.exists(filename):
			if not silent:
				if not missing_msg:
					missing_msg = self.getlstr("file.missing", filename)
				InfoDialog(parent, pos = (-1, 100), msg = missing_msg, ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
			return False
		if not os.path.isfile(filename):
			if not silent:
				if not notfile_msg:
					notfile_msg = self.getlstr("file.notfile", filename)
				InfoDialog(parent, pos = (-1, 100), msg = notfile_msg, ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
			return False
		return True

	def prepare_dispcal(self, calibrate = True, verify = False):
		cmd = self.get_argyll_util("dispcal")
		args = []
		args += ["-v"] # verbose
		args += ["-d" + self.get_display_number()]
		args += ["-c" + self.get_comport_number()]
		measurement_mode = self.get_measurement_mode()
		instrument_features = self.get_instrument_features()
		if measurement_mode:
			if measurement_mode != "p" and not instrument_features.get("spectral"):
				args += ["-y" + measurement_mode[0]] # always specify -y (won't be read from .cal when updating)
			if "p" in measurement_mode and instrument_features.get("projector_mode") and self.argyll_version >= [1, 1, 0]: # projector mode, Argyll >= 1.1.0 Beta
				args += ["-p"]
		args += [("-p" if self.argyll_version <= [1, 0, 4] else "-P") + self.get_measureframe_dimensions()]
		if self.measure_darken_background_cb.GetValue():
			args += ["-F"]
		if instrument_features.get("high_res"):
			args += ["-H"]
		if calibrate:
			args += ["-q" + self.get_calibration_quality()]
			profile_save_path = self.create_tempdir()
			if not profile_save_path or not self.check_create_dir(profile_save_path):
				return None, None
			inoutfile = self.make_argyll_compatible_path(os.path.join(profile_save_path, self.get_profile_name()))
			#
			if self.calibration_update_cb.GetValue():
				cal = self.getcfg("calibration.file")
				calcopy = os.path.join(inoutfile + ".cal")
				filename, ext = os.path.splitext(cal)
				ext = ".cal"
				cal = filename + ext
				if ext.lower() == ".cal":
					if not self.check_cal_isfile(cal):
						return None, None
					if not os.path.exists(calcopy):
						try:
							shutil.copyfile(cal, calcopy) # copy cal to profile dir
						except Exception, exception:
							InfoDialog(self, pos = (-1, 100), msg = self.getlstr("error.copy_failed", (cal, calcopy)) + "\n\n" + unicode(str(exception), enc, "replace"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
							return None, None
						if not self.check_cal_isfile(calcopy):
							return None, None
						cal = calcopy
				else:
					if not self.extract_cal(cal, calcopy):
						return None, None
				#
				if self.profile_update_cb.GetValue():
					profile_path = os.path.splitext(self.getcfg("calibration.file"))[0] + profile_ext
					if not self.check_profile_isfile(profile_path):
						return None, None
					profilecopy = os.path.join(inoutfile + profile_ext)
					if not os.path.exists(profilecopy):
						try:
							shutil.copyfile(profile_path, profilecopy) # copy profile to profile dir
						except Exception, exception:
							InfoDialog(self, pos = (-1, 100), msg = self.getlstr("error.copy_failed", (profile_path, profilecopy)) + "\n\n" + unicode(str(exception), enc, "replace"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
							return None, None
						if not self.check_profile_isfile(profilecopy):
							return None, None
					args += ["-o"]
				args += ["-u"]
		if (calibrate and not self.calibration_update_cb.GetValue()) or (not calibrate and verify):
			if calibrate and not self.interactive_display_adjustment_cb.GetValue():
				args += ["-m"] # skip interactive adjustment
			whitepoint = self.get_whitepoint()
			if not whitepoint or whitepoint.find(",") < 0:
				arg = self.get_whitepoint_locus()
				if whitepoint:
					arg += whitepoint
				args += ["-" + arg]
			else:
				args += ["-w" + whitepoint]
			luminance = self.get_luminance()
			if luminance:
				args += ["-b" + luminance]
			args += ["-" + self.get_trc_type() + self.get_trc()]
			args += ["-f" + self.get_black_output_offset()]
			ambient = self.get_ambient()
			if ambient:
				args += ["-a" + ambient]
			args += ["-k" + self.get_black_point_correction()]
			if hasattr(self, "black_point_rate_ctrl") and self.defaults["calibration.black_point_rate.enabled"] and float(self.get_black_point_correction()) < 1:
				args += ["-A" + self.get_black_point_rate()]
			black_luminance = self.get_black_luminance()
			if black_luminance:
				args += ["-B" + black_luminance]
			if verify:
				if calibrate and type(verify) == int:
					args += ["-e" + verify] # verify final computed curves
				else:
					args += ["-E"] # verify current curves
		self.options_dispcal = list(args)
		if calibrate:
			args += [inoutfile]
		return cmd, args

	def prepare_targen(self, parent):
		path = self.create_tempdir()
		if not path or not self.check_create_dir(path, parent): # check directory and in/output file(s)
			return None, None
		inoutfile = os.path.join(path, "temp")
		cmd = self.get_argyll_util("targen")
		args = []
		args += ['-v']
		args += ['-d3']
		args += ['-e%s' % self.tcframe.tc_white_patches.GetValue()]
		args += ['-s%s' % self.tcframe.tc_single_channel_patches.GetValue()]
		args += ['-g%s' % self.tcframe.tc_gray_patches.GetValue()]
		args += ['-m%s' % self.tcframe.tc_multi_steps.GetValue()]
		if self.tcframe.tc_fullspread_patches.GetValue() > 0:
			args += ['-f%s' % self.tc_get_total_patches()]
			tc_algo = self.tc_algos_ba[self.tcframe.tc_algo.GetStringSelection()]
			if tc_algo:
				args += ['-' + tc_algo]
			if tc_algo in ("i", "I"):
				args += ['-a%s' % (self.tcframe.tc_angle_intctrl.GetValue() / 10000.0)]
			if tc_algo == "":
				args += ['-A%s' % (self.tcframe.tc_adaption_intctrl.GetValue() / 100.0)]
			if self.tcframe.tc_precond.GetValue() and self.tcframe.tc_precond_profile.GetPath():
				args += ['-c']
				args += [self.tcframe.tc_precond_profile.GetPath()]
			if self.tcframe.tc_filter.GetValue():
				args += ['-F%s,%s,%s,%s' % (self.tcframe.tc_filter_L.GetValue(), self.tcframe.tc_filter_a.GetValue(), self.tcframe.tc_filter_b.GetValue(), self.tcframe.tc_filter_rad.GetValue())]
		else:
			args += ['-f0']
		if self.tcframe.tc_vrml.GetValue():
			if self.tcframe.tc_vrml_lab.GetValue():
				args += ['-w']
			if self.tcframe.tc_vrml_device.GetValue():
				args += ['-W']
		self.options_targen = list(args)
		if verbose >= 2: safe_print("Setting targen options:", *self.options_targen)
		args += [inoutfile]
		return cmd, args

	def prepare_dispread(self, apply_calibration = True):
		profile_save_path = self.create_tempdir()
		if not profile_save_path or not self.check_create_dir(profile_save_path): # check directory and in/output file(s)
			return None, None
		inoutfile = self.make_argyll_compatible_path(os.path.join(profile_save_path, self.get_profile_name()))
		if not os.path.exists(inoutfile + ".ti1"):
			filename, ext = os.path.splitext(self.get_testchart())
			if not self.check_file_isfile(filename + ext):
				return None, None
			try:
				if ext.lower() in (".icc", ".icm"):
					try:
						profile = ICCP.ICCProfile(filename + ext)
					except (IOError, ICCP.ICCProfileInvalidError), exception:
						InfoDialog(self, pos = (-1, 100), msg = self.getlstr("error.testchart.read", self.get_testchart()), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
						return None, None
					ti3 = StringIO(profile.tags.get("CIED", ""))
				elif ext.lower() == ".ti1":
					shutil.copyfile(filename + ext, inoutfile + ".ti1")
				else: # ti3
					try:
						ti3 = open(filename + ext, "rU")
					except Exception, exception:
						InfoDialog(self, pos = (-1, 100), msg = self.getlstr("error.testchart.read", self.get_testchart()), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
						return None, None
				if ext.lower() != ".ti1":
					ti3_lines = [line.strip() for line in ti3]
					ti3.close()
					if not "CTI3" in ti3_lines:
						InfoDialog(self, pos = (-1, 100), msg = self.getlstr("error.testchart.invalid", self.get_testchart()), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
						return None, None
					ti1 = open(inoutfile + ".ti1", "w")
					ti1.write(ti3_to_ti1(ti3_lines))
					ti1.close()
			except Exception, exception:
				InfoDialog(self, pos = (-1, 100), msg = self.getlstr("error.testchart.creation_failed", inoutfile + ".ti1") + "\n\n" + unicode(str(exception), enc, "replace"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
				return None, None
		if apply_calibration:
			if apply_calibration == True:
				cal = os.path.join(self.getcfg("profile.save_path"), self.get_profile_name(), self.get_profile_name()) + ".cal" # always a .cal file in that case
			else:
				cal = apply_calibration # can be .cal or .icc / .icm
			calcopy = os.path.join(inoutfile + ".cal")
			filename, ext = os.path.splitext(cal)
			if ext.lower() == ".cal":
				if not self.check_cal_isfile(cal):
					return None, None
				if not os.path.exists(calcopy):
					try:
						shutil.copyfile(cal, calcopy) # copy cal to temp dir
					except Exception, exception:
						InfoDialog(self, pos = (-1, 100), msg = self.getlstr("error.copy_failed", (cal, calcopy)) + "\n\n" + unicode(str(exception), enc, "replace"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
						return None, None
					if not self.check_cal_isfile(calcopy):
						return None, None
			else: # .icc / .icm
				self.options_dispcal = []
				if not self.check_profile_isfile(cal):
					return None, None
				try:
					profile = ICCP.ICCProfile(filename + ext)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					profile = None
				if profile:
					ti3 = StringIO(profile.tags.get("CIED", ""))
					if "cprt" in profile.tags: # get dispcal options if present
						self.options_dispcal = ["-" + arg for arg in self.get_options_from_cprt(profile.tags.cprt)[0]]
				else:
					ti3 = StringIO("")
				ti3_lines = [line.strip() for line in ti3]
				ti3.close()
				if not "CTI3" in ti3_lines:
					InfoDialog(self, pos = (-1, 100), msg = self.getlstr("error.cal_extraction", (cal)), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
					return None, None
				try:
					tmpcal = open(calcopy, "w")
					tmpcal.write(extract_cal(ti3_lines))
					tmpcal.close()
				except Exception, exception:
					InfoDialog(self, pos = (-1, 100), msg = self.getlstr("error.cal_extraction", (cal)) + "\n\n" + unicode(str(exception), enc, "replace"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
					return None, None
			cal = calcopy
		#
		cmd = self.get_argyll_util("dispread")
		args = []
		args += ["-v"] # verbose
		args += ["-d" + self.get_display_number()]
		args += ["-c" + self.get_comport_number()]
		measurement_mode = self.get_measurement_mode()
		instrument_features = self.get_instrument_features()
		if measurement_mode:
			if measurement_mode != "p" and not instrument_features.get("spectral"):
				args += ["-y" + measurement_mode[0]] # always specify -y (won't be read from .cal when updating)
			if "p" in measurement_mode and instrument_features.get("projector_mode") and self.argyll_version >= [1, 1, 0]: # projector mode, Argyll >= 1.1.0 Beta
				args += ["-p"]
		if apply_calibration:
			args += ["-k"]
			args += [cal]
		args += [("-p" if self.argyll_version <= [1, 0, 4] else "-P") + self.get_measureframe_dimensions()]
		if self.measure_darken_background_cb.GetValue():
			args += ["-F"]
		if instrument_features.get("high_res"):
			args += ["-H"]
		self.options_dispread = args + self.options_dispread
		return cmd, self.options_dispread + [inoutfile]

	def prepare_colprof(self, profile_name = None, display_name = None):
		profile_save_path = self.create_tempdir()
		if not profile_save_path or not self.check_create_dir(profile_save_path): # check directory and in/output file(s)
			return None, None
		if profile_name is None:
			profile_name = self.get_profile_name()
		inoutfile = self.make_argyll_compatible_path(os.path.join(profile_save_path, profile_name))
		if not os.path.exists(inoutfile + ".ti3"):
			InfoDialog(self, pos = (-1, 100), msg = self.getlstr("error.measurement.file_missing", inoutfile + ".ti3"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
			return None, None
		if not os.path.isfile(inoutfile + ".ti3"):
			InfoDialog(self, pos = (-1, 100), msg = self.getlstr("error.measurement.file_notfile", inoutfile + ".ti3"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
			return None, None
		#
		cmd = self.get_argyll_util("colprof")
		args = []
		args += ["-v"] # verbose
		args += ["-q" + self.get_profile_quality()]
		args += ["-a" + self.get_profile_type()]
		if self.gamap_btn.IsEnabled():
			if self.gamap_perceptual_cb.GetValue():
				gamap = "s"
			elif self.gamap_saturation_cb.GetValue():
				gamap = "S"
			else:
				gamap = None
			if gamap:
				args += ["-" + gamap]
				args += [self.gamap_profile.GetPath()]
				args += ["-c" + self.viewconds_ba[self.gamap_src_viewcond_ctrl.GetStringSelection()]]
				args += ["-d" + self.viewconds_ba[self.gamap_out_viewcond_ctrl.GetStringSelection()]]
		self.options_colprof = list(args)
		options_colprof = list(args)
		for i in range(len(options_colprof)):
			if options_colprof[i][0] != "-":
				options_colprof[i] = '"' + options_colprof[i] + '"'
		if "-d3" in self.options_targen:
			args += ["-M"]
			if display_name is None:
				if self.IsShownOnScreen():
					display_no = self.displays.index(self.display_ctrl.GetStringSelection())
				else:
					display_no = wx.Display.GetFromWindow(self.measureframe)
				if display_no < 0: # window outside visible area
					display_no = 0
				args += [self.displays[display_no].split(" @")[0]]
			else:
				args += [display_name]
			args += ["-C"]
			args += ["(c) %s %s. Created with %s and Argyll CMS: dispcal %s colprof %s" % (strftime("%Y"), getpass.getuser(), appname, " ".join(self.options_dispcal), " ".join(options_colprof))]
		else:
			args += ["-C"]
			args += ["(c) %s %s. Created with %s and Argyll CMS: colprof %s" % (strftime("%Y"), getpass.getuser(), appname, " ".join(options_colprof))]
		args += ["-D"]
		args += [profile_name]
		args += [inoutfile]
		return cmd, args

	def prepare_dispwin(self, cal = None, profile_path = None, install = True):
		cmd = self.get_argyll_util("dispwin")
		args = []
		args += ["-v"] # verbose
		args += ["-d" + self.get_display_number()]
		args += ["-c"] # first, clear any calibration
		if cal == True:
			args += ["-L"]
		elif cal:
			if not self.check_cal_isfile(cal):
				return None, None
			# calcopy = self.make_argyll_compatible_path(os.path.join(self.create_tempdir(), os.path.basename(cal)))
			# if not os.path.exists(calcopy):
				# shutil.copyfile(cal, calcopy) # copy cal to temp dir
				# if not self.check_cal_isfile(calcopy):
					# return None, None
			# cal = calcopy
			args += [cal]
		else:
			if cal is None:
				if not profile_path:
					profile_save_path = os.path.join(self.getcfg("profile.save_path"), self.get_profile_name())
					profile_path = os.path.join(profile_save_path, self.get_profile_name() + profile_ext)
				if not self.check_profile_isfile(profile_path):
					return None, None
				try:
					profile = ICCP.ICCProfile(profile_path)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					InfoDialog(self, msg = self.getlstr("profile.invalid"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
					return None, None
				if profile.profileClass != "mntr" or profile.colorSpace != "RGB":
					InfoDialog(self, msg = self.getlstr("profile.unsupported", (profile.profileClass, profile.colorSpace)), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
					return None, None
				if install:
					if self.getcfg("profile.install_scope") != "u" and \
						((sys.platform != "win32" and (os.geteuid() == 0 or get_sudo())) or 
						(sys.platform == "win32" and 
						sys.getwindowsversion() >= (6, )) or test):
						if ((sys.platform not in ("win32", "darwin") and \
							self.argyll_version >= [1, 1, 0]) or \
							sys.platform in ("win32", "darwin") or test):
								# -S option is broken on Linux with current Argyll releases
								args += ["-S" + self.getcfg("profile.install_scope")]
					args += ["-I"]
				# profcopy = self.make_argyll_compatible_path(os.path.join(self.create_tempdir(), os.path.basename(profile_path)))
				# if not os.path.exists(profcopy):
					# shutil.copyfile(profile_path, profcopy) # copy profile to temp dir
					# if not self.check_profile_isfile(profcopy):
						# return None, None
				# profile_path = profcopy
				args += [profile_path]
		return cmd, args

	def create_tempdir(self):
		if not hasattr(self, "tempdir") or not os.path.exists(self.tempdir):
			# we create the tempdir once each calibrating/profiling run (deleted automatically after each run)
			try:
				self.tempdir = tempfile.mkdtemp(prefix = appname + u"-")
			except Exception, exception:
				self.tempdir = None
				handle_error("Error - could not create temporary directory: " + str(exception), parent = self)
		return self.tempdir

	def check_overwrite(self, ext = ""):
		filename = self.get_profile_name() + ext
		dst_file = os.path.join(self.getcfg("profile.save_path"), self.get_profile_name(), filename)
		if os.path.exists(dst_file):
			dlg = ConfirmDialog(self, msg = self.getlstr("warning.already_exists", filename), ok = self.getlstr("ok"), cancel = self.getlstr("cancel"), bitmap = self.bitmaps["theme/icons/32x32/dialog-warning"])
			result = dlg.ShowModal()
			dlg.Destroy()
			if result != wx.ID_OK: return False
		return True

	def wrapup(self, copy = True, remove = True, dst_path = None, ext_filter = [".app", ".cal", ".cmd", ".command", ".icc", ".icm", ".sh", ".ti1", ".ti3"]):
		if debug: safe_print("wrapup(copy = %s, remove = %s)" % (copy, remove))
		if not hasattr(self, "tempdir") or not os.path.exists(self.tempdir) or not os.path.isdir(self.tempdir):
			return # nothing to do
		if copy:
			if dst_path is None:
				dst_path = os.path.join(self.getcfg("profile.save_path"), self.get_profile_name(), self.get_profile_name() + ".ext")
			try:
				dir_created = self.check_create_dir(os.path.dirname(dst_path))
			except Exception, exception:
				InfoDialog(self, pos = (-1, 100), msg = self.getlstr("error.dir_creation", (os.path.dirname(dst_path))) + "\n\n" + unicode(str(exception), enc, "replace"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
				return
			if dir_created:
				try:
					src_listdir = os.listdir(self.tempdir)
				except Exception, exception:
					safe_print("Error - directory '%s' listing failed: %s" % (self.tempdir, str(exception)))
				else:
					for basename in src_listdir:
						name, ext = os.path.splitext(basename)
						if ext_filter is None or ext.lower() in ext_filter:
							src = os.path.join(self.tempdir, basename)
							dst = os.path.splitext(dst_path)[0]
							if ext.lower() in (".app", cmdfile_ext): # preserve *.<utility>.[app|cmd|sh]
								dst += os.path.splitext(name)[1]
							dst += ext
							if os.path.exists(dst):
								if os.path.isdir(dst):
									if debug: safe_print("wrapup.copy: shutil.rmtree('%s', True)" % dst)
									try:
										shutil.rmtree(dst, True)
									except Exception, exception:
										safe_print("Warning - directory '%s' could not be removed: %s" % (dst, str(exception)))
								else:
									if debug: safe_print("wrapup.copy: os.remove('%s')" % dst)
									try:
										os.remove(dst)
									except Exception, exception:
										safe_print("Warning - file '%s' could not be removed: %s" % (dst, str(exception)))
							if remove:
								if debug: safe_print("wrapup.copy: shutil.move('%s', '%s')" % (src, dst))
								try:
									shutil.move(src, dst)
								except Exception, exception:
									safe_print("Warning - temporary object '%s' could not be moved to '%s': %s" % (src, dst, str(exception)))
							else:
								if os.path.isdir(src):
									if debug: safe_print("wrapup.copy: shutil.copytree('%s', '%s')" % (src, dst))
									try:
										shutil.copytree(src, dst)
									except Exception, exception:
										safe_print("Warning - temporary directory '%s' could not be copied to '%s': %s" % (src, dst, str(exception)))
								else:
									if debug: safe_print("wrapup.copy: shutil.copyfile('%s', '%s')" % (src, dst))
									try:
										shutil.copyfile(src, dst)
									except Exception, exception:
										safe_print("Warning - temporary file '%s' could not be copied to '%s': %s" % (src, dst, str(exception)))
		if remove:
			try:
				src_listdir = os.listdir(self.tempdir)
			except Exception, exception:
				safe_print("Error - directory '%s' listing failed: %s" % (self.tempdir, str(exception)))
			else:
				for basename in src_listdir:
					name, ext = os.path.splitext(basename)
					if ext_filter is None or ext.lower() not in ext_filter:
						src = os.path.join(self.tempdir, basename)
						isdir = os.path.isdir(src)
						if isdir:
							if debug: safe_print("wrapup.remove: shutil.rmtree('%s', True)" % src)
							try:
								shutil.rmtree(src, True)
							except Exception, exception:
								safe_print("Warning - temporary directory '%s' could not be removed: %s" % (src, str(exception)))
						else:
							if debug: safe_print("wrapup.remove: os.remove('%s')" % src)
							try:
								os.remove(src)
							except Exception, exception:
								safe_print("Warning - temporary directory '%s' could not be removed: %s" % (src, str(exception)))
			try:
				src_listdir = os.listdir(self.tempdir)
			except Exception, exception:
				safe_print("Error - directory '%s' listing failed: %s" % (self.tempdir, str(exception)))
			else:
				if not src_listdir:
					try:
						shutil.rmtree(self.tempdir, True)
					except Exception, exception:
						safe_print("Warning - temporary directory '%s' could not be removed: %s" % (self.tempdir, str(exception)))

	def calibrate(self, remove = False):
		capture_output = not self.interactive_display_adjustment_cb.GetValue()
		capture_output = False
		if capture_output:
			dlg = ConfirmDialog(self, pos = (-1, 100), msg = self.getlstr("instrument.place_on_screen"), ok = self.getlstr("ok"), cancel = self.getlstr("cancel"), bitmap = self.bitmaps["theme/icons/32x32/dialog-information"])
			result = dlg.ShowModal()
			dlg.Destroy()
			if result != wx.ID_OK: return False
		cmd, args = self.prepare_dispcal()
		result = self.exec_cmd(cmd, args, capture_output = capture_output)
		self.wrapup(result, remove or not result)
		if result:
			cal = os.path.join(self.getcfg("profile.save_path"), self.get_profile_name(), self.get_profile_name() + ".cal")
			self.setcfg("last_cal_path", cal)
			if self.profile_update_cb.GetValue():
				profile_path = os.path.join(self.getcfg("profile.save_path"), self.get_profile_name(), self.get_profile_name() + profile_ext)
				result = self.check_profile_isfile(profile_path, self.getlstr("error.profile.file_not_created"))
				if result:
					self.setcfg("calibration.file", profile_path)
					self.setcfg("last_cal_or_icc_path", profile_path)
					self.setcfg("last_icc_path", profile_path)
					self.update_controls(update_profile_name = False)
			else:
				result = self.check_cal_isfile(cal, self.getlstr("error.calibration.file_not_created"))
				if result:
					if self.install_cal:
						self.previous_cal = self.getcfg("calibration.file")
						self.setcfg("calibration.file", cal)
						self.update_controls(update_profile_name = False)
					self.setcfg("last_cal_or_icc_path", cal)
					self.load_cal(cal = cal, silent = True)
		return result

	def measure(self, apply_calibration = True):
		cmd, args = self.prepare_dispread(apply_calibration)
		result = self.exec_cmd(cmd, args)
		self.wrapup(result, not result)
		return result

	def profile(self, apply_calibration = True, dst_path = None, skip_cmds = False, display_name = None):
		safe_print(self.getlstr("create_profile"))
		if dst_path is None:
			dst_path = os.path.join(self.getcfg("profile.save_path"), self.get_profile_name(), self.get_profile_name() + profile_ext)
		cmd, args = self.prepare_colprof(os.path.basename(os.path.splitext(dst_path)[0]), display_name)
		result = self.exec_cmd(cmd, args, capture_output = "-as" in self.options_colprof and self.argyll_version <= [1, 0, 4], low_contrast = False, skip_cmds = skip_cmds)
		self.wrapup(result, dst_path = dst_path)
		if "-as" in self.options_colprof and self.argyll_version <= [1, 0, 4]: safe_print(self.getlstr("success") if result else self.getlstr("aborted"))
		if result:
			try:
				profile = ICCP.ICCProfile(dst_path)
			except (IOError, ICCP.ICCProfileInvalidError), exception:
				InfoDialog(self, msg = self.getlstr("profile.invalid"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
				return False
			if profile.profileClass == "mntr" and profile.colorSpace == "RGB":
				self.setcfg("last_cal_or_icc_path", dst_path)
				self.setcfg("last_icc_path", dst_path)
		return result

	def install_cal_handler(self, event = None, cal = None):
		if not self.check_set_argyll_bin():
			return
		if cal is None:
			cal = self.getcfg("calibration.file")
		if cal and self.check_file_isfile(cal):
			filename, ext = os.path.splitext(cal)
			if ext.lower() in (".icc", ".icm"):
				try:
					profile = ICCP.ICCProfile(cal)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					InfoDialog(self, msg = self.getlstr("profile.invalid"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
					return
				if profile.profileClass != "mntr" or profile.colorSpace != "RGB":
					InfoDialog(self, msg = self.getlstr("profile.unsupported", (profile.profileClass, profile.colorSpace)), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
					return
				profile_path = cal
			else:
				profile_path = filename + profile_ext
			if os.path.exists(profile_path):
				self.profile_finish(True, profile_path = profile_path, success_msg = self.getlstr("dialog.install_profile", (os.path.basename(profile_path), self.display_ctrl.GetStringSelection())), skip_cmds = True)

	def get_default_path(self, cfg_item_name):
		defaultPath = self.getcfg(cfg_item_name)
		defaultFile = ""
		if os.path.exists(defaultPath):
			defaultDir, defaultFile = os.path.dirname(defaultPath), os.path.basename(defaultPath)
		elif os.path.exists(os.path.dirname(defaultPath)):
			defaultDir = os.path.dirname(defaultPath)
		else:
			defaultDir = os.path.expanduser("~")
		return defaultDir, defaultFile

	def install_profile_handler(self, event):
		defaultDir, defaultFile = self.get_default_path("last_icc_path")
		dlg = wx.FileDialog(self, self.getlstr("install_display_profile"), defaultDir = defaultDir, defaultFile = defaultFile, wildcard = self.getlstr("filetype.icc") + "|*.icc;*.icm", style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		dlg.Center(wx.BOTH)
		result = dlg.ShowModal()
		path = dlg.GetPath()
		dlg.Destroy()
		if result == wx.ID_OK:
			if not os.path.exists(path):
				InfoDialog(self, msg = self.getlstr("file.missing", path), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
				return
			self.setcfg("last_icc_path", path)
			self.setcfg("last_cal_or_icc_path", path)
			self.install_cal_handler(cal = path)

	def load_cal_cal_handler(self, event):
		defaultDir, defaultFile = self.get_default_path("last_cal_path")
		dlg = wx.FileDialog(self, self.getlstr("calibration.load_from_cal"), defaultDir = defaultDir, defaultFile = defaultFile, wildcard = self.getlstr("filetype.cal") + "|*.cal", style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		dlg.Center(wx.BOTH)
		result = dlg.ShowModal()
		path = dlg.GetPath()
		dlg.Destroy()
		if result == wx.ID_OK:
			if not os.path.exists(path):
				InfoDialog(self, msg = self.getlstr("file.missing", path), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
				return
			self.setcfg("last_cal_path", path)
			self.setcfg("last_cal_or_icc_path", path)
			self.install_profile(capture_output = True, cal = path, install = False, skip_cmds = True)

	def load_profile_cal_handler(self, event):
		if not self.check_set_argyll_bin():
			return
		defaultDir, defaultFile = self.get_default_path("last_cal_or_icc_path")
		dlg = wx.FileDialog(self, self.getlstr("calibration.load_from_cal_or_profile"), defaultDir = defaultDir, defaultFile = defaultFile, wildcard = self.getlstr("filetype.cal_icc") + "|*.cal;*.icc;*.icm", style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		dlg.Center(wx.BOTH)
		result = dlg.ShowModal()
		path = dlg.GetPath()
		dlg.Destroy()
		if result == wx.ID_OK:
			if not os.path.exists(path):
				InfoDialog(self, msg = self.getlstr("file.missing", path), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
				return
			self.setcfg("last_cal_or_icc_path", path)
			if os.path.splitext(path)[1].lower() in (".icc", ".icm"):
				profile = ICCP.ICCProfile(path)
				if "vcgt" in profile.tags:
					self.setcfg("last_icc_path", path)
					self.install_profile(capture_output = True, profile_path = path, install = False, skip_cmds = True)
				else:
					InfoDialog(self, msg = self.getlstr("profile.no_vcgt"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
			else:
				self.setcfg("last_cal_path", path)
				self.install_profile(capture_output = True, cal = path, install = False, skip_cmds = True)

	def preview_handler(self, event = None, preview = None):
		if preview or (preview is None and self.preview.GetValue()):
			cal = self.cal
		else:
			cal = self.previous_cal
			if event and self.cal == cal:
				cal = False
			elif not cal:
				cal = True
		self.install_profile(capture_output = True, cal = cal, install = False, skip_cmds = True, silent = True)

	def install_profile(self, capture_output = False, cal = None, profile_path = None, install = True, skip_cmds = False, silent = False):
		cmd, args = self.prepare_dispwin(cal, profile_path, install)
		result = self.exec_cmd(cmd, args, capture_output, low_contrast = False, skip_cmds = skip_cmds, silent = silent)
		if result is not None and install:
			result = False
			for line in self.output:
				if "Installed" in line:
					if sys.platform == "darwin" and "-Sl" in args:
						# the profile has been installed, but we need a little help from applescript to actually make it the default for the current user
						cmd, args = 'osascript', ['-e', 
							'set iccProfile to POSIX file "%s"' % 
							os.path.join(iccprofiles, os.path.basename(args[-1])), '-e', 
							'tell app "ColorSyncScripting" to set display profile of display %s to iccProfile' % 
							self.get_display_number().split(",")[0]]
						result = self.exec_cmd(cmd, args, capture_output = True, low_contrast = False, skip_cmds = True, silent = True)
					else:
						result = True
					break
			# if "-c" in args:
				# args.remove("-c")
			# if "-I" in args:
				# args.remove("-I")
			# args.insert(-1, "-V")
			# result = self.exec_cmd(cmd, args, capture_output = True, low_contrast = False, skip_cmds = True, silent = True)
			# if result:
				# result = False
				# for line in self.output:
					# if line.find("'%s' IS loaded" % args[-1].encode(enc, "asciize")) >= 0:
						# result = True
						# break
		if result:
			if install:
				if not silent:
					if verbose >= 1: safe_print(self.getlstr("success"))
					InfoDialog(self, msg = self.getlstr("profile.install.success"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-information"])
				# try to create autostart script to load LUT curves on login
				n = self.get_display_number()
				loader_args = "-d%s -c -L" % n
				if sys.platform == "win32":
					try:
						loader_v01b = os.path.join(autostart_home, ("dispwin-d%s-c-L" % n) + ".lnk")
						if os.path.exists(loader_v01b):
							try:
								# delete v0.1b loader
								os.remove(loader_v01b)
							except Exception, exception:
								safe_print("Warning - could not remove old v0.1b calibration loader '%s': %s" % (loader_v01b, str(exception)))
						name = "%s Calibration Loader (Display %s)" % (appname, n)
						loader_v02b = os.path.join(autostart_home, name + ".lnk")
						if os.path.exists(loader_v02b):
							try:
								# delete v02.b/v0.2.1b loader
								os.remove(loader_v02b)
							except Exception, exception:
								safe_print("Warning - could not remove old v0.2b calibration loader '%s': %s" % (loader_v02b, str(exception)))
						path = os.path.join(autostart, name + ".lnk")
						scut = pythoncom.CoCreateInstance(
							shell.CLSID_ShellLink, None,
							pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink
						)
						scut.SetPath(cmd)
						if isexe:
							scut.SetIconLocation(sys.executable, 0)
						else:
							scut.SetIconLocation(get_data_path(os.path.join("theme", "icons", appname + ".ico")), 0)
						scut.SetArguments(loader_args)
						scut.SetShowCmd(win32con.SW_SHOWMINNOACTIVE)
						scut.QueryInterface(pythoncom.IID_IPersistFile).Save(path, 0)
					except Exception, exception:
						if not silent: InfoDialog(self, msg = self.getlstr("error.autostart_creation", "Windows") + "\n\n" + unicode(str(exception), enc, "replace"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-warning"])
				elif sys.platform != "darwin":
					# http://standards.freedesktop.org/autostart-spec/autostart-spec-latest.html
					name = "%s-Calibration-Loader-Display-%s" % (appname, n)
					desktopfile_path = os.path.join(autostart_home, name + ".desktop")
					# exec_ = '"%s" "%s" %s' % (os.path.join(pydir, "calibrationloader" + cmdfile_ext), cmd, loader_args)
					exec_ = '"%s" %s' % (cmd, loader_args)
					try:
						# always create user loader, even if we later try to move it to the system-wide location
						# so that atleast the user loader is present if the move to the system dir fails
						if not os.path.exists(autostart_home):
							os.makedirs(autostart_home)
						desktopfile = open(desktopfile_path, "w")
						desktopfile.write('[Desktop Entry]\n')
						desktopfile.write('Version=1.0\n')
						desktopfile.write('Encoding=UTF-8\n')
						desktopfile.write('Type=Application\n')
						desktopfile.write((u'Name=%s Calibration Loader (Display %s)\n' % (appname, n)).encode("UTF-8"))
						desktopfile.write((u'Comment=%s\n' % self.getlstr("calibrationloader.description", n)).encode("UTF-8"))
						desktopfile.write((u'Exec=%s\n' % exec_).encode("UTF-8"))
						desktopfile.close()
					except Exception, exception:
						if not silent: InfoDialog(self, msg = self.getlstr("error.autostart_creation", desktopfile_path) + "\n\n" + unicode(str(exception), enc, "replace"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-warning"])
					else:
						if "-Sl" in args:
							# copy system-wide loader
							system_desktopfile_path = os.path.join(autostart, name + ".desktop")
							if not silent and \
								(not self.exec_cmd("mkdir", ["-p", autostart], capture_output = True, low_contrast = False, skip_cmds = True, silent = True, asroot = True) or \
								not self.exec_cmd("mv", ["-f", desktopfile_path, autostart], capture_output = True, low_contrast = False, skip_cmds = True, silent = True, asroot = True)):
								InfoDialog(self, msg = self.getlstr("error.autostart_creation", system_desktopfile_path), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-warning"])
			else:
				if not silent:
					if cal == False:
						InfoDialog(self, msg = self.getlstr("calibration.reset_success"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-information"])
					else:
						InfoDialog(self, msg = self.getlstr("calibration.load_success"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-information"])
		elif not silent:
			if install:
				if verbose >= 1: safe_print(self.getlstr("failure"))
				if result is not None:
					InfoDialog(self, msg = self.getlstr("profile.install.error"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
			else:
				if cal == False:
					InfoDialog(self, msg = self.getlstr("calibration.reset_error"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
				else:
					InfoDialog(self, msg = self.getlstr("calibration.load_error"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
		self.pwd = None # do not keep password in memory longer than necessary
		return result

	def verify_calibration_handler(self, event):
		if self.check_set_argyll_bin():
			self.setup_measurement(self.verify_calibration)

	def verify_calibration(self):
		safe_print("-" * 80)
		safe_print(self.getlstr("calibration.verify"))
		capture_output = False
		if capture_output:
			dlg = ConfirmDialog(self, pos = (-1, 100), msg = self.getlstr("instrument.place_on_screen"), ok = self.getlstr("ok"), cancel = self.getlstr("cancel"), bitmap = self.bitmaps["theme/icons/32x32/dialog-information"])
			result = dlg.ShowModal()
			dlg.Destroy()
			if result != wx.ID_OK: return False
		cmd, args = self.prepare_dispcal(calibrate = False, verify = True)
		if self.exec_cmd(cmd, args, capture_output = capture_output, skip_cmds = True):
			if capture_output:
				self.infoframe.Show()
		self.wrapup(False)
		self.ShowAll()

	def load_cal(self, cal = None, silent = False):
		if not cal:
			cal = self.getcfg("calibration.file")
		if cal:
			if self.check_set_argyll_bin():
				if verbose >= 1 and silent: safe_print(self.getlstr("calibration.loading"))
				if self.install_profile(capture_output = True, cal = cal, install = False, skip_cmds = True, silent = silent):
					if verbose >= 1 and silent: safe_print(self.getlstr("success"))
					return True
				if verbose >= 1 and silent: safe_print(self.getlstr("failure"))
		return False

	def reset_cal(self, event = None):
		if self.check_set_argyll_bin():
			if verbose >= 1 and event is None: safe_print(self.getlstr("calibration.resetting"))
			if self.install_profile(capture_output = True, cal = False, install = False, skip_cmds = True, silent = event is None):
				if verbose >= 1 and event is None: safe_print(self.getlstr("success"))
				return True
			if verbose >= 1 and event is None: safe_print(self.getlstr("failure"))
		return False

	def load_display_profile_cal(self, event = None):
		if self.check_set_argyll_bin():
			if verbose >= 1 and event is None: safe_print(self.getlstr("calibration.loading_from_display_profile"))
			if self.install_profile(capture_output = True, cal = True, install = False, skip_cmds = True, silent = event is None):
				if verbose >= 1 and event is None: safe_print(self.getlstr("success"))
				return True
			if verbose >= 1 and event is None: safe_print(self.getlstr("failure"))
		return False

	def exec_cmd(self, cmd, args = [], capture_output = False, display_output = False, low_contrast = True, skip_cmds = False, silent = False, parent = None, asroot = False, log_output = True):
		if parent is None:
			parent = self
		# if capture_output:
			# fn = self.info_print
		# else:
		fn = None
		self.retcode = retcode = -1
		self.output = []
		self.errors = []
		if None in [cmd, args]:
			if verbose >= 1 and not capture_output: safe_print(self.getlstr("aborted"), fn = fn)
			return False
		cmdname = os.path.splitext(os.path.basename(cmd))[0]
		if args and args[-1].find(os.path.sep) > -1:
			working_dir = os.path.dirname(args[-1])
			working_basename = os.path.splitext(os.path.basename(args[-1]))[0] if cmdname == self.get_argyll_utilname("dispwin") else os.path.basename(args[-1]) # last arg is without extension, only for dispwin we need to strip it
		else:
			working_dir = None
		if not capture_output and low_contrast:
			# set low contrast colors (gray on black) so it doesn't interfere with measurements
			try:
				if sys.platform == "win32":
					sp.call("color 07", shell = True)
				elif sys.platform == "darwin":
					mac_terminal_set_colors()
				else:
					sp.call('echo -e "\\033[2;37m"', shell = True)
			except Exception, exception:
				safe_print("Info - could not set terminal colors:", str(exception))
		if verbose >= 1:
			if not silent:
				safe_print("", fn = fn)
				if working_dir:
					safe_print(self.getlstr("working_dir"), fn = fn)
					indent = "  "
					for name in working_dir.split(os.path.sep):
						safe_print(textwrap.fill(name + os.path.sep, 80, expand_tabs = False, replace_whitespace = False, initial_indent = indent, subsequent_indent = indent), fn = fn)
						indent += " "
					safe_print("", fn = fn)
				safe_print(self.getlstr("commandline"), fn = fn)
				printcmdline(os.path.basename(cmd), args, fn = fn, cwd = working_dir)
				safe_print("", fn = fn)
		cmdline = [cmd] + args
		for i in range(len(cmdline)):
			item = cmdline[i]
			if i == 0 or (item.find(os.path.sep) > -1 and os.path.dirname(item) == working_dir):
				# strip the path from cmd and all items in the working dir
				cmdline[i] = os.path.basename(item)
		sudo = None
		if cmdname == self.get_argyll_utilname("dispwin") and ("-Sl" in args or "-Sn" in args):
			asroot = True
		if asroot and ((sys.platform != "win32" and os.geteuid() != 0) or \
			(sys.platform == "win32" and sys.getwindowsversion() >= (6, ))):
			if sys.platform == "win32": # Vista and later
				pass
				# for src in (cmd, get_data_path("UAC.manifest")):
					# tgt = os.path.join(self.create_tempdir(), os.path.basename(cmd))
					# if src.endswith(".manifest"):
						# tgt += ".manifest"
					# else:
						# cmdline = [tgt] + cmdline[1:]
					# if not os.path.exists(tgt):
						# shutil.copy2(src, tgt)
			else:
				sudo = get_sudo()
		if sudo:
			try:
				sudoproc = sp.Popen([sudo, "-S", "echo", "OK"], stdin = sp.PIPE, stdout = sp.PIPE, stderr = sp.PIPE)
				if sudoproc.poll() is None:
					stdout, stderr = sudoproc.communicate(self.pwd)
				else:
					stdout, stderr = sudoproc.communicate()
				if not "OK" in stdout:
					sudoproc.stdin.close()
					# ask for password
					dlg = ConfirmDialog(parent, msg = self.getlstr("dialog.enter_root_password"), ok = self.getlstr("ok"), cancel = self.getlstr("cancel"), bitmap = self.bitmaps["theme/icons/32x32/dialog-question"])
					dlg.pwd_txt_ctrl = wx.TextCtrl(dlg, -1, "", size = (320, -1), style = wx.TE_PASSWORD)
					dlg.sizer3.Add(dlg.pwd_txt_ctrl, 1, flag = wx.TOP | wx.ALIGN_LEFT, border = 12)
					dlg.ok.SetDefault()
					dlg.pwd_txt_ctrl.SetFocus()
					dlg.sizer0.SetSizeHints(dlg)
					dlg.sizer0.Layout()
					n = 0
					while True:
						result = dlg.ShowModal()
						pwd = dlg.pwd_txt_ctrl.GetValue()
						if result != wx.ID_OK:
							safe_print(self.getlstr("aborted"), fn = fn)
							return None
						sudoproc = sp.Popen([sudo, "-S", "echo", "OK"], stdin = sp.PIPE, stdout = sp.PIPE, stderr = sp.PIPE)
						if sudoproc.poll() is None:
							stdout, stderr = sudoproc.communicate(pwd)
						else:
							stdout, stderr = sudoproc.communicate()
						if "OK" in stdout:
							self.pwd = pwd
							break
						elif n == 0:
							dlg.message.SetLabel(self.getlstr("auth.failed") + "\n" + self.getlstr("dialog.enter_root_password"))
							dlg.sizer0.SetSizeHints(dlg)
							dlg.sizer0.Layout()
						n += 1
					dlg.Destroy()
				cmdline.insert(0, sudo)
				cmdline.insert(1, "-S")
			except Exception, exception:
				safe_print("Warning - execution as root not possible:", str(exception))
			# tmpstdout = os.path.join(self.create_tempdir(), working_basename + ".out")
			# tmpstderr = os.path.join(self.create_tempdir(), working_basename + ".err")
			# cmdline = [sudo, u" ".join(escargs(cmdline)) + ('>"%s" 2>"%s"' % (tmpstdout, tmpstderr))]
			# if os.path.basename(sudo) in ["gnomesu", "kdesu"]:
				# cmdline.insert(1, "-c")
		if working_dir and not skip_cmds:
			try:
				cmdfilename = os.path.join(working_dir, working_basename + "." + cmdname + cmdfile_ext)
				allfilename = os.path.join(working_dir, working_basename + ".all" + cmdfile_ext)
				first = not os.path.exists(allfilename)
				last = cmdname == self.get_argyll_utilname("dispwin")
				cmdfile = open(cmdfilename, "w")
				allfile = open(allfilename, "a")
				cmdfiles = Files((cmdfile, allfile))
				if first:
					context = cmdfiles
				else:
					context = cmdfile
				if sys.platform == "win32":
					context.write(u"@echo off\n")
					context.write((u'PATH %s;%%PATH%%\n' % os.path.dirname(cmd)).encode(enc, "asciize"))
					cmdfiles.write(u'pushd "%~dp0"\n'.encode(enc, "asciize"))
					if cmdname in (self.get_argyll_utilname("dispcal"), self.get_argyll_utilname("dispread")):
						cmdfiles.write(u"color 07\n")
				else:
					context.write(u"set +v\n")
					context.write((u'PATH=%s:$PATH\n' % os.path.dirname(cmd)).encode(enc, "asciize"))
					if sys.platform == "darwin" and mac_create_app:
						cmdfiles.write(u'pushd "`dirname \\"$0\\"`/../../.."\n')
					else:
						cmdfiles.write(u'pushd "`dirname \\"$0\\"`"\n')
					if cmdname in (self.get_argyll_utilname("dispcal"), self.get_argyll_utilname("dispread")) and sys.platform != "darwin":
						context.write(u'echo -e "\\033[40;2;37m"\n')
					# if last and sys.platform != "darwin":
						# context.write(u'gnome_screensaver_running=$(ps -A -f | grep gnome-screensaver | grep -v grep)\n')
						# context.write(u'if [ "$gnome_screensaver_running" != "" ]; then gnome-screensaver-command --exit; fi\n')
					os.chmod(cmdfilename, 0755)
					os.chmod(allfilename, 0755)
				cmdfiles.write((u" ".join(escargs(cmdline)) + "\n").encode(enc, "asciize"))
				if sys.platform == "win32":
					cmdfiles.write(u"set exitcode=%errorlevel%\n")
					if cmdname in (self.get_argyll_utilname("dispcal"), self.get_argyll_utilname("dispread")):
						# reset to default commandline shell colors
						cmdfiles.write(u"color\n")
					cmdfiles.write(u"popd\n")
					cmdfiles.write(u"if not %exitcode%==0 exit /B %exitcode%\n")
				else:
					cmdfiles.write(u"exitcode=$?\n")
					if cmdname in (self.get_argyll_utilname("dispcal"), self.get_argyll_utilname("dispread")) and sys.platform != "darwin":
						# reset to default commandline shell colors
						cmdfiles.write(u'echo -e "\\033[0m"\n')
					cmdfiles.write(u"popd\n")
					# if last and sys.platform != "darwin":
						# cmdfiles.write(u'if [ "$gnome_screensaver_running" != "" ]; then gnome-screensaver; fi\n')
					cmdfiles.write(u"if [ $exitcode -ne 0 ]; then exit $exitcode; fi\n")
				cmdfiles.close()
				if sys.platform == "darwin":
					if mac_create_app:
						# could also use .command file directly, but using applescript allows giving focus to the terminal window automatically after a delay
						script = mac_terminal_do_script() + mac_terminal_set_colors(do = False) + ['-e', 'set shellscript to quoted form of (POSIX path of (path to resource "main.command"))', '-e', 'tell app "Terminal"', '-e', 'do script shellscript in first window', '-e', 'delay 3', '-e', 'activate', '-e', 'end tell', '-o']
						# Part 1: "cmdfile"
						appfilename = os.path.join(working_dir, working_basename + "." + cmdname + ".app").encode(fs_enc)
						cmdargs = ['osacompile'] + script + [appfilename]
						sp.call(cmdargs)
						shutil.move(cmdfilename, appfilename + "/Contents/Resources/main.command")
						os.chmod(appfilename + "/Contents/Resources/main.command", 0755)
						# Part 2: "allfile"
						appfilename = os.path.join(working_dir, working_basename + ".all.app")
						cmdargs = ['osacompile'] + script + [appfilename]
						sp.call(cmdargs)
						shutil.copyfile(allfilename, appfilename + "/Contents/Resources/main.command")
						os.chmod(appfilename + "/Contents/Resources/main.command", 0755)
						if last: # the last one in the chain
							os.remove(allfilename)
			except Exception, exception:
				safe_print("Warning - error during shell script creation:", str(exception))
		if cmdname == self.get_argyll_utilname("dispread") and self.dispread_after_dispcal:
			instrument_features = self.get_instrument_features()
			if instrument_features and (not instrument_features.get("sensor_cal") or instrument_features.get("skip_sensor_cal")):
				try:
					if sys.platform == "darwin":
						start_new_thread(mac_app_sendkeys, (5, "Terminal", " "))
					elif sys.platform == "win32":
						start_new_thread(wsh_sendkeys, (5, appname + exe_ext, " "))
					else:
						if which("xte"):
							start_new_thread(xte_sendkeys, (5, None, "Space"))
				except Exception, exception:
					safe_print("Warning - unattended measurements not possible (start_new_thread failed with %s)" % str(exception))
		elif cmdname in (self.get_argyll_utilname("dispcal"), self.get_argyll_utilname("dispread")) and \
			sys.platform == "darwin" and args and not self.IsShownOnScreen():
			start_new_thread(mac_app_activate, (.25, "Terminal"))
		try:
			if silent:
				stderr = sp.STDOUT
			else:
				stderr = Tea(tempfile.SpooledTemporaryFile())
			if capture_output:
				stdout = tempfile.SpooledTemporaryFile()
			else:
				stdout = sys.stdout
			tries = 1
			while tries > 0:
				self.subprocess = sp.Popen([arg.encode(fs_enc) for arg in cmdline], stdin = sp.PIPE if sudo else None, stdout = stdout, stderr = stderr, cwd = None if working_dir is None else working_dir.encode(fs_enc))
				if sudo and self.subprocess.poll() is None:
					if self.pwd:
						self.subprocess.communicate(self.pwd)
					else:
						self.subprocess.communicate()
				self.retcode = retcode = self.subprocess.wait()
				tries -= 1
				if not silent:
					stderr.seek(0)
					errors = stderr.readlines()
					stderr.close()
					# if sudo:
						# stderr = open(tmpstderr, "r")
						# errors += stderr.readlines()
						# stderr.close()
					if len(errors):
						errors2 = []
						for line in errors:
							if "Instrument Access Failed" in line and "-N" in args:
								cmdline.remove("-N")
								tries = 1
								break
							if line.strip() and line.find("User Aborted") < 0 and \
							   line.find("XRandR 1.2 is faulty - falling back to older extensions") < 0:
								errors2 += [line]
						if len(errors2):
							self.errors = errors2
							if (retcode != 0 or cmdname == self.get_argyll_utilname("dispwin")):
								InfoDialog(parent, pos = (-1, 100), msg = unicode("".join(errors2).strip(), enc, "replace"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-warning"])
							else:
								safe_print(unicode("".join(errors2).strip(), enc, "replace"), fn = fn)
					if tries > 0:
						stderr = Tea(tempfile.SpooledTemporaryFile())
				if capture_output:
					stdout.seek(0)
					self.output = output = stdout.readlines()
					stdout.close()
					# if sudo:
						# stdout = open(tmpstdout, "r")
						# errors += stdout.readlines()
						# stdout.close()
					if len(output) and log_output:
						log(unicode("".join(output).strip(), enc, "replace"))
						if display_output:
							wx.CallAfter(self.infoframe.Show)
					if tries > 0:
						stdout = tempfile.SpooledTemporaryFile()
		except Exception, exception:
			handle_error("Error: " + str(exception), parent = self)
			retcode = -1
		if not capture_output and low_contrast:
			# reset to higher contrast colors (white on black) for readability
			try:
				if sys.platform == "win32":
					sp.call("color 0F", shell = True)
				elif sys.platform == "darwin":
					mac_terminal_set_colors(text = "white", text_bold = "white")
				else:
					sp.call('echo -e "\\033[22;37m"', shell = True)
			except Exception, exception:
				safe_print("Info - could not restore terminal colors:", str(exception))
		if retcode != 0:
			if verbose >= 1 and not capture_output: safe_print(self.getlstr("aborted"), fn = fn)
			return False
		# else:
			# if verbose >= 1 and not capture_output: safe_print("", fn = fn)
		return True

	def info_print(self, txt):
		wx.CallAfter(self.infotext.AppendText, txt + os.linesep)

	def report_calibrated_handler(self, event):
		self.setup_measurement(self.report)

	def report_uncalibrated_handler(self, event):
		self.setup_measurement(self.report, False)

	def report(self, report_calibrated = True):
		if self.check_set_argyll_bin():
			safe_print("-" * 80)
			if report_calibrated:
				safe_print(self.getlstr("report.calibrated"))
			else:
				safe_print(self.getlstr("report.uncalibrated"))
			capture_output = False
			if capture_output:
				dlg = ConfirmDialog(self, pos = (-1, 100), msg = self.getlstr("instrument.place_on_screen"), ok = self.getlstr("ok"), cancel = self.getlstr("cancel"), bitmap = self.bitmaps["theme/icons/32x32/dialog-information"])
				result = dlg.ShowModal()
				dlg.Destroy()
				if result != wx.ID_OK: return False
			cmd, args = self.prepare_dispcal(calibrate = False)
			if report_calibrated:
				args += ["-r"]
			else:
				args += ["-R"]
			if self.exec_cmd(cmd, args, capture_output = capture_output, skip_cmds = True):
				if capture_output:
					self.infoframe.Show()
			self.wrapup(False)
			self.ShowAll()

	def calibrate_btn_handler(self, event):
		if sys.platform == "darwin" or debug: self.focus_handler(event)
		self.update_profile_name_timer.Stop()
		if self.check_set_argyll_bin() and self.check_overwrite(".cal"):
			self.setup_measurement(self.just_calibrate)
		else:
			self.update_profile_name_timer.Start(1000)

	def just_calibrate(self):
		safe_print("-" * 80)
		safe_print(self.getlstr("button.calibrate"))
		update = self.profile_update_cb.GetValue()
		self.install_cal = True
		if self.calibrate(remove = True):
			InfoDialog(self, pos = (-1, 100), msg = self.getlstr("calibration.complete"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-information"])
			if update:
				self.profile_finish(True, success_msg = self.getlstr("calibration_profiling.complete"))
		else:
			InfoDialog(self, pos = (-1, 100), msg = self.getlstr("calibration.incomplete"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
		self.ShowAll()

	def setup_measurement(self, pending_function, *pending_function_args, **pending_function_kwargs):
		self.write_cfg()
		self.wrapup(False)
		# if sys.platform == "win32":
			# sp.call("cls", shell = True)
		# else:
			# sp.call('clear', shell = True)
		self.HideAll()
		self.measureframe_show()
		self.set_pending_function(pending_function, *pending_function_args, **pending_function_kwargs)

	def set_pending_function(self, pending_function, *pending_function_args, **pending_function_kwargs):
		self.pending_function = pending_function
		self.pending_function_args = pending_function_args
		self.pending_function_kwargs = pending_function_kwargs

	def call_pending_function(self): # needed for proper display updates under GNOME
		self.write_cfg()
		self.measureframe_hide()
		if debug:
			safe_print("call_pending_function")
			safe_print(" pending_function_args: ", self.pending_function_args)
		wx.CallAfter(self.pending_function, *self.pending_function_args, **self.pending_function_kwargs)

	def calibrate_and_profile_btn_handler(self, event):
		if sys.platform == "darwin" or debug: self.focus_handler(event)
		self.update_profile_name_timer.Stop()
		if self.check_set_argyll_bin() and self.check_overwrite(".cal") and self.check_overwrite(".ti3") and self.check_overwrite(profile_ext):
			self.setup_measurement(self.calibrate_and_profile)
		else:
			self.update_profile_name_timer.Start(1000)

	def calibrate_and_profile(self):
		safe_print("-" * 80)
		safe_print(self.getlstr("button.calibrate_and_profile").replace("&&", "&"))
		self.install_cal = True
		if self.get_instrument_features().get("skip_sensor_cal"):
			self.options_dispread = ["-N"]
		self.dispread_after_dispcal = True
		start_timers = True
		if self.calibrate():
			if self.measure(apply_calibration = True):
				start_timers = False
				wx.CallAfter(self.start_profile_worker, self.getlstr("calibration_profiling.complete"))
			else:
				InfoDialog(self, pos = (-1, 100), msg = self.getlstr("profiling.incomplete"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
		else:
			InfoDialog(self, pos = (-1, 100), msg = self.getlstr("calibration.incomplete"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
		self.ShowAll(start_timers = start_timers)

	def start_profile_worker(self, success_msg, apply_calibration = True):
		self.start_worker(self.profile_finish, self.profile, ckwargs = {"success_msg": success_msg, "failure_msg": self.getlstr("profiling.incomplete")}, wkwargs = {"apply_calibration": apply_calibration }, progress_title = self.getlstr("create_profile"))

	def gamap_btn_handler(self, event):
		if self.gamapframe.IsShownOnScreen():
			self.gamapframe.Raise()
		else:
			self.gamapframe.Center()
			self.gamapframe.SetPosition((-1, self.GetPosition()[1] + self.GetSize()[1] - self.gamapframe.GetSize()[1] - 100))
			self.gamapframe.Show(not self.gamapframe.IsShownOnScreen())

	def profile_btn_handler(self, event):
		if sys.platform == "darwin" or debug: self.focus_handler(event)
		self.update_profile_name_timer.Stop()
		if self.check_set_argyll_bin() and self.check_overwrite(".ti3") and self.check_overwrite(profile_ext):
			cal = self.getcfg("calibration.file")
			apply_calibration = False
			if cal:
				filename, ext = os.path.splitext(cal)
				if ext.lower() in (".icc", ".icm"):
					self.options_dispcal = []
					try:
						profile = ICCP.ICCProfile(cal)
					except (IOError, ICCP.ICCProfileInvalidError), exception:
						InfoDialog(self, msg = self.getlstr("profile.invalid"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
						self.update_profile_name_timer.Start(1000)
						return
					else:
						if "cprt" in profile.tags: # get dispcal options if present
							self.options_dispcal = ["-" + arg for arg in self.get_options_from_cprt(profile.tags.cprt)[0]]
				if os.path.exists(filename + ".cal") and can_update_cal(filename + ".cal"):
					apply_calibration = filename + ".cal"
			if not apply_calibration:
				dlg = ConfirmDialog(self, msg = self.getlstr("dialog.no_cal_warning"), ok = self.getlstr("continue"), cancel = self.getlstr("cancel"), bitmap = self.bitmaps["theme/icons/32x32/dialog-warning"])
				result = dlg.ShowModal()
				dlg.Destroy()
				if result == wx.ID_OK:
					apply_calibration = False
				else:
					self.update_profile_name_timer.Start(1000)
					return
			self.setup_measurement(self.just_profile, apply_calibration)
		else:
			self.update_profile_name_timer.Start(1000)

	def just_profile(self, apply_calibration):
		safe_print("-" * 80)
		safe_print(self.getlstr("button.profile"))
		self.options_dispread = []
		self.dispread_after_dispcal = False
		start_timers = True
		if self.measure(apply_calibration):
			start_timers = False
			wx.CallAfter(self.start_profile_worker, self.getlstr("profiling.complete"), apply_calibration)
		else:
			InfoDialog(self, pos = (-1, 100), msg = self.getlstr("profiling.incomplete"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
		self.ShowAll(start_timers = start_timers)

	def profile_finish(self, result, profile_path = None, success_msg = "", failure_msg = "", preview = True, skip_cmds = False):
		if result:
			if not hasattr(self, "previous_cal") or not self.previous_cal:
				self.previous_cal = self.getcfg("calibration.file")
			if profile_path:
				profile_save_path = os.path.splitext(profile_path)[0]
			else:
				profile_save_path = os.path.join(self.getcfg("profile.save_path"), self.get_profile_name(), self.get_profile_name())
				profile_path = profile_save_path + profile_ext
			self.cal = profile_path
			filename, ext = os.path.splitext(profile_path)
			if ext.lower() in (".icc", ".icm"):
				has_cal = False
				try:
					profile = ICCP.ICCProfile(profile_path)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					InfoDialog(self, msg = self.getlstr("profile.invalid"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
					self.start_timers(True)
					self.previous_cal = None
					return
				else:
					has_cal = "vcgt" in profile.tags
					if profile.profileClass != "mntr" or profile.colorSpace != "RGB":
						InfoDialog(self, msg = success_msg, ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-information"])
						self.start_timers(True)
						self.previous_cal = None
						return
					if self.getcfg("calibration.file") != profile_path and "cprt" in profile.tags:
						options_dispcal, options_colprof = self.get_options_from_cprt(profile.tags.cprt)
						if options_dispcal or options_colprof:
							cal = profile_save_path + ".cal"
							sel = self.calibration_file_ctrl.GetSelection()
							if options_dispcal and self.recent_cals[sel] == cal:
								self.recent_cals.remove(cal)
								self.calibration_file_ctrl.Delete(sel)
							if self.getcfg("settings.changed"):
								self.settings_discard_changes()
							if options_dispcal and options_colprof:
								self.load_cal_handler(None, path = profile_path, update_profile_name = False, silent = True)
							else:
								self.setcfg("calibration.file", profile_path)
								self.update_controls(update_profile_name = False)
			else: # .cal file
				has_cal = True
			dlg = ConfirmDialog(self, msg = success_msg, ok = self.getlstr("profile.install"), cancel = self.getlstr("profile.do_not_install"), bitmap = self.bitmaps["theme/icons/32x32/dialog-information"])
			if preview and has_cal: # show calibration preview checkbox
				self.preview = wx.CheckBox(dlg, -1, self.getlstr("calibration.preview"))
				self.preview.SetValue(True)
				dlg.Bind(wx.EVT_CHECKBOX, self.preview_handler, id = self.preview.GetId())
				dlg.sizer3.Add(self.preview, flag = wx.TOP | wx.ALIGN_LEFT, border = 12)
				if (sys.platform != "win32" and (os.geteuid() == 0 or get_sudo())) or \
					(sys.platform == "win32" and sys.getwindowsversion() >= (6, ) or test): # Linux, OSX or Vista and later
					self.install_profile_user = wx.RadioButton(dlg, -1, self.getlstr("profile.install_user"), style = wx.RB_GROUP)
					self.install_profile_user.SetValue(self.getcfg("profile.install_scope") == "u")
					dlg.Bind(wx.EVT_RADIOBUTTON, self.install_profile_scope_handler, id = self.install_profile_user.GetId())
					dlg.sizer3.Add(self.install_profile_user, flag = wx.TOP | wx.ALIGN_LEFT, border = 4)
					self.install_profile_systemwide = wx.RadioButton(dlg, -1, self.getlstr("profile.install_local_system"))
					self.install_profile_systemwide.SetValue(self.getcfg("profile.install_scope") == "l")
					dlg.Bind(wx.EVT_RADIOBUTTON, self.install_profile_scope_handler, id = self.install_profile_systemwide.GetId())
					dlg.sizer3.Add(self.install_profile_systemwide, flag = wx.TOP | wx.ALIGN_LEFT, border = 4)
					if sys.platform == "darwin":
						self.install_profile_network = wx.RadioButton(dlg, -1, self.getlstr("profile.install_network"))
						self.install_profile_network.SetValue(self.getcfg("profile.install_scope") == "n")
						dlg.Bind(wx.EVT_RADIOBUTTON, self.install_profile_scope_handler, id = self.install_profile_network.GetId())
						dlg.sizer3.Add(self.install_profile_network, flag = wx.TOP | wx.ALIGN_LEFT, border = 4)
				dlg.sizer0.SetSizeHints(dlg)
				dlg.sizer0.Layout()
				if ext not in (".icc", ".icm") or self.getcfg("calibration.file") != profile_path: self.preview_handler(preview = True)
			dlg.ok.SetDefault()
			result = dlg.ShowModal()
			dlg.Destroy()
			if result == wx.ID_OK:
				safe_print("-" * 80)
				safe_print(self.getlstr("profile.install"))
				self.install_profile(capture_output = True, profile_path = profile_path, skip_cmds = skip_cmds)
			elif preview:
				if self.getcfg("calibration.file"):
					self.load_cal(silent = True) # load LUT curves from last used .cal file
				else:
					self.load_display_profile_cal(None) # load LUT curves from current display profile (if any, and if it contains curves)
		else:
			InfoDialog(self, pos = (-1, 100), msg = failure_msg, ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
		self.start_timers(True)
		self.previous_cal = None
	
	def install_profile_scope_handler(self, event):
		if self.install_profile_systemwide.GetValue():
			self.setcfg("profile.install_scope", "l")
		elif sys.platform == "darwin" and self.install_profile_network.GetValue():
			self.setcfg("profile.install_scope", "n")
		elif self.install_profile_user.GetValue():
			self.setcfg("profile.install_scope", "u")
		if debug: safe_print("profile.install_scope", self.getcfg("profile.install_scope"))
	
	def start_timers(self, wrapup = False):
		if wrapup:
			self.wrapup(False)
		self.plugplay_timer.Start(10000)
		self.update_profile_name_timer.Start(1000)
	
	def stop_timers(self):
		self.plugplay_timer.Stop()
		self.update_profile_name_timer.Stop()

	def comport_ctrl_handler(self, event):
		if debug: safe_print("comport_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		self.setcfg("comport.number", self.get_comport_number())
		self.update_measurement_modes()

	def display_ctrl_handler(self, event):
		if debug: safe_print("display_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		display_no = self.display_ctrl.GetSelection()
		self.setcfg("display.number", display_no + 1)
		if hasattr(self, "display_lut_ctrl") and bool(int(self.getcfg("display_lut.link"))):
			self.display_lut_ctrl.SetStringSelection(self.displays[display_no])
			self.setcfg("display_lut.number", display_no + 1)

	def display_lut_ctrl_handler(self, event):
		if debug: safe_print("display_lut_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		try:
			i = self.displays.index(self.display_lut_ctrl.GetStringSelection())
		except ValueError:
			i = self.display_ctrl.GetSelection()
		self.setcfg("display_lut.number", i + 1)

	def display_lut_link_ctrl_handler(self, event, link = None):
		if debug: safe_print("display_lut_link_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		bitmap_link = self.bitmaps["theme/icons/16x16/stock_lock"]
		bitmap_unlink = self.bitmaps["theme/icons/16x16/stock_lock-open"]
		if link is None:
			link = not bool(int(self.getcfg("display_lut.link")))
		if link:
			self.display_lut_link_ctrl.SetBitmapLabel(bitmap_link)
			lut_no = self.display_ctrl.GetSelection()
		else:
			self.display_lut_link_ctrl.SetBitmapLabel(bitmap_unlink)
			try:
				lut_no = self.displays.index(self.display_lut_ctrl.GetStringSelection())
			except ValueError:
				lut_no = self.display_ctrl.GetSelection()
		self.display_lut_ctrl.SetSelection(lut_no)
		self.display_lut_ctrl.Enable(not link and self.display_lut_ctrl.GetCount() > 0)
		self.setcfg("display_lut.link", int(link))
		self.setcfg("display_lut.number", lut_no + 1)

	def measurement_mode_ctrl_handler(self, event):
		if debug: safe_print("measurement_mode_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		self.set_default_testchart()
		v = self.get_measurement_mode()
		if v and "p" in v and self.argyll_version < [1, 1, 0]:
			self.measurement_mode_ctrl.SetSelection(self.measurement_modes_ba[self.get_instrument_type()].get(self.defaults["measurement_mode"], 0))
			v = None
			InfoDialog(self, msg = self.getlstr("projector_mode_unavailable"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-information"])
		cal_changed = v != self.getcfg("measurement_mode") and self.getcfg("calibration.file") not in self.presets
		if cal_changed:
			self.cal_changed()
		self.setcfg("projector_mode", 1 if v and "p" in v else None)
		self.setcfg("measurement_mode", (v.replace("p", "") if v else None) or None)
		if ((v in ("l", "lp", "p") and float(self.get_black_point_correction()) > 0) or (v in ("c", "cp") and float(self.get_black_point_correction()) == 0)) and self.getcfg("calibration.black_point_correction_choice.show"):
			if v in ("l", "lp", "p"):
				ok = self.getlstr("calibration.turn_off_black_point_correction")
			else:
				ok = self.getlstr("calibration.turn_on_black_point_correction")
			dlg = ConfirmDialog(self, title = self.getlstr("calibration.black_point_correction_choice_dialogtitle"), msg = self.getlstr("calibration.black_point_correction_choice"), ok = ok, cancel = self.getlstr("calibration.keep_black_point_correction"), bitmap = self.bitmaps["theme/icons/32x32/dialog-question"])
			chk = wx.CheckBox(dlg, -1, self.getlstr("dialog.do_not_show_again"))
			dlg.Bind(wx.EVT_CHECKBOX, self.black_point_correction_choice_dialog_handler, id = chk.GetId())
			dlg.sizer3.Add(chk, flag = wx.TOP | wx.ALIGN_LEFT, border = 12)
			dlg.sizer0.SetSizeHints(dlg)
			dlg.sizer0.Layout()
			result = dlg.ShowModal()
			dlg.Destroy()
			if result == wx.ID_OK:
				if v in ("l", "lp", "p"):
					bkpt_corr = 0.0
				else:
					bkpt_corr = 1.0
				if not cal_changed and bkpt_corr != self.getcfg("calibration.black_point_correction"):
					self.cal_changed()
				self.setcfg("calibration.black_point_correction", bkpt_corr)
				self.update_controls(update_profile_name = False)
		self.update_profile_name()
	
	def black_point_correction_choice_dialog_handler(self, event):
		self.setcfg("calibration.black_point_correction_choice.show", int(not event.GetEventObject().GetValue()))

	def profile_type_ctrl_handler(self, event):
		if debug: safe_print("profile_type_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		lut_profile = self.get_profile_type() in ("l", "x")
		self.gamap_btn.Enable(lut_profile)
		v = self.get_profile_type()
		if v != self.getcfg("profile.type"):
			self.profile_settings_changed()
		self.setcfg("profile.type", v)
		self.update_profile_name()
		self.set_default_testchart()
		if lut_profile and int(self.testchart_patches_amount.GetLabel()) < 500:
			dlg = ConfirmDialog(self, msg = self.getlstr("profile.testchart_recommendation"), ok = self.getlstr("OK"), cancel = self.getlstr("cancel"), bitmap = self.bitmaps["theme/icons/32x32/dialog-question"])
			result = dlg.ShowModal()
			dlg.Destroy()
			if result == wx.ID_OK:
				testchart = "d3-e4-s0-g52-m4-f500-crossover.ti1"
				self.testchart_defaults["c"]["l"] = testchart
				self.testchart_defaults["l"]["l"] = testchart
				self.set_testchart(get_data_path(os.path.join("ti1", testchart)))

	def profile_name_ctrl_handler(self, event):
		if debug: safe_print("profile_name_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		self.sanitize_profile_name()
	
	def sanitize_profile_name(self):
		if not self.check_profile_name():
			wx.Bell()
			x = self.profile_name_textctrl.GetInsertionPoint()
			oldval = self.profile_name_textctrl.GetValue()
			newval = self.getdefault("profile.name") if oldval == "" else re.sub("[\\/:*?\"<>|]+", "", oldval)
			self.profile_name_textctrl.ChangeValue(newval)
			self.profile_name_textctrl.SetInsertionPoint(x - (len(oldval) - len(newval)))
		self.update_profile_name()

	def create_profile_name_btn_handler(self, event):
		self.update_profile_name()

	def profile_save_path_btn_handler(self, event):
		defaultPath = os.path.sep.join(self.get_default_path("profile.save_path"))
		dlg = wx.DirDialog(self, self.getlstr("dialog.set_profile_save_path", self.get_profile_name()), defaultPath = defaultPath)
		dlg.Center(wx.BOTH)
		if dlg.ShowModal() == wx.ID_OK:
			self.setcfg("profile.save_path", dlg.GetPath())
			self.update_profile_name()
		dlg.Destroy()

	def get_display_number(self):
		if self.IsShownOnScreen() or not hasattr(self, "pending_function"):
			display_no = self.displays.index(self.display_ctrl.GetStringSelection())
		else:
			display_no = wx.Display.GetFromWindow(self.measureframe)
		if display_no < 0: # window outside visible area
			display_no = 0
		display_no = str(display_no + 1)
		if hasattr(self, "display_lut_ctrl"):
			if bool(int(self.getcfg("display_lut.link"))):
				display_no += "," + display_no
			else:
				try:
					lut_no = str(self.displays.index(self.display_lut_ctrl.GetStringSelection()) + 1)
				except ValueError:
					lut_no = display_no
				display_no += "," + lut_no
		return display_no

	def get_comport_number(self):
		return str(self.comport_ctrl.GetSelection() + 1)
	
	def profile_name_info_btn_handler(self, event):
		if not hasattr(self, "profile_name_info_frame"):
			self.profile_name_info_frame = InfoWindow(self, msg = self.profile_name_info(), title = self.getlstr("profile.name"), bitmap = self.bitmaps["theme/icons/32x32/dialog-information"])
		else:
			self.profile_name_info_frame.Show()
			self.profile_name_info_frame.Raise()

	def profile_name_info(self):
		info = [
			"%dn	" + self.getlstr("display"),
			"%in	" + self.getlstr("instrument"),
			"%im	" + self.getlstr("measurement_mode"),
			"%wp	" + self.getlstr("whitepoint"),
			"%cb	" + self.getlstr("calibration.luminance"),
			"%cB	" + self.getlstr("calibration.black_luminance"),
			"%cg	" + self.getlstr("trc"),
			"%ca	" + self.getlstr("calibration.ambient_viewcond_adjust"),
			"%cf	" + self.getlstr("calibration.black_output_offset"),
			"%ck	" + self.getlstr("calibration.black_point_correction"),
			"%cq	" + self.getlstr("calibration.quality"),
			"%pq	" + self.getlstr("profile.quality"),
			"%pt	" + self.getlstr("profile.type")
		]
		if hasattr(self, "black_point_rate_ctrl") and self.defaults["calibration.black_point_rate.enabled"]:
			info.insert(9, "%cA	" + self.getlstr("calibration.black_point_rate"))
		return self.getlstr("profile.name.placeholders") + "\n\n" + "\n".join(info)

	def get_profile_name(self):
		return self.profile_name.GetLabel()

	def make_argyll_compatible_path(self, path):
		parts = path.split(os.path.sep)
		for i in range(len(parts)):
			parts[i] = unicode(parts[i].encode(enc, "asciize"), enc).replace("/", "_")
		return os.path.sep.join(parts)

	def create_profile_handler(self, event, path = None):
		if not self.check_set_argyll_bin():
			return
		if path is None:
			# select measurement data (ti3 or profile)
			defaultDir, defaultFile = self.get_default_path("last_ti3_path")
			dlg = wx.FileDialog(self, self.getlstr("create_profile"), defaultDir = defaultDir, defaultFile = defaultFile, wildcard = self.getlstr("filetype.ti3") + "|*.icc;*.icm;*.ti3", style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
			dlg.Center(wx.BOTH)
			result = dlg.ShowModal()
			if result == wx.ID_OK:
				path = dlg.GetPath()
			dlg.Destroy()
		if path:
			if not os.path.exists(path):
				InfoDialog(self, msg = self.getlstr("file.missing", path), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
				return
			# get filename and extension of source file
			source_filename, source_ext = os.path.splitext(path)
			if source_ext.lower() != ".ti3":
				try:
					profile = ICCP.ICCProfile(path)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					InfoDialog(self, msg = self.getlstr("profile.invalid"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
					return
				if profile.tags.get("CIED", "")[0:4] != "CTI3":
					InfoDialog(self, msg = self.getlstr("profile.no_embedded_ti3"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
					return
				ti3 = StringIO(profile.tags.CIED)
			else:
				try:
					ti3 = open(path, "rU")
				except Exception, exception:
					InfoDialog(self, msg = self.getlstr("error.file.open", path), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
					return
			ti3_lines = [line.strip() for line in ti3]
			ti3.close()
			if not "CAL" in ti3_lines:
				dlg = ConfirmDialog(self, msg = self.getlstr("dialog.ti3_no_cal_info"), ok = self.getlstr("continue"), cancel = self.getlstr("cancel"), bitmap = self.bitmaps["theme/icons/32x32/dialog-warning"])
				result = dlg.ShowModal()
				dlg.Destroy()
				if result != wx.ID_OK: return
			self.setcfg("last_ti3_path", path)
			# let the user choose a location for the profile
			dlg = wx.FileDialog(self, self.getlstr("save_as"), os.path.dirname(path), os.path.basename(source_filename) + profile_ext, wildcard = self.getlstr("filetype.icc") + "|*%s" % profile_ext, style = wx.SAVE | wx.FD_OVERWRITE_PROMPT)
			dlg.Center(wx.BOTH)
			result = dlg.ShowModal()
			profile_save_path = self.make_argyll_compatible_path(dlg.GetPath())
			dlg.Destroy()
			if result == wx.ID_OK:
				filename, ext = os.path.splitext(profile_save_path)
				if ext.lower() != profile_ext:
					profile_save_path += profile_ext
					if os.path.exists(profile_save_path):
						dlg = ConfirmDialog(self, msg = self.getlstr("dialog.confirm_overwrite", (profile_save_path)), ok = self.getlstr("overwrite"), cancel = self.getlstr("cancel"), bitmap = self.bitmaps["theme/icons/32x32/dialog-warning"])
						result = dlg.ShowModal()
						dlg.Destroy()
						if result != wx.ID_OK:
							return
				self.setcfg("last_icc_path", profile_save_path)
				# get filename and extension of target file
				profile_name = os.path.basename(os.path.splitext(profile_save_path)[0])
				# create temporary working dir
				self.wrapup(False)
				tmp_working_dir = self.create_tempdir()
				if not tmp_working_dir or not self.check_create_dir(tmp_working_dir): # check directory and in/output file(s)
					return
				# copy ti3 to temp dir
				ti3_tmp_path = self.make_argyll_compatible_path(os.path.join(tmp_working_dir, profile_name + ".ti3"))
				self.options_dispcal = []
				self.options_targen = []
				if verbose >= 2: safe_print("Setting targen options:", *self.options_targen)
				display_name = None
				try:
					if source_ext.lower() == ".ti3":
						shutil.copyfile(path, ti3_tmp_path)
					else:
						ti3 = open(ti3_tmp_path, "wb") # binary mode because we want to avoid automatic newlines conversion
						ti3.write(profile.tags.CIED)
						ti3.close()
						if "cprt" in profile.tags: # get dispcal options if present
							self.options_dispcal = ["-" + arg for arg in self.get_options_from_cprt(profile.tags.cprt)[0]]
						if "dmdd" in profile.tags:
							display_name = profile.getDeviceModelDescription()
					ti3 = CGATS.CGATS(ti3_tmp_path)
					if ti3.queryv1("COLOR_REP") and ti3.queryv1("COLOR_REP")[:3] == "RGB":
						self.options_targen = ["-d3"]
						if verbose >= 2: safe_print("Setting targen options:", *self.options_targen)
				except Exception, exception:
					handle_error("Error - temporary .ti3 file could not be created: " + str(exception), parent = self)
					self.wrapup(False)
					return
				# if sys.platform == "win32":
					# sp.call("cls", shell = True)
				# else:
					# sp.call('clear', shell = True)
				safe_print("-" * 80)
				# run colprof
				self.start_worker(self.profile_finish, self.profile, ckwargs = {"profile_path": profile_save_path, "success_msg": self.getlstr("profile.created"), "failure_msg": self.getlstr("error.profile.file_not_created")}, wkwargs = {"apply_calibration": True, "dst_path": profile_save_path, "display_name": display_name}, progress_title = self.getlstr("create_profile"))

	def progress_timer_handler(self, event):
		keepGoing, skip = self.progress_parent.progress_dlg.Pulse(self.progress_parent.progress_dlg.GetTitle())
		if not keepGoing and hasattr(self, "subprocess") and self.subprocess.poll() is None:
			try:
				self.subprocess.terminate()
			except Exception, exception:
				handle_error("Error - self.subprocess.terminate() failed: " + str(exception), parent = self.progress_parent.progress_dlg)

	def start_worker(self, consumer, producer, cargs = (), ckwargs = None, wargs = (), wkwargs = None, progress_title = "", progress_msg = "", parent = None, progress_start = 100):
		if ckwargs is None:
			ckwargs = {}
		if wkwargs is None:
			wkwargs = {}
		while self.is_working():
			sleep(250) # wait until previous worker thread finishes
		self.stop_timers()
		if not progress_msg:
			progress_msg = progress_title
		if not parent:
			parent = self
		self.progress_parent = parent
		if not hasattr(self.progress_parent, "progress_timer"):
			self.progress_parent.progress_timer = wx.Timer(self.progress_parent)
			self.progress_parent.Bind(wx.EVT_TIMER, self.progress_timer_handler, self.progress_parent.progress_timer)
		if progress_start < 100:
			progress_start = 100
		self.progress_parent.progress_start_timer = wx.CallLater(progress_start, self.progress_dlg_start, progress_title, progress_msg, parent) # show the progress dialog after 1ms
		self.thread = delayedresult.startWorker(self.generic_consumer, producer, [consumer] + list(cargs), ckwargs, wargs, wkwargs)
		return True

	def is_working(self):
		return hasattr(self, "progress_parent") and (self.progress_parent.progress_start_timer.IsRunning() or self.progress_parent.progress_timer.IsRunning())

	def progress_dlg_start(self, progress_title = "", progress_msg = "", parent = None):
		if hasattr(self, "subprocess") and self.subprocess.poll() is None:
			style = wx.PD_APP_MODAL | wx.PD_ELAPSED_TIME | wx.PD_CAN_ABORT
		else:
			style = wx.PD_APP_MODAL | wx.PD_ELAPSED_TIME
		self.progress_parent.progress_dlg = wx.ProgressDialog(progress_title, progress_msg, parent = parent, style = style)
		self.progress_parent.progress_dlg.SetSize((400, -1))
		self.progress_parent.progress_dlg.Center()
		self.progress_parent.progress_timer.Start(50)

	def generic_consumer(self, delayedResult, consumer, *args, **kwargs):
		# consumer must accept result as first arg
		result = None
		exception = None
		try:
			result = delayedResult.get()
		except Exception, exception:
			handle_error("Error - delayedResult.get() failed: " + str(exception), parent = self)
		self.progress_parent.progress_start_timer.Stop()
		if hasattr(self.progress_parent, "progress_dlg"):
			self.progress_parent.progress_timer.Stop()
			self.progress_parent.progress_dlg.Hide() # do not destroy, will crash on Linux
		wx.CallAfter(consumer, result, *args, **kwargs)
	
	def create_profile_name(self):
		profile_name = self.profile_name_textctrl.GetValue()
		
		display = self.display_ctrl.GetStringSelection()
		if display:
			display = display.split(" @")[0]
		profile_name = profile_name.replace("%dn", display)
		instrument = self.comport_ctrl.GetStringSelection()
		instrument = instrument.replace("GretagMacbeth", "")
		instrument = instrument.replace("X-Rite", "")
		instrument = instrument.replace("ColorVision", "")
		instrument = instrument.replace(" ", "")
		profile_name = profile_name.replace("%in", instrument)
		measurement_mode = self.get_measurement_mode() or ""
		mode = ""
		if "c" in measurement_mode:
			mode += "CRT"
		elif "l" in measurement_mode:
			mode += "LCD"
		if len(measurement_mode) > 1:
			mode += "-"
		if "p" in measurement_mode :
			mode += self.getlstr("projector")
		if mode:
			profile_name = profile_name.replace("%im", mode)
		else:
			profile_name = re.sub("%im\W|\W%im", "", profile_name)
		whitepoint = self.get_whitepoint()
		if isinstance(whitepoint, str):
			if whitepoint.find(",") < 0:
				if self.get_whitepoint_locus() == "t":
					whitepoint = "D" + whitepoint
				else:
					whitepoint += "K"
			else:
				whitepoint = "x ".join(whitepoint.split(",")) + "y"
		profile_name = profile_name.replace("%wp", (self.getlstr("native").lower() if whitepoint == None else whitepoint))
		luminance = self.get_luminance()
		profile_name = profile_name.replace("%cb", self.getlstr("max").lower() if luminance == None else luminance + u"cdm²")
		black_luminance = self.get_black_luminance()
		profile_name = profile_name.replace("%cB", self.getlstr("min").lower() if black_luminance == None else black_luminance + u"cdm²")
		trc = self.get_trc()
		if trc not in ("l", "709", "s", "240"):
			if self.get_trc_type() == "g":
				trc += ""
			else:
				trc += " (%s)" % self.getlstr("trc.type.absolute").lower()
		else:
			trc = trc.upper().replace("L", u"L").replace("709", "Rec. 709").replace("S", "sRGB").replace("240", "SMPTE240M")
		profile_name = profile_name.replace("%cg", trc)
		ambient = self.get_ambient()
		profile_name = profile_name.replace("%ca", ambient + "lx" if ambient else "")
		f = int(float(self.get_black_output_offset()) * 100)
		profile_name = profile_name.replace("%cf", "Offset=" + str(f if f > 0 else 0) + "%")
		k = int(float(self.get_black_point_correction()) * 100)
		profile_name = profile_name.replace("%ck", (str(k) + "% " if k > 0 and k < 100 else "") + self.getlstr("neutral") if k > 0 else self.getlstr("native").lower())
		if hasattr(self, "black_point_rate_ctrl") and self.defaults["calibration.black_point_rate.enabled"]:
			profile_name = profile_name.replace("%cA", self.get_black_point_rate())
		aspects = {
			"c": self.get_calibration_quality(),
			"p": self.get_profile_quality()
		}
		msgs = {
			"u": self.getlstr("calibration.quality.ultra"),
			"h": self.getlstr("calibration.quality.high"),
			"m": self.getlstr("calibration.quality.medium"),
			"l": self.getlstr("calibration.quality.low")
		}
		for a in aspects:
			profile_name = profile_name.replace("%%%sq" % a, msgs[aspects[a]].lower())
		for q in msgs:
			pat = re.compile("(" + msgs[q] + ")\W" + msgs[q], re.I)
			profile_name = re.sub(pat, "\\1", profile_name)
		if self.get_profile_type() == "l":
			profile_type = "LUT"
		else:
			profile_type = "Matrix"
		profile_name = profile_name.replace("%pt", profile_type)
		directives = (
			"a",
			"A",
			"b",
			"B",
			"d",
			"H",
			"I",
			"j",
			"m",
			"M",
			"p",
			"S",
			"U",
			"w",
			"W",
			"y",
			"Y"
		)
		for directive in directives:
			try:
				profile_name = profile_name.replace("%%%s" % directive, strftime("%%%s" % directive))
			except UnicodeDecodeError:
				pass
		
		profile_name = re.sub("(\W?%s)+" % self.getlstr("native").lower(), "\\1", profile_name)
		
		return re.sub("[\\/:*?\"<>|]+", "_", profile_name)

	def update_profile_name(self, event = None):
		profile_name = self.create_profile_name()
		if not self.check_profile_name(profile_name):
			self.profile_name_textctrl.ChangeValue(self.getcfg("profile.name"))
			profile_name = self.create_profile_name()
			if not self.check_profile_name(profile_name):
				self.profile_name_textctrl.ChangeValue(self.getdefault("profile.name"))
				profile_name = self.create_profile_name()
		profile_name = self.make_argyll_compatible_path(profile_name)
		if profile_name != self.get_profile_name():
			self.setcfg("profile.name", self.profile_name_textctrl.GetValue())
			self.profile_name.UpdateToolTipString(profile_name)
			self.profile_name.SetLabel(profile_name)

	def check_profile_name(self, profile_name = None):
		if re.match(re.compile("^[^\\/:*?\"<>|]+$"), profile_name if profile_name is not None else self.create_profile_name()):
			return True
		else:
			return False

	def get_ambient(self):
		if self.ambient_viewcond_adjust_cb.GetValue():
			return str(stripzeroes(self.ambient_viewcond_adjust_textctrl.GetValue().replace(",", ".")))
		return None
	
	def get_instrument_type(self):
		# return the instrument type, "color" (colorimeter) or "spect" (spectrometer)
		spect = self.get_instrument_features().get("spectral", False)
		return "spect" if spect else "color"
	
	def get_instrument_features(self):
		return instruments.get(self.comport_ctrl.GetStringSelection(), {})

	def get_measurement_mode(self):
		return self.measurement_modes_ab[self.get_instrument_type()].get(self.measurement_mode_ctrl.GetSelection())

	def get_profile_type(self):
		return self.profile_types_ab[self.profile_type_ctrl.GetSelection()]

	def get_measureframe_dimensions(self):
		if debug: safe_print("get_measureframe_dimensions")
		display = get_display(self.measureframe)
		display_rect = display.Geometry
		display_size = display_rect[2:]
		display_client_rect = display.ClientArea
		display_client_size = display_client_rect[2:]
		if debug: safe_print(" display_size:", display_size)
		if debug: safe_print(" display_client_size:", display_client_size)
		default_measureframe_size = self.getdefault("size.measureframe"), self.getdefault("size.measureframe")
		if debug: safe_print(" default_measureframe_size:", default_measureframe_size)
		measureframe_pos = floatlist(self.measureframe.GetScreenPosition())
		measureframe_pos[0] -= display_rect[0]
		measureframe_pos[1] -= display_rect[1]
		if debug: safe_print(" measureframe_pos:", measureframe_pos)
		measureframe_size = floatlist(self.measureframe.GetSize())
		if debug: safe_print(" measureframe_size:", measureframe_size)
		if max(measureframe_size) >= max(display_client_size) - 50: # Fullscreen?
			measureframe_scale = 50.0 # Argyll max is 50
			measureframe_pos = [.5, .5]
		else:
			measureframe_scale = (display_size[0] / default_measureframe_size[0]) / (display_size[0] / measureframe_size[0])
			if debug: safe_print(" measureframe_scale:", measureframe_scale)
			if debug: safe_print(" scale_adjustment_factor:", scale_adjustment_factor)
			measureframe_scale *= scale_adjustment_factor
			if measureframe_size[0] >= display_client_size[0]:
				measureframe_pos[0] = .5
			elif measureframe_pos[0] != 0:
				if display_size[0] - measureframe_size[0] < measureframe_pos[0]:
					measureframe_pos[0] = display_size[0] - measureframe_size[0]
				measureframe_pos[0] = 1.0 / ((display_size[0] - measureframe_size[0]) / (measureframe_pos[0]))
			if measureframe_size[1] >= display_client_size[1]:
				measureframe_pos[1] = .5
			elif measureframe_pos[1] != 0:
				if display_size[1] - measureframe_size[1] < measureframe_pos[1]:
					measureframe_pos[1] = display_size[1] - measureframe_size[1]
				measureframe_pos[1] = 1.0 / ((display_size[1] - measureframe_size[1]) / (measureframe_pos[1]))
		if debug: safe_print(" measureframe_scale:", measureframe_scale)
		if debug: safe_print(" measureframe_pos:", measureframe_pos)
		measureframe_dimensions = str(measureframe_pos[0]) + "," + str(measureframe_pos[1]) + "," + str(measureframe_scale)
		if debug: safe_print(" measureframe_dimensions:", measureframe_dimensions)
		return measureframe_dimensions

	def get_whitepoint(self):
		if self.whitepoint_native_rb.GetValue(): # native
			return None
		elif self.whitepoint_colortemp_rb.GetValue(): # color temperature in kelvin
			return str(stripzeroes(self.whitepoint_colortemp_textctrl.GetValue().replace(",", ".")))
		elif self.whitepoint_xy_rb.GetValue():
			return str(stripzeroes(round(float(self.whitepoint_x_textctrl.GetValue().replace(",", ".")), 6))) + "," + str(stripzeroes(round(float(self.whitepoint_y_textctrl.GetValue().replace(",", ".")), 6)))

	def get_whitepoint_locus(self):
		n = self.whitepoint_colortemp_locus_ctrl.GetSelection()
		if not n in self.whitepoint_colortemp_loci_ab:
			n = 0
		return str(self.whitepoint_colortemp_loci_ab[n])

	def get_luminance(self):
		if self.luminance_max_rb.GetValue():
			return None
		else:
			return str(stripzeroes(self.luminance_textctrl.GetValue().replace(",", ".")))

	def get_black_luminance(self):
		if self.black_luminance_min_rb.GetValue():
			return None
		else:
			return str(stripzeroes(self.black_luminance_textctrl.GetValue().replace(",", ".")))

	def get_black_output_offset(self):
		return str(Decimal(self.black_output_offset_ctrl.GetValue()) / 100)

	def get_black_point_correction(self):
		return str(Decimal(self.black_point_correction_ctrl.GetValue()) / 100)

	def get_black_point_rate(self):
		return str(Decimal(self.black_point_rate_ctrl.GetValue()) / 100)

	def get_trc_type(self):
		if self.trc_type_ctrl.GetSelection() == 1 and self.trc_g_rb.GetValue():
			return "G"
		else:
			return "g"

	def get_trc(self):
		if self.trc_g_rb.GetValue():
			return str(stripzeroes(self.trc_textctrl.GetValue().replace(",", ".")))
		elif self.trc_l_rb.GetValue():
			return "l"
		elif self.trc_rec709_rb.GetValue():
			return "709"
		elif self.trc_srgb_rb.GetValue():
			return "s"
		else:
			return "240"

	def get_calibration_quality(self):
		return self.quality_ab[self.calibration_quality_ctrl.GetValue()]

	def get_interactive_display_adjustment(self):
		return str(int(self.interactive_display_adjustment_cb.GetValue()))

	def get_profile_quality(self):
		return self.quality_ab[self.profile_quality_ctrl.GetValue()]

	def getdefault(self, name):
		if name == "size.measureframe":
			display_no = wx.Display.GetFromWindow(self.measureframe)
			if display_no < 0 or display_no > wx.Display.GetCount() - 1:
				display_no = 0
			display_rect = wx.Display(display_no).Geometry
			display_size = display_rect[2:]
			display_size_mm = []
			try:
				display_size_mm = RDSMM.RealDisplaySizeMM(display_no)
			except Exception, exception:
				handle_error("Error - RealDisplaySizeMM() failed: " + str(exception), parent = self)
			if not len(display_size_mm) or 0 in display_size_mm:
				ppi_def = 100.0
				ppi_mac = 72.0
				method = 1
				if method == 0:
					# use configurable screen diagonal
					inch = 20.0
					mm = inch * 25.4
					f = mm / math.sqrt(math.pow(display_size[0], 2) + math.pow(display_size[1], 2))
					w_mm = math.sqrt(math.pow(mm, 2) - math.pow(display_size[1] * f, 2))
					h_mm = math.sqrt(math.pow(mm, 2) - math.pow(display_size[0] * f, 2))
					display_size_mm = w_mm, h_mm
				elif method == 1:
					# use the first display
					display_size_1st = wx.DisplaySize()
					display_size_mm = list(wx.DisplaySizeMM())
					if sys.platform == "darwin":
						display_size_mm[0] /= (ppi_def / ppi_mac)
						display_size_mm[1] /= (ppi_def / ppi_mac)
					if display_no > 0:
						display_size_mm[0] = display_size[0] / (display_size_1st[0] / display_size_mm[0])
						display_size_mm[1] = display_size[1] / (display_size_1st[1] / display_size_mm[1])
				else:
					# use assumed ppi
					display_size_mm = display_size[0] / ppi_def * 25.4, display_size[1] / ppi_def * 25.4
			return round(100.0 * display_size[0] / display_size_mm[0])
		else:
			if name in self.defaults:
				return self.defaults[name]
		return ""

	def getcfg(self, name, fallback = True):
		hasdef = name in self.defaults
		if hasdef:
			defval = self.defaults[name]
			deftype = type(defval)
		if self.cfg.has_option(ConfigParser.DEFAULTSECT, name):
			value = unicode(self.cfg.get(ConfigParser.DEFAULTSECT, name), "UTF-8")
			# check for invalid types and return default if wrong type
			if name != "trc" and hasdef and deftype in (Decimal, int, float):
				try:
					value = deftype(value)
				except ValueError:
					value = defval
			elif (name in ("calibration.file", "testchart.file") or \
			   name.startswith("last_")) and not os.path.exists(value):
				if value.split(os.path.sep)[-2:] == ["presets", os.path.basename(value)] or \
				   value.split(os.path.sep)[-2:] == ["ti1", os.path.basename(value)]:
					value = os.path.join(os.path.basename(os.path.dirname(value)), os.path.basename(value))
				else:
					value = os.path.basename(value)
				value = get_data_path(value) or (defval if hasdef else None)
		elif fallback and hasdef:
			value = defval
		else:
			value = None
		return value

	def setcfg(self, name, value):
		if value is None:
			self.cfg.remove_option(ConfigParser.DEFAULTSECT, name)
		else:
			self.cfg.set(ConfigParser.DEFAULTSECT, name, unicode(value).encode("UTF-8"))

	def profile_settings_changed(self):
		cal = self.getcfg("calibration.file")
		if cal:
			filename, ext = os.path.splitext(cal)
			if ext.lower() in (".icc", ".icm"):
				if not os.path.exists(filename + ".cal") and not cal in self.presets: #or not self.calibration_update_cb.GetValue():
					self.cal_changed()
					return
		if not self.updatingctrls:
			self.setcfg("settings.changed", 1)
			if self.calibration_file_ctrl.GetStringSelection()[0] != "*":
				sel = self.calibration_file_ctrl.GetSelection()
				if sel > 0:
					items = self.calibration_file_ctrl.GetItems()
					items[sel] = "* " + items[sel]
					self.calibration_file_ctrl.Freeze()
					self.calibration_file_ctrl.SetItems(items)
					self.calibration_file_ctrl.SetSelection(sel)
					self.calibration_file_ctrl.Thaw()

	def testchart_ctrl_handler(self, event):
		if debug: safe_print("testchart_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		self.set_testchart(self.testcharts[self.testchart_ctrl.GetSelection()])

	def testchart_btn_handler(self, event, path = None):
		if path is None:
			defaultDir, defaultFile = self.get_default_path("testchart.file")
			dlg = wx.FileDialog(self, self.getlstr("dialog.set_testchart"), defaultDir = defaultDir, defaultFile = defaultFile, wildcard = self.getlstr("filetype.icc_ti1_ti3") + "|*.icc;*.icm;*.ti1;*.ti3", style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
			dlg.Center(wx.BOTH)
			result = dlg.ShowModal()
			if result == wx.ID_OK:
				path = dlg.GetPath()
			dlg.Destroy()
		if path:
			if not os.path.exists(path):
				InfoDialog(self, msg = self.getlstr("file.missing", path), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
				return
			filename, ext = os.path.splitext(path)
			if ext.lower() in (".icc", ".icm"):
				try:
					profile = ICCP.ICCProfile(path)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					InfoDialog(self, msg = self.getlstr("profile.invalid"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
					return
				ti3_lines = [line.strip() for line in StringIO(profile.tags.get("CIED", ""))]
				if not "CTI3" in ti3_lines:
					InfoDialog(self, msg = self.getlstr("profile.no_embedded_ti3"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
					return
			self.set_testchart(path)
			self.write_cfg()
			self.profile_settings_changed()

	def create_testchart_btn_handler(self, event):
		if not hasattr(self, "tcframe"):
			self.init_tcframe()
		elif not hasattr(self, "ti1") or self.getcfg("testchart.file") != self.ti1.filename:
			self.tc_load_cfg_from_ti1()
		self.tcframe.Show()
		self.tcframe.Raise()
		return

	def init_tcframe(self):
		tcframe = self.tcframe = wx.Frame(self, -1, self.getlstr("testchart.edit"))
		tcframe.SetIcon(wx.Icon(get_data_path(os.path.join("theme", "icons", "16x16", appname + ".png")), wx.BITMAP_TYPE_PNG))
		tcframe.Bind(wx.EVT_CLOSE, self.tc_close_handler)

		if tc_use_alternate_preview:
			# splitter
			splitter = tcframe.splitter = wx.SplitterWindow(tcframe, -1, style = wx.SP_LIVE_UPDATE | wx.SP_3D)
			tcframe.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGED, self.tc_sash_handler, splitter)
			tcframe.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGING, self.tc_sash_handler, splitter)

			p1 = wx.Panel(splitter)
			p1.sizer = wx.BoxSizer(wx.VERTICAL)
			p1.SetSizer(p1.sizer)

			p2 = wx.Panel(splitter)
			p2.droptarget = FileDrop()
			p2.droptarget.drophandlers = {
				".icc": self.ti1_drop_handler,
				".icm": self.ti1_drop_handler,
				".ti1": self.ti1_drop_handler,
				".ti3": self.ti1_drop_handler
			}
			p2.droptarget.unsupported_handler = self.drop_unsupported_handler
			p2.SetDropTarget(p2.droptarget)
			p2.sizer = wx.BoxSizer(wx.VERTICAL)
			p2.SetSizer(p2.sizer)

			splitter.SetMinimumPaneSize(20)
			splitter.SplitHorizontally(p1, p2, -150)
			# splitter end

			panel = tcframe.panel = p1
		else:
			panel = tcframe.panel = wx.Panel(tcframe)
		panel.droptarget = FileDrop()
		panel.droptarget.drophandlers = {
			".icc": self.ti1_drop_handler,
			".icm": self.ti1_drop_handler,
			".ti1": self.ti1_drop_handler,
			".ti3": self.ti1_drop_handler
		}
		panel.droptarget.unsupported_handler = self.drop_unsupported_handler
		panel.SetDropTarget(panel.droptarget)

		tcframe.sizer = wx.BoxSizer(wx.VERTICAL)
		panel.SetSizer(tcframe.sizer)

		border = 4

		sizer = wx.FlexGridSizer(-1, 4)
		tcframe.sizer.Add(sizer, flag = (wx.ALL & ~wx.BOTTOM), border = 12)

		# white patches
		sizer.Add(wx.StaticText(panel, -1, self.getlstr("tc.white")), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		tcframe.tc_white_patches = wx.SpinCtrl(panel, -1, size = (65, -1), min = 0, name = "tc_white_patches")
		tcframe.Bind(wx.EVT_TEXT, self.tc_white_patches_handler, id = tcframe.tc_white_patches.GetId())
		sizer.Add(tcframe.tc_white_patches, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		# single channel patches
		sizer.Add(wx.StaticText(panel, -1, self.getlstr("tc.single")), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, border = border)
		tcframe.tc_single_channel_patches = wx.SpinCtrl(panel, -1, size = (65, -1), min = 0, max = 256, name = "tc_single_channel_patches")
		tcframe.tc_single_channel_patches.Bind(wx.EVT_KILL_FOCUS, self.tc_single_channel_patches_handler)
		tcframe.Bind(wx.EVT_SPINCTRL, self.tc_single_channel_patches_handler, id = tcframe.tc_single_channel_patches.GetId())
		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(hsizer)
		hsizer.Add(tcframe.tc_single_channel_patches, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		hsizer.Add(wx.StaticText(panel, -1, self.getlstr("tc.single.perchannel")), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		# gray axis patches
		sizer.Add(wx.StaticText(panel, -1, self.getlstr("tc.gray")), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		tcframe.tc_gray_patches = wx.SpinCtrl(panel, -1, size = (65, -1), min = 0, max = 256, name = "tc_gray_patches")
		tcframe.tc_gray_patches.Bind(wx.EVT_KILL_FOCUS, self.tc_gray_handler)
		tcframe.Bind(wx.EVT_SPINCTRL, self.tc_gray_handler, id = tcframe.tc_gray_patches.GetId())
		sizer.Add(tcframe.tc_gray_patches, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		# multidim steps
		sizer.Add(wx.StaticText(panel, -1, self.getlstr("tc.multidim")), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, border = border)
		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(hsizer)
		tcframe.tc_multi_steps = wx.SpinCtrl(panel, -1, size = (65, -1), min = 0, max = 21, name = "tc_multi_steps") # 16 multi dim steps = 4096 patches
		tcframe.tc_multi_steps.Bind(wx.EVT_KILL_FOCUS, self.tc_multi_steps_handler)
		tcframe.Bind(wx.EVT_SPINCTRL, self.tc_multi_steps_handler, id = tcframe.tc_multi_steps.GetId())
		hsizer.Add(tcframe.tc_multi_steps, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		tcframe.tc_multi_patches = wx.StaticText(panel, -1, "", name = "tc_multi_patches")
		hsizer.Add(tcframe.tc_multi_patches, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		# full spread patches
		sizer.Add(wx.StaticText(panel, -1, self.getlstr("tc.fullspread")), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		tcframe.tc_fullspread_patches = wx.SpinCtrl(panel, -1, size = (65, -1), min = 0, max = 9999, name = "tc_fullspread_patches")
		tcframe.Bind(wx.EVT_TEXT, self.tc_fullspread_handler, id = tcframe.tc_fullspread_patches.GetId())
		sizer.Add(tcframe.tc_fullspread_patches, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		# algo
		algos = self.tc_algos_ab.values()
		algos.sort()
		sizer.Add(wx.StaticText(panel, -1, self.getlstr("tc.algo")), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, border = border)
		tcframe.tc_algo = wx.ComboBox(panel, -1, choices = algos, style = wx.CB_READONLY, name = "tc_algo")
		tcframe.Bind(wx.EVT_COMBOBOX, self.tc_algo_handler, id = tcframe.tc_algo.GetId())
		sizer.Add(tcframe.tc_algo, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		# adaption
		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(hsizer, 1, flag = wx.EXPAND)
		hsizer.Add(wx.StaticText(panel, -1, self.getlstr("tc.adaption")), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		tcframe.tc_adaption_slider = wx.Slider(panel, -1, 0, 0, 100, size = (64, -1), name = "tc_adaption_slider")
		tcframe.Bind(wx.EVT_SLIDER, self.tc_adaption_handler, id = tcframe.tc_adaption_slider.GetId())
		hsizer.Add(tcframe.tc_adaption_slider, flag = wx.ALIGN_CENTER_VERTICAL)
		tcframe.tc_adaption_intctrl = wx.SpinCtrl(panel, -1, size = (65, -1), min = 0, max = 100, name = "tc_adaption_intctrl")
		tcframe.Bind(wx.EVT_TEXT, self.tc_adaption_handler, id = tcframe.tc_adaption_intctrl.GetId())
		sizer.Add(tcframe.tc_adaption_intctrl, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		hsizer = wx.GridSizer(-1, 2)
		sizer.Add(hsizer, 1, flag = wx.EXPAND)
		hsizer.Add(wx.StaticText(panel, -1, "%"), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		hsizer.Add(wx.StaticText(panel, -1, self.getlstr("tc.angle")), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, border = border)

		# angle
		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(hsizer, 1, flag = wx.EXPAND)
		tcframe.tc_angle_slider = wx.Slider(panel, -1, 0, 0, 5000, size = (128, -1), name = "tc_angle_slider")
		tcframe.Bind(wx.EVT_SLIDER, self.tc_angle_handler, id = tcframe.tc_angle_slider.GetId())
		hsizer.Add(tcframe.tc_angle_slider, flag = wx.ALIGN_CENTER_VERTICAL)
		tcframe.tc_angle_intctrl = wx.SpinCtrl(panel, -1, size = (75, -1), min = 0, max = 5000, name = "tc_angle_intctrl")
		tcframe.Bind(wx.EVT_TEXT, self.tc_angle_handler, id = tcframe.tc_angle_intctrl.GetId())
		hsizer.Add(tcframe.tc_angle_intctrl, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		# precond profile
		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		tcframe.sizer.Add(hsizer, flag = wx.ALL & ~(wx.BOTTOM | wx.TOP) | wx.EXPAND, border = 12)
		tcframe.tc_precond = wx.CheckBox(panel, -1, self.getlstr("tc.precond"), name = "tc_precond")
		tcframe.Bind(wx.EVT_CHECKBOX, self.tc_precond_handler, id = tcframe.tc_precond.GetId())
		hsizer.Add(tcframe.tc_precond, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		tcframe.tc_precond_profile = wx.FilePickerCtrl(panel, -1, "", message = self.getlstr("tc.precond"), wildcard = self.getlstr("filetype.icc_mpp") + "|*.icc;*.icm;*.mpp")
		tcframe.Bind(wx.EVT_FILEPICKER_CHANGED, self.tc_precond_profile_handler, id = tcframe.tc_precond_profile.GetId())
		hsizer.Add(tcframe.tc_precond_profile, 1, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		# limit samples to lab sphere
		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		tcframe.sizer.Add(hsizer, flag = wx.ALL & ~(wx.BOTTOM | wx.TOP), border = 12)
		tcframe.tc_filter = wx.CheckBox(panel, -1, self.getlstr("tc.limit.sphere"), name = "tc_filter")
		tcframe.Bind(wx.EVT_CHECKBOX, self.tc_filter_handler, id = tcframe.tc_filter.GetId())
		hsizer.Add(tcframe.tc_filter, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		# L
		hsizer.Add(wx.StaticText(panel, -1, "L"), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		tcframe.tc_filter_L = wx.SpinCtrl(panel, -1, initial = 50, size = (65, -1), min = 0, max = 100, name = "tc_filter_L")
		tcframe.Bind(wx.EVT_TEXT, self.tc_filter_handler, id = tcframe.tc_filter_L.GetId())
		hsizer.Add(tcframe.tc_filter_L, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		# a
		hsizer.Add(wx.StaticText(panel, -1, "a"), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		tcframe.tc_filter_a = wx.SpinCtrl(panel, -1, initial = 0, size = (65, -1), min = -128, max = 127, name = "tc_filter_a")
		tcframe.Bind(wx.EVT_TEXT, self.tc_filter_handler, id = tcframe.tc_filter_a.GetId())
		hsizer.Add(tcframe.tc_filter_a, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		# b
		hsizer.Add(wx.StaticText(panel, -1, "b"), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		tcframe.tc_filter_b = wx.SpinCtrl(panel, -1, initial = 0, size = (65, -1), min = -128, max = 127, name = "tc_filter_b")
		tcframe.Bind(wx.EVT_TEXT, self.tc_filter_handler, id = tcframe.tc_filter_b.GetId())
		hsizer.Add(tcframe.tc_filter_b, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		# radius
		hsizer.Add(wx.StaticText(panel, -1, self.getlstr("tc.limit.sphere_radius")), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		tcframe.tc_filter_rad = wx.SpinCtrl(panel, -1, initial = 255, size = (65, -1), min = 1, max = 255, name = "tc_filter_rad")
		tcframe.Bind(wx.EVT_TEXT, self.tc_filter_handler, id = tcframe.tc_filter_rad.GetId())
		hsizer.Add(tcframe.tc_filter_rad, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		# diagnostic VRML files
		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		tcframe.sizer.Add(hsizer, flag = wx.ALL & ~(wx.BOTTOM | wx.TOP), border = 12 + border)
		tcframe.tc_vrml = wx.CheckBox(panel, -1, self.getlstr("tc.vrml"), name = "tc_vrml")
		tcframe.Bind(wx.EVT_CHECKBOX, self.tc_vrml_handler, id = tcframe.tc_vrml.GetId())
		hsizer.Add(tcframe.tc_vrml, flag = (wx.ALL & ~wx.LEFT) | wx.ALIGN_CENTER_VERTICAL, border = border * 2)
		tcframe.tc_vrml_lab = wx.RadioButton(panel, -1, self.getlstr("tc.vrml.lab"), name = "tc_vrml_lab", style = wx.RB_GROUP)
		tcframe.Bind(wx.EVT_RADIOBUTTON, self.tc_vrml_handler, id = tcframe.tc_vrml_lab.GetId())
		hsizer.Add(tcframe.tc_vrml_lab, flag = (wx.ALL & ~wx.LEFT) | wx.ALIGN_CENTER_VERTICAL, border = border * 2)
		tcframe.tc_vrml_device = wx.RadioButton(panel, -1, self.getlstr("tc.vrml.device"), name = "tc_vrml_device")
		tcframe.Bind(wx.EVT_RADIOBUTTON, self.tc_vrml_handler, id = tcframe.tc_vrml_device.GetId())
		hsizer.Add(tcframe.tc_vrml_device, flag = (wx.ALL & ~wx.LEFT) | wx.ALIGN_CENTER_VERTICAL, border = border * 2)

		# buttons
		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		tcframe.sizer.Add(hsizer, flag = (wx.ALL & ~wx.BOTTOM) | wx.ALIGN_CENTER, border = 12)

		tcframe.preview_btn = wx.Button(panel, -1, self.getlstr("testchart.create"), name = "tc_create")
		tcframe.preview_btn.SetInitialSize((tcframe.preview_btn.GetSize()[0] + btn_width_correction, -1))
		tcframe.Bind(wx.EVT_BUTTON, self.tc_preview_handler, id = tcframe.preview_btn.GetId())
		hsizer.Add(tcframe.preview_btn, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		tcframe.save_btn = wx.Button(panel, -1, self.getlstr("testchart.save"))
		tcframe.save_btn.SetInitialSize((tcframe.save_btn.GetSize()[0] + btn_width_correction, -1))
		tcframe.save_btn.Disable()
		tcframe.Bind(wx.EVT_BUTTON, self.tc_save_handler, id = tcframe.save_btn.GetId())
		hsizer.Add(tcframe.save_btn, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		tcframe.save_as_btn = wx.Button(panel, -1, self.getlstr("testchart.save_as"))
		tcframe.save_as_btn.SetInitialSize((tcframe.save_as_btn.GetSize()[0] + btn_width_correction, -1))
		tcframe.save_as_btn.Disable()
		tcframe.Bind(wx.EVT_BUTTON, self.tc_save_as_handler, id = tcframe.save_as_btn.GetId())
		hsizer.Add(tcframe.save_as_btn, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		tcframe.clear_btn = wx.Button(panel, -1, self.getlstr("testchart.discard"), name = "tc_clear")
		tcframe.clear_btn.SetInitialSize((tcframe.clear_btn.GetSize()[0] + btn_width_correction, -1))
		tcframe.clear_btn.Disable()
		tcframe.Bind(wx.EVT_BUTTON, self.tc_clear_handler, id = tcframe.clear_btn.GetId())
		hsizer.Add(tcframe.clear_btn, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)


		# grid
		tcframe.grid = wx.grid.Grid(panel, -1, size = (-1, 150), style = wx.BORDER_STATIC)
		tcframe.grid.select_in_progress = False
		tcframe.sizer.Add(tcframe.grid, 1, flag = wx.ALL | wx.EXPAND, border = 12 + border)
		tcframe.grid.CreateGrid(0, 0)
		tcframe.Bind(wx.grid.EVT_GRID_CELL_CHANGE, self.tc_grid_cell_change_handler)
		tcframe.grid.Bind(wx.grid.EVT_GRID_LABEL_LEFT_CLICK, self.tc_grid_label_left_click_handler)
		tcframe.grid.Bind(wx.grid.EVT_GRID_LABEL_LEFT_DCLICK, self.tc_grid_label_left_dclick_handler)
		tcframe.grid.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.tc_grid_cell_left_click_handler)
		tcframe.grid.Bind(wx.grid.EVT_GRID_RANGE_SELECT, self.tc_grid_range_select_handler)
		tcframe.grid.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.tc_grid_cell_select_handler)
		tcframe.grid.DisableDragRowSize()

		# preview area
		if tc_use_alternate_preview:
			hsizer = wx.StaticBoxSizer(wx.StaticBox(p2, -1, self.getlstr("preview")), wx.VERTICAL)
			p2.sizer.Add(hsizer, 1, flag = wx.ALL | wx.ALIGN_CENTER | wx.EXPAND, border = 12)
			preview = tcframe.preview = wx.ScrolledWindow(p2, -1, style = wx.VSCROLL)
			preview.Bind(wx.EVT_ENTER_WINDOW, self.tc_set_default_status, id = preview.GetId())
			hsizer.Add(preview, 1, wx.EXPAND)
			preview.sizer = wx.BoxSizer(wx.VERTICAL)
			preview.SetSizer(preview.sizer)

			tcframe.patchsizer = wx.GridSizer(-1, -1)
			preview.sizer.Add(tcframe.patchsizer)
			preview.SetMinSize((-1, 100))
			panel.Bind(wx.EVT_ENTER_WINDOW, self.tc_set_default_status, id = panel.GetId())

		# status
		status = wx.StatusBar(tcframe, -1)
		tcframe.SetStatusBar(status)

		# layout
		tcframe.sizer.SetSizeHints(tcframe)
		tcframe.sizer.Layout()
		if tc_use_alternate_preview:
			tcframe.SetMinSize((tcframe.GetMinSize()[0], tcframe.GetMinSize()[1] + 150))

		if self.getcfg("position.tcgen.x") and self.getcfg("position.tcgen.y") and self.getcfg("size.tcgen.w") and self.getcfg("size.tcgen.h"):
			set_position(tcframe, int(self.getcfg("position.tcgen.x")), int(self.getcfg("position.tcgen.y")), int(self.getcfg("size.tcgen.w")), int(self.getcfg("size.tcgen.h")))
		else:
			tcframe.Center()

		self.tc_size_handler()

		children = tcframe.GetAllChildren()

		for child in children:
			if hasattr(child, "SetFont"):
				self.set_font_size(child)
			child.Bind(wx.EVT_KEY_DOWN, self.tc_key_handler)
		tcframe.Bind(wx.EVT_MOVE, self.tc_move_handler)
		tcframe.Bind(wx.EVT_SIZE, self.tc_size_handler, self.tcframe)
		tcframe.Bind(wx.EVT_MAXIMIZE, self.tc_size_handler, self.tcframe)

		tcframe.Children[0].Bind(wx.EVT_WINDOW_DESTROY, self.tc_destroy_handler)

		wx.CallAfter(self.tc_load_cfg_from_ti1)

	def tc_grid_cell_left_click_handler(self, event):
		event.Skip()

	def tc_grid_cell_select_handler(self, event):
		if debug: safe_print("tc_grid_cell_select_handler")
		row, col = event.GetRow(), event.GetCol()
		if event.Selecting():
			pass
		self.tcframe.grid.SelectBlock(row, col, row, col)
		self.tc_grid_anchor_row = row
		event.Skip()

	def tc_grid_range_select_handler(self, event):
		if debug: safe_print("tc_grid_range_select_handler")
		if not self.tcframe.grid.select_in_progress:
			wx.CallAfter(self.tc_set_default_status)
		event.Skip()

	def tc_grid_label_left_click_handler(self, event):
		row, col = event.GetRow(), event.GetCol()
		if row == -1 and col > -1: # col label clicked
			self.tcframe.grid.SetFocus()
			self.tcframe.grid.SetGridCursor(max(self.tcframe.grid.GetGridCursorRow(), 0), col)
			self.tcframe.grid.MakeCellVisible(max(self.tcframe.grid.GetGridCursorRow(), 0), col)
		elif col == -1 and row > -1: # row label clicked
			if self.tc_grid_select_row_handler(row, event.ShiftDown(), event.ControlDown() or event.CmdDown()):
				return
		event.Skip()

	def tc_grid_label_left_dclick_handler(self, event):
		row, col = event.GetRow(), event.GetCol()
		if col == -1: # row label clicked
			self.tcframe.grid.InsertRows(row + 1, 1)
			data = {
				"SAMPLE_ID": row + 2,
				"RGB_R": 100.0,
				"RGB_B": 100.0,
				"RGB_G": 100.0,
				"XYZ_X": 95.0543,
				"XYZ_Y": 100,
				"XYZ_Z": 108.9303
			}
			self.ti1.queryv1("DATA").add_data(data, row + 1)
			self.tc_amount = self.ti1.queryv1("NUMBER_OF_SETS")
			self.tc_set_default_status()
			for label in ("RGB_R", "RGB_G", "RGB_B"):
				for col in range(self.tcframe.grid.GetNumberCols()):
					if self.tcframe.grid.GetColLabelValue(col) == label:
						self.tcframe.grid.SetCellValue(row + 1, col, str(round(data[label], 4)))
			self.tc_grid_setcolorlabel(row + 1)
			self.tcframe.tc_vrml.SetValue(False)
			self.ti1_wrl = None
			self.tcframe.save_btn.Enable(self.ti1.modified and os.path.exists(self.ti1.filename))
			if hasattr(self.tcframe, "preview"):
				self.tcframe.preview.Freeze()
				self.tc_add_patch(row + 1, self.ti1.queryv1("DATA")[row + 1])
				self.tcframe.preview.Layout()
				self.tcframe.preview.FitInside()
				self.tcframe.preview.Thaw()
		event.Skip()

	def tc_grid_select_row_handler(self, row, shift = False, ctrl = False):
		if debug: safe_print("tc_grid_select_row_handler")
		self.tcframe.grid.SetFocus()
		if not shift and not ctrl:
			self.tcframe.grid.SetGridCursor(row, max(self.tcframe.grid.GetGridCursorCol(), 0))
			self.tcframe.grid.MakeCellVisible(row, max(self.tcframe.grid.GetGridCursorCol(), 0))
			self.tcframe.grid.SelectRow(row)
			self.tc_grid_anchor_row = row
		if self.tcframe.grid.IsSelection():
			if shift:
				self.tcframe.grid.select_in_progress = True
				rows = self.tcframe.grid.GetSelectionRows()
				sel = range(min(self.tc_grid_anchor_row, row), max(self.tc_grid_anchor_row, row))
				desel = []
				add = []
				for i in rows:
					if i not in sel:
						desel += [i]
				for i in sel:
					if i not in rows:
						add += [i]
				if len(desel) >= len(add):
					# in this case deselecting rows will take as long or longer than selecting, so use SelectRow to speed up the operation
					self.tcframe.grid.SelectRow(row)
				else:
					for i in desel:
						self.tcframe.grid.DeselectRow(i)
				for i in add:
					self.tcframe.grid.SelectRow(i, True)
				self.tcframe.grid.select_in_progress = False
				return False
			elif ctrl:
				if self.tcframe.grid.IsInSelection(row, 0):
					self.tcframe.grid.select_in_progress = True
					self.tcframe.grid.DeselectRow(row)
					self.tcframe.grid.select_in_progress = False
					self.tc_set_default_status()
					return True
				else:
					self.tcframe.grid.SelectRow(row, True)
		return False

	def tc_key_handler(self, event):
		# AltDown
		# CmdDown
		# ControlDown
		# GetKeyCode
		# GetModifiers
		# GetPosition
		# GetRawKeyCode
		# GetRawKeyFlags
		# GetUniChar
		# GetUnicodeKey
		# GetX
		# GetY
		# HasModifiers
		# KeyCode
		# MetaDown
		# Modifiers
		# Position
		# RawKeyCode
		# RawKeyFlags
		# ShiftDown
		# UnicodeKey
		# X
		# Y
		if debug: safe_print("event.KeyCode", event.GetKeyCode(), "event.RawKeyCode", event.GetRawKeyCode(), "event.UniChar", event.GetUniChar(), "event.UnicodeKey", event.GetUnicodeKey(), "CTRL/CMD:", event.ControlDown() or event.CmdDown(), "ALT:", event.AltDown(), "SHIFT:", event.ShiftDown())
		if (event.ControlDown() or event.CmdDown()): # CTRL (Linux/Mac/Windows) / CMD (Mac)
			key = event.GetKeyCode()
			focus = self.tcframe.FindFocus()
			if self.tcframe.grid in (focus, focus.GetParent(), focus.GetGrandParent()):
				if key in (8, 127): # BACKSPACE / DEL
					rows = self.tcframe.grid.GetSelectionRows()
					if rows and len(rows) and min(rows) >= 0 and max(rows) + 1 <= self.tcframe.grid.GetNumberRows():
						if len(rows) == self.tcframe.grid.GetNumberRows():
							self.tc_check_save_ti1()
						else:
							self.tc_delete_rows(rows)
						return
				elif key == 65: # A
					self.tcframe.grid.SelectAll()
					return
				elif key in (67, 88): # C / X
					clip = []
					cells = self.tcframe.grid.GetSelection()
					i = -1
					start_col = self.tcframe.grid.GetNumberCols()
					for cell in cells:
						row = cell[0]
						col = cell[1]
						if i < row:
							clip += [[]]
							i = row
						if col < start_col:
							start_col = col
						while len(clip[-1]) - 1 < col:
							clip[-1] += [""]
						clip[-1][col] = self.tcframe.grid.GetCellValue(row, col)
					for i in range(len(clip)):
						clip[i] = "\t".join(clip[i][start_col:])
					clipdata = wx.TextDataObject()
					clipdata.SetText("\n".join(clip))
					wx.TheClipboard.Open()
					wx.TheClipboard.SetData(clipdata)
					wx.TheClipboard.Close()
					return
				elif key == 86: # V
					do = wx.TextDataObject()
					wx.TheClipboard.Open()
					success = wx.TheClipboard.GetData(do)
					wx.TheClipboard.Close()
					if success:
						txt = StringIO(do.GetText())
						lines = txt.readlines()
						txt.close()
						for i in range(len(lines)):
							lines[i] = re.sub(" +", "\t", lines[i]).split("\t")
						# translate from selected cells into a grid with None values for not selected cells
						grid = []
						cells = self.tcframe.grid.GetSelection()
						i = -1
						start_col = self.tcframe.grid.GetNumberCols()
						for cell in cells:
							row = cell[0]
							col = cell[1]
							if i < row:
								grid += [[]]
								i = row
							if col < start_col:
								start_col = col
							while len(grid[-1]) - 1 < col:
								grid[-1] += [None]
							grid[-1][col] = cell
						for i in range(len(grid)):
							grid[i] = grid[i][start_col:]
						# 'paste' values from clipboard
						for i in range(len(grid)):
							for j in range(len(grid[i])):
								if grid[i][j] != None and len(lines) > i and len(lines[i]) > j and self.tcframe.grid.GetColLabelValue(j):
									self.tcframe.grid.SetCellValue(grid[i][j][0], grid[i][j][1], lines[i][j])
									self.tc_grid_cell_change_handler(CustomGridCellEvent(wx.grid.EVT_GRID_CELL_CHANGE.typeId, self.tcframe.grid, grid[i][j][0], grid[i][j][1]))
					return
			if key == 83: # S
				if (hasattr(self, "ti1")):
					if event.ShiftDown() or event.AltDown() or not os.path.exists(self.ti1.filename):
						self.tc_save_as_handler()
					elif self.ti1.modified:
						self.tc_save_handler()
				return
			else:
				event.Skip()
		else:
			event.Skip()

	def tc_sash_handler(self, event):
		if event.GetSashPosition() < self.tcframe.sizer.GetMinSize()[1]:
			self.tcframe.splitter.SetSashPosition(self.tcframe.sizer.GetMinSize()[1])
		event.Skip()

	def tc_size_handler(self, event = None):
		if hasattr(self.tcframe, "preview"):
			safe_margin = 5
			scrollbarwidth = 20
			self.tcframe.patchsizer.SetCols((self.tcframe.preview.GetSize()[0] - scrollbarwidth - safe_margin) / 20)
		if self.tcframe.IsShownOnScreen() and not self.tcframe.IsMaximized() and not self.tcframe.IsIconized():
			w, h = self.tcframe.GetSize()
			self.setcfg("size.tcgen.w", w)
			self.setcfg("size.tcgen.h", h)
		if event:
			event.Skip()

	def tc_grid_cell_change_handler(self, event):
		sample = self.ti1.queryv1("DATA")[event.GetRow()]
		label = self.tcframe.grid.GetColLabelValue(event.GetCol())
		value = self.tcframe.grid.GetCellValue(event.GetRow(), event.GetCol()).replace(",", ".")
		try:
			value = float(value)
		except ValueError, exception:
			if label in self.ti1.queryv1("DATA_FORMAT").values():
				value = sample[label]
			else:
				value = ""
		else:
			if label in ("RGB_R", "RGB_G", "RGB_B"):
				if value > 100:
					value = 100.0
				elif value < 0:
					value = 0.0
				sample[label] = value
				RGB = argyllRGB2XYZ(*[component / 100.0 for component in (sample["RGB_R"], sample["RGB_G"], sample["RGB_B"])])
				sample["XYZ_X"], sample["XYZ_Y"], sample["XYZ_Z"] = [component * 100.0 for component in RGB]
				for label in ("XYZ_X", "XYZ_Y", "XYZ_Z"):
					for col in range(self.tcframe.grid.GetNumberCols()):
						if self.tcframe.grid.GetColLabelValue(col) == label:
							self.tcframe.grid.SetCellValue(event.GetRow(), col, str(round(sample[label], 4)))
			elif label in ("XYZ_X", "XYZ_Y", "XYZ_Z"):
				if value < 0:
					value = 0.0
				sample[label] = value
				XYZ = XYZ2RGB(*[component / 100.0 for component in (sample["XYZ_X"], sample["XYZ_Y"], sample["XYZ_Z"])])
				sample["RGB_R"], sample["RGB_G"], sample["RGB_B"] = [component * 100.0 for component in XYZ]
				for label in ("RGB_R", "RGB_G", "RGB_B"):
					for col in range(self.tcframe.grid.GetNumberCols()):
						if self.tcframe.grid.GetColLabelValue(col) == label:
							self.tcframe.grid.SetCellValue(event.GetRow(), col, str(round(sample[label], 4)))
			self.tc_grid_setcolorlabel(event.GetRow())
			self.tcframe.tc_vrml.SetValue(False)
			self.ti1_wrl = None
			self.tcframe.save_btn.Enable(self.ti1.modified and os.path.exists(self.ti1.filename))
			if hasattr(self.tcframe, "preview"):
				patch = self.tcframe.patchsizer.GetItem(event.GetRow()).GetWindow()
				self.tc_patch_setcolorlabel(patch)
				patch.Refresh()
		self.tcframe.grid.SetCellValue(event.GetRow(), event.GetCol(), CGATS.rcut(value, sample.parent.vmaxlen))

	def tc_white_patches_handler(self, event = None):
		self.setcfg("tc_white_patches", self.tcframe.tc_white_patches.GetValue())
		self.tc_check()
		if event:
			event.Skip()

	def tc_single_channel_patches_handler(self, event = None):
		if event:
			event = CustomEvent(event.GetEventType(), event.GetEventObject())
		if event and event.GetEventType() == wx.EVT_TEXT.typeId:
			wx.CallLater(3000, self.tc_single_channel_patches_handler2, event) # 3 seconds delay to allow user to finish keying in a value before it is validated
		else:
			wx.CallAfter(self.tc_single_channel_patches_handler2, event)

	def tc_single_channel_patches_handler2(self, event = None):
		if self.tcframe.tc_single_channel_patches.GetValue() == 1:
			if event and event.GetEventType() in (0, wx.EVT_SPINCTRL.typeId) and self.getcfg("tc_single_channel_patches") == 2: # decrease
				self.tcframe.tc_single_channel_patches.SetValue(0)
			else: # increase
				self.tcframe.tc_single_channel_patches.SetValue(2)
		self.setcfg("tc_single_channel_patches", self.tcframe.tc_single_channel_patches.GetValue())
		self.tc_check()

	def tc_gray_handler(self, event = None):
		if event:
			event = CustomEvent(event.GetEventType(), event.GetEventObject())
		if event and event.GetEventType() == wx.EVT_TEXT.typeId:
			wx.CallLater(3000, self.tc_gray_handler2, event) # 3 seconds delay to allow user to finish keying in a value before it is validated
		else:
			wx.CallAfter(self.tc_gray_handler2, event)

	def tc_gray_handler2(self, event = None):
		if self.tcframe.tc_gray_patches.GetValue() == 1:
			if event and event.GetEventType() in (0, wx.EVT_SPINCTRL.typeId) and self.getcfg("tc_gray_patches") == 2: # decrease
				self.tcframe.tc_gray_patches.SetValue(0)
			else: # increase
				self.tcframe.tc_gray_patches.SetValue(2)
		self.setcfg("tc_gray_patches", self.tcframe.tc_gray_patches.GetValue())
		self.tc_check()

	def tc_fullspread_handler(self, event = None):
		self.setcfg("tc_fullspread_patches", self.tcframe.tc_fullspread_patches.GetValue())
		self.tc_algo_handler()
		self.tc_check()

	def tc_get_total_patches(self, white_patches = None, single_channel_patches = None, gray_patches = None, multi_steps = None, fullspread_patches = None):
		if hasattr(self, "ti1") and [white_patches, single_channel_patches, gray_patches, multi_steps, fullspread_patches] == [None] * 5:
			return self.ti1.queryv1("NUMBER_OF_SETS")
		if white_patches is None:
			white_patches = self.tcframe.tc_white_patches.GetValue()
		if single_channel_patches is None:
			single_channel_patches = self.tcframe.tc_single_channel_patches.GetValue()
		single_channel_patches_total = single_channel_patches * 3
		if gray_patches is None:
			gray_patches = self.tcframe.tc_gray_patches.GetValue()
		if gray_patches == 0 and single_channel_patches > 0 and white_patches > 0:
			gray_patches = 2
		if multi_steps is None:
			multi_steps = self.tcframe.tc_multi_steps.GetValue()
		if fullspread_patches is None:
			fullspread_patches = self.tcframe.tc_fullspread_patches.GetValue()
		total_patches = 0
		if multi_steps > 1:
			multi_patches = int(math.pow(multi_steps, 3))
			total_patches += multi_patches
			white_patches -= 1 # white always in multi channel patches

			multi_step = 255.0 / (multi_steps - 1)
			multi_values = []
			for i in range(multi_steps):
				multi_values += [str(multi_step * i)]
			if debug: safe_print("multi_values", multi_values)
			if single_channel_patches > 1:
				single_channel_step = 255.0 / (single_channel_patches - 1)
				for i in range(single_channel_patches):
					if debug: safe_print("single_channel_value", single_channel_step * i)
					if str(single_channel_step * i) in multi_values:
						if debug: safe_print("DELETE SINGLE", single_channel_step * i)
						single_channel_patches_total -= 3
			if gray_patches > 1:
				gray_step = 255.0 / (gray_patches - 1)
				for i in range(gray_patches):
					if debug: safe_print("gray_value", gray_step * i)
					if str(gray_step * i) in multi_values:
						if debug: safe_print("DELETE GRAY", gray_step * i)
						gray_patches -= 1
		elif gray_patches > 1:
			white_patches -= 1 # white always in gray patches
			single_channel_patches_total -= 3 # black always in gray patches
		else:
			single_channel_patches_total -= 2 # black always only once in single channel patches
		self.tc_white_patches_amount = max(0, white_patches)
		total_patches += self.tc_white_patches_amount + max(0, single_channel_patches_total) + max(0, gray_patches) + fullspread_patches
		if debug: safe_print("total_patches", total_patches)
		return total_patches

	def tc_multi_steps_handler(self, event = None):
		if event:
			event = CustomEvent(event.GetEventType(), event.GetEventObject())
		if event and event.GetEventType() == wx.EVT_TEXT.typeId:
			wx.CallLater(3000, self.tc_multi_steps_handler2, event) # 3 seconds delay to allow user to finish keying in a value before it is validated
		else:
			wx.CallAfter(self.tc_multi_steps_handler2, event)

	def tc_multi_steps_handler2(self, event = None):
		if self.tcframe.tc_multi_steps.GetValue() == 1:
			if event and event.GetEventType() in (0, wx.EVT_SPINCTRL.typeId) and self.getcfg("tc_multi_steps") == 2: # decrease
				self.tcframe.tc_multi_steps.SetValue(0)
			else: # increase
				self.tcframe.tc_multi_steps.SetValue(2)
		multi_steps = self.tcframe.tc_multi_steps.GetValue()
		multi_patches = int(math.pow(multi_steps, 3))
		self.tcframe.tc_multi_patches.SetLabel(self.getlstr("tc.multidim.patches", (multi_patches, multi_steps)))
		self.setcfg("tc_multi_steps", self.tcframe.tc_multi_steps.GetValue())
		self.tc_check()

	def tc_algo_handler(self, event = None):
		tc_algo_enable = self.tcframe.tc_fullspread_patches.GetValue() > 0
		self.tcframe.tc_algo.Enable(tc_algo_enable)
		tc_algo = self.tc_algos_ba[self.tcframe.tc_algo.GetStringSelection()]
		self.tcframe.tc_adaption_slider.Enable(tc_algo_enable and tc_algo == "")
		self.tcframe.tc_adaption_intctrl.Enable(tc_algo_enable and tc_algo == "")
		tc_precond_enable = (tc_algo in ("I", "R", "t") or (tc_algo == "" and self.tcframe.tc_adaption_slider.GetValue() > 0))
		self.tcframe.tc_precond.Enable(tc_algo_enable and tc_precond_enable and bool(self.getcfg("tc_precond_profile")))
		if not tc_precond_enable:
			self.tcframe.tc_precond.SetValue(False)
		else:
			self.tcframe.tc_precond.SetValue(bool(int(self.getcfg("tc_precond"))))
		self.tcframe.tc_precond_profile.Enable(tc_algo_enable and tc_precond_enable)
		self.tcframe.tc_angle_slider.Enable(tc_algo_enable and tc_algo in ("i", "I"))
		self.tcframe.tc_angle_intctrl.Enable(tc_algo_enable and tc_algo in ("i", "I"))
		self.setcfg("tc_algo", tc_algo)

	def tc_adaption_handler(self, event = None):
		if event.GetId() == self.tcframe.tc_adaption_slider.GetId():
			self.tcframe.tc_adaption_intctrl.SetValue(self.tcframe.tc_adaption_slider.GetValue())
		else:
			self.tcframe.tc_adaption_slider.SetValue(self.tcframe.tc_adaption_intctrl.GetValue())
		self.setcfg("tc_adaption", self.tcframe.tc_adaption_intctrl.GetValue() / 100.0)
		self.tc_algo_handler()

	def tc_angle_handler(self, event = None):
		if event.GetId() == self.tcframe.tc_angle_slider.GetId():
			self.tcframe.tc_angle_intctrl.SetValue(self.tcframe.tc_angle_slider.GetValue())
		else:
			self.tcframe.tc_angle_slider.SetValue(self.tcframe.tc_angle_intctrl.GetValue())
		self.setcfg("tc_angle", self.tcframe.tc_angle_intctrl.GetValue() / 10000.0)

	def tc_precond_handler(self, event = None):
		self.setcfg("tc_precond", int(self.tcframe.tc_precond.GetValue()))

	def tc_precond_profile_handler(self, event = None):
		tc_precond_enable = bool(self.tcframe.tc_precond_profile.GetPath())
		self.tcframe.tc_precond.Enable(tc_precond_enable)
		self.setcfg("tc_precond_profile", self.tcframe.tc_precond_profile.GetPath())

	def tc_filter_handler(self, event = None):
		self.setcfg("tc_filter", int(self.tcframe.tc_filter.GetValue()))
		self.setcfg("tc_filter_L", self.tcframe.tc_filter_L.GetValue())
		self.setcfg("tc_filter_a", self.tcframe.tc_filter_a.GetValue())
		self.setcfg("tc_filter_b", self.tcframe.tc_filter_b.GetValue())
		self.setcfg("tc_filter_rad", self.tcframe.tc_filter_rad.GetValue())

	def tc_vrml_handler(self, event = None):
		self.setcfg("tc_vrml", int(self.tcframe.tc_vrml.GetValue()))
		self.setcfg("tc_vrml_device", int(self.tcframe.tc_vrml_device.GetValue()))
		self.setcfg("tc_vrml_lab", int(self.tcframe.tc_vrml_lab.GetValue()))
		if hasattr(self, "ti1") and self.tcframe.tc_vrml.GetValue():
			self.tcframe.tc_vrml.SetValue(False)
			InfoDialog(self.tcframe, msg = self.getlstr("testchart.vrml_denied"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])

	def tc_update_controls(self):
		self.tcframe.tc_algo.SetStringSelection(self.tc_algos_ab.get(self.getcfg("tc_algo"), self.tc_algos_ab.get(self.defaults["tc_algo"])))
		self.tcframe.tc_white_patches.SetValue(self.getcfg("tc_white_patches"))
		self.tcframe.tc_single_channel_patches.SetValue(self.getcfg("tc_single_channel_patches"))
		self.tcframe.tc_gray_patches.SetValue(self.getcfg("tc_gray_patches"))
		self.tcframe.tc_multi_steps.SetValue(self.getcfg("tc_multi_steps"))
		self.tc_multi_steps_handler2()
		self.tcframe.tc_fullspread_patches.SetValue(self.getcfg("tc_fullspread_patches"))
		self.tcframe.tc_angle_slider.SetValue(self.getcfg("tc_angle") * 10000)
		self.tc_angle_handler(self.tcframe.tc_angle_slider)
		self.tcframe.tc_adaption_slider.SetValue(self.getcfg("tc_adaption") * 10000)
		self.tc_adaption_handler(self.tcframe.tc_adaption_slider)
		self.tcframe.tc_precond_profile.SetPath(self.getcfg("tc_precond_profile"))
		self.tcframe.tc_filter.SetValue(bool(int(self.getcfg("tc_filter"))))
		self.tcframe.tc_filter_L.SetValue(self.getcfg("tc_filter_L"))
		self.tcframe.tc_filter_a.SetValue(self.getcfg("tc_filter_a"))
		self.tcframe.tc_filter_b.SetValue(self.getcfg("tc_filter_b"))
		self.tcframe.tc_filter_rad.SetValue(self.getcfg("tc_filter_rad"))
		self.tcframe.tc_vrml.SetValue(bool(int(self.getcfg("tc_vrml"))))
		self.tcframe.tc_vrml_lab.SetValue(bool(int(self.getcfg("tc_vrml_lab"))))
		self.tcframe.tc_vrml_device.SetValue(bool(int(self.getcfg("tc_vrml_device"))))

	def tc_check(self, event = None):
		white_patches = self.tcframe.tc_white_patches.GetValue()
		self.tc_amount = self.tc_get_total_patches(white_patches)
		self.tcframe.preview_btn.Enable(self.tc_amount - max(0, self.tc_white_patches_amount) >= 8)
		self.tcframe.clear_btn.Enable(hasattr(self, "ti1"))
		self.tcframe.save_btn.Enable(hasattr(self, "ti1") and self.ti1.modified and os.path.exists(self.ti1.filename))
		self.tcframe.save_as_btn.Enable(hasattr(self, "ti1"))
		self.tc_set_default_status()

	def tc_save_cfg(self):
		self.setcfg("tc_white_patches", self.tcframe.tc_white_patches.GetValue())
		self.setcfg("tc_single_channel_patches", self.tcframe.tc_single_channel_patches.GetValue())
		self.setcfg("tc_gray_patches", self.tcframe.tc_gray_patches.GetValue())
		self.setcfg("tc_multi_steps", self.tcframe.tc_multi_steps.GetValue())
		self.setcfg("tc_fullspread_patches", self.tcframe.tc_fullspread_patches.GetValue())
		tc_algo = self.tc_algos_ba[self.tcframe.tc_algo.GetStringSelection()]
		self.setcfg("tc_algo", tc_algo)
		self.setcfg("tc_angle", self.tcframe.tc_angle_intctrl.GetValue() / 10000.0)
		self.setcfg("tc_adaption", self.tcframe.tc_adaption_intctrl.GetValue() / 100.0)
		tc_precond_enable = tc_algo in ("I", "R", "t") or (tc_algo == "" and self.tcframe.tc_adaption_slider.GetValue() > 0)
		if tc_precond_enable:
			self.setcfg("tc_precond", int(self.tcframe.tc_precond.GetValue()))
		self.setcfg("tc_precond_profile", self.tcframe.tc_precond_profile.GetPath())
		self.setcfg("tc_filter", int(self.tcframe.tc_filter.GetValue()))
		self.setcfg("tc_filter_L", self.tcframe.tc_filter_L.GetValue())
		self.setcfg("tc_filter_a", self.tcframe.tc_filter_a.GetValue())
		self.setcfg("tc_filter_b", self.tcframe.tc_filter_b.GetValue())
		self.setcfg("tc_filter_rad", self.tcframe.tc_filter_rad.GetValue())
		self.setcfg("tc_vrml", int(self.tcframe.tc_vrml.GetValue()))
		self.setcfg("tc_vrml_lab", int(self.tcframe.tc_vrml_lab.GetValue()))
		self.setcfg("tc_vrml_device", int(self.tcframe.tc_vrml_device.GetValue()))

	def tc_preview_handler(self, event = None):
		if self.is_working():
			return
		if not self.tc_check_save_ti1():
			return
		if not self.check_set_argyll_bin():
			return
		# if sys.platform == "win32":
			# sp.call("cls", shell = True)
		# else:
			# sp.call('clear', shell = True)
		safe_print("-" * 80)
		safe_print(self.getlstr("testchart.create"))
		self.start_worker(self.tc_preview, self.tc_create, wargs = (), wkwargs = {}, progress_title = self.getlstr("testchart.create"), parent = self.tcframe, progress_start = 500)

	def tc_clear_handler(self, event):
		self.tc_check_save_ti1()

	def tc_clear(self):
		grid = self.tcframe.grid
		if grid.GetNumberRows() > 0:
			grid.DeleteRows(0, grid.GetNumberRows())
		if grid.GetNumberCols() > 0:
			grid.DeleteCols(0, grid.GetNumberCols())
		if hasattr(self.tcframe, "preview"):
			self.tcframe.preview.Freeze()
			self.tcframe.patchsizer.Clear(True)
			self.tcframe.preview.Layout()
			self.tcframe.preview.FitInside()
			self.tcframe.preview.SetScrollbars(20, 20, 0, 0)
			self.tcframe.preview.Thaw()
		if hasattr(self, "ti1"):
			del self.ti1
		self.ti1_wrl = None
		self.tc_update_controls()
		self.tc_check()
		self.tcframe.SetTitle(self.getlstr("testchart.edit"))

	def tc_save_handler(self, event = None):
		self.tc_save_as_handler(event, path = self.ti1.filename)

	def tc_save_as_handler(self, event = None, path = None):
		if path is None or not os.path.exists(path):
			path = None
			defaultDir, defaultFile = self.get_default_path("last_ti1_path")
			dlg = wx.FileDialog(self.tcframe, self.getlstr("testchart.save_as"), defaultDir = defaultDir, defaultFile = defaultFile, wildcard = self.getlstr("filetype.ti1") + "|*.ti1", style = wx.SAVE | wx.OVERWRITE_PROMPT)
			dlg.Center(wx.BOTH)
			if dlg.ShowModal() == wx.ID_OK:
				path = dlg.GetPath()
			dlg.Destroy()
		if path:
			filename, ext = os.path.splitext(path)
			if ext.lower() != ".ti1":
				path += ".ti1"
				if os.path.exists(path):
					dlg = ConfirmDialog(self.tcframe, msg = self.getlstr("dialog.confirm_overwrite", (path)), ok = self.getlstr("overwrite"), cancel = self.getlstr("cancel"), bitmap = self.bitmaps["theme/icons/32x32/dialog-warning"])
					result = dlg.ShowModal()
					dlg.Destroy()
					if result != wx.ID_OK:
						return
			self.setcfg("last_ti1_path", path)
			try:
				file_ = open(path, "w")
				file_.write(str(self.ti1))
				file_.close()
				self.ti1.filename = path
				self.ti1.root.setmodified(False)
				if not self.IsBeingDeleted():
					self.tcframe.SetTitle(self.getlstr("testchart.edit").rstrip(".") + ": " + os.path.basename(path))
			except Exception, exception:
				handle_error("Error - testchart could not be saved: " + str(exception), parent = self.tcframe)
			else:
				if hasattr(self, "ti1_wrl") and self.ti1_wrl != None:
					try:
						wrl = open(os.path.splitext(path)[0] + ".wrl", "wb")
						wrl.write(self.ti1_wrl)
						wrl.close()
					except Exception, exception:
						handle_error("Warning - VRML file could not be saved: " + str(exception), parent = self.tcframe)
				if path != self.getcfg("testchart.file"):
					dlg = ConfirmDialog(self.tcframe, msg = self.getlstr("testchart.confirm_select"), ok = self.getlstr("testchart.select"), cancel = self.getlstr("testchart.dont_select"), bitmap = self.bitmaps["theme/icons/32x32/dialog-question"])
					result = dlg.ShowModal()
					dlg.Destroy()
					if result == wx.ID_OK:
						if self.IsBeingDeleted():
							self.setcfg("testchart.file", path)
						else:
							self.set_testchart(path)
				if not self.IsBeingDeleted():
					self.tcframe.save_btn.Disable()
				return True
		return False

	def tc_check_save_ti1(self, clear = True):
		if hasattr(self, "ti1"):
			if self.ti1.root.modified or not os.path.exists(self.ti1.filename):
				if os.path.exists(self.ti1.filename):
					ok = self.getlstr("testchart.save")
				else:
					ok = self.getlstr("testchart.save_as")
				dlg = ConfirmDialog(self.tcframe, msg = self.getlstr("testchart.save_or_discard"), ok = ok, cancel = self.getlstr("cancel"), bitmap = self.bitmaps["theme/icons/32x32/dialog-warning"])
				if self.IsBeingDeleted():
					dlg.sizer2.Hide(0)
				if os.path.exists(self.ti1.filename):
					dlg.save_as = wx.Button(dlg, -1, self.getlstr("testchart.save_as"))
					dlg.save_as.SetInitialSize((dlg.save_as.GetSize()[0] + btn_width_correction, -1))
					ID_SAVE_AS = dlg.save_as.GetId()
					dlg.Bind(wx.EVT_BUTTON, dlg.OnClose, id = ID_SAVE_AS)
					dlg.sizer2.Add((12, 12))
					dlg.sizer2.Add(dlg.save_as)
				else:
					ID_SAVE_AS = wx.ID_OK
				dlg.discard = wx.Button(dlg, -1, self.getlstr("testchart.discard"))
				dlg.discard.SetInitialSize((dlg.discard.GetSize()[0] + btn_width_correction, -1))
				ID_DISCARD = dlg.discard.GetId()
				dlg.Bind(wx.EVT_BUTTON, dlg.OnClose, id = ID_DISCARD)
				dlg.sizer2.Add((12, 12))
				dlg.sizer2.Add(dlg.discard)
				dlg.sizer0.SetSizeHints(dlg)
				dlg.sizer0.Layout()
				result = dlg.ShowModal()
				dlg.Destroy()
				if result in (wx.ID_OK, ID_SAVE_AS):
					if result == ID_SAVE_AS:
						path = None
					else:
						path = self.ti1.filename
					if not self.tc_save_as_handler(event = None, path = path):
						return False
				elif result == wx.ID_CANCEL:
					return False
				clear = True
			if clear and not self.IsBeingDeleted():
				self.tc_clear()
		return True

	def tc_close_handler(self, event = None):
		if (not event or self.tcframe.IsShownOnScreen()) and self.tc_check_save_ti1(False):
			self.tcframe.Hide()
			return True

	def tc_move_handler(self, event = None):
		if self.tcframe.IsShownOnScreen() and not self.tcframe.IsMaximized() and not self.tcframe.IsIconized():
			x, y = self.tcframe.GetScreenPosition()
			self.setcfg("position.tcgen.x", x)
			self.setcfg("position.tcgen.y", y)
		if event:
			event.Skip()

	def tc_destroy_handler(self, event):
		event.Skip()

	def tc_load_cfg_from_ti1(self, event = None, path = None):
		if self.is_working():
			return

		if path is None:
			path = self.getcfg("testchart.file")
		try:
			filename, ext = os.path.splitext(path)
			if ext.lower() in (".ti1", ".ti3"):
				if ext.lower() == ".ti3":
					ti1 = CGATS.CGATS(ti3_to_ti1(open(path, "rU")))
					ti1.filename = filename + ".ti1"
				else:
					ti1 = CGATS.CGATS(path)
					ti1.filename = path
			else: # icc or icm profile
				profile = ICCP.ICCProfile(path)
				ti1 = CGATS.CGATS(ti3_to_ti1(profile.tags.CIED))
				ti1.filename = filename + ".ti1"
			ti1_1 = get_ti1_1(ti1)
			if ti1_1:
				if not self.tc_check_save_ti1():
					return
				ti1.root.setmodified(False)
				self.ti1 = ti1
				self.tcframe.SetTitle(self.getlstr("testchart.edit").rstrip(".") + ": " + os.path.basename(ti1.filename))
			else:
				InfoDialog(self, msg = self.getlstr("error.testchart.invalid", path), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
				return False
		except Exception, exception:
			InfoDialog(self.tcframe, msg = self.getlstr("error.testchart.read", path) + "\n\n" + unicode(str(exception), enc, "replace"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
			return False
		safe_print(self.getlstr("testchart.read"))
		self.start_worker(self.tc_load_cfg_from_ti1_finish, self.tc_load_cfg_from_ti1_worker, wargs = (), wkwargs = {}, progress_title = self.getlstr("testchart.read"), parent = self.tcframe, progress_start = 500)

	def tc_load_cfg_from_ti1_worker(self):
		if test:
			white_patches = None
			single_channel_patches = None
			gray_patches = None
			multi_steps = None
		else:
			white_patches = self.ti1.queryv1("WHITE_COLOR_PATCHES")
			single_channel_patches = self.ti1.queryv1("SINGLE_DIM_STEPS")
			gray_patches = self.ti1.queryv1("COMP_GREY_STEPS")
			multi_steps = self.ti1.queryv1("MULTI_DIM_STEPS")
		fullspread_patches = self.ti1.queryv1("NUMBER_OF_SETS")

		if None in (white_patches, single_channel_patches, gray_patches, multi_steps):
			if None in (single_channel_patches, gray_patches, multi_steps):
				white_patches = 0
				R = []
				G = []
				B = []
				gray_channel = [0]
				data = self.ti1.queryv1("DATA")
				multi = {
					"R": [],
					"G": [],
					"B": []
				}
				uniqueRGB = []
				vmaxlen = 4
				for i in data:
					patch = [round(float(str(v * 2.55)), vmaxlen) for v in (data[i]["RGB_R"], data[i]["RGB_G"], data[i]["RGB_B"])] # normalize to 0...255 range
					strpatch = [str(int(round(round(v, 1)))) for v in patch]
					if patch[0] == patch[1] == patch[2] == 255: # white
						white_patches += 1
						if 255 not in gray_channel:
							gray_channel += [255]
					elif patch[0] == patch[1] == patch[2] == 0: # black
						if 0 not in R and 0 not in G and 0 not in B:
							R += [0]
							G += [0]
							B += [0]
						if 0 not in gray_channel:
							gray_channel += [0]
					elif patch[2] == patch[1] == 0 and patch[0] not in R: # red
						R += [patch[0]]
					elif patch[0] == patch[2] == 0 and patch[1] not in G: # green
						G += [patch[1]]
					elif patch[0] == patch[1] == 0 and patch[2] not in B: # blue
						B += [patch[2]]
					elif patch[0] == patch[1] == patch[2] and patch[0] not in gray_channel: # gray
						gray_channel += [patch[0]]
					if debug >= 9: safe_print(strpatch)
					if strpatch not in uniqueRGB:
						uniqueRGB += [strpatch]
						if patch[0] not in multi["R"]:
							multi["R"] += [patch[0]]
						if patch[1] not in multi["G"]:
							multi["G"] += [patch[1]]
						if patch[2] not in multi["B"]:
							multi["B"] += [patch[2]]

				if single_channel_patches is None:
					R_inc = self.tc_get_increments(R, vmaxlen)
					G_inc = self.tc_get_increments(G, vmaxlen)
					B_inc = self.tc_get_increments(B, vmaxlen)
					if debug: 
						safe_print("R_inc:")
						for i in R_inc:
							safe_print("%s: x%s" % (i, R_inc[i]))
						safe_print("G_inc:")
						for i in G_inc:
							safe_print("%s: x%s" % (i, G_inc[i]))
						safe_print("B_inc:")
						for i in B_inc:
							safe_print("%s: x%s" % (i, B_inc[i]))
					RGB_inc = {"0": 0}
					for inc in R_inc:
						if inc in G_inc and inc in B_inc and R_inc[inc] == G_inc[inc] == B_inc[inc]:
							RGB_inc[inc] = R_inc[inc]
					for inc in G_inc:
						if inc in R_inc and inc in B_inc and R_inc[inc] == G_inc[inc] == B_inc[inc]:
							RGB_inc[inc] = G_inc[inc]
					for inc in B_inc:
						if inc in R_inc and inc in G_inc and R_inc[inc] == G_inc[inc] == B_inc[inc]:
							RGB_inc[inc] = B_inc[inc]
					if False:
						RGB_inc_max = max(RGB_inc.values())
						if RGB_inc_max > 0:
							single_channel_patches = RGB_inc_max + 1
						else:
							single_channel_patches = 0
					else:
						single_inc = {"0": 0}
						for inc in RGB_inc:
							if inc != "0":
								finc = float(inc)
								n = int(round(float(str(255.0 / finc))))
								finc = 255.0 / n
								n += 1
								if debug >= 9:
									safe_print("inc:", inc)
									safe_print("n:", n)
								for i in range(n):
									v = str(int(round(float(str(i * finc)))))
									if debug >= 9: safe_print("Searching for", v)
									if [v, "0", "0"] in uniqueRGB and ["0", v, "0"] in uniqueRGB and ["0", "0", v] in uniqueRGB:
										if not inc in single_inc:
											single_inc[inc] = 0
										single_inc[inc] += 1
									else:
										if debug >= 9: safe_print("Not found!")
										break
						single_channel_patches = max(single_inc.values())
					if debug:
						safe_print("single_channel_patches:", single_channel_patches)
					if 0 in R + G + B:
						fullspread_patches += 3 # black in single channel patches
				elif single_channel_patches >= 2:
					fullspread_patches += 3 # black always in SINGLE_DIM_STEPS

				if gray_patches is None:
					RGB_inc = self.tc_get_increments(gray_channel, vmaxlen)
					if debug:
						safe_print("RGB_inc:")
						for i in RGB_inc:
							safe_print("%s: x%s" % (i, RGB_inc[i]))
					if False:
						RGB_inc_max = max(RGB_inc.values())
						if RGB_inc_max > 0:
							gray_patches = RGB_inc_max + 1
						else:
							gray_patches = 0
					else:
						gray_inc = {"0": 0}
						for inc in RGB_inc:
							if inc != "0":
								finc = float(inc)
								n = int(round(float(str(255.0 / finc))))
								finc = 255.0 / n
								n += 1
								if debug >= 9:
									safe_print("inc:", inc)
									safe_print("n:", n)
								for i in range(n):
									v = str(int(round(float(str(i * finc)))))
									if debug >= 9: safe_print("Searching for", v)
									if [v, v, v] in uniqueRGB:
										if not inc in gray_inc:
											gray_inc[inc] = 0
										gray_inc[inc] += 1
									else:
										if debug >= 9: safe_print("Not found!")
										break
						gray_patches = max(gray_inc.values())
					if debug:
						safe_print("gray_patches:", gray_patches)
					if 0 in gray_channel:
						fullspread_patches += 1 # black in gray patches
					if 255 in gray_channel:
						fullspread_patches += 1 # white in gray patches
				elif gray_patches >= 2:
					fullspread_patches += 2 # black and white always in COMP_GREY_STEPS

				if multi_steps is None:
					R_inc = self.tc_get_increments(multi["R"], vmaxlen)
					G_inc = self.tc_get_increments(multi["G"], vmaxlen)
					B_inc = self.tc_get_increments(multi["B"], vmaxlen)
					RGB_inc = {"0": 0}
					for inc in R_inc:
						if inc in G_inc and inc in B_inc and R_inc[inc] == G_inc[inc] == B_inc[inc]:
							RGB_inc[inc] = R_inc[inc]
					for inc in G_inc:
						if inc in R_inc and inc in B_inc and R_inc[inc] == G_inc[inc] == B_inc[inc]:
							RGB_inc[inc] = G_inc[inc]
					for inc in B_inc:
						if inc in R_inc and inc in G_inc and R_inc[inc] == G_inc[inc] == B_inc[inc]:
							RGB_inc[inc] = B_inc[inc]
					if debug:
						safe_print("RGB_inc:")
						for i in RGB_inc:
							safe_print("%s: x%s" % (i, RGB_inc[i]))
					multi_inc = {"0": 0}
					for inc in RGB_inc:
						if inc != "0":
							finc = float(inc)
							n = int(round(float(str(255.0 / finc))))
							finc = 255.0 / n
							n += 1
							if debug >= 9:
								safe_print("inc:", inc)
								safe_print("n:", n)
							for i in range(n):
								r = str(int(round(float(str(i * finc)))))
								for j in range(n):
									g = str(int(round(float(str(j * finc)))))
									for k in range(n):
										b = str(int(round(float(str(k * finc)))))
										if debug >= 9:
											safe_print("Searching for", i, j, k, [r, g, b])
										if [r, g, b] in uniqueRGB:
											if not inc in multi_inc:
												multi_inc[inc] = 0
											multi_inc[inc] += 1
										else:
											if debug >= 9: safe_print("Not found! (b loop)")
											break
									if [r, g, b] not in uniqueRGB:
										if debug >= 9: safe_print("Not found! (g loop)")
										break
								if [r, g, b] not in uniqueRGB:
									if debug >= 9: safe_print("Not found! (r loop)")
									break
					multi_patches = max(multi_inc.values())
					multi_steps = int(float(str(math.pow(multi_patches, 1 / 3.0))))
					if debug:
						safe_print("multi_patches:", multi_patches)
						safe_print("multi_steps:", multi_steps)
				elif multi_steps >= 2:
					fullspread_patches += 2 # black and white always in MULTI_DIM_STEPS
			else:
				white_patches = len(self.ti1[0].queryi({"RGB_R": 100, "RGB_G": 100, "RGB_B": 100}))
				if single_channel_patches >= 2:
					fullspread_patches += 3 # black always in SINGLE_DIM_STEPS
				if gray_patches >= 2:
					fullspread_patches += 2 # black and white always in COMP_GREY_STEPS
				if multi_steps >= 2:
					fullspread_patches += 2 # black and white always in MULTI_DIM_STEPS
			fullspread_patches -= white_patches
			fullspread_patches -= single_channel_patches * 3
			fullspread_patches -= gray_patches
			fullspread_patches -= int(float(str(math.pow(multi_steps, 3)))) - single_channel_patches * 3

		return white_patches, single_channel_patches, gray_patches, multi_steps, fullspread_patches

	def tc_load_cfg_from_ti1_finish(self, result):
		if result:
			safe_print(self.getlstr("success"))
			white_patches, single_channel_patches, gray_patches, multi_steps, fullspread_patches = result

			fullspread_ba = {
				"ERROR_OPTIMISED_PATCHES": "", # OFPS
				#"ERROR_OPTIMISED_PATCHES": "R", # Perc. space random - same keyword as OFPS :(
				"INC_FAR_PATCHES": "t", # Inc. far point
				"RANDOM_PATCHES": "r", # Dev. space random
				"SIMPLEX_DEVICE_PATCHES": "i", # Dev. space cubic grid
				"SIMPLEX_PERCEPTUAL_PATCHES": "I", # Perc. space cubic grid
				"SPACEFILING_RANDOM_PATCHES": "q",
				"SPACEFILLING_RANDOM_PATCHES": "q", # typo in Argyll. Corrected it here in advance so things don't break in the future.
			}

			algo = None

			for key in fullspread_ba.keys():
				if self.ti1.queryv1(key) > 0:
					algo = fullspread_ba[key]
					break

			if white_patches != None: self.setcfg("tc_white_patches", white_patches)
			if single_channel_patches != None: self.setcfg("tc_single_channel_patches", single_channel_patches)
			if gray_patches != None: self.setcfg("tc_gray_patches", gray_patches)
			if multi_steps != None: self.setcfg("tc_multi_steps", multi_steps)
			self.setcfg("tc_fullspread_patches", self.ti1.queryv1("NUMBER_OF_SETS") - self.tc_get_total_patches(white_patches, single_channel_patches, gray_patches, multi_steps, 0))
			if algo != None: self.setcfg("tc_algo", algo)
			self.write_cfg()

			self.tc_update_controls()
			self.tcframe.tc_vrml.SetValue(False)
			self.ti1_wrl = None
			self.tc_preview(True)
			return True
		else:
			safe_print(self.getlstr("failure"))
			self.tc_update_controls()
			self.tc_check()
			self.start_timers()

	def tc_get_increments(self, channel, vmaxlen = 4):
		channel.sort()
		increments = {"0": 0}
		for i in range(len(channel)):
			rev = range(i, len(channel))
			rev.reverse()
			for j in rev:
				inc = round(float(str(channel[j] - channel[i])), vmaxlen)
				if inc > 0:
					inc = str(inc)
					if not inc in increments:
						increments[inc] = 0
					increments[inc] += 1
		return increments

	def tc_create(self):
		self.write_cfg()
		cmd, args = self.prepare_targen(parent = self.tcframe)
		result = self.exec_cmd(cmd, args, low_contrast = False, skip_cmds = True, silent = True, parent = self.tcframe)
		if result:
			self.create_tempdir()
			if self.tempdir:
				path = os.path.join(self.tempdir, "temp.ti1")
				result = self.check_file_isfile(path, silent = False)
				if result:
					try:
						self.ti1 = CGATS.CGATS(path)
						safe_print(self.getlstr("success"))
					except Exception, exception:
						handle_error("Error - testchart file could not be read: " + str(exception), parent = self.tcframe)
						result = False
					if self.tcframe.tc_vrml.GetValue():
						try:
							wrl = open(os.path.join(self.tempdir, "temp.wrl"), "rb")
							self.ti1_wrl = wrl.read()
							wrl.close()
						except Exception, exception:
							handle_error("Warning - VRML file could not be read: " + str(exception), parent = self.tcframe)
			else:
				result = False
		self.wrapup(False)
		return result

	def tc_preview(self, result):
		self.tc_check()
		if result:
			if verbose >= 1: safe_print(self.getlstr("tc.preview.create"))
			data = self.ti1.queryv1("DATA")

			if hasattr(self.tcframe, "preview"):
				self.tcframe.preview.Freeze()

			grid = self.tcframe.grid
			data_format = self.ti1.queryv1("DATA_FORMAT")
			for i in data_format:
				if data_format[i] in ("RGB_R", "RGB_G", "RGB_B"):
					grid.AppendCols(1)
					grid.SetColLabelValue(grid.GetNumberCols() - 1, data_format[i])
			grid.AppendCols(1)
			grid.SetColLabelValue(grid.GetNumberCols() - 1, "")
			colwidth = 100
			for i in range(grid.GetNumberCols() - 1):
				grid.SetColSize(i, colwidth)
			grid.SetColSize(grid.GetNumberCols() - 1, 20)
			grid.AppendRows(self.tc_amount)
			grid.SetRowLabelSize(colwidth)
			attr = wx.grid.GridCellAttr()
			attr.SetAlignment(wx.ALIGN_CENTER, wx.ALIGN_CENTER)
			attr.SetReadOnly()
			grid.SetColAttr(grid.GetNumberCols() - 1, attr)

			for i in data:
				sample = data[i]
				for j in range(grid.GetNumberCols()):
					label = grid.GetColLabelValue(j)
					if label in ("RGB_R", "RGB_G", "RGB_B"):
						grid.SetCellValue(i, j, str(sample[label]))
				self.tc_grid_setcolorlabel(i)
				self.tc_add_patch(i, sample)

			if hasattr(self.tcframe, "preview"):
				self.tcframe.patchsizer.Layout()
				self.tcframe.preview.sizer.Layout()
				self.tcframe.preview.FitInside()
				self.tcframe.preview.SetScrollRate(20, 20)
				self.tcframe.preview.Thaw()

			self.tc_set_default_status()
			if verbose >= 1: safe_print(self.getlstr("success"))
		self.start_timers()

	def tc_add_patch(self, before, sample):
		if hasattr(self.tcframe, "preview"):
			patch = wx.Panel(self.tcframe.preview, -1)
			patch.Bind(wx.EVT_ENTER_WINDOW, self.tc_mouseover_handler, id = patch.GetId())
			patch.Bind(wx.EVT_LEFT_DOWN, self.tc_mouseclick_handler, id = patch.GetId())
			patch.SetMinSize((20,20))
			patch.sample = sample
			self.tcframe.patchsizer.Insert(before, patch)
			self.tc_patch_setcolorlabel(patch)

	def tc_grid_setcolorlabel(self, row):
		grid = self.tcframe.grid
		col = grid.GetNumberCols() - 1
		sample = self.ti1.queryv1("DATA")[row]
		style, colour, labeltext, labelcolour = self.tc_getcolorlabel(sample)
		grid.SetCellBackgroundColour(row, col, colour)
		grid.SetCellValue(row, col, labeltext)
		if labelcolour:
			grid.SetCellTextColour(row, col, labelcolour)

	def tc_getcolorlabel(self, sample):
		scale = 2.55
		colour = wx.Colour(*[round(value * scale) for value in (sample.RGB_R, sample.RGB_G, sample.RGB_B)])
		# mark patches:
		# W = white (R/G/B == 100)
		# K = black (R/G/B == 0)
		# k = light black (R == G == B > 0)
		# R = red
		# r = light red (R == 100 and G/B > 0)
		# G = green
		# g = light green (G == 100 and R/B > 0)
		# B = blue
		# b = light blue (B == 100 and R/G > 0)
		# C = cyan
		# c = light cyan (G/B == 100 and R > 0)
		# M = magenta
		# m = light magenta (R/B == 100 and G > 0)
		# Y = yellow
		# y = light yellow (R/G == 100 and B > 0)
		# border = 50% value
		style = wx.NO_BORDER
		if sample.RGB_R == sample.RGB_G == sample.RGB_B: # Neutral / black / white
			if sample.RGB_R < 50:
				labelcolour = wx.Colour(255, 255, 255)
			else:
				if sample.RGB_R == 50:
					style = wx.SIMPLE_BORDER
				labelcolour = wx.Colour(0, 0, 0)
			if sample.RGB_R <= 50:
				labeltext = "K"
			elif sample.RGB_R == 100:
				labeltext = "W"
			else:
				labeltext = "k"
		elif (sample.RGB_G == 0 and sample.RGB_B == 0) or (sample.RGB_R == 100 and sample.RGB_G == sample.RGB_B): # Red
			if sample.RGB_R > 75:
				labelcolour = wx.Colour(0, 0, 0)
			else:
				labelcolour = wx.Colour(255, 255, 255)
				if sample.RGB_R == 50:
					style = wx.SIMPLE_BORDER
			if sample.RGB_R == 100 and sample.RGB_G > 0:
				labeltext = "r"
			else:
				labeltext = "R"
		elif (sample.RGB_R == 0 and sample.RGB_B == 0) or (sample.RGB_G == 100 and sample.RGB_R == sample.RGB_B): # Green
			if sample.RGB_G > 75:
				labelcolour = wx.Colour(0, 0, 0)
			else:
				labelcolour = wx.Colour(255, 255, 255)
				if sample.RGB_G == 50:
					style = wx.SIMPLE_BORDER
			if sample.RGB_G == 100 and sample.RGB_R > 0:
				labeltext = "g"
			else:
				labeltext = "G"
		elif (sample.RGB_R == 0 and sample.RGB_G == 0) or (sample.RGB_B == 100 and sample.RGB_R == sample.RGB_G): # Blue
			if sample.RGB_R > 25:
				labelcolour = wx.Colour(0, 0, 0)
			else:
				labelcolour = wx.Colour(255, 255, 255)
				if sample.RGB_B == 50:
					style = wx.SIMPLE_BORDER
			if sample.RGB_B == 100 and sample.RGB_R > 0:
				labeltext = "b"
			else:
				labeltext = "B"
		elif (sample.RGB_R == 0 or sample.RGB_B == 100) and sample.RGB_G == sample.RGB_B: # Cyan
			if sample.RGB_G > 75:
				labelcolour = wx.Colour(0, 0, 0)
			else:
				labelcolour = wx.Colour(255, 255, 255)
				if sample.RGB_G == 50:
					style = wx.SIMPLE_BORDER
			if sample.RGB_G == 100 and sample.RGB_R > 0:
				labeltext = "c"
			else:
				labeltext = "C"
		elif (sample.RGB_G == 0 or sample.RGB_R == 100) and sample.RGB_R == sample.RGB_B: # Magenta
			if sample.RGB_R > 75:
				labelcolour = wx.Colour(0, 0, 0)
			else:
				labelcolour = wx.Colour(255, 255, 255)
				if sample.RGB_R == 50:
					style = wx.SIMPLE_BORDER
			if sample.RGB_R == 100 and sample.RGB_G > 0:
				labeltext = "m"
			else:
				labeltext = "M"
		elif (sample.RGB_B == 0 or sample.RGB_G == 100) and sample.RGB_R == sample.RGB_G: # Yellow
			if sample.RGB_G > 75:
				labelcolour = wx.Colour(0, 0, 0)
			else:
				labelcolour = wx.Colour(255, 255, 255)
				if sample.RGB_R == 100 and sample.RGB_G == 50:
					style = wx.SIMPLE_BORDER
			if sample.RGB_B > 0:
				labeltext = "y"
			else:
				labeltext = "Y"
		else:
			labeltext = ""
			labelcolour = None
		return style, colour, labeltext, labelcolour

	def tc_patch_setcolorlabel(self, patch):
		if hasattr(self.tcframe, "preview"):
			sample = patch.sample
			style, colour, labeltext, labelcolour = self.tc_getcolorlabel(sample)
			patch.SetBackgroundColour(colour)
			if style:
				patch.SetWindowStyle(style)
			if labeltext:
				if not hasattr(patch, "label"):
					label = patch.label = wx.StaticText(patch, -1, "")
					self.set_font_size(label)
					label.patch = patch
					label.Bind(wx.EVT_ENTER_WINDOW, self.tc_mouseover_handler, id = label.GetId())
					label.Bind(wx.EVT_LEFT_DOWN, self.tc_mouseclick_handler, id = label.GetId())
				else:
					label = patch.label
				label.SetLabel(labeltext)
				label.SetForegroundColour(labelcolour)
				label.Center()
			else:
				if hasattr(patch, "label"):
					patch.label.Destroy()
					del patch.label

	def tc_set_default_status(self, event = None):
		if debug: safe_print("tc_set_default_status")
		if hasattr(self, "tc_amount"):
			statustxt = "%s: %s" % (self.getlstr("tc.patches.total"), self.tc_amount)
			sel = self.tcframe.grid.GetSelectionRows()
			if sel:
				statustxt += " / %s: %s" % (self.getlstr("tc.patches.selected"), len(sel))
			self.tcframe.SetStatusText(statustxt)

	def tc_mouseover_handler(self, event):
		patch = self.tcframe.preview.FindWindowById(event.GetId())
		if hasattr(patch, "patch"):
			patch = patch.patch
		colour = patch.GetBackgroundColour()
		sample = patch.sample
		patchinfo = "%s %s: R=%s G=%s B=%s" % (self.getlstr("tc.patch"), sample.key + 1, colour[0], colour[1], colour[2])
		self.tcframe.SetStatusText("%s: %s / %s" % (self.getlstr("tc.patches.total"), self.tc_amount, patchinfo))
		event.Skip()

	def tc_mouseclick_handler(self, event):
		patch = self.tcframe.preview.FindWindowById(event.GetId())
		if hasattr(patch, "patch"):
			patch = patch.patch
		sample = patch.sample
		self.tc_grid_select_row_handler(sample.key, event.ShiftDown(), event.ControlDown() or event.CmdDown())
		return

	def tc_delete_rows(self, rows):
		self.tcframe.tc_vrml.SetValue(False)
		self.ti1_wrl = None
		self.tcframe.grid.Freeze()
		if hasattr(self.tcframe, "preview"):
			self.tcframe.preview.Freeze()
		rows.sort()
		rows.reverse()
		for row in rows:
			self.tcframe.grid.DeleteRows(row)
			self.ti1.queryv1("DATA").remove(row)
			if hasattr(self.tcframe, "preview"):
				patch = self.tcframe.patchsizer.GetItem(row).GetWindow()
				if self.tcframe.patchsizer.Detach(patch):
					patch.Destroy()
		self.tc_amount = self.ti1.queryv1("NUMBER_OF_SETS")
		row = min(rows[-1], self.tcframe.grid.GetNumberRows() - 1)
		self.tcframe.grid.SelectRow(row)
		self.tcframe.grid.SetGridCursor(row, 0)
		self.tcframe.grid.MakeCellVisible(row, 0)
		self.tcframe.grid.Thaw()
		self.tcframe.save_btn.Enable(self.ti1.modified and os.path.exists(self.ti1.filename))
		if hasattr(self.tcframe, "preview"):
			self.tcframe.preview.Layout()
			self.tcframe.preview.FitInside()
			self.tcframe.preview.Thaw()
		self.tc_set_default_status()

	def set_default_testchart(self, alert = True, force = False):
		path = self.getcfg("testchart.file")
		if os.path.basename(path) in self.app.dist_testchart_names:
			path = self.app.dist_testcharts[self.app.dist_testchart_names.index(os.path.basename(path))]
			self.setcfg("testchart.file", path)
		if force or self.getlstr(os.path.basename(path)) in [""] + self.default_testchart_names or ((not os.path.exists(path) or not os.path.isfile(path))):
			ti1 = self.testchart_defaults[self.get_measurement_mode()][self.get_profile_type()]
			path = get_data_path(os.path.join("ti1", ti1))
			if not path or not os.path.isfile(path):
				if alert:
					InfoDialog(self, msg = self.getlstr("error.testchart.missing", ti1), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
				elif verbose >= 1:
					safe_print(self.getlstr("error.testchart.missing", ti1))
				return False
			else:
				self.set_testchart(path)
			return True
		return None

	def set_testcharts(self, path = None):
		self.testchart_ctrl.Freeze()
		self.testchart_ctrl.SetItems(self.get_testchart_names(path))
		self.testchart_ctrl.Thaw()

	def set_testchart(self, path = None):
		if path is None:
			path = self.getcfg("testchart.file")
		if not self.check_file_isfile(path):
			self.set_default_testchart()
			return
		filename, ext = os.path.splitext(path)
		try:
			if ext.lower() in (".ti1", ".ti3"):
				if ext.lower() == ".ti3":
					ti1 = CGATS.CGATS(ti3_to_ti1(open(path, "rU")))
				else:
					ti1 = CGATS.CGATS(path)
			else: # icc or icm profile
				profile = ICCP.ICCProfile(path)
				ti1 = CGATS.CGATS(ti3_to_ti1(profile.tags.CIED))
			ti1_1 = get_ti1_1(ti1)
			if not ti1_1:
				InfoDialog(self, msg = self.getlstr("error.testchart.invalid", path), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
				self.set_default_testchart()
				return
			if path != self.getcfg("calibration.file"):
				self.profile_settings_changed()
			self.setcfg("testchart.file", path)
			if path not in self.testcharts:
				self.set_testcharts(path)
			# the case-sensitive index could fail because of case insensitive file systems
			# e.g. the filename string from the cfg is "C:\Users\Name\AppData\dispcalGUI\storage\MyFile",
			# but the actual filename is "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
			# (maybe because the user manually renamed the file)
			try:
				idx = self.testcharts.index(path)
			except ValueError, exception:
				idx = indexi(self.testcharts, path)
			self.testchart_ctrl.SetSelection(idx)
			self.testchart_ctrl.UpdateToolTipString(path)
			if ti1.queryv1("COLOR_REP") and ti1.queryv1("COLOR_REP")[:3] == "RGB":
				self.options_targen = ["-d3"]
				if verbose >= 2: safe_print("Setting targen options:", *self.options_targen)
			if self.testchart_ctrl.IsEnabled():
				self.testchart_patches_amount.SetLabel(str(ti1.queryv1("NUMBER_OF_SETS")))
			else:
				self.testchart_patches_amount.SetLabel("")
		except Exception, exception:
			InfoDialog(self, msg = self.getlstr("error.testchart.read", path) + "\n\n" + unicode(str(exception), enc, "replace"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
			self.set_default_testchart()
		else:
			if hasattr(self, "tcframe") and self.tcframe.IsShownOnScreen() and (not hasattr(self, "ti1") or self.getcfg("testchart.file") != self.ti1.filename):
				self.tc_load_cfg_from_ti1()

	def get_testchart_names(self, path = None):
		testchart_names = []
		self.testcharts = []
		if path is None:
			path = self.getcfg("testchart.file")
		if os.path.exists(path):
			testchart_dir = os.path.dirname(path)
			try:
				testcharts = listdir(testchart_dir, "\.(?:icc|icm|ti1|ti3)$")
			except Exception, exception:
				safe_print("Error - directory '%s' listing failed: %s" % (testchart_dir, str(exception)))
			else:
				for testchart_name in testcharts:
					if testchart_name not in testchart_names:
						testchart_names += [testchart_name]
						self.testcharts += [os.pathsep.join((testchart_name, testchart_dir))]
		default_testcharts = get_data_path("ti1", "\.(?:icc|icm|ti1|ti3)$")
		if isinstance(default_testcharts, list):
			for testchart in default_testcharts:
				testchart_dir = os.path.dirname(testchart)
				testchart_name = os.path.basename(testchart)
				if testchart_name not in testchart_names:
					testchart_names += [testchart_name]
					self.testcharts += [os.pathsep.join((testchart_name, testchart_dir))]
		self.testcharts = natsort(self.testcharts)
		self.testchart_names = []
		i = 0
		for chart in self.testcharts:
			chart = chart.split(os.pathsep)
			chart.reverse()
			self.testcharts[i] = os.path.sep.join(chart)
			self.testchart_names += [self.getlstr(chart[-1])]
			i += 1
		return self.testchart_names

	def get_testchart(self):
		return self.getcfg("testchart.file")

	def get_testcharts(self):
		return

	def check_set_argyll_bin(self):
		if self.check_argyll_bin():
			return True
		else:
			return self.set_argyll_bin()
	
	def get_argyll_util(self, name, check_dir = None):
		path = os.getenv("PATH", os.defpath)
		utils = {
			"dispcal": ["argyll-dispcal", "dispcal-argyll", "dispcal"],
			"dispread": ["argyll-dispread", "dispread-argyll", "dispread"],
			"colprof": ["argyll-colprof", "colprof-argyll", "colprof"],
			"dispwin": ["argyll-dispwin", "dispwin-argyll", "dispwin"],
			"spyd2en": ["argyll-spyd2en", "spyd2en-argyll", "spyd2en"],
			"targen": ["argyll-targen", "targen-argyll", "targen"]
		}
		if not check_dir:
			check_dir = self.getcfg("argyll.dir")
		else:
			check_dir = check_dir.rstrip(os.path.sep)
		if check_dir:
			if check_dir in path.split(os.pathsep):
				path = path.split(os.pathsep)
				path.remove(check_dir)
				path = os.pathsep.join(path)
			putenv("PATH", os.pathsep.join([check_dir, path]))
		found = None
		for altname in utils[name]:
			exe = which(altname + exe_ext)
			if exe:
				found = exe
				if (not check_dir or check_dir == os.path.dirname(exe)):
					break
		if check_dir and not found:
			putenv("PATH", path)
		if not found:
			if verbose >= 2: safe_print("Info: ", "|".join(utils[name]), " not found in ", os.getenv("PATH"))
		return found
	
	def get_argyll_utilname(self, name):
		found = self.get_argyll_util(name)
		if found:
			found = os.path.basename(os.path.splitext(found)[0])
		return found

	def check_argyll_bin(self, check_dir = None):
		path = os.getenv("PATH", os.defpath)
		names = [
			"dispcal",
			"dispread",
			"colprof",
			"dispwin",
			"spyd2en",
			"targen"
		]
		if check_dir:
			check_dir = check_dir.rstrip(os.path.sep)
			putenv("PATH", check_dir)
		else:
			check_dir = self.getcfg("argyll.dir")
			if check_dir:
				if check_dir in path.split(os.pathsep):
					path = path.split(os.pathsep)
					path.remove(check_dir)
					path = os.pathsep.join(path)
				putenv("PATH", os.pathsep.join([check_dir, path]))
		prev_dir = None
		for name in names:
			exe = self.get_argyll_util(name, check_dir = check_dir)
			if not exe:
				if check_dir and path:
					putenv("PATH", path)
				return False
			cur_dir = os.path.dirname(exe)
			if prev_dir:
				if cur_dir != prev_dir:
					if check_dir and path:
						putenv("PATH", path)
					if verbose: safe_print("Warning - Argyll executables are scattered. They should be in same directory.")
					return False
			else:
				prev_dir = cur_dir
		if check_dir and not check_dir in path.split(os.pathsep):
			putenv("PATH", os.pathsep.join([check_dir, path]))
		elif os.getenv("PATH", os.defpath) != path:
			putenv("PATH", path)
		if self.getcfg("argyll.dir") != cur_dir:
			self.setcfg("argyll.dir", cur_dir)
		if debug: safe_print("check_argyll_bin OK")
		if debug >= 2: safe_print(" PATH:\n ", "\n  ".join(os.getenv("PATH").split(os.pathsep)))
		return True

	def set_argyll_bin(self):
		if self.IsShownOnScreen():
			parent = self
		else:
			parent = None # do not center on parent if not visible
		defaultPath = os.path.sep.join(self.get_default_path("argyll.dir"))
		dlg = wx.DirDialog(parent, self.getlstr("dialog.set_argyll_bin"), defaultPath = defaultPath, style = wx.DD_DIR_MUST_EXIST)
		dlg.Center(wx.BOTH)
		result = dlg.ShowModal() == wx.ID_OK
		if result:
			path = dlg.GetPath()
			result = self.check_argyll_bin(path)
			if not result:
				InfoDialog(self, msg = self.getlstr("argyll.dir.invalid", (exe_ext, exe_ext, exe_ext, exe_ext, exe_ext)), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
			self.write_cfg()
		dlg.Destroy()
		return result

	def set_argyll_bin_handler(self, event):
		if self.set_argyll_bin():
			self.check_update_controls()
			if len(self.displays):
				if self.getcfg("calibration.file"):
					self.load_cal(silent = True) # load LUT curves from last used .cal file
				else:
					self.load_display_profile_cal(None) # load LUT curves from current display profile (if any, and if it contains curves)

	def check_update_controls(self, event = None, silent = False):
		displays = list(self.displays)
		comports = list(self.comports)
		self.enumerate_displays_and_ports(silent)
		if displays != self.displays:
			self.update_displays()
			if verbose >= 1: safe_print(self.getlstr("display_detected"))
		if comports != self.comports:
			self.update_comports()
			if verbose >= 1: safe_print(self.getlstr("comport_detected"))
		if displays != self.displays or comports != self.comports:
			self.init_menus()
			self.update_main_controls()

	def plugplay_timer_handler(self, event):
		if debug: safe_print("plugplay_timer_handler")
		self.check_update_controls(silent = True)

	def extract_cal(self, source_filename, target_filename = None):
		try:
			profile = ICCP.ICCProfile(source_filename)
		except (IOError, ICCP.ICCProfileInvalidError), exception:
			InfoDialog(self, msg = self.getlstr("profile.invalid"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
			return None
		if "CIED" in profile.tags:
			cal_lines = []
			ti3 = StringIO(profile.tags.CIED)
			ti3_lines = [line.strip() for line in ti3]
			ti3.close()
			cal_found = False
			for line in ti3_lines:
				line = line.strip()
				if line == "CAL":
					line = "CAL    " # Make sure CGATS file identifiers are always a minimum of 7 characters
					cal_found = True
				if cal_found:
					cal_lines += [line]
					if line == 'DEVICE_CLASS "DISPLAY"':
						if "cprt" in profile.tags:
							options_dispcal = self.get_options_from_cprt(profile.tags.cprt)[0]
							if options_dispcal:
								whitepoint = False
								b = profile.tags.lumi
								for o in options_dispcal:
									if o[0] == "y":
										cal_lines += ['KEYWORD "DEVICE_TYPE"']
										if o[1] == "c":
											cal_lines += ['DEVICE_TYPE "CRT"']
										else:
											cal_lines += ['DEVICE_TYPE "LCD"']
										continue
									if o[0] in ("t", "T"):
										continue
									if o[0] == "w":
										continue
									if o[0] in ("g", "G"):
										if o[1:] == "240":
											trc = "SMPTE240M"
										elif o[1:] == "709":
											trc = "REC709"
										elif o[1:] == "l":
											trc = "L_STAR"
										elif o[1:] == "s":
											trc = "sRGB"
										else:
											trc = o[1:]
											if o[0] == "G":
												try:
													trc = 0 - Decimal(trc)
												except decimal.InvalidOperation, exception:
													continue
										cal_lines += ['KEYWORD "TARGET_GAMMA"']
										cal_lines += ['TARGET_GAMMA "%s"' % trc]
										continue
									if o[0] == "f":
										cal_lines += ['KEYWORD "DEGREE_OF_BLACK_OUTPUT_OFFSET"']
										cal_lines += ['DEGREE_OF_BLACK_OUTPUT_OFFSET "%s"' % o[1:]]
										continue
									if o[0] == "k":
										cal_lines += ['KEYWORD "BLACK_POINT_CORRECTION"']
										cal_lines += ['BLACK_POINT_CORRECTION "%s"' % o[1:]]
										continue
									if o[0] == "B":
										cal_lines += ['KEYWORD "TARGET_BLACK_BRIGHTNESS"']
										cal_lines += ['TARGET_BLACK_BRIGHTNESS "%s"' % o[1:]]
										continue
									if o[0] == "q":
										if o[1] == "l":
											q = "low"
										elif o[1] == "m":
											q = "medium"
										else:
											q = "high"
										cal_lines += ['KEYWORD "QUALITY"']
										cal_lines += ['QUALITY "%s"' % q]
										continue
								if not whitepoint:
									cal_lines += ['KEYWORD "NATIVE_TARGET_WHITE"']
									cal_lines += ['NATIVE_TARGET_WHITE ""']
			if cal_lines:
				if target_filename:
					try:
						f = open(target_filename, "w")
						f.write("\n".join(cal_lines))
						f.close()
					except Exception, exception:
						InfoDialog(self, msg = self.getlstr("cal_extraction_failed") + "\n\n" + unicode(str(exception), enc, "replace"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
						return None
				return cal_lines
		else:
			return None

	def get_options_from_cprt(self, cprt):
		dispcal = unicode(cprt).split(" dispcal ")
		colprof = None
		if len(dispcal) > 1:
			dispcal[1] = dispcal[1].split(" colprof ")
			if len(dispcal[1]) > 1:
				colprof = dispcal[1][1]
			dispcal = dispcal[1][0]
		else:
			dispcal = None
		re_options_dispcal = [
			"v",
			"d\d+(?:,\d+)?",
			"c\d+",
			"m",
			"o",
			"u",
			"q[lmh]",
			"y[cl]",
			"[tT](?:\d+(?:\.\d+)?)?",
			"w\d+(?:\.\d+)?,\d+(?:\.\d+)?",
			"b\d+(?:\.\d+)?",
			"(?:g(?:240|709|l|s)|[gG]\d+(?:\.\d+)?)",
			"f\d+(?:\.\d+)?",
			"a\d+(?:\.\d+)?",
			"k\d+(?:\.\d+)?",
			"A\d+",
			"B\d+(?:\.\d+)?",
			"[pP]\d+(?:\.\d+)?,\d+(?:\.\d+)?,\d+(?:\.\d+)?",
			"p",
			"F\d+(?:\.\d+)?",
			"H"
		]
		re_options_colprof = [
			"q[lmh]",
			"a[lxgsGS]",
			's\s+["\'][^"\']+?["\']',
			'S\s+["\'][^"\']+?["\']',
			"c(?:%s)" % "|".join(self.viewconds),
			"d(?:%s)" % "|".join(self.viewconds)
		]
		options_dispcal = []
		options_colprof = []
		if dispcal:
			options_dispcal = re.findall(" -(" + "|".join(re_options_dispcal) + ")", " " + dispcal)
		if colprof:
			options_colprof = re.findall(" -(" + "|".join(re_options_colprof) + ")", " " + colprof)
		return options_dispcal, options_colprof

	def load_cal_handler(self, event, path = None, update_profile_name = True, silent = False):
		if not self.check_set_argyll_bin():
			return
		if self.getcfg("settings.changed") and not self.settings_confirm_discard():
			return
		if path is None:
			defaultDir, defaultFile = self.get_default_path("last_cal_or_icc_path")
			dlg = wx.FileDialog(self, self.getlstr("dialog.load_cal"), defaultDir = defaultDir, defaultFile = defaultFile, wildcard = self.getlstr("filetype.cal_icc") + "|*.cal;*.icc;*.icm", style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
			dlg.Center(wx.BOTH)
			if dlg.ShowModal() == wx.ID_OK:
				path = dlg.GetPath()
			dlg.Destroy()
		if path:
			if not os.path.exists(path):
				sel = self.calibration_file_ctrl.GetSelection()
				if len(self.recent_cals) > sel and self.recent_cals[sel] == path:
					self.recent_cals.remove(self.recent_cals[sel])
					recent_cals = []
					for recent_cal in self.recent_cals:
						if recent_cal not in self.presets:
							recent_cals += [recent_cal]
					self.setcfg("recent_cals", os.pathsep.join(recent_cals))
					self.calibration_file_ctrl.Delete(sel)
					cal = self.getcfg("calibration.file") or ""
					# the case-sensitive index could fail because of case insensitive file systems
					# e.g. the filename string from the cfg is "C:\Users\Name\AppData\dispcalGUI\storage\MyFile",
					# but the actual filename is "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
					# (maybe because the user manually renamed the file)
					try:
						idx = self.recent_cals.index(cal)
					except ValueError, exception:
						idx = indexi(self.recent_cals, cal)
					self.calibration_file_ctrl.SetSelection(idx)
				InfoDialog(self, msg = self.getlstr("file.missing", path), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
				return

			filename, ext = os.path.splitext(path)
			if ext.lower() in (".icc", ".icm"):
				try:
					profile = ICCP.ICCProfile(path)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					InfoDialog(self, msg = self.getlstr("profile.invalid"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
					return
				if profile.profileClass != "mntr" or profile.colorSpace != "RGB":
					InfoDialog(self, msg = self.getlstr("profile.unsupported", (profile.profileClass, profile.colorSpace)), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
					return
				cal = StringIO(profile.tags.get("CIED", ""))
			else:
				try:
					cal = open(path, "rU")
				except Exception, exception:
					InfoDialog(self, msg = self.getlstr("error.file.open", path), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
					return
			ti3_lines = [line.strip() for line in cal]
			cal.close()
			self.setcfg("last_cal_or_icc_path", path)
			if ext.lower() in (".icc", ".icm"):
				self.setcfg("last_icc_path", path)
				if "cprt" in profile.tags:
					options_dispcal, options_colprof = self.get_options_from_cprt(profile.tags.cprt)
					if options_dispcal or options_colprof:
						if debug: safe_print("options_dispcal:", options_dispcal)
						if debug: safe_print("options_colprof:", options_colprof)
						# parse options
						if options_dispcal:
							# restore defaults
							self.restore_defaults_handler(include = ("calibration", "measure.darken_background", "profile.update", "trc", "whitepoint"))
							self.options_dispcal = ["-" + arg for arg in options_dispcal]
							for o in options_dispcal:
								if o[0] == "d":
									o = o[1:].split(",")
									self.setcfg("display.number", o[0])
									if len(o) > 1:
										self.setcfg("display_lut.number", o[1])
										self.setcfg("display_lut.link", int(o[0] == o[1]))
									continue
								if o[0] == "c":
									self.setcfg("comport.number", o[1:])
									continue
								if o[0] == "m":
									self.setcfg("calibration.interactive_display_adjustment", 0)
									continue
								if o[0] == "o":
									self.setcfg("profile.update", 1)
									continue
								if o[0] == "u":
									self.setcfg("calibration.update", 1)
									continue
								if o[0] == "q":
									self.setcfg("calibration.quality", o[1])
									continue
								if o[0] == "y":
									self.setcfg("measurement_mode", o[1])
									continue
								if o[0] in ("t", "T"):
									self.setcfg("whitepoint.colortemp.locus", o[0])
									if o[1:]:
										self.setcfg("whitepoint.colortemp", o[1:])
									self.setcfg("whitepoint.x", None)
									self.setcfg("whitepoint.y", None)
									continue
								if o[0] == "w":
									o = o[1:].split(",")
									self.setcfg("whitepoint.colortemp", None)
									self.setcfg("whitepoint.x", o[0])
									self.setcfg("whitepoint.y", o[1])
									continue
								if o[0] == "b":
									self.setcfg("calibration.luminance", o[1:])
									continue
								if o[0] in ("g", "G"):
									self.setcfg("trc.type", o[0])
									self.setcfg("trc", o[1:])
									continue
								if o[0] == "f":
									self.setcfg("calibration.black_output_offset", o[1:])
									continue
								if o[0] == "a":
									self.setcfg("calibration.ambient_viewcond_adjust", 1)
									self.setcfg("calibration.ambient_viewcond_adjust.lux", o[1:])
									continue
								if o[0] == "k":
									self.setcfg("calibration.black_point_correction", o[1:])
									continue
								if o[0] == "A":
									self.setcfg("calibration.black_point_rate", o[1:])
									continue
								if o[0] == "B":
									self.setcfg("calibration.black_luminance", o[1:])
									continue
								if o[0] in ("p", "P") and len(o[1:]) >= 5:
									self.setcfg("dimensions.measureframe", o[1:])
									self.setcfg("dimensions.measureframe.unzoomed", o[1:])
									continue
								if o[0] == "p" and len(o[1:]) == 0:
									self.setcfg("projector_mode", 1)
									continue
								if o[0] == "F":
									self.setcfg("measure.darken_background", 1)
									continue
						if options_colprof:
							# restore defaults
							self.restore_defaults_handler(include = ("profile", "gamap_"), exclude = ("profile.update", "profile.name"))
							for o in options_colprof:
								if o[0] == "q":
									self.setcfg("profile.quality", o[1])
									continue
								if o[0] == "a":
									self.setcfg("profile.type", o[1])
									continue
								if o[0] in ("s", "S"):
									o = o.split(None, 1)
									self.setcfg("gamap_profile", o[1][1:-1])
									self.setcfg("gamap_perceptual", 1)
									if o[0] == "S":
										self.setcfg("gamap_saturation", 1)
									continue
								if o[0] == "c":
									self.setcfg("gamap_src_viewcond", o[1:])
									continue
								if o[0] == "d":
									self.setcfg("gamap_out_viewcond", o[1:])
									continue
						# if options_dispcal and options_colprof:
							# self.setcfg("calibration.file", path)
						# else:
							# self.setcfg("calibration.file", None)
						self.setcfg("calibration.file", path)
						if "CTI3" in ti3_lines:
							self.setcfg("testchart.file", path)
						self.update_controls(update_profile_name = update_profile_name)
						self.write_cfg()

						if "vcgt" in profile.tags:
							# load calibration into lut
							self.load_cal(cal = path, silent = True)
							if options_dispcal:
								return
							else:
								msg = self.getlstr("settings_loaded.profile_and_lut")
						elif options_dispcal:
							msg = self.getlstr("settings_loaded.cal_and_profile")
						else:
							msg = self.getlstr("settings_loaded.profile")

						if not silent: InfoDialog(self, msg = msg, ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-information"])
						return
					else:
						sel = self.calibration_file_ctrl.GetSelection()
						if len(self.recent_cals) > sel and self.recent_cals[sel] == path:
							self.recent_cals.remove(self.recent_cals[sel])
							self.calibration_file_ctrl.Delete(sel)
							cal = self.getcfg("calibration.file") or ""
							# the case-sensitive index could fail because of case insensitive file systems
							# e.g. the filename string from the cfg is "C:\Users\Name\AppData\dispcalGUI\storage\MyFile",
							# but the actual filename is "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
							# (maybe because the user manually renamed the file)
							try:
								idx = self.recent_cals.index(cal)
							except ValueError, exception:
								idx = indexi(self.recent_cals, cal)
							self.calibration_file_ctrl.SetSelection(idx)
						if "vcgt" in profile.tags:
							# load calibration into lut
							self.load_cal(cal = path, silent = False)
						if not silent: InfoDialog(self, msg = self.getlstr("no_settings"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
						return
				elif not "CIED" in profile.tags:
					sel = self.calibration_file_ctrl.GetSelection()
					if len(self.recent_cals) > sel and self.recent_cals[sel] == path:
						self.recent_cals.remove(self.recent_cals[sel])
						self.calibration_file_ctrl.Delete(sel)
						cal = self.getcfg("calibration.file") or ""
						# the case-sensitive index could fail because of case insensitive file systems
						# e.g. the filename string from the cfg is "C:\Users\Name\AppData\dispcalGUI\storage\MyFile",
						# but the actual filename is "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
						# (maybe because the user manually renamed the file)
						try:
							idx = self.recent_cals.index(cal)
						except ValueError, exception:
							idx = indexi(self.recent_cals, cal)
						self.calibration_file_ctrl.SetSelection(idx)
					if "vcgt" in profile.tags:
						# load calibration into lut
						self.load_cal(cal = path, silent = False)
					if not silent: InfoDialog(self, msg = self.getlstr("no_settings"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
					return

			self.setcfg("last_cal_path", path)

			# restore defaults
			self.restore_defaults_handler(include = ("calibration", "profile.update", "trc", "whitepoint"))

			self.options_dispcal = []
			settings = []
			for line in ti3_lines:
				line = line.strip().split(" ", 1)
				if len(line) > 1:
					value = line[1][1:-1] # strip quotes
					if line[0] == "DEVICE_CLASS":
						if value != "DISPLAY":
							InfoDialog(self, msg = self.getlstr("calibration.file.invalid"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
							return
					elif line[0] == "DEVICE_TYPE":
						measurement_mode = value.lower()[0]
						if measurement_mode in ("c", "l"):
							self.setcfg("measurement_mode", measurement_mode)
							self.options_dispcal += ["-y" + measurement_mode]
					elif line[0] == "NATIVE_TARGET_WHITE":
						self.setcfg("whitepoint.colortemp", None)
						self.setcfg("whitepoint.x", None)
						self.setcfg("whitepoint.y", None)
						settings += [self.getlstr("whitepoint")]
					elif line[0] == "TARGET_WHITE_XYZ":
						XYZ = value.split()
						i = 0
						try:
							for component in XYZ:
								XYZ[i] = float(component) / 100 # normalize to 0.0 - 1.0
								i += 1
						except ValueError, exception:
							continue
						x, y, Y = XYZ2xyY(XYZ[0], XYZ[1], XYZ[2])
						k = XYZ2CCT(XYZ[0], XYZ[1], XYZ[2])
						if not self.getlstr("whitepoint") in settings:
							self.setcfg("whitepoint.colortemp", None)
							self.setcfg("whitepoint.x", stripzeroes(round(x, 6)))
							self.setcfg("whitepoint.y", stripzeroes(round(y, 6)))
							self.options_dispcal += ["-w%s,%s" % (self.getcfg("whitepoint.x"), self.getcfg("whitepoint.y"))]
							settings += [self.getlstr("whitepoint")]
						self.setcfg("calibration.luminance", stripzeroes(round(Y * 100, 3)))
						self.options_dispcal += ["-b%s" % self.getcfg("calibration.luminance")]
						settings += [self.getlstr("calibration.luminance")]
					elif line[0] == "TARGET_GAMMA":
						self.setcfg("trc", None)
						if value == "L_STAR":
							self.setcfg("trc", "l")
						elif value == "REC709":
							self.setcfg("trc", "709")
						elif value == "SMPTE240M":
							self.setcfg("trc", "240")
						elif value == "sRGB":
							self.setcfg("trc", "s")
						else:
							try:
								value = stripzeroes(value)
								if float(value) < 0:
									self.setcfg("trc.type", "G")
									value = abs(value)
								else:
									self.setcfg("trc.type", "g")
								self.setcfg("trc", value)
							except ValueError:
								continue
						self.options_dispcal += ["-" + self.getcfg("trc.type") + self.getcfg("trc")]
						settings += [self.getlstr("trc")]
					elif line[0] == "DEGREE_OF_BLACK_OUTPUT_OFFSET":
						self.setcfg("calibration.black_output_offset", stripzeroes(value))
						self.options_dispcal += ["-f%s" % self.getcfg("calibration.black_output_offset")]
						settings += [self.getlstr("calibration.black_output_offset")]
					elif line[0] == "BLACK_POINT_CORRECTION":
						self.setcfg("calibration.black_point_correction", stripzeroes(value))
						self.options_dispcal += ["-k%s" % self.getcfg("calibration.black_point_correction")]
						settings += [self.getlstr("calibration.black_point_correction")]
					elif line[0] == "TARGET_BLACK_BRIGHTNESS":
						self.setcfg("calibration.black_luminance", stripzeroes(value))
						self.options_dispcal += ["-B%s" % self.getcfg("calibration.black_luminance")]
						settings += [self.getlstr("calibration.black_luminance")]
					elif line[0] == "QUALITY":
						self.setcfg("calibration.quality", value.lower()[0])
						self.options_dispcal += ["-q" + self.getcfg("calibration.quality")]
						settings += [self.getlstr("calibration.quality")]

			if len(settings) == 0:
				sel = self.calibration_file_ctrl.GetSelection()
				if len(self.recent_cals) > sel and self.recent_cals[sel] == path:
					self.recent_cals.remove(self.recent_cals[sel])
					self.calibration_file_ctrl.Delete(sel)
					cal = self.getcfg("calibration.file") or ""
					# the case-sensitive index could fail because of case insensitive file systems
					# e.g. the filename string from the cfg is "C:\Users\Name\AppData\dispcalGUI\storage\MyFile",
					# but the actual filename is "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
					# (maybe because the user manually renamed the file)
					try:
						idx = self.recent_cals.index(cal)
					except ValueError, exception:
						idx = indexi(self.recent_cals, cal)
					self.calibration_file_ctrl.SetSelection(idx)
				self.write_cfg()
				if not silent: InfoDialog(self, msg = self.getlstr("no_settings"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
			else:
				self.setcfg("calibration.file", path)
				if "CTI3" in ti3_lines:
					self.setcfg("testchart.file", path)
				self.update_controls(update_profile_name = update_profile_name)
				self.write_cfg()

				# load calibration into lut
				self.load_cal(silent = True)
				if not silent: InfoDialog(self, msg = self.getlstr("settings_loaded", ", ".join(settings)), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-information"])

	def delete_calibration_handler(self, event):
		cal = self.getcfg("calibration.file")
		if cal and os.path.exists(cal):
			caldir =os.path.dirname(cal)
			try:
				dircontents = os.listdir(cal)
			except Exception, exception:
				InfoDialog(self, msg = self.getlstr("error.deletion") + "\n\n" + unicode(str(exception), enc, "replace"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
				return
			self.related_files = {}
			for entry in dircontents:
				fn, ext = os.path.splitext(entry)
				if ext.lower() in (".app", cmdfile_ext):
					fn, ext = os.path.splitext(fn)
				if fn == os.path.splitext(os.path.basename(cal))[0]:
					self.related_files[entry] = True
			self.dlg = dlg = ConfirmDialog(self, msg = self.getlstr("dialog.confirm_delete"), ok = self.getlstr("delete"), cancel = self.getlstr("cancel"), bitmap = self.bitmaps["theme/icons/32x32/dialog-warning"])
			if self.related_files:
				dlg.sizer3.Add((0, 8))
				for related_file in self.related_files:
					dlg.sizer3.Add((0, 4))
					chk = wx.CheckBox(dlg, -1, related_file)
					chk.SetValue(self.related_files[related_file])
					dlg.Bind(wx.EVT_CHECKBOX, self.delete_calibration_related_handler, id = chk.GetId())
					dlg.sizer3.Add(chk, flag = wx.ALIGN_LEFT, border = 12)
				dlg.sizer0.SetSizeHints(dlg)
				dlg.sizer0.Layout()
				dlg.Center()
			result = dlg.ShowModal()
			dlg.Destroy()
			if result == wx.ID_OK:
				delete_related_files = []
				if self.related_files:
					for related_file in self.related_files:
						if self.related_files[related_file]:
							delete_related_files += [os.path.join(os.path.dirname(cal), related_file)]
				try:
					if (sys.platform == "darwin" and \
					   len(delete_related_files) + 1 == len(dircontents) and \
					   ".DS_Store" in dircontents) or \
					   len(delete_related_files) == len(dircontents):
						# delete whole folder
						trash([os.path.dirname(cal)])
					else:
						trash(delete_related_files)
				except Exception, exception:
					InfoDialog(self, msg = self.getlstr("error.deletion") + "\n\n" + unicode(str(exception), enc, "replace"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])
				# the case-sensitive index could fail because of case insensitive file systems
				# e.g. the filename string from the cfg is "C:\Users\Name\AppData\dispcalGUI\storage\MyFile",
				# but the actual filename is "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
				# (maybe because the user manually renamed the file)
				try:
					idx = self.recent_cals.index(cal)
				except ValueError, exception:
					idx = indexi(self.recent_cals, cal)
				self.recent_cals.remove(cal)
				self.calibration_file_ctrl.Delete(idx)
				self.setcfg("calibration.file", None)
				self.setcfg("settings.changed", 1)
				recent_cals = []
				for recent_cal in self.recent_cals:
					if recent_cal not in self.presets:
						recent_cals += [recent_cal]
				self.setcfg("recent_cals", os.pathsep.join(recent_cals))
				self.update_controls(False)
				self.load_display_profile_cal()
	
	def delete_calibration_related_handler(self, event):
		chk = self.dlg.FindWindowById(event.GetId())
		self.related_files[chk.GetLabel()] = chk.GetValue()
	
	def aboutdialog_handler(self, event):
		if not hasattr(self, "aboutdialog"):
			self.aboutdialog = AboutDialog(self, -1, self.getlstr("menu.about"), size = (100, 100))
			items = []
			items += [wx.StaticBitmap(self.aboutdialog, -1, self.bitmaps["theme/header-about"])]
			items += [wx.StaticText(self.aboutdialog, -1, "")]
			items += [wx.StaticText(self.aboutdialog, -1, u"%s © Florian Höch" % appname)]
			items += [wx.StaticText(self.aboutdialog, -1, u"%s build %s" % (version, build))]
			items += [wx.lib.hyperlink.HyperLinkCtrl(self.aboutdialog, -1, label="hoech.net/%s" % appname, URL="http://www.hoech.net/%s" % appname)]
			items += [wx.StaticText(self.aboutdialog, -1, "")]
			items += [wx.StaticText(self.aboutdialog, -1, u"Argyll CMS © Graeme Gill")]
			items += [wx.lib.hyperlink.HyperLinkCtrl(self.aboutdialog, -1, label="ArgyllCMS.com", URL="http://www.argyllcms.com")]
			items += [wx.StaticText(self.aboutdialog, -1, "")]
			items += [wx.StaticText(self.aboutdialog, -1, u"%s:" % self.getlstr("translations"))]
			authors = {}
			for lcode in ldict:
				author = ldict[lcode].get("author")
				lang = ldict[lcode].get("language")
				if author and lang:
					if not authors.get(author):
						authors[author] = []
					authors[author] += [lang]
			for author in authors:
				items += [wx.StaticText(self.aboutdialog, -1, "%s - %s" % (", ".join(authors[author]), author))]
			items += [wx.StaticText(self.aboutdialog, -1, "")]
			items += [wx.StaticText(self.aboutdialog, -1, self.getlstr("programming_language_info1"))]
			items += [wx.StaticText(self.aboutdialog, -1, self.getlstr("programming_language_info2"))]
			items += [wx.lib.hyperlink.HyperLinkCtrl(self.aboutdialog, -1, label="python.org", URL="http://www.python.org")]
			items += [wx.lib.hyperlink.HyperLinkCtrl(self.aboutdialog, -1, label="wxPython.org", URL="http://www.wxpython.org")]
			items += [wx.StaticText(self.aboutdialog, -1, "")]
			items += [wx.StaticText(self.aboutdialog, -1, self.getlstr("license_info"))]
			items += [wx.StaticText(self.aboutdialog, -1, "")]
			self.aboutdialog.add_items(items)
			self.aboutdialog.Layout()
			self.aboutdialog.Center()
		self.aboutdialog.Show()

	def infoframe_toggle_handler(self, event):
		self.infoframe.Show(not self.infoframe.IsShownOnScreen())

	def info_save_as_handler(self, event):
		defaultDir, defaultFile = self.get_default_path("last_filedialog_path")
		dlg = wx.FileDialog(self.infoframe, self.getlstr("save_as"), defaultDir = defaultDir, defaultFile = defaultFile, wildcard = self.getlstr("filetype.log") + "|*.log", style = wx.SAVE | wx.OVERWRITE_PROMPT)
		dlg.Center(wx.BOTH)
		result = dlg.ShowModal()
		path = dlg.GetPath()
		dlg.Destroy()
		if result == wx.ID_OK:
			filename, ext = os.path.splitext(path)
			if ext.lower() != ".log":
				path += ".log"
				if os.path.exists(path):
					dlg = ConfirmDialog(self.infoframe, msg = self.getlstr("dialog.confirm_overwrite", (path)), ok = self.getlstr("overwrite"), cancel = self.getlstr("cancel"), bitmap = self.bitmaps["theme/icons/32x32/dialog-warning"])
					result = dlg.ShowModal()
					dlg.Destroy()
					if result != wx.ID_OK:
						return
			self.setcfg("last_filedialog_path", path)
			try:
				file_ = open(path, "w")
				file_.writelines(self.infotext.GetValue())
				file_.close()
			except Exception, exception:
				InfoDialog(self.infoframe, msg = unicode(str(exception), enc, "replace"), ok = self.getlstr("ok"), bitmap = self.bitmaps["theme/icons/32x32/dialog-error"])

	def info_clear_handler(self, event):
		self.infotext.SetValue("")

	def HideAll(self):
		self.stop_timers()
		self.gamapframe.Hide()
		if hasattr(self, "aboutdialog"):
			self.aboutdialog.Hide()
		self.infoframe.Hide()
		if hasattr(self, "tcframe"):
			self.tcframe.Hide()
		self.Hide()

	def ShowAll(self, show = True, start_timers = True):
		self.Show(show)
		if hasattr(self, "tcframe"):
			self.tcframe.Show(self.tcframe.IsShownOnScreen())
		self.infoframe.Show(self.infoframe.IsShownOnScreen())
		if start_timers:
			self.start_timers()

	def OnShow(self, event):
		self.SetFocus()

	def OnClose(self, event = None):
		if sys.platform == "darwin" or debug: self.focus_handler(event)
		if not hasattr(self, "tcframe") or self.tc_close_handler():
			self.write_cfg()
			self.HideAll()
			if hasattr(self, "tempdir") and os.path.exists(self.tempdir) and os.path.isdir(self.tempdir):
				self.wrapup(False)
			if sys.platform not in ("darwin", "win32"):
				try:
					sp.call('echo -e "\\033[0m"', shell = True)
					sp.call('clear', shell = True)
				except Exception, exception:
					safe_print("Info - could not set restore terminal colors:", str(exception))
			globalconfig["app"] = None
			self.Destroy()

	def OnDestroy(self, event):
		event.Skip()

class DisplayCalibrator(wx.App):
	def OnInit(self):
		self.dist_testcharts = []
		self.dist_testchart_names = []
		for filename in resfiles:
			path, ext = get_data_path(os.path.sep.join(filename.split("/"))), os.path.splitext(filename)[1]
			if (not path or not os.path.isfile(path)):
				if ext.lower() != ".json": # ignore missing language files, these are handled later
					handle_error(u"Fatal error: Resource file '%s' not found" % filename, False)
					return False
			elif ext.lower() == ".ti1":
				self.dist_testcharts += [path]
				self.dist_testchart_names += [os.path.basename(path)]
		if sys.platform == "darwin" and not isapp:
			self.SetAppName("Python")
		else:
			self.SetAppName(appname)
		self.frame = DisplayCalibratorGUI(self)
		self.SetTopWindow(self.frame)
		return True

def mac_app_activate(delay = 0, mac_app_name = "Finder"): # only activate if already running
	applescript = [
		'on appIsRunning(appName)',
			'tell application "System Events" to (name of processes) contains appName',
		'end appIsRunning',
		'if appIsRunning("%s") then' % mac_app_name,
			'tell app "%s" to activate' % mac_app_name,
		'end if'
	]
	args = []
	for line in applescript:
		args += ['-e', line]
	try:
		if delay: sleep(delay)
		if appscript is None or mac_app_name == appname:
			# do not use the appscript method to give focus back to dispcalGUI, it does not work reliably. The osascript method works.
			sp.call(['osascript'] + args)
		else:
			mac_app = appscript.app(mac_app_name)
			if mac_app.isrunning():
				appscript.app(mac_app_name).activate()
	except Exception, exception:
		if verbose >= 1: safe_print("Warning - mac_app_activate() failed:", exception)

def mac_terminal_do_script(script = None, do = True):
	applescript = [
		'on appIsRunning(appName)',
			'tell application "System Events" to (name of processes) contains appName',
		'end appIsRunning',
		'if appIsRunning("Terminal") then',
			'tell app "Terminal"',
				'activate',
				'do script ""', # Terminal is already running, open a new window to make sure it is not blocked by another process
			'end tell',
		'else',
			'tell app "Terminal" to activate', # Terminal is not yet running, launch & use first window
		'end if'
	]
	if script:
		applescript += [
			'tell app "Terminal"',
				'do script "%s" in first window' % script.replace('"', '\\"'),
			'end tell'
		]
	args = []
	for line in applescript:
		args += ['-e', line]
	if script and do:
		retcode = -1
		try:
			if appscript is None:
				retcode = sp.call(['osascript'] + args)
			else:
				terminal = appscript.app("Terminal")
				if terminal.isrunning():
					terminal.activate()
					terminal.do_script(script) # Terminal is already running, use a new window to make sure it is not blocked by another process
				else:
					terminal.do_script(script, in_ = appscript.app.windows[1]) # Terminal is not yet running, launch & use first window
				retcode = 0
		except Exception, exception:
			if verbose >= 1: safe_print("Error - mac_terminal_do_script() failed:", exception)
		return retcode
	else:
		return args

def mac_terminal_set_colors(background = "black", cursor = "gray", text = "gray", text_bold = "gray", do = True):
	applescript = [
		'tell app "Terminal"',
		'set background color of first window to "%s"' % background,
		'set cursor color of first window to "%s"' % cursor,
		'set normal text color of first window to "%s"' % text,
		'set bold text color of first window to "%s"' % text_bold,
		'end tell'
	]
	args = []
	for line in applescript:
		args += ['-e', line]
	if do:
		retcode = -1
		try:
			if appscript is None:
				retcode = sp.call(['osascript'] + args)
			else:
				tw = appscript.app("Terminal").windows[1]
				tw.background_color.set(background)
				tw.cursor_color.set(cursor)
				tw.normal_text_color.set(text)
				tw.bold_text_color.set(text_bold)
				retcode = 0
		except Exception, exception:
			if verbose >= 1: safe_print("Info - mac_terminal_set_colors() failed:", exception)
		return retcode
	else:
		return args

def mac_app_sendkeys(delay = 0, mac_app_name = "Finder", keys = ""):
	mac_app_activate(delay, mac_app_name)
	try:
		if appscript is None:
			sp.call([
				'osascript',
				'-e', 'tell application "System Events"',
				'-e', 'keystroke "%s"' % keys,
				'-e', 'end tell'
			])
		else:
			appscript.app('System Events').keystroke(keys)
	except Exception, exception:
		if verbose >= 1: safe_print("Error - mac_app_sendkeys() failed:", exception)

def wsh_sendkeys(delay = 0, windowname = "", keys = ""):
	try:
		if delay: sleep(delay)
		# hwnd = win32gui.FindWindowEx(0, 0, 0, windowname)
		# win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)
		SendKeys(keys, with_spaces = True, with_tabs = True, with_newlines = True, turn_off_numlock = False)
	except Exception, exception:
		if verbose >= 1: safe_print("Error - wsh_sendkeys() failed:", exception)

def xte_sendkeys(delay = 0, windowname = "", keys = ""):
	try:
		if delay: sleep(delay)
		sp.call(["xte", "key %s" % keys], stdin = sp.PIPE, stdout = sp.PIPE, stderr = sp.PIPE)
	except Exception, exception:
		if verbose >= 1: safe_print("Error - xte_sendkeys() failed:", exception)

def main():
	try:
		if debug: safe_print("Entering main()...")
		setup_logging()
		if verbose >= 1: safe_print(appname + runtype, version, "build", build)
		# read pre-v0.2.2b configuration if present
		oldcfg = os.path.join(os.path.expanduser("~"), "Library", "Preferences", appname + " Preferences") if sys.platform == "darwin" else os.path.join(os.path.expanduser("~"), "." + appname)
		if not os.path.exists(confighome):
			try:
				os.makedirs(confighome)
			except Exception, exception:
				handle_error("Warning - could not create configuration directory '%s'" % confighome)
		if os.path.exists(confighome) and not os.path.exists(os.path.join(confighome, appname + ".ini")):
			try:
				if os.path.isfile(oldcfg):
					oldcfg_file = open(oldcfg, "rb")
					oldcfg_contents = oldcfg_file.read()
					oldcfg_file.close()
					cfg_file = open(os.path.join(confighome, appname + ".ini"), "wb")
					cfg_file.write("[Default]\n" + oldcfg_contents)
					cfg_file.close()
				elif sys.platform == "win32":
					key = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, "Software\\" + appname)
					numsubkeys, numvalues, mtime = _winreg.QueryInfoKey(key)
					cfg_file = open(os.path.join(confighome, appname + ".ini"), "wb")
					cfg_file.write("[Default]\n")
					for i in range(numvalues):
						name, value, type_ = _winreg.EnumValue(key, i)
						if type_ == 1: cfg_file.write((u"%s = %s\n" % (name, value)).encode("UTF-8"))
					cfg_file.close()
			except Exception, exception:
				safe_print("Warning - could not process old configuration:", str(exception))
		# create main data storage dir
		if not os.path.exists(storage):
			try:
				os.makedirs(storage)
			except Exception, exception:
				handle_error("Warning - could not create storage directory '%s'" % storage)
		if sys.platform not in ("darwin", "win32"):
			# Linux: try and fix v0.2.1b calibration loader, because calibrationloader.sh is no longer present in v0.2.2b+
			desktopfile_name = appname + "-Calibration-Loader-Display-"
			if os.path.exists(autostart_home):
				try:
					autostarts = os.listdir(autostart_home)
				except Exception, exception:
					safe_print("Warning - directory '%s' listing failed: %s" % (autostarts, str(exception)))
				for filename in autostarts:
					if filename.startswith(desktopfile_name):
						try:
							desktopfile_path = os.path.join(autostart_home, filename)
							cfg = ConfigParser.SafeConfigParser()
							cfg.optionxform = str
							cfg.read([desktopfile_path])
							exec_ = cfg.get("Desktop Entry", "Exec")
							if exec_.find("calibrationloader.sh") > -1:
								cfg.set("Desktop Entry", "Exec", re.sub('"[^"]*calibrationloader.sh"\s*', '', exec_, 1))
								cfgstorage = StringIO()
								cfg.write(cfgstorage)
								desktopfile = open(desktopfile_path, "w")
								cfgstorage.seek(0)
								desktopfile.write(cfgstorage.read().replace(" = ", "="))
								desktopfile.close()
						except Exception, exception:
							safe_print("Warning - could not process old calibration loader:", str(exception))
		# make sure we run inside a terminal
		if not sys.stdin.isatty() or not sys.stdout.isatty() or not sys.stderr.isatty() or "-oc" in sys.argv[1:]:
			terminals_opts = {
				"Terminal": "-x",
				"gnome-terminal": "-e",
				"konsole": "-e",
				"xterm": "-e"
			}
			terminals = terminals_opts.keys()
			if isapp:
				me = os.path.join(exedir, pyname)
				cmd = '"%s"' % me
				cwd = None
			elif isexe:
				me = sys.executable
				cmd = '"%s"' % me
				cwd = None
			else:
				me = pypath
				exe = sys.executable
				if os.path.basename(exe) == "pythonw" + exe_ext:
					exe = os.path.join(os.path.dirname(exe), "python" + exe_ext)
				cmd = '"%s" "%s"' % (exe, pypath)
				cwd = pydir
			safe_print("Re-launching instance in terminal")
			if sys.platform == "win32":
				cmd = 'start "%s" /WAIT %s' % (appname, cmd)
				if debug: safe_print(cmd)
				retcode = sp.call(cmd.encode(fs_enc), shell = True, cwd = None if cwd is None else cwd.encode(fs_enc))
			elif sys.platform == "darwin":
				if debug: safe_print(cmd)
				retcode = mac_terminal_do_script(cmd)
			else:
				stdout = tempfile.SpooledTemporaryFile()
				retcode = None
				for terminal in terminals:
					if which(terminal):
						if debug: safe_print('%s %s %s' % (terminal, terminals_opts[terminal], cmd))
						stdout.write('%s %s %s' % (terminal, terminals_opts[terminal], cmd))
						retcode = sp.call([terminal, terminals_opts[terminal]] + cmd.encode(fs_enc).strip('"').split('" "'), stdout = stdout, stderr = sp.STDOUT, cwd = None if cwd is None else cwd.encode(fs_enc))
						stdout.write('\n\n')
						break
				stdout.seek(0)
			if retcode != 0:
				globalconfig["app"] = app = wx.App(redirect = False)
				if sys.platform == "win32":
					msg = u'Even though %s is a GUI application, it needs to be run from a command prompt. An attempt to automatically launch the command prompt failed.' % me
				elif sys.platform == "darwin":
					msg = u'Even though %s is a GUI application, it needs to be run from Terminal. An attempt to automatically launch Terminal failed.' % me
				else:
					if retcode == None:
						msg = u'Even though %s is a GUI application, it needs to be run from a terminal. An attempt to automatically launch a terminal failed, because none of those known seem to be installed (%s).' % (me, ", ".join(terminals))
					else:
						msg = u'Even though %s is a GUI application, it needs to be run from a terminal. An attempt to automatically launch a terminal failed:\n\n%s' % (me, unicode(stdout.read(), enc, "replace"))
				handle_error(msg)
		else:
			init_languages()
			globalconfig["app"] = app = DisplayCalibrator(redirect = False) # DON'T redirect stdin/stdout
			app.MainLoop()
	except Exception, exception:
		handle_error("Fatal error: " + traceback.format_exc())
	try:
		logger = logging.getLogger()
		for handler in logger.handlers:
			logger.removeHandler(handler)
		logging.shutdown()
	except Exception, exception:
		pass

if __name__ == "__main__":
	main()
