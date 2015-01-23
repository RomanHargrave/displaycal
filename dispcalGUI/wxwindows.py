# -*- coding: utf-8 -*-

from datetime import datetime
from time import gmtime, sleep, strftime, time
import errno
import math
import os
import re
import socket
import string
import subprocess as sp
import sys
import threading
import xml.parsers.expat

import demjson

import ICCProfile as ICCP
import audio
import config
from config import (defaults, getbitmap, getcfg, geticon, get_data_path,
					get_verified_path, pyname, setcfg)
from debughelpers import getevtobjname, getevttype, handle_error
from log import log as log_, safe_print
from meta import name as appname
from options import debug
from ordereddict import OrderedDict
from util_io import StringIOu as StringIO
from util_os import waccess
from util_str import safe_str, safe_unicode, wrap
from util_xml import dict2xml
from wxaddons import (CustomEvent, FileDrop as _FileDrop,
					  get_platform_window_decoration_size, wx,
					  BetterWindowDisabler)
from wexpect import split_command_line
from wxfixes import (GenBitmapButton, GenButton, GTKMenuItemGetFixedLabel,
					 ThemedGenButton, adjust_font_size_for_gcdc,
					 get_dc_font_size, set_bitmap_labels)
from lib.agw import labelbook, pygauge
from lib.agw.gradientbutton import GradientButton, HOVER
from lib.agw.fourwaysplitter import (_TOLERANCE, FLAG_CHANGED, FLAG_PRESSED,
									 NOWHERE, FourWaySplitter,
									 FourWaySplitterEvent)
import localization as lang
import util_str

import floatspin
try:
	from wx.lib.agw import aui
	from wx.lib.agw.aui import AuiDefaultTabArt
except ImportError:
	from wx import aui
	from wx.aui import PyAuiTabArt as AuiDefaultTabArt
import wx.lib.filebrowsebutton as filebrowse
from wx.lib import fancytext
from wx.lib.statbmp import GenStaticBitmap


numpad_keycodes = [wx.WXK_NUMPAD0,
				   wx.WXK_NUMPAD1,
				   wx.WXK_NUMPAD2,
				   wx.WXK_NUMPAD3,
				   wx.WXK_NUMPAD4,
				   wx.WXK_NUMPAD5,
				   wx.WXK_NUMPAD6,
				   wx.WXK_NUMPAD7,
				   wx.WXK_NUMPAD8,
				   wx.WXK_NUMPAD9,
				   wx.WXK_NUMPAD_ADD,
				   wx.WXK_NUMPAD_DECIMAL,
				   wx.WXK_NUMPAD_ENTER,
				   wx.WXK_NUMPAD_EQUAL,
				   wx.WXK_NUMPAD_DIVIDE,
				   wx.WXK_NUMPAD_MULTIPLY,
				   wx.WXK_NUMPAD_SEPARATOR,
				   wx.WXK_NUMPAD_SUBTRACT]


def Property(func):
	return property(**func())


class AboutDialog(wx.Dialog):

	def __init__(self, *args, **kwargs):
		kwargs["style"] = wx.DEFAULT_DIALOG_STYLE & ~(wx.RESIZE_BORDER | 
													  wx.MAXIMIZE_BOX)
		kwargs["name"] = "aboutdialog"
		wx.Dialog.__init__(self, *args, **kwargs)

		self.set_properties()

		self.sizer = wx.BoxSizer(wx.VERTICAL)
		self.SetSizer(self.sizer)

	def set_properties(self):
		icon = wx.EmptyIcon()
		self.SetIcon(icon)
	
	def OnClose(self, event):
		self.Hide()

	def Layout(self):
		self.sizer.SetSizeHints(self)
		self.sizer.Layout()

	def add_items(self, items):
		self.ok = ThemedGenButton(self, -1, lang.getstr("ok"))
		self.Bind(wx.EVT_BUTTON, self.OnClose, id=self.ok.GetId())
		items.extend([self.ok, (1, 16)])
		pointsize = 10
		for item in items:
			if isinstance(item, wx.Window):
				font = item.GetFont()
				if item.GetLabel() and font.GetPointSize() > pointsize:
					font.SetPointSize(pointsize)
					item.SetFont(font)
			flag = wx.ALIGN_CENTER_HORIZONTAL
			if isinstance(item, (wx.Panel, wx.PyPanel)):
				flag |= wx.EXPAND
			else:
				flag |= wx.LEFT | wx.RIGHT
			self.sizer.Add(item, 0, flag, 12)
		self.ok.SetDefault()
		self.ok.SetFocus()


class AnimatedBitmap(wx.PyControl):

	""" Animated bitmap """

	def __init__(self, parent, id=wx.ID_ANY, bitmaps=None, range=(0, -1),
				 loop=True, pos=wx.DefaultPosition, size=wx.DefaultSize,
				 style=wx.NO_BORDER):
		"""
		Create animated bitmap
		
		bitmaps should be an array of bitmaps.
		range should be the indexes of the range of frames that should be looped.
		-1 means last frame.
		
		"""
		wx.PyControl.__init__(self, parent, id, pos, size, style)
		self._minsize = size
		self.SetBitmaps(bitmaps or [], range, loop)
		# Avoid flickering under Windows
		self.Bind(wx.EVT_ERASE_BACKGROUND, lambda event: None)
		self.Bind(wx.EVT_PAINT, self.OnPaint)
		self._timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self.OnTimer)

	def DoGetBestSize(self):
		return self._minsize

	def OnPaint(self, event):
		dc = wx.BufferedPaintDC(self)
		dc.SetBackground(wx.Brush(self.Parent.BackgroundColour))     
		dc.Clear()
		if self._bitmaps:
			if self.frame > len(self._bitmaps) - 1:
				self.frame = len(self._bitmaps) - 1
			dc.DrawBitmap(self._bitmaps[self.frame], 0, 0, True)

	def OnTimer(self, event):
		if self.loop:
			first_frame, last_frame = self.range
		else:
			first_frame, last_frame = 0, -1
		if last_frame < 0:
			last_frame += len(self._bitmaps)
		if self.frame < last_frame:
			self.frame += 1
		elif self.loop:
			self.frame = first_frame
		self.Refresh()

	def Play(self, fps=20):
		self._timer.Start(1000.0 / fps)

	def Stop(self):
		self._timer.Stop()

	def SetBitmaps(self, bitmaps, range=(0, -1), loop=True):
		w, h = self._minsize
		for bitmap in bitmaps:
			w = max(bitmap.Size[0], w)
			h = max(bitmap.Size[0], h)
		self._minsize = w, h
		self._bitmaps = bitmaps
		self.loop = loop
		self.range = range
		self.frame = 0


class AuiBetterTabArt(AuiDefaultTabArt):

	def DrawTab(self, dc, wnd, page, in_rect, close_button_state, paint_control=False):
		"""
		Draws a single tab.

		:param `dc`: a :class:`DC` device context;
		:param `wnd`: a :class:`Window` instance object;
		:param `page`: the tab control page associated with the tab;
		:param Rect `in_rect`: rectangle the tab should be confined to;
		:param integer `close_button_state`: the state of the close button on the tab;
		:param bool `paint_control`: whether to draw the control inside a tab (if any) on a :class:`MemoryDC`.
		"""

		# if the caption is empty, measure some temporary text
		caption = page.caption
		if not caption:
			caption = "Xj"

		dc.SetFont(self._selected_font)
		if hasattr(dc, "GetFullMultiLineTextExtent"):
			# Phoenix
			selected_textx, selected_texty = dc.GetMultiLineTextExtent(caption)
		else:
			# Classic
			selected_textx, selected_texty, dummy = dc.GetMultiLineTextExtent(caption)

		dc.SetFont(self._normal_font)
		if hasattr(dc, "GetFullMultiLineTextExtent"):
			# Phoenix
			normal_textx, normal_texty = dc.GetMultiLineTextExtent(caption)
		else:
			# Classic
			normal_textx, normal_texty, dummy = dc.GetMultiLineTextExtent(caption)

		control = page.control

		# figure out the size of the tab
		tab_size, x_extent = self.GetTabSize(dc, wnd, page.caption, page.bitmap,
											 page.active, close_button_state, control)

		tab_height = self._tab_ctrl_height - 3
		tab_width = tab_size[0]
		tab_x = in_rect.x
		tab_y = in_rect.y + in_rect.height - tab_height

		caption = page.caption

		# select pen, brush and font for the tab to be drawn

		if page.active:
		
			dc.SetFont(self._selected_font)
			textx, texty = selected_textx, selected_texty
		
		else:
		
			dc.SetFont(self._normal_font)
			textx, texty = normal_textx, normal_texty

		if not page.enabled:
			dc.SetTextForeground(self._tab_disabled_text_colour)
			pagebitmap = page.dis_bitmap
		else:
			dc.SetTextForeground(self._tab_text_colour(page))
			pagebitmap = page.bitmap
			
		# create points that will make the tab outline

		clip_width = tab_width
		if tab_x + clip_width > in_rect.x + in_rect.width:
			clip_width = in_rect.x + in_rect.width - tab_x

		# since the above code above doesn't play well with WXDFB or WXCOCOA,
		# we'll just use a rectangle for the clipping region for now --
		dc.SetClippingRegion(tab_x, tab_y, clip_width+1, tab_height-3)

		border_points = [wx.Point() for i in xrange(6)]
		agwFlags = self.GetAGWFlags()
		
		if agwFlags & aui.AUI_NB_BOTTOM:
		
			border_points[0] = wx.Point(tab_x,             tab_y)
			border_points[1] = wx.Point(tab_x,             tab_y+tab_height-6)
			border_points[2] = wx.Point(tab_x+2,           tab_y+tab_height-4)
			border_points[3] = wx.Point(tab_x+tab_width-2, tab_y+tab_height-4)
			border_points[4] = wx.Point(tab_x+tab_width,   tab_y+tab_height-6)
			border_points[5] = wx.Point(tab_x+tab_width,   tab_y)
		
		else: #if (agwFlags & aui.AUI_NB_TOP) 
		
			border_points[0] = wx.Point(tab_x,             tab_y+tab_height-4)
			border_points[1] = wx.Point(tab_x,             tab_y+2)
			border_points[2] = wx.Point(tab_x+2,           tab_y)
			border_points[3] = wx.Point(tab_x+tab_width-2, tab_y)
			border_points[4] = wx.Point(tab_x+tab_width,   tab_y+2)
			border_points[5] = wx.Point(tab_x+tab_width,   tab_y+tab_height-4)
		
		# TODO: else if (agwFlags & aui.AUI_NB_LEFT) 
		# TODO: else if (agwFlags & aui.AUI_NB_RIGHT) 

		drawn_tab_yoff = border_points[1].y
		drawn_tab_height = border_points[0].y - border_points[1].y

		if page.active:
		
			# draw active tab

			# draw base background colour
			r = wx.Rect(tab_x, tab_y, tab_width, tab_height)
			dc.SetPen(self._base_colour_pen)
			dc.SetBrush(self._base_colour_brush)
			dc.DrawRectangle(r.x+1, r.y+1, r.width-1, r.height-4)

			# this white helps fill out the gradient at the top of the tab
			dc.SetPen( wx.Pen(self._tab_gradient_highlight_colour) )
			dc.SetBrush( wx.Brush(self._tab_gradient_highlight_colour) )
			dc.DrawRectangle(r.x+2, r.y+1, r.width-3, r.height-4)

			# these two points help the rounded corners appear more antialiased
			dc.SetPen(self._base_colour_pen)
			dc.DrawPoint(r.x+2, r.y+1)
			dc.DrawPoint(r.x+r.width-2, r.y+1)

			# set rectangle down a bit for gradient drawing
			r.SetHeight(r.GetHeight()/2)
			r.x += 2
			r.width -= 3
			r.y += r.height
			r.y -= 2

			# draw gradient background
			top_colour = self._tab_bottom_colour
			bottom_colour = self._tab_top_colour
			dc.GradientFillLinear(r, bottom_colour, top_colour, wx.NORTH)
		
		else:
		
			# draw inactive tab

			r = wx.Rect(tab_x, tab_y+1, tab_width, tab_height-3)

			# start the gradent up a bit and leave the inside border inset
			# by a pixel for a 3D look.  Only the top half of the inactive
			# tab will have a slight gradient
			r.x += 2
			r.y += 1
			r.width -= 3
			r.height /= 2

			# -- draw top gradient fill for glossy look
			top_colour = self._tab_inactive_top_colour
			bottom_colour = self._tab_inactive_bottom_colour
			dc.GradientFillLinear(r, bottom_colour, top_colour, wx.NORTH)

			r.y += r.height
			r.y -= 1

			# -- draw bottom fill for glossy look
			top_colour = self._tab_inactive_bottom_colour
			bottom_colour = self._tab_inactive_bottom_colour
			dc.GradientFillLinear(r, top_colour, bottom_colour, wx.SOUTH)
		
		# draw tab outline
		dc.SetPen(self._border_pen)
		dc.SetBrush(wx.TRANSPARENT_BRUSH)
		dc.DrawPolygon(border_points)

		# there are two horizontal grey lines at the bottom of the tab control,
		# this gets rid of the top one of those lines in the tab control
		if page.active:
		
			if agwFlags & aui.AUI_NB_BOTTOM:
				dc.SetPen(wx.Pen(self._background_bottom_colour))
				
			# TODO: else if (agwFlags & aui.AUI_NB_LEFT) 
			# TODO: else if (agwFlags & aui.AUI_NB_RIGHT) 
			else: # for aui.AUI_NB_TOP
				dc.SetPen(self._base_colour_pen)
				
			dc.DrawLine(border_points[0].x+1,
						border_points[0].y,
						border_points[5].x,
						border_points[5].y)
		
		text_offset = tab_x + 8
		close_button_width = 0

		if close_button_state != aui.AUI_BUTTON_STATE_HIDDEN:
			close_button_width = self._active_close_bmp.GetWidth()

			if agwFlags & aui.AUI_NB_CLOSE_ON_TAB_LEFT:
				text_offset += close_button_width - 5
				
		bitmap_offset = 0
		
		if pagebitmap.IsOk():
		
			bitmap_offset = tab_x + 8
			if agwFlags & aui.AUI_NB_CLOSE_ON_TAB_LEFT and close_button_width:
				bitmap_offset += close_button_width - 5

			# draw bitmap
			dc.DrawBitmap(pagebitmap,
						  bitmap_offset,
						  drawn_tab_yoff + (drawn_tab_height/2) - (pagebitmap.GetHeight()/2),
						  True)

			text_offset = bitmap_offset + pagebitmap.GetWidth()
			text_offset += 3 # bitmap padding

		else:

			if agwFlags & aui.AUI_NB_CLOSE_ON_TAB_LEFT == 0 or not close_button_width:
				text_offset = tab_x + 8
		
		draw_text = aui.ChopText(dc, caption, tab_width - (text_offset-tab_x) - close_button_width)

		ypos = drawn_tab_yoff + (drawn_tab_height)/2 - (texty/2) - 1

		offset_focus = text_offset     

		if control is not None:
			try:
				if control.GetPosition() != wx.Point(text_offset+1, ypos):
					control.SetPosition(wx.Point(text_offset+1, ypos))

				if not control.IsShown():
					control.Show()

				if paint_control:
					bmp = aui.TakeScreenShot(control.GetScreenRect())
					dc.DrawBitmap(bmp, text_offset+1, ypos, True)
					
				controlW, controlH = control.GetSize()
				text_offset += controlW + 4
				textx += controlW + 4
			except wx.PyDeadObjectError:
				pass
			
		# draw tab text
		if hasattr(dc, "GetFullMultiLineTextExtent"):
			# Phoenix
			rectx, recty = dc.GetMultiLineTextExtent(draw_text)
		else:
			# Classic
			rectx, recty, dummy = dc.GetMultiLineTextExtent(draw_text)
		textfg = dc.GetTextForeground()
		shadow = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT)
		dc.SetTextForeground(shadow)
		dc.DrawLabel(draw_text, wx.Rect(text_offset + 1, ypos + 1, rectx, recty))
		dc.SetTextForeground(textfg)
		dc.DrawLabel(draw_text, wx.Rect(text_offset, ypos, rectx, recty))

		# draw focus rectangle
		if (agwFlags & aui.AUI_NB_NO_TAB_FOCUS) == 0:
			self.DrawFocusRectangle(dc, page, wnd, draw_text, offset_focus, bitmap_offset, drawn_tab_yoff, drawn_tab_height, rectx, recty)
		
		out_button_rect = wx.Rect()
		
		# draw close button if necessary
		if close_button_state != aui.AUI_BUTTON_STATE_HIDDEN:
		
			bmp = self._disabled_close_bmp

			if close_button_state == aui.AUI_BUTTON_STATE_HOVER:
				bmp = self._hover_close_bmp
			elif close_button_state == aui.AUI_BUTTON_STATE_PRESSED:
				bmp = self._pressed_close_bmp

			shift = (agwFlags & aui.AUI_NB_BOTTOM and [1] or [0])[0]

			if agwFlags & aui.AUI_NB_CLOSE_ON_TAB_LEFT:
				rect = wx.Rect(tab_x + 4, tab_y + (tab_height - bmp.GetHeight())/2 - shift,
							   close_button_width, tab_height)
			else:
				rect = wx.Rect(tab_x + tab_width - close_button_width - 1,
							   tab_y + (tab_height - bmp.GetHeight())/2 - shift,
							   close_button_width, tab_height)

			rect = aui.IndentPressedBitmap(rect, close_button_state)
			dc.DrawBitmap(bmp, rect.x, rect.y, True)

			out_button_rect = rect
		
		out_tab_rect = wx.Rect(tab_x, tab_y, tab_width, tab_height)

		dc.DestroyClippingRegion()

		return out_tab_rect, out_button_rect, x_extent

	def SetDefaultColours(self, base_colour=None):
		"""
		Sets the default colours, which are calculated from the given base colour.

		:param `base_colour`: an instance of :class:`Colour`. If defaulted to ``None``, a colour
		 is generated accordingly to the platform and theme.
		"""

		if base_colour is None:
			base_colour = aui.GetBaseColour()

		self.SetBaseColour( base_colour )
		self._border_colour = aui.StepColour(base_colour, 75)
		self._border_pen = wx.Pen(self._border_colour)

		self._background_top_colour = aui.StepColour(self._base_colour, 90)
		self._background_bottom_colour = aui.StepColour(self._base_colour, 120)
		
		self._tab_top_colour = self._base_colour
		self._tab_bottom_colour = aui.StepColour(self._base_colour, 130)
		self._tab_gradient_highlight_colour = aui.StepColour(self._base_colour, 130)

		self._tab_inactive_top_colour = self._background_top_colour
		self._tab_inactive_bottom_colour = aui.StepColour(self._base_colour, 110)
		
		self._tab_text_colour = lambda page: page.text_colour
		self._tab_disabled_text_colour = wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)


class BaseApp(wx.App):

	""" Application base class implementing common functionality. """

	def OnInit(self):
		self.AppName = pyname
		return True

	def MacOpenFiles(self, paths):
		if (self.TopWindow and
			isinstance(getattr(self.TopWindow, "droptarget", None), FileDrop)):
			self.TopWindow.droptarget.OnDropFiles(0, 0, paths)

	def MacReopenApp(self):
		if self.TopWindow and self.TopWindow.IsShownOnScreen():
			self.TopWindow.Raise()

	def process_argv(self, count=0):
		paths = []
		for arg in sys.argv[1:]:
			if os.path.isfile(arg):
				paths.append(safe_unicode(arg))
				if len(paths) == count:
					break
		if paths:
			self.MacOpenFiles(paths)
			return paths


active_window = None
responseformats = {}

