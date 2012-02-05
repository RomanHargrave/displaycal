#!/usr/bin/env python
# -*- coding: UTF-8 -*-


r"""
Interactive display calibration UI.



dispcal examples:



dispcal -v -yl test


1) Black level (CRT: Offset/Brightness)
...
Doing some initial measurements
Black = XYZ   0.20   0.21   0.35
Grey  = XYZ  27.49  29.06  28.11
White = XYZ 127.55 133.49 128.09

Adjust CRT brightness to get target level. Press space when done.
   Target 1.33
/ Current 2.12  -


2) White point (Color temperature, R,G,B, Gain/Contrast)
...
Doing some initial measurements
Red   = XYZ  83.72  42.53   2.14
Green = XYZ  23.64  81.74  14.92
Blue  = XYZ  20.59   9.72 111.50
White = XYZ 127.46 133.48 127.69

Adjust R,G & B gain to desired white point. Press space when done.
  Initial Br 133.48, x 0.3280 , y 0.3435 , VDT 5698K DE 2K  0.0
/ Current Br 133.56, x 0.3279-, y 0.3434+  VDT 5703K DE 2K  0.0  R=  G=  B=


3) White level (CRT: Gain/Contrast, LCD: Brightness/Backlight)
...
Doing some initial measurements
White = XYZ 127.37 133.45 127.69

Adjust CRT Contrast or LCD Brightness to desired level. Press space when done.
  Initial 133.45
\ Current 133.60


4) Black point (R,G,B, Offset/Brightness)
...
Doing some initial measurements
Black = XYZ   0.20   0.21   0.35
Grey  = XYZ  27.68  29.13  28.17
White = XYZ 127.50 133.56 127.69

Adjust R,G & B offsets to get target x,y. Press space when done.
   Target Br 1.34, x 0.3280 , y 0.3436
/ Current Br 2.13, x 0.3241+, y 0.3398+  DE  2.2  R+  G+  B--


5) Check all
...
Doing check measurements
Black = XYZ   0.20   0.21   0.35
Grey  = XYZ  27.62  29.13  27.89
White = XYZ 127.67 133.68 127.89
1%    = XYZ   1.97   2.06   2.03

  Current Brightness = 133.68
  Target 50% Level  = 25.33, Current = 29.13, error =  2.8%
  Target Near Black =  1.34, Current =  2.13, error =  0.6%
  Current white = x 0.3280, y 0.3434, VDT 5698K DE 2K  0.0
  Target black = x 0.3280, y 0.3434, Current = x 0.3248, y 0.3395, error =  2.15 DE



dispcal -v -b 130 -B 0.5 -t 5800 -yl test


1) Black level (CRT: Offset/Brightness)
...
Doing some initial measurements
Black = XYZ   0.20   0.21   0.35
Grey  = XYZ  27.51  29.02  27.95
White = XYZ 127.42 133.48 127.50

Adjust CRT brightness to get target level. Press space when done.
   Target 1.33
/ Current 2.11  -


2) White point (Color temperature, R,G,B, Gain/Contrast)
...
Doing some initial measurements
Red   = XYZ  83.81  42.57   2.14
Green = XYZ  23.55  81.71  14.92
Blue  = XYZ  20.52   9.74 111.30
White = XYZ 127.63 133.60 127.89

Adjust R,G & B gain to get target x,y. Press space when done.
   Target Br 130.00, x 0.3258 , y 0.3415
/ Current Br 133.60, x 0.3280-, y 0.3433-  DE  1.2  R-- G-  B+


3) White level (CRT: Gain/Contrast, LCD: Brightness/Backlight)
...
Doing some initial measurements
White = XYZ 127.32 133.41 127.89

Adjust CRT Contrast or LCD Brightness to get target level. Press space when done.
   Target 130.00
/ Current 133.56  -


4) Black point (R,G,B, Offset/Brightness)
...
Doing some initial measurements
Black = XYZ   0.20   0.21   0.35
Grey  = XYZ  27.61  29.17  28.09
White = XYZ 127.57 133.61 128.29

Adjust R,G & B offsets to get target x,y. Press space when done.
   Target Br 1.34, x 0.3258 , y 0.3415
\ Current Br 2.13, x 0.3244+, y 0.3397+  DE  1.0  R+  G+  B--

"""

import os
import re
import sys

from wxaddons import wx
from wx.lib import delayedresult
from lib.agw import labelbook
from lib.agw.fmresources import *
from lib.agw.gradientbutton import GradientButton
from lib.agw.pygauge import PyGauge
from lib.agw.artmanager import ArtManager

from config import get_icon_bundle, getbitmap, getcfg, setcfg
from meta import name as appname
from wxwindows import numpad_keycodes
import colormath
import config
import localization as lang

BGCOLOUR = "#333333"
BORDERCOLOUR = "#222222"
FGCOLOUR = "#999999"


class FlatShadedButton(GradientButton):

	def __init__(self, parent, id=wx.ID_ANY, bitmap=None, label="",
				 pos=wx.DefaultPosition, size=wx.DefaultSize,
				 style=wx.NO_BORDER, validator=wx.DefaultValidator,
				 name="gradientbutton"):
		GradientButton.__init__(self, parent, id, bitmap, label, pos, size,
								style, validator, name)
		self._setcolours()
	
	def _setcolours(self, colour=None):
		self.SetTopStartColour(colour or wx.Colour(0x22, 0x22, 0x22))
		self.SetTopEndColour(colour or wx.Colour(0x22, 0x22, 0x22))
		self.SetBottomStartColour(colour or wx.Colour(0x22, 0x22, 0x22))
		self.SetBottomEndColour(colour or wx.Colour(0x22, 0x22, 0x22))
		self.SetForegroundColour(FGCOLOUR)
		self.SetPressedBottomColour(colour or "#222222")
		self.SetPressedTopColour(colour or "#222222")
	
	def Enable(self, enable=True):
		if enable:
			self._setcolours()
		else:
			self._setcolours(wx.Colour(0x66, 0x66, 0x66))
		GradientButton.Enable(self, enable)
	
	def Disable(self):
		self.Enable(False)


