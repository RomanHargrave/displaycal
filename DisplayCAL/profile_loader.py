# -*- coding: utf-8 -*-

""" 
Set ICC profiles and load calibration curves for all configured display devices

"""

import os
import sys
import threading
import time

from meta import VERSION, VERSION_BASE, name as appname, version, version_short
import config
from config import appbasename, confighome, getcfg, setcfg
from log import safe_print
from options import debug

if sys.platform == "win32":
	import errno
	import ctypes
	import glob
	import math
	import struct
	import subprocess as sp
	import traceback
	import winerror
	import _winreg

	import pywintypes
	import win32api
	import win32gui
	import win32process

	from colord import device_id_from_edid
	from config import (exe, get_default_dpi, get_icon_bundle, geticon,
						iccprofiles)
	from debughelpers import handle_error
	from edid import get_edid
	from ordereddict import OrderedDict
	from util_os import getenvu
	from util_str import safe_unicode
	from util_win import (MONITORINFOF_PRIMARY,
						  calibration_management_isenabled,
						  enable_per_user_profiles,
						  get_active_display_device, get_display_devices,
						  get_file_info, get_pids, get_process_filename,
						  get_real_display_devices_info,
						  per_user_profiles_isenabled)
	from worker import UnloggedError, show_result_dialog
	from wxaddons import CustomGridCellEvent
	from wxfixes import ThemedGenButton
	from wxwindows import (BaseFrame, ConfirmDialog, CustomCellBoolRenderer,
						   CustomGrid, InfoDialog, TaskBarNotification, wx)
	import ICCProfile as ICCP
	import localization as lang
	import madvr


	def get_dialog():
		""" If there are any dialogs open, return the first one """
		dialogs = filter(lambda window: window and
										isinstance(window, wx.Dialog) and
										window.IsShown(),
						 wx.GetTopLevelWindows())
		if dialogs:
			return dialogs[0]


	class DisplayIdentificationFrame(wx.Frame):

		def __init__(self, display, pos, size):
			wx.Frame.__init__(self, None, pos=pos, size=size,
							  style=wx.CLIP_CHILDREN | wx.STAY_ON_TOP |
									wx.FRAME_NO_TASKBAR | wx.NO_BORDER,
							  name="DisplayIdentification")
			self.SetTransparent(240)
			self.Sizer = wx.BoxSizer()
			panel_outer = wx.Panel(self)
			panel_outer.BackgroundColour = "#303030"
			panel_outer.Sizer = wx.BoxSizer()
			self.Sizer.Add(panel_outer, 1, flag=wx.EXPAND)
			panel_inner = wx.Panel(panel_outer)
			panel_inner.BackgroundColour = "#0078d7"
			panel_inner.Sizer = wx.BoxSizer()
			panel_outer.Sizer.Add(panel_inner, 1, flag=wx.ALL | wx.EXPAND,
								  border=int(math.ceil(size[0] / 12. / 40)))
			display_parts = display.split("@", 1)
			if len(display_parts) > 1:
				info = display_parts[1].split(" - ", 1)
				display_parts[1] = "@" + " ".join(info[:1])
				if info[1:]:
					display_parts.append(" ".join(info[1:]))
			label = "\n".join(display_parts)
			text = wx.StaticText(panel_inner, -1, label, style=wx.ALIGN_CENTER)
			text.ForegroundColour = "#FFFFFF"
			font = wx.Font(text.Font.PointSize * size[0] / 12. / 16,
						   wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL,
						   wx.FONTWEIGHT_LIGHT)
			if not font.SetFaceName("Segoe UI Light"):
				font = text.Font
				font.PointSize *= size[0] / 12. / 16
				font.weight = wx.FONTWEIGHT_LIGHT
			text.Font = font
			panel_inner.Sizer.Add(text, 1, flag=wx.ALIGN_CENTER_VERTICAL)
			for element in (self, panel_outer, panel_inner, text):
				element.Bind(wx.EVT_LEFT_UP, lambda e: self.Close())
				element.Bind(wx.EVT_MIDDLE_UP, lambda e: self.Close())
				element.Bind(wx.EVT_RIGHT_UP, lambda e: self.Close())
			self.Bind(wx.EVT_CHAR_HOOK, lambda e: e.KeyCode == wx.WXK_ESCAPE and self.Close())
			self.Layout()
			self.Show()
			self.close_timer = wx.CallLater(3000, lambda: self and self.Close())

	class FixProfileAssociationsDialog(ConfirmDialog):

		def __init__(self, pl):
			self.pl = pl
			ConfirmDialog.__init__(self, None,
								msg=lang.getstr("profile_loader.fix_profile_associations_warning"), 
								title=pl.get_title(),
								ok=lang.getstr("profile_loader.fix_profile_associations"), 
								alt=lang.getstr("profile_associations"),
								bitmap=geticon(32, "dialog-warning"), wrap=128)
			dlg = self
			dlg.SetIcons(get_icon_bundle([256, 48, 32, 16],
						 appname + "-apply-profiles"))
			scale = getcfg("app.dpi") / get_default_dpi()
			if scale < 1:
				scale = 1
			list_panel = wx.Panel(dlg, -1)
			list_panel.BackgroundColour = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT)
			list_panel.Sizer = wx.BoxSizer(wx.HORIZONTAL)
			list_ctrl = wx.ListCtrl(list_panel, -1,
									style=wx.LC_REPORT | wx.LC_SINGLE_SEL |
										  wx.BORDER_THEME,
									name="displays2profiles")
			list_panel.Sizer.Add(list_ctrl, 1, flag=wx.ALL, border=1)
			list_ctrl.InsertColumn(0, lang.getstr("display"))
			list_ctrl.InsertColumn(1, lang.getstr("profile"))
			list_ctrl.SetColumnWidth(0, int(200 * scale))
			list_ctrl.SetColumnWidth(1, int(420 * scale))
			# Ignore item focus/selection
			list_ctrl.Bind(wx.EVT_LIST_ITEM_FOCUSED,
						   lambda e: list_ctrl.SetItemState(e.GetIndex(), 0,
															wx.LIST_STATE_FOCUSED))
			list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED,
						   lambda e: list_ctrl.SetItemState(e.GetIndex(), 0,
															wx.LIST_STATE_SELECTED))
			self.devices2profiles_ctrl = list_ctrl
			dlg.sizer3.Insert(0, list_panel, 1, flag=wx.BOTTOM | wx.ALIGN_LEFT,
							  border=12)
			self.update()

		def update(self, event=None):
			self.pl._set_display_profiles(dry_run=True)
			numdisp = min(len(self.pl.devices2profiles), 5)
			scale = getcfg("app.dpi") / get_default_dpi()
			if scale < 1:
				scale = 1
			hscroll = wx.SystemSettings_GetMetric(wx.SYS_HSCROLL_Y)
			size=(640 * scale,
				  (20 * numdisp + 25 + hscroll) * scale)
			list_ctrl = self.devices2profiles_ctrl
			list_ctrl.MinSize = size
			list_ctrl.DeleteAllItems()
			for i, (display_edid,
					profile) in enumerate(self.pl.devices2profiles.itervalues()):
				index = list_ctrl.InsertStringItem(i, "")
				list_ctrl.SetStringItem(index, 0, display_edid[0])
				list_ctrl.SetStringItem(index, 1, profile)
				try:
					profile = ICCP.ICCProfile(profile)
				except (IOError, ICCP.ICCProfileInvalidError), exception:
					pass
				else:
					if isinstance(profile.tags.get("meta"), ICCP.DictType):
						# Check if profile mapping makes sense
						id = device_id_from_edid(display_edid[1])
						if profile.tags.meta.getvalue("MAPPING_device_id") != id:
							list_ctrl.SetItemTextColour(index, "#FF8000")
			self.sizer0.SetSizeHints(self)
			self.sizer0.Layout()
			if event and not self.IsActive():
				self.RequestUserAttention()


	class ProfileLoaderExceptionsDialog(ConfirmDialog):
		
		def __init__(self, exceptions, known_apps=set()):
			self._exceptions = {}
			self.known_apps = known_apps
			scale = getcfg("app.dpi") / config.get_default_dpi()
			if scale < 1:
				scale = 1
			ConfirmDialog.__init__(self, None,
								   title=lang.getstr("exceptions"),
								   ok=lang.getstr("ok"),
								   cancel=lang.getstr("cancel"),
								   wrap=120)

			dlg = self

			dlg.SetIcons(config.get_icon_bundle([256, 48, 32, 16],
						 appname + "-apply-profiles"))

			dlg.delete_btn = wx.Button(dlg.buttonpanel, -1,
									   lang.getstr("delete"))
			dlg.sizer2.Insert(0, (12, 12))
			dlg.sizer2.Insert(0, dlg.delete_btn)
			dlg.delete_btn.Bind(wx.EVT_BUTTON, dlg.delete_handler)

			dlg.browse_btn = wx.Button(dlg.buttonpanel, -1,
									   lang.getstr("browse"))
			dlg.sizer2.Insert(0, (12, 12))
			dlg.sizer2.Insert(0, dlg.browse_btn)
			dlg.browse_btn.Bind(wx.EVT_BUTTON, dlg.browse_handler)

			dlg.add_btn = wx.Button(dlg.buttonpanel, -1, lang.getstr("add"))
			dlg.sizer2.Insert(0, (12, 12))
			dlg.sizer2.Insert(0, dlg.add_btn)
			dlg.add_btn.Bind(wx.EVT_BUTTON, dlg.browse_handler)

			if "gtk3" in wx.PlatformInfo:
				style = wx.BORDER_SIMPLE
			else:
				style = wx.BORDER_THEME
			dlg.grid = CustomGrid(dlg, -1, size=(648 * scale, 200 * scale), style=style)
			grid = dlg.grid
			grid.DisableDragRowSize()
			grid.SetCellHighlightPenWidth(0)
			grid.SetCellHighlightROPenWidth(0)
			grid.SetDefaultCellAlignment(wx.ALIGN_LEFT, wx.ALIGN_CENTER)
			grid.SetMargins(0, 0)
			grid.SetRowLabelAlignment(wx.ALIGN_RIGHT, wx.ALIGN_CENTER)
			grid.SetScrollRate(5, 5)
			grid.draw_horizontal_grid_lines = False
			grid.draw_vertical_grid_lines = False
			grid.CreateGrid(0, 4)
			grid.SetSelectionMode(wx.grid.Grid.SelectRows)
			font = grid.GetDefaultCellFont()
			if font.PointSize > 11:
				font.PointSize = 11
				grid.SetDefaultCellFont(font)
			grid.SetColLabelSize(int(round(self.grid.GetDefaultRowSize() * 1.4)))
			dc = wx.MemoryDC(wx.EmptyBitmap(1, 1))
			dc.SetFont(grid.GetLabelFont())
			grid.SetRowLabelSize(max(dc.GetTextExtent("99")[0],
									 grid.GetDefaultRowSize()))
			for i in xrange(grid.GetNumberCols()):
				if i > 1:
					attr = wx.grid.GridCellAttr()
					attr.SetReadOnly(True) 
					grid.SetColAttr(i, attr)
				if i == 0:
					# On/off checkbox
					size = 22 * scale
				elif i == 1:
					# Profile loader state icon
					size = 22 * scale
				elif i == 2:
					# Executable basename
					size = dc.GetTextExtent("W" * 12)[0]
				else:
					# Directory component
					size = dc.GetTextExtent("W" * 34)[0]
				grid.SetColSize(i, size)
			for i, label in enumerate(["", "", "executable", "directory"]):
				grid.SetColLabelValue(i, lang.getstr(label))

			# On/off checkbox
			attr = wx.grid.GridCellAttr()
			renderer = CustomCellBoolRenderer()
			bitmap = renderer._bitmap
			image = bitmap.ConvertToImage().ConvertToGreyscale(1,
															   1,
															   1)
			renderer._bitmap_unchecked = image.ConvertToBitmap()
			attr.SetRenderer(renderer)
			grid.SetColAttr(0, attr)

			# Profile loader state icon
			attr = wx.grid.GridCellAttr()
			renderer = CustomCellBoolRenderer()
			renderer._bitmap = config.geticon(16, "apply-profiles-reset")
			bitmap = config.geticon(16, appname + "-apply-profiles")
			# Use Rec. 709 luma coefficients to convert to grayscale
			image = bitmap.ConvertToImage().ConvertToGreyscale(.2126,
															   .7152,
															   .0722)
			renderer._bitmap_unchecked = image.ConvertToBitmap()
			attr.SetRenderer(renderer)
			grid.SetColAttr(1, attr)

			attr = wx.grid.GridCellAttr()
			attr.SetRenderer(wx.grid.GridCellStringRenderer())
			grid.SetColAttr(2, attr)

			attr = wx.grid.GridCellAttr()
			attr.SetRenderer(wx.grid.GridCellStringRenderer())
			grid.SetColAttr(3, attr)
			
			grid.EnableGridLines(False)

			grid.BeginBatch()
			for i, (key,
					(enabled,
					 reset,
					 path)) in enumerate(sorted(exceptions.items())):
				grid.AppendRows(1)
				grid.SetRowLabelValue(i, "%d" % (i + 1))
				grid.SetCellValue(i, 0, "1" if enabled else "")
				grid.SetCellValue(i, 1, "1" if reset else "")
				grid.SetCellValue(i, 2, os.path.basename(path))
				grid.SetCellValue(i, 3, os.path.dirname(path))
				self._exceptions[key] = enabled, reset, path
			grid.EndBatch()

			grid.Bind(wx.EVT_KEY_DOWN, dlg.key_handler)
			grid.Bind(wx.grid.EVT_GRID_CELL_LEFT_CLICK, dlg.cell_click_handler)
			grid.Bind(wx.grid.EVT_GRID_CELL_LEFT_DCLICK, dlg.cell_dclick_handler)
			grid.Bind(wx.grid.EVT_GRID_SELECT_CELL, dlg.cell_select_handler)

			dlg.sizer3.Add(grid, 1, flag=wx.LEFT | wx.ALIGN_LEFT, border=12)

			# Legend
			sizer = wx.FlexGridSizer(2, 2, 3, 1)
			sizer.Add(wx.StaticBitmap(dlg, -1, renderer._bitmap_unchecked))
			sizer.Add(wx.StaticText(dlg, -1, " = " +
											 lang.getstr("profile_loader.disable")))
			sizer.Add(wx.StaticBitmap(dlg, -1, renderer._bitmap))
			sizer.Add(wx.StaticText(dlg, -1, " = " +
											 lang.getstr("calibration.reset")))

			dlg.sizer3.Add(sizer, 1, flag=wx.LEFT | wx.TOP | wx.ALIGN_LEFT,
						   border=12)

			dlg.buttonpanel.Layout()
			dlg.sizer0.SetSizeHints(dlg)
			dlg.sizer0.Layout()

			# This workaround is needed to update cell colours
			grid.SelectAll()
			grid.ClearSelection()

			self.check_select_status()
			dlg.ok.Disable()

			dlg.Center()

		def _get_path(self, row):
			return os.path.join(self.grid.GetCellValue(row, 3),
							    self.grid.GetCellValue(row, 2))

		def _update_exception(self, row):
			path = self._get_path(row)
			enabled = int(self.grid.GetCellValue(row, 0) or 0)
			reset = int(self.grid.GetCellValue(row, 1) or 0)
			self._exceptions[path.lower()] = enabled, reset, path

		def cell_click_handler(self, event):
			if event.Col < 2:
				if self.grid.GetCellValue(event.Row, event.Col):
					value = ""
				else:
					value = "1"
				self.grid.SetCellValue(event.Row, event.Col, value)
				self._update_exception(event.Row)
				self.ok.Enable()
			event.Skip()

		def cell_dclick_handler(self, event):
			if event.Col > 1:
				self.browse_handler(event)
			else:
				self.cell_click_handler(event)

		def cell_select_handler(self, event):
			event.Skip()
			wx.CallAfter(self.check_select_status)

		def check_select_status(self):
			rows = self.grid.GetSelectedRows()
			self.browse_btn.Enable(len(rows) == 1)
			self.delete_btn.Enable(bool(rows))

		def key_handler(self, event):
			dlg = self
			if event.KeyCode == wx.WXK_SPACE:
				dlg.cell_click_handler(CustomGridCellEvent(wx.grid.EVT_GRID_CELL_CHANGE.evtType[0],
														   dlg.grid,
														   dlg.grid.GridCursorRow,
														   dlg.grid.GridCursorCol))
			elif event.KeyCode in (wx.WXK_BACK, wx.WXK_DELETE):
				self.delete_handler(None)
			else:
				event.Skip()

		def browse_handler(self, event):
			if event.GetId() == self.add_btn.Id:
				lstr = "add"
				defaultDir = getenvu("ProgramW6432") or getenvu("ProgramFiles")
				defaultFile = ""
			else:
				lstr = "browse"
				row = self.grid.GetSelectedRows()[0]
				defaultDir = self.grid.GetCellValue(row, 3)
				defaultFile = self.grid.GetCellValue(row, 2)
			dlg = wx.FileDialog(self, lang.getstr(lstr), 
								defaultDir=defaultDir, defaultFile=defaultFile,
								wildcard="*.exe", 
								style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
			dlg.Center(wx.BOTH)
			result = dlg.ShowModal()
			path = dlg.GetPath()
			dlg.Destroy()
			if result == wx.ID_OK:
				if os.path.basename(path).lower() in self.known_apps:
					show_result_dialog(UnloggedError(lang.getstr("profile_loader.exceptions.known_app.error",
													 os.path.basename(path))))
					return
				if event.GetId() == self.add_btn.Id:
					# If it already exists, select the respective row
					if path.lower() in self._exceptions:
						for row in xrange(self.grid.GetNumberRows()):
							exception = os.path.join(self.grid.GetCellValue(row, 3),
													 self.grid.GetCellValue(row, 2))
							if exception.lower() == path.lower():
								break
					else:
						# Add new row
						self.grid.AppendRows(1)
						row = self.grid.GetNumberRows() - 1
						self.grid.SetCellValue(row, 0, "1")
						self.grid.SetCellValue(row, 1, "")
						self._exceptions[path.lower()] = 1, 0, path
				self.grid.SetCellValue(row, 2, os.path.basename(path))
				self.grid.SetCellValue(row, 3, os.path.dirname(path))
				self._update_exception(row)
				self.grid.SelectRow(row)
				self.check_select_status()
				self.grid.MakeCellVisible(row, 0)
				self.ok.Enable()

		def delete_handler(self, event):
			for row in sorted(self.grid.GetSelectedRows(), reverse=True):
				del self._exceptions[self._get_path(row).lower()]
				self.grid.DeleteRows(row)
			self.check_select_status()
			self.ok.Enable()


	class ProfileAssociationsDialog(InfoDialog):

		def __init__(self, pl):
			self.monitors = []
			self.pl = pl
			self.current_user = False
			self.display_identification_frames = {}
			InfoDialog.__init__(self, None,
								msg="",
								title=lang.getstr("profile_associations"),
								ok=lang.getstr("close"),
								bitmap=geticon(32, "display"),
								show=False, log=False, wrap=128)
			dlg = self
			dlg.SetIcons(get_icon_bundle([256, 48, 32, 16],
						 appname + "-apply-profiles"))
			dlg.message.Hide()
			dlg.set_as_default_btn = wx.Button(dlg.buttonpanel, -1, lang.getstr("set_as_default"))
			dlg.sizer2.Insert(1, dlg.set_as_default_btn, flag=wx.RIGHT, border=12)
			dlg.set_as_default_btn.Bind(wx.EVT_BUTTON, dlg.set_as_default)
			dlg.set_as_default_btn.Disable()
			dlg.remove_btn = wx.Button(dlg.buttonpanel, -1, lang.getstr("remove"))
			dlg.sizer2.Insert(0, dlg.remove_btn, flag=wx.RIGHT | wx.LEFT, border=12)
			dlg.remove_btn.Bind(wx.EVT_BUTTON, dlg.remove_profile)
			dlg.remove_btn.Disable()
			dlg.add_btn = wx.Button(dlg.buttonpanel, -1, lang.getstr("add"))
			dlg.sizer2.Insert(0, dlg.add_btn, flag=wx.LEFT, border=32 + 12)
			dlg.add_btn.Bind(wx.EVT_BUTTON, dlg.add_profile)
			scale = getcfg("app.dpi") / get_default_dpi()
			if scale < 1:
				scale = 1
			dlg.display_ctrl = wx.Choice(dlg, -1)
			dlg.display_ctrl.Bind(wx.EVT_CHOICE, dlg.update_profiles)
			dlg.sizer3.Insert(0, dlg.display_ctrl, 1, flag=wx.ALIGN_LEFT |
														   wx.EXPAND | wx.TOP,
							  border=5)
			hsizer = wx.BoxSizer(wx.HORIZONTAL)
			dlg.sizer3.Insert(1, hsizer, flag=wx.ALIGN_LEFT | wx.EXPAND)
			if sys.getwindowsversion() >= (6, ):
				dlg.use_my_settings_cb = wx.CheckBox(dlg, -1,
													 lang.getstr("profile_associations.use_my_settings"))
				dlg.use_my_settings_cb.Bind(wx.EVT_CHECKBOX, self.use_my_settings)
				hsizer.Add(dlg.use_my_settings_cb, flag=wx.TOP | wx.BOTTOM |
														wx.ALIGN_LEFT |
														wx.ALIGN_CENTER_VERTICAL,
						   border=12)
			hsizer.Add((1, 1), 1)
			identify_btn = ThemedGenButton(dlg, -1,
										   lang.getstr("displays.identify"))
			identify_btn.Bind(wx.EVT_BUTTON, dlg.identify_displays)
			hsizer.Add(identify_btn, flag=wx.ALIGN_RIGHT |
										  wx.ALIGN_CENTER_VERTICAL | wx.TOP |
										  wx.BOTTOM, border=8)
			list_panel = wx.Panel(dlg, -1)
			list_panel.BackgroundColour = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT)
			list_panel.Sizer = wx.BoxSizer(wx.HORIZONTAL)
			hscroll = wx.SystemSettings_GetMetric(wx.SYS_HSCROLL_Y)
			numrows = 10
			list_ctrl = wx.ListCtrl(list_panel, -1,
									size=(640 * scale,
										  (20 * numrows + 25 + hscroll) * scale),
									style=wx.LC_REPORT | wx.LC_SINGLE_SEL |
										  wx.BORDER_THEME,
									name="displays2profiles")
			list_panel.Sizer.Add(list_ctrl, 1, flag=wx.ALL, border=1)
			list_ctrl.InsertColumn(0, lang.getstr("profile"))
			list_ctrl.SetColumnWidth(0, int(620 * scale))
			list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED,
						   lambda e: (dlg.remove_btn.Enable(self.current_user),
									  dlg.set_as_default_btn.Enable()))
			list_ctrl.Bind(wx.EVT_LIST_ITEM_DESELECTED,
						   lambda e: (dlg.remove_btn.Disable(),
									  dlg.set_as_default_btn.Disable()))
			list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, dlg.set_as_default)
			dlg.sizer3.Add(list_panel, flag=wx.BOTTOM | wx.ALIGN_LEFT,
						   border=12)
			dlg.profiles_ctrl = list_ctrl
			dlg.fix_profile_associations_cb = wx.CheckBox(dlg, -1,
														  lang.getstr("profile_loader.fix_profile_associations"))
			dlg.fix_profile_associations_cb.SetValue(bool(getcfg("profile_loader.fix_profile_associations")))
			dlg.fix_profile_associations_cb.Bind(wx.EVT_CHECKBOX,
												 self.toggle_fix_profile_associations)
			dlg.sizer3.Add(dlg.fix_profile_associations_cb, flag=wx.ALIGN_LEFT)
			dlg.update()
			dlg.sizer0.SetSizeHints(dlg)
			dlg.sizer0.Layout()
			dlg.ok.SetDefault()

		def add_profile(self, event):
			dlg = ConfirmDialog(self,
								msg=lang.getstr("profile.choose"),
								title=lang.getstr("add"),
								ok=lang.getstr("ok"),
								cancel=lang.getstr("cancel"),
								bitmap=geticon(32, appname + "-profile-info"),
								wrap=128)
			dlg.SetIcons(get_icon_bundle([256, 48, 32, 16],
						 appname + "-apply-profiles"))
			scale = getcfg("app.dpi") / get_default_dpi()
			if scale < 1:
				scale = 1
			list_panel = wx.Panel(dlg, -1)
			list_panel.BackgroundColour = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT)
			list_panel.Sizer = wx.BoxSizer(wx.HORIZONTAL)
			hscroll = wx.SystemSettings_GetMetric(wx.SYS_HSCROLL_Y)
			numrows = 15
			list_ctrl = wx.ListCtrl(list_panel, -1,
									size=(640 * scale,
										  (20 * numrows + 25 + hscroll) * scale),
									style=wx.LC_REPORT | wx.LC_SINGLE_SEL |
										  wx.BORDER_THEME,
									name="displays2profiles")
			list_panel.Sizer.Add(list_ctrl, 1, flag=wx.ALL, border=1)
			list_ctrl.InsertColumn(0, lang.getstr("profile"))
			list_ctrl.SetColumnWidth(0, int(620 * scale))
			profiles = []
			for pth in glob.glob(os.path.join(iccprofiles[0], "*.ic[cm]")):
				try:
					profile = ICCP.ICCProfile(pth, False)
				except (IOError, ICCP.ICCProfileInvalidError, exception):
					continue
				if profile.profileClass == "mntr":
					profiles.append(os.path.basename(pth))
			for i, profile in enumerate(profiles):
				pindex = list_ctrl.InsertStringItem(i, "")
				list_ctrl.SetStringItem(pindex, 0, profile)
			dlg.profiles_ctrl = list_ctrl
			dlg.sizer3.Add(list_panel, 1, flag=wx.TOP | wx.ALIGN_LEFT, border=12)
			dlg.sizer0.SetSizeHints(dlg)
			dlg.sizer0.Layout()
			dlg.ok.SetDefault()
			dlg.Center()
			result = dlg.ShowModal()
			if result == wx.ID_OK:
				pindex = list_ctrl.GetNextItem(-1, wx.LIST_NEXT_ALL, 
											   wx.LIST_STATE_SELECTED)
				if pindex > -1:
					self.set_profile(list_ctrl.GetItemText(pindex))
				else:
					wx.Bell()
			dlg.Destroy()

		def identify_displays(self, event):
			for display, frame in self.display_identification_frames.items():
				if not frame:
					self.display_identification_frames.pop(display)
			for display, edid, moninfo, device0 in self.monitors:
				frame = self.display_identification_frames.get(display)
				if frame:
					frame.close_timer.Stop()
					frame.close_timer.Start(3000)
				else:
					m_left, m_top, m_right, m_bottom = moninfo["Monitor"]
					m_width = abs(m_right - m_left)
					m_height = abs(m_bottom - m_top)
					pos = m_left + m_width / 4, m_top + m_height / 4
					size = (m_width / 2, m_height / 2)
					frame = DisplayIdentificationFrame(display, pos, size)
					self.display_identification_frames[display] = frame

		def remove_profile(self, event):
			pindex = self.profiles_ctrl.GetNextItem(-1, wx.LIST_NEXT_ALL, 
													wx.LIST_STATE_SELECTED)
			if pindex > -1:
				self.set_profile(self.profiles[pindex], True)
			else:
				wx.Bell()

		def set_as_default(self, event):
			pindex = self.profiles_ctrl.GetNextItem(-1, wx.LIST_NEXT_ALL, 
													wx.LIST_STATE_SELECTED)
			if pindex > -1:
				self.set_profile(self.profiles[pindex])
			else:
				wx.Bell()

		def set_profile(self, profile, unset=False):
			if unset:
				fn = ICCP.unset_display_profile
			else:
				fn = ICCP.set_display_profile
			self._update_configuration(fn, profile)

		def _update_configuration(self, fn, arg0):
			dindex = self.display_ctrl.GetSelection()
			display, edid, moninfo, device0 = self.monitors[dindex]
			device = get_active_display_device(moninfo["Device"])
			if device0 and device:
				with self.pl.lock:
					fn(arg0,  devicekey=device0.DeviceKey)
					if device.DeviceKey != device0.DeviceKey:
						fn(arg0,  devicekey=device.DeviceKey)
					self.update_profiles(monitor=self.monitors[dindex])
					self.pl._next = True
			else:
				wx.Bell()

		def toggle_fix_profile_associations(self, event):
			restart = event.IsChecked()
			if restart:
				self.EndModal(wx.ID_OK)
			self.pl._toggle_fix_profile_associations(event)
			if not restart:
				self.update_profiles()

		def update(self, event=None):
			self.monitors = list(self.pl.monitors)
			self.display_ctrl.SetItems([entry[0] for entry in self.monitors])
			if self.monitors:
				self.display_ctrl.SetSelection(0)
			fix = self.pl._can_fix_profile_associations()
			self.fix_profile_associations_cb.Enable(fix)
			self.update_profiles()
			if event and not self.IsActive():
				self.RequestUserAttention()

		def update_profiles(self, event=None, monitor=None):
			self.profiles_ctrl.DeleteAllItems()
			self.add_btn.Disable()
			self.remove_btn.Disable()
			self.set_as_default_btn.Disable()
			if not monitor:
				dindex = self.display_ctrl.GetSelection()
				if dindex > -1:
					monitor = self.monitors[dindex]
				else:
					wx.Bell()
					return
			display, edid, moninfo, device0 = monitor
			device = device0
			if not device:
				wx.Bell()
				return
			monkey = device.DeviceKey.split("\\")[-2:]
			self.current_user = per_user_profiles_isenabled(devicekey=device.DeviceKey)
			if sys.getwindowsversion() >= (6, ):
				self.use_my_settings_cb.SetValue(self.current_user)
			self.profiles = ICCP._winreg_get_display_profiles(monkey, self.current_user)
			self.profiles.reverse()
			try:
				current_profile = ICCP.get_display_profile(win_get_correct_profile=True,
														   path_only=True,
														   devicekey=device.DeviceKey)
			except Exception, exception:
				current_profile = None
			i = 0
			for profile in self.profiles:
				pindex = self.profiles_ctrl.InsertStringItem(i, "")
				description = profile
				if profile == os.path.basename(current_profile or ""):
					description += " (%s)" % lang.getstr("default")
				self.profiles_ctrl.SetStringItem(pindex, 0, description)
				i += 1
			self.add_btn.Enable(self.current_user)

		def use_my_settings(self, event):
			self._update_configuration(enable_per_user_profiles,
									   event.IsChecked())


