# -*- coding: utf-8 -*-

import ctypes
import _winreg
import struct
import sys

import pywintypes
import win32api
import winerror

if not hasattr(ctypes, "c_bool"):
	# Python 2.5
	ctypes.c_bool = ctypes.c_int

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

# Icm.h
CLASS_MONITOR = struct.unpack("!L", "mntr")[0]
CLASS_PRINTER = struct.unpack("!L", "prtr")[0]
CLASS_SCANNER = struct.unpack("!L", "scnr")[0]


def _get_icm_display_device_key(device):
	monkey = device.DeviceKey.split("\\")[-2:]  # pun totally intended
	subkey = "\\".join(["Software", "Microsoft", "Windows NT", 
						"CurrentVersion", "ICM", "ProfileAssociations", 
						"Display"] + monkey)
	return _winreg.CreateKey(_winreg.HKEY_CURRENT_USER, subkey)


def _get_mscms_dll_handle():
	try:
		return ctypes.windll.mscms
	except WindowsError:
		return None


def calibration_management_isenabled():
	""" Check if calibration is enabled under Windows 7 """
	if sys.getwindowsversion() < (6, 1):
		# Windows XP and Vista don't have calibration management
		return False
	if False:
		# Using registry - NEVER
		# Also, does not work!
		key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE,
							  r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ICM\Calibration")
		return bool(_winreg.QueryValueEx(key, "CalibrationManagementEnabled")[0])
	else:
		# Using ctypes
		mscms = _get_mscms_dll_handle()
		pbool = ctypes.pointer(ctypes.c_bool())
		if not mscms or not mscms.WcsGetCalibrationManagementState(pbool):
			return
		return bool(pbool.contents)


def disable_calibration_management():
	""" Disable calibration loading under Windows 7 """
	enable_calibration_management(False)


def disable_per_user_profiles(display_no=0):
	""" Disable per user profiles under Vista/Windows 7 """
	enable_per_user_profiles(False, display_no)


def enable_calibration_management(enable=True):
	""" Enable calibration loading under Windows 7 """
	if sys.getwindowsversion() < (6, 1):
		raise NotImplementedError("Calibration Management is only available "
								  "in Windows 7 or later")
	if False:
		# Using registry - NEVER
		# Also, does not work!
		key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE,
							  r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\ICM\Calibration",
							  _winreg.KEY_SET_VALUE)
		_winreg.SetValueEx(key, "CalibrationManagementEnabled", 0,
						   _winreg.REG_DWORD, int(enable))
	else:
		# Using ctypes (must be called with elevated permissions)
		mscms = _get_mscms_dll_handle()
		if not mscms:
			return False
		if not mscms.WcsSetCalibrationManagementState(enable):
			raise get_windows_error(ctypes.windll.kernel32.GetLastError())
		return True


def enable_per_user_profiles(enable=True, display_no=0):
	""" Enable per user profiles under Vista/Windows 7 """
	if sys.getwindowsversion() < (6, ):
		# Windows XP doesn't have per-user profiles
		raise NotImplementedError("Per-user profiles are only available "
								  "in Windows Vista, 7 or later")
	device = get_display_device(display_no)
	if device:
		if False:
			# Using registry - NEVER
			key = _get_icm_display_device_key(device)
			_winreg.SetValueEx(key, "UsePerUserProfiles", 0,
							   _winreg.REG_DWORD, int(enable))
		else:
			# Using ctypes
			mscms = _get_mscms_dll_handle()
			if not mscms:
				return False
			if not mscms.WcsSetUsePerUserProfiles(unicode(device.DeviceID),
																CLASS_MONITOR,
																enable):
				raise get_windows_error(ctypes.windll.kernel32.GetLastError())
		return True


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


def get_display_device(display_no=0):
	# The ordering will work as long as Argyll continues using
	# EnumDisplayMonitors
	monitors = get_real_display_devices_info()
	moninfo = monitors[display_no]
	# via win32api & registry
	return get_active_display_device(moninfo["Device"])


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


def get_windows_error(errorcode):
	for name in dir(winerror):
		if name.startswith("ERROR_") and getattr(winerror, name) == errorcode:
			return WindowsError(errorcode, name)
	return WindowsError(errorcode, "")


def per_user_profiles_isenabled(display_no=0):
	""" Check if per user profiles is enabled under Vista/Windows 7 """
	if sys.getwindowsversion() < (6, ):
		# Windows XP doesn't have per-user profiles
		return False
	device = get_display_device(display_no)
	if device:
		if False:
			# Using registry - NEVER
			key = _get_icm_display_device_key(device)
			return bool(_winreg.QueryValueEx(key, "UsePerUserProfiles")[0])
		else:
			# Using ctypes
			mscms = _get_mscms_dll_handle()
			pbool = ctypes.pointer(ctypes.c_bool())
			if not mscms or not mscms.WcsGetUsePerUserProfiles(unicode(device.DeviceID),
																CLASS_MONITOR,
																pbool):
				return
			return bool(pbool.contents)


def win_ver():
	""" Get Windows version info """
	csd = sys.getwindowsversion()[-1]
	# Use the registry to get product name, e.g. 'Windows 7 Ultimate'.
	# Not recommended, but we don't care.
	pname = "Windows"
	key = None
	try:
		key = _winreg.OpenKeyEx(_winreg.HKEY_LOCAL_MACHINE,
								r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
		pname = _winreg.QueryValueEx(key, "ProductName")[0]
	except Exception, e:
		pass
	finally:
		if key:
			_winreg.CloseKey(key)
	return pname, csd


if __name__ == "__main__":
	if "calibration" in sys.argv[1:]:
		if "enable" in sys.argv[1:] or "disable" in sys.argv[1:]:
			enable_calibration_management(sys.argv[1:][-1] != "disable")
		print calibration_management_isenabled()
	elif "per_user_profiles" in sys.argv[1:]:
		if "enable" in sys.argv[1:] or "disable" in sys.argv[1:]:
			enable_per_user_profiles(sys.argv[1:][-1] != "disable")
		print per_user_profiles_isenabled()