class DisplayAdjustmentImageContainer(labelbook.ImageContainer):

	def __init__(self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition,
				 size=wx.DefaultSize, style=0, agwStyle=0, name="ImageContainer"):
		"""
		Override default agw ImageContainer to use BackgroundColour and
		ForegroundColour with no borders/labeltext and hilite image instead of 
		hilite shading
		"""
		labelbook.ImageContainer.__init__(self, parent, id, pos, size, style,
										  agwStyle, name)
		imagelist = wx.ImageList(84, 72)
		for img in ("tab_hilite", "tab_selected"):
			bmp = getbitmap("theme/%s" % img)
			imagelist.Add(bmp)
		self.stateimgs = imagelist

	def HitTest(self, pt):
		"""
		Returns the index of the tab at the specified position or ``wx.NOT_FOUND``
		if ``None``, plus the flag style of L{HitTest}.

		:param `pt`: an instance of `wx.Point`, to test for hits.

		:return: The index of the tab at the specified position plus the hit test
		 flag, which can be one of the following bits:

		 ====================== ======= ================================
		 HitTest Flags           Value  Description
		 ====================== ======= ================================
		 ``IMG_OVER_IMG``             0 The mouse is over the tab icon
		 ``IMG_OVER_PIN``             1 The mouse is over the pin button
		 ``IMG_OVER_EW_BORDER``       2 The mouse is over the east-west book border
		 ``IMG_NONE``                 3 Nowhere
		 ====================== ======= ================================
		 
		"""
		
		style = self.GetParent().GetAGWWindowStyleFlag()
		
		if style & INB_USE_PIN_BUTTON:
			if self._pinBtnRect.Contains(pt):
				return -1, IMG_OVER_PIN        

		for i in xrange(len(self._pagesInfoVec)):
		
			if self._pagesInfoVec[i].GetPosition() == wx.Point(-1, -1):
				break
			
			# For Web Hover style, we test the TextRect
			if not self.HasAGWFlag(INB_WEB_HILITE):
				buttonRect = wx.RectPS((self._pagesInfoVec[i].GetPosition()[0], self._pagesInfoVec[i].GetPosition()[1] + i * 8), self._pagesInfoVec[i].GetSize())
			else:
				buttonRect = self._pagesInfoVec[i].GetTextRect()
				
			if buttonRect.Contains(pt):
				return i, IMG_OVER_IMG
			
		if self.PointOnSash(pt):
			return -1, IMG_OVER_EW_BORDER
		else:
			return -1, IMG_NONE

	def OnPaint(self, event):
		"""
		Handles the ``wx.EVT_PAINT`` event for L{ImageContainer}.

		:param `event`: a `wx.PaintEvent` event to be processed.
		"""

		dc = wx.BufferedPaintDC(self)
		style = self.GetParent().GetAGWWindowStyleFlag()

		backBrush = wx.Brush(self.GetBackgroundColour())
		if style & INB_BORDER:
			borderPen = wx.Pen(wx.SystemSettings_GetColour(wx.SYS_COLOUR_3DSHADOW))
		else:
			borderPen = wx.TRANSPARENT_PEN

		size = self.GetSize()

		# Background
		dc.SetBrush(backBrush)

		borderPen.SetWidth(1)
		dc.SetPen(borderPen)
		dc.DrawRectangle(0, 0, size.x, size.y)
		bUsePin = (style & INB_USE_PIN_BUTTON and [True] or [False])[0]

		if bUsePin:

			# Draw the pin button
			clientRect = self.GetClientRect()
			pinRect = wx.Rect(clientRect.GetX() + clientRect.GetWidth() - 20, 2, 20, 20)
			self.DrawPin(dc, pinRect, not self._bCollapsed)

			if self._bCollapsed:
				return

		borderPen = wx.BLACK_PEN
		borderPen.SetWidth(1)
		dc.SetPen(borderPen)
		dc.DrawLine(0, size.y, size.x, size.y)
		dc.DrawPoint(0, size.y)

		clientSize = 0
		bUseYcoord = (style & INB_RIGHT or style & INB_LEFT)

		if bUseYcoord:
			clientSize = size.GetHeight()
		else:
			clientSize = size.GetWidth()

		# We reserver 20 pixels for the 'pin' button
		
		# The drawing of the images start position. This is 
		# depenedent of the style, especially when Pin button
		# style is requested

		if bUsePin:
			if style & INB_TOP or style & INB_BOTTOM:
				pos = (style & INB_BORDER and [0] or [1])[0]
			else:
				pos = (style & INB_BORDER and [20] or [21])[0]
		else:
			pos = (style & INB_BORDER and [0] or [1])[0]

		nPadding = 4    # Pad text with 2 pixels on the left and right
		nTextPaddingLeft = 2

		count = 0
		
		for i in xrange(len(self._pagesInfoVec)):

			count = count + 1            
		
			# incase the 'fit button' style is applied, we set the rectangle width to the
			# text width plus padding
			# Incase the style IS applied, but the style is either LEFT or RIGHT
			# we ignore it
			normalFont = wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT)
			dc.SetFont(normalFont)

			textWidth, textHeight = dc.GetTextExtent(self._pagesInfoVec[i].GetCaption())

			# Restore font to be normal
			normalFont.SetWeight(wx.FONTWEIGHT_NORMAL)
			dc.SetFont(normalFont)

			# Default values for the surronounding rectangle 
			# around a button
			rectWidth = self._nImgSize  # To avoid the recangle to 'touch' the borders
			rectHeight = self._nImgSize

			# Incase the style requires non-fixed button (fit to text)
			# recalc the rectangle width
			if style & INB_FIT_BUTTON and \
			   not ((style & INB_LEFT) or (style & INB_RIGHT)) and \
			   not self._pagesInfoVec[i].GetCaption() == "" and \
			   not (style & INB_SHOW_ONLY_IMAGES):
			
				rectWidth = ((textWidth + nPadding * 2) > rectWidth and [nPadding * 2 + textWidth] or [rectWidth])[0]

				# Make the width an even number
				if rectWidth % 2 != 0:
					rectWidth += 1

			# Check that we have enough space to draw the button
			# If Pin button is used, consider its space as well (applicable for top/botton style)
			# since in the left/right, its size is already considered in 'pos'
			pinBtnSize = (bUsePin and [20] or [0])[0]
			
			if pos + rectWidth + pinBtnSize > clientSize:
				break

			# Calculate the button rectangle
			modRectWidth = ((style & INB_LEFT or style & INB_RIGHT) and [rectWidth - 2] or [rectWidth])[0]
			modRectHeight = ((style & INB_LEFT or style & INB_RIGHT) and [rectHeight] or [rectHeight - 2])[0]

			if bUseYcoord:
				buttonRect = wx.Rect(1, pos, modRectWidth, modRectHeight)
			else:
				buttonRect = wx.Rect(pos , 1, modRectWidth, modRectHeight)

			# Check if we need to draw a rectangle around the button
			#if self._nIndex == i:
			
				# Set the colours
				#penColour = wx.SystemSettings_GetColour(wx.SYS_COLOUR_ACTIVECAPTION)
				#brushColour = ArtManager.Get().LightColour(wx.SystemSettings_GetColour(wx.SYS_COLOUR_ACTIVECAPTION), 75)

				#dc.SetPen(wx.Pen(penColour))
				#dc.SetBrush(wx.Brush(brushColour))

				## Fix the surrounding of the rect if border is set
				#if style & INB_BORDER:
				
					#if style & INB_TOP or style & INB_BOTTOM:
						#buttonRect = wx.Rect(buttonRect.x + 1, buttonRect.y, buttonRect.width - 1, buttonRect.height)
					#else:
						#buttonRect = wx.Rect(buttonRect.x, buttonRect.y + 1, buttonRect.width, buttonRect.height - 1)
				
				#dc.DrawRectangleRect(buttonRect)
			
			#if self._nHoeveredImgIdx == i:
			
				## Set the colours
				#penColour = wx.SystemSettings_GetColour(wx.SYS_COLOUR_ACTIVECAPTION)
				#brushColour = ArtManager.Get().LightColour(wx.SystemSettings_GetColour(wx.SYS_COLOUR_ACTIVECAPTION), 90)

				#dc.SetPen(wx.Pen(penColour))
				#dc.SetBrush(wx.Brush(brushColour))

				## Fix the surrounding of the rect if border is set
				#if style & INB_BORDER:
				
					#if style & INB_TOP or style & INB_BOTTOM:
						#buttonRect = wx.Rect(buttonRect.x + 1, buttonRect.y, buttonRect.width - 1, buttonRect.height)
					#else:
						#buttonRect = wx.Rect(buttonRect.x, buttonRect.y + 1, buttonRect.width, buttonRect.height - 1)
				
				#dc.DrawRectangleRect(buttonRect)
			
			if bUseYcoord:
				rect = wx.Rect(0, pos, rectWidth, rectWidth)
			else:
				rect = wx.Rect(pos, 0, rectWidth, rectWidth)

			# Incase user set both flags:
			# INB_SHOW_ONLY_TEXT and INB_SHOW_ONLY_IMAGES
			# We override them to display both

			if style & INB_SHOW_ONLY_TEXT and style & INB_SHOW_ONLY_IMAGES:
			
				style ^= INB_SHOW_ONLY_TEXT
				style ^= INB_SHOW_ONLY_IMAGES
				self.GetParent().SetAGWWindowStyleFlag(style)
			
			# Draw the caption and text
			imgTopPadding = 0
			if not style & INB_SHOW_ONLY_TEXT and self._pagesInfoVec[i].GetImageIndex() != -1:
			
				if bUseYcoord:
				
					imgXcoord = 0
					imgYcoord = (style & INB_SHOW_ONLY_IMAGES and [pos] or [pos + imgTopPadding])[0] + (8 * i)
				
				else:
				
					imgXcoord = pos + (rectWidth / 2) - (self._nImgSize / 2)
					imgYcoord = (style & INB_SHOW_ONLY_IMAGES and [self._nImgSize / 2] or [imgTopPadding])[0]

				if self._nHoeveredImgIdx == i:
					self.stateimgs.Draw(0, dc,
										 0, imgYcoord,
										 wx.IMAGELIST_DRAW_TRANSPARENT, True)
					
				if self._nIndex == i:
					self.stateimgs.Draw(1, dc,
										 0, imgYcoord,
										 wx.IMAGELIST_DRAW_TRANSPARENT, True)

				self._ImageList.Draw(self._pagesInfoVec[i].GetImageIndex(), dc,
									 imgXcoord, imgYcoord,
									 wx.IMAGELIST_DRAW_TRANSPARENT, True)

			# Draw the text
			if not style & INB_SHOW_ONLY_IMAGES and not self._pagesInfoVec[i].GetCaption() == "":
			
				dc.SetFont(normalFont)
							
				# Check if the text can fit the size of the rectangle,
				# if not truncate it 
				fixedText = self._pagesInfoVec[i].GetCaption()
				if not style & INB_FIT_BUTTON or (style & INB_LEFT or (style & INB_RIGHT)):
				
					fixedText = self.FixTextSize(dc, self._pagesInfoVec[i].GetCaption(), self._nImgSize *2 - 4)

					# Update the length of the text
					textWidth, textHeight = dc.GetTextExtent(fixedText)
				
				if bUseYcoord:
				
					textOffsetX = ((rectWidth - textWidth) / 2 )
					textOffsetY = (not style & INB_SHOW_ONLY_TEXT  and [pos + self._nImgSize  + imgTopPadding + 3] or \
									   [pos + ((self._nImgSize * 2 - textHeight) / 2 )])[0]
				
				else:
				
					textOffsetX = (rectWidth - textWidth) / 2  + pos + nTextPaddingLeft
					textOffsetY = (not style & INB_SHOW_ONLY_TEXT and [self._nImgSize + imgTopPadding + 3] or \
									   [((self._nImgSize * 2 - textHeight) / 2 )])[0]
				
				dc.SetTextForeground(self.GetForegroundColour())
				dc.DrawText(fixedText, textOffsetX, textOffsetY)
			
			# Update the page info
			self._pagesInfoVec[i].SetPosition(buttonRect.GetPosition())
			self._pagesInfoVec[i].SetSize(buttonRect.GetSize())

			pos += rectWidth
		
		# Update all buttons that can not fit into the screen as non-visible
		for ii in xrange(count, len(self._pagesInfoVec)):
			self._pagesInfoVec[ii].SetPosition(wx.Point(-1, -1))

		# Draw the pin button
		if bUsePin:
		
			clientRect = self.GetClientRect()
			pinRect = wx.Rect(clientRect.GetX() + clientRect.GetWidth() - 20, 2, 20, 20)
			self.DrawPin(dc, pinRect, not self._bCollapsed)


