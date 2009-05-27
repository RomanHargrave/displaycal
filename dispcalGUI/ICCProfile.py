#!/usr/bin/env python
# -*- coding: utf-8 -*-

from decimal import Decimal
from hashlib import md5
from os import getenv, path
import struct
from sys import getfilesystemencoding, platform
from time import localtime, mktime, strftime
if platform == "win32":
	import win32api
	import win32gui
else:
	import subprocess as sp

from safe_print import safe_print

##################
#
# text encodings
#
##################

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

##########
#
# Tables
#
##########

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

####################
#
# Helper functions
#
####################

def get_display_profile(display_no = 0):
	""" Return ICC Profile for display n or None """
	profile = None
	if platform == "win32":
		display_name = win32api.EnumDisplayDevices(None, display_no).DeviceName
		dc = win32gui.CreateDC("DISPLAY", display_name, None)
		filename = win32api.GetICMProfile(dc)
		if filename:
			profile = ICCProfile(filename)
	else:
		if platform == "darwin":
			args = ['osascript', '-e', 'tell app "ColorSyncScripting"', '-e', 
					'set prof to location of (display profile of display %i)' % 
					(display_no + 1), '-e', 'try', '-e', 'POSIX path of prof', 
					'-e', 'end try', '-e', 'end tell']
			p = sp.Popen(args, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)
		else:
			# Linux - read up to 5,000,000 bytes of any X properties
			p1 = sp.Popen(["xprop", "-display", ":%i" % display_no, "-len", "5000000", 
						"-root"], stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)
			p = sp.Popen(["grep", "_ICC_PROFILE"], stdin=p1.stdout, 
						stdout=sp.PIPE, stderr=sp.PIPE)
		stdoutdata, stderrdata = [data.strip("\n") for data in p.communicate()]
		if stdoutdata:
			if platform == "darwin":
				filename = unicode(stdoutdata, "UTF-8")
				profile = ICCProfile(filename)
			else:
				stdoutdata = stdoutdata.split("=")[1].strip()
				bin = "".join([chr(int(part)) for part in stdoutdata.split(", ")])
				profile = ICCProfile(bin)
		elif stderrdata:
			raise IOError(stderrdata)
	return profile

#######################
#
# Basic numeric types
#
#######################

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
	Y, m, d, H, M, S = [uInt16Number(chunk) for chunk in (binaryString[:2], binaryString[2:4], binaryString[4:6], binaryString[6:8], binaryString[8:10], binaryString[10:12])]
	return Y, m, d, H, M, S

def s15Fixed16Number(binaryString):
	return Decimal(str(struct.unpack(">i", binaryString)[0])) / 65536

def u16Fixed16Number(binaryString):
	return Decimal(str(struct.unpack(">I", binaryString)[0])) / 65536

def u8Fixed8Number(binaryString):
	return Decimal(str(struct.unpack(">H", binaryString)[0])) / 256

def uInt16Number(binaryString):
	return struct.unpack(">H", binaryString)[0]

def uInt32Number(binaryString):
	return struct.unpack(">I", binaryString)[0]

def uInt64Number(binaryString):
	return struct.unpack(">Q", binaryString)[0]

def uInt8Number(binaryString):
	return struct.unpack(">H", "\0" + binaryString)[0]

##############
#
# Dict class
#
##############

class Dict(dict):
	def __init__(self, dictionary = None):
		if dictionary:
			self.update(dictionary)
	def __getattr__(self, name):
		return self[name]
	def __setattr__(self, name, value):
		self[name] = value

#########################
#
# Custom helper classes
#
#########################

class Colorant(Dict):
	def __init__(self, binaryString):
		self.type = uInt32Number(binaryString)
		self.channels = colorants[self.type].channels
		self.description = colorants[self.type].description

class Geometry(Dict):
	def __init__(self, binaryString):
		self.type = uInt32Number(binaryString)
		self.description = geometry[self.type]

class IlluminantType(Dict):
	def __init__(self, binaryString):
		self.type = uInt32Number(binaryString)
		self.description = illuminants[self.type]

class Observer(Dict):
	def __init__(self, binaryString):
		self.type = uInt32Number(binaryString)
		self.description = observers[self.type]

###############
#
# ICC classes
#
###############

