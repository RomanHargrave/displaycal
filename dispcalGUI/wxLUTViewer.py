#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math
import os
import sys

if not hasattr(sys, "frozen") or not sys.frozen:
	import wxversion
	try:
		wxversion.ensureMinimal("2.8")
	except:
		import wx
		if wx.VERSION < (2, 8):
			raise
from wx.lib.plot import _Numeric
import wx
import wx.lib.plot as plot

import ICCProfile as ICCP

ANTIALIAS = True
BGCOLOUR = "#333333"
FGCOLOUR = "#999999"
GRIDCOLOUR = "#444444"
HILITECOLOUR = "white"
SCALE = 20.0

class PolySpline(plot.PolyLine):
	"""Class to define line type and style
		- All methods except __init__ are private.
	"""

	_attributes = {'colour': 'black',
				   'width': 1,
				   'style': wx.SOLID,
				   'legend': ''}

	def __init__(self, points, **attr):
		"""Creates PolyLine object
			points - sequence (array, tuple or list) of (x,y) points making up line
			**attr - key word attributes
				Defaults:
					'colour'= 'black',          - wx.Pen Colour any wx.NamedColour
					'width'= 1,                 - Pen width
					'style'= wx.SOLID,          - wx.Pen style
					'legend'= ''                - Line Legend to display
		"""
		plot.PolyLine.__init__(self, points, **attr)

	def draw(self, dc, printerScale, coord= None):
		colour = self.attributes['colour']
		width = self.attributes['width'] * printerScale
		style= self.attributes['style']
		if not isinstance(colour, wx.Colour):
			colour = wx.NamedColour(colour)
		pen = wx.Pen(colour, width, style)
		pen.SetCap(wx.CAP_ROUND)
		dc.SetPen(pen)
		if coord == None:
			# points = []
			# scaled = []
			# for i in self.scaled:
				# point = [round(i[0]), round(i[1])]
				# if point not in points:
					# points += [point]
					# scaled += [[i[0], i[1]]]
			# dc.DrawSpline(scaled)
			dc.DrawSpline(self.scaled)
		else:
			dc.DrawLines(coord) # draw legend line