class DisplayAdjustmentFlatImageBook(labelbook.FlatImageBook):

	def __init__(self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition,
				 size=wx.DefaultSize, style=0, agwStyle=0, name="FlatImageBook"):
		"""
		Override default agw ImageContainer to use BackgroundColour and
		ForegroundColour with no borders/labeltext and hilite image instead of 
		hilite shading
		"""        
		labelbook.FlatImageBook.__init__(self, parent, id, pos, size, style,
										 agwStyle, name)

	def CreateImageContainer(self):
		return DisplayAdjustmentImageContainer(self, wx.ID_ANY,
											   agwStyle=self.GetAGWWindowStyleFlag())

	def SetAGWWindowStyleFlag(self, agwStyle):
		"""
		Sets the window style.

		:param `agwStyle`: can be a combination of the following bits:

		 =========================== =========== ==================================================
		 Window Styles               Hex Value   Description
		 =========================== =========== ==================================================
		 ``INB_BOTTOM``                      0x1 Place labels below the page area. Available only for L{FlatImageBook}.
		 ``INB_LEFT``                        0x2 Place labels on the left side. Available only for L{FlatImageBook}.
		 ``INB_RIGHT``                       0x4 Place labels on the right side.
		 ``INB_TOP``                         0x8 Place labels above the page area.
		 ``INB_BORDER``                     0x10 Draws a border around L{LabelBook} or L{FlatImageBook}.
		 ``INB_SHOW_ONLY_TEXT``             0x20 Shows only text labels and no images. Available only for L{LabelBook}.
		 ``INB_SHOW_ONLY_IMAGES``           0x40 Shows only tab images and no label texts. Available only for L{LabelBook}.
		 ``INB_FIT_BUTTON``                 0x80 Displays a pin button to show/hide the book control.
		 ``INB_DRAW_SHADOW``               0x100 Draw shadows below the book tabs. Available only for L{LabelBook}.
		 ``INB_USE_PIN_BUTTON``            0x200 Displays a pin button to show/hide the book control.
		 ``INB_GRADIENT_BACKGROUND``       0x400 Draws a gradient shading on the tabs background. Available only for L{LabelBook}.
		 ``INB_WEB_HILITE``                0x800 On mouse hovering, tabs behave like html hyperlinks. Available only for L{LabelBook}.
		 ``INB_NO_RESIZE``                0x1000 Don't allow resizing of the tab area.
		 ``INB_FIT_LABELTEXT``            0x2000 Will fit the tab area to the longest text (or text+image if you have images) in all the tabs.
		 =========================== =========== ==================================================
		
		"""

		self._agwStyle = agwStyle
		
		# Check that we are not in initialization process
		if self._bInitializing:
			return

		if not self._pages:
			return

		# Detach the windows attached to the sizer
		if self.GetSelection() >= 0:
			self._mainSizer.Detach(self._windows[self.GetSelection()])

		self._mainSizer.Detach(self._pages)
		
		# Create new sizer with the requested orientaion
		className = self.GetName()

		if className == "LabelBook":
			self._mainSizer = wx.BoxSizer(wx.HORIZONTAL)
		else:
			if agwStyle & INB_LEFT or agwStyle & INB_RIGHT:
				self._mainSizer = wx.BoxSizer(wx.HORIZONTAL)
			else:
				self._mainSizer = wx.BoxSizer(wx.VERTICAL)
		
		self.SetSizer(self._mainSizer)
		
		# Add the tab container and the separator
		self._mainSizer.Add(self._pages, 0, wx.EXPAND)

		if className == "FlatImageBook":
		
			if agwStyle & INB_LEFT or agwStyle & INB_RIGHT:
				self._pages.SetSizeHints(self._pages._nImgSize + 24, -1)
			else:
				self._pages.SetSizeHints(-1, self._pages._nImgSize)
		
		# Attach the windows back to the sizer to the sizer
		if self.GetSelection() >= 0:
			self.DoSetSelection(self._windows[self.GetSelection()])

		if agwStyle & INB_FIT_LABELTEXT:
			self.ResizeTabArea()
			
		self._mainSizer.Layout()
		dummy = wx.SizeEvent()
		wx.PostEvent(self, dummy)
		self._pages.Refresh()


