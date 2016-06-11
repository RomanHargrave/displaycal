# -*- coding: utf-8 -*-

""" 
Set ICC profiles and load calibration curves for all configured display devices

"""

import errno
import os
import sys
import threading
import time

from meta import VERSION, VERSION_BASE, name as appname, version, version_short


class ProfileLoader(object):

	def __init__(self):
		import config
		from config import appbasename
		from wxwindows import BaseApp, wx
		if not wx.GetApp():
			app = BaseApp(0)
		else:
			app = None
		self.reload_count = 0
		self.lock = threading.Lock()
		self.monitoring = True
		self.monitors = []
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
		self._madvr_instances = []
		self._timestamp = time.time()
		self.__other_component = None, None
		self.__other_isrunning = False
		self.__apply_profiles = None
		if (sys.platform == "win32" and not "--force" in sys.argv[1:] and
			sys.getwindowsversion() >= (6, 1)):
			from util_win import calibration_management_isenabled
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
			import ctypes
			import subprocess as sp
			import localization as lang
			import madvr
			from log import safe_print
			from util_str import safe_unicode
			from util_win import (calibration_management_isenabled,
								  get_display_devices)
			from wxfixes import set_bitmap_labels
			from wxwindows import BaseFrame, TaskBarNotification

			class PLFrame(BaseFrame):

				def __init__(self, pl):
					BaseFrame.__init__(self, None)
					self.pl = pl
					self.Bind(wx.EVT_CLOSE, pl.exit)
					self.Bind(wx.EVT_DISPLAY_CHANGED, self.pl._display_changed)

				def get_commands(self):
					return self.get_common_commands() + ["apply-profiles [force]",
														 "notify <message> [silent] [sticky]",
														 "setlanguage <languagecode>"]

				def process_data(self, data):
					if data[0] == "apply-profiles" and (len(data) == 1 or
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
					self._active_icon_reset = config.get_bitmap_as_icon(16, appname + "-apply-profiles-reset")
					self._error_icon = config.get_bitmap_as_icon(16, appname + "-apply-profiles-error")
					self.set_visual_state(True)
					self.Bind(wx.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)

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

					fix = len(self.pl.monitors) > 1
					for i, (display, edid,
							moninfo, device0) in enumerate(self.pl.monitors):
						displays = get_display_devices(moninfo["Device"])
						if len(displays) > 1:
							fix = True
							break
					if fix:
						fix = self.pl._toggle_fix_profile_associations

					menu_items = [("calibration.load_from_display_profiles",
								   restore_manual, apply_kind,
								   "profile_loader.reset_gamma_ramps",
								   lambda v: not v),
								  ("calibration.reset",
								   reset, apply_kind,
								   "profile_loader.reset_gamma_ramps", None),
								  ("-", None, False, None, None),
								  ("calibration.preserve",
								   restore_auto, restore_auto_kind,
								   "profile.load_on_login", None),
								  ("profile_loader.fix_profile_associations",
								   fix,
								   wx.ITEM_CHECK,
								   "profile_loader.fix_profile_associations",
								   None),
								  ("-", None, False, None, None)]
					if sys.getwindowsversion() >= (6, ):
						menu_items.extend([("mswin.open_color_management_settings",
											self.open_color_management_settings,
											wx.ITEM_NORMAL, None, None),
										   ("mswin.open_display_settings",
											self.open_display_settings,
											wx.ITEM_NORMAL, None, None),
										   ("-", None, False, None, None)])
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
									item.Check(oxform(config.getcfg(option)))

					return menu

				def get_icon(self, enumerate_windows_and_processes=False):
					if (self.pl._should_apply_profiles(enumerate_windows_and_processes,
													   manual_override=None) and
						("--force" in sys.argv[1:] or
						 config.getcfg("profile.load_on_login"))):
						count = len(self.pl.monitors)
						if (len(filter(lambda (i, success): success,
									   sorted(self.pl.setgammaramp_success.items())[:count])) != count or
							len(filter(lambda (i, profile): profile and
															profile.fileName,
									   sorted(self.pl.profiles.items())[:count])) != count):
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

				def open_color_management_settings(self, event):
					try:
						sp.call(["control", "/name", "Microsoft.ColorManagement"],
								close_fds=True)
					except:
						wx.Bell()

				def open_display_settings(self, event):
					try:
						sp.call(["control", "/name", "Microsoft.Display",
								 "/page", "Settings"], close_fds=True)
					except:
						wx.Bell()

				def set_auto_restore(self, event):
					config.setcfg("profile.load_on_login",
								  int(event.IsChecked()))
					if event.IsChecked():
						with self.pl.lock:
							self.pl._next = event.IsChecked()
					else:
						self.set_visual_state()

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
						text += lang.getstr("profile_loader.info",
											self.pl.reload_count)
						for i, (display, edid,
								moninfo, device0) in enumerate(self.pl.monitors):
							(profile,
							 mtime) = self.pl.profile_associations.get(i,
																	   (False,
																		None))
							if profile is False:
								profile = "?"
							if not self.pl.setgammaramp_success.get(i):
								profile = (lang.getstr("unknown") +
										   u" (%s)" % profile)
							elif self.pl._reset_gamma_ramps:
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
		import config
		import localization as lang
		from log import safe_print
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

		self.profile_associations = {}
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
				self.profile_associations[i] = (os.path.basename(profile_arg),
												mtime)
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
		from wxwindows import wx
		wx.CallAfter(lambda: self and self._notify(results, errors, sticky,
												   show_notification))

	def _notify(self, results, errors, sticky=False, show_notification=False):
		from wxwindows import wx
		self.taskbar_icon.set_visual_state()
		results.extend(errors)
		if errors:
			flags = wx.ICON_ERROR
		else:
			flags = wx.ICON_INFORMATION
		self.taskbar_icon.show_notification("\n".join(results), sticky,
											show_notification, flags)

	def apply_profiles_and_warn_on_error(self, event=None, index=None):
		errors = self.apply_profiles(event, index)
		import config
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
		from log import safe_print
		from util_win import calibration_management_isenabled
		from wxwindows import wx
		import config
		safe_print("Executing ProfileLoader.exit(%s)" % event)
		if (event and self.frame and
			event.GetEventType() == wx.EVT_MENU.typeId and
			(not calibration_management_isenabled() or
			 config.getcfg("profile_loader.fix_profile_associations"))):
			import localization as lang
			from wxwindows import ConfirmDialog
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
		config.writecfg(module="apply-profiles",
						options=("argyll.dir", "profile.load_on_login",
								 "profile_loader"))
		self.taskbar_icon and self.taskbar_icon.RemoveIcon()
		self.monitoring = False
		if self.frame:
			self.frame.listening = False
		wx.GetApp().ExitMainLoop()

	def get_title(self):
		import localization as lang
		title = "%s %s %s" % (appname, lang.getstr("profile_loader").title(),
							  version_short)
		if VERSION > VERSION_BASE:
			title += " Beta"
		if "--force" in sys.argv[1:]:
			title += " (%s)" % lang.getstr("forced")
		return title

	def _check_keep_running(self):
		from wxwindows import wx
		windows = []
		import win32gui
		#print '-' * 79
		try:
			win32gui.EnumThreadWindows(self._tid,
									   self._enumerate_own_windows_callback,
									   windows)
		except pywintypes.error, exception:
			pass
		windows.extend(filter(lambda window: not isinstance(window, wx.Dialog) and
											 window.Name != "TaskBarNotification",
							  wx.GetTopLevelWindows()))
		numwindows = len(windows)
		if numwindows < self.numwindows:
			# One of our windows has been closed by an external event
			# (i.e. WM_CLOSE). This is a hint that something external is trying
			# to get us to exit. Comply by closing our main top-level window to
			# initiate clean shutdown.
			from log import safe_print
			safe_print("Window count", self.numwindows, "->", numwindows)
			return False
		self.numwindows = numwindows
		return True

	def _enumerate_own_windows_callback(self, hwnd, windowlist):
		import win32gui
		cls = win32gui.GetClassName(hwnd)
		#print cls
		if (cls in ("madHcNetQueueWindow",
					"wxTLWHiddenParent", "wxTimerHiddenWindow",
					"wxDisplayHiddenWindow") or
			cls.startswith("madToolsMsgHandlerWindow")):
			windowlist.append(cls)

	def _display_changed(self, event):
		from log import safe_print

		safe_print(event)

		with self.lock:
			self._next = True
			if sys.getwindowsversion() < (6, ):
				# Under XP, we can't use the registry to figure out if the
				# display change was a display configuration change (e.g.
				# display added/removed) or just a resolution change
				self._enumerate_monitors()
				self._has_display_changed = True

	def _check_display_changed(self, first_run=False, dry_run=False):
		# Check registry if display configuration changed (e.g. if a display
		# was added/removed, and not just the resolution changed)
		import struct
		import _winreg

		from config import getcfg
		import localization as lang
		from log import safe_print

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
					if not (first_run or dry_run) or not self.monitors:
						self._enumerate_monitors()
						for (display, edid, moninfo, device0) in self.monitors:
							safe_print(display)
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
			from wxwindows import wx
			wx.CallAfter(self._handle_fatal_error, exception)

	def _handle_fatal_error(self, exception):
		from debughelpers import handle_error
		handle_error(exception)
		from wxwindows import wx
		wx.CallAfter(self.exit)

	def _check_display_conf(self):
		import ctypes

		import win32api
		import win32gui

		from config import getcfg
		import ICCProfile as ICCP
		from wxwindows import wx
		import localization as lang
		from log import safe_print
		from util_win import get_active_display_device

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
				try:
					profile_path = ICCP.get_display_profile(i, path_only=True,
															devicekey=devicekey)
				except IndexError:
					self._next = False
					break
				except Exception, exception:
					if exception.args[0] != errno.ENOENT:
						safe_print("Could not get display profile for display %i:" %
								   i, exception)
						continue
					else:
						profile_path = "?"
				if not profile_path:
					continue
				profile = os.path.basename(profile_path)
				association = self.profile_associations.get(i, (None, 0))
				if (not first_run and not self._has_display_changed and
					not self._next and association[0] != profile):
					# At this point we do not yet know if only the profile
					# association has changed or the display configuration.
					# One second delay to allow display configuration
					# to settle
					if not self._check_display_changed(dry_run=True):
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
						safe_print(display, "->", profile)
						device = get_active_display_device(moninfo["Device"])
						if device:
							display_edid = get_display_name_edid(device,
																 moninfo)
							self.devices2profiles[device.DeviceKey] = (display_edid,
																	   profile)
					self.profile_associations[i] = (profile, mtime)
					self.profiles[i] = None
					self.ramps[i] = (None, None)
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
				(vcgt_ramp,
				 vcgt_values) = self.ramps.get(self._reset_gamma_ramps or i,
											   (None, None))
				if not vcgt_ramp:
					vcgt_values = ([], [], [])
					if not self._reset_gamma_ramps:
						# Get display profile
						if not self.profiles.get(i):
							if profile == "?":
								profile = None
							try:
								self.profiles[i] = ICCP.ICCProfile(profile)
								self.profiles[i].tags.get("vcgt")
							except Exception, exception:
								safe_print(exception)
								continue
						profile = self.profiles[i]
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
									   os.path.basename(profile_path))
					else:
						safe_print("Caching gamma ramps for profile",
								   os.path.basename(profile_path))
					# Convert vcgt to ushort_Array_256_Array_3
					vcgt_ramp = ((ctypes.c_ushort * 256) * 3)()
					for j in xrange(len(vcgt_values[0])):
						for k in xrange(3):
							vcgt_ramp[k][j] = vcgt_values[k][j][1]
					self.ramps[self._reset_gamma_ramps or i] = (vcgt_ramp,
																vcgt_values)
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
						safe_print(display, "->", os.path.basename(profile_path))
				try:
					hdc = win32gui.CreateDC(moninfo["Device"], None, None)
				except Exception, exception:
					safe_print("Couldn't create DC for", moninfo["Device"],
							   "(%s)" % display)
					continue
				try:
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
				self.notify(results, errors,
							show_notification=(not first_run or errors) and
											  self.__other_component[1] != "madHcNetQueueWindow")
				if result:
					self.__other_component = None, None
			else:
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
					self.__apply_profiles = apply_profiles
					wx.CallAfter(lambda: self and
										 self.taskbar_icon.set_visual_state())
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
		if getcfg("profile_loader.fix_profile_associations"):
			self._reset_display_profile_associations()
		safe_print("Display configuration monitoring thread finished")

	def _enumerate_monitors(self):
		import pywintypes
		import win32api
		from util_win import (get_active_display_device,
							  get_real_display_devices_info)
		self.monitors = []
		for i, moninfo in enumerate(get_real_display_devices_info()):
			# Get monitor descriptive string
			device = get_active_display_device(moninfo["Device"])
			display, edid = get_display_name_edid(device, moninfo)
			try:
				device0 = win32api.EnumDisplayDevices(moninfo["Device"], 0)
			except pywintypes.error:
				device0 = None
			self.monitors.append((display, edid, moninfo, device0))

	def _enumerate_windows_callback(self, hwnd, extra):
		import win32gui
		cls = win32gui.GetClassName(hwnd)
		if cls == "madHcNetQueueWindow" or self._is_known_window_class(cls):
			import pywintypes
			import win32process
			from util_win import get_process_filename
			try:
				thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
				filename = get_process_filename(pid)
			except pywintypes.error:
				return
			from config import exe
			basename = os.path.basename(filename)
			if (basename.lower() != "madhcctrl.exe" and
				filename.lower() != exe.lower()):
				self.__other_isrunning = True
				self.__other_component = filename, cls

	def _is_known_window_class(self, cls):
		for partial in self._known_window_classes:
			if partial in cls:
				return True

	def _is_displaycal_running(self):
		from config import appbasename, confighome
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
			self.__other_isrunning = True
			return True
		if enumerate_windows_and_processes:
			# At launch, we won't be able to determine if madVR is running via
			# the callback API, and we can only determine if another
			# calibration solution is running by enumerating windows and
			# processes anyway.
			import pywintypes
			import win32gui
			import winerror
			from log import safe_print
			from util_win import get_process_filename, get_pids
			other_isrunning = self.__other_isrunning
			self.__other_isrunning = False
			# Look for known window classes
			# Performance on C2D 3.16 GHz (Win7 x64, ~ 90 processes): ~ 1ms
			try:
				win32gui.EnumWindows(self._enumerate_windows_callback, None)
			except pywintypes.error, exception:
				safe_print("Enumerating windows failed:", exception)
			if not self.__other_isrunning:
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
						if basename.lower() in self._known_apps:
							self.__other_isrunning = True
							self.__other_component = filename, None
							break
			if other_isrunning != self.__other_isrunning:
				import localization as lang
				from util_win import get_file_info
				if other_isrunning:
					lstr = "app.detection_lost.calibration_loading_enabled"
				else:
					lstr = "app.detected.calibration_loading_disabled"
				if self.__other_component[1] == "madHcNetQueueWindow":
					component = "madVR"
				else:
					component = os.path.basename(self.__other_component[0])
					try:
						info = get_file_info(self.__other_component[0])["StringFileInfo"].values()
					except:
						info = None
					if info:
						component = info[0].get("ProductName",
												info[0].get("FileDescription",
															component))
				msg = lang.getstr(lstr, component)
				safe_print(msg)
				self.notify([msg], [], not other_isrunning,
							show_notification=component != "madVR")
		return self.__other_isrunning

	def _madvr_connection_callback(self, param, connection, ip, pid, module,
								   component, instance, is_new_instance):
		with self.lock:
			import localization as lang
			from log import safe_print
			from util_win import get_process_filename
			if ip in ("127.0.0.1", "localhost", "::1", "0:0:0:0:0:0:0:1"):
				args = (param, connection, ip, pid, module, component, instance)
				try:
					filename = get_process_filename(pid)
				except:
					filename = lang.getstr("unknown")
				if is_new_instance:
					apply_profiles = self._should_apply_profiles(manual_override=None)
					self._madvr_instances.append(args)
					self.__other_component = filename, "madHcNetQueueWindow"
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
		import ICCProfile as ICCP
		from log import safe_print
		for devicekey, (display_edid,
						profile) in self.devices2profiles.iteritems():
			if profile:
				try:
					current_profile = ICCP.get_display_profile(path_only=True,
															   devicekey=devicekey)
				except Exception, exception:
					if exception.args[0] != errno.ENOENT:
						safe_print(exception)
					continue
				if not current_profile:
					continue
				current_profile = os.path.basename(current_profile)
				if current_profile and current_profile != profile:
					safe_print("Resetting profile association for %s:" %
							   display_edid[0], current_profile, "->", profile)
					ICCP.set_display_profile(profile, devicekey=devicekey)

	def _set_display_profiles(self, dry_run=False):
		import win32api

		import ICCProfile as ICCP
		from log import safe_print
		from util_win import get_active_display_device, get_display_devices
		self.devices2profiles = {}
		for i, (display, edid, moninfo, device0) in enumerate(self.monitors):
			devices = get_display_devices(moninfo["Device"])
			if not devices:
				continue
			active_device = get_active_display_device(None, devices=devices)
			for device in devices:
				try:
					profile = ICCP.get_display_profile(path_only=True,
													   devicekey=device.DeviceKey)
				except Exception, exception:
					if exception.args[0] != errno.ENOENT:
						safe_print(exception)
					profile = None
				if profile:
					profile = os.path.basename(profile)
				if active_device and device.DeviceID == active_device.DeviceID:
					active_moninfo = moninfo
				else:
					active_moninfo = None
				display_edid = get_display_name_edid(device, active_moninfo)
				self.devices2profiles[device.DeviceKey] = (display_edid,
														   profile or "")
			# Set the active profile
			device = active_device
			if not device:
				continue
			try:
				correct_profile = ICCP.get_display_profile(path_only=True,
														   devicekey=device.DeviceKey)
			except Exception, exception:
				if exception.args[0] != errno.ENOENT:
					safe_print(exception)
				continue
			if correct_profile:
				correct_profile = os.path.basename(correct_profile)
			device = devices[0]
			current_profile = self.devices2profiles[device.DeviceKey][1]
			if (correct_profile and current_profile != correct_profile and
				not dry_run):
				safe_print("Fixing profile association for %s:" % display,
						   current_profile, "->", correct_profile)
				ICCP.set_display_profile(os.path.basename(correct_profile),
										 devicekey=device.DeviceKey)

	def _set_manual_restore(self, event):
		from config import setcfg
		with self.lock:
			setcfg("profile_loader.reset_gamma_ramps", 0)
			self._manual_restore = True
			self._reset_gamma_ramps = False
		self.taskbar_icon.set_visual_state()

	def _set_reset_gamma_ramps(self, event):
		from config import setcfg
		with self.lock:
			setcfg("profile_loader.reset_gamma_ramps", 1)
			self._manual_restore = True
			self._reset_gamma_ramps = True
		self.taskbar_icon.set_visual_state()

	def _should_apply_profiles(self, enumerate_windows_and_processes=True,
							   manual_override=2):
		import config
		if sys.platform == "win32":
			from util_win import calibration_management_isenabled
		return (("--force" in sys.argv[1:] or
				 self._manual_restore or
				 (config.getcfg("profile.load_on_login") and
				  (sys.platform != "win32" or
				   not calibration_management_isenabled()))) and
				(not self._is_displaycal_running() or
				 self._manual_restore == manual_override) and
				not self._is_other_running(enumerate_windows_and_processes))

	def _toggle_fix_profile_associations(self, event):
		from config import (get_default_dpi, get_icon_bundle, getcfg, geticon,
							setcfg)
		if event.IsChecked():
			import ICCProfile as ICCP
			import localization as lang
			from colord import device_id_from_edid
			from wxwindows import ConfirmDialog, wx
			self._set_display_profiles(dry_run=True)
			dlg = ConfirmDialog(None,
								msg=lang.getstr("profile_loader.fix_profile_associations_warning"), 
								title=self.get_title(),
								ok=lang.getstr("profile_loader.fix_profile_associations"), 
								bitmap=geticon(32, "dialog-warning"), wrap=128)
			dlg.SetIcons(get_icon_bundle([256, 48, 32, 16],
						 appname + "-apply-profiles"))
			numdisp = len(self.devices2profiles)
			scale = getcfg("app.dpi") / get_default_dpi()
			if scale < 1:
				scale = 1
			list_panel = wx.Panel(dlg, -1)
			list_panel.BackgroundColour = wx.SystemSettings.GetColour(wx.SYS_COLOUR_3DLIGHT)
			list_panel.Sizer = wx.BoxSizer(wx.HORIZONTAL)
			hscroll = wx.SystemSettings_GetMetric(wx.SYS_HSCROLL_Y)
			list_ctrl = wx.ListCtrl(list_panel, -1,
									size=(640 * scale,
										  (20 * numdisp + 25 + hscroll) * scale),
									style=wx.LC_REPORT | wx.LC_SINGLE_SEL |
										  wx.BORDER_THEME,
									name="displays2profiles")
			list_panel.Sizer.Add(list_ctrl, 1, flag=wx.ALL, border=1)
			list_ctrl.InsertColumn(0, lang.getstr("display"))
			list_ctrl.InsertColumn(1, lang.getstr("profile"))
			list_ctrl.SetColumnWidth(0, int(200 * scale))
			list_ctrl.SetColumnWidth(1, int(420 * scale))
			for i, (display_edid,
					profile) in enumerate(self.devices2profiles.itervalues()):
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
			# Ignore item focus/selection
			list_ctrl.Bind(wx.EVT_LIST_ITEM_FOCUSED,
						   lambda e: list_ctrl.SetItemState(e.GetIndex(), 0,
															wx.LIST_STATE_FOCUSED))
			list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED,
						   lambda e: list_ctrl.SetItemState(e.GetIndex(), 0,
															wx.LIST_STATE_SELECTED))
			dlg.sizer3.Insert(0, list_panel, 1, flag=wx.BOTTOM | wx.ALIGN_LEFT,
							  border=12)
			dlg.sizer0.SetSizeHints(dlg)
			dlg.sizer0.Layout()
			result = dlg.ShowModal()
			dlg.Destroy()
			if result != wx.ID_OK:
				return
		with self.lock:
			setcfg("profile_loader.fix_profile_associations",
				   int(event.IsChecked()))
			if event.IsChecked():
				self._set_display_profiles()
			else:
				self._reset_display_profile_associations()
			self._manual_restore = True


def get_display_name_edid(device, moninfo=None):
	import localization as lang
	from edid import get_edid
	from util_str import safe_unicode
	if device:
		display = safe_unicode(device.DeviceString)
	else:
		display = lang.getstr("unknown")
	try:
		edid = get_edid(device=device)
	except Exception, exception:
		edid = {}
	display = edid.get("monitor_name", display)
	if moninfo:
		m_left, m_top, m_right, m_bottom = moninfo["Monitor"]
		m_width = m_right - m_left
		m_height = m_bottom - m_top
		display = " @ ".join([display, 
							  "%i, %i, %ix%i" %
							  (m_left, m_top, m_width,
							   m_height)])
	return display, edid

def main():
	import config
	from log import safe_print

	unknown_option = None
	for arg in sys.argv[1:]:
		if (arg not in ("--help", "--force", "-V", "--version") and
			(arg != "--oneshot" or sys.platform != "win32") and
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
