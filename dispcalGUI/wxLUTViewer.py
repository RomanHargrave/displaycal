#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from decimal import Decimal
import math
import os
import re
import subprocess as sp
import sys
import tempfile
import traceback

from numpy import interp

from argyll_cgats import cal_to_fake_profile
from config import (fs_enc, get_bitmap_as_icon, get_display_profile,
					get_display_rects, getcfg, geticon, setcfg)
from log import safe_print
from meta import name as appname
from options import debug
from util_decimal import float2dec
from util_os import waccess
from worker import (Error, Worker, get_argyll_util, make_argyll_compatible_path,
					show_result_dialog)
from wxaddons import FileDrop, wx
from wxenhancedplot import _Numeric
from wxMeasureFrame import MeasureFrame
from wxwindows import InfoDialog
import colormath
import config
import wxenhancedplot as plot
import localization as lang
import CGATS
import ICCProfile as ICCP

BGCOLOUR = "#333333"
FGCOLOUR = "#999999"
GRIDCOLOUR = "#444444"

if sys.platform == "darwin":
	FONTSIZE_LARGE = 11
	FONTSIZE_SMALL = 10
else:
	FONTSIZE_LARGE = 9
	FONTSIZE_SMALL = 8


class CoordinateType(list):
	
	"""
	List of coordinates.
	
	[(Y, x)] where Y is in the range 0..100 and x in the range 0..255
	
	"""
	
	def __init__(self):
		self._transfer_function = {}
	
	def get_gamma(self, use_vmin_vmax=False, average=True, least_squares=False,
				  slice=(0.01, 0.99)):
		""" Return average or least squares gamma or a list of gamma values """
		if len(self):
			start = slice[0] * 100
			end = slice[1] * 100
			values = []
			for i, (y, x) in enumerate(self):
				n = colormath.XYZ2Lab(0, y, 0)[0]
				if n >= start and n <= end:
					values.append((x / 255.0 * 100, y))
		else:
			# Identity
			if average or least_squares:
				return 1.0
			return [1.0]
		vmin = 0
		vmax = 100.0
		if use_vmin_vmax:
			if len(self) > 2:
				vmin = self[0][0]
				vmax = self[-1][0]
		return colormath.get_gamma(values, 100.0, vmin, vmax, average, least_squares)
	
	def get_transfer_function(self, best=True, slice=(0.05, 0.95)):
		"""
		Return transfer function name, exponent and match percentage
		
		"""
		transfer_function = self._transfer_function.get((best, slice))
		if transfer_function:
			return transfer_function
		trc = CoordinateType()
		match = {}
		vmin = self[0][0]
		vmax = self[-1][0]
		best_yx = (0, 255)
		for i, (y, x) in enumerate(self):
			if x - 127.5 > 0 and x < best_yx[1]:
				best_yx = (y, x)
		gamma = colormath.get_gamma([(best_yx[1] / 255.0 * 100.0, best_yx[0])], 100.0, vmin, vmax)
		for name, exp in (("Rec. 709", -709),
						  ("SMPTE 240M", -240),
						  ("L*", -3.0),
						  ("sRGB", -2.4),
						  ("Gamma %.2f" % gamma, gamma)):
			trc.set_trc(exp, self, vmin, vmax)
			match[(name, exp)] = 0.0
			count = 0
			start = slice[0] * 255
			end = slice[1] * 255
			for i, (n, x) in enumerate(self):
				##n = colormath.XYZ2Lab(0, n, 0)[0]
				if x >= start and x <= end:
					n = colormath.get_gamma([(x / 255.0 * 100, n)], 100.0, vmin, vmax, False)
					if n:
						n = n[0]
						##n2 = colormath.XYZ2Lab(0, trc[i][0], 0)[0]
						n2 = colormath.get_gamma([(trc[i][1] / 255.0 * 100, trc[i][0])], 100.0, vmin, vmax, False)
						if n2:
							n2 = n2[0]
							match[(name, exp)] += 1 - (max(n, n2) - min(n, n2)) / n2
							count += 1
			if count:
				match[(name, exp)] /= count
		if not best:
			self._transfer_function[(best, slice)] = match
			return match
		match, (name, exp) = sorted(zip(match.values(), match.keys()))[-1]
		self._transfer_function[(best, slice)] = (name, exp), match
		return (name, exp), match
	
	def set_trc(self, power=2.2, values=(), vmin=0, vmax=100):
		"""
		Set the response to a certain function.
		
		Positive power, or -2.4 = sRGB, -3.0 = L*, -240 = SMPTE 240M,
		-601 = Rec. 601, -709 = Rec. 709 (Rec. 601 and 709 transfer functions are
		identical)
		
		"""
		self[:] = [[y, x] for y, x in values]
		for i in xrange(len(self)):
			self[i][0] = vmin + colormath.specialpow(self[i][1] / 255.0, power) * (vmax - vmin)


