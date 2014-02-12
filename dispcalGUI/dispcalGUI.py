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

from __future__ import with_statement
import sys

# Standard modules

import datetime
import decimal
Decimal = decimal.Decimal
import glob
import httplib
import math
import os
import platform
if sys.platform == "darwin":
	from platform import mac_ver
import re
import shutil
import socket
import subprocess as sp
import threading
import traceback
import urllib
from hashlib import md5
from time import strftime, strptime, struct_time
from zlib import crc32

# 3rd party modules

import demjson

# Config
import config
from config import (autostart, autostart_home, btn_width_correction, build, 
					script_ext, defaults, enc, 
					exe, fs_enc, getbitmap, geticon, 
					get_ccxx_testchart, get_current_profile,
					get_display_profile, get_data_path, getcfg,
					get_verified_path, is_ccxx_testchart, is_profile,
					initcfg, isapp, isexe, profile_ext,
					pydir, resfiles, setcfg,
					writecfg)

# Custom modules

import CGATS
import ICCProfile as ICCP
import ccmx
import colord
import colormath
import localization as lang
import pyi_md5pickuphelper
import report
if sys.platform == "win32":
	import util_win
import wexpect
from argyll_cgats import (cal_to_fake_profile, can_update_cal, 
						  ti3_to_ti1, vcgt_to_cal,
						  verify_ti1_rgb_xyz)
from argyll_instruments import (get_canonical_instrument_name, instruments)
from argyll_names import viewconds
from colormath import (CIEDCCT2xyY, planckianCT2xyY, xyY2CCT, XYZ2CCT, XYZ2Lab, 
					   XYZ2xyY)
from debughelpers import ResourceError, getevtobjname, getevttype, handle_error
from edid import pnpidcache, get_manufacturer_name
from log import log, logbuffer, safe_print
from meta import (author, name as appname, domain, version, VERSION_BASE)
from options import debug, test, verbose
from ordereddict import OrderedDict
from trash import trash, TrashcanUnavailableError
from util_decimal import float2dec, stripzeros
from util_http import encode_multipart_formdata
from util_io import StringIOu as StringIO
from util_list import index_fallback_ignorecase, natsort
from util_os import (expanduseru, getenvu, is_superuser, launch_file, 
					 listdir_re, waccess, which)
from util_str import (ellipsis, safe_str, safe_unicode, strtr,
					  universal_newlines, wrap)
import util_x
from worker import (Error, Info, UnloggedInfo, Warn,
					Worker, check_create_dir,
					check_file_isfile,
					check_set_argyll_bin, check_ti3, check_ti3_criteria1,
					check_ti3_criteria2, get_argyll_util, get_options_from_cal,
					get_options_from_profile, get_options_from_ti3,
					make_argyll_compatible_path, parse_argument_string,
					set_argyll_bin, show_result_dialog)
from wxLUT3DFrame import LUT3DFrame
try:
	from wxLUTViewer import LUTFrame
except ImportError:
	LUTFrame = None
if sys.platform in ("darwin", "win32") or isexe:
	from wxMeasureFrame import MeasureFrame
from wxProfileInfo import ProfileInfoFrame
from wxReportFrame import ReportFrame
from wxSynthICCFrame import SynthICCFrame
from wxTestchartEditor import TestchartEditor
from wxaddons import wx, CustomEvent, CustomGridCellEvent, FileDrop
from wxwindows import (AboutDialog, BaseFrame, ConfirmDialog,
					   FileBrowseBitmapButtonWithChoiceHistory, InfoDialog,
					   LogWindow, ProgressDialog,
					   TooltipWindow)
try:
	import wx.lib.agw.floatspin as floatspin
except ImportError:
	import floatspin
import xh_floatspin

# wxPython
from wx import xrc
from wx.lib import delayedresult
from wx.lib.art import flagart
import wx.html
import wx.lib.hyperlink


if sys.platform == "darwin":
	FONTSIZE_LARGE = 11
	FONTSIZE_MEDIUM = 11
	FONTSIZE_SMALL = 10
else:
	FONTSIZE_LARGE = 10
	FONTSIZE_MEDIUM = 8
	FONTSIZE_SMALL = 8


def swap_dict_keys_values(mydict):
	""" Swap dictionary keys and values """
	return dict([(v, k) for (k, v) in mydict.iteritems()])


def app_update_check(parent=None, silent=False):
	""" Check for application update. Show an error dialog if a failure
	occurs. """
	safe_print(lang.getstr("update_check"))
	resp = http_request(parent, domain, "GET", "/VERSION",
						failure_msg=lang.getstr("update_check.fail"),
						silent=silent)
	if resp is False:
		return
	data = resp.read()
	try:
		newversion_tuple = tuple(int(n) for n in data.split("."))
	except ValueError:
		safe_print(lang.getstr("update_check.fail.version", domain))
		if not silent:
			wx.CallAfter(InfoDialog, parent, 
						 msg=lang.getstr("update_check.fail.version",
										 domain),
						 ok=lang.getstr("ok"), 
						 bitmap=geticon(32, "dialog-error"), log=False)
			return
	if newversion_tuple > VERSION_BASE:
		# Get changelog
		resp = http_request(parent, domain, "GET", "/README.html",
							silent=silent)
		if resp:
			readme = resp.read()
			chglog = re.search('<div id="(?:changelog|history)">'
							   '.+?<h2>.+?</h2>'
							   '.+?<dl>.+?</dd>', readme, re.S)
			if chglog:
				chglog = chglog.group().decode("utf-8", "replace")
				chglog = re.sub('<div id="(?:changelog|history)">', "", chglog)
				chglog = re.sub("<\/?d[l|d]>", "", chglog)
				chglog = re.sub("<(?:h2|dt)>.+?</(?:h2|dt)>", "", chglog)
				chglog = re.sub("<h3>.+?</h3>", "", chglog)
				chglog = re.sub("<h\d>(.+?)</h\d>", 
								"<p><strong>\\1</strong></p>", chglog)
		wx.CallAfter(app_update_confirm, parent, newversion_tuple, chglog)
	elif not silent:
		wx.CallAfter(app_uptodate, parent)
	else:
		safe_print(lang.getstr("update_check.uptodate", appname))


def app_uptodate(parent=None):
	""" Show a dialog confirming application is up-to-date """
	dlg = InfoDialog(parent, 
					 msg=lang.getstr("update_check.uptodate",
									 appname),
					 ok=lang.getstr("ok"), 
					 bitmap=geticon(32, "dialog-information"), show=False,
					 print_=True)
	update_check = wx.CheckBox(dlg, -1, 
							   lang.getstr("update_check.onstartup"))
	update_check.SetValue(getcfg("update_check"))
	dlg.Bind(wx.EVT_CHECKBOX, lambda event: setcfg("update_check", 
												   int(event.IsChecked())), 
			 id=update_check.GetId())
	dlg.sizer3.Add(update_check, flag=wx.TOP | wx.ALIGN_LEFT, border=12)
	dlg.sizer0.SetSizeHints(dlg)
	dlg.sizer0.Layout()
	dlg.ShowModalThenDestroy()
	if parent and getattr(parent, "menuitem_app_auto_update_check", None):
		parent.menuitem_app_auto_update_check.Check(bool(getcfg("update_check")))


def app_update_confirm(parent=None, newversion_tuple=(0, 0, 0, 0), chglog=None):
	""" Show a dialog confirming application update, with cancel option """
	dlg = ConfirmDialog(parent,
						msg=lang.getstr("update_check.new_version", 
						   ".".join(str(n) for n in newversion_tuple)), 
						ok=lang.getstr("go_to_website"), 
						cancel=lang.getstr("cancel"), 
						bitmap=geticon(32, "dialog-information"), 
						log=True,
						print_=True)
	if chglog:
		htmlwnd = wx.html.HtmlWindow(dlg, -1, size=(500, 300))
		htmlwnd.SetStandardFonts()
		htmlwnd.SetPage(chglog)
		dlg.sizer3.Add(htmlwnd, 1, flag=wx.TOP | wx.ALIGN_LEFT | wx.EXPAND, border=12)
	update_check = wx.CheckBox(dlg, -1, 
							   lang.getstr("update_check.onstartup"))
	update_check.SetValue(getcfg("update_check"))
	dlg.Bind(wx.EVT_CHECKBOX, lambda event: setcfg("update_check", 
												   int(event.IsChecked())), 
			 id=update_check.GetId())
	dlg.sizer3.Add(update_check, flag=wx.TOP | wx.ALIGN_LEFT, border=12)
	dlg.sizer0.SetSizeHints(dlg)
	dlg.sizer0.Layout()
	dlg.Center()
	if dlg.ShowModal() == wx.ID_OK:
		launch_file("http://" + domain)
	dlg.Destroy()
	if parent and getattr(parent, "menuitem_app_auto_update_check", None):
		parent.menuitem_app_auto_update_check.Check(bool(getcfg("update_check")))


def colorimeter_correction_web_check_choose(resp, parent=None):
	""" Let user choose a colorimeter correction and confirm overwrite """
	if resp is not False:
		data = resp.read()
		if data.strip().startswith("CC"):
			cgats = CGATS.CGATS(data)
		else:
			InfoDialog(parent, 
						 msg=lang.getstr("colorimeter_correction.web_check.failure"),
						 ok=lang.getstr("ok"), 
						 bitmap=geticon(32, "dialog-information"))
			return
	else:
		return
	dlg = ConfirmDialog(parent,
						msg=lang.getstr("colorimeter_correction.web_check.choose"), 
						ok=lang.getstr("ok"), 
						cancel=lang.getstr("cancel"), 
						bitmap=geticon(32, "dialog-information"), nowrap=True)
	dlg.list_ctrl = wx.ListCtrl(dlg, -1, size=(640, 150), style=wx.LC_REPORT | 
																wx.LC_SINGLE_SEL)
	dlg.list_ctrl.InsertColumn(0, lang.getstr("type"))
	dlg.list_ctrl.InsertColumn(1, lang.getstr("description"))
	dlg.list_ctrl.InsertColumn(2, lang.getstr("display.manufacturer"))
	dlg.list_ctrl.InsertColumn(3, lang.getstr("display"))
	dlg.list_ctrl.InsertColumn(4, lang.getstr("instrument"))
	dlg.list_ctrl.InsertColumn(5, lang.getstr("reference"))
	dlg.list_ctrl.InsertColumn(6, lang.getstr("created"))
	dlg.list_ctrl.SetColumnWidth(0, 50)
	dlg.list_ctrl.SetColumnWidth(1, 250)
	dlg.list_ctrl.SetColumnWidth(2, 150)
	dlg.list_ctrl.SetColumnWidth(3, 100)
	dlg.list_ctrl.SetColumnWidth(4, 75)
	dlg.list_ctrl.SetColumnWidth(5, 75)
	dlg.list_ctrl.SetColumnWidth(6, 150)
	for i in cgats:
		index = dlg.list_ctrl.InsertStringItem(i, "")
		dlg.list_ctrl.SetStringItem(index, 0, cgats[i].type.strip())
		dlg.list_ctrl.SetStringItem(index, 1, get_canonical_instrument_name(cgats[i].queryv1("DESCRIPTOR") or ""))
		dlg.list_ctrl.SetStringItem(index, 2, cgats[i].queryv1("MANUFACTURER") or "")
		dlg.list_ctrl.SetStringItem(index, 3, cgats[i].queryv1("DISPLAY"))
		dlg.list_ctrl.SetStringItem(index, 4, get_canonical_instrument_name(cgats[i].queryv1("INSTRUMENT") or ""))
		dlg.list_ctrl.SetStringItem(index, 5, get_canonical_instrument_name(cgats[i].queryv1("REFERENCE") or ""))
		created = cgats[i].queryv1("CREATED")
		if created:
			try:
				created = strptime(created)
			except ValueError:
				datetmp = re.search("\w+ (\w{3}) (\d{2}) (\d{2}(?::[0-5][0-9]){2}) (\d{4})",
									created)
				if datetmp:
					datetmp = "%s-%s-%s %s" % (datetmp.groups()[3],
											   {"Jan": "01",
												"Feb": "02",
												"Mar": "03",
												"Apr": "04",
												"May": "05",
												"Jun": "06",
												"Jul": "07",
												"Aug": "08",
												"Sep": "09",
												"Oct": "10",
												"Nov": "11",
												"Dec": "12"}.get(datetmp.groups()[0]),
												datetmp.groups()[1],
												datetmp.groups()[2])
					try:
						created = strptime(datetmp, "%Y-%m-%d %H:%M:%S")
					except ValueError:
						pass
			if isinstance(created, struct_time):
				created = strftime("%Y-%m-%d %H:%M:%S", created)
		dlg.list_ctrl.SetStringItem(index, 6, created or "")
	dlg.Bind(wx.EVT_LIST_ITEM_SELECTED, lambda event: dlg.ok.Enable(),
			 dlg.list_ctrl)
	dlg.Bind(wx.EVT_LIST_ITEM_DESELECTED, lambda event: dlg.ok.Disable(),
			 dlg.list_ctrl)
	dlg.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda event: dlg.EndModal(wx.ID_OK),
			 dlg.list_ctrl)
	dlg.sizer3.Add(dlg.list_ctrl, 1, flag=wx.TOP | wx.ALIGN_LEFT, border=12)
	if len(cgats) > 1:
		# We got several matches
		dlg.ok.Disable()
	else:
		item = dlg.list_ctrl.GetItem(0)
		dlg.list_ctrl.SetItemState(item.GetId(), wx.LIST_STATE_SELECTED, 
								   wx.LIST_STATE_SELECTED)
	dlg.sizer0.SetSizeHints(dlg)
	dlg.sizer0.Layout()
	dlg.Center()
	result = dlg.ShowModal()
	index = dlg.list_ctrl.GetNextItem(-1, wx.LIST_NEXT_ALL, 
										  wx.LIST_STATE_SELECTED)
	dlg.Destroy()
	if result != wx.ID_OK:
		return False
	# Important: Do not use parsed CGATS, order of keywords may be 
	# different than raw data so MD5 will be different
	cgats = re.sub("\n(CCMX|CCSS)( *\n)", "\n<>\n\\1\\2", data).split("\n<>\n")
	colorimeter_correction_check_overwrite(parent, cgats[index])


def colorimeter_correction_check_overwrite(parent=None, cgats=None):
	""" Check if a colorimeter correction file will be overwritten and 
	present a dialog to confirm or cancel the operation. Write the file. """
	result = check_create_dir(config.get_argyll_data_dir())
	if isinstance(result, Exception):
		show_result_dialog(result, parent)
		return
	descriptor = re.search('\nDESCRIPTOR\s+"(.+?)"\n', cgats)
	if descriptor:
		descriptor = descriptor.groups()[0]
	description = safe_unicode(descriptor or 
							   lang.getstr("unnamed"), "UTF-8")
	name = re.sub(r"[\\/:*?\"<>|]+", "_", 
				  make_argyll_compatible_path(description))[:255]
	path = os.path.join(config.get_argyll_data_dir(), 
						"%s.%s" % (name, cgats[:7].strip().lower()))
	if os.path.isfile(path):
		dlg = ConfirmDialog(parent,
							msg=lang.getstr("dialog.confirm_overwrite", path), 
							ok=lang.getstr("ok"), 
							cancel=lang.getstr("cancel"), 
							bitmap=geticon(32, "dialog-information"))
		result = dlg.ShowModal()
		dlg.Destroy()
		if result != wx.ID_OK:
			return False
	try:
		cgatsfile = open(path, 'wb')
		cgatsfile.write(cgats)
		cgatsfile.close()
	except EnvironmentError, exception:
		show_result_dialog(exception, parent)
		return False
	if getcfg("colorimeter_correction_matrix_file").split(":")[0] != "AUTO":
		setcfg("colorimeter_correction_matrix_file", ":" + path)
	parent.update_colorimeter_correction_matrix_ctrl_items(True)
	return True
	


def upload_colorimeter_correction(parent=None, params=None):
	""" Upload colorimeter correction to online database """
	path = "/colorimetercorrections/index.php"
	failure_msg = lang.getstr("colorimeter_correction.upload.failure")
	# Check for duplicate
	resp = http_request(parent, domain, "GET", path,
						# Remove CREATED date for calculating hash
						{"get": True, "hash": md5(re.sub('\nCREATED\s+".+?"\n', "\n\n",
														 safe_str(params['cgats'],
																  "UTF-8")).strip()).hexdigest()},
						silent=True)
	if resp and resp.read().strip().startswith("CC"):
		wx.CallAfter(InfoDialog, parent, 
					 msg=lang.getstr("colorimeter_correction.upload.exists"),
					 ok=lang.getstr("ok"), 
					 bitmap=geticon(32, "dialog-information"))
		return
	else:
		# Upload
		params['put'] = True
		resp = http_request(parent, domain, "POST", path, params, 
							failure_msg=failure_msg)
	if resp is not False:
		if resp.status == 201:
			wx.CallAfter(InfoDialog, parent, 
						 msg=lang.getstr("colorimeter_correction.upload.success"),
						 ok=lang.getstr("ok"), 
						 bitmap=geticon(32, "dialog-information"))
		else:
			wx.CallAfter(InfoDialog, parent, 
						 msg="\n\n".join([failure_msg, resp.read().strip()]),
						 ok=lang.getstr("ok"), 
						 bitmap=geticon(32, "dialog-error"))


def http_request(parent=None, domain=None, request_type="GET", path="", 
				 params=None, files=None, headers=None, charset="UTF-8", failure_msg="",
				 silent=False):
	""" HTTP request wrapper """
	if params is None:
		params = {}
	if files:
		content_type, params = encode_multipart_formdata(params.iteritems(),
														 files)
	else:
		for key in params:
			params[key] = safe_str(params[key], charset)
		params = urllib.urlencode(params)
	if headers is None:
		headers = {"User-Agent": "%s/%s" % (appname, version)}
		if request_type == "GET":
			path += '?' + params
			params = None
		else:
			if files:
				headers.update({"Content-Type": content_type,
								"Content-Length": str(len(params))})
			else:
				headers.update({"Content-Type": "application/x-www-form-urlencoded",
								"Accept": "text/plain"})
	conn = httplib.HTTPConnection(domain)
	try:
		conn.request(request_type, path, params, headers)
		resp = conn.getresponse()
	except (socket.error, httplib.HTTPException), exception:
		msg = " ".join([failure_msg, lang.getstr("connection.fail", 
												 " ".join([str(arg) for 
														   arg in exception.args]))]).strip()
		safe_print(msg)
		if not silent:
			wx.CallAfter(InfoDialog, parent, 
						 msg=msg,
						 ok=lang.getstr("ok"), 
						 bitmap=geticon(32, "dialog-error"), log=False)
		return False
	if resp.status >= 400:
		msg = " ".join([failure_msg,
						lang.getstr("connection.fail.http", 
									" ".join([str(resp.status),
											  resp.reason,
											  resp.read()]))]).strip()
		safe_print(msg)
		if not silent:
			wx.CallAfter(InfoDialog, parent, 
						 msg=msg,
						 ok=lang.getstr("ok"), 
						 bitmap=geticon(32, "dialog-error"), log=False)
		return False
	return resp


class ExtraArgsFrame(BaseFrame):

	""" Extra commandline arguments window. """
	
	def __init__(self, parent):
		self.res = xrc.XmlResource(get_data_path(os.path.join("xrc", 
															  "extra.xrc")))
		pre = wx.PreFrame()
		self.res.LoadOnFrame(pre, parent, "extra_args")
		self.PostCreate(pre)
		self.Bind(wx.EVT_CLOSE, self.OnClose, self)
		
		self.SetIcons(config.get_icon_bundle([256, 48, 32, 16], appname))
		
		self.set_child_ctrls_as_attrs(self)

		# Bind event handlers
		self.Bind(wx.EVT_TEXT, self.extra_args_handler, 
				   id=self.extra_args_dispcal_ctrl.GetId())
		self.Bind(wx.EVT_TEXT, self.extra_args_handler, 
				   id=self.extra_args_dispread_ctrl.GetId())
		self.Bind(wx.EVT_TEXT, self.extra_args_handler, 
				   id=self.extra_args_spotread_ctrl.GetId())
		self.Bind(wx.EVT_TEXT, self.extra_args_handler, 
				   id=self.extra_args_colprof_ctrl.GetId())
		self.Bind(wx.EVT_TEXT, self.extra_args_handler, 
				   id=self.extra_args_collink_ctrl.GetId())
		self.Bind(wx.EVT_TEXT, self.extra_args_handler, 
				   id=self.extra_args_targen_ctrl.GetId())
		
		self.setup_language()
		self.update_controls()
		self.update_layout()

	def OnClose(self, event):
		self.Hide()
	
	def extra_args_handler(self, event):
		mapping = {self.extra_args_dispcal_ctrl.GetId(): "extra_args.dispcal",
				   self.extra_args_dispread_ctrl.GetId(): "extra_args.dispread",
				   self.extra_args_spotread_ctrl.GetId(): "extra_args.spotread",
				   self.extra_args_colprof_ctrl.GetId(): "extra_args.colprof",
				   self.extra_args_collink_ctrl.GetId(): "extra_args.collink",
				   self.extra_args_targen_ctrl.GetId(): "extra_args.targen"}
		pref = mapping.get(event.GetId())
		if pref:
			setcfg(pref, self.FindWindowById(event.GetId()).Value)
	
	def update_controls(self):
		self.extra_args_dispcal_ctrl.ChangeValue(getcfg("extra_args.dispcal"))
		self.extra_args_dispread_ctrl.ChangeValue(getcfg("extra_args.dispread"))
		self.extra_args_spotread_ctrl.ChangeValue(getcfg("extra_args.spotread"))
		self.extra_args_colprof_ctrl.ChangeValue(getcfg("extra_args.colprof"))
		self.extra_args_collink_ctrl.ChangeValue(getcfg("extra_args.collink"))
		self.extra_args_targen_ctrl.ChangeValue(getcfg("extra_args.targen"))


