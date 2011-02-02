#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

if sys.platform == "win32":
	try:
		from win32com.shell.shell import SHGetSpecialFolderPath
		from win32com.shell.shellcon import (CSIDL_APPDATA, 
											 CSIDL_COMMON_APPDATA, 
											 CSIDL_COMMON_STARTUP, 
											 CSIDL_PROFILE,
											 CSIDL_PROGRAM_FILES_COMMON, 
											 CSIDL_STARTUP, CSIDL_SYSTEM)
	except ImportError:
		(CSIDL_APPDATA, CSIDL_COMMON_APPDATA, CSIDL_COMMON_STARTUP, 
		 CSIDL_PROFILE, CSIDL_PROGRAM_FILES_COMMON, CSIDL_STARTUP, 
		 CSIDL_SYSTEM) = (26, 35, 24, 40, 43, 7, 37)
		def SHGetSpecialFolderPath(hwndOwner, nFolder):
			return {
				CSIDL_APPDATA: getenvu("APPDATA"),
				CSIDL_COMMON_APPDATA: getenvu("ALLUSERSPROFILE"),
				CSIDL_COMMON_STARTUP: None,
				CSIDL_PROFILE: getenvu("USERPROFILE"),
				CSIDL_PROGRAM_FILES_COMMON: getenvu("CommonProgramFiles"),
				CSIDL_STARTUP: None,
				CSIDL_SYSTEM: getenvu("SystemRoot")
			}.get(nFolder)

from util_os import expanduseru, expandvarsu, getenvu

home = expanduseru("~")
if sys.platform == "win32":
	appdata = SHGetSpecialFolderPath(0, CSIDL_APPDATA)
	commonappdata = SHGetSpecialFolderPath(0, CSIDL_COMMON_APPDATA)
	commonprogramfiles = SHGetSpecialFolderPath(0, CSIDL_PROGRAM_FILES_COMMON)
	try:
		autostart = SHGetSpecialFolderPath(0, CSIDL_COMMON_STARTUP)
		# Can fail under Vista and later if directory doesn't exist
	except Exception, exception:
		autostart = None
	try:
		autostart_home = SHGetSpecialFolderPath(0, CSIDL_STARTUP)
		# Can fail under Vista and later if directory doesn't exist
	except Exception, exception:
		autostart_home = None
	iccprofiles = [os.path.join(SHGetSpecialFolderPath(0, CSIDL_SYSTEM), 
								"spool", "drivers", "color")]
	iccprofiles_home = iccprofiles
elif sys.platform == "darwin":
	appdata = os.path.join(home, "Library")
	commonappdata = os.path.join(os.path.sep, "Library")
	prefs = os.path.join(os.path.sep, "Library", "Preferences")
	prefs_home = os.path.join(home, "Library", "Preferences")
	appsupport = os.path.join(os.path.sep, "Library", "Application Support")
	appsupport_home = os.path.join(home, "Library", "Application Support")
	autostart = autostart_home = None
	iccprofiles = [os.path.join(os.path.sep, "Library", "ColorSync", 
								"Profiles"),
				   os.path.join(os.path.sep, "System", "Library", "ColorSync", 
								"Profiles")]
	iccprofiles_home = [os.path.join(home, "Library", "ColorSync", 
									 "Profiles")]
else:
	xdg_config_home = getenvu("XDG_CONFIG_HOME", expandvarsu("$HOME/.config"))
	xdg_config_dir_default = "/etc/xdg"
	xdg_config_dirs = [os.path.normpath(pth) for pth in 
					   getenvu("XDG_CONFIG_DIRS", 
							   xdg_config_dir_default).split(os.pathsep)]
	if not xdg_config_dir_default in xdg_config_dirs:
		xdg_config_dirs += [xdg_config_dir_default]
	xdg_data_home_default = expandvarsu("$HOME/.local/share")
	appdata = xdg_data_home = getenvu("XDG_DATA_HOME", xdg_data_home_default)
	xdg_data_dirs_default = "/usr/local/share:/usr/share:/var/lib"
	xdg_data_dirs = [os.path.normpath(pth) for pth in 
					 getenvu("XDG_DATA_DIRS", 
							 xdg_data_dirs_default).split(os.pathsep)]
	for dir_ in xdg_data_dirs_default.split(os.pathsep):
		if not dir_ in xdg_data_dirs:
			xdg_data_dirs += [dir_]
	commonappdata = xdg_data_dirs[0]
	autostart = None
	for dir_ in xdg_config_dirs:
		if os.path.exists(dir_):
			autostart = os.path.join(dir_, "autostart")
			break
	if not autostart:
		autostart = os.path.join(xdg_config_dir_default, "autostart")
	autostart_home = os.path.join(xdg_config_home, "autostart")
	iccprofiles = []
	for dir_ in xdg_data_dirs:
		if os.path.exists(dir_):
			iccprofiles += [os.path.join(dir_, "color", "icc")]
	iccprofiles.append("/var/lib/color")
	iccprofiles_home = [os.path.join(xdg_data_home, "color", "icc"), 
						expandvarsu("$HOME/.color/icc")]
if sys.platform in ("darwin", "win32"):
	iccprofiles_display = iccprofiles
	iccprofiles_display = iccprofiles_home
else:
	iccprofiles_display = [os.path.join(dir_, "devices", "display") 
						   for dir_ in iccprofiles]
	iccprofiles_display_home = [os.path.join(dir_, "devices", "display") 
								for dir_ in iccprofiles_home]
	del dir_
