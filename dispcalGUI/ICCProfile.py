#!/usr/bin/env python
# -*- coding: utf-8 -*-

from hashlib import md5
import binascii
import datetime
import locale
import math
import os
import re
import struct
import sys
from time import localtime, mktime, strftime
from UserString import UserString
if sys.platform == "win32":
	import _winreg
else:
	import subprocess as sp
	if sys.platform == "darwin":
		from platform import mac_ver
		import appscript

if sys.platform == "win32":
	try:
		import pywintypes
		import win32api
		## import win32gui
	except ImportError:
		pass

import colormath
from defaultpaths import iccprofiles, iccprofiles_home
from encoding import get_encodings
from meta import version
from ordereddict import OrderedDict
try:
	from log import safe_print
except ImportError:
	from safe_print import safe_print
from util_decimal import float2dec
from util_list import intlist
from util_str import hexunescape

if sys.platform not in ("darwin", "win32"):
	from edid import get_edid
	from util_x import get_display
	try:
		import colord
	except ImportError:
		colord = None
	try:
		import xrandr
	except ImportError:
		xrandr = None
elif sys.platform == "win32":
	import util_win

debug = "-d" in sys.argv[1:] or "--debug" in sys.argv[1:]

fs_enc = get_encodings()[1]

encodings = {
	"mac": {
		141: "africaans",
		36: "albanian",
		85: "amharic",
		12: "arabic",
		51: "armenian",
		68: "assamese",
		134: "aymara",
		49: "azerbaijani-cyrllic",
		50: "azerbaijani-arabic",
		129: "basque",
		67: "bengali",
		137: "dzongkha",
		142: "breton",
		44: "bulgarian",
		77: "burmese",
		46: "byelorussian",
		78: "khmer",
		130: "catalan",
		92: "chewa",
		33: "simpchinese",
		19: "tradchinese",
		18: "croatian",
		38: "czech",
		7: "danish",
		4: "dutch",
		0: "roman",
		94: "esperanto",
		27: "estonian",
		30: "faeroese",
		31: "farsi",
		13: "finnish",
		34: "flemish",
		1: "french",
		140: "galician",
		144: "scottishgaelic",
		145: "manxgaelic",
		52: "georgian",
		2: "german",
		14: "greek-monotonic",
		148: "greek-polytonic",
		133: "guarani",
		69: "gujarati",
		10: "hebrew",
		21: "hindi",
		26: "hungarian",
		15: "icelandic",
		81: "indonesian",
		143: "inuktitut",
		35: "irishgaelic",
		146: "irishgaelic-dotsabove",
		3: "italian",
		11: "japanese",
		138: "javaneserom",
		73: "kannada",
		61: "kashmiri",
		48: "kazakh",
		90: "kiryarwanda",
		54: "kirghiz",
		91: "rundi",
		23: "korean",
		60: "kurdish",
		79: "lao",
		131: "latin",
		28: "latvian",
		24: "lithuanian",
		43: "macedonian",
		93: "malagasy",
		83: "malayroman-latin",
		84: "malayroman-arabic",
		72: "malayalam",
		16: "maltese",
		66: "marathi",
		53: "moldavian",
		57: "mongolian",
		58: "mongolian-cyrillic",
		64: "nepali",
		9: "norwegian",
		71: "oriya",
		87: "oromo",
		59: "pashto",
		25: "polish",
		8: "portuguese",
		70: "punjabi",
		132: "quechua",
		37: "romanian",
		32: "russian",
		29: "sami",
		65: "sanskrit",
		42: "serbian",
		62: "sindhi",
		76: "sinhalese",
		39: "slovak",
		40: "slovenian",
		88: "somali",
		6: "spanish",
		139: "sundaneserom",
		89: "swahili",
		5: "swedish",
		82: "tagalog",
		55: "tajiki",
		74: "tamil",
		135: "tatar",
		75: "telugu",
		22: "thai",
		63: "tibetan",
		86: "tigrinya",
		147: "tongan",
		17: "turkish",
		56: "turkmen",
		136: "uighur",
		45: "ukrainian",
		20: "urdu",
		47: "uzbek",
		80: "vietnamese",
		128: "welsh",
		41: "yiddish"
	}
}

colorants = {
	0: {
		"description": "unknown"
		},
	1: {
		"description": "ITU-R BT.709",
		"channels": ((0.64, 0.33), (0.3, 0.6), (0.15, 0.06))
		},
	2: {
		"description": "SMPTE RP145-1994",
		"channels": ((0.63, 0.34), (0.31, 0.595), (0.155, 0.07))
		},
	3: {
		"description": "EBU Tech.3213-E",
		"channels": ((0.64, 0.33), (0.29, 0.6), (0.15, 0.06))
		},
	4: {
		"description": "P22",
		"channels": ((0.625, 0.34), (0.28, 0.605), (0.155, 0.07))
		}
}

geometry = {
	0: "unknown",
	1: "0/45 or 45/0",
	2: "0/d or d/0"
}

illuminants = {
	0: "unknown",
	1: "D50",
	2: "D65",
	3: "D93",
	4: "F2",
	5: "D55",
	6: "A",
	7: "E",
	8: "F8"
}

observers = {
	0: "unknown",
	1: "CIE 1931",
	2: "CIE 1964"
}


def Property(func):
	return property(**func())


def _colord_get_display_profile(display_no=0):
	try:
		edid = get_edid(display_no)
	except (TypeError, ValueError):
		return None
	if edid:
		incomplete = False
		section_parts = ["xrandr"]
		for name in ["manufacturer", "monitor_name", "ascii", 
					 "serial_ascii", "serial_32"]:
			if name in edid:
				if name == "serial_32" and "serial_ascii" in edid:
					# Only add serial if no ascii serial
					break
				section_parts.append(str(edid[name]).replace(" ", "_"))
			elif name not in ("ascii", "serial_ascii"):
				# Do not allow anything other than the ASCII 
				# strings to be missing
				incomplete = True
				break
		if not incomplete:
			device_key = "_".join(section_parts)
			profile_path = colord.cd_get_default_profile(device_key)
			if profile_path:
				return ICCProfile(profile_path)
	return None


def _winreg_get_display_profile(monkey, current_user=False):
	filename = None
	try:
		if current_user and sys.getwindowsversion() >= (6, ):
			# Vista / Windows 7 ONLY
			# User has to place a check in 'use my settings for this device'
			# in the color management control panel at least once to cause
			# this key to be created, otherwise it won't exist
			subkey = "\\".join(["Software", "Microsoft", "Windows NT", 
								"CurrentVersion", "ICM", "ProfileAssociations", 
								"Display"] + monkey)
			key = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, subkey)
			## print "HKEY_CURRENT_USER", subkey
		else:
			subkey = "\\".join(["SYSTEM", "CurrentControlSet", "Control", 
								"Class"] + monkey)
			key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, subkey)
			## print "HKEY_LOCAL_MACHINE", subkey
		numsubkeys, numvalues, mtime = _winreg.QueryInfoKey(key)
		for i in range(numvalues):
			name, value, type_ = _winreg.EnumValue(key, i)
			## print i, name, repr(value), type_
			if name == "ICMProfile":
				if type_ == _winreg.REG_BINARY:
					# Win2k/XP
					# convert to list of strings
					value = value.decode('utf-16').split("\0")
				elif type_ == _winreg.REG_MULTI_SZ:
					# Vista / Windows 7
					# nothing to be done, _winreg returns a list of strings
					pass
				if isinstance(value, list):
					while "" in value:
						value.remove("")
					while value:
						# last existing file in the list is active
						if os.path.isfile(os.path.join(iccprofiles[0], 
													   value[-1])):
							filename = value[-1]
							break
						value = value[:-1]
				else:
					if os.path.isfile(os.path.join(iccprofiles[0], 
												   value)):
						filename = value
			elif name == "UsePerUserProfiles" and not value:
				filename = None
				break
	except WindowsError, exception:
		if exception.args[0] == 2:
			# Key does not exist
			pass
		else:
			raise
	except Exception, exception:
		raise
	if not filename and not current_user:
		# fall back to sRGB
		filename = os.path.join(iccprofiles[0], 
								"sRGB Color Space Profile.icm")
	## print repr(filename)
	if filename:
		return ICCProfile(filename)
	return None


def _xrandr_get_display_profile(display_no=0, x_hostname="", x_display=0, 
								x_screen=0):
	try:
		property = xrandr.get_output_property(display_no, "_ICC_PROFILE", 
											  xrandr.XA_CARDINAL, x_hostname, 
											  x_display, x_screen)
	except ValueError:
		return None
	if property:
		return ICCProfile("".join(chr(i) for i in property))
	return None


def _x11_get_display_profile(display_no=0, x_hostname="", x_display=0, 
							 x_screen=0):
	try:
		atom = xrandr.get_atom("_ICC_PROFILE" + ("" if display_no == 0 else 
													 "_%s" % display_no), 
							   xrandr.XA_CARDINAL, x_hostname, x_display, 
							   x_screen)
	except ValueError:
		return None
	if atom:
		return ICCProfile("".join(chr(i) for i in atom))
	return None


