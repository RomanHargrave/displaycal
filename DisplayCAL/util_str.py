# -*- coding: utf-8 -*-

import codecs
import exceptions
import locale
import re
import string
import sys
import unicodedata
try:
	from functools import reduce
except ImportError:
	# Python < 2.6
	pass

env_errors = (EnvironmentError, )
if sys.platform == "win32":
	import pywintypes
	env_errors = env_errors + (pywintypes.error, pywintypes.com_error)

from encoding import get_encodings

fs_enc = get_encodings()[1]

ascii_printable = "".join([getattr(string, name) for name in "digits", 
						   "ascii_letters", "punctuation", "whitespace"])

# Control chars are defined as charcodes in the decimal range 0-31 (inclusive) 
# except whitespace characters, plus charcode 127 (DEL)
control_chars = "".join([chr(i) for i in range(0, 9) + range(14, 32) + [127]])

# Safe character substitution - can be used for filenames
# i.e. no \/:*?"<>| will be added through substitution
# Contains only chars that are not normalizable
safesubst = {# Latin-1 supplement
			 u"\u00a2": u"c", # Cent sign
			 u"\u00a3": u"GBP", # Pound sign
			 u"\u00a5": u"JPY", # Yen sign
			 u"\u00a9": u"(C)", # U+00A9 copyright sign
			 u"\u00ac": u"!", # Not sign
			 u"\u00ae": u"(R)", # U+00AE registered sign
			 u"\u00b0": u"deg", # Degree symbol
			 u"\u00b1": u"+-",
			 u"\u00c4": u"Ae", # Capital letter A with diaresis (Umlaut)
			 u"\u00c5": u"Aa", # Capital letter A with ring above
			 u"\u00c6": u"AE",
			 u"\u00d6": u"Oe", # Capital letter O with diaresis (Umlaut)
			 u"\u00dc": u"Ue", # Capital letter U with diaresis (Umlaut)
			 u"\u00d7": u"x", # U+00D7 multiplication sign
			 u"\u00df": u"ss",
			 u"\u00e4": u"ae", # Small letter a with diaresis (Umlaut)
			 u"\u00e5": u"aa", # Small letter a with ring above
			 u"\u00e6": u"ae",
			 u"\u00f6": u"oe", # Small letter o with diaresis (Umlaut)
			 u"\u00fc": u"ue", # Small letter u with diaresis (Umlaut)
			 # Latin extended A
			 u"\u0152": u"OE",
			 u"\u0153": u"oe",
			 # General punctuation
			 u"\u2010": u"-",
			 u"\u2011": u"-",
			 u"\u2012": u"-",
			 u"\u2013": u"-", # U+2013 en dash
			 u"\u2014": u"--", # U+2014 em dash
			 u"\u2015": u"---", # U+2015 horizontal bar
			 u"\u2018": u"'",
			 u"\u2019": u"'",
			 u"\u201a": u",",
			 u"\u201b": u"'",
			 u"\u201c": u"''",
			 u"\u201d": u"''",
			 u"\u201e": u",,",
			 u"\u201f": u"''",
			 u"\u2032": u"'",
			 u"\u2033": u"''",
			 u"\u2034": u"'''",
			 u"\u2035": u"'",
			 u"\u2036": u"''",
			 u"\u2037": u"'''",
			 u"\u2053": u"~",
			 # Superscripts and subscripts
			 u"\u207b": u"-", # Superscript minus
			 u"\u208b": u"-", # Subscript minus
			 # Currency symbols
			 u"\u20a1": u"CRC", # Costa Rica 'Colon'
			 u"\u20a6": u"NGN", # Nigeria 'Naira'
			 u"\u20a9": u"KRW", # South Korea 'Won'
			 u"\u20aa": u"ILS", # Isreael 'Sheqel'
			 u"\u20ab": u"VND", # Vietnam 'Dong'
			 u"\u20ac": u"EUR",
			 u"\u20ad": u"LAK", # Laos 'Kip'
			 u"\u20ae": u"MNT", # Mongolia 'Tugrik'
			 u"\u20b2": u"PYG", # Paraguay 'Guarani'
			 u"\u20b4": u"UAH", # Ukraine 'Hryvnja'
			 u"\u20b5": u"GHS", # Ghana 'Cedi'
			 u"\u20b8": u"KZT", # Kasachstan 'Tenge'
			 u"\u20b9": u"INR", # Indian 'Rupee'
			 u"\u20ba": u"TRY", # Turkey 'Lira'
			 u"\u20bc": u"AZN", # Aserbaidchan 'Manat'
			 u"\u20bd": u"RUB", # Russia 'Ruble'
			 u"\u20be": u"GEL", # Georgia 'Lari'
			 # Letter-like symbols
			 u"\u2117": u"(P)",
			 # Mathematical operators
			 u"\u2212": u"-", # U+2212 minus sign
			 u"\u2260": u"!=",
			 # Enclosed alphanumerics
			 u"\u2460": u"(1)",
			 u"\u2461": u"(2)",
			 u"\u2462": u"(3)",
			 u"\u2463": u"(4)",
			 u"\u2464": u"(5)",
			 u"\u2465": u"(6)",
			 u"\u2466": u"(7)",
			 u"\u2467": u"(8)",
			 u"\u2468": u"(9)",
			 u"\u2469": u"(10)",
			 u"\u246a": u"(11)",
			 u"\u246b": u"(12)",
			 u"\u246c": u"(13)",
			 u"\u246d": u"(14)",
			 u"\u246e": u"(15)",
			 u"\u246f": u"(16)",
			 u"\u2470": u"(17)",
			 u"\u2471": u"(18)",
			 u"\u2472": u"(19)",
			 u"\u2473": u"(20)",
			 u"\u24eb": u"(11)",
			 u"\u24ec": u"(12)",
			 u"\u24ed": u"(13)",
			 u"\u24ee": u"(14)",
			 u"\u24ef": u"(15)",
			 u"\u24f0": u"(16)",
			 u"\u24f1": u"(17)",
			 u"\u24f2": u"(18)",
			 u"\u24f3": u"(19)",
			 u"\u24f4": u"(20)",
			 u"\u24f5": u"(1)",
			 u"\u24f6": u"(2)",
			 u"\u24f7": u"(3)",
			 u"\u24f8": u"(4)",
			 u"\u24f9": u"(5)",
			 u"\u24fa": u"(6)",
			 u"\u24fb": u"(7)",
			 u"\u24fc": u"(8)",
			 u"\u24fd": u"(9)",
			 u"\u24fe": u"(10)",
			 u"\u24ff": u"(0)",
			 # Dingbats
			 u"\u2776": u"(1)",
			 u"\u2777": u"(2)",
			 u"\u2778": u"(3)",
			 u"\u2779": u"(4)",
			 u"\u277a": u"(5)",
			 u"\u277b": u"(6)",
			 u"\u277c": u"(7)",
			 u"\u277d": u"(8)",
			 u"\u277e": u"(9)",
			 u"\u277f": u"(10)",
			 u"\u2780": u"(1)",
			 u"\u2781": u"(2)",
			 u"\u2782": u"(3)",
			 u"\u2783": u"(4)",
			 u"\u2784": u"(5)",
			 u"\u2785": u"(6)",
			 u"\u2786": u"(7)",
			 u"\u2787": u"(8)",
			 u"\u2788": u"(9)",
			 u"\u2789": u"(10)",
			 u"\u278a": u"(1)",
			 u"\u278b": u"(2)",
			 u"\u278c": u"(3)",
			 u"\u278d": u"(4)",
			 u"\u278e": u"(5)",
			 u"\u278f": u"(6)",
			 u"\u2790": u"(7)",
			 u"\u2791": u"(8)",
			 u"\u2792": u"(9)",
			 u"\u2793": u"(10)",}

