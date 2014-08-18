# -*- coding: utf-8 -*-

from time import gmtime, strftime, time
import math
import os
import re
import string
import sys

import config
from config import (defaults, getbitmap, getcfg, geticon, 
					get_verified_path, setcfg)
from debughelpers import getevtobjname, getevttype, handle_error
from log import log as log_, safe_print
from meta import name as appname
from options import debug
from util_io import StringIOu as StringIO
from util_os import waccess
from util_str import safe_unicode, wrap
from wxaddons import (CustomEvent, FileDrop as _FileDrop,
					  adjust_font_size_for_gcdc, get_dc_font_size,
					  get_platform_window_decoration_size, wx,
					  BetterWindowDisabler)
from wxfixes import GenBitmapButton, GTKMenuItemGetFixedLabel, set_bitmap_labels
from lib.agw import labelbook
from lib.agw.gradientbutton import GradientButton, HOVER
from lib.agw.fourwaysplitter import (_TOLERANCE, FLAG_CHANGED, FLAG_PRESSED,
									 NOWHERE, FourWaySplitter,
									 FourWaySplitterEvent)
import localization as lang
import util_str

import floatspin
import wx.lib.filebrowsebutton as filebrowse

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
				   wx.WXK_NUMPAD_ENTER,
				   wx.WXK_NUMPAD_EQUAL,
				   wx.WXK_NUMPAD_DIVIDE,
				   wx.WXK_NUMPAD_MULTIPLY,
				   wx.WXK_NUMPAD_SUBTRACT]


def Property(func):
	return property(**func())


class AboutDialog(wx.Dialog):

	def __init__(self, *args, **kwargs):
		kwargs["style"] = wx.DEFAULT_DIALOG_STYLE & ~(wx.RESIZE_BORDER | 
		   wx.RESIZE_BOX | wx.MAXIMIZE_BOX)
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
		self.closebtn = wx.Button(self, -1, lang.getstr("ok"))
		self.Bind(wx.EVT_BUTTON, self.OnClose, id=self.closebtn.GetId())
		items += [self.closebtn, (1, 16)]
		pointsize = 10
		for item in items:
			if isinstance(item, wx.Window):
				font = item.GetFont()
				if item.GetLabel() and font.GetPointSize() > pointsize:
					font.SetPointSize(pointsize)
					item.SetFont(font)
			self.sizer.Add(item, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 0)


class BaseFrame(wx.Frame):

	""" Main frame base class. """
	
	def __init__(self, *args, **kwargs):
		wx.Frame.__init__(self, *args, **kwargs)

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
				if not hasattr(menu, "_Label"):
					# Backup un-translated label
					menu._Label = label
				menubar.SetMenuLabel(menu_pos, "&" + lang.getstr(
									 GTKMenuItemGetFixedLabel(menu._Label)))
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
								  BitmapBackgroundPanelText)):
				if not hasattr(child, "_Label"):
					# Backup un-translated label
					label = child._Label = child.Label
				else:
					# Restore un-translated label
					label = child._Label
				translated = lang.getstr(label)
				if translated != label:
					if isinstance(child, wx.Button):
						translated = translated.replace("&", "&&")
					child.Label = translated
				if child.ToolTip:
					if not hasattr(child, "_ToolTipString"):
						# Backup un-translated tooltip
						tooltipstr = child._ToolTipString = child.ToolTip.Tip
					else:
						# Restore un-translated tooltip
						tooltipstr = child._ToolTipString
					translated = lang.getstr(tooltipstr)
					if translated != tooltipstr:
						child.SetToolTipString(wrap(translated, 72))
	
	def update_layout(self):
		""" Update main window layout. """
		minsize, clientsize = self.Sizer.MinSize, self.ClientSize
		if ((minsize[0] > clientsize[0] or minsize[1] > clientsize[1] or not
			 getattr(self, "_layout")) and not self.IsIconized() and
			not self.IsMaximized()):
			self.Sizer.SetMinSize((max(minsize[0], clientsize[0]),
								   max(minsize[1], clientsize[1])))
			self.GetSizer().SetSizeHints(self)
			self.GetSizer().Layout()
			self.Sizer.SetMinSize((-1, -1))
			self._layout = True
		else:
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


