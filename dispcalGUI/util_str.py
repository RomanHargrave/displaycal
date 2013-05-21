#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import codecs
import locale
import string
import sys
try:
	from functools import reduce
except ImportError:
	# Python < 2.6
	pass

from encoding import get_encodings

fs_enc = get_encodings()[1]

ascii_printable = "".join([getattr(string, name) for name in "digits", 
						   "ascii_letters", "punctuation", "whitespace"])

# Control chars are defined as charcodes in the decimal range 0-31 (inclusive) 
# except whitespace characters, plus charcode 127 (DEL)
control_chars = "".join([chr(i) for i in range(0, 9) + range(14, 32) + [127]])

# Safe character substitution - can be used for filenames
# i.e. no \/:*?"<>| will be added through substitution
safesubst = {u"\u00a9": u"(C)", # U+00A9 copyright sign
			 u"\u00ae": u"(R)", # U+00AE registered sign
			 u"\u00b1": u"+-",
			 u"\u00b2": u"^2", # U+00B2 superscript two
			 u"\u00b3": u"^3", # U+00B3 superscript three
			 u"\u00b9": u"^1", # U+00B9 superscript one
			 u"\u00d7": u"x", # U+00D7 multiplication sign
			 u"\u00df": u"ss",
			 u"\u00e6": u"ae",
			 u"\u0153": u"oe",
			 u"\u0192": u"f",
			 u"\u02dc": u"~",
			 u"\u02c6": u"^",
			 u"\u2010": u"-",
			 u"\u2012": u"-",
			 u"\u2013": u"-", # U+2013 en dash
			 u"\u2014": u"--", # U+2014 em dash
			 u"\u2015": u"---", # U+2015 horizontal bar
			 u"\u2018": u"'",
			 u"\u2019": u"'",
			 u"\u201a": u",",
			 u"\u201b": u"'",
			 u"\u201e": u",,",
			 u"\u2026": u"...", # U+2026 ellipsis
			 u"\u2034": u"'''",
			 u"\u203C": u"!!",
			 u"\u2070": u"^0",
			 u"\u2074": u"^4",
			 u"\u2075": u"^5",
			 u"\u2076": u"^6",
			 u"\u2077": u"^7",
			 u"\u2078": u"^8",
			 u"\u2079": u"^9",
			 u"\u20a7": u"Pts",
			 u"\u20a8": u"Rs",
			 u"\u2113": u"l",
			 u"\u2116": u"No.",
			 u"\u2117": u"(P)",
			 u"\u2122": u"TM",
			 u"\u2212": u"-",
			 u"\u2260": u"!=",
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
			 u"\ufb01": u"fi",
			 u"\ufb02": u"fl",} # U+2212 minus sign

# Extended character substitution - can NOT be used for filenames
subst = dict(safesubst)
subst.update({u"\u00a6": u"|",
			  u"\u00ab": u"<<",
			  u"\u00bb": u">>",
			  u"\u00bc": u"1/4",
			  u"\u00bd": u"1/2",
			  u"\u00be": u"3/4",
			  u"\u00f7": u":",
			  u"\u201c": u"\x22",
			  u"\u201d": u"\x22",
			  u"\u201f": u"\x22",
			  u"\u2039": u"<",
			  u"\u203a": u">",
			  u"\u2044": u"/",
			  u"\u2105": u"c/o",
			  u"\u2153": u"1/3",
			  u"\u2154": u"2/3",
			  u"\u215b": u"1/8",
			  u"\u215c": u"3/8",
			  u"\u215d": u"5/8",
			  u"\u215e": u"7/8",
			  u"\u2190": u"<-",
			  u"\u2192": u"->",
			  u"\u2194": u"<->",
			  u"\u2264": u"<=",
			  u"\u2265": u"=>",})

def asciize(obj):
	"""
	Turn several unicode chars into an ASCII representation.
	
	This function either takes a string or an exception as argument (when used 
	as error handler for encode or decode).
	
	"""
	chars = u""
	if isinstance(obj, Exception):
		for char in obj.object[obj.start:obj.end]:
			chars += subst.get(char, u"?")
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
			chars += safesubst.get(char, u"_")
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
			chars += subst.get(char, u"\\u" % hex(ord(char))[2:])
		return chars, obj.end
	else:
		return obj.encode("ASCII", "escape")

codecs.register_error("escape", escape)


def make_ascii_printable(text, subst=""):
	return "".join([char if char in ascii_printable else subst for char in text])


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
		for i, group in enumerate(match.groups()):
			template = template.replace("\\%i" % (i + 1), group)
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
	if isinstance(obj, EnvironmentError) and obj.filename:
		obj = u"[Error %i] %s: %s" % (obj.errno, obj.strerror, obj.filename)
	elif not isinstance(obj, basestring):
		try:
			obj = unicode(obj)
		except UnicodeDecodeError:
			try:
				obj = str(obj)
			except UnicodeEncodeError:
				obj = repr(obj)
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
	
	replacements can be a dict or a list.
	If it is a list, all items are replaced with the empty string ("").
	
	"""
	if hasattr(replacements, "iteritems"):
		replacements = replacements.iteritems()
	else:
		replacements = zip(replacements, [""] * len(replacements))
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
