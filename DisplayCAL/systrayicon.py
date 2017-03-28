# -*- coding: utf-8 -*-

"""
Drop-In replacement for wx.TaskBarIcon

This one won't stop showing updates to the icon like wx.TaskBarIcon

"""

import os
import sys

import win32api
import win32con
import win32gui
import winerror
import wx


class Menu(wx.EvtHandler):

	def __init__(self):
		wx.EvtHandler.__init__(self)
		self.hmenu = win32gui.CreatePopupMenu()
		self.MenuItems = []
		self._menuitems = {}

	def _Append(self, flags, id, text):
		win32gui.AppendMenu(self.hmenu, flags, id, text)

	def Append(self, id, text, help=u"", kind=wx.ITEM_NORMAL):
		return self.AppendItem(MenuItem(self, id, text, help, kind))

	def AppendCheckItem(self, id, text, help=u""):
		return self.Append(id, text, help, wx.ITEM_CHECK)

	def AppendItem(self, item):
		flags = 0
		if item.Kind == wx.ITEM_SEPARATOR:
			flags |= win32con.MF_SEPARATOR
		else:
			if not item.Enabled:
				flags |= win32con.MF_DISABLED
		self._Append(flags, item.Id, item.ItemLabel)
		self.MenuItems.append(item)
		self._menuitems[item.Id] = item
		if item.Checked:
			self.Check(item.Id)
		return item

	def AppendRadioItem(self, id, text, help=u""):
		return self.Append(id, text, help, wx.ITEM_RADIO)

	def AppendSeparator(self):
		return self.Append(-1, u"", kind=wx.ITEM_SEPARATOR)

	def Check(self, id, check=True):
		flags = win32con.MF_BYCOMMAND
		if self._menuitems[id].Kind == wx.ITEM_RADIO:
			if not check:
				return
			id1 = id
			id2 = id
			index = self.MenuItems.index(self._menuitems[id])
			menuitems = self.MenuItems[:index]
			while menuitems:
				first_item = menuitems.pop()
				if first_item.Kind == wx.ITEM_RADIO:
					id1 = first_item.Id
					first_item.Checked = False
				else:
					break
			menuitems = self.MenuItems[index:]
			menuitems.reverse()
			while menuitems:
				last_item = menuitems.pop()
				if last_item.Kind == wx.ITEM_RADIO:
					id2 = last_item.Id
					last_item.Checked = False
				else:
					break
			win32gui.CheckMenuRadioItem(self.hmenu, id1, id2, id, flags)
		else:
			if check:
				flags |= win32con.MF_CHECKED
			win32gui.CheckMenuItem(self.hmenu, id, flags)
		self._menuitems[id].Checked = check

	def Enable(self, id, enable=True):
		flags = win32con.MF_BYCOMMAND
		if not enable:
			flags |= win32con.MF_DISABLED
		win32gui.EnableMenuItem(self.hmenu, id, flags)
		self._menuitems[id].Enabled = enable


class MenuItem(object):

	def __init__(self, menu, id=-1, text=u"", help=u"", kind=wx.ITEM_NORMAL):
		if id == -1:
			id = wx.NewId()
		self.Menu = menu
		self.Id = id
		self.ItemLabel = text
		self.Help = help
		self.Kind = kind
		self.Enabled = True
		self.Checked = False

	def Check(self, check=True):
		self.Checked = check
		if self.Id in self.Menu._menuitems:
			self.Menu.Check(self.Id, check)

	def Enable(self, enable=True):
		self.Enabled = enable
		if self.Id in self.Menu._menuitems:
			self.Menu.Enable(self.Id, enable)


