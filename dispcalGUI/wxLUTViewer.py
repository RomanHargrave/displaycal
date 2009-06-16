#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math
import os
import sys

if not hasattr(sys, "frozen") or not sys.frozen:
	import wxversion
	try:
		wxversion.ensureMinimal("2.8")
	except wxversion.AlreadyImportedError:
		import wx
		if wx.VERSION < (2, 8):
			raise
from wx.lib.plot import _Numeric
import wx
import wx.lib.plot as plot

from ICCProfile import ICCProfile as ICCP

class LUTCanvas(plot.PlotCanvas):
	def __init__(self, *args, **kwargs):
		plot.PlotCanvas.__init__(self, *args, **kwargs)
		self.SetBackgroundColour("#666666")
		self.SetFontSizeAxis(8)
		self.SetGridColour("#555555")
		self.setLogScale((False,False))

	def _Draw(self, graphics, xAxis = None, yAxis = None, dc = None):
		"""\
		Draw objects in graphics with specified x and y axis.
		graphics- instance of PlotGraphics with list of PolyXXX objects
		xAxis - tuple with (min, max) axis range to view
		yAxis - same as xAxis
		dc - drawing context - doesn't have to be specified.    
		If it's not, the offscreen buffer is used
		"""

		if dc == None:
			# sets new dc and clears it 
			dc = wx.BufferedDC(wx.ClientDC(self.canvas), self._Buffer)
			br = wx.Brush(self.GetBackgroundColour(), wx.SOLID)
			dc.SetBackground(br)
			dc.SetBackgroundMode(wx.SOLID)
			dc.Clear()
			try:
				dc = wx.GCDC(dc)
			except:
				pass
			
		dc.BeginDrawing()
		# dc.Clear()
		
		# set font size for every thing but title and legend
		dc.SetFont(self._getFont(self._fontSizeAxis))

		# sizes axis to axis type, create lower left and upper right corners of plot
		if xAxis == None or yAxis == None:
			# One or both axis not specified in Draw
			p1, p2 = graphics.boundingBox()     # min, max points of graphics
			if xAxis == None:
				xAxis = self._axisInterval(self._xSpec, p1[0], p2[0]) # in user units
			if yAxis == None:
				yAxis = self._axisInterval(self._ySpec, p1[1], p2[1])
			# Adjust bounding box for axis spec
			p1[0],p1[1] = xAxis[0], yAxis[0]     # lower left corner user scale (xmin,ymin)
			p2[0],p2[1] = xAxis[1], yAxis[1]     # upper right corner user scale (xmax,ymax)
		else:
			# Both axis specified in Draw
			p1= _Numeric.array([xAxis[0], yAxis[0]])    # lower left corner user scale (xmin,ymin)
			p2= _Numeric.array([xAxis[1], yAxis[1]])     # upper right corner user scale (xmax,ymax)

		self.last_draw = (graphics, _Numeric.array(xAxis), _Numeric.array(yAxis))       # saves most recient values

		# Get ticks and textExtents for axis if required
		if self._xSpec is not 'none':        
			xticks = self._xticks(xAxis[0], xAxis[1])
			xTextExtent = dc.GetTextExtent(xticks[-1][1])# w h of x axis text last number on axis
		else:
			xticks = None
			xTextExtent= (0,0) # No text for ticks
		if self._ySpec is not 'none':
			yticks = self._yticks(yAxis[0], yAxis[1])
			if self.getLogScale()[1]:
				yTextExtent = dc.GetTextExtent('-2e-2')
			else:
				yTextExtentBottom = dc.GetTextExtent(yticks[0][1])
				yTextExtentTop = dc.GetTextExtent(yticks[-1][1])
				yTextExtent= (max(yTextExtentBottom[0],yTextExtentTop[0]),
							  max(yTextExtentBottom[1],yTextExtentTop[1]))
		else:
			yticks = None
			yTextExtent= (0,0) # No text for ticks

		# TextExtents for Title and Axis Labels
		titleWH, xLabelWH, yLabelWH= self._titleLablesWH(dc, graphics)

		# TextExtents for Legend
		legendBoxWH, legendSymExt, legendTextExt = self._legendWH(dc, graphics)

		# room around graph area
		rhsW= max(xTextExtent[0], legendBoxWH[0]) # use larger of number width or legend width
		lhsW= yTextExtent[0]+ yLabelWH[1]
		bottomH= max(xTextExtent[1], yTextExtent[1]/2.)+ xLabelWH[1]
		topH= yTextExtent[1]/2. + titleWH[1]
		textSize_scale= _Numeric.array([rhsW+lhsW,bottomH+topH]) # make plot area smaller by text size
		textSize_shift= _Numeric.array([lhsW, bottomH])          # shift plot area by this amount

		# draw title if requested
		if self._titleEnabled:
			dc.SetFont(self._getFont(self._fontSizeTitle))
			titlePos= (self.plotbox_origin[0]+ lhsW + (self.plotbox_size[0]-lhsW-rhsW)/2.- titleWH[0]/2.,
					   self.plotbox_origin[1]- self.plotbox_size[1])
			dc.DrawText(graphics.getTitle(),titlePos[0],titlePos[1])

		# draw label text
		dc.SetFont(self._getFont(self._fontSizeAxis))
		xLabelPos= (self.plotbox_origin[0]+ lhsW + (self.plotbox_size[0]-lhsW-rhsW)/2.- xLabelWH[0]/2.,
				 self.plotbox_origin[1]- xLabelWH[1])
		dc.DrawText(graphics.getXLabel(),xLabelPos[0],xLabelPos[1])
		yLabelPos= (self.plotbox_origin[0],
				 self.plotbox_origin[1]- bottomH- (self.plotbox_size[1]-bottomH-topH)/2.+ yLabelWH[0]/2.)
		if graphics.getYLabel():  # bug fix for Linux
			dc.DrawRotatedText(graphics.getYLabel(),yLabelPos[0],yLabelPos[1],90)

		# drawing legend makers and text
		if self._legendEnabled:
			self._drawLegend(dc,graphics,rhsW,topH,legendBoxWH, legendSymExt, legendTextExt)

		# allow for scaling and shifting plotted points
		scale = (self.plotbox_size-textSize_scale) / (p2-p1)* _Numeric.array((1,-1))
		shift = -p1*scale + self.plotbox_origin + textSize_shift * _Numeric.array((1,-1))
		self._pointScale= scale  # make available for mouse events
		self._pointShift= shift        
		self._drawAxes(dc, p1, p2, scale, shift, xticks, yticks)
		
		graphics.scaleAndShift(scale, shift)
		graphics.setPrinterScale(self.printerScale)  # thicken up lines and markers if printing
		
		# set clipping area so drawing does not occur outside axis box
		ptx,pty,rectWidth,rectHeight= self._point2ClientCoord(p1, p2)
		dc.SetClippingRegion(ptx,pty,rectWidth,rectHeight)
		# Draw the lines and markers
		#start = _time.clock()
		graphics.draw(dc)
		# print "entire graphics drawing took: %f second"%(_time.clock() - start)
		# remove the clipping region
		dc.DestroyClippingRegion()
		dc.EndDrawing()

		self._adjustScrollbars()

	def Clear(self):
		"""Erase the window."""
		self.last_PointLabel = None        #reset pointLabel
		dc = wx.BufferedDC(wx.ClientDC(self.canvas), self._Buffer)
		br = wx.Brush(self.GetBackgroundColour(), wx.SOLID)
		dc.SetBackground(br)
		dc.SetBackgroundMode(wx.SOLID)
		dc.Clear()
		try:
			dc = wx.GCDC(dc)
		except:
			pass
		self.last_draw = None

	def DrawLUT(self, vcgt=None, title="LUT"):
		if "entryCount" in vcgt: # table
			input = range(0, vcgt.entryCount)
			gray = []
			red = []
			green = []
			blue = []
			for i in input:
				gray += [[i, i]]
				red += [[i, float(vcgt.data[0][i]) / (vcgt.entryCount + 1)]]
				green += [[i, float(vcgt.data[1][i]) / (vcgt.entryCount + 1)]]
				blue += [[i, float(vcgt.data[2][i]) / (vcgt.entryCount + 1)]]
		else: # formula
			input = range(0, 256)
			step = 100.0 / 255.0
			gray = []
			red = []
			green = []
			blue = []
			for i in input:
				gray += [[i, i]]
				red += [[float(vcgt["redMin"]) + math.pow(step * i / 100.0, 1.0 / float(vcgt["redGamma"])) * float(vcgt["redMax"]) * 256, i]]
				green += [[float(vcgt["greenMin"]) + math.pow(step * i / 100.0, 1.0 / float(vcgt["greenGamma"])) * float(vcgt["greenMax"]) * 256, i]]
				blue += [[float(vcgt["blueMin"]) + math.pow(step * i / 100.0, 1.0 / float(vcgt["blueGamma"])) * float(vcgt["blueMax"]) * 256, i]]

		gray_line = plot.PolyLine(gray, colour='#555555', width=1)
		red_line = plot.PolyLine(red, colour='red', width=1)
		green_line = plot.PolyLine(green, colour='green', width=1)
		blue_line = plot.PolyLine(blue, colour='blue', width=1)

		self.Draw(plot.PlotGraphics([gray_line, red_line, green_line, blue_line], title, "In", "Out"))

class LUTFrame(wx.Frame):
	def __init__(self, parent, id, title="LUT Viewer"):
		wx.Frame.__init__(self, parent, id, title,
						  wx.DefaultPosition, (512, 512))
		self.canvas = LUTCanvas(self)

class LUTViewer(wx.App):
	def OnInit(self):
		self.frame = LUTFrame(None, -1)
		self.frame.Show(True)
		return True

def main():

	app = LUTViewer(0)
	profile = ICCP(os.path.join("E.icc"))
	app.frame.canvas.DrawLUT(profile.tags.vcgt, title=profile.getDescription())
	app.MainLoop()

if __name__ == '__main__':
    main()