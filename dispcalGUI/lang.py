#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

import demjson

from config import data_dirs, getcfg
from debughelpers import handle_error
from log import safe_print

ldict = {} # language strings dictionary

def init():
	""" Populate ldict with found language strings """
	langdirs = []
	for dir_ in data_dirs:
		langdirs += [os.path.join(dir_, "lang")]
	for langdir in langdirs:
		if os.path.exists(langdir) and os.path.isdir(langdir):
			try:
				langfiles = os.listdir(langdir)
			except Exception, exception:
				safe_print("Warning - directory '%s' listing failed: %s" % (langdir, str(exception)))
			else:
				for filename in langfiles:
					name, ext = os.path.splitext(filename)
					if ext.lower() == ".json" and name.lower() not in ldict:
						langfilename = os.path.join(langdir, filename)
						try:
							langfile = open(langfilename, "rU")
							try:
								ltxt = unicode(langfile.read(), "UTF-8")
								ldict[name.lower()] = demjson.decode(ltxt)
							except (UnicodeDecodeError, demjson.JSONDecodeError), \
							   exception:
								handle_error("Warning - language file '%s': %s" % 
									(langfilename, 
									exception.args[0].capitalize() if type(exception) == 
									demjson.JSONDecodeError else 
									str(exception))
									)
						except Exception, exception:
							handle_error("Warning - language file '%s': %s" % 
								(langfilename, str(exception)))
						else:
							langfile.close()
	if len(ldict) == 0:
		handle_error("Warning: No valid language files found. The following "
			"places have been searched:\n%s" % "\n".join(langdirs))

def getstr(id_str, strvars = None, lcode = None):
	""" Get a translated string from the dictionary """
	if not lcode:
		lcode = getcfg("lang")
	if not lcode in ldict or not id_str in ldict[lcode]:
		# fall back to english
		lcode = "en"
	if lcode in ldict and id_str in ldict[lcode]:
		lstr = ldict[lcode][id_str]
		if strvars:
			if type(strvars) not in (list, tuple):
				strvars = (strvars, )
			if lstr.count("%s") == len(strvars):
				lstr %= strvars
		return lstr
	else:
		return id_str
