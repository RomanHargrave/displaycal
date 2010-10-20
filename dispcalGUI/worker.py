#!/usr/bin/env python
# -*- coding: utf-8 -*-

# stdlib
import getpass
import math
import os
import re
import shutil
import subprocess as sp
import sys
import tempfile
import textwrap
import traceback
from encodings.aliases import aliases
from hashlib import md5
from time import sleep, strftime, time
if sys.platform == "darwin":
	from thread import start_new_thread
elif sys.platform == "win32":
	from ctypes import windll

# 3rd party
if sys.platform == "win32":
	import pywintypes
	import win32api
	import win32com.client

# custom
import CGATS
import ICCProfile as ICCP
import colormath
import config
import localization as lang
import wexpect
from argyll_cgats import (add_options_to_ti3, extract_fix_copy_cal, ti3_to_ti1, 
						  verify_cgats)
from argyll_instruments import instruments as all_instruments, remove_vendor_names
from argyll_names import (names as argyll_names, altnames as argyll_altnames, 
						  viewconds)
from config import (script_ext, defaults, enc, exe_ext, fs_enc, getcfg, 
					geticon, get_data_path, get_verified_path, isapp, profile_ext,
					setcfg, writecfg)
from debughelpers import handle_error
from edid import WMIConnectionAttributeError, get_edid
from log import log, safe_print
from meta import name as appname, version
from options import ascii, debug, test, test_require_sensor_cal, verbose
from ordereddict import OrderedDict
from util_io import Files, StringIOu as StringIO
if sys.platform == "darwin":
	from util_mac import (mac_app_activate, mac_terminal_do_script, 
						  mac_terminal_set_colors)
from util_os import getenvu, putenvu, quote_args, which
from util_str import safe_str, safe_unicode
from wxaddons import wx
from wxwindows import ConfirmDialog, InfoDialog, ProgressDialog, SimpleTerminal
import wx.lib.delayedresult as delayedresult

if sys.platform == "win32": #and SendKeys is None:
	wsh_shell = win32com.client.Dispatch("WScript.Shell")

USE_WPOPEN = 0

DD_ATTACHED_TO_DESKTOP = 0x01
DD_MULTI_DRIVER        = 0x02
DD_PRIMARY_DEVICE      = 0x04
DD_MIRRORING_DRIVER    = 0x08
DD_VGA_COMPATIBLE      = 0x10
DD_REMOVABLE           = 0x20
DD_DISCONNECT          = 0x2000000  # WINVER >= 5
DD_REMOTE              = 0x4000000  # WINVER >= 5
DD_MODESPRUNED         = 0x8000000  # WINVER >= 5

keycodes = {wx.WXK_NUMPAD0: ord("0"),
			wx.WXK_NUMPAD1: ord("1"),
			wx.WXK_NUMPAD2: ord("2"),
			wx.WXK_NUMPAD3: ord("3"),
			wx.WXK_NUMPAD4: ord("4"),
			wx.WXK_NUMPAD5: ord("5"),
			wx.WXK_NUMPAD6: ord("6"),
			wx.WXK_NUMPAD7: ord("7"),
			wx.WXK_NUMPAD8: ord("8"),
			wx.WXK_NUMPAD9: ord("9"),
			wx.WXK_NUMPAD_ADD: ord("+"),
			wx.WXK_NUMPAD_ENTER: ord("\n"),
			wx.WXK_NUMPAD_EQUAL: ord("="),
			wx.WXK_NUMPAD_DIVIDE: ord("/"),
			wx.WXK_NUMPAD_MULTIPLY: ord("*"),
			wx.WXK_NUMPAD_SUBTRACT: ord("-")}


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


def check_create_dir(path):
	"""
	Try to create a directory and show an error message on failure.
	"""
	if not os.path.exists(path):
		try:
			os.makedirs(path)
		except Exception, exception:
			return Error(lang.getstr("error.dir_creation", path) + "\n\n" + 
						 safe_unicode(exception))
	if not os.path.isdir(path):
		return Error(lang.getstr("error.dir_notdir", path))
	return True


def check_cal_isfile(cal=None, missing_msg=None, notfile_msg=None, 
					 silent=False):
	"""
	Check if a calibration file exists and show an error message if not.
	"""
	if not silent:
		if not missing_msg:
			missing_msg = lang.getstr("error.calibration.file_missing", cal)
		if not notfile_msg:
			notfile_msg = lang.getstr("error.calibration.file_notfile", cal)
	return check_file_isfile(cal, missing_msg, notfile_msg, silent)


def check_profile_isfile(profile_path=None, missing_msg=None, 
						 notfile_msg=None, silent=False):
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
	return check_file_isfile(profile_path, missing_msg, notfile_msg, silent)


def check_file_isfile(filename, missing_msg=None, notfile_msg=None, 
					  silent=False):
	"""
	Check if a file exists and show an error message if not.
	"""
	if not os.path.exists(filename):
		if not silent:
			if not missing_msg:
				missing_msg = lang.getstr("file.missing", filename)
			return Error(missing_msg)
		return False
	if not os.path.isfile(filename):
		if not silent:
			if not notfile_msg:
				notfile_msg = lang.getstr("file.notfile", filename)
			return Error(notfile_msg)
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
		cmd = get_argyll_util(name)
		if sys.platform == "win32":
			startupinfo = sp.STARTUPINFO()
			startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
			startupinfo.wShowWindow = sp.SW_HIDE
		else:
			startupinfo = None
		p = sp.Popen([cmd.encode(fs_enc)], stdin=sp.PIPE, stdout=sp.PIPE, 
					 stderr=sp.STDOUT, startupinfo=startupinfo)
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


def parse_argument_string(args):
	""" Parses an argument string and returns a list of arguments. """
	return [arg.strip('"\'') for arg in re.findall('(?:^|\s+)(-[^\s]+|["\'][^"\']+?["\']|\S+)', args)]


def get_options_from_args(dispcal_args=None, colprof_args=None):
	"""
	Extract options used for dispcal and colprof from argument strings.
	"""
	re_options_dispcal = [
		"[moupHV]",
		"d\d+(?:,\d+)?",
		"[cv]\d+",
		"q[vlmh]",
		"y[cl]",
		"[tT](?:\d+(?:\.\d+)?)?",
		"w\d+(?:\.\d+)?,\d+(?:\.\d+)?",
		"[bfakABF]\d+(?:\.\d+)?",
		"(?:g(?:240|709|l|s)|[gG]\d+(?:\.\d+)?)",
		"[pP]\d+(?:\.\d+)?,\d+(?:\.\d+)?,\d+(?:\.\d+)?",
		'X\s+["\'][^"\']+?["\']',  # Argyll >= 1.3.0 colorimeter correction matrix
		"I[bw]{,2}"  # Argyll >= 1.3.0 drift compensation
	]
	re_options_colprof = [
		"q[lmh]",
		"a[lxXgsGS]",
		'[sSMA]\s+["\'][^"\']+?["\']',
		"[cd](?:%s)" % "|".join(viewconds)
	]
	options_dispcal = []
	options_colprof = []
	if dispcal_args:
		options_dispcal = re.findall(" -(" + "|".join(re_options_dispcal) + 
									 ")", " " + dispcal_args)
	if colprof_args:
		options_colprof = re.findall(" -(" + "|".join(re_options_colprof) + 
									 ")", " " + colprof_args)
	return options_dispcal, options_colprof

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
	dispcal_args = cprt.split(" dispcal ")
	colprof_args = None
	if len(dispcal_args) > 1:
		dispcal_args[1] = dispcal_args[1].split(" colprof ")
		if len(dispcal_args[1]) > 1:
			colprof_args = dispcal_args[1][1]
		dispcal_args = dispcal_args[1][0]
	else:
		dispcal_args = None
		colprof_args = cprt.split(" colprof ")
		if len(colprof_args) > 1:
			colprof_args = colprof_args[1]
		else:
			colprof_args = None
	return dispcal_args, colprof_args


def get_options_from_cal(cal):
	if not isinstance(cal, CGATS.CGATS):
		cal = CGATS.CGATS(cal)
	if not cal or not "ARGYLL_DISPCAL_ARGS" in cal[0] or \
	   not cal[0].ARGYLL_DISPCAL_ARGS:
		return [], []
	dispcal_args = cal[0].ARGYLL_DISPCAL_ARGS[0].decode("UTF-7", "replace")
	return get_options_from_args(dispcal_args)


def get_options_from_profile(profile):
	""" Try and get options from profile. First, try the 'targ' tag and 
	look for the special dispcalGUI sections 'ARGYLL_DISPCAL_ARGS' and
	'ARGYLL_COLPROF_ARGS'. If either does not exist, fall back to the 
	copyright tag (dispcalGUI < 0.4.0.2) """
	if not isinstance(profile, ICCP.ICCProfile):
		profile = ICCP.ICCProfile(profile)
	dispcal_args = None
	colprof_args = None
	if "targ" in profile.tags:
		ti3 = CGATS.CGATS(profile.tags.targ)
		if len(ti3) > 1 and "ARGYLL_DISPCAL_ARGS" in ti3[1] and \
		   ti3[1].ARGYLL_DISPCAL_ARGS:
			dispcal_args = ti3[1].ARGYLL_DISPCAL_ARGS[0].decode("UTF-7", 
																"replace")
		if "ARGYLL_COLPROF_ARGS" in ti3[0] and \
		   ti3[0].ARGYLL_COLPROF_ARGS:
			colprof_args = ti3[0].ARGYLL_COLPROF_ARGS[0].decode("UTF-7", 
																"replace")
	if not dispcal_args and "cprt" in profile.tags:
		dispcal_args = get_options_from_cprt(profile.getCopyright())[0]
	if not colprof_args and "cprt" in profile.tags:
		colprof_args = get_options_from_cprt(profile.getCopyright())[1]
	return get_options_from_args(dispcal_args, colprof_args)


def get_options_from_ti3(ti3):
	if not isinstance(ti3, CGATS.CGATS):
		ti3 = CGATS.CGATS(ti3)
	dispcal_args = None
	colprof_args = None
	if len(ti3) > 1 and "ARGYLL_DISPCAL_ARGS" in ti3[1] and \
	   ti3[1].ARGYLL_DISPCAL_ARGS:
		dispcal_args = ti3[1].ARGYLL_DISPCAL_ARGS[0].decode("UTF-7", 
															"replace")
	if "ARGYLL_COLPROF_ARGS" in ti3[0] and \
	   ti3[0].ARGYLL_COLPROF_ARGS:
		colprof_args = ti3[0].ARGYLL_COLPROF_ARGS[0].decode("UTF-7", 
															"replace")
	return get_options_from_args(dispcal_args, colprof_args)


