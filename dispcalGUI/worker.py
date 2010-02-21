#!/usr/bin/env python
# -*- coding: utf-8 -*-

import getpass
import os
import re
import shutil
import sys
import textwrap
import traceback
from time import sleep, strftime

if sys.platform == "darwin":
	try:
		import appscript
	except ImportError: # we can fall back to osascript shell command
		appscript = None
	from util_mac import (mac_app_activate, mac_terminal_do_script,
						  mac_terminal_set_colors)
elif sys.platform == "win32":
	try:
		from SendKeys import SendKeys
	except ImportError:
		import win32com.client
		SendKeys = None
	import pywintypes
	import win32api
from wxaddons import wx
import wx.lib.delayedresult as delayedresult

import ICCProfile as ICCP
import config
import localization as lang
import subprocess26 as sp
import tempfile26 as tempfile
from argyll_cgats import extract_fix_copy_cal, ti3_to_ti1
from argyll_instruments import instruments, remove_vendor_names
from argyll_names import (names as argyll_names, altnames as argyll_altnames, 
						  viewconds)
from config import (script_ext, defaults, enc, exe_ext, fs_enc, getcfg, 
					geticon, get_data_path, get_verified_path, setcfg, writecfg)
from debughelpers import handle_error
from log import log, safe_print
from meta import name as appname, version
from options import debug, test, verbose
from thread import start_new_thread
from util_io import Files, StringIOu as StringIO, Tea
from util_os import getenvu, quote_args, which
from util_str import asciize
from wxwindows import ConfirmDialog, InfoDialog

if sys.platform == "win32" and SendKeys is None:
	wsh_shell = win32com.client.Dispatch("WScript.Shell")
	def SendKeys(keys, pause=0.05, with_spaces=False, with_tabs=False, with_newlines=False, 
				turn_off_numlock=True):
		wsh_shell.SendKeys(keys)

DD_ATTACHED_TO_DESKTOP = 0x01
DD_MULTI_DRIVER        = 0x02
DD_PRIMARY_DEVICE      = 0x04
DD_MIRRORING_DRIVER    = 0x08
DD_VGA_COMPATIBLE      = 0x10
DD_REMOVABLE           = 0x20
DD_DISCONNECT          = 0x2000000  # WINVER >= 5
DD_REMOTE              = 0x4000000  # WINVER >= 5
DD_MODESPRUNED         = 0x8000000  # WINVER >= 5


def check_argyll_bin(paths=None):
	""" Check if the Argyll binaries can be found. """
	prev_dir = None
	for name in argyll_names:
		exe = get_argyll_util(name, paths)
		if not exe:
			return False
		cur_dir = os.path.dirname(exe)
		if prev_dir:
			if cur_dir != prev_dir:
				if verbose: safe_print("Warning - the Argyll executables are "
									   "scattered. They should be in the same "
									   "directory.")
				return False
		else:
			prev_dir = cur_dir
	if verbose >= 3: safe_print("Argyll binary directory:", cur_dir)
	if debug: safe_print("[D] check_argyll_bin OK")
	if debug >= 2:
		if not paths:
			paths = getenvu("PATH", os.defpath).split(os.pathsep)
			argyll_dir = (getcfg("argyll.dir") or "").rstrip(os.path.sep)
			if argyll_dir:
				if argyll_dir in paths:
					paths.remove(argyll_dir)
				paths = [argyll_dir] + paths
		safe_print("[D] Searchpath:\n  ", "\n  ".join(paths))
	return True


