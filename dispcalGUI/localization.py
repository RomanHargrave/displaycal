#!/usr/bin/env python
# -*- coding: utf-8 -*-

import __builtin__
import locale
import os

import demjson

from config import data_dirs, defaults, getcfg, storage
from debughelpers import handle_error
from log import safe_print

class TranslationDict(dict):

	"""
	Translation dictionary with key -> translated string mappings.
	
	The actual translations are loaded from the source JSON file when they
	are accessed.
	
	"""

	def __init__(self, path):
		dict.__init__(self)
		self.loaded = False
		self.path = path
	
	def __contains__(self, key):
		self.load()
		return dict.__contains__(self, key)

	def __getitem__(self, name):
		self.load()
		return dict.__getitem__(self, name)

	def __iter__(self):
		self.load()
		return dict.__iter__(self)
	
	def get(self, name, fallback=None):
		self.load()
		return dict.get(self, name, fallback)

	def load(self):
		if not self.loaded:
			self.loaded = True
			try:
				langfile = open(self.path, "rU")
				try:
					ltxt = unicode(langfile.read(), "UTF-8")
					self.update(demjson.decode(ltxt))
				except (UnicodeDecodeError, 
						demjson.JSONDecodeError), exception:
					handle_error(
						"Warning - language file '%s': %s" % 
						(self.path, 
						exception.args[0].capitalize() if 
						type(exception) == demjson.JSONDecodeError 
						else str(exception)))
			except Exception, exception:
				handle_error("Warning - language file '%s': %s" % 
							 (self.path, str(exception)))
			else:
				langfile.close()


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
				safe_print("Warning - directory '%s' listing failed: %s" % 
						   (langdir, str(exception)))
			else:
				for filename in langfiles:
					name, ext = os.path.splitext(filename)
					if ext.lower() == ".json" and name.lower() not in ldict:
						path = os.path.join(langdir, filename)
						ldict[name.lower()] = TranslationDict(path)
	if len(ldict) == 0:
		handle_error("Warning: No language files found. The following "
					 "places have been searched:\n%s" % "\n".join(langdirs))
	# else:
		# update_defaults()
	# lcode = getcode()
	# if not lcode in ldict:
		# # fall back to english
		# lcode = "en"
	# if lcode in ldict:
		# if set_wx_locale:
			# import wx
			# wx.Locale(getattr(wx, "LANGUAGE_" + ldict[lcode]["language_name"]))
			# import __builtin__
			# __builtin__.__dict__['_'] = wx.GetTranslation
		#locale.setlocale(locale.LC_ALL, ldict[lcode]["language_name"])


def update_defaults():
	defaults.update({
		"last_cal_path": os.path.join(storage, getstr("unnamed")),
		"last_cal_or_icc_path": os.path.join(storage, getstr("unnamed")),
		"last_filedialog_path": os.path.join(storage, getstr("unnamed")),
		"last_icc_path": os.path.join(storage, getstr("unnamed")),
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
		# if locale.getdefaultlocale()[0].split("_")[0].lower() != lcode:
			# locale.setlocale(locale.LC_ALL, ldict[lcode]["language_name"])
		lstr = ldict[lcode][id_str]
		if strvars:
			if type(strvars) not in (list, tuple):
				strvars = (strvars, )
			if lstr.count("%s") == len(strvars):
				lstr %= strvars
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
