# -*- coding: utf-8 -*-

import re
import subprocess as sp
import math
import os
import sys
import tempfile

from config import (defaults, fs_enc, get_data_path,
					get_display_profile, getbitmap, getcfg, geticon, setcfg,
					writecfg)
from meta import name as appname
from ordereddict import OrderedDict
from util_str import safe_unicode, universal_newlines, wrap
from worker import (Error, check_set_argyll_bin, get_argyll_util,
					show_result_dialog)
from wxaddons import get_platform_window_decoration_size, wx
from wxLUTViewer import LUTCanvas, LUTFrame
from wxwindows import (BitmapBackgroundPanelText, FileDrop, InfoDialog,
					   SimpleBook, TwoWaySplitter)
import colormath
import config
import wxenhancedplot as plot
import localization as lang
import ICCProfile as ICCP

BGCOLOUR = "#333333"
FGCOLOUR = "#999999"
TEXTCOLOUR = "#333333"

if sys.platform == "darwin":
	FONTSIZE_LARGE = 11
	FONTSIZE_MEDIUM = 11
	FONTSIZE_SMALL = 10
else:
	FONTSIZE_LARGE = 10
	FONTSIZE_MEDIUM = 8
	FONTSIZE_SMALL = 8


class GamutCanvas(LUTCanvas):

	def __init__(self, *args, **kwargs):
		LUTCanvas.__init__(self, *args, **kwargs)
		self.SetEnableTitle(False)
		self.SetFontSizeAxis(FONTSIZE_SMALL)
		self.SetFontSizeLegend(FONTSIZE_SMALL)
		self.spec_x = 8
		self.spec_y = 8
		self.SetXSpec(self.spec_x)
		self.SetYSpec(self.spec_y)
		self.pcs_data = []
		self.profiles = {}
		self.colorspace = "a*b*"
		self.intent = ""
		self.reset()
		self.resetzoom()
		self.HandCursor = wx.StockCursor(wx.CURSOR_CROSS)
		self.GrabHandCursor = wx.StockCursor(wx.CURSOR_SIZING)
	
	def _DrawCanvas(self, graphics):
		""" Draw proportionally correct, center and zoom """
		w = float(self.GetSize()[0] or 1)
		h = float(self.GetSize()[1] or 1)
		if w > 45:
			w -= 45
		if h > 20:
			h -= 20
		ratio = [w / h,
				 h / w]
		axis_x, axis_y = self.axis, self.axis
		if ratio[0] > ratio[1]:
			self.SetXSpec(self.spec_x * ratio[0])
		else:
			self.SetXSpec(self.spec_x)
		if ratio[0] > 1:
			axis_x=tuple([v * ratio[0] for v in self.axis])
		if ratio[1] > ratio[0]:
			self.SetYSpec(self.spec_y * ratio[1])
		else:
			self.SetYSpec(self.spec_y)
		if ratio[1] > 1:
			axis_y=tuple([v * ratio[1] for v in self.axis])
		x, y = self.center_x, self.center_y
		w = (axis_x[1] - axis_x[0]) * self._zoomfactor
		h = (axis_y[1] - axis_y[0]) * self._zoomfactor
		axis_x = (x - w / 2, x + w / 2)
		axis_y = (y - h / 2, y + h / 2)
		self.Draw(graphics, axis_x, axis_y)
	
	def _set_center(self):
		""" Set center position from current X and Y axis """
		axis_x = self.GetXCurrentRange()
		axis_y = self.GetYCurrentRange()
		if axis_x[0] < 0:
			if axis_x[1] < 0:
				x = axis_x[0] + (abs(axis_x[0]) - abs(axis_x[1])) / 2.0
			else:
				x = axis_x[0] + (abs(axis_x[1]) + abs(axis_x[0])) / 2.0
		else:
			x = axis_x[0] + (abs(axis_x[1]) - abs(axis_x[0])) / 2.0
		if axis_y[0] < 0:
			if axis_y[1] < 0:
				y = axis_y[0] + (abs(axis_y[0]) - abs(axis_y[1])) / 2.0
			else:
				y = axis_y[0] + (abs(axis_y[1]) + abs(axis_y[0])) / 2.0
		else:
			y = axis_y[0] + (abs(axis_y[1]) - abs(axis_y[0])) / 2.0
		self.center_x, self.center_y = x, y

	def DrawCanvas(self, title=None, colorspace=None, whitepoint=None,
				   center=False, show_outline=True):
		if not title:
			title = ""
		if colorspace:
			self.colorspace = colorspace
		
		# Defaults
		poly = plot.PolyLine
		poly._attributes["width"] = 3
		polys = []
		if self.colorspace == "xy":
			self.spec_x = 8
			self.spec_y = 8
			label_x = "x"
			label_y = "y"
			if show_outline:
				polys.append(plot.PolySpline([(0.173, 0.003),
											  (0.165, 0.010),
											  (0.157, 0.017),
											  (0.144, 0.029),
											  (0.135, 0.039),
											  (0.124, 0.057),
											  (0.109, 0.086),
											  (0.090, 0.131),
											  (0.068, 0.200),
											  (0.045, 0.295),
											  (0.023, 0.413),
											  (0.007, 0.538),
											  (0.003, 0.655),
											  (0.013, 0.750),
											  (0.039, 0.814),
											  (0.074, 0.835),
											  (0.115, 0.827),
											  (0.156, 0.807),
											  (0.194, 0.783),
											  (0.230, 0.755),
											  (0.266, 0.725),
											  (0.303, 0.693),
											  (0.338, 0.660),
											  (0.374, 0.626),
											  (0.513, 0.488),
											  (0.740, 0.260)],
											 colour=wx.Colour(102, 102, 102, 153),
											 width=1.75))
				polys.append(plot.PolyLine([(0.173, 0.003), (0.740, 0.260)],
										   colour=wx.Colour(102, 102, 102, 153),
										   width=1.75))
			max_x = 0.84
			max_y = 0.84
			min_x = 0
			min_y = 0
			step = .1
		elif self.colorspace == "u'v'":
			self.spec_x = 6
			self.spec_y = 6
			label_x = "u'"
			label_y = "v'"
			if show_outline:
				polys.append(plot.PolySpline([(0.260, 0.018),
											  (0.254, 0.016),
											  (0.232, 0.038),
											  (0.213, 0.059),
											  (0.186, 0.090),
											  (0.142, 0.154),
											  (0.082, 0.272),
											  (0.028, 0.410),
											  (0.005, 0.501),
											  (0.001, 0.543),
											  (0.002, 0.559),
											  (0.006, 0.570),
											  (0.012, 0.577),
											  (0.021, 0.583),
											  (0.036, 0.586),
											  (0.052, 0.587),
											  (0.081, 0.586),
											  (0.115, 0.582),
											  (0.156, 0.577),
											  (0.207, 0.569),
											  (0.264, 0.561),
											  (0.334, 0.550),
											  (0.408, 0.539),
											  (0.472, 0.530),
											  (0.624, 0.507)],
											 colour=wx.Colour(102, 102, 102, 153),
											 width=1.75))
				polys.append(plot.PolyLine([(0.260, 0.018), (0.624, 0.507)],
										   colour=wx.Colour(102, 102, 102, 153),
										   width=1.75))
			max_x = 0.6
			max_y = 0.6
			min_x = 0
			min_y = 0
			step = .1
		elif self.colorspace == "u*v*":
			# Not used, hard to present gamut projection appropriately in 2D
			# because blue tones 'cave in' towards the center
			label_x = "u*"
			label_y = "v*"
			max_x = 50.0
			max_y = 50.0
			min_x = -50.0
			min_y = -50.0
			step = 50
		else:
			label_x = "a*"
			label_y = "b*"
			if show_outline:
				# Very rough
				polys.append(plot.PolySpline([(102, -131),
											  (119, -134),
											  (128, -133),
											  (127, -123),
											  (124, -118),
											  (114, -108),
											  (115, -94),
											  (116, -77),
											  (114, -63),
											  (110, -46),
											  (104, -27),
											  (97, -1),
											  (92, 32),
											  (90, 53),
											  (89, 73),
											  (88, 90),
											  (84, 102),
											  (75, 114),
											  (64, 124),
											  (50, 133),
											  (35, 141),
											  (17, 145),
											  (-6, 140),
											  (-46, 129),
											  (-81, 116),
											  (-113, 97),
											  (-144, 68),
											  (-160, 39),
											  (-163, 26),
											  (-162, 16),
											  (-155, 4),
											  (-135, -12),
											  (-89, -46),
											  (-58, -67),
											  (-29, -83),
											  (17, -103),
											  (67, -121),
											  (102, -131)],
											 colour=wx.Colour(102, 102, 102, 153),
											 width=1.75))
			max_x = 130.0
			max_y = 146.0
			min_x = -166.0
			min_y = -136.0
			step = 50
		
		convert2coords = {"a*b*": lambda X, Y, Z: colormath.XYZ2Lab(*[v * 100 for v in X, Y, Z])[1:],
						  "xy": lambda X, Y, Z: colormath.XYZ2xyY(X, Y, Z)[:2],
						  "u*v*": lambda X, Y, Z: colormath.XYZ2Luv(*[v * 100 for v in X, Y, Z])[1:],
						  "u'v'": lambda X, Y, Z: colormath.XYZ2Lu_v_(X, Y, Z)[1:]}[self.colorspace]
		
		# Add color temp graph from 4000 to 9000K
		if whitepoint == 1:
			colortemps = []
			for kelvin in xrange(4000, 25001, 100):
				colortemps.append(convert2coords(*colormath.CIEDCCT2XYZ(kelvin)))
			polys.append(plot.PolySpline(colortemps,
										 colour=wx.Colour(255, 255, 255, 204),
										 width=1.5))
		elif whitepoint == 2:
			colortemps = []
			for kelvin in xrange(1667, 25001, 100):
				colortemps.append(convert2coords(*colormath.planckianCT2XYZ(kelvin)))
			polys.append(plot.PolySpline(colortemps,
										 colour=wx.Colour(255, 255, 255, 204),
										 width=1.5))

		kwargs = {"scale": 255}

		amount = len(self.pcs_data)

		for i, pcs_triplets in enumerate(reversed(self.pcs_data)):
			if not pcs_triplets or len(pcs_triplets) == 1:
				amount -= 1
				continue

			# Convert xicclu output to coordinates
			coords = []
			for pcs_triplet in pcs_triplets:
				coords.append(convert2coords(*pcs_triplet))

			xy = []
			for x, y in coords[:-1]:
				xy.append((x, y))
				if i == 0 or amount == 1:
					if x > max_x:
						max_x = x
					if y > max_y:
						max_y = y
					if x < min_x:
						min_x = x
					if y < min_y:
						min_y = y

			xy2 = []
			for j, (x, y) in enumerate(xy):
				xy2.append((x, y))
				if len(xy2) == self.size:
					xy3 = []
					for k, (x, y) in enumerate(xy2):
						xy3.append((x, y))
						if len(xy3) == 2:
							if i == 1:
								# Draw comparison profile with grey outline
								RGBA = 102, 102, 102, 255
								w = 2
							else:
								RGBA = colormath.XYZ2RGB(*pcs_triplets[j - len(xy2) + k], **kwargs)
								w = 3
							polys.append(poly(list(xy3), colour=wx.Colour(*RGBA),
											  width=w))
							if i == 1:
								xy3 = []
							else:
								xy3 = xy3[1:]
					xy2 = xy2[self.size:]
			
			# Add whitepoint
			x, y = coords[-1]
			if i == 1:
				# Draw comparison profile with grey outline
				RGBA = 204, 204, 204, 102
				marker="cross"
				s = 1.5
				w = 1.75
			else:
				RGBA = colormath.XYZ2RGB(*pcs_triplets[-1], **kwargs)
				marker = "plus"
				s = 2
				w = 1.75
			polys.append(plot.PolyMarker([(x, y)],
										 colour=wx.Colour(*RGBA),
										 size=s,
										 marker=marker,
										 width=w))
		
		max_abs_x = max(abs(min_x), max_x)
		max_abs_y = max(abs(min_y), max_y)

		if center:
			self.axis = (min(min_x, min_y), max(max_x, max_y))
			self.center_x = 0 + (min_x + max_x) / 2
			self.center_y = 0 + (min_y + max_y) / 2
		self.ratio = [max(max_abs_x, max_abs_y) /
					  max(max_abs_x, max_abs_y)] * 2
		if colorspace == "ab":
			ab_range = max(abs(min_x), abs(min_y)) + max(max_x, max_y)
			self.spec_x = ab_range / step
			self.spec_y = ab_range / step

		if polys:
			self._DrawCanvas(plot.PlotGraphics(polys, title, label_x, label_y))

	def OnMouseDoubleClick(self, event):
		self.resetzoom()
		if self.GetEnableDrag() and self.last_draw:
			self.center()

	def OnMouseLeftUp(self, event):
		if self._dragEnabled:
			self.SetCursor(self.HandCursor)
			if self.canvas.HasCapture():
				self.canvas.ReleaseMouse()
				self._set_center()
	
	def center(self):
		""" Center the current graphic """
		min_x, max_x = self.GetXMaxRange()
		min_y, max_y = self.GetYMaxRange()
		self.axis = (min(min_x, min_y), max(max_x, max_y))
		self.center_x = 0 + sum((min_x, max_x)) / 2
		self.center_y = 0 + sum((min_y, max_y)) / 2
		self._DrawCanvas(self.last_draw[0])
	
	def reset(self):
		self.axis = -128, 128
		self.ratio = 1.0, 1.0
	
	def resetzoom(self):
		self.center_x = 0
		self.center_y = 0
		self._zoomfactor = 1.0

	def set_pcs_data(self, i):
		if len(self.pcs_data) < i + 1:
			self.pcs_data.append([])
		else:
			self.pcs_data[i] = []
	
	def setup(self, profiles=None, profile_no=None, intent="a"):
		self.size = 40  # Number of segments from one primary to the next secondary color
		
		if not check_set_argyll_bin():
			return
		
		# Setup xicclu
		xicclu = get_argyll_util("xicclu")
		if not xicclu:
			return
		xicclu = xicclu.encode(fs_enc)
		cwd = self.worker.create_tempdir()
		if isinstance(cwd, Exception):
			raise cwd
		if sys.platform == "win32":
			startupinfo = sp.STARTUPINFO()
			startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
			startupinfo.wShowWindow = sp.SW_HIDE
		else:
			startupinfo = None
		
		if not profiles:
			profiles = [ICCP.ICCProfile(get_data_path("ref/sRGB.icm")),
						get_display_profile()]
		for i, profile in enumerate(profiles):
			if profile_no is not None and i != profile_no:
				continue

			if not profile or profile.profileClass == "link":
				self.set_pcs_data(i)
				self.profiles[i] = ""
				continue

			id = profile.calculateID(False)
			if self.profiles.get(i) == id and intent == self.intent:
				continue

			self.profiles[i] = id

			self.set_pcs_data(i)

			channels = {'XYZ': 3,
						'Lab': 3,
						'Luv': 3,
						'YCbr': 3,
						'Yxy': 3,
						'RGB': 3,
						'GRAY': 1,
						'HSV': 3,
						'HLS': 3,
						'CMYK': 4,
						'CMY': 3,
						'2CLR': 2,
						'3CLR': 3,
						'4CLR': 4,
						'5CLR': 5,
						'6CLR': 6,
						'7CLR': 7,
						'8CLR': 8,
						'9CLR': 9,
						'ACLR': 10,
						'BCLR': 11,
						'CCLR': 12,
						'DCLR': 13,
						'ECLR': 14,
						'FCLR': 15}.get(profile.colorSpace)

			if not channels:
				raise Error(lang.getstr("profile.unsupported",
										(profile.profileClass,
										 profile.colorSpace)))

			# Create input values
			device_values = []
			step = 1.0 / (self.size - 1)
			for j in xrange(min(3, channels)):
				for k in xrange(min(3, channels)):
					device_value = [0.0] * channels
					device_value[j] = 1.0
					if j != k:
						for l in xrange(self.size):
							device_value[k] = step * l
							device_values.append(list(device_value))
			# Add white
			if profile.colorSpace in ("RGB", "GRAY"):
				device_values.append([1.0] * channels)
			else:
				device_values.append([0.0] * channels)

			# Convert RGB triplets to list of strings
			for j, device_value in enumerate(device_values):
				device_values[j] = " ".join(str(n) for n in device_value)

			# Prepare profile
			profile.write(os.path.join(cwd, "profile.icc"))

			# Lookup RGB -> XYZ values through profile using xicclu
			stderr = tempfile.SpooledTemporaryFile()
			try:
				p = sp.Popen([xicclu, "-ff", "-i" + intent, "-px", "profile.icc"], 
							 stdin=sp.PIPE, stdout=sp.PIPE, stderr=stderr, 
							 cwd=cwd.encode(fs_enc), startupinfo=startupinfo)
			except Exception, exception:
				raise Error("\n".join([safe_unicode(v) for v in (xicclu,
																 exception)]))
			self.worker.subprocess = p
			if p.poll() not in (0, None):
				stderr.seek(0)
				raise Error(stderr.read().strip())
			try:
				odata = p.communicate("\n".join(device_values))[0].splitlines()
			except IOError:
				stderr.seek(0)
				raise Error(stderr.read().strip())
			if p.wait() != 0:
				raise IOError(''.join(odata))
			stderr.close()
		
			pcs_triplets = []
			for line in odata:
				line = "".join(line.strip().split("->")).split()
				pcs_triplets.append([float(n) for n in line[channels + 2:channels + 5]])
			if len(self.pcs_data) < i + 1:
				self.pcs_data.append(pcs_triplets)
			else:
				self.pcs_data[i] = pcs_triplets
		
		# Remove temporary files
		self.worker.wrapup(False)
		
		self.intent = intent
	
	def zoom(self, direction=1):
		_zoomfactor = .025 * direction
		if (self._zoomfactor + _zoomfactor > 0 and
			self._zoomfactor + _zoomfactor <= 5):
			self._zoomfactor += _zoomfactor
			self._set_center()
			self._DrawCanvas(self.last_draw[0])


