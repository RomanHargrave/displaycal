# -*- coding: utf-8 -*-

import platform
import re
import sys

from util_x import get_display as _get_x_display

if sys.platform == "darwin":
	# Mac OS X has universal binaries in two flavors:
	# - i386 & PPC
	# - i386 & x86_64
	if platform.architecture()[0].startswith('64'):
		from lib64.RealDisplaySizeMM import *
	else:
		from lib32.RealDisplaySizeMM import *
else:
	# Linux and Windows have separate files
	if platform.architecture()[0].startswith('64'):
		if sys.version_info[:2] == (2, 6):
			from lib64.python26.RealDisplaySizeMM import *
		elif sys.version_info[:2] == (2, 7):
			from lib64.python27.RealDisplaySizeMM import *
	else:
		if sys.version_info[:2] == (2, 6):
			from lib32.python26.RealDisplaySizeMM import *
		elif sys.version_info[:2] == (2, 7):
			from lib32.python27.RealDisplaySizeMM import *

_displays = None

_GetXRandROutputXID = GetXRandROutputXID
_RealDisplaySizeMM = RealDisplaySizeMM
_enumerate_displays = enumerate_displays


def GetXRandROutputXID(display_no=0):
	display = get_display(display_no)
	if display:
		return display.get("output", 0)
	return 0


def RealDisplaySizeMM(display_no=0):
	display = get_display(display_no)
	if display:
		return display.get("size_mm", (0, 0))
	return (0, 0)


def enumerate_displays():
	global _displays
	_displays = _enumerate_displays()
	for display in _displays:
		desc = display.get("description")
		if desc:
			match = re.findall("(.+?),? at (-?\d+), (-?\d+), "
							   "width (\d+), height (\d+)", 
							   desc)
			if len(match):
				if sys.platform not in ("darwin", "win32"):
					xrandr_name = re.search(", Output (.+)", match[0][0])
					if xrandr_name:
						display["xrandr_name"] = xrandr_name.group(1)
				desc = "%s @ %s, %s, %sx%s" % match[0]
				display["description"] = desc
	return _displays


def get_display(display_no=0):
	if _displays is None:
		enumerate_displays()
	# Translate from Argyll display index to enumerated display index
	# using the coordinates and dimensions
	from config import getcfg, is_virtual_display
	if is_virtual_display(display_no):
		return
	try:
		argyll_display = getcfg("displays")[display_no]
	except IndexError:
		return
	else:
		if argyll_display.endswith(" [PRIMARY]"):
			argyll_display = " ".join(argyll_display.split(" ")[:-1])
		for display in _displays:
			desc = display.get("description")
			if desc:
				geometry = "".join(desc.split("@ ")[-1:])
				if argyll_display.endswith("@ " + geometry):
					return display


def get_x_display(display_no=0):
	display = get_display(display_no)
	if display:
		name = display.get("name")
		if name:
			return _get_x_display(name)


def get_x_icc_profile_atom_id(display_no=0):
	display = get_display(display_no)
	if display:
		return display.get("icc_profile_atom_id")


def get_x_icc_profile_output_atom_id(display_no=0):
	display = get_display(display_no)
	if display:
		return display.get("icc_profile_output_atom_id")
