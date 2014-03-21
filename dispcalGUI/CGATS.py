# -*- coding: utf-8 -*-

"""
Simple CGATS file parser class

Copyright (C) 2008 Florian Hoech
"""

from __future__ import with_statement
import math, os, re, sys

import colormath

from safe_print import safe_print
from util_io import GzipFileProper, StringIOu as StringIO


def get_device_value_labels(color_rep=None):
	return filter(bool, map(lambda v: v[1] if not color_rep or v[0] == color_rep
									  else False,
							{"CMYK": ("CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"),
							 "RGB": ("RGB_R", "RGB_G", "RGB_B")}.iteritems()))


def rpad(value, width):
	"""
	Right-pad a value to a given width.
	
	value is converted to a string first.
	
	If value wasn't a number originally, return the quoted string.
	
	"""
	strval = str(value)
	if not isinstance(value, (int, float, long, complex)):
		return '"%s"' % strval
	i = strval.find(".")
	if i > -1:
		if i < width - 1:
			strval = str(round(value, width - i - 1)).ljust(width, '0')
		else:
			strval = str(int(round(value)))
	return strval


def rcut(value, width):
	"""
	Cut off any chars beyond width on the right-hand side.
	
	value is converted to a string first.
	
	If value wasn't a number originally, return the quoted string.
	
	"""
	strval = str(value)
	if not isinstance(value, (int, float, long, complex)):
		return '"%s"' % strval
	i = strval.find(".")
	if i > -1:
		if i < width - 1:
			strval = str(round(value, width - i - 1))
		else:
			strval = str(int(round(value)))
	return strval


def sort_RGB_gray_to_top(a, b):
	if a[0] == a[1] == a[2]:
		if b[0] == b[1] == b[2] and a[0] > b[0]:
			return 1
		return -1
	else:
		return 0


def sort_RGB_white_to_top(a, b):
	sum1, sum2 = sum(a[:3]), sum(b[:3])
	if sum1 == 300:
		return -1
	else:
		return 0


def sort_by_HSI(a, b):
	a = list(colormath.RGB2HSI(*a[:3]))
	b = list(colormath.RGB2HSI(*b[:3]))
	a[0] = round(a[0], 12)
	b[0] = round(b[0], 12)
	if a > b:
		return 1
	elif a < b:
		return -1
	else:
		return 0


def sort_by_HSL(a, b):
	a = list(colormath.RGB2HSL(*a[:3]))
	b = list(colormath.RGB2HSL(*b[:3]))
	a[0] = round(a[0], 12)
	b[0] = round(b[0], 12)
	if a > b:
		return 1
	elif a < b:
		return -1
	else:
		return 0


def sort_by_HSV(a, b):
	a = list(colormath.RGB2HSV(*a[:3]))
	b = list(colormath.RGB2HSV(*b[:3]))
	a[0] = round(a[0], 12)
	b[0] = round(b[0], 12)
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


