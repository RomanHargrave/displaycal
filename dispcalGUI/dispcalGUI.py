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

import sys

def _early_excepthook(etype, value, tb):
	import traceback
	traceback.print_exception(etype, value, tb)
	try:
		from util_os import expanduseru
		traceback.print_exception(etype, value, tb, file = open(os.path.join(expanduseru("~"), "dispcalGUI.error.log"), "w"))
	except:
		pass

sys.excepthook = _early_excepthook

# version check
pyver = map(int, sys.version.split()[0].split(".")[0:2])
if pyver < [2, 5] or pyver >= [3]:
	raise RuntimeError("Need Python version >= 2.5 < 3.0, got %s" % 
	   sys.version.split()[0])

# standard modules

import ConfigParser
ConfigParser.DEFAULTSECT = "Default"
import decimal
Decimal = decimal.Decimal
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
from StringIOu import StringIOu as StringIO, universal_newlines
from thread import start_new_thread
from time import sleep, strftime

# 3rd party modules

if sys.platform == "darwin":
	try:
		import appscript
	except ImportError: # we can fall back to osascript shell command
		appscript = None
elif sys.platform == "win32":
	from SendKeys import SendKeys
	from win32com.shell import shell, shellcon
	import _winreg
	import pythoncom
	import win32api
	import win32con

if not hasattr(sys, "frozen") or not sys.frozen:
	import wxversion
	try:
		wxversion.ensureMinimal("2.8")
	except:
		import wx
		if wx.VERSION < (2, 8):
			raise
import wx.lib.delayedresult as delayedresult
import wx.lib.hyperlink

# custom modules

import CGATS
import ICCProfile as ICCP
import config
import lang
import pyi_md5pickuphelper
from argyll_RGB2XYZ import RGB2XYZ as argyll_RGB2XYZ
from argyll_cgats import cal_to_fake_profile, can_update_cal, extract_cal_from_ti3, ti3_to_ti1, verify_ti1_rgb_xyz
from argyll_instruments import instruments, remove_vendor_names
from argyll_names import names as argyll_names, altnames as argyll_altnames
from colormath import CIEDCCT2xyY, xyY2CCT, XYZ2CCT, XYZ2RGB, XYZ2xyY
from config import autostart, autostart_home, btn_width_correction, cmdfile_ext, confighome, runtimeconfig, data_dirs, datahome, defaults, enc, exe, exe_ext, exedir, fs_enc, getbitmap, get_data_path, getcfg, get_verified_path, iccprofiles, iccprofiles_home, initcfg, isexe, profile_ext, resfiles, setcfg, storage, writecfg
from debughelpers import getevtobjname, getevttype, handle_error
from log import log, logbuffer, safe_print, setup_logging
from meta import author, name as appname, version
from natsort import natsort
from options import debug, test, verbose
from trash import trash, TrashcanUnavailableError
from util_decimal import stripzeros
from util_io import Files, Tea
from util_list import indexi
from util_os import expanduseru, expandvarsu, getenvu, get_sudo, listdir_re, putenvu, quote_args, which
from util_str import center, wrap
try:
	from wxLUTViewer import LUTFrame
except ImportError:
	LUTFrame = None
from wxMeasureFrame import MeasureFrame
from wxTestchartEditor import TestchartEditor
from wxaddons import wx, CustomEvent, CustomGridCellEvent, FileDrop, IsSizer
from wxwindows import AboutDialog, ConfirmDialog, InfoDialog, InvincibleFrame, LogWindow, TooltipWindow

# init

runtimeconfig(__file__)

from config import pypath, pydir, pyname, pyext, isapp, runtype, build

def _excepthook(etype, value, tb):
	handle_error("".join(traceback.format_exception(etype, value, tb)))

