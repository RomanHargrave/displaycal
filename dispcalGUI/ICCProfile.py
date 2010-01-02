#!/usr/bin/env python
# -*- coding: utf-8 -*-

from decimal import Decimal
from hashlib import md5
import locale
import math
import os
import struct
import sys
from time import localtime, mktime, strftime
from UserString import UserString
if sys.platform != "win32":
	import subprocess as sp

if sys.platform == "win32":
	try:
		import win32api
		import win32gui
	except ImportError:
		pass

from defaultpaths import iccprofiles, iccprofiles_home
from ordereddict import OrderedDict
from safe_print import safe_print

if sys.platform == "darwin":
	enc = "UTF-8"
else:
	enc = sys.stdout.encoding or locale.getpreferredencoding() or \
		  sys.getdefaultencoding()
fs_enc = sys.getfilesystemencoding() or enc

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


def get_display_profile(display_no=0):
	""" Return ICC Profile for display n or None """
	profile = None
	if sys.platform == "win32":
		if not "win32api" in sys.modules or not "win32gui" in sys.modules:
			raise ImportError('pywin32 not available')
		display_name = win32api.EnumDisplayDevices(None, display_no).DeviceName
		dc = win32gui.CreateDC("DISPLAY", display_name, None)
		filename = win32api.GetICMProfile(dc)
		if filename:
			profile = ICCProfile(filename)
	else:
		if sys.platform == "darwin":
			args = ['osascript', '-e', 'tell app "ColorSyncScripting"', '-e', 
					'set prof to location of (display profile of display %i)' % 
					(display_no + 1), '-e', 'try', '-e', 'POSIX path of prof', 
					'-e', 'end try', '-e', 'end tell']
			tgt_proc = sp.Popen(args, stdin=sp.PIPE, stdout=sp.PIPE, 
								stderr=sp.PIPE)
		else:
			# Linux - read up to 8 MB of any X properties
			src_proc = sp.Popen(["xprop", "-display", ":0", "-len", 
								 "8388608", "-root"], 
								stdin=sp.PIPE, 
								stdout=sp.PIPE, stderr=sp.PIPE)
			tgt_proc = sp.Popen(["grep", "-P", r"^_ICC_PROFILE%s\D*=" % 
								 ("" if display_no == 0 else "_%s" % 
								  display_no)], 
								stdin=src_proc.stdout, 
								stdout=sp.PIPE, stderr=sp.PIPE)
		stdout, stderr = [data.strip("\n") for data in tgt_proc.communicate()]
		if stdout:
			if sys.platform == "darwin":
				filename = unicode(stdout, "UTF-8")
				profile = ICCProfile(filename)
			else:
				stdout = stdout.split("=")[1].strip()
				bin = "".join([chr(int(part)) for part in stdout.split(", ")])
				profile = ICCProfile(bin)
		elif stderr:
			raise IOError(stderr)
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
	return Y, m, d, H, M, S


def s15Fixed16Number(binaryString):
	return Decimal(str(struct.unpack(">i", binaryString)[0])) / 65536


def s15Fixed16Number_tohex(num):
	return struct.pack(">i", num * 65536)


def u16Fixed16Number(binaryString):
	return Decimal(str(struct.unpack(">I", binaryString)[0])) / 65536


def u16Fixed16Number_tohex(num):
	return struct.pack(">I", num * 65536)


def u8Fixed8Number(binaryString):
	return Decimal(str(struct.unpack(">H", binaryString)[0])) / 256


def u8Fixed8Number_tohex(num):
	return struct.pack(">H", num * 256)


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


def videoCardGamma(tagData):
	reserved = uInt32Number(tagData[4:8])
	tagType = uInt32Number(tagData[8:12])
	if tagType == 0: # table
		return VideoCardGammaTableType(tagData)
	elif tagType == 1: # formula
		return VideoCardGammaFormulaType(tagData)


