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
elif sys.platform == "win32":
	from SendKeys import SendKeys
	import win32api
import wx
import wx.lib.delayedresult as delayedresult

import ICCProfile as ICCP
import config
import lang
import subprocess26 as sp
import tempfile26 as tempfile
from StringIOu import StringIOu as StringIO
from argyll_cgats import extract_fix_copy_cal
from argyll_instruments import instruments, remove_vendor_names
from argyll_names import names as argyll_names, altnames as argyll_altnames, viewconds
from config import cmdfile_ext, defaults, enc, exe_ext, fs_enc, getbitmap, getcfg, get_data_path, setcfg
from debughelpers import handle_error
from log import log, safe_print
from meta import name as appname
from options import debug, test, verbose
from util_io import Files, Tea
from util_os import getenvu, get_sudo, quote_args, which
from util_str import asciize
from wxwindows import ConfirmDialog, InfoDialog

def check_argyll_bin(paths = None):
	""" Check if the Argyll binaries can be found. """
	prev_dir = None
	for name in argyll_names:
		exe = get_argyll_util(name, paths)
		if not exe:
			return False
		cur_dir = os.path.dirname(exe)
		if prev_dir:
			if cur_dir != prev_dir:
				if verbose: safe_print("Warning - the Argyll executables are scattered. They should be in the same directory.")
				return False
		else:
			prev_dir = cur_dir
	if verbose >= 3: safe_print("Argyll binary directory:", cur_dir)
	if debug: safe_print("check_argyll_bin OK")
	if debug >= 2:
		if not paths:
			paths = getenvu("PATH", os.defpath).split(os.pathsep)
			argyll_dir = (getcfg("argyll.dir") or "").rstrip(os.path.sep)
			if argyll_dir:
				if argyll_dir in paths:
					paths.remove(argyll_dir)
				paths = [argyll_dir] + paths
		safe_print(" searchpath:\n ", "\n  ".join(paths))
	return True