class DisplayAdjustmentPanel(wx.Panel):
	
	def __init__(self, parent=None, id=wx.ID_ANY, title="", ctrltype="luminance"):
		wx.Panel.__init__(self, parent, id)
		self.SetForegroundColour(FGCOLOUR)
		self.SetSizer(wx.BoxSizer(wx.VERTICAL))
		self.GetSizer().Add(wx.StaticText(self, wx.ID_ANY, title))
		self.sizer = wx.FlexGridSizer(0, 2, 0, 0)
		self.GetSizer().Add(self.sizer, flag=wx.TOP, border=8)
		self.gauges = {}
		self.txt = {}
		if ctrltype.startswith("rgb"):
			if ctrltype == "rgb_offset":
				# CRT
				lstr = "calibration.interactive_display_adjustment.black_point.crt"
			else:
				lstr = "calibration.interactive_display_adjustment.white_point"
			txt = wx.StaticText(self, wx.ID_ANY, lang.getstr(lstr) + " " +
												 lang.getstr("calibration.interactive_display_adjustment.generic_hint.plural"))
			txt.Wrap(240)
			self.GetSizer().Insert(1, txt, flag=wx.TOP, border=8)
			self.add_marker()
			self.add_gauge("R", ctrltype + "_red")
			self.sizer.Add((1, 4))
			self.sizer.Add((1, 4))
			self.add_gauge("G", ctrltype + "_green")
			self.sizer.Add((1, 4))
			self.sizer.Add((1, 4))
			self.add_gauge("B", ctrltype + "_blue")
			self.add_marker("btm")
			self.add_txt("rgb")
			self.sizer.Add((1, 8))
			self.sizer.Add((1, 8))
		else:
			if getcfg("measurement_mode") == "c":
				# CRT
				if ctrltype == "black_level":
					lstr = "calibration.interactive_display_adjustment.black_level.crt"
				else:
					lstr = "calibration.interactive_display_adjustment.white_level.crt"
			else:
				lstr = "calibration.interactive_display_adjustment.white_level.lcd"
			txt = wx.StaticText(self, wx.ID_ANY, lang.getstr(lstr) + " " +
												 lang.getstr("calibration.interactive_display_adjustment.generic_hint.singular"))
			txt.Wrap(240)
			self.GetSizer().Insert(1, txt, flag=wx.TOP, border=8)
		self.add_marker()
		bitmapnames = {"rgb_offset": "black_level",
					   "rgb_gain": "luminance"}
		self.add_gauge("L", bitmapnames.get(ctrltype, ctrltype))
		self.add_marker("btm")
		self.add_txt("luminance")

	def add_gauge(self, label="R", bitmapname=None):
		gaugecolors = {"R": (wx.Colour(153, 0, 0), wx.Colour(255, 0, 0)),
					   "G": (wx.Colour(0, 153, 0), wx.Colour(0, 255, 0)),
					   "B": (wx.Colour(0, 0, 153), wx.Colour(0, 0, 255)),
					   "L": (wx.Colour(102, 102, 102), wx.Colour(204, 204, 204))}
		self.gauges[label] = PyGauge(self, size=(200, 8))
		self.gauges[label].SetBackgroundColour(BORDERCOLOUR)
		self.gauges[label].SetBarGradient(gaugecolors[label])
		self.gauges[label].SetBorderColour(BORDERCOLOUR)
		self.gauges[label].SetValue(0)
		if bitmapname:
			self.gauges[label].label = wx.StaticBitmap(self, wx.ID_ANY, getbitmap("theme/icons/16x16/%s" %
																				  bitmapname))
		else:
			self.gauges[label].label = wx.StaticText(self, wx.ID_ANY, label)
		self.sizer.Add(self.gauges[label].label, flag=wx.ALIGN_CENTER_VERTICAL |
													  wx.RIGHT, border=8)
		self.sizer.Add(self.gauges[label], flag=wx.ALIGN_CENTER_VERTICAL)

	def add_marker(self, direction="top"):
		self.sizer.Add((1, 1))
		self.sizer.Add(wx.StaticBitmap(self,
									   bitmap=getbitmap("theme/marker_%s" %
														direction),
									   size=(200, 10)), flag=wx.ALIGN_CENTER)
	
	def add_txt(self, label):
		bitmap = wx.StaticBitmap(self, wx.ID_ANY,
								 getbitmap("theme/icons/16x16/checkmark"))
		self.sizer.Add(bitmap, flag=wx.RIGHT | wx.TOP | wx.ALIGN_CENTER_VERTICAL, border=8)
		bitmap.GetContainingSizer().Hide(bitmap)
		txtsizer = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer.Add(txtsizer, flag=wx.TOP | wx.ALIGN_CENTER_VERTICAL, border=8)
		txtsizer.Add(wx.StaticText(self, wx.ID_ANY, ""))
		self.txt[label] = wx.StaticText(self, wx.ID_ANY, "")
		self.txt[label].bitmap = bitmap
		txtsizer.Add(self.txt[label])


