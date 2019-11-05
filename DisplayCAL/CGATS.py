# -*- coding: utf-8 -*-

"""
Simple CGATS file parser class

Copyright (C) 2008 Florian Hoech
"""

from __future__ import with_statement
import math, os, re, sys

import colormath
from log import safe_print
from options import debug, verbose
from util_io import GzipFileProper, StringIOu as StringIO
from util_str import safe_unicode


def get_device_value_labels(color_rep=None):
	return filter(bool, map(lambda v: v[1] if not color_rep or v[0] == color_rep
									  else False,
							{"CMYK": ("CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"),
							 "RGB": ("RGB_R", "RGB_G", "RGB_B")}.iteritems()))


def rpad(value, width):
	"""
	If value isn't a number, return a quoted string representation.
	If value is greater or equal than 1e+16, return string in scientific
	notation.
	Otherwise, return string in decimal notation right-padded to given width
	(using trailing zeros).
	
	"""
	strval = str(value)
	if not isinstance(value, (int, float, long, complex)):
		# Return quoted string representation
		# Also need to escape single quote -> double quote
		return '"%s"' % strval.replace('"', '""')
	if value < 1e+16:
		i = strval.find(".")
		if i > -1:
			if i < width - 1:
				# Avoid scientific notation by formatting to decimal
				fmt = "%%%i.%if" % (width, width - i - 1)
				strval = fmt % value
			else:
				strval = str(int(round(value)))
	return strval


def sort_RGB_gray_to_top(a, b):
	if a[0] == a[1] == a[2]:
		if b[0] == b[1] == b[2]:
			return 0
		return -1
	else:
		return 0


def sort_RGB_to_top_factory(i1, i2, i3, i4):
	def sort_RGB_to_top(a, b):
		if a[i1] == a[i2] and 0 <= a[i3] < a[i4]:
			if b[i1] == b[i2] and 0 <= b[i3] < b[i4]:
				return 0
			return -1
		else:
			return 0
	return sort_RGB_to_top


def sort_RGB_white_to_top(a, b):
	sum1, sum2 = sum(a[:3]), sum(b[:3])
	if sum1 == 300:
		return -1
	else:
		return 0


def sort_by_HSI(a, b):
	a = list(colormath.RGB2HSI(*a[:3]))
	b = list(colormath.RGB2HSI(*b[:3]))
	a[0] = round(math.degrees(a[0]))
	b[0] = round(math.degrees(b[0]))
	if a > b:
		return 1
	elif a < b:
		return -1
	else:
		return 0


def sort_by_HSL(a, b):
	a = list(colormath.RGB2HSL(*a[:3]))
	b = list(colormath.RGB2HSL(*b[:3]))
	a[0] = round(math.degrees(a[0]))
	b[0] = round(math.degrees(b[0]))
	if a > b:
		return 1
	elif a < b:
		return -1
	else:
		return 0


def sort_by_HSV(a, b):
	a = list(colormath.RGB2HSV(*a[:3]))
	b = list(colormath.RGB2HSV(*b[:3]))
	a[0] = round(math.degrees(a[0]))
	b[0] = round(math.degrees(b[0]))
	if a > b:
		return 1
	elif a < b:
		return -1
	else:
		return 0


def sort_by_RGB(a, b):
	if a[:3] > b[:3]:
		return 1
	elif a[:3] < b[:3]:
		return -1
	else:
		return 0


def sort_by_BGR(a, b):
	if a[:3][::-1] > b[:3][::-1]:
		return 1
	elif a[:3] == b[:3]:
		return 0
	else:
		return -1


def sort_by_RGB_sum(a, b):
	sum1, sum2 = sum(a[:3]), sum(b[:3])
	if sum1 > sum2:
		return 1
	elif sum1 < sum2:
		return -1
	else:
		return 0


def sort_by_RGB_pow_sum(a, b):
	sum1, sum2 = sum(v ** 2.2 for v in a[:3]), sum(v ** 2.2 for v in b[:3])
	if sum1 > sum2:
		return 1
	elif sum1 < sum2:
		return -1
	else:
		return 0


def sort_by_L(a, b):
	Lab1 = colormath.XYZ2Lab(*a[3:])
	Lab2 = colormath.XYZ2Lab(*b[3:])
	if Lab1[0] > Lab2[0]:
		return 1
	elif Lab1[0] < Lab2[0]:
		return -1
	else:
		return 0


def sort_by_luma_factory(RY, GY, BY, gamma=1):
	def sort_by_luma(a, b):
		a = RY * a[0] ** gamma + GY * a[1] ** gamma + BY * a[2] ** gamma
		b = RY * b[0] ** gamma + GY * b[1] ** gamma + BY * b[2] ** gamma
		if a > b:
			return 1
		elif a < b:
			return -1
		else:
			return 0
	return sort_by_luma


sort_by_rec709_luma = sort_by_luma_factory(0.2126, 0.7152, 0.0722)


class CGATSError(Exception):
	pass


class CGATSInvalidError(CGATSError, IOError):
	pass


class CGATSInvalidOperationError(CGATSError):
	pass


class CGATSKeyError(CGATSError, KeyError):
	pass


class CGATSTypeError(CGATSError, TypeError):
	pass


class CGATSValueError(CGATSError, ValueError):
	pass


