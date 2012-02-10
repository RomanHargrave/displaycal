#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Runtime configuration and user settings parser
"""

import ConfigParser
ConfigParser.DEFAULTSECT = "Default"
from decimal import Decimal
import locale
import math
import os
import sys
from time import gmtime, strftime, timezone
if sys.platform == "win32":
	import _winreg

from argyll_names import viewconds, intents
from defaultpaths import appdata, commonappdata
if sys.platform == "win32":
	from defaultpaths import commonprogramfiles
elif sys.platform == "darwin":
	from defaultpaths import appsupport, appsupport_home, prefs, prefs_home
else:
	from defaultpaths import (xdg_config_dir_default, xdg_config_home, 
							  xdg_data_home, xdg_data_home_default, 
							  xdg_data_dirs)
from defaultpaths import autostart, autostart_home
from meta import name as appname, build, lastmod, version
from options import ascii, debug, verbose
from safe_print import enc, fs_enc, original_codepage
from util_io import StringIOu as StringIO
from util_os import expanduseru, expandvarsu, getenvu, is_superuser, listdir_re
from util_str import safe_unicode
import encodedstdio

# Runtime configuration

if ascii:
	enc = "ASCII"

exe = unicode(sys.executable, fs_enc)
exedir = os.path.dirname(exe)

isexe = sys.platform != "darwin" and getattr(sys, "frozen", False)

if isexe and os.getenv("_MEIPASS2"):
	os.environ["_MEIPASS2"] = os.getenv("_MEIPASS2").replace("/", os.path.sep)

pyfile = exe if isexe else os.path.join(os.path.dirname(__file__), 
										appname + ".py")
pypath = exe if isexe else os.path.abspath(unicode(pyfile, fs_enc))
pydir = os.path.dirname(pypath)
pyname, pyext = os.path.splitext(os.path.basename(pypath))
isapp = sys.platform == "darwin" and \
		exe.split(os.path.sep)[-3:-1] == ["Contents", "MacOS"] and \
		os.path.isfile(os.path.join(exedir, pyname))
if isapp:
	if pydir.split(os.path.sep)[-1] == "site-packages.zip":
		pydir = os.path.abspath(os.path.join(pydir, "..", "..", ".."))

data_dirs = [pydir]

if sys.platform == "win32":
	if pydir.lower().startswith(exedir.lower()) and pydir != exedir:
		# We are installed in a subfolder of the executable directory (e.g. 
		# C:\Python26\Lib\site-packages\dispcalGUI) - we nee to add 
		# the executable directory to the data directories so files in
		# subfolders of the executable directory which are not in 
		# Lib\site-packages\dispcalGUI can be found
		# (e.g. Scripts\dispcalGUI-apply-profiles)
		data_dirs += [exedir]
	btn_width_correction = 20
	script_ext = ".cmd"
	scale_adjustment_factor = 1.0
	config_sys = os.path.join(commonappdata[0], appname)
	confighome = os.path.join(appdata, appname)
	datahome = os.path.join(appdata, appname)
	logdir = os.path.join(datahome, "logs")
	data_dirs += [datahome]
	data_dirs += [os.path.join(dir_, appname) for dir_ in commonappdata]
	del dir_
	data_dirs += [os.path.join(commonprogramfiles, appname)]
	exe_ext = ".exe"
	profile_ext = ".icm"
else:
	btn_width_correction = 10
	if sys.platform == "darwin":
		script_ext = ".command"
		mac_create_app = True
		scale_adjustment_factor = 1.0
		config_sys = os.path.join(prefs, appname)
		confighome = os.path.join(prefs_home, appname)
		datahome = os.path.join(appsupport_home, appname)
		logdir = os.path.join(expanduseru("~"), "Library", 
							  "Logs", appname)
		data_dirs += [datahome, os.path.join(appsupport, appname)]
	else:
		script_ext = ".sh"
		scale_adjustment_factor = 1.0
		config_sys = os.path.join(xdg_config_dir_default, appname)
		confighome = os.path.join(xdg_config_home, appname)
		datahome = os.path.join(xdg_data_home, appname)
		datahome_default = os.path.join(xdg_data_home_default, appname)
		logdir = os.path.join(datahome, "logs")
		data_dirs += [datahome]
		if not datahome_default in data_dirs:
			data_dirs += [datahome_default]
		data_dirs += [os.path.join(dir_, appname) for dir_ in xdg_data_dirs]
		del dir_
	exe_ext = ""
	profile_ext = ".icc"

storage = os.path.join(datahome, "storage")

resfiles = [
	"lang/en.json",
	"theme/brace-r.png",
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
	"theme/icons/16x16/rgbsquares.png",
	"theme/icons/16x16/stock_lock.png",
	"theme/icons/16x16/stock_lock-open.png",
	"theme/icons/16x16/web.png",
	# "theme/icons/16x16/stock_refresh.png",
	"beep.wav",
	"camera_shutter.wav",
	"test.cal",
	"xrc/gamap.xrc",
	"xrc/main.xrc",
	"xrc/mainmenu.xrc"
]

bitmaps = {}

def getbitmap(name):
	"""
	Create (if necessary) and return a named bitmap.
	
	name has to be a relative path to a png file, omitting the extension, e.g. 
	'theme/mybitmap' or 'theme/icons/16x16/myicon', which is searched for in 
	the data directories. If a matching file is not found, a placeholder 
	bitmap is returned.
	The special name 'empty' will always return a transparent bitmap of the 
	given size, e.g. '16x16/empty' or just 'empty' (size defaults to 16x16 
	if not given).
	
	"""
	from wxaddons import wx
	if not name in bitmaps:
		parts = name.split("/")
		if parts[-1] == "empty":
			w = 16
			h = 16
			if len(parts) > 1:
				size = parts[-2].split("x")
				if len(size) == 2:
					try:
						w, h = map(int, size)
					except ValueError:
						pass
			bitmaps[name] = wx.EmptyBitmap(w, h, depth=-1)
			dc = wx.MemoryDC()
			dc.SelectObject(bitmaps[name])
			dc.SetBackground(wx.Brush("black"))
			dc.Clear()
			dc.SelectObject(wx.NullBitmap)
			bitmaps[name].SetMaskColour("black")
		else:
			path = None
			if parts[-1] == appname:
				path = get_data_path(os.path.join(parts[-2], "apps", parts[-1]) + ".png")
			if not path:
				path = get_data_path(os.path.sep.join(parts) + ".png")
			if path:
				bitmaps[name] = wx.Bitmap(path)
			else:
				w = 32
				h = 32
				if len(parts) > 1:
					size = parts[-2].split("x")
					if len(size) == 2:
						try:
							w, h = map(int, size)
						except ValueError:
							pass
				bitmaps[name] = wx.ArtProvider.GetBitmap(wx.ART_MISSING_IMAGE, 
														 size=(w, h))
	return bitmaps[name]


def get_bitmap_as_icon(size, name):
	""" Like geticon, but return a wx.Icon instance """
	from wxaddons import wx
	icon = wx.EmptyIcon()
	if sys.platform == "darwin" and wx.VERSION >= (2, 9) and size > 128:
		# FIXME: wxMac 2.9 doesn't support icon sizes above 128
		size = 128
	bmp = geticon(size, name)
	icon.CopyFromBitmap(bmp)
	return icon


def get_display_name():
	""" Return name of currently configured display """
	n = getcfg("display.number") - 1
	displays = getcfg("displays").split(os.pathsep)
	if n >= 0 and n < len(displays):
		return displays[n].split("@")[0].strip()
	return ""


def get_icon_bundle(sizes, name):
	""" Return a wx.IconBundle with given icon sizes """
	from wxaddons import wx
	iconbundle = wx.IconBundle()
	for size in sizes:
		iconbundle.AddIcon(get_bitmap_as_icon(size, name))
	return iconbundle


def get_instrument_name():
	""" Return name of currently configured instrument """
	n = getcfg("comport.number") - 1
	instrument_names = getcfg("instruments").split(os.pathsep)
	if n >= 0 and n < len(instrument_names):
		return instrument_names[n]
	return ""


def geticon(size, name):
	""" Convenience function for getbitmap('theme/icons/<size>/<name>'). """
	return getbitmap("theme/icons/%(size)sx%(size)s/%(name)s" % 
					 {"size": size, "name": name})


def get_data_path(relpath, rex=None):
	"""
	Search data_dirs for relpath and return the path or a file list.
	
	If relpath is a file, return the full path, if relpath is a directory,
	return a list of files in the intersection of searched directories.
	
	"""
	if not relpath:
		return None
	intersection = []
	paths = []
	for dir_ in data_dirs:
		curpath = os.path.join(dir_, relpath)
		if os.path.exists(curpath):
			if os.path.isdir(curpath):
				try:
					filelist = listdir_re(curpath, rex)
				except Exception, exception:
					from log import safe_print
					safe_print(u"Error - directory '%s' listing failed: %s" % 
							   tuple(safe_unicode(s) for s in (curpath, exception)))
				else:
					for filename in filelist:
						if not filename in intersection:
							intersection += [filename]
							paths += [os.path.join(curpath, filename)]
			else:
				return curpath
	return None if len(paths) == 0 else paths


def runtimeconfig(pyfile):
	"""
	Configure remaining runtime options and return runtype.
	
	You need to pass in a path to the calling script (e.g. use the __file__ 
	attribute).
	
	"""
	from log import setup_logging
	setup_logging()
	if debug or verbose >= 1:
		from log import safe_print
	if debug:
		safe_print("[D] pydir:", pydir)
	if isapp:
		appdir = os.path.abspath(os.path.join(pydir, "..", "..", ".."))
		if debug:
			safe_print("[D] appdir:", appdir)
		if appdir not in data_dirs and os.path.isdir(appdir):
			data_dirs.insert(1, appdir)
		runtype = ".app"
	elif isexe:
		if debug:
			safe_print("[D] _MEIPASS2 or pydir:", getenvu("_MEIPASS2", exedir))
		if getenvu("_MEIPASS2", exedir) not in data_dirs:
			data_dirs.insert(1, getenvu("_MEIPASS2", exedir))
		runtype = exe_ext
	else:
		pydir_parent = os.path.dirname(pydir)
		if debug:
			safe_print("[D] dirname(os.path.abspath(sys.argv[0])):", 
					   os.path.dirname(os.path.abspath(sys.argv[0])))
			safe_print("[D] pydir parent:", pydir_parent)
		if os.path.dirname(os.path.abspath(sys.argv[0])) == pydir_parent and \
		   pydir_parent not in data_dirs:
			# Add the parent directory of the package directory to our list
			# of data directories if it is the directory containing the 
			# currently run script (e.g. when running from source)
			data_dirs.insert(1, pydir_parent)
		runtype = pyext
	for dir_ in sys.path:
		if not isinstance(dir_, unicode):
			dir_ = unicode(dir_, fs_enc)
		dir_ = os.path.abspath(os.path.join(dir_, appname))
		if dir_ not in data_dirs and os.path.isdir(dir_):
			data_dirs.append(dir_)
			if debug:
				safe_print("[D] from sys.path:", dir_)
	if sys.platform not in ("darwin", "win32"):
		data_dirs.extend([os.path.join(dir_, "doc", appname + "-" + version) 
						  for dir_ in xdg_data_dirs + [xdg_data_home]])
		data_dirs.extend([os.path.join(dir_, "doc", "packages", appname) 
						  for dir_ in xdg_data_dirs + [xdg_data_home]])
		data_dirs.extend([os.path.join(dir_, "doc", appname) 
						  for dir_ in xdg_data_dirs + [xdg_data_home]])
		data_dirs.extend([os.path.join(dir_, "doc", appname.lower())  # Debian
						  for dir_ in xdg_data_dirs + [xdg_data_home]])
		data_dirs.extend([os.path.join(dir_, "icons", "hicolor") 
						  for dir_ in xdg_data_dirs + [xdg_data_home]])
	if debug:
		safe_print("[D] Data files search paths:\n[D]", "\n[D] ".join(data_dirs))
	defaultmmode = defaults["measurement_mode"]
	defaultptype = defaults["profile.type"]
	defaultchart = testchart_defaults.get(defaultptype, 
										  testchart_defaults["s"])[None]
	defaults["testchart.file"] = get_data_path(os.path.join("ti1", 
															defaultchart))
	defaults["testchart.file.backup"] = defaults["testchart.file"]
	defaults["profile_verification_chart"] = get_data_path(os.path.join("ref", 
															"verify.ti1"))
	defaults["gamap_profile"] = get_data_path(os.path.join("ref", "sRGB.icm"))
	return runtype

# User settings

cfg = ConfigParser.RawConfigParser()
cfg.optionxform = str

valid_ranges = {
	"gamma": [0.000001, 10],
	"trc": [0.000001, 10],
	"calibration.ambient_viewcond_adjust.lux": [0, sys.maxint],
	"calibration.black_luminance": [0.000001, 100000],
	"calibration.black_output_offset": [0, 1],
	"calibration.black_point_correction": [0, 1],
	"calibration.black_point_rate": [0.05, 20],
	"calibration.luminance": [0.000001, 100000],
	"gamap_default_intent": [0, 3],
	"whitepoint.colortemp": [1000, 15000],
}

valid_values = {
	"calibration.quality": ["v", "l", "m", "h", "u"],
	"measurement_mode": [None, "c", "l"],
	"gamap_perceptual_intent": intents,
	"gamap_saturation_intent": intents,
	"gamap_src_viewcond": viewconds,
	"gamap_out_viewcond": ["mt", "mb", "md", "jm", "jd"],
	"profile.install_scope": ["l", "u"],
	"profile.quality": ["l", "m", "h", "u"],
	"profile.type": ["g", "G", "l", "s", "S", "x", "X"],
	"tc_algo": ["", "t", "r", "R", "q", "Q", "i", "I"],  # Q = Argyll >= 1.1.0
	"trc": ["240", "709", "l", "s"],
	"trc.type": ["g", "G"],
	"whitepoint.colortemp.locus": ["t", "T"]
}

defaults = {
	"allow_skip_sensor_cal": 0,
	"argyll.debug": 0,
	"argyll.dir": expanduseru("~"), # directory
	"drift_compensation.blacklevel": 0,
	"drift_compensation.whitelevel": 0,
	"calibration.ambient_viewcond_adjust": 0,
	"calibration.ambient_viewcond_adjust.lux": 500.0,
	"calibration.black_luminance": 0.000001,
	"calibration.black_output_offset": 1.0,
	"calibration.black_point_correction": 0.0,
	"calibration.black_point_correction_choice.show": 1,
	"calibration.black_point_rate": 4.0,
	"calibration.black_point_rate.enabled": 0,
	"calibration.file": None,
	"calibration.interactive_display_adjustment": 1,
	"calibration.luminance": 120.0,
	"calibration.quality": "m",
	"calibration.update": 0,
	"colorimeter_correction.testchart": "ccxxmake-s3.ti1",
	"colorimeter_correction_matrix_file": ":",
	"color.dir": os.path.join(commonappdata[0] if is_superuser() else 
							  appdata, "color"),
	"comport.number": 1,
	"copyright": "Created with %s %s and Argyll CMS" % (appname, 
														version),
	"dimensions.measureframe": "0.5,0.5,1.5",
	"dimensions.measureframe.unzoomed": "0.5,0.5,1.5",
	"display.number": 1,
	"display_lut.link": 1,
	"display_lut.number": 1,
	"displays": "",
	"extra_args.colprof": "",
	"extra_args.dispcal": "",
	"extra_args.dispread": "",
	"extra_args.spotread": "",
	"gamap_profile": "",
	"gamap_perceptual": 0,
	"gamap_perceptual_intent": "la",
	"gamap_saturation": 0,
	"gamap_saturation_intent": "s",
	"gamap_default_intent": 0,
	"gamma": 2.2,
	"instruments": "",
	"log.autoshow": int(not(hasattr(sys.stdout, "isatty") and 
							sys.stdout.isatty())),
	"log.show": 0,
	"lang": "en",
	"lut_viewer.show": 0,
	"lut_viewer.show_actual_lut": 0,
	"measurement_mode": "l",
	"measurement_mode.adaptive": 0,
	"measurement_mode.highres": 0,
	"measurement_mode.projector": 0,
	"measurement.name.expanded": u"",
	"measurement.play_sound": 1,
	"measurement.save_path": expanduseru("~"),
	"measure.darken_background": 0,
	"measure.darken_background.show_warning": 1,
	"position.x": 50,
	"position.y": 50,
	"position.info.x": 50,
	"position.info.y": 50,
	"position.lut_viewer.x": 50,
	"position.lut_viewer.y": 50,
	"position.progress.x": 50,
	"position.progress.y": 50,
	"position.tcgen.x": 50,
	"position.tcgen.y": 50,
	"profile.install_scope": "l" if (sys.platform != "win32" and 
									 os.geteuid() == 0) # or 
									# (sys.platform == "win32" and 
									 # sys.getwindowsversion() >= (6, )) 
								else "u",  # Linux, OSX
	"profile.load_on_login": 1,
	"profile.name": u" ".join([
		u"%dns",
		u"%Y-%m-%d",
		u"%cb",
		u"%wp",
		u"%cB",
		u"%ck",
		u"%cg",
		u"%cq-%pq",
		u"%pt"
	]),
	"profile.name.expanded": u"",
	"profile.quality": "h",
	"profile.save_path": storage, # directory
	"profile.type": "s",
	"profile.update": 0,
	"recent_cals": "",
	"recent_cals_max": 15,
	"report.pack_js": 1,
	"settings.changed": 0,
	"show_advanced_calibration_options": 0,
	"size.info.w": 512,
	"size.info.h": 384,
	"size.lut_viewer.w": 512,
	"size.lut_viewer.h": 580,
	"skip_legacy_serial_ports": 1,
	"sudo.preserve_environment": 1,
	"tc_adaption": 0.1,
	"tc_algo": "",
	"tc_angle": 0.3333,
	"tc_filter": 0,
	"tc_filter_L": 50,
	"tc_filter_a": 0,
	"tc_filter_b": 0,
	"tc_filter_rad": 255,
	"tc_fullspread_patches": 0,
	"tc_gray_patches": 9,
	"tc_multi_steps": 3,
	"tc_precond": 0,
	"tc_precond_profile": "",
	"tc_single_channel_patches": 0,
	"tc_vrml_lab": 0,
	"tc_vrml_device": 1,
	"tc_white_patches": 4,
	"tc.show": 0,
	"trc": 2.2,
	"trc.should_use_viewcond_adjust.show_msg": 1,
	"trc.type": "g",
	"update_check": 1,
	"use_separate_lut_access": 0,
	"whitepoint.colortemp": 5000.0,
	"whitepoint.colortemp.locus": "t",
	"whitepoint.x": 0.345741,
	"whitepoint.y": 0.358666
}
lcode, lenc = locale.getdefaultlocale()
if lcode:
	defaults["lang"] = lcode.split("_")[0].lower()

testchart_defaults = {
	"s": {None: "d3-e4-s0-g9-m3-f0-crossover.ti1"},  # shaper + matrix
	"l": {None: "d3-e4-s0-g49-m0-f0-cubic4-crossover.ti1"},  # lut
	"g": {None: "d3-e4-s3-g3-m0-f0.ti1"}  # gamma + matrix
}

def _init_testcharts():
	for testcharts in testchart_defaults.values():
		for chart in testcharts.values():
			resfiles.append(os.path.join("ti1", chart))
	testchart_defaults["G"] = testchart_defaults["g"]
	testchart_defaults["S"] = testchart_defaults["s"]
	for key in ("X", "x"):
		testchart_defaults[key] = testchart_defaults["l"]


def getcfg(name, fallback=True):
	"""
	Get and return an option value from the configuration.
	
	If fallback evaluates to True and the option is not set, 
	return its default value.
	
	"""
	if (name in ("profile.save_path", "profile.name.expanded") and
		is_ccxx_testchart()):
		name = {"profile.save_path": "measurement.save_path",
				"profile.name.expanded": "measurement.name.expanded"}[name]
		setcfg("measurement.name.expanded", "%s & %s" % (get_instrument_name(),
													     get_display_name()))
	hasdef = name in defaults
	if hasdef:
		defval = defaults[name]
		deftype = type(defval)
	if cfg.has_option(ConfigParser.DEFAULTSECT, name):
		try:
			value = unicode(cfg.get(ConfigParser.DEFAULTSECT, name), "UTF-8")
		except UnicodeDecodeError:
			pass
		else:
			# Check for invalid types and return default if wrong type
			if (name != "trc" or value not in valid_values["trc"]) and \
			   hasdef and deftype in (Decimal, int, float):
				try:
					value = deftype(value)
				except ValueError:
					value = defval
				else:
					valid_range = valid_ranges.get(name)
					if valid_range:
						value = min(max(valid_range[0], value), valid_range[1])
			elif name.startswith("dimensions.measureframe"):
				try:
					value = [max(0, float(n)) for n in value.split(",")]
					if len(value) != 3:
						raise ValueError()
				except ValueError:
					value = defaults[name]
				else:
					value[0] = min(value[0], 1)
					value[1] = min(value[1], 1)
					value[2] = min(value[2], 50)
					value = ",".join([str(n) for n in value])
			elif name == "profile.quality" and getcfg("profile.type") in ("g", 
																		  "G"):
				# default to high quality for gamma + matrix
				value = "h"
			elif name == "trc.type" and getcfg("trc") in valid_values["trc"]:
				value = "g"
			elif value and name.endswith("file") and not os.path.exists(value):
				if debug:
					print "%s does not exist: %s" % (name, value),
				if value.split(os.path.sep)[-3:-2] == [appname] and (
				   value.split(os.path.sep)[-2:-1] == ["presets"] or 
				   value.split(os.path.sep)[-2:-1] == ["ti1"]):
					value = os.path.join(*value.split(os.path.sep)[-2:])
					value = get_data_path(value)
				if not value and hasdef:
					value = defval
				if debug:
					print "- falling back to", value
			elif name in valid_values and value not in valid_values[name]:
				if debug:
					print "Invalid config value for %s: %s" % (name, value),
				if hasdef:
					value = defval
				else:
					value = None
				if debug:
					print "- falling back to", value
			return value
	if hasdef and fallback:
		value = defval
	else:
		if debug and not hasdef: 
			print "Warning - unknown option:", name
		value = None
	return value


def hascfg(name, fallback=True):
	"""
	Check if an option name exists in the configuration.
	
	Returns a boolean.
	If fallback evaluates to True and the name does not exist, 
	check defaults also.
	
	"""
	if cfg.has_option(ConfigParser.DEFAULTSECT, name):
		return True
	elif fallback:
		return name in defaults
	return False


def get_ccxx_testchart():
	""" Get the path to the default chart for CCMX/CCSS creation """
	return get_data_path(os.path.join("ti1",
									  defaults["colorimeter_correction.testchart"]))


def get_total_patches(white_patches=None, single_channel_patches=None, 
					  gray_patches=None, multi_steps=None, 
					  fullspread_patches=None):
	if white_patches is None:
		white_patches = getcfg("tc_white_patches")
	if single_channel_patches is None:
		single_channel_patches = getcfg("tc_single_channel_patches")
	single_channel_patches_total = single_channel_patches * 3
	if gray_patches is None:
		gray_patches = getcfg("tc_gray_patches")
	if gray_patches == 0 and single_channel_patches > 0 and white_patches > 0:
		gray_patches = 2
	if multi_steps is None:
		multi_steps = getcfg("tc_multi_steps")
	if fullspread_patches is None:
		fullspread_patches = getcfg("tc_fullspread_patches")
	total_patches = 0
	if multi_steps > 1:
		multi_patches = int(math.pow(multi_steps, 3))
		total_patches += multi_patches
		white_patches -= 1 # white always in multi channel patches

		multi_step = 255.0 / (multi_steps - 1)
		multi_values = []
		for i in range(multi_steps):
			multi_values += [str(multi_step * i)]
		if single_channel_patches > 1:
			single_channel_step = 255.0 / (single_channel_patches - 1)
			for i in range(single_channel_patches):
				if str(single_channel_step * i) in multi_values:
					single_channel_patches_total -= 3
		if gray_patches > 1:
			gray_step = 255.0 / (gray_patches - 1)
			for i in range(gray_patches):
				if str(gray_step * i) in multi_values:
					gray_patches -= 1
	elif gray_patches > 1:
		white_patches -= 1  # white always in gray patches
		single_channel_patches_total -= 3  # black always in gray patches
	else:
		# black always only once in single channel patches
		single_channel_patches_total -= 2 
	total_patches += max(0, white_patches) + \
					 max(0, single_channel_patches_total) + \
					 max(0, gray_patches) + fullspread_patches
	return total_patches


def get_verified_path(cfg_item_name, path=None):
	""" Verify and return dir and filename for a path from the user cfg,
	or a given path """
	defaultPath = path or getcfg(cfg_item_name)
	defaultDir = expanduseru("~")
	defaultFile = ""
	if defaultPath:
		if os.path.exists(defaultPath):
			defaultDir, defaultFile = (os.path.dirname(defaultPath), 
									   os.path.basename(defaultPath))
		elif (defaults.get(cfg_item_name) and 
			  os.path.exists(defaults[cfg_item_name])):
			defaultDir, defaultFile = (os.path.dirname(defaults[cfg_item_name]), 
									   os.path.basename(defaults[cfg_item_name]))
		elif os.path.exists(os.path.dirname(defaultPath)):
			defaultDir = os.path.dirname(defaultPath)
	return defaultDir, defaultFile


def is_ccxx_testchart():
	""" Check wether the current testchart is the default chart for CCMX/CCSS creation """
	return getcfg("testchart.file") == get_ccxx_testchart()


def makecfgdir(which="user", worker=None):
	if which == "user":
		if not os.path.exists(confighome):
			try:
				os.makedirs(confighome)
			except Exception, exception:
				from debughelpers import handle_error
				handle_error(u"Warning - could not create configuration directory "
							 "'%s': %s" % (confighome, safe_unicode(exception)))
				return False
	elif not os.path.exists(config_sys):
		try:
			if sys.platform == "win32":
				os.makedirs(config_sys)
			else:
				result = worker.exec_cmd("mkdir", 
										 ["-p", config_sys], 
										 capture_output=True, 
										 low_contrast=False, 
										 skip_scripts=True, 
										 silent=True, 
										 asroot=True)
				if isinstance(result, Exception):
					raise result
		except Exception, exception:
			from debughelpers import handle_error
			handle_error(u"Warning - could not create configuration directory "
						 "'%s': %s" % (config_sys, safe_unicode(exception)))
			return False
	return True


def initcfg():
	"""
	Initialize the configuration.
	
	Read in settings if the configuration file exists, else create the 
	settings directory if nonexistent.
	
	"""
	# read pre-v0.2.2b configuration if present
	if sys.platform == "darwin":
		oldcfg = os.path.join(expanduseru("~"), "Library", "Preferences", 
							  appname + " Preferences")
	else:
		oldcfg = os.path.join(expanduseru("~"), "." + appname)
	makecfgdir()
	if os.path.exists(confighome) and \
	   not os.path.exists(os.path.join(confighome, appname + ".ini")):
		try:
			if os.path.isfile(oldcfg):
				oldcfg_file = open(oldcfg, "rb")
				oldcfg_contents = oldcfg_file.read()
				oldcfg_file.close()
				cfg_file = open(os.path.join(confighome, appname + ".ini"), 
								"wb")
				cfg_file.write("[Default]\n" + oldcfg_contents)
				cfg_file.close()
			elif sys.platform == "win32":
				key = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, 
									  "Software\\" + appname)
				numsubkeys, numvalues, mtime = _winreg.QueryInfoKey(key)
				cfg_file = open(os.path.join(confighome, appname + ".ini"), 
								"wb")
				cfg_file.write("[Default]\n")
				for i in range(numvalues):
					name, value, type_ = _winreg.EnumValue(key, i)
					if type_ == 1: cfg_file.write((u"%s = %s\n" % (name, 
												   value)).encode("UTF-8"))
				cfg_file.close()
		except Exception, exception:
			# WindowsError 2 means registry key does not exist, do not show 
			# warning in that case
			if sys.platform != "win32" or not hasattr(exception, "errno") or \
			   exception.errno != 2:
				from log import safe_print
				safe_print("Warning - could not process old configuration:", 
						   safe_unicode(exception))
		# Set a few defaults which have None as possible value and thus cannot
		# be set in the 'defaults' collection
		setcfg("gamap_src_viewcond", "mt")
		setcfg("gamap_out_viewcond", "mt")
	# Read cfg
	try:
		cfg.read([os.path.join(config_sys, appname + ".ini")])
		cfg.read([os.path.join(confighome, appname + ".ini")])
		# This won't raise an exception if the file does not exist, only if it
		# can't be parsed
	except Exception, exception:
		from log import safe_print
		safe_print("Warning - could not parse configuration file '%s'" % 
				   appname + ".ini")


def setcfg(name, value):
	""" Set an option value in the configuration. """
	if value is None:
		cfg.remove_option(ConfigParser.DEFAULTSECT, name)
	else:
		cfg.set(ConfigParser.DEFAULTSECT, name, unicode(value).encode("UTF-8"))


def writecfg(which="user", worker=None):
	"""
	Write configuration file.
	
	which: 'user' or 'system'
	worker: worker instance if which == 'system'
	
	"""
	if which == "user":
		# user config - stores everything and overrides system-wide config
		cfgfilename = os.path.join(confighome, appname + ".ini")
		try:
			io = StringIO()
			cfg.write(io)
			io.seek(0)
			lines = io.read().strip("\n").split("\n")
			lines.sort()
			cfgfile = open(cfgfilename, "wb")
			cfgfile.write("\n".join(lines))
			cfgfile.close()
		except Exception, exception:
			from debughelpers import handle_error
			handle_error(u"Warning - could not write user configuration file "
						 "'%s': %s" % (cfgfilename, safe_unicode(exception)))
			return False
	else:
		# system-wide config - only stores essentials ie. Argyll directory
		cfgfilename1 = os.path.join(confighome, appname + ".local.ini")
		cfgfilename2 = os.path.join(config_sys, appname + ".ini")
		if sys.platform == "win32":
			cfgfilename = cfgfilename2
		else:
			cfgfilename = cfgfilename1
		try:
			cfgfile = open(cfgfilename, "wb")
			cfgfile.write("\n".join(["[Default]",
									 "%s = %s" % ("argyll.dir", 
												  getcfg("argyll.dir"))]))
			cfgfile.close()
			if sys.platform != "win32":
				# on Linux and OS X, we write the file to the users's config dir
				# then 'su mv' it to the system-wide config dir
				result = worker.exec_cmd("mv", 
										 ["-f", cfgfilename1, cfgfilename2], 
										 capture_output=True, 
										 low_contrast=False, 
										 skip_scripts=True, 
										 silent=True, 
										 asroot=True)
				if isinstance(result, Exception):
					raise result
		except Exception, exception:
			from debughelpers import handle_error
			handle_error(u"Warning - could not write system-wide configuration file "
						 "'%s': %s" % (cfgfilename2, safe_unicode(exception)))
			return False
	return True

_init_testcharts()
runtype = runtimeconfig(pyfile)
