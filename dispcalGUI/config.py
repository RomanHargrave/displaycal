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
import re
import string
import sys
from time import gmtime, strftime, timezone
if sys.platform == "win32":
	import _winreg

from argyll_names import viewconds, intents, video_encodings
from defaultpaths import appdata, commonappdata
if sys.platform == "win32":
	from defaultpaths import commonprogramfiles
elif sys.platform == "darwin":
	from defaultpaths import library, library_home, prefs, prefs_home
else:
	from defaultpaths import (xdg_config_dir_default, xdg_config_home, 
							  xdg_data_home, xdg_data_home_default, 
							  xdg_data_dirs)
from defaultpaths import (autostart, autostart_home, iccprofiles,
						  iccprofiles_home)
from meta import name as appname, build, lastmod, version
from options import ascii, debug, verbose
from safe_print import enc, fs_enc, original_codepage
from util_io import StringIOu as StringIO
from util_os import expanduseru, expandvarsu, getenvu, is_superuser, listdir_re
from util_str import create_replace_function, safe_unicode
import encodedstdio

# Runtime configuration

if ascii:
	enc = "ASCII"

exe = unicode(sys.executable, fs_enc)
exedir = os.path.dirname(exe)
exename = os.path.basename(exe)

isexe = sys.platform != "darwin" and getattr(sys, "frozen", False)

if isexe and os.getenv("_MEIPASS2"):
	os.environ["_MEIPASS2"] = os.getenv("_MEIPASS2").replace("/", os.path.sep)

pyfile = (exe if isexe else (os.path.isfile(sys.argv[0]) and sys.argv[0]) or
		  os.path.join(os.path.dirname(__file__), "main.py"))
pypath = exe if isexe else os.path.abspath(unicode(pyfile, fs_enc))
# Mac OS X: isapp should only be true for standalone, not 0install
isapp = sys.platform == "darwin" and \
		exe.split(os.path.sep)[-3:-1] == ["Contents", "MacOS"] and \
		os.path.exists(os.path.join(exedir, "..", "Resources", "xrc"))
if isapp:
	pyname, pyext = os.path.splitext(exe.split(os.path.sep)[-4])
	pydir = os.path.normpath(os.path.join(exedir, "..", "Resources"))
else:
	pyname, pyext = os.path.splitext(os.path.basename(pypath))
	pydir = os.path.dirname(exe if isexe
							else os.path.abspath(unicode(__file__, fs_enc)))

data_dirs = [pydir]
extra_data_dirs = []
# Search directories on PATH for data directories so Argyll reference files
# can be found automatically if Argyll directory not explicitly configured
for dir_ in getenvu("PATH", "").split(os.pathsep):
	dir_parent = os.path.dirname(dir_)
	if os.path.isdir(os.path.join(dir_parent, "ref")):
		extra_data_dirs.append(dir_parent)

if sys.platform == "win32":
	if pydir.lower().startswith(exedir.lower()) and pydir != exedir:
		# We are installed in a subfolder of the executable directory (e.g. 
		# C:\Python26\Lib\site-packages\dispcalGUI) - we nee to add 
		# the executable directory to the data directories so files in
		# subfolders of the executable directory which are not in 
		# Lib\site-packages\dispcalGUI can be found
		# (e.g. Scripts\dispcalGUI-apply-profiles)
		data_dirs.append(exedir)
	script_ext = ".cmd"
	scale_adjustment_factor = 1.0
	config_sys = os.path.join(commonappdata[0], appname)
	confighome = os.path.join(appdata, appname)
	datahome = os.path.join(appdata, appname)
	logdir = os.path.join(datahome, "logs")
	data_dirs.append(datahome)
	data_dirs.extend(os.path.join(dir_, appname) for dir_ in commonappdata)
	data_dirs.append(os.path.join(commonprogramfiles, appname))
	exe_ext = ".exe"
	profile_ext = ".icm"
else:
	if sys.platform == "darwin":
		script_ext = ".command"
		mac_create_app = True
		scale_adjustment_factor = 1.0
		config_sys = os.path.join(prefs, appname)
		confighome = os.path.join(prefs_home, appname)
		datahome = os.path.join(appdata, appname)
		logdir = os.path.join(expanduseru("~"), "Library", 
							  "Logs", appname)
		data_dirs.extend([datahome, os.path.join(commonappdata[0], appname)])
	else:
		script_ext = ".sh"
		scale_adjustment_factor = 1.0
		config_sys = os.path.join(xdg_config_dir_default, appname)
		confighome = os.path.join(xdg_config_home, appname)
		datahome = os.path.join(xdg_data_home, appname)
		datahome_default = os.path.join(xdg_data_home_default, appname)
		logdir = os.path.join(datahome, "logs")
		data_dirs.append(datahome)
		if not datahome_default in data_dirs:
			data_dirs.append(datahome_default)
		data_dirs.extend(os.path.join(dir_, appname) for dir_ in xdg_data_dirs)
		extra_data_dirs.extend(os.path.join(dir_, "argyllcms") for dir_ in
							   xdg_data_dirs)
		extra_data_dirs.extend(os.path.join(dir_, "color", "argyll") for dir_ in
							   xdg_data_dirs)
	exe_ext = ""
	profile_ext = ".icc"

storage = os.path.join(datahome, "storage")

resfiles = [
	# Only essentials
	"argyll_instruments.json",
	"lang/en.json",
	"beep.wav",
	"camera_shutter.wav",
	"linear.cal",
	"test.cal",
	"ref/ClayRGB1998.gam",
	"ref/sRGB.gam",
	"ref/verify.ti1",
	"xrc/3dlut.xrc",
	"xrc/extra.xrc",
	"xrc/gamap.xrc",
	"xrc/main.xrc",
	"xrc/mainmenu.xrc",
	"xrc/report.xrc",
	"xrc/synthicc.xrc"
]

