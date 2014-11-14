# -*- coding: utf-8 -*-

import os
import sys

from config import (get_data_path, get_verified_path, getcfg, geticon, hascfg,
					setcfg)
from log import safe_print
from meta import name as appname
from util_os import waccess
from worker import Error, get_current_profile_path, show_result_dialog
import ICCProfile as ICCP
import config
import localization as lang
import worker
from worker import check_set_argyll_bin
from wxwindows import (BaseApp, BaseFrame, ConfirmDialog, FileDrop, InfoDialog,
					   wx)
import xh_filebrowsebutton

from wx import xrc


class LUT3DFrame(BaseFrame):

	""" 3D LUT creation window """
	
	def __init__(self, parent=None):
		self.res = xrc.XmlResource(get_data_path(os.path.join("xrc", 
															  "3dlut.xrc")))
		self.res.InsertHandler(xh_filebrowsebutton.FileBrowseButtonWithHistoryXmlHandler())
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
		self.apply_cal_cb.Bind(wx.EVT_CHECKBOX, self.apply_cal_ctrl_handler)
		self.encoding_input_ctrl.Bind(wx.EVT_CHOICE,
											self.encoding_input_ctrl_handler)
		self.encoding_output_ctrl.Bind(wx.EVT_CHOICE,
									   self.encoding_output_ctrl_handler)
		self.apply_trc_cb.Bind(wx.EVT_CHECKBOX, self.apply_trc_ctrl_handler)
		self.trc_ctrl.Bind(wx.EVT_CHOICE, self.trc_ctrl_handler)
		self.trc_gamma_ctrl.Bind(wx.EVT_COMBOBOX,
								 self.trc_gamma_ctrl_handler)
		self.trc_gamma_ctrl.Bind(wx.EVT_KILL_FOCUS,
								 self.trc_gamma_ctrl_handler)
		self.trc_gamma_type_ctrl.Bind(wx.EVT_CHOICE,
									  self.trc_gamma_type_ctrl_handler)
		self.black_output_offset_ctrl.Bind(wx.EVT_SLIDER,
										   self.black_output_offset_ctrl_handler)
		self.black_output_offset_intctrl.Bind(wx.EVT_TEXT,
											  self.black_output_offset_ctrl_handler)
		self.rendering_intent_ctrl.Bind(wx.EVT_CHOICE,
										self.rendering_intent_ctrl_handler)
		self.lut3d_format_ctrl.Bind(wx.EVT_CHOICE,
									self.lut3d_format_ctrl_handler)
		self.lut3d_size_ctrl.Bind(wx.EVT_CHOICE,
								  self.lut3d_size_ctrl_handler)
		self.lut3d_bitdepth_input_ctrl.Bind(wx.EVT_CHOICE,
											self.lut3d_bitdepth_input_ctrl_handler)
		self.lut3d_bitdepth_output_ctrl.Bind(wx.EVT_CHOICE,
											 self.lut3d_bitdepth_output_ctrl_handler)
		self.lut3d_create_btn.Bind(wx.EVT_BUTTON, self.lut3d_create_handler)
		
		self.lut3d_create_btn.SetDefault()
		
		self.setup_language()
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
	
	def OnClose(self, event=None):
		if (getattr(self.worker, "thread", None) and
			self.worker.thread.isAlive()):
			self.worker.abort_subprocess(True)
			return
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
		self.abstract_profile_desc.Enable(enable)
	
	def apply_trc_ctrl_handler(self, event=None):
		v = self.apply_trc_cb.GetValue()
		self.trc_ctrl.Enable(v)
		self.trc_gamma_label.Enable(v)
		self.trc_gamma_ctrl.Enable(v)
		self.trc_gamma_type_ctrl.Enable(v)
		if event:
			setcfg("3dlut.apply_trc", int(v))
		self.black_output_offset_label.Enable(v)
		self.black_output_offset_ctrl.Enable(v)
		self.black_output_offset_intctrl.Enable(v)
		self.black_output_offset_intctrl_label.Enable(v)
	
	def apply_cal_ctrl_handler(self, event):
		setcfg("3dlut.output.profile.apply_cal",
			   int(self.apply_cal_cb.GetValue()))

	def black_output_offset_ctrl_handler(self, event):
		if event.GetId() == self.black_output_offset_intctrl.GetId():
			self.black_output_offset_ctrl.SetValue(
				self.black_output_offset_intctrl.GetValue())
		else:
			self.black_output_offset_intctrl.SetValue(
				self.black_output_offset_ctrl.GetValue())
		v = self.black_output_offset_ctrl.GetValue() / 100.0
		if v > 0:
			self.trc_ctrl.SetSelection(1)  # Gamma
		setcfg("3dlut.trc_output_offset", v)
		self.update_trc_control()

	def trc_gamma_ctrl_handler(self, event):
		try:
			v = float(self.trc_gamma_ctrl.GetValue().replace(",", "."))
			if (v < config.valid_ranges["3dlut.trc_gamma"][0] or
				v > config.valid_ranges["3dlut.trc_gamma"][1]):
				raise ValueError()
		except ValueError:
			wx.Bell()
			self.trc_gamma_ctrl.SetValue(str(getcfg("3dlut.trc_gamma")))
		else:
			if str(v) != self.trc_gamma_ctrl.GetValue():
				self.trc_gamma_ctrl.SetValue(str(v))
			setcfg("3dlut.trc_gamma", v)
			self.update_trc_control()
		event.Skip()

	def trc_ctrl_handler(self, event):
		if self.trc_ctrl.GetSelection() == 0:
			# BT.1886
			setcfg("3dlut.trc_gamma", 2.4)
			setcfg("3dlut.trc_gamma_type", "B")
			setcfg("3dlut.trc_output_offset", 0.0)
			self.update_trc_controls()

	def trc_gamma_type_ctrl_handler(self, event):
		setcfg("3dlut.trc_gamma_type",
			   self.trc_gamma_types_ab[self.trc_gamma_type_ctrl.GetSelection()])
		self.update_trc_control()

	def abstract_drop_handler(self, path):
		if not self.worker.is_working():
			self.abstract_profile_ctrl.SetPath(path)
			self.set_profile("abstract")
	
	def encoding_input_ctrl_handler(self, event):
		encoding = self.encoding_ab[self.encoding_input_ctrl.GetSelection()]
		setcfg("3dlut.encoding.input", encoding)
		if getcfg("3dlut.format") == "eeColor":
			self.encoding_output_ctrl.SetSelection(self.encoding_ba[encoding])
			setcfg("3dlut.encoding.output", encoding)
	
	def encoding_output_ctrl_handler(self, event):
		encoding = self.encoding_ab[self.encoding_output_ctrl.GetSelection()]
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
					self.encoding_ba[getcfg("3dlut.encoding.output")])
				return False
		setcfg("3dlut.encoding.output", encoding)

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
	
	def lut3d_bitdepth_input_ctrl_handler(self, event):
		setcfg("3dlut.bitdepth.input",
			   self.lut3d_bitdepth_ab[self.lut3d_bitdepth_input_ctrl.GetSelection()])
	
	def lut3d_bitdepth_output_ctrl_handler(self, event):
		setcfg("3dlut.bitdepth.output",
			   self.lut3d_bitdepth_ab[self.lut3d_bitdepth_output_ctrl.GetSelection()])
	
	def lut3d_create_consumer(self, result=None):
		if isinstance(result, Exception) and result:
			show_result_dialog(result, self)
		# Remove temporary files
		self.worker.wrapup(False)
	
	def lut3d_create_handler(self, event, path=None):
		if not check_set_argyll_bin():
			return
		profile_in = self.set_profile("input")
		if getcfg("3dlut.use_abstract_profile"):
			profile_abst = self.set_profile("abstract")
		else:
			profile_abst = None
		profile_out = self.set_profile("output")
		if (not None in (profile_in, profile_out) or
			(profile_in and profile_in.profileClass == "link")):
			if profile_out and profile_in.isSame(profile_out,
												 force_calculation=True):
				show_result_dialog(Error(lang.getstr("error.source_dest_same")),
								   self)
				return
			checkoverwrite = True
			if not path:
				defaultDir, defaultFile = get_verified_path("last_3dlut_path")
				ext = getcfg("3dlut.format")
				if ext == "eeColor":
					ext = "txt"
				elif ext == "madVR":
					ext = "3dlut"
				defaultFile = os.path.splitext(defaultFile or
											   os.path.basename(config.defaults.get("last_3dlut_path")))[0] + "." + ext
				dlg = wx.FileDialog(self, 
									lang.getstr("3dlut.create"),
									defaultDir=defaultDir,
									defaultFile=defaultFile,
									wildcard="*." + ext, 
									style=wx.SAVE | wx.FD_OVERWRITE_PROMPT)
				dlg.Center(wx.BOTH)
				if dlg.ShowModal() == wx.ID_OK:
					path = dlg.GetPath()
				dlg.Destroy()
				checkoverwrite = False
			if path:
				if not waccess(path, os.W_OK):
					show_result_dialog(Error(lang.getstr("error.access_denied.write",
														 path)),
									   self)
					return
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
				else:
					config.writecfg(module="3DLUT-maker",
									options=("3dlut.", "last_3dlut_path",
											 "position.lut3dframe",
											 "size.lut3dframe"))
				self.worker.interactive = False
				self.worker.start(self.lut3d_create_consumer,
								  self.lut3d_create_producer,
								  wargs=(profile_in, profile_abst, profile_out,
										 path),
								  progress_msg=lang.getstr("3dlut.create"))
	
	def lut3d_create_producer(self, profile_in, profile_abst, profile_out, path):
		apply_cal = (profile_out and "vcgt" in profile_out.tags and
					 getcfg("3dlut.output.profile.apply_cal"))
		input_encoding = getcfg("3dlut.encoding.input")
		output_encoding = getcfg("3dlut.encoding.output")
		if getcfg("3dlut.apply_trc"):
			trc_gamma = getcfg("3dlut.trc_gamma")
		else:
			trc_gamma = None
		trc_gamma_type = getcfg("3dlut.trc_gamma_type")
		outoffset = getcfg("3dlut.trc_output_offset")
		intent = getcfg("3dlut.rendering_intent")
		format = getcfg("3dlut.format")
		size = getcfg("3dlut.size")
		input_bits = getcfg("3dlut.bitdepth.input")
		output_bits = getcfg("3dlut.bitdepth.output")
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
									 trc_output_offset=outoffset)
		except Exception, exception:
			return exception
	
	def lut3d_format_ctrl_handler(self, event):
		if getcfg("3dlut.format") in ("eeColor", "madVR"):
			# If previous format was eeColor or madVR, restore 3D LUT encoding
			setcfg("3dlut.encoding.input", getcfg("3dlut.encoding.input.backup"))
			setcfg("3dlut.encoding.output", getcfg("3dlut.encoding.output.backup"))
		format = self.lut3d_formats_ab[self.lut3d_format_ctrl.GetSelection()]
		setcfg("3dlut.format", format)
		if format in ("eeColor", "madVR"):
			setcfg("3dlut.encoding.input.backup", getcfg("3dlut.encoding.input"))
			setcfg("3dlut.encoding.output.backup", getcfg("3dlut.encoding.output"))
		if format == "eeColor":
			if getcfg("3dlut.encoding.input") == "x":
				# As eeColor usually needs same input & output encoding,
				# and xvYCC output encoding is not supported generally, fall
				# back to Rec601 YCbCr SD for xvYCC Rec601 YCbCr SD
				setcfg("3dlut.encoding.input", "6")
			elif getcfg("3dlut.encoding.input") == "X":
				# As eeColor usually needs same input & output encoding,
				# and xvYCC output encoding is not supported generally, fall
				# back to Rec709 1125/60Hz YCbCr HD for xvYCC Rec709 YCbCr SD
				setcfg("3dlut.encoding.input", "7")
			# eeColor uses a fixed size of 65x65x65
			setcfg("3dlut.size", 65)
			self.lut3d_size_ctrl.SetSelection(self.lut3d_size_ba[65])
		elif format == "mga":
			# Pandora uses a fixed size of 33x33x33
			setcfg("3dlut.size", 33)
			self.lut3d_size_ctrl.SetSelection(self.lut3d_size_ba[33])
			# Pandora uses a fixed bitdepth of 16
			setcfg("3dlut.bitdepth.output", 16)
			self.lut3d_bitdepth_output_ctrl.SetSelection(self.lut3d_bitdepth_ba[16])
		elif format == "madVR":
			# -et -Et for madVR
			setcfg("3dlut.encoding.input", "t")
			setcfg("3dlut.encoding.output", "t")
			# collink says madVR works best with 65
			setcfg("3dlut.size", 65)
			self.lut3d_size_ctrl.SetSelection(self.lut3d_size_ba[65])
		self.setup_encoding_ctrl(format)
		self.update_encoding_controls()
		self.enable_size_controls()
		self.show_bitdepth_controls()
		self.lut3d_create_btn.Enable(format != "madVR" or
									 self.output_profile_ctrl.IsShown())
	
	def lut3d_size_ctrl_handler(self, event):
		setcfg("3dlut.size",
			   self.lut3d_size_ab[self.lut3d_size_ctrl.GetSelection()])
	
	def output_profile_ctrl_handler(self, event):
		self.set_profile("output", silent=not event)
	
	def output_profile_current_ctrl_handler(self, event):
		profile_path = get_current_profile_path()
		if profile_path and os.path.isfile(profile_path):
			self.output_profile_ctrl.SetPath(profile_path)
			self.set_profile("output", profile_path or False, silent=not event)

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
				wx.CallAfter(self.lut3d_create_handler, None, path=data[2])
			return "ok"
		return "invalid"
	
	def rendering_intent_ctrl_handler(self, event):
		setcfg("3dlut.rendering_intent",
			   self.rendering_intents_ab[self.rendering_intent_ctrl.GetSelection()])
	
	def set_profile(self, which, profile_path=None, silent=False):
		path = getattr(self, "%s_profile_ctrl" % which).GetPath()
		if which == "output":
			if profile_path is None:
				profile_path = get_current_profile_path()
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
					show_result_dialog(Error(lang.getstr("profile.invalid")),
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
							self.abstract_profile_cb.SetValue(False)
							self.abstract_profile_cb.Disable()
							self.abstract_profile_ctrl.Disable()
							self.abstract_profile_desc.Disable()
							self.Freeze()
							self.output_profile_label.Hide()
							self.output_profile_ctrl.Hide()
							self.output_profile_current_btn.Hide()
							self.output_profile_desc.Hide()
							self.apply_cal_cb.Hide()
							self.show_encoding_controls(False)
							self.show_trc_controls(False)
							self.rendering_intent_label.Hide()
							self.rendering_intent_ctrl.Hide()
							self.panel.GetSizer().Layout()
							self.update_layout()
							self.Thaw()
					else:
						if which == "input":
							enable = bool(getcfg("3dlut.use_abstract_profile"))
							self.abstract_profile_cb.SetValue(enable)
							self.abstract_profile_cb.Enable()
							self.abstract_profile_ctrl.Enable(enable)
							self.abstract_profile_desc.Enable(enable)
							self.Freeze()
							self.output_profile_label.Show()
							self.output_profile_ctrl.Show()
							self.output_profile_current_btn.Show()
							self.output_profile_desc.Show()
							self.apply_cal_cb.Show()
							self.show_encoding_controls()
							self.update_encoding_controls()
							self.show_trc_controls()
							if (getcfg("3dlut.%s.profile" % which) !=
								profile.fileName and
								"rTRC" in profile.tags and
								"gTRC" in profile.tags and
								"bTRC" in profile.tags and profile.tags.rTRC is
								profile.tags.gTRC is profile.tags.bTRC and
								isinstance(profile.tags.rTRC, ICCP.CurveType)):
								# Use BT.1886 gamma mapping for SMPTE 240M /
								# Rec. 709 TRC
								tf = profile.tags.rTRC.get_transfer_function()
								setcfg("3dlut.apply_trc",
									  int(tf[0][1] in (-240, -709)))
							self.apply_trc_cb.SetValue(bool(getcfg("3dlut.apply_trc")))
							self.apply_trc_ctrl_handler()
							self.rendering_intent_label.Show()
							self.rendering_intent_ctrl.Show()
							# Update controls related to output profile
							self.set_profile("output", silent=silent)
							self.panel.GetSizer().Layout()
							self.update_layout()
							self.Thaw()
						elif which == "output":
							self.apply_cal_cb.SetValue("vcgt" in profile.tags and
													   bool(getcfg("3dlut.output.profile.apply_cal")))
							self.apply_cal_cb.Enable("vcgt" in profile.tags)
					setattr(self, "%s_profile" % which, profile)
					getattr(self, "%s_profile_desc" % which).SetLabel(profile.getDescription())
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
			getattr(self, "%s_profile_ctrl" %
						  which).SetPath(getcfg("3dlut.%s.profile" % which))
		else:
			if which == "input":
				getattr(self, "%s_profile_ctrl" %
							  which).SetPath(getcfg("3dlut.%s.profile" % which))
				self.update_encoding_controls()
			else:
				getattr(self, "%s_profile_desc" % which).SetLabel("")
				if not silent:
					setattr(self, "%s_profile" % which, None)
					setcfg("3dlut.%s.profile" % which, None)
					if which == "output":
						self.apply_cal_cb.Disable()
						self.lut3d_create_btn.Disable()
	
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

		items = []
		for item in ("trc.rec1886", "custom"):
			items.append(lang.getstr(item))
		self.trc_ctrl.SetItems(items)
		
		self.trc_gamma_types_ab = {0: "b", 1: "B"}
		self.trc_gamma_types_ba = {"b": 0, "B": 1}
		self.trc_gamma_type_ctrl.SetItems([lang.getstr("trc.type.relative"),
											  lang.getstr("trc.type.absolute")])
		
		self.rendering_intents_ab = {}
		self.rendering_intents_ba = {}
		self.rendering_intent_ctrl.Clear()
		for i, ri in enumerate(config.valid_values["3dlut.rendering_intent"]):
			self.rendering_intent_ctrl.Append(lang.getstr("gamap.intents." + ri))
			self.rendering_intents_ab[i] = ri
			self.rendering_intents_ba[ri] = i
		
		self.lut3d_formats_ab = {}
		self.lut3d_formats_ba = {}
		self.lut3d_format_ctrl.Clear()
		for i, format in enumerate(config.valid_values["3dlut.format"]):
			if format != "madVR" or self.worker.argyll_version >= [1, 6]:
				self.lut3d_format_ctrl.Append(lang.getstr("3dlut.format.%s" % format))
				self.lut3d_formats_ab[i] = format
				self.lut3d_formats_ba[format] = i
		
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
		
		self.setup_encoding_ctrl(getcfg("3dlut.format"))
	
	def setup_encoding_ctrl(self, format=None):
		if format == "madVR":
			encodings = ["n", "t"]
		else:
			encodings = config.valid_values["3dlut.encoding.input"]
		self.encoding_ab = {}
		self.encoding_ba = {}
		self.encoding_input_ctrl.Freeze()
		self.encoding_input_ctrl.Clear()
		self.encoding_output_ctrl.Freeze()
		self.encoding_output_ctrl.Clear()
		for i, encoding in enumerate(encodings):
			lstr = lang.getstr("3dlut.encoding.type_%s" % encoding)
			if encoding not in ("x", "X") or format != "eeColor":
				# As eeColor usually needs same input & output encoding,
				# and xvYCC output encoding is not supported generally,
				# don't add xvYCC input encoding choices for eeColor
				self.encoding_input_ctrl.Append(lstr)
			if encoding not in ("x", "X"):
				# collink: xvYCC output encoding is not supported
				self.encoding_output_ctrl.Append(lstr)
			self.encoding_ab[i] = encoding
			self.encoding_ba[encoding] = i
		self.encoding_input_ctrl.Thaw()
		self.encoding_output_ctrl.Thaw()
	
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
		self.update_trc_controls()
		self.rendering_intent_ctrl.SetSelection(self.rendering_intents_ba[getcfg("3dlut.rendering_intent")])
		format = getcfg("3dlut.format")
		if format == "madVR" and self.worker.argyll_version < [1, 6]:
			# MadVR only available with Argyll 1.6+, fall back to 3dl
			format = "3dl"
			setcfg("3dlut.format", format)
		self.lut3d_format_ctrl.SetSelection(self.lut3d_formats_ba[getcfg("3dlut.format")])
		self.lut3d_size_ctrl.SetSelection(self.lut3d_size_ba[getcfg("3dlut.size")])
		self.enable_size_controls()
		self.lut3d_bitdepth_input_ctrl.SetSelection(self.lut3d_bitdepth_ba[getcfg("3dlut.bitdepth.input")])
		self.lut3d_bitdepth_output_ctrl.SetSelection(self.lut3d_bitdepth_ba[getcfg("3dlut.bitdepth.output")])
		self.show_bitdepth_controls()
		self.panel.Thaw()

	def update_trc_control(self):
		if (getcfg("3dlut.trc_gamma_type") == "B" and
			getcfg("3dlut.trc_output_offset") == 0 and
			getcfg("3dlut.trc_gamma") == 2.4):
			self.trc_ctrl.SetSelection(0)  # BT.1886
		else:
			self.trc_ctrl.SetSelection(1)  # Gamma

	def update_trc_controls(self):
		self.update_trc_control()
		self.trc_gamma_ctrl.SetValue(str(getcfg("3dlut.trc_gamma")))
		self.trc_gamma_type_ctrl.SetSelection(self.trc_gamma_types_ba[getcfg("3dlut.trc_gamma_type")])
		outoffset = int(getcfg("3dlut.trc_output_offset") * 100)
		self.black_output_offset_ctrl.SetValue(outoffset)
		self.black_output_offset_intctrl.SetValue(outoffset)
	
	def show_bitdepth_controls(self):
		self.Freeze()
		input_show = getcfg("3dlut.format") == "3dl"
		self.lut3d_bitdepth_input_label.Show(input_show)
		self.lut3d_bitdepth_input_ctrl.Show(input_show)
		output_show = getcfg("3dlut.format") in ("3dl", "mga")
		self.lut3d_bitdepth_output_label.Show(output_show)
		self.lut3d_bitdepth_output_ctrl.Show(output_show)
		self.panel.GetSizer().Layout()
		self.update_layout()
		self.Thaw()

	def show_trc_controls(self, show=True):
		show = show and self.worker.argyll_version >= [1, 6]
		self.apply_trc_cb.Show(show)
		self.trc_ctrl.Show(show)
		self.trc_gamma_label.Show(show)
		self.trc_gamma_ctrl.Show(show)
		self.trc_gamma_type_ctrl.Show(show)
		self.black_output_offset_label.Show(show)
		self.black_output_offset_ctrl.Show(show)
		self.black_output_offset_intctrl.Show(show)
		self.black_output_offset_intctrl_label.Show(show)
	
	def show_encoding_controls(self, show=True):
		show = show and self.worker.argyll_version >= [1, 6]
		self.encoding_input_label.Show(show)
		self.encoding_input_ctrl.Show(show)
		self.encoding_output_label.Show(show)
		self.encoding_output_ctrl.Show(show)
	
	def update_encoding_controls(self):
		self.encoding_input_ctrl.SetSelection(self.encoding_ba[getcfg("3dlut.encoding.input")])
		self.encoding_input_ctrl.Enable(getcfg("3dlut.format") != "madVR")
		if getcfg("3dlut.format") == "eeColor":
			setcfg("3dlut.encoding.output", getcfg("3dlut.encoding.input"))
		self.encoding_output_ctrl.SetSelection(self.encoding_ba[getcfg("3dlut.encoding.output")])
		self.encoding_output_ctrl.Enable(getcfg("3dlut.format") not in ("eeColor",
																		"madVR"))
	
	def enable_size_controls(self):
		self.lut3d_size_ctrl.Enable(getcfg("3dlut.format")
									not in ("eeColor", "madVR"))
		


def main():
	config.initcfg("3DLUT-maker")
	lang.init()
	lang.update_defaults()
	app = BaseApp(0)
	app.TopWindow = LUT3DFrame()
	if sys.platform == "darwin":
		app.TopWindow.init_menubar()
	app.TopWindow.listen()
	app.TopWindow.Show()
	app.MainLoop()

if __name__ == "__main__":
	main()