# Extended character substitution - can NOT be used for filenames
# Contains only chars that are not normalizable
subst = dict(safesubst)
subst.update({# Latin-1 supplement
			  u"\u00a6": u"|",
			  u"\u00ab": u"<<",
			  u"\u00bb": u">>",
			  u"\u00bc": u"1/4",
			  u"\u00bd": u"1/2",
			  u"\u00be": u"3/4",
			  u"\u00f7": u":",
			  # General punctuation
			  u"\u201c": u"\x22",
			  u"\u201d": u"\x22",
			  u"\u201f": u"\x22",
			  u"\u2033": u"\x22",
			  u"\u2036": u"\x22",
			  u"\u2039": u"<",
			  u"\u203a": u">",
			  u"\u203d": u"!?",
			  u"\u2044": u"/",
			  # Number forms
			  u"\u2153": u"1/3",
			  u"\u2154": u"2/3",
			  u"\u215b": u"1/8",
			  u"\u215c": u"3/8",
			  u"\u215d": u"5/8",
			  u"\u215e": u"7/8",
			  # Arrows
			  u"\u2190": u"<-",
			  u"\u2192": u"->",
			  u"\u2194": u"<->",
			  # Mathematical operators
			  u"\u226a": u"<<",
			  u"\u226b": u">>",
			  u"\u2264": u"<=",
			  u"\u2265": u"=>",})