class BaseFrame(wx.Frame):

	""" Main frame base class. """
	
	def __init__(self, *args, **kwargs):
		wx.Frame.__init__(self, *args, **kwargs)
		self.init()

	def FindWindowByName(self, name):
		""" wxPython Phoenix FindWindowByName descends into the parent windows,
		we don't want that """
		for child in self.GetAllChildren():
			if hasattr(child, "Name") and child.Name == name:
				return child

	def init(self):
		self.Bind(wx.EVT_ACTIVATE, self.activate_handler)

	def init_menubar(self):
		self.MenuBar = wx.MenuBar()
		filemenu = wx.Menu()
		quit = filemenu.Append(-1 if wx.VERSION < (2, 9) else wx.ID_EXIT,
							   "&%s\tCtrl+Q" % lang.getstr("menuitem.quit"))
		self.Bind(wx.EVT_MENU, lambda event: self.Close(), quit)
		if sys.platform != "darwin":
			self.MenuBar.Append(filemenu, "&%s" % lang.getstr("menu.file"))

	def activate_handler(self, event):
		global active_window
		active_window = self

	def listen(self):
		if isinstance(getattr(sys, "_appsocket", None), socket.socket):
			addr, port = sys._appsocket.getsockname()
			if addr == "0.0.0.0":
				try:
					addr = socket.gethostbyname(socket.gethostname())
				except socket.error:
					pass
			safe_print(lang.getstr("app.listening", (addr, port)))
			self.listening = True
			self.listener = threading.Thread(target=self.connection_handler)
			self.listener.start()

	def connection_handler(self):
		""" Handle socket connections """
		while self and getattr(self, "listening", False):
			try:
				# Wait for connection
				conn, addrport = sys._appsocket.accept()
			except socket.timeout:
				continue
			except socket.error, exception:
				if exception.errno == errno.EWOULDBLOCK:
					sleep(.05)
					continue
				break
			if (addrport[0] != "127.0.0.1" and
				not getcfg("app.allow_network_clients")):
				# Network client disallowed
				conn.close()
				safe_print(lang.getstr("app.client.network.disallowed", addrport))
				sleep(.2)
				continue
			try:
				conn.settimeout(.2)
			except socket.error, exception:
				conn.close()
				safe_print(lang.getstr("app.client.ignored", exception))
				sleep(.2)
				continue
			safe_print(lang.getstr("app.client.connect", addrport))
			threading.Thread(target=self.message_handler,
							 args=(conn, addrport)).start()
		sys._appsocket.close()

	def message_handler(self, conn, addrport):
		""" Handle messages sent via socket """
		responseformats[conn] = "plain"
		buffer = ""
		while self and getattr(self, "listening", False):
			# Wait for incoming message
			try:
				incoming = conn.recv(4096)
			except socket.timeout:
				continue
			except socket.error, exception:
				if exception.errno == errno.EWOULDBLOCK:
					sleep(.05)
					continue
				break
			else:
				if not incoming:
					break
				buffer += incoming
				while "\n" in buffer and self and getattr(self, "listening", False):
					end = buffer.find("\n")
					line = buffer[:end].strip()
					buffer = buffer[end + 1:]
					if line:
						command_timestamp = datetime.now().strftime("%Y-%m-%dTH:%M:%S.%f")
						line = safe_unicode(line, "UTF-8")
						safe_print(lang.getstr("app.incoming_message",
											   addrport + (line, )))
						data = split_command_line(line)
						response = None
						# Non-UI commands
						if data[0] == "getappname" and len(data) == 1:
							response = pyname
						elif data[0] == "getcfg" and len(data) < 3:
							if len(data) == 2:
								# Return cfg value
								if data[1] in defaults:
									if responseformats[conn].startswith("xml"):
										response = {"name": data[1],
													"value": getcfg(data[1])}
									else:
										response = {data[1]: getcfg(data[1])}
								else:
									response = "invalid"
							else:
								# Return whole cfg
								if responseformats[conn] != "plain":
									response = []
								else:
									response = OrderedDict()
								for name in sorted(defaults):
									value = getcfg(name, False)
									if value is not None:
										if responseformats[conn] != "plain":
											response.append({"name": name,
															 "value": value})
										else:
											response[name] = value
						elif data[0] == "getcommands" and len(data) == 1:
							response = sorted(self.get_commands())
						elif data[0] == "getdefault" and len(data) == 2:
							if data[1] in defaults:
								if responseformats[conn] != "plain":
									response = {"name": data[1],
												"value": defaults[data[1]]}
								else:
									response = {data[1]: defaults[data[1]]}
							else:
								response = "invalid"
						elif data[0] == "getdefaults" and len(data) == 1:
							if responseformats[conn] != "plain":
								response = []
							else:
								response = OrderedDict()
							for name in sorted(defaults):
								if responseformats[conn] != "plain":
									response.append({"name": name,
													 "value": defaults[name]})
								else:
									response[name] = defaults[name]
						elif data[0] == "getvalid" and len(data) == 1:
							if responseformats[conn] != "plain":
								response = {}
								for section, options in (("ranges",
														  config.valid_ranges),
														 ("values",
														  config.valid_values)):
									valid = response[section] = []
									for name, values in options.iteritems():
										valid.append({"name": name,
													  "values": values})
							else:
								response = {"ranges": config.valid_ranges,
											"values": config.valid_values}
							if responseformats[conn] == "plain":
								valid = []
								for section, options in response.iteritems():
									valid.append("[%s]" % section)
									for name, values in options.iteritems():
										valid.append("%s = %s" %
													 (name,
													  " ".join(demjson.encode(value)
															   for value in values)))
								response = valid
						elif (data[0] == "setresponseformat" and
							  len(data) == 2 and
							  data[1] in ("json", "json.pretty", "plain", "xml",
										  "xml.pretty")):
							responseformats[conn] = data[1]
							response = "ok"
						if response is not None:
							self.send_response(response, data, conn,
											   command_timestamp)
							continue
						# UI commands
						wx.CallAfter(self.finish_processing, data, conn,
									 command_timestamp)
		try:
			conn.shutdown(socket.SHUT_RDWR)
		except socket.error, exception:
			if exception.errno != errno.ENOTCONN:
				safe_print("Warning - could not shutdown connection:", exception)
		safe_print(lang.getstr("app.client.disconnect", addrport))
		conn.close()
		responseformats.pop(conn)

	def get_app_state(self, format):
		win = self.get_top_window()
		if isinstance(win, wx.Dialog) and win.IsShown():
			if isinstance(win, (DirDialog, FileDialog)):
				response = format_ui_element(win, format)
				if format != "plain":
					response.update({"message": win.Message, "path": win.Path})
				else:
					response = [response, demjson.encode(win.Message),
								"path", demjson.encode(win.Path)]
			elif isinstance(win, (AboutDialog, BaseInteractiveDialog,
								  ProgressDialog)):
				response = format_ui_element(win, format)
				if format == "plain":
					response = [response]
				if hasattr(win, "message") and win.message:
					if format != "plain":
						response["message"] = win.message.Label
					else:
						response.append(demjson.encode(win.message.Label))
				# Ordering in tab order
				for child in win.GetAllChildren():
					if (child and isinstance(child, (FlatShadedButton,
													 GenButton, wx.Button)) and
						child.TopLevelParent is win and
						child.IsShownOnScreen() and child.IsEnabled()):
						if format != "plain":
							if not "buttons" in response:
								response["buttons"] = []
							response["buttons"].append(child.Label)
						else:
							if not "buttons" in response:
								response.append("buttons")
							response.append(demjson.encode(child.Label))
			elif win.__class__ is wx.Dialog:
				response = format_ui_element(win, format)
				if format == "plain":
					response = [response]
			else:
				return "blocked"
			if format == "plain":
				response = " ".join(response)
			return response
		if hasattr(self, "worker") and self.worker.is_working():
			return "busy"
		return "idle"

	def get_commands(self):
		return self.get_common_commands()

	def get_common_commands(self):
		cmds = ["abort", "activate [window]",
				"alt", "cancel", "ok [filename]", "close [window]",
				"echo <string>", "getactivewindow", "getappname",
				"getcellvalues [window] <grid>", "getcommands",
				"getcfg [option]", "getdefault <option>", "getdefaults",
				"getmenus", "getmenuitems [menu]", "getstate",
				"getuielement [window] <element>", "getuielements [window]",
				"getvalid", "getwindows",
				"interact [window] <element> [setvalue value]",
				"invokemenu <menu> <menuitem>",
				"restore-defaults [category...]",
				"setcfg <option> <value>", "setresponseformat <format>"]
		if hasattr(self, "update_controls"):
			cmds.append("refresh")
			if hasattr(self, "panel"):
				cmds.append("setlanguage <languagecode>")
		return cmds

	def get_top_window(self):
		windows = [active_window or self] + list(wx.GetTopLevelWindows())
		while windows:
			win = windows.pop()
			if win and isinstance(win, wx.Dialog) and win.IsShown():
				break
		return (win and win.IsShown() and win) or self

	def process_data(self, data):
		""" Override this method in derived classes """
		return "invalid"

	def finish_processing(self, data, conn, command_timestamp):
		if not responseformats.get(conn):
			# Client connection has broken down in the meantime
			return
		state = self.get_app_state("plain")
		dialog = isinstance(self.get_top_window(), wx.Dialog)
		if ((state in ("blocked", "busy") or dialog) and
			data[0] not in ("abort", "alt", "cancel", "close",
							"getactivewindow", "getcellvalues",
							"getmenus", "getmenuitems",
							"getstate", "getuielement", "getuielements",
							"getwindows", "interact", "ok")):
			if dialog:
				state = "blocked"
			self.send_response(state, data, conn, command_timestamp)
			return
		win = None
		child = None
		response = "ok"
		if data[0] in ("abort", "close"):
			if (hasattr(self, "worker") and not self.worker.abort_all() and
				self.worker.is_working()):
				response = "failed"
			elif data[0] == "close":
				if len(data) == 2:
					win = get_toplevel_window(data[1])
				else:
					win = self.get_top_window()
				if win:
					state = self.get_app_state("plain")
					if state == "blocked":
						response = state
					elif (state not in ("busy", "idle") and
						  win is not self.get_top_window()):
						response = "blocked"
					elif (isinstance(win, (AboutDialog, BaseInteractiveDialog,
										   ProgressDialog)) or
						  win.__class__ is wx.Dialog):
						if win.IsModal():
							wx.CallAfter(win.EndModal, wx.ID_CANCEL)
						else:
							wx.CallAfter(win.Close)
					elif isinstance(win, wx.Frame):
						wx.CallAfter(win.Close)
					else:
						response = "failed"
				else:
					response = "invalid"
		elif data[0] == "activate" and len(data) < 3:
			response = "ok"
			if len(data) < 2:
				win = wx.GetApp().TopWindow
			else:
				try:
					id_name_label = int(data[1])
				except ValueError:
					id_name_label = data[1]
				for win in reversed(wx.GetTopLevelWindows()):
					if (win.Id == id_name_label or win.Name == id_name_label or
						win.Label == id_name_label) and win.IsShown():
						break
				else:
					win = None
			if win and win.IsShown():
				if win.IsIconized():
					win.Restore()
				win.Raise()
			else:
				response = "invalid"
		elif data[0] in ("alt", "cancel", "ok") and (len(data) == 1 or
													 (data[0] == "ok" and
													  len(data) == 2)):
			response = "invalid"
			win = self.get_top_window()
			if isinstance(win, (DirDialog, FileDialog)):
				if data[0] in ("ok", "cancel"):
					if len(data) > 1:
						# Path
						win.SetPath(data[1])
					if win.IsModal():
						wx.CallAfter(win.EndModal,
									 {"ok": wx.ID_OK,
									  "cancel": wx.ID_CANCEL}[data[0]])
					elif data[0] == "cancel":
						wx.CallAfter(win.Close)
					response = "ok"
			elif isinstance(win, (AboutDialog, BaseInteractiveDialog,
								  ProgressDialog)):
				if hasattr(win, data[0]):
					ctrl = getattr(win, data[0])
					if ctrl.IsEnabled():
						if win.IsModal():
							wx.CallAfter(win.EndModal, ctrl.Id)
						elif isinstance(ctrl, (FlatShadedButton, GenButton,
											   wx.Button)):
							event = wx.CommandEvent(wx.EVT_BUTTON.typeId,
													ctrl.Id)
							event.SetEventObject(ctrl)
							wx.CallAfter(ctrl.ProcessEvent, event)
						response = "ok"
					else:
						response = "forbidden"
		elif (data[0] == "echo" and
			  "echo <string>" in self.get_common_commands() and len(data) > 1):
			txt = " ".join(data[1:])
			safe_print(txt)
		elif data[0] == "invokemenu" and len(data) == 3:
			if self.get_app_state("plain") == "idle":
				menubar = self.GetMenuBar()
				response = "invalid"
			else:
				menubar = None
				response = "forbidden"
			if menubar:
				try:
					menu_pos = int(data[1])
				except ValueError:
					menu_pos = menubar.FindMenu(data[1])
				if (menu_pos not in (wx.NOT_FOUND, None) and
					menu_pos > -1 and menu_pos < menubar.GetMenuCount() and
					menubar.IsEnabledTop(menu_pos)):
					menu = menubar.GetMenu(menu_pos)
					try:
						menuitem_id = int(data[2])
					except ValueError:
						menuitem_id = menu.FindItem(data[2])
					if menuitem_id not in (wx.NOT_FOUND, None):
						menuitem = menu.FindItemById(menuitem_id)
						if menuitem.IsEnabled():
							event = wx.CommandEvent(wx.EVT_MENU.typeId,
													menuitem_id)
							event.SetEventObject(menu)
							wx.CallAfter(self.ProcessEvent, event)
							response = "ok"
						else:
							response = "forbidden"
		elif data[0] == "getactivewindow" and len(data) == 1:
			win = self.get_top_window()
			response = format_ui_element(win, responseformats[conn])
			win = None
		elif data[0] == "getcellvalues" and len(data) in (2, 3):
			response = "invalid"
			if len(data) == 3:
				win = get_toplevel_window(data[1])
			else:
				win = self.get_top_window()
			if win:
				name = data[-1]
				child = get_widget(win, name)
				if (child and isinstance(child, wx.grid.Grid) and
					child.IsShownOnScreen()):
					response = []
					for row in xrange(child.GetNumberRows()):
						values = []
						for col in xrange(child.GetNumberCols()):
							values.append(child.GetCellValue(row, col))
						if responseformats[conn] == "plain":
							values = demjson.encode(values).strip("[]").replace('","', '" "')
						response.append(values)
				elif child is False:
					response = "forbidden"
				child = None
		elif data[0] == "getmenus" and len(data) == 1:
			menus = []
			menubar = self.GetMenuBar()
			if menubar:
				for i, (menu, label) in enumerate(menubar.GetMenus()):
					label = label.lstrip("&_")
					if responseformats[conn] != "plain":
						menus.append({"label": label, "position": i,
									  "enabled": menubar.IsEnabledTop(i)})
					else:
						menus.append("%s %s %s" % (i,
												   demjson.encode(label),
												   "enabled"
												   if menubar.IsEnabledTop(i)
												   else "disabled"))
			response = menus
		elif data[0] == "getmenuitems" and len(data) < 3:
			menuitems = []
			menulabels = []
			menus = []
			menubar = self.GetMenuBar()
			if menubar:
				if len(data) == 2:
					try:
						menu_pos_label = int(data[1])
					except ValueError:
						menu_pos_label = data[1]
				for i, (menu, label) in enumerate(menubar.GetMenus()):
					label = label.lstrip("&_")
					if (len(data) == 2 and label != menu_pos_label and
						i != menu_pos_label):
						continue
					if (responseformats[conn] != "plain" and
						not label in menulabels):
						menuitems = []
						menulabels.append(label)
						menus.append({"label": label, "position": i,
									  "enabled": menubar.IsEnabledTop(i),
									  "menuitems": menuitems})
					for menuitem in menu.GetMenuItems():
						if menuitem.IsSeparator():
							continue
						if responseformats[conn] != "plain":
							menuitems.append({"label": menuitem.Label,
											  "id": menuitem.Id,
											  "enabled": menubar.IsEnabledTop(i) and
														 menuitem.IsEnabled(),
											  "checkable": menuitem.IsCheckable(),
											  "checked": menuitem.IsChecked()})
						else:
							menuitems.append("%s %s %s %s %s%s%s" %
											 (i, demjson.encode(label),
											  menuitem.Id,
											  demjson.encode(menuitem.Label),
											  "enabled"
											  if menubar.IsEnabledTop(i) and
											  menuitem.IsEnabled()
											  else "disabled",
											  " checkable" if menuitem.IsCheckable()
											  else "",
											  " checked" if menuitem.IsChecked()
											  else ""))
			if responseformats[conn] != "plain":
				response = menus
			else:
				response = menuitems
		elif data[0] == "getstate" and len(data) == 1:
			response = self.get_app_state(responseformats[conn])
		elif data[0] == "getuielement" and len(data) in (2, 3):
			response = "invalid"
			if len(data) == 3:
				win = get_toplevel_window(data[1])
			else:
				win = self.get_top_window()
			if win:
				name = data[-1]
				child = get_widget(win, name)
				if child and child.IsShownOnScreen():
					response = format_ui_element(child, responseformats[conn])
				elif child is False:
					response = "forbidden"
				child = None
		elif data[0] == "getuielements" and len(data) < 3:
			uielements = []
			if len(data) == 2:
				win = get_toplevel_window(data[1])
			else:
				win = self.get_top_window()
			if win:
				# Ordering in tab order
				for child in win.GetAllChildren():
					if is_scripting_allowed(win, child):
						uielements.append(format_ui_element(child,
															responseformats[conn]))
				child = None
				response = uielements
			else:
				response = "invalid"
		elif data[0] == "getwindows" and len(data) == 1:
			windows = filter(lambda win: win.IsShown(), wx.GetTopLevelWindows())
			response = [format_ui_element(win, responseformats[conn])
						for win in windows]
			win = None
		elif data[0] == "interact" and len(data) > 1 and len(data) < 6:
			response = "invalid"
			value = None
			args = data[1:]
			if len(args) > 2 and args[-2] == "setvalue":
				value = args.pop()
				args.pop()
			name = args.pop()
			state = self.get_app_state("plain")
			if state == "blocked":
				win = None
				response = state
			elif args:
				# Window name specified
				win = get_toplevel_window(args[0])
				if state not in ("busy",
								 "idle") and win is not self.get_top_window():
					win = None
					response = "blocked"
			else:
				win = self.get_top_window()
			if win:
				child = get_widget(win, name)
				if child is False or (child and (not child.IsShownOnScreen() or
												 not child.IsEnabled())):
					response = "forbidden"
				elif child:
					event = None
					if value is not None:
						# Set value
						values = value.split(",", 2)
						if isinstance(child, floatspin.FloatSpin):
							try:
								child.SetValue(float(value))
							except:
								response = "failed"
							else:
								event = floatspin.EVT_FLOATSPIN
						elif (isinstance(child, (CustomCheckBox,
												 wx.CheckBox)) and
							  value in ("0", "1", "false", "true")):
							child.SetValue(bool(demjson.decode(value)))
							event = wx.EVT_CHECKBOX
						elif isinstance(child, wx.ComboBox):
							child.SetValue(value)
							event = wx.EVT_TEXT
						elif isinstance(child, wx.Choice):
							# NOTE: Check for wx.ComboBox first because it is a
							# subclass of wx.Choice!
							if value in child.Items:
								child.SetStringSelection(value)
								event = wx.EVT_CHOICE
						elif isinstance(child, (aui.AuiNotebook,
												labelbook.FlatBookBase,
												wx.Notebook)):
							for page_idx in xrange(child.GetPageCount()):
								if child.GetPageText(page_idx) == value:
									child.SetSelection(page_idx)
									event = wx.EVT_NOTEBOOK_PAGE_CHANGED
									break
						elif isinstance(child, wx.grid.Grid) and len(values) == 3:
							try:
								row, col = (int(v) for v in values[:2])
							except ValueError:
								row, col = -1, -1
							if (row > -1 and col > -1 and
								row < child.GetNumberRows() and
								col < child.GetNumberCols()):
								if (child.IsEditable() and
									not child.IsReadOnly(row, col)):
									child.SetCellValue(row, col, values[2])
									event = wx.grid.GridEvent(-1,
															  wx.grid.EVT_GRID_CELL_CHANGE.evtType[0],
															  child,
															  row,
															  col)
								else:
									response = "forbidden"
						elif isinstance(child, wx.ListCtrl):
							for row in xrange(child.GetItemCount()):
								item = []
								for col in xrange(child.GetColumnCount()):
									item.append(child.GetItem(row, col).GetText())
								if " ".join(item) == value:
									state = child.GetItemState(row, wx.LIST_STATE_SELECTED)
									child.Select(row, not state &
													  wx.LIST_STATE_SELECTED)
									if state & wx.LIST_STATE_SELECTED:
										event = wx.EVT_LIST_ITEM_DESELECTED
									else:
										event = wx.EVT_LIST_ITEM_SELECTED
									break
						elif (isinstance(child, wx.RadioButton) and
							  value in ("0", "1", "false", "true")):
							child.SetValue(bool(demjson.decode(value)))
							event = wx.EVT_RADIOBUTTON
						elif isinstance(child, wx.Slider):
							try:
								child.SetValue(int(value))
							except:
								response = "failed"
							else:
								event = wx.EVT_SLIDER
						elif isinstance(child, wx.SpinCtrl):
							try:
								child.SetValue(int(value))
							except:
								response = "failed"
							else:
								event = wx.EVT_SPINCTRL
						elif isinstance(child, wx.TextCtrl):
							child.ChangeValue(value)
							event = wx.EVT_TEXT
					elif isinstance(child, (FlatShadedButton,
											GenButton, wx.Button)):
						event = wx.EVT_BUTTON
					if event:
						if isinstance(child, CustomCheckBox):
							ctrl = child._cb
						else:
							ctrl = child
						events = [event]
						if event is wx.EVT_SPINCTRL:
							events.append(wx.EVT_TEXT)
						elif event is wx.EVT_TEXT and win.FindFocus() != ctrl:
							events.append(wx.EVT_KILL_FOCUS)
						for event in events:
							if not isinstance(event, wx.Event):
								event = wx.CommandEvent(event.typeId, ctrl.Id)
								if isinstance(child, (CustomCheckBox, wx.CheckBox,
													  wx.RadioButton)):
									event.SetInt(int(ctrl.Value))
								event.SetEventObject(ctrl)
							if not isinstance(ctrl, wx.Notebook):
								# Bus error under Mac OS X
								wx.CallAfter(ctrl.ProcessEvent, event)
						wx.CallLater(1, child.Refresh)
						response = "ok"
		elif data[0] == "setcfg" and len(data) == 3:
			# Set configuration option
			if data[1] in defaults:
				value = data[2]
				if value == "null":
					value = None
				elif value == "false":
					value = 0
				elif value == "true":
					value = 1
				else:
					try:
						value = type(defaults[data[1]])(value)
					except (UnicodeEncodeError, ValueError):
						pass
				setcfg(data[1], value)
				if getcfg(data[1], False) != value:
					response = "failed"
			else:
				response = "invalid"
		else:
			try:
				response = self.process_data(data)
			except Exception, exception:
				safe_print(exception)
				if responseformats[conn] != "plain":
					response = {"class": exception.__class__.__name__,
								"error": safe_unicode(exception)}
				else:
					response = "error " + demjson.encode(safe_unicode(exception))
			else:
				# Some commands can be overriden, check response
				if response == "invalid":
					if (data[0] == "refresh" and len(data) == 1 and
						hasattr(self, "update_controls")):
						self.update_controls()
						self.update_layout()
						response = "ok"
					elif data[0] == "restore-defaults":
						for name in defaults:
							if len(data) > 1:
								include = False
								for category in data[1:]:
									if name.startswith(data[1]):
										include = True
										break
								if not include:
									continue
							setcfg(name, None)
						response = "ok"
					elif (data[0] == "setlanguage" and len(data) == 2 and
						  hasattr(self, "panel") and
						  hasattr(self, "update_controls")):
						setcfg("lang", data[1])
						self.panel.Freeze()
						self.setup_language()
						self.update_controls()
						self.update_layout()
						self.panel.Thaw()
						response = "ok"
		if (data[0].startswith("get") or data[0] in ("refresh",
													 "restore-defaults",
													 "setcfg") or
			response != "ok"):
			# No interaction with UI
			relayfunc = lambda func, *args: func(*args)
		else:
			# Interaction with UI
			# Prevent actual file dialogs blocking the UI - need to restore
			# original values after processing
			wx.DirDialog = DirDialog
			wx.FileDialog = FileDialog
			# Use CallLater so GUI methods have a chance to run before we send
			# our response
			relayfunc = lambda func, *args: wx.CallLater(55, func, *args)
			relayfunc(restore_path_dialog_classes)
		relayfunc(self.send_response, response, data, conn, command_timestamp,
				  child or win)

	def send_response(self, response, data, conn, command_timestamp, win=None):
		if not responseformats.get(conn):
			# Client connection has broken down in the meantime
			return
		if response == "invalid":
			safe_print(lang.getstr("app.incoming_message.invalid"))
		if responseformats[conn] != "plain":
			if not isinstance(response, (basestring, list)):
				response = [response]
			command = {"name": data[0], "timestamp": command_timestamp}
			if data[1:]:
				command["arguments"] = data[1:]
			response = {"command": command,
						"result": response,
						"timestamp": datetime.now().strftime("%Y-%m-%dTH:%M:%S.%f")}
			if win:
				response["object"] = format_ui_element(win, responseformats[conn])
		if responseformats[conn].startswith("json"):
			response = demjson.encode(response,
									  compactly=responseformats[conn] == "json")
		elif responseformats[conn].startswith("xml"):
			response = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
						(responseformats[conn] == "xml.pretty" and "\n" or "") +
						dict2xml(response, "response",
								 pretty=responseformats[conn] == "xml.pretty"))
		else:
			if isinstance(response, dict):
				response = ["%s = %s" % (name, value) for name, value in
							response.iteritems()]
			if isinstance(response, list):
				response = "\n".join(response)
		try:
			conn.sendall("%s\4" % safe_str(response, "UTF-8"))
		except socket.error, exception:
			safe_print(exception)

	def focus_handler(self, event):
		if debug and hasattr(self, "last_focused_ctrl"):
				safe_print("[D] Last focused control: ID %s %s %s" %
						   (self.last_focused_ctrl.GetId(),
							self.last_focused_ctrl.GetName(),
							self.last_focused_ctrl.__class__))
		if (hasattr(self, "last_focused_ctrl") and self.last_focused_ctrl and
			not isinstance(self.last_focused_ctrl, floatspin.FloatTextCtrl) and
			self.last_focused_ctrl != event.GetEventObject() and
			self.last_focused_ctrl.IsShownOnScreen()):
			catchup_event = wx.FocusEvent(wx.EVT_KILL_FOCUS.evtType[0], 
										  self.last_focused_ctrl.GetId())
			if debug:
				safe_print("[D] Last focused control ID %s %s %s processing "
						   "catchup event type %s %s" % 
						   (self.last_focused_ctrl.GetId(), 
							self.last_focused_ctrl.GetName(), 
							self.last_focused_ctrl.__class__, 
							catchup_event.GetEventType(), 
							getevttype(catchup_event)))
			if self.last_focused_ctrl.ProcessEvent(catchup_event):
				if debug:
					safe_print("[D] Last focused control processed catchup "
							   "event")
				event.Skip()
				if hasattr(event.GetEventObject(), "GetId") and \
				   callable(event.GetEventObject().GetId):
					event = CustomEvent(event.GetEventType(), 
										event.GetEventObject(), 
										self.last_focused_ctrl)
		if (hasattr(event.GetEventObject(), "GetId") and
			callable(event.GetEventObject().GetId) and
			event.GetEventObject().IsShownOnScreen()):
		   	if debug:
					safe_print("[D] Setting last focused control to ID %s %s %s"
							   % (event.GetEventObject().GetId(),
								  getevtobjname(event, self),
								  event.GetEventObject().__class__))
			self.last_focused_ctrl = event.GetEventObject()
		if debug:
			if hasattr(event, "GetWindow") and event.GetWindow():
				safe_print("[D] Focus moving from control ID %s %s %s to %s %s %s, "
						   "event type %s %s" % (event.GetWindow().GetId(), 
												 event.GetWindow().GetName(), 
												 event.GetWindow().__class__,
												 event.GetEventObject().GetId(), 
												 getevtobjname(event, self), 
												 event.GetEventObject().__class__,
												 event.GetEventType(), 
												 getevttype(event)))
			else:
				safe_print("[D] Focus moving to control ID %s %s %s, event type "
						   "%s %s" % (event.GetEventObject().GetId(), 
									  getevtobjname(event, self), 
									  event.GetEventObject().__class__,
									  event.GetEventType(), getevttype(event)))
		event.Skip()
	
	def setup_language(self):
		"""
		Substitute translated strings for menus, controls, labels and tooltips.
		
		"""
		if not hasattr(self, "_menulabels"):
			# Needed for Phoenix because custom attributes attached to menus
			# are not retained
			self._menulabels = {}
		if not hasattr(self, "_ctrllabels"):
			# Needed for Phoenix because custom attributes attached to controls
			# may not be retained
			self._ctrllabels = {}
		if not hasattr(self, "_tooltipstrings"):
			# Needed for Phoenix because custom attributes attached to controls
			# may not be retained
			self._tooltipstrings = {}
		
		# Title
		if not hasattr(self, "_Title"):
			# Backup un-translated label
			title = self._Title = self.Title
		else:
			# Restore un-translated label
			title = self._Title
		translated = lang.getstr(title)
		if translated != title:
			self.Title = translated
		
		# Menus
		menubar = self.menubar if hasattr(self, "menubar") else self.GetMenuBar()
		if menubar:
			for menu, label in menubar.GetMenus():
				menu_pos = menubar.FindMenu(label)
				if not menu in self._menulabels:
					# Backup un-translated label
					self._menulabels[menu] = label
				menubar.SetMenuLabel(menu_pos, "&" + lang.getstr(
									 GTKMenuItemGetFixedLabel(self._menulabels[menu])))
				if not hasattr(menu, "_Items"):
					# Backup un-translated labels
					menu._Items = [(item, item.Label) for item in 
								   menu.GetMenuItems()]
				for item, label in menu._Items:
					if item.Label:
						label = GTKMenuItemGetFixedLabel(label)
						if item.Accel:
							item.Text = lang.getstr(label) + "\t" + \
										item.Accel.ToString()
						else:
							item.Text = lang.getstr(label)
			if sys.platform == "darwin":
				wx.GetApp().SetMacHelpMenuTitleName(lang.getstr("menu.help"))
			self.SetMenuBar(menubar)
		
		# Controls and labels
		for child in self.GetAllChildren():
			if isinstance(child, (wx.StaticText, wx.Control,
								  BetterStaticFancyText,
								  BitmapBackgroundPanelText)):
				if not child in self._ctrllabels:
					# Backup un-translated label
					label = self._ctrllabels[child] = child.Label
				else:
					# Restore un-translated label
					label = self._ctrllabels[child]
				translated = lang.getstr(label)
				if translated != label:
					if isinstance(child, wx.Button):
						translated = translated.replace("&", "&&")
					child.Label = translated
				if child.ToolTip:
					if not child in self._tooltipstrings:
						# Backup un-translated tooltip
						tooltipstr = self._tooltipstrings[child] = child.ToolTip.Tip
					else:
						# Restore un-translated tooltip
						tooltipstr = self._tooltipstrings[child]
					translated = lang.getstr(tooltipstr)
					if translated != tooltipstr:
						child.SetToolTipString(translated)
			elif isinstance(child, FileBrowseBitmapButtonWithChoiceHistory):
				if child.history:
					selection = child.textControl.GetSelection()
					child.textControl.Clear()
					for path in child.history:
						child.textControl.Append(child.GetName(path))
					child.textControl.SetSelection(selection)
	
	def update_layout(self):
		""" Update main window layout. """
		minsize, clientsize = self.Sizer.MinSize, self.ClientSize
		if not self.IsIconized() and not self.IsMaximized():
			if ((minsize[0] > clientsize[0] or minsize[1] > clientsize[1] or not
				 getattr(self, "_layout", False))):
				self.Sizer.SetMinSize((max(minsize[0], clientsize[0]),
									   max(minsize[1], clientsize[1])))
				self.GetSizer().SetSizeHints(self)
				self.GetSizer().Layout()
				self.Sizer.SetMinSize((-1, -1))
				self._layout = True
			else:
				self.Layout()
		if hasattr(self, "ClientToWindowSize"):
			# wxPython 2.8.12
			self.SetMinSize(self.ClientToWindowSize(minsize))
		else:
			# wxPython >= 2.9
			self.MinClientSize = minsize
	
	def set_child_ctrls_as_attrs(self, parent=None):
		"""
		Set child controls and labels as attributes of the frame.
		
		Will also set a maximum font size of 11 pt.
		parent is the window over which children will be iterated and
		defaults to self.
		
		"""
		if not parent:
			parent = self
		for child in parent.GetAllChildren():
			if debug:
				safe_print(child.__class__, child.Name)
			if isinstance(child, (wx.StaticText, wx.Control, 
								  filebrowse.FileBrowseButton,
								  floatspin.FloatSpin)):
				if (isinstance(child, wx.Choice) and wx.VERSION < (2, 9) and
					sys.platform not in ("darwin", "win32") and
					child.MinSize[1] == -1):
					# wx.Choice with wxPython < 2.9 under Gnome 3 Adwaita theme
					# has varying height. We can't easily check for Gnome 3 or
					# Adwaita, so simply always set wx.Choice height to
					# wx.ComboBox height with wxPython < 2.9 under Linux
					if not hasattr(self, "_comboboxheight"):
						combobox = wx.ComboBox(self, -1)
						self._comboboxheight = combobox.Size[1]
						combobox.Destroy()
					child.MinSize = child.MinSize[0], self._comboboxheight
				elif isinstance(child, wx.BitmapButton):
					set_bitmap_labels(child)
				child.SetMaxFontSize(11)
				if sys.platform == "darwin" or debug:
					# Work around ComboBox issues on Mac OS X
					# (doesn't receive EVT_KILL_FOCUS)
					if isinstance(child, wx.ComboBox):
						if child.IsEditable():
							if debug:
								safe_print("[D]", child.Name,
										   "binds EVT_TEXT to focus_handler")
							child.Bind(wx.EVT_TEXT, self.focus_handler)
					else:
						child.Bind(wx.EVT_SET_FOCUS, self.focus_handler)
				if not hasattr(self, child.Name):
					setattr(self, child.Name, child)
			if (sys.platform == "win32" and sys.getwindowsversion() >= (6, ) and
				isinstance(child, wx.Panel)):
				# No need to enable double buffering under Linux and Mac OS X.
				# Under Windows, enabling double buffering on the panel seems
				# to work best to reduce flicker.
				child.SetDoubleBuffered(True)