class BaseInteractiveDialog(wx.Dialog):

	""" Base class for informational and confirmation dialogs """
	
	def __init__(self, parent=None, id=-1, title=appname, msg="", 
				 ok="OK", bitmap=None, pos=(-1, -1), size=(400, -1), 
				 show=True, log=True, 
				 style=wx.DEFAULT_DIALOG_STYLE, nowrap=False, wrap=70):
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
		wx.Dialog.__init__(self, parent, id, title, pos, size, style)
		if sys.platform == "win32":
			bgcolor = self.BackgroundColour
			self.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))
		self.SetPosition(pos)  # yes, this is needed
		self.SetIcons(config.get_icon_bundle([256, 48, 32, 16], appname))
		
		self.Bind(wx.EVT_SHOW, self.OnShow, self)

		margin = 12

		self.sizer0 = wx.BoxSizer(wx.VERTICAL)
		self.SetSizer(self.sizer0)
		if bitmap:
			self.sizer1 = wx.FlexGridSizer(1, 2)
		else:
			self.sizer1 = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer2 = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer3 = wx.FlexGridSizer(0, 1)
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
		if not wx.GetApp().IsActive() and wx.GetApp().GetTopWindow():
			wx.GetApp().GetTopWindow().RequestUserAttention()

	def OnClose(self, event):
		if event.GetEventObject() == self:
			id = wx.ID_OK
		else:
			id = event.GetId()
		self.EndModal(id)

	def Show(self, show=True):
		self.set_position()
		return wx.Dialog.Show(self, show)

	def ShowModal(self):
		self.set_position()
		return wx.Dialog.ShowModal(self)

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
			if self.repeat_sub_bitmap_h:
				sub_bmp = bmp.GetSubBitmap(self.repeat_sub_bitmap_h)
				sub_img = sub_bmp.ConvertToImage()
				sub_img.Rescale(self.GetSize()[0] -
								bmp.GetSize()[0],
								bmp.GetSize()[1],
								quality=self.scalequality)
				dc.DrawBitmap(sub_img.ConvertToBitmap(), bmp.GetSize()[0], 0)
		if self.drawbordertop:
			pen = wx.Pen(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT), 1, wx.SOLID)
			pen.SetCap(wx.CAP_BUTT)
			dc.SetPen(pen)
			dc.DrawLine(0, 0, self.GetSize()[0], 0)
		if self.drawborderbtm:
			pen = wx.Pen(wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DSHADOW), 1, wx.SOLID)
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
				color = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT)
				dc.SetTextForeground(color)
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
				 style=wx.DEFAULT_DIALOG_STYLE, nowrap=False, wrap=70):
		BaseInteractiveDialog.__init__(self, parent, id, title, msg, ok, 
									   bitmap, pos, size, show=False, 
									   log=log, style=style,
									   nowrap=nowrap, wrap=wrap)

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
		
		self.Fit()

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

	def AcceptsFocusFromKeyboard(self):
		return False
	
	def Disable(self):
		self.Enable(False)
	
	def Enable(self, enable=True):
		self.textControl.Enable(enable and self.history != [""])
		self.browseButton.Enable(enable)

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
			tempValue = None
		self.history = value
		control.Clear()
		for path in value:
			control.Append(os.path.basename(path))
		if tempValue:
			self.history.append(tempValue)
			control.Append(os.path.basename(tempValue))
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
			self.textControl.Append(os.path.basename(value))
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
		if self.history:
			history = self.history
			self.history = []
			self.SetHistory(history)
		if sys.platform == "darwin" and wx.VERSION > (2, 9):
			# Prevent 1px cut-off at left-hand side
			box.Add((1, 1))
		box.Add(self.textControl, 1, wx.ALIGN_CENTER_VERTICAL | wx.TOP |
									 wx.BOTTOM, 4)

		self.browseButton = self.createBrowseButton()
		box.Add(self.browseButton, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)

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


