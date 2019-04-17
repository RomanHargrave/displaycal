# -*- coding: utf-8 -*-

from __future__ import with_statement
import codecs
import os

from config import get_data_path
from debughelpers import handle_error
from util_str import safe_unicode


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

	def load(self):
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


class LazyDict_YAML_Lite(LazyDict):

	"""
	YAML Lite lazy dictionary
	
	"""

	def load(self, path=None, encoding=None, errors=None):
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
				handle_error(UserWarning(u"Warning - YAML Lite file '%s' not found" % 
										 safe_unicode(path)))
				return
			try:
				with codecs.open(path, "rU", self.encoding, self.errors) as f:
					value = []
					for line in f.readlines():
						if line.startswith("#"):
							# Ignore comments
							pass
						elif line and not line.startswith("  "):
							if value:
								self[key] = "\n".join(value)
							tokens = line.rstrip(' ->|\r\n').split(":", 1)
							key = tokens[0].strip("'"'"')
							token = tokens[1].strip()
							if token:
								# Inline value
								self[key] = token
							value = []
						else:
							value.append(line.strip())
					if value:
						self[key] = "\n".join(value)
			except (UnicodeDecodeError, 
					YAML_Lite_DecodeError), exception:
				handle_error(UserWarning(
					u"Warning - YAML Lite file '%s': %s" % 
					tuple(safe_unicode(s) for s in 
						  (path, safe_unicode(exception).capitalize() if 
								 isinstance(exception, 
											YAML_Lite_DecodeError)
								 else exception))))
			except Exception, exception:
				handle_error(UserWarning(u"Warning - YAML Lite file '%s': %s" % 
										 tuple(safe_unicode(s) for s in
											   (path, exception))))