class BaseInteractiveDialog(wx.Dialog):

	""" Base class for informational and confirmation dialogs """
	
	def __init__(self, parent=None, id=-1, title=appname, msg="", 
				 ok="OK", bitmap=None, pos=(-1, -1), size=(400, -1), 
				 show=True, log=True, 
				 style=wx.DEFAULT_DIALOG_STYLE, nowrap=False, wrap=70,
				 name=wx.DialogNameStr):
		if log:
			safe_print(msg)
		if parent:
			pos = list(pos)
			i = 0
			for coord in pos:
				if coord > -1:
					pos[i] += parent.GetScreenPosition()[i]
				i += 1
			pos = tuple(pos)
		wx.Dialog.__init__(self, parent, id, title, pos, size, style, name)
		if sys.platform == "win32":
			bgcolor = self.BackgroundColour
			self.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))
		self.SetPosition(pos)  # yes, this is needed
		self.set_icons()
		
		self.Bind(wx.EVT_SHOW, self.OnShow, self)

		margin = 12

		self.sizer0 = wx.BoxSizer(wx.VERTICAL)
		self.SetSizer(self.sizer0)
		if bitmap:
			self.sizer1 = wx.FlexGridSizer(1, 2, 0, 0)
		else:
			self.sizer1 = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer2 = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer3 = wx.FlexGridSizer(0, 1, 0, 0)
		self.sizer0.Add(self.sizer1, flag = wx.ALIGN_LEFT | wx.TOP | 
		   wx.RIGHT | wx.LEFT, border = margin)
		self.buttonpanel = wx.Panel(self)
		self.buttonpanel.SetSizer(wx.BoxSizer(wx.VERTICAL))
		self.buttonpanel.Sizer.Add(self.sizer2, 1, flag=wx.ALIGN_RIGHT | wx.ALL, 
								   border=margin)
		if sys.platform == "win32":
			self.buttonpanel_line = wx.Panel(self, size=(-1,1))
			self.buttonpanel_line.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT))
			self.sizer0.Add(self.buttonpanel_line, flag=wx.TOP | wx.EXPAND,
							border=margin)
			self.buttonpanel.SetBackgroundColour(bgcolor)
		self.sizer0.Add(self.buttonpanel, flag=wx.EXPAND)

		if bitmap:
			self.bitmap = wx.StaticBitmap(self, -1, bitmap, size=(32, 32))
			self.sizer1.Add(self.bitmap, flag=wx.RIGHT, border=margin)

		self.sizer1.Add(self.sizer3, flag=wx.ALIGN_LEFT)
		msg = msg.replace("&", "&&")
		self.message = wx.StaticText(self, -1, msg if nowrap else
											   util_str.wrap(msg, wrap))
		self.sizer3.Add(self.message)

		btnwidth = 80

		self.ok = wx.Button(self.buttonpanel, wx.ID_OK, ok)
		self.sizer2.Add(self.ok)
		self.Bind(wx.EVT_BUTTON, self.OnClose, id=wx.ID_OK)

		self.buttonpanel.Layout()
		self.sizer0.SetSizeHints(self)
		self.sizer0.Layout()
		self.pos = pos
		if show:
			self.ok.SetDefault()
			self.ShowModalThenDestroy(parent)

	def ShowModalThenDestroy(self, parent=None):
		if parent:
			if getattr(parent, "modaldlg", None):
				wx.CallLater(250, self.ShowModalThenDestroy, parent)
				return
			parent.modaldlg = self
		self.ShowModal()
		if parent:
			parent.modaldlg = None
			del parent.modaldlg
		self.Destroy()

	def OnShow(self, event):
		event.Skip()
		if not getattr(event, "IsShown", getattr(event, "GetShow", bool))():
			return
		if not wx.GetApp().IsActive() and wx.GetApp().GetTopWindow():
			wx.GetApp().GetTopWindow().RequestUserAttention()

	def OnClose(self, event):
		if event.GetEventObject() == self:
			id = wx.ID_OK
		else:
			id = event.GetId()
		self.EndModal(id)

	def Show(self, show=True):
		if show:
			self.set_position()
		return wx.Dialog.Show(self, show)

	def ShowModal(self):
		self.set_position()
		return wx.Dialog.ShowModal(self)

	def set_icons(self):
		parent = self.Parent
		while parent:
			if isinstance(parent, wx.Frame):
				break
			parent = parent.Parent
		if (parent and parent.Icon and parent.Icon.IsOk() and
			parent.Name in ("lut3dframe", "lut_viewer", "profile_info",
							"scriptingframe", "synthiccframe", "tcgen",
							"vrml2x3dframe")):
			self.Icon = parent.Icon
		else:
			self.SetIcons(config.get_icon_bundle([256, 48, 32, 16], appname))

	def set_position(self):
		if self.Parent and self.Parent.IsIconized():
			self.Parent.Restore()
		if not getattr(self, "pos", None) or self.pos == (-1, -1):
			self.Center(wx.BOTH)
		elif self.pos[0] == -1:
			self.Center(wx.HORIZONTAL)
		elif self.pos[1] == -1:
			self.Center(wx.VERTICAL)


class BitmapBackgroundBitmapButton(wx.BitmapButton):
	
	""" A BitmapButton that will use its parent bitmap background.
	
	The parent needs to have a GetBitmap() method.
	
	"""

	def __init__(self, *args, **kwargs):
		wx.BitmapButton.__init__(self, *args, **kwargs)
		self.Bind(wx.EVT_PAINT, self.OnPaint)

	def OnPaint(self, dc):
		dc = wx.PaintDC(self)
		try:
			dc = wx.GCDC(dc)
		except Exception, exception:
			pass
		dc.DrawBitmap(self.Parent.GetBitmap(), 0, -self.GetPosition()[1])
		dc.DrawBitmap(self.GetBitmapLabel(), 0, 0)


bitmaps = {}

class BitmapBackgroundPanel(wx.PyPanel):
	
	""" A panel with a background bitmap """

	def __init__(self, *args, **kwargs):
		wx.PyPanel.__init__(self, *args, **kwargs)
		self._bitmap = None
		self.alpha = 1.0
		self.blend = False
		self.borderbtmcolor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DSHADOW)
		self.bordertopcolor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT)
		self.drawborderbtm = False
		self.drawbordertop = False
		self.repeat_sub_bitmap_h = None
		self.scalebitmap = (True, False)
		self.scalequality = wx.IMAGE_QUALITY_NORMAL
		self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
		self.Bind(wx.EVT_PAINT, self.OnPaint)
		self.Bind(wx.EVT_SIZE, self.OnSize)

	def AcceptsFocus(self):
		return False

	def AcceptsFocusFromKeyboard(self):
		return False
	
	def GetBitmap(self):
		return self._bitmap

	def SetBitmap(self, bitmap):
		self._bitmap = bitmap

	def OnPaint(self, event):
		dc = wx.BufferedPaintDC(self)
		self._draw(dc)

	def OnSize(self,event):
		self.Refresh()
	
	def _draw(self, dc):
		bgcolor = self.BackgroundColour
		bbr = wx.Brush(bgcolor, wx.SOLID)
		dc.SetBackground(bbr)
		dc.SetBackgroundMode(wx.SOLID)
		dc.Clear()
		dc.SetTextForeground(self.GetForegroundColour())
		bmp = self._bitmap
		if bmp:
			if self.alpha < 1.0 or self.blend:
				key = (id(bmp), bgcolor, self.alpha)
				bmp = bitmaps.get(key)
				if not bmp:
					bmp = self._bitmap
					image = bmp.ConvertToImage()
					if self.alpha < 1.0:
						if not image.HasAlpha():
							image.InitAlpha()
						alphabuffer = image.GetAlphaBuffer()
						for i, byte in enumerate(alphabuffer):
							if byte > "\0":
								alphabuffer[i] = chr(int(round(ord(byte) *
															   self.alpha)))
					if self.blend:
						databuffer = image.GetDataBuffer()
						for i, byte in enumerate(databuffer):
							if byte > "\0":
								databuffer[i] = chr(int(round(ord(byte) *
															  (bgcolor[i % 3] /
															   255.0))))
					bmp = image.ConvertToBitmap()
					bitmaps[key] = bmp
			if True in self.scalebitmap:
				img = bmp.ConvertToImage()
				img.Rescale(self.GetSize()[0] if self.scalebitmap[0]
							else img.GetSize()[0],
							self.GetSize()[1]  if self.scalebitmap[1]
							else img.GetSize()[1], quality=self.scalequality)
				bmp = img.ConvertToBitmap()
			dc.DrawBitmap(bmp, 0, 0)
			if (self.repeat_sub_bitmap_h and self.Size[0] > bmp.Size[0] and
				bmp.Size[0] >= self.repeat_sub_bitmap_h[0] and
				bmp.Size[1] >= self.repeat_sub_bitmap_h[1]):
				sub_bmp = bmp.GetSubBitmap(self.repeat_sub_bitmap_h)
				sub_img = sub_bmp.ConvertToImage()
				sub_img.Rescale(self.GetSize()[0] -
								bmp.GetSize()[0],
								bmp.GetSize()[1],
								quality=self.scalequality)
				dc.DrawBitmap(sub_img.ConvertToBitmap(), bmp.GetSize()[0], 0)
		if self.drawbordertop:
			pen = wx.Pen(self.bordertopcolor, 1, wx.SOLID)
			pen.SetCap(wx.CAP_BUTT)
			dc.SetPen(pen)
			dc.DrawLine(0, 0, self.GetSize()[0], 0)
		if self.drawborderbtm:
			pen = wx.Pen(self.borderbtmcolor, 1, wx.SOLID)
			pen.SetCap(wx.CAP_BUTT)
			dc.SetPen(pen)
			dc.DrawLine(0, self.GetSize()[1] - 1, self.GetSize()[0], self.GetSize()[1] - 1)


class BitmapBackgroundPanelText(BitmapBackgroundPanel):
	
	""" A panel with a background bitmap and text label """

	def __init__(self, *args, **kwargs):
		BitmapBackgroundPanel.__init__(self, *args, **kwargs)
		self.label_x = None
		self.label_y = None
		self.textalpha = 1.0
		self.textshadow = True
		self.textshadowcolor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT)
		self.use_gcdc = False
	
	def _set_font(self, dc):
		font = self.GetFont()
		if self.use_gcdc:
			# NOTE: Drawing text to wx.GCDC has problems with unicode chars
			# being replaced with boxes under wxGTK
			try:
				dc = wx.GCDC(dc)
			except Exception, exception:
				pass
			font.SetPointSize(get_dc_font_size(font.GetPointSize(), dc))
		dc.SetFont(font)
		return dc
 	
	def GetLabel(self):
		return self.Label

	Label = ""
	
	def SetLabel(self, label):
		self.Label = label
	
	def _draw(self, dc):
		BitmapBackgroundPanel._draw(self, dc)
		dc.SetBackgroundMode(wx.TRANSPARENT)
		dc = self._set_font(dc)
		label = self.Label.splitlines()
		for i, line in enumerate(label):
			w1, h1 = self.GetTextExtent(line)
			w2, h2 = dc.GetTextExtent(line)
			if self.label_x is None:
				w = (max(w1, w2) - min(w1, w2)) / 2.0 + min(w1, w2)
				x = self.GetSize()[0] / 2.0 - w / 2.0
			else:
				x = self.label_x
			h = (max(h1, h2) - min(h1, h2)) / 2.0 + min(h1, h2)
			if self.label_y is None:
				y = self.GetSize()[1] / 2.0 - h / 2.0
			else:
				y = self.label_y + h * i
			if self.textshadow:
				dc.SetTextForeground(self.textshadowcolor)
				dc.DrawText(line, x + 1, y + 1)
			color = self.GetForegroundColour()
			if self.textalpha < 1:
				bgcolor = self.BackgroundColour
				bgblend = (1.0 - self.textalpha)
				blend = self.textalpha
				color = wx.Colour(int(round(bgblend * bgcolor.Red() +
											blend * color.Red())),
								  int(round(bgblend * bgcolor.Green() +
											blend * color.Green())),
								  int(round(bgblend * bgcolor.Blue() +
											blend * color.Blue())))
			dc.SetTextForeground(color)
			dc.DrawText(line, x, y)


class ConfirmDialog(BaseInteractiveDialog):

	""" Confirmation dialog with OK and Cancel buttons """

	def __init__(self, parent=None, id=-1, title=appname, msg="", 
				 ok="OK", cancel="Cancel", bitmap=None, pos=(-1, -1), 
				 size=(400, -1), alt=None, log=False, 
				 style=wx.DEFAULT_DIALOG_STYLE, nowrap=False, wrap=70,
				 name=wx.DialogNameStr):
		BaseInteractiveDialog.__init__(self, parent, id, title, msg, ok, 
									   bitmap, pos, size, show=False, 
									   log=log, style=style,
									   nowrap=nowrap, wrap=wrap,
									   name=name)

		self.Bind(wx.EVT_CLOSE, self.OnClose, self)

		margin = 12

		if alt:
			self.alt = wx.Button(self.buttonpanel, -1, alt)
			self.sizer2.Prepend((margin, margin))
			self.sizer2.Prepend(self.alt)
			self.Bind(wx.EVT_BUTTON, self.OnClose, id=self.alt.GetId())

		self.cancel = wx.Button(self.buttonpanel, wx.ID_CANCEL, cancel)
		self.sizer2.Prepend((margin, margin))
		self.sizer2.Prepend(self.cancel)
		self.Bind(wx.EVT_BUTTON, self.OnClose, id=wx.ID_CANCEL)
		
		self.buttonpanel.Layout()
		self.sizer0.SetSizeHints(self)
		self.sizer0.Layout()

	def OnClose(self, event):
		if hasattr(self, "OnCloseIntercept"):
			try:
				self.OnCloseIntercept(event)
			except Exception, exception:
				handle_error(exception, self)
			return
		if event.GetEventObject() == self:
			id = wx.ID_CANCEL
		else:
			id = event.GetId()
		self.EndModal(id)


