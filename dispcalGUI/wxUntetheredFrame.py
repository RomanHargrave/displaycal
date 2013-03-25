#!/usr/bin/env python
# -*- coding: UTF-8 -*-


"""
Interactive display calibration UI

"""

import os
import re
import sys
import time

from wxaddons import wx

from config import getcfg, get_icon_bundle
from log import get_file_logger
from meta import name as appname
from wxwindows import numpad_keycodes
import CGATS
import colormath
import config
import localization as lang

BGCOLOUR = wx.Colour(0x33, 0x33, 0x33)
WHITE = wx.Colour(0xff, 0xff, 0xff)


class UntetheredFrame(wx.Frame):

	def __init__(self, parent=None, handler=None,
				 keyhandler=None, start_timer=True):
		wx.Frame.__init__(self, parent, wx.ID_ANY,
						  lang.getstr("measurement.untethered"),
						  style=wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL)
		self.SetIcons(get_icon_bundle([256, 48, 32, 16], appname))
		self.SetBackgroundColour(BGCOLOUR)
		self.sizer = wx.FlexGridSizer(2, 2, 8, 8)
		self.SetSizer(self.sizer)
		self.label_RGB = wx.StaticText(self, wx.ID_ANY, " ")
		self.label_RGB.SetForegroundColour(WHITE)
		self.sizer.Add(self.label_RGB, 0, wx.TOP | wx.LEFT | wx.EXPAND, border=8)
		self.label_XYZ = wx.StaticText(self, wx.ID_ANY, " ")
		self.label_XYZ.SetForegroundColour(WHITE)
		self.sizer.Add(self.label_XYZ, 0, wx.TOP | wx.RIGHT | wx.EXPAND, border=8)
		self.panel_RGB = wx.Panel(self, size=(256, 256), style=wx.BORDER_SIMPLE)
		self.sizer.Add(self.panel_RGB, 1, wx.LEFT | wx.BOTTOM | wx.EXPAND, border=8)
		self.panel_XYZ = wx.Panel(self, size=(256, 256), style=wx.BORDER_SIMPLE)
		self.sizer.Add(self.panel_XYZ, 1, wx.RIGHT | wx.BOTTOM | wx.EXPAND, border=8)
		self.Fit()
		
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
		self.logger = get_file_logger("untethered")
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
		if msg == lang.getstr("instrument.initializing"):
			self.label_RGB.SetLabel(msg)
		return self.keepGoing, False
	
	def Resume(self):
		self.keepGoing = True
	
	def Show(self, show=True):
		if show:
			x, y, w, h = wx.Display(0).ClientArea
			self.SetPosition((x, y))
		wx.Frame.Show(self, show)
	
	def Update(self, value, msg=""):
		return self.Pulse(msg)
	
	def UpdatePulse(self, msg=""):
		return self.Pulse(msg)
	
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
				if keycode == 27 or chr(keycode) == "Q":
					# ESC or Q
					self.worker.safe_send(chr(keycode))
				elif not self.is_measuring:
					# Any other key
					self.measure()
		else:
			event.Skip()
	
	def measure(self, event=None):
		self.is_measuring = True
		# Use a delay to allow for TFT lag
		wx.CallLater(200, self.safe_send, " ")

	def parse_txt(self, txt):
		if not txt or not self.keepGoing or self.finished:
			return
		self.logger.info("%r" % txt)
		if "Connecting to the instrument" in txt:
			self.Pulse(lang.getstr("instrument.initializing"))
		if "Spot read failed" in txt:
			self.last_error = txt
		if "Result is XYZ:" in txt:
			self.last_error = None
			# Result is XYZ: d.dddddd d.dddddd d.dddddd, D50 Lab: d.dddddd d.dddddd d.dddddd
			XYZ = [float(v) for v in
				   re.search("XYZ:\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)",
							 txt).groups()]
			row = self.cgats[0].DATA[self.index]
			if (row["RGB_R"] == 100 and
				row["RGB_G"] == 100 and
				row["RGB_B"] == 100 and self.white_XYZ == (100, 100, 100)):
				# White
				self.cgats[0].add_keyword("LUMINANCE_XYZ_CDM2",
										  "%.6f %.6f %.6f" % tuple(XYZ))
				self.white_XYZ = XYZ
				self.white_XYZ_Y100 = [v / self.white_XYZ[1] * 100 for v in XYZ]
			XYZ_Y100 = [v / self.white_XYZ[1] * 100 for v in XYZ]
			Lab1 = colormath.XYZ2Lab(*self.last_XYZ_Y100)
			Lab2 = colormath.XYZ2Lab(*XYZ_Y100)
			delta = colormath.delta(*Lab1 + Lab2)
			if delta["E"] > 1:
				self.measure_count += 1
				if self.measure_count == 2:
					self.measure_count = 0
					self.label_RGB.SetLabel("%i/%i RGB = %i %i %i" % (self.index + 1,
																	  len(self.cgats[0].DATA),
																	  round(row["RGB_R"] * 2.55),
																	  round(row["RGB_G"] * 2.55),
																	  round(row["RGB_B"] * 2.55)))
					color = [int(round(v * 2.55)) for v in
							 (row["RGB_R"], row["RGB_G"], row["RGB_B"])]
					self.panel_RGB.SetBackgroundColour(wx.Colour(*color))
					self.panel_RGB.Refresh()
					self.panel_RGB.Update()
					self.label_XYZ.SetLabel("XYZ = %.2f %.2f %.2f" % tuple(XYZ))
					rgb_space = list(colormath.rgb_spaces["sRGB"])
					rgb_space[1] = tuple([v / 100.0 for v in self.white_XYZ_Y100])
					color = [int(round(v)) for v in
							 colormath.XYZ2RGB(*[v / 100.0 for v in XYZ_Y100],
											   rgb_space=rgb_space,
											   scale=255)]
					self.panel_XYZ.SetBackgroundColour(wx.Colour(*color))
					self.panel_XYZ.Refresh()
					self.panel_XYZ.Update()
					# Update CGATS
					query = self.cgats[0].queryi({"RGB_R": row["RGB_R"],
												  "RGB_G": row["RGB_G"],
												  "RGB_B": row["RGB_B"]})
					for i in query:
						query[i]["XYZ_X"], query[i]["XYZ_Y"], query[i]["XYZ_Z"] = XYZ_Y100
						self.index += 1
					self.last_XYZ_Y100 = XYZ_Y100
					if len(self.cgats[0].DATA) == self.index:
						self.cgats[0].type = "CTI3"
						self.cgats[0].add_keyword("COLOR_REP", "RGB_XYZ")
						self.cgats[0].add_keyword("NORMALIZED_TO_Y_100", "YES")
						self.cgats[0].add_keyword("DEVICE_CLASS", "DISPLAY")
						self.cgats[0].add_keyword("INSTRUMENT_TYPE_SPECTRAL", "NO")
						self.cgats.write(os.path.splitext(self.cgats.filename)[0] +
										 ".ti3")
						self.safe_send("Q")
						time.sleep(.5)
						self.safe_send("Q")
						self.finished = True
						return
		if "key to take a reading" in txt and not self.last_error:
			self.is_measuring = False
			self.measure()
	
	def reset(self):
		self._setup()
	
	def _setup(self):
		self.logger.info("-" * 80)
		self.is_measuring = False
		self.keepGoing = True
		self.last_error = None
		self.index = 0
		self.last_XYZ_Y100 = (100.0, 100.0, 100.0)
		self.white_XYZ = (100.0, 100.0, 100.0)
		self.measure_count = 0
		self.finished = False
		self.label_RGB.SetLabel(" ")
		self.label_XYZ.SetLabel(" ")
		self.panel_RGB.SetBackgroundColour(BGCOLOUR)
		self.panel_RGB.Refresh()
		self.panel_RGB.Update()
		self.panel_XYZ.SetBackgroundColour(BGCOLOUR)
		self.panel_XYZ.Refresh()
		self.panel_XYZ.Update()
	
	def safe_send(self, bytes):
		if self.has_worker_subprocess() and not self.worker.subprocess_abort:
			self.worker.safe_send(bytes)
	
	def start_timer(self, ms=50):
		self.timer.Start(ms)
	
	def stop_timer(self):
		self.timer.Stop()
	
	def write(self, txt):
		wx.CallAfter(self.parse_txt, txt)