class ProfileLoader(object):

	def __init__(self):
		from wxwindows import BaseApp, wx
		if not wx.GetApp():
			app = BaseApp(0)
			BaseApp.register_exitfunc(self.shutdown)
		else:
			app = None
		self.reload_count = 0
		self.lock = threading.Lock()
		self.monitoring = True
		self.monitors = []  # Display devices that can be represented as ON
		self.display_devices = {}  # All display devices
		self.numwindows = 0
		self.profile_associations = {}
		self.profiles = {}
		self.devices2profiles = {}
		self.ramps = {}
		self.setgammaramp_success = {}
		self.use_madhcnet = bool(config.getcfg("profile_loader.use_madhcnet"))
		self._has_display_changed = False
		self._skip = "--skip" in sys.argv[1:]
		apply_profiles = bool("--force" in sys.argv[1:] or
							  config.getcfg("profile.load_on_login"))
		self._manual_restore = apply_profiles
		self._reset_gamma_ramps = bool(config.getcfg("profile_loader.reset_gamma_ramps"))
		self._known_apps = set([known_app.lower() for known_app in
								config.defaults["profile_loader.known_apps"].split(";") +
								config.getcfg("profile_loader.known_apps").split(";")])
		self._known_window_classes = set(config.defaults["profile_loader.known_window_classes"].split(";") +
										 config.getcfg("profile_loader.known_window_classes").split(";"))
		self._buggy_video_drivers = set(buggy_video_driver.lower() for buggy_video_driver in
										config.defaults["profile_loader.buggy_video_drivers"].split(";") +
										config.getcfg("profile_loader.buggy_video_drivers").split(";"))
		self._set_exceptions()
		self._madvr_instances = []
		self._timestamp = time.time()
		self._component_name = None
		self._app_detection_msg = None
		self.__other_component = None, None, 0
		self.__apply_profiles = None
		if (sys.platform == "win32" and not "--force" in sys.argv[1:] and
			sys.getwindowsversion() >= (6, 1)):
			if calibration_management_isenabled():
				# Incase calibration loading is handled by Windows 7 and
				# isn't forced
				self._manual_restore = False
		if (sys.platform != "win32" and
			apply_profiles and not self._skip and
			not os.path.isfile(os.path.join(config.confighome,
											appbasename + ".lock")) and
			not self._is_other_running(True)):
			self.apply_profiles_and_warn_on_error()
		if sys.platform == "win32":
			# We create a TSR tray program only under Windows.
			# Linux has colord/Oyranos and respective session daemons should
			# take care of calibration loading

			class PLFrame(BaseFrame):

				def __init__(self, pl):
					BaseFrame.__init__(self, None)
					self.pl = pl
					self.Bind(wx.EVT_CLOSE, pl.exit)
					self.Bind(wx.EVT_DISPLAY_CHANGED, self.pl._display_changed)

				def get_commands(self):
					return self.get_common_commands() + ["apply-profiles [force | display-changed]",
														 "notify <message> [silent] [sticky]",
														 "reset-vcgt [force]",
														 "setlanguage <languagecode>"]

				def process_data(self, data):
					if data[0] in ("apply-profiles",
								   "reset-vcgt") and (len(data) == 1 or
													  (len(data) == 2 and
													   data[1] in ("force",
																   "display-changed"))):
						if (not ("--force" in sys.argv[1:] or len(data) == 2) and
							calibration_management_isenabled()):
							return lang.getstr("calibration.load.handled_by_os")
						if ((len(data) == 1 and
							 os.path.isfile(os.path.join(config.confighome,
														 appbasename + ".lock"))) or
							self.pl._is_other_running()):
							return "forbidden"
						elif data[-1] == "display-changed":
							with self.pl.lock:
								if self.pl._has_display_changed:
									# Normally calibration loading is disabled while
									# DisplayCAL is running. Override this when the
									# display has changed
									self.pl._manual_restore = 2
						else:
							if data[0] == "reset-vcgt":
								self.pl._set_reset_gamma_ramps(None)
							else:
								self.pl._set_manual_restore(None)
							with self.pl.lock:
								self.pl._manual_restore = len(data)
						return "ok"
					elif data[0] == "notify" and (len(data) == 2 or
												  (len(data) == 3 and
												   data[2] in ("silent",
															   "sticky")) or
												  (len(data) == 4 and
												   "silent" in data[2:] and
												   "sticky" in data[2:])):
						self.pl.notify([data[1]], [],
									   sticky="sticky" in data[2:],
									   show_notification=not "silent" in data[2:])
						return "ok"
					elif data[0] == "setlanguage" and len(data) == 2:
						config.setcfg("lang", data[1])
						wx.CallAfter(self.pl.taskbar_icon.set_visual_state)
						self.pl.writecfg()
						return "ok"
					return "invalid"

			class TaskBarIcon(wx.TaskBarIcon):

				def __init__(self, pl):
					super(TaskBarIcon, self).__init__()
					self.pl = pl
					self.balloon_text = None
					self.flags = 0
					bitmap = config.geticon(16, appname + "-apply-profiles")
					icon = wx.EmptyIcon()
					icon.CopyFromBitmap(bitmap)
					self._active_icon = icon
					# Use Rec. 709 luma coefficients to convert to grayscale
					image = bitmap.ConvertToImage().ConvertToGreyscale(.2126,
																	   .7152,
																	   .0722)
					icon = wx.IconFromBitmap(image.ConvertToBitmap())
					self._inactive_icon = icon
					self._active_icon_reset = config.get_bitmap_as_icon(16, "apply-profiles-reset")
					self._error_icon = config.get_bitmap_as_icon(16, "apply-profiles-error")
					self.set_visual_state(True)
					self.Bind(wx.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)
					self.Bind(wx.EVT_TASKBAR_RIGHT_DOWN, self.on_right_down)

				def CreatePopupMenu(self):
					# Popup menu appears on right-click
					menu = wx.Menu()
					
					if (os.path.isfile(os.path.join(config.confighome,
												   appbasename + ".lock")) or
						self.pl._is_other_running()):
						restore_auto = restore_manual = reset = None
					else:
						restore_manual = self.pl._set_manual_restore
						if ("--force" in sys.argv[1:] or
							calibration_management_isenabled()):
							restore_auto = None
						else:
							restore_auto = self.set_auto_restore
						reset = self.pl._set_reset_gamma_ramps
					if (not "--force" in sys.argv[1:] and
						calibration_management_isenabled()):
						restore_auto_kind = apply_kind = wx.ITEM_NORMAL
					else:
						apply_kind = wx.ITEM_RADIO
						restore_auto_kind = wx.ITEM_CHECK

					fix = self.pl._can_fix_profile_associations()
					if fix:
						fix = self.pl._toggle_fix_profile_associations

					menu_items = [("calibration.load_from_display_profiles",
								   restore_manual, apply_kind,
								   "reset_gamma_ramps",
								   lambda v: not v),
								  ("calibration.reset",
								   reset, apply_kind,
								   "reset_gamma_ramps", None),
								  ("-", None, False, None, None),
								  ("calibration.preserve",
								   restore_auto, restore_auto_kind,
								   "profile.load_on_login", None),
								  ("profile_loader.fix_profile_associations",
								   fix,
								   wx.ITEM_CHECK,
								   "profile_loader.fix_profile_associations",
								   None),
								  ("-", None, False, None, None),
								  ("exceptions",
								   self.set_exceptions,
								   wx.ITEM_NORMAL, None, None),
								  ("-", None, False, None, None)]
					menu_items.append(("profile_associations",
									   self.pl._set_profile_associations,
									   wx.ITEM_NORMAL, None, None))
					if sys.getwindowsversion() >= (6, ):
						menu_items.append(("mswin.open_display_settings",
											self.open_display_settings,
											wx.ITEM_NORMAL, None, None))
					menu_items.append(("-", None, False, None, None))
					menu_items.append(("menuitem.quit", self.pl.exit,
									   wx.ITEM_NORMAL, None, None))
					for (label, method, kind, option, oxform) in menu_items:
						if label == "-":
							menu.AppendSeparator()
						else:
							item = wx.MenuItem(menu, -1, lang.getstr(label),
											   kind=kind)
							if not method:
								item.Enable(False)
							else:
								menu.Bind(wx.EVT_MENU, method, id=item.Id)
							menu.AppendItem(item)
							if kind != wx.ITEM_NORMAL:
								if (option == "profile.load_on_login" and
									"--force" in sys.argv[1:]):
									item.Check(True)
								else:
									if not oxform:
										oxform = bool
									if option == "reset_gamma_ramps":
										value = self.pl._reset_gamma_ramps
									else:
										value = config.getcfg(option)
									item.Check(oxform(value))

					return menu

				def get_icon(self, enumerate_windows_and_processes=False):
					if (self.pl._should_apply_profiles(enumerate_windows_and_processes,
													   manual_override=None) and
						("--force" in sys.argv[1:] or
						 config.getcfg("profile.load_on_login"))):
						count = len(self.pl.monitors)
						if len(filter(lambda (i, success): success,
									  sorted(self.pl.setgammaramp_success.items())[:count])) != count:
							icon = self._error_icon
						elif self.pl._reset_gamma_ramps:
							icon = self._active_icon_reset
						else:
							icon = self._active_icon
					else:
						icon = self._inactive_icon
					return icon

				def on_left_down(self, event):
					self.show_notification(toggle=True)

				def on_right_down(self, event):
					wx.CallLater(100, self.check_user_attention)
				
				def check_user_attention(self):
					dlg = get_dialog()
					if dlg:
						wx.Bell()
						dlg.Raise()
						dlg.RequestUserAttention()

				def open_display_settings(self, event):
					safe_print("Menu command: Open display settings")
					try:
						sp.call(["control", "/name", "Microsoft.Display",
								 "/page", "Settings"], close_fds=True)
					except Exception, exception:
						wx.Bell()
						safe_print(exception)

				def set_auto_restore(self, event):
					safe_print("Menu command: Preserve calibration state",
							   event.IsChecked())
					config.setcfg("profile.load_on_login",
								  int(event.IsChecked()))
					self.pl.writecfg()
					if event.IsChecked():
						with self.pl.lock:
							self.pl._next = event.IsChecked()
					else:
						self.set_visual_state()

				def set_exceptions(self, event):
					safe_print("Menu command: Set exceptions")
					dlg = ProfileLoaderExceptionsDialog(self.pl._exceptions,
														self.pl._known_apps)
					result = dlg.ShowModal()
					if result == wx.ID_OK:
						exceptions = []
						for key, (enabled,
								  reset,
								  path) in dlg._exceptions.iteritems():
							exceptions.append("%i:%i:%s" %
											  (enabled, reset, path))
							safe_print("Enabled=%s" % bool(enabled),
									   "Action=%s" % (reset and "Reset" or
													  "Disable"), path)
						if not exceptions:
							safe_print("Clearing exceptions")
						config.setcfg("profile_loader.exceptions",
									  ";".join(exceptions))
						self.pl._exceptions = dlg._exceptions
						self.pl.writecfg()
					else:
						safe_print("Cancelled setting exceptions")
					dlg.Destroy()

				def set_visual_state(self, enumerate_windows_and_processes=False):
					self.SetIcon(self.get_icon(enumerate_windows_and_processes),
								 self.pl.get_title())

				def show_notification(self, text=None, sticky=False,
									  show_notification=True,
									  flags=wx.ICON_INFORMATION, toggle=False):
					if wx.VERSION < (3, ) or not self.pl._check_keep_running():
						wx.Bell()
						return
					if sticky:
						self.balloon_text = text
						self.flags = flags
					elif text:
						self.balloon_text = None
						self.flags = 0
					else:
						text = self.balloon_text
						flags = self.flags or flags
					if not text:
						if (not "--force" in sys.argv[1:] and
							calibration_management_isenabled()):
							text = lang.getstr("calibration.load.handled_by_os") + "\n"
						else:
							text = ""
						if self.pl._component_name:
							text += lang.getstr("app.detected",
												self.pl._component_name) + "\n"
						text += lang.getstr("profile_loader.info",
											self.pl.reload_count)
						for i, (display, edid,
								moninfo, device0) in enumerate(self.pl.monitors):
							if device0:
								devicekey = device0.DeviceKey
							else:
								devicekey = None
							key = devicekey or str(i)
							(profile,
							 mtime) = self.pl.profile_associations.get(key,
																	   (False,
																		None))
							profile_name = profile
							if profile is False:
								profile = "?"
							elif profile == "?":
								profile = lang.getstr("unassigned").lower()
							if not self.pl.setgammaramp_success.get(i):
								profile = (lang.getstr("unknown") +
										   u" (%s)" % profile)
							elif (self.pl._reset_gamma_ramps or
								  profile_name == "?"):
								profile = (lang.getstr("linear").capitalize() +
										   u" (%s)" % profile)
							text += u"\n%s: %s" % (display, profile)
					if not show_notification:
						return
					if getattr(self, "_notification", None):
						self._notification.fade("out")
						if toggle:
							return
					bitmap = wx.BitmapFromIcon(self.get_icon())
					self._notification = TaskBarNotification(bitmap,
															 self.pl.get_title(),
															 text)

			self.taskbar_icon = TaskBarIcon(self)

			try:
				self.gdi32 = ctypes.windll.gdi32
				self.gdi32.GetDeviceGammaRamp.restype = ctypes.c_bool
				self.gdi32.SetDeviceGammaRamp.restype = ctypes.c_bool
			except Exception, exception:
				self.gdi32 = None
				safe_print(exception)
				self.taskbar_icon.show_notification(safe_unicode(exception))

			if self.use_madhcnet:
				try:
					self.madvr = madvr.MadTPG()
				except Exception, exception:
					safe_print(exception)
					if safe_unicode(exception) != lang.getstr("madvr.not_found"):
						self.taskbar_icon.show_notification(safe_unicode(exception))
				else:
					self.madvr.add_connection_callback(self._madvr_connection_callback,
													   None, "madVR")
					self.madvr.add_connection_callback(self._madvr_connection_callback,
													   None, "madTPG")
					self.madvr.listen()
					self.madvr.announce()

			self.frame = PLFrame(self)
			self.frame.listen()

			self._pid = os.getpid()
			self._tid = threading.currentThread().ident
			self._check_keep_running()

			self._check_display_conf_thread = threading.Thread(target=self._check_display_conf_wrapper,
															   name="DisplayConfigurationMonitoring")
			self._check_display_conf_thread.start()

			if app:
				app.TopWindow = self.frame
				app.MainLoop()

	def apply_profiles(self, event=None, index=None):
		import localization as lang
		from util_os import which
		from worker import Worker, get_argyll_util

		if sys.platform == "win32":
			self.lock.acquire()

		worker = Worker()

		errors = []

		if sys.platform == "win32":
			separator = "-"
		else:
			separator = "="
		safe_print(separator * 80)
		safe_print(lang.getstr("calibration.loading_from_display_profile"))

		# dispwin sets the _ICC_PROFILE(_n) root window atom, per-output xrandr 
		# _ICC_PROFILE property (if xrandr is working) and loads the vcgt for the 
		# requested screen (ucmm backend using color.jcnf), and has to be called 
		# multiple times to setup multiple screens.
		#
		# If there is no profile configured in ucmm for the requested screen (or 
		# ucmm support has been removed, like in the Argyll CMS versions shipped by 
		# recent Fedora releases), it falls back to a possibly existing per-output 
		# xrandr _ICC_PROFILE property (if xrandr is working) or _ICC_PROFILE(_n) 
		# root window atom.
		dispwin = get_argyll_util("dispwin")
		if index is None:
			if dispwin:
				worker.enumerate_displays_and_ports(silent=True, check_lut_access=False,
													enumerate_ports=False,
													include_network_devices=False)
				self.monitors = []
				if sys.platform == "win32" and worker.displays:
					self._enumerate_monitors()
			else:
				errors.append(lang.getstr("argyll.util.not_found", "dispwin"))

		if sys.platform != "win32":
			# gcm-apply sets the _ICC_PROFILE root window atom for the first screen, 
			# per-output xrandr _ICC_PROFILE properties (if xrandr is working) and 
			# loads the vcgt for all configured screens (device-profiles.conf)
			# NOTE: gcm-apply is no longer part of GNOME Color Manager since the 
			# introduction of colord as it's no longer needed
			gcm_apply = which("gcm-apply")
			if gcm_apply:
				worker.exec_cmd(gcm_apply, capture_output=True, skip_scripts=True,
								silent=False)

			# oyranos-monitor sets _ICC_PROFILE(_n) root window atoms (oyranos 
			# db backend) and loads the vcgt for all configured screens when 
			# xcalib is installed
			oyranos_monitor = which("oyranos-monitor")
			xcalib = which("xcalib")

		results = []
		for i, display in enumerate([display.replace("[PRIMARY]", 
													 lang.getstr("display.primary")) 
									 for display in worker.displays]):
			if config.is_virtual_display(i) or (index is not None
												and i != index):
				continue
			# Load profile and set vcgt
			if sys.platform != "win32" and oyranos_monitor:
				display_conf_oy_compat = worker.check_display_conf_oy_compat(i + 1)
				if display_conf_oy_compat:
					worker.exec_cmd(oyranos_monitor, 
									["-x", str(worker.display_rects[i][0]), 
									 "-y", str(worker.display_rects[i][1])], 
									capture_output=True, skip_scripts=True, 
									silent=False)
			if dispwin:
				profile_arg = worker.get_dispwin_display_profile_argument(i)
				if os.path.isabs(profile_arg) and os.path.isfile(profile_arg):
					mtime = os.stat(profile_arg).st_mtime
				else:
					mtime = 0
				if (sys.platform == "win32" or not oyranos_monitor or
					not display_conf_oy_compat or not xcalib or profile_arg == "-L"):
					# Only need to run dispwin if under Windows, or if nothing else
					# has already taken care of display profile and vcgt loading
					# (e.g. oyranos-monitor with xcalib, or colord)
					if worker.exec_cmd(dispwin, ["-v", "-d%i" % (i + 1),
												 profile_arg], 
									   capture_output=True, skip_scripts=True, 
									   silent=False):
						errortxt = ""
					else:
						errortxt = "\n".join(worker.errors).strip()
					if errortxt and ((not "using linear" in errortxt and
									  not "assuming linear" in errortxt) or 
									 len(errortxt.split("\n")) > 1):
						if "Failed to get the displays current ICC profile" in errortxt:
							# Maybe just not configured
							continue
						elif sys.platform == "win32" or \
						   "Failed to set VideoLUT" in errortxt or \
						   "We don't have access to the VideoLUT" in errortxt:
							errstr = lang.getstr("calibration.load_error")
						else:
							errstr = lang.getstr("profile.load_error")
						errors.append(": ".join([display, errstr]))
						continue
					else:
						results.append(display)
				if (config.getcfg("profile_loader.verify_calibration")
					or "--verify" in sys.argv[1:]):
					# Verify the calibration was actually loaded
					worker.exec_cmd(dispwin, ["-v", "-d%i" % (i + 1), "-V",
											  profile_arg], 
									capture_output=True, skip_scripts=True, 
									silent=False)
					# The 'NOT loaded' message goes to stdout!
					# Other errors go to stderr
					errortxt = "\n".join(worker.errors + worker.output).strip()
					if "NOT loaded" in errortxt or \
					   "We don't have access to the VideoLUT" in errortxt:
						errors.append(": ".join([display, 
												lang.getstr("calibration.load_error")]))

		if sys.platform == "win32":
			self.lock.release()
			if event:
				self.notify(results, errors)

		return errors

	def notify(self, results, errors, sticky=False, show_notification=False):
		wx.CallAfter(lambda: self and self._notify(results, errors, sticky,
												   show_notification))

	def _notify(self, results, errors, sticky=False, show_notification=False):
		self.taskbar_icon.set_visual_state()
		results.extend(errors)
		if errors:
			flags = wx.ICON_ERROR
		else:
			flags = wx.ICON_INFORMATION
		self.taskbar_icon.show_notification("\n".join(results), sticky,
											show_notification, flags)

	def apply_profiles_and_warn_on_error(self, event=None, index=None):
		# wx.App must already be initialized at this point!
		errors = self.apply_profiles(event, index)
		if (errors and (config.getcfg("profile_loader.error.show_msg") or
						"--error-dialog" in sys.argv[1:]) and
			not "--silent" in sys.argv[1:]):
			import localization as lang
			from wxwindows import InfoDialog, wx
			dlg = InfoDialog(None, msg="\n".join(errors), 
							 title=self.get_title(),
							 ok=lang.getstr("ok"),
							 bitmap=config.geticon(32, "dialog-error"),
							 show=False)
			dlg.SetIcons(config.get_icon_bundle([256, 48, 32, 16],
						 appname + "-apply-profiles"))
			dlg.do_not_show_again_cb = wx.CheckBox(dlg, -1, lang.getstr("dialog.do_not_show_again"))
			dlg.do_not_show_again_cb.SetValue(not bool(config.getcfg("profile_loader.error.show_msg")))
			def do_not_show_again_handler(event=None):
				config.setcfg("profile_loader.error.show_msg",
							  int(not dlg.do_not_show_again_cb.GetValue()))
				config.writecfg(module="apply-profiles",
								options=("argyll.dir", "profile.load_on_login",
										 "profile_loader"))
			dlg.do_not_show_again_cb.Bind(wx.EVT_CHECKBOX, do_not_show_again_handler)
			dlg.sizer3.Add(dlg.do_not_show_again_cb, flag=wx.TOP, border=12)
			dlg.sizer0.SetSizeHints(dlg)
			dlg.sizer0.Layout()
			dlg.Center(wx.BOTH)
			dlg.ok.SetDefault()
			dlg.ShowModalThenDestroy()

	def exit(self, event=None):
		safe_print("Executing ProfileLoader.exit(%s)" % event)
		dlg = get_dialog()
		if dlg:
			if (not isinstance(dlg, ProfileLoaderExceptionsDialog) or
				(event and not event.CanVeto())):
				try:
					dlg.EndModal(wx.ID_CANCEL)
				except:
					pass
				else:
					dlg = None
			if dlg and event and event.CanVeto():
				event.Veto()
				safe_print("Vetoed", event)
				dlg.RequestUserAttention()
				return
		if (event and self.frame and
			event.GetEventType() == wx.EVT_MENU.typeId and
			(not calibration_management_isenabled() or
			 config.getcfg("profile_loader.fix_profile_associations"))):
			dlg = ConfirmDialog(None, msg=lang.getstr("profile_loader.exit_warning"), 
								title=self.get_title(),
								ok=lang.getstr("menuitem.quit"), 
								bitmap=config.geticon(32, "dialog-warning"))
			dlg.SetIcons(config.get_icon_bundle([256, 48, 32, 16],
						 appname + "-apply-profiles"))
			result = dlg.ShowModal()
			dlg.Destroy()
			if result != wx.ID_OK:
				safe_print("Cancelled ProfileLoader.exit(%s)" % event)
				return
		self.taskbar_icon and self.taskbar_icon.RemoveIcon()
		self.monitoring = False
		if self.frame:
			self.frame.listening = False
		wx.GetApp().ExitMainLoop()

	def get_title(self):
		title = "%s %s %s" % (appname, lang.getstr("profile_loader").title(),
							  version_short)
		if VERSION > VERSION_BASE:
			title += " Beta"
		if "--force" in sys.argv[1:]:
			title += " (%s)" % lang.getstr("forced")
		return title

	def _can_fix_profile_associations(self):
		if len(self.monitors) > 1:
			return True
		for i, (display, edid,
				moninfo, device0) in enumerate(self.monitors):
			displays = get_display_devices(moninfo["Device"])
			if len(displays) > 1:
				return True
		return False

	def _check_keep_running(self):
		windows = []
		#print '-' * 79
		try:
			win32gui.EnumThreadWindows(self._tid,
									   self._enumerate_own_windows_callback,
									   windows)
		except pywintypes.error, exception:
			pass
		windows.extend(filter(lambda window: not isinstance(window, wx.Dialog) and
											 window.Name != "TaskBarNotification" and
											 window.Name != "DisplayIdentification",
							  wx.GetTopLevelWindows()))
		numwindows = len(windows)
		if numwindows < self.numwindows:
			# One of our windows has been closed by an external event
			# (i.e. WM_CLOSE). This is a hint that something external is trying
			# to get us to exit. Comply by closing our main top-level window to
			# initiate clean shutdown.
			safe_print("Window count", self.numwindows, "->", numwindows)
			return False
		self.numwindows = numwindows
		return True

	def _enumerate_own_windows_callback(self, hwnd, windowlist):
		cls = win32gui.GetClassName(hwnd)
		#print cls
		if (cls in ("madHcNetQueueWindow",
					"wxTLWHiddenParent", "wxTimerHiddenWindow",
					"wxDisplayHiddenWindow") or
			cls.startswith("madToolsMsgHandlerWindow")):
			windowlist.append(cls)

	def _display_changed(self, event):
		safe_print(event)

		with self.lock:
			self._next = True
			self._enumerate_monitors()
			if sys.getwindowsversion() < (6, ):
				# Under XP, we can't use the registry to figure out if the
				# display change was a display configuration change (e.g.
				# display added/removed) or just a resolution change
				self._has_display_changed = True
			if getattr(self, "profile_associations_dlg", None):
				wx.CallLater(1000, lambda: self.profile_associations_dlg and
										   self.profile_associations_dlg.update(True))
			if getattr(self, "fix_profile_associations_dlg", None):
				wx.CallLater(1000, lambda: self.fix_profile_associations_dlg and
										   self.fix_profile_associations_dlg.update(True))

	def _check_display_changed(self, first_run=False, dry_run=False):
		# Check registry if display configuration changed (e.g. if a display
		# was added/removed, and not just the resolution changed)
		try:
			key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, 
								  r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers\Configuration")
		except WindowsError, exception:
			if (exception.errno != errno.ENOENT or
				sys.getwindowsversion() >= (6, )):
				safe_print("Registry access failed:", exception)
			key = None
			numsubkeys = 0
			if not (self.monitors or dry_run):
				self._enumerate_monitors()
		else:
			numsubkeys, numvalues, mtime = _winreg.QueryInfoKey(key)
		has_display_changed = False
		for i in xrange(numsubkeys):
			subkey = _winreg.OpenKey(key, _winreg.EnumKey(key, i))
			display = _winreg.QueryValueEx(subkey, "SetId")[0]
			timestamp = struct.unpack("<Q", _winreg.QueryValueEx(subkey, "Timestamp")[0].rjust(8, '0'))
			if timestamp > self._current_timestamp:
				if display != self._current_display:
					if not (first_run or dry_run):
						safe_print(lang.getstr("display_detected"))
						if debug:
							safe_print(display.replace("\0", ""))
					if not (first_run or dry_run) or not self.monitors:
						self._enumerate_monitors()
						if getcfg("profile_loader.fix_profile_associations"):
							# Work-around long-standing bug in applications
							# querying the monitor profile not making sure
							# to use the active display (this affects Windows
							# itself as well) when only one display is
							# active in a multi-monitor setup.
							if not first_run:
								self._reset_display_profile_associations()
							self._set_display_profiles()
					has_display_changed = True
					if not (first_run or
							dry_run) and self._is_displaycal_running():
						# Normally calibration loading is disabled while
						# DisplayCAL is running. Override this when the
						# display has changed
						self._manual_restore = 2
				if not dry_run:
					self._current_display = display
					self._current_timestamp = timestamp
			_winreg.CloseKey(subkey)
		if key:
			_winreg.CloseKey(key)
		if not dry_run:
			self._has_display_changed = has_display_changed
		return has_display_changed

	def _check_display_conf_wrapper(self):
		try:
			self._check_display_conf()
		except Exception, exception:
			if self.lock.locked():
				self.lock.release()
			wx.CallAfter(self._handle_fatal_error, traceback.format_exc())

	def _handle_fatal_error(self, exception):
		handle_error(exception)
		wx.CallAfter(self.exit)

	def _check_display_conf(self):
		display = None
		self._current_display = None
		self._current_timestamp = 0
		self._next = False
		first_run = True
		apply_profiles = self._should_apply_profiles()
		displaycal_running = self._is_displaycal_running()
		while self and self.monitoring:
			result = None
			results = []
			errors = []
			self.lock.acquire()
			# Check if display configuration changed
			self._check_display_changed(first_run)
			# Check profile associations
			for i, (display, edid, moninfo, device0) in enumerate(self.monitors):
				if device0:
					devicekey = device0.DeviceKey
				else:
					devicekey = None
				key = devicekey or str(i)
				exception = None
				try:
					profile_path = ICCP.get_display_profile(i, path_only=True,
															devicekey=devicekey)
				except IndexError:
					if debug:
						safe_print("Display %s (%s) no longer present?" %
								   (key, display))
					self._next = False
					break
				except Exception, exception:
					if exception.args[0] != errno.ENOENT or debug:
						safe_print("Could not get display profile for display "
								   "%s (%s):" % (key, display), exception)
					profile_path = "?"
				profile = os.path.basename(profile_path)
				profile_name = profile
				if profile_name == "?":
					profile_name = safe_unicode(exception or "?")
				association = self.profile_associations.get(key, (None, 0))
				if (getcfg("profile_loader.fix_profile_associations") and
					not first_run and not self._has_display_changed and
					not self._next and association[0] != profile):
					# At this point we do not yet know if only the profile
					# association has changed or the display configuration.
					# One second delay to allow display configuration
					# to settle
					if not self._check_display_changed(dry_run=True):
						if debug:
							safe_print("Delay 1s")
						timeout = 0
						while (self and self.monitoring and timeout < 1 and
							   self._manual_restore != 2 and not self._next):
							time.sleep(.1)
							timeout += .1
						self._next = True
					break
				if os.path.isfile(profile_path):
					mtime = os.stat(profile_path).st_mtime
				else:
					mtime = 0
				profile_association_changed = False
				if association != (profile, mtime):
					if not first_run:
						safe_print("A profile change has been detected")
						safe_print(display, "->", profile_name)
						device = get_active_display_device(moninfo["Device"])
						if device:
							display_edid = get_display_name_edid(device,
																 moninfo, i)
							if self.monitoring:
								self.devices2profiles[device.DeviceKey] = (display_edid,
																		   profile)
						if debug and device:
							safe_print("Monitor %r active display device name:" %
									   moninfo["Device"], device.DeviceName)
							safe_print("Monitor %r active display device string:" %
									   moninfo["Device"], device.DeviceString)
							safe_print("Monitor %r active display device state flags: 0x%x" %
									   (moninfo["Device"], device.StateFlags))
							safe_print("Monitor %r active display device ID:" %
									   moninfo["Device"], device.DeviceID)
							safe_print("Monitor %r active display device key:" %
									   moninfo["Device"], device.DeviceKey)
						elif debug:
							safe_print("WARNING: Monitor %r has no active display device" %
									   moninfo["Device"])
					self.profile_associations[key] = (profile, mtime)
					self.profiles[key] = None
					self.ramps[key] = (None, None, None)
					profile_association_changed = True
					if not first_run and self._is_displaycal_running():
						# Normally calibration loading is disabled while
						# DisplayCAL is running. Override this when the
						# display has changed
						self._manual_restore = 2
				# Check video card gamma table and (re)load calibration if
				# necessary
				if not self.gdi32:
					continue
				apply_profiles = self._should_apply_profiles()
				recheck = False
				(vcgt_ramp, vcgt_ramp_hack,
				 vcgt_values) = self.ramps.get(self._reset_gamma_ramps or key,
											   (None, None, None))
				if not vcgt_ramp:
					vcgt_values = ([], [], [])
					if not self._reset_gamma_ramps:
						# Get display profile
						if not self.profiles.get(key):
							if profile == "?":
								profile = None
							try:
								self.profiles[key] = ICCP.ICCProfile(profile)
								self.profiles[key].tags.get("vcgt")
							except Exception, exception:
								safe_print(exception)
								continue
						profile = self.profiles[key]
						if isinstance(profile.tags.get("vcgt"),
									  ICCP.VideoCardGammaType):
							# Get display profile vcgt
							vcgt_values = profile.tags.vcgt.get_values()[:3]
					if len(vcgt_values[0]) != 256:
						# Hmm. Do we need to deal with this?
						# I've never seen table-based vcgt with != 256 entries
						if (not self._reset_gamma_ramps and
							(self._manual_restore or
							 profile_association_changed) and
							profile.tags.get("vcgt")):
							safe_print(lang.getstr("calibration.loading_from_display_profile"))
							safe_print(display)
							safe_print(lang.getstr("vcgt.unknown_format",
												   os.path.basename(profile.fileName)))
							safe_print(lang.getstr("failure"))
							results.append(display)
							errors.append(lang.getstr("vcgt.unknown_format",
													  os.path.basename(profile.fileName)))
						# Fall back to linear calibration
						tagData = "vcgt"
						tagData += "\0" * 4  # Reserved
						tagData += "\0\0\0\x01"  # Formula type
						for channel in xrange(3):
							tagData += "\0\x01\0\0"  # Gamma 1.0
							tagData += "\0" * 4  # Min 0.0
							tagData += "\0\x01\0\0"  # Max 1.0
						vcgt = ICCP.VideoCardGammaFormulaType(tagData, "vcgt")
						vcgt_values = vcgt.get_values()[:3]
						if self._reset_gamma_ramps:
							safe_print("Caching linear gamma ramps")
						else:
							safe_print("Caching implicit linear gamma ramps for profile",
									   profile_name)
					else:
						safe_print("Caching gamma ramps for profile",
								   profile_name)
					# Convert vcgt to ushort_Array_256_Array_3
					vcgt_ramp = ((ctypes.c_ushort * 256) * 3)()
					vcgt_ramp_hack = ((ctypes.c_ushort * 256) * 3)()
					for j in xrange(len(vcgt_values[0])):
						for k in xrange(3):
							vcgt_value = vcgt_values[k][j][1]
							vcgt_ramp[k][j] = vcgt_value
							# Some video drivers won't reload gamma ramps if
							# the previously loaded calibration was the same.
							# Work-around by first loading a slightly changed
							# gamma ramp.
							if j == 0:
								vcgt_value += 1
							vcgt_ramp_hack[k][j] = vcgt_value
					self.ramps[self._reset_gamma_ramps or key] = (vcgt_ramp,
																  vcgt_ramp_hack,
																  vcgt_values)
					recheck = True
				if (not self._manual_restore and
					getcfg("profile_loader.check_gamma_ramps")):
					# Get video card gamma ramp
					try:
						hdc = win32gui.CreateDC(moninfo["Device"], None, None)
					except Exception, exception:
						safe_print("Couldn't create DC for", moninfo["Device"],
								   "(%s)" % display)
						continue
					ramp = ((ctypes.c_ushort * 256) * 3)()
					try:
						result = self.gdi32.GetDeviceGammaRamp(hdc, ramp)
					except:
						continue
					finally:
						win32gui.DeleteDC(hdc)
					if not result:
						continue
					# Get ramp values
					values = ([], [], [])
					for j, channel in enumerate(ramp):
						for k, v in enumerate(channel):
							values[j].append([float(k), v])
					# Check if video card matches profile vcgt
					if values == vcgt_values:
						continue
					safe_print(lang.getstr("vcgt.mismatch", display))
					recheck = True
				if recheck:
					# Try and prevent race condition with madVR
					# launching and resetting video card gamma table
					apply_profiles = self._should_apply_profiles()
				if not apply_profiles:
					self._next = False
					break
				# Now actually reload or reset calibration
				if (self._manual_restore or profile_association_changed or
					getcfg("profile_loader.check_gamma_ramps")):
					if self._reset_gamma_ramps:
						safe_print(lang.getstr("calibration.resetting"))
						safe_print(display)
					else:
						safe_print(lang.getstr("calibration.loading_from_display_profile"))
						safe_print(display, "->", profile_name)
				try:
					hdc = win32gui.CreateDC(moninfo["Device"], None, None)
				except Exception, exception:
					safe_print("Couldn't create DC for", moninfo["Device"],
							   "(%s)" % display)
					continue
				try:
					if self._is_buggy_video_driver(moninfo):
						result = self.gdi32.SetDeviceGammaRamp(hdc, vcgt_ramp_hack)
					result = self.gdi32.SetDeviceGammaRamp(hdc, vcgt_ramp)
				except Exception, exception:
					result = exception
				finally:
					win32gui.DeleteDC(hdc)
				self.setgammaramp_success[i] = (result and
												not isinstance(result,
															   Exception))
				if (self._manual_restore or profile_association_changed or
					getcfg("profile_loader.check_gamma_ramps")):
					if isinstance(result, Exception) or not result:
						if result:
							safe_print(result)
						safe_print(lang.getstr("failure"))
					else:
						safe_print(lang.getstr("success"))
				if (self._manual_restore or
					(profile_association_changed and
					 (isinstance(result, Exception) or not result)) or
					getcfg("profile_loader.check_gamma_ramps")):
					if isinstance(result, Exception) or not result:
						errstr = lang.getstr("calibration.load_error")
						errors.append(": ".join([display, errstr]))
					else:
						text = display + u": "
						if self._reset_gamma_ramps:
							text += lang.getstr("linear").capitalize()
						else:
							text += os.path.basename(profile_path)
						results.append(text)
			else:
				# We only arrive here if the loop was completed
				self._next = False
			if self._next:
				# We only arrive here if a change in profile associations was
				# detected and we exited the loop early
				self.lock.release()
				continue
			timestamp = time.time()
			localtime = list(time.localtime(self._timestamp))
			localtime[3:6] = 23, 59, 59
			midnight = time.mktime(localtime) + 1
			if timestamp >= midnight:
				self.reload_count = 0
				self._timestamp = timestamp
			if results or errors:
				if results:
					self.reload_count += 1
					if self._reset_gamma_ramps:
						lstr = "calibration.reset_success"
					else:
						lstr = "calibration.load_success"
					results.insert(0, lang.getstr(lstr))
					if self._app_detection_msg:
						results.insert(0, self._app_detection_msg)
						self._app_detection_msg = None
				self.notify(results, errors,
							show_notification=(not first_run or errors) and
											  self.__other_component[1] != "madHcNetQueueWindow")
			else:
				if (apply_profiles != self.__apply_profiles or
					profile_association_changed):
					if apply_profiles and (not profile_association_changed or
										   not self._reset_gamma_ramps):
						self.reload_count += 1
				if displaycal_running != self._is_displaycal_running():
					if displaycal_running:
						msg = lang.getstr("app.detection_lost.calibration_loading_enabled",
										  appname)
					else:
						msg = lang.getstr("app.detected.calibration_loading_disabled",
										  appname)
					displaycal_running = self._is_displaycal_running()
					safe_print(msg)
					self.notify([msg], [], displaycal_running,
								show_notification=False)
				elif (apply_profiles != self.__apply_profiles or
					  profile_association_changed):
					wx.CallAfter(lambda: self and
										 self.taskbar_icon.set_visual_state())
			self.__apply_profiles = apply_profiles
			first_run = False
			if result:
				self._has_display_changed = False
			self._manual_restore = False
			self.lock.release()
			if "--oneshot" in sys.argv[1:]:
				wx.CallAfter(self.exit)
				break
			# Wait three seconds
			timeout = 0
			while (self and self.monitoring and timeout < 3 and
				   not self._manual_restore	and not self._next):
				if (round(timeout * 100) % 25 == 0 and
					not self._check_keep_running()):
					self.monitoring = False
					wx.CallAfter(lambda: self.frame and self.frame.Close())
					break
				time.sleep(.1)
				timeout += .1
		safe_print("Display configuration monitoring thread finished")

	def shutdown(self):
		safe_print("Shutting down profile loader")
		if self.monitoring:
			safe_print("Shutting down display configuration monitoring thread")
			self.monitoring = False
		if getcfg("profile_loader.fix_profile_associations"):
			self._reset_display_profile_associations()

	def _enumerate_monitors(self):
		safe_print("-" * 80)
		safe_print("Enumerating display adapters and devices:")
		safe_print("")
		self.adapters = dict([(device.DeviceName, device) for device in
							   get_display_devices(None)])
		self.monitors = []
		self.display_devices = OrderedDict()
		for adapter in self.adapters:
			for i, device in enumerate(get_display_devices(adapter)):
				if not i:
					device0 = device
				if self.display_devices.get(device.DeviceKey):
					continue
				display, edid = get_display_name_edid(device)
				self.display_devices[device.DeviceKey] = [display, edid, device,
														  device0]
		for i, moninfo in enumerate(get_real_display_devices_info()):
			# Get monitor descriptive string
			device = get_active_display_device(moninfo["Device"])
			if debug:
				safe_print("Found monitor %i %r flags 0x%x" %
						   (i, moninfo["Device"], moninfo["Flags"]))
				if device:
					safe_print("Monitor %i active display device name:" % i,
							   device.DeviceName)
					safe_print("Monitor %i active display device string:" % i,
							   device.DeviceString)
					safe_print("Monitor %i active display device state flags: "
							   "0x%x" % (i, device.StateFlags))
					safe_print("Monitor %i active display device ID:" % i,
							   device.DeviceID)
					safe_print("Monitor %i active display device key:" % i,
							   device.DeviceKey)
				else:
					safe_print("WARNING: Monitor %i has no active display device" %
							   i)
				safe_print("Monitor %i display name" % i, end=" ")
			moninfo["_adapter"] = self.adapters.get(moninfo["Device"],
													ICCP.ADict({"DeviceString":
																moninfo["Device"][4:]}))
			display, edid = get_display_name_edid(device, moninfo, i)
			if device:
				self.display_devices[device.DeviceKey][0] = display
			if self._is_buggy_video_driver(moninfo):
				safe_print("Buggy video driver detected: %s." %
						   moninfo["_adapter"].DeviceString,
						   "Gamma ramp hack activated.")
			if debug:
				safe_print("Enumerating 1st display device for monitor %i %r" %
						   (i, moninfo["Device"]))
			try:
				device0 = win32api.EnumDisplayDevices(moninfo["Device"], 0)
			except pywintypes.error, exception:
				safe_print("EnumDisplayDevices(%r, 0) failed:" %
						   moninfo["Device"], exception)
				device0 = None
			if debug and device0:
				safe_print("Monitor %i 1st display device name:" % i,
						   device0.DeviceName)
				safe_print("Monitor %i 1st display device string:" % i,
						   device0.DeviceString)
				safe_print("Monitor %i 1st display device state flags: 0x%x" %
						   (i, device0.StateFlags))
				safe_print("Monitor %i 1st display device ID:" % i,
						   device0.DeviceID)
				safe_print("Monitor %i 1st display device key:" % i,
						   device0.DeviceKey)
			self.monitors.append((display, edid, moninfo, device0))
		for display, edid, device, device0 in self.display_devices.itervalues():
			if device.DeviceKey == device0.DeviceKey:
				device_name = "\\".join(device.DeviceName.split("\\")[:-1])
				safe_print(self.adapters.get(device_name,
											 ICCP.ADict({"DeviceString":
														 device_name[4:]})).DeviceString)
			display_parts = display.split("@", 1)
			if len(display_parts) > 1:
				info = display_parts[1].split(" - ", 1)
				display_parts[1] = "@" + " ".join(info[:1])
			safe_print("  |-", "".join(display_parts))
		safe_print("-" * 80)

	def _enumerate_windows_callback(self, hwnd, extra):
		cls = win32gui.GetClassName(hwnd)
		if cls == "madHcNetQueueWindow" or self._is_known_window_class(cls):
			try:
				thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
				filename = get_process_filename(pid)
			except pywintypes.error:
				return
			basename = os.path.basename(filename)
			if (basename.lower() != "madhcctrl.exe" and
				filename.lower() != exe.lower()):
				self.__other_component = filename, cls, 0

	def _is_known_window_class(self, cls):
		for partial in self._known_window_classes:
			if partial in cls:
				return True

	def _is_buggy_video_driver(self, moninfo):
		# Intel video drivers won't reload gamma ramps if the
		# previously loaded calibration was the same.
		# Work-around by first loading a slightly changed
		# gamma ramp.
		adapter = moninfo["_adapter"].DeviceString.lower()
		for buggy_video_driver in self._buggy_video_drivers:
			if buggy_video_driver in adapter:
				return True
		return False

	def _is_displaycal_running(self):
		displaycal_lockfile = os.path.join(confighome, appbasename + ".lock")
		return os.path.isfile(displaycal_lockfile)

	def _is_other_running(self, enumerate_windows_and_processes=True):
		"""
		Determine if other software that may be using the videoLUT is in use 
		(e.g. madVR video playback, madTPG, other calibration software)
		
		"""
		if sys.platform != "win32":
			return
		if len(self._madvr_instances):
			return True
		if enumerate_windows_and_processes:
			# At launch, we won't be able to determine if madVR is running via
			# the callback API, and we can only determine if another
			# calibration solution is running by enumerating windows and
			# processes anyway.
			other_component = self.__other_component
			self.__other_component = None, None, 0
			# Look for known window classes
			# Performance on C2D 3.16 GHz (Win7 x64, ~ 90 processes): ~ 1ms
			try:
				win32gui.EnumWindows(self._enumerate_windows_callback, None)
			except pywintypes.error, exception:
				safe_print("Enumerating windows failed:", exception)
			if not self.__other_component[1]:
				# Look for known processes
				# Performance on C2D 3.16 GHz (Win7 x64, ~ 90 processes):
				# ~ 6-9ms (1ms to get PIDs)
				try:
					pids = get_pids()
				except WindowsError, exception:
					safe_print("Enumerating processes failed:", exception)
				else:
					for pid in pids:
						try:
							filename = get_process_filename(pid)
						except (WindowsError, pywintypes.error), exception:
							if exception.args[0] not in (winerror.ERROR_ACCESS_DENIED,
														 winerror.ERROR_PARTIAL_COPY,
														 winerror.ERROR_INVALID_PARAMETER,
														 winerror.ERROR_GEN_FAILURE):
								safe_print("Couldn't get filename of "
										   "process %s:" % pid, exception)
							continue
						basename = os.path.basename(filename)
						known_app = basename.lower() in self._known_apps
						enabled, reset, path = self._exceptions.get(filename.lower(),
																	(0, 0, ""))
						if known_app or enabled:
							if known_app or not reset:
								self.__other_component = filename, None, 0
								break
							elif other_component != (filename, None, reset):
								self._reset_gamma_ramps = True
							self.__other_component = filename, None, reset
			if other_component != self.__other_component:
				if other_component[2] and not self.__other_component[2]:
					self._reset_gamma_ramps = bool(config.getcfg("profile_loader.reset_gamma_ramps"))
				check = ((not other_component[2] and
						  not self.__other_component[2]) or
						 (other_component[2] and
						  self.__other_component[0:2] != (None, None) and
						  not self.__other_component[2]))
				if check:
					if self.__other_component[0:2] == (None, None):
						lstr = "app.detection_lost.calibration_loading_enabled"
						component = other_component
						sticky = False
					else:
						lstr = "app.detected.calibration_loading_disabled"
						component = self.__other_component
						sticky = True
				else:
					if self.__other_component[0:2] != (None, None):
						lstr = "app.detected"
						component = self.__other_component
					else:
						lstr = "app.detection_lost"
						component = other_component
				if component[1] == "madHcNetQueueWindow":
					component_name = "madVR"
				elif component[0]:
					component_name = os.path.basename(component[0])
					try:
						info = get_file_info(component[0])["StringFileInfo"].values()
					except:
						info = None
					if info:
						component_name = info[0].get("ProductName",
													 info[0].get("FileDescription",
																 component_name))
				else:
					component_name = lang.getstr("unknown")
				if self.__other_component[0:2] != (None, None):
					self._component_name = component_name
				else:
					self._component_name = None
				msg = lang.getstr(lstr, component_name)
				safe_print(msg)
				if check:
					self.notify([msg], [], sticky,
								show_notification=component_name != "madVR")
				else:
					self._app_detection_msg = msg
					self._manual_restore = 2
		return (self.__other_component[0:2] != (None, None) and
				not self.__other_component[2])

	def _madvr_connection_callback(self, param, connection, ip, pid, module,
								   component, instance, is_new_instance):
		with self.lock:
			if ip in ("127.0.0.1", "localhost", "::1", "0:0:0:0:0:0:0:1"):
				args = (param, connection, ip, pid, module, component, instance)
				try:
					filename = get_process_filename(pid)
				except:
					filename = lang.getstr("unknown")
				if is_new_instance:
					apply_profiles = self._should_apply_profiles(manual_override=None)
					self._madvr_instances.append(args)
					self.__other_component = filename, "madHcNetQueueWindow", 0
					safe_print("madVR instance connected:", "PID", pid, filename)
					if apply_profiles:
						msg = lang.getstr("app.detected.calibration_loading_disabled",
										  component)
						safe_print(msg)
						self.notify([msg], [], True, show_notification=False)
				elif args in self._madvr_instances:
					self._madvr_instances.remove(args)
					safe_print("madVR instance disconnected:", "PID", pid, filename)
					if self._should_apply_profiles(manual_override=None):
						msg = lang.getstr("app.detection_lost.calibration_loading_enabled",
										  component)
						safe_print(msg)
						self.notify([msg], [], show_notification=False)

	def _reset_display_profile_associations(self):
		for devicekey, (display_edid,
						profile) in self.devices2profiles.iteritems():
			if profile and profile != "?":
				try:
					current_profile = ICCP.get_display_profile(path_only=True,
															   devicekey=devicekey)
				except Exception, exception:
					safe_print("Could not get display profile for display "
							   "device %r:" % devicekey, exception)
					continue
				if not current_profile:
					continue
				current_profile = os.path.basename(current_profile)
				if current_profile and current_profile != profile:
					safe_print("Resetting profile association for %s:" %
							   display_edid[0], current_profile, "->", profile)
					try:
						ICCP.set_display_profile(profile, devicekey=devicekey)
					except WindowsError, exception:
						safe_print(exception)

	def _set_display_profiles(self, dry_run=False):
		if debug:
			safe_print("-" * 80)
			safe_print("Checking profile associations")
			safe_print("-" * 80)
		self.devices2profiles = {}
		for i, (display, edid, moninfo, device0) in enumerate(self.monitors):
			if debug:
				safe_print("Enumerating display devices for monitor %i %r" %
						   (i, moninfo["Device"]))
			devices = get_display_devices(moninfo["Device"])
			if not devices:
				if debug:
					safe_print("WARNING: Monitor %i has no display devices" % i)
				continue
			active_device = get_active_display_device(None, devices=devices)
			if debug:
				if active_device:
					safe_print("Monitor %i active display device name:" % i,
							   active_device.DeviceName)
					safe_print("Monitor %i active display device string:" % i,
							   active_device.DeviceString)
					safe_print("Monitor %i active display device state flags: "
							   "0x%x" % (i, active_device.StateFlags))
					safe_print("Monitor %i active display device ID:" % i,
							   active_device.DeviceID)
					safe_print("Monitor %i active display device key:" % i,
							   active_device.DeviceKey)
				else:
					safe_print("WARNING: Monitor %i has no active display device" %
							   i)
			for device in devices:
				try:
					profile = ICCP.get_display_profile(path_only=True,
													   devicekey=device.DeviceKey)
				except Exception, exception:
					safe_print("Could not get display profile for display "
							   "device %r:" % device.DeviceKey, exception)
					profile = None
				if profile:
					profile = os.path.basename(profile)
				if active_device and device.DeviceID == active_device.DeviceID:
					active_moninfo = moninfo
				else:
					active_moninfo = None
				display_edid = get_display_name_edid(device, active_moninfo, i)
				self.devices2profiles[device.DeviceKey] = (display_edid,
														   profile or "")
				if debug:
					safe_print("%s (%s) -> %s" % (display_edid[0],
												  device.DeviceKey,
												  profile or "none"))
			# Set the active profile
			device = active_device
			if not device:
				continue
			try:
				correct_profile = ICCP.get_display_profile(path_only=True,
														   devicekey=device.DeviceKey)
			except Exception, exception:
				safe_print("Could not get display profile for display "
						   "device %r:" % device.DeviceKey, exception)
				continue
			if correct_profile:
				correct_profile = os.path.basename(correct_profile)
			device = devices[0]
			current_profile = self.devices2profiles[device.DeviceKey][1]
			if (correct_profile and current_profile != correct_profile and
				not dry_run):
				safe_print("Fixing profile association for %s:" % display,
						   current_profile, "->", correct_profile)
				try:
					ICCP.set_display_profile(os.path.basename(correct_profile),
											 devicekey=device.DeviceKey)
				except WindowsError, exception:
					safe_print(exception)

	def _set_manual_restore(self, event):
		if event:
			safe_print("Menu command:", end=" ")
		safe_print("Set calibration state to load profile vcgt")
		with self.lock:
			setcfg("profile_loader.reset_gamma_ramps", 0)
			self._manual_restore = True
			self._reset_gamma_ramps = False
		self.taskbar_icon.set_visual_state()
		self.writecfg()

	def _set_reset_gamma_ramps(self, event):
		if event:
			safe_print("Menu command:", end=" ")
		safe_print("Set calibration state to reset vcgt")
		with self.lock:
			setcfg("profile_loader.reset_gamma_ramps", 1)
			self._manual_restore = True
			self._reset_gamma_ramps = True
		self.taskbar_icon.set_visual_state()
		self.writecfg()

	def _should_apply_profiles(self, enumerate_windows_and_processes=True,
							   manual_override=2):
		return (("--force" in sys.argv[1:] or
				 self._manual_restore or
				 (config.getcfg("profile.load_on_login") and
				  (sys.platform != "win32" or
				   not calibration_management_isenabled()))) and
				(not self._is_displaycal_running() or
				 self._manual_restore == manual_override) and
				not self._is_other_running(enumerate_windows_and_processes))

	def _toggle_fix_profile_associations(self, event, alt=True):
		if event:
			safe_print("Menu command:", end=" ")
		safe_print("Toggle fix profile associations", event.IsChecked())
		if event.IsChecked():
			dlg = FixProfileAssociationsDialog(self)
			self.fix_profile_associations_dlg = dlg
			result = dlg.ShowModal()
			dlg.Destroy()
			if result == wx.ID_CANCEL:
				safe_print("Cancelled toggling fix profile associations")
				return
			elif result != wx.ID_OK:
				self._set_profile_associations(None)
				return
		with self.lock:
			setcfg("profile_loader.fix_profile_associations",
				   int(event.IsChecked()))
			if event.IsChecked():
				self._set_display_profiles()
			else:
				self._reset_display_profile_associations()
			self._manual_restore = True
			self.writecfg()

	def _set_exceptions(self):
		self._exceptions = {}
		exceptions = config.getcfg("profile_loader.exceptions").strip()
		if exceptions:
			safe_print("Exceptions:")
		for exception in exceptions.split(";"):
			exception = exception.split(":", 2)
			if len(exception) < 3:
				# Malformed, ignore
				continue
			for i in xrange(2):
				try:
					exception[i] = int(exception[i])
				except:
					exception[i] = 0
			enabled, reset, path = exception
			self._exceptions[path.lower()] = (enabled, reset, path)
			safe_print("Enabled=%s" % bool(enabled),
					   "Action=%s" % (reset and "Reset" or "Disable"), path)

	def _set_profile_associations(self, event):
		if event:
			safe_print("Menu command:", end=" ")
		safe_print("Set profile associations")
		dlg = ProfileAssociationsDialog(self)
		self.profile_associations_dlg = dlg
		dlg.Center()
		dlg.ShowModalThenDestroy()

	def writecfg(self):
		config.writecfg(module="apply-profiles",
						options=("profile.load_on_login", "profile_loader"))