class FileBrowseBitmapButtonWithChoiceHistory(filebrowse.FileBrowseButtonWithHistory):

	def __init__(self, *arguments, **namedarguments):
		self.history = namedarguments.get("history") or []
		if 'history' in namedarguments:
			del namedarguments["history"]

		self.historyCallBack = None
		if callable(self.history):
			self.historyCallBack = self.history
			self.history = []
		name = namedarguments.get('name', 'fileBrowseButtonWithHistory')
		if 'name' in namedarguments:
			del namedarguments['name']
		filebrowse.FileBrowseButton.__init__(self, *arguments, **namedarguments)
		self.SetName(name)
		self.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
		if "__WXGTK__" in wx.PlatformInfo and wx.VERSION < (2, 9):
			self.textControl.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
			self.browseButton.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

	def OnSetFocus(self, event):
		if event.EventObject is self:
			floatspin.focus_next_keyboard_focusable_control(self)
		event.Skip()

	def OnKeyDown(self, event):
		if event.KeyCode == wx.WXK_TAB:
			floatspin.focus_next_keyboard_focusable_control(event.EventObject)
		else:
			event.Skip()
	
	def Disable(self):
		self.Enable(False)
	
	def Enable(self, enable=True):
		self.textControl.Enable(enable and self.history != [""])
		self.browseButton.Enable(enable)

	def GetName(self, path):
		"""
		Return a name for a path. Return value may be a translated string.
		
		"""
		name = None
		if os.path.splitext(path)[1].lower() in (".icc", ".icm"):
			try:
				profile = ICCP.ICCProfile(path)
			except (IOError, ICCP.ICCProfileInvalidError):
				pass
			else:
				name = profile.getDescription()
		if not name:
			name = os.path.basename(path)
		return lang.getstr(name)

	def GetValue(self):
		"""
		retrieve current value of text control
		"""
		if self.textControl.GetSelection() > -1:
			return self.history[self.textControl.GetSelection()]
		return ""
	
	GetPath = GetValue

	def OnChanged(self, evt):
		self.textControl.SetToolTipString(self.history[self.textControl.GetSelection()])
		if self.callCallback and self.changeCallback:
			self.changeCallback(evt)

	def SetBackgroundColour(self,color):
		wx.Panel.SetBackgroundColour(self,color)

	def SetHistory(self, value=(), selectionIndex=None, control=None):
		"""Set the current history list"""
		if control is None:
			control = self.textControl
		if self.history == value:
			return
		index = control.GetSelection()
		if self.history and index > -1:
			tempValue = self.history[index]
		else:
			tempValue = ""
		self.history = []
		control.Clear()
		for path in list(value) + [tempValue]:
			if path:
				self.history.append(path)
				control.Append(self.GetName(path))
		self.setupControl(selectionIndex, control)
	
	def SetMaxFontSize(self, pointsize=11):
		self.textControl.SetMaxFontSize(pointsize)

	def SetValue(self, value, callBack=1, clear_on_empty_value=False):
		if not value:
			if clear_on_empty_value and self.history:
				index = self.textControl.GetSelection()
				if index > -1:
					self.history.pop(index)
					self.textControl.Delete(index)
		if not value in self.history:
			self.history.append(value)
			self.textControl.Append(self.GetName(value))
		self.setupControl(self.history.index(value))
		if callBack:
			self.changeCallback(CustomEvent(wx.EVT_CHOICE.typeId, 
											self.textControl))
	
	def SetPath(self, path):
		self.SetValue(path, 0, clear_on_empty_value=True)

	def createBrowseButton(self):
		"""Create the browse-button control"""
		button = GenBitmapButton(self, -1, geticon(16, "document-open"), 
								 style=wx.NO_BORDER)
		button.SetToolTipString(self.toolTip)
		button.Bind(wx.EVT_BUTTON, self.OnBrowse)
		return button

	def createDialog(self, parent, id, pos, size, style, name=None):
		"""Setup the graphic representation of the dialog"""
		wx.Panel.__init__ (self, parent, id, pos, size, style)
		self.SetMinSize(size) # play nice with sizers

		box = wx.BoxSizer(wx.HORIZONTAL)

		self.textControl = self.createTextControl()
		if sys.platform == "darwin" and wx.VERSION > (2, 9):
			# Prevent 1px cut-off at left-hand side
			box.Add((1, 1))
		box.Add(self.textControl, 1, wx.ALIGN_CENTER_VERTICAL | wx.TOP |
									 wx.BOTTOM, 4)

		self.browseButton = self.createBrowseButton()
		box.Add(self.browseButton, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)
		if self.history:
			history = self.history
			self.history = []
			self.SetHistory(history)

		self.SetAutoLayout(True)
		self.SetSizer(box)
		self.Layout()

	def createLabel(self):
		return (0, 0)

	def createTextControl(self):
		"""Create the text control"""
		textControl = wx.Choice(self, -1)
		textControl.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
		if self.changeCallback:
			textControl.Bind(wx.EVT_CHOICE, self.OnChanged)
		return textControl
	
	def setupControl(self, selectionIndex=None, control=None):
		if control is None:
			control = self.textControl
		if selectionIndex is None:
			selectionIndex = len(self.history) - 1
		control.SetSelection(selectionIndex)
		toolTip = (self.history[selectionIndex] if selectionIndex > -1 else
				   self.toolTip)
		control.SetToolTipString(toolTip)
		control.Enable(self.browseButton.Enabled and self.history != [""])


class PathDialog(ConfirmDialog):

	def __init__(self, parent, msg, name):
		ConfirmDialog.__init__(self, parent, msg=msg,
							   ok=lang.getstr("browse"),
							   cancel=lang.getstr("cancel"), name=name)
		self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)
		self.ok.Bind(wx.EVT_BUTTON, self.filedialog_handler)

	def OnDestroy(self, event):
		self.filedialog.Destroy()
		event.Skip()

	def __getattr__(self, name):
		return getattr(self.filedialog, name)

	def filedialog_handler(self, event):
		self.EndModal(self.filedialog.ShowModal())


_DirDialog = wx.DirDialog

class DirDialog(PathDialog):

	""" wx.DirDialog cannot be interacted with programmatically after
	ShowModal(), a functionality we need for scripting. """

	def __init__(self, *args, **kwargs):
		PathDialog.__init__(self, args[0], args[1], "dirdialog")
		self.filedialog = _DirDialog(*args, **kwargs)


_FileDialog = wx.FileDialog

class FileDialog(PathDialog):

	""" wx.FileDialog cannot be interacted with programmatically after
	ShowModal(), a functionality we need for scripting. """

	def __init__(self, *args, **kwargs):
		PathDialog.__init__(self, args[0], args[1], "filedialog")
		self.filedialog = _FileDialog(*args, **kwargs)


class FileDrop(_FileDrop):
	
	def __init__(self, parent, drophandlers=None):
		self.parent = parent
		_FileDrop.__init__(self, drophandlers)
		self.unsupported_handler = self.drop_unsupported_handler

	def drop_unsupported_handler(self):
		"""
		Drag'n'drop handler for unsupported files. 
		
		Shows an error message.
		
		"""
		if (not hasattr(self.parent, "worker") or
			not self.parent.worker.is_working()):
			InfoDialog(self.parent, msg=lang.getstr("error.file_type_unsupported") +
										"\n\n" + "\n".join(self._filenames), 
					   ok=lang.getstr("ok"), 
					   bitmap=geticon(32, "dialog-error"))


class FlatShadedButton(GradientButton):

	def __init__(self, parent, id=wx.ID_ANY, bitmap=None, label="",
				 pos=wx.DefaultPosition, size=wx.DefaultSize,
				 style=wx.NO_BORDER, validator=wx.DefaultValidator,
				 name="gradientbutton", bgcolour=None, fgcolour=None):
		GradientButton.__init__(self, parent, id, bitmap, label, pos, size,
								style, validator, name)
		self._setcolours(bgcolour, fgcolour)
		self.SetFont(adjust_font_size_for_gcdc(self.GetFont()))
	
	def _setcolours(self, bgcolour=None, fgcolour=None):
		self.SetTopStartColour(bgcolour or wx.Colour(0x22, 0x22, 0x22))
		self.SetTopEndColour(bgcolour or wx.Colour(0x22, 0x22, 0x22))
		self.SetBottomStartColour(bgcolour or wx.Colour(0x22, 0x22, 0x22))
		self.SetBottomEndColour(bgcolour or wx.Colour(0x22, 0x22, 0x22))
		self.SetForegroundColour(fgcolour or wx.Colour(0xdd, 0xdd, 0xdd))
		self.SetPressedBottomColour(bgcolour or wx.Colour(0x22, 0x22, 0x22))
		self.SetPressedTopColour(bgcolour or wx.Colour(0x22, 0x22, 0x22))
	
	def Disable(self):
		self.Enable(False)
	
	def DoGetBestSize(self):
		"""
		Overridden base class virtual. Determines the best size of the
		button based on the label and bezel size.
		"""

		if not getattr(self, "_lastBestSize", None):
			label = self.GetLabel() or u"\u200b"
			
			dc = wx.MemoryDC(wx.EmptyBitmap(1, 1))
			try:
				dc = wx.GCDC(dc)
			except:
				pass
			dc.SetFont(self.GetFont())
			retWidth, retHeight = dc.GetTextExtent(label)
			if label != u"\u200b" and wx.VERSION < (2, 9):
				retWidth += 5
			
			bmpWidth = bmpHeight = 0
			if self._bitmap:
				if label != u"\u200b":
					constant = 10
					if wx.VERSION < (2, 9):
						retWidth += 5
				else:
					constant = 0
				# Pin the bitmap height to 10
				bmpWidth, bmpHeight = self._bitmap.GetWidth()+constant, 10
				retWidth += bmpWidth
				retHeight = max(bmpHeight, retHeight)

			self._lastBestSize = wx.Size(retWidth + 20, retHeight + 15)
		return self._lastBestSize

	def OnGainFocus(self, event):
		"""
		Handles the ``wx.EVT_SET_FOCUS`` event for L{GradientButton}.

		:param `event`: a `wx.FocusEvent` event to be processed.
		"""
		
		self._hasFocus = True
		self._mouseAction = HOVER
		self.Refresh()
		self.Update()

	def OnLoseFocus(self, event):
		"""
		Handles the ``wx.EVT_LEAVE_WINDOW`` event for L{GradientButton}.

		:param `event`: a `wx.MouseEvent` event to be processed.
		"""

		self._hasFocus = False
		self._mouseAction = None
		self.Refresh()
		event.Skip()

	def OnPaint(self, event):
		"""
		Handles the ``wx.EVT_PAINT`` event for L{GradientButton}.

		:param `event`: a `wx.PaintEvent` event to be processed.
		"""

		dc = wx.BufferedPaintDC(self)
		gc = wx.GraphicsContext.Create(dc)
		dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))        
		dc.Clear()
		
		clientRect = self.GetClientRect()
		gradientRect = wx.Rect(*clientRect)
		capture = wx.Window.GetCapture()

		x, y, width, height = clientRect        
		
		gradientRect.SetHeight(gradientRect.GetHeight()/2 + ((capture==self and [1] or [0])[0]))
		if capture != self:
			if self._mouseAction == HOVER:
				topStart, topEnd = self.LightColour(self._topStartColour, 10), self.LightColour(self._topEndColour, 10)
			else:
				topStart, topEnd = self._topStartColour, self._topEndColour

			rc1 = wx.Rect(x, y, width, height/2)
			path1 = self.GetPath(gc, rc1, 8)
			br1 = gc.CreateLinearGradientBrush(x, y, x, y+height/2, topStart, topEnd)
			gc.SetBrush(br1)
			gc.FillPath(path1) #draw main

			path4 = gc.CreatePath()
			path4.AddRectangle(x, y+height/2-8, width, 8)
			path4.CloseSubpath()
			gc.SetBrush(br1)
			gc.FillPath(path4)            
		
		else:
			
			rc1 = wx.Rect(x, y, width, height)
			path1 = self.GetPath(gc, rc1, 8)
			gc.SetPen(wx.Pen(self._pressedTopColour))
			gc.SetBrush(wx.Brush(self._pressedTopColour))
			gc.FillPath(path1)
		
		gradientRect.Offset((0, gradientRect.GetHeight()))

		if capture != self:

			if self._mouseAction == HOVER:
				bottomStart, bottomEnd = self.LightColour(self._bottomStartColour, 10), self.LightColour(self._bottomEndColour, 10)
			else:
				bottomStart, bottomEnd = self._bottomStartColour, self._bottomEndColour

			rc3 = wx.Rect(x, y+height/2, width, height/2)
			path3 = self.GetPath(gc, rc3, 8)
			br3 = gc.CreateLinearGradientBrush(x, y+height/2, x, y+height, bottomStart, bottomEnd)
			gc.SetBrush(br3)
			gc.FillPath(path3) #draw main

			path4 = gc.CreatePath()
			path4.AddRectangle(x, y+height/2, width, 8)
			path4.CloseSubpath()
			gc.SetBrush(br3)
			gc.FillPath(path4)
			
			shadowOffset = 0
		else:
		
			rc2 = wx.Rect(x+1, gradientRect.height/2, gradientRect.width, gradientRect.height)
			path2 = self.GetPath(gc, rc2, 8)
			gc.SetPen(wx.Pen(self._pressedBottomColour))
			gc.SetBrush(wx.Brush(self._pressedBottomColour))
			gc.FillPath(path2)
			shadowOffset = 1

		font = gc.CreateFont(self.GetFont(), self.GetForegroundColour())
		gc.SetFont(font)
		label = self.GetLabel()
		if label and self._bitmap:
			label = " " + label
		tw, th = gc.GetTextExtent(label)

		if self._bitmap:
			bw, bh = self._bitmap.GetWidth(), self._bitmap.GetHeight()
			if tw:
				tw += 5
				if wx.VERSION < (2, 9):
					tw += 5
		else:
			bw = bh = 0
			
		pos_x = (width-bw-tw)/2+shadowOffset      # adjust for bitmap and text to centre        
		if self._bitmap:
			pos_y =  (height-bh)/2+shadowOffset
			gc.DrawBitmap(self._bitmap, pos_x, pos_y, bw, bh) # draw bitmap if available
			pos_x = pos_x + 5   # extra spacing from bitmap

		gc.DrawText(label, pos_x + bw + shadowOffset, (height-th)/2-.5+shadowOffset) 
	
	def Enable(self, enable=True):
		if enable:
			self._setcolours()
		else:
			self._setcolours(wx.Colour(0x66, 0x66, 0x66))
		GradientButton.Enable(self, enable)

	def SetBitmap(self, bitmap):
		self._bitmap = bitmap
		self.Refresh()


class BorderGradientButton(GradientButton):

	def __init__(self, parent, id=wx.ID_ANY, bitmap=None, label="",
				 pos=wx.DefaultPosition, size=wx.DefaultSize,
				 style=wx.NO_BORDER, validator=wx.DefaultValidator,
				 name="gradientbutton"):
		GradientButton.__init__(self, parent, id, bitmap, label, pos, size,
								style, validator, name)
		self.SetFont(adjust_font_size_for_gcdc(self.GetFont()))
		self._bitmapdisabled = self._bitmap
		self._bitmapfocus = self._bitmap
		self._bitmaphover = self._bitmap
		self._bitmapselected = self._bitmap
		set_bitmap_labels(self)
		self._enabled = True

	BitmapLabel = property(lambda self: self._bitmap,
						   lambda self, bitmap: self.SetBitmap(bitmap))
	
	def Disable(self):
		self.Enable(False)

	def DoGetBestSize(self):
		"""
		Overridden base class virtual. Determines the best size of the
		button based on the label and bezel size.
		"""

		label = self.GetLabel()
		if not label:
			return wx.Size(112, 48)
		
		dc = wx.ClientDC(self)
		dc.SetFont(self.GetFont())
		retWidth, retHeight = dc.GetTextExtent(label)
		
		bmpWidth = bmpHeight = 0
		constant = 15
		if self._bitmap:
			bmpWidth, bmpHeight = self._bitmap.GetWidth()+20, self._bitmap.GetHeight()
			retWidth += bmpWidth
			retHeight = max(bmpHeight, retHeight)
			constant = 15

		return wx.Size(retWidth+constant, retHeight+constant) 
	
	def Enable(self, enable=True):
		self._enabled = enable
		GradientButton.Enable(self, enable)
		self.Update()

	def IsEnabled(self):
		return self._enabled

	Enabled = property(IsEnabled, Enable)

	def OnPaint(self, event):
		"""
		Handles the ``wx.EVT_PAINT`` event for L{GradientButton}.

		:param `event`: a `wx.PaintEvent` event to be processed.
		"""

		dc = wx.BufferedPaintDC(self)
		gc = wx.GraphicsContext.Create(dc)
		dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))        
		dc.Clear()
		
		clientRect = self.GetClientRect()
		gradientRect = wx.Rect(*clientRect)
		capture = wx.Window.GetCapture()

		x, y, width, height = clientRect        
		
		gradientRect.SetHeight(gradientRect.GetHeight()/2 + ((capture==self and [1] or [0])[0]))
		if capture != self:
			if self._mouseAction == HOVER:
				topStart, topEnd = self.LightColour(self._topStartColour, 10), self.LightColour(self._bottomEndColour, 10)
			else:
				topStart, topEnd = self._topStartColour, self._bottomEndColour
			brush = gc.CreateLinearGradientBrush(0, 1, 0, height, topStart,
												 topEnd)
		else:
			brush = gc.CreateLinearGradientBrush(0, 1, 0, height,
												 self._pressedTopColour,
												 self._pressedBottomColour)

		fgcolor = self.ForegroundColour
		if not self.IsEnabled():
			fgcolor = self.LightColour(fgcolor, 40)

		gc.SetBrush(brush)
		gc.SetPen(wx.Pen(self.LightColour(fgcolor, 20)))
		gc.DrawRoundedRectangle(1, 1, width - 2, height - 2, height / 2)

		if capture != self:
			shadowOffset = 0
		else:
			shadowOffset = 1

		font = gc.CreateFont(self.GetFont(), fgcolor)
		gc.SetFont(font)
		label = self.GetLabel()
		if label and self._bitmap:
			label = " " + label
		tw, th = gc.GetTextExtent(label)

		if self._bitmap:
			bw, bh = self._bitmap.GetWidth(), self._bitmap.GetHeight()
			if tw:
				tw += 5
				if wx.VERSION < (2, 9):
					tw += 5
		else:
			bw = bh = 0
			
		pos_x = (width-bw-tw)/2+shadowOffset      # adjust for bitmap and text to centre        
		if self.IsEnabled():
			if self._mouseAction == HOVER:
				bitmap = self._bitmaphover
			else:
				bitmap = self._bitmap
		else:
			bitmap = self._bitmapdisabled
		if bitmap:
			pos_y =  (height-bh)/2+shadowOffset
			gc.DrawBitmap(bitmap, pos_x, pos_y, bw, bh) # draw bitmap if available
			pos_x = pos_x + 5   # extra spacing from bitmap

		gc.DrawText(label, pos_x + bw + shadowOffset, (height-th)/2-.5+shadowOffset) 

	def SetBitmap(self, bitmap):
		self._bitmap = bitmap

	def SetBitmapDisabled(self, bitmap):
		self._bitmapdisabled = bitmap

	def SetBitmapFocus(self, bitmap):
		self._bitmapfocus = bitmap

	def SetBitmapHover(self, bitmap):
		self._bitmaphover = bitmap

	def SetBitmapSelected(self, bitmap):
		self._bitmapselected = bitmap