def check_create_dir(path, parent = None):
	if not os.path.exists(path):
		try:
			os.makedirs(path)
		except Exception, exception:
			InfoDialog(parent, pos = (-1, 100), msg = lang.getstr("error.dir_creation", path) + "\n\n" + unicode(str(exception), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
			return False
	if not os.path.isdir(path):
		InfoDialog(parent, pos = (-1, 100), msg = lang.getstr("error.dir_notdir", path), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
		return False
	return True

def check_cal_isfile(cal = None, missing_msg = None, notfile_msg = None, parent = None, silent = False):
	if not silent:
		if not missing_msg:
			missing_msg = lang.getstr("error.calibration.file_missing", cal)
		if not notfile_msg:
			notfile_msg = lang.getstr("error.calibration.file_notfile", cal)
	return check_file_isfile(cal, missing_msg, notfile_msg, parent, silent)

def check_profile_isfile(profile_path = None, missing_msg = None, notfile_msg = None, parent = None, silent = False):
	if not silent:
		if not missing_msg:
			missing_msg = lang.getstr("error.profile.file_missing", profile_path)
		if not notfile_msg:
			notfile_msg = lang.getstr("error.profile.file_notfile", profile_path)
	return check_file_isfile(profile_path, missing_msg, notfile_msg, parent, silent)

def check_file_isfile(filename, missing_msg = None, notfile_msg = None, parent = None, silent = False):
	if not os.path.exists(filename):
		if not silent:
			if not missing_msg:
				missing_msg = lang.getstr("file.missing", filename)
			InfoDialog(parent, pos = (-1, 100), msg = missing_msg, ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
		return False
	if not os.path.isfile(filename):
		if not silent:
			if not notfile_msg:
				notfile_msg = lang.getstr("file.notfile", filename)
			InfoDialog(parent, pos = (-1, 100), msg = notfile_msg, ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
		return False
	return True

def check_set_argyll_bin():
	if check_argyll_bin():
		return True
	else:
		return set_argyll_bin()

def get_argyll_util(name, paths = None):
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
			safe_print("Info:", "|".join(argyll_altnames[name]), "not found in", os.pathsep.join(paths))
	return exe

def get_argyll_utilname(name, paths = None):
	""" Find a single Argyll utility. Return the basename. """
	exe = get_argyll_util(name, paths)
	if exe:
		exe = os.path.basename(os.path.splitext(exe)[0])
	return exe

def get_options_from_cprt(cprt):
	if not isinstance(cprt, unicode):
		if isinstance(cprt, (ICCP.TextDescriptionType, ICCP.MultiLocalizedUnicodeType)):
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
		"c(?:%s)" % "|".join(viewconds),
		"d(?:%s)" % "|".join(viewconds)
	]
	options_dispcal = []
	options_colprof = []
	if dispcal:
		options_dispcal = re.findall(" -(" + "|".join(re_options_dispcal) + ")", " " + dispcal)
	if colprof:
		options_colprof = re.findall(" -(" + "|".join(re_options_colprof) + ")", " " + colprof)
	return options_dispcal, options_colprof

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

def make_argyll_compatible_path(path):
	parts = path.split(os.path.sep)
	for i in range(len(parts)):
		parts[i] = unicode(parts[i].encode(enc, "asciize"), enc).replace("/", "_")
	return os.path.sep.join(parts)

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

def sendkeys(delay = 0, target = "", keys = ""):
	""" Send key(s) to optional target after delay. """
	if sys.platform == "darwin":
		mac_app_activate(delay, target)
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
			if verbose >= 1: safe_print("Error - sendkeys() failed:", exception)
	elif sys.platform == "win32":
		try:
			if delay: sleep(delay)
			# hwnd = win32gui.FindWindowEx(0, 0, 0, target)
			# win32gui.ShowWindow(hwnd, win32con.SW_SHOWNORMAL)
			SendKeys(keys, with_spaces = True, with_tabs = True, with_newlines = True, turn_off_numlock = False)
		except Exception, exception:
			if verbose >= 1: safe_print("Error - sendkeys() failed:", exception)
	else:
		try:
			if delay: sleep(delay)
			if verbose >= 2:
				safe_print('Sending key sequence using xte: "%s"' % keys)
			stdout = tempfile.SpooledTemporaryFile()
			retcode = sp.call(["xte", "key %s" % keys], stdin = sp.PIPE, stdout = stdout, stderr = stdout)
			if verbose >= 2:
				stdout.seek(0)
				safe_print(stdout.read())
			stdout.close()
			if retcode != 0:
				if verbose >= 2:
					safe_print(retcode)
		except Exception, exception:
			if verbose >= 1: safe_print("Error - sendkeys() failed:", exception)

def set_argyll_bin(parent = None):
	if parent and not parent.IsShownOnScreen():
		parent = None # do not center on parent if not visible
	defaultPath = os.path.sep.join(get_verified_path("argyll.dir"))
	dlg = wx.DirDialog(parent, lang.getstr("dialog.set_argyll_bin"), defaultPath = defaultPath, style = wx.DD_DIR_MUST_EXIST)
	dlg.Center(wx.BOTH)
	result = dlg.ShowModal() == wx.ID_OK
	if result:
		path = dlg.GetPath().rstrip(os.path.sep)
		result = check_argyll_bin([path])
		if result:
			if verbose >= 3: safe_print("Setting Argyll binary directory:", path)
			setcfg("argyll.dir", path)
		else:
			InfoDialog(self, msg = lang.getstr("argyll.dir.invalid", (exe_ext, exe_ext, exe_ext, exe_ext, exe_ext)), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
		writecfg()
	dlg.Destroy()
	return result

class Worker():
	def __init__(self, owner = None):
		self.owner = owner # owner should be a wxFrame or similar
		self.reset()
		self.argyll_version = [0, 0, 0]
		self.argyll_version_string = ""
		self.instruments = []
		self.displays = []
		self.dispread_after_dispcal = False
		self.options_colprof = []
		self.options_dispcal = []
		self.options_dispread = []
		self.options_targen = []
		self.tempdir = None

	def reset(self):
		self.pwd = None
		self.retcode = -1
		self.output = []
		self.errors = []

	def create_tempdir(self):
		if not self.tempdir or not os.path.isdir(self.tempdir):
			# we create the tempdir once each calibrating/profiling run (deleted automatically after each run)
			try:
				self.tempdir = tempfile.mkdtemp(prefix = appname + u"-")
			except Exception, exception:
				self.tempdir = None
				handle_error("Error - could not create temporary directory: " + str(exception), parent = self.owner)
		return self.tempdir

	def enumerate_displays_and_ports(self, silent = False):
		if (silent and check_argyll_bin()) or (not silent and check_set_argyll_bin()):
			displays = list(self.displays)
			if verbose >= 1 and not silent: safe_print(lang.getstr("enumerating_displays_and_comports"))
			self.exec_cmd(get_argyll_util("dispcal"), [], capture_output = True, skip_cmds = True, silent = True, log_output = False)
			arg = None
			self.displays = []
			self.instruments = []
			defaults["calibration.black_point_rate.enabled"] = 0
			n = -1
			for line in self.output:
				if type(line) in (str, unicode):
					n += 1
					line = line.strip()
					if n == 0 and "version" in line.lower():
						argyll_version = line[line.lower().find("version")+8:]
						self.argyll_version_string = argyll_version
						if verbose >= 3: safe_print("Argyll CMS version", argyll_version)
						argyll_version = re.findall("(\d+|[^.\d]+)", argyll_version)
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
							# Rate of blending from neutral to black point. Default 8.0
							defaults["calibration.black_point_rate.enabled"] = 1
					elif len(line) > 1 and line[1][0] == "=":
						value = line[1].strip(" ='")
						if arg == "-d":
							match = re.findall("(.+?),? at (-?\d+), (-?\d+), width (\d+), height (\d+)", value)
							if len(match):
								display = "%s @ %s, %s, %sx%s" % match[0]
								if " ".join(value.split()[-2:]) == "(Primary Display)":
									display += " " + lang.getstr("display.primary")
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
				# check lut access
				self.lut_access = [] # displays where lut access works
				i = 0
				for disp in self.displays:
					if verbose >= 1 and not silent: safe_print(lang.getstr("checking_lut_access", (i + 1)))
					# load test.cal
					self.exec_cmd(get_argyll_util("dispwin"), ["-d%s" % (i +1), "-c", get_data_path("test.cal")], capture_output = True, skip_cmds = True, silent = True)
					# check if LUT == test.cal
					self.exec_cmd(get_argyll_util("dispwin"), ["-d%s" % (i +1), "-V", get_data_path("test.cal")], capture_output = True, skip_cmds = True, silent = True)
					retcode = -1
					for line in self.output:
						if line.find("IS loaded") >= 0:
							retcode = 0
							break
					# reset LUT & load profile cal (if any)
					self.exec_cmd(get_argyll_util("dispwin"), ["-d%s" % (i +1), "-c", "-L"], capture_output = True, skip_cmds = True, silent = True)
					self.lut_access += [retcode == 0]
					if verbose >= 1 and not silent:
						if retcode == 0:
							safe_print(lang.getstr("success"))
						else:
							safe_print(lang.getstr("failure"))
					i += 1

	def exec_cmd(self, cmd, args = [], capture_output = False, display_output = False, low_contrast = True, skip_cmds = False, silent = False, parent = None, asroot = False, log_output = True):
		if parent is None:
			parent = self.owner
		# if capture_output:
			# fn = self.infoframe.Log
		# else:
		fn = None
		self.reset()
		if None in [cmd, args]:
			if verbose >= 1 and not capture_output: safe_print(lang.getstr("aborted"), fn = fn)
			return False
		cmdname = os.path.splitext(os.path.basename(cmd))[0]
		if args and args[-1].find(os.path.sep) > -1:
			working_dir = os.path.dirname(args[-1])
			working_basename = os.path.splitext(os.path.basename(args[-1]))[0] if cmdname == get_argyll_utilname("dispwin") else os.path.basename(args[-1]) # last arg is without extension, only for dispwin we need to strip it
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
			if not silent or verbose >= 3:
				safe_print("", fn = fn)
				if working_dir:
					safe_print(lang.getstr("working_dir"), fn = fn)
					indent = "  "
					for name in working_dir.split(os.path.sep):
						safe_print(textwrap.fill(name + os.path.sep, 80, expand_tabs = False, replace_whitespace = False, initial_indent = indent, subsequent_indent = indent), fn = fn)
						indent += " "
					safe_print("", fn = fn)
				safe_print(lang.getstr("commandline"), fn = fn)
				printcmdline(cmd if verbose >= 2 else os.path.basename(cmd), args, fn = fn, cwd = working_dir)
				safe_print("", fn = fn)
		cmdline = [cmd] + args
		for i in range(len(cmdline)):
			item = cmdline[i]
			if i > 0 and (item.find(os.path.sep) > -1 and os.path.dirname(item) == working_dir):
				# strip the path from all items in the working dir
				if sys.platform == "win32" and re.search("[^\x00-\x7f]", item) and os.path.exists(item):
					item = win32api.GetShortPathName(item) # avoid problems with encoding
				cmdline[i] = os.path.basename(item)
		sudo = None
		if cmdname == get_argyll_utilname("dispwin") and ("-Sl" in args or "-Sn" in args):
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
					dlg = ConfirmDialog(parent, msg = lang.getstr("dialog.enter_password"), ok = lang.getstr("ok"), cancel = lang.getstr("cancel"), bitmap = getbitmap("theme/icons/32x32/dialog-question"))
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
							safe_print(lang.getstr("aborted"), fn = fn)
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
							dlg.message.SetLabel(lang.getstr("auth.failed") + "\n" + lang.getstr("dialog.enter_password"))
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
			# cmdline = [sudo, u" ".join(quote_args(cmdline)) + ('>"%s" 2>"%s"' % (tmpstdout, tmpstderr))]
			# if os.path.basename(sudo) in ["gnomesu", "kdesu"]:
				# cmdline.insert(1, "-c")
		if working_dir and not skip_cmds:
			try:
				cmdfilename = os.path.join(working_dir, working_basename + "." + cmdname + cmdfile_ext)
				allfilename = os.path.join(working_dir, working_basename + ".all" + cmdfile_ext)
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
					context.write(u"@echo off\n")
					context.write((u'PATH %s;%%PATH%%\n' % os.path.dirname(cmd)).encode(enc, "asciize"))
					cmdfiles.write(u'pushd "%~dp0"\n'.encode(enc, "asciize"))
					if cmdname in (get_argyll_utilname("dispcal"), get_argyll_utilname("dispread")):
						cmdfiles.write(u"color 07\n")
				else:
					# context.write(u"set +v\n")
					context.write((u'PATH=%s:$PATH\n' % os.path.dirname(cmd)).encode(enc, "asciize"))
					if sys.platform == "darwin" and config.mac_create_app:
						cmdfiles.write(u'pushd "`dirname \\"$0\\"`/../../.."\n')
					else:
						cmdfiles.write(u'pushd "`dirname \\"$0\\"`"\n')
					if cmdname in (get_argyll_utilname("dispcal"), get_argyll_utilname("dispread")) and sys.platform != "darwin":
						cmdfiles.write(u'echo -e "\\033[40;2;37m" && clear\n')
					# if last and sys.platform != "darwin":
						# context.write(u'gnome_screensaver_running=$(ps -A -f | grep gnome-screensaver | grep -v grep)\n')
						# context.write(u'if [ "$gnome_screensaver_running" != "" ]; then gnome-screensaver-command --exit; fi\n')
					os.chmod(cmdfilename, 0755)
					os.chmod(allfilename, 0755)
				cmdfiles.write(u" ".join(quote_args(cmdline)).replace(cmd, cmdname).encode(enc, "asciize") + "\n")
				if sys.platform == "win32":
					cmdfiles.write(u"set exitcode=%errorlevel%\n")
					if cmdname in (get_argyll_utilname("dispcal"), get_argyll_utilname("dispread")):
						# reset to default commandline shell colors
						cmdfiles.write(u"color\n")
					cmdfiles.write(u"popd\n")
					cmdfiles.write(u"if not %exitcode%==0 exit /B %exitcode%\n")
				else:
					cmdfiles.write(u"exitcode=$?\n")
					if cmdname in (get_argyll_utilname("dispcal"), get_argyll_utilname("dispread")) and sys.platform != "darwin":
						# reset to default commandline shell colors
						cmdfiles.write(u'echo -e "\\033[0m" && clear\n')
					cmdfiles.write(u"popd\n")
					# if last and sys.platform != "darwin":
						# cmdfiles.write(u'if [ "$gnome_screensaver_running" != "" ]; then gnome-screensaver; fi\n')
					cmdfiles.write(u"if [ $exitcode -ne 0 ]; then exit $exitcode; fi\n")
				cmdfiles.close()
				if sys.platform == "darwin":
					if config.mac_create_app:
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
		if cmdname == get_argyll_utilname("dispread") and self.dispread_after_dispcal:
			instrument_features = self.get_instrument_features()
			if verbose >= 2:
				safe_print("Running calibration and profiling in succession, checking instrument for unattended capability...")
				if instrument_features:
					safe_print("Instrument needs sensor calibration before use:", "Yes" if instrument_features.get("sensor_cal") else "No")
					if instrument_features.get("sensor_cal"):
						safe_print("Instrument can be forced to skip sensor calibration:", "Yes" if instrument_features.get("skip_sensor_cal") and self.argyll_version >= [1, 1, 0] else "No")
				else:
					safe_print("Warning - instrument not recognized:", self.get_instrument_name())
			# -N switch not working as expected in Argyll 1.0.3
			if instrument_features and (not instrument_features.get("sensor_cal") or (instrument_features.get("skip_sensor_cal") and self.argyll_version >= [1, 1, 0])):
				if verbose >= 2:
					safe_print("Instrument can be used for unattended calibration and profiling")
				try:
					if verbose >= 2:
						safe_print("Sending 'SPACE' key to automatically start measurements in 10 seconds...")
					if sys.platform == "darwin":
						start_new_thread(sendkeys, (10, "Terminal", " "))
					elif sys.platform == "win32":
						start_new_thread(sendkeys, (10, appname + exe_ext, " "))
					else:
						if which("xte"):
							start_new_thread(sendkeys, (10, None, "space"))
						elif verbose >= 2:
							safe_print("Warning - 'xte' commandline tool not found, unattended measurements not possible")
				except Exception, exception:
					safe_print("Warning - unattended measurements not possible (start_new_thread failed with %s)" % str(exception))
			elif verbose >= 2:
				safe_print("Instrument can not be used for unattended calibration and profiling")
		elif cmdname in (get_argyll_utilname("dispcal"), get_argyll_utilname("dispread")) and \
			sys.platform == "darwin" and args and self.owner and not self.owner.IsShownOnScreen():
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
			while tries > 0:
				self.subprocess = sp.Popen([arg.encode(fs_enc) for arg in cmdline], stdin = sp.PIPE if sudo else None, stdout = stdout, stderr = stderr, cwd = None if working_dir is None else working_dir.encode(fs_enc))
				if sudo and self.subprocess.poll() is None:
					if self.pwd:
						self.subprocess.communicate(self.pwd)
					else:
						self.subprocess.communicate()
				self.retcode = self.subprocess.wait()
				self.subprocess = None
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
							if (self.retcode != 0 or cmdname == get_argyll_utilname("dispwin")):
								InfoDialog(parent, pos = (-1, 100), msg = unicode("".join(errors2).strip(), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-warning"))
							else:
								safe_print(unicode("".join(errors2).strip(), enc, "replace"), fn = fn)
					if tries > 0:
						stderr = Tea(tempfile.SpooledTemporaryFile())
				if capture_output:
					stdout.seek(0)
					self.output = [re.sub("^\.{4,}\s*$", "", line) for line in stdout.readlines()]
					stdout.close()
					# if sudo:
						# stdout = open(tmpstdout, "r")
						# errors += stdout.readlines()
						# stdout.close()
					if len(self.output) and log_output:
						log(unicode("".join(self.output).strip(), enc, "replace"))
						if display_output and self.owner and hasattr(self.owner, "infoframe"):
							wx.CallAfter(self.owner.infoframe.Show)
					if tries > 0:
						stdout = tempfile.SpooledTemporaryFile()
		except Exception, exception:
			handle_error("Error: " + (traceback.format_exc() if debug else str(exception)), parent = self.owner)
			self.retcode = -1
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
		if self.retcode != 0:
			if verbose >= 1 and not capture_output: safe_print(lang.getstr("aborted"), fn = fn)
			return False
		# else:
			# if verbose >= 1 and not capture_output: safe_print("", fn = fn)
		return True

	def generic_consumer(self, delayedResult, consumer, *args, **kwargs):
		# consumer must accept result as first arg
		result = None
		exception = None
		try:
			result = delayedResult.get()
		except Exception, exception:
			handle_error("Error - delayedResult.get() failed: " + traceback.format_exc(), parent = self.owner)
		self.progress_parent.progress_start_timer.Stop()
		if hasattr(self.progress_parent, "progress_dlg"):
			self.progress_parent.progress_timer.Stop()
			self.progress_parent.progress_dlg.Hide() # do not destroy, will crash on Linux
		wx.CallAfter(consumer, result, *args, **kwargs)
	
	def get_display_name(self):
		""" Return name of currently configured display """
		n = getcfg("display.number") - 1
		if n >= 0 and n < len(self.displays):
			return self.displays[n]
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

	def is_working(self):
		return hasattr(self, "progress_parent") and (self.progress_parent.progress_start_timer.IsRunning() or self.progress_parent.progress_timer.IsRunning())

	def prepare_colprof(self, profile_name = None, display_name = None):
		profile_save_path = self.create_tempdir()
		if not profile_save_path or not check_create_dir(profile_save_path, parent = self.owner): # check directory and in/output file(s)
			return None, None
		if profile_name is None:
			profile_name = getcfg("profile.name.expanded")
		inoutfile = make_argyll_compatible_path(os.path.join(profile_save_path, profile_name))
		if not os.path.exists(inoutfile + ".ti3"):
			InfoDialog(self.owner, pos = (-1, 100), msg = lang.getstr("error.measurement.file_missing", inoutfile + ".ti3"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
			return None, None
		if not os.path.isfile(inoutfile + ".ti3"):
			InfoDialog(self.owner, pos = (-1, 100), msg = lang.getstr("error.measurement.file_notfile", inoutfile + ".ti3"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
			return None, None
		#
		cmd = get_argyll_util("colprof")
		args = []
		args += ["-v"] # verbose
		args += ["-q" + getcfg("profile.quality")]
		args += ["-a" + getcfg("profile.type")]
		if getcfg("profile.type") in ["l", "x"]:
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
		if "-d3" in self.options_targen:
			if len(self.displays):
				args += ["-M"]
				if display_name is None:
					args += [self.get_display_name().split(" @")[0]]
				else:
					args += [display_name]
			args += ["-C"]
			args += [u"(c) %s %s. Created with %s and Argyll CMS: dispcal %s colprof %s" % (strftime("%Y"), unicode(getpass.getuser(), fs_enc, "asciize"), appname, " ".join(self.options_dispcal), " ".join(options_colprof))]
		else:
			args += ["-C"]
			args += [u"(c) %s %s. Created with %s and Argyll CMS: colprof %s" % (strftime("%Y"), unicode(getpass.getuser(), fs_enc, "asciize"), appname, " ".join(options_colprof))]
		args += ["-D"]
		args += [profile_name]
		args += [inoutfile]
		return cmd, args

	def prepare_dispcal(self, calibrate = True, verify = False):
		cmd = get_argyll_util("dispcal")
		args = []
		args += ["-v"] # verbose
		args += ["-d" + config.get_display()]
		args += ["-c%s" % getcfg("comport.number")]
		measurement_mode = getcfg("measurement_mode")
		instrument_features = self.get_instrument_features()
		if measurement_mode:
			if measurement_mode != "p" and not instrument_features.get("spectral"):
				args += ["-y" + measurement_mode[0]] # always specify -y (won't be read from .cal when updating)
			if "p" in measurement_mode and instrument_features.get("projector_mode") and self.argyll_version >= [1, 1, 0]: # projector mode, Argyll >= 1.1.0 Beta
				args += ["-p"]
		args += [("-p" if self.argyll_version <= [1, 0, 4] else "-P") + getcfg("dimensions.measureframe")]
		if bool(int(getcfg("measure.darken_background"))):
			args += ["-F"]
		if instrument_features.get("high_res"):
			args += ["-H"]
		if calibrate:
			args += ["-q" + getcfg("calibration.quality")]
			profile_save_path = self.create_tempdir()
			if not profile_save_path or not check_create_dir(profile_save_path, parent = self.owner):
				return None, None
			inoutfile = make_argyll_compatible_path(os.path.join(profile_save_path, getcfg("profile.name.expanded")))
			#
			if getcfg("calibration.update"):
				cal = getcfg("calibration.file")
				calcopy = os.path.join(inoutfile + ".cal")
				filename, ext = os.path.splitext(cal)
				ext = ".cal"
				cal = filename + ext
				if ext.lower() == ".cal":
					if not check_cal_isfile(cal, parent = self.owner):
						return None, None
					if not os.path.exists(calcopy):
						try:
							shutil.copyfile(cal, calcopy) # copy cal to profile dir
						except Exception, exception:
							InfoDialog(self.owner, pos = (-1, 100), msg = lang.getstr("error.copy_failed", (cal, calcopy)) + "\n\n" + unicode(str(exception), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
							return None, None
						if not check_cal_isfile(calcopy, parent = self.owner):
							return None, None
						cal = calcopy
				else:
					rslt = extract_fix_copy_cal(cal, calcopy)
					if isinstance(rslt, ICCP.ICCProfileInvalidError):
						InfoDialog(self.owner, msg = lang.getstr("profile.invalid"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					elif isinstance(rslt, Exception):
						InfoDialog(self.owner, msg = lang.getstr("cal_extraction_failed") + "\n\n" + unicode(str(rslt), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					if not isinstance(rslt, list):
						return None, None
				#
				if getcfg("profile.update"):
					profile_path = os.path.splitext(getcfg("calibration.file"))[0] + profile_ext
					if not check_profile_isfile(profile_path, parent = self.owner):
						return None, None
					profilecopy = os.path.join(inoutfile + profile_ext)
					if not os.path.exists(profilecopy):
						try:
							shutil.copyfile(profile_path, profilecopy) # copy profile to profile dir
						except Exception, exception:
							InfoDialog(self.owner, pos = (-1, 100), msg = lang.getstr("error.copy_failed", (profile_path, profilecopy)) + "\n\n" + unicode(str(exception), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
							return None, None
						if not check_profile_isfile(profilecopy, parent = self.owner):
							return None, None
					args += ["-o"]
				args += ["-u"]
		if (calibrate and not getcfg("calibration.update")) or (not calibrate and verify):
			if calibrate and not getcfg("calibration.interactive_display_adjustment"):
				args += ["-m"] # skip interactive adjustment
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
				args += ["-a%s" % getcfg("calibration.ambient_viewcond_adjust.lux")]
			args += ["-k%s" % getcfg("calibration.black_point_correction")]
			if defaults["calibration.black_point_rate.enabled"] and float(getcfg("calibration.black_point_correction")) < 1:
				black_point_rate = getcfg("calibration.black_point_rate")
				if black_point_rate:
					args += ["-A%s" % black_point_rate]
			black_luminance = getcfg("calibration.black_luminance", False)
			if black_luminance:
				args += ["-B%s" % black_luminance]
			if verify:
				if calibrate and type(verify) == int:
					args += ["-e%s" % verify] # verify final computed curves
				else:
					args += ["-E"] # verify current curves
		self.options_dispcal = list(args)
		if calibrate:
			args += [inoutfile]
		return cmd, args

	def prepare_dispread(self, apply_calibration = True):
		profile_save_path = self.create_tempdir()
		if not profile_save_path or not check_create_dir(profile_save_path, parent = self.owner): # check directory and in/output file(s)
			return None, None
		inoutfile = make_argyll_compatible_path(os.path.join(profile_save_path, getcfg("profile.name.expanded")))
		if not os.path.exists(inoutfile + ".ti1"):
			filename, ext = os.path.splitext(getcfg("testchart.file"))
			if not check_file_isfile(filename + ext, parent = self.owner):
				return None, None
			try:
				if ext.lower() in (".icc", ".icm"):
					try:
						profile = ICCP.ICCProfile(filename + ext)
					except (IOError, ICCP.ICCProfileInvalidError), exception:
						InfoDialog(self.owner, pos = (-1, 100), msg = lang.getstr("error.testchart.read", getcfg("testchart.file")), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
						return None, None
					ti3 = StringIO(profile.tags.get("CIED", ""))
				elif ext.lower() == ".ti1":
					shutil.copyfile(filename + ext, inoutfile + ".ti1")
				else: # ti3
					try:
						ti3 = open(filename + ext, "rU")
					except Exception, exception:
						InfoDialog(self.owner, pos = (-1, 100), msg = lang.getstr("error.testchart.read", getcfg("testchart.file")), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
						return None, None
				if ext.lower() != ".ti1":
					ti3_lines = [line.strip() for line in ti3]
					ti3.close()
					if not "CTI3" in ti3_lines:
						InfoDialog(self.owner, pos = (-1, 100), msg = lang.getstr("error.testchart.invalid", getcfg("testchart.file")), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
						return None, None
					ti1 = open(inoutfile + ".ti1", "w")
					ti1.write(ti3_to_ti1(ti3_lines))
					ti1.close()
			except Exception, exception:
				InfoDialog(self.owner, pos = (-1, 100), msg = lang.getstr("error.testchart.creation_failed", inoutfile + ".ti1") + "\n\n" + unicode(str(exception), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
				return None, None
		if apply_calibration:
			if apply_calibration == True:
				cal = os.path.join(getcfg("profile.save_path"), getcfg("profile.name.expanded"), getcfg("profile.name.expanded")) + ".cal" # always a .cal file in that case
			else:
				cal = apply_calibration # can be .cal or .icc / .icm
			calcopy = os.path.join(inoutfile + ".cal")
			filename, ext = os.path.splitext(cal)
			if ext.lower() == ".cal":
				if not check_cal_isfile(cal, parent = self.owner):
					return None, None
				if not os.path.exists(calcopy):
					try:
						shutil.copyfile(cal, calcopy) # copy cal to temp dir
					except Exception, exception:
						InfoDialog(self.owner, pos = (-1, 100), msg = lang.getstr("error.copy_failed", (cal, calcopy)) + "\n\n" + unicode(str(exception), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
						return None, None
					if not check_cal_isfile(calcopy, parent = self.owner):
						return None, None
			else: # .icc / .icm
				self.options_dispcal = []
				if not check_profile_isfile(cal, parent = self.owner):
					return None, None
				try:
					profile = ICCP.ICCProfile(filename + ext)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					profile = None
				if profile:
					ti3 = StringIO(profile.tags.get("CIED", ""))
					if "cprt" in profile.tags: # get dispcal options if present
						self.options_dispcal = ["-" + arg for arg in get_options_from_cprt(profile.tags.cprt)[0]]
				else:
					ti3 = StringIO("")
				ti3_lines = [line.strip() for line in ti3]
				ti3.close()
				if not "CTI3" in ti3_lines:
					InfoDialog(self.owner, pos = (-1, 100), msg = lang.getstr("error.cal_extraction", (cal)), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					return None, None
				try:
					tmpcal = open(calcopy, "w")
					tmpcal.write(extract_cal_from_ti3(ti3_lines))
					tmpcal.close()
				except Exception, exception:
					InfoDialog(self.owner, pos = (-1, 100), msg = lang.getstr("error.cal_extraction", (cal)) + "\n\n" + unicode(str(exception), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					return None, None
			cal = calcopy
		#
		cmd = get_argyll_util("dispread")
		args = []
		args += ["-v"] # verbose
		args += ["-d" + config.get_display()]
		args += ["-c%s" % getcfg("comport.number")]
		measurement_mode = getcfg("measurement_mode")
		instrument_features = self.get_instrument_features()
		if measurement_mode:
			if measurement_mode != "p" and not instrument_features.get("spectral"):
				args += ["-y" + measurement_mode[0]] # always specify -y (won't be read from .cal when updating)
			if "p" in measurement_mode and instrument_features.get("projector_mode") and self.argyll_version >= [1, 1, 0]: # projector mode, Argyll >= 1.1.0 Beta
				args += ["-p"]
		if apply_calibration:
			args += ["-k"]
			args += [cal]
		args += [("-p" if self.argyll_version <= [1, 0, 4] else "-P") + getcfg("dimensions.measureframe")]
		if bool(int(getcfg("measure.darken_background"))):
			args += ["-F"]
		if instrument_features.get("high_res"):
			args += ["-H"]
		self.options_dispread = args + self.options_dispread
		return cmd, self.options_dispread + [inoutfile]

	def prepare_dispwin(self, cal = None, profile_path = None, install = True):
		cmd = get_argyll_util("dispwin")
		args = []
		args += ["-v"] # verbose
		args += ["-d" + config.get_display()]
		args += ["-c"] # first, clear any calibration
		if cal == True:
			args += ["-L"]
		elif cal:
			if not check_cal_isfile(cal, parent = self.owner):
				return None, None
			# calcopy = make_argyll_compatible_path(os.path.join(self.create_tempdir(), os.path.basename(cal)))
			# if not os.path.exists(calcopy):
				# shutil.copyfile(cal, calcopy) # copy cal to temp dir
				# if not check_cal_isfile(calcopy, parent = self.owner):
					# return None, None
			# cal = calcopy
			args += [cal]
		else:
			if cal is None:
				if not profile_path:
					profile_save_path = os.path.join(getcfg("profile.save_path"), getcfg("profile.name.expanded"))
					profile_path = os.path.join(profile_save_path, getcfg("profile.name.expanded") + profile_ext)
				if not check_profile_isfile(profile_path, parent = self.owner):
					return None, None
				try:
					profile = ICCP.ICCProfile(profile_path)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					InfoDialog(self.owner, msg = lang.getstr("profile.invalid"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					return None, None
				if profile.profileClass != "mntr" or profile.colorSpace != "RGB":
					InfoDialog(self.owner, msg = lang.getstr("profile.unsupported", (profile.profileClass, profile.colorSpace)), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					return None, None
				if install:
					if getcfg("profile.install_scope") != "u" and \
						(((sys.platform == "darwin" or (sys.platform != "win32" and self.argyll_version >= [1, 1, 0])) and (os.geteuid() == 0 or get_sudo())) or 
						(sys.platform == "win32" and sys.getwindowsversion() >= (6, )) or test):
							# -S option is broken on Linux with current Argyll releases
							args += ["-S" + getcfg("profile.install_scope")]
					args += ["-I"]
				# profcopy = make_argyll_compatible_path(os.path.join(self.create_tempdir(), os.path.basename(profile_path)))
				# if not os.path.exists(profcopy):
					# shutil.copyfile(profile_path, profcopy) # copy profile to temp dir
					# if not check_profile_isfile(profcopy, parent = self.owner):
						# return None, None
				# profile_path = profcopy
				args += [profile_path]
		return cmd, args

	def prepare_targen(self, parent):
		path = self.create_tempdir()
		if not path or not check_create_dir(path, parent): # check directory and in/output file(s)
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
				args += ['-F%s,%s,%s,%s' % (getcfg("tc_filter_L"), getcfg("tc_filter_a"), getcfg("tc_filter_b"), getcfg("tc_filter_rad"))]
		else:
			args += ['-f0']
		if getcfg("tc_vrml"):
			if getcfg("tc_vrml_lab"):
				args += ['-w']
			if getcfg("tc_vrml_device"):
				args += ['-W']
		self.options_targen = list(args)
		if debug: safe_print("Setting targen options:", self.options_targen)
		args += [inoutfile]
		return cmd, args

	def progress_timer_handler(self, event):
		keepGoing, skip = self.progress_parent.progress_dlg.Pulse(self.progress_parent.progress_dlg.GetTitle())
		if not keepGoing:
			if hasattr(self, "subprocess") and self.subprocess:
				if self.subprocess.poll() is None:
					try:
						self.subprocess.terminate()
					except Exception, exception:
						handle_error("Error - subprocess.terminate() failed: " + str(exception), parent = self.progress_parent.progress_dlg)
				elif verbose >= 2:
					safe_print("Info: Subprocess already exited.")
			else:
				self.thread_abort = True

	def progress_dlg_start(self, progress_title = "", progress_msg = "", parent = None):
		if True: # hasattr(self, "subprocess") and self.subprocess and self.subprocess.poll() is None:
			style = wx.PD_APP_MODAL | wx.PD_ELAPSED_TIME | wx.PD_CAN_ABORT
		else:
			style = wx.PD_APP_MODAL | wx.PD_ELAPSED_TIME
		self.progress_parent.progress_dlg = wx.ProgressDialog(progress_title, progress_msg, parent = parent, style = style)
		self.progress_parent.progress_dlg.SetSize((400, -1))
		self.progress_parent.progress_dlg.Center()
		self.progress_parent.progress_timer.Start(50)

	def start(self, consumer, producer, cargs = (), ckwargs = None, wargs = (), wkwargs = None, progress_title = "", progress_msg = "", parent = None, progress_start = 100):
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
			self.progress_parent.Bind(wx.EVT_TIMER, self.progress_timer_handler, self.progress_parent.progress_timer)
		if progress_start < 100:
			progress_start = 100
		self.progress_parent.progress_start_timer = wx.CallLater(progress_start, self.progress_dlg_start, progress_title, progress_msg, parent) # show the progress dialog after 1ms
		self.thread_abort = False
		self.thread = delayedresult.startWorker(self.generic_consumer, producer, [consumer] + list(cargs), ckwargs, wargs, wkwargs)
		return True

	def wrapup(self, copy = True, remove = True, dst_path = None, ext_filter = None):
		if debug: safe_print("wrapup(copy = %s, remove = %s)" % (copy, remove))
		if not self.tempdir or not os.path.isdir(self.tempdir):
			return # nothing to do
		if copy:
			if not ext_filter:
				ext_filter = [".app", ".cal", ".cmd", ".command", ".icc", ".icm", ".sh", ".ti1", ".ti3"]
			if dst_path is None:
				dst_path = os.path.join(getcfg("profile.save_path"), getcfg("profile.name.expanded"), getcfg("profile.name.expanded") + ".ext")
			try:
				dir_created = check_create_dir(os.path.dirname(dst_path), parent = self.owner)
			except Exception, exception:
				InfoDialog(self.owner, pos = (-1, 100), msg = lang.getstr("error.dir_creation", (os.path.dirname(dst_path))) + "\n\n" + unicode(str(exception), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
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