class LUTCanvas(plot.PlotCanvas):
	def __init__(self, *args, **kwargs):
		plot.PlotCanvas.__init__(self, *args, **kwargs)
		self.SetBackgroundColour(BGCOLOUR)
		self.SetEnableGrid(False)
		self.SetEnablePointLabel(False)
		self.SetForegroundColour(FGCOLOUR)
		self.SetFontSizeAxis((9 if sys.platform in ("darwin", "win32") else 12) * SCALE)
		self.SetFontSizeLegend((9 if sys.platform in ("darwin", "win32") else 12) * SCALE)
		self.SetFontSizeTitle((9 if sys.platform in ("darwin", "win32") else 12) * SCALE)
		self.SetGridColour(GRIDCOLOUR)
		self.setLogScale((False,False))
		# self.SetXSpec('none')
		# self.SetYSpec('none')

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
			bbr = wx.Brush(self.GetBackgroundColour(), wx.SOLID)
			dc.SetBackground(bbr)
			dc.SetBackgroundMode(wx.SOLID)
			dc.Clear()
			if ANTIALIAS:
				try:
					dc = wx.GCDC(dc)
				except:
					pass
			
		dc.SetTextForeground(self.GetForegroundColour())
		dc.SetTextBackground(self.GetBackgroundColour())

		dc.SetMapMode(wx.MM_TWIPS) # high precision 1/20 pt

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

		h = dc.GetCharHeight()

		# draw label text
		dc.SetFont(self._getFont(self._fontSizeAxis))
		xLabelPos= (self.plotbox_origin[0]+ lhsW + (self.plotbox_size[0]-lhsW-rhsW)/2.- xLabelWH[0]/2.,
				 self.plotbox_origin[1]- xLabelWH[1] + 0.125 * h)
		dc.DrawText(graphics.getXLabel(),xLabelPos[0],xLabelPos[1])
		yLabelPos= (self.plotbox_origin[0] - 0.125 * h,
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
		#ptx,pty,rectWidth,rectHeight= self._point2ClientCoord(p1, p2)
		#dc.SetClippingRegion(ptx,pty,rectWidth,rectHeight)
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
		bbr = wx.Brush(self.GetBackgroundColour(), wx.SOLID)
		dc.SetBackground(bbr)
		dc.SetBackgroundMode(wx.SOLID)
		dc.Clear()
		if ANTIALIAS:
			try:
				dc = wx.GCDC(dc)
			except:
				pass
		dc.SetTextForeground(self.GetForegroundColour())
		dc.SetTextBackground(self.GetBackgroundColour())
		self.last_draw = None

	def OnPaint(self, event):
		# All that is needed here is to draw the buffer to screen
		if self.last_PointLabel != None:
			self._drawPointLabel(self.last_PointLabel) #erase old
			self.last_PointLabel = None
		dc = wx.BufferedPaintDC(self.canvas, self._Buffer)
		if ANTIALIAS:
			try:
				dc = wx.GCDC(dc)
			except:
				pass

	def _setSize(self, width=None, height=None):
		"""DC width and height."""
		if width == None:
			(self.width,self.height) = self.canvas.GetClientSize()
		else:
			self.width, self.height= width, height
		self.width *= 20 # high precision
		self.height *= 20 # high precision
		self.plotbox_size = 0.97*_Numeric.array([self.width, self.height])
		xo = 0.5*(self.width-self.plotbox_size[0])
		yo = self.height-0.5*(self.height-self.plotbox_size[1])
		self.plotbox_origin = _Numeric.array([xo, yo])

	def _drawAxes(self, dc, p1, p2, scale, shift, xticks, yticks):
		
		penWidth= self.printerScale        # increases thickness for printing only
		dc.SetPen(wx.Pen(self._gridColour, penWidth))
		
		# set length of tick marks--long ones make grid
		if self._gridEnabled:
			x,y,width,height= self._point2ClientCoord(p1,p2)
			if self._gridEnabled == 'Horizontal':
				yTickLength= width/2.0 +1
				xTickLength= 3 * self.printerScale
			elif self._gridEnabled == 'Vertical':
				yTickLength= 3 * self.printerScale
				xTickLength= height/2.0 +1
			else:
				yTickLength= width/2.0 +1
				xTickLength= height/2.0 +1
		else:
			yTickLength= 3 * SCALE * self.printerScale  # lengthens lines for printing
			xTickLength= 3 * SCALE * self.printerScale

		h = dc.GetCharHeight()

		if self._xSpec is not 'none':
			lower, upper = p1[0],p2[0]
			text = 1
			for y, d in [(p1[1], -xTickLength), (p2[1], xTickLength)]:   # miny, maxy and tick lengths
				for x, label in xticks:
					pt = scale*_Numeric.array([x, y])+shift
					dc.DrawLine(pt[0],pt[1],pt[0],pt[1] + d) # draws tick mark d units
					if text:
						dc.DrawText(label,pt[0],pt[1]+0.125*h)
				a1 = scale*_Numeric.array([lower, y])+shift
				a2 = scale*_Numeric.array([upper, y])+shift
				dc.DrawLine(a1[0],a1[1],a2[0],a2[1])  # draws upper and lower axis line
				text = 0  # axis values not drawn on top side

		if self._ySpec is not 'none':
			lower, upper = p1[1],p2[1]
			text = 1
			for x, d in [(p1[0], -yTickLength), (p2[0], yTickLength)]:
				for y, label in yticks:
					pt = scale*_Numeric.array([x, y])+shift
					dc.DrawLine(pt[0],pt[1],pt[0]-d,pt[1])
					if text:
						dc.DrawText(label,pt[0]-dc.GetTextExtent(label)[0]-0.125*h,
									pt[1]-0.75*h)
				a1 = scale*_Numeric.array([x, lower])+shift
				a2 = scale*_Numeric.array([x, upper])+shift
				dc.DrawLine(a1[0],a1[1],a2[0],a2[1])
				text = 0    # axis values not drawn on right side

	def _ticks(self, lower, upper):
		ideal = (upper-lower)/5.
		log = _Numeric.log10(ideal)
		power = _Numeric.floor(log)
		fraction = log-power
		factor = 1.
		error = fraction
		for f, lf in self._multiples:
			e = _Numeric.fabs(fraction-lf)
			if e < error:
				error = e
				factor = f
		# grid = factor * 10.**power
		grid = ideal
		if self._useScientificNotation and (power > 4 or power < -4):
			format = '%+7.1e'        
		elif power >= 0:
			digits = max(1, int(power))
			format = '%' + `digits`+'.0f'
		else:
			digits = -int(power)
			format = '%'+`digits+2`+'.'+`digits`+'f'
		ticks = []
		t = -grid*_Numeric.floor(-lower/grid)
		while t <= upper:
			ticks.append( (t, format % (t,)) )
			if t + grid <= upper:
				t = t + grid
			else:
				break
		if t < upper:
			ticks.append( (upper, format % (upper,)) )
		return ticks

	def DrawLUT(self, vcgt=None, title=None, xLabel=None, yLabel=None, r=True, g=True, b=True):
		if not title:
			title = "LUT"
		if not xLabel:
			xLabel = "In"
		if not yLabel:
			yLabel="Out"
		
		detect_increments = True
		Plot = plot.PolyLine

		lines = []
		linear_points = []

		if not vcgt:
			input = range(0, 256)
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
					if not detect_increments or not r_points or i == vcgt.entryCount - 1 or n != i:
						if detect_increments and n != i and len(r_points) == 1 and i > 1 and r_points[-1][0] == r_points[-1][1]:
							# print "R", i - 1, "=>", i - 1
							r_points += [[i - 1, i - 1]]
						r_points += [[i, n]]
				if g:
					n = float(vcgt.data[1][i]) / (vcgt.entryCount + 1)
					if not detect_increments or not g_points or i == vcgt.entryCount - 1 or n != i:
						if detect_increments and n != i and len(g_points) == 1 and i > 1 and g_points[-1][0] == g_points[-1][1]:
							# print "G", i - 1, "=>", i - 1
							g_points += [[i - 1, i - 1]]
						g_points += [[i, n]]
				if b:
					n = float(vcgt.data[2][i]) / (vcgt.entryCount + 1)
					if not detect_increments or not b_points or i == vcgt.entryCount - 1 or n != i:
						if detect_increments and n != i and len(b_points) == 1 and i > 1 and b_points[-1][0] == b_points[-1][1]:
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
					r_points += [[float(vcgt["redMin"]) + math.pow(step * i / 100.0, 1.0 / float(vcgt["redGamma"])) * float(vcgt["redMax"]) * 255, i]]
				if g:
					g_points += [[float(vcgt["greenMin"]) + math.pow(step * i / 100.0, 1.0 / float(vcgt["greenGamma"])) * float(vcgt["greenMax"]) * 255, i]]
				if b:
					b_points += [[float(vcgt["blueMin"]) + math.pow(step * i / 100.0, 1.0 / float(vcgt["blueGamma"])) * float(vcgt["blueMax"]) * 255, i]]

		# print r_points
		# print g_points
		# print b_points

		linear = [[0, 0], [input[-1], input[-1]]]
		
		if not vcgt:
			r_points = g_points = b_points = linear

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

		lines += [Plot([[input[-1] / 2.0, 0], [input[-1] / 2.0, input[-1]]], colour=GRIDCOLOUR)] # bottom center to top center
		lines += [Plot([[0, input[-1] / 2.0], [input[-1], input[-1] / 2.0]], colour=GRIDCOLOUR)] # center left to center right
		# lines += [Plot([[0, input[-1]], [input[-1], input[-1]]], colour=GRIDCOLOUR)] # top
		# lines += [Plot([[input[-1], 0], [input[-1], input[-1]]], colour=GRIDCOLOUR)] # right
		# lines += [Plot([[0, 0], [input[-1], 1]], colour=GRIDCOLOUR)] # bottom
		# lines += [Plot([[0, 0], [0, input[-1]]], colour=GRIDCOLOUR)] # left

		lines += [Plot(linear, colour=GRIDCOLOUR)] # bottom left to top right

		if r and g and b and r_points == g_points == b_points == (linear if detect_increments else linear_points):
			lines += [Plot(linear if detect_increments else linear_points, colour=HILITECOLOUR)] # bottom left to top right
		else:
			if r:
				# print r_points[0], r_points[-1]
				lines += [Plot(r_points, legend='R', colour='red')]
			if g:
				# print g_points[0], g_points[-1]
				lines += [Plot(g_points, legend='G', colour='green')]
			if b:
				# print b_points[0], b_points[-1]
				lines += [Plot(b_points, legend='B', colour='#0080FF')]

		self.Draw(plot.PlotGraphics(lines, title, xLabel, yLabel)) #, xAxis=(0, input[-1]), yAxis=(0, input[-1]))

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
		self.sizer.Add(self.box_panel, flag = wx.EXPAND)
		
		self.box_sizer = wx.GridSizer(-1, 3)
		self.box_panel.SetSizer(self.box_sizer)
		
		self.box_sizer.Add((0, 0))
		
		self.cbox_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.box_sizer.Add(self.cbox_sizer, flag = wx.ALL | wx.ALIGN_CENTER, border = 8)
		
		self.cbox_sizer.Add((20, 0))
		
		self.toggle_red = wx.CheckBox(self.box_panel, -1, "R")
		self.toggle_red.SetForegroundColour(FGCOLOUR)
		self.toggle_red.SetValue(True)
		self.cbox_sizer.Add(self.toggle_red)
		self.Bind(wx.EVT_CHECKBOX, self.DrawLUT, id = self.toggle_red.GetId())
		
		self.cbox_sizer.Add((4, 0))
		
		self.toggle_green = wx.CheckBox(self.box_panel, -1, "G")
		self.toggle_green.SetForegroundColour(FGCOLOUR)
		self.toggle_green.SetValue(True)
		self.cbox_sizer.Add(self.toggle_green)
		self.Bind(wx.EVT_CHECKBOX, self.DrawLUT, id = self.toggle_green.GetId())
		
		self.cbox_sizer.Add((4, 0))
		
		self.toggle_blue = wx.CheckBox(self.box_panel, -1, "B")
		self.toggle_blue.SetForegroundColour(FGCOLOUR)
		self.toggle_blue.SetValue(True)
		self.cbox_sizer.Add(self.toggle_blue)
		self.Bind(wx.EVT_CHECKBOX, self.DrawLUT, id = self.toggle_blue.GetId())

		self.client.SetPointLabelFunc(self.DrawPointLabel)
		self.client.canvas.Bind(wx.EVT_MOTION, self.OnMotion)

	def LoadProfile(self, profile):
		self.profile = profile
	
	def DrawLUT(self, event=None):
		self.client.DrawLUT(self.profile.tags.vcgt if self.profile else None, 
							title=self.profile.getDescription() if self.profile else None, 
							xLabel=self.xLabel,
							yLabel=self.yLabel,
							r=self.toggle_red.GetValue() if hasattr(self, "toggle_red") else False, 
							g=self.toggle_green.GetValue() if hasattr(self, "toggle_green") else False, 
							b=self.toggle_blue.GetValue() if hasattr(self, "toggle_blue") else False)

	def DrawPointLabel(self, dc, mDataDict):
		"""This is the fuction that defines how the pointLabels are plotted
			dc - DC that will be passed
			mDataDict - Dictionary of data that you want to use for the pointLabel

			As an example I have decided I want a box at the curve point
			with some text information about the curve plotted below.
			Any wxDC method can be used.
		"""
		# ----------
		dc.SetPen(wx.Pen(wx.BLACK))
		dc.SetBrush(wx.Brush( wx.BLACK, wx.SOLID ) )
		
		sx, sy = mDataDict["scaledXY"] #scaled x,y of closest point
		dc.DrawRectangle( sx-5,sy-5, 10, 10)  #10by10 square centered on point
		px,py = mDataDict["pointXY"]
		cNum = mDataDict["curveNum"]
		pntIn = mDataDict["pIndex"]
		legend = mDataDict["legend"]
		#make a string to display
		s = "Crv# %i, '%s', Pt. (%.2f,%.2f), PtInd %i" %(cNum, legend, px, py, pntIn)
		dc.DrawText(s, sx , sy+1)
		# -----------

	def OnMotion(self, event):
		self.SetStatusText("%d, %d" % tuple([round(xy) for xy in self.client._getXY(event)]))
		#show closest point (when enbled)
		if self.client.GetEnablePointLabel() == True:
			#make up dict with info for the pointLabel
			#I've decided to mark the closest point on the closest curve
			dlst= self.client.GetClosestPoint( self.client._getXY(event), pointScaled= True)
			if dlst != []:    #returns [] if none
				curveNum, legend, pIndex, pointXY, scaledXY, distance = dlst
				#make up dictionary to pass to my user function (see DrawPointLabel) 
				mDataDict= {"curveNum":curveNum, "legend":legend, "pIndex":pIndex,\
							"pointXY":pointXY, "scaledXY":scaledXY}
				#pass dict to update the pointLabel
				self.client.UpdatePointLabel(mDataDict)
		event.Skip()           #go to next handler

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