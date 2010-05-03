#!/usr/bin/env python
# -*- coding: utf-8 -*-

from decimal import Decimal
import math
import os
import sys

from util_decimal import float2dec
from wxaddons import wx
from wxenhancedplot import _Numeric
import wxenhancedplot as plot
import localization as lang
import ICCProfile as ICCP

BGCOLOUR = "#333333"
FGCOLOUR = "#999999"
GRIDCOLOUR = "#444444"
HILITECOLOUR = "white"

class LUTCanvas(plot.PlotCanvas):

	def __init__(self, *args, **kwargs):
		plot.PlotCanvas.__init__(self, *args, **kwargs)
		self.canvas.Bind(wx.EVT_LEAVE_WINDOW, None)
		self.SetBackgroundColour(BGCOLOUR)
		self.SetEnableAntiAliasing(True)
		self.SetEnableHiRes(True)
		self.SetEnableCenterLines(True)
		self.SetEnableDiagonals('Bottomleft-Topright')
		self.SetEnableGrid(False)
		self.SetEnablePointLabel(True)
		self.SetForegroundColour(FGCOLOUR)
		self.SetFontSizeAxis(9)
		self.SetFontSizeLegend(9)
		self.SetFontSizeTitle(9)
		self.SetGridColour(GRIDCOLOUR)
		self.setLogScale((False,False))
		self.SetXSpec(5)
		self.SetYSpec(5)

	def DrawLUT(self, vcgt=None, title=None, xLabel=None, yLabel=None, 
				r=True, g=True, b=True):
		if not title:
			title = "LUT"
		if not xLabel:
			xLabel = "In"
		if not yLabel:
			yLabel="Out"
		
		detect_increments = False
		Plot = plot.PolySpline

		lines = []
		linear_points = []

		if not vcgt:
			irange = range(0, 256)
			# for i in irange:
				# if not detect_increments:
					# linear_points += [[i, i]]
		elif "data" in vcgt: # table
			irange = range(0, vcgt['entryCount'])
			r_points = []
			g_points = []
			b_points = []
			for i in irange:
				j = i * (255.0 / (vcgt['entryCount'] - 1))
				if not detect_increments:
					linear_points += [[j, j]]
				if r:
					n = float(vcgt['data'][0][i]) / (math.pow(256, vcgt['entrySize']) - 1) * 255
					if not detect_increments or not r_points or \
					   i == vcgt['entryCount'] - 1 or n != i:
						if detect_increments and n != i and \
						   len(r_points) == 1 and i > 1 and \
						   r_points[-1][0] == r_points[-1][1]:
							r_points += [[i - 1, i - 1]]
						r_points += [[j, n]]
				if g:
					n = float(vcgt['data'][1][i]) / (math.pow(256, vcgt['entrySize']) - 1) * 255
					if not detect_increments or not g_points or \
					   i == vcgt['entryCount'] - 1 or n != i:
						if detect_increments and n != i and \
						   len(g_points) == 1 and i > 1 and \
						   g_points[-1][0] == g_points[-1][1]:
							g_points += [[i - 1, i - 1]]
						g_points += [[j, n]]
				if b:
					n = float(vcgt['data'][2][i]) / (math.pow(256, vcgt['entrySize']) - 1) * 255
					if not detect_increments or not b_points or \
					   i == vcgt['entryCount'] - 1 or n != i:
						if detect_increments and n != i and \
						   len(b_points) == 1 and i > 1 and \
						   b_points[-1][0] == b_points[-1][1]:
							b_points += [[i - 1, i - 1]]
						b_points += [[j, n]]
		else: # formula
			irange = range(0, 256)
			step = 100.0 / 255.0
			r_points = []
			g_points = []
			b_points = []
			for i in irange:
				# float2dec(v) fixes miniscule deviations in the calculated gamma
				if not detect_increments:
					linear_points += [[i, (i)]]
				if r:
					vmin = float2dec(vcgt["redMin"] * 255)
					v = float2dec(math.pow(step * i / 100.0, vcgt["redGamma"]))
					vmax = float2dec(vcgt["redMax"] * 255)
					r_points += [[i, float2dec(vmin + v * (vmax - vmin), 8)]]
				if g:
					vmin = float2dec(vcgt["greenMin"] * 255)
					v = float2dec(math.pow(step * i / 100.0, vcgt["greenGamma"]))
					vmax = float2dec(vcgt["greenMax"] * 255)
					g_points += [[i, float2dec(vmin + v * (vmax - vmin), 8)]]
				if b:
					vmin = float2dec(vcgt["blueMin"] * 255)
					v = float2dec(math.pow(step * i / 100.0, vcgt["blueGamma"]))
					vmax = float2dec(vcgt["blueMax"] * 255)
					b_points += [[i, float2dec(vmin + v * (vmax - vmin), 8)]]

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
		points = []
		if r:
			legend += ['R']
			points += [r_points]
		if g:
			legend += ['G']
			points += [g_points]
		if b:
			legend += ['B']
			points += [b_points]
		same = True
		if points:
			for i in range(1, len(points)):
				if points[i] != points[0]:
					same = False
					break
		suffix = ((', ' + lang.getstr('linear').capitalize()) if points and 
					points[0] == (linear if detect_increments else 
								  linear_points) else '')
		if len(legend) > 1 and same:
			if legend == ['R', 'G']:
				colour = 'yellow'
			elif legend == ['R', 'B']:
				colour = 'magenta'
			elif legend == ['G', 'B']:
				colour = 'cyan'
			else:
				colour = 'white'
			# Bottom left to top right
			lines += [Plot(points[0], legend='='.join(legend) + suffix, 
						   colour=colour)]
		else:
			if r:
				lines += [Plot(r_points, legend='R' + suffix, colour='red')]
			if g:
				suffix = ((', ' + lang.getstr('linear').capitalize()) if 
							g_points == (linear if detect_increments else 
										  linear_points) else '')
				lines += [Plot(g_points, legend='G' + suffix, colour='green')]
			if b:
				suffix = ((', ' + lang.getstr('linear').capitalize()) if 
							b_points == (linear if detect_increments else 
										  linear_points) else '')
				lines += [Plot(b_points, legend='B' + suffix, colour='#0080FF')]

		if not lines:
			lines += [Plot([])]

		self.Draw(plot.PlotGraphics(lines, title, xLabel, yLabel), 
				  xAxis=(0, 255), yAxis=(0, 255))