class StrList(list):
	
	""" It's a list. It's a string. It's a list of strings that behaves like a
	string! And like a list."""

	def __init__(self, seq=tuple()):
		list.__init__(self, seq)

	def __iadd__(self, text):
		self.append(text)
		return self

	def __getattr__(self, attr):
		return getattr(str(self), attr)

	def __str__(self):
		return "".join(self)


def asciize(obj):
	"""
	Turn several unicode chars into an ASCII representation.
	
	This function either takes a string or an exception as argument (when used 
	as error handler for encode or decode).
	
	"""
	chars = u""
	if isinstance(obj, Exception):
		for char in obj.object[obj.start:obj.end]:
			chars += subst.get(char, normalencode(char).strip() or u"?")
		return chars, obj.end
	else:
		return obj.encode("ASCII", "asciize")

codecs.register_error("asciize", asciize)


def safe_asciize(obj):
	"""
	Turn several unicode chars into an ASCII representation.
	
	This function either takes a string or an exception as argument (when used 
	as error handler for encode or decode).
	
	"""
	chars = u""
	if isinstance(obj, Exception):
		for char in obj.object[obj.start:obj.end]:
			if char in safesubst:
				subst_char = safesubst[char]
			else:
				subst_char = u"_"
				if char not in subst:
					subst_char = normalencode(char).strip() or subst_char
			chars += subst_char
		return chars, obj.end
	else:
		return obj.encode("ASCII", "safe_asciize")

codecs.register_error("safe_asciize", safe_asciize)


def escape(obj):
	"""
	Turn unicode chars into escape codes.
	
	This function either takes a string or an exception as argument (when used 
	as error handler for encode or decode).
	
	"""
	chars = u""
	if isinstance(obj, Exception):
		for char in obj.object[obj.start:obj.end]:
			chars += subst.get(char, u"\\u%s" % hex(ord(char))[2:].rjust(4, '0'))
		return chars, obj.end
	else:
		return obj.encode("ASCII", "escape")

codecs.register_error("escape", escape)


def make_ascii_printable(text, subst=""):
	return "".join([char if char in ascii_printable else subst for char in text])


def make_filename_safe(unistr, encoding=fs_enc, subst="_", concat=True):
	"""
	Make sure unicode string is safe to use as filename.
	
	I.e. turn characters that are invalid in the filesystem encoding into ASCII
	equivalents and replace characters that are invalid in filenames with
	substitution character.
	
	"""
	# Turn characters that are invalid in the filesystem encoding into ASCII
	# substitution character '?'
	# NOTE that under Windows, encoding with the filesystem encoding may
	# substitute some characters even in "strict" replacement mode depending
	# on the Windows language setting for non-Unicode programs! (Python 2.x
	# under Windows supports Unicode by wrapping the win32 ASCII API, so it is
	# a non-Unicode program from that point of view. This problem presumably
	# doesn't exist with Python 3.x which uses the win32 Unicode API)
	unidec = unistr.encode(encoding, "replace").decode(encoding)
	# Replace substitution character '?' with ASCII equivalent of original char
	uniout = u""
	for i, c in enumerate(unidec):
		if c == u"?":
			# Note: We prevent IndexError by using slice notation which will
			# return an empty string if unistr should be somehow shorter than
			# unidec. Technically, this should never happen, but who knows
			# what hidden bugs and quirks may linger in the Python 2.x Unicode
			# implementation...
			c = safe_asciize(unistr[i:i + 1])
		uniout += c
	# Remove invalid chars
	pattern = r"[\\/:*?\"<>|]"
	if concat:
		pattern += "+"
	uniout = re.sub(pattern, subst, uniout)
	return uniout