class GamutViewOptions(wx.Panel):
	
	def __init__(self, *args, **kwargs):
		wx.Panel.__init__(self, *args, **kwargs)
		self.SetBackgroundColour(BGCOLOUR)
		self.sizer = wx.FlexGridSizer(0, 3, 4)
		self.sizer.AddGrowableCol(0)
		self.sizer.AddGrowableCol(2)
		self.SetSizer(self.sizer)

		self.sizer.Add((0, 0))
		legendsizer = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer.Add(legendsizer)
		
		# Whitepoint legend
		legendsizer.Add(wx.StaticBitmap(self, -1,
											   getbitmap("theme/cross-2px-12x12-fff")),
							   flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
							   border=2)
		self.whitepoint_legend = wx.StaticText(self, -1,
											   lang.getstr("whitepoint"))
		self.whitepoint_legend.SetMaxFontSize(11)
		self.whitepoint_legend.SetForegroundColour(FGCOLOUR)
		legendsizer.Add(self.whitepoint_legend,
							 flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
							 border=10)
		
		# Comparison profile whitepoint legend
		self.comparison_whitepoint_bmp = wx.StaticBitmap(self, -1,
														 getbitmap("theme/x-2px-12x12-999"))
		legendsizer.Add(self.comparison_whitepoint_bmp,
						flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
							 border=20)
		self.comparison_whitepoint_legend = wx.StaticText(self, -1,
														  "%s (%s)" % (lang.getstr("whitepoint"),
																	   lang.getstr("comparison_profile")))
		self.comparison_whitepoint_legend.SetMaxFontSize(11)
		self.comparison_whitepoint_legend.SetForegroundColour(FGCOLOUR)
		legendsizer.Add(self.comparison_whitepoint_legend,
						flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=8)
		self.sizer.Add((0, 0))
		
		# Empty 'row'
		self.sizer.Add((0, 0))
		self.sizer.Add((0, 0))
		self.sizer.Add((0, 0))
		
		self.sizer.Add((0, 0))
		self.options_sizer = wx.FlexGridSizer(0, 3, 4, 8)
		self.sizer.Add(self.options_sizer)
		
		# Colorspace select
		self.colorspace_outline_bmp = wx.StaticBitmap(self, -1,
													  getbitmap("theme/solid-16x2-666"))
		self.options_sizer.Add(self.colorspace_outline_bmp,
							   flag=wx.ALIGN_CENTER_VERTICAL)
		self.colorspace_label = wx.StaticText(self, -1,
											  lang.getstr("colorspace"))
		self.colorspace_label.SetMaxFontSize(11)
		self.colorspace_label.SetForegroundColour(FGCOLOUR)
		self.options_sizer.Add(self.colorspace_label,
							   flag=wx.ALIGN_CENTER_VERTICAL)
		self.colorspace_select = wx.Choice(self, -1,
												 size=(150, -1), 
												 choices=["CIE a*b*",
														  #"CIE u*v*",
														  "CIE u'v'",
														  "CIE xy"])
		self.options_sizer.Add(self.colorspace_select, 
							   flag=wx.ALIGN_CENTER_VERTICAL)
		self.colorspace_select.Bind(wx.EVT_CHOICE, self.generic_select_handler)
		self.colorspace_select.SetSelection(0)
		
		# Colorspace outline
		self.options_sizer.Add((0, 0))
		self.options_sizer.Add((0, 0))
		self.draw_gamut_outline_cb = wx.CheckBox(self, -1,
												 lang.getstr("colorspace.show_outline"))
		self.draw_gamut_outline_cb.Bind(wx.EVT_CHECKBOX,
										self.draw_gamut_outline_handler)
		self.draw_gamut_outline_cb.SetMaxFontSize(11)
		self.draw_gamut_outline_cb.SetForegroundColour(FGCOLOUR)
		self.draw_gamut_outline_cb.SetValue(True)
		self.options_sizer.Add(self.draw_gamut_outline_cb,
							   flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
							   border=4)
		
		# Colortemperature curve select
		self.whitepoint_bmp = wx.StaticBitmap(self, -1,
											  getbitmap("theme/solid-16x1-fff"))
		self.options_sizer.Add(self.whitepoint_bmp,
							   flag=wx.ALIGN_CENTER_VERTICAL)
		self.whitepoint_label = wx.StaticText(self, -1,
										 lang.getstr("whitepoint.colortemp.locus.curve"))
		self.whitepoint_label.SetMaxFontSize(11)
		self.whitepoint_label.SetForegroundColour(FGCOLOUR)
		self.options_sizer.Add(self.whitepoint_label,
							   flag=wx.ALIGN_CENTER_VERTICAL)
		self.whitepoint_select = wx.Choice(self, -1,
												 size=(150, -1), 
												 choices=[lang.getstr("calibration.file.none"),
														  lang.getstr("whitepoint.colortemp.locus.daylight"),
														  lang.getstr("whitepoint.colortemp.locus.blackbody")])
		self.options_sizer.Add(self.whitepoint_select, 
							   flag=wx.ALIGN_CENTER_VERTICAL)
		self.whitepoint_select.Bind(wx.EVT_CHOICE, self.generic_select_handler)
		self.whitepoint_select.SetSelection(0)
		self.whitepoint_bmp.Hide()
		
		# Comparison profile select
		self.comparison_profile_bmp = wx.StaticBitmap(self, -1,
													  getbitmap("theme/dashed-16x2-666"))
		self.options_sizer.Add(self.comparison_profile_bmp,
							   flag=wx.ALIGN_CENTER_VERTICAL)
		self.comparison_profile_label = wx.StaticText(self, -1,
													  lang.getstr("comparison_profile"))
		self.comparison_profile_label.SetMaxFontSize(11)
		self.comparison_profile_label.SetForegroundColour(FGCOLOUR)
		self.options_sizer.Add(self.comparison_profile_label,
							   flag=wx.ALIGN_CENTER_VERTICAL)
		self.comparison_profiles = OrderedDict([(lang.getstr("calibration.file.none"),
												 None)])
		for name in ["sRGB", "ClayRGB1998", "DCI_P3", "Rec601_525_60",
					 "Rec601_625_50", "Rec709", "SMPTE240M"]:
			path = get_data_path("ref/%s.icm" % name)
			if path:
				profile = ICCP.ICCProfile(path)
				self.comparison_profiles[profile.getDescription()] = profile
		for path in ["AdobeRGB1998.icc",
					 "ECI-RGB.V1.0.icc",
					 "eciRGB_v2.icc",
					 "GRACoL2006_Coated1v2.icc",
					 "ISOcoated.icc",
					 "ISOcoated_v2_eci.icc",
					 #"ISOnewspaper26v4.icc",
					 #"ISOuncoated.icc",
					 #"ISOuncoatedyellowish.icc",
					 "ISOwebcoated.icc",
					 "LStar-RGB.icc",
					 "LStar-RGB-v2.icc",
					 "ProPhoto.icm",
					 "PSO_Coated_300_NPscreen_ISO12647_eci.icc",
					 "PSO_Coated_NPscreen_ISO12647_eci.icc",
					 "PSO_LWC_Improved_eci.icc",
					 "PSO_LWC_Standard_eci.icc",
					 "PSO_MFC_Paper_eci.icc",
					 #"PSO_Uncoated_ISO12647_eci.icc",
					 #"PSO_Uncoated_NPscreen_ISO12647_eci.icc",
					 #"PSO_SNP_Paper_eci.icc",
					 "SC_paper_eci.icc",
					 "SWOP2006_Coated3v2.icc",
					 "SWOP2006_Coated5v2.icc"]:
			try:
				profile = ICCP.ICCProfile(path)
			except IOError:
				pass
			else:
				self.comparison_profiles[profile.getDescription()] = profile
		comparison_profiles = self.comparison_profiles[2:]
		def cmp(x, y):
			if x.lower() > y.lower():
				return 1
			if x.lower() < y.lower():
				return -1
			return 0
		comparison_profiles.sort(cmp)
		self.comparison_profiles = self.comparison_profiles[:2]
		self.comparison_profiles.update(comparison_profiles)
		self.comparison_profile_select = wx.Choice(self, -1,
												   size=(150, -1), 
												   choices=self.comparison_profiles.keys()[:2] +
														   comparison_profiles.keys())
		self.options_sizer.Add(self.comparison_profile_select, 
							   flag=wx.ALIGN_CENTER_VERTICAL)
		self.comparison_profile_select.Bind(wx.EVT_CHOICE,
											self.comparison_profile_select_handler)
		self.comparison_profile_select.SetSelection(1)
		
		# Rendering intent select
		self.options_sizer.Add((0, 0))
		self.rendering_intent_label = wx.StaticText(self, -1,
													lang.getstr("rendering_intent"))
		self.rendering_intent_label.SetMaxFontSize(11)
		self.rendering_intent_label.SetForegroundColour(FGCOLOUR)
		self.options_sizer.Add(self.rendering_intent_label,
							   flag=wx.ALIGN_CENTER_VERTICAL)
		self.rendering_intent_select = wx.Choice(self, -1,
												 size=(150, -1), 
												 choices=[lang.getstr("gamap.intents.a"),
														  lang.getstr("gamap.intents.r"),
														  lang.getstr("gamap.intents.p"),
														  lang.getstr("gamap.intents.s")])
		self.options_sizer.Add(self.rendering_intent_select, 
							   flag=wx.ALIGN_CENTER_VERTICAL)
		self.rendering_intent_select.Bind(wx.EVT_CHOICE,
										  self.rendering_intent_select_handler)
		self.rendering_intent_select.SetSelection(0)

		self.sizer.Add((0, 0))

	def DrawCanvas(self, profile_no=None, reset=True):
		# Gamut plot
		parent = self.Parent.Parent.Parent.Parent
		parent.client.SetEnableCenterLines(False)
		parent.client.SetEnableDiagonals(False)
		parent.client.SetEnableDrag(True)
		parent.client.SetEnableGrid(True)
		parent.client.SetEnablePointLabel(False)
		try:
			parent.client.setup([self.comparison_profiles.values()[self.comparison_profile_select.GetSelection()],
								 parent.profile],
								profile_no,
								intent={0: "a",
										1: "r",
										2: "p",
										3: "s"}.get(self.rendering_intent_select.GetSelection()))
		except Exception, exception:
			show_result_dialog(exception, parent)
		if reset:
			parent.client.reset()
			parent.client.resetzoom()
		self.draw(center=reset)
	
	def comparison_profile_select_handler(self, event):
		self.comparison_whitepoint_bmp.Show(self.comparison_profile_select.GetSelection() > 0)
		self.comparison_whitepoint_legend.Show(self.comparison_profile_select.GetSelection() > 0)
		self.comparison_profile_bmp.Show(self.comparison_profile_select.GetSelection() > 0)
		self.DrawCanvas(0, reset=False)

	def draw(self, center=False):
		colorspace = {0: "a*b*",
					  1: "u'v'",
					  2: "xy"}.get(self.colorspace_select.GetSelection(),
								   "a*b*")
		parent = self.Parent.Parent.Parent.Parent
		parent.client.DrawCanvas("%s %s" % (colorspace,
											lang.getstr("colorspace")),
								 colorspace,
								 whitepoint=self.whitepoint_select.GetSelection(),
								 center=center,
								 show_outline=self.draw_gamut_outline_cb.GetValue())
	
	def draw_gamut_outline_handler(self, event):
		self.colorspace_outline_bmp.Show(self.draw_gamut_outline_cb.GetValue())
		self.draw()
	
	def generic_select_handler(self, event):
		self.whitepoint_bmp.Show(self.whitepoint_select.GetSelection() > 0)
		parent = self.Parent.Parent.Parent.Parent
		if parent.client.profiles:
			self.draw(center=event.GetId() == self.colorspace_select.GetId())
		else:
			self.DrawCanvas()

	def rendering_intent_select_handler(self, event):
		self.DrawCanvas(reset=False)