def get_display_name_edid(device, moninfo=None, index=None,
						  include_adapter=False):
	edid = {}
	if device:
		display = safe_unicode(device.DeviceString)
		try:
			edid = get_edid(device=device)
		except Exception, exception:
			pass
	else:
		display = lang.getstr("unknown")
	display = edid.get("monitor_name", display)
	if moninfo:
		m_left, m_top, m_right, m_bottom = moninfo["Monitor"]
		m_width = m_right - m_left
		m_height = m_bottom - m_top
		display = " @ ".join([display, 
							  "%i, %i, %ix%i" %
							  (m_left, m_top, m_width,
							   m_height)])
		if moninfo["Flags"] & MONITORINFOF_PRIMARY:
			display += " " + lang.getstr("display.primary")
		if moninfo.get("_adapter") and include_adapter:
			display += u" - %s" % moninfo["_adapter"].DeviceString
	if index is not None:
		display = "%i. %s" % (index + 1, display)
	return display, edid

def main():
	unknown_option = None
	for arg in sys.argv[1:]:
		if (arg not in ("--help", "--force", "-V", "--version") and
			(arg not in ("--oneshot", "--debug", "-d") or
			 sys.platform != "win32") and
			(arg not in ("--verify", "--silent", "--error-dialog", "--skip") or
			 sys.platform == "win32")):
			unknown_option = arg
			break

	if "--help" in sys.argv[1:] or unknown_option:

		if unknown_option:
			safe_print("%s: unrecognized option `%s'" %
					   (os.path.basename(sys.argv[0]), unknown_option))
			if sys.platform == "win32":
				from wxwindows import BaseApp
				BaseApp._run_exitfuncs()
		safe_print("Usage: %s [OPTION]..." % os.path.basename(sys.argv[0]))
		safe_print("Apply profiles to configured display devices and load calibration")
		safe_print("Version %s" % version)
		safe_print("")
		safe_print("  --help           Output this help text and exit")
		safe_print("  --force          Force loading of calibration/profile (if it has been")
		safe_print("                   disabled in %s.ini)" % appname)
		if sys.platform == "win32":
			safe_print("  --oneshot        Exit after loading calibration")
		else:
			safe_print("  --verify         Verify if calibration was loaded correctly")
			safe_print("  --silent         Do not show dialog box on error")
			safe_print("  --skip           Skip initial loading of calibration")
			safe_print("  --error-dialog   Force dialog box on error")
		safe_print("  -V, --version    Output version information and exit")
	elif "-V" in sys.argv[1:] or "--version" in sys.argv[1:]:
		safe_print("%s %s" % (os.path.basename(sys.argv[0]), version))
	else:
		config.initcfg("apply-profiles")

		if (not "--force" in sys.argv[1:] and
			not config.getcfg("profile.load_on_login") and
			sys.platform != "win32"):
			# Early exit incase profile loading has been disabled and isn't forced
			sys.exit()

		if "--error-dialog" in sys.argv[1:]:
			config.setcfg("profile_loader.error.show_msg", 1)
			config.writecfg(module="apply-profiles",
							options=("argyll.dir", "profile.load_on_login",
									 "profile_loader"))

		import localization as lang
		lang.init()

		ProfileLoader()


if __name__ == "__main__":
	main()