def normalencode(unistr, form="NFKD", encoding="ASCII", errors="ignore"):
	"""
	Return encoded normal form of unicode string
	
	"""
	return unicodedata.normalize(form, unistr).encode(encoding, errors)


def box(text, width=80, collapse=False):
	"""
	Create a box around text (monospaced font required for display)
	
	"""
	content_width = width - 4
	text = wrap(safe_unicode(text), content_width)
	lines = text.splitlines()
	if collapse:
		content_width = 0
		for line in lines:
			content_width = max(len(line), content_width)
		width = content_width + 4
	horizontal_line = u"\u2500" * (width - 2)
	box = [u"\u250c%s\u2510" % horizontal_line]
	for line in lines:
		box.append(u"\u2502 %s \u2502" % line.ljust(content_width))
	box.append(u"\u2514%s\u2518" % horizontal_line)
	return "\n".join(box)


def center(text, width = None):
	"""
	Center (mono-spaced) text.
	
	If no width is given, the longest line 
	(after breaking at each newline) is used as max width.
	
	"""
	text = text.split("\n")
	if width is None:
		width = 0
		for line in text:
			if len(line) > width:
				width = len(line)
	i = 0
	for line in text:
		text[i] = line.center(width)
		i += 1
	return "\n".join(text)


def create_replace_function(template, values):
	""" Create a replace function for use with e.g. re.sub """
	def replace_function(match, template=template, values=values):
		template = match.expand(template)
		return template % values
	return replace_function


def ellipsis(text, maxlen=64, pos="r"):
	""" Truncate text to maxlen characters and add elipsis if it was longer.
	
	Elipsis position can be 'm' (middle) or 'r' (right).
	
	"""
	if len(text) <= maxlen:
		return text
	if pos == "r":
		return text[:maxlen - 1] + u"\u2026"
	elif pos == "m":
		return text[:maxlen / 2] + u"\u2026" + text[-maxlen / 2 + 1:]


def hexunescape(match):
	""" To be used with re.sub """
	return unichr(int(match.group(1), 16))


def indent(text, prefix, predicate=None):
	# From Python 3.7 textwrap module
    """Adds 'prefix' to the beginning of selected lines in 'text'.

    If 'predicate' is provided, 'prefix' will only be added to the lines
    where 'predicate(line)' is True. If 'predicate' is not provided,
    it will default to adding 'prefix' to all non-empty lines that do not
    consist solely of whitespace characters.
    """
    if predicate is None:
        def predicate(line):
            return line.strip()

    def prefixed_lines():
        for line in text.splitlines(True):
            yield (prefix + line if predicate(line) else line)
    return ''.join(prefixed_lines())


def universal_newlines(txt):
	"""
	Return txt with all new line formats converted to POSIX newlines.
	
	"""
	return txt.replace("\r\n", "\n").replace("\r", "\n")


def replace_control_chars(txt, replacement=" ", collapse=False):
	""" Replace all control characters.
	
	Default replacement character is ' ' (space).
	If the 'collapse' keyword argument evaluates to True, consecutive
	replacement characters are collapsed to a single one.
	
	"""
	txt = strtr(txt, dict(zip(control_chars, [replacement] * len(control_chars))))
	if collapse:
		while replacement * 2 in txt:
			txt = txt.replace(replacement * 2, replacement)
	return txt


