# -*- coding: utf-8 -*-

import math
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
from wxwindows import BaseApp, BaseFrame, FileDrop, InfoDialog, wx
import floatspin
import xh_floatspin

from wx import xrc


class SynthICCFrame(BaseFrame):

	""" 3D LUT creation window """
	
	def __init__(self, parent=None):
		self.res = xrc.XmlResource(get_data_path(os.path.join("xrc", 
															  "synthicc.xrc")))
		self.res.InsertHandler(xh_floatspin.FloatSpinCtrlXmlHandler())
		if hasattr(wx, "PreFrame"):
			# Classic
			pre = wx.PreFrame()
			self.res.LoadOnFrame(pre, parent, "synthiccframe")
			self.PostCreate(pre)
		else:
			# Phoenix
			wx.Frame.__init__(self)
			self.res.LoadFrame(self, parent, "synthiccframe")
		self.init()
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		
		self.SetIcons(config.get_icon_bundle([256, 48, 32, 16],
											 appname + "-synthprofile"))
		
		self.set_child_ctrls_as_attrs(self)

		self.panel = self.FindWindowByName("panel")
		
		self._updating_ctrls = False
		
		# Presets
		presets = [""] + sorted(colormath.rgb_spaces.keys())
		self.preset_ctrl.SetItems(presets)

		self.worker = worker.Worker(self)

		# Drop targets
		self.droptarget = FileDrop(self)
		self.droptarget.drophandlers = {".icc": self.drop_handler,
										".icm": self.drop_handler}
		self.panel.SetDropTarget(self.droptarget)

		# Bind event handlers
		self.preset_ctrl.Bind(wx.EVT_CHOICE, self.preset_ctrl_handler)
		for color in ("red", "green", "blue", "white", "black"):
			for component in "XYZxy":
				if component in "xy":
					handler = "xy"
				else:
					handler = "XYZ"
				self.Bind(floatspin.EVT_FLOATSPIN,
						  getattr(self, "%s_%s_ctrl_handler" % (color,
																handler)),
						  getattr(self, "%s_%s" % (color, component)))
		self.black_point_cb.Bind(wx.EVT_CHECKBOX,
								 self.black_point_enable_handler)
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
		
		self.update_controls()
		self.update_layout()
		
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
		if self.Parent:
			config.writecfg()
		else:
			config.writecfg(module="synthprofile",
							options=("synthprofile.", "last_icc_path",
									 "position.synthiccframe",
									 "size.synthiccframe"))
		if event:
			event.Skip()
	
	def black_luminance_ctrl_handler(self, event):
		v = self.black_luminance_ctrl.GetValue()
		white_Y = getcfg("synthprofile.luminance")
		min_Y = (1 / 65535.0) * 100
		increment = (1 / 65535.0) * white_Y
		if increment < min_Y:
			increment = min_Y * (white_Y / 100.0)
		min_inc = 1.0 / (10.0 ** self.black_luminance_ctrl.GetDigits())
		if increment < min_inc:
			increment = min_inc
		self.black_luminance_ctrl.SetIncrement(increment)
		fmt = "%%.%if" % self.black_luminance_ctrl.GetDigits()
		if fmt % v > fmt % 0 and fmt % v < fmt % increment:
			if event:
				v = increment
			else:
				v = 0
		elif fmt % v == fmt % 0:
			v = 0
		v = round(v / increment) * increment
		self.black_luminance_ctrl.SetValue(v)

		old = getcfg("synthprofile.black_luminance")
		setcfg("synthprofile.black_luminance", v)
		if event:
			self.black_xy_ctrl_handler(None)
		self.black_point_cb.Enable(v > 0)
		self.black_point_enable_handler(None)
		if (v != old and (old == 0 or v == 0)) or event is True:
			self.Freeze()
			i = self.trc_ctrl.GetSelection()
			self.trc_gamma_type_ctrl.Show(i in (0, 4) and bool(v))
			black_output_offset_show = (i in (0, 4) and bool(v))
			self.black_output_offset_label.Show(black_output_offset_show)
			self.black_output_offset_ctrl.Show(black_output_offset_show)
			self.black_output_offset_intctrl.Show(black_output_offset_show)
			self.black_output_offset_intctrl_label.Show(black_output_offset_show)
			self.panel.GetSizer().Layout()
			self.update_layout()
			self.Thaw()

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

	def black_point_enable_handler(self, event):
		v = getcfg("synthprofile.black_luminance")
		for component in "XYZxy":
			getattr(self, "black_%s" % component).Enable(v > 0 and
				self.black_point_cb.Value)

	def black_XYZ_ctrl_handler(self, event):
		luminance = getcfg("synthprofile.luminance")
		XYZ = []
		for component in "XYZ":
			XYZ.append(getattr(self, "black_%s" % component).GetValue() / 100.0)
			if component == "Y":
				self.black_luminance_ctrl.SetValue(XYZ[-1] * luminance)
				self.black_luminance_ctrl_handler(None)
				if not XYZ[-1]:
					XYZ = [0, 0, 0]
					for i in xrange(3):
						getattr(self, "black_%s" % "XYZ"[i]).SetValue(0)
					break
		for i, v in enumerate(colormath.XYZ2xyY(*XYZ)[:2]):
			getattr(self, "black_%s" % "xy"[i]).SetValue(v)

	def black_xy_ctrl_handler(self, event):
		# Black Y scaled to 0..1 range
		Y = (getcfg("synthprofile.black_luminance") /
			 getcfg("synthprofile.luminance"))
		xy = []
		for component in "xy":
			xy.append(getattr(self, "black_%s" % component).GetValue() or 1.0 /
																		  3)
			getattr(self, "black_%s" % component).SetValue(xy[-1])
		for i, v in enumerate(colormath.xyY2XYZ(*xy + [Y])):
			getattr(self, "black_%s" % "XYZ"[i]).SetValue(v * 100)
	
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
		try:
			profile = ICCP.ICCProfile(path)
		except (IOError, ICCP.ICCProfileInvalidError), exception:
			show_result_dialog(Error(lang.getstr("profile.invalid")), self)
		else:
			if (profile.colorSpace != "RGB" or
				profile.connectionColorSpace not in ("Lab", "XYZ")):
				show_result_dialog(Error(lang.getstr("profile.unsupported",
													 (profile.profileClass,
													  profile.colorSpace))),
								   self)
				return
			rgb = [(1, 1, 1), (0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)]
			for i in xrange(256):
				rgb.append((1.0 / 255 * i, 1.0 / 255 * i, 1.0 / 255 * i))
			try:
				colors = self.worker.xicclu(profile, rgb, intent="a")
			except Exception, exception:
				show_result_dialog(exception, self)
			else:
				if "lumi" in profile.tags:
					luminance = profile.tags.lumi.Y
				else:
					luminance = 100
				setcfg("synthprofile.luminance", luminance)
				self.luminance_ctrl.SetValue(luminance)
				for i, color in enumerate(("white", "black")):
					for j, component in enumerate("XYZ"):
						getattr(self, "%s_%s" %
								(color, component)).SetValue(colors[i][j] /
															 colors[0][1] * 100)
					self.parse_XYZ(color)
				for i, color in enumerate(("red", "green", "blue")):
					xyY = colormath.XYZ2xyY(*colors[2 + i])
					for j, component in enumerate("xy"):
						getattr(self, "%s_%s" %
								(color, component)).SetValue(xyY[j])
				self.parse_xy(None)
				self.black_XYZ_ctrl_handler(None)
				trc = ICCP.CurveType()
				for XYZ in colors[5:]:
					trc.append(XYZ[1] / colors[0][1] * 65535)
				transfer_function = trc.get_transfer_function()
				if transfer_function and transfer_function[1] >= .95:
					# Use detected transfer function
					gamma = transfer_function[0][1]
				else:
					# Use 50% gamma value
					gamma = math.log(colors[132][1]) / math.log(128.0 / 255)
				self.set_trc(round(gamma, 2))
				setcfg("synthprofile.trc_gamma_type", "g")
				self.trc_gamma_type_ctrl.SetSelection(self.trc_gamma_types_ba["g"])
	
	def enable_save_as_btn(self):
		self.save_as_btn.Enable(bool(self.get_XYZ()))
	
	def get_XYZ(self):
		""" Get XYZ in 0..1 range """
		XYZ = {}
		black_Y = (getcfg("synthprofile.black_luminance") /
				   getcfg("synthprofile.luminance"))
		for color in ("white", "red", "green", "blue", "black"):
			for component in "XYZ":
				v = getattr(self, "%s_%s" % (color,
											 component)).GetValue() / 100.0
				if color == "black":
					key = "k"
					if not self.black_point_cb.Value:
						v = XYZ["w%s" % component] * black_Y
				else:
					key = color[0]
				XYZ[key + component] = v
		if (XYZ["wX"] and XYZ["wY"] and XYZ["wZ"] and
			(self.colorspace_gray_ctrl.Value or
			 (XYZ["rX"] and XYZ["gY"] and XYZ["bZ"]))):
			return XYZ
	
	def green_XYZ_ctrl_handler(self, event):
		self.parse_XYZ("green")
	
	def green_xy_ctrl_handler(self, event):
		self.parse_xy("green")
	
	def luminance_ctrl_handler(self, event):
		v = self.luminance_ctrl.GetValue()
		setcfg("synthprofile.luminance", v)
		self.black_luminance_ctrl_handler(event)
	
	def parse_XYZ(self, name, set_blackpoint=False):
		if not set_blackpoint:
			set_blackpoint = not self.black_point_cb.Value
		if not self._updating_ctrls:
			self.preset_ctrl.SetSelection(0)
		XYZ = {}
		# Black Y scaled to 0..1 range
		black_Y = (getcfg("synthprofile.black_luminance") /
				   getcfg("synthprofile.luminance"))
		for component in "XYZ":
			v = getattr(self, "%s_%s" % (name, component)).GetValue()
			XYZ[component] = v
			if name == "white" and set_blackpoint:
				getattr(self, "black_%s" % (component)).SetValue(v * black_Y)
		if "X" in XYZ and "Y" in XYZ and "Z" in XYZ:
			xyY = colormath.XYZ2xyY(XYZ["X"], XYZ["Y"], XYZ["Z"])
			for i, component in enumerate("xy"):
				getattr(self, "%s_%s" % (name, component)).SetValue(xyY[i])
				if name == "white" and set_blackpoint:
					getattr(self, "black_%s" % (component)).SetValue(xyY[i])
		self.enable_save_as_btn()
	
	def parse_xy(self, name=None, set_blackpoint=False):
		if not set_blackpoint:
			set_blackpoint = not self.black_point_cb.Value
		if not self._updating_ctrls:
			self.preset_ctrl.SetSelection(0)
		xy = {}
		for color in ("white", "red", "green", "blue"):
			for component in "xy":
				v = getattr(self, "%s_%s" % (color, component)).GetValue()
				xy[color[0] + component] = v
		if name == "white":
			wXYZ = colormath.xyY2XYZ(xy["wx"], xy["wy"], 1.0)
		else:
			wXYZ = []
			for component in "XYZ":
				wXYZ.append(getattr(self, "white_%s" % component).GetValue() /
							100.0)
		if name == "white":
			# Black Y scaled to 0..1 range
			black_Y = (getcfg("synthprofile.black_luminance") /
					   getcfg("synthprofile.luminance"))
			for i, component in enumerate("XYZ"):
				getattr(self, "white_%s" % component).SetValue(wXYZ[i] * 100)
				if set_blackpoint:
					getattr(self, "black_%s" % component).SetValue(wXYZ[i] *
																   black_Y *
																   100)
		has_rgb_xy = True
		# Calculate RGB to XYZ matrix from chromaticities and white
		try:
			mtx = colormath.rgb_to_xyz_matrix(xy["rx"], xy["ry"],
											  xy["gx"], xy["gy"],
											  xy["bx"], xy["by"],
											  wXYZ)
		except ZeroDivisionError:
			# Singular matrix
			has_rgb_xy = False
		rgb = {"r": (1.0, 0.0, 0.0),
			   "g": (0.0, 1.0, 0.0),
			   "b": (0.0, 0.0, 1.0)}
		XYZ = {}
		for color in ("red", "green", "blue"):
			if has_rgb_xy:
				# Calculate XYZ for primaries
				v = mtx * rgb[color[0]]
			if not has_rgb_xy:
				v = (0, 0, 0)
			XYZ[color[0]] = v
			for i, component in enumerate("XYZ"):
				getattr(self, "%s_%s" %
						(color, component)).SetValue(XYZ[color[0]][i] * 100)
		self.enable_save_as_btn()
	
	def preset_ctrl_handler(self, event):
		preset_name = self.preset_ctrl.GetStringSelection()
		if preset_name:
			gamma, white, red, green, blue = colormath.rgb_spaces[preset_name]
			white = colormath.get_whitepoint(white)
			self._updating_ctrls = True
			for i, component in enumerate("XYZ"):
				getattr(self, "white_%s" % component).SetValue(white[i] * 100)
			self.parse_XYZ("white", True)
			for color in ("red", "green", "blue"):
				for i, component in enumerate("xy"):
					getattr(self, "%s_%s" % (color, component)).SetValue(locals()[color][i])
			self.parse_xy(None)
			self.set_trc(gamma)
			self._updating_ctrls = False

	def get_commands(self):
		return self.get_common_commands() + ["synthprofile [filename]",
											 "load <filename>"]

	def process_data(self, data):
		if (data[0] == "synthprofile" and
			len(data) < 3) or (data[0] == "load" and len(data) == 2):
			if self.IsIconized():
				self.Restore()
			self.Raise()
			if len(data) == 2:
				path = data[1]
				if not os.path.isfile(path) and not os.path.isabs(path):
					path = get_data_path(path)
				if not path:
					return "fail"
				else:
					self.droptarget.OnDropFiles(0, 0, [path])
			return "ok"
		return "invalid"

	def set_trc(self, gamma):
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
		white = XYZ["wX"], XYZ["wY"], XYZ["wZ"]
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
			black = colormath.adapt(XYZ["kX"], XYZ["kY"], XYZ["kZ"], white)
			profile.tags.rTRC = ICCP.CurveType()
			profile.tags.gTRC = ICCP.CurveType()
			profile.tags.bTRC = ICCP.CurveType()
			channels = "rgb"
		else:
			# Grayscale profile
			profile = ICCP.ICCProfile()
			profile.colorSpace = "GRAY"
			profile.setCopyright(getcfg("copyright"))
			profile.tags.wtpt = ICCP.XYZType()
			(profile.tags.wtpt.X,
			 profile.tags.wtpt.Y,
			 profile.tags.wtpt.Z) = (XYZ["wX"], XYZ["wY"], XYZ["wZ"])
			black = [XYZ["wY"] * (getcfg("synthprofile.black_luminance") /
								  getcfg("synthprofile.luminance"))] * 3
			profile.tags.kTRC = ICCP.CurveType()
			channels = "k"
		if self.trc_ctrl.GetSelection() == 1:
			# DICOM
			# Absolute luminance values!
			try:
				if self.colorspace_rgb_ctrl.Value:
					# Color profile
					profile.set_dicom_trc([v * getcfg("synthprofile.luminance")
										   for v in black],
										  getcfg("synthprofile.luminance"))
				else:
					# Grayscale profile
					profile.tags.kTRC.set_dicom_trc(getcfg("synthprofile.black_luminance"),
													getcfg("synthprofile.luminance"))
			except ValueError, exception:
				show_result_dialog(exception, self)
				return
		elif self.trc_ctrl.GetSelection() in (0, 4) and black != [0, 0, 0]:
			# Gamma with output offset or Rec. 1886-like
			outoffset = getcfg("synthprofile.trc_output_offset")
			if self.colorspace_rgb_ctrl.Value:
				# Color profile
				profile.set_bt1886_trc(black, outoffset, gamma,
									   getcfg("synthprofile.trc_gamma_type"))
			else:
				# Grayscale profile
				profile.tags.kTRC.set_bt1886_trc(black[1], outoffset, gamma,
												 getcfg("synthprofile.trc_gamma_type"))
		elif black != [0, 0, 0]:
			if self.colorspace_rgb_ctrl.Value:
				# Color profile
				rXYZ = profile.tags.rXYZ.values()
				gXYZ = profile.tags.gXYZ.values()
				bXYZ = profile.tags.bXYZ.values()
				mtx = colormath.Matrix3x3([[rXYZ[0], gXYZ[0], bXYZ[0]],
										   [rXYZ[1], gXYZ[1], bXYZ[1]],
										   [rXYZ[2], gXYZ[2], bXYZ[2]]])
				rgbblack = mtx.inverted() * black
			else:
				# Grayscale profile
				rgbblack = black
			# Optimize for uInt16Number encoding
			rgbblack = [round(max(v, 0) * 65535) / 65535 for v in rgbblack]
			for i, channel in enumerate(channels):
				TRC = profile.tags["%sTRC" % channel]
				TRC.set_trc(trc, 1024, vmin=rgbblack[i] * 65535)
		else:
			for channel in channels:
				profile.tags["%sTRC" % channel].set_trc(trc, 1)
		for tagname in ("lumi", "bkpt"):
			if tagname == "lumi":
				# Absolute
				X, Y, Z = [(v / XYZ["wY"]) * getcfg("synthprofile.luminance")
						   for v in (XYZ["wX"], XYZ["wY"], XYZ["wZ"])]
			else:
				X, Y, Z = (XYZ["kX"], XYZ["kY"], XYZ["kZ"])
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
			profile.setDescription(os.path.splitext(os.path.basename(path))[0])
			profile.calculateID()
			try:
				profile.write(path)
			except Exception, exception:
				show_result_dialog(exception, self)
	
	def setup_language(self):
		BaseFrame.setup_language(self)
		
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
		if not self._updating_ctrls:
			self.update_trc_controls()

	def trc_gamma_type_ctrl_handler(self, event):
		setcfg("synthprofile.trc_gamma_type",
			   self.trc_gamma_types_ab[self.trc_gamma_type_ctrl.GetSelection()])
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
		self.black_luminance_ctrl_handler(True)
	
	def white_XYZ_ctrl_handler(self, event):
		self.parse_XYZ("white")
		self.parse_xy()
	
	def white_xy_ctrl_handler(self, event):
		self.parse_xy("white")
		


def main():
	config.initcfg("synthprofile")
	lang.init()
	lang.update_defaults()
	app = BaseApp(0)
	app.TopWindow = SynthICCFrame()
	app.TopWindow.init_menubar()
	app.TopWindow.listen()
	app.process_argv(1)
	app.TopWindow.Show()
	app.MainLoop()

if __name__ == "__main__":
	main()