sys.excepthook = _excepthook

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
		initcfg()
		if verbose >= 1: safe_print(lang.getstr("startup"))
		if sys.platform != "darwin":
			if not autostart:
				safe_print(lang.getstr("warning.autostart_system"))
			if not autostart_home:
				safe_print(lang.getstr("warning.autostart_user"))
		self.init_frame()
		self.init_defaults()
		self.init_gamapframe()
		self.init_infoframe()
		self.init_measureframe()
		self.enumerate_displays_and_ports()
		if verbose >= 1: safe_print(lang.getstr("initializing_gui"))
		self.init_menus()
		self.init_controls()
		self.fixup()
		self.framesizer.SetSizeHints(self)
		self.framesizer.Layout()
		# we add the header and settings list after layout so it won't stretch the window further than necessary
		self.header = wx.StaticBitmap(self.headercontainer, -1, getbitmap("theme/header"))
		self.calibration_file_ctrl.SetItems([lang.getstr("settings.new")] + [("* " if cal == getcfg("calibration.file") and getcfg("settings.changed") else "") + lang.getstr(os.path.basename(cal)) for cal in self.recent_cals[1:]])
		self.calpanel.SetScrollRate(0, 20)
		self.update_controls(update_profile_name = False)
		if verbose >= 1: safe_print(lang.getstr("success"))
		self.update_displays()
		self.update_comports()
		self.update_profile_name()
		self.SetSaneGeometry(int(getcfg("position.x")), int(getcfg("position.y")))
		wx.CallAfter(self.ShowAll)
		if len(self.displays):
			if getcfg("calibration.file"):
				self.load_cal(silent = True) # load LUT curves from last used .cal file
			else:
				self.load_display_profile_cal(None) # load LUT curves from current display profile (if any, and if it contains curves)
		if verbose >= 1: safe_print(lang.getstr("ready"))
		logger = logging.getLogger()
		for handler in logger.handlers:
			if isinstance(handler, logging.StreamHandler):
				logger.removeHandler(handler)
		logbuffer.seek(0)
		self.infoframe.Log("".join(line for line in logbuffer).rstrip("\n"))

	def init_defaults(self):
		# defaults
		defaults.update({
			"last_cal_path": os.path.join(storage, lang.getstr("unnamed")),
			"last_cal_or_icc_path": os.path.join(storage, lang.getstr("unnamed")),
			"last_filedialog_path": os.path.join(storage, lang.getstr("unnamed")),
			"last_icc_path": os.path.join(storage, lang.getstr("unnamed")),
			"last_ti1_path": os.path.join(storage, lang.getstr("unnamed")),
			"last_ti3_path": os.path.join(storage, lang.getstr("unnamed")),
			"position.info.x": self.GetDisplay().ClientArea[0] + 20,
			"position.info.y": self.GetDisplay().ClientArea[1] + 40,
			"position.lut_viewer.x": self.GetDisplay().ClientArea[0] + 30,
			"position.lut_viewer.y": self.GetDisplay().ClientArea[1] + 50,
			"position.x": self.GetDisplay().ClientArea[0] + 10,
			"position.y": self.GetDisplay().ClientArea[1] + 30
		})
		
		self.argyll_version_string = ""
		self.argyll_version = [0, 0, 0]

		self.lut_access = [] # displays where lut access works

		self.options_dispcal = []
		self.options_targen = []
		if debug: safe_print("Setting targen options:", self.options_targen)
		self.options_dispread = []
		self.options_colprof = []
		
		self.dispread_after_dispcal = None

		self.recent_cals = getcfg("recent_cals").split(os.pathsep)
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
			lang.getstr("whitepoint.colortemp.locus.daylight"),
			lang.getstr("whitepoint.colortemp.locus.blackbody")
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
		defaults["testchart.file"] = get_data_path(os.path.join("ti1", self.testchart_defaults[defaults["measurement_mode"]][defaults["profile.type"]]))
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
			lang.getstr("trc.type.relative"),
			lang.getstr("trc.type.absolute")
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
			"": lang.getstr("tc.ofp"),
			"t": lang.getstr("tc.t"),
			"r": lang.getstr("tc.r"),
			"R": lang.getstr("tc.R"),
			"q": lang.getstr("tc.q"),
			"i": lang.getstr("tc.i"),
			"I": lang.getstr("tc.I")
		}

		self.tc_algos_ba = {
			lang.getstr("tc.ofp"): "",
			lang.getstr("tc.t"): "t",
			lang.getstr("tc.r"): "r",
			lang.getstr("tc.R"): "R",
			lang.getstr("tc.q"): "q",
			lang.getstr("tc.i"): "i",
			lang.getstr("tc.I"): "I"
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
			lstr = lang.getstr("gamap.viewconds.%s" % v)
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
					self.default_testchart_names += [lang.getstr(self.testchart_defaults[measurement_mode][profile_type])]

	def init_frame(self):
		# window frame
		wx.Frame.__init__(self, None, -1, "%s %s build %s" % (appname, version, build), style = wx.DEFAULT_FRAME_STYLE)
		self.SetMaxSize((-1, -1))
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
			setcfg("position.x", x)
			setcfg("position.y", y)
		display_client_rect = self.GetDisplay().ClientArea
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
			if size[1] > display_client_rect[3] - safety_margin: # or fullheight > display_client_rect[3] - safety_margin:
				if verbose >= 2: safe_print("Our full height (w/o scrollbars: %s) is too tall for that workspace! Adjusting..." % fullheight)
				vsize = self.calpanel.GetSize()
				maxheight = vsize[1] - (size[1] - display_client_rect[3] + safety_margin)
			elif not hasattr(self, "display_client_rect"):
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
		self.Bind(wx.EVT_IDLE, self.frame_enableresize_handler)
		size = self.GetSize()
		self.Freeze()
		self.SetMaxSize((size[0], fullheight))
		self.calpanel.SetMaxSize((-1, virtualheight))
		self.calpanel.SetMinSize((-1, 64))
		self.calpanel.SetMaxSize((-1, height))
		self.calpanel.SetSize((-1, height))
		if debug:
			safe_print("New framesizer min height:", self.framesizer.GetMinSize()[1])
			safe_print("New framesizer height:", self.framesizer.GetSize()[1])
		self.SetMinSize((self.GetMinSize()[0], newheight))
		self.SetMaxSize((size[0], newheight))
		self.SetSize((size[0], newheight))
		# self.Fit()
		self.Thaw()
		wx.CallLater(100, self.calpanel.SetMaxSize, (-1, -1))

	def frame_enableresize_handler(self, event = None):
		if verbose >= 2:
			safe_print("Enabling window resize")
		wx.CallLater(100, self.SetMinSize, (self.GetMinSize()[0], self.GetSize()[1] - self.calpanel.GetSize()[1] + 64))
		wx.CallLater(150, self.SetMaxSize, (-1, -1))
		self.Unbind(wx.EVT_IDLE)
		if event:
			event.Skip()

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
			InfoDialog(self, msg = lang.getstr("error.file_type_unsupported"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))

	def enumerate_displays_and_ports(self, silent = False):
		if (silent and self.check_argyll_bin()) or (not silent and self.check_set_argyll_bin()):
			displays = list(self.displays)
			if verbose >= 1 and not silent: safe_print(lang.getstr("enumerating_displays_and_comports"))
			self.exec_cmd(self.get_argyll_util("dispcal"), [], capture_output = True, skip_cmds = True, silent = True, log_output = False)
			arg = None
			self.displays = []
			self.comports = []
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
							self.comports.append(value)
			if test:
				inames = instruments.keys()
				inames.sort()
				for iname in inames:
					if not iname in self.comports:
						self.comports.append(iname)
			if verbose >= 1 and not silent: safe_print(lang.getstr("success"))
			if displays != self.displays:
				# check lut access
				i = 0
				for disp in self.displays:
					if verbose >= 1 and not silent: safe_print(lang.getstr("checking_lut_access", (i + 1)))
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
							safe_print(lang.getstr("success"))
						else:
							safe_print(lang.getstr("failure"))
					i += 1

	def init_gamapframe(self):
		gamap = self.gamapframe = InvincibleFrame(self, -1, lang.getstr("gamapframe.title"), pos = (-1, 100), style = (wx.DEFAULT_FRAME_STYLE | wx.FRAME_NO_TASKBAR) & ~(wx.RESIZE_BORDER | wx.RESIZE_BOX | wx.MAXIMIZE_BOX | wx.MINIMIZE_BOX))
		gamap.SetIcon(wx.Icon(get_data_path(os.path.join("theme", "icons", "16x16", appname + ".png")), wx.BITMAP_TYPE_PNG))

		panel = gamap.panel = wx.Panel(gamap, -1)
		sizer = self.gamapframe.sizer = wx.BoxSizer(wx.VERTICAL)
		gamap.panel.SetSizer(gamap.sizer)

		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(hsizer, flag = wx.ALL & ~wx.BOTTOM | wx.EXPAND, border = 12)
		hsizer.Add(wx.StaticText(panel, -1, lang.getstr("gamap.profile")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		self.gamap_profile = wx.FilePickerCtrl(panel, -1, "", message = lang.getstr("gamap.profile"), wildcard = lang.getstr("filetype.icc") + "|*.icc;*.icm")
		gamap.Bind(wx.EVT_FILEPICKER_CHANGED, self.gamap_profile_handler, id = self.gamap_profile.GetId())
		hsizer.Add(self.gamap_profile, 1, flag = wx.ALIGN_CENTER_VERTICAL)

		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(hsizer, flag = wx.ALL & ~wx.BOTTOM | wx.EXPAND, border = 12)
		self.gamap_perceptual_cb = wx.CheckBox(gamap.panel, -1, lang.getstr("gamap.perceptual"))
		gamap.Bind(wx.EVT_CHECKBOX, self.gamap_perceptual_cb_handler, id = self.gamap_perceptual_cb.GetId())
		hsizer.Add(self.gamap_perceptual_cb)

		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(hsizer, flag = wx.ALL & ~wx.BOTTOM | wx.EXPAND, border = 12)
		self.gamap_saturation_cb = wx.CheckBox(gamap.panel, -1, lang.getstr("gamap.saturation"))
		gamap.Bind(wx.EVT_CHECKBOX, self.gamap_saturation_cb_handler, id = self.gamap_saturation_cb.GetId())
		hsizer.Add(self.gamap_saturation_cb)

		hsizer = wx.FlexGridSizer(3, 2)
		sizer.Add(hsizer, flag = wx.ALL | wx.EXPAND, border = 12)

		hsizer.Add(wx.StaticText(panel, -1, lang.getstr("gamap.src_viewcond")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		self.gamap_src_viewcond_ctrl = wx.ComboBox(panel, -1, choices = sorted(self.viewconds_ab.values()), style = wx.CB_READONLY)
		gamap.Bind(wx.EVT_COMBOBOX, self.gamap_src_viewcond_handler, id = self.gamap_src_viewcond_ctrl.GetId())
		hsizer.Add(self.gamap_src_viewcond_ctrl, 1, flag = wx.ALIGN_CENTER_VERTICAL)

		hsizer.Add((0, 8))
		hsizer.Add((0, 8))

		hsizer.Add(wx.StaticText(panel, -1, lang.getstr("gamap.out_viewcond")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		self.gamap_out_viewcond_ctrl = wx.ComboBox(panel, -1, choices = sorted(self.viewconds_out_ab.values()), style = wx.CB_READONLY)
		gamap.Bind(wx.EVT_COMBOBOX, self.gamap_out_viewcond_handler, id = self.gamap_out_viewcond_ctrl.GetId())
		hsizer.Add(self.gamap_out_viewcond_ctrl, 1, flag = wx.ALIGN_CENTER_VERTICAL)

		for child in gamap.GetAllChildren():
			if hasattr(child, "SetFont"):
				child.SetMaxFontSize(11)

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
				InfoDialog(self.gamapframe, msg = lang.getstr("profile.invalid"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
		self.gamap_perceptual_cb.Enable(p)
		self.gamap_saturation_cb.Enable(p)
		c = self.gamap_perceptual_cb.GetValue() or self.gamap_saturation_cb.GetValue()
		self.gamap_src_viewcond_ctrl.Enable(p and c)
		self.gamap_out_viewcond_ctrl.Enable(p and c)
		if v != getcfg("gamap_profile"):
			self.profile_settings_changed()
		setcfg("gamap_profile", v)

	def gamap_perceptual_cb_handler(self, event = None):
		v = self.gamap_perceptual_cb.GetValue()
		if not v:
			self.gamap_saturation_cb.SetValue(False)
			self.gamap_saturation_cb_handler()
		if int(v) != getcfg("gamap_perceptual"):
			self.profile_settings_changed()
		setcfg("gamap_perceptual", int(v))
		self.gamap_profile_handler()

	def gamap_saturation_cb_handler(self, event = None):
		v = self.gamap_saturation_cb.GetValue()
		if v:
			self.gamap_perceptual_cb.SetValue(True)
			self.gamap_perceptual_cb_handler()
		if int(v) != getcfg("gamap_saturation"):
			self.profile_settings_changed()
		setcfg("gamap_saturation", int(v))
		self.gamap_profile_handler()

	def gamap_src_viewcond_handler(self, event = None):
		v = self.viewconds_ba[self.gamap_src_viewcond_ctrl.GetStringSelection()]
		if v != getcfg("gamap_src_viewcond"):
			self.profile_settings_changed()
		setcfg("gamap_src_viewcond", v)

	def gamap_out_viewcond_handler(self, event = None):
		v = self.viewconds_ba[self.gamap_out_viewcond_ctrl.GetStringSelection()]
		if v != getcfg("gamap_out_viewcond"):
			self.profile_settings_changed()
		setcfg("gamap_out_viewcond", v)

	def init_infoframe(self):
		self.infoframe = LogWindow(self)

	def init_measureframe(self):
		self.measureframe = MeasureFrame(self, -1)

	def init_menus(self):
		# menu
		menubar = wx.MenuBar()

		file_ = wx.Menu()
		menuitem = file_.Append(-1, "&" + lang.getstr("calibration.load") + "\tCtrl+O")
		self.Bind(wx.EVT_MENU, self.load_cal_handler, menuitem)
		menuitem = file_.Append(-1, "&" + lang.getstr("testchart.set"))
		self.Bind(wx.EVT_MENU, self.testchart_btn_handler, menuitem)
		menuitem = file_.Append(-1, "&" + lang.getstr("testchart.edit"))
		self.Bind(wx.EVT_MENU, self.create_testchart_btn_handler, menuitem)
		menuitem = file_.Append(-1, "&" + lang.getstr("profile.set_save_path"))
		self.Bind(wx.EVT_MENU, self.profile_save_path_btn_handler, menuitem)
		if sys.platform != "darwin":
			file_.AppendSeparator()
		menuitem = file_.Append(-1, "&" + lang.getstr("menuitem.set_argyll_bin"))
		self.Bind(wx.EVT_MENU, self.set_argyll_bin_handler, menuitem)
		if sys.platform == "darwin":
			self.app.SetMacPreferencesMenuItemId(menuitem.GetId())
		if sys.platform != "darwin":
			file_.AppendSeparator()
		menuitem = file_.Append(-1, "&" + lang.getstr("menuitem.quit") + "\tCtrl+Q")
		self.Bind(wx.EVT_MENU, self.OnClose, menuitem)
		if sys.platform == "darwin":
			self.app.SetMacExitMenuItemId(menuitem.GetId())
		menubar.Append(file_, "&" + lang.getstr("menu.file"))

		extra = wx.Menu()
		menuitem = extra.Append(-1, "&" + lang.getstr("create_profile"))
		menuitem.Enable(bool(len(self.displays)))
		self.Bind(wx.EVT_MENU, self.create_profile_handler, menuitem)
		menuitem = extra.Append(-1, "&" + lang.getstr("install_display_profile"))
		menuitem.Enable(bool(len(self.displays)))
		self.Bind(wx.EVT_MENU, self.install_profile_handler, menuitem)
		menuitem = extra.Append(-1, "&" + lang.getstr("calibration.load_from_cal_or_profile"))
		menuitem.Enable(bool(len(self.displays)))
		self.Bind(wx.EVT_MENU, self.load_profile_cal_handler, menuitem)
		menuitem = extra.Append(-1, "&" + lang.getstr("calibration.load_from_display_profile"))
		menuitem.Enable(bool(len(self.displays)))
		self.Bind(wx.EVT_MENU, self.load_display_profile_cal, menuitem)
		menuitem = extra.Append(-1, "&" + lang.getstr("calibration.show_lut"))
		menuitem.Enable(bool(LUTFrame))
		self.Bind(wx.EVT_MENU, self.init_lut_viewer, menuitem)
		menuitem = extra.Append(-1, "&" + lang.getstr("calibration.reset"))
		menuitem.Enable(bool(len(self.displays)))
		self.Bind(wx.EVT_MENU, self.reset_cal, menuitem)
		menuitem = extra.Append(-1, "&" + lang.getstr("report.calibrated"))
		menuitem.Enable(bool(len(self.displays)) and bool(len(self.comports)))
		self.Bind(wx.EVT_MENU, self.report_calibrated_handler, menuitem)
		menuitem = extra.Append(-1, "&" + lang.getstr("report.uncalibrated"))
		menuitem.Enable(bool(len(self.displays)) and bool(len(self.comports)))
		self.Bind(wx.EVT_MENU, self.report_uncalibrated_handler, menuitem)
		menuitem = extra.Append(-1, "&" + lang.getstr("calibration.verify"))
		menuitem.Enable(bool(len(self.displays)) and bool(len(self.comports)))
		self.Bind(wx.EVT_MENU, self.verify_calibration_handler, menuitem)
		extra.AppendSeparator()
		menuitem = extra.Append(-1, "&" + lang.getstr("detect_displays_and_ports"))
		self.Bind(wx.EVT_MENU, self.check_update_controls, menuitem)
		extra.AppendSeparator()
		menuitem = extra.Append(-1, "&" + lang.getstr("enable_spyder2"))
		self.Bind(wx.EVT_MENU, self.enable_spyder2_handler, menuitem)
		extra.AppendSeparator()
		menuitem = extra.Append(-1, "&" + lang.getstr("restore_defaults"))
		self.Bind(wx.EVT_MENU, self.restore_defaults_handler, menuitem)
		extra.AppendSeparator()
		menuitem = extra.Append(-1, "&" + lang.getstr("infoframe.toggle"))
		self.Bind(wx.EVT_MENU, self.infoframe_toggle_handler, menuitem)
		menubar.Append(extra, "&" + lang.getstr("menu.extra"))

		languages = wx.Menu()
		llist = [(lang.ldict[lcode].get("language"), lcode) for lcode in lang.ldict]
		llist.sort()
		for lstr, lcode in llist:
			if getcfg("lang") == lcode:
				kind = wx.ITEM_RADIO
			else:
				kind = wx.ITEM_NORMAL
			menuitem = languages.Append(-1, "&" + lstr, kind = kind)
			lang.ldict[lcode]["id"] = menuitem.GetId() # map numerical event id to language string
			self.Bind(wx.EVT_MENU, self.set_language_handler, menuitem)
		menubar.Append(languages, "&" + lang.getstr("menu.language"))

		help = wx.Menu()
		menuitem = help.Append(-1, "&" + lang.getstr("menu.about"))
		self.Bind(wx.EVT_MENU, self.aboutdialog_handler, menuitem)
		if sys.platform == "darwin":
			self.app.SetMacAboutMenuItemId(menuitem.GetId())
			self.app.SetMacHelpMenuTitleName(lang.getstr("menu.help"))
		menubar.Append(help, "&" + lang.getstr("menu.help"))

		self.SetMenuBar(menubar)


	def init_controls(self):

		# logo
		self.AddToSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.EXPAND)
		self.headercontainer = wx.ScrolledWindow(self.panel, -1, size = (480, 60), style = wx.VSCROLL) # the width also sets the initial minimal width of the main window
		self.headercontainer.SetScrollRate(0, 0)
		self.AddToSubSizer(self.headercontainer, 1)



		self.AddToSizer(wx.FlexGridSizer(0, 2), flag = wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border = 18)
		self.subsizer[-1].AddGrowableCol(1, 1)

		# calibration file (.cal)
		self.calibration_file_label = wx.StaticText(self.panel, -1, lang.getstr("calibration.file"))
		self.AddToSubSizer(self.calibration_file_label, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border = 8)

		self.calibration_file_ctrl = wx.ComboBox(self.panel, -1, choices = [], style = wx.CB_READONLY)
		self.Bind(wx.EVT_COMBOBOX, self.calibration_file_ctrl_handler, id = self.calibration_file_ctrl.GetId())
		self.AddToSubSizer(self.calibration_file_ctrl, 1, flag = wx.ALIGN_CENTER_VERTICAL)

		self.AddToSubSizer((8, 0))

		self.calibration_file_btn = wx.BitmapButton(self.panel, -1, getbitmap("theme/icons/16x16/document-open"), style = wx.NO_BORDER)
		self.Bind(wx.EVT_BUTTON, self.load_cal_handler, id = self.calibration_file_btn.GetId())
		self.AddToSubSizer(self.calibration_file_btn, flag = wx.ALIGN_CENTER_VERTICAL)
		self.calibration_file_btn.SetToolTipString(lang.getstr("calibration.load"))

		self.AddToSubSizer((8, 0))

		self.delete_calibration_btn = wx.BitmapButton(self.panel, -1, getbitmap("theme/icons/16x16/edit-delete"), style = wx.NO_BORDER)
		self.delete_calibration_btn.SetBitmapDisabled(getbitmap("transparent16x16"))
		self.Bind(wx.EVT_BUTTON, self.delete_calibration_handler, id = self.delete_calibration_btn.GetId())
		self.AddToSubSizer(self.delete_calibration_btn, flag = wx.ALIGN_CENTER_VERTICAL)
		self.delete_calibration_btn.SetToolTipString(lang.getstr("delete"))

		self.AddToSubSizer((8, 0))

		self.install_profile_btn = wx.BitmapButton(self.panel, -1, getbitmap("theme/icons/16x16/install"), style = wx.NO_BORDER)
		self.install_profile_btn.SetBitmapDisabled(getbitmap("transparent16x16"))
		self.Bind(wx.EVT_BUTTON, self.install_cal_handler, id = self.install_profile_btn.GetId())
		self.AddToSubSizer(self.install_profile_btn, flag = wx.ALIGN_CENTER_VERTICAL)
		self.install_profile_btn.SetToolTipString(lang.getstr("profile.install"))

		self.subsizer.pop()

		self.AddToSubSizer(wx.StaticText(self.panel, -1, "")) # empty cell

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 8)

		# update calibration?
		self.calibration_update_cb = wx.CheckBox(self.panel, -1, lang.getstr("calibration.update"))
		self.calibration_update_cb.SetValue(bool(int(getcfg("calibration.update"))))
		self.Bind(wx.EVT_CHECKBOX, self.calibration_update_ctrl_handler, id = self.calibration_update_cb.GetId())
		self.AddToSubSizer(self.calibration_update_cb, flag = wx.ALIGN_CENTER_VERTICAL)

		self.AddToSubSizer((8, 0))

		# update corresponding profile?
		self.profile_update_cb = wx.CheckBox(self.panel, -1, lang.getstr("profile.update"))
		self.profile_update_cb.SetValue(bool(int(getcfg("profile.update"))))
		self.Bind(wx.EVT_CHECKBOX, self.profile_update_ctrl_handler, id = self.profile_update_cb.GetId())
		self.AddToSubSizer(self.profile_update_cb, flag = wx.ALIGN_CENTER_VERTICAL)



		# display & instrument
		self.AddToSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.EXPAND)



		# display
		self.AddToSubSizer(wx.StaticBoxSizer(wx.StaticBox(self.panel, -1, lang.getstr("display")), wx.VERTICAL), 1, flag = wx.ALL | wx.EXPAND, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), 1, flag = wx.ALIGN_CENTER_VERTICAL | wx.ALL | wx.EXPAND, border = 5)

		show_lut_ctrl = (len(self.displays) > 1 and False in self.lut_access and True in self.lut_access) or test

		if show_lut_ctrl:
			self.AddToSubSizer(wx.FlexGridSizer(3, 3), 1, flag = wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
			self.subsizer[-1].AddGrowableCol(2, 1)
			self.display_label = wx.StaticText(self.panel, -1, lang.getstr("measure"))
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
			self.lut_label = wx.StaticText(self.panel, -1, lang.getstr("lut_access"))
			self.AddToSubSizer(self.lut_label, flag = wx.ALIGN_CENTER_VERTICAL)
			self.AddToSubSizer((8, 1))
			self.display_lut_ctrl = wx.ComboBox(self.panel, -1, choices = [], style = wx.CB_READONLY)
			self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), 1, flag = wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
			self.Bind(wx.EVT_COMBOBOX, self.display_lut_ctrl_handler, id = self.display_lut_ctrl.GetId())
			self.AddToSubSizer(self.display_lut_ctrl, 1, flag = wx.ALIGN_CENTER_VERTICAL)
			self.subsizer.pop()
			self.subsizer.pop()
			self.display_lut_link_ctrl = wx.BitmapButton(self.panel, -1, getbitmap("theme/icons/16x16/stock_lock-open"), style = wx.NO_BORDER)
			self.Bind(wx.EVT_BUTTON, self.display_lut_link_ctrl_handler, id = self.display_lut_link_ctrl.GetId())
			self.AddToSubSizer(self.display_lut_link_ctrl, flag = wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border = 8)
			self.display_lut_link_ctrl.SetToolTipString(lang.getstr("display_lut.link"))

		self.subsizer.pop()

		self.subsizer.pop()



		# instrument
		self.AddToSubSizer(wx.StaticBoxSizer(wx.StaticBox(self.panel, -1, lang.getstr("instrument")), wx.VERTICAL), flag = wx.ALL | wx.EXPAND, border = 8)

		if show_lut_ctrl:
			self.AddToSubSizer(wx.BoxSizer(wx.VERTICAL), 1, flag = wx.ALL | wx.EXPAND, border = 5)
			self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), 1, flag = wx.EXPAND)
		else:
			self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), 1, flag = wx.ALL | wx.EXPAND, border = 5)

		self.comport_ctrl = wx.ComboBox(self.panel, -1, choices = [], style = wx.CB_READONLY, size = (150, -1))
		self.Bind(wx.EVT_COMBOBOX, self.comport_ctrl_handler, id = self.comport_ctrl.GetId())
		self.AddToSubSizer(self.comport_ctrl, 1, flag = wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)

		if show_lut_ctrl:
			self.subsizer.pop()
			self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP, border = 8)

		self.measurement_mode_label = wx.StaticText(self.panel, -1, lang.getstr("measurement_mode"))
		if show_lut_ctrl:
			borders = wx.RIGHT
		else:
			borders = wx.LEFT | wx.RIGHT
		self.AddToSubSizer(self.measurement_mode_label, flag = borders | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.measurement_mode_ctrl = wx.ComboBox(self.panel, -1, size = (100, -1), choices = [""] * 4, style = wx.CB_READONLY)
		self.Bind(wx.EVT_COMBOBOX, self.measurement_mode_ctrl_handler, id = self.measurement_mode_ctrl.GetId())
		self.AddToSubSizer(self.measurement_mode_ctrl, flag = wx.ALIGN_CENTER_VERTICAL)



		# calibration settings sizer
		self.AddToSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border = 4)
		self.AddToSubSizer(wx.StaticLine(self.panel, -1, size = (8, -1)), 0, flag = wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border = 8)
		self.AddToSubSizer(wx.StaticText(self.panel, -1, lang.getstr("calibration.settings")), 0, flag = wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, border = 2)
		self.AddToSubSizer(wx.StaticLine(self.panel, -1), 1, flag = wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border = 8)
		self.calpanel = wx.ScrolledWindow(self.panel, -1, style = wx.TAB_TRAVERSAL | wx.VSCROLL)
		self.AddToSizer(self.calpanel, 1, flag = wx.RIGHT | wx.LEFT | wx.EXPAND, border = 18)
		self.AddToSizer((1, 6))
		self.AddToSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border = 4)
		self.AddToSubSizer(wx.StaticLine(self.panel, -1), 1, flag = wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, border = 8)
		# self.AddToSizer(wx.StaticBoxSizer(wx.StaticBox(self.panel, -1, lang.getstr("calibration.settings")), wx.VERTICAL), 1, flag = wx.RIGHT | wx.LEFT | wx.EXPAND, border = 8)
		# self.calpanel = TransparentScrolledWindow(self.panel, -1, style = wx.TAB_TRAVERSAL | wx.VSCROLL)
		# self.AddToSubSizer(self.calpanel, 1, flag = wx.BOTTOM | wx.RIGHT | wx.LEFT | wx.EXPAND, border = 5)
		self.calpanel.sizer = wx.FlexGridSizer(0, 2)
		self.subsizer.append(self.calpanel.sizer)
		self.calpanel.SetSizer(self.calpanel.sizer)



		# whitepoint
		self.whitepoint_label = wx.StaticText(self.calpanel, -1, lang.getstr("whitepoint"))
		self.AddToSubSizer(self.whitepoint_label, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.whitepoint_native_rb = wx.RadioButton(self.calpanel, -1, lang.getstr("native"), (10, 10), style = wx.RB_GROUP)
		self.Bind(wx.EVT_RADIOBUTTON, self.whitepoint_ctrl_handler, id = self.whitepoint_native_rb.GetId())
		self.AddToSubSizer(self.whitepoint_native_rb, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.whitepoint_colortemp_rb = wx.RadioButton(self.calpanel, -1, lang.getstr("whitepoint.colortemp"), (10, 10))
		self.Bind(wx.EVT_RADIOBUTTON, self.whitepoint_ctrl_handler, id = self.whitepoint_colortemp_rb.GetId())
		self.AddToSubSizer(self.whitepoint_colortemp_rb, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.whitepoint_colortemp_textctrl = wx.ComboBox(self.calpanel, -1, "", size = (75, -1), choices = self.whitepoint_presets)
		self.Bind(wx.EVT_COMBOBOX, self.whitepoint_ctrl_handler, id = self.whitepoint_colortemp_textctrl.GetId())
		self.whitepoint_colortemp_textctrl.Bind(wx.EVT_KILL_FOCUS, self.whitepoint_ctrl_handler)
		self.AddToSubSizer(self.whitepoint_colortemp_textctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 0)

		self.whitepoint_colortemp_label = wx.StaticText(self.calpanel, -1, u"° K")
		self.AddToSubSizer(self.whitepoint_colortemp_label, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.whitepoint_colortemp_locus_ctrl = wx.ComboBox(self.calpanel, -1, size = (-1, -1), choices = self.whitepoint_colortemp_loci, style = wx.CB_READONLY)
		self.Bind(wx.EVT_COMBOBOX, self.whitepoint_colortemp_locus_ctrl_handler, id = self.whitepoint_colortemp_locus_ctrl.GetId())
		self.AddToSubSizer(self.whitepoint_colortemp_locus_ctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 0)
		
		self.AddToSubSizer((24, 1)) # padding to avoid overlapping scrollbar

		self.subsizer.pop()

		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, "")) # empty cell

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.whitepoint_xy_rb = wx.RadioButton(self.calpanel, -1, lang.getstr("whitepoint.xy"), (10, 10))
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
		
		self.AddToSubSizer((24, 1)) # padding to avoid overlapping scrollbar

		self.subsizer.pop()



		# white luminance
		self.calibration_luminance_label = wx.StaticText(self.calpanel, -1, lang.getstr("calibration.luminance"))
		self.AddToSubSizer(self.calibration_luminance_label, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.luminance_max_rb = wx.RadioButton(self.calpanel, -1, lang.getstr("maximal"), (10, 10), style = wx.RB_GROUP)
		self.Bind(wx.EVT_RADIOBUTTON, self.luminance_ctrl_handler, id = self.luminance_max_rb.GetId())
		self.AddToSubSizer(self.luminance_max_rb, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.luminance_cdm2_rb = wx.RadioButton(self.calpanel, -1, lang.getstr("other"), (10, 10))
		self.Bind(wx.EVT_RADIOBUTTON, self.luminance_ctrl_handler, id = self.luminance_cdm2_rb.GetId())
		self.AddToSubSizer(self.luminance_cdm2_rb, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.luminance_textctrl = wx.TextCtrl(self.calpanel, -1, "", size = (50, -1))
		self.luminance_textctrl.Bind(wx.EVT_KILL_FOCUS, self.luminance_ctrl_handler)
		self.AddToSubSizer(self.luminance_textctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 0)

		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, u"cd/m²"), flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.subsizer.pop()



		# black luminance
		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, lang.getstr("calibration.black_luminance")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.black_luminance_min_rb = wx.RadioButton(self.calpanel, -1, lang.getstr("minimal"), (10, 10), style = wx.RB_GROUP)
		self.Bind(wx.EVT_RADIOBUTTON, self.black_luminance_ctrl_handler, id = self.black_luminance_min_rb.GetId())
		self.AddToSubSizer(self.black_luminance_min_rb, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.black_luminance_cdm2_rb = wx.RadioButton(self.calpanel, -1, lang.getstr("other"), (10, 10))
		self.Bind(wx.EVT_RADIOBUTTON, self.black_luminance_ctrl_handler, id = self.black_luminance_cdm2_rb.GetId())
		self.AddToSubSizer(self.black_luminance_cdm2_rb, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.black_luminance_textctrl = wx.TextCtrl(self.calpanel, -1, "", size = (50, -1))
		self.black_luminance_textctrl.Bind(wx.EVT_KILL_FOCUS, self.black_luminance_ctrl_handler)
		self.AddToSubSizer(self.black_luminance_textctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 0)

		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, u"cd/m²"), flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.subsizer.pop()



		# trc
		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, lang.getstr("trc")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.trc_g_rb = wx.RadioButton(self.calpanel, -1, lang.getstr("trc.gamma"), (10, 10), style = wx.RB_GROUP)
		self.Bind(wx.EVT_RADIOBUTTON, self.trc_ctrl_handler, id = self.trc_g_rb.GetId())
		self.AddToSubSizer(self.trc_g_rb, 1, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.trc_textctrl = wx.ComboBox(self.calpanel, -1, str(defaults["gamma"]), size = (60, -1), choices = self.trc_presets)
		self.Bind(wx.EVT_COMBOBOX, self.trc_ctrl_handler, id = self.trc_textctrl.GetId())
		self.trc_textctrl.Bind(wx.EVT_KILL_FOCUS, self.trc_ctrl_handler)
		self.AddToSubSizer(self.trc_textctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 0)

		self.AddToSubSizer((8, 0))

		self.trc_type_ctrl = wx.ComboBox(self.calpanel, -1, size = (-1, -1), choices = self.trc_types, style = wx.CB_READONLY)
		self.Bind(wx.EVT_COMBOBOX, self.trc_type_ctrl_handler, id = self.trc_type_ctrl.GetId())
		self.AddToSubSizer(self.trc_type_ctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 0)

		self.subsizer.pop()

		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, "")) # empty cell

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.trc_l_rb = wx.RadioButton(self.calpanel, -1, lang.getstr("trc.lstar"), (10, 10))
		self.Bind(wx.EVT_RADIOBUTTON, self.trc_ctrl_handler, id = self.trc_l_rb.GetId())
		self.AddToSubSizer(self.trc_l_rb, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.trc_rec709_rb = wx.RadioButton(self.calpanel, -1, lang.getstr("trc.rec709"), (10, 10))
		self.Bind(wx.EVT_RADIOBUTTON, self.trc_ctrl_handler, id = self.trc_rec709_rb.GetId())
		self.AddToSubSizer(self.trc_rec709_rb, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.trc_smpte240m_rb = wx.RadioButton(self.calpanel, -1, lang.getstr("trc.smpte240m"), (10, 10))
		self.Bind(wx.EVT_RADIOBUTTON, self.trc_ctrl_handler, id = self.trc_smpte240m_rb.GetId())
		self.AddToSubSizer(self.trc_smpte240m_rb, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.trc_srgb_rb = wx.RadioButton(self.calpanel, -1, lang.getstr("trc.srgb"), (10, 10))
		self.Bind(wx.EVT_RADIOBUTTON, self.trc_ctrl_handler, id = self.trc_srgb_rb.GetId())
		self.AddToSubSizer(self.trc_srgb_rb, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.subsizer.pop()



		# viewing condition adjustment for ambient in Lux
		self.ambient_viewcond_adjust_cb = wx.CheckBox(self.calpanel, -1, lang.getstr("calibration.ambient_viewcond_adjust"))
		self.AddToSubSizer(self.ambient_viewcond_adjust_cb, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.Bind(wx.EVT_CHECKBOX, self.ambient_viewcond_adjust_ctrl_handler, id = self.ambient_viewcond_adjust_cb.GetId())

		self.ambient_viewcond_adjust_textctrl = wx.TextCtrl(self.calpanel, -1, "", size = (50, -1))
		self.ambient_viewcond_adjust_textctrl.Bind(wx.EVT_KILL_FOCUS, self.ambient_viewcond_adjust_ctrl_handler)
		self.AddToSubSizer(self.ambient_viewcond_adjust_textctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 0)

		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, "Lux"), flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.ambient_viewcond_adjust_info = wx.BitmapButton(self.calpanel, -1, getbitmap("theme/icons/16x16/dialog-information"), style = wx.NO_BORDER)
		self.ambient_viewcond_adjust_info.SetBitmapDisabled(getbitmap("transparent16x16"))
		self.Bind(wx.EVT_BUTTON, self.ambient_viewcond_adjust_info_handler, id = self.ambient_viewcond_adjust_info.GetId())
		self.AddToSubSizer(self.ambient_viewcond_adjust_info, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		self.ambient_viewcond_adjust_info.SetToolTipString(wrap(lang.getstr("calibration.ambient_viewcond_adjust.info"), 76))

		self.subsizer.pop()



		# black level output offset
		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, lang.getstr("calibration.black_output_offset")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

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
		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, lang.getstr("calibration.black_point_correction")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 2)

		self.black_point_correction_ctrl = wx.Slider(self.calpanel, -1, 0, 0, 100, size = (128, -1))
		self.Bind(wx.EVT_SLIDER, self.black_point_correction_ctrl_handler, id = self.black_point_correction_ctrl.GetId())
		self.AddToSubSizer(self.black_point_correction_ctrl, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.black_point_correction_intctrl = wx.SpinCtrl(self.calpanel, -1, initial = 0, size = (65, -1), min = 0, max = 100)
		self.Bind(wx.EVT_TEXT, self.black_point_correction_ctrl_handler, id = self.black_point_correction_intctrl.GetId())
		self.AddToSubSizer(self.black_point_correction_intctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, "%"), flag = wx.ALIGN_CENTER_VERTICAL)

		# rate
		if defaults["calibration.black_point_rate.enabled"]:
			self.AddToSubSizer(wx.StaticText(self.calpanel, -1, lang.getstr("calibration.black_point_rate")), flag = wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.LEFT, border = 8)
			self.black_point_rate_ctrl = wx.Slider(self.calpanel, -1, 400, 5, 2000, size = (64, -1))
			self.Bind(wx.EVT_SLIDER, self.black_point_rate_ctrl_handler, id = self.black_point_rate_ctrl.GetId())
			self.AddToSubSizer(self.black_point_rate_ctrl, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 4)
			self.black_point_rate_intctrl = wx.SpinCtrl(self.calpanel, -1, initial = 400, size = (55, -1), min = 5, max = 2000)
			self.Bind(wx.EVT_TEXT, self.black_point_rate_ctrl_handler, id = self.black_point_rate_intctrl.GetId())
			self.AddToSubSizer(self.black_point_rate_intctrl, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)
		
		self.AddToSubSizer((24, 1)) # padding to avoid overlapping scrollbar

		self.subsizer.pop()



		# calibration quality
		self.AddToSubSizer(wx.StaticText(self.calpanel, -1, lang.getstr("calibration.quality")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.ALIGN_CENTER_VERTICAL, border = 3)

		self.calibration_quality_ctrl = wx.Slider(self.calpanel, -1, 2, 1, 3, size = (50, -1))
		self.Bind(wx.EVT_SLIDER, self.calibration_quality_ctrl_handler, id = self.calibration_quality_ctrl.GetId())
		self.AddToSubSizer(self.calibration_quality_ctrl, 1, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		self.calibration_quality_info = wx.StaticText(self.calpanel, -1, "-", size = (64, -1))
		self.AddToSubSizer(self.calibration_quality_info, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 4)

		# interactive display adjustment?
		self.interactive_display_adjustment_cb = wx.CheckBox(self.calpanel, -1, lang.getstr("calibration.interactive_display_adjustment"))
		self.Bind(wx.EVT_CHECKBOX, self.interactive_display_adjustment_ctrl_handler, id = self.interactive_display_adjustment_cb.GetId())
		self.AddToSubSizer(self.interactive_display_adjustment_cb, flag = wx.RIGHT | wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 10)
		
		self.AddToSubSizer((24, 1)) # padding to avoid overlapping scrollbar

		self.subsizer.pop()



		# profiling settings
		self.AddToSizer(wx.StaticBoxSizer(wx.StaticBox(self.panel, -1, lang.getstr("profile.settings")), wx.VERTICAL), flag = wx.TOP | wx.RIGHT | wx.LEFT | wx.EXPAND, border = 8)
		self.AddToSubSizer(wx.FlexGridSizer(0, 2), flag = wx.RIGHT | wx.LEFT | wx.EXPAND, border = 5)
		self.subsizer[-1].AddGrowableCol(1, 1)


		# testchart file
		self.AddToSubSizer(wx.StaticText(self.panel, -1, lang.getstr("testchart.file")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border = 5)

		self.testchart_ctrl = wx.ComboBox(self.panel, -1, choices = [], style = wx.CB_READONLY)
		self.Bind(wx.EVT_COMBOBOX, self.testchart_ctrl_handler, id = self.testchart_ctrl.GetId())
		self.AddToSubSizer(self.testchart_ctrl, 1, flag = wx.ALIGN_CENTER_VERTICAL)

		self.AddToSubSizer((8, 0))

		self.testchart_btn = wx.BitmapButton(self.panel, -1, getbitmap("theme/icons/16x16/document-open"), style = wx.NO_BORDER)
		self.testchart_btn.SetBitmapDisabled(getbitmap("transparent16x16"))
		self.Bind(wx.EVT_BUTTON, self.testchart_btn_handler, id = self.testchart_btn.GetId())
		self.AddToSubSizer(self.testchart_btn, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		self.testchart_btn.SetToolTipString(lang.getstr("testchart.set"))

		self.create_testchart_btn = wx.BitmapButton(self.panel, -1, getbitmap("theme/icons/16x16/rgbsquares"), style = wx.NO_BORDER)
		self.create_testchart_btn.SetBitmapDisabled(getbitmap("transparent16x16"))
		self.Bind(wx.EVT_BUTTON, self.create_testchart_btn_handler, id = self.create_testchart_btn.GetId())
		self.AddToSubSizer(self.create_testchart_btn, flag = wx.ALIGN_CENTER_VERTICAL)
		self.create_testchart_btn.SetToolTipString(lang.getstr("testchart.edit"))

		self.testchart_patches_amount = wx.StaticText(self.panel, -1, " ", size = (50, -1))
		self.AddToSubSizer(self.testchart_patches_amount, flag = wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		self.testchart_patches_amount.SetToolTipString(lang.getstr("testchart.info"))

		self.subsizer.pop()



		# profile quality
		self.AddToSubSizer(wx.StaticText(self.panel, -1, lang.getstr("profile.quality")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 2)

		self.profile_quality_ctrl = wx.Slider(self.panel, -1, 2, 1, 3, size = (50, -1))
		self.Bind(wx.EVT_SLIDER, self.profile_quality_ctrl_handler, id = self.profile_quality_ctrl.GetId())
		self.AddToSubSizer(self.profile_quality_ctrl, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.profile_quality_info = wx.StaticText(self.panel, -1, "-", size = (64, -1))
		self.AddToSubSizer(self.profile_quality_info, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 20)

		# profile type
		self.AddToSubSizer(wx.StaticText(self.panel, -1, lang.getstr("profile.type")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		self.profile_type_ctrl = wx.ComboBox(self.panel, -1, size = (-1, -1), choices = self.profile_types, style = wx.CB_READONLY)
		self.Bind(wx.EVT_COMBOBOX, self.profile_type_ctrl_handler, id = self.profile_type_ctrl.GetId())
		self.AddToSubSizer(self.profile_type_ctrl, flag = wx.ALIGN_CENTER_VERTICAL)

		self.AddToSubSizer((8, 0))

		# advanced (gamut mapping)
		label = lang.getstr("profile.advanced_gamap")
		self.gamap_btn = wx.Button(self.panel, -1, label)
		self.gamap_btn.SetInitialSize((self.gamap_btn.GetSize()[0] + btn_width_correction, -1))
		self.Bind(wx.EVT_BUTTON, self.gamap_btn_handler, id = self.gamap_btn.GetId())
		self.AddToSubSizer(self.gamap_btn, flag = wx.ALIGN_CENTER_VERTICAL)

		self.subsizer.pop()



		# profile name
		self.AddToSubSizer(wx.StaticText(self.panel, -1, lang.getstr("profile.name")), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border = 4)

		self.profile_name_textctrl = wx.TextCtrl(self.panel, -1, "")
		self.Bind(wx.EVT_TEXT, self.profile_name_ctrl_handler, id = self.profile_name_textctrl.GetId())
		self.AddToSubSizer(self.profile_name_textctrl, 1, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		# self.profile_name_textctrl.SetToolTipString(wrap(self.profile_name_info(), 76))

		self.profile_name_info_btn = wx.BitmapButton(self.panel, -1, getbitmap("theme/icons/16x16/dialog-information"), style = wx.NO_BORDER)
		self.profile_name_info_btn.SetBitmapDisabled(getbitmap("transparent16x16"))
		self.Bind(wx.EVT_BUTTON, self.profile_name_info_btn_handler, id = self.profile_name_info_btn.GetId())
		self.AddToSubSizer(self.profile_name_info_btn, flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		self.profile_name_info_btn.SetToolTipString(wrap(self.profile_name_info(), 76))

		self.profile_save_path_btn = wx.BitmapButton(self.panel, -1, getbitmap("theme/icons/16x16/media-floppy"), style = wx.NO_BORDER)
		self.profile_save_path_btn.SetBitmapDisabled(getbitmap("transparent16x16"))
		self.Bind(wx.EVT_BUTTON, self.profile_save_path_btn_handler, id = self.profile_save_path_btn.GetId())
		self.AddToSubSizer(self.profile_save_path_btn, flag = wx.ALIGN_CENTER_VERTICAL)
		self.profile_save_path_btn.SetToolTipString(lang.getstr("profile.set_save_path"))

		self.AddToSubSizer(wx.StaticText(self.panel, -1, "", size = (50, -1)), flag = wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 8)

		self.subsizer.pop()

		self.AddToSubSizer(wx.StaticText(self.panel, -1, ""), flag = wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		
		self.AddToSubSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.ALIGN_CENTER_VERTICAL | wx.EXPAND, border = 4)
		
		self.profile_name = wx.StaticText(self.panel, -1, " ")
		self.AddToSubSizer(self.profile_name, 1, flag = wx.RIGHT | wx.BOTTOM | wx.ALIGN_CENTER_VERTICAL, border = 4)

		# self.create_profile_name_btn = wx.BitmapButton(self.panel, -1, getbitmap("theme/icons/16x16/stock_refresh"), style = wx.NO_BORDER)
		# self.create_profile_name_btn.SetBitmapDisabled(getbitmap("transparent16x16"))
		# self.Bind(wx.EVT_BUTTON, self.create_profile_name_btn_handler, id = self.create_profile_name_btn.GetId())
		# self.AddToSubSizer(self.create_profile_name_btn, flag = wx.ALIGN_CENTER_VERTICAL)
		# self.create_profile_name_btn.SetToolTipString(lang.getstr("profile.name.create"))

		# self.AddToSubSizer(wx.StaticText(self.panel, -1, "", size = (50, -1)), flag = wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border = 8)
		
		self.subsizer.pop()



		# buttons
		self.AddToSizer(wx.BoxSizer(wx.HORIZONTAL), flag = wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER, border = 16)

		# NOTE on the commented out lines below: If we ever get a working wexpect (pexpect for Windows), we could implement those

		#self.blacklevel_btn = wx.BitmapButton(self.panel, -1, getbitmap("theme/icons/16x16/blacklevel"), style = wx.NO_BORDER)
		#self.Bind(wx.EVT_BUTTON, self.blacklevel_btn_handler, id = self.blacklevel_btn.GetId())
		#self.AddToSubSizer(self.blacklevel_btn, flag = wx.ALIGN_CENTER_VERTICAL)

		#self.AddToSubSizer((16, 0))

		#self.whitelevel_btn = wx.BitmapButton(self.panel, -1, getbitmap("theme/icons/16x16/whitelevel"), style = wx.NO_BORDER)
		#self.Bind(wx.EVT_BUTTON, self.whitelevel_btn_handler, id = self.whitelevel_btn.GetId())
		#self.AddToSubSizer(self.whitelevel_btn, flag = wx.ALIGN_CENTER_VERTICAL)

		#self.AddToSubSizer((16, 0))

		#self.whitepoint_btn = wx.BitmapButton(self.panel, -1, getbitmap("theme/icons/16x16/whitepoint"), style = wx.NO_BORDER)
		#self.Bind(wx.EVT_BUTTON, self.whitepoint_btn_handler, id = self.whitepoint_btn.GetId())
		#self.AddToSubSizer(self.whitepoint_btn, flag = wx.ALIGN_CENTER_VERTICAL)

		#self.AddToSubSizer((16, 0))

		#self.blackpoint_btn = wx.BitmapButton(self.panel, -1, getbitmap("theme/icons/16x16/blackpoint"), style = wx.NO_BORDER)
		#self.Bind(wx.EVT_BUTTON, self.blackpoint_btn_handler, id = self.blackpoint_btn.GetId())
		#self.AddToSubSizer(self.blackpoint_btn, flag = wx.ALIGN_CENTER_VERTICAL)

		#self.AddToSubSizer((16, 0))

		label = lang.getstr("button.calibrate")
		self.calibrate_btn = wx.Button(self.panel, -1, label)
		self.calibrate_btn.SetInitialSize((self.calibrate_btn.GetSize()[0] + btn_width_correction, -1))
		self.Bind(wx.EVT_BUTTON, self.calibrate_btn_handler, id = self.calibrate_btn.GetId())
		self.AddToSubSizer(self.calibrate_btn, flag = wx.ALIGN_CENTER_VERTICAL)

		self.AddToSubSizer((16, 0))

		label = lang.getstr("button.calibrate_and_profile")
		self.calibrate_and_profile_btn = wx.Button(self.panel, -1, label)
		self.calibrate_and_profile_btn.SetInitialSize((self.calibrate_and_profile_btn.GetSize()[0] + btn_width_correction, -1))
		self.Bind(wx.EVT_BUTTON, self.calibrate_and_profile_btn_handler, id = self.calibrate_and_profile_btn.GetId())
		self.AddToSubSizer(self.calibrate_and_profile_btn, flag = wx.ALIGN_CENTER_VERTICAL)

		self.AddToSubSizer((16, 0))

		label = lang.getstr("button.profile")
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
			item.SetMaxFontSize(11)
		for name in dir(self):
			if name[-4:] in ("ctrl", "_btn") or name[-3:] in ("_cb", "_rb"):
				attr = getattr(self, name)
				attr.SetName(name)
				attr.SetMaxFontSize(11)
				if sys.platform == "darwin" or debug:
					if isinstance(attr, wx.ComboBox):
						if attr.IsEditable():
							if debug: safe_print("Binding EVT_TEXT to", name)
							attr.Bind(wx.EVT_TEXT, self.focus_handler)
					else:
						attr.Bind(wx.EVT_SET_FOCUS, self.focus_handler)

	def focus_handler(self, event):
		if hasattr(self, "last_focused_object") and self.last_focused_object and self.last_focused_object != event.GetEventObject():
			catchup_event = wx.FocusEvent(wx.EVT_KILL_FOCUS.evtType[0], self.last_focused_object.GetId())
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

	def AddToSizer(self, item, proportion = 0, flag = 0, border = 0, userData = None):
		self.sizer.Add(item, proportion, flag, border, userData)
		if IsSizer(item):
			self.subsizer.append(item)
		elif isinstance(item, wx.StaticText):
			self.static_labels += [item]
		return item

	def AddToSubSizer(self, item, proportion = 0, flag = 0, border = 0, userData = None):
		self.subsizer[-1].Add(item, proportion, flag, border, userData)
		if IsSizer(item):
			self.subsizer.append(item)
		elif isinstance(item, wx.StaticText):
			self.static_labels += [item]
		return item

	def set_language_handler(self, event):
		for lcode in lang.ldict:
			if lang.ldict[lcode]["id"] == event.GetId():
				setcfg("lang", lcode)
				writecfg()
				InfoDialog(self, msg = lang.getstr("app.restart_request", lcode = lcode), ok = lang.getstr("ok", lcode = lcode), bitmap = getbitmap("theme/icons/32x32/dialog-information"), logit = False)
				break

	def restore_defaults_handler(self, event = None, include = (), exclude = ()):
		if event:
			dlg = ConfirmDialog(self, msg = lang.getstr("app.confirm_restore_defaults"), ok = lang.getstr("ok"), cancel = lang.getstr("cancel"), bitmap = getbitmap("theme/icons/32x32/dialog-warning"))
			result = dlg.ShowModal()
			dlg.Destroy()
			if result != wx.ID_OK: return
		skip = [
			"argyll.dir",
			"calibration.black_point_rate.enabled",
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
			"trc": defaults["gamma"],
			"whitepoint.colortemp": None,
			"whitepoint.x": None,
			"whitepoint.y": None
		}
		for name in defaults:
			if name not in skip and name not in override:
				if (len(include) == 0 or False in [name.find(item) < 0 for item in include]) and (len(exclude) == 0 or not (False in [name.find(item) < 0 for item in exclude])):
					if verbose >= 3: safe_print("Restoring %s to %s" % (name, defaults[name]))
					setcfg(name, defaults[name])
		for name in override:
			if (len(include) == 0 or False in [name.find(item) < 0 for item in include]) and (len(exclude) == 0 or not (False in [name.find(item) < 0 for item in exclude])):
				setcfg(name, override[name])
		if event:
			writecfg()
			self.update_displays()
			self.update_controls()
			if hasattr(self, "tcframe"):
				self.tcframe.tc_update_controls()

	def cal_changed(self, setchanged = True):
		if not self.updatingctrls:
			if setchanged:
				setcfg("settings.changed", 1)
			self.options_dispcal = []
			if debug: safe_print("cal_changed")
			if getcfg("calibration.file"):
				setcfg("calibration.file", None)
				self.load_display_profile_cal(None) # load LUT curves from current display profile (if any, and if it contains curves)
			self.calibration_file_ctrl.SetStringSelection(lang.getstr("settings.new"))
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
		display_no = int(getcfg("display.number")) - 1
		self.display_ctrl.SetSelection(min(len(self.displays) - 1, display_no))
		self.display_ctrl.Enable(display_ctrl_enable)
		if hasattr(self, "display_lut_ctrl"):
			self.display_lut_ctrl.Clear()
			i = 0
			for disp in self.displays:
				if self.lut_access[i]:
					self.display_lut_ctrl.Append(disp)
				i += 1
			self.display_lut_link_ctrl_handler(CustomEvent(wx.EVT_BUTTON.evtType[0], self.display_lut_link_ctrl), bool(int(getcfg("display_lut.link"))))
		self.display_ctrl.Thaw()

	def update_comports(self):
		self.comport_ctrl.Freeze()
		self.comport_ctrl.SetItems(self.comports)
		self.comport_ctrl.SetSelection(min(len(self.comports) - 1, int(getcfg("comport.number")) - 1))
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
				lang.getstr("default")
			]
		}
		instrument_type = self.get_instrument_type()
		instrument_features = self.get_instrument_features()
		if instrument_features.get("projector_mode"):
			if instrument_type == "spect":
				measurement_modes[instrument_type] += [
					lang.getstr("projector")
				]
			else:
				measurement_modes[instrument_type] += [
					"CRT-" + lang.getstr("projector"),
					"LCD-" + lang.getstr("projector")
				]
		self.measurement_mode_ctrl.Freeze()
		self.measurement_mode_ctrl.SetItems(measurement_modes[instrument_type])
		measurement_mode = getcfg("measurement_mode") or defaults["measurement_mode"]
		if getcfg("projector_mode"):
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
		cal = getcfg("calibration.file")

		if cal and self.check_file_isfile(cal):
			filename, ext = os.path.splitext(cal)
			if not cal in self.recent_cals:
				if len(self.recent_cals) > getcfg("recent_cals_max"):
					self.recent_cals.remove(self.recent_cals[len(self.presets)])
					self.calibration_file_ctrl.Delete(len(self.presets))
				self.recent_cals.append(cal)
				recent_cals = []
				for recent_cal in self.recent_cals:
					if recent_cal not in self.presets:
						recent_cals += [recent_cal]
				setcfg("recent_cals", os.pathsep.join(recent_cals))
				self.calibration_file_ctrl.Append(lang.getstr(os.path.basename(cal)))
			# the case-sensitive index could fail because of case insensitive file systems
			# e.g. the filename string from the cfg is "C:\Users\Name\AppData\dispcalGUI\storage\MyFile",
			# but the actual filename is "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
			# (maybe because the user manually renamed the file)
			try:
				idx = self.recent_cals.index(cal)
			except ValueError, exception:
				idx = indexi(self.recent_cals, cal)
			self.calibration_file_ctrl.SetSelection(idx)
			self.calibration_file_ctrl.SetToolTipString(cal)
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
			self.calibration_file_ctrl.SetStringSelection(lang.getstr("settings.new"))
			self.calibration_file_ctrl.SetToolTip(None)
			self.calibration_update_cb.SetValue(False)
			setcfg("calibration.file", None)
			setcfg("calibration.update", "0")
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
			setcfg("profile.update", "0")
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
			self.black_point_rate_ctrl.Enable(enable_cal and getcfg("calibration.black_point_correction") < 1 and defaults["calibration.black_point_rate.enabled"])
			self.black_point_rate_intctrl.Enable(enable_cal and getcfg("calibration.black_point_correction") < 1 and defaults["calibration.black_point_rate.enabled"])
		self.interactive_display_adjustment_cb.Enable(enable_cal)

		self.testchart_btn.Enable(enable_profile)
		self.create_testchart_btn.Enable(enable_profile)
		self.profile_quality_ctrl.Enable(enable_profile)
		self.profile_type_ctrl.Enable(enable_profile)

		measurement_mode = getcfg("measurement_mode") or defaults["measurement_mode"]
		if getcfg("projector_mode"):
			measurement_mode += "p"
		self.measurement_mode_ctrl.SetSelection(min(self.measurement_modes_ba[self.get_instrument_type()].get(measurement_mode, 0), len(self.measurement_mode_ctrl.GetItems()) - 1))

		self.whitepoint_colortemp_textctrl.SetValue(str(getcfg("whitepoint.colortemp")))
		self.whitepoint_x_textctrl.ChangeValue(str(getcfg("whitepoint.x")))
		self.whitepoint_y_textctrl.ChangeValue(str(getcfg("whitepoint.y")))
		self.whitepoint_colortemp_locus_ctrl.SetSelection(self.whitepoint_colortemp_loci_ba.get(getcfg("whitepoint.colortemp.locus"), 
			self.whitepoint_colortemp_loci_ba.get(defaults["whitepoint.colortemp.locus"])))
		if getcfg("whitepoint.colortemp", False):
			self.whitepoint_colortemp_rb.SetValue(True)
			self.whitepoint_ctrl_handler(CustomEvent(wx.EVT_RADIOBUTTON.evtType[0], self.whitepoint_colortemp_rb), False)
			self.whitepoint_colortemp_locus_ctrl.Enable(enable_cal)
		elif getcfg("whitepoint.x", False) and getcfg("whitepoint.y", False):
			self.whitepoint_xy_rb.SetValue(True)
			self.whitepoint_ctrl_handler(CustomEvent(wx.EVT_RADIOBUTTON.evtType[0], self.whitepoint_xy_rb), False)
			self.whitepoint_colortemp_locus_ctrl.Disable()
		else:
			self.whitepoint_native_rb.SetValue(True)
			# self.whitepoint_ctrl_handler(CustomEvent(wx.EVT_RADIOBUTTON.evtType[0], self.whitepoint_native_rb), False)
		self.whitepoint_colortemp_textctrl.Enable(enable_cal and bool(getcfg("whitepoint.colortemp", False)))
		self.whitepoint_x_textctrl.Enable(enable_cal and bool(getcfg("whitepoint.x", False)))
		self.whitepoint_y_textctrl.Enable(enable_cal and bool(getcfg("whitepoint.y", False)))

		if getcfg("calibration.luminance", False):
			self.luminance_cdm2_rb.SetValue(True)
		else:
			self.luminance_max_rb.SetValue(True)
		self.luminance_textctrl.ChangeValue(str(getcfg("calibration.luminance")))
		self.luminance_textctrl.Enable(enable_cal and bool(getcfg("calibration.luminance", False)))

		if getcfg("calibration.black_luminance", False):
			self.black_luminance_cdm2_rb.SetValue(True)
		else:
			self.black_luminance_min_rb.SetValue(True)
		self.black_luminance_textctrl.ChangeValue(str(getcfg("calibration.black_luminance")))
		self.black_luminance_textctrl.Enable(enable_cal and bool(getcfg("calibration.black_luminance", False)))

		trc = getcfg("trc")
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
			self.trc_type_ctrl.SetSelection(self.trc_types_ba.get(getcfg("trc.type"), self.trc_types_ba.get(defaults["trc.type"])))
			self.trc_type_ctrl.Enable(enable_cal)

		self.ambient_viewcond_adjust_cb.SetValue(bool(int(getcfg("calibration.ambient_viewcond_adjust"))))
		self.ambient_viewcond_adjust_textctrl.ChangeValue(str(getcfg("calibration.ambient_viewcond_adjust.lux")))
		self.ambient_viewcond_adjust_textctrl.Enable(enable_cal and bool(int(getcfg("calibration.ambient_viewcond_adjust"))))

		self.profile_type_ctrl.SetSelection(self.profile_types_ba.get(getcfg("profile.type"), self.profile_types_ba.get(defaults["profile.type"])))

		self.black_output_offset_ctrl.SetValue(int(Decimal(str(getcfg("calibration.black_output_offset"))) * 100))
		self.black_output_offset_intctrl.SetValue(int(Decimal(str(getcfg("calibration.black_output_offset"))) * 100))

		self.black_point_correction_ctrl.SetValue(int(Decimal(str(getcfg("calibration.black_point_correction"))) * 100))
		self.black_point_correction_intctrl.SetValue(int(Decimal(str(getcfg("calibration.black_point_correction"))) * 100))

		if hasattr(self, "black_point_rate_ctrl"):
			self.black_point_rate_ctrl.SetValue(int(Decimal(str(getcfg("calibration.black_point_rate"))) * 100))
			self.black_point_rate_intctrl.SetValue(int(Decimal(str(getcfg("calibration.black_point_rate"))) * 100))

		q = self.quality_ba.get(getcfg("calibration.quality"), self.quality_ba.get(defaults["calibration.quality"]))
		self.calibration_quality_ctrl.SetValue(q)
		if q == 1:
			self.calibration_quality_info.SetLabel(lang.getstr("calibration.quality.low"))
		elif q == 2:
			self.calibration_quality_info.SetLabel(lang.getstr("calibration.quality.medium"))
		elif q == 3:
			self.calibration_quality_info.SetLabel(lang.getstr("calibration.quality.high"))

		self.interactive_display_adjustment_cb.SetValue(enable_cal and bool(int(getcfg("calibration.interactive_display_adjustment"))))

		self.testchart_ctrl.Enable(enable_profile)
		if self.set_default_testchart() is None:
			self.set_testchart()

		q = self.quality_ba.get(getcfg("profile.quality"), self.quality_ba.get(defaults["profile.quality"]))
		self.profile_quality_ctrl.SetValue(q)
		if q == 1:
			self.profile_quality_info.SetLabel(lang.getstr("calibration.quality.low"))
		elif q == 2:
			self.profile_quality_info.SetLabel(lang.getstr("calibration.quality.medium"))
		elif q == 3:
			self.profile_quality_info.SetLabel(lang.getstr("calibration.quality.high"))
		elif q == 4:
			self.profile_quality_info.SetLabel(lang.getstr("calibration.quality.ultra"))

		enable_gamap = self.get_profile_type() in ("l", "x")
		self.gamap_btn.Enable(enable_profile and enable_gamap)

		self.gamap_profile.SetPath(getcfg("gamap_profile"))
		self.gamap_perceptual_cb.SetValue(getcfg("gamap_perceptual"))
		self.gamap_saturation_cb.SetValue(getcfg("gamap_saturation"))
		self.gamap_src_viewcond_ctrl.SetStringSelection(self.viewconds_ab.get(getcfg("gamap_src_viewcond"), self.viewconds_ab.get(defaults["gamap_src_viewcond"])))
		self.gamap_out_viewcond_ctrl.SetStringSelection(self.viewconds_ab.get(getcfg("gamap_out_viewcond"), self.viewconds_ab.get(defaults["gamap_out_viewcond"])))
		self.gamap_profile_handler()

		self.updatingctrls = False

		if update_profile_name:
			self.profile_name_textctrl.ChangeValue(getcfg("profile.name"))
			self.update_profile_name()

		self.update_main_controls()

	def calibration_update_ctrl_handler(self, event):
		if debug: safe_print("calibration_update_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		setcfg("calibration.update", int(self.calibration_update_cb.GetValue()))
		self.update_controls()

	def enable_spyder2_handler(self, event):
		if self.check_set_argyll_bin():
			cmd, args = self.get_argyll_util("spyd2en"), ["-v"]
			result = self.exec_cmd(cmd, args, capture_output = True, skip_cmds = True, silent = True)
			if result:
				InfoDialog(self, msg = lang.getstr("enable_spyder2_success"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-information"))
			else:
				# prompt for setup.exe
				defaultDir, defaultFile = expanduseru("~"), "setup.exe"
				dlg = wx.FileDialog(self, lang.getstr("locate_spyder2_setup"), defaultDir = defaultDir, defaultFile = defaultFile, wildcard = "*", style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
				dlg.Center(wx.BOTH)
				result = dlg.ShowModal()
				path = dlg.GetPath()
				dlg.Destroy()
				if result == wx.ID_OK:
					if not os.path.exists(path):
						InfoDialog(self, msg = lang.getstr("file.missing", path), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
						return
					result = self.exec_cmd(cmd, args + [path], capture_output = True, skip_cmds = True, silent = True)
					if result:
						InfoDialog(self, msg = lang.getstr("enable_spyder2_success"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-information"))
					else:
						InfoDialog(self, msg = lang.getstr("enable_spyder2_failure"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))

	def profile_update_ctrl_handler(self, event):
		if debug: safe_print("profile_update_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		setcfg("profile.update", int(self.profile_update_cb.GetValue()))
		self.update_controls()

	def profile_quality_warning_handler(self, event):
		q = self.get_profile_quality()
		if q == "u":
			InfoDialog(self, msg = lang.getstr("quality.ultra.warning"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-warning"), logit = False)

	def profile_quality_ctrl_handler(self, event):
		if debug: safe_print("profile_quality_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		q = self.get_profile_quality()
		if q == "l":
			self.profile_quality_info.SetLabel(lang.getstr("calibration.quality.low"))
		elif q == "m":
			self.profile_quality_info.SetLabel(lang.getstr("calibration.quality.medium"))
		elif q == "h":
			self.profile_quality_info.SetLabel(lang.getstr("calibration.quality.high"))
		if q == "u":
			self.profile_quality_info.SetLabel(lang.getstr("calibration.quality.ultra"))
		if q != getcfg("profile.quality"):
			self.profile_settings_changed()
		setcfg("profile.quality", q)
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
		if not keep_changed_state: setcfg("settings.changed", 0)
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
			idx = self.recent_cals.index(getcfg("calibration.file") or "")
		except ValueError, exception:
			idx = indexi(self.recent_cals, getcfg("calibration.file") or "")
		self.calibration_file_ctrl.SetSelection(idx)
		dlg = ConfirmDialog(self, msg = lang.getstr("warning.discard_changes"), ok = lang.getstr("ok"), cancel = lang.getstr("cancel"), bitmap = getbitmap("theme/icons/32x32/dialog-warning"))
		result = dlg.ShowModal()
		dlg.Destroy()
		if result != wx.ID_OK: return False
		self.settings_discard_changes(sel)
		return True

	def calibration_quality_ctrl_handler(self, event):
		if debug: safe_print("calibration_quality_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		q = self.get_calibration_quality()
		if q == "l":
			self.calibration_quality_info.SetLabel(lang.getstr("calibration.quality.low"))
		elif q == "m":
			self.calibration_quality_info.SetLabel(lang.getstr("calibration.quality.medium"))
		elif q == "h":
			self.calibration_quality_info.SetLabel(lang.getstr("calibration.quality.high"))
		if q != getcfg("calibration.quality"):
			self.profile_settings_changed()
		setcfg("calibration.quality", q)
		self.update_profile_name()

	def interactive_display_adjustment_ctrl_handler(self, event):
		if debug: safe_print("interactive_display_adjustment_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		v = self.get_interactive_display_adjustment()
		if v != str(getcfg("calibration.interactive_display_adjustment")):
			self.profile_settings_changed()
		setcfg("calibration.interactive_display_adjustment", v)

	def black_point_correction_ctrl_handler(self, event):
		if debug: safe_print("black_point_correction_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		if event.GetId() == self.black_point_correction_intctrl.GetId():
			self.black_point_correction_ctrl.SetValue(self.black_point_correction_intctrl.GetValue())
		else:
			self.black_point_correction_intctrl.SetValue(self.black_point_correction_ctrl.GetValue())
		v = self.get_black_point_correction()
		if float(v) != getcfg("calibration.black_point_correction"):
			self.cal_changed()
		setcfg("calibration.black_point_correction", v)
		if hasattr(self, "black_point_rate_ctrl"):
			self.black_point_rate_ctrl.Enable(getcfg("calibration.black_point_correction") < 1 and defaults["calibration.black_point_rate.enabled"])
			self.black_point_rate_intctrl.Enable(getcfg("calibration.black_point_correction") < 1 and defaults["calibration.black_point_rate.enabled"])
		self.update_profile_name()

	def black_point_rate_ctrl_handler(self, event):
		if debug: safe_print("black_point_rate_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		if event.GetId() == self.black_point_rate_intctrl.GetId():
			self.black_point_rate_ctrl.SetValue(self.black_point_rate_intctrl.GetValue())
		else:
			self.black_point_rate_intctrl.SetValue(self.black_point_rate_ctrl.GetValue())
		v = self.get_black_point_rate()
		if v != str(getcfg("calibration.black_point_rate")):
			self.cal_changed()
		setcfg("calibration.black_point_rate", v)
		self.update_profile_name()

	def black_output_offset_ctrl_handler(self, event):
		if debug: safe_print("black_output_offset_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		if event.GetId() == self.black_output_offset_intctrl.GetId():
			self.black_output_offset_ctrl.SetValue(self.black_output_offset_intctrl.GetValue())
		else:
			self.black_output_offset_intctrl.SetValue(self.black_output_offset_ctrl.GetValue())
		v = self.get_black_output_offset()
		if float(v) != getcfg("calibration.black_output_offset"):
			self.cal_changed()
		setcfg("calibration.black_output_offset", v)
		self.update_profile_name()

	def ambient_viewcond_adjust_ctrl_handler(self, event):
		if event.GetId() == self.ambient_viewcond_adjust_textctrl.GetId() and (not self.ambient_viewcond_adjust_cb.GetValue() or str(float(getcfg("calibration.ambient_viewcond_adjust.lux"))) == self.ambient_viewcond_adjust_textctrl.GetValue()):
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
					self.ambient_viewcond_adjust_textctrl.ChangeValue(str(getcfg("calibration.ambient_viewcond_adjust.lux")))
			if event.GetId() == self.ambient_viewcond_adjust_cb.GetId():
				self.ambient_viewcond_adjust_textctrl.SetFocus()
				self.ambient_viewcond_adjust_textctrl.SelectAll()
		else:
			self.ambient_viewcond_adjust_textctrl.Disable()
		v1 = int(self.ambient_viewcond_adjust_cb.GetValue())
		v2 = self.ambient_viewcond_adjust_textctrl.GetValue()
		if v1 != getcfg("calibration.ambient_viewcond_adjust") or v2 != str(getcfg("calibration.ambient_viewcond_adjust.lux", False)):
			self.cal_changed()
		setcfg("calibration.ambient_viewcond_adjust", v1)
		setcfg("calibration.ambient_viewcond_adjust.lux", v2)
		self.update_profile_name()
		if event.GetEventType() == wx.EVT_KILL_FOCUS.evtType[0]:
			event.Skip()

	def ambient_viewcond_adjust_info_handler(self, event):
		InfoDialog(self, msg = lang.getstr("calibration.ambient_viewcond_adjust.info"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-information"), logit = False)

	def black_luminance_ctrl_handler(self, event):
		if event.GetId() == self.black_luminance_textctrl.GetId() and (not self.black_luminance_cdm2_rb.GetValue() or str(float(getcfg("calibration.black_luminance"))) == self.black_luminance_textctrl.GetValue()):
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
				self.black_luminance_textctrl.ChangeValue(str(getcfg("calibration.black_luminance")))
			if event.GetId() == self.black_luminance_cdm2_rb.GetId():
				self.black_luminance_textctrl.SetFocus()
				self.black_luminance_textctrl.SelectAll()
		else:
			self.black_luminance_textctrl.Disable()
		v = self.get_black_luminance()
		if v != str(getcfg("calibration.black_luminance", False)):
			self.cal_changed()
		setcfg("calibration.black_luminance", v)
		self.update_profile_name()
		if event.GetEventType() == wx.EVT_KILL_FOCUS.evtType[0]:
			event.Skip()

	def luminance_ctrl_handler(self, event):
		if event.GetId() == self.luminance_textctrl.GetId() and (not self.luminance_cdm2_rb.GetValue() or str(float(getcfg("calibration.luminance"))) == self.luminance_textctrl.GetValue()):
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
				self.luminance_textctrl.ChangeValue(str(getcfg("calibration.luminance")))
			if event.GetId() == self.luminance_cdm2_rb.GetId():
				self.luminance_textctrl.SetFocus()
				self.luminance_textctrl.SelectAll()
		else:
			self.luminance_textctrl.Disable()
		v = self.get_luminance()
		if v != str(getcfg("calibration.luminance", False)):
			self.cal_changed()
		setcfg("calibration.luminance", v)
		self.update_profile_name()
		if event.GetEventType() == wx.EVT_KILL_FOCUS.evtType[0]:
			event.Skip()

	def whitepoint_colortemp_locus_ctrl_handler(self, event):
		if debug: safe_print("whitepoint_colortemp_locus_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		v = self.get_whitepoint_locus()
		if v != getcfg("whitepoint.colortemp.locus"):
			self.cal_changed()
		setcfg("whitepoint.colortemp.locus", v)
		self.update_profile_name()

	def whitepoint_ctrl_handler(self, event, cal_changed = True):
		if event.GetId() == self.whitepoint_colortemp_textctrl.GetId() and (not self.whitepoint_colortemp_rb.GetValue() or str(float(getcfg("whitepoint.colortemp"))) == self.whitepoint_colortemp_textctrl.GetValue()):
			event.Skip()
			return
		if event.GetId() == self.whitepoint_x_textctrl.GetId() and (not self.whitepoint_xy_rb.GetValue() or str(float(getcfg("whitepoint.x"))) == self.whitepoint_x_textctrl.GetValue()):
			event.Skip()
			return
		if event.GetId() == self.whitepoint_y_textctrl.GetId() and (not self.whitepoint_xy_rb.GetValue() or str(float(getcfg("whitepoint.y"))) == self.whitepoint_y_textctrl.GetValue()):
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
				self.whitepoint_x_textctrl.ChangeValue(str(getcfg("whitepoint.x")))
			try:
				v = float(self.whitepoint_y_textctrl.GetValue().replace(",", "."))
				if v < 0 or v > 1:
					raise ValueError()
				self.whitepoint_y_textctrl.ChangeValue(str(v))
			except ValueError:
				wx.Bell()
				self.whitepoint_y_textctrl.ChangeValue(str(getcfg("whitepoint.y")))
			x = self.whitepoint_x_textctrl.GetValue().replace(",", ".")
			y = self.whitepoint_y_textctrl.GetValue().replace(",", ".")
			k = xyY2CCT(float(x), float(y), 1.0)
			if k:
				self.whitepoint_colortemp_textctrl.SetValue(str(stripzeros(math.ceil(k))))
			else:
				self.whitepoint_colortemp_textctrl.SetValue("")
			if cal_changed:
				if not getcfg("whitepoint.colortemp") and float(x) == getcfg("whitepoint.x") and float(y) == getcfg("whitepoint.y"):
					cal_changed = False
			setcfg("whitepoint.colortemp", None)
			setcfg("whitepoint.x", x)
			setcfg("whitepoint.y", y)
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
				self.whitepoint_colortemp_textctrl.SetValue(str(getcfg("whitepoint.colortemp")))
			xyY = CIEDCCT2xyY(float(self.whitepoint_colortemp_textctrl.GetValue().replace(",", ".")))
			if xyY:
				self.whitepoint_x_textctrl.ChangeValue(str(stripzeros(round(xyY[0], 6))))
				self.whitepoint_y_textctrl.ChangeValue(str(stripzeros(round(xyY[1], 6))))
			else:
				self.whitepoint_x_textctrl.ChangeValue("")
				self.whitepoint_y_textctrl.ChangeValue("")
			if cal_changed:
				v = float(self.whitepoint_colortemp_textctrl.GetValue())
				if getcfg("whitepoint.colortemp") == v and not getcfg("whitepoint.x") and not getcfg("whitepoint.y"):
					cal_changed = False
			setcfg("whitepoint.colortemp", v)
			setcfg("whitepoint.x", None)
			setcfg("whitepoint.y", None)
			if event.GetId() == self.whitepoint_colortemp_rb.GetId() and not self.updatingctrls:
				self.whitepoint_colortemp_textctrl.SetFocus()
				self.whitepoint_colortemp_textctrl.SelectAll()
		else:
			self.whitepoint_colortemp_locus_ctrl.Enable()
			self.whitepoint_colortemp_textctrl.Disable()
			self.whitepoint_x_textctrl.Disable()
			self.whitepoint_y_textctrl.Disable()
			if not getcfg("whitepoint.colortemp") and not getcfg("whitepoint.x") and not getcfg("whitepoint.y"):
				cal_changed = False
			setcfg("whitepoint.colortemp", None)
			setcfg("whitepoint.x", None)
			setcfg("whitepoint.y", None)
		if cal_changed and not self.updatingctrls:
			self.cal_changed()
			self.update_profile_name()
		if event.GetEventType() == wx.EVT_KILL_FOCUS.evtType[0]:
			event.Skip()

	def trc_type_ctrl_handler(self, event):
		if debug: safe_print("trc_type_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		v = self.get_trc_type()
		if v != getcfg("trc.type"):
			self.cal_changed()
		setcfg("trc.type", v)
		self.update_profile_name()

	def trc_ctrl_handler(self, event, cal_changed = True):
		if event.GetId() == self.trc_textctrl.GetId() and (not self.trc_g_rb.GetValue() or stripzeros(getcfg("trc")) == stripzeros(self.trc_textctrl.GetValue())):
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
				self.trc_textctrl.SetValue(str(getcfg("trc")))
			if event.GetId() == self.trc_g_rb.GetId():
				self.trc_textctrl.SetFocus()
				self.trc_textctrl.SelectAll()
		else:
			self.trc_textctrl.Disable()
			self.trc_type_ctrl.Disable()
		trc = self.get_trc()
		if cal_changed:
			if trc != str(getcfg("trc")):
				self.cal_changed()
		setcfg("trc", trc)
		if cal_changed:
			self.update_profile_name()
		if event.GetEventType() == wx.EVT_KILL_FOCUS.evtType[0]:
			event.Skip()
		if trc in ("240", "709", "s") and not (bool(int(getcfg("calibration.ambient_viewcond_adjust"))) and getcfg("calibration.ambient_viewcond_adjust.lux")) and getcfg("trc.should_use_viewcond_adjust.show_msg"):
			dlg = InfoDialog(self, msg = lang.getstr("trc.should_use_viewcond_adjust"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-information"), show = False, logit = False)
			chk = wx.CheckBox(dlg, -1, lang.getstr("dialog.do_not_show_again"))
			dlg.Bind(wx.EVT_CHECKBOX, self.should_use_viewcond_adjust_handler, id = chk.GetId())
			dlg.sizer3.Add(chk, flag = wx.TOP | wx.ALIGN_LEFT, border = 12)
			dlg.sizer0.SetSizeHints(dlg)
			dlg.sizer0.Layout()
			dlg.ShowModalThenDestroy()

	def should_use_viewcond_adjust_handler(self, event):
		setcfg("trc.should_use_viewcond_adjust.show_msg", int(not event.GetEventObject().GetValue()))

	def check_create_dir(self, path, parent = None):
		if parent is None:
			parent = self
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

	def check_cal_isfile(self, cal = None, missing_msg = None, notfile_msg = None, parent = None, silent = False):
		if not silent:
			if not missing_msg:
				missing_msg = lang.getstr("error.calibration.file_missing", cal)
			if not notfile_msg:
				notfile_msg = lang.getstr("error.calibration.file_notfile", cal)
		return self.check_file_isfile(cal, missing_msg, notfile_msg, parent, silent)

	def check_profile_isfile(self, profile_path = None, missing_msg = None, notfile_msg = None, parent = None, silent = False):
		if not silent:
			if not missing_msg:
				missing_msg = lang.getstr("error.profile.file_missing", profile_path)
			if not notfile_msg:
				notfile_msg = lang.getstr("error.profile.file_notfile", profile_path)
		return self.check_file_isfile(profile_path, missing_msg, notfile_msg, parent, silent)

	def check_file_isfile(self, filename, missing_msg = None, notfile_msg = None, parent = None, silent = False):
		if parent is None:
			parent = self
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
		args += [("-p" if self.argyll_version <= [1, 0, 4] else "-P") + self.measureframe.get_dimensions()]
		if bool(int(getcfg("measure.darken_background"))):
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
				cal = getcfg("calibration.file")
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
							InfoDialog(self, pos = (-1, 100), msg = lang.getstr("error.copy_failed", (cal, calcopy)) + "\n\n" + unicode(str(exception), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
							return None, None
						if not self.check_cal_isfile(calcopy):
							return None, None
						cal = calcopy
				else:
					if not self.extract_fix_copy_cal(cal, calcopy):
						return None, None
				#
				if self.profile_update_cb.GetValue():
					profile_path = os.path.splitext(getcfg("calibration.file"))[0] + profile_ext
					if not self.check_profile_isfile(profile_path):
						return None, None
					profilecopy = os.path.join(inoutfile + profile_ext)
					if not os.path.exists(profilecopy):
						try:
							shutil.copyfile(profile_path, profilecopy) # copy profile to profile dir
						except Exception, exception:
							InfoDialog(self, pos = (-1, 100), msg = lang.getstr("error.copy_failed", (profile_path, profilecopy)) + "\n\n" + unicode(str(exception), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
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
			if hasattr(self, "black_point_rate_ctrl") and defaults["calibration.black_point_rate.enabled"] and float(self.get_black_point_correction()) < 1:
				black_point_rate = self.get_black_point_rate()
				if black_point_rate:
					args += ["-A" + black_point_rate]
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
			args += ['-f%s' % self.tcframe.tc_get_total_patches()]
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
		if debug: safe_print("Setting targen options:", self.options_targen)
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
						InfoDialog(self, pos = (-1, 100), msg = lang.getstr("error.testchart.read", self.get_testchart()), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
						return None, None
					ti3 = StringIO(profile.tags.get("CIED", ""))
				elif ext.lower() == ".ti1":
					shutil.copyfile(filename + ext, inoutfile + ".ti1")
				else: # ti3
					try:
						ti3 = open(filename + ext, "rU")
					except Exception, exception:
						InfoDialog(self, pos = (-1, 100), msg = lang.getstr("error.testchart.read", self.get_testchart()), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
						return None, None
				if ext.lower() != ".ti1":
					ti3_lines = [line.strip() for line in ti3]
					ti3.close()
					if not "CTI3" in ti3_lines:
						InfoDialog(self, pos = (-1, 100), msg = lang.getstr("error.testchart.invalid", self.get_testchart()), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
						return None, None
					ti1 = open(inoutfile + ".ti1", "w")
					ti1.write(ti3_to_ti1(ti3_lines))
					ti1.close()
			except Exception, exception:
				InfoDialog(self, pos = (-1, 100), msg = lang.getstr("error.testchart.creation_failed", inoutfile + ".ti1") + "\n\n" + unicode(str(exception), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
				return None, None
		if apply_calibration:
			if apply_calibration == True:
				cal = os.path.join(getcfg("profile.save_path"), self.get_profile_name(), self.get_profile_name()) + ".cal" # always a .cal file in that case
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
						InfoDialog(self, pos = (-1, 100), msg = lang.getstr("error.copy_failed", (cal, calcopy)) + "\n\n" + unicode(str(exception), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
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
					InfoDialog(self, pos = (-1, 100), msg = lang.getstr("error.cal_extraction", (cal)), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					return None, None
				try:
					tmpcal = open(calcopy, "w")
					tmpcal.write(extract_cal_from_ti3(ti3_lines))
					tmpcal.close()
				except Exception, exception:
					InfoDialog(self, pos = (-1, 100), msg = lang.getstr("error.cal_extraction", (cal)) + "\n\n" + unicode(str(exception), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
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
		args += [("-p" if self.argyll_version <= [1, 0, 4] else "-P") + self.measureframe.get_dimensions()]
		if bool(int(getcfg("measure.darken_background"))):
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
			InfoDialog(self, pos = (-1, 100), msg = lang.getstr("error.measurement.file_missing", inoutfile + ".ti3"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
			return None, None
		if not os.path.isfile(inoutfile + ".ti3"):
			InfoDialog(self, pos = (-1, 100), msg = lang.getstr("error.measurement.file_notfile", inoutfile + ".ti3"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
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
			if len(self.displays):
				args += ["-M"]
				if display_name is None:
					if self.IsShownOnScreen():
						try:
							display_no = self.displays.index(self.display_ctrl.GetStringSelection())
						except ValueError:
							display_no = 0
					else:
						display_no = wx.Display.GetFromWindow(self.measureframe)
					if display_no < 0: # window outside visible area
						display_no = 0
					args += [self.displays[display_no].split(" @")[0]]
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
					profile_save_path = os.path.join(getcfg("profile.save_path"), self.get_profile_name())
					profile_path = os.path.join(profile_save_path, self.get_profile_name() + profile_ext)
				if not self.check_profile_isfile(profile_path):
					return None, None
				try:
					profile = ICCP.ICCProfile(profile_path)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					InfoDialog(self, msg = lang.getstr("profile.invalid"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					return None, None
				if profile.profileClass != "mntr" or profile.colorSpace != "RGB":
					InfoDialog(self, msg = lang.getstr("profile.unsupported", (profile.profileClass, profile.colorSpace)), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					return None, None
				if install:
					if getcfg("profile.install_scope") != "u" and \
						(((sys.platform == "darwin" or (sys.platform != "win32" and self.argyll_version >= [1, 1, 0])) and (os.geteuid() == 0 or get_sudo())) or 
						(sys.platform == "win32" and sys.getwindowsversion() >= (6, )) or test):
							# -S option is broken on Linux with current Argyll releases
							args += ["-S" + getcfg("profile.install_scope")]
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
		dst_file = os.path.join(getcfg("profile.save_path"), self.get_profile_name(), filename)
		if os.path.exists(dst_file):
			dlg = ConfirmDialog(self, msg = lang.getstr("warning.already_exists", filename), ok = lang.getstr("ok"), cancel = lang.getstr("cancel"), bitmap = getbitmap("theme/icons/32x32/dialog-warning"))
			result = dlg.ShowModal()
			dlg.Destroy()
			if result != wx.ID_OK: return False
		return True

	def wrapup(self, copy = True, remove = True, dst_path = None, ext_filter = None):
		if debug: safe_print("wrapup(copy = %s, remove = %s)" % (copy, remove))
		if not hasattr(self, "tempdir") or not os.path.exists(self.tempdir) or not os.path.isdir(self.tempdir):
			return # nothing to do
		if copy:
			if not ext_filter:
				ext_filter = [".app", ".cal", ".cmd", ".command", ".icc", ".icm", ".sh", ".ti1", ".ti3"]
			if dst_path is None:
				dst_path = os.path.join(getcfg("profile.save_path"), self.get_profile_name(), self.get_profile_name() + ".ext")
			try:
				dir_created = self.check_create_dir(os.path.dirname(dst_path))
			except Exception, exception:
				InfoDialog(self, pos = (-1, 100), msg = lang.getstr("error.dir_creation", (os.path.dirname(dst_path))) + "\n\n" + unicode(str(exception), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
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
			dlg = ConfirmDialog(self, pos = (-1, 100), msg = lang.getstr("instrument.place_on_screen"), ok = lang.getstr("ok"), cancel = lang.getstr("cancel"), bitmap = getbitmap("theme/icons/32x32/dialog-information"))
			result = dlg.ShowModal()
			dlg.Destroy()
			if result != wx.ID_OK: return False
		cmd, args = self.prepare_dispcal()
		result = self.exec_cmd(cmd, args, capture_output = capture_output)
		self.wrapup(result, remove or not result)
		if result:
			cal = os.path.join(getcfg("profile.save_path"), self.get_profile_name(), self.get_profile_name() + ".cal")
			setcfg("last_cal_path", cal)
			self.previous_cal = getcfg("calibration.file")
			if self.profile_update_cb.GetValue():
				profile_path = os.path.join(getcfg("profile.save_path"), self.get_profile_name(), self.get_profile_name() + profile_ext)
				result = self.check_profile_isfile(profile_path, lang.getstr("error.profile.file_not_created"))
				if result:
					setcfg("calibration.file", profile_path)
					setcfg("last_cal_or_icc_path", profile_path)
					setcfg("last_icc_path", profile_path)
					self.update_controls(update_profile_name = False)
			else:
				result = self.check_cal_isfile(cal, lang.getstr("error.calibration.file_not_created"))
				if result:
					if self.install_cal:
						setcfg("calibration.file", cal)
						self.update_controls(update_profile_name = False)
					setcfg("last_cal_or_icc_path", cal)
					self.load_cal(cal = cal, silent = True)
		return result

	def measure(self, apply_calibration = True):
		cmd, args = self.prepare_dispread(apply_calibration)
		result = self.exec_cmd(cmd, args)
		self.wrapup(result, not result)
		return result

	def profile(self, apply_calibration = True, dst_path = None, skip_cmds = False, display_name = None):
		safe_print(lang.getstr("create_profile"))
		if dst_path is None:
			dst_path = os.path.join(getcfg("profile.save_path"), self.get_profile_name(), self.get_profile_name() + profile_ext)
		cmd, args = self.prepare_colprof(os.path.basename(os.path.splitext(dst_path)[0]), display_name)
		result = self.exec_cmd(cmd, args, capture_output = "-as" in self.options_colprof and self.argyll_version <= [1, 0, 4], low_contrast = False, skip_cmds = skip_cmds)
		self.wrapup(result, dst_path = dst_path)
		if "-as" in self.options_colprof and self.argyll_version <= [1, 0, 4]: safe_print(lang.getstr("success") if result else lang.getstr("aborted"))
		if result:
			try:
				profile = ICCP.ICCProfile(dst_path)
			except (IOError, ICCP.ICCProfileInvalidError), exception:
				InfoDialog(self, msg = lang.getstr("profile.invalid"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
				return False
			if profile.profileClass == "mntr" and profile.colorSpace == "RGB":
				setcfg("last_cal_or_icc_path", dst_path)
				setcfg("last_icc_path", dst_path)
		return result

	def install_cal_handler(self, event = None, cal = None):
		if not self.check_set_argyll_bin():
			return
		if cal is None:
			cal = getcfg("calibration.file")
		if cal and self.check_file_isfile(cal):
			filename, ext = os.path.splitext(cal)
			if ext.lower() in (".icc", ".icm"):
				try:
					profile = ICCP.ICCProfile(cal)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					InfoDialog(self, msg = lang.getstr("profile.invalid"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					return
				if profile.profileClass != "mntr" or profile.colorSpace != "RGB":
					InfoDialog(self, msg = lang.getstr("profile.unsupported", (profile.profileClass, profile.colorSpace)), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					return
				profile_path = cal
			else:
				profile_path = filename + profile_ext
			if os.path.exists(profile_path):
				self.previous_cal = False
				self.profile_finish(True, profile_path = profile_path, success_msg = lang.getstr("dialog.install_profile", (os.path.basename(profile_path), self.display_ctrl.GetStringSelection())), skip_cmds = True)

	def install_profile_handler(self, event):
		defaultDir, defaultFile = get_verified_path("last_icc_path")
		dlg = wx.FileDialog(self, lang.getstr("install_display_profile"), defaultDir = defaultDir, defaultFile = defaultFile, wildcard = lang.getstr("filetype.icc") + "|*.icc;*.icm", style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		dlg.Center(wx.BOTH)
		result = dlg.ShowModal()
		path = dlg.GetPath()
		dlg.Destroy()
		if result == wx.ID_OK:
			if not os.path.exists(path):
				InfoDialog(self, msg = lang.getstr("file.missing", path), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
				return
			setcfg("last_icc_path", path)
			setcfg("last_cal_or_icc_path", path)
			self.install_cal_handler(cal = path)

	def load_cal_cal_handler(self, event):
		defaultDir, defaultFile = get_verified_path("last_cal_path")
		dlg = wx.FileDialog(self, lang.getstr("calibration.load_from_cal"), defaultDir = defaultDir, defaultFile = defaultFile, wildcard = lang.getstr("filetype.cal") + "|*.cal", style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		dlg.Center(wx.BOTH)
		result = dlg.ShowModal()
		path = dlg.GetPath()
		dlg.Destroy()
		if result == wx.ID_OK:
			if not os.path.exists(path):
				InfoDialog(self, msg = lang.getstr("file.missing", path), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
				return
			setcfg("last_cal_path", path)
			setcfg("last_cal_or_icc_path", path)
			self.install_profile(capture_output = True, cal = path, install = False, skip_cmds = True)

	def load_profile_cal_handler(self, event):
		if not self.check_set_argyll_bin():
			return
		defaultDir, defaultFile = get_verified_path("last_cal_or_icc_path")
		dlg = wx.FileDialog(self, lang.getstr("calibration.load_from_cal_or_profile"), defaultDir = defaultDir, defaultFile = defaultFile, wildcard = lang.getstr("filetype.cal_icc") + "|*.cal;*.icc;*.icm", style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		dlg.Center(wx.BOTH)
		result = dlg.ShowModal()
		path = dlg.GetPath()
		dlg.Destroy()
		if result == wx.ID_OK:
			if not os.path.exists(path):
				InfoDialog(self, msg = lang.getstr("file.missing", path), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
				return
			setcfg("last_cal_or_icc_path", path)
			if os.path.splitext(path)[1].lower() in (".icc", ".icm"):
				try:
					profile = ICCP.ICCProfile(path)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					InfoDialog(self, msg = lang.getstr("profile.invalid"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					return
				if "vcgt" in profile.tags:
					setcfg("last_icc_path", path)
					if hasattr(self, "lut_viewer") and self.lut_viewer and self.lut_viewer.IsShownOnScreen():
						self.show_lut_handler(profile = profile)
					self.install_profile(capture_output = True, profile_path = path, install = False, skip_cmds = True)
				else:
					InfoDialog(self, msg = lang.getstr("profile.no_vcgt"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
			else:
				setcfg("last_cal_path", path)
				if hasattr(self, "lut_viewer") and self.lut_viewer and self.lut_viewer.IsShownOnScreen():
					self.show_lut_handler(profile = cal_to_fake_profile(path))
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
		if hasattr(self, "lut_viewer") and self.lut_viewer and self.lut_viewer.IsShownOnScreen():
			if cal == False: # linear
				self.lut_viewer.profile = None
				self.lut_viewer.DrawLUT()
			else:
				if cal == True: # display profile
					try:
						profile = ICCP.get_display_profile(self.display_ctrl.GetSelection())
					except Exception, exception:
						safe_print("ICCP.get_display_profile(%s):" % self.display_ctrl.GetSelection(), exception)
						profile = None
				elif cal.lower().endswith(".icc") or cal.lower().endswith(".icm"):
					profile = ICCP.ICCProfile(cal)
				else:
					profile = cal_to_fake_profile(cal)
				self.show_lut_handler(profile = profile)
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
					if verbose >= 1: safe_print(lang.getstr("success"))
					InfoDialog(self, msg = lang.getstr("profile.install.success"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-information"))
				# try to create autostart script to load LUT curves on login
				n = self.get_display_number()
				loader_args = "-d%s -c -L" % n
				if sys.platform == "win32":
					name = "%s Calibration Loader (Display %s)" % (appname, n)
					if autostart_home:
						loader_v01b = os.path.join(autostart_home, ("dispwin-d%s-c-L" % n) + ".lnk")
						if os.path.exists(loader_v01b):
							try:
								# delete v0.1b loader
								os.remove(loader_v01b)
							except Exception, exception:
								safe_print("Warning - could not remove old v0.1b calibration loader '%s': %s" % (loader_v01b, str(exception)))
						loader_v02b = os.path.join(autostart_home, name + ".lnk")
						if os.path.exists(loader_v02b):
							try:
								# delete v02.b/v0.2.1b loader
								os.remove(loader_v02b)
							except Exception, exception:
								safe_print("Warning - could not remove old v0.2b calibration loader '%s': %s" % (loader_v02b, str(exception)))
					try:
						scut = pythoncom.CoCreateInstance(
							shell.CLSID_ShellLink, None,
							pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink
						)
						scut.SetPath(cmd)
						if isexe:
							scut.SetIconLocation(exe, 0)
						else:
							scut.SetIconLocation(get_data_path(os.path.join("theme", "icons", appname + ".ico")), 0)
						scut.SetArguments(loader_args)
						scut.SetShowCmd(win32con.SW_SHOWMINNOACTIVE)
						if "-Sl" in args or sys.getwindowsversion() < (6, ): # Vista and later if using system scope, Windows 2k/XP
							if autostart:
								try:
									scut.QueryInterface(pythoncom.IID_IPersistFile).Save(os.path.join(autostart, name + ".lnk"), 0)
								except Exception, exception:
									pass # try user scope
								else:
									return result
							else:
								if not silent: InfoDialog(self, msg = lang.getstr("error.autostart_system"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-warning"))
						if autostart_home:
							scut.QueryInterface(pythoncom.IID_IPersistFile).Save(os.path.join(autostart_home, name + ".lnk"), 0)
						else:
							if not silent: InfoDialog(self, msg = lang.getstr("error.autostart_user"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-warning"))
					except Exception, exception:
						if not silent: InfoDialog(self, msg = lang.getstr("error.autostart_creation", "Windows") + "\n\n" + unicode(str(exception), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-warning"))
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
						desktopfile.write((u'Comment=%s\n' % lang.getstr("calibrationloader.description", n)).encode("UTF-8"))
						desktopfile.write((u'Exec=%s\n' % exec_).encode("UTF-8"))
						desktopfile.close()
					except Exception, exception:
						if not silent: InfoDialog(self, msg = lang.getstr("error.autostart_creation", desktopfile_path) + "\n\n" + unicode(str(exception), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-warning"))
					else:
						if "-Sl" in args:
							# copy system-wide loader
							system_desktopfile_path = os.path.join(autostart, name + ".desktop")
							if not silent and \
								(not self.exec_cmd("mkdir", ["-p", autostart], capture_output = True, low_contrast = False, skip_cmds = True, silent = True, asroot = True) or \
								not self.exec_cmd("mv", ["-f", desktopfile_path, autostart], capture_output = True, low_contrast = False, skip_cmds = True, silent = True, asroot = True)):
								InfoDialog(self, msg = lang.getstr("error.autostart_creation", system_desktopfile_path), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-warning"))
			else:
				if not silent:
					if cal == False:
						InfoDialog(self, msg = lang.getstr("calibration.reset_success"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-information"))
					else:
						InfoDialog(self, msg = lang.getstr("calibration.load_success"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-information"))
		elif not silent:
			if install:
				if verbose >= 1: safe_print(lang.getstr("failure"))
				if result is not None:
					InfoDialog(self, msg = lang.getstr("profile.install.error"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
			else:
				if cal == False:
					InfoDialog(self, msg = lang.getstr("calibration.reset_error"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
				else:
					InfoDialog(self, msg = lang.getstr("calibration.load_error"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
		self.pwd = None # do not keep password in memory longer than necessary
		return result

	def verify_calibration_handler(self, event):
		if self.check_set_argyll_bin():
			self.setup_measurement(self.verify_calibration)

	def verify_calibration(self):
		safe_print("-" * 80)
		safe_print(lang.getstr("calibration.verify"))
		capture_output = False
		if capture_output:
			dlg = ConfirmDialog(self, pos = (-1, 100), msg = lang.getstr("instrument.place_on_screen"), ok = lang.getstr("ok"), cancel = lang.getstr("cancel"), bitmap = getbitmap("theme/icons/32x32/dialog-information"))
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
			cal = getcfg("calibration.file")
		if cal:
			if hasattr(self, "lut_viewer") and self.lut_viewer and self.lut_viewer.IsShownOnScreen():
				self.show_lut_handler(profile = ICCP.ICCProfile(cal) if cal.lower().endswith(".icc") or cal.lower().endswith(".icm") else cal_to_fake_profile(cal))
			if self.check_set_argyll_bin():
				if verbose >= 1 and silent: safe_print(lang.getstr("calibration.loading"))
				if self.install_profile(capture_output = True, cal = cal, install = False, skip_cmds = True, silent = silent):
					if verbose >= 1 and silent: safe_print(lang.getstr("success"))
					return True
				if verbose >= 1 and silent: safe_print(lang.getstr("failure"))
		return False

	def reset_cal(self, event = None):
		if hasattr(self, "lut_viewer") and self.lut_viewer and self.lut_viewer.IsShownOnScreen():
			self.lut_viewer.profile = None
			self.lut_viewer.DrawLUT()
		if self.check_set_argyll_bin():
			if verbose >= 1 and event is None: safe_print(lang.getstr("calibration.resetting"))
			if self.install_profile(capture_output = True, cal = False, install = False, skip_cmds = True, silent = event is None or (hasattr(self, "lut_viewer") and self.lut_viewer and self.lut_viewer.IsShownOnScreen())):
				if verbose >= 1 and event is None: safe_print(lang.getstr("success"))
				return True
			if verbose >= 1 and event is None: safe_print(lang.getstr("failure"))
		return False

	def load_display_profile_cal(self, event = None):
		if hasattr(self, "lut_viewer") and self.lut_viewer and self.lut_viewer.IsShownOnScreen():
			try:
				profile = ICCP.get_display_profile(self.display_ctrl.GetSelection())
			except Exception, exception:
				safe_print("ICCP.get_display_profile(%s):" % self.display_ctrl.GetSelection(), exception)
				profile = None
			self.show_lut_handler(profile = profile)
		if self.check_set_argyll_bin():
			if verbose >= 1 and event is None: safe_print(lang.getstr("calibration.loading_from_display_profile"))
			if self.install_profile(capture_output = True, cal = True, install = False, skip_cmds = True, silent = event is None or (hasattr(self, "lut_viewer") and self.lut_viewer and self.lut_viewer.IsShownOnScreen())):
				if verbose >= 1 and event is None: safe_print(lang.getstr("success"))
				return True
			if verbose >= 1 and event is None: safe_print(lang.getstr("failure"))
		return False

	def exec_cmd(self, cmd, args = [], capture_output = False, display_output = False, low_contrast = True, skip_cmds = False, silent = False, parent = None, asroot = False, log_output = True):
		if parent is None:
			parent = self
		# if capture_output:
			# fn = self.infoframe.Log
		# else:
		fn = None
		self.retcode = retcode = -1
		self.output = []
		self.errors = []
		if None in [cmd, args]:
			if verbose >= 1 and not capture_output: safe_print(lang.getstr("aborted"), fn = fn)
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
					# context.write(u"set +v\n")
					context.write((u'PATH=%s:$PATH\n' % os.path.dirname(cmd)).encode(enc, "asciize"))
					if sys.platform == "darwin" and mac_create_app:
						cmdfiles.write(u'pushd "`dirname \\"$0\\"`/../../.."\n')
					else:
						cmdfiles.write(u'pushd "`dirname \\"$0\\"`"\n')
					if cmdname in (self.get_argyll_utilname("dispcal"), self.get_argyll_utilname("dispread")) and sys.platform != "darwin":
						cmdfiles.write(u'echo -e "\\033[40;2;37m" && clear\n')
					# if last and sys.platform != "darwin":
						# context.write(u'gnome_screensaver_running=$(ps -A -f | grep gnome-screensaver | grep -v grep)\n')
						# context.write(u'if [ "$gnome_screensaver_running" != "" ]; then gnome-screensaver-command --exit; fi\n')
					os.chmod(cmdfilename, 0755)
					os.chmod(allfilename, 0755)
				cmdfiles.write(u" ".join(quote_args(cmdline)).replace(cmd, cmdname).encode(enc, "asciize") + "\n")
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
						cmdfiles.write(u'echo -e "\\033[0m" && clear\n')
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
			if verbose >= 2:
				safe_print("Running calibration and profiling in succession, checking instrument for unattended capability...")
				if instrument_features:
					safe_print("Instrument needs sensor calibration before use:", "Yes" if instrument_features.get("sensor_cal") else "No")
					if instrument_features.get("sensor_cal"):
						safe_print("Instrument can be forced to skip sensor calibration:", "Yes" if instrument_features.get("skip_sensor_cal") and self.argyll_version >= [1, 1, 0] else "No")
				else:
					safe_print("Warning - instrument not recognized:", self.comport_ctrl.GetStringSelection())
			# -N switch not working as expected in Argyll 1.0.3
			if instrument_features and (not instrument_features.get("sensor_cal") or (instrument_features.get("skip_sensor_cal") and self.argyll_version >= [1, 1, 0])):
				if verbose >= 2:
					safe_print("Instrument can be used for unattended calibration and profiling")
				try:
					if verbose >= 2:
						safe_print("Sending 'SPACE' key to automatically start measurements in 10 seconds...")
					if sys.platform == "darwin":
						start_new_thread(mac_app_sendkeys, (10, "Terminal", " "))
					elif sys.platform == "win32":
						start_new_thread(wsh_sendkeys, (10, appname + exe_ext, " "))
					else:
						if which("xte"):
							start_new_thread(xte_sendkeys, (10, None, "space"))
						elif verbose >= 2:
							safe_print("Warning - 'xte' commandline tool not found, unattended measurements not possible")
				except Exception, exception:
					safe_print("Warning - unattended measurements not possible (start_new_thread failed with %s)" % str(exception))
			elif verbose >= 2:
				safe_print("Instrument can not be used for unattended calibration and profiling")
		elif cmdname in (self.get_argyll_utilname("dispcal"), self.get_argyll_utilname("dispread")) and \
			sys.platform == "darwin" and args and not self.IsShownOnScreen():
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
				self.retcode = retcode = self.subprocess.wait()
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
							if (retcode != 0 or cmdname == self.get_argyll_utilname("dispwin")):
								InfoDialog(parent, pos = (-1, 100), msg = unicode("".join(errors2).strip(), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-warning"))
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
			handle_error("Error: " + (traceback.format_exc() if debug else str(exception)), parent = self)
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
			if verbose >= 1 and not capture_output: safe_print(lang.getstr("aborted"), fn = fn)
			return False
		# else:
			# if verbose >= 1 and not capture_output: safe_print("", fn = fn)
		return True

	def report_calibrated_handler(self, event):
		self.setup_measurement(self.report)

	def report_uncalibrated_handler(self, event):
		self.setup_measurement(self.report, False)

	def report(self, report_calibrated = True):
		if self.check_set_argyll_bin():
			safe_print("-" * 80)
			if report_calibrated:
				safe_print(lang.getstr("report.calibrated"))
			else:
				safe_print(lang.getstr("report.uncalibrated"))
			capture_output = False
			if capture_output:
				dlg = ConfirmDialog(self, pos = (-1, 100), msg = lang.getstr("instrument.place_on_screen"), ok = lang.getstr("ok"), cancel = lang.getstr("cancel"), bitmap = getbitmap("theme/icons/32x32/dialog-information"))
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
		safe_print(lang.getstr("button.calibrate"))
		update = self.profile_update_cb.GetValue()
		self.install_cal = True
		if self.calibrate(remove = True):
			InfoDialog(self, pos = (-1, 100), msg = lang.getstr("calibration.complete"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-information"))
			if update:
				self.profile_finish(True, success_msg = lang.getstr("calibration_profiling.complete"))
		else:
			InfoDialog(self, pos = (-1, 100), msg = lang.getstr("calibration.incomplete"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
		self.ShowAll()

	def setup_measurement(self, pending_function, *pending_function_args, **pending_function_kwargs):
		writecfg()
		self.wrapup(False)
		# if sys.platform == "win32":
			# sp.call("cls", shell = True)
		# else:
			# sp.call('clear', shell = True)
		self.HideAll()
		self.measureframe.Show()
		self.set_pending_function(pending_function, *pending_function_args, **pending_function_kwargs)

	def set_pending_function(self, pending_function, *pending_function_args, **pending_function_kwargs):
		self.pending_function = pending_function
		self.pending_function_args = pending_function_args
		self.pending_function_kwargs = pending_function_kwargs

	def call_pending_function(self): # needed for proper display updates under GNOME
		writecfg()
		self.measureframe.Hide()
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
		safe_print(lang.getstr("button.calibrate_and_profile").replace("&&", "&"))
		self.install_cal = True
		# -N switch not working as expected in Argyll 1.0.3
		if self.get_instrument_features().get("skip_sensor_cal") and self.argyll_version >= [1, 1, 0]:
			self.options_dispread = ["-N"]
		self.dispread_after_dispcal = True
		start_timers = True
		if self.calibrate():
			if self.measure(apply_calibration = True):
				start_timers = False
				wx.CallAfter(self.start_profile_worker, lang.getstr("calibration_profiling.complete"))
			else:
				InfoDialog(self, pos = (-1, 100), msg = lang.getstr("profiling.incomplete"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
		else:
			InfoDialog(self, pos = (-1, 100), msg = lang.getstr("calibration.incomplete"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
		self.ShowAll(start_timers = start_timers)

	def start_profile_worker(self, success_msg, apply_calibration = True):
		self.start_worker(self.profile_finish, self.profile, ckwargs = {"success_msg": success_msg, "failure_msg": lang.getstr("profiling.incomplete")}, wkwargs = {"apply_calibration": apply_calibration }, progress_title = lang.getstr("create_profile"))

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
			cal = getcfg("calibration.file")
			apply_calibration = False
			if cal:
				filename, ext = os.path.splitext(cal)
				if ext.lower() in (".icc", ".icm"):
					self.options_dispcal = []
					try:
						profile = ICCP.ICCProfile(cal)
					except (IOError, ICCP.ICCProfileInvalidError), exception:
						InfoDialog(self, msg = lang.getstr("profile.invalid"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
						self.update_profile_name_timer.Start(1000)
						return
					else:
						if "cprt" in profile.tags: # get dispcal options if present
							self.options_dispcal = ["-" + arg for arg in self.get_options_from_cprt(profile.tags.cprt)[0]]
				if os.path.exists(filename + ".cal") and can_update_cal(filename + ".cal"):
					apply_calibration = filename + ".cal"
			dlg = ConfirmDialog(self, msg = lang.getstr("dialog.current_cal_warning"), ok = lang.getstr("continue"), cancel = lang.getstr("cancel"), bitmap = getbitmap("theme/icons/32x32/dialog-warning"))
			result = dlg.ShowModal()
			dlg.Destroy()
			if result != wx.ID_OK:
				self.update_profile_name_timer.Start(1000)
				return
			self.setup_measurement(self.just_profile, apply_calibration)
		else:
			self.update_profile_name_timer.Start(1000)

	def just_profile(self, apply_calibration):
		safe_print("-" * 80)
		safe_print(lang.getstr("button.profile"))
		self.options_dispread = []
		self.dispread_after_dispcal = False
		start_timers = True
		self.previous_cal = False
		if self.measure(apply_calibration):
			start_timers = False
			wx.CallAfter(self.start_profile_worker, lang.getstr("profiling.complete"), apply_calibration)
		else:
			InfoDialog(self, pos = (-1, 100), msg = lang.getstr("profiling.incomplete"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
		self.ShowAll(start_timers = start_timers)

	def profile_finish(self, result, profile_path = None, success_msg = "", failure_msg = "", preview = True, skip_cmds = False):
		if result:
			if not hasattr(self, "previous_cal") or self.previous_cal == False:
				self.previous_cal = getcfg("calibration.file")
			if profile_path:
				profile_save_path = os.path.splitext(profile_path)[0]
			else:
				profile_save_path = os.path.join(getcfg("profile.save_path"), self.get_profile_name(), self.get_profile_name())
				profile_path = profile_save_path + profile_ext
			self.cal = profile_path
			filename, ext = os.path.splitext(profile_path)
			if ext.lower() in (".icc", ".icm"):
				has_cal = False
				try:
					profile = ICCP.ICCProfile(profile_path)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					InfoDialog(self, msg = lang.getstr("profile.invalid"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					self.start_timers(True)
					self.previous_cal = False
					return
				else:
					has_cal = "vcgt" in profile.tags
					if profile.profileClass != "mntr" or profile.colorSpace != "RGB":
						InfoDialog(self, msg = success_msg, ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-information"))
						self.start_timers(True)
						self.previous_cal = False
						return
					if getcfg("calibration.file") != profile_path and "cprt" in profile.tags:
						options_dispcal, options_colprof = self.get_options_from_cprt(profile.tags.cprt)
						if options_dispcal or options_colprof:
							cal = profile_save_path + ".cal"
							sel = self.calibration_file_ctrl.GetSelection()
							if options_dispcal and self.recent_cals[sel] == cal:
								self.recent_cals.remove(cal)
								self.calibration_file_ctrl.Delete(sel)
							if getcfg("settings.changed"):
								self.settings_discard_changes()
							if options_dispcal and options_colprof:
								self.load_cal_handler(None, path = profile_path, update_profile_name = False, silent = True)
							else:
								setcfg("calibration.file", profile_path)
								self.update_controls(update_profile_name = False)
			else: # .cal file
				has_cal = True
			dlg = ConfirmDialog(self, msg = success_msg, ok = lang.getstr("profile.install"), cancel = lang.getstr("profile.do_not_install"), bitmap = getbitmap("theme/icons/32x32/dialog-information"))
			if preview and has_cal: # show calibration preview checkbox
				self.preview = wx.CheckBox(dlg, -1, lang.getstr("calibration.preview"))
				self.preview.SetValue(True)
				dlg.Bind(wx.EVT_CHECKBOX, self.preview_handler, id = self.preview.GetId())
				dlg.sizer3.Add(self.preview, flag = wx.TOP | wx.ALIGN_LEFT, border = 12)
				if LUTFrame:
					self.show_lut = wx.CheckBox(dlg, -1, lang.getstr("calibration.show_lut"))
					dlg.Bind(wx.EVT_CHECKBOX, self.show_lut_handler, id = self.show_lut.GetId())
					dlg.sizer3.Add(self.show_lut, flag = wx.TOP | wx.ALIGN_LEFT, border = 4)
					if hasattr(self, "lut_viewer") and self.lut_viewer and self.lut_viewer.IsShownOnScreen():
						self.show_lut.SetValue(True)
					self.init_lut_viewer(profile = profile)
				if ((sys.platform == "darwin" or (sys.platform != "win32" and self.argyll_version >= [1, 1, 0])) and (os.geteuid() == 0 or get_sudo())) or \
					(sys.platform == "win32" and sys.getwindowsversion() >= (6, )) or test: # Linux, OSX or Vista and later
					self.install_profile_user = wx.RadioButton(dlg, -1, lang.getstr("profile.install_user"), style = wx.RB_GROUP)
					self.install_profile_user.SetValue(getcfg("profile.install_scope") == "u")
					dlg.Bind(wx.EVT_RADIOBUTTON, self.install_profile_scope_handler, id = self.install_profile_user.GetId())
					dlg.sizer3.Add(self.install_profile_user, flag = wx.TOP | wx.ALIGN_LEFT, border = 4)
					self.install_profile_systemwide = wx.RadioButton(dlg, -1, lang.getstr("profile.install_local_system"))
					self.install_profile_systemwide.SetValue(getcfg("profile.install_scope") == "l")
					dlg.Bind(wx.EVT_RADIOBUTTON, self.install_profile_scope_handler, id = self.install_profile_systemwide.GetId())
					dlg.sizer3.Add(self.install_profile_systemwide, flag = wx.TOP | wx.ALIGN_LEFT, border = 4)
					if sys.platform == "darwin" and os.path.isdir("/Network/Library/ColorSync/Profiles"):
						self.install_profile_network = wx.RadioButton(dlg, -1, lang.getstr("profile.install_network"))
						self.install_profile_network.SetValue(getcfg("profile.install_scope") == "n")
						dlg.Bind(wx.EVT_RADIOBUTTON, self.install_profile_scope_handler, id = self.install_profile_network.GetId())
						dlg.sizer3.Add(self.install_profile_network, flag = wx.TOP | wx.ALIGN_LEFT, border = 4)
				dlg.sizer0.SetSizeHints(dlg)
				dlg.sizer0.Layout()
				if ext not in (".icc", ".icm") or getcfg("calibration.file") != profile_path: self.preview_handler(preview = True)
			dlg.ok.SetDefault()
			result = dlg.ShowModal()
			dlg.Destroy()
			if result == wx.ID_OK:
				safe_print("-" * 80)
				safe_print(lang.getstr("profile.install"))
				self.install_profile(capture_output = True, profile_path = profile_path, skip_cmds = skip_cmds)
			elif preview:
				if getcfg("calibration.file"):
					self.load_cal(silent = True) # load LUT curves from last used .cal file
				else:
					self.load_display_profile_cal(None) # load LUT curves from current display profile (if any, and if it contains curves)
		else:
			InfoDialog(self, pos = (-1, 100), msg = failure_msg, ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
		self.start_timers(True)
		self.previous_cal = False
		
	def init_lut_viewer(self, event = None, profile = None):
		if LUTFrame:
			if not hasattr(self, "lut_viewer") or not self.lut_viewer:
				self.lut_viewer = LUTFrame(self, -1, lang.getstr("calibration.lut_viewer.title"), (getcfg("position.lut_viewer.x"), getcfg("position.lut_viewer.y")), (getcfg("size.lut_viewer.w"), getcfg("size.lut_viewer.h")))
				self.lut_viewer.xLabel = lang.getstr("in")
				self.lut_viewer.yLabel = lang.getstr("out")
				self.lut_viewer.SetSaneGeometry(getcfg("position.lut_viewer.x"), getcfg("position.lut_viewer.y"), getcfg("size.lut_viewer.w"), getcfg("size.lut_viewer.h"))
				self.lut_viewer.SetIcon(wx.Icon(get_data_path(os.path.join("theme", "icons", "16x16", appname + ".png")), wx.BITMAP_TYPE_PNG))
				self.lut_viewer.Bind(wx.EVT_MOVE, self.lut_viewer_move_handler)
				self.lut_viewer.Bind(wx.EVT_SIZE, self.lut_viewer_size_handler)
				self.lut_viewer.Bind(wx.EVT_CLOSE, self.lut_viewer_close_handler, self.lut_viewer)
			self.show_lut_handler(profile = profile)
	
	def show_lut_handler(self, event = None, profile = None):
		if hasattr(self, "lut_viewer") and self.lut_viewer:
			if not profile:
				path = getcfg("calibration.file")
				if path:
					name, ext = os.path.splitext(path)
					if ext.lower() in (".icc", ".icm"):
						try:
							profile = ICCP.ICCProfile(path)
						except (IOError, ICCP.ICCProfileInvalidError), exception:
							InfoDialog(self, msg = lang.getstr("profile.invalid"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
							return
					else:
						profile = cal_to_fake_profile(path)
				else:
					try:
						profile = ICCP.get_display_profile(self.display_ctrl.GetSelection()) or False
					except Exception, exception:
						safe_print("ICCP.get_display_profile(%s):" % self.display_ctrl.GetSelection(), exception)
			if profile:
				if not self.lut_viewer.profile or not hasattr(self.lut_viewer.profile, "fileName") or not hasattr(profile, "fileName") or self.lut_viewer.profile.fileName != profile.fileName:
					self.lut_viewer.LoadProfile(profile)
			else:
				self.lut_viewer.profile = None
			show = bool((hasattr(self, "show_lut") and self.show_lut and self.show_lut.GetValue()) or ((not hasattr(self, "show_lut") or not self.show_lut) and (self.lut_viewer.IsShownOnScreen() or profile is not None)))
			if show:
				self.lut_viewer.DrawLUT()
			self.lut_viewer.Show(show)

	def lut_viewer_move_handler(self, event = None):
		if self.lut_viewer.IsShownOnScreen() and not self.lut_viewer.IsMaximized() and not self.lut_viewer.IsIconized():
			x, y = self.lut_viewer.GetScreenPosition()
			setcfg("position.lut_viewer.x", x)
			setcfg("position.lut_viewer.y", y)
		if event:
			event.Skip()
	
	def lut_viewer_size_handler(self, event = None):
		if self.lut_viewer.IsShownOnScreen() and not self.lut_viewer.IsMaximized() and not self.lut_viewer.IsIconized():
			w, h = self.lut_viewer.GetSize()
			setcfg("size.lut_viewer.w", w)
			setcfg("size.lut_viewer.h", h)
		if event:
			event.Skip()
	
	def lut_viewer_close_handler(self, event = None):
		self.lut_viewer.Hide()
		if hasattr(self, "show_lut") and self.show_lut:
			self.show_lut.SetValue(self.lut_viewer.IsShownOnScreen())
	
	def install_profile_scope_handler(self, event):
		if self.install_profile_systemwide.GetValue():
			setcfg("profile.install_scope", "l")
		elif sys.platform == "darwin" and os.path.isdir("/Network/Library/ColorSync/Profiles") and self.install_profile_network.GetValue():
			setcfg("profile.install_scope", "n")
		elif self.install_profile_user.GetValue():
			setcfg("profile.install_scope", "u")
		if debug: safe_print("profile.install_scope", getcfg("profile.install_scope"))
	
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
		setcfg("comport.number", self.get_comport_number())
		self.update_measurement_modes()

	def display_ctrl_handler(self, event):
		if debug: safe_print("display_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		display_no = self.display_ctrl.GetSelection()
		setcfg("display.number", display_no + 1)
		if hasattr(self, "display_lut_ctrl") and bool(int(getcfg("display_lut.link"))):
			self.display_lut_ctrl.SetStringSelection(self.displays[display_no])
			setcfg("display_lut.number", display_no + 1)
		if hasattr(self, "lut_viewer") and self.lut_viewer and self.lut_viewer.IsShownOnScreen():
			self.show_lut_handler()

	def display_lut_ctrl_handler(self, event):
		if debug: safe_print("display_lut_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		try:
			i = self.displays.index(self.display_lut_ctrl.GetStringSelection())
		except ValueError:
			i = self.display_ctrl.GetSelection()
		setcfg("display_lut.number", i + 1)

	def display_lut_link_ctrl_handler(self, event, link = None):
		if debug: safe_print("display_lut_link_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		bitmap_link = getbitmap("theme/icons/16x16/stock_lock")
		bitmap_unlink = getbitmap("theme/icons/16x16/stock_lock-open")
		if link is None:
			link = not bool(int(getcfg("display_lut.link")))
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
		setcfg("display_lut.link", int(link))
		setcfg("display_lut.number", lut_no + 1)

	def measurement_mode_ctrl_handler(self, event):
		if debug: safe_print("measurement_mode_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		self.set_default_testchart()
		v = self.get_measurement_mode()
		if v and "p" in v and self.argyll_version < [1, 1, 0]:
			self.measurement_mode_ctrl.SetSelection(self.measurement_modes_ba[self.get_instrument_type()].get(defaults["measurement_mode"], 0))
			v = None
			InfoDialog(self, msg = lang.getstr("projector_mode_unavailable"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-information"))
		cal_changed = v != getcfg("measurement_mode") and getcfg("calibration.file") not in self.presets
		if cal_changed:
			self.cal_changed()
		setcfg("projector_mode", 1 if v and "p" in v else None)
		setcfg("measurement_mode", (v.replace("p", "") if v else None) or None)
		if ((v in ("l", "lp", "p") and float(self.get_black_point_correction()) > 0) or (v in ("c", "cp") and float(self.get_black_point_correction()) == 0)) and getcfg("calibration.black_point_correction_choice.show"):
			if v in ("l", "lp", "p"):
				ok = lang.getstr("calibration.turn_off_black_point_correction")
			else:
				ok = lang.getstr("calibration.turn_on_black_point_correction")
			dlg = ConfirmDialog(self, title = lang.getstr("calibration.black_point_correction_choice_dialogtitle"), msg = lang.getstr("calibration.black_point_correction_choice"), ok = ok, cancel = lang.getstr("calibration.keep_black_point_correction"), bitmap = getbitmap("theme/icons/32x32/dialog-question"))
			chk = wx.CheckBox(dlg, -1, lang.getstr("dialog.do_not_show_again"))
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
				if not cal_changed and bkpt_corr != getcfg("calibration.black_point_correction"):
					self.cal_changed()
				setcfg("calibration.black_point_correction", bkpt_corr)
				self.update_controls(update_profile_name = False)
		self.update_profile_name()
	
	def black_point_correction_choice_dialog_handler(self, event):
		setcfg("calibration.black_point_correction_choice.show", int(not event.GetEventObject().GetValue()))

	def profile_type_ctrl_handler(self, event):
		if debug: safe_print("profile_type_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		lut_profile = self.get_profile_type() in ("l", "x")
		self.gamap_btn.Enable(lut_profile)
		v = self.get_profile_type()
		if v != getcfg("profile.type"):
			self.profile_settings_changed()
		setcfg("profile.type", v)
		self.update_profile_name()
		self.set_default_testchart()
		if lut_profile and int(self.testchart_patches_amount.GetLabel()) < 500:
			dlg = ConfirmDialog(self, msg = lang.getstr("profile.testchart_recommendation"), ok = lang.getstr("OK"), cancel = lang.getstr("cancel"), bitmap = getbitmap("theme/icons/32x32/dialog-question"))
			result = dlg.ShowModal()
			dlg.Destroy()
			if result == wx.ID_OK:
				testchart = "d3-e4-s0-g52-m4-f500-crossover.ti1"
				self.testchart_defaults["c"]["l"] = testchart
				self.testchart_defaults["l"]["l"] = testchart
				self.set_testchart(get_data_path(os.path.join("ti1", testchart)))

	def profile_name_ctrl_handler(self, event):
		if debug: safe_print("profile_name_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		oldval = self.profile_name_textctrl.GetValue()
		if not self.check_profile_name() or len(oldval) > 255:
			wx.Bell()
			x = self.profile_name_textctrl.GetInsertionPoint()
			newval = defaults.get("profile.name", "") if oldval == "" else re.sub("[\\/:*?\"<>|]+", "", oldval)[:255]
			self.profile_name_textctrl.ChangeValue(newval)
			self.profile_name_textctrl.SetInsertionPoint(x - (len(oldval) - len(newval)))
		self.update_profile_name()

	def create_profile_name_btn_handler(self, event):
		self.update_profile_name()

	def profile_save_path_btn_handler(self, event):
		defaultPath = os.path.sep.join(get_verified_path("profile.save_path"))
		dlg = wx.DirDialog(self, lang.getstr("dialog.set_profile_save_path", self.get_profile_name()), defaultPath = defaultPath)
		dlg.Center(wx.BOTH)
		if dlg.ShowModal() == wx.ID_OK:
			setcfg("profile.save_path", dlg.GetPath())
			self.update_profile_name()
		dlg.Destroy()

	def get_display_number(self):
		if self.IsShownOnScreen() or not hasattr(self, "pending_function") or os.getenv("DISPLAY") not in (None, ":0.0"):
			display_no = self.display_ctrl.GetSelection()
		else:
			display_no = wx.Display.GetFromWindow(self.measureframe)
		if display_no < 0: # window outside visible area
			display_no = 0
		display_no = str(display_no + 1)
		if hasattr(self, "display_lut_ctrl"):
			if bool(int(getcfg("display_lut.link"))):
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
		if not hasattr(self, "profile_name_tooltip_window"):
			self.profile_name_tooltip_window = TooltipWindow(self, msg = self.profile_name_info(), title = lang.getstr("profile.name"), bitmap = getbitmap("theme/icons/32x32/dialog-information"))
		else:
			self.profile_name_tooltip_window.Show()
			self.profile_name_tooltip_window.Raise()

	def profile_name_info(self):
		info = [
			"%dn	" + lang.getstr("display"),
			"%dns	" + lang.getstr("display_short"),
			"%in	" + lang.getstr("instrument"),
			"%im	" + lang.getstr("measurement_mode"),
			"%wp	" + lang.getstr("whitepoint"),
			"%cb	" + lang.getstr("calibration.luminance"),
			"%cB	" + lang.getstr("calibration.black_luminance"),
			"%cg	" + lang.getstr("trc"),
			"%ca	" + lang.getstr("calibration.ambient_viewcond_adjust"),
			"%cf	" + lang.getstr("calibration.black_output_offset"),
			"%ck	" + lang.getstr("calibration.black_point_correction"),
			"%cq	" + lang.getstr("calibration.quality"),
			"%pq	" + lang.getstr("profile.quality"),
			"%pt	" + lang.getstr("profile.type")
		]
		if hasattr(self, "black_point_rate_ctrl") and defaults["calibration.black_point_rate.enabled"]:
			info.insert(9, "%cA	" + lang.getstr("calibration.black_point_rate"))
		return lang.getstr("profile.name.placeholders") + "\n\n" + "\n".join(info)

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
			defaultDir, defaultFile = get_verified_path("last_ti3_path")
			dlg = wx.FileDialog(self, lang.getstr("create_profile"), defaultDir = defaultDir, defaultFile = defaultFile, wildcard = lang.getstr("filetype.ti3") + "|*.icc;*.icm;*.ti3", style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
			dlg.Center(wx.BOTH)
			result = dlg.ShowModal()
			if result == wx.ID_OK:
				path = dlg.GetPath()
			dlg.Destroy()
		if path:
			if not os.path.exists(path):
				InfoDialog(self, msg = lang.getstr("file.missing", path), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
				return
			# get filename and extension of source file
			source_filename, source_ext = os.path.splitext(path)
			if source_ext.lower() != ".ti3":
				try:
					profile = ICCP.ICCProfile(path)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					InfoDialog(self, msg = lang.getstr("profile.invalid"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					return
				if profile.tags.get("CIED", "")[0:4] != "CTI3":
					InfoDialog(self, msg = lang.getstr("profile.no_embedded_ti3"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					return
				ti3 = StringIO(profile.tags.CIED)
			else:
				try:
					ti3 = open(path, "rU")
				except Exception, exception:
					InfoDialog(self, msg = lang.getstr("error.file.open", path), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					return
			ti3_lines = [line.strip() for line in ti3]
			ti3.close()
			if not "CAL" in ti3_lines:
				dlg = ConfirmDialog(self, msg = lang.getstr("dialog.ti3_no_cal_info"), ok = lang.getstr("continue"), cancel = lang.getstr("cancel"), bitmap = getbitmap("theme/icons/32x32/dialog-warning"))
				result = dlg.ShowModal()
				dlg.Destroy()
				if result != wx.ID_OK: return
			setcfg("last_ti3_path", path)
			# let the user choose a location for the profile
			dlg = wx.FileDialog(self, lang.getstr("save_as"), os.path.dirname(path), os.path.basename(source_filename) + profile_ext, wildcard = lang.getstr("filetype.icc") + "|*%s" % profile_ext, style = wx.SAVE | wx.FD_OVERWRITE_PROMPT)
			dlg.Center(wx.BOTH)
			result = dlg.ShowModal()
			profile_save_path = self.make_argyll_compatible_path(dlg.GetPath())
			dlg.Destroy()
			if result == wx.ID_OK:
				filename, ext = os.path.splitext(profile_save_path)
				if ext.lower() != profile_ext:
					profile_save_path += profile_ext
					if os.path.exists(profile_save_path):
						dlg = ConfirmDialog(self, msg = lang.getstr("dialog.confirm_overwrite", (profile_save_path)), ok = lang.getstr("overwrite"), cancel = lang.getstr("cancel"), bitmap = getbitmap("theme/icons/32x32/dialog-warning"))
						result = dlg.ShowModal()
						dlg.Destroy()
						if result != wx.ID_OK:
							return
				setcfg("last_icc_path", profile_save_path)
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
				if debug: safe_print("Setting targen options:", self.options_targen)
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
						if debug: safe_print("Setting targen options:", self.options_targen)
				except Exception, exception:
					handle_error("Error - temporary .ti3 file could not be created: " + str(exception), parent = self)
					self.wrapup(False)
					return
				self.previous_cal = False
				# if sys.platform == "win32":
					# sp.call("cls", shell = True)
				# else:
					# sp.call('clear', shell = True)
				safe_print("-" * 80)
				# run colprof
				self.start_worker(self.profile_finish, self.profile, ckwargs = {"profile_path": profile_save_path, "success_msg": lang.getstr("profile.created"), "failure_msg": lang.getstr("error.profile.file_not_created")}, wkwargs = {"apply_calibration": True, "dst_path": profile_save_path, "display_name": display_name}, progress_title = lang.getstr("create_profile"))

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
		self.thread_abort = False
		self.thread = delayedresult.startWorker(self.generic_consumer, producer, [consumer] + list(cargs), ckwargs, wargs, wkwargs)
		return True

	def is_working(self):
		return hasattr(self, "progress_parent") and (self.progress_parent.progress_start_timer.IsRunning() or self.progress_parent.progress_timer.IsRunning())

	def progress_dlg_start(self, progress_title = "", progress_msg = "", parent = None):
		if True: # hasattr(self, "subprocess") and self.subprocess and self.subprocess.poll() is None:
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
		
		# values
		measurement_mode = self.get_measurement_mode()
		whitepoint = self.get_whitepoint()
		whitepoint_locus = self.get_whitepoint_locus()
		luminance = self.get_luminance()
		black_luminance = self.get_black_luminance()
		trc = self.get_trc()
		trc_type = self.get_trc_type()
		ambient = self.get_ambient()
		black_output_offset = self.get_black_output_offset()
		black_point_correction = self.get_black_point_correction()
		black_point_rate = self.get_black_point_rate()
		calibration_quality = self.get_calibration_quality()
		profile_quality = self.get_profile_quality()
		profile_type = self.get_profile_type()
		
		# legacy (pre v0.2.2b) profile name
		legacy_profile_name = ""
		if measurement_mode:
			if "c" in measurement_mode:
				legacy_profile_name += "crt"
			elif "l" in measurement_mode:
				legacy_profile_name += "lcd"
			if "p" in measurement_mode:
				if len(measurement_mode) > 1:
					legacy_profile_name += "-"
				legacy_profile_name += lang.getstr("projector").lower()
		if legacy_profile_name:
			legacy_profile_name += "-"
		if not whitepoint or whitepoint.find(",") < 0:
			legacy_profile_name += whitepoint_locus
			if whitepoint:
				legacy_profile_name += whitepoint
		else:
			legacy_profile_name += "w" + whitepoint
		if luminance:
			legacy_profile_name += "-b" + luminance
		if black_luminance:
			legacy_profile_name += "-B" + black_luminance
		legacy_profile_name += "-" + trc_type + trc
		if ambient:
			legacy_profile_name += "-a" + ambient
		legacy_profile_name += "-f" + black_output_offset
		legacy_profile_name += "-k" + black_point_correction
		if black_point_rate and float(black_point_correction) < 1:
			legacy_profile_name += "-A" + black_point_rate
		legacy_profile_name += "-q" + calibration_quality + profile_quality
		if profile_type == "l":
			profile_type = "lut"
		else:
			profile_type = "matrix"
		legacy_profile_name += "-" + profile_type
		legacy_profile_name += "-" + strftime("%Y%m%d%H%M")
		profile_name = profile_name.replace("%legacy", legacy_profile_name)
		
		# default v0.2.2b profile name
		display = self.display_ctrl.GetStringSelection()
		if display:
			display = display.split(" @")[0]
			weight = 0
			for part in re.sub("\([^)]+\)", "", display).split():
				digits = re.search("\d+", part)
				if len(part) + (len(digits.group()) * 5 if digits else 0) > weight: # weigh parts with digits higher than those without
					display_short = part
			profile_name = profile_name.replace("%dns", display_short)
			profile_name = profile_name.replace("%dn", display)
		else:
			profile_name = re.sub("[-_\s]+%dns?|%dns?[-_\s]*", "", profile_name)
		instrument = self.comport_ctrl.GetStringSelection()
		if instrument:
			instrument = remove_vendor_names(instrument)
			instrument = instrument.replace("Colorimetre", "")
			instrument = instrument.replace(" ", "")
			profile_name = profile_name.replace("%in", instrument)
		else:
			profile_name = re.sub("[-_\s]+%in|%in[-_\s]*", "", profile_name)
		if measurement_mode:
			mode = ""
			if "c" in measurement_mode:
				mode += "CRT"
			elif "l" in measurement_mode:
				mode += "LCD"
			if "p" in measurement_mode:
				if len(measurement_mode) > 1:
					mode += "-"
				mode += lang.getstr("projector")
			profile_name = profile_name.replace("%im", mode)
		else:
			profile_name = re.sub("[-_\s]+%im|%im[-_\s]*", "", profile_name)
		if isinstance(whitepoint, str):
			if whitepoint.find(",") < 0:
				if self.get_whitepoint_locus() == "t":
					whitepoint = "D" + whitepoint
				else:
					whitepoint += "K"
			else:
				whitepoint = "x ".join(whitepoint.split(",")) + "y"
		profile_name = profile_name.replace("%wp", lang.getstr("native").lower() if whitepoint == None else whitepoint)
		profile_name = profile_name.replace("%cb", lang.getstr("max").lower() if luminance == None else luminance + u"cdm²")
		profile_name = profile_name.replace("%cB", lang.getstr("min").lower() if black_luminance == None else black_luminance + u"cdm²")
		if trc not in ("l", "709", "s", "240"):
			if trc_type == "G":
				trc += " (%s)" % lang.getstr("trc.type.absolute").lower()
		else:
			trc = trc.upper().replace("L", u"L").replace("709", "Rec. 709").replace("S", "sRGB").replace("240", "SMPTE240M")
		profile_name = profile_name.replace("%cg", trc)
		profile_name = profile_name.replace("%ca", ambient + "lx" if ambient else "")
		f = int(float(black_output_offset) * 100)
		profile_name = profile_name.replace("%cf", str(f if f > 0 else 0) + "%")
		k = int(float(black_point_correction) * 100)
		profile_name = profile_name.replace("%ck", (str(k) + "% " if k > 0 and k < 100 else "") + lang.getstr("neutral") if k > 0 else lang.getstr("native").lower())
		if black_point_rate and float(black_point_correction) < 1:
			profile_name = profile_name.replace("%cA", black_point_rate)
		aspects = {
			"c": calibration_quality,
			"p": profile_quality
		}
		msgs = {
			"u": "UQ", #lang.getstr("calibration.quality.ultra"),
			"h": "HQ", #lang.getstr("calibration.quality.high"),
			"m": "MQ", #lang.getstr("calibration.quality.medium"),
			"l": "LQ", #lang.getstr("calibration.quality.low")
		}
		for a in aspects:
			profile_name = profile_name.replace("%%%sq" % a, msgs[aspects[a]]) #.lower())
		for q in msgs:
			pat = re.compile("(" + msgs[q] + ")\W" + msgs[q], re.I)
			profile_name = re.sub(pat, "\\1", profile_name)
		if self.get_profile_type() == "l":
			profile_type = "LUT"
		else:
			profile_type = "MTX"
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
		
		profile_name = re.sub("(\W?%s)+" % lang.getstr("native").lower(), "\\1", profile_name)
		
		return re.sub("[\\/:*?\"<>|]+", "_", profile_name)[:255]

	def update_profile_name(self, event = None):
		profile_name = self.create_profile_name()
		if not self.check_profile_name(profile_name):
			self.profile_name_textctrl.ChangeValue(getcfg("profile.name"))
			profile_name = self.create_profile_name()
			if not self.check_profile_name(profile_name):
				self.profile_name_textctrl.ChangeValue(defaults.get("profile.name", ""))
				profile_name = self.create_profile_name()
		profile_name = self.make_argyll_compatible_path(profile_name)
		if profile_name != self.get_profile_name():
			setcfg("profile.name", self.profile_name_textctrl.GetValue())
			self.profile_name.SetToolTipString(profile_name)
			self.profile_name.SetLabel(profile_name.replace("&", "&&"))

	def check_profile_name(self, profile_name = None):
		if re.match(re.compile("^[^\\/:*?\"<>|]+$"), profile_name if profile_name is not None else self.create_profile_name()):
			return True
		else:
			return False

	def get_ambient(self):
		if self.ambient_viewcond_adjust_cb.GetValue():
			return str(stripzeros(self.ambient_viewcond_adjust_textctrl.GetValue().replace(",", ".")))
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

	def get_whitepoint(self):
		if self.whitepoint_native_rb.GetValue(): # native
			return None
		elif self.whitepoint_colortemp_rb.GetValue(): # color temperature in kelvin
			return str(stripzeros(self.whitepoint_colortemp_textctrl.GetValue().replace(",", ".")))
		elif self.whitepoint_xy_rb.GetValue():
			x = self.whitepoint_x_textctrl.GetValue().replace(",", ".")
			try:
				x = round(float(x), 6)
			except ValueError:
				pass
			y = self.whitepoint_y_textctrl.GetValue().replace(",", ".")
			try:
				y = round(float(y), 6)
			except ValueError:
				pass
			return str(stripzeros(x)) + "," + str(stripzeros(y))

	def get_whitepoint_locus(self):
		n = self.whitepoint_colortemp_locus_ctrl.GetSelection()
		if not n in self.whitepoint_colortemp_loci_ab:
			n = 0
		return str(self.whitepoint_colortemp_loci_ab[n])

	def get_luminance(self):
		if self.luminance_max_rb.GetValue():
			return None
		else:
			return str(stripzeros(self.luminance_textctrl.GetValue().replace(",", ".")))

	def get_black_luminance(self):
		if self.black_luminance_min_rb.GetValue():
			return None
		else:
			return str(stripzeros(self.black_luminance_textctrl.GetValue().replace(",", ".")))

	def get_black_output_offset(self):
		return str(Decimal(self.black_output_offset_ctrl.GetValue()) / 100)

	def get_black_point_correction(self):
		return str(Decimal(self.black_point_correction_ctrl.GetValue()) / 100)

	def get_black_point_rate(self):
		if hasattr(self, "black_point_rate_ctrl") and defaults["calibration.black_point_rate.enabled"]:
			return str(Decimal(self.black_point_rate_ctrl.GetValue()) / 100)
		else:
			return None

	def get_trc_type(self):
		if self.trc_type_ctrl.GetSelection() == 1 and self.trc_g_rb.GetValue():
			return "G"
		else:
			return "g"

	def get_trc(self):
		if self.trc_g_rb.GetValue():
			return str(stripzeros(self.trc_textctrl.GetValue().replace(",", ".")))
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

	def profile_settings_changed(self):
		cal = getcfg("calibration.file")
		if cal:
			filename, ext = os.path.splitext(cal)
			if ext.lower() in (".icc", ".icm"):
				if not os.path.exists(filename + ".cal") and not cal in self.presets: #or not self.calibration_update_cb.GetValue():
					self.cal_changed()
					return
		if not self.updatingctrls:
			setcfg("settings.changed", 1)
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
			defaultDir, defaultFile = get_verified_path("testchart.file")
			dlg = wx.FileDialog(self, lang.getstr("dialog.set_testchart"), defaultDir = defaultDir, defaultFile = defaultFile, wildcard = lang.getstr("filetype.icc_ti1_ti3") + "|*.icc;*.icm;*.ti1;*.ti3", style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
			dlg.Center(wx.BOTH)
			result = dlg.ShowModal()
			if result == wx.ID_OK:
				path = dlg.GetPath()
			dlg.Destroy()
		if path:
			if not os.path.exists(path):
				InfoDialog(self, msg = lang.getstr("file.missing", path), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
				return
			filename, ext = os.path.splitext(path)
			if ext.lower() in (".icc", ".icm"):
				try:
					profile = ICCP.ICCProfile(path)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					InfoDialog(self, msg = lang.getstr("profile.invalid"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					return
				ti3_lines = [line.strip() for line in StringIO(profile.tags.get("CIED", ""))]
				if not "CTI3" in ti3_lines:
					InfoDialog(self, msg = lang.getstr("profile.no_embedded_ti3"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					return
			self.set_testchart(path)
			writecfg()
			self.profile_settings_changed()

	def create_testchart_btn_handler(self, event):
		if not hasattr(self, "tcframe"):
			self.init_tcframe()
		elif not hasattr(self.tcframe, "ti1") or getcfg("testchart.file") != self.tcframe.ti1.filename:
			self.tcframe.tc_load_cfg_from_ti1()
		self.tcframe.Show()
		self.tcframe.Raise()
		return

	def init_tcframe(self):
		self.tcframe = TestchartEditor(self)

	def set_default_testchart(self, alert = True, force = False):
		path = getcfg("testchart.file")
		if os.path.basename(path) in self.app.dist_testchart_names:
			path = self.app.dist_testcharts[self.app.dist_testchart_names.index(os.path.basename(path))]
			setcfg("testchart.file", path)
		if force or lang.getstr(os.path.basename(path)) in [""] + self.default_testchart_names or ((not os.path.exists(path) or not os.path.isfile(path))):
			ti1 = self.testchart_defaults[self.get_measurement_mode()][self.get_profile_type()]
			path = get_data_path(os.path.join("ti1", ti1))
			if not path or not os.path.isfile(path):
				if alert:
					InfoDialog(self, msg = lang.getstr("error.testchart.missing", ti1), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
				elif verbose >= 1:
					safe_print(lang.getstr("error.testchart.missing", ti1))
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
			path = getcfg("testchart.file")
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
			ti1_1 = verify_ti1_rgb_xyz(ti1)
			if not ti1_1:
				InfoDialog(self, msg = lang.getstr("error.testchart.invalid", path), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
				self.set_default_testchart()
				return
			if path != getcfg("calibration.file"):
				self.profile_settings_changed()
			setcfg("testchart.file", path)
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
			self.testchart_ctrl.SetToolTipString(path)
			if ti1.queryv1("COLOR_REP") and ti1.queryv1("COLOR_REP")[:3] == "RGB":
				self.options_targen = ["-d3"]
				if debug: safe_print("Setting targen options:", self.options_targen)
			if self.testchart_ctrl.IsEnabled():
				self.testchart_patches_amount.SetLabel(str(ti1.queryv1("NUMBER_OF_SETS")))
			else:
				self.testchart_patches_amount.SetLabel("")
		except Exception, exception:
			InfoDialog(self, msg = lang.getstr("error.testchart.read", path) + "\n\n" + unicode(str(exception), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
			self.set_default_testchart()
		else:
			if hasattr(self, "tcframe") and self.tcframe.IsShownOnScreen() and (not hasattr(self.tcframe, "ti1") or getcfg("testchart.file") != self.tcframe.ti1.filename):
				self.tcframe.tc_load_cfg_from_ti1()

	def get_testchart_names(self, path = None):
		testchart_names = []
		self.testcharts = []
		if path is None:
			path = getcfg("testchart.file")
		if os.path.exists(path):
			testchart_dir = os.path.dirname(path)
			try:
				testcharts = listdir_re(testchart_dir, "\.(?:icc|icm|ti1|ti3)$")
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
			self.testchart_names += [lang.getstr(chart[-1])]
			i += 1
		return self.testchart_names

	def get_testchart(self):
		return getcfg("testchart.file")

	def get_testcharts(self):
		return

	def check_set_argyll_bin(self):
		if self.check_argyll_bin():
			return True
		else:
			return self.set_argyll_bin()
	
	def get_argyll_util(self, name, paths = None):
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
	
	def get_argyll_utilname(self, name, paths = None):
		exe = self.get_argyll_util(name, paths)
		if exe:
			exe = os.path.basename(os.path.splitext(exe)[0])
		return exe

	def check_argyll_bin(self, paths = None):
		prev_dir = None
		for name in argyll_names:
			exe = self.get_argyll_util(name, paths)
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

	def set_argyll_bin(self):
		if self.IsShownOnScreen():
			parent = self
		else:
			parent = None # do not center on parent if not visible
		defaultPath = os.path.sep.join(get_verified_path("argyll.dir"))
		dlg = wx.DirDialog(parent, lang.getstr("dialog.set_argyll_bin"), defaultPath = defaultPath, style = wx.DD_DIR_MUST_EXIST)
		dlg.Center(wx.BOTH)
		result = dlg.ShowModal() == wx.ID_OK
		if result:
			path = dlg.GetPath().rstrip(os.path.sep)
			result = self.check_argyll_bin([path])
			if result:
				if verbose >= 3: safe_print("Setting Argyll binary directory:", path)
				setcfg("argyll.dir", path)
			else:
				InfoDialog(self, msg = lang.getstr("argyll.dir.invalid", (exe_ext, exe_ext, exe_ext, exe_ext, exe_ext)), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
			writecfg()
		dlg.Destroy()
		return result

	def set_argyll_bin_handler(self, event):
		if self.set_argyll_bin():
			self.check_update_controls()
			if len(self.displays):
				if getcfg("calibration.file"):
					self.load_cal(silent = True) # load LUT curves from last used .cal file
				else:
					self.load_display_profile_cal(None) # load LUT curves from current display profile (if any, and if it contains curves)

	def check_update_controls(self, event = None, silent = False):
		displays = list(self.displays)
		comports = list(self.comports)
		self.enumerate_displays_and_ports(silent)
		if displays != self.displays:
			self.update_displays()
			if verbose >= 1: safe_print(lang.getstr("display_detected"))
		if comports != self.comports:
			self.update_comports()
			if verbose >= 1: safe_print(lang.getstr("comport_detected"))
		if displays != self.displays or comports != self.comports:
			self.init_menus()
			self.update_main_controls()

	def plugplay_timer_handler(self, event):
		if debug: safe_print("plugplay_timer_handler")
		self.check_update_controls(silent = True)

	def extract_fix_copy_cal(self, source_filename, target_filename = None):
		""" Extract the CAL info from a profile's embedded measurement data,
		try to 'fix it' (add information needed to make the resulting .cal file
		'updateable') and copy it to target_filename """
		try:
			profile = ICCP.ICCProfile(source_filename)
		except (IOError, ICCP.ICCProfileInvalidError), exception:
			InfoDialog(self, msg = lang.getstr("profile.invalid"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
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
						InfoDialog(self, msg = lang.getstr("cal_extraction_failed") + "\n\n" + unicode(str(exception), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
						return None
				return cal_lines
		else:
			return None

	def get_options_from_cprt(self, cprt):
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
		if getcfg("settings.changed") and not self.settings_confirm_discard():
			return
		if path is None:
			defaultDir, defaultFile = get_verified_path("last_cal_or_icc_path")
			dlg = wx.FileDialog(self, lang.getstr("dialog.load_cal"), defaultDir = defaultDir, defaultFile = defaultFile, wildcard = lang.getstr("filetype.cal_icc") + "|*.cal;*.icc;*.icm", style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
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
					setcfg("recent_cals", os.pathsep.join(recent_cals))
					self.calibration_file_ctrl.Delete(sel)
					cal = getcfg("calibration.file") or ""
					# the case-sensitive index could fail because of case insensitive file systems
					# e.g. the filename string from the cfg is "C:\Users\Name\AppData\dispcalGUI\storage\MyFile",
					# but the actual filename is "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
					# (maybe because the user manually renamed the file)
					try:
						idx = self.recent_cals.index(cal)
					except ValueError, exception:
						idx = indexi(self.recent_cals, cal)
					self.calibration_file_ctrl.SetSelection(idx)
				InfoDialog(self, msg = lang.getstr("file.missing", path), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
				return

			filename, ext = os.path.splitext(path)
			if ext.lower() in (".icc", ".icm"):
				try:
					profile = ICCP.ICCProfile(path)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					InfoDialog(self, msg = lang.getstr("profile.invalid"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					return
				if profile.profileClass != "mntr" or profile.colorSpace != "RGB":
					InfoDialog(self, msg = lang.getstr("profile.unsupported", (profile.profileClass, profile.colorSpace)), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					return
				cal = StringIO(profile.tags.get("CIED", ""))
			else:
				try:
					cal = open(path, "rU")
				except Exception, exception:
					InfoDialog(self, msg = lang.getstr("error.file.open", path), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					return
			ti3_lines = [line.strip() for line in cal]
			cal.close()
			setcfg("last_cal_or_icc_path", path)
			if ext.lower() in (".icc", ".icm"):
				setcfg("last_icc_path", path)
				if "cprt" in profile.tags:
					options_dispcal, options_colprof = self.get_options_from_cprt(profile.tags.cprt)
					if options_dispcal or options_colprof:
						if debug: safe_print("options_dispcal:", options_dispcal)
						if debug: safe_print("options_colprof:", options_colprof)
						# parse options
						if options_dispcal:
							# restore defaults
							self.restore_defaults_handler(include = ("calibration", "measure.darken_background", "profile.update", "trc", "whitepoint"), exclude = ("calibration.black_point_correction_choice.show", "measure.darken_background.show_warning", "trc.should_use_viewcond_adjust.show_msg"))
							self.options_dispcal = ["-" + arg for arg in options_dispcal]
							for o in options_dispcal:
								if o[0] == "d":
									o = o[1:].split(",")
									setcfg("display.number", o[0])
									if len(o) > 1:
										setcfg("display_lut.number", o[1])
										setcfg("display_lut.link", int(o[0] == o[1]))
									continue
								if o[0] == "c":
									setcfg("comport.number", o[1:])
									continue
								if o[0] == "m":
									setcfg("calibration.interactive_display_adjustment", 0)
									continue
								if o[0] == "o":
									setcfg("profile.update", 1)
									continue
								if o[0] == "u":
									setcfg("calibration.update", 1)
									continue
								if o[0] == "q":
									setcfg("calibration.quality", o[1])
									continue
								if o[0] == "y":
									setcfg("measurement_mode", o[1])
									continue
								if o[0] in ("t", "T"):
									setcfg("whitepoint.colortemp.locus", o[0])
									if o[1:]:
										setcfg("whitepoint.colortemp", o[1:])
									setcfg("whitepoint.x", None)
									setcfg("whitepoint.y", None)
									continue
								if o[0] == "w":
									o = o[1:].split(",")
									setcfg("whitepoint.colortemp", None)
									setcfg("whitepoint.x", o[0])
									setcfg("whitepoint.y", o[1])
									continue
								if o[0] == "b":
									setcfg("calibration.luminance", o[1:])
									continue
								if o[0] in ("g", "G"):
									setcfg("trc.type", o[0])
									setcfg("trc", o[1:])
									continue
								if o[0] == "f":
									setcfg("calibration.black_output_offset", o[1:])
									continue
								if o[0] == "a":
									setcfg("calibration.ambient_viewcond_adjust", 1)
									setcfg("calibration.ambient_viewcond_adjust.lux", o[1:])
									continue
								if o[0] == "k":
									setcfg("calibration.black_point_correction", o[1:])
									continue
								if o[0] == "A":
									setcfg("calibration.black_point_rate", o[1:])
									continue
								if o[0] == "B":
									setcfg("calibration.black_luminance", o[1:])
									continue
								if o[0] in ("p", "P") and len(o[1:]) >= 5:
									setcfg("dimensions.measureframe", o[1:])
									setcfg("dimensions.measureframe.unzoomed", o[1:])
									continue
								if o[0] == "p" and len(o[1:]) == 0:
									setcfg("projector_mode", 1)
									continue
								if o[0] == "F":
									setcfg("measure.darken_background", 1)
									continue
						if options_colprof:
							# restore defaults
							self.restore_defaults_handler(include = ("profile", "gamap_"), exclude = ("profile.update", "profile.name"))
							for o in options_colprof:
								if o[0] == "q":
									setcfg("profile.quality", o[1])
									continue
								if o[0] == "a":
									setcfg("profile.type", o[1])
									continue
								if o[0] in ("s", "S"):
									o = o.split(None, 1)
									setcfg("gamap_profile", o[1][1:-1])
									setcfg("gamap_perceptual", 1)
									if o[0] == "S":
										setcfg("gamap_saturation", 1)
									continue
								if o[0] == "c":
									setcfg("gamap_src_viewcond", o[1:])
									continue
								if o[0] == "d":
									setcfg("gamap_out_viewcond", o[1:])
									continue
						# if options_dispcal and options_colprof:
							# setcfg("calibration.file", path)
						# else:
							# setcfg("calibration.file", None)
						setcfg("calibration.file", path)
						if "CTI3" in ti3_lines:
							setcfg("testchart.file", path)
						self.update_controls(update_profile_name = update_profile_name)
						writecfg()

						if "vcgt" in profile.tags:
							# load calibration into lut
							self.load_cal(cal = path, silent = True)
							if options_dispcal:
								return
							else:
								msg = lang.getstr("settings_loaded.profile_and_lut")
						elif options_dispcal:
							msg = lang.getstr("settings_loaded.cal_and_profile")
						else:
							msg = lang.getstr("settings_loaded.profile")

						if not silent: InfoDialog(self, msg = msg, ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-information"))
						return
					else:
						sel = self.calibration_file_ctrl.GetSelection()
						if len(self.recent_cals) > sel and self.recent_cals[sel] == path:
							self.recent_cals.remove(self.recent_cals[sel])
							self.calibration_file_ctrl.Delete(sel)
							cal = getcfg("calibration.file") or ""
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
						if not silent: InfoDialog(self, msg = lang.getstr("no_settings"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
						return
				elif not "CIED" in profile.tags:
					sel = self.calibration_file_ctrl.GetSelection()
					if len(self.recent_cals) > sel and self.recent_cals[sel] == path:
						self.recent_cals.remove(self.recent_cals[sel])
						self.calibration_file_ctrl.Delete(sel)
						cal = getcfg("calibration.file") or ""
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
					if not silent: InfoDialog(self, msg = lang.getstr("no_settings"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
					return

			setcfg("last_cal_path", path)

			# restore defaults
			self.restore_defaults_handler(include = ("calibration", "profile.update", "trc", "whitepoint"), exclude = ("calibration.black_point_correction_choice.show", "trc.should_use_viewcond_adjust.show_msg"))

			self.options_dispcal = []
			settings = []
			for line in ti3_lines:
				line = line.strip().split(" ", 1)
				if len(line) > 1:
					value = line[1][1:-1] # strip quotes
					if line[0] == "DEVICE_CLASS":
						if value != "DISPLAY":
							InfoDialog(self, msg = lang.getstr("calibration.file.invalid"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
							return
					elif line[0] == "DEVICE_TYPE":
						measurement_mode = value.lower()[0]
						if measurement_mode in ("c", "l"):
							setcfg("measurement_mode", measurement_mode)
							self.options_dispcal += ["-y" + measurement_mode]
					elif line[0] == "NATIVE_TARGET_WHITE":
						setcfg("whitepoint.colortemp", None)
						setcfg("whitepoint.x", None)
						setcfg("whitepoint.y", None)
						settings += [lang.getstr("whitepoint")]
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
						if not lang.getstr("whitepoint") in settings:
							setcfg("whitepoint.colortemp", None)
							setcfg("whitepoint.x", stripzeros(round(x, 6)))
							setcfg("whitepoint.y", stripzeros(round(y, 6)))
							self.options_dispcal += ["-w%s,%s" % (getcfg("whitepoint.x"), getcfg("whitepoint.y"))]
							settings += [lang.getstr("whitepoint")]
						setcfg("calibration.luminance", stripzeros(round(Y * 100, 3)))
						self.options_dispcal += ["-b%s" % getcfg("calibration.luminance")]
						settings += [lang.getstr("calibration.luminance")]
					elif line[0] == "TARGET_GAMMA":
						setcfg("trc", None)
						if value == "L_STAR":
							setcfg("trc", "l")
						elif value == "REC709":
							setcfg("trc", "709")
						elif value == "SMPTE240M":
							setcfg("trc", "240")
						elif value == "sRGB":
							setcfg("trc", "s")
						else:
							try:
								value = stripzeros(value)
								if float(value) < 0:
									setcfg("trc.type", "G")
									value = abs(value)
								else:
									setcfg("trc.type", "g")
								setcfg("trc", value)
							except ValueError:
								continue
						self.options_dispcal += ["-" + getcfg("trc.type") + getcfg("trc")]
						settings += [lang.getstr("trc")]
					elif line[0] == "DEGREE_OF_BLACK_OUTPUT_OFFSET":
						setcfg("calibration.black_output_offset", stripzeros(value))
						self.options_dispcal += ["-f%s" % getcfg("calibration.black_output_offset")]
						settings += [lang.getstr("calibration.black_output_offset")]
					elif line[0] == "BLACK_POINT_CORRECTION":
						setcfg("calibration.black_point_correction", stripzeros(value))
						self.options_dispcal += ["-k%s" % getcfg("calibration.black_point_correction")]
						settings += [lang.getstr("calibration.black_point_correction")]
					elif line[0] == "TARGET_BLACK_BRIGHTNESS":
						setcfg("calibration.black_luminance", stripzeros(value))
						self.options_dispcal += ["-B%s" % getcfg("calibration.black_luminance")]
						settings += [lang.getstr("calibration.black_luminance")]
					elif line[0] == "QUALITY":
						setcfg("calibration.quality", value.lower()[0])
						self.options_dispcal += ["-q" + getcfg("calibration.quality")]
						settings += [lang.getstr("calibration.quality")]

			if len(settings) == 0:
				sel = self.calibration_file_ctrl.GetSelection()
				if len(self.recent_cals) > sel and self.recent_cals[sel] == path:
					self.recent_cals.remove(self.recent_cals[sel])
					self.calibration_file_ctrl.Delete(sel)
					cal = getcfg("calibration.file") or ""
					# the case-sensitive index could fail because of case insensitive file systems
					# e.g. the filename string from the cfg is "C:\Users\Name\AppData\dispcalGUI\storage\MyFile",
					# but the actual filename is "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
					# (maybe because the user manually renamed the file)
					try:
						idx = self.recent_cals.index(cal)
					except ValueError, exception:
						idx = indexi(self.recent_cals, cal)
					self.calibration_file_ctrl.SetSelection(idx)
				writecfg()
				if not silent: InfoDialog(self, msg = lang.getstr("no_settings"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
			else:
				setcfg("calibration.file", path)
				if "CTI3" in ti3_lines:
					setcfg("testchart.file", path)
				self.update_controls(update_profile_name = update_profile_name)
				writecfg()

				# load calibration into lut
				self.load_cal(silent = True)
				if not silent: InfoDialog(self, msg = lang.getstr("settings_loaded", ", ".join(settings)), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-information"))

	def delete_calibration_handler(self, event):
		cal = getcfg("calibration.file")
		if cal and os.path.exists(cal):
			caldir = os.path.dirname(cal)
			try:
				dircontents = os.listdir(caldir)
			except Exception, exception:
				InfoDialog(self, msg = unicode(str(exception), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
				return
			self.related_files = {}
			for entry in dircontents:
				fn, ext = os.path.splitext(entry)
				if ext.lower() in (".app", cmdfile_ext):
					fn, ext = os.path.splitext(fn)
				if fn == os.path.splitext(os.path.basename(cal))[0]:
					self.related_files[entry] = True
			self.dlg = dlg = ConfirmDialog(self, msg = lang.getstr("dialog.confirm_delete"), ok = lang.getstr("delete"), cancel = lang.getstr("cancel"), bitmap = getbitmap("theme/icons/32x32/dialog-warning"))
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
				if sys.platform == "darwin":
					trashcan = lang.getstr("trashcan.mac")
				elif sys.platform == "win32":
					trashcan = lang.getstr("trashcan.windows")
				else:
					trashcan = lang.getstr("trashcan.linux")
				try:
					if (sys.platform == "darwin" and \
					   len(delete_related_files) + 1 == len(dircontents) and \
					   ".DS_Store" in dircontents) or \
					   len(delete_related_files) == len(dircontents):
						# delete whole folder
						trash([os.path.dirname(cal)])
					else:
						trash(delete_related_files)
				except TrashcanUnavailableError, exception:
					InfoDialog(self, msg = lang.getstr("error.trashcan_unavailable", trashcan), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
				except Exception, exception:
					InfoDialog(self, msg = lang.getstr("error.deletion", trashcan) + "\n\n" + unicode(str(exception), enc, "replace"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-error"))
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
				setcfg("calibration.file", None)
				setcfg("settings.changed", 1)
				recent_cals = []
				for recent_cal in self.recent_cals:
					if recent_cal not in self.presets:
						recent_cals += [recent_cal]
				setcfg("recent_cals", os.pathsep.join(recent_cals))
				self.update_controls(False)
				self.load_display_profile_cal()
	
	def delete_calibration_related_handler(self, event):
		chk = self.dlg.FindWindowById(event.GetId())
		self.related_files[chk.GetLabel()] = chk.GetValue()
	
	def aboutdialog_handler(self, event):
		if hasattr(self, "aboutdialog"):
			self.aboutdialog.Destroy()
		self.aboutdialog = AboutDialog(self, -1, lang.getstr("menu.about"), size = (100, 100))
		items = []
		items += [wx.StaticBitmap(self.aboutdialog, -1, getbitmap("theme/header-about"))]
		items += [wx.StaticText(self.aboutdialog, -1, "")]
		items += [wx.StaticText(self.aboutdialog, -1, u"%s %s © %s" % (appname, version, author))]
		items += [wx.StaticText(self.aboutdialog, -1, u"build %s" % build)]
		items += [wx.lib.hyperlink.HyperLinkCtrl(self.aboutdialog, -1, label="%s.hoech.net" % appname, URL="http://%s.hoech.net" % appname)]
		items += [wx.StaticText(self.aboutdialog, -1, "")]
		items += [wx.StaticText(self.aboutdialog, -1, u"Argyll CMS %s © Graeme Gill" % self.argyll_version_string)]
		items += [wx.lib.hyperlink.HyperLinkCtrl(self.aboutdialog, -1, label="ArgyllCMS.com", URL="http://www.argyllcms.com")]
		items += [wx.StaticText(self.aboutdialog, -1, "")]
		items += [wx.StaticText(self.aboutdialog, -1, u"%s:" % lang.getstr("translations"))]
		lauthors = {}
		for lcode in lang.ldict:
			lauthor = lang.ldict[lcode].get("author")
			language = lang.ldict[lcode].get("language")
			if lauthor and language:
				if not lauthors.get(lauthor):
					lauthors[lauthor] = []
				lauthors[lauthor] += [language]
		lauthors = [(lauthors[lauthor], lauthor) for lauthor in lauthors]
		lauthors.sort()
		for langs, lauthor in lauthors:
			items += [wx.StaticText(self.aboutdialog, -1, "%s - %s" % (", ".join(langs), lauthor))]
		items += [wx.StaticText(self.aboutdialog, -1, "")]
		match = re.match("([^(]+)\s*(\([^(]+\))?\s*(\[[^[]+\])?", sys.version)
		if match:
			pyver_long = match.groups()
		else:
			pyver_long = [sys.version]
		items += [wx.StaticText(self.aboutdialog, -1, "Python " + pyver_long[0].strip())]
		if len(pyver_long) > 1:
			for part in pyver_long[1:]:
				if part:
					items += [wx.StaticText(self.aboutdialog, -1, part)]
		items += [wx.lib.hyperlink.HyperLinkCtrl(self.aboutdialog, -1, label="python.org", URL="http://www.python.org")]
		items += [wx.StaticText(self.aboutdialog, -1, "")]
		items += [wx.StaticText(self.aboutdialog, -1, "wxPython " + wx.version())]
		items += [wx.lib.hyperlink.HyperLinkCtrl(self.aboutdialog, -1, label="wxPython.org", URL="http://www.wxpython.org")]
		items += [wx.StaticText(self.aboutdialog, -1, "")]
		items += [wx.StaticText(self.aboutdialog, -1, lang.getstr("license_info"))]
		items += [wx.StaticText(self.aboutdialog, -1, "")]
		self.aboutdialog.add_items(items)
		self.aboutdialog.Layout()
		self.aboutdialog.Center()
		self.aboutdialog.Show()

	def infoframe_toggle_handler(self, event):
		self.infoframe.Show(not self.infoframe.IsShownOnScreen())

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
		if not hasattr(self, "tcframe") or self.tcframe.tc_close_handler():
			writecfg()
			self.HideAll()
			if hasattr(self, "tempdir") and os.path.exists(self.tempdir) and os.path.isdir(self.tempdir):
				self.wrapup(False)
			if sys.platform not in ("darwin", "win32"):
				try:
					sp.call('echo -e "\\033[0m"', shell = True)
					sp.call('clear', shell = True)
				except Exception, exception:
					safe_print("Info - could not set restore terminal colors:", str(exception))
			config.app = None
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
		if verbose >= 1: safe_print("Error - xte_sendkeys() failed:", exception)

def main():
	try:
		if debug: safe_print("Entering main()...")
		setup_logging()
		if verbose >= 1: safe_print(appname + runtype, version, "build", build)
		# read pre-v0.2.2b configuration if present
		oldcfg = os.path.join(expanduseru("~"), "Library", "Preferences", appname + " Preferences") if sys.platform == "darwin" else os.path.join(expanduseru("~"), "." + appname)
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
				# WindowsError 2 means registry key does not exist, do not show warning in that case
				if sys.platform != "win32" or not hasattr(exception, "errno") or exception.errno != 2:
					safe_print("Warning - could not process old configuration:", str(exception))
		# create main data dir
		if not os.path.exists(datahome):
			try:
				os.makedirs(datahome)
			except Exception, exception:
				handle_error("Warning - could not create directory '%s'" % datahome)
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
								cfgio = StringIO()
								cfg.write(cfgio)
								desktopfile = open(desktopfile_path, "w")
								cfgio.seek(0)
								desktopfile.write(cfgio.read().replace(" = ", "="))
								desktopfile.close()
						except Exception, exception:
							safe_print("Warning - could not process old calibration loader:", str(exception))
		# make sure we run inside a terminal
		if ((sys.platform == "darwin" or (hasattr(sys, "frozen") and sys.frozen)) and (not sys.stdin.isatty() or not sys.stdout.isatty() or not sys.stderr.isatty())) or "-oc" in sys.argv[1:]:
			terminals_opts = {
				"Terminal": "-x",
				"gnome-terminal": "-x",
				"konsole": "-e",
				"xterm": "-e"
			}
			terminals = terminals_opts.keys()
			if isapp:
				me = os.path.join(exedir, pyname)
				cmd = u'"%s"' % me
				cwd = None
			elif isexe:
				me = exe
				cmd = u'"%s"' % win32api.GetShortPathName(exe) if sys.platform == "win32" else exe
				cwd = None
			else:
				me = pypath
				if os.path.basename(exe) == "pythonw" + exe_ext:
					python = os.path.join(os.path.dirname(exe), "python" + exe_ext)
				if sys.platform == "win32":
					cmd = u'"%s" "%s"' % tuple([win32api.GetShortPathName(path) for path in (python, pypath)])
					cwd = win32api.GetShortPathName(pydir)
				else:
					cmd = u'"%s" "%s"' % (python, pypath)
					cwd = pydir.encode(fs_enc)
			safe_print("Re-launching instance in terminal")
			if sys.platform == "win32":
				cmd = u'start "%s" /WAIT %s' % (appname, cmd)
				if debug: safe_print(cmd)
				retcode = sp.call(cmd.encode(fs_enc), shell = True, cwd = cwd)
			elif sys.platform == "darwin":
				if debug: safe_print(cmd)
				retcode = mac_terminal_do_script(cmd)
			else:
				stdout = tempfile.SpooledTemporaryFile()
				retcode = None
				for terminal in terminals:
					if which(terminal):
						if debug: safe_print('%s %s %s' % (terminal, terminals_opts[terminal], cmd))
						stdout.write('%s %s %s' % (terminal, terminals_opts[terminal], cmd.encode(fs_enc)))
						retcode = sp.call([terminal, terminals_opts[terminal]] + cmd.encode(fs_enc).strip('"').split('" "'), stdout = stdout, stderr = sp.STDOUT, cwd = cwd)
						stdout.write('\n\n')
						break
				stdout.seek(0)
			if retcode != 0:
				config.app = wx.App(redirect = False)
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
			lang.init()
			config.app = DisplayCalibrator(redirect = False) # DON'T redirect stdin/stdout
			config.app.MainLoop()
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