class ChromacityType(Dict):
	def __init__(self, tagData):
		deviceChannelsCount = uInt16Number(tagData[8:10])
		colorant = uInt16Number(tagData[10:12])
		if colorant in colorants:
			colorant = colorants[colorant]
		channels = tagData[12:]
		self.colorant = colorant
		self.channels = []
		while channels:
			self.channels.append((u16Fixed16Number(channels[:4]), u16Fixed16Number(channels[4:8])))
			channels = channels[8:]

class CurveType(list):
	def __init__(self, tagData):
		curveEntriesCount = uInt32Number(tagData[8:12])
		curveEntries = tagData[12:]
		while curveEntries:
			self.append(uInt16Number(curveEntries[:2]))
			curveEntries = curveEntries[2:]

class DateTimeType(list):
	def __init__(self, tagData):
		self += dateTimeNumber(tagData[8:20])
	
class MeasurementType(Dict):
	def __init__(self, tagData):
		self.update({
			"observer": Observer(tagData[8:12]),
			"backing": XYZNumber(tagData[12:24]),
			"geometry": Geometry(tagData[24:28]),
			"flare": u16Fixed16Number(tagData[28:32]),
			"illuminantType": IlluminantType(tagData[32:36])
		})

class MultiLocalizedUnicodeType(Dict): # ICC v4
	def __init__(self, tagData):
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
				self[recordLanguageCode] = Dict()
			self[recordLanguageCode][recordCountryCode] = unicode(tagData[recordOffset:recordOffset + recordLength], "utf-16-be", "replace")
			records = records[recordSize:]
	def __str__(self):
		"""
		Return tag as string.
		TO-DO: Needs some work re locales
		(currently if en-UK or en-US is not found, simply the first entry is returned)
		"""
		if "en" in self:
			for countryCode in ("UK", "US"):
				if countryCode in self["en"]:
					return self["en"][countryCode]
		return self.values()[0].values()[0]

class SignatureType(str):
	def __init__(self, text):
		pass
	# def __repr__(self):
		# return repr(self[8:12].strip("\0\n\r "))
	# def __str__(self):
		# return str(self[8:12].strip("\0\n\r "))

