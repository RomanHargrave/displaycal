#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import os
import sys

from config import get_data_path, initcfg, getcfg, geticon, hascfg, setcfg
from log import safe_print
from meta import name as appname
from worker import Error, get_current_profile_path, show_result_dialog
import ICCProfile as ICCP
import config
import localization as lang
import worker
from wxaddons import FileDrop
from wxwindows import BaseFrame, InfoDialog, wx

from wx import xrc


class ReportFrame(BaseFrame):

	""" Measurement report creation window """
	
	def __init__(self, parent=None):
		self.res = xrc.XmlResource(get_data_path(os.path.join("xrc", 
															  "report.xrc")))
		pre = wx.PreFrame()
		self.res.LoadOnFrame(pre, parent, "reportframe")
		self.PostCreate(pre)
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		
		self.SetIcons(config.get_icon_bundle([256, 48, 32, 16], appname))
		
		self.set_child_ctrls_as_attrs(self)

		self.panel = self.FindWindowByName("panel")

		self.worker = worker.Worker(self)
		self.worker.set_argyll_version("xicclu")

		# Bind event handlers
		self.simulation_profile_cb.Bind(wx.EVT_CHECKBOX,
									  self.use_simulation_profile_ctrl_handler)
		self.use_simulation_profile_as_output_cb.Bind(wx.EVT_CHECKBOX,
													  self.use_simulation_profile_as_output_handler)
		self.apply_bt1886_cb.Bind(wx.EVT_CHECKBOX, self.apply_bt1886_ctrl_handler)
		self.bt1886_gamma_ctrl.Bind(wx.EVT_KILL_FOCUS,
									self.bt1886_gamma_ctrl_handler)
		self.bt1886_gamma_type_ctrl.Bind(wx.EVT_CHOICE,
										 self.bt1886_gamma_type_ctrl_handler)
		self.simulate_whitepoint_cb.Bind(wx.EVT_CHECKBOX,
										 self.simulate_whitepoint_ctrl_handler)
		self.simulate_whitepoint_relative_cb.Bind(wx.EVT_CHECKBOX,
												  self.simulate_whitepoint_relative_ctrl_handler)
		self.devlink_profile_cb.Bind(wx.EVT_CHECKBOX,
									 self.use_devlink_profile_ctrl_handler)
		self.output_profile_current_btn.Bind(wx.EVT_BUTTON,
											 self.output_profile_current_ctrl_handler)
		
		self.setup_language()
		self.update_controls(silent=True)
		self.update_layout()
		
		config.defaults.update({
			"position.reportframe.x": self.GetDisplay().ClientArea[0] + 40,
			"position.reportframe.y": self.GetDisplay().ClientArea[1] + 60,
			"size.reportframe.w": self.GetMinSize()[0],
			"size.reportframe.h": self.GetMinSize()[1]})

		if (hascfg("position.reportframe.x") and
			hascfg("position.reportframe.y") and
			hascfg("size.reportframe.w") and
			hascfg("size.reportframe.h")):
			self.SetSaneGeometry(int(getcfg("position.reportframe.x")),
								 int(getcfg("position.reportframe.y")),
								 int(getcfg("size.reportframe.w")),
								 int(getcfg("size.reportframe.h")))
		else:
			self.Center()
	
	def OnClose(self, event=None):
		if (self.IsShownOnScreen() and not self.IsMaximized() and
			not self.IsIconized()):
			x, y = self.GetScreenPosition()
			setcfg("position.reportframe.x", x)
			setcfg("position.reportframe.y", y)
			setcfg("size.reportframe.w", self.GetSize()[0])
			setcfg("size.reportframe.h", self.GetSize()[1])
			config.writecfg()
		if event:
			event.Skip()
	
	def apply_bt1886_ctrl_handler(self, event):
		v = self.apply_bt1886_cb.GetValue()
		setcfg("measurement_report.apply_bt1886_gamma_mapping", int(v))
		config.writecfg()
		self.update_main_controls()

	def bt1886_gamma_ctrl_handler(self, event):
		try:
			v = float(self.bt1886_gamma_ctrl.GetValue().replace(",", "."))
			if (v < config.valid_ranges["measurement_report.bt1886_gamma"][0] or
				v > config.valid_ranges["measurement_report.bt1886_gamma"][1]):
				raise ValueError()
		except ValueError:
			wx.Bell()
			self.bt1886_gamma_ctrl.SetValue(str(getcfg("measurement_report.bt1886_gamma")))
		else:
			if str(v) != self.bt1886_gamma_ctrl.GetValue():
				self.bt1886_gamma_ctrl.SetValue(str(v))
			setcfg("measurement_report.bt1886_gamma", v)
			config.writecfg()
		event.Skip()

	def bt1886_gamma_type_ctrl_handler(self, event):
		setcfg("measurement_report.bt1886_gamma_type",
			   self.bt1886_gamma_types_ab[self.bt1886_gamma_type_ctrl.GetSelection()])
		config.writecfg()
	
	def chart_ctrl_handler(self, event):
		setcfg("measurement_report.chart", self.chart_ctrl.GetPath())
		config.writecfg()
		self.update_main_controls()

	def chart_drop_handler(self, path):
		if not self.worker.is_working():
			self.chart_ctrl.SetPath(path)
			self.chart_ctrl_handler(None)

	def chart_drop_unsupported_handler(self):
		self.drop_unsupported("chart")
	
	def devlink_profile_ctrl_handler(self, event):
		self.set_profile("devlink")

	def devlink_profile_drop_handler(self, path):
		if not self.worker.is_working():
			self.devlink_profile_ctrl.SetPath(path)
			self.set_profile("devlink")
		
	def devlink_profile_drop_unsupported_handler(self):
		self.drop_unsupported("devlink_profile")
	
	def drop_unsupported(self, which):
		if not self.worker.is_working():
			files = getattr(self, "%s_droptarget" % which)._filenames
			InfoDialog(self, msg=lang.getstr("error.file_type_unsupported") +
							 "\n\n" + "\n".join(files),
					   ok=lang.getstr("ok"),
					   bitmap=geticon(32, "dialog-error"))
	
	def output_profile_ctrl_handler(self, event):
		self.set_profile("output")
	
	def output_profile_current_ctrl_handler(self, event):
		profile_path = get_current_profile_path()
		if profile_path and os.path.isfile(profile_path):
			self.output_profile_ctrl.SetPath(profile_path)
			self.set_profile("output")

	def output_profile_drop_handler(self, path):
		if not self.worker.is_working():
			self.output_profile_ctrl.SetPath(path)
			self.set_profile("output")
		
	def output_profile_drop_unsupported_handler(self):
		self.drop_unsupported("output_profile")
	
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
			except ICCP.ICCProfileInvalidError:
				if not silent:
					show_result_dialog(Error(lang.getstr("profile.invalid")),
									   parent=self)
			except IOError, exception:
				if not silent:
					show_result_dialog(exception, parent=self)
			else:
				setattr(self, "%s_profile" % which, profile)
				if ((which == "simulation" and
					 (profile.profileClass not in ("mntr", "prtr") or 
					  profile.colorSpace not in ("CMYK", "RGB"))) or
					(which == "output" and (profile.profileClass != "mntr" or
											profile.colorSpace != "RGB")) or
					(which == "devlink" and profile.profileClass != "link")):
					show_result_dialog(NotImplementedError(lang.getstr("profile.unsupported", 
																	   (profile.profileClass, 
																		profile.colorSpace))),
									   parent=self)
				else:
					getattr(self, "%s_profile_desc" % which).SetLabel(profile.getDescription())
					if which == "simulation" and not silent:
						v = int(profile.profileClass == "prtr")
						setcfg("measurement_report.whitepoint.simulate", v)
						setcfg("measurement_report.whitepoint.simulate.relative", v)
					setcfg("measurement_report.%s_profile" % which, profile.fileName)
					config.writecfg()
					self.update_main_controls()
					return profile
			getattr(self,
					"%s_profile_ctrl" %
					which).SetPath(getcfg("measurement_report.%s_profile" % which))
		else:
			getattr(self, "%s_profile_desc" % which).SetLabel("")
	
	def setup_language(self):
		BaseFrame.setup_language(self)
		
		# Create the file picker ctrls dynamically to get translated strings
		for which in ("chart", "simulation_profile", "devlink_profile",
					  "output_profile"):
			if sys.platform in ("darwin", "win32"):
				origpickerctrl = self.FindWindowByName("%s_ctrl" % which)
				hsizer = origpickerctrl.GetContainingSizer()
				if which.endswith("_profile"):
					wildcard = lang.getstr("filetype.icc")  + "|*.icc;*.icm"
				else:
					wildcard = (lang.getstr("filetype.ti1_ti3_txt") + 
								"|*.cgats;*.cie;*.ti1;*.ti2;*.ti3;*.txt")
				msg = {"chart": "measurement_report_choose_chart_or_reference",
					   "output_profile": "measurement_report_choose_profile"}.get(which, which)
				setattr(self, "%s_ctrl" % which,
						wx.FilePickerCtrl(self.panel, -1, "",
										  message=lang.getstr(msg), 
										  wildcard=wildcard,
										  name="%s_ctrl" % which))
				getattr(self, "%s_ctrl" %
							  which).PickerCtrl.Label = lang.getstr("browse")
				getattr(self, "%s_ctrl" %
							  which).PickerCtrl.SetMaxFontSize(11)
				hsizer.Replace(origpickerctrl,
							   getattr(self, "%s_ctrl" % which))
				origpickerctrl.Destroy()
				hsizer.Layout()
			getattr(self, "%s_ctrl"
						  % which).Bind(wx.EVT_FILEPICKER_CHANGED,
										getattr(self, "%s_ctrl_handler" % 
													 which))
			# Drop targets
			setattr(self, "%s_droptarget" % which, FileDrop())
			droptarget = getattr(self, "%s_droptarget" % which)
			handler = getattr(self, "%s_drop_handler" % which)
			if which.endswith("_profile"):
				droptarget.drophandlers = {".icc": handler,
										   ".icm": handler}
			else:
				droptarget.drophandlers = {".cgats": handler,
										   ".cie": handler,
										   ".ti1": handler,
										   ".ti2": handler,
										   ".ti3": handler,
										   ".txt": handler}
			droptarget.unsupported_handler = getattr(self,
													 "%s_drop_unsupported_handler"
													 % which)
			getattr(self, "%s_ctrl"
						  % which).SetDropTarget(droptarget)
		
		self.bt1886_gamma_types_ab = {0: "b", 1: "B"}
		self.bt1886_gamma_types_ba = {"b": 0, "B": 1}
		self.bt1886_gamma_type_ctrl.SetItems([lang.getstr("trc.type.relative"),
											  lang.getstr("trc.type.absolute")])
	
	def simulate_whitepoint_ctrl_handler(self, event):
		v = self.simulate_whitepoint_cb.GetValue()
		setcfg("measurement_report.whitepoint.simulate", int(v))
		config.writecfg()
		self.update_main_controls()
		
	
	def simulate_whitepoint_relative_ctrl_handler(self, event):
		setcfg("measurement_report.whitepoint.simulate.relative",
			   int(self.simulate_whitepoint_relative_cb.GetValue()))
		config.writecfg()
	
	def simulation_profile_ctrl_handler(self, event):
		self.set_profile("simulation")

	def simulation_profile_drop_handler(self, path):
		if not self.worker.is_working():
			self.simulation_profile_ctrl.SetPath(path)
			self.set_profile("simulation")

	def simulation_profile_drop_unsupported_handler(self):
		self.drop_unsupported("simulation_profile")
	
	def update_controls(self, silent=False):
		""" Update controls with values from the configuration """
		self.chart_ctrl.SetPath(getcfg("measurement_report.chart"))
		self.simulation_profile_ctrl.SetPath(getcfg("measurement_report.simulation_profile"))
		self.set_profile("simulation", silent=silent)
		self.bt1886_gamma_ctrl.SetValue(str(getcfg("measurement_report.bt1886_gamma")))
		self.bt1886_gamma_type_ctrl.SetSelection(self.bt1886_gamma_types_ba[getcfg("measurement_report.bt1886_gamma_type")])
		self.devlink_profile_ctrl.SetPath(getcfg("measurement_report.devlink_profile"))
		self.set_profile("devlink", silent=silent)
		self.output_profile_ctrl.SetPath(getcfg("measurement_report.output_profile"))
		self.set_profile("output", silent=silent)
		self.update_main_controls()
	
	def update_main_controls(self):
		enable1 = bool(getcfg("measurement_report.use_simulation_profile"))
		sim_profile_is_rgb = (bool(getattr(self, "simulation_profile", None)) and
							  self.simulation_profile.colorSpace == "RGB")
		enable2 = (sim_profile_is_rgb and
				   bool(getcfg("measurement_report.use_simulation_profile_as_output")))
		self.simulation_profile_cb.SetValue(enable1)
		self.simulation_profile_ctrl.Enable(enable1)
		self.simulation_profile_desc.Enable(enable1)
		self.use_simulation_profile_as_output_cb.Enable(enable1 and
														sim_profile_is_rgb)
		self.use_simulation_profile_as_output_cb.SetValue(enable2)
		enable5 = (sim_profile_is_rgb and
				   isinstance(self.simulation_profile.tags.get("rXYZ"),
							  ICCP.XYZType) and
				   isinstance(self.simulation_profile.tags.get("gXYZ"),
							  ICCP.XYZType) and
				   isinstance(self.simulation_profile.tags.get("bXYZ"),
							  ICCP.XYZType))
		self.apply_bt1886_cb.Enable(enable1 and enable5)
		enable6 = (enable1 and enable5 and
				   bool(getcfg("measurement_report.apply_bt1886_gamma_mapping")))
		self.apply_bt1886_cb.SetValue(enable6)
		self.bt1886_gamma_ctrl.Enable(enable6)
		self.bt1886_gamma_type_ctrl.Enable(enable6)
		self.simulate_whitepoint_cb.Enable(enable1 and not enable2)
		enable3 = bool(getcfg("measurement_report.whitepoint.simulate"))
		self.simulate_whitepoint_cb.SetValue(enable1 and not enable2 and enable3)
		self.simulate_whitepoint_relative_cb.Enable(enable1 and not enable2 and
													enable3)
		self.simulate_whitepoint_relative_cb.SetValue(enable1 and
			not enable2 and enable3 and
			bool(getcfg("measurement_report.whitepoint.simulate.relative")))
		self.devlink_profile_cb.Enable(enable1 and enable2)
		enable4 = bool(getcfg("measurement_report.use_devlink_profile"))
		self.devlink_profile_cb.SetValue(enable1 and enable2 and enable4)
		self.devlink_profile_ctrl.Enable(enable1 and enable2 and enable4)
		self.devlink_profile_desc.Enable(enable1 and enable2 and enable4)
		self.output_profile_label.Enable(not enable1 or not enable2 or
										 self.apply_bt1886_cb.GetValue())
		self.output_profile_ctrl.Enable(not enable1 or not enable2 or
										self.apply_bt1886_cb.GetValue())
		self.output_profile_desc.Enable(not enable1 or not enable2 or
										self.apply_bt1886_cb.GetValue())
		self.measure_btn.Enable(((enable1 and
								  bool(getcfg("measurement_report.simulation_profile")) and
								  os.path.isfile(getcfg("measurement_report.simulation_profile"))) or
								 not enable1) and
								bool(getcfg("measurement_report.chart")) and
								os.path.isfile(getcfg("measurement_report.chart")) and
								bool(getcfg("measurement_report.output_profile")) and
								os.path.isfile(getcfg("measurement_report.output_profile")))
	
	def use_devlink_profile_ctrl_handler(self, event):
		setcfg("measurement_report.use_devlink_profile",
			   int(self.devlink_profile_cb.GetValue()))
		config.writecfg()
		self.update_main_controls()
	
	def use_simulation_profile_ctrl_handler(self, event):
		setcfg("measurement_report.use_simulation_profile",
			   int(self.simulation_profile_cb.GetValue()))
		config.writecfg()
		self.update_main_controls()

	def use_simulation_profile_as_output_handler(self, event):
		setcfg("measurement_report.use_simulation_profile_as_output",
			   int(self.use_simulation_profile_as_output_cb.GetValue()))
		config.writecfg()
		self.update_main_controls()