def check_create_dir(path, parent=None):
	"""
	Try to create a directory and show an error message on failure.
	"""
	if not os.path.exists(path):
		try:
			os.makedirs(path)
		except Exception, exception:
			InfoDialog(parent, pos=(-1, 100), 
					   msg=lang.getstr("error.dir_creation", path) + "\n\n" + 
						   unicode(str(exception), enc, "replace"), 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-error"))
			return False
	if not os.path.isdir(path):
		InfoDialog(parent, pos=(-1, 100), msg=lang.getstr("error.dir_notdir", 
														  path), 
				   ok=lang.getstr("ok"), 
				   bitmap=geticon(32, "dialog-error"))
		return False
	return True


def check_cal_isfile(cal=None, missing_msg=None, notfile_msg=None, 
					 parent=None, silent=False):
	"""
	Check if a calibration file exists and show an error message if not.
	"""
	if not silent:
		if not missing_msg:
			missing_msg = lang.getstr("error.calibration.file_missing", cal)
		if not notfile_msg:
			notfile_msg = lang.getstr("error.calibration.file_notfile", cal)
	return check_file_isfile(cal, missing_msg, notfile_msg, parent, silent)


def check_profile_isfile(profile_path=None, missing_msg=None, 
						 notfile_msg=None, parent=None, silent=False):
	"""
	Check if a profile exists and show an error message if not.
	"""
	if not silent:
		if not missing_msg:
			missing_msg = lang.getstr("error.profile.file_missing", 
									  profile_path)
		if not notfile_msg:
			notfile_msg = lang.getstr("error.profile.file_notfile", 
									  profile_path)
	return check_file_isfile(profile_path, missing_msg, notfile_msg, parent, 
							 silent)


def check_file_isfile(filename, missing_msg=None, notfile_msg=None, 
					  parent=None, silent=False):
	"""
	Check if a file exists and show an error message if not.
	"""
	if not os.path.exists(filename):
		if not silent:
			if not missing_msg:
				missing_msg = lang.getstr("file.missing", filename)
			InfoDialog(parent, pos=(-1, 100), msg=missing_msg, 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-error"))
		return False
	if not os.path.isfile(filename):
		if not silent:
			if not notfile_msg:
				notfile_msg = lang.getstr("file.notfile", filename)
			InfoDialog(parent, pos=(-1, 100), msg=notfile_msg, 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-error"))
		return False
	return True


def check_set_argyll_bin():
	"""
	Check if Argyll binaries can be found, otherwise let the user choose.
	"""
	if check_argyll_bin():
		return True
	else:
		return set_argyll_bin()


def get_argyll_util(name, paths=None):
	""" Find a single Argyll utility. Return the full path. """
	if not paths:
		paths = getenvu("PATH", os.defpath).split(os.pathsep)
		argyll_dir = (getcfg("argyll.dir") or "").rstrip(os.path.sep)
		if argyll_dir:
			if argyll_dir in paths:
				paths.remove(argyll_dir)
			paths = [argyll_dir] + paths
	elif verbose >= 4:
		safe_print("Info: Searching for", name, "in", os.pathsep.join(paths))
	exe = None
	for path in paths:
		for altname in argyll_altnames[name]:
			exe = which(altname + exe_ext, [path])
			if exe:
				break
		if exe:
			break
	if verbose >= 4:
		if exe:
			safe_print("Info:", name, "=", exe)
		else:
			safe_print("Info:", "|".join(argyll_altnames[name]), 
					   "not found in", os.pathsep.join(paths))
	return exe


def get_argyll_utilname(name, paths=None):
	""" Find a single Argyll utility. Return the basename. """
	exe = get_argyll_util(name, paths)
	if exe:
		exe = os.path.basename(os.path.splitext(exe)[0])
	return exe


def get_argyll_version(name, silent=False):
	"""
	Determine version of a certain Argyll utility.
	
	"""
	argyll_version = [0, 0, 0]
	if (silent and check_argyll_bin()) or (not silent and 
										   check_set_argyll_bin()):
		cmd = get_argyll_util(get_argyll_utilname(name))
		p = sp.Popen([cmd], stdin=None, stdout=sp.PIPE, stderr=sp.STDOUT)
		for i, line in enumerate((p.communicate()[0] or "").splitlines()):
			if isinstance(line, basestring):
				line = line.strip()
				if i == 0 and "version" in line.lower():
					argyll_version_string = line[line.lower().find("version")+8:]
					argyll_version = re.findall("(\d+|[^.\d]+)", 
												argyll_version_string)
					for i in range(len(argyll_version)):
						try:
							argyll_version[i] = int(argyll_version[i])
						except ValueError:
							argyll_version[i] = argyll_version[i]
					break
	return argyll_version


def get_options_from_cprt(cprt):
	"""
	Extract options used for dispcal and colprof from profile copyright.
	"""
	if not isinstance(cprt, unicode):
		if isinstance(cprt, (ICCP.TextDescriptionType, 
							 ICCP.MultiLocalizedUnicodeType)):
			cprt = unicode(cprt)
		else:
			cprt = unicode(cprt, fs_enc, "replace")
	dispcal = cprt.split(" dispcal ")
	colprof = None
	if len(dispcal) > 1:
		dispcal[1] = dispcal[1].split(" colprof ")
		if len(dispcal[1]) > 1:
			colprof = dispcal[1][1]
		dispcal = dispcal[1][0]
	else:
		dispcal = None
		colprof = cprt.split(" colprof ")
		if len(colprof) > 1:
			colprof = colprof[1]
		else:
			colprof = None
	re_options_dispcal = [
		"v",
		"d\d+(?:,\d+)?",
		"c\d+",
		"m",
		"o",
		"u",
		"q[vlmh]",
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
		"H",
		"V"  # Argyll >= 1.1.0_RC3 i1pro adaptive mode
	]
	re_options_colprof = [
		"q[lmh]",
		"a[lxXgsGS]",
		's\s+["\'][^"\']+?["\']',
		'S\s+["\'][^"\']+?["\']',
		"c(?:%s)" % "|".join(viewconds),
		"d(?:%s)" % "|".join(viewconds)
	]
	options_dispcal = []
	options_colprof = []
	if dispcal:
		options_dispcal = re.findall(" -(" + "|".join(re_options_dispcal) + 
									 ")", " " + dispcal)
	if colprof:
		options_colprof = re.findall(" -(" + "|".join(re_options_colprof) + 
									 ")", " " + colprof)
	return options_dispcal, options_colprof


def make_argyll_compatible_path(path):
	"""
	Make the path compatible with the Argyll utilities.
	
	This is currently only effective under Windows to make sure that any 
	unicode 'division' slashes in the profile name are replaced with 
	underscores, and under Linux if the encoding is not UTF-8 everything is 
	forced to ASCII to prevent problems when installing profiles.
	
	"""
	if sys.platform not in ("darwin", "win32") and \
	   fs_enc.upper() not in ("UTF8", "UTF-8"):
		make_compat_enc = "ASCII"
	else:
		make_compat_enc = fs_enc
	parts = path.split(os.path.sep)
	for i in range(len(parts)):
		parts[i] = unicode(parts[i].encode(make_compat_enc, "asciize"), 
						   make_compat_enc).replace("/", "_")
	return os.path.sep.join(parts)


def printcmdline(cmd, args=None, fn=None, cwd=None):
	"""
	Pretty-print a command line.
	"""
	if args is None:
		args = []
	if cwd is None:
		cwd = os.getcwdu()
	safe_print("  " + cmd, fn=fn)
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
		if not item.startswith("-") and len(lines) and i < len(args) - 1:
			lines[-1] += "\n      " + item
		else:
			lines.append(item)
		i += 1
	for line in lines:
		safe_print(textwrap.fill(line, 80, expand_tabs = False, 
				   replace_whitespace = False, initial_indent = "    ", 
				   subsequent_indent = "      "), fn = fn)


def sendkeys(delay=0, target="", keys=""):
	""" Send key(s) to optional target after delay. """
	if sys.platform == "darwin":
		mac_app_activate(delay, target)
		try:
			if appscript is None:
				p = sp.Popen([
					'osascript',
					'-e', 'tell application "System Events"',
					'-e', 'keystroke "%s"' % keys,
					'-e', 'end tell'
				], stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)
				p.communicate()
			else:
				appscript.app('System Events').keystroke(keys)
		except Exception, exception:
			if verbose >= 1:
				safe_print("Error - sendkeys() failed:", exception)
	elif sys.platform == "win32":
		try:
			if delay: sleep(delay)
			## hwnd = win32gui.FindWindowEx(0, 0, 0, target)
			## win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)
			SendKeys(keys, with_spaces=True, with_tabs=True, 
					 with_newlines=True, turn_off_numlock=False)
		except Exception, exception:
			if verbose >= 1:
				safe_print("Error - sendkeys() failed:", exception)
	else:
		try:
			if delay: sleep(delay)
			if verbose >= 2:
				safe_print('Sending key sequence using xte: "%s"' % keys)
			p = sp.Popen(["xte", "key %s" % keys], stdin=sp.PIPE, 
							  stdout=sp.PIPE, stderr=sp.PIPE)
			stdout, stderr = p.communicate()
			if verbose >= 2:
				safe_print(stdout)
			if p.returncode != 0:
				if verbose >= 2:
					safe_print(p.returncode)
		except Exception, exception:
			if verbose >= 1:
				safe_print("Error - sendkeys() failed:", exception)


def set_argyll_bin(parent=None):
	if parent and not parent.IsShownOnScreen():
		parent = None # do not center on parent if not visible
	defaultPath = os.path.sep.join(get_verified_path("argyll.dir"))
	dlg = wx.DirDialog(parent, lang.getstr("dialog.set_argyll_bin"), 
					   defaultPath=defaultPath, style=wx.DD_DIR_MUST_EXIST)
	dlg.Center(wx.BOTH)
	result = False
	while not result:
		result = dlg.ShowModal() == wx.ID_OK
		if result:
			path = dlg.GetPath().rstrip(os.path.sep)
			result = check_argyll_bin([path])
			if result:
				if verbose >= 3:
					safe_print("Setting Argyll binary directory:", path)
				setcfg("argyll.dir", path)
				writecfg()
				break
			else:
				InfoDialog(parent, msg=path + "\n\n" + 
									   lang.getstr("argyll.dir.invalid", 
												   (exe_ext, ) * 6), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
		else:
			break
	dlg.Destroy()
	return result


class Worker():

	def __init__(self, owner=None):
		"""
		Create and return a new worker instance.
		"""
		self.owner = owner # owner should be a wxFrame or similar
		self.clear_argyll_info()
		self.clear_cmd_output()
		self.dispcal_create_fast_matrix_shaper = False
		self.dispread_after_dispcal = False
		self.options_colprof = []
		self.options_dispcal = []
		self.options_dispread = []
		self.options_targen = []
		self.tempdir = None
	
	def add_measurement_features(self, args):
		measurement_mode = getcfg("measurement_mode")
		instrument_features = self.get_instrument_features()
		if measurement_mode:
			if not instrument_features.get("spectral"):
				# Always specify -y for colorimeters (won't be read from .cal 
				# when updating)
				args += ["-y" + measurement_mode[0]]
		if getcfg("measurement_mode.projector") and \
		   instrument_features.get("projector_mode") and \
		   self.argyll_version >= [1, 1, 0]:
			# Projector mode, Argyll >= 1.1.0 Beta
			args += ["-p"]
		if getcfg("measurement_mode.adaptive") and \
		   instrument_features.get("adaptive_mode") and \
		   (self.argyll_version[0:3] > [1, 1, 0] or (
			self.argyll_version[0:3] == [1, 1, 0] and 
			not "Beta" in self.argyll_version_string and 
			not "RC1" in self.argyll_version_string and 
			not "RC2" in self.argyll_version_string)):
			# Adaptive mode, Argyll >= 1.1.0 RC3
			args += ["-V"]
		args += [("-p" if self.argyll_version <= [1, 0, 4] else "-P") + 
				 getcfg("dimensions.measureframe")]
		if getcfg("measure.darken_background"):
			args += ["-F"]
		if getcfg("measurement_mode.highres") and \
		   instrument_features.get("highres_mode"):
			args += ["-H"]
	
	def clear_argyll_info(self):
		"""
		Clear Argyll CMS version, detected displays and instruments.
		"""
		self.argyll_bin_dir = None
		self.argyll_version = [0, 0, 0]
		self.argyll_version_string = ""
		self.displays = []
		self.instruments = []
		self.lut_access = []

	def clear_cmd_output(self):
		"""
		Clear any output from the last run command.
		"""
		self.pwd = None
		self.retcode = -1
		self.output = []
		self.errors = []

	def create_tempdir(self):
		""" Create a temporary working directory and return its path. """
		if not self.tempdir or not os.path.isdir(self.tempdir):
			# we create the tempdir once each calibrating/profiling run 
			# (deleted by 'wrapup' after each run)
			try:
				self.tempdir = tempfile.mkdtemp(prefix=appname + u"-")
			except Exception, exception:
				self.tempdir = None
				handle_error("Error - couldn't create temporary directory: " + 
							 str(exception), parent=self.owner)
		return self.tempdir

	def enumerate_displays_and_ports(self, silent=False):
		"""
		Run Argyll dispcal to enumerate the available displays and ports.
		
		Also sets Argyll version number, availability of certain options
		like black point rate, and checks LUT access for each display.
		
		"""
		displays = list(self.displays)
		lut_access = list(self.lut_access)
		self.clear_argyll_info()
		if (silent and check_argyll_bin()) or (not silent and 
											   check_set_argyll_bin()):
			if verbose >= 1 and not silent:
				safe_print(lang.getstr("enumerating_displays_and_comports"))
			cmd = get_argyll_util("dispcal")
			self.argyll_bin_dir = os.path.dirname(cmd)
			self.exec_cmd(cmd, [], capture_output=True, 
						  skip_scripts=True, silent=True, log_output=False)
			arg = None
			defaults["calibration.black_point_rate.enabled"] = 0
			n = -1
			if sys.platform == "win32":
				monitors = []
				for monitor in win32api.EnumDisplayMonitors(None, None):
					monitors.append(win32api.GetMonitorInfo(monitor[0]))
			for line in self.output:
				if isinstance(line, unicode):
					n += 1
					line = line.strip()
					if n == 0 and "version" in line.lower():
						argyll_version = line[line.lower().find("version")+8:]
						self.argyll_version_string = argyll_version
						if verbose >= 3:
							safe_print("Argyll CMS version", argyll_version)
						argyll_version = re.findall("(\d+|[^.\d]+)", 
													argyll_version)
						for i in range(len(argyll_version)):
							try:
								argyll_version[i] = int(argyll_version[i])
							except ValueError:
								argyll_version[i] = argyll_version[i]
						self.argyll_version = argyll_version
						continue
					line = line.split(None, 1)
					if len(line) and line[0][0] == "-":
						arg = line[0]
						if arg == "-A":
							# Rate of blending from neutral to black point.
							defaults["calibration.black_point_rate.enabled"] = 1
					elif len(line) > 1 and line[1][0] == "=":
						value = line[1].strip(" ='")
						if arg == "-d":
							match = re.findall("(.+?),? at (-?\d+), (-?\d+), "
											   "width (\d+), height (\d+)", 
											   value)
							if len(match):
								if sys.platform == "win32":
									i = 0
									device = None
									while True:
										try:
											## The ordering will work as long
											## as Argyll continues using
											## EnumDisplayMonitors
											device = win32api.EnumDisplayDevices(
												monitors[len(self.displays)]["Device"], i)
										except pywintypes.error:
											break
										else:
											if device.StateFlags & \
											   DD_ATTACHED_TO_DESKTOP:
												break
										i += 1
									if device:
										match[0] = (device.DeviceString.decode(fs_enc, "replace"),) + match[0][1:]
								display = "%s @ %s, %s, %sx%s" % match[0]
								if " ".join(value.split()[-2:]) == \
								   "(Primary Display)":
									display += u" [PRIMARY]"
								self.displays.append(display)
						elif arg == "-c":
							value = value.split(None, 1)
							if len(value) > 1:
								value = value[1].strip("()")
							else:
								value = value[0]
							value = remove_vendor_names(value)
							self.instruments.append(value)
			if test:
				inames = instruments.keys()
				inames.sort()
				for iname in inames:
					if not iname in self.instruments:
						self.instruments.append(iname)
			if verbose >= 1 and not silent: safe_print(lang.getstr("success"))
			if displays != self.displays:
				# Check lut access
				i = 0
				dispwin = get_argyll_util("dispwin")
				for disp in self.displays:
					if verbose >= 1 and not silent:
						safe_print(lang.getstr("checking_lut_access", (i + 1)))
					# Load test.cal
					self.exec_cmd(dispwin, ["-d%s" % (i +1), "-c", 
											get_data_path("test.cal")], 
								  capture_output=True, skip_scripts=True, 
								  silent=True)
					# Check if LUT == test.cal
					self.exec_cmd(dispwin, ["-d%s" % (i +1), "-V", 
											get_data_path("test.cal")], 
								  capture_output=True, skip_scripts=True, 
								  silent=True)
					retcode = -1
					for line in self.output:
						if line.find("IS loaded") >= 0:
							retcode = 0
							break
					# Reset LUT & load profile cal (if any)
					self.exec_cmd(dispwin, ["-d%s" % (i +1), "-c", "-L"], 
								  capture_output=True, skip_scripts=True, 
								  silent=True)
					self.lut_access += [retcode == 0]
					if verbose >= 1 and not silent:
						if retcode == 0:
							safe_print(lang.getstr("success"))
						else:
							safe_print(lang.getstr("failure"))
					i += 1
			else:
				self.lut_access = lut_access

	def exec_cmd(self, cmd, args=[], capture_output=False, 
				 display_output=False, low_contrast=True, skip_scripts=False, 
				 silent=False, parent=None, asroot=False, log_output=True):
		"""
		Execute a command.
		
		cmd is the full path of the command.
		args are the arguments, if any.
		capture_output (if True) swallows any output from the command and
		sets the 'output' and 'errors' properties of the Worker instance.
		display_output shows any captured output if the Worker instance's 
		'owner' window has a 'LogWindow' child called 'infoframe'.
		low_contrast (if True) sets low contrast shell colors while the 
		command is run.
		skip_scripts (if True) skips the creation of shell scripts that allow 
		re-running the command which are created by default.
		silent (if True) skips most output and also most error dialogs 
		(except unexpected failures)
		parent sets the parent window for any message dialogs.
		asroot (if True) on Linux runs the command using sudo.
		log_output (if True) logs any output if capture_output is also set.
		"""
		if parent is None:
			parent = self.owner
		## if capture_output:
			## fn = self.infoframe.Log
		## else:
		fn = None
		self.clear_cmd_output()
		if None in [cmd, args]:
			if verbose >= 1 and not capture_output:
				safe_print(lang.getstr("aborted"), fn=fn)
			return False
		cmdname = os.path.splitext(os.path.basename(cmd))[0]
		if args and args[-1].find(os.path.sep) > -1:
			working_dir = os.path.dirname(args[-1])
			working_basename = os.path.basename(args[-1])
			if cmdname == get_argyll_utilname("dispwin"):
				# Last arg is without extension, only for dispwin we need to 
				# strip it
				working_basename = os.path.splitext(working_basename)[0] 
		else:
			working_dir = None
		if not capture_output and low_contrast:
			# Set low contrast colors (gray on black) so it doesn't interfere 
			# with measurements
			try:
				if sys.platform == "win32":
					sp.call("color 08", shell=True)
				elif sys.platform == "darwin":
					mac_terminal_set_colors()
				else:
					print "\x1b[2;37m"
			except Exception, exception:
				safe_print("Info - could not set terminal colors:", 
						   str(exception))
		if verbose >= 1:
			if not silent or verbose >= 3:
				safe_print("", fn=fn)
				if working_dir:
					safe_print(lang.getstr("working_dir"), fn=fn)
					indent = "  "
					for name in working_dir.split(os.path.sep):
						safe_print(textwrap.fill(name + os.path.sep, 80, 
												 expand_tabs=False, 
												 replace_whitespace=False, 
												 initial_indent=indent, 
												 subsequent_indent=indent), 
								   fn=fn)
						indent += " "
					safe_print("", fn=fn)
				safe_print(lang.getstr("commandline"), fn=fn)
				printcmdline(cmd if verbose >= 2 else os.path.basename(cmd), 
							 args, fn=fn, cwd=working_dir)
				safe_print("", fn=fn)
		cmdline = [cmd] + args
		for i in range(len(cmdline)):
			item = cmdline[i]
			if i > 0 and (item.find(os.path.sep) > -1 and 
						  os.path.dirname(item) == working_dir):
				# Strip the path from all items in the working dir
				if sys.platform == "win32" and \
				   re.search("[^\x00-\x7f]", item) and os.path.exists(item):
					# Avoid problems with encoding
					item = win32api.GetShortPathName(item) 
				cmdline[i] = os.path.basename(item)
		sudo = None
		if cmdname == get_argyll_utilname("dispwin") and ("-Sl" in args or 
														  "-Sn" in args):
			asroot = True
		if asroot and ((sys.platform != "win32" and os.geteuid() != 0) or 
					   (sys.platform == "win32" and 
					    sys.getwindowsversion() >= (6, ))):
			if sys.platform == "win32":
				# Vista and later
				pass
			else:
				sudo = which("sudo")
		if sudo:
			try:
				pwdproc = sp.Popen('echo "%s"' % (self.pwd or ""), shell=True, 
								   stdin=sp.PIPE, stdout=sp.PIPE, 
								   stderr=sp.STDOUT)
				sudoproc = sp.Popen([sudo, "-S", "echo", "OK"], 
									stdin=pwdproc.stdout, stdout=sp.PIPE, 
									stderr=sp.PIPE)
				stdout, stderr = sudoproc.communicate()
				if not "OK" in stdout:
					# ask for password
					dlg = ConfirmDialog(
						parent, msg=lang.getstr("dialog.enter_password"), 
						ok=lang.getstr("ok"), cancel=lang.getstr("cancel"), 
						bitmap=geticon(32, "dialog-question"))
					dlg.pwd_txt_ctrl = wx.TextCtrl(dlg, -1, "", 
												   size=(320, -1), 
												   style=wx.TE_PASSWORD)
					dlg.sizer3.Add(dlg.pwd_txt_ctrl, 1, 
								   flag=wx.TOP | wx.ALIGN_LEFT, border=12)
					dlg.ok.SetDefault()
					dlg.pwd_txt_ctrl.SetFocus()
					dlg.sizer0.SetSizeHints(dlg)
					dlg.sizer0.Layout()
					while True:
						result = dlg.ShowModal()
						pwd = dlg.pwd_txt_ctrl.GetValue()
						if result != wx.ID_OK:
							safe_print(lang.getstr("aborted"), fn=fn)
							return None
						pwdproc = sp.Popen('echo "%s"' % pwd, shell=True, 
										   stdin=sp.PIPE, stdout=sp.PIPE, 
										   stderr=sp.STDOUT)
						sudoproc = sp.Popen([sudo, "-S", "echo", "OK"], 
											stdin=pwdproc.stdout, 
											stdout=sp.PIPE, stderr=sp.PIPE)
						stdout, stderr = sudoproc.communicate()
						if "OK" in stdout:
							self.pwd = pwd
							break
						else:
							errstr = unicode(stderr, enc, "replace")
							##if not silent:
								##safe_print(errstr)
							##else:
								##log(errstr)
							dlg.message.SetLabel(
								lang.getstr("auth.failed") + "\n" + 
								##errstr +
								lang.getstr("dialog.enter_password"))
							dlg.sizer0.SetSizeHints(dlg)
							dlg.sizer0.Layout()
					dlg.Destroy()
				cmdline.insert(0, sudo)
				cmdline.insert(1, "-S")
			except Exception, exception:
				safe_print("Warning - execution as root not possible:", 
						   str(exception))
		if working_dir and not skip_scripts:
			try:
				cmdfilename = os.path.join(working_dir, working_basename + 
										   "." + cmdname + script_ext)
				allfilename = os.path.join(working_dir, working_basename + 
										   ".all" + script_ext)
				first = not os.path.exists(allfilename)
				last = cmdname == get_argyll_utilname("dispwin")
				cmdfile = open(cmdfilename, "w")
				allfile = open(allfilename, "a")
				cmdfiles = Files((cmdfile, allfile))
				if first:
					context = cmdfiles
				else:
					context = cmdfile
				if sys.platform == "win32":
					context.write("@echo off\n")
					context.write(('PATH %s;%%PATH%%\n' % 
								   os.path.dirname(cmd)).encode(enc, 
																"asciize"))
					cmdfiles.write('pushd "%~dp0"\n'.encode(enc, "asciize"))
					if cmdname in (get_argyll_utilname("dispcal"), 
								   get_argyll_utilname("dispread")):
						cmdfiles.write("color 07\n")
				else:
					context.write(('PATH=%s:$PATH\n' % 
								   os.path.dirname(cmd)).encode(enc, 
																"asciize"))
					if sys.platform == "darwin" and config.mac_create_app:
						cmdfiles.write('pushd "`dirname '
										'\\"$0\\"`/../../.."\n')
					else:
						cmdfiles.write('pushd "`dirname \\"$0\\"`"\n')
					if cmdname in (get_argyll_utilname("dispcal"), 
								   get_argyll_utilname("dispread")) and \
					   sys.platform != "darwin":
						cmdfiles.write('echo -e "\\033[40;2;37m" && clear\n')
					os.chmod(cmdfilename, 0755)
					os.chmod(allfilename, 0755)
				cmdfiles.write(u" ".join(quote_args(cmdline)).replace(cmd, 
					cmdname).encode(enc, "asciize") + "\n")
				if sys.platform == "win32":
					cmdfiles.write("set exitcode=%errorlevel%\n")
					if cmdname in (get_argyll_utilname("dispcal"), 
								   get_argyll_utilname("dispread")):
						# Reset to default commandline shell colors
						cmdfiles.write("color\n")
					cmdfiles.write("popd\n")
					cmdfiles.write("if not %exitcode%==0 exit /B %exitcode%\n")
				else:
					cmdfiles.write("exitcode=$?\n")
					if cmdname in (get_argyll_utilname("dispcal"), 
								   get_argyll_utilname("dispread")) and \
					   sys.platform != "darwin":
						# reset to default commandline shell colors
						cmdfiles.write('echo -e "\\033[0m" && clear\n')
					cmdfiles.write("popd\n")
					cmdfiles.write("if [ $exitcode -ne 0 ]; "
								   "then exit $exitcode; fi\n")
				cmdfiles.close()
				if sys.platform == "darwin":
					if config.mac_create_app:
						# Could also use .command file directly, but using 
						# applescript allows giving focus to the terminal 
						# window automatically after a delay
						script = mac_terminal_do_script() + \
								 mac_terminal_set_colors(do=False) + \
								 ['-e', 'set shellscript to quoted form of '
								  '(POSIX path of (path to resource '
								  '"main.command"))', '-e', 'tell app '
								  '"Terminal"', '-e', 'do script shellscript '
								  'in first window', '-e', 'delay 3', '-e', 
								  'activate', '-e', 'end tell', '-o']
						# Part 1: "cmdfile"
						appfilename = os.path.join(working_dir, 
												   working_basename + "." + 
												   cmdname + 
												   ".app").encode(fs_enc)
						cmdargs = ['osacompile'] + script + [appfilename]
						p = sp.Popen(cmdargs, stdin=sp.PIPE, stdout=sp.PIPE, 
									 stderr=sp.PIPE)
						p.communicate()
						shutil.move(cmdfilename, appfilename + 
									"/Contents/Resources/main.command")
						os.chmod(appfilename + 
								 "/Contents/Resources/main.command", 0755)
						# Part 2: "allfile"
						appfilename = os.path.join(
							working_dir,  working_basename + ".all.app")
						cmdargs = ['osacompile'] + script + [appfilename]
						p = sp.Popen(cmdargs, stdin=sp.PIPE, stdout=sp.PIPE, 
									 stderr=sp.PIPE)
						p.communicate()
						shutil.copyfile(allfilename, appfilename + 
										"/Contents/Resources/main.command")
						os.chmod(appfilename + 
								 "/Contents/Resources/main.command", 0755)
						if last:
							os.remove(allfilename)
			except Exception, exception:
				safe_print("Warning - error during shell script creation:", 
						   str(exception))
		if cmdname == get_argyll_utilname("dispread") and \
		   self.dispread_after_dispcal:
			instrument_features = self.get_instrument_features()
			if verbose >= 2:
				safe_print("Running calibration and profiling in succession, "
						   "checking instrument for unattended capability...")
				if instrument_features:
					safe_print("Instrument needs sensor calibration:", 
							   "Yes" if instrument_features.get("sensor_cal") 
							   else "No")
					if instrument_features.get("sensor_cal"):
						safe_print("Instrument can be forced to skip sensor "
							"calibration:", "Yes" if 
							instrument_features.get("skip_sensor_cal") and 
							self.argyll_version >= [1, 1, 0] else "No")
				else:
					safe_print("Warning - instrument not recognized:", 
							   self.get_instrument_name())
			# -N switch not working as expected in Argyll 1.0.3
			if instrument_features and \
			   (not instrument_features.get("sensor_cal") or 
			    (instrument_features.get("skip_sensor_cal") and 
				 self.argyll_version >= [1, 1, 0])):
				if verbose >= 2:
					safe_print("Instrument can be used for unattended "
							   "calibration and profiling")
				try:
					if verbose >= 2:
						safe_print("Sending 'SPACE' key to automatically "
								   "start measurements in 10 seconds...")
					if sys.platform == "darwin":
						start_new_thread(sendkeys, (10, "Terminal", " "))
					elif sys.platform == "win32":
						start_new_thread(sendkeys, (10, appname + exe_ext, 
													" "))
					else:
						if which("xte"):
							start_new_thread(sendkeys, (10, None, "space"))
						elif verbose >= 2:
							safe_print("Warning - 'xte' commandline tool not "
									   "found, unattended measurements not "
									   "possible")
				except Exception, exception:
					safe_print("Warning - unattended measurements not "
							   "possible (start_new_thread failed with %s)" % 
							   str(exception))
			elif verbose >= 2:
				safe_print("Instrument can not be used for unattended "
						   "calibration and profiling")
		elif cmdname in (get_argyll_utilname("dispcal"), 
						 get_argyll_utilname("dispread")) and \
			 sys.platform == "darwin" and args and self.owner and not \
			 self.owner.IsShownOnScreen():
			start_new_thread(mac_app_activate, (3, "Terminal"))
		try:
			if silent:
				stderr = sp.STDOUT
			else:
				stderr = Tea(tempfile.SpooledTemporaryFile())
			if capture_output:
				stdout = tempfile.SpooledTemporaryFile()
			else:
				stdout = sys.stdout
			if sys.platform == "win32" and working_dir:
				working_dir = win32api.GetShortPathName(working_dir)
			tries = 1
			cmdline = [arg.encode(fs_enc) for arg in cmdline]
			if sudo:
				pwdproc = sp.Popen('echo "%s"' % self.pwd, shell=True, 
								   stdin=sp.PIPE, stdout=sp.PIPE, 
								   stderr=sp.STDOUT)
				stdin = pwdproc.stdout
			else:
				stdin=None
			working_dir = None if working_dir is None else working_dir.encode(fs_enc)
			while tries > 0:
				self.subprocess = sp.Popen(cmdline, stdin=stdin, 
										   stdout=stdout, stderr=stderr, 
										   cwd=working_dir)
				self.retcode = self.subprocess.wait()
				self.subprocess = None
				tries -= 1
				if not silent:
					stderr.seek(0)
					errors = stderr.readlines()
					stderr.close()
					if len(errors):
						errors2 = []
						for line in errors:
							if "Instrument Access Failed" in line and \
							   "-N" in cmdline[:-1]:
								cmdline.remove("-N")
								tries = 1
								break
							if line.strip() and \
							   line.find("User Aborted") < 0 and \
							   line.find("XRandR 1.2 is faulty - falling back "
										 "to older extensions") < 0:
								errors2 += [line.decode(enc, "replace")]
						if len(errors2):
							self.errors = errors2
							errstr = "".join(errors2).strip()
							if (self.retcode != 0 or 
								cmdname == get_argyll_utilname("dispwin")):
								InfoDialog(parent, pos=(-1, 100), 
										   msg=errstr, ok=lang.getstr("ok"), 
										   bitmap=geticon(32, "dialog-warning"))
							else:
								safe_print(errstr, fn=fn)
					if tries > 0:
						stderr = Tea(tempfile.SpooledTemporaryFile())
				if capture_output:
					stdout.seek(0)
					self.output = [re.sub("^\.{4,}\s*$", "", 
										  line.decode(enc, "replace")) 
								   for line in stdout.readlines()]
					stdout.close()
					if len(self.output) and log_output:
						log("".join(self.output).strip())
						if display_output and self.owner and \
						   hasattr(self.owner, "infoframe"):
							wx.CallAfter(self.owner.infoframe.Show)
					if tries > 0:
						stdout = tempfile.SpooledTemporaryFile()
		except Exception, exception:
			if debug:
				safe_print('[D] working_dir:', working_dir)
			errmsg = (" ".join(cmdline).decode(fs_enc) + "\n" + 
						 "Error: " + (traceback.format_exc() if debug else 
									  str(exception)))
			if capture_output:
				log(errmsg)
			else:
				handle_error(errmsg, parent=self.owner, silent=silent)
			self.retcode = -1
		if not capture_output and low_contrast:
			# Reset to higher contrast colors (white on black) for readability
			try:
				if sys.platform == "win32":
					sp.call("color 07", shell=True)
				elif sys.platform == "darwin":
					mac_terminal_set_colors(text="white", text_bold="white")
				else:
					print "\x1b[22;37m"
			except Exception, exception:
				safe_print("Info - could not restore terminal colors:", 
						   str(exception))
		if self.retcode != 0:
			if verbose >= 1 and not capture_output:
				safe_print(lang.getstr("aborted"), fn=fn)
			return False
		return True

	def generic_consumer(self, delayedResult, consumer, *args, **kwargs):
		# consumer must accept result as first arg
		result = None
		exception = None
		try:
			result = delayedResult.get()
		except Exception, exception:
			handle_error("Error - delayedResult.get() failed: " + 
						 traceback.format_exc(), parent=self.owner)
		self.progress_parent.progress_start_timer.Stop()
		if hasattr(self.progress_parent, "progress_dlg"):
			self.progress_parent.progress_timer.Stop()
			# Do not destroy, will crash on Linux
			self.progress_parent.progress_dlg.Hide()
		wx.CallAfter(consumer, result, *args, **kwargs)

	def get_display(self):
		display_no = min(len(self.displays), getcfg("display.number")) - 1
		display = str(display_no + 1)
		if (self.has_separate_lut_access() or 
			getcfg("use_separate_lut_access")) and (
		   		not getcfg("display_lut.link") or 
		   		(display_no > -1 and not self.lut_access[display_no])):
			display_lut_no = min(len(self.displays), 
									 getcfg("display_lut.number")) - 1
			if display_lut_no > -1 and not self.lut_access[display_lut_no]:
				for display_lut_no, disp in enumerate(self.lut_access):
					if disp:
						break
			display += "," + str(display_lut_no + 1)
		return display
	
	def get_display_name(self):
		""" Return name of currently configured display """
		n = getcfg("display.number") - 1
		if n >= 0 and n < len(self.displays):
			return self.displays[n].split(" @")[0]
		return ""
	
	def get_instrument_features(self):
		""" Return features of currently configured instrument """
		return instruments.get(self.get_instrument_name(), {})
	
	def get_instrument_name(self):
		""" Return name of currently configured instrument """
		n = getcfg("comport.number") - 1
		if n >= 0 and n < len(self.instruments):
			return self.instruments[n]
		return ""
	
	def has_separate_lut_access(self):
		""" Return True if separate LUT access is possible and needed. """
		return (len(self.displays) > 1 and False in 
				self.lut_access and True in 
				self.lut_access)

	def is_working(self):
		""" Check if the Worker instance is busy. Return True or False. """
		return hasattr(self, "progress_parent") and \
			(self.progress_parent.progress_start_timer.IsRunning() or 
			 self.progress_parent.progress_timer.IsRunning())

	def prepare_colprof(self, profile_name=None, display_name=None):
		"""
		Prepare a colprof commandline.
		
		All options are read from the user configuration.
		Profile name and display name can be ovverridden by passing the
		corresponding arguments.
		
		"""
		profile_save_path = self.create_tempdir()
		if not profile_save_path or not check_create_dir(profile_save_path, 
														 parent=self.owner):
			# Check directory and in/output file(s)
			return None, None
		if profile_name is None:
			profile_name = getcfg("profile.name.expanded")
		inoutfile = make_argyll_compatible_path(os.path.join(profile_save_path, 
															 profile_name))
		if not os.path.exists(inoutfile + ".ti3"):
			InfoDialog(self.owner, pos=(-1, 100), 
					   msg=lang.getstr("error.measurement.file_missing", 
									   inoutfile + ".ti3"), 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-error"))
			return None, None
		if not os.path.isfile(inoutfile + ".ti3"):
			InfoDialog(self.owner, pos=(-1, 100), 
					   msg=lang.getstr("error.measurement.file_notfile", 
									   inoutfile + ".ti3"), 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-error"))
			return None, None
		#
		cmd = get_argyll_util("colprof")
		args = []
		args += ["-v"] # verbose
		args += ["-q" + getcfg("profile.quality")]
		args += ["-a" + getcfg("profile.type")]
		if getcfg("profile.type") in ["l", "x", "X"]:
			if getcfg("gamap_perceptual"):
				gamap = "s"
			elif getcfg("gamap_saturation"):
				gamap = "S"
			else:
				gamap = None
			if gamap:
				args += ["-" + gamap]
				args += [getcfg("gamap_profile")]
				args += ["-c" + getcfg("gamap_src_viewcond")]
				args += ["-d" + getcfg("gamap_out_viewcond")]
		self.options_colprof = list(args)
		options_colprof = list(args)
		for i in range(len(options_colprof)):
			if options_colprof[i][0] != "-":
				options_colprof[i] = '"' + options_colprof[i] + '"'
		args += ["-C"]
		args += [u"(c) %s %s. Created with %s %s and Argyll CMS %s:" % 
				 (strftime("%Y"), unicode(getpass.getuser(), fs_enc, 
										  "asciize"), appname, version, 
				  self.argyll_version_string)]
		if "-d3" in self.options_targen:
			# only add display desc and dispcal options if creating RGB profile
			if len(self.displays):
				args.insert(-2, "-M")
				if display_name is None:
					args.insert(-2, self.get_display_name())
				else:
					args.insert(-2, display_name)
			if self.options_dispcal:
				args[-1] += u" dispcal %s" % " ".join(self.options_dispcal)
		args[-1] += u" colprof %s" % " ".join(options_colprof)
		args += ["-D"]
		args += [profile_name]
		args += [inoutfile]
		return cmd, args

	def prepare_dispcal(self, calibrate=True, verify=False):
		"""
		Prepare a dispcal commandline.
		
		All options are read from the user configuration.
		You can choose if you want to calibrate and/or verify by passing 
		the corresponding arguments.
		
		"""
		cmd = get_argyll_util("dispcal")
		args = []
		args += ["-v"] # verbose
		args += ["-d" + self.get_display()]
		args += ["-c%s" % getcfg("comport.number")]
		self.add_measurement_features(args)
		if calibrate:
			args += ["-q" + getcfg("calibration.quality")]
			profile_save_path = self.create_tempdir()
			if not profile_save_path or not check_create_dir(profile_save_path, 
															 parent=self.owner):
				return None, None
			inoutfile = make_argyll_compatible_path(
				os.path.join(profile_save_path, 
							 getcfg("profile.name.expanded")))
			if getcfg("calibration.update") or \
			   self.dispcal_create_fast_matrix_shaper:
				args += ["-o"]
			if getcfg("calibration.update"):
				cal = getcfg("calibration.file")
				calcopy = os.path.join(inoutfile + ".cal")
				filename, ext = os.path.splitext(cal)
				ext = ".cal"
				cal = filename + ext
				if ext.lower() == ".cal":
					if not check_cal_isfile(cal, parent=self.owner):
						return None, None
					if not os.path.exists(calcopy):
						try:
							# Copy cal to profile dir
							shutil.copyfile(cal, calcopy) 
						except Exception, exception:
							InfoDialog(self.owner, pos=(-1, 100), 
									   msg=lang.getstr("error.copy_failed", 
													   (cal, calcopy)) + 
										   "\n\n" + unicode(str(exception), 
															enc, "replace"), 
									   ok=lang.getstr("ok"), 
									   bitmap=geticon(32, "dialog-error"))
							return None, None
						if not check_cal_isfile(calcopy, parent=self.owner):
							return None, None
						cal = calcopy
				else:
					rslt = extract_fix_copy_cal(cal, calcopy)
					if isinstance(rslt, ICCP.ICCProfileInvalidError):
						InfoDialog(self.owner, 
								   msg=lang.getstr("profile.invalid") + 
									   "\n" + cal, 
								   ok=lang.getstr("ok"), 
								   bitmap=geticon(32, "dialog-error"))
					elif isinstance(rslt, Exception):
						InfoDialog(self.owner, 
								   msg=lang.getstr("cal_extraction_failed") + 
									   "\n" + cal + 
									   "\n\n" + unicode(str(rslt), enc, 
														"replace"), 
								   ok=lang.getstr("ok"), 
								   bitmap=geticon(32, "dialog-error"))
					if not isinstance(rslt, list):
						return None, None
				if getcfg("profile.update"):
					profile_path = os.path.splitext(
						getcfg("calibration.file"))[0] + profile_ext
					if not check_profile_isfile(profile_path, 
												parent=self.owner):
						return None, None
					profilecopy = os.path.join(inoutfile + profile_ext)
					if not os.path.exists(profilecopy):
						try:
							# Copy profile to profile dir
							shutil.copyfile(profile_path, profilecopy)
						except Exception, exception:
							InfoDialog(self.owner, pos=(-1, 100), 
									   msg=lang.getstr("error.copy_failed", 
													   (profile_path, 
													    profilecopy)) + 
										   "\n\n" + unicode(str(exception), 
															enc, "replace"), 
									   ok=lang.getstr("ok"), 
									   bitmap=geticon(32, "dialog-error"))
							return None, None
						if not check_profile_isfile(profilecopy, 
													parent=self.owner):
							return None, None
				args += ["-u"]
		if (calibrate and not getcfg("calibration.update")) or \
		   (not calibrate and verify):
			if calibrate and not \
			   getcfg("calibration.interactive_display_adjustment"):
				# Skip interactive display adjustment
				args += ["-m"]
			whitepoint_colortemp = getcfg("whitepoint.colortemp", False)
			whitepoint_x = getcfg("whitepoint.x", False)
			whitepoint_y = getcfg("whitepoint.y", False)
			if whitepoint_colortemp or None in (whitepoint_x, whitepoint_y):
				whitepoint = getcfg("whitepoint.colortemp.locus")
				if whitepoint_colortemp:
					whitepoint += str(whitepoint_colortemp)
				args += ["-" + whitepoint]
			else:
				args += ["-w%s,%s" % (whitepoint_x, whitepoint_y)]
			luminance = getcfg("calibration.luminance", False)
			if luminance:
				args += ["-b%s" % luminance]
			args += ["-" + getcfg("trc.type") + str(getcfg("trc"))]
			args += ["-f%s" % getcfg("calibration.black_output_offset")]
			if bool(int(getcfg("calibration.ambient_viewcond_adjust"))):
				args += ["-a%s" % 
						 getcfg("calibration.ambient_viewcond_adjust.lux")]
			args += ["-k%s" % getcfg("calibration.black_point_correction")]
			if defaults["calibration.black_point_rate.enabled"] and \
			   float(getcfg("calibration.black_point_correction")) < 1:
				black_point_rate = getcfg("calibration.black_point_rate")
				if black_point_rate:
					args += ["-A%s" % black_point_rate]
			black_luminance = getcfg("calibration.black_luminance", False)
			if black_luminance:
				args += ["-B%s" % black_luminance]
			if verify:
				if calibrate and type(verify) == int:
					args += ["-e%s" % verify]  # Verify final computed curves
				else:
					args += ["-E"]  # Verify current curves
		self.options_dispcal = list(args)
		if calibrate:
			args += [inoutfile]
		return cmd, args

	def prepare_dispread(self, apply_calibration=True):
		"""
		Prepare a dispread commandline.
		
		All options are read from the user configuration.
		You can choose if you want to apply the current calibration,
		either from the user configuration by passing in 'True', or by
		passing in a valid path to a .cal file.
		
		"""
		profile_save_path = self.create_tempdir()
		if not profile_save_path or not check_create_dir(profile_save_path, 
														 parent=self.owner):
			# Check directory and in/output file(s)
			return None, None
		inoutfile = make_argyll_compatible_path(
			os.path.join(profile_save_path, getcfg("profile.name.expanded")))
		if not os.path.exists(inoutfile + ".ti1"):
			filename, ext = os.path.splitext(getcfg("testchart.file"))
			if not check_file_isfile(filename + ext, parent=self.owner):
				return None, None
			try:
				if ext.lower() in (".icc", ".icm"):
					try:
						profile = ICCP.ICCProfile(filename + ext)
					except (IOError, ICCP.ICCProfileInvalidError), exception:
						InfoDialog(self.owner, pos=(-1, 100), 
								   msg=lang.getstr("error.testchart.read", 
												   getcfg("testchart.file")), 
								   ok=lang.getstr("ok"), 
								   bitmap=geticon(32, "dialog-error"))
						return None, None
					ti3 = StringIO(profile.tags.get("CIED", "") or 
								   profile.tags.get("targ", ""))
				elif ext.lower() == ".ti1":
					shutil.copyfile(filename + ext, inoutfile + ".ti1")
				else: # ti3
					try:
						ti3 = open(filename + ext, "rU")
					except Exception, exception:
						InfoDialog(self.owner, pos=(-1, 100), 
								   msg=lang.getstr("error.testchart.read", 
												   getcfg("testchart.file")), 
								   ok=lang.getstr("ok"), 
								   bitmap=geticon(32, "dialog-error"))
						return None, None
				if ext.lower() != ".ti1":
					ti3_lines = [line.strip() for line in ti3]
					ti3.close()
					if not "CTI3" in ti3_lines:
						InfoDialog(self.owner, pos=(-1, 100), 
								   msg=lang.getstr("error.testchart.invalid", 
												   getcfg("testchart.file")), 
								   ok=lang.getstr("ok"), 
								   bitmap=geticon(32, "dialog-error"))
						return None, None
					ti1 = open(inoutfile + ".ti1", "w")
					ti1.write(ti3_to_ti1(ti3_lines))
					ti1.close()
			except Exception, exception:
				InfoDialog(self.owner, pos=(-1, 100), 
						   msg=lang.getstr("error.testchart.creation_failed", 
										   inoutfile + ".ti1") + "\n\n" + 
							   unicode(str(exception), enc, "replace"), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				return None, None
		if apply_calibration:
			if apply_calibration is True:
				# Always a .cal file in that case
				cal = os.path.join(getcfg("profile.save_path"), 
								   getcfg("profile.name.expanded"), 
								   getcfg("profile.name.expanded")) + ".cal"
			else:
				cal = apply_calibration # can be .cal or .icc / .icm
			calcopy = os.path.join(inoutfile + ".cal")
			filename, ext = os.path.splitext(cal)
			if ext.lower() == ".cal":
				if not check_cal_isfile(cal, parent=self.owner):
					return None, None
				if not os.path.exists(calcopy):
					try:
						# Copy cal to temp dir
						shutil.copyfile(cal, calcopy)
					except Exception, exception:
						InfoDialog(self.owner, pos=(-1, 100), 
								   msg=lang.getstr("error.copy_failed", 
												   (cal, calcopy)) + "\n\n" + 
									   unicode(str(exception), enc, "replace"), 
								   ok=lang.getstr("ok"), 
								   bitmap=geticon(32, "dialog-error"))
						return None, None
					if not check_cal_isfile(calcopy, parent=self.owner):
						return None, None
			else:
				# .icc / .icm
				self.options_dispcal = []
				if not check_profile_isfile(cal, parent=self.owner):
					return None, None
				try:
					profile = ICCP.ICCProfile(filename + ext)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					profile = None
				if profile:
					ti3 = StringIO(profile.tags.get("CIED", "") or 
								   profile.tags.get("targ", ""))
					if "cprt" in profile.tags:
						# Get dispcal options if present
						self.options_dispcal = ["-" + arg for arg in 
							get_options_from_cprt(profile.getCopyright())[0]]
				else:
					ti3 = StringIO("")
				ti3_lines = [line.strip() for line in ti3]
				ti3.close()
				if not "CTI3" in ti3_lines:
					InfoDialog(self.owner, pos=(-1, 100), 
							   msg=lang.getstr("error.cal_extraction", (cal)), 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
					return None, None
				try:
					tmpcal = open(calcopy, "w")
					tmpcal.write(extract_cal_from_ti3(ti3_lines))
					tmpcal.close()
				except Exception, exception:
					InfoDialog(self.owner, pos=(-1, 100), 
							   msg=lang.getstr("error.cal_extraction", (cal)) + 
								   "\n\n" + unicode(str(exception), enc, 
													"replace"), 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
					return None, None
			cal = calcopy
		#
		cmd = get_argyll_util("dispread")
		args = []
		args += ["-v"] # verbose
		args += ["-d" + self.get_display()]
		args += ["-c%s" % getcfg("comport.number")]
		self.add_measurement_features(args)
		if apply_calibration:
			args += ["-k"]
			args += [cal]
		self.options_dispread = args + self.options_dispread
		return cmd, self.options_dispread + [inoutfile]

	def prepare_dispwin(self, cal=None, profile_path=None, install=True):
		"""
		Prepare a dispwin commandline.
		
		All options are read from the user configuration.
		If you pass in cal as True, it will try to load the current 
		display profile's calibration. If cal is a path, it'll use
		that instead. If cal is False, it'll clear the current calibration.
		If cal is None, it'll try to load the calibration from a profile
		specified by profile_path.
		
		"""
		cmd = get_argyll_util("dispwin")
		args = []
		args += ["-v"]
		args += ["-d" + self.get_display()]
		args += ["-c"]
		if cal is True:
			args += ["-L"]
		elif cal:
			if not check_cal_isfile(cal, parent=self.owner):
				return None, None
			args += [cal]
		else:
			if cal is None:
				if not profile_path:
					profile_save_path = os.path.join(
						getcfg("profile.save_path"), 
						getcfg("profile.name.expanded"))
					profile_path = os.path.join(profile_save_path, 
						getcfg("profile.name.expanded") + profile_ext)
				if not check_profile_isfile(profile_path, parent=self.owner):
					return None, None
				try:
					profile = ICCP.ICCProfile(profile_path)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					InfoDialog(self.owner, msg=lang.getstr("profile.invalid") + 
											   "\n" + profile_path, 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
					return None, None
				if profile.profileClass != "mntr" or \
				   profile.colorSpace != "RGB":
					InfoDialog(self.owner, 
							   msg=lang.getstr("profile.unsupported", 
											   (profile.profileClass, 
											    profile.colorSpace)) + 
								   "\n" + profile_path, 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
					return None, None
				if install:
					if getcfg("profile.install_scope") != "u" and \
						(((sys.platform == "darwin" or 
						   (sys.platform != "win32" and 
							self.argyll_version >= [1, 1, 0])) and 
						  (os.geteuid() == 0 or which("sudo"))) or 
						 (sys.platform == "win32" and 
						  sys.getwindowsversion() >= (6, )) or test):
							# -S option is broken on Linux with current Argyll 
							# releases
							args += ["-S" + getcfg("profile.install_scope")]
					args += ["-I"]
				args += [profile_path]
		return cmd, args

	def prepare_targen(self):
		"""
		Prepare a targen commandline.
		
		All options are read from the user configuration.
		
		"""
		path = self.create_tempdir()
		if not path or not check_create_dir(path, parent=self.owner):
			# Check directory and in/output file(s)
			return None, None
		inoutfile = os.path.join(path, "temp")
		cmd = get_argyll_util("targen")
		args = []
		args += ['-v']
		args += ['-d3']
		args += ['-e%s' % getcfg("tc_white_patches")]
		args += ['-s%s' % getcfg("tc_single_channel_patches")]
		args += ['-g%s' % getcfg("tc_gray_patches")]
		args += ['-m%s' % getcfg("tc_multi_steps")]
		if getcfg("tc_fullspread_patches") > 0:
			args += ['-f%s' % config.get_total_patches()]
			tc_algo = getcfg("tc_algo")
			if tc_algo:
				args += ['-' + tc_algo]
			if tc_algo in ("i", "I"):
				args += ['-a%s' % getcfg("tc_angle")]
			if tc_algo == "":
				args += ['-A%s' % getcfg("tc_adaption")]
			if getcfg("tc_precond") and getcfg("tc_precond_profile"):
				args += ['-c']
				args += [getcfg("tc_precond_profile")]
			if getcfg("tc_filter"):
				args += ['-F%s,%s,%s,%s' % (getcfg("tc_filter_L"), 
											getcfg("tc_filter_a"), 
											getcfg("tc_filter_b"), 
											getcfg("tc_filter_rad"))]
		else:
			args += ['-f0']
		if getcfg("tc_vrml"):
			if getcfg("tc_vrml_lab"):
				args += ['-w']
			if getcfg("tc_vrml_device"):
				args += ['-W']
		self.options_targen = list(args)
		args += [inoutfile]
		return cmd, args

	def progress_timer_handler(self, event):
		keepGoing, skip = self.progress_parent.progress_dlg.Pulse(
			self.progress_parent.progress_dlg.GetTitle())
		if not keepGoing:
			if hasattr(self, "subprocess") and self.subprocess:
				if (hasattr(self.subprocess, "poll") and 
					self.subprocess.poll() is None) or \
				   (hasattr(self.subprocess, "isalive") and 
				    self.subprocess.isalive()):
					try:
						self.subprocess.terminate()
					except Exception, exception:
						handle_error("Error - subprocess.terminate() "
									 "failed: " + str(exception), 
									 parent=self.progress_parent.progress_dlg)
				elif verbose >= 2:
					safe_print("Info: Subprocess already exited.")
			else:
				self.thread_abort = True

	def progress_dlg_start(self, progress_title="", progress_msg="", 
						   parent=None):
		style = wx.PD_APP_MODAL | wx.PD_ELAPSED_TIME | wx.PD_CAN_ABORT
		self.progress_parent.progress_dlg = wx.ProgressDialog(progress_title, 
															  progress_msg, 
															  parent=parent, 
															  style=style)
		for child in self.progress_parent.progress_dlg.GetChildren():
			if isinstance(child, wx.Button):
				child.Label = lang.getstr("cancel")
			elif isinstance(child, wx.StaticText) and \
				 "Elapsed time" in child.Label:
				child.Label = lang.getstr("elapsed_time").replace(" ", u"\xa0")
		self.progress_parent.progress_dlg.SetSize((400, -1))
		self.progress_parent.progress_dlg.Center()
		self.progress_parent.progress_timer.Start(50)

	def start(self, consumer, producer, cargs=(), ckwargs=None, wargs=(), 
			  wkwargs=None, progress_title="", progress_msg="", parent=None, 
			  progress_start=100):
		"""
		Start a worker process.
		
		Also show a progress dialog while the process is running.
		
		"""
		if ckwargs is None:
			ckwargs = {}
		if wkwargs is None:
			wkwargs = {}
		while self.is_working():
			sleep(250) # wait until previous worker thread finishes
		if hasattr(self.owner, "stop_timers"):
			self.owner.stop_timers()
		if not progress_msg:
			progress_msg = progress_title
		if not parent:
			parent = self.owner
		self.progress_parent = parent
		if not hasattr(self.progress_parent, "progress_timer"):
			self.progress_parent.progress_timer = wx.Timer(self.progress_parent)
			self.progress_parent.Bind(wx.EVT_TIMER, 
									  self.progress_timer_handler, 
									  self.progress_parent.progress_timer)
		if progress_start < 100:
			progress_start = 100
		# Show the progress dialog after 1ms
		self.progress_parent.progress_start_timer = wx.CallLater(
			progress_start, self.progress_dlg_start, progress_title, 
			progress_msg, parent) 
		self.thread_abort = False
		self.thread = delayedresult.startWorker(self.generic_consumer, 
												producer, [consumer] + 
												list(cargs), ckwargs, wargs, 
												wkwargs)
		return True

	def wrapup(self, copy=True, remove=True, dst_path=None, ext_filter=None):
		"""
		Wrap up - copy and/or clean temporary file(s).
		
		"""
		if debug: safe_print("[D] wrapup(copy=%s, remove=%s)" % (copy, remove))
		if not self.tempdir or not os.path.isdir(self.tempdir):
			return # nothing to do
		if copy:
			if not ext_filter:
				ext_filter = [".app", ".cal", ".cmd", ".command", ".icc", 
							  ".icm", ".sh", ".ti1", ".ti3"]
			if dst_path is None:
				dst_path = os.path.join(getcfg("profile.save_path"), 
										getcfg("profile.name.expanded"), 
										getcfg("profile.name.expanded") + 
										".ext")
			try:
				dir_created = check_create_dir(os.path.dirname(dst_path), 
											   parent=self.owner)
			except Exception, exception:
				InfoDialog(self.owner, pos=(-1, 100), 
						   msg=lang.getstr("error.dir_creation", 
										   (os.path.dirname(dst_path))) + 
							   "\n\n" + unicode(str(exception), enc, 
												"replace"), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				return
			if dir_created:
				try:
					src_listdir = os.listdir(self.tempdir)
				except Exception, exception:
					safe_print("Error - directory '%s' listing failed: %s" % 
							   (self.tempdir, str(exception)))
				else:
					for basename in src_listdir:
						name, ext = os.path.splitext(basename)
						if ext_filter is None or ext.lower() in ext_filter:
							src = os.path.join(self.tempdir, basename)
							dst = os.path.splitext(dst_path)[0]
							if ext.lower() in (".app", script_ext):
								# Preserve *.<utility>.[app|cmd|sh]
								dst += os.path.splitext(name)[1]
							dst += ext
							if os.path.exists(dst):
								if os.path.isdir(dst):
									if debug:
										safe_print("[D] wrapup.copy: "
												   "shutil.rmtree('%s', "
												   "True)" % dst)
									try:
										shutil.rmtree(dst, True)
									except Exception, exception:
										safe_print("Warning - directory '%s' "
												   "could not be removed: %s" % 
												   (dst, str(exception)))
								else:
									if debug:
										safe_print("[D] wrapup.copy: "
												   "os.remove('%s')" % dst)
									try:
										os.remove(dst)
									except Exception, exception:
										safe_print("Warning - file '%s' could "
												   "not be removed: %s" % 
												   (dst, str(exception)))
							if remove:
								if debug:
									safe_print("[D] wrapup.copy: "
											   "shutil.move('%s', "
											   "'%s')" % (src, dst))
								try:
									shutil.move(src, dst)
								except Exception, exception:
									safe_print("Warning - temporary object "
											   "'%s' could not be moved to "
											   "'%s': %s" % (src, dst, 
															 str(exception)))
							else:
								if os.path.isdir(src):
									if debug:
										safe_print("[D] wrapup.copy: "
												   "shutil.copytree('%s', "
												   "'%s')" % (src, dst))
									try:
										shutil.copytree(src, dst)
									except Exception, exception:
										safe_print("Warning - temporary "
												   "directory '%s' could not "
												   "be copied to '%s': %s" % 
												   (src, dst, str(exception)))
								else:
									if debug:
										safe_print("[D] wrapup.copy: "
												   "shutil.copyfile('%s', "
												   "'%s')" % (src, dst))
									try:
										shutil.copyfile(src, dst)
									except Exception, exception:
										safe_print("Warning - temporary file "
												   "'%s' could not be copied "
												   "to '%s': %s" % 
												   (src, dst, str(exception)))
		if remove:
			try:
				src_listdir = os.listdir(self.tempdir)
			except Exception, exception:
				safe_print("Error - directory '%s' listing failed: %s" % 
						   (self.tempdir, str(exception)))
			else:
				for basename in src_listdir:
					name, ext = os.path.splitext(basename)
					if ext_filter is None or ext.lower() not in ext_filter:
						src = os.path.join(self.tempdir, basename)
						isdir = os.path.isdir(src)
						if isdir:
							if debug:
								safe_print("[D] wrapup.remove: "
										   "shutil.rmtree('%s', True)" % src)
							try:
								shutil.rmtree(src, True)
							except Exception, exception:
								safe_print("Warning - temporary directory "
										   "'%s' could not be removed: %s" % 
										   (src, str(exception)))
						else:
							if debug:
								safe_print("[D] wrapup.remove: os.remove('%s')" % 
										   src)
							try:
								os.remove(src)
							except Exception, exception:
								safe_print("Warning - temporary directory "
										   "'%s' could not be removed: %s" % 
										   (src, str(exception)))
			try:
				src_listdir = os.listdir(self.tempdir)
			except Exception, exception:
				safe_print("Error - directory '%s' listing failed: %s" % 
						   (self.tempdir, str(exception)))
			else:
				if not src_listdir:
					try:
						shutil.rmtree(self.tempdir, True)
					except Exception, exception:
						safe_print("Warning - temporary directory '%s' could "
								   "not be removed: %s" % (self.tempdir, 
														   str(exception)))