class DisplayAdjustmentFrame(wx.Frame):

	def __init__(self, parent=None, handler=None,
				 keyhandler=None, start_timer=True):
		self.is_measuring = None
		wx.Frame.__init__(self, parent, wx.ID_ANY,
						  lang.getstr("calibration.interactive_display_adjustment"))
		self.SetIcons(get_icon_bundle([256, 48, 32, 16], appname))
		self.SetBackgroundColour(BGCOLOUR)
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		self.SetSizer(self.sizer)
		
		# FlatImageNotebook
		self.lb = DisplayAdjustmentFlatImageBook(self,
												 agwStyle=INB_LEFT |
														  INB_SHOW_ONLY_IMAGES)
		self._assign_image_list()
		self.lb.SetBackgroundColour(BGCOLOUR)
		self.sizer.Add(self.lb, 1, flag=wx.EXPAND | wx.ALL, border=12)
		
		is_crt = getcfg("measurement_mode") == "c"
		
		self.pageid_2_argyll_key_num = {}

		if is_crt:
			# Page - black luminance
			self.page_black_luminance = DisplayAdjustmentPanel(self, wx.ID_ANY,
															   lang.getstr("calibration.black_luminance"),
															   "black_level")
			self.lb.AddPage(self.page_black_luminance,
							lang.getstr("calibration.black_luminance"), True, 0)
			self.pageid_2_argyll_key_num[len(self.pageid_2_argyll_key_num)] = "1"
		
		# Page - white point
		self.page_white_point = DisplayAdjustmentPanel(self, wx.ID_ANY,
													   lang.getstr("whitepoint") +
													   " && " +
													   lang.getstr("calibration.luminance"),
													   "rgb_gain")
		self.lb.AddPage(self.page_white_point, lang.getstr("whitepoint"), True, 1)
		self.pageid_2_argyll_key_num[len(self.pageid_2_argyll_key_num)] = "2"
		
		# Page - luminance
		self.page_luminance = DisplayAdjustmentPanel(self, wx.ID_ANY,
													 lang.getstr("calibration.luminance"))
		self.lb.AddPage(self.page_luminance,
						lang.getstr("calibration.luminance"), True, 2)
		self.pageid_2_argyll_key_num[len(self.pageid_2_argyll_key_num)] = "3"

		if is_crt:
			# Page - black point
			self.page_black_point = DisplayAdjustmentPanel(self, wx.ID_ANY,
														   lang.getstr("black_point")
														   + " && " +
														   lang.getstr("calibration.black_luminance"),
														   "rgb_offset")
			self.lb.AddPage(self.page_black_point, lang.getstr("black_point"),
							True, 3)
			self.pageid_2_argyll_key_num[len(self.pageid_2_argyll_key_num)] = "4"
		
		# Select first page
		self.lb.SetSelection(0)
		
		# Set colours
		self.lb.Children[0].SetBackgroundColour(BGCOLOUR)
		self.lb.Children[0].SetForegroundColour(FGCOLOUR)
		self.lb.Children[1].SetBackgroundColour(BGCOLOUR)
		
		# Add buttons
		self.btnsizer = wx.BoxSizer(wx.HORIZONTAL)
		self.GetSizer().Add(self.btnsizer, flag=wx.ALIGN_RIGHT | wx.BOTTOM |
									  wx.RIGHT, border=12)
		self.calibration_btn = self.create_gradient_button(getbitmap("theme/icons/10x10/skip"),
														   " " + lang.getstr("calibration.start"),
														   name="calibration_btn")
		self.calibration_btn.Bind(wx.EVT_BUTTON, self.continue_to_calibration)
		self.calibration_btn.Disable()
		self.create_start_interactive_adjustment_button()
		
		# Set size
		self.lb.SetMinSize((320, (72 + 8) * self.lb.GetPageCount() + 2 - 8))
		self.lb.GetCurrentPage().Fit()
		self.lb.SetMinSize((self.lb.GetMinSize()[0],
							max(self.lb.GetCurrentPage().GetSize()[1],
								self.lb.GetMinSize()[1])))
		self.Fit()
		self.SetMinSize(self.GetSize())
		
		# Set position
		placed = False
		if parent:
			if parent.IsShownOnScreen():
				self.Center()
				placed = True
			else:
				x = getcfg("position.progress.x", False) or parent.GetScreenPosition()[0]
				y = getcfg("position.progress.y", False) or parent.GetScreenPosition()[1]
		else:
			x = getcfg("position.progress.x")
			y = getcfg("position.progress.y")
		if not placed:
			self.SetSaneGeometry(x, y)
		
		# Use an accelerator table for space, 0-9, a-z, numpad
		keycodes = [32] + range(48, 58) + range(97, 123) + numpad_keycodes
		self.id_to_keycode = {}
		for keycode in keycodes:
			self.id_to_keycode[wx.NewId()] = keycode
		accels = []
		self.keyhandler = keyhandler
		for id, keycode in self.id_to_keycode.iteritems():
			self.Bind(wx.EVT_MENU, self.key_handler, id=id)
			accels += [(wx.ACCEL_NORMAL, keycode, id)]
		self.SetAcceleratorTable(wx.AcceleratorTable(accels))
		
		# Event handlers
		self.Bind(wx.EVT_CLOSE, self.OnClose, self)
		self.Bind(wx.EVT_MOVE, self.OnMove, self)
		self.timer = wx.Timer(self)
		if handler:
			self.Bind(wx.EVT_TIMER, handler, self.timer)
		self.Bind(labelbook.EVT_IMAGENOTEBOOK_PAGE_CHANGING, self.OnPageChanging)
		
		# Final initialization steps
		self.lastmsg = ""
		self.keepGoing = True
		self.cold_run = True
		self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy, self)
		if start_timer:
			self.start_timer()
		self.Show()
	
	def EndModal(self, returncode=wx.ID_OK):
		return returncode
	
	def MakeModal(self, makemodal=False):
		pass
	
	def OnClose(self, event):
		config.writecfg()
		if not self.timer.IsRunning():
			self.Destroy()
		else:
			self.keepGoing = False
	
	def OnDestroy(self, event):
		self.stop_timer()
		del self.timer
		
	def OnMove(self, event):
		if self.IsShownOnScreen() and not self.IsIconized() and \
		   (not self.GetParent() or
		    not self.GetParent().IsShownOnScreen()):
			prev_x = getcfg("position.progress.x")
			prev_y = getcfg("position.progress.y")
			x, y = self.GetScreenPosition()
			if x != prev_x or y != prev_y:
				setcfg("position.progress.x", x)
				setcfg("position.progress.y", y)

	def OnPageChanging(self, event):
		oldsel = event.GetOldSelection()
		newsel = event.GetSelection()
		# Reset stored target brightness
		self.lb.GetPage(oldsel).target_br = None
		self.abort()
		event.Skip()

	def Pulse(self, msg=""):
		self.lastmsg = msg
		if msg in (lang.getstr("instrument.initializing"),
				   lang.getstr("instrument.calibrating"),
				   lang.getstr("please_wait")) or msg == " " * 4:
			txt = self.lb.GetCurrentPage().txt.get("rgb",
												   self.lb.GetCurrentPage().txt.get("luminance"))
			if txt.GetLabel() != msg:
				txt.bitmap.GetContainingSizer().Hide(txt.bitmap)
				txt.SetLabel(msg)
				txt.SetForegroundColour(FGCOLOUR)
		return self.keepGoing, False
	
	def Resume(self):
		self.keepGoing = True
	
	def Update(self, value, msg=""):
		return self.Pulse(msg)
	
	def UpdatePulse(self, msg=""):
		return self.Pulse(msg)

	def _assign_image_list(self):
		imagelist = wx.ImageList(72, 72)
		for img in ("black_luminance", "white_point", "luminance",
					"black_point"):
			bmp = getbitmap("theme/icons/72x72/%s" % img)
			imagelist.Add(bmp)
		self.lb.AssignImageList(imagelist)
	
	def abort(self):
		if self.has_worker_subprocess():
			if self.is_measuring:
				try:
					self.worker.subprocess.send(" ")
				except:
					pass
	
	def abort_and_send(self, key):
		self.abort()
		if self.has_worker_subprocess():
			try:
				self.worker.subprocess.send(key)
			except:
				pass
			else:
				self.adjustment_btn.Disable()
				self.calibration_btn.Disable()
	
	def continue_to_calibration(self, event=None):
		self.abort_and_send("7")
	
	def create_start_interactive_adjustment_button(self, icon="play",
												   enable=False,
												   startstop="start"):
		if getattr(self, "adjustment_btn", None):
			#enable = self.adjustment_btn.IsEnabled()
			wx.CallAfter(self.adjustment_btn.Destroy)
			self.adjustment_btn = None
			wx.CallAfter(self.create_start_interactive_adjustment_button, icon,
						 enable, startstop)
			return
		#if self.is_measuring:
			#icon="pause"
			#startstop="stop"
		self.adjustment_btn = self.create_gradient_button(getbitmap("theme/icons/10x10/%s" %
																	icon),
														  " " +
														  lang.getstr("calibration.interactive_display_adjustment.%s" %
																	  startstop),
														  name="adjustment_btn")
		self.adjustment_btn.Bind(wx.EVT_BUTTON, self.start_interactive_adjustment)
		self.adjustment_btn.Enable(enable)
	
	def create_gradient_button(self, bitmap, label, name):
		btn = FlatShadedButton(self, bitmap=bitmap, label=label, name=name)
		self.btnsizer.Insert(0, btn, flag=wx.LEFT, border=12)
		self.btnsizer.Layout()
		return btn
	
	def flush(self):
		pass
	
	def has_worker_subprocess(self):
		return bool(getattr(self, "worker", None) and
					getattr(self.worker, "subprocess", None) and
					hasattr(self.worker.subprocess, "send"))
	
	def isatty(self):
		return True
	
	def key_handler(self, event):
		if event.GetEventType() == wx.EVT_MENU.typeId:
			keycode = self.id_to_keycode.get(event.GetId())
		if keycode:
			if keycode == ord(" "):
				self.abort()
			elif keycode in [ord(str(c)) for c in range(1, 5)]:
				key_num = chr(keycode)
				page_id = dict(zip(self.pageid_2_argyll_key_num.values(),
								   self.pageid_2_argyll_key_num.keys())).get(key_num)
				if page_id is not None and not self.is_measuring:
					self.lb.SetSelection(page_id)
					self.start_interactive_adjustment()
			elif keycode in (ord("\x1b"), ord("7"), ord("8"), ord("Q"), ord("q")):
				if self.keyhandler:
					self.keyhandler(event)
				elif self.has_worker_subprocess():
					try:
						self.worker.subprocess.send(chr(keycode))
					except:
						pass

	def parse_txt(self, txt):
		colors = {True: "#33cc00",
				  False: FGCOLOUR}
		target_br = re.search("(Target|Initial)(?:\s+Br)?\s+(\d+(?:\.\d+)?)", txt)
		if target_br:
			self.lb.GetCurrentPage().target_br = (target_br.groups()[0],
												  float(target_br.groups()[1]))
		current_br = re.search("Current(?:\s+Br)?\s+(\d+(?:\.\d+)?)", txt)
		if current_br and getattr(self.lb.GetCurrentPage(), "target_br", None) is not None:
			l_diff = (float(current_br.groups()[0]) -
					  self.lb.GetCurrentPage().target_br[1])
			l = int(round(50 + l_diff * 2))
			if self.lb.GetCurrentPage().gauges.get("L"):
				self.lb.GetCurrentPage().gauges["L"].SetValue(min(max(l, 1), 100))
				self.lb.GetCurrentPage().gauges["L"].Refresh()
			if self.lb.GetCurrentPage().txt.get("luminance"):
				self.lb.GetCurrentPage().txt["luminance"].bitmap.GetContainingSizer().Show(self.lb.GetCurrentPage().txt["luminance"].bitmap,
																						   abs(l_diff) <= 1.5)
				self.lb.GetCurrentPage().txt["luminance"].SetLabel("%s %s cd/m2, %s %s cd/m2" %
																   (lang.getstr("target"),
																	self.lb.GetCurrentPage().target_br[1],
																	lang.getstr("actual"),
																	float(current_br.groups()[0])))
				self.lb.GetCurrentPage().txt["luminance"].SetForegroundColour(colors[abs(l_diff) <= 1.5])
		xy_dE_rgb = re.search("x\s+(\d+(?:\.\d+)?)[+-]+,\s+y\s+(\d+(?:\.\d+)?)[+-]+(\s+VDT\s+\d+K?)?\s+DE\s+(?:2K\s+)?(\d+(?:\.\d+)?)\s+R([=+-]+)\s+G([=+-]+)\s+B([=+-]+)", txt)
		# groups()[0] = x
		# groups()[1] = y
		# groups()[2] = VDT (optional)
		# groups()[3] = dE
		# groups()[4] = R +-
		# groups()[5] = G +-
		# groups()[6] = B +-
		if xy_dE_rgb:
			x = float(xy_dE_rgb.groups()[0])
			y = float(xy_dE_rgb.groups()[1])
			vdt = xy_dE_rgb.groups()[2] or (" CCT %.2fK" %
											colormath.xyY2CCT(x, y))
			dE = float(xy_dE_rgb.groups()[3])
			r = int(round(50 - (xy_dE_rgb.groups()[4].count("+") -
								xy_dE_rgb.groups()[4].count("-")) * (dE)))
			g = int(round(50 - (xy_dE_rgb.groups()[5].count("+") -
								xy_dE_rgb.groups()[5].count("-")) * (dE)))
			b = int(round(50 - (xy_dE_rgb.groups()[6].count("+") -
								xy_dE_rgb.groups()[6].count("-")) * (dE)))
			if self.lb.GetCurrentPage().gauges.get("R"):
				self.lb.GetCurrentPage().gauges["R"].SetValue(min(max(r, 1), 100))
				self.lb.GetCurrentPage().gauges["R"].Refresh()
			if self.lb.GetCurrentPage().gauges.get("G"):
				self.lb.GetCurrentPage().gauges["G"].SetValue(min(max(g, 1), 100))
				self.lb.GetCurrentPage().gauges["G"].Refresh()
			if self.lb.GetCurrentPage().gauges.get("B"):
				self.lb.GetCurrentPage().gauges["B"].SetValue(min(max(b, 1), 100))
				self.lb.GetCurrentPage().gauges["B"].Refresh()
			if self.lb.GetCurrentPage().txt.get("rgb"):
				self.lb.GetCurrentPage().txt["rgb"].bitmap.GetContainingSizer().Show(self.lb.GetCurrentPage().txt["rgb"].bitmap,
																					 abs(dE) <= 1.5)
				self.lb.GetCurrentPage().txt["rgb"].SetLabel("x %s y %s%s, %s dE" %
															 (x, y, vdt, dE))
				self.lb.GetCurrentPage().txt["rgb"].SetForegroundColour(colors[abs(dE) <= 1.5])
		if current_br or xy_dE_rgb:
			if not self.is_measuring:
				self.create_start_interactive_adjustment_button("pause", True, "stop")
			self.is_measuring = True
		elif "Press 1 .. 7" in txt:
			if self.cold_run:
				self.cold_run = False
				self.Pulse(" " * 4)
			if self.is_measuring is not False:
				if self.is_measuring is True:
					self.create_start_interactive_adjustment_button(enable=True)
				else:
					self.adjustment_btn.Enable()
				self.is_measuring = False
			self.calibration_btn.Enable()
		elif "initial measurements" in txt:
			self.Pulse(lang.getstr("please_wait"))
		#self.SetTitle("is_measuring %s timer.IsRunning %s keepGoing %s" %
					  #(str(self.is_measuring), self.timer.IsRunning(), self.keepGoing))
	
	def reset(self):
		self.is_measuring = None
		for pagenum in xrange(0, self.lb.GetPageCount()):
			page = self.lb.GetPage(pagenum)
			for label in ("R", "G", "B", "L"):
				if page.gauges.get(label):
					page.gauges[label].SetValue(0)
					page.gauges[label].Refresh()
			for txt in page.txt.itervalues():
				txt.bitmap.GetContainingSizer().Hide(txt.bitmap)
				txt.SetLabel("")
				txt.SetForegroundColour(FGCOLOUR)
		self.create_start_interactive_adjustment_button()
		self.calibration_btn.Disable()
		self.cold_run = True
	
	def start_interactive_adjustment(self, event=None):
		if self.is_measuring:
			self.abort()
		else:
			self.abort_and_send(self.pageid_2_argyll_key_num[self.lb.GetSelection()])
	
	def start_timer(self, ms=50):
		self.timer.Start(ms)
	
	def stop_timer(self):
		self.timer.Stop()
	
	def write(self, txt):
		wx.CallAfter(self.parse_txt, txt)