class LUTFrame(wx.Frame):

	def __init__(self, *args, **kwargs):
	
		if len(args) < 3 and not "title" in kwargs:
			kwargs["title"] = "LUT Viewer"
		if len(args) < 5 and not "size" in kwargs:
			kwargs["size"] = (512, 580)
		
		wx.Frame.__init__(self, *args, **kwargs)
		
		self.CreateStatusBar(1)
		
		self.profile = None
		self.xLabel = None
		self.yLabel = None
		
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		self.SetSizer(self.sizer)
		
		self.client = LUTCanvas(self)
		self.sizer.Add(self.client, 1, wx.EXPAND)
		
		self.box_panel = wx.Panel(self)
		self.box_panel.SetBackgroundColour(BGCOLOUR)
		self.sizer.Add(self.box_panel, flag=wx.EXPAND)
		
		self.box_sizer = wx.GridSizer(-1, 3)
		self.box_panel.SetSizer(self.box_sizer)
		
		self.box_sizer.Add((0, 0))
		
		self.cbox_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.box_sizer.Add(self.cbox_sizer, 
						   flag=wx.ALL | wx.ALIGN_CENTER | wx.ALIGN_CENTER_VERTICAL, 
						   border=8)
		
		self.curve_select = wx.Choice(self.box_panel, -1, size=(-1, -1), 
									  choices=[])
		self.cbox_sizer.Add(self.curve_select, flag=wx.ALIGN_CENTER_VERTICAL)
		self.Bind(wx.EVT_CHOICE, self.DrawLUT, id=self.curve_select.GetId())
		
		self.cbox_sizer.Add((20, 0))
		
		self.toggle_red = wx.CheckBox(self.box_panel, -1, "R")
		self.toggle_red.SetForegroundColour(FGCOLOUR)
		self.toggle_red.SetValue(True)
		self.cbox_sizer.Add(self.toggle_red, flag=wx.ALIGN_CENTER_VERTICAL)
		self.Bind(wx.EVT_CHECKBOX, self.DrawLUT, id=self.toggle_red.GetId())
		
		self.cbox_sizer.Add((4, 0))
		
		self.toggle_green = wx.CheckBox(self.box_panel, -1, "G")
		self.toggle_green.SetForegroundColour(FGCOLOUR)
		self.toggle_green.SetValue(True)
		self.cbox_sizer.Add(self.toggle_green, flag=wx.ALIGN_CENTER_VERTICAL)
		self.Bind(wx.EVT_CHECKBOX, self.DrawLUT, id=self.toggle_green.GetId())
		
		self.cbox_sizer.Add((4, 0))
		
		self.toggle_blue = wx.CheckBox(self.box_panel, -1, "B")
		self.toggle_blue.SetForegroundColour(FGCOLOUR)
		self.toggle_blue.SetValue(True)
		self.cbox_sizer.Add(self.toggle_blue, flag=wx.ALIGN_CENTER_VERTICAL)
		self.Bind(wx.EVT_CHECKBOX, self.DrawLUT, id=self.toggle_blue.GetId())

		self.client.SetPointLabelFunc(self.DrawPointLabel)
		self.client.canvas.Bind(wx.EVT_MOTION, self.OnMotion)

	def LoadProfile(self, profile):
		if not profile:
			profile = ICCP.ICCProfile()
			profile._tags = ICCP.ADict()
			profile._tags.desc = ""
			profile._tags.vcgt = ICCP.ADict({
				"channels": 3,
				"entryCount": 256,
				"entrySize": 1,
				"data": [range(0, 256), range(0, 256), range(0, 256)]
			})
		self.profile = profile
		curves = []
		curves.append(lang.getstr('vcgt'))
		if 'rTRC' in profile.tags and isinstance(profile.tags.rTRC, 
												 ICCP.CurveType) and \
		   'gTRC' in profile.tags and isinstance(profile.tags.gTRC, 
												 ICCP.CurveType) and \
		   'bTRC' in profile.tags and isinstance(profile.tags.bTRC, 
												 ICCP.CurveType):
			curves.append(lang.getstr('[rgb]TRC'))
		selection = self.curve_select.GetSelection()
		if curves and (selection < 0 or selection > len(curves) - 1):
			selection = 0
		self.curve_select.SetItems(curves)
		self.curve_select.Enable(len(curves) > 1)
		self.curve_select.SetSelection(selection)

	def add_tone_values(self, legend):
		if self.profile and self.curve_select.GetSelection() == 0 and \
		   'vcgt' in self.profile.tags:
			colorants = legend[0]
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
					legend[-1] += " %.1f%% (%i/%i)" % (unique / 
													   (self.client.entryCount / 
														100.0), unique, 
													   self.client.entryCount)
				else:
					if 'R' in colorants:
						legend[-1] += " %.1f%% (%i/%i)" % (self.client.r_unique / 
														   (self.client.entryCount / 
															100.0), 
														   self.client.r_unique, 
														   self.client.entryCount)
					if 'G' in colorants:
						legend[-1] += " %.1f%% (%i/%i)" % (self.client.g_unique / 
														   (self.client.entryCount / 
															100.0), 
														   self.client.g_unique, 
														   self.client.entryCount)
					if 'B' in colorants:
						legend[-1] += " %.1f%% (%i/%i)" % (self.client.b_unique / 
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
					legend[-1] += ", %s %.1f%% (%i/%i)" % (lang.getstr("grayscale"), 
														   unique / 
														   (self.client.entryCount / 
															100.0), unique, 
														   self.client.entryCount)

	def DrawLUT(self, event=None):
		self.SetStatusText('')
		curves = None
		if self.profile:
			if self.curve_select.GetSelection() == 0:
				if 'vcgt' in self.profile.tags:
					curves = self.profile.tags['vcgt']
				else:
					curves = None
			elif self.curve_select.GetSelection() == 1:
				if len(self.profile.tags['rTRC']) == 1 and \
				   len(self.profile.tags['gTRC']) == 1 and \
				   len(self.profile.tags['bTRC']) == 1:
					# gamma
					curves = {
						'redMin': 0.0,
						'redGamma': self.profile.tags['rTRC'][0],
						'redMax': 1.0,
						'greenMin': 0.0,
						'greenGamma': self.profile.tags['gTRC'][0],
						'greenMax': 1.0,
						'blueMin': 0.0,
						'blueGamma': self.profile.tags['bTRC'][0],
						'blueMax': 1.0
					}
				else:
					# curves
					curves = {
						'data': [self.profile.tags['rTRC'],
								 self.profile.tags['gTRC'],
								 self.profile.tags['bTRC']],
						'entryCount': len(self.profile.tags['rTRC']),
						'entrySize': 2
					}
		self.toggle_red.Enable(bool(curves))
		self.toggle_green.Enable(bool(curves))
		self.toggle_blue.Enable(bool(curves))
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
		wx.CallLater(125, self.OnMotion, pointXY)

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
		##px,py = mDataDict["pointXY"]
		##cNum = mDataDict["curveNum"]
		##pntIn = mDataDict["pIndex"]
		##legend = mDataDict["legend"]

	def OnMotion(self, event):
		if isinstance(event, wx.MouseEvent):
			xy = self.client._getXY(event)
		else:
			xy = event
		if self.client.GetEnablePointLabel():
			# Show closest point (when enbled)
			# Make up dict with info for the point label
			dlst = self.client.GetClosestPoint(xy, pointScaled=True)
			if dlst != []:
				curveNum, legend, pIndex, pointXY, scaledXY, distance = dlst
				legend = legend.split(", ")
				if self.profile and self.curve_select.GetSelection() == 0 and \
				   'vcgt' in self.profile.tags:
					pointXY = [int(round(point)) for point in pointXY]
				legend[0] += " " + u" \u2192 ".join([str(point) for point in pointXY])
				self.add_tone_values(legend)
				self.SetStatusText(", ".join(legend))
				# Make up dictionary to pass to DrawPointLabel
				mDataDict= {"curveNum": curveNum, "legend": legend, 
							"pIndex": pIndex, "pointXY": pointXY, 
							"scaledXY": scaledXY}
				# Pass dict to update the point label
				self.client.UpdatePointLabel(mDataDict)
		if isinstance(event, wx.MouseEvent):
			event.Skip() # Go to next handler

class LUTViewer(wx.App):

	def OnInit(self):
		self.frame = LUTFrame(None, -1)
		self.frame.Show(True)
		return True


def main():

	app = LUTViewer(0)
	profile = ICCP.get_display_profile()
	app.frame.LoadProfile(profile)
	app.frame.DrawLUT()
	app.MainLoop()

if __name__ == '__main__':
    main()