class CustomGrid(wx.grid.Grid):

	def __init__(self, *args, **kwargs):
		wx.grid.Grid.__init__(self, *args, **kwargs)
		self.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
		self.Bind(wx.EVT_SIZE, self.OnResize)
		self.Bind(wx.grid.EVT_GRID_ROW_SIZE, self.OnResize)
		self.Bind(wx.grid.EVT_GRID_COL_SIZE, self.OnResize)
		self.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.OnCellLeftClick)
		self.Bind(wx.grid.EVT_GRID_CELL_LEFT_DCLICK, self.OnCellLeftClick)
		self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
		self.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.OnCellSelect)
		self.Bind(wx.grid.EVT_GRID_LABEL_LEFT_CLICK, self.OnLabelLeftClick)
		self.GetGridCornerLabelWindow().Bind(wx.EVT_PAINT, self.OnPaintCornerLabel)
		self.GetGridColLabelWindow().Bind(wx.EVT_PAINT, self.OnPaintColLabels)
		self.GetGridRowLabelWindow().Bind(wx.EVT_PAINT, self.OnPaintRowLabels)
		self.SetDefaultCellAlignment(wx.ALIGN_LEFT, wx.ALIGN_CENTER)
		self.SetDefaultCellBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))
		self.SetDefaultEditor(CustomCellEditor(self))
		self._default_cell_renderer = CustomCellRenderer()
		self.SetDefaultRenderer(self._default_cell_renderer)
		self.SetRowLabelAlignment(wx.ALIGN_CENTER, wx.ALIGN_CENTER)

		self.headerbitmap = None
		if sys.platform == "darwin":
			# wxMac draws a too short native header
			self.rendernative = False
			self.style = "Mavericks"
		else:
			self.rendernative = True
			self.style = ""
		self._default_col_label_renderer = CustomColLabelRenderer()
		self._default_row_label_renderer = CustomRowLabelRenderer()
		self._col_label_renderers = {}
		self._overwrite_cell_values = True
		self._row_label_renderers = {}
		self.alternate_cell_background_color = True
		self.alternate_col_label_background_color = False
		self.alternate_row_label_background_color = True
		self.draw_col_labels = True
		self.draw_row_labels = True
		self.draw_horizontal_grid_lines = True
		self.draw_vertical_grid_lines = True
		self.selection_alpha = 1.0
		self.show_cursor_outline = True

	if not hasattr(wx.grid.Grid, "CalcCellsExposed"):
		# wxPython < 2.8.10
		def CalcCellsExposed(self, region):
			rows = self.CalcRowLabelsExposed(region)
			cols = self.CalcColLabelsExposed(region)
			cells = []
			for row in rows:
				for col in cols:
					if row > -1 and col > -1:
						cells.append((row, col))
			return cells

	if not hasattr(wx.grid.Grid, "CalcColLabelsExposed"):
		# wxPython < 2.8.10
		def CalcColLabelsExposed(self, region):
			x, y = self.CalcUnscrolledPosition((0,0))
			ri = wx.RegionIterator(region)
			cols = []
			while ri:
				rect = ri.GetRect()
				rect.Offset((x,0))
				colPos = self.GetColPos(self.XToCol(rect.left))
				while colPos < self.GetNumberCols() and colPos >= 0:
					col = self.GetColAt(colPos)
					cl, cr = self.GetColLeftRight(col)
					if cr < rect.left:
						continue
					if cl > rect.right:
						break
					cols.append(col)
					colPos += 1
				ri.Next()
			return cols

	if not hasattr(wx.grid.Grid, "CalcRowLabelsExposed"):
		# wxPython < 2.8.10
		def CalcRowLabelsExposed(self, region):
			x, y = self.CalcUnscrolledPosition((0,0))
			ri = wx.RegionIterator(region)
			rows = []
			while ri:
				rect = ri.GetRect()
				rect.Offset((0,y))
				row = self.YToRow(rect.top)
				while row < self.GetNumberRows() and row >= 0:
					rt, rb = self.GetRowTopBottom(row)
					if rb < rect.top:
						continue
					if rt > rect.bottom:
						break
					rows.append(row)
					row += 1
				ri.Next()
			return rows

	def GetColLeftRight(self, col, c=0):
		left = 0
		while c < col:
			left += self.GetColSize(c)
			c += 1
		right = left + self.GetColSize(col) - 1
		return left, right

	def GetRowTopBottom(self, row, r=0):
		top = 0
		while r < row:
			top += self.GetRowSize(r)
			r += 1
		bottom = top + self.GetRowSize(row) - 1
		return top, bottom

	def OnCellLeftClick(self, event):
		if (event.CmdDown() or event.ControlDown() or event.ShiftDown() or
			not isinstance(self.GetCellEditor(self.GetGridCursorRow(),
											   self.GetGridCursorCol()),
							CustomCellEditor)):
			event.Skip()
		else:
			self.SetGridCursor(event.Row, event.Col)

	def OnCellSelect(self, event):
		row, col = event.GetRow(), event.GetCol()
		self._anchor_row = row
		self._overwrite_cell_values = True
		self.SelectBlock(event.Row, event.Col, event.Row, event.Col)
		self.Refresh()
		event.Skip()

	def OnKeyDown(self, event):
		keycode = event.KeyCode
		if event.CmdDown() or event.ControlDown():
			# CTRL (Linux/Mac/Windows) / CMD (Mac)
			if keycode == 65:
				# A
				self.SelectAll()
				return
			elif keycode in (67, 88):
				# C / X
				clip = []
				cells = self.GetSelection()
				i = -1
				start_col = self.GetNumberCols()
				for cell in cells:
					row = cell[0]
					col = cell[1]
					if i < row:
						clip.append([])
						i = row
						offset = 0
					# Skip cols without label
					if self.GetColLabelSize() and not self.GetColLabelValue(col):
						offset += 1
						continue
					if col - offset < start_col:
						start_col = col - offset
					while len(clip[-1]) - 1 < col - offset:
						clip[-1].append("")
					clip[-1][col - offset] = self.GetCellValue(row, col)
				for i, row in enumerate(clip):
					clip[i] = "\t".join(row[start_col:])
				clipdata = wx.TextDataObject()
				clipdata.SetText("\n".join(clip))
				wx.TheClipboard.Open()
				wx.TheClipboard.SetData(clipdata)
				wx.TheClipboard.Close()
				return
			elif keycode == 86 and self.IsEditable():
				# V
				do = wx.TextDataObject()
				wx.TheClipboard.Open()
				success = wx.TheClipboard.GetData(do)
				wx.TheClipboard.Close()
				if success:
					lines = do.GetText().splitlines()
					for i, line in enumerate(lines):
						lines[i] = re.sub(" +", "\t", line).split("\t")
					# Translate from selected cells into a grid with None values
					# for not selected cells
					grid = []
					cells = self.GetSelection()
					i = -1
					start_col = self.GetNumberCols()
					for cell in cells:
						row = cell[0]
						col = cell[1]
						if i < row:
							grid.append([])
							i = row
							offset = 0
						# Skip read-only cells and cols without label
						if (self.IsReadOnly(row, col) or
							(self.GetColLabelSize() and
							 not self.GetColLabelValue(col))):
							offset += 1
							continue
						if col - offset < start_col:
							start_col = col - offset
						while len(grid[-1]) - 1 < col - offset:
							grid[-1].append(None)
						grid[-1][col - offset] = cell
					for i, row in enumerate(grid):
						grid[i] = row[start_col:]
					# 'Paste' values from clipboard
					self.BeginBatch()
					for i, row in enumerate(grid):
						for j, cell in enumerate(row):
							if (cell is not None and len(lines) > i and
								len(lines[i]) > j):
								self.SetCellValue(cell[0], cell[1], lines[i][j])
								self.ProcessEvent(wx.grid.GridEvent(-1,
																	wx.grid.EVT_GRID_CELL_CHANGE.evtType[0],
																	self,
																	cell[0],
																	cell[1]))
					self.EndBatch()
				return
		elif self.IsEditable() and not self.IsCurrentCellReadOnly():
			if isinstance(self.GetCellEditor(self.GetGridCursorRow(),
											 self.GetGridCursorCol()),
						  CustomCellEditor):
				ch = None
				if keycode in [wx.WXK_NUMPAD0, wx.WXK_NUMPAD1, wx.WXK_NUMPAD2,
							   wx.WXK_NUMPAD3, wx.WXK_NUMPAD4, wx.WXK_NUMPAD5,
							   wx.WXK_NUMPAD6, wx.WXK_NUMPAD7, wx.WXK_NUMPAD8,
							   wx.WXK_NUMPAD9]:
					ch = chr(ord('0') + keycode - wx.WXK_NUMPAD0)
				elif keycode in (wx.WXK_NUMPAD_DECIMAL,
								 wx.WXK_NUMPAD_SEPARATOR):
					ch = "."
				elif keycode < 256 and keycode >= 32:
					ch = safe_unicode(chr(keycode))
				if ch is not None or keycode in (wx.WXK_BACK, wx.WXK_DELETE):
					changed = 0
					batch = False
					for i, (row, col) in enumerate(self.GetSelection()):
						if row > -1 and col > -1 and not self.IsReadOnly(row, col):
							if changed and not batch:
								self.BeginBatch()
								batch = True
							if (self._overwrite_cell_values or
								keycode == wx.WXK_DELETE):
								value = ""
							else:
								value = self.GetCellValue(row, col)
							if keycode == wx.WXK_BACK:
								value = value[:-1]
							elif keycode != wx.WXK_DELETE:
								value += ch
							self.SetCellValue(row, col, value)
							self.ProcessEvent(wx.grid.GridEvent(-1,
																wx.grid.EVT_GRID_CELL_CHANGE.evtType[0],
																self,
																row,
																col))
							changed += 1
					if batch:
						self.EndBatch()
					self._overwrite_cell_values = False
					if not changed:
						wx.Bell()
					return
			elif (event.KeyCode == wx.WXK_RETURN or
				  event.KeyCode == wx.WXK_NUMPAD_ENTER):
				self.EnableCellEditControl()
				return
		event.Skip()

	def OnKillFocus(self, event):
		self.Refresh()
		event.Skip()

	def OnLabelLeftClick(self, event):
		row, col = event.GetRow(), event.GetCol()
		if row == -1 and col > -1:
			# Col label clicked
			self.SetFocus()
			self.SetGridCursor(max(self.GetGridCursorRow(), 0), col)
			self.MakeCellVisible(max(self.GetGridCursorRow(), 0), col)
		elif col == -1 and row > -1:
			# Row label clicked
			if self.select_row(row, event.ShiftDown(),
							   event.ControlDown() or event.CmdDown()):
				return
		event.Skip()

	def OnPaintColLabels(self, evt):
		window = evt.GetEventObject()
		dc = wx.PaintDC(window)

		cols = self.CalcColLabelsExposed(window.GetUpdateRegion())
		if cols == [-1]:
			return

		x, y = self.CalcUnscrolledPosition((0,0))
		pt = dc.GetDeviceOrigin()
		dc.SetDeviceOrigin(pt.x-x, pt.y)
		leftoffset = 0
		for i, col in enumerate(cols):
			left, right = self.GetColLeftRight(col, cols[0] if i > 0 else 0)
			if i > 0:
				left += leftoffset
				right += leftoffset
			else:
				leftoffset = left
			rect = wx.Rect()
			rect.left = left
			rect.right = right
			rect.y = 0
			rect.height = self.GetColLabelSize()

			renderer = self._col_label_renderers.get(col,
													 self._default_col_label_renderer)

			renderer.Draw(self, dc, rect, col)

	def OnPaintCornerLabel(self, evt):
		window = evt.GetEventObject()
		dc = wx.PaintDC(window)

		rect = wx.Rect()
		rect.width = self.GetRowLabelSize()
		rect.height = self.GetColLabelSize()
		rect.x = 0
		rect.y = 0
		self._default_col_label_renderer.Draw(self, dc, rect)

	def OnPaintRowLabels(self, evt):
		window = evt.GetEventObject()
		dc = wx.PaintDC(window)

		rows = self.CalcRowLabelsExposed(window.GetUpdateRegion())
		if rows == [-1]:
			return

		x, y = self.CalcUnscrolledPosition((0,0))
		pt = dc.GetDeviceOrigin()
		dc.SetDeviceOrigin(pt.x, pt.y-y)
		topoffset = 0
		for i, row in enumerate(rows):
			top, bottom = self.GetRowTopBottom(row, rows[0] if i > 0 else 0)
			if i > 0:
				top += topoffset
				bottom += topoffset
			else:
				topoffset = top
			rect = wx.Rect()
			rect.top = top
			rect.bottom = bottom
			rect.x = 0
			rect.width = self.GetRowLabelSize()

			renderer = self._row_label_renderers.get(row,
													 self._default_row_label_renderer)

			renderer.Draw(self, dc, rect, row)

	def OnResize(self, event):
		region = wx.Region(*self.ClientRect.Get())
		for row, col in self.CalcCellsExposed(region):
			cell_renderer = self.GetCellRenderer(row, col)
			if (isinstance(cell_renderer, CustomCellRenderer) and
				cell_renderer._selectionbitmaps):
				# On resize, we need to tell any CustomCellRenderer that its
				# bitmaps are no longer valid and are garbage collected
				cell_renderer._selectionbitmaps = {}
		event.Skip()
        
	def SetColLabelRenderer(self, renderer):
		"""
		Register a renderer to be used for drawing the label for the
		given column.
		"""
		if renderer is None:
			if col in self._col_label_renderers:
				del self._col_label_renderers[col]
		else:
			self._col_label_renderers[col] = renderer

	def SetDefaultCellBackgroundColour(self, color):
		# Set alpha to 0 so we can detect the default color
		if not isinstance(color, wx.Colour):
			color_str = color
			color = wx.Colour()
			if hasattr(wx.Colour, "SetFromString"):
				color.SetFromString(color_str)
			else:
				color.SetFromName(color_str)
		color.Set(color.Red(), color.Green(), color.Blue(), 0)
		wx.grid.Grid.SetDefaultCellBackgroundColour(self, color)

	def SetRowLabelRenderer(self, row, renderer):
		"""
		Register a renderer to be used for drawing the label for the
		given row.
		"""
		if renderer is None:
			if row in self._row_label_renderers:
				del self._row_label_renderers[row]
		else:
			self._row_label_renderers[row] = renderer

	def select_row(self, row, shift=False, ctrl=False):
		self.SetFocus()
		if not shift and not ctrl:
			self.SetGridCursor(row, max(self.GetGridCursorCol(), 0))
			self.SelectRow(row)
			self._anchor_row = row
		self.MakeCellVisible(row, max(self.GetGridCursorCol(), 0))
		if self.IsSelection():
			if shift:
				self.BeginBatch()
				rows = self.GetSelectionRows()
				sel = range(min(self._anchor_row, row),
							max(self._anchor_row, row) + 1)
				desel = []
				add = []
				for i in rows:
					if i not in sel:
						desel.append(i)
				for i in sel:
					if i not in rows:
						add.append(i)
				if len(desel) >= len(add):
					# in this case deselecting rows will take as long or longer than selecting, so use SelectRow to speed up the operation
					self.SelectRow(row)
				else:
					for i in desel:
						self.DeselectRow(i)
				for i in add:
					self.SelectRow(i, True)
				self.EndBatch()
				return False
			elif ctrl:
				if self.IsInSelection(row, 0):
					self.DeselectRow(row)
					return True
				else:
					self.SelectRow(row, True)
		return False


class CustomCheckBox(wx.Panel):

	"""
	A custom checkbox where the label is independent from the checkbox itself.
	
	Works around wxMac not taking into account text (foreground) color on
	a default checkbox label.
	
	"""

	def __init__(self, parent, id=wx.ID_ANY, label="", pos=wx.DefaultPosition,
				 size=wx.DefaultSize, style=wx.NO_BORDER,
				 validator=wx.DefaultValidator, name="CustomCheckBox"):
		wx.Panel.__init__(self, parent, id, pos, size, style, name)
		self.BackgroundColour = parent.BackgroundColour
		self.SetSizer(wx.BoxSizer(wx.HORIZONTAL))
		self._cb = wx.CheckBox(self, -1)
		self._enabled = True
		self.Sizer.Add(self._cb, flag=wx.ALIGN_CENTER_VERTICAL)
		if sys.platform == "darwin":
			self._label = wx.StaticText(self, -1, "")
			self.Sizer.Add(self._label, 1, wx.ALIGN_CENTER_VERTICAL)
			self._label.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
			self._label.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
			self._up = True
		else:
			self._label = self._cb
		self._label.Label = label

	def Bind(self, event_id, handler):
		self._cb.Bind(event_id, handler)

	def Disable(self):
		self.Enable(False)

	def Enable(self, enable=True):
		self._enabled = enable
		self._cb.Enable(enable)
		if self._label is not self._cb:
			color = self.ForegroundColour
			if not enable:
				bgcolor = self.Parent.BackgroundColour
				bgblend = .5
				blend = .5
				color = wx.Colour(int(round(bgblend * bgcolor.Red() +
											blend * color.Red())),
								  int(round(bgblend * bgcolor.Green() +
											blend * color.Green())),
								  int(round(bgblend * bgcolor.Blue() +
											blend * color.Blue())))
			self._label.ForegroundColour = color

	@Property
	def Enabled():
		def fget(self):
			return self.IsEnabled()

		def fset(self, enable=True):
			self.Enable(enable)

		return locals()

	def IsEnabled(self):
		return self._enabled

	def OnLeftDown(self, event):
		if not self.Enabled:
			return
		self._up = False
		self._cb.SetFocus()
		event.Skip()

	def OnLeftUp(self, event):
		if not self.Enabled:
			return
		if not self._up and self.ClientRect.Contains(event.GetPosition()):
			# if the checkbox was down when the mouse was released...
			self.SendCheckBoxEvent()
		self._up = True

	def SendCheckBoxEvent(self):
		""" Actually sends the event to the checkbox. """
		
		self.Value = not self.Value
		checkEvent = wx.CommandEvent(wx.wxEVT_COMMAND_CHECKBOX_CLICKED,
									 self._cb.GetId())
		checkEvent.SetInt(int(self.Value))

		# Set the originating object for the event (the checkbox)
		checkEvent.SetEventObject(self._cb)

		# Watch for a possible listener of this event that will catch it and
		# eventually process it
		self._cb.GetEventHandler().ProcessEvent(checkEvent)

	def SetMaxFontSize(self, pointsize=11):
		self._label.SetMaxFontSize(pointsize)

	def GetValue(self):
		"""
		Returns the state of CustomCheckBox, True if checked, False
		otherwise.
		"""

		return self._cb.Value

	def IsChecked(self):
		"""
		This is just a maybe more readable synonym for GetValue: just as the
		latter, it returns True if the CustomCheckBox is checked and False
		otherwise.
		"""

		return self._cb.Value

	def SetValue(self, state):
		"""
		Sets the CustomCheckBox to the given state. This does not cause a
		wx.wxEVT_COMMAND_CHECKBOX_CLICKED event to get emitted.
		"""

		self._cb.Value = state

	def GetLabel(self):
		return self._label.Label

	def SetLabel(self, label):
		self._label.Label = label

	def SetForegroundColour(self, color):
		wx.Panel.SetForegroundColour(self, color)
		self._label.ForegroundColour = color

	@Property
	def Label():
		def fget(self):
			return self.GetLabel()

		def fset(self, label):
			self.SetLabel(label)

		return locals()

	@Property
	def Value():
		def fget(self):
			return self.GetValue()

		def fset(self, state):
			self.SetValue(state)

		return locals()

	@Property
	def ForegroundColour():
		def fget(self):
			return self.GetForegroundColour()

		def fset(self, color):
			self.SetForegroundColour(color)

		return locals()


class CustomCellEditor(wx.grid.PyGridCellEditor):

	def __init__(self, grid):
		wx.grid.PyGridCellEditor.__init__(self)
		self._grid = grid
		self._cell_renderer = CustomCellRenderer()

	def Create(self, parent, id, evtHandler):
		"""
		Called to create the control, which must derive from wx.Control.
		"""
		safe_print("CustomCellEditor.Create(%r, %r, %r) was called. This "
				   "should not happen, but is unlikely an issue." %
				   (parent, id, evtHandler))
		self.SetControl(wx.StaticText(parent, -1, ""))

	def SetSize(self, rect):
		"""
		Called to position/size the edit control within the cell rectangle.
		If you don't fill the cell (the rect) then be sure to override
		PaintBackground and do something meaningful there.
		"""
		safe_print("CustomCellEditor.SetSize(%r) was called. This should not "
				   "happen, but is unlikely an issue." % rect)
		self.Control.SetDimensions(rect.x, rect.y, rect.width, rect.height,
							   wx.SIZE_ALLOW_MINUS_ONE)

	def Show(self, show, attr):
		"""
		Show or hide the edit control.  You can use the attr (if not None)
		to set colours or fonts for the control.
		"""
		safe_print("CustomCellEditor.Show(%r, %r) was called. This should "
				   "not happen, but is unlikely an issue." % (show, attr))
		super(self.__class__, self).Show(show, attr)

	def PaintBackground(self, dc, rect, attr=None):
		"""
		Draws the part of the cell not occupied by the edit control.  The
		base  class version just fills it with background colour from the
		attribute.  In this class the edit control fills the whole cell so
		don't do anything at all in order to reduce flicker.
		"""
		self._cell_renderer.Draw(self._grid, attr, dc, rect,
								 self._grid.GetGridCursorRow(),
								 self._grid.GetGridCursorCol(), True)

	def BeginEdit(self, row, col, grid):
		"""
		Fetch the value from the table and prepare the edit control
		to begin editing.  Set the focus to the edit control.
		"""
		safe_print("CustomCellEditor.BeginEdit(%r, %r, %r) was called. This "
				   "should not happen, but is unlikely an issue." %
				   (row, col, grid))

	def EndEdit(self, row, col, grid, value=None):
		"""
		Complete the editing of the current cell. Returns True if the value
		has changed.  If necessary, the control may be destroyed.
		"""
		safe_print("CustomCellEditor.EndEdit(%r, %r, %r, %r) was called. This "
				   "should not happen, but is unlikely an issue." %
				   (row, col, grid, value))
		if wx.VERSION >= (2, 9):
			changed = None
		else:
			changed = False
		return changed

	def Reset(self):
		"""
		Reset the value in the control back to its starting value.
		"""
		safe_print("CustomCellEditor.Reset() was called. This should "
				   "not happen, but is unlikely an issue.")

	def IsAcceptedKey(self, evt):
		"""
		Return True to allow the given key to start editing: the base class
		version only checks that the event has no modifiers.  F2 is special
		and will always start the editor.
		"""
		return False

	def StartingKey(self, evt):
		"""
		If the editor is enabled by pressing keys on the grid, this will be
		called to let the editor do something about that first key if desired.
		"""
		safe_print("CustomCellEditor.StartingKey(%r) was called. This should "
				   "not happen, but is unlikely an issue." % evt)
		evt.Skip()

	def StartingClick(self):
		"""
		If the editor is enabled by clicking on the cell, this method will be
		called to allow the editor to simulate the click on the control if
		needed.
		"""

	def Destroy(self):
		"""final cleanup"""
		super(self.__class__, self).Destroy()

	def Clone(self):
		"""
		Create a new object which is the copy of this one
		*Must Override*
		"""
		return self.__class__()


class CustomCellRenderer(wx.grid.PyGridCellRenderer):

	def __init__(self, *args, **kwargs):
		wx.grid.PyGridCellRenderer.__init__(self)
		self.specialbitmap = getbitmap("theme/checkerboard-10x10x2-333-444")
		self._selectionbitmaps = {}

	def Clone(self):
		return self.__class__()

	def Draw(self, grid, attr, dc, rect, row, col, isSelected):
		orect = rect
		#if col == grid.GetNumberCols() - 1:
			## Last column
			#w = max(grid.ClientSize[0] - rect[0], rect[2])
			#rect = wx.Rect(rect[0], rect[1], w, rect[3])
		bgcolor = grid.GetCellBackgroundColour(row, col)
		col_label = grid.GetColLabelValue(col)
		is_default_bgcolor = bgcolor == grid.GetDefaultCellBackgroundColour()
		is_read_only = grid.IsReadOnly(row, col)
		if is_default_bgcolor:
			if (is_read_only or not grid.IsEditable()) and col_label:
				bgcolor = grid.GetLabelBackgroundColour()
			if row % 2 == 0 and grid.alternate_cell_background_color:
				bgcolor = wx.Colour(*[int(v * .98) for v in bgcolor])
			elif bgcolor.Alpha() < 255:
				# Make sure it's opaque
				bgcolor = wx.Colour(bgcolor.Red(), bgcolor.Green(),
									bgcolor.Blue())
		special = bgcolor.Get(True) == (0, 0, 0, 0)
		mavericks = getattr(grid, "style", None) == "Mavericks"
		if (not special and mavericks and bgcolor.Red() < 255):
			# Use Mavericks-like color scheme
			newcolor = [int(round(min(bgcolor.Get()[i] * (v / 102.0), 255)))
						for i, v in enumerate((98, 100, 102))]
			bgcolor.Set(*newcolor)
		rowselect = grid.GetSelectionMode() == wx.grid.Grid.wxGridSelectRows
		isCursor = (grid.show_cursor_outline and
					((row, col) == (grid.GetGridCursorRow(),
									grid.GetGridCursorCol()) or
					 (rowselect and row == grid.GetGridCursorRow())))
		if (isSelected or isCursor) and is_default_bgcolor and col_label:
			color = grid.GetSelectionBackground()
			if isSelected:
				textcolor = grid.GetSelectionForeground()
			else:
				textcolor = grid.GetCellTextColour(row, col)
			focus = grid.Parent.FindFocus()
			if not focus or grid not in (focus, focus.GetParent(),
										 focus.GetGrandParent()):
				if mavericks or sys.platform == "darwin":
					# Use Mavericks-like color scheme
					color = wx.Colour(202, 202, 202)
					if isSelected:
						textcolor = wx.Colour(51, 51, 51)
				else:
					rgb = int((color.Red() + color.Green() + color.Blue()) / 3.0)
					color = wx.Colour(rgb, rgb, rgb)
			elif mavericks or sys.platform == "darwin":
				# Use Mavericks-like color scheme
				color = wx.Colour(44, 93, 205)
				if isSelected:
					textcolor = wx.WHITE
			else:
				alpha = (grid.selection_alpha * 255 or
						 grid.GetSelectionBackground().Alpha())
				# Blend with bg color
				if alpha < 255:
					# Alpha blending
					bgblend = (255 - alpha) / 255.0
					blend = alpha / 255.0
					color = wx.Colour(int(round(bgblend * bgcolor.Red() +
												blend * color.Red())),
									  int(round(bgblend * bgcolor.Green() +
												blend * color.Green())),
									  int(round(bgblend * bgcolor.Blue() +
												blend * color.Blue())))
		else:
			color = bgcolor
			textcolor = grid.GetCellTextColour(row, col)
		if special:
			# Special
			image = self.specialbitmap.ConvertToImage()
			image.Rescale(rect[2], rect[3])
			dc.DrawBitmap(image.ConvertToBitmap(), rect[0], rect[1])
		else:
			if (isSelected or isCursor) and col_label:
				dc.SetBrush(wx.Brush(bgcolor))
				dc.SetPen(wx.TRANSPARENT_PEN)
				dc.DrawRectangleRect(rect)
				rect = orect
				if not rowselect:
					w = 60 + rect[3] * 2
					if rect.Width > w:
						rect.Left += (rect.Width - w) / 2.0
						rect.Width = w
				offset = 1  # Selection offset from cell boundary
				cb = 2  # Cursor border
				left = (not rowselect or
						col == 0 or not grid.GetColLabelValue(col - 1))
				right = (not rowselect or
						 col == grid.GetNumberCols() - 1 or
						 not grid.GetColLabelValue(col + 1))
				# We could use wx.GCDC, but it is buggy under wxGTK
				# (grid doesn't refresh properly when scrolling).
				# Implement our own supersampling antialiasing method
				# using wx.MemoryDC and cached bitmaps.
				# This has the drawback that it may use a lot of memory if
				# a grid has many cells with different dimensions or color
				# properties, but we make sure that old bitmaps are garbage
				# collected if the grid or rows/cols are resized by binding
				# resize events in CustomGrid initialization.
				key = rect[2:] + bgcolor.Get() + color.Get() + (left, right,
																not isSelected
																and isCursor)
				if not self._selectionbitmaps.get(key):
					scale = 4.0  # Supersampling factor
					offset *= scale
					cb *= scale
					x, y, w, h = 0, 0, rect[2] * scale, rect[3] * scale
					self._selectionbitmaps[key] = wx.EmptyBitmap(w, h)
					paintdc = dc
					dc = mdc = wx.MemoryDC(self._selectionbitmaps[key])
					dc.SetBrush(wx.Brush(bgcolor))
					dc.SetPen(wx.TRANSPARENT_PEN)
					dc.DrawRectangle(x, y, w, h)
					dc.SetBrush(wx.Brush(color))
					dc.SetPen(wx.TRANSPARENT_PEN)
					draw = dc.DrawRoundedRectangle
					draw(x + offset, y + offset, w - offset * 2,
						 h - offset * 2, h / 2.0 - offset)
					if not left:
						dc.DrawRectangle(x, y + offset, h / 2.0,
										 h - offset * 2)
					if not right:
						dc.DrawRectangle(x + w - h / 2.0, y + offset, h / 2.0,
										 h - offset * 2)
					if not isSelected and isCursor:
						dc.SetBrush(wx.Brush(bgcolor))
						draw(x + offset + cb, y + offset + cb,
							 w - (offset + cb) * 2, h - (offset + cb) * 2,
							 h / 2.0 - (offset + cb))
						if not left:
							dc.DrawRectangle(x, y + offset + cb, h / 2.0,
											 h - (offset + cb) * 2)
						if not right:
							dc.DrawRectangle(x + w - h / 2.0, y + offset + cb,
											 h / 2.0, h - (offset + cb) * 2)
					mdc.SelectObject(wx.NullBitmap)
					dc = paintdc
					img = self._selectionbitmaps[key].ConvertToImage()
					# Scale down to original size ("antialiasing")
					img.Rescale(rect[2], rect[3])
					self._selectionbitmaps[key] = img.ConvertToBitmap()
				bmp = self._selectionbitmaps.get(key)
				if bmp:
					dc.DrawBitmap(bmp, rect[0], rect[1])
			else:
				dc.SetBrush(wx.Brush(color))
				dc.SetPen(wx.TRANSPARENT_PEN)
				dc.DrawRectangleRect(rect)
		dc.SetFont(grid.GetCellFont(row, col))
		dc.SetTextForeground(textcolor)
		self.DrawLabel(grid, dc, orect, row, col)

	def DrawLabel(self, grid, dc, rect, row, col):
		align = grid.GetCellAlignment(row, col)
		if align[1] == wx.ALIGN_CENTER:
			align = align[0], wx.ALIGN_CENTER_VERTICAL
		dc.DrawLabel(grid.GetCellValue(row, col), rect,
					 align[0] | align[1])

	def GetBestSize(self, grid, attr, dc, row, col):
		dc.SetFont(grid.GetCellFont(row, col))
		return dc.GetTextExtent(grid.GetCellValue(row, col))


