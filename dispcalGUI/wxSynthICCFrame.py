# -*- coding: utf-8 -*-

import os
import sys

from ICCProfile import ICCProfile
from config import get_data_path, get_verified_path, getcfg, hascfg, setcfg
from log import safe_print
from meta import name as appname
from util_os import waccess
from worker import Error, show_result_dialog
import ICCProfile as ICCP
import colormath
import config
import localization as lang
import worker
from wxaddons import FileDrop
from wxwindows import BaseFrame, InfoDialog, wx
try:
	import wx.lib.agw.floatspin as floatspin
except ImportError:
	import floatspin
import xh_floatspin

from wx import xrc


class SynthICCFrame(BaseFrame):

	""" 3D LUT creation window """
	
	def __init__(self, parent=None):
		self.res = xrc.XmlResource(get_data_path(os.path.join("xrc", 
															  "synthicc.xrc")))
		self.res.InsertHandler(xh_floatspin.FloatSpinCtrlXmlHandler())
		pre = wx.PreFrame()
		self.res.LoadOnFrame(pre, parent, "synthiccframe")
		self.PostCreate(pre)
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		
		self.SetIcons(config.get_icon_bundle([256, 48, 32, 16],
											 appname + "-synthprofile"))
		
		self.set_child_ctrls_as_attrs(self)

		self.panel = self.FindWindowByName("panel")
		
		self._updating_ctrls = False
		
		# Presets
		presets = [""] + sorted(colormath.rgb_spaces.keys())
		self.preset_ctrl.SetItems(presets)

		# Bind event handlers
		self.preset_ctrl.Bind(wx.EVT_CHOICE, self.preset_ctrl_handler)
		for color in ("red", "green", "blue", "white"):
			for component in "XYZxy":
				if component in "xy":
					handler = "xy"
				else:
					handler = "XYZ"
				self.Bind(wx.EVT_TEXT, getattr(self, "%s_%s_ctrl_handler" %
													 (color, handler)),
						  getattr(self, "%s_%s" % (color, component)))
		self.trc_ctrl.Bind(wx.EVT_CHOICE, self.trc_ctrl_handler)
		self.trc_gamma_ctrl.Bind(wx.EVT_COMBOBOX, self.trc_gamma_ctrl_handler)
		self.trc_gamma_ctrl.Bind(wx.EVT_KILL_FOCUS, self.trc_gamma_ctrl_handler)
		self.trc_gamma_type_ctrl.Bind(wx.EVT_CHOICE, self.trc_gamma_type_ctrl_handler)
		self.black_output_offset_ctrl.Bind(wx.EVT_SLIDER,
										   self.black_output_offset_ctrl_handler)
		self.black_output_offset_intctrl.Bind(wx.EVT_TEXT,
											  self.black_output_offset_ctrl_handler)
		self.colorspace_rgb_ctrl.Bind(wx.EVT_RADIOBUTTON,
									  self.colorspace_ctrl_handler)
		self.colorspace_gray_ctrl.Bind(wx.EVT_RADIOBUTTON,
									   self.colorspace_ctrl_handler)
		self.black_luminance_ctrl.Bind(floatspin.EVT_FLOATSPIN,
									   self.black_luminance_ctrl_handler)
		self.luminance_ctrl.Bind(floatspin.EVT_FLOATSPIN,
								 self.luminance_ctrl_handler)
		self.save_as_btn.Bind(wx.EVT_BUTTON, self.save_as_btn_handler)

		self.save_as_btn.SetDefault()
		self.save_as_btn.Disable()
		
		self.setup_language()
		
		self.update_layout()
		self.update_controls()
		
		self.save_btn.Hide()
		
		config.defaults.update({
			"position.synthiccframe.x": self.GetDisplay().ClientArea[0] + 40,
			"position.synthiccframe.y": self.GetDisplay().ClientArea[1] + 60,
			"size.synthiccframe.w": self.GetMinSize()[0],
			"size.synthiccframe.h": self.GetMinSize()[1]})

		if (hascfg("position.synthiccframe.x") and
			hascfg("position.synthiccframe.y") and
			hascfg("size.synthiccframe.w") and
			hascfg("size.synthiccframe.h")):
			self.SetSaneGeometry(int(getcfg("position.synthiccframe.x")),
								 int(getcfg("position.synthiccframe.y")),
								 int(getcfg("size.synthiccframe.w")),
								 int(getcfg("size.synthiccframe.h")))
		else:
			self.Center()
	
	def OnClose(self, event=None):
		if (self.IsShownOnScreen() and not self.IsMaximized() and
			not self.IsIconized()):
			x, y = self.GetScreenPosition()
			setcfg("position.synthiccframe.x", x)
			setcfg("position.synthiccframe.y", y)
			setcfg("size.synthiccframe.w", self.GetSize()[0])
			setcfg("size.synthiccframe.h", self.GetSize()[1])
		config.writecfg()
		if event:
			event.Skip()
	
	def black_luminance_ctrl_handler(self, event):
		v = self.black_luminance_ctrl.GetValue()
		setcfg("synthprofile.black_luminance", v)
		self.panel.Freeze()
		i = self.trc_ctrl.GetSelection()
		self.trc_gamma_type_ctrl.Show(i in (0, 4) and bool(v))
		black_output_offset_show = (i in (0, 4) and
									bool(v))
		self.black_output_offset_label.Show(black_output_offset_show)
		self.black_output_offset_ctrl.Show(black_output_offset_show)
		self.black_output_offset_intctrl.Show(black_output_offset_show)
		self.black_output_offset_intctrl_label.Show(black_output_offset_show)
		self.panel.GetSizer().Layout()
		self.panel.Thaw()

	def black_output_offset_ctrl_handler(self, event):
		if event.GetId() == self.black_output_offset_intctrl.GetId():
			self.black_output_offset_ctrl.SetValue(
				self.black_output_offset_intctrl.GetValue())
		else:
			self.black_output_offset_intctrl.SetValue(
				self.black_output_offset_ctrl.GetValue())
		v = self.black_output_offset_ctrl.GetValue() / 100.0
		setcfg("synthprofile.trc_output_offset", v)
		self.update_trc_control()
	
	def blue_XYZ_ctrl_handler(self, event):
		self.parse_XYZ("blue")
	
	def blue_xy_ctrl_handler(self, event):
		self.parse_xy("blue")
	
	def colorspace_ctrl_handler(self, event):
		show = bool(self.colorspace_rgb_ctrl.Value)
		for color in ("red", "green", "blue"):
			getattr(self, "label_%s" % color).Show(show)
			for component in "XYZxy":
				getattr(self, "%s_%s" % (color, component)).Show(show)
		self.enable_save_as_btn()
		self.update_layout()
	
	def drop_handler(self, path):
		pass
	
	def drop_unsupported_handler(self):
		pass
	
	def enable_save_as_btn(self):
		self.save_as_btn.Enable(bool(self.get_XYZ()))
	
	def get_XYZ(self):
		XYZ = {}
		for color in ("white", "red", "green", "blue"):
			for component in "XYZ":
				try:
					XYZ[color[0] + component] = float(getattr(self,
															  "%s_%s" %
															  (color, component)).Value.replace(",", ".")) / 100.0
				except ValueError:
					pass
		if ("wX" in XYZ and "wY" in XYZ and "wZ" in XYZ and
			(self.colorspace_gray_ctrl.Value or
			 ("rX" in XYZ and "rY" in XYZ and "rZ" in XYZ and
			  "gX" in XYZ and "gY" in XYZ and "gZ" in XYZ and
			  "bX" in XYZ and "bY" in XYZ and "bZ" in XYZ))):
			return XYZ
	
	def green_XYZ_ctrl_handler(self, event):
		self.parse_XYZ("green")
	
	def green_xy_ctrl_handler(self, event):
		self.parse_xy("green")
	
	def luminance_ctrl_handler(self, event):
		v = self.luminance_ctrl.GetValue()
		setcfg("synthprofile.luminance", v)
	
	def parse_XYZ(self, name):
		if not self._updating_ctrls:
			self.preset_ctrl.SetSelection(0)
		XYZ = {}
		for component in "XYZ":
			try:
				XYZ[component] = float(getattr(self, "%s_%s" %
									   (name, component)).Value.replace(",", "."))
			except ValueError:
				pass
		if "X" in XYZ and "Y" in XYZ and "Z" in XYZ:
			xyY = colormath.XYZ2xyY(XYZ["X"], XYZ["Y"], XYZ["Z"])
			for i, component in enumerate("xy"):
				getattr(self, "%s_%s" % (name, component)).ChangeValue(str(xyY[i]))
		self.enable_save_as_btn()
	
	def parse_xy(self, name):
		if not self._updating_ctrls:
			self.preset_ctrl.SetSelection(0)
		xy = {}
		for color in ("white", "red", "green", "blue"):
			for component in "xy":
				try:
					xy[color[0] + component] = float(getattr(self,
															 "%s_%s" %
															 (color, component)).Value.replace(",", "."))
				except ValueError:
					pass
		if "wx" in xy and "wy" in xy:
			wXYZ = colormath.xyY2XYZ(xy["wx"], xy["wy"], 1.0)
			for i, component in enumerate("XYZ"):
				getattr(self, "white_%s" % component).ChangeValue(str(wXYZ[i] * 100))
			has_rgb_xy = ("rx" in xy and "ry" in xy and
						  "gx" in xy and "gy" in xy and
						  "bx" in xy and "by" in xy)
			if name != "white" and has_rgb_xy:
				# Calculate RGB to XYZ matrix from chromaticities and white
				mtx = colormath.rgb_to_xyz_matrix(xy["rx"], xy["ry"],
												  xy["gx"], xy["gy"],
												  xy["bx"], xy["by"], wXYZ)
				rgb = {"r": (1.0, 0.0, 0.0),
					   "g": (0.0, 1.0, 0.0),
					   "b": (0.0, 0.0, 1.0)}
				XYZ = {}
				for color in ("red", "green", "blue"):
					# Calculate XYZ for primaries
					XYZ[color[0]] = mtx * rgb[color[0]]
					for i, component in enumerate("XYZ"):
						getattr(self, "%s_%s" %
								(color, component)).ChangeValue(str(XYZ[color[0]][i] * 100))
		self.enable_save_as_btn()
	
	def preset_ctrl_handler(self, event):
		preset_name = self.preset_ctrl.GetStringSelection()
		if preset_name:
			gamma, white, red, green, blue = colormath.rgb_spaces[preset_name]
			white = colormath.get_whitepoint(white)
			self._updating_ctrls = True
			for i, component in enumerate("XYZ"):
				getattr(self, "white_%s" % component).SetValue(str(white[i] * 100))
			for color in ("red", "green", "blue"):
				for i, component in enumerate("xy"):
					getattr(self, "%s_%s" % (color, component)).SetValue(str(locals()[color][i]))
			if gamma == -1023:
				# DICOM
				self.trc_ctrl.SetSelection(1)
			elif gamma == -3.0:
				# L*
				self.trc_ctrl.SetSelection(2)
			elif gamma == -709:
				# Rec. 709
				self.trc_ctrl.SetSelection(3)
			elif gamma == -1886:
				# Rec. 1886
				self.trc_ctrl.SetSelection(4)
				self.trc_ctrl_handler()
			elif gamma == -240:
				# SMPTE 240M
				self.trc_ctrl.SetSelection(5)
			elif gamma == -2.4:
				# sRGB
				self.trc_ctrl.SetSelection(6)
			else:
				# Gamma
				self.trc_ctrl.SetSelection(0)
				setcfg("synthprofile.trc_gamma", gamma)
			self.update_trc_controls()
			self._updating_ctrls = False
	
	def profile_ctrl_handler(self, event):
		pass
	
	def profile_name_ctrl_handler(self, event):
		self.enable_save_as_btn()
	
	def red_XYZ_ctrl_handler(self, event):
		self.parse_XYZ("red")
	
	def red_xy_ctrl_handler(self, event):
		self.parse_xy("red")
	
	def save_as_btn_handler(self, event):
		XYZ = self.get_XYZ()
		try:
			gamma = float(self.trc_gamma_ctrl.Value)
		except ValueError:
			wx.Bell()
			gamma = 2.2
			self.trc_gamma_ctrl.Value = str(gamma)
		# Black Y scaled to 0..1 range
		black_Y = (getcfg("synthprofile.black_luminance") /
				   getcfg("synthprofile.luminance"))
		if self.trc_ctrl.GetSelection() == 0:
			# Gamma
			trc = gamma
		elif self.trc_ctrl.GetSelection() == 1:
			# DICOM - gamma set here is not actually used
			trc = 2.2
		elif self.trc_ctrl.GetSelection() == 2:
			# L*
			trc = -3.0
		elif self.trc_ctrl.GetSelection() == 3:
			# Rec. 709
			trc = -709
		elif self.trc_ctrl.GetSelection() == 4:
			# Rec. 1886 - gamma set here is not actually used
			trc = 2.2
		elif self.trc_ctrl.GetSelection() == 5:
			# SMPTE 240M
			trc = -240
		elif self.trc_ctrl.GetSelection() == 6:
			# sRGB
			trc = -2.4
		defaultDir, defaultFile = get_verified_path("last_icc_path")
		defaultFile = lang.getstr("unnamed")
		if self.colorspace_rgb_ctrl.Value:
			# Color profile
			profile = ICCP.ICCProfile.from_XYZ((XYZ["rX"], XYZ["rY"], XYZ["rZ"]),
											   (XYZ["gX"], XYZ["gY"], XYZ["gZ"]),
											   (XYZ["bX"], XYZ["bY"], XYZ["bZ"]),
											   (XYZ["wX"], XYZ["wY"], XYZ["wZ"]),
											   trc,
											   defaultFile,
											   getcfg("copyright"))
			TRC = profile.tags.rTRC = profile.tags.gTRC = profile.tags.bTRC
		else:
			# Grayscale profile
			profile = ICCP.ICCProfile()
			profile.colorSpace = "GRAY"
			profile.setCopyright(getcfg("copyright"))
			profile.tags.wtpt = ICCP.XYZType()
			(profile.tags.wtpt.X,
			 profile.tags.wtpt.Y,
			 profile.tags.wtpt.Z) = (XYZ["wX"], XYZ["wY"], XYZ["wZ"])
			TRC = profile.tags.rTRC = profile.tags.gTRC = profile.tags.bTRC = \
				  profile.tags.kTRC = ICCP.CurveType()
		if self.trc_ctrl.GetSelection() == 1:
			# DICOM
			# Absolute luminance values!
			TRC.set_dicom_trc(getcfg("synthprofile.black_luminance"),
							  getcfg("synthprofile.luminance"))
		elif self.trc_ctrl.GetSelection() in (0, 4):
			# Gamma with output offset or Rec. 1886
			outoffset = getcfg("synthprofile.trc_output_offset")
			if getcfg("synthprofile.trc_gamma_type") == "g":
				gamma = colormath.xicc_tech_gamma(gamma, black_Y, outoffset)
			TRC.set_bt1886_trc(black_Y, outoffset, gamma)
		elif black_Y:
			TRC.set_trc(trc, 1024, vmin=black_Y * 65535)
		elif not TRC:
			TRC.set_trc(trc, 1)
		for tagname in ("lumi", "bkpt"):
			if tagname == "lumi":
				# Absolute
				X, Y, Z = [v * getcfg("synthprofile.luminance")
						   for v in (XYZ["wX"], XYZ["wY"], XYZ["wZ"])]
			else:
				x, y = colormath.XYZ2xyY(XYZ["wX"], XYZ["wY"], XYZ["wZ"])[:2]
				X, Y, Z = colormath.xyY2XYZ(x, y, black_Y)
			profile.tags[tagname] = ICCP.XYZType()
			(profile.tags[tagname].X,
			 profile.tags[tagname].Y,
			 profile.tags[tagname].Z) = X, Y, Z
		path = None
		dlg = wx.FileDialog(self, 
							lang.getstr("save_as"),
							defaultDir=defaultDir,
							defaultFile=defaultFile,
							wildcard="*.icc", 
							style=wx.SAVE | wx.FD_OVERWRITE_PROMPT)
		dlg.Center(wx.BOTH)
		if dlg.ShowModal() == wx.ID_OK:
			path = dlg.GetPath()
		dlg.Destroy()
		if path:
			if os.path.splitext(path)[1].lower() not in (".icc", ".icm"):
				path += ".icc"
			if not waccess(path, os.W_OK):
				show_result_dialog(Error(lang.getstr("error.access_denied.write",
													 path)),
								   self)
				return
			setcfg("last_icc_path", path)
			config.writecfg()
			profile.setDescription(os.path.splitext(os.path.basename(path))[0])
			profile.calculateID()
			try:
				profile.write(path)
			except Exception, exception:
				show_result_dialog(exception, self)
	
	def setup_language(self):
		BaseFrame.setup_language(self)
		
		# Create the file picker ctrls dynamically to get translated strings
		if sys.platform in ("darwin", "win32"):
			origpickerctrl = self.FindWindowByName("profile_ctrl")
			sizer = origpickerctrl.GetContainingSizer()
			self.profile_ctrl = wx.FilePickerCtrl(self.panel, -1, "",
												  message=lang.getstr("profile"), 
												  wildcard=lang.getstr("filetype.icc")
												  + "|*.icc;*.icm",
												  name="profile_ctrl")
			self.profile_ctrl.PickerCtrl.Label = lang.getstr("browse")
			self.profile_ctrl.PickerCtrl.SetMaxFontSize(11)
			sizer.Replace(origpickerctrl, self.profile_ctrl)
			origpickerctrl.Destroy()
			sizer.Layout()
		self.profile_ctrl.Bind(wx.EVT_FILEPICKER_CHANGED,
							   self.profile_ctrl_handler)
		self.profile_ctrl_label.Hide()
		self.profile_ctrl.Hide()

		# Drop targets
		self.droptarget = FileDrop()
		self.droptarget.drophandlers = {".icc": self.drop_handler,
										".icm": self.drop_handler}
		self.droptarget.unsupported_handler = self.drop_unsupported_handler
		self.profile_ctrl.SetDropTarget(self.droptarget)
		
		items = []
		for item in self.trc_ctrl.Items:
			items.append(lang.getstr(item))
		self.trc_ctrl.SetItems(items)
		self.trc_ctrl.SetSelection(0)
		
		self.trc_gamma_types_ab = {0: "g", 1: "G"}
		self.trc_gamma_types_ba = {"g": 0, "G": 1}
		self.trc_gamma_type_ctrl.SetItems([lang.getstr("trc.type.relative"),
										   lang.getstr("trc.type.absolute")])
	
	def trc_ctrl_handler(self, event=None):
		if not self._updating_ctrls:
			self.preset_ctrl.SetSelection(0)
		i = self.trc_ctrl.GetSelection()
		if i == 4:
			# BT.1886
			setcfg("synthprofile.trc_gamma", 2.4)
			setcfg("synthprofile.trc_gamma_type", "G")
			setcfg("synthprofile.trc_output_offset", 0.0)
			config.writecfg()
		if not self._updating_ctrls:
			self.update_trc_controls()

	def trc_gamma_type_ctrl_handler(self, event):
		setcfg("synthprofile.trc_gamma_type",
			   self.trc_gamma_types_ab[self.trc_gamma_type_ctrl.GetSelection()])
		config.writecfg()
		self.update_trc_control()
	
	def trc_gamma_ctrl_handler(self, event):
		if not self._updating_ctrls:
			try:
				v = float(self.trc_gamma_ctrl.GetValue().replace(",", "."))
				if (v < config.valid_ranges["gamma"][0] or
					v > config.valid_ranges["gamma"][1]):
					raise ValueError()
			except ValueError:
				wx.Bell()
				self.trc_gamma_ctrl.SetValue(str(getcfg("synthprofile.trc_gamma")))
			else:
				if str(v) != self.trc_gamma_ctrl.GetValue():
					self.trc_gamma_ctrl.SetValue(str(v))
				setcfg("synthprofile.trc_gamma",
					   float(self.trc_gamma_ctrl.GetValue()))
				config.writecfg()
				self.preset_ctrl.SetSelection(0)
				self.update_trc_control()
		event.Skip()
	
	def update_controls(self):
		""" Update controls with values from the configuration """
		self.luminance_ctrl.SetValue(getcfg("synthprofile.luminance"))
		self.black_luminance_ctrl.SetValue(getcfg("synthprofile.black_luminance"))
		self.update_trc_control()
		self.update_trc_controls()

	def update_trc_control(self):
		if self.trc_ctrl.GetSelection() in (0, 4):
			if (getcfg("synthprofile.trc_gamma_type") == "G" and
				getcfg("synthprofile.trc_output_offset") == 0 and
				getcfg("synthprofile.trc_gamma") == 2.4):
				self.trc_ctrl.SetSelection(4)  # BT.1886
			else:
				self.trc_ctrl.SetSelection(0)  # Gamma

	def update_trc_controls(self):
		i = self.trc_ctrl.GetSelection()
		self.panel.Freeze()
		self.trc_gamma_label.Show(i in (0, 4))
		self.trc_gamma_ctrl.SetValue(str(getcfg("synthprofile.trc_gamma")))
		self.trc_gamma_ctrl.Show(i in (0, 4))
		self.trc_gamma_type_ctrl.SetSelection(self.trc_gamma_types_ba[getcfg("synthprofile.trc_gamma_type")])
		self.panel.GetSizer().Layout()
		self.panel.Thaw()
		if i in (0, 4):
			outoffset = int(getcfg("synthprofile.trc_output_offset") * 100)
		else:
			outoffset = 100
		self.black_output_offset_ctrl.SetValue(outoffset)
		self.black_output_offset_intctrl.SetValue(outoffset)
		self.black_luminance_ctrl_handler(None)
	
	def white_XYZ_ctrl_handler(self, event):
		self.parse_XYZ("white")
	
	def white_xy_ctrl_handler(self, event):
		self.parse_xy("white")
		


def main():
	config.initcfg()
	lang.init()
	lang.update_defaults()
	app = wx.App(0)
	app.synthiccframe = SynthICCFrame()
	app.synthiccframe.Show()
	app.MainLoop()

if __name__ == "__main__":
	main()
