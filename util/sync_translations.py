#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import StringIO
import codecs
import os
import sys
import textwrap

import ppdir

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root)

from DisplayCAL import demjson
from DisplayCAL import jsondict
from DisplayCAL import ordereddict
from DisplayCAL.safe_print import safe_print
from DisplayCAL.util_list import natsort
from DisplayCAL.util_os import listdir_re


def quote(obj):
	if isinstance(obj, basestring):
		return '"%s"' % obj.replace('\\', '\\\\').replace('"', '\\"').replace("\n", "\\n")
	else:
		return repr(obj)


def langmerge(infilename1, infilename2, outfilename):
	safe_print("Syncing", infilename1, "to", infilename2)
	dictin1 = jsondict.JSONDict(infilename1)
	dictin1.load()
	dictin2 = jsondict.JSONDict(infilename2)
	dictin2.load()
	
	added = []
	same = []
	for key, value in dictin2.iteritems():
		if not key in dictin1:
			dictin1[key] = value
			added.append(key.encode("UTF-8"))
			if not "*" + key in dictin1:
				safe_print("Added: '%s' '%s'" % (key, value))
		#elif dictin1[key] == value and not key.startswith("*") and not key.startswith("!") and value.strip():
			#same.append(key.encode("UTF-8"))
			#safe_print("Same: '%s' '%s'" % (key, value))
	
	merged = ordereddict.OrderedDict()
	merged["*"] = "Note to translators: Keys which are not yet translated are marked with a leading asterisk (*) and are indented with two tabs instead of one. Please remove the asterisk when translated."
	
	for key in natsort(dictin2.keys(), False):
		#merged[key] = dictin1[key]
		merged[key.encode("UTF-8")] = dictin1[key].encode("UTF-8")
	
	for key in natsort(dictin1.keys(), False):
		if key not in dictin2 and not key.startswith("*"):
			if not "ORPHANED KEY-VALUE PAIRS" in merged:
				merged["ORPHANED KEY-VALUE PAIRS"] = "Note to translators: Key-value pairs below this point are no longer used. You may consider removing them."
			merged[key.encode("UTF-8")] = dictin1[key].encode("UTF-8")
			safe_print("Orphan: '%s' '%s'" % (key, dictin1[key]))
	
	#json_out = demjson.encode(merged, compactly=False)
	#outfile = codecs.open(outfilename, "w", "UTF-8")
	#outfile.write(json_out)
	outstream = StringIO.StringIO()
	ppdir.ppdir(merged, stream=outstream, repr=quote)
	outstream.seek(0)
	formatted = outstream.read()
	for key in added:
		formatted = formatted.replace('"%s":' % key, '\t"*%s":' % key)
	for key in same:
		formatted = formatted.replace('"%s":' % key, '\t"*%s":' % key)
	safe_print("writing", outfilename)
	outfile = open(outfilename, "wb")
	outfile.write(formatted.replace(" " * 4, "\t"))
	outfile.close()


if __name__ == "__main__":
	if "-h" in sys.argv[1:] or "--help" in sys.argv[1:]:
		safe_print("Usage: %s" % os.path.basename(sys.argv[0]))
		safe_print("Synchronizes translations to en.json")
	else:
		for langfile in listdir_re(os.path.join(root, "DisplayCAL", "lang"),
								   r"^\w+\.json$"):
			if langfile != "en.json":
				langmerge(os.path.join("lang", langfile),
						  os.path.join("lang", "en.json"),
						  os.path.join(root, "DisplayCAL", "lang", langfile))
				safe_print("")