class ADict(dict):

	"""
	Convenience class for dictionary key access via attributes.
	
	Instead of writing aodict[key], you can also write aodict.key
	
	"""

	def __init__(self, *args, **kwargs):
		dict.__init__(self, *args, **kwargs)

	def __getattr__(self, name):
		try:
			return object.__getattribute__(self, name)
		except AttributeError:
			if name in self:
				return self[name]
			else:
				raise

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

	def __init__(self, tagData):
		self.tagData = tagData

	def __setattr__(self, name, value):
		if not isinstance(self, dict) or name in ("_keys", "tagData"):
			object.__setattr__(self, name, value)
		else:
			self[name] = value


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

	def __init__(self, tagData):
		ICCProfileTag.__init__(self, tagData)
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

	def __init__(self, tagData):
		ICCProfileTag.__init__(self, tagData)
		curveEntriesCount = uInt32Number(tagData[8:12])
		curveEntries = tagData[12:]
		while curveEntries:
			self.append(uInt16Number(curveEntries[:2]))
			curveEntries = curveEntries[2:]


class DateTimeType(ICCProfileTag, list):

	def __init__(self, tagData):
		ICCProfileTag.__init__(self, tagData)
		self += dateTimeNumber(tagData[8:20])


class MeasurementType(ICCProfileTag, ADict):

	def __init__(self, tagData):
		ICCProfileTag.__init__(self, tagData)
		self.update({
			"observer": Observer(tagData[8:12]),
			"backing": XYZNumber(tagData[12:24]),
			"geometry": Geometry(tagData[24:28]),
			"flare": u16Fixed16Number(tagData[28:32]),
			"illuminantType": Illuminant(tagData[32:36])
		})


class MultiLocalizedUnicodeType(ICCProfileTag, AODict): # ICC v4

	def __init__(self, tagData):
		ICCProfileTag.__init__(self, tagData)
		AODict.__init__(self)
		recordsCount = uInt32Number(tagData[8:12])
		recordSize = uInt32Number(tagData[12:16]) # 12
		records = tagData[16:16 + recordSize * recordsCount]
		while records:
			record = records[:recordSize]
			recordLanguageCode = record[:2]
			recordCountryCode = record[2:4]
			recordLength = uInt32Number(record[4:8])
			recordOffset = uInt32Number(record[8:12])
			if recordLanguageCode not in self:
				self[recordLanguageCode] = AODict()
			self[recordLanguageCode][recordCountryCode] = unicode(
				tagData[recordOffset:recordOffset + recordLength], 
				"utf-16-be", "replace")
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
		return self.values()[0].values()[0]


class SignatureType(ICCProfileTag, UserString):

	def __init__(self, tagData):
		ICCProfileTag.__init__(self, tagData)
		UserString.__init__(self, tagData[8:12].rstrip("\0"))


class TextDescriptionType(ICCProfileTag, ADict): # ICC v2

	def __init__(self, tagData):
		ICCProfileTag.__init__(self, tagData)
		ASCIIDescriptionLength = uInt32Number(tagData[8:12])
		if ASCIIDescriptionLength:
			ASCIIDescription = tagData[12:12 + 
									   ASCIIDescriptionLength].strip("\0\n\r ")
			if ASCIIDescription:
				self.ASCII = ASCIIDescription
		unicodeOffset = 12 + ASCIIDescriptionLength
		unicodeLanguageCode = uInt32Number(
							  tagData[unicodeOffset:unicodeOffset + 4])
		unicodeDescriptionLength = uInt32Number(tagData[unicodeOffset + 
														4:unicodeOffset + 8])
		if unicodeDescriptionLength:
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
		if len(tagData) > macOffset + 2:
			macScriptCode = uInt16Number(tagData[macOffset:macOffset + 2])
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
											 encodings["mac"][macScriptCode], 
											 errors="replace").strip("\0\n\r ")
					if macDescription:
						self.Macintosh = macDescription
				except UnicodeDecodeError:
					safe_print("UnicodeDecodeError (non-critical): could not "
							   "decode '%s' Macintosh part" % tagData[:4])

	def __str__(self):
		return unicode(self).encode(sys.getdefaultencoding())

	def __unicode__(self):
		for localizedType in ("Unicode", "Macintosh", "ASCII"):
			if localizedType in self:
				value = self[localizedType]
				if not isinstance(value, unicode):
					# Even ASCII description may contain non-ASCII chars, so 
					# assume system encoding and convert to unicode, replacing 
					# unknown chars
					value = unicode(value, fs_enc, errors="replace")
				return value


class TextType(ICCProfileTag, UserString):

	def __init__(self, tagData):
		ICCProfileTag.__init__(self, tagData)
		UserString.__init__(self, tagData[8:].rstrip("\0"))


