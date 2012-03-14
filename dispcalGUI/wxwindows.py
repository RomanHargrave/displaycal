#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math
import os
import sys

import config
from config import (btn_width_correction, defaults, getbitmap, getcfg, geticon, 
					get_bitmap_as_icon, get_data_path, get_verified_path, 
					setcfg)
from log import log as log_, safe_print
from meta import name as appname
from thread import start_new_thread
from util_str import safe_unicode
from wxaddons import (FileDrop as _FileDrop, get_dc_font_size,
					  get_platform_window_decoration_size, wx)
from lib.agw import labelbook
from lib.agw.fourwaysplitter import (_TOLERANCE, FLAG_CHANGED, FLAG_PRESSED,
									 NOWHERE, FourWaySplitter,
									 FourWaySplitterEvent)
import localization as lang
import util_str

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


class BaseInteractiveDialog(wx.Dialog):

	""" Base class for informational and confirmation dialogs """
	
	def __init__(self, parent=None, id=-1, title=appname, msg="", 
				 ok="OK", bitmap=None, pos=(-1, -1), size=(400, -1), 
				 show=True, log=True, print_=False, 
				 style=wx.DEFAULT_DIALOG_STYLE, nowrap=False, wrap=70):
		if print_:
			safe_print(msg, log=False)
		if log:
			log_(msg)
		if parent:
			pos = list(pos)
			i = 0
			for coord in pos:
				if coord > -1:
					pos[i] += parent.GetScreenPosition()[i]
				i += 1
			pos = tuple(pos)
		wx.Dialog.__init__(self, parent, id, title, pos, size, style)
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
		self.sizer0.Add(self.sizer2, flag = wx.ALIGN_RIGHT | wx.ALL, 
		   border = margin)

		if bitmap:
			self.bitmap = wx.StaticBitmap(self, -1, bitmap, size=(32, 32))
			self.sizer1.Add(self.bitmap, flag=wx.RIGHT, border=margin)

		self.sizer1.Add(self.sizer3, flag=wx.ALIGN_LEFT)
		msg = msg.replace("&", "&&")
		self.message = wx.StaticText(self, -1, msg if nowrap else
											   util_str.wrap(msg, wrap))
		self.sizer3.Add(self.message)

		btnwidth = 80

		self.ok = wx.Button(self, wx.ID_OK, ok)
		self.ok.SetInitialSize((self.ok.GetSize()[0] + btn_width_correction, 
		   -1))
		self.sizer2.Add(self.ok)
		self.Bind(wx.EVT_BUTTON, self.OnClose, id=wx.ID_OK)

		self.sizer0.SetSizeHints(self)
		self.sizer0.Layout()
		if parent and parent.IsIconized():
			parent.Restore()
		if not pos or pos == (-1, -1):
			self.Center(wx.BOTH)
		elif pos[0] == -1:
			self.Center(wx.HORIZONTAL)
		elif pos[1] == -1:
			self.Center(wx.VERTICAL)
		if not wx.GetApp().IsActive() and wx.GetApp().GetTopWindow():
			wx.CallAfter(wx.GetApp().GetTopWindow().RequestUserAttention)
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
		self.SetFocus()

	def OnClose(self, event):
		if event.GetEventObject() == self:
			id = wx.ID_OK
		else:
			id = event.GetId()
		self.EndModal(id)


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


class BitmapBackgroundPanel(wx.Panel):
	
	""" A panel with a background bitmap and text label """

	def __init__(self, *args, **kwargs):
		wx.Panel.__init__(self, *args, **kwargs)
		self._bitmap = getbitmap("empty")
		self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
		self.Bind(wx.EVT_ERASE_BACKGROUND, self.OnEraseBackground)
	
	def GetBitmap(self):
		return self._bitmap

	def SetBitmap(self, bitmap):
		self._bitmap = bitmap

	def OnEraseBackground(self, event):
		dc = event.GetDC()
		if not dc:
			dc = wx.ClientDC(self)
			rect = self.GetUpdateRegion().GetBox()
			dc.SetClippingRect(rect)
		dc.Clear()
		self._drawbitmap(dc)
	
	def _drawbitmap(self, dc):
		dc.DrawBitmap(self._bitmap, 0, 0)
		pen = wx.Pen(wx.Colour(0x66, 0x66, 0x66), 1, wx.SOLID)
		pen.SetCap(wx.CAP_BUTT)
		dc.SetPen(pen)
		dc.DrawLine(0, self.GetSize()[1] - 1, self.GetSize()[0], self.GetSize()[1] - 1)