def sort_by_RGB_sum(a, b):
	sum1, sum2 = sum(a[:3]), sum(b[:3])
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
	key = None
	_modified = False
	mtime = None
	parent = None
	root = None
	type = 'ROOT'
	vmaxlen = 0
	
	def __init__(self, cgats=None, normalize_fields=False, file_identifier="CTI3"):
		"""
		Return a CGATS instance.
		
		cgats can be a path, a string holding CGATS data, or a file object.
		
		If normalize_fields evaluates to True, convert all KEYWORDs and all 
		fields in DATA_FORMAT to UPPERCASE and SampleId or SampleName to
		SAMPLE_ID or SAMPLE_NAME respectively
		
		file_identifier is used as fallback if no file identifier is present
		
		"""
		
		self.normalize_fields = normalize_fields
		self.file_identifier = file_identifier
		self.root = self
		
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
				# strip control chars and leading/trailing whitespace
				line = re.sub('[^\x09\x20-\x7E\x80-\xFF]', '', 
								raw_line.strip())
				comment_offset = line.find('#')
				if comment_offset >= 0: # strip comment
					line = line[:comment_offset].strip()
				values = [value.strip('"') for value in line.split()]
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
						match = re.match(
							'([^"]+?)(?:\s+("[^"]+"|[^\s]+))?(?:\s*#(.*))?$', 
							line)
						if match:
							key, value, comment = match.groups()
							if value != None:
								context = context.add_data({key: value.strip('"')})
							else:
								context = context.add_data({key: ''})
				elif values and values[0] not in ('Comment:', 'Date:') and \
				     len(line) >= 3 and not re.search("[^ 0-9A-Za-z]", line):
					context = self.add_data(line)
			self.setmodified(False)

	def __delattr__(self, name):
		del self[name]
		self.setmodified()
	
	def __delitem__(self, name):
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

	def get_descriptor(self):
		""" Return descriptor """
		desc = self.queryv1("DESCRIPTOR")
		if not desc or desc == "Not specified":
			desc = self.queryv1("INSTRUMENT")
			if desc:
				desc += " & "
			else:
				desc = ""
			desc += self.queryv1("DISPLAY") or ""
		if not desc and self.filename:
			desc = os.path.splitext(os.path.basename(self.filename))[0]
		return desc

	def __setattr__(self, name, value):
		if name == 'modified':
			self.setmodified(value)
		elif name in ('datetime', 'filename', 'file_identifier', 'key', 
					  'mtime', 'normalize_fields', 'parent', 'root', 'type', 
					  'vmaxlen'):
			object.__setattr__(self, name, value)
			self.setmodified()
		else:
			self[name] = value
	
	def __setitem__(self, name, value):
		dict.__setitem__(self, name, value)
		self.setmodified()
	
	def setmodified(self, modified=True):
		""" Set 'modified' state on the 'root' object. """
		if self.root and self.root._modified != modified:
			object.__setattr__(self.root, '_modified', modified)
	
	def __str__(self):
		result = []
		data = None
		if self.type == 'SAMPLE':
			result += [' '.join([str(self[item]) for item in 
						self.parent.parent['DATA_FORMAT'].values()])]
		elif self.type == 'DATA':
			data = self
		elif self.type == 'DATA_FORMAT':
			result += [' '.join(self.values())]
		else:
			if self.datetime:
				result += [self.datetime]
			if self.type == 'SECTION':
				result += ['BEGIN_' + self.key]
			elif self.parent and self.parent.type == 'ROOT':
				result += [self.type.ljust(7)]	# Make sure CGATS file 
												# identifiers are always 
												# a minimum of 7 characters
				result += ['']
			for key in self:
				value = self[key]
				if key == 'DATA':
					data = value
				elif type(value) in (float, int, str, unicode):
					if key not in ('NUMBER_OF_FIELDS', 'NUMBER_OF_SETS'):
						if type(key) == int:
							result += [str(value)]
						else:
							if 'KEYWORDS' in self and \
								key in self['KEYWORDS'].values():
								result += ['KEYWORD "%s"' % key]
								result += ['%s "%s"' % (key, value)]
							elif type(value) in (int, float):
								result += ['%s %s' % (key, value)]
							else:
								result += ['%s "%s"' % (key, value)]
				elif key not in ('DATA_FORMAT', 'KEYWORDS'):
					if (value.type == 'SECTION' and result[-1:] and 
						result[-1:][0][-1] != '\n'):
						result += ['']
					result += [str(value)]
			if self.type == 'SECTION':
				result += ['END_' + self.key]
			if self.type == 'SECTION' or data:
				result += ['']
		if data and data.parent['DATA_FORMAT']:
			if 'KEYWORDS' in data.parent:
				for item in data.parent['DATA_FORMAT'].values():
					if item in data.parent['KEYWORDS'].values():
						result += ['KEYWORD "%s"' % item]
			result += ['NUMBER_OF_FIELDS %s' % len(data.parent['DATA_FORMAT'])]
			result += ['BEGIN_DATA_FORMAT']
			result += [' '.join(data.parent['DATA_FORMAT'].values())]
			result += ['END_DATA_FORMAT']
			result += ['']
			result += ['NUMBER_OF_SETS %s' % (len(data))]
			result += ['BEGIN_DATA']
			for key in data:
				result += [' '.join([rpad(data[key][item], 
										  data.vmaxlen + 
										  (1 if data[key][item] < 0 else 0)) 
									 for item in 
									 data.parent['DATA_FORMAT'].values()])]
			result += ['END_DATA']
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
			return False
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
	
	def checkerboard(self):
		data, valueslist = self.get_RGB_XYZ_values()
		if not valueslist:
			return False
		valueslist *= 2
		valueslist.sort(sort_by_L)
		valueslist.sort(sort_RGB_white_to_top)
		split = len(valueslist) / 2
		valueslist1 = valueslist[:split]
		valueslist2 = valueslist[split:]
		valueslist2.reverse()
		valueslist = valueslist1 + valueslist2
		checkerboard = []
		for i in xrange(split):
			if i % 2 == 1:
				i = len(valueslist) - 1 - i
			values = valueslist[i]
			checkerboard.append(values)
		return data.set_RGB_XYZ_values(checkerboard)
	
	def sort_RGB_gray_to_top(self):
		data, valueslist = self.get_RGB_XYZ_values()
		if not valueslist:
			return False
		valueslist.sort(sort_RGB_gray_to_top)
		return data.set_RGB_XYZ_values(valueslist)
	
	def sort_RGB_white_to_top(self):
		data, valueslist = self.get_RGB_XYZ_values()
		if not valueslist:
			return False
		valueslist.sort(sort_RGB_white_to_top)
		return data.set_RGB_XYZ_values(valueslist)
	
	def sort_by_HSI(self):
		data, valueslist = self.get_RGB_XYZ_values()
		if not valueslist:
			return False
		valueslist.sort(sort_by_HSI)
		return data.set_RGB_XYZ_values(valueslist)
	
	def sort_by_HSL(self):
		data, valueslist = self.get_RGB_XYZ_values()
		if not valueslist:
			return False
		valueslist.sort(sort_by_HSL)
		return data.set_RGB_XYZ_values(valueslist)
	
	def sort_by_HSV(self):
		data, valueslist = self.get_RGB_XYZ_values()
		if not valueslist:
			return False
		valueslist.sort(sort_by_HSV)
		return data.set_RGB_XYZ_values(valueslist)
	
	def sort_by_L(self):
		data, valueslist = self.get_RGB_XYZ_values()
		if not valueslist:
			return False
		valueslist.sort(sort_by_L)
		return data.set_RGB_XYZ_values(valueslist)
	
	def sort_by_RGB(self):
		data, valueslist = self.get_RGB_XYZ_values()
		if not valueslist:
			return False
		valueslist.sort(sort_by_RGB)
		return data.set_RGB_XYZ_values(valueslist)
	
	def sort_by_RGB_sum(self):
		data, valueslist = self.get_RGB_XYZ_values()
		if not valueslist:
			return False
		valueslist.sort(sort_by_RGB_sum)
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
			if type(data) in (CGATS, dict, list, tuple):
				if self.parent['DATA_FORMAT']:
					fl, il = len(self.parent['DATA_FORMAT']), len(data)
					if fl != il:
						raise CGATSTypeError('DATA entries take exactly %s '
											 'values (%s given)' % (fl, il))
					dataset = CGATS()
					i = -1
					for item in self.parent['DATA_FORMAT'].values():
						i += 1
						if type(data) in (CGATS, dict):
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
								lencheck = len(str(abs(value)).split("e")[0])
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
			if type(data) in (CGATS, dict, list, tuple):
				for var in data:
					if var in ('NUMBER_OF_FIELDS', 'NUMBER_OF_SETS'):
						self[var] = None
					else:
						if type(data) in (CGATS, dict):
							if self.type in ('DATA_FORMAT', 'KEYWORDS'):
								key, value = len(self), data[var]
							else:
								key, value = var, data[var]
						else:
							key, value = len(self), var
						if self.root.normalize_fields:
							if isinstance(value, basestring):
								value = value.upper()
							if value == 'SAMPLEID':
								value = 'SAMPLE_ID'
							elif value == 'SAMPLENAME':
								value = 'SAMPLE_NAME'
						if var == 'KEYWORD':
							if value != 'KEYWORD':
								self.add_keyword(value)
							else:
								safe_print('Warning: cannot add keyword '
											'"KEYWORD"')
						else:
							if isinstance(value, basestring):
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
	
	def export_vrml(self, filename, colorspace="RGB", RGB_black_offset=40,
					normalize_RGB_white=False, compress=True):
		if colorspace not in ("DIN99", "DIN99b", "DIN99c", "DIN99d", "LCH(ab)",
							  "LCH(uv)", "Lab", "Luv", "Lu'v'", "RGB", "xyY",
							  "HSI", "HSL", "HSV"):
			raise ValueError("export_vrml: Unknown colorspace %r" % colorspace)
		data = self.queryv1("DATA")
		if self.queryv1("ACCURATE_EXPECTED_VALUES") == "true":
			cat = "Bradford"
		else:
			cat = "XYZ scaling"
		radius = 15.0 / (len(data) ** (1.0 / 3.0))
		if colorspace.startswith("DIN99"):
			if colorspace == "DIN99":
				radius /= 3.0
			else:
				radius /= 2.25
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

		#%(axes)s
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
		if colorspace != "Lab" and not colorspace.startswith("DIN99"):
			axes = ""
		else:
			if colorspace.startswith("DIN99"):
				if colorspace == "DIN99":
					values = {"wh": .75,
							  "ab": 40.0,
							  "aboffset": 20.0,
							  "fontsize": 4.0,
							  "ap": 41.0,
							  "an": 44.0,
							  "Ln": 1.2,
							  "bp0": 1.2,
							  "bp1": 41.2,
							  "bn0": 1.2,
							  "bn1": 43.2}
				else:
					values = {"wh": 1.0,
							  "ab": 50.0,
							  "aboffset": 25.0,
							  "fontsize": 5.0,
							  "ap": 51.0,
							  "an": 54.0,
							  "Ln": 1.5,
							  "bp0": 1.5,
							  "bp1": 51.5,
							  "bn0": 1.5,
							  "bn1": 53.5}
			else:
				values = {"wh": 2.0,
						  "ab": 100.0,
						  "aboffset": 50.0,
						  "fontsize": 10.0,
						  "ap": 102.0,
						  "an": 108.0,
						  "Ln": 3.0,
						  "bp0": 3.0,
						  "bp1": 103.0,
						  "bn0": 3.0,
						  "bn1": 107.0}
			axes = """# L* axis
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
						string ["L"]
						fontStyle FontStyle { family "SANS" style "BOLD" size %(fontsize).1f }
					}
					appearance Appearance {
						material Material { diffuseColor 0.7 0.7 0.7}
					}
				}
			]
		}
		# +a axis
		Transform {
			translation %(aboffset).1f 0.0 -50.0
			children [
				Shape {
					geometry Box { size %(ab).1f %(wh).1f %(wh).1f }
					appearance Appearance {
						material Material { diffuseColor 1.0 0.0 0.0 }
					}
				}
			]
		}
		# +a axis label
		Transform {
			translation %(ap).1f -%(wh).1f -50.0
			children [
				Shape {
					geometry Text {
						string ["+a"]
						fontStyle FontStyle { family "SANS" style "BOLD" size %(fontsize).1f }
					}
					appearance Appearance {
						material Material { diffuseColor 1.0 0.0 0.0}
					}
				}
			]
		}
		# -a axis
		Transform {
			translation -%(aboffset).1f 0.0 -50.0
			children [
				Shape {
					geometry Box { size %(ab).1f %(wh).1f %(wh).1f }
					appearance Appearance {
						material Material { diffuseColor 0.0 1.0 0.0 }
					}
				}
			]
		}
		# -a axis label
		Transform {
			translation -%(an).1f -%(wh).1f -50.0
			children [
				Shape {
					geometry Text {
						string ["-a"]
						fontStyle FontStyle { family "SANS" style "BOLD" size %(fontsize).1f }
					}
					appearance Appearance {
						material Material { diffuseColor 0.0 1.0 0.0}
					}
				}
			]
		}
		# +b axis
		Transform {
			translation 0.0 %(aboffset).1f -50.0
			children [
				Shape {
					geometry Box { size %(wh).1f %(ab).1f %(wh).1f }
					appearance Appearance {
						material Material { diffuseColor 1.0 1.0 0.0 }
					}
				}
			]
		}
		# +b axis label
		Transform {
			translation -%(bp0).1f %(bp1).1f -50.0
			children [
				Shape {
					geometry Text {
						string ["+b"]
						fontStyle FontStyle { family "SANS" style "BOLD" size %(fontsize).1f }
					}
					appearance Appearance {
						material Material { diffuseColor 1.0 1.0 0.0}
					}
				}
			]
		}
		# -b axis
		Transform {
			translation 0.0 -%(aboffset).1f -50.0
			children [
				Shape {
					geometry Box { size %(wh).1f %(ab).1f %(wh).1f }
					appearance Appearance {
						material Material { diffuseColor 0.0 0.0 1.0 }
					}
				}
			]
		}
		# -b axis label
		Transform {
			translation -%(bn0).1f -%(bn1).1f -50.0
			children [
				Shape {
					geometry Text {
						string ["-b"]
						fontStyle FontStyle { family "SANS" style "BOLD" size %(fontsize).1f }
					}
					appearance Appearance {
						material Material { diffuseColor 0.0 0.0 1.0}
					}
				}
			]
		}
""" % values
		children = []
		for entry in data.itervalues():
			X, Y, Z = colormath.adapt(entry["XYZ_X"],
									  entry["XYZ_Y"],
									  entry["XYZ_Z"],
									  white,
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
				x, y, z = x * 100, y * 100, z * math.sqrt(3) * 100 - 50
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
				x, y, z = x * 100, y * 100, z * math.sqrt(3) * 100 - 50
			elif colorspace == "HSV":
				H, S, z = colormath.RGB2HSV(entry["RGB_R"] / 100.0,
											entry["RGB_G"] / 100.0,
											entry["RGB_B"] / 100.0)
				rad = H * 360 * math.pi / 180
				x, y = S * z * math.cos(rad), S * z * math.sin(rad)
				# Fudge device locations into Lab space
				x, y, z = x * 50, y * 50, z * math.sqrt(3) * 100 - 50
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
				x, y, z = ((u_ - white_u_ - .0625) * 500,
						   (v_ - white_v_ + .15625) * 500, L * 5 - 50)
			elif colorspace == "xyY":
				x, y, Y = colormath.XYZ2xyY(X, Y, Z)
				x, y, z = ((x - white_x) * 400,
						   (y - white_y - .0625) * 400,
						   Y * 4 - 50)
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
		# Choose z based on colorspace
		if colorspace in ("LCH(ab)", "LCH(uv)", "Lu'v'", "xyY"):
			fov = 45 / 8.0
			z = 3400
		elif colorspace.startswith("DIN99"):
			if colorspace == "DIN99":
				fov = 45 / 2.0
				z = 270
			else:
				fov = 45 / 1.75
				z = 300
		else:
			fov = 45
			z = 340
		# Use a very narrow field of view for LCH, Lu'v' and xyY
		vrml = vrml % {"children": children,
					   "axes": axes,
					   "fov": fov / 180.0 * math.pi,
					   "z": z}
		if compress:
			writer = GzipFileProper
		else:
			writer = open
		with writer(filename, 'w') as vrmlfile:
			vrmlfile.write(vrml)
	
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
			if type(item) in (CGATS, dict, list, tuple):
			
				if not get_first:
					n = len(result)
				
				if get_value:
					result_n = CGATS()
				else:
					result_n = None
				
				match_count = 0
				for query_key in query:
					if query_key in item or (type(item) == CGATS and 
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
		dict.pop(self, len(self) - 1)
		self.setmodified()
		return result
	
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
			if not dataset.has_cie():
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
	
	def apply_bpc(self, weight=False):
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
			else:
				labels = ("XYZ_X", "XYZ_Y", "XYZ_Z")
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
					if blacks[i]["XYZ_Y"] > black[1]:
						for j, label in enumerate(labels):
							black[j] = blacks[i][label]

				white = [0, 0, 0]
				for i in whites:
					if whites[i]["XYZ_Y"] > white[1]:
						for j, label in enumerate(labels):
							white[j] = whites[i][label]

			# Apply black point compensation
			n += 1
			for i in data:
				XYZ = data[i].queryv1(labels)
				XYZ = colormath.apply_bpc(XYZ[0], XYZ[1], XYZ[2], black,
										  (0, 0, 0), white, weight)
				for j, label in enumerate(labels):
					data[i][label] = max(0.0, XYZ[j])

		return n
	
	def get_white_cie(self, colorspace=None):
		"""
		Get the 'white' from the CIE values (if any).
		
		"""
		data_format = self.has_cie()
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
	
	def has_cie(self):
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
				if len(filter(lambda v: v is not None,
							  cie.itervalues())) in (3, 6):
					return data_format
	
	pop = remove
	
	def write(self, filename=None):
		if not filename:
			filename = self.filename
		txt = open(filename, "w")
		txt.write(str(self))
		txt.close()
	