class VideoCardGammaType(ICCProfileTag, ADict):

	# Private tag
	# http://developer.apple.com/documentation/GraphicsImaging/Reference/ColorSync_Manager/Reference/reference.html#//apple_ref/doc/uid/TP30000259-CH3g-C001473

	def __init__(self, tagData):
		ICCProfileTag.__init__(self, tagData)

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

	def __init__(self, tagData):
		VideoCardGammaType.__init__(self, tagData)
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
							 float(self[key + "Max"])]
		return zip(*rgb.values())


class VideoCardGammaTableType(VideoCardGammaType):

	def __init__(self, tagData):
		VideoCardGammaType.__init__(self, tagData)
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
		i = 0
		while i < channels:
			self.data.append([])
			j = 0
			while j < entryCount:
				index = 6 + i * entryCount * entrySize + j * entrySize
				if entrySize == 1:
					self.data[i].append(uInt8Number(data[index:index + 
														 entrySize]))
				elif entrySize == 2:
					self.data[i].append(uInt16Number(data[index:index + 
														  entrySize]))
				elif entrySize == 4:
					self.data[i].append(uInt32Number(data[index:index + 
														  entrySize]))
				elif entrySize == 8:
					self.data[i].append(uInt64Number(data[index:index + 
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


class ViewingConditionsType(ICCProfileTag, ADict):

	def __init__(self, tagData):
		ICCProfileTag.__init__(self, tagData)
		self.update({
			"illuminant": XYZNumber(tagData[8:20]),
			"surround": XYZNumber(tagData[20:32]),
			"illuminantType": Illuminant(tagData[32:36])
		})


class XYZNumber(ADict):

	"""
	Byte
	Offset Content Encoded as...
	0..3   CIE X   s15Fixed16Number
	4..7   CIE Y   s15Fixed16Number
	8..11  CIE Z   s15Fixed16Number
	"""

	def __init__(self, binaryString):
		self.X, self.Y, self.Z = [s15Fixed16Number(chunk) for chunk in 
								  (binaryString[:4], binaryString[4:8], 
								   binaryString[8:12])]


class XYZType(ICCProfileTag, XYZNumber):

	def __init__(self, tagData):
		ICCProfileTag.__init__(self, tagData)
		XYZNumber.__init__(self, tagData[8:20])


typeSignature2Type = {
	"chrm": ChromacityType,
	"curv": CurveType,
	"desc": TextDescriptionType,  # ICC v2
	"dtim": DateTimeType,
	"meas": MeasurementType,
	"mluc": MultiLocalizedUnicodeType,  # ICC v4
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
	a filename, or a file-like object.
	
	"""

	def __init__(self, profile=None):
		self.ID = "\0" * 16
		self._data = None
		self._file = None
		self._tags = AODict()
		self.fileName = None
		self.size = self._size = 0
		
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
			if not data: # file object
				self._file = profile
				self.fileName = self._file.name
				self._file.seek(0)
				data = self._file.read(128)
			
			if not data or len(data) < 128:
				raise ICCProfileInvalidError("Not enough data")
			
			if data[36:40] != "acsp":
				raise ICCProfileInvalidError("Profile signature mismatch - "
											 "expected 'acsp', found '" + 
											 data[36:40] + "'")
			
			header = data[:128]
			self.size = self._size = uInt32Number(header[0:4])
			self.preferredCMM = header[4:8].strip("\0\n\r ")
			self.version = Decimal(str(ord(header[8:12][0])) + "." + 
								   str(ord(header[8:12][1])))
			self.profileClass = header[12:16].strip()
			self.colorSpace = header[16:20].strip()
			self.connectionColorSpace = header[20:24].strip()
			try:
				self.dateTime = dateTimeNumber(header[24:36])
			except Exception:
				self.dateTime = 0
			self.platform = header[40:44].strip("\0\n\r ")
			flags = uInt16Number(header[44:48][:2])
			self.embedded = flags | 1 == flags
			self.independent = flags | 2 != flags
			deviceAttributes = uInt32Number(header[56:64][:4])
			self.device = {
				"manufacturer": header[48:52].strip("\0\n\r "),
				"model": header[52:56].strip("\0\n\r "),
				"attributes": {
					"reflective":   deviceAttributes | 1 != deviceAttributes,
					"glossy":       deviceAttributes | 2 != deviceAttributes,
					"positive":     deviceAttributes | 4 != deviceAttributes,
					"color":        deviceAttributes | 8 != deviceAttributes
				}
			}
			self.intent = uInt32Number(header[64:68])
			self.illuminant = XYZNumber(header[68:80])
			self.creator = header[80:84].strip("\0\n\r ")
			if header[84:100] != "\0" * 16:
				self.ID = header[84:100]
			
			self._data = data[:self.size]
	
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
			tagsDataOffset.append(tagDataOffset)
			tagTable.append(uInt32Number_tohex(tagDataSize))
			if not tagData in tagsData:
				tagsData.append(tagData)
				tagDataOffset += tagDataSize + padding
		header = uInt32Number_tohex(128 + 4 + tagTableSize + 
									len("".join(tagsData))) + self._data[4:84] + self.ID + self._data[100:128]
		data = "".join([header, uInt32Number_tohex(tagCount), 
						"".join(tagTable), "".join(tagsData)])
		return data
	
	@property
	def tags(self):
		"Profile Tag Table"
		if not self._tags:
			self.load()
			# tag table and tagged element data
			tagCount = uInt32Number(self._data[128:132])
			tagTable = self._data[132:132 + tagCount * 12]
			discard_len = 0
			tags = {}
			while tagTable:
				tag = tagTable[:12]
				tagSignature = tag[:4]
				tagDataOffset = uInt32Number(tag[4:8])
				tagDataSize = uInt32Number(tag[8:12])
				if tagSignature in self._tags:
					safe_print("Error (non-critical): Tag '%s' already "
							   "encountered. Skipping..." % tagSignature)
				else:
					if (tagDataOffset, tagDataSize) in tags:
						self._tags[tagSignature] = tags[(tagDataOffset, tagDataSize)]
					else:
						start = tagDataOffset - discard_len
						end = tagDataOffset - discard_len + tagDataSize
						tagData = self._data[start:end]
						self._data = self._data[:128] + self._data[end:]
						discard_len += tagDataOffset - 128 - discard_len + tagDataSize
						typeSignature = tagData[:4]
						if typeSignature in typeSignature2Type:
							tagData = typeSignature2Type[typeSignature](tagData)
						self._tags[tagSignature] = tags[(tagDataOffset, tagDataSize)] = tagData
				tagTable = tagTable[12:]
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
			   self.data[100:self.size]
		self.ID = md5(data).digest()
		return self.ID
	
	def close(self):
		"""
		Closes the associated file object (if any).
		"""
		if self._file and not self._file.closed:
			self._file.close()
	
	def getCopyright(self):
		"""
		Return profile copyright.
		"""
		return unicode(self.tags.cprt)
	
	def getDescription(self):
		"""
		Return profile description.
		"""
		return unicode(self.tags.desc)
	
	def getDeviceManufacturerDescription(self):
		"""
		Return device manufacturer description.
		"""
		return unicode(self.tags.dmnd)
	
	def getDeviceModelDescription(self):
		"""
		Return device model description.
		"""
		return unicode(self.tags.dmdd)
	
	def getViewingConditionsDescription(self):
		"""
		Return viewing conditions description.
		"""
		return unicode(self.tags.vued)
	
	def isSame(self, profile):
		"""
		Compare the ID of profiles.
		
		Returns a boolean indicating if the profiles have the same ID.
		
		profile can be a ICCProfile instance, a binary string
		containing profile data, a filename or a file object.
		
		"""
		if not isinstance(profile, self.__class__):
			profile = self.__class__(profile)
		if not self.ID:
			self.calculateID()
		if not profile.ID:
			profile.calculateID()
		return self.ID == profile.ID
	
	def load(self):
		"""
		Loads the profile from the file object.

		Normally, you don't need to call this method, since the ICCProfile 
		class automatically loads the profile when necessary (load does 
		nothing if the profile was passed in as a binary string).
		
		"""
		if (not self._data or len(self._data) < self._size) and self._file:
			if self._file.closed:
				self._file = open(self._file.name, "rb")
				self._file.seek(len(self._data))
			self._data += self._file.read(self._size - len(self._data))
			self._file.close()
	
	def read(self, profile):
		"""
		Read profile from binary string, filename or file object.
		Same as self.__init__(profile)
		"""
		self.__init__(profile)
	
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
