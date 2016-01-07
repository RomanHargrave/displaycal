#!/usr/bin/env python2
# -*- coding: utf-8 -*-

""" 
Set ICC profiles and load calibration curves for all configured display devices

"""

import os
import sys
import threading
import time

from meta import name as appname, version


class ProfileLoader(object):

	def __init__(self):
		import config
		from worker import Worker
		from wxwindows import wx
		if not wx.GetApp():
			app = wx.App(0)
		else:
			app = None
		self.worker = Worker()
		self.reload_count = 0
		self.lock = threading.Lock()
		apply_profiles = ("--force" in sys.argv[1:] or
						  config.getcfg("profile.load_on_login"))
		if (sys.platform == "win32" and not "--force" in sys.argv[1:] and
			sys.getwindowsversion() >= (6, 1)):
			from util_win import calibration_management_isenabled
			if calibration_management_isenabled():
				# Incase calibration loading is handled by Windows 7 and
				# isn't forced
				apply_profiles = False
		if apply_profiles and not "--skip" in sys.argv[1:]:
			self.apply_profiles_and_warn_on_error()
		if sys.platform == "win32":
			# We create a TSR tray program only under Windows.
			# Linux has colord/Oyranos and respective session daemons should
			# take care of calibration loading
			import localization as lang
			from config import appbasename
			from util_win import calibration_management_isenabled
			from wxwindows import BaseFrame

			class PLFrame(BaseFrame):

				def __init__(self, pl):
					BaseFrame.__init__(self, None)
					self.pl = pl
					self.Bind(wx.EVT_CLOSE, pl.exit)

				def get_commands(self):
					return self.get_common_commands() + ["apply-profiles"]

				def process_data(self, data):
					if data[0] == "apply-profiles" and len(data) == 1:
						if (not "--force" in sys.argv[1:] and
							calibration_management_isenabled()):
							return lang.getstr("calibration.load.handled_by_os")
						if os.path.isfile(os.path.join(config.confighome,
													   appbasename + ".lock")):
							return "forbidden"
						else:
							self.pl.apply_profiles(True)
						return self.pl.errors or "ok"
					return "invalid"

			self.frame = PLFrame(self)

			class TaskBarIcon(wx.TaskBarIcon):

				def __init__(self, pl):
					super(TaskBarIcon, self).__init__()
					self.pl = pl
					self.SetIcon(config.get_bitmap_as_icon(16, appname +
															   "-apply-profiles"),
								 self.pl.get_title())
					self.Bind(wx.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)

				def CreatePopupMenu(self):
					# Popup menu appears on right-click
					menu = wx.Menu()
					
					if os.path.isfile(os.path.join(config.confighome,
												   appbasename + ".lock")):
						method = None
					else:
						method = self.pl.apply_profiles_and_warn_on_error
					for label, method in (("calibration.reload_from_display_profiles",
										   method),
										  ("-", None),
										  ("menuitem.quit", self.pl.exit)):
						if label == "-":
							menu.AppendSeparator()
						else:
							item = wx.MenuItem(menu, -1, lang.getstr(label))
							if method is None:
								item.Enable(False)
							else:
								menu.Bind(wx.EVT_MENU, method, id=item.Id)
							menu.AppendItem(item)

					return menu

				def on_left_down(self, event):
					self.show_balloon()

				def show_balloon(self, text=None):
					if wx.VERSION < (3, ):
						return
					if not text:
						if (not "--force" in sys.argv[1:] and
							calibration_management_isenabled()):
							text = lang.getstr("calibration.load.handled_by_os") + "\n"
						else:
							text = ""
						text += lang.getstr("calibration.reload.info",
											self.pl.reload_count)
					self.ShowBalloon(self.pl.get_title(), text, 100)

			self.taskbar_icon = TaskBarIcon(self)

			self.frame.listen()

			self._check_display_conf_thread = threading.Thread(target=self._check_display_conf)
			self._check_display_conf_thread.start()

			if app:
				app.MainLoop()

	def apply_profiles(self, event=None, index=None):
		import config
		import localization as lang
		from log import safe_print
		from util_os import which
		from worker import Worker, get_argyll_util
		from wxwindows import wx

		if sys.platform == "win32":
			self.lock.acquire()

		worker = self.worker

		errors = self.errors = []

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
				self.profile_associations[i] = os.path.basename(profile_arg)
				if (sys.platform == "win32" or not oyranos_monitor or
					not display_conf_oy_compat or not xcalib or profile_arg == "-L"):
					# Only need to run dispwin if under Windows, or if nothing else
					# has already taken care of display profile and vcgt loading
					# (e.g. oyranos-monitor with xcalib, or colord)
					if worker.exec_cmd(dispwin, ["-v", "-d%i" % (i + 1), "-c", 
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
				if results:
					self.reload_count += 1
					results.insert(0, lang.getstr("calibration.load_success"))
				results.extend(errors)
				wx.CallAfter(lambda text: self and
										  self.taskbar_icon.show_balloon(text),
							 "\n".join(results))

		return errors

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
				config.writecfg()
			dlg.do_not_show_again_cb.Bind(wx.EVT_CHECKBOX, do_not_show_again_handler)
			dlg.sizer3.Add(dlg.do_not_show_again_cb, flag=wx.TOP, border=12)
			dlg.sizer0.SetSizeHints(dlg)
			dlg.sizer0.Layout()
			dlg.Center(wx.BOTH)
			dlg.ok.SetDefault()
			dlg.ShowModalThenDestroy()

	def exit(self, event=None):
		from util_win import calibration_management_isenabled
		from wxwindows import ConfirmDialog, wx
		if (self.frame and event.GetEventType() == wx.EVT_MENU.typeId and
			not calibration_management_isenabled()):
			import config
			import localization as lang
			from wxwindows import ConfirmDialog, wx
			dlg = ConfirmDialog(None, msg=lang.getstr("profile_loader.exit_warning"), 
								title=self.get_title(),
								ok=lang.getstr("menuitem.quit"), 
								bitmap=config.geticon(32, "dialog-warning"))
			dlg.SetIcons(config.get_icon_bundle([256, 48, 32, 16],
						 appname + "-apply-profiles"))
			result = dlg.ShowModal()
			dlg.Destroy()
			if result != wx.ID_OK:
				return
		self.frame and self.frame.Destroy()
		self.taskbar_icon and self.taskbar_icon.Destroy()

	def get_title(self):
		import localization as lang
		title = "%s %s %s" % (appname, lang.getstr("profile_loader").title(),
							  version)
		if "--force" in sys.argv[1:]:
			title += " (%s)" % lang.getstr("forced")
		return title

	def _check_display_conf(self):
		import struct
		import _winreg

		import config
		import ICCProfile as ICCP
		from wxwindows import wx
		import localization as lang
		from log import safe_print
		from util_win import calibration_management_isenabled

		display = None
		current_display = None
		current_timestamp = 0
		displays_enumerated = self.worker.displays
		first_run = True
		self.profile_associations = {}
		while wx.GetApp():
			apply_profiles = ("--force" in sys.argv[1:] or
							  (config.getcfg("profile.load_on_login") and
							   not calibration_management_isenabled()))
			if not apply_profiles:
				self.profile_associations = {}
			# Check if display configuration changed
			key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, 
								  r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers\Configuration")
			numsubkeys, numvalues, mtime = _winreg.QueryInfoKey(key)
			for i in xrange(numsubkeys):
				subkey = _winreg.OpenKey(key, _winreg.EnumKey(key, i))
				display = _winreg.QueryValueEx(subkey, "SetId")[0]
				timestamp = struct.unpack("<Q", _winreg.QueryValueEx(subkey, "Timestamp")[0].rjust(8, '0'))
				if timestamp > current_timestamp:
					if display != current_display:
						if not first_run and apply_profiles:
							safe_print(lang.getstr("display_detected"))
							# One second delay to allow display configuration
							# to settle
							time.sleep(1)
							self.apply_profiles(True)
							apply_profiles = False
						if not first_run or not displays_enumerated:
							self.worker.enumerate_displays_and_ports(silent=True, check_lut_access=False,
																	 enumerate_ports=False,
																	 include_network_devices=False)
							displays_enumerated = True
					current_display = display
					current_timestamp = timestamp
				_winreg.CloseKey(subkey)
			_winreg.CloseKey(key)
			# Check profile associations
			self.lock.acquire()
			for i, display in enumerate(self.worker.displays):
				if config.is_virtual_display(i):
					continue
				try:
					profile = ICCP.get_display_profile(i, path_only=True)
				except IndexError:
					break
				if self.profile_associations.get(i) != profile and apply_profiles:
					if not first_run:
						safe_print(lang.getstr("display_detected"))
						self.lock.release()
						self.apply_profiles(True, index=i)
						self.lock.acquire()
					self.profile_associations[i] = profile
			self.lock.release()
			first_run = False
			# Wait three seconds
			timeout = 0
			while wx.GetApp():
				time.sleep(.1)
				timeout += .1
				if timeout > 2.9:
					break


def main():
	unknown_option = None
	for arg in sys.argv[1:]:
		if arg not in ("--help", "--force", "--verify", "--silent",
					   "--error-dialog", "-V", "--version", "--skip"):
			unknown_option = arg
			break

	if "--help" in sys.argv[1:] or unknown_option:
		if unknown_option:
			print "%s: unrecognized option `%s'" % (os.path.basename(sys.argv[0]),
											 unknown_option)
		print "Usage: %s [OPTION]..." % os.path.basename(sys.argv[0])
		print "Apply profiles to configured display devices and load calibration"
		print "Version %s" % version
		print ""
		print "  --help           Output this help text and exit"
		print "  --force          Force loading of calibration/profile (if it has been"
		print "                   disabled in %s.ini)" % appname
		print "  --verify         Verify if calibration was loaded correctly"
		print "  --silent         Do not show dialog box on error"
		print "  --skip           Skip initial loading of calibration"
		print "  --error-dialog   Force dialog box on error"
		print "  -V, --version    Output version information and exit"
	elif "-V" in sys.argv[1:] or "--version" in sys.argv[1:]:
		print "%s %s" % (os.path.basename(sys.argv[0]), version)
	else:
		import config

		config.initcfg("apply-profiles")

		if (not "--force" in sys.argv[1:] and
			not config.getcfg("profile.load_on_login") and
			sys.platform != "win32"):
			# Early exit incase profile loading has been disabled and isn't forced
			sys.exit()

		if "--error-dialog" in sys.argv[1:]:
			config.setcfg("profile_loader.error.show_msg", 1)
			config.writecfg()

		import localization as lang
		lang.init()

		ProfileLoader()


if __name__ == "__main__":
	main()