class FileDrop(_FileDrop):
	
	def __init__(self, *args, **kwargs):
		self.parent = kwargs.pop("parent")
		_FileDrop.__init__(self, *args, **kwargs)
		self.unsupported_handler = self.drop_unsupported_handler

	def drop_unsupported_handler(self):
		"""
		Drag'n'drop handler for unsupported files. 
		
		Shows an error message.
		
		"""
		files = self._filenames
		InfoDialog(self.parent, msg=lang.getstr("error.file_type_unsupported") +
									"\n\n" + "\n".join(files), 
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
		self._select_in_progress = False
		self.alternate_cell_background_color = True
		self.alternate_col_label_background_color = False
		self.alternate_row_label_background_color = True
		self.draw_col_labels = True
		self.draw_row_labels = True
		self.draw_horizontal_grid_lines = True
		self.draw_vertical_grid_lines = True
		self.selection_alpha = 1.0
		self.show_cursor_outline = True

	def GetColLeftRight(self, col):
		c = 0
		left = 0
		while c < col:
			left += self.GetColSize(c)
			c += 1
		right = left + self.GetColSize(col) - 1
		return left, right

	def GetRowTopBottom(self, row):
		r = 0
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
						clip += [[]]
						i = row
						offset = 0
					# Skip cols without label
					if self.GetColLabelSize() and not self.GetColLabelValue(col):
						offset += 1
						continue
					if col - offset < start_col:
						start_col = col - offset
					while len(clip[-1]) - 1 < col - offset:
						clip[-1] += [""]
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
							grid += [[]]
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
							grid[-1] += [None]
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
					self.BeginBatch()
					for row, col in self.GetSelection():
						if row > -1 and col > -1 and not self.IsReadOnly(row, col):
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

		if getattr(self, "CalcColLabelsExposed", None):
			# wxPython >= 2.8.10
			cols = self.CalcColLabelsExposed(window.GetUpdateRegion())
			if cols == [-1]:
				return
		else:
			# wxPython < 2.8.10
			cols = xrange(self.GetNumberCols())
			if not cols:
				return

		x, y = self.CalcUnscrolledPosition((0,0))
		pt = dc.GetDeviceOrigin()
		dc.SetDeviceOrigin(pt.x-x, pt.y)
		for col in cols:
			left, right = self.GetColLeftRight(col)
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

		if getattr(self, "CalcRowLabelsExposed", None):
			# wxPython >= 2.8.10
			rows = self.CalcRowLabelsExposed(window.GetUpdateRegion())
			if rows == [-1]:
				return
		else:
			# wxPython < 2.8.10
			rows = xrange(self.GetNumberRows())
			if not rows:
				return

		x, y = self.CalcUnscrolledPosition((0,0))
		pt = dc.GetDeviceOrigin()
		dc.SetDeviceOrigin(pt.x, pt.y-y)
		for row in rows:
			top, bottom = self.GetRowTopBottom(row)
			rect = wx.Rect()
			rect.top = top
			rect.bottom = bottom
			rect.x = 0
			rect.width = self.GetRowLabelSize()

			renderer = self._row_label_renderers.get(row,
													 self._default_row_label_renderer)

			renderer.Draw(self, dc, rect, row)

	def OnResize(self, event):
		for row, col in self.GetSelection():
			cell_renderer = self.GetCellRenderer(row, col)
			if (isinstance(cell_renderer, CustomCellRenderer) and
				cell_renderer._selectionbitmaps):
				# On resize, we need to tell any CustomCellRenderer that its
				# bitmaps are no longer valid and are garbage collected
				cell_renderer._selectionbitmaps = {}
		event.Skip()
        
	def SetColLabelRenderer(self, row, renderer):
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
			self.MakeCellVisible(row, max(self.GetGridCursorCol(), 0))
			self.SelectRow(row)
			self._anchor_row = row
		if self.IsSelection():
			if shift:
				self._select_in_progress = True
				rows = self.GetSelectionRows()
				sel = range(min(self._anchor_row, row), max(self._anchor_row, row))
				desel = []
				add = []
				for i in rows:
					if i not in sel:
						desel += [i]
				for i in sel:
					if i not in rows:
						add += [i]
				if len(desel) >= len(add):
					# in this case deselecting rows will take as long or longer than selecting, so use SelectRow to speed up the operation
					self.SelectRow(row)
				else:
					for i in desel:
						self.DeselectRow(i)
				for i in add:
					self.SelectRow(i, True)
				self._select_in_progress = False
				return False
			elif ctrl:
				if self.IsInSelection(row, 0):
					self._select_in_progress = True
					self.DeselectRow(row)
					self._select_in_progress = False
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
		wx.grid.PyGridCellRenderer.__init__(self, *args, **kwargs)
		self.specialbitmap = getbitmap("theme/checkerboard-10x10x2-333-444")
		self._selectionbitmaps = {}

	def Clone(self):
		return self.__class__()

	def Draw(self, grid, attr, dc, rect, row, col, isSelected):
		orect = rect
		if col == grid.GetNumberCols() - 1:
			# Last column
			w = max(grid.ClientSize[0] - rect[0], rect[2])
			rect = wx.Rect(rect[0], rect[1], w, rect[3])
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
		CustomCellRenderer.__init__(self, *args, **kwargs)
		self._bitmap = geticon(16, "checkmark")
		self._bitmap_unchecked = geticon(16, "x")

	def DrawLabel(self, grid, dc, rect, row, col):
		if grid.GetCellValue(row, col):
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
			if getattr(grid, "draw_horizontal_grid_lines", True) or mavericks:
				dc.DrawLine(rect[0], rect[1] + rect[3] - 1, rect[0] + rect[2] - 1,
							rect[1] + rect[3] - 1)
			if getattr(grid, "draw_vertical_grid_lines", True):
				dc.DrawLine(rect[0] + rect[2] - 1, rect[1],
							rect[0] + rect[2] - 1, rect[3])
		if getattr(grid, "draw_col_labels", True) and col > -1:
			dc.SetFont(grid.GetLabelFont())
			if mavericks:
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


class InfoDialog(BaseInteractiveDialog):

	""" Informational dialog with OK button """

	def __init__(self, parent=None, id=-1, title=appname, msg="", 
				 ok="OK", bitmap=None, pos=(-1, -1), size=(400, -1), 
				 show=True, log=True):
		BaseInteractiveDialog.__init__(self, parent, id, title, msg, ok, 
									   bitmap, pos, size, show, log)


class InvincibleFrame(wx.Frame):

	""" A frame that won't be destroyed when closed """

	def __init__(self, parent=None, id=-1, title="", pos=None, size=None, 
				 style=wx.DEFAULT_FRAME_STYLE):
		wx.Frame.__init__(self, parent, id, title, pos, size, style)
		self.Bind(wx.EVT_CLOSE, self.OnClose, self)

	def OnClose(self, event):
		self.Hide()


class LogWindow(InvincibleFrame):

	""" A log-type window with Clear and Save As buttons """

	def __init__(self, parent=None, id=-1):
		InvincibleFrame.__init__(self, parent, id, 
								 lang.getstr("infoframe.title"), 
								 pos=(int(getcfg("position.info.x")), 
									  int(getcfg("position.info.y"))), 
								 style=wx.DEFAULT_FRAME_STYLE)
		self.last_visible = False
		self.panel = wx.Panel(self, -1)
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		self.panel.SetSizer(self.sizer)
		self.log_txt = wx.TextCtrl(self.panel, -1, "", style=wx.TE_MULTILINE | 
															 wx.TE_READONLY)
		if sys.platform == "win32":
			font = wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, 
													  wx.FONTWEIGHT_NORMAL,
													  face="Consolas")
		elif sys.platform == "darwin":
			font = wx.Font(11, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, 
													   wx.FONTWEIGHT_NORMAL,
													   face="Monaco")
		else:
			font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, 
													   wx.FONTWEIGHT_NORMAL)
		self.log_txt.SetFont(font)
		self.sizer.Add(self.log_txt, 1, flag=wx.ALL | wx.EXPAND, border=4)
		self.btnsizer = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer.Add(self.btnsizer)
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
		self.SetMinSize((defaults["size.info.w"], defaults["size.info.h"]))
		self.SetSaneGeometry(int(getcfg("position.info.x")), 
							 int(getcfg("position.info.y")), 
							 int(getcfg("size.info.w")), 
							 int(getcfg("size.info.h")))
		self.Bind(wx.EVT_MOVE, self.OnMove)
		self.Bind(wx.EVT_SIZE, self.OnSize)
		self.Children[0].Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy)

	def Log(self, txt):
		self.log_txt.AppendText(txt + os.linesep)
	
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
	
	def __init__(self, title=appname, msg="", maximum=100, parent=None, style=None, 
				 handler=None, keyhandler=None, start_timer=True, pos=None,
				 pauseable=False):
		if style is None:
			style = (wx.PD_APP_MODAL | wx.PD_ELAPSED_TIME |
					 wx.PD_REMAINING_TIME | wx.PD_CAN_ABORT | wx.PD_SMOOTH)
		wx.Dialog.__init__(self, parent, wx.ID_ANY, title)
		if sys.platform == "win32":
			bgcolor = self.BackgroundColour
			self.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))
		self.SetIcons(config.get_icon_bundle([256, 48, 32, 16], appname))
		self.Bind(wx.EVT_CLOSE, self.OnClose, self)
		if not pos:
			self.Bind(wx.EVT_MOVE, self.OnMove, self)
		self.timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, handler or self.OnTimer, self.timer)
		
		self.keepGoing = True
		self.skip = False
		self.paused = False

		margin = 12

		self.sizer0 = wx.BoxSizer(wx.VERTICAL)
		self.SetSizer(self.sizer0)
		self.sizer1 = wx.BoxSizer(wx.VERTICAL)
		self.sizer2 = wx.BoxSizer(wx.HORIZONTAL)
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

		self.msg = wx.StaticText(self, -1, "")
		self.sizer1.Add(self.msg, flag=wx.EXPAND | wx.BOTTOM, border=margin)
		
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

		if style & wx.PD_CAN_ABORT:
			self.cancel = wx.Button(self.buttonpanel, wx.ID_ANY,
									lang.getstr("cancel"))
			self.sizer2.Add(self.cancel)
			self.Bind(wx.EVT_BUTTON, self.OnClose, id=self.cancel.GetId())

		self.pause_continue = wx.Button(self.buttonpanel, wx.ID_ANY,
										lang.getstr("pause"))
		self.sizer2.Prepend((margin, margin))
		self.sizer2.Prepend(self.pause_continue)
		self.Bind(wx.EVT_BUTTON, self.pause_continue_handler,
				  id=self.pause_continue.GetId())
		self.pause_continue.Show(pauseable)

		self.buttonpanel.Layout()
		
		# Use an accelerator table for 0-9, a-z, numpad
		keycodes = range(48, 58) + range(97, 123) + numpad_keycodes
		self.id_to_keycode = {}
		for keycode in keycodes:
			self.id_to_keycode[wx.NewId()] = keycode
		accels = []
		for id, keycode in self.id_to_keycode.iteritems():
			self.Bind(wx.EVT_MENU, keyhandler or self.key_handler, id=id)
			accels += [(wx.ACCEL_NORMAL, keycode, id)]
		self.SetAcceleratorTable(wx.AcceleratorTable(accels))
		
		text_extent = self.msg.GetTextExtent("E")
		w, h = (text_extent[0] * 80, 
				text_extent[1] * 4)
		self.msg.SetMinSize((w, h))
		self.msg.SetSize((w, h))
		self.Fit()
		self.SetMinSize(self.GetSize())
		self.msg.SetLabel(msg.replace("&", "&&"))
		
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
			if self.gauge.GetValue() < self.gauge.GetRange():
				self.Update(self.gauge.GetValue() + 1)
			else:
				self.stop_timer()
				self.Update(self.gauge.GetRange(),
							"Finished. You may now close this window.")
		else:
			self.Pulse("Aborting...")
			if not hasattr(self, "delayed_stop"):
				self.delayed_stop = wx.CallLater(3000, self.stop_timer)
				wx.CallLater(3000, self.Pulse, 
							 "Aborted. You may now close this window.")
	
	def Pulse(self, msg=None):
		if msg and msg != self.msg.Label:
			self.msg.SetLabel(msg)
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
			self.msg.Refresh()
			self.msg.Update()
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
		self.gauge.SetValue(value)
		return self.keepGoing, self.skip
	
	UpdatePulse = Pulse
	
	def elapsed_time_handler(self, event):
		self.elapsed_time.Label = strftime("%H:%M:%S",
										   gmtime(time() - self.time))
	
	def key_handler(self, event):
		pass

	def pause_continue_handler(self, event=None):
		self.paused = not self.paused
		if self.paused:
			self.pause_continue.Label = lang.getstr("continue")
		else:
			self.pause_continue.Label = lang.getstr("pause")
		self.pause_continue.Enable(not event)
		self.Layout()

	def start_timer(self, ms=50):
		self.timer.Start(ms)
		if hasattr(self, "elapsed_timer"):
			self.elapsed_timer.Start(1000)
	
	def stop_timer(self):
		self.timer.Stop()
		if hasattr(self, "elapsed_timer"):
			self.elapsed_timer.Stop()


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
				 keyhandler=None, start_timer=True):
		wx.Frame.__init__(self, parent, id, title, 
								style=wx.DEFAULT_FRAME_STYLE)
		self.SetIcons(config.get_icon_bundle([256, 48, 32, 16], appname))
		
		self.Bind(wx.EVT_CLOSE, self.OnClose, self)
		self.Bind(wx.EVT_MOVE, self.OnMove, self)
		self.timer = wx.Timer(self)
		if handler:
			self.Bind(wx.EVT_TIMER, handler, self.timer)
		
		self.panel = wx.Panel(self, -1)
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		self.panel.SetSizer(self.sizer)
		self.console = wx.TextCtrl(self.panel, -1, "", style=wx.TE_MULTILINE | 
															 wx.TE_READONLY |
															 wx.VSCROLL |
															 wx.NO_BORDER)
		self.console.SetBackgroundColour(wx.BLACK)
		self.console.SetForegroundColour("#808080")
		if sys.platform == "win32":
			font = wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, 
													  wx.FONTWEIGHT_NORMAL,
													  face="Terminal")
		elif sys.platform == "darwin":
			font = wx.Font(11, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, 
													   wx.FONTWEIGHT_NORMAL,
													   face="Monaco")
		else:
			font = wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, 
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
		vscroll_w = self.console.GetSize()[0] - self.console.GetClientRect()[2]
		w, h = (text_extent[0] * 80 + vscroll_w, 
				text_extent[1] * 24)
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
				x = getcfg("position.progress.x", False) or parent.GetScreenPosition()[0]
				y = getcfg("position.progress.y", False) or parent.GetScreenPosition()[1]
		else:
			x = getcfg("position.progress.x")
			y = getcfg("position.progress.y")
		if not placed:
			self.SetSaneGeometry(x, y, w, h)
		
		self.lastmsg = ""
		self.keepGoing = True
		
		self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy, self)
		
		if start_timer:
			self.start_timer()
		
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
	
	def __init__(self, parent=None, id=-1, title=appname, msg="", 
				 bitmap=None, pos=(-1, -1), size=(400, -1), 
				 style=wx.DEFAULT_FRAME_STYLE | wx.FRAME_TOOL_WINDOW, wrap=70):
		InvincibleFrame.__init__(self, parent, id, title, pos, size, style)
		self.SetPosition(pos)  # yes, this is needed
		self.SetIcons(config.get_icon_bundle([256, 48, 32, 16], appname))

		margin = 12
		
		self.panel = wx.Panel(self, -1)
		self.sizer0 = wx.BoxSizer(wx.VERTICAL)
		self.panel.SetSizer(self.sizer0)
		if bitmap:
			self.sizer1 = wx.FlexGridSizer(1, 2)
		else:
			self.sizer1 = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer0.Add(self.sizer1, flag = wx.ALIGN_CENTER | wx.ALL, 
		   border = margin)

		if bitmap:
			self.bitmap = wx.StaticBitmap(self.panel, -1, bitmap, 
			   size = (32, 32))
			self.sizer1.Add(self.bitmap, flag=wx.RIGHT, border=margin)

		self.message = wx.StaticText(self.panel, -1, util_str.wrap(msg, wrap))
		self.message.SetMaxFontSize()
		self.sizer1.Add(self.message)

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
				win0.SetDimensions(0, 0, self._splitx, self._splity)
				win0.Show()
			if win1:
				win1.SetDimensions(self._splitx + barSize, 0, rightw, self._splity)
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
	gradientpanel = BitmapBackgroundPanelText(parent, size=(-1, 23))
	gradientpanel.alpha = .75
	gradientpanel.blend = True
	gradientpanel.drawborderbtm = True
	gradientpanel.label_x = x
	gradientpanel.textalpha = .8
	bitmap = bitmaps.get("gradient_panel")
	if not bitmap:
		bitmap = getbitmap("theme/gradient")
		bitmaps["gradient_panel"] = bitmap
	gradientpanel.SetBitmap(bitmap)
	gradientpanel.SetMaxFontSize(11)
	gradientpanel.SetLabel(label)
	return gradientpanel


def test():
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
	
	app = wx.App(0)
	p = ProgressDialog(msg="".join(("Test " * 5)))
	t = SimpleTerminal(start_timer=False)
	app.MainLoop()

if __name__ == "__main__":
	test()
