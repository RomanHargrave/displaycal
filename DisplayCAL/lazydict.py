# -*- coding: utf-8 -*-

from __future__ import with_statement
import codecs
import os

from config import get_data_path
from debughelpers import handle_error
from util_str import safe_unicode, strtr


def unquote(string, raise_exception=True):
	"""
	Remove single or double quote at start and end of string and unescape
	escaped chars, YAML-style
	
	Unlike 'string'.strip("'"'"'), only removes the outermost quote pair.
	Raises ValueError on missing end quote if there is a start quote.
	
	"""
	if len(string) > 1 and string[0] in "'"'"':
		if string[-1] == string[0]:

			# NOTE: Order of unescapes is important to match YAML!
			string = unescape(string[1:-1])

		elif raise_exception:
			raise ValueError("Missing end quote while scanning quoted scalar")
	return string


def escape(string):
	r"""
	Backslash-escape \r, \n, \t, and " in string
	
	"""
	return strtr(string, [("\r", "\\r"),
						  ("\n", "\\n"),
						  ("\t", "\\t"),
						  ('"', '\\"')])


def unescape(string):
	r"""
	Unescape \\r, \\n, \\t, and \\" in string
	
	"""
	return strtr(string, [# ("\r\n", "\n"),
						  # ("\r", "\n"),
						  # ("\n\n", "\\n"),
						  # ("\n", " "),
						  ("\\r", "\r"),
						  ("\\n", "\n"),
						  ("\\t", "\t"),
						  ('\\"', '"')])


class LazyDict(dict):

	"""
	Lazy dictionary with key -> value mappings.
	
	The actual mappings are loaded from the source YAML file when they
	are accessed.
	
	"""

	def __init__(self, path=None, encoding="UTF-8", errors="strict"):
		dict.__init__(self)
		self._isloaded = False
		self.path = path
		self.encoding = encoding
		self.errors = errors
		
	def __cmp__(self, other):
		self.load()
		return dict.__cmp__(self, other)
	
	def __contains__(self, key):
		self.load()
		return dict.__contains__(self, key)
	
	def __delitem__(self, key):
		self.load()
		dict.__delitem__(self, key)
	
	def __delslice__(self, i, j):
		self.load()
		dict.__delslice__(self, i, j)
	
	def __eq__(self, other):
		self.load()
		return dict.__eq__(self, other)
	
	def __ge__(self, other):
		self.load()
		return dict.__ge__(self, other)

	def __getitem__(self, name):
		self.load()
		return dict.__getitem__(self, name)
	
	def __getslice__(self, i, j):
		self.load()
		return dict.__getslice__(self, i, j)
	
	def __gt__(self, other):
		self.load()
		return dict.__gt__(self, other)

	def __iter__(self):
		self.load()
		return dict.__iter__(self)
	
	def __le__(self, other):
		self.load()
		return dict.__le__(self, other)
	
	def __len__(self):
		self.load()
		return dict.__len__(self)
	
	def __lt__(self, other):
		self.load()
		return dict.__lt__(self, other)
	
	def __ne__(self, other):
		self.load()
		return dict.__ne__(self, other)
	
	def __repr__(self):
		self.load()
		return dict.__repr__(self)

	def __setitem__(self, name, value):
		self.load()
		dict.__setitem__(self, name, value)

	def __sizeof__(self):
		self.load()
		return dict.__sizeof__(self)
	
	def clear(self):
		if not self._isloaded:
			self._isloaded = True
		dict.clear(self)
	
	def copy(self):
		self.load()
		return dict.copy(self)
	
	def get(self, name, fallback=None):
		self.load()
		return dict.get(self, name, fallback)
	
	def has_key(self, name):
		self.load()
		return dict.has_key(self, name)
	
	def items(self):
		self.load()
		return dict.items(self)
	
	def iteritems(self):
		self.load()
		return dict.iteritems(self)
	
	def iterkeys(self):
		self.load()
		return dict.iterkeys(self)
	
	def itervalues(self):
		self.load()
		return dict.itervalues(self)
	
	def keys(self):
		self.load()
		return dict.keys(self)

	def load(self, path=None, encoding=None, errors=None, raise_exceptions=False):
		if not self._isloaded and (path or self.path):
			self._isloaded = True
			if not path:
				path = self.path
			if path and not os.path.isabs(path):
				path = get_data_path(path)
			if path and os.path.isfile(path):
				self.path = path
				if encoding:
					self.encoding = encoding
				if errors:
					self.errors = errors
			else:
				handle_error(UserWarning(u"Warning - file '%s' not found" % 
										 safe_unicode(path)))
				return
			try:
				with codecs.open(path, "rU", self.encoding, self.errors) as f:
					self.parse(f)
			except (UnicodeDecodeError, ValueError), exception:
				if raise_exceptions:
					raise
				handle_error(UserWarning(
					u"Warning - file '%s': %s" % 
					tuple(safe_unicode(s) for s in 
						  (path, safe_unicode(exception).capitalize() if 
								 isinstance(exception, ValueError)
								 else exception))))
			except Exception, exception:
				if raise_exceptions:
					raise
				handle_error(UserWarning(u"Warning - file '%s': %s" % 
										 tuple(safe_unicode(s) for s in
											   (path, exception))))

	def parse(self, iterable):
		# Override this in subclass
		pass

	def pop(self, key, *args):
		self.load()
		return dict.pop(self, key, *args)

	def popitem(self, name, value):
		self.load()
		return dict.popitem(self, name, value)

	def setdefault(self, name, value=None):
		self.load()
		return dict.setdefault(self, name, value)
	
	def update(self, other):
		self.load()
		dict.update(self, other)
	
	def values(self):
		self.load()
		return dict.values(self)