def make_argyll_compatible_path(path):
	"""
	Make the path compatible with the Argyll utilities.
	
	This is currently only effective under Windows to make sure that any 
	unicode 'division' slashes in the profile name are replaced with 
	underscores.
	
	"""
	###Under Linux if the encoding is not UTF-8 everything is 
	###forced to ASCII to prevent problems when installing profiles.
	##if ascii or (sys.platform not in ("darwin", "win32") and 
				 ##fs_enc.upper() not in ("UTF8", "UTF-8")):
		##make_compat_enc = "ASCII"
	##else:
	make_compat_enc = fs_enc
	skip = -1
	if re.match(r'\\\\\?\\', path, re.I):
		# Don't forget about UNC paths: 
		# \\?\UNC\Server\Volume\File
		# \\?\C:\File
		skip = 2
	parts = path.split(os.path.sep)
	for i in range(len(parts)):
		if i > skip:
			parts[i] = unicode(parts[i].encode(make_compat_enc, "safe_asciize"), 
							   make_compat_enc).replace("/", "_").replace("?", 
																		  "_")
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
		item = quote_args([item])[0]
		##if not item.startswith("-") and len(lines) and i < len(args) - 1:
			##lines[-1] += "\n      " + item
		##else:
		lines.append(item)
		i += 1
	for line in lines:
		safe_print(textwrap.fill(line, 80, expand_tabs = False, 
				   replace_whitespace = False, initial_indent = "    ", 
				   subsequent_indent = "      "), fn = fn)


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
				not_found = []
				for name in argyll_names:
					if not get_argyll_util(name, [path]):
						not_found.append((" " + 
										  lang.getstr("or") + 
										  " ").join(filter(lambda altname: not "argyll" in altname, 
														   [altname + exe_ext 
														    for altname in 
															argyll_altnames[name]])))
				InfoDialog(parent, msg=path + "\n\n" + 
								   lang.getstr("argyll.dir.invalid", 
											   ", ".join(not_found)), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
		else:
			break
	dlg.Destroy()
	return result


def show_result_dialog(result, parent=None, pos=None):
	msg=result.args[0]
	if not pos:
		pos=(-1, -1)
	if isinstance(result, Info):
		bitmap = geticon(32, "dialog-information")
	elif isinstance(result, Warning):
		bitmap = geticon(32, "dialog-warning")
	else:
		bitmap = geticon(32, "dialog-error")
	InfoDialog(parent, pos=pos, msg=msg, ok=lang.getstr("ok"), bitmap=bitmap, 
			   log=not isinstance(result, UnloggedError))


class Error(Exception):
	pass


class Info(UserWarning):
	pass


class UnloggedError(Error):
	pass


class Warn(UserWarning):
	pass


class FilteredStream():
	
	""" Wrap a stream and filter all lines written to it. """
	
	# Discard progress information like ... or *** or %
	discard = ""
	
	# If one of the triggers is contained in a line, skip the whole line
	triggers = ["Place instrument on test window",
				"key to continue",
				"key to retry",
				"key to take a reading",
				"Esc or Q"]
	
	substitutions = {" peqDE ": " previous pass DE ",
					 "patch ": "Patch ",
					 re.compile("Point (\\d+ Delta E)", re.I): " point \\1"}
	
	def __init__(self, stream, data_encoding=None, file_encoding=None,
				 errors="replace", discard=None, linesep_in="\r\n", 
				 linesep_out="\n", substitutions=None,
				 triggers=None):
		self.stream = stream
		self.data_encoding = data_encoding
		self.file_encoding = file_encoding
		self.errors = errors
		if discard is not None:
			self.discard = discard
		self.linesep_in = linesep_in
		self.linesep_out = linesep_out
		if substitutions is not None:
			self.substitutions = substitutions
		if triggers is not None:
			self.triggers = triggers
	
	def __getattr__(self, name):
		return getattr(self.stream, name)
	
	def write(self, data):
		""" Write data to stream, stripping all unwanted output.
		
		Incoming lines are expected to be delimited by linesep_in.
		
		"""
		if not data:
			return
		lines = []
		for line in data.split(self.linesep_in):
			if line and not re.sub(self.discard, "", line):
				line = ""
			write = True
			for trigger in self.triggers:
				if trigger.lower() in line.lower():
					write = False
					break
			if write:
				if self.data_encoding:
					line = line.decode(self.data_encoding, self.errors)
				for search, sub in self.substitutions.iteritems():
					line = re.sub(search, sub, line)
				if self.file_encoding:
					line = line.encode(self.file_encoding, self.errors)
				lines.append(line)
		if lines:
			self.stream.write(self.linesep_out.join(lines))


class LineBufferedStream():
	
	""" Buffer lines and only write them to stream if line separator is 
		detected """
		
	def __init__(self, stream, data_encoding=None, file_encoding=None,
				 errors="replace", linesep_in="\r\n", linesep_out="\n"):
		self.buf = ""
		self.data_encoding = data_encoding
		self.file_encoding = file_encoding
		self.errors = errors
		self.linesep_in = linesep_in
		self.linesep_out = linesep_out
		self.stream = stream
	
	def __del__(self):
		self.commit()
	
	def __getattr__(self, name):
		return getattr(self.stream, name)
	
	def close(self):
		self.commit()
		self.stream.close()
	
	def commit(self):
		if self.buf:
			if self.data_encoding:
				self.buf = self.buf.decode(self.data_encoding, self.errors)
			if self.file_encoding:
				self.buf = self.buf.encode(self.file_encoding, self.errors)
			self.stream.write(self.buf)
			self.buf = ""
	
	def write(self, data):
		data = data.replace(self.linesep_in, "\n")
		for char in data:
			if char == "\r":
				while self.buf and not self.buf.endswith(self.linesep_out):
					self.buf = self.buf[:-1]
			else:
				if char == "\n":
					self.buf += self.linesep_out
					self.commit()
				else:
					self.buf += char


class LineCache():
	
	""" When written to it, stores only the last n + 1 lines and
		returns only the last n non-empty lines when read. """
	
	def __init__(self, maxlines=1):
		self.clear()
		self.maxlines = maxlines
	
	def clear(self):
		self.cache = [""]
	
	def flush(self):
		pass
	
	def read(self, triggers=None):
		lines = [""]
		for line in self.cache:
			read = True
			if triggers:
				for trigger in triggers:
					if trigger.lower() in line.lower():
						read = False
						break
			if read and line:
				lines.append(line)
		return "\n".join(filter(lambda line: line, lines)[-self.maxlines:])
	
	def write(self, data):
		for char in data:
			if char == "\r":
				self.cache[-1] = ""
			elif char == "\n":
				self.cache.append("")
			else:
				self.cache[-1] += char
		self.cache = (filter(lambda line: line, self.cache[:-1]) + 
					  self.cache[-1:])[-self.maxlines - 1:]


class WPopen(sp.Popen):
	
	def __init__(self, *args, **kwargs):
		sp.Popen.__init__(self, *args, **kwargs)
		self._seekpos = 0
		self._stdout = kwargs["stdout"]
		self.after = None
		self.before = None
		self.exitstatus = None
		self.logfile_read = None
		self.match = None
		self.maxlen = 80
		self.timeout = 30
	
	def isalive(self):
		self.exitstatus = self.poll()
		return self.exitstatus is None
	
	def expect(self, patterns, timeout=-1):
		if not isinstance(patterns, list):
			patterns = [patterns]
		if timeout == -1:
			timeout = self.timeout
		if timeout is not None:
			end = time() + timeout
		while timeout is None or time() < end:
			self._stdout.seek(self._seekpos)
			buf = self._stdout.read()
			self._seekpos += len(buf)
			if not buf and not self.isalive():
				self.match = wexpect.EOF("End Of File (EOF) in expect() - dead child process")
				if wexpect.EOF in patterns:
					return self.match
				raise self.match
			if buf and self.logfile_read:
				self.logfile_read.write(buf)
			for pattern in patterns:
				if isinstance(pattern, basestring) and pattern in buf:
					offset = buf.find(pattern)
					self.after = buf[offset:]
					self.before = buf[:offset]
					self.match = buf[offset:offset + len(pattern)]
					return self.match
			sleep(.01)
		if timeout is not None:
			self.match = wexpect.TIMEOUT("Timeout exceeded in expect()")
			if wexpect.TIMEOUT in patterns:
				return self.match
			raise self.match
	
	def send(self, s):
		self.stdin.write(s)
		self._stdout.seek(self._seekpos)
		buf = self._stdout.read()
		self._seekpos += len(buf)
		if buf and self.logfile_read:
			self.logfile_read.write(buf)
	
	def terminate(self, force=False):
		sp.Popen.terminate(self)


class Worker():

	def __init__(self, owner=None):
		"""
		Create and return a new worker instance.
		"""
		self.owner = owner # owner should be a wxFrame or similar
		if sys.platform == "win32":
			self.data_encoding = aliases.get(str(windll.kernel32.GetACP()), 
											 "ascii")
		else:
			self.data_encoding = enc
		self.dispcal_create_fast_matrix_shaper = False
		self.dispread_after_dispcal = False
		self.finished = True
		self.interactive = False
		self.lastmsg_discard = re.compile("[\\*\\.]+")
		self.options_colprof = []
		self.options_dispcal = []
		self.options_dispread = []
		self.options_targen = []
		self.recent_discard = re.compile("^\\s*(?:Adjusted )?(Current|[Tt]arget) (?:Brightness|50% Level|white|(?:Near )?[Bb]lack|(?:advertised )?gamma) .+|^Gamma curve .+|^Display adjustment menu:|^Press|^\\d\\).+|^(?:1%|Black|Red|Green|Blue|White)\\s+=.+|^\\s*patch \\d+ of \\d+.*|^\\s*point \\d+.*|^\\s*Added \\d+/\\d+|[\\*\\.]+|\\s*\\d*%?", re.I)
		self.subprocess_abort = False
		self.tempdir = None
		self.thread_abort = False
		self.triggers = []
		self.clear_argyll_info()
		self.clear_cmd_output()
	
	def add_measurement_features(self, args):
		args += ["-d" + self.get_display()]
		args += ["-c%s" % getcfg("comport.number")]
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
		if self.argyll_version >= [1, 3, 0] and \
		   not instrument_features.get("spectral"):
			ccmx = getcfg("colorimeter_correction_matrix_file").split(":", 1)
			if ccmx[0] == "AUTO":
				# TODO: implement auto selection based on available ccmx files 
				# and display/instrument combo
				ccmx = None
			elif len(ccmx) > 1 and ccmx[1]:
				ccmx = ccmx[1]
			else:
				ccmx = None
			if ccmx:
				result = check_file_isfile(ccmx)
				if isinstance(result, Exception):
					return result
				if not result:
					return None
				tempdir = self.create_tempdir()
				if not tempdir or isinstance(tempdir, Exception):
					return tempdir
				ccmxcopy = os.path.join(tempdir, 
										getcfg("profile.name.expanded") + 
										".ccmx")
				if not os.path.isfile(ccmxcopy):
					try:
						# Copy ccmx to profile dir
						shutil.copyfile(ccmx, ccmxcopy) 
					except Exception, exception:
						return Error(lang.getstr("error.copy_failed", 
												 (ccmx, ccmxcopy)) + 
												 "\n\n" + 
												 safe_unicode(exception))
					result = check_file_isfile(ccmxcopy)
					if isinstance(result, Exception):
						return result
					if not result:
						return None
				args += ["-X"]
				args += [ccmx]
		if (getcfg("drift_compensation.blacklevel") or 
			getcfg("drift_compensation.whitelevel")) and \
		   self.argyll_version >= [1, 3, 0]:
			args += ["-I"]
			if getcfg("drift_compensation.blacklevel"):
				args[-1] += "b"
			if getcfg("drift_compensation.whitelevel"):
				args[-1] += "w"
		return True
	
	def get_needs_no_sensor_cal(self):
		instrument_features = self.get_instrument_features()
		# TTBD/FIXME: Skipping of sensor calibration can't be done in
		# emissive mode (see Argyll source spectro/ss.c, around line 40)
		return instrument_features and \
			   (not instrument_features.get("sensor_cal") or 
			    (getcfg("allow_skip_sensor_cal") and 
			     self.dispread_after_dispcal and 
			     (instrument_features.get("skip_sensor_cal") or test) and 
				 self.argyll_version >= [1, 1, 0]))
	
	def check_display_conf_oy_compat(self, display_no):
		""" Check the screen configuration for oyranos-monitor compatibility 
		
		oyranos-monitor works off screen coordinates, so it will not handle 
		overlapping screens (like separate X screens, which will usually 
		have the same x, y coordinates)!
		So, oyranos-monitor can only be used if:
		- The wx.Display count is > 1 which means NOT separate X screens
		  OR if we use the 1st screen
		- The screens don't overlap
		
		"""
		oyranos = False
		if wx.Display.GetCount() > 1 or display_no == 1:
			oyranos = True
			for display_rect_1 in self.display_rects:
				for display_rect_2 in self.display_rects:
					if display_rect_1 is not display_rect_2:
						if display_rect_1.Intersects(display_rect_2):
							oyranos = False
							break
				if not oyranos:
					break
		return oyranos
	
	def clear_argyll_info(self):
		"""
		Clear Argyll CMS version, detected displays and instruments.
		"""
		self.argyll_bin_dir = None
		self.argyll_version = [0, 0, 0]
		self.argyll_version_string = ""
		self._displays = []
		self.display_edid = []
		self.display_names = []
		self.display_rects = []
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
		self.recent = FilteredStream(LineCache(maxlines=3), self.data_encoding, 
									 discard=self.recent_discard,
									 triggers=self.triggers)
		self.lastmsg = FilteredStream(LineCache(), self.data_encoding, 
									  discard=self.lastmsg_discard,
									  triggers=self.triggers)

	def create_tempdir(self):
		""" Create a temporary working directory and return its path. """
		if not self.tempdir or not os.path.isdir(self.tempdir):
			# we create the tempdir once each calibrating/profiling run 
			# (deleted by 'wrapup' after each run)
			if verbose >= 2:
				if not self.tempdir:
					msg = "there is none"
				else:
					msg = "the previous (%s) no longer exists" % self.tempdir
				safe_print(appname + ": Creating a new temporary directory "
						   "because", msg)
			try:
				self.tempdir = tempfile.mkdtemp(prefix=appname + u"-")
			except Exception, exception:
				self.tempdir = None
				return Error("Error - couldn't create temporary directory: " + 
							 safe_str(exception))
		return self.tempdir

	def enumerate_displays_and_ports(self, silent=False, check_lut_access=True):
		"""
		Run Argyll dispcal to enumerate the available displays and ports.
		
		Also sets Argyll version number, availability of certain options
		like black point rate, and checks LUT access for each display.
		
		"""
		if (silent and check_argyll_bin()) or (not silent and 
											   check_set_argyll_bin()):
			displays = []
			instruments = []
			lut_access = []
			if verbose >= 1 and not silent:
				safe_print(lang.getstr("enumerating_displays_and_comports"))
			if hasattr(wx.GetApp(), "progress_dlg") and \
			   wx.GetApp().progress_dlg.IsShownOnScreen():
				wx.GetApp().progress_dlg.Pulse(
					lang.getstr("enumerating_displays_and_comports"))
			cmd = get_argyll_util("dispcal") or get_argyll_util("dispwin")
			argyll_bin_dir = os.path.dirname(cmd)
			if (argyll_bin_dir != self.argyll_bin_dir):
				self.argyll_bin_dir = argyll_bin_dir
				log(self.argyll_bin_dir)
			result = self.exec_cmd(cmd, ["-?"], capture_output=True, 
								   skip_scripts=True, silent=True, 
								   log_output=False)
			if isinstance(result, Exception):
				safe_print(result)
			arg = None
			defaults["calibration.black_point_rate.enabled"] = 0
			n = -1
			self.display_rects = []
			for line in self.output:
				if isinstance(line, unicode):
					n += 1
					line = line.strip()
					if n == 0 and "version" in line.lower():
						argyll_version = line[line.lower().find("version")+8:]
						argyll_version_string = argyll_version
						if (argyll_version_string != self.argyll_version_string):
							self.argyll_version_string = argyll_version_string
							log("Argyll CMS " + self.argyll_version_string)
						config.defaults["copyright"] = ("Created with %s %s "
														"and Argyll CMS %s" % 
														(appname, version, 
														 argyll_version))
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
								display = "%s @ %s, %s, %sx%s" % match[0]
								if " ".join(value.split()[-2:]) == \
								   "(Primary Display)":
									display += u" [PRIMARY]"
								displays.append(display)
								self.display_rects.append(
									wx.Rect(*[int(item) for item in match[0][1:]]))
						elif arg == "-c":
							value = value.split(None, 1)
							if len(value) > 1:
								value = value[1].strip("()")
							else:
								value = value[0]
							value = remove_vendor_names(value)
							instruments.append(value)
			if test:
				inames = all_instruments.keys()
				inames.sort()
				for iname in inames:
					if not iname in instruments:
						instruments.append(iname)
			if verbose >= 1 and not silent: safe_print(lang.getstr("success"))
			if hasattr(wx.GetApp(), "progress_dlg") and \
			   wx.GetApp().progress_dlg.IsShownOnScreen():
				wx.GetApp().progress_dlg.Pulse(
					lang.getstr("success"))
			if instruments != self.instruments:
				self.instruments = instruments
			if displays != self._displays:
				self._displays = list(displays)
				self.display_edid = []
				self.display_names = []
				if sys.platform == "win32":
					monitors = []
					for monitor in win32api.EnumDisplayMonitors(None, None):
						monitors.append(win32api.GetMonitorInfo(monitor[0]))
				for i, display in enumerate(displays):
					# Make sure we have nice descriptions
					desc = []
					if sys.platform == "win32":
						# Get monitor description using win32api
						n = 0
						device = None
						while True:
							try:
								# The ordering will work as long
								# as Argyll continues using
								# EnumDisplayMonitors
								device = win32api.EnumDisplayDevices(
									monitors[i]["Device"], n)
							except pywintypes.error:
								break
							else:
								if device.StateFlags & \
								   DD_ATTACHED_TO_DESKTOP:
									break
							n += 1
						if device:
							desc.append(device.DeviceString.decode(fs_enc, "replace"))
					# Get monitor descriptions from EDID
					try:
						edid = get_edid(i)
					except (TypeError, ValueError, WMIConnectionAttributeError):
						edid = {}
					self.display_edid.append(edid)
					if edid:
						manufacturer = edid.get("manufacturer", "").split()
						monitor = edid.get("monitor_name")
						if monitor and not monitor in "".join(desc):
							desc = [monitor]
						##if manufacturer and (not monitor or 
											 ##not monitor.lower().startswith(manufacturer[0].lower())):
							##desc.insert(0, manufacturer[0])
					if desc and desc[-1] not in display:
						# Only replace the description if it not already
						# contains the monitor model
						displays[i] = " @".join([" ".join(desc), 
												 display.split("@")[1]])
					self.display_names.append(displays[i].split("@")[0].strip())
				self.displays = displays
				if check_lut_access:
					dispwin = get_argyll_util("dispwin")
					for i, disp in enumerate(displays):
						if verbose >= 1 and not silent:
							safe_print(lang.getstr("checking_lut_access", (i + 1)))
						if hasattr(wx.GetApp(), "progress_dlg") and \
						   wx.GetApp().progress_dlg.IsShownOnScreen():
							wx.GetApp().progress_dlg.Pulse(
								lang.getstr("checking_lut_access", (i + 1)))
						# Load test.cal
						result = self.exec_cmd(dispwin, ["-d%s" % (i +1), "-c", 
														 get_data_path("test.cal")], 
											   capture_output=True, 
											   skip_scripts=True, 
											   silent=True)
						if isinstance(result, Exception):
							safe_print(result)
						# Check if LUT == test.cal
						result = self.exec_cmd(dispwin, ["-d%s" % (i +1), "-V", 
														 get_data_path("test.cal")], 
											   capture_output=True, 
											   skip_scripts=True, 
											   silent=True)
						if isinstance(result, Exception):
							safe_print(result)
						retcode = -1
						for line in self.output:
							if line.find("IS loaded") >= 0:
								retcode = 0
								break
						# Reset LUT & load profile cal (if any)
						result = self.exec_cmd(dispwin, ["-d%s" % (i + 1), "-c", 
														 "-L"], 
											   capture_output=True, 
											   skip_scripts=True, 
											   silent=True)
						if isinstance(result, Exception):
							safe_print(result)
						lut_access += [retcode == 0]
						if verbose >= 1 and not silent:
							if retcode == 0:
								safe_print(lang.getstr("success"))
							else:
								safe_print(lang.getstr("failure"))
						if hasattr(wx.GetApp(), "progress_dlg") and \
						   wx.GetApp().progress_dlg.IsShownOnScreen():
							wx.GetApp().progress_dlg.Pulse(
								lang.getstr("success" if retcode == 0 else
											"failure"))
					self.lut_access = lut_access
		elif silent or not check_argyll_bin():
			self.clear_argyll_info()

	def exec_cmd(self, cmd, args=[], capture_output=False, 
				 display_output=False, low_contrast=True, skip_scripts=False, 
				 silent=False, parent=None, asroot=False, log_output=True,
				 title=appname, shell=False, working_dir=None):
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
		title = Title for sudo dialog
		working_dir = Working directory. If None, will be determined from
		absulte path of last argument and last argument will be set to only 
		the basename. If False, no working dir will be used and file arguments
		not changed.
		"""
		if parent is None:
			parent = self.owner
		if not capture_output:
			capture_output = not sys.stdout.isatty()
		fn = None
		self.clear_cmd_output()
		if None in [cmd, args]:
			if verbose >= 1 and not silent:
				safe_print(lang.getstr("aborted"), fn=fn)
			return False
		cmdname = os.path.splitext(os.path.basename(cmd))[0]
		if args and args[-1].find(os.path.sep) > -1:
			working_basename = os.path.basename(args[-1])
			if cmdname in (get_argyll_utilname("dispwin"),
						   "oyranos-monitor"):
				# Last arg is without extension, only for dispwin we need to 
				# strip it
				working_basename = os.path.splitext(working_basename)[0]
			if working_dir is None:
				working_dir = os.path.dirname(args[-1])
			if working_dir is not False and not os.path.isdir(working_dir):
				working_dir = None
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
		if working_dir:
			for i in range(len(cmdline)):
				item = cmdline[i]
				if i > 0 and (item.find(os.path.sep) > -1 and 
							  os.path.dirname(item) == working_dir):
					# Strip the path from all items in the working dir
					if sys.platform == "win32" and \
					   re.search("[^\x00-\x7f]", 
								 os.path.basename(item)) and os.path.exists(item):
						# Avoid problems with encoding
						item = win32api.GetShortPathName(item) 
					cmdline[i] = os.path.basename(item)
		sudo = None
		if cmdname == get_argyll_utilname("dispwin") and ("-Sl" in args or 
														  "-Sn" in args):
			asroot = True
		# Run commands through wexpect.spawn instead of subprocess.Popen if
		# all of these conditions apply:
		# - command is dispcal, dispread or spotread
		# - arguments are not empty
		# - actual user interaction in a terminal is not needed OR
		#   we are on Windows and running without a console
		measure_cmds = (get_argyll_utilname("dispcal"), 
						get_argyll_utilname("dispread"), 
						get_argyll_utilname("spotread"))
		process_cmds = (get_argyll_utilname("colprof"),
						get_argyll_utilname("targen"))
		interact = args and not "-?" in args and cmdname in measure_cmds + process_cmds
		self.measure = not "-?" in args and cmdname in measure_cmds
		if self.measure:
			# TTBD/FIXME: Skipping of sensor calibration can't be done in
			# emissive mode (see Argyll source spectro/ss.c, around line 40)
			skip_sensor_cal = not self.get_instrument_features().get("sensor_cal") ##or \
							  ##"-N" in args
		self.dispcal = cmdname == get_argyll_utilname("dispcal")
		self.needs_user_interaction = args and (self.dispcal and not "-?" in args and 
									   not "-E" in args and not "-R" in args and 
									   not "-m" in args and not "-r" in args and 
									   not "-u" in args) or (self.measure and 
															 not skip_sensor_cal)
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
				stdin = tempfile.SpooledTemporaryFile()
				stdin.write((self.pwd or "").encode(enc, "replace") + os.linesep)
				stdin.seek(0)
				sudoproc = sp.Popen([sudo, "-S", "echo", "OK"], 
									stdin=stdin, stdout=sp.PIPE, 
									stderr=sp.PIPE)
				stdout, stderr = sudoproc.communicate()
				if not stdin.closed:
					stdin.close()
				if not "OK" in stdout:
					# ask for password
					dlg = ConfirmDialog(
						parent, title=title, 
						msg=lang.getstr("dialog.enter_password"), 
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
						stdin = tempfile.SpooledTemporaryFile()
						stdin.write(pwd.encode(enc, "replace") + os.linesep)
						stdin.seek(0)
						sudoproc = sp.Popen([sudo, "-S", "echo", "OK"], 
											stdin=stdin, 
											stdout=sp.PIPE, stderr=sp.PIPE)
						stdout, stderr = sudoproc.communicate()
						if not stdin.closed:
							stdin.close()
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
				if not interact:
					cmdline.insert(1, "-S")
			except Exception, exception:
				safe_print("Warning - execution as root not possible:", 
						   safe_unicode(exception))
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
																"safe_asciize"))
					cmdfiles.write('pushd "%~dp0"\n'.encode(enc, "safe_asciize"))
					if cmdname in (get_argyll_utilname("dispcal"), 
								   get_argyll_utilname("dispread")):
						cmdfiles.write("color 07\n")
				else:
					context.write(('PATH=%s:$PATH\n' % 
								   os.path.dirname(cmd)).encode(enc, 
																"safe_asciize"))
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
					cmdname).encode(enc, "safe_asciize") + "\n")
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
						   safe_unicode(exception))
		cmdline = [arg.encode(fs_enc) for arg in cmdline]
		working_dir = None if not working_dir else working_dir.encode(fs_enc)
		try:
			if not self.measure and self.argyll_version >= [1, 2]:
				# Argyll tools will no longer respond to keys
				if debug:
					safe_print("[D] Setting ARGYLL_NOT_INTERACTIVE 1")
				putenvu("ARGYLL_NOT_INTERACTIVE", "1")
			elif "ARGYLL_NOT_INTERACTIVE" in os.environ:
				del os.environ["ARGYLL_NOT_INTERACTIVE"]
			if debug:
				safe_print("[D] argyll_version", self.argyll_version)
				safe_print("[D] ARGYLL_NOT_INTERACTIVE", 
						   os.environ.get("ARGYLL_NOT_INTERACTIVE"))
			if sys.platform == "win32":
				startupinfo = sp.STARTUPINFO()
				startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
				startupinfo.wShowWindow = sp.SW_HIDE
			else:
				startupinfo = None
			if not interact:
				if silent:
					stderr = sp.STDOUT
				else:
					stderr = tempfile.SpooledTemporaryFile()
				if capture_output:
					stdout = tempfile.SpooledTemporaryFile()
				elif sys.stdout.isatty():
					stdout = sys.stdout
				else:
					stdout = sp.PIPE
				if sudo:
					stdin = tempfile.SpooledTemporaryFile()
					stdin.write((self.pwd or "").encode(enc, "replace") + os.linesep)
					stdin.seek(0)
				elif sys.stdin.isatty():
					stdin = None
				else:
					stdin = sp.PIPE
			else:
				kwargs = dict(timeout=30, cwd=working_dir,
							  env=os.environ)
				if sys.platform == "win32":
					kwargs["codepage"] = windll.kernel32.GetACP()
				stderr = StringIO()
				stdout = StringIO()
				if log_output:
					if sys.stdout.isatty():
						logfile = LineBufferedStream(
								  FilteredStream(safe_print, self.data_encoding,
												 discard="", 
												 linesep_in="\n", 
												 triggers=[]))
					else:
						logfile = LineBufferedStream(
								  FilteredStream(log, self.data_encoding,
												 discard="",
												 linesep_in="\n", 
												 triggers=[]))
					logfile = Files((logfile, stdout, self.recent,
									 self.lastmsg))
				else:
					logfile = Files((stdout, self.recent,
									 self.lastmsg))
				if ((self.interactive or (test and not "-?" in args)) and 
					getattr(self, "terminal", None)):
					logfile = Files((FilteredStream(self.terminal,
													discard="",
													triggers=self.triggers), 
									logfile))
			if sys.platform == "win32" and working_dir:
				working_dir = win32api.GetShortPathName(working_dir)
			logfn = log
			tries = 1
			while tries > 0:
				if interact:
					if self.argyll_version >= [1, 2] and USE_WPOPEN and \
					   os.environ.get("ARGYLL_NOT_INTERACTIVE"):
						self.subprocess = WPopen(" ".join(cmdline) if shell else
												 cmdline, stdin=sp.PIPE, 
												 stdout=tempfile.SpooledTemporaryFile(), 
												 stderr=sp.STDOUT, 
												 shell=shell, cwd=working_dir, 
												 startupinfo=startupinfo)
					else:
						self.subprocess = wexpect.spawn(cmdline[0], cmdline[1:], 
														**kwargs)
						if debug or (test and not "-?" in args):
							self.subprocess.interact()
					self.subprocess.logfile_read = logfile
					if self.subprocess.isalive():
						try:
							if self.measure:
								self.subprocess.expect(["Esc or Q", "ESC or Q"])
								msg = self.recent.read()
								lastmsg = self.lastmsg.read().strip()
								if "key to continue" in lastmsg.lower() and \
								   "place instrument on test window" in \
								   "".join(msg.splitlines()[-2:-1]).lower():
									self.recent.clear()
									if not "-F" in args or \
									  (not self.dispcal and
									   self.dispread_after_dispcal):
										# Allow the user to move the terminal 
										# window if using black background, 
										# otherwise send space key to start
										# measurements right away
										if sys.platform != "win32":
											sleep(.5)
										if self.subprocess.isalive():
											if debug or test:
												safe_print('Sending SPACE key')
											self.subprocess.send(" ")
								if self.needs_user_interaction and \
								   sys.platform == "darwin":
									# On the Mac dispcal's test window
									# hides the cursor and steals focus
									start_new_thread(mac_app_activate, 
													 (1, appname if isapp 
													 	 else "Python"))
								retrycount = 0
								while self.subprocess.isalive():
									# Automatically retry on error, user can 
									# cancel via progress dialog
									self.subprocess.expect("key to retry:", 
														   timeout=None)
									if sys.platform != "win32":
										sleep(.5)
									if self.subprocess.isalive() and \
									   not "Sample read stopped at user request!" \
									   in self.recent.read() and \
									   not self.subprocess_abort:
										retrycount += 1
										logfile.write("\r\n%s: Retrying (%s)..." % 
													  (appname, retrycount))
										self.subprocess.send(" ")
							else:
								self.subprocess.expect(wexpect.EOF, 
													   timeout=None)
						except (wexpect.EOF, wexpect.TIMEOUT), exception:
							pass
					if self.subprocess.after not in (wexpect.EOF, 
													 wexpect.TIMEOUT):
						self.subprocess.expect(wexpect.EOF, timeout=None)
					# We need to call isalive() to set the exitstatus.
					# We can't use wait() because it might block in the
					# case of a timeout
					while self.subprocess.isalive():
						sleep(.1)
					self.retcode = self.subprocess.exitstatus
				else:
					self.subprocess = sp.Popen(" ".join(cmdline) if shell else
											   cmdline, stdin=stdin, 
											   stdout=stdout, stderr=stderr, 
											   shell=shell, cwd=working_dir, 
											   startupinfo=startupinfo)
					self.retcode = self.subprocess.wait()
					if stdin and not getattr(stdin, "closed", True):
						stdin.close()
				if self.is_working() and self.subprocess_abort and \
				   self.retcode == 0:
					self.retcode = -1
				self.subprocess = None
				tries -= 1
				if not silent:
					stderr.seek(0)
					errors = stderr.readlines()
					if not capture_output or stderr is not stdout:
						stderr.close()
					if len(errors):
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
								self.errors += [line.decode(enc, "replace")]
						if len(self.errors):
							errstr = "".join(self.errors).strip()
							safe_print(errstr, fn=fn)
					if tries > 0 and not interact:
						stderr = tempfile.SpooledTemporaryFile()
				if capture_output or interact:
					stdout.seek(0)
					self.output = [re.sub("^\.{4,}\s*$", "", 
										  line.decode(enc, "replace")) 
								   for line in stdout.readlines()]
					stdout.close()
					if len(self.output) and log_output:
						if not interact:
							logfn = log if silent else safe_print
							logfn("".join(self.output).strip())
						if display_output and self.owner and \
						   hasattr(self.owner, "infoframe"):
							wx.CallAfter(self.owner.infoframe.Show)
					if tries > 0 and not interact:
						stdout = tempfile.SpooledTemporaryFile()
		except Exception, exception:
			if debug:
				safe_print('[D] working_dir:', working_dir)
			errmsg = (" ".join(cmdline).decode(fs_enc) + "\n" + 
					  safe_unicode(traceback.format_exc()))
			self.retcode = -1
			return Error(errmsg)
		if debug and not silent:
			safe_print("*** Returncode:", self.retcode)
		if self.retcode != 0:
			if interact and verbose >= 1 and not silent:
				safe_print(lang.getstr("aborted"), fn=fn)
			if interact and len(self.output):
				for i, line in enumerate(self.output):
					if line.startswith(cmdname + ": Error") and \
					   not "failed with 'User Aborted'" in line and \
					   not "test_crt returned error code 1" in line:
						# "test_crt returned error code 1" == user aborted
						return UnloggedError("".join(self.output[i:]))
			return False
		return True

	def generic_consumer(self, delayedResult, consumer, continue_next, *args, 
						 **kwargs):
		# consumer must accept result as first arg
		result = None
		exception = None
		try:
			result = delayedResult.get()
		except Exception, exception:
			result = Error(u"Error - delayedResult.get() failed: " + 
						   safe_unicode(traceback.format_exc()))
		if self.progress_start_timer.IsRunning():
			self.progress_start_timer.Stop()
		if hasattr(self, "progress_wnd") and (not continue_next or 
											  isinstance(result, Exception) or 
											  not result):
			self.progress_wnd.stop_timer()
			self.progress_wnd.MakeModal(False)
			# under Linux, destroying it here causes segfault
			self.progress_wnd.Hide()
		self.finished = True
		self.subprocess_abort = False
		self.thread_abort = False
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
		if n >= 0 and n < len(self.display_names):
			return self.display_names[n]
		return ""
	
	def update_display_name_manufacturer(self, ti3, display_name=None,
										 display_manufacturer=None, 
										 write=True):
		options_colprof = []
		if not display_name and not display_manufacturer:
			# Note: Do not mix'n'match display name and manufacturer from 
			# different sources
			for option in get_options_from_ti3(ti3)[1]:
				if option[0] == "M":
					display_name = option.split(None, 1)[-1][1:-1]
				elif option[0] == "A":
					display_manufacturer = option.split(None, 1)[-1][1:-1]
		if not display_name and not display_manufacturer:
			# Note: Do not mix'n'match display name and manufacturer from 
			# different sources
			edid = self.display_edid[max(0, min(len(self.displays), 
												getcfg("display.number") - 1))]
			display_name = edid.get("monitor_name")
			display_manufacturer = edid.get("manufacturer")
		if not display_name and not display_manufacturer:
			# Note: Do not mix'n'match display name and manufacturer from 
			# different sources
			display_name = self.get_display_name()
		if display_name:
			options_colprof.append("-M")
			options_colprof.append(display_name)
		if display_manufacturer:
			options_colprof.append("-A")
			options_colprof.append(display_manufacturer)
		if write:
			# Add dispcal and colprof arguments to ti3
			ti3 = add_options_to_ti3(ti3, self.options_dispcal, options_colprof)
			if ti3:
				ti3.write()
		return options_colprof
	
	def get_instrument_features(self):
		""" Return features of currently configured instrument """
		features = all_instruments.get(self.get_instrument_name(), {})
		if test_require_sensor_cal:
			features["sensor_cal"] = True
			features["skip_sensor_cal"] = False
		return features
	
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
		return not getattr(self, "finished", True)

	def prepare_colprof(self, profile_name=None, display_name=None,
						display_manufacturer=None):
		"""
		Prepare a colprof commandline.
		
		All options are read from the user configuration.
		Profile name and display name can be ovverridden by passing the
		corresponding arguments.
		
		"""
		profile_save_path = self.create_tempdir()
		if not profile_save_path or isinstance(profile_save_path, Exception):
			return profile_save_path, None
		# Check directory and in/output file(s)
		result = check_create_dir(profile_save_path)
		if isinstance(result, Exception):
			return result, None
		if profile_name is None:
			profile_name = getcfg("profile.name.expanded")
		inoutfile = os.path.join(profile_save_path, 
								 make_argyll_compatible_path(profile_name))
		if not os.path.exists(inoutfile + ".ti3"):
			return Error(lang.getstr("error.measurement.file_missing", 
									 inoutfile + ".ti3")), None
		if not os.path.isfile(inoutfile + ".ti3"):
			return Error(lang.getstr("error.measurement.file_notfile", 
									 inoutfile + ".ti3")), None
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
		args += ["-C"]
		args += [getcfg("copyright").encode("ASCII", "asciize")]
		if getcfg("extra_args.colprof").strip():
			args += parse_argument_string(getcfg("extra_args.colprof"))
		options_dispcal = None
		if "-d3" in self.options_targen:
			# only add display desc and dispcal options if creating RGB profile
			options_dispcal = self.options_dispcal
			if len(self.displays):
				args.extend(
					self.update_display_name_manufacturer(inoutfile + ".ti3", 
														  display_name,
														  display_manufacturer, 
														  write=False))
		self.options_colprof = list(args)
		args += ["-D"]
		args += [profile_name]
		args += [inoutfile]
		# Add dispcal and colprof arguments to ti3
		ti3 = add_options_to_ti3(inoutfile + ".ti3", options_dispcal, 
								 self.options_colprof)
		if ti3:
			ti3.write()
		return cmd, args

	def prepare_dispcal(self, calibrate=True, verify=False, dry_run=False):
		"""
		Prepare a dispcal commandline.
		
		All options are read from the user configuration.
		You can choose if you want to calibrate and/or verify by passing 
		the corresponding arguments.
		
		"""
		cmd = get_argyll_util("dispcal")
		args = []
		args += ["-v2"] # verbose
		if getcfg("argyll.debug"):
			args += ["-D6"]
		result = self.add_measurement_features(args)
		if isinstance(result, Exception):
			return result, None
		if not result:
			return None, None
		if calibrate:
			args += ["-q" + getcfg("calibration.quality")]
			profile_save_path = self.create_tempdir()
			if not profile_save_path or isinstance(profile_save_path, Exception):
				return profile_save_path, None
			# Check directory and in/output file(s)
			result = check_create_dir(profile_save_path)
			if isinstance(result, Exception):
				return result, None
			inoutfile = os.path.join(profile_save_path, 
									 make_argyll_compatible_path(getcfg("profile.name.expanded")))
			if getcfg("profile.update") or \
			   self.dispcal_create_fast_matrix_shaper:
				args += ["-o"]
			if getcfg("calibration.update") and not dry_run:
				cal = getcfg("calibration.file")
				calcopy = os.path.join(inoutfile + ".cal")
				filename, ext = os.path.splitext(cal)
				ext = ".cal"
				cal = filename + ext
				if ext.lower() == ".cal":
					result = check_cal_isfile(cal)
					if isinstance(result, Exception):
						return result, None
					if not result:
						return None, None
					if not os.path.exists(calcopy):
						try:
							# Copy cal to profile dir
							shutil.copyfile(cal, calcopy) 
						except Exception, exception:
							return Error(lang.getstr("error.copy_failed", 
													 (cal, calcopy)) + 
													 "\n\n" + 
													 safe_unicode(exception)), None
						result = check_cal_isfile(calcopy)
						if isinstance(result, Exception):
							return result, None
						if not result:
							return None, None
						cal = calcopy
				else:
					rslt = extract_fix_copy_cal(cal, calcopy)
					if isinstance(rslt, ICCP.ICCProfileInvalidError):
						return Error(lang.getstr("profile.invalid") + 
									 "\n" + cal), None
					elif isinstance(rslt, Exception):
						return Error(lang.getstr("cal_extraction_failed") + 
									 "\n" + cal + "\n\n" + 
									 unicode(str(rslt),  enc, "replace")), None
					if not isinstance(rslt, list):
						return None, None
				if getcfg("profile.update"):
					profile_path = os.path.splitext(
						getcfg("calibration.file"))[0] + profile_ext
					result = check_profile_isfile(profile_path)
					if isinstance(result, Exception):
						return result, None
					if not result:
						return None, None
					profilecopy = os.path.join(inoutfile + profile_ext)
					if not os.path.exists(profilecopy):
						try:
							# Copy profile to profile dir
							shutil.copyfile(profile_path, profilecopy)
						except Exception, exception:
							return Error(lang.getstr("error.copy_failed", 
													   (profile_path, 
													    profilecopy)) + 
										   "\n\n" + safe_unicode(exception)), None
						result = check_profile_isfile(profilecopy)
						if isinstance(result, Exception):
							return result, None
						if not result:
							return None, None
				args += ["-u"]
		##if (calibrate and not getcfg("calibration.update")) or \
		   ##(not calibrate and verify):
		if calibrate or verify:
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
		if getcfg("extra_args.dispcal").strip():
			args += parse_argument_string(getcfg("extra_args.dispcal"))
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
		if not profile_save_path or isinstance(profile_save_path, Exception):
			return profile_save_path, None
		# Check directory and in/output file(s)
		result = check_create_dir(profile_save_path)
		if isinstance(result, Exception):
			return result, None
		inoutfile = os.path.join(profile_save_path, 
								 make_argyll_compatible_path(getcfg("profile.name.expanded")))
		if not os.path.exists(inoutfile + ".ti1"):
			filename, ext = os.path.splitext(getcfg("testchart.file"))
			result = check_file_isfile(filename + ext)
			if isinstance(result, Exception):
				return result, None
			try:
				if ext.lower() in (".icc", ".icm"):
					try:
						profile = ICCP.ICCProfile(filename + ext)
					except (IOError, ICCP.ICCProfileInvalidError), exception:
						return Error(lang.getstr("error.testchart.read", 
												 getcfg("testchart.file"))), None
					ti3 = StringIO(profile.tags.get("CIED", "") or 
								   profile.tags.get("targ", ""))
				elif ext.lower() == ".ti1":
					shutil.copyfile(filename + ext, inoutfile + ".ti1")
				else: # ti3
					try:
						ti3 = open(filename + ext, "rU")
					except Exception, exception:
						return Error(lang.getstr("error.testchart.read", 
												 getcfg("testchart.file"))), None
				if ext.lower() != ".ti1":
					ti3_lines = [line.strip() for line in ti3]
					ti3.close()
					if not "CTI3" in ti3_lines:
						return Error(lang.getstr("error.testchart.invalid", 
												 getcfg("testchart.file"))), None
					ti1 = open(inoutfile + ".ti1", "w")
					ti1.write(ti3_to_ti1(ti3_lines))
					ti1.close()
			except Exception, exception:
				return Error(lang.getstr("error.testchart.creation_failed", 
										 inoutfile + ".ti1") + "\n\n" + 
							 safe_unicode(exception)), None
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
				result = check_cal_isfile(cal)
				if isinstance(result, Exception):
					return result, None
				if not result:
					return None, None
				# Get dispcal options if present
				options_dispcal = get_options_from_cal(cal)[0]
				if not os.path.exists(calcopy):
					try:
						# Copy cal to temp dir
						shutil.copyfile(cal, calcopy)
					except Exception, exception:
						return Error(lang.getstr("error.copy_failed", 
												 (cal, calcopy)) + "\n\n" + 
									 safe_unicode(exception)), None
					result = check_cal_isfile(calcopy)
					if isinstance(result, Exception):
						return result, None
					if not result:
						return None, None
			else:
				# .icc / .icm
				result = check_profile_isfile(cal)
				if isinstance(result, Exception):
					return result, None
				if not result:
					return None, None
				try:
					profile = ICCP.ICCProfile(filename + ext)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					profile = None
				if profile:
					ti3 = StringIO(profile.tags.get("CIED", "") or 
								   profile.tags.get("targ", ""))
					# Get dispcal options if present
					options_dispcal = get_options_from_profile(profile)[0]
				else:
					ti3 = StringIO("")
				ti3_lines = [line.strip() for line in ti3]
				ti3.close()
				if not "CTI3" in ti3_lines:
					return Error(lang.getstr("error.cal_extraction", 
											 (cal))), None
				try:
					tmpcal = open(calcopy, "w")
					tmpcal.write(extract_cal_from_ti3(ti3_lines))
					tmpcal.close()
				except Exception, exception:
					return Error(lang.getstr("error.cal_extraction", (cal)) + 
								 "\n\n" + safe_unicode(exception)), None
			cal = calcopy
			if options_dispcal:
				self.options_dispcal = ["-" + arg for arg in options_dispcal]
		#
		# Make sure any measurement options are present
		if not self.options_dispcal:
			self.prepare_dispcal(dry_run=True)
		# strip options we may override (basically all the stuff which will be 
		# added by add_measurement_features)
		self.options_dispcal = filter(lambda arg: not arg[:2] in ("-F", "-H", 
																  "-I", "-P", 
																  "-V", "-X", 
																  "-d", "-c", 
																  "-p", "-y"), 
									  self.options_dispcal)
		self.add_measurement_features(self.options_dispcal)
		cmd = get_argyll_util("dispread")
		args = []
		args += ["-v"] # verbose
		if getcfg("argyll.debug"):
			args += ["-D6"]
		result = self.add_measurement_features(args)
		if isinstance(result, Exception):
			return result, None
		if not result:
			return None, None
		# TTBD/FIXME: Skipping of sensor calibration can't be done in
		# emissive mode (see Argyll source spectro/ss.c, around line 40)
		if getcfg("allow_skip_sensor_cal") and self.dispread_after_dispcal and \
		   (self.get_instrument_features().get("skip_sensor_cal") or test) and \
		   self.argyll_version >= [1, 1, 0]:
			args += ["-N"]
		if apply_calibration:
			args += ["-k"]
			args += [cal]
		if getcfg("extra_args.dispread").strip():
			args += parse_argument_string(getcfg("extra_args.dispread"))
		self.options_dispread = list(args)
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
		if getcfg("argyll.debug"):
			args += ["-E6"]
		args += ["-d" + self.get_display()]
		args += ["-c"]
		if cal is True:
			args += ["-L"]
		elif cal:
			result = check_cal_isfile(cal)
			if isinstance(result, Exception):
				return result, None
			if not result:
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
				result = check_profile_isfile(profile_path)
				if isinstance(result, Exception):
					return result, None
				if not result:
					return None, None
				try:
					profile = ICCP.ICCProfile(profile_path)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					return Error(lang.getstr("profile.invalid") + 
											 "\n" + profile_path), None
				if profile.profileClass != "mntr" or \
				   profile.colorSpace != "RGB":
					return Error(lang.getstr("profile.unsupported", 
											 (profile.profileClass, 
											  profile.colorSpace)) + 
								   "\n" + profile_path), None
				if install:
					if getcfg("profile.install_scope") != "u" and \
						(((sys.platform == "darwin" or 
						   (sys.platform != "win32" and 
							self.argyll_version >= [1, 1, 0])) and 
						  (os.geteuid() == 0 or which("sudo"))) or 
						 (sys.platform == "win32" and 
						  sys.getwindowsversion() >= (6, ) and 
						  self.argyll_version > [1, 1, 1]) or test):
							# -S option is broken on Linux with current Argyll 
							# releases
							args += ["-S" + getcfg("profile.install_scope")]
					args += ["-I"]
					if (sys.platform in ("win32", "darwin") or 
						fs_enc.upper() not in ("UTF8", "UTF-8")) and \
					   re.search("[^\x00-\x7f]", 
								 os.path.basename(profile_path)):
						# Copy to temp dir and give unique ASCII-only name to
						# avoid profile install issues
						tmp_dir = self.create_tempdir()
						if not tmp_dir or isinstance(tmp_dir, Exception):
							return tmp_dir, None
						# Check directory and in/output file(s)
						result = check_create_dir(tmp_dir)
						if isinstance(result, Exception):
							return result, None
						# profile name: 'display<n>-<hexmd5sum>.icc'
						profile_tmp_path = os.path.join(tmp_dir, "display" + 
														self.get_display() + 
														"-" + 
														md5(profile.data).hexdigest() + 
														profile_ext)
						shutil.copyfile(profile_path, profile_tmp_path)
						profile_path = profile_tmp_path
				args += [profile_path]
		return cmd, args

	def prepare_targen(self):
		"""
		Prepare a targen commandline.
		
		All options are read from the user configuration.
		
		"""
		path = self.create_tempdir()
		if not path or isinstance(path, Exception):
			return path, None
		# Check directory and in/output file(s)
		result = check_create_dir(path)
		if isinstance(result, Exception):
			return result, None
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
		if getcfg("tc_vrml_lab"):
			args += ['-w']
		if getcfg("tc_vrml_device"):
			args += ['-W']
		self.options_targen = list(args)
		args += [inoutfile]
		return cmd, args

	def progress_handler(self, event):
		if getattr(self, "subprocess_abort", False) or \
		   getattr(self, "thread_abort", False):
			self.progress_wnd.Pulse(lang.getstr("aborting"))
			return
		percentage = None
		msg = self.recent.read(FilteredStream.triggers)
		lastmsg = self.lastmsg.read(FilteredStream.triggers).strip()
		if re.match("\\s*\\d+%", lastmsg):
			# colprof
			try:
				percentage = int(self.lastmsg.read().strip("%"))
			except ValueError:
				pass
		elif re.match("Patch \\d+ of \\d+", lastmsg, re.I):
			# dispcal/dispread
			components = lastmsg.split()
			try:
				start = float(components[1])
				end = float(components[3])
			except ValueError:
				pass
			else:
				percentage = start / end * 100
		elif re.match("Added \\d+/\\d+", lastmsg, re.I):
			# targen
			components = lastmsg.lower().replace("added ", "").split("/")
			try:
				start = float(components[0])
				end = float(components[1])
			except ValueError:
				pass
			else:
				percentage = start / end * 100
		if not test and percentage and self.progress_wnd is getattr(self, "terminal", None):
			# We no longer need keyboard interaction, switch over to
			# progress dialog
			wx.CallAfter(self.swap_progress_wnds)
		if getattr(self.progress_wnd, "original_msg", None) and \
		   msg != self.progress_wnd.original_msg:
			self.progress_wnd.SetTitle(self.progress_wnd.original_msg)
			self.progress_wnd.original_msg = None
		if percentage:
			if "Setting up the instrument" in msg or "Commencing device calibration" in msg:
				self.recent.clear()
				msg = ""
			keepGoing, skip = self.progress_wnd.Update(math.ceil(percentage), 
													   msg + "\n" + 
													   lastmsg)
		else:
			if getattr(self.progress_wnd, "lastmsg", "") == msg or not msg:
				keepGoing, skip = self.progress_wnd.Pulse()
			else:
				keepGoing, skip = self.progress_wnd.Pulse(msg)
		if not keepGoing:
			if getattr(self, "subprocess", None) and \
			   not getattr(self, "subprocess_abort", False):
				if debug:
					log('[D] calling quit_terminate_cmd')
				self.subprocess_abort = True
				self.thread_abort = True
				delayedresult.startWorker(lambda result: None, 
										  self.quit_terminate_cmd)
				##wx.CallAfter(self.quit_terminate_cmd)
			elif not getattr(self, "thread_abort", False):
				if debug:
					log('[D] thread_abort')
				self.thread_abort = True
		if self.finished is True:
			return
		if not self.activated and self.progress_wnd.IsShownOnScreen() and \
		   (not wx.GetApp().IsActive() or not self.progress_wnd.IsActive()):
		   	self.activated = True
			self.progress_wnd.Raise()

	def progress_dlg_start(self, progress_title="", progress_msg="", 
						   parent=None, resume=False):
		if getattr(self, "progress_dlg", None) and not resume:
			self.progress_dlg.Destroy()
			self.progress_dlg = None
		if getattr(self, "progress_wnd", None) and \
		   self.progress_wnd is getattr(self, "terminal", None):
			self.terminal.stop_timer()
			self.terminal.Hide()
		if self.finished is True:
			return
		if getattr(self, "progress_dlg", None):
			self.progress_wnd = self.progress_dlg
			self.progress_wnd.MakeModal(True)
			self.progress_wnd.SetTitle(progress_title)
			self.progress_wnd.Update(0, progress_msg)
			self.progress_wnd.Resume()
			if not self.progress_wnd.IsShownOnScreen():
				self.progress_wnd.Show()
			self.progress_wnd.start_timer()
		else:
			# Set maximum to 101 to prevent the 'cancel' changing to 'close'
			# when 100 is reached
			self.progress_dlg = ProgressDialog(progress_title, progress_msg, 
											   maximum=101, 
											   parent=parent, 
											   handler=self.progress_handler,
											   keyhandler=self.terminal_key_handler)
			self.progress_wnd = self.progress_dlg
		self.progress_wnd.original_msg = progress_msg
	
	def quit_terminate_cmd(self):
		if debug:
			log('[D] safe_quit')
		##if getattr(self, "subprocess", None) and \
		   ##not getattr(self, "subprocess_abort", False) and \
		if getattr(self, "subprocess", None) and \
		   (hasattr(self.subprocess, "poll") and 
			self.subprocess.poll() is None) or \
		   (hasattr(self.subprocess, "isalive") and 
			self.subprocess.isalive()):
			if debug or test:
				log('User requested abort')
			##self.subprocess_abort = True
			##self.thread_abort = True
			try:
				if self.measure and hasattr(self.subprocess, "send"):
					try:
						if debug or test:
							log('Sending ESC (1)')
						self.subprocess.send("\x1b")
						ts = time()
						while getattr(self, "subprocess", None) and \
						   self.subprocess.isalive():
							if time() > ts + 9 or \
							   "esc or q" in self.lastmsg.read().lower():
								break
							sleep(1)
						if getattr(self, "subprocess", None) and \
						   self.subprocess.isalive():
							if debug or test:
								log('Sending ESC (2)')
							self.subprocess.send("\x1b")
							sleep(.5)
					except Exception, exception:
						if debug:
							log(traceback.format_exc())
				if getattr(self, "subprocess", None) and \
				   (hasattr(self.subprocess, "poll") and 
					self.subprocess.poll() is None) or \
				   (hasattr(self.subprocess, "isalive") and 
					self.subprocess.isalive()):
					if debug or test:
						log('Trying to terminate subprocess...')
					self.subprocess.terminate()
					ts = time()
					while getattr(self, "subprocess", None) and \
					   hasattr(self.subprocess, "isalive") and \
					   self.subprocess.isalive():
						if time() > ts + 3:
							break
						sleep(.25)
					if getattr(self, "subprocess", None) and \
					   hasattr(self.subprocess, "isalive") and \
					   self.subprocess.isalive():
						if debug or test:
							log('Trying to terminate subprocess forcefully...')
						self.subprocess.terminate(force=True)
			except Exception, exception:
				if debug:
					log(traceback.format_exc())
			if debug:
				log('[D] end try')
		elif debug:
			log('[D] subprocess: %r' % getattr(self, "subprocess", None))
			log('[D] subprocess_abort: %r' % getattr(self, "subprocess_abort", 
													 False))
			if getattr(self, "subprocess", None):
				log('[D] subprocess has poll: %r' % hasattr(self.subprocess, 
															"poll"))
				if hasattr(self.subprocess, "poll"):
					log('[D] subprocess.poll(): %r' % self.subprocess.poll())
				log('[D] subprocess has isalive: %r' % hasattr(self.subprocess, 
															   "isalive"))
				if hasattr(self.subprocess, "isalive"):
					log('[D] subprocess.isalive(): %r' % self.subprocess.isalive())

	def start(self, consumer, producer, cargs=(), ckwargs=None, wargs=(), 
			  wkwargs=None, progress_title=appname, progress_msg="", 
			  parent=None, progress_start=100, resume=False, 
			  continue_next=False):
		"""
		Start a worker process.
		
		Also show a progress dialog while the process is running.
		
		consumer         consumer function.
		producer         producer function.
		cargs            consumer arguments.
		ckwargs          consumer keyword arguments.
		wargs            producer arguments.
		wkwargs          producer keyword arguments.
		progress_title   progress dialog title. Defaults to '%s'.
		progress_msg     progress dialog message. Defaults to ''.
		progress_start   show progress dialog after delay (ms).
		resume           resume previous progress dialog (elapsed time etc).
		continue_next    do not hide progress dialog after producer finishes.
		
		""" % appname
		if ckwargs is None:
			ckwargs = {}
		if wkwargs is None:
			wkwargs = {}
		while self.is_working():
			sleep(.25) # wait until previous worker thread finishes
		if hasattr(self.owner, "stop_timers"):
			self.owner.stop_timers()
		if not parent:
			parent = self.owner
		if progress_start < 100:
			progress_start = 100
		self.resume = resume
		if self.interactive or test:
			self.progress_start_timer = wx.Timer()
			if getattr(self, "progress_wnd", None) and \
			   self.progress_wnd is getattr(self, "progress_dlg", None):
				self.progress_dlg.Destroy()
				self.progress_dlg = None
			if progress_msg and progress_title == appname:
				progress_title = progress_msg
			if getattr(self, "terminal", None):
				self.progress_wnd = self.terminal
				if not resume:
					self.progress_wnd.console.SetValue("")
				self.progress_wnd.stop_timer()
				self.progress_wnd.start_timer()
				self.progress_wnd.SetTitle(progress_title)
				self.progress_wnd.Show()
				if resume:
					self.progress_wnd.console.ScrollLines(
						self.progress_wnd.console.GetNumberOfLines())
			else:
				self.terminal = SimpleTerminal(parent, title=progress_title,
											   handler=self.progress_handler,
											   keyhandler=self.terminal_key_handler)
				self.progress_wnd = self.terminal
		else:
			if not progress_msg:
				progress_msg = lang.getstr("please_wait")
			# Show the progress dialog after a delay
			self.progress_start_timer = wx.CallLater(progress_start, 
													 self.progress_dlg_start, 
													 progress_title, 
													 progress_msg, parent,
													 resume)
		self.activated = False
		self.finished = False
		self.subprocess_abort = False
		self.thread_abort = False
		self.thread = delayedresult.startWorker(self.generic_consumer, 
												producer, [consumer, 
														   continue_next] + 
												list(cargs), ckwargs, wargs, 
												wkwargs)
		return True
	
	def swap_progress_wnds(self):
		parent = self.terminal.GetParent()
		title = self.terminal.GetTitle()
		self.progress_dlg_start(title, "", parent, self.resume)
	
	def terminal_key_handler(self, event):
		keycode = None
		if event.GetEventType() in (wx.EVT_CHAR_HOOK.typeId,
									wx.EVT_KEY_DOWN.typeId):
			keycode = event.GetKeyCode()
		elif event.GetEventType() == wx.EVT_MENU.typeId:
			keycode = self.progress_wnd.id_to_keycode.get(event.GetId())
		if keycode is not None and getattr(self, "subprocess", None) and \
			hasattr(self.subprocess, "send"):
			keycode = keycodes.get(keycode, keycode)
			##if keycode == ord("7") and \
			   ##self.progress_wnd is getattr(self, "terminal", None) and \
			   ##"7) Continue on to calibration" in self.recent.read():
				### calibration
				##wx.CallAfter(self.swap_progress_wnds)
			##el
			if keycode in (ord("\x1b"), ord("8"), ord("Q"), ord("q")):
				# exit
				self.thread_abort = True
				self.subprocess_abort = True
				delayedresult.startWorker(lambda result: None, 
										  self.quit_terminate_cmd)
				return
			try:
				self.subprocess.send(chr(keycode))
			except:
				pass
	
	def ti1_lookup_to_ti3(self, ti1, profile, pcs=None):
		"""
		Read TI1 (filename or CGATS instance), lookup device->pcs values 
		absolute colorimetrically through profile using Argyll's xicclu 
		utility and return TI3 (CGATS instance)
		
		"""
		
		# ti1
		if isinstance(ti1, basestring):
			ti1 = CGATS.CGATS(ti1)
		if not isinstance(ti1, CGATS.CGATS):
			raise TypeError('Wrong type for ti1, needs to be CGATS.CGATS '
							'instance')
		required = ("RGB_R", "RGB_G", "RGB_B")
		ti1_filename = ti1.filename
		ti1 = verify_cgats(ti1, required, True)
		if not ti1:
			raise ValueError(lang.getstr("error.testchart.missing_fields", 
										 (ti1_filename, ", ".join(required))))
		
		# profile
		if isinstance(profile, basestring):
			profile = ICCP.ICCProfile(profile)
		if not isinstance(profile, ICCP.ICCProfile):
			raise TypeError('Wrong type for profile, needs to be '
							'ICCP.ICCProfile instance')
		
		# determine pcs for lookup
		if not pcs:
			color_rep = profile.connectionColorSpace.upper()
			if color_rep == 'LAB':
				pcs = 'l'
			elif color_rep == 'XYZ':
				pcs = 'x'
			else:
				raise ValueError('Unknown color representation ' + color_rep)
		
		# get profile color space
		colorspace = profile.colorSpace
		
		# read device values from ti1
		data = ti1.queryv1("DATA")
		if not data:
			raise ValueError(lang.getstr("error.testchart.invalid", 
										 ti1_filename))
		device_data = data.queryv(required)
		if not device_data:
			raise ValueError(lang.getstr("error.testchart.missing_fields", 
										 (ti1_filename, ", ".join(required))))
		# make sure the first four patches are white so the whitepoint can be
		# averaged
		white_rgb = {'RGB_R': 100, 'RGB_G': 100, 'RGB_B': 100}
		white = dict(white_rgb)
		for label in data.parent.DATA_FORMAT.values():
			if not label in white:
				if label.upper() == 'LAB_L':
					value = 100
				elif label.upper() in ('LAB_A', 'LAB_B'):
					value = 0
				elif label.upper() == 'XYZ_X':
					value = 95.1065
				elif label.upper() == 'XYZ_Y':
					value = 100
				elif label.upper() == 'XYZ_Z':
					value = 108.844
				else:
					value = '0'
				white.update({label: value})
		white_added_count = 0
		while len(data.queryi(white_rgb)) < 4:  # add white patches
			data.insert(0, white)
			white_added_count += 1
		safe_print("Added %i white patch(es)" % white_added_count)
		idata = []
		for rgb in device_data.values():
			idata.append(' '.join(str(n) for n in rgb.values()))

		# lookup device->cie values through profile using xicclu
		xicclu = get_argyll_util("xicclu").encode(fs_enc)
		cwd = self.create_tempdir()
		if isinstance(cwd, Exception):
			raise cwd
		profile.write(os.path.join(cwd, "temp.icc"))
		if sys.platform == "win32":
			startupinfo = sp.STARTUPINFO()
			startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
			startupinfo.wShowWindow = sp.SW_HIDE
		else:
			startupinfo = None
		p = sp.Popen([xicclu, '-ff', '-ir', '-p' + pcs, '-s100', "temp.icc"], 
					 stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.STDOUT, 
					 cwd=cwd.encode(fs_enc), startupinfo=startupinfo)
		odata = p.communicate('\n'.join(idata))[0].splitlines()
		if p.wait() != 0:
			# error
			raise IOError(''.join(odata))
		
		# treat r=g=b specially: set expected a=b=0
		gray = []
		igray = []
		igray_idx = []
		for i, line in enumerate(odata):
			line = line.strip().split('->')
			line = ''.join(line).split()
			if line[-1] == '(clip)':
				line.pop()
			r, g, b = [float(n) for n in line[:3]]
			if r == g == b < 100:
				# if grayscale and not white
				cie = [float(n) for n in line[5:-1]]
				if pcs == 'x':
					# Need to scale XYZ coming from xicclu, Lab is already scaled
					cie = colormath.XYZ2Lab(*[n * 100.0 for n in cie])
				cie = (cie[0], 0, 0)  # set a=b=0
				igray.append("%s %s %s" % cie)
				igray_idx.append(i)
				if pcs == 'x':
					cie = colormath.Lab2XYZ(*cie)
					luminance = cie[1]
				else:
					luminance = colormath.Lab2XYZ(*cie)[1]
				if luminance * 100.0 >= 1:
					# only add if luminance is greater or equal 1% because 
					# dark tones fluctuate too much
					gray.append((r, g, b))
				if False:  # NEVER?
					# set cie in odata to a=b=0
					line[5:-1] = [str(n) for n in cie]
					odata[i] = ' -> '.join([' '.join(line[:4]), line[4], 
											' '.join(line[5:])])
		
		if igray and False:  # NEVER?
			# lookup cie->device values for grays through profile using xicclu
			gray = []
			xicclu = get_argyll_util("xicclu").encode(fs_enc)
			cwd = self.create_tempdir()
			if isinstance(cwd, Exception):
				raise cwd
			profile.write(os.path.join(cwd, "temp.icc"))
			if sys.platform == "win32":
				startupinfo = sp.STARTUPINFO()
				startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
				startupinfo.wShowWindow = sp.SW_HIDE
			else:
				startupinfo = None
			p = sp.Popen([xicclu, '-fb', '-ir', '-pl', '-s100', "temp.icc"], 
						 stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.STDOUT, 
						 cwd=cwd.encode(fs_enc), startupinfo=startupinfo)
			ogray = p.communicate('\n'.join(igray))[0].splitlines()
			if p.wait() != 0:
				# error
				raise IOError(''.join(odata))
			for i, line in enumerate(ogray):
				line = line.strip().split('->')
				line = ''.join(line).split()
				if line[-1] == '(clip)':
					line.pop()
				cie = [float(n) for n in line[:3]]
				rgb = [float(n) for n in line[5:-1]]
				if colormath.Lab2XYZ(cie[0], 0, 0)[1] * 100.0 >= 1:
					# only add if luminance is greater or equal 1% because 
					# dark tones fluctuate too much
					gray.append(rgb)
				# update values in ti1 and data for ti3
				for n, channel in enumerate(("R", "G", "B")):
					data[igray_idx[i] + 
						 white_added_count]["RGB_" + channel] = rgb[n]
				oline = odata[igray_idx[i]].strip().split('->', 1)
				odata[igray_idx[i]] = ' [RGB] ->'.join([' '.join(line[5:-1])] + 
													   oline[1:])
		
		self.wrapup(False)

		# write output ti3
		ofile = StringIO()
		ofile.write('CTI3\n')
		ofile.write('\n')
		ofile.write('DESCRIPTOR "Argyll Calibration Target chart information 3"\n')
		ofile.write('KEYWORD "DEVICE_CLASS"\n')
		ofile.write('DEVICE_CLASS "' + ('DISPLAY' if colorspace == 'RGB' else 
										'OUTPUT') + '"\n')
		include_sample_name = False
		i = 0
		for line in odata:
			line = line.strip().split('->')
			line = ''.join(line).split()
			if line[-1] == '(clip)':
				line.pop()
			if i == 0:
				icolor = line[3].strip('[]')
				if icolor == 'RGB':
					olabel = 'RGB_R RGB_G RGB_B'
				elif icolor == 'CMYK':
					olabel = 'CMYK_C CMYK_M CMYK_Y CMYK_K'
				else:
					raise ValueError('Unknown color representation ' + icolor)
				ocolor = line[-1].strip('[]').upper()
				if ocolor == 'LAB':
					ilabel = 'LAB_L LAB_A LAB_B'
				elif ocolor == 'XYZ':
					ilabel = 'XYZ_X XYZ_Y XYZ_Z'
				else:
					raise ValueError('Unknown color representation ' + ocolor)
				ofile.write('KEYWORD "COLOR_REP"\n')
				ofile.write('COLOR_REP "' + icolor + '_' + ocolor + '"\n')
				
				ofile.write('\n')
				ofile.write('NUMBER_OF_FIELDS ')
				if include_sample_name:
					ofile.write(str(2 + len(icolor) + len(ocolor)) + '\n')
				else:
					ofile.write(str(1 + len(icolor) + len(ocolor)) + '\n')
				ofile.write('BEGIN_DATA_FORMAT\n')
				ofile.write('SAMPLE_ID ')
				if include_sample_name:
					ofile.write('SAMPLE_NAME ' + olabel + ' ' + ilabel + '\n')
				else:
					ofile.write(olabel + ' ' + ilabel + '\n')
				ofile.write('END_DATA_FORMAT\n')
				ofile.write('\n')
				ofile.write('NUMBER_OF_SETS ' + str(len(odata)) + '\n')
				ofile.write('BEGIN_DATA\n')
			i += 1
			cie = [float(n) for n in line[5:-1]]
			if pcs == 'x':
				# Need to scale XYZ coming from xicclu, Lab is already scaled
				cie = [round(n * 100.0, 5 - len(str(int(abs(n * 100.0))))) 
					   for n in cie]
			cie = [str(n) for n in cie]
			if include_sample_name:
				ofile.write(str(i) + ' ' + data[i - 1][1].strip('"') + ' ' + 
							' '.join(line[:3]) + ' ' + ' '.join(cie) + '\n')
			else:
				ofile.write(str(i) + ' ' + ' '.join(line[:3]) + ' ' + 
							' '.join(cie) + '\n')
		ofile.write('END_DATA\n')
		ofile.seek(0)
		return ti1, CGATS.CGATS(ofile)[0], map(list, gray)
	
	def ti3_lookup_to_ti1(self, ti3, profile):
		"""
		Read TI3 (filename or CGATS instance), lookup cie->device values 
		absolute colorimetrically through profile using Argyll's xicclu 
		utility and return TI1 and compatible TI3 (CGATS instances)
		
		"""
		
		# ti3
		if isinstance(ti3, basestring):
			ti3 = CGATS.CGATS(ti3)
		if not isinstance(ti3, CGATS.CGATS):
			raise TypeError('Wrong type for ti3, needs to be CGATS.CGATS '
							'instance')
		ti3_filename = ti3.filename
		ti3v = verify_cgats(ti3, ("LAB_L", "LAB_A", "LAB_B"), True)
		if ti3v:
			color_rep = 'LAB'
		else:
			ti3v = verify_cgats(ti3, ("XYZ_X", "XYZ_Y", "XYZ_Z"), True)
			if ti3v:
				color_rep = 'XYZ'
			else:
				raise ValueError(lang.getstr("error.testchart.missing_fields", 
										 (ti3_filename, 
										  "XYZ_X, XYZ_Y, XYZ_Z " +
										  lang.getstr("or") + 
										  " LAB_L, LAB_A, LAB_B")))
		
		# profile
		if isinstance(profile, basestring):
			profile = ICCP.ICCProfile(profile)
		if not isinstance(profile, ICCP.ICCProfile):
			raise TypeError('Wrong type for profile, needs to be '
							'ICCP.ICCProfile instance')
			
		# determine pcs for lookup
		if color_rep == 'LAB':
			pcs = 'l'
			required = ("LAB_L", "LAB_A", "LAB_B")
		elif color_rep == 'XYZ':
			pcs = 'x'
			required = ("XYZ_X", "XYZ_Y", "XYZ_Z")
		else:
			raise ValueError('Unknown color representation ' + color_rep)

		# get profile color space
		colorspace = profile.colorSpace

		# read cie values from ti3
		data = ti3v.queryv1("DATA")
		if not data:
			raise ValueError(lang.getstr("error.testchart.invalid", 
										 ti3_filename))
		cie_data = data.queryv(required)
		if not cie_data:
			raise ValueError(lang.getstr("error.testchart.missing_fields", 
										 (ti3_filename, ", ".join(required))))
		idata = []
		# make sure the first four patches are white so the whitepoint can be
		# averaged
		wp = [n * 100.0 for n in profile.tags.wtpt.values()]
		if color_rep == 'LAB':
			wp = colormath.XYZ2Lab(*wp)
			wp = OrderedDict((('L', wp[0]), ('a', wp[1]), ('b', wp[2])))
		else:
			wp = OrderedDict((('X', wp[0]), ('Y', wp[1]), ('Z', wp[2])))
		wp = [wp] * 4
		safe_print("Added 4 white patches")
		for cie in wp + cie_data.values():  # first four patches = white
			cie = cie.values()
			if color_rep == 'XYZ':
				# assume scale 0...100 in ti3, we need to convert to 0...1
				cie = [n / 100.0 for n in cie]
			idata.append(' '.join(str(n) for n in cie))

		# lookup cie->device values through profile.icc using xicclu
		xicclu = get_argyll_util("xicclu").encode(fs_enc)
		cwd = self.create_tempdir()
		if isinstance(cwd, Exception):
			raise cwd
		profile.write(os.path.join(cwd, "temp.icc"))
		if sys.platform == "win32":
			startupinfo = sp.STARTUPINFO()
			startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
			startupinfo.wShowWindow = sp.SW_HIDE
		else:
			startupinfo = None
		p = sp.Popen([xicclu, '-fb', '-ir', '-p' + pcs, '-s100', "temp.icc"], 
					 stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.STDOUT, 
					 cwd=cwd.encode(fs_enc), startupinfo=startupinfo)
		odata = p.communicate('\n'.join(idata))[0].splitlines()
		if p.wait() != 0:
			# error
			raise IOError(''.join(odata))
		self.wrapup(False)
		
		# write output ti1/ti3
		ti1out = StringIO()
		ti1out.write('CTI1\n')
		ti1out.write('\n')
		ti1out.write('DESCRIPTOR "Argyll Calibration Target chart information 1"\n')
		include_sample_name = False
		i = 0
		for line in odata:
			line = line.strip().split('->')
			line = ''.join(line).split()
			if line[-1] == '(clip)':
				line.pop()
			if i == 0:
				icolor = line[3].strip('[]').upper()
				if icolor == 'LAB':
					ilabel = 'LAB_L LAB_A LAB_B'
				elif icolor == 'XYZ':
					ilabel = 'XYZ_X XYZ_Y XYZ_Z'
				else:
					raise ValueError('Unknown color representation ' + icolor)
				ocolor = line[-1].strip('[]')
				if ocolor == 'RGB':
					olabel = 'RGB_R RGB_G RGB_B'
				else:
					raise ValueError('Unknown color representation ' + ocolor)
				olabels = olabel.split()
				# add device fields to DATA_FORMAT if not yet present
				if not olabels[0] in ti3v.DATA_FORMAT.values() and \
				   not olabels[1] in ti3v.DATA_FORMAT.values() and \
				   not olabels[2] in ti3v.DATA_FORMAT.values():
					ti3v.DATA_FORMAT.add_data(olabels)
				# add required fields to DATA_FORMAT if not yet present
				if not required[0] in ti3v.DATA_FORMAT.values() and \
				   not required[1] in ti3v.DATA_FORMAT.values() and \
				   not required[2] in ti3v.DATA_FORMAT.values():
					ti3v.DATA_FORMAT.add_data(required)
				ti1out.write('KEYWORD "COLOR_REP"\n')
				ti1out.write('COLOR_REP "' + ocolor + '"\n')
				ti1out.write('\n')
				ti1out.write('NUMBER_OF_FIELDS ')
				if include_sample_name:
					ti1out.write(str(2 + len(icolor) + len(ocolor)) + '\n')
				else:
					ti1out.write(str(1 + len(icolor) + len(ocolor)) + '\n')
				ti1out.write('BEGIN_DATA_FORMAT\n')
				ti1out.write('SAMPLE_ID ')
				if include_sample_name:
					ti1out.write('SAMPLE_NAME ' + olabel + ' ' + ilabel + '\n')
				else:
					ti1out.write(olabel + ' ' + ilabel + '\n')
				ti1out.write('END_DATA_FORMAT\n')
				ti1out.write('\n')
				ti1out.write('NUMBER_OF_SETS ' + str(len(odata)) + '\n')
				ti1out.write('BEGIN_DATA\n')
			if i < len(wp):
				device = '100.00 100.00 100.00'.split()
			else:
				device = line[5:-1]
			cie = (wp + cie_data.values())[i].values()
			cie = [str(n) for n in cie]
			if include_sample_name:
				ti1out.write(str(i + 1) + ' ' + data[i][1].strip('"') + ' ' + 
							 ' '.join(device) + ' ' + ' '.join(cie) + '\n')
			else:
				ti1out.write(str(i + 1) + ' ' + ' '.join(device) + ' ' + 
							 ' '.join(cie) + '\n')
			if i > len(wp) - 1:  # don't include whitepoint patches in ti3
				# set device values in ti3
				for n, v in enumerate(olabels):
					ti3v.DATA[i - len(wp)][v] = float(line[5 + n])
				# set PCS values in ti3
				for n, v in enumerate(cie):
					ti3v.DATA[i - len(wp)][required[n]] = float(v)
			i += 1
		ti1out.write('END_DATA\n')
		ti1out.seek(0)
		return CGATS.CGATS(ti1out), ti3v


	def wrapup(self, copy=True, remove=True, dst_path=None, ext_filter=None):
		"""
		Wrap up - copy and/or clean temporary file(s).
		
		"""
		if debug: safe_print("[D] wrapup(copy=%s, remove=%s)" % (copy, remove))
		if not self.tempdir or not os.path.isdir(self.tempdir):
			return # nothing to do
		if copy:
			if not ext_filter:
				ext_filter = [".app", ".cal", ".ccmx", ".cmd", ".command", ".icc", 
							  ".icm", ".sh", ".ti1", ".ti3"]
			if dst_path is None:
				dst_path = os.path.join(getcfg("profile.save_path"), 
										getcfg("profile.name.expanded"), 
										getcfg("profile.name.expanded") + 
										".ext")
			result = check_create_dir(os.path.dirname(dst_path))
			if isinstance(result, Exception):
				return result
			if result:
				try:
					src_listdir = os.listdir(self.tempdir)
				except Exception, exception:
					safe_print(u"Error - directory '%s' listing failed: %s" % 
							   tuple(safe_unicode(s) for s in (self.tempdir, 
															   exception)))
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
									if verbose >= 2:
										safe_print(appname + 
												   ": Removing existing "
												   "destination directory tree", 
												   dst)
									try:
										shutil.rmtree(dst, True)
									except Exception, exception:
										safe_print(u"Warning - directory '%s' "
												   u"could not be removed: %s" % 
												   tuple(safe_unicode(s) 
														 for s in (dst, 
																   exception)))
								else:
									if verbose >= 2:
										safe_print(appname + 
												   ": Removing existing "
												   "destination file", dst)
									try:
										os.remove(dst)
									except Exception, exception:
										safe_print(u"Warning - file '%s' could "
												   u"not be removed: %s" % 
												   tuple(safe_unicode(s) 
														 for s in (dst, 
																   exception)))
							if remove:
								if verbose >= 2:
									safe_print(appname + ": Moving temporary "
											   "object %s to %s" % (src, dst))
								try:
									shutil.move(src, dst)
								except Exception, exception:
									safe_print(u"Warning - temporary object "
											   u"'%s' could not be moved to "
											   u"'%s': %s" % 
											   tuple(safe_unicode(s) for s in 
													 (src, dst, exception)))
							else:
								if os.path.isdir(src):
									if verbose >= 2:
										safe_print(appname + 
												   ": Copying temporary "
												   "directory tree %s to %s" % 
												   (src, dst))
									try:
										shutil.copytree(src, dst)
									except Exception, exception:
										safe_print(u"Warning - temporary "
												   u"directory '%s' could not "
												   u"be copied to '%s': %s" % 
												   tuple(safe_unicode(s) 
														 for s in 
														 (src, dst, exception)))
								else:
									if verbose >= 2:
										safe_print(appname + 
												   ": Copying temporary "
												   "file %s to %s" % (src, dst))
									try:
										shutil.copyfile(src, dst)
									except Exception, exception:
										safe_print(u"Warning - temporary file "
												   u"'%s' could not be copied "
												   u"to '%s': %s" % 
												   tuple(safe_unicode(s) 
														 for s in 
														 (src, dst, exception)))
		if remove:
			try:
				src_listdir = os.listdir(self.tempdir)
			except Exception, exception:
				safe_print(u"Error - directory '%s' listing failed: %s" % 
						   tuple(safe_unicode(s) for s in (self.tempdir, 
														   exception)))
			else:
				for basename in src_listdir:
					name, ext = os.path.splitext(basename)
					if ext_filter is None or ext.lower() not in ext_filter:
						src = os.path.join(self.tempdir, basename)
						isdir = os.path.isdir(src)
						if isdir:
							if verbose >= 2:
								safe_print(appname + ": Removing temporary "
										   "directory tree", src)
							try:
								shutil.rmtree(src, True)
							except Exception, exception:
								safe_print(u"Warning - temporary directory "
										   u"'%s' could not be removed: %s" % 
										   tuple(safe_unicode(s) for s in 
												 (src, exception)))
						else:
							if verbose >= 2:
								safe_print(appname + 
										   ": Removing temporary file", 
										   src)
							try:
								os.remove(src)
							except Exception, exception:
								safe_print(u"Warning - temporary directory "
										   u"'%s' could not be removed: %s" % 
										   tuple(safe_unicode(s) for s in 
												 (src, exception)))
			try:
				src_listdir = os.listdir(self.tempdir)
			except Exception, exception:
				safe_print(u"Error - directory '%s' listing failed: %s" % 
						   tuple(safe_unicode(s) for s in (self.tempdir, 
														   exception)))
			else:
				if not src_listdir:
					if verbose >= 2:
						safe_print(appname + 
								   ": Removing empty temporary directory", 
								   self.tempdir)
					try:
						shutil.rmtree(self.tempdir, True)
					except Exception, exception:
						safe_print(u"Warning - temporary directory '%s' could "
								   u"not be removed: %s" % 
								   tuple(safe_unicode(s) for s in 
										 (self.tempdir, exception)))
		return True
