#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

from config import (btn_width_correction, defaults, getcfg, 
					geticon, get_verified_path, setcfg)
from meta import name as appname
from thread import start_new_thread
from util_str import wrap
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
				 show=True, logit=True):
		oparent = parent
		if oparent:
			gparent = oparent.GetGrandParent()
			if gparent is None:
				gparent = oparent
			if hasattr(gparent, "worker") and \
			   hasattr(gparent.worker, "progress_parent") and \
			   (gparent.worker.progress_parent.progress_start_timer.IsRunning() or 
			    gparent.worker.progress_parent.progress_timer.IsRunning()):
				gparent.worker.progress_parent.progress_start_timer.Stop()
				if hasattr(gparent.worker.progress_parent, "progress_dlg"):
					gparent.worker.progress_parent.progress_timer.Stop()
					wx.CallAfter(gparent.worker.progress_parent.progress_dlg.Hide)
				wx.CallAfter(self.__init__, oparent, id, title, msg, ok, 
				   bitmap, pos, size)
				return
			if not oparent.IsShownOnScreen():
				# Do not center on parent if not visible
				parent = None 
			else:
				pos = list(pos)
				i = 0
				for coord in pos:
					if coord > -1:
						pos[i] += parent.GetScreenPosition()[i]
					i += 1
				pos = tuple(pos)
		else:
			parent = None
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
			self.ShowModalThenDestroy(oparent)

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
				 size=(400, -1)):
		BaseInteractiveDialog.__init__(self, parent, id, title, msg, ok, 
									   bitmap, pos, size, show=False, 
									   logit=False)

		self.Bind(wx.EVT_CLOSE, self.OnClose, self)

		margin = 12

		self.cancel = wx.Button(self, wx.ID_CANCEL, cancel)
		self.cancel.SetInitialSize((self.cancel.GetSize()[0] + 
		   btn_width_correction, -1))
		self.sizer2.Prepend((margin, margin))
		self.sizer2.Prepend(self.cancel)
		self.Bind(wx.EVT_BUTTON, self.OnClose, id=wx.ID_CANCEL)

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
				 show=True, logit=True):
		BaseInteractiveDialog.__init__(self, parent, id, title, msg, ok, 
									   bitmap, pos, size, show, logit)


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
								 style=wx.DEFAULT_FRAME_STYLE | 
									   wx.FRAME_TOOL_WINDOW)
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
		wx.CallAfter(self.log_txt.AppendText, txt + os.linesep)

	def OnClear(self, event):
		self.log_txt.SetValue("")

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
		defaultDir, defaultFile = get_verified_path("last_filedialog_path")
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
				InfoDialog(self, msg=unicode(str(exception), enc, "replace"), 
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