class LazyDict_YAML_UltraLite(LazyDict):

	"""
	'YAML Ultra Lite' lazy dictionary

	YAML Ultra Lite is a restricted subset of YAML. It only supports the
	following notations:
	
	Key: Value 1
	"Key 2": "Value 2"
	"Key 3": |-
	  Value 3 Line 1
	  Value 3 Line 2
	
	All values are treated as strings.
	
	Syntax checking is limited for speed.
	Parsing is around a factor of 20 to 30 faster than PyYAML,
	around 8 times faster than JSONDict (based on demjson),
	and about 2 times faster than YAML_Lite.
	
	"""

	def __init__(self, path=None, encoding="UTF-8", errors="strict",
				 debug=False):
		LazyDict.__init__(self, path, encoding, errors)
		self.debug = debug

	def parse(self, fileobj):
		"""
		Parse fileobj and update dict
		
		"""
		value = []
		# Readlines is actually MUCH faster than iterating over the
		# file object
		for i, line in enumerate(fileobj.readlines()):
			if line.startswith("#"):
				# Ignore comments
				pass
			elif line != "\n" and not line.startswith("  "):
				if value:
					self[key] = "\n".join(value)
				#tokens = line.rstrip(' -|\n').split(":", 1)
				tokens = line.split(":", 1)
				if len(tokens) == 1:
					raise ValueError("Unsupported format (%r line %i)" %
									 (getattr(fileobj, "name", line), i))
				token = tokens[1].strip(" \n")
				if token.startswith("|-"):
					token = token[2:].lstrip()
				elif token.startswith("|") or token.startswith(">"):
					raise ValueError("Style not supported "
									 "(%r line %i)" % (getattr(fileobj, "name",
															   line), i))
				# key = tokens[0].strip("'"'"')
				key = self._unquote(tokens[0].strip(), False, False, fileobj, i)
				if token:
					# Inline value
					# value = [token.strip("'"'"')]
					value = [self._unquote(token, True, True, fileobj, i)]
				else:
					value = []
			else:
				value.append(line[2:].rstrip("\n"))
		if value:
			self[key] = "\n".join(value)

	def _unquote(self, token, unescape=True, check=True, fileobj=None, lineno=-1):
		if len(token) > 1:
			c = token[0]
			if c in "'"'"' and c == token[-1]:
				token = token[1:-1]
				if check and token.count(c) != token.count("\\" + c):
					raise ValueError("Unescaped quotes found in token "
									 "(%r line %i)" % (getattr(fileobj, "name",
															   token),
													   lineno))
			elif check and (token.count('"') != token.count('\\"')):
				raise ValueError("Unbalanced quotes found in token "
								 "(%r line %i)" % (getattr(fileobj, "name",
														   token),
												   lineno))
			if check and "\\'" in token:
				raise ValueError("Found unknown escape character \"'\" "
								 "(%r line %i)" % (getattr(fileobj, "name",
														   token),
												   lineno))
			if unescape:
				token = token.replace('\\"', '"')
		return token