class BitmapBackgroundPanelText(BitmapBackgroundPanel):
	
	""" A panel with a background bitmap and text label """

	def __init__(self, *args, **kwargs):
		BitmapBackgroundPanel.__init__(self, *args, **kwargs)
		self._label = ""
		self.Unbind(wx.EVT_ERASE_BACKGROUND)
		self.Bind(wx.EVT_PAINT, self.OnPaint)
	
	def _set_font(self, dc):
		try:
			dc = wx.GCDC(dc)
		except Exception, exception:
			pass
		font = self.GetFont()
		font.SetPointSize(get_dc_font_size(font.GetPointSize(), dc))
		dc.SetFont(font)
		return dc
	
	def GetLabel(self):
		return self._label
	
	def SetLabel(self, label):
		self._label = label

	def OnPaint(self, dc):
		dc = wx.PaintDC(self)
		self._drawbitmap(dc)
		dc = self._set_font(dc)
		w1, h1 = self.GetTextExtent(self.GetLabel())
		w2, h2 = dc.GetTextExtent(self.GetLabel())
		w = (max(w1, w2) - min(w1, w2)) / 2.0 + min(w1, w2)
		h = (max(h1, h2) - min(h1, h2)) / 2.0 + min(h1, h2)
		x, y = (self.GetSize()[0] / 2.0 - w / 2.0,
				self.GetSize()[1] / 2.0 - h / 2.0)
		dc.SetTextForeground(wx.Colour(214, 214, 214))
		dc.DrawText(self.GetLabel(), x + 1, y + 1)
		dc.SetTextForeground(self.GetForegroundColour())
		dc.DrawText(self.GetLabel(), x, y)


class ConfirmDialog(BaseInteractiveDialog):

	""" Confirmation dialog with OK and Cancel buttons """

	def __init__(self, parent=None, id=-1, title=appname, msg="", 
				 ok="OK", cancel="Cancel", bitmap=None, pos=(-1, -1), 
				 size=(400, -1), alt=None, log=False, print_=False, 
				 style=wx.DEFAULT_DIALOG_STYLE, nowrap=False, wrap=70):
		BaseInteractiveDialog.__init__(self, parent, id, title, msg, ok, 
									   bitmap, pos, size, show=False, 
									   log=log, print_=print_, style=style,
									   nowrap=nowrap, wrap=wrap)

		self.Bind(wx.EVT_CLOSE, self.OnClose, self)

		margin = 12

		if alt:
			self.alt = wx.Button(self, -1, alt)
			self.alt.SetInitialSize((self.alt.GetSize()[0] + 
			   btn_width_correction, -1))
			self.sizer2.Prepend((margin, margin))
			self.sizer2.Prepend(self.alt)
			self.Bind(wx.EVT_BUTTON, self.OnClose, id=self.alt.GetId())

		self.cancel = wx.Button(self, wx.ID_CANCEL, cancel)
		self.cancel.SetInitialSize((self.cancel.GetSize()[0] + 
		   btn_width_correction, -1))
		self.sizer2.Prepend((margin, margin))
		self.sizer2.Prepend(self.cancel)
		self.Bind(wx.EVT_BUTTON, self.OnClose, id=wx.ID_CANCEL)
		
		self.Fit()

	def OnClose(self, event):
		if hasattr(self, "OnCloseIntercept"):
			self.OnCloseIntercept(event)
			return
		if event.GetEventObject() == self:
			id = wx.ID_CANCEL
		else:
			id = event.GetId()
		self.EndModal(id)


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


