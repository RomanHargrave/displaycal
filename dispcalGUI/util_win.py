#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys

import pywintypes
import win32api

# http://msdn.microsoft.com/en-us/library/dd183569%28v=vs.85%29.aspx
DISPLAY_DEVICE_ACTIVE = 0x1  # DISPLAY_DEVICE_ACTIVE specifies whether a monitor is presented as being "on" by the respective GDI view.
							 # Windows Vista: EnumDisplayDevices will only enumerate monitors that can be presented as being "on."
DISPLAY_DEVICE_MIRRORING_DRIVER = 0x8  # Represents a pseudo device used to mirror application drawing for remoting or other purposes. 
									   # An invisible pseudo monitor is associated with this device. 
									   # For example, NetMeeting uses it. Note that GetSystemMetrics (SM_MONITORS) only accounts for visible display monitors.
DISPLAY_DEVICE_MODESPRUNED = 0x8000000  # The device has more display modes than its output devices support.
DISPLAY_DEVICE_PRIMARY_DEVICE = 0x4  # The primary desktop is on the device. 
									 # For a system with a single display card, this is always set. 
									 # For a system with multiple display cards, only one device can have this set.
DISPLAY_DEVICE_REMOVABLE = 0x20  # The device is removable; it cannot be the primary display.
DISPLAY_DEVICE_VGA_COMPATIBLE = 0x10  # The device is VGA compatible.
DISPLAY_DEVICE_DISCONNECT = 0x2000000
DISPLAY_DEVICE_MULTI_DRIVER = 0x2
DISPLAY_DEVICE_REMOTE = 0x4000000


def get_real_display_devices_info():
	""" Return info for real (non-virtual) devices """
	# See Argyll source spectro/dispwin.c MonitorEnumProc, get_displays
	monitors = []
	for monitor in win32api.EnumDisplayMonitors(None, None):
		try:
			moninfo = win32api.GetMonitorInfo(monitor[0])
		except pywintypes.error:
			pass
		else:
			if moninfo and not moninfo["Device"].startswith("\\\\.\\DISPLAYV"):
				monitors.append(moninfo)
	return monitors


def get_active_display_device(devicename):
	"""
	Get active display device of an output (there can only be one per output)
	
	Return value: display device object or None
	
	Example usage:
	get_active_display_device('\\\\.\\DISPLAY1', 0)
	devicename = '\\\\.\\DISPLAYn' where n is a positive integer starting at 1
	
	"""
	devices = []
	n = 0
	while True:
		try:
			devices.append(win32api.EnumDisplayDevices(devicename, n))
		except pywintypes.error:
			break
		n += 1
	for device in devices:
		if (device.StateFlags & DISPLAY_DEVICE_ACTIVE 
			and (len(devices) == 1 or device.StateFlags & 
									  DISPLAY_DEVICE_MULTI_DRIVER)):
			return device