class LUTCanvas(plot.PlotCanvas):

	def __init__(self, *args, **kwargs):
		plot.PlotCanvas.__init__(self, *args, **kwargs)
		self.canvas.Unbind(wx.EVT_LEAVE_WINDOW)
		self.SetBackgroundColour(BGCOLOUR)
		self.SetEnableAntiAliasing(True)
		self.SetEnableHiRes(True)
		self.SetEnableCenterLines(True)
		self.SetEnableDiagonals('Bottomleft-Topright')
		self.SetEnableGrid(False)
		self.SetEnablePointLabel(True)
		self.SetForegroundColour(FGCOLOUR)
		self.SetFontSizeAxis(FONTSIZE_SMALL)
		self.SetFontSizeLegend(FONTSIZE_SMALL)
		self.SetFontSizeTitle(FONTSIZE_LARGE)
		self.SetGridColour(GRIDCOLOUR)
		self.setLogScale((False,False))
		self.SetXSpec(5)
		self.SetYSpec(5)
		self.SetPointLabelFunc(self.DrawPointLabel)
		self.worker = Worker()

	def DrawLUT(self, vcgt=None, title=None, xLabel=None, yLabel=None, 
				r=True, g=True, b=True):
		if not title:
			title = ""
		if not xLabel:
			xLabel = ""
		if not yLabel:
			yLabel = ""
		
		detect_increments = False
		Plot = plot.PolyLine
		Plot._attributes["width"] = 1

		lines = []
		linear_points = []
		
		axis_y = 255.0
		if xLabel in ("L*", "Y"):
			axis_x = 100.0
		else:
			axis_x = 255.0
		
		self.point_grid = [{}, {}, {}]

		if not vcgt:
			irange = range(0, 256)
		elif "data" in vcgt: # table
			data = list(vcgt['data'])
			while len(data) < 3:
				data.append(data[0])
			r_points = []
			g_points = []
			b_points = []
			if (not isinstance(vcgt, ICCP.VideoCardGammaTableType) and
				not isinstance(data[0], ICCP.CurveType)):
				# Coordinate list
				irange = range(0, len(data[0]))
				for i in xrange(len(data)):
					if i == 0 and r:
						for n, y in data[i]:
							if xLabel == "L*":
								n = colormath.XYZ2Lab(0, n / axis_x * 100, 0)[0] * (axis_x / 100.0)
							r_points.append([n, y])
							self.point_grid[i][n] = y
					elif i == 1 and g:
						for n, y in data[i]:
							if xLabel == "L*":
								n = colormath.XYZ2Lab(0, n / axis_x * 100, 0)[0] * (axis_x / 100.0)
							g_points.append([n, y])
							self.point_grid[i][n] = y
					elif i == 2 and b:
						for n, y in data[i]:
							if xLabel == "L*":
								n = colormath.XYZ2Lab(0, n / axis_x * 100, 0)[0] * (axis_x / 100.0)
							b_points.append([n, y])
							self.point_grid[i][n] = y
			else:
				irange = range(0, vcgt['entryCount'])
				for i in irange:
					j = i * (axis_y / (vcgt['entryCount'] - 1))
					if not detect_increments:
						linear_points += [[j, j]]
					if r:
						n = float(data[0][i]) / (math.pow(256, vcgt['entrySize']) - 1) * axis_x
						if not detect_increments or not r_points or \
						   i == vcgt['entryCount'] - 1 or n != i:
							if detect_increments and n != i and \
							   len(r_points) == 1 and i > 1 and \
							   r_points[-1][0] == r_points[-1][1]:
								r_points += [[i - 1, i - 1]]
							if xLabel == "L*":
								n = colormath.XYZ2Lab(0, n / axis_x * 100, 0)[0] * (axis_x / 100.0)
							if xLabel in ("L*", "Y"):
								r_points += [[n, j]]
								self.point_grid[0][n] = j
							else:
								r_points += [[j, n]]
								self.point_grid[0][j] = n
					if g:
						n = float(data[1][i]) / (math.pow(256, vcgt['entrySize']) - 1) * axis_x
						if not detect_increments or not g_points or \
						   i == vcgt['entryCount'] - 1 or n != i:
							if detect_increments and n != i and \
							   len(g_points) == 1 and i > 1 and \
							   g_points[-1][0] == g_points[-1][1]:
								g_points += [[i - 1, i - 1]]
							if xLabel == "L*":
								n = colormath.XYZ2Lab(0, n / axis_x * 100, 0)[0] * (axis_x / 100.0)
							if xLabel in ("L*", "Y"):
								g_points += [[n, j]]
								self.point_grid[1][n] = j
							else:
								g_points += [[j, n]]
								self.point_grid[1][j] = n
					if b:
						n = float(data[2][i]) / (math.pow(256, vcgt['entrySize']) - 1) * axis_x
						if not detect_increments or not b_points or \
						   i == vcgt['entryCount'] - 1 or n != i:
							if detect_increments and n != i and \
							   len(b_points) == 1 and i > 1 and \
							   b_points[-1][0] == b_points[-1][1]:
								b_points += [[i - 1, i - 1]]
							if xLabel == "L*":
								n = colormath.XYZ2Lab(0, n / axis_x * 100, 0)[0] * (axis_x / 100.0)
							if xLabel in ("L*", "Y"):
								b_points += [[n, j]]
								self.point_grid[2][n] = j
							else:
								b_points += [[j, n]]
								self.point_grid[2][j] = n
		else: # formula
			irange = range(0, 256)
			step = 100.0 / axis_y
			r_points = []
			g_points = []
			b_points = []
			for i in irange:
				# float2dec(v) fixes miniscule deviations in the calculated gamma
				# n = float2dec(n, 8)
				if not detect_increments:
					linear_points += [[i, (i)]]
				if r:
					vmin = float2dec(vcgt["redMin"] * axis_x)
					v = float2dec(math.pow(step * i / 100.0, vcgt["redGamma"]))
					vmax = float2dec(vcgt["redMax"] * axis_x)
					n = vmin + v * (vmax - vmin)
					if xLabel == "L*":
						n = colormath.XYZ2Lab(0, float(n) / axis_x * 100, 0)[0] * (axis_x / 100.0)
					if xLabel in ("L*", "Y"):
						r_points += [[n, i]]
						self.point_grid[0][n] = i
					else:
						r_points += [[i, n]]
						self.point_grid[0][i] = n
				if g:
					vmin = float2dec(vcgt["greenMin"] * axis_x)
					v = float2dec(math.pow(step * i / 100.0, vcgt["greenGamma"]))
					vmax = float2dec(vcgt["greenMax"] * axis_x)
					n = vmin + v * (vmax - vmin)
					if xLabel == "L*":
						n = colormath.XYZ2Lab(0, float(n) / axis_x * 100, 0)[0] * (axis_x / 100.0)
					if xLabel in ("L*", "Y"):
						g_points += [[n, i]]
						self.point_grid[1][n] = i
					else:
						g_points += [[i, n]]
						self.point_grid[1][i] = n
				if b:
					vmin = float2dec(vcgt["blueMin"] * axis_x)
					v = float2dec(math.pow(step * i / 100.0, vcgt["blueGamma"]))
					vmax = float2dec(vcgt["blueMax"] * axis_x)
					n = vmin + v * (vmax - vmin)
					if xLabel == "L*":
						n = colormath.XYZ2Lab(0, float(n) / axis_x * 100, 0)[0] * (axis_x / 100.0)
					if xLabel in ("L*", "Y"):
						b_points += [[n, i]]
						self.point_grid[2][n] = i
					else:
						b_points += [[i, n]]
						self.point_grid[2][i] = n

		#for n in sorted(self.point_grid[0].keys()):
			#print n, self.point_grid[0].get(n), self.point_grid[1].get(n), self.point_grid[2].get(n)

		self.entryCount = irange[-1] + 1
		
		linear = [[0, 0], [irange[-1], irange[-1]]]
		
		if not vcgt:
			if detect_increments:
				r_points = g_points = b_points = linear
			else:
				r_points = g_points = b_points = linear_points
		
		self.r_unique = len(set(round(y) for x, y in r_points))
		self.g_unique = len(set(round(y) for x, y in g_points))
		self.b_unique = len(set(round(y) for x, y in b_points))

		legend = []
		colour = None
		if r and g and b and r_points == g_points == b_points:
			colour = 'white'
			points = r_points
			legend += ['R']
			legend += ['G']
			legend += ['B']
		elif r and g and r_points == g_points:
			colour = 'yellow'
			points = r_points
			legend += ['R']
			legend += ['G']
		elif r and b and r_points == b_points:
			colour = 'magenta'
			points = b_points
			legend += ['R']
			legend += ['B']
		elif g and b and g_points == b_points:
			colour = 'cyan'
			points = b_points
			legend += ['G']
			legend += ['B']
		else:
			if r:
				legend += ['R']
			if g:
				legend += ['G']
			if b:
				legend += ['B']
		if colour:
			suffix = ((', ' + lang.getstr('linear').capitalize()) if 
						points == (linear if detect_increments else 
									linear_points) else '')
			lines += [Plot(points, legend='='.join(legend) + suffix, 
						   colour=colour)]
		if colour != 'white':
			if r and colour not in ('yellow', 'magenta'):
				suffix = ((', ' + lang.getstr('linear').capitalize()) if 
							r_points == (linear if detect_increments else 
										  linear_points) else '')
				lines += [Plot(r_points, legend='R' + suffix, colour='red')]
			if g and colour not in ('yellow', 'cyan'):
				suffix = ((', ' + lang.getstr('linear').capitalize()) if 
							g_points == (linear if detect_increments else 
										  linear_points) else '')
				lines += [Plot(g_points, legend='G' + suffix, colour='green')]
			if b and colour not in ('cyan', 'magenta'):
				suffix = ((', ' + lang.getstr('linear').capitalize()) if 
							b_points == (linear if detect_increments else 
										  linear_points) else '')
				lines += [Plot(b_points, legend='B' + suffix, colour='#0080FF')]

		if not lines:
			lines += [Plot([])]

		self.Draw(plot.PlotGraphics(lines, title, " ".join([xLabel,
														    lang.getstr("in")]), 
									" ".join([yLabel, lang.getstr("out")])), 
				  xAxis=(0, axis_x), yAxis=(0, axis_y))

	def DrawPointLabel(self, dc, mDataDict):
		"""
		Draw point labels.
		
		dc - DC that will be passed
		mDataDict - Dictionary of data that you want to use for the pointLabel
		
		"""
		dc.SetPen(wx.Pen(wx.BLACK))
		dc.SetBrush(wx.Brush( wx.BLACK, wx.SOLID ) )
		
		sx, sy = mDataDict["scaledXY"]  # Scaled x, y of closest point
		dc.DrawRectangle(sx - 3, sy - 3, 7, 7)  # 7x7 square centered on point


