# -*- coding: utf-8 -*-

# stdlib
from __future__ import with_statement
from binascii import hexlify
import ctypes
import getpass
import glob
import math
import os
import pipes
import re
import socket
import shutil
import string
import subprocess as sp
import sys
import tempfile
import textwrap
import traceback
import urllib2
import zipfile
from UserString import UserString
from hashlib import md5
from threading import _MainThread, currentThread
from time import sleep, strftime, time
if sys.platform == "darwin":
	from platform import mac_ver
	from thread import start_new_thread
elif sys.platform == "win32":
	from ctypes import windll
	import _winreg

# 3rd party
if sys.platform == "win32":
	from win32com.shell import shell as win32com_shell
	import pythoncom
	import win32api
	import win32con
elif sys.platform != "darwin":
	try:
		import dbus
	except ImportError:
		dbus = None
		dbus_session = None
	else:
		try:
			dbus_session = dbus.SessionBus()
		except dbus.exceptions.DBusException:
			dbus_session = None

# custom
import CGATS
import ICCProfile as ICCP
import audio
import colormath
import config
import defaultpaths
import imfile
import localization as lang
import wexpect
from argyll_cgats import (add_dispcal_options_to_cal, add_options_to_ti3,
						  cal_to_fake_profile,
						  extract_fix_copy_cal, ti3_to_ti1, vcgt_to_cal,
						  verify_cgats)
from argyll_instruments import (get_canonical_instrument_name,
								instruments as all_instruments)
from argyll_names import (names as argyll_names, altnames as argyll_altnames, 
						  optional as argyll_optional, viewconds, intents)
from config import (autostart, autostart_home, script_ext, defaults, enc, exe,
					exe_ext, fs_enc, getcfg, geticon, get_data_path,
					get_total_patches, get_verified_path, isapp, isexe,
					is_ccxx_testchart, logdir, profile_ext, pydir, setcfg,
					split_display_name, writecfg, appbasename)
from defaultpaths import cache, iccprofiles_home, iccprofiles_display_home
from edid import WMIError, get_edid
from jsondict import JSONDict
from log import DummyLogger, LogFile, get_file_logger, log, safe_print
import madvr
from meta import VERSION, VERSION_BASE, domain, name as appname, version
from options import debug, test, test_require_sensor_cal, verbose
from ordereddict import OrderedDict
from patterngenerators import (PrismaPatternGeneratorClient,
							   ResolveLSPatternGeneratorServer,
							   ResolveCMPatternGeneratorServer)
from trash import trash
from util_io import (EncodedWriter, Files, GzipFileProper,
					 StringIOu as StringIO, TarFileProper)
from util_list import get as listget, intlist
if sys.platform == "darwin":
	from util_mac import (mac_app_activate, mac_terminal_do_script, 
						  mac_terminal_set_colors, osascript)
elif sys.platform == "win32":
	import util_win
import colord
from util_os import (expanduseru, getenvu, is_superuser, launch_file,
					 make_win32_compatible_long_path, quote_args, which,
					 whereis)
if sys.platform == "win32" and sys.getwindowsversion() >= (6, ):
	from util_os import win64_disable_file_system_redirection
from util_str import (safe_basestring, safe_str, safe_unicode, strtr,
					  universal_newlines)
from wxaddons import BetterCallLater, BetterWindowDisabler, wx
from wxwindows import ConfirmDialog, InfoDialog, ProgressDialog, SimpleTerminal
from wxDisplayAdjustmentFrame import DisplayAdjustmentFrame
from wxDisplayUniformityFrame import DisplayUniformityFrame
from wxUntetheredFrame import UntetheredFrame
xrandr = None
if sys.platform not in ("darwin", "win32"):
	try:
		import xrandr
	except ImportError:
		pass
import wx.lib.delayedresult as delayedresult

INST_CAL_MSGS = ["Do a reflective white calibration",
				 "Do a transmissive white calibration",
				 "Do a transmissive dark calibration",
				 "Place the instrument on its reflective white reference",
				 "Click the instrument on its reflective white reference",
				 "Place the instrument in the dark",
				 "Place cap on the instrument",  # i1 Pro
				 "or place on the calibration reference", # i1 Pro
				 "Place ambient adapter and cap on the instrument",
				 "Set instrument sensor to calibration position",  # ColorMunki
				 "Place the instrument on its transmissive white source",
				 "Use the appropriate tramissive blocking",
				 "Change filter on instrument to"]
USE_WPOPEN = 0

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


technology_strings_170 = JSONDict()
technology_strings_170["u"] = "Unknown"
technology_strings_170.path = "technology_strings-1.7.0.json"

# Argyll 1.7.1 fixes the technology type and display type selector
# "uniqueification" bug and thus uses different technology selectors
technology_strings_171 = JSONDict()
technology_strings_171["u"] = "Unknown"
technology_strings_171.path = "technology_strings-1.7.1.json"

workers = []


def Property(func):
	return property(**func())


def add_keywords_to_cgats(cgats, keywords):
	""" Add keywords to CGATS """
	if not isinstance(cgats, CGATS.CGATS):
		cgats = CGATS.CGATS(cgats)
	for keyword, value in keywords.iteritems():
		cgats[0].add_keyword(keyword, value)
	return cgats


def check_argyll_bin(paths=None):
	""" Check if the Argyll binaries can be found. """
	prev_dir = None
	for name in argyll_names:
		exe = get_argyll_util(name, paths)
		if not exe:
			if name in argyll_optional:
				continue
			return False
		cur_dir = os.path.dirname(exe)
		if prev_dir:
			if cur_dir != prev_dir:
				if name in argyll_optional:
					if verbose: safe_print("Warning: Optional Argyll "
										   "executable %s is not in the same "
										   "directory as the main executables "
										   "(%s)." % (exe, prev_dir))
				else:
					if verbose: safe_print("Error: Main Argyll "
										   "executable %s is not in the same "
										   "directory as the other executables "
										   "(%s)." % (exe, prev_dir))
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
	# Fedora doesn't ship Rec709.icm
	config.defaults["3dlut.input.profile"] = get_data_path(os.path.join("ref",
																		"Rec709.icm")) or \
											 get_data_path(os.path.join("ref", "sRGB.icm")) or ""
	config.defaults["testchart.reference"] = get_data_path(os.path.join("ref", 
																		"ColorChecker.cie")) or ""
	config.defaults["gamap_profile"] = get_data_path(os.path.join("ref", "sRGB.icm")) or ""
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
			notfile_msg = lang.getstr("file_notfile", cal)
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
			notfile_msg = lang.getstr("file_notfile", 
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


def check_set_argyll_bin(paths=None):
	"""
	Check if Argyll binaries can be found, otherwise let the user choose.
	"""
	if check_argyll_bin(paths):
		return True
	else:
		return set_argyll_bin()


def check_ti3_criteria1(RGB, XYZ, black_XYZ, white_XYZ,
						delta_to_sRGB_threshold_E=10,
						delta_to_sRGB_threshold_L=10,
						delta_to_sRGB_threshold_C=75,
						delta_to_sRGB_threshold_H=75,
						print_debuginfo=True):
	sRGBLab = colormath.RGB2Lab(RGB[0] / 100.0,
								RGB[1] / 100.0,
								RGB[2] / 100.0,
								noadapt=not white_XYZ)
	if white_XYZ:
		if black_XYZ:
			black_Lab = colormath.XYZ2Lab(*colormath.adapt(black_XYZ[0],
														   black_XYZ[1],
														   black_XYZ[2],
														   white_XYZ))
			black_C = math.sqrt(math.pow(black_Lab[1], 2) +
								math.pow(black_Lab[2], 2))
			if black_Lab[0] < 3 and black_C < 3:
				# Sanity check: Is this color reasonably dark and achromatic?
				# Then do BPC so we can compare better to perfect black sRGB
				XYZ = colormath.apply_bpc(XYZ[0], XYZ[1], XYZ[2], black_XYZ,
										  (0, 0, 0), white_XYZ)
		XYZ = colormath.adapt(XYZ[0], XYZ[1], XYZ[2], white_XYZ)
	Lab = colormath.XYZ2Lab(*XYZ)

	delta_to_sRGB = colormath.delta(*sRGBLab + Lab + (2000, ))

	# Depending on how (a)chromatic the sRGB color is, scale the thresholds
	# Use math derived from DE2000 formula to get chroma and hue angle
	L, a, b = sRGBLab
	b_pow = math.pow(b, 2)
	C = math.sqrt(math.pow(a, 2) + b_pow)
	C_pow = math.pow(C, 7)
	G = .5 * (1 - math.sqrt(C_pow / (C_pow + math.pow(25, 7))))
	a = (1 + G) * a
	C = math.sqrt(math.pow(a, 2) + b_pow)
	h = 0 if a == 0 and b == 0 else math.degrees(math.atan2(b, a)) + (0 if b >= 0 else 360.0)
	# C and h scaling factors
	C_scale = C / 100.0
	h_scale = h / 360.0
	# RGB hue, saturation and value scaling factors
	H, S, V = colormath.RGB2HSV(*[v / 100.0 for v in RGB])
	SV_scale = S * V
	# Scale the thresholds
	delta_to_sRGB_threshold_E += (delta_to_sRGB_threshold_E *
								  max(C_scale, SV_scale))
	delta_to_sRGB_threshold_L += (delta_to_sRGB_threshold_L *
								  max(C_scale, SV_scale))
	# Allow higher chroma errors as luminance of reference decreases
	L_scale = max(1 - (1 * C_scale) + (100.0 - L) / 100.0, 1)
	delta_to_sRGB_threshold_C = ((delta_to_sRGB_threshold_C *
								  max(C_scale, SV_scale) + 2) * L_scale)
	delta_to_sRGB_threshold_H = ((delta_to_sRGB_threshold_H *
								  max(C_scale, h_scale, H, SV_scale) + 2) *
								 L_scale)

	criteria1 = (delta_to_sRGB["E"] > delta_to_sRGB_threshold_E and
				 (abs(delta_to_sRGB["L"]) > delta_to_sRGB_threshold_L or
				  abs(delta_to_sRGB["C"]) > delta_to_sRGB_threshold_C or
				  abs(delta_to_sRGB["H"]) > delta_to_sRGB_threshold_H))
	# This patch has an unusually high delta 00 to its sRGB equivalent

	delta_to_sRGB["E_ok"] = delta_to_sRGB["E"] <= delta_to_sRGB_threshold_E
	delta_to_sRGB["L_ok"] = (abs(delta_to_sRGB["L"]) <=
							 delta_to_sRGB_threshold_L)
	delta_to_sRGB["C_ok"] = (abs(delta_to_sRGB["C"]) <=
							 delta_to_sRGB_threshold_C)
	delta_to_sRGB["H_ok"] = (abs(delta_to_sRGB["H"]) <=
							 delta_to_sRGB_threshold_H)
	delta_to_sRGB["ok"] = (delta_to_sRGB["E_ok"] and
						   delta_to_sRGB["L_ok"] and
						   delta_to_sRGB["C_ok"] and
						   delta_to_sRGB["H_ok"])

	debuginfo = ("RGB: %6.2f %6.2f %6.2f  RGB(sRGB)->Lab(D50): %6.2f %6.2f %6.2f  "
				 "L_scale: %5.3f   C: %5.2f C_scale: %5.3f  h: %5.2f  "
				 "h_scale: %5.3f  H: %5.2f  H_scale: %5.3f  S: %5.2f  "
				 "V: %5.2f  SV_scale: %5.3f  Thresholds: E %5.2f  L %5.2f  "
				 "C %5.2f  H %5.2f   XYZ->Lab(D50): %6.2f %6.2f %6.2f  delta "
				 "RGB(sRGB)->Lab(D50) to XYZ->Lab(D50): dE %5.2f  dL %5.2f  dC "
				 "%5.2f  dH %5.2f" %
				 (RGB[0], RGB[1], RGB[2], sRGBLab[0], sRGBLab[1], sRGBLab[2],
				  L_scale, C, C_scale, h, h_scale, H * 360, H, S, V, SV_scale,
				  delta_to_sRGB_threshold_E, delta_to_sRGB_threshold_L,
				  delta_to_sRGB_threshold_C, delta_to_sRGB_threshold_H,
				  Lab[0], Lab[1], Lab[2],
				  delta_to_sRGB["E"], delta_to_sRGB["L"], delta_to_sRGB["C"],
				  delta_to_sRGB["H"]))
	if print_debuginfo:
		safe_print(debuginfo)

	return sRGBLab, Lab, delta_to_sRGB, criteria1, debuginfo


def check_ti3_criteria2(prev_Lab, Lab, prev_sRGBLab, sRGBLab,
						prev_RGB, RGB, sRGB_delta_E_scale_factor=.5):
	delta = colormath.delta(*prev_Lab + Lab + (2000, ))
	sRGB_delta = colormath.delta(*prev_sRGBLab + sRGBLab + (2000, ))
	sRGB_delta["E"] *= sRGB_delta_E_scale_factor

	criteria2 =  delta["E"] < sRGB_delta["E"]
	# These two patches have different RGB values
	# but suspiciously low delta E 76.

	
	if criteria2 and (prev_RGB[0] == prev_RGB[1] == prev_RGB[2] and
					  RGB[0] == RGB[1] == RGB[2]):
		# If RGB gray, check if the Y difference makes sense
		criteria2 = ((RGB[0] > prev_RGB[0] and Lab[0] <= prev_Lab[0]) or
					 (RGB[0] < prev_RGB[0] and Lab[0] >= prev_Lab[0]))
		delta["L_ok"] = not criteria2
		delta["E_ok"] = True
	else:
		delta["E_ok"] = not criteria2
		delta["L_ok"] = True

	return delta, sRGB_delta, criteria2


def check_ti3(ti3, print_debuginfo=True):
	""" Check subsequent patches' expected vs real deltaE and collect patches
	with different RGB values, but suspiciously low delta E
	
	Used as a means to find misreads.
	
	The expected dE is calculated by converting from a patches RGB values
	(assuming sRGB) to Lab and comparing the values.
	
	"""
	if not isinstance(ti3, CGATS.CGATS):
		ti3 = CGATS.CGATS(ti3)
	data = ti3.queryv1("DATA")
	datalen = len(data)
	black = data.queryi1({"RGB_R": 0, "RGB_G": 0, "RGB_B": 0})
	if black:
		black = black["XYZ_X"], black["XYZ_Y"], black["XYZ_Z"]
	elif print_debuginfo:
		safe_print("Warning - no black patch found in CGATS")
	white = data.queryi1({"RGB_R": 100, "RGB_G": 100, "RGB_B": 100})
	if white:
		white = white["XYZ_X"], white["XYZ_Y"], white["XYZ_Z"]
	elif print_debuginfo:
		safe_print("Warning - no white patch found in CGATS")
	suspicious = []
	prev = {}
	delta = {}
	for index, item in data.iteritems():
		(sRGBLab,
		 Lab,
		 delta_to_sRGB,
		 criteria1,
		 debuginfo) = check_ti3_criteria1((item["RGB_R"],
										   item["RGB_G"],
										   item["RGB_B"]),
										  (item["XYZ_X"],
										   item["XYZ_Y"],
										   item["XYZ_Z"]),
										  black, white, print_debuginfo=False)
		if (criteria1 or (prev and (max(prev["item"]["RGB_R"], item["RGB_R"]) -
									min(prev["item"]["RGB_R"], item["RGB_R"]) >
									1.0 / 2.55 or
									max(prev["item"]["RGB_G"], item["RGB_G"]) -
									min(prev["item"]["RGB_G"], item["RGB_G"]) >
									1.0 / 2.55 or
									max(prev["item"]["RGB_B"], item["RGB_B"]) -
									min(prev["item"]["RGB_B"], item["RGB_B"]) >
									1.0 / 2.55))):
			if prev:
				(delta,
				 sRGB_delta,
				 criteria2) = check_ti3_criteria2(prev["Lab"], Lab,
												  prev["sRGBLab"], sRGBLab,
												  (prev["item"]["RGB_R"],
												   prev["item"]["RGB_G"],
												   prev["item"]["RGB_B"]),
												  (item["RGB_R"],
												   item["RGB_G"],
												   item["RGB_B"]))
			else:
				criteria2 = False
			if criteria1 or criteria2:
				if print_debuginfo:
					if criteria2:
						debuginfo = (("%s  dE to previous XYZ->Lab(D50): "
									  "%5.3f  dE_OK: %s  L_OK: %s  "
									  "0.5 dE RGB(sRGB)->Lab(D50) to previous "
									  "RGB(sRGB)->Lab(D50): %5.3f") % 
									 (debuginfo, delta["E"], delta["E_ok"],
									  delta["L_ok"], sRGB_delta["E"]))
					sample_id = "Patch #%%.0%id" % len(str(datalen))
					safe_print(sample_id % item.SAMPLE_ID, debuginfo)
				suspicious.append((prev["item"] if criteria2 else None,
								   item, delta if criteria2 else None,
								   sRGB_delta if criteria2 else None,
								   prev["delta_to_sRGB"] if criteria2 else None,
								   delta_to_sRGB))
		prev["item"] = item
		prev["sRGBLab"] = sRGBLab
		prev["Lab"] = Lab
		prev["delta_to_sRGB"] = delta_to_sRGB
	return suspicious


argyll_utils = {}

def get_argyll_util(name, paths=None):
	""" Find a single Argyll utility. Return the full path. """
	cfg_argyll_dir = getcfg("argyll.dir")
	if paths:
		cache_key = os.pathsep.join(paths)
	else:
		cache_key = cfg_argyll_dir
	exe = argyll_utils.get(cache_key, {}).get(name, None)
	if exe:
		return exe
	if not paths:
		paths = getenvu("PATH", os.defpath).split(os.pathsep)
		argyll_dir = (cfg_argyll_dir or "").rstrip(os.path.sep)
		if argyll_dir:
			if argyll_dir in paths:
				paths.remove(argyll_dir)
			paths = [argyll_dir] + paths
	elif verbose >= 4:
		safe_print("Info: Searching for", name, "in", os.pathsep.join(paths))
	for path in paths:
		for altname in argyll_altnames.get(name, []):
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
	if exe:
		if not cache_key in argyll_utils:
			argyll_utils[cache_key] = {}
		argyll_utils[cache_key][name] = exe
	return exe


def get_argyll_utilname(name, paths=None):
	""" Find a single Argyll utility. Return the basename without extension. """
	exe = get_argyll_util(name, paths)
	if exe:
		exe = os.path.basename(os.path.splitext(exe)[0])
	return exe


def get_argyll_version(name, silent=False, paths=None):
	"""
	Determine version of a certain Argyll utility.
	
	"""
	argyll_version_string = get_argyll_version_string(name, silent, paths)
	return parse_argyll_version_string(argyll_version_string)


def get_argyll_version_string(name, silent=False, paths=None):
	argyll_version_string = "0.0.0"
	if (silent and check_argyll_bin(paths)) or (not silent and 
												check_set_argyll_bin(paths)):
		cmd = get_argyll_util(name, paths)
		if sys.platform == "win32":
			startupinfo = sp.STARTUPINFO()
			startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
			startupinfo.wShowWindow = sp.SW_HIDE
		else:
			startupinfo = None
		try:
			p = sp.Popen([cmd.encode(fs_enc), "-?"], stdin=sp.PIPE,
						 stdout=sp.PIPE, stderr=sp.STDOUT,
						 startupinfo=startupinfo)
		except Exception, exception:
			safe_print(cmd)
			safe_print(exception)
			return argyll_version_string
		for i, line in enumerate((p.communicate()[0] or "").splitlines()):
			if isinstance(line, basestring):
				line = line.strip()
				if "version" in line.lower():
					argyll_version_string = line[line.lower().find("version")+8:]
					break
	return argyll_version_string


def get_current_profile_path(include_display_profile=True,
							 save_profile_if_no_path=False):
	profile = None
	profile_path = getcfg("calibration.file", False)
	if profile_path:
		filename, ext = os.path.splitext(profile_path)
		if ext.lower() in (".icc", ".icm"):
			try:
				profile = ICCP.ICCProfile(profile_path)
			except Exception, exception:
				safe_print("ICCP.ICCProfile(%r):" % profile_path, 
						   exception)
	elif include_display_profile:
		profile = config.get_display_profile()
		if profile and not profile.fileName and save_profile_if_no_path:
			if profile.ID == "\0" * 16:
				profile.calculateID()
			profile_cache_path = os.path.join(cache, "icc")
			if check_create_dir(profile_cache_path) is True:
				profile.fileName = os.path.join(profile_cache_path,
												"id=" + hexlify(profile.ID) +
												profile_ext)
				if not os.path.isfile(profile.fileName):
					profile.write()
	if profile:
		return profile.fileName


def parse_argument_string(args):
	""" Parses an argument string and returns a list of arguments. """
	return [re.sub('^["\']|["\']$', '', arg) for arg in
			re.findall('(?:^|\s+)(-[^\s"\']+|"[^"]+?"|\'[^\']+?\'|[^\s"\']+)', args)]


def parse_argyll_version_string(argyll_version_string):
	argyll_version = re.findall("(\d+|[^.\d]+)", argyll_version_string)
	for i, v in enumerate(argyll_version):
		try:
			argyll_version[i] = int(v)
		except ValueError:
			pass
	return argyll_version


def get_cfg_option_from_args(option_name, argmatch, args, whole=False):
	""" Parse args and return option (if found), otherwise default """
	option = defaults[option_name]
	iarg = get_arg(argmatch, args, whole)
	if iarg:
		if len(iarg[1]) == len(argmatch):
			# Option value is the next argument
			if len(args) > iarg[0] + 1:
				option = args[iarg[0] + 1]
		else:
			# Option value follows argument directly
			option = iarg[1][len(argmatch):]
	return option


def get_options_from_args(dispcal_args=None, colprof_args=None):
	"""
	Extract options used for dispcal and colprof from argument strings.
	"""
	re_options_dispcal = [
		"[moupHVF]",
		"d(?:\d+(?:,\d+)?|madvr|web)",
		"[cv]\d+",
		"q(?:%s)" % "|".join(config.valid_values["calibration.quality"]),
		"y(?:%s)" % "|".join(filter(None, config.valid_values["measurement_mode"])),
		"[tT](?:\d+(?:\.\d+)?)?",
		"w\d+(?:\.\d+)?,\d+(?:\.\d+)?",
		"[bfakAB]\d+(?:\.\d+)?",
		"(?:g(?:240|709|l|s)|[gG]\d+(?:\.\d+)?)",
		"[pP]\d+(?:\.\d+)?,\d+(?:\.\d+)?,\d+(?:\.\d+)?",
		'X(?:\s*\d+|\s+["\'][^"\']+?["\'])',  # Argyll >= 1.3.0 colorimeter correction matrix / Argyll >= 1.3.4 calibration spectral sample
		"I[bw]{,2}",  # Argyll >= 1.3.0 drift compensation
		"YA",  # Argyll >= 1.5.0 disable adaptive mode
		"Q\w+"
	]
	re_options_colprof = [
		"q[lmh]",
		"b[lmh]",  # B2A quality
		"a(?:%s)" % "|".join(config.valid_values["profile.type"]),
		'[sSMA]\s+["\'][^"\']+?["\']',
		"[cd](?:%s)(?=\W|$)" % "|".join(viewconds),
		"[tT](?:%s)(?=\W|$)" % "|".join(intents)
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
	look for the special DisplayCAL sections 'ARGYLL_DISPCAL_ARGS' and
	'ARGYLL_COLPROF_ARGS'. If either does not exist, fall back to the 
	copyright tag (DisplayCAL < 0.4.0.2) """
	if not isinstance(profile, ICCP.ICCProfile):
		profile = ICCP.ICCProfile(profile)
	dispcal_args = None
	colprof_args = None
	if "targ" in profile.tags:
		ti3 = CGATS.CGATS(profile.tags.targ)
		if 1 in ti3 and "ARGYLL_DISPCAL_ARGS" in ti3[1] and \
		   ti3[1].ARGYLL_DISPCAL_ARGS:
			dispcal_args = ti3[1].ARGYLL_DISPCAL_ARGS[0].decode("UTF-7", 
																"replace")
		if 0 in ti3 and "ARGYLL_COLPROF_ARGS" in ti3[0] and \
		   ti3[0].ARGYLL_COLPROF_ARGS:
			colprof_args = ti3[0].ARGYLL_COLPROF_ARGS[0].decode("UTF-7", 
																"replace")
	if not dispcal_args and "cprt" in profile.tags:
		dispcal_args = get_options_from_cprt(profile.getCopyright())[0]
	if not colprof_args and "cprt" in profile.tags:
		colprof_args = get_options_from_cprt(profile.getCopyright())[1]
	return get_options_from_args(dispcal_args, colprof_args)


def get_options_from_ti3(ti3):
	""" Try and get options from TI3 file by looking for the special
	DisplayCAL sections 'ARGYLL_DISPCAL_ARGS' and 'ARGYLL_COLPROF_ARGS'. """
	if not isinstance(ti3, CGATS.CGATS):
		ti3 = CGATS.CGATS(ti3)
	dispcal_args = None
	colprof_args = None
	if 1 in ti3 and "ARGYLL_DISPCAL_ARGS" in ti3[1] and \
	   ti3[1].ARGYLL_DISPCAL_ARGS:
		dispcal_args = ti3[1].ARGYLL_DISPCAL_ARGS[0].decode("UTF-7", 
															"replace")
	if 0 in ti3 and "ARGYLL_COLPROF_ARGS" in ti3[0] and \
	   ti3[0].ARGYLL_COLPROF_ARGS:
		colprof_args = ti3[0].ARGYLL_COLPROF_ARGS[0].decode("UTF-7", 
															"replace")
	return get_options_from_args(dispcal_args, colprof_args)


def get_pattern_geometry():
	""" Return pattern geometry for pattern generator """
	x, y, size = [float(v) for v in
				  getcfg("dimensions.measureframe").split(",")]
	size = size * defaults["size.measureframe"]
	match = re.search("@ -?\d+, -?\d+, (\d+)x(\d+)", getcfg("displays",
															raw=True))
	if match:
		display_size = [int(item) for item in match.groups()]
	else:
		display_size = 1920, 1080
	w, h = [min(size / v, 1.0) for v in display_size]
	if config.get_display_name(None, True) == "Prisma":
		w = h
	x = (display_size[0] - w * display_size[0]) * x / display_size[0]
	y = (display_size[1] - h * display_size[1]) * y / display_size[1]
	x, y, w, h = [max(v, 0) for v in (x, y, w, h)]
	size = min((w * display_size[0] * h * display_size[1]) /
			   float(display_size[0] * display_size[1]), 1.0)
	return x, y, w, h, size


def get_python_and_pythonpath():
	""" Return (system) python and pythonpath """
	# Determine the path of python, and python module search paths
	# If we are running 'frozen', expect python.exe in the same directory
	# as the packed executable.
	# py2exe: The python executable can be included via setup script by 
	# adding it to 'data_files'
	pythonpath = list(sys.path)
	dirname = os.path.dirname(sys.executable)
	if sys.platform == "win32":
		if getattr(sys, "frozen", False):
			pythonpath = [dirname]
			# If we are running 'frozen', add library.zip and lib\library.zip
			# to sys.path
			# py2exe: Needs appropriate 'zipfile' option in setup script and 
			# 'bundle_files' 3
			pythonpath.append(os.path.join(dirname, "library.zip"))
			pythonpath.append(os.path.join(dirname, "library.zip", appname))
			if os.path.isdir(os.path.join(dirname, "lib")):
				dirname = os.path.join(dirname, "lib")
				pythonpath.append(os.path.join(dirname, "library.zip"))
				pythonpath.append(os.path.join(dirname, "library.zip", appname))
		python = os.path.join(dirname, "python.exe")
	else:
		# Linux / Mac OS X
		if isapp:
			python = os.path.join(dirname, "python")
		else:
			paths = os.defpath.split(os.pathsep)
			python = (which("python2.7", paths) or which("python2.6", paths) or
					  "/usr/bin/env python")
	return (python, pythonpath)


def get_arg(argmatch, args, whole=False):
	""" Return first found entry beginning with the argmatch string or None """
	for i, arg in enumerate(args):
		if (whole and arg == argmatch) or (not whole and
										   arg.startswith(argmatch)):
			return i, arg


def make_argyll_compatible_path(path):
	"""
	Make the path compatible with the Argyll utilities.
	
	This is currently only effective under Windows to make sure that any 
	unicode 'division' slashes in the profile name are replaced with 
	underscores.
	
	"""
	make_compat_enc = fs_enc
	skip = -1
	if re.match(r'\\\\\?\\', path, re.I):
		# Don't forget about UNC paths: 
		# \\?\UNC\Server\Volume\File
		# \\?\C:\File
		skip = 2
	parts = path.split(os.path.sep)
	for i, part in enumerate(parts):
		if i > skip:
			parts[i] = unicode(part.encode(make_compat_enc, "safe_asciize"), 
							   make_compat_enc).replace("/", "_").replace("?", 
																		  "_")
	return os.path.sep.join(parts)


def printcmdline(cmd, args=None, fn=safe_print, cwd=None):
	"""
	Pretty-print a command line.
	"""
	if args is None:
		args = []
	if cwd is None:
		cwd = os.getcwdu()
	fn("  " + cmd)
	i = 0
	lines = []
	for item in args:
		ispath = False
		if item.find(os.path.sep) > -1:
			if os.path.dirname(item) == cwd:
				item = os.path.basename(item)
			ispath = True
		if sys.platform == "win32":
			item = sp.list2cmdline([item])
			if not item.startswith('"'):
				item = quote_args([item])[0]
		else:
			item = pipes.quote(item)
		lines.append(item)
		i += 1
	for line in lines:
		fn(textwrap.fill(line, 80, expand_tabs = False, 
				   replace_whitespace = False, initial_indent = "    ", 
				   subsequent_indent = "      "))


def set_argyll_bin(parent=None, silent=False, callafter=None, callafter_args=()):
	""" Set the directory containing the Argyll CMS binary executables """
	if parent and not parent.IsShownOnScreen():
		parent = None # do not center on parent if not visible
	# Check if Argyll version on PATH is newer than configured Argyll version
	paths = getenvu("PATH", os.defpath).split(os.pathsep)
	argyll_version_string = get_argyll_version_string("dispwin", True, paths)
	argyll_version = parse_argyll_version_string(argyll_version_string)
	argyll_version_string_cfg = get_argyll_version_string("dispwin", True)
	argyll_version_cfg = parse_argyll_version_string(argyll_version_string_cfg)
	# Don't prompt for 1.2.3_foo if current version is 1.2.3
	# but prompt for 1.2.3 if current version is 1.2.3_foo
	# Also prompt for 1.2.3_beta2 if current version is 1.2.3_beta
	if ((argyll_version > argyll_version_cfg and
		 (argyll_version[:4] == argyll_version_cfg[:4] or
		  not argyll_version_string.startswith(argyll_version_string_cfg))) or
		(argyll_version < argyll_version_cfg and
		 argyll_version_string_cfg.startswith(argyll_version_string))):
		argyll_dir = os.path.dirname(get_argyll_util("dispwin", paths) or "")
		dlg = ConfirmDialog(parent,
							msg=lang.getstr("dialog.select_argyll_version",
											(argyll_version_string,
											 argyll_version_string_cfg)),
							ok=lang.getstr("ok"),
							cancel=lang.getstr("cancel"),
							alt=lang.getstr("browse"),
							bitmap=geticon(32, "dialog-question"))
		dlg_result = dlg.ShowModal()
		dlg.Destroy()
		if dlg_result == wx.ID_OK:
			setcfg("argyll.dir", None)
			return True
		if dlg_result == wx.ID_CANCEL:
			if callafter:
				callafter(*callafter_args)
			return False
	else:
		argyll_dir = None
	if parent and not check_argyll_bin():
		dlg = ConfirmDialog(parent,
							msg=lang.getstr("dialog.argyll.notfound.choice"),
							ok=lang.getstr("download"),
							cancel=lang.getstr("cancel"),
							alt=lang.getstr("browse"),
							bitmap=geticon(32, "dialog-question"))
		dlg_result = dlg.ShowModal()
		dlg.Destroy()
		if dlg_result == wx.ID_OK:
			# Download Argyll CMS
			from DisplayCAL import app_update_check
			app_update_check(parent, silent, argyll=True)
			return False
		elif dlg_result == wx.ID_CANCEL:
			if callafter:
				callafter(*callafter_args)
			return False
	defaultPath = os.path.join(*get_verified_path("argyll.dir",
												  path=argyll_dir))
	dlg = wx.DirDialog(parent, lang.getstr("dialog.set_argyll_bin"), 
					   defaultPath=defaultPath, style=wx.DD_DIR_MUST_EXIST)
	dlg.Center(wx.BOTH)
	result = False
	while not result:
		result = dlg.ShowModal() == wx.ID_OK
		if result:
			path = dlg.GetPath().rstrip(os.path.sep)
			if os.path.basename(path) != "bin":
				path = os.path.join(path, "bin")
			result = check_argyll_bin([path])
			if result:
				if verbose >= 3:
					safe_print("Setting Argyll binary directory:", path)
				setcfg("argyll.dir", path)
				break
			else:
				not_found = []
				for name in argyll_names:
					if (not get_argyll_util(name, [path]) and
						not name in argyll_optional):
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
	if not result and callafter:
		callafter(*callafter_args)
	return result


def show_result_dialog(result, parent=None, pos=None, confirm=False):
	""" Show dialog depending on type of result. Result should be an
	exception type. An appropriate visual representation will be chosen
	whether result is of exception type 'Info', 'Warning' or other error. """
	msg = safe_unicode(result)
	if not pos:
		pos=(-1, -1)
	if isinstance(result, Info):
		bitmap = geticon(32, "dialog-information")
	elif isinstance(result, Warning):
		bitmap = geticon(32, "dialog-warning")
	else:
		bitmap = geticon(32, "dialog-error")
	if confirm:
		cls = ConfirmDialog
		ok = confirm
	else:
		cls = InfoDialog
		ok = lang.getstr("ok")
	dlg = cls(parent, pos=pos, msg=msg, ok=ok, bitmap=bitmap, 
			  log=not isinstance(result, (UnloggedError, UnloggedInfo,
										  UnloggedWarning)))
	if confirm:
		returncode = dlg.ShowModal()
		dlg.Destroy()
		return returncode == wx.ID_OK


class Error(Exception):
	pass


class Info(UserWarning):
	pass


class UnloggedError(Error):
	pass


class UnloggedInfo(Info):
	pass


class UnloggedWarning(UserWarning):
	pass


class Warn(UserWarning):
	pass


class EvalFalse(object):

	""" Evaluate to False in boolean comparisons """

	def __init__(self, wrapped_object):
		self._wrapped_object = wrapped_object

	def __getattribute__(self, name):
		return getattr(object.__getattribute__(self, "_wrapped_object"), name)

	def __nonzero__(self):
		return False


class DummyDialog(object):

	def __init__(self, *args, **kwargs):
		self.is_shown_on_screen = True

	def Close(self):
		pass

	def Destroy(self):
		pass

	def EndModal(self, id=-1):
		return id

	def Hide(self):
		pass

	def IsShownOnScreen(self):
		return self.is_shown_on_screen

	def Show(self, show=True):
		self.is_shown_on_screen = show

	def ShowModal(self):
		pass


class FilteredStream():
	
	""" Wrap a stream and filter all lines written to it. """
	
	# Discard the whole line if it is empty after replacing patterns
	discard = ""
	
	# If one of the triggers is contained in a line, skip the whole line
	triggers = ["Place instrument on test window",
				"key to continue",
				"key to retry",
				"key to take a reading",
				"] to read",
				"' to set",
				"' to report",
				"' to toggle",
				" or Q to ",
				"place on the white calibration reference",
				"read failed due to the sensor being in the wrong position",
				"Ambient filter should be removed"] + INST_CAL_MSGS
	
	substitutions = {r"\^\[": "",  # ESC key on Linux/OSX
					 "patch ": "Patch ",
					 re.compile(r"Point \d+", re.I): ""}

	# Strip these patterns from input before writing. Note that this only works
	# on full lines (ending with linesep_in)
	prestrip = ""
	
	def __init__(self, stream, data_encoding=None, file_encoding=None,
				 errors="replace", discard=None, linesep_in="\r\n", 
				 linesep_out="\n", substitutions=None,
				 triggers=None, prestrip=None):
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
		if prestrip is not None:
			self.prestrip = prestrip
		self._buffer = ""
	
	def __getattr__(self, name):
		return getattr(self.stream, name)
	
	def write(self, data):
		""" Write data to stream, stripping all unwanted output.
		
		Incoming lines are expected to be delimited by linesep_in.
		
		"""
		if not data:
			return
		if self.prestrip and (re.search(self.prestrip, data) or self._buffer):
			if not data.endswith(self.linesep_in):
				# Buffer all data until we see a line ending
				self._buffer += data
				return
			elif self._buffer:
				# Assemble the full line from the buffer
				data = self._buffer + data
				self._buffer = ""
			data = re.sub(self.prestrip, "", data)
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
				if self.data_encoding and not isinstance(line, unicode):
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
			if self.data_encoding and not isinstance(self.buf, unicode):
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


class Producer(object):

	""" Generic producer """

	def __init__(self, worker, producer, continue_next=False):
		self.worker = worker
		self.producer = producer
		self.continue_next = continue_next

	def __call__(self, *args, **kwargs):
		result = self.producer(*args, **kwargs)
		if not self.continue_next and self.worker._progress_wnd:
			if (hasattr(self.worker.progress_wnd, "animbmp") and
				self.worker.progress_wnd.progress_type in (0, 2)):
				# Allow time for animation fadeout
				wx.CallAfter(self.worker.progress_wnd.stop_timer, False)
				if self.worker.progress_wnd.progress_type == 0:
					sleep(4)
				else:
					sleep(1)
		return result


class StringWithLengthOverride(UserString):

	""" Allow defined behavior in comparisons and when evaluating length """

	def __init__(self, seq, length=None):
		UserString.__init__(self, seq)
		if length is None:
			length = len(seq)
		self.length = length

	def __len__(self):
		return self.length


class Sudo(object):

	""" Determine if a command can be run via sudo """

	def __init__(self):
		self.availoptions = {}
		self.sudo = which("sudo")
		if self.sudo:
			# Determine available sudo options
			man = which("man")
			if man:
				manproc = sp.Popen([man, "sudo"], stdout=sp.PIPE, 
									stderr=sp.PIPE)
				# Strip formatting
				stdout = re.sub(".\x08", "", manproc.communicate()[0])
				self.availoptions = {"E": bool(re.search("-E\W", stdout)),
									 "l [command]":
									 bool(re.search("-l\W(?:.*?\W)?command\W",
													stdout)),
									 "K": bool(re.search("-K\W", stdout)),
									 "k": bool(re.search("-k\W", stdout))}
			if debug:
				safe_print("[D] Available sudo options:", 
						   ", ".join(filter(lambda option: self.availoptions[option], 
											self.availoptions.keys())))

	def __len__(self):
		return int(bool(self.sudo))

	def __str__(self):
		return str(self.sudo or "")

	def __unicode__(self):
		return unicode(self.sudo or "")
	
	def _expect_timeout(self, patterns, timeout=-1, child_timeout=1):
		"""
		wexpect.spawn.expect with better timeout handling.
		
		The default expect can block up to timeout seconds if the child is
		already dead. To prevent this, we run expect in a loop until a pattern
		is matched, timeout is reached or an exception occurs. The max time an
		expect call will block if the child is already dead can be set with the
		child_timeout parameter.
		
		"""
		if timeout == -1:
			timeout = self.subprocess.timeout
		patterns = list(patterns)
		if not wexpect.TIMEOUT in patterns:
			patterns.append(wexpect.TIMEOUT)
		start = time()
		while True:
			result = self.subprocess.expect(patterns, timeout=child_timeout)
			if (self.subprocess.after is not wexpect.TIMEOUT or
				time() - start >= timeout):
				break
		return result

	def _terminate(self):
		""" Terminate running sudo subprocess """
		self.subprocess.sendcontrol("C")
		self._expect_timeout([wexpect.EOF], 10)
		if self.subprocess.after is wexpect.TIMEOUT:
			safe_print("Warning: sudo timed out")
			if not self.subprocess.terminate(force=True):
				safe_print("Warning: Couldn't terminate timed-out "
						   "sudo subprocess")
		else:
			safe_print(self.subprocess.before.strip().decode(enc, "replace"))

	def authenticate(self, args, title, parent=None):
		"""
		Athenticate for a given command
		
		The return value will be a tuple (auth_succesful, password).
		
		auth_succesful will be a custom class that will always have length 0 if
		authentication was not successful or the command is not allowed (even
		if the actual string length is non-zero), thus allowing for easy
		boolean comparisons.
		
		"""
		# Authentication using sudo is pretty convoluted if dealing with
		# platform and configuration differences. Ask for a password by first
		# clearing any cached credentials (sudo -K) so that sudo is guaranteed
		# to ask for a password if a command is run through it, then we spawn
		# sudo true (with true being the standard GNU utility that always
		# has an exit status of 0) and expect the password prompt. The user
		# is then given the opportunity to enter a password, which is then fed
		# to sudo. If sudo exits with a status of 0, the password must have
		# been accepted, but we still don't know for sure if our command is
		# allowed, so we run sudo -l <command> to determine if it is
		# indeed allowed.
		pwd = ""
		dlg = ConfirmDialog(
			parent, title=title, 
			msg=lang.getstr("dialog.enter_password"), 
			ok=lang.getstr("ok"), cancel=lang.getstr("cancel"), 
			bitmap=geticon(32, "lock"))
		dlg.pwd_txt_ctrl = wx.TextCtrl(dlg, -1, pwd, 
									   size=(320, -1), 
									   style=wx.TE_PASSWORD | 
											 wx.TE_PROCESS_ENTER)
		dlg.pwd_txt_ctrl.Bind(wx.EVT_TEXT_ENTER, 
							  lambda event: dlg.EndModal(wx.ID_OK))
		dlg.sizer3.Add(dlg.pwd_txt_ctrl, 1, 
					   flag=wx.TOP | wx.ALIGN_LEFT, border=12)
		dlg.ok.SetDefault()
		dlg.sizer0.SetSizeHints(dlg)
		dlg.sizer0.Layout()
		# Remove cached credentials
		self.kill()
		sudo_args = ["-p", "Password:", "true"]
		try:
			p = self.subprocess = wexpect.spawn(safe_str(self.sudo), sudo_args)
		except Exception, exception:
				return StringWithLengthOverride("Could not run %s %s: %s" %
												(self.sudo, " ".join(sudo_args),
												 exception), 0), pwd
		self._expect_timeout(["Password:", wexpect.EOF], 10)
		# We need to call isalive() to set the exitstatus
		while p.isalive() and p.after == "Password:":
			# Ask for password
			dlg.pwd_txt_ctrl.SetFocus()
			result = dlg.ShowModal()
			pwd = dlg.pwd_txt_ctrl.GetValue()
			if result != wx.ID_OK:
				self._terminate()
				return False, pwd
			p.send(pwd + os.linesep)
			self._expect_timeout(["Password:", wexpect.EOF], 10)
			if p.after == "Password:":
				msg = lang.getstr("dialog.enter_password")
				errstr = p.before.strip().decode(enc, "replace")
				if errstr:
					safe_print(errstr)
					msg = "\n\n".join([errstr, msg])
				dlg.message.SetLabel(msg)
				dlg.message.Wrap(dlg.GetSize()[0] - 32 - 12 * 2)
				dlg.pwd_txt_ctrl.SetValue("")
				dlg.sizer0.SetSizeHints(dlg)
				dlg.sizer0.Layout()
		dlg.Destroy()
		if p.after is wexpect.TIMEOUT:
			safe_print("Error: sudo timed out")
			if not p.terminate(force=True):
				safe_print("Warning: Couldn't terminate timed-out sudo "
						   "subprocess")
			return StringWithLengthOverride("sudo timed out", 0), pwd
		if p.exitstatus != 0:
			return StringWithLengthOverride(p.before.strip().decode(enc,
																	"replace") or
											("sudo exited prematurely with "
											 "status %s" % p.exitstatus), 0), pwd
		# Password was accepted, check if command is allowed
		return self.is_allowed(args, pwd), pwd

	def is_allowed(self, args=None, pwd=""):
		"""
		Check if a command is allowed via sudo. Return either a string
		listing allowed and forbidden commands, or the fully-qualified path of
		the command along with any arguments, or an error message in case the 
		command is not allowed, or False if the password was not accepted.
		
		The returned error is a custom class that will always have length 0
		if the command is not allowed (even if the actual string length is
		non-zero), thus allowing for easy boolean comparisons.
		
		"""
		sudo_args = ["-p", "Password:", "-l"]
		# Set sudo args based on available options
		if self.availoptions.get("l [command]") and args:
			sudo_args += args
		try:
			p = self.subprocess = wexpect.spawn(safe_str(self.sudo),
												sudo_args)
		except Exception, exception:
			return StringWithLengthOverride("Could not run %s %s: %s" %
											(self.sudo, " ".join(sudo_args),
											 exception), 0)
		self._expect_timeout(["Password:", wexpect.EOF], 10)
		# We need to call isalive() to set the exitstatus
		while p.isalive() and p.after == "Password:":
			p.send(pwd + os.linesep)
			self._expect_timeout(["Password:", wexpect.EOF], 10)
			if p.after == "Password:":
				# Password was not accepted
				self._terminate()
				return StringWithLengthOverride(p.before.strip().decode(enc,
																		"replace"),
												0)
		if p.after is wexpect.TIMEOUT:
			safe_print("Error: sudo timed out")
			if not p.terminate(force=True):
				safe_print("Warning: Couldn't terminate timed-out sudo "
						   "subprocess")
			return StringWithLengthOverride("sudo timed out", 0)
		if p.exitstatus != 0:
			return StringWithLengthOverride(p.before.strip().decode(enc,
																	"replace") or
											("sudo exited prematurely with "
											 "status %s" % p.exitstatus), 0)
		return p.before.strip().decode(enc, "replace")

	def kill(self):
		""" Remove cached credentials """
		kill_arg = None
		if self.availoptions.get("K"):
			kill_arg = "-K"
		elif self.availoptions.get("k"):
			kill_arg = "-k"
		if kill_arg:
			sp.call([safe_str(self.sudo), kill_arg])


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


class Worker(object):

	def __init__(self, owner=None):
		"""
		Create and return a new worker instance.
		"""
		self.owner = owner # owner should be a wxFrame or similar
		if sys.platform == "win32":
			self.pty_encoding = "cp%i" % windll.kernel32.GetACP()
		else:
			self.pty_encoding = enc
		self.cmdrun = False
		self.dispcal_create_fast_matrix_shaper = False
		self.dispread_after_dispcal = False
		self.finished = True
		self.instrument_on_screen = False
		self.interactive = False
		self.spotread_just_do_instrument_calibration = False
		self.lastcmdname = None
		# Filter out warnings from OS components (e.g. shared libraries)
		# E.g.:
		# Nov 26 16:28:16  dispcal[1006] <Warning>: void CGSUpdateManager::log() const: conn 0x1ec57 token 0x3ffffffffffd0a
		prestrip = re.compile(r"\D+\s+\d+\s+\d+:\d+:\d+\s+\w+\[\d+\]\s+<Warning>:[\S\s]*")
		discard = [r"[\*\.]+|Current (?:RGB|XYZ)(?: +.*)?"]
		self.lastmsg_discard = re.compile("|".join(discard))
		self.measurement_modes = {}
		# Sounds when measuring
		# Needs to be stereo!
		self.measurement_sound = audio.Sound(get_data_path("beep.wav"))
		self.commit_sound = audio.Sound(get_data_path("camera_shutter.wav"))
		self.options_colprof = []
		self.options_dispcal = []
		self.options_dispread = []
		self.options_targen = []
		self.pauseable = False
		discard = [r"^Display type is .+",
				   r"^Doing (?:some initial|check) measurements",
				   r"^Adjust .+? Press space when done\.\s*",
				   r"^\s*(?:[/\\]\s+)?(?:Adjusted )?(Current",
					   r"Initial",
					   r"[Tt]arget) (?:Br(?:ightness)?",
					   r"50% Level",
					   r"white",
					   r"(?:Near )?[Bb]lack",
					   r"(?:advertised )?gamma",
					   r"RGB",
					   r"\d(?:\.\d+)?).*",
				   r"^Gamma curve .+",
				   r"^Display adjustment menu:",
				   r"^Press",
				   r"^\d\).+",
				   r"^(?:1%|Black|Red|Green|Blue|White|Grey)\s+=.+",
				   r"^\s*patch \d+ of \d+.*",
				   r"^\s*point \d+.*",
				   r"^\s*Added \d+/\d+",
				   # These need to be last because they're very generic!
				   r"[\*\.]+",
				   r"\s*\d*%?"]
		self.recent_discard = re.compile("|".join(discard), re.I)
		self.subprocess_abort = False
		self.sudo = None
		self.auth_timestamp = 0
		self.sessionlogfiles = {}
		self.tempdir = None
		self.thread_abort = False
		self.triggers = ["Password:"]
		self.recent = FilteredStream(LineCache(maxlines=3), self.pty_encoding, 
									 discard=self.recent_discard,
									 triggers=self.triggers +
											  ["stopped at user request"],
									 prestrip=prestrip)
		self.lastmsg = FilteredStream(LineCache(), self.pty_encoding, 
									  discard=self.lastmsg_discard,
									  triggers=self.triggers,
									  prestrip=prestrip)
		self.clear_argyll_info()
		self.clear_cmd_output()
		self._patterngenerators = {}
		self._progress_dlgs = {}
		self._progress_wnd = None
		self._pwdstr = ""
		workers.append(self)
	
	def add_measurement_features(self, args, display=True,
								 ignore_display_name=False,
								 allow_nondefault_observer=False,
								 ambient=False):
		""" Add common options and to dispcal, dispread and spotread arguments """
		if display and not get_arg("-d", args):
			args.append("-d" + self.get_display())
		if not get_arg("-c", args):
			args.append("-c%s" % getcfg("comport.number"))
		instrument_name = self.get_instrument_name()
		measurement_mode = getcfg("measurement_mode")
		if measurement_mode == "auto":
			# Make changes in DisplayCAL.MainFrame.set_ccxx_measurement_mode too!
			if instrument_name == "ColorHug":
				measurement_mode = "R"
			elif instrument_name == "ColorHug2":
				measurement_mode = "F"
			else:
				measurement_mode = "l"
		instrument_features = self.get_instrument_features()
		if (not ambient and
			measurement_mode and not get_arg("-y", args) and
			instrument_name != "specbos 1201"):
				# Always specify -y for colorimeters (won't be read from .cal 
				# when updating)
				# The specbos 1201 (unlike 1211) doesn't support measurement
				# mode selection
				if self.argyll_version >= [1, 5, 0]:
					measurement_mode_map = instrument_features.get("measurement_mode_map",
																   {})
					measurement_mode = measurement_mode_map.get(measurement_mode[0],
																measurement_mode)
				args.append("-y" + measurement_mode[0])
		if getcfg("measurement_mode.projector") and \
		   instrument_features.get("projector_mode") and \
		   self.argyll_version >= [1, 1, 0] and not get_arg("-p", args):
			# Projector mode, Argyll >= 1.1.0 Beta
			args.append("-p")
		if instrument_features.get("adaptive_mode"):
			if getcfg("measurement_mode.adaptive"):
				if ((self.argyll_version[0:3] > [1, 1, 0] or
					 (self.argyll_version[0:3] == [1, 1, 0] and
					  not "Beta" in self.argyll_version_string and
					  not "RC1" in self.argyll_version_string and
					  not "RC2" in self.argyll_version_string)) and
					 self.argyll_version[0:3] < [1, 5, 0] and
					 not get_arg("-V", args, True)):
					# Adaptive measurement mode, Argyll >= 1.1.0 RC3
					args.append("-V")
			else:
				if self.argyll_version[0:3] >= [1, 5, 0]:
					# Disable adaptive measurement mode
					args.append("-YA")
		if (instrument_name in ("Spyder4", "Spyder5") and
			self.argyll_version == [1, 7, 0] and
			measurement_mode in ("f", "e") and
			not get_arg("-YR:", args)):
			# Prevent 'Warning - Spyder: measuring refresh rate failed'
			args.append("-YR:60")
		non_argyll_prisma = (config.get_display_name() == "Prisma" and
							 not defaults["patterngenerator.prisma.argyll"])
		if display and not (get_arg("-dweb", args) or get_arg("-dmadvr", args)):
			if ((self.argyll_version <= [1, 0, 4] and not get_arg("-p", args)) or 
				(self.argyll_version > [1, 0, 4] and not get_arg("-P", args))):
				if ((config.get_display_name() == "Resolve" or
				     non_argyll_prisma) and
					not ignore_display_name):
					# Move Argyll test window to lower right corner and make it
					# very small
					dimensions_measureframe = "1,1,0.01"
				else:
					dimensions_measureframe = getcfg("dimensions.measureframe")
					if get_arg("-dcc", args):
						# Rescale for Chromecast default patch size of 10%
						dimensions_measureframe = config.get_measureframe_dimensions(
							dimensions_measureframe, 10)
				args.append(("-p" if self.argyll_version <= [1, 0, 4] else "-P") + 
							dimensions_measureframe)
			farg = get_arg("-F", args, True)
			if ((config.get_display_name() == "Resolve" or
				 non_argyll_prisma) and not ignore_display_name):
				if farg:
					# Remove -F (darken background) as we relay colors to
					# pattern generator
					args = args[:farg[0]] + args[farg[0] + 1:]
			elif getcfg("measure.darken_background") and not farg:
				args.append("-F")
		if (display and config.get_display_name() == "Prisma" and
			defaults["patterngenerator.prisma.argyll"] and
			getcfg("patterngenerator.prisma.use_video_levels") and
			not get_arg("-E", args, True)):
			args.append("-E")
		if getcfg("measurement_mode.highres") and \
		   instrument_features.get("highres_mode") and not get_arg("-H", args,
																   True):
			args.append("-H")
		if (allow_nondefault_observer and
			self.instrument_can_use_nondefault_observer() and
			getcfg("observer") != defaults["observer"] and
			not get_arg("-Q", args)):
			args.append("-Q" + getcfg("observer"))
		if (not ambient and
			self.instrument_can_use_ccxx() and
		    not is_ccxx_testchart() and not get_arg("-X", args)):
			# Use colorimeter correction?
			ccmx = getcfg("colorimeter_correction_matrix_file").split(":", 1)
			if len(ccmx) > 1 and ccmx[1]:
				ccmx = ccmx[1]
			else:
				ccmx = None
			if ccmx and (not ccmx.lower().endswith(".ccss") or
						 self.instrument_supports_ccss()):
				result = check_file_isfile(ccmx)
				if isinstance(result, Exception):
					return result
				try:
					cgats = CGATS.CGATS(ccmx)
				except (IOError, CGATS.CGATSError), exception:
					return exception
				else:
					ccxx_instrument = get_canonical_instrument_name(
						str(cgats.queryv1("INSTRUMENT") or ""),
						{"DTP94-LCD mode": "DTP94",
						 "eye-one display": "i1 Display",
						 "Spyder 2 LCD": "Spyder2",
						 "Spyder 3": "Spyder3"})
				if ((ccxx_instrument and
					 instrument_name.lower().replace(" ", "") in
					 ccxx_instrument.lower().replace(" ", "")) or
					ccmx.lower().endswith(".ccss")):
					tempdir = self.create_tempdir()
					if isinstance(tempdir, Exception):
						return tempdir
					ccmxcopy = os.path.join(tempdir, 
											os.path.basename(ccmx))
					if not os.path.isfile(ccmxcopy):
						if 0 in cgats and cgats[0].type.strip() == "CCMX":
							# Add display base ID if missing
							self.check_add_display_type_base_id(cgats)
						try:
							# Copy ccmx to profile dir
							cgats.write(ccmxcopy) 
						except Exception, exception:
							return Error(lang.getstr("error.copy_failed", 
													 (ccmx, ccmxcopy)) + 
													 "\n\n" + 
													 safe_unicode(exception))
						result = check_file_isfile(ccmxcopy)
						if isinstance(result, Exception):
							return result
					args.append("-X")
					args.append(os.path.basename(ccmxcopy))
		if (display and (getcfg("drift_compensation.blacklevel") or 
						 getcfg("drift_compensation.whitelevel")) and
			self.argyll_version >= [1, 3, 0] and not get_arg("-I", args)):
			args.append("-I")
			if getcfg("drift_compensation.blacklevel"):
				args[-1] += "b"
			if getcfg("drift_compensation.whitelevel"):
				args[-1] += "w"
		# TTBD/FIXME: Skipping of sensor calibration can't be done in
		# emissive mode (see Argyll source spectro/ss.c, around line 40)
		if (getcfg("allow_skip_sensor_cal") and
			instrument_features.get("skip_sensor_cal") and
			self.argyll_version >= [1, 1, 0] and not get_arg("-N", args, True) and
			not self.spotread_just_do_instrument_calibration):
			args.append("-N")
		return True
	
	def authenticate(self, cmd, title=appname, parent=None):
		"""
		Athenticate (using sudo) for a given command
		
		The return value will either be True (authentication successful and
		command allowed), False (in case of the user cancelling the password
		dialog), None (Windows or running as root) or an error.
		
		"""
		if sys.platform == "win32" or os.geteuid() == 0:
			return
		self.auth_timestamp = 0
		ocmd = cmd
		if cmd and not os.path.isabs(cmd):
			cmd = get_argyll_util(ocmd)
			if not cmd:
				cmd = which(ocmd)
		if not cmd or not os.path.isfile(cmd):
			return Error(lang.getstr("file.missing", ocmd))
		_disabler = BetterWindowDisabler()
		result = True
		if not self.sudo:
			self.sudo = Sudo()
			if not self.sudo:
				result = Error(lang.getstr("file.missing", "sudo"))
		if result is True:
			pwd = self.pwd
			args = [cmd, "-?"]
			if not pwd or not self.sudo.is_allowed(args, pwd):
				# If no password was previously available, or if the requested
				# command cannot be run via sudo regardless of password (we check
				# this with sudo -l <command>), we ask for a password.
				safe_print(lang.getstr("auth"))
				progress_dlg = self._progress_wnd or getattr(wx.GetApp(),
															 "progress_dlg", None)
				if parent is None:
					if progress_dlg and progress_dlg.IsShownOnScreen():
						parent = progress_dlg
					else:
						parent = self.owner
				result, pwd = self.sudo.authenticate(args, title, parent)
				if result:
					self.pwd = pwd
					result = True
				elif result is False:
					safe_print(lang.getstr("aborted"))
				else:
					result = Error(result)
			if result is True:
				self.auth_timestamp = time()
		del _disabler
		return result

	def blend_profile_blackpoint(self, profile1, profile2, outoffset=0.0,
								 gamma=2.4, gamma_type="B", size=None,
								 apply_trc=True, white_cdm2=100):
		"""
		Apply BT.1886-like tone response to profile1 using profile2 blackpoint.
		
		profile1 has to be a matrix profile
		
		"""
		odata = self.xicclu(profile2, (0, 0, 0), pcs="x")
		if len(odata) != 1 or len(odata[0]) != 3:
			raise ValueError("Blackpoint is invalid: %s" % odata)
		XYZbp = odata[0]
		smpte2084 = gamma in ("smpte2084.hardclip", "smpte2084.rolloffclip")
		if smpte2084:
			outoffset = 1.0
			self.log(appname + ": Applying " + lang.getstr("trc." + gamma) +
					 " TRC to " + os.path.basename(profile1.fileName))
		elif apply_trc:
			self.log(appname + ": Applying BT.1886-like TRC to " +
					 os.path.basename(profile1.fileName))
		else:
			self.log(appname + ": Applying BT.1886-like black offset to " +
					 os.path.basename(profile1.fileName))
		self.log(appname + ": Black XYZ (normalized 0..100) = %.6f %.6f %.6f" %
				 tuple([v * 100 for v in XYZbp]))
		self.log(appname + ": Black Lab = %.6f %.6f %.6f" %
				 tuple(colormath.XYZ2Lab(*[v * 100 for v in XYZbp])))
		self.log(appname + ": Output offset = %.2f%%" % (outoffset * 100))
		if smpte2084:
			profile1.set_smpte2084_trc((0, 0, 0), white_cdm2,
									   rolloff=gamma == "smpte2084.rolloffclip")
		if not apply_trc or smpte2084:
			# Apply only the black point blending portion of BT.1886 mapping
			profile1.apply_black_offset(XYZbp)
			return
		if gamma_type in ("b", "g"):
			# Get technical gamma needed to achieve effective gamma
			self.log(appname + ": Effective gamma = %.2f" % gamma)
			tgamma = colormath.xicc_tech_gamma(gamma, XYZbp[1], outoffset)
		else:
			tgamma = gamma
		self.log(appname + ": Technical gamma = %.2f" % tgamma)
		profile1.set_bt1886_trc(XYZbp, outoffset, gamma, gamma_type, size)

	def calibrate_instrument_producer(self):
		cmd, args = get_argyll_util("spotread"), ["-v", "-e"]
		if cmd:
			result = self.add_measurement_features(args, display=False)
			if isinstance(result, Exception):
				return result
			self.spotread_just_do_instrument_calibration = True
			result = self.exec_cmd(cmd, args, skip_scripts=True)
			self.spotread_just_do_instrument_calibration = False
			return result
		else:
			return Error(lang.getstr("argyll.util.not_found", "spotread"))
	
	def instrument_can_use_ccxx(self, check_measurement_mode=True,
								instrument_name=None):
		"""
		Return boolean whether the instrument in its current measurement mode
		can use a CCMX or CCSS colorimeter correction
		
		"""
		# Special cases:
		# Spectrometer (not needed), 
		# ColorHug (only sensible in factory or raw measurement mode),
		# ColorMunki Smile (only generic LCD CCFL measurement mode),
		# Colorimétre HCFR (only raw measurement mode),
		# DTP94 (only LCD, refresh and generic measurement modes)
		# Spyder4/5 (only generic LCD and refresh measurement modes)
		# K-10 (only factory measurement mode)

		# IMPORTANT: Make changes aswell in the following locations:
		# - DisplayCAL.MainFrame.create_colorimeter_correction_handler
		# - DisplayCAL.MainFrame.get_ccxx_measurement_modes
		# - DisplayCAL.MainFrame.set_ccxx_measurement_mode
		# - DisplayCAL.MainFrame.update_colorimeter_correction_matrix_ctrl_items
		# - worker.Worker.check_add_display_type_base_id
		if not instrument_name:
			instrument_name = self.get_instrument_name()
		return (self.argyll_version >= [1, 3, 0] and
				not self.get_instrument_features(instrument_name).get("spectral") and
				(not check_measurement_mode or
				 getcfg("measurement_mode") == "auto" or
				 ((instrument_name not in ("ColorHug", "ColorHug2") or
				   getcfg("measurement_mode") in ("F", "R")) and
				  (instrument_name != "ColorMunki Smile" or
				   getcfg("measurement_mode") == "f") and
				  (instrument_name != "Colorimtre HCFR" or  # Missing é is NOT a typo
				   getcfg("measurement_mode") == "R") and
				  (instrument_name != "DTP94" or
				   getcfg("measurement_mode") in ("l", "c", "g")) and
				  (instrument_name not in ("Spyder4", "Spyder5") or
				   getcfg("measurement_mode") in ("l", "c")) and
				  (instrument_name != "K-10" or
				   getcfg("measurement_mode") == "F"))))

	def instrument_can_use_nondefault_observer(self, instrument_name=None):
		if not instrument_name:
			instrument_name = self.get_instrument_name()
		return bool(self.get_instrument_features(instrument_name).get("spectral") or
					self.instrument_supports_ccss(instrument_name))
	
	@Property
	def progress_wnd():
		def fget(self):
			if not self._progress_wnd:
				if (getattr(self, "progress_start_timer", None) and
					self.progress_start_timer.IsRunning()):
					if currentThread().__class__ is not _MainThread:
						raise RuntimeError("GUI access in non-main thread!")
					# Instantiate the progress dialog instantly on access
					self.progress_start_timer.Notify()
					self.progress_start_timer.Stop()
			return self._progress_wnd
		
		def fset(self, progress_wnd):
			self._progress_wnd = progress_wnd
		
		return locals()

	@property
	def progress_wnds(self):
		progress_wnds = self._progress_dlgs.values()
		if hasattr(self, "terminal"):
			progress_wnds.append(self.terminal)
		return progress_wnds

	@Property
	def pwd():
		def fget(self):
			return self._pwdstr[10:].ljust(int(math.ceil(len(self._pwdstr[10:]) / 4.0) * 4),
										  "=").decode("base64").decode("UTF-8")
		
		def fset(self, pwd):
			self._pwdstr = "/tmp/%s%s" % (md5(getpass.getuser()).hexdigest().encode("base64")[:5],
										  pwd.encode("UTF-8").encode("base64").rstrip("=\n"))
		
		return locals()

	def get_argyll_instrument_conf(self, what=None):
		""" Check for Argyll CMS udev rules/hotplug scripts """
		filenames = []
		if what == "installed":
			for filename in ("/etc/udev/rules.d/55-Argyll.rules",
							 "/etc/udev/rules.d/45-Argyll.rules",
							 "/etc/hotplug/Argyll",
							 "/etc/hotplug/Argyll.usermap",
							 "/lib/udev/rules.d/55-Argyll.rules",
							 "/lib/udev/rules.d/69-cd-sensors.rules"):
				if os.path.isfile(filename):
					filenames.append(filename)
		else:
			if what == "expected":
				fn = lambda filename: filename
			else:
				fn = get_data_path
			if os.path.isdir("/etc/udev/rules.d"):
				if glob.glob("/dev/bus/usb/*/*"):
					# USB and serial instruments using udev, where udev 
					# already creates /dev/bus/usb/00X/00X devices
					filenames.append(fn("usb/55-Argyll.rules"))
				else:
					# USB using udev, where there are NOT /dev/bus/usb/00X/00X 
					# devices
					filenames.append(fn("usb/45-Argyll.rules"))
			else:
				if os.path.isdir("/etc/hotplug"):
					# USB using hotplug and Serial using udev
					# (older versions of Linux)
					filenames.extend(fn(filename) for filename in
									 ("usb/Argyll", "usb/Argyll.usermap"))
		return filter(lambda filename: filename, filenames)

	def check_add_display_type_base_id(self, cgats, cfgname="measurement_mode"):
		""" Add DISPLAY_TYPE_BASE_ID to CCMX """
		if not cgats.queryv1("DISPLAY_TYPE_BASE_ID"):
			# c, l (most colorimeters)
			# R (ColorHug and Colorimétre HCFR)
			# F (ColorHug)
			# f (ColorMunki Smile)
			# g (DTP94)

			# IMPORTANT: Make changes aswell in the following locations:
			# - DisplayCAL.MainFrame.create_colorimeter_correction_handler
			# - DisplayCAL.MainFrame.get_ccxx_measurement_modes
			# - DisplayCAL.MainFrame.set_ccxx_measurement_modes
			# - DisplayCAL.MainFrame.update_colorimeter_correction_matrix_ctrl_items
			# - worker.Worker.instrument_can_use_ccxx
			cgats[0].add_keyword("DISPLAY_TYPE_BASE_ID",
							     {"c": 2,
								  "l": 1,
								  "R": 2,
								  "F": 1,
								  "f": 1,
								  "g": 3}.get(getcfg(cfgname), 1))
			safe_print("Added DISPLAY_TYPE_BASE_ID %r" %
					   cgats[0].DISPLAY_TYPE_BASE_ID)
	
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
	
	def check_is_ambient_measuring(self, txt):
		if (("ambient light measuring" in txt.lower() or
			 "Will use emissive mode instead" in txt) and
			not getattr(self, "is_ambient_measuring", False)):
			self.is_ambient_measuring = True
		if (getattr(self, "is_ambient_measuring", False) and
			"Place instrument on spot to be measured" in txt):
			self.is_ambient_measuring = False
			self.do_ambient_measurement()
	
	def do_ambient_measurement(self):
		if getattr(self, "subprocess_abort", False) or \
		   getattr(self, "thread_abort", False):
			# If we are aborting, ignore request
			return
		self.progress_wnd.Pulse(" " * 4)
		dlg = ConfirmDialog(self.progress_wnd,
							msg=lang.getstr("instrument.measure_ambient"), 
							ok=lang.getstr("ok"), 
							cancel=lang.getstr("cancel"), 
							bitmap=geticon(32, "dialog-information"))
		self.progress_wnd.dlg = dlg
		dlg_result = dlg.ShowModal()
		dlg.Destroy()
		if self.finished:
			return
		if dlg_result != wx.ID_OK:
			self.abort_subprocess()
			return False
		if self.safe_send(" "):
			self.progress_wnd.Pulse(lang.getstr("please_wait"))
	
	def check_instrument_calibration(self, txt):
		""" Check if current instrument needs sensor calibration by looking
		at Argyll CMS command output """
		if not self.instrument_calibration_complete:
			if "calibration complete" in txt.lower():
				self.instrument_calibration_complete = True
			else:
				for calmsg in INST_CAL_MSGS:
					if calmsg in txt or "calibration failed" in txt.lower():
						self.do_instrument_calibration(
							"calibration failed" in txt.lower())
						break
	
	def check_instrument_place_on_screen(self, txt):
		""" Check if instrument should be placed on screen by looking
		at Argyll CMS command output """
		if "place instrument on test window" in txt.lower():
			self.instrument_place_on_screen_msg = True
		if ((self.instrument_place_on_screen_msg and
			 "key to continue" in txt.lower()) or
			(self.instrument_calibration_complete and
			 "place instrument on spot" in txt.lower() and
			 self.progress_wnd is getattr(self, "terminal", None))):
			self.instrument_place_on_screen_msg = False
			if (self.cmdname == get_argyll_utilname("dispcal") and
				sys.platform == "darwin"):
				# On the Mac dispcal's test window
				# hides the cursor and steals focus
				start_new_thread(mac_app_activate, (1, wx.GetApp().AppName))
			if (self.instrument_calibration_complete or
				((config.is_untethered_display() or
				  getcfg("measure.darken_background") or
				  self.madtpg_fullscreen is False) and
				 (not self.dispread_after_dispcal or
				  self.cmdname == get_argyll_utilname("dispcal")) and
				  not self.instrument_on_screen)):
				# Show a dialog asking user to place the instrument on the
				# screen if the instrument calibration was completed,
				# or if we measure a remote ("Web") display,
				# or if we use a black background during measurements,
				# but in case of the latter two only if dispread is not
				# run directly after dispcal
				self.instrument_calibration_complete = False
				self.instrument_place_on_screen()
			else:
				if self.isalive():
					# Delay to work-around a problem with i1D2 and Argyll 1.7
					# to 1.8.3 under Mac OS X 10.11 El Capitan where skipping
					# interactive display adjustment would botch the first
					# reading (black)
					wx.CallLater(1500, self.instrument_on_screen_continue)

	def instrument_on_screen_continue(self):
		self.safe_send(" ")
		self.pauseable_now = True
		self.instrument_on_screen = True
	
	def check_instrument_sensor_position(self, txt):
		""" Check instrument sensor position by looking
		at Argyll CMS command output """
		if "read failed due to the sensor being in the wrong position" in txt.lower():
			self.instrument_sensor_position_msg = True
		if (self.instrument_sensor_position_msg and
			" or q to " in txt.lower()):
			self.instrument_sensor_position_msg = False
			self.instrument_reposition_sensor()
	
	def check_retry_measurement(self, txt):
		if ("key to retry:" in txt and
			not "read stopped at user request!"
			in self.recent.read() and
			("Sample read failed due to misread"
			 in self.recent.read() or 
			 "Sample read failed due to communication problem"
			 in self.recent.read()) and
			not self.subprocess_abort):
			self.retrycount += 1
			self.recent.write("\r\n%s: Retrying (%s)..." % 
							  (appname, self.retrycount))
			self.safe_send(" ")
	
	def check_spotread_result(self, txt):
		""" Check if spotread returned a result """
		if (self.cmdname == get_argyll_utilname("spotread") and
			self.progress_wnd is not getattr(self, "terminal", None) and
			("Result is XYZ:" in txt or "Result is Y:" in txt or
			 (self.instrument_calibration_complete and
			  self.spotread_just_do_instrument_calibration))):
			# Single spotread reading, we are done
			wx.CallLater(1000, self.quit_terminate_cmd)
	
	def do_instrument_calibration(self, failed=False):
		""" Ask user to initiate sensor calibration and execute.
		Give an option to cancel. """
		if getattr(self, "subprocess_abort", False) or \
		   getattr(self, "thread_abort", False):
			# If we are aborting, ignore request
			return
		self.progress_wnd.Pulse(" " * 4)
		if failed:
			msg = lang.getstr("failure")
		elif self.get_instrument_name() == "ColorMunki":
			msg = lang.getstr("instrument.calibrate.colormunki")
		else:
			serial = re.search("Serial no. (\S+)", self.recent.read(), re.I)
			if serial:
				# Reflective calibration, white reference tile required
				# (e.g. i1 Pro hires mode)
				msg = lang.getstr("instrument.calibrate.reflective",
								  serial.group(1))
			else:
				# Emissive dark calibration
				msg = lang.getstr("instrument.calibrate")
		dlg = ConfirmDialog(self.progress_wnd, msg=msg +
							"\n\n" + self.get_instrument_name(), 
							ok=lang.getstr("ok"), 
							cancel=lang.getstr("cancel"), 
							bitmap=geticon(32, "dialog-information"))
		self.progress_wnd.dlg = dlg
		dlg_result = dlg.ShowModal()
		dlg.Destroy()
		if self.finished:
			return
		if dlg_result != wx.ID_OK:
			self.abort_subprocess()
			return False
		self.progress_wnd.Pulse(lang.getstr("please_wait"))
		if self.safe_send(" "):
			self.progress_wnd.Pulse(lang.getstr("instrument.calibrating"))

	def abort_all(self, confirm=False):
		aborted = False
		for worker in workers:
			if not getattr(worker, "finished", True):
				worker.abort_subprocess(confirm)
				aborted = True
		return aborted
	
	def abort_subprocess(self, confirm=False):
		""" Abort the current subprocess or thread """
		if getattr(self, "abort_requested", False):
			return
		self.abort_requested = True
		if confirm and getattr(self, "progress_wnd", None):
			prev_dlg = getattr(self.progress_wnd, "dlg", None)
			if (prev_dlg and prev_dlg.IsShownOnScreen() and
				not isinstance(prev_dlg, DummyDialog)):
				self.abort_requested = False
				return
			pause = (not getattr(self.progress_wnd, "paused", False) and
					 hasattr(self.progress_wnd, "pause_continue_handler"))
			if pause:
				self.progress_wnd.pause_continue_handler(True)
				self.pause_continue()
			dlg = ConfirmDialog(self.progress_wnd,
								msg=lang.getstr("dialog.confirm_cancel"), 
								ok=lang.getstr("yes"), 
								cancel=lang.getstr("no"), 
								bitmap=geticon(32, "dialog-warning"))
			self.progress_wnd.dlg = dlg
			dlg_result = dlg.ShowModal()
			if isinstance(prev_dlg, DummyDialog):
				self.progress_wnd.dlg = prev_dlg
			dlg.Destroy()
			if dlg_result != wx.ID_OK:
				self.progress_wnd.Resume()
				self.abort_requested = False
				return
		self.patch_count = 0
		self.subprocess_abort = True
		self.thread_abort = True
		if self.use_patterngenerator or self.use_madnet_tpg:
			abortfilename = os.path.join(self.tempdir, ".abort")
			open(abortfilename, "w").close()
		delayedresult.startWorker(self.quit_terminate_consumer, 
								  self.quit_terminate_cmd)

	def quit_terminate_consumer(self, delayedResult):
		try:
			result = delayedResult.get()
		except Exception, exception:
			if hasattr(exception, "originalTraceback"):
				self.log(exception.originalTraceback, fn=log)
			else:
				self.log(traceback.format_exc(), fn=log)
			result = UnloggedError(exception)
		if isinstance(result, Exception):
			show_result_dialog(result, getattr(self, "progress_wnd", None))
			result = False
		if not result:
			self.subprocess_abort = False
			self.thread_abort = False
			self.abort_requested = False
			if hasattr(self, "progress_wnd"):
				self.progress_wnd.Resume()
	
	def instrument_place_on_screen(self):
		""" Show a dialog asking user to place the instrument on the screen
		and give an option to cancel """
		if getattr(self, "subprocess_abort", False) or \
		   getattr(self, "thread_abort", False):
			# If we are aborting, ignore request
			return
		self.progress_wnd.Pulse(" " * 4)
		dlg = ConfirmDialog(self.progress_wnd,
							msg=lang.getstr("instrument.place_on_screen") +
							"\n\n" + self.get_instrument_name(), 
							ok=lang.getstr("ok"), 
							cancel=lang.getstr("cancel"), 
							bitmap=geticon(32, "dialog-information"))
		self.progress_wnd.dlg = dlg
		dlg_result = dlg.ShowModal()
		dlg.Destroy()
		if self.finished:
			return
		if dlg_result != wx.ID_OK:
			self.abort_subprocess()
			return False
		if not isinstance(self.progress_wnd, (UntetheredFrame,
											  DisplayUniformityFrame)):
			self.safe_send(" ")
			self.pauseable_now = True
		self.instrument_on_screen = True
	
	def instrument_reposition_sensor(self):
		if getattr(self, "subprocess_abort", False) or \
		   getattr(self, "thread_abort", False):
			# If we are aborting, ignore request
			return
		self.progress_wnd.Pulse(" " * 4)
		dlg = ConfirmDialog(self.progress_wnd,
							msg=lang.getstr("instrument.reposition_sensor"), 
							ok=lang.getstr("ok"), 
							cancel=lang.getstr("cancel"), 
							bitmap=geticon(32, "dialog-warning"))
		self.progress_wnd.dlg = dlg
		dlg_result = dlg.ShowModal()
		dlg.Destroy()
		if self.finished:
			return
		if dlg_result != wx.ID_OK:
			self.abort_subprocess()
			return False
		self.safe_send(" ")
	
	def clear_argyll_info(self):
		"""
		Clear Argyll CMS version, detected displays and instruments.
		"""
		self.argyll_bin_dir = None
		self.argyll_version = [0, 0, 0]
		self.argyll_version_string = "0.0.0"
		self._displays = []
		self.display_edid = []
		self.display_manufacturers = []
		self.display_names = []
		self.display_rects = []
		self.displays = []
		self.instruments = []
		self.lut_access = []

	def clear_cmd_output(self):
		"""
		Clear any output from the last run command.
		"""
		self.cmd = None
		self.cmdname = None
		self.retcode = -1
		self.output = []
		self.errors = []
		self.recent.clear()
		self.retrycount = 0
		self.lastmsg.clear()
		self.repeat = False
		self.send_buffer = None
		# Log interaction with Argyll tools
		if (not hasattr(self, "logger") or
			(isinstance(self.logger, DummyLogger) and self.owner and
			 self.owner.Name == "mainframe")):
			if not self.owner or self.owner.Name != "mainframe":
				self.logger = DummyLogger()
			else:
				self.logger = get_file_logger("interact")
		if (hasattr(self, "thread") and self.thread.isAlive() and
			self.interactive):
			self.logger.info("-" * 80)
		self.sessionlogfile = None
		self.madtpg_fullscreen = None
		self.use_madnet_tpg = False
		self.use_patterngenerator = False
		self.patch_sequence = False
		self.patch_count = 0
		self.patterngenerator_sent_count = 0
		self.exec_cmd_returnvalue = None
		self.tmpfiles = {}
		self.buffer = []

	def create_3dlut(self, profile_in, path, profile_abst=None, profile_out=None,
					 apply_cal=True, intent="r", format="cube",
					 size=17, input_bits=10, output_bits=12, maxval=1.0,
					 input_encoding="n", output_encoding="n",
					 trc_gamma=None, trc_gamma_type="B", trc_output_offset=0.0,
					 save_link_icc=True, apply_black_offset=True,
					 use_b2a=False, white_cdm2=100):
		""" Create a 3D LUT from one (device link) or two (device) profiles,
		optionally incorporating an abstract profile. """
		# .cube: http://doc.iridas.com/index.php?title=LUT_Formats
		# .3dl: http://www.kodak.com/US/plugins/acrobat/en/motion/products/look/UserGuide.pdf
		#       http://download.autodesk.com/us/systemdocs/pdf/lustre_color_management_user_guide.pdf
		# .spi3d: https://github.com/imageworks/OpenColorIO/blob/master/src/core/FileFormatSpi3D.cpp
		# .mga: http://pogle.pandora-int.com/download/manual/lut3d_format.html
		
		for profile in (profile_in, profile_out):
			if (profile.profileClass not in ("mntr", "link", "scnr", "spac") or 
				profile.colorSpace != "RGB"):
				raise NotImplementedError(lang.getstr("profile.unsupported", 
													  (profile.profileClass, 
													   profile.colorSpace)))
			if profile_in.profileClass == "link":
				break
		
		# Setup temp dir
		cwd = self.create_tempdir()
		if isinstance(cwd, Exception):
			raise cwd

		result = None

		path = os.path.split(path)
		path = os.path.join(path[0], make_argyll_compatible_path(path[1]))
		filename, ext = os.path.splitext(path)
		name = os.path.basename(filename)
		
		if profile_in.profileClass == "link":
			link_basename = os.path.basename(profile_in.fileName)
			link_filename = os.path.join(cwd, link_basename)
			profile_in.write(link_filename)
		else:
			# Check if files are the same
			if profile_in.isSame(profile_out, force_calculation=True):
				raise Error(lang.getstr("error.source_dest_same"))
			
			# Prepare building a device link
			link_basename = name + profile_ext
			link_filename = os.path.join(cwd, link_basename)

			profile_in_basename = make_argyll_compatible_path(os.path.basename(profile_in.fileName))
			profile_out_basename = make_argyll_compatible_path(os.path.basename(profile_out.fileName))
			if profile_in_basename == profile_out_basename:
				(profile_out_filename,
				 profile_out_ext) = os.path.splitext(profile_out_basename)
				profile_out_basename = "%s (2)%s" % (profile_out_filename,
													 profile_out_ext)
			profile_out.fileName = os.path.join(cwd, profile_out_basename)
			profile_out.write()
			profile_out_cal_path = os.path.splitext(profile_out.fileName)[0] + ".cal"
			
			manufacturer = profile_out.getDeviceManufacturerDescription()
			model = profile_out.getDeviceModelDescription()
			device_manufacturer = profile_out.device["manufacturer"]
			device_model = profile_out.device["model"]
			mmod = profile_out.tags.get("mmod")
			
			self.sessionlogfile = LogFile(name, cwd)
			self.sessionlogfiles[name] = self.sessionlogfile
			
			# Apply calibration?
			if apply_cal:
				# Get the calibration from profile vcgt
				if not profile_out.tags.get("vcgt", None):
					raise Error(lang.getstr("profile.no_vcgt"))
				try:
					cgats = vcgt_to_cal(profile_out)
				except (IOError, CGATS.CGATSInvalidError, 
						CGATS.CGATSInvalidOperationError, CGATS.CGATSKeyError, 
						CGATS.CGATSTypeError, CGATS.CGATSValueError), exception:
					raise Error(lang.getstr("cal_extraction_failed"))
				cgats.write(profile_out_cal_path)
				
				if self.argyll_version < [1, 6]:
					# Can't apply the calibration with old collink versions -
					# apply the calibration to the 'out' profile prior to
					# device linking instead
					applycal = get_argyll_util("applycal")
					if not applycal:
						raise Error(lang.getstr("argyll.util.not_found",
												"applycal"))
					safe_print(lang.getstr("apply_cal"))
					result = self.exec_cmd(applycal, ["-v",
													  profile_out_cal_path,
													  profile_out_basename,
													  profile_out.fileName],
										   capture_output=True,
										   skip_scripts=True,
										   sessionlogfile=self.sessionlogfile)
					if isinstance(result, Exception) and not getcfg("dry_run"):
						raise result
					elif not result:
						raise Error("\n\n".join([lang.getstr("apply_cal.error"),
												 "\n".join(self.errors)]))
					profile_out = ICCP.ICCProfile(profile_out.fileName)

			# Deal with applying TRC
			collink_version_string = get_argyll_version_string("collink")
			collink_version = parse_argyll_version_string(collink_version_string)
			smpte2084 = trc_gamma in ("smpte2084.hardclip",
									 "smpte2084.rolloffclip")
			if trc_gamma:
				if (not smpte2084 and
					(collink_version >= [1, 7] or not trc_output_offset)):
					# Make sure the profile has the expected Rec. 709 TRC
					# for BT.1886
					self.log(appname + ": Applying Rec. 709 TRC to " +
							 os.path.basename(profile_in.fileName))
					for i, channel in enumerate(("r", "g", "b")):
						if channel + "TRC" in profile_in.tags:
							profile_in.tags[channel + "TRC"].set_trc(-709)
				else:
					# For SMPTE 2084 and Argyll < 1.7 beta, alter profile TRC
					# Argyll CMS prior to 1.7 beta development code 2014-07-10
					# does not support output offset, alter the source profile
					# instead (note that accuracy is limited due to 16-bit
					# encoding used in ICC profile, collink 1.7 can use full
					# floating point processing and will be more precise)
					self.blend_profile_blackpoint(profile_in, profile_out,
												  trc_output_offset, trc_gamma,
												  trc_gamma_type,
												  white_cdm2=white_cdm2)
			elif apply_black_offset:
				# Apply only the black point blending portion of BT.1886 mapping
				self.blend_profile_blackpoint(profile_in, profile_out, 1.0,
											  apply_trc=False)
			profile_in.fileName = os.path.join(cwd, profile_in_basename)
			profile_in.write()

			# Now build the device link
			collink = get_argyll_util("collink")
			if not collink:
				raise Error(lang.getstr("argyll.util.not_found", "collink"))
			is_argyll_lut_format = (self.argyll_version >= [1, 6] and
									(((format == "eeColor" or
									   (format == "cube" and
										collink_version >= [1, 7])) and
									  not test) or
									 format == "madVR") or format == "icc")
			args = ["-v", "-qh", "-g" if use_b2a else "-G", "-i%s" % intent,
					"-r%i" % size, "-n"]
			if profile_abst:
				profile_abst.write(os.path.join(cwd, "abstract.icc"))
				args.extend(["-p", "abstract.icc"])
			if self.argyll_version >= [1, 6]:
				if format == "madVR":
					args.append("-3m")
				elif format == "eeColor" and not test:
					args.append("-3e")
				elif (format == "cube" and collink_version >= [1, 7] and
					  not test):
					args.append("-3c")
				args.append("-e%s" % input_encoding)
				args.append("-E%s" % output_encoding)
				if (((trc_gamma and trc_gamma_type in ("b", "B")) or
					 (not trc_gamma and apply_black_offset)) and
					collink_version >= [1, 7]):
					args.append("-b")  # Use RGB->RGB forced black point hack
				if (trc_gamma and not smpte2084 and
					trc_gamma_type in ("b", "B")):
					if collink_version >= [1, 7]:
						args.append("-I%s:%s:%s" % (trc_gamma_type,
													trc_output_offset,
													trc_gamma))
					elif not trc_output_offset:
						args.append("-I%s:%s" % (trc_gamma_type, trc_gamma))
				if apply_cal:
					# Apply the calibration when building our device link
					# i.e. use collink -a parameter (apply calibration curves
					# to link output and append linear)
					args.extend(["-a", os.path.basename(profile_out_cal_path)])
			if getcfg("extra_args.collink").strip():
				args += parse_argument_string(getcfg("extra_args.collink"))
			result = self.exec_cmd(collink, args + [profile_in_basename,
													profile_out_basename,
													link_filename],
								   capture_output=True, skip_scripts=True)

			if (result and not isinstance(result, Exception) and
				save_link_icc and
				os.path.isfile(link_filename)):
				profile_link = ICCP.ICCProfile(link_filename)
				profile_link.setDescription(name)
				profile_link.setCopyright(getcfg("copyright"))
				if manufacturer:
					profile_link.setDeviceManufacturerDescription(manufacturer)
				if model:
					profile_link.setDeviceModelDescription(model)
				profile_link.device["manufacturer"] = device_manufacturer
				profile_link.device["model"] = device_model
				if mmod:
					profile_link.tags.mmod = mmod
				profile_link.tags.meta = ICCP.DictType()
				profile_link.tags.meta.update([("CMF_product", appname),
											   ("CMF_binary", appname),
											   ("CMF_version", version),
											   ("collink.args",
											    sp.list2cmdline(
												   args + [profile_in_basename,
														   profile_out_basename,
														   link_basename])),
											   ("collink.version", collink_version_string),
											   ("encoding.input", input_encoding),
											   ("encoding.output", output_encoding)])
				profile_link.calculateID()
				profile_link.write(filename + profile_ext)

			if is_argyll_lut_format:
				# Collink has already written the 3DLUT for us
				result2 = self.wrapup(not isinstance(result, UnloggedInfo) and
									  result, dst_path=path,
									  ext_filter=[".3dlut", ".cube",
												  ".log", ".txt"])
				if not result:
					result = UnloggedError(lang.getstr("aborted"))
				if isinstance(result2, Exception):
					if isinstance(result, Exception):
						result = Error(safe_unicode(result) + "\n\n" +
									   safe_unicode(result2))
					else:
						result = result2
				if not isinstance(result, Exception):
					return

			if isinstance(result, Exception):
				raise result
			elif not result:
				raise UnloggedError(lang.getstr("aborted"))

		# We have to create the 3DLUT ourselves

		# Create input RGB values
		RGB_in = []
		RGB_indexes = []
		seen = {}
		if format == "eeColor":
			# Fixed size
			size = 65
		elif format == "ReShade":
			format = "png"
		step = 1.0 / (size - 1)
		RGB_triplet = [0.0, 0.0, 0.0]
		RGB_index = [0, 0, 0]
		# Set the fastest and slowest changing columns, from right to left
		if (format in ("3dl", "mga", "spi3d") or
			(format == "png" and getcfg("3dlut.image.order") == "bgr")):
			columns = (0, 1, 2)
		elif format == "eeColor":
			columns = (2, 0, 1)
		else:
			columns = (2, 1, 0)
		for i in xrange(0, size):
			# Red
			RGB_triplet[columns[0]] = step * i
			RGB_index[columns[0]] = i
			for j in xrange(0, size):
				# Green
				RGB_triplet[columns[1]] = step * j
				RGB_index[columns[1]] = j
				for k in xrange(0, size):
					# Blue
					RGB_triplet[columns[2]] = step * k
					RGB_copy = list(RGB_triplet)
					if format == "eeColor":
						# eeColor cLUT is fake 65^3 - only 64^3 is usable.
						# This affects full range and xvYCC RGB, so un-map
						# inputs to cLUT to only use 64^3
						if input_encoding == "n":
							for l in xrange(3):
								RGB_copy[l] = min(RGB_copy[l] * (size - 1.0) /
												  (size - 2.0), 100.0)
						elif input_encoding in ("x", "X"):
							for l in xrange(2):
								RGB_copy[1 + l] = min((RGB_copy[1 + l] *
													   (size - 1.0) -
													   1.0) / (size - 3.0), 100.0)
					RGB_index[columns[2]] = k
					RGB_in.append(RGB_copy)
					RGB_indexes.append(list(RGB_index))

		# Lookup RGB -> RGB values through devicelink profile using icclu
		# (Using icclu instead of xicclu because xicclu in versions
		# prior to Argyll CMS 1.6.0 could not deal with devicelink profiles)
		RGB_out = self.xicclu(link_filename, RGB_in, use_icclu=True)

		# Remove temporary files, move log file
		result2 = self.wrapup(dst_path=path, ext_filter=[".log"])

		if isinstance(result, Exception):
			raise result

		if format != "png":
			lut = [["# Created with %s %s" % (appname, version)]]
			valsep = " "
			linesep = "\n"
		if format == "3dl":
			if maxval is None:
				maxval = 1023
			if output_bits is None:
				output_bits = math.log(maxval + 1) / math.log(2)
			if input_bits is None:
				input_bits = output_bits
			maxval = math.pow(2, output_bits) - 1
			pad = len(str(maxval))
			lut.append(["# INPUT RANGE: %i" % input_bits])
			lut.append(["# OUTPUT RANGE: %i" % output_bits])
			lut.append([])
			for i in xrange(0, size):
				lut[-1].append("%i" % int(round(i * step * (math.pow(2, input_bits) - 1))))
			for RGB_triplet in RGB_out:
				lut.append([])
				for component in (0, 1, 2):
					lut[-1].append("%i" % int(round(RGB_triplet[component] * maxval)))
		elif format == "cube":
			if maxval is None:
				maxval = 1.0
			lut.append(["LUT_3D_SIZE %i" % size])
			lut.append(["DOMAIN_MIN 0.0 0.0 0.0"])
			fp_offset = str(maxval).find(".")
			domain_max = "DOMAIN_MAX %s %s %s" % (("%%.%if" % len(str(maxval)[fp_offset + 1:]), ) * 3)
			lut.append([domain_max % ((maxval ,) * 3)])
			lut.append([])
			for RGB_triplet in RGB_out:
				lut.append([])
				for component in (0, 1, 2):
					lut[-1].append("%.6f" % (RGB_triplet[component] * maxval))
		elif format == "spi3d":
			if maxval is None:
				maxval = 1.0
			lut = [["SPILUT 1.0"]]
			lut.append(["3 3"])
			lut.append(["%i %i %i" % ((size, ) * 3)])
			for i, RGB_triplet in enumerate(RGB_out):
				lut.append([str(index) for index in RGB_indexes[i]])
				for component in (0, 1, 2):
					lut[-1].append("%.6f" % (RGB_triplet[component] * maxval))
		elif format == "eeColor":
			if maxval is None:
				maxval = 1.0
			lut = []
			for i, RGB_triplet in enumerate(RGB_out):
				lut.append(["%.6f" % (float(component) * maxval) for component in RGB_in[i].split()])
				for component in (0, 1, 2):
					lut[-1].append("%.6f" % (RGB_triplet[component] * maxval))
			linesep = "\r\n"
		elif format == "mga":
			lut = [["#HEADER"],
				   ["#filename: %s" % os.path.basename(path)],
				   ["#type: 3D cube file"],
				   ["#format: 1.00"],
				   ["#created: %s" % strftime("%d %B %Y")],
				   ["#owner: %s" % getpass.getuser()],
				   ["#title: %s" % os.path.splitext(os.path.basename(path))[0]],
				   ["#END"]]
			lut.append([])
			lut.append(["channel 3d"])
			lut.append(["in %i" % (size ** 3)])
			maxval = 2 ** output_bits - 1
			lut.append(["out %i" % (maxval + 1)])
			lut.append([""])
			lut.append(["format lut"])
			lut.append([""])
			lut.append(["values\tred\tgreen\tblue"])
			for i, RGB_triplet in enumerate(RGB_out):
				lut.append(["%i" % i])
				for component in (0, 1, 2):
					lut[-1].append(("%i" % int(round(RGB_triplet[component] * maxval))))
			valsep = "\t"
		elif format == "png":
			lut = [[]]
			if output_bits > 8:
				# PNG only supports 8 and 16 bit
				output_bits = 16
			maxval = 2 ** output_bits - 1
			for RGB_triplet in RGB_out:
				if len(lut[-1]) == size:
					# Append new scanline
					lut.append([])
				lut[-1].append([int(round(v * maxval)) for v in RGB_triplet])
			# Current layout is vertical
			if getcfg("3dlut.image.layout") == "h":
				# Change layout to horizontal
				lutv = lut
				lut = [[]]
				for i in xrange(size):
					if len(lut[-1]) == size ** 2:
						# Append new scanline
						lut.append([])
					for j in xrange(size):
						lut[-1].extend(lutv[i + size * j])

		if format != "png":
			lut.append([])
			for i, line in enumerate(lut):
				lut[i] = valsep.join(line)
			result = linesep.join(lut)

		# Write 3DLUT
		lut_file = open(path, "wb")
		if format != "png":
			lut_file.write(result)
		else:
			im = imfile.Image(lut, output_bits)
			im.write(lut_file)
		lut_file.close()

		if isinstance(result2, Exception):
			raise result2

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

	def enumerate_displays_and_ports(self, silent=False, check_lut_access=True,
									 enumerate_ports=True,
									 include_network_devices=True):
		"""
		Enumerate the available displays and ports.
		
		Also sets Argyll version number, availability of certain options
		like black point rate, and checks LUT access for each display.
		
		"""
		if (silent and check_argyll_bin()) or (not silent and 
											   check_set_argyll_bin()):
			displays = []
			lut_access = []
			if verbose >= 1:
				safe_print(lang.getstr("enumerating_displays_and_comports"))
			instruments = []
			current_display = listget(getcfg("displays"),
									  getcfg("display.number") - 1)
			cfg_instruments = getcfg("instruments")
			current_instrument = listget(cfg_instruments,
										 getcfg("comport.number") - 1)
			if enumerate_ports:
				cmd = get_argyll_util("dispcal")
			else:
				cmd = get_argyll_util("dispwin")
				for instrument in cfg_instruments:
					# Names are canonical from 1.1.4.7 onwards, but we may have
					# verbose names from an old configuration
					instrument = get_canonical_instrument_name(instrument)
					if instrument.strip():
						instruments.append(instrument)
			args = []
			if include_network_devices:
				args.append("-dcc:?")
			args.append("-?")
			argyll_bin_dir = os.path.dirname(cmd)
			if (argyll_bin_dir != self.argyll_bin_dir):
				self.argyll_bin_dir = argyll_bin_dir
				safe_print(self.argyll_bin_dir)
			result = self.exec_cmd(cmd, args, capture_output=True, 
								   skip_scripts=True, silent=True, 
								   log_output=False)
			if isinstance(result, Exception):
				safe_print(result)
			arg = None
			defaults["calibration.black_point_hack"] = 0
			defaults["calibration.black_point_rate.enabled"] = 0
			defaults["patterngenerator.prisma.argyll"] = 0
			n = -1
			self.display_rects = []
			non_standard_display_args = ("-dweb[:port]", "-dmadvr")
			if test:
				# Add dummy Chromecasts
				self.output.append(u" -dcc[:n]")
				self.output.append(u"    100 = '\xd4\xc7\xf3 Test A'")
				self.output.append(u"    101 = '\xd4\xc7\xf3 Test B'")
			argyll_version_string = None
			for line in self.output:
				if isinstance(line, unicode):
					n += 1
					line = line.strip()
					if (argyll_version_string is None
						and "version" in line.lower()):
						argyll_version_string = line[line.lower().find("version")
													 + 8:]
						if (argyll_version_string != self.argyll_version_string):
							self.set_argyll_version_from_string(argyll_version_string)
							safe_print("Argyll CMS " + self.argyll_version_string)
						config.defaults["copyright"] = ("No copyright. Created "
														"with %s %s and Argyll "
														"CMS %s" % 
														(appname, version, 
														 argyll_version_string))
						if self.argyll_version > [1, 0, 4]:
							# Rate of blending from neutral to black point.
							defaults["calibration.black_point_rate.enabled"] = 1
						if (self.argyll_version >= [1, 7] and
							not "Beta" in self.argyll_version_string):
							# Forced black point hack available
							# (Argyll CMS 1.7)
							defaults["calibration.black_point_hack"] = 1
						continue
					line = line.split(None, 1)
					if len(line) and line[0][0] == "-":
						arg = line[0]
						if arg == "-A":
							# Rate of blending from neutral to black point.
							defaults["calibration.black_point_rate.enabled"] = 1
						elif arg in non_standard_display_args:
							displays.append(arg)
						elif arg == "-b" and not line[-1].startswith("bright"):
							# Forced black point hack available
							# (Argyll CMS 1.7b 2014-12-22)
							defaults["calibration.black_point_hack"] = 1
						elif arg == "-dprisma[:host]":
							defaults["patterngenerator.prisma.argyll"] = 1
					elif len(line) > 1 and line[1][0] == "=":
						value = line[1].strip(" ='")
						if arg == "-d":
							# Standard displays
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
						elif arg == "-dcc[:n]":
							# Chromecast
							if value:
								# Note the Chromecast name may be mangled due
								# to being UTF-8 encoded, but commandline output
								# will always be decoded to Unicode using the
								# stdout encoding, which may not be UTF-8
								# (e.g. under Windows). We can recover characters
								# valid in both UTF-8 and stdout encoding
								# by a re-encode/decode step
								displays.append("Chromecast %s: %s" %
												(line[0],
												 safe_unicode(safe_str(value, enc),
															  "UTF-8")))
						elif arg == "-dprisma[:host]":
							# Prisma (via Argyll CMS)
							# <serial no>: <name> @ <ip>
							# 141550000000: prisma-0000 @ 172.31.31.162
							match = re.findall(".+?: (.+) @ (.+)", value)
							if len(match):
								displays.append("Prisma %s: %s @ %s" %
												(line[0],
												 safe_unicode(safe_str(match[0][0], enc),
															  "UTF-8"), match[0][1]))
						elif arg == "-c" and enumerate_ports:
							if ((re.match("/dev(?:/[\w.]+)*$", value) or
								 re.match("COM\d+$", value)) and 
								getcfg("skip_legacy_serial_ports")):
								# Skip all legacy serial ports (this means we 
								# deliberately don't support DTP92 and
								# Spectrolino, although they may work when
								# used with a serial to USB adaptor)
								continue
							value = value.split(None, 1)
							if len(value) > 1:
								value = value[1].strip("()")
							else:
								value = value[0]
							value = get_canonical_instrument_name(value)
							instruments.append(value)
			if test:
				inames = all_instruments.keys()
				inames.sort()
				for iname in inames:
					iname = get_canonical_instrument_name(iname)
					if not iname in instruments:
						instruments.append(iname)
			if verbose >= 1: safe_print(lang.getstr("success"))
			if instruments != self.instruments:
				self.instruments = instruments
				setcfg("instruments", instruments)
				if current_instrument in instruments:
					setcfg("comport.number",
						   instruments.index(current_instrument) + 1)
			if displays != self._displays:
				self._displays = list(displays)
				displays = filter(lambda display:
									  not display in non_standard_display_args,
								  displays)
				self.display_edid = []
				self.display_manufacturers = []
				self.display_names = []
				if sys.platform == "win32":
					# The ordering will work as long
					# as Argyll continues using
					# EnumDisplayMonitors
					monitors = util_win.get_real_display_devices_info()
				for i, display in enumerate(displays):
					if (display.startswith("Chromecast ") or
						display.startswith("Prisma ")):
						self.display_edid.append({})
						if display.startswith("Prisma "):
							display_manufacturer = "Q, Inc"
						else:
							display_manufacturer = "Google"
						self.display_manufacturers.append(display_manufacturer)
						self.display_names.append(display.split(":", 1)[1].strip())
						continue
					display_name = split_display_name(display)
					# Make sure we have nice descriptions
					desc = []
					if sys.platform == "win32" and i < len(monitors):
						# Get monitor description using win32api
						device = util_win.get_active_display_device(
									monitors[i]["Device"])
						if device:
							desc.append(device.DeviceString.decode(fs_enc, 
																   "replace"))
						# Deal with HiDPI - update monitor rect
						m_left, m_top, m_right, m_bottom = monitors[i]["Monitor"]
						m_width = m_right - m_left
						m_height = m_bottom - m_top
						self.display_rects[i] = wx.Rect(m_left, m_top, m_width,
														m_height)
						is_primary = u" [PRIMARY]" in display
						display = " @ ".join([display_name, 
											  "%i, %i, %ix%i" %
											  (m_left, m_top, m_width,
											   m_height)])
						if is_primary:
							display += u" [PRIMARY]"
					# Get monitor descriptions from EDID
					try:
						# Important: display_name must be given for get_edid
						# under Mac OS X, but it doesn't hurt to always
						# include it
						edid = get_edid(i, display_name)
					except (EnvironmentError, TypeError, ValueError,
							WMIError), exception:
						if isinstance(exception, EnvironmentError):
							safe_print(exception)
						edid = {}
					self.display_edid.append(edid)
					if edid:
						manufacturer = edid.get("manufacturer", "").split()
						monitor = edid.get("monitor_name",
										   edid.get("ascii",
													str(edid["product_id"] or
														"")))
						if monitor and not monitor in "".join(desc):
							desc = [monitor]
					else:
						manufacturer = []
					if desc and desc[-1] not in display:
						# Only replace the description if it not already
						# contains the monitor model
						display = " @".join([" ".join(desc), 
												 display.split("@")[-1]])
					displays[i] = display
					self.display_manufacturers.append(" ".join(manufacturer))
					self.display_names.append(split_display_name(display))
				if self.argyll_version >= [1, 4, 0]:
					displays.append("Web @ localhost")
					self.display_edid.append({})
					self.display_manufacturers.append("")
					self.display_names.append("Web")
				if self.argyll_version >= [1, 6, 0]:
					displays.append("madVR")
					self.display_edid.append({})
					self.display_manufacturers.append("")
					self.display_names.append("madVR")
				# Prisma (via DisplayCAL)
				displays.append("Prisma")
				self.display_edid.append({})
				self.display_manufacturers.append("Q, Inc")
				self.display_names.append("Prisma")
				# Resolve
				displays.append("Resolve")
				self.display_edid.append({})
				self.display_manufacturers.append("DaVinci")
				self.display_names.append("Resolve")
				# Untethered
				displays.append("Untethered")
				self.display_edid.append({})
				self.display_manufacturers.append("")
				self.display_names.append("Untethered")
				#
				self.displays = displays
				setcfg("displays", displays)
				if current_display in displays:
					setcfg("display.number",
						   displays.index(current_display) + 1)
				# Filter out Prisma (via DisplayCAL), Resolve and Untethered
				# IMPORTANT: Also make changes to display filtering in
				# worker.Worker.has_separate_lut_access
				displays = displays[:-3]
				if self.argyll_version >= [1, 6, 0]:
					# Filter out madVR
					displays = displays[:-1]
				if self.argyll_version >= [1, 4, 0]:
					# Filter out Web @ localhost
					displays = displays[:-1]
				if check_lut_access:
					dispwin = get_argyll_util("dispwin")
					test_cal = get_data_path("test.cal")
					if not test_cal:
						safe_print(lang.getstr("file.missing", "test.cal"))
					tmp = self.create_tempdir()
					if isinstance(tmp, Exception):
						safe_print(tmp)
						tmp = None
					for i, disp in enumerate(displays):
						if (disp.startswith("Chromecast ") or
							disp.startswith("Prisma ") or not test_cal):
							lut_access.append(None)
							continue
						if sys.platform == "darwin":
							# There's no easy way to check LUT access under
							# Mac OS X because loading a LUT isn't persistent
							# unless you run as root. Just assume we have
							# access to all displays.
							lut_access.append(True)
							continue
						if verbose >= 1:
							safe_print(lang.getstr("checking_lut_access", (i + 1)))
						# Save current calibration?
						if tmp:
							current_cal = os.path.join(tmp, "current.cal")
							tmp_cal = current_cal
							result = self.save_current_video_lut(i + 1,
																 current_cal,
																 silent=True)
						# Load test.cal
						result = self.exec_cmd(dispwin, ["-d%s" % (i +1), "-c", 
														 test_cal], 
											   capture_output=True, 
											   skip_scripts=True, 
											   silent=True)
						if isinstance(result, Exception):
							safe_print(result)
						elif result is None:
							lut_access.append(None)
							continue
						# Check if LUT == test.cal
						result = self.exec_cmd(dispwin, ["-d%s" % (i +1), "-V", 
														 test_cal], 
											   capture_output=True, 
											   skip_scripts=True, 
											   silent=True)
						if isinstance(result, Exception):
							safe_print(result)
						elif result is None:
							lut_access.append(None)
							continue
						retcode = -1
						for line in self.output:
							if line.find("IS loaded") >= 0:
								retcode = 0
								break
						# Reset LUT & (re-)load previous cal (if any)
						if not tmp or not os.path.isfile(current_cal):
							current_cal = self.get_dispwin_display_profile_argument(i)
						result = self.exec_cmd(dispwin, ["-d%s" % (i + 1), "-c", 
														 current_cal], 
											   capture_output=True, 
											   skip_scripts=True, 
											   silent=True)
						if isinstance(result, Exception):
							safe_print(result)
						if tmp and os.path.isfile(tmp_cal):
							try:
								os.remove(tmp_cal)
							except EnvironmentError, exception:
								safe_print(exception)
						lut_access.append(retcode == 0)
						if verbose >= 1:
							if retcode == 0:
								safe_print(lang.getstr("success"))
							else:
								safe_print(lang.getstr("failure"))
				else:
					lut_access.extend([None] * len(displays))
				if self.argyll_version >= [1, 4, 0]:
					# Web @ localhost
					lut_access.append(False)
				if self.argyll_version >= [1, 6, 0]:
					# madVR
					lut_access.append(True)
				# Prisma (via DisplayCAL)
				lut_access.append(False)
				# Resolve
				lut_access.append(False)
				# Untethered
				lut_access.append(False)
				self.lut_access = lut_access
		elif silent or not check_argyll_bin():
			self.clear_argyll_info()

	def exec_cmd(self, cmd, args=[], capture_output=False, 
				 display_output=False, low_contrast=True, skip_scripts=False, 
				 silent=False, parent=None, asroot=False, log_output=True,
				 title=appname, shell=False, working_dir=None, dry_run=False,
				 sessionlogfile=None):
		"""
		Execute a command.
		
		Return value is either True (succeed), False (failed), None (canceled)
		or an exception.
		
		cmd is the full path of the command.
		args are the arguments, if any.
		capture_output (if True) swallows any output from the command and
		sets the 'output' and 'errors' properties of the Worker instance.
		display_output shows the log after the command.
		low_contrast (if True) sets low contrast shell colors while the 
		command is run.
		skip_scripts (if True) skips the creation of shell scripts that allow 
		re-running the command. Note that this is also controlled by a global 
		config option and scripts will only be created if it evaluates to False.
		silent (if True) skips most output and also most error dialogs 
		(except unexpected failures)
		parent sets the parent window for auth dialog (if asroot is True).
		asroot (if True) on Linux runs the command using sudo.
		log_output (if True) logs any output if capture_output is also set.
		title = Title for auth dialog (if asroot is True)
		working_dir = Working directory. If None, will be determined from
		absulte path of last argument and last argument will be set to only 
		the basename. If False, no working dir will be used and file arguments
		not changed.
		"""
		if not capture_output:
			capture_output = not sys.stdout.isatty()
		self.clear_cmd_output()
		if None in [cmd, args]:
			if verbose >= 1 and not silent:
				safe_print(lang.getstr("aborted"))
			return False
		self.cmd = cmd
		cmdname = os.path.splitext(os.path.basename(cmd))[0]
		self.cmdname = cmdname
		if not "-?" in args and cmdname == get_argyll_utilname("dispwin"):
			if "-I" in args or "-U" in args:
				if "-Sl" in args or "-Sn" in args:
					# Root is required if installing a profile to a system
					# location
					asroot = True
			elif not ("-s" in args or self.calibration_loading_generally_supported):
				# Loading/clearing calibration not supported
				# Don't actually do it, pretend we were successful
				if "-V" in args:
					self.output.append("IS loaded")
				self.retcode = 0
				return True
		if asroot:
			silent = False
		measure_cmds = (get_argyll_utilname("dispcal"), 
						get_argyll_utilname("dispread"), 
						get_argyll_utilname("spotread"))
		process_cmds = (get_argyll_utilname("collink"),
						get_argyll_utilname("colprof"),
						get_argyll_utilname("targen"))
		# Run commands through wexpect.spawn instead of subprocess.Popen if
		# any of these conditions apply
		use_pty = args and not "-?" in args and cmdname in measure_cmds + process_cmds
		self.measure_cmd = not "-?" in args and cmdname in measure_cmds
		self.use_patterngenerator = (self.measure_cmd and
									 cmdname != get_argyll_utilname("spotread") and
									 (config.get_display_name() == "Resolve" or
									  (config.get_display_name() == "Prisma" and
									   not defaults["patterngenerator.prisma.argyll"])))
		use_3dlut_override = (((self.use_patterngenerator and
								config.get_display_name(None, True) == "Prisma") or
							   (config.get_display_name(None, True) == "madVR" and
							    (sys.platform != "win32" or
							     not getcfg("madtpg.native")))) and
							  cmdname == get_argyll_utilname("dispread") and
							  "-V" in args)
		if use_3dlut_override:
			args.remove("-V")
		working_basename = None
		if args and args[-1].find(os.path.sep) > -1:
			working_basename = os.path.basename(args[-1])
			if cmdname not in (get_argyll_utilname("dispcal"),
							   get_argyll_utilname("dispread"),
							   get_argyll_utilname("colprof"),
							   get_argyll_utilname("targen"),
							   get_argyll_utilname("txt2ti3")):
				# Last arg is with extension
				working_basename = os.path.splitext(working_basename)[0]
			if working_dir is None:
				working_dir = os.path.dirname(args[-1])
		if working_dir is None:
			working_dir = self.tempdir
		if working_dir and not os.path.isdir(working_dir):
			working_dir = None
		if working_dir and working_dir == self.tempdir:
			# Get a list of files in the temp directory and their modification
			# times so we can determine later if anything has changed and we
			# should keep the files in case of errors
			for filename in os.listdir(working_dir):
				self.tmpfiles[filename] = os.stat(os.path.join(working_dir,
															   filename)).st_mtime
		if (working_basename and working_dir == self.tempdir and not silent
			and log_output and not getcfg("dry_run")):
			if sessionlogfile:
				self.sessionlogfile = sessionlogfile
			else:
				self.sessionlogfile = LogFile(working_basename, working_dir)
			self.sessionlogfiles[working_basename] = self.sessionlogfile
		if not silent or verbose >= 3:
			self.log("-" * 80)
			if self.sessionlogfile:
				safe_print("Session log: %s" % working_basename + ".log")
				safe_print("")
		use_madvr = (cmdname in (get_argyll_utilname("dispcal"),
								 get_argyll_utilname("dispread"),
								 get_argyll_utilname("dispwin")) and
					 get_arg("-dmadvr", args) and madvr)
		if use_madvr:
			# Try to connect to running madTPG or launch a new instance
			try:
				if self.madtpg_connect():
					# Connected
					# Check madVR version
					madvr_version = self.madtpg.get_version()
					if not madvr_version or madvr_version < madvr.min_version:
						self.madtpg_disconnect(False)
						return Error(lang.getstr("madvr.outdated",
												 madvr.min_version))
					self.log("Connected to madVR version %i.%i.%i.%i (%s)" %
							 (madvr_version + (self.madtpg.uri, )))
					if isinstance(self.madtpg, madvr.MadTPG_Net):
						# Need to handle calibration clearing/loading/saving
						# for madVR net-protocol pure python implementation
						cal = None
						calfilename = None
						profile = None
						ramp = False
						if cmdname == get_argyll_utilname("dispwin"):
							if "-c" in args:
								# Clear calibration
								self.log("MadTPG_Net clear calibration")
								ramp = None
							if "-L" in args:
								# NOTE: Hmm, profile will be None. It's not
								# functionality we currently use though.
								profile = config.get_display_profile()
							if "-s" in args:
								# Save calibration. Get from madTPG
								self.log("MadTPG_Net save calibration:", args[-1])
								ramp = self.madtpg.get_device_gamma_ramp()
								if not ramp:
									self.madtpg_disconnect(False)
									return Error("madVR_GetDeviceGammaRamp failed")
								cal = """CAL    

KEYWORD "DEVICE_CLASS"
DEVICE_CLASS "DISPLAY"
KEYWORD "COLOR_REP"
COLOR_REP "RGB"
BEGIN_DATA_FORMAT
RGB_I RGB_R RGB_G RGB_B
END_DATA_FORMAT
NUMBER_OF_SETS 256
BEGIN_DATA
"""
								# Convert ushort_Array_256_Array_3 to dictionary
								RGB = {}
								for j in xrange(3):
									for i in xrange(256):
										if not i in RGB:
											RGB[i] = []
										RGB[i].append(ramp[j][i] / 65535.0)
								# Get RGB from dictionary
								for i, (R, G, B) in RGB.iteritems():
									cal += "%f %f %f %f\n" % (i / 255.0, R, G, B)
								cal += "END_DATA"
								# Write out .cal file
								try:
									with open(args[-1], "w") as calfile:
										calfile.write(cal)
								except (IOError, OSError), exception:
									self.madtpg_disconnect(False)
									return exception
								cal = None
								ramp = False
							elif working_basename:
								# .cal/.icc/.icm file to load
								calfilename = args[-1]
						elif cmdname == get_argyll_utilname("dispread"):
							# Check for .cal file to load
							# NOTE this isn't normally used as we use -K
							# for madTPG, but is overridable by the user
							k_arg = get_arg("-k", args, True)
							if k_arg:
								calfilename = args[k_arg[0] + 1]
							else:
								ramp = None
						else:
							# dispcal
							ramp = None
						if calfilename:
							# Load calibration from .cal file or ICC profile
							self.log("MadTPG_Net load calibration:", calfilename)
							result = check_file_isfile(calfilename)
							if isinstance(result, Exception):
								self.madtpg_disconnect(False)
								return result
							if calfilename.lower().endswith(".cal"):
								# .cal file
								try:
									cal = CGATS.CGATS(calfilename)
								except (IOError, CGATS.CGATSError), exception:
									self.madtpg_disconnect(False)
									return exception
							else:
								# ICC profile
								try:
									profile = ICCP.ICCProfile(calfilename)
								except (IOError, ICCP.ICCProfileInvalidError), exception:
									self.madtpg_disconnect(False)
									return exception
						if profile:
							# Load calibration from ICC profile vcgt (if present)
							if isinstance(profile.tags.get("vcgt"),
										  ICCP.VideoCardGammaType):
								cal = vcgt_to_cal(profile)
							else:
								# Linear
								ramp = None
						if cal:
							# Check calibration we're going to load
							try:
								cal = verify_cgats(cal,
												   ("RGB_R", "RGB_G", "RGB_B"))
								if len(cal.DATA) != 256:
									# Needs to have 256 entries
									raise CGATSError("%s: %s != 256" %
													 (lang.getstr("calibration"),
													  lang.getstr("number_of_entries")))
							except CGATS.CGATSError, exception:
								self.madtpg_disconnect(False)
								return exception
							# Convert calibration to ushort_Array_256_Array_3
							ramp = ((ctypes.c_ushort * 256) * 3)()
							for i in xrange(256):
								for j, channel in enumerate("RGB"):
									ramp[j][i] = int(round(cal.DATA[i]["RGB_" + channel] * 65535))
					else:
						ramp = None
					if (ramp is not False and
						not self.madtpg.set_device_gamma_ramp(ramp)):
						self.madtpg_disconnect(False)
						return Error("madVR_SetDeviceGammaRamp failed")
					if (isinstance(self.madtpg, madvr.MadTPG_Net) and
						cmdname == get_argyll_utilname("dispwin")):
						# For madVR net-protocol pure python implementation
						# we are now done
						self.madtpg_disconnect(False)
						return True
					if not "-V" in args and not use_3dlut_override:
						endis = "disable"
					else:
						endis = "enable"
					if not getattr(self.madtpg, endis + "_3dlut")():
						self.madtpg_disconnect(False)
						return Error("madVR_%s3dlut failed" % endis.capitalize())
					fullscreen = self.madtpg.is_use_fullscreen_button_pressed()
					if sys.platform == "win32":
						# Make sure interactive display adjustment window isn't
						# concealed by temporarily disabling fullscreen if
						# needed. This is only a problem in single display
						# configurations.
						# Check if we have more than one "real" display.
						non_virtual_displays = []
						for display_no in xrange(len(self.displays)):
							if not config.is_virtual_display(display_no):
								non_virtual_displays.append(display_no)
						if len(non_virtual_displays) == 1:
							# We only have one "real" display connected
							if cmdname == get_argyll_utilname("dispcal"):
								if not ("-m" in args or "-u" in args) and fullscreen:
									# Disable fullscreen
									if self.madtpg.set_use_fullscreen_button(False):
										self.log("Temporarily leaving madTPG "
												 "fullscreen")
										self.madtpg_previous_fullscreen = fullscreen
									else:
										self.log("Warning - couldn't "
												 "temporarily leave madTPG "
												 "fullscreen")
							elif (getattr(self, "madtpg_previous_fullscreen", None) and
								  cmdname == get_argyll_utilname("dispread") and
								  self.dispread_after_dispcal):
								# Restore fullscreen
								if self.madtpg.set_use_fullscreen_button(True):
									self.log("Restored madTPG fullscreen")
									self.madtpg_previous_fullscreen = None
								else:
									self.log("Warning - couldn't restore "
											 "madTPG fullscreen")
					self.madtpg_fullscreen = self.madtpg.is_use_fullscreen_button_pressed()
					if ((not (cmdname == get_argyll_utilname("dispwin") or
							  self.dispread_after_dispcal) or
						 (cmdname == get_argyll_utilname("dispcal") and
						  ("-m" in args or "-u" in args))) and
						self.madtpg_fullscreen and
						not self.instrument_on_screen):
						# Show place instrument on screen message with countdown
						countdown = 15
						# We need to show the progress bar to make OSD visible
						if not self.madtpg.show_progress_bar(countdown):
							self.madtpg_disconnect()
							return Error("madVR_ShowProgressBar failed")
						self.madtpg_osd = not self.madtpg.is_disable_osd_button_pressed()
						if not self.madtpg_osd:
							# Enable OSD if disabled
							if self.madtpg.set_disable_osd_button(False):
								self.log("Temporarily enabled madTPG OSD for "
										 "instrument placement countdown")
							else:
								self.log("Warning - couldn't temporarily "
										 "enable madTPG OSD")
						for i in xrange(countdown):
							if self.subprocess_abort or self.thread_abort:
								break
							if not self.madtpg.set_osd_text(
								lang.getstr("instrument.place_on_screen.madvr",
											(countdown - i,
											 self.get_instrument_name()))):
								self.madtpg_disconnect()
								return Error("madVR_SetOsdText failed")
							ts = time()
							if i % 2 == 0:
								# Flash test area red
								self.madtpg.show_rgb(.8, 0, 0)
							else:
								self.madtpg.show_rgb(.15, .15, .15)
							delay = time() - ts
							if delay < 1:
								sleep(1 - delay)
						self.instrument_on_screen = True
						if not self.madtpg_osd:
							# Disable OSD
							if self.madtpg.set_disable_osd_button(True):
								self.log("Restored madTPG 'Disable OSD' button "
										 "state")
								self.madtpg_osd = None
							else:
								self.log("Warning - could not restore madTPG "
								 "'Disable OSD' button state")
					# Get pattern config
					patternconfig = self.madtpg.get_pattern_config()
					if (not patternconfig or
						not isinstance(patternconfig, tuple) or
						len(patternconfig) != 4):
						self.madtpg_disconnect()
						return Error("madVR_GetPatternConfig failed")
					self.log("Pattern area: %i%%" % patternconfig[0])
					self.log("Background level: %i%%" % patternconfig[1])
					self.log("Background mode: %s" % {0: "Constant",
													  1: "APL gamma",
													  2: "APL linear"}.get(patternconfig[2],
																		   patternconfig[2]))
					self.log("Border width: %i pixels" % patternconfig[3])
					if isinstance(self.madtpg, madvr.MadTPG_Net):
						args.remove("-dmadvr")
						args.insert(0, "-P1,1,0.01")
					else:
						# Only if using native madTPG implementation!
						if not get_arg("-P", args):
							# Setup patch size to match pattern config
							args.insert(0, "-P0.5,0.5,%f" %
											math.sqrt(patternconfig[0]))
						if not patternconfig[1] and self.argyll_version >= [1, 7]:
							# Setup black background if background level is zero.
							# Only do this for Argyll >= 1.7 to prevent messing
							# with pattern area when Argyll 1.6.x is used
							args.insert(0, "-F")
						# Disconnect
						self.madtpg_disconnect(False)
					self.log("")
				else:
					return Error(lang.getstr("madtpg.launch.failure"))
			except Exception, exception:
				if isinstance(getattr(self, "madtpg", None), madvr.MadTPG_Net):
					self.madtpg_disconnect()
				return exception
		# Use mad* net protocol pure python implementation
		use_madnet = use_madvr and isinstance(self.madtpg, madvr.MadTPG_Net)
		# Use mad* net protocol pure python implementation as pattern generator
		self.use_madnet_tpg = use_madnet and cmdname != get_argyll_utilname("dispwin")
		if self.use_patterngenerator or self.use_madnet_tpg:
			# Run a dummy command so we can grab the RGB numbers for
			# the pattern generator from the output
			carg = get_arg("-C", args, True)
			if carg:
				index = min(carg[0] + 1, len(args) - 1)
				args[index] += " && "
			else:
				args.insert(0, "-C")
				args.insert(1, "")
				index = 1
			python, pythonpath = get_python_and_pythonpath()
			script_dir = working_dir
			pythonscript = """from __future__ import print_function
import os, sys, time
if sys.platform != "win32":
	print(*["\\nCurrent RGB"] + sys.argv[1:])
abortfilename = os.path.join(%r, ".abort")
okfilename = os.path.join(%r, ".ok")
while 1:
	if os.path.isfile(abortfilename):
		break
	if os.path.isfile(okfilename):
		try:
			os.remove(okfilename)
		except OSError, e:
			pass
		else:
			break
	time.sleep(0.001)
""" % (script_dir, script_dir)
			waitfilename = os.path.join(script_dir, ".wait")
			if sys.platform == "win32":
				# Avoid problems with encoding
				python = win32api.GetShortPathName(python)
				for i, path in enumerate(pythonpath):
					if os.path.exists(path):
						pythonpath[i] = win32api.GetShortPathName(path)
				# Write out .wait.py file
				scriptfilename = waitfilename + ".py"
				with open(scriptfilename, "w") as scriptfile:
					scriptfile.write(pythonscript)
				scriptfilename = win32api.GetShortPathName(scriptfilename)
				# Write out .wait.cmd file
				with open(waitfilename + ".cmd", "w") as waitfile:
					waitfile.write('@echo off\n')
					waitfile.write('echo.\n')
					waitfile.write('echo Current RGB %*\n')
					waitfile.write('set "PYTHONPATH=%s"\n' %
								   safe_str(os.pathsep.join(pythonpath), enc))
					waitfile.write('"%s" -S "%s" %%*\n' %
								   (safe_str(python, enc),
									safe_str(scriptfilename, enc)))
				args[index] += waitfilename
			else:
				# Write out .wait file
				with open(waitfilename, "w") as waitfile:
					waitfile.write('#!/usr/bin/env python\n')
					waitfile.write(pythonscript)
				os.chmod(waitfilename, 0755)
				args[index] += '"%s" ./%s' % (strtr(safe_str(python),
													{'"': r'\"',
													 "$": r"\$"}),
											  os.path.basename(waitfilename))
		if verbose >= 1 or not silent:
			if not silent or verbose >= 3:
				if (not silent and (dry_run or getcfg("dry_run")) and
					not self.cmdrun):
					safe_print(lang.getstr("dry_run"))
					safe_print("")
					self.cmdrun = True
				if working_dir:
					self.log(lang.getstr("working_dir"))
					indent = "  "
					for name in working_dir.split(os.path.sep):
						self.log(textwrap.fill(name + os.path.sep, 80, 
											   expand_tabs=False, 
											   replace_whitespace=False, 
											   initial_indent=indent, 
											   subsequent_indent=indent))
						indent += " "
					self.log("")
				self.log(lang.getstr("commandline"))
				printcmdline(cmd if verbose >= 2 else os.path.basename(cmd), 
							 args, fn=self.log, cwd=working_dir)
				self.log("")
				if not silent and (dry_run or getcfg("dry_run")):
					if not self.lastcmdname or self.lastcmdname == cmdname:
						safe_print(lang.getstr("dry_run.end"))
					if self.owner and hasattr(self.owner, "infoframe_toggle_handler"):
						wx.CallAfter(self.owner.infoframe_toggle_handler,
									 show=True)
					if use_madnet:
						self.madtpg_disconnect()
					return UnloggedInfo(lang.getstr("dry_run.info"))
		cmdline = [cmd] + args
		for i, item in enumerate(cmdline):
			if i > 0 and item.find(os.path.sep) > -1:
				if sys.platform == "win32":
					item = make_win32_compatible_long_path(item)
					if (re.search("[^\x20-\x7e]", 
								  os.path.basename(item)) and
								  os.path.exists(item) and
								  i < len(cmdline) - 1):
						# Avoid problems with encoding under Windows by using
						# GetShortPathName, but be careful with the last
						# parameter which may be used as the basename for the
						# output file
						item = win32api.GetShortPathName(item)
				if working_dir and os.path.dirname(cmdline[i]) == working_dir:
					# Strip the path from all items in the working dir
					item = os.path.basename(item)
				if item != cmdline[i]:
					cmdline[i] = item
		if (working_dir and sys.platform == "win32" and 
			re.search("[^\x20-\x7e]", working_dir) and 
			os.path.exists(working_dir)):
			# Avoid problems with encoding
			working_dir = win32api.GetShortPathName(working_dir)
		sudo = None
		if asroot and ((sys.platform != "win32" and os.geteuid() != 0) or 
					   (sys.platform == "win32" and 
					    sys.getwindowsversion() >= (6, ))):
			if sys.platform == "win32":
				# Vista and later
				pass
			else:
				if not self.auth_timestamp:
					if hasattr(self, "thread") and self.thread.isAlive():
						# Careful: We can only show the auth dialog if running
						# in the main GUI thread!
						if use_madnet:
							self.madtpg_disconnect()
						return Error("Authentication requested in non-GUI thread")
					result = self.authenticate(cmd, title, parent)
					if result is False:
						if use_madnet:
							self.madtpg_disconnect()
						return None
					elif isinstance(result, Exception):
						if use_madnet:
							self.madtpg_disconnect()
						return result
				sudo = unicode(self.sudo)
		if sudo:
			if not use_pty:
				# Sudo may need a tty depending on configuration
				use_pty = True
			cmdline.insert(0, sudo)
			if (cmdname == get_argyll_utilname("dispwin")
				and sys.platform != "darwin"
				and self.sudo.availoptions.get("E")
				and getcfg("sudo.preserve_environment")):
				# Preserve environment so $DISPLAY is set
				cmdline.insert(1, "-E")
			if not use_pty:
				cmdline.insert(1, "-S")
				# Set empty string as password prompt to hide it from stderr
				cmdline.insert(1, "")
				cmdline.insert(1, "-p")
			else:
				# Use a designated prompt
				cmdline.insert(1, "Password:")
				cmdline.insert(1, "-p")
		if (working_dir and working_basename and not skip_scripts and
			not getcfg("skip_scripts")):
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
				self.log("Warning - error during shell script creation:", 
						   safe_unicode(exception))
		cmdline = [safe_str(arg, fs_enc) for arg in cmdline]
		working_dir = None if not working_dir else working_dir.encode(fs_enc)
		try:
			if not self.measure_cmd and self.argyll_version >= [1, 2]:
				# Argyll tools will no longer respond to keys
				if debug:
					self.log("[D] Setting ARGYLL_NOT_INTERACTIVE 1")
				os.environ["ARGYLL_NOT_INTERACTIVE"] = "1"
			elif "ARGYLL_NOT_INTERACTIVE" in os.environ:
				del os.environ["ARGYLL_NOT_INTERACTIVE"]
			if debug:
				self.log("[D] argyll_version", self.argyll_version)
				self.log("[D] ARGYLL_NOT_INTERACTIVE", 
						   os.environ.get("ARGYLL_NOT_INTERACTIVE"))
			if self.measure_cmd:
				for name, version in (("MIN_DISPLAY_UPDATE_DELAY_MS", [1, 5]),
									  ("DISPLAY_SETTLE_TIME_MULT", [1, 7])):
					backup = os.getenv("ARGYLL_%s_BACKUP" % name)
					value = None
					if (getcfg("measure.override_%s" % name.lower()) and
						self.argyll_version >= version):
						if backup is None:
							# Backup current value if any
							current = os.getenv("ARGYLL_%s" % name, "")
							os.environ["ARGYLL_%s_BACKUP" % name] = current
						else:
							current = backup
						if current:
							self.log("%s: Overriding ARGYLL_%s %s" %
									   (appname, name, current))
						# Override
						value = str(getcfg("measure.%s" % name.lower()))
						self.log("%s: Setting ARGYLL_%s %s" % (appname,
																 name, value))
					elif backup is not None:
						value = backup
						del os.environ["ARGYLL_%s_BACKUP" % name]
						if value:
							self.log("%s: Restoring ARGYLL_%s %s" % (appname,
																	   name,
																	   value))
						elif "ARGYLL_%s" % name in os.environ:
							del os.environ["ARGYLL_%s" % name]
					elif "ARGYLL_%s" % name in os.environ:
						self.log("%s: ARGYLL_%s" % (appname, name),
								   os.getenv("ARGYLL_%s" % name))
					if value:
						os.environ["ARGYLL_%s" % name] = value
			elif cmdname in (get_argyll_utilname("iccgamut"),
							 get_argyll_utilname("tiffgamut"),
							 get_argyll_utilname("viewgam")):
				os.environ["ARGYLL_3D_DISP_FORMAT"] = "VRML"
			if sys.platform not in ("darwin", "win32"):
				os.environ["ENABLE_COLORHUG"] = "1"
			if sys.platform == "win32":
				startupinfo = sp.STARTUPINFO()
				startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
				startupinfo.wShowWindow = sp.SW_HIDE
			else:
				startupinfo = None
			if not use_pty:
				data_encoding = enc
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
					stdin.write(self.pwd.encode(enc, "replace") + os.linesep)
					stdin.seek(0)
				else:
					stdin = sp.PIPE
			else:
				data_encoding = self.pty_encoding
				kwargs = dict(timeout=5, cwd=working_dir,
							  env=os.environ)
				if sys.platform == "win32":
					kwargs["codepage"] = windll.kernel32.GetACP()
					# As Windows' console always hard wraps at the
					# rightmost column, increase the buffer width
					kwargs["columns"] = 160
				stderr = None
				stdout = EncodedWriter(StringIO(), None, data_encoding)
				logfiles = []
				if (hasattr(self, "thread") and self.thread.isAlive() and
					self.interactive and getattr(self, "terminal", None)):
					logfiles.append(FilteredStream(self.terminal,
												   discard="",
												   triggers=self.triggers))
				if log_output:
					linebuffered_logfiles = []
					if sys.stdout.isatty():
						linebuffered_logfiles.append(safe_print)
					else:
						linebuffered_logfiles.append(log)
					if self.sessionlogfile:
						linebuffered_logfiles.append(self.sessionlogfile)
					logfiles.append(LineBufferedStream(
									FilteredStream(Files(linebuffered_logfiles),
												   data_encoding,
												   discard="",
												   linesep_in="\n", 
												   triggers=[])))
				logfiles.append(stdout)
				if (hasattr(self, "thread") and self.thread.isAlive() and 
					cmdname in measure_cmds + process_cmds):
					logfiles.extend([self.recent, self.lastmsg, self])
				logfiles = Files(logfiles)
				if self.use_patterngenerator:
					pgname = config.get_display_name()
					if self.patterngenerator:
						# Use existing pattern generator instance
						self.patterngenerator.logfile = logfiles
						self.patterngenerator.use_video_levels = getcfg("patterngenerator.%s.use_video_levels" % pgname.lower())
						if hasattr(self.patterngenerator, "conn"):
							# Try to use existing connection
							try:
								self.patterngenerator_send((.5, ) * 3, True)
							except socket.error:
								self.patterngenerator.disconnect_client()
					else:
						self.setup_patterngenerator(logfiles)
					if not hasattr(self.patterngenerator, "conn"):
						# Wait for connection - blocking
						self.patterngenerator.wait()
						if hasattr(self.patterngenerator, "conn"):
							self.patterngenerator_send((.5, ) * 3)
						else:
							# User aborted before connection was established
							return False
					if pgname == "Prisma":
						x, y, w, h, size = get_pattern_geometry()
						if use_3dlut_override:
							self.patterngenerator.enable_processing(size=size * 100)
						else:
							self.patterngenerator.disable_processing(size=size * 100)
			tries = 1
			while tries > 0:
				if self.subprocess_abort or self.thread_abort:
					break
				if use_pty:
					if self.argyll_version >= [1, 2] and USE_WPOPEN and \
					   os.environ.get("ARGYLL_NOT_INTERACTIVE"):
						self.subprocess = WPopen(cmdline, stdin=sp.PIPE, 
												 stdout=tempfile.SpooledTemporaryFile(), 
												 stderr=sp.STDOUT, shell=shell,
												 cwd=working_dir, 
												 startupinfo=startupinfo)
					else:
						# Minimum Windows version: XP or Server 2003
						if (sys.platform == "win32" and
							sys.getwindowsversion() < (5, 1)):
							raise Error(lang.getstr("windows.version.unsupported"))
						try:
							self.subprocess = wexpect.spawn(cmdline[0],
															cmdline[1:], 
															**kwargs)
						except wexpect.ExceptionPexpect, exception:
							self.retcode = -1
							raise Error(safe_unicode(exception))
						if debug >= 9 or (test and not "-?" in args):
							self.subprocess.interact()
					self.subprocess.logfile_read = logfiles
					if self.measure_cmd:
						keyhit_strs = [" or Q to ", "8\) Exit"]
						patterns = keyhit_strs + ["Current", r" \d+ of \d+"]
						self.log("%s: Starting interaction with subprocess" %
								 appname)
					else:
						patterns = []
						self.log("%s: Waiting for EOF" % appname)
					loop = 0
					pwdsent = False
					authfailed = False
					eof = False
					while 1:
						if loop < 1 and sudo:
							curpatterns = ["Password:"] + patterns
						else:
							curpatterns = patterns
						# NOTE: Using a timeout of None can block indefinitely
						# and prevent expect() from ever returning!
						self.subprocess.expect(curpatterns + [wexpect.EOF,
															  wexpect.TIMEOUT],
											   timeout=1)
						if self.subprocess.after is wexpect.EOF:
							self.log("%s: Reached EOF (OK)" % appname)
							break
						elif self.subprocess.after is wexpect.TIMEOUT:
							if not self.subprocess.isalive():
								self.log("%s: Subprocess no longer alive (timeout)" %
										 appname)
								if eof:
									break
								eof = True
							continue
						elif (self.subprocess.after == "Password:" and
							  loop < 1 and sudo):
							if pwdsent:
								self.subprocess.sendcontrol("C")
								authfailed = True
								self.auth_timestamp = 0
							else:
								self._safe_send(self.pwd.encode(enc, "replace") +
												os.linesep, obfuscate=True)
								pwdsent = True
							if not self.subprocess.isalive():
								break
							continue
						elif self.measure_cmd:
							if filter(lambda keyhit_str:
										  re.search(keyhit_str,
													self.subprocess.after),
										  keyhit_strs):
								# Wait for the keypress
								self.log("%s: Waiting for send buffer" %
										 appname)
								while not self.send_buffer:
									if not self.subprocess.isalive():
										self.log("%s: Subprocess no longer alive (unknown reason)" %
												 appname)
										break
									sleep(.05)
							if (self.send_buffer and
								self.subprocess.isalive()):
								self.log("%s: Sending buffer: %r" %
										 (appname, self.send_buffer))
								self._safe_send(self.send_buffer)
								self.send_buffer = None
						if not self.subprocess.isalive():
							break
						loop += 1
					# We need to call isalive() to set the exitstatus.
					# We can't use wait() because it might block in the
					# case of a timeout
					if self.subprocess.isalive():
						self.log("%s: Checking subprocess status" % appname)
						while self.subprocess.isalive():
							sleep(.1)
						self.log("%s: Subprocess no longer alive (OK)" % appname)
					self.retcode = self.subprocess.exitstatus
					if authfailed:
						raise Error(lang.getstr("auth.failed"))
				else:
					try:
						if (asroot and sys.platform == "win32" and
							sys.getwindowsversion() >= (6, )):
							win32com_shell.ShellExecuteEx(lpVerb="runas",
														  lpFile=cmd,
														  lpParameters=" ".join(quote_args(args)))
							return True
						else:
							self.subprocess = sp.Popen(cmdline, stdin=stdin,
													   stdout=stdout,
													   stderr=stderr,
													   shell=shell,
													   cwd=working_dir, 
													   startupinfo=startupinfo)
					except Exception, exception:
						self.retcode = -1
						raise Error(safe_unicode(exception))
					self.retcode = self.subprocess.wait()
					if stdin != sp.PIPE and not getattr(stdin, "closed", True):
						stdin.close()
				if self.is_working() and self.subprocess_abort and \
				   self.retcode == 0:
					self.retcode = -1
				self.subprocess = None
				tries -= 1
				if not silent and stderr:
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
								self.errors.append(line.decode(data_encoding,
															   "replace"))
					if tries > 0 and not use_pty:
						stderr = tempfile.SpooledTemporaryFile()
				if capture_output or use_pty:
					stdout.seek(0)
					self.output = [re.sub("^\.{4,}\s*$", "", 
										  line.decode(data_encoding,
													  "replace")) 
								   for line in stdout.readlines()]
					stdout.close()
					if len(self.output) and log_output:
						if not use_pty:
							self.log("".join(self.output).strip())
						if display_output and self.owner and \
						   hasattr(self.owner, "infoframe_toggle_handler"):
							wx.CallAfter(self.owner.infoframe_toggle_handler,
										 show=True)
					if tries > 0 and not use_pty:
						stdout = tempfile.SpooledTemporaryFile()
				if not silent and len(self.errors):
					errstr = "".join(self.errors).strip()
					self.log(errstr)
		except (Error, socket.error, EnvironmentError, RuntimeError), exception:
			return exception
		except Exception, exception:
			if debug:
				self.log('[D] working_dir:', working_dir)
			errmsg = (" ".join(cmdline).decode(fs_enc) + "\n" + 
					  safe_unicode(traceback.format_exc()))
			self.retcode = -1
			return Error(errmsg)
		finally:
			if (sudo and cmdname not in ("chown",
										 get_argyll_utilname("dispwin")) and
				working_dir and working_dir == self.tempdir and
				os.listdir(working_dir)):
				# We need to take ownership of any files created by commands
				# run via sudo otherwise we cannot move or remove them from
				# the temporary directory!
				errors = self.errors
				output = self.output
				retcode = self.retcode
				self.exec_cmd("chown", ["-R", getpass.getuser().decode(fs_enc),
										working_dir],
							  capture_output=capture_output, skip_scripts=True,
							  asroot=True)
				self.errors = errors
				self.output = output
				self.retcode = retcode
			if self.patterngenerator:
				if hasattr(self.patterngenerator, "conn"):
					try:
						if config.get_display_name() == "Resolve":
							# Send fullscreen black to prevent plasma burn-in
							try:
								self.patterngenerator.send((0, ) * 3, x=0, y=0, w=1, h=1)
							except socket.error:
								pass
						else:
							self.patterngenerator.disconnect_client()
					except Exception, exception:
						self.log(exception)
			if hasattr(self, "madtpg"):
				self.madtpg_disconnect()
		if debug and not silent:
			self.log("*** Returncode:", self.retcode)
		if self.retcode != 0:
			if use_pty and verbose >= 1 and not silent:
				self.log(lang.getstr("aborted"))
			if use_pty and len(self.output):
				errmsg = None
				for i, line in enumerate(self.output):
					if "Calibrate failed with 'User hit Abort Key' (No device error)" in line:
						break
					if ((": Error" in line and
					     not "failed with 'User Aborted'" in line and
					     not "returned error code 1" in line) or
					    (line.startswith("Failed to") and
					     not "Failed to meet target" in line) or
					    ("Requested ambient light capability" in line and
					     len(self.output) == i + 2) or
					    ("Diagnostic:" in line and
					     (len(self.output) == i + 1 or
						  self.output[i + 1].startswith("usage:"))) or
						 "communications failure" in line.lower()):
						# "returned error code 1" == user aborted
						if (sys.platform == "win32" and
							("config 1 failed (Operation not supported or "
							 "unimplemented on this platform) (Permissions ?)")
							in line):
							self.output.insert(i, lang.getstr("argyll.instrument.driver.missing") +
															  "\n\n" +
															  lang.getstr("argyll.error.detail") +
															  " ")
						if "Diagnostic:" in line:
							errmsg = line
						else:
							errmsg = "".join(self.output[i:])
						startpos = errmsg.find(": Error")
						if startpos > -1:
							errmsg = errmsg[startpos + 2:]
				if errmsg:
					return UnloggedError(errmsg.strip())
		if self.exec_cmd_returnvalue is not None:
			return self.exec_cmd_returnvalue
		return self.retcode == 0
	
	def flush(self):
		pass

	def _generic_consumer(self, delayedResult, consumer, continue_next, *args, 
						 **kwargs):
		# consumer must accept result as first arg
		result = None
		exception = None
		try:
			result = delayedResult.get()
		except Exception, exception:
			if hasattr(exception, "originalTraceback"):
				self.log(exception.originalTraceback)
			else:
				self.log(traceback.format_exc())
			result = UnloggedError(exception)
		if self.progress_start_timer.IsRunning():
			self.progress_start_timer.Stop()
		self.finished = True
		if not continue_next or isinstance(result, Exception) or not result:
			self.stop_progress()
		self.subprocess_abort = False
		self.thread_abort = False
		self.recent.clear()
		self.lastmsg.clear()
		wx.CallAfter(consumer, result, *args, **kwargs)
	
	def generate_A2B0(self, profile, clutres=None, logfile=None):
		
		# Lab cLUT is currently not implemented and should NOT be used!
		if profile.connectionColorSpace != "XYZ":
			raise Error(lang.getstr("profile.unsupported",
									(profile.connectionColorSpace,
									 profile.connectionColorSpace)))

		if logfile:
			safe_print("-" * 80)
			logfile.write("Creating perceptual A2B0 table\n")
			logfile.write("\n")
		# Make new A2B0
		A2B0 = ICCP.LUT16Type()
		# Matrix (identity)
		A2B0.matrix = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
		# Input / output curves (linear)
		A2B0.input = []
		A2B0.output = []
		channel = []
		for j in xrange(256):
			channel.append(j * 257)
		for table in (A2B0.input, A2B0.output):
			for i in xrange(3):
				table.append(channel)
		# cLUT
		if logfile:
			logfile.write("Generating A2B0 table lookup input values...\n")
		A2B0.clut = []
		if not clutres:
			clutres = len(profile.tags.A2B0.clut[0])
		if logfile:
			logfile.write("cLUT grid res: %i\n" % clutres)
		vrange = xrange(clutres)
		step = 1.0 / (clutres - 1.0)
		idata = []
		for R in vrange:
			for G in vrange:
				for B in vrange:
					idata.append([v * step for v in (R, G, B)])
		if logfile:
			logfile.write("Looking up input values through A2B0 table...\n")
		odata = self.xicclu(profile, idata, pcs="x", logfile=logfile)
		numrows = len(odata)
		if numrows != clutres ** 3:
			raise ValueError("Number of cLUT entries (%s) exceeds cLUT res "
							 "maximum (%s^3 = %s)" % (numrows, clutres,
													  clutres ** 3))
		XYZbp = list(odata[0])
		XYZwp = list(odata[-1])
		if logfile:
			logfile.write("Filling cLUT...\n")
		for i, (X, Y, Z) in enumerate(odata):
			if i % clutres == 0:
				if self.thread_abort:
					raise Info(lang.getstr("aborted"))
				A2B0.clut.append([])
				if logfile:
					logfile.write("\r%i%%" % round(i / (numrows - 1.0) * 100))
			# Apply black point compensation
			XYZ = colormath.apply_bpc(X, Y, Z, XYZbp, (0, 0, 0), XYZwp)
			XYZ = [v / XYZwp[1] for v in XYZ]
			A2B0.clut[-1].append([max(v * 32768, 0) for v in XYZ])
		if logfile:
			logfile.write("\n")
		profile.tags.A2B0 = A2B0
		return True
	
	def generate_B2A_from_inverse_table(self, profile, clutres=None,
										source="A2B", tableno=None, bpc=False,
										logfile=None, filename=None):
		"""
		Generate a profile's B2A table by inverting the A2B table 
		(default A2B1 or A2B0)
		
		It is also poosible to re-generate a B2A table by interpolating
		the B2A table itself.
		
		"""

		if tableno is None:
			if "A2B1" in profile.tags:
				tableno = 1
			else:
				tableno = 0
		if not clutres:
			if "B2A%i" % tableno in profile.tags:
				tablename = "B2A%i" % tableno
			else:
				tablename = "A2B%i" % tableno
			clutres = len(profile.tags[tablename].clut[0])
		
		if source == "B2A" and clutres > 23:
			# B2A interpolation is smoothest when used with a lower cLUT res
			clutres = 23

		if logfile:
			if source == "A2B":
				msg = ("Generating B2A%i table by inverting A2B%i table\n" %
					   (tableno, tableno))
			else:
				msg = "Re-generating B2A%i table by interpolation\n" % tableno
			logfile.write(msg)
			logfile.write("\n")

		# Note that intent 0 will be colorimetric if no other tables are
		# present
		intent = {0: "p",
				  1: "r",
				  2: "s"}[tableno]
		
		# Lookup RGB -> XYZ for primaries, black- and white point
		idata = [[0, 0, 0], [1, 1, 1], [1, 0, 0], [0, 1, 0], [0, 0, 1]]
		
		direction = {"A2B": "f", "B2A": "ib"}[source]
		odata = self.xicclu(profile, idata, intent, direction, pcs="x")
		
		# Scale to Y = 1
		XYZwp_abs = odata[1]
		XYZwpY = odata[1][1]
		odata = [[n / XYZwpY for n in v] for v in odata]

		XYZbp = odata[0]
		XYZwp = odata[1]
		XYZr = odata[2]
		XYZg = odata[3]
		XYZb = odata[4]

		# Sanity check whitepoint
		if (round(XYZwp[0], 3) != .964 or round(XYZwp[1], 3) != 1 or
			round(XYZwp[2], 3) != .825):
			raise Error("Argyll CMS xicclu: Invalid white XYZ: "
						"%.4f %.4f %.4f" % tuple(XYZwp_abs))

		# Get the primaries
		XYZrgb = [XYZr, XYZg, XYZb]

		# Sanity check primaries:
		# Red Y, Z shall not be higher than X
		# Green X, Z shall not be higher than Y
		# Blue X, Y shall not be higher than Z
		for i, XYZ in enumerate(XYZrgb):
			for j, v in enumerate(XYZ):
				if v > XYZ[i]:
					raise Error("Argyll CMS xicclu: Invalid primary %s XYZ: "
								"%.4f %.4f %.4f" % (("RGB"[i], ) + tuple(XYZ)))

		if logfile:
			logfile.write("Black XYZ: %.4f %.4f %.4f\n" %
						  tuple(XYZbp))
			logfile.write("White XYZ: %.4f %.4f %.4f\n" %
						  tuple(XYZwp))
			for i in xrange(3):
				logfile.write("%s XYZ: %.4f %.4f %.4f\n" %
							  (("RGB"[i], ) + tuple(XYZrgb[i])))
		
		# Prepare input PCS values
		if logfile:
			logfile.write("Generating input curve PCS values...\n")
		idata = []
		numentries = 4096
		maxval = numentries - 1.0
		vrange = xrange(numentries)
		Lbp, abp, bbp = colormath.XYZ2Lab(*[v * 100 for v in XYZbp])
		# Method to determine device <-> PCS neutral axis relationship
		# 0: L* (a*=b*=0) -> RGB
		# 1: As method 0, but blend a* b* to blackpoint hue
		# 2: R=G=B -> PCS
		# 3: As method 0, but blend a* b* to blackpoint hue in XYZ (BPC)
		# Method 0 and 1 result in lowest invprofcheck dE2k, with method 1
		# having a slight edge due to more accurately encoding the blackpoint
		method = 1
		if method != 2:
			for i in vrange:
				L, a, b = i / maxval * 100, 0, 0
				if method in (1, 3) and not bpc and XYZbp != [0, 0, 0]:
					# Blend to blackpoint hue
					if method == 1:
						vv = (L - Lbp) / (100.0 - Lbp)  # 0 at bp, 1 at wp
						vv = 1.0 - vv
						if vv < 0.0:
							vv = 0.0
						elif vv > 1.0:
							vv = 1.0
						vv = math.pow(vv, 40.0)
						a += vv * abp
						b += vv * bbp
					else:
						X, Y, Z = colormath.Lab2XYZ(L, a, b)
						XYZ = colormath.apply_bpc(X, Y, Z, (0, 0, 0), XYZbp)
						a, b = colormath.XYZ2Lab(*[v * 100 for v in XYZ])[1:]
				idata.append((L, a, b))
		
		pcs = profile.connectionColorSpace[0].lower()
		
		if source == "B2A":
			# NOTE:
			# Argyll's B2A tables are slightly inaccurate:
			# 0 0 0 PCS -> RGB may give RGB levels > 0 (it should clip
			# instead). Inversely, 0 0 0 RGB -> PCS (through inverted B2A)
			# will return PCS values that are too low or zero (ie. not the
			# black point as expected)
			
			# TODO: How to deal with this?
			pass

		if method == 2:
			# lookup RGB -> XYZ values through profile using xicclu to get TRC
			odata = []
			if not bpc:
				numentries -= 1
				maxval -= 1
			for i in xrange(numentries):
				odata.append([i / maxval] * 3)
			idata = self.xicclu(profile, odata, intent,
								{"A2B": "f", "B2A": "ib"}[source], pcs="x")
			if not bpc:
				numentries += 1
				maxval += 1
				idata.insert(0, [0, 0, 0])
				odata.insert(0, [0, 0, 0])
			wY = idata[-1][1]
			oXYZ = idata = [[n / wY for n in v] for v in idata]
			D50 = colormath.get_whitepoint("D50")
			fpL = [cm.XYZ2Lab(*v + [D50])[0] for v in oXYZ]
		else:
			oXYZ = [colormath.Lab2XYZ(*v) for v in idata]
			fpL = [v[0] for v in idata]
		fpX = [v[0] for v in oXYZ]
		fpY = [v[1] for v in oXYZ]
		fpZ = [v[2] for v in oXYZ]

		if method != 2 and bpc and XYZbp != [0, 0, 0]:
			if logfile:
				logfile.write("Applying BPC to input curve PCS values...\n")
			for i, (L, a, b) in enumerate(idata):
				X, Y, Z = colormath.Lab2XYZ(L, a, b)
				X, Y, Z = colormath.apply_bpc(X, Y, Z, (0, 0, 0), XYZbp, XYZwp)
				idata[i] = colormath.XYZ2Lab(X * 100, Y * 100, Z * 100)

		if logfile:
			logfile.write("Looking up input curve RGB values...\n")
		
		direction = {"A2B": "if", "B2A": "b"}[source]

		if method != 2:
			# Lookup Lab -> RGB values through profile using xicclu to get TRC
			odata = self.xicclu(profile, idata, intent, direction, pcs="l")

			# Sanity check white
			if (round(odata[-1][0], 3) != 1 or round(odata[-1][1], 3) != 1 or
				round(odata[-1][2], 3) != 1):
				wrgb_warning = ("Warning: Argyll CMS xicclu: Invalid white RGB: "
								"%.4f %.4f %.4f\n" % tuple(odata[-1]))
				if logfile:
					logfile.write(wrgb_warning)
				else:
					safe_print(wrgb_warning)

		xpR = [v[0] for v in odata]
		xpG = [v[1] for v in odata]
		xpB = [v[2] for v in odata]

		# Initialize B2A
		itable = ICCP.LUT16Type()

		use_cam_clipping = True
		
		# Setup matrix
		if profile.connectionColorSpace == "XYZ":
			# Use a matrix that scales the profile colorspace into the XYZ
			# encoding range, to make optimal use of the cLUT grid points

			xyYrgb = [colormath.XYZ2xyY(*XYZ) for XYZ in XYZrgb]
			area1 = 0.5 * abs(sum(x0 * y1 - x1 * y0
								  for ((x0, y0, Y0), (x1, y1, Y1)) in
								  zip(xyYrgb, xyYrgb[1:] + [xyYrgb[0]])))

			if logfile:
				logfile.write("Setting up matrix\n")

			matrices = []

			# RGB spaces used as PCS candidates.
			# Six synthetic RGB spaces that are large enough to encompass
			# display gamuts (except the LaserVue one) found on
			# http://www.tftcentral.co.uk/articles/pointers_gamut.htm
			# aswell as a selection of around two dozen profiles from openSUSE
			# ICC Profile Taxi database aswell as other user contributions
			rgb_spaces = []

			# A colorspace that encompasses Rec709. Uses Rec. 2020 blue.
			rgb_spaces.append([2.2, "D50",
							   [0.68280181011, 0.315096403371, 0.224182128906],
							   [0.310096375087, 0.631250246526, 0.73258972168],
							   [0.129244796433, 0.0471357502953, 0.0432281494141],
							   "Rec709-encompassing, variant 1"])

			# A colorspace that encompasses Rec709. Uses slightly different
			# primaries (based on WLED and B+RG LED) than variant 1.
			rgb_spaces.append([2.2, "D50",
							   [0.664580313612, 0.329336320112, 0.228820800781],
							   [0.318985161632, 0.644740328564, 0.742568969727],
							   [0.143284983488, 0.0303535582465, 0.0286102294922],
							   "Rec709-encompassing, variant 2"])

			# A colorspace that encompasses Rec709 with imaginary red and blue
			rgb_spaces.append([2.2, "D50",
							   [0.672053135694, 0.331936091367, 0.250122070312],
							   [0.319028093312, 0.644705491217, 0.710144042969],
							   [0.113899645442, 0.0424325604954, 0.0396270751953],
							   "Rec709-encompassing, variant 3"])

			# A colorspace that encompasses Rec709. Uses red and blue from
			# variant 2, but a slightly different green primary.
			rgb_spaces.append([2.2, "D50",
							   [0.664627993657, 0.329338357942, 0.244033813477],
							   [0.300155771607, 0.640946446796, 0.728302001953],
							   [0.143304213944, 0.0303410650333, 0.0276641845703],
							   "Rec709-encompassing, variant 4"])

			# A colorspace with Plasma-like primaries. Uses Rec. 2020 blue.
			rgb_spaces.append([2.2, "D50",
							   [0.692947816539, 0.30857396028, 0.244430541992],
							   [0.284461719244, 0.70017174365, 0.709167480469],
							   [0.129234824405, 0.0471509419335, 0.0464019775391],
							   "SMPTE-431-2/DCI-P3-encompassing, variant 1"])

			# A colorspace that encompasses both AdobeRGB and NTSC1953. Uses
			# Rec. 2020 blue.
			rgb_spaces.append([2.2, "D50",
							   [0.680082575358, 0.319746686121, 0.314331054688],
							   [0.200003470174, 0.730003123156, 0.641983032227],
							   [0.129238369699, 0.0471305063812, 0.0436706542969],
							   "AdobeRGB-NTSC1953-hybrid, variant 1"])

			# A colorspace with Plasma-like primaries. Uses Rec. 2020 blue.
			# More saturated green primary than variant 1.
			rgb_spaces.append([2.2, "D50",
							   [0.692943297796, 0.308579731457, 0.268966674805],
							   [0.249088838269, 0.730263586072, 0.684844970703],
							   [0.129230721306, 0.047147329564, 0.0461883544922],
							   "SMPTE-431-2/DCI-P3-encompassing, variant 2"])

			# A colorspace that encompasses both AdobeRGB and NTSC1953.
			# Different, more saturated primaries than variant 1.
			rgb_spaces.append([2.2, "D50",
							   [0.700603882817, 0.299296301842, 0.274520874023],
							   [0.200006562972, 0.75, 0.697494506836],
							   [0.143956453416, 0.0296952711131, 0.0279693603516],
							   "AdobeRGB-NTSC1953-hybrid, variant 2"])

			# A colorspace that encompasses DCI P3 with imaginary red and blue
			rgb_spaces.append([2.2, "D50",
							   [0.699964323939, 0.312334528794, 0.253814697266],
							   [0.284337791321, 0.68212854805, 0.73779296875],
							   [0.098165262763, 0.00937830372063, 0.00839233398438],
							   "SMPTE-431-2/DCI-P3-encompassing, variant 3"])

			# Rec. 2020
			rgb_spaces.append([2.2, "D50",
							   [0.7084978651, 0.293540723619, 0.279037475586],
							   [0.190200063067, 0.775375775201, 0.675354003906],
							   [0.129244405192, 0.0471399056886, 0.0456085205078],
							   "Rec2020"])

			# A colorspace that encompasses Rec2020 with imaginary primaries
			rgb_spaces.append([2.2, "D50",
							   [0.71715243505, 0.296225595183, 0.291244506836],
							   [0.191129060214, 0.795212673762, 0.700057983398],
							   [0.0981403936826, 0.00939694681658, 0.00869750976562],
							   "Rec2020-encompassing"])

			# Find smallest candidate that encompasses space defined by actual
			# primaries
			if logfile:
				logfile.write("Checking for suitable PCS candidate...\n")
			pcs_candidate = None
			for rgb_space in rgb_spaces:
				extremes = []
				for i in xrange(3):
					RGB = colormath.XYZ2RGB(XYZrgb[i][0], XYZrgb[i][1],
											XYZrgb[i][2],
											rgb_space=rgb_space,
											clamp=False)
					maxima = max(RGB)
					minima = min(RGB)
					if minima < 0:
						maxima += abs(minima)
					extremes.append(maxima)
				# Check area % (in xy for simplicity's sake)
				xyYrgb = rgb_space[2:5]
				area2 = 0.5 * abs(sum(x0 * y1 - x1 * y0
									  for ((x0, y0, Y0), (x1, y1, Y1)) in
									  zip(xyYrgb, xyYrgb[1:] + [xyYrgb[0]])))
				if logfile:
					logfile.write("%s fit: %.2f (area: %.2f%%)\n" %
								  (rgb_space[-1], 1.0 / max(extremes),
								   area1 / area2 * 100))
				# Check if tested RGB space contains actual primaries
				if max(extremes) <= 1.0:
					if logfile:
						logfile.write("Using primaries: %s\n" % rgb_space[-1])
					XYZrgb[0] = colormath.RGB2XYZ(1, 0, 0, rgb_space=rgb_space)
					XYZrgb[1] = colormath.RGB2XYZ(0, 1, 0, rgb_space=rgb_space)
					XYZrgb[2] = colormath.RGB2XYZ(0, 0, 1, rgb_space=rgb_space)
					pcs_candidate = rgb_space[-1]
					break

			if not pcs_candidate and False:  # NEVER?
				# Create quick medium quality shaper+matrix profile and use the
				# matrix from that
				if logfile:
					logfile.write("No suitable PCS candidate. "
								  "Computing best fit matrix...\n")
				# Lookup small testchart so profile computation finishes quickly
				ti1name = "ti1/d3-e4-s17-g49-m5-b5-f0.ti1"
				ti1 = get_data_path(ti1name)
				if not ti1:
					raise Error(lang.getstr("file.missing", ti1name))
				ti1, ti3, gray = self.ti1_lookup_to_ti3(ti1, profile,
														intent="a",
														white_patches=1)
				dirname, basename = os.path.split(profile.fileName)
				basepath = os.path.join(dirname,
										"." + os.path.splitext(basename)[0] +
										"-MTX.tmp")
				ti3.write(basepath + ".ti3")
				# Calculate profile
				cmd, args = get_argyll_util("colprof"), ["-v", "-qm", "-as",
														 basepath]
				result = self.exec_cmd(cmd, args, capture_output=True,
									   sessionlogfile=getattr(self,
															  "sessionlogfile",
															  None))
				if isinstance(result, Exception):
					raise result
				if result:
					mtx = ICCP.ICCProfile(basepath + profile_ext)
					XYZrgb = []
					for column in "rgb":
						tag = mtx.tags.get(column + "XYZ")
						if isinstance(tag, ICCP.XYZType):
							XYZrgb.append(tag.values())
					#os.remove(basepath + ".ti3")
					#os.remove(basepath + profile_ext)
					if not XYZrgb:
						raise Error(lang.getstr("profile.required_tags_missing",
												"rXYZ/gXYZ/bXYZ"))
				pcs_candidate = "BestFit"
			else:
				# If clutres is -1 (auto), set it depending on area coverage
				if clutres == -1:
					if area1 / area2 <= .51:
						clutres = 65
					elif area1 / area2 <= .73:
						clutres = 45

			if not pcs_candidate:
				# Use largest
				if logfile:
					logfile.write("Using primaries: %s\n" % rgb_spaces[-1][-1])
				XYZrgb[0] = colormath.RGB2XYZ(1, 0, 0, rgb_space=rgb_spaces[-1])
				XYZrgb[1] = colormath.RGB2XYZ(0, 1, 0, rgb_space=rgb_spaces[-1])
				XYZrgb[2] = colormath.RGB2XYZ(0, 0, 1, rgb_space=rgb_spaces[-1])
				pcs_candidate = rgb_spaces[-1][-1]

			for i in xrange(3):
				logfile.write("Using %s XYZ: %.4f %.4f %.4f\n" %
							  (("RGB"[i], ) + tuple(XYZrgb[i])))
	
			# Construct the final matrix
			Xr, Yr, Zr = XYZrgb[0]
			Xg, Yg, Zg = XYZrgb[1]
			Xb, Yb, Zb = XYZrgb[2]
			if logfile:
				logfile.write("R+G+B XYZ: %.4f %.4f %.4f\n" %
							  (Xr + Xg + Xb, Yr + Yg + Yb, Zr + Zg + Zb))
			m1 = colormath.Matrix3x3(((Xr, Xg, Xb),
									  (Yr, Yg, Yb),
									  (Zr, Zg, Zb))).inverted()
			matrices.append(m1)
			Sr, Sg, Sb = m1 * XYZwp
			if logfile:
				logfile.write("Correction factors: %.4f %.4f %.4f\n" %
							  (Sr, Sg, Sb))
			m2 = colormath.Matrix3x3(((Sr * Xr, Sg * Xg, Sb * Xb),
									  (Sr * Yr, Sg * Yg, Sb * Yb),
									  (Sr * Zr, Sg * Zg, Sb * Zb))).inverted()
			matrices.append(m2)
			scale = 1 + (32767 / 32768.0)
			m3 = colormath.Matrix3x3(((scale, 0, 0),
									  (0, scale, 0),
									  (0, 0, scale)))
			matrices.append(m3)
			
			for m, matrix in enumerate(matrices):
				if logfile:
					logfile.write("Matrix %i:\n" % (m + 1))
					for row in matrix:
						logfile.write("%r\n" % row)
			
			itable.matrix = m2 * m3
			if logfile:
				logfile.write("Final matrix:\n")
				for row in itable.matrix:
					logfile.write("%r\n" % row)
		else:
			# Use identity matrix for Lab as mandated by ICC spec
			itable.matrix = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]

		if profile.connectionColorSpace == "XYZ":
			if logfile:
				logfile.write("Applying matrix to input curve XYZ values...\n")
			# Apply matrix
			rX = []
			rY = []
			rZ = []
			for i in vrange:
				X, Y, Z = fpX[i], fpY[i], fpZ[i]
				X, Y, Z = m2 * (X, Y, Z)
				rX.append(X)
				rY.append(Y)
				rZ.append(Z)
			interp = (colormath.Interp(xpR, rX),
					  colormath.Interp(xpG, rY),
					  colormath.Interp(xpB, rZ))
			rinterp = (colormath.Interp(rX, xpR),
					   colormath.Interp(rY, xpG),
					   colormath.Interp(rZ, xpB))
		else:
			Lscale = 65280.0 / 65535.0
			oldmin = (xpR[0] + xpG[0] + xpB[0]) / 3.0
			oldmax = (xpR[-1] + xpG[-1] + xpB[-1]) / 3.0
			oldrange = oldmax - oldmin
			newmin = 0.0
			newmax = 100
			newrange = newmax - newmin
			xpL = []
			for i in vrange:
				v = (xpR[i] + xpG[i] + xpB[i]) / 3.0
				v = max((((v - oldmin) * newrange) / oldrange) + newmin, 0)
				xpL.append(v)
			Linterp = colormath.Interp(xpL, fpL)
			rLinterp = colormath.Interp(fpL, xpL)
		# Set input curves
		# Apply inverse TRC to input values to distribute them
		# optimally across cLUT grid points
		if logfile:
			logfile.write("Generating input curves...\n")
		itable.input = [[], [], []]
		for j in vrange:
			if self.thread_abort:
				raise Info(lang.getstr("aborted"))
			if profile.connectionColorSpace == "XYZ":
				v = [rinterp[i](j / maxval) for i in xrange(3)]
			else:
				# CIELab PCS encoding
				v = [rLinterp(j / (maxval * Lscale) * 100) / 100.0]
				v.extend([j / maxval] * 2)
			for i in xrange(len(itable.input)):
				itable.input[i].append(min(v[i] * 65535, 65535))
			if logfile and j % math.floor(maxval / 100.0) == 0:
				logfile.write("\r%i%%" % round(j / maxval * 100))
		if logfile:
			logfile.write("\n")
		if False and method and not bpc:
			# Force the blackpoint - NEVER
			if logfile:
				logfile.write("Forcing B2A input curve blackpoint...\n")
			XYZbp_m = m2 * XYZbp
			for i in xrange(3):
				black_index = int(math.ceil(maxval * XYZbp_m[i]))
				if logfile:
					logfile.write("Channel #%i\n" % i)
				for j in xrange(black_index + 1):
					v = 0
					if logfile:
						logfile.write("#%i %i -> %i\n" %
									  (j, itable.input[i][j], v))
					itable.input[i][j] = v

		if clutres == -1:
			# Auto
			clutres = 33
		step = 1.0 / (clutres - 1.0)
		do_lookup = True
		if do_lookup:
			# Generate inverse table lookup input values
			if logfile:
				logfile.write("Generating %s%i table lookup input values...\n" %
							  (source, tableno))
				logfile.write("cLUT grid res: %i\n" % clutres)
				logfile.write("Looking up input values through %s%i table...\n" %
							  (source, tableno))
			idata = []
			odata = []
			abmaxval = 255 + (255 / 256.0)
			xicclu1 = Xicclu(profile, intent, direction, "n", pcs, 100)
			if logfile:
				logfile.write("%s CAM Jab for clipping\n" %
							  (use_cam_clipping and "Using" or "Not using"))
			if use_cam_clipping:
				# Use CAM Jab for clipping for cLUT grid points after a given
				# threshold
				xicclu2 = Xicclu(profile, intent, direction, "n", pcs, 100,
								 use_cam_clipping=True)
			threshold = int((clutres - 1) * 0.75)
			threshold2 = int((clutres - 1) / 3)
			for a in xrange(clutres):
				if self.thread_abort:
					if use_cam_clipping:
						xicclu2.exit()
					xicclu1.exit()
					raise Info(lang.getstr("aborted"))
				for b in xrange(clutres):
					for c in xrange(clutres):
						d, e, f = [v * step for v in (a, b, c)]
						if profile.connectionColorSpace == "XYZ":
							# Apply TRC to XYZ values to distribute them optimally
							# across cLUT grid points.
							XYZ = [interp[i](v) for i, v in enumerate((d, e, f))]
							##print "%3.6f %3.6f %3.6f" % tuple(XYZ), '->',
							# Scale into device colorspace
							v = m2.inverted() * XYZ
							if bpc and XYZbp != [0, 0, 0]:
								v = colormath.apply_bpc(v[0], v[1], v[2],
														(0, 0, 0), XYZbp, XYZwp)
							##print "%3.6f %3.6f %3.6f" % tuple(v)
							##raw_input()
							if intent == "a":
								v = colormath.adapt(*v + [XYZwp,
														  profile.tags.wtpt.ir.values()])
						else:
							# Legacy CIELAB
							L = Linterp(d * 100)
							v = L, -128 + e * abmaxval, -128 + f * abmaxval
						idata.append("%.6f %.6f %.6f" % tuple(v))
						# Lookup CIE -> device values through profile using xicclu
						if not use_cam_clipping or (pcs == "x" and
													a <= threshold and
													b <= threshold and
													c <= threshold):
							xicclu1(v)
						if use_cam_clipping and (pcs == "l" or
												 a > threshold2 or
												 b > threshold2 or
												 c > threshold2):
							xicclu2(v)
					if logfile:
						logfile.write("\r%i%%" % round(len(idata) /
													   clutres ** 3.0 *
													   100))
			if use_cam_clipping:
				xicclu2.exit()
			xicclu1.exit()
			if logfile:
				logfile.write("\n")
			if logfile and (pcs == "x" or clutres // 2 != clutres / 2.0):
				if pcs == "x":
					iXYZbp = idata[0]
					iXYZwp = idata[-1]
					logfile.write("Input black XYZ: %s\n" % iXYZbp)
					logfile.write("Input white XYZ: %s\n" % iXYZwp)
				else:
					iLabbp = idata[clutres * (clutres // 2) + clutres // 2]
					iLabwp = idata[(clutres ** 2 * (clutres - 1) +
								   clutres * (clutres // 2) + clutres // 2)]
					logfile.write("Input black L*a*b*: %s\n" % iLabbp)
					logfile.write("Input white L*a*b*: %s\n" % iLabwp)

			odata1 = xicclu1.get()
			if not use_cam_clipping:
				odata = odata1
			elif pcs == "l":
				odata = xicclu2.get()
			else:
				# Linearly interpolate the crossover to CAM Jab clipping region
				cam_diag = False
				odata2 = xicclu2.get()
				j, k = 0, 0
				r = float(threshold - threshold2)
				for a in xrange(clutres):
					for b in xrange(clutres):
						for c in xrange(clutres):
							if a <= threshold and b <= threshold and c <= threshold:
								v = odata1[j]
								j += 1
								if a > threshold2 or b > threshold2 or c > threshold2:
									d = max(a, b, c)
									if cam_diag:
										v = [100.0, 100.0, 0.0]
										v2 = [0.0, 100.0, 100.0]
									else:
										v2 = odata2[k]
									k += 1
									for i, n in enumerate(v):
										v[i] *= (threshold - d) / r
										v2[i] *= 1 - (threshold - d) / r
										v[i] += v2[i]
							else:
								if cam_diag:
									v = [100.0, 0.0, 100.0]
								else:
									v = odata2[k]
								k += 1
							odata.append(v)
			numrows = len(odata)
			if numrows != clutres ** 3:
				raise ValueError("Number of cLUT entries (%s) exceeds cLUT res "
								 "maximum (%s^3 = %s)" % (numrows, clutres,
														  clutres ** 3))
			if logfile and (pcs == "x" or clutres // 2 != clutres / 2.0):
				if pcs == "x":
					oRGBbp = odata[0]
					oRGBwp = odata[-1]
				else:
					oRGBbp = odata[clutres * (clutres // 2) + clutres // 2]
					oRGBwp = odata[(clutres ** 2 * (clutres - 1) +
								   clutres * (clutres // 2) + clutres // 2)]
				logfile.write("Output black RGB: %.4f %.4f %.4f\n" %
							  tuple(oRGBbp))
				logfile.write("Output white RGB: %.4f %.4f %.4f\n" %
							  tuple(oRGBwp))
			odata = [[n / 100.0 for n in v] for v in odata]

		# Fill cCLUT
		itable.clut = []
		if logfile:
			logfile.write("Filling cLUT...\n")
		if not do_lookup:
			# Linearly scale RGB
			for R in xrange(clutres):
				if self.thread_abort:
					raise Info(lang.getstr("aborted"))
				for G in xrange(clutres):
					itable.clut.append([])
					for B in xrange(clutres):
						itable.clut[-1].append([v * step * 65535
												for v in (R, G, B)])
					if logfile:
						logfile.write("\r%i%%" % round((R * G * B) /
													   ((clutres - 1.0) ** 3) * 100))
		else:
			for i, RGB in enumerate(odata):
				if i % clutres == 0:
					if self.thread_abort:
						raise Info(lang.getstr("aborted"))
					itable.clut.append([])
					if logfile:
						logfile.write("\r%i%%" % round(i / (numrows - 1.0) * 100))
				# Set RGB black and white explicitly
				if pcs == "x":
					if i == 0:
						RGB = 0, 0, 0
					elif i == numrows - 1.0:
						RGB = 1, 1, 1
				elif clutres // 2 != clutres / 2.0:
					# For CIELab cLUT, white- and black point will only
					# fall on a cLUT point if uneven cLUT res
					if i == clutres * (clutres // 2) + clutres // 2:
						##if raw_input("%i %r" % (i, RGB)):
						RGB = 0, 0, 0
					elif i == (clutres ** 2 * (clutres - 1) +
							   clutres * (clutres // 2) + clutres // 2):
						##if raw_input("%i %r" % (i, RGB)):
						RGB = 1, 1, 1
				itable.clut[-1].append([v * 65535 for v in RGB])
		if logfile:
			logfile.write("\n")
		
		if getcfg("profile.b2a.hires.diagpng") and filename:
			# Generate diagnostic images
			fname, ext = os.path.splitext(filename)
			for suffix, table in [("pre", profile.tags["B2A%i" % tableno]),
								  ("post", itable)]:
				table.clut_writepng(fname + ".B2A%i.%s.CLUT.png" %
									(tableno, suffix))

		# Update profile
		profile.tags["B2A%i" % tableno] = itable

		if getcfg("profile.b2a.hires.smooth"):
			self.smooth_B2A(profile, tableno,
							getcfg("profile.b2a.hires.diagpng"), filename,
							logfile) 

		# Set output curves
		itable.output = [[], [], []]
		numentries = 256
		maxval = numentries - 1.0
		for i in xrange(len(itable.output)):
			for j in xrange(numentries):
				itable.output[i].append(j / maxval * 65535)
		
		return True

	def smooth_B2A(self, profile, tableno, diagpng=2, filename=None,
				   logfile=None):
		""" Apply extra smoothing to the cLUT """
		if not filename:
			filename = profile.fileName

		itable = profile.tags.get("B2A%i" % tableno)
		if not itable:
			return False

		clutres = len(itable.clut[0])

		if diagpng and filename:
			# Generate diagnostic images
			fname, ext = os.path.splitext(filename)
			if diagpng == 2:
				itable.clut_writepng(fname + ".B2A%i.pre-smoothing.CLUT.png" %
									 tableno)

		if logfile:
			logfile.write("Smoothing B2A%i...\n" % tableno)
		# Create a list of <clutres> number of 2D grids, each one with a
		# size of (width x height) <clutres> x <clutres>
		grids = []
		for i, block in enumerate(itable.clut):
			if i % clutres == 0:
				grids.append([])
			grids[-1].append([])
			for RGB in block:
				grids[-1][-1].append(RGB)
		for i, grid in enumerate(grids):
			for y in xrange(clutres):
				for x in xrange(clutres):
					is_dark = sum(grid[y][x]) < 65535 * .03125 * 3
					if profile.connectionColorSpace == "XYZ":
						is_gray = x == y == i
					elif clutres // 2 != clutres / 2.0:
						# For CIELab cLUT, gray will only
						# fall on a cLUT point if uneven cLUT res
						is_gray = x == y == clutres // 2
					else:
						is_gray = False
					##print i, y, x, "%i %i %i" % tuple(v / 655.35 * 2.55 for v in grid[y][x]), is_dark, raw_input(is_gray) if is_gray else ''
					if is_dark or is_gray:
						# Don't smooth dark colors and gray axis
						continue
					RGB = [[v] for v in grid[y][x]]
					# Use either "plus"-shaped or box filter depending if one
					# channel is fully saturated
					if [65535.0] in RGB:
						# Filter with a "plus" (+) shape
						if (profile.connectionColorSpace == "Lab" and
							i > clutres / 2.0):
							# Smoothing factor for L*a*b* -> RGB cLUT above 50%
							smooth = 0.25
						else:
							smooth = 1.0
						for j, c in enumerate((x, y)):
							if c > 0 and c < clutres - 1 and y < clutres - 1:
								for n in (-1, 1):
									RGBn = grid[(y, y + n)[j]][(x + n, x)[j]]
									for k in xrange(3):
										RGB[k].append(RGBn[k] * smooth +
													  RGB[k][0] * (1 - smooth))
					else:
						# Box filter, 3x3
						# Center pixel weight = 1.0, surround = 0.5
						for j in (0, 1):
							for n in (-1, 1):
								yi, xi = (y, y + n)[j], (x + n, x)[j]
								if (xi > -1 and yi > -1 and
									xi < clutres and yi < clutres):
									RGBn = grid[yi][xi]
									for k in xrange(3):
										RGB[k].append(RGBn[k] * 0.5 +
													  RGB[k][0] * 0.5)
								yi, xi = y - n, (x + n, x - n)[j]
								if (xi > -1 and yi > -1 and
									xi < clutres and yi < clutres):
									RGBn = grid[yi][xi]
									for k in xrange(3):
										RGB[k].append(RGBn[k] * 0.5 +
													  RGB[k][0] * 0.5)
					grid[y][x] = [sum(v) / float(len(v)) for v in RGB]
			for j, row in enumerate(grid):
				itable.clut[i * clutres + j] = [[v for v in RGB]
												for RGB in row]

		if diagpng and filename:
			itable.clut_writepng(fname + ".B2A%i.post.CLUT.extrasmooth.png" %
								 tableno)

		return True
	
	def get_device_id(self, quirk=True, use_serial_32=True,
					  truncate_edid_strings=False):
		""" Get org.freedesktop.ColorManager device key """
		if config.is_virtual_display():
			return None
		display_no = max(0, min(len(self.displays) - 1, 
								getcfg("display.number") - 1))
		edid = self.display_edid[display_no]
		if not edid and xrandr:
			# XrandR fallback
			if not (quirk and use_serial_32 and not truncate_edid_strings):
				return
			try:
				display_name = xrandr.get_display_name(display_no)
			except:
				pass
			else:
				if display_name:
					edid = {"monitor_name": display_name}
		return colord.device_id_from_edid(edid, quirk=quirk,
										  use_serial_32=use_serial_32,
										  truncate_edid_strings=truncate_edid_strings)

	def get_display(self):
		""" Get the currently configured display number.
		
		Returned is the Argyll CMS dispcal/dispread -d argument
		
		"""
		display_name = config.get_display_name(None, True)
		if display_name == "Web @ localhost":
			return "web:%i" % getcfg("webserver.portnumber")
		if display_name == "madVR":
			return "madvr"
		if display_name == "Untethered":
			return "0"
		if (display_name == "Resolve" or
			(display_name == "Prisma" and
			 not defaults["patterngenerator.prisma.argyll"])):
			return "1"
		if display_name == "Prisma":
			host = getcfg("patterngenerator.prisma.host")
			try:
				host = socket.gethostbyname(host)
			except socket.error:
				pass
			return "prisma:%s" % host
		if display_name.startswith("Chromecast "):
			return "cc:%s" % display_name.split(":")[0].split(None, 1)[1].strip()
		if display_name.startswith("Prisma "):
			return "prisma:%s" % display_name.split("@")[-1].strip()
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
	
	def get_display_edid(self):
		""" Return EDID of currently configured display """
		n = getcfg("display.number") - 1
		if n >= 0 and n < len(self.display_edid):
			return self.display_edid[n]
		return {}
	
	def get_display_name(self, prepend_manufacturer=False, prefer_edid=False,
						 remove_manufacturer=True):
		""" Return name of currently configured display """
		n = getcfg("display.number") - 1
		if n >= 0 and n < len(self.display_names):
			display = []
			manufacturer = None
			display_name = None
			if prefer_edid:
				edid = self.get_display_edid()
				manufacturer = edid.get("manufacturer")
				display_name = edid.get("monitor_name",
										edid.get("ascii",
												 str(edid.get("product_id") or
													 "")))
			if not manufacturer:
				manufacturer = self.display_manufacturers[n]
			if not display_name:
				display_name = self.display_names[n]
			if manufacturer:
				manufacturer = colord.quirk_manufacturer(manufacturer)
				if prepend_manufacturer:
					if manufacturer.lower() not in display_name.lower():
						display.append(manufacturer)
				elif remove_manufacturer:
					start = display_name.lower().find(manufacturer.lower())
					if start > -1:
						display_name = (display_name[:start] +
										display_name[start + len(manufacturer):]).lstrip()
						display_name = re.sub("^[^([{\w]+", "", display_name)
			display.append(display_name)
			return " ".join(display)
		return ""

	def get_display_name_short(self, prepend_manufacturer=False, prefer_edid=False):
		""" Return shortened name of configured display (if possible)
		
		If name can't be shortened (e.g. because it's already 10 characters
		or less), return full string
		
		"""
		display_name = self.get_display_name(prepend_manufacturer, prefer_edid)
		if len(display_name) > 10:
			maxweight = 0
			for part in re.findall('[^\s_]+(?:\s*\d+)?', re.sub("\([^)]+\)", "", 
																display_name)):
				digits = re.search("\d+", part)
				if digits:
					# Weigh parts with digits higher than those without
					chars = re.sub("\d+", "", part)
					weight = len(chars) + len(digits.group()) * 5
				else:
					# Weigh parts with uppercase letters higher than those without
					chars = ""
					for char in part:
						if char.lower() != char:
							chars += char
					weight = len(chars)
				if chars and weight >= maxweight:
					# Weigh parts further to the right higher
					display_name = re.sub("^[^([{\w]+", "", part)
					maxweight = weight
		return display_name
	
	def get_dispwin_display_profile_argument(self, display_no=0):
		""" Return argument corresponding to the display profile for use
		with dispwin.
		
		Will either return '-L' (use current profile) or a filename
		
		"""
		arg = "-L"
		try:
			return ICCP.get_display_profile(display_no, path_only=True) or arg
		except Exception, exception:
			safe_print(exception)
		return arg
	
	def update_display_name_manufacturer(self, ti3, display_name=None,
										 display_manufacturer=None, 
										 write=True):
		""" Update display name and manufacturer in colprof arguments
		embedded in 'ARGYLL_COLPROF_ARGS' section in a TI3 file. """
		options_colprof = []
		if not display_name and not display_manufacturer:
			# Note: Do not mix'n'match display name and manufacturer from 
			# different sources
			try:
				ti3_options_colprof = get_options_from_ti3(ti3)[1]
			except (IOError, CGATS.CGATSInvalidError, 
					CGATS.CGATSInvalidOperationError, CGATS.CGATSKeyError, 
					CGATS.CGATSTypeError, CGATS.CGATSValueError), exception:
				safe_print(exception)
				ti3_options_colprof = []
			for option in ti3_options_colprof:
				if option[0] == "M":
					display_name = option.split(None, 1)[-1][1:-1]
				elif option[0] == "A":
					display_manufacturer = option.split(None, 1)[-1][1:-1]
		if not display_name and not display_manufacturer:
			# Note: Do not mix'n'match display name and manufacturer from 
			# different sources
			edid = self.display_edid[max(0, min(len(self.displays), 
												getcfg("display.number") - 1))]
			display_name = edid.get("monitor_name",
									edid.get("ascii",
											 str(edid.get("product_id") or "")))
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
			if is_ccxx_testchart():
				options_dispcal = []
			else:
				options_dispcal = self.options_dispcal
			ti3 = add_options_to_ti3(ti3, options_dispcal, options_colprof)
			if ti3:
				ti3.write()
		return options_colprof
	
	def get_instrument_features(self, instrument_name=None):
		""" Return features of currently configured instrument """
		features = all_instruments.get(instrument_name or
									   self.get_instrument_name(), {})
		if test_require_sensor_cal:
			features["sensor_cal"] = True
			features["skip_sensor_cal"] = False
		return features
	
	def get_instrument_measurement_modes(self, instrument_id=None,
										 skip_ccxx_modes=True):
		""" Enumerate measurement modes supported by the instrument """
		if not instrument_id:
			features = self.get_instrument_features()
			instrument_id = features.get("id", self.get_instrument_name())
		if instrument_id:
			measurement_modes = self.measurement_modes.get(instrument_id,
														   OrderedDict())
			if not measurement_modes:
				result = self.exec_cmd(get_argyll_util("spotread"), ["-?"],
									   capture_output=True, skip_scripts=True,
									   silent=True, log_output=False)
				if isinstance(result, Exception):
					safe_print(result)
				if test:
					self.output.extend("""Measure spot values, Version 1.7.0_beta
Author: Graeme W. Gill, licensed under the GPL Version 2 or later
Diagnostic: Usage requested
usage: spotread [-options] [logfile]
 -v                   Verbose mode
 -s                   Print spectrum for each reading
 -S                   Plot spectrum for each reading
 -c listno            Set communication port from the following list (default 1)
    1 = 'COM13 (Klein K-10)'
    2 = 'COM1'
    3 = 'COM3'
    4 = 'COM4'
 -t                   Use transmission measurement mode
 -e                   Use emissive measurement mode (absolute results)
 -eb                  Use display white brightness relative measurement mode
 -ew                  Use display white point relative chromatically adjusted mode
 -p                   Use telephoto measurement mode (absolute results)
 -pb                  Use projector white brightness relative measurement mode
 -pw                  Use projector white point relative chromatically adjusted mode
 -a                   Use ambient measurement mode (absolute results)
 -f                   Use ambient flash measurement mode (absolute results)
 -y F                  K-10: Factory Default [Default,CB1]
    c                  K-10: Default CRT File
    P                  K-10: Klein DLP Lux
    E                  K-10: Klein SMPTE C
    b                  K-10: TVL XVM245
    d                  K-10: Klein LED Bk LCD
    m                  K-10: Klein Plasma
    p                  K-10: DLP Screen
    o                  K-10: TVL LEM150
    O                  K-10: Sony EL OLED
    z                  K-10: Eizo CG LCD
    L                  K-10: FSI 2461W
    h                  K-10: HP DreamColor 2
    1                  K-10: LCD CCFL Wide Gamut IPS (LCD2690WUXi)
    l|c                Other: l = LCD, c = CRT
 -I illum             Set simulated instrument illumination using FWA (def -i illum):
                       M0, M1, M2, A, C, D50, D50M2, D65, F5, F8, F10 or file.sp]
 -i illum             Choose illuminant for computation of CIE XYZ from spectral data & FWA:
                       A, C, D50 (def.), D50M2, D65, F5, F8, F10 or file.sp
 -Q observ            Choose CIE Observer for spectral data or CCSS instrument:
                      1931_2 (def), 1964_10, S&B 1955_2, shaw, J&V 1978_2
                      (Choose FWA during operation)
 -F filter            Set filter configuration (if aplicable):
    n                  None
    p                  Polarising filter
    6                  D65
    u                  U.V. Cut
 -E extrafilterfile   Apply extra filter compensation file
 -x                   Display Yxy instead of Lab
 -h                   Display LCh instead of Lab
 -V                   Show running average and std. devation from ref.
 -T                   Display correlated color temperatures and CRI
 -N                   Disable auto calibration of instrument
 -O                   Do one cal. or measure and exit
 -H                   Start in high resolution spectrum mode (if available)
 -X file.ccmx         Apply Colorimeter Correction Matrix
 -Y r|n               Override refresh, non-refresh display mode
 -Y R:rate            Override measured refresh rate with rate Hz
 -Y A                 Use non-adaptive integration time mode (if available).
 -W n|h|x             Override serial port flow control: n = none, h = HW, x = Xon/Xoff
 -D [level]           Print debug diagnostics to stderr
 logfile              Optional file to save reading results as text""".splitlines())
				measurement_modes_follow = False
				if self.argyll_version >= [1, 7, 1]:
					technology_strings = technology_strings_171
				else:
					technology_strings = technology_strings_170
				for line in self.output:
					line = line.strip()
					if line.startswith("-y "):
						line = line.lstrip("-y ")
						measurement_modes_follow = True
					elif line.startswith("-"):
						measurement_modes_follow = False
					parts = [v.strip() for v in line.split(None, 1)]
					if measurement_modes_follow and len(parts) == 2:
						measurement_mode, desc = parts
						if (measurement_mode not in
							(string.digits[1:] + string.ascii_letters)):
							# Ran out of selectors
							continue
						measurement_mode_instrument_id, desc = desc.split(":",
																		  1)
						desc = desc.strip()
						if measurement_mode_instrument_id == instrument_id:
							# Found a mode for our instrument
							if (re.sub(r"\s*\(.*?\)$", "", desc) in
								technology_strings.values() + [""] and
								skip_ccxx_modes):
								# This mode is supplied via CCMX/CCSS, skip
								continue
							desc = re.sub(r"\s*(?:File|\[[^\]]*\])", "", desc)
							measurement_modes[measurement_mode] = desc
				self.measurement_modes[instrument_id] = measurement_modes
			return measurement_modes
		return {}
	
	def get_instrument_name(self):
		""" Return name of currently configured instrument """
		n = getcfg("comport.number") - 1
		if n >= 0 and n < len(self.instruments):
			return self.instruments[n]
		return ""
	
	def has_lut_access(self):
		display_no = min(len(self.lut_access), getcfg("display.number")) - 1
		return display_no > -1 and bool(self.lut_access[display_no])
	
	def has_separate_lut_access(self):
		""" Return True if separate LUT access is possible and needed. """
		# Filter out Prisma, Resolve and Untethered
		# IMPORTANT: Also make changes to display filtering in
		# worker.Worker.enumerate_displays_and_ports
		lut_access = self.lut_access[:-3]
		if self.argyll_version >= [1, 6, 0]:
			# Filter out madVR
			lut_access = lut_access[:-1]
		if self.argyll_version >= [1, 4, 0]:
			# Filter out Web @ localhost
			lut_access = lut_access[:-1]
		return (len(self.displays) > 1 and False in lut_access and True in 
				lut_access)
	
	def import_colorimeter_corrections(self, cmd, args=None, asroot=False):
		""" Import colorimeter corrections. cmd can be 'i1d3ccss', 'spyd4en'
		or 'oeminst' """
		if not args:
			args = []
		if (is_superuser() or asroot) and not "-Sl" in args:
			# If we are root or need root privs anyway, install to local
			# system scope
			args.insert(0, "-Sl")
		return self.exec_cmd(cmd, ["-v"] + args, capture_output=True, 
							 skip_scripts=True, silent=False,
							 asroot=asroot)
	
	def import_edr(self, args=None, asroot=False):
		""" Import X-Rite .edr files """
		return self.import_colorimeter_corrections(get_argyll_util("i1d3ccss"),
												   args, asroot)
	
	def import_spyd4cal(self, args=None, asroot=False):
		""" Import Spyder4/5 calibrations to spy4cal.bin """
		return self.import_colorimeter_corrections(get_argyll_util("spyd4en"),
												   args, asroot)

	def install_3dlut(self, path, filename=None):
		basename = os.path.basename(getcfg("3dlut.input.profile"))
		if getcfg("3dlut.format") == "madVR" and madvr:
			# Install (load) 3D LUT using madTPG
			# Get mapping from source profile to madVR gamut slot
			gamut = {"Rec709.icm": 0,
					 "SMPTE_RP145_NTSC.icm": 1,
					 "EBU3213_PAL.icm": 2,
					 "Rec2020.icm": 3,
					 "SMPTE431_P3.icm": 4}.get(basename, 0)
			try:
				# Connect & load 3D LUT
				if (self.madtpg_connect() and
					self.madtpg.load_3dlut_file(path, True, gamut)):
					raise Info(lang.getstr("3dlut.install.success"))
				else:
					raise Error(lang.getstr("3dlut.install.failure"))
			except Exception, exception:
				return exception
			finally:
				if hasattr(self, "madtpg"):
					self.madtpg.quit()
					if isinstance(self.madtpg, madvr.MadTPG_Net):
						self.madtpg.shutdown()
		elif config.get_display_name(None, True) == "Prisma":
			try:
				# Use Prisma HTTP REST interface to upload 3D LUT
				if not self.patterngenerator:
					self.setup_patterngenerator()
				self.patterngenerator.connect()
				# Check preset. If it has a custom LUT assigned, we delete the
				# currently assigned LUT before uploading, unless its filename
				# is the same as the LUT to be uploaded, in which case it will
				# be simply overwritten, and unless the custom LUT is still
				# assigned to another preset as well.
				presetname = getcfg("patterngenerator.prisma.preset")
				if False:
					# NEVER?
					# Check all presets for currently assigned LUT
					# Check the preset we're going to use for the upload last
					presetnames = filter(lambda name: name != presetname,
										 config.valid_values["patterngenerator.prisma.preset"])
				else:
					# Check only the preset we're going to use for the upload
					presetnames = []
				presetnames.append(presetname)
				assigned_luts = {}
				for presetname in presetnames:
					self.log("Loading Prisma preset", presetname)
					preset = self.patterngenerator.load_preset(presetname)
					assigned_lut = preset["settings"].get("cube", "")
					if not assigned_lut in assigned_luts:
						assigned_luts[assigned_lut] = 0
					assigned_luts[assigned_lut] += 1
				# Only remove the currently assigned custom LUT if it's not
				# assigned to another preset
				if (assigned_lut.lower().endswith(".3dl") and
					assigned_luts[assigned_lut] == 1):
					remove = preset["settings"]["cube"]
				else:
					remove = False
				# Check total size of installed 3D LUTs. The Prisma has 1 MB of
				# custom LUT storage, which is enough for 15 67 KB LUTs.
				maxsize = 1024 * 67 * 15
				installed = self.patterngenerator.get_installed_3dluts()
				rawlen = len(installed["raw"])
				size = 0
				numinstalled = 0
				for table in installed["tables"]:
					if table.get("n") != remove:
						size += table.get("s", 0)
						numinstalled += 1
					else:
						rawlen -= len('{"n":"%s", "s":%i},' %
									  (table["n"], table.get("s", 0)))
				filesize = os.stat(path).st_size
				size_exceeded = size + filesize > maxsize
				# NOTE that due to a bug in the Prisma firmware (1.02),
				# responses are sometimes truncated to 512 bytes, which means
				# with the current 3D LUT naming scheme we can effectively only
				# store two of them.
				response_len_exceeded = rawlen + len('{"n":"%s", "s":%i},' %
													 (filename, filesize)) > 512
				# NOTE that the total number of 3D LUT slots seems to be limited
				# to 32, which includes built-in LUTs.
				maxluts = 32
				luts_exceeded = numinstalled >= maxluts
				if size_exceeded or response_len_exceeded or luts_exceeded:
					if size_exceeded:
						missing = size + filesize - maxsize
					elif luts_exceeded:
						missing = filesize * (numinstalled + 1 - maxluts)
					else:
						missing = size + filesize - 1024 * 67 * 2
					raise Error(lang.getstr("3dlut.holder.out_of_memory",
											(getcfg("patterngenerator.prisma.host"),
											 round(missing / 1024.0),
											 getcfg("patterngenerator.prisma.host"),
											 "Prisma")))
				if remove and remove != filename:
					self.log("Removing currently assigned LUT", remove)
					self.patterngenerator.remove_3dlut(remove)
				self.log("Uploading LUT", path, "as", filename)
				self.patterngenerator.load_3dlut_file(path, filename)
				self.log("Setting LUT", filename)
				self.patterngenerator.set_3dlut(filename)
				self.log("Setting PrismaVue to zero")
				self.patterngenerator.set_prismavue(0)
			except Exception, exception:
				return exception
			return Info(lang.getstr("3dlut.install.success"))
		else:
			return Error(lang.getstr("3dlut.install.unsupported"))

	def install_profile(self, profile_path, capture_output=True,
						skip_scripts=False, silent=False):
		""" Install a profile by copying it to an appropriate location and
		registering it with the system """
		colord_install = None
		oy_install = None
		argyll_install = self._install_profile_argyll(profile_path,
													  capture_output,
													  skip_scripts, silent)
		if argyll_install and sys.platform == "win32":
			# Assign profile to active display
			display_no = min(len(self.displays), getcfg("display.number")) - 1
			ICCP.set_display_profile(os.path.basename(profile_path), display_no,
									 use_active_display_device=True)
		loader_install = None
		profile = None
		try:
			profile = ICCP.ICCProfile(profile_path)
		except (IOError, ICCP.ICCProfileInvalidError), exception:
			return exception
		device_id = self.get_device_id(quirk=True)
		if (sys.platform not in ("darwin", "win32") and not getcfg("dry_run") and
			(self.argyll_version < [1, 6] or not whereis("libcolordcompat.so.*") or
			 argyll_install is not True) and
			which("colormgr")):
			if device_id:
				result = False
				# Try a range of possible device IDs
				device_ids = [device_id,
							  self.get_device_id(quirk=True,
												 truncate_edid_strings=True),
							  self.get_device_id(quirk=True,
												 use_serial_32=False),
							  self.get_device_id(quirk=True,
												 use_serial_32=False,
												 truncate_edid_strings=True),
							  self.get_device_id(quirk=False),
							  self.get_device_id(quirk=False,
												 truncate_edid_strings=True),
							  self.get_device_id(quirk=False,
												 use_serial_32=False),
							  self.get_device_id(quirk=False,
												 use_serial_32=False,
												 truncate_edid_strings=True)]
				for device_id in OrderedDict.fromkeys(device_ids).iterkeys():
					if device_id:
						# NOTE: This can block
						result = self._install_profile_colord(profile,
															  device_id)
						if isinstance(result, colord.CDObjectQueryError):
							# Device ID was not found, try next one
							continue
						else:
							# Either returned ok or there was another error
							break
				colord_install = result
			if not device_id or result is not True:
				gcm_import = bool(which("gcm-import"))
				if gcm_import:
					self._install_profile_gcm(profile)
					# gcm-import doesn't seem to return a useful exit code or
					# stderr output, so check for our profile
					profilename = os.path.basename(profile.fileName)
					for dirname in iccprofiles_home:
						profile_install_path = os.path.join(dirname, profilename)
						if os.path.isfile(profile_install_path):
							colord_install = Warn(lang.getstr("profile.import.success"))
							break
		if (which("oyranos-monitor") and
			self.check_display_conf_oy_compat(getcfg("display.number"))):
			if device_id:
				profile_name = re.sub("[- ]", "_", device_id.lower()) + ".icc"
			else:
				profile_name = None
			result = self._install_profile_oy(profile_path, profile_name,
											  capture_output, skip_scripts,
											  silent)
			oy_install = result
		if (argyll_install is not True and
			((colord_install and not isinstance(colord_install,
												colord.CDError)) or
			 oy_install is True)):
			# Ignore Argyll install errors if colord or Oyranos install was
			# succesful
			argyll_install = None
		# Check if atleast one of our profile install methods did return a
		# result that is not an error
		for result in (argyll_install, colord_install, oy_install):
			check = result is True or isinstance(result, Warning)
			if check:
				break
		# Only go on to create profile loader if profile loading on login
		# isn't disabled in the config file, and we are not under Mac OS X
		# (no loader required  there), and if atleast one of our profile
		# install methods did return a result that is not an error
		if (getcfg("profile.load_on_login") and sys.platform != "darwin" and
			check):
			# Create profile loader. Failing to create it is a critical error 
			# under Windows if calibration loading isn't handled by the OS
			# (this is checked), and also under Linux if colord profile install
			# failed (colord handles loading otherwise)
			check = (sys.platform == "win32" or
					 (not colord_install or isinstance(colord_install,
													   colord.CDError)))
			if (getcfg("profile.install_scope") == "l"):
				# We need a system-wide config file to store the path to 
				# the Argyll binaries for the profile loader
				if (not config.makecfgdir("system", self) or
					(not config.writecfg("system", self) and check)):
					# If the system-wide config dir could not be created,
					# or the system-wide config file could not be written,
					# error out if under Windows or if under Linux but
					# colord profile install failed
					return Error(lang.getstr("error.autostart_system"))
			if sys.platform == "win32":
				loader_install = self._install_profile_loader_win32(silent)
			else:
				loader_install = self._install_profile_loader_xdg(silent)
			if loader_install is not True and check:
				return loader_install
		# Check if atleast one of our profile install methods returned a result
		for result in (argyll_install, colord_install, oy_install):
			if result is not None:
				return argyll_install, colord_install, oy_install, loader_install
		if not result:
			# This should never happen
			result = Error(lang.getstr("profile.install.error"))
		return result

	def install_argyll_instrument_conf(self, uninstall=False, filenames=None):
		""" (Un-)install Argyll CMS instrument configuration under Linux """
		udevrules = "/etc/udev/rules.d"
		hotplug = "/etc/hotplug"
		if not os.path.isdir(udevrules) and not os.path.isdir(hotplug):
			return Error(lang.getstr("udev_hotplug.unavailable"))
		if not filenames:
			filenames = self.get_argyll_instrument_conf("installed" if uninstall
														else None)
		if not filenames:
			return Error("\n".join(lang.getstr("file.missing", filename)
								   for filename in
								   self.get_argyll_instrument_conf("expected")))
		for filename in filenames:
			if filename.endswith(".rules"):
				dst = udevrules
			else:
				dst = hotplug
			if uninstall:
				# Move file to backup location
				backupdir = "".join([os.path.join(config.datahome, "backup"),
									 os.path.dirname(filename)])
				if not os.path.isdir(backupdir):
					os.makedirs(backupdir)
				cmd, args = "mv", ["-f", filename,
								   "".join([os.path.join(config.datahome,
														"backup"),
										    filename])]
			else:
				cmd, args = "cp", ["-f", filename]
				args.append(os.path.join(dst, os.path.basename(filename)))
			result = self.exec_cmd(cmd, args, capture_output=True,
								   skip_scripts=True, asroot=True)
			if result is not True:
				break
		if result is True and dst == udevrules:
			# Reload udev rules
			udevadm = which("udevadm", ["/sbin"])
			if udevadm:
				result = self.exec_cmd(udevadm, ["control", "--reload-rules"],
									   capture_output=True,
									   skip_scripts=True, asroot=True)
		return result
	
	def install_argyll_instrument_drivers(self, uninstall=False,
										  launch_devman=False):
		""" (Un-)install the Argyll CMS instrument drivers under Windows """
		winxp = sys.getwindowsversion() < (6,)
		if launch_devman:
			if winxp:
				cmd = "start"
				args = ["mmc", "devmgmt.msc"]
			else:
				cmd = "mmc"
				args = ["devmgmt.msc"]
			self.exec_cmd(cmd, args, capture_output=True, skip_scripts=True,
						  asroot=not winxp, shell=winxp, working_dir=False)
		if not uninstall:
			usbinfpath = get_data_path("usb/ArgyllCMS.inf")
			if not usbinfpath:
				return Error(lang.getstr("file.missing", "usb/ArgyllCMS.inf"))
		if not winxp:
			# Windows Vista and newer
			with win64_disable_file_system_redirection():
				pnputil = which("PnPutil.exe")
				if not pnputil:
					return Error(lang.getstr("file.missing", "PnPutil.exe"))
				if uninstall:
					result = self.exec_cmd(pnputil, ["-e"], capture_output=True,
										   log_output=False, silent=True,
										   skip_scripts=True)
					if not result:
						return Error(lang.getstr("argyll.instrument.drivers.uninstall.failure"))
					elif isinstance(result, Exception):
						return result
					output = universal_newlines("".join(self.output))
					for entry in output.split("\n\n"):
						entry = [line.split(":", 1)[-1].strip()
								 for line in entry.split("\n")]
						for value in entry:
							if value == "ArgyllCMS":
								result = self.exec_cmd(pnputil,
													   ["-f", "-d", entry[0]],
													   capture_output=True,
													   skip_scripts=True,
													   asroot=True)
					return result
				else:
					return self.exec_cmd(pnputil, ["-i", "-a", usbinfpath],
										 capture_output=True, skip_scripts=True,
										 asroot=True)
		else:
			# Windows XP
			#subkey = "\\".join(["Software", "Microsoft", "Windows", 
								#"CurrentVersion"])
			#try:
				#key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, subkey, 0,
									  #_winreg.KEY_READ |
									  #_winreg.KEY_QUERY_VALUE |
									  #_winreg.KEY_SET_VALUE)
				#newvalue = value = _winreg.QueryValueEx(key, "DevicePath")[0]
				#if uninstall:
					## No real uninstallation possible. Just remove all paths
					## ending in '\argyllcms.inf'
					#paths = []
					#for path in value.split(os.pathsep):
						#path = os.path.normpath(path)
						#if not path.lower().endswith(r"\argyllcms.inf"):
							#paths.append(path)
					#newvalue = os.pathsep.join(paths)
				#elif not usbinfpath.lower() in value.lower().split(os.pathsep):
					#newvalue = value + os.pathsep + usbinfpath
				#if newvalue != value:
					#_winreg.SetValueEx(key, "DevicePath", 0,
									   #_winreg.REG_EXPAND_SZ, newvalue)
			#except Exception, exception:
				#return exception
			if uninstall:
				# Uninstallation not supported
				pass
			else:
				sections = ["LIBUSB0_DEV"]
				#with open(usbinfpath, "rb") as usbinf:
					#sections += re.findall(r"\[(\w+_Devices)\]", usbinf.read())
				working_dir, infbasename = os.path.split(usbinfpath)
				result = True
				for section in sections:
					result = self.exec_cmd(which("rundll32.exe"),
										   ["setupapi,InstallHinfSection",
											section, "132",
											os.path.join(".", infbasename)],
										   capture_output=True,
										   skip_scripts=True,
										   working_dir=working_dir)
					if isinstance(result, Exception) or not result:
						break
				if not result:
					result = Error(lang.getstr("argyll.instrument.drivers.install.failure"))
			return result
	
	def _install_profile_argyll(self, profile_path, capture_output=False,
								skip_scripts=False, silent=False):
		""" Install profile using dispwin """
		if (sys.platform == "darwin" and False):  # NEVER
			# Alternate way of 'installing' the profile under OS X by just
			# copying it
			profiles = os.path.join("Library", "ColorSync", "Profiles")
			profile_install_path = os.path.join(profiles,
												os.path.basename(profile_path))
			network = os.path.join(os.path.sep, "Network", profiles)
			if getcfg("profile.install_scope") == "l":
				profile_install_path = os.path.join(os.path.sep,
													profile_install_path)
			elif (getcfg("profile.install_scope") == "n" and
				  os.path.isdir(network)):
				profile_install_path = os.path.join(network,
													profile_install_path)
			else:
				profile_install_path = os.path.join(os.path.expanduser("~"),
													profile_install_path)
			cmd, args = "cp", ["-f", profile_path, profile_install_path]
			result = self.exec_cmd(cmd, args, capture_output, 
								   low_contrast=False, 
								   skip_scripts=skip_scripts, 
								   silent=silent,
								   asroot=getcfg("profile.install_scope") in ("l", "n"),
								   title=lang.getstr("profile.install"))
			if not isinstance(result, Exception) and result:
				self.output = ["Installed"]
		else:
			if sys.platform == "win32" and sys.getwindowsversion() >= (6, ):
				try:
					per_user_profiles = util_win.per_user_profiles_isenabled(getcfg("display.number") - 1)
				except Exception, exception:
					per_user_profiles = None
					self.log("util_win.per_user_profiles_isenabled(%s): %s" %
							 (getcfg("display.number") - 1,
							  safe_unicode(exception)))
				if not per_user_profiles:
					# Enable per-user profiles under Vista / Windows 7
					try:
						util_win.enable_per_user_profiles(True,
														  getcfg("display.number") - 1)
					except Exception, exception:
						self.log("util_win.enable_per_user_profiles(True, %s): %s" %
								   (getcfg("display.number") - 1,
									safe_unicode(exception)))
			cmd, args = self.prepare_dispwin(None, profile_path, True)
			if not isinstance(cmd, Exception):
				if "-Sl" in args and (sys.platform != "darwin" or 
									  intlist(mac_ver()[0].split(".")) >= [10, 6]):
					# If a 'system' install is requested under Linux,
					# Mac OS X >= 10.6 or Windows, 
					# install in 'user' scope first because a system-wide install 
					# doesn't also set it as current user profile on those systems 
					# (on Mac OS X < 10.6, we can use ColorSyncScripting to set it).
					# It has the small drawback under Linux and OS X 10.6 that 
					# it will copy the profile to both the user and system-wide 
					# locations, though, which is not a problem under Windows as 
					# they are the same.
					args.remove("-Sl")
					result = self.exec_cmd(cmd, args, capture_output, 
												  low_contrast=False, 
												  skip_scripts=skip_scripts, 
												  silent=silent,
												  title=lang.getstr("profile.install"))
					output = list(self.output)
					args.insert(0, "-Sl")
				else:
					output = None
					result = True
				if not isinstance(result, Exception) and result:
					result = self.exec_cmd(cmd, args, capture_output, 
										   low_contrast=False, 
										   skip_scripts=skip_scripts, 
										   silent=silent,
										   title=lang.getstr("profile.install"))
			else:
				result = cmd
		if not isinstance(result, Exception) and result is not None:
			result = False
			for line in output or self.output:
				if "Installed" in line:
					if (sys.platform == "darwin" and "-Sl" in args and
					    intlist(mac_ver()[0].split(".")) < [10, 6]):
						# The profile has been installed, but we need a little 
						# help from AppleScript to actually make it the default 
						# for the current user. Only works under Mac OS < 10.6
						n = getcfg("display.number")
						path = os.path.join(os.path.sep, "Library", 
											"ColorSync", "Profiles", 
											os.path.basename(args[-1]))
						applescript = ['tell app "ColorSyncScripting"',
										   'set displayProfile to POSIX file "%s" as alias' % path,
										   'set display profile of display %i to displayProfile' % n,
									   'end tell']
						try:
							retcode, output, errors = osascript(applescript)
						except Exception, exception:
							self.log(exception)
						else:
							if errors.strip():
								self.log("osascript error: %s" % errors)
							else:
								result = True
						break
					elif (sys.platform == "darwin" and False):  # NEVER
						# After 'installing' a profile under Mac OS X by just
						# copying it, show system preferences
						applescript = ['tell application "System Preferences"',
										   'activate',
										   'set current pane to pane id "com.apple.preference.displays"',
										   'reveal (first anchor of current pane whose name is "displaysColorTab")',
										   # This needs access for assistive devices enabled
										   #'tell application "System Events"',
											   #'tell process "System Preferences"',
												   #'select row 2 of table 1 of scroll area 1 of group 1 of tab group 1 of window "<Display name from EDID here>"',
											   #'end tell',
										   #'end tell',
									   'end tell']
						try:
							retcode, output, errors = osascript(applescript)
						except Exception, exception:
							self.log(exception)
						else:
							if errors.strip():
								self.log("osascript error: %s" % errors)
							else:
								result = True
					else:
						result = True
					break
			if not result and self.errors:
				result = Error("".join(self.errors).strip())
		# DO NOT call wrapup() here, it'll remove the profile in the temp
		# directory before dispwin can get a hold of it when running with UAC
		# under Windows, because that makes the call to dispwin run in a
		# separate thread. DisplayCAL.MainFrame.profile_finish_consumer calls
		# DisplayCAL.MainFrame.start_timers(True) after displaying the result
		# message which takes care of cleanup.
		return result
	
	def _install_profile_colord(self, profile, device_id):
		""" Install profile using colord """
		self.log("%s: Trying device ID %r" % (appname, device_id))
		try:
			colord.install_profile(device_id, profile, logfn=self.log)
		except Exception, exception:
			self.log(exception)
			return exception
		return True
	
	def _install_profile_gcm(self, profile):
		""" Install profile using gcm-import """
		if which("colormgr"):
			# Check if profile already exists in database
			try:
				colord.get_object_path("icc-" + hexlify(profile.ID), "profile")
			except colord.CDObjectQueryError:
				# Profile not in database
				pass
			except colord.CDError, exception:
				self.log(exception)
			else:
				# Profile already in database, nothing to do
				return None
		# gcm-import will check if the profile is already in the database
		# (based on profile ID), but will fail to overwrite a profile with the
		# same name. We need to remove those profiles so gcm-import can work.
		profilename = os.path.basename(profile.fileName)
		for dirname in iccprofiles_home:
			profile_install_path = os.path.join(dirname, profilename)
			if os.path.isfile(profile_install_path) and \
			   profile_install_path != profile.fileName:
				try:
					trash([profile_install_path])
				except Exception, exception:
					self.log(exception)
				else:
					# Give colord time to recognize that the profile was
					# removed, otherwise gcm-import may complain if it's
					# a profile that was already in the database
					sleep(3)
		if self._progress_wnd and not getattr(self._progress_wnd, "dlg", None):
			self._progress_wnd.dlg = DummyDialog()
		# Run gcm-import
		cmd, args = which("gcm-import"), [profile.fileName]
		# gcm-import does not seem to return a useful exit code (it's always 1)
		# or stderr output
		self.exec_cmd(cmd, args, capture_output=True, skip_scripts=True)
	
	def _install_profile_oy(self, profile_path, profile_name=None,
							capture_output=False, skip_scripts=False,
							silent=False):
		""" Install profile using oyranos-monitor """
		display = self.displays[max(0, min(len(self.displays) - 1,
										   getcfg("display.number") - 1))]
		x, y = [pos.strip() for pos in display.split("@")[-1].split(",")[0:2]]
		if getcfg("profile.install_scope") == "l":
			# If system-wide install, copy profile to 
			# /var/lib/color/icc/devices/display
			var_icc = "/var/lib/color/icc/devices/display"
			if not profile_name:
				profile_name = os.path.basename(profile_path)
			profile_install_path = os.path.join(var_icc, profile_name)
			result = self.exec_cmd("mkdir", 
								   ["-p", os.path.dirname(profile_install_path)], 
								   capture_output=True, low_contrast=False, 
								   skip_scripts=True, silent=True, asroot=True)
			if not isinstance(result, Exception) and result:
				result = self.exec_cmd("cp", ["-f", profile_path, 
											  profile_install_path], 
									   capture_output=True, low_contrast=False, 
									   skip_scripts=True, silent=True, 
									   asroot=True)
		else:
			result = True
			dirname = None
			for dirname in iccprofiles_display_home:
				if os.path.isdir(dirname):
					# Use the first one that exists
					break
				else:
					dirname = None
			if not dirname:
				# Create the first one in the list
				dirname = iccprofiles_display_home[0]
				try:
					os.makedirs(dirname)
				except Exception, exception:
					self.log(exception)
					result = False
			if result is not False:
				profile_install_path = os.path.join(dirname,
													os.path.basename(profile_path))
				try:
					shutil.copyfile(profile_path, 
									profile_install_path)
				except Exception, exception:
					self.log(exception)
					result = False
		if not isinstance(result, Exception) and result is not False:
			cmd = which("oyranos-monitor")
			args = ["-x", x, "-y", y, profile_install_path]
			result = self.exec_cmd(cmd, args, capture_output, 
								  low_contrast=False, skip_scripts=skip_scripts, 
								  silent=silent, working_dir=False)
			##if getcfg("profile.install_scope") == "l":
				##result = self.exec_cmd(cmd, args, 
											  ##capture_output, 
											  ##low_contrast=False, 
											  ##skip_scripts=skip_scripts, 
											  ##silent=silent,
											  ##asroot=True,
											  ##working_dir=False)
		if not result and self.errors:
			result = Error("".join(self.errors).strip())
		return result
	
	def _install_profile_loader_win32(self, silent=False):
		""" Install profile loader """
		if (sys.platform == "win32" and sys.getwindowsversion() >= (6, 1) and
			util_win.calibration_management_isenabled()):
			self._uninstall_profile_loader_win32()
			return True
		# Must return either True on success or an Exception object on error
		result = True
		# Remove outdated (pre-0.5.5.9) profile loaders
		display_no = self.get_display()
		name = "%s Calibration Loader (Display %s)" % (appname, display_no)
		if autostart_home:
			loader_v01b = os.path.join(autostart_home, 
									   ("dispwin-d%s-c-L" % display_no) + 
									   ".lnk")
			if os.path.exists(loader_v01b):
				try:
					# delete v0.1b loader
					os.remove(loader_v01b)
				except Exception, exception:
					self.log(u"Warning - could not remove old "
							   u"v0.1b calibration loader '%s': %s" 
							   % tuple(safe_unicode(s) for s in 
									   (loader_v01b, exception)))
			loader_v02b = os.path.join(autostart_home, 
									   name + ".lnk")
			if os.path.exists(loader_v02b):
				try:
					# delete v02.b/v0.2.1b loader
					os.remove(loader_v02b)
				except Exception, exception:
					self.log(u"Warning - could not remove old "
							   u"v0.2b calibration loader '%s': %s" 
							   % tuple(safe_unicode(s) for s in 
									   (loader_v02b, exception)))
			loader_v0558 = os.path.join(autostart_home, 
										name + ".lnk")
			if os.path.exists(loader_v0558):
				try:
					# delete v0.5.5.8 user loader
					os.remove(loader_v0558)
				except Exception, exception:
					self.log(u"Warning - could not remove old "
							   u"v0.2b calibration loader '%s': %s" 
							   % tuple(safe_unicode(s) for s in 
									   (loader_v02b, exception)))
		if autostart:
			loader_v0558 = os.path.join(autostart, 
										name + ".lnk")
			if os.path.exists(loader_v0558):
				try:
					# delete v0.5.5.8 system loader
					os.remove(loader_v0558)
				except Exception, exception:
					self.log(u"Warning - could not remove old "
							   u"v0.2b calibration loader '%s': %s" 
							   % tuple(safe_unicode(s) for s in 
									   (loader_v02b, exception)))
		# Create unified loader
		name = appname + " Profile Loader"
		if autostart:
			autostart_lnkname = os.path.join(autostart,
											 name + ".lnk")
		if autostart_home:
			autostart_home_lnkname = os.path.join(autostart_home, 
												  name + ".lnk")
		loader_args = []
		if os.path.basename(sys.executable).lower() in ("python.exe", 
														"pythonw.exe"):
			cmd = os.path.join(os.path.dirname(sys.executable),
							   "pythonw.exe")
			pyw = os.path.normpath(os.path.join(pydir, "..",
												appname +
												"-apply-profiles.pyw"))
			if os.path.exists(pyw):
				# Running from source or 0install
				# Check if this is a 0install implementation, in which
				# case we want to call 0launch with the appropriate
				# command
				if re.match("sha\d+(?:new)?",
							os.path.basename(os.path.dirname(pydir))):
					cmd = which("0install-win.exe") or "0install-win.exe"
					loader_args.extend(["run", "--batch", "--no-wait",
										"--offline",
										"--command=run-apply-profiles",
										"http://%s/0install/%s.xml" %
										(domain.lower(), appname)])
				else:
					# Running from source
					loader_args.append(u'"%s"' % pyw)
			else:
				# Regular install
				loader_args.append(u'"%s"' % get_data_path(os.path.join("scripts", 
																		appname + "-apply-profiles")))
		else:
			cmd = os.path.join(pydir, appname + "-apply-profiles.exe")
		not_main_thread = currentThread().__class__ is not _MainThread
		if not_main_thread:
			# If running in a thread, need to call pythoncom.CoInitialize
			pythoncom.CoInitialize()
		try:
			scut = pythoncom.CoCreateInstance(win32com_shell.CLSID_ShellLink, None,
											  pythoncom.CLSCTX_INPROC_SERVER, 
											  win32com_shell.IID_IShellLink)
			scut.SetPath(cmd)
			if len(loader_args) == 1:
				scut.SetWorkingDirectory(pydir)
			if os.path.basename(cmd) == appname + "-apply-profiles.exe":
				scut.SetIconLocation(cmd, 0)
			else:
				scut.SetIconLocation(get_data_path(os.path.join("theme",
																"icons", 
																appname +
																"-apply-profiles.ico")), 0)
			scut.SetArguments(" ".join(loader_args))
			scut.SetShowCmd(win32con.SW_SHOWDEFAULT)
			if is_superuser():
				if autostart:
					try:
						scut.QueryInterface(pythoncom.IID_IPersistFile).Save(autostart_lnkname, 0)
					except Exception, exception:
						if not silent:
							result = Warning(lang.getstr("error.autostart_creation", 
													     autostart) + "\n" + 
										     safe_unicode(exception))
						# Now try user scope
				else:
					if not silent:
						result = Warning(lang.getstr("error.autostart_system"))
			if autostart_home:
				if (autostart and 
					os.path.isfile(autostart_lnkname)):
					# Remove existing user loader
					if os.path.isfile(autostart_home_lnkname):
						os.remove(autostart_home_lnkname)
				else:
					# Only create user loader if no system loader
					try:
						scut.QueryInterface(
							pythoncom.IID_IPersistFile).Save(
								autostart_home_lnkname, 0)
					except Exception, exception:
						if not silent:
							result = Warning(lang.getstr("error.autostart_creation", 
													     autostart_home) + "\n" + 
										     safe_unicode(exception))
			else:
				if not silent:
					result = Warning(lang.getstr("error.autostart_user"))
		except Exception, exception:
			if not silent:
				result = Warning(lang.getstr("error.autostart_creation", 
										     autostart_home) + "\n" + 
							     safe_unicode(exception))
		finally:
			if not_main_thread:
				# If running in a thread, need to call pythoncom.CoUninitialize
				pythoncom.CoUninitialize()
		if not os.path.isfile(os.path.join(config.confighome,
										   appbasename + "-apply-profiles.lock")):
			# Run profile loader TSR program if not yet loaded
			if loader_args:
				cmdline = '%s" %s "--skip' % (cmd, " ".join(loader_args))
			else:
				cmdline = '%s" "--skip' % cmd
			launch_file(cmdline)
		return result
	
	def _uninstall_profile_loader_win32(self):
		""" Uninstall profile loader """
		name = appname + " Profile Loader"
		if autostart and is_superuser():
			autostart_lnkname = os.path.join(autostart,
											 name + ".lnk")
			if os.path.exists(autostart_lnkname):
				try:
					os.remove(autostart_lnkname)
				except Exception, exception:
					self.log(autostart_lnkname, exception)
		if autostart_home:
			autostart_home_lnkname = os.path.join(autostart_home, 
												  name + ".lnk")
			if os.path.exists(autostart_home_lnkname):
				try:
					os.remove(autostart_home_lnkname)
				except Exception, exception:
					self.log(autostart_home_lnkname, exception)
		return True
	
	def _install_profile_loader_xdg(self, silent=False):
		""" Install profile loader """
		# See http://standards.freedesktop.org/autostart-spec
		# Must return either True on success or an Exception object on error
		result = True
		# Remove outdated (pre-0.5.5.9) profile loaders
		name = "%s-Calibration-Loader-Display-%s" % (appname,
													 self.get_display())
		desktopfile_path = os.path.join(autostart_home, 
										name + ".desktop")
		oy_desktopfile_path = os.path.join(autostart_home, 
										   "oyranos-monitor.desktop")
		system_desktopfile_path = os.path.join(
			autostart, name + ".desktop")
		# Remove old (pre-0.5.5.9) dispwin user loader
		if os.path.exists(desktopfile_path):
			try:
				os.remove(desktopfile_path)
			except Exception, exception:
				result = Warning(lang.getstr("error.autostart_remove_old", 
										     desktopfile_path))
		# Remove old (pre-0.5.5.9) oyranos user loader
		if os.path.exists(oy_desktopfile_path):
			try:
				os.remove(oy_desktopfile_path)
			except Exception, exception:
				result = Warning(lang.getstr("error.autostart_remove_old", 
										     oy_desktopfile_path))
		# Remove old (pre-0.5.5.9) dispwin system loader
		if (os.path.exists(system_desktopfile_path) and
		    (self.exec_cmd("rm", ["-f", system_desktopfile_path], 
								 capture_output=True, low_contrast=False, 
								 skip_scripts=True, silent=False, asroot=True, 
								 title=lang.getstr("autostart_remove_old")) 
			 is not True) and not silent):
			result = Warning(lang.getstr("error.autostart_remove_old", 
									     system_desktopfile_path))
		# Create unified loader
		# Prepend 'z' so our loader hopefully loads after
		# possible nvidia-settings entry (which resets gamma table)
		name = "z-%s-apply-profiles" % appname
		desktopfile_path = os.path.join(autostart_home, 
										name + ".desktop")
		system_desktopfile_path = os.path.join(autostart, name + ".desktop")
		try:
			# Create user loader, even if we later try to 
			# move it to the system-wide location so that atleast 
			# the user loader is present if the move to the system 
			# dir fails
			if not os.path.exists(autostart_home):
				os.makedirs(autostart_home)
			desktopfile = open(desktopfile_path, "w")
			desktopfile.write('[Desktop Entry]\n')
			desktopfile.write('Version=1.0\n')
			desktopfile.write('Encoding=UTF-8\n')
			desktopfile.write('Type=Application\n')
			desktopfile.write('Name=%s\n' % (appname + 
											 ' ICC Profile Loader').encode("UTF-8"))
			desktopfile.write('Comment=%s\n' % 
							  lang.getstr("calibrationloader.description", 
										  lcode="en").encode("UTF-8"))
			if lang.getcode() != "en":
				desktopfile.write(('Comment[%s]=%s\n' % 
								   (lang.getcode(),
									lang.getstr("calibrationloader.description"))).encode("UTF-8"))
			pyw = os.path.normpath(os.path.join(pydir, "..",
												appname +
												"-apply-profiles.pyw"))
			icon = appname + "-apply-profiles"
			if os.path.exists(pyw):
				# Running from source, or 0install/Listaller install
				# Check if this is a 0install implementation, in which
				# case we want to call 0launch with the appropriate
				# command
				if re.match("sha\d+(?:new)?",
							os.path.basename(os.path.dirname(pydir))):
					executable = ("0launch --console --offline "
								  "--command=run-apply-profiles "
								  "http://%s/0install/%s.xml" %
								  (domain.lower(), appname))
				else:
					icon = os.path.join(pydir, "theme", "icons", "256x256",
										appname + "-apply-profiles.png")
					executable = pyw
			else:
				# Regular install
				executable = appname + "-apply-profiles"
			desktopfile.write('Icon=%s\n' % icon.encode("UTF-8"))
			desktopfile.write('Exec=%s\n' % executable.encode("UTF-8"))
			desktopfile.write('Terminal=false\n')
			desktopfile.close()
		except Exception, exception:
			if not silent:
				result = Warning(lang.getstr("error.autostart_creation", 
											 desktopfile_path) + "\n" + 
								 safe_unicode(exception))
		else:
			if getcfg("profile.install_scope") == "l" and autostart:
				# Move system-wide loader
				if (self.exec_cmd("mkdir", 
										 ["-p", autostart], 
										 capture_output=True, 
										 low_contrast=False, 
										 skip_scripts=True, 
										 silent=True, 
										 asroot=True) is not True or 
					self.exec_cmd("mv", 
										 ["-f", 
										  desktopfile_path, 
										  system_desktopfile_path], 
										 capture_output=True, 
										 low_contrast=False, 
										 skip_scripts=True, 
										 silent=True, 
										 asroot=True) is not True) and \
				   not silent:
					result = Warning(lang.getstr("error.autostart_creation", 
												 system_desktopfile_path))
		return result
	
	def instrument_supports_ccss(self, instrument_name=None):
		""" Return whether instrument supports CCSS files or not """
		if not instrument_name:
			instrument_name = self.get_instrument_name()
		return ("i1 DisplayPro, ColorMunki Display" in instrument_name or
				"Spyder4" in instrument_name or "Spyder5" in instrument_name)
	
	def create_ccxx(self, args=None, working_dir=None):
		""" Create CCMX or CCSS """
		if not args:
			args = []
		cmd = get_argyll_util("ccxxmake")
		if not "-I" in args:
			# Display manufacturer & name
			name = self.get_display_name(True)
			if name:
				args.insert(0, "-I")
				args.insert(1, name)
			elif not "-T" in args:
				# Display technology
				args.insert(0, "-T")
				displaytech = ["LCD" if getcfg("measurement_mode") == "l" else "CRT"]
				if (self.get_instrument_features().get("projector_mode") and 
					getcfg("measurement_mode.projector")):
					displaytech.append("Projector")
				args.insert(1, " ".join(displaytech))
		return self.exec_cmd(cmd, ["-v"] + args, capture_output=True, 
							 skip_scripts=True, silent=False,
							 working_dir=working_dir)

	def create_gamut_views(self, profile_path):
		""" Generate gamut views (VRML files) and show progress in current
		progress dialog """
		if getcfg("profile.create_gamut_views"):
			self.log("-" * 80)
			self.log(lang.getstr("gamut.view.create"))
			self.recent.clear()
			self.recent.write(lang.getstr("gamut.view.create"))
			sleep(.75)  # Allow time for progress window to update
			return self.calculate_gamut(profile_path)
		else:
			return None, None

	def create_profile(self, dst_path=None, 
				skip_scripts=False, display_name=None, 
				display_manufacturer=None, tags=None):
		""" Create an ICC profile and process the generated file """
		safe_print(lang.getstr("create_profile"))
		if dst_path is None:
			dst_path = os.path.join(getcfg("profile.save_path"), 
									getcfg("profile.name.expanded"), 
									getcfg("profile.name.expanded") + 
									profile_ext)
		cmd, args = self.prepare_colprof(
			os.path.basename(os.path.splitext(dst_path)[0]), display_name,
			display_manufacturer)
		if not isinstance(cmd, Exception): 
			result = self.exec_cmd(cmd, args, low_contrast=False, 
								   skip_scripts=skip_scripts)
			if (os.path.isfile(args[-1] + ".ti3.backup") and
				os.path.isfile(args[-1] + ".ti3")):
				# Restore backed up TI3
				os.rename(args[-1] + ".ti3", args[-1] + ".bpc.ti3")
				os.rename(args[-1] + ".ti3.backup", args[-1] + ".ti3")
				ti3_file = open(args[-1] + ".ti3", "rb")
				ti3 = ti3_file.read()
				ti3_file.close()
			else:
				ti3 = None
			if os.path.isfile(args[-1] + ".chrm"):
				# Get ChromaticityType tag
				with open(args[-1] + ".chrm", "rb") as blob:
					chrm = ICCP.ChromaticityType(blob.read())
			else:
				chrm = None
		else:
			result = cmd
		bpc_applied = False
		profchanged = False
		if not isinstance(result, Exception) and result:
			profile_path = args[-1] + profile_ext
			try:
				profile = ICCP.ICCProfile(profile_path)
			except (IOError, ICCP.ICCProfileInvalidError), exception:
				result = Error(lang.getstr("profile.invalid") + "\n" + profile_path)
			else:
				# Hires CIECAM02 gamut mapping - perceptual and saturation
				# tables, also colorimetric table for non-RGB profiles
				# Use collink for smoother result.
				# Only for XYZ LUT and if source profile is a simple matrix
				# profile, otherwise CIECAM02 tables will already have been
				# created by colprof
				gamap = ((getcfg("gamap_perceptual") or
						  getcfg("gamap_saturation")) and
						 getcfg("gamap_profile"))
				collink = None
				if ("A2B0" in profile.tags and
					profile.connectionColorSpace == "XYZ" and
					(gamap or profile.colorSpace != "RGB") and
					getcfg("profile.b2a.hires")):
					collink = get_argyll_util("collink")
					if not collink:
						self.log(lang.getstr("argyll.util.not_found",
											 "collink"))
				gamap_profile = None
				if gamap and collink:
					try:
						gamap_profile = ICCP.ICCProfile(getcfg("gamap_profile"))
					except (IOError, ICCProfileInvalidError), exception:
						self.log(exception)
					else:
						if (not "A2B0" in gamap_profile.tags and
							"rXYZ" in gamap_profile.tags and
							"gXYZ" in gamap_profile.tags and
							"bXYZ" in gamap_profile.tags):
							# Simple matrix source profile. Change gamma to 1.0
							gamap_profile.tags.rTRC = ICCP.CurveType()
							gamap_profile.tags.rTRC.append(1.0)
							gamap_profile.tags.gTRC = gamap_profile.tags.rTRC
							gamap_profile.tags.bTRC = gamap_profile.tags.rTRC
							# Write to temp file
							fd, gamap_profile.fileName = tempfile.mkstemp(profile_ext,
																		  dir=self.tempdir)
							stream = os.fdopen(fd, "wb")
							gamap_profile.write(stream)
							stream.close()
							if profile.colorSpace == "RGB":
								# Only table 0 (colorimetric) in display profile.
								# Assign it to table 1 as per ICC spec to prepare
								# for adding table 0 (perceptual) and 2 (saturation)
								profile.tags.B2A1 = profile.tags.B2A0
						else:
							gamap_profile = None
				tables = []
				if gamap_profile or (collink and profile.colorSpace != "RGB"):
					size = getcfg("profile.b2a.hires.size")
					# Make sure to map 'auto' value (-1) to an actual size
					size = {-1: 33}.get(size, size)
					collink_args = ["-v", "-q" + getcfg("profile.quality"),
									"-G", "-r%i" % size]
					for tableno, cfgname in [(0, "gamap_perceptual"),
											 (2, "gamap_saturation")]:
						if getcfg(cfgname):
							tables.append((tableno, getcfg(cfgname + "_intent")))
					if profile.colorSpace != "RGB":
						# Create colorimetric table for non-RGB profile
						tables.append((1, "r"))
						# Get inking rules from colprof extra args
						extra_args = getcfg("extra_args.colprof")
						inking = re.findall(r"-[Kk](?:[zhxr]|p[0-9\.\s]+)|"
											 "-[Ll][0-9\.\s]+", extra_args)
						if inking:
							collink_args.extend(parse_argument_string(" ".join(inking)))
					for tableno, intent in tables:
						# Create device link(s)
						gamap_args = []
						if tableno == 1:
							# Use PhotoPrintRGB as PCS if creating colorimetric
							# table for non-RGB profile.
							# PhotoPrintRGB is a synthetic linear gamma space
							# with the Rec2020 red and blue adapted to D50
							# and a green of x 0.1292 (same as blue x) y 0.8185
							# It almost completely encompasses PhotoGamutRGB
							pcs = get_data_path("ref/PhotoPrintRGB.icc")
							if pcs:
								try:
									gamap_profile = ICCP.ICCProfile(pcs)
								except (IOError, ICCProfileInvalidError), exception:
									self.log(exception)
							else:
								missing = lang.getstr("file.missing",
													  "ref/PhotoPrintRGB.icc")
								if gamap_profile:
									self.log(missing)
								else:
									result = Error(missing)
									break
						else:
							if getcfg("gamap_src_viewcond"):
								gamap_args.append("-c" +
												  getcfg("gamap_src_viewcond"))
							if getcfg("gamap_out_viewcond"):
								gamap_args.append("-d" +
												  getcfg("gamap_out_viewcond"))
						link_profile = tempfile.mktemp(profile_ext,
													   dir=self.tempdir)
						result = self.exec_cmd(collink,
											   collink_args + gamap_args +
											   ["-i" + intent,
												gamap_profile.fileName,
												profile_path,
												link_profile],
											   sessionlogfile=self.sessionlogfile)
						if not isinstance(result, Exception) and result:
							try:
								link_profile = ICCP.ICCProfile(link_profile)
							except (IOError,
									ICCP.ICCProfileInvalidError), exception:
								self.log(exception)
								continue
							table = "B2A%i" % tableno
							profile.tags[table] = link_profile.tags.A2B0
							# Remove temporary link profile
							os.remove(link_profile.fileName)
							# Update B2A matrix with source profile matrix
							matrix = colormath.Matrix3x3([[gamap_profile.tags.rXYZ.X,
														   gamap_profile.tags.gXYZ.X,
														   gamap_profile.tags.bXYZ.X],
														  [gamap_profile.tags.rXYZ.Y,
														   gamap_profile.tags.gXYZ.Y,
														   gamap_profile.tags.bXYZ.Y],
														  [gamap_profile.tags.rXYZ.Z,
														   gamap_profile.tags.gXYZ.Z,
														   gamap_profile.tags.bXYZ.Z]])
							matrix.invert()
							scale = 1 + (32767 / 32768.0)
							matrix *= colormath.Matrix3x3(((scale, 0, 0),
														   (0, scale, 0),
														   (0, 0, scale)))
							profile.tags[table].matrix = matrix
							profchanged = True
						else:
							break
				elif (getcfg("profile.b2a.hires") and
					  getcfg("profile.b2a.hires.smooth") and gamap):
					# Smooth existing B2A tables
					linebuffered_logfiles = []
					if sys.stdout.isatty():
						linebuffered_logfiles.append(safe_print)
					else:
						linebuffered_logfiles.append(log)
					if self.sessionlogfile:
						linebuffered_logfiles.append(self.sessionlogfile)
					logfiles = Files([LineBufferedStream(
										FilteredStream(Files(linebuffered_logfiles),
													   enc, discard="",
													   linesep_in="\n", 
													   triggers=[])), self.recent,
										self.lastmsg])
					smooth_tables = []
					for tableno in (0, 2):
						table = profile.tags.get("B2A%i" % tableno)
						if table in smooth_tables:
							continue
						if self.smooth_B2A(profile, tableno,
										   getcfg("profile.b2a.hires.diagpng") and 2,
										   logfile=logfiles):
							smooth_tables.append(table)
							profchanged = True
			if not isinstance(result, Exception) and result:
				if (gamap_profile and
					os.path.dirname(gamap_profile.fileName) == self.tempdir):
					# Remove temporary source profile
					os.remove(gamap_profile.fileName)
				if profchanged and tables:
					# Make sure we match Argyll colprof i.e. have a complete
					# set of tables
					if profile.colorSpace != "RGB":
						if len(tables) == 1:
							# We only created a colorimetric table, the
							# others are still low quality. Assign 
							# colorimetric table
							profile.tags.B2A0 = profile.tags.B2A1
						if len(tables) < 3:
							# We only created colorimetric and/or perceptual
							# tables, saturation table is still low quality.
							# Assign perceptual table
							profile.tags.B2A2 = profile.tags.B2A0
					if not "A2B1" in profile.tags:
						profile.tags.A2B1 = profile.tags.A2B0
					if not "A2B2" in profile.tags:
						profile.tags.A2B2 = profile.tags.A2B0
					if not "B2A2" in profile.tags:
						profile.tags.B2A2 = profile.tags.B2A0
				# A2B processing
				process_A2B = ("A2B0" in profile.tags and
							   profile.colorSpace == "RGB" and
							   profile.connectionColorSpace in ("XYZ", "Lab") and
							   (getcfg("profile.b2a.hires") or
								getcfg("profile.quality.b2a") in ("l", "n")))
				if ("rTRC" in profile.tags and
					"gTRC" in profile.tags and
					"bTRC" in profile.tags and
					isinstance(profile.tags.rTRC, ICCP.CurveType) and
					isinstance(profile.tags.gTRC, ICCP.CurveType) and
					isinstance(profile.tags.bTRC, ICCP.CurveType) and
					((getcfg("profile.black_point_compensation") and
					  not "A2B0" in profile.tags) or
					 (process_A2B and getcfg("profile.b2a.hires"))) and
					len(profile.tags.rTRC) > 1 and
					len(profile.tags.gTRC) > 1 and
					len(profile.tags.bTRC) > 1):
					for component in ("r", "g", "b"):
						self.log("%s: Applying black point compensation to "
								 "%sTRC" % (appname, component))
						profile.tags["%sTRC" % component].apply_bpc()
					bpc_applied = True
					profchanged = True
				if process_A2B:
					bpc_applied = False
					if getcfg("profile.black_point_compensation"):
						if "A2B1" in profile.tags:
							table = "A2B1"
						else:
							table = "A2B0"
						if isinstance(profile.tags[table], ICCP.LUT16Type):
							self.log("%s: Applying black point "
									 "compensation to %s table" % (appname,
																   table))
							profile.tags[table].apply_bpc()
							bpc_applied = True
							profchanged = True
						else:
							self.log("%s: Can't apply black point "
									 "compensation to non-LUT16Type %s "
									 "table" % (appname, table))
					if getcfg("profile.b2a.hires"):
						if profchanged:
							# We need to write the changed profile before
							# enhancing B2A resolution!
							try:
								profile.write()
							except Exception, exception:
								return exception
						result = self.update_profile_B2A(profile)
						if not isinstance(result, Exception) and result:
							profchanged = True
			if profchanged and not isinstance(result, Exception) and result:
				if "bkpt" in profile.tags and bpc_applied:
					# We need to update the blackpoint tag
					try:
						odata = self.xicclu(profile, (0, 0, 0), intent="a",
											pcs="x")
						if len(odata) != 1 or len(odata[0]) != 3:
							raise ValueError("Blackpoint is invalid: %s" %
											 odata)
					except Exception, exception:
						self.log(exception)
					else:
						(profile.tags.bkpt.X,
						 profile.tags.bkpt.Y,
						 profile.tags.bkpt.Z) = odata[0]
				# We need to write the changed profile
				try:
					profile.write()
				except Exception, exception:
					return exception
				if bpc_applied:
					# We need to re-do profile self check
					self.exec_cmd(get_argyll_util("profcheck"),
								  [args[-1] + ".ti3", args[-1] + profile_ext],
								  capture_output=True, skip_scripts=True)
		# Get profile max and avg err to be later added to metadata
		# Argyll outputs the following:
		# Profile check complete, peak err = x.xxxxxx, avg err = x.xxxxxx, RMS = x.xxxxxx
		peak = None
		avg = None
		rms = None
		for line in self.output:
			if line.startswith("Profile check complete"):
				peak = re.search("(?:peak err|max\.) = (\d+(?:\.\d+))", line)
				avg = re.search("avg(?: err|\.) = (\d+(?:\.\d+))", line)
				rms = re.search("RMS = (\d+(?:\.\d+))", line)
				if peak:
					peak = peak.groups()[0]
				if avg:
					avg = avg.groups()[0]
				if rms:
					rms = rms.groups()[0]
				break
		if not isinstance(result, Exception) and result:
			(gamut_volume,
			 gamut_coverage) = self.create_gamut_views(profile_path)
		self.log("-" * 80)
		if not isinstance(result, Exception) and result:
			result = self.update_profile(profile, ti3, chrm,
										 tags, avg, peak, rms, gamut_volume,
										 gamut_coverage,
										 quality=getcfg("profile.quality"))
		result2 = self.wrapup(not isinstance(result, UnloggedInfo) and result,
							  dst_path=dst_path)
		if isinstance(result2, Exception):
			if isinstance(result, Exception):
				result = Error(safe_unicode(result) + "\n\n" +
							   safe_unicode(result2))
			else:
				result = result2
		elif not isinstance(result, Exception) and result:
			setcfg("last_cal_or_icc_path", dst_path)
			setcfg("last_icc_path", dst_path)
		return result
	
	def update_profile(self, profile, ti3=None, chrm=None, tags=None,
					   avg=None, peak=None, rms=None, gamut_volume=None,
					   gamut_coverage=None, quality=None):
		""" Update profile tags and metadata """
		if isinstance(profile, basestring):
			profile_path = profile
			try:
				profile = ICCP.ICCProfile(profile_path)
			except (IOError, ICCP.ICCProfileInvalidError), exception:
				return Error(lang.getstr("profile.invalid") + "\n" + profile_path)
		else:
			profile_path = profile.fileName
		if (profile.profileClass == "mntr" and profile.colorSpace == "RGB" and
			not (self.tempdir and profile_path.startswith(self.tempdir))):
			setcfg("last_cal_or_icc_path", profile_path)
			setcfg("last_icc_path", profile_path)
		if ti3:
			# Embed original TI3
			profile.tags.targ = profile.tags.DevD = profile.tags.CIED = ICCP.TextType(
											"text\0\0\0\0" + ti3 + "\0", 
											"targ")
		if chrm:
			# Add ChromaticityType tag
			profile.tags.chrm = chrm
		# Fixup desc tags - ASCII needs to be 7-bit
		# also add Unicode strings if different from ASCII
		if "desc" in profile.tags and isinstance(profile.tags.desc, 
												 ICCP.TextDescriptionType):
			profile.setDescription(profile.getDescription())
		if "dmdd" in profile.tags and isinstance(profile.tags.dmdd, 
												 ICCP.TextDescriptionType):
			profile.setDeviceModelDescription(
				profile.getDeviceModelDescription())
		if "dmnd" in profile.tags and isinstance(profile.tags.dmnd, 
												 ICCP.TextDescriptionType):
			profile.setDeviceManufacturerDescription(
				profile.getDeviceManufacturerDescription())
		if tags and tags is not True:
			# Add custom tags
			for tagname, tag in tags.iteritems():
				if tagname == "mmod":
					profile.device["manufacturer"] = "\0\0" + tag["manufacturer"][1] + tag["manufacturer"][0]
					profile.device["model"] = "\0\0" + tag["model"][0] + tag["model"][1]
				profile.tags[tagname] = tag
		elif tags is True:
			edid = self.get_display_edid()
			if edid:
				profile.device["manufacturer"] = "\0\0" + edid["edid"][9] + edid["edid"][8]
				profile.device["model"] = "\0\0" + edid["edid"][11] + edid["edid"][10]
				# Add Apple-specific 'mmod' tag (TODO: need full spec)
				mmod = ("mmod" + ("\x00" * 6) + edid["edid"][8:10] +
						("\x00" * 2) + edid["edid"][11] + edid["edid"][10] +
						("\x00" * 4) + ("\x00" * 20))
				profile.tags.mmod = ICCP.ICCProfileTag(mmod, "mmod")
				# Add new meta information based on EDID
				profile.set_edid_metadata(edid)
			elif not "meta" in profile.tags:
				# Make sure meta tag exists
				profile.tags.meta = ICCP.DictType()
			profile.tags.meta.update({"CMF_product": appname,
									  "CMF_binary": appname,
									  "CMF_version": version})
			# Set license
			profile.tags.meta["License"] = getcfg("profile.license")
			# Set profile quality
			quality = {"v": "very low",
					   "l": "low",
					   "m": "medium",
					   "h": "high"}.get(quality)
			if quality:
				profile.tags.meta["Quality"] = quality
			# Set OPENICC_automatic_generated to "0"
			profile.tags.meta["OPENICC_automatic_generated"] = "0"
			# Set GCM DATA_source to "calib"
			profile.tags.meta["DATA_source"] = "calib"
			# Add instrument
			profile.tags.meta["MEASUREMENT_device"] = self.get_instrument_name().lower()
			spec_prefixes = "CMF_,DATA_,MEASUREMENT_,OPENICC_"
			# Add screen brightness if applicable
			if sys.platform not in ("darwin", "win32") and dbus_session:
				try:
					proxy = dbus_session.get_object("org.gnome.SettingsDaemon",
													"/org/gnome/SettingsDaemon/Power")
					iface = dbus.Interface(proxy,
										   dbus_interface="org.gnome.SettingsDaemon.Power.Screen")
					brightness = iface.GetPercentage()
				except dbus.exceptions.DBusException:
					pass
				else:
					profile.tags.meta["SCREEN_brightness"] = str(brightness)
					spec_prefixes += ",SCREEN_"
			# Set device ID
			device_id = self.get_device_id(quirk=True)
			if device_id:
				profile.tags.meta["MAPPING_device_id"] = device_id
				spec_prefixes += ",MAPPING_"
			prefixes = (profile.tags.meta.getvalue("prefix", "", None) or spec_prefixes).split(",")
			for prefix in spec_prefixes.split(","):
				if not prefix in prefixes:
					prefixes.append(prefix)
			profile.tags.meta["prefix"] = ",".join(prefixes)
		if (avg, peak, rms) != (None, ) * 3:
			# Make sure meta tag exists
			if not "meta" in profile.tags:
				profile.tags.meta = ICCP.DictType()
			# Update meta prefix
			prefixes = (profile.tags.meta.getvalue("prefix", "", None) or "ACCURACY_").split(",")
			if not "ACCURACY_" in prefixes:
				prefixes.append("ACCURACY_")
				profile.tags.meta["prefix"] = ",".join(prefixes)
			# Add error info
			if avg is not None:
				profile.tags.meta["ACCURACY_dE76_avg"] = avg
			if peak is not None:
				profile.tags.meta["ACCURACY_dE76_max"] = peak
			if rms is not None:
				profile.tags.meta["ACCURACY_dE76_rms"] = rms
		profile.set_gamut_metadata(gamut_volume, gamut_coverage)
		# Set default rendering intent
		if ("B2A0" in profile.tags and ("B2A1" in profile.tags or
										"B2A2" in profile.tags)):
			profile.intent = {"p": 0,
							  "r": 1,
							  "s": 2,
							  "a": 3}[getcfg("gamap_default_intent")]
		# Calculate profile ID
		profile.calculateID()
		try:
			profile.write()
		except Exception, exception:
			return exception
		return True
	
	def update_profile_B2A(self, profile):
		# Use reverse A2B interpolation to generate B2A table
		clutres = getcfg("profile.b2a.hires.size")
		linebuffered_logfiles = []
		if sys.stdout.isatty():
			linebuffered_logfiles.append(safe_print)
		else:
			linebuffered_logfiles.append(log)
		if self.sessionlogfile:
			linebuffered_logfiles.append(self.sessionlogfile)
		logfiles = Files([LineBufferedStream(
							FilteredStream(Files(linebuffered_logfiles),
										   enc, discard="",
										   linesep_in="\n", 
										   triggers=[])), self.recent,
							self.lastmsg])
		tables = [1]
		self.log("-" * 80)
		# Add perceptual tables if not present
		if "A2B0" in profile.tags and not "A2B1" in profile.tags:
			if not isinstance(profile.tags.A2B0, ICCP.LUT16Type):
				self.log("%s: Can't process non-LUT16Type A2B0 table" % appname)
				return []
			try:
				# Copy A2B0
				logfiles.write("Generating A2B1 by copying A2B0\n")
				profile.tags.A2B1 = profile.tags.A2B0
				if "B2A0" in profile.tags:
					# Copy B2A0
					B2A0 = profile.tags.B2A0
					profile.tags.B2A1 = B2A1 = ICCP.LUT16Type()
					B2A1.matrix = []
					for row in B2A0.matrix:
						B2A1.matrix.append(list(row))
					B2A1.input = []
					B2A1.output = []
					for table in ("input", "output"):
						for channel in getattr(B2A0, table):
							getattr(B2A1, table).append(list(channel))
					B2A1.clut = []
					for block in B2A0.clut:
						B2A1.clut.append([])
						for row in block:
							B2A1.clut[-1].append(list(row))
			except Exception, exception:
				return exception
		if not "A2B2" in profile.tags:
			# Argyll always creates a complete set of A2B / B2A tables if
			# colprof -s (perceptual) or -S (perceptual and saturation) is used,
			# so we can assume that if A2B2 is not present then it is safe to
			# re-generate B2A0 because it was not created by Argyll CMS.
			tables.append(0)
		# Invert A2B tables if present. Always invert colorimetric A2B table.
		results = []
		bpc_applied = False
		filename = profile.fileName
		for tableno in tables:
			if "A2B%i" % tableno in profile.tags:
				if ("B2A%i" % tableno in profile.tags and
					profile.tags["B2A%i" % tableno] in results):
					continue
				if not isinstance(profile.tags["A2B%i" % tableno],
								  ICCP.LUT16Type):
					self.log("%s: Can't process non-LUT16Type A2B%i table" %
							 (appname, tableno))
					continue
				# Check if we want to apply BPC
				bpc = tableno != 1
				if (bpc and
					profile.tags["A2B%i" % tableno].clut[0][0] != [0, 0, 0]):
					# Need to apply BPC. Use temporary copy of A2B.
					otables = {}
					table = ICCP.LUT16Type(profile=profile)
					for i in xrange(3):
						if "A2B%i" % i in profile.tags:
							otables[i] = profile.tags["A2B%i" % i]
							profile.tags["A2B%i" % i] = table
					otable = otables[tableno]
					# Copy table
					table.matrix = []
					for row in otable.matrix:
						table.matrix.append(list(row))
					table.input = []
					table.output = []
					for curves in ("input", "output"):
						for channel in getattr(otable, curves):
							getattr(table, curves).append(list(channel))
					table.clut = []
					for block in otable.clut:
						table.clut.append([])
						for row in block:
							table.clut[-1].append(list(row))
					logfiles.write("Applying BPC to temporary A2B tables...\n")
					table.apply_bpc()
					bpc_applied = True
				elif bpc:
					# BPC not needed, copy existing B2A
					profile.tags["B2A%i" % tableno] = results[0]
					return results
				if not filename or not os.path.isfile(filename) or bpc_applied:
					# Write profile to temp dir
					tempdir = self.create_tempdir()
					if isinstance(tempdir, Exception):
						return tempdir
					fd, profile.fileName = tempfile.mkstemp(profile_ext,
															dir=tempdir)
					stream = os.fdopen(fd, "wb")
					profile.write(stream)
					stream.close()
					temp = True
				else:
					temp = False
				# Invert A2B
				try:
					result = self.generate_B2A_from_inverse_table(profile,
																  clutres,
																  "A2B",
																  tableno,
																  bpc,
																  logfiles,
																  filename)
				except (Error, Info), exception:
					return exception
				except Exception, exception:
					self.log(traceback.format_exc())
					return exception
				else:
					if result:
						results.append(profile.tags["B2A%i" % tableno])
					else:
						return False
				finally:
					if bpc_applied:
						logfiles.write("Restoring original A2B tables...\n")
						for i, otable in otables.iteritems():
							profile.tags["A2B%i" % i] = otable
					if temp:
						os.remove(profile.fileName)
						if self.tempdir and not os.listdir(self.tempdir):
							self.wrapup(False)
						profile.fileName = filename
		return results
	
	def isalive(self, subprocess=None):
		""" Check if subprocess is still alive """
		if not subprocess:
			subprocess = getattr(self, "subprocess", None)
		return (subprocess and
				((hasattr(subprocess, "poll") and 
				  subprocess.poll() is None) or
				 (hasattr(subprocess, "isalive") and 
				  subprocess.isalive())))

	def is_working(self):
		""" Check if any Worker instance is busy. Return True or False. """
		for worker in workers:
			if not getattr(worker, "finished", True):
				return True
		return False
	
	def log(self, *args, **kwargs):
		""" Log to global logfile and session logfile (if any) """
		msg = " ".join(safe_basestring(arg) for arg in args)
		fn = kwargs.get("fn", safe_print)
		fn(msg)
		if self.sessionlogfile:
			self.sessionlogfile.write(msg + "\n")

	def start_measurement(self, consumer, apply_calibration=True,
						  progress_msg="", resume=False, continue_next=False):
		""" Start a measurement and use a progress dialog for progress
		information """
		self.start(consumer, self.measure, 
				   wkwargs={"apply_calibration": apply_calibration},
				   progress_msg=progress_msg, resume=resume, 
				   continue_next=continue_next, pauseable=True)
	
	def start_calibration(self, consumer, remove=False, progress_msg="",
						  resume=False, continue_next=False):
		""" Start a calibration and use a progress dialog for progress
		information """
		self.start(consumer, self.calibrate, wkwargs={"remove": remove},
				   progress_msg=progress_msg, resume=resume,
				   continue_next=continue_next, interactive_frame="adjust",
				   pauseable=True)

	def madtpg_connect(self):
		if not hasattr(self, "madtpg"):
			if sys.platform == "win32" and getcfg("madtpg.native"):
				# Using native implementation (madHcNet32.dll)
				self.madtpg = madvr.MadTPG()
			else:
				# Using madVR net-protocol pure python implementation
				self.madtpg = madvr.MadTPG_Net()
				self.madtpg.debug = verbose
		return self.madtpg.connect(method2=madvr.CM_StartLocalInstance)

	def madtpg_disconnect(self, restore_settings=True):
		""" Restore madVR settings and disconnect """
		if restore_settings:
			restore_fullscreen = getattr(self, "madtpg_previous_fullscreen", None)
			restore_osd = getattr(self, "madtpg_osd", None) is False
			if restore_fullscreen or restore_osd:
				check = self.madtpg.get_version()
				if not check:
					check = self.madtpg_connect()
				if check:
					if restore_fullscreen:
						# Restore fullscreen
						if self.madtpg.set_use_fullscreen_button(True):
							self.log("Restored madTPG 'Fullscreen' button state")
							self.madtpg_previous_fullscreen = None
						else:
							self.log("Warning - could not restore madTPG "
									 "'Fullscreen' button state")
					if restore_osd:
						# Restore disable OSD
						if self.madtpg.set_disable_osd_button(True):
							self.log("Restored madTPG 'Disable OSD' button state")
							self.madtpg_osd = None
						else:
							self.log("Warning - could not restore madTPG 'Disable "
									 "OSD' button state")
				else:
					self.log("Warning - could not re-connect to madTPG to restore"
							 "'Fullscreen'/'Disable OSD' button states")
		self.madtpg.disconnect()
	
	def measure(self, apply_calibration=True):
		""" Measure the configured testchart """
		precond_ti3 = None
		auto = getcfg("testchart.auto_optimize") or 7
		if getcfg("testchart.file") == "auto" and auto > 4:
			# Testchart auto-optimization
			# Create optimized testchart on-the-fly. To do this, create a
			# simple profile for preconditioning
			if config.get_display_name() == "Untethered":
				return Error(lang.getstr("testchart.auto_optimize.untethered.unsupported"))
			# Use small LUT testchart
			setcfg("testchart.file",
				   get_data_path("ti1/d3-e4-s13-g37-m4-b4-f0.ti1"))
			cmd, args = self.prepare_dispread(apply_calibration)
			setcfg("testchart.file", "auto")
			if not isinstance(cmd, Exception):
				# Measure testchart
				result = self.exec_cmd(cmd, args)
				if not isinstance(result, Exception) and result:
					# Create preconditioning profile
					self.pauseable = False
					basename = args[-1]
					precond_ti3 = CGATS.CGATS(basename + ".ti3")
					cmd, args = get_argyll_util("colprof"), ["-v", "-qm", "-ax",
															 "-bn", basename]
					result = self.exec_cmd(cmd, args)
					if (not isinstance(result, Exception) and result and
						getcfg("testchart.auto_optimize.fix_zero_blackpoint")):
						# Hmm. Some users have reported targen hanging, and I
						# couldn't reproduce it unless I used MinGW (32-bit) to
						# compile Argyll 1.7b (2015-03-06) development code
						# and a preconditioning profile with zero blackpoint.
						self.log("Pre-conditioning zero black point fix enabled")
						try:
							profile = ICCP.ICCProfile(basename + profile_ext)
						except Exception, exception:
							result = exception
						else:
							profchanged = False
							if isinstance(profile.tags.get("A2B0"),
										  ICCP.LUT16Type):
								# Make sure blackpoint isn't zero
								if profile.tags.A2B0.clut[0][0] == [0, 0, 0]:
									profile.tags.A2B0.apply_bpc((1.0 / 65535, ) * 3)
									profchanged = True
							elif (isinstance(profile.tags.get("rTRC"),
											 ICCP.CurveType) and
								  isinstance(profile.tags.get("gTRC"),
											 ICCP.CurveType) and
								  isinstance(profile.tags.get("bTRC"),
											 ICCP.CurveType)):
								# Make sure blackpoint isn't zero
								for channel in "rgb":
									if profile.tags[channel + "TRC"][0] == 0:
										profile.tags[channel + "TRC"].apply_bpc(1.0 / 65535)
										profchanged = True
							if profchanged:
								try:
									profile.write()
								except Exception, exception:
									result = exception
								self.log("Pre-conditioning zero black point fix applied")
					if not isinstance(result, Exception) and result:
						# Create optimized testchart
						if getcfg("use_fancy_progress"):
							# Fade out animation/sound
							self.cmdname = get_argyll_utilname("targen")
							# Allow time for fade out
							sleep(4)
						s = min(auto, 11) * 4 - 3
						g = s * 3 - 2
						f = get_total_patches(4, 4, s, g, auto, auto, 0)
						cmd, args = (get_argyll_util("targen"),
									 ["-v", "-d3", "-e4", "-s%i" % s,
									  "-g%i" % g, "-m0", "-f%i" % f, "-A1.0"])
						if self.argyll_version >= [1, 1]:
							args.append("-G")
						if self.argyll_version >= [1, 3, 3]:
							args.append("-N0.5")
						if self.argyll_version >= [1, 6]:
							args.extend(["-B4", "-b0"])
						if self.argyll_version >= [1, 6, 2]:
							args.append("-V1.6")
						args.extend(["-c", basename + profile_ext, basename])
						result = self.exec_cmd(cmd, args)
						self.pauseable = True
			else:
				result = cmd
		else:
			result = True
			if getcfg("testchart.file") == "auto" and auto < 5:
				# Use pre-baked testchart
				if auto == 3:
					testchart = "ti1/d3-e4-s0-g25-m3-b3-f0-crossover.ti1"
				else:
					testchart = "ti1/d3-e4-s0-g49-m3-b3-f0-crossover.ti1"
				testchart_path = get_data_path(testchart)
				if testchart_path:
					setcfg("testchart.file", testchart_path)
				else:
					result = Error(lang.getstr("not_found", testchart))
		if not isinstance(result, Exception) and result:
			cmd, args = self.prepare_dispread(apply_calibration)
		else:
			cmd = result
		if not isinstance(cmd, Exception) and cmd:
			if config.get_display_name() == "Untethered":
				cmd, args2 = get_argyll_util("spotread"), ["-v", "-e"]
				if getcfg("extra_args.spotread").strip():
					args2 += parse_argument_string(getcfg("extra_args.spotread"))
				result = self.add_measurement_features(args2, False,
													   allow_nondefault_observer=is_ccxx_testchart())
				if isinstance(result, Exception):
					return result
			else:
				args2 = args
			result = self.exec_cmd(cmd, args2)
			if not isinstance(result, Exception) and result:
				self.update_display_name_manufacturer(args[-1] + ".ti3")
				ti3 = args[-1] + ".ti3"
				if precond_ti3:
					# Add patches from preconditioning measurements
					ti3 = CGATS.CGATS(ti3)
					precond_data = precond_ti3.queryv1("DATA")
					data = ti3.queryv1("DATA")
					data_format = ti3.queryv1("DATA_FORMAT")
					# Get only RGB data
					data.parent.DATA_FORMAT = CGATS.CGATS()
					data.parent.DATA_FORMAT.key = "DATA_FORMAT"
					data.parent.DATA_FORMAT.parent = data
					data.parent.DATA_FORMAT.root = data.root
					data.parent.DATA_FORMAT.type = "DATA_FORMAT"
					for i, label in enumerate(("RGB_R", "RGB_G", "RGB_B")):
						data.parent.DATA_FORMAT[i] = label
					precond_data.parent.DATA_FORMAT = data.parent.DATA_FORMAT
					rgbdata = str(data)
					# Restore DATA_FORMAT
					data.parent.DATA_FORMAT = data_format
					# Collect all preconditioning point datasets not in data
					precond_data.vmaxlen = data.vmaxlen
					precond_datasets = []
					for i, dataset in precond_data.iteritems():
						if not str(dataset) in rgbdata:
							precond_datasets.append(dataset)
					if precond_datasets:
						# Insert preconditioned point datasets after first patch
						self.log("%s: Adding %i fixed points" %
								   (appname, len(precond_datasets)))
						data.moveby1(1, len(precond_datasets))
						for i, dataset in enumerate(precond_datasets):
							dataset.key = i + 1
							dataset.parent = data
							dataset.root = data.root
							data[dataset.key] = dataset
				options = {"OBSERVER": get_cfg_option_from_args("observer", "-Q",
																args[:-1])}
				ti3 = add_keywords_to_cgats(ti3, options)
				ti3.write()
		else:
			result = cmd
		result2 = self.wrapup(not isinstance(result, UnloggedInfo) and result,
							  isinstance(result, Exception) or not result)
		if isinstance(result2, Exception):
			if isinstance(result, Exception):
				result = Error(safe_unicode(result) + "\n\n" +
							   safe_unicode(result2))
			else:
				result = result2
		return result
	
	def parse(self, txt):
		if not txt:
			return
		self.logger.info("%r" % txt)
		self.check_instrument_calibration(txt)
		self.check_instrument_place_on_screen(txt)
		self.check_instrument_sensor_position(txt)
		self.check_retry_measurement(txt)
		self.check_is_ambient_measuring(txt)
		self.check_spotread_result(txt)
		if self.cmdname in (get_argyll_utilname("dispcal"),
							get_argyll_utilname("dispread"),
							get_argyll_utilname("spotread")):
			if (self.cmdname == get_argyll_utilname("dispcal") and
				", repeat" in txt.lower()):
				self.repeat = True
			elif ", ok" in txt.lower():
				self.repeat = False
			if (re.search(r"Patch [2-9]\d* of ", txt, re.I) or
				(re.search(r"Patch \d+ of |The instrument can be removed from "
						   "the screen", txt, re.I) and self.patch_count > 1) or
				("Result is XYZ:" in txt and
				 not isinstance(self.progress_wnd, UntetheredFrame))):
				if self.cmdname == get_argyll_utilname("dispcal") and self.repeat:
					if (getcfg("measurement.play_sound") and
						hasattr(self.progress_wnd, "sound_on_off_btn")):
						self.measurement_sound.safe_play()
				else:
					if (getcfg("measurement.play_sound") and
						(hasattr(self.progress_wnd, "sound_on_off_btn")
						 or isinstance(self.progress_wnd, DisplayUniformityFrame))):
						self.commit_sound.safe_play()
					if hasattr(self.progress_wnd, "animbmp"):
						self.progress_wnd.animbmp.frame = 0

	def setup_patterngenerator(self, logfile=None):
		if config.get_display_name() == "Prisma":
			patterngenerator = PrismaPatternGeneratorClient
			self.patterngenerator = patterngenerator(
				host=getcfg("patterngenerator.prisma.host"),
				port=getcfg("patterngenerator.prisma.port"),
				use_video_levels=getcfg("patterngenerator.prisma.use_video_levels"),
				logfile=logfile)
		else:
			# Resolve
			if getcfg("patterngenerator.resolve") == "LS":
				patterngenerator = ResolveLSPatternGeneratorServer
			else:
				patterngenerator = ResolveCMPatternGeneratorServer
			self.patterngenerator = patterngenerator(
				port=getcfg("patterngenerator.resolve.port"),
				use_video_levels=getcfg("patterngenerator.resolve.use_video_levels"),
				logfile=logfile)

	@Property
	def patterngenerator():
		def fget(self):
			pgname = config.get_display_name()
			return self._patterngenerators.get(pgname)

		def fset(self, patterngenerator):
			pgname = config.get_display_name()
			self._patterngenerators[pgname] = patterngenerator

		return locals()

	def patterngenerator_send(self, rgb, raise_exceptions=False):
		""" Send RGB color to pattern generator """
		if getattr(self, "abort_requested", False):
			return
		x, y, w, h, size = get_pattern_geometry()
		size = min(sum((w, h)) / 2.0, 1.0)
		if getcfg("measure.darken_background") or size == 1.0:
			bgrgb = (0, 0, 0)
		else:
			# Constant APL
			rgbl = sum([v * size for v in rgb])
			bgrgb = [(1.0 - v * size) * (1.0 - size) for v in rgb]
			bgrgbl = sum(bgrgb)
			desired_apl = getcfg("patterngenerator.apl")
			apl = desired_apl * 3
			bgrgb = [max(apl - max(rgbl - apl, 0.0), 0.0) / bgrgbl * v for v in bgrgb]
		self.log("%s: Sending RGB %.3f %.3f %.3f, background RGB %.3f %.3f %.3f, "
				 "x %.4f, y %.4f, w %.4f, h %.4f" %
				 ((appname, ) + tuple(rgb) + tuple(bgrgb) + (x, y, w, h)))
		try:
			self.patterngenerator.send(rgb, bgrgb, x=x, y=y, w=w, h=h)
		except Exception, exception:
			if raise_exceptions:
				raise
			else:
				self.exec_cmd_returnvalue = exception
				self.abort_subprocess()
		else:
			self.patterngenerator_sent_count += 1
			self.log("%s: Patterngenerator sent count: %i" %
					 (appname, self.patterngenerator_sent_count))

	@Property
	def pauseable():
		def fget(self):
			return self._pauseable

		def fset(self, pauseable):
			self._pauseable = pauseable
			self.pauseable_now = False

		return locals()
	
	def pause_continue(self):
		if not self.pauseable or not self.pauseable_now:
			return
		if (getattr(self.progress_wnd, "paused", False) and
			  not getattr(self, "paused", False)):
			self.paused = True
			self.safe_send("\x1b")
		elif (not getattr(self.progress_wnd, "paused", False) and
			  getattr(self, "paused", False)):
			self.paused = False
			self.safe_send(" ")

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
			return Error(lang.getstr("file_notfile", 
									 inoutfile + ".ti3")), None
		#
		cmd = get_argyll_util("colprof")
		args = []
		args.append("-v") # verbose
		args.append("-q" + getcfg("profile.quality"))
		args.append("-a" + getcfg("profile.type"))
		gamap_args = args
		if getcfg("profile.type") in ["l", "x", "X"]:
			if getcfg("gamap_saturation"):
				gamap = "S"
			elif getcfg("gamap_perceptual"):
				gamap = "s"
			else:
				gamap = None
			gamap_profile = None
			if gamap and getcfg("gamap_profile"):
				# CIECAM02 gamut mapping - perceptual and saturation tables
				# Only for L*a*b* LUT or if source profile is not a simple matrix
				# profile, otherwise create hires CIECAM02 tables with collink
				try:
					gamap_profile = ICCP.ICCProfile(getcfg("gamap_profile"))
				except ICCProfileInvalidError, exception:
					self.log(exception)
					return Error(lang.getstr("profile.invalid") + "\n" +
								 getcfg("gamap_profile"))
				except IOError, exception:
					return exception
				if (getcfg("profile.type") != "l" and
					getcfg("profile.b2a.hires") and
					not "A2B0" in gamap_profile.tags and
					"rXYZ" in gamap_profile.tags and
					"gXYZ" in gamap_profile.tags and
					"bXYZ" in gamap_profile.tags):
					# Make a copy so we can store options without adding them
					# to actual colprof arguments
					gamap_args = []
					gamap_profile = None
				gamap_args.append("-" + gamap)
				gamap_args.append(getcfg("gamap_profile"))
				gamap_args.append("-t" + getcfg("gamap_perceptual_intent"))
				if gamap == "S":
					gamap_args.append("-T" + getcfg("gamap_saturation_intent"))
				if getcfg("gamap_src_viewcond"):
					gamap_args.append("-c" + getcfg("gamap_src_viewcond"))
				if getcfg("gamap_out_viewcond"):
					gamap_args.append("-d" + getcfg("gamap_out_viewcond"))
			b2a_q = getcfg("profile.quality.b2a")
			if (getcfg("profile.b2a.hires") and
				getcfg("profile.type") in ("l", "x", "X") and
				not (gamap and gamap_profile)):
				# Disable B2A creation in colprof, B2A is handled
				# by A2B inversion code
				b2a_q = "n"
			if b2a_q and b2a_q != getcfg("profile.quality"):
				args.append("-b" + b2a_q)
		args.append("-C")
		args.append(getcfg("copyright").encode("ASCII", "asciize"))
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
		if gamap_args is not args:
			self.options_colprof.extend(gamap_args)
		args.append("-D")
		args.append(profile_name)
		args.append(inoutfile)
		# Add dispcal and colprof arguments to ti3
		ti3 = add_options_to_ti3(inoutfile + ".ti3", options_dispcal, 
								 self.options_colprof)
		if ti3:
			color_rep = (ti3.queryv1("COLOR_REP") or "").split("_")
			# Prepare ChromaticityType tag
			colorants = ti3.get_colorants()
			if colorants and not None in colorants:
				chrm = ICCP.ChromaticityType()
				chrm.type = 0
				for colorant in colorants:
					if color_rep[1] == "LAB":
						XYZ = colormath.Lab2XYZ(colorant["LAB_L"],
												colorant["LAB_A"],
												colorant["LAB_B"])
					else:
						XYZ = (colorant["XYZ_X"], colorant["XYZ_Y"],
							   colorant["XYZ_Z"])
					chrm.channels.append(colormath.XYZ2xyY(*XYZ)[:-1])
				with open(inoutfile + ".chrm", "wb") as blob:
					blob.write(chrm.tagData)
			# Black point compensation
			ti3[0].add_keyword("USE_BLACK_POINT_COMPENSATION",
							   "YES" if getcfg("profile.black_point_compensation")
							   else "NO")
			# Hires B2A with optional smoothing
			ti3[0].add_keyword("HIRES_B2A",
							   "YES" if getcfg("profile.b2a.hires")
							   else "NO")
			ti3[0].add_keyword("HIRES_B2A_SIZE",
							   getcfg("profile.b2a.hires.size"))
			ti3[0].add_keyword("SMOOTH_B2A",
							   "YES" if getcfg("profile.b2a.hires.smooth")
							   else "NO")
			# Display update delay
			if getcfg("measure.override_min_display_update_delay_ms"):
				ti3[0].add_keyword("MIN_DISPLAY_UPDATE_DELAY_MS",
								   getcfg("measure.min_display_update_delay_ms"))
			# Display settle time multiplier
			if getcfg("measure.override_display_settle_time_mult"):
				ti3[0].add_keyword("DISPLAY_SETTLE_TIME_MULT",
								   getcfg("measure.display_settle_time_mult"))
			# Remove AUTO_OPTIMIZE
			if ti3[0].queryv1("AUTO_OPTIMIZE"):
				ti3[0].remove_keyword("AUTO_OPTIMIZE")
			# Add 3D LUT options if set, else remove them
			for keyword, cfgname in {"3DLUT_SOURCE_PROFILE":
									 "3dlut.input.profile",
									 "3DLUT_TRC":
									 "3dlut.trc",
									 "3DLUT_HDR_PEAK_LUMINANCE":
									 "3dlut.hdr_peak_luminance",
									 "3DLUT_GAMMA":
									 "3dlut.trc_gamma",
									 "3DLUT_DEGREE_OF_BLACK_OUTPUT_OFFSET":
									 "3dlut.trc_output_offset",
									 "3DLUT_INPUT_ENCODING":
									 "3dlut.encoding.input",
									 "3DLUT_OUTPUT_ENCODING":
									 "3dlut.encoding.output",
									 "3DLUT_GAMUT_MAPPING_MODE":
									 "3dlut.gamap.use_b2a",
									 "3DLUT_RENDERING_INTENT":
									 "3dlut.rendering_intent",
									 "3DLUT_FORMAT":
									 "3dlut.format",
									 "3DLUT_SIZE":
									 "3dlut.size",
									 "3DLUT_INPUT_BITDEPTH":
									 "3dlut.bitdepth.input",
									 "3DLUT_OUTPUT_BITDEPTH":
									 "3dlut.bitdepth.output",
									 "3DLUT_APPLY_CAL":
									 "3dlut.output.profile.apply_cal"}.iteritems():
				if getcfg("3dlut.create"):
					value = getcfg(cfgname)
					if cfgname == "3dlut.gamap.use_b2a":
						if value:
							value = "g"
						else:
							value = "G"
					elif cfgname == "3dlut.trc_gamma":
						if getcfg("3dlut.trc_gamma_type") == "B":
							value = -value
					ti3[0].add_keyword(keyword, safe_str(value, "UTF-7"))
				elif keyword in ti3[0]:
					ti3[0].remove_keyword(keyword)
			data = ti3[0].get("DATA")
			if len(color_rep) == 2 and data:
				# Check for XYZ/Lab = 0 readings
				query = {}
				for channel in color_rep[1]:
					query[color_rep[1] + "_" + channel] = 0
				device_labels = []
				for channel in color_rep[0]:
					device_labels.append(color_rep[0] + "_" + channel)
				zeros = data.queryi(query)
				errors = []
				remove = []
				for key in zeros.keys():
					sample = zeros[key]
					device_values = [sample[label] for label in device_labels]
					device_sum = 0
					for value in device_values:
						if value >= 5:
							# Error on device values >= 5
							errors.append(sample)
							self.log("Warning: Sample ID %i has %s = 0 and %s >= 5%%! (%s)" %
									 (sample.SAMPLE_ID, color_rep[1], color_rep[0],
									  " ".join(str(sample.queryv1(device_labels)).split())))
							device_sum = 0
							break
						device_sum += value
					if not device_sum:
						# Skip device black and device values >= 5
						continue
					# Queue sample for removal
					remove.insert(0, sample)
					self.log("Removed sample ID %i with %s = 0 and %s < 5%% (%s)" %
							 (sample.SAMPLE_ID, color_rep[1], color_rep[0],
							  " ".join(str(sample.queryv1(device_labels)).split())))
				for sample in remove:
					# Remove sample
					data.pop(sample)
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
		args.append("-v2") # verbose
		if getcfg("argyll.debug"):
			args.append("-D8")
		result = self.add_measurement_features(args,
											   allow_nondefault_observer=True)
		if isinstance(result, Exception):
			return result, None
		if calibrate:
			if getcfg("trc"):
				args.append("-q" + getcfg("calibration.quality"))
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
				args.append("-o")
			if getcfg("calibration.update") and not dry_run:
				cal = getcfg("calibration.file", False)
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
						getcfg("calibration.file", False))[0] + profile_ext
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
				args.append("-u")
		if calibrate or verify:
			if calibrate and not \
			   getcfg("calibration.interactive_display_adjustment"):
				# Skip interactive display adjustment
				args.append("-m")
			whitepoint_colortemp = getcfg("whitepoint.colortemp", False)
			whitepoint_x = getcfg("whitepoint.x", False)
			whitepoint_y = getcfg("whitepoint.y", False)
			if whitepoint_colortemp or None in (whitepoint_x, whitepoint_y):
				whitepoint = getcfg("whitepoint.colortemp.locus")
				if whitepoint_colortemp:
					whitepoint += str(whitepoint_colortemp)
				args.append("-" + whitepoint)
			else:
				args.append("-w%s,%s" % (whitepoint_x, whitepoint_y))
			luminance = getcfg("calibration.luminance", False)
			if luminance:
				args.append("-b%s" % luminance)
			if getcfg("trc"):
				args.append("-" + getcfg("trc.type") + str(getcfg("trc")))
				args.append("-f%s" % getcfg("calibration.black_output_offset"))
				if bool(int(getcfg("calibration.ambient_viewcond_adjust"))):
					args.append("-a%s" % 
								getcfg("calibration.ambient_viewcond_adjust.lux"))
				if not getcfg("calibration.black_point_correction.auto"):
					args.append("-k%s" % getcfg("calibration.black_point_correction"))
				if defaults["calibration.black_point_rate.enabled"] and \
				   float(getcfg("calibration.black_point_correction")) < 1:
					black_point_rate = getcfg("calibration.black_point_rate")
					if black_point_rate:
						args.append("-A%s" % black_point_rate)
			black_luminance = getcfg("calibration.black_luminance", False)
			if black_luminance:
				args.append("-B%f" % black_luminance)
			elif (not (getcfg("calibration.black_point_correction.auto") or
					   getcfg("calibration.black_point_correction")) and
				  defaults["calibration.black_point_hack"]):
				# Forced black point hack
				# (Argyll CMS 1.7b 2014-12-22)
				# Always use this if no black luminance or black point hue
				# correction specified. The rationale is that a reasonably good
				# quality digitally driven display should have no "dead zone"
				# above zero device input if set up correctly. Using this option
				# with a display that is not well behaved may result in a loss
				# of shadow detail.
				args.append("-b")
			if verify:
				if calibrate and type(verify) == int:
					args.append("-e%s" % verify)  # Verify final computed curves
				elif self.argyll_version >= [1, 6]:
					args.append("-z")  # Verify current curves
				else:
					args.append("-E")  # Verify current curves
		if getcfg("extra_args.dispcal").strip():
			args += parse_argument_string(getcfg("extra_args.dispcal"))
		if (config.get_display_name() == "Resolve" or
			(config.get_display_name() == "Prisma" and
			 not defaults["patterngenerator.prisma.argyll"])):
			# Substitute actual measurement frame dimensions
			self.options_dispcal = map(lambda arg: re.sub("^-[Pp]1,1,0.01$",
														  "-P" + getcfg("dimensions.measureframe"),
														  arg), args)
			# Re-add -F (darken background) so it can be set when loading settings
			if getcfg("measure.darken_background"):
				self.options_dispcal.append("-F")
		else:
			self.options_dispcal = list(args)
		if calibrate:
			args.append(inoutfile)
		return cmd, args

	def prepare_dispread(self, apply_calibration=True):
		"""
		Prepare a dispread commandline.
		
		All options are read from the user configuration.
		You can choose if you want to apply the current calibration,
		either the previously by dispcal created one by passing in True, by
		passing in a valid path to a .cal file, or by passing in None
		(current video card gamma table).
		
		"""
		self.lastcmdname = get_argyll_utilname("dispread")
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
		if apply_calibration is not False:
			if apply_calibration is True:
				# Always a .cal file in that case
				cal = os.path.join(getcfg("profile.save_path"), 
								   getcfg("profile.name.expanded"), 
								   getcfg("profile.name.expanded")) + ".cal"
			elif apply_calibration is None:
				# Use current videoLUT
				cal = inoutfile + ".cal"
				result = self.save_current_video_lut(self.get_display(), cal)
				if (isinstance(result, Exception) and
					not isinstance(result, UnloggedInfo)):
					return result, None
			else:
				cal = apply_calibration # can be .cal or .icc / .icm
			calcopy = inoutfile + ".cal"
			filename, ext = os.path.splitext(cal)
			if getcfg("dry_run"):
				options_dispcal = []
			elif ext.lower() == ".cal":
				result = check_cal_isfile(cal)
				if isinstance(result, Exception):
					return result, None
				if not result:
					return None, None
				# Get dispcal options if present
				try:
					options_dispcal = get_options_from_cal(cal)[0]
				except (IOError, CGATS.CGATSInvalidError, 
						CGATS.CGATSInvalidOperationError, CGATS.CGATSKeyError, 
						CGATS.CGATSTypeError, CGATS.CGATSValueError), exception:
					return exception, None
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
		# Special case -X because it can have a separate filename argument
		if "-X" in self.options_dispcal:
			index = self.options_dispcal.index("-X")
			if (len(self.options_dispcal) > index + 1 and
				self.options_dispcal[index + 1][0] != "-"):
				self.options_dispcal = (self.options_dispcal[:index] +
										self.options_dispcal[index + 2:])
		# Strip options we may override (basically all the stuff which can be 
		# added by add_measurement_features. -X is repeated because it can
		# have a number instead of explicit filename argument, e.g. -X1)
		dispcal_override_args = ("-F", "-H", "-I", "-P", "-V", "-X", "-d", "-c", 
								 "-p", "-y")
		self.options_dispcal = filter(lambda arg: not arg[:2] in dispcal_override_args, 
									  self.options_dispcal)
		# Only add the dispcal extra args which may override measurement features
		dispcal_extra_args = parse_argument_string(getcfg("extra_args.dispcal"))
		for i, arg in enumerate(dispcal_extra_args):
			if not arg.startswith("-") and i > 0:
				# Assume option to previous arg
				arg = dispcal_extra_args[i - 1]
			if arg[:2] in dispcal_override_args:
				self.options_dispcal.append(dispcal_extra_args[i])
		result = self.add_measurement_features(self.options_dispcal,
											   ignore_display_name=True)
		if isinstance(result, Exception):
			return result, None
		cmd = get_argyll_util("dispread")
		args = []
		args.append("-v") # verbose
		if getcfg("argyll.debug"):
			args.append("-D8")
		result = self.add_measurement_features(args,
											   allow_nondefault_observer=is_ccxx_testchart())
		if isinstance(result, Exception):
			return result, None
		if apply_calibration is not False:
			if (self.argyll_version >= [1, 3, 3] and
				(not self.has_lut_access() or
				 not getcfg("calibration.use_video_lut"))):
				args.append("-K")
			else:
				args.append("-k")
			args.append(cal)
		if self.get_instrument_features().get("spectral"):
			args.append("-s")
		if getcfg("extra_args.dispread").strip():
			args += parse_argument_string(getcfg("extra_args.dispread"))
		self.options_dispread = list(args)
		if getattr(self, "terminal", None) and isinstance(self.terminal,
														  UntetheredFrame):
			result = self.set_terminal_cgats(inoutfile + ".ti1")
			if isinstance(result, Exception):
				return result, None
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
		args.append("-v")
		if getcfg("argyll.debug"):
			if self.argyll_version >= [1, 3, 1]:
				args.append("-D8")
			else:
				args.append("-E8")
		args.append("-d" + self.get_display())
		if sys.platform != "darwin" or cal is False:
			# Mac OS X 10.7 Lion needs root privileges when clearing 
			# calibration
			args.append("-c")
		if cal is True:
			args.append(self.get_dispwin_display_profile_argument(
							max(0, min(len(self.displays), 
									   getcfg("display.number")) - 1)))
		elif cal:
			result = check_cal_isfile(cal)
			if isinstance(result, Exception):
				return result, None
			if not result:
				return None, None
			args.append(cal)
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
						  self.argyll_version > [1, 1, 1])):
							# -S option is broken on Linux with current Argyll 
							# releases
							args.append("-S" + getcfg("profile.install_scope"))
					else:
						# Make sure user profile dir exists
						# (e.g. on Mac OS X 10.9 Mavericks, it does not by
						# default)
						for profile_dir in reversed(iccprofiles_home):
							if os.path.isdir(profile_dir):
								break
						if not os.path.isdir(profile_dir):
							try:
								os.makedirs(profile_dir)
							except OSError, exception:
								return exception, None
					args.append("-I")
					# Always copy to temp dir so if a user accidentally tries
					# to install a profile from the location where it's already
					# installed (e.g. system32/spool/drivers/color) it doesn't
					# get nuked by dispwin
					tmp_dir = self.create_tempdir()
					if not tmp_dir or isinstance(tmp_dir, Exception):
						return tmp_dir, None
					# Check directory and in/output file(s)
					result = check_create_dir(tmp_dir)
					if isinstance(result, Exception):
						return result, None
					profile_name = os.path.basename(profile_path)
					if (sys.platform in ("win32", "darwin") or 
						fs_enc.upper() not in ("UTF8", "UTF-8")) and \
					   re.search("[^\x20-\x7e]", profile_name):
						# Copy to temp dir and give unique ASCII-only name to
						# avoid profile install issues
						# profile name: 'display<n>-<hexmd5sum>.icc'
						profile_tmp_path = os.path.join(tmp_dir, "display" + 
														self.get_display() + 
														"-" + 
														md5(profile.data).hexdigest() + 
														profile_ext)
					else:
						profile_tmp_path = os.path.join(tmp_dir, profile_name)
					shutil.copyfile(profile_path, profile_tmp_path)
					profile_path = profile_tmp_path
				args.append(profile_path)
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
		args.append('-v')
		args.append('-d3')
		args.append('-e%s' % getcfg("tc_white_patches"))
		if self.argyll_version >= [1, 6]:
			args.append('-B%s' % getcfg("tc_black_patches"))
		args.append('-s%s' % getcfg("tc_single_channel_patches"))
		args.append('-g%s' % getcfg("tc_gray_patches"))
		args.append('-m%s' % getcfg("tc_multi_steps"))
		if self.argyll_version >= [1, 6, 0]:
			args.append('-b%s' % getcfg("tc_multi_bcc_steps"))
		tc_algo = getcfg("tc_algo")
		if getcfg("tc_fullspread_patches") > 0:
			args.append('-f%s' % config.get_total_patches())
			if tc_algo:
				args.append('-' + tc_algo)
			if tc_algo in ("i", "I"):
				args.append('-a%s' % getcfg("tc_angle"))
			if tc_algo == "":
				args.append('-A%s' % getcfg("tc_adaption"))
			if self.argyll_version >= [1, 3, 3]:
				args.append('-N%s' % getcfg("tc_neutral_axis_emphasis"))
			if (self.argyll_version == [1, 1, "RC1"] or
				self.argyll_version >= [1, 1]):
				args.append('-G')
		else:
			args.append('-f0')
		if getcfg("tc_precond") and getcfg("tc_precond_profile"):
			args.append('-c')
			args.append(getcfg("tc_precond_profile"))
		if getcfg("tc_filter"):
			args.append('-F%s,%s,%s,%s' % (getcfg("tc_filter_L"), 
										   getcfg("tc_filter_a"), 
										   getcfg("tc_filter_b"), 
										   getcfg("tc_filter_rad")))
		if (self.argyll_version >= [1, 6, 2] and
			("-c" in args or self.argyll_version >= [1, 6, 3])):
			args.append('-V%s' % (1 + getcfg("tc_dark_emphasis") * 3))
		if self.argyll_version == [1, 1, "RC2"] or self.argyll_version >= [1, 1]:
			args.append('-p%s' % getcfg("tc_gamma"))
		if getcfg("extra_args.targen").strip():
			# Disallow -d and -D as the testchart editor only supports
			# video RGB (-d3)
			args += filter(lambda arg: not arg.lower().startswith("-d"),
						   parse_argument_string(getcfg("extra_args.targen")))
		self.options_targen = list(args)
		args.append(inoutfile)
		return cmd, args

	def progress_handler(self, event):
		""" Handle progress dialog updates and react to Argyll CMS command output """
		if getattr(self, "subprocess_abort", False) or \
		   getattr(self, "thread_abort", False):
			self.progress_wnd.Pulse(lang.getstr("aborting"))
			return
		percentage = None
		msg = self.recent.read(FilteredStream.triggers)
		lastmsg = self.lastmsg.read(FilteredStream.triggers).strip()
		warning = r"\D+: Warning -.*"
		msg = re.sub(warning, "", msg)
		lastmsg = re.sub(warning, "", lastmsg)
		# Filter for '=' so that 1% reading during calibration check
		# measurements doesn't trigger swapping from the interactive adjustment
		# to the progress window
		if re.match(r"\s*\d+%\s*(?:[^=]+)?$", lastmsg):
			# colprof, download progress
			try:
				percentage = int(self.lastmsg.read().split("%")[0])
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
				percentage = max(start - 1, 0) / end * 100
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
		else:
			iteration = re.search("It (\\d+):", msg)
			if iteration:
				# targen
				try:
					start = float(iteration.groups()[0])
				except ValueError:
					pass
				else:
					end = 20
					percentage = min(start, 20.0) / end * 100
					lastmsg = ""
		if (percentage is not None and time() > self.starttime + 3 and
			self.progress_wnd is getattr(self, "terminal", None)):
			# We no longer need keyboard interaction, switch over to
			# progress dialog
			wx.CallAfter(self.swap_progress_wnds)
		if hasattr(self.progress_wnd, "progress_type"):
			if self.pauseable or getattr(self, "interactive_frame", "") == "ambient":
				# If pauseable, we assume it's a measurement
				progress_type = 1  # Measuring
			elif self.cmdname == get_argyll_utilname("targen"):
				progress_type = 2  # Generating test patches
			else:
				progress_type = 0  # Processing
			if self.progress_wnd.progress_type != progress_type:
				self.progress_wnd.set_progress_type(progress_type)
		if getattr(self.progress_wnd, "original_msg", None) and \
		   msg != self.progress_wnd.original_msg:
			# UGLY HACK: This 'safe_print' call fixes a GTK assertion and 
			# segfault under Arch Linux when setting the window title.
			# This has a chance of throwing a IOError: [Errno 9] Bad file
			# descriptor under Windows, so check for wxGTK
			if "__WXGTK__" in wx.PlatformInfo:
				safe_print("")
			self.progress_wnd.SetTitle(self.progress_wnd.original_msg)
			self.progress_wnd.original_msg = None
		if percentage is not None:
			if "Setting up the instrument" in msg or \
			   "Commencing device calibration" in msg or \
			   "Commencing display calibration" in msg or \
			   "Calibration complete" in msg:
				self.recent.clear()
				msg = ""
			keepGoing, skip = self.progress_wnd.Update(max(min(percentage, 100), 0), 
													   msg + "\n" + 
													   lastmsg)
		elif re.match("\d+(?:\.\d+)? (?:[KM]iB)", lastmsg, re.I):
			keepGoing, skip = self.progress_wnd.Pulse("\n".join([msg, lastmsg]))
		else:
			if getattr(self.progress_wnd, "lastmsg", "") == msg or not msg:
				keepGoing, skip = self.progress_wnd.Pulse()
			else:
				if "Setting up the instrument" in lastmsg:
					msg = lang.getstr("instrument.initializing")
				elif "Created web server at" in msg:
					webserver = re.search("(http\:\/\/[^']+)", msg)
					if webserver:
						msg = (lang.getstr("webserver.waiting") +
							   " " + webserver.groups()[0])
				keepGoing, skip = self.progress_wnd.Pulse(msg)
		self.pause_continue()
		if hasattr(self.progress_wnd, "pause_continue"):
			if "read stopped at user request!" in lastmsg:
				self.progress_wnd.pause_continue.Enable()
			if self.progress_wnd.pause_continue.IsShown() != self.pauseable:
				self.progress_wnd.pause_continue.Show(self.pauseable)
				self.progress_wnd.Layout()
		if not keepGoing and not getattr(self, "abort_requested", False):
			# Only confirm abort if we are not currently doing interactive
			# display adjustment
			self.abort_subprocess(not isinstance(self._progress_wnd,
												 DisplayAdjustmentFrame))
		if self.finished is True:
			return
		if (self.progress_wnd.IsShownOnScreen() and
			not self.progress_wnd.IsActive() and
			(not getattr(self.progress_wnd, "dlg", None) or
			 not self.progress_wnd.dlg.IsShownOnScreen()) and
			wx.GetApp().GetTopWindow() and
			wx.GetApp().GetTopWindow().IsShownOnScreen() and
			(wx.GetApp().IsActive() or (sys.platform == "darwin" and
										not self.activated))):
			for window in wx.GetTopLevelWindows():
				if (window and window is not self.progress_wnd and
					isinstance(window, wx.Dialog) and window.IsShownOnScreen()):
					return
		   	self.activated = True
			self.progress_wnd.Raise()

	def progress_dlg_start(self, progress_title="", progress_msg="", 
						   parent=None, resume=False, fancy=True):
		""" Start a progress dialog, replacing existing one if present """
		if self._progress_wnd and \
		   self.progress_wnd is getattr(self, "terminal", None):
			self.terminal.stop_timer()
			self.terminal.Hide()
		if self.finished is True:
			return
		pauseable = getattr(self, "pauseable", False)
		fancy = fancy and getcfg("use_fancy_progress")
		if self._progress_dlgs.get((self.show_remaining_time, self.cancelable,
									fancy)):
			self.progress_wnd = self._progress_dlgs[(self.show_remaining_time,
													 self.cancelable, fancy)]
			# UGLY HACK: This 'safe_print' call fixes a GTK assertion and 
			# segfault under Arch Linux when setting the window title
			# This has a chance of throwing a IOError: [Errno 9] Bad file
			# descriptor under Windows, so check for wxGTK
			if "__WXGTK__" in wx.PlatformInfo:
				safe_print("")
			self.progress_wnd.SetTitle(progress_title)
			if not resume or not self.progress_wnd.IsShown():
				self.progress_wnd.reset()
			self.progress_wnd.Pulse(progress_msg)
			if hasattr(self.progress_wnd, "pause_continue"):
				self.progress_wnd.pause_continue.Show(pauseable)
				self.progress_wnd.Layout()
			self.progress_wnd.Resume()
			if not self.progress_wnd.IsShownOnScreen():
				self.progress_wnd.place()
				self.progress_wnd.Show()
		else:
			style = wx.PD_SMOOTH | wx.PD_ELAPSED_TIME
			if self.show_remaining_time:
				style |= wx.PD_REMAINING_TIME
			if self.cancelable:
				style |= wx.PD_CAN_ABORT
			# Set maximum to 101 to prevent the 'cancel' changing to 'close'
			# when 100 is reached
			self._progress_dlgs[(self.show_remaining_time, self.cancelable,
								 fancy)] = ProgressDialog(progress_title,
											   progress_msg, 
											   maximum=101, 
											   parent=parent, 
											   handler=self.progress_handler,
											   keyhandler=self.terminal_key_handler,
											   pauseable=pauseable,
											   style=style, start_timer=False,
											   fancy=fancy)
			self.progress_wnd = self._progress_dlgs[(self.show_remaining_time,
													 self.cancelable, fancy)]
		if hasattr(self.progress_wnd, "progress_type"):
			if pauseable or getattr(self, "interactive_frame", "") == "ambient":
				# If pauseable, we assume it's a measurement
				self.progress_wnd.progress_type = 1  # Measuring
			elif self.cmdname == get_argyll_utilname("targen"):
				self.progress_wnd.progress_type = 2  # Generating test patches
			else:
				self.progress_wnd.progress_type = 0  # Processing
		if not self.progress_wnd.timer.IsRunning():
			self.progress_wnd.start_timer()
		self.progress_wnd.original_msg = progress_msg
	
	def quit_terminate_cmd(self):
		""" Forcefully abort the current subprocess.
		
		Try to gracefully exit first by sending common Argyll CMS abort
		keystrokes (ESC), forcefully terminate the subprocess if not
		reacting
		
		"""
		# If running wexpect.spawn in a thread under Windows, writing to
		# sys.stdout from another thread can fail sporadically with IOError 9
		# 'Bad file descriptor', so don't use sys.stdout
		# Careful: Python 2.5 Producer objects don't have a name attribute
		if (hasattr(self, "thread") and self.thread.isAlive() and
			(not hasattr(currentThread(), "name") or
			 currentThread().name != self.thread.name)):
			logfn = log
		else:
			logfn = safe_print
		subprocess = getattr(self, "subprocess", None)
		if self.isalive(subprocess):
			try:
				if self.measure_cmd and hasattr(subprocess, "send"):
					self.log("%s: Trying to end subprocess gracefully..." % appname,
							 fn=logfn)
					try:
						if subprocess.after == "Current":
							# Stop measurement
							self.safe_send(" ")
							sleep(1)
						ts = time()
						while (self.isalive(subprocess) and
							   self.subprocess == subprocess):
							self.safe_send("\x1b")
							if time() > ts + 9:
								break
							sleep(.5)
					except Exception, exception:
						self.log(traceback.format_exc(), fn=logfn)
						self.log("%s: Exception in quit_terminate_command: %s" %
								 (appname, exception),  fn=logfn)
				if self.isalive(subprocess):
					self.log("%s: Trying to terminate subprocess..." % appname,
							 fn=logfn)
					subprocess.terminate()
					ts = time()
					while self.isalive(subprocess):
						if time() > ts + 3:
							break
						sleep(.25)
					if sys.platform != "win32" and self.isalive(subprocess):
						self.log("%s: Trying to terminate subprocess forcefully..." %
								 appname, fn=logfn)
						if isinstance(subprocess, sp.Popen):
							subprocess.kill()
						else:
							subprocess.terminate(force=True)
						ts = time()
						while self.isalive(subprocess):
							if time() > ts + 3:
								break
							sleep(.25)
					if self.isalive(subprocess):
						self.log("...warning: couldn't terminate subprocess.",
								 fn=logfn)
					else:
						self.log("...subprocess terminated.", fn=logfn)
			except Exception, exception:
				self.log(traceback.format_exc(), fn=logfn)
				self.log("%s: Exception in quit_terminate_command: %s" %
						 (appname, exception), fn=logfn)
		subprocess_isalive = self.isalive(subprocess)
		if (subprocess_isalive or
			(hasattr(self, "thread") and not self.thread.isAlive())):
			# We don't normally need this as closing of the progress window is
			# handled by _generic_consumer(), but there are two cases where it
			# is desirable to have this 'safety net':
			# 1. The user aborted a running task, but we couldn't terminate the
			#    associated subprocess. In that case, we have a lingering
			#    subprocess which is problematic but we can't do anything about
			#    it. Atleast we need to give control back to the user by closing
			#    the progress window so he can interact with the application
			#    and doesn't have to resort to forecfully terminate it.
			# 2. We started a thread with continue_next=True, which then exited
			#    without returning an error, yet not the result we were looking
			#    for, so we never started the next thread with resume=True, but
			#    we forgot to call stop_progress() exlicitly. This should never
			#    happen if we design our result consumer correctly to handle
			#    this particular case, but we need to make sure the user can
			#    close the progress window in case we mess up.
			if hasattr(self, "thread") and not self.thread.isAlive():
				wx.CallAfter(self.stop_progress)
			if subprocess_isalive:
				wx.CallAfter(show_result_dialog,
							 Warning("Couldn't terminate %s. Please try to end "
									 "it manually before continuing to use %s. " 
									 "If you can not terminate %s, restarting "
									 "%s may also help. Apologies for the "
									 "inconvenience." %
									 (self.cmd, appname, self.cmd, appname)),
							 self.owner)
		if self.patterngenerator:
			self.patterngenerator.listening = False
		return not subprocess_isalive
	
	def report(self, report_calibrated=True):
		""" Report on calibrated or uncalibrated display device response """
		cmd, args = self.prepare_dispcal(calibrate=False)
		if isinstance(cmd, Exception):
			return cmd
		if args:
			if report_calibrated:
				args.append("-r")
			else:
				args.append("-R")
		return self.exec_cmd(cmd, args, capture_output=True, skip_scripts=True)
	
	def reset_cal(self):
		cmd, args = self.prepare_dispwin(False)
		result = self.exec_cmd(cmd, args, capture_output=True, 
							   skip_scripts=True, silent=False)
		return result
	
	def safe_send(self, bytes):
		self.send_buffer = bytes
		return True
	
	def _safe_send(self, bytes, retry=3, obfuscate=False):
		""" Safely send a keystroke to the current subprocess """
		for i in xrange(0, retry):
			if obfuscate:
				logbytes = "***"
			else:
				logbytes = bytes
			self.logger.info("Sending key(s) %r (%i)" % (logbytes, i + 1))
			try:
				wrote = self.subprocess.send(bytes)
			except Exception, exception:
				self.logger.exception("Exception: %s" % safe_unicode(exception))
			else:
				if wrote == len(bytes):
					return True
			sleep(.25)
		return False

	def save_current_video_lut(self, display_no, outfilename,
							   interpolate_to_256=True, silent=False):
		""" Save current videoLUT, optionally interpolating to n entries """
		result = None
		if (self.argyll_version[0:3] > [1, 1, 0] or
			(self.argyll_version[0:3] == [1, 1, 0] and
			 not "Beta" in self.argyll_version_string)):
			cmd, args = (get_argyll_util("dispwin"),
						 ["-d%s" % display_no, "-s", outfilename])
			result = self.exec_cmd(cmd, args, capture_output=True, 
								   skip_scripts=True, silent=silent)
			if (isinstance(result, Exception) and
				not isinstance(result, UnloggedInfo)):
				return result
		if not result:
			return Error(lang.getstr("calibration.load_error"))
		# Make sure there are 256 entries in the .cal file, otherwise dispwin
		# will complain and not be able to load it back in.
		# Under Windows, the GetDeviceGammaRamp API seems to enforce 256 entries
		# regardless of graphics card, but under Linux and Mac OS X there may be
		# more than 256 entries if the graphics card has greater than 8 bit
		# videoLUTs (e.g. Quadro and newer consumer cards)
		cgats = CGATS.CGATS(outfilename)
		data = cgats.queryv1("DATA")
		if data and len(data) != 256:
			safe_print("VideoLUT has %i entries, interpolating to 256" %
					   len(data))
			rgb = {"I": [], "R": [], "G": [], "B": []}
			for entry in data.itervalues():
				for column in ("I", "R", "G", "B"):
					rgb[column].append(entry["RGB_" + column])
			interp = {}
			for column in ("R", "G", "B"):
				interp[column] = colormath.Interp(rgb["I"], rgb[column])
			resized = CGATS.CGATS()
			data.parent.DATA = resized
			resized.key = 'DATA'
			resized.parent = data.parent
			resized.root = cgats
			resized.type = 'DATA'
			for i in xrange(256):
				entry = {"RGB_I": i / 255.0}
				for column in ("R", "G", "B"):
					entry["RGB_" + column] = interp[column](entry["RGB_I"])
				resized.add_data(entry)
			cgats.write()
		return result
	
	def set_argyll_version(self, name, silent=False, cfg=False):
		self.set_argyll_version_from_string(get_argyll_version_string(name,
																	  silent),
											cfg)
	
	def set_argyll_version_from_string(self, argyll_version_string, cfg=True):
		self.argyll_version_string = argyll_version_string
		if cfg:
			setcfg("argyll.version", argyll_version_string)
			writecfg()
		self.argyll_version = parse_argyll_version_string(argyll_version_string)
	
	def set_terminal_cgats(self, cgats_filename):
		try:
			self.terminal.cgats = CGATS.CGATS(cgats_filename)
		except (IOError, CGATS.CGATSInvalidError, 
				CGATS.CGATSInvalidOperationError, CGATS.CGATSKeyError, 
				CGATS.CGATSTypeError, CGATS.CGATSValueError), exception:
			return exception
	
	def argyll_support_file_exists(self, name):
		""" Check if named file exists in any of the known Argyll support
		locations valid for the chosen Argyll CMS version. """
		if sys.platform != "darwin":
			paths = [defaultpaths.appdata] + defaultpaths.commonappdata
		else:
			paths = [defaultpaths.library_home, defaultpaths.library]
		searchpaths = []
		if self.argyll_version >= [1, 5, 0]:
			if sys.platform != "darwin":
				searchpaths.extend(os.path.join(dir_, "ArgyllCMS", name)
								   for dir_ in paths)
			else:
				searchpaths.extend(os.path.join(dir_, "ArgyllCMS", name)
								   for dir_ in [defaultpaths.appdata,
												defaultpaths.library])
		searchpaths.extend(os.path.join(dir_, "color", name) for dir_ in paths)
		for searchpath in searchpaths:
			if os.path.isfile(searchpath):
				return True
		return False

	def spyder2_firmware_exists(self):
		""" Check if the Spyder 2 firmware file exists in any of the known
		locations valid for the chosen Argyll CMS version. """
		if self.argyll_version < [1, 2, 0]:
			spyd2en = get_argyll_util("spyd2en")
			if not spyd2en:
				return False
			return os.path.isfile(os.path.join(os.path.dirname(spyd2en),
											   "spyd2PLD.bin"))
		else:
			return self.argyll_support_file_exists("spyd2PLD.bin")

	def spyder4_cal_exists(self):
		""" Check if the Spyder4/5 calibration file exists in any of the known
		locations valid for the chosen Argyll CMS version. """
		if self.argyll_version < [1, 3, 6]:
			# We couldn't use it even if it exists
			return False
		return self.argyll_support_file_exists("spyd4cal.bin")

	def start(self, consumer, producer, cargs=(), ckwargs=None, wargs=(), 
			  wkwargs=None, progress_title=appname, progress_msg="", 
			  parent=None, progress_start=100, resume=False, 
			  continue_next=False, stop_timers=True, interactive_frame="",
			  pauseable=False, cancelable=True, show_remaining_time=True,
			  fancy=True):
		"""
		Start a worker process.
		
		Also show a progress dialog while the process is running.
		
		consumer            consumer function.
		producer            producer function.
		cargs               consumer arguments.
		ckwargs             consumer keyword arguments.
		wargs               producer arguments.
		wkwargs             producer keyword arguments.
		progress_title      progress dialog title. Defaults to '%s'.
		progress_msg        progress dialog message. Defaults to ''.
		progress_start      show progress dialog after delay (ms).
		resume              resume previous progress dialog (elapsed time etc).
		continue_next       do not hide progress dialog after producer finishes.
		stop_timers         stop the timers on the owner window if True
		interactive_frame   "" or "uniformity" (selects the type of
		                    interactive window)
		pauseable           Is the operation pauseable? (show pause button on
		                    progress dialog)
		cancelable          Is the operation cancelable? (show cancel button on
		                    progress dialog)
		fancy               Use fancy progress dialog with animated throbber &
		                    sound fx
		
		""" % appname
		if ckwargs is None:
			ckwargs = {}
		if wkwargs is None:
			wkwargs = {}
		while self.is_working():
			sleep(.25) # wait until previous worker thread finishes
		if hasattr(self.owner, "stop_timers") and stop_timers:
			self.owner.stop_timers()
		if not parent:
			parent = self.owner
		if progress_start < 1:
			# Can't be zero!
			progress_start = 1
		self.activated = False
		self.cmdname = None
		self.cmdrun = False
		self.finished = False
		self.instrument_calibration_complete = False
		if not resume:
			self.instrument_on_screen = False
		self.instrument_place_on_screen_msg = False
		self.instrument_sensor_position_msg = False
		self.interactive_frame = interactive_frame
		self.is_ambient_measuring = interactive_frame == "ambient"
		self.lastcmdname = None
		self.pauseable = pauseable
		self.paused = False
		self.cancelable = cancelable
		self.show_remaining_time = show_remaining_time
		self.fancy = fancy
		self.resume = resume
		self.subprocess_abort = False
		self.abort_requested = False
		self.starttime = time()
		self.thread_abort = False
		if fancy and (not self.interactive or
					  interactive_frame not in ("uniformity", "untethered")):
			# Pre-init progress dialog bitmaps
			ProgressDialog.get_bitmaps(0)
			ProgressDialog.get_bitmaps(1)
		if self.interactive:
			self.progress_start_timer = wx.Timer()
			if progress_msg and progress_title == appname:
				progress_title = progress_msg
			if (config.get_display_name() == "Untethered" and
				interactive_frame != "uniformity"):
				interactive_frame = "untethered"
			if interactive_frame == "adjust":
				windowclass = DisplayAdjustmentFrame
			elif interactive_frame == "uniformity":
				windowclass = DisplayUniformityFrame
			elif interactive_frame == "untethered":
				windowclass = UntetheredFrame
			else:
				windowclass = SimpleTerminal
			if getattr(self, "terminal", None) and isinstance(self.terminal,
															  windowclass):
				self.progress_wnd = self.terminal
				if not resume:
					if isinstance(self.progress_wnd, SimpleTerminal):
						self.progress_wnd.console.SetValue("")
					elif (isinstance(self.progress_wnd, DisplayAdjustmentFrame) or
						  isinstance(self.progress_wnd, DisplayUniformityFrame) or
						  isinstance(self.progress_wnd, UntetheredFrame)):
						self.progress_wnd.reset()
				self.progress_wnd.stop_timer()
				self.progress_wnd.Resume()
				self.progress_wnd.start_timer()
				# UGLY HACK: This 'safe_print' call fixes a GTK assertion and 
				# segfault under Arch Linux when setting the window title
				safe_print("")
				if isinstance(self.progress_wnd, SimpleTerminal):
					self.progress_wnd.SetTitle(progress_title)
				self.progress_wnd.Show()
				if resume and isinstance(self.progress_wnd, SimpleTerminal):
					self.progress_wnd.console.ScrollLines(
						self.progress_wnd.console.GetNumberOfLines())
			else:
				if getattr(self, "terminal", None):
					# Destroy the wx object so the decref'd python object can
					# be garbage collected
					self.terminal.Destroy()
				if interactive_frame == "adjust":
					self.terminal = DisplayAdjustmentFrame(parent,
														   handler=self.progress_handler,
														   keyhandler=self.terminal_key_handler)
				elif interactive_frame == "uniformity":
					self.terminal = DisplayUniformityFrame(parent,
														   handler=self.progress_handler,
														   keyhandler=self.terminal_key_handler)
				elif interactive_frame == "untethered":
					self.terminal = UntetheredFrame(parent,
													handler=self.progress_handler,
													keyhandler=self.terminal_key_handler)
				else:
					self.terminal = SimpleTerminal(parent, title=progress_title,
												   handler=self.progress_handler,
												   keyhandler=self.terminal_key_handler)
				self.terminal.worker = self
				self.progress_wnd = self.terminal
		else:
			if not progress_msg:
				progress_msg = lang.getstr("please_wait")
			# Show the progress dialog after a delay
			self.progress_start_timer = BetterCallLater(progress_start, 
													 self.progress_dlg_start, 
													 progress_title, 
													 progress_msg, parent,
													 resume, fancy)
		if not hasattr(self, "_disabler"):
			self._disabler = BetterWindowDisabler(self.progress_wnds)
		# Can't use startWorker because we may need access to self.thread from
		# within thread, and startWorker does not return before the actual
		# thread starts running
		jobID = None
		sender = delayedresult.SenderCallAfter(self._generic_consumer, jobID,
											   args=[consumer, continue_next] +
													list(cargs), kwargs=ckwargs)
		self.thread = delayedresult.Producer(sender, Producer(self, producer,
															  continue_next),
											 args=wargs, kwargs=wkwargs, 
											 name=jobID, group=None,
											 daemon=False, senderArg=None,
											 sendReturn=True)
        
		self.thread.start()
		return True
	
	def stop_progress(self):
		if hasattr(self, "_disabler"):
			del self._disabler
		if getattr(self, "progress_wnd", False):
			if getattr(self.progress_wnd, "dlg", None):
				if self.progress_wnd.dlg.IsShownOnScreen():
					self.progress_wnd.dlg.EndModal(wx.ID_CANCEL)
				self.progress_wnd.dlg = None
			self.progress_wnd.stop_timer()
			self.progress_wnd.Hide()
			self.subprocess_abort = False
			self.thread_abort = False
			self.interactive = False
	
	def swap_progress_wnds(self):
		""" Swap the current interactive window with a progress dialog """
		parent = self.terminal.GetParent()
		if isinstance(self.terminal, DisplayAdjustmentFrame):
			title = lang.getstr("calibration")
		else:
			title = self.terminal.GetTitle()
		self.progress_dlg_start(title, "", parent, self.resume, self.fancy)
	
	def terminal_key_handler(self, event):
		""" Key handler for the interactive window or progress dialog. """
		keycode = None
		if event.GetEventType() in (wx.EVT_CHAR_HOOK.typeId,
									wx.EVT_KEY_DOWN.typeId):
			keycode = event.GetKeyCode()
		elif event.GetEventType() == wx.EVT_MENU.typeId:
			keycode = self.progress_wnd.id_to_keycode.get(event.GetId())
		if keycode is not None and getattr(self, "subprocess", None) and \
			hasattr(self.subprocess, "send"):
			keycode = keycodes.get(keycode, keycode)
			if keycode in (ord("\x1b"), ord("8"), ord("Q"), ord("q")):
				# exit
				self.abort_subprocess(True)
				return
			try:
				self.safe_send(chr(keycode))
			except:
				pass
	
	def calculate_gamut(self, profile_path, intent="r", direction="f",
						order="n", compare_standard_gamuts=True):
		"""
		Calculate gamut, volume, and coverage % against sRGB and Adobe RGB.
		
		Return gamut volume (int, scaled to sRGB = 1.0) and
		coverage (dict) as tuple.
		
		"""
		if isinstance(profile_path, list):
			profile_paths = profile_path
		else:
			profile_paths = [profile_path]
		outname = os.path.splitext(profile_paths[0])[0]
		mods = []
		if intent != "r":
			mods.append(intent)
		if direction != "f":
			mods.append(direction)
		if order != "n":
			mods.append(order)
		if mods:
			outname += " " + "".join(["[%s]" % mod.upper()
									  for mod in mods])
		gamut_volume = None
		gamut_coverage = {}
		# Create profile gamut and vrml
		det = getcfg("iccgamut.surface_detail")
		for i, profile_path in enumerate(profile_paths):
			if not profile_path:
				self.log("Warning: calculate_gamut(): No profile path %i" % i)
				continue
			result = self.exec_cmd(get_argyll_util("iccgamut"),
								   ["-v", "-w", "-i" + intent, "-f" + direction,
									"-o" + order, "-d%.2f" % det, profile_path],
								   capture_output=True,
								   skip_scripts=True)
			if not isinstance(result, Exception) and result:
				# iccgamut output looks like this:
				# Header:
				#  <...>
				#
				# Total volume of gamut is xxxxxx.xxxxxx cubic colorspace units
				for line in self.output:
					match = re.search("(\d+(?:\.\d+)?)\s+cubic\s+colorspace\s+"
									  "units", line)
					if match:
						gamut_volume = float(match.groups()[0]) / ICCP.GAMUT_VOLUME_SRGB
						break
			else:
				break
		name = os.path.splitext(profile_paths[0])[0]
		gamfilename = name + ".gam"
		wrlfilename = name + ".wrl"
		tmpfilenames = [gamfilename, wrlfilename]
		if compare_standard_gamuts:
			comparison_gamuts = [("srgb", "sRGB"),
								 ("adobe-rgb", "ClayRGB1998"),
								 ("dci-p3", "SMPTE431_P3")]
		else:
			comparison_gamuts = []
		for profile_path in profile_paths[1:]:
			filename, ext = os.path.splitext(profile_path)
			comparison_gamuts.append((filename.lower().replace(" ", "-"),
									  filename + ".gam"))
		for key, src in comparison_gamuts:
			if not isinstance(result, Exception) and result:
				# Create gamut view and intersection
				if os.path.isabs(src):
					src_path = src
					src = os.path.splitext(os.path.basename(src))[0]
				else:
					if mods:
						src += " " + "".join(["[%s]" % mod.upper()
											  for mod in mods])
					src_path = get_data_path("ref/%s.gam" % src)
				if not src_path:
					continue
				outfilename = outname + " vs " + src
				if mods:
					outfilename += " " + "".join(["[%s]" % mod.upper()
												  for mod in mods])
				outfilename += ".wrl"
				tmpfilenames.append(outfilename)
				result = self.exec_cmd(get_argyll_util("viewgam"),
									   ["-cw", "-t0", "-w", src_path, "-cn",
										"-t.3", "-s", gamfilename, "-i",
										outfilename],
									   capture_output=True,
									   skip_scripts=True)
				if not isinstance(result, Exception) and result:
					# viewgam output looks like this:
					# Intersecting volume = xxx.x cubic units
					# 'path/to/1.gam' volume = xxx.x cubic units, intersect = xx.xx%
					# 'path/to/2.gam' volume = xxx.x cubic units, intersect = xx.xx%
					for line in self.output:
						match = re.search("[\\\/]%s.gam'\s+volume\s*=\s*"
										  "\d+(?:\.\d+)?\s+cubic\s+units,?"
										  "\s+intersect\s*=\s*"
										  "(\d+(?:\.\d+)?)" %
										  re.escape(src), line)
						if match:
							gamut_coverage[key] = float(match.groups()[0]) / 100.0
							break
		if not isinstance(result, Exception) and result:
			for tmpfilename in tmpfilenames:
				if (tmpfilename == gamfilename and
					tmpfilename != outname + ".gam"):
					# Use the original file name
					filename = outname + ".gam"
				elif (tmpfilename == wrlfilename and
					  tmpfilename != outname + ".wrl"):
					# Use the original file name
					filename = outname + ".wrl"
				else:
					filename = tmpfilename
				try:
					def tweak_vrml(vrml):
						# Set viewpoint further away
						vrml = re.sub("(Viewpoint\s*\{)[^}]+\}",
									  r"\1 position 0 0 340 }", vrml)
						# Fix label color for -a* axis
						label = re.search(r'Transform\s*\{\s*translation\s+[+\-0-9.]+\s*[+\-0-9.]+\s*[+\-0-9.]+\s+children\s*\[\s*Shape\s*\{\s*geometry\s+Text\s*\{\s*string\s*\["-a\*"\]\s*fontStyle\s+FontStyle\s*\{[^}]*\}\s*\}\s*appearance\s+Appearance\s*\{\s*material\s+Material\s*{[^}]*\}\s*\}\s*\}\s*\]\s*\}', vrml)
						if label:
							label = label.group()
							vrml = vrml.replace(label,
												re.sub(r"(diffuseColor)\s+[+\-0-9.]+\s+[+\-0-9.]+\s+[+\-0-9.]+",
													   r"\1 0.0 1.0 0.0",
													   label))
						# Add range to axes
						vrml = re.sub(r'(string\s*\[")(\+?)(L\*)("\])',
									  r'\1\3", "\2\0$\4', vrml)
						vrml = re.sub(r'(string\s*\[")([+\-]?)(a\*)("\])',
									  r'\1\3", "\2\0$\4', vrml)
						vrml = re.sub(r'(string\s*\[")([+\-]?)(b\*)("\])',
									  r'\1\3 \2\0$\4', vrml)
						vrml = vrml.replace("\0$", "100")
						return vrml
					gzfilename = filename + ".gz"
					if sys.platform == "win32":
						filename = make_win32_compatible_long_path(filename)
						gzfilename = make_win32_compatible_long_path(gzfilename)
						tmpfilename = make_win32_compatible_long_path(tmpfilename)
					if getcfg("vrml.compress"):
						# Compress gam and wrl files using gzip
						with GzipFileProper(gzfilename, "wb") as gz:
							# Always use original filename with '.gz' extension,
							# that way the filename in the header will be correct
							with open(tmpfilename, "rb") as infile:
								gz.write(tweak_vrml(infile.read()))
						# Remove uncompressed file
						os.remove(tmpfilename)
						tmpfilename = gzfilename
					else:
						with open(tmpfilename, "rb") as infile:
							vrml = infile.read()
						with open(tmpfilename, "wb") as outfile:
							outfile.write(tweak_vrml(vrml))
					if filename.endswith(".wrl"):
						filename = filename[:-4] + ".wrz"
					else:
						filename = gzfilename
					if tmpfilename != filename:
						# Rename the file if filename is different
						if os.path.exists(filename):
							os.remove(filename)
						os.rename(tmpfilename, filename)
				except Exception, exception:
					self.log(exception)
		elif result:
			# Exception
			self.log(result)
		return gamut_volume, gamut_coverage

	def calibrate(self, remove=False):
		""" Calibrate the screen and process the generated file(s). """
		capture_output = not sys.stdout.isatty()
		cmd, args = self.prepare_dispcal()
		if not isinstance(cmd, Exception):
			result = self.exec_cmd(cmd, args, capture_output=capture_output)
		else:
			result = cmd
		if not isinstance(result, Exception) and result and getcfg("trc"):
			dst_pathname = os.path.join(getcfg("profile.save_path"), 
										getcfg("profile.name.expanded"), 
										getcfg("profile.name.expanded"))
			cal = args[-1] + ".cal"
			result = check_cal_isfile(
				cal, lang.getstr("error.calibration.file_not_created"))
			if not isinstance(result, Exception) and result:
				cal_cgats = add_dispcal_options_to_cal(cal, 
													   self.options_dispcal)
				if cal_cgats:
					cal_cgats.write()
				if getcfg("profile.update") or \
				   self.dispcal_create_fast_matrix_shaper:
					profile_path = args[-1] + profile_ext
					result = check_profile_isfile(
						profile_path, 
						lang.getstr("error.profile.file_not_created"))
					if not isinstance(result, Exception) and result:
						try:
							profile = ICCP.ICCProfile(profile_path)
						except (IOError, ICCP.ICCProfileInvalidError), exception:
							result = Error(lang.getstr("profile.invalid") + "\n"
										   + profile_path)
					if not isinstance(result, Exception) and result:
						if not getcfg("profile.update"):
							# Created fast matrix shaper profile
							# we need to set cprt, targ and a few other things
							profile.setCopyright(getcfg("copyright"))
							# Fast matrix shaper profiles currently don't
							# contain TI3 data, but look for it anyways
							# to be future-proof
							ti3 = add_options_to_ti3(
								profile.tags.get("targ", 
												 profile.tags.get("CIED", 
																  "")), 
								self.options_dispcal)
							if not ti3:
								ti3 = CGATS.CGATS("TI3\n")
								ti3[1] = cal_cgats
							edid = self.get_display_edid()
							display_name = edid.get("monitor_name",
													edid.get("ascii",
															 str(edid.get("product_id") or "")))
							display_manufacturer = edid.get("manufacturer")
							profile.setDeviceModelDescription(display_name)
							if display_manufacturer:
								profile.setDeviceManufacturerDescription(
									display_manufacturer)
							(gamut_volume,
							 gamut_coverage) = self.create_gamut_views(profile_path)
							self.update_profile(profile, ti3=str(ti3),
												chrm=None, tags=True, avg=None,
												peak=None, rms=None,
												gamut_volume=gamut_volume,
												gamut_coverage=gamut_coverage,
												quality=getcfg("calibration.quality"))
						else:
							# Update desc tag - ASCII needs to be 7-bit
							# also add Unicode string if different from ASCII
							if "desc" in profile.tags and isinstance(profile.tags.desc, 
																	 ICCP.TextDescriptionType):
								profile.setDescription(
									getcfg("profile.name.expanded"))
							# Calculate profile ID
							profile.calculateID()
							try:
								profile.write()
							except Exception, exception:
								self.log(exception)
		result2 = self.wrapup(not isinstance(result, UnloggedInfo) and result,
							  remove or isinstance(result, Exception) or
							  not result)
		if isinstance(result2, Exception):
			if isinstance(result, Exception):
				result = Error(safe_unicode(result) + "\n\n" +
							   safe_unicode(result2))
			else:
				result = result2
		elif not isinstance(result, Exception) and result and getcfg("trc"):
			setcfg("last_cal_path", dst_pathname + ".cal")
			setcfg("calibration.file.previous", getcfg("calibration.file", False))
			if (getcfg("profile.update") or
				self.dispcal_create_fast_matrix_shaper):
				setcfg("last_cal_or_icc_path", dst_pathname + profile_ext)
				setcfg("last_icc_path", dst_pathname + profile_ext)
				setcfg("calibration.file", dst_pathname + profile_ext)
			else:
				setcfg("calibration.file", dst_pathname + ".cal")
				setcfg("last_cal_or_icc_path", dst_pathname + ".cal")
		return result

	@property
	def calibration_loading_generally_supported(self):
		# Loading/clearing calibration seems to have undesirable side-effects
		# on Mac OS X 10.6 and newer
		return (sys.platform != "darwin" or
				intlist(mac_ver()[0].split(".")) < [10, 6])
	
	@property
	def calibration_loading_supported(self):
		# Loading/clearing calibration seems to have undesirable side-effects
		# on Mac OS X 10.6 and newer
		return (self.calibration_loading_generally_supported and
				not config.is_virtual_display())

	def change_display_profile_cal_whitepoint(self, profile, x, y, outfilename,
											  calibration_only=False,
											  use_collink=False):
		"""
		Change display profile (and calibration) whitepoint.
		
		Do it in an colorimetrically accurate manner (as far as possible).
		
		"""
		XYZw = colormath.xyY2XYZ(x, y)
		xicclu = get_argyll_util("xicclu")
		if not xicclu:
			return Error(lang.getstr("argyll.util.not_found", "xicclu"))
		tempdir = self.create_tempdir()
		if isinstance(tempdir, Exception):
			return tempdir
		outpathname = os.path.splitext(outfilename)[0]
		outname = os.path.basename(outpathname)
		logfiles = Files([self.recent, self.lastmsg,
						  LineBufferedStream(safe_print)])
		ofilename = profile.fileName
		temppathname = os.path.join(tempdir, outname)
		if ofilename and os.path.isfile(ofilename):
			# Profile comes from a file
			temp = False
			temporig = ofilename
		else:
			# Profile not associated to a file, write to temp dir
			temp = True
			profile.fileName = temporig = temppathname + ".orig.icc"
			profile.write(temporig)
		# Remember original white XYZ
		origXYZ = profile.tags.wtpt.X, profile.tags.wtpt.Y, profile.tags.wtpt.Z
		# Make a copy of the profile with changed whitepoint
		profile.tags.wtpt.X, profile.tags.wtpt.Y, profile.tags.wtpt.Z = XYZw
		tempcopy = temppathname + ".copy.icc"
		profile.write(tempcopy)
		# Generate updated calibration with changed whitepoint
		if use_collink:
			collink = get_argyll_util("collink")
			if not collink:
				profile.fileName = ofilename
				self.wrapup(False)
				return Error(lang.getstr("argyll.util.not_found", "collink"))
			linkpath = temppathname + ".link.icc"
			result = self.exec_cmd(collink, ["-v", "-n", "-G", "-iaw", "-b",
											 tempcopy, temporig, linkpath],
								   capture_output=True)
			if not result or isinstance(result, Exception):
				profile.fileName = ofilename
				self.wrapup(False)
				return result
			link = ICCP.ICCProfile(linkpath)
			RGBscaled = []
			for i in xrange(256):
				RGBscaled.append([i / 255.0] * 3)
			RGBscaled = self.xicclu(link, RGBscaled)
			logfiles.write("RGB white %6.4f %6.4f %6.4f\n" % tuple(RGBscaled[-1]))
			# Restore original white XYZ
			profile.tags.wtpt.X, profile.tags.wtpt.Y, profile.tags.wtpt.Z = origXYZ
			# Get white RGB
			XYZwscaled = self.xicclu(profile, RGBscaled[-1], "a")[0]
			logfiles.write("XYZ white %6.4f %6.4f %6.4f, CCT %i\n" %
						   tuple(XYZwscaled + [colormath.XYZ2CCT(*XYZwscaled)]))
		else:
			# Lookup scaled down white XYZ
			logfiles.write("Looking for solution...\n")
			XYZscaled = []
			for i in xrange(2000):
				XYZscaled.append([v * (1 - i / 1999.0) for v in XYZw])
			RGBscaled = self.xicclu(profile, XYZscaled, "a", "if", get_clip=True)
			# Set filename to copy (used by worker.xicclu to get profile path)
			profile.fileName = tempcopy
			# Find point at which it no longer clips
			for i, RGBclip in enumerate(RGBscaled):
				if RGBclip[3] is True:
					# Clipped, skip
					continue
				# Found
				XYZwscaled = XYZscaled[i]
				logfiles.write("Solution found at index %i (step size %f)\n" %
							   (i, 1 / 1999.0))
				logfiles.write("RGB white %6.4f %6.4f %6.4f\n" % tuple(RGBclip[:3]))
				logfiles.write("XYZ white %6.4f %6.4f %6.4f, CCT %i\n" %
							   tuple(XYZscaled[i] +
									 [colormath.XYZ2CCT(*XYZscaled[i])]))
				break
			else:
				profile.fileName = ofilename
				self.wrapup(False)
				return Error("No solution found in %i steps" % i)
			# Generate RGB input values
			# Reduce interpolation res as target whitepoint moves farther away
			# from profile whitepoint in RGB
			res = max(int(round((min(RGBclip[:3]) / 1.0) * 33)), 9)
			logfiles.write("Interpolation res %i\n" % res)
			RGBscaled = []
			for i in xrange(res):
				RGBscaled.append([v * (i / (res - 1.0)) for v in (1, 1, 1)])
			# Lookup RGB -> XYZ through whitepoint adjusted profile
			RGBscaled2XYZ = self.xicclu(profile, RGBscaled, "a")
			# Restore original XYZ
			profile.tags.wtpt.X, profile.tags.wtpt.Y, profile.tags.wtpt.Z = origXYZ
			# Restore original filename (used by worker.xicclu to get profile path)
			profile.fileName = temporig
			# Get original black point
			XYZk = self.xicclu(profile, [0, 0, 0], "a")[0]
			logfiles.write("XYZ black %6.4f %6.4f %6.4f\n" % tuple(XYZk))
			logfiles.write("XYZ white after forward lookup %6.4f %6.4f %6.4f\n" %
						   tuple(RGBscaled2XYZ[-1]))
			# Scale down XYZ
			XYZscaled = []
			for i in xrange(res):
				XYZ = [v * XYZwscaled[1] for v in RGBscaled2XYZ[i]]
				if i == 0:
					bp_in = XYZ
				XYZ = colormath.apply_bpc(*XYZ, bp_in=bp_in, bp_out=XYZk,
										  wp_out=XYZwscaled, weight=True)
				XYZscaled.append(XYZ)
			logfiles.write("XYZ white after scale down %6.4f %6.4f %6.4f\n" %
						   tuple(XYZscaled[-1]))
			# Lookup XYZ -> RGB through original profile
			RGBscaled = self.xicclu(profile, XYZscaled, "a", "if",
									use_cam_clipping=True)
			logfiles.write("RGB black after inverse forward lookup %6.4f %6.4f %6.4f\n" %
						   tuple(RGBscaled[0]))
			logfiles.write("RGB white after inverse forward lookup %6.4f %6.4f %6.4f\n" %
						   tuple(RGBscaled[-1]))
			if res != 256:
				# Interpolate
				R = []
				G = []
				B = []
				for i, RGB in enumerate(RGBscaled):
					R.append(RGB[0])
					G.append(RGB[1])
					B.append(RGB[2])
				if res > 2:
					# Catmull-Rom spline interpolation
					Ri = ICCP.CRInterpolation(R)
					Gi = ICCP.CRInterpolation(G)
					Bi = ICCP.CRInterpolation(B)
				else:
					# Linear interpolation
					Ri = colormath.Interp(range(res), R)
					Gi = colormath.Interp(range(res), G)
					Bi = colormath.Interp(range(res), B)
				RGBscaled = []
				step = (res - 1) / 255.0
				for i in xrange(256):
					RGB = [Ri(i * step), Gi(i * step), Bi(i * step)]
					RGBscaled.append(RGB)
				logfiles.write("RGB black after interpolation %6.4f %6.4f %6.4f\n" %
							   tuple(RGBscaled[0]))
				logfiles.write("RGB white after interpolation %6.4f %6.4f %6.4f\n" %
							   tuple(RGBscaled[-1]))
		has_nonlinear_vcgt = (isinstance(profile.tags.get("vcgt"),
										 ICCP.VideoCardGammaType) and
							  not profile.tags.vcgt.is_linear())
		if has_nonlinear_vcgt:
			# Apply cal
			ocal = vcgt_to_cal(profile)
			bp_out = ocal.queryv1({"RGB_R": 0, "RGB_G": 0, "RGB_B": 0}).values()
			ocalpath = temppathname + ".cal"
			ocal.filename = ocalpath
			RGBscaled = self.xicclu(ocal, RGBscaled)
			logfiles.write("RGB black after cal %6.4f %6.4f %6.4f\n" %
						   tuple(RGBscaled[0]))
			logfiles.write("RGB white after cal %6.4f %6.4f %6.4f\n" %
						   tuple(RGBscaled[-1]))
		else:
			bp_out = (0, 0, 0)
		cal = """CAL    

KEYWORD "DEVICE_CLASS"
DEVICE_CLASS "DISPLAY"
KEYWORD "COLOR_REP"
COLOR_REP "RGB"
BEGIN_DATA_FORMAT
RGB_I RGB_R RGB_G RGB_B
END_DATA_FORMAT
NUMBER_OF_SETS 256
BEGIN_DATA
"""
		for i, RGB in enumerate(RGBscaled):
			R, G, B = colormath.apply_bpc(*RGB, bp_in=RGBscaled[0],
										  bp_out=bp_out, wp_out=RGBscaled[-1],
										  weight=True)
			cal += "%f %f %f %f\n" % (i / 255.0, R, G, B)
		cal += "END_DATA"
		cal = CGATS.CGATS(cal)
		cal.filename = outpathname + ".cal"
		cal.write()
		if calibration_only:
			# Only update calibration
			profile.setDescription(outname)
			profile.tags.vcgt = cal_to_fake_profile(cal).tags.vcgt
			profile.tags.wtpt.X, profile.tags.wtpt.Y, profile.tags.wtpt.Z = XYZw
			profile.calculateID()
			profile.write(outfilename)
			self.wrapup(False)
			return True
		else:
			# Re-create profile
			cti3 = None
			if isinstance(profile.tags.get("targ"), ICCP.Text):
				# Get measurement data
				try:
					cti3 = CGATS.CGATS(profile.tags.targ)
				except (IOError, CGATS.CGATSError):
					pass
				else:
					if not 0 in cti3 or cti3[0].type.strip() != "CTI3":
						# Not Argyll measurement data
						cti3 = None
			if not cti3:
				# Use fakeread
				fakeread = get_argyll_util("fakeread")
				if not fakeread:
					profile.fileName = ofilename
					self.wrapup(False)
					return Error(lang.getstr("argyll.util.not_found", "fakeread"))
				shutil.copyfile(defaults["testchart.file"],
								temppathname + ".ti1")
				result = self.exec_cmd(fakeread, [temporig, temppathname])
				if not result or isinstance(result, Exception):
					profile.fileName = ofilename
					self.wrapup(False)
					return result
				cti3 = CGATS.CGATS(temppathname + ".ti3")
			# Get RGB from measurement data
			RGBorig = []
			for i, sample in cti3[0].DATA.iteritems():
				RGB = []
				for j, component in enumerate("RGB"):
					RGB.append(sample["RGB_" + component])
				RGBorig.append(RGB)
			# Lookup RGB -> scaled RGB through calibration
			RGBscaled = self.xicclu(cal, RGBorig, scale=100)
			if has_nonlinear_vcgt:
				# Undo original calibration
				RGBscaled = self.xicclu(ocal, RGBscaled, direction="b", scale=100)
			# Update CAL in ti3 file
			if 1 in cti3 and cti3[1].type.strip() == "CAL":
				cti3[1].DATA = cal[0].DATA
			else:
				cti3[1] = cal[0]
			# Lookup scaled RGB -> XYZ through profile
			RGBscaled2XYZ = self.xicclu(profile, RGBscaled, "a", scale=100)
			# Update measurement data
			if "LUMINANCE_XYZ_CDM2" in cti3[0]:
				XYZa = [float(v) * XYZwscaled[i] for i, v in enumerate(cti3[0].LUMINANCE_XYZ_CDM2.split())]
				cti3[0].add_keyword("LUMINANCE_XYZ_CDM2", " ".join([str(v) for v in XYZa]))
			for i, sample in cti3[0].DATA.iteritems():
				for j, component in enumerate("XYZ"):
					sample["XYZ_" + component] = RGBscaled2XYZ[i][j] / XYZwscaled[1] * 100
			cti3.write(temppathname + ".ti3")
			# Preserve custom tags
			display_name = profile.getDeviceModelDescription()
			display_manufacturer = profile.getDeviceManufacturerDescription()
			tags = {}
			for tagname in ("mmod", "meta"):
				if tagname in profile.tags:
					tags[tagname] = profile.tags[tagname]
			if temp:
				os.remove(temporig)
			os.remove(tempcopy)
			# Compute profile
			self.options_targen = ["-d3"]
			return self.create_profile(outfilename, True, display_name,
									   display_manufacturer, tags)
	
	def chart_lookup(self, cgats, profile, as_ti3=False, fields=None,
					 check_missing_fields=False, function="f", pcs="l",
					 intent="r", bt1886=None, white_patches=4,
					 white_patches_total=True, raise_exceptions=False):
		""" Lookup CIE or device values through profile """
		if profile.colorSpace == "RGB":
			labels = ('RGB_R', 'RGB_G', 'RGB_B')
		else:
			labels = ('CMYK_C', 'CMYK_M', 'CMYK_Y', 'CMYK_K')
		ti1 = None
		ti3_ref = None
		gray = None
		try:
			if not isinstance(cgats, CGATS.CGATS):
				cgats = CGATS.CGATS(cgats, True)
			else:
				# Always make a copy and do not alter a passed in CGATS instance!
				cgats_filename = cgats.filename
				cgats = CGATS.CGATS(str(cgats))
				cgats.filename = cgats_filename
			if 0 in cgats:
				# only look at the first section
				cgats[0].filename = cgats.filename
				cgats = cgats[0]
			primaries = cgats.queryi(labels)
			if primaries and not as_ti3:
				primaries.fix_device_values_scaling(profile.colorSpace)
				cgats.type = 'CTI1'
				cgats.COLOR_REP = profile.colorSpace
				ti1, ti3_ref, gray = self.ti1_lookup_to_ti3(cgats, profile, 
															function, pcs,
															"r",
															white_patches,
															white_patches_total)
				if bt1886 or intent == "a":
					cat = profile.guess_cat() or "Bradford"
					for item in ti3_ref.DATA.itervalues():
						if pcs == "l":
							X, Y, Z = colormath.Lab2XYZ(item["LAB_L"],
														item["LAB_A"],
														item["LAB_B"])
						else:
							X, Y, Z = item["XYZ_X"], item["XYZ_Y"], item["XYZ_Z"]
						if bt1886:
							X, Y, Z = bt1886.apply(X, Y, Z)
						if intent == "a":
							X, Y, Z = colormath.adapt(X, Y, Z,
													  "D50",
													  profile.tags.wtpt.values(),
													  cat=cat)
						X, Y, Z = [v * 100 for v in (X, Y, Z)]
						if pcs == "l":
							(item["LAB_L"],
							 item["LAB_A"],
							 item["LAB_B"]) = colormath.XYZ2Lab(X, Y, Z)
						else:
							item["XYZ_X"], item["XYZ_Y"], item["XYZ_Z"] = X, Y, Z
			else:
				if not primaries and check_missing_fields:
					raise ValueError(lang.getstr("error.testchart.missing_fields", 
												 (cgats.filename, ", ".join(labels))))
				ti1, ti3_ref = self.ti3_lookup_to_ti1(cgats, profile, fields,
													  intent, white_patches)
		except Exception, exception:
			if raise_exceptions:
				raise exception
			InfoDialog(self.owner, msg=safe_unicode(exception), 
					   ok=lang.getstr("ok"), bitmap=geticon(32, "dialog-error"))
		return ti1, ti3_ref, gray
	
	def ti1_lookup_to_ti3(self, ti1, profile, function="f", pcs=None,
						  intent="r", white_patches=4, white_patches_total=True):
		"""
		Read TI1 (filename or CGATS instance), lookup device->pcs values 
		colorimetrically through profile using Argyll's xicclu 
		utility and return TI3 (CGATS instance)
		
		"""
		
		# ti1
		if isinstance(ti1, basestring):
			ti1 = CGATS.CGATS(ti1)
		if not isinstance(ti1, CGATS.CGATS):
			raise TypeError('Wrong type for ti1, needs to be CGATS.CGATS '
							'instance')
		
		# profile
		if isinstance(profile, basestring):
			profile = ICCP.ICCProfile(profile)
		if not isinstance(profile, ICCP.ICCProfile):
			raise TypeError('Wrong type for profile, needs to be '
							'ICCP.ICCProfile instance')
		
		# determine pcs for lookup
		color_rep = profile.connectionColorSpace.upper()
		if color_rep == "RGB":
			pcs = None
		elif not pcs:
			if color_rep == 'LAB':
				pcs = 'l'
			elif color_rep == 'XYZ':
				pcs = 'x'
			else:
				raise ValueError('Unknown CIE color representation ' + color_rep)
		else:
			if pcs == "l":
				color_rep = "LAB"
			elif pcs == "x":
				color_rep = "XYZ"
		
		
		# get profile color space
		colorspace = profile.colorSpace
		
		# required fields for ti1
		if colorspace == "CMYK":
			required = ("CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K")
		else:
			required = ("RGB_R", "RGB_G", "RGB_B")
		ti1_filename = ti1.filename
		try:
			ti1 = verify_cgats(ti1, required, True)
		except CGATS.CGATSInvalidError:
			raise ValueError(lang.getstr("error.testchart.invalid", 
										 ti1_filename))
		except CGATS.CGATSKeyError:
			raise ValueError(lang.getstr("error.testchart.missing_fields", 
										 (ti1_filename, ", ".join(required))))
		
		# read device values from ti1
		data = ti1.queryv1("DATA")
		if not data:
			raise ValueError(lang.getstr("error.testchart.invalid", 
										 ti1_filename))
		device_data = data.queryv(required)
		if not device_data:
			raise ValueError(lang.getstr("error.testchart.missing_fields", 
										 (ti1_filename, ", ".join(required))))
		
		if colorspace == "RGB" and white_patches:
			# make sure the first four patches are white so the whitepoint can be
			# averaged
			white_rgb = {'RGB_R': 100, 'RGB_G': 100, 'RGB_B': 100}
			white = dict(white_rgb)
			wp = ti1.queryv1("APPROX_WHITE_POINT")
			if wp:
				wp = [float(v) for v in wp.split()]
				wp = [CGATS.rpad((v / wp[1]) * 100.0, data.vmaxlen) for v in wp]
			else:
				wp = colormath.get_standard_illuminant("D65", scale=100)
			for label in data.parent.DATA_FORMAT.values():
				if not label in white:
					if label.upper() == 'LAB_L':
						value = 100
					elif label.upper() in ('LAB_A', 'LAB_B'):
						value = 0
					elif label.upper() == 'XYZ_X':
						value = wp[0]
					elif label.upper() == 'XYZ_Y':
						value = 100
					elif label.upper() == 'XYZ_Z':
						value = wp[2]
					else:
						value = '0'
					white.update({label: value})
			white_added_count = 0
			if profile.profileClass != "link":
				if white_patches_total:
					# Ensure total of n white patches
					while len(data.queryi(white_rgb)) < white_patches:
						data.insert(0, white)
						white_added_count += 1
				else:
					# Add exactly n white patches
					while white_added_count < white_patches:
						data.insert(0, white)
						white_added_count += 1
				safe_print("Added %i white patch(es)" % white_added_count)
		
		idata = []
		for primaries in device_data.values():
			idata.append(primaries.values())
		
		if debug:
			safe_print("ti1_lookup_to_ti3 %s -> %s idata" % (profile.colorSpace,
														  color_rep))
			for v in idata:
				safe_print(" ".join(("%3.4f", ) * len(v)) % tuple(v))

		# lookup device->cie values through profile using (x)icclu
		if pcs or self.argyll_version >= [1, 6]:
			use_icclu = False
		else:
			# DeviceLink profile, we have to use icclu under older Argyll CMS
			# versions because older xicclu cannot handle devicelink
			use_icclu = True

		input_encoding = None
		output_encoding = None
		if not pcs:
			# Try to determine input/output encoding for devicelink
			if isinstance(profile.tags.get("meta"), ICCP.DictType):
				input_encoding = profile.tags.meta.getvalue("encoding.input")
				output_encoding = profile.tags.meta.getvalue("encoding.output")
				if input_encoding == "T":
					# 'T' (clip wtw on input) not supported for xicclu
					input_encoding = "t"
			# Fall back to configured 3D LUT encoding
			if (not input_encoding or input_encoding
				not in config.valid_values["3dlut.encoding.input"]):
				input_encoding = getcfg("3dlut.encoding.input")
				if input_encoding == "T":
					# 'T' (clip wtw on input) not supported for xicclu
					input_encoding = "t"
			if (not output_encoding or output_encoding
				not in config.valid_values["3dlut.encoding.output"]):
				output_encoding = getcfg("3dlut.encoding.output")
			if (self.argyll_version < [1, 6] and
				not (input_encoding == output_encoding == "n")):
				# Fail if encoding is not n (data levels)
				raise ValueError("The used version of Argyll CMS only"
								 "supports full range RGB encoding.")
			
		odata = self.xicclu(profile, idata, intent, function, pcs=pcs,
							scale=100, use_icclu=use_icclu,
							input_encoding=input_encoding,
							output_encoding=output_encoding)
		
		gray = []
		igray = []
		igray_idx = []
		if colorspace == "RGB":
			# treat r=g=b specially: set expected a=b=0
			for i, cie in enumerate(odata):
				r, g, b = idata[i]
				if r == g == b < 100:
					# if grayscale and not white
					if pcs == 'x':
						# Need to scale XYZ coming from xicclu
						# Lab is already scaled
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
						odata[i] = cie
			
		if igray and False:  # NEVER?
			# lookup cie->device values for grays through profile using xicclu
			gray = []
			ogray = self.xicclu(profile, igray, "r", "b", pcs="l", scale=100)
			for i, rgb in enumerate(ogray):
				cie = idata[i]
				if colormath.Lab2XYZ(cie[0], 0, 0)[1] * 100.0 >= 1:
					# only add if luminance is greater or equal 1% because 
					# dark tones fluctuate too much
					gray.append(rgb)
				# update values in ti1 and data for ti3
				for n, channel in enumerate(("R", "G", "B")):
					data[igray_idx[i] + 
						 white_added_count]["RGB_" + channel] = rgb[n]
				odata[igray_idx[i]] = cie

		# write output ti3
		ofile = StringIO()
		if pcs:
			ofile.write('CTI3   \n')
			ofile.write('\nDESCRIPTOR "Argyll Calibration Target chart information 3"\n')
		else:
			ofile.write('CTI1   \n')
			ofile.write('\nDESCRIPTOR "Argyll Calibration Target chart information 1"\n')
		ofile.write('KEYWORD "DEVICE_CLASS"\n')
		ofile.write('DEVICE_CLASS "' + ('DISPLAY' if colorspace == 'RGB' else 
										'OUTPUT') + '"\n')
		include_sample_name = False
		for i, cie in enumerate(odata):
			if i == 0:
				icolor = profile.colorSpace
				if icolor == 'RGB':
					olabel = 'RGB_R RGB_G RGB_B'
				elif icolor == 'CMYK':
					olabel = 'CMYK_C CMYK_M CMYK_Y CMYK_K'
				else:
					raise ValueError('Unknown color representation ' + icolor)
				if color_rep == 'LAB':
					ilabel = 'LAB_L LAB_A LAB_B'
				elif color_rep in ('XYZ', 'RGB'):
					ilabel = 'XYZ_X XYZ_Y XYZ_Z'
				else:
					raise ValueError('Unknown CIE color representation ' + color_rep)
				ofile.write('KEYWORD "COLOR_REP"\n')
				if icolor == color_rep:
					ofile.write('COLOR_REP "' + icolor + '"\n')
				else:
					ofile.write('COLOR_REP "' + icolor + '_' + color_rep + '"\n')
				
				ofile.write('\n')
				ofile.write('NUMBER_OF_FIELDS ')
				if include_sample_name:
					ofile.write(str(2 + len(icolor) + len(color_rep)) + '\n')
				else:
					ofile.write(str(1 + len(icolor) + len(color_rep)) + '\n')
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
			if pcs == 'x':
				# Need to scale XYZ coming from xicclu, Lab is already scaled
				cie = [round(n * 100.0, 5 - len(str(int(abs(n * 100.0))))) 
					   for n in cie]
			elif not pcs:
				# Actually CIE = RGB because Devicelink
				idata[i] = cie
				cie = [round(n * 100.0, 5 - len(str(int(abs(n * 100.0))))) 
					   for n in colormath.RGB2XYZ(*[n / 100.0 for n in cie])]
			device = [str(n) for n in idata[i]]
			cie = [str(n) for n in cie]
			if include_sample_name:
				ofile.write(str(i) + ' ' + data[i - 1][1].strip('"') + ' ' + 
							' '.join(device) + ' ' + ' '.join(cie) + '\n')
			else:
				ofile.write(str(i) + ' ' + ' '.join(device) + ' ' + 
							' '.join(cie) + '\n')
		ofile.write('END_DATA\n')
		ofile.seek(0)
		ti3 = CGATS.CGATS(ofile)[0]

		if (colorspace == "RGB" and white_patches and
			profile.profileClass == "link"):
			if white_patches_total:
				# Ensure total of n white patches
				while len(ti3.DATA.queryi(white_rgb)) < white_patches:
					ti3.DATA.insert(0, white)
					white_added_count += 1
			else:
				# Add exactly n white patches
				while white_added_count < white_patches:
					ti3.DATA.insert(0, white)
					white_added_count += 1
			safe_print("Added %i white patch(es)" % white_added_count)

		if debug:
			safe_print(ti3)
		return ti1, ti3, map(list, gray)
	
	def ti3_lookup_to_ti1(self, ti3, profile, fields=None, intent="r",
						  add_white_patches=4):
		"""
		Read TI3 (filename or CGATS instance), lookup cie->device values 
		colorimetrically through profile using Argyll's xicclu 
		utility and return TI1 and compatible TI3 (CGATS instances)
		
		"""
		
		# ti3
		copy = True
		if isinstance(ti3, basestring):
			copy = False
			ti3 = CGATS.CGATS(ti3)
		if not isinstance(ti3, CGATS.CGATS):
			raise TypeError('Wrong type for ti3, needs to be CGATS.CGATS '
							'instance')
		ti3_filename = ti3.filename
		if copy:
			# Make a copy and do not alter a passed in CGATS instance!
			ti3 = CGATS.CGATS(str(ti3))
		
		if fields == "XYZ":
			labels = ("XYZ_X", "XYZ_Y", "XYZ_Z")
		else:
			labels = ("LAB_L", "LAB_A", "LAB_B")
		
		try:
			ti3v = verify_cgats(ti3, labels, True)
		except CGATS.CGATSInvalidError, exception:
			raise ValueError(lang.getstr("error.testchart.invalid", 
										 ti3_filename) + "\n" +
										 lang.getstr(safe_str(exception)))
		except CGATS.CGATSKeyError:
			try:
				if fields:
					raise
				else:
					labels = ("XYZ_X", "XYZ_Y", "XYZ_Z")
				ti3v = verify_cgats(ti3, labels, True)
			except CGATS.CGATSKeyError:
				missing = ", ".join(labels)
				if not fields:
					missing += " " + lang.getstr("or") + " LAB_L, LAB_A, LAB_B"
				raise ValueError(lang.getstr("error.testchart.missing_fields", 
											 (ti3_filename, missing)))
			else:
				color_rep = 'XYZ'
		else:
			color_rep = fields or 'LAB'
		
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
			raise ValueError('Unknown CIE color representation ' + color_rep)

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
		if colorspace == "RGB" and add_white_patches:
			# make sure the first four patches are white so the whitepoint can be
			# averaged
			wp = [n * 100.0 for n in profile.tags.wtpt.values()]
			if color_rep == 'LAB':
				wp = colormath.XYZ2Lab(*wp)
				wp = OrderedDict((('L', wp[0]), ('a', wp[1]), ('b', wp[2])))
			else:
				wp = OrderedDict((('X', wp[0]), ('Y', wp[1]), ('Z', wp[2])))
			wp = [wp] * int(add_white_patches)
			safe_print("Added %i white patches" % add_white_patches)
		else:
			wp = []
		
		for cie in wp + cie_data.values():
			cie = cie.values()
			if color_rep == 'XYZ':
				# assume scale 0...100 in ti3, we need to convert to 0...1
				cie = [n / 100.0 for n in cie]
			idata.append(cie)
		
		if debug:
			safe_print("ti3_lookup_to_ti1 %s -> %s idata" % (color_rep,
														  profile.colorSpace))
			for v in idata:
				safe_print(" ".join(("%3.4f", ) * len(v)) % tuple(v))

		# lookup cie->device values through profile.icc using xicclu
		odata = self.xicclu(profile, idata, intent, "b", pcs=pcs, scale=100)
		
		# write output ti1/ti3
		ti1out = StringIO()
		ti1out.write('CTI1\n')
		ti1out.write('\n')
		ti1out.write('DESCRIPTOR "Argyll Calibration Target chart information 1"\n')
		include_sample_name = False
		for i, device in enumerate(odata):
			if i == 0:
				if color_rep == 'LAB':
					ilabel = 'LAB_L LAB_A LAB_B'
				elif color_rep == 'XYZ':
					ilabel = 'XYZ_X XYZ_Y XYZ_Z'
				else:
					raise ValueError('Unknown CIE color representation ' + color_rep)
				ocolor = profile.colorSpace.upper()
				if ocolor == 'RGB':
					olabel = 'RGB_R RGB_G RGB_B'
				elif ocolor == 'CMYK':
					olabel = 'CMYK_C CMYK_M CMYK_Y CMYK_K'
				else:
					raise ValueError('Unknown color representation ' + ocolor)
				olabels = olabel.split()
				# add device fields to DATA_FORMAT if not yet present
				if not olabels[0] in ti3v.DATA_FORMAT.values() and \
				   not olabels[1] in ti3v.DATA_FORMAT.values() and \
				   not olabels[2] in ti3v.DATA_FORMAT.values() and \
				   (ocolor == 'RGB' or (ocolor == 'CMYK' and 
				    not olabels[3] in ti3v.DATA_FORMAT.values())):
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
					ti1out.write(str(2 + len(color_rep) + len(ocolor)) + '\n')
				else:
					ti1out.write(str(1 + len(color_rep) + len(ocolor)) + '\n')
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
				if ocolor == 'RGB':
					device = [100.00, 100.00, 100.00]
				else:
					device = [0, 0, 0, 0]
			# Make sure device values do not exceed valid range of 0..100
			device = [str(max(0, min(v, 100))) for v in device]
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
					ti3v.DATA[i - len(wp)][v] = float(device[n])
				# set PCS values in ti3
				for n, v in enumerate(cie):
					ti3v.DATA[i - len(wp)][required[n]] = float(v)
		ti1out.write('END_DATA\n')
		ti1out.seek(0)
		ti1 = CGATS.CGATS(ti1out)
		if debug:
			safe_print(ti1)
		return ti1, ti3v

	def download(self, uri):
		try:
			response = urllib2.urlopen(uri)
		except urllib2.URLError, exception:
			return exception
		total_size = response.info().getheader("Content-Length")
		if total_size is not None:
			try:
				total_size = int(total_size)
			except (TypeError, ValueError):
				return Error(lang.getstr("download_fail_wrong_size",
										 ("<%s>" % lang.getstr("unknown"), ) * 2))
		uri = response.geturl()
		filename = os.path.basename(uri)
		contentdispo = response.info().getheader("Content-Disposition")
		if contentdispo:
			filename = re.search('filename="([^"]+)"', contentdispo)
			if filename:
				filename = filename.groups()[0]
		download_dir = os.path.join(expanduseru("~"), "Downloads")
		download_path = os.path.join(download_dir, filename)
		if (not os.path.isfile(download_path) or
			(total_size is not None and
			 os.stat(download_path).st_size != total_size)):
			self.recent.write(lang.getstr("downloading") + " " + filename + "\n")
			chunk_size = 8192
			bytes_so_far = 0
			bytes = []
			unit = "Bytes"
			unit_size = 1

			while True:
				if self.thread_abort:
					return False

				chunk = response.read(chunk_size)

				if not chunk:
					break

				bytes_so_far += len(chunk)

				bytes.append(chunk)

				if bytes_so_far > 1024 and unit_size < 1024:
					unit = "KiB"
					unit_size = 1024.0
				elif bytes_so_far > 1048576 and unit_size < 1048576:
					unit = "MiB"
					unit_size = 1048576.0

				if total_size:
					percent = float(bytes_so_far) / total_size
					percent = round(percent * 100, 2)
					self.lastmsg.write("\r%i%% (%.1f / %.1f %s)" %
									   (percent, bytes_so_far / unit_size,
										total_size / unit_size, unit))
				else:
					self.lastmsg.write("\r%.1f %s" % (bytes_so_far / unit_size,
													unit))

			response.close()
			if not bytes:
				return Error(lang.getstr("download_fail_empty_response", uri))
			if total_size is not None and bytes_so_far != total_size:
				return Error(lang.getstr("download_fail_wrong_size",
										 (total_size, bytes_so_far)))
			if not os.path.isdir(download_dir):
				os.makedirs(download_dir)
			with open(download_path, "wb") as download_file:
				download_file.write("".join(bytes))
		return download_path

	def process_argyll_download(self, result, exit=False):
		if isinstance(result, Exception):
			show_result_dialog(result, self.owner)
		elif result:
			if (result.lower().endswith(".zip") or
				result.lower().endswith(".tgz")):
				self.start(self.set_argyll_bin, self.extract_archive,
						   cargs=(result, ), wargs=(result, ),
						   progress_msg=lang.getstr("please_wait"),
						   fancy=False)
			else:
				show_result_dialog(lang.getstr("error.file_type_unsupported") +
								   "\n" + result, self.owner)
	def extract_archive(self, filename):
		extracted = []
		if filename.lower().endswith(".zip"):
			cls = zipfile.ZipFile
			mode = "r"
		elif filename.lower().endswith(".tgz"):
			cls = TarFileProper.open  # classmethod
			mode = "r:gz"
		else:
			return extracted
		with cls(filename, mode) as z:
			outdir = os.path.realpath(os.path.dirname(filename))
			if cls is not zipfile.ZipFile:
				method = z.getnames
			else:
				method = z.namelist
			names = method()
			names.sort()
			extracted = [os.path.join(outdir, os.path.normpath(name))
						 for name in names]
			if names:
				name0 = os.path.normpath(names[0])
			for outpath in extracted:
				if not os.path.realpath(outpath).startswith(os.path.join(outdir,
																		 name0)):
					return Error(lang.getstr("file.invalid") + "\n" +
								 filename)
			if cls is not zipfile.ZipFile:
				z.extractall(outdir)
			else:
				for name in names:
					# If the ZIP file was created with Unicode names stored
					# in the file, 'name' will already be Unicode.
					# Otherwise, it'll either be 7-bit ASCII or (legacy)
					# cp437 encoding
					outname = safe_unicode(name, "cp437")
					outpath = os.path.join(outdir, os.path.normpath(outname))
					if outname.endswith("/"):
						if not os.path.isdir(outpath):
							os.makedirs(outpath)
					elif not os.path.isfile(outpath):
						with open(outpath, "wb") as outfile:
							outfile.write(z.read(name))
		return extracted

	def set_argyll_bin(self, result, filename):
		if isinstance(result, Exception):
			show_result_dialog(result, self.owner)
		elif result and os.path.isdir(result[0]):
			setcfg("argyll.dir",
				   os.path.join(result[0], "bin"))
			from DisplayCAL import check_donation
			snapshot = VERSION > VERSION_BASE
			self.owner.set_argyll_bin_handler(None, True,
											  self.owner.check_instrument_setup,
											  (check_donation, (self.owner,
																snapshot)))
		else:
			show_result_dialog(lang.getstr("error.no_files_extracted_from_archive",
										   filename), self.owner)

	def process_download(self, result, exit=False):
		if isinstance(result, Exception):
			show_result_dialog(result, self.owner)
		elif result:
			if exit:
				if self.owner:
					self.owner.Close()
				else:
					wx.GetApp().ExitMainLoop()
			launch_file(result)

	def verify_calibration(self):
		""" Verify the current calibration """
		cmd, args = self.prepare_dispcal(calibrate=False, verify=True)
		if not isinstance(cmd, Exception):
			result = self.exec_cmd(cmd, args, capture_output=True, 
										  skip_scripts=True)
		else:
			result = cmd
		return result

	def measure_ti1(self, ti1_path, cal_path=None, colormanaged=False):
		""" Measure a TI1 testchart file """
		if config.get_display_name() == "Untethered":
			cmd, args = get_argyll_util("spotread"), ["-v", "-e"]
			if getcfg("extra_args.spotread").strip():
				args += parse_argument_string(getcfg("extra_args.spotread"))
			result = self.set_terminal_cgats(ti1_path)
			if isinstance(result, Exception):
				return result
		else:
			cmd = get_argyll_util("dispread")
			args = ["-v"]
			if config.get_display_name() in ("madVR", "Prisma") and colormanaged:
				args.append("-V")
			if cal_path:
				if (self.argyll_version >= [1, 3, 3] and
					(not self.has_lut_access() or
					 not getcfg("calibration.use_video_lut"))):
					args.append("-K")
				else:
					args.append("-k")
				args.append(cal_path)
			if getcfg("extra_args.dispread").strip():
				args += parse_argument_string(getcfg("extra_args.dispread"))
		result = self.add_measurement_features(args,
											   cmd == get_argyll_util("dispread"),
											   allow_nondefault_observer=is_ccxx_testchart())
		if isinstance(result, Exception):
			return result
		self.options_dispread = list(args)
		if config.get_display_name() != "Untethered":
			args.append(os.path.splitext(ti1_path)[0])
		return self.exec_cmd(cmd, args, skip_scripts=True)

	def wrapup(self, copy=True, remove=True, dst_path=None, ext_filter=None):
		"""
		Wrap up - copy and/or clean temporary file(s).
		
		"""
		if debug: safe_print("[D] wrapup(copy=%s, remove=%s)" % (copy, remove))
		if not self.tempdir or not os.path.isdir(self.tempdir):
			return # nothing to do
		if (isinstance(copy, Exception) and
			not isinstance(copy, (UnloggedError, UnloggedInfo,
								  UnloggedWarning)) and self.sessionlogfile):
			# This is an incomplete run, log exception to session logfile
			self.sessionlogfile.write(safe_basestring(copy))
		while self.sessionlogfiles:
			self.sessionlogfiles.popitem()[1].close()
		if isinstance(copy, Exception):
			# This is an incomplete run, check if any files have been added or
			# modified (except log files and 'hidden' temporary files)
			changes = False
			for filename in os.listdir(self.tempdir):
				if (filename.endswith(".log") or
					filename in (".abort", ".ok", ".wait", ".wait.cmd",
								 ".wait.py")):
					# Skip log files and 'hidden' temporary files
					continue
				if (filename not in self.tmpfiles or
					os.stat(os.path.join(self.tempdir, filename)).st_mtime !=
					self.tmpfiles[filename]):
					changes = True
					break
			if not changes:
				copy = False
		result = True
		if copy:
			try:
				src_listdir = os.listdir(self.tempdir)
			except Exception, exception:
				result = exception
				remove = False
			if not isinstance(result, Exception) and src_listdir:
				if not ext_filter:
					ext_filter = [".app", ".cal", ".ccmx", ".ccss", ".cmd", 
								  ".command", ".gam", ".gz", ".icc", ".icm", ".log",
								  ".png", ".sh", ".ti1", ".ti3", ".wrl", ".wrz"]
				save_path = getcfg("profile.save_path")
				if dst_path is None:
					dst_path = os.path.join(save_path, 
											getcfg("profile.name.expanded"), 
											getcfg("profile.name.expanded") + 
											".ext")
				if isinstance(copy, Exception):
					# This is an incomplete run
					parts = os.path.normpath(dst_path).split(os.sep)
					# DON'T use os.path.join due to how it works under Windows:
					# os.path.join("c:", "foo") represents a path relative to
					# the current directory on drive C: (c:foo), not c:\foo.
					if os.sep.join(parts[:-2]) == os.path.normpath(save_path):
						# If storage directory, save incomplete runs to
						# different directory
						parts = [config.datahome, "incomplete"] + parts[-2:]
						dst_path = os.sep.join(parts)
				result = check_create_dir(os.path.dirname(dst_path))
				if isinstance(result, Exception):
					remove = False
				else:
					if isinstance(copy, Exception):
						safe_print("Moving files of incomplete run to",
								   os.path.dirname(dst_path))
					for basename in src_listdir:
						name, ext = os.path.splitext(basename)
						if ext_filter is None or ext.lower() in ext_filter:
							src = os.path.join(self.tempdir, basename)
							dst = os.path.join(os.path.dirname(dst_path), basename)
							if sys.platform == "win32":
								dst = make_win32_compatible_long_path(dst)
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
									try:
										shutil.copyfile(src, dst)
									except Exception, exception:
										result = Error(lang.getstr("error.copy_failed",
																   (src, dst)))
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
								safe_print(u"Warning - temporary file "
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
		if isinstance(result, Exception):
			result = Error(safe_unicode(result) + "\n\n" +
						   lang.getstr("tempdir_should_still_contain_files",
									   self.tempdir))
		return result
	
	def write(self, txt):
		if True:
			# Don't buffer
			self._write(txt)
			return
		# NEVER - Use line buffer
		self.buffer.append(txt)
		self.buffer = [line for line in StringIO("".join(self.buffer))]
		for line in self.buffer:
			if not (line.endswith("\n") or line.rstrip().endswith(":") or
					line.rstrip().endswith(",") or line.rstrip().endswith(".")):
				break
			self._write(line)
			self.buffer = self.buffer[1:]

	def _write(self, txt):
		if re.search("press 1|space when done|patch 1 of ", txt, re.I):
			# There are some intial measurements which we can't check for
			# unless -D (debug) is used for Argyll tools
			if not "patch 1 of " in txt.lower() or not self.patch_sequence:
				if "patch 1 of " in txt.lower():
					self.patch_sequence = True
				self.patch_count = 0
				self.patterngenerator_sent_count = 0
		update = re.search(r"[/\\] current|patch \d+ of |the instrument "
						   "can be removed from the screen", txt, re.I)
		# Send colors to pattern generator
		use_patterngenerator = (self.use_patterngenerator and
								self.patterngenerator and
								hasattr(self.patterngenerator, "conn"))
		if use_patterngenerator or self.use_madnet_tpg:
			rgb = re.search(r"Current RGB(?:\s+\d+){3}((?:\s+\d+(?:\.\d+)){3})",
							txt)
			if rgb:
				rgb = [float(v) for v in rgb.groups()[0].strip().split()]
				if self.use_madnet_tpg:
					if self.madtpg.show_rgb(*rgb):
						self.patterngenerator_sent_count += 1
						self.log("%s: MadTPG_Net sent count: %i" %
								 (appname, self.patterngenerator_sent_count))
					else:
						self.exec_cmd_returnvalue = Error(lang.getstr("patterngenerator.sync_lost"))
						self.abort_subprocess()
				else:
					self.patterngenerator_send(rgb)
				# Create .ok file which will be picked up by .wait script
				okfilename = os.path.join(self.tempdir, ".ok")
				open(okfilename, "w").close()
			if update:
				# Check if patch count is higher than patterngenerator sent count
				if (self.patch_count > self.patterngenerator_sent_count and
					self.exec_cmd_returnvalue is None):
					# This should never happen
					self.exec_cmd_returnvalue = Error(lang.getstr("patterngenerator.sync_lost"))
					self.abort_subprocess()
		if update and not (self.subprocess_abort or self.thread_abort or
						   "the instrument can be removed from the screen"
						   in txt.lower()):
			self.patch_count += 1
			if use_patterngenerator or self.use_madnet_tpg:
				self.log("%s: Argyll CMS patch update count: %i" %
						 (appname, self.patch_count))
			if self.use_madnet_tpg and re.match("Patch \\d+ of \\d+", txt, re.I):
				# Set madTPG progress bar
				components = txt.split()
				try:
					start = int(components[1])
					end = int(components[3])
				except ValueError:
					pass
				else:
					self.madtpg.set_progress_bar_pos(start, end)
		# Parse
		wx.CallAfter(self.parse, txt)
	
	def xicclu(self, profile, idata, intent="r", direction="f", order="n",
			   pcs=None, scale=1, cwd=None, startupinfo=None, raw=False,
			   logfile=None, use_icclu=False, use_cam_clipping=False,
			   get_clip=False, show_actual_if_clipped=False,
			   input_encoding=None, output_encoding=None):
		"""
		Call xicclu, feed input floats into stdin, return output floats.
		
		input data needs to be a list of 3-tuples (or lists) with floats,
		alternatively a list of strings.
		output data will be returned in same format, or as list of strings
		if 'raw' is true.
		
		"""
		with Xicclu(profile, intent, direction, order, pcs, scale, cwd,
					startupinfo, use_icclu, use_cam_clipping, logfile,
					self, show_actual_if_clipped, input_encoding,
					output_encoding) as xicclu:
			xicclu(idata)
		return xicclu.get(raw, get_clip)


class Xicclu(Worker):
	def __init__(self, profile, intent="r", direction="f", order="n",
				 pcs=None, scale=1, cwd=None, startupinfo=None, use_icclu=False,
				 use_cam_clipping=False, logfile=None, worker=None,
				 show_actual_if_clipped=False, input_encoding=None,
				 output_encoding=None):
		Worker.__init__(self)
		self.logfile = logfile
		self.worker = worker
		self.temp = False
		utilname = "icclu" if use_icclu else "xicclu"
		xicclu = get_argyll_util(utilname)
		if not xicclu:
			raise Error(lang.getstr("argyll.util.not_found", utilname))
		if not isinstance(profile, (CGATS.CGATS, ICCP.ICCProfile)):
			if profile.lower().endswith(".cal"):
				profile = CGATS.CGATS(profile)
			else:
				profile = ICCP.ICCProfile(profile)
		is_profile = isinstance(profile, ICCP.ICCProfile)
		if not profile.fileName or not os.path.isfile(profile.fileName):
			if not cwd:
				cwd = self.create_tempdir()
				if isinstance(cwd, Exception):
					raise cwd
			fd, profile.fileName = tempfile.mkstemp(profile_ext, dir=cwd)
			stream = os.fdopen(fd, "wb")
			profile.write(stream)
			stream.close()
			self.temp = True
		elif not cwd:
			cwd = os.path.dirname(profile.fileName)
		profile_basename = safe_unicode(os.path.basename(profile.fileName))
		profile_path = profile.fileName
		if sys.platform == "win32":
			profile_path = win32api.GetShortPathName(profile_path)
		self.profile_path = safe_str(profile_path)
		if sys.platform == "win32" and not startupinfo:
			startupinfo = sp.STARTUPINFO()
			startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
			startupinfo.wShowWindow = sp.SW_HIDE
		xicclu = safe_str(xicclu)
		cwd = safe_str(cwd)
		args = [xicclu, "-s%s" % scale]
		if utilname == "xicclu":
			if (is_profile and
				show_actual_if_clipped and "A2B0" in profile.tags and
				("B2A0" in profile.tags or direction == "if")):
				args.append("-a")
			if use_cam_clipping:
				args.append("-b")
			if get_argyll_version("xicclu") >= [1, 6]:
				# Add encoding parameters
				# Note: Not adding -e -E can cause problems due to unitialized
				# in_tvenc and out_tvenc variables in xicclu.c for Argyll 1.6.x
				if not input_encoding:
					input_encoding = "n"
				if not output_encoding:
					output_encoding = "n"
				args += ["-e" + input_encoding, "-E" + output_encoding]
		args.append("-f" + direction)
		if is_profile:
			if profile.profileClass not in ("abst", "link"):
				args.append("-i" + intent)
				if order != "n":
					args.append("-o" + order)
			if pcs and profile.profileClass != "link":
				args.append("-p" + pcs)
		args.append(self.profile_path)
		if debug or verbose > 1:
			self.sessionlogfile = LogFile(profile_basename + ".xicclu",
										  os.path.dirname(profile.fileName))
			if is_profile:
				profile_act = ICCP.ICCProfile(profile.fileName)
				self.sessionlogfile.write("Profile ID %s (actual %s)" %
										  (hexlify(profile.ID),
										   hexlify(profile_act.calculateID(False))))
			if cwd:
				self.log(lang.getstr("working_dir"))
				indent = "  "
				for name in cwd.split(os.path.sep):
					self.log(textwrap.fill(name + os.path.sep, 80, 
										   expand_tabs=False, 
										   replace_whitespace=False, 
										   initial_indent=indent, 
										   subsequent_indent=indent))
					indent += " "
				self.log("")
			self.log(lang.getstr("commandline"))
			printcmdline(xicclu if debug or verbose > 2 else
						 os.path.basename(xicclu), args[1:], fn=self.log,
						 cwd=cwd)
			self.log("")
		self.stdout = tempfile.SpooledTemporaryFile()
		self.stderr = tempfile.SpooledTemporaryFile()
		self.subprocess = sp.Popen(args, stdin=sp.PIPE, stdout=self.stdout,
								   stderr=self.stderr, cwd=cwd,
								   startupinfo=startupinfo)
	
	def __call__(self, idata):
		if not isinstance(idata, basestring):
			idata = list(idata)  # Make a copy
			for i, v in enumerate(idata):
				if isinstance(v, (float, int, long)):
					self([idata])
					return
				if not isinstance(v, basestring):
					for n in v:
						if not isinstance(n, (float, int, long)):
							raise TypeError("xicclu: Expecting list of "
											"strings or n-tuples with "
											"floats")
					idata[i] = " ".join([str(n) for n in v])
		else:
			idata = idata.splitlines()
		numrows = len(idata)
		chunklen = 1000
		i = 0
		p = self.subprocess
		while True:
			# Process in chunks to prevent broken pipe if input data is too
			# large
			if self.subprocess_abort or self.thread_abort:
				if p.poll() is None:
					p.stdin.write("\n")
					p.stdin.close()
					p.wait()
				raise Info(lang.getstr("aborted"))
			if p.poll() is None:
				# We don't use communicate() because it will end the
				# process
				p.stdin.write("\n".join(idata[chunklen * i:
											  chunklen * (i + 1)]) + "\n")
				p.stdin.flush()
			else:
				# Error
				break
			if self.logfile:
				self.logfile.write("\r%i%%" % min(round(chunklen * (i + 1) /
												   float(numrows) * 100),
											 100))
			if chunklen * (i + 1) > numrows - 1:
				break
			i += 1
	
	def __enter__(self):
		return self
	
	def __exit__(self, etype=None, value=None, tb=None):
		self.exit()
		if tb:
			return False
	
	def exit(self):
		p = self.subprocess
		if p.poll() is None:
			try:
				p.stdin.write("\n")
			except IOError:
				pass
			p.stdin.close()
		p.wait()
		self.stdout.seek(0)
		self.output = self.stdout.readlines()
		self.stdout.close()
		self.stderr.seek(0)
		self.errors = self.stderr.readlines()
		self.stderr.close()
		if self.sessionlogfile and self.errors:
			self.sessionlogfile.write("\n".join(self.errors))
		if p.returncode:
			# Error
			raise IOError("\n".join(self.errors))
		if self.logfile:
			self.logfile.write("\n")
		if self.temp:
			os.remove(self.profile_path)
			if self.tempdir and not os.listdir(self.tempdir):
				self.wrapup(False)
	
	def get(self, raw=False, get_clip=False):
		if raw:
			if self.sessionlogfile:
				self.sessionlogfile.write("\n".join(self.output))
				self.sessionlogfile.close()
			return self.output
		parsed = []
		j = 0
		for i, line in enumerate(self.output):
			line = line.strip()
			if line.startswith("["):
				if self.sessionlogfile:
					self.sessionlogfile.write(line)
				continue
			elif not "->" in line:
				if self.sessionlogfile and line:
					self.sessionlogfile.write(line)
				continue
			elif self.sessionlogfile:
				self.sessionlogfile.write("#%i %s" % (j, line))
			parts = line.split("->")[-1].strip().split()
			clip = parts.pop() == "(clip)"
			if clip:
				parts.pop()
			parsed.append([float(n) for n in parts])
			if get_clip:
				parsed[-1].append(clip)
			j += 1
		if self.sessionlogfile:
			self.sessionlogfile.close()
		return parsed
	
	@Property
	def subprocess_abort():
		def fget(self):
			if self.worker:
				return self.worker.subprocess_abort
			return False
		
		def fset(self, v):
			pass
		
		return locals()
	
	@Property
	def thread_abort():
		def fget(self):
			if self.worker:
				return self.worker.thread_abort
			return False
		
		def fset(self, v):
			pass
		
		return locals()