class TextDescriptionType(Dict): # ICC v2
	def __init__(self, tagData, tagSignature):
		ASCIIDescriptionLength = uInt32Number(tagData[8:12])
		if ASCIIDescriptionLength:
			ASCIIDescription = tagData[12:12 + ASCIIDescriptionLength].strip("\0\n\r ")
			if ASCIIDescription: self.ASCII = unicode(ASCIIDescription, getfilesystemencoding(), errors="replace") # even ASCII description may contain non-ASCII chars, so assume system encoding and convert to unicode, replacing unknown chars
		unicodeOffset = 12 + ASCIIDescriptionLength
		unicodeLanguageCode = uInt32Number(tagData[unicodeOffset:unicodeOffset + 4])
		unicodeDescriptionLength = uInt32Number(tagData[unicodeOffset + 4:unicodeOffset + 8])
		if unicodeDescriptionLength:
			if tagData[unicodeOffset + 8 + unicodeDescriptionLength:unicodeOffset + 8 + unicodeDescriptionLength + 2] == "\0\0":
				safe_print("Warning (non-critical): '" + tagSignature + "' tag Unicode part seems to be a single-byte string (double-byte string expected)")
				charBytes = 1 # fix for fubar'd desc tag
			else:
				charBytes = 2
			unicodeDescription = tagData[unicodeOffset + 8:unicodeOffset + 8 + (unicodeDescriptionLength) * charBytes]
			try:
				if charBytes == 1:
					unicodeDescription = unicode(unicodeDescription, errors="replace")
				else:
					if unicodeDescription[:2] == "\xfe\xff": # UTF-16 Big Endian
						unicodeDescription = unicodeDescription[2:]
						if len(unicodeDescription.split(" ")) == unicodeDescriptionLength - 1:
							safe_print("Warning (non-critical): '" + tagSignature + "' tag Unicode part starts with UTF-16 big endian BOM, but actual contents seem to be UTF-16 little endian")
							unicodeDescription = unicode("\0".join(unicodeDescription.split(" ")), "utf-16-le", errors="replace") # fix for fubar'd desc tag
						else:
							unicodeDescription = unicode(unicodeDescription, "utf-16-be", errors="replace")
					elif unicodeDescription[:2] == "\xff\xfe": # UTF-16 Little Endian
						unicodeDescription = unicodeDescription[2:]
						if unicodeDescription[0] == "\0":
							safe_print("Warning (non-critical): '" + tagSignature + "' tag Unicode part starts with UTF-16 little endian BOM, but actual contents seem to be UTF-16 big endian")
							unicodeDescription = unicode(unicodeDescription, "utf-16-be", errors="replace") # fix for fubar'd desc tag
						else:
							unicodeDescription = unicode(unicodeDescription, "utf-16-le", errors="replace")
					else:
						unicodeDescription = unicode(unicodeDescription, "utf-16-be", errors="replace")
				unicodeDescription = unicodeDescription.strip("\0\n\r ")
				if unicodeDescription:
					if unicodeDescription.find("\0") < 0: self.Unicode = unicodeDescription
					else:
						safe_print("Error (non-critical): could not decode '" + tagSignature + "' tag Unicode part - null byte(s) encountered")
						#self.Unicode = unicodeDescription
			except UnicodeDecodeError:
				safe_print("UnicodeDecodeError (non-critical): could not decode '" + tagSignature + "' tag Unicode part")
				unicodeDescription = None
		else: charBytes = 1
		macOffset = unicodeOffset + 8 + unicodeDescriptionLength * charBytes
		macOffsetBackup = macOffset
		if tagData[macOffset:macOffset + 5] == "\0\0\0\0\0":
			macOffset += 5 # fix for fubar'd desc tag
		if len(tagData) > macOffset + 2:
			macScriptCode = uInt16Number(tagData[macOffset:macOffset + 2])
			macDescriptionLength = ord(tagData[macOffset + 2])
			if macDescriptionLength:
				if macOffsetBackup < macOffset:
					safe_print("Warning (non-critical): '" + tagSignature + "' tag Macintosh part offset points to null bytes")
				try:
					macDescription = unicode(tagData[macOffset + 3:macOffset + 3 + macDescriptionLength], "mac-" + encodings["mac"][macScriptCode], errors="replace").strip("\0\n\r ")
					if macDescription: self.Macintosh = macDescription
				except UnicodeDecodeError:
					safe_print("UnicodeDecodeError (non-critical): could not decode '" + tagSignature + "' tag Macintosh part")
					macDescription = None
	def __str__(self):
		for localizedType in ("ASCII", "Macintosh", "Unicode"):
			if localizedType in self:
				return self[localizedType]

class TextType(str):
	def __init__(self, text):
		pass
	# def __repr__(self):
		# return repr(self[8:].strip("\0\n\r "))
	# def __str__(self):
		# return str(self[8:].strip("\0\n\r "))

class VideoCardGammaType(Dict):
	def __init__(self, tagData):
		reserved = uInt32Number(tagData[4:8])
		videoCardGamma = tagData[8:]
		tagType = uInt32Number(videoCardGamma[0:4])
		if tagType == 0: # table
			videoCardGammaTable = videoCardGamma[4:]
			channels   = uInt16Number(videoCardGammaTable[0:2])
			entryCount = uInt16Number(videoCardGammaTable[2:4])
			entrySize  = uInt16Number(videoCardGammaTable[4:6])
			data = videoCardGammaTable[6:]
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
					index = i * entryCount * entrySize + j * entrySize
					if entrySize == 1:
						self.data[i].append(uInt8Number(data[index:index + entrySize]))
					elif entrySize == 2:
						self.data[i].append(uInt16Number(data[index:index + entrySize]))
					elif entrySize == 4:
						self.data[i].append(uInt32Number(data[index:index + entrySize]))
					elif entrySize == 8:
						self.data[i].append(uInt64Number(data[index:index + entrySize]))
					j = j + 1
				i = i + 1
	def printNormalizedValues(self, amount = None, digits = 12):
		"""
		Normalizes all values in the vcgt to a range of 0.0...1.0 and prints them, e.g.
		for a 256-entry table with linear values from 0 to 65535:
		#   REF            C1             C2             C3
		001 0.000000000000 0.000000000000 0.000000000000 0.000000000000
		002 0.003921568627 0.003921568627 0.003921568627 0.003921568627
		003 0.007843137255 0.007843137255 0.007843137255 0.007843137255
		...
		You can also specify the amount of values to print (where a value 
		lesser than the entry count will leave out intermediate values) 
		and the number of digits.
		"""
		if type(amount) != int:
			amount = self.entryCount
		modulo = 256 / float(amount - 1)
		i = 0
		j = 0
		while i < self.entryCount:
			if i == 0:
				k = 0
				header = ['REF']
				while k < self.channels:
					k = k + 1
					header.append('C' + str(k))
				header = [title.ljust(digits + 2) for title in header]
				safe_print("#".ljust(len(str(amount)) + 1) + " ".join(header))
			if i == 0 or (i + 1) % modulo < 1 or i + 1 == self.entryCount:
				j = j + 1
				values = [str(round(channel[i] / 65535.0, digits)).ljust(digits + 2, '0') for channel in self.data]
				safe_print(str(j).rjust(len(str(amount)), '0'), str(round(i / float(self.entryCount - 1), digits)).ljust(digits + 2, '0'), " ".join(values))
			i = i + 1