def get_display_profile(display_no=0, x_hostname="", x_display=0, 
						x_screen=0):
	""" Return ICC Profile for display n or None """
	profile = None
	if sys.platform == "win32":
		if not "win32api" in sys.modules: ## or not "win32gui" in sys.modules:
			raise ImportError("pywin32 not available")
		# The ordering will work as long as Argyll continues using
		# EnumDisplayMonitors
		monitors = util_win.get_real_display_devices_info()
		moninfo = monitors[display_no]
		# via GetICMProfile - not dynamic, will not reflect runtime changes
		## dc = win32gui.CreateDC("DISPLAY", moninfo["Device"], None)
		## filename = win32api.GetICMProfile(dc)
		## win32gui.ReleaseDC(None, dc)
		# via win32api & registry
		device = util_win.get_active_display_device(moninfo["Device"])
		if device:
			monkey = device.DeviceKey.split("\\")[-2:]  # pun totally intended
			## print monkey
			# current user
			profile = _winreg_get_display_profile(monkey, True)
			if not profile:
				# system
				profile = _winreg_get_display_profile(monkey)
	elif "--admin" not in sys.argv[1:] or mac_ver()[0] >= "10.6":
		# We set --admin on Mac OS X when using osascript to run as admin
		# under a standard account. In this case any attempt to access the
		# display profile with AppleScript will time out with 
		# ColorSyncScripting, so we skip it
		if sys.platform == "darwin":
			if intlist(mac_ver()[0].split(".")) >= [10, 6]:
				options = ["Image Events"]
			else:
				options = ["ColorSyncScripting"]
		else:
			options = ["_ICC_PROFILE"]
			display = get_display()
			if not x_hostname:
				x_hostname = display[0]
			if not x_display:
				x_display = display[1]
			if not x_screen:
				x_screen = display[2]
		for option in options:
			if sys.platform == "darwin":
				# appscript: one-based index
				display_profile = appscript.app(option).displays[display_no + 1].display_profile.get()
				if isinstance(display_profile, appscript.reference.Reference):
					fobj = display_profile.location.get()
					if fobj:
						path = fobj.path
						if type(fobj.path) not in (str, unicode):
							# Mac OS X 10.6: We need to turn this:
							# app(u'/System/Library/CoreServices/Image Events.app').aliases[u'Macintosh HD:Library:ColorSync:Profiles:Displays:ProfileName.icc'].path
							# into a POSIX path
							#
							# Turn into unicode representation
							path = unicode(repr(path))
							# Get the HFS path from the aliases[...] part
							path = re.sub("^.+\\[u?'", "", path).replace("'].path", "")
							# Replace unicode escapes ('\u') with literal unicode chars
							path = re.sub("\\\\u([0-9a-f]{4})", hexunescape, path)
							# Replace hex escapes ('\x') with literal chars
							path = re.sub("\\\\x([0-9a-f]{2})", hexunescape, path)
							# Split path and strip off the leading 'Macintosh HD'
							path = path.split(":")[1:]
							# Assemble POSIX path
							path = os.path.join(os.path.sep, *path)
						profile = ICCProfile(path)
			else:
				# Linux
				# Try colord
				if colord:
					try:
						profile = _colord_get_display_profile(display_no)
					except colord.CDError, exception:
						safe_print(exception)
					if profile:
						return profile
				# Try XrandR
				if xrandr and option == "_ICC_PROFILE":
					if debug:
						safe_print("Using XrandR")
					profile = _xrandr_get_display_profile(display_no, 
														  x_hostname, 
														  x_display, x_screen)
					if profile:
						return profile
					if debug:
						safe_print("Couldn't get _ICC_PROFILE XrandR output property")
						safe_print("Using X11")
					# Try X11
					profile = _x11_get_display_profile(display_no, 
													   x_hostname, 
													   x_display, x_screen)
					if profile:
						return profile
					if debug:
						safe_print("Couldn't get _ICC_PROFILE X atom")
				# Read up to 8 MB of any X properties
				if debug:
					safe_print("Using xprop")
				atom = "%s%s" % (option, "" if display_no == 0 else 
									   "_%s" % display_no)
				tgt_proc = sp.Popen(["xprop", "-display", "%s:%s.%s" % 
														  (x_hostname, 
														   x_display, 
														   x_screen), 
									 "-len", "8388608", "-root", "-notype", 
									 atom], stdin=sp.PIPE, stdout=sp.PIPE, 
									stderr=sp.PIPE)
				stdout, stderr = [data.strip("\n") for data in tgt_proc.communicate()]
				if stdout:
					if sys.platform == "darwin":
						filename = unicode(stdout, "UTF-8")
						profile = ICCProfile(filename)
					else:
						raw = [item.strip() for item in stdout.split("=")]
						if raw[0] == atom and len(raw) == 2:
							bin = "".join([chr(int(part)) for part in raw[1].split(", ")])
							profile = ICCProfile(bin)
				elif stderr and tgt_proc.wait() != 0:
					raise IOError(stderr)
			if profile:
				break
	return profile


def dateTimeNumber(binaryString):
	"""
	Byte
	Offset Content                                     Encoded as...
	0..1   number of the year (actual year, e.g. 1994) uInt16Number
	2..3   number of the month (1-12)                  uInt16Number
	4..5   number of the day of the month (1-31)       uInt16Number
	6..7   number of hours (0-23)                      uInt16Number
	8..9   number of minutes (0-59)                    uInt16Number
	10..11 number of seconds (0-59)                    uInt16Number
	"""
	Y, m, d, H, M, S = [uInt16Number(chunk) for chunk in (binaryString[:2], 
														  binaryString[2:4], 
														  binaryString[4:6], 
														  binaryString[6:8], 
														  binaryString[8:10], 
														  binaryString[10:12])]
	return datetime.datetime(*(Y, m, d, H, M, S))


def dateTimeNumber_tohex(dt):
	data = [uInt16Number_tohex(n) for n in dt.timetuple()[:6]]
	return "".join(data)


def s15Fixed16Number(binaryString):
	return struct.unpack(">i", binaryString)[0] / 65536.0


def s15Fixed16Number_tohex(num):
	return struct.pack(">i", num * 65536)


def u16Fixed16Number(binaryString):
	return struct.unpack(">I", binaryString)[0] / 65536.0


def u16Fixed16Number_tohex(num):
	return struct.pack(">I", int(num * 65536))


def u8Fixed8Number(binaryString):
	return struct.unpack(">H", binaryString)[0] / 256.0


def u8Fixed8Number_tohex(num):
	return struct.pack(">H", int(num * 256))


def uInt16Number(binaryString):
	return struct.unpack(">H", binaryString)[0]


def uInt16Number_tohex(num):
	return struct.pack(">H", num)


def uInt32Number(binaryString):
	return struct.unpack(">I", binaryString)[0]


def uInt32Number_tohex(num):
	return struct.pack(">I", num)


def uInt64Number(binaryString):
	return struct.unpack(">Q", binaryString)[0]


def uInt64Number_tohex(num):
	return struct.pack(">Q", num)


def uInt8Number(binaryString):
	return struct.unpack(">H", "\0" + binaryString)[0]


def uInt8Number_tohex(num):
	return struct.pack(">H", num)[1]


def videoCardGamma(tagData, tagSignature):
	reserved = uInt32Number(tagData[4:8])
	tagType = uInt32Number(tagData[8:12])
	if tagType == 0: # table
		return VideoCardGammaTableType(tagData, tagSignature)
	elif tagType == 1: # formula
		return VideoCardGammaFormulaType(tagData, tagSignature)




class CRInterpolation(object):

	"""
	Catmull-Rom interpolation.
	Curve passes through the points exactly, with neighbouring points influencing curvature.
	points[] should be at least 3 points long.
	"""

	def __init__(self, points):
		self.points = points

	def __call__(self, pos):
		lbound = int(math.floor(pos) - 1)
		ubound = int(math.ceil(pos) + 1)
		t = pos % 1.0
		if abs((lbound + 1) - pos) < 0.0001:
			# sitting on a datapoint, so just return that
			return self.points[lbound + 1]
		if lbound < 0:
			p = self.points[:ubound + 1]
			# extend to the left linearly
			while len(p) < 4:
				p.insert(0, p[0] - (p[1] - p[0]))
		else:
			p = self.points[lbound:ubound + 1]
			# extend to the right linearly
			while len(p) < 4:
				p.append(p[-1] - (p[-2] - p[-1]))
		t2 = t * t
		return 0.5 * ((2 * p[1]) + (-p[0] + p[2]) * t + 
					  ((2 * p[0]) - (5 * p[1]) + (4 * p[2]) - p[3]) * t2 +
					  (-p[0] + (3 * p[1]) - (3 * p[2]) + p[3]) * (t2 * t))


class ADict(dict):

	"""
	Convenience class for dictionary key access via attributes.
	
	Instead of writing aodict[key], you can also write aodict.key
	
	"""

	def __init__(self, *args, **kwargs):
		dict.__init__(self, *args, **kwargs)

	def __getattr__(self, name):
		if name in self:
			return self[name]
		else:
			return self.__getattribute__(name)

	def __setattr__(self, name, value):
		self[name] = value


class AODict(ADict, OrderedDict):

	def __init__(self, *args, **kwargs):
		OrderedDict.__init__(self, *args, **kwargs)

	def __setattr__(self, name, value):
		if name == "_keys":
			object.__setattr__(self, name, value)
		else:
			self[name] = value


