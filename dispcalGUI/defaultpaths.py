# -*- coding: utf-8 -*-

import os
import sys

if sys.platform == "win32":
	try:
		from win32com.shell.shell import SHGetSpecialFolderPath
		from win32com.shell.shellcon import (CSIDL_APPDATA, 
											 CSIDL_COMMON_APPDATA, 
											 CSIDL_COMMON_STARTUP, 
											 CSIDL_LOCAL_APPDATA,
											 CSIDL_PROFILE,
											 CSIDL_PROGRAM_FILES_COMMON, 
											 CSIDL_STARTUP, CSIDL_SYSTEM)
	except ImportError:
		import ctypes
		(CSIDL_APPDATA, CSIDL_COMMON_APPDATA, CSIDL_COMMON_STARTUP, 
		 CSIDL_LOCAL_APPDATA, CSIDL_PROFILE, CSIDL_PROGRAM_FILES_COMMON,
		 CSIDL_STARTUP, CSIDL_SYSTEM) = (26, 35, 24, 28, 40, 43, 7, 37)
		MAX_PATH = 260
		def SHGetSpecialFolderPath(hwndOwner, nFolder, create=0):
			""" ctypes wrapper around shell32.SHGetSpecialFolderPathW """
			buffer = ctypes.create_unicode_buffer(u'\0' * MAX_PATH)
			ctypes.windll.shell32.SHGetSpecialFolderPathW(0, buffer, nFolder, 
														  create)
			return buffer.value

from util_os import expanduseru, expandvarsu, getenvu

home = expanduseru("~")
if sys.platform == "win32":
	# Always specify create=1 for SHGetSpecialFolderPath so we don't get an
	# exception if the folder does not yet exist
	try:
		library_home = appdata = SHGetSpecialFolderPath(0, CSIDL_APPDATA, 1)
	except Exception, exception:
		raise Exception("FATAL - Could not get/create user application data folder: %s"
						% exception)
	try:
		localappdata = SHGetSpecialFolderPath(0, CSIDL_LOCAL_APPDATA, 1)
	except Exception, exception:
		localappdata = os.path.join(appdata, "Local")
	cache = localappdata
	# Argyll CMS uses ALLUSERSPROFILE for local system wide app related data
	# Note: On Windows Vista and later, ALLUSERSPROFILE and COMMON_APPDATA
	# are actually the same ('C:\ProgramData'), but under Windows XP the former
	# points to 'C:\Documents and Settings\All Users' while COMMON_APPDATA
	# points to 'C:\Documents and Settings\All Users\Application Data'
	allusersprofile = getenvu("ALLUSERSPROFILE")
	if allusersprofile:
		commonappdata = [allusersprofile]
	else:
		try:
			commonappdata = [SHGetSpecialFolderPath(0, CSIDL_COMMON_APPDATA, 1)]
		except Exception, exception:
			raise Exception("FATAL - Could not get/create common application data folder: %s"
							% exception)
	library = commonappdata[0]
	try:
		commonprogramfiles = SHGetSpecialFolderPath(0, CSIDL_PROGRAM_FILES_COMMON, 1)
	except Exception, exception:
		raise Exception("FATAL - Could not get/create common program files folder: %s"
						% exception)
	try:
		autostart = SHGetSpecialFolderPath(0, CSIDL_COMMON_STARTUP, 1)
	except Exception, exception:
		autostart = None
	try:
		autostart_home = SHGetSpecialFolderPath(0, CSIDL_STARTUP, 1)
	except Exception, exception:
		autostart_home = None
	try:
		iccprofiles = [os.path.join(SHGetSpecialFolderPath(0, CSIDL_SYSTEM), 
									"spool", "drivers", "color")]
	except Exception, exception:
		raise Exception("FATAL - Could not get system folder: %s"
						% exception)
	iccprofiles_home = iccprofiles
elif sys.platform == "darwin":
	library_home = os.path.join(home, "Library")
	cache = os.path.join(library_home, "Caches")
	library = os.path.join(os.path.sep, "Library")
	prefs = os.path.join(os.path.sep, "Library", "Preferences")
	prefs_home = os.path.join(home, "Library", "Preferences")
	appdata = os.path.join(home, "Library", "Application Support")
	commonappdata = [os.path.join(os.path.sep, "Library", "Application Support")]
	autostart = autostart_home = None
	iccprofiles = [os.path.join(os.path.sep, "Library", "ColorSync", 
								"Profiles"),
				   os.path.join(os.path.sep, "System", "Library", "ColorSync", 
								"Profiles")]
	iccprofiles_home = [os.path.join(home, "Library", "ColorSync", 
									 "Profiles")]
else:
	cache = xdg_cache_home = getenvu("XDG_CACHE_HOME",
									 expandvarsu("$HOME/.cache"))
	xdg_config_home = getenvu("XDG_CONFIG_HOME", expandvarsu("$HOME/.config"))
	xdg_config_dir_default = "/etc/xdg"
	xdg_config_dirs = [os.path.normpath(pth) for pth in 
					   getenvu("XDG_CONFIG_DIRS", 
							   xdg_config_dir_default).split(os.pathsep)]
	if not xdg_config_dir_default in xdg_config_dirs:
		xdg_config_dirs.append(xdg_config_dir_default)
	xdg_data_home_default = expandvarsu("$HOME/.local/share")
	library_home = appdata = xdg_data_home = getenvu("XDG_DATA_HOME", xdg_data_home_default)
	xdg_data_dirs_default = "/usr/local/share:/usr/share:/var/lib"
	xdg_data_dirs = [os.path.normpath(pth) for pth in 
					 getenvu("XDG_DATA_DIRS", 
							 xdg_data_dirs_default).split(os.pathsep)]
	for dir_ in xdg_data_dirs_default.split(os.pathsep):
		if not dir_ in xdg_data_dirs:
			xdg_data_dirs.append(dir_)
	commonappdata = xdg_data_dirs
	library = commonappdata[0]
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
			iccprofiles.append(os.path.join(dir_, "color", "icc"))
	iccprofiles.append("/var/lib/color")
	iccprofiles_home = [os.path.join(xdg_data_home, "color", "icc"), 
						os.path.join(xdg_data_home, "icc"), 
						expandvarsu("$HOME/.color/icc")]
if sys.platform in ("darwin", "win32"):
	iccprofiles_display = iccprofiles
	iccprofiles_display_home = iccprofiles_home
else:
	iccprofiles_display = [os.path.join(dir_, "devices", "display") 
						   for dir_ in iccprofiles]
	iccprofiles_display_home = [os.path.join(dir_, "devices", "display") 
								for dir_ in iccprofiles_home]
	del dir_
