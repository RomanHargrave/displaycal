#!/usr/bin/env python
# -*- coding: UTF-8 -*-


"""
Interactive display calibration UI

"""

import math
import re
import sys
import time

from wxaddons import wx

from config import getbitmap, get_icon_bundle
from meta import name as appname
from wxwindows import FlatShadedButton, numpad_keycodes
import colormath
import config
import localization as lang

BGCOLOUR = wx.Colour(0x33, 0x33, 0x33)
BLACK = wx.Colour(0, 0, 0)
BORDERCOLOUR = wx.Colour(0x22, 0x22, 0x22)
FGCOLOUR = wx.Colour(0x99, 0x99, 0x99)
LIGHTGRAY = wx.Colour(0xcc, 0xcc, 0xcc)
MEDIUMGRAY = wx.Colour(0x80, 0x80, 0x80)
WHITE = wx.Colour(0xff, 0xff, 0xff)


class FlatShadedNumberedButton(FlatShadedButton):
	
	def __init__(self, parent, id=wx.ID_ANY, bitmap=None, label="",
				 pos=wx.DefaultPosition, size=wx.DefaultSize,
				 style=wx.NO_BORDER, validator=wx.DefaultValidator,
				 name="gradientbutton", bgcolour=None, fgcolour=None, index=0):
		FlatShadedButton.__init__(self, parent, id, bitmap, label, pos, size,
								  style, validator, name, bgcolour, fgcolour)
		self.index = index
		self.Bind(wx.EVT_BUTTON, self.measure)
	
	def measure(self, event):
		if event:
			self.Parent.Parent.results[self.index] = []
		self.Parent.Parent.index = self.index
		self.Parent.Parent.disable_buttons()
		self.Parent.Parent.worker.safe_send(" ")