class ICCProfileTag(object):

	def __init__(self, tagData, tagSignature):
		self.tagData = tagData
		self.tagSignature = tagSignature

	def __setattr__(self, name, value):
		if not isinstance(self, dict) or name in ("_keys", "tagData", 
												  "tagSignature"):
			object.__setattr__(self, name, value)
		else:
			self[name] = value
	
	def __repr__(self):
		"""
		t.__repr__() <==> repr(t)
		"""
		if isinstance(self, OrderedDict):
			return OrderedDict.__repr__(self)
		elif isinstance(self, dict):
			return dict.__repr__(self)
		elif isinstance(self, UserString):
			return UserString.__repr__(self)
		elif isinstance(self, list):
			return list.__repr__(self)
		else:
			if not self:
				return "%s.%s()" % (self.__class__.__module__, self.__class__.__name__)
			return "%s.%s(%r)" % (self.__class__.__module__, self.__class__.__name__, self.tagData)


class Text(ICCProfileTag, UserString, str):

	def __init__(self, seq):
		UserString.__init__(self, seq)

	def __unicode__(self):
		return unicode(self.data, fs_enc, errors="replace")


class Colorant(ADict):

	def __init__(self, binaryString):
		self.type = uInt32Number(binaryString)
		self.channels = colorants[self.type].channels
		self.description = colorants[self.type].description


class Geometry(ADict):

	def __init__(self, binaryString):
		self.type = uInt32Number(binaryString)
		self.description = geometry[self.type]


class Illuminant(ADict):

	def __init__(self, binaryString):
		self.type = uInt32Number(binaryString)
		self.description = illuminants[self.type]


class Observer(ADict):

	def __init__(self, binaryString):
		self.type = uInt32Number(binaryString)
		self.description = observers[self.type]


class ChromacityType(ICCProfileTag, ADict):

	def __init__(self, tagData, tagSignature):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		deviceChannelsCount = uInt16Number(tagData[8:10])
		colorant = uInt16Number(tagData[10:12])
		if colorant in colorants:
			colorant = colorants[colorant]
		channels = tagData[12:]
		self.colorant = colorant
		self.channels = []
		while channels:
			self.channels.append((u16Fixed16Number(channels[:4]), 
								  u16Fixed16Number(channels[4:8])))
			channels = channels[8:]


class CurveType(ICCProfileTag, list):

	def __init__(self, tagData=None, tagSignature=None):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		if not tagData:
			return
		curveEntriesCount = uInt32Number(tagData[8:12])
		curveEntries = tagData[12:]
		if curveEntriesCount == 1:
			# gamma
			self.append(u8Fixed8Number(curveEntries[:2]))
		else:
			# curve
			while curveEntries:
				self.append(uInt16Number(curveEntries[:2]))
				curveEntries = curveEntries[2:]
	
	@Property
	def tagData():
		doc = """
		Return raw tag data.
		"""
	
		def fget(self):
			curveEntriesCount = len(self)
			tagData = ["curv", "\0" * 4, uInt32Number_tohex(curveEntriesCount)]
			if curveEntriesCount == 1:
				tagData.append(u8Fixed8Number_tohex(self[0]))
			else:
				for curveEntry in self:
					tagData.append(uInt16Number_tohex(curveEntry))
			return "".join(tagData)
		
		def fset(self, tagData):
			pass
		
		return locals()


class DateTimeType(ICCProfileTag, list):

	def __init__(self, tagData, tagSignature):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		self += dateTimeNumber(tagData[8:20])


class DictType(ICCProfileTag, AODict):
	""" ICC dictType Tag
	
	Implements all features of 'Dictionary Type and Metadata TAG Definition'
	(ICC spec revision 2010-02-25), including shared data (the latter will
	only be effective for mutable types, ie. MultiLocalizedUnicodeType)
	
	Examples:
	
	tag[key]   Returns the (non-localized) value
	tag.getname(key, locale='en_US') Returns the localized name if present
	tag.getvalue(key, locale='en_US') Returns the localized value if present
	tag[key] = value   Sets the (non-localized) value
	
	"""

	def __init__(self, tagData=None, tagSignature=None):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		AODict.__init__(self)
		if not tagData:
			return
		numrecords = uInt32Number(tagData[8:12])
		recordlen = uInt32Number(tagData[12:16])
		if recordlen not in (16, 24, 32):
			safe_print("Error (non-critical): '%s' invalid record length "
					   "(expected 16, 24 or 32, got %s)" % (tagData[:4],
															recordlen))
			return
		elements = {}
		for n in range(0, numrecords):
			record = tagData[16 + n * recordlen:16 + (n + 1) * recordlen]
			if len(record) < recordlen:
				safe_print("Error (non-critical): '%s' record %s too short "
						   "(expected %s bytes, got %s bytes)" % (tagData[:4],
																  n,
																  recordlen,
																  len(record)))
				break
			for key, offsetpos in (("name", 0), ("value", 8),
								   ("display_name", 16), ("display_value", 24)):
				if (offsetpos in (0, 8) or recordlen == offsetpos + 8 or
					recordlen == offsetpos + 16):
					# Required:
					# Bytes 0..3, 4..7: Name offset and size
					# Bytes 8..11, 12..15: Value offset and size
					# Optional:
					# Bytes 16..23, 24..23: Display name offset and size
					# Bytes 24..27, 28..31: Display value offset and size
					offset = uInt32Number(record[offsetpos:offsetpos + 4])
					size = uInt32Number(record[offsetpos + 4:offsetpos + 8])
					if offset > 0:
						if (offset, size) in elements:
							# Use existing element if same offset and size
							# This will really only make a difference for
							# mutable types ie. MultiLocalizedUnicodeType
							data = elements[(offset, size)]
						else:
							data = tagData[offset:offset + size]
							try:
								if key.startswith("display_"):
									data = MultiLocalizedUnicodeType(data,
																	 "mluc")
								else:
									data = data.decode("UTF-16-BE",
													   "replace").rstrip("\0")
							except Exception, exception:
								safe_print("Error (non-critical): could not "
										   "decode '%s', offset %s, length %s" %
										   (tagData[:4], offset, size))
							# Remember element by offset and size
							elements[(offset, size)] = data
						if key == "name":
							name = data
							self[name] = ""
						else:
							self.get(name)[key] = data
					##else:
						##safe_print(name, key)

	def __getitem__(self, name):
		return self.get(name).value

	def __setitem__(self, name, value):
		AODict.__setitem__(self, name, ADict(value=value))

	@Property
	def tagData():
		doc = """
		Return raw tag data.
		"""

		def fget(self):
			numrecords = len(self)
			recordlen = 16
			keys = ("name", "value")
			for value in self.itervalues():
				if "display_value" in value:
					recordlen = 32
					break
				elif "display_name" in value:
					recordlen = 24
			if recordlen > 16:
				keys += ("display_name", )
			if recordlen > 24:
				keys += ("display_value", )
			tagData = ["dict", "\0" * 4, uInt32Number_tohex(numrecords),
					   uInt32Number_tohex(recordlen)]
			storage_offset = 16 + numrecords * recordlen
			storage = []
			elements = []
			offsets = []
			for item in self.iteritems():
				for key in keys:
					if key == "name":
						element = item[0]
					else:
						element = item[1].get(key)
					if element is None:
						offset = 0
						size = 0
					else:
						if element in elements:
							# Use existing offset and size if same element
							offset, size = offsets[elements.index(element)]
						else:
							offset = storage_offset + len("".join(storage))
							if isinstance(element, MultiLocalizedUnicodeType):
								data = element.tagData
							else:
								data = unicode(element).encode("UTF-16-BE")
							size = len(data)
							if isinstance(element, MultiLocalizedUnicodeType):
								# Remember element, offset and size
								elements.append(element)
								offsets.append((offset, size))
							# Pad all data with binary zeros so it lies on 
							# 4-byte boundaries
							padding = int(math.ceil(size / 4.0)) * 4 - size
							data += "\0" * padding
							storage.append(data)
					tagData.append(uInt32Number_tohex(offset))
					tagData.append(uInt32Number_tohex(size))
			tagData.extend(storage)
			return "".join(tagData)

		def fset(self, tagData):
			pass

		return locals()

	def getname(self, name, default=None, locale="en_US"):
		""" Convenience function to get (localized) names
		
		"""
		item = self.get(name, default)
		if item is default:
			return default
		if locale and "display_name" in item:
			return item.display_name.get_localized_string(*locale.split("_"))
		else:
			return name

	def getvalue(self, name, default=None, locale="en_US"):
		""" Convenience function to get (localized) values
		
		"""
		item = self.get(name, default)
		if item is default:
			return default
		if locale and "display_value" in item:
			return item.display_value.get_localized_string(*locale.split("_"))
		else:
			return item.value

	def setitem(self, name, value, display_name=None, display_value=None):
		""" Convenience function to set items
		
		display_name and display_value (if given) should be dict types with
		country -> language -> string mappings, e.g.:
		
		{"en": {"US": u"localized string"},
		 "de": {"DE": u"localized string", "CH": u"localized string"}}
		
		"""
		self[name] = value
		item = self.get(name)
		if display_name:
			item.display_name = MultiLocalizedUnicodeType()
			item.display_name.update(display_name)
		if display_value:
			item.display_value = MultiLocalizedUnicodeType()
			item.display_value.update(display_value)

	def to_json(self, encoding="UTF-8", errors="replace", locale="en_US"):
		""" Return a JSON representation
		
		Display names/values are used if present.
		
		"""
		json = []
		for name in self:
			value = self.getvalue(name, None, locale)
			name = self.getname(name, None, locale)
			#try:
				#value = str(int(value))
			#except ValueError:
				#try:
					#value = str(float(value))
				#except ValueError:
			value = '"%s"' % repr(unicode(value))[2:-1]
			json.append('"%s": %s' % tuple([re.sub(r"\\x([0-9a-f]{2})",
												   "\\u00\\1", item)
											for item in [repr(unicode(name))[2:-1],
														 value]]))
		return "{%s}" % ",\n".join(json)