bitmaps = {}

uncalibratable_displays = ("Untethered$", )

patterngenerators = ("madVR$", "Resolve$", "Chromecast ")

non_argyll_displays = uncalibratable_displays + ("Resolve$", )

untethered_displays = non_argyll_displays + ("Web$", "Chromecast ")

virtual_displays = untethered_displays + ("madVR$", )


def is_special_display(display_no=None, tests=virtual_displays):
	display_name = get_display_name(display_no)
	for test in tests:
		if re.match(test, display_name):
			return True
	return False


def is_uncalibratable_display(display_no=None):
	return is_special_display(display_no, uncalibratable_displays)


def is_patterngenerator(display_no=None):
	return is_special_display(display_no, patterngenerators)


def is_non_argyll_display(display_no=None):
	return is_special_display(display_no, non_argyll_displays)


def is_untethered_display(display_no=None):
	return is_special_display(display_no, untethered_displays)


def is_virtual_display(display_no=None):
	return is_special_display(display_no, virtual_displays)


def getbitmap(name, display_missing_icon=True):
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
		w = 16
		h = 16
		if len(parts) > 1:
			size = parts[-2].split("x")
			if len(size) == 2:
				try:
					w, h = map(int, size)
				except ValueError:
					pass
		if parts[-1] == "empty":
			bitmaps[name] = wx.EmptyBitmap(w, h, depth=-1)
			dc = wx.MemoryDC()
			dc.SelectObject(bitmaps[name])
			dc.SetBackground(wx.Brush("black"))
			dc.Clear()
			dc.SelectObject(wx.NullBitmap)
			bitmaps[name].SetMaskColour("black")
		else:
			path = None
			if parts[-1].startswith(appname):
				path = get_data_path(os.path.join(parts[-2], "apps", parts[-1]) + ".png")
			if not path:
				path = get_data_path(os.path.sep.join(parts) + ".png")
			if path:
				bitmaps[name] = wx.Bitmap(path)
			else:
				img = wx.EmptyImage(w, h)
				img.SetMaskColour(0, 0, 0)
				img.InitAlpha()
				bmp = img.ConvertToBitmap()
				bitmaps[name] = bmp
				dc = wx.MemoryDC()
				dc.SelectObject(bitmaps[name])
				if display_missing_icon:
					bmp = wx.ArtProvider.GetBitmap(wx.ART_MISSING_IMAGE,
												   size=(w, h))
					dc.DrawBitmap(bmp, 0, 0, True)
				dc.SelectObject(wx.NullBitmap)
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


def get_argyll_data_dir():
	if getcfg("argyll.version") < "1.5.0":
		argyll_data_dirname = "color"
	else:
		argyll_data_dirname = "ArgyllCMS"
	if sys.platform == "darwin" and getcfg("argyll.version") < "1.5.0":
		return os.path.join(library if is_superuser() else library_home,
							argyll_data_dirname)
	else:
		return os.path.join(commonappdata[0] if is_superuser() else appdata,
							argyll_data_dirname)


def get_display_name(n=None, include_geometry=False):
	""" Return name of currently configured display """
	if n is None:
		n = getcfg("display.number") - 1
	displays = getcfg("displays").split(os.pathsep)
	if n >= 0 and n < len(displays):
		if include_geometry:
			return displays[n]
		else:
			return displays[n].split("@")[0].strip()
	return ""


def get_argyll_display_number(geometry):
	""" Translate from wx display geometry to Argyll display index """
	geometry = "%i, %i, %ix%i" % tuple(geometry)
	for i, display in enumerate(getcfg("displays").split(os.pathsep)):
		if display.find("@ " + geometry) > -1:
			if debug:
				from log import safe_print
				safe_print("[D] Found display %s at index %i" % 
						   (geometry, i))
			return i


def get_display_number(display_no):
	""" Translate from Argyll display index to wx display index """
	if is_virtual_display(display_no):
		return 0
	from wxaddons import wx
	try:
		display = getcfg("displays").split(os.pathsep)[display_no]
	except IndexError:
		return 0
	else:
		for i in xrange(wx.Display.GetCount()):
			geometry = "%i, %i, %ix%i" % tuple(wx.Display(i).Geometry)
			if display.find("@ " + geometry) > -1:
				if debug:
					from log import safe_print
					safe_print("[D] Found display %s at index %i" % 
							   (geometry, i))
				return i
	return 0


def get_display_rects():
	""" Return the Argyll enumerated display coordinates and sizes """
	from wxaddons import wx
	display_rects = []
	for i, display in enumerate(getcfg("displays").split(os.pathsep)):
		match = re.search("@ (-?\d+), (-?\d+), (\d+)x(\d+)", display)
		if match:
			display_rects.append(wx.Rect(*[int(item) for item in match.groups()]))
	return display_rects


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


