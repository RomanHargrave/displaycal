#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

try:
	import RealDisplaySizeMM as RDSMM
except ImportError:
	RDSMM = None
import config
import lang
from config import btn_width_correction, defaults, getbitmap, getcfg, get_data_path, scale_adjustment_factor, setcfg, writecfg
from debughelpers import handle_error
from log import safe_print
from meta import name as appname
from options import debug
from util_list import floatlist, strlist
from wxaddons import CustomEvent, wx
from wxwindows import ConfirmDialog, InfoDialog, InvincibleFrame

class MeasureFrame(InvincibleFrame):
	def __init__(self, parent = None, id = -1):
		InvincibleFrame.__init__(self, parent, id, lang.getstr("measureframe.title"), style = wx.DEFAULT_FRAME_STYLE & ~(wx.RESIZE_BORDER | wx.RESIZE_BOX | wx.MAXIMIZE_BOX))
		self.SetIcon(wx.Icon(get_data_path(os.path.join("theme", "icons", "16x16", appname + ".png")), wx.BITMAP_TYPE_PNG))
		self.Bind(wx.EVT_CLOSE, self.close_handler, self)
		self.Bind(wx.EVT_SIZE, self.size_handler, self)
		self.panel = wx.Panel(self, -1)
		self.sizer = wx.GridSizer(3, 1)
		self.panel.SetSizer(self.sizer)

		self.hsizer = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer.Add(self.hsizer, flag = wx.ALIGN_CENTER_HORIZONTAL | wx.ALL | wx.ALIGN_TOP, border = 10)

		self.zoommaxbutton = wx.BitmapButton(self.panel, -1, getbitmap("theme/icons/32x32/zoom-best-fit"), style = wx.NO_BORDER)
		self.Bind(wx.EVT_BUTTON, self.zoommax_handler, self.zoommaxbutton)
		self.hsizer.Add(self.zoommaxbutton, flag = wx.ALIGN_CENTER)
		self.zoommaxbutton.SetToolTipString(lang.getstr("measureframe.zoommax"))

		self.hsizer.Add((2, 1))

		self.zoominbutton = wx.BitmapButton(self.panel, -1, getbitmap("theme/icons/32x32/zoom-in"), style = wx.NO_BORDER)
		self.Bind(wx.EVT_BUTTON, self.zoomin_handler, self.zoominbutton)
		self.hsizer.Add(self.zoominbutton, flag = wx.ALIGN_CENTER)
		self.zoominbutton.SetToolTipString(lang.getstr("measureframe.zoomin"))

		self.hsizer.Add((2, 1))

		self.zoomnormalbutton = wx.BitmapButton(self.panel, -1, getbitmap("theme/icons/32x32/zoom-original"), style = wx.NO_BORDER)
		self.Bind(wx.EVT_BUTTON, self.zoomnormal_handler, self.zoomnormalbutton)
		self.hsizer.Add(self.zoomnormalbutton, flag = wx.ALIGN_CENTER)
		self.zoomnormalbutton.SetToolTipString(lang.getstr("measureframe.zoomnormal"))

		self.hsizer.Add((2, 1))

		self.zoomoutbutton = wx.BitmapButton(self.panel, -1, getbitmap("theme/icons/32x32/zoom-out"), style = wx.NO_BORDER)
		self.Bind(wx.EVT_BUTTON, self.zoomout_handler, self.zoomoutbutton)
		self.hsizer.Add(self.zoomoutbutton, flag = wx.ALIGN_CENTER)
		self.zoomoutbutton.SetToolTipString(lang.getstr("measureframe.zoomout"))

		self.centerbutton = wx.BitmapButton(self.panel, -1, getbitmap("theme/icons/32x32/window-center"), style = wx.NO_BORDER)
		self.Bind(wx.EVT_BUTTON, self.center_handler, self.centerbutton)
		self.sizer.Add(self.centerbutton, flag = wx.ALIGN_CENTER | wx.LEFT | wx.RIGHT, border = 10)
		self.centerbutton.SetToolTipString(lang.getstr("measureframe.center"))

		self.vsizer = wx.BoxSizer(wx.VERTICAL)
		self.sizer.Add(self.vsizer, flag = wx.ALIGN_BOTTOM | wx.ALIGN_CENTER_HORIZONTAL)

		self.measure_darken_background_cb = wx.CheckBox(self.panel, -1, lang.getstr("measure.darken_background"))
		self.measure_darken_background_cb.SetValue(bool(int(getcfg("measure.darken_background"))))
		self.Bind(wx.EVT_CHECKBOX, self.measure_darken_background_ctrl_handler, id = self.measure_darken_background_cb.GetId())
		self.vsizer.Add(self.measure_darken_background_cb, flag = wx.ALIGN_BOTTOM | wx.ALIGN_CENTER_HORIZONTAL | wx.LEFT | wx.RIGHT | wx.TOP, border = 10)

		self.measurebutton = wx.Button(self.panel, -1, lang.getstr("measureframe.measurebutton"))
		self.Bind(wx.EVT_BUTTON, self.measure_handler, self.measurebutton)
		self.vsizer.Add(self.measurebutton, flag = wx.ALIGN_BOTTOM | wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, border = 10)
		self.measurebutton.SetMaxFontSize(11)
		self.measurebutton.SetInitialSize((self.measurebutton.GetSize()[0] + btn_width_correction, -1))

		min_size = max(self.sizer.GetMinSize())
		self.SetMinSize((min_size, min_size)) # make sure the min size is quadratic and large enough to accomodate all controls
		self.SetMaxSize((20000, 20000))

	def measure_darken_background_ctrl_handler(self, event):
		if debug: safe_print("measure_darken_background_ctrl_handler ID %s %s TYPE %s %s" % (event.GetId(), getevtobjname(event, self), event.GetEventType(), getevttype(event)))
		if self.measure_darken_background_cb.GetValue() and getcfg("measure.darken_background.show_warning"):
			dlg = ConfirmDialog(self, msg = lang.getstr("measure.darken_background.warning"), ok = lang.getstr("ok"), cancel = lang.getstr("cancel"), bitmap = getbitmap("theme/icons/32x32/dialog-warning"))
			chk = wx.CheckBox(dlg, -1, lang.getstr("dialog.do_not_show_again"))
			dlg.Bind(wx.EVT_CHECKBOX, self.measure_darken_background_warning_handler, id = chk.GetId())
			dlg.sizer3.Add(chk, flag = wx.TOP | wx.ALIGN_LEFT, border = 12)
			dlg.sizer0.SetSizeHints(dlg)
			dlg.sizer0.Layout()
			rslt = dlg.ShowModal()
			if rslt == wx.ID_CANCEL:
				self.measure_darken_background_cb.SetValue(False)
		setcfg("measure.darken_background", int(self.measure_darken_background_cb.GetValue()))
	
	def measure_darken_background_warning_handler(self, event):
		setcfg("measure.darken_background.show_warning", int(not event.GetEventObject().GetValue()))

	def info_handler(self, event):
		InfoDialog(self, msg = lang.getstr("measureframe.info"), ok = lang.getstr("ok"), bitmap = getbitmap("theme/icons/32x32/dialog-information"), logit = False)

	def measure_handler(self, event):
		self.save_cfg()
		if self.Parent and hasattr(self.Parent, "call_pending_function"):
			self.Parent.call_pending_function()

	def save_cfg(self):
		setcfg("dimensions.measureframe", self.get_dimensions())
		if self.Parent and (self.Parent.IsShownOnScreen() or not hasattr(self.Parent, "pending_function") or os.getenv("DISPLAY") not in (None, ":0.0")) and hasattr(self.Parent, "display_ctrl"):
			display_no = self.Parent.display_ctrl.GetSelection()
		else:
			display_no = wx.Display.GetFromWindow(self)
		if display_no < 0: # window outside visible area
			display_no = 0
		setcfg("display.number", display_no + 1)
		if self.Parent:
			if hasattr(self.Parent, "display_lut_ctrl"):
				if bool(int(getcfg("display_lut.link"))):
					setcfg("display_lut.number", display_no + 1)

	def Show(self, show = True):
		if debug: safe_print("measureframe.Show", show)
		if show:
			self.measure_darken_background_cb.SetValue(bool(int(getcfg("measure.darken_background"))))
			if self.Parent and hasattr(self.Parent, "display_ctrl"):
				display_no = self.Parent.display_ctrl.GetSelection()
			else:
				display_no = wx.Display.GetFromWindow(self)
			if display_no < 0 or display_no > wx.Display.GetCount() - 1:
				display_no = 0
			x, y = wx.Display(display_no).Geometry[:2]
			self.SetPosition((x, y)) # place measure frame on correct display
			self.place_n_zoom(*floatlist(getcfg("dimensions.measureframe").split(",")))
		else:
			self.save_cfg()
			if os.getenv("DISPLAY") in (None, ":0.0"):
				display_no = wx.Display.GetFromWindow(self)
				if display_no < 0 or display_no > wx.Display.GetCount() - 1:
					display_no = 0
				if self.Parent and hasattr(self.Parent, "display_ctrl"):
					self.Parent.display_ctrl.SetSelection(display_no)
					self.Parent.display_ctrl_handler(CustomEvent(wx.EVT_COMBOBOX.evtType[0], self.Parent.display_ctrl))
		wx.CallAfter(wx.Frame.Show, self, show)

	def Hide(self):
		self.Show(False)

	def place_n_zoom(self, x = None, y = None, scale = None):
		if debug: safe_print("measureframe.place_n_zoom")
		cur_x, cur_y, cur_scale = floatlist(self.get_dimensions().split(","))
		if None in (x, y, scale):
			if x is None:
				x = cur_x
			if y is None:
				y = cur_y
			if scale is None:
				scale = cur_scale
		if scale > 50.0: # Argyll max
			scale = 50
		if debug: safe_print(" x:", x)
		if debug: safe_print(" y:", y)
		if debug: safe_print(" scale:", scale)
		if debug: safe_print(" scale_adjustment_factor:", scale_adjustment_factor)
		scale /= scale_adjustment_factor
		if debug: safe_print(" scale / scale_adjustment_factor:", scale)
		display = self.GetDisplay()
		display_client_rect = display.ClientArea
		if debug: safe_print(" display_client_rect:", display_client_rect)
		display_client_size = display_client_rect[2:]
		if debug: safe_print(" display_client_size:", display_client_size)
		measureframe_min_size = list(self.GetMinSize())
		if debug: safe_print(" measureframe_min_size:", measureframe_min_size)
		default_measureframe_size = self.get_default_size()
		measureframe_size = [min(display_client_size[0], default_measureframe_size * scale), min(display_client_size[1], default_measureframe_size * scale)]
		if measureframe_min_size[0] > measureframe_size[0]:
			measureframe_size = measureframe_min_size
		if measureframe_size[0] > display_client_size[0]:
			measureframe_size[0] = display_client_size[0]
		if measureframe_size[1] > display_client_size[1]:
			measureframe_size[1] = display_client_size[1]
		if max(measureframe_size) >= max(display_client_size):
			scale = 50
		if debug: safe_print(" measureframe_size:", measureframe_size)
		self.SetSize(measureframe_size)
		display_rect = display.Geometry
		if debug: safe_print(" display_rect:", display_rect)
		display_size = display_rect[2:]
		if debug: safe_print(" display_size:", display_size)
		measureframe_pos = [display_rect[0] + round((display_size[0] - measureframe_size[0]) * x), display_rect[1] + round((display_size[1] - measureframe_size[1]) * y)]
		if measureframe_pos[0] < display_client_rect[0]:
			measureframe_pos[0] = display_client_rect[0]
		if measureframe_pos[1] < display_client_rect[1]:
			measureframe_pos[1] = display_client_rect[1]
		if debug: safe_print(" measureframe_pos:", measureframe_pos)
		setcfg("dimensions.measureframe", ",".join(strlist((x, y, scale))))
		wx.CallAfter(self.SetPosition, measureframe_pos)

	def zoomin_handler(self, event):
		if debug: safe_print("measureframe_zoomin_handler")
		# we can't use self.get_dimensions() here because if we are near fullscreen, next magnification step will be larger than normal
		display = self.GetDisplay()
		display_size = display.Geometry[2:]
		default_measureframe_size = self.get_default_size()
		measureframe_size = floatlist(self.GetSize())
		x, y = None, None
		self.place_n_zoom(x, y, scale = (display_size[0] / default_measureframe_size) / (display_size[0] / measureframe_size[0]) + .125)

	def zoomout_handler(self, event):
		if debug: safe_print("measureframe_zoomout_handler")
		# we can't use self.get_dimensions() here because if we are fullscreen, scale will be 50, thus changes won't be visible quickly
		display = self.GetDisplay()
		display_size = display.Geometry[2:]
		default_measureframe_size = self.get_default_size()
		measureframe_size = floatlist(self.GetSize())
		x, y = None, None
		self.place_n_zoom(x, y, scale = (display_size[0] / default_measureframe_size) / (display_size[0] / measureframe_size[0]) - .125)

	def zoomnormal_handler(self, event):
		if debug: safe_print("measureframe_zoomnormal_handler")
		x, y = None, None
		self.place_n_zoom(x, y, scale = floatlist(defaults["dimensions.measureframe"].split(","))[2])

	def zoommax_handler(self, event):
		if debug: safe_print("measureframe_zoommax_handler")
		display = self.GetDisplay()
		display_client_rect = display.ClientArea
		if debug: safe_print(" display_client_rect:", display_client_rect)
		display_client_size = display.ClientArea[2:]
		if debug: safe_print(" display_client_size:", display_client_size)
		measureframe_size = self.GetSize()
		if debug: safe_print(" measureframe_size:", measureframe_size)
		if max(measureframe_size) >= max(display_client_size) - 50:
			self.place_n_zoom(*floatlist(getcfg("dimensions.measureframe.unzoomed").split(",")))
		else:
			setcfg("dimensions.measureframe.unzoomed", self.get_dimensions())
			self.place_n_zoom(x = .5, y = .5, scale = 50.0)

	def center_handler(self, event):
		if debug: safe_print("measureframe_center_handler")
		x, y = floatlist(defaults["dimensions.measureframe"].split(","))[:2]
		self.place_n_zoom(x, y)

	def close_handler(self, event):
		if debug: safe_print("measureframe_close_handler")
		self.Hide()
		if self.Parent:
			self.Parent.Show()
		else:
			writecfg()
			self.Destroy()

	def sizing_handler(self, event):
		if debug: safe_print("measureframe_sizing_handler")

	def size_handler(self, event):
		if debug: safe_print("measureframe_size_handler")
		display = self.GetDisplay()
		display_client_size = display.ClientArea[2:]
		measureframe_size = self.GetSize()
		if debug:
			safe_print(" display_client_size:", display_client_size)
			safe_print(" measureframe_size:", measureframe_size)
			measureframe_pos = self.GetScreenPosition()
			safe_print(" measureframe_pos:", measureframe_pos)
		if min(measureframe_size) < min(display_client_size) - 50 and measureframe_size[0] != measureframe_size[1]:
			if sys.platform != "win32":
				wx.CallAfter(self.SetSize, (min(measureframe_size), min(measureframe_size)))
			else:
				self.SetSize((min(measureframe_size), min(measureframe_size)))
			if debug: wx.CallAfter(self.get_dimensions)
		event.Skip()

	def get_default_size(self):
		display_no = wx.Display.GetFromWindow(self)
		if display_no < 0 or display_no > wx.Display.GetCount() - 1:
			display_no = 0
		display_rect = wx.Display(display_no).Geometry
		display_size = display_rect[2:]
		display_size_mm = []
		try:
			display_size_mm = RDSMM.RealDisplaySizeMM(display_no)
		except Exception, exception:
			handle_error("Error - RealDisplaySizeMM() failed: " + str(exception), parent = self.Parent or self)
		if not len(display_size_mm) or 0 in display_size_mm:
			ppi_def = 100.0
			ppi_mac = 72.0
			method = 1
			if method == 0:
				# use configurable screen diagonal
				inch = 20.0
				mm = inch * 25.4
				f = mm / math.sqrt(math.pow(display_size[0], 2) + math.pow(display_size[1], 2))
				w_mm = math.sqrt(math.pow(mm, 2) - math.pow(display_size[1] * f, 2))
				h_mm = math.sqrt(math.pow(mm, 2) - math.pow(display_size[0] * f, 2))
				display_size_mm = w_mm, h_mm
			elif method == 1:
				# use the first display
				display_size_1st = wx.DisplaySize()
				display_size_mm = list(wx.DisplaySizeMM())
				if sys.platform == "darwin":
					display_size_mm[0] /= (ppi_def / ppi_mac)
					display_size_mm[1] /= (ppi_def / ppi_mac)
				if display_no > 0:
					display_size_mm[0] = display_size[0] / (display_size_1st[0] / display_size_mm[0])
					display_size_mm[1] = display_size[1] / (display_size_1st[1] / display_size_mm[1])
			else:
				# use assumed ppi
				display_size_mm = display_size[0] / ppi_def * 25.4, display_size[1] / ppi_def * 25.4
		return round(100.0 * display_size[0] / display_size_mm[0])

	def get_dimensions(self):
		if debug: safe_print("measureframe.get_dimensions")
		display = self.GetDisplay()
		display_rect = display.Geometry
		display_size = display_rect[2:]
		display_client_rect = display.ClientArea
		display_client_size = display_client_rect[2:]
		if debug: safe_print(" display_size:", display_size)
		if debug: safe_print(" display_client_size:", display_client_size)
		default_measureframe_size = self.get_default_size()
		if debug: safe_print(" default_measureframe_size:", default_measureframe_size)
		measureframe_pos = floatlist(self.GetScreenPosition())
		measureframe_pos[0] -= display_rect[0]
		measureframe_pos[1] -= display_rect[1]
		if debug: safe_print(" measureframe_pos:", measureframe_pos)
		measureframe_size = floatlist(self.GetSize())
		if debug: safe_print(" measureframe_size:", measureframe_size)
		if max(measureframe_size) >= max(display_client_size) - 50: # Fullscreen?
			measureframe_scale = 50.0 # Argyll max is 50
			measureframe_pos = [.5, .5]
		else:
			measureframe_scale = (display_size[0] / default_measureframe_size) / (display_size[0] / measureframe_size[0])
			if debug: safe_print(" measureframe_scale:", measureframe_scale)
			if debug: safe_print(" scale_adjustment_factor:", scale_adjustment_factor)
			measureframe_scale *= scale_adjustment_factor
			if measureframe_size[0] >= display_client_size[0]:
				measureframe_pos[0] = .5
			elif measureframe_pos[0] != 0:
				if display_size[0] - measureframe_size[0] < measureframe_pos[0]:
					measureframe_pos[0] = display_size[0] - measureframe_size[0]
				measureframe_pos[0] = 1.0 / ((display_size[0] - measureframe_size[0]) / (measureframe_pos[0]))
			if measureframe_size[1] >= display_client_size[1]:
				measureframe_pos[1] = .5
			elif measureframe_pos[1] != 0:
				if display_size[1] - measureframe_size[1] < measureframe_pos[1]:
					measureframe_pos[1] = display_size[1] - measureframe_size[1]
				measureframe_pos[1] = 1.0 / ((display_size[1] - measureframe_size[1]) / (measureframe_pos[1]))
		if debug: safe_print(" measureframe_scale:", measureframe_scale)
		if debug: safe_print(" measureframe_pos:", measureframe_pos)
		measureframe_dimensions = str(measureframe_pos[0]) + "," + str(measureframe_pos[1]) + "," + str(measureframe_scale)
		if debug: safe_print(" measureframe_dimensions:", measureframe_dimensions)
		return measureframe_dimensions

def main():
	config.runtimeconfig(os.path.join(os.path.dirname(__file__), appname + ".py"))
	config.initcfg()
	lang.init()
	config.app = wx.App(0)
	config.app.measureframe = MeasureFrame()
	config.app.measureframe.Show()
	config.app.MainLoop()

if __name__ == "__main__":
	main()