if __name__ == "__main__":
	class Subprocess():
		def send(self, chars):
			test(chars)
	class Worker(object):
		def __init__(self):
			self.subprocess = Subprocess()
	config.initcfg()
	lang.init()
	app = wx.App(0)
	if "--crt" in sys.argv[1:]:
		setcfg("measurement_mode", "c")
	else:
		setcfg("measurement_mode", "l")
	frame = DisplayAdjustmentFrame(start_timer=False)
	frame.worker = Worker()
	frame.Show()
	def test(chars=None):
		if chars in (" ", None):
			txt = r"""Setting up the instrument
Place instrument on test window.
Hit Esc or Q to give up, any other key to continue:
Display type is LCD
Target white = native white point
Target white brightness = native brightness
Target black brightness = native brightness
Target gamma = sRGB curve

Display adjustment menu:
Press 1 .. 7
1) Black level (CRT: Offset/Brightness)
2) White point (Color temperature, R,G,B, Gain/Contrast)
3) White level (CRT: Gain/Contrast, LCD: Brightness/Backlight)
4) Black point (R,G,B, Offset/Brightness)
5) Check all
6) Measure and set ambient for viewing condition adjustment
7) Continue on to calibration
8) Exit
"""
		elif chars in ("7", "8", "q"):
			if chars != "7" or not frame.is_measuring:
				frame.Close()
			return
		else:
			txt = r"""
Doing some initial measurements
Red   = XYZ  82.22  41.78   2.23
Green = XYZ  23.48  81.55  14.93
Blue  = XYZ  20.97   9.82 113.67
White = XYZ 126.45 132.82 130.47

Adjust R,G & B gain to desired white point. Press space when done.
   Target Br 130, x 0.3280 , y 0.3436")
/ Current Br 131, x 0.3241+, y 0.3398+ VDT 5789K DE 2K 2.2  R+  G+  B--"""
		for line in txt.split("\n"):
			frame.write(line)
	test()
	app.MainLoop()