if __name__ == "__main__":
	from thread import start_new_thread
	from time import sleep
	class Subprocess():
		def send(self, bytes):
			start_new_thread(test, (bytes,))
	class Worker(object):
		def __init__(self):
			self.subprocess = Subprocess()
			self.subprocess_abort = False
		def safe_send(self, bytes):
			self.subprocess.send(bytes)
			return True
	config.initcfg()
	lang.init()
	lang.update_defaults()
	app = wx.App(0)
	frame = UntetheredFrame(start_timer=False)
	frame.cgats = CGATS.CGATS(getcfg("testchart.file"))
	frame.worker = Worker()
	frame.Show()
	i = 0
	def test(bytes=None):
		global i
		menu = r"""Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:"""
		if not bytes:
			txt = menu
		elif bytes == " ":
			txt = ["""
 Result is XYZ: 95.153402 100.500147 109.625585

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""", """
 Result is XYZ: 41.629826 21.903717 1.761510

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""", """
 Result is XYZ: 35.336831 71.578641 11.180005

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:""", """
 Result is XYZ: 18.944662 7.614568 95.107897

Place instrument on spot to be measured,
and hit [A-Z] to read white and setup FWA compensation (keyed to letter)
[a-z] to read and make FWA compensated reading from keyed reference
'r' to set reference, 's' to save spectrum,
'h' to toggle high res., 'k' to do a calibration
Hit ESC or Q to exit, any other key to take a reading:"""][i]
			if i < 3:
				i += 1
			else:
				i -= 3
		elif bytes in ("Q", "q"):
			wx.CallAfter(frame.Close)
			return
		else:
			return
		for line in txt.split("\n"):
			sleep(.03125)
			if frame:
				wx.CallAfter(frame.write, line)
				print line
	start_new_thread(test, tuple())
	app.MainLoop()
