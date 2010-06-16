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
		logfile = open(os.path.join(expanduseru("~"), "dispcalGUI.error.log"), 
					   "w")
		traceback.print_exception(etype, value, tb, file=logfile)
	except:
		pass

sys.excepthook = _early_excepthook

# Python version check

pyver = sys.version_info[:2]
if pyver < (2, 5) or pyver >= (3, ):
	raise RuntimeError("Need Python version >= 2.5 < 3.0, got %s" % 
					   sys.version.split()[0])

# Standard modules

import ConfigParser
ConfigParser.DEFAULTSECT = "Default"
import codecs
import decimal
Decimal = decimal.Decimal
import getpass
import httplib
import logging
import math
import os
if sys.platform == "darwin":
	from platform import mac_ver
import re
import shutil
import socket
import subprocess as sp
import tempfile26 as tempfile
import threading
import traceback
from encodings.aliases import aliases
from time import sleep, strftime

# 3rd party modules

if sys.platform == "win32":
	from ctypes import windll
	from win32com.shell import shell
	from win32console import SetConsoleOutputCP
	import pythoncom
	import win32api
	import win32con
import jspacker

# Config
import config
from config import (autostart, autostart_home, btn_width_correction, build, 
					script_ext, confighome, datahome, defaults, enc, exe, 
					exe_ext, exedir, fs_enc, getbitmap, geticon, get_data_path, 
					getcfg, get_verified_path, original_codepage, 
					initcfg, isapp, isexe, profile_ext, pydir, pyext, pyname, 
					pypath, resfiles, runtype, setcfg, storage, writecfg)

# Custom modules

import CGATS
import ICCProfile as ICCP
import colormath
import localization as lang
import pyi_md5pickuphelper
import wexpect
from argyll_cgats import (add_dispcal_options_to_cal, add_options_to_ti3,
						  cal_to_fake_profile, can_update_cal, 
						  extract_cal_from_ti3, ti3_to_ti1, verify_ti1_rgb_xyz)
from argyll_instruments import instruments, remove_vendor_names
from argyll_names import (names as argyll_names, altnames as argyll_altnames, 
						  viewconds)
from colormath import CIEDCCT2xyY, xyY2CCT, XYZ2CCT, XYZ2Lab, XYZ2xyY
from debughelpers import getevtobjname, getevttype, handle_error
from log import _safe_print, log, logbuffer, safe_print
from meta import (author, name as appname, domain, version, VERSION_BASE)
from options import debug, test, verbose
from trash import trash, TrashcanUnavailableError
from util_decimal import float2dec, stripzeros
from util_io import Files, StringIOu as StringIO
from util_list import index_fallback_ignorecase, natsort
if sys.platform == "darwin":
	from util_mac import mac_terminal_do_script
from util_os import expanduseru, launch_file, listdir_re, which
from util_str import safe_str, safe_unicode, strtr, wrap
import util_x
from worker import (FilteredStream, LineCache, Worker, check_cal_isfile, 
					check_create_dir, check_file_isfile, check_profile_isfile, 
					check_set_argyll_bin, get_argyll_util, 
					get_options_from_profile, make_argyll_compatible_path, 
					printcmdline, set_argyll_bin, show_result_dialog)
try:
	from wxLUTViewer import LUTFrame
except ImportError:
	LUTFrame = None
if sys.platform in ("darwin", "win32") or isexe:
	from wxMeasureFrame import MeasureFrame
from wxTestchartEditor import TestchartEditor
from wxaddons import wx, CustomEvent, CustomGridCellEvent, FileDrop, IsSizer
from wxfixes import GTKMenuItemGetFixedLabel, _intversion
from wxwindows import (AboutDialog, ConfirmDialog, InfoDialog, InvincibleFrame, 
					   LogWindow, TooltipWindow)

# wxPython
from wx import xrc
from wx.lib import delayedresult
from wx.lib.art import flagart
import wx.lib.hyperlink

def _excepthook(etype, value, tb):
	safe_print("".join(safe_unicode(s) for s in traceback.format_exception(etype, value, tb)))

sys.excepthook = _excepthook


def swap_dict_keys_values(mydict):
	return dict([(v, k) for (k, v) in mydict.iteritems()])


def app_update_check(parent=None):
	safe_print(lang.getstr("check_update"))
	conn = httplib.HTTPConnection(domain)
	try:
		conn.request("GET", "/VERSION")
		resp = conn.getresponse()
	except (socket.error, httplib.HTTPException), exception:
		safe_print(lang.getstr("failure"), log=False)
		wx.CallAfter(InfoDialog, parent, 
					 msg=" ".join([lang.getstr("check_update.fail"),
								   lang.getstr("connection.fail", 
											   " ".join([str(arg) for 
														 arg in exception.args]))]),
					 ok=lang.getstr("ok"), 
					 bitmap=geticon(32, "dialog-error"))
		return
	if resp.status != httplib.OK:
		safe_print(lang.getstr("failure"), log=False)
		wx.CallAfter(InfoDialog, parent, 
					 msg=" ".join([lang.getstr("check_update.fail"),
								   lang.getstr("connection.fail.http", 
											   " ".join([str(resp.status),
														 resp.reason,
														 domain + "/VERSION"]))]),
					 ok=lang.getstr("ok"), 
					 bitmap=geticon(32, "dialog-error"))
		return
	data = resp.read()
	try:
		newversion_tuple = tuple(int(n) for n in data.split("."))
	except ValueError:
		safe_print(lang.getstr("failure"), log=False)
		wx.CallAfter(InfoDialog, parent, 
					 msg=lang.getstr("check_update.fail.version",
									 domain),
					 ok=lang.getstr("ok"), 
					 bitmap=geticon(32, "dialog-error"))
		return
	if newversion_tuple > VERSION_BASE:
		safe_print(lang.getstr("check_update.new_version", 
							   ".".join(str(n) for n in newversion_tuple)))
		launch_file("http://" + domain)
	else:
		wx.CallAfter(InfoDialog, parent, 
					 msg=lang.getstr("check_update.uptodate",
									 appname),
					 ok=lang.getstr("ok"), 
					 bitmap=geticon(32, "dialog-information"), print_=True)


class BaseFrame(wx.Frame):

	""" Main frame base class. """
	
	def __init__(self, *args, **kwargs):
		wx.Frame.__init__(self, *args, **kwargs)

	def focus_handler(self, event):
		if debug and hasattr(self, "last_focused_ctrl"):
				safe_print("[D] Last focused control: %s" %
						   self.last_focused_ctrl)
		if hasattr(self, "last_focused_ctrl") and self.last_focused_ctrl and \
		   self.last_focused_ctrl != event.GetEventObject():
			catchup_event = wx.FocusEvent(wx.EVT_KILL_FOCUS.evtType[0], 
										  self.last_focused_ctrl.GetId())
			if debug:
				safe_print("[D] Last focused control ID %s %s processing "
						   "catchup event type %s %s" % 
						   (self.last_focused_ctrl.GetId(), 
							self.last_focused_ctrl.GetName(), 
							catchup_event.GetEventType(), 
							getevttype(catchup_event)))
			if self.last_focused_ctrl.ProcessEvent(catchup_event):
				if debug:
					safe_print("[D] Last focused control processed catchup "
							   "event")
				event.Skip()
				if hasattr(event.GetEventObject(), "GetId") and \
				   callable(event.GetEventObject().GetId):
					event = CustomEvent(event.GetEventType(), 
										event.GetEventObject(), 
										self.last_focused_ctrl)
		if hasattr(event.GetEventObject(), "GetId") and \
		   callable(event.GetEventObject().GetId):
		   	if debug:
					safe_print("[D] Setting last focused control to %s " %
							   event.GetEventObject())
			self.last_focused_ctrl = event.GetEventObject()
		if debug:
			if hasattr(event, "GetWindow") and event.GetWindow():
				safe_print("[D] Focus moving from control ID %s %s to %s %s, "
						   "event type %s %s" % (event.GetWindow().GetId(), 
												 event.GetWindow().GetName(), 
												 event.GetId(), 
												 getevtobjname(event, self), 
												 event.GetEventType(), 
												 getevttype(event)))
			else:
				safe_print("[D] Focus moving to control ID %s %s, event type "
						   "%s %s" % (event.GetId(), 
									  getevtobjname(event, self), 
									  event.GetEventType(), getevttype(event)))
		event.Skip()
	
	def setup_language(self):
		"""
		Substitute translated strings for menus, controls, labels and tooltips.
		
		"""
		
		# Menus
		menubar = self.menubar if hasattr(self, "menubar") else self.GetMenuBar()
		if menubar:
			for menu, label in menubar.GetMenus():
				menu_pos = menubar.FindMenu(label)
				if not hasattr(menu, "_Label"):
					# Backup un-translated label
					menu._Label = label
				menubar.SetMenuLabel(menu_pos, "&" + lang.getstr(
									 GTKMenuItemGetFixedLabel(menu._Label)))
				if not hasattr(menu, "_Items"):
					# Backup un-translated labels
					menu._Items = [(item, item.Label) for item in 
								   menu.GetMenuItems()]
				for item, label in menu._Items:
					if item.Label:
						label = GTKMenuItemGetFixedLabel(label)
						if item.Accel:
							item.Text = lang.getstr(label) + "\t" + \
										item.Accel.ToString()
						else:
							item.Text = lang.getstr(label)
			if sys.platform == "darwin":
				wx.GetApp().SetMacHelpMenuTitleName(lang.getstr("menu.help"))
			self.SetMenuBar(menubar)
		
		# Controls and labels
		for child in self.GetAllChildren():
			if (isinstance(child, wx.StaticText) or 
				isinstance(child, wx.Control)):
				if not hasattr(child, "_Label"):
					# Backup un-translated label
					label = child._Label = child.Label
				else:
					# Restore un-translated label
					label = child._Label
				translated = lang.getstr(label)
				if translated != label:
					child.Label = translated
				if child.ToolTip:
					if not hasattr(child, "_ToolTipString"):
						# Backup un-translated tooltip
						tooltipstr = child._ToolTipString = child.ToolTip.Tip
					else:
						# Restore un-translated tooltip
						tooltipstr = child._ToolTipString
					translated = lang.getstr(tooltipstr)
					if translated != tooltipstr:
						child.SetToolTipString(wrap(translated, 72))
	
	def update_layout(self):
		""" Update main window layout. """
		self.GetSizer().SetSizeHints(self)
		self.GetSizer().Layout()
	
	def set_child_ctrls_as_attrs(self, parent=None):
		"""
		Set child controls and labels as attributes of the frame.
		
		Will also set a maximum font size of 11 pt.
		parent is the window over which children will be iterated and
		defaults to self.
		
		"""
		if not parent:
			parent = self
		for child in parent.GetAllChildren():
			if (isinstance(child, wx.StaticText) or 
				isinstance(child, wx.Control)):
				child.SetMaxFontSize(11)
				if sys.platform == "darwin" or debug:
					# Work around ComboBox issues on Mac OS X
					# (doesn't receive EVT_KILL_FOCUS)
					if isinstance(child, wx.ComboBox):
						if child.IsEditable():
							if debug:
								safe_print("[D]", child.Name,
										   "binds EVT_TEXT to focus_handler")
							child.Bind(wx.EVT_TEXT, self.focus_handler)
					else:
						child.Bind(wx.EVT_SET_FOCUS, self.focus_handler)
				if not hasattr(self, child.Name):
					setattr(self, child.Name, child)


