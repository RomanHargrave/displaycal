# -*- coding: utf-8 -*-

import ctypes
import _winreg
import struct
import sys

import pywintypes
import win32api
import win32con
import win32process
import winerror

from ctypes import POINTER, byref, sizeof, windll
from ctypes.wintypes import HANDLE, DWORD, LPWSTR

if not hasattr(ctypes, "c_bool"):
	# Python 2.5
	ctypes.c_bool = ctypes.c_int

if sys.getwindowsversion() >= (6, ):
	LPDWORD = POINTER(DWORD)
	PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
	kernel32 = windll.kernel32
	QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
	QueryFullProcessImageNameW.argtypes = [HANDLE, DWORD, LPWSTR, LPDWORD]
	QueryFullProcessImageNameW.restype  = bool

try:
	psapi = ctypes.windll.psapi
except WindowsError:
	psapi = None

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


def _get_icm_display_device_key(devicekey):
	monkey = devicekey.split("\\")[-2:]  # pun totally intended
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


def enable_per_user_profiles(enable=True, display_no=0, devicekey=None):
	""" Enable per user profiles under Vista/Windows 7 """
	if sys.getwindowsversion() < (6, ):
		# Windows XP doesn't have per-user profiles
		raise NotImplementedError("Per-user profiles are only available "
								  "in Windows Vista, 7 or later")
	if not devicekey:
		device = get_display_device(display_no)
		if device:
			devicekey = device.DeviceKey
	if devicekey:
		if False:
			# Using registry - NEVER
			key = _get_icm_display_device_key(devicekey)
			_winreg.SetValueEx(key, "UsePerUserProfiles", 0,
							   _winreg.REG_DWORD, int(enable))
		else:
			# Using ctypes
			mscms = _get_mscms_dll_handle()
			if not mscms:
				return False
			if not mscms.WcsSetUsePerUserProfiles(unicode(devicekey),
																CLASS_MONITOR,
																enable):
				raise get_windows_error(ctypes.windll.kernel32.GetLastError())
		return True


def get_display_devices(devicename):
	"""
	Get all display devices of an output (there can be several)
	
	Return value: list of display devices
	
	Example usage:
	get_display_devices('\\\\.\\DISPLAY1')
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
	return devices


def get_active_display_device(devicename):
	"""
	Get active display device of an output (there can only be one per output)
	
	Return value: display device object or None
	
	Example usage:
	get_active_display_device('\\\\.\\DISPLAY1')
	devicename = '\\\\.\\DISPLAYn' where n is a positive integer starting at 1
	
	"""
	devices = get_display_devices(devicename)
	for device in devices:
		if (device.StateFlags & DISPLAY_DEVICE_ACTIVE 
			and (len(devices) == 1 or device.StateFlags & 
									  DISPLAY_DEVICE_MULTI_DRIVER)):
			return device


def get_display_device(display_no=0, use_active_display_device=False):
	# The ordering will work as long as Argyll continues using
	# EnumDisplayMonitors
	monitors = get_real_display_devices_info()
	moninfo = monitors[display_no]
	if use_active_display_device:
		return get_active_display_device(moninfo["Device"])
	else:
		return win32api.EnumDisplayDevices(moninfo["Device"], 0)


def get_process_filename(pid):
	if sys.getwindowsversion() >= (6, ):
		flags = PROCESS_QUERY_LIMITED_INFORMATION
	else:
		flags = win32con.PROCESS_QUERY_INFORMATION |  win32con.PROCESS_VM_READ
	handle = win32api.OpenProcess(flags, False, pid)
	try:
		if sys.getwindowsversion() >= (6, ):
			dwSize = win32con.MAX_PATH
			while True:
				dwFlags = 0  # The name should use the Win32 path format
				lpdwSize = DWORD(dwSize)
				lpExeName = ctypes.create_unicode_buffer("", lpdwSize.value + 1)
				success = QueryFullProcessImageNameW(int(handle), dwFlags,
													 lpExeName, byref(lpdwSize))
				if success and 0 < lpdwSize.value < dwSize:
					break
				error = kernel32.GetLastError()
				if error != winerror.ERROR_INSUFFICIENT_BUFFER:
					raise ctypes.WinError(error)
				dwSize = dwSize + 256
				if dwSize > 0x1000:
					# This prevents an infinite loop under Windows Server 2008
					# if the path contains spaces, see
					# http://msdn.microsoft.com/en-us/library/ms684919(VS.85).aspx#4
					raise ctypes.WinError(error)
			filename = lpExeName.value
		else:
			filename = win32process.GetModuleFileNameEx(handle, 0)
	finally:
		win32api.CloseHandle(handle)
	return filename


def get_file_info(filename):
	""" Get exe/dll file information """
	info = {"FileInfo": None, "StringFileInfo": {}, "FileVersion": None}

	finfo = win32api.GetFileVersionInfo(filename, "\\")
	info["FileInfo"] = finfo
	info["FileVersion"] = "%i.%i.%i.%i" % (finfo["FileVersionMS"] / 65536,
										   finfo["FileVersionMS"] % 65536,
										   finfo["FileVersionLS"] / 65536,
										   finfo["FileVersionLS"] % 65536)
	for lcid, codepage in win32api.GetFileVersionInfo(filename,
													  "\\VarFileInfo\\Translation"):
		info["StringFileInfo"][lcid, codepage] = {}
		for name in ["Comments", "CompanyName", "FileDescription",
					 "FileVersion", "InternalName", "LegalCopyright",
					 "LegalTrademarks", "OriginalFilename", "PrivateBuild",
					 "ProductName", "ProductVersion", "SpecialBuild"]:
			value = win32api.GetFileVersionInfo(filename,
												u"\\StringFileInfo\\%04X%04X\\%s" %
												(lcid, codepage, name))
			if value is not None:
				info["StringFileInfo"][lcid, codepage][name] = value

	return info


def get_pids():
	""" Get PIDs of all running processes """
	pids_count = 1024
	while True:
		pids = (DWORD * pids_count)()
		pids_size = sizeof(pids)
		bytes = DWORD()
		if not psapi.EnumProcesses(byref(pids), pids_size, byref(bytes)):
			raise get_windows_error(ctypes.windll.kernel32.GetLastError())
		if bytes.value >= pids_size:
			pids_count *= 2
			continue
		count = bytes.value / (pids_size / pids_count)
		return filter(None, pids[:count])


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
	return ctypes.WinError(errorcode)


def per_user_profiles_isenabled(display_no=0, devicekey=None):
	""" Check if per user profiles is enabled under Vista/Windows 7 """
	if sys.getwindowsversion() < (6, ):
		# Windows XP doesn't have per-user profiles
		return False
	if not devicekey:
		device = get_display_device(display_no)
		if device:
			devicekey = device.DeviceKey
	if devicekey:
		if False:
			# Using registry - NEVER
			key = _get_icm_display_device_key(devicekey)
			return bool(_winreg.QueryValueEx(key, "UsePerUserProfiles")[0])
		else:
			# Using ctypes
			mscms = _get_mscms_dll_handle()
			pbool = ctypes.pointer(ctypes.c_bool())
			if not mscms or not mscms.WcsGetUsePerUserProfiles(unicode(devicekey),
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