class GamapFrame(BaseFrame):

	""" Gamut mapping options window. """
	
	def __init__(self, parent):
		self.res = xrc.XmlResource(get_data_path(os.path.join("xrc", 
															  "gamap.xrc")))
		pre = wx.PreFrame()
		self.res.LoadOnFrame(pre, parent, "gamapframe")
		self.PostCreate(pre)
		self.Bind(wx.EVT_CLOSE, self.OnClose, self)
		
		self.SetIcons(config.get_icon_bundle([256, 48, 32, 16], appname))

		self.panel = self.FindWindowByName("panel")
		
		self.set_child_ctrls_as_attrs(self)

		# Bind event handlers
		self.Bind(wx.EVT_CHECKBOX, self.gamap_perceptual_cb_handler, 
				   id=self.gamap_perceptual_cb.GetId())
		self.Bind(wx.EVT_CHOICE, self.gamap_perceptual_intent_handler, 
				   id=self.gamap_perceptual_intent_ctrl.GetId())
		self.Bind(wx.EVT_CHECKBOX, self.gamap_saturation_cb_handler, 
				   id=self.gamap_saturation_cb.GetId())
		self.Bind(wx.EVT_CHOICE, self.gamap_saturation_intent_handler, 
				   id=self.gamap_saturation_intent_ctrl.GetId())
		self.Bind(wx.EVT_CHOICE, self.gamap_src_viewcond_handler, 
				   id=self.gamap_src_viewcond_ctrl.GetId())
		self.Bind(wx.EVT_CHOICE, self.gamap_out_viewcond_handler, 
				   id=self.gamap_out_viewcond_ctrl.GetId())
		self.Bind(wx.EVT_CHOICE, self.gamap_default_intent_handler, 
				   id=self.gamap_default_intent_ctrl.GetId())

		self.viewconds_ab = OrderedDict()
		self.viewconds_ba = {}
		self.viewconds_out_ab = OrderedDict()
		
		self.intents_ab = OrderedDict()
		self.intents_ba = OrderedDict()
		
		self.default_intent_ab = {}
		self.default_intent_ba = {}
		for i, ri in enumerate(config.valid_values["gamap_default_intent"]):
			self.default_intent_ab[i] = ri
			self.default_intent_ba[ri] = i
		
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
				if event:
					# pre-select suitable viewing condition
					if profile.profileClass == "prtr":
						self.gamap_src_viewcond_ctrl.SetStringSelection(
							lang.getstr("gamap.viewconds.pp"))
					else:
						self.gamap_src_viewcond_ctrl.SetStringSelection(
							lang.getstr("gamap.viewconds.mt"))
					self.gamap_src_viewcond_handler()
		self.gamap_perceptual_cb.Enable()
		self.gamap_perceptual_intent_ctrl.Enable(self.gamap_perceptual_cb.GetValue())
		self.gamap_saturation_cb.Enable()
		self.gamap_saturation_intent_ctrl.Enable(self.gamap_saturation_cb.GetValue())
		c = self.gamap_perceptual_cb.GetValue() or \
			self.gamap_saturation_cb.GetValue()
		self.gamap_profile.Enable(c)
		self.gamap_src_viewcond_ctrl.Enable(p and c)
		self.gamap_out_viewcond_ctrl.Enable(p and c)
		self.gamap_default_intent_ctrl.Enable(p and c)
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

	def gamap_perceptual_intent_handler(self, event=None):
		v = self.intents_ba[self.gamap_perceptual_intent_ctrl.GetStringSelection()]
		if v != getcfg("gamap_perceptual_intent") and self.Parent and \
		   hasattr(self.Parent, "profile_settings_changed"):
			self.Parent.profile_settings_changed()
		setcfg("gamap_perceptual_intent", v)

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

	def gamap_saturation_intent_handler(self, event=None):
		v = self.intents_ba[self.gamap_saturation_intent_ctrl.GetStringSelection()]
		if v != getcfg("gamap_saturation_intent") and self.Parent and \
		   hasattr(self.Parent, "profile_settings_changed"):
			self.Parent.profile_settings_changed()
		setcfg("gamap_saturation_intent", v)

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
	
	def gamap_default_intent_handler(self, event=None):
		v = self.gamap_default_intent_ctrl.GetSelection()
		if (self.default_intent_ab[v] != getcfg("gamap_default_intent") and
			self.Parent and hasattr(self.Parent, "profile_settings_changed")):
			self.Parent.profile_settings_changed()
		setcfg("gamap_default_intent", self.default_intent_ab[v])
	
	def setup_language(self):
		"""
		Substitute translated strings for menus, controls, labels and tooltips.
		
		"""
		BaseFrame.setup_language(self)
		
		# Create the profile picker ctrl dynamically to get translated strings
		origpickerctrl = self.FindWindowByName("gamap_profile")
		hsizer = origpickerctrl.GetContainingSizer()
		self.gamap_profile = FileBrowseBitmapButtonWithChoiceHistory(
			self.panel, -1, toolTip=lang.getstr("gamap.profile"),
			dialogTitle=lang.getstr("gamap.profile"),
			fileMask=lang.getstr("filetype.icc") + "|*.icc;*.icm",
			changeCallback=self.gamap_profile_handler,
			history=get_data_path("ref", "\.(icm|icc)$"),
			name="gamap_profile")
		self.gamap_profile.SetMaxFontSize(11)
		hsizer.Replace(origpickerctrl, self.gamap_profile)
		origpickerctrl.Destroy()
		
		intents = ["a", "aa", "aw", "la", "ms", "p", "r", "s"]
		if (self.Parent and hasattr(self.Parent, "worker") and
			self.Parent.worker.argyll_version >= [1, 3, 3]):
			intents.append("pa")
		for v in sorted(intents):
			lstr = lang.getstr("gamap.intents.%s" % v)
			self.intents_ab[v] = lstr
			self.intents_ba[lstr] = v
		
		self.gamap_perceptual_intent_ctrl.SetItems(
			self.intents_ab.values())
		self.gamap_saturation_intent_ctrl.SetItems(
			self.intents_ab.values())
		
		self.viewconds_ab[None] = lang.getstr("default")
		self.viewconds_ba[lang.getstr("default")] = None
		for v in viewconds:
			lstr = lang.getstr("gamap.viewconds.%s" % v)
			self.viewconds_ab[v] = lstr
			self.viewconds_ba[lstr] = v
			if v not in ("pp", "pe", "pcd", "ob", "cx"):
				self.viewconds_out_ab[v] = lstr
		
		self.gamap_src_viewcond_ctrl.SetItems(
			self.viewconds_ab.values())
		self.gamap_out_viewcond_ctrl.SetItems(
			[lang.getstr("default")] + self.viewconds_out_ab.values())
		
		self.gamap_default_intent_ctrl.SetItems([lang.getstr("gamap.intents." + v)
												 for v in config.valid_values["gamap_default_intent"]])
	
	def update_controls(self):
		""" Update controls with values from the configuration """
		self.gamap_profile.SetPath(getcfg("gamap_profile"))
		self.gamap_perceptual_cb.SetValue(getcfg("gamap_perceptual"))
		self.gamap_perceptual_intent_ctrl.SetStringSelection(
			self.intents_ab.get(getcfg("gamap_perceptual_intent"), 
			self.intents_ab.get(defaults["gamap_perceptual_intent"])))
		self.gamap_saturation_cb.SetValue(getcfg("gamap_saturation"))
		self.gamap_saturation_intent_ctrl.SetStringSelection(
			self.intents_ab.get(getcfg("gamap_saturation_intent"), 
			self.intents_ab.get(defaults["gamap_saturation_intent"])))
		self.gamap_src_viewcond_ctrl.SetStringSelection(
			self.viewconds_ab.get(getcfg("gamap_src_viewcond", False), 
			self.viewconds_ab.get(defaults.get("gamap_src_viewcond"))))
		self.gamap_out_viewcond_ctrl.SetStringSelection(
			self.viewconds_ab.get(getcfg("gamap_out_viewcond"), 
			self.viewconds_ab.get(defaults.get("gamap_out_viewcond"))))
		self.gamap_default_intent_ctrl.SetSelection(self.default_intent_ba[getcfg("gamap_default_intent")])
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
				missing += [filename]
			elif ext.lower() == ".ti1":
				self.dist_testcharts += [path]
				self.dist_testchart_names += [os.path.basename(path)]
			wx.GetApp().progress_dlg.Pulse()
		if missing:
			raise ResourceError(safe_str(lang.getstr("resources.notfound.warning") + "\n" +
								"\n".join(missing)))
		wx.GetApp().progress_dlg.Pulse()
		
		# Create main worker instance
		wx.GetApp().progress_dlg.Pulse()
		self.worker = Worker(None)
		wx.GetApp().progress_dlg.Pulse()
		self.worker.enumerate_displays_and_ports(enumerate_ports=getcfg("enumerate_ports.auto"))
		wx.GetApp().progress_dlg.Pulse()
		
		# Initialize GUI
		if verbose >= 1:
			safe_print(lang.getstr("initializing_gui"))
		wx.GetApp().progress_dlg.Pulse(lang.getstr("initializing_gui"))
		wx.GetApp().progress_dlg.stop_timer()
		self.res = xrc.XmlResource(get_data_path(os.path.join("xrc", 
															  "main.xrc")))
		self.res.InsertHandler(xh_floatspin.FloatSpinCtrlXmlHandler())
		pre = wx.PreFrame()
		self.res.LoadOnFrame(pre, None, "mainframe")
		self.PostCreate(pre)
		self.worker.owner = self
		self.init_frame()
		self.init_defaults()
		self.init_infoframe()
		if sys.platform in ("darwin", "win32") or isexe:
			self.init_measureframe()
		self.init_menus()
		self.init_controls()
		self.show_advanced_calibration_options_handler()
		self.setup_language()
		self.update_displays(update_ccmx_items=False)
		BaseFrame.update_layout(self)
		# Add the header bitmap after layout so it won't stretch the window 
		# further than necessary
		self.headerbitmap = self.panel.FindWindowByName("headerbitmap")
		self.headerbitmap.SetBitmap(getbitmap("theme/header"))
		self.calpanel.SetScrollRate(2, 2)
		self.update_comports()
		self.update_controls(update_ccmx_items=False)
		self.SetSaneGeometry(int(getcfg("position.x")), 
							 int(getcfg("position.y")))
		self.Bind(wx.EVT_MOVE, self.OnMove, self)
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
		wx.GetApp().progress_dlg.stop_timer()
		wx.GetApp().progress_dlg.Close()
		
		# Check for updates if configured
		if getcfg("update_check"):
			self.app_update_check_handler(None, silent=True)
	
	def log(self):
		""" Put log buffer contents into the log window. """
		# We do this after all initialization because the log.log() function 
		# expects the window to be fully created and accessible via 
		# wx.GetApp().frame.infoframe
		logbuffer.seek(0)
		self.infoframe.Log("".join(line.decode("UTF-8", "replace") 
								   for line in logbuffer).strip())

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
		self.quality_b2a_ab = {
			0: "n",
			1: "l",
			2: "m",
			3: "h",
			4: "u"
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
			"5000",
			"5500",
			"6000",
			"6500"
		]

	def init_frame(self):
		"""
		Initialize the main window and its event handlers.
		
		Controls are initialized in a separate step (see init_controls).
		
		"""
		# UGLY HACK: This 'safe_print' call fixes a GTK assertion and 
		# segfault under Arch Linux when setting the window title
		safe_print("")
		self.SetTitle("%s %s" % (appname, version))
		self.SetMaxSize((-1, -1))
		self.SetIcons(config.get_icon_bundle([256, 48, 32, 16], appname))
		self.Bind(wx.EVT_CLOSE, self.OnClose, self)
		self.Bind(wx.EVT_SHOW, self.OnShow, self)
		self.Bind(wx.EVT_SIZE, self.OnResize, self)
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
		
		self.profile_info = {}
	
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
		self.SetMinSize((self.GetMinSize()[0], 0))
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
		self.SetMinSize((min(self.GetDisplay().ClientArea[2], 
							 self.GetMinSize()[0]), newheight))
		# We add a margin on the right side for the vertical scrollbar
		size = (min(self.GetDisplay().ClientArea[2], 
					max(self.GetMinSize()[0], 
						self.calpanel.GetSizer().GetMinSize()[0] + 34)), 
				newheight)
		self.SetMaxSize(size)
		self.SetSize(size)
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
		wx.CallLater(100, self.SetMinSize, (min(self.GetDisplay().ClientArea[2],
												self.GetMinSize()[0]), 
											self.GetSize()[1] - 
											self.calpanel.GetSize()[1] + 64))
		wx.CallLater(150, self.SetMaxSize, (-1, -1))
		self.Unbind(wx.EVT_IDLE)
		if event:
			event.Skip()
	
	def OnResize(self, event):
		# Hide the header bitmap on small screens
		self.header.GetContainingSizer().Show(
			self.header, self.Size[1] > 480)
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

	def init_infoframe(self, show=None):
		"""
		Create & initialize the info (log) window and its controls.
		
		"""
		self.infoframe = LogWindow(self)
		self.infoframe.Bind(wx.EVT_CLOSE, self.infoframe_close_handler, 
							self.infoframe)
		self.infoframe.SetIcons(config.get_icon_bundle([256, 48, 32, 16], 
													   appname))
		if show:
			self.infoframe.Show()

	def init_lut3dframe(self):
		"""
		Create & initialize the 3D LUT creation window and its controls.
		
		"""
		self.lut3dframe = LUT3DFrame(self)

	def init_reportframe(self):
		"""
		Create & initialize the measurement report creation window and its controls.
		
		"""
		self.reportframe = ReportFrame(self)
		self.reportframe.measure_btn.Bind(wx.EVT_BUTTON,
										  self.measurement_report_handler)

	def init_synthiccframe(self):
		"""
		Create & initialize the 3D LUT creation window and its controls.
		
		"""
		self.synthiccframe = SynthICCFrame(self)
	
	def infoframe_close_handler(self, event):
		self.infoframe_toggle_handler(event)
	
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
		
		self.whitepoint_ctrl.SetItems([lang.getstr("as_measured"),
									   lang.getstr("whitepoint.colortemp"),
									   lang.getstr("whitepoint.xy")])
		
		self.whitepoint_colortemp_loci = [
			lang.getstr("whitepoint.colortemp.locus.daylight"),
			lang.getstr("whitepoint.colortemp.locus.blackbody")
		]
		self.whitepoint_colortemp_locus_ctrl.SetItems(
			self.whitepoint_colortemp_loci)
		
		self.luminance_ctrl.SetItems([lang.getstr("as_measured"),
									  lang.getstr("custom")])
		
		self.black_luminance_ctrl.SetItems([lang.getstr("as_measured"),
											lang.getstr("custom")])
		
		self.trc_ctrl.SetItems([lang.getstr("trc.gamma"),
								lang.getstr("trc.lstar"),
								lang.getstr("trc.rec709"),
								lang.getstr("trc.rec1886"),
								lang.getstr("trc.smpte240m"),
								lang.getstr("trc.srgb")])
		
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
		""" Populate the profile type control with available choices
		depending on Argyll version. """
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
		self.menubar = res.LoadMenuBar("menu")
		
		file_ = self.menubar.GetMenu(self.menubar.FindMenu("menu.file"))
		menuitem = file_.FindItemById(file_.FindItem("calibration.load"))
		self.Bind(wx.EVT_MENU, self.load_cal_handler, menuitem)
		menuitem = file_.FindItemById(file_.FindItem("testchart.set"))
		self.Bind(wx.EVT_MENU, self.testchart_btn_handler, menuitem)
		menuitem = file_.FindItemById(file_.FindItem("testchart.edit"))
		self.Bind(wx.EVT_MENU, self.create_testchart_btn_handler, menuitem)
		menuitem = file_.FindItemById(file_.FindItem("profile.set_save_path"))
		self.Bind(wx.EVT_MENU, self.profile_save_path_btn_handler, menuitem)
		self.menuitem_profile_info = file_.FindItemById(file_.FindItem("profile.info"))
		self.Bind(wx.EVT_MENU, self.profile_info_handler, self.menuitem_profile_info)
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
		self.menuitem_measure_testchart = options.FindItemById(
			options.FindItem("measure.testchart"))
		self.Bind(wx.EVT_MENU, self.measure_handler, 
				  self.menuitem_measure_testchart)
		self.menuitem_create_profile = options.FindItemById(
			options.FindItem("create_profile"))
		self.Bind(wx.EVT_MENU, self.create_profile_handler, 
				  self.menuitem_create_profile)
		self.menuitem_create_profile_from_edid = options.FindItemById(
			options.FindItem("create_profile_from_edid"))
		self.Bind(wx.EVT_MENU, self.create_profile_from_edid, 
				  self.menuitem_create_profile_from_edid)
		self.menuitem_install_display_profile = options.FindItemById(
			options.FindItem("install_display_profile"))
		self.Bind(wx.EVT_MENU, self.select_install_profile_handler, 
				  self.menuitem_install_display_profile)
		self.menuitem_profile_share = options.FindItemById(
			options.FindItem("profile.share"))
		self.Bind(wx.EVT_MENU, self.profile_share_handler, 
				  self.menuitem_profile_share)
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
		self.menuitem_auto_enumerate_ports = options.FindItemById(
			options.FindItem("enumerate_ports.auto"))
		self.Bind(wx.EVT_MENU, self.auto_enumerate_ports_handler, 
				  self.menuitem_auto_enumerate_ports) 
		self.menuitem_use_separate_lut_access = options.FindItemById(
			options.FindItem("use_separate_lut_access"))
		self.Bind(wx.EVT_MENU, self.use_separate_lut_access_handler, 
				  self.menuitem_use_separate_lut_access)
		self.menuitem_do_not_use_video_lut = options.FindItemById(
			options.FindItem("calibration.do_not_use_video_lut"))
		self.Bind(wx.EVT_MENU, self.do_not_use_video_lut_handler, 
				  self.menuitem_do_not_use_video_lut)
		self.menuitem_allow_skip_sensor_cal = options.FindItemById(
			options.FindItem("allow_skip_sensor_cal"))
		self.Bind(wx.EVT_MENU, self.allow_skip_sensor_cal_handler, 
				  self.menuitem_allow_skip_sensor_cal)
		self.menuitem_show_advanced_calibration_options = options.FindItemById(
			options.FindItem("show_advanced_calibration_options"))
		self.Bind(wx.EVT_MENU, self.show_advanced_calibration_options_handler, 
				  self.menuitem_show_advanced_calibration_options)
		menuitem = options.FindItemById(options.FindItem("extra_args"))
		self.Bind(wx.EVT_MENU, self.extra_args_handler, menuitem)
		self.menuitem_enable_argyll_debug = options.FindItemById(
			options.FindItem("enable_argyll_debug"))
		self.Bind(wx.EVT_MENU, self.enable_argyll_debug_handler, 
				  self.menuitem_enable_argyll_debug)
		self.menuitem_enable_dry_run = options.FindItemById(
			options.FindItem("dry_run"))
		self.Bind(wx.EVT_MENU, self.enable_dry_run_handler, 
				  self.menuitem_enable_dry_run)
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
		self.menuitem_measurement_report = tools.FindItemById(
			tools.FindItem("measurement_report"))
		self.Bind(wx.EVT_MENU, self.measurement_report_create_handler, 
				  self.menuitem_measurement_report)
		menuitem = tools.FindItemById(
			tools.FindItem("measurement_report.update"))
		self.Bind(wx.EVT_MENU, self.update_measurement_report, 
				  menuitem)
		self.menuitem_measure_uniformity = tools.FindItemById(
			tools.FindItem("report.uniformity"))
		self.Bind(wx.EVT_MENU, self.measure_uniformity_handler, 
				  self.menuitem_measure_uniformity)

		self.menuitem_measurement_file_check = tools.FindItemById(
			tools.FindItem("measurement_file.check_sanity"))
		self.Bind(wx.EVT_MENU, self.measurement_file_check_handler, 
				  self.menuitem_measurement_file_check)

		self.menuitem_measurement_file_check_auto = tools.FindItemById(
			tools.FindItem("measurement_file.check_sanity.auto"))
		self.Bind(wx.EVT_MENU, self.measurement_file_check_auto_handler, 
				  self.menuitem_measurement_file_check_auto)

		self.menuitem_import_colorimeter_correction = tools.FindItemById(
			tools.FindItem("colorimeter_correction.import"))
		self.Bind(wx.EVT_MENU, self.import_colorimeter_correction_handler, 
				  self.menuitem_import_colorimeter_correction)
		self.menuitem_create_colorimeter_correction = tools.FindItemById(
			tools.FindItem("colorimeter_correction.create"))
		self.Bind(wx.EVT_MENU, self.create_colorimeter_correction_handler, 
				  self.menuitem_create_colorimeter_correction)
		self.menuitem_upload_colorimeter_correction = tools.FindItemById(
			tools.FindItem("colorimeter_correction.upload"))
		self.Bind(wx.EVT_MENU, self.upload_colorimeter_correction_handler, 
				  self.menuitem_upload_colorimeter_correction)
		self.menuitem_synthicc_create = tools.FindItemById(
			tools.FindItem("synthicc.create"))
		self.Bind(wx.EVT_MENU, self.synthicc_create_handler, 
				  self.menuitem_synthicc_create)
		self.menuitem_lut3d_create = tools.FindItemById(
			tools.FindItem("3dlut.create"))
		self.Bind(wx.EVT_MENU, self.lut3d_create_handler, 
				  self.menuitem_lut3d_create)
		self.menuitem_enable_spyder2 = tools.FindItemById(
			tools.FindItem("enable_spyder2"))
		self.Bind(wx.EVT_MENU, self.enable_spyder2_handler, 
				  self.menuitem_enable_spyder2)
		self.menuitem_show_lut = tools.FindItemById(
			tools.FindItem("calibration.show_lut"))
		self.Bind(wx.EVT_MENU, self.init_lut_viewer, self.menuitem_show_lut)
		self.menuitem_show_log = tools.FindItemById(tools.FindItem("infoframe.toggle"))
		self.Bind(wx.EVT_MENU, self.infoframe_toggle_handler, 
				  self.menuitem_show_log)
		self.menuitem_log_autoshow = tools.FindItemById(
			tools.FindItem("log.autoshow"))
		self.Bind(wx.EVT_MENU, self.infoframe_autoshow_handler, 
				  self.menuitem_log_autoshow)

		languages = self.menubar.GetMenu(self.menubar.FindMenu("menu.language"))
		llist = [(lang.ldict[lcode].get("!language", ""), lcode) for lcode in 
				 lang.ldict]
		llist.sort()
		for lstr, lcode in llist:
			menuitem = languages.Append(-1, "&" + lstr, kind=wx.ITEM_RADIO)
			if (lcode.upper().replace("EN", "US") in flagart.catalog):
				menuitem.SetBitmap(
					flagart.catalog[lcode.upper().replace("EN", 
														  "US")].getBitmap())
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
									 os.path.isfile("/usr/share/common-licenses/GPL-3"))
		self.Bind(wx.EVT_MENU, self.license_handler, self.menuitem_license)
		menuitem = help.FindItemById(help.FindItem("help_support"))
		self.Bind(wx.EVT_MENU, self.help_support_handler, menuitem)
		menuitem = help.FindItemById(help.FindItem("bug_report"))
		self.Bind(wx.EVT_MENU, self.bug_report_handler, menuitem)
		self.menuitem_app_auto_update_check = help.FindItemById(
			help.FindItem("update_check.onstartup"))
		self.Bind(wx.EVT_MENU, self.app_auto_update_check_handler,
				  self.menuitem_app_auto_update_check)
		menuitem = help.FindItemById(help.FindItem("update_check"))
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
		self.menuitem_measure_testchart.Enable(bool(self.worker.displays) and 
											   bool(self.worker.instruments))
		self.menuitem_create_profile.Enable(bool(self.worker.displays))
		edid = self.worker.get_display_edid()
		self.menuitem_create_profile_from_edid.Enable(bool(self.worker.displays
														   and edid
														   and edid.get("monitor_name",
																		edid.get("ascii",
																				 edid["product_id"]))
														   and edid["red_x"]
														   and edid["red_y"]
														   and edid["green_x"]
														   and edid["green_y"]
														   and edid["blue_x"]
														   and edid["blue_y"]))
		self.menuitem_install_display_profile.Enable(bool(self.worker.displays) and
			not config.get_display_name() in ("Web", "Untethered", "madVR"))
		self.menuitem_load_lut_from_cal_or_profile.Enable(
			bool(self.worker.displays) and
			not config.get_display_name() in ("Web", "Untethered"))
		self.menuitem_load_lut_from_display_profile.Enable(
			bool(self.worker.displays) and
			not config.get_display_name() in ("Web", "Untethered"))
		self.menuitem_auto_enumerate_ports.Check(bool(getcfg("enumerate_ports.auto")))
		self.menuitem_auto_enumerate_ports.Enable(self.worker.argyll_version >
												  [0, 0, 0])
		has_separate_lut_access = self.worker.has_separate_lut_access()
		self.menuitem_use_separate_lut_access.Check(has_separate_lut_access or
													bool(getcfg("use_separate_lut_access")))
		self.menuitem_use_separate_lut_access.Enable(not has_separate_lut_access)
		has_lut_access = self.worker.has_lut_access()
		do_not_use_video_lut = (self.worker.argyll_version >= [1, 3, 3] and
								(not has_lut_access or
								 not getcfg("calibration.use_video_lut")))
		self.menuitem_do_not_use_video_lut.Check(do_not_use_video_lut)
		self.menuitem_do_not_use_video_lut.Enable(self.worker.argyll_version >=
												  [1, 3, 3] and has_lut_access)
		self.menuitem_allow_skip_sensor_cal.Check(bool(getcfg("allow_skip_sensor_cal")))
		self.menuitem_enable_argyll_debug.Check(bool(getcfg("argyll.debug")))
		self.menuitem_enable_dry_run.Check(bool(getcfg("dry_run")))
		spyd2en = get_argyll_util("spyd2en")
		spyder2_firmware_exists = self.worker.spyder2_firmware_exists()
		self.menuitem_enable_spyder2.Enable(bool(spyd2en))
		self.menuitem_enable_spyder2.Check(bool(spyd2en) and  
										   spyder2_firmware_exists)
		self.menuitem_show_lut.Enable(bool(LUTFrame))
		self.menuitem_show_lut.Check(bool(getcfg("lut_viewer.show")))
		if hasattr(self, "lut_viewer"):
			self.lut_viewer.update_controls()
		self.menuitem_lut_reset.Enable(bool(self.worker.displays) and
									   not config.get_display_name() in
									   ("Web", "Untethered"))
		self.menuitem_report_calibrated.Enable(bool(self.worker.displays) and 
											   bool(self.worker.instruments) and
											   config.get_display_name() != "Untethered")
		self.menuitem_report_uncalibrated.Enable(bool(self.worker.displays) and 
												 bool(self.worker.instruments) and
												 config.get_display_name() != "Untethered")
		self.menuitem_calibration_verify.Enable(bool(self.worker.displays) and 
												bool(self.worker.instruments) and
												config.get_display_name() != "Untethered")
		self.menuitem_measurement_report.Enable(bool(self.worker.displays) and 
											bool(self.worker.instruments))
		self.menuitem_measure_uniformity.Enable(bool(self.worker.displays) and 
												bool(self.worker.instruments))
		self.menuitem_measurement_file_check_auto.Check(bool(getcfg("ti3.check_sanity.auto")))
		self.menuitem_create_colorimeter_correction.Enable(bool(get_argyll_util("ccxxmake")))
		self.menuitem_lut3d_create.Enable(bool(get_argyll_util("icclu")))
		self.menuitem_show_log.Check(bool(getcfg("log.show")))
		self.menuitem_log_autoshow.Enable(not bool(getcfg("log.show")))
		self.menuitem_log_autoshow.Check(bool(getcfg("log.autoshow")))
		self.menuitem_app_auto_update_check.Check(bool(getcfg("update_check")))

	def init_controls(self):
		"""
		Initialize the main window controls and their event handlers.
		
		"""
		
		self.set_child_ctrls_as_attrs(self)

		# Settings file controls
		# ======================
		
		# Settings file dropdown
		self.Bind(wx.EVT_CHOICE, self.calibration_file_ctrl_handler, 
				  id=self.calibration_file_ctrl.GetId())
		self.Bind(wx.EVT_BUTTON, self.load_cal_handler, 
				  id=self.calibration_file_btn.GetId())
		self.delete_calibration_btn.SetBitmapDisabled(geticon(16, "empty"))
		self.Bind(wx.EVT_BUTTON, self.delete_calibration_handler, 
				  id=self.delete_calibration_btn.GetId())
		self.install_profile_btn.SetBitmapDisabled(geticon(16, "empty"))
		self.Bind(wx.EVT_BUTTON, self.install_profile_handler, 
				  id=self.install_profile_btn.GetId())
		self.profile_info_btn.SetBitmapDisabled(geticon(16, "empty"))
		self.Bind(wx.EVT_BUTTON, self.profile_info_handler, 
				  id=self.profile_info_btn.GetId())

		# Update calibration checkbox
		self.Bind(wx.EVT_CHECKBOX, self.calibration_update_ctrl_handler, 
				  id=self.calibration_update_cb.GetId())

		# Display
		self.Bind(wx.EVT_CHOICE, self.display_ctrl_handler, 
				  id=self.display_ctrl.GetId())
		self.Bind(wx.EVT_CHOICE, self.display_lut_ctrl_handler, 
				  id=self.display_lut_ctrl.GetId())
		self.Bind(wx.EVT_BUTTON, self.display_lut_link_ctrl_handler, 
				  id=self.display_lut_link_ctrl.GetId())

		# Instrument
		self.Bind(wx.EVT_CHOICE, self.comport_ctrl_handler, 
				  id=self.comport_ctrl.GetId())
		self.Bind(wx.EVT_CHOICE, self.measurement_mode_ctrl_handler, 
				  id=self.measurement_mode_ctrl.GetId())
		self.detect_displays_and_ports_btn.SetBitmapDisabled(getbitmap("32x16/empty"))
		self.Bind(wx.EVT_BUTTON, self.check_update_controls, 
				  id=self.detect_displays_and_ports_btn.GetId())
		
		# Colorimeter correction matrix
		self.Bind(wx.EVT_CHOICE, self.colorimeter_correction_matrix_ctrl_handler, 
				  id=self.colorimeter_correction_matrix_ctrl.GetId())
		self.Bind(wx.EVT_BUTTON, self.colorimeter_correction_matrix_ctrl_handler, 
				  id=self.colorimeter_correction_matrix_btn.GetId())
		self.Bind(wx.EVT_BUTTON, self.colorimeter_correction_web_handler, 
				  id=self.colorimeter_correction_web_btn.GetId())

		# Calibration settings
		# ====================

		# Whitepoint
		self.Bind(wx.EVT_CHOICE, self.whitepoint_ctrl_handler, 
				  id=self.whitepoint_ctrl.GetId())
		self.Bind(wx.EVT_COMBOBOX, self.whitepoint_ctrl_handler, 
				  id=self.whitepoint_colortemp_textctrl.GetId())
		self.whitepoint_colortemp_textctrl.SetItems(self.whitepoint_presets)
		self.whitepoint_colortemp_textctrl.Bind(
			wx.EVT_KILL_FOCUS, self.whitepoint_ctrl_handler)
		self.Bind(wx.EVT_CHOICE, self.whitepoint_colortemp_locus_ctrl_handler, 
				  id=self.whitepoint_colortemp_locus_ctrl.GetId())
		self.whitepoint_x_textctrl.Bind(wx.EVT_KILL_FOCUS, 
										self.whitepoint_ctrl_handler)
		self.whitepoint_y_textctrl.Bind(wx.EVT_KILL_FOCUS, 
										self.whitepoint_ctrl_handler)
		self.Bind(wx.EVT_BUTTON, self.ambient_measure_handler, 
				  id=self.whitepoint_measure_btn.GetId())

		# White luminance
		self.Bind(wx.EVT_CHOICE, self.luminance_ctrl_handler, 
				  id=self.luminance_ctrl.GetId())
		self.luminance_textctrl.Bind(wx.EVT_KILL_FOCUS, 
									 self.luminance_ctrl_handler)
		self.Bind(wx.EVT_CHECKBOX, self.whitelevel_drift_compensation_handler, 
				  id=self.whitelevel_drift_compensation.GetId())

		# Black luminance
		self.Bind(wx.EVT_CHOICE, self.black_luminance_ctrl_handler, 
				  id=self.black_luminance_ctrl.GetId())
		self.black_luminance_textctrl.Bind(wx.EVT_KILL_FOCUS, 
										   self.black_luminance_ctrl_handler)
		self.Bind(wx.EVT_CHECKBOX, self.blacklevel_drift_compensation_handler, 
				  id=self.blacklevel_drift_compensation.GetId())

		# Tonal response curve (TRC)
		self.Bind(wx.EVT_CHOICE, self.trc_ctrl_handler, 
				  id=self.trc_ctrl.GetId())
		self.trc_textctrl.SetItems(self.trc_presets)
		self.trc_textctrl.SetValue(str(defaults["gamma"]))
		self.Bind(wx.EVT_COMBOBOX, self.trc_ctrl_handler, 
				  id=self.trc_textctrl.GetId())
		self.trc_textctrl.Bind(wx.EVT_KILL_FOCUS, self.trc_ctrl_handler)
		self.Bind(wx.EVT_CHOICE, self.trc_type_ctrl_handler, 
				  id=self.trc_type_ctrl.GetId())

		# Viewing condition adjustment for ambient in Lux
		self.Bind(wx.EVT_CHECKBOX, self.ambient_viewcond_adjust_ctrl_handler, 
				  id=self.ambient_viewcond_adjust_cb.GetId())
		self.ambient_viewcond_adjust_textctrl.Bind(
			wx.EVT_KILL_FOCUS, self.ambient_viewcond_adjust_ctrl_handler)
		self.ambient_viewcond_adjust_info.SetCursor(wx.StockCursor(wx.CURSOR_QUESTION_ARROW))
		self.Bind(wx.EVT_BUTTON, self.ambient_measure_handler,
				  id=self.ambient_measure_btn.GetId())

		# Black level output offset
		self.Bind(wx.EVT_SLIDER, self.black_output_offset_ctrl_handler, 
				  id=self.black_output_offset_ctrl.GetId())
		self.Bind(wx.EVT_TEXT, self.black_output_offset_ctrl_handler, 
				  id=self.black_output_offset_intctrl.GetId())

		# Black point hue correction
		self.Bind(wx.EVT_CHECKBOX, self.black_point_correction_auto_handler, 
				  id=self.black_point_correction_auto_cb.GetId())
		self.Bind(wx.EVT_SLIDER, self.black_point_correction_ctrl_handler, 
				  id=self.black_point_correction_ctrl.GetId())
		self.Bind(wx.EVT_TEXT, self.black_point_correction_ctrl_handler, 
				  id=self.black_point_correction_intctrl.GetId())

		# Black point correction rate
		self.Bind(wx.EVT_SLIDER, self.black_point_rate_ctrl_handler, 
				  id=self.black_point_rate_ctrl.GetId())
		self.Bind(floatspin.EVT_FLOATSPIN, self.black_point_rate_ctrl_handler, 
				  id=self.black_point_rate_floatctrl.GetId())

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
		self.Bind(wx.EVT_CHOICE, self.testchart_ctrl_handler, 
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
		self.Bind(wx.EVT_CHECKBOX, self.profile_quality_b2a_ctrl_handler, 
				  id=self.low_quality_b2a_cb.GetId())

		# Profile type
		self.Bind(wx.EVT_CHOICE, self.profile_type_ctrl_handler, 
				  id=self.profile_type_ctrl.GetId())

		# Advanced (gamut mapping)
		self.Bind(wx.EVT_BUTTON, self.gamap_btn_handler, 
				  id=self.gamap_btn.GetId())

		# Black point compensation
		self.Bind(wx.EVT_CHECKBOX, 
				  self.black_point_compensation_ctrl_handler, 
				  id=self.black_point_compensation_cb.GetId())

		# Profile name
		self.Bind(wx.EVT_TEXT, self.profile_name_ctrl_handler, 
				  id=self.profile_name_textctrl.GetId())
		self.profile_name_info_btn.SetCursor(wx.StockCursor(wx.CURSOR_QUESTION_ARROW))
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
				if getattr(self, "lut3dframe", None):
					self.lut3dframe.panel.Freeze()
					self.lut3dframe.setup_language()
					self.lut3dframe.update_controls()
					self.lut3dframe.update_layout()
					self.lut3dframe.panel.Thaw()
				if getattr(self, "reportframe", None):
					self.reportframe.panel.Freeze()
					self.reportframe.setup_language()
					self.reportframe.update_controls()
					self.reportframe.update_layout()
					self.reportframe.panel.Thaw()
				if getattr(self, "synthiccframe", None):
					self.synthiccframe.panel.Freeze()
					self.synthiccframe.setup_language()
					self.synthiccframe.update_controls()
					self.synthiccframe.update_layout()
					self.synthiccframe.panel.Thaw()
				self.update_measurement_modes()
				self.update_controls()
				self.update_displays()
				self.set_testcharts()
				self.update_layout()
				self.panel.Thaw()
				if hasattr(self, "aboutdialog"):
					self.aboutdialog.Destroy()
					del self.aboutdialog
				self.infoframe.Destroy()
				self.init_infoframe(show=getcfg("log.show"))
				self.log()
				if sys.platform in ("darwin", "win32") or isexe:
					self.measureframe.Destroy()
					self.init_measureframe()
				if hasattr(self, "lut_viewer"):
					self.lut_viewer.Destroy()
					del self.lut_viewer
					if getcfg("lut_viewer.show"):
						self.init_lut_viewer(show=True)
				if hasattr(self, "profile_name_tooltip_window"):
					self.profile_name_tooltip_window.Destroy()
					del self.profile_name_tooltip_window
				self.Raise()
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
			"3dlut.apply_bt1886_gamma_mapping",
			"3dlut.bitdepth.input",
			"3dlut.bitdepth.output",
			"3dlut.bt1886_gamma",
			"3dlut.bt1886_gamma_type",
			"3dlut.encoding.input",
			"3dlut.encoding.input.backup",
			"3dlut.encoding.output",
			"3dlut.encoding.output.backup",
			"3dlut.format",
			"3dlut.input.profile",
			"3dlut.abstract.profile",
			"3dlut.output.profile",
			"3dlut.output.profile.apply_cal",
			"3dlut.rendering_intent",
			"3dlut.use_abstract_profile",
			"3dlut.size",
			"allow_skip_sensor_cal",
			"argyll.dir",
			"argyll.version",
			"calibration.black_output_offset.backup",
			"calibration.black_point_rate.enabled",
			"calibration.file.previous",
			"calibration.update",
			"calibration.use_video_lut.backup",
			"colorimeter_correction_matrix_file",
			"comport.number",
			"copyright",
			"display.number",
			"display_lut.link",
			"display_lut.number",
			"displays",
			"dry_run",
			"enumerate_ports.auto",
			"gamma",
			"instruments",
			"lang",
			"last_3dlut_path",
			"last_cal_path",
			"last_cal_or_icc_path",
			"last_filedialog_path",
			"last_icc_path",
			"last_ti1_path",
			"last_ti3_path",
			"last_vrml_path",
			"log.autoshow",
			"log.show",
			"lut_viewer.show",
			"lut_viewer.show_actual_lut",
			"measurement_mode",
			"measurement_mode.backup",
			"measurement_mode.projector",
			"measurement.name.expanded",
			"measurement.play_sound",
			"measurement.save_path",
			"profile.install_scope",
			"profile.license",
			"profile.load_on_login",
			"profile.name",
			"profile.name.expanded",
			"profile.save_path",
			"profile_loader.error.show_msg",
			"profile_loader.verify_calibration",
			"profile.update",
			"position.x",
			"position.y",
			"position.info.x",
			"position.info.y",
			"position.lut_viewer.x",
			"position.lut_viewer.y",
			"position.lut3dframe.x",
			"position.lut3dframe.y",
			"position.synthiccframe.x",
			"position.synthiccframe.y",
			"position.profile_info.x",
			"position.profile_info.y",
			"position.progress.x",
			"position.progress.y",
			"position.reportframe.x",
			"position.reportframe.y",
			"position.tcgen.x",
			"position.tcgen.y",
			"recent_cals",
			"report.pack_js",
			"settings.changed",
			"show_advanced_calibration_options",
			"skip_legacy_serial_ports",
			"sudo.preserve_environment",
			"tc_precond_profile",
			"tc_vrml_lab",
			"tc_vrml_device",
			"tc.show",
			"testchart.file.backup",
			"trc.backup",
			"trc.type.backup",
			"untethered.measure.auto",
			"update_check"
		]
		override = {
			"calibration.black_luminance": None,
			"calibration.file": None,
			"calibration.luminance": None,
			"gamap_src_viewcond": "mt",
			"gamap_out_viewcond": "mt",
			"trc": defaults["gamma"],
			"whitepoint.colortemp": None,
			"whitepoint.x": None,
			"whitepoint.y": None
		}
		for name in defaults:
			if name not in skip and name not in override:
				if (len(include) == 0 or False in [name.find(item) != 0 for 
												   item in include]) and \
				   (len(exclude) == 0 or not (False in [name.find(item) != 0 for 
														item in exclude])):
					if verbose >= 3:
						safe_print("Restoring %s to %s" % (name, 
														   defaults[name]))
					setcfg(name, defaults[name])
		for name in override:
			if (len(include) == 0 or False in [name.find(item) != 0 for item in 
											   include]) and \
			   (len(exclude) == 0 or not (False in [name.find(item) != 0 for 
													item in exclude])):
				setcfg(name, override[name])
		if event:
			writecfg()
			self.update_displays()
			self.update_controls()
			self.update_menus()
			if hasattr(self, "extra_args"):
				self.extra_args.update_controls()
			if hasattr(self, "gamapframe"):
				self.gamapframe.update_controls()
			if hasattr(self, "tcframe"):
				self.tcframe.tc_update_controls()

	def cal_changed(self, setchanged=True):
		"""
		Called internally when calibration settings controls are changed.
		
		Exceptions are the calibration quality and interactive display
		adjustment controls, which do not cause a 'calibration changed' event.
		
		"""
		if not self.updatingctrls and self.IsShownOnScreen():
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
			do_update_controls = self.calibration_update_cb.GetValue()
			self.calibration_update_cb.SetValue(False)
			setcfg("calibration.update", 0)
			self.calibration_update_cb.Disable()
			setcfg("profile.update", 0)
			if do_update_controls:
				self.update_controls()
			self.settings_discard_changes(keep_changed_state=True)

	def update_displays(self, update_ccmx_items=False):
		""" Update the display selector controls. """
		if debug:
			safe_print("[D] update_displays")
		self.calpanel.Freeze()
		self.displays = []
		for item in self.worker.displays:
			self.displays += [item.replace("[PRIMARY]", 
										   lang.getstr("display.primary"))]
			self.displays[-1] = lang.getstr(self.displays[-1])
		self.display_ctrl.SetItems(self.displays)
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
		self.get_set_display(update_ccmx_items)
		self.calpanel.Layout()
		self.calpanel.Thaw()
		self.update_scrollbars()
	
	def update_scrollbars(self):
		self.Freeze()
		self.calpanel.SetVirtualSize(self.calpanel.GetBestVirtualSize())
		self.Thaw()

	def update_comports(self):
		""" Update the comport selector control. """
		self.comport_ctrl.Freeze()
		self.comport_ctrl.SetItems(self.worker.instruments)
		if self.worker.instruments:
			self.comport_ctrl.SetSelection(
				min(max(0, len(self.worker.instruments) - 1), 
					max(0, int(getcfg("comport.number")) - 1)))
		self.comport_ctrl.Enable(len(self.worker.instruments) > 1)
		self.comport_ctrl.Thaw()
		self.comport_ctrl_handler()

	def update_measurement_mode(self):
		""" Update the measurement mode control. """
		measurement_mode = getcfg("measurement_mode")
		instrument_features = self.worker.get_instrument_features()
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
					measurement_mode, 1), 
				len(self.measurement_mode_ctrl.GetItems()) - 1))
	
	def update_measurement_modes(self):
		""" Populate the measurement mode control. """
		instrument_name = self.worker.get_instrument_name()
		instrument_type = self.get_instrument_type()
		measurement_mode = getcfg("measurement_mode")
		#if self.get_instrument_type() == "spect":
			#measurement_mode = strtr(measurement_mode, {"c": "", "l": ""})
		if instrument_name != "DTP92":
			measurement_modes = dict({instrument_type: [lang.getstr("measurement_mode.refresh"),
														lang.getstr("measurement_mode.lcd")]})
			measurement_modes_ab = dict({instrument_type: ["c", "l"]})
		else:
			measurement_modes = dict({instrument_type: [lang.getstr("measurement_mode.refresh")]})
			measurement_modes_ab = dict({instrument_type: ["c"]})
		if instrument_name == "Spyder4" and self.worker.spyder4_cal_exists():
			# Argyll CMS 1.3.6
			# See http://www.argyllcms.com/doc/instruments.html#spyd4
			# for description of supported modes
			measurement_modes[instrument_type].extend([lang.getstr("measurement_mode.lcd.ccfl"),
													   lang.getstr("measurement_mode.lcd.wide_gamut.ccfl"),
													   lang.getstr("measurement_mode.lcd.white_led"),
													   lang.getstr("measurement_mode.lcd.wide_gamut.rgb_led"),
													   lang.getstr("measurement_mode.lcd.ccfl.2")])
			if self.worker.argyll_version >= [1, 5, 0]:
				measurement_modes_ab[instrument_type].extend(["f", "L", "e",
															  "B", "x"])
			else:
				measurement_modes_ab[instrument_type].extend(["3", "4", "5",
															  "6", "7"])
		elif instrument_name == "ColorHug":
			# Argyll CMS 1.3.6, spectro/colorhug.c, colorhug_disptypesel
			# Note: projector mode (-yp) is not the same as ColorMunki
			# projector mode! (-p)
			measurement_modes[instrument_type].extend([lang.getstr("projector"),
													   lang.getstr("measurement_mode.lcd.white_led"),
													   lang.getstr("measurement_mode.factory"),
													   lang.getstr("measurement_mode.raw")])
			measurement_modes_ab[instrument_type].extend(["p", "e", "F", "R"])
		elif (instrument_name == "DTP94" and
			  self.worker.argyll_version >= [1, 5, 0]):
			# Argyll CMS 1.5.x introduces new measurement mode
			measurement_modes[instrument_type].extend([lang.getstr("measurement_mode.generic")])
			measurement_modes_ab[instrument_type].append("g")
		elif instrument_name == "ColorMunki Smile":
			# Only supported in Argyll CMS 1.5.x and newer
			measurement_modes[instrument_type] = [lang.getstr("measurement_mode.lcd.ccfl"),
												  lang.getstr("measurement_mode.lcd.white_led")]
			measurement_modes_ab[instrument_type] = ["f", "e"]
		elif (instrument_name == "Colorimtre HCFR" and
			  self.worker.argyll_version >= [1, 5, 0]):
			# Argyll CMS 1.5.x introduces new measurement mode
			measurement_modes[instrument_type].extend([lang.getstr("measurement_mode.raw")])
			measurement_modes_ab[instrument_type].append("R")
		instrument_features = self.worker.get_instrument_features()
		if instrument_features.get("projector_mode") and \
		   self.worker.argyll_version >= [1, 1, 0]:
			# Projector mode introduced in Argyll 1.1.0 Beta
			measurement_modes[instrument_type] += [lang.getstr("projector")]
			measurement_modes_ab[instrument_type] += ["p"]
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
															   1), 
				len(measurement_modes[instrument_type]) - 1))
		setcfg("measurement_mode", (self.get_measurement_mode() or "l")[0])
		self.measurement_mode_ctrl.Enable(
			bool(self.worker.instruments) and 
			len(measurement_modes[instrument_type]) > 1 and
			bool(getcfg("measurement_mode_unlocked")))
		self.measurement_mode_ctrl.Thaw()
	
	def update_colorimeter_correction_matrix_ctrl(self):
		""" Show or hide the colorimeter correction matrix controls """
		self.calpanel.Freeze()
		instrument_features = self.worker.get_instrument_features()
		show_control = (self.worker.instrument_can_use_ccxx() and
						not is_ccxx_testchart())
		self.colorimeter_correction_matrix_ctrl.GetContainingSizer().Show(
			self.colorimeter_correction_matrix_ctrl, show_control)
		self.colorimeter_correction_matrix_label.GetContainingSizer().Show(
			self.colorimeter_correction_matrix_label, show_control)
		self.colorimeter_correction_matrix_btn.GetContainingSizer().Show(
			self.colorimeter_correction_matrix_btn, show_control)
		self.colorimeter_correction_web_btn.GetContainingSizer().Show(
			self.colorimeter_correction_web_btn, show_control)
		self.calpanel.Layout()
		self.calpanel.Thaw()
		self.update_scrollbars()
	
	def delete_colorimeter_correction_matrix_ctrl_item(self, path):
		if path in self.ccmx_cached_paths:
			self.ccmx_cached_paths.remove(path)
		if path in self.ccmx_cached_descriptors:
			del self.ccmx_cached_descriptors[path]
		if path in self.ccmx_instruments:
			del self.ccmx_instruments[path]
		delete = False
		for key, value in self.ccmx_mapping.iteritems():
			if value == path:
				delete = True
				break
		if delete:
			del self.ccmx_mapping[key]
	
	def update_colorimeter_correction_matrix_ctrl_items(self, force=False,
														warn_on_mismatch=False):
		"""
		Show the currently selected correction matrix and list all files
		in ccmx directories below
		
		force	If True, reads the ccmx directory again, otherwise uses a
				previously cached result if available
		
		"""
		items = [lang.getstr("colorimeter_correction.file.none"),
				 lang.getstr("auto")]
		self.ccmx_item_paths = []
		index = 0
		ccmx = getcfg("colorimeter_correction_matrix_file").split(":", 1)
		if len(ccmx) > 1 and not os.path.isfile(ccmx[1]):
			ccmx = ccmx[:1]
		if force or not getattr(self, "ccmx_cached_paths", None):
			ccmx_paths = []
			ccss_paths = []
			if sys.platform != "darwin":
				for commonappdata in config.commonappdata:
					ccmx_paths += glob.glob(os.path.join(commonappdata, "color",
														 "*.ccmx"))
					ccmx_paths += glob.glob(os.path.join(commonappdata, "ArgyllCMS",
														 "*.ccmx"))
					ccss_paths += glob.glob(os.path.join(commonappdata, "color",
														 "*.ccss"))
					ccss_paths += glob.glob(os.path.join(commonappdata, "ArgyllCMS",
														 "*.ccss"))
				ccmx_paths += glob.glob(os.path.join(config.appdata, "color",
													 "*.ccmx"))
				ccss_paths += glob.glob(os.path.join(config.appdata, "color",
													 "*.ccss"))
			else:
				ccmx_paths += glob.glob(os.path.join(config.library, "color",
													 "*.ccmx"))
				ccmx_paths += glob.glob(os.path.join(config.library, "ArgyllCMS",
													 "*.ccmx"))
				ccmx_paths += glob.glob(os.path.join(config.library_home, "color",
													 "*.ccmx"))
				ccss_paths += glob.glob(os.path.join(config.library, "color",
													 "*.ccss"))
				ccss_paths += glob.glob(os.path.join(config.library, "ArgyllCMS",
													 "*.ccss"))
				ccss_paths += glob.glob(os.path.join(config.library_home, "color",
													 "*.ccss"))
			ccmx_paths += glob.glob(os.path.join(config.appdata, "ArgyllCMS",
												 "*.ccmx"))
			ccss_paths += glob.glob(os.path.join(config.appdata, "ArgyllCMS",
												 "*.ccss"))
			ccmx_paths.sort(key=os.path.basename)
			ccss_paths.sort(key=os.path.basename)
			self.ccmx_cached_paths = ccmx_paths + ccss_paths
			self.ccmx_cached_descriptors = OrderedDict()
			self.ccmx_instruments = {}
			self.ccmx_mapping = {}
		types = {"ccss": lang.getstr("spectral").replace(":", ""),
				 "ccmx": lang.getstr("matrix").replace(":", "")}
		for i, path in enumerate(self.ccmx_cached_paths):
			if self.ccmx_cached_descriptors.get(path):
				desc = self.ccmx_cached_descriptors[path]
			elif os.path.isfile(path):
				try:
					cgats = CGATS.CGATS(path)
				except (IOError, CGATS.CGATSError), exception:
					safe_print("%s:" % path, exception)
					continue
				desc = safe_unicode(cgats.get_descriptor(), "UTF-8")
				# If the description is not the same as the 'sane'
				# filename, add the filename after the description
				# (max 31 chars)
				# See also colorimeter_correction_check_overwite, the
				# way the filename is processed must be the same
				if (re.sub(r"[\\/:*?\"<>|]+", "_",
						   make_argyll_compatible_path(desc)) !=
					os.path.splitext(os.path.basename(path))[0]):
					desc = "%s <%s>" % (ellipsis(desc, 66, "m"),
										ellipsis(os.path.basename(path), 31,
												 "m"))
				else:
					desc = ellipsis(desc, 100, "m")
				self.ccmx_cached_descriptors[path] = desc
				self.ccmx_instruments[path] = get_canonical_instrument_name(
					str(cgats.queryv1("INSTRUMENT") or
									  "").replace("eye-one display",
												  "i1 Display"))
				key = "%s\0%s" % (self.ccmx_instruments[path],
								  str(cgats.queryv1("DISPLAY") or ""))
				if (not self.ccmx_mapping.get(key) or
					(len(ccmx) > 1 and path == ccmx[1])):
					# Prefer the selected CCMX
					self.ccmx_mapping[key] = path
			else:
				continue
			if (self.worker.get_instrument_name().lower().replace(" ", "") in
				self.ccmx_instruments.get(path, "").lower().replace(" ", "") or
				(path.lower().endswith(".ccss") and
				 self.worker.instrument_supports_ccss())):
				# Only add the correction to the list if it matches the
				# currently selected instrument or if it is a CCSS
				if len(ccmx) > 1 and ccmx[0] != "AUTO" and ccmx[1] == path:
					index = len(items)
				items.append("%s: %s" %
							 (types.get(os.path.splitext(path)[1].lower()[1:]),
							  desc))
				self.ccmx_item_paths.append(path)
		if (len(ccmx) > 1 and ccmx[1] and ccmx[1] not in self.ccmx_cached_paths
			and (not ccmx[1].lower().endswith(".ccss") or
				 self.worker.instrument_supports_ccss())):
			self.ccmx_cached_paths.insert(0, ccmx[1])
			desc = self.ccmx_cached_descriptors.get(ccmx[1])
			if not desc and os.path.isfile(ccmx[1]):
				try:
					cgats = CGATS.CGATS(ccmx[1])
				except (IOError, CGATS.CGATSError), exception:
					safe_print("%s:" % ccmx[1], exception)
				else:
					desc = safe_unicode(cgats.get_descriptor(), "UTF-8")
					# If the description is not the same as the 'sane'
					# filename, add the filename after the description
					# (max 31 chars)
					# See also colorimeter_correction_check_overwite, the
					# way the filename is processed must be the same
					if (re.sub(r"[\\/:*?\"<>|]+", "_",
							   make_argyll_compatible_path(desc)) !=
						os.path.splitext(os.path.basename(ccmx[1]))[0]):
						desc = "%s <%s>" % (ellipsis(desc, 66, "m"),
											ellipsis(os.path.basename(ccmx[1]),
													 31, "m"))
					else:
						desc = ellipsis(desc, 100, "m")
					self.ccmx_cached_descriptors[ccmx[1]] = desc
					self.ccmx_instruments[ccmx[1]] = get_canonical_instrument_name(
						str(cgats.queryv1("INSTRUMENT") or
										  "").replace("eye-one display",
													  "i1 Display"))
					key = "%s\0%s" % (self.ccmx_instruments[ccmx[1]],
									  str(cgats.queryv1("DISPLAY") or ""))
					self.ccmx_mapping[key] = ccmx[1]
			if (desc and
				(self.worker.get_instrument_name().lower().replace(" ", "") in
				 self.ccmx_instruments.get(ccmx[1], "").lower().replace(" ", "") or
				 ccmx[1].lower().endswith(".ccss"))):
				# Only add the correction to the list if it matches the
				# currently selected instrument or if it is a CCSS
				items.insert(2, "%s: %s" %
								(types.get(os.path.splitext(ccmx[1])[1].lower()[1:]),
								 desc))
				self.ccmx_item_paths.insert(0, ccmx[1])
				if ccmx[0] != "AUTO":
					index = 2
		if ccmx[0] == "AUTO":
			if len(ccmx) < 2:
				ccmx.append("")
			display_name = self.worker.get_display_name(False, True)
			if self.worker.instrument_supports_ccss():
				# Prefer CCSS
				ccmx[1] = self.ccmx_mapping.get("\0%s" % display_name, "")
			if not self.worker.instrument_supports_ccss() or not ccmx[1]:
				ccmx[1] = self.ccmx_mapping.get("%s\0%s" %
												(self.worker.get_instrument_name(),
												 display_name), "")
		if (self.worker.instrument_can_use_ccxx() and len(ccmx) > 1 and
			ccmx[1] and ccmx[1] not in self.ccmx_item_paths):
			# CCMX does not match the currently selected instrument,
			# don't use
			ccmx = [""]
			if warn_on_mismatch:
				show_result_dialog(Warn(lang.getstr("colorimeter_correction.instrument_mismatch")), self)
		elif ccmx[0] == "AUTO":
			index = 1
			if ccmx[1]:
				items[1] += " (%s: %s)" % (types.get(os.path.splitext(ccmx[1])[1].lower()[1:]),
										   self.ccmx_cached_descriptors[ccmx[1]])
			else:
				items[1] += " (%s)" % lang.getstr("colorimeter_correction.file.none")
		setcfg("colorimeter_correction_matrix_file", ":".join(ccmx))
		self.colorimeter_correction_matrix_ctrl.SetItems(items)
		self.colorimeter_correction_matrix_ctrl.SetSelection(index)
		setcfg("measurement_mode_unlocked", 1)
		if self.worker.instrument_can_use_ccxx() and len(ccmx) > 1 and ccmx[1]:
			tooltip = ccmx[1]
			try:
				cgats = CGATS.CGATS(ccmx[1])
			except (IOError, CGATS.CGATSError), exception:
				safe_print("%s:" % ccmx[1], exception)
			else:
				base_id = cgats.queryv1("DISPLAY_TYPE_BASE_ID")
				refresh = cgats.queryv1("DISPLAY_TYPE_REFRESH")
				mode = None
				if base_id:
					# Set measurement mode according to base ID
					if self.worker.get_instrument_name() == "ColorHug":
						mode = {1: "R",
								2: "F"}.get(base_id)
					elif self.worker.get_instrument_name() == "ColorMunki Smile":
						mode = {1: "f"}.get(base_id)
					elif self.worker.get_instrument_name() == "Colorimtre HCFR":
						mode = {1: "R"}.get(base_id)
					else:
						mode = {1: "l",
								2: "c",
								3: "g"}.get(base_id)
				elif refresh == "NO":
					mode = "l"
				elif refresh == "YES":
					mode = "c"
				if mode:
					setcfg("measurement_mode", mode)
					setcfg("measurement_mode_unlocked", 0)
					self.update_measurement_mode()
		else:
			tooltip = ""
		self.update_main_controls()
		self.colorimeter_correction_matrix_ctrl.SetToolTipString(tooltip)

	def update_main_controls(self):
		""" Enable/disable the calibrate and profile buttons 
		based on available Argyll functionality. """
		self.panel.Freeze()
		
		update_cal = self.calibration_update_cb.GetValue()

		self.measurement_mode_ctrl.Enable(
			not update_cal and bool(self.worker.instruments) and 
			len(self.measurement_mode_ctrl.GetItems()) > 1 and
			bool(getcfg("measurement_mode_unlocked")))
		
		update_profile = self.calibration_update_cb.GetValue() and is_profile()
		enable_profile = not update_profile and not is_ccxx_testchart()

		self.whitepoint_measure_btn.Enable(bool(self.worker.instruments) and
										   not update_cal)
		self.ambient_measure_btn.Enable(bool(self.worker.instruments) and
										not update_cal)

		self.calibrate_btn.Enable(not is_ccxx_testchart() and
								  bool(self.worker.displays) and 
								  True in self.worker.lut_access and 
								  bool(self.worker.instruments) and
								  config.get_display_name() != "Untethered")
		self.calibrate_and_profile_btn.Enable(enable_profile and 
											  bool(self.worker.displays) and 
											  True in self.worker.lut_access and 
											  bool(self.worker.instruments) and
											  config.get_display_name() != "Untethered")
		self.profile_btn.Enable(enable_profile and not update_cal and 
								bool(self.worker.displays) and 
								bool(self.worker.instruments))
		
		self.panel.Thaw()

	def update_calibration_file_ctrl(self, silent=False):
		""" Update items shown in the calibration file control and set
		a tooltip with the path of the currently selected file """
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
			filename = None
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
		
		return cal, filename, profile_path, profile_exists

	def update_controls(self, update_profile_name=True, update_ccmx_items=True,
						silent=False):
		""" Update all controls based on configuration 
		and available Argyll functionality. """
		self.updatingctrls = True
		
		self.panel.Freeze()
		
		(cal, filename, profile_path,
		 profile_exists) = self.update_calibration_file_ctrl(silent)
		self.delete_calibration_btn.Enable(bool(cal) and 
										   cal not in self.presets)
		self.install_profile_btn.Enable(profile_exists and
										profile_path == cal and
										cal not in self.presets)
		is_profile_ = is_profile(include_display_profile=True)
		self.profile_info_btn.Enable(is_profile_)
		enable_update = (bool(cal) and os.path.exists(filename + ".cal") and
						 can_update_cal(filename + ".cal"))
		if not enable_update:
			setcfg("calibration.update", 0)
		self.calibration_update_cb.Enable(enable_update)
		self.calibration_update_cb.SetValue(
			bool(getcfg("calibration.update")))

		update_cal = self.calibration_update_cb.GetValue()

		if not update_cal or not profile_exists:
			setcfg("profile.update", "0")

		update_profile = self.calibration_update_cb.GetValue() and profile_exists
		enable_profile = not(update_profile)
		
		if update_ccmx_items:
			self.update_colorimeter_correction_matrix_ctrl_items()

		self.whitepoint_ctrl.Enable(not update_cal)
		self.whitepoint_colortemp_textctrl.Enable(not update_cal)
		self.whitepoint_colortemp_locus_ctrl.Enable(not update_cal)
		self.whitepoint_x_textctrl.Enable(not update_cal)
		self.whitepoint_y_textctrl.Enable(not update_cal)
		self.whitepoint_measure_btn.Enable(not update_cal)
		self.luminance_ctrl.Enable(not update_cal)
		self.luminance_textctrl.Enable(not update_cal)
		self.black_luminance_ctrl.Enable(not update_cal)
		self.black_luminance_textctrl.Enable(not update_cal)
		self.trc_ctrl.Enable(not update_cal)
		self.trc_textctrl.Enable(not update_cal)
		self.trc_type_ctrl.Enable(not update_cal)
		self.ambient_viewcond_adjust_cb.Enable(not update_cal)
		self.ambient_viewcond_adjust_info.Enable(not update_cal)
		self.black_output_offset_ctrl.Enable(not update_cal)
		self.black_output_offset_intctrl.Enable(not update_cal)
		self.black_point_correction_auto_cb.Enable(not update_cal)
		self.black_point_correction_ctrl.Enable(not update_cal)
		self.black_point_correction_intctrl.Enable(not update_cal)
		self.black_point_correction_auto_handler()
		self.update_black_point_rate_ctrl()
		self.update_drift_compensation_ctrls()
		self.interactive_display_adjustment_cb.Enable(not update_cal)

		self.testchart_btn.Enable(enable_profile)
		self.create_testchart_btn.Enable(enable_profile)
		self.profile_type_ctrl.Enable(enable_profile)

		self.update_measurement_mode()

		self.whitepoint_colortemp_textctrl.SetValue(
			str(stripzeros(getcfg("whitepoint.colortemp"))))
		self.whitepoint_colortemp_locus_ctrl.SetSelection(
			self.whitepoint_colortemp_loci_ba.get(
				getcfg("whitepoint.colortemp.locus"), 
			self.whitepoint_colortemp_loci_ba.get(
				defaults["whitepoint.colortemp.locus"])))
		if getcfg("whitepoint.colortemp", False):
			self.whitepoint_ctrl.SetSelection(1)
		elif getcfg("whitepoint.x", False) and getcfg("whitepoint.y", False):
			self.whitepoint_x_textctrl.ChangeValue(str(getcfg("whitepoint.x")))
			self.whitepoint_y_textctrl.ChangeValue(str(getcfg("whitepoint.y")))
			self.whitepoint_ctrl.SetSelection(2)
		else:
			self.whitepoint_ctrl.SetSelection(0)
		self.whitepoint_ctrl_handler(
			CustomEvent(wx.EVT_CHOICE.evtType[0], 
			self.whitepoint_ctrl), False)

		if getcfg("calibration.luminance", False):
			self.luminance_ctrl.SetSelection(1)
		else:
			self.luminance_ctrl.SetSelection(0)
		self.luminance_textctrl.ChangeValue(
			str(getcfg("calibration.luminance")))
		self.luminance_textctrl.Show(bool(getcfg("calibration.luminance", 
												 False)))
		self.luminance_textctrl_label.Show(bool(getcfg("calibration.luminance", 
													   False)))
		
		self.whitelevel_drift_compensation.SetValue(
			bool(getcfg("drift_compensation.whitelevel")))

		if getcfg("calibration.black_luminance", False):
			self.black_luminance_ctrl.SetSelection(1)
		else:
			self.black_luminance_ctrl.SetSelection(0)
		self.black_luminance_textctrl.ChangeValue(
			"%.6f" % getcfg("calibration.black_luminance"))
		self.black_luminance_textctrl.Show(
			not update_cal and bool(getcfg("calibration.black_luminance", False)))
		self.black_luminance_textctrl_label.Show(
			not update_cal and bool(getcfg("calibration.black_luminance", False)))
		
		self.blacklevel_drift_compensation.SetValue(
			bool(getcfg("drift_compensation.blacklevel")))

		trc = getcfg("trc")
		bt1886 = (trc == 2.4 and getcfg("trc.type") == "G" and
				  getcfg("calibration.black_output_offset") == 0)
		if trc in ("l", "709", "240", "s"):
			self.trc_textctrl.Hide()
			self.trc_type_ctrl.SetSelection(0)
			self.trc_type_ctrl.Hide()
		if trc == "l":
			self.trc_ctrl.SetSelection(1)
		elif trc == "709":
			self.trc_ctrl.SetSelection(2)
		elif trc == "240":
			self.trc_ctrl.SetSelection(4)
		elif trc == "s":
			self.trc_ctrl.SetSelection(5)
		elif bt1886:
			self.trc_ctrl.SetSelection(3)
			self.trc_textctrl.SetValue(str(trc))
			self.trc_textctrl.Hide()
			self.trc_type_ctrl.SetSelection(1)
			self.trc_type_ctrl.Hide()
		elif trc:
			self.trc_ctrl.SetSelection(0)
			self.trc_textctrl.SetValue(str(trc))
			self.trc_textctrl.Show()
			self.trc_textctrl.Enable(not update_cal)
			self.trc_type_ctrl.SetSelection(
				self.trc_types_ba.get(getcfg("trc.type"), 
				self.trc_types_ba.get(defaults["trc.type"])))
			self.trc_type_ctrl.Show(getcfg("show_advanced_calibration_options"))
			self.trc_type_ctrl.Enable(not update_cal)

		self.ambient_viewcond_adjust_cb.SetValue(
			bool(int(getcfg("calibration.ambient_viewcond_adjust"))))
		self.ambient_viewcond_adjust_textctrl.ChangeValue(
			str(getcfg("calibration.ambient_viewcond_adjust.lux")))
		self.ambient_viewcond_adjust_textctrl.Enable(
			not update_cal and 
			bool(int(getcfg("calibration.ambient_viewcond_adjust"))))

		self.profile_type_ctrl.SetSelection(
			self.profile_types_ba.get(getcfg("profile.type"), 
			self.profile_types_ba.get(defaults["profile.type"])))

		self.update_black_output_offset_ctrl()

		self.black_point_correction_ctrl.SetValue(
			int(Decimal(str(getcfg("calibration.black_point_correction"))) * 
							100))
		self.black_point_correction_intctrl.SetValue(
			int(Decimal(str(getcfg("calibration.black_point_correction"))) * 
							100))

		self.black_point_rate_ctrl.SetValue(
			int(Decimal(str(getcfg("calibration.black_point_rate"))) * 100))
		self.black_point_rate_floatctrl.SetValue(
			getcfg("calibration.black_point_rate"))

		q = self.quality_ba.get(getcfg("calibration.quality"), 
								self.quality_ba.get(
									defaults["calibration.quality"]))
		self.calibration_quality_ctrl.SetValue(q)
		self.set_calibration_quality_label(self.quality_ab[q])

		self.interactive_display_adjustment_cb.SetValue(not update_cal and 
			bool(int(getcfg("calibration.interactive_display_adjustment"))))

		self.black_point_compensation_cb.Enable(not update_cal)
		self.black_point_compensation_cb.SetValue(
			bool(int(getcfg("profile.black_point_compensation"))))

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

		self.low_quality_b2a_cb.SetValue(enable_gamap and
										 getcfg("profile.quality.b2a") == "l")
		self.low_quality_b2a_cb.Enable(enable_gamap)

		if hasattr(self, "gamapframe"):
			self.gamapframe.update_controls()

		if getattr(self, "lut3dframe", None):
			self.lut3dframe.set_profile("output")

		if getattr(self, "reportframe", None):
			self.reportframe.set_profile("output")

		if update_profile_name:
			self.profile_name_textctrl.ChangeValue(getcfg("profile.name"))
			self.update_profile_name()

		self.update_main_controls()
		
		self.panel.Thaw()

		self.updatingctrls = False
	
	def update_black_output_offset_ctrl(self):
		self.black_output_offset_ctrl.SetValue(
			int(Decimal(str(getcfg("calibration.black_output_offset"))) * 100))
		self.black_output_offset_intctrl.SetValue(
			int(Decimal(str(getcfg("calibration.black_output_offset"))) * 100))
	
	def update_black_point_rate_ctrl(self):
		self.calpanel.Freeze()
		enable = not(self.calibration_update_cb.GetValue())
		show = (bool(getcfg("show_advanced_calibration_options")) and
				defaults["calibration.black_point_rate.enabled"])
		self.black_point_rate_label.GetContainingSizer().Show(
			self.black_point_rate_label,
			show)
		self.black_point_rate_ctrl.GetContainingSizer().Show(
			self.black_point_rate_ctrl,
			show)
		self.black_point_rate_ctrl.Enable(
			enable and 
			getcfg("calibration.black_point_correction") < 1 and 
			defaults["calibration.black_point_rate.enabled"])
		self.black_point_rate_floatctrl.GetContainingSizer().Show(
			self.black_point_rate_floatctrl,
			show)
		self.black_point_rate_floatctrl.Enable(
			enable  and 
			getcfg("calibration.black_point_correction") < 1 and 
			defaults["calibration.black_point_rate.enabled"])
		self.calpanel.Layout()
		self.calpanel.Thaw()
	
	def update_drift_compensation_ctrls(self):
		self.calpanel.Freeze()
		self.blacklevel_drift_compensation.GetContainingSizer().Show(
			self.blacklevel_drift_compensation,
			self.worker.argyll_version >= [1, 3, 0])
		self.whitelevel_drift_compensation.GetContainingSizer().Show(
			self.whitelevel_drift_compensation,
			self.worker.argyll_version >= [1, 3, 0])
		self.calpanel.Layout()
		self.calpanel.Thaw()
	
	def blacklevel_drift_compensation_handler(self, event):
		setcfg("drift_compensation.blacklevel", 
			   int(self.blacklevel_drift_compensation.GetValue()))
	
	def whitelevel_drift_compensation_handler(self, event):
		setcfg("drift_compensation.whitelevel", 
			   int(self.whitelevel_drift_compensation.GetValue()))

	def calibration_update_ctrl_handler(self, event):
		if debug:
			safe_print("[D] calibration_update_ctrl_handler called for ID %s "
					   "%s event type %s %s" % (event.GetId(), 
												getevtobjname(event, self), 
												event.GetEventType(), 
												getevttype(event)))
		setcfg("calibration.update", 
			   int(self.calibration_update_cb.GetValue()))
		setcfg("profile.update", 
			   int(self.calibration_update_cb.GetValue() and is_profile()))
		self.update_controls()

	def enable_spyder2_handler(self, event):
		self.update_menus()
		if check_set_argyll_bin():
			cmd, args = get_argyll_util("spyd2en"), ["-v"]
			if sys.platform in ("darwin", "win32"):
				# Look for Spyder.lib/CVSpyder.dll ourself because spyd2en will 
				# only try some fixed paths
				if sys.platform == "darwin":
					wildcard = os.path.join(os.path.sep, "Applications", 
											"Spyder2*", "Spyder2*.app", 
											"Contents", "MacOSClassic", 
											"Spyder.lib")
				else:
					wildcard = os.path.join(getenvu("PROGRAMFILES", ""), 
											"ColorVision", "Spyder2*", 
											"CVSpyder.dll")
				safe_print(u"Looking for install at '%s'" % wildcard)
				for path in glob.glob(wildcard):
					args += [path]
					break
			result = self.worker.exec_cmd(cmd, args, capture_output=True, 
										  skip_scripts=True, silent=False,
										  asroot=self.worker.argyll_version < [1, 2, 0] or 
												 (sys.platform == "darwin" and mac_ver()[0] >= '10.6'),
										  title=lang.getstr("enable_spyder2"))
			if not isinstance(result, Exception) and result:
				InfoDialog(self, msg=lang.getstr("enable_spyder2_success"), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-information"),
						   log=False)
				self.update_menus()
			else:
				if isinstance(result, Exception):
					show_result_dialog(result, self)
					if getcfg("dry_run"):
						return
				# prompt for installer executable
				dlg = ConfirmDialog(self, 
									msg=lang.getstr("locate_spyder2_setup"), 
									ok=lang.getstr("continue"), 
									cancel=lang.getstr("cancel"), 
									bitmap=geticon(32, "dialog-information"))
				result = dlg.ShowModal()
				if result != wx.ID_OK:
					return
				defaultDir, defaultFile = expanduseru("~"), ""
				dlg = wx.FileDialog(self, lang.getstr("file.select"),
									defaultDir=defaultDir, 
									defaultFile=defaultFile, 
									wildcard=lang.getstr("filetype.any") + "|*", 
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
					cmd, args = get_argyll_util("spyd2en"), ["-v", path]
					result = self.worker.exec_cmd(cmd, args, 
												  capture_output=True, 
												  skip_scripts=True, 
												  silent=False,
												  asroot=self.worker.argyll_version < [1, 2, 0] or 
														 (sys.platform == "darwin" and mac_ver()[0] >= '10.6'),
												  title=lang.getstr("enable_spyder2"))
					if not isinstance(result, Exception) and result:
						InfoDialog(self, 
								   msg=lang.getstr("enable_spyder2_success"), 
								   ok=lang.getstr("ok"), 
								   bitmap=geticon(32, "dialog-information"),
								   log=False)
						self.update_menus()
					else:
						if isinstance(result, Exception):
							show_result_dialog(result, self)
						InfoDialog(self, 
								   msg=lang.getstr("enable_spyder2_failure"), 
								   ok=lang.getstr("ok"), 
								   bitmap=geticon(32, "dialog-error"),
								   log=False)

	def extra_args_handler(self, event):
		if not hasattr(self, "extra_args"):
			self.extra_args = ExtraArgsFrame(self)
			self.extra_args.Center()
		if self.extra_args.IsShownOnScreen():
			self.extra_args.Raise()
		else:
			self.extra_args.Show()

	def use_separate_lut_access_handler(self, event):
		setcfg("use_separate_lut_access", 
			   int(self.menuitem_use_separate_lut_access.IsChecked()))
		self.update_displays()

	def do_not_use_video_lut_handler(self, event):
		do_not_use_video_lut = self.menuitem_do_not_use_video_lut.IsChecked()
		display_name = config.get_display_name()
		recommended = {"madVR": True}.get(display_name, False)
		if do_not_use_video_lut != recommended:
			dlg = ConfirmDialog(self,
								msg=lang.getstr("calibration.do_not_use_video_lut.warning"),  
								ok=lang.getstr("yes"), 
								cancel=lang.getstr("no"), 
								bitmap=geticon(32, "dialog-warning"), log=False)
			result = dlg.ShowModal()
			dlg.Destroy()
			if result != wx.ID_OK:
				self.menuitem_do_not_use_video_lut.Check(recommended)
				return
		setcfg("calibration.use_video_lut", 
			   int(not do_not_use_video_lut))
		if display_name != "madVR":
			setcfg("calibration.use_video_lut.backup", None)

	def allow_skip_sensor_cal_handler(self, event):
		setcfg("allow_skip_sensor_cal", 
			   int(self.menuitem_allow_skip_sensor_cal.IsChecked()))

	def enable_argyll_debug_handler(self, event):
		if not getcfg("argyll.debug"):
			dlg = ConfirmDialog(self, msg=lang.getstr("argyll.debug.warning1"),  
								ok=lang.getstr("ok"), 
								cancel=lang.getstr("cancel"), 
								bitmap=geticon(32, "dialog-warning"), log=False)
			result = dlg.ShowModal()
			dlg.Destroy()
			if result != wx.ID_OK:
				self.menuitem_enable_argyll_debug.Check(False)
				return
			InfoDialog(self, msg=lang.getstr("argyll.debug.warning2"), 
					   bitmap=geticon(32, "dialog-warning"), log=False)
		setcfg("argyll.debug", 
			   int(self.menuitem_enable_argyll_debug.IsChecked()))

	def enable_dry_run_handler(self, event):
		setcfg("dry_run", int(self.menuitem_enable_dry_run.IsChecked()))
	
	def enable_menus(self, enable=True):
		for menu, label in self.menubar.GetMenus():
			for item in menu.GetMenuItems():
				item.Enable(enable)
		if enable:
			self.update_menus()

	def lut3d_create_handler(self, event):
		""" Assign and initialize the 3DLUT creation window """
		if not getattr(self, "lut3dframe", None):
			self.init_lut3dframe()
		if self.lut3dframe.IsShownOnScreen():
			self.lut3dframe.Raise()
		else:
			self.lut3dframe.Show(not self.lut3dframe.IsShownOnScreen())

	def profile_quality_warning_handler(self, event):
		q = self.get_profile_quality()
		if q == "u":
			InfoDialog(self, msg=lang.getstr("quality.ultra.warning"), 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-warning"), log=False)

	def profile_quality_b2a_ctrl_handler(self, event):
		if self.low_quality_b2a_cb.GetValue():
			v = "l"
		else:
			v = None
		if v != getcfg("profile.quality.b2a"):
			self.profile_settings_changed()
		setcfg("profile.quality.b2a", v)

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
		elif q == "u":
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
			if getattr(self, "lut3dframe", None):
				self.lut3dframe.set_profile("output")
			if getattr(self, "reportframe", None):
				self.reportframe.set_profile("output")
	
	def settings_discard_changes(self, sel=None, keep_changed_state=False):
		""" Update the calibration file control and remove the leading
		asterisk (*) from items """
		if sel is None:
			sel = self.calibration_file_ctrl.GetSelection()
		if not keep_changed_state: setcfg("settings.changed", 0)
		items = self.calibration_file_ctrl.GetItems()
		changed = False
		for j, item in enumerate(items):
			#if j != sel and item[0] == "*":
			if item[0] == "*":
				items[j] = item[2:]
				changed = True
		if changed:
			self.calibration_file_ctrl.Freeze()
			self.calibration_file_ctrl.SetItems(items)
			self.calibration_file_ctrl.SetSelection(sel)
			self.calibration_file_ctrl.Thaw()
			
	def settings_confirm_discard(self):
		""" Show a dialog for user to confirm or cancel discarding changed
		settings """
		sel = self.calibration_file_ctrl.GetSelection()
		cal = getcfg("calibration.file") or ""
		if not cal in self.recent_cals:
			self.recent_cals.append(cal)
		# The case-sensitive index could fail because of 
		# case insensitive file systems, e.g. if the 
		# stored filename string is 
		# "C:\Users\Name\AppData\dispcalGUI\storage\MyFile"
		# but the actual filename is 
		# "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
		# (maybe because the user renamed the file)
		idx = index_fallback_ignorecase(self.recent_cals, 
										cal)
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
		self.set_calibration_quality_label(q)
		if q != getcfg("calibration.quality"):
			self.profile_settings_changed()
		setcfg("calibration.quality", q)
		self.update_profile_name()
	
	def set_calibration_quality_label(self, q):
		if q == "v":
			self.calibration_quality_info.SetLabel(
				lang.getstr("calibration.speed.veryhigh"))
		elif q == "l":
			self.calibration_quality_info.SetLabel(
				lang.getstr("calibration.speed.high"))
		elif q == "m":
			self.calibration_quality_info.SetLabel(
				lang.getstr("calibration.speed.medium"))
		elif q == "h":
			self.calibration_quality_info.SetLabel(
				lang.getstr("calibration.speed.low"))
		elif q == "u":
			self.calibration_quality_info.SetLabel(
				lang.getstr("calibration.speed.verylow"))

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

	def black_point_compensation_ctrl_handler(self, event):
		v = int(self.black_point_compensation_cb.GetValue())
		if v != getcfg("profile.black_point_compensation"):
			self.profile_settings_changed()
		setcfg("profile.black_point_compensation", v)
	
	def black_point_correction_auto_handler(self, event=None):
		if event:
			auto = self.black_point_correction_auto_cb.GetValue()
			setcfg("calibration.black_point_correction.auto", int(auto))
			self.cal_changed()
		else:
			auto = getcfg("calibration.black_point_correction.auto")
			self.black_point_correction_auto_cb.SetValue(bool(auto))
		show = bool(getcfg("show_advanced_calibration_options")) and not auto
		self.calpanel.Freeze()
		self.black_point_correction_ctrl.Show(show)
		self.black_point_correction_intctrl.Show(show)
		self.black_point_correction_intctrl_label.Show(show)
		self.calpanel.Layout()
		self.calpanel.Refresh()
		self.calpanel.Thaw()

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
		self.black_point_rate_floatctrl.Enable(
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
		if event.GetId() == self.black_point_rate_floatctrl.GetId():
			self.black_point_rate_ctrl.SetValue(
				int(round(self.black_point_rate_floatctrl.GetValue() * 100)))
		else:
			self.black_point_rate_floatctrl.SetValue(
				self.black_point_rate_ctrl.GetValue() / 100.0)
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
		if float(v) > 0 and self.trc_ctrl.GetSelection() == 3:
			self.restore_trc_backup()
			if getcfg("calibration.black_output_offset.backup", False):
				setcfg("calibration.black_output_offset.backup", None)
			self.calpanel.Freeze()
			self.trc_ctrl.SetSelection(0)
			self.trc_textctrl.Show()
			self.trc_type_ctrl.Show(getcfg("show_advanced_calibration_options"))
			self.calpanel.Layout()
			self.calpanel.Refresh()
			self.calpanel.Thaw()
		if float(v) != getcfg("calibration.black_output_offset"):
			self.cal_changed()
		setcfg("calibration.black_output_offset", v)
		self.update_profile_name()
	
	def ambient_measure_handler(self, event):
		""" Start measuring ambient illumination """
		if not check_set_argyll_bin():
			return
		# Minimum Windows version: XP or Server 2003
		if sys.platform == "win32" and sys.getwindowsversion() < (5, 1):
			show_result_dialog(Error(lang.getstr("windows.version.unsupported")))
			return
		safe_print("-" * 80)
		safe_print(lang.getstr("ambient.measure"))
		self.stop_timers()
		self.worker.interactive = False
		self.worker.start(self.ambient_measure_consumer, 
						  self.ambient_measure_producer, 
						  ckwargs={"event_id": event.GetId()},
						  progress_title=lang.getstr("ambient.measure"),
						  interactive_frame="ambient")
	
	def ambient_measure_producer(self):
		""" Process spotread output for ambient readings """
		cmd = get_argyll_util("spotread")
		args = ["-v", "-a", "-x"]
		if getcfg("extra_args.spotread").strip():
			args += parse_argument_string(getcfg("extra_args.spotread"))
		self.worker.add_measurement_features(args, False)
		return self.worker.exec_cmd(cmd, args, capture_output=True,
									skip_scripts=True)
	
	def ambient_measure_consumer(self, result=None, event_id=None):
		self.start_timers()
		if not result or isinstance(result, Exception):
			if getattr(self.worker, "subprocess", None):
				self.worker.quit_terminate_cmd()
			if isinstance(result, Exception):
				show_result_dialog(result, self)
			return
		safe_print(lang.getstr("success"))
		result = re.sub("[^\t\n\r\x20-\x7f]", "",
						"".join(self.worker.output)).strip()
		if not result:
			wx.Bell()
			return
		if getcfg("whitepoint.colortemp.locus") == "T":
			K = re.search("Planckian temperature += (\d+(?:\.\d+)?)K", 
						  result, re.I)
		else:
			K = re.search("Daylight temperature += (\d+(?:\.\d+)?)K", 
						  result, re.I)
		lux = re.search("Ambient = (\d+(?:\.\d+)) Lux", result, re.I)
		set_whitepoint = event_id == self.whitepoint_measure_btn.GetId()
		set_ambient = event_id == self.ambient_measure_btn.GetId()
		if set_whitepoint and not set_ambient and bool(getcfg("show_advanced_calibration_options")):
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
					self.whitepoint_ctrl.SetSelection(2)
					self.whitepoint_ctrl_handler(
						CustomEvent(wx.EVT_CHOICE.evtType[0], 
									self.whitepoint_ctrl))
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
					if v < 0.000001 or v > sys.maxint:
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
		if event.GetId() == self.black_luminance_textctrl.GetId() and (
		   self.black_luminance_ctrl.GetSelection() != 1 or 
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
		self.calpanel.Freeze()
		if self.black_luminance_ctrl.GetSelection() == 1: # cd/m2
			self.black_luminance_textctrl.Show()
			self.black_luminance_textctrl_label.Show()
			try:
				v = float(self.black_luminance_textctrl.GetValue().replace(",", 
																		   "."))
				if v < 0.000001 or v > 100000:
					raise ValueError()
				self.black_luminance_textctrl.ChangeValue("%.6f" % v)
			except ValueError:
				wx.Bell()
				self.black_luminance_textctrl.ChangeValue(
					"%.6f" % getcfg("calibration.black_luminance"))
			if (event.GetId() == self.black_luminance_ctrl.GetId() and
				self.black_luminance_ctrl.GetSelection() == 1):
				self.black_luminance_textctrl.SetFocus()
				self.black_luminance_textctrl.SelectAll()
		else:
			self.black_luminance_textctrl.Hide()
			self.black_luminance_textctrl_label.Hide()
		self.calpanel.Layout()
		self.calpanel.Refresh()
		self.calpanel.Thaw()
		v = self.get_black_luminance()
		if v != str(getcfg("calibration.black_luminance", False)):
			self.cal_changed()
		setcfg("calibration.black_luminance", v)
		self.update_profile_name()
		if event.GetEventType() == wx.EVT_KILL_FOCUS.evtType[0]:
			event.Skip()

	def luminance_ctrl_handler(self, event):
		if event.GetId() == self.luminance_textctrl.GetId() and (
		   self.luminance_ctrl.GetSelection() != 1 or 
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
		self.calpanel.Freeze()
		if self.luminance_ctrl.GetSelection() == 1: # cd/m2
			self.luminance_textctrl.Show()
			self.luminance_textctrl_label.Show()
			try:
				v = float(self.luminance_textctrl.GetValue().replace(",", "."))
				if v < 0.000001 or v > 100000:
					raise ValueError()
				self.luminance_textctrl.ChangeValue(str(v))
			except ValueError:
				wx.Bell()
				self.luminance_textctrl.ChangeValue(
					str(getcfg("calibration.luminance")))
			if (event.GetId() == self.luminance_ctrl.GetId() and
				self.luminance_ctrl.GetSelection() == 1):
				self.luminance_textctrl.SetFocus()
				self.luminance_textctrl.SelectAll()
		else:
			self.luminance_textctrl.Hide()
			self.luminance_textctrl_label.Hide()
		self.calpanel.Layout()
		self.calpanel.Refresh()
		self.calpanel.Thaw()
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
			setcfg("whitepoint.colortemp.locus", v)
			self.whitepoint_ctrl_handler(
				CustomEvent(wx.EVT_CHOICE.evtType[0], 
				self.whitepoint_ctrl), False)
			self.cal_changed()
		self.update_profile_name()

	def whitepoint_ctrl_handler(self, event, cal_changed=True):
		if event.GetId() == self.whitepoint_colortemp_textctrl.GetId() and (
		   self.whitepoint_ctrl.GetSelection() != 1 or 
		   str(int(getcfg("whitepoint.colortemp"))) == 
		   self.whitepoint_colortemp_textctrl.GetValue()):
			event.Skip()
			return
		if event.GetId() == self.whitepoint_x_textctrl.GetId() and (
		   self.whitepoint_ctrl.GetSelection() != 2 or 
		   str(float(getcfg("whitepoint.x"))) == 
		   self.whitepoint_x_textctrl.GetValue()):
			event.Skip()
			return
		if event.GetId() == self.whitepoint_y_textctrl.GetId() and (
		   self.whitepoint_ctrl.GetSelection() != 2 or 
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
		self.calpanel.Freeze()
		if self.whitepoint_ctrl.GetSelection() == 2: # x,y chromaticity coordinates
			self.whitepoint_colortemp_locus_label.Hide()
			self.whitepoint_colortemp_locus_ctrl.Hide()
			self.whitepoint_colortemp_textctrl.Hide()
			self.whitepoint_colortemp_label.Hide()
			self.whitepoint_x_textctrl.Show()
			self.whitepoint_x_label.Show()
			self.whitepoint_y_textctrl.Show()
			self.whitepoint_y_label.Show()
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
			if (event.GetId() == self.whitepoint_ctrl.GetId() and
				self.whitepoint_ctrl.GetSelection() == 2 and
				not self.updatingctrls):
				self.whitepoint_x_textctrl.SetFocus()
				self.whitepoint_x_textctrl.SelectAll()
		elif self.whitepoint_ctrl.GetSelection() == 1:
			self.whitepoint_colortemp_locus_label.Show()
			self.whitepoint_colortemp_locus_ctrl.Show()
			self.whitepoint_colortemp_textctrl.Show()
			self.whitepoint_colortemp_label.Show()
			self.whitepoint_x_textctrl.Hide()
			self.whitepoint_x_label.Hide()
			self.whitepoint_y_textctrl.Hide()
			self.whitepoint_y_label.Hide()
			try:
				v = float(
					self.whitepoint_colortemp_textctrl.GetValue().replace(
						",", "."))
				if v < 1000 or v > 15000:
					raise ValueError()
				self.whitepoint_colortemp_textctrl.SetValue(str(stripzeros(v)))
			except ValueError:
				wx.Bell()
				self.whitepoint_colortemp_textctrl.SetValue(
					str(stripzeros(getcfg("whitepoint.colortemp"))))
			if cal_changed:
				v = float(self.whitepoint_colortemp_textctrl.GetValue())
				if getcfg("whitepoint.colortemp") == v and not \
				   getcfg("whitepoint.x") and not getcfg("whitepoint.y"):
					cal_changed = False
			setcfg("whitepoint.colortemp", int(v))
			setcfg("whitepoint.x", None)
			setcfg("whitepoint.y", None)
			if (event.GetId() == self.whitepoint_ctrl.GetId() and
				self.whitepoint_ctrl.GetSelection() == 1 and
				not self.updatingctrls):
				self.whitepoint_colortemp_textctrl.SetFocus()
				self.whitepoint_colortemp_textctrl.SelectAll()
		else:
			self.whitepoint_colortemp_locus_label.Show()
			self.whitepoint_colortemp_locus_ctrl.Show()
			self.whitepoint_colortemp_textctrl.Hide()
			self.whitepoint_colortemp_label.Hide()
			self.whitepoint_x_textctrl.Hide()
			self.whitepoint_x_label.Hide()
			self.whitepoint_y_textctrl.Hide()
			self.whitepoint_y_label.Hide()
			if not getcfg("whitepoint.colortemp") and \
			   not getcfg("whitepoint.x") and not getcfg("whitepoint.y"):
				cal_changed = False
			setcfg("whitepoint.colortemp", None)
			self.whitepoint_colortemp_textctrl.SetValue(
					str(stripzeros(getcfg("whitepoint.colortemp"))))
			setcfg("whitepoint.x", None)
			setcfg("whitepoint.y", None)
		self.whitepoint_measure_btn.Show(self.whitepoint_ctrl.GetSelection() > 0)
		self.calpanel.Layout()
		self.calpanel.Refresh()
		self.calpanel.Thaw()
		if self.whitepoint_ctrl.GetSelection() != 2:
			if getcfg("whitepoint.colortemp.locus") == "T":
				# Planckian locus
				xyY = planckianCT2xyY(getcfg("whitepoint.colortemp"))
			else:
				# Daylight locus
				xyY = CIEDCCT2xyY(getcfg("whitepoint.colortemp"))
			if xyY:
				self.whitepoint_x_textctrl.ChangeValue(
					str(stripzeros(round(xyY[0], 6))))
				self.whitepoint_y_textctrl.ChangeValue(
					str(stripzeros(round(xyY[1], 6))))
			else:
				self.whitepoint_x_textctrl.ChangeValue("")
				self.whitepoint_y_textctrl.ChangeValue("")
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
		if event.GetId() == self.trc_textctrl.GetId() and (
		   self.trc_ctrl.GetSelection() != 0 or stripzeros(getcfg("trc")) == 
		   stripzeros(self.trc_textctrl.GetValue())):
			event.Skip()
			return
		if debug:
			safe_print("[D] trc_ctrl_handler called for ID %s %s event type %s "
					   "%s" % (event.GetId(), getevtobjname(event, self), 
							   event.GetEventType(), getevttype(event)))
		self.calpanel.Freeze()
		if self.trc_ctrl.GetSelection() == 3:
			# BT.1886
			setcfg("trc.backup", self.trc_textctrl.GetValue().replace(",", "."))
			self.trc_textctrl.SetValue("2.4")
			setcfg("trc.type.backup", getcfg("trc.type"))
			setcfg("trc.type", "G")
			self.trc_type_ctrl.SetSelection(1)
			setcfg("calibration.black_output_offset.backup",
				   getcfg("calibration.black_output_offset"))
			setcfg("calibration.black_output_offset", 0)
			self.black_output_offset_ctrl.SetValue(0)
			self.black_output_offset_intctrl.SetValue(0)
		elif event.GetId() == self.trc_ctrl.GetId():
			self.restore_trc_backup()
			if getcfg("calibration.black_output_offset.backup", False):
				setcfg("calibration.black_output_offset",
					   getcfg("calibration.black_output_offset.backup"))
				setcfg("calibration.black_output_offset.backup", None)
				self.update_black_output_offset_ctrl()
		if self.trc_ctrl.GetSelection() == 0:
			self.trc_textctrl.Show()
			self.trc_type_ctrl.Show(getcfg("show_advanced_calibration_options"))
			try:
				v = float(self.trc_textctrl.GetValue().replace(",", "."))
				if v == 0 or v > 10:
					raise ValueError()
				if str(v) != self.trc_textctrl.GetValue():
					self.trc_textctrl.SetValue(str(v))
			except ValueError:
				wx.Bell()
				self.trc_textctrl.SetValue(str(getcfg("trc")))
			if event.GetId() == self.trc_ctrl.GetId():
				self.trc_textctrl.SetFocus()
				self.trc_textctrl.SelectAll()
		else:
			self.trc_textctrl.Hide()
			self.trc_type_ctrl.Hide()
		self.calpanel.Layout()
		self.calpanel.Refresh()
		self.calpanel.Thaw()
		trc = self.get_trc()
		if cal_changed:
			if trc != str(getcfg("trc")):
				self.cal_changed()
		setcfg("trc", trc)
		if cal_changed:
			self.update_profile_name()
		if event.GetEventType() == wx.EVT_KILL_FOCUS.evtType[0]:
			event.Skip()
		if (trc in ("240", "709", "s") and not
		    (bool(int(getcfg("calibration.ambient_viewcond_adjust"))) and 
			 getcfg("calibration.ambient_viewcond_adjust.lux")) and
			getcfg("trc.should_use_viewcond_adjust.show_msg") and
			getcfg("show_advanced_calibration_options")):
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
	
	def restore_trc_backup(self):
		if getcfg("trc.backup", False):
			setcfg("trc", getcfg("trc.backup"))
			setcfg("trc.backup", None)
			self.trc_textctrl.SetValue(str(getcfg("trc")))
		if getcfg("trc.type.backup", False):
			setcfg("trc.type", getcfg("trc.type.backup"))
			setcfg("trc.type.backup", None)
			self.trc_type_ctrl.SetSelection(
				self.trc_types_ba.get(getcfg("trc.type"), 
									  self.trc_types_ba.get(defaults["trc.type"])))

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
	
	def measure_uniformity_handler(self, event):
		""" Start measuring display device uniformity """
		self.HideAll()
		self.worker.interactive = True
		self.worker.start(self.measure_uniformity_consumer,
						  self.measure_uniformity_producer, resume=False, 
						  continue_next=False, interactive_frame="uniformity")
	
	def measure_uniformity_producer(self):
		cmd, args = get_argyll_util("spotread"), ["-v", "-e", "-T"]
		if cmd:
			self.worker.add_measurement_features(args, display=False)
			return self.worker.exec_cmd(cmd, args, skip_scripts=True)
		else:
			wx.CallAfter(show_result_dialog,
						 Error(lang.getstr("argyll.util.not_found",
										   "spotread")), self)
	
	def measure_uniformity_consumer(self, result):
		self.Show()
		if isinstance(result, Exception):
			show_result_dialog(result, self)
			if getcfg("dry_run"):
				return
		for i, line in enumerate(self.worker.output):
			if line.startswith("spotread: Error"):
				show_result_dialog(Error(line.strip()), self)
			elif line.startswith("spotread: Warning"):
				show_result_dialog(Warn(line.strip()), self)
	
	def profile_share_get_meta_error(self, profile):
		""" Check for required metadata in profile to allow sharing.
		
		The treshold for average delta E 1976 is 1.0
		
		"""
		if ("meta" in profile.tags and
			isinstance(profile.tags.meta, ICCP.DictType)):
			try:
				avg_dE76 = float(profile.tags.meta.getvalue("ACCURACY_dE76_avg"))
			except (TypeError, ValueError):
				return lang.getstr("profile.share.meta_missing")
			else:
				threshold = 1.0
				if avg_dE76 and avg_dE76 > threshold:
					return lang.getstr("profile.share.avg_dE_too_high",
									   ("%.2f" % avg_dE76, "%.2f" % threshold))
				else:
					# Check for EDID metadata
					metadata = profile.tags.meta
					if (not "EDID_model_id" in metadata or
						(not "EDID_model" in metadata and
						 metadata["EDID_model_id"] == "0") or
						not "EDID_mnft_id" in metadata or
						not "EDID_mnft" in metadata or
						not "EDID_manufacturer" in metadata or
						metadata["EDID_manufacturer"] == metadata["EDID_mnft"] or
						not "OPENICC_automatic_generated" in metadata):
						return lang.getstr("profile.share.meta_missing")
		else:
			return lang.getstr("profile.share.meta_missing")
	
	def profile_share_handler(self, event):
		""" Share ICC profile via http://icc.opensuse.org """
		# Select profile
		profile = self.select_profile()
		if not profile:
			return
		
		# Check meta and profcheck data
		error = self.profile_share_get_meta_error(profile)
		if error:
			InfoDialog(getattr(self, "modaldlg", self), msg=error,
					   ok=lang.getstr("ok"), bitmap=geticon(32, "dialog-error"))
			return
		
		# Get options from profile
		options_dispcal, options_colprof = get_options_from_profile(profile)
		gamma = None
		for option in options_dispcal:
			if option.startswith("g") or option.startswith("G"):
				option = option[1:]
				gamma = {"240": "SMPTE 240M",
						 "709": "Rec. 709",
						 "l": "L*",
						 "s": "sRGB"}.get(option, "Gamma %s" % option)

		metadata = profile.tags.meta
		# Model will be shown in overview on http://icc.opensuse.org
		model = metadata.getvalue("EDID_model",
								  profile.getDeviceModelDescription() or
								  metadata["EDID_model_id"],
								  None)
		description = model
		date = metadata.getvalue("EDID_date", "", None).split("-T")
		if len(date) == 2:
			year = int(date[0])
			week = int(date[1])
			date = datetime.date(int(year), 1, 1) + datetime.timedelta(weeks=week)
			description += " '" + strftime("%y", date.timetuple())
		if "vcgt" in profile.tags:
			if profile.tags.vcgt.is_linear():
				vcgt = "linear VCGT"
			else:
				vcgt = "VCGT"
		else:
			vcgt = "no VCGT"
		if vcgt:
			description += ", " + vcgt
		whitepoint = "%iK" % round(XYZ2CCT(*profile.tags.wtpt.values()))
		description += ", " + whitepoint
		description += u", %i cd/m²" % profile.tags.lumi.Y 
		if gamma:
			description += ", " + gamma
		instrument = metadata.getvalue("MEASUREMENT_device")
		if instrument:
			for instrument_name in instruments:
				if instrument_name.lower() == instrument:
					instrument = instrument_name
					break
			description += ", " + instrument
		description += ", " + strftime("%Y-%m-%d", profile.dateTime.timetuple())
		dlg = ConfirmDialog(
			getattr(self, "modaldlg", self), 
			msg=lang.getstr("profile.share.enter_info"), 
			ok=lang.getstr("upload"), cancel=lang.getstr("cancel"), 
			bitmap=geticon(32, "dialog-information"), alt=lang.getstr("save"),
			wrap=100)
		# Description field
		dlg.sizer3.Add(wx.StaticText(dlg, -1, lang.getstr("description")), 1, 
					   flag=wx.TOP | wx.ALIGN_LEFT, border=12)
		dlg.description_txt_ctrl = wx.TextCtrl(dlg, -1, 
											   description)
		dlg.sizer3.Add(dlg.description_txt_ctrl, 1, 
					   flag=wx.TOP | wx.ALIGN_LEFT | wx.EXPAND, border=4)
		# Display properties
		boxsizer = wx.StaticBoxSizer(wx.StaticBox(dlg, -1,
												  lang.getstr("display.properties")),
									 wx.VERTICAL)
		dlg.sizer3.Add(boxsizer, 1, flag=wx.TOP | wx.EXPAND, border=12)
		box_gridsizer = wx.FlexGridSizer(0, 1)
		boxsizer.Add(box_gridsizer, 1, flag=wx.ALL, border=4)
		# Display panel surface type, connection
		gridsizer = wx.FlexGridSizer(0, 4, 4, 8)
		box_gridsizer.Add(gridsizer, 1, wx.ALIGN_LEFT)
		# Panel surface type
		gridsizer.Add(wx.StaticText(dlg, -1, lang.getstr("panel.surface")), 1, 
					   flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
		paneltypes = ["glossy", "matte"]
		dlg.panel_ctrl = wx.Choice(dlg, -1, 
								   choices=[""] + [lang.getstr(panel)
												   for panel in
												   paneltypes])
		panel_surface = metadata.getvalue("SCREEN_surface", "")
		try:
			index = dlg.panel_ctrl.GetItems().index(lang.getstr(panel_surface))
		except ValueError:
			index = 0
		dlg.panel_ctrl.SetSelection(index)
		gridsizer.Add(dlg.panel_ctrl, 1, flag=wx.RIGHT | wx.ALIGN_LEFT |
					  wx.ALIGN_CENTER_VERTICAL, border=8)
		# Connection type
		gridsizer.Add(wx.StaticText(dlg, -1,
									lang.getstr("display.connection.type")), 1,
					  flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL)
		connections = ["dvi", "displayport", "hdmi", "internal", "vga"]
		dlg.connection_ctrl = wx.Choice(dlg, -1, 
										choices=[lang.getstr(contype)
												 for contype in
												 connections])
		connection_type = metadata.getvalue("CONNECTION_type",
											"dvi")
		try:
			index = dlg.connection_ctrl.GetItems().index(lang.getstr(connection_type))
		except ValueError:
			index = 0
		dlg.connection_ctrl.SetSelection(index)
		gridsizer.Add(dlg.connection_ctrl, 1, flag=wx.RIGHT | wx.ALIGN_LEFT |
					  wx.ALIGN_CENTER_VERTICAL, border=8)
		display_settings_tabs = wx.Notebook(dlg, -1)
		# Column layout
		display_settings = ((# 1st tab
							 lang.getstr("osd") + ": " +
							 lang.getstr("settings.basic"), # Tab title
							 2, # Number of columns
							 (# 1st (left) column
							  (("preset", 100),
							   ("brightness", 50),
							   ("contrast", 50),
							   ("trc.gamma", 50),
							   ("blacklevel", 50),
							   ("hue", 50)),
							  # 2nd (right) column
							  (("", 0),
							   ("whitepoint.colortemp", 75),
							   ("whitepoint", 50),
							   ("saturation", 50)))),
							(# 2nd tab
							 lang.getstr("osd") + ": " +
							 lang.getstr("settings.additional"), # Tab title
							 3, # Number of columns
							 (# 1st (left) column
							  (("hue", 50), ),
							  # 2nd (middle) column
							  (("offset", 50), ),
							  # 3rd (right) column
							  (("saturation", 50), ))))
		display_settings_ctrls = []
		for tab_num, settings in enumerate(display_settings):
			panel = wx.Panel(display_settings_tabs, -1)
			panel.SetSizer(wx.BoxSizer(wx.VERTICAL))
			gridsizer = wx.FlexGridSizer(0, settings[1] * 2, 4, 12)
			panel.GetSizer().Add(gridsizer, 1, wx.ALL | wx.EXPAND, border=8)
			display_settings_tabs.AddPage(panel, settings[0])
			ctrls = []
			for column in settings[2]:
				for name, width in column:
					if name in ("whitepoint", ):
						components = ("red", "green", "blue")
					elif tab_num == 1 and name in ("hue", "offset",
												   "saturation"):
						components = ("red", "green", "blue", "cyan", "magenta",
									  "yellow")
					else:
						components = ("", )
					nameprefix = name
					for component in components:
						if component:
							name = nameprefix + " " + component
						if name:
							ctrl = wx.TextCtrl(panel, -1,
											   metadata.getvalue("OSD_settings_%s" %
																 re.sub("[ .]", "_", name), ""),
											   size=(width, -1),
											   name=name)
						else:
							ctrl = (0, 0)
						ctrls.append(ctrl)
						display_settings_ctrls.append(ctrl)
			# Add the controls to the sizer
			rows = int(math.ceil(len(ctrls) / float(settings[1])))
			for row_num in range(rows):
				for column_num in range(settings[1]):
					ctrl_index = row_num + column_num * rows
					if ctrl_index < len(ctrls):
						if isinstance(ctrls[ctrl_index], wx.Window):
							label = ctrls[ctrl_index].Name
							if (" " in label):
								label = label.split(" ")
								for i, part in enumerate(label):
									label[i] = lang.getstr(part)
								label = " ".join(label)
							else:
								label = lang.getstr(label)
							text = wx.StaticText(panel, -1, label)
						else:
							text = (0, 0)
						gridsizer.Add(text,
									  1, flag=wx.ALIGN_CENTER_VERTICAL |
											  wx.ALIGN_LEFT)
						gridsizer.Add(ctrls[ctrl_index], 1, 
									   flag=wx.ALIGN_CENTER_VERTICAL |
											wx.ALIGN_LEFT | wx.RIGHT, border=4)
		box_gridsizer.Add(display_settings_tabs, 1, 
					   flag=wx.TOP | wx.ALIGN_LEFT, border=8)
		# License field
		##dlg.sizer3.Add(wx.StaticText(dlg, -1, lang.getstr("license")), 1, 
					   ##flag=wx.TOP | wx.ALIGN_LEFT, border=12)
		##dlg.license_ctrl = wx.Choice(dlg, -1, 
									 ##choices=["http://www.color.org/registry/icc_license_2011.txt",
											  ##"http://www.gzip.org/zlib/zlib_license.html"])
		##dlg.license_ctrl.SetSelection(0)
		##sizer4 = wx.BoxSizer(wx.HORIZONTAL)
		##dlg.sizer3.Add(sizer4, 1, 
					   ##flag=wx.TOP | wx.ALIGN_LEFT, border=4)
		##sizer4.Add(dlg.license_ctrl, 1, 
					   ##flag=wx.RIGHT | wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL,
							##border=8)
		# License link button
		##dlg.license_link_ctrl = wx.BitmapButton(dlg, -1,
												##geticon(16, "dialog-information"), 
												##style=wx.NO_BORDER)
		##dlg.license_link_ctrl.SetToolTipString(lang.getstr("license"))
		##dlg.Bind(wx.EVT_BUTTON,
				 ##lambda event: launch_file(dlg.license_ctrl.GetValue()),
				 ##dlg.license_link_ctrl)
		##sizer4.Add(dlg.license_link_ctrl, flag=wx.ALIGN_LEFT |
				   ##wx.ALIGN_CENTER_VERTICAL)
		# Link to ICC Profile Taxi service
		dlg.sizer3.Add(wx.lib.hyperlink.HyperLinkCtrl(dlg, -1,
													  label="icc.opensuse.org", 
													  URL="http://icc.opensuse.org"),
					   flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL | wx.TOP,
					   border=12)
		dlg.description_txt_ctrl.SetFocus()
		dlg.sizer0.SetSizeHints(dlg)
		dlg.sizer0.Layout()
		dlg.Center()
		result = dlg.ShowModal()
		if result == wx.ID_CANCEL:
			return
		# Get meta prefix
		prefixes = (metadata.getvalue("prefix", "", None) or "CONNECTION_").split(",")
		if not "CONNECTION_" in prefixes:
			prefixes.append("CONNECTION_")
		# Update meta
		panel = dlg.panel_ctrl.GetSelection()
		if panel > 0:
			metadata["SCREEN_surface"] = paneltypes[panel - 1]
			if not "SCREEN_" in prefixes:
				prefixes.append("SCREEN_")
		# Update meta
		metadata["CONNECTION_type"] = connections[dlg.connection_ctrl.GetSelection()]
		for ctrl in display_settings_ctrls:
			if isinstance(ctrl, wx.TextCtrl) and ctrl.GetValue().strip():
				metadata["OSD_settings_%s" %
						 re.sub("[ .]", "_", ctrl.Name)] = ctrl.GetValue().strip()
			if not "OSD_" in prefixes:
				prefixes.append("OSD_")
		# Set meta prefix
		metadata["prefix"] = ",".join(prefixes)
		# Calculate profile ID
		profile.calculateID()
		# Save profile
		try:
			profile.write()
		except EnvironmentError, exception:
			show_result_dialog(exception, self)
		if result != wx.ID_OK:
			return
		# Get profile data
		data = profile.data
		# Add metadata which should not be reflected in profile
		metadata["model"] = model
		metadata["vcgt"] = int("vcgt" in profile.tags)
		# Upload
		params = {"description": dlg.description_txt_ctrl.GetValue(),
				  ##"licence": dlg.license_ctrl.GetValue()}
				  "licence": "http://www.color.org/registry/icc_license_2011.txt"}
		files = [("metadata", "metadata.json",
				  '{"org":{"freedesktop":{"openicc":{"device":{"monitor":[%s]}}}}}' %
				  metadata.to_json()),
				 ("profile", "profile.icc", data)]
		self.worker.interactive = False
		self.worker.start(self.profile_share_consumer, 
						  http_request, 
						  ckwargs={}, 
						  wkwargs={"domain": "dispcalgui.hoech.net" if test
											 else "icc.opensuse.org",
								   "request_type": "POST",
								   "path": "/print_r_post.php" if test
										   else "/upload",
								   "params": params,
								   "files": files},
						  progress_msg=lang.getstr("profile.share"),
						  stop_timers=False)

	def profile_share_consumer(self, result, parent=None):
		""" This function receives the response from the profile upload """
		if result is not False:
			safe_print(safe_unicode(result.read().strip(), "UTF-8"))
			parent = parent or getattr(self, "modaldlg", self)
			dlg = InfoDialog(parent, 
							 msg=lang.getstr("profile.share.success"),
							 ok=lang.getstr("ok"), 
							 bitmap=geticon(32, "dialog-information"),
							 show=False)
			# Link to ICC Profile Taxi service
			dlg.sizer3.Add(wx.lib.hyperlink.HyperLinkCtrl(dlg, -1,
														  label="icc.opensuse.org", 
														  URL="http://icc.opensuse.org"),
						   flag=wx.ALIGN_LEFT | wx.ALIGN_CENTER_VERTICAL |
								wx.TOP,
						   border=12)
			dlg.sizer0.SetSizeHints(dlg)
			dlg.sizer0.Layout()
			dlg.ok.SetDefault()
			dlg.ShowModalThenDestroy(parent)

	def install_profile_handler(self, event=None, profile_path=None):
		""" Install a profile. Show an error dialog if the profile is
		invalid or unsupported (only 'mntr' RGB profiles are allowed) """
		if not check_set_argyll_bin():
			return
		if profile_path is None:
			profile_path = getcfg("calibration.file")
		if profile_path:
			result = check_file_isfile(profile_path)
			if isinstance(result, Exception):
				show_result_dialog(result, self)
		else:
			result = False
		if not isinstance(result, Exception) and result:
			try:
				profile = ICCP.ICCProfile(profile_path)
			except (IOError, ICCP.ICCProfileInvalidError), exception:
				InfoDialog(self, msg=lang.getstr("profile.invalid") + 
									 "\n" + profile_path, 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				return
			if profile.profileClass != "mntr" or \
			   profile.colorSpace != "RGB":
				InfoDialog(self, msg=lang.getstr("profile.unsupported", 
												 (profile.profileClass, 
												  profile.colorSpace)) +
									 "\n" + profile_path, 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				return
			setcfg("calibration.file.previous", getcfg("calibration.file"))
			self.profile_finish(
				True, profile_path=profile_path, 
				skip_scripts=True,
				allow_show_log=False)

	def select_install_profile_handler(self, event):
		""" Show a dialog for user to select a profile for installation """
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
			setcfg("last_icc_path", path)
			setcfg("last_cal_or_icc_path", path)
			self.install_profile_handler(profile_path=path)

	def load_profile_cal_handler(self, event):
		""" Show a dialog for user to select a profile to load calibration
		(vcgt) from. """
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
				setcfg("last_icc_path", path)
				if self.install_cal(capture_output=True, 
									profile_path=path, 
									skip_scripts=True, 
									silent=not getcfg("dry_run"),
									title=lang.getstr("calibration.load_from_profile")) is True:
					self.lut_viewer_load_lut(profile=profile)
					if verbose >= 1: safe_print(lang.getstr("success"))
				elif not getcfg("dry_run"):
					if verbose >= 1: safe_print(lang.getstr("failure"))
					InfoDialog(self, msg=lang.getstr("calibration.load_error") + 
										 "\n" + path, 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
			else:
				setcfg("last_cal_path", path)
				if self.install_cal(capture_output=True, cal=path, 
									skip_scripts=True, silent=not getcfg("dry_run"),
									title=lang.getstr("calibration.load_from_cal")) is True:
					self.lut_viewer_load_lut(profile=cal_to_fake_profile(path))
					if verbose >= 1: safe_print(lang.getstr("success"))
				elif not getcfg("dry_run"):
					if verbose >= 1: safe_print(lang.getstr("failure"))

	def preview_handler(self, event=None, preview=False):
		""" Preview profile calibration (vcgt).
		
		Toggle between profile curves and previous calibration curves.
		
		"""
		if preview or self.preview.GetValue():
			cal = self.cal
		else:
			cal = getcfg("calibration.file.previous")
			if self.cal == cal:
				cal = False
			elif not cal:
				cal = True
		if cal is False: # linear
			profile = None
		else:
			if cal is True: # display profile
				profile = get_display_profile()
				if not profile:
					cal = False
			elif cal.lower().endswith(".icc") or \
				 cal.lower().endswith(".icm"):
				try:
					profile = ICCP.ICCProfile(cal)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					show_result_dialog(exception, self)
					profile = None
			else:
				profile = cal_to_fake_profile(cal)
		if profile:
			if verbose >= 1:
				safe_print(lang.getstr("calibration.loading"))
				if profile.fileName:
					safe_print(profile.fileName)
		else:
			if verbose >= 1: safe_print(lang.getstr("calibration.resetting"))
		if self.install_cal(capture_output=True, cal=cal, 
							skip_scripts=True, silent=True,
							title=lang.getstr("calibration.load_from_cal_or_profile")) is True:
			self.lut_viewer_load_lut(profile=profile)
			if verbose >= 1: safe_print(lang.getstr("success"))
		else:
			if verbose >= 1: safe_print(lang.getstr("failure"))
	
	def profile_load_on_login_handler(self, event=None):
		setcfg("profile.load_on_login", 
			   int(self.profile_load_on_login.GetValue()))
		if sys.platform == "win32" and sys.getwindowsversion() >= (6, 1):
			self.profile_load_on_login.Enable(is_superuser() or
											  not util_win.calibration_management_isenabled())
			self.profile_load_by_os.Enable(is_superuser() and
										   self.profile_load_on_login.GetValue())
			if (not self.profile_load_on_login.GetValue() and 
				self.profile_load_by_os.GetValue() and is_superuser()):
				self.profile_load_by_os.SetValue(False)
				self.profile_load_by_os_handler()
	
	def profile_load_by_os_handler(self, event=None):
		if is_superuser():
			# Enable calibration management under Windows 7
			try:
				util_win.enable_calibration_management(self.profile_load_by_os.GetValue())
			except Exception, exception:
				safe_print("util_win.enable_calibration_management(True): %s" %
						   safe_unicode(exception))

	def install_cal(self, capture_output=False, cal=None, profile_path=None,
					skip_scripts=False, silent=False, title=appname):
		""" 'Install' (load) a calibration from a calibration file or
		profile """
		if config.get_display_name() in ("Web", "Untethered", "madVR"):
			return True
		# Install using dispwin
		cmd, args = self.worker.prepare_dispwin(cal, profile_path, False)
		if not isinstance(cmd, Exception):
			result = self.worker.exec_cmd(cmd, args, capture_output, 
										  low_contrast=False, 
										  skip_scripts=skip_scripts, 
										  silent=silent,
										  title=title)
		else:
			result = cmd
		if not isinstance(result, Exception) and result:
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
			if isinstance(result, Exception) and getcfg("dry_run"):
				show_result_dialog(result, self)
				return
			if cal is False:
				InfoDialog(self, 
						   msg=lang.getstr("calibration.reset_error"), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"), log=False)
			else:
				InfoDialog(self, msg=lang.getstr("calibration.load_error"), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"), log=False)
		return result
	
	def update_measurement_report(self, event=None):
		""" Show file dialog to select a HTML measurement report
		for updating. Update the selected report and show it afterwards. """
		defaultDir, defaultFile = get_verified_path("last_filedialog_path")
		dlg = wx.FileDialog(self, lang.getstr("measurement_report.update"), 
							defaultDir=defaultDir, defaultFile=defaultFile, 
							wildcard=lang.getstr("filetype.html") + "|*.html;*.htm", 
							style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		dlg.Center(wx.BOTH)
		result = dlg.ShowModal()
		if result == wx.ID_OK:
			path = dlg.GetPath()
			setcfg("last_filedialog_path", path)
		dlg.Destroy()
		if result != wx.ID_OK:
			return
		try:
			report.update(path, pack=getcfg("report.pack_js"))
		except (IOError, OSError), exception:
			show_result_dialog(exception)
		else:
			# show report
			wx.CallAfter(launch_file, path)

	def verify_calibration_handler(self, event):
		if check_set_argyll_bin():
			self.setup_measurement(self.verify_calibration)

	def verify_calibration(self):
		safe_print("-" * 80)
		progress_msg = lang.getstr("calibration.verify")
		safe_print(progress_msg)
		self.worker.interactive = False
		self.worker.start(self.result_consumer, self.worker.verify_calibration, 
						  progress_msg=progress_msg, pauseable=True)
	
	def select_profile(self, parent=None, check_profile_class=True, msg=None):
		"""
		Selects the currently configured profile or display profile. Falls
		back to user choice via FileDialog if both not set.
		
		"""
		if not parent:
			parent = self
		if not msg:
			msg = lang.getstr("profile.choose")
		profile = get_current_profile(include_display_profile=True)
		if not profile:
			defaultDir, defaultFile = get_verified_path("last_icc_path")
			dlg = wx.FileDialog(parent, msg, 
								defaultDir=defaultDir, defaultFile=defaultFile, 
								wildcard=lang.getstr("filetype.icc") + "|*.icc;*.icm", 
								style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
			dlg.Center(wx.BOTH)
			result = dlg.ShowModal()
			if result == wx.ID_OK:
				path = dlg.GetPath()
				setcfg("last_icc_path", path)
				setcfg("last_cal_or_icc_path", path)
			dlg.Destroy()
			if result != wx.ID_OK:
				return
			try:
				profile = ICCP.ICCProfile(path)
			except (IOError, ICCP.ICCProfileInvalidError), exception:
				InfoDialog(parent, msg=lang.getstr("profile.invalid") + 
								 "\n" + path, 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				return
			if check_profile_class and (profile.profileClass != "mntr" or
										profile.colorSpace != "RGB"):
				InfoDialog(parent, msg=lang.getstr("profile.unsupported", 
												 profile.profileClass, 
												 profile.colorSpace) + 
								 "\n" + path, 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				return
		return profile

	def measurement_report_create_handler(self, event):
		""" Assign and initialize the report creation window """
		if not getattr(self, "reportframe", None):
			self.init_reportframe()
		if self.reportframe.IsShownOnScreen():
			self.reportframe.Raise()
		else:
			self.reportframe.Show(not self.reportframe.IsShownOnScreen())

	def measurement_report_handler(self, event):
		if not check_set_argyll_bin():
			return
			
		sim_ti3 = None
		sim_gray = None
			
		# select measurement data (ti1 or ti3)
		chart = getcfg("measurement_report.chart")
		
		try:
			chart = CGATS.CGATS(chart, True)
		except (IOError, CGATS.CGATSError), exception:
			show_result_dialog(exception, self.reportframe)
			return
		
		fields = getcfg("measurement_report.chart.fields")
		
		# profile(s)
		paths = []
		use_sim = getcfg("measurement_report.use_simulation_profile")
		use_sim_as_output = getcfg("measurement_report.use_simulation_profile_as_output")
		use_devlink = getcfg("measurement_report.use_devlink_profile")
		#if not use_sim or not use_sim_as_output:
		paths.append(getcfg("measurement_report.output_profile"))
		if use_sim:
			if use_sim_as_output and use_devlink:
				paths.append(getcfg("measurement_report.devlink_profile"))
			paths.append(getcfg("measurement_report.simulation_profile"))
		sim_profile = None
		devlink = None
		oprof = None
		for i, path in enumerate(paths):
			try:
				profile = ICCP.ICCProfile(path)
			except (IOError, ICCP.ICCProfileInvalidError), exception:
				InfoDialog(self.reportframe, msg=lang.getstr("profile.invalid") + 
								 "\n" + path, 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				return
			if i == 0:
				oprof = profile
			elif i in (1, 2) and use_sim:
				if use_sim_as_output and profile.colorSpace == "RGB":
					if i == 1 and use_devlink:
						devlink = profile
				else:
					if profile.colorSpace != "RGB":
						devlink = None
					sim_profile = profile
					profile = oprof
		colormanaged = (use_sim and use_sim_as_output and not sim_profile and
						config.get_display_name() == "madVR" and
						getcfg("3dlut.madVR.enable"))
		if debug:
			for n, p in {"profile": profile, "devlink": devlink,
						 "sim_profile": sim_profile, "oprof": oprof}.iteritems():
				if p:
					safe_print(n, p.getDescription())

		if use_sim:
			if sim_profile:
				mprof = sim_profile
			else:
				mprof = profile
		apply_bt1886 = (use_sim and
						getcfg("measurement_report.apply_bt1886_gamma_mapping") and
						mprof.colorSpace == "RGB" and
						isinstance(mprof.tags.get("rXYZ"), ICCP.XYZType) and
						isinstance(mprof.tags.get("gXYZ"), ICCP.XYZType) and
						isinstance(mprof.tags.get("bXYZ"), ICCP.XYZType))
		bt1886 = None
		if apply_bt1886:
			# TRC BT.1886-like
			if "bkpt" in oprof.tags:
				XYZbp = oprof.tags.bkpt.pcs.values()
			else:
				XYZbp = (0, 0, 0)
			gamma = getcfg("measurement_report.bt1886_gamma")
			if getcfg("measurement_report.bt1886_gamma_type") == "b":
				# Convert effective to technical gamma
				gamma = colormath.xicc_tech_gamma(gamma, XYZbp[1])
			rXYZ = mprof.tags.rXYZ.values()
			gXYZ = mprof.tags.gXYZ.values()
			bXYZ = mprof.tags.bXYZ.values()
			mtx = colormath.Matrix3x3([[rXYZ[0], gXYZ[0], bXYZ[0]],
									   [rXYZ[1], gXYZ[1], bXYZ[1]],
									   [rXYZ[2], gXYZ[2], bXYZ[2]]])
			bt1886 = colormath.BT1886(mtx, XYZbp, gamma)

		if sim_profile:
			sim_intent = ("a"
						  if getcfg("measurement_report.whitepoint.simulate")
						  else "r")
			void, sim_ti3, sim_gray = self.worker.chart_lookup(chart, 
													  sim_profile,
													  check_missing_fields=True, 
													  intent=sim_intent,
													  bt1886=bt1886)
			# NOTE: we ignore the ti1 and gray patches here
			# only the ti3 is valuable at this point
			if not sim_ti3:
				return
			intent = ("r"
					  if sim_intent == "r" or
					  getcfg("measurement_report.whitepoint.simulate.relative")
					  else "a")
			bt1886 = None
		else:
			sim_intent = None
			intent = "r"
			if fields in ("LAB", "XYZ"):
				if getcfg("measurement_report.whitepoint.simulate"):
					sim_intent = "a"
					if not getcfg("measurement_report.whitepoint.simulate.relative"):
						intent = "a"
				else:
					chart.fix_device_values_scaling()
					chart.adapt(cat=profile.guess_cat() or "Bradford")
		
		# lookup test patches
		ti1, ti3_ref, gray = self.worker.chart_lookup(sim_ti3 or chart, 
													  profile,
													  bool(sim_ti3) or
													  fields in ("LAB", "XYZ"),
													  fields=None
															 if bool(sim_ti3)
															 else fields,
													  intent=intent,
													  bt1886=bt1886)
		if not ti3_ref:
			return
		if not gray and sim_gray:
			gray = sim_gray
		
		if devlink:
			void, ti1, void = self.worker.chart_lookup(chart, devlink,
													   check_missing_fields=True)
			if not ti1:
				return
		
		# let the user choose a location for the result
		defaultFile = u"Measurement Report %s — %s — %s" % (version,
			re.sub(r"[\\/:*?\"<>|]+", "_",
			self.display_ctrl.GetStringSelection().replace(" " +
														   lang.getstr("display.primary"),
														   "")),
			strftime("%Y-%m-%d %H-%M.html"))
		defaultDir = get_verified_path(None, 
									   os.path.join(getcfg("profile.save_path"), 
									   defaultFile))[0]
		dlg = wx.FileDialog(self.reportframe, lang.getstr("save_as"), 
							defaultDir, defaultFile, 
							wildcard=lang.getstr("filetype.html") + "|*.html;*.htm", 
							style=wx.SAVE | wx.FD_OVERWRITE_PROMPT)
		dlg.Center(wx.BOTH)
		result = dlg.ShowModal()
		if result == wx.ID_OK:
			path = dlg.GetPath()
			if not waccess(path, os.W_OK):
				show_result_dialog(Error(lang.getstr("error.access_denied.write",
													 path)),
								   self.reportframe)
				return
			save_path = os.path.splitext(path)[0] + ".html"
			setcfg("last_filedialog_path", save_path)
		dlg.Destroy()
		if result != wx.ID_OK:
			return
		# check if file(s) already exist
		if os.path.exists(save_path):
				dlg = ConfirmDialog(
					self.reportframe, msg=lang.getstr("dialog.confirm_overwrite", 
										  save_path), 
					ok=lang.getstr("overwrite"), 
					cancel=lang.getstr("cancel"), 
					bitmap=geticon(32, "dialog-warning"))
				result = dlg.ShowModal()
				dlg.Destroy()
				if result != wx.ID_OK:
					return
		
		# setup for measurement
		self.setup_measurement(self.measurement_report, ti1, profile, sim_profile, 
							   intent, sim_intent, devlink, ti3_ref, sim_ti3,
							   save_path, chart, gray, apply_bt1886,
							   colormanaged)

	def measurement_report(self, ti1, profile, sim_profile, intent, sim_intent,
						   devlink, ti3_ref, sim_ti3, save_path, chart, gray,
						   apply_bt1886, colormanaged):
		safe_print("-" * 80)
		progress_msg = lang.getstr("measurement_report")
		safe_print(progress_msg)
		
		# setup temp dir
		temp = self.worker.create_tempdir()
		if isinstance(temp, Exception):
			show_result_dialog(temp, self.reportframe)
			return
		
		# filenames
		name, ext = os.path.splitext(os.path.basename(save_path))
		ti1_path = os.path.join(temp, name + ".ti1")
		profile_path = os.path.join(temp, name + ".icc")
		
		# write ti1 to temp dir
		try:
			ti1_file = open(ti1_path, "w")
		except EnvironmentError, exception:
			InfoDialog(self.reportframe, msg=lang.getstr("error.file.create", 
											 ti1_path), 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-error"))
			self.worker.wrapup(False)
			return
		ti1_file.write(str(ti1))
		ti1_file.close()
		
		# write profile to temp dir
		profile.write(profile_path)
		
		# extract calibration from profile
		cal_path = None
		if "vcgt" in profile.tags:
			try:
				cgats = vcgt_to_cal(profile)
			except (CGATS.CGATSInvalidError, 
					CGATS.CGATSInvalidOperationError, CGATS.CGATSKeyError, 
					CGATS.CGATSTypeError, CGATS.CGATSValueError), exception:
				wx.CallAfter(show_result_dialog,
							 Error(lang.getstr("cal_extraction_failed")),
							 self.reportframe)
				self.Show()
				return
			cal_path = os.path.join(temp, name + ".cal")
			cgats.write(cal_path)
		else:
			# Use linear calibration
			cal_path = get_data_path("linear.cal")
		
		# start readings
		self.worker.dispread_after_dispcal = False
		self.worker.interactive = config.get_display_name() == "Untethered"
		self.worker.start(self.measurement_report_consumer, 
						  self.worker.measure_ti1, 
						  cargs=(os.path.splitext(ti1_path)[0] + ".ti3", 
								 profile, sim_profile, intent, sim_intent,
								 devlink, ti3_ref, sim_ti3, save_path, chart,
								 gray, apply_bt1886),
						  wargs=(ti1_path, cal_path, colormanaged),
						  progress_msg=progress_msg, pauseable=True)
	
	def measurement_report_consumer(self, result, ti3_path, profile, sim_profile,
									intent, sim_intent, devlink, ti3_ref,
									sim_ti3, save_path, chart, gray,
									apply_bt1886):
		
		if not isinstance(result, Exception) and result:
			# get item 0 of the ti3 to strip the CAL part from the measured data
			try:
				ti3_measured = CGATS.CGATS(ti3_path)[0]
			except (IOError, CGATS.CGATSInvalidError, CGATS.CGATSKeyError), exc:
				result = exc
			else:
				safe_print(lang.getstr("success"))
				result = self.measurement_file_check_confirm(ti3_measured)
		
		# cleanup
		self.worker.wrapup(False)
		
		self.Show()
		
		if isinstance(result, Exception) or not result:
			if isinstance(result, Exception):
				wx.CallAfter(show_result_dialog, result, self.reportframe)
			return

		# Account for additional white patches
		white_rgb = {'RGB_R': 100, 'RGB_G': 100, 'RGB_B': 100}
		white_measured = ti3_measured.queryi(white_rgb)
		white_ref = ti3_ref.queryi(white_rgb)
		offset = max(len(white_measured) - len(white_ref), 0)

		# If patches were removed from the measured TI3, we need to remove them
		# from reference and simulation TI3
		if isinstance(result, tuple):
			ref_removed = []
			sim_removed = []
			for item in reversed(result[0]):
				key = item.key - offset
				ref_removed.insert(0, ti3_ref.DATA.pop(key))
				if sim_ti3:
					sim_removed.insert(0, sim_ti3.DATA.pop(key))
			for item in ref_removed:
				safe_print("Removed patch #%i from reference TI3: %s" %
						   (item.key, item))
			for item in sim_removed:
				safe_print("Removed patch #%i from simulation TI3: %s" %
						   (item.key, item))
			# Update offset
			white_ref = ti3_ref.queryi(white_rgb)
			offset = max(len(white_measured) - len(white_ref), 0)
		
		# Determine if we should use planckian locus for assumed target wp
		# Detection will only work for profiles created by dispcalGUI
		planckian = False
		if (profile.tags.get("CIED", "") or 
			profile.tags.get("targ", ""))[0:4] == "CTI3":
			options_dispcal = get_options_from_profile(profile)[0]
			for option in options_dispcal:
				if option.startswith("T"):
					planckian = True
					break
		
		# calculate amount of calibration grayscale tone values
		cal_entrycount = 256
		if "vcgt" in profile.tags and isinstance(profile.tags.vcgt,
												 ICCP.VideoCardGammaType):
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
			# Assume linear with all steps
			cal_rgblevels = [256, 256, 256]
		
		if not chart.filename.lower().endswith(".ti1") or sim_ti3:
			# make the device values match
			for i in ti3_ref.DATA:
				for color in ("RGB_R", "RGB_G", "RGB_B"):
					if sim_ti3 and sim_ti3.DATA[i].get(color) is not None:
						ti3_ref.DATA[i][color] = sim_ti3.DATA[i][color]
					else:
						ti3_ref.DATA[i][color] = ti3_measured.DATA[i + offset][color]
		
		cat = "Bradford"
		
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
		
		wtpt_profile_norm = tuple(n * 100 for n in profile.tags.wtpt.values())
		if "chad" in profile.tags:
			# undo chromatic adaption of profile whitepoint
			WX, WY, WZ = profile.tags.chad.inverted() * wtpt_profile_norm
			wtpt_profile_norm = tuple((n / WY) * 100.0 for n in (WX, WY, WZ))
			# guess chromatic adaption transform (Bradford, CAT02...)
			cat = profile.guess_cat() or cat
		if "lumi" in profile.tags and isinstance(profile.tags.lumi,
												 ICCP.XYZType):
			# calculate unscaled whitepoint
			scale = profile.tags.lumi.Y / 100.0
			wtpt_profile = tuple(n * scale for n in wtpt_profile_norm)
		else:
			wtpt_profile = wtpt_profile_norm
		
		if sim_profile:
			wtpt_sim_profile_norm = tuple(n * 100 for n in sim_profile.tags.wtpt.values())
			if "chad" in sim_profile.tags:
				# undo chromatic adaption of profile whitepoint
				WX, WY, WZ = sim_profile.tags.chad.inverted() * wtpt_sim_profile_norm
				wtpt_sim_profile_norm = tuple((n / WY) * 100.0 for n in (WX, WY, WZ))
		
		wtpt_measured = tuple(float(n) for n in ti3_joined.LUMINANCE_XYZ_CDM2.split())
		# normalize so that Y = 100
		wtpt_measured_norm = tuple((n / wtpt_measured[1]) * 100 for n in wtpt_measured)
		
		if intent != "a" and sim_intent != "a":
			white = ti3_joined.queryi(white_rgb)
			for i in white:
				white[i].update({'XYZ_X': wtpt_measured_norm[0], 
								 'XYZ_Y': wtpt_measured_norm[1], 
								 'XYZ_Z': wtpt_measured_norm[2]})
		
		black = ti3_joined.queryi1({'RGB_R': 0, 'RGB_G': 0, 'RGB_B': 0})
		if black:
			bkpt_measured_norm = black["XYZ_X"], black["XYZ_Y"], black["XYZ_Z"]
			bkpt_measured = tuple(wtpt_measured[1] / 100 * n for n in bkpt_measured_norm)
		else:
			bkpt_measured_norm = None
			bkpt_measured = None
		
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
							X, Y, Z = colormath.adapt(X, Y, Z, 
													  wtpt_measured_norm, 
													  cat=cat)
							#print X, Y, Z
						Lab = XYZ2Lab(X, Y, Z)
						for j, color in enumerate(labels_Lab):
							data.DATA[i][color] = Lab[j]
			if data is ti3_ref and sim_intent == "a" and intent == "a":
				for i in data.DATA:
					# we need to adapt the reference values to D50
					L, a, b = [data.DATA[i][color] for color in labels_Lab]
					X, Y, Z = colormath.Lab2XYZ(L, a, b, scale=100)
					#print X, Y, Z, '->',
					X, Y, Z = colormath.adapt(X, Y, Z,
											  wtpt_profile_norm,
											  cat=cat)
					#print X, Y, Z
					Lab = XYZ2Lab(X, Y, Z)
					for j, color in enumerate(labels_Lab):
						data.DATA[i][color] = Lab[j]
		
		# gather data for report
		
		instrument = self.comport_ctrl.GetStringSelection()
		measurement_mode = self.get_measurement_mode()
		mode = []
		if measurement_mode:
			if "c" in measurement_mode:
				mode += [lang.getstr("measurement_mode.refresh")]
			elif "l" in measurement_mode:
				mode += [lang.getstr("measurement_mode.lcd")]
			if "p" in measurement_mode:
				mode += [lang.getstr("projector")]
			if "V" in measurement_mode:
				mode += [lang.getstr("measurement_mode.adaptive")]
			if "H" in measurement_mode:
				mode += [lang.getstr("measurement_mode.highres")]
		if mode:
			instrument += " (%s)" % "/".join(mode)
		
		ccmx = "None"
		if self.worker.instrument_can_use_ccxx():
			ccmx = getcfg("colorimeter_correction_matrix_file").split(":", 1)
			if len(ccmx) > 1 and ccmx[1]:
				ccmxpath = ccmx[1]
				ccmx = os.path.basename(ccmx[1])
				try:
					cgats = CGATS.CGATS(ccmxpath)
				except (IOError, CGATS.CGATSError), exception:
					safe_print("%s:" % ccmxpath, exception)
				else:
					desc = safe_unicode(cgats.get_descriptor(), "UTF-8")
					# If the description is not the same as the 'sane'
					# filename, add the filename after the description
					# (max 31 chars)
					# See also colorimeter_correction_check_overwite, the
					# way the filename is processed must be the same
					if (re.sub(r"[\\/:*?\"<>|]+", "_",
							   make_argyll_compatible_path(desc)) !=
						os.path.splitext(ccmx)[0]):
						ccmx = "%s &amp;lt;%s&amp;gt;" % (desc, ellipsis(ccmx,
																		 31,
																		 "m"))
			else:
				ccmx = "None"
		
		use_sim = getcfg("measurement_report.use_simulation_profile")
		use_sim_as_output = getcfg("measurement_report.use_simulation_profile_as_output")
		if not sim_profile and use_sim and use_sim_as_output:
			sim_profile = profile
		
		placeholders2data = {"${PLANCKIAN}": 'checked="checked"' if planckian 
											 else "",
							 "${DISPLAY}": self.display_ctrl.GetStringSelection().replace(" " +
																						  lang.getstr("display.primary"),
																						  ""),
							 "${INSTRUMENT}": instrument,
							 "${CORRECTION_MATRIX}": ccmx,
							 "${BLACKPOINT}": "%f %f %f" % (bkpt_measured if
											  bkpt_measured else (-1, ) * 3),
							 "${WHITEPOINT}": "%f %f %f" % wtpt_measured,
							 "${WHITEPOINT_NORMALIZED}": "%f %f %f" % 
														 wtpt_measured_norm,
							 "${PROFILE}": profile.getDescription(),
							 "${PROFILE_WHITEPOINT}": "%f %f %f" % wtpt_profile,
							 "${PROFILE_WHITEPOINT_NORMALIZED}": "%f %f %f" % 
																 wtpt_profile_norm,
							 "${SIMULATION_PROFILE}": sim_profile.getDescription() if sim_profile else '',
							 "${BT_1886_GAMMA}": str(getcfg("measurement_report.bt1886_gamma")
													 if apply_bt1886 else 'null'),
							 "${BT_1886_GAMMA_TYPE}": str(getcfg("measurement_report.bt1886_gamma_type")
														  if apply_bt1886 else ''),
							 "${WHITEPOINT_SIMULATION}": str(sim_intent == "a").lower(),
							 "${WHITEPOINT_SIMULATION_RELATIVE}": str(sim_intent == "a" and
																	  intent == "r").lower(),
							 "${DEVICELINK_PROFILE}": devlink.getDescription() if devlink else '',
							 "${TESTCHART}": os.path.basename(chart.filename),
							 "${ADAPTION}": str(cat),
							 "${DATETIME}": strftime("%Y-%m-%d %H:%M:%S"),
							 "${REF}":  str(ti3_ref).decode(enc, 
															"replace").replace('"', 
																			   "&quot;"),
							 "${MEASURED}": str(ti3_joined).decode(enc, 
																   "replace").replace('"', 
																					  "&quot;"),
							 "${CAL_ENTRYCOUNT}": str(cal_entrycount),
							 "${CAL_RGBLEVELS}": repr(cal_rgblevels),
							 "${GRAYSCALE}": repr(gray) if gray else 'null',
							 "${REPORT_VERSION}": version}
		
		# create report
		try:
			report.create(save_path, placeholders2data, getcfg("report.pack_js"))
		except (IOError, OSError), exception:
			show_result_dialog(exception, self)
		else:
			# show report
			wx.CallAfter(launch_file, save_path)

	def load_cal(self, cal=None, silent=False):
		""" Load a calibration from a .cal file or ICC profile. Defaults
		to currently configured file if cal parameter is not given. """
		if not cal:
			cal = getcfg("calibration.file")
		if cal:
			if check_set_argyll_bin():
				if verbose >= 1:
					safe_print(lang.getstr("calibration.loading"))
					safe_print(cal)
				if self.install_cal(capture_output=True, cal=cal, 
									skip_scripts=True, silent=silent,
									title=lang.getstr("calibration.load_from_cal_or_profile")) is True:
					if (cal.lower().endswith(".icc") or 
						cal.lower().endswith(".icm")):
						try:
							profile = ICCP.ICCProfile(cal)
						except (IOError, ICCP.ICCProfileInvalidError), exception:
							safe_print(exception)
							profile = None
					else:
						profile = cal_to_fake_profile(cal)
					self.lut_viewer_load_lut(profile=profile)
					if verbose >= 1 and silent:
						safe_print(lang.getstr("success"))
					return True
				if verbose >= 1:
					safe_print(lang.getstr("failure"))
		return False

	def reset_cal(self, event=None):
		""" Reset video card gamma table to linear """
		if check_set_argyll_bin():
			if verbose >= 1:
				safe_print(lang.getstr("calibration.resetting"))
			if self.install_cal(capture_output=True, cal=False, 
								skip_scripts=True, silent=not (getcfg("dry_run") and event),
								title=lang.getstr("calibration.reset")) is True:
				profile = ICCP.ICCProfile()
				profile._data = "\0" * 128
				profile._tags.desc = ICCP.TextDescriptionType("", "desc")
				profile._tags.vcgt = ICCP.VideoCardGammaTableType("", "vcgt")
				profile._tags.vcgt.update({
					"channels": 3,
					"entryCount": 256,
					"entrySize": 1,
					"data": [range(0, 256), range(0, 256), range(0, 256)]
				})
				profile.size = len(profile.data)
				profile.is_loaded = True
				self.lut_viewer_load_lut(profile=profile)
				if verbose >= 1:
					safe_print(lang.getstr("success"))
				return True
			if verbose >= 1 and not getcfg("dry_run"):
				safe_print(lang.getstr("failure"))
		return False

	def load_display_profile_cal(self, event=None):
		""" Load calibration (vcgt) from current display profile """
		profile = get_display_profile()
		if check_set_argyll_bin():
			if verbose >= 1:
				safe_print(
					lang.getstr("calibration.loading_from_display_profile"))
				if profile and profile.fileName:
					safe_print(profile.fileName)
			if self.install_cal(capture_output=True, cal=True, 
								skip_scripts=True, silent=not (getcfg("dry_run") and event),
								title=lang.getstr("calibration.load_from_display_profile")) is True:
				self.lut_viewer_load_lut(profile=profile)
				if verbose >= 1:
					safe_print(lang.getstr("success"))
				return True
			if verbose >= 1 and not getcfg("dry_run"):
				safe_print(lang.getstr("failure"))
		return False

	def report_calibrated_handler(self, event):
		""" Report on calibrated display and exit """
		self.setup_measurement(self.report)

	def report_uncalibrated_handler(self, event):
		""" Report on uncalibrated display and exit """
		self.setup_measurement(self.report, False)

	def report(self, report_calibrated=True):
		if check_set_argyll_bin():
			safe_print("-" * 80)
			if report_calibrated:
				progress_msg = lang.getstr("report.calibrated")
			else:
				progress_msg = lang.getstr("report.uncalibrated")
			safe_print(progress_msg)
			self.worker.interactive = False
			self.worker.start(self.result_consumer, self.worker.report, 
							  wkwargs={"report_calibrated": report_calibrated},
							  progress_msg=progress_msg, pauseable=True)
	
	def result_consumer(self, result):
		""" Generic result consumer. Shows the info window on success
		if enabled in the configuration or an info/warn/error dialog if
		result was an exception. """
		if isinstance(result, Exception) and result:
			wx.CallAfter(show_result_dialog, result, self)
		elif getcfg("log.autoshow"):
			wx.CallAfter(self.infoframe_toggle_handler, show=True)
		self.worker.wrapup(False)
		self.Show()

	def calibrate_btn_handler(self, event):
		if sys.platform == "darwin" or debug: self.focus_handler(event)
		if not getcfg("profile.update") and (not getcfg("calibration.update") or 
											 is_profile()):
			update_profile = getcfg("calibration.update") and is_profile()
			if update_profile:
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
			if update_profile and result == wx.ID_OK:
				setcfg("profile.update", 1)
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
		""" Just calibrate, optionally creating a fast matrix shaper profile """
		safe_print("-" * 80)
		safe_print(lang.getstr("button.calibrate"))
		if getcfg("calibration.interactive_display_adjustment") and \
		   not getcfg("calibration.update"):
			# Interactive adjustment, do not show progress dialog
			self.worker.interactive = True
		else:
			# No interactive adjustment, show progress dialog
			self.worker.interactive = False
		self.worker.start_calibration(self.just_calibrate_finish, remove=True,
									  progress_msg=lang.getstr("calibration"))
	
	def just_calibrate_finish(self, result):
		start_timers = True
		if not isinstance(result, Exception) and result:
			wx.CallAfter(self.update_calibration_file_ctrl)
			if getcfg("log.autoshow"):
				wx.CallAfter(self.infoframe_toggle_handler, show=True)
			if getcfg("profile.update") or \
			   self.worker.dispcal_create_fast_matrix_shaper:
				start_timers = False
				wx.CallAfter(self.profile_finish, True, 
							 success_msg=lang.getstr("calibration.complete"))
			else:
				wx.CallAfter(self.load_cal, silent=True)
				wx.CallAfter(InfoDialog, self, 
							 msg=lang.getstr("calibration.complete"), 
							 ok=lang.getstr("ok"), 
							 bitmap=geticon(32, "dialog-information"))
		else:
			if isinstance(result, Exception):
				wx.CallAfter(show_result_dialog, result, self)
			if not getcfg("dry_run"):
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
		if (config.get_display_name() in ("Web", "Untethered", "madVR") or
			getcfg("dry_run")):
			self.call_pending_function()
		elif sys.platform in ("darwin", "win32") or isexe:
			self.measureframe.Show()
		else:
			wx.CallAfter(self.measureframe_subprocess)
	
	def measureframe_subprocess(self):
		args = u'"%s" -c "%s"' % (exe, "import sys;"
									   "sys.path.insert(0, %r);"
									   "import wxMeasureFrame;"
									   "wxMeasureFrame.main();"
									   "sys.exit(wxMeasureFrame.MeasureFrame.exitcode)" %
									   pydir)
		if wx.Display.GetCount() == 1 and len(self.worker.display_rects) > 1:
			# Separate X screens, TwinView or similar
			display = wx.Display(0)
			geometry = display.Geometry
			union = wx.Rect()
			xy = []
			for rect in self.worker.display_rects:
				if rect[:2] in xy or rect[2:] == geometry[2:]:
					# Overlapping x y coordinates or screen filling whole
					# reported geometry, so assume separate X screens
					union = None
					break
				xy.append(rect[:2])
				union = union.Union(rect)
			if union == geometry:
				# Assume TwinView or similar where Argyll enumerates 1+n 
				# displays but wx only 'sees' one that is the union of them
				pass
			else:
				# Assume separate X screens
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
			p = sp.Popen(args.encode(fs_enc), 
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
			self.restore_measurement_mode()
			self.restore_testchart()
			if stderr and stderr.strip():
				InfoDialog(self, msg=safe_unicode(stderr.strip()), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"), print_=True)
		else:
			self.call_pending_function()
	
	def get_set_display(self, update_ccmx_items=False):
		""" Get the currently configured display number, and set the
		display device selection """
		if debug:
			safe_print("[D] get_set_display")
		if self.worker.displays:
			self.display_ctrl.SetSelection(
				min(max(0, len(self.worker.displays) - 1), 
					max(0, getcfg("display.number") - 1)))
		self.display_ctrl_handler(
			CustomEvent(wx.EVT_CHOICE.evtType[0], 
						self.display_ctrl), load_lut=False,
						update_ccmx_items=update_ccmx_items)

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
		""" Setup calibration and characterization measurements """
		if sys.platform == "darwin" or debug: self.focus_handler(event)
		self.update_profile_name_timer.Stop()
		if check_set_argyll_bin() and self.check_overwrite(".cal") and \
		   self.check_overwrite(".ti3") and self.check_overwrite(profile_ext):
			self.setup_measurement(self.calibrate_and_profile)
		else:
			self.update_profile_name_timer.Start(1000)

	def calibrate_and_profile(self):
		""" Start calibration measurements """
		safe_print("-" * 80)
		safe_print(lang.getstr("button.calibrate_and_profile").replace("&&", 
																	   "&"))
		self.worker.dispcal_create_fast_matrix_shaper = False
		self.worker.dispread_after_dispcal = True
		if getcfg("calibration.interactive_display_adjustment") and \
		   not getcfg("calibration.update"):
			# Interactive adjustment, do not show progress dialog
			self.worker.interactive = True
		else:
			# No interactive adjustment, show progress dialog
			self.worker.interactive = False
		self.worker.start_calibration(self.calibrate_finish,
									  progress_msg=lang.getstr("calibration"), 
									  continue_next=True)
	
	def calibrate_finish(self, result):
		""" Start characterization measurements """
		self.worker.interactive = False
		if not isinstance(result, Exception) and result:
			wx.CallAfter(self.update_calibration_file_ctrl)
			self.worker.start_measurement(self.calibrate_and_profile_finish,
										  apply_calibration=True, 
										  progress_msg=lang.getstr("measuring.characterization"), 
										  resume=True, continue_next=True)
		else:
			if isinstance(result, Exception):
				wx.CallAfter(show_result_dialog, result, self)
			if not getcfg("dry_run"):
				wx.CallAfter(InfoDialog, self, 
							 msg=lang.getstr("calibration.incomplete"), 
							 ok=lang.getstr("ok"), 
							 bitmap=geticon(32, "dialog-error"))
			self.Show()
	
	def calibrate_and_profile_finish(self, result):
		""" Build profile from characterization measurements """
		start_timers = True
		if not isinstance(result, Exception) and result:
			result = self.check_copy_ti3()
		if not isinstance(result, Exception) and result:
			start_timers = False
			wx.CallAfter(self.start_profile_worker, 
						 lang.getstr("calibration_profiling.complete"), 
						 resume=True)
		else:
			if isinstance(result, Exception):
				wx.CallAfter(show_result_dialog, result, self)
			if not getcfg("dry_run"):
				wx.CallAfter(InfoDialog, self, 
							 msg=lang.getstr("profiling.incomplete"), 
							 ok=lang.getstr("ok"), 
							 bitmap=geticon(32, "dialog-error"))
		self.Show(start_timers=start_timers)
	
	def check_copy_ti3(self):
		result = self.measurement_file_check_confirm(parent=getattr(self.worker, "progress_wnd", self))
		if isinstance(result, tuple):
			result = self.worker.wrapup(copy=True, remove=False,
										ext_filter=[".ti3"])
		if isinstance(result, Exception) or not result:
			self.worker.stop_progress()
		return result

	def start_profile_worker(self, success_msg, resume=False):
		self.worker.interactive = False
		self.worker.start(self.profile_finish, self.worker.create_profile, 
						  ckwargs={"success_msg": success_msg, 
								   "failure_msg": lang.getstr(
									   "profiling.incomplete")}, 
						  wkwargs={"tags": True},
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
	
	def current_cal_choice(self):
		""" Prompt user to either keep or clear the current calibration,
		with option to embed or not embed
		
		Return None if the current calibration should be embedded
		Return False if no calibration should be embedded
		Return filename if a .cal file should be used
		Return wx.ID_CANCEL if whole operation should be cancelled
		
		"""
		if config.get_display_name() == "Untethered":
			return False
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
					return wx.ID_CANCEL
				else:
					# get dispcal options if present
					self.worker.options_dispcal = [
						"-" + arg for arg in 
						get_options_from_profile(profile)[0]]
			if os.path.isfile(filename + ".cal"):
				cal = filename + ".cal"
			else:
				cal = None
		if (self.worker.argyll_version < [1, 1, 0] or
			not self.worker.has_lut_access()):
			# If Argyll < 1.1, we cannot save the current VideoLUT to use it.
			# For web, there is no point in using the current VideoLUT as it
			# may not be from the display we render on (and we cannot save it
			# to begin with as there is no VideoLUT access).
			# So an existing .cal file or no calibration are the only options.
			can_use_current_cal = False
		else:
			can_use_current_cal = True
		if cal:
			msgstr = "dialog.cal_info"
			icon = "information"
		elif can_use_current_cal:
			msgstr = "dialog.current_cal_warning"
			icon = "warning"
		else:
			msgstr = "dialog.linear_cal_info"
			icon = "information"
		dlg = ConfirmDialog(self, 
							msg=lang.getstr(msgstr, os.path.basename(cal)
													if cal else None), 
							ok=lang.getstr("continue"), 
							cancel=lang.getstr("cancel"), 
							bitmap=geticon(32, "dialog-%s" % icon))
		border = 12
		if can_use_current_cal or cal:
			dlg.reset_cal_ctrl = wx.CheckBox(dlg, -1, 
									   lang.getstr("calibration.use_linear_instead"))
			dlg.sizer3.Add(dlg.reset_cal_ctrl, flag=wx.TOP | wx.ALIGN_LEFT, 
						   border=border)
			border = 4
		dlg.embed_cal_ctrl = wx.CheckBox(dlg, -1, 
								   lang.getstr("calibration.embed"))
		def embed_cal_ctrl_handler(event):
			embed_cal = dlg.embed_cal_ctrl.GetValue()
			dlg.reset_cal_ctrl.Enable(embed_cal)
			if not embed_cal:
				dlg.reset_cal_ctrl.SetValue(True)
		if can_use_current_cal or cal:
			dlg.embed_cal_ctrl.Bind(wx.EVT_CHECKBOX, embed_cal_ctrl_handler)
		dlg.embed_cal_ctrl.SetValue(bool(can_use_current_cal or cal))
		dlg.sizer3.Add(dlg.embed_cal_ctrl, flag=wx.TOP | wx.ALIGN_LEFT, 
					   border=border)
		dlg.sizer0.SetSizeHints(dlg)
		dlg.sizer0.Layout()
		result = dlg.ShowModal()
		if can_use_current_cal or cal:
			reset_cal = dlg.reset_cal_ctrl.GetValue()
		embed_cal = dlg.embed_cal_ctrl.GetValue()
		dlg.Destroy()
		if result == wx.ID_CANCEL:
			self.update_profile_name_timer.Start(1000)
			return wx.ID_CANCEL
		if not embed_cal:
			if can_use_current_cal and reset_cal:
				self.reset_cal()
			return False
		elif not (can_use_current_cal or cal) or reset_cal:
			return get_data_path("linear.cal")
		elif cal:
			return cal
	
	def restore_measurement_mode(self):
		if getcfg("measurement_mode.backup", False):
			setcfg("measurement_mode", getcfg("measurement_mode.backup"))
			setcfg("measurement_mode.backup", None)
			self.update_measurement_mode()

	def restore_testchart(self):
		if getcfg("testchart.file.backup", False):
			self.set_testchart(getcfg("testchart.file.backup"))
			setcfg("testchart.file.backup", None)
	
	def measure_handler(self, event=None):
		if is_ccxx_testchart():
			# Allow different location to store measurements
			path = None
			defaultPath = os.path.join(*get_verified_path("measurement.save_path"))
			dlg = wx.DirDialog(self, lang.getstr("measurement.set_save_path"), 
							   defaultPath=defaultPath)
			dlg.Center(wx.BOTH)
			if dlg.ShowModal() == wx.ID_OK:
				path = dlg.GetPath()
			dlg.Destroy()
			if path:
				if not waccess(path, os.W_OK):
					show_result_dialog(Error(lang.getstr("error.access_denied.write",
														 path)), self)
					return
				setcfg("measurement.save_path", path)
			else:
				self.restore_measurement_mode()
				self.restore_testchart()
				return
		self.update_profile_name_timer.Stop()
		if check_set_argyll_bin() and self.check_overwrite(".ti3"):
			if is_ccxx_testchart():
				# Reset calibration before measuring CCXX testchart
				self.reset_cal()
				apply_calibration = False
			else:
				apply_calibration = self.current_cal_choice()
			if apply_calibration != wx.ID_CANCEL:
				self.setup_measurement(self.just_measure, apply_calibration)
		else:
			self.restore_measurement_mode()
			self.restore_testchart()
			self.update_profile_name_timer.Start(1000)

	def profile_btn_handler(self, event):
		""" Setup characterization measurements """
		if sys.platform == "darwin" or debug: self.focus_handler(event)
		self.update_profile_name_timer.Stop()
		if check_set_argyll_bin() and self.check_overwrite(".ti3") and \
		   self.check_overwrite(profile_ext):
			apply_calibration = self.current_cal_choice()
			if apply_calibration != wx.ID_CANCEL:
				self.setup_measurement(self.just_profile, apply_calibration)
		else:
			self.update_profile_name_timer.Start(1000)

	def just_measure(self, apply_calibration):
		safe_print("-" * 80)
		safe_print(lang.getstr("measure"))
		self.worker.dispread_after_dispcal = False
		self.worker.interactive = config.get_display_name() == "Untethered"
		setcfg("calibration.file.previous", None)
		self.worker.start_measurement(self.just_measure_finish, apply_calibration,
									  progress_msg=lang.getstr("measuring.characterization"), 
									  continue_next=False)
	
	def just_measure_finish(self, result):
		if not isinstance(result, Exception) and result:
			result = self.check_copy_ti3()
		self.worker.wrapup(copy=False, remove=True)
		if isinstance(result, Exception) or not result:
			if isinstance(result, Exception):
				wx.CallAfter(show_result_dialog, result, self)
		elif is_ccxx_testchart():
			try:
				cgats = CGATS.CGATS(os.path.join(getcfg("measurement.save_path"),
												 getcfg("measurement.name.expanded"),
												 getcfg("measurement.name.expanded")) + ".ti3")
			except Exception, exception:
				wx.CallAfter(show_result_dialog, exception, self)
			else:
				if cgats.queryv1("INSTRUMENT_TYPE_SPECTRAL") == "YES":
					setcfg("last_reference_ti3_path", cgats.filename)
				else:
					setcfg("last_colorimeter_ti3_path", cgats.filename)
				wx.CallAfter(self.create_colorimeter_correction_handler)
		else:
			wx.CallAfter(self.just_measure_show_result, 
						 os.path.join(getcfg("profile.save_path"), 
									  getcfg("profile.name.expanded"), 
									  getcfg("profile.name.expanded") + 
									  ".ti3"))
		self.Show(start_timers=True)
		if is_ccxx_testchart():
			# Restore calibration after measuring CCXX testcahrt
			self.load_cal(silent=True) or self.load_display_profile_cal()
		self.restore_measurement_mode()
		self.restore_testchart()
	
	def just_measure_show_result(self, path):
		dlg = ConfirmDialog(self, msg=lang.getstr("measurements.complete"), 
						    ok=lang.getstr("ok"), 
						    cancel=lang.getstr("cancel"), 
						    bitmap=geticon(32, "dialog-question"))
		if dlg.ShowModal() == wx.ID_OK:
			launch_file(os.path.dirname(path))
		dlg.Destroy()

	def just_profile(self, apply_calibration):
		""" Start characterization measurements """
		safe_print("-" * 80)
		safe_print(lang.getstr("button.profile"))
		self.worker.dispread_after_dispcal = False
		self.worker.interactive = config.get_display_name() == "Untethered"
		setcfg("calibration.file.previous", None)
		self.worker.start_measurement(self.just_profile_finish, apply_calibration,
									  progress_msg=lang.getstr("measuring.characterization"), 
									  continue_next=config.get_display_name() != "Untethered")
	
	def just_profile_finish(self, result):
		""" Build profile from characterization measurements """
		start_timers = True
		if not isinstance(result, Exception) and result:
			result = self.check_copy_ti3()
		if not isinstance(result, Exception) and result:
			start_timers = False
			wx.CallAfter(self.start_profile_worker, 
						 lang.getstr("profiling.complete"), resume=True)
		else:
			if isinstance(result, Exception):
				wx.CallAfter(show_result_dialog, result, self)
			if not getcfg("dry_run"):
				wx.CallAfter(InfoDialog, self, 
							 msg=lang.getstr("profiling.incomplete"), 
							 ok=lang.getstr("ok"), 
							 bitmap=geticon(32, "dialog-error"))
		self.Show(start_timers=start_timers)

	def profile_finish(self, result, profile_path=None, success_msg="", 
					   failure_msg="", preview=True, skip_scripts=False,
					   allow_show_log=True):
		if not isinstance(result, Exception) and result:
			if getcfg("log.autoshow") and allow_show_log:
				self.infoframe_toggle_handler(show=True)
			if profile_path:
				profile_save_path = os.path.splitext(profile_path)[0]
			else:
				profile_save_path = os.path.join(
										getcfg("profile.save_path"), 
										getcfg("profile.name.expanded"), 
										getcfg("profile.name.expanded"))
				profile_path = profile_save_path + profile_ext
			if not success_msg:
				success_msg = lang.getstr("dialog.install_profile", 
										  (os.path.basename(profile_path), 
										   self.display_ctrl.GetStringSelection()))
			self.cal = profile_path
			profile = None
			filename, ext = os.path.splitext(profile_path)
			extra = []
			has_cal = False
			try:
				profile = ICCP.ICCProfile(profile_path)
			except (IOError, ICCP.ICCProfileInvalidError), exception:
				InfoDialog(self, msg=lang.getstr("profile.invalid") + 
									 "\n" + profile_path, 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				self.start_timers(True)
				setcfg("calibration.file.previous", None)
				return
			else:
				has_cal = "vcgt" in profile.tags
				if profile.profileClass != "mntr" or \
				   profile.colorSpace != "RGB":
					InfoDialog(self, msg=lang.getstr("profiling.complete"), 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-information"))
					self.start_timers(True)
					setcfg("calibration.file.previous", None)
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
				if "meta" in profile.tags:
					for key in ("avg", "max", "rms"):
						try:
							dE = float(profile.tags.meta.getvalue("ACCURACY_dE76_%s" % key))
						except (TypeError, ValueError):
							pass
						else:
							lstr = lang.getstr("profile.self_check") + ":"
							if not lstr in extra:
								extra.append(lstr)
							extra.append(u" %s %.2f" %
										 (lang.getstr("profile.self_check.%s" %
													  key), dE))
					if extra:
						extra.append("")
						extra.append("")
					for key, name in (("srgb", "sRGB"),
									  ("adobe-rgb", "Adobe RGB")):
						try:
							gamut_coverage = float(profile.tags.meta.getvalue("GAMUT_coverage(%s)" % key))
						except (TypeError, ValueError):
							gamut_coverage = None
						if gamut_coverage:
							if not lang.getstr("gamut.coverage") + ":" in extra:
								if extra:
									extra.append("")
								extra.append(lang.getstr("gamut.coverage") + ":")
							extra.append(" %.1f%% %s" % (gamut_coverage * 100,
														 name))
					try:
						gamut_volume = float(profile.tags.meta.getvalue("GAMUT_volume"))
					except (TypeError, ValueError):
						gamut_volume = None
					if gamut_volume:
						gamut_volumes = {"srgb": ICCP.GAMUT_VOLUME_SRGB,
										 "adobe-rgb": ICCP.GAMUT_VOLUME_ADOBERGB}
						for key, name in (("srgb", "sRGB"),
										  ("adobe-rgb", "Adobe RGB")):
							if not lang.getstr("gamut.volume") + ":" in extra:
								if extra:
									extra.append("")
								extra.append(lang.getstr("gamut.volume") + ":")
							extra.append(" %.1f%% %s" %
										 (gamut_volume *
										  ICCP.GAMUT_VOLUME_SRGB /
										  gamut_volumes[key] * 100,
										  name))
			if extra:
				extra = ",".join(extra).replace(":,", ":").replace(",,", "\n")
				success_msg = "\n\n".join([success_msg, extra])
			# Always load calibration curves
			self.load_cal(cal=profile_path, silent=True)
			# Check profile metadata
			share_profile = None
			if not self.profile_share_get_meta_error(profile):
				share_profile = lang.getstr("profile.share")
			dlg = ConfirmDialog(self, msg=success_msg, 
								title=lang.getstr("profile.install"),
								ok=lang.getstr("profile.install"), 
								cancel=lang.getstr("profile.do_not_install"), 
								bitmap=geticon(32, "dialog-information"),
								alt=share_profile,
								style=wx.CAPTION | wx.CLOSE_BOX | 
									  wx.FRAME_FLOAT_ON_PARENT)
			if share_profile:
				# Show share profile button
				dlg.Unbind(wx.EVT_BUTTON, dlg.alt)
				dlg.Bind(wx.EVT_BUTTON, self.profile_share_handler,
						 id=dlg.alt.GetId())
			if preview and has_cal:
				# Show calibration preview checkbox
				self.preview = wx.CheckBox(dlg, -1, 
										   lang.getstr("calibration.preview"))
				self.preview.SetValue(True)
				dlg.Bind(wx.EVT_CHECKBOX, self.preview_handler, 
						 id=self.preview.GetId())
				dlg.sizer3.Add(self.preview, flag=wx.TOP | wx.ALIGN_LEFT, 
							   border=12)
				if LUTFrame and not ProfileInfoFrame:
					# Disabled, use profile information window instead
					self.show_lut = wx.CheckBox(dlg, -1, 
												lang.getstr(
													"calibration.show_lut"))
					dlg.Bind(wx.EVT_CHECKBOX, self.show_lut_handler, 
							 id=self.show_lut.GetId())
					dlg.sizer3.Add(self.show_lut, flag=wx.TOP | wx.ALIGN_LEFT, 
								   border=4)
					self.show_lut.SetValue(bool(getcfg("lut_viewer.show")))
					if not getattr(self, "lut_viewer", None):
						self.init_lut_viewer(profile=profile, 
											 show=getcfg("lut_viewer.show"))
				if ext not in (".icc", ".icm") or \
				   getcfg("calibration.file") != profile_path:
					self.preview_handler(preview=True)
			else:
				dlg.sizer3.Add((0, 8))
			self.show_profile_info = wx.CheckBox(dlg, -1,
												 lang.getstr("profile.info.show"))
			dlg.Bind(wx.EVT_CHECKBOX, self.profile_info_handler, 
					 id=self.show_profile_info.GetId())
			dlg.sizer3.Add(self.show_profile_info, flag=wx.TOP |
														wx.ALIGN_LEFT, 
						   border=4)
			if profile.ID == "\0" * 16:
				id = profile.calculateID(False)
			else:
				id = profile.ID
			if id in self.profile_info:
				self.show_profile_info.SetValue(
					self.profile_info[id].IsShownOnScreen())
			if sys.platform != "darwin" or test:
				self.profile_load_on_login = wx.CheckBox(dlg, -1, 
					lang.getstr("profile.load_on_login"))
				self.profile_load_on_login.SetValue(
					bool(getcfg("profile.load_on_login") or
						 (sys.platform == "win32" and
						  sys.getwindowsversion() >= (6, 1) and
						  util_win.calibration_management_isenabled())))
				dlg.Bind(wx.EVT_CHECKBOX, self.profile_load_on_login_handler, 
						 id=self.profile_load_on_login.GetId())
				dlg.sizer3.Add(self.profile_load_on_login, 
							   flag=wx.TOP | wx.ALIGN_LEFT, border=12)
				dlg.sizer3.Add((1, 4))
				if sys.platform == "win32" and sys.getwindowsversion() >= (6, 1):
					self.profile_load_by_os = wx.CheckBox(dlg, -1, 
						lang.getstr("profile.load_on_login.handled_by_os"))
					self.profile_load_by_os.SetValue(
						bool(util_win.calibration_management_isenabled()))
					dlg.Bind(wx.EVT_CHECKBOX, self.profile_load_by_os_handler, 
							 id=self.profile_load_by_os.GetId())
					dlg.sizer3.Add(self.profile_load_by_os, 
								   flag=wx.LEFT | wx.ALIGN_LEFT, border=16)
					dlg.sizer3.Add((1, 4))
					self.profile_load_on_login_handler()
			if ((sys.platform == "darwin" or (sys.platform != "win32" and 
											  self.worker.argyll_version >= 
											  [1, 1, 0])) and 
				(os.geteuid() == 0 or which("sudo"))) or \
				(sys.platform == "win32" and 
				 sys.getwindowsversion() >= (6, ) and 
				 self.worker.argyll_version > 
				 [1, 1, 1] and is_superuser()) or test:
				# Linux, OSX or Vista and later
				# NOTE: System install scope is currently not implemented
				# correctly in dispwin 1.1.0, but a patch is trivial and
				# should be in the next version
				# 2010-06-18: Do not offer system install in dispcalGUI when
				# installing via GCM or oyranos FIXME: oyranos-monitor can't 
				# be run via sudo
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
			self.Disable()
			dlg.profile = profile
			dlg.profile_path = profile_path
			dlg.skip_scripts = skip_scripts
			dlg.preview = preview
			dlg.OnCloseIntercept = self.profile_finish_close_handler
			self.modaldlg = dlg
			if sys.platform == "darwin":
				# FRAME_FLOAT_ON_PARENT does not work on Mac,
				# make sure we stay under our dialog
				self.Bind(wx.EVT_ACTIVATE, self.modaldlg_raise_handler)
			wx.CallAfter(dlg.Show)
		else:
			if isinstance(result, Exception):
				show_result_dialog(result, self)
				if getcfg("dry_run"):
					return
			InfoDialog(self, msg=failure_msg, 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-error"))
			if sys.platform == "darwin":
				# For some reason, the call to enable_menus() in Show()
				# sometimes isn't enough under Mac OS X (e.g. after calibrate &
				# profile)
				self.enable_menus()
			self.start_timers(True)
			setcfg("calibration.file.previous", None)
	
	def profile_finish_close_handler(self, event):
		if event.GetEventObject() == self.modaldlg:
			result = wx.ID_CANCEL
		else:
			result = event.GetId()
		if result == wx.ID_OK:
			if config.get_display_name() in ("Web", "Untethered", "madVR"):
				show_result_dialog(Info(lang.getstr("profile.install.virtual.unsupported")),
								   parent=self.modaldlg)
			else:
				safe_print("-" * 80)
				safe_print(lang.getstr("profile.install"))
				result = self.worker.install_profile(profile_path=self.modaldlg.profile_path, 
													 skip_scripts=self.modaldlg.skip_scripts)
				if isinstance(result, Exception):
					show_result_dialog(result, parent=self.modaldlg)
		elif self.modaldlg.preview:
			if getcfg("calibration.file"):
				# Load LUT curves from last used .cal file
				self.load_cal(silent=True)
			else:
				# Load LUT curves from current display profile (if any, 
				# and if it contains curves)
				self.load_display_profile_cal(None)
		self.Enable()
		if sys.platform == "darwin":
			# FRAME_FLOAT_ON_PARENT does not work on Mac,
			# unbind automatic lowering
			self.Unbind(wx.EVT_ACTIVATE, handler=self.modaldlg_raise_handler)
			self.Raise()
		self.modaldlg.Destroy()
		# The C part of modaldlg will not be gone instantly, so we must
		# dereference it before we can delete the python attribute
		self.modaldlg = None
		del self.modaldlg
		if sys.platform == "darwin":
			# For some reason, the call to enable_menus() in Show()
			# sometimes isn't enough under Mac OS X (e.g. after calibrate &
			# profile)
			self.enable_menus()
		self.start_timers(True)
		setcfg("calibration.file.previous", None)
	
	def profile_info_close_handler(self, event):
		if getattr(self, "show_profile_info", None):
			# If the profile install dialog is shown, just hide info window
			self.profile_info[event.GetEventObject().profileID].Hide()
			self.show_profile_info.SetValue(False)
		else:
			# Remove the frame from the hash table
			self.profile_info.pop(event.GetEventObject().profileID)
			# Closes the window
			event.Skip()
	
	def profile_info_handler(self, event):
		if event.GetEventObject() == getattr(self, "show_profile_info", None):
			# Use the profile that was requested to be installed
			profile = self.modaldlg.profile
		else:
			profile = self.select_profile(check_profile_class=False)
		if not profile:
			return
		if profile.ID == "\0" * 16:
			id = profile.calculateID(False)
		else:
			id = profile.ID
		show = (not getattr(self, "show_profile_info", None) or
				self.show_profile_info.GetValue())
		if show:
			if not id in self.profile_info:
				# Create profile info window and store in hash table
				self.profile_info[id] = ProfileInfoFrame(None, -1)
				self.profile_info[id].Unbind(wx.EVT_CLOSE)
				self.profile_info[id].Bind(wx.EVT_CLOSE,
										   self.profile_info_close_handler)
			if (not self.profile_info[id].profile or
				self.profile_info[id].profile.calculateID(False) != id):
				# Load profile if info window has no profile or ID is different
				self.profile_info[id].profileID = id
				self.profile_info[id].LoadProfile(profile)
		if self.profile_info.get(id):
			self.profile_info[id].Show(show)
			if show:
				self.profile_info[id].Raise()
	
	def modaldlg_raise_handler(self, event):
		""" Prevent modal dialog from being lowered (keep on top) """
		self.modaldlg.Raise()
		
	def init_lut_viewer(self, event=None, profile=None, show=None):
		if debug:
			safe_print("[D] init_lut_viewer", 
					   profile.getDescription() if profile else None, 
					   "show:", show)
		if LUTFrame:
			lut_viewer = getattr(self, "lut_viewer", None)
			if not lut_viewer:
				self.lut_viewer = LUTFrame(None, -1)
				self.lut_viewer.client.worker = self.worker
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
							msg = lang.getstr("profile.invalid") + "\n" + path
							if event or not lut_viewer:
								show_result_dialog(Error(msg), self)
							else:
								safe_print(msg)
							profile = None
					else:
						profile = cal_to_fake_profile(path)
				else:
					profile = get_display_profile() or False
			if show is None:
				show = not self.lut_viewer.IsShownOnScreen()
			if debug:
				safe_print("[D] init_lut_viewer (2)", 
						   profile.getDescription() if profile else None, 
						   "show:", show)
			self.show_lut_handler(profile=profile, show=show)
	
	def lut_viewer_load_lut(self, event=None, profile=None, force_draw=False):
		if debug:
			safe_print("[D] lut_viewer_load_lut", 
					   profile.getDescription() if profile else None, 
					   "force_draw:", force_draw)
		if LUTFrame:
			self.current_cal = profile
		if getattr(self, "lut_viewer", None) and \
		   (self.lut_viewer.IsShownOnScreen() or force_draw):
			self.lut_viewer.load_lut(profile)
	
	def show_lut_handler(self, event=None, profile=None, show=None):
		if debug:
			safe_print("[D] show_lut_handler", 
					   profile.getDescription() if profile else None, 
					   "show:", show)
		if show is None:
			show = bool((hasattr(self, "show_lut") and self.show_lut and 
						 self.show_lut.GetValue()) or 
						(not hasattr(self, "show_lut") or 
						 not self.show_lut))
		setcfg("lut_viewer.show", int(show))
		if not profile and hasattr(self, "current_cal"):
			profile = self.current_cal
		if show:
			self.lut_viewer_load_lut(event, profile, force_draw=True)
		if getattr(self, "lut_viewer", None):
			self.menuitem_show_lut.Check(show)
			self.lut_viewer.Show(show)
			if show:
				self.lut_viewer.Raise()
	
	def lut_viewer_close_handler(self, event=None):
		setcfg("lut_viewer.show", 0)
		self.lut_viewer.Hide()
		self.menuitem_show_lut.Check(False)
		if hasattr(self, "show_lut") and self.show_lut:
			self.show_lut.SetValue(self.lut_viewer.IsShownOnScreen())

	def show_advanced_calibration_options_handler(self, event=None):
		""" Show or hide advanced calibration settings """
		show_advanced_calibration_options = bool(getcfg("show_advanced_calibration_options"))
		if event:
			show_advanced_calibration_options = not show_advanced_calibration_options
			setcfg("show_advanced_calibration_options", 
				   int(show_advanced_calibration_options))
		self.calpanel.Freeze()
		self.menuitem_show_advanced_calibration_options.Check(show_advanced_calibration_options)
		for ctrl in (#self.black_luminance_label,
					 #self.black_luminance_ctrl,
					 #self.black_luminance_textctrl,
					 #self.black_luminance_textctrl_label,
					 #self.blacklevel_drift_compensation,
					 self.trc_type_ctrl,
					 self.ambient_viewcond_adjust_cb,
					 self.ambient_viewcond_adjust_textctrl,
					 self.ambient_viewcond_adjust_textctrl_label,
					 self.ambient_viewcond_adjust_info,
					 self.ambient_measure_btn,
					 self.black_output_offset_label,
					 self.black_output_offset_ctrl,
					 self.black_output_offset_intctrl,
					 self.black_output_offset_intctrl_label,
					 self.black_point_correction_label,
					 self.black_point_correction_auto_cb,
					 self.black_point_rate_label,
					 self.black_point_rate_ctrl,
					 self.black_point_rate_floatctrl):
			if (ctrl is not self.trc_type_ctrl or
				self.trc_ctrl.GetSelection() == 0):
				ctrl.GetContainingSizer().Show(ctrl,
											   show_advanced_calibration_options)
		self.black_point_correction_auto_handler()
		self.calpanel.Layout()
		self.calpanel.Refresh()
		self.calpanel.Thaw()
		self.update_scrollbars()
	
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
		if not self.plugplay_timer.IsRunning():
			self.plugplay_timer.Start(10000)
		if not self.update_profile_name_timer.IsRunning():
			self.update_profile_name_timer.Start(1000)
	
	def stop_timers(self):
		self.plugplay_timer.Stop()
		self.update_profile_name_timer.Stop()

	def synthicc_create_handler(self, event):
		""" Assign and initialize the synthetic ICC creation window """
		if not getattr(self, "synthiccframe", None):
			self.init_synthiccframe()
		if self.synthiccframe.IsShownOnScreen():
			self.synthiccframe.Raise()
		else:
			self.synthiccframe.Show(not self.synthiccframe.IsShownOnScreen())
	
	def colorimeter_correction_matrix_ctrl_handler(self, event):
		measurement_mode = getcfg("measurement_mode")
		if event.GetId() == self.colorimeter_correction_matrix_ctrl.GetId():
			path = None
			ccmx = getcfg("colorimeter_correction_matrix_file").split(":", 1)
			if self.colorimeter_correction_matrix_ctrl.GetSelection() == 0:
				# Off
				ccmx = ["", ""]
			elif self.colorimeter_correction_matrix_ctrl.GetSelection() == 1:
				# Auto
				ccmx = ["AUTO", ""]
			else:
				path = self.ccmx_item_paths[
					self.colorimeter_correction_matrix_ctrl.GetSelection() - 2]
				ccmx = ["", path]
			setcfg("colorimeter_correction_matrix_file", ":".join(ccmx))
			self.update_colorimeter_correction_matrix_ctrl_items()
		else:
			path = None
			ccmx = getcfg("colorimeter_correction_matrix_file").split(":", 1)
			defaultDir, defaultFile = get_verified_path(None, ccmx.pop())
			dlg = wx.FileDialog(self, 
								lang.getstr("colorimeter_correction_matrix_file.choose"), 
								defaultDir=defaultDir if defaultFile else config.get_argyll_data_dir(), 
								defaultFile=defaultFile,
								wildcard=lang.getstr("filetype.ccmx") + 
										 "|*.ccmx;*.ccss", 
								style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
			dlg.Center(wx.BOTH)
			if dlg.ShowModal() == wx.ID_OK:
				path = dlg.GetPath()
			dlg.Destroy()
			if path:
				if (getcfg("colorimeter_correction_matrix_file").split(":")[0] != "AUTO" or
					path not in self.ccmx_cached_paths):
					setcfg("colorimeter_correction_matrix_file", ":" + path)
				self.update_colorimeter_correction_matrix_ctrl_items(warn_on_mismatch=True)
		if measurement_mode != getcfg("measurement_mode"):
			# Check if black point correction should be turned on
			self.measurement_mode_ctrl_handler()
	
	def colorimeter_correction_web_handler(self, event):
		""" Check the web for cccmx or ccss files """
		if self.worker.instrument_supports_ccss():
			filetype = 'ccss,ccmx'
		else:
			filetype = 'ccmx'
		params = {'get': True,
				  'type': filetype,
				  'display': self.worker.get_display_name(False, True) or "Unknown",
				  'instrument': self.worker.get_instrument_name() or "Unknown"}
		self.worker.interactive = False
		self.worker.start(colorimeter_correction_web_check_choose, 
						  http_request, 
						  ckwargs={"parent": self}, 
						  wargs=(self, domain, "GET",
								 "/colorimetercorrections/index.php", params),
						  progress_msg=lang.getstr("colorimeter_correction.web_check"),
						  stop_timers=False)
	
	def create_colorimeter_correction_handler(self, event=None):
		"""
		Create a CCSS or CCMX file from one or more .ti3 files
		
		Atleast one of the ti3 files must be a measured with a spectrometer.
		
		"""
		dlg = ConfirmDialog(self,
							msg=lang.getstr("colorimeter_correction.create.info"), 
							ok=lang.getstr("colorimeter_correction.create"), 
							cancel=lang.getstr("cancel"), 
							alt=lang.getstr("measure.testchart"), 
							bitmap=geticon(32, "dialog-information"))
		dlg.alt.Enable(bool(self.worker.displays) and 
					   bool(self.worker.instruments))
		result = dlg.ShowModal()
		dlg.Destroy()
		if result == wx.ID_CANCEL:
			return
		elif result != wx.ID_OK:
			if not is_ccxx_testchart():
				setcfg("testchart.file.backup", getcfg("testchart.file"))
			self.set_testchart(get_ccxx_testchart())
			self.measure_handler()
			return
		try:
			ccxx = CGATS.CGATS(get_ccxx_testchart())
		except (IOError, CGATS.CGATSInvalidError), exception:
			show_result_dialog(exception, self)
			return
		cgats_list = []
		reference_ti3 = None
		colorimeter_ti3 = None
		spectral = False
		for n in (0, 1):
			path = None
			if reference_ti3:
				defaultDir, defaultFile = get_verified_path("last_colorimeter_ti3_path")
				msg = lang.getstr("measurement_file.choose.colorimeter")
			else:
				defaultDir, defaultFile = get_verified_path("last_reference_ti3_path")
				msg = lang.getstr("measurement_file.choose.reference")
			dlg = wx.FileDialog(self, 
								msg,
								defaultDir=defaultDir,
								defaultFile=defaultFile,
								wildcard=lang.getstr("filetype.ti3") +
										 "|*.ti3;*.icm;*.icc", 
								style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
			dlg.Center(wx.BOTH)
			if dlg.ShowModal() == wx.ID_OK:
				path = dlg.GetPath()
			dlg.Destroy()
			if path:
				try:
					if os.path.splitext(path.lower())[1] in (".icm", ".icc"):
						profile = ICCP.ICCProfile(path)
						cgats = self.worker.ti1_lookup_to_ti3(ccxx, profile,
															  pcs="x",
															  intent="a")[1]
						cgats.add_keyword("DATA_SOURCE",
										  profile.tags.get("meta",
														   {}).get("DATA_source",
																   {}).get("value",
																		   "").upper() or
										  "Unknown")
						if cgats.DATA_SOURCE == "EDID":
							instrument = "EDID"
						else:
							targ = profile.tags.get("CIED",
													profile.tags.get("targ", ""))
							instrument = None
							if targ[0:4] == "CTI3":
								targ = CGATS.CGATS(targ)
								instrument = targ.queryv1("TARGET_INSTRUMENT")
							if not instrument:
								instrument = profile.tags.get("meta",
															  {}).get("MEASUREMENT_device",
																	  {}).get("value",
																			  "Unknown")
						cgats.add_keyword("TARGET_INSTRUMENT", instrument)
						spectral = "YES" if instruments.get(get_canonical_instrument_name(cgats.TARGET_INSTRUMENT),
															{}).get("spectral", False) else "NO"
						cgats.add_keyword("INSTRUMENT_TYPE_SPECTRAL", spectral)
						cgats.ARGYLL_COLPROF_ARGS = CGATS.CGATS()
						cgats.ARGYLL_COLPROF_ARGS.key = "ARGYLL_COLPROF_ARGS"
						cgats.ARGYLL_COLPROF_ARGS.parent = cgats
						cgats.ARGYLL_COLPROF_ARGS.root = cgats
						cgats.ARGYLL_COLPROF_ARGS.type = "SECTION"
						display = profile.tags.get("meta",
												   {}).get("EDID_model",
														   {}).get("value",
																   "").encode("UTF-7")
						manufacturer = profile.tags.get("meta",
												   {}).get("EDID_manufacturer",
														   {}).get("value",
																   "").encode("UTF-7")
						cgats.ARGYLL_COLPROF_ARGS.add_data('-M "%s" -A "%s"' %
														   (display,
															manufacturer))
						cgats = CGATS.CGATS(str(cgats))
					else:
						cgats = CGATS.CGATS(path)
					if not cgats.queryv1("DATA"):
						raise CGATS.CGATSError("Missing DATA")
				except Exception, exception:
					safe_print(exception)
					InfoDialog(self,
							   msg=lang.getstr("error.measurement.file_invalid", path), 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
					return
				else:
					cgats_list.append(cgats)
					# Check if measurement contains spectral values
					# Check if instrument type is spectral
					if (cgats.queryv1("SPECTRAL_BANDS") or
						cgats.queryv1("DATA_SOURCE") == "EDID"):
						if reference_ti3:
							# We already have a reference ti3
							reference_ti3 = None
							break
						reference_ti3 = cgats
						setcfg("last_reference_ti3_path", path)
						if cgats.queryv1("SPECTRAL_BANDS"):
							spectral = True
							# Ask if user wants to create CCSS
							dlg = ConfirmDialog(self, 
												msg=lang.getstr("create_ccss_or_ccmx"), 
												ok=lang.getstr("CCSS"), 
												cancel=lang.getstr("cancel"), 
												alt=lang.getstr("CCMX"),
												bitmap=geticon(32, "dialog-information"))
							result = dlg.ShowModal()
							dlg.Destroy()
							if result == wx.ID_OK:
								break
							elif result == wx.ID_CANCEL:
								return
					elif cgats.queryv1("INSTRUMENT_TYPE_SPECTRAL") == "YES":
						if reference_ti3:
							# We already have a reference ti3
							reference_ti3 = None
							break
						reference_ti3 = cgats
						setcfg("last_reference_ti3_path", path)
					elif cgats.queryv1("INSTRUMENT_TYPE_SPECTRAL") == "NO":
						if colorimeter_ti3:
							# We already have a colorimeter ti3
							colorimeter_ti3 = None
							break
						colorimeter_ti3 = cgats
						setcfg("last_colorimeter_ti3_path", path)
			else:
				# User canceled dialog
				return
		# Check if atleast one file has been measured with a reference
		if not reference_ti3:
			InfoDialog(self,
					   msg=lang.getstr("error.measurement.one_reference"), 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-error"))
			return
		if len(cgats_list) == 2:
			if not colorimeter_ti3:
				# If 2 files, check if atleast one file has NOT been measured 
				# with a spectro (CCMX creation)
				InfoDialog(self,
						   msg=lang.getstr("error.measurement.one_colorimeter"), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				return
			# Use only the device combinations from CCXX testchart
			reference_new = CGATS.CGATS("BEGIN_DATA\nEND_DATA")
			reference_new.DATA_FORMAT = reference_ti3.queryv1("DATA_FORMAT")
			colorimeter_new = CGATS.CGATS("BEGIN_DATA\nEND_DATA")
			colorimeter_new.DATA_FORMAT = colorimeter_ti3.queryv1("DATA_FORMAT")
			data_reference = reference_ti3.queryv1("DATA")
			data_colorimeter = colorimeter_ti3.queryv1("DATA")
			required = ccxx.queryv(("RGB_R", "RGB_G", "RGB_B"))
			devicecombination2name = {"RGB_R=100 RGB_G=100 RGB_B=100": "white",
									  "RGB_R=100 RGB_G=0 RGB_B=0": "red",
									  "RGB_R=0 RGB_G=100 RGB_B=0": "green",
									  "RGB_R=0 RGB_G=0 RGB_B=100": "blue"}
			for i, values in required.iteritems():
				patch = OrderedDict([("RGB_R", values[0]),
									 ("RGB_G", values[1]),
									 ("RGB_B", values[2])])
				devicecombination = " ".join(["=".join([key, "%i" % value])
											  for key, value in
											  patch.iteritems()])
				name = devicecombination2name.get(devicecombination,
												  devicecombination)
				item = data_reference.queryi1(patch)
				if item:
					reference_new.DATA.add_data(item)
				else:
					show_result_dialog(lang.getstr("error.testchart.missing_fields", 
									   (os.path.basename(reference_ti3.filename),
										lang.getstr(name))))
					return
				item = data_colorimeter.queryi1(patch)
				if item:
					colorimeter_new.DATA.add_data(item)
				else:
					show_result_dialog(lang.getstr("error.testchart.missing_fields", 
									   (os.path.basename(colorimeter_ti3.filename),
									    lang.getstr(name))))
					return
			reference_ti3.queryi1("DATA").DATA = reference_new.DATA
			colorimeter_ti3.queryi1("DATA").DATA = colorimeter_new.DATA
			# If the reference comes from EDID, normalize luminance to Y=100
			if reference_ti3.queryv1("DATA_SOURCE") == "EDID":
				white = colorimeter_ti3.queryi1("DATA").queryi1({"RGB_R": 100,
																 "RGB_G": 100,
																 "RGB_B": 100})
				white = " ".join([str(v) for v in (white["XYZ_X"],
												   white["XYZ_Y"],
												   white["XYZ_Z"])])
				colorimeter_ti3.queryi1("DATA").LUMINANCE_XYZ_CDM2 = white
			# Add display base ID
			if not colorimeter_ti3.queryv1("DISPLAY_TYPE_BASE_ID"):
				# c, l (most colorimeters)
				# R (ColorHug and Colorimétre HCFR)
				# F (ColorHug)
				# f (ColorMunki Smile)
				# g (DTP94)
				colorimeter_ti3[0].add_keyword("DISPLAY_TYPE_BASE_ID",
											   {"c": 2,
												"l": 1,
												"R": 1,
												"F": 2,
												"f": 1,
												"g": 3}.get(getcfg("measurement_mode"),
															1))
		elif not spectral:
			# If 1 file, check if it contains spectral values (CCSS creation)
			InfoDialog(self,
					   msg=lang.getstr("error.measurement.missing_spectral"), 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-error"))
			return
		else:
			description = self.worker.get_display_name(True)
		# Add display type
		for cgats in cgats_list:
			if not cgats.queryv1("DISPLAY_TYPE_REFRESH"):
				cgats[0].add_keyword("DISPLAY_TYPE_REFRESH",
									 {"c": "YES",
									  "l": "NO"}.get(getcfg("measurement_mode"),
													 "NO"))
		options_dispcal, options_colprof = get_options_from_ti3(reference_ti3)
		display = None
		manufacturer = None
		manufacturer_display = None
		for option in options_colprof:
			if option.startswith("M"):
				display = option[1:].strip(' "')
			elif option.startswith("A"):
				manufacturer = option[1:].strip(' "')
		if manufacturer and display:
			manufacturer_display = " ".join([colord.quirk_manufacturer(manufacturer),
											 display])
		elif display:
			manufacturer_display = display
		if len(cgats_list) == 2:
			instrument = colorimeter_ti3.queryv1("TARGET_INSTRUMENT")
			if instrument:
				instrument = safe_unicode(instrument, "UTF-8")
			description = "%s & %s" % (instrument or 
									   self.worker.get_instrument_name(),
									   manufacturer_display or
									   self.worker.get_display_name(True))
		target_instrument = reference_ti3.queryv1("TARGET_INSTRUMENT")
		if target_instrument:
			description = "%s (%s)" % (description, target_instrument)
		args = []
		# Allow use to alter description, display and instrument
		dlg = ConfirmDialog(
			self, 
			msg=lang.getstr("colorimeter_correction.create.details"), 
			ok=lang.getstr("ok"), cancel=lang.getstr("cancel"), 
			bitmap=geticon(32, "dialog-question"))
		dlg.sizer3.Add(wx.StaticText(dlg, -1, lang.getstr("description")), 1, 
					   flag=wx.TOP | wx.ALIGN_LEFT, border=12)
		dlg.description_txt_ctrl = wx.TextCtrl(dlg, -1, 
											   description, 
											   size=(400, -1))
		dlg.sizer3.Add(dlg.description_txt_ctrl, 1, 
					   flag=wx.TOP | wx.ALIGN_LEFT, border=4)
		if not display:
			dlg.sizer3.Add(wx.StaticText(dlg, -1, lang.getstr("display")), 1, 
						   flag=wx.TOP | wx.ALIGN_LEFT, border=12)
			dlg.display_txt_ctrl = wx.TextCtrl(dlg, -1, 
											   self.worker.get_display_name(True,
																			True), 
											   size=(400, -1))
			dlg.sizer3.Add(dlg.display_txt_ctrl, 1, 
						   flag=wx.TOP | wx.ALIGN_LEFT, border=4)
		if not manufacturer:
			dlg.sizer3.Add(wx.StaticText(dlg, -1, lang.getstr("display.manufacturer")), 1, 
						   flag=wx.TOP | wx.ALIGN_LEFT, border=12)
			dlg.manufacturer_txt_ctrl = wx.TextCtrl(dlg, -1, 
													self.worker.get_display_edid().get("manufacturer", ""), 
													size=(400, -1))
			dlg.sizer3.Add(dlg.manufacturer_txt_ctrl, 1, 
						   flag=wx.TOP | wx.ALIGN_LEFT, border=4)
		dlg.sizer4 = wx.FlexGridSizer(2, 3, 0, 8)
		dlg.sizer4.AddGrowableCol(0, 1)
		dlg.sizer4.AddGrowableCol(1, 1)
		dlg.sizer4.AddGrowableCol(2, 1)
		dlg.sizer3.Add(dlg.sizer4, 1, flag=wx.EXPAND)
		dlg.sizer4.Add(wx.StaticText(dlg, -1, lang.getstr("display.tech")), 1, 
					   flag=wx.TOP | wx.ALIGN_LEFT, border=12)
		dlg.sizer4.Add(wx.StaticText(dlg, -1, lang.getstr("backlight")), 1, 
					   flag=wx.TOP | wx.ALIGN_LEFT, border=12)
		dlg.sizer4.Add(wx.StaticText(dlg, -1, lang.getstr("panel.type")), 1, 
					   flag=wx.TOP | wx.ALIGN_LEFT, border=12)
		# Display technology
		dlg.display_tech_ctrl = wx.Choice(dlg, -1,
										  choices=["LCD", "CRT",
												   "Plasma", "Projector"])
		dlg.display_tech_ctrl.SetSelection(0)
		dlg.sizer4.Add(dlg.display_tech_ctrl,
					   flag=wx.TOP | wx.ALIGN_LEFT | wx.EXPAND, border=4)
		def display_tech_handler(event):
			tech = dlg.display_tech_ctrl.GetStringSelection()
			illumination = dlg.illumination_ctrl.GetStringSelection()
			separate_illumination = ("LCD", "DLP", "LCoS")
			dlg.illumination_ctrl.Enable(tech in separate_illumination)
			if tech in ("DLP", "LCoS") and illumination == "CCFL":
				dlg.illumination_ctrl.SetStringSelection("UHP")
			dlg.panel_type_ctrl.Enable(tech == "LCD")
		dlg.Bind(wx.EVT_CHOICE, display_tech_handler, 
				 id=dlg.display_tech_ctrl.GetId())
		# Display illumination/backlight
		dlg.illumination_ctrl = wx.Choice(dlg, -1,
										  choices=["CCFL",
												   "White LED",
												   "RGB LED"])
		dlg.illumination_ctrl.SetSelection(0)
		dlg.sizer4.Add(dlg.illumination_ctrl,
					   flag=wx.TOP | wx.ALIGN_LEFT | wx.EXPAND, border=4)
		# Panel type
		dlg.panel_type_ctrl = wx.Choice(dlg, -1,
										choices=["IPS",
												 "Wide Gamut IPS",
												 "PVA",
												 "Wide Gamut PVA",
												 "TN"])
		dlg.panel_type_ctrl.SetSelection(1)
		dlg.sizer4.Add(dlg.panel_type_ctrl,
					   flag=wx.TOP | wx.ALIGN_LEFT | wx.EXPAND, border=4)
		dlg.description_txt_ctrl.SetFocus()
		dlg.sizer0.SetSizeHints(dlg)
		dlg.sizer0.Layout()
		dlg.Center()
		result = dlg.ShowModal()
		args += ["-E", safe_str(dlg.description_txt_ctrl.GetValue().strip(), "UTF-8")]
		if not display:
			display = dlg.display_txt_ctrl.GetValue()
		args += ["-I", safe_str(display.strip(), "UTF-8")]
		tech = []
		for ctrl in (dlg.display_tech_ctrl, dlg.illumination_ctrl,
					 dlg.panel_type_ctrl):
			if ctrl.IsEnabled() and ctrl.GetStringSelection():
				tech.append(ctrl.GetStringSelection())
		if reference_ti3 and not colorimeter_ti3:
			args += ["-T", safe_str(" ".join(tech), "UTF-8")]
		if result != wx.ID_OK:
			return
		# Prepare our files
		cwd = self.worker.create_tempdir()
		ti3_tmp_names = []
		if reference_ti3:
			reference_ti3.write(os.path.join(cwd, 'reference.ti3'))
			ti3_tmp_names.append('reference.ti3')
		if colorimeter_ti3:
			# Create CCMX
			colorimeter_ti3.write(os.path.join(cwd, 'colorimeter.ti3'))
			ti3_tmp_names.append('colorimeter.ti3')
			name = "correction"
			ext = ".ccmx"
		else:
			# Create CCSS
			args.append("-S")
			name = "calibration"
			ext = ".ccss"
		args.append("-f")
		args.append(",".join(ti3_tmp_names))
		args.append(name + ext)
		result = self.worker.create_ccxx(args, cwd)
		source = os.path.join(self.worker.tempdir, name + ext)
		if isinstance(result, Exception):
			show_result_dialog(result, self)
		elif result and os.path.isfile(source):
			# Important: Do not use parsed CGATS, order of keywords may be 
			# different than raw data so MD5 will be different
			try:
				cgatsfile = open(source, "rb")
			except Exception, exception:
				show_result_dialog(exception, self)
				self.worker.wrapup(False)
				return
			cgats = universal_newlines(cgatsfile.read())
			cgatsfile.close()
			if (reference_ti3[0].get("TARGET_INSTRUMENT") and
				not re.search('\nREFERENCE\s+".+?"\n', cgats)):
				# By default, CCSS files don't contain reference instrument
				cgats = re.sub('(\nKEYWORD\s+"DISPLAY"\n)',
							   '\nKEYWORD "REFERENCE"\nREFERENCE "%s"\\1' %
							   reference_ti3[0].get("TARGET_INSTRUMENT"), cgats)
			if not re.search('\nTECHNOLOGY\s+".+?"\n', cgats):
				# By default, CCMX files don't contain technology string
				cgats = re.sub('(\nKEYWORD\s+"DISPLAY"\n)',
							   '\nKEYWORD "TECHNOLOGY"\nTECHNOLOGY "%s"\\1' %
							   safe_str(" ".join(tech), "UTF-8"), cgats)
			manufacturer_id = None
			if not manufacturer:
				manufacturer = dlg.manufacturer_txt_ctrl.GetValue()
			if manufacturer:
				if not pnpidcache:
					# Populate pnpidcache
					get_manufacturer_name("???")
				manufacturers = dict([name, id] for id, name in
									 pnpidcache.iteritems())
				manufacturer_id = manufacturers.get(manufacturer)
			if manufacturer_id and not re.search('\nMANUFACTURER_ID\s+".+?"\n',
												 cgats):
				# By default, CCMX/CCSS files don't contain manufacturer ID
				cgats = re.sub('(\nKEYWORD\s+"DISPLAY"\n)',
							   '\nKEYWORD "MANUFACTURER_ID"\nMANUFACTURER_ID "%s"\\1' %
							   safe_str(manufacturer_id, "UTF-8"), cgats)
			if manufacturer and not re.search('\nMANUFACTURER\s+".+?"\n', cgats):
				# By default, CCMX/CCSS files don't contain manufacturer
				cgats = re.sub('(\nKEYWORD\s+"DISPLAY"\n)',
							   '\nKEYWORD "MANUFACTURER"\nMANUFACTURER "%s"\\1' %
							   safe_str(manufacturer, "UTF-8"), cgats)
			result = check_create_dir(config.get_argyll_data_dir())
			if isinstance(result, Exception):
				show_result_dialog(result, self)
				return
			if (colorimeter_correction_check_overwrite(self, cgats)):
				self.upload_colorimeter_correction(cgats)
		elif result is not None:
			InfoDialog(self,
					   msg=lang.getstr("colorimeter_correction.create.failure") +
						   "\n" + "\n".join(self.worker.errors), 
					   ok=lang.getstr("cancel"), 
					   bitmap=geticon(32, "dialog-error"))
		self.worker.wrapup(False)
	
	def upload_colorimeter_correction(self, cgats):
		""" Ask the user if he wants to upload a colorimeter correction
		to the online database. Upload the file. """
		dlg = ConfirmDialog(self, 
							msg=lang.getstr("colorimeter_correction.upload.confirm"), 
							ok=lang.getstr("ok"), 
							cancel=lang.getstr("cancel"), 
							bitmap=geticon(32, "dialog-information"))
		result = dlg.ShowModal()
		dlg.Destroy()
		if result == wx.ID_OK:
			params = {"cgats": cgats}
			# Upload correction
			self.worker.interactive = False
			self.worker.start(lambda result: result, 
							  upload_colorimeter_correction, 
							  wargs=(self, params),
							  progress_msg=lang.getstr("colorimeter_correction.upload"),
							  stop_timers=False)
	
	def upload_colorimeter_correction_handler(self, event):
		""" Let user choose a ccss/ccmx file to upload """
		path = None
		defaultDir, defaultFile = get_verified_path("last_filedialog_path")
		dlg = wx.FileDialog(self, 
							lang.getstr("colorimeter_correction_matrix_file.choose"),
							defaultDir=defaultDir,
							defaultFile=defaultFile,
							wildcard=lang.getstr("filetype.ccmx") + 
									 "|*.ccmx;*.ccss", 
							style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
		dlg.Center(wx.BOTH)
		if dlg.ShowModal() == wx.ID_OK:
			path = dlg.GetPath()
		dlg.Destroy()
		if path:
			setcfg("last_filedialog_path", path)
			# Important: Do not use parsed CGATS, order of keywords may be 
			# different than raw data so MD5 will be different
			cgatsfile = open(path, "rb")
			cgats = cgatsfile.read()
			cgatsfile.close()
			originator = re.search('\nORIGINATOR\s+"Argyll', cgats)
			if not originator:
				InfoDialog(self,
						   msg=lang.getstr("colorimeter_correction.upload.deny"), 
						   ok=lang.getstr("cancel"), 
						   bitmap=geticon(32, "dialog-error"))
			else:
				self.upload_colorimeter_correction(cgats)

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
		self.update_colorimeter_correction_matrix_ctrl()
		self.update_colorimeter_correction_matrix_ctrl_items()
	
	def import_colorimeter_correction_handler(self, event):
		"""
		Convert correction matrices from other profiling softwares to Argyll's
		CCMX or CCSS format (or to spyd4cal.bin in case of the Spyder4)
		
		Currently supported: iColor Display (native import to CCMX),
							 i1 Profiler (import to CCSS via Argyll CMS 1.3.4)
							 Spyder4 (import to spyd4cal.bin via Argyll CMS 1.3.6)
		
		"""
		dlg = ConfirmDialog(self, title=lang.getstr("colorimeter_correction.import"),
							msg=lang.getstr("colorimeter_correction.import.auto_manual"),
							ok=lang.getstr("auto"),
							cancel=lang.getstr("cancel"),
							bitmap=geticon(32, "dialog-question"),
							alt=lang.getstr("file.select"))
		choice = dlg.ShowModal()
		if choice == wx.ID_CANCEL:
			return
		result = None
		i1d3 = False
		i1d3ccss = get_argyll_util("i1d3ccss")
		if i1d3ccss and choice == wx.ID_OK:
			# Automatically import X-Rite .edr files
			result = self.worker.import_edr()
			if not isinstance(result, Exception):
				i1d3 = result
		spyd4 = False
		spyd4en = get_argyll_util("spyd4en")
		if spyd4en and choice == wx.ID_OK:
			# Automatically import Spyder4 calibrations
			result = self.worker.import_spyd4cal()
			if not isinstance(result, Exception):
				spyd4 = result
		# Import iColorDisplay device corrections or let the user choose
		defaultDir = ""
		defaultFile = ""
		path = None
		# Look for iColorDisplay
		if sys.platform == "win32":
			defaultDir = os.path.join(getenvu("PROGRAMFILES", ""), "Quato", 
									  "iColorDisplay")
		elif sys.platform == "darwin":
			paths = glob.glob(os.path.join(os.path.sep, "Applications", 
										   "iColorDisplay*.app"))
			paths += glob.glob(os.path.join(os.path.sep, "Volumes", 
											"iColorDisplay*", 
											"iColorDisplay*.app"))
			if paths:
				defaultDir = paths[-1]
		if defaultDir and os.path.isdir(defaultDir):
			# iColorDisplay found
			defaultFile = "DeviceCorrections.txt"
		elif i1d3ccss and not i1d3:
			# Look for *.edr files
			if sys.platform == "win32":
				defaultDir = os.path.join(getenvu("PROGRAMFILES", ""), 
										  "X-Rite", "Devices", "i1d3", 
										  "Calibrations")
			elif sys.platform == "darwin":
				paths = glob.glob(os.path.join(os.path.sep, "Library", 
											   "Application Support", "X-Rite", 
											   "Devices", "i1d3xrdevice", 
											   "Contents", "Resources", 
											   "Calibrations"))
				paths += glob.glob(os.path.join(os.path.sep, "Volumes", 
												"i1Profiler"))
				paths += glob.glob(os.path.join(os.path.sep, "Volumes", 
												"ColorMunki Display"))
				if paths:
					defaultDir = paths[-1]
		elif spyd4en and not spyd4:
			# Look for dccmtr.dll
			if sys.platform == "win32":
				paths = glob.glob(os.path.join(getenvu("PROGRAMFILES", ""), 
											   "Datacolor", "Spyder4*", 
											   "dccmtr.dll"))
			elif sys.platform == "darwin":
				# Look for setup.exe on CD-ROM
				paths = glob.glob(os.path.join(os.path.sep, "Volumes", 
											   "Datacolor", "Data",
											   "setup.exe"))
				paths += glob.glob(os.path.join(os.path.sep, "Volumes", 
												"Datacolor_ISO", "Data",
												"setup.exe"))
			if paths:
				defaultDir, defaultFile = os.path.split(paths[-1])
		if defaultDir and os.path.isdir(defaultDir):
			if choice == wx.ID_OK:
				path = os.path.join(defaultDir, defaultFile)
		if (not path or not os.path.isfile(path)) and not (i1d3 or spyd4):
			dlg = wx.FileDialog(self, 
								lang.getstr("colorimeter_correction.import.choose"),
								defaultDir=defaultDir,
								defaultFile=defaultFile,
								wildcard=lang.getstr("filetype.any") + 
										 "|*.edr;*.exe;*.txt", 
								style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
			dlg.Center(wx.BOTH)
			if dlg.ShowModal() == wx.ID_OK:
				path = dlg.GetPath()
			dlg.Destroy()
		icd = False
		if path and os.path.exists(path):
			type = None
			if path.lower().endswith(".txt"):
				type = ".txt"
			else:
				icolordisplay = "icolordisplay" in os.path.basename(path).lower()
				if path.lower().endswith(".dmg"):
					if icolordisplay:
						# TODO: We have a iColorDisplay disk image,
						# try mounting it
						pass
				elif i1d3ccss and path.lower().endswith(".edr"):
					type = "xrite"
				elif path.lower().endswith(".exe"):
					if icolordisplay:
						# TODO: We have a iColorDisplay installer,
						# try opening it as lzma archive
						pass
					elif i1d3ccss and ("colormunki" in
									   os.path.basename(path).lower() or
									   "i1profiler" in
									   os.path.basename(path).lower()):
						# Assume X-Rite installer
						type = "xrite"
					elif spyd4en and "spyder4" in os.path.basename(path).lower():
						# Assume Spyder4
						type = "spyder4"
			if type == ".txt":
				if not getcfg("dry_run"):
					# Assume iColorDisplay DeviceCorrections.txt
					ccmx_dir = config.get_argyll_data_dir()
					if not os.path.exists(ccmx_dir):
						result = check_create_dir(ccmx_dir)
						if isinstance(result, Exception):
							show_result_dialog(result, self)
							return
					safe_print(lang.getstr("colorimeter_correction.import"))
					safe_print(path)
					try:
						ccmx.convert_devicecorrections_to_ccmx(path, ccmx_dir)
					except (EnvironmentError, UnicodeDecodeError,
							demjson.JSONDecodeError), exception:
						result = Error(lang.getstr("file.invalid"))
					else:
						result = icd = True
			elif type == "xrite":
				# Import .edr
				result = i1d3 = self.worker.import_edr([path])
			elif type == "spyder4":
				# Import spyd4cal.bin
				result = spyd4 = self.worker.import_spyd4cal([path])
			else:
				result = Error(lang.getstr("error.file_type_unsupported"))
		if isinstance(result, Exception):
			show_result_dialog(result, self)
		elif result:
			if spyd4en:
				self.update_measurement_modes()
			self.update_colorimeter_correction_matrix_ctrl_items(True)
			imported = []
			if i1d3:
				imported.append("i1 Profiler/ColorMunki Display")
			if spyd4:
				imported.append("Spyder4")
			if icd:
				imported.append("iColor Display")
			InfoDialog(self,
					   msg=lang.getstr("colorimeter_correction.import.success",
									   "\n".join(imported)), 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-information"))
		elif result is not None:
			InfoDialog(self,
					   msg=lang.getstr("colorimeter_correction.import.failure"), 
					   ok=lang.getstr("cancel"), 
					   bitmap=geticon(32, "dialog-error"))

	def display_ctrl_handler(self, event, load_lut=True,
							 update_ccmx_items=True):
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
			if load_lut:
				profile = get_display_profile(display_no)
			self.profile_info_btn.Enable(bool(profile))
		if self.display_lut_link_ctrl.IsShown():
			self.display_lut_link_ctrl_handler(CustomEvent(
				wx.EVT_BUTTON.evtType[0], self.display_lut_link_ctrl), 
				bool(int(getcfg("display_lut.link"))))
		if load_lut:
			if debug:
				safe_print("[D] display_ctrl_handler -> lut_viewer_load_lut", 
						   profile.getDescription() if profile else None)
			self.lut_viewer_load_lut(profile=profile)
			if debug:
				safe_print("[D] display_ctrl_handler -> lut_viewer_load_lut END")
		if config.get_display_name() == "madVR":
			if getcfg("calibration.use_video_lut.backup", False) is None:
				setcfg("calibration.use_video_lut.backup",
					   getcfg("calibration.use_video_lut"))
				setcfg("calibration.use_video_lut", 0)
		elif getcfg("calibration.use_video_lut.backup", False):
			setcfg("calibration.use_video_lut",
				   getcfg("calibration.use_video_lut.backup"))
			setcfg("calibration.use_video_lut.backup", None)
		if self.IsShownOnScreen():
			self.update_menus()
		if (update_ccmx_items and
			getcfg("colorimeter_correction_matrix_file").split(":")[0] == "AUTO"):
			self.update_colorimeter_correction_matrix_ctrl_items()
		self.update_main_controls()
		if getattr(self, "reportframe", None):
			self.reportframe.update_main_controls()

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
		link = (not len(self.worker.displays) or
				(link and self.worker.lut_access[max(min(len(self.worker.displays),
														 getcfg("display.number")),
													 0) - 1]))
		lut_no = -1
		if link:
			self.display_lut_link_ctrl.SetBitmapLabel(bitmap_link)
			try:
				lut_no = self.display_lut_ctrl.Items.index(self.display_ctrl.GetStringSelection())
			except ValueError:
				pass
		else:
			self.display_lut_link_ctrl.SetBitmapLabel(bitmap_unlink)
		if lut_no < 0:
			try:
				lut_no = self.display_lut_ctrl.Items.index(self.display_ctrl.Items[getcfg("display_lut.number") - 1])
			except (IndexError, ValueError):
				lut_no = min(0, self.display_ctrl.GetSelection())
		self.display_lut_ctrl.SetSelection(lut_no)
		self.display_lut_ctrl.Enable(not link and 
									 self.display_lut_ctrl.GetCount() > 1)
		setcfg("display_lut.link", int(link))
		try:
			i = self.displays.index(self.display_lut_ctrl.Items[lut_no])
		except (IndexError, ValueError):
			i = min(0, self.display_ctrl.GetSelection())
		setcfg("display_lut.number", i + 1)

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
					defaults["measurement_mode"], 1))
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
					defaults["measurement_mode"], 1))
			v = None
			InfoDialog(self, msg=lang.getstr("adaptive_mode_unavailable"), 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-information"))
		cal_changed = v != getcfg("measurement_mode") and \
					  getcfg("calibration.file") not in self.presets
		if cal_changed:
			self.cal_changed()
		setcfg("measurement_mode", (strtr(v, {"V": "", 
											  "H": ""}) if v else None) or None)
		instrument_features = self.worker.get_instrument_features()
		if instrument_features.get("adaptive_mode"):
			setcfg("measurement_mode.adaptive", 1 if v and "V" in v else 0)
		if instrument_features.get("highres_mode"):
			setcfg("measurement_mode.highres", 1 if v and "H" in v else 0)
		if v and self.worker.get_instrument_name() == "ColorHug" and "p" in v:
			# ColorHug projector mode is just a correction matrix
			# Avoid setting ColorMunki projector mode
			v = v.replace("p", "")
		# ColorMunki projector mode is an actual special sensor dial position
		setcfg("measurement_mode.projector", 1 if v and "p" in v else None)
		self.update_colorimeter_correction_matrix_ctrl()
		if (v and (((not "c" in v or "p" in v) and
					float(self.get_black_point_correction()) > 0) or
				   ("c" in v and
					float(self.get_black_point_correction()) == 0)) and
			getcfg("calibration.black_point_correction_choice.show") and
			not getcfg("calibration.black_point_correction.auto")):
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
		lut_type = v in ("l", "x", "X")
		self.gamap_btn.Enable(lut_type)
		self.low_quality_b2a_cb.SetValue(lut_type and
										 getcfg("profile.quality.b2a") == "l")
		self.low_quality_b2a_cb.Enable(lut_type)
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
		""" Check if the selected testchart has at least the recommended
		amount of patches. Give user the choice to use the recommended amount
		if patch count is lower. """
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
		if recommended > patches and not is_ccxx_testchart():
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
	
	def measurement_file_check_auto_handler(self, event):
		if not getcfg("ti3.check_sanity.auto"):
			dlg = ConfirmDialog(self,
								msg=lang.getstr("measurement_file.check_sanity.auto.warning"),  
								ok=lang.getstr("ok"), 
								cancel=lang.getstr("cancel"), 
								bitmap=geticon(32, "dialog-warning"), log=False)
			result = dlg.ShowModal()
			dlg.Destroy()
			if result != wx.ID_OK:
				self.menuitem_measurement_file_check_auto.Check(False)
				return
		setcfg("ti3.check_sanity.auto", 
			   int(self.menuitem_measurement_file_check_auto.IsChecked()))
	
	def measurement_file_check_handler(self, event):
		# select measurement data (ti3 or profile)
		path = None
		defaultDir, defaultFile = get_verified_path("last_ti3_path")
		dlg = wx.FileDialog(self, lang.getstr("measurement_file.choose"), 
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
				show_result_dialog(Error(lang.getstr("file.missing", path)),
								   self)
				return
			tags = OrderedDict()
			# Get filename and extension of file
			filename, ext = os.path.splitext(path)
			if ext.lower() != ".ti3":
				try:
					profile = ICCP.ICCProfile(path)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					show_result_dialog(Error(lang.getstr("profile.invalid") + 
											 "\n" + path), self)
					return
				if (profile.tags.get("CIED", "") or 
					profile.tags.get("targ", ""))[0:4] != "CTI3":
					show_result_dialog(Error(lang.getstr("profile.no_embedded_ti3") + 
											 "\n" + path), self)
					return
				ti3 = StringIO(profile.tags.get("CIED", "") or 
							   profile.tags.get("targ", ""))
			else:
				profile = None
				try:
					ti3 = open(path, "rU")
				except Exception, exception:
					show_result_dialog(Error(lang.getstr("error.file.open", path)),
									   self)
					return
			setcfg("last_ti3_path", path)
			ti3 = CGATS.CGATS(ti3)
			if self.measurement_file_check_confirm(ti3, True):
				if ti3.modified:
					if profile:
						# Regenerate the profile?
						dlg = ConfirmDialog(self,
											msg=lang.getstr("profile.confirm_regeneration"), 
											ok=lang.getstr("ok"),
											cancel=lang.getstr("cancel"),
											bitmap=geticon(32, "dialog-information"))
						dlg.Center()
						result = dlg.ShowModal()
						if result == wx.ID_OK:
							self.worker.wrapup(False)
							tmp_working_dir = self.worker.create_tempdir()
							if isinstance(tmp_working_dir, Exception):
								show_result_dialog(tmp_working_dir, self)
								return
							profile.tags.targ = ICCP.TextType("text\0\0\0\0" +
															  str(ti3) + "\0", 
															  "targ")
							profile.tags.DevD = profile.tags.CIED = profile.tags.targ
							tmp_path = os.path.join(tmp_working_dir,
													os.path.basename(path))
							profile.write(tmp_path)
							self.create_profile_handler(None, tmp_path, True)
					else:
						dlg = wx.FileDialog(self, lang.getstr("save_as"), 
											os.path.dirname(path), 
											os.path.basename(path), 
											wildcard=lang.getstr("filetype.ti3") + 
													 "|*.ti3", 
											style=wx.SAVE | wx.FD_OVERWRITE_PROMPT)
						dlg.Center(wx.BOTH)
						result = dlg.ShowModal()
						path = dlg.GetPath()
						dlg.Destroy()
						if result == wx.ID_OK:
							if not waccess(path, os.W_OK):
								show_result_dialog(Error(lang.getstr("error.access_denied.write",
																	 path)),
												   self)
								return
							try:
								ti3.write(path)
							except EnvironmentError, exception:
								show_result_dialog(exception, self)
				else:
					show_result_dialog(UnloggedInfo(lang.getstr("errors.none_found")),
									   self)

	def measurement_file_check_confirm(self, ti3=None, force=False, parent=None):
		if not getcfg("ti3.check_sanity.auto") and not force:
			return True
		if not ti3:
			profile_save_path = self.worker.tempdir
			if profile_save_path and os.path.isdir(profile_save_path):
				profile_name = getcfg("profile.name.expanded")
				ti3 = os.path.join(profile_save_path, 
								   make_argyll_compatible_path(profile_name) +
								   ".ti3")
				if not os.path.isfile(ti3):
					ti3 = None
			if not ti3:
				# Let the caller handle missing files
				return True
		try:
			if not isinstance(ti3, CGATS.CGATS):
				ti3 = CGATS.CGATS(ti3)
			ti3_1 = verify_ti1_rgb_xyz(ti3)
		except (IOError, CGATS.CGATSError), exception:
			show_result_dialog(exception, self)
			return False
		suspicious = check_ti3(ti3_1)
		if not suspicious:
			return True
		self.Show(start_timers=False)
		dlg = MeasurementFileCheckSanityDialog(parent or self, ti3_1,
											   suspicious, force)
		result = dlg.ShowModal()
		if result == wx.ID_OK:
			indexes = []
			for index in xrange(dlg.grid.GetNumberRows()):
				if dlg.grid.GetCellValue(index, 0) == "":
					indexes.insert(0, index)
			data = ti3_1.queryv1("DATA")
			removed = []
			for index in indexes:
				removed.insert(0, data.pop(dlg.suspicious_items[index]))
			for item in removed:
				safe_print("Removed patch #%i from TI3: %s" % (item.key, item))
			for index, (RGB, XYZ) in dlg.mods.iteritems():
				if index not in indexes:
					item = dlg.suspicious_items[index]
					oldRGB = []
					for i, label in enumerate("RGB"):
						oldRGB.append(item["RGB_%s" % label])
					if RGB != oldRGB:
						for i, label in enumerate("RGB"):
							item["RGB_%s" % label] = RGB[i]
					safe_print(u"Updated patch #%s in TI3: RGB %.4f %.4f %.4f \u2192 %.4f %.4f %.4f" % 
							   tuple([item.SAMPLE_ID] + oldRGB + RGB))
					oldXYZ = []
					for i, label in enumerate("XYZ"):
						oldXYZ.append(item["XYZ_%s" % label])
					if XYZ != oldXYZ:
						for i, label in enumerate("XYZ"):
							item["XYZ_%s" % label] = XYZ[i]
					safe_print(u"Updated patch #%s in TI3: XYZ %.4f %.4f %.4f \u2192 %.4f %.4f %.4f" % 
							   tuple([item.SAMPLE_ID] + oldXYZ + XYZ))
		dlg.Destroy()
		if result == wx.ID_CANCEL:
			return False
		elif result == wx.ID_OK:
			if ti3.modified:
				if ti3.filename and os.path.exists(ti3.filename) and not force:
					try:
						ti3.write()
					except EnvironmentError, exception:
						show_result_dialog(exception, self)
						return False
					safe_print("Written updated TI3 to", ti3.filename)
				return removed, ti3
		return True

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
		defaultPath = os.path.join(*get_verified_path("profile.save_path"))
		profile_name = getcfg("profile.name.expanded")
		dlg = wx.DirDialog(self, lang.getstr("dialog.set_profile_save_path", 
											 profile_name), 
						   defaultPath=defaultPath)
		dlg.Center(wx.BOTH)
		if dlg.ShowModal() == wx.ID_OK:
			path = dlg.GetPath()
			profile_save_dir = os.path.join(path, profile_name)
			if not os.path.isdir(profile_save_dir):
				try:
					os.makedirs(profile_save_dir)
				except:
					pass
			if not waccess(os.path.join(profile_save_dir, profile_name),
						   os.W_OK):
				show_result_dialog(Error(lang.getstr("error.access_denied.write",
													 path)), self)
				return
			try:
				os.rmdir(profile_save_dir)
			except:
				pass
			setcfg("profile.save_path", path)
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
		info = ["%nn	" + lang.getstr("computer.name"),
				"%dn	" + lang.getstr("display"),
				"%dns	" + lang.getstr("display_short"),
				"%dnw	" + lang.getstr("display") + " (" +
							lang.getstr("windows_only") + ")",
				"%dnws	" + lang.getstr("display_short") + " (" +
							lang.getstr("windows_only") + ")",
				"%ds	" + lang.getstr("edid.serial") + " (" +
							lang.getstr("if_available") + ")",
				"%crc32	" + lang.getstr("edid.crc32") + " (" +
							lang.getstr("if_available") + ")",
				"%in	" + lang.getstr("instrument"),
				"%im	" + lang.getstr("measurement_mode"),
				"%wp	" + lang.getstr("whitepoint"),
				"%cb	" + lang.getstr("calibration.luminance"),
				"%cB	" + lang.getstr("calibration.black_luminance"),
				"%cg	" + lang.getstr("trc"),
				"%ca	" + lang.getstr("calibration.ambient_viewcond_adjust"),
				"%cf	" + lang.getstr("calibration.black_output_offset"),
				"%ck	" + lang.getstr("calibration.black_point_correction")]
		if defaults["calibration.black_point_rate.enabled"]:
			info.append("%cA	" + lang.getstr("calibration.black_point_rate"))
		info += ["%cq	" + lang.getstr("calibration.speed"),
				 "%pq	" + lang.getstr("profile.quality"),
				 "%pt	" + lang.getstr("profile.type"),
				 "%tpa	" + lang.getstr("testchart.info")]
		return lang.getstr("profile.name.placeholders") + "\n\n" + \
			   "\n".join(info)

	def create_profile_handler(self, event, path=None, skip_ti3_check=False):
		""" Create profile from existing measurements """
		if not check_set_argyll_bin():
			return
		if path is None:
			selectedpaths = []
			# select measurement data (ti3 or profile)
			defaultDir, defaultFile = get_verified_path("last_ti3_path")
			dlg = wx.FileDialog(self, lang.getstr("create_profile"), 
								defaultDir=defaultDir, defaultFile=defaultFile, 
								wildcard=lang.getstr("filetype.icc_ti3") + 
										 "|*.icc;*.icm;*.ti3", 
								style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST |
									  wx.FD_MULTIPLE)
			dlg.Center(wx.BOTH)
			result = dlg.ShowModal()
			if result == wx.ID_OK:
				selectedpaths = dlg.GetPaths()
			dlg.Destroy()
		elif path:
			selectedpaths = [path]
		collected_ti3s = []
		for path in selectedpaths:
			if not os.path.exists(path):
				InfoDialog(self, msg=lang.getstr("file.missing", path), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				return
			tags = OrderedDict()
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
				# Preserve custom tags
				for tagname in ("mmod", "meta"):
					if tagname in profile.tags:
						tags[tagname] = profile.tags[tagname]
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
			collected_ti3s.append((path, ti3_lines))
		if collected_ti3s:
			if len(collected_ti3s) > 1:
				source_filename = os.path.splitext(defaults["last_ti3_path"])[0]
				source_ext = ".ti3"
			path = collected_ti3s[0][0]
			is_tmp = False
			tmp_working_dir = self.worker.tempdir
			if tmp_working_dir:
				if sys.platform == "win32":
					if path.lower().startswith(tmp_working_dir.lower()):
						is_tmp = True
				elif path.startswith(tmp_working_dir):
					is_tmp = True
			if is_tmp:
				defaultDir, defaultFile = get_verified_path("last_ti3_path")
			else:
				defaultDir, defaultFile = os.path.split(path)
				setcfg("last_ti3_path", path)
			# let the user choose a location for the profile
			dlg = wx.FileDialog(self, lang.getstr("save_as"), 
								defaultDir, 
								os.path.basename(source_filename) + 
								profile_ext, 
								wildcard=lang.getstr("filetype.icc") + 
										 "|*" + profile_ext, 
								style=wx.SAVE | wx.FD_OVERWRITE_PROMPT)
			dlg.Center(wx.BOTH)
			result = dlg.ShowModal()
			profile_save_path = os.path.split(dlg.GetPath())
			profile_save_path = os.path.join(profile_save_path[0], 
											 make_argyll_compatible_path(profile_save_path[1]))
			dlg.Destroy()
			if result == wx.ID_OK:
				if not waccess(profile_save_path, os.W_OK):
					show_result_dialog(Error(lang.getstr("error.access_denied.write",
														 profile_save_path)),
									   self)
					return
				filename, ext = os.path.splitext(profile_save_path)
				if ext.lower() not in (".icc", ".icm"):
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
				setcfg("last_cal_or_icc_path", profile_save_path)
				setcfg("last_icc_path", profile_save_path)
				# get filename and extension of target file
				profile_name = os.path.basename(
					os.path.splitext(profile_save_path)[0])
				# create temporary working dir
				tmp_working_dir = self.worker.create_tempdir()
				if isinstance(tmp_working_dir, Exception):
					self.worker.wrapup(False)
					show_result_dialog(tmp_working_dir, self)
					return
				# Copy ti3 to temp dir
				ti3_tmp_path = os.path.join(tmp_working_dir, 
											make_argyll_compatible_path(profile_name + 
																		".ti3"))
				if len(collected_ti3s) > 1:
					# Collect files for averaging
					collected_paths = []
					for ti3_path, ti3_lines in collected_ti3s:
						collected_path = os.path.join(tmp_working_dir,
													  os.path.basename(ti3_path))
						with open(collected_path, "w") as ti3_file:
							ti3_file.write("\n".join(ti3_lines))
						collected_paths.append(collected_path)
					# Average the TI3 files
					args = ["-v"] + collected_paths + [ti3_tmp_path]
					cmd = get_argyll_util("average")
					result = self.worker.exec_cmd(cmd, args, capture_output=True,
												  skip_scripts=True)
					for collected_path in collected_paths:
						os.remove(collected_path)
					if isinstance(result, Exception) or not result:
						self.worker.wrapup(False)
						show_result_dialog(result or
										   Error("\n".join(self.worker.errors)), self)
						return
					path = ti3_tmp_path
				self.worker.options_dispcal = []
				self.worker.options_targen = []
				display_name = None
				display_manufacturer = None
				try:
					if source_ext.lower() == ".ti3":
						if path != ti3_tmp_path:
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
						if "dmnd" in profile.tags:
							display_manufacturer = profile.getDeviceManufacturerDescription()
						if is_tmp and path != ti3_tmp_path:
							profile.close()
							os.remove(path)
					ti3 = CGATS.CGATS(ti3_tmp_path)
					if ti3.queryv1("COLOR_REP") and \
					   ti3.queryv1("COLOR_REP")[:3] == "RGB":
						self.worker.options_targen = ["-d3"]
				except Exception, exception:
					handle_error(u"Error - temporary .ti3 file could not be "
								 u"created: " + safe_unicode(exception), parent=self)
					self.worker.wrapup(False)
					return
				setcfg("calibration.file.previous", None)
				safe_print("-" * 80)
				if (not skip_ti3_check and
					not self.measurement_file_check_confirm(ti3)):
					self.worker.wrapup(False)
					return
				# Run colprof
				self.worker.interactive = False
				self.worker.start(
					self.profile_finish, self.worker.create_profile, ckwargs={
						"profile_path": profile_save_path, 
						"failure_msg": lang.getstr(
							"error.profile.file_not_created")}, 
					wkwargs={"dst_path": profile_save_path, 
							 "display_name": display_name,
							 "display_manufacturer": display_manufacturer,
							 "tags": tags}, 
					progress_msg=lang.getstr("create_profile"))
	
	def create_profile_from_edid(self, event):
		edid = self.worker.get_display_edid()
		defaultFile = edid.get("monitor_name",
							   edid.get("ascii",
										str(edid["product_id"]))) + profile_ext
		defaultDir = get_verified_path(None, 
									   os.path.join(getcfg("profile.save_path"), 
													defaultFile))[0]
		# let the user choose a location for the profile
		dlg = wx.FileDialog(self, lang.getstr("save_as"), defaultDir, 
							defaultFile, wildcard=lang.getstr("filetype.icc") + 
												  "|*" + profile_ext, 
							style=wx.SAVE | wx.FD_OVERWRITE_PROMPT)
		dlg.Center(wx.BOTH)
		result = dlg.ShowModal()
		profile_save_path = os.path.split(dlg.GetPath())
		profile_save_path = os.path.join(profile_save_path[0], 
										 make_argyll_compatible_path(profile_save_path[1]))
		dlg.Destroy()
		if result == wx.ID_OK:
			if not waccess(profile_save_path, os.W_OK):
				show_result_dialog(Error(lang.getstr("error.access_denied.write",
													 profile_save_path)),
								   self)
				return
			profile = ICCP.ICCProfile.from_edid(edid)
			try:
				profile.write(profile_save_path)
			except Exception, exception:
				InfoDialog(self, msg=safe_unicode(exception), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
			else:
				if getcfg("profile.create_gamut_views"):
					safe_print("-" * 80)
					safe_print(lang.getstr("gamut.view.create"))
					self.worker.interactive = False
					self.worker.start(self.create_profile_from_edid_finish,
									  self.worker.calculate_gamut, 
									  cargs=(profile, ),
									  wargs=(profile_save_path, ),
									  progress_msg=lang.getstr("gamut.view.create"), 
									  resume=False)
				else:
					self.create_profile_from_edid_finish(True, profile)
	
	def create_profile_from_edid_finish(self, result, profile):
		if isinstance(result, Exception):
			show_result_dialog(result, self)
		elif result:
			if isinstance(result, tuple):
				profile.set_gamut_metadata(result[0], result[1])
				prefixes = profile.tags.meta.getvalue("prefix", "", None).split(",")
				# Set license
				profile.tags.meta["License"] = getcfg("profile.license")
				# Set device ID
				device_id = self.worker.get_device_id(quirk=True)
				if device_id:
					profile.tags.meta["MAPPING_device_id"] = device_id
					prefixes.append("MAPPING_")
					profile.tags.meta["prefix"] = ",".join(prefixes)
				profile.calculateID()
				safe_print("-" * 80)
			try:
				profile.write()
			except Exception, exception:
				show_result_dialog(exception, self)
				return
			self.profile_finish(True, profile.fileName)
	
	def create_profile_name(self):
		"""
		Replace placeholders in profile name with values from configuration
		
		"""
		profile_name = self.profile_name_textctrl.GetValue()
		
		# Computername
		if "%nn" in profile_name:
			profile_name = profile_name.replace("%nn",
												safe_unicode(platform.node()) or
												"\0")

		# Windows display name (EnumDisplayDevices / DeviceString)
		if "%dnws" in profile_name:
			display_win32_short = self.worker.get_display_name_short(False,
																	 False)
			profile_name = profile_name.replace("%dnws", display_win32_short or
														 "\0")
		if "%dnw" in profile_name:
			display_win32 = self.worker.get_display_name(True, False)
			profile_name = profile_name.replace("%dnw", display_win32 or "\0")

		# EDID
		if "%ds" in profile_name or "%crc32" in profile_name:
			edid = self.worker.get_display_edid()
		# Serial
		if "%ds" in profile_name:
			serial = edid.get("serial_ascii", hex(edid.get("serial_32", 0))[2:])
			if serial and serial not in ("0", "1010101", "fffffff"):
				profile_name = profile_name.replace("%ds", serial)
			else:
				profile_name = profile_name.replace("%ds", "\0")
		# CRC32
		if "%crc32" in profile_name:
			if edid.get("edid"):
				profile_name = profile_name.replace("%crc32",
													"%X" %
													(crc32(edid["edid"])
													 & 0xFFFFFFFF))
			else:
				profile_name = profile_name.replace("%crc32", "\0")

		# Display name
		if "%dns" in profile_name:
			display_short = self.worker.get_display_name_short(False, True)
			profile_name = profile_name.replace("%dns", display_short or "\0")
		if "%dn" in profile_name:
			display = self.worker.get_display_name(True, True)
			profile_name = profile_name.replace("%dn", display or "\0")

		# Instrument name
		if "%in" in profile_name:
			instrument = self.comport_ctrl.GetStringSelection()
			profile_name = profile_name.replace("%in", instrument or "\0")

		# Measurement mode
		if "%im" in profile_name:
			mode = ""
			measurement_mode = self.get_measurement_mode()
			if measurement_mode:
				if "c" in measurement_mode:
					mode += lang.getstr("measurement_mode.refresh")
				elif "l" in measurement_mode:
					mode += lang.getstr("measurement_mode.lcd")
				if "p" in measurement_mode:
					if mode:
						mode += "-"
					mode += lang.getstr("projector")
				if "V" in measurement_mode:
					if mode:
						mode += "-"
					mode += lang.getstr("measurement_mode.adaptive")
				if "H" in measurement_mode:
					if mode:
						mode += "-"
					mode += lang.getstr("measurement_mode.highres")
			else:
				mode += lang.getstr("default")
			profile_name = profile_name.replace("%im", mode)

		# Whitepoint
		if "%wp" in profile_name:
			whitepoint = self.get_whitepoint()
			whitepoint_locus = self.get_whitepoint_locus()
			if isinstance(whitepoint, str):
				if whitepoint.find(",") < 0:
					if whitepoint_locus == "t":
						whitepoint = "D" + whitepoint
					else:
						whitepoint += "K"
				else:
					whitepoint = "x ".join(whitepoint.split(",")) + "y"
			profile_name = profile_name.replace("%wp", whitepoint or "\0")

		# Luminance
		if "%cb" in profile_name:
			luminance = self.get_luminance()
			profile_name = profile_name.replace("%cb", 
												"\0" if 
												luminance is None
												else luminance + u"cdm²")

		# Black luminance
		if "%cB" in profile_name:
			black_luminance = self.get_black_luminance()
			profile_name = profile_name.replace("%cB", 
												"\0" if 
												black_luminance is None
												else black_luminance + u"cdm²")

		# TRC / black output offset
		if "%cg" in profile_name or "%cf" in profile_name:
			black_output_offset = self.get_black_output_offset()

		# TRC
		if "%cg" in profile_name:
			trc = self.get_trc()
			trc_type = self.get_trc_type()
			bt1886 = (trc == "2.4" and trc_type == "G" and
					  black_output_offset == "0")
			if bt1886:
				trc = "Rec. 1886"
			elif trc not in ("l", "709", "s", "240"):
				if trc_type == "G":
					trc += " (%s)" % lang.getstr("trc.type.absolute").lower()
			else:
				trc = strtr(trc, {"l": "L", 
								  "709": "Rec. 709", 
								  "s": "sRGB", 
								  "240": "SMPTE240M"})
			profile_name = profile_name.replace("%cg", trc)

		# Ambient adjustment
		if "%ca" in profile_name:
			ambient = self.get_ambient()
			profile_name = profile_name.replace("%ca", "\0" if ambient is None
													   else ambient + "lx")

		# Black output offset
		if "%cf" in profile_name:
			f = int(float(black_output_offset) * 100)
			profile_name = profile_name.replace("%cf", "%i%%" % f)

		# Black point correction / rate
		if "%ck" in profile_name or "%cA" in profile_name:
			black_point_correction = self.get_black_point_correction()

		# Black point correction
		if "%ck" in profile_name:
			k = int(float(black_point_correction) * 100)
			profile_name = profile_name.replace("%ck", (str(k) + "% " if k > 0 and 
														k < 100 else "") + 
													   (lang.getstr("neutral") if 
														k > 0 else "\0").lower())

		# Black point rate
		if "%cA" in profile_name:
			black_point_rate = self.get_black_point_rate()
			if black_point_rate and float(black_point_correction) < 1:
				profile_name = profile_name.replace("%cA", black_point_rate)
			else:
				profile_name = profile_name.replace("%cA", "\0")

		# Calibration / profile quality
		if "%cq" in profile_name or "%pq" in profile_name:
			calibration_quality = self.get_calibration_quality()
			profile_quality = getcfg("profile.quality")
			aspects = {
				"c": calibration_quality,
				"p": profile_quality
			}
			msgs = {
				"u": "VS", 
				"h": "S", 
				"m": "M", 
				"l": "F", 
				"v": "VF"
			}
			quality = {}
			if "%cq" in profile_name:
				quality["c"] = msgs[aspects["c"]]
			if "%pq" in profile_name:
				quality["p"] = msgs[aspects["p"]]
			if len(quality) == 2 and quality["c"] == quality["p"]:
				profile_name = re.sub("%cq\W*%pq", quality["c"], profile_name)
			for q in quality:
				profile_name = profile_name.replace("%%%sq" % q, quality[q])

		# Profile type
		if "%pt" in profile_name:
			profile_type = {
				"G": "1xGamma+MTX",
				"g": "3xGamma+MTX",
				"l": "LabLUT",
				"S": "1xCurve+MTX",
				"s": "3xCurve+MTX",
				"X": "XYZLUT+MTX",
				"x": "XYZLUT"
			}.get(self.get_profile_type())
			profile_name = profile_name.replace("%pt", profile_type or "\0")

		# Amount of test patches
		if "%tpa" in profile_name:
			profile_name = profile_name.replace("%tpa", 
												self.testchart_patches_amount.GetLabel())

		# Date / time
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
			if "%%%s" % directive in profile_name:
				try:
					profile_name = profile_name.replace("%%%s" % directive, 
														strftime("%%%s" % 
																 directive))
				except UnicodeDecodeError:
					pass

		# All whitespace to space
		profile_name = re.sub("\s", " ", profile_name)

		# Get rid of inserted NULL bytes
		# Try to keep spacing intact
		if "\0" in profile_name:
			profile_name = re.sub("^(\0[_\- ]?)+|([_\- ]?\0)+$", "", profile_name)
			# Surrounded by underscores
			while "_\0" in profile_name or "\0_" in profile_name:
				while re.search("_\0+_", profile_name):
					profile_name = re.sub("_\0+_", "_", profile_name)
				profile_name = re.sub("_\0+", "_", profile_name)
				profile_name = re.sub("\0+_", "_", profile_name)
			# Surrounded by dashes
			while "-\0" in profile_name or "\0-" in profile_name:
				while re.search("-\0+-", profile_name):
					profile_name = re.sub("-\0+-", "-", profile_name)
				profile_name = re.sub("-\0+", "-", profile_name)
				profile_name = re.sub("\0+-", "-", profile_name)
			# Surrounded by whitespace
			while " \0" in profile_name or "\0 " in profile_name:
				while re.search(" \0+ ", profile_name):
					profile_name = re.sub(" \0+ ", " ", profile_name)
				profile_name = re.sub(" \0+", " ", profile_name)
				profile_name = re.sub("\0+ ", " ", profile_name)
			profile_name = re.sub("\0+", "", profile_name)

		# Get rid of characters considered invalid for filenames and shorten
		# to a length of max 255 chars
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
		""" Return the measurement mode as string.
		
		Examples
		
		Argyll options -V -H (adaptive highres mode)
		Returned string 'VH'
		
		Argyll option -yl
		Returned string 'l'
		
		Argyll options -p -H (projector highres mode)
		Returned string 'pH'
		
		"""
		return self.measurement_modes_ab.get(self.get_instrument_type(), {}).get(
			self.measurement_mode_ctrl.GetSelection())

	def get_profile_type(self):
		return self.profile_types_ab.get(self.profile_type_ctrl.GetSelection(),
										 getcfg("profile.type"))

	def get_whitepoint(self):
		if self.whitepoint_ctrl.GetSelection() == 0:
			# Native
			return None
		elif self.whitepoint_ctrl.GetSelection() == 1:
			# Color temperature in kelvin
			return str(stripzeros(
				self.whitepoint_colortemp_textctrl.GetValue().replace(",", 
																	  ".")))
		elif self.whitepoint_ctrl.GetSelection() == 2:
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
		if self.luminance_ctrl.GetSelection() == 0:
			return None
		else:
			return str(stripzeros(
				self.luminance_textctrl.GetValue().replace(",", ".")))

	def get_black_luminance(self):
		if self.black_luminance_ctrl.GetSelection() == 0:
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
			return str(self.black_point_rate_floatctrl.GetValue())
		else:
			return None

	def get_trc_type(self):
		if ((self.trc_type_ctrl.GetSelection() == 1 and
			 self.trc_ctrl.GetSelection() == 0) or
			self.trc_ctrl.GetSelection() == 3):
			return "G"
		else:
			return "g"

	def get_trc(self):
		if self.trc_ctrl.GetSelection() == 0:
			return str(stripzeros(self.trc_textctrl.GetValue().replace(",", 
																	   ".")))
		elif self.trc_ctrl.GetSelection() == 1:
			return "l"
		elif self.trc_ctrl.GetSelection() == 2:
			return "709"
		elif self.trc_ctrl.GetSelection() == 3:
			# BT.1886
			return "2.4"
		elif self.trc_ctrl.GetSelection() == 4:
			return "240"
		elif self.trc_ctrl.GetSelection() == 5:
			return "s"
		else:
			raise ValueError("Invalid TRC selection")

	def get_calibration_quality(self):
		return self.quality_ab[self.calibration_quality_ctrl.GetValue()]

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
		if force or (lang.getstr(os.path.basename(path)) in [""] +
					 self.default_testchart_names) or not os.path.isfile(path):
			if (not force and lang.getstr(os.path.basename(path)) in [""] +
				self.default_testchart_names):
				ti1 = os.path.basename(path)
			else:
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
			self.set_default_testchart(force=True)
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
			try:
				ti1_1 = verify_ti1_rgb_xyz(ti1)
			except CGATS.CGATSError, exception:
				msg = {CGATS.CGATSKeyError: lang.getstr("error.testchart.missing_fields", 
														(path, 
														 "RGB_R, RGB_G, RGB_B, "
														 " XYZ_X, XYZ_Y, XYZ_Z"))}.get(exception.__class__,
																					   lang.getstr("error.testchart.invalid",
																								   path) + 
																					   "\n" + 
																					   lang.getstr(safe_str(exception)))
				InfoDialog(self, 
						   msg=msg, 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				self.set_default_testchart(force=True)
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
			self.set_default_testchart(force=True)
		else:
			if hasattr(self, "tcframe") and \
			   self.tcframe.IsShownOnScreen() and \
			   (not hasattr(self.tcframe, "ti1") or 
				getcfg("testchart.file") != self.tcframe.ti1.filename):
				self.tcframe.tc_load_cfg_from_ti1()
		if is_ccxx_testchart():
			measurement_mode = None
			if (self.worker.get_instrument_name() == "ColorHug"
				and getcfg("measurement_mode") not in ("F", "R")):
				# Automatically set factory measurement mode if not already
				# factory or raw measurement mode
				measurement_mode = "F"
			elif (self.worker.get_instrument_name() == "ColorMunki Smile"
				and getcfg("measurement_mode") != "f"):
				# Automatically set LCD measurement mode if not already
				# LCD CCFL measurement mode
				measurement_mode = "f"
			elif (self.worker.get_instrument_name() == "Colorimtre HCFR"
				and getcfg("measurement_mode") != "R"):
				# Automatically set raw measurement mode if not already
				# raw measurement mode
				measurement_mode = "R"
			elif (self.worker.get_instrument_name() == "Spyder4"
				and getcfg("measurement_mode") not in ("l", "c")):
				# Automatically set LCD measurement mode if not already
				# LCD or refresh measurement mode
				measurement_mode = "l"
			if measurement_mode:
				setcfg("measurement_mode.backup", getcfg("measurement_mode"))
				setcfg("measurement_mode", measurement_mode)
				self.update_measurement_mode()
		else:
			self.restore_measurement_mode()
		self.update_colorimeter_correction_matrix_ctrl()
		if not self.updatingctrls:
			self.update_main_controls()

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
			self.testcharts[i] = os.path.join(*chart)
			self.testchart_names += [lang.getstr(chart[-1])]
			i += 1
		return self.testchart_names

	def set_argyll_bin_handler(self, event):
		""" Set Argyll CMS binary executables directory """
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
		if event:
			# Explicitly called from menu
			enumerate_ports = True
		else:
			# Use configured value
			enumerate_ports = getcfg("enumerate_ports.auto")
		if False:
			self.thread = delayedresult.startWorker(self.check_update_controls_consumer, 
													self.worker.enumerate_displays_and_ports, 
													cargs=(argyll_bin_dir, argyll_version, 
														   displays, comports), 
													wargs=(silent, ),
													wkwargs={"enumerate_ports":
															 enumerate_ports})
		else:
			self.worker.enumerate_displays_and_ports(silent,
													 enumerate_ports=enumerate_ports)
			return self.check_update_controls_consumer(True, argyll_bin_dir,
													   argyll_version, displays, 
													   comports)
	
	def check_update_controls_consumer(self, result, argyll_bin_dir,
									   argyll_version, displays, comports):
		if argyll_bin_dir != self.worker.argyll_bin_dir or \
		   argyll_version != self.worker.argyll_version:
			self.update_measurement_modes()
			if comports == self.worker.instruments:
				self.update_colorimeter_correction_matrix_ctrl()
			self.update_black_point_rate_ctrl()
			self.update_drift_compensation_ctrls()
			self.update_profile_type_ctrl()
			self.profile_type_ctrl.SetSelection(
				self.profile_types_ba.get(getcfg("profile.type"), 
				self.profile_types_ba.get(defaults["profile.type"])))
			if hasattr(self, "aboutdialog"):
				if self.aboutdialog.IsShownOnScreen():
					self.aboutdialog_handler(None)
			if hasattr(self, "gamapframe"):
				visible = self.gamapframe.IsShownOnScreen()
				self.gamapframe.Close()
				self.gamapframe.Destroy()
				del self.gamapframe
				if visible:
					self.gamap_btn_handler(None)
			if getattr(self, "lut3dframe", None):
				visible = self.lut3dframe.IsShownOnScreen()
				self.lut3dframe.Close()
				self.lut3dframe.Destroy()
				del self.lut3dframe
				if visible:
					self.lut3d_create_handler(None)
			if getattr(self, "reportframe", None):
				visible = self.reportframe.IsShownOnScreen()
				self.reportframe.Close()
				self.reportframe.Destroy()
				del self.reportframe
				if visible:
					self.measurement_report_create_handler(None)
			if hasattr(self, "tcframe"):
				visible = self.tcframe.IsShownOnScreen()
				self.tcframe.tc_close_handler()
				self.tcframe.Destroy()
				del self.tcframe
				if visible:
					self.create_testchart_btn_handler(None)
		if displays != self.worker.displays:
			self.update_displays(update_ccmx_items=True)
			if verbose >= 1: safe_print(lang.getstr("display_detected"))
		if comports != self.worker.instruments:
			self.update_comports()
			if verbose >= 1: safe_print(lang.getstr("comport_detected"))
		if displays != self.worker.displays or \
		   comports != self.worker.instruments:
			if self.IsShownOnScreen():
				self.update_menus()
			self.update_main_controls()
			return True
		return False

	def plugplay_timer_handler(self, event):
		if debug >= 9:
			safe_print("[D] plugplay_timer_handler")
		if (getcfg("enumerate_ports.auto") and not self.worker.is_working() and
			(not hasattr(self, "tcframe") or 
			 not self.tcframe.worker.is_working())):
			self.check_update_controls(silent=True)

	def load_cal_handler(self, event, path=None, update_profile_name=True, 
						 silent=False, load_vcgt=True):
		""" Load settings and calibration """
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
					if not cal in self.recent_cals:
						self.recent_cals.append(cal)
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
			update_ccmx_items = True
			if ext.lower() in (".icc", ".icm"):
				setcfg("last_icc_path", path)
				(options_dispcal, 
				 options_colprof) = get_options_from_profile(profile)
				# Get and set the display
				# First try to find the correct display by comparing
				# the model (if present)
				display_name = profile.getDeviceModelDescription()
				# Second try to find the correct display by comparing
				# the EDID hash (if present)
				edid_md5 = profile.tags.get("meta", {}).get("EDID_md5",
															{}).get("value")
				if display_name or edid_md5:
					display_name_indexes = []
					edid_md5_indexes = []
					for i, edid in enumerate(self.worker.display_edid):
						if display_name in (edid.get("monitor_name", False),
											self.worker.display_names[i]):
							display_name_indexes.append(i)
						if edid_md5 == edid.get("monitor_name", False):
							edid_md5_indexes.append(i)
					if len(display_name_indexes) == 1:
						display_index = display_name_indexes[0]
						safe_print("Found display device matching model "
								   "description at index #%i" % display_index)
					elif len(edid_md5_indexes) == 1:
						display_index = edid_md5_indexes[0]
						safe_print("Found display device matching EDID MD5 "
								   "at index #%i" % display_index)
					else:
						# We got several matches. As we can't be sure which
						# is the right one, do nothing.
						display_index = None
					if display_index is not None:
						# Found it
						setcfg("display.number", display_index + 1)
						self.get_set_display()
				# Get and set the instrument
				instrument_id = profile.tags.get("meta",
												 {}).get("MEASUREMENT_device",
														 {}).get("value")
				if instrument_id:
					for i, instrument in enumerate(self.worker.instruments):
						if instrument.lower() == instrument_id:
							# Found it
							setcfg("comport.number", i + 1)
							self.update_comports()
							# No need to update ccmx items in update_controls,
							# as comport_ctrl_handler took care of it
							update_ccmx_items = False
							break
			else:
				try:
					(options_dispcal, 
					 options_colprof) = get_options_from_cal(path)
				except (IOError, CGATS.CGATSError), exception:
					InfoDialog(self, msg=lang.getstr("calibration.file.invalid") + 
										 "\n" + path, 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
					return
			if options_dispcal or options_colprof:
				if debug:
					safe_print("[D] options_dispcal:", options_dispcal)
				if debug:
					safe_print("[D] options_colprof:", options_colprof)
				ccxxsetting = getcfg("colorimeter_correction_matrix_file").split(":", 1)[0]
				ccmx = None
				# Parse options
				if options_dispcal:
					# Restore defaults
					self.restore_defaults_handler(
						include=("calibration", 
								 "drift_compensation", 
								 "measure.darken_background", 
								 "trc", 
								 "whitepoint"), 
						exclude=("calibration.black_point_correction_choice.show", 
								 "calibration.update", 
								 "calibration.use_video_lut",
								 "measure.darken_background.show_warning", 
								 "trc.should_use_viewcond_adjust.show_msg"))
					self.worker.options_dispcal = ["-" + arg for arg 
												   in options_dispcal]
					for o in options_dispcal:
						if o[0] == "d" and o[1:] in ("web", "madvr"):
							# Special case web and madvr so it can be used in
							# preset templates which are TI3 files
							for i, display_name in enumerate(self.worker.display_names):
								if (display_name.lower() == o[1:] and
									getcfg("display.number") != i + 1):
									# Found it
									setcfg("display.number", i + 1)
									self.get_set_display()
									break
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
								setcfg("whitepoint.colortemp",
									   int(float(o[1:])))
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
							setcfg("calibration.black_point_correction.auto",
								   int(stripzeros(o[1:]) < 0))
							if stripzeros(o[1:]) >= 0:
								setcfg("calibration.black_point_correction",
									   o[1:])
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
						if o[0:2] == "YA":
							setcfg("measurement_mode.adaptive", 0)
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
						if o[0] == "X":
							o = o.split(None, 1)
							ccmx = o[-1][1:-1]
							if not os.path.isabs(ccmx):
								ccmx = os.path.join(os.path.dirname(path), ccmx)
							# Need to update ccmx items again even if
							# comport_ctrl_handler already did
							update_ccmx_items = True
							continue
						if o[0] == "I":
							if "b" in o[1:]:
								setcfg("drift_compensation.blacklevel", 1)
							if "w" in o[1:]:
								setcfg("drift_compensation.whitelevel", 1)
							continue
				if not ccmx:
					ccxx = (glob.glob(os.path.join(os.path.dirname(path), "*.ccmx")) or
							glob.glob(os.path.join(os.path.dirname(path), "*.ccss")))
					if ccxx and len(ccxx) == 1:
						ccmx = ccxx[0]
						update_ccmx_items = True
				if ccmx:
					setcfg("colorimeter_correction_matrix_file",
						   "%s:%s" % (ccxxsetting, ccmx))
				if options_colprof:
					# restore defaults
					self.restore_defaults_handler(
						include=("profile", "gamap_"), 
						exclude=("profile.update", "profile.name",
								 "gamap_default_intent"))
					for o in options_colprof:
						if o[0] == "q":
							setcfg("profile.quality", o[1])
							continue
						if o[0] == "b":
							setcfg("profile.quality.b2a", o[1] or "l")
							continue
						if o[0] == "a":
							setcfg("profile.type", o[1])
							continue
						if o[0] in ("s", "S"):
							o = o.split(None, 1)
							setcfg("gamap_profile", o[-1][1:-1])
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
						if o[0] == "t":
							setcfg("gamap_perceptual_intent", o[1:])
							continue
						if o[0] == "T":
							setcfg("gamap_saturation_intent", o[1:])
							continue
				setcfg("calibration.file", path)
				if "CTI3" in ti3_lines:
					if debug:
						safe_print("[D] load_cal_handler testchart.file:", path)
					setcfg("testchart.file", path)
				if 'USE_BLACK_POINT_COMPENSATION "YES"' in ti3_lines:
					setcfg("profile.black_point_compensation", 1)
				elif 'USE_BLACK_POINT_COMPENSATION "NO"' in ti3_lines:
					setcfg("profile.black_point_compensation", 0)
				self.update_controls(
					update_profile_name=update_profile_name,
					update_ccmx_items=update_ccmx_items)
				writecfg()

				if ext.lower() in (".icc", ".icm"):
					if load_vcgt:
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
					if not load_vcgt:
						msg = lang.getstr("settings_loaded.cal")
					else:
						# load calibration into lut
						self.load_cal(cal=path, silent=True)
						msg = lang.getstr("settings_loaded.cal_and_lut")
				else:
					msg = lang.getstr("settings_loaded.profile")

				if not silent:
					InfoDialog(self, msg=msg + "\n" + path, ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-information"))
				return
			elif ext.lower() in (".icc", ".icm"):
				sel = self.calibration_file_ctrl.GetSelection()
				if len(self.recent_cals) > sel and self.recent_cals[sel] == path:
					self.recent_cals.remove(self.recent_cals[sel])
					self.calibration_file_ctrl.Delete(sel)
					cal = getcfg("calibration.file") or ""
					if not cal in self.recent_cals:
						self.recent_cals.append(cal)
					# The case-sensitive index could fail because of 
					# case insensitive file systems, e.g. if the 
					# stored filename string is 
					# "C:\Users\Name\AppData\dispcalGUI\storage\MyFile"
					# but the actual filename is 
					# "C:\Users\Name\AppData\dispcalGUI\storage\myfile"
					# (maybe because the user renamed the file)
					idx = index_fallback_ignorecase(self.recent_cals, cal)
					self.calibration_file_ctrl.SetSelection(idx)
				if load_vcgt:
					# load calibration into lut
					self.load_cal(cal=path, silent=True)
				if not silent:
					InfoDialog(self, msg=lang.getstr("no_settings") + 
										 "\n" + path, 
							   ok=lang.getstr("ok"), 
							   bitmap=geticon(32, "dialog-error"))
				return

			# Old .cal file without ARGYLL_DISPCAL_ARGS section
			
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
						setcfg("calibration.black_point_correction.auto",
							   int(stripzeros(value) < 0))
						if stripzeros(value) >= 0:
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

			setcfg("calibration.file", path)
			self.update_controls(update_profile_name=update_profile_name)
			if "CTI3" in ti3_lines:
				if debug:
					safe_print("[D] load_cal_handler testchart.file:", path)
				setcfg("testchart.file", path)
			writecfg()
			if load_vcgt:
				# load calibration into lut
				self.load_cal(silent=True)
			if len(settings) == 0:
				msg = lang.getstr("no_settings")
			else:
				msg = lang.getstr("settings_loaded", ", ".join(settings))
			if not silent:
				InfoDialog(self, msg=msg + "\n" + path, 
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
				if (fn.startswith(os.path.splitext(os.path.basename(cal))[0]) or
					ext.lower() in (".ccss", ".ccmx")):
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
				update_colorimeter_correction_matrix_ctrl_items = False
				update_testcharts = False
				for path in delete_related_files:
					if path not in orphan_related_files:
						if (os.path.splitext(path)[1].lower() in (".ccss",
																  ".ccmx")):
							self.delete_colorimeter_correction_matrix_ctrl_item(path)
							update_colorimeter_correction_matrix_ctrl_items = True
						elif path in self.testcharts:
							update_testcharts = True
				if update_testcharts:
					self.set_testcharts()
				self.update_controls(False,
									 update_colorimeter_correction_matrix_ctrl_items)
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
			self.aboutdialog, -1, label=domain, 
			URL="http://%s" % domain)]
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
			lauthor = lang.ldict[lcode].get("!author", "")
			language = lang.ldict[lcode].get("!language", "")
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
		readme = get_data_path("README.html")
		if readme:
			launch_file(readme)
	
	def license_handler(self, event):
		license = get_data_path("LICENSE.txt")
		if not license:
			# Debian
			license = "/usr/share/common-licenses/GPL-3"
		if license and os.path.isfile(license):
			launch_file(license)
	
	def help_support_handler(self, event):
		launch_file("http://%s/#help" % domain)
	
	def bug_report_handler(self, event):
		launch_file("http://%s/#reportbug" % domain)
	
	def app_update_check_handler(self, event, silent=False):
		if not hasattr(self, "app_update_check") or \
		   not self.app_update_check.isAlive():
			self.app_update_check = threading.Thread(target=app_update_check, 
													 args=(self, silent))
			self.app_update_check.start()
	
	def app_auto_update_check_handler(self, event):
		setcfg("update_check", 
			   int(self.menuitem_app_auto_update_check.IsChecked()))

	def auto_enumerate_ports_handler(self, event):
		setcfg("enumerate_ports.auto", 
			   int(self.menuitem_auto_enumerate_ports.IsChecked()))

	def infoframe_toggle_handler(self, event=None, show=None):
		if show is None:
			show = not self.infoframe.IsShownOnScreen()
		setcfg("log.show", int(show))
		self.infoframe.Show(show)
		self.menuitem_show_log.Check(show)
		self.menuitem_log_autoshow.Enable(not show)
	
	def infoframe_autoshow_handler(self, event):
		setcfg("log.autoshow", int(self.menuitem_log_autoshow.IsChecked()))

	def HideAll(self):
		self.stop_timers()
		if hasattr(self, "gamapframe"):
			self.gamapframe.Hide()
		if hasattr(self, "aboutdialog"):
			self.aboutdialog.Hide()
		if hasattr(self, "extra_args"):
			self.extra_args.Hide()
		self.infoframe.Hide()
		if hasattr(self, "tcframe"):
			self.tcframe.Hide()
		if getattr(self, "lut_viewer", None) and \
		   self.lut_viewer.IsShownOnScreen():
			self.lut_viewer.Hide()
		if getattr(self, "lut3dframe", None):
			self.lut3dframe.Hide()
		if getattr(self, "reportframe", None):
			self.reportframe.Hide()
		if getattr(self, "synthiccframe", None):
			self.synthiccframe.Hide()
		for profile_info in self.profile_info.values():
			profile_info.Close()
		self.Hide()
		self.enable_menus(False)

	def Show(self, show=True, start_timers=True):
		if not self.IsShownOnScreen():
			if hasattr(self, "tcframe"):
				self.tcframe.Show(getcfg("tc.show"))
			self.infoframe.Show(getcfg("log.show"))
			if LUTFrame and getcfg("lut_viewer.show"):
				self.init_lut_viewer(show=True)
			for profile_info in reversed(self.profile_info.values()):
				profile_info.Show()
		if start_timers:
			self.start_timers()
		self.enable_menus()
		wx.Frame.Show(self, show)
		self.Raise()
		if not wx.GetApp().IsActive():
			self.RequestUserAttention()

	def OnShow(self, event):
		self.SetFocus()

	def OnClose(self, event=None):
		if sys.platform == "darwin" or debug: self.focus_handler(event)
		if not hasattr(self, "tcframe") or self.tcframe.tc_close_handler():
			writecfg()
			if getattr(self, "thread", None) and self.thread.isAlive():
				self.Disable()
				if debug:
					safe_print("Waiting for child thread to exit...")
				self.thread.join()
			self.HideAll()
			if self.worker.tempdir and os.path.isdir(self.worker.tempdir):
				self.worker.wrapup(False)
			wx.GetApp().ExitMainLoop()

class MainApp(wx.App):
	def OnInit(self):
		if sys.platform == "darwin" and not isapp:
			self.SetAppName("Python")
		else:
			self.SetAppName(appname)
		##wx_lang = getattr(wx, "LANGUAGE_" + lang.getstr("!language_name"), 
						  ##wx.LANGUAGE_ENGLISH)
		##self.locale = wx.Locale(wx_lang)
		##if debug:
			##safe_print("[D]", lang.getstr("!language_name"), wx_lang, 
					   ##self.locale.GetLocale())
		self.progress_dlg = ProgressDialog(msg=lang.getstr("startup"), 
										   handler=self.startup_progress_handler,
										   style=wx.PD_SMOOTH & ~wx.PD_CAN_ABORT,
										   pos=(getcfg("position.x") + 50, 
												getcfg("position.y") + 50))
		self.progress_dlg.MakeModal(False)
		self.frame = MainFrame()
		self.SetTopWindow(self.frame)
		self.frame.Show()
		return True
	
	def startup_progress_handler(self, event):
		self.progress_dlg.Pulse()


class MeasurementFileCheckSanityDialog(ConfirmDialog):
	
	def __init__(self, parent, ti3, suspicious, force=False):
		ConfirmDialog.__init__(self, parent,
							   title=os.path.basename(ti3.filename)
									 if ti3.filename else appname,
							   ok=lang.getstr("ok"),
							   cancel=lang.getstr("cancel"),
							   alt=lang.getstr("invert_selection"),
							   bitmap=geticon(32, "dialog-warning"), wrap=120)
		msg_col1 = lang.getstr("warning.suspicious_delta_e")
		msg_col2 = lang.getstr("warning.suspicious_delta_e.info")

		margin = 12

		dlg = self
		
		dlg.sizer3.Remove(dlg.message)
		dlg.message.Destroy()
		dlg.sizer4 = wx.BoxSizer(wx.HORIZONTAL)
		dlg.sizer3.Add(dlg.sizer4)
		dlg.message_col1 = wx.StaticText(dlg, -1, msg_col1)
		dlg.message_col1.Wrap(470)
		dlg.sizer4.Add(dlg.message_col1, flag=wx.RIGHT, border = 20)
		dlg.message_col2 = wx.StaticText(dlg, -1, msg_col2)
		dlg.message_col2.Wrap(470)
		dlg.sizer4.Add(dlg.message_col2, flag=wx.LEFT, border = 20)

		dlg.Unbind(wx.EVT_BUTTON, dlg.alt)
		dlg.Bind(wx.EVT_BUTTON, dlg.invert_selection_handler, id=dlg.alt.GetId())

		dlg.select_all_btn = wx.Button(dlg, -1, lang.getstr("deselect_all"))
		dlg.select_all_btn.SetInitialSize((dlg.select_all_btn.GetSize()[0] + 
										   btn_width_correction, -1))
		dlg.sizer2.Insert(2, (margin, margin))
		dlg.sizer2.Insert(2, dlg.select_all_btn)
		dlg.Bind(wx.EVT_BUTTON, dlg.select_all_handler,
				 id=dlg.select_all_btn.GetId())

		dlg.ti3 = ti3
		dlg.suspicious = suspicious
		dlg.mods = {}
		dlg.force = force

		dlg.grid = wx.grid.Grid(dlg, -1, size=(981, 240),
								style=wx.BORDER_SIMPLE)
		grid = dlg.grid
		grid.CreateGrid(0, 15)
		grid.SetColLabelSize(50)
		grid.SetRowLabelSize(60)
		attr = wx.grid.GridCellAttr()
		attr.SetReadOnly(True) 
		for i in xrange(grid.GetNumberCols()):
			if i in (4, 5) or i > 8:
				grid.SetColAttr(i, attr)
			if i == 0:
				size = 22
			elif i in (4, 5):
				size = 20
			elif i > 8:
				size = 80
			else:
				size = 60
			grid.SetColSize(i, size)
		for i, label in enumerate(["", "R %", "G %", "B %", "", "", "X", "Y", "Z",
								   u"\u0394E*00\nXYZ A/B",
								   u"0.5 \u0394E*00\nRGB A/B",
								   u"\u0394E*00\nRGB-XYZ",
								   u"\u0394L*00\nRGB-XYZ",
								   u"\u0394C*00\nRGB-XYZ",
								   u"\u0394H*00\nRGB-XYZ"]):
			grid.SetColLabelValue(i, label)
		attr = wx.grid.GridCellAttr()
		attr.SetEditor(wx.grid.GridCellBoolEditor())
		attr.SetRenderer(wx.grid.GridCellBoolRenderer())
		grid.SetColAttr(0, attr)
		font = wx.Font(FONTSIZE_MEDIUM, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, 
					   wx.FONTWEIGHT_NORMAL)
		grid.SetDefaultCellFont(font)
		grid.SetDefaultRowSize(20)
		grid.EnableDragColSize()
		grid.EnableGridLines(True)

		black = ti3.queryi1({"RGB_R": 0, "RGB_G": 0, "RGB_B": 0})
		if black:
			black = black["XYZ_X"], black["XYZ_Y"], black["XYZ_Z"]
		dlg.black = black
		white = ti3.queryi1({"RGB_R": 100, "RGB_G": 100, "RGB_B": 100})
		if white:
			white = white["XYZ_X"], white["XYZ_Y"], white["XYZ_Z"]
		dlg.white = white
		dlg.suspicious_items = []
		for i, (prev, item, delta, sRGB_delta, prev_delta_to_sRGB,
				delta_to_sRGB) in enumerate(suspicious):
			for cur in (prev, item):
				if cur and cur not in dlg.suspicious_items:
					dlg.suspicious_items.append(cur)
					grid.AppendRows(1)
					row = grid.GetNumberRows() - 1
					grid.SetRowLabelValue(row, "%d" % cur.SAMPLE_ID)
					RGB = []
					for k, label in enumerate("RGB"):
						value = cur["RGB_%s" % label]
						grid.SetCellValue(row, 1 + k, "%.4f" % value)
						RGB.append(value)
					XYZ = []
					for k, label in enumerate("XYZ"):
						value = cur["XYZ_%s" % label]
						grid.SetCellValue(row, 6 + k, "%.4f" % value)
						XYZ.append(value)
					if cur is prev:
						dlg.update_row(row, RGB, XYZ, None, None,
									   prev_delta_to_sRGB)
					else:
						dlg.update_row(row, RGB, XYZ, delta, sRGB_delta,
									   delta_to_sRGB)

		grid.Bind(wx.EVT_KEY_DOWN, dlg.key_handler)
		grid.Bind(wx.grid.EVT_GRID_CELL_CHANGE, dlg.cell_change_handler)
		grid.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, dlg.cell_click_handler)
		grid.Bind(wx.grid.EVT_GRID_SELECT_CELL, dlg.cell_select_handler)
		grid.Bind(wx.grid.EVT_GRID_EDITOR_CREATED, dlg.editor_created_handler)

		dlg.sizer3.Add(grid, 1, flag=wx.TOP | wx.ALIGN_LEFT, border=12)

		dlg.sizer0.SetSizeHints(dlg)
		dlg.sizer0.Layout()

		# This workaround is needed to update cell colours
		grid.SelectAll()
		grid.ClearSelection()

		dlg.Center()
	
	def cell_change_handler(self, event):
		dlg = self
		grid = dlg.grid
		if event.Col == 0:
			self.check_select_status()
		else:
			try:
				value = float(grid.GetCellValue(event.Row, event.Col).replace(",", "."))
			except ValueError:
				wx.Bell()
				item = dlg.suspicious_items[event.Row]
				label = "_RGB__XYZ"[event.Col]
				if event.Col < 6:
					label = "RGB_%s" % label
				else:
					label = "XYZ_%s" % label
				grid.SetCellValue(event.Row, event.Col,
									  "%.4f" % item[label])
			else:
				if event.Col < 4: 
					value = max(min(value, 100), 0)
				grid.SetCellValue(event.Row, event.Col, str(value))
				RGB = []
				for i in (1, 2, 3):
					RGB.append(float(grid.GetCellValue(event.Row, i)))
				XYZ = []
				for i in (6, 7, 8):
					XYZ.append(float(grid.GetCellValue(event.Row, i)))
				dlg.mods[event.Row] = (RGB, XYZ)
				# Update row
				(sRGBLab, Lab, delta_to_sRGB,
				 criteria1,
				 debuginfo) = check_ti3_criteria1(RGB, XYZ, dlg.black,
												  dlg.white,
												  print_debuginfo=True)
				if grid.GetCellValue(event.Row, 9):
					prev = dlg.suspicious_items[event.Row - 1]
					prev_RGB = prev["RGB_R"], prev["RGB_G"], prev["RGB_B"]
					prev_XYZ = prev["XYZ_X"], prev["XYZ_Y"], prev["XYZ_Z"]
					(prev_sRGBLab, prev_Lab, prev_delta_to_sRGB,
					 prev_criteria1,
					 prev_debuginfo) = check_ti3_criteria1(prev_RGB, prev_XYZ,
														   dlg.black, dlg.white,
														   print_debuginfo=False)
					(delta,
					 sRGB_delta,
					 criteria2) = check_ti3_criteria2(prev_Lab, Lab,
													  prev_sRGBLab, sRGBLab,
													  prev_RGB, RGB)
				else:
					delta, sRGB_delta = (None, ) * 2
				dlg.update_row(event.Row, RGB, XYZ, delta, sRGB_delta,
							   delta_to_sRGB)

				# This workaround is needed to update cell colours
				cells = grid.GetSelectedCells()
				grid.SelectAll()
				grid.ClearSelection()
				if cells:
					grid.SelectBlock(cells[0][0], cells[0][1],
									 cells[-1][0], cells[-1][0])

	def cell_click_handler(self, event):
		if event.Col == 0:
			wx.CallLater(100, self.toggle_cb)
		event.Skip()

	def cell_select_handler(self, event):
		dlg = self
		if event.Col == 0:
			wx.CallAfter(dlg.grid.EnableCellEditControl)
		event.Skip()
	
	def check_enable_ok(self):
		dlg = self
		for index in xrange(dlg.grid.GetNumberRows()):
			if dlg.grid.GetCellValue(index, 0) == "":
				dlg.ok.Enable()
				return
		dlg.ok.Enable(not dlg.force)
	
	def check_select_status(self, has_false_values=None, has_true_values=None):
		dlg = self
		if None in (has_false_values, has_true_values):
			for index in xrange(dlg.grid.GetNumberRows()):
				if dlg.grid.GetCellValue(index, 0) == "":
					has_false_values = True
				else:
					has_true_values = True
		if has_false_values:
			dlg.ok.Enable()
		else:
			dlg.ok.Enable(not self.force)
		if has_true_values:
			dlg.select_all_btn.SetLabel(lang.getstr("deselect_all"))
		else:
			dlg.select_all_btn.SetLabel(lang.getstr("select_all"))

	def editor_created_handler(self, event):
		dlg = self
		if event.Col == 0:
			dlg.grid.cb = event.Control
			dlg.grid.cb.WindowStyle |= wx.WANTS_CHARS
			dlg.grid.cb.Bind(wx.EVT_KEY_DOWN, dlg.key_handler)
		event.Skip()
	
	def invert_selection_handler(self, event):
		dlg = self
		has_false_values = False
		has_true_values = False
		for index in xrange(dlg.grid.GetNumberRows()):
			if dlg.grid.GetCellValue(index, 0) == "1":
				value = ""
				has_false_values = True
			else:
				value = "1"
				has_true_values = True
			dlg.grid.SetCellValue(index, 0, value)
		self.check_select_status(has_false_values, has_true_values)

	def key_handler(self, event):
		dlg = self
		if event.KeyCode == wx.WXK_UP:
			if dlg.grid.GridCursorRow > 0:
				dlg.grid.DisableCellEditControl()
				dlg.grid.MoveCursorUp(False)
		elif event.KeyCode == wx.WXK_DOWN:
			if dlg.grid.GridCursorRow < dlg.grid.NumberRows -1:
				dlg.grid.DisableCellEditControl()
				dlg.grid.MoveCursorDown(False)
		elif event.KeyCode == wx.WXK_LEFT:
			if dlg.grid.GridCursorCol > 0:
				dlg.grid.DisableCellEditControl()
				dlg.grid.MoveCursorLeft(False)
		elif event.KeyCode == wx.WXK_RIGHT:
			if dlg.grid.GridCursorCol < dlg.grid.NumberCols - 1:
				dlg.grid.DisableCellEditControl()
				dlg.grid.MoveCursorRight(False)
		elif event.KeyCode == wx.WXK_SPACE:
			if dlg.grid.GridCursorRow == 0:
				wx.CallLater(100, dlg.toggle_cb)
		else:
			if event.ControlDown() or event.CmdDown():
				keycode = event.KeyCode
				# CTRL (Linux/Mac/Windows) / CMD (Mac)
				if keycode == 65: # A
					dlg.grid.SelectAll()
					return
				elif keycode in (67, 88): # C / X
					clip = []
					cells = dlg.grid.GetSelection()
					i = -1
					start_col = dlg.grid.GetNumberCols()
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
						clip[-1][col] = dlg.grid.GetCellValue(row, col)
					# Skip first col with the checkbox
					if start_col == 0:
						start_col = 1
					for i, row in enumerate(clip):
						clip[i] = "\t".join(row[start_col:])
					clipdata = wx.TextDataObject()
					clipdata.SetText("\n".join(clip))
					wx.TheClipboard.Open()
					wx.TheClipboard.SetData(clipdata)
					wx.TheClipboard.Close()
					return
				elif keycode == 86: # V
					do = wx.TextDataObject()
					wx.TheClipboard.Open()
					success = wx.TheClipboard.GetData(do)
					wx.TheClipboard.Close()
					if success:
						txt = StringIO(do.GetText())
						lines = txt.readlines()
						txt.close()
						for i, line in enumerate(lines):
							lines[i] = re.sub("\s+", "\t", line).split("\t")
						# translate from selected cells into a grid with None values for not selected cells
						grid = []
						cells = dlg.grid.GetSelection()
						i = -1
						for cell in cells:
							row = cell[0]
							col = cell[1]
							# Skip read-only cells
							if (dlg.grid.IsReadOnly(row, col) or
								not dlg.grid.GetColLabelValue(col)):
								continue
							if i < row:
								grid += [[]]
								i = row
							grid[-1].append(cell)
						# 'paste' values from clipboard
						for i, row in enumerate(grid):
							for j, cell in enumerate(row):
								if (cell != None and len(lines) > i and
									len(lines[i]) > j):
									dlg.grid.SetCellValue(cell[0], cell[1], lines[i][j])
									dlg.cell_change_handler(CustomGridCellEvent(wx.grid.EVT_GRID_CELL_CHANGE.evtType[0],
																				dlg.grid, cell[0], cell[1]))
					return
			event.Skip()
	
	def mark_cell(self, row, col, ok=False):
		grid = self.grid
		font = wx.Font(FONTSIZE_MEDIUM, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, 
					   wx.FONTWEIGHT_NORMAL if ok else wx.FONTWEIGHT_BOLD)
		grid.SetCellFont(row, col, font)
		grid.SetCellTextColour(row, col, grid.GetDefaultCellTextColour() if ok
										 else wx.Colour(204, 0, 0))
	
	def select_all_handler(self, event):
		dlg = self
		if dlg.select_all_btn.GetLabel() == lang.getstr("select_all"):
			value = "1"
		else:
			value = ""
		for index in xrange(dlg.grid.GetNumberRows()):
			dlg.grid.SetCellValue(index, 0, value)
		self.check_select_status(not value, value)

	def toggle_cb(self):
		dlg = self
		if hasattr(dlg.grid, "cb"):
			# Click on the cell border does not cause the editor to be
			# created
			dlg.grid.cb.Value = not dlg.grid.cb.Value
		wx.CallLater(100, dlg.grid.DisableCellEditControl)
	
	def update_row(self, row, RGB, XYZ, delta, sRGB_delta, delta_to_sRGB):
		dlg = self
		grid = dlg.grid
		RGB255 = [int(round(float(str(v * 2.55)))) for v in RGB]
		dlg.grid.SetCellBackgroundColour(row, 4,
										 wx.Colour(*RGB255))
		if dlg.white:
			XYZ = colormath.adapt(XYZ[0], XYZ[1], XYZ[2],
								  dlg.white, "D65")
		RGB255 = [int(round(float(str(v)))) for v in
				  colormath.XYZ2RGB(XYZ[0] / 100.0,
									XYZ[1] / 100.0,
									XYZ[2] / 100.0, scale=255)]
		dlg.grid.SetCellBackgroundColour(row, 5,
										 wx.Colour(*RGB255))
		grid.SetCellValue(row, 0, "1" if (not delta or (delta["E_ok"] and
														delta["L_ok"])) and
										 delta_to_sRGB["ok"]
									  else "")
		for col in xrange(3):
			dlg.mark_cell(row, 6 + col, (not delta or (delta["E_ok"] and
													   (delta["L_ok"] or
														col != 1))) and
										delta_to_sRGB["ok"])
		if delta:
			grid.SetCellValue(row, 9, "%.2f" % delta["E"])
			dlg.mark_cell(row, 9, delta["E_ok"])
			if sRGB_delta:
				grid.SetCellValue(row, 10, "%.2f" % sRGB_delta["E"])
		for col, ELCH in enumerate("ELCH"):
			grid.SetCellValue(row, 11 + col, "%.2f" % delta_to_sRGB[ELCH])
			dlg.mark_cell(row, 11 + col, delta_to_sRGB["%s_ok" % ELCH])


def main():
	initcfg()
	lang.init()
	app = MainApp(redirect=False)  # Don't redirect stdin/stdout
	app.MainLoop()

if __name__ == "__main__":
	
	main()
