#!/usr/bin/env python
# -*- coding: utf-8 -*-

import math
import os
import re
import sys

import CGATS
import ICCProfile as ICCP
import colormath
import config
import localization as lang
from argyll_RGB2XYZ import RGB2XYZ as argyll_RGB2XYZ, XYZ2RGB as argyll_XYZ2RGB
from argyll_cgats import ti3_to_ti1, verify_ti1_rgb_xyz
from config import (btn_width_correction, defaults, getcfg, geticon, 
					get_bitmap_as_icon, get_data_path, get_total_patches, 
					get_verified_path, hascfg, setcfg, writecfg)
from debughelpers import handle_error
from log import safe_print
from meta import name as appname
from options import debug, tc_use_alternate_preview, test, verbose
from util_io import StringIOu as StringIO
from util_os import waccess
from util_str import safe_str, safe_unicode
from worker import (Error, Worker, check_file_isfile, check_set_argyll_bin, 
					get_argyll_version, show_result_dialog)
from wxaddons import CustomEvent, CustomGridCellEvent, FileDrop, wx
from wxwindows import ConfirmDialog, InfoDialog


def swap_dict_keys_values(mydict):
	return dict([(v, k) for (k, v) in mydict.iteritems()])


class TestchartEditor(wx.Frame):
	def __init__(self, parent = None, id = -1):
		wx.Frame.__init__(self, parent, id, lang.getstr("testchart.edit"))
		self.SetIcons(config.get_icon_bundle([256, 48, 32, 16], appname))
		self.Bind(wx.EVT_CLOSE, self.tc_close_handler)

		self.tc_algos_ab = {
			"": lang.getstr("tc.ofp"),
			"t": lang.getstr("tc.t"),
			"r": lang.getstr("tc.r"),
			"R": lang.getstr("tc.R"),
			"q": lang.getstr("tc.q"),
			"i": lang.getstr("tc.i"),
			"I": lang.getstr("tc.I")
		}
		
		self.worker = Worker()
		self.worker.argyll_version = get_argyll_version("targen", silent=True)
		
		if self.worker.argyll_version >= [1, 1, 0]:
			self.tc_algos_ab["Q"] = lang.getstr("tc.Q")

		self.tc_algos_ba = swap_dict_keys_values(self.tc_algos_ab)
		
		self.droptarget = FileDrop()
		self.droptarget.drophandlers = {
			".icc": self.ti1_drop_handler,
			".icm": self.ti1_drop_handler,
			".ti1": self.ti1_drop_handler,
			".ti3": self.ti1_drop_handler
		}
		self.droptarget.unsupported_handler = self.drop_unsupported_handler

		if tc_use_alternate_preview:
			# splitter
			splitter = self.splitter = wx.SplitterWindow(self, -1, style = wx.SP_LIVE_UPDATE | wx.SP_3D)
			self.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGED, self.tc_sash_handler, splitter)
			self.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGING, self.tc_sash_handler, splitter)

			p1 = wx.Panel(splitter)
			p1.sizer = wx.BoxSizer(wx.VERTICAL)
			p1.SetSizer(p1.sizer)

			p2 = wx.Panel(splitter)
			# Setting a droptarget seems to cause crash when destroying
			##p2.SetDropTarget(self.droptarget)
			p2.sizer = wx.BoxSizer(wx.VERTICAL)
			p2.SetSizer(p2.sizer)

			splitter.SetMinimumPaneSize(20)
			splitter.SplitHorizontally(p1, p2, -150)
			# splitter end

			panel = self.panel = p1
		else:
			panel = self.panel = wx.Panel(self)
		panel.SetDropTarget(self.droptarget)

		self.sizer = wx.BoxSizer(wx.VERTICAL)
		panel.SetSizer(self.sizer)

		border = 4

		sizer = wx.FlexGridSizer(0, 4)
		self.sizer.Add(sizer, flag = (wx.ALL & ~wx.BOTTOM), border = 12)

		# white patches
		sizer.Add(wx.StaticText(panel, -1, lang.getstr("tc.white")), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		self.tc_white_patches = wx.SpinCtrl(panel, -1, size = (65, -1), min = 0, name = "tc_white_patches")
		self.Bind(wx.EVT_TEXT, self.tc_white_patches_handler, id = self.tc_white_patches.GetId())
		sizer.Add(self.tc_white_patches, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		# single channel patches
		sizer.Add(wx.StaticText(panel, -1, lang.getstr("tc.single")), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, border = border)
		self.tc_single_channel_patches = wx.SpinCtrl(panel, -1, size = (65, -1), min = 0, max = 256, name = "tc_single_channel_patches")
		self.tc_single_channel_patches.Bind(wx.EVT_KILL_FOCUS, self.tc_single_channel_patches_handler)
		self.Bind(wx.EVT_SPINCTRL, self.tc_single_channel_patches_handler, id = self.tc_single_channel_patches.GetId())
		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(hsizer)
		hsizer.Add(self.tc_single_channel_patches, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		hsizer.Add(wx.StaticText(panel, -1, lang.getstr("tc.single.perchannel")), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		# gray axis patches
		sizer.Add(wx.StaticText(panel, -1, lang.getstr("tc.gray")), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		self.tc_gray_patches = wx.SpinCtrl(panel, -1, size = (65, -1), min = 0, max = 256, name = "tc_gray_patches")
		self.tc_gray_patches.Bind(wx.EVT_KILL_FOCUS, self.tc_gray_handler)
		self.Bind(wx.EVT_SPINCTRL, self.tc_gray_handler, id = self.tc_gray_patches.GetId())
		sizer.Add(self.tc_gray_patches, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		# multidim steps
		sizer.Add(wx.StaticText(panel, -1, lang.getstr("tc.multidim")), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, border = border)
		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(hsizer)
		self.tc_multi_steps = wx.SpinCtrl(panel, -1, size = (65, -1), min = 0, max = 21, name = "tc_multi_steps") # 16 multi dim steps = 4096 patches
		self.tc_multi_steps.Bind(wx.EVT_KILL_FOCUS, self.tc_multi_steps_handler)
		self.Bind(wx.EVT_SPINCTRL, self.tc_multi_steps_handler, id = self.tc_multi_steps.GetId())
		hsizer.Add(self.tc_multi_steps, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		self.tc_multi_patches = wx.StaticText(panel, -1, "", name = "tc_multi_patches")
		hsizer.Add(self.tc_multi_patches, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		# full spread patches
		sizer.Add(wx.StaticText(panel, -1, lang.getstr("tc.fullspread")), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		self.tc_fullspread_patches = wx.SpinCtrl(panel, -1, size = (65, -1), min = 0, max = 9999, name = "tc_fullspread_patches")
		self.Bind(wx.EVT_TEXT, self.tc_fullspread_handler, id = self.tc_fullspread_patches.GetId())
		sizer.Add(self.tc_fullspread_patches, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		# algo
		algos = self.tc_algos_ab.values()
		algos.sort()
		sizer.Add(wx.StaticText(panel, -1, lang.getstr("tc.algo")), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, border = border)
		self.tc_algo = wx.Choice(panel, -1, choices = algos, name = "tc_algo")
		self.Bind(wx.EVT_CHOICE, self.tc_algo_handler, id = self.tc_algo.GetId())
		sizer.Add(self.tc_algo, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		# adaption
		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(hsizer, 1, flag = wx.EXPAND)
		hsizer.Add(wx.StaticText(panel, -1, lang.getstr("tc.adaption")), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		self.tc_adaption_slider = wx.Slider(panel, -1, 0, 0, 100, size = (64, -1), name = "tc_adaption_slider")
		self.Bind(wx.EVT_SLIDER, self.tc_adaption_handler, id = self.tc_adaption_slider.GetId())
		hsizer.Add(self.tc_adaption_slider, flag = wx.ALIGN_CENTER_VERTICAL)
		self.tc_adaption_intctrl = wx.SpinCtrl(panel, -1, size = (65, -1), min = 0, max = 100, name = "tc_adaption_intctrl")
		self.Bind(wx.EVT_TEXT, self.tc_adaption_handler, id = self.tc_adaption_intctrl.GetId())
		sizer.Add(self.tc_adaption_intctrl, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		hsizer = wx.GridSizer(0, 2)
		sizer.Add(hsizer, 1, flag = wx.EXPAND)
		hsizer.Add(wx.StaticText(panel, -1, "%"), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		hsizer.Add(wx.StaticText(panel, -1, lang.getstr("tc.angle")), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT, border = border)

		# angle
		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		sizer.Add(hsizer, 1, flag = wx.EXPAND)
		self.tc_angle_slider = wx.Slider(panel, -1, 0, 0, 5000, size = (128, -1), name = "tc_angle_slider")
		self.Bind(wx.EVT_SLIDER, self.tc_angle_handler, id = self.tc_angle_slider.GetId())
		hsizer.Add(self.tc_angle_slider, flag = wx.ALIGN_CENTER_VERTICAL)
		self.tc_angle_intctrl = wx.SpinCtrl(panel, -1, size = (75, -1), min = 0, max = 5000, name = "tc_angle_intctrl")
		self.Bind(wx.EVT_TEXT, self.tc_angle_handler, id = self.tc_angle_intctrl.GetId())
		hsizer.Add(self.tc_angle_intctrl, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		# precond profile
		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer.Add(hsizer, flag = wx.ALL & ~(wx.BOTTOM | wx.TOP) | wx.EXPAND, border = 12)
		self.tc_precond = wx.CheckBox(panel, -1, lang.getstr("tc.precond"), name = "tc_precond")
		self.Bind(wx.EVT_CHECKBOX, self.tc_precond_handler, id = self.tc_precond.GetId())
		hsizer.Add(self.tc_precond, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		self.tc_precond_profile = wx.FilePickerCtrl(panel, -1, "", message = lang.getstr("tc.precond"), wildcard = lang.getstr("filetype.icc_mpp") + "|*.icc;*.icm;*.mpp")
		if sys.platform in ("darwin", "win32"):
			self.tc_precond_profile.PickerCtrl.Label = lang.getstr("browse")
		self.Bind(wx.EVT_FILEPICKER_CHANGED, self.tc_precond_profile_handler, id = self.tc_precond_profile.GetId())
		hsizer.Add(self.tc_precond_profile, 1, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		# limit samples to lab sphere
		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer.Add(hsizer, flag = wx.ALL & ~(wx.BOTTOM | wx.TOP), border = 12)
		self.tc_filter = wx.CheckBox(panel, -1, lang.getstr("tc.limit.sphere"), name = "tc_filter")
		self.Bind(wx.EVT_CHECKBOX, self.tc_filter_handler, id = self.tc_filter.GetId())
		hsizer.Add(self.tc_filter, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		# L
		hsizer.Add(wx.StaticText(panel, -1, "L"), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		self.tc_filter_L = wx.SpinCtrl(panel, -1, initial = 50, size = (65, -1), min = 0, max = 100, name = "tc_filter_L")
		self.Bind(wx.EVT_TEXT, self.tc_filter_handler, id = self.tc_filter_L.GetId())
		hsizer.Add(self.tc_filter_L, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		# a
		hsizer.Add(wx.StaticText(panel, -1, "a"), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		self.tc_filter_a = wx.SpinCtrl(panel, -1, initial = 0, size = (65, -1), min = -128, max = 127, name = "tc_filter_a")
		self.Bind(wx.EVT_TEXT, self.tc_filter_handler, id = self.tc_filter_a.GetId())
		hsizer.Add(self.tc_filter_a, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		# b
		hsizer.Add(wx.StaticText(panel, -1, "b"), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		self.tc_filter_b = wx.SpinCtrl(panel, -1, initial = 0, size = (65, -1), min = -128, max = 127, name = "tc_filter_b")
		self.Bind(wx.EVT_TEXT, self.tc_filter_handler, id = self.tc_filter_b.GetId())
		hsizer.Add(self.tc_filter_b, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		# radius
		hsizer.Add(wx.StaticText(panel, -1, lang.getstr("tc.limit.sphere_radius")), flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)
		self.tc_filter_rad = wx.SpinCtrl(panel, -1, initial = 255, size = (65, -1), min = 1, max = 255, name = "tc_filter_rad")
		self.Bind(wx.EVT_TEXT, self.tc_filter_handler, id = self.tc_filter_rad.GetId())
		hsizer.Add(self.tc_filter_rad, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		# diagnostic VRML files
		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer.Add(hsizer, flag = wx.ALL & ~(wx.BOTTOM | wx.TOP), border = 12 + border)
		self.tc_vrml_label = wx.StaticText(panel, -1, lang.getstr("tc.vrml"), name = "tc_vrml_label")
		hsizer.Add(self.tc_vrml_label, flag = (wx.ALL & ~wx.LEFT) | wx.ALIGN_CENTER_VERTICAL, border = border * 2)
		self.tc_vrml_lab = wx.CheckBox(panel, -1, lang.getstr("tc.vrml.lab"), name = "tc_vrml_lab", style = wx.RB_GROUP)
		self.Bind(wx.EVT_CHECKBOX, self.tc_vrml_handler, id = self.tc_vrml_lab.GetId())
		hsizer.Add(self.tc_vrml_lab, flag = (wx.ALL & ~wx.LEFT) | wx.ALIGN_CENTER_VERTICAL, border = border * 2)
		self.tc_vrml_device = wx.CheckBox(panel, -1, lang.getstr("tc.vrml.device"), name = "tc_vrml_device")
		self.Bind(wx.EVT_CHECKBOX, self.tc_vrml_handler, id = self.tc_vrml_device.GetId())
		hsizer.Add(self.tc_vrml_device, flag = (wx.ALL & ~wx.LEFT) | wx.ALIGN_CENTER_VERTICAL, border = border * 2)

		# buttons
		hsizer = wx.BoxSizer(wx.HORIZONTAL)
		self.sizer.Add(hsizer, flag = (wx.ALL & ~wx.BOTTOM) | wx.ALIGN_CENTER, border = 12)

		self.preview_btn = wx.Button(panel, -1, lang.getstr("testchart.create"), name = "tc_create")
		self.preview_btn.SetInitialSize((self.preview_btn.GetSize()[0] + btn_width_correction, -1))
		self.Bind(wx.EVT_BUTTON, self.tc_preview_handler, id = self.preview_btn.GetId())
		hsizer.Add(self.preview_btn, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		self.save_btn = wx.Button(panel, -1, lang.getstr("testchart.save"))
		self.save_btn.SetInitialSize((self.save_btn.GetSize()[0] + btn_width_correction, -1))
		self.save_btn.Disable()
		self.Bind(wx.EVT_BUTTON, self.tc_save_handler, id = self.save_btn.GetId())
		hsizer.Add(self.save_btn, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		self.save_as_btn = wx.Button(panel, -1, lang.getstr("testchart.save_as"))
		self.save_as_btn.SetInitialSize((self.save_as_btn.GetSize()[0] + btn_width_correction, -1))
		self.save_as_btn.Disable()
		self.Bind(wx.EVT_BUTTON, self.tc_save_as_handler, id = self.save_as_btn.GetId())
		hsizer.Add(self.save_as_btn, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)

		self.clear_btn = wx.Button(panel, -1, lang.getstr("testchart.discard"), name = "tc_clear")
		self.clear_btn.SetInitialSize((self.clear_btn.GetSize()[0] + btn_width_correction, -1))
		self.clear_btn.Disable()
		self.Bind(wx.EVT_BUTTON, self.tc_clear_handler, id = self.clear_btn.GetId())
		hsizer.Add(self.clear_btn, flag = wx.ALL | wx.ALIGN_CENTER_VERTICAL, border = border)


		# grid
		self.grid = wx.grid.Grid(panel, -1, size = (-1, 150), style = wx.BORDER_STATIC)
		self.grid.select_in_progress = False
		self.sizer.Add(self.grid, 1, flag = wx.ALL | wx.EXPAND, border = 12 + border)
		self.grid.CreateGrid(0, 0)
		self.Bind(wx.grid.EVT_GRID_CELL_CHANGE, self.tc_grid_cell_change_handler)
		self.grid.Bind(wx.grid.EVT_GRID_LABEL_LEFT_CLICK, self.tc_grid_label_left_click_handler)
		self.grid.Bind(wx.grid.EVT_GRID_LABEL_LEFT_DCLICK, self.tc_grid_label_left_dclick_handler)
		self.grid.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, self.tc_grid_cell_left_click_handler)
		self.grid.Bind(wx.grid.EVT_GRID_RANGE_SELECT, self.tc_grid_range_select_handler)
		self.grid.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.tc_grid_cell_select_handler)
		self.grid.DisableDragRowSize()

		# preview area
		if tc_use_alternate_preview:
			hsizer = wx.StaticBoxSizer(wx.StaticBox(p2, -1, lang.getstr("preview")), wx.VERTICAL)
			p2.sizer.Add(hsizer, 1, flag = wx.ALL | wx.ALIGN_CENTER | wx.EXPAND, border = 12)
			preview = self.preview = wx.ScrolledWindow(p2, -1, style = wx.VSCROLL)
			preview.Bind(wx.EVT_ENTER_WINDOW, self.tc_set_default_status, id = preview.GetId())
			hsizer.Add(preview, 1, wx.EXPAND)
			preview.sizer = wx.BoxSizer(wx.VERTICAL)
			preview.SetSizer(preview.sizer)

			self.patchsizer = wx.GridSizer(0, 0)
			preview.sizer.Add(self.patchsizer)
			preview.SetMinSize((-1, 100))
			panel.Bind(wx.EVT_ENTER_WINDOW, self.tc_set_default_status, id = panel.GetId())

		# status
		status = wx.StatusBar(self, -1)
		self.SetStatusBar(status)

		# layout
		self.sizer.SetSizeHints(self)
		self.sizer.Layout()
		if tc_use_alternate_preview:
			self.SetMinSize((self.GetMinSize()[0], self.GetMinSize()[1] + 150))
		
		defaults.update({
			"position.tcgen.x": self.GetDisplay().ClientArea[0] + 40,
			"position.tcgen.y": self.GetDisplay().ClientArea[1] + 60,
			"size.tcgen.w": self.GetMinSize()[0],
			"size.tcgen.h": self.GetMinSize()[1]
		})

		if hascfg("position.tcgen.x") and hascfg("position.tcgen.y") and hascfg("size.tcgen.w") and hascfg("size.tcgen.h"):
			self.SetSaneGeometry(int(getcfg("position.tcgen.x")), int(getcfg("position.tcgen.y")), int(getcfg("size.tcgen.w")), int(getcfg("size.tcgen.h")))
		else:
			self.Center()

		self.tc_size_handler()

		children = self.GetAllChildren()

		for child in children:
			if hasattr(child, "SetFont"):
				child.SetMaxFontSize(11)
			child.Bind(wx.EVT_KEY_DOWN, self.tc_key_handler)
		self.Bind(wx.EVT_MOVE, self.tc_move_handler)
		self.Bind(wx.EVT_SIZE, self.tc_size_handler, self)
		self.Bind(wx.EVT_MAXIMIZE, self.tc_size_handler, self)

		self.Children[0].Bind(wx.EVT_WINDOW_DESTROY, self.tc_destroy_handler)

		wx.CallAfter(self.tc_load_cfg_from_ti1)

	def ti1_drop_handler(self, path):
		if not self.worker.is_working():
			self.tc_load_cfg_from_ti1(None, path)

	def drop_unsupported_handler(self):
		if not self.worker.is_working():
			files = self.droptarget._filenames
			InfoDialog(self, msg = lang.getstr("error.file_type_unsupported") +
								 "\n\n" + "\n".join(files), ok = lang.getstr("ok"), bitmap = geticon(32, "dialog-error"))

	def tc_grid_cell_left_click_handler(self, event):
		event.Skip()

	def tc_grid_cell_select_handler(self, event):
		if debug: safe_print("[D] tc_grid_cell_select_handler")
		row, col = event.GetRow(), event.GetCol()
		if event.Selecting():
			pass
		self.grid.SelectBlock(row, col, row, col)
		self.tc_grid_anchor_row = row
		event.Skip()

	def tc_grid_range_select_handler(self, event):
		if debug: safe_print("[D] tc_grid_range_select_handler")
		if not self.grid.select_in_progress:
			wx.CallAfter(self.tc_set_default_status)
		event.Skip()

	def tc_grid_label_left_click_handler(self, event):
		row, col = event.GetRow(), event.GetCol()
		if row == -1 and col > -1: # col label clicked
			self.grid.SetFocus()
			self.grid.SetGridCursor(max(self.grid.GetGridCursorRow(), 0), col)
			self.grid.MakeCellVisible(max(self.grid.GetGridCursorRow(), 0), col)
		elif col == -1 and row > -1: # row label clicked
			if self.tc_grid_select_row_handler(row, event.ShiftDown(), event.ControlDown() or event.CmdDown()):
				return
		event.Skip()

	def tc_grid_label_left_dclick_handler(self, event):
		row, col = event.GetRow(), event.GetCol()
		if col == -1: # row label clicked
			self.grid.InsertRows(row + 1, 1)
			data = self.ti1.queryv1("DATA")
			wp = self.ti1.queryv1("APPROX_WHITE_POINT")
			if wp:
				wp = [float(v) for v in wp.split()]
				wp = [CGATS.rpad((v / wp[1]) * 100.0, data.vmaxlen) for v in wp]
			else:
				wp = colormath.get_standard_illuminant("D65", scale=100)
			newdata = {
				"SAMPLE_ID": row + 2,
				"RGB_R": 100.0,
				"RGB_B": 100.0,
				"RGB_G": 100.0,
				"XYZ_X": wp[0],
				"XYZ_Y": 100,
				"XYZ_Z": wp[2]
			}
			data.add_data(newdata, row + 1)
			self.tc_amount = self.ti1.queryv1("NUMBER_OF_SETS")
			self.tc_set_default_status()
			for label in ("RGB_R", "RGB_G", "RGB_B"):
				for col in range(self.grid.GetNumberCols()):
					if self.grid.GetColLabelValue(col) == label:
						self.grid.SetCellValue(row + 1, col, str(round(float(newdata[label]), 4)))
			self.tc_grid_setcolorlabel(row + 1)
			self.tc_vrml_device.SetValue(False)
			self.tc_vrml_lab.SetValue(False)
			self.ti1_wrl = None
			self.tc_save_check()
			if hasattr(self, "preview"):
				self.preview.Freeze()
				self.tc_add_patch(row + 1, data[row + 1])
				self.preview.Layout()
				self.preview.FitInside()
				self.preview.Thaw()
		event.Skip()

	def tc_grid_select_row_handler(self, row, shift = False, ctrl = False):
		if debug: safe_print("[D] tc_grid_select_row_handler")
		self.grid.SetFocus()
		if not shift and not ctrl:
			self.grid.SetGridCursor(row, max(self.grid.GetGridCursorCol(), 0))
			self.grid.MakeCellVisible(row, max(self.grid.GetGridCursorCol(), 0))
			self.grid.SelectRow(row)
			self.tc_grid_anchor_row = row
		if self.grid.IsSelection():
			if shift:
				self.grid.select_in_progress = True
				rows = self.grid.GetSelectionRows()
				sel = range(min(self.tc_grid_anchor_row, row), max(self.tc_grid_anchor_row, row))
				desel = []
				add = []
				for i in rows:
					if i not in sel:
						desel += [i]
				for i in sel:
					if i not in rows:
						add += [i]
				if len(desel) >= len(add):
					# in this case deselecting rows will take as long or longer than selecting, so use SelectRow to speed up the operation
					self.grid.SelectRow(row)
				else:
					for i in desel:
						self.grid.DeselectRow(i)
				for i in add:
					self.grid.SelectRow(i, True)
				self.grid.select_in_progress = False
				return False
			elif ctrl:
				if self.grid.IsInSelection(row, 0):
					self.grid.select_in_progress = True
					self.grid.DeselectRow(row)
					self.grid.select_in_progress = False
					self.tc_set_default_status()
					return True
				else:
					self.grid.SelectRow(row, True)
		return False

	def tc_key_handler(self, event):
		# AltDown
		# CmdDown
		# ControlDown
		# GetKeyCode
		# GetModifiers
		# GetPosition
		# GetRawKeyCode
		# GetRawKeyFlags
		# GetUniChar
		# GetUnicodeKey
		# GetX
		# GetY
		# HasModifiers
		# KeyCode
		# MetaDown
		# Modifiers
		# Position
		# RawKeyCode
		# RawKeyFlags
		# ShiftDown
		# UnicodeKey
		# X
		# Y
		if debug: safe_print("[D] event.KeyCode", event.GetKeyCode(), "event.RawKeyCode", event.GetRawKeyCode(), "event.UniChar", event.GetUniChar(), "event.UnicodeKey", event.GetUnicodeKey(), "CTRL/CMD:", event.ControlDown() or event.CmdDown(), "ALT:", event.AltDown(), "SHIFT:", event.ShiftDown())
		if (event.ControlDown() or event.CmdDown()): # CTRL (Linux/Mac/Windows) / CMD (Mac)
			key = event.GetKeyCode()
			focus = self.FindFocus()
			if self.grid in (focus, focus.GetParent(), focus.GetGrandParent()):
				if key in (8, 127): # BACKSPACE / DEL
					rows = self.grid.GetSelectionRows()
					if rows and len(rows) and min(rows) >= 0 and max(rows) + 1 <= self.grid.GetNumberRows():
						if len(rows) == self.grid.GetNumberRows():
							self.tc_check_save_ti1()
						else:
							self.tc_delete_rows(rows)
						return
				elif key == 65: # A
					self.grid.SelectAll()
					return
				elif key in (67, 88): # C / X
					clip = []
					cells = self.grid.GetSelection()
					i = -1
					start_col = self.grid.GetNumberCols()
					for cell in cells:
						row = cell[0]
						col = cell[1]
						if i < row:
							clip += [[]]
							i = row
						if col < start_col:
							start_col = col
						while len(clip[-1]) - 1 < col:
							clip[-1] += [""]
						clip[-1][col] = self.grid.GetCellValue(row, col)
					for i, row in enumerate(clip):
						clip[i] = "\t".join(row[start_col:])
					clipdata = wx.TextDataObject()
					clipdata.SetText("\n".join(clip))
					wx.TheClipboard.Open()
					wx.TheClipboard.SetData(clipdata)
					wx.TheClipboard.Close()
					return
				elif key == 86: # V
					do = wx.TextDataObject()
					wx.TheClipboard.Open()
					success = wx.TheClipboard.GetData(do)
					wx.TheClipboard.Close()
					if success:
						txt = StringIO(do.GetText())
						lines = txt.readlines()
						txt.close()
						for i, line in enumerate(lines):
							lines[i] = re.sub(" +", "\t", line).split("\t")
						# translate from selected cells into a grid with None values for not selected cells
						grid = []
						cells = self.grid.GetSelection()
						i = -1
						start_col = self.grid.GetNumberCols()
						for cell in cells:
							row = cell[0]
							col = cell[1]
							if i < row:
								grid += [[]]
								i = row
							if col < start_col:
								start_col = col
							while len(grid[-1]) - 1 < col:
								grid[-1] += [None]
							grid[-1][col] = cell
						for i, row in enumerate(grid):
							grid[i] = row[start_col:]
						# 'paste' values from clipboard
						for i, row in enumerate(grid):
							for j, cell in enumerate(row):
								if cell != None and len(lines) > i and len(lines[i]) > j and self.grid.GetColLabelValue(j):
									self.grid.SetCellValue(cell[0], cell[1], lines[i][j])
									self.tc_grid_cell_change_handler(CustomGridCellEvent(wx.grid.EVT_GRID_CELL_CHANGE.evtType[0], self.grid, cell[0], cell[1]))
					return
			if key == 83: # S
				if (hasattr(self, "ti1")):
					if event.ShiftDown() or event.AltDown() or not os.path.exists(self.ti1.filename):
						self.tc_save_as_handler()
					elif self.ti1.modified:
						self.tc_save_handler()
				return
			else:
				event.Skip()
		else:
			event.Skip()

	def tc_sash_handler(self, event):
		if event.GetSashPosition() < self.sizer.GetMinSize()[1]:
			self.splitter.SetSashPosition(self.sizer.GetMinSize()[1])
		event.Skip()

	def tc_size_handler(self, event = None):
		if hasattr(self, "preview"):
			safe_margin = 5
			scrollbarwidth = 20
			self.patchsizer.SetCols((self.preview.GetSize()[0] - scrollbarwidth - safe_margin) / 20)
		if self.IsShownOnScreen() and not self.IsMaximized() and not self.IsIconized():
			w, h = self.GetSize()
			setcfg("size.tcgen.w", w)
			setcfg("size.tcgen.h", h)
		if event:
			event.Skip()

	def tc_grid_cell_change_handler(self, event):
		data = self.ti1.queryv1("DATA")
		sample = data[event.GetRow()]
		label = self.grid.GetColLabelValue(event.GetCol())
		value = self.grid.GetCellValue(event.GetRow(), event.GetCol()).replace(",", ".")
		try:
			value = float(value)
		except ValueError, exception:
			if label in self.ti1.queryv1("DATA_FORMAT").values():
				value = sample[label]
			else:
				value = ""
		else:
			if label in ("RGB_R", "RGB_G", "RGB_B"):
				if value > 100:
					value = 100.0
				elif value < 0:
					value = 0.0
				sample[label] = value
				# If the same RGB combo is already in the ti1, use its XYZ
				# TODO: Implement proper lookup when using precond profile
				ref = data.queryi({"RGB_R": sample["RGB_R"],
								   "RGB_G": sample["RGB_G"],
								   "RGB_B": sample["RGB_B"]})
				if ref:
					for i in ref:
						if ref[i] != sample:
							ref = ref[i]
							break
				if "XYZ_X" in ref:
					XYZ = [component / 100.0 for component in (ref["XYZ_X"], ref["XYZ_Y"], ref["XYZ_Z"])]
				else:
					# Fall back to default D65-ish values
					XYZ = argyll_RGB2XYZ(*[component / 100.0 for component in (sample["RGB_R"], sample["RGB_G"], sample["RGB_B"])])
				sample["XYZ_X"], sample["XYZ_Y"], sample["XYZ_Z"] = [component * 100.0 for component in XYZ]
				for label in ("XYZ_X", "XYZ_Y", "XYZ_Z"):
					for col in range(self.grid.GetNumberCols()):
						if self.grid.GetColLabelValue(col) == label:
							self.grid.SetCellValue(event.GetRow(), col, str(round(sample[label], 4)))
			elif label in ("XYZ_X", "XYZ_Y", "XYZ_Z"):
				# FIXME: Should this be removed? There are no XYZ fields in the editor 
				if value < 0:
					value = 0.0
				sample[label] = value
				RGB = argyll_XYZ2RGB(*[component / 100.0 for component in (sample["XYZ_X"], sample["XYZ_Y"], sample["XYZ_Z"])])
				sample["RGB_R"], sample["RGB_G"], sample["RGB_B"] = [component * 100.0 for component in RGB]
				for label in ("RGB_R", "RGB_G", "RGB_B"):
					for col in range(self.grid.GetNumberCols()):
						if self.grid.GetColLabelValue(col) == label:
							self.grid.SetCellValue(event.GetRow(), col, str(round(sample[label], 4)))
			self.tc_grid_setcolorlabel(event.GetRow())
			self.tc_vrml_device.SetValue(False)
			self.tc_vrml_lab.SetValue(False)
			self.ti1_wrl = None
			self.tc_save_check()
			if hasattr(self, "preview"):
				patch = self.patchsizer.GetItem(event.GetRow()).GetWindow()
				self.tc_patch_setcolorlabel(patch)
				patch.Refresh()
		self.grid.SetCellValue(event.GetRow(), event.GetCol(), CGATS.rcut(value, sample.parent.vmaxlen))

	def tc_white_patches_handler(self, event = None):
		setcfg("tc_white_patches", self.tc_white_patches.GetValue())
		self.tc_check()
		if event:
			event.Skip()

	def tc_single_channel_patches_handler(self, event = None):
		if event:
			event = CustomEvent(event.GetEventType(), event.GetEventObject())
		if event and event.GetEventType() == wx.EVT_TEXT.evtType[0]:
			wx.CallLater(3000, self.tc_single_channel_patches_handler2, event) # 3 seconds delay to allow user to finish keying in a value before it is validated
		else:
			wx.CallAfter(self.tc_single_channel_patches_handler2, event)

	def tc_single_channel_patches_handler2(self, event = None):
		if self.tc_single_channel_patches.GetValue() == 1:
			if event and event.GetEventType() in (0, wx.EVT_SPINCTRL.evtType[0]) and getcfg("tc_single_channel_patches") == 2: # decrease
				self.tc_single_channel_patches.SetValue(0)
			else: # increase
				self.tc_single_channel_patches.SetValue(2)
		setcfg("tc_single_channel_patches", self.tc_single_channel_patches.GetValue())
		self.tc_check()

	def tc_gray_handler(self, event = None):
		if event:
			event = CustomEvent(event.GetEventType(), event.GetEventObject())
		if event and event.GetEventType() == wx.EVT_TEXT.evtType[0]:
			wx.CallLater(3000, self.tc_gray_handler2, event) # 3 seconds delay to allow user to finish keying in a value before it is validated
		else:
			wx.CallAfter(self.tc_gray_handler2, event)

	def tc_gray_handler2(self, event = None):
		if self.tc_gray_patches.GetValue() == 1:
			if event and event.GetEventType() in (0, wx.EVT_SPINCTRL.evtType[0]) and getcfg("tc_gray_patches") == 2: # decrease
				self.tc_gray_patches.SetValue(0)
			else: # increase
				self.tc_gray_patches.SetValue(2)
		setcfg("tc_gray_patches", self.tc_gray_patches.GetValue())
		self.tc_check()

	def tc_fullspread_handler(self, event = None):
		setcfg("tc_fullspread_patches", self.tc_fullspread_patches.GetValue())
		self.tc_algo_handler()
		self.tc_check()

	def tc_get_total_patches(self, white_patches = None, single_channel_patches = None, gray_patches = None, multi_steps = None, fullspread_patches = None):
		if hasattr(self, "ti1") and [white_patches, single_channel_patches, gray_patches, multi_steps, fullspread_patches] == [None] * 5:
			return self.ti1.queryv1("NUMBER_OF_SETS")
		if white_patches is None:
			white_patches = self.tc_white_patches.GetValue()
		if single_channel_patches is None:
			single_channel_patches = self.tc_single_channel_patches.GetValue()
		single_channel_patches_total = single_channel_patches * 3
		if gray_patches is None:
			gray_patches = self.tc_gray_patches.GetValue()
		if gray_patches == 0 and single_channel_patches > 0 and white_patches > 0:
			gray_patches = 2
		if multi_steps is None:
			multi_steps = self.tc_multi_steps.GetValue()
		if fullspread_patches is None:
			fullspread_patches = self.tc_fullspread_patches.GetValue()
		return get_total_patches(white_patches, single_channel_patches, gray_patches, multi_steps, fullspread_patches)
	
	def tc_get_white_patches(self):
		white_patches = self.tc_white_patches.GetValue()
		single_channel_patches = self.tc_single_channel_patches.GetValue()
		gray_patches = self.tc_gray_patches.GetValue()
		if gray_patches == 0 and single_channel_patches > 0 and white_patches > 0:
			gray_patches = 2
		multi_steps = self.tc_multi_steps.GetValue()
		if multi_steps > 1 or gray_patches > 1: # white always in multi channel or gray patches
			white_patches -= 1
		return max(0, white_patches)

	def tc_multi_steps_handler(self, event = None):
		if event:
			event = CustomEvent(event.GetEventType(), event.GetEventObject())
		if event and event.GetEventType() == wx.EVT_TEXT.evtType[0]:
			wx.CallLater(3000, self.tc_multi_steps_handler2, event) # 3 seconds delay to allow user to finish keying in a value before it is validated
		else:
			wx.CallAfter(self.tc_multi_steps_handler2, event)

	def tc_multi_steps_handler2(self, event = None):
		if self.tc_multi_steps.GetValue() == 1:
			if event and event.GetEventType() in (0, wx.EVT_SPINCTRL.evtType[0]) and getcfg("tc_multi_steps") == 2: # decrease
				self.tc_multi_steps.SetValue(0)
			else: # increase
				self.tc_multi_steps.SetValue(2)
		multi_steps = self.tc_multi_steps.GetValue()
		multi_patches = int(math.pow(multi_steps, 3))
		self.tc_multi_patches.SetLabel(lang.getstr("tc.multidim.patches", (multi_patches, multi_steps)))
		setcfg("tc_multi_steps", self.tc_multi_steps.GetValue())
		self.tc_check()

	def tc_algo_handler(self, event = None):
		tc_algo_enable = self.tc_fullspread_patches.GetValue() > 0
		self.tc_algo.Enable(tc_algo_enable)
		tc_algo = self.tc_algos_ba[self.tc_algo.GetStringSelection()]
		self.tc_adaption_slider.Enable(tc_algo_enable and tc_algo == "")
		self.tc_adaption_intctrl.Enable(tc_algo_enable and tc_algo == "")
		tc_precond_enable = (tc_algo in ("I", "Q", "R", "t") or (tc_algo == "" and self.tc_adaption_slider.GetValue() > 0))
		self.tc_precond.Enable(tc_algo_enable and tc_precond_enable and bool(getcfg("tc_precond_profile")))
		if not tc_precond_enable:
			self.tc_precond.SetValue(False)
		else:
			self.tc_precond.SetValue(bool(int(getcfg("tc_precond"))))
		self.tc_precond_profile.Enable(tc_algo_enable and tc_precond_enable)
		self.tc_angle_slider.Enable(tc_algo_enable and tc_algo in ("i", "I"))
		self.tc_angle_intctrl.Enable(tc_algo_enable and tc_algo in ("i", "I"))
		setcfg("tc_algo", tc_algo)

	def tc_adaption_handler(self, event = None):
		if event.GetId() == self.tc_adaption_slider.GetId():
			self.tc_adaption_intctrl.SetValue(self.tc_adaption_slider.GetValue())
		else:
			self.tc_adaption_slider.SetValue(self.tc_adaption_intctrl.GetValue())
		setcfg("tc_adaption", self.tc_adaption_intctrl.GetValue() / 100.0)
		self.tc_algo_handler()

	def tc_angle_handler(self, event = None):
		if event.GetId() == self.tc_angle_slider.GetId():
			self.tc_angle_intctrl.SetValue(self.tc_angle_slider.GetValue())
		else:
			self.tc_angle_slider.SetValue(self.tc_angle_intctrl.GetValue())
		setcfg("tc_angle", self.tc_angle_intctrl.GetValue() / 10000.0)

	def tc_precond_handler(self, event = None):
		setcfg("tc_precond", int(self.tc_precond.GetValue()))

	def tc_precond_profile_handler(self, event = None):
		tc_precond_enable = bool(self.tc_precond_profile.GetPath())
		self.tc_precond.Enable(tc_precond_enable)
		setcfg("tc_precond_profile", self.tc_precond_profile.GetPath())

	def tc_filter_handler(self, event = None):
		setcfg("tc_filter", int(self.tc_filter.GetValue()))
		setcfg("tc_filter_L", self.tc_filter_L.GetValue())
		setcfg("tc_filter_a", self.tc_filter_a.GetValue())
		setcfg("tc_filter_b", self.tc_filter_b.GetValue())
		setcfg("tc_filter_rad", self.tc_filter_rad.GetValue())

	def tc_vrml_handler(self, event = None):
		if get_argyll_version("targen", silent=True) < [1, 1, 0]:
			if event.GetId() == self.tc_vrml_device.GetId():
				self.tc_vrml_lab.SetValue(False)
			else:
				self.tc_vrml_device.SetValue(False)
		setcfg("tc_vrml_device", int(self.tc_vrml_device.GetValue()))
		setcfg("tc_vrml_lab", int(self.tc_vrml_lab.GetValue()))
		if hasattr(self, "ti1") and (self.tc_vrml_device.GetValue() or
									 self.tc_vrml_lab.GetValue()):
			self.tc_vrml_device.SetValue(False)
			self.tc_vrml_lab.SetValue(False)
			InfoDialog(self, msg = lang.getstr("testchart.vrml_denied"), ok = lang.getstr("ok"), bitmap = geticon(32, "dialog-error"), log=False)

	def tc_update_controls(self):
		self.tc_algo.SetStringSelection(self.tc_algos_ab.get(getcfg("tc_algo"), self.tc_algos_ab.get(defaults["tc_algo"])))
		self.tc_white_patches.SetValue(getcfg("tc_white_patches"))
		self.tc_single_channel_patches.SetValue(getcfg("tc_single_channel_patches"))
		self.tc_gray_patches.SetValue(getcfg("tc_gray_patches"))
		self.tc_multi_steps.SetValue(getcfg("tc_multi_steps"))
		self.tc_multi_steps_handler2()
		self.tc_fullspread_patches.SetValue(getcfg("tc_fullspread_patches"))
		self.tc_angle_slider.SetValue(getcfg("tc_angle") * 10000)
		self.tc_angle_handler(self.tc_angle_slider)
		self.tc_adaption_slider.SetValue(getcfg("tc_adaption") * 100)
		self.tc_adaption_handler(self.tc_adaption_slider)
		self.tc_precond_profile.SetPath(getcfg("tc_precond_profile"))
		self.tc_filter.SetValue(bool(int(getcfg("tc_filter"))))
		self.tc_filter_L.SetValue(getcfg("tc_filter_L"))
		self.tc_filter_a.SetValue(getcfg("tc_filter_a"))
		self.tc_filter_b.SetValue(getcfg("tc_filter_b"))
		self.tc_filter_rad.SetValue(getcfg("tc_filter_rad"))
		self.tc_vrml_lab.SetValue(bool(int(getcfg("tc_vrml_lab"))))
		self.tc_vrml_device.SetValue(bool(int(getcfg("tc_vrml_device"))))

	def tc_check(self, event = None):
		white_patches = self.tc_white_patches.GetValue()
		self.tc_amount = self.tc_get_total_patches(white_patches)
		self.preview_btn.Enable(self.tc_amount - max(0, self.tc_get_white_patches()) >= 8)
		self.clear_btn.Enable(hasattr(self, "ti1"))
		self.tc_save_check()
		self.save_as_btn.Enable(hasattr(self, "ti1"))
		self.tc_set_default_status()
	
	def tc_save_check(self):
		self.save_btn.Enable(hasattr(self, "ti1") and self.ti1.modified and 
							 os.path.exists(self.ti1.filename) and 
							 get_data_path(os.path.join("ti1", os.path.basename(self.ti1.filename))) != self.ti1.filename)

	def tc_save_cfg(self):
		setcfg("tc_white_patches", self.tc_white_patches.GetValue())
		setcfg("tc_single_channel_patches", self.tc_single_channel_patches.GetValue())
		setcfg("tc_gray_patches", self.tc_gray_patches.GetValue())
		setcfg("tc_multi_steps", self.tc_multi_steps.GetValue())
		setcfg("tc_fullspread_patches", self.tc_fullspread_patches.GetValue())
		tc_algo = self.tc_algos_ba[self.tc_algo.GetStringSelection()]
		setcfg("tc_algo", tc_algo)
		setcfg("tc_angle", self.tc_angle_intctrl.GetValue() / 10000.0)
		setcfg("tc_adaption", self.tc_adaption_intctrl.GetValue() / 100.0)
		tc_precond_enable = tc_algo in ("I", "Q", "R", "t") or (tc_algo == "" and self.tc_adaption_slider.GetValue() > 0)
		if tc_precond_enable:
			setcfg("tc_precond", int(self.tc_precond.GetValue()))
		setcfg("tc_precond_profile", self.tc_precond_profile.GetPath())
		setcfg("tc_filter", int(self.tc_filter.GetValue()))
		setcfg("tc_filter_L", self.tc_filter_L.GetValue())
		setcfg("tc_filter_a", self.tc_filter_a.GetValue())
		setcfg("tc_filter_b", self.tc_filter_b.GetValue())
		setcfg("tc_filter_rad", self.tc_filter_rad.GetValue())
		setcfg("tc_vrml_lab", int(self.tc_vrml_lab.GetValue()))
		setcfg("tc_vrml_device", int(self.tc_vrml_device.GetValue()))

	def tc_preview_handler(self, event = None):
		if self.worker.is_working():
			return
		if not self.tc_check_save_ti1():
			return
		if not check_set_argyll_bin():
			return
		# if sys.platform == "win32":
			# sp.call("cls", shell = True)
		# else:
			# sp.call('clear', shell = True)
		safe_print("-" * 80)
		safe_print(lang.getstr("testchart.create"))
		#self.tc_create()
		self.worker.interactive = False
		self.worker.start(self.tc_preview, self.tc_create, wargs = (), wkwargs = {}, progress_msg = lang.getstr("testchart.create"), parent = self, progress_start = 500)

	def tc_clear_handler(self, event):
		self.tc_check_save_ti1()

	def tc_clear(self):
		grid = self.grid
		if grid.GetNumberRows() > 0:
			grid.DeleteRows(0, grid.GetNumberRows())
		if grid.GetNumberCols() > 0:
			grid.DeleteCols(0, grid.GetNumberCols())
		if hasattr(self, "preview"):
			self.preview.Freeze()
			self.patchsizer.Clear(True)
			self.preview.Layout()
			self.preview.FitInside()
			self.preview.SetScrollbars(20, 20, 0, 0)
			self.preview.Thaw()
		if hasattr(self, "ti1"):
			del self.ti1
		self.ti1_wrl = None
		self.tc_update_controls()
		self.tc_check()
		# UGLY HACK: This 'safe_print' call fixes a GTK assertion and 
		# segfault under Arch Linux when setting the window title
		safe_print("")
		self.SetTitle(lang.getstr("testchart.edit"))

	def tc_save_handler(self, event = None):
		self.tc_save_as_handler(event, path = self.ti1.filename)

	def tc_save_as_handler(self, event = None, path = None):
		if path is None or not os.path.exists(path):
			path = None
			defaultDir, defaultFile = get_verified_path("last_ti1_path")[0], os.path.basename(getcfg("last_ti1_path"))
			dlg = wx.FileDialog(self, lang.getstr("testchart.save_as"), defaultDir = defaultDir, defaultFile = defaultFile, wildcard = lang.getstr("filetype.ti1") + "|*.ti1", style = wx.SAVE | wx.OVERWRITE_PROMPT)
			dlg.Center(wx.BOTH)
			if dlg.ShowModal() == wx.ID_OK:
				path = dlg.GetPath()
			dlg.Destroy()
		if path:
			if not waccess(os.path.dirname(path), os.W_OK):
				show_result_dialog(Error(lang.getstr("error.access_denied.write",
													 os.path.dirname(path))),
								   self)
				return
			filename, ext = os.path.splitext(path)
			if ext.lower() != ".ti1":
				path += ".ti1"
				if os.path.exists(path):
					dlg = ConfirmDialog(self, msg = lang.getstr("dialog.confirm_overwrite", (path)), ok = lang.getstr("overwrite"), cancel = lang.getstr("cancel"), bitmap = geticon(32, "dialog-warning"))
					result = dlg.ShowModal()
					dlg.Destroy()
					if result != wx.ID_OK:
						return
			setcfg("last_ti1_path", path)
			try:
				file_ = open(path, "w")
				file_.write(str(self.ti1))
				file_.close()
				self.ti1.filename = path
				self.ti1.root.setmodified(False)
				if not self.IsBeingDeleted():
					# UGLY HACK: This 'safe_print' call fixes a GTK assertion and 
					# segfault under Arch Linux when setting the window title
					safe_print("")
					self.SetTitle(lang.getstr("testchart.edit").rstrip(".") + ": " + os.path.basename(path))
			except Exception, exception:
				handle_error(u"Error - testchart could not be saved: " + safe_unicode(exception), parent = self)
			else:
				if hasattr(self, "ti1_wrl") and self.ti1_wrl != None:
					for vrml_type in self.ti1_wrl:
						wrlsuffix = "%s.wrl" % vrml_type
						try:
							wrl = open(os.path.splitext(path)[0] + wrlsuffix, "wb")
							wrl.write(self.ti1_wrl[vrml_type])
							wrl.close()
						except Exception, exception:
							handle_error(u"Warning - VRML file could not be saved: " + safe_unicode(exception), parent = self)
				if path != getcfg("testchart.file"):
					dlg = ConfirmDialog(self, msg = lang.getstr("testchart.confirm_select"), ok = lang.getstr("testchart.select"), cancel = lang.getstr("testchart.dont_select"), bitmap = geticon(32, "dialog-question"))
					result = dlg.ShowModal()
					dlg.Destroy()
					if result == wx.ID_OK:
						setcfg("testchart.file", path)
						writecfg()
				if path == getcfg("testchart.file") and self.Parent and hasattr(self.Parent, "set_testchart"):
					self.Parent.set_testchart(path)
				if not self.IsBeingDeleted():
					self.save_btn.Disable()
				return True
		return False

	def tc_check_save_ti1(self, clear = True):
		if hasattr(self, "ti1"):
			if self.ti1.root.modified or not os.path.exists(self.ti1.filename):
				if os.path.exists(self.ti1.filename):
					ok = lang.getstr("testchart.save")
				else:
					ok = lang.getstr("testchart.save_as")
				dlg = ConfirmDialog(self, msg = lang.getstr("testchart.save_or_discard"), ok = ok, cancel = lang.getstr("cancel"), bitmap = geticon(32, "dialog-warning"))
				if self.IsBeingDeleted():
					dlg.sizer2.Hide(0)
				if os.path.exists(self.ti1.filename):
					dlg.save_as = wx.Button(dlg, -1, lang.getstr("testchart.save_as"))
					dlg.save_as.SetInitialSize((dlg.save_as.GetSize()[0] + btn_width_correction, -1))
					ID_SAVE_AS = dlg.save_as.GetId()
					dlg.Bind(wx.EVT_BUTTON, dlg.OnClose, id = ID_SAVE_AS)
					dlg.sizer2.Add((12, 12))
					dlg.sizer2.Add(dlg.save_as)
				else:
					ID_SAVE_AS = wx.ID_OK
				dlg.discard = wx.Button(dlg, -1, lang.getstr("testchart.discard"))
				dlg.discard.SetInitialSize((dlg.discard.GetSize()[0] + btn_width_correction, -1))
				ID_DISCARD = dlg.discard.GetId()
				dlg.Bind(wx.EVT_BUTTON, dlg.OnClose, id = ID_DISCARD)
				dlg.sizer2.Add((12, 12))
				dlg.sizer2.Add(dlg.discard)
				dlg.sizer0.SetSizeHints(dlg)
				dlg.sizer0.Layout()
				result = dlg.ShowModal()
				dlg.Destroy()
				if result in (wx.ID_OK, ID_SAVE_AS):
					if result == ID_SAVE_AS:
						path = None
					else:
						path = self.ti1.filename
					if not self.tc_save_as_handler(event = None, path = path):
						return False
				elif result == wx.ID_CANCEL:
					return False
				clear = True
			if clear and not self.IsBeingDeleted():
				self.tc_clear()
		return True

	def tc_close_handler(self, event = None):
		if (not event or self.IsShownOnScreen()) and self.tc_check_save_ti1(False):
			self.Hide()
			if self.Parent:
				setcfg("tc.show", 0)
				return True
			else:
				self.Destroy()

	def tc_move_handler(self, event = None):
		if self.IsShownOnScreen() and not self.IsMaximized() and not self.IsIconized():
			x, y = self.GetScreenPosition()
			setcfg("position.tcgen.x", x)
			setcfg("position.tcgen.y", y)
		if event:
			event.Skip()

	def tc_destroy_handler(self, event):
		event.Skip()

	def tc_load_cfg_from_ti1(self, event = None, path = None):
		if self.worker.is_working():
			return

		if path is None:
			path = getcfg("testchart.file")
		try:
			filename, ext = os.path.splitext(path)
			if ext.lower() in (".ti1", ".ti3"):
				if ext.lower() == ".ti3":
					ti1 = CGATS.CGATS(ti3_to_ti1(open(path, "rU")))
					ti1.filename = filename + ".ti1"
				else:
					ti1 = CGATS.CGATS(path)
					ti1.filename = path
			else: # icc or icm profile
				profile = ICCP.ICCProfile(path)
				ti1 = CGATS.CGATS(ti3_to_ti1(profile.tags.get("CIED", "") or 
											 profile.tags.get("targ", "")))
				ti1.filename = filename + ".ti1"
			try:
				ti1_1 = verify_ti1_rgb_xyz(ti1)
			except CGATS.CGATSError, exception:
				msg = {CGATS.CGATSKeyError: lang.getstr("error.testchart.missing_fields", 
														(path, 
														 "RGB_R, RGB_G, RGB_B, "
														 " XYZ_X, XYZ_Y, XYZ_Z"))}.get(exception.__class__,
																					   lang.getstr("error.testchart.invalid",
																								   path) + 
																					   "\n" + 
																					   lang.getstr(safe_str(exception)))
				InfoDialog(self,
						   msg=msg,
						   ok=lang.getstr("ok"),
						   bitmap=geticon(32, "dialog-error"))
				return False
			else:
				if not self.tc_check_save_ti1():
					return
				ti1.root.setmodified(False)
				self.ti1 = ti1
				# UGLY HACK: This 'safe_print' call fixes a GTK assertion and 
				# segfault under Arch Linux when setting the window title
				safe_print("")
				self.SetTitle(lang.getstr("testchart.edit").rstrip(".") + ": " + os.path.basename(ti1.filename))
		except Exception, exception:
			InfoDialog(self, msg = lang.getstr("error.testchart.read", path) + "\n\n" + safe_unicode(exception), ok = lang.getstr("ok"), bitmap = geticon(32, "dialog-error"))
			return False
		safe_print(lang.getstr("testchart.read"))
		self.worker.interactive = False
		self.worker.start(self.tc_load_cfg_from_ti1_finish, self.tc_load_cfg_from_ti1_worker, wargs = (), wkwargs = {}, progress_msg = lang.getstr("testchart.read"), parent = self, progress_start = 500)

	def tc_load_cfg_from_ti1_worker(self):
		if test:
			white_patches = None
			single_channel_patches = None
			gray_patches = None
			multi_steps = None
		else:
			white_patches = self.ti1.queryv1("WHITE_COLOR_PATCHES") or None
			single_channel_patches = self.ti1.queryv1("SINGLE_DIM_STEPS") or 0
			gray_patches = self.ti1.queryv1("COMP_GREY_STEPS") or 0
			multi_steps = self.ti1.queryv1("MULTI_DIM_STEPS") or 0
		fullspread_patches = self.ti1.queryv1("NUMBER_OF_SETS")

		if None in (white_patches, single_channel_patches, gray_patches, multi_steps):
			if None in (single_channel_patches, gray_patches, multi_steps):
				white_patches = 0
				R = []
				G = []
				B = []
				gray_channel = [0]
				data = self.ti1.queryv1("DATA")
				multi = {
					"R": [],
					"G": [],
					"B": []
				}
				if multi_steps is None:
					multi_steps = 0
				uniqueRGB = []
				vmaxlen = 4
				for i in data:
					if self.worker.thread_abort:
						return False
					patch = [round(float(str(v * 2.55)), vmaxlen) for v in (data[i]["RGB_R"], data[i]["RGB_G"], data[i]["RGB_B"])] # normalize to 0...255 range
					strpatch = [str(int(round(round(v, 1)))) for v in patch]
					if patch[0] == patch[1] == patch[2] == 255: # white
						white_patches += 1
						if 255 not in gray_channel:
							gray_channel += [255]
					elif patch[0] == patch[1] == patch[2] == 0: # black
						if 0 not in R and 0 not in G and 0 not in B:
							R += [0]
							G += [0]
							B += [0]
						if 0 not in gray_channel:
							gray_channel += [0]
					elif patch[2] == patch[1] == 0 and patch[0] not in R: # red
						R += [patch[0]]
					elif patch[0] == patch[2] == 0 and patch[1] not in G: # green
						G += [patch[1]]
					elif patch[0] == patch[1] == 0 and patch[2] not in B: # blue
						B += [patch[2]]
					elif patch[0] == patch[1] == patch[2]: # gray
						if patch[0] not in gray_channel:
							gray_channel += [patch[0]]
					elif multi_steps == 0:
						multi_steps = None
					if debug >= 9: safe_print("[D]", strpatch)
					if strpatch not in uniqueRGB:
						uniqueRGB += [strpatch]
						if patch[0] not in multi["R"]:
							multi["R"] += [patch[0]]
						if patch[1] not in multi["G"]:
							multi["G"] += [patch[1]]
						if patch[2] not in multi["B"]:
							multi["B"] += [patch[2]]

				if single_channel_patches is None:
					R_inc = self.tc_get_increments(R, vmaxlen)
					G_inc = self.tc_get_increments(G, vmaxlen)
					B_inc = self.tc_get_increments(B, vmaxlen)
					if debug: 
						safe_print("[D] R_inc:")
						for i in R_inc:
							if self.worker.thread_abort:
								return False
							safe_print("[D] %s: x%s" % (i, R_inc[i]))
						safe_print("[D] G_inc:")
						for i in G_inc:
							if self.worker.thread_abort:
								return False
							safe_print("[D] %s: x%s" % (i, G_inc[i]))
						safe_print("[D] B_inc:")
						for i in B_inc:
							if self.worker.thread_abort:
								return False
							safe_print("[D] %s: x%s" % (i, B_inc[i]))
					RGB_inc = {"0": 0}
					for inc in R_inc:
						if self.worker.thread_abort:
							return False
						if inc in G_inc and inc in B_inc and R_inc[inc] == G_inc[inc] == B_inc[inc]:
							RGB_inc[inc] = R_inc[inc]
					for inc in G_inc:
						if self.worker.thread_abort:
							return False
						if inc in R_inc and inc in B_inc and R_inc[inc] == G_inc[inc] == B_inc[inc]:
							RGB_inc[inc] = G_inc[inc]
					for inc in B_inc:
						if self.worker.thread_abort:
							return False
						if inc in R_inc and inc in G_inc and R_inc[inc] == G_inc[inc] == B_inc[inc]:
							RGB_inc[inc] = B_inc[inc]
					if False:
						RGB_inc_max = max(RGB_inc.values())
						if RGB_inc_max > 0:
							single_channel_patches = RGB_inc_max + 1
						else:
							single_channel_patches = 0
					else:
						single_inc = {"0": 0}
						for inc in RGB_inc:
							if self.worker.thread_abort:
								return False
							if inc != "0":
								finc = float(inc)
								n = int(round(float(str(255.0 / finc))))
								finc = 255.0 / n
								n += 1
								if debug >= 9:
									safe_print("[D] inc:", inc)
									safe_print("[D] n:", n)
								for i in range(n):
									if self.worker.thread_abort:
										return False
									v = str(int(round(float(str(i * finc)))))
									if debug >= 9: safe_print("[D] Searching for", v)
									if [v, "0", "0"] in uniqueRGB and ["0", v, "0"] in uniqueRGB and ["0", "0", v] in uniqueRGB:
										if not inc in single_inc:
											single_inc[inc] = 0
										single_inc[inc] += 1
									else:
										if debug >= 9: safe_print("[D] Not found!")
										break
						single_channel_patches = max(single_inc.values())
					if debug:
						safe_print("[D] single_channel_patches:", single_channel_patches)
					if 0 in R + G + B:
						fullspread_patches += 3 # black in single channel patches
				elif single_channel_patches >= 2:
					fullspread_patches += 3 # black always in SINGLE_DIM_STEPS

				if gray_patches is None:
					RGB_inc = self.tc_get_increments(gray_channel, vmaxlen)
					if debug:
						safe_print("[D] RGB_inc:")
						for i in RGB_inc:
							if self.worker.thread_abort:
								return False
							safe_print("[D] %s: x%s" % (i, RGB_inc[i]))
					if False:
						RGB_inc_max = max(RGB_inc.values())
						if RGB_inc_max > 0:
							gray_patches = RGB_inc_max + 1
						else:
							gray_patches = 0
					else:
						gray_inc = {"0": 0}
						for inc in RGB_inc:
							if self.worker.thread_abort:
								return False
							if inc != "0":
								finc = float(inc)
								n = int(round(float(str(255.0 / finc))))
								finc = 255.0 / n
								n += 1
								if debug >= 9:
									safe_print("[D] inc:", inc)
									safe_print("[D] n:", n)
								for i in range(n):
									if self.worker.thread_abort:
										return False
									v = str(int(round(float(str(i * finc)))))
									if debug >= 9: safe_print("[D] Searching for", v)
									if [v, v, v] in uniqueRGB:
										if not inc in gray_inc:
											gray_inc[inc] = 0
										gray_inc[inc] += 1
									else:
										if debug >= 9: safe_print("[D] Not found!")
										break
						gray_patches = max(gray_inc.values())
					if debug:
						safe_print("[D] gray_patches:", gray_patches)
					if 0 in gray_channel:
						fullspread_patches += 1 # black in gray patches
					if 255 in gray_channel:
						fullspread_patches += 1 # white in gray patches
				elif gray_patches >= 2:
					fullspread_patches += 2 # black and white always in COMP_GREY_STEPS

				if multi_steps is None:
					R_inc = self.tc_get_increments(multi["R"], vmaxlen)
					G_inc = self.tc_get_increments(multi["G"], vmaxlen)
					B_inc = self.tc_get_increments(multi["B"], vmaxlen)
					RGB_inc = {"0": 0}
					for inc in R_inc:
						if self.worker.thread_abort:
							return False
						if inc in G_inc and inc in B_inc and R_inc[inc] == G_inc[inc] == B_inc[inc]:
							RGB_inc[inc] = R_inc[inc]
					for inc in G_inc:
						if self.worker.thread_abort:
							return False
						if inc in R_inc and inc in B_inc and R_inc[inc] == G_inc[inc] == B_inc[inc]:
							RGB_inc[inc] = G_inc[inc]
					for inc in B_inc:
						if self.worker.thread_abort:
							return False
						if inc in R_inc and inc in G_inc and R_inc[inc] == G_inc[inc] == B_inc[inc]:
							RGB_inc[inc] = B_inc[inc]
					if debug:
						safe_print("[D] RGB_inc:")
						for i in RGB_inc:
							if self.worker.thread_abort:
								return False
							safe_print("[D] %s: x%s" % (i, RGB_inc[i]))
					multi_inc = {"0": 0}
					for inc in RGB_inc:
						if self.worker.thread_abort:
							return False
						if inc != "0":
							finc = float(inc)
							n = int(round(float(str(255.0 / finc))))
							finc = 255.0 / n
							n += 1
							if debug >= 9:
								safe_print("[D] inc:", inc)
								safe_print("[D] n:", n)
							for i in range(n):
								if self.worker.thread_abort:
									return False
								r = str(int(round(float(str(i * finc)))))
								for j in range(n):
									if self.worker.thread_abort:
										return False
									g = str(int(round(float(str(j * finc)))))
									for k in range(n):
										if self.worker.thread_abort:
											return False
										b = str(int(round(float(str(k * finc)))))
										if debug >= 9:
											safe_print("[D] Searching for", i, j, k, [r, g, b])
										if [r, g, b] in uniqueRGB:
											if not inc in multi_inc:
												multi_inc[inc] = 0
											multi_inc[inc] += 1
										else:
											if debug >= 9: safe_print("[D] Not found! (b loop)")
											break
									if [r, g, b] not in uniqueRGB:
										if debug >= 9: safe_print("[D] Not found! (g loop)")
										break
								if [r, g, b] not in uniqueRGB:
									if debug >= 9: safe_print("[D] Not found! (r loop)")
									break
					multi_patches = max(multi_inc.values())
					multi_steps = int(float(str(math.pow(multi_patches, 1 / 3.0))))
					if debug:
						safe_print("[D] multi_patches:", multi_patches)
						safe_print("[D] multi_steps:", multi_steps)
				elif multi_steps >= 2:
					fullspread_patches += 2 # black and white always in MULTI_DIM_STEPS
			else:
				white_patches = len(self.ti1[0].queryi({"RGB_R": 100, "RGB_G": 100, "RGB_B": 100}))
				if single_channel_patches >= 2:
					fullspread_patches += 3 # black always in SINGLE_DIM_STEPS
				if gray_patches >= 2:
					fullspread_patches += 2 # black and white always in COMP_GREY_STEPS
				if multi_steps >= 2:
					fullspread_patches += 2 # black and white always in MULTI_DIM_STEPS
			fullspread_patches -= white_patches
			fullspread_patches -= single_channel_patches * 3
			fullspread_patches -= gray_patches
			fullspread_patches -= int(float(str(math.pow(multi_steps, 3)))) - single_channel_patches * 3

		return white_patches, single_channel_patches, gray_patches, multi_steps, fullspread_patches

	def tc_load_cfg_from_ti1_finish(self, result):
		if result:
			safe_print(lang.getstr("success"))
			white_patches, single_channel_patches, gray_patches, multi_steps, fullspread_patches = result

			fullspread_ba = {
				"ERROR_OPTIMISED_PATCHES": "", # OFPS
				#"ERROR_OPTIMISED_PATCHES": "R", # Perc. space random - same keyword as OFPS :(
				"INC_FAR_PATCHES": "t", # Inc. far point
				"RANDOM_PATCHES": "r", # Dev. space random
				"SIMPLEX_DEVICE_PATCHES": "i", # Dev. space cubic grid
				"SIMPLEX_PERCEPTUAL_PATCHES": "I", # Perc. space cubic grid
				"SPACEFILING_RANDOM_PATCHES": "q",
				"SPACEFILLING_RANDOM_PATCHES": "q", # typo in Argyll. Corrected it here in advance so things don't break in the future.
			}

			algo = None

			for key in fullspread_ba.keys():
				if self.ti1.queryv1(key) > 0:
					algo = fullspread_ba[key]
					break

			if white_patches != None: setcfg("tc_white_patches", white_patches)
			if single_channel_patches != None: setcfg("tc_single_channel_patches", single_channel_patches)
			if gray_patches != None: setcfg("tc_gray_patches", gray_patches)
			if multi_steps != None: setcfg("tc_multi_steps", multi_steps)
			setcfg("tc_fullspread_patches", self.ti1.queryv1("NUMBER_OF_SETS") - self.tc_get_total_patches(white_patches, single_channel_patches, gray_patches, multi_steps, 0))
			if algo != None: setcfg("tc_algo", algo)
			writecfg()

			self.tc_update_controls()
			self.tc_vrml_device.SetValue(False)
			self.tc_vrml_lab.SetValue(False)
			self.ti1_wrl = None
			self.tc_preview(True)
			return True
		else:
			safe_print(lang.getstr("aborted"))
			self.tc_update_controls()
			self.tc_check()
			if self.Parent and hasattr(self.Parent, "start_timers"):
				self.Parent.start_timers()

	def tc_get_increments(self, channel, vmaxlen = 4):
		channel.sort()
		increments = {"0": 0}
		for i, v in enumerate(channel):
			for j in reversed(xrange(i, len(channel))):
				inc = round(float(str(channel[j] - v)), vmaxlen)
				if inc > 0:
					inc = str(inc)
					if not inc in increments:
						increments[inc] = 0
					increments[inc] += 1
		return increments

	def tc_create(self):
		writecfg()
		self.worker.argyll_version = get_argyll_version("targen", silent=True)
		cmd, args = self.worker.prepare_targen()
		if not isinstance(cmd, Exception):
			result = self.worker.exec_cmd(cmd, args, low_contrast = False, skip_scripts = True, silent = False, parent = self)
		else:
			result = cmd
		if not isinstance(result, Exception) and result:
			tmp = self.worker.create_tempdir()
			if isinstance(tmp, Exception):
				result = tmp
			if not isinstance(result, Exception):
				path = os.path.join(self.worker.tempdir, "temp.ti1")
				result = check_file_isfile(path, silent = False)
				if not isinstance(result, Exception) and result:
					try:
						self.ti1 = CGATS.CGATS(path)
						safe_print(lang.getstr("success"))
					except Exception, exception:
						return Error(u"Error - testchart file could not be read: " + safe_unicode(exception))
					self.ti1_wrl = {}
					for ctrl in (self.tc_vrml_device, 
								 self.tc_vrml_lab):
						if ctrl.GetValue():
							vrml_type = "l" if ctrl.Name == "tc_vrml_lab" else "d"
							if self.worker.argyll_version >= [1, 1, 0]:
								wrlname = "temp%s.wrl" % vrml_type
							else:
								wrlname = "temp.wrl"
							try:
								wrl = open(os.path.join(self.worker.tempdir, wrlname), "rb")
								self.ti1_wrl[vrml_type] = wrl.read()
								wrl.close()
							except Exception, exception:
								return Error(u"Warning - VRML file could not be read: " + safe_unicode(exception))
		self.worker.wrapup(False)
		return result

	def tc_preview(self, result):
		self.tc_check()
		if isinstance(result, Exception):
			show_result_dialog(result, self)
		elif result:
			if verbose >= 1: safe_print(lang.getstr("tc.preview.create"))
			data = self.ti1.queryv1("DATA")

			if hasattr(self, "preview"):
				self.preview.Freeze()

			grid = self.grid
			data_format = self.ti1.queryv1("DATA_FORMAT")
			for i in data_format:
				if data_format[i] in ("RGB_R", "RGB_G", "RGB_B"):
					grid.AppendCols(1)
					grid.SetColLabelValue(grid.GetNumberCols() - 1, data_format[i])
			grid.AppendCols(1)
			grid.SetColLabelValue(grid.GetNumberCols() - 1, "")
			colwidth = 100
			for i in range(grid.GetNumberCols() - 1):
				grid.SetColSize(i, colwidth)
			grid.SetColSize(grid.GetNumberCols() - 1, 20)
			self.tc_amount = self.ti1.queryv1("NUMBER_OF_SETS")
			grid.AppendRows(self.tc_amount)
			grid.SetRowLabelSize(colwidth)
			attr = wx.grid.GridCellAttr()
			attr.SetAlignment(wx.ALIGN_CENTER, wx.ALIGN_CENTER)
			attr.SetReadOnly()
			grid.SetColAttr(grid.GetNumberCols() - 1, attr)

			for i in data:
				sample = data[i]
				for j in range(grid.GetNumberCols()):
					label = grid.GetColLabelValue(j)
					if label in ("RGB_R", "RGB_G", "RGB_B"):
						grid.SetCellValue(i, j, str(sample[label]))
				self.tc_grid_setcolorlabel(i)
				self.tc_add_patch(i, sample)

			if hasattr(self, "preview"):
				self.patchsizer.Layout()
				self.preview.sizer.Layout()
				self.preview.FitInside()
				self.preview.SetScrollRate(20, 20)
				self.preview.Thaw()

			self.tc_set_default_status()
			if verbose >= 1: safe_print(lang.getstr("success"))
		if self.Parent and hasattr(self.Parent, "start_timers"):
			self.Parent.start_timers()

	def tc_add_patch(self, before, sample):
		if hasattr(self, "preview"):
			patch = wx.Panel(self.preview, -1)
			patch.Bind(wx.EVT_ENTER_WINDOW, self.tc_mouseover_handler, id = patch.GetId())
			patch.Bind(wx.EVT_LEFT_DOWN, self.tc_mouseclick_handler, id = patch.GetId())
			patch.SetMinSize((20,20))
			patch.sample = sample
			self.patchsizer.Insert(before, patch)
			self.tc_patch_setcolorlabel(patch)

	def tc_grid_setcolorlabel(self, row):
		grid = self.grid
		col = grid.GetNumberCols() - 1
		sample = self.ti1.queryv1("DATA")[row]
		style, colour, labeltext, labelcolour = self.tc_getcolorlabel(sample)
		grid.SetCellBackgroundColour(row, col, colour)
		grid.SetCellValue(row, col, labeltext)
		if labelcolour:
			grid.SetCellTextColour(row, col, labelcolour)

	def tc_getcolorlabel(self, sample):
		scale = 2.55
		colour = wx.Colour(*[round(value * scale) for value in (sample.RGB_R, sample.RGB_G, sample.RGB_B)])
		# mark patches:
		# W = white (R/G/B == 100)
		# K = black (R/G/B == 0)
		# k = light black (R == G == B > 0)
		# R = red
		# r = light red (R == 100 and G/B > 0)
		# G = green
		# g = light green (G == 100 and R/B > 0)
		# B = blue
		# b = light blue (B == 100 and R/G > 0)
		# C = cyan
		# c = light cyan (G/B == 100 and R > 0)
		# M = magenta
		# m = light magenta (R/B == 100 and G > 0)
		# Y = yellow
		# y = light yellow (R/G == 100 and B > 0)
		# border = 50% value
		style = wx.NO_BORDER
		if sample.RGB_R == sample.RGB_G == sample.RGB_B: # Neutral / black / white
			if sample.RGB_R < 50:
				labelcolour = wx.Colour(255, 255, 255)
			else:
				if sample.RGB_R == 50:
					style = wx.SIMPLE_BORDER
				labelcolour = wx.Colour(0, 0, 0)
			if sample.RGB_R <= 50:
				labeltext = "K"
			elif sample.RGB_R == 100:
				labeltext = "W"
			else:
				labeltext = "k"
		elif (sample.RGB_G == 0 and sample.RGB_B == 0) or (sample.RGB_R == 100 and sample.RGB_G == sample.RGB_B): # Red
			if sample.RGB_R > 75:
				labelcolour = wx.Colour(0, 0, 0)
			else:
				labelcolour = wx.Colour(255, 255, 255)
				if sample.RGB_R == 50:
					style = wx.SIMPLE_BORDER
			if sample.RGB_R == 100 and sample.RGB_G > 0:
				labeltext = "r"
			else:
				labeltext = "R"
		elif (sample.RGB_R == 0 and sample.RGB_B == 0) or (sample.RGB_G == 100 and sample.RGB_R == sample.RGB_B): # Green
			if sample.RGB_G > 75:
				labelcolour = wx.Colour(0, 0, 0)
			else:
				labelcolour = wx.Colour(255, 255, 255)
				if sample.RGB_G == 50:
					style = wx.SIMPLE_BORDER
			if sample.RGB_G == 100 and sample.RGB_R > 0:
				labeltext = "g"
			else:
				labeltext = "G"
		elif (sample.RGB_R == 0 and sample.RGB_G == 0) or (sample.RGB_B == 100 and sample.RGB_R == sample.RGB_G): # Blue
			if sample.RGB_R > 25:
				labelcolour = wx.Colour(0, 0, 0)
			else:
				labelcolour = wx.Colour(255, 255, 255)
				if sample.RGB_B == 50:
					style = wx.SIMPLE_BORDER
			if sample.RGB_B == 100 and sample.RGB_R > 0:
				labeltext = "b"
			else:
				labeltext = "B"
		elif (sample.RGB_R == 0 or sample.RGB_B == 100) and sample.RGB_G == sample.RGB_B: # Cyan
			if sample.RGB_G > 75:
				labelcolour = wx.Colour(0, 0, 0)
			else:
				labelcolour = wx.Colour(255, 255, 255)
				if sample.RGB_G == 50:
					style = wx.SIMPLE_BORDER
			if sample.RGB_G == 100 and sample.RGB_R > 0:
				labeltext = "c"
			else:
				labeltext = "C"
		elif (sample.RGB_G == 0 or sample.RGB_R == 100) and sample.RGB_R == sample.RGB_B: # Magenta
			if sample.RGB_R > 75:
				labelcolour = wx.Colour(0, 0, 0)
			else:
				labelcolour = wx.Colour(255, 255, 255)
				if sample.RGB_R == 50:
					style = wx.SIMPLE_BORDER
			if sample.RGB_R == 100 and sample.RGB_G > 0:
				labeltext = "m"
			else:
				labeltext = "M"
		elif (sample.RGB_B == 0 or sample.RGB_G == 100) and sample.RGB_R == sample.RGB_G: # Yellow
			if sample.RGB_G > 75:
				labelcolour = wx.Colour(0, 0, 0)
			else:
				labelcolour = wx.Colour(255, 255, 255)
				if sample.RGB_R == 100 and sample.RGB_G == 50:
					style = wx.SIMPLE_BORDER
			if sample.RGB_B > 0:
				labeltext = "y"
			else:
				labeltext = "Y"
		else:
			labeltext = ""
			labelcolour = None
		return style, colour, labeltext, labelcolour

	def tc_patch_setcolorlabel(self, patch):
		if hasattr(self, "preview"):
			sample = patch.sample
			style, colour, labeltext, labelcolour = self.tc_getcolorlabel(sample)
			patch.SetBackgroundColour(colour)
			if style:
				patch.SetWindowStyle(style)
			if labeltext:
				if not hasattr(patch, "label"):
					label = patch.label = wx.StaticText(patch, -1, "")
					label.SetMaxFontSize(11)
					label.patch = patch
					label.Bind(wx.EVT_ENTER_WINDOW, self.tc_mouseover_handler, id = label.GetId())
					label.Bind(wx.EVT_LEFT_DOWN, self.tc_mouseclick_handler, id = label.GetId())
				else:
					label = patch.label
				label.SetLabel(labeltext)
				label.SetForegroundColour(labelcolour)
				label.Center()
			else:
				if hasattr(patch, "label"):
					patch.label.Destroy()
					del patch.label

	def tc_set_default_status(self, event = None):
		if hasattr(self, "tc_amount"):
			statustxt = "%s: %s" % (lang.getstr("tc.patches.total"), self.tc_amount)
			sel = self.grid.GetSelectionRows()
			if sel:
				statustxt += " / %s: %s" % (lang.getstr("tc.patches.selected"), len(sel))
			self.SetStatusText(statustxt)

	def tc_mouseover_handler(self, event):
		patch = self.preview.FindWindowById(event.GetId())
		if hasattr(patch, "patch"):
			patch = patch.patch
		colour = patch.GetBackgroundColour()
		sample = patch.sample
		patchinfo = "%s %s: R=%s G=%s B=%s" % (lang.getstr("tc.patch"), sample.key + 1, colour[0], colour[1], colour[2])
		self.SetStatusText("%s: %s / %s" % (lang.getstr("tc.patches.total"), self.tc_amount, patchinfo))
		event.Skip()

	def tc_mouseclick_handler(self, event):
		patch = self.preview.FindWindowById(event.GetId())
		if hasattr(patch, "patch"):
			patch = patch.patch
		sample = patch.sample
		self.tc_grid_select_row_handler(sample.key, event.ShiftDown(), event.ControlDown() or event.CmdDown())
		return

	def tc_delete_rows(self, rows):
		self.tc_vrml_device.SetValue(False)
		self.tc_vrml_lab.SetValue(False)
		self.ti1_wrl = None
		self.grid.Freeze()
		if hasattr(self, "preview"):
			self.preview.Freeze()
		rows.sort()
		rows.reverse()
		for row in rows:
			self.grid.DeleteRows(row)
			self.ti1.queryv1("DATA").remove(row)
			if hasattr(self, "preview"):
				patch = self.patchsizer.GetItem(row).GetWindow()
				if self.patchsizer.Detach(patch):
					patch.Destroy()
		self.tc_amount = self.ti1.queryv1("NUMBER_OF_SETS")
		row = min(rows[-1], self.grid.GetNumberRows() - 1)
		self.grid.SelectRow(row)
		self.grid.SetGridCursor(row, 0)
		self.grid.MakeCellVisible(row, 0)
		self.grid.Thaw()
		self.tc_save_check()
		if hasattr(self, "preview"):
			self.preview.Layout()
			self.preview.FitInside()
			self.preview.Thaw()
		self.tc_set_default_status()

def main():
	config.initcfg()
	lang.init()
	lang.update_defaults()
	app = wx.App(0)
	app.tcframe = TestchartEditor()
	app.tcframe.Show()
	app.MainLoop()

if __name__ == "__main__":
	main()