def get_measureframe_dimensions(dimensions_measureframe=None, percent=10):
	""" return measurement area size adjusted for percentage of screen area """
	if not dimensions_measureframe:
		dimensions_measureframe = getcfg("dimensions.measureframe")
	dimensions_measureframe = [float(n) for n in
							   dimensions_measureframe.split(",")]
	dimensions_measureframe[2] *= defaults["size.measureframe"]
	dimensions_measureframe[2] /= get_display_rects()[0][2]
	dimensions_measureframe[2] *= percent
	return ",".join([str(min(n, 50)) for n in dimensions_measureframe])


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
	if (not relpath or relpath.endswith(os.path.sep) or
		(isinstance(os.path.altsep, basestring) and
		 relpath.endswith(os.path.altsep))):
		return None
	dirs = list(data_dirs)
	argyll_dir = getcfg("argyll.dir")
	if argyll_dir and os.path.isdir(os.path.join(argyll_dir, "..", "ref")):
		dirs.append(os.path.dirname(argyll_dir))
	dirs.extend(extra_data_dirs)
	intersection = []
	paths = []
	for dir_ in dirs:
		curpath = os.path.join(dir_, relpath)
		if (dir_.endswith("/argyll") and (relpath + "/").startswith("ref/") and
			not os.path.exists(curpath)):
			# Work-around distribution-specific differences for location
			# of Argyll reference files
			# Fedora and Ubuntu: /usr/share/color/argyll/ref
			# openSUSE: /usr/share/color/argyll
			pth = relpath.split("/", 1)[-1]
			if pth != "ref":
				curpath = os.path.join(dir_, pth)
			else:
				curpath = dir_
		if os.path.exists(curpath):
			curpath = os.path.normpath(curpath)
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
							intersection.append(filename)
							paths.append(os.path.join(curpath, filename))
			else:
				return curpath
	if paths:
		paths.sort(key=lambda path: os.path.basename(path).lower())
	return None if len(paths) == 0 else paths


def runtimeconfig(pyfile):
	"""
	Configure remaining runtime options and return runtype.
	
	You need to pass in a path to the calling script (e.g. use the __file__ 
	attribute).
	
	"""
	from log import setup_logging
	if pyname.startswith(appname):
		setup_logging(logdir, pyname)
	if debug or verbose >= 1:
		from log import safe_print
	if debug:
		safe_print("[D] pydir:", pydir)
	if isapp:
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
		if (os.path.dirname(os.path.abspath(sys.argv[0])).decode(fs_enc) ==
			pydir_parent and pydir_parent not in data_dirs):
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
										  testchart_defaults["l"])[None]
	defaults["testchart.file"] = get_data_path(os.path.join("ti1", 
															defaultchart)) or ""
	defaults["testchart.file.backup"] = defaults["testchart.file"]
	defaults["measurement_report.chart"] = get_data_path(os.path.join("ref", 
															"verify.ti1")) or ""
	return runtype

# User settings

cfg = ConfigParser.RawConfigParser()
cfg.optionxform = str

valid_ranges = {
	"3dlut.trc_gamma": [0.000001, 10],
	"3dlut.trc_output_offset": [0.0, 1.0],
	"app.port": [1, 65535],
	"gamma": [0.000001, 10],
	"trc": [0.000001, 10],
	"calibration.ambient_viewcond_adjust.lux": [0, sys.maxint],
	"calibration.black_luminance": [0.000001, 100000],
	"calibration.black_output_offset": [0, 1],
	"calibration.black_point_correction": [0, 1],
	"calibration.black_point_rate": [0.05, 20],
	"calibration.luminance": [0.000001, 100000],
	"iccgamut.surface_detail": [1.0, 50.0],
	"measurement_report.trc_gamma": [0.01, 10],
	"measurement_report.trc_output_offset": [0.0, 1.0],
	"measure.display_settle_time_mult": [0.000001, 10000.0],
	"measure.min_display_update_delay_ms": [20, 60000],
	"patterngenerator.apl": [0.0, 1.0],
	"patterngenerator.resolve.port": [1, 65535],
	"synthprofile.trc_output_offset": [0.0, 1.0],
	"tc_export_repeat_patch_max": [1, 1000],
	"tc_export_repeat_patch_min": [1, 1000],
	"tc_vrml_black_offset": [0, 40],
	"webserver.portnumber": [1, 65535],
	"whitepoint.colortemp": [1000, 15000],
}

valid_values = {
	"3d.format": ["HTML", "VRML", "X3D"],
	"3dlut.bitdepth.input": [8, 10, 12, 14, 16],
	"3dlut.bitdepth.output": [8, 10, 12, 14, 16],
	"3dlut.encoding.input": list(video_encodings),
	# collink: xvYCC output encoding is not supported
	"3dlut.encoding.output": filter(lambda v: v not in ("T", "x", "X"),
									video_encodings),
	"3dlut.format": ["3dl", "cube", "eeColor", "madVR", "mga", "spi3d"],
	"3dlut.rendering_intent": intents,
	"3dlut.size": [17, 24, 32, 33, 64, 65],
	"3dlut.trc_gamma_type": ["b", "B"],
	"calibration.quality": ["v", "l", "m", "h", "u"],
	"colorimeter_correction.type": ["matrix", "spectral"],
	# Measurement modes as supported by Argyll -y parameter
	# 'l' = 'n' (non-refresh-type display, e.g. LCD)
	# 'c' = 'r' (refresh-type display, e.g. CRT)
	# We map 'l' and 'c' to "n" and "r" in
	# worker.Worker.add_measurement_features if using Argyll >= 1.5
	# See http://www.argyllcms.com/doc/instruments.html
	# for description of per-instrument supported modes
	"measurement_mode": [None, "auto"] + list(string.digits[1:] +
											  string.ascii_letters),
	"gamap_default_intent": ["a", "r", "p", "s"],
	"gamap_perceptual_intent": intents,
	"gamap_saturation_intent": intents,
	"gamap_src_viewcond": viewconds,
	"gamap_out_viewcond": ["mt", "mb", "md", "jm", "jd"],
	"measurement_report.trc_gamma_type": ["b", "B"],
	"patterngenerator.resolve.use_video_levels": [0, 1],
	"profile.black_point_compensation": [0, 1],
	"profile.install_scope": ["l", "u"],
	"profile.quality": ["l", "m", "h", "u"],
	"profile.quality.b2a": ["l", "m", "h", "u", "n", None],
	"profile.b2a.hires.size": [9, 17, 33, 45, 65],
	"profile.type": ["g", "G", "l", "s", "S", "x", "X"],
	"synthprofile.black_point_compensation": [0, 1],
	"synthprofile.trc_gamma_type": ["g", "G"],
	"tc_algo": ["", "t", "r", "R", "q", "Q", "i", "I"],  # Q = Argyll >= 1.1.0
	"tc_vrml_use_D50": [0, 1],
	"tc_vrml_cie_colorspace": ["DIN99", "DIN99b", "DIN99c", "DIN99d", "LCH(ab)",
							   "LCH(uv)", "Lab", "Luv", "Lu'v'", "xyY"],
	"tc_vrml_device_colorspace": ["HSI", "HSL", "HSV", "RGB"],
	"testchart.auto_optimize": [0, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17],
	"trc": ["240", "709", "l", "s", ""],
	"trc.type": ["g", "G"],
	"whitepoint.colortemp.locus": ["t", "T"]
}

