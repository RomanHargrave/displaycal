#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

from config import (btn_width_correction, defaults, getcfg, 
					geticon, get_verified_path, setcfg)
from log import log as log_, safe_print
from meta import name as appname
from thread import start_new_thread
from util_str import safe_unicode, wrap
from wxaddons import wx
import localization as lang

if sys.platform == "darwin":
	from util_mac import mac_app_activate

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

	def Layout(self):
		self.sizer.SetSizeHints(self)
		self.sizer.Layout()

	def add_items(self, items):
		pointsize = 10
		for item in items:
			font = item.GetFont()
			if item.GetLabel() and font.GetPointSize() > pointsize:
				font.SetPointSize(pointsize)
				item.SetFont(font)
			self.sizer.Add(item, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 0)


class BaseInteractiveDialog(wx.Dialog):

	""" Base class for informational and confirmation dialogs """
	
	def __init__(self, parent=None, id=-1, title=appname, msg="", 
				 ok="OK", bitmap=None, pos=(-1, -1), size=(400, -1), 
				 show=True, log=True, print_=False):
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
		wx.Dialog.__init__(self, parent, id, title, pos, size)
		self.SetPosition(pos)  # yes, this is needed
		
		self.Bind(wx.EVT_SHOW, self.OnShow, self)

		margin = 12

		self.sizer0 = wx.BoxSizer(wx.VERTICAL)
		self.SetSizer(self.sizer0)
		if bitmap:
			self.sizer1 = wx.FlexGridSizer(1, 2)
		else:
			self.sizer1 = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer2 = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer3 = wx.BoxSizer(wx.VERTICAL)
		self.sizer0.Add(self.sizer1, flag = wx.ALIGN_LEFT | wx.TOP | 
		   wx.RIGHT | wx.LEFT, border = margin)
		self.sizer0.Add(self.sizer2, flag = wx.ALIGN_RIGHT | wx.ALL, 
		   border = margin)

		if bitmap:
			self.bitmap = wx.StaticBitmap(self, -1, bitmap, size=(32, 32))
			self.sizer1.Add(self.bitmap, flag=wx.RIGHT, border=margin)

		self.sizer1.Add(self.sizer3, flag=wx.ALIGN_LEFT)
		self.message = wx.StaticText(self, -1, wrap(msg))
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
		if sys.platform == "darwin" and \
		   (not wx.GetApp().IsActive() or 
			(hasattr(wx.GetApp(), "frame") and not 
			 wx.GetApp().frame.IsShownOnScreen())):
			start_new_thread(mac_app_activate, (.25, wx.GetApp().GetAppName()))
		if show:
			self.ok.SetDefault()
			self.ShowModalThenDestroy(parent)

	def ShowModalThenDestroy(self, parent=None):
		if parent:
			if hasattr(parent, "modaldlg") and parent.modaldlg != None:
				wx.CallLater(250, self.ShowModalThenDestroy, parent)
				return
			parent.modaldlg = self
		self.ShowModal()
		if parent:
			parent.modaldlg = None
		self.Destroy()

	def OnShow(self, event):
		self.SetFocus()

	def OnClose(self, event):
		self.Close(True)


class ConfirmDialog(BaseInteractiveDialog):

	""" Confirmation dialog with OK and Cancel buttons """

	def __init__(self, parent=None, id=-1, title=appname, msg="", 
				 ok="OK", cancel="Cancel", bitmap=None, pos=(-1, -1), 
				 size=(400, -1), alt=None):
		BaseInteractiveDialog.__init__(self, parent, id, title, msg, ok, 
									   bitmap, pos, size, show=False, 
									   log=False)

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
		if event.GetEventObject() == self:
			id = wx.ID_CANCEL
		else:
			id = event.GetId()
		self.EndModal(id)


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
			font = wx.Font(8, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, 
													  wx.FONTWEIGHT_NORMAL)
		else:
			font = wx.Font(11, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, 
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
		self.ScrollToBottom()
	
	def ScrollToBottom(self):
		self.log_txt.ScrollLines(len(self.log_txt.GetValue().splitlines()))

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
								   os.path.basename(getcfg("last_filedialog_path")))
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
				file_.writelines(self.log_txt.GetValue())
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
	
	def __init__(self, title=appname, msg="", maximum=1, parent=None, style=None, 
				 handler=None, start_timer=True):
		if style is None:
			style = wx.PD_APP_MODAL | wx.PD_ELAPSED_TIME | wx.PD_CAN_ABORT | wx.PD_SMOOTH
		wx.ProgressDialog.__init__(self, title, msg, maximum, parent=parent, style=style)
		self.Bind(wx.EVT_CLOSE, self.OnClose, self)
		self.Bind(wx.EVT_MOVE, self.OnMove, self)
		if handler is None:
			handler = self.OnTimer
		self.timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, handler, self.timer)
		
		# custom localization
		for child in self.GetChildren():
			if isinstance(child, wx.Button):
				child.Label = lang.getstr("cancel")
			elif isinstance(child, wx.StaticText) and \
				 "Elapsed time" in child.Label:
				child.Label = lang.getstr("elapsed_time").replace(" ", u"\xa0")
		
		# set size and position	
		self.SetMinSize((500, -1))
		self.SetSize((500, -1))
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
		
		if start_timer:
			self.start_timer()
	
	def OnClose(self, event):
		if not self.timer.IsRunning():
			self.Hide()
		else:
			event.Skip()
		
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
		self.Pulse()
	
	def start_timer(self, ms=50):
		self.timer.Start(ms)
	
	def stop_timer(self):
		self.timer.Stop()


class TooltipWindow(InvincibleFrame):

	""" A tooltip-style window """
	
	def __init__(self, parent=None, id=-1, title=appname, msg="", 
				 bitmap=None, pos=(-1, -1), size=(400, -1), 
				 style=wx.DEFAULT_FRAME_STYLE | wx.FRAME_TOOL_WINDOW):
		InvincibleFrame.__init__(self, parent, id, title, pos, size, style)
		self.SetPosition(pos)  # yes, this is needed

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

		self.message = wx.StaticText(self.panel, -1, wrap(msg))
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