class LazyDict_YAML_Lite(LazyDict_YAML_UltraLite):

	"""
	'YAML Lite' lazy dictionary

	YAML Lite is a restricted subset of YAML. It only supports the
	following notations:
	
	Key: Value 1
	"Key 2": "Value 2"
	"Key 3": |-
	  Value 3 Line 1
	  Value 3 Line 2
	"Key 4": |
	  Value 4 Line 1
	  Value 4 Line 2
	"Key 5": Folded value 5
	  Folded value 5, continued
	
	All values are treated as strings.
	
	Syntax checking is limited for speed.
	Parsing is around a factor of 12 to 16 faster than PyYAML,
	and around 4 times faster than JSONDict (based on demjson).
	
	"""

	def parse(self, fileobj):
		"""
		Parse fileobj and update dict
		
		"""
		style = None
		value = []
		block_styles = ("|", ">", "|-", ">-", "|+", ">+")
		quote = None
		key = None
		# Readlines is actually MUCH faster than iterating over the
		# file object
		for i, line in enumerate(fileobj.readlines()):
			line_lwstrip = line.lstrip(" ")
			if quote:
				line_rstrip = line.rstrip()
			if self.debug:
				print 'LINE', repr(line)
			if line.startswith("#"):
				# Ignore comments
				pass
			elif quote and line_rstrip and line_rstrip[-1] == quote:
				if self.debug:
					print "END QUOTE"
				if self.debug:
					print "+ APPEND STRIPPED", repr(line.strip())
				value.append(line.strip())
				self._collect(key, value, ">i")
				style = None
				value = []
				quote = None
				key = None
			elif (style not in block_styles and line.startswith(" ") and
				  line_lwstrip and line_lwstrip[0] in ("'", '"')):
				if quote:
					raise ValueError("Wrong end quote while scanning quoted "
									 "scalar (%r line %i)" %
									 (getattr(fileobj, "name", line), i))
				else:
					if self.debug:
						print "START QUOTE"
					quote = line_lwstrip[0]
					if self.debug:
						print "+ APPEND LWSTRIPPED", repr(line_lwstrip)
					value.append(line_lwstrip)
			elif line.startswith("  ") and (style in block_styles or
											line_lwstrip != "\n"):
				if style == ">i":
					if not quote and "\t" in line:
						raise ValueError("Found character '\\t' that cannot "
										 "start any token (%r line %i)" %
										 (getattr(fileobj, "name", line), i))
					line = line.strip() + "\n"
					if self.debug:
						print "APPEND STRIPPED + \\n", repr(line)
				else:
					line = line[2:]
					if self.debug:
						print "APPEND [2:]", repr(line)
				value.append(line)
			elif not quote and line_lwstrip != "\n" and not line.startswith(" "):
				if key and value:
					self._collect(key, value, style)
				tokens = line.split(":", 1)
				key = unquote(tokens[0].strip())
				if len(tokens) > 1:
					token = tokens[1].lstrip(" ").rstrip(" \n")
					style = token
					if style.startswith("\t"):
						raise ValueError("Found character '\\t' that cannot "
										 "start any token (%r line %i)" %
										 (getattr(fileobj, "name", line), i))
					if style.startswith(">"):
						raise NotImplementedError("Folded style is not "
												  "supported (%r line %i)" %
												  (getattr(fileobj, "name",
														   line), i))
				else:
					raise ValueError("Unsupported format (%r line %i)" %
									 (getattr(fileobj, "name", line), i))
				if style in block_styles or not style:
					# Block or folded
					if self.debug:
						print 'IN BLOCK', repr(key), style
					value = []
				else:
					# Inline value
					if self.debug:
						print 'IN PLAIN', repr(key), repr(token)
					style = None
					token_rstrip = token.rstrip()
					if (token_rstrip and token_rstrip[0] in ("'", '"') and
						(len(token_rstrip) < 2 or
						 token_rstrip[0] != token_rstrip[-1])):
						if self.debug:
							print "START QUOTE"
						quote = token_rstrip[0]
					else:
						style = ">i"
					token_rstrip += "\n"
					if self.debug:
						print "SET", repr(token_rstrip)
					value = [token_rstrip]
			else:
				#if line_lwstrip == "\n":
				if True:
					if self.debug:
						print "APPEND LWSTRIPPED", repr(line_lwstrip)
					line = line_lwstrip
				else:
					if self.debug:
						print "APPEND", repr(line)
				value.append(line)
		if quote:
			raise ValueError("EOF while scanning quoted scalar (%r line %i)" %
							 (getattr(fileobj, "name", line), i))
		if key and value:
			if self.debug:
				print "FINAL COLLECT"
			self._collect(key, value, style)

	def _collect(self, key, value, style=None):
		if self.debug:
			print 'COLLECT', key, value, style
		chars = "".join(value)
		if style != ">i":
			chars = chars.rstrip(" ")
		if not style or style.startswith(">"):
			if self.debug:
				print 'FOLD'
			out = ""
			state = 0
			for c in chars:
				#print repr(c), repr(state)
				if c == "\n":
					if state > 0:
						out += c
					state += 1
				else:
					if state == 1:
						out += " "
						state = 0
					if style == ">i":
						state = 0
					out += c
		else:
			out = chars
		out = out.lstrip(" ")
		if self.debug:
			print "OUT", repr(out)
		if not style:
			# Inline value
			out = out.rstrip()
		elif style.endswith("+"):
			# Keep trailing newlines
			if self.debug:
				print 'KEEP'
			pass
		else:
			out = out.rstrip("\n")
			if style == ">i":
				out = unquote(out)
			elif style.endswith("-"):
				# Chomp trailing newlines
				if self.debug:
					print 'CHOMP'
				pass
			else:
				# Clip trailing newlines (default)
				if self.debug:
					print 'CLIP'
				if chars.endswith("\n"):
					out += "\n"
		self[key] = out


