#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import codecs
import os
import sys

import ppdir

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root)

from DisplayCAL import jsondict
from DisplayCAL.safe_print import safe_print
from DisplayCAL.util_list import natsort
from DisplayCAL.util_os import safe_glob
from DisplayCAL.util_str import wrap


def convert(infilename):
	dictin = jsondict.JSONDict(infilename)
	dictin.load()

	outfilename = os.path.splitext(infilename)[0] + ".yaml"
	with open(outfilename, "wb") as outfile:
		for key in natsort(dictin.keys(), False):
			outfile.write('"%s": |-\n' % key.encode("UTF-8"))
			for line in dictin[key].split("\n"):
				# Do not use splitlines, returns empty list for empty string
				outfile.write("  %s\n" % line.encode("UTF-8"))


if __name__ == "__main__":
	if "-h" in sys.argv[1:] or "--help" in sys.argv[1:]:
		safe_print("Usage: %s" % os.path.basename(sys.argv[0]))
		safe_print("Converts translation JSON files to YAML files")
	else:
		for langfile in safe_glob(os.path.join(root, "DisplayCAL", "lang",
											   "*.json")):
			convert(langfile)