class DisplayUniformityFrame(wx.Frame):

	def __init__(self, parent=None, handler=None,
				 keyhandler=None, start_timer=True, rows=3, cols=5):
		wx.Frame.__init__(self, parent, wx.ID_ANY,
						  lang.getstr("report.uniformity"),
						  style=wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL)
		self.SetIcons(get_icon_bundle([256, 48, 32, 16], appname))
		self.SetBackgroundColour(BGCOLOUR)
		self.sizer = wx.GridSizer(rows, cols)
		self.SetSizer(self.sizer)
		
		self.rows = rows
		self.cols = cols
		self.colors = (WHITE, wx.Colour(192, 192, 192),
							  wx.Colour(128, 128, 128), wx.Colour(64, 64, 64),
					   BLACK)
		self.labels = {}
		self.panels = []
		self.buttons = []
		for index in xrange(rows * cols):
			panel = wx.Panel(self, style=wx.BORDER_SIMPLE)
			##panel.SetBackgroundColour(wx.Colour(0x33, 0x33, 255.0 / (rows * cols) * (index + 1)))
			panel.SetBackgroundColour(WHITE)
			sizer = wx.BoxSizer(wx.VERTICAL)
			panel.SetSizer(sizer)
			self.panels.append(panel)
			button = FlatShadedNumberedButton(panel, label=" %s " %
													 lang.getstr("measure"),
											  bitmap=getbitmap("theme/icons/10x10/record"),
											  bgcolour=LIGHTGRAY,
											  fgcolour=BLACK, index=index)
			self.buttons.append(button)
			label = wx.StaticText(panel)
			self.labels[index] = label
			sizer.Add(label, 1, wx.ALIGN_CENTER)
			sizer.Add(button, 0, wx.ALIGN_BOTTOM | wx.ALIGN_CENTER | wx.BOTTOM |
								 wx.LEFT | wx.RIGHT,
					  border=8)
			self.sizer.Add(panel, 1, wx.EXPAND)
		self.disable_buttons()
		
		self.keyhandler = keyhandler
		if sys.platform in ("darwin", "win32"):
			# Use an accelerator table for space, 0-9, A-Z, numpad
			keycodes = [ord(" ")] + range(ord("0"),
										  ord("9")) + range(ord("A"),
															ord("Z")) + numpad_keycodes
			self.id_to_keycode = {}
			for keycode in keycodes:
				self.id_to_keycode[wx.NewId()] = keycode
			accels = []
			for id, keycode in self.id_to_keycode.iteritems():
				self.Bind(wx.EVT_MENU, self.key_handler, id=id)
				accels += [(wx.ACCEL_NORMAL, keycode, id)]
			self.SetAcceleratorTable(wx.AcceleratorTable(accels))
		else:
			self.Bind(wx.EVT_CHAR_HOOK, self.key_handler)
		
		# Event handlers
		self.Bind(wx.EVT_CLOSE, self.OnClose, self)
		self.Bind(wx.EVT_MOVE, self.OnMove, self)
		self.timer = wx.Timer(self)
		if handler:
			self.Bind(wx.EVT_TIMER, handler, self.timer)
		self.Bind(wx.EVT_WINDOW_DESTROY, self.OnDestroy, self)
		
		# Final initialization steps
		self._setup()
		
		self.Show()
		self.Maximize()
		
		if start_timer:
			self.start_timer()
	
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
		pass

	def Pulse(self, msg=""):
		if ((msg in (lang.getstr("instrument.initializing"),
					 lang.getstr("instrument.calibrating"),
					 lang.getstr("please_wait")) or msg == " " * 4 or
			 "error" in msg.lower() or "failed" in msg.lower()) and
			msg != self.lastmsg):
			self.lastmsg = msg
			self.Freeze()
			self.Thaw()
		return self.keepGoing, False
	
	def Resume(self):
		self.keepGoing = True
	
	def Show(self, show=True):
		self.disable_buttons()
		wx.Frame.Show(self, show)
	
	def Update(self, value, msg=""):
		return self.Pulse(msg)
	
	def UpdatePulse(self, msg=""):
		return self.Pulse(msg)
	
	def abort(self):
		if self.has_worker_subprocess():
			if self.is_measuring:
				self.worker.safe_send(" ")
	
	def abort_and_send(self, key):
		self.abort()
		if self.has_worker_subprocess():
			if self.worker.safe_send(key):
				self.is_busy = True
	
	def disable_buttons(self):
		for button in self.buttons:
			button.Disable()
	
	def flush(self):
		pass
	
	def has_worker_subprocess(self):
		return bool(getattr(self, "worker", None) and
					getattr(self.worker, "subprocess", None))
	
	def isatty(self):
		return True
	
	def key_handler(self, event):
		keycode = None
		if event.GetEventType() in (wx.EVT_CHAR.typeId,
									wx.EVT_CHAR_HOOK.typeId,
									wx.EVT_KEY_DOWN.typeId):
			keycode = event.GetKeyCode()
		elif event.GetEventType() == wx.EVT_MENU.typeId:
			keycode = self.id_to_keycode.get(event.GetId())
		if keycode is not None:
			if self.has_worker_subprocess():
				self.worker.safe_send(chr(keycode))
		else:
			event.Skip()

	def parse_txt(self, txt):
		if not txt:
			return
		if "Setting up the instrument" in txt:
			self.Pulse(lang.getstr("instrument.initializing"))
		if "key to take a reading" in txt:
			for button in self.buttons:
				button.Enable()
		if "Result is XYZ:" in txt:
			# Result is XYZ: d.dddddd d.dddddd d.dddddd, D50 Lab: d.dddddd d.dddddd d.dddddd
			#							CCT = ddddK (Delta E d.dddddd)
			# Closest Planckian temperature = ddddK (Delta E d.dddddd)
			# Closest Daylight temperature  = ddddK (Delta E d.dddddd)
			XYZ = re.search("XYZ:\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)", txt)
			XYZ = [float(value) for value in XYZ.groups()]
			XYZ_Y100 = [100.0 / XYZ[1] * value for value in XYZ]
			#Lab = re.search("Lab:\s+(\d+\.\d+)\s+(\-?\d+\.\d+)\s+(\-?\d+\.\d+)", txt)
			#Lab = [float(value) for value in Lab.groups()]
			Lab = colormath.XYZ2Lab(*XYZ_Y100)
			self.results[self.index].append({"XYZ": XYZ,
											 "Lab": Lab})
		if "Closest Daylight" in txt:
			CDT_delta_E = re.search("Closest Daylight\s+temperature\s+=\s+(\d+)K\s+\(Delta\s+E\s+(\d+\.\d+)\)", txt)
			CDT = int(CDT_delta_E.groups()[0])
			delta_E = float(CDT_delta_E.groups()[1])
			self.results[self.index][-1]["CDT"] = CDT
			self.results[self.index][-1]["delta_E"] = delta_E
			if len(self.results[self.index]) < 4:
				# Take readings at 4 different brightness levels per swatch
				self.panels[self.index].SetBackgroundColour(self.colors[len(self.results[self.index])])
				self.panels[self.index].Refresh()
				self.panels[self.index].Update()
				wx.CallAfter(self.buttons[self.index].measure, None)
			else:
				self.buttons[self.index].SetBitmap(getbitmap("theme/icons/16x16/checkmark"))
				self.panels[self.index].SetBackgroundColour(WHITE)
				self.panels[self.index].Refresh()
				self.panels[self.index].Update()
				if len(self.results) == self.rows * self.cols:
					# All swatches have been measured
					reference = self.results[int(math.floor(self.rows * self.cols / 2.0))]
					Yr = 0
					Lr, ar, br = 0, 0, 0
					for item in reference:
						Yr += item["XYZ"][1]
						Lr += item["Lab"][0]
						ar += item["Lab"][1]
						br += item["Lab"][2]
					Yr /= 4.0
					Lr /= 4.0
					ar /= 4.0
					br /= 4.0
					for index in self.results:
						result = self.results[index]
						if result is reference:
							continue
						Y = 0
						L, a, b = 0, 0, 0
						for item in result:
							Y += item["XYZ"][1]
							L += item["Lab"][0]
							a += item["Lab"][1]
							b += item["Lab"][2]
						Y /= 4.0
						L /= 4.0
						a /= 4.0
						b /= 4.0
						Y_diff_percent = Yr - Y
						delta_C = colormath.delta(Lr, ar, br, L, a, b, "2k")["C"]
						self.labels[index].SetLabel("Delta C 2000: %.2f, Y: %.2f" % (delta_C, Y_diff_percent))
						self.labels[index].GetContainingSizer().Layout()
	
	def reset(self):
		self._setup()
		for panel in self.panels:
			panel.SetBackgroundColour(WHITE)
		for button in self.buttons:
			button.SetBitmap(getbitmap("theme/icons/10x10/record"))
		for index in self.labels:
			self.labels[index].SetLabel("")
			self.labels[index].GetContainingSizer().Layout()
	
	def _setup(self):
		self.index = 0
		self.is_busy = None
		self.is_measuring = None
		self.lastmsg = ""
		self.keepGoing = True
		self.results = {}
	
	def start_timer(self, ms=50):
		self.timer.Start(ms)
	
	def stop_timer(self):
		self.timer.Stop()
	
	def write(self, txt):
		wx.CallAfter(self.parse_txt, txt)


if __name__ == "__main__":
	config.initcfg()
	lang.init()
	lang.update_defaults()
	app = wx.App(0)
	frame = DisplayUniformityFrame(start_timer=False)
	frame.Show()
	app.MainLoop()