def test():
	from StringIO import StringIO
	from time import time

	from jsondict import LazyDict_JSON

	# PyYAML
	import yaml

	def y(doc):
		try:
			return yaml.safe_load(StringIO(doc))
		except Exception, e:
			print "%s:" % e.__class__.__name__, e
			return e


	def l(doc):
		l = LazyDict_YAML_Lite(debug=True)
		try:
			l.parse(StringIO(doc))
		except Exception, e:
			print "%s:" % e.__class__.__name__, e
			return e
		return l


	def c(doc):
		print "-" * 80
		print repr(doc)
		a = l(doc)
		print 'LazyDict_YAML_Lite', a
		b = y(doc)
		print 'yaml.YAML         ', b
		identical = isinstance(a, dict) and isinstance(b, dict) and a == b
		print 'Identical?', identical
		assert identical


	print "Testing YAML Lite to YAML conformance"
	c('TEST: \n  "ABC\n\n  DEF\n"  \n    \n\n\n\n')
	c('TEST: \n  "ABC\n\n  DEF"')
	c('TEST: \n  "ABC\n  DEF\n"')
	c('TEST: \n  "ABC\n\n  DEF\tG\n  \n    \n\n\n\n \t"')
	c('TEST: \n  ABC\n\n  DEFG\n  \n    \n\n\n\n')
	c('TEST: \n  "ABC\n\n  DEF\n"')
	c('TEST: \n  ABC\n\n DEFG\n  \n    \n\n\n\n ')
	c('TEST: \n  "ABC\n\n DEF\tG\n  \n    \n\n\n\n" ')
	c('TEST: |\n  ABC\n\n  DEFG\n  \n    \n\n\n\n')
	c('TEST: |+\n  ABC\n\n  DEFG\n  \n    \n\n\n\n')
	c('TEST: |-\n  ABC\n\n  DEFG\n  \n    \n\n\n\n')
	# c('TEST: >\n  ABC\n\n  DEFG\n  \n    \n\n\n\n')
	# c('TEST: >+\n  ABC\n\n  DEFG\n  \n    \n\n\n\n')
	# c('TEST: >-\n  ABC\n\n  DEFG\n  \n    \n\n\n\n')
	c('TEST: "\n ABC\n\n  DEFG\n  \n    \n\n\n\n"')
	c('TEST: |\n  ABC\n\n  DEFG\n  \n    \n\n\n\n ')
	c('TEST: |+\n  ABC\n\n  DEFG\n  \n    \n\n\n\n ')
	c('TEST: |-\n  ABC\n\n  DEFG\n  \n    \n\n\n\n ')
	# c('TEST: >\n  ABC\n\n  DEFG\n  \n    \n\n\n\n ')
	# c('TEST: >+\n  ABC\n\n  DEFG\n  \n    \n\n\n\n ')
	# c('TEST: >-\n  ABC\n\n  DEFG\n  \n    \n\n\n\n ')
	c('TEST : |\n  "\n  ABC\n\n  DEFG\n  \n    \n\n\n\n  "')
	c('TEST: |-\n  \n  ABC\n\n  DEFG\n  \n    \n\n\n\n ')
	c('TEST: |\n  \n  ABC\n\n  DEFG\n  \n    \n\n\n\n ')
	c('TEST:\n  \n  ABC\n\n  DEFG\n  \n    \n\n\n\n ')

	print "=" * 80
	print "Performance test"

	io = StringIO('''{"test1": "Value 1",
"test2": "Value 2 Line 1\\nValue 2 Line 2\\n\\nValue 2 Line 4\\n",
"test3": "Value 3 Line 1\\n",
"test4": "Value 4"}
''')

	d = LazyDict_JSON()
	ts = time()
	for i in xrange(10000):
		d.parse(io)
		io.seek(0)
	jt = time() - ts

	io = StringIO('''"test1": Value 1
"test2": |-
  Value 2 Line 1
  Value 2 Line 2
  
  Value 2 Line 4
"test3": |-
  Value 3 Line 1
"test4": "Value 4"
''')

	d = LazyDict_YAML_UltraLite()
	ts = time()
	for i in xrange(10000):
		d.parse(io)
		io.seek(0)
	yult = time() - ts

	d = LazyDict_YAML_Lite()
	ts = time()
	for i in xrange(10000):
		d.parse(io)
		io.seek(0)
	ylt = time() - ts

	ts = time()
	for i in xrange(10000):
		yaml.safe_load(io)
		io.seek(0)
	yt = time() - ts

	print "LazyDict_JSON:", jt
	print "LazyDict_YAML_UltraLite: %.3fs," % yult, "vs JSON: %.1fx speed," % round(jt / yult, 1), "vs YAML_Lite: %.1fx speed," % round(ylt / yult, 1), "vs PyYAML: %.1fx speed," % round(yt / yult, 1)
	print "LazyDict_YAML_Lite: %.3fs," % ylt, "vs JSON: %.1fx speed," % round(jt / ylt, 1), "vs PyYAML: %.1fx speed," % round(yt / ylt, 1)
	print "yaml.safe_load: %.3fs," % yt


if __name__ == "__main__":
	test()