defaults = {
	"3d.format": "HTML",
	"3dlut.apply_black_offset": 0,
	"3dlut.apply_trc": 1,
	"3dlut.bitdepth.input": 10,
	"3dlut.bitdepth.output": 10,
	"3dlut.create": 0,
	"3dlut.trc_gamma": 2.4,
	"3dlut.trc_gamma.backup": 2.4,
	"3dlut.trc_gamma_type": "B",
	"3dlut.trc_output_offset": 0.0,
	"3dlut.encoding.input": "n",
	"3dlut.encoding.input.backup": "n",
	"3dlut.encoding.output": "n",
	"3dlut.encoding.output.backup": "n",
	"3dlut.format": "cube",
	"3dlut.gamap.use_b2a": 0,
	"3dlut.input.profile": "",
	"3dlut.abstract.profile": "",
	"3dlut.madVR.enable": 1,
	"3dlut.output.profile": "",
	"3dlut.output.profile.apply_cal": 1,
	"3dlut.rendering_intent": "aw",
	"3dlut.use_abstract_profile": 0,
	"3dlut.size": 65,
	"3dlut.tab.enable": 0,
	"3dlut.tab.enable.backup": 0,
	"allow_skip_sensor_cal": 0,
	"app.allow_network_clients": 0,
	"app.port": 15411,
	"argyll.debug": 0,
	"argyll.dir": None,
	"argyll.version": "0.0.0",
	"drift_compensation.blacklevel": 0,
	"drift_compensation.whitelevel": 0,
	"calibration.ambient_viewcond_adjust": 0,
	"calibration.ambient_viewcond_adjust.lux": 500.0,
	"calibration.autoload": 0,
	"calibration.black_luminance": 0.000001,
	"calibration.black_luminance.backup": 0.000001,
	"calibration.black_output_offset": 1.0,
	"calibration.black_output_offset.backup": 1.0,
	"calibration.black_point_correction": 0.0,
	"calibration.black_point_correction.auto": 0,
	"calibration.black_point_correction_choice.show": 1,
	"calibration.black_point_hack": 0,
	"calibration.black_point_rate": 4.0,
	"calibration.black_point_rate.enabled": 0,
	"calibration.continue_next": 0,
	"calibration.file": "presets/default.icc",
	"calibration.file.previous": None,
	"calibration.interactive_display_adjustment": 1,
	"calibration.interactive_display_adjustment.backup": 1,
	"calibration.luminance": 120.0,
	"calibration.luminance.backup": 120.0,
	"calibration.quality": "m",
	"calibration.update": 0,
	"calibration.use_video_lut": 1,
	"calibration.use_video_lut.backup": 1,
	"colorimeter_correction.instrument": None,
	"colorimeter_correction.instrument.reference": None,
	"colorimeter_correction.measurement_mode": "l",
	"colorimeter_correction.measurement_mode.reference.adaptive": 1,
	"colorimeter_correction.measurement_mode.reference.highres": 0,
	"colorimeter_correction.measurement_mode.reference.projector": 0,
	"colorimeter_correction.measurement_mode.reference": "l",
	"colorimeter_correction.testchart": "ccxx.ti1",
	"colorimeter_correction_matrix_file": "AUTO:",
	"colorimeter_correction.type": "matrix",
	"comport.number": 1,
	"comport.number.backup": 1,
	# Note: worker.Worker.enumerate_displays_and_ports() overwrites copyright
	"copyright": "No copyright. Created with %s %s and Argyll CMS" % (appname, 
																	  version),
	"dimensions.measureframe": "0.5,0.5,1.5",
	"dimensions.measureframe.unzoomed": "0.5,0.5,1.5",
	"display.number": 1,
	"display_lut.link": 1,
	"display_lut.number": 1,
	"display.technology": "LCD",
	"displays": "",
	"dry_run": 0,
	"enumerate_ports.auto": 0,
	"extra_args.collink": "",
	"extra_args.colprof": "",
	"extra_args.dispcal": "",
	"extra_args.dispread": "",
	"extra_args.spotread": "",
	"extra_args.targen": "",
	"gamap_profile": "",
	"gamap_perceptual": 0,
	"gamap_perceptual_intent": "la",
	"gamap_saturation": 0,
	"gamap_saturation_intent": "s",
	"gamap_default_intent": "p",
	"gamma": 2.2,
	"iccgamut.surface_detail": 6.0,
	"instruments": "",
	"log.autoshow": 0,
	"log.show": 0,
	"lang": "en",
	# The last_[...]_path defaults are set in localization.py
	"lut_viewer.show": 0,
	"lut_viewer.show_actual_lut": 0,
	"measurement_mode": "l",
	"measurement_mode.adaptive": 1,
	"measurement_mode.backup": "l",
	"measurement_mode.highres": 0,
	"measurement_mode.projector": 0,
	"measurement_report.apply_black_offset": 0,
	"measurement_report.apply_trc": 0,
	"measurement_report.trc_gamma": 2.4,
	"measurement_report.trc_gamma.backup": 2.4,
	"measurement_report.trc_gamma_type": "B",
	"measurement_report.trc_output_offset": 0.0,
	"measurement_report.chart": "",
	"measurement_report.chart.fields": "RGB",
	"measurement_report.devlink_profile": "",
	"measurement_report.output_profile": "",
	"measurement_report.whitepoint.simulate": 0,
	"measurement_report.whitepoint.simulate.relative": 0,
	"measurement_report.simulation_profile": "",
	"measurement_report.use_devlink_profile": 0,
	"measurement_report.use_simulation_profile": 0,
	"measurement_report.use_simulation_profile_as_output": 0,
	"measurement.name.expanded": u"",
	"measurement.play_sound": 1,
	"measurement.save_path": expanduseru("~"),
	"measure.darken_background": 0,
	"measure.darken_background.show_warning": 1,
	"measure.display_settle_time_mult": 1.0,
	"measure.display_settle_time_mult.backup": 1.0,
	"measure.min_display_update_delay_ms": 20,
	"measure.min_display_update_delay_ms.backup": 20,
	"measure.override_display_settle_time_mult": 0,
	"measure.override_display_settle_time_mult.backup": 0,
	"measure.override_min_display_update_delay_ms": 0,
	"measure.override_min_display_update_delay_ms.backup": 0,
	"patterngenerator.apl": .22,
	"patterngenerator.resolve": "CM",
	"patterngenerator.resolve.port": 20002,
	"patterngenerator.resolve.use_video_levels": 0,
	"position.x": 50,
	"position.y": 50,
	"position.info.x": 50,
	"position.info.y": 50,
	"position.lut_viewer.x": 50,
	"position.lut_viewer.y": 50,
	"position.lut3dframe.x": 50,
	"position.lut3dframe.y": 50,
	"position.profile_info.x": 50,
	"position.profile_info.y": 50,
	"position.progress.x": 50,
	"position.progress.y": 50,
	"position.reportframe.x": 50,
	"position.reportframe.y": 50,
	"position.scripting.x": 50,
	"position.scripting.y": 50,
	"position.synthiccframe.x": 50,
	"position.synthiccframe.y": 50,
	"position.tcgen.x": 50,
	"position.tcgen.y": 50,
	"profile.black_point_compensation": 0,
	"profile.create_gamut_views": 1,
	"profile.install_scope": "l" if (sys.platform != "win32" and 
									 os.geteuid() == 0) # or 
									# (sys.platform == "win32" and 
									 # sys.getwindowsversion() >= (6, )) 
								else "u",  # Linux, OSX
	"profile.license": "Public Domain",
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
	"profile.quality.b2a": "h",
	"profile.b2a.hires": 1,
	"profile.b2a.hires.diagpng": 1,
	"profile.b2a.hires.size": 33,
	"profile.b2a.hires.smooth": 1,
	"profile.save_path": storage, # directory
	"profile.type": "X",
	"profile.update": 0,
	"profile_loader.error.show_msg": 1,
	"profile_loader.verify_calibration": 0,
	"recent_cals": "",
	"report.pack_js": 1,
	"settings.changed": 0,
	"show_advanced_options": 0,
	"size.info.w": 512,
	"size.info.h": 384,
	"size.lut3dframe.w": 512,
	"size.lut3dframe.h": 384,
	"size.measureframe": 300,
	"size.profile_info.w": 432,
	"size.profile_info.split.w": 960,
	"size.profile_info.h": 552,
	"size.lut_viewer.w": 432,
	"size.lut_viewer.h": 552,
	"size.reportframe.w": 512,
	"size.reportframe.h": 256,
	"size.scripting.w": 512,
	"size.scripting.h": 384,
	"size.synthiccframe.w": 512,
	"size.synthiccframe.h": 384,
	"skip_legacy_serial_ports": 1,
	"skip_scripts": 1,
	"sudo.preserve_environment": 1,
	"synthprofile.black_luminance": 0.0,
	"synthprofile.luminance": 120.0,
	"synthprofile.trc_gamma": 2.4,
	"synthprofile.trc_gamma_type": "G",
	"synthprofile.trc_output_offset": 0.0,
	"tc_adaption": 0.1,
	"tc_add_ti3_relative": 1,
	"tc_algo": "",
	"tc_angle": 0.3333,
	"tc_black_patches": 4,
	"tc_export_repeat_patch_max": 1,
	"tc_export_repeat_patch_min": 1,
	"tc_filter": 0,
	"tc_filter_L": 50,
	"tc_filter_a": 0,
	"tc_filter_b": 0,
	"tc_filter_rad": 255,
	"tc_fullspread_patches": 0,
	"tc_gamma": 1.0,
	"tc_gray_patches": 9,
	"tc_multi_bcc": 0,
	"tc_multi_bcc_steps": 0,
	"tc_multi_steps": 3,
	"tc_neutral_axis_emphasis": 0.5,
	"tc_dark_emphasis": 0.0,
	"tc_precond": 0,
	"tc_precond_profile": "",
	"tc.saturation_sweeps": 5,
	"tc.saturation_sweeps.custom.R": 0.0,
	"tc.saturation_sweeps.custom.G": 0.0,
	"tc.saturation_sweeps.custom.B": 0.0,
	"tc_single_channel_patches": 0,
	"tc_vrml_black_offset": 40,
	"tc_vrml_cie": 0,
	"tc_vrml_cie_colorspace": "Lab",
	"tc_vrml_device_colorspace": "RGB",
	"tc_vrml_device": 1,
	"tc_vrml_use_D50": 0,
	"tc_white_patches": 4,
	"tc.show": 0,
	"testchart.auto_optimize": 0,
	"testchart.auto_optimize.fix_zero_blackpoint": 0,
	"testchart.reference": "",
	"ti3.check_sanity.auto": 0,
	"trc": 2.2,
	"trc.backup": 2.2,
	"trc.should_use_viewcond_adjust.show_msg": 1,
	"trc.type": "g",
	"trc.type.backup": "g",
	"uniformity.measure.continuous": 0,
	"untethered.measure.auto": 1,
	"untethered.measure.manual.delay": 0.75,
	"untethered.max_delta.chroma": 0.5,
	"untethered.min_delta": 1.5,
	"untethered.min_delta.lightness": 1.0,
	"update_check": 1,
	"use_fancy_progress": 1,
	"use_separate_lut_access": 0,
	"vrml.compress": 1,
	"webserver.portnumber": 8080,
	"whitepoint.colortemp": 5000,
	"whitepoint.colortemp.backup": 5000,
	"whitepoint.colortemp.locus": "t",
	"whitepoint.x": 0.345741,
	"whitepoint.x.backup": 0.345741,
	"whitepoint.y": 0.358666,
	"whitepoint.y.backup": 0.358666,
	"x3dom.cache": 1,
	"x3dom.embed": 0
}
lcode, lenc = locale.getdefaultlocale()
if lcode:
	defaults["lang"] = lcode.split("_")[0].lower()