class CustomCellBoolRenderer(CustomCellRenderer):

	def __init__(self, *args, **kwargs):
		CustomCellRenderer.__init__(self)
		self._bitmap = geticon(16, "checkmark")
		self._bitmap_unchecked = geticon(16, "x")

	def DrawLabel(self, grid, dc, rect, row, col):
		if grid.GetCellValue(row, col) == "1":
			bitmap = self._bitmap
		else:
			bitmap = self._bitmap_unchecked
		x = rect[0] + int((rect[2] - self._bitmap.Size[0]) / 2.0)
		y = rect[1] + int((rect[3] - self._bitmap.Size[1]) / 2.0)
		dc.DrawBitmap(bitmap, x, y)

	def GetBestSize(self, grid, attr, dc, row, col):
		return self._bitmap.Size


class CustomColLabelRenderer(object):

	def __init__(self, bgcolor=None):
		self.bgcolor = bgcolor

	def Draw(self, grid, dc, rect, col=-1):
		if not grid.GetNumberCols():
			return
		orect = rect
		if col == grid.GetNumberCols() - 1:
			# Last column
			w = max(grid.ClientSize[0] - rect[0], rect[2])
			rect = wx.Rect(rect[0], rect[1], w, rect[3])
		mavericks = (getattr(grid, "style", None) == "Mavericks" or
					 sys.platform == "darwin")
		if grid.headerbitmap:
			img = grid.headerbitmap.ConvertToImage()
			img.Rescale(rect[2], rect[3], quality=wx.IMAGE_QUALITY_NORMAL)
			dc.DrawBitmap(img.ConvertToBitmap(), rect[0], 0)
			pen = wx.Pen(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DSHADOW), 1,
						 wx.SOLID)
			pen.SetCap(wx.CAP_BUTT)
			dc.SetPen(pen)
			dc.DrawLine(rect[0], rect[1] + rect[3] - 1, rect[0] + rect[2],
						rect[1] + rect[3] - 1)
		elif grid.rendernative:
			render = wx.RendererNative.Get()
			render.DrawHeaderButton(grid, dc, rect)
		else:
			if self.bgcolor:
				color = self.bgcolor
			else:
				if mavericks:
					# Use Mavericks-like color scheme
					color = wx.Colour(255, 255, 255)
				else:
					color = grid.GetLabelBackgroundColour()
				if col % 2 == 0 and grid.alternate_col_label_background_color:
					color = wx.Colour(*[int(v * .98) for v in color])
				elif color.Alpha() < 255:
					# Make sure it's opaque
					color = wx.Colour(color.Red(), color.Green(), color.Blue())
			dc.SetBrush(wx.Brush(color))
			dc.SetPen(wx.TRANSPARENT_PEN)
			dc.DrawRectangleRect(rect)
			pen = wx.Pen(grid.GetGridLineColour())
			dc.SetPen(pen)
			if getattr(grid, "draw_horizontal_grid_lines", True) or (mavericks and
																	 not self.bgcolor):
				dc.DrawLine(rect[0], rect[1] + rect[3] - 1, rect[0] + rect[2] - 1,
							rect[1] + rect[3] - 1)
			if getattr(grid, "draw_vertical_grid_lines", True):
				dc.DrawLine(rect[0] + rect[2] - 1, rect[1],
							rect[0] + rect[2] - 1, rect[3])
		if getattr(grid, "draw_col_labels", True) and col > -1:
			dc.SetFont(grid.GetLabelFont())
			if mavericks and not self.bgcolor:
				# Use Mavericks-like color scheme
				color = wx.Colour(80, 100, 120)
			else:
				color = grid.GetLabelTextColour()
			dc.SetTextForeground(color)
			align = grid.GetColLabelAlignment()
			if align[1] == wx.ALIGN_CENTER:
				align = align[0], wx.ALIGN_CENTER_VERTICAL
			dc.DrawLabel(" %s " % grid.GetColLabelValue(col), orect,
						 align[0] | align[1])


class CustomRowLabelRenderer(object):

	def __init__(self, bgcolor=None):
		self.bgcolor = bgcolor

	def Draw(self, grid, dc, rect, row):
		if self.bgcolor:
			color = self.bgcolor
		else:
			color = grid.GetLabelBackgroundColour()
			if row % 2 == 0 and grid.alternate_row_label_background_color:
				color = wx.Colour(*[int(v * .98) for v in color])
			elif color.Alpha() < 255:
				# Make sure it's opaque
				color = wx.Colour(color.Red(), color.Green(), color.Blue())
			if getattr(grid, "style", None) == "Mavericks" and color.Red() < 255:
				# Use Mavericks-like color scheme
				newcolor = [int(round(color.Get()[i] * (v / 102.0)))
							for i, v in enumerate((98, 100, 102))]
				color.Set(*newcolor)
		dc.SetBrush(wx.Brush(color))
		dc.SetPen(wx.TRANSPARENT_PEN)
		dc.DrawRectangleRect(rect)
		pen = wx.Pen(grid.GetGridLineColour())
		dc.SetPen(pen)
		if getattr(grid, "draw_horizontal_grid_lines", True):
			dc.DrawLine(rect[0], rect[1] + rect[3] - 1, rect[0] + rect[2] - 1,
						rect[1] + rect[3] - 1)
		if getattr(grid, "draw_vertical_grid_lines", True):
			dc.DrawLine(rect[0] + rect[2] - 1, rect[1], rect[0] + rect[2] - 1,
						rect[3])
		if getattr(grid, "draw_row_labels", True):
			dc.SetFont(grid.GetLabelFont())
			dc.SetTextForeground(grid.GetLabelTextColour())
			align = grid.GetRowLabelAlignment()
			if align[1] == wx.ALIGN_CENTER:
				align = align[0], wx.ALIGN_CENTER_VERTICAL
			dc.DrawLabel(" %s " % grid.GetRowLabelValue(row), rect,
						 align[0] | align[1])


class HStretchStaticBitmap(wx.StaticBitmap):

	"""
	A StaticBitmap that will automatically stretch horizontally.
	
	To be used with sizers.
	
	"""

	def __init__(self, *args, **kwargs):
		wx.StaticBitmap.__init__(self, *args, **kwargs)
		if sys.platform in ("darwin", "win32"):
			# Works (only) under Mac OS X / Windows.
			# Works better (no jump to correct width) under Mac OS X than
			# EVT_SIZE method.
			self.Bind(wx.EVT_PAINT, self.OnPaint)
		else:
			# Works under Mac OS X, Windows and Linux.
			# Under Mac OS X, this visibly jumps to the correct width when
			# first shown on screen.
			self.Bind(wx.EVT_SIZE, self.OnPaint)
		self._init = False

	def OnPaint(self, event):
		if self.GetBitmap() and self.GetBitmap().IsOk():
			if hasattr(self, "_bmp"):
				bmp = self._bmp
			else:
				bmp = self.GetBitmap()
				self._bmp = bmp
			w = self.Size[0]
			if getattr(self, "_width", -1) != w:
				img = bmp.ConvertToImage()
				img.Rescale(w, img.GetSize()[1])
				bmp = img.ConvertToBitmap()
				self._width = w
				# Avoid flicker under Windows
				if self._init:
					self.Freeze()
				self.SetBitmap(bmp)
				self.MinSize = self._bmp.GetSize()
				if self._init:
					self.Thaw()
				elif self.IsShownOnScreen():
					self._init = True
		if event:
			event.Skip()


class HyperLinkCtrl(wx.HyperlinkCtrl):

	def __init__(self, parent, id=wx.ID_ANY, label="",
				 pos=wx.DefaultPosition, size=wx.DefaultSize,
				 style=wx.HL_DEFAULT_STYLE, name=wx.HyperlinkCtrlNameStr, URL=""):
		wx.HyperlinkCtrl.__init__(self, parent, id, label, URL, pos, size,
								  style, name)


class BetterLinkCtrl(wx.StaticText):

	""" HyperLinkCtrl colors can't be chnaged under Windows """

	def __init__(self, parent, id=wx.ID_ANY, label="",
				 pos=wx.DefaultPosition, size=wx.DefaultSize,
				 style=wx.HL_DEFAULT_STYLE, name=wx.HyperlinkCtrlNameStr, URL=""):
		wx.StaticText.__init__(self, parent, id, label, pos, size,
							   style, name)
		self.URL = URL
		self.Visited = False

		font = self.GetFont()
		font.SetUnderlined(True)
		self.SetFont(font)

		self.SetCursor(wx.StockCursor(wx.CURSOR_HAND))

		# Colors recommended for HTML5
		self._normalcolor = "#0000EE"
		self._visitedcolor = "#551A8B"
		# Firefox uses this
		self._hovercolor = "#EE0000"

		self._hover = False

		self.Bind(wx.EVT_LEFT_UP, self.OnClick)

	def GetHoverColour(self):
		return self._hovercolour

	def GetNormalColour(self):
		return self._normalcolor

	def GetURL(self):
		return self.URL

	def GetVisited(self):
		return self.Visited

	def GetVisitedColour(self):
		return self._visitedcolor

	@Property
	def HoverColour():
		def fget(self):
			return self._hoverlcolor

		def fset(self, color):
			self.SetHoverColour(color)

		return locals()

	@Property
	def NormalColour():
		def fget(self):
			return self._normalcolor

		def fset(self, color):
			self.SetNormalColour(color)

		return locals()

	def OnClick(self, event):
		wx.LaunchDefaultBrowser(self.URL)
		self.Visited = True

	@Property
	def VisitedColour():
		def fget(self):
			return self._visitedcolor

		def fset(self, color):
			self.SetVisitedColour(color)

		return locals()

	def SetHoverColour(self, color):
		self._hovercolor = color
		if self._hover:
			self.ForegroundColour = color

	def SetNormalColour(self, color):
		self._normalcolor = color
		if not self.Visited and not self._hover:
			self.ForegroundColour = color

	def SetURL(self, url):
		self.URL = url

	def SetVisited(self, visited):
		self.Visited = visited

	def SetVisitedColour(self, color):
		self._visitedcolor = color
		if self.Visited and not self._hover:
			self.ForegroundColour = color


def fancytext_Renderer_getCurrentFont(self):
	font = self.fonts[-1]
	_font = self._font or wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT)
	if "encoding" in font:
		_font.SetEncoding(font["encoding"])
	if "family" in font:
		_font.SetFamily(font["family"])
	if "size" in font:
		_font.SetPointSize(font["size"])
	if "style" in font:
		_font.SetStyle(font["style"])
	if "weight" in font:
		_font.SetWeight(font["weight"])
	return _font

fancytext.Renderer._font = None
fancytext.Renderer.getCurrentFont = fancytext_Renderer_getCurrentFont


def fancytext_RenderToRenderer(str, renderer, enclose=True):
	str = safe_str(str, "UTF-8")
	try:
		if enclose:
			str = '<?xml version="1.0"?><FancyText>%s</FancyText>' % str
		p = xml.parsers.expat.ParserCreate()
		p.returns_unicode = 1
		p.StartElementHandler = renderer.startElement
		p.EndElementHandler = renderer.endElement
		p.CharacterDataHandler = renderer.characterData
		p.Parse(str, 1)
	except xml.parsers.expat.error, err:
		raise ValueError('error parsing text text "%s": %s' % (str, err)) 

fancytext.RenderToRenderer = fancytext_RenderToRenderer


class BetterPyGauge(pygauge.PyGauge):

	def __init__(self, *args, **kwargs):
		pygauge.PyGauge.__init__(self, *args, **kwargs)
		self._indeterminate = False
		self.gradientindex = 0
		self._gradients = []
		self._indeterminate_gradients = []
		self._timer = wx.Timer(self, self._timerId)
		self._timer.Start(50)

	def OnTimer(self, event):
		gradient = self._barGradient
		if self._indeterminate:
			if self.gradientindex < len(self._indeterminate_gradients) - 1:
				self.gradientindex += 1
			else:
				self.gradientindex = 0
			self._barGradient = [self._indeterminate_gradients[self.gradientindex]]
		else:
			if self.gradientindex < len(self._gradients) - 1:
				self.gradientindex += 1
			else:
				self.gradientindex = 0
			self._barGradient = [self._gradients[self.gradientindex]]
		if hasattr(self, "_update_step") and not self._indeterminate:
			stop = True
			for i, v in enumerate(self._value):
				self._value[i] += self._update_step[i]
				
				if self._update_step[i] > 0:
					if self._value[i] > self._update_value[i]:
						self._value[i] = self._update_value[i]
					else: stop = False
				else:
					if self._value[i] < self._update_value[i]:
						self._value[i] = self._update_value[i]
					else: stop = False
			if stop:
				del self._update_step
			updated = True
		else:
			updated = False
		if gradient != self._barGradient or updated:
			self.SortForDisplay()
			if self._indeterminate:
				self._valueSorted = [self.GetRange()]
			self.Refresh()

	def Pulse(self):
		self._indeterminate = True

	def SetBarGradients(self, gradients):
		self._gradients = gradients

	def SetIndeterminateBarGradients(self, gradients):
		self._indeterminate_gradients = gradients

	def SetValue(self, value):
		self._indeterminate = False
		pygauge.PyGauge.SetValue(self, value)
		self.Refresh()

	def Update(self, value, time=0):
		"""
		Update the gauge by adding `value` to it over `time` milliseconds. The `time` parameter
		**must** be a multiple of 50 milliseconds.

		:param `value`: The value to be added to the gauge;
		:param `time`: The length of time in milliseconds that it will take to move the gauge.
		"""
		self._indeterminate = False
	   
		if type(value) != type([]):
			value = [value]
			 
		if len(value) != len(self._value):
			raise Exception("ERROR:\n len(value) != len(self.GetValue())")

		self._update_value = []
		self._update_step  = []
		for i, v in enumerate(self._value):
			if value[i] < 0 or value[i] > self._range:
				raise Exception("ERROR:\n Gauge value must be between 0 and its range. ")
		
			self._update_value.append(value[i])
			self._update_step.append((float(value[i]) - v)/(time/50))


class BetterStaticFancyText(GenStaticBitmap):

	_textlabel = ""

	def __init__(self, window, id, text, *args, **kargs):
		self._textlabel = text
		args = list(args)
		kargs.setdefault('name', 'staticFancyText')
		if 'background' in kargs:
			background = kargs.pop('background')
		elif args:
			background = args.pop(0)
		else:
			background = wx.Brush(window.GetBackgroundColour(), wx.SOLID)
		
		bmp = fancytext.RenderToBitmap(text, background)
		self._enabledbitmap = bmp
		self._enabled = True
		GenStaticBitmap.__init__(self, window, id, bmp, *args, **kargs)

	def Disable(self):
		self.Enable(False)

	def Enable(self, enable=True):
		self._enabled = enable
		if enable:
			bmp = self._enabledbitmap
		else:
			bmp = self._enabledbitmap.ConvertToImage().AdjustChannels(1, 1, 1, .5).ConvertToBitmap()
		self.SetBitmap(bmp)

	def IsEnabled(self):
		return self._enabled

	Enabled = property(IsEnabled, Enable)

	def GetFont(self):
		return fancytext.Renderer._font or wx.SystemSettings_GetFont(wx.SYS_DEFAULT_GUI_FONT)

	def GetLabel(self):
		return self._textlabel

	@Property
	def Label():
		def fget(self):
			return self._textlabel
		
		def fset(self, label):
			self.SetLabel(label)
		
		return locals()
    
	def OnPaint(self, event):
		dc = wx.BufferedPaintDC(self)
		dc.SetBackground(wx.Brush(self.Parent.BackgroundColour, wx.SOLID))
		dc.SetBackgroundMode(wx.SOLID)
		dc.Clear()
		if self._bitmap:
			dc.DrawBitmap(self._bitmap, 0, 0, True)

	def SetFont(self, font):
		fancytext.Renderer._font = font

	def SetLabel(self, label):
		self._textlabel = label
		# Wrap ignoring tags, only break in whitespace
		wrapped = ""
		llen = 0
		intag = False
		for c in label:
			if c == "<":
				intag = True
			elif intag and c == ">":
				intag = False
			if c in "\t ":
				whitespace = True
			else:
				whitespace = False
			if c in u"-\u2012\u2013\u2014\u2015":
				hyphen = True
			else:
				hyphen = False
			if c == "\n":
				llen = 0
			elif not intag:
				llen += 1
				if llen >= 120 and (whitespace or hyphen):
					if hyphen:
						wrapped += c
					c = "\n"
					llen = 0
			wrapped += c
		label = wrapped
		background = wx.Brush(self.Parent.BackgroundColour, wx.SOLID)
		try:
			bmp = fancytext.RenderToBitmap(label, background)
		except ValueError:
			# XML parsing error, strip all tags
			label = re.sub(r"<[^>]*?>", "", label)
			bmp = fancytext.RenderToBitmap(label, background)
		self._enabledbitmap = bmp
		self.SetBitmap(bmp)


class InfoDialog(BaseInteractiveDialog):

	""" Informational dialog with OK button """

	def __init__(self, parent=None, id=-1, title=appname, msg="", 
				 ok="OK", bitmap=None, pos=(-1, -1), size=(400, -1), 
				 show=True, log=True):
		BaseInteractiveDialog.__init__(self, parent, id, title, msg, ok, 
									   bitmap, pos, size, show, log)


class InvincibleFrame(BaseFrame):

	""" A frame that won't be destroyed when closed """

	def __init__(self, parent=None, id=-1, title="", pos=wx.DefaultPosition,
				 size=wx.DefaultSize, style=wx.DEFAULT_FRAME_STYLE,
				 name=wx.FrameNameStr):
		BaseFrame.__init__(self, parent, id, title, pos, size, style, name)
		self.Bind(wx.EVT_CLOSE, self.OnClose, self)

	def OnClose(self, event):
		self.Hide()


class LogWindow(InvincibleFrame):

	""" A log-type window with Clear and Save As buttons """

	def __init__(self, parent=None, id=-1, title=None, pos=wx.DefaultPosition,
				 size=wx.DefaultSize, logctrlstyle=wx.TE_MULTILINE |
												   wx.TE_RICH | wx.NO_BORDER |
												   wx.TE_READONLY):
		if not title:
			title = lang.getstr("infoframe.title")
		if pos == wx.DefaultPosition:
			pos = getcfg("position.info.x"), getcfg("position.info.y")
		if size == wx.DefaultSize:
			size = getcfg("size.info.w"), getcfg("size.info.h")
		InvincibleFrame.__init__(self, parent, id, 
								 title,
								 pos=pos,
								 style=wx.DEFAULT_FRAME_STYLE,
								 name="info")
		self.last_visible = False
		self.panel = wx.Panel(self, -1)
		# Fix wrong background color when disabled
		self.panel.Enable = lambda enable=True: None
		self.panel.Disable = lambda: None
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		self.panel.SetSizer(self.sizer)
		self.log_txt = wx.TextCtrl(self.panel, -1, "", style=logctrlstyle)
		# Fix wrong background color when disabled
		self.log_txt.Enable = lambda enable=True: None
		self.log_txt.Disable = lambda: None
		if u"phoenix" in wx.PlatformInfo:
			kwarg = "faceName"
		else:
			kwarg = "face"
		if sys.platform == "win32":
			font = wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, 
													  wx.FONTWEIGHT_NORMAL,
													  **{kwarg: "Consolas"})
		elif sys.platform == "darwin":
			font = wx.Font(11, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, 
													   wx.FONTWEIGHT_NORMAL,
													   **{kwarg: "Monaco"})
		else:
			font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, 
													   wx.FONTWEIGHT_NORMAL)
		self.log_txt.SetFont(font)
		self.log_txt.SetDefaultStyle(wx.TextAttr(self.log_txt.ForegroundColour,
												 self.log_txt.BackgroundColour,
												 font=font))
		bgcol = wx.Colour(self.log_txt.BackgroundColour.Red() * .5,
						  self.log_txt.BackgroundColour.Green() * .5,
						  self.log_txt.BackgroundColour.Blue() * .5)
		fgcol = wx.Colour(bgcol.Red() + self.log_txt.ForegroundColour.Red() * .5,
						  bgcol.Green() + self.log_txt.ForegroundColour.Green() * .5,
						  bgcol.Blue() + self.log_txt.ForegroundColour.Blue() * .5)
		self._1stcolstyle = wx.TextAttr(fgcol, self.log_txt.BackgroundColour,
										font=font)
		self.sizer.Add(self.log_txt, 1, flag=wx.EXPAND)
		self.log_txt.MinSize = (self.log_txt.GetTextExtent("=" * 95)[0] +
								wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X),
								defaults["size.info.h"] - 24 -
								max(0, self.Size[1] - self.ClientSize[1]))
		separator = BitmapBackgroundPanel(self.panel, size=(-1, 1))
		separator.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DSHADOW))
		self.sizer.Add(separator, flag=wx.EXPAND)
		self.btnsizer = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer.Add(self.btnsizer, flag=wx.EXPAND)
		self.save_as_btn = GenBitmapButton(self.panel, -1, 
										   geticon(16, "media-floppy"), 
										   style = wx.NO_BORDER)
		self.save_as_btn.Bind(wx.EVT_BUTTON, self.OnSaveAs)
		self.save_as_btn.SetToolTipString(lang.getstr("save_as"))
		self.btnsizer.Add(self.save_as_btn, flag=wx.ALL, border=4)
		self.clear_btn = GenBitmapButton(self.panel, -1, 
										 geticon(16, "edit-delete"), 
										 style = wx.NO_BORDER)
		self.clear_btn.Bind(wx.EVT_BUTTON, self.OnClear)
		self.clear_btn.SetToolTipString(lang.getstr("clear"))
		self.btnsizer.Add(self.clear_btn, flag=wx.ALL, border=4)
		self.sizer.SetSizeHints(self)
		self.sizer.Layout()
		self.SetSaneGeometry(*pos + size)
		self.Bind(wx.EVT_MOVE, self.OnMove)
		self.Bind(wx.EVT_SIZE, self.OnSize)
		self.Children[0].Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

	def Log(self, txt):
		for line in txt.splitlines():
			line_lower = line.lower()
			textattr = None
			if (lang.getstr("warning").lower() in line_lower or
				"warning" in line_lower):
				textattr = wx.TextAttr("#F07F00", font=self.log_txt.Font)
			elif (lang.getstr("error").lower() in line_lower or
				"error" in line_lower):
				textattr = wx.TextAttr("#FF3300", font=self.log_txt.Font)
			for line in wrap(line, 80).splitlines():
				while line:
					ms = time() - int(time())
					logline = strftime("%H:%M:%S,") + ("%.3f " % ms)[2:] + line[:80]
					start = self.log_txt.GetLastPosition()
					self.log_txt.AppendText(logline + os.linesep)
					self.log_txt.SetStyle(start, start + 12, self._1stcolstyle)
					if textattr:
						self.log_txt.SetStyle(start + 12, start + len(logline),
											  textattr)
					line = line[80:]
	
	def ScrollToBottom(self):
		self.log_txt.ScrollLines(self.log_txt.GetNumberOfLines())

	def OnClear(self, event):
		self.log_txt.SetValue("")
	
	def OnClose(self, event):
		setcfg("log.show", 0)
		self.Hide()

	def OnDestroy(self, event):
		event.Skip()

	def OnMove(self, event=None):
		if self.IsShownOnScreen() and not self.IsMaximized() and not \
		   self.IsIconized():
			x, y = self.GetScreenPosition()
			setcfg("position.info.x", x)
			setcfg("position.info.y", y)
		if event:
			event.Skip()

	def OnSaveAs(self, event):
		defaultDir, defaultFile = (get_verified_path("last_filedialog_path")[0], 
								   appname)
		dlg = wx.FileDialog(self, lang.getstr("save_as"), 
							defaultDir=defaultDir, defaultFile=defaultFile, 
							wildcard=lang.getstr("filetype.log") + "|*.log", 
							style=wx.SAVE | wx.OVERWRITE_PROMPT)
		dlg.Center(wx.BOTH)
		result = dlg.ShowModal()
		path = dlg.GetPath()
		dlg.Destroy()
		if result == wx.ID_OK:
			if not waccess(path, os.W_OK):
				InfoDialog(self, msg=lang.getstr("error.access_denied.write",
												 path),
						   ok=lang.getstr("ok"),
						   bitmap=geticon(32, "dialog-error"))
				return
			filename, ext = os.path.splitext(path)
			if ext.lower() != ".log":
				path += ".log"
				if os.path.exists(path):
					dlg = ConfirmDialog(self, 
										msg=lang.getstr("dialog."
														"confirm_overwrite", 
														(path)), 
										ok=lang.getstr("overwrite"), 
										cancel=lang.getstr("cancel"), 
										bitmap=geticon(32, "dialog-warning"))
					result = dlg.ShowModal()
					dlg.Destroy()
					if result != wx.ID_OK:
						return
			setcfg("last_filedialog_path", path)
			try:
				file_ = open(path, "w")
				file_.write(self.log_txt.GetValue().encode("UTF-8", "replace"))
				file_.close()
			except Exception, exception:
				InfoDialog(self, msg=safe_unicode(exception), 
						   ok=lang.getstr("ok"), 
						   bitmap=geticon(32, "dialog-error"))

	def OnSize(self, event=None):
		if self.IsShownOnScreen() and not self.IsMaximized() and not \
		   self.IsIconized():
			w, h = self.GetSize()
			setcfg("size.info.w", w)
			setcfg("size.info.h", h)
		if event:
			event.Skip()