class SysTrayIcon(wx.EvtHandler):

	def __init__(self):
		wx.EvtHandler.__init__(self)
		msg_TaskbarCreated = win32gui.RegisterWindowMessage("TaskbarCreated")
		message_map = {msg_TaskbarCreated: self.OnTaskbarCreated,
					   win32con.WM_DESTROY: self.OnDestroy,
					   win32con.WM_COMMAND: self.OnCommand,
					   win32con.WM_USER + 20: self.OnTaskbarNotify}

		wc = win32gui.WNDCLASS()
		hinst = wc.hInstance = win32api.GetModuleHandle(None)
		wc.lpszClassName = "SysTrayIcon"
		wc.style = win32con.CS_VREDRAW | win32con.CS_HREDRAW
		wc.hCursor = win32api.LoadCursor(0, win32con.IDC_ARROW)
		wc.hbrBackground = win32con.COLOR_WINDOW
		wc.lpfnWndProc = message_map

		classAtom = win32gui.RegisterClass(wc)

		style = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU
		self.hwnd = win32gui.CreateWindow(wc.lpszClassName, "SysTrayIcon",
										  style, 0, 0, win32con.CW_USEDEFAULT,
										  win32con.CW_USEDEFAULT, 0, 0, hinst,
										  None)
		win32gui.UpdateWindow(self.hwnd)
		self._nid = None
		self.menu = None
		self.Bind(wx.EVT_TASKBAR_RIGHT_UP, self.OnRightUp)

	def CreatePopupMenu(self):
		""" Override this method in derived classes """
		if self.menu:
			return self.menu
		menu = Menu()
		item = menu.AppendRadioItem(-1, "Radio 1")
		item.Check()
		menu.Bind(wx.EVT_MENU, lambda event: menu.Check(event.Id,
														event.IsChecked()),
				  id=item.Id)
		item = menu.AppendRadioItem(-1, "Radio 2")
		menu.Bind(wx.EVT_MENU, lambda event: menu.Check(event.Id,
														event.IsChecked()),
				  id=item.Id)
		menu.AppendSeparator()
		item = menu.AppendCheckItem(-1, "Checkable")
		item.Check()
		menu.Bind(wx.EVT_MENU, lambda event: menu.Check(event.Id,
														event.IsChecked()),
				  id=item.Id)
		menu.AppendSeparator()
		item = menu.AppendCheckItem(-1, "Disabled")
		item.Enable(False)
		menu.AppendSeparator()
		item = menu.Append(-1, "Exit")
		menu.Bind(wx.EVT_MENU, lambda event: win32gui.DestroyWindow(self.hwnd),
				  id=item.Id)
		return menu

	def OnCommand(self, hwnd, msg, wparam, lparam):
		event = wx.CommandEvent(wx.wxEVT_COMMAND_MENU_SELECTED)
		event.Id = win32api.LOWORD(wparam)
		item = self.menu._menuitems[event.Id]
		if item.Kind == wx.ITEM_RADIO:
			event.SetInt(1)
		elif item.Kind == wx.ITEM_CHECK:
			event.SetInt(int(not item.Checked))
		self.menu.ProcessEvent(event)

	def OnDestroy(self, hwnd, msg, wparam, lparam):
		self.RemoveIcon()
		if not wx.GetApp() or not wx.GetApp().IsMainLoopRunning():
			win32gui.PostQuitMessage(0)

	def OnRightUp(self, event):
		self.PopupMenu(self.CreatePopupMenu())

	def OnTaskbarCreated(self, hwnd, msg, wparam, lparam):
		if self._nid:
			hicon, tooltip = self._nid[4:6]
			self._nid = None
			self.SetIcon(hicon, tooltip)

	def OnTaskbarNotify(self, hwnd, msg, wparam, lparam):
		if lparam == win32con.WM_LBUTTONDOWN:
			self.ProcessEvent(wx.CommandEvent(wx.wxEVT_TASKBAR_LEFT_DOWN))
		elif lparam == win32con.WM_LBUTTONUP:
			self.ProcessEvent(wx.CommandEvent(wx.wxEVT_TASKBAR_LEFT_UP))
		elif lparam == win32con.WM_LBUTTONDBLCLK:
			self.ProcessEvent(wx.CommandEvent(wx.wxEVT_TASKBAR_LEFT_DCLICK))
		elif lparam == win32con.WM_RBUTTONDOWN:
			self.ProcessEvent(wx.CommandEvent(wx.wxEVT_TASKBAR_RIGHT_DOWN))
		elif lparam == win32con.WM_RBUTTONUP:
			self.ProcessEvent(wx.CommandEvent(wx.wxEVT_TASKBAR_RIGHT_UP))
		return 1

	def PopupMenu(self, menu):
		self.menu = menu
		pos = win32gui.GetCursorPos()
		# See http://msdn.microsoft.com/library/default.asp?url=/library/en-us/winui/menus_0hdi.asp
		win32gui.SetForegroundWindow(self.hwnd)
		win32gui.TrackPopupMenu(menu.hmenu, win32con.TPM_LEFTALIGN, pos[0],
								pos[1], 0, self.hwnd, None)
		win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)

	def RemoveIcon(self):
		if self._nid:
			self._nid = None
			try:
				win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (self.hwnd, 0))
			except win32gui.error:
				return False
			return True
		return False

	def SetIcon(self, hicon, tooltip=u""):
		if isinstance(hicon, wx.Icon):
			hicon = hicon.GetHandle()
		flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
		if self._nid:
			msg = win32gui.NIM_MODIFY
		else:
			msg = win32gui.NIM_ADD
		self._nid = (self.hwnd, 0, flags, win32con.WM_USER + 20, hicon, tooltip)
		try:
			win32gui.Shell_NotifyIcon(msg, self._nid)
		except win32gui.error:
			return False
		return True


def main():
	app = wx.App(0)
	hinst = win32gui.GetModuleHandle(None)
	try:
		hicon = win32gui.LoadImage(hinst, 1, win32con.IMAGE_ICON, 0, 0,
								   win32con.LR_DEFAULTSIZE)
	except pywintypes.error:
		hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
	tooltip = os.path.basename(sys.executable)
	icon = SysTrayIcon()
	icon.Bind(wx.EVT_TASKBAR_LEFT_UP,
			  lambda event: wx.MessageDialog(None,
											 u"Native system tray icon demo (Windows only)",
											 u"SysTrayIcon class",
											 wx.OK | wx.ICON_INFORMATION).ShowModal())
	icon.SetIcon(hicon, tooltip)
	win32gui.PumpMessages()


if __name__=='__main__':
	main()