def safe_basestring(obj):
	"""
	Return a unicode or string representation of obj
	
	Return obj if isinstance(obj, basestring). Otherwise, return unicode(obj), 
	string(obj), or repr(obj), whichever succeeds first.
	
	"""
	if isinstance(obj, env_errors):
		# Possible variations of environment-type errors:
		# - instance with 'errno', 'strerror', 'filename' and 'args' attributes
		#   (created by EnvironmentError with three arguments)
		#   NOTE: The 'args' attribute will contain only the first two arguments
		# - instance with 'errno', 'strerror' and 'args' attributes
		#   (created by EnvironmentError with two arguments)
		# - instance with just 'args' attribute
		#   (created by EnvironmentError with one or more than three arguments)
		# - urllib2.URLError with empty 'args' attribute but 'reason' and
		#   'filename' attributes
		# - pywintypes.error with 'funcname', 'message', 'strerror', 'winerror'
		#   and 'args' attributes
		if hasattr(obj, "reason"):
			if isinstance(obj.reason, basestring):
				obj.args = (obj.reason, )
			else:
				obj.args = obj.reason
		error = []
		if getattr(obj, "winerror", None) is not None:
			# pywintypes.error or WindowsError
			error.append("[Windows Error %s]" % obj.winerror)
		elif getattr(obj, "errno", None) is not None:
			error.append("[Errno %s]" % obj.errno)
		if getattr(obj, "strerror", None) is not None:
			if getattr(obj, "filename", None) is not None:
				error.append(obj.strerror.rstrip(":.") + ":")
			elif getattr(obj, "funcname", None) is not None:
				# pywintypes.error
				error.append(obj.funcname + ": " + obj.strerror)
			else:
				error.append(obj.strerror)
		if not error:
			error = list(obj.args)
		if getattr(obj, "filename", None) is not None:
			error.append(obj.filename)
		error = [safe_unicode(arg) for arg in error]
		obj = " ".join(error)
	elif isinstance(obj, KeyError) and obj.args:
		obj = "Key does not exist: " + repr(obj.args[0])
	oobj = obj
	if not isinstance(obj, basestring):
		try:
			obj = unicode(obj)
		except UnicodeDecodeError:
			try:
				obj = str(obj)
			except UnicodeEncodeError:
				obj = repr(obj)
	if isinstance(oobj, Exception) and not isinstance(oobj, Warning):
		if obj and oobj.__class__.__name__ in dir(exceptions):
			obj = obj[0].capitalize() + obj[1:]
		module = getattr(oobj, "__module__", "")
		package = safe_basestring.__module__.split(".")[0]  # Our own package
		if not module.startswith(package + "."):
			clspth = ".".join(filter(None, [module, oobj.__class__.__name__]))
			if not obj.startswith(clspth + ":") and obj != clspth:
				obj = ": ".join(filter(None, [clspth, obj]))
	return obj


def safe_str(obj, enc=fs_enc, errors="replace"):
	""" Return string representation of obj """
	obj = safe_basestring(obj)
	if isinstance(obj, unicode):
		return obj.encode(enc, errors)
	else:
		return obj


def safe_unicode(obj, enc=fs_enc, errors="replace"):
	""" Return unicode representation of obj """
	obj = safe_basestring(obj)
	if isinstance(obj, unicode):
		return obj
	else:
		return obj.decode(enc, errors)


def strtr(txt, replacements):
	"""
	String multi-replace, a bit like PHP's strtr.
	
	replacements can be a dict, a list or a string.
	If list or string, all matches are replaced with the empty string ("").
	
	"""
	if hasattr(replacements, "iteritems"):
		replacements = replacements.iteritems()
	elif isinstance(replacements, basestring):
		for srch in replacements:
			txt = txt.replace(srch, "")
		return txt
	for srch, sub in replacements:
		txt = txt.replace(srch, sub)
	return txt


def wrap(text, width = 70):
	"""
	A word-wrap function that preserves existing line breaks and spaces.
	
	Expects that existing line breaks are posix newlines (\\n).
	
	"""
	return reduce(lambda line, word, width=width: '%s%s%s' %
		(line,
		' \n'[(len(line)-line.rfind('\n')-1
			+ len(word.split('\n',1)[0]
				) >= width)],
		word),
		text.split(' ')
		)


def test():
	for k, v in subst.iteritems():
		print k, v

if __name__ == "__main__":
	test()
