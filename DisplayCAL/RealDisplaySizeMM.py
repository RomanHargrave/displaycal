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
	if _displays is None:
		enumerate_displays()
	if len(_displays) > display_no:
		return _displays[display_no].get("output", 0)
	return 0


def RealDisplaySizeMM(display_no=0):
	if _displays is None:
		enumerate_displays()
	if len(_displays) > display_no:
		return _displays[display_no].get("size_mm", (0, 0))
	return (0, 0)


def enumerate_displays():
	global _displays
	_displays = _enumerate_displays()
	if sys.platform not in ("darwin", "win32"):
		for display in _displays:
			desc = display.get("description")
			if desc:
				# Extract XRandR name
				xrandr_name = re.search(", Output (.+) at -?\d+, -?\d+, "
										"width \d+, height \d+$", desc)
				if xrandr_name:
					display["xrandr_name"] = xrandr_name.group(1)
	return _displays


def get_display(display_no=0):
	if _displays is None:
		enumerate_displays()
	if len(_displays) > display_no:
		return _displays[display_no]


def get_x_display(display_no=0):
	if _displays is None:
		enumerate_displays()
	if len(_displays) > display_no:
		name = _displays[display_no].get("name")
		if name:
			return _get_x_display(name)


def get_x_icc_profile_atom_id(display_no=0):
	if _displays is None:
		enumerate_displays()
	if len(_displays) > display_no:
		return _displays[display_no].get("icc_profile_atom_id")


def get_x_icc_profile_output_atom_id(display_no=0):
	if _displays is None:
		enumerate_displays()
	if len(_displays) > display_no:
		return _displays[display_no].get("icc_profile_output_atom_id")