class ViewingConditionsType(Dict):
	def __init__(self, tagData):
		self.update({
			"illuminant": XYZNumber(tagData[8:20]),
			"surround": XYZNumber(tagData[20:32]),
			"illuminantType": IlluminantType(tagData[32:36])
		})

class XYZNumber(Dict):
	"""
	Byte
	Offset Content Encoded as...
	0..3   CIE X   s15Fixed16Number
	4..7   CIE Y   s15Fixed16Number
	8..11  CIE Z   s15Fixed16Number
	"""
	def __init__(self, binaryString):
		self.X, self.Y, self.Z = [s15Fixed16Number(chunk) for chunk in (binaryString[:4], binaryString[4:8], binaryString[8:12])]

class XYZType(XYZNumber):
	def __init__(self, tagData):
		XYZNumber.__init__(self, tagData[8:20])

class ICCProfileInvalidError(IOError):
	def __str__(self):
		return self.args[0]

#####################
#
# ICC profile class
#
#####################

class ICCProfile:
	"""
	Returns a new ICCProfile object, optionally initialized with a string 
	(binary or filename), or a file object.
	"""
	
	def __init__(self, binaryStringOrFileNameOrFileObject = None):
		self.ID = None
		self._data = None
		self._fileObject = None
		self._tags = None
		self.fileName = None
		self.size = 0
		
		if binaryStringOrFileNameOrFileObject:
		
			data = None
			
			if type(binaryStringOrFileNameOrFileObject) in (str, unicode):
				if binaryStringOrFileNameOrFileObject.find("\0") < 0: # filename
					if not path.exists(binaryStringOrFileNameOrFileObject):
						if platform == "win32" and binaryStringOrFileNameOrFileObject.find("\\") < 0:
							binaryStringOrFileNameOrFileObject = getenv("SYSTEMROOT") + "\\system32\\spool\\drivers\\color\\" + binaryStringOrFileNameOrFileObject
					binaryStringOrFileNameOrFileObject = open(binaryStringOrFileNameOrFileObject, "rb")
				else: # binary string
					data = binaryStringOrFileNameOrFileObject
			if not data: # file object
				self._fileObject = binaryStringOrFileNameOrFileObject
				self.fileName = self._fileObject.name
				self._fileObject.seek(0)
				data = self._fileObject.read(128)
			
			if not data or len(data) < 128:
				raise ICCProfileInvalidError("Not enough data")
			
			if data[36:40] != "acsp":
				raise ICCProfileInvalidError("Profile file signature mismatch - expected 'acsp', found '" + data[36:40] + "'")
			
			header = data[:128]
			self.size = uInt32Number(header[0:4])
			self.preferredCMM = header[4:8].strip("\0\n\r ")
			self.version = Decimal(str(ord(header[8:12][0])) + "." + str(ord(header[8:12][1])))
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
			if header[84:100] != "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0":
				self.ID = header[84:100]
			
			self._data = data[:self.size]
	
	def __del__(self):
		self.close()
	
	def __getData(self):
		self.load()
		return self._data
	data = property(__getData, doc = "Profile data")
	
	def __getTags(self):
		if not self._tags:
			# tag table and tagged element data
			self._tags = Dict()
			self._rawtags = Dict()
			tagCount = uInt32Number(self.data[128:132])
			tagTable = self.data[132:132 + tagCount * 12]
			while tagTable:
				tag = tagTable[:12]
				tagSignature = tag[:4]
				tagDataOffset = uInt32Number(tag[4:8])
				tagDataSize = uInt32Number(tag[8:12])
				tagData = self.data[tagDataOffset:tagDataOffset + tagDataSize]
				if tagSignature in self._tags:
					safe_print("Error (non-critical): Tag '" + tagSignature + "' already encountered. Skipping...")
				else:
					self._tagSignature = tagSignature
					self._rawtags[tagSignature] = tagData
					if tagData[:4] == "chrm":
						self._tags[tagSignature] = ChromacityType(tagData)
					elif tagData[:4] == "curv":
						self._tags[tagSignature] = CurveType(tagData)
					elif tagData[:4] == "desc": # ICC v2
						self._tags[tagSignature] = TextDescriptionType(tagData, tagSignature)
					elif tagData[:4] == "dtim":
						self._tags[tagSignature] = DateTimeType(tagData)
					elif tagData[:4] == "meas":
						self._tags[tagSignature] = MeasurementType(tagData)
					elif tagData[:4] == "mluc": # ICC v4
						self._tags[tagSignature] = MultiLocalizedUnicodeType(tagData)
					elif tagData[:4] == "sig ":
						self._tags[tagSignature] = SignatureType(tagData[8:12].strip("\0\n\r "))
					elif tagData[:4] == "text":
						self._tags[tagSignature] = TextType(tagData[8:].strip("\0\n\r "))
					elif tagData[:4] == "vcgt":
						# private tag
						# http://developer.apple.com/documentation/GraphicsImaging/Reference/ColorSync_Manager/Reference/reference.html#//apple_ref/doc/uid/TP30000259-CH3g-C001473
						self._tags[tagSignature] = VideoCardGammaType(tagData)
					elif tagData[:4] == "view":
						self._tags[tagSignature] = ViewingConditionsType(tagData)
					elif tagData[:4] == "XYZ ":
						if tagSignature == "lumi":
							self._tags[tagSignature] = XYZType(tagData).Y
						else:
							self._tags[tagSignature] = XYZType(tagData)
					else:
						self._tags[tagSignature] = tagData
				tagTable = tagTable[12:]
			self._tagSignature = None
		return self._tags
	tags = property(__getTags, doc = "Profile Tag Table")
	
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
		data = self.data[:44] + "\0\0\0\0" + self.data[48:64] + "\0\0\0\0" + self.data[68:84] + "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0" + self.data[100:self.size]
		self.ID = md5(data).digest()
		return self.ID
	
	def close(self):
		"""
		Closes the associated file object (if any).
		"""
		if self._fileObject:
			self._fileObject.close()
	
	def getCopyright(self):
		"""
		Return profile copyright.
		"""
		return self.tags.cprt.__str__()
	
	def getDescription(self):
		"""
		Return profile description.
		"""
		return self.tags.desc.__str__()
	
	def getDeviceManufacturerDescription(self):
		"""
		Return device manufacturer description.
		"""
		return self.tags.dmnd.__str__()
	
	def getDeviceModelDescription(self):
		"""
		Return device model description.
		"""
		return self.tags.dmdd.__str__()
	
	def getViewingConditionsDescription(self):
		"""
		Return viewing conditions description.
		"""
		return self.tags.vued.__str__()
	
	def isSame(self, profile):
		"""
		Returns True if the passed in profile has the same ID 
		or False otherwise.
		
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
		Loads the profile from the file object (load does nothing if the 
		profile was passed in as a binary string). Normally, you don't need 
		to call this method, since the ICCProfile class automatically loads 
		the profile when necessary.
		"""
		if (not self._data or len(self._data) < self.size) and self._fileObject:
			if self._fileObject.closed:
				self._fileObject = open(self._fileObject.name, "rb")
				self._fileObject.seek(len(self._data))
			self._data += self._fileObject.read(self.size - len(self._data))
			self._fileObject.close()
	
	def open(self, path):
		"""
		Open profile from file.
		"""
		self.__init__(open(path, "rb"))
	
	def read(self, binaryStringOrFileNameOrFileObject):
		"""
		Read profile from binary string, filename or file object.
		"""
		self.__init__(binaryStringOrFileNameOrFileObject)