class CGATS(dict):

	"""
	CGATS structure.
	
	CGATS files are treated mostly as 'soup', so only basic checking is
	in place.
	
	"""
	
	datetime = None
	filename = None
	fileName = property(lambda self: self.filename,
						lambda self, filename: setattr(self, "filename", filename))
	key = None
	_lvl = 0
	_modified = False
	mtime = None
	parent = None
	root = None
	type = 'ROOT'
	vmaxlen = 0
	
	def __init__(self, cgats=None, normalize_fields=False, file_identifier="CTI3",
				 emit_keywords=False, strict=False):
		"""
		Return a CGATS instance.
		
		cgats can be a path, a string holding CGATS data, or a file object.
		
		If normalize_fields evaluates to True, convert all KEYWORDs and all 
		fields in DATA_FORMAT to UPPERCASE and SampleId or SampleName to
		SAMPLE_ID or SAMPLE_NAME respectively
		
		file_identifier is used as fallback if no file identifier is present
		
		"""
		
		self.normalize_fields = normalize_fields
		self.file_identifier = file_identifier.strip()
		self.emit_keywords = emit_keywords
		self.root = self
		self._keys = []
		
		if cgats:
			
			if isinstance(cgats, list):
				raw_lines = cgats
			else:
				if isinstance(cgats, basestring):
					if cgats.find('\n') < 0 and cgats.find('\r') < 0:
						# assume filename
						cgats = open(cgats, 'rU')
						self.filename = cgats.name
					else:
						# assume text
						cgats = StringIO(cgats)
				elif isinstance(cgats, file):
					self.filename = cgats.name
				elif not isinstance(cgats, StringIO):
					raise CGATSInvalidError('Unsupported type: %s' % type(cgats))
				if self.filename not in ('', None):
					self.mtime = os.stat(self.filename).st_mtime
				cgats.seek(0)
				raw_lines = cgats.readlines()
				cgats.close()

			context = self

			for raw_line in raw_lines:
				# Replace 1.#IND00 with NaN
				raw_line = raw_line.replace("1.#IND00", "NaN")
				# strip control chars and leading/trailing whitespace
				line = re.sub('[^\x09\x20-\x7E\x80-\xFF]', '', 
								raw_line.strip())
				if '#' in line or '"' in line:
					# Deal with comments and quotes
					quoted = False
					values = []
					token_start = 0
					end = len(line) - 1
					for i, char in enumerate(line):
						if char == '"':
							if quoted is False:
								if not line[token_start:i]:
									token_start = i
								quoted = True
							else:
								quoted = False
						if (quoted is False and char in '# \t') or i == end:
							if i == end:
								i += 1
							value = line[token_start:i]
							if value:
								if value[0] == '"' == value[-1]:
									# Unquote
									value = value[1:-1]
								# Need to unescape double quote -> single quote
								values.append(value.replace('""', '"'))
							if char == '#':
								# Strip comment
								line = line[:i].strip()
								break
							elif char in ' \t':
								token_start = i + 1
				else:
					values = line.split()
				if line[:6] == 'BEGIN_':
					key = line[6:]
					if key in context:
						# Start new CGATS
						new = len(self)
						self[new] = CGATS()
						self[new].key = ''
						self[new].parent = self
						self[new].root = self.root
						self[new].type = ''
						context = self[new]
				if line == 'BEGIN_DATA_FORMAT':
					context['DATA_FORMAT'] = CGATS()
					context['DATA_FORMAT'].key = 'DATA_FORMAT'
					context['DATA_FORMAT'].parent = context
					context['DATA_FORMAT'].root = self
					context['DATA_FORMAT'].type = 'DATA_FORMAT'
					context = context['DATA_FORMAT']
				elif line == 'END_DATA_FORMAT':
					context = context.parent
				elif line == 'BEGIN_DATA':
					context['DATA'] = CGATS()
					context['DATA'].key = 'DATA'
					context['DATA'].parent = context
					context['DATA'].root = self
					context['DATA'].type = 'DATA'
					context = context['DATA']
				elif line == 'END_DATA':
					context = context.parent
				elif line[:6] == 'BEGIN_':
					key = line[6:]
					context[key] = CGATS()
					context[key].key = key
					context[key].parent = context
					context[key].root = self
					context[key].type = 'SECTION'
					context = context[key]
				elif line[:4] == 'END_':
					context = context.parent
				elif context.type in ('DATA_FORMAT', 'DATA'):
					if len(values):
						context = context.add_data(values)
				elif context.type == 'SECTION':
					context = context.add_data(line)
				elif len(values) > 1:
					if values[0] == 'Date:':
						context.datetime = line
					else:
						if len(values) == 2 and not '"' in values[0]:
							key, value = values
							if value != None:
								context = context.add_data({key: value.strip('"')})
							else:
								context = context.add_data({key: ''})
						elif strict:
							raise CGATSInvalidError('Malformed %s file: %s' %
													(context.parent and
													 context.type or "CGATS",
													 self.filename or self))
				elif values and values[0] not in ('Comment:', 'Date:') and \
				     len(line) >= 3 and not re.search("[^ 0-9A-Za-z/.]", line):
					context = self.add_data(line)
			if 0 in self and self[0].get("NORMALIZED_TO_Y_100") == "NO":
				# Always normalize to Y = 100
				reprstr = (self.filename or "<%s.%s instance at 0x%016x>" %
											(self.__module__,
											 self.__class__.__name__, id(self)))
				if self[0].normalize_to_y_100():
					safe_print("Normalized to Y = 100:", reprstr)
				else:
					safe_print("Warning: Could not normalize to Y = 100:",
							   reprstr)
			self.setmodified(False)

	def __delattr__(self, name):
		del self[name]
		self.setmodified()
	
	def __delitem__(self, name):
		if (self.type not in ('DATA', 'DATA_FORMAT', 'KEYWORDS', 'SECTION') and
			name in self._keys):
			self._keys.remove(name)
		dict.__delitem__(self, name)
		self.setmodified()

	def __getattr__(self, name):
		if name in self:
			return self[name]
		else:
			raise AttributeError(name)

	def __getitem__(self, name):
		if name == -1:
			return self.get(len(self) - 1)
		elif name in ('NUMBER_OF_FIELDS', 'NUMBER_OF_SETS'):
			return getattr(self, name)
		elif name in self:
			if str(name).upper() in ('INDEX', 'SAMPLE_ID', 'SAMPLEID'):
				if type(self.get(name)) not in (int, float):
					return self.get(name)
				if str(name).upper() == 'INDEX':
					return self.key
				if type(self.get(name)) == float:
					return 1.0 / (self.NUMBER_OF_SETS - 1) * self.key
				return self.key + 1
			return self.get(name)
		raise CGATSKeyError(name)
	
	def get(self, name, default=None):
		if name == -1:
			return dict.get(self, len(self) - 1, default)
		elif name in ('NUMBER_OF_FIELDS', 'NUMBER_OF_SETS'):
			return getattr(self, name, default)
		else:
			return dict.get(self, name, default)
	
	def get_colorants(self):
		color_rep = (self.queryv1("COLOR_REP") or "").split("_")
		if len(color_rep) == 2:
			query = {}
			colorants = []
			for i in xrange(len(color_rep[0])):
				for j, channelname in enumerate(color_rep[0]):
					query["_".join([color_rep[0], channelname])] = {i: 100}.get(j, 0)
				colorants.append(self.queryi1(query))
			return colorants

	def get_descriptor(self, localized=True):
		"""
		Return CGATS description as unicode, based on metadata
		
		If 'localized' is True (default), include localized technology
		description for CCSS files.
		
		"""
		desc = self.queryv1("DESCRIPTOR")
		is_ccss = self.get(0, self).type == "CCSS"
		if not desc or desc == "Not specified" or is_ccss:
			if not is_ccss:
				desc = self.queryv1("INSTRUMENT")
				if desc:
					display = self.queryv1("DISPLAY")
					if display:
						desc += " & " + display
			else:
				tech = self.queryv1("TECHNOLOGY")
				if tech:
					if (desc and desc != "Not specified" and
						desc != "CCSS for " + tech):
						display = desc
					else:
						display = self.queryv1("DISPLAY")
					if localized:
						import localization as lang
						tech = safe_unicode(tech, "UTF-8")
						tech = lang.getstr(u"display.tech." + tech, default=tech)
						if display:
							# Localized tech will be unicode always, need to
							# make sure display is as well
							display = safe_unicode(display, "UTF-8")
					if display:
						tech += " (%s)" % display
				desc = tech
		if not desc and self.filename:
			# Filesystem encoding can be different than UTF-8 (depending on
			# platform), by default safe_unicode will use FS enc
			desc = safe_unicode(os.path.splitext(os.path.basename(self.filename))[0])
		else:
			desc = safe_unicode(desc or "", "UTF-8")
		return desc

	def __setattr__(self, name, value):
		if name in ('_keys', '_lvl'):
			object.__setattr__(self, name, value)
		elif name == 'modified':
			self.setmodified(value)
		elif name in ('datetime', 'filename', 'fileName', 'file_identifier', 'key', 
					  'mtime', 'normalize_fields', 'parent', 'root', 'type', 
					  'vmaxlen', 'emit_keywords'):
			object.__setattr__(self, name, value)
			self.setmodified()
		else:
			self[name] = value
	
	def __setitem__(self, name, value):
		if (self.type not in ('DATA', 'DATA_FORMAT', 'KEYWORDS', 'SECTION') and
			not name in self):
			self._keys.append(name)
		dict.__setitem__(self, name, value)
		self.setmodified()
	
	def setmodified(self, modified=True):
		""" Set 'modified' state on the 'root' object. """
		if self.root and self.root._modified != modified:
			object.__setattr__(self.root, '_modified', modified)
	
	def __str__(self):
		result = []
		lvl = self.root._lvl
		self.root._lvl += 1
		data = None
		if self.type == 'SAMPLE':
			result.append(' '.join(rpad(self[item], 
										self.parent.vmaxlen + 
										(1 if self[item] < 0 else 0))
								   for item in 
								   self.parent.parent['DATA_FORMAT'].values()))
		elif self.type == 'DATA':
			data = self
		elif self.type == 'DATA_FORMAT':
			result.append(' '.join(self.values()))
		else:
			if self.datetime:
				result.append(self.datetime)
			if self.type == 'SECTION':
				result.append('BEGIN_' + self.key)
			elif self.parent and self.parent.type == 'ROOT':
				result.append(self.type.ljust(7))	# Make sure CGATS file 
												# identifiers are always 
												# a minimum of 7 characters
				result.append('')
			if self.type in ('DATA', 'DATA_FORMAT', 'KEYWORDS', 'SECTION'):
				iterable = self
			else:
				iterable = self._keys
			for key in iterable:
				value = self[key]
				if key == 'DATA':
					data = value
				elif type(value) in (float, int, str, unicode):
					if key not in ('NUMBER_OF_FIELDS', 'NUMBER_OF_SETS'):
						if type(key) == int:
							result.append(str(value))
						else:
							if 'KEYWORDS' in self and \
								key in self['KEYWORDS'].values():
								if self.emit_keywords:
									result.append('KEYWORD "%s"' % key)
							if isinstance(value, basestring):
								# Need to escape single quote -> double quote
								value = value.replace('"', '""')
							result.append('%s "%s"' % (key, value))
				elif key not in ('DATA_FORMAT', 'KEYWORDS'):
					if (value.type == 'SECTION' and result[-1:] and 
						result[-1:][0] != ''):
						result.append('')
					result.append(str(value))
			if self.type == 'SECTION':
				result.append('END_' + self.key)
			if self.type == 'SECTION' or data:
				result.append('')
		if data and data.parent['DATA_FORMAT']:
			if 'KEYWORDS' in data.parent and self.emit_keywords:
				for item in data.parent['DATA_FORMAT'].values():
					if item in data.parent['KEYWORDS'].values():
						result.append('KEYWORD "%s"' % item)
			result.append('NUMBER_OF_FIELDS %s' % len(data.parent['DATA_FORMAT']))
			result.append('BEGIN_DATA_FORMAT')
			result.append(' '.join(data.parent['DATA_FORMAT'].values()))
			result.append('END_DATA_FORMAT')
			result.append('')
			result.append('NUMBER_OF_SETS %s' % (len(data)))
			result.append('BEGIN_DATA')
			for key in data:
				result.append(' '.join([rpad(data[key][item], 
											 data.vmaxlen + 
											 (1 if data[key][item] < 0 else 0)) 
										for item in 
										data.parent['DATA_FORMAT'].values()]))
			result.append('END_DATA')
		if (self.parent and self.parent.type or
			self.type) == 'ROOT' and result and result[-1] != '' and lvl == 0:
			# Add empty line at end if not yet present
			result.append('')
		self.root._lvl -= 1
		return '\n'.join(result)

	def add_keyword(self, keyword, value=None):
		""" Add a keyword to the list of keyword values. """
		if self.type in ('DATA', 'DATA_FORMAT', 'KEYWORDS', 'SECTION'):
			context = self.parent
		elif self.type == 'SAMPLE':
			context = self.parent.parent
		else:
			context = self
		if not 'KEYWORDS' in context:
			context['KEYWORDS'] = CGATS()
			context['KEYWORDS'].key = 'KEYWORDS'
			context['KEYWORDS'].parent = context
			context['KEYWORDS'].root = self.root
			context['KEYWORDS'].type = 'KEYWORDS'
		if not keyword in context['KEYWORDS'].values():
			newkey = len(context['KEYWORDS'])
			while newkey in context['KEYWORDS']:
				newkey += 1
			context['KEYWORDS'][newkey] = keyword
		if value != None:
			context[keyword] = value
	
	def add_section(self, key, value):
		self[key] = CGATS()
		self[key].key = key
		self[key].parent = self
		self[key].root = self
		self[key].type = 'SECTION'
		self[key].add_data(value)

	def remove_keyword(self, keyword, remove_value=True):
		""" Remove a keyword from the list of keyword values. """
		if self.type in ('DATA', 'DATA_FORMAT', 'KEYWORDS', 'SECTION'):
			context = self.parent
		elif self.type == 'SAMPLE':
			context = self.parent.parent
		else:
			context = self
		for key in context['KEYWORDS'].keys():
			if context['KEYWORDS'][key] == keyword:
				del context['KEYWORDS'][key]
		if remove_value:
			del context[keyword]
	
	def insert(self, key=None, data=None):
		""" Insert data at index key. Also see add_data method. """
		self.add_data(data, key)
	
	def append(self, data):
		""" Append data. Also see add_data method. """
		self.add_data(data)
	
	def get_data(self, field_names=None):
		data = self.queryv1("DATA")
		if not data:
			return False
		elif field_names:
			data = data.queryi(field_names)
		return data
	
	def get_RGB_XYZ_values(self):
		field_names = ("RGB_R", "RGB_G", "RGB_B", "XYZ_X", "XYZ_Y", "XYZ_Z")
		data = self.get_data(field_names)
		if not data:
			return False, False
		valueslist = []
		for key, item in data.iteritems():
			values = []
			for field_name in field_names:
				values.append(item[field_name])
			valueslist.append(values)
		return data, valueslist
	
	def set_RGB_XYZ_values(self, valueslist):
		field_names = ("RGB_R", "RGB_G", "RGB_B", "XYZ_X", "XYZ_Y", "XYZ_Z")
		for i, values in enumerate(valueslist):
			for j, field_name in enumerate(field_names):
				self[i][field_name] = values[j]
		return True
	
	def checkerboard(self, sort1=sort_by_L, sort2=sort_RGB_white_to_top,
					 split_grays=False, shift=False):
		data, valueslist = self.get_RGB_XYZ_values()
		if not valueslist:
			return False
		numvalues = len(valueslist)
		if sort1:
			valueslist.sort(sort1)
		if sort2:
			valueslist.sort(sort2)
		gray = []
		if split_grays:
			# Split values into gray and color. First gray in a consecutive
			# sequence of two or more grays will be added to color list,
			# following grays will be added to gray list.
			color = []
			prev_i = -1
			prev_values = []
			added = {prev_i: True}  # Keep track of entries we have added
			for i, values in enumerate(valueslist):
				if debug:
					safe_print(i + 1, "IN", values[:3])
				is_gray = values[:3] == [values[:3][0]] * 3
				prev = color
				cur = color
				if is_gray:
					if not prev_values:
						if debug:
							safe_print("WARNING - skipping gray because no prev")
					elif values[:3] == prev_values[:3]:
						# Same gray as prev value
						prev = color
						cur = gray
						if prev_i not in added:
							if debug:
								safe_print("INFO - appending prev %s to color "
										   "because prev was same gray but got "
										   "skipped" % prev_values[:3])
						if debug:
							safe_print("INFO - appending cur to gray because "
									   "prev %s was same gray" %
									   prev_values[:3])
					elif prev_values[:3] == [prev_values[:3][0]] * 3:
						# Prev value was different gray
						prev = gray
						cur = gray
						if prev_i not in added:
							if debug:
								safe_print("INFO - appending prev %s to gray "
										   "because prev was different gray "
										   "but got skipped" % prev_values[:3])
						if debug:
							safe_print("INFO - appending cur to gray because "
									   "prev %s was different gray" %
									   prev_values[:3])
					elif i < numvalues - 1:
						if debug:
							safe_print("WARNING - skipping gray because "
									   "prev %s was not gray" %
									   prev_values[:3])
					else:
						# Last
						if debug:
							safe_print("INFO - appending cur to color "
									   "because prev %s was not gray but "
									   "cur is last" % prev_values[:3])
				if not is_gray or cur is gray or i == numvalues - 1:
					if prev_i not in added:
						if debug and prev is cur is color:
							safe_print("INFO - appending prev %s to color because "
									   "prev got skipped" % prev_values[:3])
						prev.append(prev_values)
						added[prev_i] = True
					if debug and not is_gray and cur is color:
						safe_print("INFO - appending cur to color")
					cur.append(values)
					added[i] = True
				prev_i = i
				prev_values = values
			if (len(color) == 2 and color[0][:3] == [0, 0, 0] and
				color[1][:3] == [100, 100, 100]):
				if debug:
					safe_print("INFO - appending color to gray because color "
							   "is only black and white")
				gray.extend(color)
				color = []
				if sort1:
					gray.sort(sort1)
				if sort2:
					gray.sort(sort2)
			if debug:
				for i, values in enumerate(gray):
					safe_print("%4i" % (i + 1), "GRAY", ("%8.4f " * 3) %
							   tuple(values[:3]))
				for i, values in enumerate(color):
					safe_print("%4i" % (i + 1), "COLOR", ("%8.4f " * 3) %
							   tuple(values[:3]))
		else:
			color = valueslist
		checkerboard = []
		for valueslist in [gray, color]:
			if not valueslist:
				continue
			split = int(round(len(valueslist) / 2.0))
			valueslist1 = valueslist[:split]
			valueslist2 = valueslist[split:]
			if shift:
				# Shift values.
				#
				# If split is even:
				#   A1 A2 A3 A4 -> A1 B2 B3 B1 B4
				#   B1 B2 B3 B4 -> A3 A4 A2
				#
				# If split is uneven:
				#   A1 A2 A3 -> A1 B1 B2 B3 B4
				#   B1 B2 B3 B4 -> A2 A3
				offset = 0
				if split == len(valueslist) / 2.0:
					# Even split
					offset += 1
				valueslist1_orig = list(valueslist1)
				valueslist2_orig = list(valueslist2)
				valueslist1 = valueslist2_orig[offset:]
				valueslist2 = valueslist1_orig[offset + 1:]
				valueslist1.insert(0, valueslist1_orig[0])
				if offset:
					valueslist1.insert(-1, valueslist2_orig[0])
					valueslist2.extend(valueslist1_orig[1:2])
			# Interleave.
			# 1 2 3 4 5 6 7 8 -> 1 5 2 6 3 7 4 8
			while valueslist1 or valueslist2:
				for valueslist in (valueslist1, valueslist2):
					if valueslist:
						values = valueslist.pop(0)
						checkerboard.append(values)
		if (shift and
			checkerboard[-1][:3] == [100, 100, 100]):
			# Move white patch to front
			if debug:
				safe_print("INFO - moving white to front")
			checkerboard.insert(0, checkerboard.pop())
		if len(checkerboard) != numvalues:
			# This should never happen
			safe_print("Number of patches incorrect after re-ordering (is %i, "
					   "should be %i)" % (len(checkerboard), numvalues))
			return False
		return data.set_RGB_XYZ_values(checkerboard)
	
	def sort_RGB_gray_to_top(self):
		return self.sort_data_RGB_XYZ(sort_RGB_gray_to_top)
	
	def sort_RGB_to_top(self, r=0, g=0, b=0):
		"""
		Sort quantities of R, G or B (or combinations) to top.
		
		Example: sort_RGB_to_top(True, 0, 0) - sort red values to top
		Example: sort_RGB_to_top(0, True, True) - sort cyan values to top
		
		"""
		if r and g and b:
			fn = sort_RGB_gray_to_top
		elif r and g:
			fn = sort_RGB_to_top_factory(0, 1, 2, 0)
		elif r and b:
			fn = sort_RGB_to_top_factory(0, 2, 1, 0)
		elif g and b:
			fn = sort_RGB_to_top_factory(1, 2, 0, 1)
		elif r:
			fn = sort_RGB_to_top_factory(1, 2, 1, 0)
		elif g:
			fn = sort_RGB_to_top_factory(0, 2, 0, 1)
		elif b:
			fn = sort_RGB_to_top_factory(0, 1, 0, 2)
		return self.sort_data_RGB_XYZ(fn)
	
	def sort_RGB_white_to_top(self):
		return self.sort_data_RGB_XYZ(sort_RGB_white_to_top)
	
	def sort_by_HSI(self):
		return self.sort_data_RGB_XYZ(sort_by_HSI)
	
	def sort_by_HSL(self):
		return self.sort_data_RGB_XYZ(sort_by_HSL)
	
	def sort_by_HSV(self):
		return self.sort_data_RGB_XYZ(sort_by_HSV)
	
	def sort_by_L(self):
		return self.sort_data_RGB_XYZ(sort_by_L)
	
	def sort_by_RGB(self):
		return self.sort_data_RGB_XYZ(sort_by_RGB)
	
	def sort_by_BGR(self):
		return self.sort_data_RGB_XYZ(sort_by_BGR)
	
	def sort_by_RGB_pow_sum(self):
		return self.sort_data_RGB_XYZ(sort_by_RGB_pow_sum)
	
	def sort_by_RGB_sum(self):
		return self.sort_data_RGB_XYZ(sort_by_RGB_sum)
	
	def sort_by_rec709_luma(self):
		return self.sort_data_RGB_XYZ(sort_by_rec709_luma)

	def sort_data_RGB_XYZ(self, cmp=None, key=None, reverse=False):
		""" Sort RGB/XYZ data """
		data, valueslist = self.get_RGB_XYZ_values()
		if not valueslist:
			return False
		valueslist.sort(cmp, key, reverse)
		return data.set_RGB_XYZ_values(valueslist)
	
	@property
	def modified(self):
		if self.root:
			return self.root._modified
		return self._modified
	
	def moveby1(self, start, inc=1):
		"""
		Move items from start by icrementing or decrementing their key by inc.
		"""
		r = xrange(start, len(self) + 1)
		if inc > 0:
			r = reversed(r)
		for key in r:
			if key in self:
				if key + inc < 0:
					break
				else:
					self[key].key += inc
					self[key + inc] = self[key]
					if key == len(self) - 1:
						break
	
	def add_data(self, data, key=None):
		"""
		Add data to the CGATS structure.
		
		data can be a CGATS instance, a dict, a list, a tuple, or a string or
		unicode instance.
		
		"""
		context = self
		if self.type == 'DATA':
			if isinstance(data, (dict, list, tuple)):
				if self.parent['DATA_FORMAT']:
					fl, il = len(self.parent['DATA_FORMAT']), len(data)
					if fl != il:
						raise CGATSTypeError('DATA entries take exactly %s '
											 'values (%s given)' % (fl, il))
					dataset = CGATS()
					i = -1
					for item in self.parent['DATA_FORMAT'].values():
						i += 1
						if isinstance(data, dict):
							try:
								value = data[item]
							except KeyError:
								raise CGATSKeyError(item)
						else:
							value = data[i]
						if item.upper() in ('INDEX', 'SAMPLE_ID', 'SAMPLEID'):
							if self.root.normalize_fields and \
							   item.upper() == 'SAMPLEID':
								item = 'SAMPLE_ID'
							# allow alphanumeric INDEX / SAMPLE_ID
							if isinstance(value, basestring):
								match = re.match(
									'(?:\d+|((?:\d*\.\d+|\d+)(?:e[+-]?\d+)?))$', value)
								if match:
									if match.groups()[0]:
										value = float(value)
									else:
										value = int(value)
						elif item.upper() not in ('SAMPLE_NAME', 'SAMPLE_LOC',
												  'SAMPLENAME'):
							try:
								value = float(value)
							except ValueError:
								raise CGATSValueError('Invalid data type for '
													  '%s (expected float, '
													  'got %s)' % 
													  (item, type(value)))
							else:
								strval = str(abs(value))
								if (self.parent.type != "CAL" and
									item.startswith("RGB_") or
									item.startswith("CMYK_")):
									# Assuming 0..100, 4 decimal digits is
									# enough for roughly 19 bits integer
									# device values
									parts = strval.split(".")
									if len(parts) == 2 and len(parts[-1]) > 4:
										value = round(value, 4)
										strval = str(abs(value))
								parts = strval.split("e")
								lencheck = len(parts[0])
								if len(parts) > 1:
									lencheck += abs(int(parts[1]))
								if lencheck > self.vmaxlen:
									self.vmaxlen = lencheck
						elif self.root.normalize_fields and \
							 item.upper() == 'SAMPLENAME':
							item = 'SAMPLE_NAME'
						dataset[item] = value
					if type(key) == int:
						# accept only integer keys.
						# move existing items
						self.moveby1(key)
					else:
						key = len(self)
					dataset.key = key
					dataset.parent = self
					dataset.root = self.root
					dataset.type = 'SAMPLE'
					self[key] = dataset
				else:
					raise CGATSInvalidOperationError('Cannot add to DATA '
						'because of missing DATA_FORMAT')
			else:
				raise CGATSTypeError('Invalid data type for %s (expected '
									 'CGATS, dict, list or tuple, got %s)' % 
									 (self.type, type(data)))
		elif self.type == 'ROOT':
			if isinstance(data, basestring) and data.find('\n') < 0 and \
			   data.find('\r') < 0:
				if type(key) == int:
					# accept only integer keys.
					# move existing items
					self.moveby1(key)
				else:
					key = len(self)
				self[key] = CGATS()
				self[key].key = key
				self[key].parent = self
				self[key].root = self.root
				self[key].type = data
				context = self[key]
			elif not len(self):
				context = self.add_data(self.file_identifier)  # create root element
				context = context.add_data(data, key)
			else:
				raise CGATSTypeError('Invalid data type for %s (expected str '
									 'or unicode without line endings, got %s)'
									 % (self.type, type(data)))
		elif self.type == 'SECTION':
			if isinstance(data, basestring):
				if type(key) == int:
					# accept only integer keys.
					# move existing items
					self.moveby1(key)
				else:
					key = len(self)
				self[key] = data
			else:
				raise CGATSTypeError('Invalid data type for %s (expected str'
					'or unicode, got %s)' % (self.type, type(data)))
		elif self.type in ('DATA_FORMAT', 'KEYWORDS') or \
			(self.parent and self.parent.type == 'ROOT'):
			if isinstance(data, (dict, list, tuple)):
				for var in data:
					if var in ('NUMBER_OF_FIELDS', 'NUMBER_OF_SETS'):
						self[var] = None
					else:
						if isinstance(data, dict):
							if self.type in ('DATA_FORMAT', 'KEYWORDS'):
								key, value = len(self), data[var]
							else:
								key, value = var, data[var]
						else:
							key, value = len(self), var
						if (self.root.normalize_fields and
							(self.type in ('DATA_FORMAT', 'KEYWORDS') or
							 var == 'KEYWORD') and
							isinstance(value, basestring)):
							value = value.upper()
							if value == 'SAMPLEID':
								value = 'SAMPLE_ID'
							elif value == 'SAMPLENAME':
								value = 'SAMPLE_NAME'
						if var == 'KEYWORD':
							self.emit_keywords = True
							if value != 'KEYWORD':
								self.add_keyword(value)
							else:
								safe_print('Warning: cannot add keyword '
											'"KEYWORD"')
						else:
							if (isinstance(value, basestring) and
								key not in ("DESCRIPTOR", "ORIGINATOR",
										    "CREATED", "DEVICE_CLASS",
										    "COLOR_REP", "TARGET_INSTRUMENT",
										    "LUMINANCE_XYZ_CDM2", "OBSERVER",
											"INSTRUMENT", "MANUFACTURER_ID",
											"MANUFACTURER", "REFERENCE",
											"REFERENCE_OBSERVER", "DISPLAY",
											"TECHNOLOGY", "REFERENCE_FILENAME",
											"REFERENCE_HASH", "TARGET_FILENAME",
											"TARGET_HASH", "FIT_METHOD")):
								match = re.match(
									'(?:\d+|((?:\d*\.\d+|\d+)(?:e[+-]?\d+)?))$', value)
								if match:
									if match.groups()[0]:
										value = float(value)
									else:
										value = int(value)
									if self.type in ('DATA_FORMAT', 
													'KEYWORDS'):
										raise CGATSTypeError('Invalid data '
															 'type for %s '
															 '(expected str '
															 'or unicode, got '
															 '%s)' % 
															 (self.type, 
															  type(value)))
							self[key] = value
			else:
				raise CGATSTypeError('Invalid data type for %s (expected '
					'CGATS, dict, list or tuple, got %s)' % (self.type, 
															 type(data)))
		else:
			raise CGATSInvalidOperationError('Cannot add data to %s' % 
											 self.type)
		return context
	
	def export_3d(self, filename, colorspace="RGB", RGB_black_offset=40,
				  normalize_RGB_white=False, compress=True, format="VRML"):
		if colorspace not in ("DIN99", "DIN99b", "DIN99c", "DIN99d", "LCH(ab)",
							  "LCH(uv)", "Lab", "Luv", "Lu'v'", "RGB", "xyY",
							  "HSI", "HSL", "HSV", "ICtCp", "IPT", "Lpt"):
			raise ValueError("export_3d: Unknown colorspace %r" % colorspace)
		import x3dom
		data = self.queryv1("DATA")
		if self.queryv1("ACCURATE_EXPECTED_VALUES") == "true":
			cat = "Bradford"
		else:
			cat = "XYZ scaling"
		radius = 15.0 / (len(data) ** (1.0 / 3.0))
		scale = 1.0
		if colorspace.startswith("DIN99"):
			if colorspace == "DIN99":
				scale = 100.0 / 40
			else:
				scale = 100.0 / 50
			radius /= scale
		white = data.queryi1({"RGB_R": 100, "RGB_G": 100, "RGB_B": 100})
		if white:
			white = white["XYZ_X"], white["XYZ_Y"], white["XYZ_Z"]
		else:
			white = "D50"
		white = colormath.get_whitepoint(white)
		d50 = colormath.get_whitepoint("D50")
		if colorspace == "Lu'v'":
			white_u_, white_v_ = colormath.XYZ2Lu_v_(*d50)[1:]
		elif colorspace == "xyY":
			white_x, white_y = colormath.XYZ2xyY(*d50)[:2]
		vrml = """#VRML V2.0 utf8

Transform {
	children [

		NavigationInfo {
			type "EXAMINE"
		}

		DirectionalLight {
			direction 0 0 -1
			direction 0 -1 0
		}

		Viewpoint {
			fieldOfView %(fov)s
			position 0 0 %(z)s
		}

		%(axes)s
%(children)s
	]
}
"""
		child = """		# Sphere
		Transform {
			translation %(x).6f %(y).6f %(z).6f
			children [
				Shape{
					geometry Sphere { radius %(radius).6f}
					appearance Appearance { material Material { diffuseColor %(R).6f %(G).6f %(B).6f} }
				}
			]
		}
"""
		axes = ""
		if (colorspace not in ("Lab", "Luv", "ICtCp", "IPT", "Lpt") and
			not colorspace.startswith("DIN99")):
			if colorspace in ("Lu'v'", "xyY"):
				maxz = scale = 100
				maxxy = 200
				radius /= 2.0
				if colorspace == "Lu'v'":
					xlabel, ylabel, zlabel = "u' 0.6", "v' 0.6", "L* 100"
					offsetx, offsety = -.3, -.3
					scale = maxxy / .6
				else:
					xlabel, ylabel, zlabel = "x 0.8", "y 0.8", "Y 100"
					offsetx, offsety = -.4, -.4
					scale = maxxy / .8
				axes = x3dom.get_vrml_axes(xlabel, ylabel, zlabel,
										   offsetx * scale, offsety * scale,
										   0, maxxy, maxxy, maxz)
			elif colorspace in ("LCH(ab)", "LCH(uv)"):
				if colorspace == "LCH(ab)":
					xlabel, ylabel, zlabel = "H(ab)", "C(ab)", "L*"
				else:
					xlabel, ylabel, zlabel = "H(uv)", "C(uv)", "L*"
				axes = x3dom.get_vrml_axes(xlabel, ylabel, zlabel,
										   -180, -100, 0, 360, 200, 100, False)
		else:
			pxcolor = "1.0 0.0 0.0"
			nxcolor = "0.0 1.0 0.0"
			pycolor = "1.0 1.0 0.0"
			nycolor = "0.0 0.0 1.0"
			if colorspace.startswith("DIN99"):
				axes += """Transform {
			translation %.1f %.1f -50.0
			children [
				Shape {
					geometry Text {
						string ["%s"]
						fontStyle FontStyle { family "SANS" style "BOLD" size %.1f }
					}
					appearance Appearance {
						material Material { diffuseColor 0.7 0.7 0.7 }
					}
				}
			]
		}
""" % (100 / scale, 100 / scale, colorspace, 10.0 / scale)
				(pxlabel,
				 nxlabel,
				 pylabel,
				 nylabel,
				 pllabel) = ('"a", "+%i"' % (100 / scale),
							 '"a", "-%i"' % (100 / scale),
							 '"b +%i"' % (100 / scale),
							 '"b -%i"' % (100 / scale),
							 '"L", "+100"')
			elif colorspace == "ICtCp":
				scale = 2.0
				radius /= 2.0
				(pxlabel,
				 nxlabel,
				 pylabel,
				 nylabel,
				 pllabel) = ('"Ct", "+%.1f"' % .5,
							 '"Ct", "-%.1f"' % .5,
							 '"Cp +%.1f"' % .5,
							 '"Cp -%.1f"' % .5,
							 '"I"')
				pxcolor = "0.5 0.0 1.0"
				nxcolor = "0.8 1.0 0.0"
				pycolor = "1.0 0.0 0.25"
				nycolor = "0.0 1.0 1.0"
			elif colorspace == "IPT":
				(pxlabel,
				 nxlabel,
				 pylabel,
				 nylabel,
				 pllabel) = ('"P", "+%.1f"' % 1,
							 '"P", "-%.1f"' % 1,
							 '"T +%.1f"' % 1,
							 '"T -%.1f"' % 1,
							 '"I"')
			else:
				if colorspace == "Luv":
					x = "u"
					y = "v"
				elif colorspace == "Lpt":
					x = "p"
					y = "t"
				else:
					x = "a"
					y = "b"
				(pxlabel,
				 nxlabel,
				 pylabel,
				 nylabel,
				 pllabel) = ('"%s*", "+100"' % x,
							 '"%s*", "-100"' % x,
							 '"%s* +100"' % y,
							 '"%s* -100"' % y,
							 '"L*", "+100"')
			values = {"wh": 2.0 / scale,
					  "ab": 100.0 / scale,
					  "aboffset": 50.0 / scale,
					  "fontsize": 10.0 / scale,
					  "ap": 102.0 / scale,
					  "an": 108.0 / scale,
					  "Ln": 3.0,
					  "bp0": 3.0,
					  "bp1": 103.0 / scale,
					  "bn0": 3.0,
					  "bn1": 107.0 / scale,
					  "pxlabel": pxlabel,
					  "nxlabel": nxlabel,
					  "pylabel": pylabel,
					  "nylabel": nylabel,
					  "pllabel": pllabel,
					  "pxcolor": pxcolor,
					  "nxcolor": nxcolor,
					  "pycolor": pycolor,
					  "nycolor": nycolor}
			axes += """# L* axis
		Transform {
			translation 0.0 0.0 0.0
			children [
				Shape {
					geometry Box { size %(wh).1f %(wh).1f 100.0 }
					appearance Appearance {
						material Material { diffuseColor 0.7 0.7 0.7 }
					}
				}
			]
		}
		# L* axis label
		Transform {
			translation -%(Ln).1f -%(wh).1f 55.0
			children [
				Shape {
					geometry Text {
						string [%(pllabel)s]
						fontStyle FontStyle { family "SANS" style "BOLD" size %(fontsize).1f }
					}
					appearance Appearance {
						material Material { diffuseColor 0.7 0.7 0.7}
					}
				}
			]
		}
		# +x axis
		Transform {
			translation %(aboffset).1f 0.0 -50.0
			children [
				Shape {
					geometry Box { size %(ab).1f %(wh).1f %(wh).1f }
					appearance Appearance {
						material Material { diffuseColor %(pxcolor)s }
					}
				}
			]
		}
		# +x axis label
		Transform {
			translation %(ap).1f -%(wh).1f -50.0
			children [
				Shape {
					geometry Text {
						string [%(pxlabel)s]
						fontStyle FontStyle { family "SANS" style "BOLD" size %(fontsize).1f }
					}
					appearance Appearance {
						material Material { diffuseColor %(pxcolor)s }
					}
				}
			]
		}
		# -x axis
		Transform {
			translation -%(aboffset).1f 0.0 -50.0
			children [
				Shape {
					geometry Box { size %(ab).1f %(wh).1f %(wh).1f }
					appearance Appearance {
						material Material { diffuseColor %(nxcolor)s }
					}
				}
			]
		}
		# -x axis label
		Transform {
			translation -%(an).1f -%(wh).1f -50.0
			children [
				Shape {
					geometry Text {
						string [%(nxlabel)s]
						fontStyle FontStyle { family "SANS" style "BOLD" size %(fontsize).1f }
					}
					appearance Appearance {
						material Material { diffuseColor %(nxcolor)s }
					}
				}
			]
		}
		# +y axis
		Transform {
			translation 0.0 %(aboffset).1f -50.0
			children [
				Shape {
					geometry Box { size %(wh).1f %(ab).1f %(wh).1f }
					appearance Appearance {
						material Material { diffuseColor %(pycolor)s }
					}
				}
			]
		}
		# +y axis label
		Transform {
			translation -%(bp0).1f %(bp1).1f -50.0
			children [
				Shape {
					geometry Text {
						string [%(pylabel)s]
						fontStyle FontStyle { family "SANS" style "BOLD" size %(fontsize).1f }
					}
					appearance Appearance {
						material Material { diffuseColor %(pycolor)s }
					}
				}
			]
		}
		# -y axis
		Transform {
			translation 0.0 -%(aboffset).1f -50.0
			children [
				Shape {
					geometry Box { size %(wh).1f %(ab).1f %(wh).1f }
					appearance Appearance {
						material Material { diffuseColor %(nycolor)s }
					}
				}
			]
		}
		# -y axis label
		Transform {
			translation -%(bn0).1f -%(bn1).1f -50.0
			children [
				Shape {
					geometry Text {
						string [%(nylabel)s]
						fontStyle FontStyle { family "SANS" style "BOLD" size %(fontsize).1f }
					}
					appearance Appearance {
						material Material { diffuseColor %(nycolor)s }
					}
				}
			]
		}
		# Zero
		Transform {
			translation -%(Ln).1f -%(wh).1f -55.0
			children [
				Shape {
					geometry Text {
						string ["0"]
						fontStyle FontStyle { family "SANS" style "BOLD" size %(fontsize).1f }
					}
					appearance Appearance {
						material Material { diffuseColor 0.7 0.7 0.7}
					}
				}
			]
		}
""" % values
		children = []
		sqrt3_100 = math.sqrt(3) * 100
		sqrt3_50 = math.sqrt(3) * 50
		for entry in data.itervalues():
			X, Y, Z = colormath.adapt(entry["XYZ_X"],
									  entry["XYZ_Y"],
									  entry["XYZ_Z"],
									  white,
									  "D65" if colorspace in ("ICtCp", "IPT")
									  else "D50",
									  cat=cat)
			L, a, b = colormath.XYZ2Lab(X, Y, Z)
			if colorspace == "RGB":
				# Fudge device locations into Lab space
				x, y, z = (entry["RGB_G"] - 50,
						   entry["RGB_B"] - 50,
						   entry["RGB_R"] - 50)
			elif colorspace == "HSI":
				H, S, z = colormath.RGB2HSI(entry["RGB_R"] / 100.0,
											entry["RGB_G"] / 100.0,
											entry["RGB_B"] / 100.0)
				rad = H * 360 * math.pi / 180
				x, y = S * z * math.cos(rad), S * z * math.sin(rad)
				# Fudge device locations into Lab space
				x, y, z = x * sqrt3_100, y * sqrt3_100, z * sqrt3_100 - sqrt3_50
			elif colorspace == "HSL":
				H, S, z = colormath.RGB2HSL(entry["RGB_R"] / 100.0,
											entry["RGB_G"] / 100.0,
											entry["RGB_B"] / 100.0)
				rad = H * 360 * math.pi / 180
				if z > .5:
					S *= 1 - z
				else:
					S *= z
				x, y = S * math.cos(rad), S * math.sin(rad)
				# Fudge device locations into Lab space
				x, y, z = x * sqrt3_100, y * sqrt3_100, z * sqrt3_100 - sqrt3_50
			elif colorspace == "HSV":
				H, S, z = colormath.RGB2HSV(entry["RGB_R"] / 100.0,
											entry["RGB_G"] / 100.0,
											entry["RGB_B"] / 100.0)
				rad = H * 360 * math.pi / 180
				x, y = S * z * math.cos(rad), S * z * math.sin(rad)
				# Fudge device locations into Lab space
				x, y, z = x * sqrt3_50, y * sqrt3_50, z * sqrt3_100 - sqrt3_50
			elif colorspace == "Lab":
				x, y, z = a, b, L - 50
			elif colorspace in ("DIN99", "DIN99b"):
				if colorspace == "DIN99":
					L99, a99, b99 = colormath.Lab2DIN99(L, a, b)
				else:
					L99, a99, b99 = colormath.Lab2DIN99b(L, a, b)
				x, y, z = a99, b99, L99 - 50
			elif colorspace in ("DIN99c", "DIN99d"):
				if colorspace == "DIN99c":
					L99, a99, b99 = colormath.XYZ2DIN99c(X, Y, Z)
				else:
					L99, a99, b99 = colormath.XYZ2DIN99d(X, Y, Z)
				x, y, z = a99, b99, L99 - 50
			elif colorspace in ("LCH(ab)", "LCH(uv)"):
				if colorspace == "LCH(ab)":
					L, C, H = colormath.Lab2LCHab(L, a, b)
				else:
					L, u, v = colormath.XYZ2Luv(X, Y, Z)
					L, C, H = colormath.Luv2LCHuv(L, u, v)
				x, y, z = H - 180, C - 100, L - 50
			elif colorspace == "Luv":
				L, u, v = colormath.XYZ2Luv(X, Y, Z)
				x, y, z = u, v, L - 50
			elif colorspace == "Lu'v'":
				L, u_, v_ = colormath.XYZ2Lu_v_(X, Y, Z)
				x, y, z = ((u_ + offsetx) * scale,
						   (v_ + offsety) * scale, L / 100.0 * maxz - 50)
			elif colorspace == "xyY":
				x, y, Y = colormath.XYZ2xyY(X, Y, Z)
				x, y, z = ((x + offsetx) * scale,
						   (y + offsety) * scale,
						   Y / 100.0 * maxz - 50)
			elif colorspace == "ICtCp":
				I, Ct, Cp = colormath.XYZ2ICtCp(X / 100.0, Y / 100.0, Z / 100.0,
												clamp=False)
				x, y, z = Ct * 100, Cp * 100, I * 100 - 50
			elif colorspace == "IPT":
				I, P, T = colormath.XYZ2IPT(X / 100.0, Y / 100.0, Z / 100.0)
				x, y, z = P * 100, T * 100, I * 100 - 50
			elif colorspace == "Lpt":
				L, p, t = colormath.XYZ2Lpt(X, Y, Z)
				x, y, z = p, t, L - 50
			if RGB_black_offset != 40:
				# Keep reference hue and saturation
				# Lab to sRGB using reference black offset of 40 like Argyll CMS
				R, G, B = colormath.Lab2RGB(L * (100.0 - 40.0) / 100.0 + 40.0,
											a, b, scale=.7,
											noadapt=not normalize_RGB_white)
				H_ref, S_ref, V_ref = colormath.RGB2HSV(R, G, B)
			# Lab to sRGB using actual black offset
			R, G, B = colormath.Lab2RGB(L * (100.0 - RGB_black_offset) / 100.0 +
										RGB_black_offset, a, b, scale=.7,
										noadapt=not normalize_RGB_white)
			if RGB_black_offset != 40:
				H, S, V = colormath.RGB2HSV(R, G, B)
				# Use reference H and S to go back to RGB
				R, G, B = colormath.HSV2RGB(H_ref, S_ref, V)
			children.append(child % {"x": x,
									 "y": y,
									 "z": z,
									 "R": R + .05,
									 "G": G + .05,
									 "B": B + .05,
									 "radius": radius})
		children = "".join(children)
		# Choose viewpoint fov and z position based on colorspace
		fov = 45
		z = 340
		if colorspace in ("LCH(ab)", "LCH(uv)"):
			# Use a very narrow field of view for LCH
			fov /= 16.0
			z *= 16
		elif colorspace.startswith("DIN99") or colorspace == "ICtCp":
			fov /= scale
		out = vrml % {"children": children,
					  "axes": axes,
					  "fov": fov / 180.0 * math.pi,
					  "z": z}
		if format != "VRML":
			safe_print("Generating", format)
			x3d = x3dom.vrml2x3dom(out)
			if format == "HTML":
				out = x3d.html(title=os.path.basename(filename))
			else:
				out = x3d.x3d()
		if compress:
			writer = GzipFileProper
		else:
			writer = open
		safe_print("Writing", filename)
		with writer(filename, "wb") as outfile:
			outfile.write(out)
	
	@property
	def NUMBER_OF_FIELDS(self):
		"""Get number of fields"""
		if 'DATA_FORMAT' in self:
			return len(self['DATA_FORMAT'])
		return 0
	
	@property
	def NUMBER_OF_SETS(self):
		"""Get number of sets"""
		if 'DATA' in self:
			return len(self['DATA'])
		return 0

	def query(self, query, query_value = None, get_value = False, 
				get_first = False):
		"""
		Return CGATS object of items or values where query matches.
		
		Query can be a dict with key / value pairs, a tuple or a string.
		Return empty CGATS object if no matching items found.
		
		"""
		modified = self.modified
		
		if not get_first:
			result = CGATS()
		else:
			result = None
		
		if not isinstance(query, dict):
			if type(query) not in (list, tuple):
				query = (query, )
		
		items = [self] + [self[key] for key in self]
		for item in items:
			if isinstance(item, (dict, list, tuple)):
			
				if not get_first:
					n = len(result)
				
				if get_value:
					result_n = CGATS()
				else:
					result_n = None
				
				match_count = 0
				for query_key in query:
					if query_key in item or (type(item) is CGATS and 
					   ((query_key == 'NUMBER_OF_FIELDS' and 'DATA_FORMAT' in 
					   item) or (query_key == 'NUMBER_OF_SETS' and 'DATA' in 
					   item))):
						if query_value is None and isinstance(query, dict):
							current_query_value = query[query_key]
						else:
							current_query_value = query_value
						if current_query_value != None:
							if item[query_key] != current_query_value:
								break
						if get_value:
							result_n[len(result_n)] = item[query_key]
						match_count += 1
					else:
						break
				
				if match_count == len(query):
					if not get_value:
						result_n = item
					if result_n != None:
						if get_first:
							if get_value and isinstance(result_n, dict) and \
							   len(result_n) == 1:
								result = result_n[0]
							else:
								result = result_n
							break
						elif len(result_n):
							if get_value and isinstance(result_n, dict) and \
							   len(result_n) == 1:
								result[n] = result_n[0]
							else:
								result[n] = result_n
				
				if type(item) == CGATS and item != self:
					result_n = item.query(query, query_value, get_value, 
										  get_first)
					if result_n != None:
						if get_first:
							result = result_n
							break
						elif len(result_n):
							for i in result_n:
								n = len(result)
								if result_n[i] not in result.values():
									result[n] = result_n[i]
		
		if isinstance(result, CGATS):
			result.setmodified(modified)
		return result
	
	def queryi(self, query, query_value=None):
		""" Query and return matching items. See also query method. """
		return self.query(query, query_value, get_value=False, get_first=False)
	
	def queryi1(self, query, query_value=None):
		""" Query and return first matching item. See also query method. """
		return self.query(query, query_value, get_value=False, get_first=True)
	
	def queryv(self, query, query_value=None):
		""" Query and return matching values. See also query method. """
		return self.query(query, query_value, get_value=True, get_first=False)
	
	def queryv1(self, query, query_value=None):
		""" Query and return first matching value. See also query method. """
		return self.query(query, query_value, get_value=True, get_first=True)
	
	def remove(self, item):
		""" Remove an item from the internal CGATS structure. """
		if type(item) == CGATS:
			key = item.key
		else:
			key = item
		maxindex = len(self) - 1
		result = self[key]
		if type(key) == int and key != maxindex:
			self.moveby1(key + 1, -1)
		name = len(self) - 1
		if (self.type not in ('DATA', 'DATA_FORMAT', 'KEYWORDS', 'SECTION') and
			name in self._keys):
			self._keys.remove(name)
		dict.pop(self, name)
		self.setmodified()
		return result

	def convert_XYZ_to_Lab(self):
		"""
		Convert XYZ to D50 L*a*b* and add it as additional fields
		
		"""
		color_rep = (self.queryv1("COLOR_REP") or "").split("_")

		if color_rep[1] == "LAB":
			# Nothing to do
			return

		if (len(color_rep) != 2 or color_rep[0] not in ("RGB", "CMYK") or
			color_rep[1] != "XYZ"):
			raise NotImplementedError("Got unsupported color representation %s"
									  % "_".join(color_rep))

		data = self.queryv1("DATA")
		if not data:
			raise CGATSError("No data")

		if color_rep[0] == "RGB":
			white = data.queryv1({"RGB_R": 100, "RGB_G": 100, "RGB_B": 100})
		elif color_rep[0] == "CMYK":
			white = data.queryv1({"CMYK_C": 0, "CMYK_M": 0, "CMYK_Y": 0,
								  "CMYK_K": 0})
		if not white:
			raise CGATSError("Missing white patch")

		device_labels = []
		for channel in color_rep[0]:
			device_labels.append(color_rep[0] + "_" + channel)

		# Always XYZ
		cie_labels = []
		for channel in color_rep[1]:
			cie_labels.append(color_rep[1] + "_" + channel)

		# Add entries to DATA_FORMAT
		Lab_data_format = ("LAB_L", "LAB_A", "LAB_B")
		for label in Lab_data_format:
			if not label in data.parent.DATA_FORMAT.values():
				data.parent.DATA_FORMAT.add_data((label, ))

		# Add L*a*b* to each sample
		for key, sample in data.iteritems():
			cie_values = [sample[label] for label in cie_labels]
			Lab = colormath.XYZ2Lab(*cie_values)
			for i, label in enumerate(Lab_data_format):
				sample[label] = Lab[i]

	def fix_zero_measurements(self, warn_only=False, logfile=safe_print):
		"""
		Fix (or warn about) <= zero measurements
		
		If XYZ/Lab = 0, the sample gets removed. If only one component of
		XYZ/Lab is <= 0, it gets fudged so that the component is nonzero
		(because otherwise, Argyll's colprof will remove it, which can have bad
		effects if it's an 'essential' sample)
		
		"""
		color_rep = (self.queryv1("COLOR_REP") or "").split("_")
		data = self.queryv1("DATA")
		if len(color_rep) == 2 and data:
			# Check for XYZ/Lab = 0 readings
			cie_labels = []
			for channel in color_rep[1]:
				cie_labels.append(color_rep[1] + "_" + channel)
				if color_rep[1] == "LAB":
					# Only check L* for zero values
					break
			device_labels = []
			for channel in color_rep[0]:
				device_labels.append(color_rep[0] + "_" + channel)
			remove = []
			for key, sample in data.iteritems():
				cie_values = [sample[label] for label in cie_labels]
				# Check if zero
				if filter(lambda v: v, cie_values):
					# Not all zero. Check if some component(s) equal or below zero
					if min(cie_values) <= 0:
						for label in cie_labels:
							if sample[label] <= 0:
								if warn_only:
									if logfile:
										logfile.write("Warning: Sample ID %i (%s %s) has %s <= 0!\n" %
													  (sample.SAMPLE_ID,
													   color_rep[0],
													   " ".join(str(sample.queryv1(device_labels)).split()),
													   label))
								else:
									# Fudge to be nonzero
									sample[label] = 0.000001
									if logfile:
										logfile.write("Fudged sample ID %i (%s %s) %s to be non-zero\n" %
													  (sample.SAMPLE_ID,
													   color_rep[0],
													   " ".join(str(sample.queryv1(device_labels)).split()),
													   label))
					continue
				# All zero
				device_values = [sample[label] for label in device_labels]
				if not max(device_values):
					# Skip device black
					continue
				if warn_only:
					if logfile:
						logfile.write("Warning: Sample ID %i (%s %s) has %s = 0!\n" %
									  (sample.SAMPLE_ID,
									   color_rep[0],
									   " ".join(str(sample.queryv1(device_labels)).split()),
									   color_rep[1]))
				else:
					# Queue sample for removal
					remove.insert(0, sample)
					if logfile:
						logfile.write("Removed sample ID %i (%s %s) with %s = 0\n" %
									  (sample.SAMPLE_ID,
									   color_rep[0],
									   " ".join(str(sample.queryv1(device_labels)).split()),
									   color_rep[1]))
			for sample in remove:
				# Remove sample
				data.pop(sample)
	
	def fix_device_values_scaling(self, color_rep=None):
		"""
		Attempt to fix device value scaling so that max = 100
		
		Return number of fixed DATA sections

		"""
		fixed = 0
		for labels in get_device_value_labels(color_rep):
			for dataset in self.query("DATA").itervalues():
				for item in dataset.queryi(labels).itervalues():
					for label in labels:
						if item[label] > 100:
							dataset.scale_device_values(color_rep=color_rep)
							fixed += 1
							break
		return fixed

	def normalize_to_y_100(self):
		""" Scale XYZ values so that RGB 100 = Y 100 """
		if "DATA" in self:
			white_cie = self.get_white_cie()
			if white_cie and "XYZ_Y" in white_cie:
				white_Y = white_cie["XYZ_Y"]
				if white_Y != 100:
					self.add_keyword("LUMINANCE_XYZ_CDM2",
									 "%.4f %.4f %.4f" % (white_cie["XYZ_X"],
														 white_cie["XYZ_Y"],
														 white_cie["XYZ_Z"]))
					for sample in self.DATA.itervalues():
						for label in "XYZ":
							v = sample["XYZ_" + label]
							sample["XYZ_" + label] = v / white_Y * 100
				self.add_keyword("NORMALIZED_TO_Y_100", "YES")
				return True
		return False
	
	def quantize_device_values(self, bits=8, quantizer=round):
		""" Quantize device values to n bits """
		q = 2 ** bits - 1.0
		for data in self.queryv("DATA").itervalues():
			if data.parent.type == "CAL":
				maxv = 1.0
				digits = 8
			else:
				maxv = 100.0
				# Assuming 0..100, 4 decimal digits is
				# enough for roughly 19 bits integer
				# device values
				digits = 4
			color_rep = (data.parent.queryv1("COLOR_REP") or "").split("_")[0]
			for labels in get_device_value_labels(color_rep):
				for item in data.queryi(labels).itervalues():
					for label in labels:
						item[label] = round(quantizer(item[label] / maxv * q) /
											q * maxv, digits)
	
	def scale_device_values(self, factor=100.0 / 255, color_rep=None):
		""" Scales device values by multiplying with factor. """
		for labels in get_device_value_labels(color_rep):
			for data in self.queryv("DATA").itervalues():
				for item in data.queryi(labels).itervalues():
					for label in labels:
						item[label] *= factor
	
	def adapt(self, whitepoint_source=None, whitepoint_destination=None,
			  cat="Bradford"):
		"""
		Perform chromatic adaptation if possible (needs XYZ or LAB)
		
		Return number of affected DATA sections.
		
		"""
		n = 0
		for dataset in self.query("DATA").itervalues():
			if not dataset.get_cie_data_format():
				continue
			if not whitepoint_source:
				whitepoint_source = dataset.get_white_cie("XYZ")
			if whitepoint_source:
				n += 1
				for item in dataset.queryv1("DATA").itervalues():
					if "XYZ_X" in item:
						X, Y, Z = item["XYZ_X"], item["XYZ_Y"], item["XYZ_Z"]
					else:
						X, Y, Z = colormath.Lab2XYZ(item["LAB_L"],
													item["LAB_A"],
													item["LAB_B"],
													scale=100)
					X, Y, Z = colormath.adapt(X, Y, Z,
											  whitepoint_source,
											  whitepoint_destination,
											  cat)
					if "LAB_L" in item:
						(item["LAB_L"],
						 item["LAB_A"],
						 item["LAB_B"]) = colormath.XYZ2Lab(X, Y, Z)
					if "XYZ_X" in item:
						item["XYZ_X"], item["XYZ_Y"], item["XYZ_Z"] = X, Y, Z
		return n
	
	def apply_bpc(self, bp_out=(0, 0, 0), weight=False):
		"""
		Apply black point compensation.
		
		Scales XYZ so that black (RGB 0) = zero.
		Needs a CGATS structure with RGB and XYZ data and atleast one black and
		white patch.
		
		Return number of affected DATA sections.
		
		"""
		n = 0
		for dataset in self.query("DATA").itervalues():
			if dataset.type.strip() == "CAL":
				is_Lab = False
				labels = ("RGB_R", "RGB_G", "RGB_B")
				data = dataset.queryi(labels)

				# Get black
				black1 = data.queryi1({"RGB_I": 0})
				# Get white
				white1 = data.queryi1({"RGB_I": 1})
				if not black1 or not white1:
					# Can't apply bpc
					continue

				black = []
				white = []
				for label in labels:
					black.append(black1[label])
					white.append(white1[label])
				max_v = 1.0
			else:
				is_Lab = "_LAB" in (dataset.queryv1("COLOR_REP") or "")
				if is_Lab:
					labels = ("LAB_L", "LAB_A", "LAB_B")
					index = 0  # Index of L* in labels
				else:
					labels = ("XYZ_X", "XYZ_Y", "XYZ_Z")
					index = 1  # Index of Y in labels
				data = dataset.queryi(("RGB_R", "RGB_G", "RGB_B") + labels)

				# Get blacks
				blacks = data.queryi({"RGB_R": 0, "RGB_G": 0, "RGB_B": 0})
				# Get whites
				whites = data.queryi({"RGB_R": 100, "RGB_G": 100, "RGB_B": 100})
				if not blacks or not whites:
					# Can't apply bpc
					continue

				black = [0, 0, 0]
				for i in blacks:
					if blacks[i][labels[index]] > black[index]:
						for j, label in enumerate(labels):
							black[j] = blacks[i][label]
				if is_Lab:
					black = colormath.Lab2XYZ(*black)

				white = [0, 0, 0]
				for i in whites:
					if whites[i][labels[index]] > white[index]:
						for j, label in enumerate(labels):
							white[j] = whites[i][label]
				if is_Lab:
					max_v = 100.0
					white = colormath.Lab2XYZ(*white)
				else:
					max_v = white[1]
					black = [v / max_v for v in black]
					white = [v / max_v for v in white]

			# Apply black point compensation
			n += 1
			for i in data:
				values = data[i].queryv1(labels).values()
				if is_Lab:
					values = colormath.Lab2XYZ(*values)
				else:
					values = [v / max_v for v in values]
				if weight:
					values = colormath.apply_bpc(values[0], values[1],
												 values[2], black, bp_out,
												 white, weight)
				else:
					values = colormath.blend_blackpoint(values[0], values[1],
														values[2], black,
														bp_out, white)
				values = [v * max_v for v in values]
				if is_Lab:
					values = colormath.XYZ2Lab(*values)
				for j, label in enumerate(labels):
					if is_Lab and j > 0:
						data[i][label] = values[j]
					else:
						data[i][label] = max(0.0, values[j])

		return n
	
	def get_white_cie(self, colorspace=None):
		"""
		Get the 'white' from the CIE values (if any).
		
		"""
		data_format = self.get_cie_data_format()
		if data_format:
			if "RGB_R" in data_format.values():
				white = {"RGB_R": 100, "RGB_G": 100, "RGB_B": 100}
			elif "CMYK_C" in data_format.values():
				white = {"CMYK_C": 0, "CMYK_M": 0, "CMYK_Y": 0, "CMYK_K": 0}
			else:
				white = None
			if white:
				white = self.queryi1(white)
			if not white:
				for key in ("LUMINANCE_XYZ_CDM2", "APPROX_WHITE_POINT"):
					white = self.queryv1(key)
					if white:
						try:
							white = [float(v) for v in white.split()]
						except ValueError:
							white = None
						else:
							if len(white) == 3:
								white = [v / white[1] * 100 for v in white]
								white = {"XYZ_X": white[0],
										 "XYZ_Y": white[1],
										 "XYZ_Z": white[2]}
								break
							else:
								white = None
				if not white:
					return
			if white and (("XYZ_X" in white and
						   "XYZ_Y" in white and
						   "XYZ_Z" in white) or ("LAB_L" in white and
												 "LAB_B" in white and
												 "LAB_B" in white)):
				if colorspace == "XYZ":
					if "XYZ_X" in white:
						return white["XYZ_X"], white["XYZ_Y"], white["XYZ_Z"]
					else:
						return colormath.Lab2XYZ(white["LAB_L"],
												 white["LAB_A"],
												 white["LAB_B"],
												 scale=100)
				elif colorspace == "Lab":
					if "LAB_L" in white:
						return white["LAB_L"], white["LAB_A"], white["LAB_B"]
					else:
						return colormath.XYZ2Lab(white["XYZ_X"],
												 white["XYZ_Y"],
												 white["XYZ_Z"])
				return white
	
	def get_cie_data_format(self):
		"""
		Check if DATA_FORMAT defines any CIE XYZ or LAB columns.
		
		Return the DATA_FORMAT on success or None on failure.
		
		"""
		data_format = self.queryv1("DATA_FORMAT")
		if data_format:
			cie = {}
			for ch in ("L", "A", "B"):
				cie[ch] = "LAB_%s" % ch in data_format.values()
			if len(cie.values()) in (0, 3):
				for ch in ("X", "Y", "Z"):
					cie[ch] = "XYZ_%s" % ch in data_format.values()
				if len(filter(lambda v: v is not False,
							  cie.itervalues())) in (3, 6):
					return data_format
	
	pop = remove
	
	def write(self, stream_or_filename=None):
		"""
		Write CGATS text to stream.
		
		"""
		if not stream_or_filename:
			stream_or_filename = self.filename
		if isinstance(stream_or_filename, basestring):
			stream = open(stream_or_filename, "w")
		else:
			stream = stream_or_filename
		stream.write(str(self))
		if isinstance(stream_or_filename, basestring):
			stream.close()
	