class MeasurementType(ICCProfileTag, ADict):

	def __init__(self, tagData, tagSignature):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		self.update({
			"observer": Observer(tagData[8:12]),
			"backing": XYZNumber(tagData[12:24]),
			"geometry": Geometry(tagData[24:28]),
			"flare": u16Fixed16Number(tagData[28:32]),
			"illuminantType": Illuminant(tagData[32:36])
		})


class MultiLocalizedUnicodeType(ICCProfileTag, AODict): # ICC v4

	def __init__(self, tagData=None, tagSignature=None):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		AODict.__init__(self)
		if not tagData:
			return
		recordsCount = uInt32Number(tagData[8:12])
		recordSize = uInt32Number(tagData[12:16]) # 12
		records = tagData[16:16 + recordSize * recordsCount]
		while records:
			record = records[:recordSize]
			recordLanguageCode = record[:2]
			recordCountryCode = record[2:4]
			recordLength = uInt32Number(record[4:8])
			recordOffset = uInt32Number(record[8:12])
			self.add_localized_string(recordLanguageCode, recordCountryCode,
				unicode(tagData[recordOffset:recordOffset + recordLength], 
						"utf-16-be", "replace"))
			records = records[recordSize:]

	def __str__(self):
		return unicode(self).encode(sys.getdefaultencoding())

	def __unicode__(self):
		"""
		Return tag as string.
		"""
		# TODO: Needs some work re locales
		# (currently if en-UK or en-US is not found, simply the first entry 
		# is returned)
		if "en" in self:
			for countryCode in ("UK", "US"):
				if countryCode in self["en"]:
					return self["en"][countryCode]
		elif len(self):
			return self.values()[0].values()[0]
		else:
			return u""

	def add_localized_string(self, languagecode, countrycode, localized_string):
		""" Convenience function for adding localized strings """
		if languagecode not in self:
			self[languagecode] = AODict()
		self[languagecode][countrycode] = localized_string

	def get_localized_string(self, languagecode="en", countrycode="US"):
		""" Convenience function for retrieving localized strings
		
		Falls back to first locale available if the requested one isn't
		
		"""
		try:
			return self[languagecode][countrycode]
		except KeyError:
			return unicode(self)


	@Property
	def tagData():
		doc = """
		Return raw tag data.
		"""

		def fget(self):
			tagData = ["mluc", "\0" * 4]
			recordsCount = 0
			for languageCode in self:
				for countryCode in self[languageCode]:
					recordsCount += 1
			tagData.append(uInt32Number_tohex(recordsCount))
			recordSize = 12
			tagData.append(uInt32Number_tohex(recordSize))
			storage_offset = 16 + recordSize * recordsCount
			storage = []
			offsets = []
			for languageCode in self:
				for countryCode in self[languageCode]:
					tagData.append(languageCode + countryCode)
					data = self[languageCode][countryCode].encode("UTF-16-BE")
					if data in storage:
						offset, recordLength = offsets[storage.index(data)]
					else:
						recordLength = len(data)
						offset = len("".join(storage))
						offsets.append((offset, recordLength))
						storage.append(data)
					tagData.append(uInt32Number_tohex(recordLength))
					tagData.append(uInt32Number_tohex(storage_offset + offset))
			tagData.append("".join(storage))
			return "".join(tagData)

		def fset(self, tagData):
			pass

		return locals()


class s15Fixed16ArrayType(ICCProfileTag, list):

	def __init__(self, tagData=None, tagSignature=None):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		if tagData:
			data = tagData[8:]
			while data:
				self.append(s15Fixed16Number(data[0:4]))
				data = data[4:]
	
	@Property
	def tagData():
		doc = """
		Return raw tag data.
		"""
	
		def fget(self):
			tagData = ["sf32", "\0" * 4]
			for value in self:
				tagData.append(s15Fixed16Number_tohex(value))
			return "".join(tagData)
		
		def fset(self, tagData):
			pass
		
		return locals()


def SignatureType(tagData, tagSignature):
	tag = Text(tagData[8:12].rstrip("\0"))
	tag.tagData = tagData
	tag.tagSignature = tagSignature
	return tag


class TextDescriptionType(ICCProfileTag, ADict): # ICC v2

	def __init__(self, tagData=None, tagSignature=None):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		self.ASCII = ""
		if not tagData:
			return
		ASCIIDescriptionLength = uInt32Number(tagData[8:12])
		if ASCIIDescriptionLength:
			ASCIIDescription = tagData[12:12 + 
									   ASCIIDescriptionLength].strip("\0\n\r ")
			if ASCIIDescription:
				self.ASCII = ASCIIDescription
		unicodeOffset = 12 + ASCIIDescriptionLength
		self.unicodeLanguageCode = uInt32Number(
									tagData[unicodeOffset:unicodeOffset + 4])
		unicodeDescriptionLength = uInt32Number(tagData[unicodeOffset + 
														4:unicodeOffset + 8])
		if unicodeDescriptionLength:
			if unicodeOffset + 8 + unicodeDescriptionLength * 2 > len(tagData):
				# Damn you MS. The Unicode character count should be the number of 
				# double-byte characters (including trailing unicode NUL), not the
				# number of bytes as in the profiles created by Vista and later
				safe_print("Warning (non-critical): '%s' Unicode part end points "
						   "past the tag data, assuming number of bytes instead "
						   "of number of characters for length" % tagData[:4])
				unicodeDescriptionLength /= 2
			if tagData[unicodeOffset + 8 + 
					   unicodeDescriptionLength:unicodeOffset + 8 + 
					   unicodeDescriptionLength + 2] == "\0\0":
				safe_print("Warning (non-critical): '%s' Unicode part "
						   "seems to be a single-byte string (double-byte "
						   "string expected)" % tagData[:4])
				charBytes = 1 # fix for fubar'd desc
			else:
				charBytes = 2
			unicodeDescription = tagData[unicodeOffset + 8:unicodeOffset + 8 + 
										 (unicodeDescriptionLength) * charBytes]
			try:
				if charBytes == 1:
					unicodeDescription = unicode(unicodeDescription, 
												 errors="replace")
				else:
					if unicodeDescription[:2] == "\xfe\xff":
						# UTF-16 Big Endian
						if debug: safe_print("UTF-16 Big endian")
						unicodeDescription = unicodeDescription[2:]
						if len(unicodeDescription.split(" ")) == \
						   unicodeDescriptionLength - 1:
							safe_print("Warning (non-critical): '%s' "
									   "Unicode part starts with UTF-16 big "
									   "endian BOM, but actual contents seem "
									   "to be UTF-16 little endian" % 
									   tagData[:4])
							# fix fubar'd desc
							unicodeDescription = unicode(
								"\0".join(unicodeDescription.split(" ")), 
								"utf-16-le", errors="replace")
						else:
							unicodeDescription = unicode(unicodeDescription, 
														 "utf-16-be", 
														 errors="replace")
					elif unicodeDescription[:2] == "\xff\xfe":
						# UTF-16 Little Endian
						if debug: safe_print("UTF-16 Little endian")
						unicodeDescription = unicodeDescription[2:]
						if unicodeDescription[0] == "\0":
							safe_print("Warning (non-critical): '%s' "
									   "Unicode part starts with UTF-16 "
									   "little endian BOM, but actual "
									   "contents seem to be UTF-16 big "
									   "endian" % tagData[:4])
							# fix fubar'd desc
							unicodeDescription = unicode(unicodeDescription, 
														 "utf-16-be", 
														 errors="replace")
						else:
							unicodeDescription = unicode(unicodeDescription, 
														 "utf-16-le", 
														 errors="replace")
					else:
						if debug: safe_print("ASSUMED UTF-16 Big Endian")
						unicodeDescription = unicode(unicodeDescription, 
													 "utf-16-be", 
													 errors="replace")
				unicodeDescription = unicodeDescription.strip("\0\n\r ")
				if unicodeDescription:
					if unicodeDescription.find("\0") < 0:
						self.Unicode = unicodeDescription
					else:
						safe_print("Error (non-critical): could not decode "
								   "'%s' Unicode part - null byte(s) "
								   "encountered" % tagData[:4])
			except UnicodeDecodeError:
				safe_print("UnicodeDecodeError (non-critical): could not "
						   "decode '%s' Unicode part" % tagData[:4])
		else:
			charBytes = 1
		macOffset = unicodeOffset + 8 + unicodeDescriptionLength * charBytes
		macOffsetBackup = macOffset
		if tagData[macOffset:macOffset + 5] == "\0\0\0\0\0":
			macOffset += 5  # fix for fubar'd desc
		self.macScriptCode = 0
		if len(tagData) > macOffset + 2:
			self.macScriptCode = uInt16Number(tagData[macOffset:macOffset + 2])
			macDescriptionLength = ord(tagData[macOffset + 2])
			if macDescriptionLength:
				if macOffsetBackup < macOffset:
					safe_print("Warning (non-critical): '%s' Macintosh "
							   "part offset points to null bytes" % 
							   tagData[:4])
				try:
					macDescription = unicode(tagData[macOffset + 3:macOffset + 
											 3 + macDescriptionLength], 
											 "mac-" + 
											 encodings["mac"][self.macScriptCode], 
											 errors="replace").strip("\0\n\r ")
					if macDescription:
						self.Macintosh = macDescription
				except UnicodeDecodeError:
					safe_print("UnicodeDecodeError (non-critical): could not "
							   "decode '%s' Macintosh part" % tagData[:4])
	
	@Property
	def tagData():
		doc = """
		Return raw tag data.
		"""
	
		def fget(self):
			tagData = ["desc", "\0" * 4,
					   uInt32Number_tohex(len(self.ASCII) + 1),  # count of ASCII chars + 1
					   self.ASCII.encode("ASCII", "replace") + "\0",  # ASCII desc, \0 terminated
					   uInt32Number_tohex(self.get("unicodeLanguageCode", 0))]
			if "Unicode" in self:
				tagData.extend([uInt32Number_tohex(len(self.Unicode) + 1),  # count of Unicode chars + 1 (1 char = 2 byte)
								"\xfe\xff" + self.Unicode.encode("utf-16-be", "replace") + 
								"\0\0"])  # Unicode desc, \0\0 terminated
			else:
				tagData.append(uInt32Number_tohex(0))  # Unicode desc length = 0
			tagData.append(uInt16Number_tohex(self.get("macScriptCode", 0)))
			if "Macintosh" in self:
				macDescription = self.Macintosh[:66]
				tagData.extend([uInt8Number_tohex(len(macDescription) + 1),  # count of Macintosh chars + 1
								macDescription.encode("mac-" + 
													  encodings["mac"][self.get("macScriptCode", 0)], 
													  "replace") + "\0"])
			else:
				tagData.extend([uInt32Number_tohex(0),  # Mac desc length = 0
								"\0" * 67])
			return "".join(tagData)
		
		def fset(self, tagData):
			pass
		
		return locals()

	def __str__(self):
		return unicode(self).encode(sys.getdefaultencoding())

	def __unicode__(self):
		if sys.platform == "darwin":
			localizedTypes = ("Unicode", "Macintosh", "ASCII")
		else:
			localizedTypes = ("Unicode", "ASCII", "Macintosh")
		for localizedType in localizedTypes:
			if localizedType in self:
				value = self[localizedType]
				if not isinstance(value, unicode):
					# Even ASCII description may contain non-ASCII chars, so 
					# assume system encoding and convert to unicode, replacing 
					# unknown chars
					value = unicode(value, fs_enc, errors="replace")
				return value


