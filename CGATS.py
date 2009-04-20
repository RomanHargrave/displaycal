#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Simple CGATS file parser class

Copyright (C) 2008 Florian Hoech
"""

import StringIO, os, re, sys
from safe_print import safe_print

def universal_newlines(txt):
	return txt.replace("\r\n", "\n").replace("\r", "\n")

StringIO__init__ = StringIO.StringIO.__init__

def StringIO__init__universal_newlines(self, txt = ""):
	StringIO__init__(self, universal_newlines(txt))

StringIO.StringIO.__init__ = StringIO__init__universal_newlines

debug = '-d' in sys.argv[1:]

def rpad(value, width):
	strval = str(value)
	i = strval.find(".")
	if i > -1:
		strval = str(round(value, width - i - 1)).ljust(width, '0')
	return strval

def rcut(value, width):
	strval = str(value)
	i = strval.find(".")
	if i > -1:
		strval = str(round(value, width - i - 1))
	return strval

class CGATSInvalidError(IOError):
	def __str__(self):
		return self.args[0]

class CGATSInvalidOperationError(Exception):
	def __str__(self):
		return self.args[0]

class CGATSKeyError(KeyError):
	def __str__(self):
		return self.args[0]

class CGATSTypeError(TypeError):
	def __str__(self):
		return self.args[0]

class CGATSValueError(ValueError):
	def __str__(self):
		return self.args[0]

class CGATS(dict):
	datetime = None
	filename = None
	key = None
	modified = False
	mtime = None
	parent = None
	root = None
	type = 'ROOT'
	vmaxlen = 0
	
	def __init__(self, cgats = None):
		self.root = self
		
		if cgats:
			
			if isinstance(cgats, list):
				raw_lines = cgats
			else:
				if isinstance(cgats, (str, unicode)):
					if cgats.find('\n') < 0 and cgats.find('\r') < 0: # assume filename
						cgats = open(cgats, 'rU')
						self.filename = cgats.name
					else: # assume text
						cgats = StringIO.StringIO(cgats)
				elif isinstance(cgats, file):
					self.filename = cgats.name
				elif not isinstance(cgats, StringIO.StringIO):
					raise CGATSInvalidError('Unsupported type:', type(cgats))
				if self.filename not in ('', None):
					self.mtime = os.stat(self.filename).st_mtime
				cgats.seek(0)
				raw_lines = cgats.readlines()
				cgats.close()

			context = self

			for raw_line in raw_lines:
				line = re.sub('[^\x09\x20-\x7E\x80-\xFF]', '', raw_line.strip()) # strip control chars and leading/trailing whitespace
				# if debug: safe_print(line)
				comment_offset = line.find('#')
				if comment_offset >= 0: # strip comment
					line = line[:comment_offset].strip()
				values = [value.strip('"') for value in line.split()]
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
						context.add_data(values)
				elif context.type == 'SECTION':
					context.add_data(line)
				elif len(values) > 1:
					if values[0] == 'Date:':
						context.datetime = line
					else:
						match = re.match('([^"]+?)(?:\s+("[^"]+"|[^\s]+))?(?:\s*#(.*))?$', line)
						if match:
							key, value, comment = match.groups()
							if value != None:
								context.add_data({key: value.strip('"')})
							else:
								context.add_data({key: ''})
				elif line and values[0] not in ('Comment:', 'Date:'):
					self.add_data(line)
					# context = self[-1][line]
					context = self[-1]
			self.setmodified(False)

	def __delattr__(self, name):
		del self[name]
		self.setmodified()
	
	def __delitem__(self, name):
		dict.__delitem__(self, name)
		self.setmodified()

	def __getattr__(self, name):
		try:
			if name == 'modified':
				return object.__getattribute__(self.root, name)
			return object.__getattribute__(self, name)
		except AttributeError:
			return self[name]

	def __getitem__(self, name):
		if name == -1:
			return self.get(len(self) - 1)
		elif name in ('NUMBER_OF_FIELDS', 'NUMBER_OF_SETS'):
			return object.__getattribute__(self, name)
		elif name in self:
			if str(name).upper() in ('INDEX', 'SAMPLE_ID'):
				if type(self.get(name)) not in (int, float):
					return self.get(name)
				if str(name).upper() == 'INDEX':
					return self.key
				if type(self.get(name)) == float:
					return 1.0 / (self.NUMBER_OF_SETS - 1) * self.key
				return self.key + 1
			return self.get(name)
		raise CGATSKeyError(name)
	
	def get(self, name):
		if name == -1:
			return dict.get(self, len(self) - 1)
		elif name in ('NUMBER_OF_FIELDS', 'NUMBER_OF_SETS'):
			return object.__getattribute__(self, name)
		else:
			return dict.get(self, name)

	def __setattr__(self, name, value):
		if name == 'modified':
			self.setmodified(value)
		elif name in ('datetime', 'filename', 'key', 'parent', 'root', 'type', 'vmaxlen'):
			object.__setattr__(self, name, value)
			self.setmodified()
		else:
			self[name] = value
	
	def __setitem__(self, name, value):
		dict.__setitem__(self, name, value)
		self.setmodified()
	
	def setmodified(self, modified = True):
		if self.root and self.root.modified != modified:
			object.__setattr__(self.root, 'modified', modified)
	
	def __str__(self):
		result = []
		data = None
		if self.type == 'SAMPLE':
			result += [' '.join([str(self[item]) for item in self.parent.parent['DATA_FORMAT'].values()])]
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
				result += [self.type.ljust(7)] # Make sure CGATS file identifiers are always a minimum of 7 characters
				result += ['']
			# elif self.type == 'FILE':
				# result += [self.key]
				# result += ['']
			for key in self:
				value = self[key]
				if key == 'DATA':
					data = value
				elif type(value) in (float, int, str, unicode):
					if key not in ('NUMBER_OF_FIELDS', 'NUMBER_OF_SETS'):
						if type(key) == int:
							result += [str(value)]
						else:
							if 'KEYWORDS' in self and key in self['KEYWORDS'].values():
								result += ['KEYWORD "%s"' % key]
								result += ['%s "%s"' % (key, value)]
							elif type(value) in (int, float):
								result += ['%s %s' % (key, value)]
							else:
								result += ['%s "%s"' % (key, value)]
				elif key not in ('DATA_FORMAT', 'KEYWORDS'):
					if (value.type == 'SECTION' and result[-1:] and result[-1:][0][-1] != '\n'):
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
			# l = []
			for key in data:
				result += [' '.join([rpad(data[key][item], data.vmaxlen) for item in data.parent['DATA_FORMAT'].values()])]
				# l += [[data[key][item] for item in data.parent['DATA_FORMAT'].values()]]
			# l.sort()
			# result += [' '.join([str(value) for value in item]) for item in l]
			result += ['END_DATA']
		return '\n'.join(result)

	def add_keyword(self, keyword, value = None):
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
			context['KEYWORDS'][len(context['KEYWORDS'])] = keyword
		if value != None:
			context[keyword] = value

	def remove_keyword(self, keyword, remove_value = True):
		if self.type in ('DATA', 'DATA_FORMAT', 'KEYWORDS', 'SECTION'):
			context = self.parent
		elif self.type == 'SAMPLE':
			context = self.parent.parent
		else:
			context = self
		for key in context['KEYWORDS']:
			if context['KEYWORDS'][key] == keyword:
				del context['KEYWORDS'][key]
		if remove_value:
			del context[keyword]
	
	def insert(self, key = None, item = None):
		self.add_data(item, key)
	
	def append(self, item):
		self.add_data(item)
	
	def moveby1(self, start, inc = 1):
		""" move items beginning from start by icrementing or decrementing key by inc """
		r = range(start, len(self) + 1)
		if inc > 0:
			r.reverse()
		for key in r:
			if key in self:
				if key + inc < 0:
					break
				else:
					self[key].key += inc
					self[key + inc] = self[key]
					if key == len(self) - 1:
						break
	
	def add_data(self, data, key = None):
		if self.type == 'DATA':
			if type(data) in (CGATS, dict, list, tuple):
				if self.parent['DATA_FORMAT']:
					fl, il = len(self.parent['DATA_FORMAT']), len(data)
					if fl != il:
						raise CGATSTypeError('DATA entries take exactly %s values (%s given)' % (fl, il))
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
						if item.upper() in ('INDEX', 'SAMPLE_ID'): # allow alphanumeric INDEX / SAMPLE_ID
							if isinstance(value, (str, unicode)):
								match = re.match('(?:\d+|\d*(\.\d+))(e[+-]\d+)?$', value)
								if match:
									if match.groups()[0]:
										value = float(value)
									else:
										value = int(value)
						elif item.upper() not in ('SAMPLE_NAME', 'SAMPLE_LOC'):
							if isinstance(value, (str, unicode)):
								if len(value) > self.vmaxlen:
									self.vmaxlen = len(value)
							try:
								value = float(value)
							except ValueError:
								raise CGATSValueError('Invalid data type for %s (expected float, got %s)' % (item, type(value)))
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
					raise CGATSInvalidOperationError('Cannot add to DATA because of missing DATA_FORMAT')
			else:
				raise CGATSTypeError('Invalid data type for %s (expected CGATS, dict, list or tuple, got %s)' % (self.type, type(data)))
		elif self.type == 'ROOT':
			if isinstance(data, (str, unicode)) and data.find('\n') < 0 and data.find('\r') < 0:
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
				# self[key][data] = CGATS()
				# self[key][data].key = data
				# self[key][data].parent = self[key]
				# self[key][data].type = 'FILE'
				self[key].type = data
			else:
				raise CGATSTypeError('Invalid data type for %s (expected str or unicode without line endings, got %s)' % (self.type, type(data)))
		elif self.type == 'SECTION':
			if isinstance(data, (str, unicode)):
				if type(key) == int:
					# accept only integer keys.
					# move existing items
					self.moveby1(key)
				else:
					key = len(self)
				self[key] = data
			else:
				raise CGATSTypeError('Invalid data type for %s (expected str or unicode, got %s)' % (self.type, type(data)))
		elif self.type in ('DATA_FORMAT', 'KEYWORDS') or (self.parent and self.parent.type == 'ROOT'):
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
						if var == 'KEYWORD':
							if value != 'KEYWORD':
								self.add_keyword(value)
							else:
								safe_print('Warning: cannot add keyword "KEYWORD"')
						else:
							if isinstance(value, (str, unicode)):
								match = re.match('(?:\d+|\d*(\.\d+))(e[+-]\d+)?$', value)
								if match:
									if match.groups()[0]:
										value = float(value)
									else:
										value = int(value)
									if self.type in ('DATA_FORMAT', 'KEYWORDS'):
										raise CGATSTypeError('Invalid data type for %s (expected str or unicode, got %s)' % (self.type, type(value)))
							self[key] = value
			else:
				raise CGATSTypeError('Invalid data type for %s (expected CGATS, dict, list or tuple, got %s)' % (self.type, type(data)))
		else:
			raise CGATSInvalidOperationError('Cannot add data to %s' % self.type)
	
	def get_NUMBER_OF_FIELDS(self):
		if 'DATA_FORMAT' in self:
			return len(self['DATA_FORMAT'])
		return 0
	
	NUMBER_OF_FIELDS = property(get_NUMBER_OF_FIELDS, doc = 'Get number of fields')
	
	def get_NUMBER_OF_SETS(self):
		if 'DATA' in self:
			return len(self['DATA'])
		return 0
	
	NUMBER_OF_SETS = property(get_NUMBER_OF_SETS, doc = 'Get number of sets')

	def query(self, query, query_value = None, get_value = False, get_first = False):
		""" Return CGATS object of items or values where query matches.
		Query can be a dict with key / value pairs, a tuple or a string.
		Return empty CGATS object if no matching items found. """
		
		if not get_first:
			result = CGATS()
		else:
			result = None
		
		if not isinstance(query, dict):
			if type(query) not in (list, tuple):
				query = (query, )
		
		items = [self] + [self[key] for key in self]
		# for key in self:
			# item = self[key]
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
					if query_key in item or (type(item) == CGATS and ((query_key == 'NUMBER_OF_FIELDS' and 'DATA_FORMAT' in item) or (query_key == 'NUMBER_OF_SETS' and 'DATA' in item))):
						if query_value == None and isinstance(query, dict):
							_query_value = query[query_key]
						else:
							_query_value = query_value
						if _query_value != None:
							if item[query_key] != _query_value:
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
							if get_value and isinstance(result_n, dict) and len(result_n) == 1:
								return result_n[0]
							else:
								return result_n
						elif len(result_n):
							if get_value and isinstance(result_n, dict) and len(result_n) == 1:
								result[n] = result_n[0]
							else:
								result[n] = result_n
				
				if type(item) == CGATS and item != self:
					result_n = item.query(query, query_value, get_value, get_first)
					if result_n != None:
						if get_first:
							return result_n
						elif len(result_n):
							for i in result_n:
								n = len(result)
								if result_n[i] not in result.values():
									result[n] = result_n[i]
		
		return result
	
	def queryi(self, query, query_value = None):
		return self.query(query, query_value, get_value = False, get_first = False)
	
	def queryi1(self, query, query_value = None):
		return self.query(query, query_value, get_value = False, get_first = True)
	
	def queryv(self, query, query_value = None):
		return self.query(query, query_value, get_value = True, get_first = False)
	
	def queryv1(self, query, query_value = None):
		return self.query(query, query_value, get_value = True, get_first = True)
	
	def remove(self, item):
		if type(item) == CGATS:
			key = item.key
		else:
			key = item
		l = len(self) - 1
		result = dict.pop(self, key)
		if type(key) == int and key != l:
			self.moveby1(key + 1, -1)
			dict.pop(self, len(self) - 1)
		self.setmodified()
		return result
	
	pop = remove
