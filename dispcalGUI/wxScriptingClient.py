# -*- coding: utf-8 -*-

from __future__ import with_statement
import os
import socket
import sys
import threading

from config import confighome, getcfg, geticon, initcfg, setcfg, writecfg
from meta import name as appname
from safe_print import safe_print
from util_str import safe_str, safe_unicode
from wxaddons import wx
from wxfixes import GenBitmapButton
from wxwindows import BaseApp, LogWindow
import config
import demjson
import localization as lang

import wx.lib.delayedresult as delayedresult


class ScriptingClientSocket(socket.socket):

	def __del__(self):
		self.disconnect()

	def __enter__(self):
		return self

	def __exit__(self, etype, value, tb):
		self.disconnect()

	def __init__(self):
		socket.socket.__init__(self)
		self.recv_buffer = ""

	def disconnect(self):
		try:
			# Will fail if the socket isn't connected, i.e. if there was an
			# error during the call to connect()
			self.shutdown(socket.SHUT_RDWR)
		except socket.error:
			pass
		self.close()

	def get_single_response(self):
		# Buffer received data until EOT (response end marker) and return
		# single response (additional data will still be in the buffer)
		while not "\4" in self.recv_buffer:
			incoming = self.recv(4096)
			if incoming == "":
				raise socket.error("Connection broken")
			self.recv_buffer += incoming
		end = self.recv_buffer.find("\4")
		single_response = self.recv_buffer[:end]
		self.recv_buffer = self.recv_buffer[end + 1:]
		return single_response

	def send_command(self, command):
		# Automatically append newline (command end marker)
		self.sendall(command + "\n")


