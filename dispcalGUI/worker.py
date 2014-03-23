# -*- coding: utf-8 -*-

# stdlib
from __future__ import with_statement
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
	from platform import mac_ver
	from thread import start_new_thread
elif sys.platform == "win32":
	from ctypes import windll
	from win32com.shell import shell
	import pythoncom
	import win32con

# 3rd party
if sys.platform == "win32":
	import win32api
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
import colormath
import config
import defaultpaths
import localization as lang
import wexpect
from argyll_cgats import (add_dispcal_options_to_cal, add_options_to_ti3,
						  extract_fix_copy_cal, ti3_to_ti1, vcgt_to_cal,
						  verify_cgats)
from argyll_instruments import (get_canonical_instrument_name,
								instruments as all_instruments)
from argyll_names import (names as argyll_names, altnames as argyll_altnames, 
						  optional as argyll_optional, viewconds, intents)
from config import (autostart, autostart_home, script_ext, defaults, enc, exe,
					exe_ext, fs_enc, getcfg, geticon,
					get_data_path, get_verified_path, isapp, isexe,
					is_ccxx_testchart, profile_ext, pydir, setcfg, writecfg)
if sys.platform not in ("darwin", "win32"):
	from defaultpaths import iccprofiles_home, iccprofiles_display_home
from edid import WMIError, get_edid
from log import DummyLogger, LogFile, get_file_logger, log, safe_print
from meta import name as appname, version
from options import debug, test, test_require_sensor_cal, verbose
from ordereddict import OrderedDict
from trash import trash
from util_io import Files, GzipFileProper, StringIOu as StringIO
from util_list import intlist
if sys.platform == "darwin":
	from util_mac import (mac_app_activate, mac_terminal_do_script, 
						  mac_terminal_set_colors, osascript)
elif sys.platform == "win32":
	import util_win
import colord
from util_os import getenvu, is_superuser, putenvu, quote_args, which
from util_str import safe_str, safe_unicode
from wxaddons import wx
from wxwindows import ConfirmDialog, InfoDialog, ProgressDialog, SimpleTerminal
from wxDisplayAdjustmentFrame import DisplayAdjustmentFrame
from wxDisplayUniformityFrame import DisplayUniformityFrame
from wxUntetheredFrame import UntetheredFrame
import wx.lib.delayedresult as delayedresult