testchart_defaults = {
	"s": {None: "d3-e4-s0-g25-m3-b3-f0-crossover.ti1"},  # shaper + matrix
	"l": {None: "d3-e4-s17-g49-m5-b5-f0.ti1"},  # lut
	"g": {None: "d3-e4-s0-g25-m3-b3-f0-crossover.ti1"}  # gamma + matrix
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
	if name == "profile.name.expanded" and is_ccxx_testchart():
		name = "measurement.name.expanded"
	value = None
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
					elif name in valid_values and value not in valid_values[name]:
						value = defval
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
			elif name in valid_values and value not in valid_values[name]:
				if debug:
					print "Invalid config value for %s: %s" % (name, value),
				value = None
			elif name == "copyright":
				# Make sure dispcalGUI and Argyll version are up-to-date
				pattern = re.compile("(%s(?:\s*v(?:ersion|\.)?)?\s*)\d+(?:\.\d+)*" %
									 appname, re.I)
				repl = create_replace_function("\\1%s", version)
				value = re.sub(pattern, repl, value)
				pattern = re.compile("(Argyll(?:\s*CMS)?)((?:\s*v(?:ersion|\.)?)?\s*)\d+(?:\.\d+)*",
									 re.I)
				if defval.split()[-1] != "CMS":
					repl = create_replace_function("\\1\\2%s",
												   defval.split()[-1])
				else:
					repl = "\\1"
				value = re.sub(pattern, repl, value)
			elif name == "measurement_mode":
				# Map n and r measurement modes to canonical l and c
				# - the inverse mapping happens per-instrument in
				# Worker.add_measurement_features(). That way we can have
				# compatibility with old and current Argyll CMS
				value = {"n": "l", "r": "c"}.get(value, value)
	if value is None:
		if hasdef and fallback:
			value = defval
			if debug:
				print "- falling back to", value
		else:
			if debug and not hasdef: 
				print "Warning - unknown option:", name
	if (value and isinstance(value, basestring) and
		name.endswith("file") and
		name != "colorimeter_correction_matrix_file" and
		(name != "testchart.file" or value != "auto") and
		(not os.path.isabs(value) or not os.path.exists(value))):
		# colorimeter_correction_matrix_file is special because it's
		# not (only) a path
		if debug:
			print "%s does not exist: %s" % (name, value),
		# Normalize path (important, this turns altsep into sep under
		# Windows)
		value = os.path.normpath(value)
		# Check if this is a relative path covered by data_dirs
		if (value.split(os.path.sep)[-3:-2] == [appname] or
			not os.path.isabs(value)) and (
		   value.split(os.path.sep)[-2:-1] == ["presets"] or 
		   value.split(os.path.sep)[-2:-1] == ["ref"] or 
		   value.split(os.path.sep)[-2:-1] == ["ti1"]):
			value = os.path.join(*value.split(os.path.sep)[-2:])
			value = get_data_path(value)
		elif hasdef:
			value = None
		if not value and hasdef:
			value = defval
		if debug:
			print "- falling back to", value
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


def get_current_profile(include_display_profile=False):
	""" Get the currently selected profile (if any) """
	path = getcfg("calibration.file", False)
	if path:
		import ICCProfile as ICCP
		try:
			profile = ICCP.ICCProfile(path)
		except (IOError, ICCP.ICCProfileInvalidError), exception:
			return
		return profile
	elif include_display_profile:
		return get_display_profile()


def get_display_profile(display_no=None):
	if display_no is None:
		display_no = max(getcfg("display.number") - 1, 0)
	if is_virtual_display(display_no):
		return None
	import ICCProfile as ICCP
	try:
		return ICCP.get_display_profile(display_no)
	except Exception, exception:
		from log import _safe_print, log
		_safe_print("ICCP.get_display_profile(%s):" % display_no, 
					exception, fn=log)


standard_profiles = []


def get_standard_profiles(paths_only=False):
	if not standard_profiles:
		import ICCProfile as ICCP
		from log import safe_print
		# Reference profiles (Argyll + dispcalGUI)
		ref_icc = get_data_path("ref", "\.ic[cm]$") or []
		# Other profiles installed on the system
		other_icc = []
		rex = re.compile("\.ic[cm]$", re.IGNORECASE)
		for icc_dir in set(iccprofiles + iccprofiles_home):
			for dirpath, dirnames, basenames in os.walk(icc_dir):
				for basename in filter(rex.search, basenames):
					filename, ext = os.path.splitext(basename.lower())
					if (filename.endswith("_bas") or
						filename.endswith("_eci") or
						filename.endswith("adobergb1998") or
						filename.startswith("eci-rgb") or
						filename.startswith("ecirgb") or
						filename.startswith("ekta space") or
						filename.startswith("ektaspace") or
						filename.startswith("fogra") or
						filename.startswith("gracol") or
						filename.startswith("iso") or
						filename.startswith("lstar-") or
						filename.startswith("pso_") or
						filename.startswith("prophoto") or
						filename.startswith("psr_") or
						filename.startswith("psrgravure") or
						filename.startswith("snap") or
						filename.startswith("srgb") or
						filename.startswith("swop") or
						filename in ("applergb",
									 "bestrgb",
									 "betargb",
									 "brucergb",
									 "ciergb",
									 "cie-rgb",
									 "colormatchrgb",
									 "donrgb",
									 "widegamutrgb")):
						other_icc.append(os.path.join(dirpath, basename))
		for path in ref_icc + other_icc:
			try:
				profile = ICCP.ICCProfile(path, load=False)
			except EnvironmentError:
				pass
			except Exception, exception:
				safe_print(exception)
			else:
				if (profile.version < 4 and
					profile.profileClass != "nmcl" and
					profile.colorSpace != "GRAY" and
					profile.connectionColorSpace in ("Lab", "XYZ")):
					standard_profiles.append(profile)
	if paths_only:
		return [profile.fileName for profile in standard_profiles]
	return standard_profiles


def get_total_patches(white_patches=None, black_patches=None,
					  single_channel_patches=None, gray_patches=None,
					  multi_steps=None, multi_bcc_steps=None,
					  fullspread_patches=None):
	if white_patches is None:
		white_patches = getcfg("tc_white_patches")
	if black_patches is None and getcfg("argyll.version") >= "1.6":
		black_patches = getcfg("tc_black_patches")
	if single_channel_patches is None:
		single_channel_patches = getcfg("tc_single_channel_patches")
	single_channel_patches_total = single_channel_patches * 3
	if gray_patches is None:
		gray_patches = getcfg("tc_gray_patches")
	if gray_patches == 0 and single_channel_patches > 0 and white_patches > 0:
		gray_patches = 2
	if multi_steps is None:
		multi_steps = getcfg("tc_multi_steps")
	if multi_bcc_steps is None and getcfg("argyll.version") >= "1.6":
		multi_bcc_steps = getcfg("tc_multi_bcc_steps")
	if fullspread_patches is None:
		fullspread_patches = getcfg("tc_fullspread_patches")
	total_patches = 0
	if multi_steps > 1:
		multi_patches = int(math.pow(multi_steps, 3))
		if multi_bcc_steps > 1:
			multi_patches += int(math.pow(multi_bcc_steps - 1, 3))
		total_patches += multi_patches
		white_patches -= 1 # white always in multi channel patches

		multi_step = 255.0 / (multi_steps - 1)
		multi_values = []
		multi_bcc_values = []
		if multi_bcc_steps > 1:
			multi_bcc_step = multi_step
			for i in range(multi_bcc_steps):
				multi_values.append(str(multi_bcc_step  * i))
			for i in range(multi_bcc_steps * 2 - 1):
				multi_bcc_values.append(str(multi_bcc_step / 2.0  * i))
		else:
			for i in range(multi_steps):
				multi_values.append(str(multi_step * i))
		if single_channel_patches > 1:
			single_channel_step = 255.0 / (single_channel_patches - 1)
			for i in range(single_channel_patches):
				if str(single_channel_step * i) in multi_values:
					single_channel_patches_total -= 3
		if gray_patches > 1:
			gray_step = 255.0 / (gray_patches - 1)
			for i in range(gray_patches):
				if (str(gray_step * i) in multi_values or
					str(gray_step * i) in multi_bcc_values):
					gray_patches -= 1
	elif gray_patches > 1:
		white_patches -= 1  # white always in gray patches
		single_channel_patches_total -= 3  # black always in gray patches
	elif single_channel_patches_total:
		# black always only once in single channel patches
		single_channel_patches_total -= 2
	total_patches += max(0, white_patches) + \
					 max(0, single_channel_patches_total) + \
					 max(0, gray_patches) + fullspread_patches
	if black_patches:
		if gray_patches > 1 or single_channel_patches_total or multi_steps:
			black_patches -= 1  # black always in other patches
		total_patches += black_patches
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


def is_ccxx_testchart(testchart=None):
	""" Check wether the testchart is the default chart for CCMX/CCSS creation """
	testchart = testchart or getcfg("testchart.file")
	return testchart == get_ccxx_testchart()


def is_profile(filename=None, include_display_profile=False):
	filename = filename or getcfg("calibration.file", False)
	if filename:
		if os.path.exists(filename):
			import ICCProfile as ICCP
			try:
				profile = ICCP.ICCProfile(filename)
			except (IOError, ICCP.ICCProfileInvalidError):
				pass
			else:
				return True
	elif include_display_profile:
		return bool(get_display_profile())
	return False


def makecfgdir(which="user", worker=None):
	if which == "user":
		if not os.path.exists(confighome):
			try:
				os.makedirs(confighome)
			except Exception, exception:
				from log import safe_print
				safe_print(u"Warning - could not create configuration directory "
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
			from log import safe_print
			safe_print(u"Warning - could not create configuration directory "
					   "'%s': %s" % (config_sys, safe_unicode(exception)))
			return False
	return True


def initcfg(module=None):
	"""
	Initialize the configuration.
	
	Read in settings if the configuration file exists, else create the 
	settings directory if nonexistent.
	
	"""
	if module:
		cfgbasename = "%s-%s" % (appname, module)
	else:
		cfgbasename = appname
	# read pre-v0.2.2b configuration if present
	if sys.platform == "darwin":
		oldcfg = os.path.join(expanduseru("~"), "Library", "Preferences", 
							  appname + " Preferences")
	else:
		oldcfg = os.path.join(expanduseru("~"), "." + appname)
	makecfgdir()
	if os.path.exists(confighome) and \
	   not os.path.exists(os.path.join(confighome, cfgbasename + ".ini")):
		try:
			if os.path.isfile(oldcfg):
				oldcfg_file = open(oldcfg, "rb")
				oldcfg_contents = oldcfg_file.read()
				oldcfg_file.close()
				cfg_file = open(os.path.join(confighome, cfgbasename + ".ini"), 
								"wb")
				cfg_file.write("[Default]\n" + oldcfg_contents)
				cfg_file.close()
			elif sys.platform == "win32":
				key = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, 
									  "Software\\" + appname)
				numsubkeys, numvalues, mtime = _winreg.QueryInfoKey(key)
				cfg_file = open(os.path.join(confighome, cfgbasename + ".ini"), 
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
	cfgnames = []
	if module != "3DLUT-maker":
		cfgnames.append(appname)
	if module:
		cfgnames.append(cfgbasename)
	else:
		cfgnames.extend("%s-%s" % (appname, othermod) for othermod in
						("synthprofile", "testchart-editor"))
	cfgroots = [confighome]
	if module == "apply-profiles":
		cfgroots.append(config_sys)
	cfgfiles = []
	for cfgname in cfgnames:
		for cfgroot in cfgroots:
			cfgfile = os.path.join(cfgroot, cfgname + ".ini")
			if os.path.isfile(cfgfile):
				cfgfiles.append(cfgfile)
				# Make user config take precedence
				break
	cfgfiles.sort(key=lambda cfgfile: os.stat(cfgfile).st_mtime)
	try:
		cfg.read(cfgfiles)
		# This won't raise an exception if the file does not exist, only
		# if it can't be parsed
	except Exception, exception:
		from log import safe_print
		safe_print("Warning - could not parse configuration files:\n%s" %
				   "\n".join(cfgfiles))


def setcfg(name, value):
	""" Set an option value in the configuration. """
	if value is None:
		cfg.remove_option(ConfigParser.DEFAULTSECT, name)
	else:
		cfg.set(ConfigParser.DEFAULTSECT, name, unicode(value).encode("UTF-8"))


def writecfg(which="user", worker=None, module=None, options=()):
	"""
	Write configuration file.
	
	which: 'user' or 'system'
	worker: worker instance if which == 'system'
	
	"""
	if module:
		cfgbasename = "%s-%s" % (appname, module)
	else:
		cfgbasename = appname
	if which == "user":
		# user config - stores everything and overrides system-wide config
		cfgfilename = os.path.join(confighome, cfgbasename + ".ini")
		try:
			io = StringIO()
			cfg.write(io)
			io.seek(0)
			lines = io.read().strip("\n").split("\n")
			if options:
				optionlines = []
				for optionline in lines[1:]:
					for option in options:
						if optionline.startswith(option):
							optionlines.append(optionline)
			else:
				optionlines = lines[1:]
			# Sorting works as long as config has only one section
			lines = lines[:1] + sorted(optionlines)
			cfgfile = open(cfgfilename, "wb")
			cfgfile.write("\n".join(lines))
			cfgfile.close()
		except Exception, exception:
			from log import safe_print
			safe_print(u"Warning - could not write user configuration file "
					   "'%s': %s" % (cfgfilename, safe_unicode(exception)))
			return False
	else:
		# system-wide config - only stores essentials ie. Argyll directory
		cfgfilename1 = os.path.join(confighome, cfgbasename + ".local.ini")
		cfgfilename2 = os.path.join(config_sys, cfgbasename + ".ini")
		if sys.platform == "win32":
			cfgfilename = cfgfilename2
		else:
			cfgfilename = cfgfilename1
		try:
			cfgfile = open(cfgfilename, "wb")
			if getcfg("argyll.dir"):
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
			from log import safe_print
			safe_print(u"Warning - could not write system-wide configuration file "
					   "'%s': %s" % (cfgfilename2, safe_unicode(exception)))
			return False
	return True

_init_testcharts()
runtype = runtimeconfig(pyfile)
