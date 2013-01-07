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

from config import getbitmap, getcfg, get_icon_bundle, get_display_number
from meta import name as appname
from wxaddons import CustomEvent
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
			button.Bind(wx.EVT_BUTTON, self.measure)
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
		return self.keepGoing, False
	
	def Resume(self):
		self.keepGoing = True
	
	def Show(self, show=True):
		if show:
			display_no = getcfg("display.number") - 1
			if display_no < 0 or display_no > wx.Display.GetCount() - 1:
				display_no = 0
			else:
				display_no = get_display_number(display_no)
			x, y, w, h = wx.Display(display_no).ClientArea
			# Place frame on correct display
			self.SetPosition((x, y))
			self.SetSize((w, h))
			self.disable_buttons()
			wx.CallAfter(self.Maximize)
		wx.Frame.Show(self, show)
	
	def Update(self, value, msg=""):
		return self.Pulse(msg)
	
	def UpdatePulse(self, msg=""):
		return self.Pulse(msg)
	
	def disable_buttons(self):
		self.enable_buttons(False)
	
	def enable_buttons(self, enable=True):
		for button in self.buttons:
			button.Enable(enable)
	
	def flush(self):
		pass
	
	def has_worker_subprocess(self):
		return bool(getattr(self, "worker", None) and
					getattr(self.worker, "subprocess", None))
	
	def hide_cursor(self):
		cursor_id = wx.CURSOR_BLANK
		cursor = wx.StockCursor(cursor_id)
		self.SetCursor(cursor)
		for panel in self.panels:
			panel.SetCursor(cursor)
		for label in self.labels.values():
			label.SetCursor(cursor)
		for button in self.buttons:
			button.SetCursor(cursor)
	
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
				if keycode == 27 or chr(keycode) == "Q":
					# ESC or Q
					self.worker.safe_send(chr(keycode))
				elif self.index > -1 and not self.is_measuring:
					# Any other key
					self.measure(CustomEvent(wx.EVT_BUTTON.typeId,
											 self.buttons[self.index]))
		else:
			event.Skip()
	
	def measure(self, event=None):
		if event:
			self.index = event.GetEventObject().index
			self.is_measuring = True
			self.results[self.index] = []
			self.labels[self.index].SetLabel("")
			self.hide_cursor()
			self.disable_buttons()
		self.worker.safe_send(" ")

	def parse_txt(self, txt):
		if not txt:
			return
		if "Setting up the instrument" in txt:
			self.Pulse(lang.getstr("instrument.initializing"))
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
		if "key to take a reading" in txt:
			if not self.is_measuring:
				self.enable_buttons()
				return
			if len(self.results[self.index]) < 4:
				# Take readings at 4 different brightness levels per swatch
				self.panels[self.index].SetBackgroundColour(self.colors[len(self.results[self.index])])
				self.panels[self.index].Refresh()
				self.panels[self.index].Update()
				wx.CallAfter(self.measure)
			else:
				self.is_measuring = False
				self.show_cursor()
				self.enable_buttons()
				self.buttons[self.index].SetBitmap(getbitmap("theme/icons/16x16/checkmark"))
				self.panels[self.index].SetBackgroundColour(WHITE)
				self.panels[self.index].Refresh()
				self.panels[self.index].Update()
				if len(self.results) == self.rows * self.cols:
					# All swatches have been measured, show results
					reference = self.results[int(math.floor(self.rows * self.cols / 2.0))]
					Yr = 0
					Lr, ar, br = 0, 0, 0
					CDTr = 0
					delta_Er = 0
					for item in reference:
						Yr += item["XYZ"][1]
						Lr += item["Lab"][0]
						ar += item["Lab"][1]
						br += item["Lab"][2]
						CDTr += item["CDT"]
						delta_Er += item["delta_E"]
					Yr /= 4.0
					Lr /= 4.0
					ar /= 4.0
					br /= 4.0
					CDTr /= 4.0
					delta_Er /= 4.0
					for index in self.results:
						result = self.results[index]
						if result is reference:
							continue
						Y = 0
						L, a, b = 0, 0, 0
						CDT = 0
						delta_E = 0
						for item in result:
							Y += item["XYZ"][1]
							L += item["Lab"][0]
							a += item["Lab"][1]
							b += item["Lab"][2]
							CDT += item["CDT"]
							delta_E += item["delta_E"]
						Y /= 4.0
						L /= 4.0
						a /= 4.0
						b /= 4.0
						CDT /= 4.0
						delta_E /= 4.0
						Y_diff_percent = Yr - Y
						delta_C = colormath.delta(Lr, ar, br, L, a, b, "2k")["C"]
						self.labels[index].SetLabel(u"\u0394C*00: %.2f, \u0394Y: %.2f\nCDT: %i (\u0394E: %.2f)" %
													(delta_C, Y_diff_percent, round(CDT), delta_E))
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
		self.index = -1
		self.is_measuring = False
		self.keepGoing = True
		self.results = {}
	
	def show_cursor(self):
		cursor = wx.StockCursor(wx.CURSOR_ARROW)
		self.SetCursor(cursor)
		for panel in self.panels:
			panel.SetCursor(cursor)
		for label in self.labels.values():
			label.SetCursor(cursor)
		for button in self.buttons:
			button.SetCursor(cursor)
	
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
