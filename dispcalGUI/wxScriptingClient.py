# -*- coding: utf-8 -*-

from __future__ import with_statement
from time import sleep
import os
import socket
import sys
import threading

from config import confighome, getcfg, geticon, initcfg, setcfg, writecfg
from meta import name as appname
from safe_print import safe_print
from util_str import safe_str, safe_unicode, universal_newlines
from wexpect import split_command_line
from wxaddons import wx
from wxfixes import GenBitmapButton
from wxwindows import BaseApp, SimpleTerminal, numpad_keycodes
import config
import demjson
import localization as lang

import wx.lib.delayedresult as delayedresult


ERRORCOLOR = "#FF3300"
RESPONSECOLOR = "#CCCCCC"


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
				raise socket.error(lang.getstr("connection.broken"))
			self.recv_buffer += incoming
		end = self.recv_buffer.find("\4")
		single_response = self.recv_buffer[:end]
		self.recv_buffer = self.recv_buffer[end + 1:]
		return single_response

	def send_command(self, command):
		# Automatically append newline (command end marker)
		self.sendall(command + "\n")


class ScriptingClientFrame(SimpleTerminal):

	def __init__(self):
		SimpleTerminal.__init__(self, None, wx.ID_ANY,
								lang.getstr("scripting-client"),
								pos=(getcfg("position.scripting.x"),
									 getcfg("position.scripting.y")),
								size=(getcfg("size.scripting.w"),
									  getcfg("size.scripting.h")),
								consolestyle=wx.TE_CHARWRAP | wx.TE_MULTILINE |
											 wx.TE_PROCESS_ENTER | wx.TE_RICH |
											 wx.VSCROLL | wx.NO_BORDER)
		self.SetIcons(config.get_icon_bundle([256, 48, 32, 16], 
											 appname + "-scripting-client"))
		self.console.SetDefaultStyle(wx.TextAttr("#EEEEEE"))

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
		# Always have empty selection at bottom
		self.history.append("")
		self.historypos = len(self.history) - 1

		self.overwrite = False

		# Determine which application we should connect to by default (if any)
		self.conn = None
		scripting_hosts = self.get_scripting_hosts()

		self.sizer.Layout()
		self.SetTransparent(240)

		self.Bind(wx.EVT_ACTIVATE, self.OnActivate)
		self.Bind(wx.EVT_SIZE, self.OnSize)
		##self.Unbind(wx.EVT_CHAR_HOOK)
		##self.console.Unbind(wx.EVT_KEY_DOWN)
		##self.console.Bind(wx.EVT_CHAR, self.key_handler)

		if scripting_hosts:
			self.add_text(lang.getstr("scripting-client.detected-hosts") + "\n")
			for host in scripting_hosts:
				self.add_text(host + "\n")
			ip_port = scripting_hosts[0].split()[0]
			self.add_text("> connect " + ip_port + "\n")
			self.connect_handler(ip_port)

	def OnActivate(self, event):
		self.console.SetFocus()
		linecount = self.console.GetNumberOfLines()
		lastline = self.console.GetLineText(linecount - 1)
		lastpos = self.console.GetLastPosition()
		start, end = self.console.GetSelection()
		if (start == end and
			self.console.GetInsertionPoint() < lastpos - len(lastline)):
			self.console.SetInsertionPoint(lastpos)

	def OnClose(self, event):
		# So we can send_command('close') ourselves without prematurely exiting
		# the wx main loop
		while self.busy:
			wx.Yield()
			sleep(.05)
		self.Hide()
		try:
			with open(self.historyfilename, "wb") as historyfile:
				for command in self.history:
					if command:
						historyfile.write(safe_str(command, "UTF-8") + "\n")
		except EnvironmentError, exception:
			safe_print("Warning - couldn't write history file:", exception)
		self.Destroy()

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

	def add_error_text(self, text):
		self.add_text(text)
		end = self.console.GetLastPosition()
		start = end - len(text)
		self.mark_text(start, end, ERRORCOLOR)

	def check_result(self, delayedResult, get_response=False,
					 additional_commands=None, colorize=True):
		result = delayedResult.get()
		if result:
			text = "%s\n" % safe_unicode(result)
			self.add_text(text)
			if colorize or isinstance(result, Exception):
				end = self.console.GetLastPosition()
				start = end - len(text)
				if isinstance(result, Exception):
					color = ERRORCOLOR
				else:
					color = RESPONSECOLOR
				self.mark_text(start, end, color)
		if get_response and not isinstance(result, Exception):
			delayedresult.startWorker(self.check_result, get_response,
									  cargs=(False, additional_commands))
		else:
			self.add_text("> ")
			if additional_commands:
				self.add_text(additional_commands[0].rstrip("\n"))
				if additional_commands[0].endswith("\n"):
					self.send_command_handler(additional_commands[0],
											  additional_commands[1:])
					return
			self.console.SetFocus()
			self.busy = False

	def clear(self):
		self.console.Clear()
		self.add_text("> ")
		self.console.SetInsertionPoint(2)

	def connect_handler(self, ip_port):
		ip, port = ip_port.split(":", 1)
		try:
			port = int(port)
		except ValueError:
			self.add_error_text(lang.getstr("port.invalid", port) + "\n")
			self.add_text("> ")
			return
		if self.conn:
			self.disconnect()
		self.add_text(lang.getstr("connecting.to", (ip, port)) + "\n")
		self.conn = ScriptingClientSocket()
		self.conn.settimeout(3)
		delayedresult.startWorker(self.check_result, self.connect,
								  cargs=(self.get_app_info, None, False),
								  wargs=(ip, port))

	def connect(self, ip, port):
		self.busy = True
		try:
			self.conn.connect((ip, port))
		except socket.error, exception:
			self.conn.close()
			del self.conn
			self.conn = None
			return exception
		return lang.getstr("connection.established")

	def disconnect(self):
		if self.conn:
			try:
				peer = self.conn.getpeername()
				self.conn.shutdown(socket.SHUT_RDWR)
			except:
				pass
			else:
				self.add_text(lang.getstr("disconnected.from", peer) + "\n")
			self.conn.close()
			del self.conn
			self.conn = None
			self.commands = []
		else:
			self.add_error_text(lang.getstr("not_connected") + "\n")

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
					wx.CallAfter(self.add_text,
								 lang.getstr("connected.to.at",
											 ((response, ) +
											 self.conn.getpeername())) +
								 "\n%s\n" %
								 lang.getstr("scripting-client.cmdhelptext"))
		except socket.error, exception:
			return exception

	def get_commands(self):
		if self.conn:
			commands = self.get_common_commands() + ["disconnect"]
		else:
			commands = ["echo"]
		return commands + ["clear", "connect <ip>:<port>",
						   "getscriptinghosts"]

	def get_response(self):
		try:
			return "< " + "\n< ".join(self.conn.get_single_response().decode("UTF-8").splitlines())
		except socket.error, exception:
			return exception

	def get_scripting_hosts(self):
		scripting_hosts = []
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
							ports = lockfile.read().splitlines()
					except EnvironmentError, exception:
						# This shouldn't happen
						safe_print("Warning - could not read lockfile %s:" %
								   lockfilename, exception)
					else:
						for port in ports:
							scripting_hosts.append("127.0.0.1:%s %s" %
												   (port, lockfilebasename))
		return scripting_hosts

	def key_handler(self, event):
		##safe_print(event.KeyCode)
		linecount = self.console.GetNumberOfLines()
		lastline = self.console.GetLineText(linecount - 1)
		lastpos = self.console.GetLastPosition()
		insertionpoint = self.console.GetInsertionPoint()
		start, end = self.console.GetSelection()
		startcol, startrow = self.console.PositionToXY(start)
		endcol, endrow = self.console.PositionToXY(end)
		cmd_or_ctrl = event.ControlDown() or event.CmdDown()
		if cmd_or_ctrl and event.KeyCode == 65:
			# A
			self.console.SelectAll()
		elif cmd_or_ctrl and event.KeyCode in (67, 88):
			# C / X
			event.Skip()
		elif insertionpoint >= lastpos - len(lastline) + 2:
			if cmd_or_ctrl:
				if event.KeyCode == 86:
					# V
					do = wx.TextDataObject()
					wx.TheClipboard.Open()
					success = wx.TheClipboard.GetData(do)
					wx.TheClipboard.Close()
					if success:
						cliptext = universal_newlines(do.GetText())
						lines = cliptext.replace("\n", "\n\0").split("\0")
						command1 = (lastline[2:startcol] +
									lines[0].rstrip("\n") +
									lastline[endcol:])
						self.add_text("\r> " + command1)
						if "\n" in cliptext:
							self.send_command_handler(command1, lines[1:])
						else:
							self.console.SetInsertionPoint(insertionpoint +
														   len(cliptext))
				elif event.UnicodeKey:
					wx.Bell()
			elif event.KeyCode in (10, 13, wx.WXK_NUMPAD_ENTER):
				# Enter, return key
				self.send_command_handler(lastline[2:])
			elif event.KeyCode == wx.WXK_BACK:
				# Backspace
				if startcol == endcol:
					startcol -= 1
					insertionpoint -= 1
				if startcol > 1:
					self.add_text("\r> " + lastline[2:startcol] +
								  lastline[endcol:])
					self.console.SetInsertionPoint(insertionpoint)
				else:
					wx.Bell()
			elif event.KeyCode in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
				if startcol == endcol:
					endcol += 1
				if endcol <= len(lastline):
					self.add_text("\r> " + lastline[2:startcol] +
								  lastline[endcol:])
					self.console.SetInsertionPoint(insertionpoint)
				else:
					wx.Bell()
			elif event.KeyCode in (wx.WXK_DOWN, wx.WXK_NUMPAD_DOWN,
								   wx.WXK_NUMPAD_PAGEDOWN, wx.WXK_PAGEDOWN):
				if self.historypos < len(self.history) - 1:
					self.historypos += 1
					self.add_text("\r> " + self.history[self.historypos])
				else:
					wx.Bell()
			elif event.KeyCode in (wx.WXK_END, wx.WXK_NUMPAD_END):
				self.console.SetInsertionPoint(lastpos)
			elif event.KeyCode in (wx.WXK_HOME, wx.WXK_NUMPAD_HOME):
				self.console.SetInsertionPoint(lastpos - len(lastline) + 2)
			elif event.KeyCode in (wx.WXK_INSERT, wx.WXK_NUMPAD_INSERT):
				self.overwrite = not self.overwrite
			elif event.KeyCode in (wx.WXK_LEFT, wx.WXK_NUMPAD_LEFT):
				if (start > lastpos - len(lastline) + 2):
					self.console.SetInsertionPoint(start - 1)
				else:
					wx.Bell()
			elif event.KeyCode in (wx.WXK_RIGHT, wx.WXK_NUMPAD_RIGHT):
				if end < lastpos:
					self.console.SetInsertionPoint(end + 1)
				else:
					wx.Bell()
			elif event.KeyCode in (wx.WXK_UP, wx.WXK_NUMPAD_UP,
								   wx.WXK_NUMPAD_PAGEUP, wx.WXK_PAGEUP):
				if self.historypos > 0:
					self.historypos -= 1
					self.add_text("\r> " + self.history[self.historypos])
				else:
					wx.Bell()
			elif event.KeyCode == wx.WXK_TAB:
				# Tab completion
				commonpart = lastline[2:endcol]
				candidates = []
				for command in sorted(list(set(self.commands +
											   self.get_commands()))):
					command = command.split()[0]
					if command.startswith(commonpart):
						candidates.append(command)
				findcommon = bool(candidates)
				while findcommon and len(candidates[0]) > len(commonpart):
					commonpart += candidates[0][len(commonpart)]
					for candidate in candidates:
						if candidate.startswith(commonpart):
							continue
						else:
							commonpart = commonpart[:-1]
							findcommon = False
							break
				if len(candidates) > 1:
					self.add_text("\n%s\n" % " ".join(candidates))
				self.add_text("\r> " + commonpart + lastline[endcol:])
				self.console.SetInsertionPoint(self.console.GetLastPosition() -
											   len(lastline[endcol:]))
			elif event.UnicodeKey or event.KeyCode in numpad_keycodes:
				if startcol > 1:
					event.Skip()
					if self.overwrite and startcol == endcol:
						self.add_text("\r> " + lastline[2:startcol] +
									  lastline[endcol + 1:])
						self.console.SetInsertionPoint(insertionpoint)
				else:
					wx.Bell()
					self.console.SetInsertionPoint(lastpos)
		elif event.KeyCode not in (wx.WXK_ALT, wx.WXK_COMMAND, wx.WXK_CONTROL,
								   wx.WXK_SHIFT):
			wx.Bell()
			self.console.SetInsertionPoint(lastpos)

	def mark_text(self, start, end, color):
		self.console.SetStyle(start, end, wx.TextAttr(color))

	def process_data(self, data):
		if data[0] == "echo" and len(data) > 1:
			linecount = self.console.GetNumberOfLines()
			lastline = self.console.GetLineText(linecount - 1)
			if lastline:
				self.add_text("\n")
			self.add_text(" ".join(data[1:]) + "\n")
			if lastline:
				self.add_text("> ")
			return "ok"
		return "invalid"

	def process_data_local(self, data):
		if data[0] == "clear" and len(data) == 1:
			self.clear()
		elif (data[0] == "connect" and len(data) == 2 and
			len(data[1].split(":")) == 2):
			wx.CallAfter(self.connect_handler, data[1])
		elif data[0] == "disconnect" and len(data) == 1:
			self.disconnect()
			self.add_text("> ")
		#elif data[0] == "echo" and len(data) > 1:
			#self.add_text(" ".join(data[1:]) + "\n")
			#return
		elif data[0] == "getscriptinghosts" and len(data) == 1:
			return self.get_scripting_hosts()
		else:
			return "invalid"
		return "ok"

	def send_command(self, command):
		self.busy = True
		try:
			self.conn.send_command(command)
		except socket.error, exception:
			return exception
		if not wx.GetApp().IsMainLoopRunning():
			delayedresult.AbortEvent()()

	def send_command_handler(self, command, additional_commands=None):
		self.add_text("\n")
		command = command.strip()
		if not command:
			self.add_text("> ")
			return
		data = split_command_line(command)
		response = self.process_data_local(data)
		if response == "ok":
			pass
		elif isinstance(response, list):
			self.add_text("\n".join(response))
			self.add_text("\n> ")
		elif not self or not self.conn:
			self.add_error_text(lang.getstr("not_connected") + "\n")
			self.add_text("> ")
		else:
			delayedresult.startWorker(self.check_result, self.send_command,
									  cargs=(self.get_response,
											 additional_commands),
									  wargs=(command, ))
		self.history.insert(len(self.history) - 1, command)
		if len(self.history) > 8192:
			del self.history[0]
		self.historypos = len(self.history) - 1


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