class InfoDialog(BaseInteractiveDialog):

	""" Informational dialog with OK button """

	def __init__(self, parent=None, id=-1, title=appname, msg="", 
				 ok="OK", bitmap=None, pos=(-1, -1), size=(400, -1), 
				 show=True, log=True, print_=False):
		BaseInteractiveDialog.__init__(self, parent, id, title, msg, ok, 
									   bitmap, pos, size, show, log, print_)


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
		self.save_as_btn = wx.BitmapButton(self.panel, -1, 
										   geticon(16, "media-floppy"), 
										   style = wx.NO_BORDER)
		self.save_as_btn.Bind(wx.EVT_BUTTON, self.OnSaveAs)
		self.save_as_btn.SetToolTipString(lang.getstr("save_as"))
		self.btnsizer.Add(self.save_as_btn, flag=wx.ALL, border=4)
		self.clear_btn = wx.BitmapButton(self.panel, -1, 
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


class ProgressDialog(wx.ProgressDialog):
	
	""" A progress dialog. """
	
	def __init__(self, title=appname, msg="", maximum=100, parent=None, style=None, 
				 handler=None, keyhandler=None, start_timer=True, pos=None):
		if style is None:
			style = wx.PD_APP_MODAL | wx.PD_ELAPSED_TIME | wx.PD_CAN_ABORT | wx.PD_SMOOTH
		wx.ProgressDialog.__init__(self, title, "", maximum, parent=parent, style=style)
		self.SetIcons(config.get_icon_bundle([256, 48, 32, 16], appname))
		self.Bind(wx.EVT_CLOSE, self.OnClose, self)
		if not pos:
			self.Bind(wx.EVT_MOVE, self.OnMove, self)
		self.timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, handler or self.OnTimer, self.timer)
		
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
		
		# custom localization
		self.msg = None
		for child in self.GetChildren():
			if isinstance(child, wx.Button):
				child.Label = lang.getstr("cancel")
			elif isinstance(child, wx.StaticText):
				if "Elapsed time" in child.Label:
					child.Label = lang.getstr("elapsed_time").replace(" ", u"\xa0")
				elif not child.Label:
					self.msg = child
					#child.SetBackgroundColour(wx.LIGHT_GREY)
					child.SetWindowStyle(wx.ST_NO_AUTORESIZE)
		
		if self.msg:
			##if sys.platform not in ("darwin", "win32"):
			text_extent = self.msg.GetTextExtent("E")
			w, h = (text_extent[0] * 80, 
					text_extent[1] * 4)
			self.msg.SetMinSize((w, h))
			self.msg.SetSize((w, h))
			##else:
			##self.msg.Freeze()
			##self.msg.SetLabel("\n".join(["E" * 80] * 4))
			##self.msg.Fit()
			##self.msg.Thaw()
		self.Fit()
		self.SetMinSize(self.GetSize())
		if self.msg:
			self.msg.SetLabel(msg)
		else:
			self.Pulse(msg)
		
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
	
	def OnClose(self, event):
		if not self.timer.IsRunning():
			self.Destroy()
		else:
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
		if getattr(self, "keepGoing", True):
			if not hasattr(self, "i"):
				self.i = 0
			if self.i < 100:
				self.i += 1
				if self.i == 100:
					self.stop_timer()
				self.keepGoing, self.skip = self.Update(self.i)
				if self.i == 100:
					self.Destroy()
		if not self.keepGoing:
			self.Pulse("Aborting...")
			if not hasattr(self, "delayed_stop"):
				self.delayed_stop = wx.CallLater(3000, self.stop_timer)
				wx.CallLater(3000, self.Pulse, 
							 "Aborted. You may now close this window.")
	
	def key_handler(self, event):
		pass
	
	def start_timer(self, ms=50):
		self.timer.Start(ms)
	
	def stop_timer(self):
		self.timer.Stop()


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
		##accels = []
		##for id, keycode in self.id_to_keycode.iteritems():
			##self.Bind(wx.EVT_MENU, keyhandler or self.key_handler, id=id)
			##accels += [(wx.ACCEL_NORMAL, keycode, id)]
		##self.SetAcceleratorTable(wx.AcceleratorTable(accels))
		
		# set size
		text_extent = self.console.GetTextExtent(" ")
		vscroll_w = self.console.GetSize()[0] - self.console.GetClientRect()[2]
		##w, h = (self.console.GetCharWidth() * 80 + vscroll_w, 
				##self.console.GetCharHeight() * 25)
		w, h = (text_extent[0] * 80 + vscroll_w, 
				text_extent[1] * 24)
		##self.console.SetMinSize((w, h))
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
			rightw = totw - self._splitx
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

		backColour = self.GetBackgroundColour()
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
		
		dc.SetPen(wx.Pen(wx.Colour(178, 178, 178), 1))
		dc.DrawLine(splitx, 0, splitx, height)
		dc.DrawLine(splitx + self._GetSashSize() - 1, 0, splitx + self._GetSashSize() - 1, height)
	
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
