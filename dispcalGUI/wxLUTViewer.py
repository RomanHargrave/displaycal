#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math
import os
import sys

from wxenhancedplot import _Numeric
import wx
import wxenhancedplot as plot

import ICCProfile as ICCP

BGCOLOUR = "#333333"
FGCOLOUR = "#999999"
GRIDCOLOUR = "#444444"
HILITECOLOUR = "white"

class LUTCanvas(plot.PlotCanvas):

	def __init__(self, *args, **kwargs):
		plot.PlotCanvas.__init__(self, *args, **kwargs)
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
			input = range(0, 256)
			for i in input:
				if not detect_increments:
					linear_points += [[i, i]]
		elif "entryCount" in vcgt: # table
			input = range(0, vcgt.entryCount)
			r_points = []
			g_points = []
			b_points = []
			for i in input:
				if not detect_increments:
					linear_points += [[i, i]]
				if r:
					n = float(vcgt.data[0][i]) / (vcgt.entryCount + 1)
					if not detect_increments or not r_points or \
					   i == vcgt.entryCount - 1 or n != i:
						if detect_increments and n != i and \
						   len(r_points) == 1 and i > 1 and \
						   r_points[-1][0] == r_points[-1][1]:
							# print "R", i - 1, "=>", i - 1
							r_points += [[i - 1, i - 1]]
						r_points += [[i, n]]
				if g:
					n = float(vcgt.data[1][i]) / (vcgt.entryCount + 1)
					if not detect_increments or not g_points or \
					   i == vcgt.entryCount - 1 or n != i:
						if detect_increments and n != i and \
						   len(g_points) == 1 and i > 1 and \
						   g_points[-1][0] == g_points[-1][1]:
							# print "G", i - 1, "=>", i - 1
							g_points += [[i - 1, i - 1]]
						g_points += [[i, n]]
				if b:
					n = float(vcgt.data[2][i]) / (vcgt.entryCount + 1)
					if not detect_increments or not b_points or \
					   i == vcgt.entryCount - 1 or n != i:
						if detect_increments and n != i and \
						   len(b_points) == 1 and i > 1 and \
						   b_points[-1][0] == b_points[-1][1]:
							# print "B", i - 1, "=>", i - 1
							b_points += [[i - 1, i - 1]]
						b_points += [[i, n]]
		else: # formula
			input = range(0, 256)
			step = 100.0 / 255.0
			r_points = []
			g_points = []
			b_points = []
			for i in input:
				if not detect_increments:
					linear_points += [[i, i]]
				if r:
					r_points += [[float(vcgt["redMin"]) + math.pow(step * i / 
						100.0, 1.0 / float(vcgt["redGamma"])) * 
						float(vcgt["redMax"]) * 255, i]]
				if g:
					g_points += [[float(vcgt["greenMin"]) + math.pow(step * i / 
						100.0, 1.0 / float(vcgt["greenGamma"])) * 
						float(vcgt["greenMax"]) * 255, i]]
				if b:
					b_points += [[float(vcgt["blueMin"]) + math.pow(step * i / 
					100.0, 1.0 / float(vcgt["blueGamma"])) * 
					float(vcgt["blueMax"]) * 255, i]]

		# print r_points
		# print g_points
		# print b_points

		linear = [[0, 0], [input[-1], input[-1]]]
		
		if not vcgt:
			if detect_increments:
				r_points = g_points = b_points = linear
			else:
				r_points = g_points = b_points = linear_points

		# # scale
		# for i in range(len(input)):
			# input[i] *= (len(input) + 1)
		# for i in range(len(r_points)):
			# if r:
				# for j in range(len(r_points[i])):
					# r_points[i][j] *= (len(input) + 1)
		# for i in range(len(g_points)):
			# if g:
				# for j in range(len(g_points[i])):
					# g_points[i][j] *= (len(input) + 1)
		# for i in range(len(b_points)):
			# if b:
				# for j in range(len(b_points[i])):
					# b_points[i][j] *= (len(input) + 1)

		# lines += [Plot([[input[-1] / 2.0, 0], [input[-1] / 2.0, input[-1]]], 
		# 				 colour=GRIDCOLOUR)]  # bottom center to top center
		# lines += [Plot([[0, input[-1] / 2.0], [input[-1], input[-1] / 2.0]], 
		# 				 colour=GRIDCOLOUR)]  # center left to center right
		# lines += [Plot([[0, input[-1]], [input[-1], input[-1]]], 
		# 				 colour=GRIDCOLOUR)]  # top
		# lines += [Plot([[input[-1], 0], [input[-1], input[-1]]], 
		# 				 colour=GRIDCOLOUR)]  # right
		# lines += [Plot([[0, 0], [input[-1], 1]], colour=GRIDCOLOUR)]  # bottom
		# lines += [Plot([[0, 0], [0, input[-1]]], colour=GRIDCOLOUR)]  # left

		# lines += [Plot(linear, colour=GRIDCOLOUR)]  # bottom left to top right

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
		prefix = ('LIN ' if points and 
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
			lines += [Plot(points[0], legend=prefix + '='.join(legend), 
						   colour=colour)]
		else:
			if r:
				# print r_points[0], r_points[-1]
				lines += [Plot(r_points, legend=prefix + 'R', colour='red')]
			if g:
				# print g_points[0], g_points[-1]
				lines += [Plot(g_points, legend=prefix + 'G', colour='green')]
			if b:
				# print b_points[0], b_points[-1]
				lines += [Plot(b_points, legend=prefix + 'B', colour='#0080FF')]

		if not lines:
			lines += [Plot([])]

		self.Draw(plot.PlotGraphics(lines, title, xLabel, yLabel), 
				  xAxis=(0, input[-1]), yAxis=(0, input[-1]))


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
						   flag=wx.ALL | wx.ALIGN_CENTER, border=8)
		
		self.cbox_sizer.Add((20, 0))
		
		self.toggle_red = wx.CheckBox(self.box_panel, -1, "R")
		self.toggle_red.SetForegroundColour(FGCOLOUR)
		self.toggle_red.SetValue(True)
		self.cbox_sizer.Add(self.toggle_red)
		self.Bind(wx.EVT_CHECKBOX, self.DrawLUT, id=self.toggle_red.GetId())
		
		self.cbox_sizer.Add((4, 0))
		
		self.toggle_green = wx.CheckBox(self.box_panel, -1, "G")
		self.toggle_green.SetForegroundColour(FGCOLOUR)
		self.toggle_green.SetValue(True)
		self.cbox_sizer.Add(self.toggle_green)
		self.Bind(wx.EVT_CHECKBOX, self.DrawLUT, id=self.toggle_green.GetId())
		
		self.cbox_sizer.Add((4, 0))
		
		self.toggle_blue = wx.CheckBox(self.box_panel, -1, "B")
		self.toggle_blue.SetForegroundColour(FGCOLOUR)
		self.toggle_blue.SetValue(True)
		self.cbox_sizer.Add(self.toggle_blue)
		self.Bind(wx.EVT_CHECKBOX, self.DrawLUT, id=self.toggle_blue.GetId())

		self.client.SetPointLabelFunc(self.DrawPointLabel)
		self.client.canvas.Bind(wx.EVT_MOTION, self.OnMotion)

	def LoadProfile(self, profile):
		self.profile = profile
	
	def DrawLUT(self, event=None):
		self.SetStatusText('')
		self.client.DrawLUT(self.profile.tags.vcgt if self.profile and 
							"vcgt" in self.profile.tags else None, 
							title=self.profile.getDescription() if 
								  self.profile else None, 
							xLabel=self.xLabel,
							yLabel=self.yLabel,
							r=self.toggle_red.GetValue() if 
							  hasattr(self, "toggle_red") else False, 
							g=self.toggle_green.GetValue() if 
							  hasattr(self, "toggle_green") else False, 
							b=self.toggle_blue.GetValue() if 
							  hasattr(self, "toggle_blue") else False)

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
		px,py = mDataDict["pointXY"]
		cNum = mDataDict["curveNum"]
		pntIn = mDataDict["pIndex"]
		legend = mDataDict["legend"]

	def OnMotion(self, event):
		if self.client.GetEnablePointLabel():
			# Show closest point (when enbled)
			# Make up dict with info for the point label
			dlst = self.client.GetClosestPoint(self.client._getXY(event), 
											   pointScaled= True)
			if dlst != []:
				curveNum, legend, pIndex, pointXY, scaledXY, distance = dlst
				self.SetStatusText(legend + " " + 
								   u" \u2192 ".join([str(point) for point in 
													 pointXY]))
				# Make up dictionary to pass to DrawPointLabel
				mDataDict= {"curveNum": curveNum, "legend": legend, 
							"pIndex": pIndex, "pointXY": pointXY, 
							"scaledXY": scaledXY}
				# Pass dict to update the point label
				self.client.UpdatePointLabel(mDataDict)
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