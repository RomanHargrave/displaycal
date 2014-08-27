# -*- coding: utf-8 -*-

import os
import sys

from config import get_data_path, initcfg, getcfg, geticon, hascfg, setcfg
from log import safe_print
from meta import name as appname
from util_str import strtr
from worker import Error, get_current_profile_path, show_result_dialog
import CGATS
import ICCProfile as ICCP
import config
import localization as lang
import worker
from wxTestchartEditor import TestchartEditor
from wxwindows import (BaseFrame, FileDrop, InfoDialog, wx)
import xh_filebrowsebutton

from wx import xrc


class ReportFrame(BaseFrame):

	""" Measurement report creation window """
	
	def __init__(self, parent=None):
		self.res = xrc.XmlResource(get_data_path(os.path.join("xrc", 
															  "report.xrc")))
		self.res.InsertHandler(xh_filebrowsebutton.FileBrowseButtonWithHistoryXmlHandler())
		pre = wx.PreFrame()
		self.res.LoadOnFrame(pre, parent, "reportframe")
		self.PostCreate(pre)
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		
		self.SetIcons(config.get_icon_bundle([256, 48, 32, 16], appname))
		
		self.set_child_ctrls_as_attrs(self)

		self.panel = self.FindWindowByName("panel")

		self.worker = worker.Worker(self)
		self.worker.set_argyll_version("xicclu")

		for which in ("chart", "simulation_profile", "devlink_profile",
					  "output_profile"):
			ctrl = self.FindWindowByName("%s_ctrl" % which)
			setattr(self, "%s_ctrl" % which, ctrl)
			ctrl.changeCallback = getattr(self, "%s_ctrl_handler" % which)
			if which not in ("devlink_profile", "output_profile"):
				if which == "chart":
					wildcard = "\.(cie|gam|ti1|ti3)$"
				else:
					wildcard = "\.(icc|icm)$"
				if which == "simulation_profile":
					history = []
					standard_profiles = config.get_standard_profiles(True)
					basenames = []
					for path in standard_profiles:
						basename = os.path.basename(path)
						if not basename in basenames:
							basenames.append(basename)
							history.append(path)
				else:
					history = get_data_path("ref", wildcard)
				history = sorted(history, key=lambda path:
											  os.path.basename(path).lower())
				ctrl.SetHistory(history)
			ctrl.SetMaxFontSize(11)
			# Drop targets
			handler = getattr(self, "%s_drop_handler" % which)
			if which.endswith("_profile"):
				drophandlers = {".icc": handler,
								".icm": handler}
			else:
				drophandlers = {".cgats": handler,
								".cie": handler,
								".ti1": handler,
								".ti2": handler,
								".ti3": handler,
								".txt": handler}
			ctrl.SetDropTarget(FileDrop(self, drophandlers))

		# Bind event handlers
		self.fields_ctrl.Bind(wx.EVT_CHOICE,
							  self.fields_ctrl_handler)
		self.chart_btn.Bind(wx.EVT_BUTTON, self.chart_btn_handler)
		self.simulation_profile_cb.Bind(wx.EVT_CHECKBOX,
									  self.use_simulation_profile_ctrl_handler)
		self.use_simulation_profile_as_output_cb.Bind(wx.EVT_CHECKBOX,
													  self.use_simulation_profile_as_output_handler)
		self.enable_3dlut_cb.Bind(wx.EVT_CHECKBOX, self.enable_3dlut_handler)
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
		self.simulate_whitepoint_cb.Bind(wx.EVT_CHECKBOX,
										 self.simulate_whitepoint_ctrl_handler)
		self.simulate_whitepoint_relative_cb.Bind(wx.EVT_CHECKBOX,
												  self.simulate_whitepoint_relative_ctrl_handler)
		self.devlink_profile_cb.Bind(wx.EVT_CHECKBOX,
									 self.use_devlink_profile_ctrl_handler)
		self.output_profile_current_btn.Bind(wx.EVT_BUTTON,
											 self.output_profile_current_ctrl_handler)
		
		self.setup_language()
		self.update_controls()
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
	
	def apply_trc_ctrl_handler(self, event):
		v = self.apply_trc_cb.GetValue()
		setcfg("measurement_report.apply_trc", int(v))
		config.writecfg()
		self.update_main_controls()

	def black_output_offset_ctrl_handler(self, event):
		if event.GetId() == self.black_output_offset_intctrl.GetId():
			self.black_output_offset_ctrl.SetValue(
				self.black_output_offset_intctrl.GetValue())
		else:
			self.black_output_offset_intctrl.SetValue(
				self.black_output_offset_ctrl.GetValue())
		v = self.black_output_offset_ctrl.GetValue() / 100.0
		setcfg("measurement_report.trc_output_offset", v)
		self.update_trc_control()

	def trc_gamma_ctrl_handler(self, event):
		try:
			v = float(self.trc_gamma_ctrl.GetValue().replace(",", "."))
			if (v < config.valid_ranges["measurement_report.trc_gamma"][0] or
				v > config.valid_ranges["measurement_report.trc_gamma"][1]):
				raise ValueError()
		except ValueError:
			wx.Bell()
			self.trc_gamma_ctrl.SetValue(str(getcfg("measurement_report.trc_gamma")))
		else:
			if str(v) != self.trc_gamma_ctrl.GetValue():
				self.trc_gamma_ctrl.SetValue(str(v))
			setcfg("measurement_report.trc_gamma", v)
			config.writecfg()
			self.update_trc_control()
		event.Skip()

	def trc_ctrl_handler(self, event):
		if self.trc_ctrl.GetSelection() == 0:
			# BT.1886
			setcfg("measurement_report.trc_gamma", 2.4)
			setcfg("measurement_report.trc_gamma_type", "B")
			setcfg("measurement_report.trc_output_offset", 0.0)
			config.writecfg()
			self.update_trc_controls()

	def trc_gamma_type_ctrl_handler(self, event):
		setcfg("measurement_report.trc_gamma_type",
			   self.trc_gamma_types_ab[self.trc_gamma_type_ctrl.GetSelection()])
		config.writecfg()
		self.update_trc_control()
	
	def chart_btn_handler(self, event):
		if self.Parent:
			parent = self.Parent
		else:
			parent = self
		chart = getcfg("measurement_report.chart")
		if not hasattr(parent, "tcframe"):
			parent.tcframe = TestchartEditor(parent, path=chart,
											 cfg="measurement_report.chart",
											 target=self)
		elif (not hasattr(parent.tcframe, "ti1") or
			  chart != parent.tcframe.ti1.filename):
			parent.tcframe.tc_load_cfg_from_ti1(None, chart,
												"measurement_report.chart",
												self)
		setcfg("tc.show", 1)
		parent.tcframe.Show()
		parent.tcframe.Raise()
	
	def chart_ctrl_handler(self, event):
		chart = self.chart_ctrl.GetPath()
		values = []
		try:
			cgats = CGATS.CGATS(chart)
		except (IOError, CGATS.CGATSInvalidError), exception:
			show_result_dialog(exception, self)
		else:
			data_format = cgats.queryv1("DATA_FORMAT")
			if data_format:
				for column in data_format.itervalues():
					column_prefix = column.split("_")[0]
					if (column_prefix in ("CMYK", "LAB", "RGB", "XYZ") and
						column_prefix not in values):
						values.append(column_prefix)
				if values:
					self.panel.Freeze()
					self.fields_ctrl.SetItems(values)
					self.fields_ctrl.GetContainingSizer().Layout()
					self.panel.Thaw()
					fields = getcfg("measurement_report.chart.fields")
					try:
						index = values.index(fields)
					except ValueError:
						index = 0
					self.fields_ctrl.SetSelection(index)
					setcfg("measurement_report.chart", chart)
					config.writecfg()
					self.chart_patches_amount.Freeze()
					self.chart_patches_amount.SetLabel(
						str(cgats.queryv1("NUMBER_OF_SETS") or ""))
					self.chart_patches_amount.GetContainingSizer().Layout()
					self.chart_patches_amount.Thaw()
					self.chart_white = cgats.get_white_cie()
					if event:
						v = int(not self.chart_white or not "RGB" in values)
						setcfg("measurement_report.whitepoint.simulate", v)
						setcfg("measurement_report.whitepoint.simulate.relative", v)
			if not values:
				if chart:
					show_result_dialog(lang.getstr("error.testchart.missing_fields",
												   (chart, "RGB/CMYK %s LAB/XYZ" %
														   lang.getstr("or"))), self)
				self.chart_ctrl.SetPath(getcfg("measurement_report.chart"))
			else:
				self.chart_btn.Enable("RGB" in values and
									  "XYZ" in values)
		self.fields_ctrl.Enable(self.fields_ctrl.GetCount() > 1)
		self.fields_ctrl_handler(None)

	def chart_drop_handler(self, path):
		if not self.worker.is_working():
			self.chart_ctrl.SetPath(path)
			self.chart_ctrl_handler(True)
	
	def devlink_profile_ctrl_handler(self, event):
		self.set_profile("devlink")

	def devlink_profile_drop_handler(self, path):
		if not self.worker.is_working():
			self.devlink_profile_ctrl.SetPath(path)
			self.set_profile("devlink")
	
	def enable_3dlut_handler(self, event):
		setcfg("3dlut.madVR.enable", int(self.enable_3dlut_cb.GetValue()))
		setcfg("measurement_report.use_devlink_profile", 0)
		config.writecfg()
		self.update_main_controls()
	
	def fields_ctrl_handler(self, event):
		setcfg("measurement_report.chart.fields",
			   self.fields_ctrl.GetStringSelection())
		self.update_main_controls()
	
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
					setattr(self, "%s_profile" % which, profile)
					getattr(self, "%s_profile_desc" % which).SetLabel(profile.getDescription())
					if not silent:
						setcfg("measurement_report.%s_profile" % which, profile.fileName)
						if which == "simulation":
							self.use_simulation_profile_ctrl_handler(None)
						else:
							self.update_main_controls()
					return profile
			getattr(self,
					"%s_profile_ctrl" %
					which).SetPath(getcfg("measurement_report.%s_profile" % which))
		else:
			getattr(self, "%s_profile_desc" % which).SetLabel("")
			if not silent:
				setattr(self, "%s_profile" % which, None)
				setcfg("measurement_report.%s_profile" % which, None)
				self.update_main_controls()
	
	def setup_language(self):
		BaseFrame.setup_language(self)
		
		for which in ("chart", "simulation_profile", "devlink_profile",
					  "output_profile"):
			if which.endswith("_profile"):
				wildcard = lang.getstr("filetype.icc")  + "|*.icc;*.icm"
			else:
				wildcard = (lang.getstr("filetype.ti1_ti3_txt") + 
							"|*.cgats;*.cie;*.gam;*.ti1;*.ti2;*.ti3;*.txt")
			msg = {"chart": "measurement_report_choose_chart_or_reference",
				   "devlink_profile": "devicelink_profile",
				   "output_profile": "measurement_report_choose_profile"}.get(which, which)
			kwargs = dict(toolTip=lang.getstr(msg).rstrip(":"),
						  dialogTitle=lang.getstr(msg), 
						  fileMask=wildcard)
			ctrl = getattr(self, "%s_ctrl" % which)
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
	
	def update_controls(self):
		""" Update controls with values from the configuration """
		self.simulation_profile_ctrl.SetPath(getcfg("measurement_report.simulation_profile"))
		self.set_profile("simulation", silent=True)
		self.update_trc_controls()
		self.devlink_profile_ctrl.SetPath(getcfg("measurement_report.devlink_profile"))
		self.set_profile("devlink", silent=True)
		self.output_profile_ctrl.SetPath(getcfg("measurement_report.output_profile"))
		self.set_profile("output", silent=True)
		self.set_testchart(getcfg("measurement_report.chart"))

	def update_trc_control(self):
		if (getcfg("measurement_report.trc_gamma_type") == "B" and
			getcfg("measurement_report.trc_output_offset") == 0 and
			getcfg("measurement_report.trc_gamma") == 2.4):
			self.trc_ctrl.SetSelection(0)  # BT.1886
		else:
			self.trc_ctrl.SetSelection(1)  # Gamma

	def update_trc_controls(self):
		self.update_trc_control()
		self.trc_gamma_ctrl.SetValue(str(getcfg("measurement_report.trc_gamma")))
		self.trc_gamma_type_ctrl.SetSelection(self.trc_gamma_types_ba[getcfg("measurement_report.trc_gamma_type")])
		outoffset = int(getcfg("measurement_report.trc_output_offset") * 100)
		self.black_output_offset_ctrl.SetValue(outoffset)
		self.black_output_offset_intctrl.SetValue(outoffset)
	
	def set_testchart(self, path):
		self.chart_ctrl.SetPath(path)
		self.chart_ctrl_handler(None)
	
	def update_main_controls(self):
		chart_has_white = bool(getattr(self, "chart_white", None))
		color = getcfg("measurement_report.chart.fields")
		sim_profile_color = (getattr(self, "simulation_profile", None) and
							 self.simulation_profile.colorSpace)
		if getcfg("measurement_report.use_simulation_profile"):
			setcfg("measurement_report.use_simulation_profile",
				   int(sim_profile_color == color))
		self.simulation_profile_cb.Enable(sim_profile_color == color)
		enable1 = bool(getcfg("measurement_report.use_simulation_profile"))
		enable2 = (sim_profile_color == "RGB" and
				   bool(getcfg("measurement_report.use_simulation_profile_as_output")))
		self.simulation_profile_cb.SetValue(enable1)
		self.simulation_profile_ctrl.Enable(color in ("CMYK", "RGB"))
		self.simulation_profile_desc.Enable(color in ("CMYK", "RGB"))
		self.use_simulation_profile_as_output_cb.Enable(enable1 and
														sim_profile_color == "RGB")
		self.use_simulation_profile_as_output_cb.SetValue(enable1 and enable2)
		self.enable_3dlut_cb.Enable(enable1 and enable2)
		self.enable_3dlut_cb.SetValue(enable1 and enable2 and
									  bool(getcfg("3dlut.madVR.enable")))
		self.enable_3dlut_cb.Show(config.get_display_name() == "madVR")
		enable5 = (sim_profile_color == "RGB" and
				   isinstance(self.simulation_profile.tags.get("rXYZ"),
							  ICCP.XYZType) and
				   isinstance(self.simulation_profile.tags.get("gXYZ"),
							  ICCP.XYZType) and
				   isinstance(self.simulation_profile.tags.get("bXYZ"),
							  ICCP.XYZType))
		self.apply_trc_cb.Enable(enable1 and enable5)
		enable6 = (enable1 and enable5 and
				   bool(getcfg("measurement_report.apply_trc")))
		self.apply_trc_cb.SetValue(enable6)
		self.trc_ctrl.Enable(enable6)
		self.trc_gamma_label.Enable(enable6)
		self.trc_gamma_ctrl.Enable(enable6)
		self.trc_gamma_type_ctrl.Enable(enable6)
		self.black_output_offset_label.Enable(enable6)
		self.black_output_offset_ctrl.Enable(enable6)
		self.black_output_offset_intctrl.Enable(enable6)
		self.black_output_offset_intctrl_label.Enable(enable6)
		self.simulate_whitepoint_cb.Enable((enable1 and not enable2) or
										   (color in ("LAB", "XYZ") and
											chart_has_white))
		enable3 = bool(getcfg("measurement_report.whitepoint.simulate"))
		self.simulate_whitepoint_cb.SetValue(((enable1 and not enable2) or
											  color in ("LAB", "XYZ")) and
											 enable3)
		self.simulate_whitepoint_relative_cb.Enable(((enable1 and not enable2) or
													 color in ("LAB", "XYZ")) and
													enable3)
		self.simulate_whitepoint_relative_cb.SetValue(
			((enable1 and not enable2) or color in ("LAB", "XYZ")) and
			enable3 and
			bool(getcfg("measurement_report.whitepoint.simulate.relative")))
		self.devlink_profile_cb.Enable(enable1 and enable2)
		enable4 = bool(getcfg("measurement_report.use_devlink_profile"))
		self.devlink_profile_cb.SetValue(enable1 and enable2 and enable4)
		self.devlink_profile_ctrl.Enable(enable1 and enable2 and enable4)
		self.devlink_profile_desc.Enable(enable1 and enable2 and enable4)
		self.output_profile_label.Enable((color in ("LAB", "RGB", "XYZ") or
										  enable1) and
										 (not enable1 or not enable2 or
										 self.apply_trc_cb.GetValue()))
		self.output_profile_ctrl.Enable((color in ("LAB", "RGB", "XYZ") or
										 enable1) and
										(not enable1 or not enable2 or
										self.apply_trc_cb.GetValue()))
		self.output_profile_desc.Enable((color in ("LAB", "RGB", "XYZ") or
										 enable1) and
										(not enable1 or not enable2 or
										self.apply_trc_cb.GetValue()))
		output_profile = (bool(getcfg("measurement_report.output_profile")) and
						  os.path.isfile(getcfg("measurement_report.output_profile")))
		self.measure_btn.Enable(((enable1 and enable2 and (not enable6 or
														   output_profile) and
								  (not enable4 or
								   (bool(getcfg("measurement_report.devlink_profile")) and
								    os.path.isfile(getcfg("measurement_report.devlink_profile"))))) or
								 (((not enable1 and
								    color in ("LAB", "RGB", "XYZ")) or
								   (enable1 and sim_profile_color == color and
								    not enable2)) and
								  output_profile)) and
								 bool(getcfg("measurement_report.chart")) and
								 os.path.isfile(getcfg("measurement_report.chart")))
		self.update_layout()
	
	def use_devlink_profile_ctrl_handler(self, event):
		setcfg("3dlut.madVR.enable", 0)
		setcfg("measurement_report.use_devlink_profile",
			   int(self.devlink_profile_cb.GetValue()))
		config.writecfg()
		self.update_main_controls()
	
	def use_simulation_profile_ctrl_handler(self, event):
		use_sim_profile = self.simulation_profile_cb.GetValue()
		setcfg("measurement_report.use_simulation_profile",
			   int(use_sim_profile))
		sim_profile = getattr(self, "simulation_profile", None)
		if use_sim_profile and sim_profile:
			v = int(sim_profile.profileClass == "prtr")
			setcfg("measurement_report.whitepoint.simulate", v)
			setcfg("measurement_report.whitepoint.simulate.relative", v)
			if ("rTRC" in sim_profile.tags and "gTRC" in sim_profile.tags and
				"bTRC" in sim_profile.tags and sim_profile.tags.rTRC is
				sim_profile.tags.gTRC is sim_profile.tags.bTRC and
				isinstance(sim_profile.tags.rTRC, ICCP.CurveType)):
				# Use BT.1886 gamma mapping for SMPTE 240M / Rec. 709 TRC
				tf = sim_profile.tags.rTRC.get_transfer_function()
				setcfg("measurement_report.apply_trc",
					  int(tf[0][1] in (-240, -709)))
		config.writecfg()
		self.update_main_controls()

	def use_simulation_profile_as_output_handler(self, event):
		setcfg("measurement_report.use_simulation_profile_as_output",
			   int(self.use_simulation_profile_as_output_cb.GetValue()))
		config.writecfg()
		self.update_main_controls()


if __name__ == "__main__":
	config.initcfg()
	lang.init()
	lang.update_defaults()
	app = wx.App(0)
	frame = ReportFrame()
	frame.Show()
	app.MainLoop()
