#!/usr/bin/env python
# -*- coding: utf-8 -*-

import StringIO
import codecs
import os
import sys
import textwrap

import ppdir

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dispcalGUI import demjson
from dispcalGUI import jsondict
from dispcalGUI import ordereddict
from dispcalGUI.safe_print import safe_print


def quote(obj):
	if isinstance(obj, basestring):
		return '"%s"' % obj.replace('\\', '\\\\').replace('"', '\\"').replace("\n", "\\n")
	else:
		return repr(obj)


def jsonmerge(infilename1, infilename2, outfilename):
	dictin1 = jsondict.JSONDict(infilename1)
	dictin1.load()
	dictin2 = jsondict.JSONDict(infilename2)
	dictin2.load()
	
	added = []
	for key, value in dictin2.iteritems():
		if not key in dictin1:
			dictin1[key] = value
			added.append(key.encode("UTF-8"))
			safe_print("Added: '%s' '%s'" % (key, value))
	
	merged = ordereddict.OrderedDict()
	merged["*"] = "Note to translators: Keys which are not yet translated are marked with a leading asterisk (*) and are indented with two tabs instead of one. Please remove the asterisk when translated."
	
	for key in sorted(dictin2.keys()):
		#merged[key] = dictin1[key]
		merged[key.encode("UTF-8")] = dictin1[key].encode("UTF-8")
	
	for key in sorted(dictin1.keys()):
		if key not in dictin2 and not key.startswith("*"):
			if not "ORPHANED KEY-VALUE PAIRS" in merged:
				merged["ORPHANED KEY-VALUE PAIRS"] = "Note to translators: Key-value pairs below this point may no longer be used (but there are exceptions, all keys from ICCProfile.ICCProfile.get_info will be listed as orphaned). You may consider removing them."
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
		formatted = formatted.replace('"%s"' % key, '\t"*%s"' % key)
	outfile = open(outfilename, "wb")
	outfile.write(formatted.replace(" " * 4, "\t"))
	outfile.close()


if __name__ == "__main__":
	if sys.argv[1:] and not "-h" in sys.argv[1:] and not "--help" in sys.argv[1:]:
		jsonmerge(*sys.argv[1:])
	else:
		print "Usage: %s infilename1 infilename2 outfilename" % os.path.basename(sys.argv[0])
		print textwrap.fill("Merges file1 with file2 (adds all keys from file2"
							" not present in file1) and writes to outfile", 
							width=80)