class LUTFrame(wx.Frame):

	def __init__(self, *args, **kwargs):
	
		if len(args) < 3 and not "title" in kwargs:
			kwargs["title"] = lang.getstr("calibration.lut_viewer.title")
		
		wx.Frame.__init__(self, *args, **kwargs)
		
		self.SetIcons(config.get_icon_bundle([256, 48, 32, 16], appname))
		
		self.CreateStatusBar(1)
		
		self.profile = None
		self.xLabel = lang.getstr("in")
		self.yLabel = lang.getstr("out")
		
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		self.SetSizer(self.sizer)
		
		self.client = LUTCanvas(self)
		self.sizer.Add(self.client, 1, wx.EXPAND)
		
		self.box_panel = wx.Panel(self)
		self.box_panel.SetBackgroundColour(BGCOLOUR)
		self.sizer.Add(self.box_panel, flag=wx.EXPAND)
		
		self.box_sizer = wx.FlexGridSizer(0, 3)
		self.box_sizer.AddGrowableCol(0)
		self.box_sizer.AddGrowableCol(2)
		self.box_panel.SetSizer(self.box_sizer)
		
		self.box_sizer.Add((0, 0))
		
		self.cbox_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.box_sizer.Add(self.cbox_sizer, 
						   flag=wx.ALL | wx.ALIGN_CENTER | wx.ALIGN_CENTER_VERTICAL, 
						   border=8)
		
		self.box_sizer.Add((0, 0))
		
		self.plot_mode_select = wx.Choice(self.box_panel, -1, size=(-1, -1), 
										  choices=[])
		self.plot_mode_select.SetMaxFontSize(11)
		self.cbox_sizer.Add(self.plot_mode_select, flag=wx.ALIGN_CENTER_VERTICAL)
		self.Bind(wx.EVT_CHOICE, self.DrawLUT, id=self.plot_mode_select.GetId())
		
		self.cbox_sizer.Add((20, 0))
		
		self.show_as_L = wx.CheckBox(self.box_panel, -1, u"L* \u2192")
		self.show_as_L.SetForegroundColour(FGCOLOUR)
		self.show_as_L.SetMaxFontSize(11)
		self.show_as_L.SetValue(True)
		self.cbox_sizer.Add(self.show_as_L, flag=wx.ALIGN_CENTER_VERTICAL |
												 wx.RIGHT,
							border=4)
		self.Bind(wx.EVT_CHECKBOX, self.DrawLUT, id=self.show_as_L.GetId())
		
		self.toggle_red = wx.CheckBox(self.box_panel, -1, "R")
		self.toggle_red.SetForegroundColour(FGCOLOUR)
		self.toggle_red.SetMaxFontSize(11)
		self.toggle_red.SetValue(True)
		self.cbox_sizer.Add(self.toggle_red, flag=wx.ALIGN_CENTER_VERTICAL)
		self.Bind(wx.EVT_CHECKBOX, self.DrawLUT, id=self.toggle_red.GetId())
		
		self.cbox_sizer.Add((4, 0))
		
		self.toggle_green = wx.CheckBox(self.box_panel, -1, "G")
		self.toggle_green.SetForegroundColour(FGCOLOUR)
		self.toggle_green.SetMaxFontSize(11)
		self.toggle_green.SetValue(True)
		self.cbox_sizer.Add(self.toggle_green, flag=wx.ALIGN_CENTER_VERTICAL)
		self.Bind(wx.EVT_CHECKBOX, self.DrawLUT, id=self.toggle_green.GetId())
		
		self.cbox_sizer.Add((4, 0))
		
		self.toggle_blue = wx.CheckBox(self.box_panel, -1, "B")
		self.toggle_blue.SetForegroundColour(FGCOLOUR)
		self.toggle_blue.SetMaxFontSize(11)
		self.toggle_blue.SetValue(True)
		self.cbox_sizer.Add(self.toggle_blue, flag=wx.ALIGN_CENTER_VERTICAL)
		self.Bind(wx.EVT_CHECKBOX, self.DrawLUT, id=self.toggle_blue.GetId())
		
		self.toggle_clut = wx.CheckBox(self.box_panel, -1, "LUT")
		self.toggle_clut.SetForegroundColour(FGCOLOUR)
		self.toggle_clut.SetMaxFontSize(11)
		xicclu = get_argyll_util("xicclu")
		self.toggle_clut.SetValue(bool(xicclu))
		self.toggle_clut.Enable(bool(xicclu))
		self.cbox_sizer.Add(self.toggle_clut, flag=wx.ALIGN_CENTER_VERTICAL |
												   wx.LEFT, border=16)
		self.Bind(wx.EVT_CHECKBOX, self.toggle_clut_handler,
				  id=self.toggle_clut.GetId())

		self.save_plot_btn = wx.BitmapButton(self.box_panel, -1,
											 geticon(16, "media-floppy"),
											 style=wx.NO_BORDER)
		self.save_plot_btn.SetBackgroundColour(BGCOLOUR)
		self.cbox_sizer.Add(self.save_plot_btn, flag=wx.ALIGN_CENTER_VERTICAL |
													 wx.LEFT, border=16)
		self.save_plot_btn.Bind(wx.EVT_BUTTON, self.SaveFile)
		self.save_plot_btn.SetToolTipString(lang.getstr("save_as"))
		self.save_plot_btn.SetBitmapDisabled(geticon(16, "empty"))
		self.save_plot_btn.Disable()

		self.box_sizer.Add((0, 0))

		self.show_actual_lut_cb = wx.CheckBox(self.box_panel, -1,
											  lang.getstr("calibration.show_actual_lut"))
		self.show_actual_lut_cb.SetForegroundColour(FGCOLOUR)
		self.show_actual_lut_cb.SetMaxFontSize(11)
		self.box_sizer.Add(self.show_actual_lut_cb,
							flag=wx.ALIGN_CENTER | wx.BOTTOM, border=16)
		self.Bind(wx.EVT_CHECKBOX, self.show_actual_lut_handler,
				  id=self.show_actual_lut_cb.GetId())

		self.box_sizer.Add((0, 0))

		self.client.canvas.Bind(wx.EVT_MOTION, self.OnMotion)
		
		self.droptarget = FileDrop()
		self.droptarget.drophandlers = {
			".cal": self.drop_handler,
			".icc": self.drop_handler,
			".icm": self.drop_handler
		}
		self.droptarget.unsupported_handler = self.drop_unsupported_handler
		self.client.SetDropTarget(self.droptarget)
		
		self.SetSaneGeometry(
			getcfg("position.lut_viewer.x"), 
			getcfg("position.lut_viewer.y"), 
			getcfg("size.lut_viewer.w"), 
			getcfg("size.lut_viewer.h"))
		
		self.Bind(wx.EVT_MOVE, self.OnMove)
		self.Bind(wx.EVT_SIZE, self.OnSize)
		
		self.display_no = -1
		self.display_rects = get_display_rects()

	def drop_handler(self, path):
		"""
		Drag'n'drop handler for .cal/.icc/.icm files.
		
		"""
		filename, ext = os.path.splitext(path)
		if ext == ".cal":
			profile = cal_to_fake_profile(path)
			if not profile:
				InfoDialog(self, msg=lang.getstr("calibration.file.invalid") + 
									 "\n" + path, 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				return
		else:
			try:
				profile = ICCP.ICCProfile(path)
			except ICCP.ICCProfileInvalidError, exception:
				InfoDialog(self, msg=lang.getstr("profile.invalid") + 
									 "\n" + path, 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
				return
		self.LoadProfile(profile)
		self.DrawLUT()

	def drop_unsupported_handler(self):
		"""
		Drag'n'drop handler for unsupported files. 
		
		Shows an error message.
		
		"""
		files = self.droptarget._filenames
		InfoDialog(self, msg=lang.getstr("error.file_type_unsupported") +
							 "\n\n" + "\n".join(files), 
				   ok=lang.getstr("ok"), 
				   bitmap=geticon(32, "dialog-error"))
	
	get_display = MeasureFrame.__dict__["get_display"]
	
	def toggle_clut_handler(self, event):
		try:
			self.lookup_tone_response_curves()
		except Exception, exception:
			show_result_dialog(exception, self)
		else:
			self.trc = None
			self.DrawLUT()

	def show_actual_lut_handler(self, event):
		setcfg("lut_viewer.show_actual_lut", 
			   int(self.show_actual_lut_cb.GetValue()))
		if hasattr(self, "current_cal"):
			profile = self.current_cal
		else:
			profile = None
		self.load_lut(profile=profile)
	
	def load_lut(self, profile=None):
		self.current_cal = profile
		if (getcfg("lut_viewer.show_actual_lut") and
			self.worker.argyll_version >= [1, 1, 0] and
			not "Beta" in self.worker.argyll_version_string and
			not config.get_display_name() in ("Web", "Untethered")):
			tmp = self.worker.create_tempdir()
			if isinstance(tmp, Exception):
				show_result_dialog(tmp, self)
				return
			cmd, args = (get_argyll_util("dispwin"), 
						 ["-d" + self.worker.get_display(), "-s", 
						  os.path.join(tmp, 
									   re.sub(r"[\\/:*?\"<>|]+",
											  "",
											  make_argyll_compatible_path(
												config.get_display_name(
													include_geometry=True) or 
												"Video LUT")))])
			result = self.worker.exec_cmd(cmd, args, capture_output=True, 
										  skip_scripts=True, silent=not __name__ == "__main__")
			if not isinstance(result, Exception) and result:
				profile = cal_to_fake_profile(args[-1])
			else:
				if isinstance(result, Exception):
					safe_print(result)
			# Important: lut_viewer_load_lut is called after measurements,
			# so make sure to only delete the temporary cal file we created
			# (which hasn't an extension, so we can use ext_filter to 
			# exclude files which should not be deleted)
			self.worker.wrapup(copy=False, ext_filter=[".app", ".cal", 
													   ".ccmx", ".ccss",
													   ".cmd", ".command", 
													   ".gam", ".gz",
													   ".icc", ".icm",
													   ".log",
													   ".sh", ".ti1",
													   ".ti3", ".wrl",
													   ".wrz"])
		if profile and (profile.is_loaded or not profile.fileName or 
						os.path.isfile(profile.fileName)):
			if not self.profile or \
			   self.profile.fileName != profile.fileName or \
			   not self.profile.isSame(profile):
				self.LoadProfile(profile)
				self.DrawLUT()
		else:
			self.LoadProfile(None)
			self.DrawLUT()
	
	def lookup_tone_response_curves(self, intent="r"):
		""" Lookup Y -> RGB tone values through TRC tags or LUT """
		
		mult = 2
		size = 256 * mult  # Final number of coordinates

		if (intent == "r" and (not "B2A0" in self.profile.tags or
						       not self.toggle_clut.GetValue()) and
			isinstance(self.profile.tags.get("rTRC"), ICCP.CurveType) and
			isinstance(self.profile.tags.get("gTRC"), ICCP.CurveType) and
			isinstance(self.profile.tags.get("bTRC"), ICCP.CurveType)):
			#self.rTRC = self.profile.tags.rTRC
			#self.gTRC = self.profile.tags.gTRC
			#self.bTRC = self.profile.tags.bTRC
			#return
			# Use TRC tags if no LUT
			if (len(self.profile.tags.rTRC) == 1 and
				len(self.profile.tags.gTRC) == 1 and
				len(self.profile.tags.bTRC) == 1):
				# Gamma, convert to curves
				trc = {"rTRC": [],
					   "gTRC": [],
					   "bTRC": []}
				for sig in ("rTRC", "gTRC", "bTRC"):
					gamma = self.profile.tags[sig][0]
					setattr(self, sig, CoordinateType())
					for i in xrange(256):
						trc[sig].append(math.pow(i / 255.0, gamma) * 65535)
			else:
				trc = {"rTRC": self.profile.tags.rTRC,
					   "gTRC": self.profile.tags.gTRC,
					   "bTRC": self.profile.tags.bTRC}
			# Curves
			for sig in ("rTRC", "gTRC", "bTRC"):
				x, xp, y, yp = [], [], [], []
				# First, get actual values
				for i, Y in enumerate(trc[sig]):
					xp.append(i / (len(trc[sig]) - 1.0) * 255)
					yp.append(Y / 65535.0 * 100)
				# Second, interpolate to given size and use the same Y axis 
				# for all channels
				for i in xrange(size):
					x.append(i / (size - 1.0) * 255)
					y.append(colormath.Lab2XYZ(i / (size - 1.0) * 100, 0, 0)[1] * 100)
				yi = interp(x, xp, yp)
				xi = interp(y, yi, x)
				setattr(self, sig, CoordinateType())
				for v, Y in zip(xi, y):
					if Y <= yp[0]:
						Y = yp[0]
					getattr(self, sig).append([Y, v])
			return

		profile = self.profile
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
		
		# Setup xicclu
		xicclu = get_argyll_util("xicclu")
		if not xicclu:
			return
		xicclu = xicclu.encode(fs_enc)
		cwd = self.client.worker.create_tempdir()
		if isinstance(cwd, Exception):
			raise cwd
		if sys.platform == "win32":
			startupinfo = sp.STARTUPINFO()
			startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
			startupinfo.wShowWindow = sp.SW_HIDE
		else:
			startupinfo = None

		# Prepare profile
		profile.write(os.path.join(cwd, "profile.icc"))
		
		# Prepare input Lab values
		XYZ_triplets = []
		Lab_triplets = []
		for i in xrange(0, size):
			if intent == "a":
				# Experimental - basically this makes the resulting
				# response match relative colorimetric
				X, Y, Z = colormath.Lab2XYZ(i * (100.0 / (size - 1)), 0, 0)
				L, a, b = colormath.XYZ2Lab(*[v * 100 for v in
											  colormath.adapt(X, Y, Z,
															  whitepoint_destination=profile.tags.wtpt.values())])
			else:
				a = b = 0
			Lab_triplets.append(" ".join([str(i * (100.0 / (size - 1))),
										  str(a), str(b)]))
		
		# Lookup Lab -> RGB values through 'input' profile using xicclu
		stderr = tempfile.SpooledTemporaryFile()
		p = sp.Popen([xicclu, "-fb", "-i" + intent, "-pl", "profile.icc"], 
					 stdin=sp.PIPE, stdout=sp.PIPE, stderr=stderr, 
					 cwd=cwd.encode(fs_enc), startupinfo=startupinfo)
		self.client.worker.subprocess = p
		if p.poll() not in (0, None):
			stderr.seek(0)
			raise Error(stderr.read().strip())
		try:
			odata = p.communicate("\n".join(Lab_triplets))[0].splitlines()
		except IOError:
			stderr.seek(0)
			raise Error(stderr.read().strip())
		if p.wait() != 0:
			raise IOError(''.join(odata))
		stderr.close()

		# Remove temporary files
		self.client.worker.wrapup(False)

		rgb_triplets = []
		for i, line in enumerate(odata):
			line = "".join(line.strip().split("->")).split()
			rgb_triplet = [float(n) for n in line[channels + 2:channels + 5]]
			rgb_triplets.append(rgb_triplet)
		
		self.rTRC = CoordinateType()
		self.gTRC = CoordinateType()
		self.bTRC = CoordinateType()
		for j, rgb in enumerate(rgb_triplets):
			for i, v in enumerate(rgb):
				v *= 255
				y = colormath.Lab2XYZ(float(Lab_triplets[j].split()[0]), 0, 0)[1] * 100
				if i == 0:
					self.rTRC.append([y, v])
				elif i == 1:
					self.gTRC.append([y, v])
				elif i == 2:
					self.bTRC.append([y, v])

	def move_handler(self, event):
		if not self.IsShownOnScreen():
			return
		display_no, geometry, client_area = self.get_display()
		if display_no != self.display_no:
			self.display_no = display_no
			# Translate from wx display index to Argyll display index
			geometry = "%i, %i, %ix%i" % tuple(geometry)
			for i, display in enumerate(getcfg("displays").split(os.pathsep)):
				if display.find("@ " + geometry) > -1:
					if debug:
						safe_print("[D] Found display %s at index %i" % 
								   (geometry, i))
					# Save Argyll display index to configuration
					setcfg("display.number", i + 1)
					self.load_lut(get_display_profile(i))
					break
		event.Skip()

	def LoadProfile(self, profile):
		if not profile:
			profile = ICCP.ICCProfile()
			profile._data = "\0" * 128
			profile._tags.desc = ICCP.TextDescriptionType("", "desc")
			profile.size = len(profile.data)
			profile.is_loaded = True
		elif not isinstance(profile, ICCP.ICCProfile):
			profile = ICCP.ICCProfile(profile)
		self.profile = profile
		self.rTRC = profile.tags.get("rTRC")
		self.gTRC = profile.tags.get("gTRC")
		self.bTRC = profile.tags.get("bTRC")
		self.trc = None
		curves = []
		curves.append(lang.getstr('vcgt'))
		if ((isinstance(self.rTRC, ICCP.CurveType) and
			 isinstance(self.gTRC, ICCP.CurveType) and
			 isinstance(self.bTRC, ICCP.CurveType)) or
			("B2A0" in profile.tags and profile.colorSpace == "RGB")):
			try:
				self.lookup_tone_response_curves()
			except Exception, exception:
				show_result_dialog(exception, self)
			else:
				curves.append(lang.getstr('[rgb]TRC'))
		selection = self.plot_mode_select.GetSelection()
		if curves and (selection < 0 or selection > len(curves) - 1):
			selection = 0
		self.plot_mode_select.SetItems(curves)
		self.plot_mode_select.Enable(len(curves) > 1)
		self.plot_mode_select.SetSelection(selection)
		self.cbox_sizer.Layout()
		self.box_sizer.Layout()

	def add_tone_values(self, legend):
		if not self.profile:
			return
		colorants = legend[0]
		if (self.plot_mode_select.GetSelection() == 0 and
			'vcgt' in self.profile.tags):
			if 'R' in colorants or 'G' in colorants or 'B' in colorants:
				legend.append(lang.getstr("tone_values"))
				if '=' in colorants:
					unique = []
					if 'R' in colorants:
						unique.append(self.client.r_unique)
					if 'G' in colorants:
						unique.append(self.client.g_unique)
					if 'B' in colorants:
						unique.append(self.client.b_unique)
					unique = min(unique)
					legend[-1] += " %.1f%% (%i/%i) @ 8 Bit" % (unique / 
													   (self.client.entryCount / 
														100.0), unique, 
													   self.client.entryCount)
				else:
					if 'R' in colorants:
						legend[-1] += " %.1f%% (%i/%i) @ 8 Bit" % (self.client.r_unique / 
														   (self.client.entryCount / 
															100.0), 
														   self.client.r_unique, 
														   self.client.entryCount)
					if 'G' in colorants:
						legend[-1] += " %.1f%% (%i/%i) @ 8 Bit" % (self.client.g_unique / 
														   (self.client.entryCount / 
															100.0), 
														   self.client.g_unique, 
														   self.client.entryCount)
					if 'B' in colorants:
						legend[-1] += " %.1f%% (%i/%i) @ 8 Bit" % (self.client.b_unique / 
														   (self.client.entryCount / 
															100.0), 
														   self.client.b_unique, 
														   self.client.entryCount)
				unique = []
				unique.append(self.client.r_unique)
				unique.append(self.client.g_unique)
				unique.append(self.client.b_unique)
				if not 0 in unique:
					unique = min(unique)
					legend[-1] += ", %s %.1f%% (%i/%i) @ 8 Bit" % (lang.getstr("grayscale"), 
														   unique / 
														   (self.client.entryCount / 
															100.0), unique, 
														   self.client.entryCount)
		elif (self.plot_mode_select.GetSelection() == 1 and
			  isinstance(self.rTRC, (ICCP.CurveType, CoordinateType)) and
			  len(self.rTRC) > 1 and
			  isinstance(self.gTRC, (ICCP.CurveType, CoordinateType)) and
			  len(self.gTRC) > 1 and
			  isinstance(self.bTRC, (ICCP.CurveType, CoordinateType)) and
			  len(self.bTRC) > 1):
			transfer_function = None
			if (not getattr(self, "trc", None) and
				len(self.rTRC) == len(self.gTRC) == len(self.bTRC)):
				if isinstance(self.rTRC, ICCP.CurveType):
					self.trc = ICCP.CurveType()
					for i in xrange(len(self.rTRC)):
						self.trc.append(int(round((self.rTRC[i] +
												   self.gTRC[i] +
												   self.bTRC[i]) / 3.0)))
				else:
					self.trc = CoordinateType()
					for i in xrange(len(self.rTRC)):
						self.trc.append([(self.rTRC[i][0] +
										  self.gTRC[i][0] +
										  self.bTRC[i][0]) / 3.0,
										 (self.rTRC[i][1] +
										  self.gTRC[i][1] +
										  self.bTRC[i][1]) / 3.0])
			if getattr(self, "trc", None):
				transfer_function = self.trc.get_transfer_function(slice=(0.00, 1.00))
			#if "R" in colorants and "G" in colorants and "B" in colorants:
				#if self.profile.tags.rTRC == self.profile.tags.gTRC == self.profile.tags.bTRC:
					#transfer_function = self.profile.tags.rTRC.get_transfer_function()
			#elif ("R" in colorants and
				  #(not "G" in colorants or
				   #self.profile.tags.rTRC == self.profile.tags.gTRC) and
				  #(not "B" in colorants or
				   #self.profile.tags.rTRC == self.profile.tags.bTRC)):
				#transfer_function = self.profile.tags.rTRC.get_transfer_function()
			#elif ("G" in colorants and
				  #(not "R" in colorants or
				   #self.profile.tags.gTRC == self.profile.tags.rTRC) and
				  #(not "B" in colorants or
				   #self.profile.tags.gTRC == self.profile.tags.bTRC)):
				#transfer_function = self.profile.tags.gTRC.get_transfer_function()
			#elif ("B" in colorants and
				  #(not "G" in colorants or
				   #self.profile.tags.bTRC == self.profile.tags.gTRC) and
				  #(not "R" in colorants or
				   #self.profile.tags.bTRC == self.profile.tags.rTRC)):
				#transfer_function = self.profile.tags.bTRC.get_transfer_function()
			if transfer_function and transfer_function[1] >= .95:
				if self.rTRC == self.gTRC == self.bTRC:
					label = lang.getstr("rgb.trc")
				else:
					label = lang.getstr("rgb.trc.averaged")
				if round(transfer_function[1], 2) == 1.0:
					value = u"%s" % (transfer_function[0][0])
				else:
					value = u"≈ %s (Δ %.2f%%)" % (transfer_function[0][0],
												  100 - transfer_function[1] * 100)
				legend.append(" ".join([label, value]))

	def DrawLUT(self, event=None):
		self.SetStatusText('')
		self.Freeze()
		curves = None
		if self.profile:
			yLabel = []
			if self.toggle_red.GetValue():
				yLabel.append("R")
			if self.toggle_green.GetValue():
				yLabel.append("G")
			if self.toggle_blue.GetValue():
				yLabel.append("B")
			if self.plot_mode_select.GetSelection() == 0:
				if 'vcgt' in self.profile.tags:
					curves = self.profile.tags['vcgt']
				else:
					curves = None
				self.xLabel = "".join(yLabel)
				self.yLabel = "".join(yLabel)
			elif (self.plot_mode_select.GetSelection() == 1 and
				  isinstance(self.rTRC, (ICCP.CurveType, CoordinateType)) and
				  isinstance(self.gTRC, (ICCP.CurveType, CoordinateType)) and
				  isinstance(self.bTRC, (ICCP.CurveType, CoordinateType))):
				if (len(self.rTRC) == 1 and
					len(self.gTRC) == 1 and
					len(self.bTRC) == 1):
					# gamma
					curves = {
						'redMin': 0.0,
						'redGamma': self.rTRC[0],
						'redMax': 1.0,
						'greenMin': 0.0,
						'greenGamma': self.gTRC[0],
						'greenMax': 1.0,
						'blueMin': 0.0,
						'blueGamma': self.bTRC[0],
						'blueMax': 1.0
					}
				else:
					# curves
					curves = {
						'data': [self.rTRC,
								 self.gTRC,
								 self.bTRC],
						'entryCount': len(self.rTRC),
						'entrySize': 2
					}
				if self.show_as_L.GetValue():
					self.xLabel = "L*"
				else:
					self.xLabel = "Y"
				self.yLabel = "".join(yLabel)
		self.toggle_red.Enable(bool(curves))
		self.toggle_green.Enable(bool(curves))
		self.toggle_blue.Enable(bool(curves))
		self.show_as_L.Enable(bool(curves))
		self.show_as_L.Show(self.plot_mode_select.GetSelection() != 0)
		self.toggle_clut.Show(self.plot_mode_select.GetSelection() == 1 and
							  "B2A0" in self.profile.tags and
							  isinstance(self.profile.tags.get("rTRC"), ICCP.CurveType) and
							  isinstance(self.profile.tags.get("gTRC"), ICCP.CurveType) and
							  isinstance(self.profile.tags.get("bTRC"), ICCP.CurveType))
		self.save_plot_btn.Enable(bool(curves))
		self.show_as_L.GetContainingSizer().Layout()
		if hasattr(self, "show_actual_lut_cb"):
			self.show_actual_lut_cb.Show(self.plot_mode_select.GetSelection() == 0)
		if hasattr(self, "cbox_sizer"):
			self.cbox_sizer.Layout()
		if hasattr(self, "box_sizer"):
			self.box_sizer.Layout()
		if self.client.last_PointLabel != None:
			pointXY = self.client.last_PointLabel["pointXY"]
			self.client._drawPointLabel(self.client.last_PointLabel) #erase old
			self.client.last_PointLabel = None
		else:
			pointXY = (127.5, 127.5)
		self.client.DrawLUT(curves, title=self.profile.getDescription() if 
										  self.profile else None, 
							xLabel=self.xLabel,
							yLabel=self.yLabel,
							r=self.toggle_red.GetValue() if 
							  hasattr(self, "toggle_red") else False, 
							g=self.toggle_green.GetValue() if 
							  hasattr(self, "toggle_green") else False, 
							b=self.toggle_blue.GetValue() if 
							  hasattr(self, "toggle_blue") else False)
		self.Thaw()
		wx.CallLater(125, self.UpdatePointLabel, pointXY)

	def OnMotion(self, event):
		if isinstance(event, wx.MouseEvent):
			xy = self.client._getXY(event)
		else:
			xy = event
		self.UpdatePointLabel(xy)
		if isinstance(event, wx.MouseEvent):
			event.Skip() # Go to next handler

	def OnMove(self, event=None):
		if self.IsShownOnScreen() and not \
		   self.IsMaximized() and not self.IsIconized():
			x, y = self.GetScreenPosition()
			setcfg("position.lut_viewer.x", x)
			setcfg("position.lut_viewer.y", y)
		if event:
			event.Skip()
	
	def OnSize(self, event=None):
		if self.IsShownOnScreen() and not \
		   self.IsMaximized() and not self.IsIconized():
			w, h = self.GetSize()
			setcfg("size.lut_viewer.w", w)
			setcfg("size.lut_viewer.h", h)
		if event:
			event.Skip()

	def SaveFile(self, event=None):
		"""Saves the file to the type specified in the extension. If no file
		name is specified a dialog box is provided.  Returns True if sucessful,
		otherwise False.
		
		.bmp  Save a Windows bitmap file.
		.xbm  Save an X bitmap file.
		.xpm  Save an XPM bitmap file.
		.png  Save a Portable Network Graphics file.
		.jpg  Save a Joint Photographic Experts Group file.
		"""
		fileName = " ".join([self.plot_mode_select.GetStringSelection(),
							 os.path.basename(os.path.splitext(self.profile.fileName or
															   lang.getstr("unnamed"))[0])])
		extensions = {
			"bmp": wx.BITMAP_TYPE_BMP,       # Save a Windows bitmap file.
			"xbm": wx.BITMAP_TYPE_XBM,       # Save an X bitmap file.
			"xpm": wx.BITMAP_TYPE_XPM,       # Save an XPM bitmap file.
			"jpg": wx.BITMAP_TYPE_JPEG,      # Save a JPG file.
			"png": wx.BITMAP_TYPE_PNG,       # Save a PNG file.
			}

		fType = fileName[-3:].lower()
		dlg1 = None
		while fType not in extensions:

			if dlg1:                   # FileDialog exists: Check for extension
				InfoDialog(self,
						   msg=lang.getstr("error.file_type_unsupported"), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))
			else:                      # FileDialog doesn't exist: just check one
				dlg1 = wx.FileDialog(
					self, 
					lang.getstr("save_as"), ".", fileName,
					"PNG (*.png)|*.png|BMP (*.bmp)|*.bmp|XBM (*.xbm)|*.xbm|XPM (*.xpm)|*.xpm|JPG (*.jpg)|*.jpg",
					wx.SAVE|wx.OVERWRITE_PROMPT
					)

			if dlg1.ShowModal() == wx.ID_OK:
				fileName = dlg1.GetPath()
				if not waccess(fileName, os.W_OK):
					show_result_dialog(Error(lang.getstr("error.access_denied.write",
														 fileName)), self)
					return
				fType = fileName[-3:].lower()
			else:                      # exit without saving
				dlg1.Destroy()
				return False

		if dlg1:
			dlg1.Destroy()

		# Save Bitmap
		res= self.client._Buffer.SaveFile(fileName, extensions.get(fType, ".png"))
		return res
	
	def UpdatePointLabel(self, xy):
		if self.client.GetEnablePointLabel():
			# Show closest point (when enbled)
			# Make up dict with info for the point label
			dlst = self.client.GetClosestPoint(xy, pointScaled=True)
			if dlst != []:
				curveNum, legend, pIndex, pointXY, scaledXY, distance = dlst
				legend = legend.split(", ")
				R, G, B = (self.client.point_grid[0].get(pointXY[0],
							0 if self.toggle_red.GetValue() else None),
						   self.client.point_grid[1].get(pointXY[0],
							0 if self.toggle_green.GetValue() else None),
						   self.client.point_grid[2].get(pointXY[0],
							0 if self.toggle_blue.GetValue() else None))
				if (self.plot_mode_select.GetSelection() == 0 or
					R == G == B or ((R == G or G == B or R == B) and
									None in (R, G ,B))):
					rgb = ""
				else:
					rgb = legend[0] + " "
				if self.plot_mode_select.GetSelection() == 1:
					joiner = u" \u2192 "
					if self.show_as_L.GetValue():
						format = "L* %.4f", "%s %.2f"
					else:
						format = "Y %.4f", "%s %.2f"
					axis_y = 100.0
					if R == G == B or ((R == G or G == B or R == B) and
									   None in (R, G ,B)):
						#if R is None:
						RGB = " ".join(["=".join(["%s" % v for v, s in
												  filter(lambda v: v[1] is not None,
														 (("R", R), ("G", G), ("B", B)))]),
										"%.2f" % pointXY[1]])
						#else:
							#RGB = "R=G=B %.2f" % R
					else:
						RGB = " ".join([format[1] % (v, s) for v, s in
										filter(lambda v: v[1] is not None,
											   (("R", R), ("G", G), ("B", B)))])
					legend[0] = joiner.join([format[0] % pointXY[0], RGB])
					pointXY = pointXY[1], pointXY[0]
				else:
					joiner = u" \u2192 "
					format = "%.2f", "%.2f"
					axis_y = 255.0
					legend[0] += " " + joiner.join([format[i] % point
													for i, point in
													enumerate(pointXY)])
				if (len(legend) == 1 and pointXY[0] > 0 and
					pointXY[0] < 255 and pointXY[1] > 0):
					y = pointXY[1]
					if (self.plot_mode_select.GetSelection() == 1 and
						self.show_as_L.GetValue()):
						y = colormath.Lab2XYZ(y, 0, 0)[1] * 100
					legend.append(rgb + "Gamma %.2f" % (math.log(y / axis_y) / math.log(pointXY[0] / 255.0)))
				self.add_tone_values(legend)
				self.SetStatusText(", ".join(legend))
				# Make up dictionary to pass to DrawPointLabel
				mDataDict= {"curveNum": curveNum, "legend": legend, 
							"pIndex": pIndex, "pointXY": pointXY, 
							"scaledXY": scaledXY}
				# Pass dict to update the point label
				self.client.UpdatePointLabel(mDataDict)
	
	def update_controls(self):
		self.show_actual_lut_cb.Enable(self.worker.argyll_version >= [1, 1, 0] and 
									   not "Beta" in self.worker.argyll_version_string and
									   not config.get_display_name() in
									   ("Web", "Untethered"))
		self.show_actual_lut_cb.SetValue(bool(getcfg("lut_viewer.show_actual_lut")) and
										 not config.get_display_name() in
										 ("Web", "Untethered"))
	
	@property
	def worker(self):
		return self.client.worker


class LUTViewer(wx.App):

	def OnInit(self):
		self.frame = LUTFrame(None, -1)
		return True


def main(profile=None):
	config.initcfg()
	lang.init()
	lang.update_defaults()
	app = LUTViewer(0)
	app.frame.worker.enumerate_displays_and_ports(check_lut_access=False,
												  enumerate_ports=False)
	app.frame.update_controls()
	app.frame.Bind(wx.EVT_MOVE, app.frame.move_handler, app.frame)
	app.frame.Show(True)
	if profile:
		app.frame.drop_handler(profile)
	else:
		app.frame.load_lut(get_display_profile())
	app.MainLoop()
	config.writecfg()

if __name__ == '__main__':
    main(*sys.argv[1:2])