class ProfileInfoFrame(LUTFrame):

	def __init__(self, *args, **kwargs):
	
		if len(args) < 3 and not "title" in kwargs:
			kwargs["title"] = lang.getstr("profile.info")
		
		wx.Frame.__init__(self, *args, **kwargs)
		
		self.SetIcons(config.get_icon_bundle([256, 48, 32, 16],
											 appname + "-profile-info"))
		
		self.CreateStatusBar(1)
		
		self.profile = None
		self.xLabel = lang.getstr("in")
		self.yLabel = lang.getstr("out")
		
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		self.SetSizer(self.sizer)
		
		self.title_panel = BitmapBackgroundPanelText(self)
		self.title_panel.SetForegroundColour(TEXTCOLOUR)
		self.title_panel.SetBitmap(getbitmap("theme/gradient"))
		self.sizer.Add(self.title_panel, flag=wx.EXPAND)
		
		self.title_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.title_panel.SetSizer(self.title_sizer)
		
		self.title_txt = self.title_panel
		font = wx.Font(FONTSIZE_LARGE, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, 
					   wx.FONTWEIGHT_NORMAL)
		self.title_txt.SetFont(font)
		self.title_sizer.Add((0, 32))
		
		gridbgcolor = wx.Colour(234, 234, 234)
		
		self.splitter = TwoWaySplitter(self, -1, agwStyle = wx.SP_LIVE_UPDATE | wx.SP_NOSASH)
		self.splitter.SetBackgroundColour(wx.Colour(204, 204, 204))
		self.sizer.Add(self.splitter, 1, flag=wx.EXPAND)
		
		p1 = wx.Panel(self.splitter)
		p1.SetBackgroundColour(BGCOLOUR)
		p1.sizer = wx.BoxSizer(wx.VERTICAL)
		p1.SetSizer(p1.sizer)
		self.splitter.AppendWindow(p1)

		self.plot_mode_sizer = wx.BoxSizer(wx.HORIZONTAL)
		p1.sizer.Add(self.plot_mode_sizer, flag=wx.ALIGN_CENTER | wx.TOP, border=12)
		
		# The order of the choice items is significant for compatibility
		# with LUTFrame:
		# 0 = vcgt,
		# 1 = [rgb]TRC
		# 2 = gamut
		self.plot_mode_select = wx.Choice(p1, -1, choices=[lang.getstr("vcgt"),
														   lang.getstr("[rgb]TRC"),
														   lang.getstr("gamut")])
		self.plot_mode_sizer.Add(self.plot_mode_select, flag=wx.ALIGN_CENTER_VERTICAL |
															 wx.LEFT, border=20)
		self.plot_mode_select.Bind(wx.EVT_CHOICE, self.plot_mode_select_handler)
		self.plot_mode_select.SetSelection(2)
		self.plot_mode_select.Disable()
		
		self.tooltip_btn = wx.StaticBitmap(p1, -1, geticon(16, "dialog-information"),
										   style=wx.NO_BORDER)
		self.tooltip_btn.SetBackgroundColour(BGCOLOUR)
		self.tooltip_btn.SetToolTipString(lang.getstr("gamut_plot.tooltip"))
		self.tooltip_btn.SetCursor(wx.StockCursor(wx.CURSOR_QUESTION_ARROW))
		self.plot_mode_sizer.Add(self.tooltip_btn, flag=wx.ALIGN_CENTER_VERTICAL |
														wx.LEFT, border=8)

		self.save_plot_btn = wx.BitmapButton(p1, -1,
											 geticon(16, "media-floppy"),
											 style=wx.NO_BORDER)
		self.save_plot_btn.SetBackgroundColour(BGCOLOUR)
		self.save_plot_btn.Bind(wx.EVT_BUTTON, self.SaveFile)
		self.save_plot_btn.SetToolTipString(lang.getstr("save_as"))
		self.save_plot_btn.SetBitmapDisabled(geticon(16, "empty"))
		self.save_plot_btn.Disable()
		self.plot_mode_sizer.Add(self.save_plot_btn, flag=wx.ALIGN_CENTER_VERTICAL |
														  wx.LEFT, border=8)

		self.client = GamutCanvas(p1)
		p1.sizer.Add(self.client, 1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT |
										  wx.TOP | wx.BOTTOM, border=4)
		
		self.options_panel = SimpleBook(p1)
		self.options_panel.SetBackgroundColour(BGCOLOUR)
		p1.sizer.Add(self.options_panel, flag=wx.EXPAND | wx.BOTTOM, border=12)
		
		# Gamut view options
		self.options_panel.AddPage(GamutViewOptions(p1), "")
		
		# Curve view options
		self.lut_view_options = wx.Panel(p1)
		self.lut_view_options.SetBackgroundColour(BGCOLOUR)
		self.lut_view_options_sizer = wx.FlexGridSizer(0, 8, 4, 4)
		self.lut_view_options_sizer.AddGrowableCol(0)
		self.lut_view_options_sizer.AddGrowableCol(7)
		self.lut_view_options.SetSizer(self.lut_view_options_sizer)
		self.options_panel.AddPage(self.lut_view_options, "")
		
		self.lut_view_options_sizer.Add((0, 0))
		
		self.lut_view_options_sizer.Add((26, 0))
		
		self.show_as_L = wx.CheckBox(self.lut_view_options, -1, u"L* \u2192")
		self.show_as_L.SetForegroundColour(FGCOLOUR)
		self.show_as_L.SetValue(True)
		self.lut_view_options_sizer.Add(self.show_as_L,
										flag=wx.ALIGN_CENTER_VERTICAL)
		self.Bind(wx.EVT_CHECKBOX, self.DrawLUT, id=self.show_as_L.GetId())
		
		self.toggle_red = wx.CheckBox(self.lut_view_options, -1, "R")
		self.toggle_red.SetForegroundColour(FGCOLOUR)
		self.toggle_red.SetValue(True)
		self.lut_view_options_sizer.Add(self.toggle_red,
										flag=wx.ALIGN_CENTER_VERTICAL)
		self.Bind(wx.EVT_CHECKBOX, self.DrawLUT, id=self.toggle_red.GetId())
		
		self.toggle_green = wx.CheckBox(self.lut_view_options, -1, "G")
		self.toggle_green.SetForegroundColour(FGCOLOUR)
		self.toggle_green.SetValue(True)
		self.lut_view_options_sizer.Add(self.toggle_green,
										flag=wx.ALIGN_CENTER_VERTICAL)
		self.Bind(wx.EVT_CHECKBOX, self.DrawLUT, id=self.toggle_green.GetId())
		
		self.toggle_blue = wx.CheckBox(self.lut_view_options, -1, "B")
		self.toggle_blue.SetForegroundColour(FGCOLOUR)
		self.toggle_blue.SetValue(True)
		self.lut_view_options_sizer.Add(self.toggle_blue,
										flag=wx.ALIGN_CENTER_VERTICAL)
		self.Bind(wx.EVT_CHECKBOX, self.DrawLUT, id=self.toggle_blue.GetId())
		
		self.toggle_clut = wx.CheckBox(self.lut_view_options, -1, "LUT")
		self.toggle_clut.SetForegroundColour(FGCOLOUR)
		self.toggle_clut.SetValue(True)
		self.lut_view_options_sizer.Add(self.toggle_clut, flag=wx.ALIGN_CENTER_VERTICAL |
												   wx.LEFT, border=16)
		self.Bind(wx.EVT_CHECKBOX, self.toggle_clut_handler,
				  id=self.toggle_clut.GetId())
		
		self.lut_view_options_sizer.Add((0, 0))
		
		p2 = wx.Panel(self.splitter)
		p2.SetBackgroundColour(gridbgcolor)
		p2.sizer = wx.BoxSizer(wx.VERTICAL)
		p2.SetSizer(p2.sizer)
		self.splitter.AppendWindow(p2)
		
		self.grid = wx.grid.Grid(p2, -1)
		self.grid.CreateGrid(0, 2)
		self.grid.SetCellHighlightColour(gridbgcolor)
		self.grid.SetCellHighlightPenWidth(0)
		self.grid.SetCellHighlightROPenWidth(0)
		self.grid.SetDefaultCellBackgroundColour(gridbgcolor)
		self.grid.SetDefaultCellTextColour(TEXTCOLOUR)
		font = wx.Font(FONTSIZE_MEDIUM, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, 
					   wx.FONTWEIGHT_NORMAL)
		self.grid.SetDefaultCellFont(font)
		self.grid.SetDefaultRowSize(20)
		self.grid.SetLabelBackgroundColour(gridbgcolor)
		self.grid.SetRowLabelSize(0)
		self.grid.SetColLabelSize(0)
		self.grid.DisableDragRowSize()
		self.grid.EnableDragColSize()
		self.grid.EnableEditing(False)
		self.grid.EnableGridLines(False)
		self.grid.Bind(wx.grid.EVT_GRID_COL_SIZE, self.resize_grid)
		p2.sizer.Add(self.grid, 1, flag=wx.EXPAND, border=12)
		
		drophandlers = {
			".icc": self.drop_handler,
			".icm": self.drop_handler
		}
		droptarget = FileDrop(drophandlers, parent=self)
		self.title_panel.SetDropTarget(droptarget)
		droptarget = FileDrop(drophandlers, parent=self)
		self.title_txt.SetDropTarget(droptarget)
		droptarget = FileDrop(drophandlers, parent=self)
		self.client.SetDropTarget(droptarget)
		droptarget = FileDrop(drophandlers, parent=self)
		self.grid.SetDropTarget(droptarget)

		self.splitter.SetMinimumPaneSize(defaults["size.profile_info.w"] - self.splitter._GetSashSize())
		self.splitter.SetHSplit(0)
		
		border, titlebar = get_platform_window_decoration_size()
		self.SetSaneGeometry(
			getcfg("position.profile_info.x"),
			getcfg("position.profile_info.y"),
			getcfg("size.profile_info.w") + border * 2,
			getcfg("size.profile_info.h") + titlebar + border)
		self.SetMinSize((defaults["size.profile_info.w"] + border * 2,
						 defaults["size.profile_info.h"] + titlebar + border))
		self.splitter.SetSplitSize((getcfg("size.profile_info.split.w") + border * 2,
									self.GetSize()[1]))
		self.splitter.SetExpandedSize(self.GetSize())
		self.splitter.SetExpanded(0)
		
		self.client.canvas.Bind(wx.EVT_MOTION, self.OnMotion)
		self.Bind(wx.EVT_MOVE, self.OnMove)
		self.Bind(wx.EVT_SIZE, self.OnSize)
		self.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGING, self.OnSashPosChanging)

		children = self.GetAllChildren()

		for child in children:
			if isinstance(child, wx.Choice):
				child.SetMaxFontSize(11)
			child.Bind(wx.EVT_KEY_DOWN, self.key_handler)
			child.Bind(wx.EVT_MOUSEWHEEL, self.OnWheel)

	def DrawCanvas(self, profile_no=None, reset=True):
		self.SetStatusText('')
		if self.plot_mode_select.GetSelection() == self.plot_mode_select.GetCount() - 1:
			# Gamut plot
			self.plot_mode_sizer.Show(self.tooltip_btn)
			self.options_panel.GetCurrentPage().DrawCanvas(reset=reset)
			self.save_plot_btn.Enable()
		else:
			# Curves plot
			self.plot_mode_sizer.Hide(self.tooltip_btn)
			self.client.SetEnableCenterLines(True)
			self.client.SetEnableDiagonals('Bottomleft-Topright')
			self.client.SetEnableDrag(False)
			self.client.SetEnableGrid(False)
			self.client.SetEnablePointLabel(True)
			self.client.SetXSpec(5)
			self.client.SetYSpec(5)
			if ("vcgt" in self.profile.tags or
				("rTRC" in self.profile.tags and
				 "gTRC" in self.profile.tags and
				 "bTRC" in self.profile.tags) or
				("B2A0" in self.profile.tags and
				 self.profile.colorSpace == "RGB")):
				self.toggle_red.Enable()
				self.toggle_green.Enable()
				self.toggle_blue.Enable()
				self.DrawLUT()
			else:
				self.toggle_red.Disable()
				self.toggle_green.Disable()
				self.toggle_blue.Disable()
				self.client.DrawLUT()
		self.splitter.GetTopLeft().sizer.Layout()
		self.splitter.GetTopLeft().Refresh()

	def LoadProfile(self, profile):
		if not isinstance(profile, ICCP.ICCProfile):
			try:
				profile = ICCP.ICCProfile(profile)
			except ICCP.ICCProfileInvalidError, exception:
				show_result_dialog(Error(lang.getstr("profile.invalid") + 
									     "\n" + profile), self)
				return
		self.profile = profile
		self.rTRC = profile.tags.get("rTRC")
		self.gTRC = profile.tags.get("gTRC")
		self.bTRC = profile.tags.get("bTRC")
		self.trc = None
		
		plot_mode = self.plot_mode_select.GetSelection()
		plot_mode_count = self.plot_mode_select.GetCount()
		choice = []
		info = profile.get_info()
		if (("rTRC" in self.profile.tags and "gTRC" in self.profile.tags and
			 "bTRC" in self.profile.tags) or
			("B2A0" in self.profile.tags and self.profile.colorSpace == "RGB")):
			# vcgt needs to be in here for compatibility with LUTFrame
			choice.append(lang.getstr("vcgt"))
			try:
				self.lookup_tone_response_curves()
			except Exception, exception:
				show_result_dialog(exception, self)
			else:
				choice.append(lang.getstr("[rgb]TRC"))
		choice.append(lang.getstr("gamut"))
		self.Freeze()
		self.plot_mode_select.SetItems(choice)
		if plot_mode_count != self.plot_mode_select.GetCount():
			plot_mode = self.plot_mode_select.GetCount() - 1
		self.plot_mode_select.SetSelection(min(plot_mode,
											   self.plot_mode_select.GetCount() - 1))
		self.select_current_page()
		self.plot_mode_select.Enable()
		
		self.title_txt.SetLabel(profile.getDescription())
		border, titlebar = get_platform_window_decoration_size()
		titlewidth = self.title_txt.GetTextExtent(self.title_txt.GetLabel())[0] + 30
		if titlewidth > defaults["size.profile_info.w"]:
			defaults["size.profile_info.w"] = titlewidth
		if titlewidth > defaults["size.profile_info.split.w"]:
			defaults["size.profile_info.split.w"] = titlewidth
		if titlewidth + border * 2 > self.GetMinSize()[0]:
			self.SetMinSize((titlewidth + border * 2,
							 defaults["size.profile_info.h"] + titlebar + border))
			if titlewidth + border * 2 > self.GetSize()[0]:
				self.SetSize((self.get_platform_window_size()[0],
							  self.GetSize()[1]))
				self.splitter.SetExpandedSize(self.get_platform_window_size())
		
		rows = [("", "")]
		lines = []
		for label, value in info:
			label = label.replace("\0", "")
			value = wrap(universal_newlines(value.strip()), 52).replace("\0", "").split("\n")
			linecount = len(value)
			for i, line in enumerate(value):
				value[i] = line.strip()
			label = universal_newlines(label).split("\n")
			while len(label) < linecount:
				label.append("")
			lines.extend(zip(label, value))
		for i, line in enumerate(lines):
			line = list(line)
			indent = re.match("\s+", line[0])
			if indent:
				#if i + 1 < len(lines) and lines[i + 1][0].startswith(" "):
					#marker = u" ├  "
				#else:
					#marker = u" └  "
				line[0] = indent.group() + lang.getstr(line[0].strip())
			elif line[0]:
				#if i + 1 < len(lines) and lines[i + 1][0].startswith(" "):
					#marker = u"▼ "
				#else:
					#marker = u"► "
				line[0] = lang.getstr(line[0])
			line[1] = lang.getstr(line[1])
			rows.append(line)
		
		rows.append(("", ""))
		
		if self.grid.GetNumberRows():
			self.grid.DeleteRows(0, self.grid.GetNumberRows())
		self.grid.AppendRows(len(rows))
		labelcolor = wx.Colour(0x80, 0x80, 0x80)
		altcolor = wx.Colour(230, 230, 230)
		for i, (label, value) in enumerate(rows):
			self.grid.SetCellValue(i, 0, " " * 4 + label)
			if i % 2:
				self.grid.SetCellBackgroundColour(i, 0, altcolor)
				self.grid.SetCellBackgroundColour(i, 1, altcolor)
			self.grid.SetCellTextColour(i, 0, labelcolor)
			self.grid.SetCellValue(i, 1, value)
		
		self.grid.AutoSizeColumn(0)
		self.resize_grid()
		self.DrawCanvas()
		self.Thaw()

	def OnMotion(self, event):
		if isinstance(event, wx.MouseEvent):
			xy = self.client._getXY(event)
		else:
			xy = event
		if self.plot_mode_select.GetSelection() < self.plot_mode_select.GetCount() - 1:
			# Curves plot
			self.UpdatePointLabel(xy)
		else:
			# Gamut plot
			if self.options_panel.GetCurrentPage().colorspace_select.GetSelection() == 0:
				format = "%.2f %.2f"
			else:
				format = "%.4f %.4f"
			page = self.options_panel.GetCurrentPage()
			colorspace_no = page.colorspace_select.GetSelection()
			whitepoint_no = page.whitepoint_select.GetSelection()
			if whitepoint_no > 0:
				if colorspace_no == 0:
					# a*b*
					x, y, Y = colormath.Lab2xyY(100.0, xy[0], xy[1])
				elif colorspace_no == 1:
					# u' v'
					x, y = colormath.u_v_2xy(xy[0], xy[1])
				else:
					x, y = xy
				cct, delta = colormath.xy_CCT_delta(x, y,
													daylight=whitepoint_no == 1)
				status = format % xy
				if cct:
					if delta:
						locus = {"Blackbody": "blackbody",
								 "Daylight": "daylight"}.get(page.whitepoint_select.GetStringSelection(),
															 page.whitepoint_select.GetStringSelection())
						status = u"%s, CCT %i (%s %.2f)" % (
							format % xy, cct, lang.getstr("delta_e_to_locus", 
														  locus),
							delta["E"])
					else:
						status = u"%s, CCT %i" % (format % xy, cct)
				self.SetStatusText(status)
			else:
				self.SetStatusText(format % xy)
		if isinstance(event, wx.MouseEvent):
			event.Skip() # Go to next handler

	def OnMove(self, event=None):
		if self.IsShownOnScreen() and not \
		   self.IsMaximized() and not self.IsIconized():
			x, y = self.GetScreenPosition()
			setcfg("position.profile_info.x", x)
			setcfg("position.profile_info.y", y)
		if event:
			event.Skip()
	
	def OnSashPosChanging(self, event):
		border, titlebar = get_platform_window_decoration_size()
		self.splitter.SetExpandedSize((self.splitter._splitx +
									   self.splitter._GetSashSize() +
									   border * 2,
									   self.GetSize()[1]))
		setcfg("size.profile_info.w", self.splitter._splitx +
									  self.splitter._GetSashSize())
		wx.CallAfter(self.redraw)
		wx.CallAfter(self.resize_grid)
	
	def OnSize(self, event=None):
		if self.IsShownOnScreen() and self.IsMaximized():
			self.splitter.AdjustLayout()
		self.splitter.Refresh()
		wx.CallAfter(self.redraw)
		wx.CallAfter(self.resize_grid)
		if self.IsShownOnScreen() and not self.IsIconized():
			wx.CallAfter(self._setsize)
		if event:
			event.Skip()
	
	def OnWheel(self, event):
		xy = wx.GetMousePosition()
		if not self.client.GetClientRect().Contains(self.client.ScreenToClient(xy)):
			if self.grid.GetClientRect().Contains(self.grid.ScreenToClient(xy)):
				self.grid.SetFocus()
			event.Skip()
		elif self.client.GetEnableDrag() and self.client.last_draw:
			if event.WheelRotation < 0:
				direction = 1.0
			else:
				direction = -1.0
			self.client.zoom(direction)
	
	def _setsize(self):
		if not self.IsMaximized():
			w, h = self.GetSize()
			border, titlebar = get_platform_window_decoration_size()
			if self.splitter._expanded < 0:
				self.splitter.SetExpandedSize((self.splitter._splitx +
											   self.splitter._GetSashSize() +
											   border * 2,
											   self.GetSize()[1]))
				self.splitter.SetSplitSize((w, self.GetSize()[1]))
				setcfg("size.profile_info.w", self.splitter._splitx +
											  self.splitter._GetSashSize())
				setcfg("size.profile_info.split.w", w - border * 2)
			else:
				self.splitter.SetExpandedSize((w, self.GetSize()[1]))
				setcfg("size.profile_info.w", w - border * 2)
			setcfg("size.profile_info.h", h - titlebar - border)
	
	def drop_handler(self, path):
		"""
		Drag'n'drop handler for .cal/.icc/.icm files.
		
		"""
		self.LoadProfile(path)


	def get_platform_window_size(self, defaultwidth=None, defaultheight=None,
								 split=False):
		if split:
			name = ".split"
		else:
			name = ""
		if not defaultwidth:
			defaultwidth = defaults["size.profile_info%s.w" % name]
		if not defaultheight:
			defaultheight = defaults["size.profile_info.h"]
		border, titlebar = get_platform_window_decoration_size()
		#return (max(max(getcfg("size.profile_info%s.w" % name),
						#defaultwidth) + border * 2, self.GetMinSize()[0]),
				#max(getcfg("size.profile_info.h"),
					#defaultheight) + titlebar + border)
		if split:
			w, h = self.splitter.GetSplitSize()
		else:
			w, h = self.splitter.GetExpandedSize()
		return (max(w, defaultwidth + border * 2, self.GetMinSize()[0]),
				max(h, defaultheight + titlebar + border))

	def key_handler(self, event):
		# AltDown
		# CmdDown
		# ControlDown
		# GetKeyCode
		# GetModifiers
		# GetPosition
		# GetRawKeyCode
		# GetRawKeyFlags
		# GetUniChar
		# GetUnicodeKey
		# GetX
		# GetY
		# HasModifiers
		# KeyCode
		# MetaDown
		# Modifiers
		# Position
		# RawKeyCode
		# RawKeyFlags
		# ShiftDown
		# UnicodeKey
		# X
		# Y
		key = event.GetKeyCode()
		if (event.ControlDown() or event.CmdDown()): # CTRL (Linux/Mac/Windows) / CMD (Mac)
			focus = self.FindFocus()
			if self.grid in (focus, focus.GetParent(), focus.GetGrandParent()):
				if key == 65: # A
					self.grid.SelectAll()
					return
				elif key in (67, 88): # C / X
					clip = []
					cells = self.grid.GetSelection()
					i = -1
					start_col = self.grid.GetNumberCols()
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
						clip[-1][col] = self.grid.GetCellValue(row, col)
					for i, row in enumerate(clip):
						clip[i] = "\t".join(row[start_col:])
					clipdata = wx.TextDataObject()
					clipdata.SetText("\n".join(clip))
					wx.TheClipboard.Open()
					wx.TheClipboard.SetData(clipdata)
					wx.TheClipboard.Close()
					return
			if key == 83 and self.profile: # S
				self.SaveFile()
				return
			else:
				event.Skip()
		elif key in (43, wx.WXK_NUMPAD_ADD) and self.client.GetEnableDrag():
			# + key zoom in
			self.client.zoom(-1)
		elif key in (45, wx.WXK_NUMPAD_SUBTRACT) and self.client.GetEnableDrag():
			# - key zoom out
			self.client.zoom(1)
		else:
			event.Skip()
	
	def plot_mode_select_handler(self, event):
		self.Freeze()
		self.select_current_page()
		self.DrawCanvas(reset=False)
		self.Thaw()
	
	def redraw(self):
		if self.plot_mode_select.GetSelection() == self.plot_mode_select.GetCount() - 1 and self.client.last_draw:
			# Update gamut plot
			self.client.Parent.Freeze()
			self.client._DrawCanvas(self.client.last_draw[0])
			self.client.Parent.Thaw()
	
	def resize_grid(self, event=None):
		self.grid.SetColSize(1, max(self.grid.GetSize()[0] -
									self.grid.GetColSize(0) -
									wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X),
									0))
		self.grid.SetMargins(0 - wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X),
							 0 - wx.SystemSettings_GetMetric(wx.SYS_HSCROLL_Y))
		self.grid.ForceRefresh()
	
	def select_current_page(self):
		if self.plot_mode_select.GetSelection() == self.plot_mode_select.GetCount() - 1:
			# Gamut plot
			self.options_panel.SetSelection(0)
		else:
			# Curves plot
			self.options_panel.SetSelection(1)
		self.splitter.GetTopLeft().Layout()


class ProfileInfoViewer(wx.App):

	def OnInit(self):
		check_set_argyll_bin()
		self.frame = ProfileInfoFrame(None, -1)
		return True


def main(profile=None):
	config.initcfg()
	lang.init()
	lang.update_defaults()
	app = ProfileInfoViewer(0)
	app.frame.LoadProfile(profile or get_display_profile())
	app.frame.Show(True)
	app.MainLoop()
	writecfg()

if __name__ == "__main__":
	main(*sys.argv[max(len(sys.argv) - 1, 1):])