class GamapFrame(BaseFrame):

	""" Gamut mapping options window. """
	
	def __init__(self, parent):
		self.res = xrc.XmlResource(get_data_path(os.path.join("xrc", 
															  "gamap.xrc")))
		pre = wx.PreFrame()
		self.res.LoadOnFrame(pre, parent, "gamapframe")
		self.PostCreate(pre)
		self.Bind(wx.EVT_CLOSE, self.OnClose, self)
		
		icon = get_data_path(os.path.join("theme", "icons", "16x16", appname + 
										  ".png"))
		if icon:
			self.SetIcon(wx.Icon(icon, wx.BITMAP_TYPE_PNG))
		
		self.SetTitle(lang.getstr("gamapframe.title"))

		self.panel = self.FindWindowByName("panel")
		
		self.set_child_ctrls_as_attrs(self)

		# Bind event handlers
		self.Bind(wx.EVT_CHECKBOX, self.gamap_perceptual_cb_handler, 
				   id=self.gamap_perceptual_cb.GetId())
		self.Bind(wx.EVT_CHECKBOX, self.gamap_saturation_cb_handler, 
				   id=self.gamap_saturation_cb.GetId())
		self.Bind(wx.EVT_COMBOBOX, self.gamap_src_viewcond_handler, 
				   id=self.gamap_src_viewcond_ctrl.GetId())
		self.Bind(wx.EVT_COMBOBOX, self.gamap_out_viewcond_handler, 
				   id=self.gamap_out_viewcond_ctrl.GetId())

		self.viewconds_ab = {}
		self.viewconds_ba = {}
		self.viewconds_out_ab = {}
		
		self.setup_language()
		self.update_controls()
		self.update_layout()

	def OnClose(self, event):
		self.Hide()

	def gamap_profile_handler(self, event=None):
		v = self.gamap_profile.GetPath()
		p = bool(v) and os.path.exists(v)
		if p:
			try:
				profile = ICCP.ICCProfile(v)
			except (IOError, ICCP.ICCProfileInvalidError), exception:
				p = False
				InfoDialog(self, msg=lang.getstr("profile.invalid") + "\n" + v, 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				self.gamap_profile.SetPath("")
				v = None
			else:
				# pre-select suitable viewing condition
				if profile.profileClass == "prtr":
					self.gamap_src_viewcond_ctrl.SetStringSelection(
						lang.getstr("gamap.viewconds.pp"))
				else:
					self.gamap_src_viewcond_ctrl.SetStringSelection(
						lang.getstr("gamap.viewconds.mt"))
		self.gamap_perceptual_cb.Enable(p)
		self.gamap_saturation_cb.Enable(p)
		c = self.gamap_perceptual_cb.GetValue() or \
			self.gamap_saturation_cb.GetValue()
		self.gamap_src_viewcond_ctrl.Enable(p and c)
		self.gamap_out_viewcond_ctrl.Enable(p and c)
		if v != getcfg("gamap_profile") and self.Parent and \
		   hasattr(self.Parent, "profile_settings_changed"):
			self.Parent.profile_settings_changed()
		setcfg("gamap_profile", v or None)

	def gamap_perceptual_cb_handler(self, event=None):
		v = self.gamap_perceptual_cb.GetValue()
		if not v:
			self.gamap_saturation_cb.SetValue(False)
			self.gamap_saturation_cb_handler()
		if int(v) != getcfg("gamap_perceptual") and self.Parent and \
		   hasattr(self.Parent, "profile_settings_changed"):
			self.Parent.profile_settings_changed()
		setcfg("gamap_perceptual", int(v))
		self.gamap_profile_handler()

	def gamap_saturation_cb_handler(self, event=None):
		v = self.gamap_saturation_cb.GetValue()
		if v:
			self.gamap_perceptual_cb.SetValue(True)
			self.gamap_perceptual_cb_handler()
		if int(v) != getcfg("gamap_saturation") and self.Parent and \
		   hasattr(self.Parent, "profile_settings_changed"):
			self.Parent.profile_settings_changed()
		setcfg("gamap_saturation", int(v))
		self.gamap_profile_handler()

	def gamap_src_viewcond_handler(self, event=None):
		v = self.viewconds_ba[self.gamap_src_viewcond_ctrl.GetStringSelection()]
		if v != getcfg("gamap_src_viewcond") and self.Parent and \
		   hasattr(self.Parent, "profile_settings_changed"):
			self.Parent.profile_settings_changed()
		setcfg("gamap_src_viewcond", v)

	def gamap_out_viewcond_handler(self, event=None):
		v = self.viewconds_ba[self.gamap_out_viewcond_ctrl.GetStringSelection()]
		if v != getcfg("gamap_out_viewcond") and self.Parent and \
		   hasattr(self.Parent, "profile_settings_changed"):
			self.Parent.profile_settings_changed()
		setcfg("gamap_out_viewcond", v)
	
	def setup_language(self):
		"""
		Substitute translated strings for menus, controls, labels and tooltips.
		
		"""
		BaseFrame.setup_language(self)
		
		# Create the profile picker ctrl dynamically to get translated strings
		if sys.platform in ("darwin", "win32"):
			origpickerctrl = self.FindWindowByName("gamap_profile")
			hsizer = origpickerctrl.GetContainingSizer()
			self.gamap_profile = wx.FilePickerCtrl(
				self.panel, -1, "", message=lang.getstr("gamap.profile"), 
				wildcard=lang.getstr("filetype.icc") + "|*.icc;*.icm",
				name="gamap_profile")
			self.gamap_profile.PickerCtrl.Label = lang.getstr("browse")
			hsizer.Replace(origpickerctrl, self.gamap_profile)
			origpickerctrl.Destroy()
		self.Bind(wx.EVT_FILEPICKER_CHANGED, self.gamap_profile_handler, 
				   id=self.gamap_profile.GetId())
		
		for v in viewconds:
			lstr = lang.getstr("gamap.viewconds.%s" % v)
			self.viewconds_ab[v] = lstr
			self.viewconds_ba[lstr] = v
			if v not in ("pp", "pe", "pcd", "ob", "cx"):
				self.viewconds_out_ab[v] = lstr
		
		self.gamap_src_viewcond_ctrl.SetItems(
			self.viewconds_ab.values())
		self.gamap_out_viewcond_ctrl.SetItems(
			self.viewconds_out_ab.values())
	
	def update_controls(self):
		""" Update controls with values from the global configuration """
		self.gamap_profile.SetPath(getcfg("gamap_profile"))
		self.gamap_perceptual_cb.SetValue(getcfg("gamap_perceptual"))
		self.gamap_saturation_cb.SetValue(getcfg("gamap_saturation"))
		self.gamap_src_viewcond_ctrl.SetStringSelection(
			self.viewconds_ab.get(getcfg("gamap_src_viewcond"), 
			self.viewconds_ab.get(defaults["gamap_src_viewcond"])))
		self.gamap_out_viewcond_ctrl.SetStringSelection(
			self.viewconds_ab.get(getcfg("gamap_out_viewcond"), 
			self.viewconds_ab.get(defaults["gamap_out_viewcond"])))
		self.gamap_profile_handler()


class MainFrame(BaseFrame):

	""" Display calibrator main application window. """
	
	def __init__(self):		
		# Startup messages
		if verbose >= 1:
			safe_print(lang.getstr("startup"))
		if sys.platform != "darwin":
			if not autostart:
				safe_print(lang.getstr("warning.autostart_system"))
			if not autostart_home:
				safe_print(lang.getstr("warning.autostart_user"))
		
		# Check for required resource files and get pre-canned testcharts
		self.dist_testcharts = []
		self.dist_testchart_names = []
		missing = []
		for filename in resfiles:
			path, ext = (get_data_path(os.path.sep.join(filename.split("/"))), 
				os.path.splitext(filename)[1])
			if (not path or not os.path.isfile(path)):
				if ext.lower() != ".json":
					# Ignore missing language files, these are handled separate
					missing += [filename]
			elif ext.lower() == ".ti1":
				self.dist_testcharts += [path]
				self.dist_testchart_names += [os.path.basename(path)]
		if missing:
			handle_error(lang.getstr("resources.notfound.warning") + "\n" +
						 "\n".join(missing), False)
			for filename in missing:
				if filename.lower().endswith(".xrc"):
					handle_error(lang.getstr("resources.notfound.error") + 
						 "\n" + filename, False)
		
		# Create main worker instance
		self.worker = Worker(self)
		self.worker.enumerate_displays_and_ports()
		
		# Initialize GUI
		if verbose >= 1:
			safe_print(lang.getstr("initializing_gui"))
		self.res = xrc.XmlResource(get_data_path(os.path.join("xrc", 
															  "main.xrc")))
		pre = wx.PreFrame()
		self.res.LoadOnFrame(pre, None, "mainframe")
		self.PostCreate(pre)
		self.init_frame()
		self.init_defaults()
		self.init_infoframe()
		if sys.platform in ("darwin", "win32") or isexe:
			self.init_measureframe()
		self.init_menus()
		self.update_menus()
		self.init_controls()
		self.setup_language()
		BaseFrame.update_layout(self)
		self.update_displays()
		# Add the header bitmap after layout so it won't stretch the window 
		# further than necessary
		self.headerbitmap = self.panel.FindWindowByName("headerbitmap")
		self.headerbitmap.SetBitmap(getbitmap("theme/header"))
		self.calpanel.SetScrollRate(0, 20)
		self.update_comports()
		self.update_controls()
		self.SetSaneGeometry(int(getcfg("position.x")), 
							 int(getcfg("position.y")))
		if verbose >= 1:
			safe_print(lang.getstr("success"))
		
		# Check for and load default calibration
		if len(self.worker.displays):
			if getcfg("calibration.file"):
				# Load LUT curves from last used .cal file
				self.load_cal(silent=True)
			else:
				# Load LUT curves from current display profile (if any, and 
				# if it contains curves)
				self.load_display_profile_cal(None)
		
		self.init_timers()
		
		if verbose >= 1:
			safe_print(lang.getstr("ready"))
		
		self.log()
	
	def log(self):
		""" Put log buffer contents into the log window. """
		# We do this after all initialization because the log.log() function 
		# expects the window to be fully created and accessible via 
		# wx.GetApp().frame.infoframe
		logbuffer.seek(0)
		self.infoframe.log_txt.SetValue("".join(line.decode("UTF-8", 
															"replace") 
												for line in logbuffer))

	def init_defaults(self):
		""" Initialize GUI-specific defaults. """
		defaults.update({
			"position.info.x": self.GetDisplay().ClientArea[0] + 20,
			"position.info.y": self.GetDisplay().ClientArea[1] + 40,
			"position.lut_viewer.x": self.GetDisplay().ClientArea[0] + 30,
			"position.lut_viewer.y": self.GetDisplay().ClientArea[1] + 50,
			"position.progress.x": self.GetDisplay().ClientArea[0] + 20,
			"position.progress.y": self.GetDisplay().ClientArea[1] + 40,
			"position.x": self.GetDisplay().ClientArea[0] + 10,
			"position.y": self.GetDisplay().ClientArea[1] + 30
		})

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
		
		# Left side - internal enumeration, right side - commmandline
		self.whitepoint_colortemp_loci_ab = {
			0: "t",
			1: "T"
		}
		
		# Left side - commmandline, right side - internal enumeration
		self.whitepoint_colortemp_loci_ba = {
			"t": 0,
			"T": 1
		}
		
		# Left side - commmandline, right side - internal enumeration
		self.quality_ab = {
			1: "v",
			2: "l",
			3: "m",
			4: "h",
			5: "u"
		}
		
		# Left side - commmandline, right side - internal enumeration
		self.quality_ba = swap_dict_keys_values(self.quality_ab)
		
		self.testchart_defaults = config.testchart_defaults
		self.testcharts = []
		self.testchart_names = []
		
		# Left side - commmandline, right side - .cal file
		self.trc_ab = {
			"l": "L_STAR",
			"709": "REC709",
			"s": "sRGB",
			"240": "SMPTE240M"
		}
		
		# Left side - .cal file, right side - commmandline
		self.trc_ba = swap_dict_keys_values(self.trc_ab)
		
		# Left side - internal enumeration, right side - commmandline
		self.trc_types_ab = {
			0: "g",
			1: "G"
		}
		
		# Left side - commmandline, right side - internal enumeration
		self.trc_types_ba = swap_dict_keys_values(self.trc_types_ab)
		
		self.trc_presets = [
			"1.8",
			"2.0",
			"2.2",
			"2.4"
		]
		
		self.whitepoint_presets = [
			"5000.0",
			"5500.0",
			"6000.0",
			"6500.0"
		]
		
		defaults["use_separate_lut_access"] = int(
			self.worker.has_separate_lut_access() or test)

	def init_frame(self):
		"""
		Initialize the main window and its event handlers.
		
		Controls are initialized in a separate step (see init_controls).
		
		"""
		self.SetTitle("%s %s %s" % (appname, version, build))
		self.SetMaxSize((-1, -1))
		icon = get_data_path(os.path.join("theme", "icons", "16x16", appname + 
										  ".png"))
		if icon:
			self.SetIcon(wx.Icon(icon, wx.BITMAP_TYPE_PNG))
		self.Bind(wx.EVT_CLOSE, self.OnClose, self)
		self.Bind(wx.EVT_MOVE, self.OnMove, self)
		self.Bind(wx.EVT_SHOW, self.OnShow, self)
		self.Children[0].Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
		self.droptarget = FileDrop()
		self.droptarget.drophandlers = {
			".cal": self.cal_drop_handler,
			".icc": self.cal_drop_handler,
			".icm": self.cal_drop_handler,
			".ti1": self.ti1_drop_handler,
			".ti3": self.ti3_drop_handler
		}
		self.droptarget.unsupported_handler = self.drop_unsupported_handler

		# Main panel
		self.panel = self.FindWindowByName("panel")
		self.panel.SetDropTarget(self.droptarget)
		
		# Header
		# Its width also determines the initial min width of the main window
		# after SetSizeHints and Layout
		self.header = self.FindWindowByName("header")
		self.header.SetScrollRate(0, 0)
		
		# Calibration settings panel
		self.calpanel = self.FindWindowByName("calpanel")
	
	def init_timers(self):
		"""
		Setup the timers for display/instrument detection and profile name.
		
		"""
		self.plugplay_timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self.plugplay_timer_handler, 
				  self.plugplay_timer)
		self.update_profile_name_timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self.update_profile_name, 
				  self.update_profile_name_timer)

	def OnMove(self, event=None):
		# When moving, check if we are on another screen and resize if needed.
		if self.IsShownOnScreen() and not self.IsMaximized() and not \
		   self.IsIconized():
			x, y = self.GetScreenPosition()
			setcfg("position.x", x)
			setcfg("position.y", y)
		display_client_rect = self.GetDisplay().ClientArea
		if hasattr(self, "calpanel") and (not hasattr(self, 
													  "display_client_rect") or 
										  self.display_client_rect != 
										  display_client_rect):
			# We just moved to this workspace
			size = self.GetSize()
			if sys.platform not in ("darwin", "win32"):
				# Linux
				safety_margin = 45
			else:
				safety_margin = 20
			vsize = self.calpanel.GetVirtualSize()
			fullheight = size[1] - self.calpanel.GetSize()[1] + vsize[1]
			maxheight = None
			if size[1] > display_client_rect[3] - safety_margin:
				# Our full height is too tall for that workspace, adjust
				vsize = self.calpanel.GetSize()
				maxheight = vsize[1] - (size[1] - display_client_rect[3] + 
										safety_margin)
			elif not hasattr(self, "display_client_rect"):
				# Our full height fits on that workspace
				maxheight = vsize[1]
			self.display_client_rect = display_client_rect
			if maxheight:
				newheight = size[1] - self.calpanel.GetSize()[1] + maxheight
				if debug:
					safe_print("[D] Calibration settings virtual height:", 
							   vsize[1])
					safe_print("[D] Calibration settings height after adjust:", 
							   maxheight)
					safe_print("[D] Main window height after adjust:", 
							   newheight)
				wx.CallAfter(self.frame_fit, fullheight, vsize[1], maxheight, 
							 newheight)
			if event:
				event.Skip()

	def frame_fit(self, fullheight, virtualheight, height, newheight):
		"""
		Fit the main window to a new size.
		
		Used internally by OnMove to make sure the window fits into available 
		(usable, not covered by e.g. taskbars) screen space.
		
		"""
		self.Bind(wx.EVT_IDLE, self.frame_enableresize_handler)
		size = self.GetSize()
		self.Freeze()
		self.SetMaxSize((size[0], fullheight))
		self.calpanel.SetMaxSize((-1, virtualheight))
		self.calpanel.SetMinSize((-1, 64))
		self.calpanel.SetMaxSize((-1, height))
		self.calpanel.SetSize((-1, height))
		if debug:
			safe_print("[D] Main window sizer min height after adjust:", 
					   self.GetSizer().GetMinSize()[1])
			safe_print("[D] Main window sizer height after adjust:", 
					   self.GetSizer().GetSize()[1])
		self.SetMinSize((self.GetMinSize()[0], newheight))
		self.SetMaxSize((size[0], newheight))
		self.SetSize((size[0], newheight))
		self.Thaw()
		wx.CallLater(100, self.calpanel.SetMaxSize, (-1, -1))

	def frame_enableresize_handler(self, event=None):
		"""
		Enable resizing after fitting the main window to a new size.
		
		Used internally by frame_fit.
		
		"""
		# frame_fit sets a static max size and min size = size, so after
		# that operation we can no longer resize the window. This is fixed
		# here by setting another min size and no max size.
		# The CallLater logic implemented in frame_fit and here is rather
		# arcane, but needed to circumvent the issue where the size set by 
		# frame_fit is immediately scrapped under certain circumstances
		# (related to the selected window manager under Linux, for example).
		wx.CallLater(100, self.SetMinSize, (self.GetMinSize()[0], 
											self.GetSize()[1] - 
											self.calpanel.GetSize()[1] + 64))
		wx.CallLater(150, self.SetMaxSize, (-1, -1))
		self.Unbind(wx.EVT_IDLE)
		if event:
			event.Skip()

	def cal_drop_handler(self, path):
		"""
		Drag'n'drop handler for .cal files. 
		
		Settings and calibration are loaded from dropped files.
		
		"""
		if not self.worker.is_working():
			self.load_cal_handler(None, path)

	def ti1_drop_handler(self, path):
		"""
		Drag'n'drop handler for .ti1 files.
		
		Dropped files are added to the testchart chooser and selected.
		
		"""
		if not self.worker.is_working():
			self.testchart_btn_handler(None, path)

	def ti3_drop_handler(self, path):
		"""
		Drag'n'drop handler for .ti3 files.
		
		Dropped files are used to create an ICC profile.
		
		"""
		if not self.worker.is_working():
			self.create_profile_handler(None, path)

	def drop_unsupported_handler(self):
		"""
		Drag'n'drop handler for unsupported files. 
		
		Shows an error message.
		
		"""
		if not self.worker.is_working():
			files = self.droptarget._filenames
			InfoDialog(self, msg=lang.getstr("error.file_type_unsupported") +
								 "\n\n" + "\n".join(files), 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-error"))

	def init_gamapframe(self):
		"""
		Create & initialize the gamut mapping options window and its controls.
		
		"""
		self.gamapframe = GamapFrame(self)

	def init_infoframe(self):
		"""
		Create & initialize the info (log) window and its controls.
		
		"""
		self.infoframe = LogWindow(self)
		icon = get_data_path(os.path.join("theme", "icons", "16x16", appname + 
										  ".png"))
		if icon:
			self.infoframe.SetIcon(wx.Icon(icon, wx.BITMAP_TYPE_PNG))
	
	def setup_language(self):
		"""
		Substitute translated strings for menus, controls, labels and tooltips.
		
		"""
		# Set language specific defaults
		lang.update_defaults()
		
		# Translate controls and labels
		
		BaseFrame.setup_language(self)
		
		settings = [lang.getstr("settings.new")]
		for cal in self.recent_cals[1:]:
			lstr = lang.getstr(os.path.basename(cal))
			if cal == getcfg("calibration.file") and getcfg("settings.changed"):
				lstr = "* " + lstr
			settings += [lstr]
		self.calibration_file_ctrl.SetItems(settings)
		
		self.whitepoint_colortemp_loci = [
			lang.getstr("whitepoint.colortemp.locus.daylight"),
			lang.getstr("whitepoint.colortemp.locus.blackbody")
		]
		self.whitepoint_colortemp_locus_ctrl.SetItems(
			self.whitepoint_colortemp_loci)
		
		self.trc_types = [
			lang.getstr("trc.type.relative"),
			lang.getstr("trc.type.absolute")
		]
		self.trc_type_ctrl.SetItems(self.trc_types)

		self.update_profile_type_ctrl()

		self.default_testchart_names = []
		for testcharts in self.testchart_defaults.values():
			for chart in testcharts.values():
				chart = lang.getstr(chart)
				if not chart in self.default_testchart_names:
					self.default_testchart_names += [chart]
		
		self.profile_name_info_btn.SetToolTipString(
			wrap(self.profile_name_info(), 72))
	
	def update_profile_type_ctrl(self):
		self.profile_types = [
			lang.getstr("profile.type.lut.lab"),
			lang.getstr("profile.type.shaper_matrix"),
			lang.getstr("profile.type.single_shaper_matrix"),
			lang.getstr("profile.type.gamma_matrix"),
			lang.getstr("profile.type.single_gamma_matrix")
		]
		self.profile_types_ab = {}
		profile_types_index = 0
		if self.worker.argyll_version[0:3] > [1, 1, 0] or (
		   self.worker.argyll_version[0:3] == [1, 1, 0] 
		   and not "Beta" in self.worker.argyll_version_string 
		   and not "RC1" in self.worker.argyll_version_string 
		   and not "RC2" in self.worker.argyll_version_string 
		   and not "RC3" in self.worker.argyll_version_string):
			# Argyll 1.1.0_RC3 had a bug when using -aX
			# which was fixed in 1.1.0_RC4
			self.profile_types.insert(profile_types_index, 
									  lang.getstr("profile.type.lut_matrix.xyz"))
			self.profile_types_ab[profile_types_index] = "X"  # XYZ LUT + accurate matrix
			profile_types_index += 1
		if self.worker.argyll_version[0:3] > [1, 1, 0] or (
		   self.worker.argyll_version[0:3] == [1, 1, 0] 
		   and not "Beta" in self.worker.argyll_version_string
		   and not "RC1" in self.worker.argyll_version_string
		   and not "RC2" in self.worker.argyll_version_string):
			# Windows wants matrix tags in XYZ LUT profiles,
			# which is satisfied with Argyll >= 1.1.0_RC3
			self.profile_types.insert(profile_types_index, 
									  lang.getstr("profile.type.lut_rg_swapped_matrix.xyz"))
			self.profile_types_ab[profile_types_index] = "x"  # XYZ LUT + dummy matrix (R <-> G swapped)
			profile_types_index += 1
		elif sys.platform != "win32":
			self.profile_types.insert(profile_types_index, 
									  lang.getstr("profile.type.lut.xyz"))
			self.profile_types_ab[profile_types_index] = "x"  # XYZ LUT
			profile_types_index += 1
		self.profile_type_ctrl.SetItems(self.profile_types)
		self.profile_types_ab[profile_types_index] = "l"
		self.profile_types_ab[profile_types_index + 1] = "s"
		self.profile_types_ab[profile_types_index + 2] = "S"
		self.profile_types_ab[profile_types_index + 3] = "g"
		self.profile_types_ab[profile_types_index + 4] = "G"
		self.profile_types_ba = swap_dict_keys_values(self.profile_types_ab)

	def init_measureframe(self):
		""" Create & initialize the measurement window and its controls. """
		self.measureframe = MeasureFrame(self, -1)

	def init_menus(self):
		""" Initialize the menus and menuitem event handlers. """
		res = xrc.XmlResource(get_data_path(os.path.join("xrc", 
														 "mainmenu.xrc")))
		self.menubar = res.LoadMenuBar("menu")  ##self.GetMenuBar()
		
		file_ = self.menubar.GetMenu(self.menubar.FindMenu("menu.file"))
		menuitem = file_.FindItemById(file_.FindItem("calibration.load"))
		self.Bind(wx.EVT_MENU, self.load_cal_handler, menuitem)
		menuitem = file_.FindItemById(file_.FindItem("testchart.set"))
		self.Bind(wx.EVT_MENU, self.testchart_btn_handler, menuitem)
		menuitem = file_.FindItemById(file_.FindItem("testchart.edit"))
		self.Bind(wx.EVT_MENU, self.create_testchart_btn_handler, menuitem)
		menuitem = file_.FindItemById(file_.FindItem("profile.set_save_path"))
		self.Bind(wx.EVT_MENU, self.profile_save_path_btn_handler, menuitem)
		if sys.platform != "darwin":
			file_.AppendSeparator()
		self.menuitem_prefs = file_.Append(
			-1, "&" + "menuitem.set_argyll_bin")
		self.Bind(wx.EVT_MENU, self.set_argyll_bin_handler, self.menuitem_prefs)
		if sys.platform != "darwin":
			file_.AppendSeparator()
		self.menuitem_quit = file_.Append(-1, "&menuitem.quit\tCtrl+Q")
		self.Bind(wx.EVT_MENU, self.OnClose, self.menuitem_quit)

		options = self.menubar.GetMenu(self.menubar.FindMenu("menu.options"))
		self.menuitem_create_profile = options.FindItemById(
			options.FindItem("create_profile"))
		self.Bind(wx.EVT_MENU, self.create_profile_handler, 
				  self.menuitem_create_profile)
		self.menuitem_install_display_profile = options.FindItemById(
			options.FindItem("install_display_profile"))
		self.Bind(wx.EVT_MENU, self.install_profile_handler, 
				  self.menuitem_install_display_profile)
		self.menuitem_load_lut_from_cal_or_profile = options.FindItemById(
			options.FindItem("calibration.load_from_cal_or_profile"))
		self.Bind(wx.EVT_MENU, self.load_profile_cal_handler, 
				  self.menuitem_load_lut_from_cal_or_profile)
		self.menuitem_load_lut_from_display_profile = options.FindItemById(
			options.FindItem("calibration.load_from_display_profile"))
		self.Bind(wx.EVT_MENU, self.load_display_profile_cal, 
				  self.menuitem_load_lut_from_display_profile)
		self.menuitem_lut_reset = options.FindItemById(
			options.FindItem("calibration.reset"))
		self.Bind(wx.EVT_MENU, self.reset_cal, self.menuitem_lut_reset)
		menuitem = options.FindItemById(
			options.FindItem("detect_displays_and_ports"))
		self.Bind(wx.EVT_MENU, self.check_update_controls, menuitem)
		self.menuitem_use_separate_lut_access = options.FindItemById(
			options.FindItem("use_separate_lut_access"))
		self.Bind(wx.EVT_MENU, self.use_separate_lut_access_handler, 
				  self.menuitem_use_separate_lut_access)
		menuitem = options.FindItemById(options.FindItem("restore_defaults"))
		self.Bind(wx.EVT_MENU, self.restore_defaults_handler, menuitem)
		
		tools = self.menubar.GetMenu(self.menubar.FindMenu("menu.tools"))
		self.menuitem_report_uncalibrated = tools.FindItemById(
			tools.FindItem("report.uncalibrated"))
		self.Bind(wx.EVT_MENU, self.report_uncalibrated_handler, 
			self.menuitem_report_uncalibrated)
		self.menuitem_report_calibrated = tools.FindItemById(
			tools.FindItem("report.calibrated"))
		self.Bind(wx.EVT_MENU, self.report_calibrated_handler, 
				  self.menuitem_report_calibrated)
		self.menuitem_calibration_verify = tools.FindItemById(
			tools.FindItem("calibration.verify"))
		self.Bind(wx.EVT_MENU, self.verify_calibration_handler, 
				  self.menuitem_calibration_verify)
		self.menuitem_profile_verify = tools.FindItemById(
			tools.FindItem("profile.verify"))
		self.Bind(wx.EVT_MENU, self.verify_profile_handler, 
				  self.menuitem_profile_verify)
		menuitem = tools.FindItemById(tools.FindItem("enable_spyder2"))
		self.Bind(wx.EVT_MENU, self.enable_spyder2_handler, menuitem)
		self.menuitem_show_lut = tools.FindItemById(
			tools.FindItem("calibration.show_lut"))
		self.Bind(wx.EVT_MENU, self.init_lut_viewer, self.menuitem_show_lut)
		self.menuitem_show_actual_lut = tools.FindItemById(
			tools.FindItem("calibration.show_actual_lut"))
		self.Bind(wx.EVT_MENU, self.lut_viewer_show_actual_lut_handler, 
							   self.menuitem_show_actual_lut)
		menuitem = tools.FindItemById(tools.FindItem("infoframe.toggle"))
		self.Bind(wx.EVT_MENU, self.infoframe_toggle_handler, menuitem)
		self.menuitem_log_autoshow = tools.FindItemById(
			tools.FindItem("log.autoshow"))
		self.Bind(wx.EVT_MENU, self.infoframe_autoshow_handler, 
				  self.menuitem_log_autoshow)

		languages = self.menubar.GetMenu(self.menubar.FindMenu("menu.language"))
		llist = [(lang.ldict[lcode].get("language", ""), lcode) for lcode in 
				 lang.ldict]
		llist.sort()
		for lstr, lcode in llist:
			menuitem = languages.Append(-1, "&" + lstr, kind=wx.ITEM_RADIO)
			menuitem.SetBitmap(
				flagart.catalog[lcode.upper().replace("EN", "US")].getBitmap())
			if lang.getcode() == lcode:
				menuitem.Check()
				font = menuitem.Font
				font.SetWeight(wx.BOLD)
				menuitem.SetFont(font)
			# Map numerical event id to language string
			lang.ldict[lcode].menuitem_id = menuitem.GetId()
			self.Bind(wx.EVT_MENU, self.set_language_handler, menuitem)

		help = self.menubar.GetMenu(self.menubar.FindMenu("menu.help"))
		self.menuitem_about = help.FindItemById(help.FindItem("menu.about"))
		self.Bind(wx.EVT_MENU, self.aboutdialog_handler, self.menuitem_about)
		self.menuitem_readme = help.FindItemById(help.FindItem("readme"))
		self.menuitem_readme.Enable(isinstance(get_data_path("README.html"), 
											   basestring))
		self.Bind(wx.EVT_MENU, self.readme_handler, self.menuitem_readme)
		self.menuitem_license = help.FindItemById(help.FindItem("license"))
		self.menuitem_license.Enable(isinstance(get_data_path("LICENSE.txt"), 
												basestring) or 
									 isinstance(get_data_path("LICENSE.txt.gz"), 
												basestring))
		self.Bind(wx.EVT_MENU, self.license_handler, self.menuitem_license)
		menuitem = help.FindItemById(help.FindItem("help_support"))
		self.Bind(wx.EVT_MENU, self.help_support_handler, menuitem)
		menuitem = help.FindItemById(help.FindItem("bug_report"))
		self.Bind(wx.EVT_MENU, self.bug_report_handler, menuitem)
		menuitem = help.FindItemById(help.FindItem("check_update"))
		self.Bind(wx.EVT_MENU, self.app_update_check_handler, menuitem)
		
		if sys.platform == "darwin":
			wx.GetApp().SetMacAboutMenuItemId(self.menuitem_about.GetId())
			wx.GetApp().SetMacPreferencesMenuItemId(self.menuitem_prefs.GetId())
			wx.GetApp().SetMacExitMenuItemId(self.menuitem_quit.GetId())
			wx.GetApp().SetMacHelpMenuTitleName(lang.getstr("menu.help"))
	
	def update_menus(self):
		"""
		Enable/disable menu items based on available Argyll functionality.
		
		"""
		self.menuitem_create_profile.Enable(bool(self.worker.displays))
		self.menuitem_install_display_profile.Enable(bool(self.worker.displays))
		self.menuitem_load_lut_from_cal_or_profile.Enable(
			bool(self.worker.displays))
		self.menuitem_load_lut_from_display_profile.Enable(
			bool(self.worker.displays))
		self.menuitem_use_separate_lut_access.Check(bool(getcfg("use_separate_lut_access")))
		self.menuitem_show_lut.Enable(bool(LUTFrame))
		self.menuitem_show_actual_lut.Enable(bool(LUTFrame) and 
											 self.worker.argyll_version >= [1, 1, 0] and 
											 not "Beta" in self.worker.argyll_version_string)
		self.menuitem_show_actual_lut.Check(bool(getcfg("lut_viewer.show_actual_lut")))
		self.menuitem_lut_reset.Enable(bool(self.worker.displays))
		self.menuitem_report_calibrated.Enable(bool(self.worker.displays) and 
						bool(self.worker.instruments))
		self.menuitem_report_uncalibrated.Enable(bool(self.worker.displays) and 
						bool(self.worker.instruments))
		self.menuitem_calibration_verify.Enable(bool(self.worker.displays) and 
						bool(self.worker.instruments))
		self.menuitem_profile_verify.Enable(bool(self.worker.displays) and 
						bool(self.worker.instruments))
		self.menuitem_log_autoshow.Check(bool(getcfg("log.autoshow")))

	def init_controls(self):
		"""
		Initialize the main window controls and their event handlers.
		
		"""
		
		self.set_child_ctrls_as_attrs(self)

		# Settings file controls
		# ======================
		
		# Settings file dropdown
		self.Bind(wx.EVT_COMBOBOX, self.calibration_file_ctrl_handler, 
				  id=self.calibration_file_ctrl.GetId())
		self.Bind(wx.EVT_BUTTON, self.load_cal_handler, 
				  id=self.calibration_file_btn.GetId())
		self.delete_calibration_btn.SetBitmapDisabled(geticon(16, "empty"))
		self.Bind(wx.EVT_BUTTON, self.delete_calibration_handler, 
				  id=self.delete_calibration_btn.GetId())
		self.install_profile_btn.SetBitmapDisabled(geticon(16, "empty"))
		self.Bind(wx.EVT_BUTTON, self.install_cal_handler, 
				  id=self.install_profile_btn.GetId())

		# Update calibration checkbox
		self.Bind(wx.EVT_CHECKBOX, self.calibration_update_ctrl_handler, 
				  id=self.calibration_update_cb.GetId())

		# Update corresponding profile checkbox
		self.Bind(wx.EVT_CHECKBOX, self.profile_update_ctrl_handler, 
				  id=self.profile_update_cb.GetId())

		# Display
		self.Bind(wx.EVT_COMBOBOX, self.display_ctrl_handler, 
				  id=self.display_ctrl.GetId())
		self.Bind(wx.EVT_COMBOBOX, self.display_lut_ctrl_handler, 
				  id=self.display_lut_ctrl.GetId())
		self.Bind(wx.EVT_BUTTON, self.display_lut_link_ctrl_handler, 
				  id=self.display_lut_link_ctrl.GetId())

		# Instrument
		self.Bind(wx.EVT_COMBOBOX, self.comport_ctrl_handler, 
				  id=self.comport_ctrl.GetId())
		self.Bind(wx.EVT_COMBOBOX, self.measurement_mode_ctrl_handler, 
				  id=self.measurement_mode_ctrl.GetId())

		# Calibration settings
		# ====================

		# Whitepoint
		self.Bind(wx.EVT_RADIOBUTTON, self.whitepoint_ctrl_handler, 
				  id=self.whitepoint_native_rb.GetId())
		self.Bind(wx.EVT_RADIOBUTTON, self.whitepoint_ctrl_handler, 
				  id=self.whitepoint_colortemp_rb.GetId())
		self.Bind(wx.EVT_COMBOBOX, self.whitepoint_ctrl_handler, 
				  id=self.whitepoint_colortemp_textctrl.GetId())
		self.whitepoint_colortemp_textctrl.SetItems(self.whitepoint_presets)
		self.whitepoint_colortemp_textctrl.Bind(
			wx.EVT_KILL_FOCUS, self.whitepoint_ctrl_handler)
		self.Bind(wx.EVT_COMBOBOX, self.whitepoint_colortemp_locus_ctrl_handler, 
				  id=self.whitepoint_colortemp_locus_ctrl.GetId())
		self.Bind(wx.EVT_RADIOBUTTON, self.whitepoint_ctrl_handler, 
				  id=self.whitepoint_xy_rb.GetId())
		self.whitepoint_x_textctrl.Bind(wx.EVT_KILL_FOCUS, 
										self.whitepoint_ctrl_handler)
		self.whitepoint_y_textctrl.Bind(wx.EVT_KILL_FOCUS, 
										self.whitepoint_ctrl_handler)
		self.Bind(wx.EVT_BUTTON, self.ambient_measure_handler, 
				  id=self.whitepoint_measure_btn.GetId())

		# White luminance
		self.Bind(wx.EVT_RADIOBUTTON, self.luminance_ctrl_handler, 
				  id=self.luminance_max_rb.GetId())
		self.Bind(wx.EVT_RADIOBUTTON, self.luminance_ctrl_handler, 
				  id=self.luminance_cdm2_rb.GetId())
		self.luminance_textctrl.Bind(wx.EVT_KILL_FOCUS, 
									 self.luminance_ctrl_handler)

		# Black luminance
		self.Bind(wx.EVT_RADIOBUTTON, self.black_luminance_ctrl_handler, 
				  id=self.black_luminance_min_rb.GetId())
		self.Bind(wx.EVT_RADIOBUTTON, self.black_luminance_ctrl_handler, 
				  id=self.black_luminance_cdm2_rb.GetId())
		self.black_luminance_textctrl.Bind(wx.EVT_KILL_FOCUS, 
										   self.black_luminance_ctrl_handler)

		# Tonal response curve (TRC)
		self.Bind(wx.EVT_RADIOBUTTON, self.trc_ctrl_handler, 
				  id=self.trc_g_rb.GetId())
		self.trc_textctrl.SetItems(self.trc_presets)
		self.trc_textctrl.SetValue(str(defaults["gamma"]))
		self.Bind(wx.EVT_COMBOBOX, self.trc_ctrl_handler, 
				  id=self.trc_textctrl.GetId())
		self.trc_textctrl.Bind(wx.EVT_KILL_FOCUS, self.trc_ctrl_handler)
		self.Bind(wx.EVT_COMBOBOX, self.trc_type_ctrl_handler, 
				  id=self.trc_type_ctrl.GetId())
		self.Bind(wx.EVT_RADIOBUTTON, self.trc_ctrl_handler, 
				  id=self.trc_l_rb.GetId())
		self.Bind(wx.EVT_RADIOBUTTON, self.trc_ctrl_handler, 
				  id=self.trc_rec709_rb.GetId())
		self.Bind(wx.EVT_RADIOBUTTON, self.trc_ctrl_handler, 
				  id=self.trc_smpte240m_rb.GetId())
		self.Bind(wx.EVT_RADIOBUTTON, self.trc_ctrl_handler, 
				  id=self.trc_srgb_rb.GetId())

		# Viewing condition adjustment for ambient in Lux
		self.Bind(wx.EVT_CHECKBOX, self.ambient_viewcond_adjust_ctrl_handler, 
				  id=self.ambient_viewcond_adjust_cb.GetId())
		self.ambient_viewcond_adjust_textctrl.Bind(
			wx.EVT_KILL_FOCUS, self.ambient_viewcond_adjust_ctrl_handler)
		self.ambient_viewcond_adjust_info.SetBitmapDisabled(
			geticon(16, "empty"))
		self.Bind(wx.EVT_BUTTON, self.ambient_viewcond_adjust_info_handler, 
				  id=self.ambient_viewcond_adjust_info.GetId())
		self.Bind(wx.EVT_BUTTON, self.ambient_measure_handler,
				  id=self.ambient_measure_btn.GetId())

		# Black level output offset
		self.Bind(wx.EVT_SLIDER, self.black_output_offset_ctrl_handler, 
				  id=self.black_output_offset_ctrl.GetId())
		self.Bind(wx.EVT_TEXT, self.black_output_offset_ctrl_handler, 
				  id=self.black_output_offset_intctrl.GetId())

		# Black point hue correction
		self.Bind(wx.EVT_SLIDER, self.black_point_correction_ctrl_handler, 
				  id=self.black_point_correction_ctrl.GetId())
		self.Bind(wx.EVT_TEXT, self.black_point_correction_ctrl_handler, 
				  id=self.black_point_correction_intctrl.GetId())

		# Black point correction rate
		self.Bind(wx.EVT_SLIDER, self.black_point_rate_ctrl_handler, 
				  id=self.black_point_rate_ctrl.GetId())
		self.Bind(wx.EVT_TEXT, self.black_point_rate_ctrl_handler, 
				  id=self.black_point_rate_intctrl.GetId())

		# Calibration quality
		self.Bind(wx.EVT_SLIDER, self.calibration_quality_ctrl_handler, 
				  id=self.calibration_quality_ctrl.GetId())

		# Interactive display adjustment
		self.Bind(wx.EVT_CHECKBOX, 
				  self.interactive_display_adjustment_ctrl_handler, 
				  id=self.interactive_display_adjustment_cb.GetId())

		# Profiling settings
		# ==================

		# Testchart file
		self.Bind(wx.EVT_COMBOBOX, self.testchart_ctrl_handler, 
				  id=self.testchart_ctrl.GetId())
		self.testchart_btn.SetBitmapDisabled(geticon(16, "empty"))
		self.Bind(wx.EVT_BUTTON, self.testchart_btn_handler, 
				  id=self.testchart_btn.GetId())
		self.create_testchart_btn.SetBitmapDisabled(geticon(16, "empty"))
		self.Bind(wx.EVT_BUTTON, self.create_testchart_btn_handler, 
				  id=self.create_testchart_btn.GetId())

		# Profile quality
		self.Bind(wx.EVT_SLIDER, self.profile_quality_ctrl_handler, 
				  id=self.profile_quality_ctrl.GetId())

		# Profile type
		self.Bind(wx.EVT_COMBOBOX, self.profile_type_ctrl_handler, 
				  id=self.profile_type_ctrl.GetId())

		# Advanced (gamut mapping)
		self.Bind(wx.EVT_BUTTON, self.gamap_btn_handler, 
				  id=self.gamap_btn.GetId())

		# Profile name
		self.Bind(wx.EVT_TEXT, self.profile_name_ctrl_handler, 
				  id=self.profile_name_textctrl.GetId())
		self.profile_name_info_btn.SetBitmapDisabled(geticon(16, "empty"))
		self.Bind(wx.EVT_BUTTON, self.profile_name_info_btn_handler, 
				  id=self.profile_name_info_btn.GetId())
		self.profile_save_path_btn.SetBitmapDisabled(geticon(16, "empty"))
		self.Bind(wx.EVT_BUTTON, self.profile_save_path_btn_handler, 
				  id=self.profile_save_path_btn.GetId())

		# Main buttons
		# ============
		
		self.Bind(wx.EVT_BUTTON, self.calibrate_btn_handler, 
				  id=self.calibrate_btn.GetId())
		self.Bind(wx.EVT_BUTTON, self.calibrate_and_profile_btn_handler, 
				  id=self.calibrate_and_profile_btn.GetId())
		self.Bind(wx.EVT_BUTTON, self.profile_btn_handler, 
				  id=self.profile_btn.GetId())

	def set_language_handler(self, event):
		"""
		Set a new language globally and on-the-fly.
		
		"""
		##menubar = self.GetMenuBar()
		for lcode in lang.ldict:
			if lang.ldict[lcode].menuitem_id == event.GetId():
				# Get the previously marked menu item
				menuitem = self.menubar.FindItemById(
					lang.ldict[lang.getcode()].menuitem_id)
				if hasattr(self, "tcframe"):
					if not self.tcframe.tc_close_handler():
						# Do not change language, mark previous menu item
						menuitem.Check()
						return
					self.tcframe.Destroy()
					del self.tcframe
				# Set the previously marked menu item's font weight to normal
				font = menuitem.Font
				font.SetWeight(wx.NORMAL)
				menuitem.SetFont(font)
				# Set the currently marked menu item's font weight to bold
				menuitem = self.menubar.FindItemById(lang.ldict[lcode].menuitem_id)
				font = menuitem.Font
				font.SetWeight(wx.BOLD)
				menuitem.SetFont(font)
				setcfg("lang", lcode)
				writecfg()
				self.panel.Freeze()
				self.setup_language()
				if hasattr(self, "gamapframe"):
					self.gamapframe.panel.Freeze()
					self.gamapframe.setup_language()
					self.gamapframe.update_layout()
					self.gamapframe.panel.Thaw()
				self.update_controls()
				self.update_displays()
				self.set_testcharts()
				self.update_layout()
				self.panel.Thaw()
				if hasattr(self, "aboutdialog"):
					self.aboutdialog.Destroy()
					del self.aboutdialog
				self.infoframe.Destroy()
				self.init_infoframe()
				self.log()
				if sys.platform in ("darwin", "win32") or isexe:
					self.measureframe.Destroy()
					self.init_measureframe()
				if hasattr(self, "lut_viewer"):
					self.lut_viewer.Destroy()
					del self.lut_viewer
				if hasattr(self, "profile_name_tooltip_window"):
					self.profile_name_tooltip_window.Destroy()
					del self.profile_name_tooltip_window
				break
	
	def update_layout(self):
		""" Update main window layout. """
		self.calpanel.Layout()
		self.panel.Layout()

	def restore_defaults_handler(self, event=None, include=(), exclude=()):
		if event:
			dlg = ConfirmDialog(self, 
								msg=lang.getstr("app.confirm_restore_defaults"), 
								ok=lang.getstr("ok"), 
								cancel=lang.getstr("cancel"), 
								bitmap=getbitmap(
									"theme/icons/32x32/dialog-warning"))
			result = dlg.ShowModal()
			dlg.Destroy()
			if result != wx.ID_OK: return
		skip = [
			"argyll.dir",
			"calibration.black_point_rate.enabled",
			"comport.number",
			"display.number",
			"display_lut.link",
			"display_lut.number",
			"gamap_profile",
			"gamma",
			"lang",
			"last_cal_path",
			"last_cal_or_icc_path",
			"last_filedialog_path",
			"last_icc_path",
			"last_ti1_path",
			"last_ti3_path",
			"measurement_mode",
			"measurement_mode.adaptive",
			"measurement_mode.highres",
			"measurement_mode.projector",
			"profile.name",
			"profile.save_path",
			"position.x",
			"position.y",
			"position.info.x",
			"position.info.y",
			"position.lut_viewer.x",
			"position.lut_viewer.y",
			"position.progress.x",
			"position.progress.y",
			"position.tcgen.x",
			"position.tcgen.y",
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
				if (len(include) == 0 or False in [name.find(item) < 0 for 
												   item in include]) and \
				   (len(exclude) == 0 or not (False in [name.find(item) < 0 for 
														item in exclude])):
					if verbose >= 3:
						safe_print("Restoring %s to %s" % (name, 
														   defaults[name]))
					setcfg(name, defaults[name])
		for name in override:
			if (len(include) == 0 or False in [name.find(item) < 0 for item in 
											   include]) and \
			   (len(exclude) == 0 or not (False in [name.find(item) < 0 for 
													item in exclude])):
				setcfg(name, override[name])
		if event:
			writecfg()
			self.update_displays()
			self.update_controls()
			if hasattr(self, "tcframe"):
				self.tcframe.tc_update_controls()

	def cal_changed(self, setchanged=True):
		"""
		Called internally when calibration settings controls are changed.
		
		Exceptions are the calibration quality and interactive display
		adjustment controls, which do not cause a 'calibration changed' event.
		
		"""
		if not self.updatingctrls:
			# update_controls which is called from cal_changed might cause a 
			# another cal_changed call, in which case we can skip it
			if debug:
				safe_print("[D] cal_changed")
			if setchanged:
				setcfg("settings.changed", 1)
			self.worker.options_dispcal = []
			if getcfg("calibration.file"):
				setcfg("calibration.file", None)
				# Load LUT curves from current display profile (if any, and if 
				# it contains curves)
				self.load_display_profile_cal(None)
			self.calibration_file_ctrl.SetStringSelection(
				lang.getstr("settings.new"))
			self.calibration_file_ctrl.SetToolTip(None)
			self.delete_calibration_btn.Disable()
			self.install_profile_btn.Disable()
			do_update_controls = self.calibration_update_cb.GetValue() or \
								 self.profile_update_cb.GetValue()
			self.calibration_update_cb.SetValue(False)
			setcfg("calibration.update", 0)
			self.calibration_update_cb.Disable()
			self.profile_update_cb.SetValue(False)
			setcfg("profile.update", 0)
			self.profile_update_cb.Disable()
			if do_update_controls:
				self.update_controls()
			self.settings_discard_changes(keep_changed_state=True)

	def update_displays(self):
		""" Update the display selector controls. """
		self.panel.Freeze()
		self.displays = []
		for item in self.worker.displays:
			self.displays += [item.replace("[PRIMARY]", 
										   lang.getstr("display.primary"))]
		setcfg("displays", os.pathsep.join(self.worker.displays))
		self.display_ctrl.SetItems(self.displays)
		self.get_set_display()
		self.display_ctrl.Enable(len(self.worker.displays) > 1)
		display_lut_sizer = self.display_ctrl.GetContainingSizer()
		display_sizer = self.display_lut_link_ctrl.GetContainingSizer()
		comport_sizer = self.comport_ctrl.GetContainingSizer()
		use_lut_ctrl = self.worker.has_separate_lut_access() or \
					   bool(getcfg("use_separate_lut_access"))
		menubar = self.GetMenuBar()
		options = menubar.GetMenu(menubar.FindMenu(lang.getstr("menu.options")))
		menuitem = options.FindItemById(
			options.FindItem(lang.getstr("use_separate_lut_access")))
		menuitem.Check(use_lut_ctrl)
		if use_lut_ctrl:
			self.display_lut_ctrl.Clear()
			for i, disp in enumerate(self.displays):
				if self.worker.lut_access[i]:
					self.display_lut_ctrl.Append(disp)
			display_lut_no = min(len(self.displays), 
								 getcfg("display_lut.number")) - 1
			if display_lut_no > -1 and not self.worker.lut_access[display_lut_no]:
				for display_lut_no, disp in enumerate(self.worker.lut_access):
					if disp:
						break
			self.display_lut_ctrl.SetSelection(display_lut_no)
			self.display_lut_link_ctrl_handler(CustomEvent(
				wx.EVT_BUTTON.evtType[0], self.display_lut_link_ctrl), 
				bool(int(getcfg("display_lut.link"))))
			comport_sizer.SetCols(1)
			comport_sizer.SetRows(2)
		else:
			comport_sizer.SetCols(2)
			comport_sizer.SetRows(1)
			setcfg("display_lut.link", 1)
		display_lut_sizer.Show(self.display_label, use_lut_ctrl)
		display_lut_sizer.Show(self.display_lut_label, use_lut_ctrl)
		display_lut_sizer.Show(self.display_lut_ctrl, use_lut_ctrl)
		display_sizer.Show(self.display_lut_link_ctrl, use_lut_ctrl)
		self.panel.Layout()
		self.panel.Thaw()

	def update_comports(self):
		""" Update the comport selector control. """
		self.comport_ctrl.Freeze()
		self.comport_ctrl.SetItems(self.worker.instruments)
		self.comport_ctrl.SetSelection(
			min(max(0, len(self.worker.instruments) - 1), 
				max(0, int(getcfg("comport.number")) - 1)))
		self.comport_ctrl.Enable(len(self.worker.instruments) > 1)
		self.comport_ctrl.Thaw()
		self.comport_ctrl_handler()
	
	def update_measurement_modes(self):
		""" Update the measurement mode control. """
		instrument_type = self.get_instrument_type()
		measurement_mode = getcfg("measurement_mode")
		if self.get_instrument_type() == "spect":
			measurement_mode = strtr(measurement_mode, {"c": "", "l": ""})
		measurement_modes = dict({instrument_type: ["CRT", "LCD"] if 
												   instrument_type == "color" 
												   else [lang.getstr("default")]})
		measurement_modes_ab = dict({instrument_type: ["c", "l"] if 
													  instrument_type == "color" 
													  else [None]})
		instrument_features = self.worker.get_instrument_features()
		if instrument_features.get("projector_mode") and \
		   self.worker.argyll_version >= [1, 1, 0]:
			# Projector mode introduced in Argyll 1.1.0 Beta
			if instrument_type == "spect":
				measurement_modes[instrument_type] += [lang.getstr("projector")]
				measurement_modes_ab[instrument_type] += ["p"]
			else:
				measurement_modes[instrument_type] += [
					"CRT-" + lang.getstr("projector"),
					"LCD-" + lang.getstr("projector")
				]
				measurement_modes_ab[instrument_type] += ["cp"]
				measurement_modes_ab[instrument_type] += ["lp"]
			if getcfg("measurement_mode.projector",):
				measurement_mode += "p"
		if instrument_features.get("adaptive_mode") and (
		   self.worker.argyll_version[0:3] > [1, 1, 0] or (
		   self.worker.argyll_version[0:3] == [1, 1, 0] and
		   not "Beta" in self.worker.argyll_version_string and
		   not "RC1" in self.worker.argyll_version_string and
		   not "RC2" in self.worker.argyll_version_string)):
			# Adaptive mode introduced in Argyll 1.1.0 RC3
			for key in iter(measurement_modes):
				instrument_modes = list(measurement_modes[key])
				for i, mode in reversed(zip(xrange(0, len(instrument_modes)), 
										    instrument_modes)):
					if mode == lang.getstr("default"):
						mode = lang.getstr("measurement_mode.adaptive")
					else:
						mode = "%s %s" % (mode,
										  lang.getstr("measurement_mode.adaptive"))
					measurement_modes[key].insert(i + 1, mode)
					modesig = measurement_modes_ab[key][i]
					measurement_modes_ab[key].insert(i + 1, (modesig or "") + "V")
			if getcfg("measurement_mode.adaptive"):
				measurement_mode += "V"
		if instrument_features.get("highres_mode"):
			for key in iter(measurement_modes):
				instrument_modes = list(measurement_modes[key])
				for i, mode in reversed(zip(xrange(0, len(instrument_modes)), 
											instrument_modes)):
					if mode == lang.getstr("default"):
						mode = lang.getstr("measurement_mode.highres")
					else:
						mode = "%s %s" % (mode,
										  lang.getstr("measurement_mode.highres"))
					measurement_modes[key].insert(i + 1, mode)
					modesig = measurement_modes_ab[key][i]
					measurement_modes_ab[key].insert(i + 1, (modesig or "") + "H")
			if getcfg("measurement_mode.highres"):
				measurement_mode += "H"
		self.measurement_modes_ab = dict(zip(measurement_modes_ab.keys(), 
											 [dict(zip(range(len(measurement_modes_ab[key])), 
													   measurement_modes_ab[key])) 
													   for key in measurement_modes_ab]))
		self.measurement_modes_ba = dict(zip(measurement_modes_ab.keys(), 
											 [swap_dict_keys_values(self.measurement_modes_ab[key]) 
											  for key in measurement_modes_ab]))
		self.measurement_mode_ctrl.Freeze()
		self.measurement_mode_ctrl.SetItems(measurement_modes[instrument_type])
		self.measurement_mode_ctrl.SetSelection(
			min(self.measurement_modes_ba[instrument_type].get(measurement_mode, 
															   0), 
				len(measurement_modes[instrument_type]) - 1))
		self.measurement_mode_ctrl.Enable(
			bool(self.worker.instruments) and 
			len(measurement_modes[instrument_type]) > 1)
		self.measurement_mode_ctrl.Thaw()

	def update_main_controls(self):
		""" Enable/disable the calibrate and profile buttons 
		based on available Argyll functionality. """
		self.panel.Freeze()
		
		update_cal = self.calibration_update_cb.GetValue()
		enable_cal = not(update_cal)

		self.measurement_mode_ctrl.Enable(
			enable_cal and bool(self.worker.instruments) and 
			len(self.measurement_mode_ctrl.GetItems()) > 1)

		update_profile = self.profile_update_cb.GetValue()
		enable_profile = not(update_profile)

		self.whitepoint_measure_btn.Enable(bool(self.worker.instruments) and
										   enable_cal)
		self.ambient_measure_btn.Enable(bool(self.worker.instruments) and
										enable_cal)

		self.calibrate_btn.Enable(bool(self.worker.displays) and 
								  True in self.worker.lut_access and 
								  bool(self.worker.instruments))
		self.calibrate_and_profile_btn.Enable(enable_profile and 
											  bool(self.worker.displays) and 
											  True in self.worker.lut_access and 
											  bool(self.worker.instruments))
		self.profile_btn.Enable(enable_profile and not update_cal and 
								bool(self.worker.displays) and 
								bool(self.worker.instruments))
		
		self.panel.Thaw()

	def update_controls(self, update_profile_name=True, silent=False):
		""" Update all controls based on global configuration 
		and available Argyll functionality. """
		self.updatingctrls = True
		
		self.panel.Freeze()
		
		cal = getcfg("calibration.file")
		
		if cal:
			result = check_file_isfile(cal, silent=silent)
			if isinstance(result, Exception) and not silent:
				show_result_dialog(result, self)
		else:
			result = False
		if not isinstance(result, Exception) and result:
			filename, ext = os.path.splitext(cal)
			if not cal in self.recent_cals:
				self.recent_cals.append(cal)
				recent_cals = []
				for recent_cal in self.recent_cals:
					if recent_cal not in self.presets:
						recent_cals += [recent_cal]
				setcfg("recent_cals", os.pathsep.join(recent_cals))
				self.calibration_file_ctrl.Append(
					lang.getstr(os.path.basename(cal)))
			# The case-sensitive index could fail because of 
			# case insensitive file systems, e.g. if the 
			# stored filename string is 
			# "C:\Users\Name\AppData\dispcalGUI\storage\MyFile"
			# but the actual filename is 
			# "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
			# (maybe because the user renamed the file)
			idx = index_fallback_ignorecase(self.recent_cals, cal)
			self.calibration_file_ctrl.SetSelection(idx)
			self.calibration_file_ctrl.SetToolTipString(cal)
			if ext.lower() in (".icc", ".icm"):
				profile_path = cal
			else:
				profile_path = filename + profile_ext
			profile_exists = os.path.exists(profile_path)
		else:
			if cal in self.recent_cals:
				# The case-sensitive index could fail because of 
				# case insensitive file systems, e.g. if the 
				# stored filename string is 
				# "C:\Users\Name\AppData\dispcalGUI\storage\MyFile"
				# but the actual filename is 
				# "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
				# (maybe because the user renamed the file)
				idx = index_fallback_ignorecase(self.recent_cals, cal)
				self.recent_cals.remove(cal)
				self.calibration_file_ctrl.Delete(idx)
			cal = None
			self.calibration_file_ctrl.SetStringSelection(
				lang.getstr("settings.new"))
			self.calibration_file_ctrl.SetToolTip(None)
			setcfg("calibration.file", None)
			setcfg("calibration.update", 0)
			profile_path = None
			profile_exists = False
		self.delete_calibration_btn.Enable(bool(cal) and 
										   cal not in self.presets)
		self.install_profile_btn.Enable(profile_exists and 
										cal not in self.presets)
		enable_update = bool(cal) and os.path.exists(filename + ".cal")
		if not enable_update:
			setcfg("calibration.update", 0)
		self.calibration_update_cb.Enable(enable_update)
		self.calibration_update_cb.SetValue(
			bool(getcfg("calibration.update")))

		update_cal = self.calibration_update_cb.GetValue()
		enable_cal = not(update_cal)

		if not update_cal or not profile_exists:
			setcfg("profile.update", "0")
		self.profile_update_cb.Enable(update_cal and profile_exists)
		self.profile_update_cb.SetValue(
			bool(getcfg("profile.update")))

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
		self.update_black_point_rate_ctrl()
		self.interactive_display_adjustment_cb.Enable(enable_cal)

		self.testchart_btn.Enable(enable_profile)
		self.create_testchart_btn.Enable(enable_profile)
		self.profile_type_ctrl.Enable(enable_profile)

		measurement_mode = getcfg("measurement_mode")
		if self.get_instrument_type() == "spect":
			measurement_mode = strtr(measurement_mode, {"c": "", "l": ""})
		instrument_features = self.worker.get_instrument_features()
		if instrument_features.get("projector_mode") and \
		   self.worker.argyll_version >= [1, 1, 0] and \
		   getcfg("measurement_mode.projector"):
			measurement_mode += "p"
		if instrument_features.get("adaptive_mode") and (
		   self.worker.argyll_version[0:3] > [1, 1, 0] or (
		   self.worker.argyll_version[0:3] == [1, 1, 0] and
		   not "Beta" in self.worker.argyll_version_string and
		   not "RC1" in self.worker.argyll_version_string and
		   not "RC2" in self.worker.argyll_version_string)) and \
		   getcfg("measurement_mode.adaptive"):
			measurement_mode += "V"
		if instrument_features.get("highres_mode") and \
		   getcfg("measurement_mode.highres"):
			measurement_mode += "H"
		self.measurement_mode_ctrl.SetSelection(
			min(self.measurement_modes_ba[self.get_instrument_type()].get(
					measurement_mode, 0), 
				len(self.measurement_mode_ctrl.GetItems()) - 1))

		self.whitepoint_colortemp_textctrl.SetValue(
			str(getcfg("whitepoint.colortemp")))
		self.whitepoint_x_textctrl.ChangeValue(str(getcfg("whitepoint.x")))
		self.whitepoint_y_textctrl.ChangeValue(str(getcfg("whitepoint.y")))
		self.whitepoint_colortemp_locus_ctrl.SetSelection(
			self.whitepoint_colortemp_loci_ba.get(
				getcfg("whitepoint.colortemp.locus"), 
			self.whitepoint_colortemp_loci_ba.get(
				defaults["whitepoint.colortemp.locus"])))
		if getcfg("whitepoint.colortemp", False):
			self.whitepoint_colortemp_rb.SetValue(True)
			self.whitepoint_ctrl_handler(
				CustomEvent(wx.EVT_RADIOBUTTON.evtType[0], 
				self.whitepoint_colortemp_rb), False)
			self.whitepoint_colortemp_locus_ctrl.Enable(enable_cal)
		elif getcfg("whitepoint.x", False) and getcfg("whitepoint.y", False):
			self.whitepoint_xy_rb.SetValue(True)
			self.whitepoint_ctrl_handler(
				CustomEvent(wx.EVT_RADIOBUTTON.evtType[0], 
				self.whitepoint_xy_rb), False)
			self.whitepoint_colortemp_locus_ctrl.Disable()
		else:
			self.whitepoint_native_rb.SetValue(True)
		self.whitepoint_colortemp_textctrl.Enable(
			enable_cal and bool(getcfg("whitepoint.colortemp", False)))
		self.whitepoint_x_textctrl.Enable(enable_cal and 
										  bool(getcfg("whitepoint.x", False)))
		self.whitepoint_y_textctrl.Enable(enable_cal and 
										  bool(getcfg("whitepoint.y", False)))

		if getcfg("calibration.luminance", False):
			self.luminance_cdm2_rb.SetValue(True)
		else:
			self.luminance_max_rb.SetValue(True)
		self.luminance_textctrl.ChangeValue(
			str(getcfg("calibration.luminance")))
		self.luminance_textctrl.Enable(enable_cal and 
									   bool(getcfg("calibration.luminance", 
												   False)))

		if getcfg("calibration.black_luminance", False):
			self.black_luminance_cdm2_rb.SetValue(True)
		else:
			self.black_luminance_min_rb.SetValue(True)
		self.black_luminance_textctrl.ChangeValue(
			str(getcfg("calibration.black_luminance")))
		self.black_luminance_textctrl.Enable(
			enable_cal and bool(getcfg("calibration.black_luminance", False)))

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
			self.trc_type_ctrl.SetSelection(
				self.trc_types_ba.get(getcfg("trc.type"), 
				self.trc_types_ba.get(defaults["trc.type"])))
			self.trc_type_ctrl.Enable(enable_cal)

		self.ambient_viewcond_adjust_cb.SetValue(
			bool(int(getcfg("calibration.ambient_viewcond_adjust"))))
		self.ambient_viewcond_adjust_textctrl.ChangeValue(
			str(getcfg("calibration.ambient_viewcond_adjust.lux")))
		self.ambient_viewcond_adjust_textctrl.Enable(
			enable_cal and 
			bool(int(getcfg("calibration.ambient_viewcond_adjust"))))

		self.profile_type_ctrl.SetSelection(
			self.profile_types_ba.get(getcfg("profile.type"), 
			self.profile_types_ba.get(defaults["profile.type"])))

		self.black_output_offset_ctrl.SetValue(
			int(Decimal(str(getcfg("calibration.black_output_offset"))) * 100))
		self.black_output_offset_intctrl.SetValue(
			int(Decimal(str(getcfg("calibration.black_output_offset"))) * 100))

		self.black_point_correction_ctrl.SetValue(
			int(Decimal(str(getcfg("calibration.black_point_correction"))) * 
							100))
		self.black_point_correction_intctrl.SetValue(
			int(Decimal(str(getcfg("calibration.black_point_correction"))) * 
							100))

		self.black_point_rate_ctrl.SetValue(
			int(Decimal(str(getcfg("calibration.black_point_rate"))) * 100))
		self.black_point_rate_intctrl.SetValue(
			int(Decimal(str(getcfg("calibration.black_point_rate"))) * 100))

		q = self.quality_ba.get(getcfg("calibration.quality"), 
								self.quality_ba.get(
									defaults["calibration.quality"]))
		self.calibration_quality_ctrl.SetValue(q)
		if q == 1:
			self.calibration_quality_info.SetLabel(
				lang.getstr("calibration.quality.verylow"))
		elif q == 2:
			self.calibration_quality_info.SetLabel(
				lang.getstr("calibration.quality.low"))
		elif q == 3:
			self.calibration_quality_info.SetLabel(
				lang.getstr("calibration.quality.medium"))
		elif q == 4:
			self.calibration_quality_info.SetLabel(
				lang.getstr("calibration.quality.high"))

		self.interactive_display_adjustment_cb.SetValue(enable_cal and 
			bool(int(getcfg("calibration.interactive_display_adjustment"))))

		self.testchart_ctrl.Enable(enable_profile)
		if self.set_default_testchart() is None:
			self.set_testchart()

		simple_gamma_model = self.get_profile_type() in ("g", "G")
		if simple_gamma_model:
			q = 3
		else:
			q = self.quality_ba.get(getcfg("profile.quality"), 
									self.quality_ba.get(
										defaults["profile.quality"])) - 1
		self.profile_quality_ctrl.SetValue(q)
		if q == 1:
			self.profile_quality_info.SetLabel(
				lang.getstr("calibration.quality.low"))
		elif q == 2:
			self.profile_quality_info.SetLabel(
				lang.getstr("calibration.quality.medium"))
		elif q == 3:
			self.profile_quality_info.SetLabel(
				lang.getstr("calibration.quality.high"))
		elif q == 4:
			self.profile_quality_info.SetLabel(
				lang.getstr("calibration.quality.ultra"))
		self.profile_quality_ctrl.Enable(enable_profile and not simple_gamma_model)

		enable_gamap = self.get_profile_type() in ("l", "x", "X")
		self.gamap_btn.Enable(enable_profile and enable_gamap)

		if hasattr(self, "gamapframe"):
			self.gamapframe.update_controls()

		if update_profile_name:
			self.profile_name_textctrl.ChangeValue(getcfg("profile.name"))
			self.update_profile_name()

		self.update_main_controls()
		
		self.panel.Thaw()

		self.updatingctrls = False
	
	def update_black_point_rate_ctrl(self):
		self.calpanel.Freeze()
		enable = not(self.calibration_update_cb.GetValue())
		self.black_point_rate_label.GetContainingSizer().Show(
			self.black_point_rate_label,
			defaults["calibration.black_point_rate.enabled"])
		self.black_point_rate_ctrl.GetContainingSizer().Show(
			self.black_point_rate_ctrl,
			defaults["calibration.black_point_rate.enabled"])
		self.black_point_rate_ctrl.Enable(
			enable and 
			getcfg("calibration.black_point_correction") < 1 and 
			defaults["calibration.black_point_rate.enabled"])
		self.black_point_rate_intctrl.GetContainingSizer().Show(
			self.black_point_rate_intctrl,
			defaults["calibration.black_point_rate.enabled"])
		self.black_point_rate_intctrl.Enable(
			enable  and 
			getcfg("calibration.black_point_correction") < 1 and 
			defaults["calibration.black_point_rate.enabled"])
		self.calpanel.Layout()
		self.calpanel.Thaw()

	def calibration_update_ctrl_handler(self, event):
		if debug:
			safe_print("[D] calibration_update_ctrl_handler called for ID %s "
					   "%s event type %s %s" % (event.GetId(), 
												getevtobjname(event, self), 
												event.GetEventType(), 
												getevttype(event)))
		setcfg("calibration.update", 
			   int(self.calibration_update_cb.GetValue()))
		self.update_controls()

	def enable_spyder2_handler(self, event):
		if check_set_argyll_bin():
			cmd, args = get_argyll_util("spyd2en"), ["-v"]
			result = self.worker.exec_cmd(cmd, args, capture_output=True, 
										  skip_scripts=True, silent=True,
										  asroot=True)
			if not isinstance(result, Exception) and result:
				InfoDialog(self, msg=lang.getstr("enable_spyder2_success"), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-information"),
						   log=False)
			else:
				if isinstance(result, Exception):
					show_result_dialog(result, self) 
				# prompt for setup.exe
				defaultDir, defaultFile = expanduseru("~"), "setup.exe"
				dlg = wx.FileDialog(self, lang.getstr("locate_spyder2_setup"), 
									defaultDir=defaultDir, 
									defaultFile=defaultFile, wildcard="*", 
									style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
				dlg.Center(wx.BOTH)
				result = dlg.ShowModal()
				path = dlg.GetPath()
				dlg.Destroy()
				if result == wx.ID_OK:
					if not os.path.exists(path):
						InfoDialog(self, msg=lang.getstr("file.missing", path), 
								   ok=lang.getstr("ok"), 
								   bitmap=geticon(32, "dialog-error"))
						return
					result = self.worker.exec_cmd(cmd, args + [path], 
												  capture_output=True, 
												  skip_scripts=True, 
												  silent=True,
												  asroot=True)
					if not isinstance(result, Exception) and result:
						InfoDialog(self, 
								   msg=lang.getstr("enable_spyder2_success"), 
								   ok=lang.getstr("ok"), 
								   bitmap=geticon(32, "dialog-information"),
								   log=False)
					else:
						if isinstance(result, Exception):
							show_result_dialog(result, self)
						InfoDialog(self, 
								   msg=lang.getstr("enable_spyder2_failure"), 
								   ok=lang.getstr("ok"), 
								   bitmap=geticon(32, "dialog-error"),
								   log=False)

	def use_separate_lut_access_handler(self, event):
		setcfg("use_separate_lut_access", 
			   int(self.menuitem_use_separate_lut_access.IsChecked()))
		self.update_displays()

	def lut_viewer_show_actual_lut_handler(self, event):
		setcfg("lut_viewer.show_actual_lut", 
			   int(self.menuitem_show_actual_lut.IsChecked()))
		if hasattr(self, "current_cal"):
			profile = self.current_cal
		else:
			profile = None
		self.lut_viewer_load_lut(profile=profile)
	
	def profile_update_ctrl_handler(self, event):
		if debug:
			safe_print("[D] profile_update_ctrl_handler called for ID %s %s "
					   "event type %s %s" % (event.GetId(), 
											 getevtobjname(event, self), 
											 event.GetEventType(), 
											 getevttype(event)))
		setcfg("profile.update", int(self.profile_update_cb.GetValue()))
		self.update_controls()

	def profile_quality_warning_handler(self, event):
		q = self.get_profile_quality()
		if q == "u":
			InfoDialog(self, msg=lang.getstr("quality.ultra.warning"), 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-warning"), log=False)

	def profile_quality_ctrl_handler(self, event):
		if debug:
			safe_print("[D] profile_quality_ctrl_handler called for ID %s %s "
					   "event type %s %s" % (event.GetId(), 
											 getevtobjname(event, self), 
											 event.GetEventType(), 
											 getevttype(event)))
		oldq = getcfg("profile.quality")
		q = self.get_profile_quality()
		if q == oldq:
			return
		if q == "l":
			self.profile_quality_info.SetLabel(
				lang.getstr("calibration.quality.low"))
		elif q == "m":
			self.profile_quality_info.SetLabel(lang.getstr(
				"calibration.quality.medium"))
		elif q == "h":
			self.profile_quality_info.SetLabel(lang.getstr(
				"calibration.quality.high"))
		if q == "u":
			self.profile_quality_info.SetLabel(lang.getstr(
				"calibration.quality.ultra"))
		self.profile_settings_changed()
		setcfg("profile.quality", q)
		self.update_profile_name()
		self.set_default_testchart(False, force=True)
		wx.CallAfter(self.check_testchart_patches_amount)

	def calibration_file_ctrl_handler(self, event):
		if debug:
			safe_print("[D] calibration_file_ctrl_handler called for ID %s %s "
					   "event type %s %s" % (event.GetId(), 
											 getevtobjname(event, self), 
											 event.GetEventType(), 
											 getevttype(event)))
		sel = self.calibration_file_ctrl.GetSelection()
		if sel > 0:
			self.load_cal_handler(None, path=self.recent_cals[sel])
		else:
			self.cal_changed(setchanged=False)
	
	def settings_discard_changes(self, sel=None, keep_changed_state=False):
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
		# The case-sensitive index could fail because of 
		# case insensitive file systems, e.g. if the 
		# stored filename string is 
		# "C:\Users\Name\AppData\dispcalGUI\storage\MyFile"
		# but the actual filename is 
		# "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
		# (maybe because the user renamed the file)
		idx = index_fallback_ignorecase(self.recent_cals, 
										getcfg("calibration.file") or "")
		self.calibration_file_ctrl.SetSelection(idx)
		dlg = ConfirmDialog(self, msg=lang.getstr("warning.discard_changes"), 
								  ok=lang.getstr("ok"), 
								  cancel=lang.getstr("cancel"), 
								  bitmap=geticon(32, "dialog-warning"))
		result = dlg.ShowModal()
		dlg.Destroy()
		if result != wx.ID_OK: return False
		self.settings_discard_changes(sel)
		return True

	def calibration_quality_ctrl_handler(self, event):
		if debug:
			safe_print("[D] calibration_quality_ctrl_handler called for ID %s "
					   "%s event type %s %s" % (event.GetId(), 
												getevtobjname(event, self), 
												event.GetEventType(), 
												getevttype(event)))
		q = self.get_calibration_quality()
		if q == "v":
			self.calibration_quality_info.SetLabel(
				lang.getstr("calibration.quality.verylow"))
		elif q == "l":
			self.calibration_quality_info.SetLabel(
				lang.getstr("calibration.quality.low"))
		elif q == "m":
			self.calibration_quality_info.SetLabel(
				lang.getstr("calibration.quality.medium"))
		elif q == "h":
			self.calibration_quality_info.SetLabel(
				lang.getstr("calibration.quality.high"))
		if q != getcfg("calibration.quality"):
			self.profile_settings_changed()
		setcfg("calibration.quality", q)
		self.update_profile_name()

	def interactive_display_adjustment_ctrl_handler(self, event):
		if debug:
			safe_print("[D] interactive_display_adjustment_ctrl_handler called "
					   "for ID %s %s event type %s %s" % (event.GetId(), 
														  getevtobjname(event, 
																		self), 
														  event.GetEventType(), 
														  getevttype(event)))
		v = int(self.interactive_display_adjustment_cb.GetValue())
		if v != getcfg("calibration.interactive_display_adjustment"):
			self.profile_settings_changed()
		setcfg("calibration.interactive_display_adjustment", v)

	def black_point_correction_ctrl_handler(self, event):
		if debug:
			safe_print("[D] black_point_correction_ctrl_handler called for ID "
					   "%s %s event type %s %s" % (event.GetId(), 
												   getevtobjname(event, self), 
												   event.GetEventType(), 
												   getevttype(event)))
		if event.GetId() == self.black_point_correction_intctrl.GetId():
			self.black_point_correction_ctrl.SetValue(
				self.black_point_correction_intctrl.GetValue())
		else:
			self.black_point_correction_intctrl.SetValue(
				self.black_point_correction_ctrl.GetValue())
		v = self.get_black_point_correction()
		if float(v) != getcfg("calibration.black_point_correction"):
			self.cal_changed()
		setcfg("calibration.black_point_correction", v)
		self.black_point_rate_ctrl.Enable(
			getcfg("calibration.black_point_correction") < 1 and 
			defaults["calibration.black_point_rate.enabled"])
		self.black_point_rate_intctrl.Enable(
			getcfg("calibration.black_point_correction") < 1 and 
			defaults["calibration.black_point_rate.enabled"])
		self.update_profile_name()

	def black_point_rate_ctrl_handler(self, event):
		if debug:
			safe_print("[D] black_point_rate_ctrl_handler called for ID %s %s "
					   "event type %s %s" % (event.GetId(), 
											 getevtobjname(event, self), 
											 event.GetEventType(), 
											 getevttype(event)))
		if event.GetId() == self.black_point_rate_intctrl.GetId():
			self.black_point_rate_ctrl.SetValue(
				self.black_point_rate_intctrl.GetValue())
		else:
			self.black_point_rate_intctrl.SetValue(
				self.black_point_rate_ctrl.GetValue())
		v = self.get_black_point_rate()
		if v != str(getcfg("calibration.black_point_rate")):
			self.cal_changed()
		setcfg("calibration.black_point_rate", v)
		self.update_profile_name()

	def black_output_offset_ctrl_handler(self, event):
		if debug:
			safe_print("[D] black_output_offset_ctrl_handler called for ID %s "
					   "%s event type %s %s" % (event.GetId(), 
												getevtobjname(event, self), 
												event.GetEventType(), 
												getevttype(event)))
		if event.GetId() == self.black_output_offset_intctrl.GetId():
			self.black_output_offset_ctrl.SetValue(
				self.black_output_offset_intctrl.GetValue())
		else:
			self.black_output_offset_intctrl.SetValue(
				self.black_output_offset_ctrl.GetValue())
		v = self.get_black_output_offset()
		if float(v) != getcfg("calibration.black_output_offset"):
			self.cal_changed()
		setcfg("calibration.black_output_offset", v)
		self.update_profile_name()
	
	def ambient_measure_handler(self, event):
		if not check_set_argyll_bin():
			return
		safe_print("-" * 80)
		safe_print(lang.getstr("ambient.measure"))
		self.worker.interactive = False
		self.worker.start(self.ambient_measure_process, 
						  self.ambient_measure_process, 
						  ckwargs={"event_id": event.GetId(),
								   "phase": "instcal_prepare"}, 
						  wkwargs={"phase": "init"},
						  progress_msg=lang.getstr("instrument.initializing"))
	
	def ambient_measure_process(self, result=None, event_id=None, phase=None):
		if self.worker.thread_abort:
			return
		if phase == "init":
			cmd = get_argyll_util("spotread")
			args = ["-v", "-c%s" % getcfg("comport.number"), "-a", "-x"]
			measurement_mode = getcfg("measurement_mode")
			instrument_features = self.worker.get_instrument_features()
			if measurement_mode and not instrument_features.get("spectral"):
				# Always specify -y for colorimeters
				args += ["-y" + measurement_mode[0]]
			safe_print("")
			safe_print(lang.getstr("commandline"))
			printcmdline(cmd, args)
			safe_print("")
			kwargs = dict(timeout=10)
			if sys.platform == "win32":
				codepage = windll.kernel32.GetACP()
				kwargs["codepage"] = codepage
				data_encoding = aliases.get(str(codepage), "ascii")
			else:
				data_encoding = enc
			self.worker.clear_cmd_output()
			try:
				result = wexpect.spawn(cmd, args, **kwargs)
				result.logfile_read = FilteredStream(safe_print)
			except Exception, exception:
				return exception
			if not result or not result.isalive():
				return
			if self.worker.get_instrument_features().get("sensor_cal"):
				return result
			else:
				phase = "measure_init"
		if phase is not None and (not result or isinstance(result, 
														   Exception) or 
								  not result.isalive()):
			if isinstance(result, Exception):
				log(safe_unicode(result))
			InfoDialog(self,
					   msg=lang.getstr("error"), 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-error"), log=False)
			return
		if phase == "instcal_prepare":
			if self.worker.get_instrument_features().get("sensor_cal"):
				dlg = ConfirmDialog(self, msg=lang.getstr("instrument.calibrate"), 
									ok=lang.getstr("ok"), 
									cancel=lang.getstr("cancel"), 
									bitmap=geticon(32, "dialog-information"))
				dlg_result = dlg.ShowModal()
				dlg.Destroy()
				if dlg_result != wx.ID_OK:
					safe_print(lang.getstr("aborted"))
					return False
				self.worker.start(self.ambient_measure_process, 
								  self.ambient_measure_process, 
								  ckwargs={"event_id": event_id, 
										   "phase": "measure_prepare"}, 
								  wkwargs={"result": result, 
										   "phase": "instcal"},
								  progress_msg=lang.getstr("instrument.calibrating"))
				return
			else:
				phase = "measure_prepare"
		elif phase == "instcal":
			# the only optional phase
			try:
				result.send(" ")
			except Exception, exception:
				return exception
			phase = "measure_init"
		pat = "Hit ESC or Q to exit, any other key to take a reading:"
		if phase == "measure_init":
			try:
				result.expect(pat)
			except Exception, exception:
				return exception
			if self.worker.thread_abort:
				return
			return result
		elif phase == "measure_prepare":
			dlg = ConfirmDialog(self, msg=lang.getstr("instrument.measure_ambient"), 
								ok=lang.getstr("ok"), 
								cancel=lang.getstr("cancel"), 
								bitmap=geticon(32, "dialog-information"))
			dlg_result = dlg.ShowModal()
			dlg.Destroy()
			if dlg_result != wx.ID_OK:
				safe_print(lang.getstr("aborted"))
				return False
			self.worker.start(self.ambient_measure_process, 
							  self.ambient_measure_process, 
							  ckwargs={"event_id": event_id}, 
							  wkwargs={"result": result, 
									   "phase": "measure"},
							  progress_msg=lang.getstr("ambient.measure"))
			return
		elif phase == "measure":
			try:
				result.send(" ")
				result.expect("Place instrument")
			except Exception, exception:
				return exception
			if self.worker.thread_abort:
				return
			data = result.before if isinstance(result.before, basestring) else ""
			data = re.sub("[^\t\n\r\x20-\x7f]", "", data).strip()
			#safe_print(os.linesep.join([line.strip() for line in data.splitlines()]))
			try:
				result.expect(pat)
				result.send("q")
				result.expect(":")
				result.send("q")
			except Exception, exception:
				return exception
			sleep(.05)
			try:
				if result.isalive():
					result.terminate(force=True)
			except Exception, exception:
				log(safe_unicode(exception))
			return data
		# finish
		# result = data
		if getcfg("whitepoint.colortemp.locus") == "T":
			K = re.search("Planckian temperature += (\d+(?:\.\d+))K", 
						  result, re.I)
		else:
			K = re.search("Daylight temperature += (\d+(?:\.\d+))K", 
						  result, re.I)
		lux = re.search("Ambient = (\d+(?:\.\d+)) Lux", result, re.I)
		set_whitepoint = event_id == self.whitepoint_measure_btn.GetId()
		set_ambient = event_id == self.ambient_measure_btn.GetId()
		if set_whitepoint and not set_ambient:
			dlg = ConfirmDialog(self, msg=lang.getstr("ambient.set"), 
								ok=lang.getstr("yes"), 
								cancel=lang.getstr("no"), 
								bitmap=geticon(32, "dialog-question"))
			set_ambient = dlg.ShowModal() == wx.ID_OK
			dlg.Destroy()
		if set_ambient and not set_whitepoint:
			dlg = ConfirmDialog(self, msg=lang.getstr("whitepoint.set"), 
								ok=lang.getstr("yes"), 
								cancel=lang.getstr("no"), 
								bitmap=geticon(32, "dialog-question"))
			set_whitepoint = dlg.ShowModal() == wx.ID_OK
			dlg.Destroy()
		if set_whitepoint:
			if K and len(K.groups()) == 1:
				self.whitepoint_colortemp_textctrl.SetValue(K.groups()[0])
			Yxy = re.search("Yxy: (\d+(?:\.\d+)) (\d+(?:\.\d+)) (\d+(?:\.\d+))", 
							result)
			if Yxy and len(Yxy.groups()) == 3:
				Y, x, y = Yxy.groups()
				self.whitepoint_x_textctrl.SetValue(x)
				self.whitepoint_y_textctrl.SetValue(y)
				if not getcfg("whitepoint.colortemp", False):
					self.whitepoint_xy_rb.SetValue(True)
					self.whitepoint_ctrl_handler(
						CustomEvent(wx.EVT_RADIOBUTTON.evtType[0], 
									self.whitepoint_xy_rb))
		if set_ambient:
			if lux and len(lux.groups()) == 1:
				self.ambient_viewcond_adjust_textctrl.SetValue(lux.groups()[0])
				self.ambient_viewcond_adjust_cb.SetValue(True)
				self.ambient_viewcond_adjust_ctrl_handler(
						CustomEvent(wx.EVT_CHECKBOX.evtType[0], 
									self.ambient_viewcond_adjust_cb))

	def ambient_viewcond_adjust_ctrl_handler(self, event):
		if event.GetId() == self.ambient_viewcond_adjust_textctrl.GetId() and \
		   (not self.ambient_viewcond_adjust_cb.GetValue() or 
			str(float(getcfg("calibration.ambient_viewcond_adjust.lux"))) == 
			self.ambient_viewcond_adjust_textctrl.GetValue()):
			event.Skip()
			return
		if debug:
			safe_print("[D] ambient_viewcond_adjust_ctrl_handler called for ID "
					   "%s %s event type %s %s" % (event.GetId(), 
												   getevtobjname(event, self), 
												   event.GetEventType(), 
												   getevttype(event)))
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
					self.ambient_viewcond_adjust_textctrl.ChangeValue(
						str(getcfg("calibration.ambient_viewcond_adjust.lux")))
			if event.GetId() == self.ambient_viewcond_adjust_cb.GetId():
				self.ambient_viewcond_adjust_textctrl.SetFocus()
				self.ambient_viewcond_adjust_textctrl.SelectAll()
		else:
			self.ambient_viewcond_adjust_textctrl.Disable()
		v1 = int(self.ambient_viewcond_adjust_cb.GetValue())
		v2 = self.ambient_viewcond_adjust_textctrl.GetValue()
		if v1 != getcfg("calibration.ambient_viewcond_adjust") or \
		   v2 != str(getcfg("calibration.ambient_viewcond_adjust.lux", False)):
			self.cal_changed()
		setcfg("calibration.ambient_viewcond_adjust", v1)
		setcfg("calibration.ambient_viewcond_adjust.lux", v2)
		self.update_profile_name()
		if event.GetEventType() == wx.EVT_KILL_FOCUS.evtType[0]:
			event.Skip()

	def ambient_viewcond_adjust_info_handler(self, event):
		InfoDialog(self, 
				   msg=lang.getstr("calibration.ambient_viewcond_adjust.info"), 
				   ok=lang.getstr("ok"), 
				   bitmap=geticon(32, "dialog-information"), log=False)

	def black_luminance_ctrl_handler(self, event):
		if event.GetId() == self.black_luminance_textctrl.GetId() and (not 
		   self.black_luminance_cdm2_rb.GetValue() or 
		   str(float(getcfg("calibration.black_luminance"))) == 
		   self.black_luminance_textctrl.GetValue()):
			event.Skip()
			return
		if debug:
			safe_print("[D] black_luminance_ctrl_handler called for ID %s %s "
					   "event type %s %s" % (event.GetId(), 
											 getevtobjname(event, self), 
											 event.GetEventType(), 
											 getevttype(event)))
		if self.black_luminance_cdm2_rb.GetValue(): # cd/m2
			self.black_luminance_textctrl.Enable()
			try:
				v = float(self.black_luminance_textctrl.GetValue().replace(",", 
																		   "."))
				if v < 0.000001 or v > 100000:
					raise ValueError()
				self.black_luminance_textctrl.ChangeValue(str(v))
			except ValueError:
				wx.Bell()
				self.black_luminance_textctrl.ChangeValue(
					str(getcfg("calibration.black_luminance")))
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
		if event.GetId() == self.luminance_textctrl.GetId() and (not 
		   self.luminance_cdm2_rb.GetValue() or 
		   str(float(getcfg("calibration.luminance"))) == 
		   self.luminance_textctrl.GetValue()):
			event.Skip()
			return
		if debug:
			safe_print("[D] luminance_ctrl_handler called for ID %s %s event "
					   "type %s %s" % (event.GetId(), 
									   getevtobjname(event, self), 
									   event.GetEventType(), 
									   getevttype(event)))
		if self.luminance_cdm2_rb.GetValue(): # cd/m2
			self.luminance_textctrl.Enable()
			try:
				v = float(self.luminance_textctrl.GetValue().replace(",", "."))
				if v < 0.000001 or v > 100000:
					raise ValueError()
				self.luminance_textctrl.ChangeValue(str(v))
			except ValueError:
				wx.Bell()
				self.luminance_textctrl.ChangeValue(
					str(getcfg("calibration.luminance")))
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
		if debug:
			safe_print("[D] whitepoint_colortemp_locus_ctrl_handler called for "
					   "ID %s %s event type %s %s" % (event.GetId(), 
													  getevtobjname(event, 
																	self), 
													  event.GetEventType(), 
													  getevttype(event)))
		v = self.get_whitepoint_locus()
		if v != getcfg("whitepoint.colortemp.locus"):
			self.cal_changed()
		setcfg("whitepoint.colortemp.locus", v)
		self.update_profile_name()

	def whitepoint_ctrl_handler(self, event, cal_changed=True):
		if event.GetId() == self.whitepoint_colortemp_textctrl.GetId() and (not 
		   self.whitepoint_colortemp_rb.GetValue() or 
		   str(float(getcfg("whitepoint.colortemp"))) == 
		   self.whitepoint_colortemp_textctrl.GetValue()):
			event.Skip()
			return
		if event.GetId() == self.whitepoint_x_textctrl.GetId() and (not 
		   self.whitepoint_xy_rb.GetValue() or 
		   str(float(getcfg("whitepoint.x"))) == 
		   self.whitepoint_x_textctrl.GetValue()):
			event.Skip()
			return
		if event.GetId() == self.whitepoint_y_textctrl.GetId() and (not 
		   self.whitepoint_xy_rb.GetValue() or 
		   str(float(getcfg("whitepoint.y"))) == 
		   self.whitepoint_y_textctrl.GetValue()):
			event.Skip()
			return
		if debug:
			safe_print("[D] whitepoint_ctrl_handler called for ID %s %s event "
					   "type %s %s" % (event.GetId(), 
									   getevtobjname(event, self), 
									   event.GetEventType(), 
									   getevttype(event)))
		if self.whitepoint_xy_rb.GetValue(): # x,y chromaticity coordinates
			self.whitepoint_colortemp_locus_ctrl.Disable()
			self.whitepoint_colortemp_textctrl.Disable()
			self.whitepoint_x_textctrl.Enable()
			self.whitepoint_y_textctrl.Enable()
			try:
				v = float(self.whitepoint_x_textctrl.GetValue().replace(",", 
																		"."))
				if v < 0 or v > 1:
					raise ValueError()
				self.whitepoint_x_textctrl.ChangeValue(str(v))
			except ValueError:
				wx.Bell()
				self.whitepoint_x_textctrl.ChangeValue(
					str(getcfg("whitepoint.x")))
			try:
				v = float(self.whitepoint_y_textctrl.GetValue().replace(",", 
																		"."))
				if v < 0 or v > 1:
					raise ValueError()
				self.whitepoint_y_textctrl.ChangeValue(str(v))
			except ValueError:
				wx.Bell()
				self.whitepoint_y_textctrl.ChangeValue(
					str(getcfg("whitepoint.y")))
			x = self.whitepoint_x_textctrl.GetValue().replace(",", ".")
			y = self.whitepoint_y_textctrl.GetValue().replace(",", ".")
			k = xyY2CCT(float(x), float(y), 1.0)
			if k:
				self.whitepoint_colortemp_textctrl.SetValue(
					str(stripzeros(math.ceil(k))))
			else:
				self.whitepoint_colortemp_textctrl.SetValue("")
			if cal_changed:
				if not getcfg("whitepoint.colortemp") and \
				   float(x) == getcfg("whitepoint.x") and \
				   float(y) == getcfg("whitepoint.y"):
					cal_changed = False
			setcfg("whitepoint.colortemp", None)
			setcfg("whitepoint.x", x)
			setcfg("whitepoint.y", y)
			if event.GetId() == self.whitepoint_xy_rb.GetId() and \
			   not self.updatingctrls:
				self.whitepoint_x_textctrl.SetFocus()
				self.whitepoint_x_textctrl.SelectAll()
		elif self.whitepoint_colortemp_rb.GetValue():
			self.whitepoint_colortemp_locus_ctrl.Enable()
			self.whitepoint_colortemp_textctrl.Enable()
			self.whitepoint_x_textctrl.Disable()
			self.whitepoint_y_textctrl.Disable()
			try:
				v = float(
					self.whitepoint_colortemp_textctrl.GetValue().replace(
						",", "."))
				if v < 1000 or v > 15000:
					raise ValueError()
				self.whitepoint_colortemp_textctrl.SetValue(str(v))
			except ValueError:
				wx.Bell()
				self.whitepoint_colortemp_textctrl.SetValue(
					str(getcfg("whitepoint.colortemp")))
			xyY = CIEDCCT2xyY(
				float(self.whitepoint_colortemp_textctrl.GetValue().replace(
					",", ".")))
			if xyY:
				self.whitepoint_x_textctrl.ChangeValue(
					str(stripzeros(round(xyY[0], 6))))
				self.whitepoint_y_textctrl.ChangeValue(
					str(stripzeros(round(xyY[1], 6))))
			else:
				self.whitepoint_x_textctrl.ChangeValue("")
				self.whitepoint_y_textctrl.ChangeValue("")
			if cal_changed:
				v = float(self.whitepoint_colortemp_textctrl.GetValue())
				if getcfg("whitepoint.colortemp") == v and not \
				   getcfg("whitepoint.x") and not getcfg("whitepoint.y"):
					cal_changed = False
			setcfg("whitepoint.colortemp", v)
			setcfg("whitepoint.x", None)
			setcfg("whitepoint.y", None)
			if event.GetId() == self.whitepoint_colortemp_rb.GetId() and not \
			   self.updatingctrls:
				self.whitepoint_colortemp_textctrl.SetFocus()
				self.whitepoint_colortemp_textctrl.SelectAll()
		else:
			self.whitepoint_colortemp_locus_ctrl.Enable()
			self.whitepoint_colortemp_textctrl.Disable()
			self.whitepoint_x_textctrl.Disable()
			self.whitepoint_y_textctrl.Disable()
			if not getcfg("whitepoint.colortemp") and \
			   not getcfg("whitepoint.x") and not getcfg("whitepoint.y"):
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
		if debug:
			safe_print("[D] trc_type_ctrl_handler called for ID %s %s event "
					   "type %s %s" % (event.GetId(), 
									   getevtobjname(event, self), 
									   event.GetEventType(), 
									   getevttype(event)))
		v = self.get_trc_type()
		if v != getcfg("trc.type"):
			self.cal_changed()
		setcfg("trc.type", v)
		self.update_profile_name()

	def trc_ctrl_handler(self, event, cal_changed=True):
		if event.GetId() == self.trc_textctrl.GetId() and (not 
		   self.trc_g_rb.GetValue() or stripzeros(getcfg("trc")) == 
		   stripzeros(self.trc_textctrl.GetValue())):
			event.Skip()
			return
		if debug:
			safe_print("[D] trc_ctrl_handler called for ID %s %s event type %s "
					   "%s" % (event.GetId(), getevtobjname(event, self), 
							   event.GetEventType(), getevttype(event)))
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
		if trc in ("240", "709", "s") and not \
		   (bool(int(getcfg("calibration.ambient_viewcond_adjust"))) and 
			getcfg("calibration.ambient_viewcond_adjust.lux")) and \
			getcfg("trc.should_use_viewcond_adjust.show_msg"):
			dlg = InfoDialog(self, 
							 msg=lang.getstr("trc.should_use_viewcond_adjust"), 
							 ok=lang.getstr("ok"), 
							 bitmap=geticon(32, "dialog-information"), 
							 show=False, log=False)
			chk = wx.CheckBox(dlg, -1, lang.getstr("dialog.do_not_show_again"))
			dlg.Bind(wx.EVT_CHECKBOX, self.should_use_viewcond_adjust_handler, 
					 id=chk.GetId())
			dlg.sizer3.Add(chk, flag=wx.TOP | wx.ALIGN_LEFT, border=12)
			dlg.sizer0.SetSizeHints(dlg)
			dlg.sizer0.Layout()
			dlg.ShowModalThenDestroy()

	def should_use_viewcond_adjust_handler(self, event):
		setcfg("trc.should_use_viewcond_adjust.show_msg", 
			   int(not event.GetEventObject().GetValue()))

	def check_overwrite(self, ext=""):
		filename = getcfg("profile.name.expanded") + ext
		dst_file = os.path.join(getcfg("profile.save_path"), 
								getcfg("profile.name.expanded"), filename)
		if os.path.exists(dst_file):
			dlg = ConfirmDialog(self, msg=lang.getstr("warning.already_exists", 
													  filename), 
								ok=lang.getstr("ok"), 
								cancel=lang.getstr("cancel"), 
								bitmap=geticon(32, "dialog-warning"))
			result = dlg.ShowModal()
			dlg.Destroy()
			if result != wx.ID_OK: return False
		return True

	def calibrate(self, remove=False):
		capture_output = not sys.stdout.isatty()
		cmd, args = self.worker.prepare_dispcal()
		if not isinstance(cmd, Exception):
			result = self.worker.exec_cmd(cmd, args, capture_output=capture_output)
		else:
			result = cmd
		self.worker.wrapup(not isinstance(result, Exception) and 
									result, remove or isinstance(result, 
																 Exception) or 
									not result)
		if not isinstance(result, Exception) and result:
			cal = os.path.join(getcfg("profile.save_path"), 
							   getcfg("profile.name.expanded"), 
							   getcfg("profile.name.expanded") + ".cal")
			result = check_cal_isfile(
				cal, lang.getstr("error.calibration.file_not_created"))
			if not isinstance(result, Exception) and result:
				cal_cgats = add_dispcal_options_to_cal(cal, 
													   self.worker.options_dispcal)
				if cal_cgats:
					cal_cgats.write()
				setcfg("last_cal_path", cal)
				self.previous_cal = getcfg("calibration.file")
				if getcfg("profile.update") or \
				   self.worker.dispcal_create_fast_matrix_shaper:
					profile_path = os.path.join(getcfg("profile.save_path"), 
												getcfg("profile.name.expanded"), 
												getcfg("profile.name.expanded") + 
												profile_ext)
					result = check_profile_isfile(
						profile_path, 
						lang.getstr("error.profile.file_not_created"))
					if not isinstance(result, Exception) and result:
						if not getcfg("profile.update"):
							# we need to set cprt and targ
							try:
								profile = ICCP.ICCProfile(profile_path)
								profile.tags.cprt = ICCP.TextType(
									"text\0\0\0\0" + 
									getcfg("copyright").encode("ASCII", "asciize") + 
									"\0",
									"cprt")
								ti3 = add_options_to_ti3(
									profile.tags.get("targ", 
													 profile.tags.get("CIED", 
																	  "")), 
									self.worker.options_dispcal)
								if not ti3:
									ti3 = CGATS.CGATS("TI3\n")
									ti3[1] = cal_cgats
								if ti3:
									profile.tags.targ = ICCP.TextType(
										"text\0\0\0\0" + str(ti3) + "\0", 
										"targ")
									profile.tags.CIED = ICCP.TextType(
										"text\0\0\0\0" + str(ti3) + "\0", 
										"CIED")
									profile.tags.DevD = ICCP.TextType(
										"text\0\0\0\0" + str(ti3) + "\0", 
										"DevD")
								profile.write()
							except Exception, exception:
								safe_print(exception)
						setcfg("calibration.file", profile_path)
						wx.CallAfter(self.update_controls, 
									 update_profile_name=False)
						setcfg("last_cal_or_icc_path", profile_path)
						setcfg("last_icc_path", profile_path)
				else:
					setcfg("calibration.file", cal)
					wx.CallAfter(self.update_controls, 
								 update_profile_name=False)
					setcfg("last_cal_or_icc_path", cal)
					wx.CallAfter(self.load_cal, cal=cal, silent=True)
		return result

	def measure(self, consumer, apply_calibration=True, progress_msg="",
				resume=False, continue_next=False):
		self.worker.start(consumer, self.measure_producer, 
						  wkwargs={"apply_calibration": apply_calibration},
						  progress_msg=progress_msg, resume=resume, 
						  continue_next=continue_next)
	
	def measure_producer(self, apply_calibration=True):
		cmd, args = self.worker.prepare_dispread(apply_calibration)
		if not isinstance(cmd, Exception):
			result = self.worker.exec_cmd(cmd, args)
		self.worker.wrapup(not isinstance(result, Exception) and 
									result, isinstance(result, Exception) or 
									not result)
		return result
	
	def measure_calibrate(self, consumer, producer, remove=False, 
						  progress_msg="", continue_next=False):
		self.worker.start(consumer, producer, wkwargs={"remove": remove},
						  progress_msg=progress_msg, 
						  continue_next=continue_next)

	def profile(self, dst_path=None, 
				skip_scripts=False, display_name=None):
		safe_print(lang.getstr("create_profile"))
		if dst_path is None:
			dst_path = os.path.join(getcfg("profile.save_path"), 
									getcfg("profile.name.expanded"), 
									getcfg("profile.name.expanded") + 
									profile_ext)
		cmd, args = self.worker.prepare_colprof(
			os.path.basename(os.path.splitext(dst_path)[0]), display_name)
		if not isinstance(cmd, Exception): 
			result = self.worker.exec_cmd(cmd, args, low_contrast=False, 
										  skip_scripts=skip_scripts)
		else:
			result = cmd
		safe_print("-" * 80)
		self.worker.wrapup(not isinstance(result, Exception) and 
									result, dst_path=dst_path)
		if not isinstance(result, Exception) and result:
			try:
				profile = ICCP.ICCProfile(dst_path)
			except (IOError, ICCP.ICCProfileInvalidError), exception:
				return Error(lang.getstr("profile.invalid") + "\n" + dst_path)
			if profile.profileClass == "mntr" and profile.colorSpace == "RGB":
				setcfg("last_cal_or_icc_path", dst_path)
				setcfg("last_icc_path", dst_path)
			# Fixup desc tags - ASCII needs to be 7-bit
			# also add Unicode and Mac ScriptCode strings
			desc = profile.getDescription()
			profile.tags.desc["ASCII"] = desc.encode("ascii", "asciize")
			profile.tags.desc["Macintosh"] = desc
			profile.tags.desc["Unicode"] = desc
			if "dmdd" in profile.tags:
				ddesc = profile.getDeviceModelDescription()
				profile.tags.dmdd["ASCII"] = ddesc.encode("ascii", "asciize")
				profile.tags.dmdd["Macintosh"] = ddesc
				profile.tags.dmdd["Unicode"] = ddesc
			profile.write()
		return result

	def install_cal_handler(self, event=None, cal=None):
		if not check_set_argyll_bin():
			return
		if cal is None:
			cal = getcfg("calibration.file")
		if cal:
			result = check_file_isfile(cal)
			if isinstance(result, Exception):
				show_result_dialog(result, self)
		else:
			result = False
		if not isinstance(result, Exception) and result:
			filename, ext = os.path.splitext(cal)
			if ext.lower() in (".icc", ".icm"):
				try:
					profile = ICCP.ICCProfile(cal)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					InfoDialog(self, msg=lang.getstr("profile.invalid") + 
										 "\n" + cal, 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
					return
				if profile.profileClass != "mntr" or \
				   profile.colorSpace != "RGB":
					InfoDialog(self, msg=lang.getstr("profile.unsupported", 
													 (profile.profileClass, 
													  profile.colorSpace)) +
										 "\n" + cal, 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
					return
				profile_path = cal
			else:
				profile_path = filename + profile_ext
			if os.path.exists(profile_path):
				self.previous_cal = False
				self.profile_finish(
					True, profile_path=profile_path, 
					success_msg=lang.getstr(
						"dialog.install_profile", 
						(os.path.basename(profile_path), 
						 self.display_ctrl.GetStringSelection())), 
					skip_scripts=True)

	def install_profile_handler(self, event):
		defaultDir, defaultFile = get_verified_path("last_icc_path")
		dlg = wx.FileDialog(self, lang.getstr("install_display_profile"), 
							defaultDir=defaultDir, defaultFile=defaultFile, 
							wildcard=lang.getstr("filetype.icc") + 
									 "|*.icc;*.icm", 
							style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		dlg.Center(wx.BOTH)
		result = dlg.ShowModal()
		path = dlg.GetPath()
		dlg.Destroy()
		if result == wx.ID_OK:
			if not os.path.exists(path):
				InfoDialog(self, msg=lang.getstr("file.missing", path), 
						   ok=lang.getstr("ok"), bitmap=geticon(32, 
																"dialog-error"))
				return
			setcfg("last_icc_path", path)
			setcfg("last_cal_or_icc_path", path)
			self.install_cal_handler(cal=path)

	def load_profile_cal_handler(self, event):
		if not check_set_argyll_bin():
			return
		defaultDir, defaultFile = get_verified_path("last_cal_or_icc_path")
		dlg = wx.FileDialog(self, 
							lang.getstr("calibration.load_from_cal_or_profile"), 
							defaultDir=defaultDir, defaultFile=defaultFile, 
							wildcard=lang.getstr("filetype.cal_icc") + 
									 "|*.cal;*.icc;*.icm", 
							style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		dlg.Center(wx.BOTH)
		result = dlg.ShowModal()
		path = dlg.GetPath()
		dlg.Destroy()
		if result == wx.ID_OK:
			if not os.path.exists(path):
				InfoDialog(self, msg=lang.getstr("file.missing", path), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				return
			setcfg("last_cal_or_icc_path", path)
			if verbose >= 1:
				safe_print(lang.getstr("calibration.loading"))
				safe_print(path)
			if os.path.splitext(path)[1].lower() in (".icc", ".icm"):
				try:
					profile = ICCP.ICCProfile(path)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					if verbose >= 1: safe_print(lang.getstr("failure"))
					InfoDialog(self, msg=lang.getstr("profile.invalid") + 
										 "\n" + path, 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
					return
				if "vcgt" in profile.tags:
					setcfg("last_icc_path", path)
					if self.install_profile(capture_output=True, 
											profile_path=path, 
											install=False, 
											skip_scripts=True, 
											silent=True) is True:
						self.lut_viewer_load_lut(profile=profile)
						if verbose >= 1: safe_print(lang.getstr("success"))
					else:
						if verbose >= 1: safe_print(lang.getstr("failure"))
				else:
					if verbose >= 1: safe_print(lang.getstr("failure"))
					InfoDialog(self, msg=lang.getstr("profile.no_vcgt") + 
										 "\n" + path, 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
			else:
				setcfg("last_cal_path", path)
				if self.install_profile(capture_output=True, cal=path, 
										install=False, skip_scripts=True, 
										silent=True) is True:
					self.lut_viewer_load_lut(profile=cal_to_fake_profile(path))
					if verbose >= 1: safe_print(lang.getstr("success"))
				else:
					if verbose >= 1: safe_print(lang.getstr("failure"))

	def preview_handler(self, event=None, preview=False):
		if preview or self.preview.GetValue():
			cal = self.cal
		else:
			cal = self.previous_cal
			if self.cal == cal:
				cal = False
			elif not cal:
				cal = True
		if cal is False: # linear
			profile = None
		else:
			if cal is True: # display profile
				profile = self.get_display_profile()
			elif cal.lower().endswith(".icc") or \
				 cal.lower().endswith(".icm"):
				profile = ICCP.ICCProfile(cal)
			else:
				profile = cal_to_fake_profile(cal)
		if profile:
			if verbose >= 1:
				safe_print(lang.getstr("calibration.loading"))
				if profile.fileName:
					safe_print(profile.fileName)
		else:
			if verbose >= 1: safe_print(lang.getstr("calibration.resetting"))
		if self.install_profile(capture_output=True, cal=cal, install=False, 
								skip_scripts=True, silent=True) is True:
			self.lut_viewer_load_lut(profile=profile)
			if verbose >= 1: safe_print(lang.getstr("success"))
		else:
			if verbose >= 1: safe_print(lang.getstr("failure"))

	def install_profile(self, capture_output=False, cal=None, 
						profile_path=None, install=True, skip_scripts=False, 
						silent=False):
		cmd, args = self.worker.prepare_dispwin(cal, profile_path, install)
		if not isinstance(cmd, Exception): 
			if "-Sl" in args and (sys.platform != "darwin" or 
								  _intversion(mac_ver()[0].split(".")) >= (10, 6)):
				# If a 'system' install is requested under Linux or Windows, 
				# install in 'user' scope first because a system-wide install 
				# doesn't also set it as current user profile on those systems 
				# (on Mac OS X < 10.6, we can use ColorSyncScripting to set it).
				# It has the small drawback under Linux that it will copy the 
				# profile to both the user and system-wide locations, though,
				# which is not a problem under Windows as they are the same.
				args.remove("-Sl")
				result = self.worker.exec_cmd(cmd, args, capture_output, 
											  low_contrast=False, 
											  skip_scripts=skip_scripts, 
											  silent=silent)
				args.insert(0, "-Sl")
			else:
				result = True
			if result:
				result = self.worker.exec_cmd(cmd, args, capture_output, 
											  low_contrast=False, 
											  skip_scripts=skip_scripts, 
											  silent=silent)
		else:
			result = cmd
		if not isinstance(result, Exception) and \
		   result is not None and install:
			result = False
			for line in self.worker.output:
				if "Installed" in line:
					if sys.platform == "darwin" and "-Sl" in args and \
					   _intversion(mac_ver()[0].split(".")) < (10, 6):
						# The profile has been installed, but we need a little 
						# help from AppleScript to actually make it the default 
						# for the current user
						profile_name = os.path.basename(args[-1])
						for option in ["ColorSyncScripting"]:
							cmd, args = 'osascript', ['-e', 
								'set iccProfile to POSIX file "%s"' % 
								os.path.join(os.path.sep, "Library", 
											 "ColorSync", "Profiles", 
											 profile_name), '-e', 
											 'tell app "%s" to set '
											 'display profile of display %s to '
											 'iccProfile' % (option,
															 self.worker.get_display().split(",")[0])]
							result = self.worker.exec_cmd(cmd, args, 
														  capture_output=True, 
														  low_contrast=False, 
														  skip_scripts=True, 
														  silent=False)
							if result and not isinstance(result, Exception):
								break
					else:
						result = True
					break
			## Verify if LUT is actually loaded?
			# if "-c" in args:
				# args.remove("-c")
			# if "-I" in args:
				# args.remove("-I")
			# args.insert(-1, "-V")
			# result = self.worker.exec_cmd(cmd, args, capture_output=True, 
			# 								low_contrast=False, 
			# 								skip_scripts=True, silent=True)
			# if result:
				# result = False
				# for line in self.worker.output:
					# if line.find("'%s' IS loaded" % 
								 # args[-1].encode(enc, "safe_asciize")) >= 0:
						# result = True
						# break
		self.worker.wrapup(False)
		if not isinstance(result, Exception) and result:
			if install:
				if not silent:
					if verbose >= 1: safe_print(lang.getstr("success"))
					InfoDialog(self, 
							   msg=lang.getstr("profile.install.success"), 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-information"),
							   log=False)
				# try to create autostart script to load LUT curves on login
				n = self.worker.get_display()
				loader_args = "-d%s -c -L" % n
				if sys.platform == "win32":
					name = "%s Calibration Loader (Display %s)" % (appname, n)
					if autostart_home:
						loader_v01b = os.path.join(autostart_home, 
												   ("dispwin-d%s-c-L" % n) + 
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
					try:
						scut = pythoncom.CoCreateInstance(
							shell.CLSID_ShellLink, 
							None,
							pythoncom.CLSCTX_INPROC_SERVER, 
							shell.IID_IShellLink)
						scut.SetPath(cmd)
						if isexe:
							scut.SetIconLocation(exe, 0)
						else:
							scut.SetIconLocation(
								get_data_path(os.path.join("theme", "icons", 
														   appname + ".ico")), 
								0)
						scut.SetArguments(loader_args)
						scut.SetShowCmd(win32con.SW_SHOWMINNOACTIVE)
						if "-Sl" in args or sys.getwindowsversion() < (6, ):
							# Vista and later if using system scope, Win 2k/XP
							if autostart:
								try:
									scut.QueryInterface(
										pythoncom.IID_IPersistFile).Save(
											os.path.join(autostart, 
														 name + ".lnk"), 0)
								except Exception, exception:
									if not silent:
										InfoDialog(self,
												   msg=lang.getstr(
													   "error.autostart_creation", 
													   autostart) + "\n\n" + 
													   safe_unicode(exception.args[1]), 
												   ok=lang.getstr("ok"), 
												   bitmap=geticon(32, 
																  "dialog-warning"))
									# now try user scope
								else:
									return result
							else:
								if not silent:
									InfoDialog(self, 
											   msg=lang.getstr(
												   "error.autostart_system"), 
											   ok=lang.getstr("ok"), 
											   bitmap=geticon(32, 
															  "dialog-warning"))
						if autostart_home:
							scut.QueryInterface(
								pythoncom.IID_IPersistFile).Save(
									os.path.join(autostart_home, 
												 name + ".lnk"), 0)
						else:
							if not silent:
								InfoDialog(self, 
										   msg=lang.getstr(
											   "error.autostart_user"), 
										   ok=lang.getstr("ok"), 
										   bitmap=geticon(32, "dialog-warning"))
					except Exception, exception:
						if not silent:
							InfoDialog(self, 
									   msg=lang.getstr(
										   "error.autostart_creation", 
										   autostart_home) + "\n\n" + 
										   safe_unicode(exception.args[1]), 
									   ok=lang.getstr("ok"), 
									   bitmap=geticon(32, "dialog-warning"))
				elif sys.platform != "darwin":
					# http://standards.freedesktop.org/autostart-spec/autostart-spec-latest.html
					name = "%s-Calibration-Loader-Display-%s" % (appname, n)
					desktopfile_path = os.path.join(autostart_home, 
													name + ".desktop")
					exec_ = '"%s" %s' % (cmd, loader_args)
					try:
						# Always create user loader, even if we later try to 
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
						desktopfile.write((u'Name=%s Calibration Loader '
										   '(Display %s)\n' % 
										   (appname, n)).encode("UTF-8"))
						desktopfile.write((u'Comment=%s\n' % 
										   lang.getstr(
											   "calibrationloader.description", 
											   n)).encode("UTF-8"))
						desktopfile.write((u'Exec=%s\n' % 
										   exec_).encode("UTF-8"))
						desktopfile.close()
					except Exception, exception:
						if not silent:
							InfoDialog(self, 
									   msg=lang.getstr(
										   "error.autostart_creation", 
										   desktopfile_path) + "\n\n" + 
										   safe_unicode(exception), 
									   ok=lang.getstr("ok"), 
									   bitmap=geticon(32, "dialog-warning"))
					else:
						if "-Sl" in args and autostart:
							# copy system-wide loader
							system_desktopfile_path = os.path.join(
								autostart, name + ".desktop")
							if not silent and \
								(self.worker.exec_cmd("mkdir", 
													  ["-p", autostart], 
													  capture_output=True, 
													  low_contrast=False, 
													  skip_scripts=True, 
													  silent=True, 
													  asroot=True) is not True or 
								 self.worker.exec_cmd("mv", 
													  ["-f", 
													   desktopfile_path, 
													   autostart], 
													  capture_output=True, 
													  low_contrast=False, 
													  skip_scripts=True, 
													  silent=True, 
													  asroot=True) is not True):
								InfoDialog(self, 
										   msg=lang.getstr(
											   "error.autostart_creation", 
											   system_desktopfile_path), 
										   ok=lang.getstr("ok"), 
										   bitmap=geticon(32, "dialog-warning"))
			else:
				if not silent:
					if cal is False:
						InfoDialog(self, 
								   msg=lang.getstr("calibration.reset_success"), 
								   ok=lang.getstr("ok"), 
								   bitmap=geticon(32, "dialog-information"),
								   log=False)
					else:
						InfoDialog(self, 
								   msg=lang.getstr("calibration.load_success"), 
								   ok=lang.getstr("ok"), 
								   bitmap=geticon(32, "dialog-information"),
								   log=False)
		elif not silent:
			if install:
				if result is not None:
					if verbose >= 1: safe_print(lang.getstr("failure"))
					InfoDialog(self, msg=lang.getstr("profile.install.error"), 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"), log=False)
			else:
				if cal is False:
					InfoDialog(self, 
							   msg=lang.getstr("calibration.reset_error"), 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"), log=False)
				else:
					InfoDialog(self, msg=lang.getstr("calibration.load_error"), 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"), log=False)
		self.worker.pwd = None  # don't keep password in memory
		return result

	def verify_calibration_handler(self, event):
		if check_set_argyll_bin():
			self.setup_measurement(self.verify_calibration)

	def verify_calibration(self):
		safe_print("-" * 80)
		progress_msg = lang.getstr("calibration.verify")
		safe_print(progress_msg)
		self.worker.interactive = self.worker.get_instrument_features().get("sensor_cal")
		self.worker.start(self.result_consumer, 
						  self.verify_calibration_worker, 
						  progress_msg=progress_msg)
	
	def verify_calibration_worker(self):
		cmd, args = self.worker.prepare_dispcal(calibrate=False, verify=True)
		if not isinstance(cmd, Exception):
			result = self.worker.exec_cmd(cmd, args, capture_output=True, 
										  skip_scripts=True)
		else:
			result = cmd
		return result

	def verify_profile_handler(self, event):
		if not check_set_argyll_bin():
			return
			
		# select measurement data (ti1 or ti3)
		defaultDir, defaultFile = get_verified_path("profile_verification_chart")
		dlg = wx.FileDialog(self, lang.getstr("profile_verification_choose_chart"), 
							defaultDir=defaultDir, defaultFile=defaultFile, 
							wildcard=lang.getstr("filetype.ti1_ti3_txt") + 
									 "|*.cgats;*.ti1;*.ti3;*.txt", 
							style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		dlg.Center(wx.BOTH)
		result = dlg.ShowModal()
		if result == wx.ID_OK:
			chart = dlg.GetPath()
		dlg.Destroy()
		if result != wx.ID_OK:
			return
		setcfg("profile_verification_chart", chart)
		
		# select profile
		profile = None
		path = getcfg("calibration.file")
		if path:
			try:
				profile = ICCP.ICCProfile(path)
			except ICCP.ICCProfileInvalidError, exception:
				pass
		if not profile:
			profile = self.get_display_profile()
			if profile:
				path = profile.fileName
			else:
				path = None
		if not profile:
			defaultDir, defaultFile = get_verified_path(path)
			dlg = wx.FileDialog(self, lang.getstr("profile_verification_choose_profile"), 
								defaultDir=defaultDir, defaultFile=defaultFile, 
								wildcard=lang.getstr("filetype.icc") + "|*.icc;*.icm", 
								style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
			dlg.Center(wx.BOTH)
			result = dlg.ShowModal()
			if result == wx.ID_OK:
				path = dlg.GetPath()
			dlg.Destroy()
			if result != wx.ID_OK:
				return
			try:
				profile = ICCP.ICCProfile(path)
			except ICCP.ICCProfileInvalidError, exception:
				InfoDialog(self, msg=lang.getstr("profile.invalid") + 
								 "\n" + path, 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				return
		
		# lookup test patches
		ti3_ref = None
		rgb_labels = ('RGB_R', 'RGB_G', 'RGB_B')
		scale = 1.0
		try:
			cgats = CGATS.CGATS(chart, True)
			rgb = cgats.queryi(rgb_labels)
			if rgb:
				for i in rgb:
					for label in rgb_labels:
						if rgb[i][label] > 100:
							scale = 2.55
							break
				if scale > 1.0:
					for i in rgb:
						for label in rgb_labels:
							rgb[i][label] = rgb[i][label] / scale
				cgats[0].type = 'CTI1'
				cgats[0].COLOR_REP = 'RGB'
				ti1, ti3_ref, gray = self.worker.ti1_lookup_to_ti3(cgats, profile, "l")
			else:
				ti1, ti3_ref = self.worker.ti3_lookup_to_ti1(cgats, profile)
				gray = None
			##print ti3_ref
		except Exception, exception:
			InfoDialog(self, msg=safe_unicode(exception), 
					   ok=lang.getstr("ok"), bitmap=geticon(32, "dialog-error"))
			return
		if not ti3_ref:
			return
		
		# let the user choose a location for the result
		defaultFile = "verify_" + strftime("%Y-%m-%d_%H-%M.html")
		defaultDir = get_verified_path(None, 
									   os.path.join(getcfg("profile.save_path"), 
									   defaultFile))[0]
		dlg = wx.FileDialog(self, lang.getstr("save_as"), 
							defaultDir, defaultFile, wildcard="*.html", 
							style=wx.SAVE | wx.FD_OVERWRITE_PROMPT)
		dlg.Center(wx.BOTH)
		result = dlg.ShowModal()
		if result == wx.ID_OK:
			save_path = os.path.splitext(dlg.GetPath())[0] + ".html"
		dlg.Destroy()
		if result != wx.ID_OK:
			return
		# check if file(s) already exist
		if os.path.exists(save_path):
				dlg = ConfirmDialog(
					self, msg=lang.getstr("dialog.confirm_overwrite", 
										  save_path), 
					ok=lang.getstr("overwrite"), 
					cancel=lang.getstr("cancel"), 
					bitmap=geticon(32, "dialog-warning"))
				result = dlg.ShowModal()
				dlg.Destroy()
				if result != wx.ID_OK:
					return
		
		# setup for measurement
		self.setup_measurement(self.verify_profile, ti1, profile, ti3_ref, 
							   save_path, chart, gray)

	def verify_profile(self, ti1, profile, ti3_ref, save_path, chart, gray):
		safe_print("-" * 80)
		progress_msg = lang.getstr("profile.verify")
		safe_print(progress_msg)
		
		# setup temp dir
		temp = self.worker.create_tempdir()
		if isinstance(temp, Exception):
			show_result_dialog(temp, self)
			return
		
		# filenames
		name, ext = os.path.splitext(os.path.basename(save_path))
		ti1_path = os.path.join(temp, name + ".ti1")
		profile_path = os.path.join(temp, name + ".icc")
		
		# write ti1 to temp dir
		try:
			ti1_file = open(ti1_path, "w")
		except (IOError, OSError), exception:
			InfoDialog(self, msg=lang.getstr("error.file.create", 
											 ti1_path), 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-error"))
			self.worker.wrapup(False)
			return
		ti1_file.write(str(ti1))
		ti1_file.close()
		
		# write profile to temp dir
		profile.write(profile_path)
		
		# load calibration from profile
		cmd, args = self.worker.prepare_dispwin(profile_path=profile_path, 
												install=False)
		if isinstance(cmd, Exception):
			wx.CallAfter(show_result_dialog, result, self)
			self.Show()
		else:
			result = self.worker.exec_cmd(cmd, args, skip_scripts=True)
			if isinstance(cmd, Exception):
				wx.CallAfter(show_result_dialog, result, self)
				self.Show()
				return
		
			# start readings
			self.worker.dispread_after_dispcal = False
			self.worker.interactive = self.worker.get_instrument_features().get("sensor_cal")
			self.worker.start(self.verify_profile_consumer, 
							  self.verify_profile_worker, 
							  cargs=(os.path.splitext(ti1_path)[0] + ".ti3", 
									 profile, ti3_ref, save_path, chart, gray),
							  wargs=(ti1_path, ),
							  progress_msg=progress_msg)
	
	def verify_profile_worker(self, ti1_path):
		# measure
		cmd = get_argyll_util("dispread")
		args = ["-v"]
		self.worker.add_measurement_features(args)
		args += [os.path.splitext(ti1_path)[0]]
		return self.worker.exec_cmd(cmd, args, skip_scripts=True)
	
	def verify_profile_consumer(self, result, ti3_path, profile, ti3_ref, 
								save_path, chart, gray):
		
		if not isinstance(result, Exception) and result:
			# get item 0 of the ti3 to strip the CAL part from the measured data
			ti3_measured = CGATS.CGATS(ti3_path)[0]
			safe_print(lang.getstr("success"))
		
		# cleanup
		self.worker.wrapup(False)
		
		self.Show()
		
		if isinstance(result, Exception) or not result:
			if isinstance(result, Exception):
				wx.CallAfter(show_result_dialog, result, self)
			return
		
		# calculate amount of calibration grayscale tone values
		cal_entrycount = 256
		if "vcgt" in profile.tags:
			rgb = [[], [], []]
			vcgt = profile.tags.vcgt
			if "data" in vcgt:
				# table
				cal_entrycount = vcgt['entryCount']
				for i in range(0, cal_entrycount):
					for j in range(0, 3):
						rgb[j] += [float(vcgt['data'][j][i]) / (math.pow(256, vcgt['entrySize']) - 1) * 255]
			else:
				# formula
				step = 100.0 / 255.0
				for i in range(0, cal_entrycount):
					# float2dec(v) fixes miniscule deviations in the calculated gamma
					for j, name in enumerate(("red", "green", "blue")):
						vmin = float2dec(vcgt[name + "Min"] * 255)
						v = float2dec(math.pow(step * i / 100.0, vcgt[name + "Gamma"]))
						vmax = float2dec(vcgt[name + "Max"] * 255)
						rgb[j] += [float2dec(vmin + v * (vmax - vmin), 8)]
			cal_rgblevels = [len(set(round(n) for n in channel)) for channel in rgb]
		else:
			# should never happen
			cal_rgblevels = [0, 0, 0]
		
		offset = len(ti3_measured.DATA) - len(ti3_ref.DATA)
		if not chart.lower().endswith(".ti1"):
			# make the device values match
			for i in ti3_ref.DATA:
				for color in ("RGB_R", "RGB_G", "RGB_B"):
					ti3_ref.DATA[i][color] = ti3_measured.DATA[i + offset][color]
		
		adaption_matrix = "Bradford"
		
		# create a 'joined' ti3 from ref ti3, with XYZ values from measured ti3
		# this makes sure CMYK data in the original ref will be present in
		# the newly joined ti3
		ti3_joined = CGATS.CGATS(str(ti3_ref))[0]
		ti3_joined.LUMINANCE_XYZ_CDM2 = ti3_measured.LUMINANCE_XYZ_CDM2
		# add XYZ to DATA_FORMAT if not yet present
		labels_xyz = ("XYZ_X", "XYZ_Y", "XYZ_Z")
		if not "XYZ_X" in ti3_joined.DATA_FORMAT.values() and \
		   not "XYZ_Y" in ti3_joined.DATA_FORMAT.values() and \
		   not "XYZ_Z" in ti3_joined.DATA_FORMAT.values():
			ti3_joined.DATA_FORMAT.add_data(labels_xyz)
		# set XYZ in joined ti3 to XYZ of measurements
		for i in ti3_joined.DATA:
			for color in labels_xyz:
				ti3_joined.DATA[i][color] = ti3_measured.DATA[i + offset][color]
		
		wtpt_profile = tuple(n * 100 for n in profile.tags.wtpt.values())
		if "chad" in profile.tags:
			# undo chromatic adaption of profile whitepoint
			X, Y, Z = wtpt_profile
			M = colormath.Matrix3x3(profile.tags.chad).inverted()
			X = X * M[0][0] + Y * M[0][1] + Z * M[0][2]
			Y = X * M[1][0] + Y * M[1][1] + Z * M[1][2]
			Z = X * M[2][0] + Y * M[2][1] + Z * M[2][2]
			# normalize so that Y = 100
			wtpt_profile = tuple((n / Y) * 100 for n in (X, Y, Z))
		
		wtpt_measured = tuple(float(n) for n in ti3_joined.LUMINANCE_XYZ_CDM2.split())
		# normalize so that Y = 100
		wtpt_measured_norm = tuple((n / wtpt_measured[1]) * 100 for n in wtpt_measured)
		
		white_rgb = {'RGB_R': 100, 'RGB_G': 100, 'RGB_B': 100}
		white = ti3_joined.queryi(white_rgb)
		for i in white:
			white[i].update({'XYZ_X': wtpt_measured_norm[0], 
							 'XYZ_Y': wtpt_measured_norm[1], 
							 'XYZ_Z': wtpt_measured_norm[2]})
		
		# set Lab values
		labels_Lab = ("LAB_L", "LAB_A", "LAB_B")
		for data in (ti3_ref, ti3_joined):
			if "XYZ_X" in data.DATA_FORMAT.values() and \
			   "XYZ_Y" in data.DATA_FORMAT.values() and \
			   "XYZ_Z" in data.DATA_FORMAT.values():
				if not "LAB_L" in data.DATA_FORMAT.values() and \
				   not "LAB_A" in data.DATA_FORMAT.values() and \
				   not "LAB_B" in data.DATA_FORMAT.values():
					# add Lab fields to DATA_FORMAT if not present
					data.DATA_FORMAT.add_data(labels_Lab)
					has_Lab = False
				else:
					has_Lab = True
				if data is ti3_joined or not has_Lab:
					for i in data.DATA:
						X, Y, Z = [data.DATA[i][color] for color in labels_xyz]
						if data is ti3_joined:
							# we need to adapt the measured values to D50
							#print X, Y, Z, '->',
							X, Y, Z = [n * 100 for n in 
									   colormath.adapt(X, Y, Z, wtpt_measured_norm, 
													   matrix=adaption_matrix)]
							#print X, Y, Z
						Lab = XYZ2Lab(X, Y, Z)
						for j, color in enumerate(labels_Lab):
							data.DATA[i][color] = Lab[j]
		
		# read report template
		report_html_template_path = get_data_path(os.path.join("report", 
															   "report.html"))
		if not report_html_template_path:
			InfoDialog(self, msg=lang.getstr("file.missing", 
											 report_html_template_path), 
					   ok=lang.getstr("ok"), bitmap=geticon(32, "dialog-error"))
			return
		try:
			report_html_template = codecs.open(report_html_template_path, "r", 
										   "UTF-8")
		except (IOError, OSError), exception:
			InfoDialog(self, msg=lang.getstr("error.file.open", 
											 report_html_template_path), 
					   ok=lang.getstr("ok"), bitmap=geticon(32, "dialog-error"))
			return
		report_html = report_html_template.read()
		report_html_template.close()
		
		# create report
		report_html = report_html.replace("${DISPLAY}", 
										  self.display_ctrl.GetStringSelection())
		report_html = report_html.replace("${INSTRUMENT}", 
										  self.comport_ctrl.GetStringSelection())
		report_html = report_html.replace("${WHITEPOINT}", 
										  "%f %f %f" % wtpt_measured)
		report_html = report_html.replace("${WHITEPOINT_NORMALIZED}", 
										  "%f %f %f" % wtpt_measured_norm)
		report_html = report_html.replace("${PROFILE}", 
										  profile.getDescription())
		report_html = report_html.replace("${PROFILE_WHITEPOINT}", 
										  "%f %f %f" % wtpt_profile)
		report_html = report_html.replace("${TESTCHART}", 
										  os.path.basename(chart))
		report_html = report_html.replace("${ADAPTION}", 
										  str(adaption_matrix))
		report_html = report_html.replace("${DATETIME}", 
										  strftime("%Y-%m-%d %H:%M:%S"))
		report_html = report_html.replace("${REF}", 
										  str(ti3_ref).decode(enc, 
															  "replace").replace('"', 
																				 "&quot;"))
		report_html = report_html.replace("${MEASURED}", 
										  str(ti3_joined).decode(enc, 
																 "replace").replace('"', 
																					"&quot;"))
		report_html = report_html.replace("${CAL_ENTRYCOUNT}", 
										  str(cal_entrycount))
		report_html = report_html.replace("${CAL_RGBLEVELS}", 
										  repr(cal_rgblevels))
		report_html = report_html.replace("${GRAYSCALE}", 
										  repr(gray) if gray else 'null')
		for include in ("base.css", "compare.css", "compare-dark-light.css", 
						"compare-dark.css", "compare-light.css", 
						"compare-light-dark.css", "print.css", 
						"jsapi-packages.js", "jsapi-patches.js", 
						"compare.constants.js", "compare.variables.js", 
						"compare.functions.js", "compare.init.js"):
			path = get_data_path(os.path.join("report", include))
			if not path:
				InfoDialog(self, msg=lang.getstr("file.missing", 
												 include), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				return
			try:
				f = codecs.open(path, "r", "UTF-8")
			except (IOError, OSError), exception:
				InfoDialog(self, msg=lang.getstr("error.file.open", 
												 path), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				return
			if include.endswith(".js"):
				packer = jspacker.JavaScriptPacker()
				report_html = report_html.replace('src="%s">' % include, 
												  ">/*<![CDATA[*/\n" + 
												  packer.pack(f.read(), 
															  62, 
															  True).strip() + 
												  "\n/*]]>*/")
			else:
				report_html = report_html.replace('@import "%s";' % include, 
												  f.read().strip())
			f.close()
		
		# write report
		try:
			report_html_file = codecs.open(save_path, "w", "UTF-8")
		except (IOError, OSError), exception:
			InfoDialog(self, msg=lang.getstr("error.file.create", 
											 save_path), 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-error"))
			return
		report_html_file.write(report_html)
		report_html_file.close()
		
		# show report
		wx.CallAfter(launch_file, save_path)

	def load_cal(self, cal=None, silent=False):
		if not cal:
			cal = getcfg("calibration.file")
		if cal:
			if check_set_argyll_bin():
				if verbose >= 1: ## and silent:
					safe_print(lang.getstr("calibration.loading"))
					safe_print(cal)
				if self.install_profile(capture_output=True, cal=cal, 
										install=False, skip_scripts=True, 
										silent=silent) is True:
					self.lut_viewer_load_lut(profile=ICCP.ICCProfile(cal) if 
											 cal.lower().endswith(".icc") or 
											 cal.lower().endswith(".icm") else 
											 cal_to_fake_profile(cal))
					if verbose >= 1 and silent:
						safe_print(lang.getstr("success"))
					return True
				if verbose >= 1: ## and silent:
					safe_print(lang.getstr("failure"))
		return False

	def reset_cal(self, event=None):
		if check_set_argyll_bin():
			if verbose >= 1: ## and event is None:
				safe_print(lang.getstr("calibration.resetting"))
			if self.install_profile(capture_output=True, cal=False, 
									install=False, skip_scripts=True, 
									silent=True) is True: ## event is None or (
										## hasattr(self, "lut_viewer") and 
										## self.lut_viewer and 
										## self.lut_viewer.IsShownOnScreen())):
				self.lut_viewer_load_lut(profile=None)
				if verbose >= 1: ## and event is None:
					safe_print(lang.getstr("success"))
				return True
			if verbose >= 1: ## and event is None:
				safe_print(lang.getstr("failure"))
		return False

	def load_display_profile_cal(self, event=None):
		profile = self.get_display_profile()
		if check_set_argyll_bin():
			if verbose >= 1: ## and event is None:
				safe_print(
					lang.getstr("calibration.loading_from_display_profile"))
				if profile and profile.fileName:
					safe_print(profile.fileName)
			if self.install_profile(capture_output=True, cal=True, 
									install=False, skip_scripts=True, 
									silent=True) is True: ## event is None or (
										## hasattr(self, "lut_viewer") and 
										## self.lut_viewer and 
										## self.lut_viewer.IsShownOnScreen())):
				self.lut_viewer_load_lut(profile=profile)
				if verbose >= 1: ## and event is None:
					safe_print(lang.getstr("success"))
				return True
			if verbose >= 1: ## and event is None:
				safe_print(lang.getstr("failure"))
		return False

	def report_calibrated_handler(self, event):
		self.setup_measurement(self.report)

	def report_uncalibrated_handler(self, event):
		self.setup_measurement(self.report, False)

	def report(self, report_calibrated=True):
		if check_set_argyll_bin():
			safe_print("-" * 80)
			if report_calibrated:
				progress_msg = lang.getstr("report.calibrated")
			else:
				progress_msg = lang.getstr("report.uncalibrated")
			safe_print(progress_msg)
			self.worker.interactive = self.worker.get_instrument_features().get("sensor_cal")
			self.worker.start(self.result_consumer, self.report_worker, 
							  wkwargs={"report_calibrated": report_calibrated},
							  progress_msg=progress_msg)
	
	def report_worker(self, report_calibrated=True):
		cmd, args = self.worker.prepare_dispcal(calibrate=False)
		if isinstance(cmd, Exception):
			return cmd
		if args:
			if report_calibrated:
				args += ["-r"]
			else:
				args += ["-R"]
		return self.worker.exec_cmd(cmd, args, capture_output=True, 
									skip_scripts=True)
	
	def result_consumer(self, result):
		if isinstance(result, Exception) and result:
			wx.CallAfter(show_result_dialog, result, self)
		elif getcfg("log.autoshow"):
			wx.CallAfter(self.infoframe.Show)
		self.worker.wrapup(False)
		self.Show()

	def calibrate_btn_handler(self, event):
		if sys.platform == "darwin" or debug: self.focus_handler(event)
		if not getcfg("profile.update") and (not getcfg("calibration.update") or 
											 self.profile_update_cb.IsEnabled()):
			if getcfg("calibration.update") and \
			   self.profile_update_cb.IsEnabled():
				msg = lang.getstr("calibration.update_profile_choice")
				ok = lang.getstr("profile.update")
			else:
				msg = lang.getstr("calibration.create_fast_matrix_shaper_choice")
				ok = lang.getstr("calibration.create_fast_matrix_shaper")
			dlg = ConfirmDialog(self, 
								msg=msg,
								ok=ok, 
								alt=lang.getstr("button.calibrate"), 
								cancel=lang.getstr("cancel"), 
								bitmap=geticon(32, "dialog-question"))
			result = dlg.ShowModal()
			dlg.Destroy()
			if result == wx.ID_CANCEL:
				return
		else:
			result = None
		self.worker.dispcal_create_fast_matrix_shaper = result == wx.ID_OK
		self.update_profile_name_timer.Stop()
		if check_set_argyll_bin() and self.check_overwrite(".cal") and \
		   ((not getcfg("profile.update") and 
			 not self.worker.dispcal_create_fast_matrix_shaper) or 
			self.check_overwrite(profile_ext)):
			self.setup_measurement(self.just_calibrate)
		else:
			self.update_profile_name_timer.Start(1000)

	def just_calibrate(self):
		safe_print("-" * 80)
		safe_print(lang.getstr("button.calibrate"))
		if getcfg("calibration.interactive_display_adjustment") and \
		   not getcfg("calibration.update"):
			# Interactive adjustment, do not show progress dialog
			##self.just_calibrate_finish(self.calibrate(remove=True))
			self.worker.interactive = True
		else:
			self.worker.interactive = self.worker.get_instrument_features().get("sensor_cal")
		if True:
			# No interactive adjustment, show progress dialog
			self.measure_calibrate(self.just_calibrate_finish, self.calibrate, 
								   remove=True,
								   progress_msg=lang.getstr("calibration"))
	
	def just_calibrate_finish(self, result):
		start_timers = True
		if not isinstance(result, Exception) and result:
			if getcfg("log.autoshow"):
				wx.CallAfter(self.infoframe.Show)
			if getcfg("profile.update") or \
			   self.worker.dispcal_create_fast_matrix_shaper:
				start_timers = False
				wx.CallAfter(self.profile_finish, True, 
							 success_msg=lang.getstr("calibration.complete"))
			else:
				wx.CallAfter(InfoDialog, self, 
							 msg=lang.getstr("calibration.complete"), 
							 ok=lang.getstr("ok"), 
							 bitmap=geticon(32, "dialog-information"))
		else:
			if isinstance(result, Exception):
				wx.CallAfter(show_result_dialog, result, self)
			wx.CallAfter(InfoDialog, self, 
						 msg=lang.getstr("calibration.incomplete"), 
						 ok=lang.getstr("ok"), 
						 bitmap=geticon(32, "dialog-error"))
		self.Show(start_timers=start_timers)

	def setup_measurement(self, pending_function, *pending_function_args, 
						  **pending_function_kwargs):
		writecfg()
		if pending_function_kwargs.get("wrapup", True):
			self.worker.wrapup(False)
		if "wrapup" in pending_function_kwargs:
			del pending_function_kwargs["wrapup"]
		self.HideAll()
		self.set_pending_function(pending_function, *pending_function_args, 
								  **pending_function_kwargs)
		if sys.platform in ("darwin", "win32") or isexe:
			self.measureframe.Show()
		else:
			wx.CallAfter(self.measureframe_subprocess)
	
	def measureframe_subprocess(self):
		args = (u'"%s" "%s"' % (exe, 
								os.path.join(pydir, 
											 "wxMeasureFrame.py"))).encode(fs_enc)
		if wx.Display.GetCount() == 1:
			try:
				x_hostname, x_display, x_screen = util_x.get_display()
			except ValueError, exception:
				InfoDialog(self, msg=safe_unicode(exception), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				self.Show(start_timers=True)
				return
			args = "DISPLAY=%s:%s.%s %s" % (x_hostname, x_display,
											getcfg("display.number") - 1,
											args)
		returncode = -1
		try:
			p = sp.Popen(args, 
						 shell=True, 
						 stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)
		except Exception, exception:
			stderr = safe_str(exception)
		else:
			stdout, stderr = p.communicate()
			returncode = p.returncode
			config.initcfg()
			self.get_set_display()
		if returncode != 255:
			self.Show(start_timers=True)
			if stderr and stderr.strip():
				safe_print(stderr.strip())
		else:
			self.call_pending_function()
	
	def get_set_display(self):
		self.display_ctrl.SetSelection(
			min(max(0, len(self.worker.displays) - 1), 
				max(0, getcfg("display.number") - 1)))
		self.display_ctrl_handler(
			CustomEvent(wx.EVT_COMBOBOX.evtType[0], 
						self.display_ctrl))

	def set_pending_function(self, pending_function, *pending_function_args, 
							 **pending_function_kwargs):
		self.pending_function = pending_function
		self.pending_function_args = pending_function_args
		self.pending_function_kwargs = pending_function_kwargs

	def call_pending_function(self):
		# Needed for proper display updates under GNOME
		writecfg()
		if sys.platform in ("darwin", "win32") or isexe:
			self.measureframe.Hide()
		if debug:
			safe_print("[D] Calling pending function with args:", 
					   self.pending_function_args)
		wx.CallLater(100, self.pending_function, *self.pending_function_args, 
					 **self.pending_function_kwargs)

	def calibrate_and_profile_btn_handler(self, event):
		if sys.platform == "darwin" or debug: self.focus_handler(event)
		self.update_profile_name_timer.Stop()
		if check_set_argyll_bin() and self.check_overwrite(".cal") and \
		   self.check_overwrite(".ti3") and self.check_overwrite(profile_ext):
			self.setup_measurement(self.calibrate_and_profile)
		else:
			self.update_profile_name_timer.Start(1000)

	def calibrate_and_profile(self):
		safe_print("-" * 80)
		safe_print(lang.getstr("button.calibrate_and_profile").replace("&&", 
																	   "&"))
		self.worker.dispcal_create_fast_matrix_shaper = False
		self.worker.dispread_after_dispcal = True
		if getcfg("calibration.interactive_display_adjustment") and \
		   not getcfg("calibration.update"):
			# Interactive adjustment, do not show progress dialog
			##self.calibrate_finish(self.calibrate())
			self.worker.interactive = True
		else:
			self.worker.interactive = self.worker.get_instrument_features().get("sensor_cal")
		if True:
			# No interactive adjustment, show progress dialog
			self.measure_calibrate(self.calibrate_finish, self.calibrate, 
								   progress_msg=lang.getstr("calibration"), 
								   continue_next=True)
	
	def calibrate_finish(self, result):
		self.worker.interactive = not self.worker.get_needs_no_sensor_cal()
		if not isinstance(result, Exception) and result:
			self.measure(self.calibrate_and_profile_finish,
						 True, 
						 progress_msg=lang.getstr("measuring.characterization"), 
						 resume=True, continue_next=True)
		else:
			if isinstance(result, Exception):
				wx.CallAfter(show_result_dialog, result, self)
			wx.CallAfter(InfoDialog, self, 
						 msg=lang.getstr("calibration.incomplete"), 
						 ok=lang.getstr("ok"), 
						 bitmap=geticon(32, "dialog-error"))
			self.Show()
	
	def calibrate_and_profile_finish(self, result):
		start_timers = True
		if not isinstance(result, Exception) and result:
			start_timers = False
			wx.CallAfter(self.start_profile_worker, 
						 lang.getstr("calibration_profiling.complete"), 
						 resume=True)
		else:
			if isinstance(result, Exception):
				wx.CallAfter(show_result_dialog, result, self)
			wx.CallAfter(InfoDialog, self, 
						 msg=lang.getstr("profiling.incomplete"), 
						 ok=lang.getstr("ok"), 
						 bitmap=geticon(32, "dialog-error"))
		self.Show(start_timers=start_timers)

	def start_profile_worker(self, success_msg, resume=False):
		self.worker.interactive = False
		self.worker.start(self.profile_finish, self.profile, 
						  ckwargs={"success_msg": success_msg, 
								   "failure_msg": lang.getstr(
									   "profiling.incomplete")}, 
						  progress_msg=lang.getstr("create_profile"), 
						  resume=resume)

	def gamap_btn_handler(self, event):
		if not hasattr(self, "gamapframe"):
			self.init_gamapframe()
		if self.gamapframe.IsShownOnScreen():
			self.gamapframe.Raise()
		else:
			self.gamapframe.Center()
			self.gamapframe.SetPosition((-1, self.GetPosition()[1] + 
											 self.GetSize()[1] - 
											 self.gamapframe.GetSize()[1] - 
											 100))
			self.gamapframe.Show(not self.gamapframe.IsShownOnScreen())

	def profile_btn_handler(self, event):
		if sys.platform == "darwin" or debug: self.focus_handler(event)
		self.update_profile_name_timer.Stop()
		if check_set_argyll_bin() and self.check_overwrite(".ti3") and \
		   self.check_overwrite(profile_ext):
			apply_calibration = False
			dlg = ConfirmDialog(self, 
								msg=lang.getstr("dialog.current_cal_warning"), 
								ok=lang.getstr("continue"), 
								cancel=lang.getstr("cancel"), 
								bitmap=geticon(32, "dialog-warning"))
			dlg.reset_cal_ctrl = wx.CheckBox(dlg, -1, 
									   lang.getstr("calibration.reset"))
			dlg.sizer3.Add(dlg.reset_cal_ctrl, flag=wx.TOP | wx.ALIGN_LEFT, 
						   border=12)
			dlg.sizer0.SetSizeHints(dlg)
			dlg.sizer0.Layout()
			result = dlg.ShowModal()
			reset_cal = dlg.reset_cal_ctrl.GetValue()
			dlg.Destroy()
			if result == wx.ID_CANCEL:
				self.update_profile_name_timer.Start(1000)
				return
			if reset_cal:
				self.reset_cal()
			else:
				cal = getcfg("calibration.file")
				if cal:
					filename, ext = os.path.splitext(cal)
					if ext.lower() in (".icc", ".icm"):
						self.worker.options_dispcal = []
						try:
							profile = ICCP.ICCProfile(cal)
						except (IOError, ICCP.ICCProfileInvalidError), exception:
							InfoDialog(self, msg=lang.getstr("profile.invalid") + 
											 "\n" + path, 
									   ok=lang.getstr("ok"), 
									   bitmap=geticon(32, "dialog-error"))
							self.update_profile_name_timer.Start(1000)
							return
						else:
							# get dispcal options if present
							self.worker.options_dispcal = [
								"-" + arg for arg in 
								get_options_from_profile(profile)[0]]
					if os.path.exists(filename + ".cal") and \
					   can_update_cal(filename + ".cal"):
						apply_calibration = filename + ".cal"
			self.setup_measurement(self.just_profile, apply_calibration)
		else:
			self.update_profile_name_timer.Start(1000)

	def just_profile(self, apply_calibration):
		safe_print("-" * 80)
		safe_print(lang.getstr("button.profile"))
		self.worker.dispread_after_dispcal = False
		self.worker.interactive = self.worker.get_instrument_features().get("sensor_cal")
		self.previous_cal = False
		self.measure(self.just_profile_finish, apply_calibration,
					 progress_msg=lang.getstr("measuring.characterization"), 
					 continue_next=True)
	
	def just_profile_finish(self, result):
		start_timers = True
		if not isinstance(result, Exception) and result:
			start_timers = False
			wx.CallAfter(self.start_profile_worker, 
						 lang.getstr("profiling.complete"), resume=True)
		else:
			if isinstance(result, Exception):
				wx.CallAfter(show_result_dialog, result, self)
			wx.CallAfter(InfoDialog, self, 
						 msg=lang.getstr("profiling.incomplete"), 
						 ok=lang.getstr("ok"), 
						 bitmap=geticon(32, "dialog-error"))
		self.Show(start_timers=start_timers)

	def profile_finish(self, result, profile_path=None, success_msg="", 
					   failure_msg="", preview=True, skip_scripts=False):
		if not isinstance(result, Exception) and result:
			if getcfg("log.autoshow"):
				self.infoframe.Show()
			if not hasattr(self, "previous_cal") or self.previous_cal is False:
				self.previous_cal = getcfg("calibration.file")
			if profile_path:
				profile_save_path = os.path.splitext(profile_path)[0]
			else:
				profile_save_path = os.path.join(
										getcfg("profile.save_path"), 
										getcfg("profile.name.expanded"), 
										getcfg("profile.name.expanded"))
				profile_path = profile_save_path + profile_ext
			self.cal = profile_path
			filename, ext = os.path.splitext(profile_path)
			if ext.lower() in (".icc", ".icm"):
				has_cal = False
				try:
					profile = ICCP.ICCProfile(profile_path)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					InfoDialog(self, msg=lang.getstr("profile.invalid") + 
										 "\n" + profile_path, 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
					self.start_timers(True)
					self.previous_cal = False
					return
				else:
					has_cal = "vcgt" in profile.tags
					if profile.profileClass != "mntr" or \
					   profile.colorSpace != "RGB":
						InfoDialog(self, msg=success_msg, 
								   ok=lang.getstr("ok"), 
								   bitmap=geticon(32, "dialog-information"))
						self.start_timers(True)
						self.previous_cal = False
						return
					if getcfg("calibration.file") != profile_path:
						(options_dispcal, 
						 options_colprof) = get_options_from_profile(profile)
						if options_dispcal or options_colprof:
							cal = profile_save_path + ".cal"
							sel = self.calibration_file_ctrl.GetSelection()
							if options_dispcal and self.recent_cals[sel] == cal:
								self.recent_cals.remove(cal)
								self.calibration_file_ctrl.Delete(sel)
							if getcfg("settings.changed"):
								self.settings_discard_changes()
							if options_dispcal and options_colprof:
								self.load_cal_handler(None, path=profile_path, 
													  update_profile_name=False, 
													  silent=True,
													  load_vcgt=False)
							else:
								setcfg("calibration.file", profile_path)
								self.update_controls(update_profile_name=False)
			else:
				# .cal file
				has_cal = True
			# Always load calibration curves
			self.load_cal(cal=profile_path, silent=True)
			dlg = ConfirmDialog(self, msg=success_msg, 
								ok=lang.getstr("profile.install"), 
								cancel=lang.getstr("profile.do_not_install"), 
								bitmap=geticon(32, "dialog-information"))
			if preview and has_cal:
				# Show calibration preview checkbox
				self.preview = wx.CheckBox(dlg, -1, 
										   lang.getstr("calibration.preview"))
				self.preview.SetValue(True)
				dlg.Bind(wx.EVT_CHECKBOX, self.preview_handler, 
						 id=self.preview.GetId())
				dlg.sizer3.Add(self.preview, flag=wx.TOP | wx.ALIGN_LEFT, 
							   border=12)
				if LUTFrame:
					self.show_lut = wx.CheckBox(dlg, -1, 
												lang.getstr(
													"calibration.show_lut"))
					dlg.Bind(wx.EVT_CHECKBOX, self.show_lut_handler, 
							 id=self.show_lut.GetId())
					dlg.sizer3.Add(self.show_lut, flag=wx.TOP | wx.ALIGN_LEFT, 
								   border=4)
					if hasattr(self, "lut_viewer") and self.lut_viewer and \
					   self.lut_viewer.IsShownOnScreen():
						self.show_lut.SetValue(True)
					self.init_lut_viewer(profile=profile)
				if ext not in (".icc", ".icm") or \
				   getcfg("calibration.file") != profile_path:
					self.preview_handler(preview=True)
			if ((sys.platform == "darwin" or (sys.platform != "win32" and 
											  self.worker.argyll_version >= 
											  [1, 1, 0])) and 
				(os.geteuid() == 0 or which("sudo"))) or \
				(sys.platform == "win32" and 
				 sys.getwindowsversion() >= (6, ) and 
				 self.worker.argyll_version > 
				 [1, 1, 1]) or test:
				# Linux, OSX or Vista and later
				# NOTE: System install scope is currently not implemented
				# correctly in dispwin 1.1.0, but a patch is trivial and
				# should be in the next version
				self.install_profile_user = wx.RadioButton(
					dlg, -1, lang.getstr("profile.install_user"), 
					style=wx.RB_GROUP)
				self.install_profile_user.SetValue(
					getcfg("profile.install_scope") == "u")
				dlg.Bind(wx.EVT_RADIOBUTTON, 
						 self.install_profile_scope_handler, 
						 id=self.install_profile_user.GetId())
				dlg.sizer3.Add(self.install_profile_user, 
							   flag=wx.TOP | wx.ALIGN_LEFT, border=8)
				self.install_profile_systemwide = wx.RadioButton(
					dlg, -1, lang.getstr("profile.install_local_system"))
				self.install_profile_systemwide.SetValue(
					getcfg("profile.install_scope") == "l")
				dlg.Bind(wx.EVT_RADIOBUTTON, 
						 self.install_profile_scope_handler, 
						 id=self.install_profile_systemwide.GetId())
				dlg.sizer3.Add(self.install_profile_systemwide, 
							   flag=wx.TOP | wx.ALIGN_LEFT, border=4)
				if sys.platform == "darwin" and \
				   os.path.isdir("/Network/Library/ColorSync/Profiles"):
					self.install_profile_network = wx.RadioButton(
						dlg, -1, lang.getstr("profile.install_network"))
					self.install_profile_network.SetValue(
						getcfg("profile.install_scope") == "n")
					dlg.Bind(wx.EVT_RADIOBUTTON, 
							 self.install_profile_scope_handler, 
							 id=self.install_profile_network.GetId())
					dlg.sizer3.Add(self.install_profile_network, 
								   flag=wx.TOP | wx.ALIGN_LEFT, border=4)
			dlg.sizer0.SetSizeHints(dlg)
			dlg.sizer0.Layout()
			dlg.ok.SetDefault()
			result = dlg.ShowModal()
			dlg.Destroy()
			if result == wx.ID_OK:
				safe_print("-" * 80)
				safe_print(lang.getstr("profile.install"))
				self.install_profile(capture_output=True, 
									 profile_path=profile_path, 
									 skip_scripts=skip_scripts)
			elif preview:
				if getcfg("calibration.file"):
					# Load LUT curves from last used .cal file
					self.load_cal(silent=True)
				else:
					# Load LUT curves from current display profile (if any, 
					# and if it contains curves)
					self.load_display_profile_cal(None)
		else:
			if isinstance(result, Exception):
				show_result_dialog(result, self) 
			InfoDialog(self, msg=failure_msg, 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-error"))
		self.start_timers(True)
		self.previous_cal = False
		
	def init_lut_viewer(self, event=None, profile=None):
		if LUTFrame:
			if not hasattr(self, "lut_viewer") or not self.lut_viewer:
				self.lut_viewer = LUTFrame(
					None, -1, lang.getstr("calibration.lut_viewer.title"), 
					(getcfg("position.lut_viewer.x"), 
					 getcfg("position.lut_viewer.y")), 
					(getcfg("size.lut_viewer.w"), 
					 getcfg("size.lut_viewer.h")))
				self.lut_viewer.xLabel = lang.getstr("in")
				self.lut_viewer.yLabel = lang.getstr("out")
				self.lut_viewer.SetSaneGeometry(
					getcfg("position.lut_viewer.x"), 
					getcfg("position.lut_viewer.y"), 
					getcfg("size.lut_viewer.w"), 
					getcfg("size.lut_viewer.h"))
				icon = get_data_path(os.path.join("theme", "icons", "16x16", 
												  appname + ".png"))
				if icon:
					self.lut_viewer.SetIcon(wx.Icon(icon, wx.BITMAP_TYPE_PNG))
				self.lut_viewer.Bind(wx.EVT_MOVE, self.lut_viewer_move_handler)
				self.lut_viewer.Bind(wx.EVT_SIZE, self.lut_viewer_size_handler)
				self.lut_viewer.Bind(wx.EVT_CLOSE, 
									 self.lut_viewer_close_handler, 
									 self.lut_viewer)
			if not profile and not hasattr(self, "current_cal"):
				path = getcfg("calibration.file")
				if path:
					name, ext = os.path.splitext(path)
					if ext.lower() in (".icc", ".icm"):
						try:
							profile = ICCP.ICCProfile(path)
						except (IOError, ICCP.ICCProfileInvalidError), \
							   exception:
							InfoDialog(self, 
									   msg=lang.getstr("profile.invalid") + 
										   "\n" + path, 
									   ok=lang.getstr("ok"), 
									   bitmap=geticon(32, "dialog-error"))
							return
					else:
						profile = cal_to_fake_profile(path)
				else:
					profile = self.get_display_profile() or False
			self.show_lut_handler(profile=profile)
	
	def lut_viewer_load_lut(self, event=None, profile=None, force_draw=False):
		if LUTFrame:
			self.current_cal = profile
		if hasattr(self, "lut_viewer") and self.lut_viewer and \
		   (self.lut_viewer.IsShownOnScreen() or force_draw):
			force_update = False
			if getcfg("lut_viewer.show_actual_lut") and \
			   self.worker.argyll_version >= [1, 1, 0] and \
			   not "Beta" in self.worker.argyll_version_string:
				tmp = self.worker.create_tempdir()
				if isinstance(tmp, Exception):
					show_result_dialog(tmp, self)
					return
				cmd, args = (get_argyll_util("dispwin"), 
							 ["-d" + self.worker.get_display(), "-s", 
							  os.path.join(tmp, 
										   self.display_ctrl.GetStringSelection() or 
										   "LUT")])
				result = self.worker.exec_cmd(cmd, args, capture_output=True, 
											  skip_scripts=True, silent=True)
				if not isinstance(result, Exception) and result:
					profile = cal_to_fake_profile(args[-1])
					force_update = True
				else:
					if isinstance(result, Exception):
						safe_print(result)
				self.worker.wrapup(copy=False)
			if profile:
				if force_update or not self.lut_viewer.profile or \
				   not self.lut_viewer.profile.fileName or \
				   not profile.fileName or \
				   self.lut_viewer.profile.fileName != profile.fileName:
					self.lut_viewer.LoadProfile(profile)
					self.lut_viewer.DrawLUT()
			else:
				self.lut_viewer.LoadProfile(None)
				self.lut_viewer.DrawLUT()
	
	def show_lut_handler(self, event=None, profile=None):
		show = bool((hasattr(self, "show_lut") and self.show_lut and 
					 self.show_lut.GetValue()) or 
					((not hasattr(self, "show_lut") or 
					  not self.show_lut)))
		if not profile and hasattr(self, "current_cal"):
			profile = self.current_cal
		self.lut_viewer_load_lut(event, profile, force_draw=show)
		if hasattr(self, "lut_viewer") and self.lut_viewer:
			self.lut_viewer.Show(show)

	def lut_viewer_move_handler(self, event=None):
		if self.lut_viewer.IsShownOnScreen() and not \
		   self.lut_viewer.IsMaximized() and not self.lut_viewer.IsIconized():
			x, y = self.lut_viewer.GetScreenPosition()
			setcfg("position.lut_viewer.x", x)
			setcfg("position.lut_viewer.y", y)
		if event:
			event.Skip()
	
	def lut_viewer_size_handler(self, event=None):
		if self.lut_viewer.IsShownOnScreen() and not \
		   self.lut_viewer.IsMaximized() and not self.lut_viewer.IsIconized():
			w, h = self.lut_viewer.GetSize()
			setcfg("size.lut_viewer.w", w)
			setcfg("size.lut_viewer.h", h)
		if event:
			event.Skip()
	
	def lut_viewer_close_handler(self, event=None):
		self.lut_viewer.Hide()
		if hasattr(self, "show_lut") and self.show_lut:
			self.show_lut.SetValue(self.lut_viewer.IsShownOnScreen())
	
	def install_profile_scope_handler(self, event):
		if self.install_profile_systemwide.GetValue():
			setcfg("profile.install_scope", "l")
		elif sys.platform == "darwin" and \
			 os.path.isdir("/Network/Library/ColorSync/Profiles") and \
			 self.install_profile_network.GetValue():
			setcfg("profile.install_scope", "n")
		elif self.install_profile_user.GetValue():
			setcfg("profile.install_scope", "u")
	
	def start_timers(self, wrapup=False):
		if wrapup:
			self.worker.wrapup(False)
		self.plugplay_timer.Start(10000)
		self.update_profile_name_timer.Start(1000)
	
	def stop_timers(self):
		self.plugplay_timer.Stop()
		self.update_profile_name_timer.Stop()

	def comport_ctrl_handler(self, event=None):
		if debug and event:
			safe_print("[D] comport_ctrl_handler called for ID %s %s event "
					   "type %s %s" % (event.GetId(), 
									   getevtobjname(event, self), 
									   event.GetEventType(), 
									   getevttype(event)))
		if self.comport_ctrl.GetSelection() > -1:
			setcfg("comport.number", self.comport_ctrl.GetSelection() + 1)
		self.update_measurement_modes()

	def display_ctrl_handler(self, event):
		if debug:
			safe_print("[D] display_ctrl_handler called for ID %s %s event "
					   "type %s %s" % (event.GetId(), 
									   getevtobjname(event, self), 
									   event.GetEventType(), 
									   getevttype(event)))
		display_no = self.display_ctrl.GetSelection()
		profile = None
		if display_no > -1:
			setcfg("display.number", display_no + 1)
			if bool(int(getcfg("display_lut.link"))):
				self.display_lut_ctrl.SetStringSelection(self.displays[display_no])
				try:
					i = self.displays.index(
						self.display_lut_ctrl.GetStringSelection())
				except ValueError:
					i = min(0, self.display_ctrl.GetSelection())
				setcfg("display_lut.number", i + 1)
			profile = self.get_display_profile(display_no)
		self.lut_viewer_load_lut(profile=profile)

	def display_lut_ctrl_handler(self, event):
		if debug:
			safe_print("[D] display_lut_ctrl_handler called for ID %s %s event "
					   "type %s %s" % (event.GetId(), 
									   getevtobjname(event, self), 
									   event.GetEventType(), 
									   getevttype(event)))
		try:
			i = self.displays.index(self.display_lut_ctrl.GetStringSelection())
		except ValueError:
			i = min(0, self.display_ctrl.GetSelection())
		setcfg("display_lut.number", i + 1)

	def display_lut_link_ctrl_handler(self, event, link=None):
		if debug:
			safe_print("[D] display_lut_link_ctrl_handler called for ID %s %s "
					   "event type %s %s" % (event.GetId(), 
											 getevtobjname(event, self), 
											 event.GetEventType(), 
											 getevttype(event)))
		bitmap_link = geticon(16, "stock_lock")
		bitmap_unlink = geticon(16, "stock_lock-open")
		if link is None:
			link = not bool(int(getcfg("display_lut.link")))
		link = self.display_ctrl.GetCount() == 1 or (link and 
			self.display_lut_ctrl.GetCount() > 1)
		if link:
			self.display_lut_link_ctrl.SetBitmapLabel(bitmap_link)
			lut_no = self.display_ctrl.GetSelection()
		else:
			self.display_lut_link_ctrl.SetBitmapLabel(bitmap_unlink)
			try:
				lut_no = self.displays.index(
					self.display_lut_ctrl.GetStringSelection())
			except ValueError:
				lut_no = min(0, self.display_ctrl.GetSelection())
		self.display_lut_ctrl.SetSelection(lut_no)
		self.display_lut_ctrl.Enable(not link and 
									 self.display_lut_ctrl.GetCount() > 1)
		setcfg("display_lut.link", int(link))
		setcfg("display_lut.number", lut_no + 1)

	def measurement_mode_ctrl_handler(self, event=None):
		if debug:
			safe_print("[D] measurement_mode_ctrl_handler called for ID %s %s "
					   "event type %s %s" % (event.GetId(), 
											 getevtobjname(event, self), 
											 event.GetEventType(), 
											 getevttype(event)))
		v = self.get_measurement_mode()
		if v and "p" in v and self.worker.argyll_version < [1, 1, 0]:
			self.measurement_mode_ctrl.SetSelection(
				self.measurement_modes_ba[self.get_instrument_type()].get(
					defaults["measurement_mode"], 0))
			v = None
			InfoDialog(self, msg=lang.getstr("projector_mode_unavailable"), 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-information"))
		if v and "V" in v and self.worker.argyll_version < [1, 1, 0] or (
			 self.worker.argyll_version[0:3] == [1, 1, 0] and (
			 "Beta" in self.worker.argyll_version_string or 
			 "RC1" in self.worker.argyll_version_string or 
			 "RC2" in self.worker.argyll_version_string)):
			# adaptive emissive mode was added in RC3
			self.measurement_mode_ctrl.SetSelection(
				self.measurement_modes_ba[self.get_instrument_type()].get(
					defaults["measurement_mode"], 0))
			v = None
			InfoDialog(self, msg=lang.getstr("adaptive_mode_unavailable"), 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-information"))
		cal_changed = v != getcfg("measurement_mode") and \
					  getcfg("calibration.file") not in self.presets
		if cal_changed:
			self.cal_changed()
		setcfg("measurement_mode.adaptive", 1 if v and "V" in v else None)
		setcfg("measurement_mode.highres", 1 if v and "H" in v else None)
		setcfg("measurement_mode.projector", 1 if v and "p" in v else None)
		setcfg("measurement_mode", (strtr(v, {"V": "", 
											  "H": "", 
											  "p": ""}) if v else None) or None)
		if v and ((("l" in v or "p" in v) and 
			 float(self.get_black_point_correction()) > 0) or 
			("c" in v and 
			 float(self.get_black_point_correction()) == 0)) and \
		   getcfg("calibration.black_point_correction_choice.show"):
			if "c" in v:
				ok = lang.getstr("calibration.turn_on_black_point_correction")
			else:
				ok = lang.getstr("calibration.turn_off_black_point_correction")
			title = "calibration.black_point_correction_choice_dialogtitle"
			msg = "calibration.black_point_correction_choice"
			cancel = "calibration.keep_black_point_correction"
			dlg = ConfirmDialog(self, title=lang.getstr(title), 
								msg=lang.getstr(msg), ok=ok, 
								cancel=lang.getstr(cancel), 
								bitmap=geticon(32, "dialog-question"))
			chk = wx.CheckBox(dlg, -1, lang.getstr("dialog.do_not_show_again"))
			dlg.Bind(wx.EVT_CHECKBOX, 
					 self.black_point_correction_choice_dialog_handler, 
					 id=chk.GetId())
			dlg.sizer3.Add(chk, flag=wx.TOP | wx.ALIGN_LEFT, border=12)
			dlg.sizer0.SetSizeHints(dlg)
			dlg.sizer0.Layout()
			result = dlg.ShowModal()
			dlg.Destroy()
			if result == wx.ID_OK:
				if "c" in v:
					bkpt_corr = 1.0
				else:
					bkpt_corr = 0.0
				if not cal_changed and \
				   bkpt_corr != getcfg("calibration.black_point_correction"):
					self.cal_changed()
				setcfg("calibration.black_point_correction", bkpt_corr)
				self.update_controls(update_profile_name=False)
		self.update_profile_name()
	
	def black_point_correction_choice_dialog_handler(self, event):
		setcfg("calibration.black_point_correction_choice.show", 
			   int(not event.GetEventObject().GetValue()))

	def profile_type_ctrl_handler(self, event):
		if debug:
			safe_print("[D] profile_type_ctrl_handler called for ID %s %s "
					   "event type %s %s" % (event.GetId(), 
											 getevtobjname(event, self), 
											 event.GetEventType(), 
											 getevttype(event)))
		v = self.get_profile_type()
		self.gamap_btn.Enable(v in ("l", "x", "X"))
		self.profile_quality_ctrl.Enable(v not in ("g", "G"))
		if v in ("g", "G"):
			self.profile_quality_ctrl.SetValue(3)
			self.profile_quality_info.SetLabel(
				lang.getstr("calibration.quality.high"))
		if v != getcfg("profile.type"):
			self.profile_settings_changed()
		setcfg("profile.type", v)
		self.update_profile_name()
		self.set_default_testchart(force=True)
		self.check_testchart_patches_amount
	
	def check_testchart_patches_amount(self):
		recommended = {"G": 9,
					   "g": 11,
					   "l": 238,
					   "lh": 124,
					   "S": 36,
					   "s": 36,
					   "X": 238,
					   "Xh": 124,
					   "x": 238,
					   "xh": 124}
		# lower quality actually needs *higher* patchcount while high quality
		# can get away with fewer patches and still improved result
		recommended = recommended.get(self.get_profile_type() + 
									  self.get_profile_quality(), 
									  recommended[self.get_profile_type()])
		patches = int(self.testchart_patches_amount.GetLabel())
		if recommended > patches:
			self.profile_quality_ctrl.Disable()
			dlg = ConfirmDialog(
				self, msg=lang.getstr("profile.testchart_recommendation"), 
				ok=lang.getstr("OK"), cancel=lang.getstr("cancel"), 
				bitmap=geticon(32, "dialog-question"))
			result = dlg.ShowModal()
			self.profile_quality_ctrl.Enable(not getcfg("profile.update") and 
											 self.get_profile_type() not in 
											 ("g", "G"))
			dlg.Destroy()
			if result == wx.ID_OK:
				testchart = self.testchart_defaults[self.get_profile_type()].get(
					self.get_profile_quality(), 
					self.testchart_defaults[self.get_profile_type()][None])
				self.set_testchart(get_data_path(os.path.join("ti1", 
															  testchart)))

	def profile_name_ctrl_handler(self, event):
		if debug:
			safe_print("[D] profile_name_ctrl_handler called for ID %s %s "
					   "event type %s %s" % (event.GetId(), 
											 getevtobjname(event, self), 
											 event.GetEventType(), 
											 getevttype(event)))
		oldval = self.profile_name_textctrl.GetValue()
		if not self.check_profile_name() or len(oldval) > 255:
			wx.Bell()
			x = self.profile_name_textctrl.GetInsertionPoint()
			if oldval == "":
				newval = defaults.get("profile.name", "")
			else:
				newval = re.sub(r"[\\/:*?\"<>|]+", "", oldval)[:255]
			self.profile_name_textctrl.ChangeValue(newval)
			self.profile_name_textctrl.SetInsertionPoint(x - (len(oldval) - 
															  len(newval)))
		self.update_profile_name()

	def create_profile_name_btn_handler(self, event):
		self.update_profile_name()

	def profile_save_path_btn_handler(self, event):
		defaultPath = os.path.sep.join(get_verified_path("profile.save_path"))
		dlg = wx.DirDialog(self, lang.getstr("dialog.set_profile_save_path", 
						   getcfg("profile.name.expanded")), 
						   defaultPath=defaultPath)
		dlg.Center(wx.BOTH)
		if dlg.ShowModal() == wx.ID_OK:
			setcfg("profile.save_path", dlg.GetPath())
			self.update_profile_name()
		dlg.Destroy()
	
	def profile_name_info_btn_handler(self, event):
		if not hasattr(self, "profile_name_tooltip_window"):
			self.profile_name_tooltip_window = TooltipWindow(
				self, msg=self.profile_name_info(), 
				title=lang.getstr("profile.name"), 
				bitmap=geticon(32, "dialog-information"))
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
			"%pt	" + lang.getstr("profile.type"),
			"%tpa	" + lang.getstr("testchart.info")
		]
		if defaults["calibration.black_point_rate.enabled"]:
			info.insert(9, "%cA	" + lang.getstr("calibration.black_point_rate"))
		return lang.getstr("profile.name.placeholders") + "\n\n" + \
			   "\n".join(info)

	def create_profile_handler(self, event, path=None):
		if not check_set_argyll_bin():
			return
		if path is None:
			# select measurement data (ti3 or profile)
			defaultDir, defaultFile = get_verified_path("last_ti3_path")
			dlg = wx.FileDialog(self, lang.getstr("create_profile"), 
								defaultDir=defaultDir, defaultFile=defaultFile, 
								wildcard=lang.getstr("filetype.icc_ti3") + 
										 "|*.icc;*.icm;*.ti3", 
								style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
			dlg.Center(wx.BOTH)
			result = dlg.ShowModal()
			if result == wx.ID_OK:
				path = dlg.GetPath()
			dlg.Destroy()
		if path:
			if not os.path.exists(path):
				InfoDialog(self, msg=lang.getstr("file.missing", path), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				return
			# Get filename and extension of source file
			source_filename, source_ext = os.path.splitext(path)
			if source_ext.lower() != ".ti3":
				try:
					profile = ICCP.ICCProfile(path)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					InfoDialog(self, msg=lang.getstr("profile.invalid") + 
										 "\n" + path, 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
					return
				if (profile.tags.get("CIED", "") or 
					profile.tags.get("targ", ""))[0:4] != "CTI3":
					InfoDialog(self, 
							   msg=lang.getstr("profile.no_embedded_ti3") + 
								   "\n" + path, 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
					return
				ti3 = StringIO(profile.tags.get("CIED", "") or 
							   profile.tags.get("targ", ""))
			else:
				try:
					ti3 = open(path, "rU")
				except Exception, exception:
					InfoDialog(self, msg=lang.getstr("error.file.open", path), 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
					return
			ti3_lines = [line.strip() for line in ti3]
			ti3.close()
			if not "CAL" in ti3_lines:
				dlg = ConfirmDialog(self, 
									msg=lang.getstr("dialog.ti3_no_cal_info"), 
									ok=lang.getstr("continue"), 
									cancel=lang.getstr("cancel"), 
									bitmap=geticon(32, "dialog-warning"))
				result = dlg.ShowModal()
				dlg.Destroy()
				if result != wx.ID_OK: return
			setcfg("last_ti3_path", path)
			# let the user choose a location for the profile
			dlg = wx.FileDialog(self, lang.getstr("save_as"), 
								os.path.dirname(path), 
								os.path.basename(source_filename) + 
								profile_ext, 
								wildcard=lang.getstr("filetype.icc") + 
										 "|*.icc;*.icm", 
								style=wx.SAVE | wx.FD_OVERWRITE_PROMPT)
			dlg.Center(wx.BOTH)
			result = dlg.ShowModal()
			profile_save_path = os.path.split(dlg.GetPath())
			profile_save_path = os.path.join(profile_save_path[0], 
											 make_argyll_compatible_path(profile_save_path[1]))
			dlg.Destroy()
			if result == wx.ID_OK:
				filename, ext = os.path.splitext(profile_save_path)
				if ext.lower() != profile_ext:
					profile_save_path += profile_ext
					if os.path.exists(profile_save_path):
						dlg = ConfirmDialog(
							self, msg=lang.getstr("dialog.confirm_overwrite", 
												  (profile_save_path)), 
							ok=lang.getstr("overwrite"), 
							cancel=lang.getstr("cancel"), 
							bitmap=geticon(32, "dialog-warning"))
						result = dlg.ShowModal()
						dlg.Destroy()
						if result != wx.ID_OK:
							return
				setcfg("last_icc_path", profile_save_path)
				# get filename and extension of target file
				profile_name = os.path.basename(
					os.path.splitext(profile_save_path)[0])
				# create temporary working dir
				self.worker.wrapup(False)
				tmp_working_dir = self.worker.create_tempdir()
				if isinstance(tmp_working_dir, Exception):
					show_result_dialog(tmp_working_dir, self)
					return
				# Check directory and in/output file(s)
				result = check_create_dir(tmp_working_dir)
				if isinstance(result, Exception):
					show_result_dialog(result, self)
				# Copy ti3 to temp dir
				ti3_tmp_path = os.path.join(tmp_working_dir, 
											make_argyll_compatible_path(profile_name + 
																		".ti3"))
				self.worker.options_dispcal = []
				self.worker.options_targen = []
				display_name = None
				try:
					if source_ext.lower() == ".ti3":
						shutil.copyfile(path, ti3_tmp_path)
					else:
						# Binary mode because we want to avoid automatic 
						# newlines conversion
						ti3 = open(ti3_tmp_path, "wb") 
						ti3.write(profile.tags.get("CIED", "") or 
								  profile.tags.get("targ", ""))
						ti3.close()
						# Get dispcal options if present
						self.worker.options_dispcal = [
							"-" + arg for arg in 
							get_options_from_profile(profile)[0]]
						if "dmdd" in profile.tags:
							display_name = profile.getDeviceModelDescription()
					ti3 = CGATS.CGATS(ti3_tmp_path)
					if ti3.queryv1("COLOR_REP") and \
					   ti3.queryv1("COLOR_REP")[:3] == "RGB":
						self.worker.options_targen = ["-d3"]
				except Exception, exception:
					handle_error(u"Error - temporary .ti3 file could not be "
								 u"created: " + safe_unicode(exception), parent=self)
					self.worker.wrapup(False)
					return
				self.previous_cal = False
				safe_print("-" * 80)
				# Run colprof
				self.worker.interactive = False
				self.worker.start(
					self.profile_finish, self.profile, ckwargs={
						"profile_path": profile_save_path, 
						"success_msg": lang.getstr(
							"dialog.install_profile", 
							(profile_name, 
							 self.display_ctrl.GetStringSelection())), 
						"failure_msg": lang.getstr(
							"error.profile.file_not_created")}, 
					wkwargs={"dst_path": profile_save_path, 
							 "display_name": display_name}, 
					progress_msg=lang.getstr("create_profile"))
	
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
		profile_quality = getcfg("profile.quality")
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
			if "V" in measurement_mode:
				if len(measurement_mode) > 1:
					legacy_profile_name += "-"
				legacy_profile_name += lang.getstr("measurement_mode.adaptive").lower()
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
			display_short = display = display.split(" @")[0]
			if len(display_short) > 10:
				maxweight = 0
				for part in re.findall('[^\s_]+(?:\s*\d+)?', re.sub("\([^)]+\)", "", 
																	display)):
					digits = re.search("\d+", part)
					chars = re.sub("\d+", "", part)
					weight = len(chars) + (len(digits.group()) * 5 if digits else 0)
					if chars and weight > maxweight:
						# Weigh parts with digits higher than those without
						display_short = part
						maxweight = weight
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
			if "V" in measurement_mode:
				if len(measurement_mode) > 1:
					mode += "-"
				mode += lang.getstr("measurement_mode.adaptive")
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
		profile_name = profile_name.replace("%wp", 
											lang.getstr("native").lower() if 
											whitepoint is None else whitepoint)
		profile_name = profile_name.replace("%cb", 
											lang.getstr("max").lower() if 
											luminance is None else 
											luminance + u"cdm²")
		profile_name = profile_name.replace("%cB", 
											lang.getstr("min").lower() if 
											black_luminance is None else 
											black_luminance + u"cdm²")
		if trc not in ("l", "709", "s", "240"):
			if trc_type == "G":
				trc += " (%s)" % lang.getstr("trc.type.absolute").lower()
		else:
			trc = strtr(trc, {"l": "L", 
							  "709": "Rec. 709", 
							  "s": "sRGB", 
							  "240": "SMPTE240M"})
		profile_name = profile_name.replace("%cg", trc)
		profile_name = profile_name.replace("%ca", ambient + "lx" if ambient 
												   else "")
		f = int(float(black_output_offset) * 100)
		profile_name = profile_name.replace("%cf", str(f if f > 0 else 0) + 
												   "%")
		k = int(float(black_point_correction) * 100)
		profile_name = profile_name.replace("%ck", (str(k) + "% " if k > 0 and 
													k < 100 else "") + 
												   (lang.getstr("neutral") if 
													k > 0 else 
													lang.getstr("native")
												   ).lower())
		if black_point_rate and float(black_point_correction) < 1:
			profile_name = profile_name.replace("%cA", black_point_rate)
		aspects = {
			"c": calibration_quality,
			"p": profile_quality
		}
		msgs = {
			"u": "UQ", 
			"h": "HQ", 
			"m": "MQ", 
			"l": "LQ", 
			"v": "VLQ"
		}
		for a in aspects:
			profile_name = profile_name.replace("%%%sq" % a, msgs[aspects[a]])
		for q in msgs:
			pat = re.compile("(" + msgs[q] + ")\W" + msgs[q], re.I)
			profile_name = re.sub(pat, "\\1", profile_name)
		profile_type = {
			"G": "1xGamma+MTX",
			"g": "3xGamma+MTX",
			"l": "LabLUT",
			"S": "1xCurve+MTX",
			"s": "3xCurve+MTX",
			"X": "XYZLUT+MTX",
			"x": "XYZLUT"
		}.get(self.get_profile_type())
		if profile_type:
			profile_name = profile_name.replace("%pt", profile_type)
		profile_name = profile_name.replace("%tpa", 
											self.testchart_patches_amount.GetLabel())
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
				profile_name = profile_name.replace("%%%s" % directive, 
													strftime("%%%s" % 
															 directive))
			except UnicodeDecodeError:
				pass
		
		profile_name = re.sub("(\W?%s)+" % lang.getstr("native").lower(), 
							  "\\1", profile_name)
		
		return re.sub(r"[\\/:*?\"<>|]+", "_", profile_name)[:255]

	def update_profile_name(self, event=None):
		profile_name = self.create_profile_name()
		if not self.check_profile_name(profile_name):
			self.profile_name_textctrl.ChangeValue(getcfg("profile.name"))
			profile_name = self.create_profile_name()
			if not self.check_profile_name(profile_name):
				self.profile_name_textctrl.ChangeValue(
					defaults.get("profile.name", ""))
				profile_name = self.create_profile_name()
		profile_name = make_argyll_compatible_path(profile_name)
		if profile_name != self.profile_name.GetLabel():
			setcfg("profile.name", self.profile_name_textctrl.GetValue())
			self.profile_name.SetToolTipString(profile_name)
			self.profile_name.SetLabel(profile_name.replace("&", "&&"))
			setcfg("profile.name.expanded", profile_name)

	def check_profile_name(self, profile_name=None):
		if re.match(re.compile(r"^[^\\/:*?\"<>|]+$"), 
					profile_name if profile_name is not None else 
					self.create_profile_name()):
			return True
		else:
			return False

	def get_ambient(self):
		if self.ambient_viewcond_adjust_cb.GetValue():
			return str(stripzeros(
				self.ambient_viewcond_adjust_textctrl.GetValue().replace(",", 
																		 ".")))
		return None
	
	def get_instrument_type(self):
		# Return the instrument type, "color" (colorimeter) or "spect" 
		# (spectrometer)
		spect = self.worker.get_instrument_features().get("spectral", False)
		return "spect" if spect else "color"

	def get_measurement_mode(self):
		return self.measurement_modes_ab[self.get_instrument_type()].get(
			self.measurement_mode_ctrl.GetSelection())

	def get_profile_type(self):
		return self.profile_types_ab[self.profile_type_ctrl.GetSelection()]

	def get_whitepoint(self):
		if self.whitepoint_native_rb.GetValue():
			# Native
			return None
		elif self.whitepoint_colortemp_rb.GetValue():
			# Color temperature in kelvin
			return str(stripzeros(
				self.whitepoint_colortemp_textctrl.GetValue().replace(",", 
																	  ".")))
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
			return str(stripzeros(
				self.luminance_textctrl.GetValue().replace(",", ".")))

	def get_black_luminance(self):
		if self.black_luminance_min_rb.GetValue():
			return None
		else:
			return str(stripzeros(
				self.black_luminance_textctrl.GetValue().replace(",", ".")))

	def get_black_output_offset(self):
		return str(Decimal(self.black_output_offset_ctrl.GetValue()) / 100)

	def get_black_point_correction(self):
		return str(Decimal(self.black_point_correction_ctrl.GetValue()) / 100)

	def get_black_point_rate(self):
		if defaults["calibration.black_point_rate.enabled"]:
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
			return str(stripzeros(self.trc_textctrl.GetValue().replace(",", 
																	   ".")))
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
	
	def get_display_profile(self, display_no=None):
		if display_no is None:
			display_no = max(self.display_ctrl.GetSelection(), 0)
		try:
			return ICCP.get_display_profile(display_no)
		except Exception, exception:
			_safe_print("ICCP.get_display_profile(%s):" % display_no, 
						exception, fn=log)
			return None

	def get_profile_quality(self):
		return self.quality_ab[self.profile_quality_ctrl.GetValue() + 1]

	def profile_settings_changed(self):
		cal = getcfg("calibration.file")
		if cal:
			filename, ext = os.path.splitext(cal)
			if ext.lower() in (".icc", ".icm"):
				if not os.path.exists(filename + ".cal") and \
				   not cal in self.presets:
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
		if debug:
			safe_print("[D] testchart_ctrl_handler called for ID %s %s event "
					   "type %s %s" % (event.GetId(), 
									   getevtobjname(event, self), 
									   event.GetEventType(), 
									   getevttype(event)))
		self.set_testchart(self.testcharts[self.testchart_ctrl.GetSelection()])
		wx.CallAfter(self.check_testchart_patches_amount)

	def testchart_btn_handler(self, event, path=None):
		if path is None:
			defaultDir, defaultFile = get_verified_path("testchart.file")
			dlg = wx.FileDialog(self, lang.getstr("dialog.set_testchart"), 
								defaultDir=defaultDir, 
								defaultFile=defaultFile, 
								wildcard=lang.getstr("filetype.icc_ti1_ti3") + 
										 "|*.icc;*.icm;*.ti1;*.ti3", 
								style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
			dlg.Center(wx.BOTH)
			result = dlg.ShowModal()
			if result == wx.ID_OK:
				path = dlg.GetPath()
			dlg.Destroy()
		if path:
			if not os.path.exists(path):
				InfoDialog(self, msg=lang.getstr("file.missing", path), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				return
			filename, ext = os.path.splitext(path)
			if ext.lower() in (".icc", ".icm"):
				try:
					profile = ICCP.ICCProfile(path)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					InfoDialog(self, msg=lang.getstr("profile.invalid") + 
										 "\n" + path, 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
					return
				ti3_lines = [line.strip() for 
							 line in StringIO(profile.tags.get("CIED", "") or 
											  profile.tags.get("targ", ""))]
				if not "CTI3" in ti3_lines:
					InfoDialog(self, 
							   msg=lang.getstr("profile.no_embedded_ti3") + 
								   "\n" + path, 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
					return
			self.set_testchart(path)
			writecfg()
			self.profile_settings_changed()

	def create_testchart_btn_handler(self, event):
		if not hasattr(self, "tcframe"):
			self.init_tcframe()
		elif not hasattr(self.tcframe, "ti1") or \
			 getcfg("testchart.file") != self.tcframe.ti1.filename:
			self.tcframe.tc_load_cfg_from_ti1()
		setcfg("tc.show", 1)
		self.tcframe.Show()
		self.tcframe.Raise()
		return

	def init_tcframe(self):
		self.tcframe = TestchartEditor(self)

	def set_default_testchart(self, alert=True, force=False):
		path = getcfg("testchart.file")
		if os.path.basename(path) in self.dist_testchart_names:
			path = self.dist_testcharts[
				self.dist_testchart_names.index(os.path.basename(path))]
			if debug:
				safe_print("[D] set_default_testchart testchart.file:", path)
			setcfg("testchart.file", path)
		if force or lang.getstr(os.path.basename(path)) in [""] + \
		   self.default_testchart_names or not os.path.isfile(path):
			ti1 = self.testchart_defaults[self.get_profile_type()].get(
				self.get_profile_quality(), 
				self.testchart_defaults[self.get_profile_type()][None])
			path = get_data_path(os.path.join("ti1", ti1))
			if not path or not os.path.isfile(path):
				if alert:
					InfoDialog(self, 
							   msg=lang.getstr("error.testchart.missing", ti1), 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
				elif verbose >= 1:
					safe_print(lang.getstr("error.testchart.missing", ti1))
				return False
			else:
				self.set_testchart(path)
			return True
		return None

	def set_testcharts(self, path=None):
		idx = self.testchart_ctrl.GetSelection()
		self.testchart_ctrl.Freeze()
		self.testchart_ctrl.SetItems(self.get_testchart_names(path))
		self.testchart_ctrl.SetSelection(idx)
		self.testchart_ctrl.Thaw()

	def set_testchart(self, path=None):
		if path is None:
			path = getcfg("testchart.file")
		
		result = check_file_isfile(path)
		if isinstance(result, Exception):
			show_result_dialog(result, self)
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
				ti1 = CGATS.CGATS(ti3_to_ti1(profile.tags.get("CIED", "") or 
											 profile.tags.get("targ", "")))
			ti1_1 = verify_ti1_rgb_xyz(ti1)
			if not ti1_1:
				InfoDialog(self, 
						   msg=lang.getstr("error.testchart.invalid", path), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				self.set_default_testchart()
				return
			if path != getcfg("calibration.file"):
				self.profile_settings_changed()
			if debug:
				safe_print("[D] set_testchart testchart.file:", path)
			setcfg("testchart.file", path)
			if path not in self.testcharts:
				self.set_testcharts(path)
			# The case-sensitive index could fail because of 
			# case insensitive file systems, e.g. if the 
			# stored filename string is 
			# "C:\Users\Name\AppData\dispcalGUI\storage\MyFile"
			# but the actual filename is 
			# "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
			# (maybe because the user renamed the file)
			idx = index_fallback_ignorecase(self.testcharts, path)
			self.testchart_ctrl.SetSelection(idx)
			self.testchart_ctrl.SetToolTipString(path)
			if ti1.queryv1("COLOR_REP") and \
			   ti1.queryv1("COLOR_REP")[:3] == "RGB":
				self.worker.options_targen = ["-d3"]
			if self.testchart_ctrl.IsEnabled():
				self.testchart_patches_amount.SetLabel(
					str(ti1.queryv1("NUMBER_OF_SETS")))
			else:
				self.testchart_patches_amount.SetLabel("")
		except Exception, exception:
			error = traceback.format_exc() if debug else exception
			InfoDialog(self, 
					   msg=lang.getstr("error.testchart.read", path) + 
						   "\n\n" + safe_unicode(error), 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-error"))
			self.set_default_testchart()
		else:
			if hasattr(self, "tcframe") and \
			   self.tcframe.IsShownOnScreen() and \
			   (not hasattr(self.tcframe, "ti1") or 
				getcfg("testchart.file") != self.tcframe.ti1.filename):
				self.tcframe.tc_load_cfg_from_ti1()

	def get_testchart_names(self, path=None):
		testchart_names = []
		self.testcharts = []
		if path is None:
			path = getcfg("testchart.file")
		if os.path.exists(path):
			testchart_dir = os.path.dirname(path)
			try:
				testcharts = listdir_re(testchart_dir, 
										"\.(?:icc|icm|ti1|ti3)$")
			except Exception, exception:
				safe_print(u"Error - directory '%s' listing failed: %s" % 
						   tuple(safe_unicode(s) for s in (testchart_dir, 
														   exception)))
			else:
				for testchart_name in testcharts:
					if testchart_name not in testchart_names:
						testchart_names += [testchart_name]
						self.testcharts += [os.pathsep.join((testchart_name, 
															 testchart_dir))]
		default_testcharts = get_data_path("ti1", "\.(?:icc|icm|ti1|ti3)$")
		if isinstance(default_testcharts, list):
			for testchart in default_testcharts:
				testchart_dir = os.path.dirname(testchart)
				testchart_name = os.path.basename(testchart)
				if testchart_name not in testchart_names:
					testchart_names += [testchart_name]
					self.testcharts += [os.pathsep.join((testchart_name, 
														 testchart_dir))]
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

	def set_argyll_bin_handler(self, event):
		if set_argyll_bin():
			self.check_update_controls() or self.update_menus()
			if len(self.worker.displays):
				if getcfg("calibration.file"):
					# Load LUT curves from last used .cal file
					self.load_cal(silent=True)
				else:
					# Load LUT curves from current display profile (if any, 
					# and if it contains curves)
					self.load_display_profile_cal(None)

	def check_update_controls(self, event=None, silent=False):
		"""
		Update controls and menuitems when changes in displays or instruments
		are detected.
		
		Return True if update was needed and carried out, False otherwise.
		
		"""
		argyll_bin_dir = self.worker.argyll_bin_dir
		argyll_version = list(self.worker.argyll_version)
		displays = list(self.worker.displays)
		comports = list(self.worker.instruments)
		if silent:
			self.thread = delayedresult.startWorker(self.check_update_controls_consumer, 
													self.worker.enumerate_displays_and_ports, 
													cargs=(argyll_bin_dir, argyll_version, 
														   displays, comports), 
													wargs=(silent, ))
		else:
			self.worker.enumerate_displays_and_ports(silent)
			return self.check_update_controls_consumer(True, argyll_bin_dir,
													   argyll_version, displays, 
													   comports)
	
	def check_update_controls_consumer(self, result, argyll_bin_dir,
									   argyll_version, displays, comports):
		if argyll_bin_dir != self.worker.argyll_bin_dir or \
		   argyll_version != self.worker.argyll_version:
			self.update_black_point_rate_ctrl()
			self.update_profile_type_ctrl()
			self.profile_type_ctrl.SetSelection(
				self.profile_types_ba.get(getcfg("profile.type"), 
				self.profile_types_ba.get(defaults["profile.type"])))
			if hasattr(self, "aboutdialog"):
				self.aboutdialog.Destroy()
				del self.aboutdialog
		if displays != self.worker.displays:
			self.update_displays()
			if verbose >= 1: safe_print(lang.getstr("display_detected"))
		if comports != self.worker.instruments:
			self.update_comports()
			if verbose >= 1: safe_print(lang.getstr("comport_detected"))
		if displays != self.worker.displays or \
		   comports != self.worker.instruments:
			self.update_menus()
			self.update_main_controls()
			return True
		return False

	def plugplay_timer_handler(self, event):
		if debug:
			safe_print("[D] plugplay_timer_handler")
		self.check_update_controls(silent=True)

	def load_cal_handler(self, event, path=None, update_profile_name=True, 
						 silent=False, load_vcgt=True):
		if not check_set_argyll_bin():
			return
		if path is None:
			defaultDir, defaultFile = get_verified_path("last_cal_or_icc_path")
			dlg = wx.FileDialog(self, lang.getstr("dialog.load_cal"), 
								defaultDir=defaultDir, defaultFile=defaultFile, 
								wildcard=lang.getstr("filetype.cal_icc") + 
										 "|*.cal;*.icc;*.icm", 
								style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
			dlg.Center(wx.BOTH)
			if dlg.ShowModal() == wx.ID_OK:
				path = dlg.GetPath()
			dlg.Destroy()
		if path:
			if getcfg("settings.changed") and not self.settings_confirm_discard():
				return
			if not os.path.exists(path):
				sel = self.calibration_file_ctrl.GetSelection()
				if len(self.recent_cals) > sel and \
				   self.recent_cals[sel] == path:
					self.recent_cals.remove(self.recent_cals[sel])
					recent_cals = []
					for recent_cal in self.recent_cals:
						if recent_cal not in self.presets:
							recent_cals += [recent_cal]
					setcfg("recent_cals", os.pathsep.join(recent_cals))
					self.calibration_file_ctrl.Delete(sel)
					cal = getcfg("calibration.file") or ""
					# The case-sensitive index could fail because of 
					# case insensitive file systems, e.g. if the 
					# stored filename string is 
					# "C:\Users\Name\AppData\dispcalGUI\storage\MyFile"
					# but the actual filename is 
					# "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
					# (maybe because the user renamed the file)
					idx = index_fallback_ignorecase(self.recent_cals, cal)
					self.calibration_file_ctrl.SetSelection(idx)
				InfoDialog(self, msg=lang.getstr("file.missing", path), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				return

			filename, ext = os.path.splitext(path)
			if ext.lower() in (".icc", ".icm"):
				try:
					profile = ICCP.ICCProfile(path)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					InfoDialog(self, msg=lang.getstr("profile.invalid") + 
										 "\n" + path, 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
					return
				if profile.profileClass != "mntr" or \
				   profile.colorSpace != "RGB":
					InfoDialog(self, msg=lang.getstr("profile.unsupported", 
													 (profile.profileClass, 
													  profile.colorSpace)) + 
										 "\n" + path, 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
					return
				cal = StringIO(profile.tags.get("CIED", "") or 
							   profile.tags.get("targ", ""))
			else:
				try:
					cal = open(path, "rU")
				except Exception, exception:
					InfoDialog(self, msg=lang.getstr("error.file.open", path), 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
					return
			ti3_lines = [line.strip() for line in cal]
			cal.close()
			setcfg("last_cal_or_icc_path", path)
			if ext.lower() in (".icc", ".icm"):
				setcfg("last_icc_path", path)
				(options_dispcal, 
				 options_colprof) = get_options_from_profile(profile)
				if options_dispcal or options_colprof:
					if debug:
						safe_print("[D] options_dispcal:", options_dispcal)
					if debug:
						safe_print("[D] options_colprof:", options_colprof)
					# Parse options
					if options_dispcal:
						# Restore defaults
						self.restore_defaults_handler(
							include=("calibration", 
									 "measure.darken_background", 
									 "profile.update", 
									 "trc", 
									 "whitepoint"), 
							exclude=("calibration.black_point_correction_choice.show", 
									 "calibration.update", 
									 "measure.darken_background.show_warning", 
									 "trc.should_use_viewcond_adjust.show_msg"))
						self.worker.options_dispcal = ["-" + arg for arg 
													   in options_dispcal]
						for o in options_dispcal:
							if o[0] == "d":
								o = o[1:].split(",")
								setcfg("display.number", o[0])
								if len(o) > 1:
									setcfg("display_lut.number", o[1])
									setcfg("display_lut.link", 
										   int(o[0] == o[1]))
								else:
									setcfg("display_lut.number", o[0])
									setcfg("display_lut.link", 1)
								continue
							if o[0] == "c":
								setcfg("comport.number", o[1:])
								self.update_comports()
								continue
							if o[0] == "m":
								setcfg("calibration.interactive_display_adjustment", 0)
								continue
							##if o[0] == "o":
								##setcfg("profile.update", 1)
								##continue
							##if o[0] == "u":
								##setcfg("calibration.update", 1)
								##continue
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
								setcfg("calibration.black_output_offset", 
									   o[1:])
								continue
							if o[0] == "a":
								setcfg("calibration.ambient_viewcond_adjust", 1)
								setcfg("calibration.ambient_viewcond_adjust.lux", o[1:])
								continue
							if o[0] == "k":
								setcfg("calibration.black_point_correction", o[1:])
								continue
							if o[0] == "A":
								setcfg("calibration.black_point_rate", 
									   o[1:])
								continue
							if o[0] == "B":
								setcfg("calibration.black_luminance", 
									   o[1:])
								continue
							if o[0] in ("p", "P") and len(o[1:]) >= 5:
								setcfg("dimensions.measureframe", o[1:])
								setcfg("dimensions.measureframe.unzoomed", 
									   o[1:])
								continue
							if o[0] == "V":
								setcfg("measurement_mode.adaptive", 1)
								continue
							if o[0] == "H":
								setcfg("measurement_mode.highres", 1)
								continue
							if o[0] == "p" and len(o[1:]) == 0:
								setcfg("measurement_mode.projector", 1)
								continue
							if o[0] == "F":
								setcfg("measure.darken_background", 1)
								continue
					if options_colprof:
						# restore defaults
						self.restore_defaults_handler(
							include=("profile", "gamap_"), 
							exclude=("profile.update", "profile.name"))
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
					setcfg("calibration.file", path)
					if "CTI3" in ti3_lines:
						if debug:
							safe_print("[D] load_cal_handler testchart.file:", path)
						setcfg("testchart.file", path)
					self.update_controls(
						update_profile_name=update_profile_name)
					writecfg()

					if "vcgt" in profile.tags and load_vcgt:
						# load calibration into lut
						self.load_cal(cal=path, silent=True)
						if options_dispcal and options_colprof:
							return
						elif options_dispcal:
							msg = lang.getstr("settings_loaded.cal_and_lut")
						else:
							msg = lang.getstr("settings_loaded.profile_and_lut")
					elif options_dispcal and options_colprof:
						msg = lang.getstr("settings_loaded.cal_and_profile")
					elif options_dispcal:
						msg = lang.getstr("settings_loaded.cal")
					else:
						msg = lang.getstr("settings_loaded.profile")

					if not silent:
						InfoDialog(self, msg=msg + "\n" + path, ok=lang.getstr("ok"), 
								   bitmap=geticon(32, "dialog-information"))
					return
				else:
					sel = self.calibration_file_ctrl.GetSelection()
					if len(self.recent_cals) > sel and self.recent_cals[sel] == path:
						self.recent_cals.remove(self.recent_cals[sel])
						self.calibration_file_ctrl.Delete(sel)
						cal = getcfg("calibration.file") or ""
						# The case-sensitive index could fail because of 
						# case insensitive file systems, e.g. if the 
						# stored filename string is 
						# "C:\Users\Name\AppData\dispcalGUI\storage\MyFile"
						# but the actual filename is 
						# "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
						# (maybe because the user renamed the file)
						idx = index_fallback_ignorecase(self.recent_cals, cal)
						self.calibration_file_ctrl.SetSelection(idx)
					if "vcgt" in profile.tags and load_vcgt:
						# load calibration into lut
						self.load_cal(cal=path, silent=True)
					if not silent:
						InfoDialog(self, msg=lang.getstr("no_settings") + 
											 "\n" + path, 
								   ok=lang.getstr("ok"), 
								   bitmap=geticon(32, "dialog-error"))
					return

			setcfg("last_cal_path", path)

			# Restore defaults
			self.restore_defaults_handler(
				include=("calibration", 
						 "profile.update", 
						 "trc", 
						 "whitepoint"), 
				exclude=("calibration.black_point_correction_choice.show", 
						 "calibration.update", 
						 "trc.should_use_viewcond_adjust.show_msg"))

			self.worker.options_dispcal = []
			settings = []
			for line in ti3_lines:
				line = line.strip().split(" ", 1)
				if len(line) > 1:
					value = line[1][1:-1] # strip quotes
					if line[0] == "DEVICE_CLASS":
						if value != "DISPLAY":
							InfoDialog(self, 
									   msg=lang.getstr(
										   "calibration.file.invalid") + 
										   "\n" + path, 
									   ok=lang.getstr("ok"), 
									   bitmap=geticon(32, "dialog-error"))
							return
					elif line[0] == "DEVICE_TYPE":
						measurement_mode = value.lower()[0]
						if measurement_mode in ("c", "l"):
							setcfg("measurement_mode", measurement_mode)
							self.worker.options_dispcal += ["-y" + 
															measurement_mode]
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
								# Normalize to 0.0 - 1.0
								XYZ[i] = float(component) / 100
								i += 1
						except ValueError, exception:
							continue
						x, y, Y = XYZ2xyY(XYZ[0], XYZ[1], XYZ[2])
						k = XYZ2CCT(XYZ[0], XYZ[1], XYZ[2])
						if not lang.getstr("whitepoint") in settings:
							setcfg("whitepoint.colortemp", None)
							setcfg("whitepoint.x", stripzeros(round(x, 6)))
							setcfg("whitepoint.y", stripzeros(round(y, 6)))
							self.worker.options_dispcal += [
								"-w%s,%s" % (getcfg("whitepoint.x"), 
											 getcfg("whitepoint.y"))]
							settings += [lang.getstr("whitepoint")]
						setcfg("calibration.luminance", 
							   stripzeros(round(Y * 100, 3)))
						self.worker.options_dispcal += [
							"-b%s" % getcfg("calibration.luminance")]
						settings += [lang.getstr("calibration.luminance")]
					elif line[0] == "TARGET_GAMMA":
						setcfg("trc", None)
						if value in ("L_STAR", "REC709", "SMPTE240M", "sRGB"):
							setcfg("trc.type", "g")
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
						self.worker.options_dispcal += [
							"-" + getcfg("trc.type") + str(getcfg("trc"))]
						settings += [lang.getstr("trc")]
					elif line[0] == "DEGREE_OF_BLACK_OUTPUT_OFFSET":
						setcfg("calibration.black_output_offset", 
							   stripzeros(value))
						self.worker.options_dispcal += [
							"-f%s" % getcfg("calibration.black_output_offset")]
						settings += [
							lang.getstr("calibration.black_output_offset")]
					elif line[0] == "BLACK_POINT_CORRECTION":
						setcfg("calibration.black_point_correction", 
							   stripzeros(value))
						self.worker.options_dispcal += [
							"-k%s" % 
							getcfg("calibration.black_point_correction")]
						settings += [
							lang.getstr("calibration.black_point_correction")]
					elif line[0] == "TARGET_BLACK_BRIGHTNESS":
						setcfg("calibration.black_luminance", 
							   stripzeros(value))
						self.worker.options_dispcal += [
							"-B%s" % getcfg("calibration.black_luminance")]
						settings += [lang.getstr("calibration.black_luminance")]
					elif line[0] == "QUALITY":
						setcfg("calibration.quality", value.lower()[0])
						self.worker.options_dispcal += [
							"-q" + getcfg("calibration.quality")]
						settings += [lang.getstr("calibration.quality")]

			if len(settings) == 0:
				sel = self.calibration_file_ctrl.GetSelection()
				if len(self.recent_cals) > sel and \
				   self.recent_cals[sel] == path:
					self.recent_cals.remove(self.recent_cals[sel])
					self.calibration_file_ctrl.Delete(sel)
					cal = getcfg("calibration.file") or ""
					# The case-sensitive index could fail because of 
					# case insensitive file systems, e.g. if the 
					# stored filename string is 
					# "C:\Users\Name\AppData\dispcalGUI\storage\MyFile"
					# but the actual filename is 
					# "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
					# (maybe because the user renamed the file)
					idx = index_fallback_ignorecase(self.recent_cals, cal)
					self.calibration_file_ctrl.SetSelection(idx)
				writecfg()
				if not silent:
					InfoDialog(self, msg=lang.getstr("no_settings") + 
										 "\n" + path, 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
			else:
				setcfg("calibration.file", path)
				if "CTI3" in ti3_lines:
					if debug:
						safe_print("[D] load_cal_handler testchart.file:", path)
					setcfg("testchart.file", path)
				self.update_controls(update_profile_name=update_profile_name)
				writecfg()

				# load calibration into lut
				self.load_cal(silent=True)
				if not silent:
					InfoDialog(self, msg=lang.getstr("settings_loaded", 
													 ", ".join(settings)) + 
										 "\n" + path, 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-information"))

	def delete_calibration_handler(self, event):
		cal = getcfg("calibration.file")
		if cal and os.path.exists(cal):
			caldir = os.path.dirname(cal)
			try:
				dircontents = os.listdir(caldir)
			except Exception, exception:
				InfoDialog(self, msg=safe_unicode(exception), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				return
			self.related_files = {}
			for entry in dircontents:
				fn, ext = os.path.splitext(entry)
				if ext.lower() in (".app", script_ext):
					fn, ext = os.path.splitext(fn)
				if fn == os.path.splitext(os.path.basename(cal))[0]:
					self.related_files[entry] = True
			self.dlg = dlg = ConfirmDialog(
				self, msg=lang.getstr("dialog.confirm_delete"), 
				ok=lang.getstr("delete"), cancel=lang.getstr("cancel"), 
				bitmap=geticon(32, "dialog-warning"))
			if self.related_files:
				dlg.sizer3.Add((0, 8))
				for related_file in self.related_files:
					dlg.sizer3.Add((0, 4))
					chk = wx.CheckBox(dlg, -1, related_file)
					chk.SetValue(self.related_files[related_file])
					dlg.Bind(wx.EVT_CHECKBOX, 
							 self.delete_calibration_related_handler, 
							 id=chk.GetId())
					dlg.sizer3.Add(chk, flag=wx.ALIGN_LEFT, border=12)
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
							delete_related_files += [
								os.path.join(os.path.dirname(cal), 
											 related_file)]
				if sys.platform == "darwin":
					trashcan = lang.getstr("trashcan.mac")
				elif sys.platform == "win32":
					trashcan = lang.getstr("trashcan.windows")
				else:
					trashcan = lang.getstr("trashcan.linux")
				try:
					if (sys.platform == "darwin" and 
						len(delete_related_files) + 1 == len(dircontents) and 
						".DS_Store" in dircontents) or \
					   len(delete_related_files) == len(dircontents):
						# Delete whole folder
						deleted = trash([os.path.dirname(cal)])
					else:
						deleted = trash(delete_related_files)
					orphan_related_files = filter(lambda related_file:  
												  os.path.exists(related_file), 
												  delete_related_files)
					if orphan_related_files:
						InfoDialog(self, 
								   msg=lang.getstr("error.deletion", trashcan) + 
									   "\n\n" + 
									   "\n".join(os.path.basename(related_file) 
												 for related_file in 
												 orphan_related_files), 
								   ok=lang.getstr("ok"), 
								   bitmap=geticon(32, "dialog-error"))
				except TrashcanUnavailableError, exception:
					InfoDialog(self, 
							   msg=lang.getstr("error.trashcan_unavailable", 
											   trashcan), 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
				except Exception, exception:
					InfoDialog(self, 
							   msg=lang.getstr("error.deletion", trashcan) + 
								   "\n\n" + safe_unicode(exception), 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
				# The case-sensitive index could fail because of 
				# case insensitive file systems, e.g. if the 
				# stored filename string is 
				# "C:\Users\Name\AppData\dispcalGUI\storage\MyFile"
				# but the actual filename is 
				# "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
				# (maybe because the user renamed the file)
				idx = index_fallback_ignorecase(self.recent_cals, cal)
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
		self.related_files[chk.GetLabel()]=chk.GetValue()
	
	def aboutdialog_handler(self, event):
		if hasattr(self, "aboutdialog"):
			self.aboutdialog.Destroy()
		self.aboutdialog = AboutDialog(self, -1, 
									   lang.getstr("menu.about"), 
									   size=(100, 100))
		items = []
		items += [wx.StaticBitmap(self.aboutdialog, -1, 
								  getbitmap("theme/header-about"))]
		items += [wx.StaticText(self.aboutdialog, -1, "")]
		items += [wx.StaticText(self.aboutdialog, -1, u"%s © %s" % (appname, 
																	   author))]
		items += [wx.StaticText(self.aboutdialog, -1, u"%s %s" % (version,
																   build))]
		items += [wx.lib.hyperlink.HyperLinkCtrl(
			self.aboutdialog, -1, label="%s.hoech.net" % appname, 
			URL="http://%s.hoech.net" % appname)]
		items += [wx.StaticText(self.aboutdialog, -1, "")]
		items += [wx.StaticText(
			self.aboutdialog, -1, u"Argyll CMS © Graeme Gill")]
		items += [wx.StaticText(
			self.aboutdialog, -1, u"%s" % 
								  self.worker.argyll_version_string)]
		items += [wx.lib.hyperlink.HyperLinkCtrl(
			self.aboutdialog, -1, label="ArgyllCMS.com", 
			URL="http://www.argyllcms.com")]
		items += [wx.StaticText(self.aboutdialog, -1, "")]
		items += [wx.StaticText(self.aboutdialog, -1, 
								u"%s:" % lang.getstr("translations"))]
		lauthors = {}
		for lcode in lang.ldict:
			lauthor = lang.ldict[lcode].get("author", "")
			language = lang.ldict[lcode].get("language", "")
			if lauthor and language:
				if not lauthors.get(lauthor):
					lauthors[lauthor] = []
				lauthors[lauthor] += [language]
		lauthors = [(lauthors[lauthor], lauthor) for lauthor in lauthors]
		lauthors.sort()
		for langs, lauthor in lauthors:
			items += [wx.StaticText(self.aboutdialog, -1, 
									"%s - %s" % (", ".join(langs), lauthor))]
		items += [wx.StaticText(self.aboutdialog, -1, "")]
		match = re.match("([^(]+)\s*(\([^(]+\))?\s*(\[[^[]+\])?", sys.version)
		if match:
			pyver_long = match.groups()
		else:
			pyver_long = [sys.version]
		items += [wx.StaticText(self.aboutdialog, -1, 
								"Python " + pyver_long[0].strip())]
		if len(pyver_long) > 1:
			for part in pyver_long[1:]:
				if part:
					items += [wx.StaticText(self.aboutdialog, -1, part)]
		items += [wx.lib.hyperlink.HyperLinkCtrl(
			self.aboutdialog, -1, label="python.org", 
			URL="http://www.python.org")]
		items += [wx.StaticText(self.aboutdialog, -1, "")]
		items += [wx.StaticText(self.aboutdialog, -1, "wxPython " + 
													  wx.version())]
		items += [wx.lib.hyperlink.HyperLinkCtrl(
			self.aboutdialog, -1, label="wxPython.org", 
			URL="http://www.wxpython.org")]
		items += [wx.StaticText(self.aboutdialog, -1, "")]
		self.aboutdialog.add_items(items)
		self.aboutdialog.Layout()
		self.aboutdialog.Center()
		self.aboutdialog.Show()
	
	def readme_handler(self, event):
		launch_file(get_data_path("README.html"))
	
	def license_handler(self, event):
		license = get_data_path("LICENSE.txt")
		if not license:
			license = get_data_path("LICENSE.txt.gz")
		launch_file(license)
	
	def help_support_handler(self, event):
		launch_file("http://sourceforge.net/projects/dispcalgui/support")
	
	def bug_report_handler(self, event):
		launch_file("http://sourceforge.net/tracker/?group_id=257092&atid=1127028")
	
	def app_update_check_handler(self, event):
		if not hasattr(self, "app_update_check") or \
		   not self.app_update_check.isAlive():
			self.app_update_check = threading.Thread(target=app_update_check, 
													 args=(self, ))
			self.app_update_check.start()

	def infoframe_toggle_handler(self, event):
		setcfg("log.show", int(not self.infoframe.IsShownOnScreen()))
		self.infoframe.Show(getcfg("log.show"))
	
	def infoframe_autoshow_handler(self, event):
		setcfg("log.autoshow", int(self.menuitem_log_autoshow.IsChecked()))

	def HideAll(self):
		self.stop_timers()
		if hasattr(self, "gamapframe"):
			self.gamapframe.Hide()
		if hasattr(self, "aboutdialog"):
			self.aboutdialog.Hide()
		self.infoframe.Hide()
		if hasattr(self, "tcframe"):
			self.tcframe.Hide()
		if hasattr(self, "lut_viewer") and self.lut_viewer and \
		   self.lut_viewer.IsShownOnScreen():
			self.lut_viewer.Hide()
		self.Hide()

	def Show(self, show=True, start_timers=True):
		wx.Frame.Show(self, show)
		self.Raise()
		if not wx.GetApp().IsActive():
			self.RequestUserAttention()
		if hasattr(self, "tcframe"):
			self.tcframe.Show(getcfg("tc.show"))
		self.infoframe.Show(getcfg("log.show"))
		if start_timers:
			self.start_timers()

	def OnShow(self, event):
		self.SetFocus()

	def OnClose(self, event=None):
		if sys.platform == "darwin" or debug: self.focus_handler(event)
		if not hasattr(self, "tcframe") or self.tcframe.tc_close_handler():
			writecfg()
			if getattr(self, "thread", None) and self.thread.is_alive():
				self.Disable()
				if debug:
					safe_print("Waiting for child thread to exit...")
				self.thread.join()
			self.HideAll()
			if self.worker.tempdir and os.path.isdir(self.worker.tempdir):
				self.worker.wrapup(False)
			self.Destroy()

	def OnDestroy(self, event):
		if hasattr(self, "lut_viewer") and self.lut_viewer:
			self.lut_viewer.Hide()
			self.lut_viewer.Destroy()
		event.Skip()

class MainApp(wx.App):
	def OnInit(self):
		if sys.platform == "darwin" and not isapp:
			self.SetAppName("Python")
		else:
			self.SetAppName(appname)
		self.SetAssertMode(wx.PYAPP_ASSERT_SUPPRESS)
		wx_lang = getattr(wx, "LANGUAGE_" + lang.getstr("language_name"), 
						  wx.LANGUAGE_ENGLISH)
		##self.locale = wx.Locale(wx_lang)
		##if debug:
			##safe_print("[D]", lang.getstr("language_name"), wx_lang, 
					   ##self.locale.GetLocale())
		self.frame = MainFrame()
		self.SetTopWindow(self.frame)
		self.frame.Show()
		return True

def main():
	log("=" * 80)
	if verbose >= 1:
		safe_print(appname + runtype, version, build)
	log("Python " + sys.version)
	log("wxPython " + wx.version())
	try:
		
		# Force to run inside tty with the --terminal option
		if "--terminal" in sys.argv[1:]:
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
				if sys.platform == "win32":
					cmd = u'"%s"' % win32api.GetShortPathName(exe)
				else:
					cmd = u'"%s"' % exe
				cwd = None
			else:
				me = pypath
				if os.path.basename(exe) == "pythonw" + exe_ext:
					python = os.path.join(os.path.dirname(exe), 
										  "python" + exe_ext)
				if sys.platform == "win32":
					cmd = u'"%s" "%s"' % tuple(
						[win32api.GetShortPathName(path) for path in (python, 
																	  pypath)])
					cwd = win32api.GetShortPathName(pydir)
				else:
					cmd = u'"%s" "%s"' % (python, pypath)
					cwd = pydir.encode(fs_enc)
			safe_print("Re-launching instance in terminal")
			if sys.platform == "win32":
				cmd = u'start "%s" /WAIT %s' % (appname, cmd)
				if debug: safe_print("[D]", cmd)
				retcode = sp.call(cmd.encode(fs_enc), shell=True, cwd=cwd)
			elif sys.platform == "darwin":
				if debug: safe_print("[D]", cmd)
				retcode = mac_terminal_do_script(cmd)
			else:
				stdout = tempfile.SpooledTemporaryFile()
				retcode = None
				for terminal in terminals:
					if which(terminal):
						if debug:
							safe_print("[D] %s %s %s" % 
									   (terminal, terminals_opts[terminal], 
										cmd))
						stdout.write('%s %s %s' % 
									 (terminal, terminals_opts[terminal], 
									  cmd.encode(fs_enc)))
						retcode = sp.call(
							[terminal, terminals_opts[terminal]] + 
							cmd.encode(fs_enc).strip('"').split('" "'), 
							stdout=stdout, stderr=sp.STDOUT, cwd=cwd)
						stdout.write('\n\n')
						break
				stdout.seek(0)
			if retcode != 0:
				app = wx.App(redirect=False)
				if sys.platform == "win32":
					msg = (u'Even though %s is a GUI application, it needs to '
						   'be run from a command prompt. An attempt to '
						   'automatically launch a command prompt failed.' % me)
				elif sys.platform == "darwin":
					msg = (u'Even though %s is a GUI application, it needs to '
						   'be run from Terminal. An attempt to automatically '
						   'launch Terminal failed.' % me)
				else:
					if retcode is None:
						msg = (u'Even though %s is a GUI application, it needs '
							   'to be run from a terminal. An attempt to '
							   'automatically launch a terminal failed, '
							   'because none of those known seem to be '
							   'installed (%s).' % (me, ", ".join(terminals)))
					else:
						msg = (u'Even though %s is a GUI application, it needs '
							   'to be run from a terminal. An attempt to '
							   'automatically launch a terminal failed:\n\n%s' %
							   (me, unicode(stdout.read(), enc, "replace")))
				handle_error(msg)
		else:
			# Create main data dir if it does not exist
			if not os.path.exists(datahome):
				try:
					os.makedirs(datahome)
				except Exception, exception:
					handle_error("Warning - could not create directory '%s'" % 
								 datahome)
			if sys.platform not in ("darwin", "win32"):
				# Linux: Try and fix v0.2.1b calibration loader, because 
				# calibrationloader.sh is no longer present in v0.2.2b+
				desktopfile_name = appname + "-Calibration-Loader-Display-"
				if os.path.exists(autostart_home):
					try:
						autostarts = os.listdir(autostart_home)
					except Exception, exception:
						safe_print(u"Warning - directory '%s' listing failed: "
								   u"%s" % tuple(safe_unicode(s) for s in 
												 (autostarts, exception)))
					for filename in autostarts:
						if filename.startswith(desktopfile_name):
							try:
								desktopfile_path = os.path.join(autostart_home, 
																filename)
								cfg = ConfigParser.SafeConfigParser()
								cfg.optionxform = str
								cfg.read([desktopfile_path])
								exec_ = cfg.get("Desktop Entry", "Exec")
								if exec_.find("calibrationloader.sh") > -1:
									cfg.set(
										"Desktop Entry", "Exec", 
										re.sub('"[^"]*calibrationloader.sh"\s*', 
											   '', exec_, 1))
									cfgio = StringIO()
									cfg.write(cfgio)
									desktopfile = open(desktopfile_path, "w")
									cfgio.seek(0)
									desktopfile.write(cfgio.read().replace("=", 
													  "="))
									desktopfile.close()
							except Exception, exception:
								safe_print("Warning - could not process old "
										   "calibration loader:", 
										   safe_unicode(exception))
			# Initialize & run
			initcfg()
			lang.init()
			app = MainApp(redirect=False)  # Don't redirect stdin/stdout
			app.MainLoop()
	except Exception, exception:
		handle_error(u"Fatal error: " + safe_unicode(traceback.format_exc()))
	try:
		logger = logging.getLogger()
		for handler in logger.handlers:
			logger.removeHandler(handler)
		logging.shutdown()
	except Exception, exception:
		pass

if __name__ == "__main__":
	
	main()
