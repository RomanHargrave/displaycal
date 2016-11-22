#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import StringIO
import os
import re
import sys

import ppdir

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root)

from DisplayCAL import jsondict
from DisplayCAL import ordereddict
from DisplayCAL.config import confighome
from DisplayCAL.safe_print import safe_print
from DisplayCAL.util_os import listdir_re


def quote(obj):
	if isinstance(obj, basestring):
		return '"%s"' % obj.replace('\\', '\\\\').replace('"', '\\"').replace("\n", "\\n")
	else:
		return repr(obj)


def find_potentially_unused_strings(filepath, keys):
	ldict = jsondict.JSONDict(filepath)

	merged = ordereddict.OrderedDict()
	merged["*"] = ""

	count = 0
	for key in sorted(ldict.keys()):
		merged[key.encode("UTF-8")] = ldict[key].encode("UTF-8")
		if not key.startswith("*") and not key.startswith("!") and not key in keys:
			safe_print("Found potentially unused '%s' in '%s'" %
					   (key, os.path.basename(filepath)))
			count += 1
	safe_print("Found %i potentially unused keys in '%s'" %
			   (count, os.path.basename(filepath)))


def main():
	keys = {}
	for (dirpath, dirnames, filenames) in os.walk(os.path.join(root, "DisplayCAL")):
		for filename in filenames:
			ext = os.path.splitext(filename)[1][1:]
			if ext not in ("py", "pyw", "xrc"):
				continue
			filepath = os.path.join(dirpath, filename)
			with open(filepath, "rb") as py:
				code = py.read()
			if ext == "xrc":
				pattern = r'<(?:label|title|tooltip)>([^>]+)</(?:label|title|tooltip)>'
			else:
				pattern = r'(?:getstr\(|(?:lstr|msg|msgid|msgstr|title)\s*=)\s*["\']([^"\']+)["\']'
			for match in re.findall(pattern, code):
				if not match in keys:
					keys[match.decode("UTF-8")] = 1
	safe_print(len(keys), "unique keys in py/pyw/xrc")
	usage_path = os.path.join(confighome, "localization_usage.json")
	if os.path.isfile(usage_path):
		usage = jsondict.JSONDict(usage_path)
		usage.load()
		keys.update(usage)
		safe_print(len(keys), "unique keys after merging localization_usage.json")
	for langfile in listdir_re(os.path.join(root, "DisplayCAL", "lang"),
							   r"^\w+\.json$"):
		if langfile != "en.json":
			find_potentially_unused_strings(os.path.join("lang", langfile), keys.keys())
			raw_input("Press any key to continue")
			safe_print("")


if __name__ == "__main__":
	if "-h" in sys.argv[1:] or "--help" in sys.argv[1:]:
		safe_print("Usage: %s" % os.path.basename(sys.argv[0]))
		safe_print("Finds potentially unused strings in localizations")
	else:
		main()
