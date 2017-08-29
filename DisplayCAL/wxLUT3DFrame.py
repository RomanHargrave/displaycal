# -*- coding: utf-8 -*-

from __future__ import with_statement
import glob
import os
import re
import shutil
import sys

if sys.platform == "win32":
	import win32api

from argyll_cgats import cal_to_fake_profile
from argyll_names import video_encodings
from config import (get_data_path, get_verified_path, getcfg, geticon, hascfg,
					profile_ext, setcfg)
from log import safe_print
from meta import name as appname, version
from options import debug
from util_os import islink, readlink, waccess
from util_str import safe_unicode, strtr
from worker import (Error, Info, UnloggedInfo, get_current_profile_path,
					show_result_dialog)
import ICCProfile as ICCP
import colormath
import config
import localization as lang
import madvr
import worker
from worker import UnloggedWarning, check_set_argyll_bin, get_options_from_profile
from wxwindows import (BaseApp, BaseFrame, ConfirmDialog, FileDrop, InfoDialog,
					   wx)
from wxfixes import TempXmlResource
import floatspin
import xh_filebrowsebutton
import xh_floatspin
import xh_bitmapctrls

from wx import xrc


class LUT3DFrame(BaseFrame):

	""" 3D LUT creation window """
	
	def __init__(self, parent=None, setup=True):
		self.res = TempXmlResource(get_data_path(os.path.join("xrc", 
															  "3dlut.xrc")))
		self.res.InsertHandler(xh_filebrowsebutton.FileBrowseButtonWithHistoryXmlHandler())
		self.res.InsertHandler(xh_floatspin.FloatSpinCtrlXmlHandler())
		self.res.InsertHandler(xh_bitmapctrls.BitmapButton())
		self.res.InsertHandler(xh_bitmapctrls.StaticBitmap())
		if hasattr(wx, "PreFrame"):
			# Classic
			pre = wx.PreFrame()
			self.res.LoadOnFrame(pre, parent, "lut3dframe")
			self.PostCreate(pre)
		else:
			# Phoenix
			wx.Frame.__init__(self)
			self.res.LoadFrame(self, parent, "lut3dframe")
		self.init()
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		
		self.SetIcons(config.get_icon_bundle([256, 48, 32, 16],
											 appname + "-3DLUT-maker"))
		
		self.set_child_ctrls_as_attrs(self)

		self.panel = self.FindWindowByName("panel")

		if setup:
			self.setup()

	def setup(self):
		self.worker = worker.Worker(self)
		self.worker.set_argyll_version("collink")

		for which in ("input", "abstract", "output"):
			ctrl = self.FindWindowByName("%s_profile_ctrl" % which)
			setattr(self, "%s_profile_ctrl" % which, ctrl)
			ctrl.changeCallback = getattr(self, "%s_profile_ctrl_handler" % 
												which)
			if which not in ("abstract", "output"):
				ctrl.SetHistory(get_data_path("ref", "\.(icc|icm)$"))
			ctrl.SetMaxFontSize(11)
			# Drop targets
			droptarget = FileDrop(self,
								  {".icc": getattr(self, "%s_drop_handler" % which),
								   ".icm": getattr(self, "%s_drop_handler" % which)})
			ctrl.SetDropTarget(droptarget)

		# Bind event handlers
		self.abstract_profile_cb.Bind(wx.EVT_CHECKBOX,
									  self.use_abstract_profile_ctrl_handler)
		self.output_profile_current_btn.Bind(wx.EVT_BUTTON,
											 self.output_profile_current_ctrl_handler)
		self.lut3d_trc_apply_none_ctrl.Bind(wx.EVT_RADIOBUTTON, self.lut3d_trc_apply_ctrl_handler)
		self.lut3d_trc_apply_black_offset_ctrl.Bind(wx.EVT_RADIOBUTTON, self.lut3d_trc_apply_ctrl_handler)
		self.lut3d_trc_apply_ctrl.Bind(wx.EVT_RADIOBUTTON, self.lut3d_trc_apply_ctrl_handler)
		self.lut3d_bind_event_handlers()
		
		self.lut3d_create_btn.SetDefault()
		
		self.setup_language()
		self.XYZbpin = [0, 0, 0]
		# XYZbpout will be set to the blackpoint of the selected profile. This
		# is used to determine if lack output offset controls should be shown.
		# Set a initial value slightly above zero so output offset controls are
		# shown if the selected profile doesn't exist.
		self.XYZbpout = [0.001, 0.001, 0.001]
		self.update_controls()
		self.update_layout()
		
		config.defaults.update({
			"position.lut3dframe.x": self.GetDisplay().ClientArea[0] + 40,
			"position.lut3dframe.y": self.GetDisplay().ClientArea[1] + 60,
			"size.lut3dframe.w": self.GetMinSize()[0],
			"size.lut3dframe.h": self.GetMinSize()[1]})

		if (hascfg("position.lut3dframe.x") and
			hascfg("position.lut3dframe.y") and
			hascfg("size.lut3dframe.w") and
			hascfg("size.lut3dframe.h")):
			self.SetSaneGeometry(int(getcfg("position.lut3dframe.x")),
								 int(getcfg("position.lut3dframe.y")),
								 int(getcfg("size.lut3dframe.w")),
								 int(getcfg("size.lut3dframe.h")))
		else:
			self.Center()

	def lut3d_bind_event_handlers(self):
		# Shared with main window
		self.lut3d_apply_cal_cb.Bind(wx.EVT_CHECKBOX, self.lut3d_apply_cal_ctrl_handler)
		self.lut3d_create_btn.Bind(wx.EVT_BUTTON, self.lut3d_create_handler)
		self.lut3d_trc_ctrl.Bind(wx.EVT_CHOICE, self.lut3d_trc_ctrl_handler)
		self.lut3d_trc_gamma_ctrl.Bind(wx.EVT_COMBOBOX,
								 self.lut3d_trc_gamma_ctrl_handler)
		self.lut3d_trc_gamma_ctrl.Bind(wx.EVT_KILL_FOCUS,
								 self.lut3d_trc_gamma_ctrl_handler)
		self.lut3d_trc_gamma_type_ctrl.Bind(wx.EVT_CHOICE,
									  self.lut3d_trc_gamma_type_ctrl_handler)
		self.lut3d_trc_black_output_offset_ctrl.Bind(wx.EVT_SLIDER,
										   self.lut3d_trc_black_output_offset_ctrl_handler)
		self.lut3d_trc_black_output_offset_intctrl.Bind(wx.EVT_TEXT,
											  self.lut3d_trc_black_output_offset_ctrl_handler)
		self.lut3d_hdr_peak_luminance_ctrl.Bind(wx.EVT_TEXT,
											self.lut3d_hdr_peak_luminance_handler)
		self.lut3d_hdr_display_ctrl.Bind(wx.EVT_CHOICE, self.lut3d_hdr_display_handler)
		self.lut3d_hdr_maxcll_ctrl.Bind(wx.EVT_TEXT,
										self.lut3d_hdr_maxcll_handler)
		self.lut3d_content_colorspace_ctrl.Bind(wx.EVT_CHOICE,
												self.lut3d_content_colorspace_handler)
		for color in ("white", "red", "green", "blue"):
			for coord in "xy":
				v = getcfg("3dlut.content.colorspace.%s.%s" % (color, coord))
				getattr(self, "lut3d_content_colorspace_%s_%s" %
							  (color, coord)).Bind(floatspin.EVT_FLOATSPIN,
												   self.lut3d_content_colorspace_xy_handler)
		self.encoding_input_ctrl.Bind(wx.EVT_CHOICE,
											self.lut3d_encoding_input_ctrl_handler)
		self.encoding_output_ctrl.Bind(wx.EVT_CHOICE,
									   self.lut3d_encoding_output_ctrl_handler)
		self.gamut_mapping_inverse_a2b.Bind(wx.EVT_RADIOBUTTON,
											self.lut3d_gamut_mapping_mode_handler)
		self.gamut_mapping_b2a.Bind(wx.EVT_RADIOBUTTON,
									self.lut3d_gamut_mapping_mode_handler)
		self.lut3d_rendering_intent_ctrl.Bind(wx.EVT_CHOICE,
										self.lut3d_rendering_intent_ctrl_handler)
		self.lut3d_format_ctrl.Bind(wx.EVT_CHOICE,
									self.lut3d_format_ctrl_handler)
		self.lut3d_size_ctrl.Bind(wx.EVT_CHOICE,
								  self.lut3d_size_ctrl_handler)
		self.lut3d_bitdepth_input_ctrl.Bind(wx.EVT_CHOICE,
											self.lut3d_bitdepth_input_ctrl_handler)
		self.lut3d_bitdepth_output_ctrl.Bind(wx.EVT_CHOICE,
											 self.lut3d_bitdepth_output_ctrl_handler)
	
	def OnClose(self, event=None):
		if (getattr(self.worker, "thread", None) and
			self.worker.thread.isAlive()):
			self.worker.abort_subprocess(True)
			return
		if sys.platform == "darwin" or debug: self.focus_handler(event)
		if (self.IsShownOnScreen() and not self.IsMaximized() and
			not self.IsIconized()):
			x, y = self.GetScreenPosition()
			setcfg("position.lut3dframe.x", x)
			setcfg("position.lut3dframe.y", y)
			setcfg("size.lut3dframe.w", self.GetSize()[0])
			setcfg("size.lut3dframe.h", self.GetSize()[1])
		if self.Parent:
			config.writecfg()
		else:
			config.writecfg(module="3DLUT-maker",
							options=("3dlut.", "last_3dlut_path",
									 "position.lut3dframe", "size.lut3dframe"))
		if event:
			event.Skip()
	
	def use_abstract_profile_ctrl_handler(self, event):
		setcfg("3dlut.use_abstract_profile",
			   int(self.abstract_profile_cb.GetValue()))
		enable = bool(getcfg("3dlut.use_abstract_profile"))
		self.abstract_profile_ctrl.Enable(enable)
	
	def lut3d_trc_apply_ctrl_handler(self, event=None):
		v = self.lut3d_trc_apply_ctrl.GetValue()
		self.lut3d_trc_ctrl.Enable(v)
		self.lut3d_trc_gamma_label.Enable(v)
		self.lut3d_trc_gamma_ctrl.Enable(v)
		self.lut3d_trc_gamma_type_ctrl.Enable(v)
		if event:
			setcfg("3dlut.apply_trc", int(v))
			setcfg("3dlut.apply_black_offset",
				   int(self.lut3d_trc_apply_black_offset_ctrl.GetValue()))
		self.lut3d_hdr_peak_luminance_label.Enable(v)
		self.lut3d_hdr_peak_luminance_ctrl.Enable(v)
		self.lut3d_hdr_peak_luminance_ctrl_label.Enable(v)
		self.lut3d_hdr_maxcll_label.Enable(v)
		self.lut3d_hdr_maxcll_ctrl.Enable(v)
		self.lut3d_hdr_maxcll_ctrl_label.Enable(v)
		self.lut3d_content_colorspace_label.Enable(v)
		self.lut3d_content_colorspace_ctrl.Enable(v)
		for color in ("white", "red", "green", "blue"):
			for coord in "xy":
				getattr(self, "lut3d_content_colorspace_%s_label" %
							  color[0]).Enable(v)
				getattr(self, "lut3d_content_colorspace_%s_%s" %
							  (color, coord)).Enable(v)
				getattr(self, "lut3d_content_colorspace_%s_%s_label" %
							  (color, coord)).Enable(v)
		self.lut3d_trc_black_output_offset_label.Enable(v)
		self.lut3d_trc_black_output_offset_ctrl.Enable(v)
		self.lut3d_trc_black_output_offset_intctrl.Enable(v)
		self.lut3d_trc_black_output_offset_intctrl_label.Enable(v)
		self.lut3d_show_input_value_clipping_warning(event)
		self.lut3d_show_hdr_display_control()

	def lut3d_show_input_value_clipping_warning(self, layout):
		self.panel.Freeze()
		show = (self.lut3d_trc_apply_none_ctrl.GetValue() and
				self.XYZbpout > self.XYZbpin and
				getcfg("3dlut.rendering_intent") not in ("la", "p", "pa", "ms",
														 "s", "lp"))
		self.lut3d_input_value_clipping_bmp.Show(show)
		self.lut3d_input_value_clipping_label.Show(show)
		if layout:
			self.panel.Sizer.Layout()
			self.update_layout()
		self.panel.Thaw()
	
	def lut3d_apply_cal_ctrl_handler(self, event):
		setcfg("3dlut.output.profile.apply_cal",
			   int(self.lut3d_apply_cal_cb.GetValue()))

	def lut3d_hdr_display_handler(self, event):
		if (self.lut3d_hdr_display_ctrl.GetSelection() and
			not getcfg("3dlut.hdr_display")):
			if not show_result_dialog(UnloggedInfo(lang.getstr("3dlut.format.madVR.hdr.confirm")),
									  self, confirm=lang.getstr("ok")):
				self.lut3d_hdr_display_ctrl.SetSelection(0)
				return
		self.lut3d_set_option("3dlut.hdr_display",
							  self.lut3d_hdr_display_ctrl.GetSelection())

	def lut3d_hdr_peak_luminance_handler(self, event):
		self.lut3d_set_option("3dlut.hdr_peak_luminance",
							  self.lut3d_hdr_peak_luminance_ctrl.GetValue())

	def lut3d_hdr_maxcll_handler(self, event):
		self.lut3d_set_option("3dlut.hdr_maxcll",
							  self.lut3d_hdr_maxcll_ctrl.GetValue())

	def lut3d_trc_black_output_offset_ctrl_handler(self, event):
		if event.GetId() == self.lut3d_trc_black_output_offset_intctrl.GetId():
			self.lut3d_trc_black_output_offset_ctrl.SetValue(
				self.lut3d_trc_black_output_offset_intctrl.GetValue())
		else:
			self.lut3d_trc_black_output_offset_intctrl.SetValue(
				self.lut3d_trc_black_output_offset_ctrl.GetValue())
		v = self.lut3d_trc_black_output_offset_ctrl.GetValue() / 100.0
		if v != getcfg("3dlut.trc_output_offset"):
			self.lut3d_set_option("3dlut.trc_output_offset", v)
			self.lut3d_update_trc_control()
			self.lut3d_show_trc_controls()

	def lut3d_trc_gamma_ctrl_handler(self, event):
		try:
			v = float(self.lut3d_trc_gamma_ctrl.GetValue().replace(",", "."))
			if (v < config.valid_ranges["3dlut.trc_gamma"][0] or
				v > config.valid_ranges["3dlut.trc_gamma"][1]):
				raise ValueError()
		except ValueError:
			wx.Bell()
			self.lut3d_trc_gamma_ctrl.SetValue(str(getcfg("3dlut.trc_gamma")))
		else:
			if str(v) != self.lut3d_trc_gamma_ctrl.GetValue():
				self.lut3d_trc_gamma_ctrl.SetValue(str(v))
			if v != getcfg("3dlut.trc_gamma"):
				self.lut3d_set_option("3dlut.trc_gamma", v)
				self.lut3d_update_trc_control()
				self.lut3d_show_trc_controls()
		event.Skip()

	def lut3d_trc_ctrl_handler(self, event):
		self.Freeze()
		if self.lut3d_trc_ctrl.GetSelection() == 1:
			# BT.1886
			self.lut3d_set_option("3dlut.trc_gamma", 2.4)
			self.lut3d_set_option("3dlut.trc_gamma_type", "B")
			self.lut3d_set_option("3dlut.trc_output_offset", 0.0)
			trc = "bt1886"
		elif self.lut3d_trc_ctrl.GetSelection() == 0:
			# Pure power gamma 2.2
			self.lut3d_set_option("3dlut.trc_gamma", 2.2)
			self.lut3d_set_option("3dlut.trc_gamma_type", "b")
			self.lut3d_set_option("3dlut.trc_output_offset", 1.0)
			trc = "gamma2.2"
		elif self.lut3d_trc_ctrl.GetSelection() == 2:  # SMPTE 2084, hard clip
			self.lut3d_set_option("3dlut.trc_output_offset", 0.0)
			trc = "smpte2084.hardclip"
			self.lut3d_set_option("3dlut.hdr_maxcll", 10000)
		elif self.lut3d_trc_ctrl.GetSelection() == 3:  # SMPTE 2084, roll-off clip
			self.lut3d_set_option("3dlut.trc_output_offset", 0.0)
			trc = "smpte2084.rolloffclip"
			self.lut3d_set_option("3dlut.hdr_maxcll", 10000)
		else:
			trc = "customgamma"
		self.lut3d_set_option("3dlut.trc", trc)
		if trc != "customgamma":
			self.lut3d_update_trc_controls()
		self.lut3d_show_trc_controls()
		self.Thaw()

	def lut3d_trc_gamma_type_ctrl_handler(self, event):
		v = self.trc_gamma_types_ab[self.lut3d_trc_gamma_type_ctrl.GetSelection()]
		if v != getcfg("3dlut.trc_gamma_type"):
			self.lut3d_set_option("3dlut.trc_gamma_type", v)
			self.lut3d_update_trc_control()
			self.lut3d_show_trc_controls()

	def abstract_drop_handler(self, path):
		if not self.worker.is_working():
			self.abstract_profile_ctrl.SetPath(path)
			self.set_profile("abstract")
	
	def lut3d_encoding_input_ctrl_handler(self, event):
		encoding = self.encoding_input_ab[self.encoding_input_ctrl.GetSelection()]
		self.lut3d_set_option("3dlut.encoding.input", encoding)
		if getcfg("3dlut.format") == "eeColor":
			if encoding == "T":
				encoding = "t"
			self.encoding_output_ctrl.SetSelection(self.encoding_output_ba[encoding])
			self.lut3d_set_option("3dlut.encoding.output", encoding)
		if getattr(self, "lut3dframe", None):
			self.lut3dframe.lut3d_update_encoding_controls()
		elif self.Parent:
			self.Parent.lut3d_update_encoding_controls()
	
	def lut3d_encoding_output_ctrl_handler(self, event):
		encoding = self.encoding_output_ab[self.encoding_output_ctrl.GetSelection()]
		if getcfg("3dlut.format") == "madVR" and encoding != "t":
			profile = getattr(self, "output_profile", None)
			if (profile and "meta" in profile.tags and
				isinstance(profile.tags.meta, ICCP.DictType) and
				"EDID_model" in profile.tags.meta):
				devicename = profile.tags.meta["EDID_model"]
			else:
				devicename = None
			dlg = ConfirmDialog(self,
						msg=lang.getstr("3dlut.encoding.output.warning.madvr",
										devicename or
										lang.getstr("device.name.placeholder")), 
						ok=lang.getstr("ok"), 
						cancel=lang.getstr("cancel"), 
						bitmap=geticon(32, "dialog-warning"))
			result = dlg.ShowModal()
			dlg.Destroy()
			if result != wx.ID_OK:
				self.encoding_output_ctrl.SetSelection(
					self.encoding_output_ba[getcfg("3dlut.encoding.output")])
				return False
		self.lut3d_set_option("3dlut.encoding.output", encoding)
		if getattr(self, "lut3dframe", None):
			self.lut3dframe.lut3d_update_encoding_controls()
		elif self.Parent:
			self.Parent.lut3d_update_encoding_controls()

	def input_drop_handler(self, path):
		if not self.worker.is_working():
			self.input_profile_ctrl.SetPath(path)
			self.set_profile("input")

	def output_drop_handler(self, path):
		if not self.worker.is_working():
			self.output_profile_ctrl.SetPath(path)
			self.set_profile("output")
	
	def abstract_profile_ctrl_handler(self, event):
		self.set_profile("abstract", silent=not event)
	
	def input_profile_ctrl_handler(self, event):
		self.set_profile("input", silent=not event)
		if self.Parent:
			self.Parent.lut3d_init_input_profiles()
			self.Parent.lut3d_update_controls()
	
	def lut3d_bitdepth_input_ctrl_handler(self, event):
		self.lut3d_set_option("3dlut.bitdepth.input",
			   self.lut3d_bitdepth_ab[self.lut3d_bitdepth_input_ctrl.GetSelection()])
		if getattr(self, "lut3dframe", None):
			self.lut3dframe.lut3d_update_shared_controls()
		elif self.Parent:
			self.Parent.lut3d_update_shared_controls()
	
	def lut3d_bitdepth_output_ctrl_handler(self, event):
		if (getcfg("3dlut.format") in ("png", "ReShade") and
			self.lut3d_bitdepth_ab[self.lut3d_bitdepth_output_ctrl.GetSelection()]
			not in (8, 16)):
			wx.Bell()
			self.lut3d_bitdepth_output_ctrl.SetSelection(self.lut3d_bitdepth_ba[8])
		self.lut3d_set_option("3dlut.bitdepth.output",
			   self.lut3d_bitdepth_ab[self.lut3d_bitdepth_output_ctrl.GetSelection()])
		if getattr(self, "lut3dframe", None):
			self.lut3dframe.lut3d_update_shared_controls()
		elif self.Parent:
			self.Parent.lut3d_update_shared_controls()

	def lut3d_content_colorspace_handler(self, event):
		sel = self.lut3d_content_colorspace_ctrl.Selection
		try:
			rgb_space = self.lut3d_content_colorspace_names[sel]
		except IndexError:
			# Custom
			rgb_space = None
		else:
			rgb_space = colormath.get_rgb_space(rgb_space)
			for i, color in enumerate(("white", "red", "green", "blue")):
				if i == 0:
					xyY = colormath.XYZ2xyY(*rgb_space[1])
				else:
					xyY = rgb_space[2:][i - 1]
				for j, coord in enumerate("xy"):
					v = round(xyY[j], 4)
					self.lut3d_set_option("3dlut.content.colorspace.%s.%s" %
										  (color, coord), v)
			self.lut3d_update_trc_controls()
		self.panel.Freeze()
		sizer = self.lut3d_content_colorspace_red_x.ContainingSizer
		sizer.ShowItems(not rgb_space)
		self.panel.Layout()
		self.panel.Thaw()
		if isinstance(self, LUT3DFrame):
			self.update_layout()

	def lut3d_content_colorspace_xy_handler(self, event):
		option = event.GetEventObject().Name.replace("_", ".")[5:]
		self.lut3d_set_option("3dlut" + option,
							  event.GetEventObject().GetValue())
		self.lut3d_update_trc_controls()
	
	def lut3d_create_consumer(self, result=None):
		if isinstance(result, Exception):
			show_result_dialog(result, self)
		# Remove temporary files
		self.worker.wrapup(False)
		if not isinstance(result, Exception) and result:
			if not isinstance(self, LUT3DFrame) and getattr(self, "lut3d_path",
															None):
				# 3D LUT tab is part of main window
				if getcfg("3dlut.create"):
					# 3D LUT was created automatically after profiling, show
					# usual profile summary window
					self.profile_finish(True,
										getcfg("calibration.file", False),
										lang.getstr("calibration_profiling.complete"), 
										lang.getstr("profiling.incomplete"),
										install_3dlut=True)
				else:
					# 3D LUT was created manually
					self.profile_finish(True,
										getcfg("calibration.file", False),
										"", 
										lang.getstr("profiling.incomplete"),
										install_3dlut=True)
	
	def lut3d_create_handler(self, event, path=None, copy_from_path=None):
		if sys.platform == "darwin" or debug: self.focus_handler(event)
		if not check_set_argyll_bin():
			return
		if isinstance(self, LUT3DFrame):
			profile_in = self.set_profile("input")
			if getcfg("3dlut.use_abstract_profile"):
				profile_abst = self.set_profile("abstract")
			else:
				profile_abst = None
			profile_out = self.set_profile("output")
		else:
			profile_abst = None
			profile_in_path = getcfg("3dlut.input.profile")
			if not profile_in_path or not os.path.isfile(profile_in_path):
				show_result_dialog(Error(lang.getstr("error.profile.file_missing",
													 getcfg("3dlut.input.profile",
															raw=True))),
								   parent=self)
				return
				
			try:
				profile_in = ICCP.ICCProfile(profile_in_path)
			except (IOError, ICCP.ICCProfileInvalidError), exception:
				show_result_dialog(Error(lang.getstr("profile.invalid") + "\n" +
										 profile_in_path), parent=self)
				return
			profile_out = config.get_current_profile()
			if not profile_out:
				show_result_dialog(Error(lang.getstr("profile.invalid") +
										 "\n%s" % getcfg("calibration.file",
														 False)), parent=self)
				return
			if path:
				# Called from script client
				self.lut3d_path = None
			elif not copy_from_path:
				self.lut3d_set_path()
				path = self.lut3d_path
		if (not None in (profile_in, profile_out) or
			(profile_in and profile_in.profileClass == "link")):
			if profile_out and profile_in.isSame(profile_out,
												 force_calculation=True):
				if not show_result_dialog(Warning(lang.getstr("error.source_dest_same")),
										  self, confirm=lang.getstr("continue")):
					return
			checkoverwrite = True
			remember_last_3dlut_path = False
			if not path:
				defaultDir, defaultFile = get_verified_path("last_3dlut_path")
				if copy_from_path:
					defaultFile = os.path.basename(copy_from_path)
				# Only remember last used path if it was a deliberate user
				# choice via the filedialog
				remember_last_3dlut_path = True
				if copy_from_path and config.get_display_name() == "Resolve":
					# Find path to Resolve LUT folder
					if sys.platform == "win32":
						drives = win32api.GetLogicalDriveStrings()
						for drive in drives.split("\0")[:-1]:
							lut_dir = os.path.join(drive, "ProgramData",
												   "Blackmagic Design",
												   "DaVinci Resolve", "Support",
												   "LUT")
							if os.path.isdir(lut_dir):
								defaultDir = lut_dir
								remember_last_3dlut_path = False
								break
					else:
						# Assume OS X
						volumes = ["/"] + glob.glob("/Volumes/*")
						for volume in volumes:
							lut_dir = os.path.join(volume, "Library",
												   "Application Support",
												   "Blackmagic Design",
												   "DaVinci Resolve", "LUT")
							if os.path.isdir(lut_dir):
								defaultDir = lut_dir
								remember_last_3dlut_path = False
								break
				ext = getcfg("3dlut.format")
				if (ext != "madVR" and not isinstance(self, LUT3DFrame) and
					getcfg("3dlut.output.profile.apply_cal")):
					# Check if there's a clash between current videoLUT
					# and 3D LUT (do both contain non-linear calibration?)
					profile_display_name = profile_out.getDeviceModelDescription()
					tempdir = self.worker.create_tempdir()
					if isinstance(tempdir, Exception):
						show_result_dialog(tempdir, self)
						return
					tempcal = os.path.join(tempdir, "temp.cal")
					cancel = False
					real_displays_count = 0
					show_nonlinear_videolut_warning = False
					for i, display_name in enumerate(self.worker.display_names):
						if (display_name == profile_display_name and
							display_name != "madVR" and
							self.worker.lut_access[i] and
							self.worker.save_current_video_lut(
								i + 1, tempcal, silent=True) is True and
							not cal_to_fake_profile(tempcal).tags.vcgt.is_linear()):
							show_nonlinear_videolut_warning = True
							break
						if not config.is_virtual_display(i):
							real_displays_count += 1
					if (show_nonlinear_videolut_warning or
						real_displays_count == 1):
						if copy_from_path:
							confirm = lang.getstr("3dlut.save_as")
						else:
							confirm = lang.getstr("3dlut.install")
						if not show_result_dialog(UnloggedWarning(
							lang.getstr("3dlut.1dlut.videolut.nonlinear")),
							self, confirm=confirm):
							cancel = True
					if os.path.isfile(tempcal):
						os.remove(tempcal)
					if cancel:
						return
				if ext == "ReShade":
					dlg = wx.DirDialog(self, lang.getstr("3dlut.install"), 
									   defaultPath=defaultDir)
				else:
					if ext == "eeColor":
						ext = "txt"
					elif ext == "madVR":
						ext = "3dlut"
					elif ext == "icc":
						ext = profile_ext[1:]
					defaultFile = os.path.splitext(defaultFile or
												   os.path.basename(config.defaults.get("last_3dlut_path")))[0] + "." + ext
					dlg = wx.FileDialog(self, 
										lang.getstr("3dlut.save_as"),
										defaultDir=defaultDir,
										defaultFile=defaultFile,
										wildcard="*." + ext, 
										style=wx.SAVE | wx.FD_OVERWRITE_PROMPT)
				dlg.Center(wx.BOTH)
				if dlg.ShowModal() == wx.ID_OK:
					path = dlg.GetPath()
					if ext == "ReShade":
						path = os.path.join(path.rstrip(os.path.sep),
											"ColorLookupTable.png")
				dlg.Destroy()
				checkoverwrite = False
			if path:
				if not waccess(path, os.W_OK):
					show_result_dialog(Error(lang.getstr("error.access_denied.write",
														 path)),
									   self)
					return
				if remember_last_3dlut_path:
					setcfg("last_3dlut_path", path)
				if checkoverwrite and os.path.isfile(path):
					dlg = ConfirmDialog(self,
										msg=lang.getstr("dialog.confirm_overwrite",
														(path)),
										ok=lang.getstr("overwrite"),
										cancel=lang.getstr("cancel"),
										bitmap
										=geticon(32, "dialog-warning"))
					result = dlg.ShowModal()
					dlg.Destroy()
					if result != wx.ID_OK:
						return
				if self.Parent:
					config.writecfg()
				elif isinstance(self, LUT3DFrame):
					config.writecfg(module="3DLUT-maker",
									options=("3dlut.", "last_3dlut_path",
											 "position.lut3dframe",
											 "size.lut3dframe"))
				if copy_from_path:
					# Instead of creating a 3D LUT, copy existing one
					src_name = os.path.splitext(copy_from_path)[0]
					dst_name = os.path.splitext(path)[0]
					src_paths = [copy_from_path]
					dst_paths = [path]
					if getcfg("3dlut.format") == "eeColor":
						# eeColor: 3D LUT + 6x 1D LUT
						for part in ("first", "second"):
							for channel in ("blue", "green", "red"):
								src_path = "%s-%s1d%s.txt" % (src_name, part,
															  channel)
								if os.path.isfile(src_path):
									src_paths.append(src_path)
									dst_paths.append("%s-%s1d%s.txt" %
													 (dst_name, part, channel))
					elif getcfg("3dlut.format") == "ReShade":
						dst_dir = os.path.dirname(path)
						# Check if MasterEffect is installed
						me_header_path = os.path.join(dst_dir, "MasterEffect.h")
						use_mclut3d = False
						if (use_mclut3d and os.path.isfile(me_header_path) and
							os.path.isdir(os.path.join(dst_dir, "MasterEffect"))):
							dst_paths = [os.path.join(dst_dir, "MasterEffect",
													  "mclut3d.png")]
							# Alter existing MasterEffect.h
							with open(me_header_path, "rb") as me_header_file:
								me_header = me_header_file.read()
							# Enable LUT
							me_header = re.sub(r"#define\s+USE_LUT\s+0",
											   "#define USE_LUT 1", me_header)
							# iLookupTableMode 2 = use mclut3d.png
							me_header = re.sub(r"#define\s+iLookupTableMode\s+\d+",
											   "#define iLookupTableMode 2", me_header)
							# Amount of color change by lookup table.
							# 1.0 means full effect.
							me_header = re.sub(r"#define\s+fLookupTableMix\s+\d+(?:\.\d+)",
											   "#define fLookupTableMix 1.0", me_header)
							with open(me_header_path, "wb") as me_header_file:
								me_header_file.write(me_header)
						else:
							# Write out our own shader
							clut_fx_path = get_data_path("ColorLookupTable.fx")
							if not clut_fx_path:
								show_result_dialog(Error(lang.getstr("file.missing",
																	 "ColorLookupTable.fx")),
												   self)
								return
							with open(clut_fx_path, "rb") as clut_fx_file:
								clut_fx = clut_fx_file.read()
							clut_size = getcfg("3dlut.size")
							clut_fx = strtr(clut_fx,
											{"${VERSION}": version,
											 "${WIDTH}": str(clut_size ** 2),
											 "${HEIGHT}": str(clut_size),
											 "${FORMAT}": "RGBA%i" % getcfg("3dlut.bitdepth.output")})
							reshade_fx_path = os.path.join(dst_dir, "ReShade.fx")
							# Adjust path for correct installation if ReShade.fx
							# is a symlink.
							if islink(reshade_fx_path):
								reshade_fx_path = readlink(reshade_fx_path)
								path = os.path.join(os.path.dirname(reshade_fx_path),
													os.path.basename(path))
								dst_paths = [path]
							if os.path.isfile(reshade_fx_path):
								# Alter existing ReShade.fx
								with open(reshade_fx_path, "rb") as reshade_fx_file:
									reshade_fx = reshade_fx_file.read()
								# Remove existing shader include
								reshade_fx = re.sub(r'[ \t]*//\s*Automatically\s+\S+\s+by\s+%s\s+.+[ \t]*\r?\n?' %
													appname, "", reshade_fx)
								reshade_fx = re.sub(r'[ \t]*#include\s+"ColorLookupTable.fx"[ \t]*\r?\n?',
												    "", reshade_fx).rstrip("\r\n")
							else:
								reshade_fx = ""
							if reshade_fx:
								reshade_fx += "%s// Automatically added by %s %s%s" % (os.linesep * 2, appname, version, os.linesep)
							else:
								reshade_fx = "// Automatically created by %s %s%s" % (appname, version, os.linesep)
							reshade_fx += '#include "ColorLookupTable.fx"' + os.linesep
							clut_fx_path = os.path.join(os.path.dirname(path),
														"ColorLookupTable.fx")
							with open(clut_fx_path, "wb") as clut_fx_file:
								clut_fx_file.write(clut_fx)
							if not os.path.isdir(os.path.join(dst_dir,
															  "reshade-shaders")):
								# ReShade < 3.0
								with open(reshade_fx_path, "wb") as reshade_fx_file:
									reshade_fx_file.write(reshade_fx)
					for src_path, dst_path in zip(src_paths, dst_paths):
						shutil.copyfile(src_path, dst_path)
					return
				self.worker.interactive = False
				self.worker.start(self.lut3d_create_consumer,
								  self.lut3d_create_producer,
								  wargs=(profile_in, profile_abst, profile_out,
										 path),
								  progress_msg=lang.getstr("3dlut.create"),
								  resume=not isinstance(self, LUT3DFrame) and
										 getcfg("3dlut.create"))
	
	def lut3d_create_producer(self, profile_in, profile_abst, profile_out, path):
		apply_cal = (profile_out and isinstance(profile_out.tags.get("vcgt"),
												ICCP.VideoCardGammaType) and
					 (getcfg("3dlut.output.profile.apply_cal") or
					  not hasattr(self, "lut3d_apply_cal_cb")))
		input_encoding = getcfg("3dlut.encoding.input")
		output_encoding = getcfg("3dlut.encoding.output")
		if (getcfg("3dlut.apply_trc") or
			not hasattr(self, "lut3d_trc_apply_none_ctrl")):
			if getcfg("3dlut.trc").startswith("smpte2084"):
				trc_gamma = getcfg("3dlut.trc")
			else:
				trc_gamma = getcfg("3dlut.trc_gamma")
		else:
			trc_gamma = None
		XYZwp = None
		if not isinstance(self, LUT3DFrame):
			x = getcfg("3dlut.whitepoint.x", False)
			y = getcfg("3dlut.whitepoint.y", False)
			if x and y:
				XYZwp = colormath.xyY2XYZ(x, y)
		trc_gamma_type = getcfg("3dlut.trc_gamma_type")
		outoffset = getcfg("3dlut.trc_output_offset")
		intent = getcfg("3dlut.rendering_intent")
		format = getcfg("3dlut.format")
		size = getcfg("3dlut.size")
		input_bits = getcfg("3dlut.bitdepth.input")
		output_bits = getcfg("3dlut.bitdepth.output")
		apply_black_offset = getcfg("3dlut.apply_black_offset")
		use_b2a = getcfg("3dlut.gamap.use_b2a")
		white_cdm2 = getcfg("3dlut.hdr_peak_luminance")
		maxcll = getcfg("3dlut.hdr_maxcll")
		content_rgb_space = [-2084, [], [], [], []]
		for i, color in enumerate(("white", "red", "green", "blue")):
			for coord in "xy":
				v = getcfg("3dlut.content.colorspace.%s.%s" % (color, coord))
				content_rgb_space[i + 1].append(v)
			# Dummy Y value, not used for primaries but needs to be present
			content_rgb_space[i + 1].append(1.0)
		content_rgb_space[1] = colormath.xyY2XYZ(*content_rgb_space[1])
		content_rgb_space = colormath.get_rgb_space(content_rgb_space)
		try:
			self.worker.create_3dlut(profile_in, path, profile_abst,
									 profile_out, apply_cal=apply_cal,
									 intent=intent, format=format, size=size,
									 input_bits=input_bits,
									 output_bits=output_bits,
									 input_encoding=input_encoding,
									 output_encoding=output_encoding,
									 trc_gamma=trc_gamma,
									 trc_gamma_type=trc_gamma_type,
									 trc_output_offset=outoffset,
									 apply_black_offset=apply_black_offset,
									 use_b2a=use_b2a, white_cdm2=white_cdm2,
									 maxcll=maxcll,
									 content_rgb_space=content_rgb_space,
									 hdr_display=getcfg("3dlut.hdr_display"),
									 XYZwp=XYZwp)
		except Exception, exception:
			return exception
		return True
	
	def lut3d_format_ctrl_handler(self, event):
		# Get selected format
		format = self.lut3d_formats_ab[self.lut3d_format_ctrl.GetSelection()]
		if getcfg("3dlut.format") in ("eeColor",
									  "madVR",
									  "ReShade") and format not in ("eeColor",
																	"madVR",
																	"ReShade"):
			# If previous format was eeColor/madVR/ReShade, restore 3D LUT encoding
			setcfg("3dlut.encoding.input", getcfg("3dlut.encoding.input.backup"))
			setcfg("3dlut.encoding.output", getcfg("3dlut.encoding.output.backup"))
		if getcfg("3dlut.format") in ("eeColor", "madVR", "mga", "ReShade"):
			setcfg("3dlut.size", getcfg("3dlut.size.backup"))
		if getcfg("3dlut.format") not in ("eeColor",
										  "madVR",
										  "ReShade") and format in ("eeColor",
																	"madVR",
																	"ReShade"):
			# If selected format is eeColor/madVR/ReShade, backup 3D LUT encoding
			setcfg("3dlut.encoding.input.backup", getcfg("3dlut.encoding.input"))
			setcfg("3dlut.encoding.output.backup", getcfg("3dlut.encoding.output"))
		# Set selected format
		self.lut3d_set_option("3dlut.format", format)
		if format in ("eeColor", "madVR", "mga", "ReShade"):
			setcfg("3dlut.size.backup", getcfg("3dlut.size"))
		if format == "eeColor":
			# -et -Et for eeColor
			if getcfg("3dlut.encoding.input") not in ("t", "T"):
				self.lut3d_set_option("3dlut.encoding.input", "t")
			self.lut3d_set_option("3dlut.encoding.output", "t")
			# eeColor uses a fixed size of 65x65x65
			self.lut3d_set_option("3dlut.size", 65)
		elif format == "mga":
			# Pandora uses a fixed bitdepth of 16
			self.lut3d_set_option("3dlut.bitdepth.output", 16)
			self.lut3d_bitdepth_output_ctrl.SetSelection(self.lut3d_bitdepth_ba[16])
		elif format == "madVR":
			# -et -Et for madVR
			if getcfg("3dlut.encoding.input") not in ("t", "T"):
				self.lut3d_set_option("3dlut.encoding.input", "t")
			self.lut3d_set_option("3dlut.encoding.output", "t")
			# collink says madVR works best with 65
			self.lut3d_set_option("3dlut.size", 65)
		elif format in ("png", "ReShade"):
			if format == "ReShade":
				self.lut3d_set_option("3dlut.encoding.input", "n")
				self.lut3d_set_option("3dlut.encoding.output", "n")
				self.lut3d_set_option("3dlut.bitdepth.output", 8)
			elif getcfg("3dlut.bitdepth.output") not in (8, 16):
				self.lut3d_set_option("3dlut.bitdepth.output", 8)
			self.lut3d_bitdepth_output_ctrl.SetSelection(self.lut3d_bitdepth_ba[getcfg("3dlut.bitdepth.output")])
		size = getcfg("3dlut.size")
		snap_size = self.lut3d_snap_size(size)
		if snap_size != size:
			self.lut3d_set_option("3dlut.size", snap_size)
		self.lut3d_size_ctrl.SetSelection(self.lut3d_size_ba[getcfg("3dlut.size")])
		self.lut3d_update_encoding_controls()
		self.lut3d_enable_size_controls()
		self.lut3d_show_bitdepth_controls()
		if not isinstance(self, LUT3DFrame):
			self.panel.Freeze()
			self.lut3d_show_controls()
			self.calpanel.Layout()
			self.update_main_controls()
			self.panel.Thaw()
			if getattr(self, "lut3dframe", None):
				self.lut3dframe.lut3d_update_shared_controls()
			return
		else:
			self.panel.Freeze()
			self.lut3d_show_hdr_display_control()
			self.panel.Layout()
			self.panel.Thaw()
			self.update_layout()
			if self.Parent:
				self.Parent.lut3d_update_shared_controls()
		self.lut3d_create_btn.Enable(format != "madVR" or
									 self.output_profile_ctrl.IsShown())
	
	def lut3d_size_ctrl_handler(self, event):
		size = self.lut3d_size_ab[self.lut3d_size_ctrl.GetSelection()]
		snap_size = self.lut3d_snap_size(size)
		if snap_size != size:
			wx.Bell()
			self.lut3d_size_ctrl.SetSelection(self.lut3d_size_ba[snap_size])
		self.lut3d_set_option("3dlut.size", snap_size)
		if getattr(self, "lut3dframe", None):
			self.lut3dframe.lut3d_update_shared_controls()
		elif self.Parent:
			self.Parent.lut3d_update_shared_controls()

	def lut3d_snap_size(self, size):
		if getcfg("3dlut.format") == "mga" and size not in (17, 33):
			if size < 33:
				size = 17
			else:
				size = 33
		elif getcfg("3dlut.format") == "ReShade" and size not in (16, 32, 64):
			if size < 32:
				size = 16
			elif size < 64:
				size = 32
			else:
				size = 64
		return size
	
	def output_profile_ctrl_handler(self, event):
		self.set_profile("output", silent=not event)
	
	def output_profile_current_ctrl_handler(self, event):
		profile_path = get_current_profile_path(True, True)
		if profile_path and os.path.isfile(profile_path):
			self.output_profile_ctrl.SetPath(profile_path)
			self.set_profile("output", profile_path or False, silent=not event)

	def lut3d_gamut_mapping_mode_handler(self, event):
		self.lut3d_set_option("3dlut.gamap.use_b2a",
							  int(self.gamut_mapping_b2a.GetValue()))
		if getattr(self, "lut3dframe", None):
			self.lut3dframe.update_controls()
		elif self.Parent:
			self.Parent.lut3d_update_b2a_controls()

	def get_commands(self):
		return self.get_common_commands() + ["3DLUT-maker [create <filename>]"]

	def process_data(self, data):
		if data[0] == "3DLUT-maker" and (len(data) == 1 or
										 (len(data) == 3 and
										  data[1] == "create")):
			if self.IsIconized():
				self.Restore()
			self.Raise()
			if len(data) == 3:
				wx.CallAfter(self.lut3d_create_handler,
							 CustomEvent(wx.EVT_BUTTON.evtType[0],
										 self.lut3d_create_btn), path=data[2])
			return "ok"
		return "invalid"
	
	def lut3d_rendering_intent_ctrl_handler(self, event):
		self.lut3d_set_option("3dlut.rendering_intent",
			   self.rendering_intents_ab[self.lut3d_rendering_intent_ctrl.GetSelection()])
		if getattr(self, "lut3dframe", None):
			self.lut3dframe.lut3d_update_shared_controls()
		else:
			if hasattr(self, "lut3d_show_input_value_clipping_warning"):
				self.lut3d_show_input_value_clipping_warning(True)
			if self.Parent:
				self.Parent.lut3d_update_shared_controls()
	
	def set_profile(self, which, profile_path=None, silent=False):
		path = getattr(self, "%s_profile_ctrl" % which).GetPath()
		if which == "output":
			if profile_path is None:
				profile_path = get_current_profile_path(True, True)
			self.output_profile_current_btn.Enable(self.output_profile_ctrl.IsShown() and
												   bool(profile_path) and
												   os.path.isfile(profile_path) and
												   profile_path != path)
		if path:
			if not os.path.isfile(path):
				if not silent:
					show_result_dialog(Error(lang.getstr("file.missing", path)),
									   parent=self)
				return
			try:
				profile = ICCP.ICCProfile(path)
			except (IOError, ICCP.ICCProfileInvalidError):
				if not silent:
					show_result_dialog(Error(lang.getstr("profile.invalid") +
											 "\n" + path),
									   parent=self)
			except IOError, exception:
				if not silent:
					show_result_dialog(exception, parent=self)
			else:
				if ((which in ("input", "output") and
					 (profile.profileClass not in ("mntr", "link", "scnr", "spac") or 
					  profile.colorSpace != "RGB")) or
					(which == "abstract" and
					 (profile.profileClass != "abst" or profile.colorSpace
					  not in ("Lab", "XYZ")))):
					show_result_dialog(NotImplementedError(lang.getstr("profile.unsupported", 
																	   (profile.profileClass, 
																		profile.colorSpace))),
									   parent=self)
				else:
					if profile.profileClass == "link":
						if which == "output":
							self.input_profile_ctrl.SetPath(path)
							if getcfg("3dlut.output.profile") == path:
								# The original file was probably overwritten
								# by the device link. Reset.
								setcfg("3dlut.output.profile", None)
							self.output_profile_ctrl.SetPath(getcfg("3dlut.output.profile"))
							self.set_profile("input", silent=silent)
							return
						else:
							self.Freeze()
							self.abstract_profile_cb.SetValue(False)
							self.abstract_profile_cb.Hide()
							self.abstract_profile_ctrl.Hide()
							self.output_profile_label.Hide()
							self.output_profile_ctrl.Hide()
							self.output_profile_current_btn.Hide()
							self.lut3d_apply_cal_cb.Hide()
							self.lut3d_trc_label.Hide()
							self.lut3d_trc_apply_none_ctrl.Hide()
							self.lut3d_input_value_clipping_bmp.Hide()
							self.lut3d_input_value_clipping_label.Hide()
							self.lut3d_trc_apply_black_offset_ctrl.Hide()
							self.gamut_mapping_mode.Hide()
							self.gamut_mapping_inverse_a2b.Hide()
							self.gamut_mapping_b2a.Hide()
							self.lut3d_show_encoding_controls(False)
							self.lut3d_show_trc_controls(False)
							self.lut3d_rendering_intent_label.Hide()
							self.lut3d_rendering_intent_ctrl.Hide()
							self.panel.GetSizer().Layout()
							self.update_layout()
							self.Thaw()
					else:
						if which == "input":
							if (not hasattr(self, which + "_profile") or
								getcfg("3dlut.%s.profile" % which) !=
								profile.fileName):
								# Get profile blackpoint so we can check if it makes
								# sense to show TRC type and output offset controls
								try:
									odata = self.worker.xicclu(profile, (0, 0, 0),
															   pcs="x")
								except Exception, exception:
									show_result_dialog(exception, self)
									self.set_profile_ctrl_path(which)
									return
								else:
									if len(odata) != 1 or len(odata[0]) != 3:
										show_result_dialog("Blackpoint is invalid: %s"
														   % odata, self)
										self.set_profile_ctrl_path(which)
										return
									self.XYZbpin = odata[0]
							self.Freeze()
							self.lut3d_trc_label.Show()
							self.lut3d_trc_apply_none_ctrl.Show()
							self.lut3d_trc_apply_black_offset_ctrl.Show()
							self.gamut_mapping_mode.Show()
							self.gamut_mapping_inverse_a2b.Show()
							self.gamut_mapping_b2a.Show()
							enable = bool(getcfg("3dlut.use_abstract_profile"))
							self.abstract_profile_cb.SetValue(enable)
							self.abstract_profile_cb.Show()
							self.abstract_profile_ctrl.Enable(enable)
							self.abstract_profile_ctrl.Show()
							self.output_profile_label.Show()
							self.output_profile_ctrl.Show()
							self.output_profile_current_btn.Show()
							self.lut3d_apply_cal_cb.Show()
							self.lut3d_show_encoding_controls()
							self.lut3d_update_encoding_controls()
							# Update controls related to output profile
							setattr(self, "input_profile", profile)
							if not self.set_profile("output", silent=silent):
								self.update_linking_controls()
						elif which == "output":
							if (not hasattr(self, which + "_profile") or
								getcfg("3dlut.%s.profile" % which) !=
								profile.fileName):
								# Get profile blackpoint so we can check if input
								# values would be clipped
								try:
									odata = self.worker.xicclu(profile, (0, 0, 0),
															   pcs="x")
								except Exception, exception:
									show_result_dialog(exception, self)
									self.set_profile_ctrl_path(which)
									return
								else:
									if len(odata) != 1 or len(odata[0]) != 3:
										show_result_dialog("Blackpoint is invalid: %s"
														   % odata, self)
										self.set_profile_ctrl_path(which)
										return
									self.XYZbpout = odata[0]
							self.Freeze()
							enable_apply_cal = (isinstance(profile.tags.get("vcgt"),
														   ICCP.VideoCardGammaType))
							self.lut3d_apply_cal_cb.SetValue(enable_apply_cal and
													   bool(getcfg("3dlut.output.profile.apply_cal")))
							self.lut3d_apply_cal_cb.Enable(enable_apply_cal)
							self.gamut_mapping_inverse_a2b.Enable()
							allow_b2a_gamap = ("B2A0" in profile.tags and
											   isinstance(profile.tags.B2A0,
														  ICCP.LUT16Type) and
											   profile.tags.B2A0.clut_grid_steps >= 17)
							# Allow using B2A instead of inverse A2B?
							self.gamut_mapping_b2a.Enable(allow_b2a_gamap)
							if not allow_b2a_gamap:
								setcfg("3dlut.gamap.use_b2a", 0)
							self.update_linking_controls()
							self.lut3d_trc_apply_ctrl_handler()
							self.lut3d_rendering_intent_label.Show()
							self.lut3d_rendering_intent_ctrl.Show()
						self.panel.GetSizer().Layout()
						self.update_layout()
						self.Thaw()
					setattr(self, "%s_profile" % which, profile)
					if which == "output" and not self.output_profile_ctrl.IsShown():
						return
					setcfg("3dlut.%s.profile" % which, profile.fileName)
					self.lut3d_create_btn.Enable(bool(getcfg("3dlut.input.profile")) and
												 os.path.isfile(getcfg("3dlut.input.profile")) and
												 ((bool(getcfg("3dlut.output.profile")) and
												   os.path.isfile(getcfg("3dlut.output.profile"))) or
												  profile.profileClass == "link") and
												 (getcfg("3dlut.format") != "madVR" or
												  self.output_profile_ctrl.IsShown()))
					return profile
			self.set_profile_ctrl_path(which)
		else:
			if which == "input":
				self.set_profile_ctrl_path(which)
				self.lut3d_update_encoding_controls()
			else:
				if not silent:
					setattr(self, "%s_profile" % which, None)
					setcfg("3dlut.%s.profile" % which, None)
					if which == "output":
						self.lut3d_apply_cal_cb.Disable()
						self.lut3d_create_btn.Disable()

	def set_profile_ctrl_path(self, which):
		getattr(self, "%s_profile_ctrl" %
					  which).SetPath(getcfg("3dlut.%s.profile" % which))
	
	def setup_language(self):
		BaseFrame.setup_language(self)
		
		for which in ("input", "abstract", "output"):
			msg = {"input": lang.getstr("3dlut.input.profile"),
				   "abstract": lang.getstr("3dlut.use_abstract_profile"),
				   "output": lang.getstr("output.profile")}[which]
			kwargs = dict(toolTip=msg.rstrip(":"),
						  dialogTitle=msg,
						  fileMask=lang.getstr("filetype.icc")
								   + "|*.icc;*.icm")
			ctrl = getattr(self, "%s_profile_ctrl" % which)
			for name, value in kwargs.iteritems():
				setattr(ctrl, name, value)

		self.lut3d_setup_language()

	def lut3d_setup_language(self):
		# Shared with main window
		items = []
		for item in ("Gamma 2.2", "trc.rec1886", "trc.smpte2084.hardclip",
					 "trc.smpte2084.rolloffclip", "custom"):
			items.append(lang.getstr(item))
		self.lut3d_trc_ctrl.SetItems(items)
		
		self.trc_gamma_types_ab = {0: "b", 1: "B"}
		self.trc_gamma_types_ba = {"b": 0, "B": 1}
		self.lut3d_trc_gamma_type_ctrl.SetItems([lang.getstr("trc.type.relative"),
											  lang.getstr("trc.type.absolute")])

		self.lut3d_content_colorspace_names = ["Rec. 2020", "DCI P3", "Rec. 709"]
		self.lut3d_content_colorspace_ctrl.SetItems(self.lut3d_content_colorspace_names +
													[lang.getstr("custom")])

		self.rendering_intents_ab = {}
		self.rendering_intents_ba = {}
		self.lut3d_rendering_intent_ctrl.Clear()
		intents = list(config.valid_values["3dlut.rendering_intent"])
		if self.worker.argyll_version < [1, 8, 3]:
			intents.remove("lp")
		for i, ri in enumerate(intents):
			self.lut3d_rendering_intent_ctrl.Append(lang.getstr("gamap.intents." + ri))
			self.rendering_intents_ab[i] = ri
			self.rendering_intents_ba[ri] = i
		
		self.lut3d_formats_ab = {}
		self.lut3d_formats_ba = {}
		self.lut3d_format_ctrl.Clear()
		i = 0
		for format in config.valid_values["3dlut.format"]:
			if format != "madVR" or self.worker.argyll_version >= [1, 6]:
				self.lut3d_format_ctrl.Append(lang.getstr("3dlut.format.%s" % format))
				self.lut3d_formats_ab[i] = format
				self.lut3d_formats_ba[format] = i
				i += 1

		self.lut3d_hdr_display_ctrl.SetItems([lang.getstr(item)
											  for item in
											  ("3dlut.format.madVR.hdr_to_sdr",
											   "3dlut.format.madVR.hdr")])
		
		self.lut3d_size_ab = {}
		self.lut3d_size_ba = {}
		self.lut3d_size_ctrl.Clear()
		for i, size in enumerate(config.valid_values["3dlut.size"]):
			self.lut3d_size_ctrl.Append("%sx%sx%s" % ((size, ) * 3))
			self.lut3d_size_ab[i] = size
			self.lut3d_size_ba[size] = i
		
		self.lut3d_bitdepth_ab = {}
		self.lut3d_bitdepth_ba = {}
		self.lut3d_bitdepth_input_ctrl.Clear()
		self.lut3d_bitdepth_output_ctrl.Clear()
		for i, bitdepth in enumerate(config.valid_values["3dlut.bitdepth.input"]):
			self.lut3d_bitdepth_input_ctrl.Append(str(bitdepth))
			self.lut3d_bitdepth_output_ctrl.Append(str(bitdepth))
			self.lut3d_bitdepth_ab[i] = bitdepth
			self.lut3d_bitdepth_ba[bitdepth] = i
	
	def lut3d_setup_encoding_ctrl(self):
		format = getcfg("3dlut.format")
		# Shared with amin window
		if format == "madVR":
			encodings = ["t"]
			config.defaults["3dlut.encoding.input"] = "t"
			config.defaults["3dlut.encoding.output"] = "t"
		else:
			encodings = list(video_encodings)
			config.defaults["3dlut.encoding.input"] = "n"
			config.defaults["3dlut.encoding.output"] = "n"
		if (self.worker.argyll_version >= [1, 7] and
			self.worker.argyll_version != [1, 7, 0, "_beta"]):
			# Argyll 1.7 beta 3 (2015-04-02) added clip WTW on input TV encoding
			encodings.insert(2, "T")
		config.valid_values["3dlut.encoding.input"] = encodings
		# collink: xvYCC output encoding is not supported
		config.valid_values["3dlut.encoding.output"] = filter(lambda v:
															  v not in ("T", "x", "X"),
															  encodings)
		self.encoding_input_ab = {}
		self.encoding_input_ba = {}
		self.encoding_output_ab = {}
		self.encoding_output_ba = {}
		self.encoding_input_ctrl.Freeze()
		self.encoding_input_ctrl.Clear()
		self.encoding_output_ctrl.Freeze()
		self.encoding_output_ctrl.Clear()
		for i, encoding in enumerate(config.valid_values["3dlut.encoding.input"]):
			lstr = lang.getstr("3dlut.encoding.type_%s" % encoding)
			self.encoding_input_ctrl.Append(lstr)
			self.encoding_input_ab[i] = encoding
			self.encoding_input_ba[encoding] = i
		for o, encoding in enumerate(config.valid_values["3dlut.encoding.output"]):
			lstr = lang.getstr("3dlut.encoding.type_%s" % encoding)
			self.encoding_output_ctrl.Append(lstr)
			self.encoding_output_ab[o] = encoding
			self.encoding_output_ba[encoding] = o
		self.encoding_input_ctrl.Thaw()
		self.encoding_output_ctrl.Thaw()

	def lut3d_set_option(self, option, v, set_changed=True):
		""" Set option to value and update settings state """
		if (hasattr(self, "profile_settings_changed") and set_changed and
			getcfg("3dlut.create") and v != getcfg(option)):
			self.profile_settings_changed()
		setcfg(option, v)
	
	def update_controls(self):
		""" Update controls with values from the configuration """
		self.panel.Freeze()
		self.lut3d_create_btn.Disable()
		self.input_profile_ctrl.SetPath(getcfg("3dlut.input.profile"))
		self.output_profile_ctrl.SetPath(getcfg("3dlut.output.profile"))
		self.input_profile_ctrl_handler(None)
		enable = bool(getcfg("3dlut.use_abstract_profile"))
		self.abstract_profile_cb.SetValue(enable)
		self.abstract_profile_ctrl.SetPath(getcfg("3dlut.abstract.profile"))
		self.abstract_profile_ctrl_handler(None)
		self.output_profile_ctrl_handler(None)
		self.lut3d_update_shared_controls()
		self.panel.Thaw()

	def lut3d_update_shared_controls(self):
		# Shared with main window
		self.lut3d_update_trc_controls()
		self.lut3d_rendering_intent_ctrl.SetSelection(self.rendering_intents_ba[getcfg("3dlut.rendering_intent")])
		format = getcfg("3dlut.format")
		if format == "madVR" and self.worker.argyll_version < [1, 6]:
			# MadVR only available with Argyll 1.6+, fall back to IRIDAS .cube
			format = "cube"
			setcfg("3dlut.format", format)
		self.lut3d_format_ctrl.SetSelection(self.lut3d_formats_ba[getcfg("3dlut.format")])
		self.lut3d_hdr_display_ctrl.SetSelection(getcfg("3dlut.hdr_display"))
		self.lut3d_size_ctrl.SetSelection(self.lut3d_size_ba[getcfg("3dlut.size")])
		self.lut3d_enable_size_controls()
		self.lut3d_bitdepth_input_ctrl.SetSelection(self.lut3d_bitdepth_ba[getcfg("3dlut.bitdepth.input")])
		self.lut3d_bitdepth_output_ctrl.SetSelection(self.lut3d_bitdepth_ba[getcfg("3dlut.bitdepth.output")])
		self.lut3d_show_bitdepth_controls()
		if self.Parent:
			self.Parent.lut3d_update_shared_controls()

	def lut3d_update_trc_control(self):
		if getcfg("3dlut.trc").startswith("smpte2084"):  # SMPTE 2084
			if getcfg("3dlut.trc") == "smpte2084.hardclip":
				sel = 2
			else:
				sel = 3
			self.lut3d_trc_ctrl.SetSelection(sel)
		elif (getcfg("3dlut.trc_gamma_type") == "B" and
			getcfg("3dlut.trc_output_offset") == 0 and
			getcfg("3dlut.trc_gamma") == 2.4):
			self.lut3d_trc_ctrl.SetSelection(1)  # BT.1886
			setcfg("3dlut.trc", "bt1886")
		elif (getcfg("3dlut.trc_gamma_type") == "b" and
			getcfg("3dlut.trc_output_offset") == 1 and
			getcfg("3dlut.trc_gamma") == 2.2):
			self.lut3d_trc_ctrl.SetSelection(0)  # Pure power gamma 2.2
			setcfg("3dlut.trc", "gamma2.2")
		else:
			self.lut3d_trc_ctrl.SetSelection(4)  # Custom
			setcfg("3dlut.trc", "customgamma")

	def lut3d_update_trc_controls(self):
		self.lut3d_update_trc_control()
		self.lut3d_trc_gamma_ctrl.SetValue(str(getcfg("3dlut.trc_gamma")))
		self.lut3d_trc_gamma_type_ctrl.SetSelection(self.trc_gamma_types_ba[getcfg("3dlut.trc_gamma_type")])
		outoffset = int(getcfg("3dlut.trc_output_offset") * 100)
		self.lut3d_trc_black_output_offset_ctrl.SetValue(outoffset)
		self.lut3d_trc_black_output_offset_intctrl.SetValue(outoffset)
		self.lut3d_hdr_peak_luminance_ctrl.SetValue(getcfg("3dlut.hdr_peak_luminance"))
		self.lut3d_hdr_maxcll_ctrl.SetValue(getcfg("3dlut.hdr_maxcll"))
		# Content colorspace (currently only used for SMPTE 2084)
		content_colors = []
		for color in ("white", "red", "green", "blue"):
			for coord in "xy":
				v = getcfg("3dlut.content.colorspace.%s.%s" % (color, coord))
				getattr(self, "lut3d_content_colorspace_%s_%s" %
							  (color, coord)).SetValue(v)
				content_colors.append(round(v, 4))
		for i, rgb_space in enumerate(self.lut3d_content_colorspace_names):
			rgb_space = colormath.get_rgb_space(rgb_space)
			wx, wy = (round(v, 4) for v in
					  colormath.XYZ2xyY(*colormath.get_whitepoint(rgb_space[1]))[:2])
			colors = [wx, wy]
			for primary in rgb_space[2:5]:
				for j in xrange(2):
					colors.append(round(primary[j], 4))
			if colors == content_colors:
				break
		else:
			i = self.lut3d_content_colorspace_ctrl.Count - 1
		self.lut3d_content_colorspace_ctrl.SetSelection(i)

	def update_linking_controls(self):
		self.gamut_mapping_inverse_a2b.SetValue(
			not getcfg("3dlut.gamap.use_b2a"))
		self.gamut_mapping_b2a.SetValue(
			bool(getcfg("3dlut.gamap.use_b2a")))
		self.lut3d_show_trc_controls()
		if (hasattr(self, "input_profile") and
			"rTRC" in self.input_profile.tags and
			"gTRC" in self.input_profile.tags and
			"bTRC" in self.input_profile.tags and
			self.input_profile.tags.rTRC ==
			self.input_profile.tags.gTRC ==
			self.input_profile.tags.bTRC and
			isinstance(self.input_profile.tags.rTRC,
					   ICCP.CurveType)):
			tf = self.input_profile.tags.rTRC.get_transfer_function(outoffset=1.0)
			if (getcfg("3dlut.input.profile") !=
				self.input_profile.fileName):
				# Use BT.1886 gamma mapping for SMPTE 240M /
				# Rec. 709 TRC
				setcfg("3dlut.apply_trc",
					   int(tf[0][1] in (-240, -709) or
						   (tf[0][0].startswith("Gamma") and tf[1] >= .95)))
				# Use only BT.1886 black output offset
				setcfg("3dlut.apply_black_offset",
					   int(tf[0][1] not in (-240, -709) and
						   (not tf[0][0].startswith("Gamma") or tf[1] < .95) and
						   self.XYZbpin != self.XYZbpout))
			self.lut3d_trc_apply_black_offset_ctrl.Enable(
				tf[0][1] not in (-240, -709) and
				self.XYZbpin != self.XYZbpout)
			# Set gamma to profile gamma if single gamma
			# profile
			if tf[0][0].startswith("Gamma") and tf[1] >= .95:
				if not getcfg("3dlut.trc_gamma.backup", False):
					# Backup current gamma
					setcfg("3dlut.trc_gamma.backup",
						   getcfg("3dlut.trc_gamma"))
				setcfg("3dlut.trc_gamma",
					   round(tf[0][1], 2))
			# Restore previous gamma if not single gamma
			# profile
			elif getcfg("3dlut.trc_gamma.backup", False):
				setcfg("3dlut.trc_gamma",
					   getcfg("3dlut.trc_gamma.backup"))
				setcfg("3dlut.trc_gamma.backup", None)
			self.lut3d_update_trc_controls()
		elif (hasattr(self, "input_profile") and
			  isinstance(self.input_profile.tags.get("A2B0"),
						 ICCP.LUT16Type) and
			  isinstance(self.input_profile.tags.get("A2B1", ICCP.LUT16Type()),
						 ICCP.LUT16Type) and
			  isinstance(self.input_profile.tags.get("A2B2", ICCP.LUT16Type()),
						 ICCP.LUT16Type)):
			self.lut3d_trc_apply_black_offset_ctrl.Enable(self.XYZbpin !=
														  self.XYZbpout)
			if self.XYZbpin == self.XYZbpout:
				setcfg("3dlut.apply_black_offset", 0)
		else:
			self.lut3d_trc_apply_black_offset_ctrl.Disable()
			setcfg("3dlut.apply_black_offset", 0)
		if getcfg("3dlut.apply_black_offset"):
			self.lut3d_trc_apply_black_offset_ctrl.SetValue(True)
		elif getcfg("3dlut.apply_trc"):
			self.lut3d_trc_apply_ctrl.SetValue(True)
		else:
			self.lut3d_trc_apply_none_ctrl.SetValue(True)
	
	def lut3d_show_bitdepth_controls(self):
		frozen = self.IsFrozen()
		if not frozen:
			self.Freeze()
		show = True
		input_show = show and getcfg("3dlut.format") == "3dl"
		self.lut3d_bitdepth_input_label.Show(input_show)
		self.lut3d_bitdepth_input_ctrl.Show(input_show)
		output_show = show and getcfg("3dlut.format") in ("3dl", "png")
		self.lut3d_bitdepth_output_label.Show(output_show)
		self.lut3d_bitdepth_output_ctrl.Show(output_show)
		if isinstance(self, LUT3DFrame):
			self.panel.GetSizer().Layout()
			self.update_layout()
		else:
			self.update_scrollbars()
		if not frozen:
			self.Thaw()

	def lut3d_show_hdr_display_control(self):
		self.lut3d_hdr_display_ctrl.Show((getcfg("3dlut.apply_trc") or
								not hasattr(self, "lut3d_trc_apply_none_ctrl")) and
							   getcfg("3dlut.trc").startswith("smpte2084") and
							   getcfg("3dlut.format") == "madVR")

	def lut3d_show_trc_controls(self, show=True):
		self.panel.Freeze()
		show = show and self.worker.argyll_version >= [1, 6]
		if hasattr(self, "lut3d_trc_apply_ctrl"):
			self.lut3d_trc_apply_ctrl.Show(show)
		self.lut3d_trc_ctrl.Show(show)
		smpte2084 = getcfg("3dlut.trc").startswith("smpte2084")
		show = show and (getcfg("3dlut.trc") == "customgamma" or
						 (isinstance(self, LUT3DFrame) or
						  getcfg("show_advanced_options")))
		self.lut3d_trc_gamma_label.Show(show and not smpte2084)
		self.lut3d_trc_gamma_ctrl.Show(show and not smpte2084)
		smpte2084r = getcfg("3dlut.trc") == "smpte2084.rolloffclip"
		# Show items in this order so we end up with the correct controls shown
		showcc = smpte2084r and (isinstance(self, LUT3DFrame) or
								 getcfg("show_advanced_options"))
		self.lut3d_content_colorspace_label.ContainingSizer.ShowItems(showcc)
		sel = self.lut3d_content_colorspace_ctrl.Selection
		lastsel = self.lut3d_content_colorspace_ctrl.Count - 1
		sizer = self.lut3d_content_colorspace_red_x.ContainingSizer
		sizer.ShowItems(showcc and sel == lastsel)
		self.lut3d_hdr_maxcll_label.Show(show and smpte2084r)
		self.lut3d_hdr_maxcll_ctrl.Show(show and smpte2084r)
		self.lut3d_hdr_maxcll_ctrl_label.Show(show and smpte2084r)
		show = show or smpte2084
		show = show and ((hasattr(self, "lut3d_create_cb") and
						  getcfg("3dlut.create")) or self.XYZbpout > [0, 0, 0])
		self.lut3d_trc_gamma_type_ctrl.Show(show and not smpte2084)
		self.lut3d_trc_black_output_offset_label.Show(show)
		self.lut3d_trc_black_output_offset_ctrl.Show(show)
		self.lut3d_trc_black_output_offset_intctrl.Show(show)
		self.lut3d_trc_black_output_offset_intctrl_label.Show(show)
		self.lut3d_hdr_peak_luminance_label.Show(smpte2084)
		self.lut3d_hdr_peak_luminance_ctrl.Show(smpte2084)
		self.lut3d_hdr_peak_luminance_ctrl_label.Show(smpte2084)
		self.lut3d_show_hdr_display_control()
		self.panel.Layout()
		self.panel.Thaw()
		if isinstance(self, LUT3DFrame):
			self.update_layout()
	
	def lut3d_show_encoding_controls(self, show=True):
		show = show and ((self.worker.argyll_version >= [1, 7] and
						  self.worker.argyll_version != [1, 7, 0, "_beta"]) or
						 self.worker.argyll_version >= [1, 6])
		# Argyll 1.7 beta 3 (2015-04-02) added clip WTW on input TV encoding
		self.encoding_input_label.Show(show)
		self.encoding_input_ctrl.Show(show)
		show = show and self.worker.argyll_version >= [1, 6]
		self.encoding_output_label.Show(show)
		self.encoding_output_ctrl.Show(show)
	
	def lut3d_update_encoding_controls(self):
		self.lut3d_setup_encoding_ctrl()
		self.encoding_input_ctrl.SetSelection(self.encoding_input_ba[getcfg("3dlut.encoding.input")])
		self.encoding_input_ctrl.Enable(self.encoding_input_ctrl.Count > 1)
		self.encoding_output_ctrl.SetSelection(self.encoding_output_ba[getcfg("3dlut.encoding.output")])
		self.encoding_output_ctrl.Enable(getcfg("3dlut.format") != "madVR")
	
	def lut3d_enable_size_controls(self):
		self.lut3d_size_ctrl.Enable(getcfg("3dlut.format")
									not in ("eeColor", "madVR"))
		


def main():
	config.initcfg("3DLUT-maker")
	lang.init()
	lang.update_defaults()
	app = BaseApp(0)
	app.TopWindow = LUT3DFrame(setup=False)
	if sys.platform == "darwin":
		app.TopWindow.init_menubar()
	wx.CallLater(1, _main, app)
	app.MainLoop()

def _main(app):
	app.TopWindow.listen()
	app.TopWindow.setup()
	app.TopWindow.Show()

if __name__ == "__main__":
	main()