class ProgressDialog(wx.Dialog):
	
	""" A progress dialog. """

	bitmaps = {}
	
	def __init__(self, title=appname, msg="", maximum=100, parent=None, style=None, 
				 handler=None, keyhandler=None, start_timer=True, pos=None,
				 pauseable=False, fancy=True):
		if style is None:
			style = (wx.PD_APP_MODAL | wx.PD_ELAPSED_TIME |
					 wx.PD_REMAINING_TIME | wx.PD_CAN_ABORT | wx.PD_SMOOTH)
		self._style = style
		wx.Dialog.__init__(self, parent, wx.ID_ANY, title,
						   name="progressdialog")
		if fancy:
			self.BackgroundColour = "#141414"
			self.ForegroundColour = "#FFFFFF"
		if sys.platform == "win32":
			if not fancy:
				bgcolor = self.BackgroundColour
				self.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))
			if sys.getwindowsversion() >= (6, ):
				# No need to enable double buffering under Linux and Mac OS X.
				# Under Windows, enabling double buffering on the panel seems
				# to work best to reduce flicker.
				self.SetDoubleBuffered(True)
		self.set_icons()
		self.Bind(wx.EVT_CLOSE, self.OnClose, self)
		if not pos:
			self.Bind(wx.EVT_MOVE, self.OnMove, self)
		self.timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, handler or self.OnTimer, self.timer)
		
		self.keepGoing = True
		self.skip = False
		self.paused = False
		self.progress_type = 0  # 0 = processing, 1 = measurement

		margin = 12

		self.sizer0 = wx.BoxSizer(wx.VERTICAL)
		if fancy:
			self.sizerH = wx.BoxSizer(wx.HORIZONTAL)
			self.SetSizer(self.sizerH)
			self.animbmp = AnimatedBitmap(self, -1, size=(200, 200))
			self.sizerH.Add(self.animbmp, 0, flag=wx.ALIGN_CENTER_VERTICAL)
			self.sizerH.Add(self.sizer0, 1, flag=wx.EXPAND)
			try:
				audio.init()
			except Exception, exception:
				safe_print(exception)
			self.sound = audio.Sound(get_data_path("theme/engine_hum_loop.wav"),
									 True)
			self.indicator_sound = audio.Sound(get_data_path("theme/beep_boop.wav"))
			self.get_bitmaps(self.progress_type)
			sizer0flag = 0
		else:
			self.SetSizer(self.sizer0)
			sizer0flag = wx.LEFT
		self.sizer1 = wx.BoxSizer(wx.VERTICAL)
		self.sizer2 = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer0.Add(self.sizer1, flag = wx.ALIGN_LEFT | wx.TOP | wx.RIGHT |
						sizer0flag, border=margin)
		self.buttonpanel = wx.Panel(self)
		self.buttonpanel.SetSizer(wx.BoxSizer(wx.VERTICAL))
		self.buttonpanel.Sizer.Add(self.sizer2, 1, flag=wx.ALIGN_RIGHT | wx.ALL, 
								   border=margin)
		if sys.platform == "win32" and not fancy:
			self.buttonpanel_line = wx.Panel(self, size=(-1,1))
			self.buttonpanel_line.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT))
			self.sizer0.Add(self.buttonpanel_line, flag=wx.TOP | wx.EXPAND,
							border=margin)
			self.buttonpanel.SetBackgroundColour(bgcolor)
		elif fancy:
			self.buttonpanel.BackgroundColour = "#141414"
		self.sizer0.Add(self.buttonpanel, flag=wx.EXPAND)

		self.msg = wx.StaticText(self, -1, "", size=(-1, 74))
		self.sizer1.Add(self.msg, flag=wx.EXPAND | wx.BOTTOM, border=margin)
		
		self._fpprogress = 0.0
		if fancy:
			self.gauge = BetterPyGauge(self, wx.ID_ANY, range=maximum,
									   size=(-1, 4))
			self.gauge.SetBackgroundColour("#202020")
			self.gauge.SetBorderColour("#0066CC")
			self.gauge.SetBarGradients([("#0099CC", "#00CCFF"),
									    ("#0088BB", "#00BBEE"),
									    ("#0077AA", "#00AADD"),
									    ("#006699", "#0099CC"),
									    ("#0077AA", "#00AADD"),
									    ("#0088BB", "#00BBEE")])
			self.gauge.SetIndeterminateBarGradients([("#00CCFF", "#001144"),
													 ("#00BBEE", "#002255"),
													 ("#00AADD", "#003366"),
													 ("#0099CC", "#004477"),
													 ("#0088BB", "#005588"),
													 ("#0077AA", "#006699"),
													 ("#006699", "#0077AA"),
													 ("#005588", "#0088BB"),
													 ("#004477", "#0099CC"),
													 ("#003366", "#00AADD"),
													 ("#002255", "#00BBEE"),
													 ("#001144", "#00CCFF"),
													 ("#002255", "#00BBEE"),
													 ("#003366", "#00AADD"),
													 ("#004477", "#0099CC"),
													 ("#005588", "#0088BB"),
													 ("#006699", "#0077AA"),
													 ("#0077AA", "#006699"),
													 ("#0088BB", "#005588"),
													 ("#0099CC", "#004477"),
													 ("#00AADD", "#003366"),
													 ("#00BBEE", "#002255")])
			self.gauge.SetValue(0)
		else:
			gauge_style = wx.GA_HORIZONTAL
			if style & wx.PD_SMOOTH:
				gauge_style |= wx.GA_SMOOTH
			self.gauge = wx.Gauge(self, wx.ID_ANY, range=maximum, style=gauge_style)
		self.sizer1.Add(self.gauge, flag=wx.EXPAND | wx.BOTTOM, border=margin)
		
		if style & wx.PD_ELAPSED_TIME or style & wx.PD_REMAINING_TIME:
			self.sizer3 = wx.FlexGridSizer(0, 2, 0, margin)
			self.sizer1.Add(self.sizer3, flag=wx.ALIGN_LEFT)
			self.time = time()
		
		if style & wx.PD_ELAPSED_TIME:
			self.sizer3.Add(wx.StaticText(self, -1,
										  lang.getstr("elapsed_time")))
			self.elapsed_time = wx.StaticText(self, -1, "--:--:--")
			self.elapsed_time_handler(None)
			self.sizer3.Add(self.elapsed_time)
			self.elapsed_timer = wx.Timer(self)
			self.Bind(wx.EVT_TIMER, self.elapsed_time_handler,
					  self.elapsed_timer)
		
		if style & wx.PD_REMAINING_TIME:
			self.sizer3.Add(wx.StaticText(self, -1,
										  lang.getstr("remaining_time")))
			self.time2 = 0
			self.time3 = time()
			self.time4 = 0
			self.remaining_time = wx.StaticText(self, -1, u"––:––:––")
			self.sizer3.Add(self.remaining_time)

		if fancy:
			def buttoncls(parent, id, label):
				return FlatShadedButton(parent, id, None, label,
										fgcolour="#FFFFFF")
		else:
			buttoncls = wx.Button

		if style & wx.PD_CAN_ABORT:
			self.cancel = buttoncls(self.buttonpanel, wx.ID_ANY,
									lang.getstr("cancel"))
			self.sizer2.Add(self.cancel)
			self.Bind(wx.EVT_BUTTON, self.OnClose, id=self.cancel.GetId())

		self.pause_continue = buttoncls(self.buttonpanel, wx.ID_ANY,
										lang.getstr("continue"))
		self.sizer2.Prepend((margin, margin))
		self.sizer2.Prepend(self.pause_continue, flag=wx.LEFT, border=margin)
		self.Bind(wx.EVT_BUTTON, self.pause_continue_handler,
				  id=self.pause_continue.GetId())
		self.pause_continue.Show(pauseable)

		if fancy:
			if getcfg("measurement.play_sound"):
				bitmap = geticon(16, "sound_volume_full")
			else:
				bitmap = geticon(16, "sound_off")
			im = bitmap.ConvertToImage()
			im.AdjustMinMax(maxvalue=1.5)
			bitmap = im.ConvertToBitmap()
			self.sound_on_off_btn = FlatShadedButton(self.buttonpanel,
													 bitmap=bitmap,
													 fgcolour="#FFFFFF")
			self.sizer2.Prepend(self.sound_on_off_btn)
			self.sound_on_off_btn.Bind(wx.EVT_BUTTON,
									   self.play_sound_handler)

		self.buttonpanel.Layout()
		
		# Use an accelerator table for 0-9, a-z, numpad
		keycodes = range(48, 58) + range(97, 123) + numpad_keycodes
		self.id_to_keycode = {}
		for keycode in keycodes:
			self.id_to_keycode[wx.NewId()] = keycode
		accels = []
		for id, keycode in self.id_to_keycode.iteritems():
			self.Bind(wx.EVT_MENU, keyhandler or self.key_handler, id=id)
			accels.append((wx.ACCEL_NORMAL, keycode, id))
		self.SetAcceleratorTable(wx.AcceleratorTable(accels))
		
		self.msg.Label = "\n".join(["E" * 80] * 4)
		w, h = self.msg.Size
		self.msg.WindowStyle |= wx.ST_NO_AUTORESIZE
		self.msg.SetMinSize((w, h))
		self.msg.SetSize((w, h))
		self.Sizer.SetSizeHints(self)
		self.Sizer.Layout()
		self.msg.SetLabel(msg.replace("&", "&&"))

		self.pause_continue.Label = lang.getstr("pause")
		
		self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy, self)
		
		# set position
		placed = False
		if pos:
			x, y = pos
		else:
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
		
		if start_timer:
			self.start_timer()
		
		self.Show()
		if style & wx.PD_APP_MODAL:
			self.MakeModal()
	
	def MakeModal(self, modal=True):
		# wxPython 3.0 deprecates MakeModal, use a replacement implementation
		# based on http://wxpython.org/Phoenix/docs/html/MigrationGuide.html
		if modal and not hasattr(self, '_disabler'):
			self._disabler = BetterWindowDisabler(self)
		if not modal and hasattr(self, '_disabler'):
			del self._disabler
	
	def OnClose(self, event):
		self.keepGoing = False
		if hasattr(self, "cancel"):
			self.cancel.Disable()
		self.pause_continue.Disable()
		if not self.timer.IsRunning():
			self.Destroy()
		elif self.gauge.GetValue() == self.gauge.GetRange():
			event.Skip()
	
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
	
	def OnTimer(self, event):
		if self.keepGoing:
			if not self.pause_continue.IsEnabled():
				self.set_progress_type(int(not self.progress_type))
			self.pause_continue.Enable()
			if self.paused:
				return
			if self._fpprogress < self.gauge.GetRange():
				self.Update(self._fpprogress + self.gauge.GetRange() / 1000.0)
			else:
				self.stop_timer()
				self.Update(self.gauge.GetRange(),
							"Finished. You may now close this window.")
				self.pause_continue.Disable()
				if hasattr(self, "cancel"):
					self.cancel.Disable()
		else:
			self.Pulse("Aborting...")
			if not hasattr(self, "delayed_stop"):
				self.delayed_stop = wx.CallLater(3000, self.stop_timer)
				wx.CallLater(3000, self.Pulse, 
							 "Aborted. You may now close this window.")
	
	def Pulse(self, msg=None):
		if msg and msg != self.msg.Label:
			self.msg.SetLabel(msg)
			self.msg.Wrap(self.msg.ContainingSizer.Size[0])
			self.msg.Refresh()
			self.msg.Update()
		if getattr(self, "time2", 0):
			self.time2 = 0
			if not self.time3:
				self.time3 = time()
			self.remaining_time.Label = u"––:––:––"
		self.gauge.Pulse()
		return self.keepGoing, self.skip
	
	def Resume(self):
		self.keepGoing = True
		if hasattr(self, "cancel"):
			self.cancel.Enable()
		if self.paused:
			self.pause_continue_handler()
		else:
			self.pause_continue.Enable()
	
	def Update(self, value, msg=None):
		if msg and msg != self.msg.Label:
			self.msg.SetLabel(msg)
			self.msg.Wrap(self.msg.ContainingSizer.Size[0])
			self.msg.Refresh()
			self.msg.Update()
		prev_value = self._fpprogress
		self._fpprogress = value
		value = int(round(value))
		if hasattr(self, "time2"):
			t = time()
			if not self.time2:
				if value < self.gauge.GetValue():
					# Reset
					self.time2 = t
				else:
					# Continue
					self.time4 += time() - self.time3
					self.time2 = self.time + self.time4
					self.time3 = 0
			if value and value != self.gauge.GetValue() and self.time2 < t:
				remaining = ((t - self.time2) / value *
								  (self.gauge.GetRange() - value))
				if remaining > 9 or value > self.gauge.GetRange() * .03:
					self.remaining_time.Label = strftime("%H:%M:%S",
														 gmtime(remaining))
		if getcfg("measurement.play_sound"):
			if value < prev_value and hasattr(self, "indicator_sound"):
				self.indicator_sound.safe_play()
		if (isinstance(self.gauge, BetterPyGauge) and
			self._style & wx.PD_SMOOTH):
			if value >= prev_value:
				update_value = abs(self._fpprogress - prev_value)
				if update_value:
					# Higher ms = smoother animation, but potentially
					# increased "lag"
					ms = 950 + 50 * update_value
					self.gauge.Update(value, ms)
			else:
				self.gauge.Update(value, 50)
		else:
			self.gauge.SetValue(value)
		return self.keepGoing, self.skip
	
	UpdatePulse = Pulse

	def anim_fadein(self):
		bitmaps = ProgressDialog.get_bitmaps(self.progress_type)
		if self.progress_type == 0:
			# Processing
			range = (60, 68)
		else:
			# Measuring
			range = (27, 36)
		self.animbmp.SetBitmaps(bitmaps, range=range, loop=True)
		wx.CallLater(50, lambda: self and self.IsShown() and
								  self.animbmp.Play(20))
		if self.progress_type == 0 and getcfg("measurement.play_sound"):
			wx.CallLater(50, lambda: self and self.IsShown() and
									  self.sound.safe_play(3000))

	def anim_fadeout(self):
		self.animbmp.loop = False
		if self.sound.is_playing:
			self.sound.safe_stop(3000)
	
	def elapsed_time_handler(self, event):
		self.elapsed_time.Label = strftime("%H:%M:%S",
										   gmtime(time() - self.time))

	@staticmethod
	def get_bitmaps(progress_type=0):
		if progress_type in ProgressDialog.bitmaps:
			bitmaps = ProgressDialog.bitmaps[progress_type]
		else:
			bitmaps = ProgressDialog.bitmaps[progress_type] = []
			if progress_type == 0:
				# Processing
				for pth in get_data_path("theme/jet_anim", r"\.png$") or []:
					im = wx.Image(pth)
					# Blend red
					im = im.AdjustChannels(1, .2, 0)
					# Adjust for background
					im.AdjustMinMax(1.0 / 255 * 0x14)
					bitmaps.append(im)
				# Needs to be exactly 8 images
				if bitmaps and len(bitmaps) == 8:
					for i in xrange(7):
						bitmaps.extend(bitmaps[:8])
					bitmaps.extend(bitmaps[:4])
					# Fade in
					for i, im in enumerate(bitmaps[:10]):
						im = im.AdjustChannels(1, 1, 1, i / 10.0)
						bitmaps[i] = im.ConvertToBitmap()
					# Normal
					for i in xrange(50):
						im = bitmaps[i + 10].Copy()
						im.RotateHue(.05 * (i / 50.0))
						bitmaps[i + 10] = im.ConvertToBitmap()
					for i, im in enumerate(bitmaps[60:]):
						im = im.Copy()
						im.RotateHue(.05)
						bitmaps[i + 60] = im.ConvertToBitmap()
					# Fade out
					bitmaps.extend(reversed(bitmaps[:60]))
			else:
				# Measuring
				for pth in get_data_path("theme/patch_anim", r"\.png$") or []:
					im = wx.Image(pth)
					bitmaps.append(im)
				# Needs to be exactly 9 images
				if bitmaps and len(bitmaps) == 9:
					for i in xrange(3):
						bitmaps.extend(bitmaps[:9])
					# Fade in
					for i, im in enumerate(bitmaps[:27]):
						im = im.AdjustChannels(1, 1, 1, i / 27.0)
						bitmaps[i] = im.ConvertToBitmap()
					# Normal
					for i, im in enumerate(bitmaps[27:]):
						bitmaps[i + 27] = im.ConvertToBitmap()
					# Fade out
					for i in xrange(3):
						bitmaps.extend(bitmaps[27:36])
					for i, bmp in enumerate(bitmaps[36:]):
						im = bmp.ConvertToImage().AdjustChannels(1, 1, 1, 1 - i / 26.0)
						bitmaps[i + 36] = im.ConvertToBitmap()
		return bitmaps
	
	def key_handler(self, event):
		pass

	def pause_continue_handler(self, event=None):
		self.paused = not self.paused
		self.gauge.Pulse()
		if self.paused:
			self.pause_continue.Label = lang.getstr("continue")
		else:
			self.pause_continue.Label = lang.getstr("pause")
		self.pause_continue.Enable(not event)
		self.Layout()
	
	def play_sound_handler(self, event):
		setcfg("measurement.play_sound",
			   int(not(bool(getcfg("measurement.play_sound")))))
		if getcfg("measurement.play_sound"):
			bitmap = getbitmap("theme/icons/16x16/sound_volume_full")
			if self.keepGoing and self._fpprogress < self.gauge.GetRange():
				self.sound.safe_play()
		else:
			bitmap = getbitmap("theme/icons/16x16/sound_off")
			if self.sound.is_playing:
				self.sound.safe_stop()
		im = bitmap.ConvertToImage()
		im.AdjustMinMax(maxvalue=1.5)
		bitmap = im.ConvertToBitmap()
		self.sound_on_off_btn._bitmap = bitmap

	set_icons = BaseInteractiveDialog.__dict__["set_icons"]

	def set_progress_type(self, progress_type):
		if hasattr(self, "animbmp"):
			self.anim_fadeout()
			if self.progress_type == 0:
				delay = 4000
			else:
				delay = 2000
			wx.CallLater(delay, lambda: self and
										self.progress_type == progress_type and
										self.anim_fadein())
		if progress_type != self.progress_type:
			self.progress_type = progress_type

	def start_timer(self, ms=50):
		self.timer.Start(ms)
		if hasattr(self, "elapsed_timer"):
			self.elapsed_timer.Start(1000)
		if hasattr(self, "animbmp"):
			self.anim_fadein()
	
	def stop_timer(self):
		self.timer.Stop()
		if hasattr(self, "elapsed_timer"):
			self.elapsed_timer.Stop()
		if hasattr(self, "animbmp") and self.animbmp.loop:
			self.anim_fadeout()


class FancyProgressDialog(ProgressDialog):

	def __init__(self, *args, **kwargs):
		kwargs["fancy"] = True
		ProgressDialog.__init__(self, *args, **kwargs)


class SimpleBook(labelbook.FlatBookBase):

	def __init__(self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition, size=wx.DefaultSize,
				 style=0, agwStyle=0, name="SimpleBook"):
		
		labelbook.FlatBookBase.__init__(self, parent, id, pos, size, style, agwStyle, name)
		
		self._pages = self.CreateImageContainer()

		# Label book specific initialization
		self._mainSizer = wx.BoxSizer(wx.HORIZONTAL)
		self.SetSizer(self._mainSizer)
		

	def CreateImageContainer(self):
		""" Creates the image container (LabelContainer) class for L{FlatImageBook}. """

		return labelbook.ImageContainerBase(self, wx.ID_ANY, agwStyle=self.GetAGWWindowStyleFlag())