INST_CAL_MSGS = ["Do a reflective white calibration",
				 "Do a transmissive white calibration",
				 "Do a transmissive dark calibration",
				 "Place the instrument on its reflective white reference",
				 "Click the instrument on its reflective white reference",
				 "Place the instrument in the dark",
				 "Place cap on the instrument",  # i1 Pro
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


def Property(func):
	return property(**func())


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
	argyll_dir = os.path.dirname(cur_dir)
	if (os.path.isdir(os.path.join(argyll_dir, "ref")) and
		not argyll_dir in config.data_dirs):
		config.data_dirs.append(argyll_dir)
	config.defaults["3dlut.input.profile"] = get_data_path(os.path.join("ref",
																		"Rec709.icm")) or ""
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
	return exe


def get_argyll_utilname(name, paths=None):
	""" Find a single Argyll utility. Return the basename without extension. """
	exe = get_argyll_util(name, paths)
	if exe:
		exe = os.path.basename(os.path.splitext(exe)[0])
	return exe


def get_argyll_version(name, silent=False):
	"""
	Determine version of a certain Argyll utility.
	
	"""
	argyll_version_string = get_argyll_version_string(name, silent)
	return parse_argyll_version_string(argyll_version_string)


def get_argyll_version_string(name, silent=False):
	argyll_version_string = "0.0.0"
	if (silent and check_argyll_bin()) or (not silent and 
										   check_set_argyll_bin()):
		cmd = get_argyll_util(name)
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
				if i == 0 and "version" in line.lower():
					argyll_version_string = line[line.lower().find("version")+8:]
					break
	return argyll_version_string


def get_current_profile_path():
	profile = None
	profile_path = getcfg("calibration.file")
	if profile_path:
		try:
			profile = ICCP.ICCProfile(profile_path)
		except Exception, exception:
			return
	else:
		try:
			profile = ICCP.get_display_profile(getcfg("display.number") - 1)
		except Exception, exception:
			return
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
		"YA"  # Argyll >= 1.5.0 disable adaptive mode
	]
	re_options_colprof = [
		"q[lmh]",
		"b[lmh]",  # B2A quality
		"a(?:%s)" % "|".join(config.valid_values["profile.type"]),
		'[sSMA]\s+["\'][^"\']+?["\']',
		"[cd](?:%s)" % "|".join(viewconds),
		"[tT](?:%s)" % "|".join(intents)
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
	""" Try and get options from TI3 file by looking for the special
	dispcalGUI sections 'ARGYLL_DISPCAL_ARGS' and 'ARGYLL_COLPROF_ARGS'. """
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


def get_arg(argmatch, args):
	""" Return first found entry beginning with the argmatch string or None """
	for arg in args:
		if arg.startswith(argmatch):
			return arg


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
		item = quote_args([item])[0]
		lines.append(item)
		i += 1
	for line in lines:
		fn(textwrap.fill(line, 80, expand_tabs = False, 
				   replace_whitespace = False, initial_indent = "    ", 
				   subsequent_indent = "      "))


def set_argyll_bin(parent=None):
	""" Set the directory containing the Argyll CMS binary executables """
	if parent and not parent.IsShownOnScreen():
		parent = None # do not center on parent if not visible
	defaultPath = os.path.join(*get_verified_path("argyll.dir"))
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
	return result


def show_result_dialog(result, parent=None, pos=None):
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
	InfoDialog(parent, pos=pos, msg=msg, ok=lang.getstr("ok"), bitmap=bitmap, 
			   log=not isinstance(result, (UnloggedError, UnloggedInfo,
										   UnloggedWarning)))


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


class FilteredStream():
	
	""" Wrap a stream and filter all lines written to it. """
	
	# Discard progress information like ... or *** or %
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
	
	substitutions = {" peqDE ": " DE to previous pass ",
					 r"\^\[": "",  # ESC key on Linux/OSX
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
			self.data_encoding = aliases.get(str(windll.kernel32.GetACP()), 
											 "ascii")
		else:
			self.data_encoding = enc
		self.cmdrun = False
		self.dispcal_create_fast_matrix_shaper = False
		self.dispread_after_dispcal = False
		self.finished = True
		self.interactive = False
		self.lastcmdname = None
		self.lastmsg_discard = re.compile("[\\*\\.]+")
		self.options_colprof = []
		self.options_dispcal = []
		self.options_dispread = []
		self.options_targen = []
		self.recent_discard = re.compile("^\\s*(?:Adjusted )?(Current|[Tt]arget) (?:Brightness|50% Level|white|(?:Near )?[Bb]lack|(?:advertised )?gamma) .+|^Gamma curve .+|^Display adjustment menu:|^Press|^\\d\\).+|^(?:1%|Black|Red|Green|Blue|White)\\s+=.+|^\\s*patch \\d+ of \\d+.*|^\\s*point \\d+.*|^\\s*Added \\d+/\\d+|[\\*\\.]+|\\s*\\d*%?", re.I)
		self.subprocess_abort = False
		self.sudo_availoptions = None
		self.auth_timestamp = 0
		self.sessionlogfiles = {}
		self.tempdir = None
		self.thread_abort = False
		self.triggers = []
		self.clear_argyll_info()
		self.clear_cmd_output()
		self._progress_wnd = None
		self._pwdstr = ""
	
	def add_measurement_features(self, args, display=True):
		""" Add common options and to dispcal, dispread and spotread arguments """
		if display and not get_arg("-d", args):
			args += ["-d" + self.get_display()]
		if not get_arg("-c", args):
			args += ["-c%s" % getcfg("comport.number")]
		measurement_mode = getcfg("measurement_mode")
		instrument_features = self.get_instrument_features()
		if (measurement_mode and (measurement_mode != "p" or
								  self.get_instrument_name() == "ColorHug") and
			not get_arg("-y", args)):
				# Always specify -y for colorimeters (won't be read from .cal 
				# when updating)
				# Only ColorHug supports -yp parameter
				if self.argyll_version >= [1, 5, 0]:
					measurement_mode_map = instrument_features.get("measurement_mode_map",
																   {})
					measurement_mode = measurement_mode_map.get(measurement_mode[0],
																measurement_mode)
				args += ["-y" + measurement_mode[0]]
		if getcfg("measurement_mode.projector") and \
		   instrument_features.get("projector_mode") and \
		   self.argyll_version >= [1, 1, 0] and not get_arg("-p", args):
			# Projector mode, Argyll >= 1.1.0 Beta
			args += ["-p"]
		if instrument_features.get("adaptive_mode"):
			if getcfg("measurement_mode.adaptive"):
				if ((self.argyll_version[0:3] > [1, 1, 0] or
					 (self.argyll_version[0:3] == [1, 1, 0] and
					  not "Beta" in self.argyll_version_string and
					  not "RC1" in self.argyll_version_string and
					  not "RC2" in self.argyll_version_string)) and
					 self.argyll_version[0:3] < [1, 5, 0] and
					 not get_arg("-V", args)):
					# Adaptive measurement mode, Argyll >= 1.1.0 RC3
					args += ["-V"]
			else:
				if self.argyll_version[0:3] >= [1, 5, 0]:
					# Disable adaptive measurement mode
					args += ["-YA"]
		if display and not (get_arg("-dweb", args) or get_arg("-dmadvr", args)):
			if ((self.argyll_version <= [1, 0, 4] and not get_arg("-p", args)) or 
				(self.argyll_version > [1, 0, 4] and not get_arg("-P", args))):
				args += [("-p" if self.argyll_version <= [1, 0, 4] else "-P") + 
						 getcfg("dimensions.measureframe")]
			if getcfg("measure.darken_background") and not get_arg("-F", args):
				args += ["-F"]
		if getcfg("measurement_mode.highres") and \
		   instrument_features.get("highres_mode") and not get_arg("-H", args):
			args += ["-H"]
		if (self.instrument_can_use_ccxx() and
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
					safe_print("%s:" % ccmx, exception)
					instrument = None
				else:
					instrument = get_canonical_instrument_name(str(cgats.queryv1("INSTRUMENT") or "").replace("eye-one display", "i1 Display"))
				if ((instrument and
					 self.get_instrument_name().lower().replace(" ", "") in
					 instrument.lower().replace(" ", "")) or
					ccmx.lower().endswith(".ccss")):
					tempdir = self.create_tempdir()
					if isinstance(tempdir, Exception):
						return tempdir
					ccmxcopy = os.path.join(tempdir, 
											os.path.basename(ccmx))
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
					args += ["-X"]
					args += [os.path.basename(ccmxcopy)]
		if (display and (getcfg("drift_compensation.blacklevel") or 
						 getcfg("drift_compensation.whitelevel")) and
			self.argyll_version >= [1, 3, 0] and not get_arg("-I", args)):
			args += ["-I"]
			if getcfg("drift_compensation.blacklevel"):
				args[-1] += "b"
			if getcfg("drift_compensation.whitelevel"):
				args[-1] += "w"
		# TTBD/FIXME: Skipping of sensor calibration can't be done in
		# emissive mode (see Argyll source spectro/ss.c, around line 40)
		if (getcfg("allow_skip_sensor_cal") and
			instrument_features.get("skip_sensor_cal") and
			self.argyll_version >= [1, 1, 0] and not get_arg("-N", args)):
			args += ["-N"]
		return True
	
	def instrument_can_use_ccxx(self):
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
		# Spyder 4 (only generic LCD and refresh measurement modes)
		return (self.argyll_version >= [1, 3, 0] and
				not self.get_instrument_features().get("spectral") and
				(self.get_instrument_name() != "ColorHug" or
				 getcfg("measurement_mode") in ("F", "R")) and
				(self.get_instrument_name() != "ColorMunki Smile" or
				 getcfg("measurement_mode") == "f") and
				(self.get_instrument_name() != "Colorimtre HCFR" or  # Missing é is NOT a typo
				 getcfg("measurement_mode") == "R") and
				(self.get_instrument_name() != "DTP94" or
				 getcfg("measurement_mode") in ("l", "c", "g")) and
				(self.get_instrument_name() != "Spyder4" or
				 getcfg("measurement_mode") in ("l", "c")))
	
	@Property
	def progress_wnd():
		def fget(self):
			if not self._progress_wnd:
				if (getattr(self, "progress_start_timer", None) and
					self.progress_start_timer.IsRunning()):
					# Instantiate the progress dialog instantly on access
					self.progress_start_timer.Notify()
					self.progress_start_timer.Stop()
			return self._progress_wnd
		
		def fset(self, progress_wnd):
			self._progress_wnd = progress_wnd
		
		return locals()
	
	@Property
	def pwd():
		def fget(self):
			return self._pwdstr[10:].ljust(int(math.ceil(len(self._pwdstr[10:]) / 4.0) * 4),
										  "=").decode("base64").decode("UTF-8")
		
		def fset(self, pwd):
			self._pwdstr = "/tmp/%s%s" % (md5(getpass.getuser()).hexdigest().encode("base64")[:5],
										  pwd.encode("UTF-8").encode("base64").rstrip("=\n"))
		
		return locals()
	
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
						self.do_instrument_calibration()
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
				start_new_thread(mac_app_activate, (1, appname if isapp 
													else "Python"))
			if (self.instrument_calibration_complete or
				((config.get_display_name() == "Web" or
				  getcfg("measure.darken_background")) and
				 (not self.dispread_after_dispcal or
				  self.cmdname == "dispcal"))):
				# Show a dialog asking user to place the instrument on the
				# screen if the instrument calibration was completed,
				# or if we measure a remote ("Web") display,
				# or if we use a black background during measurements,
				# but in case of the latter two only if dispread is not
				# run directly after dispcal
				self.instrument_calibration_complete = False
				self.instrument_place_on_screen()
			else:
				if self.subprocess.isalive():
					if debug or test:
						safe_print('Sending SPACE key')
					self.safe_send(" ")
	
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
		if (self.cmdname == "spotread" and
			self.progress_wnd is not getattr(self, "terminal", None) and
			"Result is XYZ:" in txt):
			# Single spotread reading, we are done
			wx.CallLater(1000, self.quit_terminate_cmd)
	
	def do_instrument_calibration(self):
		""" Ask user to initiate sensor calibration and execute.
		Give an option to cancel. """
		if getattr(self, "subprocess_abort", False) or \
		   getattr(self, "thread_abort", False):
			# If we are aborting, ignore request
			return
		self.progress_wnd.Pulse(" " * 4)
		if self.get_instrument_name() == "ColorMunki":
			lstr ="instrument.calibrate.colormunki"
		else:
			lstr = "instrument.calibrate"
		dlg = ConfirmDialog(self.progress_wnd, msg=lang.getstr(lstr), 
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
		if debug or test:
			safe_print('Sending SPACE key')
		if self.safe_send(" "):
			self.progress_wnd.Pulse(lang.getstr("instrument.calibrating"))
	
	def abort_subprocess(self, confirm=False):
		""" Abort the current subprocess or thread """
		if confirm and getattr(self, "progress_wnd", None):
			if getattr(self.progress_wnd, "dlg", None):
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
			dlg.Destroy()
			if self.finished:
				return
			if dlg_result != wx.ID_OK:
				self.progress_wnd.Resume()
				if pause:
					self.progress_wnd.pause_continue_handler()
				return
		self.subprocess_abort = True
		self.thread_abort = True
		delayedresult.startWorker(lambda result: None, 
								  self.quit_terminate_cmd)
	
	def instrument_place_on_screen(self):
		""" Show a dialog asking user to place the instrument on the screen
		and give an option to cancel """
		if getattr(self, "subprocess_abort", False) or \
		   getattr(self, "thread_abort", False):
			# If we are aborting, ignore request
			return
		self.progress_wnd.Pulse(" " * 4)
		dlg = ConfirmDialog(self.progress_wnd,
							msg=lang.getstr("instrument.place_on_screen"), 
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
		if not isinstance(self.progress_wnd, UntetheredFrame):
			if debug or test:
				safe_print('Sending SPACE key')
			self.safe_send(" ")
	
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
		if debug or test:
			safe_print('Sending SPACE key')
		self.safe_send(" ")
	
	def clear_argyll_info(self):
		"""
		Clear Argyll CMS version, detected displays and instruments.
		"""
		self.argyll_bin_dir = None
		self.argyll_version = [0, 0, 0]
		self.argyll_version_string = "0.0.0"
		self._displays = []
		self.cmdname = None
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
		self.retcode = -1
		self.output = []
		self.errors = []
		self.recent = FilteredStream(LineCache(maxlines=3), self.data_encoding, 
									 discard=self.recent_discard,
									 triggers=self.triggers +
											  ["stopped at user request"])
		self.retrycount = 0
		self.lastmsg = FilteredStream(LineCache(), self.data_encoding, 
									  discard=self.lastmsg_discard,
									  triggers=self.triggers)
		self.send_buffer = None
		if not hasattr(self, "logger") or (self.interactive and self.owner and
										   isinstance(self.logger,
													  DummyLogger)):
			# Log interaction with Argyll tools that run interactively
			if self.interactive and self.owner:
				if self.owner.Name != "mainframe":
					name = "interact.%s" % self.owner.Name
				else:
					name = "interact"
				self.logger = get_file_logger(name)
			else:
				self.logger = DummyLogger()
		if self.interactive:
			self.logger.info("-" * 80)
		self.sessionlogfile = None

	def create_3dlut(self, profile_in, path, profile_abst=None, profile_out=None,
					 apply_cal=True, intent="r", format="3dl",
					 size=17, input_bits=10, output_bits=12, maxval=1.0,
					 input_encoding="n", output_encoding="n",
					 bt1886_gamma=None, bt1886_gamma_type="b",
					 save_link_icc=True):
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
			profile_in.fileName = os.path.join(cwd, profile_in_basename)
			profile_in.write()
			profile_out.fileName = os.path.join(cwd, profile_out_basename)
			profile_out.write()
			profile_out_cal_path = os.path.splitext(profile_out.fileName)[0] + ".cal"
			
			# Apply calibration?
			if apply_cal:
				# Get the calibration from profile vcgt
				if not profile_out.tags.get("vcgt", None):
					raise Error(lang.getstr("profile.no_vcgt"))
				try:
					cgats = vcgt_to_cal(profile_out)
				except (CGATS.CGATSInvalidError, 
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
						raise NotImplementedError(lang.getstr("argyll.util.not_found",
															  "applycal"))
					safe_print(lang.getstr("apply_cal"))
					result = self.exec_cmd(applycal, ["-v",
													  profile_out_cal_path,
													  profile_out_basename,
													  profile_out.fileName],
										   capture_output=True,
										   skip_scripts=True)
					if isinstance(result, Exception) and not getcfg("dry_run"):
						raise result
					elif not result:
						raise Error("\n\n".join([lang.getstr("apply_cal.error"),
												 "\n".join(self.errors)]))

			# Now build the device link
			collink = get_argyll_util("collink")
			if not collink:
				raise NotImplementedError(lang.getstr("argyll.util.not_found",
													  "collink"))
			args = ["-v", "-qh", "-G", "-i%s" % intent, "-r65", "-n"]
			if profile_abst:
				profile_abst.write(os.path.join(cwd, "abstract.icc"))
				args += ["-p", "abstract.icc"]
			if self.argyll_version >= [1, 6]:
				if format == "madVR":
					args += ["-3m"]
				elif format == "eeColor" and not test:
					args += ["-3e"]
				args += ["-e%s" % input_encoding]
				args += ["-E%s" % output_encoding]
				if bt1886_gamma:
					args += ["-I%s:%s" % (bt1886_gamma_type, bt1886_gamma)]
				if apply_cal:
					# Apply the calibration when building our device link
					# i.e. use collink -a parameter (apply calibration curves
					# to link output and append linear)
					args += ["-a", profile_out_cal_path]
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
				manufacturer = profile_out.getDeviceManufacturerDescription()
				if manufacturer:
					profile_link.setDeviceManufacturerDescription(manufacturer)
				model = profile_out.getDeviceModelDescription()
				if model:
					profile_link.setDeviceModelDescription(model)
				profile_link.device["manufacturer"] = profile_out.device["manufacturer"]
				profile_link.device["model"] = profile_out.device["model"]
				if "mmod" in profile_out.tags:
					profile_link.tags.mmod = profile_out.tags.mmod
				profile_link.calculateID()
				profile_link.write(filename + profile_ext)

			if self.argyll_version >= [1, 6] and ((format == "eeColor" and
												   not test) or
												  format == "madVR"):
				# Collink has already written the 3DLUT for us
				result2 = self.wrapup(not isinstance(result, UnloggedInfo) and
									  result, dst_path=path,
									  ext_filter=[".3dlut", ".cal", ".log",
												  ".txt"])
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
		step = 1.0 / (size - 1)
		RGB_triplet = [0.0, 0.0, 0.0]
		RGB_index = [0, 0, 0]
		# Set the fastest and slowest changing columns, from right to left
		if format in ("3dl", "mga", "spi3d"):
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

		# Lookup RGB -> XYZ values through devicelink profile using icclu
		# (Using icclu instead of xicclu because xicclu in versions
		# prior to Argyll CMS 1.6.0 could not deal with devicelink profiles)
		RGB_out = self.xicclu(link_filename, RGB_in, use_icclu=True)

		# Remove temporary files, move .cal and .log files
		result2 = self.wrapup(dst_path=path, ext_filter=[".cal", ".log"])

		if isinstance(result, Exception):
			raise result

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
				lut[-1] += ["%i" % int(round(i * step * (math.pow(2, input_bits) - 1)))]
			for RGB_triplet in RGB_out:
				lut.append([])
				for component in (0, 1, 2):
					lut[-1] += [("%i" % int(round(RGB_triplet[component] * maxval))).rjust(pad, " ")]
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
					lut[-1] += ["%.6f" % (RGB_triplet[component] * maxval)]
		elif format == "spi3d":
			if maxval is None:
				maxval = 1.0
			lut = [["SPILUT 1.0"]]
			lut.append(["3 3"])
			lut.append(["%i %i %i" % ((size, ) * 3)])
			for i, RGB_triplet in enumerate(RGB_out):
				lut.append([str(index) for index in RGB_indexes[i]])
				for component in (0, 1, 2):
					lut[-1] += ["%.6f" % (RGB_triplet[component] * maxval)]
		elif format == "eeColor":
			if maxval is None:
				maxval = 1.0
			lut = []
			for i, RGB_triplet in enumerate(RGB_out):
				lut.append(["%.6f" % (float(component) * maxval) for component in RGB_in[i].split()])
				for component in (0, 1, 2):
					lut[-1] += ["%.6f" % (RGB_triplet[component] * maxval)]
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
					lut[-1] += [("%i" % int(round(RGB_triplet[component] * maxval)))]
			valsep = "\t"
		lut.append([])
		for i, line in enumerate(lut):
			lut[i] = valsep.join(line)
		result = linesep.join(lut)

		# Write 3DLUT
		lut_file = open(path, "wb")
		lut_file.write(result)
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
									 enumerate_ports=True):
		"""
		Enumerate the available displays and ports.
		
		Also sets Argyll version number, availability of certain options
		like black point rate, and checks LUT access for each display.
		
		"""
		if (silent and check_argyll_bin()) or (not silent and 
											   check_set_argyll_bin()):
			displays = []
			lut_access = []
			if verbose >= 1 and not silent:
				safe_print(lang.getstr("enumerating_displays_and_comports"))
			if getattr(wx.GetApp(), "progress_dlg", None) and \
			   wx.GetApp().progress_dlg.IsShownOnScreen():
				wx.GetApp().progress_dlg.Pulse(
					lang.getstr("enumerating_displays_and_comports"))
			instruments = []
			if enumerate_ports:
				cmd = get_argyll_util("dispcal")
			else:
				cmd = get_argyll_util("dispwin")
				for instrument in getcfg("instruments").split(os.pathsep):
					# Names are canonical from 1.1.4.7 onwards, but we may have
					# verbose names from an old configuration
					instrument = get_canonical_instrument_name(instrument)
					if instrument.strip():
						instruments.append(instrument)
			argyll_bin_dir = os.path.dirname(cmd)
			if (argyll_bin_dir != self.argyll_bin_dir):
				self.argyll_bin_dir = argyll_bin_dir
				safe_print(self.argyll_bin_dir)
			result = self.exec_cmd(cmd, ["-?"], capture_output=True, 
								   skip_scripts=True, silent=True, 
								   log_output=False)
			if isinstance(result, Exception):
				safe_print(result)
			arg = None
			defaults["calibration.black_point_rate.enabled"] = 0
			n = -1
			self.display_rects = []
			non_standard_display_args = ("-dweb[:port]", "-dmadvr")
			for line in self.output:
				if isinstance(line, unicode):
					n += 1
					line = line.strip()
					if n == 0 and "version" in line.lower():
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
						continue
					line = line.split(None, 1)
					if len(line) and line[0][0] == "-":
						arg = line[0]
						if arg == "-A":
							# Rate of blending from neutral to black point.
							defaults["calibration.black_point_rate.enabled"] = 1
						elif arg in non_standard_display_args:
							displays.append(arg)
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
							if ((re.match("/dev/tty\w?\d+$", value) or
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
			if verbose >= 1 and not silent: safe_print(lang.getstr("success"))
			if getattr(wx.GetApp(), "progress_dlg", None) and \
			   wx.GetApp().progress_dlg.IsShownOnScreen():
				wx.GetApp().progress_dlg.Pulse(
					lang.getstr("success"))
			if instruments != self.instruments:
				self.instruments = instruments
				setcfg("instruments", os.pathsep.join(instruments))
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
					display_name = displays[i].split("@")[0].strip()
					# Make sure we have nice descriptions
					desc = []
					if sys.platform == "win32" and i < len(monitors):
						# Get monitor description using win32api
						device = util_win.get_active_display_device(
									monitors[i]["Device"])
						if device:
							desc.append(device.DeviceString.decode(fs_enc, 
																   "replace"))
					# Get monitor descriptions from EDID
					try:
						# Important: display_name must be given for get_edid
						# under Mac OS X, but it doesn't hurt to always
						# include it
						edid = get_edid(i, display_name)
					except (TypeError, ValueError, WMIError):
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
						displays[i] = " @".join([" ".join(desc), 
												 display.split("@")[1]])
					self.display_manufacturers.append(" ".join(manufacturer))
					self.display_names.append(displays[i].split("@")[0].strip())
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
				displays.append("Untethered")
				self.display_edid.append({})
				self.display_manufacturers.append("")
				self.display_names.append("Untethered")
				self.displays = displays
				setcfg("displays", os.pathsep.join(displays))
				# Filter out Untethered
				displays = displays[:-1]
				if self.argyll_version >= [1, 6, 0]:
					# Filter out madVR
					displays = displays[:-1]
				if self.argyll_version >= [1, 4, 0]:
					# Filter out Web @ localhost
					displays = displays[:-1]
				if check_lut_access:
					dispwin = get_argyll_util("dispwin")
					for i, disp in enumerate(displays):
						if verbose >= 1 and not silent:
							safe_print(lang.getstr("checking_lut_access", (i + 1)))
						if getattr(wx.GetApp(), "progress_dlg", None) and \
						   wx.GetApp().progress_dlg.IsShownOnScreen():
							wx.GetApp().progress_dlg.Pulse(
								lang.getstr("checking_lut_access", (i + 1)))
						test_cal = get_data_path("test.cal")
						if not test_cal:
							safe_print(lang.getstr("file.missing", "test.cal"))
							return
						# Load test.cal
						result = self.exec_cmd(dispwin, ["-d%s" % (i +1), "-c", 
														 test_cal], 
											   capture_output=True, 
											   skip_scripts=True, 
											   silent=True)
						if isinstance(result, Exception):
							safe_print(result)
						# Check if LUT == test.cal
						result = self.exec_cmd(dispwin, ["-d%s" % (i +1), "-V", 
														 test_cal], 
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
														 self.get_dispwin_display_profile_argument(i)], 
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
						if getattr(wx.GetApp(), "progress_dlg", None) and \
						   wx.GetApp().progress_dlg.IsShownOnScreen():
							wx.GetApp().progress_dlg.Pulse(
								lang.getstr("success" if retcode == 0 else
											"failure"))
				else:
					lut_access += [None] * len(displays)
				if self.argyll_version >= [1, 4, 0]:
					# Web @ localhost
					lut_access.append(False)
				if self.argyll_version >= [1, 6, 0]:
					# madVR
					lut_access.append(True)
				# Untethered
				lut_access.append(False)
				self.lut_access = lut_access
		elif silent or not check_argyll_bin():
			self.clear_argyll_info()

	def exec_cmd(self, cmd, args=[], capture_output=False, 
				 display_output=False, low_contrast=True, skip_scripts=False, 
				 silent=False, parent=None, asroot=False, log_output=True,
				 title=appname, shell=False, working_dir=None, dry_run=False):
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
		progress_dlg = self._progress_wnd or getattr(wx.GetApp(),
													 "progress_dlg", None)
		if parent is None:
			if progress_dlg and progress_dlg.IsShownOnScreen():
				parent = progress_dlg
			else:
				parent = self.owner
		if not capture_output:
			capture_output = not sys.stdout.isatty()
		self.clear_cmd_output()
		if None in [cmd, args]:
			if verbose >= 1 and not silent:
				safe_print(lang.getstr("aborted"))
			return False
		cmdname = os.path.splitext(os.path.basename(cmd))[0]
		self.cmdname = cmdname
		if cmdname == get_argyll_utilname("dispwin"):
			if "-Sl" in args or "-Sn" in args or (sys.platform == "darwin" and
												  not "-I" in args and
												  mac_ver()[0] >= '10.6'):
				# Mac OS X 10.6 and up needs root privileges if loading/clearing 
				# calibration
				# In all other cases, root is only required if installing a
				# profile to a system location
				asroot = True
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
		if (working_basename and working_dir == self.tempdir and not silent
			and log_output and not getcfg("dry_run")):
			self.sessionlogfile = LogFile(working_basename, working_dir)
			self.sessionlogfiles[working_basename] = self.sessionlogfile
		if verbose >= 1 or not silent:
			if not silent or verbose >= 3:
				self.log("-" * 80)
				if self.sessionlogfile:
					safe_print("Session log: %s" % working_basename + ".log")
					safe_print("")
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
					if self.owner and hasattr(self.owner, "infoframe"):
						wx.CallAfter(self.owner.infoframe.Show)
					return UnloggedInfo(lang.getstr("dry_run.info"))
		cmdline = [cmd] + args
		if working_dir:
			for i, item in enumerate(cmdline):
				if i > 0 and (item.find(os.path.sep) > -1 and 
							  os.path.dirname(item) == working_dir):
					# Strip the path from all items in the working dir
					if sys.platform == "win32" and \
					   re.search("[^\x20-\x7e]", 
								 os.path.basename(item)) and os.path.exists(item):
						# Avoid problems with encoding
						item = win32api.GetShortPathName(item) 
					cmdline[i] = os.path.basename(item)
			if (sys.platform == "win32" and 
				re.search("[^\x20-\x7e]", working_dir) and 
				os.path.exists(working_dir)):
				# Avoid problems with encoding
				working_dir = win32api.GetShortPathName(working_dir)
		sudo = None
		# Run commands through wexpect.spawn instead of subprocess.Popen if
		# all of these conditions apply:
		# - command is dispcal, dispread or spotread
		# - arguments are not empty
		# - actual user interaction in a terminal is not needed OR
		#   we are on Windows and running without a console
		measure_cmds = (get_argyll_utilname("dispcal"), 
						get_argyll_utilname("dispread"), 
						get_argyll_utilname("spotread"))
		process_cmds = (get_argyll_utilname("collink"),
						get_argyll_utilname("colprof"),
						get_argyll_utilname("targen"))
		interact = args and not "-?" in args and cmdname in measure_cmds + process_cmds
		self.measure_cmd = not "-?" in args and cmdname in measure_cmds
		if asroot and ((sys.platform != "win32" and os.geteuid() != 0) or 
					   (sys.platform == "win32" and 
					    sys.getwindowsversion() >= (6, ))):
			if sys.platform == "win32":
				# Vista and later
				pass
			else:
				sudo = which("sudo")
		if sudo:
			if not self.pwd:
				# Determine available sudo options
				if not self.sudo_availoptions:
					man = which("man")
					if man:
						manproc = sp.Popen([man, "sudo"], stdout=sp.PIPE, 
											stderr=sp.PIPE)
						# Strip formatting
						stdout = re.sub(".\x08", "", manproc.communicate()[0])
						self.sudo_availoptions = {"E": bool(re.search("-E", stdout)),
												  "l [command]": bool(re.search("-l(?:\[l\])?\s+\[command\]", stdout)),
												  "n": bool(re.search("-n", stdout))}
					else:
						self.sudo_availoptions = {"E": False, 
												  "l [command]": False, 
												  "n": False}
					if debug:
						safe_print("[D] Available sudo options:", 
								   ", ".join(filter(lambda option: self.sudo_availoptions[option], 
													self.sudo_availoptions.keys())))
				# Set sudo args based on available options
				if self.sudo_availoptions["l [command]"]:
					sudo_args = ["-l",
								 "-n" if self.sudo_availoptions["n"] else "-S",
								 cmd, "-?"]
				else:
					sudo_args = ["-l", "-S"]
				# Set stdin based on -n option availability
				if "-S" in sudo_args:
					stdin = tempfile.SpooledTemporaryFile()
					stdin.write((self.pwd or "").encode(enc, "replace") + os.linesep)
					stdin.seek(0)
				else:
					stdin = None
				sudoproc = sp.Popen([sudo] + sudo_args, stdin=stdin, stdout=sp.PIPE, 
									stderr=sp.PIPE)
				stdout, stderr = sudoproc.communicate()
				if stdin and not stdin.closed:
					stdin.close()
				pwd = self.pwd
				if not stdout.strip() or not pwd:
					# ask for password
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
					sudo_args = ["-k", "-l", "-S"]
					if self.sudo_availoptions["l [command]"]:
						sudo_args += [cmd, "-?"]
					while True:
						dlg.pwd_txt_ctrl.SetFocus()
						result = dlg.ShowModal()
						pwd = dlg.pwd_txt_ctrl.GetValue()
						if result != wx.ID_OK:
							safe_print(lang.getstr("aborted"))
							return None
						stdin = tempfile.SpooledTemporaryFile()
						stdin.write(pwd.encode(enc, "replace") + os.linesep)
						stdin.seek(0)
						sudoproc = sp.Popen([sudo] + sudo_args, stdin=stdin, 
											stdout=sp.PIPE, stderr=sp.PIPE)
						stdout, stderr = sudoproc.communicate()
						if not stdin.closed:
							stdin.close()
						if stdout.strip():
							# password was accepted
							self.auth_timestamp = time()
							self.pwd = pwd
							break
						else:
							errstr = unicode(stderr, enc, "replace")
							errstr = "\n".join([re.sub("^[^:]+:\s*", "", line)
												for line in errstr.splitlines()])
							if not silent:
								safe_print(errstr)
							else:
								log(errstr)
							dlg.message.SetLabel(errstr)
							dlg.pwd_txt_ctrl.SetValue("")
							dlg.sizer0.SetSizeHints(dlg)
							dlg.sizer0.Layout()
					dlg.Destroy()
			cmdline.insert(0, sudo)
			if (cmdname == get_argyll_utilname("dispwin")
				and sys.platform != "darwin"
				and self.sudo_availoptions["E"]
				and getcfg("sudo.preserve_environment")):
				# Preserve environment so $DISPLAY is set
				cmdline.insert(1, "-E")
			if not interact:
				cmdline.insert(1, "-S")
		if working_dir and working_basename and not skip_scripts:
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
			if not self.measure_cmd and self.argyll_version >= [1, 2]:
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
			if sys.platform not in ("darwin", "win32"):
				putenvu("ENABLE_COLORHUG", "1")
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
				kwargs = dict(timeout=5, cwd=working_dir,
							  env=os.environ)
				if sys.platform == "win32":
					kwargs["codepage"] = windll.kernel32.GetACP()
				stderr = StringIO()
				stdout = StringIO()
				logfiles = []
				if (self.interactive and getattr(self, "terminal", None)):
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
												   self.data_encoding,
												   discard="",
												   linesep_in="\n", 
												   triggers=[])))
				logfiles += [stdout, self.recent, self.lastmsg, self]
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
						# Minimum Windows version: XP or Server 2003
						if (sys.platform == "win32" and
							sys.getwindowsversion() < (5, 1)):
							return Error(lang.getstr("windows.version.unsupported"))
						try:
							self.subprocess = wexpect.spawn(cmdline[0],
															cmdline[1:], 
															**kwargs)
						except wexpect.ExceptionPexpect, exception:
							self.retcode = -1
							return Error(safe_unicode(exception))
						if debug >= 9 or (test and not "-?" in args):
							self.subprocess.interact()
					self.subprocess.logfile_read = Files(logfiles)
					if self.subprocess.isalive():
						if self.measure_cmd:
							keyhit_strs = [" or Q to ",
										  "8\) Exit"]
							while self.subprocess.isalive():
								self.subprocess.expect(keyhit_strs + ["Current",
														r" \d+ of \d+",
														wexpect.EOF],
													   timeout=None)
								if self.subprocess.after in (wexpect.EOF, None):
									break
								if filter(lambda keyhit_str:
											  re.search(keyhit_str,
														self.subprocess.after),
											  keyhit_strs):
									# Wait for the keypress
									while not self.send_buffer:
										if not self.subprocess.isalive():
											break
										sleep(.05)
								if (self.send_buffer and
									self.subprocess.isalive()):
									self._safe_send(self.send_buffer)
									self.send_buffer = None
						else:
							self.subprocess.expect(wexpect.EOF, 
												   timeout=None)
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
					try:
						self.subprocess = sp.Popen(" ".join(cmdline) if shell else
												   cmdline, stdin=stdin, 
												   stdout=stdout, stderr=stderr, 
												   shell=shell, cwd=working_dir, 
												   startupinfo=startupinfo)
					except Exception, exception:
						self.retcode = -1
						return Error("\n".join([safe_unicode(v) for v in
												(cmd, exception)]))
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
							self.log("".join(self.output).strip(), logfn)
						if display_output and self.owner and \
						   hasattr(self.owner, "infoframe"):
							wx.CallAfter(self.owner.infoframe.Show)
					if tries > 0 and not interact:
						stdout = tempfile.SpooledTemporaryFile()
				if not silent and len(self.errors):
					errstr = "".join(self.errors).strip()
					self.log(errstr)
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
				safe_print(lang.getstr("aborted"))
			if interact and len(self.output):
				for i, line in enumerate(self.output):
					if "Calibrate failed with 'User hit Abort Key' (No device error)" in line:
						break
					if ((": Error" in line and
					     not "failed with 'User Aborted'" in line and
					     not "test_crt returned error code 1" in line) or
					    (line.startswith("Failed to") and
					     not "Failed to meet target" in line) or
					    ("Requested ambient light capability" in line and
					     len(self.output) == i + 2) or
					    ("Diagnostic:" in line and
					     (len(self.output) == i + 1 or
						  self.output[i + 1].startswith("usage:"))) or
						 "communications failure" in line.lower()):
						# "test_crt returned error code 1" == user aborted
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
						return UnloggedError(errmsg.strip())
			return False
		return True
	
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
			result = Error(u"Error - delayedResult.get() failed: " + 
						   safe_unicode(traceback.format_exc()))
		if self.progress_start_timer.IsRunning():
			self.progress_start_timer.Stop()
		self.finished = True
		if not continue_next or isinstance(result, Exception) or not result:
			self.stop_progress()
		self.subprocess_abort = False
		self.thread_abort = False
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
			A2B0.clut[-1].append([int(round(max(v * 32768, 0))) for v in XYZ])
		if logfile:
			logfile.write("\n")
		profile.tags.A2B0 = A2B0
		return True
	
	def generate_B2A_from_inverse_table(self, profile, clutres=None,
										source="A2B", tableno=None, bpc=False,
										logfile=None):
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
			safe_print("-" * 80)
			if source == "A2B":
				msg = ("Generating B2A%i table by inverting A2B%i table\n" %
					   (tableno, tableno))
			else:
				msg = "Re-generating B2A%i table by interpolation\n" % tableno
			logfile.write(msg)
			logfile.write("\n")

		# Note that intent 0 will be colorimetric if no other tables are present
		intent = {0: "p",
				  1: "r",
				  2: "s"}[tableno]
		
		# Lookup RGB -> XYZ for primaries, black- and white point
		idata = [[0, 0, 0], [1, 1, 1], [1, 0, 0], [0, 1, 0], [0, 0, 1]]
		
		direction = {"A2B": "f", "B2A": "ib"}[source]
		odata = self.xicclu(profile, idata, intent, direction, pcs="x")
		
		# Scale to Y = 1
		XYZwpY = odata[1][1]
		odata = [[n / XYZwpY for n in v] for v in odata]

		XYZbp = odata[0]
		XYZwp = odata[1]
		XYZr = odata[2]
		XYZg = odata[3]
		XYZb = odata[4]
		
		# Prepare input PCS values
		if logfile:
			logfile.write("Generating input curve PCS values...\n")
		idata = []
		numentries = 4096
		maxval = numentries - 1.0
		for i in xrange(numentries):
			# Lab
			idata.append((i / maxval * 100, 0, 0))
		
		pcs = profile.connectionColorSpace[0].lower()

		if logfile:
			logfile.write("Looking up input curve RGB values...\n")
		
		if source == "B2A":
			# NOTE:
			# Argyll's B2A tables are slightly inaccurate:
			# 0 0 0 PCS -> RGB may give RGB levels > 0 (it should clip
			# instead). Inversely, 0 0 0 RGB -> PCS (through inverted B2A)
			# will return PCS values that are too low or zero (ie. not the
			# black point as expected)
			
			# TODO: How to deal with this?
			pass

		oXYZ = [colormath.Lab2XYZ(*v) for v in idata]
		fpL = [v[0] for v in idata]
		fpX = [v[0] for v in oXYZ]
		fpY = [v[1] for v in oXYZ]
		fpZ = [v[2] for v in oXYZ]

		if bpc:
			for i, (L, a, b) in enumerate(idata):
				X, Y, Z = colormath.Lab2XYZ(L, a, b)
				X, Y, Z = colormath.apply_bpc(X, Y, Z, (0, 0, 0), XYZbp, XYZwp)
				idata[i] = colormath.XYZ2Lab(X * 100, Y * 100, Z * 100)
		
		# Lookup Lab -> RGB values through profile using xicclu to get TRC
		direction = {"A2B": "if", "B2A": "b"}[source]
		odata = self.xicclu(profile, idata, intent, direction, pcs="l")

		xpR = [v[0] for v in odata]
		xpG = [v[1] for v in odata]
		xpB = [v[2] for v in odata]

		# Initialize B2A
		itable = ICCP.LUT16Type()
		
		# Setup matrix
		if profile.connectionColorSpace == "XYZ":
			# Use a matrix that scales the profile colorspace into the XYZ
			# encoding range, to make optimal use of the cLUT grid points

			matrices = []

			# Get the primaries
			XYZrgb = [XYZr, XYZg, XYZb]
	
			# Construct the final matrix
			Xr, Yr, Zr = XYZrgb[0]
			Xg, Yg, Zg = XYZrgb[1]
			Xb, Yb, Zb = XYZrgb[2]
			m1 = colormath.Matrix3x3(((Xr, Xg, Xb),
									  (Yr, Yg, Yb),
									  (Zr, Zg, Zb))).inverted()
			matrices.append(m1)
			Sr, Sg, Sb = m1 * XYZwp
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

		numentries = 4096
		maxval = numentries - 1.0
		vrange = xrange(numentries)
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
			Linterp = (colormath.Interp(xpR, fpL),
					   colormath.Interp(xpG, fpL),
					   colormath.Interp(xpB, fpL))
			rLinterp = (colormath.Interp(fpL, xpR),
						colormath.Interp(fpL, xpG),
						colormath.Interp(fpL, xpB))
			maxL = 100.0 + 25500.0 / 65280.0
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
				XYZ = fpX[j], fpY[j], fpZ[j]
				v = list(colormath.XYZ2Lab(*[n * 100 for n in XYZ]))
				v[0] = j / maxval
				v[1] = j / maxval + v[1] / (127 + (255 / 256.0))
				v[2] = j / maxval + v[2] / (127 + (255 / 256.0))
			for i in xrange(len(itable.input)):
				if profile.connectionColorSpace == "Lab":
					if i == 0:
						# L*
						v[0] = rLinterp[i](v[0] * maxL)
				itable.input[i].append(int(round(v[i] * 65535)))
			if logfile and j % math.floor(maxval / 100.0) == 0:
				logfile.write("\r%i%%" % round(j / maxval * 100))
		if logfile:
			logfile.write("\n")

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
			# Use CAM Jab for clipping for cLUT grid points after a given
			# threshold
			xicclu1 = Xicclu(profile, intent, direction, "n", pcs, 100)
			xicclu2 = Xicclu(profile, intent, direction, "n", pcs, 100,
							 cwd=xicclu1.tempdir, use_cam_clipping=True)
			threshold = clutres / 2
			for a in xrange(clutres):
				if self.thread_abort:
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
							if bpc:
								v = colormath.apply_bpc(v[0], v[1], v[2],
														(0, 0, 0), XYZbp, XYZwp)
							##print "%3.6f %3.6f %3.6f" % tuple(v)
							##raw_input()
							if intent == "a":
								v = colormath.adapt(*v + [XYZwp,
														  profile.tags.wtpt.ir.values()])
						else:
							# Legacy CIELAB
							d = Linterp[1](d)
							v = d, -128 + e * abmaxval, -128 + f * abmaxval
						idata.append("%.6f %.6f %.6f" % tuple(v))
						# Lookup CIE -> device values through profile using xicclu
						xicclu1(v)
						if a > threshold or b > threshold or c > threshold:
							xicclu2(v)
					if logfile:
						logfile.write("\r%i%%" % round(len(idata) /
													   clutres ** 3.0 *
													   100))
			xicclu2.exit()
			xicclu1.exit()
			if logfile:
				logfile.write("\n")
				logfile.write("Input black XYZ: %s\n" % idata[0])
				logfile.write("Input white XYZ: %s\n" % idata[-1])

			# Linearly interpolate the crossover to CAM Jab clipping region
			odata1 = xicclu1.get()
			odata2 = xicclu2.get()
			j, k = 0, 0
			r = clutres - 1.0 - threshold
			for a in xrange(clutres):
				for b in xrange(clutres):
					for c in xrange(clutres):
						v = odata1[j]
						j += 1
						if a > threshold or b > threshold or c > threshold:
							d = max(a, b, c)
							v2 = odata2[k]
							k += 1
							for i, n in enumerate(v):
								v[i] *= (clutres - 1 - d) / r
								v2[i] *= 1 - (clutres - 1 - d) / r
								v[i] += v2[i]
						odata.append(v)
			numrows = len(odata)
			if numrows != clutres ** 3:
				raise ValueError("Number of cLUT entries (%s) exceeds cLUT res "
								 "maximum (%s^3 = %s)" % (numrows, clutres,
														  clutres ** 3))
			if logfile:
				logfile.write("Output black RGB: %.4f %.4f %.4f\n" %
							  tuple(odata[0]))
				logfile.write("Output white RGB: %.4f %.4f %.4f\n" %
							  tuple(odata[-1]))
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
						itable.clut[-1].append([int(round(v * step * 65535))
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
				if i == 0:
					RGB = 0, 0, 0
				elif i == numrows - 1.0:
					RGB = 1, 1, 1
				itable.clut[-1].append([int(round(v * 65535)) for v in RGB])
		if logfile:
			logfile.write("\n")
		
		if getcfg("profile.b2a.smooth.diagpng") and profile.fileName:
			# Generate diagnostic images
			fname, ext = os.path.splitext(profile.fileName)
			for suffix, table in [("pre", profile.tags["B2A%i" % tableno]),
								  ("post", itable)]:
				table.clut_writepng(fname + ".B2A%i.%s.CLUT.png" %
									(tableno, suffix))
		if getcfg("profile.b2a.smooth.extra"):
			# Apply extra smoothing to the cLUT
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
						if sum(grid[y][x]) < 65535 * .0625 * 3 or x == y == i:
							# Don't smooth dark colors and gray axis
							continue
						RGB = [[v] for v in grid[y][x]]
						for j, c in enumerate((x, y)):
							if c > 0 and c < clutres - 1 and y < clutres - 1:
								for n in (-1, 1):
									RGBn = grid[(y, y + n)[j]][(x + n, x)[j]]
									for k in xrange(3):
										RGB[k].append(RGBn[k])
						grid[y][x] = [sum(v) / float(len(v)) for v in RGB]
				for j, row in enumerate(grid):
					itable.clut[i * clutres + j] = [[int(round(v))
													 for v in RGB]
													for RGB in row]
			if getcfg("profile.b2a.smooth.diagpng") and profile.fileName:
				itable.clut_writepng(fname + ".B2A%i.post.CLUT.extrasmooth.png" %
									 tableno)

		# Set output curves
		itable.output = [[], [], []]
		numentries = 256
		maxval = numentries - 1.0
		for i in xrange(len(itable.output)):
			for j in xrange(numentries):
				itable.output[i].append(int(round(j / maxval * 65535)))
		
		# Update profile
		profile.tags["B2A%i" % tableno] = itable
		return True
	
	def get_device_id(self, quirk=True):
		""" Get org.freedesktop.ColorManager device key """
		if config.get_display_name() in ("Web", "Untethered", "madVR"):
			return None
		edid = self.display_edid[max(0, min(len(self.displays) - 1, 
											getcfg("display.number") - 1))]
		return colord.device_id_from_edid(edid, quirk=quirk)

	def get_display(self):
		""" Get the currently configured display number.
		
		Returned is the Argyll CMS dispcal/dispread -d argument
		
		"""
		if config.get_display_name() == "Web":
			return "web:%i" % getcfg("webserver.portnumber")
		if config.get_display_name() == "madVR":
			return "madvr"
		if config.get_display_name() == "Untethered":
			return "0"
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
	
	def get_display_name(self, prepend_manufacturer=False, prefer_edid=False):
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
				else:
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
			profile = ICCP.get_display_profile(display_no)
		except Exception, exception:
			safe_print("Error - couldn't get profile for display %s" % 
					   display_no)
		else:
			if profile and profile.fileName:
				arg = profile.fileName
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
			except (IOError, CGATS.CGATSInvalidError), exception:
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
	
	def has_lut_access(self):
		display_no = min(len(self.lut_access), getcfg("display.number")) - 1
		return display_no > -1 and self.lut_access[display_no]
	
	def has_separate_lut_access(self):
		""" Return True if separate LUT access is possible and needed. """
		if self.argyll_version >= [1, 6, 0]:
			# filter out Web @ localhost, madVR and Untethered
			lut_access = self.lut_access[:-3]
		elif self.argyll_version >= [1, 4, 0]:
			# filter out Web @ localhost and Untethered
			lut_access = self.lut_access[:-2]
		else:
			# filter out Untethered
			lut_access = self.lut_access[:-1]
		return (len(self.displays) > 1 and False in lut_access and True in 
				lut_access)
	
	def import_colorimeter_corrections(self, cmd, args=None):
		""" Import colorimeter corrections. cmd can be 'i1d3ccss', 'spyd4en'
		or 'oeminst' """
		if not args:
			args = []
		needroot = sys.platform != "win32"
		if (is_superuser() or needroot) and not "-Sl" in args:
			# If we are root or need root privs anyway, install to local
			# system scope
			args.insert(0, "-Sl")
		return self.exec_cmd(cmd, ["-v"] + args, capture_output=True, 
							 skip_scripts=True, silent=False,
							 asroot=needroot)
	
	def import_edr(self, args=None):
		""" Import X-Rite .edr files """
		return self.import_colorimeter_corrections(get_argyll_util("i1d3ccss"),
												   args)
	
	def import_spyd4cal(self, args=None):
		""" Import Spyder4 calibrations to spy4cal.bin """
		return self.import_colorimeter_corrections(get_argyll_util("spyd4en"),
												   args)

	def install_profile(self, profile_path, capture_output=True,
						skip_scripts=False, silent=False):
		""" Install a profile by copying it to an appropriate location and
		registering it with the system """
		result = True
		colord_install = False
		gcm_import = False
		oy_install = False
		argyll_install = self._install_profile_argyll(profile_path,
													  capture_output,
													  skip_scripts, silent)
		device_id = self.get_device_id(quirk=True)
		if (self.argyll_version < [1, 6] and
			sys.platform not in ("darwin", "win32") and not getcfg("dry_run")):
			if device_id and colord.Colord:
				try:
					client = colord.client_connect()
					device = colord.device_connect(client, device_id)
				except colord.CDError:
					device_id = self.get_device_id(quirk=False)
				# FIXME: This can block, so should really be run in separate
				# thread with progress dialog in 'indeterminate' mode
				result = self._install_profile_colord(profile_path, device_id)
				colord_install = result
			if (not device_id or not colord.Colord or
				isinstance(result, Exception) or not result):
				gcm_import = bool(which("gcm-import"))
				if (isinstance(result, Exception) or not result) and gcm_import:
					# Fall back to gcm-import if colord profile install failed
					result = gcm_import
		if (not isinstance(result, Exception) and result and
			which("oyranos-monitor") and
			self.check_display_conf_oy_compat(getcfg("display.number"))):
			if device_id:
				profile_name = re.sub("[- ]", "_", device_id.lower()) + ".icc"
			else:
				profile_name = None
			result = self._install_profile_oy(profile_path, profile_name,
											  capture_output, skip_scripts,
											  silent)
			oy_install = result
		if not isinstance(result, Exception) and result:
			if isinstance(argyll_install, Exception) or not argyll_install:
				# Fedora's Argyll cannot install profiles using dispwin
				# Check if profile installation via colord or oyranos-monitor
				# was successful and continue
				if not isinstance(colord_install, Exception) and colord_install:
					result = colord_install
				elif not isinstance(oy_install, Exception) and oy_install:
					result = oy_install
				else:
					result = argyll_install
		if not isinstance(result, Exception) and result:
			if getcfg("profile.install_scope") == "l":
				# We need a system-wide config file to store the path to 
				# the Argyll binaries
				result = config.makecfgdir("system", self)
				if result:
					result = config.writecfg("system", self)
				if not result:
					return Error(lang.getstr("error.autostart_system"))
			if sys.platform == "win32":
				if getcfg("profile.load_on_login"):
					result = self._install_profile_loader_win32(silent)
			elif sys.platform != "darwin":
				if getcfg("profile.load_on_login"):
					result = self._install_profile_loader_xdg(silent)
				if gcm_import:
					self._install_profile_gcm(profile_path)
			if not isinstance(result, Exception) and result and not gcm_import:
				if verbose >= 1: safe_print(lang.getstr("success"))
				if sys.platform == "darwin" and False:  # NEVER
					# If installing the profile by just copying it to the
					# right location, tell user to select it manually
					msg = lang.getstr("profile.install.osx_manual_select")
				else:
					msg = lang.getstr("profile.install.success")
				result = Info(msg)
		else:
			if result is not None and not getcfg("dry_run"):
				if verbose >= 1: safe_print(lang.getstr("failure"))
				result = Error(lang.getstr("profile.install.error"))
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
			if (sys.platform == "win32" and
				sys.getwindowsversion() >= (6, ) and
				not util_win.per_user_profiles_isenabled()):
					# Enable per-user profiles under Vista / Windows 7
					try:
						util_win.enable_per_user_profiles(True,
														  getcfg("display.number") - 1)
					except Exception, exception:
						safe_print("util_win.enable_per_user_profiles(True, %s): %s" %
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
					args.insert(0, "-Sl")
				else:
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
			for line in self.output:
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
							safe_print(exception)
						else:
							if errors.strip():
								safe_print("osascript error: %s" % errors)
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
							safe_print(exception)
						else:
							if errors.strip():
								safe_print("osascript error: %s" % errors)
							else:
								result = True
					else:
						result = True
					break
		self.wrapup(False)
		return result
	
	def _install_profile_colord(self, profile_path, device_id):
		""" Install profile using colord """
		try:
			colord.install_profile(device_id, profile_path)
		except Exception, exception:
			safe_print(exception)
			return exception
		return True
	
	def _install_profile_gcm(self, profile_path):
		""" Install profile using gcm-import """
		# Remove old profile so gcm-import can work
		profilename = os.path.basename(profile_path)
		for dirname in iccprofiles_home:
			profile_install_path = os.path.join(dirname, profilename)
			if os.path.isfile(profile_install_path) and \
			   profile_install_path != profile_path:
				try:
					trash([profile_install_path])
				except Exception, exception:
					safe_print(exception)
		# Run gcm-import
		cmd, args = which("gcm-import"), [profile_path]
		args = " ".join('"%s"' % arg for arg in args)
		safe_print('%s %s &' % (cmd, args))
		sp.call(('%s %s &' % (cmd,  args)).encode(fs_enc), shell=True)
	
	def _install_profile_oy(self, profile_path, profile_name=None,
							capture_output=False, skip_scripts=False,
							silent=False):
		""" Install profile using oyranos-monitor """
		display = self.displays[max(0, min(len(self.displays) - 1,
										   getcfg("display.number") - 1))]
		x, y = [pos.strip() for pos in display.split(" @")[1].split(",")[0:2]]
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
					safe_print(exception)
					result = False
			if result is not False:
				profile_install_path = os.path.join(dirname,
													os.path.basename(profile_path))
				try:
					shutil.copyfile(profile_path, 
									profile_install_path)
				except Exception, exception:
					safe_print(exception)
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
					safe_print(u"Warning - could not remove old "
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
					safe_print(u"Warning - could not remove old "
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
					safe_print(u"Warning - could not remove old "
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
					safe_print(u"Warning - could not remove old "
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
		if os.path.basename(sys.executable) in ("python.exe", 
												"pythonw.exe"):
			cmd = sys.executable
			loader_args += [u'"%s"' % get_data_path(os.path.join("scripts", 
																 "dispcalGUI-apply-profiles"))]
		else:
			cmd = os.path.join(pydir, "dispcalGUI-apply-profiles.exe")
		try:
			scut = pythoncom.CoCreateInstance(shell.CLSID_ShellLink, None,
											  pythoncom.CLSCTX_INPROC_SERVER, 
											  shell.IID_IShellLink)
			scut.SetPath(cmd)
			scut.SetWorkingDirectory(pydir)
			if isexe:
				scut.SetIconLocation(exe, 0)
			else:
				scut.SetIconLocation(get_data_path(os.path.join("theme",
																"icons", 
																appname +
																".ico")), 0)
			scut.SetArguments(" ".join(loader_args))
			scut.SetShowCmd(win32con.SW_SHOWMINNOACTIVE)
			if is_superuser():
				if autostart:
					try:
						scut.QueryInterface(pythoncom.IID_IPersistFile).Save(autostart_lnkname, 0)
					except Exception, exception:
						if not silent:
							result = Warning(lang.getstr("error.autostart_creation", 
													     autostart) + "\n\n" + 
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
													     autostart_home) + "\n\n" + 
										     safe_unicode(exception))
			else:
				if not silent:
					result = Warning(lang.getstr("error.autostart_user"))
		except Exception, exception:
			if not silent:
				result = Warning(lang.getstr("error.autostart_creation", 
										     autostart_home) + "\n\n" + 
							     safe_unicode(exception))
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
					safe_print(autostart_lnkname, exception)
		if autostart_home:
			autostart_home_lnkname = os.path.join(autostart_home, 
												  name + ".lnk")
			if os.path.exists(autostart_home_lnkname):
				try:
					os.remove(autostart_home_lnkname)
				except Exception, exception:
					safe_print(autostart_home_lnkname, exception)
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
		if not os.path.exists(system_desktopfile_path) and \
		   not os.path.exists(desktopfile_path):
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
				if os.path.exists(pyw):
					# Running from source, or 0install/Listaller install
					icon = os.path.join(pydir, "theme", "icons", "256x256",
										appname + "-apply-profiles.png")
					executable = pyw
				else:
					# Regular install
					icon = appname + "-apply-profiles"
					executable = appname + "-apply-profiles"
				desktopfile.write('Icon=%s\n' % icon.encode("UTF-8"))
				desktopfile.write('Exec=%s\n' % executable.encode("UTF-8"))
				desktopfile.write('Terminal=false\n')
				desktopfile.close()
			except Exception, exception:
				if not silent:
					result = Warning(lang.getstr("error.autostart_creation", 
											     desktopfile_path) + "\n\n" + 
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
	
	def instrument_supports_ccss(self):
		""" Return whether instrument supports CCSS files or not """
		instrument_name = self.get_instrument_name()
		return ("i1 DisplayPro, ColorMunki Display" in instrument_name or
				"Spyder4" in instrument_name)
	
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
			safe_print("-" * 80)
			safe_print(lang.getstr("gamut.view.create"))
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
		else:
			result = cmd
		# Get profile max and avg err to be later added to metadata
		# Argyll outputs the following:
		# Profile check complete, peak err = x.xxxxxx, avg err = x.xxxxxx, RMS = x.xxxxxx
		peak = None
		avg = None
		rms = None
		for line in self.output:
			if line.startswith("Profile check complete"):
				peak = re.search("peak err = (\d+(?:\.\d+))", line)
				avg = re.search("avg err = (\d+(?:\.\d+))", line)
				rms = re.search("RMS = (\d+(?:\.\d+))", line)
				if peak:
					peak = peak.groups()[0]
				if avg:
					avg = avg.groups()[0]
				if rms:
					rms = rms.groups()[0]
				break
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
		if not isinstance(result, Exception) and result:
			profile_path = args[-1] + profile_ext
			try:
				profile = ICCP.ICCProfile(profile_path)
			except (IOError, ICCP.ICCProfileInvalidError), exception:
				result = Error(lang.getstr("profile.invalid") + "\n" + profile_path)
			else:
				if (profile.profileClass == "mntr" and
					profile.colorSpace == "RGB" and "A2B0" in profile.tags and
					getcfg("profile.b2a.smooth") and
					getcfg("profile.type") in ("x", "X")):
					result = self.update_profile_B2A(profile)
		if not isinstance(result, Exception) and result:
			(gamut_volume,
			 gamut_coverage) = self.create_gamut_views(profile_path)
		safe_print("-" * 80)
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
		if ((getcfg("gamap_perceptual") and "B2A0" in profile.tags) or
			(getcfg("gamap_saturation") and "B2A2" in profile.tags)):
			profile.intent = {"p": 0,
							  "r": 1,
							  "s": 2,
							  "a": 3}[getcfg("gamap_default_intent")]
		elif "B2A0" in profile.tags and "B2A1" in profile.tags:
			profile.intent = 0
		# Calculate profile ID
		profile.calculateID()
		try:
			profile.write()
		except Exception, exception:
			return exception
		return True
	
	def update_profile_B2A(self, profile):
		# Use reverse A2B interpolation to generate B2A table
		clutres = getcfg("profile.b2a.smooth.size")
		linebuffered_logfiles = []
		if sys.stdout.isatty():
			linebuffered_logfiles.append(safe_print)
		else:
			linebuffered_logfiles.append(log)
		if self.sessionlogfile:
			linebuffered_logfiles.append(self.sessionlogfile)
		logfiles = Files([LineBufferedStream(
							FilteredStream(Files(linebuffered_logfiles),
										   self.data_encoding,
										   discard="",
										   linesep_in="\n", 
										   triggers=[])), self.recent,
							self.lastmsg])
		tables = [1]
		# Add perceptual tables if not present
		if "A2B0" in profile.tags and not "A2B1" in profile.tags:
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
		A2B = []
		for tableno in tables:
			if "A2B%i" % tableno in profile.tags:
				if ("B2A%i" % tableno in profile.tags and
					profile.tags["B2A%i" % tableno] in results):
					continue
				# Invert A2B
				source = "A2B"
				try:
					result = self.generate_B2A_from_inverse_table(profile,
																  clutres,
																  source,
																  tableno,
																  tableno != 1,
																  logfiles)
				except Exception, exception:
					return exception
				else:
					if result:
						results.append(profile.tags["B2A%i" % tableno])
						A2B.append(profile.tags["A2B%i" % tableno])
					else:
						return False
		return results

	def is_working(self):
		""" Check if the Worker instance is busy. Return True or False. """
		return not getattr(self, "finished", True)
	
	def log(self, msg, fn=safe_print):
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
						  continue_next=False):
		""" Start a calibration and use a progress dialog for progress
		information """
		self.start(consumer, self.calibrate, wkwargs={"remove": remove},
				   progress_msg=progress_msg, continue_next=continue_next,
				   interactive_frame="adjust", pauseable=True)
	
	def measure(self, apply_calibration=True):
		""" Measure the configured testchart """
		cmd, args = self.prepare_dispread(apply_calibration)
		if not isinstance(cmd, Exception):
			if config.get_display_name() == "Untethered":
				cmd, args2 = get_argyll_util("spotread"), ["-v", "-e"]
				if getcfg("extra_args.spotread").strip():
					args2 += parse_argument_string(getcfg("extra_args.spotread"))
				result = self.add_measurement_features(args2, False)
				if isinstance(result, Exception):
					return result
			else:
				args2 = args
			result = self.exec_cmd(cmd, args2)
			if not isinstance(result, Exception) and result:
				self.update_display_name_manufacturer(args[-1] + ".ti3")
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
	
	def pause_continue(self):
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
			return Error(lang.getstr("error.measurement.file_notfile", 
									 inoutfile + ".ti3")), None
		#
		cmd = get_argyll_util("colprof")
		args = []
		args += ["-v"] # verbose
		args += ["-q" + getcfg("profile.quality")]
		args += ["-a" + getcfg("profile.type")]
		if getcfg("profile.type") in ["l", "x", "X"]:
			if getcfg("gamap_saturation"):
				gamap = "S"
			elif getcfg("gamap_perceptual"):
				gamap = "s"
			else:
				gamap = None
			if gamap and getcfg("gamap_profile"):
				args += ["-" + gamap]
				args += [getcfg("gamap_profile")]
				args += ["-t" + getcfg("gamap_perceptual_intent")]
				if gamap == "S":
					args += ["-T" + getcfg("gamap_saturation_intent")]
				if getcfg("gamap_src_viewcond"):
					args += ["-c" + getcfg("gamap_src_viewcond")]
				if getcfg("gamap_out_viewcond"):
					args += ["-d" + getcfg("gamap_out_viewcond")]
			b2a_q = getcfg("profile.quality.b2a")
			if (getcfg("profile.b2a.smooth") and
				getcfg("profile.type") in ("x", "X") and
				not (gamap and getcfg("gamap_profile"))):
				# Disable B2A creation in colprof, B2A is handled
				# by A2B inversion code
				b2a_q = "n"
			if b2a_q and b2a_q != getcfg("profile.quality"):
				args += ["-b" + b2a_q]
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
			# Prepare ChromaticityType tag
			colorants = ti3.get_colorants()
			if colorants and not None in colorants:
				color_rep = ti3.queryv1("COLOR_REP").split("_")
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
			# Smooth B2A
			ti3[0].add_keyword("SMOOTH_B2A",
							   "YES" if getcfg("profile.b2a.smooth")
							   else "NO")
			ti3[0].add_keyword("SMOOTH_B2A_SIZE",
							   getcfg("profile.b2a.smooth.size"))
			if getcfg("profile.black_point_compensation"):
				# Backup TI3
				ti3.write(inoutfile + ".ti3.backup")
				# Apply black point compensation
				ti3[0].apply_bpc()
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
			if not getcfg("calibration.black_point_correction.auto"):
				args += ["-k%s" % getcfg("calibration.black_point_correction")]
			if defaults["calibration.black_point_rate.enabled"] and \
			   float(getcfg("calibration.black_point_correction")) < 1:
				black_point_rate = getcfg("calibration.black_point_rate")
				if black_point_rate:
					args += ["-A%s" % black_point_rate]
			black_luminance = getcfg("calibration.black_luminance", False)
			if black_luminance:
				args += ["-B%f" % black_luminance]
			if verify:
				if calibrate and type(verify) == int:
					args += ["-e%s" % verify]  # Verify final computed curves
				elif self.argyll_version >= [1, 6]:
					args += ["-z"]  # Verify current curves
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
				result = None
				if self.argyll_version >= [1, 1, 0]:
					cal = inoutfile + ".cal"
					cmd, args = (get_argyll_util("dispwin"), 
								 ["-d" + self.get_display(), "-s", cal])
					result = self.exec_cmd(cmd, args, capture_output=True, 
										   skip_scripts=True, silent=False)
					if (isinstance(result, Exception) and
						not isinstance(result, UnloggedInfo)):
						return result, None
				if not result:
					return Error(lang.getstr("calibration.load_error")), None
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
				except (IOError, CGATS.CGATSInvalidError), exception:
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
				self.options_dispcal += [dispcal_extra_args[i]]
		result = self.add_measurement_features(self.options_dispcal)
		if isinstance(result, Exception):
			return result, None
		cmd = get_argyll_util("dispread")
		args = []
		args += ["-v"] # verbose
		if getcfg("argyll.debug"):
			args += ["-D6"]
		result = self.add_measurement_features(args)
		if isinstance(result, Exception):
			return result, None
		if apply_calibration is not False:
			if (self.argyll_version >= [1, 3, 3] and
				(not self.has_lut_access() or
				 not getcfg("calibration.use_video_lut"))):
				if config.get_display_name() == "madVR":
					# Normally -K will automatically reset the video LUT,
					# but when using madVR, we have to do it explicitly
					result = self.reset_cal()
					if (isinstance(result, Exception) and
						not isinstance(result, UnloggedInfo)):
						return result, None
				args += ["-K"]
			else:
				args += ["-k"]
			args += [cal]
		if self.get_instrument_features().get("spectral"):
			args += ["-s"]
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
		args += ["-v"]
		if getcfg("argyll.debug"):
			if self.argyll_version >= [1, 3, 1]:
				args += ["-D6"]
			else:
				args += ["-E6"]
		args += ["-d" + self.get_display()]
		if sys.platform != "darwin" or cal is False:
			# Mac OS X 10.7 Lion needs root privileges when clearing 
			# calibration
			args += ["-c"]
		if cal is True:
			args += [self.get_dispwin_display_profile_argument(
						max(0, min(len(self.displays), 
								   getcfg("display.number")) - 1))]
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
						  self.argyll_version > [1, 1, 1])):
							# -S option is broken on Linux with current Argyll 
							# releases
							args += ["-S" + getcfg("profile.install_scope")]
					args += ["-I"]
					if (sys.platform in ("win32", "darwin") or 
						fs_enc.upper() not in ("UTF8", "UTF-8")) and \
					   re.search("[^\x20-\x7e]", 
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
		if self.argyll_version >= [1, 6]:
			args += ['-B%s' % getcfg("tc_black_patches")]
		args += ['-s%s' % getcfg("tc_single_channel_patches")]
		args += ['-g%s' % getcfg("tc_gray_patches")]
		args += ['-m%s' % getcfg("tc_multi_steps")]
		if self.argyll_version >= [1, 6, 0]:
			args += ['-b%s' % getcfg("tc_multi_bcc_steps")]
		tc_algo = getcfg("tc_algo")
		if getcfg("tc_fullspread_patches") > 0:
			args += ['-f%s' % config.get_total_patches()]
			if tc_algo:
				args += ['-' + tc_algo]
			if tc_algo in ("i", "I"):
				args += ['-a%s' % getcfg("tc_angle")]
			if tc_algo == "":
				args += ['-A%s' % getcfg("tc_adaption")]
			if self.argyll_version >= [1, 3, 3]:
				args += ['-N%s' % getcfg("tc_neutral_axis_emphasis")]
			if (self.argyll_version == [1, 1, "RC1"] or
				self.argyll_version >= [1, 1]):
				args += ['-G']
		else:
			args += ['-f0']
		if getcfg("tc_precond") and getcfg("tc_precond_profile"):
			args += ['-c']
			args += [getcfg("tc_precond_profile")]
		if getcfg("tc_filter"):
			args += ['-F%s,%s,%s,%s' % (getcfg("tc_filter_L"), 
										getcfg("tc_filter_a"), 
										getcfg("tc_filter_b"), 
										getcfg("tc_filter_rad"))]
		if (self.argyll_version >= [1, 6, 2] and
			("-c" in args or self.argyll_version >= [1, 6, 3])):
			args += ['-V%s' % (1 + getcfg("tc_dark_emphasis") * 3)]
		if self.argyll_version == [1, 1, "RC2"] or self.argyll_version >= [1, 1]:
			args += ['-p%s' % getcfg("tc_gamma")]
		if getcfg("extra_args.targen").strip():
			# Disallow -d and -D as the testchart editor only supports
			# video RGB (-d3)
			args += filter(lambda arg: not arg.lower().startswith("-d"),
						   parse_argument_string(getcfg("extra_args.targen")))
		self.options_targen = list(args)
		args += [inoutfile]
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
		if (percentage and time() > self.starttime + 3 and
			self.progress_wnd is getattr(self, "terminal", None)):
			# We no longer need keyboard interaction, switch over to
			# progress dialog
			wx.CallAfter(self.swap_progress_wnds)
		if getattr(self.progress_wnd, "original_msg", None) and \
		   msg != self.progress_wnd.original_msg:
			# UGLY HACK: This 'safe_print' call fixes a GTK assertion and 
			# segfault under Arch Linux when setting the window title
			safe_print("")
			self.progress_wnd.SetTitle(self.progress_wnd.original_msg)
			self.progress_wnd.original_msg = None
		if percentage:
			if "Setting up the instrument" in msg or \
			   "Commencing device calibration" in msg or \
			   "Calibration complete" in msg:
				self.recent.clear()
				msg = ""
			keepGoing, skip = self.progress_wnd.Update(math.ceil(percentage), 
													   msg + "\n" + 
													   lastmsg)
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
		if (hasattr(self.progress_wnd, "pause_continue") and
			"read stopped at user request!" in lastmsg):
			self.progress_wnd.pause_continue.Enable()
		if not keepGoing:
			if getattr(self, "subprocess", None) and \
			   not getattr(self, "subprocess_abort", False):
				if debug:
					safe_print('[D] calling quit_terminate_cmd')
				self.abort_subprocess(True)
			elif not getattr(self, "thread_abort", False):
				if debug:
					safe_print('[D] thread_abort')
				self.abort_subprocess(True)
		if self.finished is True:
			return
		if (not self.activated and self.progress_wnd.IsShownOnScreen() and
			(not wx.GetApp().IsActive() or not self.progress_wnd.IsActive()) and
			not getattr(self.progress_wnd, "dlg", None)):
		   	self.activated = True
			self.progress_wnd.Raise()

	def progress_dlg_start(self, progress_title="", progress_msg="", 
						   parent=None, resume=False):
		""" Start a progress dialog, replacing existing one if present """
		if getattr(self, "progress_dlg", None) and not resume:
			self.progress_dlg.Destroy()
			self.progress_dlg = None
		if self._progress_wnd and \
		   self.progress_wnd is getattr(self, "terminal", None):
			self.terminal.stop_timer()
			self.terminal.Hide()
		if self.finished is True:
			return
		pauseable = getattr(self, "pauseable", False)
		if getattr(self, "progress_dlg", None):
			self.progress_wnd = self.progress_dlg
			self.progress_wnd.MakeModal(True)
			# UGLY HACK: This 'safe_print' call fixes a GTK assertion and 
			# segfault under Arch Linux when setting the window title
			safe_print("")
			self.progress_wnd.SetTitle(progress_title)
			self.progress_wnd.Update(0, progress_msg)
			if hasattr(self.progress_wnd, "pause_continue"):
				self.progress_wnd.pause_continue.Show(pauseable)
				self.progress_wnd.Layout()
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
											   keyhandler=self.terminal_key_handler,
											   pauseable=pauseable)
			self.progress_wnd = self.progress_dlg
		self.progress_wnd.original_msg = progress_msg
	
	def quit_terminate_cmd(self):
		""" Forcefully abort the current subprocess.
		
		Try to gracefully exit first by sending common Argyll CMS abort
		keystrokes (ESC), forcefully terminate the subprocess if not
		reacting
		
		"""
		if debug:
			safe_print('[D] safe_quit')
		if getattr(self, "subprocess", None) and \
		   (hasattr(self.subprocess, "poll") and 
			self.subprocess.poll() is None) or \
		   (hasattr(self.subprocess, "isalive") and 
			self.subprocess.isalive()):
			if debug or test:
				safe_print('User requested abort')
			try:
				if self.measure_cmd and hasattr(self.subprocess, "send"):
					try:
						if self.subprocess.after == "Current":
							# Stop measurement
							self.safe_send(" ")
							sleep(1)
						ts = time()
						while getattr(self, "subprocess", None) and \
						   self.subprocess.isalive():
							self.safe_send("\x1b")
							if time() > ts + 9:
								break
							sleep(.5)
					except Exception, exception:
						self.logger.exception("Exception")
				if getattr(self, "subprocess", None) and \
				   (hasattr(self.subprocess, "poll") and 
					self.subprocess.poll() is None) or \
				   (hasattr(self.subprocess, "isalive") and 
					self.subprocess.isalive()):
					self.logger.info("Trying to terminate subprocess...")
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
						self.logger.info("Trying to terminate subprocess forcefully...")
						self.subprocess.terminate(force=True)
			except Exception, exception:
				self.logger.exception("Exception")
			if debug:
				safe_print('[D] end try')
		elif debug:
			safe_print('[D] subprocess: %r' % getattr(self, "subprocess", None))
			safe_print('[D] subprocess_abort: %r' % getattr(self, "subprocess_abort", 
													 False))
			if getattr(self, "subprocess", None):
				safe_print('[D] subprocess has poll: %r' % hasattr(self.subprocess, 
															"poll"))
				if hasattr(self.subprocess, "poll"):
					safe_print('[D] subprocess.poll(): %r' % self.subprocess.poll())
				safe_print('[D] subprocess has isalive: %r' % hasattr(self.subprocess, 
															   "isalive"))
				if hasattr(self.subprocess, "isalive"):
					safe_print('[D] subprocess.isalive(): %r' % self.subprocess.isalive())
	
	def report(self, report_calibrated=True):
		""" Report on calibrated or uncalibrated display device response """
		cmd, args = self.prepare_dispcal(calibrate=False)
		if isinstance(cmd, Exception):
			return cmd
		if args:
			if report_calibrated:
				args += ["-r"]
			else:
				args += ["-R"]
		return self.exec_cmd(cmd, args, capture_output=True, skip_scripts=True)
	
	def reset_cal(self):
		cmd, args = self.prepare_dispwin(False)
		result = self.exec_cmd(cmd, args, capture_output=True, 
							   skip_scripts=True, silent=False)
		return result
	
	def safe_send(self, bytes):
		self.send_buffer = bytes
		return True
	
	def _safe_send(self, bytes, retry=3):
		""" Safely send a keystroke to the current subprocess """
		for i in xrange(0, retry):
			self.logger.info("Sending key(s) %r (%i)" % (bytes, i + 1))
			try:
				wrote = self.subprocess.send(bytes)
			except Exception, exception:
				self.logger.exception("Exception: %s" % safe_unicode(exception))
			else:
				if wrote == len(bytes):
					return True
			sleep(.25)
		return False
	
	def set_argyll_version(self, name, silent=False, cfg=False):
		self.set_argyll_version_from_string(get_argyll_version_string(name,
																	  silent),
											cfg)
	
	def set_argyll_version_from_string(self, argyll_version_string, cfg=True):
		self.argyll_version_string = argyll_version_string
		if cfg:
			setcfg("argyll.version", argyll_version_string)
		self.argyll_version = parse_argyll_version_string(argyll_version_string)
	
	def set_terminal_cgats(self, cgats_filename):
		try:
			self.terminal.cgats = CGATS.CGATS(cgats_filename)
		except (IOError, CGATS.CGATSInvalidError), exception:
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
				searchpaths += [os.path.join(dir_, "ArgyllCMS", name)
								for dir_ in paths]
			else:
				searchpaths += [os.path.join(dir_, "ArgyllCMS", name)
								for dir_ in [defaultpaths.appdata,
											 defaultpaths.library]]
		searchpaths += [os.path.join(dir_, "color", name) for dir_ in paths]
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
		""" Check if the Spyder 4 calibration file exists in any of the known
		locations valid for the chosen Argyll CMS version. """
		if self.argyll_version < [1, 3, 6]:
			# We couldn't use it even if it exists
			return False
		return self.argyll_support_file_exists("spyd4cal.bin")

	def start(self, consumer, producer, cargs=(), ckwargs=None, wargs=(), 
			  wkwargs=None, progress_title=appname, progress_msg="", 
			  parent=None, progress_start=100, resume=False, 
			  continue_next=False, stop_timers=True, interactive_frame="",
			  pauseable=False):
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
		if progress_start < 100:
			progress_start = 100
		self.activated = False
		self.cmdrun = False
		self.finished = False
		self.instrument_calibration_complete = False
		self.instrument_place_on_screen_msg = False
		self.instrument_sensor_position_msg = False
		self.is_ambient_measuring = interactive_frame == "ambient"
		self.lastcmdname = None
		self.pauseable = pauseable
		self.paused = False
		self.resume = resume
		self.subprocess_abort = False
		self.starttime = time()
		self.thread_abort = False
		if self.interactive:
			self.progress_start_timer = wx.Timer()
			if getattr(self, "progress_wnd", None) and \
			   self.progress_wnd is getattr(self, "progress_dlg", None):
				self.progress_dlg.Destroy()
				self.progress_dlg = None
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
			self.progress_start_timer = wx.CallLater(progress_start, 
													 self.progress_dlg_start, 
													 progress_title, 
													 progress_msg, parent,
													 resume)
		self.thread = delayedresult.startWorker(self._generic_consumer, 
												producer, [consumer, 
														   continue_next] + 
												list(cargs), ckwargs, wargs, 
												wkwargs)
		return True
	
	def stop_progress(self):
		if getattr(self, "progress_wnd", False):
			if getattr(self.progress_wnd, "dlg", None):
				self.progress_wnd.dlg.EndModal(wx.ID_CANCEL)
				self.progress_wnd.dlg = None
			self.progress_wnd.stop_timer()
			self.progress_wnd.MakeModal(False)
			self.progress_wnd.Close()
	
	def swap_progress_wnds(self):
		""" Swap the current interactive window with a progress dialog """
		parent = self.terminal.GetParent()
		if isinstance(self.terminal, DisplayAdjustmentFrame):
			title = lang.getstr("calibration")
		else:
			title = self.terminal.GetTitle()
		self.progress_dlg_start(title, "", parent, self.resume)
	
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
	
	def calculate_gamut(self, profile_path):
		"""
		Calculate gamut, volume, and coverage % against sRGB and Adobe RGB.
		
		Return gamut volume (int, scaled to sRGB = 1.0) and
		coverage (dict) as tuple.
		
		"""
		outname = os.path.splitext(profile_path)[0]
		gamut_volume = None
		gamut_coverage = {}
		# Create profile gamut and vrml
		if (sys.platform == "win32" and
			re.search("[^\x20-\x7e]", os.path.basename(profile_path))):
			# Avoid problems with encoding
			profile_path = win32api.GetShortPathName(profile_path)
		result = self.exec_cmd(get_argyll_util("iccgamut"),
							   ["-v", "-w", "-ir", profile_path],
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
		name = os.path.splitext(profile_path)[0]
		gamfilename = name + ".gam"
		wrlfilename = name + ".wrl"
		tmpfilenames = [gamfilename, wrlfilename]
		for key, src in (("srgb", "sRGB"), ("adobe-rgb", "ClayRGB1998")):
			if not isinstance(result, Exception) and result:
				# Create gamut view and intersection
				src_path = get_data_path("ref/%s.gam" % src)
				if not src_path:
					continue
				outfilename = outname + (" vs %s.wrl" % src)
				tmpfilenames.append(outfilename)
				result = self.exec_cmd(get_argyll_util("viewgam"),
									   ["-cw", "-t.75", "-s", src_path, "-cn",
										"-t.25", "-s", gamfilename, "-i",
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
					if getcfg("vrml.compress"):
						# Compress gam and wrl files using gzip
						if filename.endswith(".wrl"):
							filename = filename[:-4] + ".wrz"
						else:
							filename = filename + ".gz"
						with GzipFileProper(tmpfilename + ".gz", "wb") as gz:
							# Always use original filename with '.gz' extension,
							# that way the filename in the header will be correct
							with open(tmpfilename, "rb") as infile:
								gz.write(infile.read())
						# Remove uncompressed file
						os.remove(tmpfilename)
						tmpfilename = tmpfilename + ".gz"
					if tmpfilename != filename:
						# Rename the file if filename is different
						if os.path.exists(filename):
							os.remove(filename)
						os.rename(tmpfilename, filename)
				except Exception, exception:
					safe_print(safe_unicode(exception))
		elif result:
			# Exception
			safe_print(safe_unicode(result))
		return gamut_volume, gamut_coverage

	def calibrate(self, remove=False):
		""" Calibrate the screen and process the generated file(s). """
		capture_output = not sys.stdout.isatty()
		cmd, args = self.prepare_dispcal()
		if not isinstance(cmd, Exception):
			result = self.exec_cmd(cmd, args, capture_output=capture_output)
		else:
			result = cmd
		if not isinstance(result, Exception) and result:
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
								safe_print(exception)
		result2 = self.wrapup(not isinstance(result, UnloggedInfo) and result,
							  remove or isinstance(result, Exception) or
							  not result)
		if isinstance(result2, Exception):
			if isinstance(result, Exception):
				result = Error(safe_unicode(result) + "\n\n" +
							   safe_unicode(result2))
			else:
				result = result2
		elif not isinstance(result, Exception) and result:
			setcfg("last_cal_path", dst_pathname + ".cal")
			setcfg("calibration.file.previous", getcfg("calibration.file"))
			if (getcfg("profile.update") or
				self.dispcal_create_fast_matrix_shaper):
				setcfg("last_cal_or_icc_path", dst_pathname + profile_ext)
				setcfg("last_icc_path", dst_pathname + profile_ext)
				setcfg("calibration.file", dst_pathname + profile_ext)
			else:
				setcfg("calibration.file", dst_pathname + ".cal")
				setcfg("last_cal_or_icc_path", dst_pathname + ".cal")
		return result
	
	def chart_lookup(self, cgats, profile, as_ti3=False, fields=None,
					 check_missing_fields=False, function="f", pcs="l",
					 intent="r", bt1886=None, add_white_patches=True,
					 raise_exceptions=False):
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
				cgats = CGATS.CGATS(str(cgats))
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
															add_white_patches)
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
													  intent, add_white_patches)
		except Exception, exception:
			if raise_exceptions:
				raise exception
			InfoDialog(self.owner, msg=safe_unicode(exception), 
					   ok=lang.getstr("ok"), bitmap=geticon(32, "dialog-error"))
		return ti1, ti3_ref, gray
	
	def ti1_lookup_to_ti3(self, ti1, profile, function="f", pcs=None,
						  intent="r", add_white_patches=True):
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
		
		if colorspace == "RGB" and add_white_patches:
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
			while len(data.queryi(white_rgb)) < 4:  # add white patches
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
			
		odata = self.xicclu(profile, idata, intent, function, pcs=pcs,
							scale=100, use_icclu=use_icclu)
		
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
		
		self.wrapup(False)

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
		if debug:
			safe_print(ti3)
		return ti1, ti3, map(list, gray)
	
	def ti3_lookup_to_ti1(self, ti3, profile, fields=None, intent="r",
						  add_white_patches=True):
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
			wp = [wp] * 4
			safe_print("Added 4 white patches")
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
			if config.get_display_name() == "madVR" and colormanaged:
				args += ["-V"]
			if cal_path:
				if (self.argyll_version >= [1, 3, 3] and
					(not self.has_lut_access() or
					 not getcfg("calibration.use_video_lut"))):
					if config.get_display_name() == "madVR":
						# Normally -K will automatically reset the video LUT,
						# but when using madVR, we have to do it explicitly
						result = self.reset_cal()
						if (isinstance(result, Exception) and
							not isinstance(result, UnloggedInfo)):
							return result, None
					args += ["-K"]
				else:
					args += ["-k"]
				args += [cal_path]
			if getcfg("extra_args.dispread").strip():
				args += parse_argument_string(getcfg("extra_args.dispread"))
		result = self.add_measurement_features(args,
											   cmd == get_argyll_util("dispread"))
		if isinstance(result, Exception):
			return result
		if config.get_display_name() != "Untethered":
			args += [os.path.splitext(ti1_path)[0]]
		return self.exec_cmd(cmd, args, skip_scripts=True)

	def wrapup(self, copy=True, remove=True, dst_path=None, ext_filter=None):
		"""
		Wrap up - copy and/or clean temporary file(s).
		
		"""
		if debug: safe_print("[D] wrapup(copy=%s, remove=%s)" % (copy, remove))
		if not self.tempdir or not os.path.isdir(self.tempdir):
			return # nothing to do
		while self.sessionlogfiles:
			self.sessionlogfiles.popitem()[1].close()
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
				if dst_path is None:
					dst_path = os.path.join(getcfg("profile.save_path"), 
											getcfg("profile.name.expanded"), 
											getcfg("profile.name.expanded") + 
											".ext")
				result = check_create_dir(os.path.dirname(dst_path))
				if isinstance(result, Exception):
					remove = False
				else:
					for basename in src_listdir:
						name, ext = os.path.splitext(basename)
						if ext_filter is None or ext.lower() in ext_filter:
							src = os.path.join(self.tempdir, basename)
							dst = os.path.join(os.path.dirname(dst_path), basename)
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
		wx.CallAfter(self.parse, txt)
	
	def xicclu(self, profile, idata, intent="r", direction="f", order="n",
			   pcs=None, scale=1, cwd=None, startupinfo=None, raw=False,
			   logfile=None, use_icclu=False, use_cam_clipping=False):
		"""
		Call xicclu, feed input floats into stdin, return output floats.
		
		input data needs to be a list of 3-tuples (or lists) with floats,
		alternatively a list of strings.
		output data will be returned in same format, or as list of strings
		if 'raw' is true.
		
		"""
		with Xicclu(profile, intent, direction, order, pcs, scale, cwd,
					startupinfo, use_icclu, use_cam_clipping, logfile,
					worker=self) as xicclu:
			xicclu(idata)
		return xicclu.get(raw)


class Xicclu(Worker):
	def __init__(self, profile, intent="r", direction="f", order="n",
				 pcs=None, scale=1, cwd=None, startupinfo=None, use_icclu=False,
				 use_cam_clipping=False, logfile=None, worker=None):
		Worker.__init__(self)
		self.logfile = logfile
		self.worker = worker
		self.temp = False
		utilname = "icclu" if use_icclu else "xicclu"
		xicclu = get_argyll_util(utilname)
		if not xicclu:
			raise NotImplementedError(lang.getstr("argyll.util.not_found",
												  utilname))
		if not isinstance(profile, ICCP.ICCProfile):
			profile = ICCP.ICCProfile(profile)
		if not cwd:
			cwd = self.create_tempdir()
		if isinstance(cwd, Exception):
			raise cwd
		if not profile.fileName:
			fd, profile.fileName = tempfile.mkstemp(profile_ext, dir=cwd)
			profile.write(os.fdopen(fd, "wb"))
			profile.close()
			self.temp = True
		profile_basename = os.path.basename(profile.fileName)
		profile_path = os.path.join(cwd, profile_basename)
		if not os.path.isfile(profile_path):
			profile.write(profile_path)
			self.temp = True
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
			if "A2B0" in profile.tags and ("B2A0" in profile.tags or
										   direction == "if"):
				args.append("-a")
			if use_cam_clipping:
				args.append("-b")
		args.append("-f" + direction)
		if profile.profileClass not in ("abst", "link"):
			args.append("-i" + intent)
			if order != "n":
				args.append("-o" + order)
		if pcs and profile.profileClass != "link":
			args.append("-p" + pcs)
		args.append(self.profile_path)
		if debug or verbose > 1:
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
						 os.path.basename(xicclu), args[1:], cwd=cwd)
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
			p.stdin.write("\n")
			p.stdin.close()
		if p.wait():
			# Error
			self.stderr.seek(0)
			raise IOError(self.stderr.read())
		if self.logfile:
			self.logfile.write("\n")
		if self.temp:
			os.remove(self.profile_path)
			if self.tempdir and not os.listdir(self.tempdir):
				self.wrapup(False)
	
	def get(self, raw=False):
		self.stdout.seek(0)
		odata = self.stdout.readlines()
		if raw:
			return odata
		parsed = []
		j = 0
		for i, line in enumerate(odata):
			line = line.strip()
			if line.startswith("["):
				if j > 0 and (debug or verbose > 3):
					self.log(j - 1, odata[j - 1], line)
				continue
			elif not "->" in line:
				if line and (debug or verbose > 3):
					self.log(line)
				continue
			elif debug or verbose > 3:
				self.log(line)
			parts = line.split("->")[-1].strip().split()
			if parts.pop() == "(clip)":
				parts.pop()
			parsed.append([float(n) for n in parts])
			j += 1
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