def TextType(tagData, tagSignature):
	tag = Text(tagData[8:].rstrip("\0"))
	tag.tagData = tagData
	tag.tagSignature = tagSignature
	return tag


class VideoCardGammaType(ICCProfileTag, ADict):

	# Private tag
	# http://developer.apple.com/documentation/GraphicsImaging/Reference/ColorSync_Manager/Reference/reference.html#//apple_ref/doc/uid/TP30000259-CH3g-C001473

	def __init__(self, tagData, tagSignature):
		ICCProfileTag.__init__(self, tagData, tagSignature)
	
	def is_linear(self, r=True, g=True, b=True):
		r_points = []
		g_points = []
		b_points = []
		linear_points = []
		vcgt = self
		if "data" in vcgt: # table
			irange = range(0, vcgt['entryCount'])
			for i in irange:
				j = i * (255.0 / (vcgt['entryCount'] - 1))
				linear_points += [[j, j]]
				if r:
					n = float(vcgt['data'][0][i]) / (math.pow(256, vcgt['entrySize']) - 1) * 255
					r_points += [[j, n]]
				if g:
					n = float(vcgt['data'][1][i]) / (math.pow(256, vcgt['entrySize']) - 1) * 255
					g_points += [[j, n]]
				if b:
					n = float(vcgt['data'][2][i]) / (math.pow(256, vcgt['entrySize']) - 1) * 255
					b_points += [[j, n]]
		else: # formula
			irange = range(0, 256)
			step = 100.0 / 255.0
			for i in irange:
				# float2dec(v) fixes miniscule deviations in the calculated gamma
				linear_points += [[i, (i)]]
				if r:
					vmin = float2dec(vcgt["redMin"] * 255)
					v = float2dec(math.pow(step * i / 100.0, vcgt["redGamma"]))
					vmax = float2dec(vcgt["redMax"] * 255)
					r_points += [[i, float2dec(vmin + v * (vmax - vmin), 8)]]
				if g:
					vmin = float2dec(vcgt["greenMin"] * 255)
					v = float2dec(math.pow(step * i / 100.0, vcgt["greenGamma"]))
					vmax = float2dec(vcgt["greenMax"] * 255)
					g_points += [[i, float2dec(vmin + v * (vmax - vmin), 8)]]
				if b:
					vmin = float2dec(vcgt["blueMin"] * 255)
					v = float2dec(math.pow(step * i / 100.0, vcgt["blueGamma"]))
					vmax = float2dec(vcgt["blueMax"] * 255)
					b_points += [[i, float2dec(vmin + v * (vmax - vmin), 8)]]
		if ((r and g and b and r_points == g_points == b_points) or
			(r and g and r_points == g_points) or not (g or b)):
			points = r_points
		elif ((r and b and r_points == b_points) or
			  (g and b and g_points == b_points) or not (r or g)):
			points = b_points
		elif g:
			points = g_points
		return points == linear_points

	def printNormalizedValues(self, amount=None, digits=12):
		"""
		Normalizes and prints all values in the vcgt (range of 0.0...1.0).
		
		For a 256-entry table with linear values from 0 to 65535:
		#   REF            C1             C2             C3
		001 0.000000000000 0.000000000000 0.000000000000 0.000000000000
		002 0.003921568627 0.003921568627 0.003921568627 0.003921568627
		003 0.007843137255 0.007843137255 0.007843137255 0.007843137255
		...
		You can also specify the amount of values to print (where a value 
		lesser than the entry count will leave out intermediate values) 
		and the number of digits.
		
		"""
		if amount is None:
			if hasattr(self, 'entryCount'):
				amount = self.entryCount
			else:
				amount = 256  # common value
		values = self.getNormalizedValues(amount)
		entryCount = len(values)
		channels = len(values[0])
		header = ['REF']
		for k in xrange(channels):
			header.append('C' + str(k + 1))
		header = [title.ljust(digits + 2) for title in header]
		safe_print("#".ljust(len(str(amount)) + 1) + " ".join(header))
		for i, value in enumerate(values):
			formatted_values = [str(round(channel, 
								digits)).ljust(digits + 2, '0') for 
					  channel in value]
			safe_print(str(i + 1).rjust(len(str(amount)), '0'), 
					   str(round(i / float(entryCount - 1), 
								 digits)).ljust(digits + 2, '0'), 
					   " ".join(formatted_values))


class VideoCardGammaFormulaType(VideoCardGammaType):

	def __init__(self, tagData, tagSignature):
		VideoCardGammaType.__init__(self, tagData, tagSignature)
		data = tagData[12:]
		self.update({
			"redGamma": u16Fixed16Number(data[0:4]),
			"redMin": u16Fixed16Number(data[4:8]),
			"redMax": u16Fixed16Number(data[8:12]),
			"greenGamma": u16Fixed16Number(data[12:16]),
			"greenMin": u16Fixed16Number(data[16:20]),
			"greenMax": u16Fixed16Number(data[20:24]),
			"blueGamma": u16Fixed16Number(data[24:28]),
			"blueMin": u16Fixed16Number(data[28:32]),
			"blueMax": u16Fixed16Number(data[32:36])
		})
	
	def getNormalizedValues(self, amount=None):
		if amount is None:
			amount = 256  # common value
		step = 1.0 / float(amount - 1)
		rgb = AODict([("red", []), ("green", []), ("blue", [])])
		for i in xrange(0, amount):
			for key in rgb:
				rgb[key] += [float(self[key + "Min"]) + math.pow(step * i / 1.0, 
								float(self[key + "Gamma"])) * 
							 float(self[key + "Max"] - self[key + "Min"])]
		return zip(*rgb.values())
	
	def getTableType(self, entryCount=256, entrySize=2):
		"""
		Return gamma as table type.
		"""
		maxValue = math.pow(256, entrySize) - 1
		tagData = [self.tagData[:8], 
				   uInt32Number_tohex(0),  # type 0 = table
				   uInt16Number_tohex(3),  # channels
				   uInt16Number_tohex(entryCount),
				   uInt16Number_tohex(entrySize)]
		int2hex = {
			1: uInt8Number_tohex,
			2: uInt16Number_tohex,
			4: uInt32Number_tohex,
			8: uInt64Number_tohex
		}
		for key in ("red", "green", "blue"):
			for i in xrange(0, entryCount):
				vmin = float(self[key + "Min"])
				vmax = float(self[key + "Max"])
				gamma = float(self[key + "Gamma"])
				v = (vmin + 
					 math.pow(1.0 / (entryCount - 1) * i, gamma) * 
					 float(vmax - vmin))
				tagData.append(int2hex[entrySize](round(v * maxValue)))
		return VideoCardGammaTableType("".join(tagData), self.tagSignature)


