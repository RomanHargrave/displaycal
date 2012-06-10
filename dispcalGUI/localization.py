#!/usr/bin/env python
# -*- coding: utf-8 -*-

import __builtin__
import locale
import os

import demjson

from config import data_dirs, defaults, getcfg, storage
from debughelpers import handle_error
from jsondict import JSONDict
from log import safe_print
from util_os import expanduseru
from util_str import safe_unicode


def init(set_wx_locale=False):
	"""
	Populate translation dict with found language strings and set locale.
	
	If set_wx_locale is True, set locale also for wxPython.
	
	"""
	langdirs = []
	for dir_ in data_dirs:
		langdirs += [os.path.join(dir_, "lang")]
	for langdir in langdirs:
		if os.path.exists(langdir) and os.path.isdir(langdir):
			try:
				langfiles = os.listdir(langdir)
			except Exception, exception:
				safe_print(u"Warning - directory '%s' listing failed: %s" % 
						   tuple(safe_unicode(s) for s in (langdir, exception)))
			else:
				for filename in langfiles:
					name, ext = os.path.splitext(filename)
					if ext.lower() == ".json" and name.lower() not in ldict:
						path = os.path.join(langdir, filename)
						ldict[name.lower()] = JSONDict(path)
	if len(ldict) == 0:
		handle_error("Warning: No language files found. The following "
					 "places have been searched:\n%s" % "\n".join(langdirs))


def update_defaults():
	defaults.update({
		"last_3dlut_path": os.path.join(expanduseru("~"), getstr("unnamed")),
		"last_cal_path": os.path.join(storage, getstr("unnamed")),
		"last_cal_or_icc_path": os.path.join(storage, getstr("unnamed")),
		"last_colorimeter_ti3_path": os.path.join(expanduseru("~"),
												  getstr("unnamed")),
		"last_filedialog_path": os.path.join(expanduseru("~"),
											 getstr("unnamed")),
		"last_icc_path": os.path.join(storage, getstr("unnamed")),
		"last_reference_ti3_path": os.path.join(expanduseru("~"),
												getstr("unnamed")),
		"last_ti1_path": os.path.join(storage, getstr("unnamed")),
		"last_ti3_path": os.path.join(storage, getstr("unnamed"))
	})


def getcode():
	""" Get language code from config """
	lcode = getcfg("lang")
	if not lcode in ldict:
		# fall back to default
		lcode = defaults["lang"]
	if not lcode in ldict:
		# fall back to english
		lcode = "en"
	return lcode


def getstr(id_str, strvars=None, lcode=None):
	""" Get a translated string from the dictionary """
	if not lcode:
		lcode = getcode()
	if not lcode in ldict or not id_str in ldict[lcode]:
		# fall back to english
		lcode = "en"
	if lcode in ldict and id_str in ldict[lcode]:
		lstr = ldict[lcode][id_str]
		if strvars is not None:
			if type(strvars) not in (list, tuple):
				strvars = (strvars, )
			if lstr.count("%s") == len(strvars):
				lstr %= tuple(safe_unicode(s) for s in strvars)
		return lstr
	else:
		return id_str


def gettext(text):
	if not catalog and defaults["lang"] in ldict:
		for id_str in ldict[defaults["lang"]]:
			lstr = ldict[defaults["lang"]][id_str]
			catalog[lstr] = {}
			catalog[lstr].id_str = id_str
	lcode = getcode()
	if catalog and text in catalog and not lcode in catalog[text]:
		catalog[text][lcode] = ldict[lcode].get(catalog[text].id_str, text)
	return catalog.get(text, {}).get(lcode, text)


ldict = {}
catalog = {}
