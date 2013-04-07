#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

from ICCProfile import ICCProfile, get_display_profile
from config import (get_data_path, get_verified_path, getcfg, geticon, hascfg,
					setcfg)
from log import safe_print
from meta import name as appname
from util_os import waccess
from worker import Error, show_result_dialog
import ICCProfile as ICCP
import config
import localization as lang
import worker
from worker import check_set_argyll_bin
from wxaddons import FileDrop
from wxwindows import BaseFrame, InfoDialog, wx

from wx import xrc


def get_current_profile_path():
	profile = None
	profile_path = getcfg("calibration.file")
	if profile_path:
		try:
			profile = ICCProfile(profile_path)
		except Exception, exception:
			return
	else:
		try:
			profile = get_display_profile(getcfg("display.number") - 1)
		except Exception, exception:
			return
	if profile:
		return profile.fileName


class LUT3DFrame(BaseFrame):

	""" 3D LUT creation window """
	
	def __init__(self, parent=None):
		self.res = xrc.XmlResource(get_data_path(os.path.join("xrc", 
															  "3dlut.xrc")))
		pre = wx.PreFrame()
		self.res.LoadOnFrame(pre, parent, "lut3dframe")
		self.PostCreate(pre)
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		
		self.SetIcons(config.get_icon_bundle([256, 48, 32, 16], appname))
		
		self.set_child_ctrls_as_attrs(self)

		self.panel = self.FindWindowByName("panel")

		self.worker = worker.Worker(self)

		# Bind event handlers
		self.abstract_profile_cb.Bind(wx.EVT_CHECKBOX,
									  self.use_abstract_profile_ctrl_handler)
		self.output_profile_current_btn.Bind(wx.EVT_BUTTON,
											 self.output_profile_current_ctrl_handler)
		self.apply_cal_cb.Bind(wx.EVT_CHECKBOX, self.apply_cal_ctrl_handler)
		self.rendering_intent_ctrl.Bind(wx.EVT_CHOICE,
										self.rendering_intent_ctrl_handler)
		self.black_point_compensation_cb.Bind(wx.EVT_CHECKBOX,
											  self.black_point_compensation_ctrl_handler)
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
		if (self.IsShownOnScreen() and not self.IsMaximized() and
			not self.IsIconized()):
			x, y = self.GetScreenPosition()
			setcfg("position.lut3dframe.x", x)
			setcfg("position.lut3dframe.y", y)
			setcfg("size.lut3dframe.w", self.GetSize()[0])
			setcfg("size.lut3dframe.h", self.GetSize()[1])
			config.writecfg()
		if event:
			event.Skip()
	
	def use_abstract_profile_ctrl_handler(self, event):
		setcfg("3dlut.use_abstract_profile",
			   int(self.abstract_profile_cb.GetValue()))
		config.writecfg()
		enable = bool(getcfg("3dlut.use_abstract_profile"))
		self.abstract_profile_ctrl.Enable(enable)
		self.abstract_profile_desc.Enable(enable)
	
	def apply_cal_ctrl_handler(self, event):
		setcfg("3dlut.output.profile.apply_cal",
			   int(self.apply_cal_cb.GetValue()))
		config.writecfg()
	
	def black_point_compensation_ctrl_handler(self, event):
		setcfg("3dlut.black_point_compensation",
			   int(self.black_point_compensation_cb.GetValue()))
		config.writecfg()

	def abstract_drop_unsupported_handler(self):
		self.drop_unsupported("abstract")

	def input_drop_unsupported_handler(self):
		self.drop_unsupported("input")
		
	def output_drop_unsupported_handler(self):
		self.drop_unsupported("output")
	
	def drop_unsupported(self, which):
		if not self.worker.is_working():
			files = getattr(self, "%s_droptarget" % which)._filenames
			InfoDialog(self, msg=lang.getstr("error.file_type_unsupported") +
							 "\n\n" + "\n".join(files),
					   ok=lang.getstr("ok"),
					   bitmap=geticon(32, "dialog-error"))

	def abstract_drop_handler(self, path):
		if not self.worker.is_working():
			self.abstract_profile_ctrl.SetPath(path)
			self.set_profile("abstract")

	def input_drop_handler(self, path):
		if not self.worker.is_working():
			self.input_profile_ctrl.SetPath(path)
			self.set_profile("input")

	def output_drop_handler(self, path):
		if not self.worker.is_working():
			self.output_profile_ctrl.SetPath(path)
			self.set_profile("output")
	
	def abstract_profile_ctrl_handler(self, event):
		self.set_profile("abstract")
	
	def input_profile_ctrl_handler(self, event):
		self.set_profile("input")
	
	def lut3d_bitdepth_input_ctrl_handler(self, event):
		setcfg("3dlut.bitdepth.input",
			   self.lut3d_bitdepth_ab[self.lut3d_bitdepth_input_ctrl.GetSelection()])
		config.writecfg()
	
	def lut3d_bitdepth_output_ctrl_handler(self, event):
		setcfg("3dlut.bitdepth.output",
			   self.lut3d_bitdepth_ab[self.lut3d_bitdepth_output_ctrl.GetSelection()])
		config.writecfg()
	
	def lut3d_create_consumer(self, result):
		if isinstance(result, Exception) and result:
			show_result_dialog(result, self)
		else:
			path = None
			defaultDir, defaultFile = get_verified_path("last_3dlut_path")
			format = getcfg("3dlut.format")
			if format == "eeColor":
				format = "txt"
			defaultFile = os.path.splitext(defaultFile or
										   os.path.basename(config.defaults.get("last_3dlut_path")))[0] + "." + format
			dlg = wx.FileDialog(self, 
								lang.getstr("3dlut.create"),
								defaultDir=defaultDir,
								defaultFile=defaultFile,
								wildcard="*." + format, 
								style=wx.SAVE | wx.FD_OVERWRITE_PROMPT)
			dlg.Center(wx.BOTH)
			if dlg.ShowModal() == wx.ID_OK:
				path = dlg.GetPath()
			dlg.Destroy()
			if path:
				if not waccess(os.path.dirname(path), os.W_OK):
					show_result_dialog(Error(lang.getstr("error.access_denied.write",
														 os.path.dirname(path))),
									   self)
					return
				setcfg("last_3dlut_path", path)
				config.writecfg()
				result = result.replace("${FILENAME}", os.path.basename(path))
				result = result.replace("${TITLE}",
										os.path.splitext(os.path.basename(path))[0])
				try:
					lut_file = open(path, "wb")
					lut_file.write(result)
					lut_file.close()
				except Exception, exception:
					show_result_dialog(exception, self)
	
	def lut3d_create_handler(self, event):
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
			self.worker.interactive = False
			self.worker.start(self.lut3d_create_consumer,
							  self.lut3d_create_producer,
							  wargs=(profile_in, profile_abst, profile_out),
							  progress_msg=lang.getstr("3dlut.create"))
	
	def lut3d_create_producer(self, profile_in, profile_abst, profile_out):
		apply_cal = (profile_out and "vcgt" in profile_out.tags and
					 getcfg("3dlut.output.profile.apply_cal"))
		intent = getcfg("3dlut.rendering_intent")
		bpc = bool(getcfg("3dlut.black_point_compensation"))
		format = getcfg("3dlut.format")
		size = getcfg("3dlut.size")
		input_bits = getcfg("3dlut.bitdepth.input")
		output_bits = getcfg("3dlut.bitdepth.output")
		try:
			lut = self.worker.create_3dlut(profile_in, profile_abst,
										   profile_out, apply_cal=apply_cal,
										   intent=intent, bpc=bpc, 
										   format=format, size=size,
										   input_bits=input_bits,
										   output_bits=output_bits)
		except Exception, exception:
			return exception
		else:
			return lut
	
	def lut3d_format_ctrl_handler(self, event):
		setcfg("3dlut.format", self.lut3d_formats_ab[self.lut3d_format_ctrl.GetSelection()])
		if getcfg("3dlut.format") == "eeColor":
			# eeColor uses a fixed size of 65x65x65
			setcfg("3dlut.size", 65)
			self.lut3d_size_ctrl.SetSelection(self.lut3d_size_ba[65])
		elif getcfg("3dlut.format") == "mga":
			# Pandora uses a fixed size of 33x33x33
			setcfg("3dlut.size", 33)
			self.lut3d_size_ctrl.SetSelection(self.lut3d_size_ba[33])
			# Pandora uses a fixed bitdepth of 16
			setcfg("3dlut.bitdepth.output", 16)
			self.lut3d_bitdepth_output_ctrl.SetSelection(self.lut3d_bitdepth_ba[16])
		config.writecfg()
		self.enable_size_controls()
		self.enable_bitdepth_controls()
	
	def lut3d_size_ctrl_handler(self, event):
		setcfg("3dlut.size",
			   self.lut3d_size_ab[self.lut3d_size_ctrl.GetSelection()])
		config.writecfg()
	
	def output_profile_ctrl_handler(self, event):
		self.set_profile("output", silent=not event)
	
	def output_profile_current_ctrl_handler(self, event):
		profile_path = get_current_profile_path()
		if profile_path and os.path.isfile(profile_path):
			self.output_profile_ctrl.SetPath(profile_path)
			self.set_profile("output", profile_path or False, silent=not event)
	
	def rendering_intent_ctrl_handler(self, event):
		setcfg("3dlut.rendering_intent",
			   self.rendering_intents_ab[self.rendering_intent_ctrl.GetSelection()])
		config.writecfg()
	
	def set_profile(self, which, profile_path=None, silent=False):
		path = getattr(self, "%s_profile_ctrl" % which).GetPath()
		if which == "output":
			if profile_path is None:
				profile_path = get_current_profile_path()
			self.output_profile_current_btn.Enable(self.output_profile_ctrl.Enabled and
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
			except ICCP.ICCProfileInvalidError:
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
							self.output_profile_ctrl.SetPath(getcfg("3dlut.output.profile"))
							self.set_profile("input", silent=silent)
							return
						else:
							self.abstract_profile_cb.SetValue(False)
							self.abstract_profile_cb.Disable()
							self.abstract_profile_ctrl.Disable()
							self.abstract_profile_desc.Disable()
							self.output_profile_ctrl.Disable()
							self.output_profile_current_btn.Disable()
							self.output_profile_desc.Disable()
							self.apply_cal_cb.SetValue(False)
							self.apply_cal_cb.Disable()
							self.rendering_intent_ctrl.Disable()
							self.black_point_compensation_cb.Disable()
					else:
						if which == "input":
							enable = bool(getcfg("3dlut.use_abstract_profile"))
							self.abstract_profile_cb.SetValue(enable)
							self.abstract_profile_cb.Enable()
							self.abstract_profile_ctrl.Enable(enable)
							self.abstract_profile_desc.Enable(enable)
							self.output_profile_ctrl.Enable()
							self.output_profile_current_btn.Enable()
							self.output_profile_desc.Enable()
							self.rendering_intent_ctrl.Enable()
							self.black_point_compensation_cb.Enable()
						elif which == "output":
							self.apply_cal_cb.SetValue("vcgt" in profile.tags and
													   bool(getcfg("3dlut.output.profile.apply_cal")))
							self.apply_cal_cb.Enable("vcgt" in profile.tags)
					getattr(self, "%s_profile_desc" % which).SetLabel(profile.getDescription())
					if which == "output" and not self.output_profile_ctrl.Enabled:
						return
					setcfg("3dlut.%s.profile" % which, profile.fileName)
					config.writecfg()
					self.lut3d_create_btn.Enable(bool(getcfg("3dlut.input.profile")) and
												 os.path.isfile(getcfg("3dlut.input.profile")) and
												 ((bool(getcfg("3dlut.output.profile")) and
												   os.path.isfile(getcfg("3dlut.output.profile"))) or
												  profile.profileClass == "link"))
					return profile
			getattr(self, "%s_profile_ctrl" %
						  which).SetPath(getcfg("3dlut.%s.profile" % which))
		else:
			getattr(self, "%s_profile_desc" % which).SetLabel("")
	
	def setup_language(self):
		BaseFrame.setup_language(self)
		
		# Create the file picker ctrls dynamically to get translated strings
		for which in ("input", "abstract", "output"):
			if sys.platform in ("darwin", "win32"):
				origpickerctrl = self.FindWindowByName("%s_profile_ctrl" % which)
				hsizer = origpickerctrl.GetContainingSizer()
				setattr(self, "%s_profile_ctrl" % which,
						wx.FilePickerCtrl(self.panel, -1, "",
										  message=lang.getstr("3dlut.%s.profile"
															  % which), 
										  wildcard=lang.getstr("filetype.icc")
												   + "|*.icc;*.icm",
										  name="%s_profile_ctrl" % which))
				getattr(self, "%s_profile_ctrl" %
							  which).PickerCtrl.Label = lang.getstr("browse")
				getattr(self, "%s_profile_ctrl" %
							  which).PickerCtrl.SetMaxFontSize(11)
				hsizer.Replace(origpickerctrl,
							   getattr(self, "%s_profile_ctrl" % which))
				origpickerctrl.Destroy()
				hsizer.Layout()
			getattr(self, "%s_profile_ctrl"
						  % which).Bind(wx.EVT_FILEPICKER_CHANGED,
										getattr(self, "%s_profile_ctrl_handler" % 
													 which))
			# Drop targets
			setattr(self, "%s_droptarget" % which, FileDrop())
			getattr(self, "%s_droptarget" % which).drophandlers = {".icc": getattr(self, "%s_drop_handler" % which),
																   ".icm": getattr(self, "%s_drop_handler" % which)}
			getattr(self, "%s_droptarget" % which).unsupported_handler = getattr(self, "%s_drop_unsupported_handler" % which)
			getattr(self, "%s_profile_ctrl"
						  % which).SetDropTarget(getattr(self, "%s_droptarget"
														 % which))
		
		self.rendering_intents_ab = {}
		self.rendering_intents_ba = {}
		for i, ri in enumerate(config.valid_values["3dlut.rendering_intent"]):
			self.rendering_intent_ctrl.Append(lang.getstr("gamap.intents." + ri))
			self.rendering_intents_ab[i] = ri
			self.rendering_intents_ba[ri] = i
		
		self.lut3d_formats_ab = {}
		self.lut3d_formats_ba = {}
		for i, format in enumerate(config.valid_values["3dlut.format"]):
			self.lut3d_format_ctrl.Append(lang.getstr("3dlut.format.%s" % format))
			self.lut3d_formats_ab[i] = format
			self.lut3d_formats_ba[format] = i
		
		self.lut3d_size_ab = {}
		self.lut3d_size_ba = {}
		for i, size in enumerate(config.valid_values["3dlut.size"]):
			self.lut3d_size_ctrl.Append("%sx%sx%s" % ((size, ) * 3))
			self.lut3d_size_ab[i] = size
			self.lut3d_size_ba[size] = i
		
		self.lut3d_bitdepth_ab = {}
		self.lut3d_bitdepth_ba = {}
		for i, bitdepth in enumerate(config.valid_values["3dlut.bitdepth.input"]):
			self.lut3d_bitdepth_input_ctrl.Append(str(bitdepth))
			self.lut3d_bitdepth_output_ctrl.Append(str(bitdepth))
			self.lut3d_bitdepth_ab[i] = bitdepth
			self.lut3d_bitdepth_ba[bitdepth] = i
	
	def update_controls(self):
		""" Update controls with values from the configuration """
		self.lut3d_create_btn.Disable()
		self.input_profile_ctrl.SetPath(getcfg("3dlut.input.profile"))
		self.input_profile_ctrl_handler(None)
		enable = bool(getcfg("3dlut.use_abstract_profile"))
		self.abstract_profile_cb.SetValue(enable)
		self.abstract_profile_ctrl.SetPath(getcfg("3dlut.abstract.profile"))
		self.abstract_profile_ctrl_handler(None)
		self.output_profile_ctrl.SetPath(getcfg("3dlut.output.profile"))
		self.apply_cal_cb.Disable()
		self.output_profile_ctrl_handler(None)
		self.rendering_intent_ctrl.SetSelection(self.rendering_intents_ba[getcfg("3dlut.rendering_intent")])
		self.black_point_compensation_cb.SetValue(bool(getcfg("3dlut.black_point_compensation")))
		self.lut3d_format_ctrl.SetSelection(self.lut3d_formats_ba[getcfg("3dlut.format")])
		self.lut3d_size_ctrl.SetSelection(self.lut3d_size_ba[getcfg("3dlut.size")])
		self.enable_size_controls()
		self.lut3d_bitdepth_input_ctrl.SetSelection(self.lut3d_bitdepth_ba[getcfg("3dlut.bitdepth.input")])
		self.lut3d_bitdepth_output_ctrl.SetSelection(self.lut3d_bitdepth_ba[getcfg("3dlut.bitdepth.output")])
		self.enable_bitdepth_controls()
	
	def enable_bitdepth_controls(self):
		self.Freeze()
		input_enable = getcfg("3dlut.format") == "3dl"
		self.lut3d_bitdepth_input_label.Show(input_enable)
		self.lut3d_bitdepth_input_ctrl.Show(input_enable)
		output_enable = getcfg("3dlut.format") in ("3dl", "mga")
		self.lut3d_bitdepth_output_label.Show(output_enable)
		self.lut3d_bitdepth_output_ctrl.Show(output_enable)
		self.panel.GetSizer().Layout()
		self.Thaw()
	
	def enable_size_controls(self):
		self.lut3d_size_ctrl.Enable(getcfg("3dlut.format") != "eeColor")
		


def main():
	config.initcfg()
	lang.init()
	lang.update_defaults()
	app = wx.App(0)
	app.lut3dframe = LUT3DFrame()
	app.lut3dframe.Show()
	app.MainLoop()

if __name__ == "__main__":
	main()