class VideoCardGammaTableType(VideoCardGammaType):

	def __init__(self, tagData, tagSignature):
		VideoCardGammaType.__init__(self, tagData, tagSignature)
		if not tagData:
			self.update({"channels": 0,
						 "entryCount": 0,
						 "entrySize": 0,
						 "data": []})
			return
		data = tagData[12:]
		channels   = uInt16Number(data[0:2])
		entryCount = uInt16Number(data[2:4])
		entrySize  = uInt16Number(data[4:6])
		self.update({
			"channels": channels,
			"entryCount": entryCount,
			"entrySize": entrySize,
			"data": []
		})
		hex2int = {
			1: uInt8Number,
			2: uInt16Number,
			4: uInt32Number,
			8: uInt64Number
		}
		i = 0
		while i < channels:
			self.data.append([])
			j = 0
			while j < entryCount:
				index = 6 + i * entryCount * entrySize + j * entrySize
				self.data[i].append(hex2int[entrySize](data[index:index + 
															entrySize]))
				j = j + 1
			i = i + 1
	
	def getNormalizedValues(self, amount=None):
		if amount is None:
			amount = self.entryCount
		values = zip(*[[entry / 65535.0 for entry in channel] for channel in self.data])
		if amount <= self.entryCount:
			step = self.entryCount / float(amount - 1)
			all = values
			values = []
			for i, value in enumerate(all):
				if i == 0 or (i + 1) % step < 1 or i + 1 == self.entryCount:
					values += [value]
		return values
	
	def getFormulaType(self):
		"""
		Return formula representing gamma value at 50% input.
		"""
		maxValue = math.pow(256, self.entrySize) - 1
		tagData = [self.tagData[:8], 
				   uInt32Number_tohex(1)]  # type 1 = formula
		for channel in self.data:
			l = (len(channel) - 1) / 2.0
			floor = float(channel[int(math.floor(l))])
			ceil = float(channel[int(math.ceil(l))])
			vmin = channel[0] / maxValue
			vmax = channel[-1] / maxValue
			v = (vmin + ((floor + ceil) / 2.0) * (vmax - vmin)) / maxValue
			gamma = (math.log(v) / math.log(.5))
			print vmin, gamma, vmax
			tagData.append(u16Fixed16Number_tohex(gamma))
			tagData.append(u16Fixed16Number_tohex(vmin))
			tagData.append(u16Fixed16Number_tohex(vmax))
		return VideoCardGammaFormulaType("".join(tagData), self.tagSignature)
	
	def resize(self, length=128):
		data = [[], [], []]
		for i, channel in enumerate(self.data):
			for j in xrange(0, length):
				j *= (len(channel) - 1) / float(length - 1)
				if int(j) != j:
					floor = channel[int(math.floor(j))]
					ceil = channel[min(int(math.ceil(j)), len(channel) - 1)]
					interpolated = xrange(floor, ceil + 1)
					fraction = j - int(j)
					index = int(round(fraction * (ceil - floor)))
					v = interpolated[index]
				else:
					v = channel[int(j)]
				data[i].append(v)
		self.data = data
		self.entryCount = len(data[0])
	
	def resized(self, length=128):
		resized = self.__class__(self.tagData, self.tagSignature)
		resized.resize(length)
		return resized
	
	def smooth_cr(self, length=64):
		"""
		Smooth video LUT curves (Catmull-Rom).
		"""
		resized = self.resized(length)
		for i in xrange(0, len(self.data)):
			step = float(length - 1) / (len(self.data[i]) - 1)
			interpolation = CRInterpolation(resized.data[i])
			for j in xrange(0, len(self.data[i])):
				self.data[i][j] = int(round(interpolation(j * step)))
	
	def smooth_avg(self, passes=1, window=None):
		"""
		Smooth video LUT curves (moving average).
		
		passses   Number of passes
		window    Tuple or list containing weighting factors. Its length
		          determines the size of the window to use.
		          Defaults to (1.0, 1.0, 1.0)
		
		"""
		if not window or len(window) < 3 or len(window) % 2 != 1:
			window = (1.0, 1.0, 1.0)
		for x in xrange(0, passes):
			data = [[], [], []]
			for i, channel in enumerate(self.data):
				for j, v in enumerate(channel):
					tmpwindow = window
					while j > 0 and j < len(channel) - 1 and len(tmpwindow) >= 3:
						tl = (len(tmpwindow) - 1) / 2
						# print j, tl, tmpwindow
						if tl > 0 and j - tl >= 0 and j + tl <= len(channel) - 1:
							windowslice = channel[j - tl:j + tl + 1]
							windowsize = 0
							for k, weight in enumerate(tmpwindow):
								windowsize += float(weight) * windowslice[k]
							v = int(round(windowsize / sum(tmpwindow)))
							break
						else:
							tmpwindow = tmpwindow[1:-1]
					data[i].append(v)
			self.data = data
			self.entryCount = len(data[0])
	
	@Property
	def tagData():
		doc = """
		Return raw tag data.
		"""
	
		def fget(self):
			tagData = ["vcgt", "\0" * 4,
					   uInt32Number_tohex(0),  # type 0 = table
					   uInt16Number_tohex(len(self.data)),  # channels
					   uInt16Number_tohex(self.entryCount),
					   uInt16Number_tohex(self.entrySize)]
			int2hex = {
				1: uInt8Number_tohex,
				2: uInt16Number_tohex,
				4: uInt32Number_tohex,
				8: uInt64Number_tohex
			}
			for channel in self.data:
				for i in xrange(0, self.entryCount):
					tagData.append(int2hex[self.entrySize](channel[i]))
			return "".join(tagData)
		
		def fset(self, tagData):
			pass
		
		return locals()


class ViewingConditionsType(ICCProfileTag, ADict):

	def __init__(self, tagData, tagSignature):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		self.update({
			"illuminant": XYZNumber(tagData[8:20]),
			"surround": XYZNumber(tagData[20:32]),
			"illuminantType": Illuminant(tagData[32:36])
		})


class XYZNumber(AODict):

	"""
	Byte
	Offset Content Encoded as...
	0..3   CIE X   s15Fixed16Number
	4..7   CIE Y   s15Fixed16Number
	8..11  CIE Z   s15Fixed16Number
	"""

	def __init__(self, binaryString):
		AODict.__init__(self)
		self.X, self.Y, self.Z = [s15Fixed16Number(chunk) for chunk in 
								  (binaryString[:4], binaryString[4:8], 
								   binaryString[8:12])]
	
	def tohex(self):
		data = [s15Fixed16Number_tohex(n) for n in self.values()]
		return "".join(data)


class XYZType(ICCProfileTag, XYZNumber):

	def __init__(self, tagData="\0" * 20, tagSignature=None):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		XYZNumber.__init__(self, tagData[8:20])
	
	@Property
	def tagData():
		doc = """
		Return raw tag data.
		"""
	
		def fget(self):
			tagData = ["XYZ ", "\0" * 4]
			tagData += [self.tohex()]
			return "".join(tagData)
		
		def fset(self, tagData):
			pass
		
		return locals()


class chromaticAdaptionTag(colormath.Matrix3x3, s15Fixed16ArrayType):
	
	def __init__(self, tagData=None, tagSignature=None):
		ICCProfileTag.__init__(self, tagData, tagSignature)
		if tagData:
			data = tagData[8:]
			if data:
				matrix = []
				while data:
					if len(matrix) == 0 or len(matrix[-1]) == 3:
						matrix.append([])
					matrix[-1].append(s15Fixed16Number(data[0:4]))
					data = data[4:]
				self.update(matrix)
	
	@Property
	def tagData():
		doc = """
		Return raw tag data.
		"""
	
		def fget(self):
			tagData = ["sf32", "\0" * 4]
			for row in self:
				for column in row:
					tagData.append(s15Fixed16Number_tohex(column))
			return "".join(tagData)
		
		def fset(self, tagData):
			pass
		
		return locals()


tagSignature2Tag = {
	"chad": chromaticAdaptionTag
}

typeSignature2Type = {
	"chrm": ChromacityType,
	"curv": CurveType,
	"desc": TextDescriptionType,  # ICC v2
	"dict": DictType,  # ICC v2 + v4
	"dtim": DateTimeType,
	"meas": MeasurementType,
	"mluc": MultiLocalizedUnicodeType,  # ICC v4
	"sf32": s15Fixed16ArrayType,
	"sig ": SignatureType,
	"text": TextType,
	"vcgt": videoCardGamma,
	"view": ViewingConditionsType,
	"XYZ ": XYZType
}


class ICCProfileInvalidError(IOError):

	def __str__(self):
		return self.args[0]