class SimpleTerminal(InvincibleFrame):
	
	""" A simple terminal-like window. """

	def __init__(self, parent=None, id=-1, title=appname, handler=None, 
				 keyhandler=None, start_timer=True, pos=wx.DefaultPosition,
				 size=wx.DefaultSize, consolestyle=wx.TE_CHARWRAP |
												   wx.TE_MULTILINE |
												   wx.TE_READONLY | wx.VSCROLL |
												   wx.NO_BORDER, show=True,
				 name="simpleterminal"):
		if pos == wx.DefaultPosition:
			pos = getcfg("position.progress.x"), getcfg("position.progress.y")
		if size == wx.DefaultSize:
			size = getcfg("size.progress.w"), getcfg("size.progress.h")
		InvincibleFrame.__init__(self, parent, id, title, pos=pos,
								 style=wx.DEFAULT_FRAME_STYLE, name=name)
		
		self.Bind(wx.EVT_CLOSE, self.OnClose, self)
		self.Bind(wx.EVT_MOVE, self.OnMove, self)
		self.timer = wx.Timer(self)
		if handler:
			self.Bind(wx.EVT_TIMER, handler, self.timer)
		
		self.panel = wx.Panel(self, -1)
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		self.panel.SetSizer(self.sizer)
		self.console = wx.TextCtrl(self.panel, -1, "", style=consolestyle)
		self.console.SetBackgroundColour("#272727")
		self.console.SetForegroundColour("#808080")
		if u"phoenix" in wx.PlatformInfo:
			kwarg = "faceName"
		else:
			kwarg = "face"
		if sys.platform == "win32":
			font = wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, 
													  wx.FONTWEIGHT_NORMAL,
													  **{kwarg: "Consolas"})
		elif sys.platform == "darwin":
			font = wx.Font(11, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, 
													   wx.FONTWEIGHT_NORMAL,
													   **{kwarg: "Monaco"})
		else:
			font = wx.Font(11, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, 
													   wx.FONTWEIGHT_NORMAL)
		self.console.SetFont(font)
		self.sizer.Add(self.console, 1, flag=wx.ALL | wx.EXPAND, border=0)
		
		if sys.platform == "win32":
			# Mac: TextCtrls don't receive EVT_KEY_DOWN
			self.console.Bind(wx.EVT_KEY_DOWN, keyhandler or self.key_handler, 
							  self.console)
		else:
			# Windows: EVT_CHAR_HOOK only receives "special" keys e.g. ESC, Tab
			self.Bind(wx.EVT_CHAR_HOOK, keyhandler or self.key_handler)
		
		# Use an accelerator table for space, 0-9, a-z, numpad
		keycodes = [32] + range(48, 58) + range(97, 123) + numpad_keycodes
		self.id_to_keycode = {}
		for keycode in keycodes:
			self.id_to_keycode[wx.NewId()] = keycode
		
		# set size
		text_extent = self.console.GetTextExtent(" ")
		vscroll_w = wx.SystemSettings_GetMetric(wx.SYS_VSCROLL_X)
		w, h = (text_extent[0] * 80 + vscroll_w + 4, 
				text_extent[1] * 24)
		self.console.SetMinSize((w, h))
		w, h = max(size[0], w), max(size[1], h)
		self.console.SetSize((w, h))
		self.sizer.SetSizeHints(self)
		self.sizer.Layout()
		
		# set position	
		placed = False
		if parent:
			if parent.IsShownOnScreen():
				self.Center()
				placed = True
			else:
				x = pos[0] or parent.GetScreenPosition()[0]
				y = pos[1] or parent.GetScreenPosition()[1]
		else:
			x, y = pos
		if not placed:
			self.SetSaneGeometry(x, y, w, h)
		
		self.lastmsg = ""
		self.keepGoing = True
		
		self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy, self)
		
		if start_timer:
			self.start_timer()
		
		if show:
			self.Show()
			self.console.SetFocus()
	
	def EndModal(self, returncode=wx.ID_OK):
		return returncode
	
	def MakeModal(self, makemodal=False):
		pass
	
	def OnClose(self, event):
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
	
	def Pulse(self, msg=""):
		self.lastmsg = msg
		return self.keepGoing, False
	
	def Resume(self):
		self.keepGoing = True
	
	def Update(self, value, msg=""):
		return self.Pulse(msg)
	
	def UpdatePulse(self, msg=""):
		return self.Pulse(msg)
	
	def add_text(self, txt):
		pos = self.console.GetLastPosition()
		if txt.startswith("\r"):
			txt = txt.lstrip("\r")
			numlines = self.console.GetNumberOfLines()
			start = pos - self.console.GetLineLength(numlines - 1)
			self.console.Replace(start, pos, txt)
		else:
			self.console.AppendText(txt)
	
	def flush(self):
		pass
	
	def isatty(self):
		return True
	
	def key_handler(self, event):
		pass
	
	def start_timer(self, ms=50):
		self.timer.Start(ms)
	
	def stop_timer(self):
		self.timer.Stop()
	
	def write(self, txt):
		wx.CallAfter(self.add_text, txt)


class TooltipWindow(InvincibleFrame):

	""" A tooltip-style window """
	
	def __init__(self, parent=None, id=-1, title=appname, msg="", cols=1,
				 bitmap=None, pos=(-1, -1), size=(400, -1), 
				 style=wx.DEFAULT_FRAME_STYLE | wx.FRAME_TOOL_WINDOW, wrap=70):
		InvincibleFrame.__init__(self, parent, id, title, pos, size, style)
		self.SetPosition(pos)  # yes, this is needed
		self.set_icons()

		margin = 12
		
		self.panel = wx.Panel(self, -1)
		self.sizer0 = wx.BoxSizer(wx.VERTICAL)
		self.panel.SetSizer(self.sizer0)
		self.sizer1 = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer0.Add(self.sizer1, flag = wx.ALIGN_CENTER | wx.ALL, 
		   border = margin)

		if bitmap:
			self.bitmap = wx.StaticBitmap(self.panel, -1, bitmap, 
			   size = (32, 32))
			self.sizer1.Add(self.bitmap)

		self.sizer2 = wx.BoxSizer(wx.VERTICAL)
		self.sizer1.Add(self.sizer2)

		msg = util_str.wrap(msg, wrap).splitlines()
		for i, line in enumerate(msg):
			if not line:
				# Use as header
				header = wx.StaticText(self.panel, -1, "\n".join(msg[:i + 1]))
				self.sizer2.Add(header, flag=wx.LEFT, border=margin)
				msg = msg[i + 1:]
				break
		self.sizer3 = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer2.Add(self.sizer3, flag=wx.EXPAND)
		rowspercol = int(math.ceil(len(msg) / float(cols)))
		msgs = []
		while msg:
			msgs.append(msg[:rowspercol])
			msg = msg[rowspercol:]
		for msg in msgs:
			col = wx.StaticText(self.panel, -1, "")
			col.SetMaxFontSize()
			maxlinewidth = 0
			for line in msg:
				maxlinewidth = max(col.GetTextExtent(line)[0], maxlinewidth)
			col.Label = "\n".join(msg)
			col.MinSize = maxlinewidth + margin * 2, -1
			self.sizer3.Add(col, flag=wx.LEFT, border=margin)

		self.sizer0.SetSizeHints(self)
		self.sizer0.Layout()
		if not pos or pos == (-1, -1):
			self.Center(wx.BOTH)
		elif pos[0] == -1:
			self.Center(wx.HORIZONTAL)
		elif pos[1] == -1:
			self.Center(wx.VERTICAL)
		self.Show()
		self.Raise()

	set_icons = BaseInteractiveDialog.__dict__["set_icons"]


class TwoWaySplitter(FourWaySplitter):
	
	def __init__(self, *args, **kwargs):
		FourWaySplitter.__init__(self, *args, **kwargs)
		self._minimum_pane_size = 0
		self._sashbitmap = getbitmap("theme/sash")
		self._splitsize = (800, 400)
		self._expandedsize = (400, 400)
		self._handcursor = wx.StockCursor(wx.CURSOR_HAND)
		self.Bind(wx.EVT_LEFT_DCLICK, self.OnLeftDClick)

	def _GetSashSize(self):
		""" Used internally. """

		if self.HasFlag(wx.SP_NOSASH):
			return 0

		return self._sashbitmap.GetSize()[0]

    # Recompute layout
	def _SizeWindows(self):
		"""
		Recalculate the layout based on split positions and split fractions.

		:see: L{SetHSplit} and L{SetVSplit} for more information about split fractions.
		"""
			
		win0 = self.GetTopLeft()
		win1 = self.GetTopRight()

		width, height = self.GetSize()
		barSize = self._GetSashSize()
		border = self._GetBorderSize()
		
		if self._expanded < 0:
			totw = width - barSize - 2*border
			self._splitx = max((self._fhor*totw)/10000, self._minimum_pane_size)
			self._splity = height
			rightw = max(totw - self._splitx, 0)
			if win0:
				win0.SetPosition((0, 0))
				win0.SetSize((self._splitx, self._splity))
				win0.Show()
			if win1:
				win1.SetPosition((self._splitx + barSize, 0))
				win1.SetSize((rightw, self._splity))
				win1.Show()

		else:
			if self._expanded < len(self._windows):
				for ii, win in enumerate(self._windows):
					if ii == self._expanded:
						win.SetDimensions(0, 0, width - barSize - 2*border, height-2*border)
						win.Show()
					else:
						win.Hide()

	# Draw the horizontal split
	def DrawSplitter(self, dc):
		"""
		Actually draws the sashes.

		:param `dc`: an instance of `wx.DC`.
		"""

		backColour = wx.Colour(*[int(v * .85) for v in self.BackgroundColour])
		dc.SetBrush(wx.Brush(backColour, wx.SOLID))
		dc.SetPen(wx.Pen(backColour))
		dc.Clear()
		
		width, height = self.GetSize()

		if self._expanded > -1:
			splitx = width - self._GetSashSize() - 2*self._GetBorderSize()
		else:
			splitx = self._splitx

		if self._expanded < 0:
			if splitx <= self._minimum_pane_size:
				self._sashbitmap = getbitmap("theme/sash-right")
			else:
				self._sashbitmap = getbitmap("theme/sash")
		else:
			self._sashbitmap = getbitmap("theme/sash-left")
		sashwidth, sashheight = self._sashbitmap.GetSize()
		
		dc.DrawRectangle(splitx, 0, sashwidth, height)
		
		dc.DrawBitmap(self._sashbitmap, splitx, height / 2 - sashheight / 2, True)
	
	def GetExpandedSize(self):
		return self._expandedsize

	# Determine split mode
	def GetMode(self, pt):
		"""
		Determines the split mode for L{FourWaySplitter}.

		:param `pt`: the point at which the mouse has been clicked, an instance of
		 `wx.Point`.

		:return: One of the following 3 split modes:

		 ================= ==============================
		 Split Mode        Description
		 ================= ==============================
		 ``wx.HORIZONTAL`` the user has clicked on the horizontal sash
		 ``wx.VERTICAL``   The user has clicked on the vertical sash
		 ``wx.BOTH``       The user has clicked at the intersection between the 2 sashes
		 ================= ==============================

		"""

		barSize = self._GetSashSize()        
		flag = wx.BOTH

		width, height = self.GetSize()
		if self._expanded > -1:
			splitx = width - self._GetSashSize() - 2*self._GetBorderSize()
		else:
			splitx = self._splitx

		if pt.x < splitx - _TOLERANCE:
			flag &= ~wx.VERTICAL

		if pt.y < self._splity - _TOLERANCE:
			flag &= ~wx.HORIZONTAL

		if pt.x >= splitx + barSize + _TOLERANCE:
			flag &= ~wx.VERTICAL
			
		if pt.y >= self._splity + barSize + _TOLERANCE:
			flag &= ~wx.HORIZONTAL
			
		return flag
	
	def GetSplitSize(self):
		return self._splitsize
	
	def OnLeftDClick(self, event):
		if not self.IsEnabled():
			return
		
		pt = event.GetPosition()

		if self.GetMode(pt):
			
			width, height = self.GetSize()
			barSize = self._GetSashSize()
			border = self._GetBorderSize()
			
			totw = width - barSize - 2*border
			
			winborder, titlebar = get_platform_window_decoration_size()
			winwidth, winheight = self.Parent.GetSize()
			
			self.Freeze()
			self.SetExpanded(-1 if self._expanded > -1 else 0)
			if self._expanded < 0:
				if self.GetExpandedSize()[0] < self.GetSplitSize()[0]:
					self._fhor = int(math.ceil((self.GetExpandedSize()[0] - 
												barSize - winborder * 2) /
											   float(self.GetSplitSize()[0] - 
													 barSize - winborder * 2) *
											   10000))
				else:
					self._fhor = int(math.ceil(self._minimum_pane_size /
											   float(self.GetSplitSize()[0] - 
													 barSize - winborder * 2) *
											   10000))
				self.Parent.SetMinSize((defaults["size.profile_info.split.w"] + winborder * 2,
										self.Parent.GetMinSize()[1]))
				if (not self.Parent.IsMaximized() and
					self.Parent.GetSize()[0] < self.GetSplitSize()[0]):
					self.Parent.SetSize((self.GetSplitSize()[0],
										 self.Parent.GetSize()[1]))
			else:
				self.Parent.SetMinSize((defaults["size.profile_info.w"] + winborder * 2,
										self.Parent.GetMinSize()[1]))
				w = max(self.GetExpandedSize()[0],
						self._splitx + barSize + winborder * 2)
				if (not self.Parent.IsMaximized() and
					self.Parent.GetSize()[0] > w):
					self.Parent.SetSize((w,
										 self.Parent.GetSize()[1]))
			#wx.CallLater(25, self.Parent.redraw)
			self.Parent.idle = False
			self.Parent.resize_grid()
			self.Thaw()

	# Button being released
	def OnLeftUp(self, event):
		"""
		Handles the ``wx.EVT_LEFT_UP`` event for L{FourWaySplitter}.

		:param `event`: a `wx.MouseEvent` event to be processed.
		"""
		
		if not self.IsEnabled():
			return

		if self.HasCapture():
			self.ReleaseMouse()

		flgs = self._flags
		
		self._flags &= ~FLAG_CHANGED
		self._flags &= ~FLAG_PRESSED
		
		if flgs & FLAG_PRESSED:
			
			if not self.GetAGWWindowStyleFlag() & wx.SP_LIVE_UPDATE:
				self.DrawTrackSplitter(self._splitx, self._splity)
				self.DrawSplitter(wx.ClientDC(self))
				self.AdjustLayout()
				
			if flgs & FLAG_CHANGED:
				event = FourWaySplitterEvent(wx.wxEVT_COMMAND_SPLITTER_SASH_POS_CHANGED, self)
				event.SetSashIdx(self._mode)
				event.SetSashPosition(wx.Point(self._splitx, self._splity))
				self.GetEventHandler().ProcessEvent(event)                
			else:
				self.OnLeftDClick(event)

		self._mode = NOWHERE

	def OnMotion(self, event):
		"""
		Handles the ``wx.EVT_MOTION`` event for L{FourWaySplitter}.

		:param `event`: a `wx.MouseEvent` event to be processed.
		"""

		if self.HasFlag(wx.SP_NOSASH):
			return

		pt = event.GetPosition()

		# Moving split
		if self._flags & FLAG_PRESSED:
			
			width, height = self.GetSize()
			barSize = self._GetSashSize()
			border = self._GetBorderSize()
			
			totw = width - barSize - 2*border
			
			if pt.x > totw - _TOLERANCE:
				self._expanded = 0
				self._offx += 1
			elif self._expanded > -1 and pt.x > self._minimum_pane_size:
				self._fhor = int((pt.x - barSize - 2*border) / float(totw) * 10000)
				self._splitx = (self._fhor*totw)/10000
				self._offx = pt.x - self._splitx + 1
				self._expanded = -1

			oldsplitx = self._splitx
			oldsplity = self._splity
			
			if self._mode == wx.BOTH:
				self.MoveSplit(pt.x - self._offx, pt.y - self._offy)
			  
			elif self._mode == wx.VERTICAL:
				self.MoveSplit(pt.x - self._offx, self._splity)
			  
			elif self._mode == wx.HORIZONTAL:
				self.MoveSplit(self._splitx, pt.y - self._offy)

			# Send a changing event
			if not self.DoSendChangingEvent(wx.Point(self._splitx, self._splity)):
				self._splitx = oldsplitx
				self._splity = oldsplity
				return              

			if oldsplitx != self._splitx or oldsplity != self._splity:
				if not self.GetAGWWindowStyleFlag() & wx.SP_LIVE_UPDATE:
					self.DrawTrackSplitter(oldsplitx, oldsplity)
					self.DrawTrackSplitter(self._splitx, self._splity)
				else:
					self.AdjustLayout()

				self._flags |= FLAG_CHANGED

			self.Refresh()
		
		# Change cursor based on position
		ff = self.GetMode(pt)
		
		if self._expanded > -1 and self._splitx <= self._minimum_pane_size:
			self.SetCursor(self._handcursor)

		elif ff == wx.BOTH:
			self.SetCursor(self._sashCursorSIZING)

		elif ff == wx.VERTICAL:
			self.SetCursor(self._sashCursorWE)

		elif ff == wx.HORIZONTAL:
			self.SetCursor(self._sashCursorNS)

		else:
			self.SetCursor(self._handcursor)

		event.Skip()
	
	def SetExpandedSize(self, size):
		self._expandedsize = size

	def SetMinimumPaneSize(self, size=0):
		self._minimum_pane_size = size
	
	def SetSplitSize(self, size):
		self._splitsize = size

def get_gradient_panel(parent, label, x=16):
	gradientpanel = BitmapBackgroundPanelText(parent, size=(-1, 31))
	gradientpanel.alpha = .75
	gradientpanel.blend = True
	gradientpanel.bordertopcolor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DSHADOW)
	gradientpanel.drawbordertop = True
	gradientpanel.label_x = x
	gradientpanel.textalpha = .8
	bitmap = bitmaps.get("gradient_panel")
	if not bitmap:
		bitmap = getbitmap("theme/gradient").GetSubBitmap((0, 1, 8, 15)).ConvertToImage().Mirror(False).ConvertToBitmap()
		image = bitmap.ConvertToImage()
		databuffer = image.GetDataBuffer()
		for i, byte in enumerate(databuffer):
			if byte > "\0":
				databuffer[i] = chr(int(round(ord(byte) * (255.0 / 223.0))))
		bitmap = image.ConvertToBitmap()
		bitmaps["gradient_panel"] = bitmap
	gradientpanel.SetBitmap(bitmap)
	gradientpanel.SetMaxFontSize(11)
	font = gradientpanel.Font
	font.SetWeight(wx.BOLD)
	gradientpanel.Font = font
	gradientpanel.SetLabel(label)
	return gradientpanel


def get_widget(win, id_name_label):
	# hasattr, getattr, setattr silently convert attribute names to byte strings,
	# we have to make sure there's no UnicodeEncodeError
	if (id_name_label == safe_str(safe_unicode(id_name_label), "ascii") and
		hasattr(win, id_name_label)):
		# Attribute name
		try:
			# Trying to access some attributes of wx widgets may
			# raise an exception
			child = getattr(win, id_name_label)
		except:
			return False
		if is_scripting_allowed(win, child):
			return child
	else:
		# ID or label
		try:
			id_name_label = int(id_name_label)
		except ValueError:
			pass
		for child in win.GetAllChildren():
			if (is_scripting_allowed(win, child) and
				(child.Id == id_name_label or child.Name == id_name_label or
				 child.Label == id_name_label)):
				return child


def get_toplevel_window(id_name_label):
	try:
		id_name_label = int(id_name_label)
	except ValueError:
		pass
	for win in reversed(wx.GetTopLevelWindows()):
		if win and (win.Id == id_name_label or win.Name == id_name_label or
					win.Label == id_name_label) and win.IsShown():
			return win


def is_scripting_allowed(win, child):
	return (child and child.TopLevelParent is win and
			child.IsShownOnScreen() and
		    isinstance(child, (CustomCheckBox, aui.AuiNotebook,
							   labelbook.FlatBookBase,  wx.Control, wx.Notebook,
							   wx.grid.Grid)) and
			not isinstance(child, (SimpleBook, aui.AuiTabCtrl,
								   wx.StaticBitmap)))


_elementtable = {}

def format_ui_element(child, format="plain"):
	if child.TopLevelParent:
		if not hasattr(child.TopLevelParent, "_win2name"):
			child.TopLevelParent._win2name = {}
			for name, attr in child.TopLevelParent.__dict__.iteritems():
				if isinstance(attr, wx.Window):
					child.TopLevelParent._win2name[attr] = name
		name = child.TopLevelParent._win2name.get(child, child.Name)
	else:
		name = child.Name
	items = getattr(child, "Items", [])
	value = None
	if not items and isinstance(child, wx.ListCtrl):
		for row in xrange(child.GetItemCount()):
			item = []
			for col in xrange(child.GetColumnCount()):
				item.append(child.GetItem(row, col).GetText())
			items.append(" ".join(item))
		row = child.GetFirstSelected()
		if row != wx.NOT_FOUND:
			value = items[row]
	elif isinstance(child, (aui.AuiNotebook, labelbook.FlatBookBase,
							wx.Notebook)):
		for page_idx in xrange(child.GetPageCount()):
			items.append(child.GetPageText(page_idx))
		page_idx = child.GetSelection()
		if page_idx != wx.NOT_FOUND:
			value = child.GetPageText(page_idx)
	cols = []
	if isinstance(child, wx.grid.Grid):
		for col in xrange(child.GetNumberCols()):
			cols.append(child.GetColLabelValue(col))
	if format != "plain":
		uielement = {"class": child.__class__.__name__, "name": name,
					 "enabled": child.IsEnabled(), "id": child.Id}
		if child.Label:
			uielement["label"] = child.Label
		if isinstance(child, (CustomCheckBox, wx.CheckBox, wx.RadioButton)):
			uielement["checked"] = child.GetValue()
		elif hasattr(child, "GetValue"):
			uielement["value"] = child.GetValue()
		elif hasattr(child, "GetStringSelection"):
			uielement["value"] = child.GetStringSelection()
		elif value is not None:
			uielement["value"] = value
		if items:
			uielement["items"] = items
		if cols:
			uielement["cols"] = cols
			uielement["rows"] = child.GetNumberRows()
		return uielement
	return "%s %s %s%s %s%s%s%s" % (child.__class__.__name__, child.Id,
									sp.list2cmdline([name]),
									(child.Label and
									 " " + demjson.encode(child.Label)),
									"enabled" if child.IsEnabled() else "disabled",
									(isinstance(child, (CustomCheckBox, wx.CheckBox,
														wx.RadioButton)) and
									 child.GetValue() and " checked") or
									(getattr(child, "GetValue", "") and
									 not isinstance(child, (CustomCheckBox, wx.CheckBox,
													  wx.RadioButton)) and
									 " value " + demjson.encode(child.GetValue())) or
									(getattr(child, "GetStringSelection", "") and
									 " value " + demjson.encode(child.GetStringSelection())) or
									(value is not None and " value " +
									 demjson.encode(value) or ""),
									(items and " items " +
									 demjson.encode(items).strip("[]").replace('","', '" "') or
									 ""),
									(cols and " rows %s cols %s" %
									 (child.GetNumberRows(),
									  demjson.encode(cols).strip("[]").replace('","', '" "')) or
									 ""))


def restore_path_dialog_classes():
	wx.DirDialog = _DirDialog
	wx.FileDialog = _FileDialog


def test():
	config.initcfg()
	lang.init()
	def key_handler(self, event):
		if event.GetEventType() == wx.EVT_CHAR_HOOK.typeId:
			print "Received EVT_CHAR_HOOK", event.GetKeyCode(), repr(unichr(event.GetKeyCode()))
		elif event.GetEventType() == wx.EVT_KEY_DOWN.typeId:
			print "Received EVT_KEY_DOWN", event.GetKeyCode(), repr(unichr(event.GetKeyCode()))
		elif event.GetEventType() == wx.EVT_MENU.typeId:
			print "Received EVT_MENU", self.id_to_keycode.get(event.GetId()), repr(unichr(self.id_to_keycode.get(event.GetId())))
		event.Skip()
			
	ProgressDialog.key_handler = key_handler
	SimpleTerminal.key_handler = key_handler
	
	app = BaseApp(0)
	style = (wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME | wx.PD_CAN_ABORT |
			 wx.PD_SMOOTH)
	p = ProgressDialog(msg="".join(("Test " * 5)), maximum=10000, style=style,
					   pauseable=True, fancy=not "+fancy" in sys.argv[1:])
	#t = SimpleTerminal(start_timer=False)
	app.MainLoop()

if __name__ == "__main__":
	test()