class ScriptingClientFrame(LogWindow):

	def __init__(self):
		LogWindow.__init__(self, None, wx.ID_ANY,
						   lang.getstr("scripting-client"),
						   pos=(getcfg("position.scripting.x"),
								getcfg("position.scripting.y")),
						   size=(getcfg("size.scripting.w"),
								 getcfg("size.scripting.h")))
		self.SetIcons(config.get_icon_bundle([256, 48, 32, 16], 
											 appname + "-scripting-client"))

		self.commands = []
		self.history = []
		self.historyfilename = os.path.join(confighome,
											appname +
											"-scripting-client.history")
		if os.path.isfile(self.historyfilename):
			try:
				with open(self.historyfilename) as historyfile:
					for line in historyfile:
						self.history.append(safe_unicode(line,
														 "UTF-8").rstrip("\n"))
			except EnvironmentError, exception:
				safe_print("Warning - couldn't read history file:", exception)
		if self.history:
			# Always have empty selection at bottom
			self.history.append("")

		# Determine which application we should connect to by default (if any)
		self.conn = None
		choices = []
		lockfilebasenames = [appname]
		for module in ["3DLUT-maker", "curve-viewer", "profile-info",
					   "scripting-client", "synthprofile", "testchart-editor",
					   "VRML-to-X3D-converter"]:
			lockfilebasenames.append("%s-%s" % (appname, module))
		for lockfilebasename in lockfilebasenames:
				lockfilename = os.path.join(confighome, "%s.lock" %
														lockfilebasename)
				if os.path.isfile(lockfilename):
					try:
						with open(lockfilename) as lockfile:
							port = lockfile.read().strip()
					except EnvironmentError, exception:
						# This shouldn't happen
						safe_print("Warning - could not read lockfile %s:" %
								   lockfilename, exception)
					else:
						choices.append("127.0.0.1:%s %s" % (port,
															lockfilebasename))

		self.connect_to_ip_port_textctrl = wx.ComboBox(self.panel, -1,
													   choices[0],
													   choices=choices,
													   style=wx.TE_PROCESS_ENTER)
		self.connect_to_ip_port_textctrl.Bind(wx.EVT_COMBOBOX,
											  self.connect_handler)
		self.connect_to_ip_port_textctrl.Bind(wx.EVT_TEXT_ENTER,
											  self.connect_handler)
		self.sizer.Insert(0, self.connect_to_ip_port_textctrl,
						  flag=wx.TOP | wx.LEFT | wx.RIGHT | wx.EXPAND, border=4)

		self.commands_btn = GenBitmapButton(self.panel, -1, 
											geticon(16, "applications-system"), 
											style=wx.NO_BORDER)
		self.commands_btn.Bind(wx.EVT_BUTTON, self.select_command_popup)
		self.commands_btn.Bind(wx.EVT_CONTEXT_MENU,
								   self.select_command_popup)
		self.commands_btn.SetToolTipString(lang.getstr("commands"))
		self.btnsizer.Add(self.commands_btn, flag=wx.ALL, border=4)

		self.command_textctrl = wx.ComboBox(self.panel, -1,
											choices=self.history,
											style=wx.TE_PROCESS_ENTER)
		self.command_textctrl.Bind(wx.EVT_TEXT_ENTER, self.send_command_handler)
		self.sizer.Add(self.command_textctrl, flag=wx.BOTTOM | wx.LEFT |
												   wx.RIGHT | wx.EXPAND,
					   border=4)

		self.sizer.Layout()

		self.connect_handler(None)

		self.command_textctrl.SetSelection(self.command_textctrl.Count - 1)
		self.command_textctrl.SetFocus()

	def OnClose(self, event):
		# So we can send_command('close') ourselves without prematurely exiting
		# the wx main loop
		self.Hide()
		try:
			with open(self.historyfilename, "wb") as historyfile:
				for command in self.history:
					if command:
						historyfile.write(safe_str(command, "UTF-8") + "\n")
		except EnvironmentError, exception:
			safe_print("Warning - couldn't read history file:", exception)
		wx.CallLater(200, self.Destroy)

	def OnMove(self, event=None):
		if self.IsShownOnScreen() and not self.IsMaximized() and not \
		   self.IsIconized():
			x, y = self.GetScreenPosition()
			setcfg("position.scripting.x", x)
			setcfg("position.scripting.y", y)
		if event:
			event.Skip()

	def OnSize(self, event=None):
		if self.IsShownOnScreen() and not self.IsMaximized() and not \
		   self.IsIconized():
			w, h = self.GetSize()
			setcfg("size.scripting.w", w)
			setcfg("size.scripting.h", h)
		if event:
			event.Skip()

	def check_result(self, delayedResult, get_response=False):
		result = delayedResult.get()
		if result:
			txt = safe_unicode(result)
			if isinstance(result, basestring):
				lead = txt[:2]
				txt = ("\n" + lead).join(txt.splitlines())
			self.Log(txt)
		if get_response and not isinstance(result, Exception):
			delayedresult.startWorker(self.check_result, get_response)
		else:
			self.connect_to_ip_port_textctrl.Enable()
			self.command_textctrl.Enable()
			self.command_textctrl.SetFocus()
			self.command_textctrl.SelectAll()

	def connect_handler(self, event):
		if self.conn:
			try:
				peer = self.conn.getpeername()
				self.conn.shutdown(socket.SHUT_RDWR)
			except:
				pass
			else:
				self.Log(lang.getstr("disconnected.from", peer))
			self.conn.close()
		ip, port = self.connect_to_ip_port_textctrl.Value.split()[0].split(":", 1)
		try:
			port = int(port)
		except ValueError:
			self.Log(lang.getstr("port.invalid", port))
			return
		self.Log(lang.getstr("connecting.to", (ip, port)))
		self.conn = ScriptingClientSocket()
		self.conn.settimeout(3)
		self.connect_to_ip_port_textctrl.Disable()
		self.command_textctrl.Disable()
		delayedresult.startWorker(self.check_result, self.connect,
								  cargs=(self.get_app_info, ),
								  wargs=(ip, port))

	def connect(self, ip, port):
		try:
			self.conn.connect((ip, port))
		except socket.error, exception:
			return exception
		return lang.getstr("connection.established")

	def get_app_info(self):
		commands = ["setresponseformat json", "getcommands",
					"setresponseformat plain", "getappname"]
		try:
			for command in commands:
				self.conn.send_command(command)
				response = self.conn.get_single_response()
				if command == "getcommands":
					self.commands = demjson.decode(response)["result"]
				elif command == "getappname":
					wx.CallAfter(self.Log, lang.getstr("connected.to.at",
													   ((response, ) +
														self.conn.getpeername())))
		except socket.error, exception:
			return exception

	def get_response(self):
		try:
			return "< " + self.conn.get_single_response().decode("UTF-8")
		except socket.error, exception:
			return exception

	def select_command_popup(self, event):
		menu = wx.Menu()

		item_selected = False
		for command in self.commands:
			item = menu.Append(-1, command)
			self.Bind(wx.EVT_MENU, self.insert_command_handler, id=item.Id)

		self.PopupMenu(menu)
		for item in menu.MenuItems:
			self.Unbind(wx.EVT_MENU, id=item.Id)
		menu.Destroy()

	def insert_command_handler(self, event):
		for item in event.EventObject.MenuItems:
			if item.Id == event.Id:
				self.command_textctrl.Value = item.GetItemLabelText().split()[0]
				self.command_textctrl.SetFocus()

	def send_command(self, command):
		try:
			self.conn.send_command(command)
		except socket.error, exception:
			return exception
		if not wx.GetApp().IsMainLoopRunning():
			delayedresult.AbortEvent()()

	def send_command_handler(self, event):
		if not self or not self.conn and not self.connect_handler(None):
			return
		self.Log("> " + self.command_textctrl.Value)
		self.connect_to_ip_port_textctrl.Disable()
		self.command_textctrl.Disable()
		command = self.command_textctrl.Value
		delayedresult.startWorker(self.check_result, self.send_command,
								  cargs=(self.get_response, ),
								  wargs=(command, ))
		if command in self.history:
			self.history.remove(command)
			index = self.command_textctrl.FindString(command)
			if index != wx.NOT_FOUND:
				self.command_textctrl.Delete(index)
		self.history.insert(len(self.history) - 1, command)
		self.command_textctrl.Insert(command, self.command_textctrl.Count - 1)
		if len(self.history) > 8192:
			del self.history[0]
			self.command_textctrl.Delete(0)
		self.command_textctrl.SetSelection(self.command_textctrl.Count - 1)


def main():
	config.initcfg("scripting-client")
	lang.init()
	app = BaseApp(0)
	app.TopWindow = ScriptingClientFrame()
	app.TopWindow.listen()
	app.TopWindow.Show()
	app.MainLoop()
	writecfg(module="scripting-client", options=("position.scripting",
												 "size.scripting"))


if __name__ == "__main__":
	main()