class ICCProfile:

	"""
	Returns a new ICCProfile object. 
	
	Optionally initialized with a string containing binary profile data or 
	a filename, or a file-like object. Also if the 'load' keyword argument
	is False (default True), only the header will be read initially and
	loading of the tags will be deferred to when they are accessed the
	first time.
	
	"""

	def __init__(self, profile=None, load=True):
		self.ID = "\0" * 16
		self._data = ""
		self._file = None
		self._tags = AODict()
		self.fileName = None
		self.is_loaded = False
		self.size = 0
		
		if profile:
		
			data = None
			
			if type(profile) in (str, unicode):
				if profile.find("\0") < 0:
					# filename
					if not os.path.isfile(profile) and \
					   not os.path.sep in profile and \
					   not os.path.altsep in profile:
						for path in iccprofiles_home + filter(lambda x: 
							x not in iccprofiles_home, iccprofiles):
							if os.path.isdir(path):
								for path, dirs, files in os.walk(path):
									path = os.path.join(path, profile)
									if os.path.isfile(path):
										profile = path
										break
								if os.path.isfile(path):
									break
					profile = open(profile, "rb")
				else: # binary string
					data = profile
					self.is_loaded = True
			if not data: # file object
				self._file = profile
				self.fileName = self._file.name
				self._file.seek(0)
				data = self._file.read(128)
				self.close()
			
			if not data or len(data) < 128:
				raise ICCProfileInvalidError("Not enough data")
			
			if data[36:40] != "acsp":
				raise ICCProfileInvalidError("Profile signature mismatch - "
											 "expected 'acsp', found '" + 
											 data[36:40] + "'")
			
			header = data[:128]
			self.size = uInt32Number(header[0:4])
			self.preferredCMM = header[4:8].strip("\0\n\r ")
			minorrev_bugfixrev = binascii.hexlify(header[8:12][1])
			self.version = float(str(ord(header[8:12][0])) + "." + 
								 str(int("0x0" + minorrev_bugfixrev[0], 16)) + 
								 str(int("0x0" + minorrev_bugfixrev[1], 16)))
			self.profileClass = header[12:16].strip()
			self.colorSpace = header[16:20].strip()
			self.connectionColorSpace = header[20:24].strip()
			try:
				self.dateTime = dateTimeNumber(header[24:36])
			except ValueError:
				raise ICCProfileInvalidError("Profile creation date/time invalid")
			self.platform = header[40:44].strip("\0\n\r ")
			flags = uInt32Number(header[44:48])
			self.embedded = flags & 1 != 0
			self.independent = flags & 2 == 0
			deviceAttributes = uInt64Number(header[56:64])
			self.device = {
				"manufacturer": header[48:52].strip("\0\n\r "),
				"model": header[52:56].strip("\0\n\r "),
				"attributes": {
					"reflective":   deviceAttributes & 1 == 0,
					"glossy":       deviceAttributes & 2 == 0,
					"positive":     deviceAttributes & 4 == 0,
					"color":        deviceAttributes & 8 == 0
				}
			}
			self.intent = uInt32Number(header[64:68])
			self.illuminant = XYZNumber(header[68:80])
			self.creator = header[80:84].strip("\0\n\r ")
			if header[84:100] != "\0" * 16:
				self.ID = header[84:100]
			
			self._data = data[:self.size]
			
			if load:
				self.tags
		else:
			# Default to RGB display device profile
			self.preferredCMM = ""
			self.version = 2.4
			self.profileClass = "mntr"
			self.colorSpace = "RGB"
			self.connectionColorSpace = "XYZ"
			self.dateTime = datetime.datetime.now()
			self.platform = ""
			self.embedded = False
			self.independent = True
			self.device = {
				"manufacturer": "",
				"model": "",
				"attributes": {
					"reflective":   True,
					"glossy":       True,
					"positive":     True,
					"color":        True
				}
			}
			self.intent = 0
			self.illuminant = XYZNumber("\0\0\xf6\xd6\0\x01\0\0\0\0\xd3-")  # D50
			self.creator = ""
	
	def __del__(self):
		self.close()
	
	@property
	def data(self):
		"""
		Get raw binary profile data.
		
		This will re-assemble the various profile parts (header, 
		tag table and data) on-the-fly.
		
		"""
		# Assemble tag table and tag data
		tagCount = len(self.tags)
		tagTable = []
		tagTableSize = tagCount * 12
		tagsData = []
		tagsDataOffset = []
		tagDataOffset = 128 + 4 + tagTableSize
		for tagSignature in self.tags:
			tagData = self.tags[tagSignature].tagData
			tagDataSize = len(tagData)
			# Pad all data with binary zeros so it lies on 4-byte boundaries
			padding = int(math.ceil(tagDataSize / 4.0)) * 4 - tagDataSize
			tagData += "\0" * padding
			tagTable.append(tagSignature)
			if tagData in tagsData:
				tagTable.append(uInt32Number_tohex(tagsDataOffset[tagsData.index(tagData)]))
			else:
				tagTable.append(uInt32Number_tohex(tagDataOffset))
			tagTable.append(uInt32Number_tohex(tagDataSize))
			if not tagData in tagsData:
				tagsData.append(tagData)
				tagsDataOffset.append(tagDataOffset)
				tagDataOffset += tagDataSize + padding
		header = self.header(tagTableSize, len("".join(tagsData)))
		data = "".join([header, uInt32Number_tohex(tagCount), 
						"".join(tagTable), "".join(tagsData)])
		return data
	
	def header(self, tagTableSize, tagDataSize):
		"Profile Header"
		# Profile size: 128 bytes header + 4 bytes tag count + tag table + data
		header = [uInt32Number_tohex(128 + 4 + tagTableSize + tagDataSize),
				  self.preferredCMM[:4].ljust(4, " ") if self.preferredCMM else "\0" * 4,
				  # Next three lines are ICC version
				  chr(int(str(self.version).split(".")[0])),
				  binascii.unhexlify(("%.2f" % self.version).split(".")[1]),
				  "\0" * 2,
				  self.profileClass[:4].ljust(4, " "),
				  self.colorSpace[:4].ljust(4, " "),
				  self.connectionColorSpace[:4].ljust(4, " "),
				  dateTimeNumber_tohex(self.dateTime),
				  "acsp",
				  self.platform[:4].ljust(4, " ") if self.platform else "\0" * 4,]
		flags = 0
		if self.embedded:
			flags += 1
		if not self.independent:
			flags += 2
		header += [uInt32Number_tohex(flags),
				   self.device["manufacturer"][:4].ljust(4, " ") if self.device["manufacturer"] else "\0" * 4,
				   self.device["model"][:4].ljust(4, " ") if self.device["model"] else "\0" * 4]
		deviceAttributes = 0
		for name, bit in {"reflective": 1,
						  "glossy": 2,
						  "positive": 4,
						  "color": 8}.iteritems():
			if not self.device["attributes"][name]:
				deviceAttributes += bit
		header += [uInt64Number_tohex(deviceAttributes),
				   uInt32Number_tohex(self.intent),
				   self.illuminant.tohex(),
				   self.creator[:4].ljust(4, " ") if self.creator else "\0" * 4,
				   self.ID[:16].ljust(16, "\0"),
				   self._data[100:128] if len(self._data[100:128]) == 28 else "\0" * 28]
		return "".join(header)
	
	@property
	def tags(self):
		"Profile Tag Table"
		if not self._tags:
			self.load()
			if self._data and len(self._data) > 131:
				# tag table and tagged element data
				tagCount = uInt32Number(self._data[128:132])
				if debug: print "tagCount:", tagCount
				tagTable = self._data[132:132 + tagCount * 12]
				discard_len = 0
				tags = {}
				while tagTable:
					tag = tagTable[:12]
					if len(tag) < 12:
						raise ICCProfileInvalidError("Tag table is truncated")
					tagSignature = tag[:4]
					if debug: print "tagSignature:", tagSignature
					tagDataOffset = uInt32Number(tag[4:8])
					if debug: print "    tagDataOffset:", tagDataOffset
					tagDataSize = uInt32Number(tag[8:12])
					if debug: print "    tagDataSize:", tagDataSize
					if tagSignature in self._tags:
						safe_print("Error (non-critical): Tag '%s' already "
								   "encountered. Skipping..." % tagSignature)
					else:
						if (tagDataOffset, tagDataSize) in tags:
							if debug: print "    tagDataOffset and tagDataSize indicate shared tag"
							self._tags[tagSignature] = tags[(tagDataOffset, tagDataSize)]
						else:
							start = tagDataOffset - discard_len
							if debug: print "    tagData start:", start
							end = tagDataOffset - discard_len + tagDataSize
							if debug: print "    tagData end:", end
							tagData = self._data[start:end]
							if len(tagData) < tagDataSize:
								raise ICCProfileInvalidError("Tag data for tag %r (offet %i, size %i) is truncated" % (tagSignature,
																													   tagDataOffset,
																													   tagDataSize))
							##self._data = self._data[:128] + self._data[end:]
							##discard_len += tagDataOffset - 128 - discard_len + tagDataSize
							##if debug: print "    discard_len:", discard_len
							typeSignature = tagData[:4]
							if len(typeSignature) < 4:
								raise ICCProfileInvalidError("Tag type signature for tag %r (offet %i, size %i) is truncated" % (tagSignature,
																																 tagDataOffset,
																																 tagDataSize))
							if debug: print "    typeSignature:", typeSignature
							try:
								if tagSignature in tagSignature2Tag:
									tag = tagSignature2Tag[tagSignature](tagData, tagSignature)
								elif typeSignature in typeSignature2Type:
									tag = typeSignature2Type[typeSignature](tagData, tagSignature)
								else:
									tag = ICCProfileTag(tagData, tagSignature)
							except Exception, exception:
								raise ICCProfileInvalidError("Couldn't parse tag %r (type %r, offet %i, size %i): %r" % (tagSignature,
																														 typeSignature,
																														 tagDataOffset,
																														 tagDataSize,
																														 exception))
							self._tags[tagSignature] = tags[(tagDataOffset, tagDataSize)] = tag
					tagTable = tagTable[12:]
				self._data = self._data[:128]
		return self._tags
	
	def calculateID(self):
		"""
		Calculates, sets, and returns the profile's ID (checksum).
		
		Calling this function always recalculates the checksum on-the-fly, 
		in contrast to just accessing the ID property.
		
		The entire profile, based on the size field in the header, is used 
		to calculate the ID after the values in the Profile Flags field 
		(bytes 44 to 47), Rendering Intent field (bytes 64 to 67) and 
		Profile ID field (bytes 84 to 99) in the profile header have been 
		temporarily replaced with zeros.
		
		"""
		data = self.data[:44] + "\0\0\0\0" + self.data[48:64] + "\0\0\0\0" + \
			   self.data[68:84] + "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0" + \
			   self.data[100:]
		self.ID = md5(data).digest()
		return self.ID
	
	def close(self):
		"""
		Closes the associated file object (if any).
		"""
		if self._file and not self._file.closed:
			self._file.close()
	
	@staticmethod
	def from_edid(edid, iccv4=False, cat="Bradford"):
		""" Create an ICC Profile from EDID data and return it
		
		You may override the gamma from EDID by setting it to a list of curve
		values.
		
		"""
		profile = ICCProfile()
		monitor_name = edid.get("monitor_name",
								md5(edid.get("edid")).hexdigest())
		if iccv4:
			profile.version = 4.2
			profile.tags.desc = MultiLocalizedUnicodeType()
			profile.tags.desc.add_localized_string("en", "US", monitor_name)
			profile.tags.cprt = MultiLocalizedUnicodeType()
			profile.tags.cprt.add_localized_string("en", "US",
												   "Created from EDID")
			profile.tags.dmnd = MultiLocalizedUnicodeType()
			profile.tags.dmnd.add_localized_string("en", "US",
												   edid.get("manufacturer", ""))
			profile.tags.dmdd = MultiLocalizedUnicodeType()
			profile.tags.dmdd.add_localized_string("en", "US", monitor_name)
		else:
			profile.tags.desc = TextDescriptionType()
			profile.tags.desc.ASCII = monitor_name
			profile.tags.dmnd = TextDescriptionType()
			profile.tags.dmnd.ASCII = edid.get("manufacturer",
											   "").encode("ASCII", "replace")
			profile.tags.dmdd = TextDescriptionType()
			profile.tags.dmdd.ASCII = monitor_name
			profile.tags.cprt = TextType("text\0\0\0\0Created from EDID\0",
										 "cprt")
		white = colormath.xyY2XYZ(edid.get("white_x", 0.0),
								  edid.get("white_y", 0.0), 1.0)
		profile.tags.wtpt = XYZType()
		D50 = colormath.get_whitepoint("D50")
		if iccv4:
			# Set wtpt to D50 and store actual white -> D50 transform in chad
			(profile.tags.wtpt.X, profile.tags.wtpt.Y,
			 profile.tags.wtpt.Z) = D50
			profile.tags.chad = chromaticAdaptionTag()
			matrix = colormath.wp_adaption_matrix(white, D50, cat)
			profile.tags.chad.update(matrix)
		else:
			# Store actual white in wtpt
			(profile.tags.wtpt.X, profile.tags.wtpt.Y,
			 profile.tags.wtpt.Z) = white
		# Get chromaticities of primaries
		xy = {}
		for color in ("red", "green", "blue"):
			xy[color[0] + "x"] = edid.get(color + "_x", 0.0)
			xy[color[0] + "y"] = edid.get(color + "_y", 0.0)
		# Calculate RGB to XYZ matrix from chromaticities and white
		mtx = colormath.rgb_to_xyz_matrix(xy["rx"], xy["ry"],
										  xy["gx"], xy["gy"],
										  xy["bx"], xy["by"], white)
		rgb = {"r": (1.0, 0.0, 0.0),
			   "g": (0.0, 1.0, 0.0),
			   "b": (0.0, 0.0, 1.0)}
		for color in "rgb":
			# Calculate XYZ for primaries
			X, Y, Z = mtx * rgb[color]
			# Write XYZ and TRC tags (don't forget to adapt to D50)
			tagname = color + "XYZ"
			profile.tags[tagname] = XYZType()
			(profile.tags[tagname].X, profile.tags[tagname].Y,
			 profile.tags[tagname].Z) = colormath.adapt(X, Y, Z, white, D50, cat)
			tagname = color + "TRC"
			profile.tags[tagname] = CurveType()
			gamma = edid.get("gamma", 2.2)
			if not isinstance(gamma, (list, tuple)):
				gamma = [gamma]
			profile.tags[tagname].extend(gamma)
		profile.set_edid_metadata(edid)
		profile.tags.meta["OPENICC_automatic_generated"] = "1"
		profile.tags.meta["DATA_source"] = "edid"
		return profile
	
	def getCopyright(self):
		"""
		Return profile copyright.
		"""
		return unicode(self.tags.get("cprt", ""))
	
	def getDescription(self):
		"""
		Return profile description.
		"""
		return unicode(self.tags.get("desc", ""))
	
	def getDeviceManufacturerDescription(self):
		"""
		Return device manufacturer description.
		"""
		return unicode(self.tags.get("dmnd", ""))
	
	def getDeviceModelDescription(self):
		"""
		Return device model description.
		"""
		return unicode(self.tags.get("dmdd", ""))
	
	def getViewingConditionsDescription(self):
		"""
		Return viewing conditions description.
		"""
		return unicode(self.tags.get("vued", ""))
	
	def guess_cat(self):
		illuminant = self.illuminant.values()
		if "chad" in self.tags:
			return colormath.guess_cat(self.tags.chad, 
									   self.tags.chad.inverted() * illuminant, 
									   illuminant)
	
	def isSame(self, profile, force_calculation=False):
		"""
		Compare the ID of profiles.
		
		Returns a boolean indicating if the profiles have the same ID.
		
		profile can be a ICCProfile instance, a binary string
		containing profile data, a filename or a file object.
		
		"""
		if not isinstance(profile, self.__class__):
			profile = self.__class__(profile)
		if force_calculation or self.ID == "\0" * 16:
			self.calculateID()
		if force_calculation or profile.ID == "\0" * 16:
			profile.calculateID()
		return self.ID == profile.ID
	
	def load(self):
		"""
		Loads the profile from the file object.

		Normally, you don't need to call this method, since the ICCProfile 
		class automatically loads the profile when necessary (load does 
		nothing if the profile was passed in as a binary string).
		
		"""
		if not self.is_loaded and self._file:
			if self._file.closed:
				self._file = open(self._file.name, "rb")
				self._file.seek(len(self._data))
			self._data += self._file.read(self.size - len(self._data))
			self._file.close()
			self.is_loaded = True
	
	def read(self, profile):
		"""
		Read profile from binary string, filename or file object.
		Same as self.__init__(profile)
		"""
		self.__init__(profile)
	
	def set_edid_metadata(self, edid):
		"""
		Sets metadata from EDID
		
		Key names follow the examples provided by OpenICC Configuration 0.1 DRAFT 1
		http://www.oyranos.org/wiki/index.php?title=OpenICC_Configuration_0.1
		and the GNOME Color Manager metadata specification
		http://gitorious.org/colord/master/blobs/master/doc/metadata-spec.txt
		
		"""
		if not "meta" in self.tags:
			self.tags.meta = DictType()
		spec_prefixes = "EDID_,CMF_,DATA_"
		prefixes = (self.tags.meta.getvalue("prefix", "", None) or spec_prefixes).split(",")
		for prefix in spec_prefixes.split(","):
			if not prefix in prefixes:
				prefixes.append(prefix)
		# OpenICC keys
		self.tags.meta.update({"prefix": ",".join(prefixes),
							   "EDID_manufacturer": edid["manufacturer"],
							   "EDID_mnft": edid["manufacturer_id"],
							   "EDID_model": edid.get("monitor_name",
														  str(edid["product_id"])),
							   "EDID_serial": edid.get("serial_ascii",
														   str(edid["serial_32"])),
							   "EDID_date": "%0.4i-T%i" %
											(edid["year_of_manufacture"],
											 edid["week_of_manufacture"]),
							   "EDID_mnft_id": struct.unpack(">H",
															 edid["edid"][8:10])[0],
							   "EDID_model_id": edid["product_id"],
							   "EDID_redx": edid["red_x"],
							   "EDID_redy": edid["red_y"],
							   "EDID_greenx": edid["green_x"],
							   "EDID_greeny": edid["green_y"],
							   "EDID_bluex": edid["blue_x"],
							   "EDID_bluey": edid["blue_y"],
							   "EDID_whitex": edid["white_x"],
							   "EDID_whitey": edid["white_y"],
							   "EDID_gamma": edid["gamma"],
							   # GCM keys
							   "EDID_md5": edid["hash"],
							   "CMF_product": "dispcalGUI",
							   "CMF_binary": "dispcalGUI",
							   "CMF_version": version})
	
	def write(self, stream_or_filename=None):
		"""
		Write profile to stream.
		
		This will re-assemble the various profile parts (header, 
		tag table and data) on-the-fly.
		
		"""
		if not stream_or_filename:
			if self._file:
				if not self._file.closed:
					self.close()
				stream_or_filename = self.fileName
		if isinstance(stream_or_filename, basestring):
			stream = open(stream_or_filename, "wb")
		else:
			stream = stream_or_filename
		stream.write(self.data)
		if isinstance(stream_or_filename, basestring):
			stream.close()
